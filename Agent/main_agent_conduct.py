"""
主Agent - Conduct层(执行层)
基于LangGraph实现实时学习任务执行和特征更新
负责:编程练习、题目生成、文档生成、视频搜索、思维导图等
"""

from typing import Dict, Any, List, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import contextvars
import sys
import time

# ==================== 后台任务引用集合 ====================
# 防止 asyncio.create_task() 返回的 Task 被垃圾回收导致任务丢失
_background_tasks: set = set()

def _safe_create_task(coro):
    """安全创建后台任务，保存引用防止 GC 回收"""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

# ==================== 节点状态通知机制 ====================
# 用于向前端SSE流式推送当前正在执行的节点状态
# 由 api_server.py 中的 SSE 端点设置，节点函数写入，前端消费
# ★★★ 使用 ContextVar 而非全局变量，避免多用户并发请求下队列被覆盖 ★★★

_node_status_queue: contextvars.ContextVar = contextvars.ContextVar('node_status_queue', default=None)

def set_node_status_queue(queue: "asyncio.Queue"):
    """设置当前请求的节点状态队列（由SSE端点调用）"""
    _node_status_queue.set(queue)

def clear_node_status_queue():
    """清除当前请求的节点状态队列"""
    _node_status_queue.set(None)

async def _emit_status(node: str, status: str, detail: str = ""):
    """
    发射节点状态事件

    Args:
        node: 节点名称 (如 practice, question_gen, router, integrator)
        status: 状态 (start / complete / error)
        detail: 额外信息
    """
    queue = _node_status_queue.get()
    if queue is not None:
        await queue.put({
            "type": "node_status",
            "node": node,
            "status": status,
            "detail": detail,
            "timestamp": time.time()
        })

# ==================== LLM 思考过程推送 ====================

async def _emit_thinking(node: str, content: str):
    """
    发射 LLM 推理思考文本到 SSE 流

    Args:
        node: 所属节点名称
        content: 思考文本内容（可包含换行）
    """
    queue = _node_status_queue.get()
    if queue is not None:
        await queue.put({
            "type": "thinking",
            "node": node,
            "content": content,
            "timestamp": time.time()
        })


class SSEThinkingCallbackHandler(AsyncCallbackHandler):
    """
    LangChain Callback Handler - 捕获 LLM 推理过程中的 token，
    通过 _emit_thinking 推送到前端 SSE 流。

    使用方式:
        在 _wrap_node 中创建实例并通过 set_llm_callback() 注入上下文，
        get_chat_openai() 自动附加到新创建的 ChatOpenAI 实例。
    """

    def __init__(self, node_name: str):
        self.node_name = node_name
        self._buffer: list[str] = []
        self._buffer_len = 0
        self._flush_threshold = 50  # 每累积 50 个字符推送一次

    async def on_chat_model_start(self, serialized: Dict[str, Any], messages: List[List], **kwargs):
        """Chat 模型开始推理时，推送 prompt 摘要（兼容 ChatOpenAI）"""
        prompt_text = ""
        try:
            msg_list = messages[0] if messages else []
            for msg in msg_list:
                if hasattr(msg, 'content'):
                    prompt_text += str(msg.content) + "\n"
        except Exception:
            prompt_text = str(messages)[:300]
        if len(prompt_text) > 300:
            prompt_text = prompt_text[:300] + "..."
        lines = prompt_text.split("\n")
        if len(lines) > 15:
            prompt_text = "\n".join(lines[:15]) + "\n..."
        await _emit_thinking(self.node_name, f"[LLM 开始推理]\n输入:\n{prompt_text}")

    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """LLM 开始推理时，推送 prompt 摘要"""
        # prompts 是消息模板列表，取第一个的前 300 字
        prompt_text = str(prompts[0]) if prompts else ""
        if len(prompt_text) > 300:
            prompt_text = prompt_text[:300] + "..."
        # 按行裁剪，只保留前 15 行
        lines = prompt_text.split("\n")
        if len(lines) > 15:
            prompt_text = "\n".join(lines[:15]) + "\n..."
        await _emit_thinking(self.node_name, f"[LLM 开始推理]\n输入:\n{prompt_text}")

    async def on_llm_new_token(self, token: str, **kwargs):
        """收到新 token，累积到缓冲区"""
        self._buffer.append(token)
        self._buffer_len += len(token)
        if self._buffer_len >= self._flush_threshold:
            content = "".join(self._buffer)
            await _emit_thinking(self.node_name, content)
            self._buffer.clear()
            self._buffer_len = 0

    async def on_llm_end(self, response, **kwargs):
        """LLM 推理完成，冲刷剩余缓冲区"""
        if self._buffer:
            content = "".join(self._buffer)
            await _emit_thinking(self.node_name, content)
            self._buffer.clear()
            self._buffer_len = 0
        await _emit_thinking(self.node_name, "[LLM 推理完成]")

    async def on_llm_error(self, error: Exception, **kwargs):
        """LLM 推理错误"""
        content = "".join(self._buffer) if self._buffer else ""
        msg = f"[LLM 错误] {error}"
        if content:
            msg = content + "\n" + msg
        await _emit_thinking(self.node_name, msg)
        self._buffer.clear()
        self._buffer_len = 0

# 导入Conduct层的所有子Agent
from Agent.children_agent.practice_agent import PracticeAgent
from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent
from Agent.children_agent.course_doc_agent_ali import CourseDocAgent
from Agent.children_agent.extension_reading_agent import ExtensionReadingAgent
from Agent.children_agent.video_search_agent import VideoSearchAgent
from Agent.children_agent.mindmap_agent import MindMapAgent
from Agent.children_agent.study_plan_agent import StudyPlanAgent
from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
from Agent.children_agent.ppt_agent import PPTCreationAgent
from Agent.children_agent.judge_agent import JudgeAgent
from utils.llm_config import set_llm_callback, get_chat_openai


# ==================== 状态定义 ====================

class ConductState(TypedDict):
    """
    Conduct层的状态定义
    """
    # 输入数据
    user_id: str                    # 用户ID
    user_input: str                 # 用户输入/问题
    
    # 学生特征(从中央管理器获取)
    student_features: Optional[Dict[str, Any]]
    
    # 任务类型
    task_type: str                  # practice/question_gen/doc/extension/video/mindmap
    
    # 各Agent执行结果
    practice_result: Optional[Dict[str, Any]]
    question_result: Optional[Dict[str, Any]]
    doc_result: Optional[Dict[str, Any]]
    extension_result: Optional[Dict[str, Any]]
    video_result: Optional[Dict[str, Any]]
    mindmap_result: Optional[Dict[str, Any]]
    animation_result: Optional[Dict[str, Any]]  # ★★★ 动画生成结果
    knowledge_result: Optional[Dict[str, Any]]  # ★★★ 知识库问答结果
    study_plan_result: Optional[Dict[str, Any]]  # ★★★ 学习路径规划结果
    ppt_result: Optional[Dict[str, Any]]  # ★★★ PPT生成结果
    judge_result: Optional[Dict[str, Any]]  # ★★★ 代码评判结果
    
    # 控制流
    next_node: str                  # 下一个执行的节点
    execution_log: List[str]        # 执行日志
    
    # TTS语音合成开关
    enable_tts: bool
    
    # 用户确认覆盖采纳建议
    confirmed: bool
    override_suggestions: bool
    
    # 学习计划焦点参数
    ignore_weak_points: bool
    focus_weak_points: bool
    
    # 最终输出
    final_result: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # 方案配置
    plan_config: Optional[Dict[str, Any]]  # ★★★ 用户选择的学习方案配置
    plan_context: Optional[str]            # ★★★ 方案上下文字段（供LLM Prompt拼接）


# ==================== 节点函数 ====================

