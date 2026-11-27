"""
admin_helper_agent.py - 管理端协助 Agent

为管理员提供自然语言交互能力：
1. 解答管理端功能、字段含义等操作问题
2. 通过自然语言指令自动执行增删改查操作
执行过程实时流式推送给前端可见。
"""

import json
import os
import re
from typing import Dict, Any, Optional, AsyncGenerator, List

import httpx
from pydantic import BaseModel, Field

try:
    from langchain_deepseek import ChatDeepSeek
except ImportError:
    ChatDeepSeek = None

try:
    from langchain_qwq import ChatQwen
except ImportError:
    ChatQwen = None


# ★★★ 修复：复用 httpx 客户端，避免每次工具调用新建 TCP 连接 ★★★
_HTTP_CLIENT: httpx.AsyncClient = None

def _get_http_client() -> httpx.AsyncClient:
    """获取共享的 httpx.AsyncClient 实例（懒加载）"""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=30.0)
    return _HTTP_CLIENT


# ==================== 工具 Schema（Pydantic 模型 → 自动转为 tool schema）====================

class ListKnowledgeFilesInput(BaseModel):
    """查看知识库文件列表"""

class SyncKnowledgeBaseInput(BaseModel):
    """同步知识库到向量库"""

class DeleteKnowledgeFileInput(BaseModel):
    filename: str = Field(description="文件名，如 数据结构.md")

class ListQuestionsInput(BaseModel):
    question_type: str = Field(default="", description="题型: theory=理论题 practice=编程题，空=全部")
    topic: str = Field(default="", description="主题筛选")
    difficulty: str = Field(default="", description="难度 1-5")
    keyword: str = Field(default="", description="关键词")
    page: int = Field(default=1, description="页码")

class AddQuestionInput(BaseModel):
    topic: str = Field(description="主题/知识点分类（必填）")
    difficulty: int = Field(description="难度 1-5（必填）")
    content: str = Field(description="题目内容/题干（必填）")
    solution: str = Field(description="答案/解析（必填）")
    title: str = Field(default="", description="题目标题")
    knowledge_points: str = Field(default="", description="知识点，逗号分隔")
    sub_topic: str = Field(default="", description="子主题: single_choice/multiple_choice/judge/fill_blank/short_answer")

class DeleteQuestionInput(BaseModel):
    qid: str = Field(description="题目 ID")

class GetQuestionDetailInput(BaseModel):
    qid: str = Field(description="题目 ID")

class ListVideosInput(BaseModel):
    topic: str = Field(default="", description="主题筛选")
    difficulty: str = Field(default="", description="难度 1-5")
    keyword: str = Field(default="", description="关键词")
    page: int = Field(default=1, description="页码")

class AddVideoInput(BaseModel):
    title: str = Field(description="视频标题（必填）")
    topic: str = Field(description="主题/知识点（必填）")
    platform: str = Field(default="bilibili", description="平台: bilibili/youtube/other")
    difficulty: int = Field(default=3, description="难度 1-5")
    url: str = Field(default="", description="视频链接")
    duration_sec: int = Field(default=0, description="时长（秒）")
    knowledge_points: str = Field(default="", description="知识点，逗号分隔")


class ListVideoFilesInput(BaseModel):
    """查看媒体素材列表（OSS/本地上传的视频文件，非B站外部链接）"""
    pass

class DeleteVideoFileInput(BaseModel):
    """删除媒体素材文件"""
    filename: str = Field(description="文件名，如 video/admin/xxx.mp4")

class UploadVideoFileInput(BaseModel):
    """上传媒体素材文件"""
    file_path: str = Field(description="本地文件路径，如 /path/to/video.mp4")

class DeleteVideoInput(BaseModel):
    vid: str = Field(description="视频 ID")

class GetVideoDetailInput(BaseModel):
    vid: str = Field(description="视频 ID")

class UpdateQuestionInput(BaseModel):
    qid: str = Field(description="题目 ID（必填）")
    topic: str = Field(default="", description="主题/知识点分类")
    difficulty: int = Field(default=0, description="难度 1-5")
    content: str = Field(default="", description="题目内容/题干")
    solution: str = Field(default="", description="答案/解析")
    title: str = Field(default="", description="题目标题")
    knowledge_points: str = Field(default="", description="知识点，逗号分隔")
    sub_topic: str = Field(default="", description="子主题: single_choice/multiple_choice/judge/fill_blank/short_answer")

