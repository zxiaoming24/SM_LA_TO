"""
teacher_helper_agent.py - 教师端协助 Agent

为教师提供自然语言交互能力：
1. 解答教师端功能、字段含义等操作问题
2. 通过自然语言指令自动执行班级/作业/批改/学情查询操作
执行过程实时流式推送给前端可见。

架构仿 admin_helper_agent.py：
- Pydantic Input 模型定义工具 schema（供 bind_tools）
- _TOOL_FUNCTIONS 注册表（供执行时查找函数）
- 工具函数直接调用 teacher_db（同进程，无需 HTTP）
- LLM 支持 DeepSeek / Qwen，按环境变量 LLM_PROVIDER 选择
"""

import json
import os
import re
from typing import Dict, Any, Optional, AsyncGenerator, List

from pydantic import BaseModel, Field

try:
    from langchain_deepseek import ChatDeepSeek
except ImportError:
    ChatDeepSeek = None

try:
    from langchain_qwq import ChatQwen
except ImportError:
    ChatQwen = None

from . import teacher_db


# ==================== 系统提示 ====================

SYSTEM_PROMPT = """你是「教师工作台」的教学助手，协助教师完成教学管理操作。

## 你的能力
- 班级管理：创建班级、列出我的班级、查看班级学生名单
- 作业管理：创建作业（含题目ID列表、截止时间）、列出作业、查看作业详情
- 批改管理：查看某作业的所有提交、对学生提交进行手动批改（主观题评分+评语）
- 学情查看：班级学情概览（学生数、作业数、提交率、平均分）、查某学生的提交历史

## 回答规则
1. 教师问操作方式或字段含义时，基于系统实际情况回答
2. 教师给出具体指令（含完整信息）时，调用对应工具执行
3. 执行前先说明要做什么，执行后报告结果
4. 信息不完整时，询问缺少的关键信息（如班级ID、作业ID、学生ID）
5. 当教师提出任何管理操作需求（查看数据、布置作业、批改等）时，优先调用对应工具获取真实数据或执行操作，而非仅描述操作步骤
6. **只调用教师当前指令相关的一个工具**，不要同时调用多个不相关的工具
7. 报告学情数据时，对低提交率或低平均分的班级给出教学建议
"""


# ==================== 工具 Schema（Pydantic 模型） ====================

class ListClassesInput(BaseModel):
    """列出教师的所有班级"""
    teacher_id: str = Field(..., description="教师ID，如 teacher_001")


class GetClassProgressInput(BaseModel):
    """查看班级学情概览"""
    class_id: str = Field(..., description="班级ID")


class ListClassStudentsInput(BaseModel):
    """查看班级学生名单"""
    class_id: str = Field(..., description="班级ID")


class CreateClassInput(BaseModel):
    """创建班级"""
    teacher_id: str = Field(..., description="教师ID")
    class_name: str = Field(..., description="班级名称")
    description: str = Field("", description="班级描述")


class AddStudentsInput(BaseModel):
    """批量加入学生到班级"""
    class_id: str = Field(..., description="班级ID")
    student_ids: List[str] = Field(..., description="学生ID列表")


class CreateHomeworkInput(BaseModel):
    """创建作业"""
    teacher_id: str = Field(..., description="教师ID")
    class_id: str = Field(..., description="所属班级ID")
    title: str = Field(..., description="作业标题")
    description: str = Field("", description="作业说明")
    question_ids: List[str] = Field(default_factory=list, description="题目ID列表")
    auto_grade: bool = Field(True, description="是否启用客观题自动批改")
    due_at: Optional[str] = Field(None, description="截止时间 ISO 字符串")


class ListHomeworkInput(BaseModel):
    """列出作业"""
    teacher_id: Optional[str] = Field(None, description="按教师过滤")
    class_id: Optional[str] = Field(None, description="按班级过滤")


class ListSubmissionsInput(BaseModel):
    """查看某作业的所有提交"""
    homework_id: str = Field(..., description="作业ID")


class GradeSubmissionInput(BaseModel):
    """教师手动批改学生提交"""
    submission_id: str = Field(..., description="提交ID")
    manual_score: float = Field(..., description="教师手动评分 0-100", ge=0, le=100)
    teacher_comment: str = Field("", description="教师评语")