def create_practice_node(practice_agent: PracticeAgent, feature_updater: DynamicFeatureUpdater):
    """创建编程练习节点(异步)"""
    async def practice_node(state: ConductState) -> ConductState:
        print("\n💻 [Conduct节点] 编程练习Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [练习] 已临时禁用全局缓存，SSE 直连 LLM")

        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback ★★★
        practice_agent.llm = practice_agent._initialize_llm()
        await _emit_thinking("practice", "开始编程练习生成任务")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            confirmed = state.get("confirmed", False)
            override_suggestions = state.get("override_suggestions", False)
            
            # 获取最新学生特征（异步，避免阻塞事件循环）
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            # ★★★ 先查库，避免每次调LLM ★★★
            existing = _try_find_existing("practice", user_input, user_id)
            if existing:
                print(f"  ✅ [查库] 直接使用已有题目: {existing.get('title', '')}")
                await _emit_thinking("practice", "命中题库缓存，直接使用已有题目")
                problem = existing
            else:
                await _emit_thinking("practice", "未命中缓存，正在调用LLM生成编程练习题")
                problem = await practice_agent.generate_problem_async(user_input, user_id, confirmed=confirmed, override_suggestions=override_suggestions)
            
            if problem:
                result = {
                    "status": "success",
                    "type": "generate_practice",
                    "problem": problem,
                    "student_features": features
                }
                print(f"✅ 练习题生成完成: {problem.get('title', 'N/A')}")
                await _emit_thinking("practice", f"练习题生成完成: {problem.get('title', '')}")
            else:
                result = {
                    "status": "error",
                    "type": "generate_practice",
                    "message": "练习题生成失败"
                }
                await _emit_thinking("practice", "练习题生成失败")
            
            return {
                **state,
                "practice_result": result,
                "student_features": features,
                "execution_log": state.get("execution_log", []) + ["practice"]
            }
        except Exception as e:
            print(f"❌ 编程练习节点失败: {e}")
            await _emit_thinking("practice", f"编程练习生成失败: {str(e)}")
            return {
                **state,
                "error": f"编程练习失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["practice"]
            }
        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [练习] 已恢复全局缓存")

    return practice_node


def create_question_gen_node(question_agent: QuestionGeneratorAgent, feature_updater: DynamicFeatureUpdater):
    """创建理论题生成节点(异步)"""
    async def question_gen_node(state: ConductState) -> ConductState:
        print("\n📝 [Conduct节点] 理论题生成Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [理论题] 已临时禁用全局缓存，SSE 直连 LLM")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            # ★★★ 先查库，避免每次调LLM ★★★
            existing = _try_find_existing("question", user_input, user_id)
            if existing:
                print(f"  ✅ [查库] 直接使用已有理论题（{len([k for k in existing if k != 'source'])}种题型）")
                await _emit_thinking("question_gen", "命中题库缓存，跳过LLM调用")
                questions = existing
            else:
                await _emit_thinking("question_gen", "未命中缓存，正在构建学生画像并调用LLM生成理论题")
                info = {
                    "major": features.get("academic_background", {}).get("major_preference", "计算机") if features else "计算机",
                    "course_name": user_input,
                    "weak_points": "",
                    "learn_level": "medium",
                    "user_input": user_input,
                    "student_feature": features or {},
                    "user_id": user_id
                }
                questions = await question_agent.generate_all_questions_async(info, state.get("enable_tts", False))
            
            result = {
                "status": "success",
                "type": "generate_theory_questions",
                "questions": questions,
                "student_features": features
            }
            
            print(f"✅ 理论题生成完成")
            await _emit_thinking("question_gen", "理论题生成完成")
            
            return {
                **state,
                "question_result": result,
                "student_features": features,
                "execution_log": state.get("execution_log", []) + ["question_gen"]
            }
        except Exception as e:
            print(f"❌ 理论题生成节点失败: {e}")
            await _emit_thinking("question_gen", f"理论题生成失败: {str(e)}")
            return {
                **state,
                "error": f"理论题生成失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["question_gen"]
            }
    
    return question_gen_node


def create_doc_gen_node(doc_agent: CourseDocAgent, feature_updater: DynamicFeatureUpdater):
    """创建文档生成节点(异步)"""
    async def doc_gen_node(state: ConductState) -> ConductState:
        print("\n📄 [Conduct节点] 课程文档Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [文档] 已临时禁用全局缓存，SSE 直连 LLM")

        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback ★★★
        doc_agent.llm = doc_agent._initialize_llm()
        await _emit_thinking("doc_gen", "开始课程文档生成任务")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None
            
            # ★★★ 先查库，避免每次调LLM ★★★
            existing = _try_find_existing("doc", user_input, user_id)
            if existing:
                print(f"  ✅ [查库] 直接使用已有文档: {existing.get('doc_title', '')}")
                await _emit_thinking("doc_gen", "命中缓存，直接使用已有文档")
                doc_data = existing
                updated_features = features
            else:
                await _emit_thinking("doc_gen", "未命中缓存，正在调用LLM生成课程文档")
                student_info = {
                    "major": features.get("academic_background", {}).get("major_preference", "计算机") if features else "计算机",
                    "course_name": user_input,
                    "weak_points": user_input,
                    "learn_level": "medium",
                    "student_feature": features or {}
                }
                
                doc_data = await doc_agent.generate_course_document_async(
                    student_info,
                    user_id=user_id,
                    enable_tts=state.get("enable_tts", False)
                )
                
                if doc_data and user_id and features:
                    # ★★★ 后台异步更新特征，不阻塞文档结果返回 ★★★
                    _safe_create_task(
                        feature_updater.update_features_async(
                            current_features=features,
                            task_type="document_reading",
                            task_content=user_input,
                            performance_data={
                                "reading_time": "5分钟",
                                "pages_read": 1,
                                "doc_title": doc_data.get("doc_title", ""),
                            },
                            completion_quality="good",
                            user_id=user_id
                        )
                    )
                    print(f"✅ 文档生成后特征更新已异步触发（不阻塞）")
                
                updated_features = features
            
            result = {
                "status": "success" if doc_data else "error",
                "type": "generate_document",
                "document": doc_data,
                "student_features": updated_features
            }
            
            print(f"✅ 文档生成完成")
            
            return {
                **state,
                "doc_result": result,
                "student_features": updated_features,
                "execution_log": state.get("execution_log", []) + ["doc_gen"]
            }
        except Exception as e:
            print(f"❌ 文档生成节点失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"文档生成失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["doc_gen"]
            }
        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [文档] 已恢复全局缓存")

    return doc_gen_node


def create_extension_node(extension_agent: ExtensionReadingAgent, feature_updater: DynamicFeatureUpdater):
    """创建拓展阅读节点(异步)"""
    async def extension_node(state: ConductState) -> ConductState:
        print("\n📚 [Conduct节点] 拓展阅读Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [拓展阅读] 已临时禁用全局缓存，SSE 直连 LLM")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            info = {
                "major": features.get("academic_background", {}).get("major_preference", "计算机") if features else "计算机",
                "course_name": user_input,
                "weak_points": "",
                "learn_level": "medium",
                "user_input": user_input,
                "student_feature": features or {},
                "user_id": user_id
            }
            
            # ★★★ 先查库，避免每次调LLM ★★★
            existing = _try_find_existing("extension", user_input, user_id)
            if existing:
                print(f"  ✅ [查库] 直接使用已有拓展材料: {existing.get('doc_title', '')}")
                await _emit_thinking("extension", "命中缓存，直接使用已有拓展阅读材料")
                reading_material = existing
                updated_features = features
            else:
                await _emit_thinking("extension", "未命中缓存，正在调用LLM生成拓展阅读材料")
                reading_material = await extension_agent.generate_reading_material_async(info, state.get("enable_tts", False))
            
            if reading_material and user_id and features and not existing:
                # ★★★ 后台异步更新特征，不阻塞拓展阅读结果返回 ★★★
                _safe_create_task(
                    feature_updater.update_features_async(
                        current_features=features,
                        task_type="extension_reading",
                        task_content=user_input,
                        performance_data={
                            "reading_time": "8分钟",
                            "completion_rate": 0.8,
                            "topics_explored": [user_input],
                        },
                        completion_quality="good",
                        user_id=user_id
                    )
                )
                print(f"✅ 扩展阅读后特征更新已异步触发（不阻塞）")
            
            updated_features = features
            
            result = {
                "status": "success",
                "type": "generate_extension",
                "reading_material": reading_material,
                "student_features": updated_features  # ★★★ 使用更新后的特征 ★★★
            }
            
            print(f"✅ 拓展阅读生成完成")
            await _emit_thinking("extension", "拓展阅读生成完成")
            
            return {
                **state,
                "extension_result": result,
                "student_features": updated_features,  # ★★★ 返回更新后的特征 ★★★
                "execution_log": state.get("execution_log", []) + ["extension"]
            }
        except Exception as e:
            print(f"❌ 拓展阅读节点失败: {e}")
            await _emit_thinking("extension", f"拓展阅读生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"拓展阅读生成失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["extension"]
            }
        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [拓展阅读] 已恢复全局缓存")

    return extension_node


