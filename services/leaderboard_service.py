"""
编程题排行榜服务 - 记录和查询用户对同一道题的答题情况

核心功能：
1. 记录用户答题成绩到SQLite数据库
2. 按题目ID查询排行榜
3. 支持多种排序方式（分数、时间等）
4. 保护用户隐私（可选匿名显示）
"""

import sqlite3
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class LeaderboardService:
    """编程题排行榜服务 - 基于SQLite数据库"""
    
    def __init__(self, db_path: str = None):
        """
        初始化排行榜服务
        
        Args:
            db_path: SQLite数据库文件路径，默认使用项目根目录下的数据库
        """
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent
            db_path = project_root / "leaderboard_data" / "leaderboard.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        print(f"✅ LeaderboardService 初始化完成，数据库路径: {db_path}")
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建提交记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                passed_tests TEXT NOT NULL,
                submission_time TEXT NOT NULL,
                language TEXT DEFAULT 'python',
                code_preview TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        
        # ★★★ 数据库迁移：为已存在的表添加 full_code 字段 ★★★
        try:
            cursor.execute('ALTER TABLE submissions ADD COLUMN full_code TEXT')
            print("✅ 数据库迁移：已添加 full_code 字段")
        except Exception:
            # 字段已存在，忽略错误
            pass
        
        # 创建索引优化查询性能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_problem_id 
            ON submissions(problem_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_id 
            ON submissions(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_problem_score 
            ON submissions(problem_id, score DESC)
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ 数据库表结构初始化完成")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn
    
    def record_submission(
        self,
        problem_id: str,
        user_id: str,
        score: int,
        verdict: str,
        passed_tests: str,
        submission_time: Optional[str] = None,
        code_snippet: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        记录用户答题提交

        Args:
            problem_id: 题目ID
            user_id: 用户ID
            score: 得分 (0-100)
            verdict: 评判结果 (Accepted/Wrong Answer等)
            passed_tests: 通过的测试用例 (如 "2/2")
            submission_time: 提交时间（ISO格式），默认为当前时间
            code_snippet: 代码片段（可选，用于展示）
            language: 编程语言

        Returns:
            Dict: {"success": bool, "submission_id": int or None, "error": str or None}
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 构建提交记录
            submission_time = submission_time or datetime.now().isoformat()
            code_preview = self._extract_code_preview(code_snippet) if code_snippet else None
            full_code = code_snippet  # ★★★ 保存完整代码 ★★★
            created_at = datetime.now().isoformat()

            # 插入记录
            cursor.execute('''
                INSERT INTO submissions
                (problem_id, user_id, score, verdict, passed_tests,
                 submission_time, language, code_preview, full_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (problem_id, user_id, score, verdict, passed_tests,
                  submission_time, language, code_preview, full_code, created_at))

            submission_id = cursor.lastrowid
            conn.commit()
            conn.close()

            print(f"✅ 已记录提交: {user_id} - {problem_id} - {score}分 (id={submission_id})")
            return {"success": True, "submission_id": submission_id}

        except Exception as e:
            print(f"❌ 记录提交失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "submission_id": None, "error": str(e)}
    
    def get_leaderboard(
        self,
        problem_id: str,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取题目排行榜（每个用户只显示最高分记录）
        
        Args:
            problem_id: 题目ID
            limit: 返回的记录数量限制
            user_id: 当前用户ID（用于标记当前位置）
            
        Returns:
            Dict: 排行榜数据
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 查询总提交数
            cursor.execute('SELECT COUNT(*) FROM submissions WHERE problem_id = ?', (problem_id,))
            total_submissions = cursor.fetchone()[0]
            
            # 查询独立用户数
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM submissions WHERE problem_id = ?', (problem_id,))
            unique_users = cursor.fetchone()[0]
            
            # 查询排行榜（每个用户只显示最高分，同分按最新提交时间）
            cursor.execute('''
                SELECT s.id, s.user_id, s.score, s.verdict, s.passed_tests, 
                       s.submission_time, s.language, s.code_preview
                FROM submissions s
                WHERE s.problem_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM submissions s2
                    WHERE s2.problem_id = s.problem_id
                    AND s2.user_id = s.user_id
                    AND (s2.score > s.score OR (s2.score = s.score AND s2.submission_time > s.submission_time))
                )
                ORDER BY s.score DESC, s.submission_time ASC
                LIMIT ?
            ''', (problem_id, limit))
            
            rows = cursor.fetchall()
            
            # 转换为字典列表
            top_submissions = []
            for row in rows:
                top_submissions.append({
                    "submission_id": row["id"],
                    "user_id": row["user_id"],
                    "score": row["score"],
                    "verdict": row["verdict"],
                    "passed_tests": row["passed_tests"],
                    "submission_time": row["submission_time"],
                    "language": row["language"],
                    "code_preview": row["code_preview"]
                })
            
            # 查找当前用户的排名（基于去重后的记录）
            user_rank = None
            if user_id:
                cursor.execute('''
                    SELECT COUNT(*) + 1 as rank
                    FROM (
                        SELECT user_id, MAX(score) as max_score,
                               MIN(submission_time) as min_time
                        FROM submissions
                        WHERE problem_id = ?
                        GROUP BY user_id
                    ) u
                    WHERE u.max_score > (
                        SELECT MAX(score) FROM submissions 
                        WHERE problem_id = ? AND user_id = ?
                    )
                ''', (problem_id, problem_id, user_id))
                
                result = cursor.fetchone()
                if result:
                    user_rank = result[0]
            
            conn.close()
            
            return {
                "success": True,
                "problem_id": problem_id,
                "total_submissions": total_submissions,
                "unique_users": unique_users,
                "top_submissions": top_submissions,
                "user_rank": user_rank,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ 获取排行榜失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_best_score(self, problem_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户在某题的最佳成绩
        
        Args:
            problem_id: 题目ID
            user_id: 用户ID
            
        Returns:
            Dict: 最佳成绩记录，如果没有则返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 查询该用户的最高分记录
            cursor.execute('''
                SELECT user_id, score, verdict, passed_tests, 
                       submission_time, language, code_preview
                FROM submissions
                WHERE problem_id = ? AND user_id = ?
                ORDER BY score DESC, submission_time ASC
                LIMIT 1
            ''', (problem_id, user_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "user_id": row["user_id"],
                    "score": row["score"],
                    "verdict": row["verdict"],
                    "passed_tests": row["passed_tests"],
                    "submission_time": row["submission_time"],
                    "language": row["language"],
                    "code_preview": row["code_preview"]
                }
            
            return None
            
        except Exception as e:
            print(f"❌ 获取用户最佳成绩失败: {e}")
            return None
    
    def get_problem_statistics(self, problem_id: str) -> Dict[str, Any]:
        """
        获取题目的统计信息
        
        Args:
            problem_id: 题目ID
            
        Returns:
            Dict: 统计信息
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 查询总提交数
            cursor.execute('SELECT COUNT(*) FROM submissions WHERE problem_id = ?', (problem_id,))
            total = cursor.fetchone()[0]
            
            if total == 0:
                conn.close()
                return {
                    "problem_id": problem_id,
                    "total_submissions": 0,
                    "unique_users": 0,
                    "average_score": 0,
                    "acceptance_rate": 0
                }
            
            # 查询独立用户数
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM submissions WHERE problem_id = ?', (problem_id,))
            unique_users = cursor.fetchone()[0]
            
            # 查询平均分
            cursor.execute('SELECT AVG(score) FROM submissions WHERE problem_id = ?', (problem_id,))
            avg_score = cursor.fetchone()[0]
            
            # 查询通过数
            cursor.execute('SELECT COUNT(*) FROM submissions WHERE problem_id = ? AND verdict = ?', 
                          (problem_id, 'Accepted'))
            accepted = cursor.fetchone()[0]
            
            # 查询最高分和最低分
            cursor.execute('SELECT MAX(score), MIN(score) FROM submissions WHERE problem_id = ?', 
                          (problem_id,))
            row = cursor.fetchone()
            highest_score = row[0]
            lowest_score = row[1]
            
            conn.close()
            
            acceptance_rate = (accepted / total * 100) if total > 0 else 0
            
            return {
                "problem_id": problem_id,
                "total_submissions": total,
                "unique_users": unique_users,
                "average_score": round(avg_score, 2),
                "acceptance_rate": round(acceptance_rate, 2),
                "highest_score": highest_score,
                "lowest_score": lowest_score
            }
            
        except Exception as e:
            print(f"❌ 获取题目统计失败: {e}")
            return {"error": str(e)}
    
    def _extract_code_preview(self, code: str, max_lines: int = 10) -> str:
        """提取代码预览（前N行）"""
        if not code:
            return ""
        
        lines = code.strip().split('\n')
        preview_lines = lines[:max_lines]
        preview = '\n'.join(preview_lines)
        
        if len(lines) > max_lines:
            preview += f"\n... ({len(lines) - max_lines} more lines)"
        
        return preview
    
    def get_full_code(self, submission_id: int, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取提交的完整代码（需要验证权限）
        
        Args:
            submission_id: 提交记录ID
            user_id: 当前用户ID（用于权限验证）
            
        Returns:
            Dict: 包含完整代码的信息，或None（无权限）
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 查询提交记录
            cursor.execute('''
                SELECT id, problem_id, user_id, score, verdict, 
                       submission_time, language, full_code
                FROM submissions
                WHERE id = ?
            ''', (submission_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {"success": False, "error": "提交记录不存在"}
            
            # 权限验证：只能查看自己的代码，或者其他人的代码（公开）
            # 这里允许查看所有用户的代码（排行榜公开性质）
            
            return {
                "success": True,
                "submission_id": row["id"],
                "problem_id": row["problem_id"],
                "user_id": row["user_id"],
                "score": row["score"],
                "verdict": row["verdict"],
                "submission_time": row["submission_time"],
                "language": row["language"],
                "full_code": row["full_code"]
            }
            
        except Exception as e:
            print(f"❌ 获取完整代码失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_submission_by_id(self, submission_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取提交记录（内部使用，不做权限验证）
        
        Args:
            submission_id: 提交记录ID
            
        Returns:
            Dict: 提交记录字典，或None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, problem_id, user_id, score, verdict, 
                       passed_tests, submission_time, language, full_code
                FROM submissions
                WHERE id = ?
            ''', (submission_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                "id": row["id"],
                "submission_id": row["id"],
                "problem_id": row["problem_id"],
                "user_id": row["user_id"],
                "score": row["score"],
                "verdict": row["verdict"],
                "passed_tests": row["passed_tests"],
                "submission_time": row["submission_time"],
                "language": row["language"],
                "full_code": row["full_code"]
            }
            
        except Exception as e:
            print(f"❌ 获取提交记录失败: {e}")
            return None
    
    def clear_leaderboard(self, problem_id: str) -> bool:
        """
        清空题目的排行榜（管理员功能）
        
        Args:
            problem_id: 题目ID
            
        Returns:
            bool: 是否清空成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM submissions WHERE problem_id = ?', (problem_id,))
            conn.commit()
            conn.close()
            
            print(f"✅ 已清空题目 {problem_id} 的排行榜")
            return True
        except Exception as e:
            print(f"❌ 清空排行榜失败: {e}")
            return False
    
    def get_problem_data(self, problem_id: str) -> Optional[Dict[str, Any]]:
        """
        获取题目相关数据（用于比较功能）
        
        Args:
            problem_id: 题目ID
            
        Returns:
            Dict: 题目数据，包含统计信息等
        """
        try:
            statistics = self.get_problem_statistics(problem_id)
            if statistics.get("error"):
                return None
            
            return {
                "problem_id": problem_id,
                "statistics": statistics,
                "title": f"题目 {problem_id}"
            }
        except Exception as e:
            print(f"❌ 获取题目数据失败: {e}")
            return None
    
    def get_user_submissions(self, problem_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取用户在某题目上的所有提交记录（按时间倒序）
        
        Args:
            problem_id: 题目ID
            user_id: 用户ID
            
        Returns:
            Dict: 用户提交记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, problem_id, user_id, score, verdict, passed_tests, 
                       submission_time, language, code_preview
                FROM submissions
                WHERE problem_id = ? AND user_id = ?
                ORDER BY submission_time DESC
            ''', (problem_id, user_id))
            
            rows = cursor.fetchall()
            conn.close()
            
            submissions = []
            for row in rows:
                submissions.append({
                    "submission_id": row["id"],
                    "problem_id": row["problem_id"],
                    "user_id": row["user_id"],
                    "score": row["score"],
                    "verdict": row["verdict"],
                    "passed_tests": row["passed_tests"],
                    "submission_time": row["submission_time"],
                    "language": row["language"],
                    "code_preview": row["code_preview"]
                })
            
            return {
                "success": True,
                "problem_id": problem_id,
                "user_id": user_id,
                "submissions": submissions
            }
            
        except Exception as e:
            print(f"❌ 获取用户提交记录失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