class GetStudentSubmissionsInput(BaseModel):
    """查某学生的所有提交历史"""
    student_id: str = Field(..., description="学生ID")


_TOOL_SCHEMAS = [
    ListClassesInput, GetClassProgressInput, ListClassStudentsInput,
    CreateClassInput, AddStudentsInput, CreateHomeworkInput,
    ListHomeworkInput, ListSubmissionsInput, GradeSubmissionInput,
    GetStudentSubmissionsInput,
]


# ==================== 工具函数 ====================

_TOOL_FUNCTIONS: Dict[str, callable] = {}


def _register_tool(func):
    _TOOL_FUNCTIONS[func.__name__] = func
    return func


@_register_tool
async def list_classes(teacher_id: str) -> Dict:
    """列出教师的所有班级（含学生数）"""
    return {"status": "success", "classes": teacher_db.list_classes(teacher_id)}


@_register_tool
async def get_class_progress(class_id: str) -> Dict:
    """查看班级学情概览：学生数、作业数、提交率、平均分"""
    return {"status": "success", "progress": teacher_db.get_class_progress(class_id)}


@_register_tool
async def list_class_students(class_id: str) -> Dict:
    """查看班级学生名单"""
    return {"status": "success", "students": teacher_db.list_class_students(class_id)}


@_register_tool
async def create_class(teacher_id: str, class_name: str, description: str = "") -> Dict:
    """创建班级"""
    import uuid as _uuid
    class_id = f"cls_{_uuid.uuid4().hex[:12]}"
    result = teacher_db.create_class(teacher_id, class_id, class_name, description)
    return {"status": "success", "class": result}


@_register_tool
async def add_students(class_id: str, student_ids: List[str]) -> Dict:
    """批量加入学生到班级"""
    added = teacher_db.add_students_to_class(class_id, student_ids)
    return {"status": "success", "added_count": added}


@_register_tool
async def create_homework(teacher_id: str, class_id: str, title: str,
                          description: str = "", question_ids: Optional[List[str]] = None,
                          auto_grade: bool = True, due_at: Optional[str] = None) -> Dict:
    """创建作业"""
    import uuid as _uuid
    homework_id = f"hw_{_uuid.uuid4().hex[:12]}"
    result = teacher_db.create_homework(
        teacher_id, class_id, homework_id, title, description,
        question_ids or [], auto_grade, due_at
    )
    return {"status": "success", "homework": result}


@_register_tool
async def list_homework(teacher_id: Optional[str] = None,
                        class_id: Optional[str] = None) -> Dict:
    """列出作业（可按教师或班级过滤）"""
    rows = teacher_db.list_homework(teacher_id=teacher_id, class_id=class_id)
    return {"status": "success", "homework": rows}


@_register_tool
async def list_submissions(homework_id: str) -> Dict:
    """查看某作业的所有提交"""
    rows = teacher_db.list_submissions(homework_id)
    return {"status": "success", "submissions": rows}


@_register_tool
async def grade_submission(submission_id: str, manual_score: float,
                           teacher_comment: str = "") -> Dict:
    """教师手动批改学生提交（主观题评分+评语）"""
    result = teacher_db.grade_submission(submission_id, manual_score, teacher_comment)
    return {"status": "success", "graded": result}


@_register_tool
async def get_student_submissions(student_id: str) -> Dict:
    """查某学生的所有提交历史"""
    rows = teacher_db.get_student_submissions(student_id)
    return {"status": "success", "submissions": rows}


# ==================== Agent 类 ====================