def create_video_node(video_agent: VideoSearchAgent, feature_updater: DynamicFeatureUpdater):
    """创建视频搜索节点(异步)"""
    async def video_node(state: ConductState) -> ConductState:
        print("\n🎬 [Conduct节点] 视频搜索Agent执行中...")

        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback ★★★
        video_agent.llm = video_agent._initialize_llm()

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            # ★★★ 先查库，避免每次调LLM ★★★
            existing = _try_find_existing("video", user_input, user_id)
            if existing:
                print(f"  ✅ [查库] 直接使用已有视频: {len(existing.get('videos', []))}个")
                result = existing
                updated_features = features
            else:
                result = await video_agent.search_videos_for_question_async(
                    user_question=user_input,
                    top_k=3,
                    student_features=features,
                    user_id=user_id
                )
            
            if result and result.get('videos') and user_id and features and not existing:
                # ★★★ 后台异步更新特征，不阻塞视频搜索返回 ★★★
                _safe_create_task(
                    feature_updater.update_features_async(
                        current_features=features,
                        task_type="video_search",
                        task_content=user_input,
                        performance_data={
                            "video_count": len(result['videos']),
                            "first_video_title": result['videos'][0].get('title', ''),
                        },
                        completion_quality="good",
                        user_id=user_id
                    )
                )
                print(f"✅ 视频搜索后特征更新已异步触发（不阻塞）")
            
            updated_features = features
            
            result["type"] = "search_video"
            result["student_features"] = updated_features

            # ★★★ 视频搜索成功，巩固管道将在用户看完视频后通过播放器弹窗触发 ★★★
            # 前端播放器弹窗参考: templates/agent_test.html 中的 showQuizModal 和 startQuiz
            # API 端点: api_server.py 中的 /video/trigger-quiz（看完视频后调用）

            # ★★★ YOLO 联动标记：前端看到此标记应启动摄像头实时情绪检测 ★★★
            # 开启方式：前端打开摄像头 → WebRTC → YOLO情绪识别 → 更新 emotional_state 维度
            if user_id and result.get('videos'):
                result["yolo_monitoring"] = {
                    "enable": True,
                    "mode": "emotion_tracking",
                    "message": "观看视频时开启摄像头实时监测学习状态",
                    "webrtc_port": 8081,  # YOLO WebRTC 服务端口
                }

            print(f"✅ 视频搜索完成,找到 {len(result.get('videos', []))} 个视频")
            
            return {
                **state,
                "video_result": result,
                "student_features": updated_features,
                "execution_log": state.get("execution_log", []) + ["video"]
            }
        except Exception as e:
            print(f"❌ 视频搜索节点失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"视频搜索失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["video"]
            }
    
    return video_node


def create_mindmap_node(mindmap_agent: MindMapAgent, feature_updater: DynamicFeatureUpdater):
    """创建思维导图节点(异步)"""
    async def mindmap_node(state: ConductState) -> ConductState:
        print("\n🧠 [Conduct节点] 思维导图Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [思维导图] 已临时禁用全局缓存，SSE 直连 LLM")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            await _emit_thinking("mindmap", "正在构建学生画像并生成思维导图JSON")
            info = {
                "major": features.get("academic_background", {}).get("major_preference", "计算机") if features else "计算机",
                "course_name": user_input,
                "weak_points": "",
                "learn_level": "medium",
                "student_feature": features or {},
                "user_id": user_id
            }
            
            mindmap_json = await mindmap_agent.generate_mindmap_json_async(info, state.get("enable_tts", False))
            
            if mindmap_json and user_id and features:
                # ★★★ 后台异步更新特征，不阻塞思维导图结果返回 ★★★
                asyncio.create_task(
                    feature_updater.update_features_async(
                        current_features=features,
                        task_type="mindmap_creation",
                        task_content=user_input,
                        performance_data={
                            "node_count": len(str(mindmap_json).split('children')),
                            "depth_level": 3,
                            "time_spent": "15分钟",
                        },
                        completion_quality="good",
                        user_id=user_id
                    )
                )
                print(f"✅ 思维导图生成后特征更新已异步触发（不阻塞）")
            
            updated_features = features
            
            result = {
                "status": "success",
                "type": "generate_mindmap",
                "mindmap": mindmap_json,
                "student_features": updated_features
            }
            
            print(f"✅ 思维导图生成完成")
            await _emit_thinking("mindmap", "思维导图生成完成")
            
            return {
                **state,
                "mindmap_result": result,
                "student_features": updated_features,
                "execution_log": state.get("execution_log", []) + ["mindmap"]
            }
        except Exception as e:
            print(f"❌ 思维导图节点失败: {e}")
            await _emit_thinking("mindmap", f"思维导图生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"思维导图生成失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["mindmap"]
            }
        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [思维导图] 已恢复全局缓存")

    return mindmap_node


def create_animation_node(animation_agent):
    """创建动画生成节点(异步)"""
    async def animation_node(state: ConductState) -> ConductState:
        print("\n🎨 [Conduct节点] 动画生成Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [动画] 已临时禁用全局缓存，SSE 直连 LLM")

        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback ★★★
        animation_agent.llm = animation_agent._initialize_llm()
        await _emit_thinking("animation", "开始动画生成任务")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            await _emit_thinking("animation", f"正在为用户 {user_id} 生成主题为「{user_input}」的教育动画")

            from .children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            feature_updater = DynamicFeatureUpdater()
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            if features:
                print(f"✅ 已获取用户 {user_id} 的最新特征")
            else:
                print(f"⚠️ 未找到用户 {user_id} 的特征，将使用默认值")

            await _emit_thinking("animation", "正在调用LLM生成动画HTML内容")
            result = await animation_agent.generate_animation(
                topic=user_input,
                user_id=user_id,
                enable_tts=True
            )
            
            print(f"✅ 动画生成完成")
            await _emit_thinking("animation", "动画HTML生成完成")

            updated_features = features
            if result.get("status") == "success" and user_id and features:
                # ★★★ 后台异步更新特征，不阻塞结果返回 ★★★
                from .children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                feature_updater = DynamicFeatureUpdater()

                creation_data = {
                    "animation_complexity": "medium",
                    "visual_elements": len(result.get('html', '').split('<div')),
                    "time_spent": "10分钟",
                    "creativity_score": 75,
                    "technical_quality": "good"
                }

                _safe_create_task(
                    feature_updater.update_features_async(
                        current_features=features,
                        task_type="animation_generation",
                        task_content=user_input,
                        performance_data=creation_data,
                        completion_quality="medium",
                        time_spent="10分钟",
                        user_id=user_id
                    )
                )
                print(f"✅ 动画生成后特征更新已异步触发（不阻塞）")
            
            return {
                **state,
                "animation_result": result,
                "student_features": updated_features,
                "execution_log": state.get("execution_log", []) + ["animation"]
            }
        except Exception as e:
            print(f"❌ 动画生成节点失败: {e}")
            await _emit_thinking("animation", f"动画生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"动画生成失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["animation"]
            }
    
    return animation_node


# ==================== 节点状态包装器 ====================