class UpdateVideoInput(BaseModel):
    vid: str = Field(description="视频 ID（必填）")
    title: str = Field(default="", description="视频标题")
    topic: str = Field(default="", description="主题/知识点")
    platform: str = Field(default="", description="平台: bilibili/youtube/other")
    difficulty: int = Field(default=0, description="难度 1-5")
    url: str = Field(default="", description="视频链接")
    duration_sec: int = Field(default=0, description="时长（秒）")
    knowledge_points: str = Field(default="", description="知识点，逗号分隔")

class GetWeightConfigInput(BaseModel):
    category: str = Field(description="分类: attention_tracker / emotion_state_mapper / attention_bridge / gaze_detector")

class UpdateWeightInput(BaseModel):
    category: str = Field(description="分类名")
    updates_json: str = Field(description='JSON格式更新内容，如 {"immersion_weights": {"focus_score": 0.5}}')

class ResetWeightsInput(BaseModel):
    """重置所有权重为默认值"""

class GetQuestionStatsInput(BaseModel):
    """查看题库统计信息"""

class GetVideoStatsInput(BaseModel):
    """查看视频统计信息"""

class GetTopicsInput(BaseModel):
    """获取所有知识点列表"""

class GetKnowledgeStatsInput(BaseModel):
    """查看知识库统计信息"""

class ResetAgentStatsInput(BaseModel):
    """重置 Agent 统计数据"""

class GetAgentStatsInput(BaseModel):
    """查看 Agent 调用排行和实时状态"""

class GetGlobalRankingWeightsInput(BaseModel):
    """查看全局排行榜权重配置"""

class UpdateGlobalRankingWeightsInput(BaseModel):
    """更新全局排行榜权重配置"""
    coding_score: float = Field(default=0.30, description="编程能力分权重，0~1")
    accuracy_score: float = Field(default=0.25, description="准确率分权重，0~1")
    learning_time_score: float = Field(default=0.15, description="学习时长分权重，0~1")
    problem_count_score: float = Field(default=0.15, description="做题数量分权重，0~1")
    overall_feature_score: float = Field(default=0.15, description="综合特征分权重，0~1")


# ==================== 系统提示 ====================

SYSTEM_PROMPT = """你是「权重配置管理面板」的管理助手，协助管理员完成管理端操作。

## 你的能力
- 知识库管理：查看文件列表、上传文件、同步到向量库、删除文件、查看统计信息
- 题库管理：新增/查看/更新/删除题目（理论题和编程题）、查看题库统计、获取知识点列表
- 视频管理（🎬 视频）：新增/查看/更新/删除视频（ResourceDB 数据库中的B站等外部链接记录）、查看视频统计
- 媒体素材管理（📁 媒体素材）：查看OSS/本地上传的视频文件列表（非B站外部链接，而是可播放的 mp4 文件）
- 权重配置：查看和修改各类权重、重置所有权重为默认值，分类包括：attention_tracker（注意力追踪）、emotion_state_mapper（情绪状态映射）、attention_bridge（注意力桥梁）、gaze_detector（凝视检测）
- 全局排行榜权重：查看和修改全局用户排行榜的各维度权重（编程能力、准确率、学习时长、做题数量、综合特征），权重总和必须为1.0
- Agent 监控：查看 Agent 调用排行和实时状态、重置 Agent 统计数据

## 回答规则
1. 管理员问操作方式或字段含义时，基于系统实际情况回答
2. 管理员给出具体指令（含完整信息）时，调用对应工具执行
3. 执行前先说明要做什么，执行后报告结果
4. 信息不完整时，询问缺少的关键信息
5. 当用户提出任何管理操作需求（查看数据、执行增删改查等）时，优先调用对应工具获取真实数据或执行操作，而非仅描述操作步骤
6. **只调用用户当前指令相关的一个工具**，不要同时调用多个不相关的工具。例如用户问"查看视频"只调用视频相关工具，不要同时查知识库
7. **严格区分"视频"和"媒体素材"**：用户说"视频"指的是 ResourceDB 中的B站等外部链接视频记录；用户说"媒体素材/视频文件/素材"指的是 OSS/本地上传的 mp4 文件。这两者是完全不同的数据源，不要混为一谈，不要在展示一类时主动推荐另一类。
"""


