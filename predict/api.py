"""
FastAPI 接口实现
提供代码提交、比较、排行榜等RESTful API
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env 环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

from predict.models import (
    CodeSubmissionRequest,
    CodeSubmissionResponse,
    ComparisonRequest,
    ComparisonResponse,
    RankingResponse,
    UserSubmissionsResponse,
    ErrorResponse
)
from predict.database import init_db, submission_repo, CodeSubmission
from predict.comparison_service import ComparisonService

# 创建FastAPI应用
app = FastAPI(
    title="编程练习系统API",
    description="提供代码提交、评判、比较和排行榜功能",
    version="1.0.0"
)

# 配置CORS（允许跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()

# 创建服务实例
comparison_service = ComparisonService()


@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "message": "编程练习系统API",
        "version": "1.0.0",
        "endpoints": {
            "submit": "/submit",
            "compare": "/compare",
            "ranking": "/ranking/{problem_id}",
            "user_submissions": "/submissions/{problem_id}/{user_id}"
        }
    }


@app.post("/submit", response_model=CodeSubmissionResponse)
async def submit_code(request: CodeSubmissionRequest):
    """
    提交代码并获取评判结果
    
    - **user_id**: 用户ID
    - **user_name**: 用户姓名
    - **problem_id**: 题目ID
    - **problem_data**: 题目完整信息
    - **code**: 用户提交的代码
    - **language**: 编程语言（默认python）
    """
    try:
        from Agent.children_agent.practice_agent import PracticeAgent
        
        print(f"\n📝 [API] 收到代码提交:")
        print(f"   用户: {request.user_name} ({request.user_id})")
        print(f"   题目: {request.problem_id}")
        print(f"   语言: {request.language}")
        
        # 1. 创建 PracticeAgent 实例
        practice_agent = PracticeAgent()
        
        # 2. 评判代码
        judge_result = practice_agent.judge_code(
            problem=request.problem_data,
            user_code=request.code,
            language=request.language
        )
        
        print(f"✅ 代码评判完成: {judge_result.get('verdict')} (得分: {judge_result.get('score')})")
        
        # 3. 保存提交记录到数据库
        submission = CodeSubmission.from_judge_result(
            user_id=request.user_id,
            user_name=request.user_name,
            problem_id=request.problem_id,
            problem_title=request.problem_title or request.problem_data.get('title', ''),
            code=request.code,
            language=request.language,
            judge_result=judge_result
        )
        
        submission_id = submission_repo.save_submission(submission)
        
        print(f"💾 提交记录已保存 (ID: {submission_id})")
        
        # 4. 返回结果
        return CodeSubmissionResponse(
            submission_id=submission_id,
            score=judge_result.get('score', 0),
            verdict=judge_result.get('verdict', 'Unknown'),
            passed_tests=judge_result.get('passed_tests', 0),
            total_tests=judge_result.get('total_tests', 0),
            message="提交成功"
        )
        
    except Exception as e:
        print(f"❌ 提交失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@app.post("/compare")
async def compare_solutions(request: ComparisonRequest):
    """
    比较两个用户的解法
    
    - **problem_data**: 题目完整信息
    - **submission_a_id**: 用户A的提交ID
    - **submission_b_id**: 用户B的提交ID
    """
    try:
        print(f"\n🔍 [API] 收到比较请求:")
        print(f"   提交A ID: {request.submission_a_id}")
        print(f"   提交B ID: {request.submission_b_id}")
        
        # 调用比较服务
        result = comparison_service.compare_two_solutions(
            problem_data=request.problem_data,
            submission_a_id=request.submission_a_id,
            submission_b_id=request.submission_b_id
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"❌ 比较失败: {e}")
        raise HTTPException(status_code=500, detail=f"比较失败: {str(e)}")


@app.get("/ranking/{problem_id}", response_model=RankingResponse)
async def get_ranking(problem_id: str, limit: int = 50):
    """
    获取某题目的排行榜
    
    - **problem_id**: 题目ID
    - **limit**: 返回的排名数量限制（默认50）
    """
    try:
        print(f"\n📊 [API] 获取排行榜: {problem_id}")
        
        # 调用比较服务获取排行榜
        result = comparison_service.get_ranking_with_details(
            problem_id=problem_id,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        print(f"❌ 获取排行榜失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取排行榜失败: {str(e)}")


@app.get("/submissions/{problem_id}/{user_id}", response_model=UserSubmissionsResponse)
async def get_user_submissions(problem_id: str, user_id: str):
    """
    获取某用户在某题目上的所有提交记录
    
    - **problem_id**: 题目ID
    - **user_id**: 用户ID
    """
    try:
        print(f"\n📋 [API] 获取用户提交记录:")
        print(f"   用户: {user_id}")
        print(f"   题目: {problem_id}")
        
        # 调用比较服务获取用户提交记录
        result = comparison_service.get_user_submissions_detail(
            user_id=user_id,
            problem_id=problem_id
        )
        
        return result
        
    except Exception as e:
        print(f"❌ 获取提交记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取提交记录失败: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