def _wrap_node(node_name: str, node_func):
    """
    包装节点函数，自动在节点执行前后发射状态事件，
    并上报 AgentMonitor 调用统计。
    
    用于 _build_workflow 中包装所有执行节点，
    使前端SSE能实时感知当前正在执行的节点。
    """
    async def wrapped(state: ConductState) -> ConductState:
        task_type = state.get("task_type", "")
        user_id = state.get("user_id", "")
        detail = f"task_type={task_type}"
        await _emit_status(node_name, "start", detail)

        # ★★★ 上报 AgentMonitor：调用开始 ★★★
        try:
            from Agent.agent_monitor import report_call_start
            report_call_start(node_name, user_id, task_type)
        except Exception:
            pass

        # ★★★ 创建 SSE LLM callback handler 并注入上下文，
        # get_chat_openai() 自动附加到新创建的 LLM 实例，
        # 实现 LLM 推理过程的逐词 token 推送 ★★★
        handler = SSEThinkingCallbackHandler(node_name)
        set_llm_callback(handler)

        try:
            result = await node_func(state)
            if result.get("error"):
                await _emit_status(node_name, "error", str(result["error"]))
            else:
                await _emit_status(node_name, "complete")
            return result
        except Exception as e:
            await _emit_status(node_name, "error", str(e))
            # ★★★ 标记异常状态，供 finally 块判断 ★★★
            state["_node_exception"] = True
            raise
        finally:
            # ★★★ 清除 callback handler，避免影响后续请求 ★★★
            set_llm_callback(None)
            # ★★★ 上报 AgentMonitor：调用结束 ★★★
            try:
                from Agent.agent_monitor import report_call_end
                success = state.get("_node_exception", False) is False and state.get("error") is None
                report_call_end(node_name, success)
            except Exception:
                pass

    return wrapped


def create_study_plan_node(study_plan_agent):
    """创建学习路径规划节点(异步)"""
    async def study_plan_node(state: ConductState) -> ConductState:
        print("\n📋 [Conduct节点] 学习路径规划Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [学习规划] 已临时禁用全局缓存，SSE 直连 LLM")

        try:
            # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback ★★★
            study_plan_agent.llm = study_plan_agent._initialize_llm()
            await _emit_thinking("study_plan", "开始学习路径规划任务")

            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")

            from .children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            feature_updater = DynamicFeatureUpdater()
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            await _emit_thinking("study_plan", "正在分析用户画像与学习需求")

            # ★★★ 提取并传递焦点参数（避免二次弹窗）★★★
            ignore_weak_points = state.get("ignore_weak_points", False)
            focus_weak_points = state.get("focus_weak_points", False)

            result = await study_plan_agent.generate_plan_async(
                user_input=user_input,
                user_id=user_id,
                ignore_weak_points=ignore_weak_points,
                focus_weak_points=focus_weak_points
            )

            if result.get("status") == "weak_points_detected":
                await _emit_thinking("study_plan", f"检测到薄弱环节，等待用户确认是否针对性制定计划")
                return {
                    **state,
                    "study_plan_result": result,
                    "student_features": features,
                    "execution_log": state.get("execution_log", []) + ["study_plan"]
                }

            if result.get("status") == "success":
                plan = result.get("plan", {})
                phases = plan.get("phases", [])
                title = plan.get("title", "未命名计划")
                await _emit_thinking(
                    "study_plan",
                    f"学习计划已生成: 「{title}」，共 {len(phases)} 个阶段"
                )

                updated_features = features
                if user_id and features:
                    # ★★★ 后台异步更新特征，不阻塞结果返回 ★★★
                    _safe_create_task(
                        feature_updater.update_features_async(
                            current_features=features,
                            task_type="learning_planning",
                            task_content=user_input,
                            performance_data={
                                "plan_generated": True,
                                "plan_title": title,
                                "phases_count": len(phases),
                            },
                            completion_quality="good",
                            time_spent="5分钟",
                            user_id=user_id
                        )
                    )
                    print(f"✅ 学习规划特征更新已异步触发（不阻塞）")

                return {
                    **state,
                    "study_plan_result": result,
                    "student_features": updated_features,
                    "execution_log": state.get("execution_log", []) + ["study_plan"]
                }

            # 其他状态（如 error）
            await _emit_thinking("study_plan", f"学习计划生成异常: {result.get('message', '未知错误')}")
            return {
                **state,
                "study_plan_result": result,
                "student_features": features,
                "execution_log": state.get("execution_log", []) + ["study_plan"]
            }

        except Exception as e:
            print(f"❌ 学习路径规划节点失败: {e}")
            await _emit_thinking("study_plan", f"学习路径规划失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"学习路径规划失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["study_plan"]
            }

        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [学习规划] 已恢复全局缓存")

    return study_plan_node


def create_ppt_node(ppt_agent):
    """创建PPT生成节点(异步)"""
    async def ppt_node(state: ConductState) -> ConductState:
        print("\n📽️ [Conduct节点] PPT生成Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [PPT] 已临时禁用全局缓存，SSE 直连 LLM")

        try:
            user_id = state.get("user_id", "")
            user_input = state.get("user_input", "")
            await _emit_thinking("ppt", f"正在为用户 {user_id} 生成主题为「{user_input}」的PPT")

            from .children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            feature_updater = DynamicFeatureUpdater()
            features = await feature_updater.get_latest_features_async(user_id) if user_id else None

            if features:
                print(f"✅ 已获取用户 {user_id} 的最新特征")
            else:
                print(f"⚠️ 未找到用户 {user_id} 的特征，将使用默认值")

            await _emit_thinking("ppt", "正在调用PPT生成流水线（大纲→配色→图片→视频→合成）")
            result = await ppt_agent.generate_ppt_async(topic=user_input, user_id=user_id)
            await _emit_thinking("ppt", f"PPT生成完成: {result.get('page_count', 0)}页")

            updated_features = features
            if result.get("status") == "success" and user_id and features:
                # ★★★ 后台异步更新特征，不阻塞 PPT 结果返回 ★★★
                creation_data = {
                    "ppt_topic": user_input,
                    "page_count": result.get("page_count", 4),
                    "ppt_style": result.get("style", "新中式科技风"),
                    "time_spent": "10分钟",
                    "creativity_score": 75,
                    "technical_quality": "good"
                }
                _safe_create_task(
                    feature_updater.update_features_async(
                        current_features=features,
                        task_type="ppt_generation",
                        task_content=user_input,
                        performance_data=creation_data,
                        completion_quality="good",
                        time_spent="10分钟",
                        user_id=user_id
                    )
                )
                print(f"✅ PPT生成后特征更新已异步触发（不阻塞）")

            return {
                **state,
                "ppt_result": result,
                "student_features": updated_features,
                "execution_log": state.get("execution_log", []) + ["ppt"]
            }
        except Exception as e:
            print(f"❌ PPT生成节点失败: {e}")
            await _emit_thinking("ppt", f"PPT生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"PPT生成失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["ppt"]
            }
        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [PPT] 已恢复全局缓存")

    return ppt_node


def create_judge_node(judge_agent: JudgeAgent):
    """创建代码评判节点(异步)"""
    async def judge_node(state: ConductState) -> ConductState:
        print("\n🔍 [Conduct节点] 代码评判Agent执行中...")

        # ★★★ SSE 流式生成期间禁用全局缓存，避免 Redis 拦截直接返回旧结果 ★★★
        from langchain_core.globals import get_llm_cache, set_llm_cache
        _saved_cache = get_llm_cache()
        set_llm_cache(None)
        print("  🧹 [评判] 已临时禁用全局缓存，SSE 直连 LLM")

        try:
            user_input = state.get("user_input", "")

            await _emit_thinking("judge", "正在分析用户提交的代码...")
            judge_result = await judge_agent.debug_code_async(user_input)

            if judge_result:
                has_error = judge_result.get("has_error", False)
                error_type = judge_result.get("error_type", "未知")
                print(f"✅ 代码评判完成: 存在错误={has_error}, 类型={error_type}")
                await _emit_thinking("judge", f"代码评判完成: {'发现问题' if has_error else '未发现明显错误'}")
                result = {
                    "status": "success",
                    "type": "judge_code",
                    "judge_result": judge_result
                }
            else:
                print("❌ 代码评判生成失败")
                await _emit_thinking("judge", "代码评判生成失败")
                result = {
                    "status": "error",
                    "type": "judge_code",
                    "message": "代码评判生成失败"
                }

            return {
                **state,
                "judge_result": result,
                "execution_log": state.get("execution_log", []) + ["judge"]
            }
        except Exception as e:
            print(f"❌ 代码评判节点失败: {e}")
            await _emit_thinking("judge", f"代码评判失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"代码评判失败: {str(e)}",
                "execution_log": state.get("execution_log", []) + ["judge"]
            }
        finally:
            set_llm_cache(_saved_cache)
            print("  🔄 [评判] 已恢复全局缓存")

    return judge_node