class TeacherHelperAgent:
    """教师端协助 Agent（支持 DeepSeek 和 Qwen 模型）"""

    def __init__(self):
        _api_key = os.getenv("LLM_API_KEY")
        _base_url = os.getenv("LLM_BASE_URL")
        _llm_provider = os.getenv("LLM_PROVIDER", "deepseek").lower()

        if _llm_provider == "qwen" and ChatQwen:
            self.llm = ChatQwen(
                model="qwen-flash", temperature=0.3,
                api_key=_api_key, base_url=_base_url
            ).bind_tools(_TOOL_SCHEMAS)
        elif ChatDeepSeek:
            self.llm = ChatDeepSeek(
                model="deepseek-v4-flash", temperature=0.3,
                api_key=_api_key, base_url=_base_url
            ).bind_tools(_TOOL_SCHEMAS)
        else:
            raise ImportError("请安装 langchain_deepseek 或 langchain_qwq，或检查 LLM_PROVIDER 配置")

        self.messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    @staticmethod
    def _model_name_to_func_name(model_name: str) -> str:
        """将 Pydantic 模型名称转换为工具函数名称（ListQuestionsInput → list_questions）"""
        if model_name.endswith('Input'):
            model_name = model_name[:-5]
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', model_name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    async def _execute_tool(self, tool_name: str, tool_args: dict, tool_call_id: str = ""):
        """执行工具并返回结果"""
        final_tool_name = tool_name
        result = None

        func = _TOOL_FUNCTIONS.get(tool_name)
        if not func:
            converted_name = self._model_name_to_func_name(tool_name)
            func = _TOOL_FUNCTIONS.get(converted_name)
            if func:
                final_tool_name = converted_name

        if func is not None:
            try:
                result = await func(**tool_args)
            except Exception as e:
                result = {"error": str(e)}
        else:
            result = {"error": f"未知工具: {tool_name}"}

        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False)
        })
        yield {"type": "tool_result", "tool": final_tool_name, "args": tool_args, "result": result}

    async def run_async(self, user_input: str, teacher_id: Optional[str] = None) -> AsyncGenerator:
        """流式运行 Agent：用户输入 → LLM → 工具调用 → 最终回复"""
        # 注入 teacher_id 到上下文（便于 LLM 调用工具时填参数）
        user_msg = user_input
        if teacher_id and "teacher_id" not in user_input.lower():
            user_msg = f"[当前教师ID: {teacher_id}]\n{user_input}"

        self.messages.append({"role": "user", "content": user_msg})

        # 工具调用循环（最多 5 轮，防止无限循环）
        for _ in range(5):
            response = await self.llm.ainvoke(self.messages)
            content = response.content if hasattr(response, 'content') else str(response)

            # 检查是否有工具调用
            tool_calls = getattr(response, 'tool_calls', None) or []
            if not tool_calls:
                # 无工具调用，输出最终回复
                self.messages.append({"role": "assistant", "content": content})
                yield {"type": "final", "content": content}
                return

            # 有工具调用，先输出 assistant 的工具调用意图
            self.messages.append({"role": "assistant", "content": content,
                                  "tool_calls": tool_calls})
            yield {"type": "assistant", "content": content, "tool_calls": tool_calls}

            # 执行每个工具调用
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id", "")
                async for chunk in self._execute_tool(tool_name, tool_args, tool_call_id):
                    yield chunk

        # 超过最大轮数，强制收尾
        final = await self.llm.ainvoke(self.messages)
        final_content = final.content if hasattr(final, 'content') else str(final)
        yield {"type": "final", "content": final_content}

    def reset(self):
        """重置对话历史"""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


# ==================== 单例工厂 ====================

_teacher_helper_agent: Optional[TeacherHelperAgent] = None


def get_teacher_helper_agent() -> TeacherHelperAgent:
    """获取教师协助 Agent 单例"""
    global _teacher_helper_agent
    if _teacher_helper_agent is None:
        _teacher_helper_agent = TeacherHelperAgent()
    return _teacher_helper_agent


if __name__ == "__main__":
    # 工具函数直连测试（不依赖 LLM）
    import asyncio

    async def _test():
        print("=== 工具函数直连测试 ===")
        r = await create_class(teacher_id="t1", class_name="测试班")
        print("create_class:", r)
        cid = r["class"]["class_id"]
        print("add_students:", await add_students(cid, ["s1", "s2"]))
        print("list_classes:", await list_classes("t1"))
        hw = await create_homework("t1", cid, "第一周", question_ids=["q1"])
        print("create_homework:", hw)
        print("list_homework:", await list_homework(teacher_id="t1"))
        print("get_class_progress:", await get_class_progress(cid))
        print("list_class_students:", await list_class_students(cid))

    asyncio.run(_test())