# ==================== 工具函数 ====================

_TOOL_FUNCTIONS: Dict[str, callable] = {}


def _register_tool(func):
    _TOOL_FUNCTIONS[func.__name__] = func
    return func


@_register_tool
async def list_knowledge_files() -> Dict:
    """查看知识库文件列表"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/knowledge/files")
    return r.json()


@_register_tool
async def sync_knowledge_base() -> Dict:
    """同步知识库到向量库"""
    client = _get_http_client()
    r = await client.post("http://localhost:8000/admin/knowledge/sync",
                          data={"user_id": "admin", "recreate": True})
    return r.json()


@_register_tool
async def delete_knowledge_file(filename: str) -> Dict:
    """删除知识库文件"""
    client = _get_http_client()
    r = await client.delete(f"http://localhost:8000/admin/knowledge/files/{filename}")
    return r.json()


@_register_tool
async def list_questions(question_type: str = "", topic: str = "",
                         difficulty: str = "", keyword: str = "",
                         page: int = 1) -> Dict:
    """列出题目"""
    client = _get_http_client()
    params = {"page": page, "page_size": 10}
    if question_type: params["question_type"] = question_type
    if topic: params["topic"] = topic
    if difficulty: params["difficulty"] = difficulty
    if keyword: params["keyword"] = keyword
    url = "http://localhost:8000/admin/questions"
    if question_type == "theory":
        url = "http://localhost:8000/admin/theory-questions"
    elif question_type == "practice":
        url = "http://localhost:8000/admin/practice-questions"
    r = await client.get(url, params=params)
    return r.json()


@_register_tool
async def add_question(topic: str, difficulty: int, content: str,
                       solution: str = "", title: str = "",
                       knowledge_points: str = "",
                       sub_topic: str = "") -> Dict:
    """新增题目"""
    client = _get_http_client()
    body = {
        "topic": topic, "difficulty": difficulty,
        "content": content, "solution": solution,
        "title": title, "sub_topic": sub_topic,
        "knowledge_points": [k.strip() for k in knowledge_points.split(",") if k.strip()]
    }
    r = await client.post("http://localhost:8000/admin/questions", json=body)
    return r.json()


@_register_tool
async def delete_question(qid: str) -> Dict:
    """删除题目"""
    client = _get_http_client()
    r = await client.delete(f"http://localhost:8000/admin/questions/{qid}")
    return r.json()


@_register_tool
async def get_question_detail(qid: str) -> Dict:
    """查看题目详情"""
    client = _get_http_client()
    r = await client.get(f"http://localhost:8000/admin/questions/{qid}")
    return r.json()


@_register_tool
async def list_videos(topic: str = "", difficulty: str = "",
                      keyword: str = "", page: int = 1) -> Dict:
    """列出视频（数据库中的视频记录）"""
    client = _get_http_client()
    params = {"page": page, "page_size": 10}
    if topic: params["topic"] = topic
    if difficulty: params["difficulty"] = difficulty
    if keyword: params["keyword"] = keyword
    r = await client.get("http://localhost:8000/admin/videos", params=params)
    return r.json()


@_register_tool
async def list_video_files() -> Dict:
    """查看媒体素材列表（OSS/本地上传的视频文件，非B站外部链接）"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/video/files")
    return r.json()


@_register_tool
async def delete_video_file(filename: str) -> Dict:
    """删除媒体素材文件"""
    client = _get_http_client()
    r = await client.delete(f"http://localhost:8000/admin/video/files/{filename}")
    return r.json()


# 允许上传的文件目录白名单
_UPLOAD_ALLOWED_DIRS = {
    os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")),
    os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "community_data", "uploads")),
    os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_documents")),
}