async def router_node(state: ConductState) -> ConductState:
    """
    路由决策节点 - 根据task_type和状态分发到对应Agent
    
    与Des层不同,Conduct层的路由更简单:
    - task_type在调用时已确定
    - 不需要复杂的状态检查
    - 直接映射到对应节点
    """
    print("\n🔀 [Conduct路由] 决策中...")
    await _emit_thinking("router", f"开始路由决策，当前任务类型: {state.get('task_type', 'unknown')}")
    
    # ★★★ 读取方案配置，注入到 state ★★★
    from utils.plan_config import get_plan_config, get_plan_context_text
    _user_id = state.get("user_id", "")
    _plan_config = get_plan_config(_user_id)
    _plan_context = get_plan_context_text(_user_id) if _plan_config else ""
    if _plan_config:
        print(f"📋 [方案配置] {_plan_context}")
    
    task_type = state.get("task_type", "")
    execution_log = state.get("execution_log", [])
    error = state.get("error")
    
    # 如果之前有错误,直接跳到integrator
    if error:
        print(f"⚠️  检测到错误,跳过执行直接整合")
        await _emit_thinking("router", f"检测到错误状态，跳过执行直接整合")
        next_node = "integrator"
        await _emit_status("router", "complete", f"error_detected→integrator")
    
    # 根据task_type路由到对应节点
    elif task_type == "practice":
        next_node = "practice"
        print(f"✅ 路由决策: task_type={task_type} → practice节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 practice 节点")
        await _emit_status("router", "complete", f"→practice")

    elif task_type == "judge_code":
        next_node = "judge"
        print(f"✅ 路由决策: task_type={task_type} → judge节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 judge 节点")
        await _emit_status("router", "complete", f"→judge")
    
    elif task_type == "question_gen":
        next_node = "question_gen"
        print(f"✅ 路由决策: task_type={task_type} → question_gen节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 question_gen 节点")
        await _emit_status("router", "complete", f"→question_gen")
    
    elif task_type == "doc_gen":
        next_node = "doc_gen"
        print(f"✅ 路由决策: task_type={task_type} → doc_gen节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 doc_gen 节点")
        await _emit_status("router", "complete", f"→doc_gen")
    
    elif task_type == "extension":
        next_node = "extension"
        print(f"✅ 路由决策: task_type={task_type} → extension节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 extension 节点")
        await _emit_status("router", "complete", f"→extension")
    
    elif task_type == "video":
        next_node = "video"
        print(f"✅ 路由决策: task_type={task_type} → video节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 video 节点")
        await _emit_status("router", "complete", f"→video")
    
    elif task_type == "mindmap":
        next_node = "mindmap"
        print(f"✅ 路由决策: task_type={task_type} → mindmap节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 mindmap 节点")
        await _emit_status("router", "complete", f"→mindmap")
    
    elif task_type == "animation":  # ★★★ 动画生成
        next_node = "animation"
        print(f"✅ 路由决策: task_type={task_type} → animation节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 animation 节点")
        await _emit_status("router", "complete", f"→animation")
    
    elif task_type == "study_plan":  # ★★★ 学习路径规划
        next_node = "study_plan"
        print(f"✅ 路由决策: task_type={task_type} → study_plan节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 study_plan 节点")
        await _emit_status("router", "complete", f"→study_plan")

    elif task_type == "ppt":  # ★★★ PPT生成
        next_node = "ppt"
        print(f"✅ 路由决策: task_type={task_type} → ppt节点")
        await _emit_thinking("router", f"任务类型 {task_type} → 路由到 ppt 节点")
        await _emit_status("router", "complete", f"→ppt")

    # elif task_type == "knowledge_query":  # ★★★ 知识库问答（暂未实现）
    #     next_node = "knowledge_query"
    #     print(f"✅ 路由决策: task_type={task_type} → knowledge_query节点")
    
    else:
        # 未知任务类型,返回错误
        print(f"❌ 未知任务类型: {task_type}")
        await _emit_thinking("router", f"未知任务类型: {task_type}，路由到 integrator")
        next_node = "integrator"
        state["error"] = f"不支持的任务类型: {task_type}"
        await _emit_status("router", "error", f"unknown_task:{task_type}")
    
    return {
        **state,
        "next_node": next_node,
        "plan_config": _plan_config,
        "plan_context": _plan_context,
        "execution_log": execution_log + ["router"]
    }


