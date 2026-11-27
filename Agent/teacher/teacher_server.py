"""
teacher_server.py - 教师端 REST API

提供教师身份下的核心操作接口：
- 班级管理：创建/列表/加学生/查学生
- 作业管理：创建/列表/详情
- 提交批改：查提交列表/手动批改
- 学情查看：班级学情概览/学生提交历史

挂载到 api_server.py 使用：
    from Agent.teacher.teacher_server import teacher_router
    app.include_router(teacher_router, prefix="/teacher")

身份校验暂未实现，teacher_id 由前端 Query 传入（约定 teacher_xxx），后续可加 Depends 校验。
"""

import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from . import teacher_db

teacher_router = APIRouter()


# ==================== 请求模型 ====================

class ClassCreateRequest(BaseModel):
    class_name: str = Field(..., description="班级名称")
    description: str = Field("", description="班级描述")
    teacher_id: str = Field(..., description="教师ID（如 teacher_001）")


class AddStudentsRequest(BaseModel):
    student_ids: List[str] = Field(..., description="要加入班级的学生ID列表")


class HomeworkCreateRequest(BaseModel):
    class_id: str = Field(..., description="所属班级ID")
    teacher_id: str = Field(..., description="教师ID")
    title: str = Field(..., description="作业标题")
    description: str = Field("", description="作业说明")
    question_ids: List[str] = Field(default_factory=list, description="题目ID列表")
    auto_grade: bool = Field(True, description="是否启用客观题自动批改")
    due_at: Optional[str] = Field(None, description="截止时间 ISO 字符串")


class GradeRequest(BaseModel):
    manual_score: float = Field(..., description="教师手动评分", ge=0, le=100)
    teacher_comment: str = Field("", description="教师评语")


# ==================== 班级管理 ====================

@teacher_router.post("/classes", summary="创建班级")
def create_class(req: ClassCreateRequest):
    class_id = f"cls_{uuid.uuid4().hex[:12]}"
    result = teacher_db.create_class(
        teacher_id=req.teacher_id,
        class_id=class_id,
        class_name=req.class_name,
        description=req.description
    )
    return {"success": True, "data": result}


@teacher_router.get("/classes", summary="列出教师的所有班级")
def list_classes(teacher_id: str = Query(..., description="教师ID")):
    rows = teacher_db.list_classes(teacher_id)
    return {"success": True, "data": rows}


@teacher_router.post("/classes/{class_id}/students", summary="批量加入学生到班级")
def add_students(class_id: str, req: AddStudentsRequest):
    # 校验班级存在
    if not _class_exists(class_id):
        raise HTTPException(status_code=404, detail=f"班级不存在: {class_id}")
    added = teacher_db.add_students_to_class(class_id, req.student_ids)
    return {"success": True, "data": {"class_id": class_id, "added_count": added}}


@teacher_router.get("/classes/{class_id}/students", summary="列出班级所有学生")
def list_class_students(class_id: str):
    if not _class_exists(class_id):
        raise HTTPException(status_code=404, detail=f"班级不存在: {class_id}")
    rows = teacher_db.list_class_students(class_id)
    return {"success": True, "data": rows}


# ==================== 作业管理 ====================

@teacher_router.post("/homework", summary="创建作业")
def create_homework(req: HomeworkCreateRequest):
    if not _class_exists(req.class_id):
        raise HTTPException(status_code=404, detail=f"班级不存在: {req.class_id}")
    homework_id = f"hw_{uuid.uuid4().hex[:12]}"
    result = teacher_db.create_homework(
        teacher_id=req.teacher_id,
        class_id=req.class_id,
        homework_id=homework_id,
        title=req.title,
        description=req.description,
        question_ids=req.question_ids,
        auto_grade=req.auto_grade,
        due_at=req.due_at
    )
    return {"success": True, "data": result}


@teacher_router.get("/homework", summary="列出作业（可按教师或班级过滤）")
def list_homework(teacher_id: Optional[str] = Query(None),
                  class_id: Optional[str] = Query(None)):
    rows = teacher_db.list_homework(teacher_id=teacher_id, class_id=class_id)
    return {"success": True, "data": rows}


@teacher_router.get("/homework/{homework_id}", summary="获取作业详情")
def get_homework(homework_id: str):
    hw = teacher_db.get_homework(homework_id)
    if not hw:
        raise HTTPException(status_code=404, detail=f"作业不存在: {homework_id}")
    return {"success": True, "data": hw}


# ==================== 提交与批改 ====================

@teacher_router.get("/homework/{homework_id}/submissions", summary="列出某作业的所有提交")
def list_submissions(homework_id: str):
    if not teacher_db.get_homework(homework_id):
        raise HTTPException(status_code=404, detail=f"作业不存在: {homework_id}")
    rows = teacher_db.list_submissions(homework_id)
    return {"success": True, "data": rows}


@teacher_router.post("/submissions/{submission_id}/grade", summary="教师手动批改")
def grade_submission(submission_id: str, req: GradeRequest):
    result = teacher_db.grade_submission(
        submission_id=submission_id,
        manual_score=req.manual_score,
        teacher_comment=req.teacher_comment
    )
    return {"success": True, "data": result}


# ==================== 学情查询（只读） ====================

@teacher_router.get("/classes/{class_id}/progress", summary="班级学情概览")
def get_class_progress(class_id: str):
    if not _class_exists(class_id):
        raise HTTPException(status_code=404, detail=f"班级不存在: {class_id}")
    result = teacher_db.get_class_progress(class_id)
    return {"success": True, "data": result}


@teacher_router.get("/students/{student_id}/submissions", summary="查某学生的所有提交历史")
def get_student_submissions(student_id: str):
    rows = teacher_db.get_student_submissions(student_id)
    return {"success": True, "data": rows}


# ==================== 内部辅助 ====================

def _class_exists(class_id: str) -> bool:
    """快速判断班级是否存在"""
    with teacher_db._get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM classes WHERE class_id=?", (class_id,)
        ).fetchone()
    return row is not None


# ==================== AI 助手对话 ====================

class TeacherChatRequest(BaseModel):
    teacher_id: Optional[str] = Field(None, description="教师ID（注入工具调用上下文）")
    message: str = Field(..., description="教师输入的消息")


@teacher_router.post("/chat", summary="教师AI助手对话")
async def teacher_chat(request: TeacherChatRequest):
    """
    与教师AI助手对话，支持自然语言操作班级/作业/批改/学情。
    返回 SSE 流式响应，包含工具调用过程和最终回复。
    若 LLM 未配置，返回降级提示。
    """
    from fastapi.responses import StreamingResponse

    async def event_stream():
        try:
            from .teacher_helper_agent import get_teacher_helper_agent
            try:
                agent = get_teacher_helper_agent()
            except Exception as e:
                yield f'data: {json.dumps({"type":"error","content":f"AI助手初始化失败: {e}。请检查 LLM_API_KEY/LLM_PROVIDER 配置，或使用上方功能 Tab 操作。"}, ensure_ascii=False)}\n\n'
                yield "data: [DONE]\n\n"
                return
            async for event in agent.run_async(request.message, request.teacher_id):
                yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        except Exception as e:
            yield f'data: {json.dumps({"type":"error","content":str(e)}, ensure_ascii=False)}\n\n'
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
