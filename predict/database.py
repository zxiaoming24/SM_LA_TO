"""
数据库模型和操作模块
用于存储和查询用户代码提交记录
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
import os

# 数据库配置
# 必须通过环境变量 DATABASE_URL 设置，禁止在代码中硬编码密码
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError(
        "环境变量 DATABASE_URL 未设置。请设置数据库连接字符串，例如：\n"
        "export DATABASE_URL='mysql+pymysql://user:password@localhost:3306/code_db'"
    )

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


class CodeSubmission(Base):
    """代码提交记录表"""
    __tablename__ = 'code_submissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='提交ID')
    user_id = Column(String(50), nullable=False, index=True, comment='用户ID')
    user_name = Column(String(100), nullable=False, comment='用户姓名')
    problem_id = Column(String(50), nullable=False, index=True, comment='题目ID')
    problem_title = Column(String(200), comment='题目标题')
    language = Column(String(20), default='python', comment='编程语言')
    code = Column(Text, nullable=False, comment='用户代码')
    score = Column(Integer, default=0, comment='得分')
    verdict = Column(String(50), default='Unknown', comment='评判结果')
    submit_time = Column(DateTime, default=datetime.now, comment='提交时间')
    
    # 评判详情
    passed_tests = Column(Integer, default=0, comment='通过的测试用例数')
    total_tests = Column(Integer, default=0, comment='总测试用例数')
    analysis = Column(Text, comment='详细分析（JSON格式）')
    bugs = Column(Text, comment='发现的bug（JSON数组）')
    suggestions = Column(Text, comment='改进建议（JSON数组）')
    completeness_check = Column(Text, comment='完整性检查（JSON对象）')
    
    # 索引
    __table_args__ = (
        Index('idx_user_problem', 'user_id', 'problem_id'),
        Index('idx_problem_score', 'problem_id', 'score'),
        Index('idx_submit_time', 'submit_time'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'problem_id': self.problem_id,
            'problem_title': self.problem_title,
            'language': self.language,
            'code': self.code,
            'score': self.score,
            'verdict': self.verdict,
            'submit_time': self.submit_time.isoformat() if self.submit_time else None,
            'passed_tests': self.passed_tests,
            'total_tests': self.total_tests,
            'analysis': json.loads(self.analysis) if self.analysis else {},
            'bugs': json.loads(self.bugs) if self.bugs else [],
            'suggestions': json.loads(self.suggestions) if self.suggestions else [],
            'completeness_check': json.loads(self.completeness_check) if self.completeness_check else {}
        }
    
    @classmethod
    def from_judge_result(cls, user_id: str, user_name: str, problem_id: str, 
                          problem_title: str, code: str, language: str,
                          judge_result: dict):
        """从评判结果创建提交记录"""
        return cls(
            user_id=user_id,
            user_name=user_name,
            problem_id=problem_id,
            problem_title=problem_title,
            language=language,
            code=code,
            score=judge_result.get('score', 0),
            verdict=judge_result.get('verdict', 'Unknown'),
            passed_tests=judge_result.get('passed_tests', 0),
            total_tests=judge_result.get('total_tests', 0),
            analysis=json.dumps(judge_result.get('analysis', {}), ensure_ascii=False),
            bugs=json.dumps(judge_result.get('bugs', []), ensure_ascii=False),
            suggestions=json.dumps(judge_result.get('suggestions', []), ensure_ascii=False),
            completeness_check=json.dumps(judge_result.get('completeness_check', {}), ensure_ascii=False)
        )


def init_db():
    """初始化数据库（创建表）"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库初始化完成")


def get_db():
    """获取数据库会话（依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SubmissionRepository:
    """提交记录数据仓库"""
    
    def __init__(self):
        self.SessionLocal = SessionLocal
    
    def save_submission(self, submission: CodeSubmission) -> int:
        """保存提交记录，返回提交ID"""
        db = self.SessionLocal()
        try:
            db.add(submission)
            db.commit()
            db.refresh(submission)
            return submission.id
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_submission_by_id(self, submission_id: int) -> CodeSubmission:
        """根据ID获取提交记录"""
        db = self.SessionLocal()
        try:
            return db.query(CodeSubmission).filter(
                CodeSubmission.id == submission_id
            ).first()
        finally:
            db.close()
    
    def get_submissions_by_problem(self, problem_id: str) -> list:
        """获取某题目的所有提交记录"""
        db = self.SessionLocal()
        try:
            submissions = db.query(CodeSubmission).filter(
                CodeSubmission.problem_id == problem_id
            ).order_by(
                CodeSubmission.score.desc(),
                CodeSubmission.submit_time.asc()
            ).all()
            return [sub.to_dict() for sub in submissions]
        finally:
            db.close()
    
    def get_submissions_by_user_and_problem(self, user_id: str, problem_id: str) -> list:
        """获取某用户在某题目上的所有提交"""
        db = self.SessionLocal()
        try:
            submissions = db.query(CodeSubmission).filter(
                CodeSubmission.user_id == user_id,
                CodeSubmission.problem_id == problem_id
            ).order_by(
                CodeSubmission.submit_time.desc()
            ).all()
            return [sub.to_dict() for sub in submissions]
        finally:
            db.close()
    
    def get_ranking(self, problem_id: str, limit: int = 50) -> list:
        """获取某题目的排行榜（前N名）"""
        db = self.SessionLocal()
        try:
            # 每个用户只取最高分
            from sqlalchemy import func
            
            # 先获取每个用户的最高分
            max_scores = db.query(
                CodeSubmission.user_id,
                CodeSubmission.user_name,
                func.max(CodeSubmission.score).label('max_score'),
                func.min(CodeSubmission.submit_time).label('best_time')  #  要是使用的话，应该需要修改为起始时间，终止时间 之间的差值
            ).filter(
                CodeSubmission.problem_id == problem_id
            ).group_by(
                CodeSubmission.user_id,
                CodeSubmission.user_name
            ).order_by(
                func.max(CodeSubmission.score).desc(),
                func.min(CodeSubmission.submit_time).asc()
            ).limit(limit).all()
            
            ranking = []
            for rank, (user_id, user_name, max_score, best_time) in enumerate(max_scores, 1):
                ranking.append({
                    'rank': rank,
                    'user_id': user_id,
                    'user_name': user_name,
                    'score': max_score,
                    'best_time': best_time.isoformat() if best_time else None,
                    'problem_id': problem_id
                })
            
            return ranking
        finally:
            db.close()
    
    def get_user_best_submission(self, user_id: str, problem_id: str) -> CodeSubmission:
        """获取用户在某题目上的最佳提交"""
        db = self.SessionLocal()
        try:
            return db.query(CodeSubmission).filter(
                CodeSubmission.user_id == user_id,
                CodeSubmission.problem_id == problem_id
            ).order_by(
                CodeSubmission.score.desc(),
                CodeSubmission.submit_time.asc()
            ).first()
        finally:
            db.close()


# 创建全局数据仓库实例
submission_repo = SubmissionRepository()