async def integrator_node(state: ConductState) -> ConductState:
    """结果整合节点 + 持久化保存 + 工作记忆写回"""
    print("\n📦 [Conduct整合] 整合结果中...")
    await _emit_thinking("integrator", "开始整合所有节点的执行结果")
    
    error = state.get("error")
    user_id = state.get("user_id")
    task_type = state.get("task_type")

    doc_result = state.get("doc_result", {})
    practice_result = state.get("practice_result", {})
    question_result = state.get("question_result", {})
    extension_result = state.get("extension_result", {})
    video_result = state.get("video_result", {})
    mindmap_result = state.get("mindmap_result", {})
    animation_result = state.get("animation_result", {})
    study_plan_result = state.get("study_plan_result", {})
    ppt_result = state.get("ppt_result", {})
    judge_result = state.get("judge_result", {})
    
    loop = asyncio.get_running_loop()

    if error:
        await _emit_thinking("integrator", f"检测到错误，结果为错误状态: {error}")
        final_result = {
            "status": "error",
            "error": error,
            "layer": "conduct"
        }
    else:
        # ✅ 收集所有结果,展开嵌套结构
        final_result = {
            "status": "success",
            "layer": "conduct",
            "task_type": task_type,
            "document": doc_result.get("document") if doc_result else None,
            "practice": practice_result.get("problem") if practice_result else None,
            "question": question_result.get("questions") if question_result else None,
            "extension": extension_result.get("reading_material") if extension_result else None,
            "video": video_result.get("videos") if video_result else None,
            "mindmap": mindmap_result.get("mindmap") if mindmap_result else None,
            "animation": animation_result if animation_result else None,  # dict包含html,metadata,resource_id
            "study_plan": study_plan_result.get("plan") if study_plan_result else None,
            "study_plan_status": study_plan_result.get("status") if study_plan_result else None,
            "weak_points_info": study_plan_result.get("weak_points_info") if study_plan_result else None,
            "ppt": ppt_result if ppt_result else None,  # ★★★ PPT生成结果
            "judge": judge_result.get("judge_result") if judge_result else None,  # ★★★ 代码评判结果
            "student_features": state.get("student_features"),
            "metadata": {
                "agents_used": state.get("execution_log", []),
                "raw_results": {
                    "doc_result": doc_result,
                    "practice_result": practice_result,
                    "question_result": question_result,
                    "extension_result": extension_result,
                    "video_result": video_result,
                    "mindmap_result": mindmap_result,
                    "animation_result": animation_result,
                    "study_plan_result": study_plan_result,
                    "ppt_result": ppt_result,  # ★★★ PPT结果
                    "judge_result": judge_result,  # ★★★ 代码评判结果
                }
            }
        }

    # ★★★ 持久化保存 & 工作记忆写回（所有生成类型）★★★
    if user_id:
        try:
            from memory import get_shared_memory_hub
            hub = get_shared_memory_hub()

            if task_type == "practice" and (practice_result or {}).get("status") == "success":
                problem = practice_result.get("problem", {})
                pid = problem.get("problem_id", "")
                if pid:
                    problem["resource_id"] = pid  # ★★★ 回写resource_id ★★★
                    await loop.run_in_executor(None, hub.content.save, user_id, "practice", pid, problem)
                    await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "practice", pid,
                                                   f"题目: {problem.get('title', '')}")
                    await loop.run_in_executor(None, hub.working.add_focus_knowledge, user_id, (problem.get("knowledge_points") or [""])[0])

            elif task_type == "doc_gen" and (doc_result or {}).get("status") == "success":
                doc = doc_result.get("document", {})
                import hashlib
                doc_title = doc.get("doc_title", "文档")
                doc_id = f"doc_{hashlib.md5(doc_title.encode()).hexdigest()[:12]}"
                doc["resource_id"] = doc_id  # ★★★ 回写resource_id ★★★
                await loop.run_in_executor(None, hub.content.save, user_id, "document", doc_id, doc)
                doc_summary = doc.get("doc_content", "")[:300]
                await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "document", doc_id,
                                               f"文档: {doc_title}\n{doc_summary}" if doc_summary else f"文档: {doc_title}")
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "doc_gen", f"生成文档: {doc_title}")

            elif task_type == "question_gen" and (question_result or {}).get("status") == "success":
                questions = question_result.get("questions", {})
                import hashlib
                # ★★★ 基于题目内容生成稳定 ID（移除 time.time()）★★★
                _q_text = str(questions)[:200] if isinstance(questions, dict) else str(questions)
                qid = f"q_{hashlib.md5((str(user_id) + _q_text).encode()).hexdigest()[:12]}"
                if isinstance(questions, dict):
                    questions["resource_id"] = qid  # ★★★ 回写resource_id ★★★
                await loop.run_in_executor(None, hub.content.save, user_id, "question", qid, {"questions": questions, "type": "theory"})
                q_count = len(questions.get("questions", [])) if isinstance(questions, dict) else 0
                await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "question", qid, f"理论题 {q_count} 道")
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "question_gen", "生成了理论题")

            elif task_type == "extension" and (extension_result or {}).get("status") == "success":
                ext = extension_result.get("reading_material", {})
                import hashlib
                ext_title = ext.get("title", "拓展阅读")
                ext_id = f"ext_{hashlib.md5(ext_title.encode()).hexdigest()[:12]}"
                ext["resource_id"] = ext_id  # ★★★ 回写resource_id ★★★
                await loop.run_in_executor(None, hub.content.save, user_id, "extension", ext_id, ext)
                ext_summary = (ext.get("content") or ext.get("background") or "")[:300]
                await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "extension", ext_id,
                                               f"拓展阅读: {ext_title}\n{ext_summary}" if ext_summary else f"拓展阅读: {ext_title}")
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "extension", f"拓展阅读: {ext_title}")

            elif task_type == "mindmap" and (mindmap_result or {}).get("status") == "success":
                mm = mindmap_result.get("mindmap", {})
                import hashlib
                mm_topic = mm.get("topic", mm.get("central_topic", "思维导图"))
                mm_id = f"mm_{hashlib.md5((str(user_id) + mm_topic).encode()).hexdigest()[:12]}"
                mm["resource_id"] = mm_id  # ★★★ 回写resource_id ★★★
                await loop.run_in_executor(None, hub.content.save, user_id, "mindmap", mm_id, {"mindmap": mm})
                await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "mindmap", mm_id, f"思维导图: {mm_topic}")
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "mindmap", "生成了思维导图")

            elif task_type == "animation" and (animation_result or {}).get("status") == "success":
                raw_html = animation_result.get("html", "")
                try:
                    from Agent.children_agent.wx_html_create import AnimationAgent
                    raw_html = AnimationAgent._clean_html_output(raw_html)
                except Exception:
                    pass
                anim = {"html": raw_html,
                        "metadata": animation_result.get("metadata", {})}
                import hashlib
                anim_title = animation_result.get("title", animation_result.get("topic", "动画"))
                anim_id = f"anim_{hashlib.md5((str(user_id) + anim_title).encode()).hexdigest()[:12]}"
                animation_result["resource_id"] = anim_id  # ★★★ 回写resource_id ★★★
                animation_result["html"] = raw_html       # ★★★ 同步 cleaned html ★★★
                await loop.run_in_executor(None, hub.content.save, user_id, "animation", anim_id, anim)
                await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "animation", anim_id, f"动画: {anim_title}")
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "animation", "生成了动画")

            elif task_type == "video" and (video_result or {}):
                videos = video_result.get("videos", [])
                if videos:
                    import hashlib, json
                    # ★★★ 每个视频按 BVID 独立存入 ContentStore（BVID 是 B 站永久唯一标识）★★★
                    # 同一个 BVID → 同一个文件 → 覆盖 → _saved_at 自动更新到当前时间
                    _current_bvids = set()
                    for v in videos:
                        _bvid = v.get("bvid", "")
                        if _bvid:
                            _current_bvids.add(_bvid)
                            await loop.run_in_executor(None, hub.content.save, user_id, "video", f"bvid_{_bvid}", v)
                    # ★★★ 清理旧格式批量搜索结果中含当前 BVID 的文件（这些视频已独立存储）★★★
                    _user_content_dir = await loop.run_in_executor(None, hub.content._get_user_dir, user_id)
                    _current_bvids_local = _current_bvids.copy()
                    def _clean_old_videos():
                        for _old_file in _user_content_dir.glob("video_video_*.json"):
                            try:
                                with open(_old_file, "r", encoding="utf-8") as _f:
                                    _old_data = json.load(_f)
                                _old_videos = _old_data.get("videos", _old_data.get("result", {}).get("videos", []))
                                if any(v.get("bvid", "") in _current_bvids_local for v in _old_videos if v.get("bvid")):
                                    _old_file.unlink(missing_ok=True)
                            except Exception:
                                pass
                    await loop.run_in_executor(None, _clean_old_videos)
                    # 工作记忆记录一条搜索记录（不存文件，只用于上下文）
                    _search_key = video_result.get("refined_title", "") or state.get("user_input", "")
                    if not _search_key:
                        _search_key = videos[0].get("title", "视频搜索")[:50]
                    vsum = "\n".join([f"- {v.get('title','')}" for v in videos[:3]])
                    await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "video", f"search_{_search_key}",
                                                   f"视频搜索: {_search_key}\n{vsum}" if vsum else f"视频搜索: {_search_key}")
                    await loop.run_in_executor(None, hub.working.set_current_task, user_id, "video", f"搜索视频: {_search_key}")

            elif task_type == "judge_code" and (judge_result or {}).get("status") == "success":
                jr = judge_result.get("judge_result", {})
                import hashlib
                # ★★★ 基于评判内容生成稳定 ID（移除 time.time()）★★★
                _judge_key = str(user_id) + str(jr.get("code", ""))[:200] + str(jr.get("error_type", ""))
                judge_id = f"judge_{hashlib.md5(_judge_key.encode()).hexdigest()[:12]}"
                await loop.run_in_executor(None, hub.content.save, user_id, "judge_code", judge_id, jr)
                has_error = jr.get("has_error", False)
                error_type = jr.get("error_type", "")
                await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "judge_code", judge_id,
                                               f"代码评判: {error_type}")
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "judge_code",
                                             f"评判了代码，{'发现错误: ' + error_type if has_error else '未发现错误'}")

            elif task_type == "ppt" and ppt_result.get("status") == "success":
                ppt_info = {"filename": ppt_result.get("filename", ""),
                            "filepath": ppt_result.get("filepath", ""),
                            "markdown_path": ppt_result.get("markdown_path", ""),
                            "topic": ppt_result.get("topic", ""),
                            "pages": ppt_result.get("pages", 0)}
                # ★★★ 上传 PPT 到 OSS ★★★
                try:
                    from services.oss_storage import upload_file as oss_upload
                    local_path = ppt_result.get("filepath", "")
                    if local_path:
                        oss_key = oss_upload(
                            local_path=local_path,
                            user_id=user_id,
                            resource_type="ppt",
                            filename=ppt_result.get("filename", ""),
                        )
                        if oss_key:
                            ppt_info["oss_key"] = oss_key
                            # 生成签名 URL 直接存入结果
                            from services.oss_storage import get_public_url
                            ppt_info["oss_url"] = get_public_url(oss_key)
                            # 同时回写到 ppt_result，前端可直接使用
                            ppt_result["oss_url"] = ppt_info["oss_url"]
                except Exception as e:
                    print(f"  ⚠️ PPT 上传 OSS 失败（不影响本地）: {e}")
                import hashlib
                ppt_topic = ppt_result.get("topic", "")
                ppt_id = f"ppt_{hashlib.md5((str(user_id) + ppt_topic).encode()).hexdigest()[:12]}"
                ppt_result["resource_id"] = ppt_id  # ★★★ 回写resource_id ★★★
                await loop.run_in_executor(None, hub.content.save, user_id, "ppt", ppt_id, ppt_info)
                await loop.run_in_executor(None, hub.working.set_current_task, user_id, "ppt", f"生成PPT: {ppt_result.get('topic', '')}")

            print("   ✅ 内容已持久化 & 工作记忆已更新")
        except Exception as e:
            print(f"   ⚠️ 持久化保存失败（不影响主流程）: {e}")

    # ★★★ 提取 resource_id 到 final_result 顶层 ★★★
    for _res_key, _res_var in [
        ("practice", practice_result),
        ("document", doc_result),      
        ("question", question_result),
        ("extension", extension_result),
        ("mindmap", mindmap_result),
        ("video", video_result),
        ("animation", animation_result),
        ("ppt", ppt_result),
    ]:
        if not _res_var:
            continue
        _rid = _res_var.get("resource_id")
        if not _rid:
            _inner = final_result.get(_res_key)
            if isinstance(_inner, dict):
                _rid = _inner.get("resource_id")
        if _rid:
            final_result["resource_id"] = _rid

    print("✅ 结果整合完成")
    await _emit_thinking("integrator", "结果整合完成，准备持久化保存")
    
    await _emit_status("integrator", "complete",
                       f"task_type={task_type}, status={final_result.get('status', 'unknown')}")
    
    return {
        **state,
        "final_result": final_result,
        "execution_log": state.get("execution_log", []) + ["integrator"]
    }