_UPLOAD_ALLOWED_EXTENSIONS = {".mp4", ".webm", ".avi", ".mov", ".mkv", ".mp3", ".wav", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


@_register_tool
async def upload_video_file(file_path: str) -> Dict:
    """上传媒体素材文件"""
    client = _get_http_client()
    try:
        abs_path = os.path.normpath(os.path.abspath(file_path))
        
        # 校验文件是否在允许的目录内
        if not any(abs_path.startswith(d + os.sep) or abs_path == d for d in _UPLOAD_ALLOWED_DIRS):
            return {"error": f"文件路径不在允许的上传目录内: {file_path}"}
        
        # 校验文件扩展名
        _, ext = os.path.splitext(abs_path)
        if ext.lower() not in _UPLOAD_ALLOWED_EXTENSIONS:
            return {"error": f"不支持的文件类型: {ext}"}
        
        with open(abs_path, 'rb') as f:
            files = {'file': (os.path.basename(abs_path), f)}
            r = await client.post("http://localhost:8000/admin/video/upload", files=files)
        return r.json()
    except FileNotFoundError:
        return {"error": f"文件不存在: {file_path}"}
    except Exception as e:
        return {"error": str(e)}


@_register_tool
async def add_video(title: str, topic: str, platform: str = "bilibili",
                    difficulty: int = 3, url: str = "",
                    duration_sec: int = 0, knowledge_points: str = "") -> Dict:
    """新增视频"""
    client = _get_http_client()
    body = {
        "title": title, "topic": topic, "platform": platform,
        "difficulty": difficulty, "url": url,
        "duration_sec": duration_sec,
        "knowledge_points": [k.strip() for k in knowledge_points.split(",") if k.strip()]
    }
    r = await client.post("http://localhost:8000/admin/videos", json=body)
    return r.json()


@_register_tool
async def delete_video(vid: str) -> Dict:
    """删除视频"""
    client = _get_http_client()
    r = await client.delete(f"http://localhost:8000/admin/videos/{vid}")
    return r.json()


@_register_tool
async def get_weight_config(category: str) -> Dict:
    """查看权重配置"""
    client = _get_http_client()
    r = await client.get(f"http://localhost:8000/admin/weights/{category}")
    return r.json()


@_register_tool
async def update_weight(category: str, updates_json: str) -> Dict:
    """修改权重配置"""
    client = _get_http_client()
    updates = json.loads(updates_json)
    r = await client.post(f"http://localhost:8000/admin/weights/{category}",
                          json={"updates": updates})
    return r.json()


@_register_tool
async def get_agent_stats() -> Dict:
    """查看 Agent 调用排行和实时状态"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/agent-monitor/stats")
    return r.json()


@_register_tool
async def get_video_detail(vid: str) -> Dict:
    """查看视频详情"""
    client = _get_http_client()
    r = await client.get(f"http://localhost:8000/admin/videos/{vid}")
    return r.json()


@_register_tool
async def update_question(qid: str, topic: str = "", difficulty: int = 0,
                          content: str = "", solution: str = "", title: str = "",
                          knowledge_points: str = "", sub_topic: str = "") -> Dict:
    """更新题目"""
    client = _get_http_client()
    body = {}
    if topic: body["topic"] = topic
    if difficulty > 0: body["difficulty"] = difficulty
    if content: body["content"] = content
    if solution: body["solution"] = solution
    if title: body["title"] = title
    if sub_topic: body["sub_topic"] = sub_topic
    if knowledge_points:
        body["knowledge_points"] = [k.strip() for k in knowledge_points.split(",") if k.strip()]
    r = await client.put(f"http://localhost:8000/admin/questions/{qid}", json=body)
    return r.json()


@_register_tool
async def update_video(vid: str, title: str = "", topic: str = "", platform: str = "",
                       difficulty: int = 0, url: str = "", duration_sec: int = 0,
                       knowledge_points: str = "") -> Dict:
    """更新视频"""
    client = _get_http_client()
    body = {}
    if title: body["title"] = title
    if topic: body["topic"] = topic
    if platform: body["platform"] = platform
    if difficulty > 0: body["difficulty"] = difficulty
    if url: body["url"] = url
    if duration_sec > 0: body["duration_sec"] = duration_sec
    if knowledge_points:
        body["knowledge_points"] = [k.strip() for k in knowledge_points.split(",") if k.strip()]
    r = await client.put(f"http://localhost:8000/admin/videos/{vid}", json=body)
    return r.json()


@_register_tool
async def reset_weights() -> Dict:
    """重置所有权重为默认值"""
    client = _get_http_client()
    r = await client.post("http://localhost:8000/admin/weights/reset")
    return r.json()


@_register_tool
async def get_question_stats() -> Dict:
    """查看题库统计信息"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/questions/stats")
    return r.json()


