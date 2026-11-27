"""
统一Agent测试API服务 - FastAPI
提供所有Agent的统一接口，支持动态参数传递
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uvicorn
import os
import sys
import json
import uuid
import asyncio
import threading
import time
from typing import Set

# 加载 Java 结果适配器
from services.java_result_adapter import (
    get_java_result, set_java_result, transform_to_java_result, cache_java_result
)

# 加载 .env 配置文件（可选依赖）
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env 配置文件已加载")
except ImportError:
    print("[WARN] python-dotenv 未安装，跳过 .env 加载（可通过 pip install python-dotenv 安装）")

# ==================== 全局后台任务追踪（防止退出时 Task was destroyed 警告）====================
# 方案：patch asyncio.create_task，自动追踪所有 create_task 创建的后台任务，
# 无需修改散落在各处的 29+ 处调用点。
_original_create_task = asyncio.create_task
_background_tasks: Set[asyncio.Task] = set()

def _tracked_create_task(coro, *, name=None, context=None):
    """自动追踪所有后台任务，程序退出时统一取消，防止 Task was destroyed 警告"""
    task = _original_create_task(coro, name=name, context=context)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

asyncio.create_task = _tracked_create_task


async def _cancel_pending_tasks():
    """取消所有仍在挂起的后台任务"""
    if not _background_tasks:
        return
    pending = [t for t in _background_tasks if not t.done()]
    if not pending:
        return
    print(f"   ⏳ 正在取消 {len(pending)} 个挂起后台任务...")
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    print(f"   ✅ 已清理 {len(pending)} 个后台任务")
# ========================================================================

# ==================== 学习计划查询专用线程池 ====================
# 与 asyncio 默认线程池隔离：默认线程池可能被长耗时后台任务（LLM 调用等）占满，
# 导致 /study_plan 查询路由在 run_in_executor(None, ...) 排队卡死。
from concurrent.futures import ThreadPoolExecutor
STUDY_PLAN_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="study_plan_api")

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Agent.main_controller import MasterController

# ==================== 管理端权重配置路由 ====================
from manager_server import manager_router

# ==================== 教师端路由 ====================
from Agent.teacher.teacher_server import teacher_router

# ==================== 多用户实例管理 ====================
# 每个用户独立持有 MasterController 实例（含独立的 DesAgent / ConductAgent）
# 避免单例带来的数据污染和并发安全问题

_USER_CONTROLLERS: Dict[str, MasterController] = {}
_USER_CONTROLLERS_LOCK = threading.Lock()

def _get_controller_for_user(user_id: str) -> MasterController:
    """获取或创建用户专属的 MasterController 实例
    
    关键设计：创建实例的耗时操作放在锁外面执行，
    避免一个用户初始化时阻塞其他所有用户的请求。
    
    使用双重检查锁定（Double-Checked Locking）防止竞态条件：
    两个并发线程不会为同一用户重复创建实例。
    """
    # 快速路径：已有实例直接返回（读锁，很快）
    with _USER_CONTROLLERS_LOCK:
        if user_id in _USER_CONTROLLERS:
            return _USER_CONTROLLERS[user_id]
    
    # ★★★ 耗时的初始化在锁外面执行，不阻塞其他用户 ★★★
    print(f"👤 为用户 {user_id} 创建独立的 MasterController 实例")
    controller = MasterController()
    
    # ★★★ 写回字典前再次检查，防止并发创建导致重复实例 ★★★
    with _USER_CONTROLLERS_LOCK:
        if user_id in _USER_CONTROLLERS:
            return _USER_CONTROLLERS[user_id]
        _USER_CONTROLLERS[user_id] = controller
        return controller


def _extract_suggestion_warning(result: Dict[str, Any]) -> str:
    """从任意深度的结果结构中提取 suggestion_warning"""
    if not isinstance(result, dict):
        return ""
    # 顶层直接命中
    if result.get("suggestion_warning"):
        return result["suggestion_warning"]
    # 检查 data.practice / data.data.practice 等嵌套路径
    for key in ("data", "problem", "practice"):
        child = result.get(key)
        if isinstance(child, dict):
            if child.get("suggestion_warning"):
                return child["suggestion_warning"]
            deeper = _extract_suggestion_warning(child)
            if deeper:
                return deeper
        # data 下可能还有一层
        if key == "data" and isinstance(child, dict):
            practice = child.get("practice")
            if isinstance(practice, dict) and practice.get("suggestion_warning"):
                return practice["suggestion_warning"]
    return ""


# ==================== FastAPI应用初始化 ====================

app = FastAPI(
    title="智能教育系统 - Agent测试API",
    description="统一的Agent测试接口，支持所有子Agent功能",
    version="1.0.0"
)

# ★★★ 优雅关闭：退出时取消所有挂起的后台任务，避免 Task was destroyed 警告 ★★★
@app.on_event("startup")
async def _startup_boost_executor():
    """启动时将默认线程池扩容到32线程，避免缓存/文件IO操作时耗尽"""
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=32, thread_name_prefix="asyncio_default")
    loop.set_default_executor(pool)
    print("  🚀 默认线程池已扩容至 32 线程")

@app.on_event("shutdown")
async def _shutdown_cleanup():
    print("\n🛑 服务关闭中，清理后台任务...")
    await _cancel_pending_tasks()
    print("✅ 服务关闭完成")
# ========================================================================

# 配置CORS（允许前端跨域访问）
# 通过 ALLOWED_ORIGINS 环境变量配置，多个域名用逗号分隔，默认为允许所有源
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ★★★ 挂载管理端权重配置路由 ★★★
app.include_router(manager_router, prefix="/admin")
print("✅ 管理端权重配置路由已挂载: /admin/*")

# ★★★ 挂载教师端路由 ★★★
app.include_router(teacher_router, prefix="/teacher")
print("✅ 教师端路由已挂载: /teacher/*")

# ★★★ 启用 LLM 缓存 ★★★
from utils.llm_config import enable_cache
enable_cache("exact")

# ★★★ 配置静态文件服务 ★★★
# 让前端可以访问TTS音频等静态资源
static_dir = os.path.join(os.path.dirname(__file__), "Agent", "children_agent", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    print(f"✅ 静态文件服务已启动: {static_dir}")
else:
    print(f"⚠️ 静态文件目录不存在: {static_dir}")

# ★★★ 社区上传文件静态服务 ★★★
COMMUNITY_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "community_data", "uploads")
os.makedirs(COMMUNITY_UPLOAD_DIR, exist_ok=True)
app.mount("/community/uploads", StaticFiles(directory=COMMUNITY_UPLOAD_DIR), name="community_uploads")
print(f"✅ 社区上传文件服务已启动: {COMMUNITY_UPLOAD_DIR}")

# ★★★ 笔记附件静态服务 ★★★
try:
    from services.note_service import get_attachment_static_dir
    note_upload_dir = get_attachment_static_dir()
    os.makedirs(note_upload_dir, exist_ok=True)
    app.mount("/note-uploads", StaticFiles(directory=note_upload_dir), name="note_uploads")
    print(f"✅ 笔记附件静态服务已启动: {note_upload_dir}")
except Exception as e:
    print(f"⚠️ 笔记附件服务初始化失败: {e}")

# ★★★ 本地视频文件静态服务 ★★★
VIDEO_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_knowledge", "video_data")
os.makedirs(VIDEO_DATA_DIR, exist_ok=True)
app.mount("/video-data", StaticFiles(directory=VIDEO_DATA_DIR), name="video_data")
print(f"✅ 视频文件静态服务已启动: {VIDEO_DATA_DIR}")

# ==================== 数据模型 ====================

class ChatRequest(BaseModel):
    """通用对话请求模型"""
    user_id: str = Field(..., description="用户ID（必需）", json_schema_extra={"example": "user_001"})
    user_input: str = Field(..., description="用户输入", json_schema_extra={"example": "你好，我叫张三"})
    session_id: Optional[str] = Field(None, description="会话ID（可选，用于区分不同会话）")


class ContextChatRequest(BaseModel):
    """上下文感知对话请求模型（智能球使用）"""
    user_id: str = Field(..., description="用户ID（必需）")
    user_input: str = Field(..., description="用户输入")
    page_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="前端页面上下文（页面名、标题、操作等）"
    )
    enable_tts: bool = Field(default=False, description="是否启用TTS语音合成")


class PageContextUpdateRequest(BaseModel):
    """前端页面上下文上报请求模型"""
    user_id: str = Field(..., description="用户ID")
    page: str = Field(..., description="当前页面标识（agent_test/study_plan/wrong_answers/community/assessment/companion）")
    title: Optional[str] = Field("", description="页面标题或当前内容标题")
    action: Optional[str] = Field("", description="当前操作（viewing/practicing/reviewing/browsing等）")
    detail: Optional[str] = Field("", description="操作详情（如题目ID、知识点名等）")


class AgentTestRequest(BaseModel):
    """Agent测试请求模型（支持动态参数）"""
    user_id: str = Field(..., description="用户ID（必需）")
    user_input: str = Field(..., description="用户输入/问题描述")
    
    # 动态参数：根据task_type不同，传入不同的额外参数
    task_type: Optional[str] = Field(
        None, 
        description="任务类型（可选，不填则自动识别）",
        json_schema_extra={"enum": ["practice", "question_gen", "doc_gen", "extension", "video", "mindmap", "chat"]}
    )
    
    # 额外参数（根据不同任务类型动态使用）
    extra_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="额外参数，根据任务类型动态传入",
        json_schema_extra={"example": {"course_name": "Python程序设计", "difficulty": "medium", "topic": "循环结构"}}
    )
    
    # TTS语音合成开关
    enable_tts: bool = Field(
        False,
        description="是否启用TTS语音合成（启用后返回结果中会包含 tts_audio_path 音频路径）"
    )
    
    # 用户确认覆盖采纳建议
    confirmed: bool = Field(
        False,
        description="用户是否已确认覆盖采纳建议（前端弹窗确认后传入）"
    )
    override_suggestions: bool = Field(
        False,
        description="是否忽略已采纳建议按用户要求执行（用户弹窗点取消时传入）"
    )


class TestConfig(BaseModel):
    """测试配置模型"""
    user_id: str = Field(..., description="用户ID")
    test_scenarios: List[Dict[str, Any]] = Field(..., description="测试场景列表")


class PPTRequest(BaseModel):
    """PPT生成请求模型"""
    user_id: str = Field(..., description="用户ID")
    topic: str = Field(..., description="PPT主题")
    style: str = Field(default="新中式科技风", description="设计风格")
    page_count: int = Field(default=4, ge=2, le=10, description="页数")


class CodeSubmissionRequest(BaseModel):
    """代码提交请求模型"""
    user_id: str = Field(..., description="用户ID")
    problem_id: str = Field(..., description="题目ID")
    code: str = Field(..., description="用户提交的代码")
    language: str = Field(default="python", description="编程语言")
    enable_tts: bool = Field(default=False, description="是否启用TTS语音反馈")
    problem: Optional[Dict[str, Any]] = Field(default=None, description="完整的题目数据（可选，附带后错题本能显示题目内容）")
    session_id: Optional[str] = Field(default=None, description="复习会话ID，有此ID时答案记录到会话而非直接更新遗忘曲线")


class VisualizationRequest(BaseModel):
    """算法可视化请求模型"""
    user_id: str = Field(..., description="用户ID")
    problem_id: str = Field(..., description="题目ID")
    user_code: str = Field(..., description="用户提交的代码")  # ★★★ 用户代码
    language: str = Field(default="python", description="编程语言")


# ★★★ 新增：排行榜相关请求模型 ★★★
class LeaderboardRequest(BaseModel):
    """排行榜查询请求模型"""
    problem_id: str = Field(..., description="题目ID")
    limit: int = Field(default=50, description="返回记录数量", ge=1, le=100)
    user_id: Optional[str] = Field(None, description="当前用户ID（用于标记位置）")


class TheoryAnswerSubmission(BaseModel):
    """理论题答案提交请求模型"""
    user_id: str = Field(..., description="用户ID")
    question_type: str = Field(..., description="题目类型", json_schema_extra={"enum": ["single_choice", "multiple_choice", "judge", "fill_blank", "short_answer"]})
    question: Dict[str, Any] = Field(..., description="题目完整数据（包含question、options、answer等字段）")
    user_answer: str = Field(..., description="用户提交的答案")
    knowledge_points: Optional[List[str]] = Field(default_factory=list, description="相关知识点")
    source: str = Field(default="theory", description="来源")
    record_id: Optional[str] = Field(default="", description="错题记录ID（从错题本重练时传入）")


class TheoryJudgeRequest(BaseModel):
    """理论题判题请求模型"""
    question_type: str = Field(..., description="题目类型", json_schema_extra={"enum": ["single_choice", "multiple_choice", "judge", "fill_blank", "short_answer"]})
    question: Dict[str, Any] = Field(..., description="单道题目完整数据（必须包含answer字段）")
    user_answer: str = Field(..., description="用户提交的答案")
    user_id: Optional[str] = Field(default=None, description="用户ID，提供时错误答案自动记入错题本")
    knowledge_points: Optional[List[str]] = Field(default=None, description="相关知识点")
    session_id: Optional[str] = Field(default=None, description="复习会话ID，有此ID时答案记录到会话而非直接更新遗忘曲线")


class RejudgeRequest(BaseModel):
    """错题重练请求模型"""
    user_id: str = Field(..., description="用户ID")
    problem_data: Dict[str, Any] = Field(..., description="编程题完整数据")
    user_code: str = Field(..., description="用户新提交的代码")
    language: str = Field(default="python", description="编程语言")
    record_id: Optional[str] = Field(None, description="错题记录ID（如果答对则自动删除）")


# ★★★ 学伴相关请求模型 ★★★
class CompanionInviteRequest(BaseModel):
    from_user: str = Field(..., description="邀请方用户ID")
    to_user: str = Field(..., description="被邀请方用户ID")


class CompanionRespondRequest(BaseModel):
    user_id: str = Field(..., description="当前用户ID")
    companion_id: int = Field(..., description="学伴关系ID")
    accept: bool = Field(..., description="是否接受")


class CompanionMessageRequest(BaseModel):
    relation_id: int = Field(..., description="学伴关系ID")
    sender_id: str = Field(..., description="发送方用户ID")
    content: str = Field(..., description="消息内容")


class ShareRequest(BaseModel):
    sharer_id: str = Field(..., description="分享者用户ID")
    receiver_id: str = Field(..., description="接收者用户ID（学伴ID 或 '__community__'）")
    resource_type: str = Field(..., description="资源类型: doc/practice/question/video/mindmap/extension/ppt")
    resource_id: str = Field(..., description="资源ID（ContentStore中的content_id）")
    title: str = Field(default="", description="资源标题")
    knowledge_point: str = Field(default="", description="关联知识点")
    message: str = Field(default="", description="分享留言")


class FavoriteRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    resource_type: str = Field(..., description="资源类型")
    resource_id: str = Field(..., description="资源ID")
    title: str = Field(default="", description="资源标题")
    knowledge_point: str = Field(default="", description="关联知识点")
    source_user_id: str = Field(default="", description="资源来源用户ID（如果是学伴分享的）")


class FavoriteRemoveRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    resource_type: str = Field(..., description="资源类型")
    resource_id: str = Field(..., description="资源ID")


class CoStudyInviteRequest(BaseModel):
    inviter_id: str = Field(..., description="邀请方用户ID")
    invitee_id: str = Field(..., description="被邀请方用户ID")
    resource_type: str = Field(..., description="资源类型: practice/video/doc")
    resource_id: str = Field(..., description="资源ID")
    title: str = Field(default="", description="资源标题")
    mode: str = Field(default="separate", description="模式: separate=各自练习, pair=结对编程")


# ★★★ 小组与比赛请求模型 ★★★
class CreateGroupRequest(BaseModel):
    name: str = Field(..., description="小组名称")
    creator_id: str = Field(..., description="创建者用户ID")
    description: str = Field(default="", description="小组描述")
    max_members: int = Field(default=50, description="最大成员数")
    is_public: bool = Field(default=True, description="是否公开（True=公开，False=私密）")


class JoinGroupRequest(BaseModel):
    group_id: int = Field(..., description="小组ID")
    user_id: str = Field(..., description="用户ID")


class GroupMessageRequest(BaseModel):
    group_id: int = Field(..., description="小组ID")
    sender_id: str = Field(..., description="发送者ID")
    content: str = Field(..., description="消息内容")
    msg_type: str = Field(default="text", description="消息类型: text/image")


class CreateCompetitionRequest(BaseModel):
    group_id: int = Field(..., description="小组ID")
    title: str = Field(..., description="比赛名称")
    created_by: str = Field(..., description="创建者ID")
    description: str = Field(default="", description="比赛描述")
    problem_count: int = Field(default=3, description="题目数量")
    start_at: Optional[str] = Field(default=None, description="开始时间 ISO 格式，不填则手动开始")
    end_at: Optional[str] = Field(default=None, description="结束时间 ISO 格式，不填则开始后2小时")


class UpdateCompetitionRequest(BaseModel):
    competition_id: int = Field(..., description="比赛ID")
    user_id: str = Field(..., description="用户ID")
    title: Optional[str] = Field(default=None, description="比赛名称")
    description: Optional[str] = Field(default=None, description="比赛描述")
    start_at: Optional[str] = Field(default=None, description="开始时间 ISO 格式")
    end_at: Optional[str] = Field(default=None, description="结束时间 ISO 格式")


class GenerateProblemsRequest(BaseModel):
    competition_id: int = Field(..., description="比赛ID")
    user_id: str = Field(..., description="用户ID")
    input_text: str = Field(..., description="用户输入的题目描述/主题")
    problem_count: int = Field(default=3, description="题目数量")


class SubmitSolutionRequest(BaseModel):
    competition_id: int = Field(..., description="比赛ID")
    problem_id: int = Field(..., description="题目ID")
    user_id: str = Field(..., description="用户ID")
    answer_text: str = Field(..., description="提交的答案")


class SaveProblemsManualRequest(BaseModel):
    competition_id: int = Field(..., description="比赛ID")
    user_id: str = Field(..., description="用户ID（必须是创建者）")
    problems: List[Dict] = Field(..., description="赛题列表，每项含 title/description/difficulty/score")
    replace: bool = Field(default=True, description="True=覆盖, False=追加")


class GroupInviteRequest(BaseModel):
    group_id: int = Field(..., description="小组ID")
    inviter_id: str = Field(..., description="邀请者ID")
    invitee_id: str = Field(..., description="被邀请者ID")


class GroupInviteRespondRequest(BaseModel):
    invitation_id: int = Field(..., description="邀请ID")
    invitee_id: str = Field(..., description="被邀请者ID（当前用户）")
    accept: bool = Field(..., description="是否接受")


class CoStudyRespondRequest(BaseModel):
    invite_id: int = Field(..., description="共学邀请ID")
    accept: bool = Field(..., description="是否接受")


class ActivityUpdateRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    task_type: str = Field(..., description="任务类型: practice/video/doc/question/mindmap/extension/ppt")
    task_detail: str = Field(default="", description="任务详情")
    topic: str = Field(default="", description="当前主题")


class ResourceContextRequest(BaseModel):
    """资源上下文（告知摄像头模块用户当前在看什么）"""
    user_id: str = Field(..., description="用户ID")
    resource_type: str = Field(..., description="资源类型: practice/video/doc/mindmap/extension/animation")
    resource_id: str = Field(default="", description="资源ID")
    knowledge_point: str = Field(default="", description="关联知识点")
    action: str = Field(default="open", description="操作: open/close")


class CoStudyMessageRequest(BaseModel):
    invitation_id: int = Field(..., description="共学邀请ID")
    sender_id: str = Field(..., description="发送方用户ID")
    content: str = Field(..., description="消息内容")


class CoStudyDeleteRequest(BaseModel):
    invitation_id: int = Field(..., description="共学邀请ID")
    user_id: str = Field(..., description="用户ID（邀请方或被邀请方均可）")


# ==================== 笔记相关数据模型 ====================

class NoteCreateRequest(BaseModel):
    title: str = Field(..., description="笔记标题")
    content: str = Field(..., description="笔记内容（markdown）")
    use_ai: bool = Field(default=False, description="是否使用AI整理后保存")


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, description="笔记标题")
    content: Optional[str] = Field(None, description="笔记内容（markdown）")
    knowledge_points: Optional[List[str]] = Field(None, description="知识点列表")


class NoteOrganizeRequest(BaseModel):
    title: str = Field(..., description="笔记标题")
    content: str = Field(..., description="笔记内容（markdown）")


class NoteExportRequest(BaseModel):
    note_id: str = Field(..., description="笔记ID")
    format: str = Field(default="docx", description="导出格式: docx / pdf")


# ==================== API路由 ====================


@app.get("/")
async def root():
    """根路径 - API信息"""
    return {
        "service": "智能教育系统 - Agent测试API",
        "version": "1.0.0",
        "endpoints": {
            "/chat": "POST - Agent对话接口（SSE流式，支持动态参数）",
            "/chat-json": "POST - Agent对话接口（Java JSON版，供Java后端更新数据库，SSE完成后自动缓存）",
            "/practice/generate": "POST - 生成编程练习题",
            "/practice/submit": "POST - 提交代码并评分",
            "/practice/rejudge": "POST - 错题重练（重新提交代码评分）",
            "/practice/visualize": "POST - 生成算法可视化HTML",
            "/animation/generate": "POST - 生成教育动画HTML",
            "/ppt/generate": "POST - 生成PPT",
            "/ppt/download/{filename}": "GET - 下载PPT文件",
            "/leaderboard/{problem_id}": "GET - 获取题目排行榜",
            "/leaderboard/{problem_id}/statistics": "GET - 获取题目统计信息",
            "/leaderboard/{problem_id}/user/{user_id}": "GET - 获取用户最佳成绩",
            "/leaderboard/submission/{submission_id}/code": "GET - 获取提交的完整代码",
            "/api/global-ranking": "GET - 获取全局用户综合排行榜",
            "/api/global-ranking/user/{user_id}": "GET - 获取用户全局排名详情",
            "/speech/recognize": "POST - 语音识别（ASR）",
            "/speech/tts": "POST - 语音合成（TTS）",
            "/features/{user_id}": "GET - 获取用户8维度特征",
            "/clear_cache/{user_id}": "POST - 清除用户内存缓存",
            "/chat/context": "POST - 上下文感知对话接口（智能球专用）",
            "/api/user/context/update": "POST - 前端页面上下文上报接口",
            "/api/user/context/{user_id}": "GET - 获取用户完整实时上下文",
            "/api/user/attention-profile/{user_id}": "GET - 查看用户注意力偏好画像",
            "/user/resources/{user_id}": "GET - 列出用户所有已生成的资源",
            "/user/resource/{user_id}/{resource_type}/{resource_id}": "GET - 获取单个用户生成资源的完整内容",
            "/api/user/resource-context": "POST - 上报用户当前查看的资源上下文",
            "/document/download/{user_id}/{doc_id}": "GET - 下载生成的Word文档",
            "/video/report-watch": "POST - 上报视频观看行为数据",
            "/video/rewind-event": "POST - 上报视频回溯事件",
            "/viz": "GET - 算法可视化前端页面",
            "/api/algorithms": "GET - 算法列表（层级结构）",
            "/api/algorithms/{category}/{algorithm}": "GET - 算法详情",
            "/api/visualize/transform": "POST - LLM代码转换（纯算法代码→可视化代码）",
            "/health": "GET - 健康检查"
        },
        "companion_endpoints": {
            "/companion-page": "GET - 学伴前端页面",
            "/companion/match/{user_id}": "GET - 匹配学伴",
            "/companion/invite": "POST - 发送学伴邀请",
            "/companion/respond": "POST - 接受/拒绝学伴邀请",
            "/companion/list/{user_id}": "GET - 我的学伴列表",
            "/companion/pending/{user_id}": "GET - 待处理的学伴邀请",
            "/companion/message": "POST - 发送学伴消息",
            "/companion/messages/{relation_id}": "GET - 获取学伴会话消息",
            "/companion/notifications/{user_id}": "GET - 学伴通知列表",
            "/companion/activities/{user_id}": "GET - 学伴动态感知",
            "/companion/activity/update": "POST - 更新学习活动",
            "/companion/share": "POST - 分享资源给学伴或社区",
            "/companion/shared/to-me/{user_id}": "GET - 别人分享给我的资源",
            "/companion/shared/by-me/{user_id}": "GET - 我分享出去的资源",
            "/companion/shared/community": "GET - 社区共享资源",
            "/companion/shared/load/{sharer_id}/{resource_type}/{resource_id}": "GET - 读取共享资源内容",
            "/companion/favorite/add": "POST - 收藏资源",
            "/companion/favorite/remove": "POST - 取消收藏",
            "/companion/favorites/{user_id}": "GET - 我的收藏列表",
            "/companion/favorite/check/{user_id}/{resource_type}/{resource_id}": "GET - 检查是否已收藏"
        },
        "co_study_endpoints": {
            "/companion/co-study/invite": "POST - 发送共学邀请",
            "/companion/co-study/respond": "POST - 接受/拒绝共学邀请",
            "/companion/co-study/invites/{user_id}": "GET - 待处理的共学邀请",
            "/companion/co-study/sessions/{user_id}": "GET - 历史共学记录",
            "/companion/co-study/sent/{user_id}": "GET - 我发出的共学邀请",
            "/companion/co-study/notifications/{user_id}": "GET - 共学通知",
            "/companion/co-study/invitation/{invite_id}": "GET - 共学邀请详情",
            "/companion/co-study/message": "POST - 共学会话发消息",
            "/companion/co-study/messages/{invitation_id}": "GET - 共学会话消息列表",
            "/companion/co-study/delete": "POST - 删除共学记录"
        },
        "pair_programming_endpoints": {
            "/companion/compare/{problem_id}/{user_id_a}/{user_id_b}": "GET - 对比两人成绩",
            "/companion/pair/session/{invitation_id}": "GET - 获取结对编程会话",
            "/companion/pair/code": "POST - 提交结对编程代码",
            "/companion/pair/submit": "POST - 提交结对编程评分"
        },
        "note_endpoints": {
            "/notes/{user_id}": "GET - 获取用户笔记列表",
            "/notes/{user_id}": "POST - 创建新笔记",
            "/notes/{user_id}/{note_id}": "GET - 获取单篇笔记详情",
            "/notes/{user_id}/{note_id}": "PUT - 更新笔记（支持 title/content/knowledge_points）",
            "/notes/{user_id}/{note_id}": "DELETE - 删除笔记",
            "/notes/{user_id}/{note_id}/organize-preview": "POST - AI 整理预览（返回 diff，不保存）",
            "/notes/{user_id}/{note_id}/organize-preview/accept": "POST - 接受 AI 整理结果并保存",
            "/notes/{user_id}/{note_id}/explain-selection": "POST - AI 解释选中文本（SSE 流式）",
            "/notes/{user_id}/{note_id}/export": "POST - 导出笔记（docx/pdf）",
            "/notes/upload/{user_id}": "POST - 上传笔记附件（图片/文档）",
            "/api/note/mindmap": "POST - 从笔记内容生成思维导图"
        },
        "study_plan_endpoints": {
            "/study_plan/generate": "POST - 生成个性化学习路径规划",
            "/study_plan/{user_id}": "GET - 获取用户学习计划（支持 ?plan_id=）",
            "/study_plan/{user_id}/summary": "GET - 获取学习计划摘要（支持 ?plan_id=）",
            "/study_plan/{user_id}/phases": "GET - 获取学习计划所有阶段",
            "/study_plan/{user_id}/phase/{phase_index}/status": "GET - 获取某阶段资源缓存状态",
            "/study_plan/{user_id}/phase/{phase_index}/generate/{resource_type}": "POST - 生成某阶段指定资源",
            "/study_plan/{user_id}/phase/{phase_index}/generate-all": "POST - 生成某阶段所有未缓存资源",
            "/study_plan/{user_id}/pipeline-status": "GET - 获取用户管道状态摘要",
            "/study_plan/{user_id}/progress": "GET - 获取所有阶段完成度",
            "/study_plan/{user_id}/phase/{phase_index}/progress": "GET - 获取某阶段完成度",
            "/study_plan/{user_id}/notification": "GET - 检查阶段完成通知",
            "/study_plan/{user_id}/notification/ack": "POST - 确认阶段完成通知",
            "/study_plans/{user_id}": "GET - 获取所有计划列表",
            "/study_plan/{user_id}/version-tree": "GET - 获取学习计划版本树（含当前执行中版本）",
            "/study_plan/{user_id}/switch-version": "POST - 切换版本树的当前执行中版本",
            "/study_plan/{user_id}/regenerate-phase": "POST - 重新生成指定阶段及其后续阶段（支持进行中阶段）",
            "/study_plan/{user_id}/switch-plan": "POST - 切换全局活跃计划",
            "/study_plan/{user_id}/plan/{plan_id}": "DELETE - 删除指定计划",
            "/study_plan/{user_id}/continuation": "GET - 检查续期状态",
            "/study_plan/{user_id}/receive-continuation": "POST - 接收续期建议（后台生成新计划）",
            "/study_plan/{user_id}/reject-continuation": "POST - 拒绝续期建议",
            "/study_plan/{user_id}/accept-continuation": "POST - 接受续期计划",
            "/study_plan/{user_id}/ignore-continuation": "POST - 忽略续期计划",
            "/study_plan/{user_id}/phase/{phase_index}/heartbeat": "POST - 前端心跳上报",
            "/study_plan/{user_id}/phase/{phase_index}/exam/choice": "POST - 用户选择是否参加阶段考试",
            "/study_plan/{user_id}/phase/{phase_index}/exam": "GET - 获取阶段考试题目数据",
            "/study_plan/{user_id}/phase/{phase_index}/exam/submit": "POST - 提交阶段考试答案"
        },
        "community_endpoints": {
            "/community/upload": "POST - 上传文件（图片/Word/PDF等）",
            "/community/post": "POST - 发布学习困惑/分享",
            "/community/zones": "GET - 获取社区区域列表",
            "/community/post/preview": "POST - 发帖助手-预览帖子草稿",
            "/community/post/publish": "POST - 发帖助手-发布帖子",
            "/community/posts": "GET - 获取社区帖子列表（分页）",
            "/community/post/{post_id}": "GET - 获取帖子详情（含回复）",
            "/community/reply": "POST - 回复帖子（支持嵌套回复）",
            "/community/post/{post_id}": "PUT - 编辑帖子（仅作者可编辑）",
            "/community/post/{post_id}/{user_id}": "DELETE - 删除帖子（仅作者可删）",
            "/community/reply/{reply_id}/{user_id}": "DELETE - 删除回复（仅作者可删）"
        },
        "wrong_answer_endpoints": {
            "/theory/submit": "POST - 提交理论题答案（错误自动记入错题本）",
            "/theory/judge": "POST - 判理论题（不记入错题本，智能助手中使用）",
            "/resource/question/{qid}": "GET - 根据题目ID获取题目详情",
            "/wrong-answers/{user_id}": "GET - 获取用户错题列表",
            "/wrong-answers/{user_id}/stats": "GET - 获取用户错题统计（含易错题数量）",
            "/wrong-answers/{user_id}/mastered": "GET - 获取用户已掌握列表",
            "/wrong-answers/{user_id}/frequently-wrong": "GET - 获取用户易错题列表（答错>4次的顽固错题）",
            "/wrong-answers/{user_id}/frequently-wrong/stats": "GET - 获取用户易错题专项统计",
            "/wrong-answers/{record_id}/recommend/{user_id}": "GET - 获取错题推荐资料",
            "/wrong-answers/llm-generate": "POST - LLM生成补充学习资料（错题本弹窗）",
            "/wrong-answers/{record_id}/{user_id}": "DELETE - 删除错题记录"
        },
        "assessment_endpoints": {
            "/assessment/generate/{user_id}": "POST - 生成用户学习效果评估报告",
            "/assessment/latest/{user_id}": "GET - 获取用户最新评估报告",
            "/assessment/apply/{user_id}": "POST - 应用评估报告的调整建议",
            "/assessment/phase-apply/{user_id}/{phase_index}": "POST - 接受阶段性评估（保存到评估页面）",
            "/assessment/phase/{user_id}/{phase_index}": "GET - 获取阶段性评估报告",
            "/assessment/regenerate/{user_id}": "POST - 局部重新评估报告（仅重新生成指定部分）",
            "/assessment/notifications/{user_id}": "GET - 获取用户评估报告通知",
            "/assessment/notifications/{user_id}/read": "POST - 标记评估通知为已读",
            "/assessment/adopt/{user_id}": "POST - 采纳一条评估建议",
            "/assessment/reject/{user_id}": "POST - 拒绝/撤销已采纳的建议",
            "/assessment/adopted/{user_id}": "GET - 获取用户所有已采纳的评估建议",
            "/study_plan/{user_id}/review-reminder": "GET - 获取用户复习提醒（今日到期+即将到期）"
        },
        "voice_profile_endpoints": {
            "/api/user/voice-profile/upload-sample": "POST - 上传用户语音样本",
            "/api/user/voice-profile": "POST - 设置用户音色偏好",
            "/api/user/voice-profile/{user_id}": "GET - 获取用户当前音色配置",
            "/api/user/voice-profile/{user_id}": "DELETE - 重置音色偏好为默认",
            "/api/user/voice-profile/preview": "POST - 预览音色效果（不保存）"
        },
        "pages": {
            "/notebook-page": "GET - 学习笔记前端页面",
            "/test-page": "GET - Agent测试平台页面",
            "/wrong-answers-page": "GET - 错题本前端页面",
            "/assessment-page": "GET - 学习效果评估页面",
            "/study-plan-page": "GET - 学习计划前端页面",
            "/route-market-page": "GET - 学习路线市场页面",
            "/community-page": "GET - 学习社区页面",
            "/unified-page": "GET - 统一前端页面（智能助手+社区+错题本）",
            "/knowledge-comparison-page": "GET - 知识点智能对比页面"
        },
        "knowledge_comparison_endpoints": {
            "/knowledge-comparison/list": "GET - 获取可对比的知识点列表",
            "/knowledge-comparison/compare": "POST - 智能对比两个知识点",
            "/knowledge-comparison/recommendations": "GET - 获取推荐的对比组合"
        },
        "supported_agents": [
            "ChatAgent (日常对话)",
            "PracticeAgent (编程练习)",
            "QuestionGeneratorAgent (题目生成)",
            "CourseDocAgent (文档生成)",
            "ExtensionReadingAgent (拓展阅读)",
            "VideoSearchAgent (视频搜索)",
            "MindMapAgent (思维导图)",
            "AnimationAgent (动画生成)",
            "StudyPlanAgent (学习路径规划)",
            "LearningAssessmentAgent (学习效果评估)",
            "PPTCreationAgent (PPT生成)",
            "KnowledgeComparisonAgent (知识点智能对比)"
        ],
        "features": [
            "文本交互",
            "语音输入（ASR）",
            "TTS语音合成（含个性化音色）",
            "动画生成",
            "排行榜系统",
            "8维度特征雷达图",
            "算法可视化（Canvas动画）",
            "错题本（自动记录+重练+特征更新+LLM推荐）",
            "学习路径规划（阶段资源自动生成）",
            "学习效果评估（LLM综合分析报告+通知）",
            "PPT生成（AI自动生成专业课件）",
            "学习社区（发帖+回复）",
            "学伴系统（匹配+消息+动态感知）",
            "共学/结对编程（邀请+会话+代码协作）",
            "统一前端（智能助手+社区+错题本+学伴）",
            "知识点智能对比（多维度差异分析）"
        ]
    }

# ★★★ 后台预加载语义嵌入模型（不阻塞服务器启动）★★★
import threading
def _preload_intent_classifier():
    print("  ⏳ [后台预加载] 正在加载意图分类器...")
    from utils.intent_classifier import get_intent_classifier
    get_intent_classifier()
    print("  ✅ [后台预加载] 意图分类器加载完成")
threading.Thread(target=_preload_intent_classifier, daemon=True).start()


@app.get("/health")
async def health_check():
    """健康检查"""
    from datetime import datetime
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/chat/context")
async def chat_with_context_endpoint(request: ContextChatRequest):
    """
    上下文感知对话接口（智能球专用）

    与 /chat 的区别：
    - 接收前端上报的 page_context（页面、操作等）
    - ChatAgent 会自动聚合错题、练题结果、掌握度等实时上下文
    - 回复更"知你所做，懂你所困"
    """
    try:
        from Agent.children_agent.chat_agent import ChatAgent

        chat_agent = ChatAgent()
        result = await chat_agent.chat_async(
            user_input=request.user_input,
            user_id=request.user_id,
            enable_tts=request.enable_tts,
            page_context=request.page_context if request.page_context else None
        )

        return {
            "success": True,
            "data": result,
            "metadata": {"user_id": request.user_id}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上下文对话失败: {str(e)}")


@app.post("/api/user/context/update")
async def update_user_context_endpoint(request: PageContextUpdateRequest):
    """
    前端页面上下文上报接口

    各页面通过在 iframe 中调用来告知系统用户当前在做什么。
    示例:
    {
      "user_id": "user_001",
      "page": "agent_test",
      "title": "冒泡排序练习题",
      "action": "practicing",
      "detail": "题目ID: P001, 当前得分: 45"
    }
    """
    try:
        from services.user_context_service import UserContextService
        service = UserContextService()
        await service.update_page_context(
            request.user_id,
            {
                "page": request.page,
                "title": request.title or "",
                "action": request.action or "",
                "detail": request.detail or "",
            }
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上下更新失败: {str(e)}")


@app.get("/api/user/context/{user_id}")
async def get_user_context_endpoint(user_id: str):
    """
    获取用户完整实时上下文（供调试/前端展示用）
    """
    try:
        from services.user_context_service import UserContextService
        service = UserContextService()
        context = service.build_full_context(user_id)
        return {"success": True, "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取上下文失败: {str(e)}")



@app.post("/chat")
async def chat_endpoint(request: AgentTestRequest):
    """
    Agent对话接口（SSE流式 → 推送完毕后自动转存 Java JSON）
    
    通过 Server-Sent Events 实时推送当前正在执行的节点状态。
    事件类型:
      - node_status: 节点状态变更 { node, status, detail }
      - task_result:  最终执行结果 { result }
      - done:         SSE 流推送完毕标识
    
    ★ SSE 推送完毕后，服务端自动将结果转换为整洁 JSON 存入内存，
      Java 后端调用 /chat-json 接口即可获取转换结果并更新数据库。
    """
    # 尝试导入节点状态通知（如不可用则退回普通JSON响应）
    try:
        from Agent.main_agent_conduct import set_node_status_queue, clear_node_status_queue
        _has_sse = True
    except ImportError:
        _has_sse = False

    if not _has_sse:
        # ★★★ 降级：普通JSON响应（旧版main_agent_conduct无状态通知机制）★★★
        try:
            controller = _get_controller_for_user(request.user_id)
            user_input = request.user_input
            extra = request.extra_params or {}
            if request.task_type and extra:
                params_str = ", ".join([f"{k}={v}" for k, v in extra.items()])
                user_input = f"{user_input} ({params_str})"

            result = await controller.process_request_async(
                user_input=user_input,
                user_id=request.user_id,
                enable_tts=request.enable_tts,
                confirmed=request.confirmed,
                override_suggestions=request.override_suggestions,
                ignore_weak_points=extra.get("ignore_weak_points", False),
                focus_weak_points=extra.get("focus_weak_points", False)
            )

            needs_confirmation = False
            suggestion_warning = ""
            if isinstance(result, dict):
                conduct_data = result.get("data", {})
                if isinstance(conduct_data, dict):
                    practice_data = conduct_data.get("practice", {})
                    if isinstance(practice_data, dict) and practice_data.get("needs_confirmation"):
                        needs_confirmation = True
                        suggestion_warning = practice_data.get("suggestion_warning", "")

            if request.enable_tts and not needs_confirmation:
                from utils.tts_helper import ensure_tts_in_result
                result = await ensure_tts_in_result(result, user_id=request.user_id)

            return {
                "success": True,
                "data": result,
                "needs_confirmation": needs_confirmation,
                "suggestion_warning": suggestion_warning if needs_confirmation else _extract_suggestion_warning(result),
                "request_info": {
                    "user_id": request.user_id,
                    "task_type": request.task_type or "auto_detect",
                    "extra_params": request.extra_params,
                    "enable_tts": request.enable_tts
                }
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

    try:
        # 创建异步队列，用于在 SSE 生成器和图执行之间传递事件
        event_queue: asyncio.Queue = asyncio.Queue()

        set_node_status_queue(event_queue)

        # 构建额外参数
        user_input = request.user_input
        extra = request.extra_params or {}
        if request.task_type and extra:
            params_str = ", ".join([f"{k}={v}" for k, v in extra.items()])
            user_input = f"{user_input} ({params_str})"

        async def event_generator():
            """SSE 事件生成器（完成后自动存储 Java JSON）"""
            final_result = None
            error_msg = None
            try:
                controller = _get_controller_for_user(request.user_id)

                async def _run_agent():
                    nonlocal final_result
                    try:
                        result = await controller.process_request_async(
                            user_input=user_input,
                            user_id=request.user_id,
                            enable_tts=request.enable_tts,
                            confirmed=request.confirmed,
                            override_suggestions=request.override_suggestions,
                            ignore_weak_points=extra.get("ignore_weak_points", False),
                            focus_weak_points=extra.get("focus_weak_points", False)
                        )
                        if request.enable_tts:
                            try:
                                from utils.tts_helper import ensure_tts_in_result
                                result = await ensure_tts_in_result(result, user_id=request.user_id)
                            except Exception:
                                pass
                        await event_queue.put({"type": "task_result", "result": result, "timestamp": time.time()})
                        final_result = result
                    except Exception as e:
                        nonlocal error_msg
                        error_msg = str(e)
                        await event_queue.put({"type": "error", "message": str(e), "timestamp": time.time()})

                agent_task = asyncio.create_task(_run_agent())

                while True:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        if event.get("type") == "task_result":
                            final_result = event.get("result")
                            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                            break
                        if event.get("type") == "error":
                            error_msg = event.get("message")
                            break
                    except asyncio.TimeoutError:
                        if agent_task.done():
                            try:
                                while True:
                                    event = event_queue.get_nowait()
                                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                                    if event.get("type") == "task_result":
                                        final_result = event.get("result")
                                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                                        break
                                    if event.get("type") == "error":
                                        error_msg = event.get("message")
                            except asyncio.QueueEmpty:
                                pass
                            break

                await agent_task

            except Exception as e:
                error_msg = str(e)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                clear_node_status_queue()
                # ★★★ SSE 推流完毕后，自动转换并存储 Java 可用 JSON ★★★
                raw = final_result if not error_msg else None
                if raw is not None and isinstance(raw, dict):
                    cache_java_result(request.user_id, raw)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        clear_node_status_queue()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/chat-json")
async def chat_json_endpoint(request: AgentTestRequest):
    """
    Agent对话接口（Java JSON 版 — 返回转换后的整洁 JSON，供 Java 更新数据库）
    
    ★ 执行流程：
       1. 优先从内存读取 SSE 完成时自动存储的转换结果
       2. 如无缓存结果，则独立执行 Agent 并实时转换
    
    ★ 返回 JSON 结构（以 practice 为例）：
       {
         "success": true,                    // 整体是否成功
         "task_type": "practice",            // 任务类型
         "status": 2,                        // 2=有完整资源, 1=仅有提示无资源, 3=失败
         "problem": { ... },                 // 资源数据（task_type 不同字段名不同）
         "suggestion_warning": "..."         // 建议冲突警告（仅 practice）
       }
    
    Java 等后端客户端通过此接口获取可直接映射数据库的 JSON。
    请求体同 /chat 接口。
    """
    # ========== 1. 优先尝试读取缓存 ==========
    cached = get_java_result(request.user_id)
    if cached is not None:
        print(f"📋 /chat-json 命中缓存: user_id={request.user_id}")
        return cached

    # ========== 2. 无缓存，独立执行 ==========
    print(f"⚙️ /chat-json 缓存未命中，独立执行: user_id={request.user_id}")
    try:
        controller = _get_controller_for_user(request.user_id)
        user_input = request.user_input
        if request.task_type and request.extra_params:
            params_str = ", ".join([f"{k}={v}" for k, v in request.extra_params.items()])
            user_input = f"{user_input} ({params_str})"

        result = await controller.process_request_async(
            user_input=user_input,
            user_id=request.user_id,
            enable_tts=request.enable_tts,
            confirmed=request.confirmed,
            override_suggestions=request.override_suggestions,
        )

        if request.enable_tts and isinstance(result, dict):
            try:
                from utils.tts_helper import ensure_tts_in_result
                result = await ensure_tts_in_result(result, user_id=request.user_id)
            except Exception:
                pass

        # 转换为 Java 友好 JSON 并缓存
        java_json = cache_java_result(request.user_id, result)
        if java_json is None:
            java_json = transform_to_java_result(result)
        return java_json

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.post("/batch_test")
async def batch_test_endpoint(config: TestConfig):
    """
    批量测试接口(异步并发版本)
    
    一次性执行多个测试场景,每个场景在独立线程中执行
    """
    try:
        controller = _get_controller_for_user(config.user_id)
        results = []
        
        # ★★★ 创建并发任务列表 ★★★
        tasks = []
        for i, scenario in enumerate(config.test_scenarios):
            task_func = controller.process_request
            task_args = (scenario.get("user_input", ""), config.user_id)
            tasks.append((task_func, task_args, {}))
        
        # ★★★ 并发执行所有任务 ★★★
        from utils.concurrent_executor import ConcurrentExecutor
        executor = ConcurrentExecutor(max_workers=10)
        batch_results = executor.execute_batch_async(tasks)
        
        # 整理结果
        for i, batch_result in enumerate(batch_results):
            results.append({
                "scenario_index": i,
                "success": batch_result["success"],
                "result": batch_result.get("result"),
                "error": batch_result.get("error")
            })
        
        return {
            "success": True,
            "total": len(config.test_scenarios),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量测试失败: {str(e)}")


@app.post("/practice/generate")
async def generate_practice_endpoint(request: AgentTestRequest):
    """
    生成编程练习题(异步版本)
    
    示例:
    {
      "user_id": "test_2",
      "user_input": "帮我生成一道简单的循环编程题",
      "task_type": "practice"
    }
    """
    try:
        controller = _get_controller_for_user(request.user_id)
        
        # ★★★ 使用异步方法 ★★★
        result = await controller.process_request_async(
            user_input=request.user_input,
            user_id=request.user_id,
            confirmed=request.confirmed,
            override_suggestions=request.override_suggestions
        )
        
        # ▶ 检测是否需要用户确认（建议冲突）
        if isinstance(result, dict):
            data_layer = result.get("data", {}) if result.get("layer") == "conduct" else result
            practice_data = (data_layer.get("practice", {}) if isinstance(data_layer, dict) else {}) or data_layer
            if practice_data.get("needs_confirmation"):
                return {
                    "success": True,
                    "needs_confirmation": True,
                    "suggestion_warning": practice_data.get("suggestion_warning", ""),
                    "message": "检测到与已采纳建议矛盾，请确认后继续"
                }
        
        # 提取题目信息
        if result.get("status") == "success" and result.get("layer") == "conduct":
            conduct_data = result.get("data", {})
            practice_data = conduct_data.get("practice", {})
            
            # ★★★ 提取建议冲突警告到响应顶层（供前端直接展示）★★★
            suggestion_warning = practice_data.get("suggestion_warning", "") if isinstance(practice_data, dict) else ""
            
            return {
                "success": True,
                "problem_id": practice_data.get("problem_id", "P001"),
                "problem": practice_data,
                "suggestion_warning": suggestion_warning,
                "message": "题目生成成功，请提交代码进行评分"
            }
        else:
            return {
                "success": False,
                "message": "题目生成失败",
                "error": result.get("error", "未知错误")
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成题目失败: {str(e)}")


@app.post("/practice/submit")
async def submit_code_endpoint(request: CodeSubmissionRequest):
    """
    提交代码并评分
    
    示例:
    {
      "user_id": "test_2",
      "problem_id": "P001",
      "code": "for i in range(5):\n    print(i)",
      "language": "python",
      "session_id": "optional-session-uuid"
    }
    """
    try:
        from Agent.children_agent.practice_agent import PracticeAgent

        practice_agent = PracticeAgent()

        if request.session_id and request.problem:
            request.problem['session_id'] = request.session_id

        # ★★★ 上报 AgentMonitor：JudgeAgent 开始工作 ★★★
        try:
            from Agent.agent_monitor import report_call_start
            report_call_start("judge_code", request.user_id or "", "代码评判")
        except Exception:
            pass

        judge_success = False
        try:
            judge_result = await practice_agent.judge_code_async(
                problem_id=request.problem_id,
                problem=request.problem,
                user_code=request.code,
                language=request.language,
                student_features=None,
                user_id=request.user_id,
                enable_tts=request.enable_tts
            )
            judge_success = judge_result.get("success", False) or judge_result.get("score", 0) >= 0
        finally:
            # ★★★ 上报 AgentMonitor：JudgeAgent 工作结束 ★★★
            try:
                from Agent.agent_monitor import report_call_end
                report_call_end("judge_code", judge_success)
            except Exception:
                pass

        score = judge_result.get("score", 0)
        is_correct = score >= 60

        # ★★★ 数字孪生对比：自动触发孪生模拟作答并记录对比 ★★★
        twin_comparison = None
        try:
            from services.digital_twin_service import get_digital_twin_service
            # 截断代码避免存储过大
            _code_preview = (request.code or "")[:200]
            # 题目内容（从完整的 problem 数据中提取）
            _problem = request.problem or {}
            _q_content = _problem.get("content") or _problem.get("description") or _problem.get("question", request.problem_id)
            _correct_ans = _problem.get("answer") or _problem.get("correct_answer", "60分以上为通过")
            twin_comparison = await get_digital_twin_service().record_user_activity_async(
                request.user_id, "practice_submit",
                {
                    "problem_id": request.problem_id,
                    "knowledge_point": "",
                    "difficulty": 0.5,
                    "language": request.language,
                    "question_content": _q_content,
                    "correct_answer": _correct_ans,
                    "problem": _problem,  # 传完整题目给孪生写代码
                },
                {
                    "score": float(score),
                    "user_answer": _code_preview,
                }
            )
        except Exception:
            pass  # 孪生对比不阻塞主流程

        judge_result["twin_comparison"] = (
            {
                "twin_correct": twin_comparison.get("twin_correct"),
                "result_type": twin_comparison.get("result_type"),
                "twin_confidence": twin_comparison.get("twin_confidence"),
            }
            if twin_comparison
            else None
        )

        if request.session_id:
            from memory.knowledge_mastery import KnowledgeMasteryGraph
            kg = KnowledgeMasteryGraph()
            kg.submit_review_answer(
                session_id=request.session_id,
                question_id=request.problem_id,
                question_type="practice",
                user_answer=request.code,
                is_correct=is_correct,
                score=score
            )

        return {
            "success": True,
            "judge_result": judge_result,
            "leaderboard": judge_result.get("leaderboard"),
            "message": f"评分完成: {judge_result.get('verdict', 'Unknown')} ({score}分)"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"代码评分失败: {str(e)}")


@app.post("/practice/rejudge")
async def rejudge_code_endpoint(request: RejudgeRequest):
    """
    错题重练：使用已保存的题目数据重新提交代码并评分
    如果答对（score >= 60）自动标记掌握，答错3次+自动推荐学习资料
    """
    try:
        from Agent.children_agent.practice_agent import PracticeAgent
        from services.wrong_answer_service import WrongAnswerService

        practice_agent = PracticeAgent()
        wa_service = WrongAnswerService()

        # ★★★ 安全校验：如果传了 record_id，验证 problem_data 与错题记录匹配 ★★★
        if request.record_id:
            record = wa_service.get_wrong_answer_detail(request.record_id, request.user_id)
            if record:
                stored_problem_id = record.get("problem_id", "")
                sent_problem_id = request.problem_data.get("problem_id", "")
                if stored_problem_id and sent_problem_id and stored_problem_id != sent_problem_id:
                    raise HTTPException(status_code=400, detail=f"题目ID不匹配: 记录中为 {stored_problem_id}，提交为 {sent_problem_id}")

        judge_result = await practice_agent.judge_code_async(
            problem_id=request.problem_data.get("problem_id", "rejudge"),
            problem=request.problem_data,
            user_code=request.user_code,
            language=request.language,
            student_features=None,
            user_id=request.user_id,
            enable_tts=False
        )

        score = judge_result.get("score", 0)
        problem_id = request.problem_data.get("problem_id", "")
        kps = request.problem_data.get("knowledge_points", [])   #  所以导致在执行最小数据的时候在problem_data中需要知识点字段

        wa_result = await wa_service.handle_judge_result_async(
            user_id=request.user_id,
            record_id=request.record_id,
            problem_id=problem_id,
            score=score,
            knowledge_points=kps,
            problem_data=request.problem_data,
            user_answer=request.user_code,
            verdict=judge_result.get("verdict", ""),
        )

        if score < 60:
            pass

        # ★★★ 第2次错误后触发自我表述；检查是否已提前推荐过（防止3次重复）★★★
        explain_required = False
        _recommendation_already_done = False
        if score < 60 and request.record_id:
            _detail = wa_service.get_wrong_answer_detail(request.record_id, request.user_id)
            if _detail:
                _attempt = _detail.get("attempt_count", 0)
                # 第2次错误开始提示自我表述
                explain_required = _attempt >= 2
                # 如果已经通过自我表述提前推荐过 → 守卫，不再重复
                try:
                    from services.self_explanation_service import SelfExplanationService
                    _recommendation_already_done = SelfExplanationService().has_recommendation_been_triggered(
                        request.record_id, request.user_id
                    )
                    if _recommendation_already_done:
                        explain_required = False  # ★★★ 已推荐过，不再弹自我表述 ★★★
                except Exception:
                    pass

        # ★★★ 已提前推荐过 → 优先显示缓存（第2次已生成），第3次不用再算 ★★★
        material_recommendations = None
        self_explanation_data = None
        if _recommendation_already_done:
            try:
                _cached = await wa_service._get_recommendations_for_record(
                    request.record_id, request.user_id
                )
                if _cached:
                    material_recommendations = _cached
                # ★★★ 同时获取自我表述的分析结果（供前端显示历史按钮）★★★
                from services.self_explanation_service import SelfExplanationService
                _se_data = SelfExplanationService().get_latest_analysis_for_record(
                    request.record_id, request.user_id
                )
                if _se_data:
                    self_explanation_data = _se_data
            except Exception:
                pass
        if not material_recommendations:
            material_recommendations = wa_result.get("material_recommendations")

        return {
            "success": True,
            "judge_result": judge_result,
            "auto_marked_as_resolved": wa_result.get("auto_marked_as_resolved", False),
            "material_recommendations": material_recommendations,
            "self_explanation_data": self_explanation_data,
            "message": f"评分完成: {judge_result.get('verdict', 'Unknown')} ({score}分)",
            # ★★★ 独立标记：>=2次时触发自我表述（不改变任何现有字段含义）★★★
            "explain_required": explain_required,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"重练失败: {str(e)}")


@app.post("/practice/visualize")
async def visualize_algorithm_endpoint(request: VisualizationRequest):
    """
    基于用户代码生成算法可视化HTML
    
    示例:
    {
      "user_id": "test_2",
      "problem_id": "P_xxxxxxxx",
      "user_code": "def fib(n):...",
      "language": "python"
    }
    """
    try:
        from Agent.children_agent.practice_agent import PracticeAgent
        
        practice_agent = PracticeAgent()
        
        # ★★★ 基于用户代码生成可视化（不再需要生成参考代码）★★★
        result = await practice_agent.generate_visualization_from_user_code(
            problem=request.problem_id,
            user_code=request.user_code,
            language=request.language,
            user_id=request.user_id
        )
        
        if result.get("status") == "success":
            return {
                "success": True,
                "visualization_html": result["visualization_html"],
                "metadata": result.get("metadata", {})
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "可视化生成失败"))
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"可视化生成失败: {str(e)}")


@app.get("/features/{user_id}")
async def get_user_features(user_id: str):
    """
    获取用户8维度特征（用于雷达图展示，异步版本）

    示例: GET /features/user_001
    """
    try:
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        from fastapi.concurrency import run_in_threadpool

        # ★★★ 在线程池中执行 sync 文件 I/O，不阻塞事件循环 ★★★
        def query_features():
            feature_updater = DynamicFeatureUpdater()
            return feature_updater.get_latest_features(user_id)

        features = await run_in_threadpool(query_features)

        if not features:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 的特征未找到")

        return {
            "success": True,
            "user_id": user_id,
            "features": features
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取特征失败: {str(e)}")


@app.get("/features/{user_id}/stream")
async def stream_user_features(user_id: str):
    """
    SSE实时推送用户特征数据（用于动态曲线图展示）
    
    持续监听用户特征变化，实时推送到前端。
    客户端连接后会立即收到当前特征数据，之后每隔3秒检查一次是否有更新。
    
    事件类型:
      - feature_update: 特征数据更新 { user_id, features, timestamp }
      - keepalive: 心跳保活
    
    示例: GET /features/user_001/stream
    """
    try:
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        from fastapi.concurrency import run_in_threadpool
        import hashlib

        feature_updater = DynamicFeatureUpdater()

        def get_features_hash(features):
            if not features:
                return ""
            return hashlib.md5(json.dumps(features, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

        async def event_generator():
            last_hash = ""
            heartbeat_count = 0
            first_time = True
            
            while True:
                try:
                    features = await run_in_threadpool(feature_updater.get_latest_features, user_id)
                    
                    if features:
                        # 确保有 summary_scores 字段
                        if 'summary_scores' not in features:
                            all_8_dims = [
                                "academic_background", "learning_behavior", "goal_motivation",
                                "cognitive_abilities", "emotional_state", "social_interaction",
                                "time_management", "creativity_innovation"
                            ]
                            dim_scores = []
                            for dim in all_8_dims:
                                score = features.get(dim, {}).get("score", 50)
                                dim_scores.append(max(0, min(100, int(score))))
                            features['summary_scores'] = {
                                "dimension_scores": dim_scores,
                                "overall_score": sum(dim_scores) // 8
                            }
                    else:
                        # 没有数据，生成默认数据
                        features = {
                            'summary_scores': {
                                'overall_score': 65,
                                'dimension_scores': [65, 72, 68, 75, 70, 62, 78, 71]
                            },
                            'academic_background': {'score': 65},
                            'learning_behavior': {'score': 72},
                            'goal_motivation': {'score': 68},
                            'cognitive_abilities': {'score': 75},
                            'emotional_state': {'score': 70},
                            'social_interaction': {'score': 62},
                            'time_management': {'score': 78},
                            'creativity_innovation': {'score': 71}
                        }
                    
                    current_hash = get_features_hash(features)
                    if current_hash != last_hash or first_time:
                        print(f"📡 推送特征数据给用户 {user_id}, first_time={first_time}")
                        last_hash = current_hash
                        first_time = False
                        yield f"data: {json.dumps({'type': 'feature_update', 'user_id': user_id, 'features': features, 'timestamp': time.time()}, ensure_ascii=False)}\n\n"
                    
                    heartbeat_count += 1
                    if heartbeat_count >= 20:
                        yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': time.time()}, ensure_ascii=False)}\n\n"
                        heartbeat_count = 0
                    
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"⚠️ SSE特征推送异常: {e}")
                    await asyncio.sleep(3)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"SSE特征推送失败: {str(e)}")


@app.post("/clear_cache/{user_id}")
async def clear_user_cache_endpoint(user_id: str):
    """
    清除指定用户的内存缓存，确保下次读取时从磁盘重新加载
    
    当用户在前端切换 user_id 时，可以调用此接口避免读取到前一个用户的缓存
    
    示例: POST /clear_cache/user_001
    """
    try:
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater

        feature_updater = DynamicFeatureUpdater()
        feature_updater.clear_cache(user_id)

        return {
            "success": True,
            "user_id": user_id,
            "message": f"用户 {user_id} 的内存缓存已清除"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


# ==================== 时间维度管理 API ====================

class CheckInRequest(BaseModel):
    """学习打卡请求"""
    duration_seconds: int = Field(..., ge=0, description="本次学习时长（秒）")


@app.post("/time-dimension/{user_id}/check-in")
async def check_in_time_dimension(user_id: str, request: CheckInRequest):
    """
    学习打卡 - 传入 user_id + 学习时长（秒），自动更新时间维度

    等级标准（基于单次学习时长，秒）：
      Lv.0 未学习    0s        → score: 0
      Lv.1 短暂      ≤10min    → score: 15
      Lv.2 短时      ≤30min    → score: 35
      Lv.3 基础      ≤1h       → score: 55
      Lv.4 有效      ≤1.5h     → score: 70
      Lv.5 高效      ≤2h       → score: 85
      Lv.6 优秀      ≤3h       → score: 95
      Lv.7 卓越      >3h       → score: 100

    请求体示例:
    ```json
    {"duration_seconds": 3600}
    ```

    示例: POST /time-dimension/user_001/check-in
    """
    try:
        from services.time_dimension_service import check_in
        result = check_in(user_id, request.duration_seconds)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"学习打卡失败: {str(e)}")


# ==================== 我的资源库 API ====================

RESOURCE_TYPE_CONFIG = {
    "practice": {"icon": "💻", "label": "编程题"},
    "document": {"icon": "📄", "label": "文档"},
    "question": {"icon": "📝", "label": "理论题"},
    "extension": {"icon": "📚", "label": "拓展阅读"},
    "mindmap": {"icon": "🧠", "label": "思维导图"},
    "animation": {"icon": "🎨", "label": "动画"},
    "video": {"icon": "🎬", "label": "视频"},
    "ppt": {"icon": "📊", "label": "PPT"},
}


@app.get("/user/resources/{user_id}")
async def list_user_resources(user_id: str, limit: int = 50):
    """
    列出用户所有已生成的资源，按类型分组

    示例: GET /user/resources/user_001?limit=20
    """
    try:
        from memory.content_store import ContentStore
        store = ContentStore()
        groups = {}
        counts = {}

        for rtype, cfg in RESOURCE_TYPE_CONFIG.items():
            items = store.list_by_type(user_id, rtype, limit=limit)
            # 清理每个资源的元数据提取
            clean_items = []
            for item in items:
                entry = {
                    "id": item.get("_content_id", ""),
                    "saved_at": item.get("_saved_at", ""),
                    "icon": cfg["icon"],
                    "type_label": cfg["label"],
                    "type": rtype,
                }
                if rtype == "practice":
                    problem = item.get("problem", item)
                    entry["title"] = problem.get("title", "编程题")
                    entry["description"] = (problem.get("description", "") or "")[:120]
                    entry["knowledge_points"] = problem.get("knowledge_points", [])
                elif rtype == "document":
                    entry["title"] = item.get("doc_title", item.get("title", "文档"))
                    entry["description"] = (item.get("doc_content", item.get("summary", "")) or "")[:120]
                    entry["oss_url"] = item.get("oss_url", "")
                    entry["download_url"] = item.get("oss_url", "") or (f"/document/download/{user_id}/{item.get('_content_id', '')}" if item.get("file_path") else "")
                elif rtype == "question":
                    questions = item.get("questions", {})
                    first = None
                    if isinstance(questions, list) and len(questions) > 0:
                        first = questions[0]
                    elif isinstance(questions, dict):
                        first = questions
                    entry["title"] = "理论题"
                    if first:
                        entry["title"] = first.get("question", first.get("title", "理论题"))[:60]
                    entry["description"] = f"{len(questions) if isinstance(questions, list) else 1} 道题"
                elif rtype == "extension":
                    entry["title"] = item.get("title", "拓展阅读")
                    entry["description"] = (item.get("background", item.get("summary", item.get("content", ""))) or "")[:120]
                elif rtype == "mindmap":
                    mm = item.get("mindmap", item)
                    entry["title"] = mm.get("topic", mm.get("title", "思维导图"))
                    entry["description"] = f"{len(mm.get('nodes', mm.get('children', [])))} 个节点"
                elif rtype == "animation":
                    entry["title"] = item.get("topic", "教育动画")
                    html = item.get("html", "")
                    entry["description"] = f"HTML动画 ({len(html)} 字符)"
                elif rtype == "video":
                    videos = item.get("videos", item.get("recommendations", []))
                    if isinstance(videos, list) and len(videos) > 0:
                        first = videos[0] if isinstance(videos[0], dict) else {}
                        entry["title"] = first.get("title", first.get("name", "视频"))
                    else:
                        # ★★★ 兼容新格式：按 BVID 独立存储，数据直接在顶层 ★★★
                        entry["title"] = item.get("title", "视频资源")
                    entry["description"] = (item.get("description", "") or item.get("title", ""))[:120]
                elif rtype == "ppt":
                    raw_topic = item.get("topic", "")
                    # topic 可能包含用户画像脏数据，提取实际主题
                    lines = (raw_topic or "").split("\n")
                    clean_title = "PPT课件"
                    for line in lines:
                        l = line.strip()
                        if "】" in l:
                            l = l.split("】", 1)[1].strip()
                        if l.startswith("[user] "):
                            l = l[7:].strip()
                        if len(l) > 2:
                            clean_title = l
                            break
                    entry["title"] = clean_title
                    entry["description"] = f"{item.get('pages', 0)} 页"
                    entry["oss_url"] = item.get("oss_url", "")
                    entry["filename"] = item.get("filename", "")
                    entry["download_url"] = f"/ppt/download/{item.get('filename', '')}" if item.get("filename") else ""

                clean_items.append(entry)
            groups[rtype] = clean_items
            counts[rtype] = len(clean_items)
            print(f"  📦 [{user_id}] {rtype}: {len(clean_items)} 条")

        return {
            "success": True,
            "groups": groups,
            "counts": counts,
            "total": sum(counts.values()),
            "type_config": RESOURCE_TYPE_CONFIG,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取资源列表失败: {str(e)}")


@app.get("/user/resource/{user_id}/{resource_type}/{resource_id}")
async def get_user_resource(user_id: str, resource_type: str, resource_id: str):
    """
    获取单个用户生成资源的完整内容

    示例: GET /user/resource/user_001/animation/anim_xxx
    """
    try:
        from memory.content_store import ContentStore
        store = ContentStore()
        data = store.load(user_id, resource_type, resource_id)
        if not data:
            raise HTTPException(status_code=404, detail="资源不存在")
        return {"success": True, "resource": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载资源失败: {str(e)}")


@app.post("/api/user/resource-context")
async def report_resource_context(request: ResourceContextRequest):
    """
    上报用户当前查看的资源上下文（供摄像头模块感知资源类型）

    前端在用户打开/关闭资源时调用此接口，写入共享文件，
    摄像头模块（face-select）读取后传递给 AttentionTracker。

    Body:
        user_id: 用户ID
        resource_type: 资源类型 (practice/video/doc/mindmap/extension/animation)
        resource_id: 资源ID（可选）
        knowledge_point: 知识点（可选）
        action: open 或 close
    """
    try:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "user_context")
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, f"{request.user_id}.json")

        context = {
            "user_id": request.user_id,
            "resource_type": request.resource_type if request.action == "open" else "",
            "resource_id": request.resource_id if request.action == "open" else "",
            "knowledge_point": request.knowledge_point if request.action == "open" else "",
            "action": request.action,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)

        return {"success": True, "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入资源上下文失败: {str(e)}")


# ★★★ 新增：排行榜相关API ★★★

@app.get("/api/user/attention-profile/{user_id}")
async def get_attention_profile_endpoint(user_id: str):
    """
    查看用户注意力偏好画像（调试用）

    示例: GET /api/user/attention-profile/user_001
    """
    try:
        from Agent.children_agent.recommendation.attention_profile import get_profile
        profile = get_profile(user_id)
        summary = profile.get_summary()
        return {"success": True, "profile": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取注意力画像失败: {str(e)}")


# ==================== AI数字孪生（AI克隆）API ====================

@app.get("/digital-twin/{user_id}", tags=["数字孪生"])
async def get_digital_twin_status(user_id: str):
    """
    获取用户数字孪生状态和画像
    
    返回孪生是否启用、画像数据、对比统计等
    
    示例: GET /digital-twin/user_001
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()

        status = await service.get_twin_status_async(user_id)
        stats = await service.get_comparison_stats_async(user_id)

        return {
            "success": True,
            "user_id": user_id,
            "status": status,
            "stats": stats
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取孪生状态失败: {str(e)}")


@app.post("/digital-twin/{user_id}/toggle", tags=["数字孪生"])
async def toggle_digital_twin(user_id: str, enabled: bool = Body(..., embed=True)):
    """
    开启/关闭用户数字孪生
    
    请求体: { "enabled": true/false }
    
    示例: POST /digital-twin/user_001/toggle
         Body: { "enabled": true }
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()
        result = await service.set_twin_enabled_async(user_id, enabled)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "操作失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换孪生状态失败: {str(e)}")


@app.get("/digital-twin/{user_id}/build-stream", tags=["数字孪生"])
async def build_digital_twin_stream(user_id: str):
    """
    SSE流式构建数字孪生，实时推送进度
    
    事件格式:
    {
        "progress": int,     # 进度百分比 0-100
        "message": str,      # 简短状态信息
        "status": str,       # building/complete/error
        "detail": str        # 详细说明（当前在做什么、依据什么数据）
    }
    
    示例: GET /digital-twin/user_001/build-stream
    """
    from services.digital_twin_service import get_digital_twin_service
    from fastapi.responses import StreamingResponse

    service = get_digital_twin_service()

    async def event_generator():
        loop = asyncio.get_running_loop()
        # 在线程池中运行流式生成器
        gen = await loop.run_in_executor(
            None, lambda: list(service.build_twin_stream(user_id))
        )
        for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)  # 给前端一点时间渲染

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/digital-twin/{user_id}/rebuild-stream", tags=["数字孪生"])
async def rebuild_digital_twin_stream(user_id: str):
    """
    SSE流式重建数字孪生（保留对比历史）
    
    示例: GET /digital-twin/user_001/rebuild-stream
    """
    from services.digital_twin_service import get_digital_twin_service
    from fastapi.responses import StreamingResponse

    service = get_digital_twin_service()

    async def event_generator():
        loop = asyncio.get_running_loop()
        gen = await loop.run_in_executor(
            None, lambda: list(service.rebuild_twin_stream(user_id))
        )
        for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )



@app.get("/digital-twin/{user_id}/comparison", tags=["数字孪生"])
async def get_twin_comparison_history(
    user_id: str,
    limit: int = 50,
    result_type: Optional[str] = None
):
    """
    获取用户 vs 孪生对比历史
    
    参数:
    - limit: 返回条数（默认50）
    - result_type: 筛选类型（both_correct/both_wrong/user_right_twin_wrong/user_wrong_twin_right）
    
    示例: GET /digital-twin/user_001/comparison?limit=20&result_type=user_wrong_twin_right
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()
        history = await service.get_comparison_history_async(user_id, limit, result_type)
        return {
            "success": True,
            "user_id": user_id,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对比历史失败: {str(e)}")


@app.get("/digital-twin/{user_id}/stats", tags=["数字孪生"])
async def get_twin_comparison_stats(user_id: str):
    """
    获取对比统计摘要（含薄弱知识点分析）
    
    示例: GET /digital-twin/user_001/stats
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()
        stats = await service.get_comparison_stats_async(user_id)
        return {
            "success": True,
            "user_id": user_id,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对比统计失败: {str(e)}")


@app.delete("/digital-twin/{user_id}/history", tags=["数字孪生"])
async def clear_twin_comparison_history(user_id: str):
    """
    清空对比历史
    
    示例: DELETE /digital-twin/user_001/history
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()
        result = await service.clear_history_async(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空历史失败: {str(e)}")


@app.get("/digital-twin/{user_id}/comparison/{record_index}/analyze", tags=["数字孪生"])
async def analyze_twin_comparison(user_id: str, record_index: int):
    """
    基于用户和孪生的做题信息实时生成分析
    
    参数:
    - record_index: 对比历史记录的索引（从0开始）
    
    示例: GET /digital-twin/user_001/comparison/0/analyze
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()
        result = await service.analyze_comparison(user_id, record_index)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成分析失败: {str(e)}")


@app.get("/digital-twin/{user_id}/hints", tags=["数字孪生"])
async def get_twin_writing_hints(
    user_id: str,
    knowledge_points: str = "",
    code_snippet: str = ""
):
    """
    基于孪生画像获取编程提醒
    
    参数:
    - knowledge_points: 知识点列表（逗号分隔）
    - code_snippet: 当前已编写的代码（用于实时代码模式检测）
    
    示例: GET /digital-twin/user_001/hints?knowledge_points=循环,数组&code_snippet=for i in range
    """
    try:
        from services.digital_twin_service import get_digital_twin_service
        service = get_digital_twin_service()
        kps = [kp.strip() for kp in knowledge_points.split(",") if kp.strip()] if knowledge_points else []
        result = await service.get_writing_hints_async(user_id, kps, code_snippet)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取孪生提示失败: {str(e)}")


@app.post("/lint", tags=["代码"])
async def lint_code(request: dict):
    """代码语法检查
    
    POST /lint  {"code": "...", "language": "python|javascript|java|c|cpp"}
    返回: {"errors": [{"line": 1, "col": 0, "msg": "..."}]}
    """
    code = request.get("code", "")
    language = request.get("language", "python")
    errors = []

    if not code.strip():
        return {"errors": [], "language": language}

    try:
        if language == "python":
            import ast
            try:
                ast.parse(code)
            except SyntaxError as e:
                errors.append({
                    "line": e.lineno or 1,
                    "col": (e.offset or 1) - 1,
                    "msg": e.msg,
                    "end_col": (e.offset or 1),
                })

        elif language == "javascript":
            import tempfile, os, subprocess
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False)
            try:
                tmp.write(code)
                tmp.close()
                result = subprocess.run(['node', '--check', tmp.name],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    stderr = result.stderr or ''
                    # 解析 node 错误输出: "filename:line:col: error message"
                    import re
                    m = re.search(r':(\d+):(\d+)\s*(.*)', stderr)
                    if m:
                        errors.append({
                            "line": int(m.group(1)),
                            "col": int(m.group(2)) - 1,
                            "msg": m.group(3).strip(),
                            "end_col": int(m.group(2)),
                        })
                    else:
                        errors.append({"line": 1, "col": 0, "msg": stderr.strip()[:200]})
            finally:
                os.unlink(tmp.name)

        elif language == "java":
            import tempfile, os, subprocess
            # 提取 public class 名
            import re
            cls_match = re.search(r'public\s+class\s+(\w+)', code)
            if cls_match:
                class_name = cls_match.group(1)
            else:
                class_name = 'Main'
                # 如果没有 public class，包装一下
                code = 'public class Main {\n' + code + '\n}'
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False)
            try:
                tmp.write(code)
                tmp.close()
                result = subprocess.run(['javac', tmp.name],
                                        capture_output=True, text=True, timeout=15)
                if result.returncode != 0:
                    stderr = result.stderr or ''
                    for line in stderr.splitlines():
                        m = re.search(r'\.java:(\d+):\s*(error|warning):\s*(.*)', line)
                        if m:
                            errors.append({
                                "line": int(m.group(1)),
                                "col": 0,
                                "msg": m.group(3).strip(),
                                "end_col": 0,
                            })
                    if not errors:
                        errors.append({"line": 1, "col": 0, "msg": stderr.strip()[:200]})
            finally:
                os.unlink(tmp.name)
                # 清理生成的 .class 文件
                class_file = tmp.name.replace('.java', '.class')
                if os.path.exists(class_file):
                    os.unlink(class_file)

        elif language in ("c", "cpp"):
            errors.append({
                "line": 1, "col": 0,
                "msg": "当前服务器未安装 gcc/g++，C/C++ 语法检查不可用"
            })

    except FileNotFoundError:
        errors.append({
            "line": 1, "col": 0,
            "msg": f"{language} 的编译器未安装"
        })
    except subprocess.TimeoutExpired:
        errors.append({
            "line": 1, "col": 0,
            "msg": "语法检查超时"
        })
    except Exception as e:
        errors.append({
            "line": 1, "col": 0,
            "msg": f"检查失败: {str(e)[:100]}"
        })

    return {"errors": errors, "language": language}


@app.get("/digital-twin-page", tags=["页面"])
async def serve_digital_twin_page():
    """提供数字孪生管理前端页面"""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'digital_twin.html')
    if os.path.exists(html_path):
        from fastapi.responses import HTMLResponse
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="数字孪生页面未找到")


@app.get("/teacher-page")
async def teacher_page():
    """提供教师工作台前端页面"""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'teacher.html')
    if os.path.exists(html_path):
        from fastapi.responses import HTMLResponse
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="教师工作台页面未找到")


@app.get("/leaderboard/{problem_id}")
async def get_leaderboard_endpoint(
    problem_id: str,
    limit: int = 50,
    user_id: Optional[str] = None
):
    """
    获取题目排行榜（异步版本 - 支持多用户并发查询）
    
    示例: GET /leaderboard/P001?limit=20&user_id=user_001
    """
    try:
        from services.leaderboard_service import LeaderboardService
        from fastapi.concurrency import run_in_threadpool
        
        # ★★★ 在线程池中执行数据库查询，不阻塞事件循环 ★★★
        def query_leaderboard():
            leaderboard_service = LeaderboardService()
            return leaderboard_service.get_leaderboard(
                problem_id=problem_id,
                limit=limit,
                user_id=user_id
            )
        
        result = await run_in_threadpool(query_leaderboard)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取排行榜失败: {str(e)}")


@app.get("/leaderboard/{problem_id}/statistics")
async def get_problem_statistics_endpoint(problem_id: str):
    """
    获取题目统计信息（异步版本 - 使用线程池避免阻塞）
    
    示例: GET /leaderboard/P001/statistics
    """
    try:
        from services.leaderboard_service import LeaderboardService
        from fastapi.concurrency import run_in_threadpool
        
        # ★★★ 在线程池中执行同步SQLite查询，不阻塞事件循环 ★★★
        def query_statistics():
            leaderboard_service = LeaderboardService()
            return leaderboard_service.get_problem_statistics(problem_id)
        
        stats = await run_in_threadpool(query_statistics)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@app.get("/leaderboard/{problem_id}/user/{user_id}")
async def get_user_best_score_endpoint(problem_id: str, user_id: str):
    """
    获取用户在某题的最佳成绩（异步版本）
    
    示例: GET /leaderboard/P001/user/user_001
    """
    try:
        from services.leaderboard_service import LeaderboardService
        from fastapi.concurrency import run_in_threadpool
        
        # ★★★ 在线程池中执行 ★★★
        def query_best_score():
            leaderboard_service = LeaderboardService()
            return leaderboard_service.get_user_best_score(problem_id, user_id)
        
        best_score = await run_in_threadpool(query_best_score)
        
        if best_score is None:
            return {
                "success": True,
                "user_id": user_id,
                "problem_id": problem_id,
                "best_score": None,
                "message": "该用户尚未提交此题目"
            }
        
        return {
            "success": True,
            "user_id": user_id,
            "problem_id": problem_id,
            "best_score": best_score
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取用户最佳成绩失败: {str(e)}")


@app.get("/leaderboard/submission/{submission_id}/code")
async def get_submission_code_endpoint(submission_id: int, user_id: Optional[str] = None):
    """
    获取提交的完整代码（异步版本）
    
    示例: GET /leaderboard/submission/123/code?user_id=user_001
    """
    try:
        from services.leaderboard_service import LeaderboardService
        from fastapi.concurrency import run_in_threadpool
        
        # ★★★ 在线程池中执行 ★★★
        def query_code():
            leaderboard_service = LeaderboardService()
            return leaderboard_service.get_full_code(submission_id, user_id or "")
        
        result = await run_in_threadpool(query_code)
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "提交记录不存在"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取代码失败: {str(e)}")


# ==================== 全局用户排行榜 API ====================

@app.get("/api/global-ranking")
async def get_global_ranking_endpoint(
    limit: int = 50,
    user_id: Optional[str] = None
):
    """
    获取全局用户综合排行榜（异步版本）
    
    综合评分维度：
    - 编程能力分（30%）: 所有编程题提交的平均分
    - 准确率分（25%）: Accepted提交数 / 总提交数
    - 学习时长分（15%）: 基于time_management维度的分数
    - 做题数量分（15%）: 提交题目数量（非线性计算）
    - 综合特征分（15%）: 8维度特征的overall_score
    
    示例: GET /api/global-ranking?limit=20&user_id=user_001
    """
    try:
        from services.global_ranking_service import GlobalRankingService
        
        service = GlobalRankingService()
        result = await service.get_global_ranking(
            limit=limit,
            user_id=user_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取全局排行榜失败: {str(e)}")


@app.get("/api/global-ranking/user/{user_id}")
async def get_user_global_rank_endpoint(user_id: str):
    """
    获取用户的全局排名详情（真正异步版本）
    
    用途: 在排行榜页面中，当用户点击某个用户时，查看该用户的详细排名数据和各维度得分
    示例: GET /api/global-ranking/user/user_001
    """
    try:
        from services.global_ranking_service import GlobalRankingService
        
        service = GlobalRankingService()
        detail = await service.get_user_rank_detail(user_id)
        
        if detail is None:
            return {
                "success": True,
                "user_id": user_id,
                "rank": None,
                "message": "该用户不存在或无数据"
            }
        
        return {
            "success": True,
            "user_id": user_id,
            **detail
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取用户排名失败: {str(e)}")


# ==================== 代码比较 API ====================

class CompareRequest(BaseModel):
    """代码比较请求模型"""
    problem_id: str = Field(..., description="题目ID")
    submission_a_id: int = Field(..., description="提交A的ID")
    submission_b_id: int = Field(..., description="提交B的ID")


@app.post("/compare")
async def compare_solutions_endpoint(request: CompareRequest):
    """
    比较两个用户的解题方案（异步版本）  -------这个才是代码比较的情况
    示例:
    {
      "problem_id": "P001",
      "submission_a_id": 123,
      "submission_b_id": 456
    }
    """
    try:
        from predict.comparison_service import ComparisonService
        from fastapi.concurrency import run_in_threadpool
        
        def do_compare():
            comparison_service = ComparisonService()
            
            from services.leaderboard_service import LeaderboardService
            leaderboard_service = LeaderboardService()
            
            problem_data = leaderboard_service.get_problem_data(request.problem_id)
            if not problem_data:
                problem_data = {"problem_id": request.problem_id, "title": "未知题目"}
            
            return comparison_service.compare_two_solutions(
                problem_data=problem_data,
                submission_a_id=request.submission_a_id,
                submission_b_id=request.submission_b_id
            )
        
        result = await run_in_threadpool(do_compare)
        
        return {
            "success": True,
            "data": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"比较失败: {str(e)}")


@app.get("/leaderboard/user/{problem_id}/{user_id}")
async def get_user_submissions_for_problem(problem_id: str, user_id: str):
    """
    获取用户在某题目上的所有提交记录（用于比较功能）
    
    示例: GET /leaderboard/user/P001/user_001
    """
    try:
        from services.leaderboard_service import LeaderboardService
        from fastapi.concurrency import run_in_threadpool
        
        def query_submissions():
            leaderboard_service = LeaderboardService()
            return leaderboard_service.get_user_submissions(problem_id, user_id)
        
        result = await run_in_threadpool(query_submissions)
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取提交记录失败: {str(e)}")


# ==================== 语音识别 API ====================

@app.post("/speech/recognize")
async def recognize_speech(audio_file: UploadFile = File(...)):
    """
    ASR: 语音转文字接口
    
    接收音频文件，使用 Whisper 进行识别，返回识别结果文本
    
    Args:
        audio_file: 上传的音频文件（wav/mp3格式）
        
    Returns:
        {
            "success": true,
            "text": "识别出的文字",
            "duration": 录音时长（秒）
        }
    """
    try:
        import tempfile
        from Agent.TTS.speech_to_text import speech_to_text
        
        # 保存上传的音频文件到临时文件
        temp_suffix = os.path.splitext(audio_file.filename)[1] or '.wav'
        with tempfile.NamedTemporaryFile(delete=False, suffix=temp_suffix) as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        print(f"🎤 收到音频文件: {audio_file.filename}, 大小: {len(content)} bytes")
        
        try:
            # 使用 Whisper 进行语音识别（自动降级：讯飞优先→Whisper兜底）
            recognized_text = speech_to_text(
                audio_file=temp_path,
                method='auto',
                whisper_language='zh'  # 默认中文
            )
            
            # 删除临时文件
            os.remove(temp_path)
            
            if recognized_text and recognized_text.strip():
                # ★★★ 繁转简（Whisper 可能输出繁体中文）★★★
                from zhconv import convert
                recognized_text = convert(recognized_text, 'zh-cn')
                print(f"✅ ASR识别成功: {recognized_text}")
                return {
                    "success": True,
                    "text": recognized_text.strip(),
                    "filename": audio_file.filename
                }
            else:
                raise Exception("识别结果为空")
                
        except Exception as e:
            # 确保删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
        
    except ImportError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"缺少依赖: {str(e)}\n请安装: pip install openai-whisper pyaudio"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"语音识别失败: {str(e)}")


# ==================== TTS 语音合成 API ====================

class TTSRequest(BaseModel):
    """TTS语音合成请求模型"""
    text: str = Field(..., description="要转为语音的文本内容")
    user_id: str = Field(default="user_001", description="用户ID（用于读取音色偏好）")


@app.post("/speech/tts")
async def text_to_speech_endpoint(request: TTSRequest):
    """
    TTS: 文本转语音接口
    
    根据用户ID读取其音色偏好（支持 Edge TTS 和 VoxCPM），
    生成对应的语音文件并返回访问URL。
    
    Args:
        request: TTSRequest {text, user_id}
        
    Returns:
        {
            "success": true,
            "audio_url": "/static/tts_audio/xxx.mp3",
            "method": "edge_tts" | "voxcpm"
        }
    """
    try:
        from utils.tts_helper import generate_tts_audio

        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="文本内容不能为空")

        # 生成TTS音频（自动读取用户音色偏好）
        audio_url = await generate_tts_audio(
            text=text,
            agent_name="warning_alert",
            user_id=request.user_id,
        )

        if audio_url:
            return {
                "success": True,
                "audio_url": audio_url,
                "method": "auto",
            }
        else:
            # fallback: 使用默认 edge_tts 再试一次
            audio_url = await generate_tts_audio(
                text=text,
                agent_name="warning_alert",
                method="edge_tts",
                voice_profile=None,
            )
            if audio_url:
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "method": "edge_tts_fallback",
                }
            raise HTTPException(status_code=500, detail="TTS生成失败")

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"缺少依赖: {str(e)}\n请安装: pip install edge-tts"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS生成失败: {str(e)}")


# ==================== 动画生成 API ====================

class AnimationRequest(BaseModel):
    """动画生成请求模型"""
    user_id: str = Field(..., description="用户ID")
    topic: str = Field(..., description="动画主题")
    enable_tts: bool = Field(default=True, description="是否启用TTS语音解说")


class StudyPlanRequest(BaseModel):
    """学习路径规划请求模型"""
    user_id: str = Field(..., description="用户ID")
    user_input: str = Field(..., description="学习目标描述，如：3个月学完Python")
    enable_tts: bool = Field(default=False, description="是否启用TTS语音反馈")
    ignore_weak_points: bool = Field(default=False, description="是否忽略薄弱点提示，继续生成计划")
    focus_weak_points: bool = Field(default=False, description="是否针对薄弱点制定学习计划")


class SwitchPlanRequest(BaseModel):
    """切换学习计划请求模型"""
    plan_id: str = Field(..., description="目标计划ID")
    phase_index: Optional[int] = Field(None, description="阶段索引（可选，提供时一并返回阶段进度）")


class RegeneratePhaseRequest(BaseModel):
    """重新生成阶段请求模型"""
    phase_index: int = Field(..., description="目标阶段索引（从0开始）")
    plan_id: str = Field(..., description="当前计划ID（用于版本族场景）")


@app.post("/animation/generate")
async def generate_animation_endpoint(request: AnimationRequest):
    """
    生成教育动画HTML
    
    示例:
    {
      "user_id": "user_001",
      "topic": "光合作用",
      "enable_tts": true
    }
    """
    try:
        from Agent.children_agent.wx_html_create import AnimationAgent
        
        animation_agent = AnimationAgent()
        
        # 调用动画生成
        result = await animation_agent.generate_animation(
            topic=request.topic,
            user_id=request.user_id,
            enable_tts=request.enable_tts
        )
        
        return {
            "success": result.get("status") == "success",
            "data": result
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"动画生成失败: {str(e)}")


@app.post("/ppt/generate")
async def generate_ppt_endpoint(request: PPTRequest):
    """
    生成PPT

    示例:
    {
      "user_id": "user_001",
      "topic": "Python循环结构",
      "style": "新中式科技风",
      "page_count": 4
    }
    """
    try:
        from Agent.children_agent.ppt_agent import PPTCreationAgent

        agent = PPTCreationAgent()
        result = await agent.generate_ppt_async(
            topic=request.topic,
            style=request.style,
            page_count=request.page_count,
            user_id=request.user_id,
        )

        if result.get("status") == "success":
            return {
                "success": True,
                "data": result,
                "message": result.get("message", ""),
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "生成失败"),
                "error": result.get("message", ""),
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PPT生成失败: {str(e)}")


@app.get("/ppt/download/{filename}")
async def download_ppt(filename: str, viewer_id: Optional[str] = None):
    """下载生成的PPT文件（OSS代理优先，本地兜底）
    若提供 viewer_id，自动将 Markdown 内容写入其工作记忆。
    """
    import os
    from fastapi.responses import FileResponse

    filepath = ""
    oss_key = ""
    markdown_path = ""
    ppt_topic = ""

    # ★★★ 先在 ContentStore 中通过文件名查找 ★★★
    try:
        from memory.content_store import ContentStore
        store = ContentStore()
        from memory.content_store import USER_FEATURES_DIR
        for user_dir in USER_FEATURES_DIR.iterdir():
            if not user_dir.is_dir():
                continue
            content_dir = user_dir / "content"
            if not content_dir.exists():
                continue
            for pattern in ("phase_ppt_*.json", "ppt_*.json"):
                for f in content_dir.glob(pattern):
                    try:
                        import json
                        data = json.loads(f.read_text(encoding="utf-8"))
                        ppt_inner = data.get("ppt", data)
                        if ppt_inner.get("filename") == filename:
                            filepath = ppt_inner.get("filepath", "")
                            if not filepath or not os.path.exists(filepath):
                                filepath = ""
                            oss_key = ppt_inner.get("oss_key", "") or data.get("oss_key", "")
                            markdown_path = ppt_inner.get("markdown_path", "") or data.get("markdown_path", "")
                            ppt_topic = ppt_inner.get("topic", "") or data.get("topic", "")
                            break
                    except Exception:
                        pass
                if filepath or oss_key:
                    break
            if filepath or oss_key:
                break
    except Exception:
        pass

    # ★★★ 若有 viewer_id，写入 MemoryHub 工作记忆 ★★★
    if viewer_id:
        try:
            from memory import get_shared_memory_hub
            hub = get_shared_memory_hub()
            md_content = ""
            if markdown_path and os.path.exists(markdown_path):
                with open(markdown_path, "r", encoding="utf-8") as _f:
                    md_content = _f.read()
            if not md_content:
                md_content = _find_ppt_markdown(filename, ppt_topic)
            if not md_content and ppt_topic:
                md_content = f"# {ppt_topic}"
            if md_content:
                summary = md_content[:2000] + ("..." if len(md_content) > 2000 else "")
                hub.working.set_last_generated(
                    user_id=viewer_id,
                    resource_type="ppt",
                    resource_id=filename,
                    summary=summary,
                )
                print(f"  📚 [PPT下载] Markdown 已注入 {viewer_id} 的工作记忆")
        except Exception as e:
            print(f"  ⚠️ [PPT下载] MemoryHub 写入失败: {e}")

    # ★★★ OSS 优先 → 服务端代理下载（避免浏览器处理 %2F 编码 URL 时文件损坏） ★★★
    if oss_key:
        try:
            from services.oss_storage import _get_bucket
            bucket = _get_bucket()
            if bucket is not None:
                import asyncio, urllib.parse
                def _oss_download():
                    result = bucket.get_object(oss_key)
                    return result.read()
                content = await asyncio.to_thread(_oss_download)
                # 下载文件名：优先用主题名，否则用原始文件名
                topic_label = "".join(c for c in ppt_topic if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:60] if ppt_topic else ""
                dl_name = f"{topic_label}.pptx" if topic_label else filename
                # RFC 5987: 中文文件名编码 (ascii_fallback + utf-8 urlencoded)
                ascii_fallback = f"{topic_label}.pptx" if topic_label and topic_label.isascii() else "download.pptx"
                utf8_encoded = urllib.parse.quote(dl_name, safe='')
                from fastapi.responses import Response
                print(f"  📦 [PPT下载] OSS代理下载 ({len(content)} bytes) → {dl_name}")
                return Response(
                    content=content,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_encoded}"},
                )
        except Exception as e:
            print(f"  ⚠️ [PPT下载] OSS代理下载失败，回退到本地: {e}")

    # ★★★ OSS 不可用时，本地文件兜底 ★★★
    if filepath and os.path.exists(filepath):
        topic_label = "".join(c for c in ppt_topic if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:60] if ppt_topic else ""
        dl_name = f"{topic_label}.pptx" if topic_label else filename
        return FileResponse(
            filepath,
            filename=dl_name,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    # ★★★ 最后回退：从固定路径查找 ★★★
    fallback = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Agent", "children_agent", "PPT", "ppt_create", "outputs", filename
    )
    if os.path.exists(fallback):
        # 从文件名提取主题（新命名规则）
        dl_name = filename
        if "_" in filename and filename.endswith(".pptx"):
            dl_name = filename.rsplit("_", 1)[0] + ".pptx"
        return FileResponse(
            fallback,
            filename=dl_name,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    raise HTTPException(status_code=404, detail="PPT文件不存在或已过期")


@app.get("/document/download/{user_id}/{doc_id}")
async def download_document(user_id: str, doc_id: str):
    """下载生成的Word文档（OSS代理优先，本地兜底）"""
    import os
    import urllib.parse
    from fastapi.responses import FileResponse, Response
    try:
        from memory.content_store import ContentStore
        store = ContentStore()
        # ★★★ 同时查找 document 和 phase_doc 类型 ★★★
        doc = store.load(user_id, "document", doc_id)
        if not doc:
            doc = store.load(user_id, "phase_doc", doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档记录不存在")

        doc_title = doc.get("doc_title", doc.get("title", "文档"))

        # ★★★ 1. OSS 优先：通过 oss_key 代理下载 ★★★
        oss_key = doc.get("oss_key", "")
        if oss_key:
            try:
                from services.oss_storage import _get_bucket
                bucket = _get_bucket()
                if bucket is not None:
                    import asyncio
                    def _oss_download():
                        result = bucket.get_object(oss_key)
                        return result.read()
                    content = await asyncio.to_thread(_oss_download)
                    doc_label = "".join(c for c in doc_title if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:60] or "文档"
                    dl_name = f"{doc_label}.docx"
                    utf8_encoded = urllib.parse.quote(dl_name, safe='')
                    print(f"  📦 [文档下载] OSS代理下载 ({len(content)} bytes) → {dl_name}")
                    return Response(
                        content=content,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename=\"{dl_name}\"; filename*=UTF-8''{utf8_encoded}"},
                    )
            except Exception as e:
                print(f"  ⚠️ [文档下载] OSS代理下载失败，回退到本地: {e}")

        # ★★★ 2. 本地文件兜底 ★★★
        raw_path = doc.get("file_path", "")
        file_path = ""
        if raw_path:
            candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), raw_path) if not os.path.isabs(raw_path) else raw_path
            if os.path.exists(candidate):
                file_path = candidate
        if not file_path:
            import glob
            base_dir = os.path.dirname(os.path.abspath(__file__))
            for pattern in (
                os.path.join(base_dir, "generated_documents", f"{doc_title}_*.docx"),
                os.path.join(base_dir, "generated_documents", f"*{doc_id}*.docx"),
            ):
                matches = glob.glob(pattern)
                if matches:
                    file_path = matches[0]
                    break

        if file_path:
            filename = os.path.basename(file_path)
            return FileResponse(file_path, filename=filename,
                                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        raise HTTPException(status_code=404, detail="文档文件不存在或已过期")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载文档失败: {str(e)}")


# ==================== 音色偏好管理 API =====================

class VoiceProfileRequest(BaseModel):
    """音色偏好设置请求"""
    user_id: str = Field(..., description="用户ID")
    method: str = Field("edge_tts", description="生成方式: edge_tts / voxcpm")
    mode: Optional[str] = Field(None, description="VoxCPM 模式: design / clone / ultimate_clone")
    control: Optional[str] = Field(None, description="声音描述（design/clone 模式使用）")
    prompt_text: Optional[str] = Field(None, description="参考音频转录文本（ultimate_clone 模式使用）")
    reference_audio_filename: Optional[str] = Field(None, description="已上传的参考音频文件名")
    cfg_value: float = Field(2.0, ge=0.1, le=10.0, description="CFG 引导强度")
    inference_timesteps: int = Field(10, ge=1, le=100, description="扩散步数")


@app.post("/api/user/voice-profile/upload-sample")
async def upload_voice_sample(
    user_id: str = Form(...),
    audio_file: UploadFile = File(..., description="用户的语音样本（wav/mp3）"),
):
    """上传用户的语音样本"""
    try:
        from services.voice_profile_service import VoiceProfileService
        content = await audio_file.read()
        svc = VoiceProfileService()
        result = svc.upload_sample(user_id, audio_file.filename or "sample.wav", content)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.post("/api/user/voice-profile")
async def set_voice_profile(request: VoiceProfileRequest):
    """设置用户的音色偏好"""
    try:
        from services.voice_profile_service import VoiceProfileService
        svc = VoiceProfileService()
        profile = svc.set_profile(request.user_id, request.model_dump())
        return {"success": True, "user_id": request.user_id, "voice_profile": profile}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置失败: {str(e)}")


@app.get("/api/user/voice-profile/{user_id}")
async def get_voice_profile(user_id: str):
    """获取用户的当前音色偏好配置"""
    from services.voice_profile_service import VoiceProfileService
    svc = VoiceProfileService()
    profile = svc.get_profile(user_id)
    if profile:
        return {"success": True, "user_id": user_id, "voice_profile": profile}
    return {"success": True, "user_id": user_id, "voice_profile": {"method": "edge_tts"},
            "message": "用户未设置音色偏好，当前使用默认 Edge TTS"}


@app.delete("/api/user/voice-profile/{user_id}")
async def reset_voice_profile(user_id: str):
    """重置用户音色偏好为默认"""
    from services.voice_profile_service import VoiceProfileService
    svc = VoiceProfileService()
    svc.reset_profile(user_id)
    return {"success": True, "user_id": user_id, "message": "音色偏好已重置为默认 Edge TTS"}


@app.post("/api/user/voice-profile/preview")
async def preview_voice_profile(request: VoiceProfileRequest):
    """
    预览音色效果 —— 生成一段示例语音但不保存配置
    """
    try:
        from services.voice_profile_service import VoiceProfileService
        from utils.tts_helper import generate_tts_audio

        svc = VoiceProfileService()
        voice_profile = svc.build_voice_profile_for_preview(request.model_dump(), request.user_id)
        method = request.method

        preview_text = "你好，这是您的个性化语音预览，听听看这个音色是否满意。"
        audio_url = await generate_tts_audio(
            text=preview_text,
            agent_name="voice_preview",
            method=method,
            voice_profile=voice_profile,
        )

        if audio_url:
            return {"success": True, "audio_url": audio_url}
        raise HTTPException(status_code=500, detail="预览音频生成失败")

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")






# ==================== 视频观看行为上报 ====================

class VideoWatchReport(BaseModel):
    """视频观看行为上报"""
    user_id: str = Field(..., description="用户ID")
    video_info: Dict[str, Any] = Field(default_factory=dict, description="视频信息")
    watch_data: Dict[str, Any] = Field(default_factory=dict, description="观看行为数据")


@app.post("/video/report-watch", tags=["视频"])
async def report_video_watch(request: VideoWatchReport):
    """
    上报视频观看行为数据（用于更新学生特征）
    
    示例:
    {
      "user_id": "user_001",
      "video_info": {
        "title": "C语言指针教程",
        "author": "某UP主",
        "url": "https://www.bilibili.com/video/BV1xx...",
        "bvid": "BV1xx..."
      },
      "watch_data": {
        "watch_duration": "120s",
        "total_duration": "600s",
        "completion_rate": "20%",
        "pause_count": 3,
        "rewind_count": 2,
        "rewind_events": [{"from": 300, "to": 180, "time": "2024-01-01T00:00:00Z"}],
        "engagement_signals": {
          "significant_rewinds": 2,
          "total_rewinds": 2,
          "user_active": true,
          "watch_progress": "20%"
        }
      }
    }
    """
    try:
        user_id = request.user_id
        watch_data = request.watch_data or {}
        video_info = request.video_info or {}

        print(f"\n📊 [视频观看上报] 用户 {user_id}")
        print(f"   视频: {video_info.get('title', '未知')}")
        print(f"   观看进度: {watch_data.get('completion_rate', '0%')}")
        print(f"   回溯次数: {watch_data.get('rewind_count', 0)}")
        print(f"   暂停次数: {watch_data.get('pause_count', 0)}")

        # ★★★ 数字孪生对比：自动记录视频观看对比 ★★★
        try:
            from services.digital_twin_service import get_digital_twin_service
            twin = get_digital_twin_service()

            # 解析 completion_rate
            cr_raw = str(watch_data.get("completion_rate", "0%")).replace("%", "").strip()
            try:
                completion_rate = float(cr_raw) / 100.0
            except ValueError:
                completion_rate = 0.0

            # 解析 watch_duration
            dur_raw = str(watch_data.get("watch_duration", "0")).replace("s", "").strip()
            try:
                watch_duration = int(float(dur_raw))
            except ValueError:
                watch_duration = 0

            await twin.record_user_activity_async(
                user_id, "video_watch",
                {
                    "bvid": video_info.get("bvid", ""),
                    "video_title": video_info.get("title", ""),
                    "knowledge_point": "",
                    "difficulty": 0.3,
                },
                {
                    "completion_rate": completion_rate,
                    "watch_duration": watch_duration,
                    "rewind_count": int(watch_data.get("rewind_count", 0)),
                }
            )
        except Exception:
            pass  # 孪生对比不阻塞主流程

        # ★★★ 仅记录日志，不再轮询更新特征 ★★★
        # 特征更新仅在用户确认回溯困惑时通过 /video/rewind-event 触发
        print(f"   📝 观看数据已记录（跳过特征更新，等待回溯事件）")
        return {
            "success": True,
            "data": {
                "status": "logged",
                "message": "观看数据已记录，特征更新仅在回溯困惑时触发",
                "rewind_count": watch_data.get('rewind_count', 0)
            }
        }

    except Exception as e:
        print(f"   ❌ 视频观看上报失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 视频看完触发测试 ====================

class VideoTriggerQuizRequest(BaseModel):
    """视频看完触发测试请求"""
    user_id: str = Field(..., description="用户ID")
    video_title: str = Field(default="", description="视频标题")
    bvid: str = Field(default="", description="视频BVID")


@app.post("/video/trigger-quiz", tags=["视频"])
async def trigger_video_quiz(request: VideoTriggerQuizRequest):
    """
    视频观看完成后触发小测试（生成练习题和理论题）
    
    等待管道执行完成，返回生成的题目内容。
    
    示例:
    {
      "user_id": "user_001",
      "video_title": "Go语言核心知识点",
      "bvid": "BV1GJ411x7FE"
    }
    """
    try:
        user_id = request.user_id
        video_title = request.video_title
        bvid = request.bvid
        
        print(f"\n🎯 [视频触发测试] 用户 {user_id}, 视频: {video_title}")
        
        from services.collaboration_orchestrator import trigger_pipeline_async
        
        # ★★★ 走 trigger_pipeline_async，复用计划检查 + 管道映射逻辑 ★★★
        result = await trigger_pipeline_async(
            event_type="video_completed",
            user_id=user_id,
            context={"video_title": video_title, "bvid": bvid, "topic": video_title},
        )
        
        if result.get("skipped"):
            return {
                "success": False,
                "pipeline_triggered": False,
                "message": result.get("reason", "已跳过"),
            }

        if result.get("success"):
            generated = result.get("generated_resources", {})
            practice = generated.get("practice", {})
            question = generated.get("question", {})
            
            print(f"  ✅ 管道完成，生成 practice={bool(practice)}, question={bool(question)}")
            
            return {
                "success": True,
                "message": "测试题已生成",
                "pipeline_triggered": True,
                "practice": practice,
                "question": question,
            }
        else:
            return {
                "success": False,
                "error": f"管道执行失败: {result.get('failed', '未知')}/{result.get('total_steps', 0)} 步骤失败",
                "pipeline_triggered": True,
            }
        
    except Exception as e:
        print(f"   ❌ 触发测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 视频回溯事件上报 ====================

class VideoRewindEvent(BaseModel):
    """视频回溯事件（困惑检测）"""
    user_id: str = Field(..., description="用户ID")
    bvid: str = Field(..., description="视频BVID")
    video_title: str = Field(default="", description="视频标题")
    rewind_from: float = Field(0, description="回溯前的时间点(秒)")
    rewind_to: float = Field(0, description="回溯后的时间点(秒)")
    rewind_gap: int = Field(0, description="回溯倒退秒数")
    is_confused: bool = Field(default=False, description="用户是否表示困惑")
    page: int = Field(default=1, description="视频分P编号（多P视频使用）")


@app.post("/video/rewind-event", tags=["视频"])
async def report_video_rewind_event(request: VideoRewindEvent):
    """
    上报视频回溯事件（用户回看/困惑）
    
    1. 将回溯事件写入 MemoryHub 工作记忆，ChatAgent 回复时自动感知
    2. 若用户确认困惑，更新学生特征（video_confusion维度）
    3. 记录回溯上下文供后续对话使用

    示例:
    {
      "user_id": "user_001",
      "bvid": "BV1e4411x7VM",
      "video_title": "Python入门教程",
      "rewind_from": 600.5,
      "rewind_to": 180.2,
      "rewind_gap": 420,
      "is_confused": true
    }
    """
    try:
        user_id = request.user_id
        video_title = request.video_title or request.bvid
        is_confused = request.is_confused

        print(f"\n↩ [回溯事件] 用户 {user_id}")
        print(f"   视频: {video_title} ({request.bvid})")
        print(f"   回看: {format_time_short(request.rewind_from)} → {format_time_short(request.rewind_to)}")
        print(f"   困惑: {'是' if is_confused else '否（复习）'}")

        # ★★★ 0. 若用户确认困惑，获取视频CID并拉取对应时间段的字幕 ★★★
        subtitle_text = ''
        if is_confused:
            try:
                from services.bili_stream_service import _bili_client
                # 先获取视频信息拿到 cid
                info = _bili_client.get_video_info(request.bvid)
                cid = info.get('cid', 0)
                if not cid:
                    pages = info.get('pages', [])
                    cid = pages[0].get('cid', 0) if pages else 0
                if cid:
                    # 获取回溯时间段的字幕（从 rewind_to 到 rewind_from）
                    subtitle_text = _bili_client.get_subtitle_snippet(
                        request.bvid, cid,
                        from_sec=float(request.rewind_to),
                        to_sec=float(request.rewind_from),
                        page=request.page,
                    )
                    if subtitle_text:
                        print(f"   📝 获取到回溯段字幕: {len(subtitle_text)} 字符")
                    else:
                        print(f"   ℹ️ 该视频暂无字幕或该时间段无字幕内容")
            except Exception as e:
                print(f"   ⚠️ 获取字幕失败: {e}")

        # ★★★ 1. 写入 MemoryHub 工作记忆 ★★★
        try:
            from memory import get_shared_memory_hub
            hub = get_shared_memory_hub()

            if is_confused:
                # 构建含字幕内容的summary
                summary_parts = [
                    f'【视频回溯-困惑】用户在观看视频「{video_title}」时，',
                    f'将进度从 {format_time_short(request.rewind_from)} 回退到 {format_time_short(request.rewind_to)}',
                    f'（倒退 {request.rewind_gap} 秒），并标注为"有疑惑"。',
                ]
                if subtitle_text:
                    summary_parts.append(
                        f'【回退时间段视频字幕内容（{format_time_short(request.rewind_to)} ~ {format_time_short(request.rewind_from)}）】\n'
                        f'{subtitle_text}'
                    )
                summary_parts.append(
                    f'请基于以上字幕内容，主动询问用户对这段内容的具体疑问，并提供针对性解答。'
                )
                confusion_summary = '\n'.join(summary_parts)
                hub.working.set_last_generated(
                    user_id=user_id,
                    resource_type="video_rewind",
                    resource_id=request.bvid,
                    summary=confusion_summary
                )
                # 同时添加一条助手记忆到对话轮次
                hub.working.add_turn(
                    user_id=user_id,
                    role="assistant",
                    content=f"[系统] 检测到用户在视频「{video_title}」{format_time_short(request.rewind_from)}处回退，可能存在困惑",
                    metadata={"type": "video_rewind", "bvid": request.bvid}
                )
                # 关注此知识点
                hub.working.add_focus_knowledge(user_id, video_title)
                print(f"   ✅ 已将回溯困惑注入工作记忆")
            else:
                # 复习行为，轻量记录
                hub.working.add_focus_knowledge(user_id, video_title)
                print(f"   📝 已记录复习行为")

        except Exception as e:
            print(f"   ⚠️ MemoryHub 写入失败: {e}")

        # ★★★ 2. 若用户确认困惑，更新学生特征（轻量更新）★★★
        if is_confused:
            try:
                from fastapi.concurrency import run_in_threadpool
                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater

                async def _update_feature_for_confusion():
                    updater = DynamicFeatureUpdater()
                    features = await run_in_threadpool(updater.get_latest_features, user_id)
                    if not features:
                        return {"status": "skipped"}

                    await updater.update_features_async(
                        current_features=features,
                        task_type="video_rewind_confusion",
                        task_content=f"视频回溯困惑: {video_title} ({format_time_short(request.rewind_from)}→{format_time_short(request.rewind_to)})",
                        performance_data={
                            "rewind_gap": request.rewind_gap,
                            "video_title": video_title,
                            "bvid": request.bvid,
                            "is_confused": True,
                        },
                        completion_quality="medium",
                        user_id=user_id
                    )
                    return {"status": "success"}

                await _update_feature_for_confusion()
                print(f"   ✅ 特征已更新（video_confusion）")

            except Exception as e:
                print(f"   ⚠️ 特征更新失败: {e}")

        return {
            "success": True,
            "data": {
                "bvid": request.bvid,
                "is_confused": is_confused,
                "context_injected": is_confused
            }
        }

    except Exception as e:
        print(f"   ❌ 回溯事件处理失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def format_time_short(seconds: float) -> str:
    """将秒数格式化为 mm:ss"""
    if seconds < 0:
        return "0:00"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


# ==================== 测试页面路由 ====================
@app.get("/test-page", tags=["页面"])
async def serve_test_page():
    """提供 Agent 测试平台页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'agent_test.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="测试页面未找到")


@app.get("/global-ranking-page", tags=["页面"])
async def serve_global_ranking_page():
    """提供全局用户排行榜页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'global_ranking.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="排行榜页面未找到")


# ==================== 笔记功能 API ====================

# ★★★ 特征更新任务队列模式 ★★★
# 笔记保存时只把任务丢进队列，立即释放主线程
# 后台消费者串行处理，即使卡住也不影响用户请求
_feature_update_queue = asyncio.Queue(maxsize=20)
_feature_update_consumer_task = None

async def _feature_update_consumer():
    """后台消费者：串行处理特征更新任务，不阻塞任何用户请求"""
    while True:
        task = await _feature_update_queue.get()
        try:
            from services.note_service import trigger_note_feature_update
            await asyncio.wait_for(
                trigger_note_feature_update(**task),
                timeout=300.0  # 5分钟超时，LLM慢时也不误杀
            )
            print(f"   ✅ [特征更新] 任务完成")
        except asyncio.TimeoutError:
            print(f"   ⚠️ [特征更新] 任务超时(300s)，跳过")
        except Exception as e:
            print(f"   ⚠️ [特征更新] 任务异常: {e}")
        finally:
            _feature_update_queue.task_done()

async def _safe_trigger_feature_update(user_id: str, title: str, content: str, action: str = "save", use_ai: bool = False):
    """安全触发特征更新：入队列后立即返回，绝不阻塞主线程"""
    global _feature_update_consumer_task
    if _feature_update_consumer_task is None:
        _feature_update_consumer_task = asyncio.create_task(_feature_update_consumer())
        print("   🚀 [特征更新] 消费者已启动")

    task = {
        "user_id": user_id, "title": title, "content": content,
        "action": action, "use_ai": use_ai,
    }
    try:
        await asyncio.wait_for(_feature_update_queue.put(task), timeout=1.0)
        print(f"   📋 [特征更新] 任务已入队列")
    except asyncio.TimeoutError:
        print(f"   ⚠️ [特征更新] 队列已满(20)，丢弃任务")

@app.get("/notes/{user_id}")
async def list_notes(user_id: str):
    """获取用户笔记列表"""
    try:
        from services.note_service import list_notes
        notes = list_notes(user_id)
        return {"success": True, "notes": notes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取笔记列表失败: {str(e)}")


@app.post("/notes/{user_id}")
async def create_note(user_id: str, request: NoteCreateRequest):
    """创建笔记（AI 整理改走 preview/accept 流程，不再在此处理）"""
    try:
        from services.note_service import create_note as sync_create_note
        note = sync_create_note(user_id, request.title, request.content)

        # ★★★ 后台线程安全执行特征更新（限制并发，不阻塞主响应）★★★
        asyncio.create_task(_safe_trigger_feature_update(
            user_id, request.title, request.content, action="create", use_ai=False
        ))

        return {"success": True, "note": note}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"保存笔记失败: {str(e)}")


@app.get("/notes/{user_id}/graph-data")
async def get_note_graph_data(user_id: str):
    """获取笔记知识图谱数据（节点和边）"""
    try:
        from services.note_service import get_graph_data
        data = get_graph_data(user_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图谱数据失败: {str(e)}")


@app.get("/notes/{user_id}/search")
async def search_notes(user_id: str, q: str = ""):
    """搜索笔记标题（用于 [[ 提及自动补全）"""
    try:
        from services.note_service import list_notes
        notes = list_notes(user_id)
        if q:
            q_lower = q.lower()
            notes = [n for n in notes if q_lower in n.get("title", "").lower()]
        return {"success": True, "notes": notes[:20]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索笔记失败: {str(e)}")


@app.get("/notes/{user_id}/{note_id}")
async def get_note(user_id: str, note_id: str):
    """获取单篇笔记详情"""
    try:
        from services.note_service import get_note
        note = get_note(user_id, note_id)
        if note is None:
            raise HTTPException(status_code=404, detail="笔记不存在")
        return {"success": True, "note": note}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取笔记失败: {str(e)}")


@app.put("/notes/{user_id}/{note_id}")
async def update_note(user_id: str, note_id: str, request: NoteUpdateRequest):
    """更新笔记"""
    try:
        from services.note_service import update_note as sync_update_note
        note = await asyncio.to_thread(
            sync_update_note, user_id, note_id,
            title=request.title, content=request.content,
            knowledge_points=request.knowledge_points
        )
        if note is None:
            raise HTTPException(status_code=404, detail="笔记不存在")

        # ★★★ 后台线程安全执行特征更新（限制并发，不阻塞主响应）★★★
        asyncio.create_task(_safe_trigger_feature_update(
            user_id, request.title or note.get("title", ""),
            request.content or note.get("content", ""), action="update"
        ))

        return {"success": True, "note": note}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新笔记失败: {str(e)}")


@app.delete("/notes/{user_id}/{note_id}")
async def delete_note(user_id: str, note_id: str):
    """删除笔记"""
    try:
        from services.note_service import delete_note
        ok = delete_note(user_id, note_id)
        if not ok:
            raise HTTPException(status_code=404, detail="笔记不存在")
        return {"success": True, "message": "笔记已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除笔记失败: {str(e)}")


@app.post("/notes/{user_id}/{note_id}/organize-preview")
async def organize_note_preview(user_id: str, note_id: str, request: NoteOrganizeRequest):
    """
    AI 整理预览：运行 AI 整理逻辑，返回原始 vs 整理结果的 diff 数据，不保存到笔记。
    前端展示 diff 对比后，由用户决定是否调用 /organize-preview/accept 接受。
    """
    try:
        from services.note_service import organize_note_preview as preview_func
        result = await preview_func(user_id, note_id, request.title, request.content)
        return {"success": True, "preview": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"AI 整理预览失败: {str(e)}")


class NoteAcceptOrganizeRequest(BaseModel):
    title: str = Field(..., description="整理后的标题")
    organized_content: str = Field(..., description="整理后的内容")
    ai_result: Dict[str, Any] = Field(..., description="AI 整理附加结果（terms, error_prone_points, corrections, summary, knowledge_points）")


@app.post("/notes/{user_id}/{note_id}/organize-preview/accept")
async def accept_organize_preview(user_id: str, note_id: str, request: NoteAcceptOrganizeRequest):
    """接受 AI 整理结果，保存到笔记"""
    try:
        from services.note_service import accept_organize_preview as accept_func
        note = await accept_func(user_id, note_id, request.title, request.organized_content, request.ai_result)
        if note is None:
            raise HTTPException(status_code=404, detail="笔记不存在")

        # ★★★ 后台线程安全执行特征更新 ★★★
        asyncio.create_task(_safe_trigger_feature_update(
            user_id, request.title, request.organized_content, action="ai_organized", use_ai=True
        ))

        return {"success": True, "note": note}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"接受整理结果失败: {str(e)}")


class NoteMindmapRequest(BaseModel):
    title: str = Field(..., description="笔记标题")
    content: str = Field(..., description="笔记内容")


@app.post("/api/note/mindmap", tags=["笔记"])
async def note_mindmap(request: NoteMindmapRequest):
    """从笔记内容生成思维导图 JSON"""
    try:
        from services.note_service import generate_note_mindmap
        mindmap = await generate_note_mindmap(request.title, request.content)
        return {"success": True, "mindmap": mindmap}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成思维导图失败: {str(e)}")


class NoteExplainRequest(BaseModel):
    selected_text: str = Field(..., description="选中的文本内容")


@app.post("/notes/{user_id}/{note_id}/explain-selection")
async def explain_note_selection(user_id: str, note_id: str, request: NoteExplainRequest):
    """AI 解释笔记中选中的文本（SSE 流式）"""
    from services.note_service import explain_selection_stream
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        explain_selection_stream(request.selected_text),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/notes/{user_id}/{note_id}/life-case")
async def note_life_case(user_id: str, note_id: str, request: NoteExplainRequest):
    """AI 为笔记中选中文本生成生活案例（SSE 流式）"""
    from services.note_service import life_case_stream
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        life_case_stream(request.selected_text),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/notes/{user_id}/{note_id}/export")
async def export_note_file(user_id: str, note_id: str, request: NoteExportRequest):
    """
    导出笔记（word / pdf）
    返回文件下载
    """
    try:
        from services.note_service import get_note, export_to_docx, export_to_pdf, get_export_filename
        from fastapi.responses import Response

        note = get_note(user_id, note_id)
        if note is None:
            raise HTTPException(status_code=404, detail="笔记不存在")

        fmt = request.format.lower()
        if fmt == "docx":
            data = export_to_docx(user_id, note_id)
            if data is None:
                raise HTTPException(status_code=500, detail="Word 导出失败（python-docx 未安装）")
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif fmt == "pdf":
            data = export_to_pdf(user_id, note_id)
            if data is None:
                raise HTTPException(status_code=500, detail="PDF 导出失败（fpdf2 未安装）")
            media_type = "application/pdf"
        else:
            raise HTTPException(status_code=400, detail="不支持的导出格式，仅支持 docx / pdf")

        filename = get_export_filename(note, fmt)
        import urllib.parse
        utf8_encoded = urllib.parse.quote(filename, safe="")
        # filename 可能含中文，HTTP header 只支持 latin-1，所以只用 filename*=UTF-8'' 格式
        safe_filename = filename.encode("ascii", errors="ignore").decode("ascii") or "note"

        return Response(
            content=data,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{utf8_encoded}"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.get("/notebook-page", tags=["页面"])
async def serve_notebook_page():
    """提供学习笔记前端页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'notebook.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="笔记页面未找到")


# ── 知识图谱 ──

@app.get("/knowledge-graph-page", tags=["页面"])
async def serve_knowledge_graph_page():
    """提供知识图谱前端页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'knowledge_graph.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="知识图谱页面未找到")


@app.post("/knowledge-graph/upload/{user_id}", tags=["知识图谱"])
async def upload_document_for_graph(user_id: str, file: UploadFile = File(...)):
    """上传文档，解析内容并生成知识图谱"""
    import tempfile
    from services.knowledge_graph_service import create_graph, SUPPORTED_EXTENSIONS

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )

    # 保存到临时文件
    suffix = ext or ".tmp"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        record = await create_graph(user_id, tmp_path)
        return {"success": True, "data": record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成知识图谱失败: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/knowledge-graph/{user_id}", tags=["知识图谱"])
async def list_knowledge_graphs(user_id: str):
    """获取用户的所有知识图谱列表"""
    from services.knowledge_graph_service import get_graphs
    graphs = get_graphs(user_id)
    return {"success": True, "data": graphs}


@app.get("/knowledge-graph/{user_id}/{graph_id}", tags=["知识图谱"])
async def get_knowledge_graph_detail(user_id: str, graph_id: str):
    """获取单个知识图谱的完整数据"""
    from services.knowledge_graph_service import get_graph_data
    data = get_graph_data(user_id, graph_id)
    if data is None:
        raise HTTPException(status_code=404, detail="知识图谱不存在")
    return {"success": True, "data": data}


@app.delete("/knowledge-graph/{user_id}/{graph_id}", tags=["知识图谱"])
async def delete_knowledge_graph(user_id: str, graph_id: str):
    """删除知识图谱"""
    from services.knowledge_graph_service import delete_graph
    if delete_graph(user_id, graph_id):
        return {"success": True, "message": "已删除"}
    raise HTTPException(status_code=404, detail="知识图谱不存在")


@app.get("/knowledge-graph/{user_id}/{graph_id}/enriched", tags=["知识图谱"])
async def get_enriched_knowledge_graph(user_id: str, graph_id: str):
    """
    获取融合掌握度的增强知识图谱数据
    将图谱节点名称与 KnowledgeMasteryGraph 的掌握度数据对齐
    """
    from services.knowledge_graph_service import get_graph_data
    from memory.knowledge_mastery import KnowledgeMasteryGraph, MASTERY_LABELS

    data = get_graph_data(user_id, graph_id)
    if data is None:
        raise HTTPException(status_code=404, detail="知识图谱不存在")

    # 获取用户掌握度数据
    kg = KnowledgeMasteryGraph()
    mastery_items = kg.get_all_mastery(user_id)
    mastery_map = {item["knowledge_point"]: item for item in mastery_items}

    # 仅对文档图谱已有的节点标注掌握度，不混入掌握度系统的额外知识点
    enriched_nodes = []
    for node in data.get("nodes", []):
        name = node.get("name", "")
        m = mastery_map.get(name, {})
        enriched_nodes.append({
            **node,
            "mastery_level": m.get("mastery_level", 0),
            "mastery_points": m.get("mastery_points", 0.0),
            "mastery_label": MASTERY_LABELS.get(m.get("mastery_level", 0), "未接触"),
        })

    return {
        "success": True,
        "data": {
            **data,
            "nodes": enriched_nodes,
            "edges": data.get("edges", []),
        }
    }


@app.post("/knowledge-graph/{user_id}/merge", tags=["知识图谱"])
async def merge_knowledge_graphs(user_id: str, body: dict):
    """
    合并多个知识图谱为一个总图谱
    请求体: {"graph_ids": ["id1", "id2", ...], "title": "可选标题"}
    """
    from services.knowledge_graph_service import merge_and_save_graphs

    graph_ids = body.get("graph_ids", [])
    if len(graph_ids) < 2:
        raise HTTPException(status_code=400, detail="至少选择2个图谱才能合并")

    title = body.get("title", "")

    try:
        record = await merge_and_save_graphs(user_id, graph_ids, title)
        return {"success": True, "data": record}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"合并失败: {str(e)}")


# ── 知识点智能对比 ──

@app.get("/knowledge-comparison-page", tags=["页面"])
async def serve_knowledge_comparison_page():
    """提供知识点智能对比前端页面"""
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'knowledge_comparison.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="知识点对比页面未找到")


@app.get("/knowledge-comparison/list", tags=["知识点对比"])
async def get_knowledge_comparison_list(
    user_id: str = Query("user_001", description="用户ID，用于合并自定义知识点")
):
    """获取可对比的知识点列表（内置 + 用户自定义）"""
    try:
        from Agent.children_agent.knowledge_comparison_agent import KnowledgeComparisonAgent
        agent = KnowledgeComparisonAgent()
        result = await agent.get_knowledge_list_async(user_id=user_id)
        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取知识点列表失败: {str(e)}")


class KnowledgeCompareRequest(BaseModel):
    knowledge_point_a: str = Field(..., description="知识点A名称")
    knowledge_point_b: str = Field(..., description="知识点B名称")


@app.post("/knowledge-comparison/compare", tags=["知识点对比"])
async def compare_knowledge(request: KnowledgeCompareRequest):
    """
    智能对比两个知识点

    请求体: {"knowledge_point_a": "顺序表", "knowledge_point_b": "单链表"}
    """
    try:
        from Agent.children_agent.knowledge_comparison_agent import KnowledgeComparisonAgent
        agent = KnowledgeComparisonAgent()

        result = await agent.compare_knowledge_points_async(
            knowledge_point_a=request.knowledge_point_a,
            knowledge_point_b=request.knowledge_point_b
        )

        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"知识点对比失败: {str(e)}")


@app.get("/knowledge-comparison/recommendations", tags=["知识点对比"])
async def get_comparison_recommendations(
    knowledge_list: str = Query("", description="知识点列表（逗号分隔）"),
    limit: int = Query(5, description="推荐数量")
):
    """获取推荐的知识点对比组合"""
    try:
        from Agent.children_agent.knowledge_comparison_agent import KnowledgeComparisonAgent
        agent = KnowledgeComparisonAgent()

        kp_list = [k.strip() for k in knowledge_list.split(",") if k.strip()] if knowledge_list else []

        if not kp_list:
            # 返回内置推荐
            builtin = [
                {"knowledge_a": "顺序表", "knowledge_b": "单链表", "reason": "存储结构不同，适用场景有重叠"},
                {"knowledge_a": "栈", "knowledge_b": "队列", "reason": "都是线性结构，但操作受限不同"},
                {"knowledge_a": "二叉搜索树", "knowledge_b": "AVL平衡树", "reason": "BST的优化版本，理解平衡树的必要性"},
                {"knowledge_a": "B树", "knowledge_b": "B+树", "reason": "磁盘索引的两种主要实现"},
                {"knowledge_a": "哈希表", "knowledge_b": "二叉搜索树", "reason": "查找效率对比，空间换时间"},
            ]
            return {"success": True, "data": builtin}

        recommendations = await agent.get_recommended_pairs_async(kp_list, limit)
        return {"success": True, "data": recommendations}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取推荐失败: {str(e)}")


# ── 用户自定义知识点管理 ──

class CustomKnowledgeRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="知识点名称")
    category: str = Field(default="自定义", description="分类")


@app.post("/knowledge-comparison/custom/add", tags=["知识点对比"])
async def add_custom_knowledge(request: CustomKnowledgeRequest):
    """添加用户自定义知识点"""
    try:
        from Agent.children_agent.knowledge_comparison_agent import KnowledgeComparisonAgent
        agent = KnowledgeComparisonAgent()
        result = agent.add_custom_knowledge(request.user_id, request.name, request.category)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "添加失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加失败: {str(e)}")


class CustomKnowledgeRemoveRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="要删除的知识点名称")


@app.post("/knowledge-comparison/custom/remove", tags=["知识点对比"])
async def remove_custom_knowledge(request: CustomKnowledgeRemoveRequest):
    """删除用户自定义知识点"""
    try:
        from Agent.children_agent.knowledge_comparison_agent import KnowledgeComparisonAgent
        agent = KnowledgeComparisonAgent()
        result = agent.remove_custom_knowledge(request.user_id, request.name)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.get("/knowledge-comparison/custom/{user_id}", tags=["知识点对比"])
async def get_custom_knowledge_list(user_id: str):
    """获取用户自定义知识点列表"""
    try:
        from Agent.children_agent.knowledge_comparison_agent import KnowledgeComparisonAgent
        agent = KnowledgeComparisonAgent()
        items = agent.get_custom_knowledge(user_id)
        return {"success": True, "data": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


# ── 算法实验室 ──

@app.get("/algorithm-lab-page", tags=["页面"])
async def serve_algorithm_lab_page():
    """提供算法实验室前端页面"""
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'algorithm_lab.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="算法实验室页面未找到")


@app.get("/algorithm-lab/structures", tags=["算法实验室"])
async def get_algorithm_structures(
    user_id: str = Query("", description="用户ID（用于合并自定义数据结构）")
):
    """获取支持的数据结构列表（内置 + 用户自定义）"""
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()
        structures = agent.get_all_structures(user_id) if user_id else agent.get_supported_structures()
        return {"success": True, "data": structures}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取数据结构列表失败: {str(e)}")


@app.get("/algorithm-lab/operations", tags=["算法实验室"])
async def get_algorithm_operations(
    structure_key: str = Query(..., description="数据结构类型"),
    user_id: str = Query("", description="用户ID（用于查询自定义结构操作）")
):
    """获取指定数据结构支持的操作列表"""
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()
        operations = agent.get_operations_for_structure(structure_key, user_id)
        return {"success": True, "data": operations}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取操作列表失败: {str(e)}")


@app.get("/algorithm-lab/initial-state", tags=["算法实验室"])
async def get_algorithm_initial_state(
    structure_key: str = Query(..., description="数据结构类型"),
    count: int = Query(5, description="初始节点数量"),
    user_id: str = Query("", description="用户ID（用于自定义结构初始状态生成）")
):
    """获取数据结构的初始状态（自定义结构通过LLM生成）"""
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()
        # 自定义数据结构通过LLM生成初始状态
        if structure_key.startswith("custom_") and user_id:
            state = await agent.generate_custom_initial_state_async(structure_key, user_id, count)
        else:
            state = agent.get_initial_state(structure_key, count)
        return {"success": True, "data": state}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取初始状态失败: {str(e)}")


class AlgorithmExecuteRequest(BaseModel):
    structure_key: str = Field(..., description="数据结构类型")
    operation_type: str = Field(..., description="操作类型")
    params: Dict[str, Any] = Field(default={}, description="操作参数")
    current_state: Optional[Dict[str, Any]] = Field(default=None, description="当前状态")


@app.post("/algorithm-lab/execute", tags=["算法实验室"])
async def execute_algorithm_operation(request: AlgorithmExecuteRequest):
    """
    执行数据结构操作，生成伪代码和步骤序列
    
    请求体:
    {
        "structure_key": "singly_linked_list",
        "operation_type": "insert_at_head",
        "params": {"value": 42},
        "current_state": {"nodes": [...], "edges": [...], "pointers": {...}}
    }
    """
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()

        result = await agent.execute_operation_async(
            structure_key=request.structure_key,
            operation_type=request.operation_type,
            params=request.params,
            current_state=request.current_state
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "执行失败"))

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"执行操作失败: {str(e)}")


class AlgorithmCustomExecuteRequest(BaseModel):
    structure_key: str = Field(..., description="数据结构类型（内置key或自定义key）")
    operation_description: str = Field(..., description="用户自定义操作描述（自然语言）")
    params: Dict[str, Any] = Field(default={}, description="操作参数")
    current_state: Optional[Dict[str, Any]] = Field(default=None, description="当前状态")
    user_id: str = Field(default="", description="用户ID（用于查询自定义数据结构）")


@app.post("/algorithm-lab/execute-custom", tags=["算法实验室"])
async def execute_custom_algorithm_operation(request: AlgorithmCustomExecuteRequest):
    """
    根据用户自定义操作描述生成并执行算法步骤
    支持内置数据结构和用户自定义数据结构

    请求体:
    {
        "structure_key": "singly_linked_list",
        "operation_description": "反转链表",
        "params": {},
        "current_state": {"nodes": [...], "edges": [...], "pointers": {...}},
        "user_id": "user_001"
    }
    """
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()

        result = await agent.generate_custom_operation_async(
            structure_key=request.structure_key,
            operation_description=request.operation_description,
            params=request.params,
            current_state=request.current_state,
            user_id=request.user_id
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "执行失败"))

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"执行操作失败: {str(e)}")


# ── 自定义数据结构管理 ──

class CustomStructureRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="数据结构名称")
    description: str = Field(default="", description="数据结构描述（用于LLM生成伪代码）")
    category: str = Field(default="自定义", description="分类")


@app.get("/algorithm-lab/custom-structures/{user_id}", tags=["算法实验室"])
async def get_custom_structures(user_id: str):
    """获取用户自定义数据结构列表"""
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()
        items = agent.get_custom_structures(user_id)
        return {"success": True, "data": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@app.post("/algorithm-lab/custom-structures", tags=["算法实验室"])
async def add_custom_structure(request: CustomStructureRequest):
    """添加用户自定义数据结构"""
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()
        result = agent.add_custom_structure(
            user_id=request.user_id,
            name=request.name,
            description=request.description,
            category=request.category
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "添加失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加失败: {str(e)}")


@app.delete("/algorithm-lab/custom-structures", tags=["算法实验室"])
async def delete_custom_structure(
    user_id: str = Query(..., description="用户ID"),
    key: str = Query(..., description="数据结构key")
):
    """删除用户自定义数据结构"""
    try:
        from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
        agent = AlgorithmLabAgent()
        result = agent.remove_custom_structure(user_id, key)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.post("/notes/upload/{user_id}")
async def upload_note_attachment(user_id: str, file: UploadFile = File(...)):
    """
    上传笔记附件（图片/文档等）
    返回可访问的 URL，前端插入到笔记内容中
    """
    import uuid
    import re as re_mod
    import shutil

    try:
        from services.note_service import _attachment_dir, ALLOWED_ATTACHMENT_EXTENSIONS
    except ImportError:
        from services.note_service import _attachment_dir
        ALLOWED_ATTACHMENT_EXTENSIONS = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
            ".doc", ".docx", ".pdf", ".txt", ".md",
        }

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    # 安全文件名
    name_no_ext = os.path.splitext(file.filename)[0]
    safe_name_part = re_mod.sub(r'[<>:"/\\|?*\s]', '_', name_no_ext)[:80] or 'attachment'
    file_id = uuid.uuid4().hex[:8]
    safe_name = f"{file_id}_{safe_name_part}{ext}"

    attach_dir = _attachment_dir(user_id)
    file_path = os.path.join(attach_dir, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    file_size = len(content)
    url = f"/note-uploads/{user_id}/attachments/{safe_name}"

    # 判断是否图片类型
    is_image = ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}

    return {
        "success": True,
        "url": url,
        "file_name": file.filename,
        "file_size": file_size,
        "content_type": file.content_type,
        "is_image": is_image,
        "markdown_insert": f"![{file.filename}]({url})" if is_image else f"[{file.filename}]({url})",
    }


# ==================== 算法可视化路由 ====================
# ★★★ server-master 可视化功能已用纯 Python 实现，无需启动 Node.js 服务 ★★★
try:
    from services.visualization_proxy import router as viz_router
    app.include_router(viz_router)
    print("✅ 算法可视化路由已注册（/viz, /api/algorithms, /api/visualize, /api/tracers）")
except ImportError as e:
    print(f"⚠️  算法可视化模块未加载: {e}")

# ★★★ B站视频流代理路由（自建播放器）★★★
try:
    from services.bili_stream_service import create_bili_stream_router
    app.include_router(create_bili_stream_router())
    print("✅ B站视频流代理路由已注册（/api/play-info, /api/stream, /api/proxy-image）")
except ImportError as e:
    print(f"⚠️  B站视频流代理模块未加载: {e}")


# ==================== 学习路径规划 API（纯异步，不阻塞事件循环） ====================

@app.post("/study_plan/generate")
async def generate_study_plan_endpoint(request: StudyPlanRequest):
    """
    生成个性化学习路径规划（异步版本，不阻塞其他用户请求）

    示例:
    {
      "user_id": "user_001",
      "user_input": "我想在3个月内学完Python，从零开始",
      "enable_tts": false
    }
    """
    try:
        from Agent.children_agent.study_plan_agent import StudyPlanAgent

        agent = StudyPlanAgent()

        # ★★★ 直接调用纯异步方法，不走 LangGraph 同步工作流 ★★★
        result = await agent.generate_plan_async(
            user_input=request.user_input,
            user_id=request.user_id,
            ignore_weak_points=request.ignore_weak_points,
            focus_weak_points=request.focus_weak_points,
        )

        if result.get("status") == "success":
            plan = result.get("plan", {})
            plan_id = result.get("plan_id") or plan.get("plan_id", "")
            return {
                "success": True,
                "plan_id": plan_id,
                "plan": plan,
                "message": result.get("message", ""),
                "study_plan_summary": {
                    "plan_id": plan_id,
                    "title": plan.get("title", ""),
                    "total_duration": plan.get("total_duration", ""),
                    "phases_count": len(plan.get("phases", [])),
                    "total_estimated_hours": plan.get("total_estimated_hours", ""),
                },
            }
        elif result.get("status") == "weak_points_detected":
            # ★★★ 返回薄弱点信息，前端弹窗让用户选择针对薄弱点还是忽略 ★★★
            return {
                "success": False,
                "weak_points_detected": True,
                "weak_points_info": result.get("weak_points_info", []),
                "message": result.get("message", "检测到薄弱点"),
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "生成失败"),
                "error": result.get("message", "未知错误"),
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"学习路径规划失败: {str(e)}")


# ==================== 多计划管理 API ====================

@app.get("/study_plans/{user_id}")
async def list_study_plans_endpoint(user_id: str):
    """
    获取用户的所有学习计划列表（含元信息，不含完整阶段数据）

    示例: GET /study_plans/user_001
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plans = await planner.list_plans_async(user_id)
        active_id = await planner.get_active_plan_id_async(user_id)
        return {
            "success": True,
            "plans": plans,
            "active_plan_id": active_id,
            "count": len(plans),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取计划列表失败: {str(e)}")


@app.get("/study_plan/{user_id}/version-tree")
async def get_plan_version_tree_endpoint(user_id: str,
                                          plan_id: Optional[str] = Query(None)):
    """
    获取学习计划的版本树

    必须传入 plan_id 以确定版本族。只返回与指定计划共根祖先的所有版本。
    若无 plan_id 或该计划无版本族，has_tree=false，前端不应显示版本树。

    示例: GET /study_plan/user_001/version-tree?plan_id=demo_v1
    """
    try:
        from Agent.children_agent.study_plan_agent import StudyPlanAgent
        agent = StudyPlanAgent()
        result = await agent.get_plan_version_tree_async(user_id, plan_id=plan_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取版本树失败: {str(e)}")


@app.post("/study_plan/{user_id}/switch-version")
async def switch_plan_version_endpoint(user_id: str, request: SwitchPlanRequest):
    """
    切换版本树的"当前执行中"版本（不改变全局活跃计划）

    示例: POST /study_plan/user_001/switch-version
    Body: {"plan_id": "demo_v2"}
    """
    try:
        from Agent.children_agent.study_plan_agent import StudyPlanAgent
        agent = StudyPlanAgent()
        result = await agent.switch_plan_version_async(user_id, request.plan_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换版本失败: {str(e)}")


@app.post("/study_plan/{user_id}/regenerate-phase")
async def regenerate_phase_endpoint(user_id: str, request: RegeneratePhaseRequest):
    """
    重新生成指定阶段的内容

    适用于用户觉得当前阶段内容不合适、难度不当等场景，支持对"进行中"状态的阶段重新生成。
    直接修改原计划，不创建新版本。

    示例: POST /study_plan/user_001/regenerate-phase
    Body: {"phase_index": 1, "plan_id": "demo_v1"}
    """
    try:
        from Agent.children_agent.study_plan_agent import StudyPlanAgent
        agent = StudyPlanAgent()
        result = await agent.regenerate_phase_async(user_id, request.phase_index, request.plan_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新生成阶段失败: {str(e)}")


@app.post("/study_plan/{user_id}/switch-plan")
async def switch_study_plan_endpoint(user_id: str, request: SwitchPlanRequest):
    """
    切换用户的活跃学习计划（全局活跃计划）

    示例: POST /study_plan/user_001/switch-plan
    Body: {"plan_id": "plan_20260601_abc123"}
    """
    try:
        from memory.study_planner import StudyPlanner
        from services.phase_progress_tracker import PhaseProgressTracker

        planner = StudyPlanner()
        success = await planner.set_active_plan_async(user_id, request.plan_id)
        if not success:
            return {"success": False, "message": "切换失败，计划不存在"}

        result = {"success": True, "message": "已切换活跃计划"}

        # ★★★ 如果传了 phase_index，顺带查阶段进度 ★★★
        if request.phase_index is not None:
            tracker = PhaseProgressTracker()
            loop = asyncio.get_event_loop()
            detail = await loop.run_in_executor(
                STUDY_PLAN_EXECUTOR, tracker.get_phase_detail, user_id, request.phase_index
            )
            result["phase_detail"] = detail or None

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换活跃计划失败: {str(e)}")


@app.delete("/study_plan/{user_id}/plan/{plan_id}")
async def delete_study_plan_endpoint(user_id: str, plan_id: str):
    """
    删除用户指定的学习计划

    示例: DELETE /study_plan/user_001/plan/plan_20260601_abc123
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        success = await planner.delete_plan_async(user_id, plan_id)
        if success:
            return {"success": True, "message": "计划已删除"}
        else:
            return {"success": False, "message": "删除失败"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除计划失败: {str(e)}")


# ==================== 续期学习计划 API ====================

@app.get("/study_plan/{user_id}/continuation")
async def check_continuation_proposal(user_id: str):
    """
    检查续期状态：
    - Stage 1: _continuation_pending=true（所有阶段完成，等待用户"接收"）
    - Stage 2: 存在标记 _is_continuation_suggestion=true 的计划（等待用户"接受"或"忽略"）

    示例: GET /study_plan/user_001/continuation
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)

        # ★★★ 追溯母树：版本子树通过 version_info.parent_plan_id 链向上追溯 ★★★
        #    找到母树后判断是否在全局 index 中 → 是则确认是母树，用其目录下的版本族 index.json
        active_plan = plan
        if plan:
            # 1. 追溯 plan_id 到根（母树）
            root_id = planner._find_root_plan_id(user_id, plan.get("plan_id"))
            if not root_id:
                root_id = plan.get("plan_id")

            # 2. 确认母树是否在全局 index 中（确认是母树而非孤立计划）
            all_plans = await planner.list_plans_async(user_id)
            root_in_global = any(p.get("plan_id") == root_id for p in all_plans)

            # 3. 母树在全局中 → 到母树目录下找版本族 index.json
            if root_in_global:
                family_ver_id = planner.get_family_active_version_id(user_id, root_id)
                if family_ver_id and family_ver_id != plan.get("plan_id"):
                    version_plan = await planner.get_plan_async(user_id, family_ver_id)
                    if version_plan:
                        active_plan = version_plan

        # 检查 Stage 1: 续期待接收
        continuation_pending = False
        if active_plan and active_plan.get("_continuation_pending"):
            continuation_pending = True

        # 检查 Stage 2: 是否存在已生成的续期计划
        has_continuation_plan = False
        continuation_plan = None
        all_plans = await planner.list_plans_async(user_id)
        for entry in all_plans:
            pid = entry.get("plan_id")
            if not pid:
                continue
            full_plan = await planner.get_plan_async(user_id, pid)
            if full_plan and full_plan.get("_is_continuation_suggestion"):
                has_continuation_plan = True
                # 只返回概要信息（不含 phases 详细数据可减少传输）
                continuation_plan = {
                    "plan_id": pid,
                    "title": full_plan.get("title", ""),
                    "total_duration": full_plan.get("total_duration", ""),
                    "difficulty": full_plan.get("difficulty", ""),
                    "description": full_plan.get("description", ""),
                    "phases_count": len(full_plan.get("phases", [])),
                    "total_estimated_hours": full_plan.get("total_estimated_hours", ""),
                    "prerequisites": full_plan.get("prerequisites", ""),
                    "phases": [
                        {
                            "name": p.get("name", ""),
                            "estimated_hours": p.get("estimated_hours", "?"),
                            "difficulty": p.get("difficulty", ""),
                            "description": p.get("description", ""),
                            "knowledge_points": p.get("knowledge_points", []),
                        }
                        for p in full_plan.get("phases", [])
                    ],
                }
                break

        return {
            "success": True,
            "continuation_pending": continuation_pending,
            "has_continuation_plan": has_continuation_plan,
            "continuation_plan": continuation_plan,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查续期状态失败: {str(e)}")


@app.post("/study_plan/{user_id}/receive-continuation")
async def receive_continuation_proposal(user_id: str):
    """
    用户点击"接收"续期建议 → 后台生成续期学习计划，保存为独立新计划（标记 _is_continuation_suggestion=true，非活跃）

    示例: POST /study_plan/user_001/receive-continuation
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            raise HTTPException(status_code=404, detail="学习计划不存在")

        # ★★★ 追溯母树：版本子树通过 version_info.parent_plan_id 链向上追溯 ★★★
        #    找到母树后判断是否在全局 index 中 → 是则确认是母树，用其目录下的版本族 index.json
        active_plan = plan
        # 1. 追溯 plan_id 到根（母树）
        root_id = planner._find_root_plan_id(user_id, plan.get("plan_id"))
        if not root_id:
            root_id = plan.get("plan_id")

        # 2. 确认母树是否在全局 index 中（确认是母树而非孤立计划）
        all_plans = await planner.list_plans_async(user_id)
        root_in_global = any(p.get("plan_id") == root_id for p in all_plans)

        # 3. 母树在全局中 → 到母树目录下找版本族 index.json
        if root_in_global:
            family_ver_id = planner.get_family_active_version_id(user_id, root_id)
            if family_ver_id and family_ver_id != plan.get("plan_id"):
                version_plan = await planner.get_plan_async(user_id, family_ver_id)
                if version_plan:
                    active_plan = version_plan

        # 检查是否处于待接收状态
        if not active_plan.get("_continuation_pending"):
            raise HTTPException(status_code=400, detail="当前没有待接收的续期建议")

        # 调用 LLM 生成续期建议
        from Agent.children_agent.study_plan_agent import StudyPlanAgent
        agent = StudyPlanAgent()
        result = await agent.generate_continuation_async(user_id)

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=f"续期计划生成失败: {result.get('message', '')}")

        proposal = result.get("proposal", {})

        # 从 proposal 构建独立新计划
        new_plan = {
            "title": proposal.get("title", "续期学习计划"),
            "total_duration": proposal.get("total_duration", ""),
            "difficulty": proposal.get("difficulty", "中等"),
            "description": proposal.get("description", ""),
            "phases": proposal.get("phases", []),
            "total_estimated_hours": proposal.get("total_estimated_hours", ""),
            "prerequisites": proposal.get("prerequisites", ""),
            "_is_continuation_suggestion": True,  # ★★★ 标记为续期建议计划（非活跃）★★★
            "_continuation_from": plan.get("title", ""),
            "_continuation_from_plan_id": plan.get("plan_id", ""),
        }

        # 初始化阶段状态
        for i, phase in enumerate(new_plan.get("phases", [])):
            phase.setdefault("status", "进行中" if i == 0 else "待完成")
            phase.setdefault("completed_kps", [])
            phase["phase"] = i + 1

        # 保存为新计划（非活跃，因为是待用户接受/忽略的续期建议）
        saved = await planner.save_plan_async(user_id, new_plan, make_active=False)

        if saved:
            # ★★★ 清除原计划的续期待接收标记 ★★★
            plan.pop("_continuation_pending", None)
            plan.pop("_continuation_proposal", None)
            await planner.save_plan_async(user_id, plan, plan_id=plan.get("plan_id"), make_active=False)

            new_plan_id = new_plan.get("plan_id", "")

            return {
                "success": True,
                "plan_id": new_plan_id,
                "message": f"续期计划「{new_plan.get('title', '')}」已生成！",
            }
        else:
            return {"success": False, "message": "续期计划保存失败"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成续期计划失败: {str(e)}")


@app.post("/study_plan/{user_id}/accept-continuation")
async def accept_continuation_proposal(user_id: str):
    """
    用户点击"接受" → 切换到已存在的续期计划（清理 _is_continuation_suggestion 标记）

    示例: POST /study_plan/user_001/accept-continuation
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()

        # 查找标记为 _is_continuation_suggestion 的计划
        all_plans = await planner.list_plans_async(user_id)
        target_plan_id = None
        for entry in all_plans:
            pid = entry.get("plan_id")
            if not pid:
                continue
            full_plan = await planner.get_plan_async(user_id, pid)
            if full_plan and full_plan.get("_is_continuation_suggestion"):
                target_plan_id = pid
                break

        if not target_plan_id:
            raise HTTPException(status_code=400, detail="无续期计划可接受")

        # 清除 _is_continuation_suggestion 标记
        target_plan = await planner.get_plan_async(user_id, target_plan_id)
        target_plan.pop("_is_continuation_suggestion", None)
        await planner.save_plan_async(user_id, target_plan, plan_id=target_plan_id, make_active=True)

        return {
            "success": True,
            "plan_id": target_plan_id,
            "message": f"已切换到续期计划「{target_plan.get('title', '')}」！",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"接受续期计划失败: {str(e)}")


@app.post("/study_plan/{user_id}/reject-continuation")
async def reject_continuation_proposal(user_id: str):
    """
    拒绝续期建议（第一阶段"拒绝"）→ 清除 _continuation_pending 标记，不生成任何计划

    示例: POST /study_plan/user_001/reject-continuation
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if plan:
            plan.pop("_continuation_pending", None)
            plan.pop("_continuation_proposal", None)
            await planner.save_plan_async(user_id, plan, plan_id=plan.get("plan_id"), make_active=False)
        return {"success": True, "message": "已拒绝续期建议"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拒绝续期建议失败: {str(e)}")


@app.post("/study_plan/{user_id}/ignore-continuation")
async def ignore_continuation_proposal(user_id: str):
    """
    忽略续期计划（第二阶段"忽略"）→ 清除 _is_continuation_suggestion 标记
    计划保留在列表中，用户后续可手动切换

    示例: POST /study_plan/user_001/ignore-continuation
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()

        # 查找标记为 _is_continuation_suggestion 的计划
        all_plans = await planner.list_plans_async(user_id)
        for entry in all_plans:
            pid = entry.get("plan_id")
            if not pid:
                continue
            full_plan = await planner.get_plan_async(user_id, pid)
            if full_plan and full_plan.get("_is_continuation_suggestion"):
                # 清除标记，保留计划
                full_plan.pop("_is_continuation_suggestion", None)
                await planner.save_plan_async(user_id, full_plan, plan_id=pid, make_active=False)
                break

        return {"success": True, "message": "已忽略续期计划，计划保留在列表中"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"忽略续期计划失败: {str(e)}")


@app.get("/study_plan/{user_id}")
async def get_study_plan_endpoint(user_id: str, plan_id: str = ""):
    """
    获取用户的学习计划（异步版本）

    示例: GET /study_plan/user_001           ← 获取活跃计划
          GET /study_plan/user_001?plan_id=plan_20260601_abc123  ← 获取指定计划
    """
    try:
        from memory.study_planner import StudyPlanner

        planner = StudyPlanner()

        # ★★★ 支持 plan_id 查询参数，获取指定计划 ★★★
        plan_id_param = plan_id if plan_id else None
        plan = await planner.get_plan_async(user_id, plan_id_param)

        if plan:
            plan_id_val = plan.get("plan_id", "")

            # ★★★ 注入考试状态到各阶段（从每阶段的 _notification 中读取）★★★
            phases = plan.get("phases", [])
            for idx, phase in enumerate(phases):
                notif = phase.get("_notification", {})
                if notif.get("phase_index") == idx:
                    if notif.get("exam_completed"):
                        phases[idx]["_exam_completed_info"] = {
                            "score": notif.get("exam_score"),
                            "total": notif.get("exam_data", {}).get("total_score", 0),
                            "results": notif.get("exam_results", []),
                            "exam_data": notif.get("exam_data"),
                            "phase_name": phase.get("name", f"阶段{idx+1}"),
                        }
                    else:
                        # 未完成考试（含跳过）→ 显示补考按钮
                        phases[idx]["_exam_pending"] = True

            # ★★★ 检测重规划是否正在后台执行 ★★★
            if plan.get("_regenerating_phases"):
                pass  # 标记已存在，保留前端可见

            return {
                "success": True,
                "plan_id": plan_id_val,
                "plan": plan,
            }
        else:
            return {
                "success": False,
                "message": "该用户尚无学习计划",
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取学习计划失败: {str(e)}")


@app.get("/study_plan/{user_id}/summary")
async def get_study_plan_summary_endpoint(user_id: str, plan_id: str = ""):
    """
    获取用户学习计划摘要（进度等）

    示例: GET /study_plan/user_001/summary
          GET /study_plan/user_001/summary?plan_id=plan_20260601_abc123
    """
    try:
        from memory.study_planner import StudyPlanner

        planner = StudyPlanner()
        plan_id_param = plan_id if plan_id else None
        summary = await planner.get_plan_summary_async(user_id, plan_id_param)

        if summary:
            return {
                "success": True,
                "summary": summary,
            }
        else:
            return {
                "success": False,
                "message": "该用户尚无学习计划",
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取计划摘要失败: {str(e)}")


# ==================== 学习计划阶段资源 API ====================

@app.get("/study_plan/{user_id}/phases")
async def get_plan_phases(user_id: str):
    """获取用户学习计划的所有阶段（含考试状态）"""
    try:
        from services.phase_bridge import PhaseResourceBridge
        from memory.study_planner import StudyPlanner
        bridge = PhaseResourceBridge()
        loop = asyncio.get_event_loop()
        phases = await loop.run_in_executor(STUDY_PLAN_EXECUTOR, bridge.get_plan_phases, user_id)
        # 附加考试状态
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if plan:
            # ★★★ 从每阶段的 _notification 注入考试状态 ★★★
            for idx, phase in enumerate(phases):
                notif = phase.get("_notification", {})
                if notif.get("phase_index") == idx:
                    if notif.get("exam_completed"):
                        phases[idx]["_exam_completed_info"] = {
                            "score": notif.get("exam_score"),
                            "total": notif.get("exam_data", {}).get("total_score", 0),
                            "results": notif.get("exam_results", []),
                            "exam_data": notif.get("exam_data"),
                            "phase_name": phase.get("name", f"阶段{idx+1}"),
                        }
                    else:
                        # 未完成考试（含跳过）→ 显示补考按钮
                        phases[idx]["_exam_pending"] = True
        return {"success": True, "phases": phases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取阶段失败: {str(e)}")


@app.get("/study_plan/{user_id}/phase/{phase_index}/status")
async def get_phase_resource_status(user_id: str, phase_index: int):
    """获取某阶段资源缓存状态（不触发生成）"""
    try:
        from services.phase_bridge import PhaseResourceBridge
        bridge = PhaseResourceBridge()
        loop = asyncio.get_event_loop()
        status = await loop.run_in_executor(None, bridge.get_phase_resource_status, user_id, phase_index)
        return {"success": True, **status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@app.post("/study_plan/{user_id}/phase/{phase_index}/generate/{resource_type}")
async def generate_phase_resource(
    user_id: str, phase_index: int, resource_type: str,
    knowledge_point: str = "", entry: str = "quick",
    cached_only: str = "false"
):
    """
    为某阶段生成指定知识点+资源类型
    已有缓存直接返回，未缓存则调用对应Agent生成

    参数:
      entry: "plan" → 管道模式（一键生成全套资源）
             "quick" → 独立模式（只生成指定类型）
      cached_only: "true" → 仅查缓存，不生成任何新资源

    示例: POST /study_plan/user_001/phase/0/generate/practice?knowledge_point=循环结构&entry=plan&cached_only=true
    """
    try:
        from services.collaboration_orchestrator import CollaborationOrchestrator
        orchestrator = CollaborationOrchestrator()

        if not knowledge_point:
            loop = asyncio.get_event_loop()
            phases = await loop.run_in_executor(None, orchestrator._bridge.get_plan_phases, user_id)
            if phases and phase_index < len(phases):
                kps = phases[phase_index].get("knowledge_points", [])
                if len(kps) == 1:
                    knowledge_point = kps[0]
                elif len(kps) > 1:
                    return {
                        "success": False,
                        "error": "need_knowledge_point",
                        "message": "该阶段包含多个知识点，请指定 knowledge_point 参数",
                        "knowledge_points": kps
                    }

        if not knowledge_point:
            raise HTTPException(status_code=400, detail="请指定 knowledge_point")

        result = await orchestrator.generate_resource(
            user_id=user_id,
            phase_index=phase_index,
            resource_type=resource_type,
            knowledge_point=knowledge_point,
            entry=entry,
            cached_only=(cached_only.lower() == "true"),
        )
        return {"success": result.get("success", True), **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成资源失败: {str(e)}")


@app.post("/study_plan/{user_id}/phase/{phase_index}/generate-all")
async def generate_all_phase_resources(user_id: str, phase_index: int):
    """
    生成某阶段所有未缓存的资源（逐个按序生成）
    已缓存的不重复生成
    """
    try:
        from services.phase_bridge import PhaseResourceBridge
        bridge = PhaseResourceBridge()
        result = await bridge.generate_all_pending(user_id, phase_index)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成全部资源失败: {str(e)}")


@app.get("/study_plan/{user_id}/pipeline-status")
async def get_pipeline_status(user_id: str):
    """
    获取用户的管道状态摘要（有无规划、当前阶段、模式等）

    示例: GET /study_plan/user_001/pipeline-status
    """
    try:
        from services.collaboration_orchestrator import CollaborationOrchestrator
        orchestrator = CollaborationOrchestrator()
        loop = asyncio.get_event_loop()
        status = await loop.run_in_executor(STUDY_PLAN_EXECUTOR, orchestrator.get_pipeline_status, user_id)
        return {"success": True, **status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取管道状态失败: {str(e)}")


# ==================== 阶段进度追踪 API ====================

@app.get("/study_plan/{user_id}/progress")
async def get_phase_progress(user_id: str):
    """
    获取用户所有阶段的完成度详情

    示例: GET /study_plan/user_001/progress
    """
    try:
        from services.phase_progress_tracker import PhaseProgressTracker
        tracker = PhaseProgressTracker()
        loop = asyncio.get_event_loop()
        progress = await loop.run_in_executor(STUDY_PLAN_EXECUTOR, tracker.get_all_phases_progress, user_id)
        return {"success": True, "user_id": user_id, "phases": progress}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取阶段进度失败: {str(e)}")


@app.get("/study_plan/{user_id}/phase/{phase_index}/progress")
async def get_phase_detail_progress(user_id: str, phase_index: int):
    """
    获取某个阶段的详细完成度

    示例: GET /study_plan/user_001/phase/0/progress
    """
    try:
        from services.phase_progress_tracker import PhaseProgressTracker
        tracker = PhaseProgressTracker()
        loop = asyncio.get_event_loop()
        detail = await loop.run_in_executor(None, tracker.get_phase_detail, user_id, phase_index)
        if not detail:
            raise HTTPException(status_code=404, detail="阶段不存在")
        return {"success": True, **detail}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取阶段详情失败: {str(e)}")


@app.get("/study_plan/{user_id}/notification")
async def check_phase_notification(user_id: str):
    """
    检查是否有阶段完成通知（前端弹窗用）

    示例: GET /study_plan/user_001/notification
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            return {"success": True, "notification": None}

        notification = None
        phases = plan.get("phases", [])
        for phase in phases:
            notif = phase.get("_notification", {})
            if not notif or notif.get("acknowledged") is True:
                continue
            # ★★★ 考试完成且阶段评估已就绪 → 显示评估弹窗 ★★★
            if notif.get("exam_completed"):
                phase_assessment = phases[notif["phase_index"]].get("phase_assessment") if notif["phase_index"] < len(phases) else None
                if phase_assessment:
                    notification = notif
                    break
            # ★★★ 未考试/未跳过 → 显示考试弹窗 ★★★
            if not notif.get("exam_completed") and not notif.get("exam_skipped"):
                notification = notif
                break

        if notification:
            phase_index = notification["phase_index"]
            phase_assessment = None
            if phase_index < len(phases):
                phase_assessment = phases[phase_index].get("phase_assessment")
            
            # 提取考试相关信息
            exam_ready = notification.get("exam_ready", False)
            exam_data = notification.get("exam_data", {})
            exam_completed = notification.get("exam_completed", False)
            exam_score = notification.get("exam_score", None)
            exam_skipped = notification.get("exam_skipped", False)
            
            return {
                "success": True,
                "notification": {
                    "phase_index": phase_index,
                    "phase_name": notification["phase_name"],
                    "triggered_at": notification["triggered_at"],
                    "assessment_ready": phase_assessment is not None,
                    "assessment": phase_assessment,
                    # 考试相关信息
                    "exam_ready": exam_ready,
                    "exam_data": exam_data,
                    "exam_completed": exam_completed,
                    "exam_score": exam_score,
                    "exam_skipped": exam_skipped,
                }
            }
        return {"success": True, "notification": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查通知失败: {str(e)}")


@app.post("/study_plan/{user_id}/notification/reset-exam")
async def reset_exam_notification(user_id: str, request: dict = None):
    """
    取消考试后重置阶段状态：将阶段状态恢复为"进行中"，清除 _notification 中的考试标记，
    使用户可以重新参加考试，后续阶段保持锁定。
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            return {"success": True}
        phase_index = (request or {}).get("phase_index", 0)
        phases = plan.get("phases", [])
        if 0 <= phase_index < len(phases):
            phase = phases[phase_index]
            phase["status"] = "进行中"
            notif = phase.get("_notification", {})
            if notif:
                notif["exam_skipped"] = False
                notif["exam_completed"] = False
                notif["exam_score"] = None
                notif["exam_results"] = None
                notif["acknowledged"] = False
                # 保留 exam_ready / exam_data，下次直接复用，不重新生成
            plan["phases"] = phases
            await planner.save_plan_async(user_id, plan)
            print(f"  🔄 [考试重置] 阶段{phase_index+1}已重置为进行中")
        return {"success": True}
    except Exception as e:
        print(f"  ⚠️ [考试重置] 失败: {e}")
        return {"success": True}


@app.post("/study_plan/{user_id}/notification/ack")
async def acknowledge_phase_notification(user_id: str, phase_index: int = Query(None, description="要确认的阶段索引，不传则自动找到第一个未确认的")):
    """
    确认阶段完成通知（关闭弹窗后调用）

    示例: POST /study_plan/user_001/notification/ack
          POST /study_plan/user_001/notification/ack?phase_index=0
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            return {"success": True}
        
        phases = plan.get("phases", [])
        if phase_index is not None:
            # 确认指定阶段的通知
            if 0 <= phase_index < len(phases) and "_notification" in phases[phase_index]:
                phases[phase_index]["_notification"]["acknowledged"] = True
                plan["phases"] = phases
                await planner.save_plan_async(user_id, plan)
        else:
            # 自动确认第一个未确认的通知（兼容旧调用）
            for phase in phases:
                notif = phase.get("_notification", {})
                if notif and notif.get("acknowledged") is False:
                    notif["acknowledged"] = True
                    plan["phases"] = phases
                    await planner.save_plan_async(user_id, plan)
                    break
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认通知失败: {str(e)}")


# ==================== 阶段心跳 API ====================

@app.post("/study_plan/{user_id}/phase/{phase_index}/heartbeat")
async def phase_heartbeat(user_id: str, phase_index: int):
    """
    前端心跳上报，每30秒调用一次，累加用户活跃时间

    示例: POST /study_plan/user_001/phase/0/heartbeat
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            return {"success": False, "error": "无学习计划"}

        phases = plan.get("phases", [])
        if phase_index < 0 or phase_index >= len(phases):
            return {"success": False, "error": "阶段不存在"}

        phase = phases[phase_index]
        # 只有进行中的阶段才接受心跳
        if phase.get("status") not in ("进行中", "active"):
            return {"success": False, "error": "阶段不是进行中状态，不接受心跳"}
        current = phase.get("_total_active_seconds", 0)
        phase["_total_active_seconds"] = current + 30
        await planner.save_plan_async(user_id, plan)

        return {"success": True, "total_seconds": phase["_total_active_seconds"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"心跳上报失败: {str(e)}")


# ==================== 阶段考试 API ====================

class ExamChoiceRequest(BaseModel):
    """阶段考试选择请求模型"""
    take_exam: bool = Field(..., description="是否参加考试")


@app.post("/study_plan/{user_id}/phase/{phase_index}/exam/choice")
async def handle_exam_choice(user_id: str, phase_index: int, request: ExamChoiceRequest):
    """
    用户选择是否参加阶段考试

    示例: POST /study_plan/user_001/phase/0/exam/choice
    Body: {"take_exam": true}
    """
    try:
        from services.phase_progress_tracker import PhaseProgressTracker
        tracker = PhaseProgressTracker()
        result = await tracker.handle_exam_choice(user_id, phase_index, request.take_exam)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理考试选择失败: {str(e)}")


@app.get("/study_plan/{user_id}/phase/{phase_index}/exam")
async def get_phase_exam(user_id: str, phase_index: int):
    """
    获取阶段考试题目数据

    示例: GET /study_plan/user_001/phase/0/exam
    """
    try:
        from services.phase_progress_tracker import PhaseProgressTracker
        tracker = PhaseProgressTracker()
        loop = asyncio.get_event_loop()
        exam_data = await loop.run_in_executor(STUDY_PLAN_EXECUTOR, tracker.get_exam_data, user_id, phase_index)
        if exam_data:
            return {"success": True, "exam_data": exam_data}
        return {"success": False, "message": "考试数据不存在或尚未生成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取考试数据失败: {str(e)}")


class ExamSubmissionRequest(BaseModel):
    """阶段考试答案提交请求模型"""
    answers: Dict[str, Any] = Field(..., description="用户答案，格式: {\"programming_0\": \"代码\", \"theory_0\": \"A\"}")


@app.post("/study_plan/{user_id}/phase/{phase_index}/exam/submit")
async def submit_exam_answers(user_id: str, phase_index: int, request: ExamSubmissionRequest):
    """
    提交阶段考试答案

    示例: POST /study_plan/user_001/phase/0/exam/submit
    Body: {"answers": {"programming_0": "print('Hello')", "theory_0": "A", "theory_1": "AB"}}
    """
    try:
        from services.phase_progress_tracker import PhaseProgressTracker
        tracker = PhaseProgressTracker()
        result = await tracker.submit_exam_answers(user_id, phase_index, request.answers)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交考试答案失败: {str(e)}")


@app.get("/assessment/phase/{user_id}/{phase_index}")
async def get_phase_assessment(user_id: str, phase_index: int):
    """
    获取阶段性评估报告

    示例: GET /assessment/phase/user_001/0
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            raise HTTPException(status_code=404, detail="学习计划不存在")
        phases = plan.get("phases", [])
        if phase_index >= len(phases):
            raise HTTPException(status_code=404, detail="阶段不存在")
        assessment = phases[phase_index].get("phase_assessment")
        if not assessment:
            return {"success": False, "message": "该阶段暂无评估报告"}
        return {"success": True, "assessment": assessment}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取阶段性评估失败: {str(e)}")


# ==================== 社区模块 Request Models ====================

class CommunityPostRequest(BaseModel):
    """发帖请求模型"""
    user_id: str = Field(..., description="用户ID")
    title: str = Field(..., description="帖子标题")
    content: str = Field(..., description="帖子内容")
    tags: List[str] = Field(default=[], description="标签列表")
    zone: Optional[str] = Field(default=None, description="社区区域（可选，默认自动判断）")


class CommunityPostDraftRequest(BaseModel):
    """发帖助手-生成草稿请求模型"""
    user_id: str = Field(..., description="用户ID")
    resource_type: str = Field(..., description="资源类型（practice/video/doc/mindmap/study_plan等）")
    resource_title: str = Field(..., description="资源标题")
    resource_content: str = Field(..., description="资源内容")


class CommunityPublishRequest(BaseModel):
    """发帖助手-发布帖子请求模型"""
    user_id: str = Field(..., description="用户ID")
    resource_type: str = Field(..., description="资源类型")
    resource_title: str = Field(..., description="资源标题")
    resource_content: str = Field(..., description="资源内容")
    title: Optional[str] = Field(default=None, description="自定义标题（可选）")
    content: Optional[str] = Field(default=None, description="自定义内容（可选）")
    tags: Optional[List[str]] = Field(default=None, description="自定义标签（可选）")
    zone: Optional[str] = Field(default=None, description="自定义区域（可选）")


class CommunityUpdateRequest(BaseModel):
    """编辑帖子请求模型"""
    user_id: str = Field(..., description="用户ID（需与作者一致）")
    title: Optional[str] = Field(default=None, description="新标题（可选）")
    content: Optional[str] = Field(default=None, description="新内容（可选）")
    tags: Optional[List[str]] = Field(default=None, description="新标签列表（可选）")
    zone: Optional[str] = Field(default=None, description="新区域（可选）")


class CommunityReplyRequest(BaseModel):
    """回复请求模型"""
    user_id: str = Field(..., description="用户ID")
    post_id: str = Field(..., description="目标帖子ID")
    content: str = Field(..., description="回复内容")
    parent_reply_id: Optional[str] = Field(default=None, description="父回复ID（嵌套回复）")


# ★★★ 社区特征更新后台任务（不阻塞用户响应）★★★
async def _background_community_feature_update(user_id: str, action_type: str, action_data: Dict[str, Any]):
    """后台执行社区特征更新，不阻塞 API 响应"""
    try:
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        updater = DynamicFeatureUpdater()
        features = await updater.get_latest_features_async(user_id)
        if not features:
            return

        performance_data = {"action_type": action_type, **action_data}
        await updater.update_features_async(
            current_features=features,
            task_type="community_activity",
            task_content=f"社区{action_type}",
            performance_data=performance_data,
            completion_quality="medium",
            user_id=user_id
        )
        print(f"   📊 [后台] 社区特征更新完成: {action_type}")
    except Exception as e:
        print(f"   ⚠️ [后台] 社区特征更新失败: {e}")


# ==================== 社区 API ====================

@app.post("/community/upload")
async def community_upload(file: UploadFile = File(...)):
    """
    社区文件上传
    支持图片(jpg/png/gif/webp)、Word文档(doc/docx)、PDF等
    返回可访问的URL，前端插入到内容中
    """
    import uuid
    import re
    import shutil

    # 允许的文件类型
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp",
                         ".doc", ".docx", ".pdf", ".xls", ".xlsx",
                         ".ppt", ".pptx", ".txt", ".zip", ".rar"}

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    # 清除原始文件名中的危险字符，保留可读名称
    name_no_ext = os.path.splitext(file.filename)[0]
    safe_name_part = re.sub(r'[<>:"/\\|?*\s]', '_', name_no_ext)[:80] or 'file'
    file_id = uuid.uuid4().hex[:8]
    safe_name = f"{file_id}_{safe_name_part}{ext}"

    # ★★★ 先存到 _temp 临时目录 ★★★
    temp_dir = os.path.join(COMMUNITY_UPLOAD_DIR, "_temp")
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, safe_name)

    # 写入文件
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    file_size = len(content)
    url = f"/community/uploads/_temp/{safe_name}"

    return {
        "success": True,
        "url": url,
        "file_name": file.filename,
        "file_size": file_size,
        "content_type": file.content_type,
    }


# ★★★ 工具函数：将 content 中的 _temp 文件迁移到所属者目录 ★★★
def _migrate_uploaded_files(content: str, owner_id: str) -> str:
    """扫描 content 中的 /community/uploads/_temp/ 链接，
    将对应文件迁移到 /community/uploads/{owner_id}/ 目录，
    并返回替换 URL 后的新 content。
    """
    import re
    import shutil

    if "_temp" not in content:
        return content

    # 找到所有 /community/uploads/_temp/xxx 的 URL
    pattern = r'/community/uploads/_temp/([^\s<>&"]+)'

    def _do_move(match):
        fname = match.group(1)
        src = os.path.join(COMMUNITY_UPLOAD_DIR, "_temp", fname)
        if not os.path.exists(src):
            return match.group(0)  # 文件不存在，保持原样
        # 目标目录
        dst_dir = os.path.join(COMMUNITY_UPLOAD_DIR, owner_id)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, fname)
        try:
            shutil.move(src, dst)
        except Exception:
            return match.group(0)
        return f"/community/uploads/{owner_id}/{fname}"

    return re.sub(pattern, _do_move, content)


@app.post("/community/post")
async def create_community_post(request: CommunityPostRequest):
    """
    发布学习困惑/分享

    示例:
    {
      "user_id": "user_001",
      "title": "递归函数怎么理解？",
      "content": "学了半天递归还是不太明白，有没有好的理解方式？",
      "tags": ["递归", "函数", "算法"]
    }
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _create():
            service = CommunityService()
            post = service.create_post(
                user_id=request.user_id,
                title=request.title,
                content=request.content,
                tags=request.tags,
                zone=request.zone,
            )
            # ★★★ 迁移帖子中的临时文件到 {post_id} 目录 ★★★
            owner_id = post["post_id"]
            new_content = _migrate_uploaded_files(post["content"], owner_id)
            if new_content != post["content"]:
                service.update_post(
                    post_id=post["post_id"],
                    user_id=request.user_id,
                    content=new_content,
                )
                post["content"] = new_content
            return post

        post = await run_in_threadpool(_create)

        # ★★★ 发帖成功 → 后台异步更新特征（不阻塞用户响应）★★★
        asyncio.create_task(_background_community_feature_update(
            request.user_id, "create_post", {
                "title_preview": (request.title or "")[:50],
                "has_tags": bool(request.tags),
                "zone": request.zone or "learning",
                "content_preview": (request.content or "")[:100],
            }
        ))

        return {"success": True, "post": post}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发帖失败: {str(e)}")


@app.get("/community/zones")
async def get_community_zones():
    """
    获取社区区域列表

    返回所有可用的社区区域及其信息
    """
    try:
        from Agent.community_service import COMMUNITY_ZONES
        return {
            "success": True,
            "zones": COMMUNITY_ZONES,
            "default_zone": "learning"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取社区区域失败: {str(e)}")


@app.post("/community/post/preview")
async def preview_community_post(request: CommunityPostDraftRequest):
    """
    发帖助手-预览帖子草稿

    根据资源内容生成帖子草稿，供用户查看和修改

    示例:
    {
      "user_id": "user_001",
      "resource_type": "practice",
      "resource_title": "Python循环练习题",
      "resource_content": "请编写一个程序，输出1到100之间所有偶数的和..."
    }
    """
    try:
        from Agent.children_agent.community_post_agent import CommunityPostAgent
        from fastapi.concurrency import run_in_threadpool

        def _preview():
            agent = CommunityPostAgent()
            return agent.preview_post(
                user_id=request.user_id,
                resource_type=request.resource_type,
                resource_title=request.resource_title,
                resource_content=request.resource_content,
            )

        result = await run_in_threadpool(_preview)
        return {"success": True, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成帖子草稿失败: {str(e)}")


@app.post("/community/post/publish")
async def publish_community_post(request: CommunityPublishRequest):
    """
    发帖助手-发布帖子

    将用户修改后的帖子内容发布到社区

    示例:
    {
      "user_id": "user_001",
      "resource_type": "practice",
      "resource_title": "Python循环练习题",
      "resource_content": "请编写一个程序，输出1到100之间所有偶数的和...",
      "title": "【已修改】Python循环练习题求解",
      "content": "我在做这道题时遇到了困难...",
      "tags": ["Python", "循环", "求助"],
      "zone": "learning"
    }
    """
    try:
        from Agent.children_agent.community_post_agent import CommunityPostAgent
        from fastapi.concurrency import run_in_threadpool

        def _publish():
            agent = CommunityPostAgent()
            return agent.publish_post(
                user_id=request.user_id,
                resource_type=request.resource_type,
                resource_title=request.resource_title,
                resource_content=request.resource_content,
                title=request.title,
                content=request.content,
                tags=request.tags,
                zone=request.zone,
            )

        result = await run_in_threadpool(_publish)
        if result.get("success"):
            # ★★★ 发帖成功 → 后台异步更新特征 ★★★
            asyncio.create_task(_background_community_feature_update(
                request.user_id, "create_post", {
                    "title_preview": (request.title or "")[:50],
                    "has_tags": bool(request.tags),
                    "zone": request.zone or "learning",
                    "content_preview": (request.content or "")[:100],
                }
            ))
            return {"success": True, **result}
        else:
            error_msg = result.get("error") or result.get("message", "发布失败")
            raise HTTPException(status_code=400, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发布帖子失败: {str(e)}")


@app.get("/community/posts")
async def list_community_posts(
    page: int = 1,
    page_size: int = 20,
    tag: Optional[str] = None,
    user_id: Optional[str] = None,
    zone: Optional[str] = None,
):
    """
    获取社区帖子列表（分页，按时间倒序）

    示例: GET /community/posts?page=1&page_size=10&tag=递归
          GET /community/posts?page=1&page_size=10&zone=learning
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _list():
            service = CommunityService()
            return service.list_posts(
                page=page, page_size=page_size,
                tag=tag, user_id=user_id, zone=zone,
            )

        result = await run_in_threadpool(_list)
        return {"success": True, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取帖子列表失败: {str(e)}")


@app.get("/community/post/{post_id}")
async def get_community_post(post_id: str):
    """
    获取帖子详情（含回复）

    示例: GET /community/post/post_abc123
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _get():
            service = CommunityService()
            post = service.get_post(post_id)
            if not post:
                return None, []
            replies = service.get_replies(post_id)
            return post, replies

        post, replies = await run_in_threadpool(_get)

        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")

        return {
            "success": True,
            "post": post,
            "replies": replies,
            "reply_count": len(replies),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取帖子详情失败: {str(e)}")


@app.post("/community/reply")
async def create_community_reply(request: CommunityReplyRequest):
    """
    回复帖子（支持嵌套回复）

    示例:
    {
      "user_id": "user_002",
      "post_id": "post_abc123",
      "content": "可以试试画递归树来理解",
      "parent_reply_id": null
    }
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _reply():
            service = CommunityService()
            return service.create_reply(
                post_id=request.post_id,
                user_id=request.user_id,
                content=request.content,
                parent_reply_id=request.parent_reply_id,
            )

        reply = await run_in_threadpool(_reply)

        if not reply:
            raise HTTPException(status_code=404, detail="帖子不存在")

        # ★★★ 迁移回复中的临时文件到所属帖子的目录 ★★★
        owner_id = request.post_id
        new_content = _migrate_uploaded_files(reply["content"], owner_id)
        if new_content != reply["content"]:
            from Agent.community_service import _get_conn
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE community_replies SET content = ? WHERE reply_id = ?",
                    (new_content, reply["reply_id"])
                )
                conn.commit()
            reply["content"] = new_content

        # ★★★ 回复成功 → 后台异步更新特征（不阻塞用户响应）★★★
        asyncio.create_task(_background_community_feature_update(
            request.user_id, "create_reply", {
                "post_id": request.post_id,
                "content_preview": (request.content or "")[:100],
                "is_nested_reply": request.parent_reply_id is not None,
            }
        ))

        return {"success": True, "reply": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回复失败: {str(e)}")


@app.put("/community/post/{post_id}")
async def update_community_post(post_id: str, request: CommunityUpdateRequest):
    """
    编辑帖子（仅作者可编辑）

    示例: PUT /community/post/post_abc123
    {
      "user_id": "user_001",
      "title": "新标题",
      "content": "新内容",
      "tags": ["新标签"],
      "zone": "learning"
    }
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _update():
            service = CommunityService()
            result = service.update_post(
                post_id=post_id,
                user_id=request.user_id,
                title=request.title,
                content=request.content,
                tags=request.tags,
                zone=request.zone,
            )
            # ★★★ 迁移编辑后的文件到 {post_id} 目录 ★★★
            if result and request.content:
                owner_id = post_id
                new_content = _migrate_uploaded_files(request.content, owner_id)
                if new_content != request.content:
                    result = service.update_post(
                        post_id=post_id,
                        user_id=request.user_id,
                        content=new_content,
                    )
            return result

        result = await run_in_threadpool(_update)

        if not result:
            raise HTTPException(status_code=403, detail="无权编辑或帖子不存在")

        return {"success": True, "post": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"编辑失败: {str(e)}")


@app.delete("/community/post/{post_id}/{user_id}")
async def delete_community_post(post_id: str, user_id: str):
    """
    删除帖子（仅作者可删）

    示例: DELETE /community/post/post_abc123/user_001
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _delete():
            service = CommunityService()
            return service.delete_post(post_id, user_id)

        success = await run_in_threadpool(_delete)

        if not success:
            raise HTTPException(status_code=403, detail="无权删除或帖子不存在")

        return {"success": True, "message": "帖子已删除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.delete("/community/reply/{reply_id}/{user_id}")
async def delete_community_reply(reply_id: str, user_id: str):
    """
    删除回复（仅作者可删）

    示例: DELETE /community/reply/reply_abc123/user_002
    """
    try:
        from Agent.community_service import CommunityService
        from fastapi.concurrency import run_in_threadpool

        def _delete():
            service = CommunityService()
            return service.delete_reply(reply_id, user_id)

        success = await run_in_threadpool(_delete)

        if not success:
            raise HTTPException(status_code=403, detail="无权删除或回复不存在")

        return {"success": True, "message": "回复已删除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.get("/wrong-answers-page", tags=["页面"])
async def serve_wrong_answers_page():
    """提供错题本前端页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'wrong_answers.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="错题本页面未找到")


@app.get("/assessment-page", tags=["页面"])
async def serve_assessment_page():
    """提供学习效果评估页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'assessment.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="评估页面未找到")


@app.get("/study-plan-page", tags=["页面"])
async def serve_study_plan_page():
    """提供学习计划前端页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'study_plan.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="计划页面未找到")


@app.get("/route-market-page", tags=["页面"])
async def serve_route_market_page():
    """提供学习路线市场前端页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'route_market.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="路线市场页面未找到")


@app.get("/community-page", tags=["页面"])
async def serve_community_page():
    """提供学习社区页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'community.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="社区页面未找到")


@app.get("/unified-page", tags=["页面"])
async def serve_unified_page():
    """提供统一前端页面（智能助手+社区+错题本）"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'unified.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="统一页面未找到")


@app.get("/companion-page", tags=["页面"])
async def serve_companion_page():
    """提供学伴匹配页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'companion.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="学伴页面未找到")





# ==================== 学伴搜索与匹配 API ====================

@app.get("/companion/match/{user_id}")
async def find_companions(user_id: str, limit: int = 10):
    """
    根据用户特征自动搜索匹配的学伴（无需手动选择维度）

    示例: GET /companion/match/user_001?limit=10
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.find_matches(user_id, limit=limit)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索学伴失败: {str(e)}")


@app.post("/companion/invite")
async def invite_companion(request: CompanionInviteRequest):
    """
    发送学伴邀请

    示例:
    {"from_user": "user_001", "to_user": "user_002"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.invite(request.from_user, request.to_user)
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送邀请失败: {str(e)}")


@app.post("/companion/respond")
async def respond_companion(request: CompanionRespondRequest):
    """
    接受/拒绝学伴邀请

    示例:
    {"user_id": "user_002", "companion_id": 1, "accept": true}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.respond(request.user_id, request.companion_id, request.accept)
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@app.get("/companion/list/{user_id}")
async def list_companions(user_id: str):
    """
    获取用户的所有学伴

    示例: GET /companion/list/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.list_companions(user_id)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学伴列表失败: {str(e)}")


@app.get("/companion/pending/{user_id}")
async def get_pending_invites(user_id: str):
    """
    获取待处理的学伴邀请

    示例: GET /companion/pending/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        invites = service.get_pending_invites(user_id)
        return {"success": True, "invites": invites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取邀请失败: {str(e)}")


@app.post("/companion/message")
async def send_companion_message(request: CompanionMessageRequest):
    """
    学伴之间发消息

    示例:
    {"relation_id": 1, "sender_id": "user_001", "content": "这道题你会吗？"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.send_message(request.relation_id, request.sender_id, request.content)
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@app.get("/companion/messages/{relation_id}")
async def get_companion_messages(relation_id: int, limit: int = 50):
    """
    获取学伴之间的互动记录

    示例: GET /companion/messages/1?limit=50
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        interactions = service.get_interactions(relation_id, limit=limit)
        return {"success": True, "interactions": interactions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")


@app.get("/companion/notifications/{user_id}")
async def check_companion_notifications(user_id: str, since: str = None):
    """
    检查学伴消息通知

    示例: GET /companion/notifications/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        new_messages = service.check_new_messages(user_id, since=since)
        pending_invites = service.get_pending_invites(user_id)
        return {
            "success": True,
            "new_messages": len(new_messages),
            "pending_invites": len(pending_invites),
            "messages": new_messages[:5],
            "invites": pending_invites,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查通知失败: {str(e)}")


# ==================== 学伴动态感知 API ====================

@app.get("/companion/activities/{user_id}")
async def get_companion_activities(user_id: str):
    """
    获取所有学伴的当前学习动态

    示例: GET /companion/activities/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        activities = service.get_companion_activities(user_id)
        return {"success": True, "activities": activities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学伴动态失败: {str(e)}")


@app.post("/companion/activity/update")
async def update_user_activity(request: ActivityUpdateRequest):
    """
    更新用户当前学习活动状态（供前端在学习时调用）

    示例:
    {"user_id": "user_001", "task_type": "practice", "task_detail": "正在练习: 循环结构", "topic": "循环结构"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.record_user_activity(
            request.user_id, request.task_type, request.task_detail, request.topic
        )
        return {"success": result["success"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新活动状态失败: {str(e)}")


# ==================== 共学邀请 API ====================

@app.post("/companion/co-study/invite")
async def invite_co_study(request: CoStudyInviteRequest):
    """
    发送共学邀请

    示例:
    {"inviter_id": "user_001", "invitee_id": "user_002",
     "resource_type": "practice", "resource_id": "P_03c63643",
     "title": "循环结构练习题"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.invite_co_study(
            request.inviter_id, request.invitee_id,
            request.resource_type, request.resource_id,
            request.title, request.mode
        )
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送共学邀请失败: {str(e)}")


@app.post("/companion/co-study/respond")
async def respond_co_study(request: CoStudyRespondRequest):
    """
    接受/拒绝共学邀请

    示例:
    {"invite_id": 1, "accept": true}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.respond_co_study(request.invite_id, request.accept)
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@app.get("/companion/co-study/invites/{user_id}")
async def get_co_study_invites(user_id: str):
    """
    获取待处理的共学邀请

    示例: GET /companion/co-study/invites/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        invites = service.get_co_study_invites(user_id)
        return {"success": True, "invites": invites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取共学邀请失败: {str(e)}")


@app.get("/companion/co-study/sessions/{user_id}")
async def get_co_study_sessions(user_id: str):
    """
    获取用户的所有共学记录

    示例: GET /companion/co-study/sessions/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        sessions = service.get_my_co_study_sessions(user_id)
        return {"success": True, "sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取共学记录失败: {str(e)}")


@app.get("/companion/co-study/sent/{user_id}")
async def get_sent_co_study_invites(user_id: str):
    """
    获取我发出的共学邀请（含状态）

    示例: GET /companion/co-study/sent/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        invites = service.get_sent_co_study_invites(user_id)
        return {"success": True, "invites": invites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取已发邀请失败: {str(e)}")


@app.get("/companion/co-study/notifications/{user_id}")
async def check_co_study_notifications(user_id: str, since: str = None):
    """
    检查共学邀请是否有被接受的（作为邀请方）

    示例: GET /companion/co-study/notifications/user_001?since=2026-06-01T00:00:00
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        accepted = service.check_co_study_notifications(user_id, since=since)
        return {"success": True, "accepted": accepted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查共学通知失败: {str(e)}")


@app.get("/companion/co-study/invitation/{invite_id}")
async def get_co_study_invitation(invite_id: int):
    """
    获取单个共学邀请详情

    示例: GET /companion/co-study/invitation/1
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        inv = service.get_invitation(invite_id)
        if inv:
            return {"success": True, "invitation": inv}
        return {"success": False, "error": "邀请不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取邀请详情失败: {str(e)}")


@app.post("/companion/co-study/message")
async def send_co_study_message(request: CoStudyMessageRequest):
    """
    在共学会话中发送消息

    示例:
    {"invitation_id": 1, "sender_id": "user_001", "content": "这道题我们一起做吧！"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.send_co_study_message(
            request.invitation_id, request.sender_id, request.content
        )
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@app.get("/companion/co-study/messages/{invitation_id}")
async def get_co_study_messages(invitation_id: int, limit: int = 100):
    """
    获取共学会话的交流消息

    示例: GET /companion/co-study/messages/1?limit=100
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        messages = service.get_co_study_messages(invitation_id, limit=limit)
        return {"success": True, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")


@app.post("/companion/co-study/delete")
async def delete_co_study(request: CoStudyDeleteRequest):
    """
    删除共学记录（邀请方或被邀请方均可）

    示例:
    {"invitation_id": 1, "user_id": "user_001"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.delete_co_study_invitation(
            request.invitation_id, request.user_id
        )
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ==================== 练习对比 API ====================

@app.get("/companion/compare/{problem_id}/{user_id_a}/{user_id_b}")
async def compare_practice(problem_id: str, user_id_a: str, user_id_b: str):
    """
    对比两个用户在同一道编程题上的成绩  --用于排行顺序

    示例: GET /companion/compare/P_03c63643/user_001/user_002
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.compare_practice_results(problem_id, user_id_a, user_id_b)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对比失败: {str(e)}")


# ==================== 结对编程 API ====================

class PairCodeUpdateRequest(BaseModel):
    invitation_id: int = Field(..., description="共学邀请ID")
    user_id: str = Field(..., description="用户ID")
    code_content: str = Field(..., description="代码内容")
    language: Optional[str] = Field(default="python", description="编程语言")


class PairSubmitRequest(BaseModel):
    invitation_id: int = Field(..., description="共学邀请ID")
    submitter_id: str = Field(..., description="提交者用户ID")
    language: Optional[str] = Field(default=None, description="编程语言（可选，不传则使用会话中保存的语言）")


@app.get("/companion/pair/session/{invitation_id}")
async def get_pair_session(invitation_id: int):
    """
    获取结对编程会话

    示例: GET /companion/pair/session/1
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        session = service.get_pair_session(invitation_id)
        if session:
            session["submit_result"] = json.loads(session.get("submit_result", "{}"))
            return {"success": True, "session": session}
        return {"success": False, "error": "会话不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话失败: {str(e)}")


@app.post("/companion/pair/code")
async def update_pair_code(request: PairCodeUpdateRequest):
    """
    更新结对编程代码

    示例:
    {"invitation_id": 1, "user_id": "user_001", "code_content": "print('hello')", "language": "python"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.update_pair_code(request.invitation_id, request.user_id, request.code_content, request.language)
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新代码失败: {str(e)}")


@app.post("/companion/pair/submit")
async def submit_pair_code(request: PairSubmitRequest):
    """
    提交结对编程的代码（结果算提交者的）

    示例:
    {"invitation_id": 1, "submitter_id": "user_001", "language": "python"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.submit_pair_code(request.invitation_id, request.submitter_id, request.language)
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


# ==================== 分享与收藏 API ====================

@app.post("/companion/share")
async def share_resource(request: ShareRequest):
    """
    分享资源给学伴或社区

    示例（分享给学伴）:
    {"sharer_id": "user_001", "receiver_id": "user_002",
     "resource_type": "practice", "resource_id": "p0_practice_循环结构",
     "title": "循环结构练习题", "knowledge_point": "循环结构"}

    示例（分享到社区）:
    {"sharer_id": "user_001", "receiver_id": "__community__",
     "resource_type": "doc", "resource_id": "p0_doc_循环结构",
     "title": "循环结构讲解文档", "knowledge_point": "循环结构"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()

        if request.receiver_id == "__community__":
            result = service.share_to_community(
                sharer_id=request.sharer_id,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                title=request.title,
                knowledge_point=request.knowledge_point,
                message=request.message,
            )
        else:
            result = service.share_to_companion(
                sharer_id=request.sharer_id,
                receiver_id=request.receiver_id,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                title=request.title,
                knowledge_point=request.knowledge_point,
                message=request.message,
            )
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分享失败: {str(e)}")


@app.post("/companion/favorite/add")
async def add_favorite(request: FavoriteRequest):
    """
    收藏资源

    示例:
    {"user_id": "user_001", "resource_type": "practice",
     "resource_id": "p0_practice_循环结构",
     "title": "循环结构练习题", "knowledge_point": "循环结构"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.add_favorite(
            user_id=request.user_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            title=request.title,
            knowledge_point=request.knowledge_point,
            source_user_id=request.source_user_id,
        )
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"收藏失败: {str(e)}")


@app.post("/companion/favorite/remove")
async def remove_favorite(request: FavoriteRemoveRequest):
    """
    取消收藏

    示例:
    {"user_id": "user_001", "resource_type": "practice", "resource_id": "p0_practice_循环结构"}
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        result = service.remove_favorite(
            user_id=request.user_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
        )
        return {"success": result["success"], **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消收藏失败: {str(e)}")


@app.get("/companion/favorites/{user_id}")
async def get_favorites(user_id: str):
    """
    获取我的收藏列表

    示例: GET /companion/favorites/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        favorites = service.get_favorites(user_id)
        return {"success": True, "favorites": favorites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取收藏失败: {str(e)}")


@app.get("/companion/favorite/check/{user_id}/{resource_type}/{resource_id}")
async def check_favorite(user_id: str, resource_type: str, resource_id: str):
    """
    检查是否已收藏

    示例: GET /companion/favorite/check/user_001/practice/p0_practice_循环结构
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        is_fav = service.is_favorited(user_id, resource_type, resource_id)
        return {"success": True, "is_favorited": is_fav}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查收藏失败: {str(e)}")


@app.get("/companion/shared/to-me/{user_id}")
async def get_shared_to_me(user_id: str):
    """
    获取别人分享给我的资源

    示例: GET /companion/shared/to-me/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        shared = service.get_shared_to_me(user_id)
        return {"success": True, "shared": shared}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取共享资源失败: {str(e)}")


@app.get("/companion/shared/by-me/{user_id}")
async def get_shared_by_me(user_id: str):
    """
    获取我分享出去的资源

    示例: GET /companion/shared/by-me/user_001
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        shared = service.get_shared_by_me(user_id)
        return {"success": True, "shared": shared}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取共享记录失败: {str(e)}")


@app.get("/companion/shared/community")
async def get_community_shared(limit: int = 50):
    """
    获取分享到社区的所有资源

    示例: GET /companion/shared/community?limit=20
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        shared = service.get_community_shared(limit=limit)
        return {"success": True, "shared": shared}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取社区共享失败: {str(e)}")


@app.get("/companion/shared/load/{sharer_id}/{resource_type}/{resource_id}")
async def load_shared_resource(sharer_id: str, resource_type: str, resource_id: str,
                               viewer_id: Optional[str] = None):
    """
    读取分享者存储的原始资源内容。
    若提供 viewer_id，自动将资源摘要写入其工作记忆，供 ChatAgent 上下文感知。
    """
    try:
        from services.companion_search import CompanionSearchService
        service = CompanionSearchService()
        data = service.load_shared_resource(sharer_id, resource_type, resource_id)
        if data:
            # ★★★ 泛化：所有资源类型查看时都写入 MemoryHub 工作记忆 ★★★
            if viewer_id:
                summary = _build_resource_summary(resource_type, data, resource_id)
                if summary:
                    try:
                        from memory import get_shared_memory_hub
                        hub = get_shared_memory_hub()
                        hub.working.set_last_generated(
                            user_id=viewer_id,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            summary=summary[:2000] + ("..." if len(summary) > 2000 else ""),
                        )
                        print(f"  📚 [资料卡] {resource_type} 已注入 {viewer_id} 的工作记忆")
                    except Exception as e:
                        print(f"  ⚠️ [资料卡] MemoryHub 写入失败: {e}")
            return {"success": True, "resource": data}
        return {"success": False, "error": "资源不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取资源失败: {str(e)}")


def _build_resource_summary(resource_type: str, data: dict, resource_id: str) -> str:
    """根据资源类型和内容构建统一的文本摘要"""
    try:
        if resource_type == "ppt":
            md = data.get("markdown_content", "")
            if md:
                return md
            # ★★★ 兜底：markdown_path 未存时，从目录搜索 ★★★
            filename = data.get("filename", "")
            topic_fallback = data.get("topic", "")
            _md = _find_ppt_markdown(filename, topic_fallback)
            if _md:
                return _md
            return f"PPT: {filename or resource_id}"

        if resource_type in ("doc", "document"):
            title = data.get("doc_title", data.get("title", "文档"))
            content = data.get("doc_content", data.get("content", ""))
            if content:
                return f"文档: {title}\n{content[:500]}"
            return f"文档: {title}"

        if resource_type == "extension":
            title = data.get("title", "拓展阅读")
            content = data.get("content", data.get("background", ""))
            if content:
                return f"拓展阅读: {title}\n{content[:500]}"
            return f"拓展阅读: {title}"

        if resource_type == "practice":
            problem = data.get("problem", data)
            title = problem.get("title", problem.get("topic", "编程题"))
            kps = problem.get("knowledge_points", [])
            kp_str = f" 知识点: {','.join(kps[:3])}" if kps else ""
            desc = (problem.get("description") or problem.get("content") or "")[:200]
            return f"编程题: {title}{kp_str}\n{desc}" if desc else f"编程题: {title}{kp_str}"

        if resource_type == "video":
            videos = data.get("videos", [data])
            lines = [f"视频搜索 ({len(videos)}个):"]
            for v in videos[:3]:
                lines.append(f"  - {v.get('title','')} ({v.get('author','')})")
            return "\n".join(lines)

        if resource_type == "mindmap":
            mm = data.get("mindmap", data)
            return f"思维导图: {mm.get('topic', mm.get('central_topic', '未命名'))}"

        if resource_type == "question":
            questions = data.get("questions", data)
            if isinstance(questions, dict):
                qs = questions.get("questions", [])
                return f"理论题 {len(qs)} 道"
            return f"理论题"

        if resource_type == "animation":
            meta = data.get("metadata", {})
            return f"动画: {meta.get('title', meta.get('topic', '未命名'))}"

        # 兜底
        return f"{resource_type}: {resource_id}"
    except Exception as e:
        print(f"  ⚠️ 构建资源摘要失败 ({resource_type}): {e}")
        return f"{resource_type}: {resource_id}"


def _find_ppt_markdown(filename: str, topic: str) -> str:
    """兜底搜索：在 markdown 目录中找匹配的 PPT markdown 文件"""
    import os
    md_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Agent", "children_agent", "PPT", "ppt_create", "markdown"
    )
    if not os.path.isdir(md_dir):
        return ""
    # 1. 通过文件名精确匹配（旧命名 uuid.md）
    if filename:
        prefix = filename.rsplit(".", 1)[0]
        md_candidate = os.path.join(md_dir, f"{prefix}.md")
        if os.path.exists(md_candidate):
            with open(md_candidate, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                return content[:2000] + ("..." if len(content) > 2000 else "")
        # 2. 新命名 topic_shortid.md 模式
        base = filename.rsplit(".", 1)[0]
        if "_" in base:
            topic_part = base.rsplit("_", 1)[0]
            for f_name in os.listdir(md_dir):
                if f_name.endswith(".md") and f_name.startswith(topic_part):
                    fp = os.path.join(md_dir, f_name)
                    with open(fp, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    if content.strip():
                        return content[:2000] + ("..." if len(content) > 2000 else "")
    # 3. 通过 topic 关键词搜索
    if topic:
        for f_name in os.listdir(md_dir):
            if not f_name.endswith(".md"):
                continue
            fp = os.path.join(md_dir, f_name)
            if os.path.getsize(fp) < 20:
                continue
            with open(fp, "r", encoding="utf-8") as fh:
                first_line = fh.readline()
            if topic in first_line or topic in f_name:
                with open(fp, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if content.strip():
                    return content[:2000] + ("..." if len(content) > 2000 else "")
    return ""


# ==================== 错题本 API ====================


@app.post("/theory/submit")
async def submit_theory_answer(request: TheoryAnswerSubmission):
    """
    提交理论题答案（自动判断正误，错误自动记入错题本）
    """
    try:
        from services.wrong_answer_service import WrongAnswerService, WrongAnswerError
        wa_service = WrongAnswerService()
        result = await wa_service.submit_theory_answer(
            user_id=request.user_id,
            question_type=request.question_type,
            question=request.question,
            user_answer=request.user_answer,
            knowledge_points=request.knowledge_points,
            source=request.source,
            record_id=request.record_id or ""
        )

        # ★★★ 数字孪生对比：自动触发孪生模拟作答并记录对比 ★★★
        twin_comparison = None
        try:
            from services.digital_twin_service import get_digital_twin_service
            twin_comparison = await get_digital_twin_service().record_user_activity_async(
                request.user_id, "theory_answer",
                {
                    "knowledge_point": (request.knowledge_points or [None])[0] or "",
                    "difficulty": float(request.question.get("difficulty", 0.5) if not isinstance(request.question.get("difficulty"), str) else 0.5),
                    "question_type": request.question_type,
                    "question": request.question,
                },
                {
                    "correct": result.get("is_correct", False),
                    "user_answer": request.user_answer,
                }
            )
        except Exception:
            pass  # 孪生对比不阻塞主流程

        if twin_comparison:
            result["twin_comparison"] = {
                "twin_correct": twin_comparison.get("twin_correct"),
                "result_type": twin_comparison.get("result_type"),
                "twin_confidence": twin_comparison.get("twin_confidence"),
                "knowledge_point": twin_comparison.get("knowledge_point"),
            }

        # ★★★ 查询错题尝试次数，决定是否触发自我表述 ★★★
        explain_required = False
        self_explanation_data = None
        if not result.get("is_correct", False) and request.record_id:
            try:
                _detail = wa_service.get_wrong_answer_detail(request.record_id, request.user_id)
                if _detail:
                    _attempt = _detail.get("attempt_count", 0)
                    explain_required = _attempt >= 2
                    # ★★★ 已提前推荐过 → 从缓存取推荐，不弹自我表述 ★★★
                    if _attempt >= 2:
                        try:
                            from services.self_explanation_service import SelfExplanationService
                            _se = SelfExplanationService()
                            if _se.has_recommendation_been_triggered(request.record_id, request.user_id):
                                explain_required = False
                                # 从缓存取推荐
                                _cached = await wa_service._get_recommendations_for_record(
                                    request.record_id, request.user_id
                                )
                                if _cached:
                                    result["material_recommendations"] = _cached
                                # 取分析数据供历史按钮
                                _se_data = _se.get_latest_analysis_for_record(
                                    request.record_id, request.user_id
                                )
                                if _se_data:
                                    self_explanation_data = _se_data
                        except Exception:
                            pass
            except Exception:
                pass
        result["explain_required"] = explain_required
        if self_explanation_data:
            result["self_explanation_data"] = self_explanation_data

        return result
    except WrongAnswerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交答案失败: {str(e)}")


@app.post("/review/session/get-or-create")
async def get_or_create_review_session(user_id: str = Body(...), knowledge_point: str = Body(...)):
    """
    获取或创建复习会话：同一个知识点复用同一个 session_id（理论/编程题共享）

    示例:
    {
      "user_id": "user_001",
      "knowledge_point": "循环结构"
    }
    """
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        session_id = kg.get_or_create_review_session(user_id, knowledge_point)
        return {"success": True, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取/创建会话失败: {str(e)}")


@app.get("/review/session/recent-completed/{user_id}")
async def get_recent_completed_sessions(user_id: str, days: int = 7):
    """获取最近 N 天内完成的复习会话"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        sessions = kg.get_recent_completed_sessions(user_id, days)
        return {"success": True, "sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最近复习记录失败: {str(e)}")


@app.get("/knowledge-mastery/all/{user_id}")
async def get_all_knowledge_mastery(user_id: str):
    """获取用户所有知识点的掌握度（过滤无效知识点）"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph, MASTERY_LABELS

        # ★★★ 非知识点的过滤规则（与数字孪生、复习提醒保持一致）★★★
        _NON_KP_PATTERNS = {
            "fill_blank", "judge", "multiple_choice", "short_answer",
            "single_choice", "rag_knowledge", "true_false", "completion",
            "essay", "matching", "ordering", "code_completion"
        }

        kg = KnowledgeMasteryGraph()
        items = kg.get_all_mastery(user_id)

        # 过滤无效知识点
        def _is_valid(item) -> bool:
            name = item.get("knowledge_point", "")
            if name in _NON_KP_PATTERNS:
                return False
            if len(name.strip()) <= 1:
                return False
            if "帮我复习" in name or "rag_" in name:
                return False
            return True

        items = [item for item in items if _is_valid(item)]
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识点掌握度失败: {str(e)}")


@app.get("/knowledge-universe/{user_id}")
async def get_knowledge_universe(user_id: str):
    """获取知识宇宙数据：所有知识点 + 依赖关系 + 掌握度"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph, MASTERY_LABELS
        kg = KnowledgeMasteryGraph()
        items = kg.get_all_mastery(user_id)
        mastery_map = {item["knowledge_point"]: item for item in items}

        # 获取所有依赖关系
        conn = kg.__class__._get_conn() if hasattr(kg.__class__, '_get_conn') else None
        all_deps = []
        try:
            from memory.knowledge_mastery import _get_conn
            conn = _get_conn()
            rows = conn.execute("SELECT knowledge_point, prerequisite FROM knowledge_dependencies").fetchall()
            all_deps = [{"knowledge_point": r["knowledge_point"], "prerequisite": r["prerequisite"]} for r in rows]
        finally:
            if conn:
                conn.close()

        # 收集所有知识点名称（包含依赖中出现但用户未学习的）
        all_kp_names = set(mastery_map.keys())
        for dep in all_deps:
            all_kp_names.add(dep["knowledge_point"])
            all_kp_names.add(dep["prerequisite"])

        # 构建节点列表
        stars = []
        for name in all_kp_names:
            m = mastery_map.get(name, {})
            stars.append({
                "name": name,
                "mastery_level": m.get("mastery_level", 0),
                "mastery_points": m.get("mastery_points", 0.0),
                "mastery_label": MASTERY_LABELS.get(m.get("mastery_level", 0), "未接触"),
            })

        return {"success": True, "stars": stars, "dependencies": all_deps}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识宇宙数据失败: {str(e)}")



@app.post("/review/session/complete")
async def complete_review_session(session_id: str = Body(..., embed=True)):
    """
    完成复习会话（计算综合得分，更新遗忘曲线）   作用就是判断复习情况是否满足更新条件

    示例:
    {
      "session_id": "uuid-string"
    }
    """
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        result = kg.complete_review_session(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"完成复习失败: {str(e)}")


@app.get("/review/session/{session_id}")
async def get_review_session(session_id: str):
    """获取复习会话状态"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        session = kg.get_review_session(session_id)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话失败: {str(e)}")


@app.get("/review/session/active-all/{user_id}")
async def get_all_active_review_sessions(user_id: str):
    """获取用户所有活跃的复习会话（支持多会话同时进行）---保证即使是刷新了也可以获取对应的session_id当然是用数据库得到"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        sessions = kg.get_all_active_review_sessions(user_id)
        return {"success": True, "sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取活跃会话失败: {str(e)}")


@app.get("/review/session/{session_id}/questions")
async def get_review_session_questions(session_id: str, question_type: str = None):
    """获取复习会话生成的题目（从数据库恢复）"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        questions = kg.get_review_questions(session_id, question_type)
        return {"success": True, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取题目失败: {str(e)}")


@app.post("/review/session/{session_id}/save-questions")
async def save_review_session_questions(session_id: str, questions: List[Dict] = Body(...), question_type: str = Body("theory")):
    """保存复习会话生成的题目到数据库"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        kg.save_review_questions(session_id, questions, question_type)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存题目失败: {str(e)}")


@app.get("/review/question/{question_id}/session")
async def get_session_by_question_id(question_id: str):
    """根据题目ID查询对应的复习会话信息"""
    try:
        from memory.knowledge_mastery import KnowledgeMasteryGraph
        kg = KnowledgeMasteryGraph()
        result = kg.get_session_by_question_id(question_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询会话失败: {str(e)}")


@app.post("/theory/judge")
async def judge_theory_answer(request: TheoryJudgeRequest):
    """
    判理论题（答错且传了user_id时自动记入错题本）

    示例:
    {
      "question_type": "single_choice",
      "question": {"question": "...", "options": [...], "answer": "A"},
      "user_answer": "B",
      "user_id": "user_001",
      "knowledge_points": ["循环结构"],
      "session_id": "optional-session-uuid"
    }
    """
    try:
        # ★★★ 上报 AgentMonitor：QuestionGeneratorAgent 开始判题 ★★★
        try:
            from Agent.agent_monitor import report_call_start
            report_call_start("question_gen", request.user_id or "", "理论题评判")
        except Exception:
            pass

        _theory_judge_ok = False
        try:
            from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent
            result = await QuestionGeneratorAgent.judge_theory_answer(
                question_data=request.question,
                user_answer=request.user_answer,
                question_type=request.question_type
            )
            _theory_judge_ok = True
        finally:
            # ★★★ 上报 AgentMonitor：QuestionGeneratorAgent 判题结束 ★★★
            try:
                from Agent.agent_monitor import report_call_end
                report_call_end("question_gen", _theory_judge_ok)
            except Exception:
                pass

        # ★★★ 数字孪生对比：自动触发孪生模拟作答并记录对比 ★★★
        twin_comparison = None
        try:
            if request.user_id:
                from services.digital_twin_service import get_digital_twin_service
                twin_comparison = await get_digital_twin_service().record_user_activity_async(
                    request.user_id, "theory_answer",
                    {
                        "knowledge_point": (request.knowledge_points or [None])[0] or "",
                        "difficulty": float(request.question.get("difficulty", 0.5) if not isinstance(request.question.get("difficulty"), str) else 0.5),
                        "question_type": request.question_type,
                        "question": request.question,
                    },
                    {
                        "correct": result.get("is_correct", False),
                        "user_answer": request.user_answer,
                    }
                )
        except Exception:
            pass  # 孪生对比不阻塞主流程

        if twin_comparison:
            result["twin_comparison"] = {
                "twin_correct": twin_comparison.get("twin_correct"),
                "result_type": twin_comparison.get("result_type"),
                "twin_confidence": twin_comparison.get("twin_confidence"),
                "knowledge_point": twin_comparison.get("knowledge_point"),
            }

        # ★★★ 答错且提供了 user_id，自动记入错题本 ★★★
        if not result["is_correct"] and request.user_id:
            from services.wrong_answer_service import WrongAnswerService
            import hashlib
            q_text = request.question.get("question", "")
            qid = f"q_{hashlib.md5(q_text.encode()).hexdigest()[:12]}"
            wa_service = WrongAnswerService()
            wa_service.add_wrong_answer(
                user_id=request.user_id,
                question_type=request.question_type,
                question_data=request.question,
                user_answer=request.user_answer,
                correct_answer=result.get("correct_answer", ""),
                score=0,
                question_id=qid,
                knowledge_points=request.knowledge_points or [],
                source="agent_judge",
            )

        # ★★★ 如果有 session_id，记录到复习会话（暂不更新遗忘曲线）★★★
        if request.session_id:
            print(f"\n🔗 [理论题] 收到 session_id={request.session_id[:12]}...，记录到复习会话")
            from memory.knowledge_mastery import KnowledgeMasteryGraph
            kg = KnowledgeMasteryGraph()
            kg.submit_review_answer(
                session_id=request.session_id,
                question_id=None,
                question_type="theory",
                user_answer=request.user_answer,
                is_correct=result["is_correct"],
                score=result.get("score", 0.0)
            )
        # ★★★ 如果没有 session_id，直接更新遗忘曲线（独立做题）★★★
        elif request.user_id and request.knowledge_points:
            # ★★★ 过滤脏数据：只保留长度 <= 20 的短知识点名，丢弃完整用户输入 ★★★
            _clean_kps = [kp for kp in (request.knowledge_points or []) if len(kp) <= 20]
            if not _clean_kps:
                print(f"⚠️ [理论题] knowledge_points 均为脏数据，跳过遗忘曲线更新: {request.knowledge_points}")
            else:
                print(f"\n⚠️ [理论题] 没有 session_id，直接更新遗忘曲线: kp={_clean_kps}")
                from memory.knowledge_mastery import KnowledgeMasteryGraph
                kg = KnowledgeMasteryGraph()
                for kp in _clean_kps:
                    kg.record_activity(
                        user_id=request.user_id,
                        knowledge_point=kp,
                        correct=result["is_correct"],
                        activity_type="theory",
                        difficulty="中等"
                    )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"判题失败: {str(e)}")


@app.get("/resource/question/{qid}")
async def get_question_by_id(qid: str):
    """
    根据问题ID从题库中查找已存在的题目（内容固定，不受LLM重新生成影响）

    示例: GET /resource/question/P_03c63643
    """
    try:
        from Agent.children_agent.recommendation.resource_db import ResourceDB
        db = ResourceDB()
        question = db.get_question(qid)
        if question:
            return {"success": True, "question": question}

        # ★★★ 后备方案：从所有用户的 ContentStore 中查找 ★★★
        try:
            from memory.content_store import USER_FEATURES_DIR
            import json, glob
            content_dir = str(USER_FEATURES_DIR)
            found = None
            # 匹配 practice_{qid}.json 和 phase_practice_{qid}.json
            for pattern in (
                f"{content_dir}/**/content/practice_{qid}.json",
                f"{content_dir}/**/content/phase_practice_{qid}.json",
            ):
                matches = glob.glob(pattern, recursive=True)
                if matches:
                    with open(matches[0], "r", encoding="utf-8") as f:
                        found = json.load(f)
                    break

            # ★★★ 如果文件名不匹配，再尝试扫描所有 phase_practice 文件，按 problem_id 匹配 ★★★
            if not found:
                for fp in glob.glob(f"{content_dir}/**/content/phase_practice_*.json", recursive=True):
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                        problem = raw.get("problem", {})
                        if problem.get("problem_id") == qid:
                            found = raw
                            break
                    except Exception:
                        continue

            if found:
                problem = found.get("problem", found)
                db.upsert_question(
                    qid=qid,
                    topic=(problem.get("knowledge_points") or [""])[0] or "编程",
                    sub_topic="",
                    difficulty={"简单": 1, "中等偏易": 2, "中等": 3, "中等偏难": 4, "困难": 5, "挑战": 5}.get(problem.get("difficulty", "中等"), 3),
                    knowledge_points=problem.get("knowledge_points", ["编程"]),
                    content=problem.get("description", "") + "\n" + problem.get("input_format", "") + "\n" + problem.get("output_format", ""),
                    hints=problem.get("hints", []),
                    metadata={"title": problem.get("title", ""), "examples": problem.get("examples", [])}
                )
                print(f"  ✅ 已从用户目录恢复题目 {qid} 到资源库")
                return {"success": True, "question": {
                    "id": qid,
                    "topic": (problem.get("knowledge_points") or [""])[0] or "编程",
                    "difficulty": {"简单": 1, "中等偏易": 2, "中等": 3, "中等偏难": 4, "困难": 5, "挑战": 5}.get(problem.get("difficulty", "中等"), 3),
                    "knowledge_points": ",".join(problem.get("knowledge_points", [])),
                    "content": problem.get("description", ""),
                    "hints": problem.get("hints", []),
                    "metadata": json.dumps({"title": problem.get("title", ""), "examples": problem.get("examples", [])})
                }}
        except Exception as fallback_e:
            print(f"  ⚠️ 用户目录后备查询失败: {fallback_e}")

        return {"success": False, "error": "题目不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询题目失败: {str(e)}")


@app.get("/wrong-answers/{user_id}")
async def get_wrong_answers(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    question_type: Optional[str] = None,
    source: Optional[str] = None,
    show_resolved: bool = False,
):
    """
    获取用户的错题列表（分页，按时间倒序）

    示例: GET /wrong-answers/user_001?page=1&page_size=10&question_type=programming
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()

        result = wa_service.get_wrong_answers(
            user_id=user_id,
            page=page,
            page_size=page_size,
            question_type=question_type,
            source=source,
            show_resolved=show_resolved,
        )

        return {"success": True, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取错题列表失败: {str(e)}")


@app.get("/wrong-answers/{user_id}/stats")
async def get_wrong_answer_stats(user_id: str):
    """
    获取用户错题统计信息

    示例: GET /wrong-answers/user_001/stats
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        stats = wa_service.get_wrong_answer_stats(user_id)
        # 追加易错题数量
        fw_stats = await wa_service.get_frequently_wrong_stats(user_id)
        stats["frequently_wrong"] = fw_stats["total"]
        return {"success": True, **stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取错题统计失败: {str(e)}")


@app.get("/wrong-answers/{user_id}/mastered")
async def get_mastered_answers(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    question_type: Optional[str] = None,
):
    """
    获取用户已掌握的错题列表（分页，按掌握时间倒序）

    展示掌握历程：错误次数、掌握时间、掌握得分等。

    示例: GET /wrong-answers/user_001/mastered?page=1&page_size=10
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        result = wa_service.get_mastered_answers(
            user_id=user_id,
            page=page,
            page_size=page_size,
            question_type=question_type,
        )
        return {"success": True, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取已掌握列表失败: {str(e)}")


@app.get("/wrong-answers/{user_id}/frequently-wrong")
async def get_frequently_wrong_answers(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    question_type: Optional[str] = None,
    source: Optional[str] = None,
):
    """
    获取用户的易错题列表（同一题答错超过4次且未掌握的顽固错题）

    示例: GET /wrong-answers/user_001/frequently-wrong?page=1&page_size=10
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        result = await wa_service.get_frequently_wrong_answers(
            user_id=user_id,
            page=page,
            page_size=page_size,
            question_type=question_type,
            source=source,
        )
        return {"success": True, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取易错题列表失败: {str(e)}")


@app.get("/wrong-answers/{user_id}/frequently-wrong/stats")
async def get_frequently_wrong_stats(user_id: str):
    """
    获取用户易错题专项统计（答错4次以上的顽固题分布、薄弱知识点）

    示例: GET /wrong-answers/user_001/frequently-wrong/stats
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        stats = await wa_service.get_frequently_wrong_stats(user_id)
        return {"success": True, **stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取易错题统计失败: {str(e)}")


@app.get("/wrong-answers/{record_id}/recommend/{user_id}")
async def get_wrong_answer_recommend(record_id: str, user_id: str):
    """
    获取某条错题的推荐学习资料（用于错3次以上时，弹窗中恢复推荐）

    示例: GET /wrong-answers/wa_abc123/recommend/user_001
    
    【缓存机制】优先从缓存表获取与该错题记录关联的推荐资源，确保每次返回相同的推荐
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        detail = wa_service.get_wrong_answer_detail(record_id, user_id)
        if not detail:
            raise HTTPException(status_code=404, detail="错题记录不存在")

        attempt_count = detail.get("attempt_count", 0)
        if attempt_count < 3:
            return {"success": True, "should_recommend": False, "attempt_count": attempt_count}

        # ★★★ 优先从缓存获取与该错题记录关联的推荐资源 ★★★
        cached_rec = await wa_service._get_recommendations_for_record(record_id, user_id)
        if cached_rec:
            print(f"   [错题本] 命中推荐缓存 (record_id={record_id})")
            return {"success": True, **cached_rec}

        # ★★★ 缓存不存在，生成新推荐 ★★★
        kps = detail.get("knowledge_points", [])
        diff = detail.get("difficulty", "")
        rec_result = await wa_service.recommend_materials_for_wrong_answer_async(
            user_id=user_id,
            knowledge_points=kps,
            attempt_count=attempt_count,
            difficulty=diff,
        )

        # ★★★ 将推荐资源与该错题记录关联并保存到缓存 ★★★
        if rec_result.get("should_recommend"):
            await wa_service._save_recommendations_for_record(
                record_id=record_id,
                user_id=user_id,
                materials=rec_result
            )

        return {"success": True, **rec_result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取推荐失败: {str(e)}")


@app.post("/wrong-answers/llm-generate")
async def llm_generate_materials(request: dict):
    """
    手动触发 LLM 生成补充学习资料（前端"用AI生成补充资料"按钮调用）

    请求体: {"user_id": "user_001", "record_id": "wa_abc123", 
             "knowledge_points": ["循环结构", "列表"],
             "resource_types": ["document", "video", "practice"]}
             
    如果传入 record_id，生成的推荐会保存到缓存表，与该错题记录关联
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        user_id = request.get("user_id", "")
        record_id = request.get("record_id", "")  # 新增：错题记录ID
        kps = request.get("knowledge_points", [])
        resource_types = request.get("resource_types", ["question", "practice"])
        difficulty = request.get("difficulty", "")

        if not user_id or not kps:
            raise HTTPException(status_code=400, detail="缺少 user_id 或 knowledge_points")

        llm_result = await wa_service.generate_llm_materials(
            user_id=user_id,
            knowledge_points=kps,
            resource_types=resource_types,
            difficulty=difficulty,
        )

        if llm_result:
            # 如果传入了 record_id，将生成的推荐保存到缓存表
            if record_id:
                # 先获取现有缓存（如果有）
                existing_rec = await wa_service._get_recommendations_for_record(record_id, user_id)
                if existing_rec:
                    # 合并材料
                    for key in llm_result.keys():
                        if key in existing_rec.get("materials", {}):
                            llm_result[key] = existing_rec["materials"][key] + llm_result[key]
                # 构建完整的推荐结果并保存
                rec_data = {
                    "should_recommend": True,
                    "attempt_count": 3,  # 默认3次触发推荐
                    "resource_types": resource_types,
                    "knowledge_points": kps,
                    "learning_style": "综合型",
                    "difficulty": difficulty,
                    "materials": llm_result,
                }
                await wa_service._save_recommendations_for_record(record_id, user_id, rec_data)
                print(f"   [错题本] LLM生成推荐已保存到缓存 (record_id={record_id})")
            
            return {"success": True, "materials": llm_result}
        else:
            return {"success": False, "error": "LLM 生成失败"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 生成失败: {str(e)}")


@app.delete("/wrong-answers/{record_id}/{user_id}")
async def delete_wrong_answer(record_id: str, user_id: str):
    """
    删除一条错题记录

    示例: DELETE /wrong-answers/wa_abc123/user_001
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        success = wa_service.delete_wrong_answer(record_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="错题记录不存在")

        return {"success": True, "message": "错题记录已删除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.post("/wrong-answers/{record_id}/unmaster/{user_id}")
async def unmark_wrong_answer(record_id: str, user_id: str):
    """
    取消已掌握标记，将错题移回待巩固列表

    示例: POST /wrong-answers/wa_abc123/unmaster/user_001
    """
    try:
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        success = wa_service.unmark_resolved(user_id, record_id)

        if not success:
            raise HTTPException(status_code=404, detail="错题记录不存在")

        return {"success": True, "message": "已取消掌握状态"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消掌握失败: {str(e)}")


# ==================== 自我表述 API（独立模块，不修改任何错题本字段） ====================


@app.post("/wrong-answers/explain/start")
async def start_self_explanation_endpoint(user_id: str = Body(...), record_id: str = Body(...)):
    """
    开始一次自我表述会话

    当用户在错题重练后答错时，前端检测到 explain_required=true，调用此接口。
    本接口根据 record_id 从错题本获取题目信息，创建一个自我表述会话。

    示例:
    POST /wrong-answers/explain/start
    {"user_id": "user_001", "record_id": "wa_abc123"}
    """
    try:
        from services.self_explanation_service import SelfExplanationService
        from services.wrong_answer_service import WrongAnswerService

        se_service = SelfExplanationService()
        wa_service = WrongAnswerService()

        # 从错题记录中获取题目详情
        detail = wa_service.get_wrong_answer_detail(record_id, user_id)
        if not detail:
            raise HTTPException(status_code=404, detail="错题记录不存在")

        qdata = detail.get("question_data", {})
        question_type = detail.get("question_type", "")

        # 提取题目内容
        if question_type == "programming":
            question_content = qdata.get("description", "") or qdata.get("content", "") or ""
            question_title = qdata.get("title", "") or ""
            correct_answer = str(qdata.get("solution", qdata.get("answer", "")))
        else:
            question_content = qdata.get("question", "") or qdata.get("description", "") or ""
            question_title = question_content[:100] if question_content else ""
            correct_answer = detail.get("correct_answer", "")

        # 创建会话
        session = se_service.start_session(
            user_id=user_id,
            record_id=record_id,
            question_type=question_type,
            question_title=question_title,
            question_content=question_content,
            correct_answer=correct_answer,
            user_answer=detail.get("user_answer", ""),
            knowledge_points=detail.get("knowledge_points", []),
        )
        return {"success": True, **session}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动自我表述失败: {str(e)}")


class TriggerRecommendationRequest(BaseModel):
    """触发推荐请求模型"""
    session_id: str = Field(..., description="自我表述会话ID")
    user_id: str = Field(..., description="用户ID")


@app.post("/wrong-answers/explain/trigger-recommendation")
async def trigger_recommendation_from_explanation(request: TriggerRecommendationRequest):
    """
    基于自我表述分析，触发错题推荐

    调用时机：LLM评估用户表述为"理解差"时，提前触发推荐（跳过等待第3次错误）
    效果：生成推荐内容并缓存到错题推荐表，标记已推荐，后续第3次重练不再重复
    """
    try:
        from services.self_explanation_service import SelfExplanationService

        se_service = SelfExplanationService()
        rec_result = await se_service.trigger_recommendation(
            session_id=request.session_id,
            user_id=request.user_id,
        )
        return {"success": True, **rec_result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发推荐失败: {str(e)}")


class SubmitExplanationRequest(BaseModel):
    """提交自我表述请求模型"""
    session_id: str = Field(..., description="自我表述会话ID")
    user_id: str = Field(..., description="用户ID")
    user_explanation: str = Field(..., description="用户的自我表述内容")


@app.post("/wrong-answers/explain/submit")
async def submit_self_explanation_endpoint(request: SubmitExplanationRequest):
    """
    提交用户的自我表述并获取 LLM 分析结果

    示例:
    POST /wrong-answers/explain/submit
    {
        "session_id": "se_abc123",
        "user_id": "user_001",
        "user_explanation": "我觉得是因为我没有考虑到边界情况..."
    }
    """
    try:
        from services.self_explanation_service import SelfExplanationService

        se_service = SelfExplanationService()
        result = await se_service.submit_explanation(
            session_id=request.session_id,
            user_id=request.user_id,
            user_explanation=request.user_explanation,
        )
        return {"success": True, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交分析失败: {str(e)}")


@app.get("/wrong-answers/explain/history/{user_id}")
async def get_self_explanation_history(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    获取用户的自我表述历史

    示例: GET /wrong-answers/explain/history/user_001?page=1&page_size=20
    """
    try:
        from services.self_explanation_service import SelfExplanationService

        se_service = SelfExplanationService()
        return se_service.get_user_sessions(user_id, page=page, page_size=page_size)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")


@app.get("/wrong-answers/explain/{session_id}/{user_id}")
async def get_self_explanation_session(session_id: str, user_id: str):
    """
    获取自我表述会话详情（含分析结果）

    示例: GET /wrong-answers/explain/se_abc123/user_001
    """
    try:
        from services.self_explanation_service import SelfExplanationService

        se_service = SelfExplanationService()
        session = se_service.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        return {"success": True, "session": session}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话失败: {str(e)}")


# ==================== 知识点盘问 API ====================


def _is_valid_knowledge_point(kp: str) -> bool:
    """过滤掉非知识点的文本（如命令短语、对话文本等）"""
    kp = kp.strip()
    if not kp:
        return False
    # 与 study_plan 的 _NON_KP_PATTERNS 保持一致：排除题型名称误写入
    _type_patterns = {
        "fill_blank", "judge", "multiple_choice", "short_answer",
        "single_choice", "rag_knowledge", "true_false", "completion",
        "essay", "matching", "ordering", "code_completion",
    }
    if kp in _type_patterns or kp.startswith("rag_"):
        return False
    # 含"帮"字——任何含"帮"的都不是知识点
    if "帮" in kp:
        return False
    # 含疑问词/语气词的也不是知识点
    _question_words = ["吗", "呢", "吧", "嘛", "啥", "怎么", "怎样", "什么", "哪个", "是否", "有没有"]
    for w in _question_words:
        if w in kp:
            return False
    # 请求/命令类动词——指示让系统做事，不是知识点名称
    _command_verbs = [
        "出题", "出理论", "出代码", "出应用", "出例子", "出案例",
        "生成", "创建", "提供", "给出", "列举", "举例",
        "解释", "说明", "阐述", "描述", "介绍",
        "检验", "检查", "判断", "评估", "验证",
        "训练", "练习", "做题", "答题",
        "推荐", "建议", "安排",
    ]
    for w in _command_verbs:
        if w in kp:
            return False
    # 常见非知识点关键词黑名单
    _blacklist = [
        "复习一下", "讲解一下", "总结一下", "看一下",
        "你好", "您好", "谢谢", "请问", "在吗",
        "不知道", "不会", "不懂", "不理解",
        "测试", "test", "例子", "示例",
        "其他的", "其他", "随便", "什么",
        "给我", "我要", "我想", "我来",
        "如何", "为什么", "能不能", "可不可以",
        "概念",   # "检验概念是否遗忘" 这类
    ]
    kp_lower = kp.lower()
    for word in _blacklist:
        if word in kp_lower:
            return False
    # 长度过滤：知识点通常 2-30 字
    if len(kp) > 30 or len(kp) < 2:
        return False
    return True


class StartInterrogationRequest(BaseModel):
    """开始盘问请求模型"""
    user_id: str = Field(..., description="用户ID")
    knowledge_point: str = Field(..., description="知识点名称")


class SubmitAnswerRequest(BaseModel):
    """提交答案请求模型"""
    session_id: str = Field(..., description="盘问会话ID")
    answer: str = Field(..., description="用户答案")


@app.get("/api/knowledge-points/{user_id}")
async def get_knowledge_points(user_id: str):
    """
    获取用户的知识点列表（从错题和知识点图谱中提取）

    示例: GET /api/knowledge-points/user_001
    """
    try:
        from services.wrong_answer_service import WrongAnswerService

        wa_service = WrongAnswerService()

        # 从错题本获取知识点（所有错题去重提取）
        all_wrong = wa_service.get_wrong_answers(
            user_id=user_id,
            page=1,
            page_size=10000,
            show_resolved=True,
        )
        records = all_wrong.get("records", [])

        kp_map = {}  # knowledge_point -> {count, max_attempt, avg_score, has_unresolved}
        for r in records:
            kps = r.get("knowledge_points", [])
            if isinstance(kps, str):
                kps = [s.strip() for s in kps.split(",") if s.strip()]
            for kp in kps:
                if not kp:
                    continue
                if not _is_valid_knowledge_point(kp):
                    continue
                if kp not in kp_map:
                    kp_map[kp] = {
                        "count": 0,
                        "max_attempt": 0,
                        "total_score": 0,
                        "has_unresolved": False,
                        "sources": set(),
                    }
                kp_map[kp]["count"] += 1
                kp_map[kp]["max_attempt"] = max(kp_map[kp]["max_attempt"], r.get("attempt_count", 1))
                kp_map[kp]["total_score"] += r.get("score", 0)
                if not r.get("resolved", False):
                    kp_map[kp]["has_unresolved"] = True
                kp_map[kp]["sources"].add(r.get("source", "unknown"))

        # 合并知识点图谱的掌握度信息
        try:
            from memory.knowledge_mastery import KnowledgeMasteryGraph
            km = KnowledgeMasteryGraph()
            all_mastery = km.get_all_mastery(user_id)
            mastery_map = {m["knowledge_point"]: m for m in all_mastery}

            # 把知识图谱中有的但错题中没有的知识点也加入（同样需要过滤）
            for kp, m in mastery_map.items():
                if kp not in kp_map and _is_valid_knowledge_point(kp):
                    kp_map[kp] = {
                        "count": 0,
                        "max_attempt": 0,
                        "total_score": 0,
                        "has_unresolved": False,
                        "sources": set(),
                    }
        except Exception:
            mastery_map = {}

        # 构建结果
        result = []
        for kp, info in kp_map.items():
            mastery = mastery_map.get(kp, {})
            avg_score = round(info["total_score"] / max(info["count"], 1), 1)
            expected_level = min(mastery.get("mastery_level", 0) * 25 + 10, 100)

            result.append({
                "knowledge_point": kp,
                "wrong_count": info["count"],
                "max_attempt": info["max_attempt"],
                "avg_score": avg_score,
                "has_unresolved": info["has_unresolved"],
                "sources": list(info["sources"]),
                "mastery_level": mastery.get("mastery_level", 0),
                "mastery_label": mastery.get("mastery_label", "未接触"),
                "mastery_points": mastery.get("mastery_points", 0.0),
                "expected_mastery_score": expected_level,
                "total_practiced": mastery.get("total_practiced", 0),
                "total_correct": mastery.get("total_correct", 0),
            })

        # ★★★ 合并盘问结果（持久化的）+ 计算 status ★★★
        try:
            from Agent.children_agent.quiz_interrogation_agent import get_interrogation_results
            interrogation_results = get_interrogation_results(user_id)
            for item in result:
                kp = item["knowledge_point"]
                ir = interrogation_results.get(kp)
                item["interrogation"] = ir
                # 计算分类 status
                if ir:
                    if ir.get("overall_score", 0) >= 75:
                        item["status"] = "mastered"       # 已掌握
                    else:
                        item["status"] = "struggling"     # 需巩固
                else:
                    if item.get("wrong_count", 0) > 0:
                        item["status"] = "unpracticed"    # 待盘问
                    else:
                        item["status"] = "new"             # 新知识点
        except Exception:
            for item in result:
                item["interrogation"] = None
                item["status"] = "unpracticed" if item.get("wrong_count", 0) > 0 else "new"

        # 排序：需巩固 > 待盘问 > 新知识点 > 已掌握
        _status_order = {"struggling": 0, "unpracticed": 1, "new": 2, "mastered": 3}
        result.sort(key=lambda x: (_status_order.get(x["status"], 9), -x.get("wrong_count", 0)))

        return {"success": True, "knowledge_points": result, "total": len(result)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识点列表失败: {str(e)}")


@app.post("/api/interrogation/start")
async def start_interrogation(request: StartInterrogationRequest):
    """
    开始知识点盘问会话

    示例: POST /api/interrogation/start
    { "user_id": "user_001", "knowledge_point": "排序算法" }
    """
    try:
        from Agent.children_agent.quiz_interrogation_agent import QuizInterrogationAgent
        agent = QuizInterrogationAgent()
        result = await agent.start_interrogation(
            user_id=request.user_id,
            knowledge_point=request.knowledge_point,
        )
        return {"success": True, **result}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"开始盘问失败: {str(e)}")


@app.post("/api/interrogation/answer")
async def submit_interrogation_answer(request: SubmitAnswerRequest):
    """
    提交盘问答案，获取评估和下一轮问题

    示例: POST /api/interrogation/answer
    { "session_id": "iq_xxx", "answer": "用户回答内容" }
    """
    try:
        from Agent.children_agent.quiz_interrogation_agent import QuizInterrogationAgent
        agent = QuizInterrogationAgent()
        result = await agent.submit_answer(
            session_id=request.session_id,
            user_answer=request.answer,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交答案失败: {str(e)}")


@app.get("/api/interrogation/result/{session_id}")
async def get_interrogation_result(session_id: str):
    """
    获取盘问最终结果及可视化数据

    示例: GET /api/interrogation/result/iq_xxx
    """
    try:
        from Agent.children_agent.quiz_interrogation_agent import QuizInterrogationAgent
        agent = QuizInterrogationAgent()
        result = await agent.get_result(session_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取结果失败: {str(e)}")


# 内存存储（供 analyze-image 会话模式使用）：session_id -> [{"role","content","image_data_url"}, ...]
_image_chat_sessions: Dict[str, List[Dict[str, Any]]] = {}


@app.post("/api/interrogation/analyze-image")
async def analyze_interrogation_image(
    file: UploadFile = File(None),
    knowledge_point: str = Form(""),
    question: str = Form(""),
    session_id: str = Form(""),
):
    """
    分析用户上传的盘问配图，使用 Qwen-VL 多模态模型
    - 不传 session_id：单次分析（原有行为）
    - 传 session_id：会话模式，携带历史上下文，支持图片/文字多轮追问

    示例: POST /api/interrogation/analyze-image (multipart/form-data)
    file=图片文件&knowledge_point=排序算法&question=请画出冒泡排序的过程
    file=&session_id=imgc_xxx&question=继续分析（纯文字追问）
    """
    temp_path = None
    try:
        dashscope_key = os.getenv("DASHSCOPE_API_KEY", "sk-ws-H.EHEXPER.yUFF.MEYCIQD5dksUxv1hLfiF5kqi_LKN2WLrHmUUQXfPLKBdmJnoFwIhAIHSxUX4b71Lpa56Vu2J6ad_M9Kx4-TAD4_UbxbmFrSy")
        from openai import OpenAI
        client = OpenAI(
            api_key=dashscope_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        is_session_mode = bool(session_id)

        # ========== 会话模式：初始化/获取历史 ==========
        if is_session_mode:
            global _image_chat_sessions
            if session_id not in _image_chat_sessions:
                _image_chat_sessions[session_id] = []
            history = _image_chat_sessions[session_id]
        else:
            history = []

        # ========== 处理上传的图片 ==========
        image_data_url = None
        if file and file.filename:
            import tempfile, base64
            suffix = os.path.splitext(file.filename or ".jpg")[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_path = tmp.name

            with open(temp_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            mime_type = "image/png" if suffix.lower() in (".png",) else "image/jpeg"
            image_data_url = f"data:{mime_type};base64,{b64_data}"

        # ========== 构建消息（系统提示 + 历史上下文 + 当前消息） ==========
        if is_session_mode:
            # 会话模式：教育助教角色，含上下文
            messages = [
                {
                    "role": "system",
                    "content": "你是专业的计算机教育助教，擅长解答学生提交的题目图片和文字问题。"
                               "请仔细观察图片内容，结合对话历史，给出详细、准确的分析和解答。"
                               "回答要清晰、结构化，指出关键知识点和易错点。",
                },
            ]
            # 历史上下文（最近6轮）
            for h in history[-6:]:
                msg_content = []
                if h.get("image_data_url"):
                    msg_content.append({"type": "image_url", "image_url": {"url": h["image_data_url"]}})
                if h.get("content"):
                    msg_content.append({"type": "text", "text": h["content"]})
                if msg_content:
                    messages.append({"role": h["role"], "content": msg_content})

            # 当前用户消息
            user_content = []
            if image_data_url:
                user_content.append({"type": "image_url", "image_url": {"url": image_data_url}})
            if question:
                user_content.append({"type": "text", "text": question})
            elif not image_data_url:
                user_content.append({"type": "text", "text": "请继续分析"})
            messages.append({"role": "user", "content": user_content})
        else:
            # 单次模式：原有行为
            if not file or not file.filename:
                raise HTTPException(status_code=400, detail="单次分析模式必须上传图片文件")

            messages = [
                {
                    "role": "system",
                    "content": "你是专业的计算机教育助教，擅长分析学生提交的图片内容（手写代码、流程图、笔记等）。"
                               "请仔细观察图片，描述图中内容，并判断与知识点的关系。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"知识点: {knowledge_point}\n问题: {question}\n请分析这张图片的内容，指出其中的正确和错误之处。"},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ]

        # ========== 调用 Qwen-VL 多模态模型（异步线程池，不阻塞事件循环） ==========
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="qwen-vl-max",
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )

        analysis = resp.choices[0].message.content if resp.choices else ""

        # ========== 会话模式：存储本轮对话 ==========
        if is_session_mode:
            # 用户消息
            user_record = {"role": "user", "content": question or ""}
            if image_data_url:
                user_record["image_data_url"] = image_data_url
            history.append(user_record)
            # AI回复
            history.append({"role": "assistant", "content": analysis})

        # ========== 如有图片，同步到OSS持久化（异步线程池） ==========
        oss_url = None
        if temp_path and file and file.filename:
            try:
                from services.oss_storage import upload_file
                folder = "image_chat" if is_session_mode else (knowledge_point or "user")
                obj_key = await asyncio.to_thread(
                    upload_file, temp_path, folder, "interrogation_user_img", file.filename
                )
                if obj_key:
                    oss_url = f"https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/{obj_key}"
            except Exception as e:
                print(f"  ⚠️ [盘问API] 用户图片上传OSS失败: {e}")

        return {
            "success": True,
            "analysis": analysis,
            "filename": file.filename if file else None,
            "oss_url": oss_url,
            "session_id": session_id if is_session_mode else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"图片分析失败: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


@app.get("/knowledge-quiz-page")
async def serve_knowledge_quiz_page():
    """提供知识点盘问前端页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'knowledge_quiz.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="知识点盘问页面未找到")


class AdoptSuggestionRequest(BaseModel):
    """采纳评估建议请求模型"""
    suggestion_type: str = Field(..., description="建议类型: resource_adjustment/difficulty_adjustment/knowledge_priority/pace_advice")
    content: str = Field(..., description="建议内容")
    weight: float = Field(default=0.7, description="采纳权重 0.0~1.0")


class RejectSuggestionRequest(BaseModel):
    """拒绝/撤销采纳建议请求模型"""
    suggestion_type: str = Field(..., description="建议类型")
    content: str = Field(..., description="建议内容")


# ==================== 学习效果评估 API ====================

class RegeneratePartRequest(BaseModel):
    """局部重新评估请求模型"""
    assessment_id: str = Field(..., description="评估报告ID")
    part_type: str = Field(..., description="要重新生成的部分类型: dimension/weak_point/suggestion/overall")
    part_index: Optional[int] = Field(None, description="要重新生成的部分索引（从0开始），不填则重新生成所有该类型")


@app.post("/assessment/regenerate/{user_id}")
async def regenerate_assessment_part(user_id: str, request: RegeneratePartRequest):
    """
    局部重新评估：只重新生成评估报告中的指定部分，其他部分保持不变
    
    示例: POST /assessment/regenerate/user_001
    {
      "assessment_id": "assess_20240101_001",
      "part_type": "dimension",
      "part_index": 0
    }
    
    part_type 支持的值:
    - dimension: 重新生成某个维度的评估
    - weak_point: 重新生成某个薄弱点
    - suggestion: 重新生成某条建议
    - overall: 重新生成总体评估等级
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        result = await agent.regenerate_assessment_part(
            user_id=user_id,
            assessment_id=request.assessment_id,
            part_type=request.part_type,
            part_index=request.part_index
        )
        
        if result.get("status") == "success":
            return {"success": True, "assessment": result.get("assessment"), "message": result.get("message")}
        else:
            return {"success": False, "message": result.get("message", "重新生成失败")}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"局部重新评估失败: {str(e)}")


@app.get("/assessment/notifications/{user_id}")
async def get_assessment_notifications(user_id: str):
    """
    获取用户评估报告通知
    
    示例: GET /assessment/notifications/user_001
    """
    try:
        from Agent.children_agent.assessment_notifier import get_assessment_notifier
        notifier = get_assessment_notifier()
        
        notifications = notifier.get_notifications(user_id)
        unread_count = notifier.get_unread_count(user_id)
        
        return {
            "success": True,
            "notifications": notifications,
            "unread_count": unread_count
        }
    except Exception as e:
        return {"success": False, "message": str(e), "notifications": [], "unread_count": 0}


class ReadNotificationRequest(BaseModel):
    """标记通知已读请求"""
    assessment_id: Optional[str] = Field(None, description="评估报告ID（可选，不填则标记所有已读）")


@app.post("/assessment/notifications/{user_id}/read")
async def mark_notifications_read(user_id: str, request: ReadNotificationRequest = None):
    """
    标记评估通知为已读
    
    示例: POST /assessment/notifications/user_001/read
    {
      "assessment_id": "assess_..."  # 可选
    }
    """
    try:
        from Agent.children_agent.assessment_notifier import get_assessment_notifier
        notifier = get_assessment_notifier()
        
        assessment_id = request.assessment_id if request else None
        notifier.mark_as_read(user_id, assessment_id)
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/assessment/generate/{user_id}")
async def generate_assessment(user_id: str):
    """
    生成用户学习效果评估报告
    整合特征画像、知识点掌握、错题本、学习统计等多维数据，
    由LLM分析生成综合评估与动态调整建议

    示例: POST /assessment/generate/user_001
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        assessment = await agent.generate_assessment(user_id)
        return {"success": True, "assessment": assessment}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成评估报告失败: {str(e)}")


@app.get("/assessment/latest/{user_id}")
async def get_latest_assessment(user_id: str):
    """
    获取用户最新的评估报告

    示例: GET /assessment/latest/user_001
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        assessment = agent.get_latest_assessment(user_id)
        if assessment:
            return {"success": True, "assessment": assessment}
        return {"success": False, "message": "暂无评估报告"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评估报告失败: {str(e)}")


@app.post("/assessment/apply/{user_id}")
async def apply_assessment_adjustments(user_id: str):
    """
    应用最新评估报告的调整建议
    自动更新学习焦点、标注计划优化建议等

    示例: POST /assessment/apply/user_001
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        assessment = agent.get_latest_assessment(user_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="暂无评估报告")
        result = await agent.apply_adjustments(user_id, assessment)
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用调整失败: {str(e)}")


@app.post("/assessment/phase-apply/{user_id}/{phase_index}")
async def apply_phase_assessment(user_id: str, phase_index: int):
    """
    接受阶段性评估：保存到评估页面，供用户自行采纳建议

    示例: POST /assessment/phase-apply/user_001/0
    """
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = await planner.get_plan_async(user_id)
        if not plan:
            raise HTTPException(status_code=404, detail="学习计划不存在")
        phases = plan.get("phases", [])
        if phase_index >= len(phases):
            raise HTTPException(status_code=404, detail="阶段不存在")
        assessment = phases[phase_index].get("phase_assessment")
        if not assessment:
            raise HTTPException(status_code=404, detail="该阶段暂无评估报告")
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        result = await agent.apply_adjustments(user_id, assessment)

        # ★★★ 检测所有阶段是否已完成 → 触发续期流程 ★★★
        all_done = all(p.get("status") == "已完成" for p in phases)
        if all_done:
            plan["_continuation_pending"] = True
            plan.pop("_continuation_proposal", None)
            await planner.save_plan_async(user_id, plan, plan_id=plan.get("plan_id"), make_active=False)
            print(f"  🔄 [进度追踪] 所有阶段完成，标记续期待用户确认接收...")
            return {
                "success": True,
                "result": result,
                "continuation_pending": True,
                "all_phases_completed": True,
                "message": "所有阶段已完成，可接收续期计划"
            }

        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用阶段性评估失败: {str(e)}")


@app.get("/study_plan/{user_id}/review-reminder")
async def get_review_reminder(user_id: str):
    """
    获取用户复习提醒（今日到期 + 即将到期）

    示例: GET /study_plan/user_001/review-reminder
    """
    try:
        from Agent.children_agent.recommendation.recommender import PersonalizedRecommender
        recommender = PersonalizedRecommender()
        reminder = recommender.get_review_reminder(user_id)
        return {"success": True, "reminder": reminder}
    except Exception as e:
        return {"success": False, "reminder": None, "error": str(e)}


@app.post("/assessment/adopt/{user_id}")
async def adopt_assessment_suggestion(user_id: str, request: AdoptSuggestionRequest):
    """
    采纳一条评估建议（带权重）

    示例: POST /assessment/adopt/user_001
    {
      "suggestion_type": "knowledge_priority",
      "content": "循环结构",
      "weight": 0.8
    }
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        result = agent.adopt_suggestion(
            user_id=user_id,
            suggestion_type=request.suggestion_type,
            content=request.content,
            weight=request.weight
        )
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采纳建议失败: {str(e)}")


@app.post("/assessment/reject/{user_id}")
async def reject_assessment_suggestion(user_id: str, request: RejectSuggestionRequest):
    """
    拒绝/撤销一条已采纳的建议

    示例: POST /assessment/reject/user_001
    {
      "suggestion_type": "knowledge_priority",
      "content": "循环结构"
    }
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        result = agent.reject_suggestion(
            user_id=user_id,
            suggestion_type=request.suggestion_type,
            content=request.content
        )
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拒绝建议失败: {str(e)}")


@app.get("/assessment/adopted/{user_id}")
async def get_adopted_suggestions(user_id: str):
    """
    获取用户所有已采纳的评估建议

    示例: GET /assessment/adopted/user_001
    """
    try:
        from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
        agent = LearningAssessmentAgent()
        adopted = agent.get_adopted_suggestions(user_id)
        weights = agent.build_adoption_weights(user_id)
        return {
            "success": True,
            "adopted_suggestions": adopted,
            "adoption_weights": weights
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取采纳建议失败: {str(e)}")


# ==================== 主动触发引擎 ====================

class HesitateRequest(BaseModel):
    """犹豫检测请求模型"""
    user_id: str = Field(..., description="用户ID")
    input_prefix: str = Field(default="", description="用户当前输入的部分文本")


@app.get("/api/proactive/check")
async def check_proactive_greeting(user_id: str):
    """
    登录时检查是否需要发送时段问候。
    根据当前时间（早上/中午/下午/晚上/深夜）和用户学习数据生成问候。
    
    示例: GET /api/proactive/check?user_id=user_001
    
    返回:
        success: 是否成功
        message: 问候消息对象（或null）
            text: 消息文本
            keywords: 可点击的关键词列表
            type: 消息类型
    """
    try:
        from Agent.proactive_trigger_engine import ProactiveTriggerEngine
        engine = ProactiveTriggerEngine()
        message = engine.check_greeting(user_id)
        if message:
            return {"success": True, "message": message}
        return {"success": True, "message": None}
    except Exception as e:
        print(f"⚠️ 主动问候检查失败: {e}")
        return {"success": False, "message": None, "error": str(e)}


@app.post("/api/proactive/hesitate")
async def check_hesitation(data: HesitateRequest):
    """
    用户输入卡顿时生成建议消息。
    前端检测到用户连续删除3次以上时调用此接口。
    
    示例: POST /api/proactive/hesitate
    Body: {"user_id": "user_001", "input_prefix": "什么是"}
    
    返回:
        success: 是否成功
        message: 建议消息对象（或null）
            text: 消息文本
            keywords: 可点击的关键词列表
            type: 消息类型
    """
    try:
        from Agent.proactive_trigger_engine import ProactiveTriggerEngine
        engine = ProactiveTriggerEngine()
        message = engine.check_hesitation(data.user_id, data.input_prefix)
        if message:
            return {"success": True, "message": message}
        return {"success": True, "message": None}
    except Exception as e:
        print(f"⚠️ 犹豫检测失败: {e}")
        return {"success": False, "message": None, "error": str(e)}


# ==================== 学习方案选择 ====================

class PlanSelectRequest(BaseModel):
    """方案选择请求模型"""
    user_id: str = Field(..., description="用户ID")
    plan_id: str = Field(..., description="选中的方案ID (A/B/C)")
    plan_name: str = Field(default="", description="方案名称")


@app.post("/api/plan/select")
async def select_plan(data: PlanSelectRequest):
    """
    用户选择学习方案后存储选择结果。
    
    存储到 DynamicFeatureUpdater 的中央特征中，
    供后续 Conduct 层资源生成时读取。
    
    示例: POST /api/plan/select
    Body: {"user_id": "user_001", "plan_id": "B", "plan_name": "实践驱动"}
    """
    try:
        # ★★★ 存储到独立的 plan_configs 目录 ★★★
        import json
        import os
        from datetime import datetime
        
        config_dir = os.path.join(os.path.dirname(__file__), "data", "plan_configs")
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, f"{data.user_id}.json")
        
        config = {
            "user_id": data.user_id,
            "plan_id": data.plan_id,
            "plan_name": data.plan_name,
            "selected_at": datetime.now().isoformat()
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 用户 {data.user_id} 选择了方案 {data.plan_id}: {data.plan_name}")
        return {"success": True, "plan_id": data.plan_id, "plan_name": data.plan_name}
    except Exception as e:
        print(f"⚠️ 方案选择保存失败: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/plan/selected/{user_id}")
async def get_selected_plan(user_id: str):
    """
    获取用户已选择的学习方案。
    
    示例: GET /api/plan/selected/user_001
    """
    try:
        import json
        import os
        config_file = os.path.join(os.path.dirname(__file__), "data", "plan_configs", f"{user_id}.json")
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                plan = json.load(f)
            return {"success": True, "plan": plan}
        return {"success": True, "plan": None}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/plan/options/{user_id}")
async def get_plan_options(user_id: str):
    """
    获取用户已生成的学习方案列表（持久化存储的选项）。
    
    示例: GET /api/plan/options/user_001
    """
    try:
        import json
        import os
        options_file = os.path.join(os.path.dirname(__file__), "data", "plan_configs", f"{user_id}_options.json")
        if os.path.exists(options_file):
            with open(options_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            plans = data.get("plans", [])
            return {"success": True, "plans": plans}
        return {"success": True, "plans": []}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 学习路线市场 API ====================

@app.get("/api/route-market/categories", tags=["路线市场"])
async def route_market_categories():
    """获取所有路线分类"""
    from services.route_market_service import get_categories
    categories = await get_categories()
    return {"success": True, "categories": categories}


@app.get("/api/route-market/list", tags=["路线市场"])
async def route_market_list(category: str = "", difficulty: str = "",
                            sort: str = "hot", search: str = "", user_id: str = ""):
    """列出路线市场中的路线模板
    
    Args:
        user_id: 用户ID，用于返回该用户的采纳状态
    """
    from services.route_market_service import list_routes
    routes = await list_routes(category=category, difficulty=difficulty,
                               sort=sort, search=search, user_id=user_id)
    return {"success": True, "routes": routes, "total": len(routes)}


@app.get("/api/route-market/{route_id}", tags=["路线市场"])
async def route_market_detail(route_id: str, user_id: str = ""):
    """获取路线完整详情（含阶段和资源）
    
    Args:
        user_id: 用户ID，用于返回该用户的采纳状态
    """
    from services.route_market_service import get_route_detail, _load_user_adoptions_map
    route = await get_route_detail(route_id)
    if not route:
        return {"success": False, "error": "路线不存在"}
    
    # 添加用户采纳状态
    if user_id:
        adoptions = _load_user_adoptions_map(user_id)
        if route_id in adoptions:
            adoption_info = adoptions[route_id]
            if adoption_info.get("personalized"):
                # AI个性化不标记为"已采纳"
                route["adopted_by_user"] = False
                route["adoption_mode"] = None
                route["adopted_at"] = None
                route["was_personalized"] = True
            else:
                route["adopted_by_user"] = True
                route["adoption_mode"] = "直接使用"
                route["adopted_at"] = adoption_info.get("adopted_at", "")
        else:
            route["adopted_by_user"] = False
            route["adoption_mode"] = None
            route["adopted_at"] = None
    
    return {"success": True, "route": route}


@app.post("/api/route-market/{route_id}/adopt", tags=["路线市场"])
async def route_market_adopt(route_id: str, data: dict):
    """采纳路线为用户的学习计划"""
    from services.route_market_service import adopt_route
    user_id = data.get("user_id", "")
    personalize = data.get("personalize", False)
    if not user_id:
        return {"success": False, "error": "缺少 user_id"}
    result = await adopt_route(route_id, user_id, personalize)
    return result


@app.get("/api/route-market/{user_id}/adopted", tags=["路线市场"])
async def route_market_user_adoptions(user_id: str):
    """获取用户已采纳的路线"""
    from services.route_market_service import get_user_adoptions
    adoptions = await get_user_adoptions(user_id)
    return {"success": True, "adoptions": adoptions}


@app.post("/api/route-market/{route_id}/rate", tags=["路线市场"])
async def route_market_rate(route_id: str, data: dict):
    """用户对路线评分"""
    from services.route_market_service import rate_route
    user_id = data.get("user_id", "")
    rating = data.get("rating", 5)
    comment = data.get("comment", "")
    if not user_id:
        return {"success": False, "error": "缺少 user_id"}
    result = await rate_route(route_id, user_id, rating, comment)
    return result


@app.post("/api/route-market/auto-generate", tags=["路线市场"])
async def auto_generate_route_info_endpoint(data: dict):
    """自动分析学习计划，生成路线市场信息（供前端预填充）"""
    from services.route_market_service import auto_generate_route_info
    plan_data = data.get("plan_data", {})
    if not plan_data or not plan_data.get("phases"):
        return {"success": False, "error": "学习计划数据无效"}
    route_info = await auto_generate_route_info(plan_data)
    return {"success": True, "route_info": route_info}


@app.post("/api/route-market/publish", tags=["路线市场"])
async def publish_plan_to_market_endpoint(data: dict):
    """用户将学习计划发布到路线市场"""
    from services.route_market_service import publish_plan_to_market
    user_id = data.get("user_id", "")
    plan_data = data.get("plan_data", {})
    route_info = data.get("route_info", {})
    if not user_id:
        return {"success": False, "error": "缺少 user_id"}
    if not plan_data or not plan_data.get("phases"):
        return {"success": False, "error": "学习计划数据无效"}
    result = await publish_plan_to_market(user_id, plan_data, route_info)
    return result


@app.get("/api/route-market/check-published", tags=["路线市场"])
async def check_plan_published(user_id: str = "", plan_id: str = "", plan_name: str = ""):
    """检查学习计划是否已发布到路线市场"""
    from services.route_market_service import _ROUTES_DIR, _read_json, _write_json
    import os
    if not user_id:
        return {"published": False}

    # 第一层：按 _original_plan_id 精确匹配
    if plan_id:
        for fname in os.listdir(_ROUTES_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(_ROUTES_DIR, fname)
            existing = _read_json(fpath)
            if existing and existing.get("_original_plan_id") == plan_id and existing.get("creator", {}).get("id") == user_id:
                return {"published": True, "route_id": existing.get("route_id", "")}

    # 第二层：按路线名称 + 发布者匹配（兼容旧数据）
    if plan_name:
        for fname in os.listdir(_ROUTES_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(_ROUTES_DIR, fname)
            existing = _read_json(fpath)
            if existing and existing.get("name") == plan_name and existing.get("creator", {}).get("id") == user_id:
                # 补写 _original_plan_id 以便后续精确匹配
                if plan_id and not existing.get("_original_plan_id"):
                    existing["_original_plan_id"] = plan_id
                    _write_json(fpath, existing)
                return {"published": True, "route_id": existing.get("route_id", "")}

    return {"published": False}


@app.get("/route-share/{route_id}", tags=["路线市场"])
async def route_share_page(route_id: str):
    """分享学习计划流程图页面 - 使用模板渲染"""
    import os
    import html as html_module
    from fastapi.responses import HTMLResponse
    from services.route_market_service import _get_route_detail_sync, generate_mermaid_flowchart

    route = _get_route_detail_sync(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")

    # 使用 Agent 智能生成流程图
    mermaid_syntax = generate_mermaid_flowchart(route)

    # 读取模板文件
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'route_share.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 模板变量替换（先替换 mermaid，避免其他变量被误替换）
    diff_label = {"easy": "入门", "medium": "进阶", "hard": "高级"}.get(route.get("difficulty", ""), route.get("difficulty", ""))
    rating = route.get("stats", {}).get("rating", 0)
    adoptions = route.get("stats", {}).get("adoptions", 0)

    # 对 mermaid 语法进行 HTML 转义（保留换行）
    mermaid_escaped = html_module.escape(mermaid_syntax).replace('\n', '&#10;')

    replacements = {
        '{{mermaid_syntax}}': mermaid_escaped,
        '{{route_name}}': html_module.escape(route.get("name", "")),
        '{{route_subtitle}}': html_module.escape(route.get("subtitle", "")),
        '{{route_desc}}': html_module.escape(route.get("description", "")),
        '{{diff_label}}': diff_label,
        '{{duration}}': html_module.escape(route.get("estimated_duration", "")),
        '{{hours}}': str(route.get("estimated_hours", 0)),
        '{{rating}}': f"⭐ {rating}" if rating else "暂无",
        '{{adoptions}}': str(adoptions),
    }
    for key, value in replacements.items():
        html = html.replace(key, value)

    # 设置 CSS 变量（动态封面颜色）
    cover_color = route.get("cover_color", "#667eea")
    html = html.replace('<div class="share-card">', f'<div class="share-card" style="--cover-color: {cover_color};">')

    return HTMLResponse(content=html)


@app.delete("/api/route-market/{route_id}/delete", tags=["路线市场"])
async def delete_route_api(route_id: str, body: dict = Body(...)):
    """删除路线（仅发布者本人可删除）"""
    from services.route_market_service import delete_route_sync

    user_id = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")

    result = delete_route_sync(route_id, user_id)
    if not result.get("success"):
        raise HTTPException(status_code=403, detail=result.get("error", "删除失败"))
    return result


@app.put("/api/route-market/{route_id}/update", tags=["路线市场"])
async def update_route_api(route_id: str, body: dict = Body(...)):
    """更新路线信息（仅发布者本人可编辑）"""
    from services.route_market_service import update_route_sync

    user_id = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")

    updates = {k: v for k, v in body.items() if k != "user_id"}
    result = update_route_sync(route_id, user_id, updates)
    if not result.get("success"):
        raise HTTPException(status_code=403, detail=result.get("error", "更新失败"))
    return result


# ==================== 预制游戏页面 ====================

@app.get("/game/1", tags=["游戏"])
async def serve_game_1():
    """提供喵星叠叠乐游戏页面"""
    import os
    from fastapi.responses import HTMLResponse
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', '1.html')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="游戏页面未找到")

@app.get("/game/2", tags=["游戏"])
async def serve_game_2():
    """提供迷宫导航游戏页面"""
    import os
    from fastapi.responses import HTMLResponse
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', '2.html')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="游戏页面未找到")




#   -------------------------------管理端——————————————————————————————
@app.get("/weights-page", tags=["页面"])
async def serve_weights_page():
    """提供权重配置管理测试页面"""
    import os
    from fastapi.responses import HTMLResponse
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'weights_test.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="权重配置页面未找到")

# ==================== 学伴语音通话 API ====================

@app.websocket("/companion/voice/ws")
async def voice_call_websocket(websocket: WebSocket):
    """
    学伴语音通话 WebSocket 信令端点

    消息类型:
    - call: 发起通话 {"type": "call", "caller_id": "user_001", "callee_id": "user_002"}
    - join: 加入通话 {"type": "join", "room_id": "call_xxx", "user_id": "user_002"}
    - accept: 接听通话 {"type": "accept", "room_id": "call_xxx", "user_id": "user_002"}
    - reject: 拒绝通话 {"type": "reject", "room_id": "call_xxx", "user_id": "user_002"}
    - hangup: 挂断通话 {"type": "hangup", "room_id": "call_xxx", "user_id": "user_001"}
    - offer: SDP offer {"type": "offer", "room_id": "call_xxx", "sdp": {...}}
    - answer: SDP answer {"type": "answer", "room_id": "call_xxx", "sdp": {...}}
    - ice-candidate: ICE 候选 {"type": "ice-candidate", "room_id": "call_xxx", "candidate": {...}}
    """
    await websocket.accept()
    user_id = None
    room_id = None

    try:
        from services.voice_call_service import voice_call_manager

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # 注册/更新用户 WebSocket 连接
            if msg_type == "register":
                # 主动注册（页面加载时调用）
                uid = data.get("user_id")
                if uid:
                    user_id = uid
                    voice_call_manager.register_user_ws(user_id, websocket)
                    await websocket.send_json({"type": "registered", "user_id": user_id})
                continue
            elif msg_type in ["call", "join", "accept"] and user_id is None:
                uid = data.get("caller_id") or data.get("user_id")
                if uid:
                    user_id = uid
                    voice_call_manager.register_user_ws(user_id, websocket)

            if msg_type == "call":
                # 发起通话
                caller_id = data.get("caller_id")
                callee_id = data.get("callee_id")
                user_id = caller_id
                voice_call_manager.register_user_ws(user_id, websocket)

                try:
                    room = await voice_call_manager.create_room(caller_id, callee_id)
                    room_id = room.room_id
                    voice_call_manager.set_caller_ws(room_id, websocket)

                    await websocket.send_json({
                        "type": "call_created",
                        "room_id": room_id,
                        "caller_id": caller_id,
                        "callee_id": callee_id
                    })

                    # 通知被叫方（如果在线），不在线则等超时自动结束
                    callee_ws = voice_call_manager.get_user_ws(callee_id)
                    if callee_ws:
                        try:
                            await callee_ws.send_json({
                                "type": "incoming_call",
                                "room_id": room_id,
                                "caller_id": caller_id
                            })
                        except Exception:
                            pass

                    # 启动30秒响铃超时，超时后通知双方
                    async def _notify_timeout(rid, cid, callee):
                        for uid in (cid, callee):
                            ws = voice_call_manager.get_user_ws(uid)
                            if ws:
                                try:
                                    await ws.send_json({"type": "call_ended", "room_id": rid, "reason": "no_answer"})
                                except Exception:
                                    pass
                    await voice_call_manager.start_ring_timeout(
                        room_id, 30, on_timeout=_notify_timeout
                    )

                except ValueError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })

            elif msg_type == "join":
                # 被叫方加入通话
                room_id = data.get("room_id")
                user_id = data.get("user_id")
                room = voice_call_manager.get_room(room_id)

                if room and user_id == room.callee_id:
                    voice_call_manager.set_callee_ws(room_id, websocket)
                    voice_call_manager.update_status(room_id, "ringing")

                    await websocket.send_json({
                        "type": "joined",
                        "room_id": room_id,
                        "caller_id": room.caller_id
                    })

                    # 通知主叫方有人加入
                    caller_ws = room.caller_ws
                    if caller_ws:
                        await caller_ws.send_json({
                            "type": "callee_joined",
                            "room_id": room_id,
                            "callee_id": user_id
                        })

            elif msg_type == "accept":
                # 接听通话
                room_id = data.get("room_id")
                user_id = data.get("user_id")
                voice_call_manager.update_status(room_id, "connected")
                voice_call_manager.cancel_ring_timeout(room_id)

                room = voice_call_manager.get_room(room_id)
                if room:
                    # 通知主叫方已接听
                    caller_ws = room.caller_ws
                    if caller_ws:
                        await caller_ws.send_json({
                            "type": "call_accepted",
                            "room_id": room_id
                        })

                    await websocket.send_json({
                        "type": "call_connected",
                        "room_id": room_id
                    })

            elif msg_type == "reject":
                # 拒绝通话
                room_id = data.get("room_id")
                user_id = data.get("user_id")
                voice_call_manager.cancel_ring_timeout(room_id)

                room = voice_call_manager.get_room(room_id)
                if room:
                    caller_ws = room.caller_ws
                    await voice_call_manager.reject_call(room_id)
                    if caller_ws:
                        await caller_ws.send_json({
                            "type": "call_rejected",
                            "room_id": room_id
                        })

            elif msg_type == "hangup":
                # 挂断通话
                room_id = data.get("room_id")
                user_id = data.get("user_id")
                voice_call_manager.cancel_ring_timeout(room_id)
                room = voice_call_manager.get_room(room_id)

                if room:
                    peer_ws = voice_call_manager.get_peer_ws(room_id, user_id)
                    await voice_call_manager.end_call(room_id)
                    if peer_ws:
                        try:
                            await peer_ws.send_json({
                                "type": "call_ended",
                                "room_id": room_id
                            })
                        except Exception:
                            pass

                    await websocket.send_json({
                        "type": "call_ended",
                        "room_id": room_id
                    })

            elif msg_type == "offer":
                # SDP offer 转发
                room_id = data.get("room_id")
                sdp = data.get("sdp")
                peer_ws = voice_call_manager.get_peer_ws(room_id, user_id)
                if peer_ws:
                    await peer_ws.send_json({
                        "type": "offer",
                        "room_id": room_id,
                        "sdp": sdp
                    })

            elif msg_type == "answer":
                # SDP answer 转发
                room_id = data.get("room_id")
                sdp = data.get("sdp")
                peer_ws = voice_call_manager.get_peer_ws(room_id, user_id)
                if peer_ws:
                    await peer_ws.send_json({
                        "type": "answer",
                        "room_id": room_id,
                        "sdp": sdp
                    })

            elif msg_type == "ice-candidate":
                # ICE candidate 转发
                room_id = data.get("room_id")
                candidate = data.get("candidate")
                peer_ws = voice_call_manager.get_peer_ws(room_id, user_id)
                if peer_ws:
                    await peer_ws.send_json({
                        "type": "ice-candidate",
                        "room_id": room_id,
                        "candidate": candidate
                    })

    except WebSocketDisconnect:
        # 断开连接时清理通话和注册信息
        if user_id:
            from services.voice_call_service import voice_call_manager
            # 注销 WebSocket 连接（只有当前注册的是这个 WS 才注销，避免多标签页误删）
            voice_call_manager.unregister_user_ws(user_id, websocket)

            # 清理用户所在的所有通话房间（任何状态）
            room = voice_call_manager.get_user_room(user_id)
            if room:
                room_id = room.room_id
                voice_call_manager.cancel_ring_timeout(room_id)
                peer_ws = voice_call_manager.get_peer_ws(room_id, user_id)
                await voice_call_manager.end_call(room_id)
                if peer_ws:
                    try:
                        await peer_ws.send_json({
                            "type": "call_ended",
                            "room_id": room_id,
                            "reason": "peer_disconnected"
                        })
                    except Exception:
                        pass
    except Exception as e:
        print(f"语音通话 WebSocket 错误: {e}")


@app.get("/companion/voice/history/{user_id}")
async def get_voice_call_history(user_id: str, limit: int = 20):
    """
    获取用户的语音通话记录

    示例: GET /companion/voice/history/user_001?limit=20
    """
    try:
        from services.voice_call_service import voice_call_manager
        history = voice_call_manager.get_call_history(user_id, limit)
        return {"success": True, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取通话记录失败: {str(e)}")


# ==================== 学习小组 API ====================

@app.post("/group/create")
async def create_group(request: CreateGroupRequest):
    """创建学习小组"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.create_group(request.name, request.creator_id,
                                       request.description, request.max_members,
                                       request.is_public)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建小组失败: {str(e)}")


@app.post("/group/join")
async def join_group(request: JoinGroupRequest):
    """加入小组"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.join_group(request.group_id, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加入小组失败: {str(e)}")


@app.post("/group/leave")
async def leave_group(request: JoinGroupRequest):
    """退出小组"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.leave_group(request.group_id, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"退出小组失败: {str(e)}")


@app.post("/group/dissolve")
async def dissolve_group(request: JoinGroupRequest):
    """解散小组（仅创建者）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.dissolve_group(request.group_id, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解散小组失败: {str(e)}")


@app.get("/group/list/{user_id}")
async def list_user_groups(user_id: str):
    """获取用户加入的所有小组"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        groups = service.list_user_groups(user_id)
        return {"success": True, "groups": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取小组列表失败: {str(e)}")


@app.get("/group/detail/{group_id}")
async def get_group_detail(group_id: int):
    """获取小组详情"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        detail = service.get_group_detail(group_id)
        if detail:
            return {"success": True, "group": detail}
        return {"success": False, "error": "小组不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取小组详情失败: {str(e)}")


@app.get("/group/all")
async def list_all_groups():
    """获取所有小组（发现页）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        groups = service.list_all_groups()
        return {"success": True, "groups": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取小组列表失败: {str(e)}")


# ==================== 小组邀请 API ====================

@app.post("/group/invite")
async def invite_to_group(request: GroupInviteRequest):
    """邀请用户加入小组（仅 owner/admin）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.invite_to_group(request.group_id, request.inviter_id, request.invitee_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"邀请失败: {str(e)}")


@app.post("/group/invite/respond")
async def respond_group_invite(request: GroupInviteRespondRequest):
    """接受/拒绝小组邀请"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.respond_group_invite(request.invitation_id, request.invitee_id, request.accept)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@app.get("/group/invites/pending/{user_id}")
async def get_pending_group_invites(user_id: str):
    """获取用户待处理的入组邀请"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        invites = service.get_pending_group_invites(user_id)
        return {"success": True, "invites": invites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取邀请失败: {str(e)}")


@app.get("/group/invites/{group_id}")
async def get_group_invitations(group_id: int):
    """获取小组的待处理邀请列表（owner/admin）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        invites = service.get_group_invitations(group_id)
        return {"success": True, "invites": invites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取邀请列表失败: {str(e)}")


# ==================== 小组聊天 API ====================

@app.post("/group/message")
async def send_group_message(request: GroupMessageRequest):
    """发送小组消息"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.send_message(request.group_id, request.sender_id,
                                       request.content, request.msg_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@app.get("/group/messages/{group_id}")
async def get_group_messages(group_id: int, limit: int = 50, before_id: Optional[int] = None):
    """获取小组聊天消息"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        messages = service.get_messages(group_id, limit, before_id)
        return {"success": True, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")


# ==================== 比赛 API ====================

@app.post("/group/competition/create")
async def create_competition(request: CreateCompetitionRequest):
    """创建比赛"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.create_competition(
            request.group_id, request.title, request.created_by,
            request.description, request.problem_count,
            request.start_at, request.end_at)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建比赛失败: {str(e)}")


@app.post("/group/competition/update")
async def update_competition(request: UpdateCompetitionRequest):
    """更新比赛信息（仅创建者，仅 pending 状态可修改）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.update_competition(
            request.competition_id, request.user_id,
            title=request.title,
            description=request.description,
            start_at=request.start_at,
            end_at=request.end_at)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新比赛失败: {str(e)}")


@app.post("/group/competition/generate-problems")
async def generate_problems(request: GenerateProblemsRequest):
    """生成比赛赛题"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.generate_problems(
            request.competition_id, request.user_id,
            request.input_text, request.problem_count)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成赛题失败: {str(e)}")


@app.post("/group/competition/save-problems")
async def save_problems_manual(request: SaveProblemsManualRequest):
    """手动保存/覆盖赛题"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.save_problems_manual(
            request.competition_id, request.user_id, request.problems, request.replace)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存赛题失败: {str(e)}")


@app.post("/group/competition/start")
async def start_competition(request: JoinGroupRequest):
    """开始比赛（group_id 字段复用为 competition_id）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        # 复用 JoinGroupRequest: group_id=competition_id, user_id=operator
        result = service.start_competition(request.group_id, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"开始比赛失败: {str(e)}")


@app.post("/group/competition/end")
async def end_competition(request: JoinGroupRequest):
    """结束比赛"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.end_competition(request.group_id, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"结束比赛失败: {str(e)}")


@app.post("/group/competition/delete")
async def delete_competition(request: JoinGroupRequest):
    """删除比赛（仅创建者，复用 JoinGroupRequest: group_id=competition_id, user_id=user_id）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.delete_competition(request.group_id, request.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除比赛失败: {str(e)}")


@app.get("/group/competitions/{group_id}")
async def get_competitions(group_id: int):
    """获取小组的所有比赛"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        comps = service.get_competitions(group_id)
        return {"success": True, "competitions": comps}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取比赛列表失败: {str(e)}")


@app.get("/group/competition/detail/{competition_id}")
async def get_competition_detail(competition_id: int):
    """获取比赛详情（含题目）"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        detail = service.get_competition_detail(competition_id)
        if detail:
            return {"success": True, "competition": detail}
        return {"success": False, "error": "比赛不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取比赛详情失败: {str(e)}")


@app.post("/group/competition/submit")
async def submit_solution(request: SubmitSolutionRequest):
    """提交答案"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        result = service.submit_solution(
            request.competition_id, request.problem_id,
            request.user_id, request.answer_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@app.get("/group/competition/ranking/{competition_id}")
async def get_competition_ranking(competition_id: int):
    """获取比赛实时排行"""
    try:
        from services.group_service import GroupService
        service = GroupService()
        ranking = service.get_ranking(competition_id)
        return {"success": True, "ranking": ranking}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取排行失败: {str(e)}")


@app.post("/group/upload-image")
async def upload_group_image(file: UploadFile = File(...), sender_id: str = Form(...),
                              group_id: int = Form(...)):
    """上传图片到小组聊天"""
    try:
        from services.oss_storage import upload_file
        content = await file.read()
        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        object_key = f"group_images/{group_id}/{uuid.uuid4().hex}.{ext}"
        url = upload_file(object_key, content)
        if url:
            # 保存图片消息
            from services.group_service import GroupService
            service = GroupService()
            service.send_message(group_id, sender_id, url, "image")
            return {"success": True, "url": url}
        return {"success": False, "error": "上传失败"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传图片失败: {str(e)}")


# ==================== 启动服务 ====================

if __name__ == "__main__":
    # 部署配置：通过环境变量覆盖默认值
    _host = os.getenv("API_HOST", "0.0.0.0")
    _port = int(os.getenv("API_PORT", "8000"))

    print("\n" + "="*80)
    print("🚀 启动Agent测试API服务")
    print("="*80)
    print(f"\n📍 API地址: http://localhost:{_port}")
    print(f"📚 API文档: http://localhost:{_port}/docs")
    print(f"🎯 可视化前端: http://localhost:{_port}/viz")
    print("💡 提示: 可以使用前端页面或curl测试\n")

    uvicorn.run(
        "api_server:app",  # ★★★ 使用字符串格式以支持reload ★★★
        host=_host,
        port=_port,
        reload=False  # ★★★ 关闭自动重启，防止内存缓存丢失 ★★★
    )