# ==================== 查库辅助函数（避免每次调LLM） ====================

def _try_find_existing(resource_type: str, topic: str, user_id: str = "") -> Optional[Dict]:
    """
    三层查库：①用户自己缓存 → ②全局库 → ③LLM生成

    Returns:
        命中返回资源dict（带 source 标记），未命中返回 None
    """
    # ---------- Tier 1: 用户自己的 ContentStore ----------
    if user_id:
        try:
            from memory.content_store import ContentStore
            cstore = ContentStore()
            ctype_map = {"practice": "practice", "question": "question",
                         "doc": "document", "extension": "extension", "video": "video"}
            cs_type = ctype_map.get(resource_type)
            if cs_type:
                own = cstore.search_by_topic(user_id, cs_type, topic, limit=1)
                if own:
                    item = own[0]
                    print(f"  ✅ [查库·用户缓存] 命中: {item.get('_content_type', '')}")
                    if resource_type == "video":
                        # ★★★ 兼容新旧两种格式获取 BVID ★★★
                        _bvid = item.get("bvid", "")
                        if not _bvid:
                            _videos = item.get("videos", [])
                            if _videos and isinstance(_videos[0], dict):
                                _bvid = _videos[0].get("bvid", "")
                        return {"status": "success", "videos": [{
                            "title": item.get("title", item.get("query", "")),
                            "url": item.get("url", ""),
                            "bvid": _bvid,
                            "source": "content_store",
                        }], "source": "content_store"}
                    else:
                        return {"status": "success", "title": item.get("title", item.get("topic", "")),
                                "description": (item.get("doc_content") or item.get("content") or "")[:500],
                                "knowledge_points": item.get("knowledge_points", []),
                                "source": "content_store"}
        except Exception as e:
            print(f"  ⚠️ [查库·用户缓存] 查询失败: {e}")

    # ---------- Tier 2: ResourceDB 全局库 ----------
    try:
        from Agent.children_agent.recommendation.resource_db import ResourceDB
        db = ResourceDB()

        if resource_type == "practice":
            rows = db.find_questions(knowledge_point=topic, limit=1)
            if rows:
                r = rows[0]
                print(f"  ✅ [查库·全局库] 题库命中: {r.get('topic', '')}")
                return {
                    "status": "success",
                    "problem_id": r.get("id", ""),
                    "title": r.get("topic", ""),
                    "description": r.get("content", "")[:500],
                    "difficulty": r.get("difficulty", "中等"),
                    "knowledge_points": (r.get("knowledge_points", "") or "").split(",") if isinstance(r.get("knowledge_points"), str) else (r.get("knowledge_points", []) or []),
                    "reference_code": r.get("reference_code", ""),
                    "source": "resource_db",
                }

        elif resource_type == "question":
            rows = db.find_questions(knowledge_point=topic, limit=20)
            if rows:
                print(f"  ✅ [查库·全局库] 理论题库命中: 共{len(rows)}道")
                import json as _json
                result = {"source": "resource_db"}
                for r in rows:
                    sub = r.get("sub_topic", "single_choice")
                    if sub not in result:
                        result[sub] = []
                    # 从 metadata 中提取 explanation
                    meta_str = r.get("metadata", "{}")
                    explanation = ""
                    if isinstance(meta_str, str) and meta_str.strip():
                        try:
                            meta = _json.loads(meta_str)
                            explanation = meta.get("explanation", "")
                        except Exception:
                            pass
                    item = {
                        "question": r.get("content", ""),
                        "answer": r.get("solution", ""),
                    }
                    # 选择题/多选题才有 options
                    if sub in ("single_choice", "multiple_choice"):
                        opts = r.get("options", "[]")
                        if isinstance(opts, str):
                            try:
                                item["options"] = _json.loads(opts)
                            except Exception:
                                item["options"] = []
                        else:
                            item["options"] = opts or []
                        # ★★★ 如果选择题选项为空，跳过该题（避免展示无选项的题目）★★★
                        if not item["options"] or len(item["options"]) < 2:
                            continue
                    if explanation:
                        item["explanation"] = explanation
                    result[sub].append(item)
                # ★★★ 清理空的题型分组 ★★★
                for k in list(result.keys()):
                    if isinstance(result[k], list) and len(result[k]) == 0:
                        del result[k]
                # ★★★ 如果没有任何有效题型，返回 None 让 LLM 重新生成 ★★★
                if len(result) <= 1:  # 只有 source 键
                    print("  ⚠️ [查库·全局库] 题库中有效题目（含选项）为空，回退到LLM生成")
                    return None
                return result

        elif resource_type in ("doc", "extension"):
            rows = db.find_documents(topic=topic, limit=1)
            if rows:
                r = rows[0]
                print(f"  ✅ [查库·全局库] 文档库命中: {r.get('topic', '')}")
                return {
                    "status": "success",
                    "doc_title": r.get("topic", ""),
                    "doc_content": r.get("content", ""),
                    "knowledge_points": (r.get("knowledge_points", "") or "").split(",") if isinstance(r.get("knowledge_points"), str) else [],
                    "source": "resource_db",
                }

        elif resource_type == "video":
            rows = db.find_videos(topic=topic, limit=3)
            if rows:
                print(f"  ✅ [查库·全局库] 视频库命中: {len(rows)}个")
                return {
                    "status": "success",
                    "videos": [{
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "author": r.get("author", ""),
                        "duration": r.get("duration", ""),
                        "source": "resource_db",
                    } for r in rows],
                }

    except Exception as e:
        print(f"  ⚠️ [查库·全局库] 查询失败: {e}")

    # ---------- Tier 3: 都未命中，让调用方调LLM生成 ----------
    return None


# ==================== 主Agent类 ====================