@_register_tool
async def get_video_stats() -> Dict:
    """查看视频统计信息"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/videos/stats")
    return r.json()


@_register_tool
async def get_topics() -> Dict:
    """获取所有知识点列表"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/questions/topics")
    return r.json()


@_register_tool
async def get_knowledge_stats() -> Dict:
    """查看知识库统计信息"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/knowledge/stats")
    return r.json()


@_register_tool
async def reset_agent_stats() -> Dict:
    """重置 Agent 统计数据"""
    client = _get_http_client()
    r = await client.post("http://localhost:8000/admin/agent-monitor/reset")
    return r.json()


@_register_tool
async def get_global_ranking_weights() -> Dict:
    """查看全局排行榜权重配置"""
    client = _get_http_client()
    r = await client.get("http://localhost:8000/admin/global-ranking/weights")
    return r.json()


@_register_tool
async def update_global_ranking_weights(coding_score: float = 0.30, accuracy_score: float = 0.25,
                                        learning_time_score: float = 0.15, problem_count_score: float = 0.15,
                                        overall_feature_score: float = 0.15) -> Dict:
    """更新全局排行榜权重配置"""
    client = _get_http_client()
    body = {
        "coding_score": coding_score,
        "accuracy_score": accuracy_score,
        "learning_time_score": learning_time_score,
        "problem_count_score": problem_count_score,
        "overall_feature_score": overall_feature_score
    }
    r = await client.post("http://localhost:8000/admin/global-ranking/weights", json=body)
    return r.json()


# ==================== 主处理逻辑 ====================

# Pydantic 模型列表 → bind_tools 自动转为 tool schema
_TOOL_SCHEMAS = [
    ListKnowledgeFilesInput,
    SyncKnowledgeBaseInput,
    DeleteKnowledgeFileInput,
    ListQuestionsInput,
    AddQuestionInput,
    DeleteQuestionInput,
    GetQuestionDetailInput,
    UpdateQuestionInput,
    ListVideosInput,
    ListVideoFilesInput,
    DeleteVideoFileInput,
    UploadVideoFileInput,
    AddVideoInput,
    DeleteVideoInput,
    GetVideoDetailInput,
    UpdateVideoInput,
    GetWeightConfigInput,
    UpdateWeightInput,
    ResetWeightsInput,
    GetQuestionStatsInput,
    GetVideoStatsInput,
    GetTopicsInput,
    GetKnowledgeStatsInput,
    ResetAgentStatsInput,
    GetAgentStatsInput,
    GetGlobalRankingWeightsInput,
    UpdateGlobalRankingWeightsInput,
]


class AdminHelperAgent:
    """管理端协助 Agent（支持 DeepSeek 和 Qwen 模型）"""

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
            raise ImportError("请安装 langchain_deepseek 或 langchain_qwq")

        self.messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    @staticmethod
    def _model_name_to_func_name(model_name: str) -> str:
        """将 Pydantic 模型名称转换为工具函数名称"""
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
                print(f"[DEBUG] Converted tool name: {tool_name} -> {converted_name}")
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

        print(f"[DEBUG] Added tool message with id: {tool_call_id}")
        print(f"[DEBUG] Messages count after adding tool: {len(self.messages)}")

        yield {"type": "tool_result", "tool": final_tool_name, "args": tool_args, "result": result}

    @staticmethod
    def _parse_tool_call_from_content(content: str) -> Optional[Dict]:
        """从 LLM 回复文本中解析工具调用 JSON"""
        import re
        pattern = r'\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"args"\s*:\s*(\{.*?\})\s*\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            tool_name = match.group(1)
            try:
                args = json.loads(match.group(2))
            except json.JSONDecodeError:
                args = {}
            return {"tool": tool_name, "args": args}
        return None

    async def chat(self, user_message: str) -> AsyncGenerator[Dict, None]:
        self.messages.append({"role": "user", "content": user_message})

        max_rounds = 10
        for _ in range(max_rounds):
            try:
                response = await self.llm.ainvoke(self.messages)
            except Exception as e:
                yield {"type": "error", "content": f"LLM 调用失败: {str(e)}"}
                return

            raw_calls = getattr(response, 'tool_calls', None)
            if raw_calls is None:
                raw_calls = response.additional_kwargs.get('tool_calls', [])

            print(f"[DEBUG] Raw tool calls: {raw_calls}")
            print(f"[DEBUG] Response content type: {type(getattr(response, 'content', ''))}")
            print(f"[DEBUG] Response content: {getattr(response, 'content', '')}")
            print(f"[DEBUG] Messages count before processing: {len(self.messages)}")

            if raw_calls:
                response_content = getattr(response, 'content', '')
                if isinstance(response_content, list):
                    response_content = ''.join(str(c) for c in response_content)
                elif response_content is None:
                    response_content = ''

                assistant_msg_dict = {
                    "role": "assistant",
                    "content": response_content,
                    "tool_calls": []
                }

                valid_tool_calls = []
                for tc in raw_calls:
                    tool_name = ""
                    tool_args = {}
                    tool_call_id = ""
                    
                    if isinstance(tc, dict):
                        if 'function' in tc:
                            tool_name = tc['function'].get('name', '')
                            raw_args = tc['function'].get('arguments', '{}')
                            tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                            tool_call_id = tc.get('id', '')
                        elif 'name' in tc:
                            tool_name = tc.get('name', '')
                            tool_args = tc.get('args', {})
                            tool_call_id = tc.get('id', '')
                    else:
                        tool_name = tc.name
                        tool_args = tc.args
                        tool_call_id = tc.id

                    if not tool_name:
                        continue

                    import uuid
                    if not tool_call_id:
                        tool_call_id = f"auto_gen_{uuid.uuid4().hex[:8]}"

                    arguments_str = json.dumps(tool_args, ensure_ascii=False) if isinstance(tool_args, dict) else str(tool_args)
                    valid_tool_calls.append({
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments_str
                        }
                    })

                if not valid_tool_calls:
                    self.messages.append({"role": "assistant", "content": response.content or ""})
                    yield {"type": "answer", "content": response.content}
                    return

                assistant_msg_dict["tool_calls"] = valid_tool_calls
                self.messages.append(assistant_msg_dict)

                print(f"[DEBUG] Added assistant message with {len(valid_tool_calls)} tool calls")
                print(f"[DEBUG] Messages count after adding assistant: {len(self.messages)}")

                for tc in valid_tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args = json.loads(tc["function"]["arguments"])
                    tool_call_id = tc["id"]

                    print(f"[DEBUG] Yielding tool_call: {tool_name}, args: {tool_args}")
                    yield {"type": "tool_call", "tool": tool_name, "args": tool_args}
                    async for ev in self._execute_tool(tool_name, tool_args, tool_call_id):
                        print(f"[DEBUG] Yielding tool_result: {ev}")
                        yield ev

                continue

            parsed = self._parse_tool_call_from_content(response.content or "")
            if parsed:
                import uuid
                tool_call_id = f"content_parsed_{uuid.uuid4().hex[:8]}"
                tool_name = parsed["tool"]
                tool_args = parsed["args"]

                assistant_msg = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [{
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args, ensure_ascii=False)
                        }
                    }]
                }
                self.messages.append(assistant_msg)
                yield {"type": "tool_call", "tool": tool_name, "args": tool_args}
                async for ev in self._execute_tool(tool_name, tool_args, tool_call_id):
                    yield ev
                continue

            self.messages.append({"role": "assistant", "content": response.content or ""})
            yield {"type": "answer", "content": response.content}
            return

        yield {"type": "answer", "content": "操作步骤较多未能完全执行完毕，请继续补充说明。"}


# ==================== 全局实例 ====================

_helper_agent: Optional[AdminHelperAgent] = None


def get_helper_agent() -> AdminHelperAgent:
    global _helper_agent
    if _helper_agent is None:
        _helper_agent = AdminHelperAgent()
    return _helper_agent