class ConductAgent:
    """
    Conduct层主Agent - 基于LangGraph的执行层控制器
    
    负责实时学习任务执行和特征更新
    """
    
    def __init__(self):
        """初始化Conduct层Agent并构建工作流"""
        print("🚀 正在初始化Conduct层Agent系统...")
        
        # 初始化所有Conduct层子Agent
        self.practice_agent = PracticeAgent()
        self.question_agent = QuestionGeneratorAgent()
        self.doc_agent = CourseDocAgent()
        self.extension_agent = ExtensionReadingAgent()
        self.video_agent = VideoSearchAgent()
        self.mindmap_agent = MindMapAgent()
        
        # 导入动画Agent
        try:
            from .children_agent.wx_html_create import AnimationAgent
        except ImportError:
            from Agent.children_agent.wx_html_create import AnimationAgent
        self.animation_agent = AnimationAgent()

        # 初始化学习路径规划Agent
        self.study_plan_agent = StudyPlanAgent()

        # 初始化PPT生成Agent
        self.ppt_agent = PPTCreationAgent()

        # 初始化代码评判Agent
        self.judge_agent = JudgeAgent()

        # 共享组件
        self.feature_updater = DynamicFeatureUpdater()
        
        # 构建LangGraph工作流
        self.app = self._build_workflow()
        
        print("✅ Conduct层Agent系统初始化完成")
    
    def _build_workflow(self):
        """构建LangGraph工作流"""
        workflow = StateGraph(ConductState)  #  要知道的是在传递对应的conductState，原来对应定义的键值对会被注册到其下的组件中，因为执行图的时候我们需要知道实际执行的时候动态信息，所以我们得转换，对应stategraph中会自动实现
        
        # 添加节点（所有节点函数均为 async，LangGraph ainvoke 会自动 await）
        # 使用 _wrap_node 包装每个节点以向前端推送实时状态
        workflow.add_node("router", router_node)
        workflow.add_node("practice", _wrap_node("practice", create_practice_node(self.practice_agent, self.feature_updater)))
        workflow.add_node("question_gen", _wrap_node("question_gen", create_question_gen_node(self.question_agent, self.feature_updater)))
        workflow.add_node("doc_gen", _wrap_node("doc_gen", create_doc_gen_node(self.doc_agent, self.feature_updater)))
        workflow.add_node("extension", _wrap_node("extension", create_extension_node(self.extension_agent, self.feature_updater)))
        workflow.add_node("video", _wrap_node("video", create_video_node(self.video_agent, self.feature_updater)))
        workflow.add_node("mindmap", _wrap_node("mindmap", create_mindmap_node(self.mindmap_agent, self.feature_updater)))
        workflow.add_node("animation", _wrap_node("animation", create_animation_node(self.animation_agent)))
        workflow.add_node("study_plan", _wrap_node("study_plan", create_study_plan_node(self.study_plan_agent)))
        workflow.add_node("ppt", _wrap_node("ppt", create_ppt_node(self.ppt_agent)))
        workflow.add_node("judge", _wrap_node("judge", create_judge_node(self.judge_agent)))

        workflow.add_node("integrator", integrator_node)
        
        # 设置入口点
        workflow.set_entry_point("router") #  相当于实现的就是add_edge(START, 'router') 也就是实现了对应声明的START，需要注意的是，START是一个特殊的节点，它没有前驱节点，所以不能直接添加边到它--也就是不能实现add_node(START, 'router')

        
        # 定义路由决策函数
        def route_decision(state: ConductState) -> str:
            next_node = state.get("next_node", "END")
            print(f"🚀 Conduct动态路由到: {next_node}")
            return next_node
        
        # 添加条件边
        workflow.add_conditional_edges(
            "router",
            route_decision,
            {
                "practice": "practice",
                "judge": "judge",
                "question_gen": "question_gen",
                "doc_gen": "doc_gen",
                "extension": "extension",
                "video": "video",
                "mindmap": "mindmap",
                "animation": "animation",  # ★★★ 动画生成
                "study_plan": "study_plan",  # ★★★ 学习路径规划
                "ppt": "ppt",  # ★★★ PPT生成
                # "knowledge_query": "knowledge_query",  # ★★★ 知识库问答（暂未实现）
                "END": END
            }
        )
        
        # 所有执行节点 → integrator
        workflow.add_edge("practice", "integrator")
        workflow.add_edge("question_gen", "integrator")
        workflow.add_edge("doc_gen", "integrator")
        workflow.add_edge("extension", "integrator")
        workflow.add_edge("video", "integrator")
        workflow.add_edge("mindmap", "integrator")
        workflow.add_edge("animation", "integrator")  # ★★★ 动画生成
        workflow.add_edge("study_plan", "integrator")  # ★★★ 学习路径规划
        workflow.add_edge("ppt", "integrator")  # ★★★ PPT生成
        workflow.add_edge("judge", "integrator")  # ★★★ 代码评判

        # integrator → END
        workflow.add_edge("integrator", END)
        
        # 编译工作流
        app = workflow.compile()
        
        print("✅ Conduct层LangGraph工作流编译完成")
        print("   流程图: router → [practice/judge/question_gen/doc_gen/extension/video/mindmap/animation/study_plan/ppt] → integrator → END")
        
        return app
    
    async def execute_task_async(self, user_id: str, user_input: str, task_type: str, enable_tts: bool = False, confirmed: bool = False, override_suggestions: bool = False, ignore_weak_points: bool = False, focus_weak_points: bool = False) -> Dict[str, Any]:
        """
        异步执行Conduct层任务

        Args:
            user_id: 用户ID
            user_input: 用户输入
            task_type: 任务类型 (practice/question_gen/doc_gen/extension/video/mindmap)
            enable_tts: 是否启用TTS语音合成
            confirmed: 用户是否已确认覆盖采纳建议
            override_suggestions: 是否忽略已采纳建议按用户要求执行
            ignore_weak_points: 是否忽略薄弱点提示直接生成学习计划
            focus_weak_points: 是否针对薄弱点制定学习计划

        Returns:
            Dict: 执行结果
        """
        print("\n" + "="*70)
        print("🎯 Conduct层开始执行任务")
        print("="*70)
        print(f"用户ID: {user_id}")
        print(f"用户输入: {user_input}")
        print(f"任务类型: {task_type}")
        print(f"启用TTS: {enable_tts}")
        
        # ★★★ 注入方案配置到 user_input ★★★
        from utils.plan_config import get_plan_context_text
        _plan_context = get_plan_context_text(user_id)
        if _plan_context:
            user_input = f"[{_plan_context}]\n{user_input}"
            print(f"📋 注入方案上下文: {_plan_context}")

        # 发射任务开始事件（供SSE流推送）
        await _emit_status("task", "start",
                           f"task_type={task_type}, user_id={user_id}")
        await _emit_thinking("task", f"🚀 任务开始: task_type={task_type}, user_id={user_id}")

        initial_state = ConductState(
            user_id=user_id,
            user_input=user_input,
            student_features=None,
            task_type=task_type,
            practice_result=None,
            question_result=None,
            doc_result=None,
            extension_result=None,
            video_result=None,
            mindmap_result=None,
            animation_result=None,
            knowledge_result=None,
            study_plan_result=None,
            ppt_result=None,
            judge_result=None,
            next_node="",
            execution_log=[],
            final_result=None,
            error=None,
            enable_tts=enable_tts,
            confirmed=confirmed,
            override_suggestions=override_suggestions,
            ignore_weak_points=ignore_weak_points,
            focus_weak_points=focus_weak_points
        )
        
        try:
            config = {"recursion_limit": 50}
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            result = final_state.get("final_result", {})
            
            print("\n✅ Conduct层任务执行完成")
            print(f"   执行节点: {final_state.get('execution_log', [])}")
            
        except Exception as e:
            print(f"❌ Conduct层任务执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            result = {
                "status": "error",
                "error": str(e),
                "layer": "conduct"
            }
        
        # 发射任务完成事件（供SSE流推送节点状态，不重复发task_result — 由MasterController统一处理）
        await _emit_status("task", "complete",
                           f"status={result.get('status', 'unknown')}")
        
        print("="*70 + "\n")
        
        return result
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取Conduct层系统状态"""
        return {
            "system_name": "Conduct层执行Agent",
            "version": "1.0.0",
            "architecture": "LangGraph StateGraph",
            "nodes": ["router", "practice", "judge", "question_gen", "doc_gen", "extension", "video", "mindmap", "integrator"],
            "capabilities": [
                "编程练习生成与判题",
                "代码评判与调试",
                "理论题生成",
                "课程文档生成",
                "拓展阅读生成",
                "B站视频搜索",
                "思维导图生成",
                "实时特征更新"
            ]
        }



