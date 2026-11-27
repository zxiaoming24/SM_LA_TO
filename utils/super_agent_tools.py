"""
SuperAgent 工具层 - 将现有子Agent封装为可调用的Tool函数

每个Tool接受一个参数字典，返回处理结果。
所有Tool函数均为异步，支持并发调用。
"""

import asyncio
import json
import hashlib
from typing import Dict, Any, Optional
from utils.llm_config import get_chat_openai

# 全局 Agent 初始化锁（延迟创建，确保绑定到正确的事件循环）
_agent_init_lock: Optional[asyncio.Lock] = None

async def _get_agent_lock() -> asyncio.Lock:
    """延迟创建 Agent 初始化锁"""
    global _agent_init_lock
    if _agent_init_lock is None:
        _agent_init_lock = asyncio.Lock()
    return _agent_init_lock


# ==================== 用户私有库持久化（ContentStore + Working Memory）====================

async def _save_to_user_store(user_id: str, task_type: str, resource_id: str,
                               resource_data: Dict[str, Any], summary: str = "",
                               knowledge_point: str = ""):
    """
    将生成的资源保存到用户的私有 ContentStore 和 Working Memory

    Args:
        user_id: 用户ID
        task_type: 资源类型（practice / document / question / extension / mindmap / video / ppt）
        resource_id: 资源唯一ID
        resource_data: 资源数据（会写入 content_store）
        summary: 摘要文本（写入 working memory）
        knowledge_point: 关联知识点（写入 knowledge mastery）
    """
    if not user_id:
        return
    try:
        from memory.content_store import ContentStore
        from memory.memory_hub import MemoryHub

        hub = MemoryHub()
        loop = asyncio.get_running_loop()

        # 1. 保存到 ContentStore（用户私有库）
        await loop.run_in_executor(None, hub.content.save, user_id, task_type, resource_id, resource_data)

        # 2. 更新 Working Memory
        if summary:
            await loop.run_in_executor(None, hub.working.set_last_generated, user_id, task_type, resource_id, summary)
        if knowledge_point:
            await loop.run_in_executor(None, hub.working.add_focus_knowledge, user_id, knowledge_point)

        print(f"  ✅ [资源入库] {task_type}/{resource_id} → 用户 {user_id} 私有库")
    except Exception as e:
        print(f"  ⚠️ [资源入库] 失败（不影响使用）: {e}")

# ==================== 工具：编程练习生成 ====================

_practice_agent = None

async def tool_generate_practice(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成编程练习题
    
    Args:
        params: {
            "user_input": str,        # 用户输入/知识点
            "user_id": str,           # 用户ID
            "confirmed": bool,        # 是否确认
            "override_suggestions": bool  # 是否忽略建议
        }
    """
    global _practice_agent
    if _practice_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _practice_agent is None:
                from Agent.children_agent.practice_agent import PracticeAgent
                _practice_agent = PracticeAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    confirmed = params.get("confirmed", False)
    override_suggestions = params.get("override_suggestions", False)
    
    # 获取学生特征
    features = None
    if user_id:
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
        except Exception:
            pass
    
    problem = await _practice_agent.generate_problem_async(
        user_input, user_id, confirmed=confirmed,
        override_suggestions=override_suggestions
    )
    
    if problem:
        result = {
            "success": True,
            "task_type": "practice",
            "practice": problem,
            "summary": f"已生成编程练习题：{problem.get('title', '')} (难度：{problem.get('difficulty', '')})"
        }
        # 持久化到用户私有库
        pid = problem.get("problem_id", f"p_{hashlib.md5(str(problem.get('title', '') + str(problem.get('knowledge_points', ''))).encode()).hexdigest()[:12]}")
        problem["resource_id"] = pid
        kps = problem.get("knowledge_points", [])
        await _save_to_user_store(
            user_id=user_id, task_type="practice", resource_id=pid,
            resource_data=problem,
            summary=result["summary"],
            knowledge_point=kps[0] if kps else ""
        )
        return result
    return {"success": False, "error": "编程练习生成失败"}


# ==================== 工具：理论题生成 ====================

_question_agent = None

async def tool_generate_questions(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成理论题（选择题/判断题/填空题等）
    
    Args:
        params: {
            "user_input": str,    # 课程/知识点
            "user_id": str        # 用户ID
        }
    """
    global _question_agent
    if _question_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _question_agent is None:
                from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent
                _question_agent = QuestionGeneratorAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    # 获取学生特征
    features = None
    if user_id:
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
        except Exception:
            pass
    
    info = {
        "major": params.get("major", "计算机"),
        "course_name": user_input,
        "weak_points": "",
        "learn_level": "medium",
        "user_input": user_input,
        "student_feature": features or {},
        "user_id": user_id
    }
    
    questions = await _question_agent.generate_all_questions_async(info, False)
    
    if questions:
        question_types = [k for k in questions.keys() if k != "source"]
        result = {
            "success": True,
            "task_type": "question_gen",
            "questions": questions,
            "summary": f"已生成理论题（题型：{'/'.join(question_types)}）"
        }
        # 持久化到用户私有库
        qid = f"q_{hashlib.md5((str(user_id) + user_input).encode()).hexdigest()[:12]}"
        if isinstance(questions, dict):
            questions["resource_id"] = qid
        await _save_to_user_store(
            user_id=user_id, task_type="question", resource_id=qid,
            resource_data={"questions": questions, "type": "theory"},
            summary=result["summary"],
            knowledge_point=user_input
        )
        return result
    return {"success": False, "error": "理论题生成失败"}


# ==================== 工具：课程文档生成 ====================

_doc_agent = None

async def tool_generate_document(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成课程讲解文档
    
    Args:
        params: {
            "user_input": str,    # 课程/知识点
            "user_id": str        # 用户ID
        }
    """
    global _doc_agent
    if _doc_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _doc_agent is None:
                from Agent.children_agent.course_doc_agent_ali import CourseDocAgent
                _doc_agent = CourseDocAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    features = None
    if user_id:
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
        except Exception:
            pass
    
    info = {
        "major": features.get("academic_background", {}).get("major_preference", "计算机") if features else "计算机",
        "course_name": user_input,
        "weak_points": user_input,
        "learn_level": "medium",
        "student_feature": features or {}
    }
    
    doc_data = await _doc_agent.generate_course_document_async(
        student_info=info, user_id=user_id, enable_tts=False
    )
    
    if doc_data:
        result = {
            "success": True,
            "task_type": "doc_gen",
            "document": doc_data,
            "summary": f"已生成课程文档：{doc_data.get('doc_title', '')}"
        }
        # 持久化到用户私有库
        doc_title = doc_data.get("doc_title", "文档")
        doc_id = f"doc_{hashlib.md5(doc_title.encode()).hexdigest()[:12]}"
        doc_data["resource_id"] = doc_id
        doc_summary = doc_data.get("doc_content", "")[:300]
        await _save_to_user_store(
            user_id=user_id, task_type="document", resource_id=doc_id,
            resource_data=doc_data,
            summary=f"文档: {doc_title}\n{doc_summary}" if doc_summary else f"文档: {doc_title}",
            knowledge_point=user_input
        )
        return result
    return {"success": False, "error": "文档生成失败"}


# ==================== 工具：思维导图生成 ====================

_mindmap_agent = None

async def tool_generate_mindmap(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成思维导图JSON
    
    Args:
        params: {
            "user_input": str,    # 知识点
            "user_id": str        # 用户ID
        }
    """
    global _mindmap_agent
    if _mindmap_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _mindmap_agent is None:
                from Agent.children_agent.mindmap_agent import MindMapAgent
                _mindmap_agent = MindMapAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    features = None
    if user_id:
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
        except Exception:
            pass
    
    info = {
        "major": params.get("major", "计算机"),
        "course_name": user_input,
        "weak_points": "",
        "learn_level": "medium",
        "student_feature": features or {}
    }
    
    result = await _mindmap_agent.generate_mindmap_json_async(info, False)
    
    if result:
        title = ""
        if isinstance(result, dict):
            title = result.get("root", {}).get("name", "") if isinstance(result.get("root"), dict) else ""
        result_data = {
            "success": True,
            "task_type": "mindmap",
            "mindmap": result,
            "summary": f"已生成思维导图：{title or user_input}"
        }
        # 持久化到用户私有库
        mm_id = f"mm_{hashlib.md5((str(user_id) + user_input).encode()).hexdigest()[:12]}"
        if isinstance(result, dict):
            result["resource_id"] = mm_id
        await _save_to_user_store(
            user_id=user_id, task_type="mindmap", resource_id=mm_id,
            resource_data={"mindmap": result},
            summary=f"思维导图: {title or user_input}",
            knowledge_point=user_input
        )
        return result_data
    return {"success": False, "error": "思维导图生成失败"}


# ==================== 工具：视频搜索 ====================

_video_agent = None

async def tool_search_video(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    搜索B站教学视频
    
    Args:
        params: {
            "user_input": str,    # 搜索关键词
            "user_id": str        # 用户ID
        }
    """
    global _video_agent
    if _video_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _video_agent is None:
                from Agent.children_agent.video_search_agent import VideoSearchAgent
                _video_agent = VideoSearchAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    features = None
    if user_id:
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
        except Exception:
            pass
    
    info = {
        "major": params.get("major", "计算机"),
        "course_name": user_input,
        "weak_points": "",
        "learn_level": "medium",
        "user_input": user_input,
        "student_feature": features or {}
    }
    
    result = await _video_agent.search_videos_for_question_async(
        user_question=user_input,
        top_k=3,
        student_features=features,
        user_id=user_id,
        enable_tts=False
    )
    
    # assembler.assemble_response() 返回的格式没有 "status" 字段
    # 检查 result 中是否有 videos 列表来判断成功与否
    videos = []
    if result:
        videos = result.get("videos", [])
    if videos:
        result = {
            "success": True,
            "task_type": "video",
            "videos": videos,
            "summary": f"已搜索到 {len(videos)} 个教学视频"
        }
        # 持久化到用户私有库
        if user_id and videos:
            from memory.content_store import ContentStore
            from memory.memory_hub import MemoryHub
            import json, glob
            hub = MemoryHub()
            # ★★★ 每个视频按 BVID 独立存入 ContentStore（BVID 是 B 站永久唯一标识）★★★
            # 同一个 BVID → 同一个文件 → 覆盖 → _saved_at 自动更新到当前时间
            loop = asyncio.get_running_loop()
            _current_bvids = set()
            for v in videos:
                _bvid = v.get("bvid", "")
                if _bvid:
                    _current_bvids.add(_bvid)
                    await loop.run_in_executor(None, hub.content.save, user_id, "video", f"bvid_{_bvid}", v)
            # ★★★ 清理旧格式批量搜索结果中含当前 BVID 的文件 ★★★
            def _clean_old_video_files():
                _user_content_dir = hub.content._get_user_dir(user_id)
                for _old_file in _user_content_dir.glob("video_video_*.json"):
                    try:
                        with open(_old_file, "r", encoding="utf-8") as _f:
                            _old_data = json.load(_f)
                        _old_videos = _old_data.get("videos", _old_data.get("result", {}).get("videos", []))
                        if any(v.get("bvid", "") in _current_bvids for v in _old_videos if v.get("bvid")):
                            _old_file.unlink(missing_ok=True)
                    except Exception:
                        pass
            await loop.run_in_executor(None, _clean_old_video_files)
            # 工作记忆记录搜索记录
            vid_title = videos[0].get("title", "")[:50]
            await loop.run_in_executor(None, hub.working.set_last_generated, user_id, "video", f"search_{user_input}",
                                       f"视频搜索: {vid_title} (共{len(videos)}个)")
            if user_input:
                await loop.run_in_executor(None, hub.working.add_focus_knowledge, user_id, user_input)
                try:
                    await loop.run_in_executor(None, lambda: hub.knowledge.record_activity(
                        user_id, user_input, correct=None, activity_type="video", difficulty="中等"
                    ))
                except Exception:
                    pass
            print(f"  ✅ [资源入库] 视频已按 BVID 独立存入用户 {user_id} 私有库 ({len(videos)} 个)")
        return result
    return {"success": False, "error": "视频搜索失败"}


# ==================== 工具：拓展阅读生成 ====================

_extension_agent = None

async def tool_generate_extension(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成拓展阅读材料
    
    Args:
        params: {
            "user_input": str,    # 知识点
            "user_id": str        # 用户ID
        }
    """
    global _extension_agent
    if _extension_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _extension_agent is None:
                from Agent.children_agent.extension_reading_agent import ExtensionReadingAgent
                _extension_agent = ExtensionReadingAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    features = None
    if user_id:
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
        except Exception:
            pass
    
    info = {
        "major": params.get("major", "计算机"),
        "course_name": user_input,
        "weak_points": "",
        "learn_level": "medium",
        "user_input": user_input,
        "student_feature": features or {},
        "user_id": user_id
    }
    
    material = await _extension_agent.generate_reading_material_async(info, False)
    
    if material:
        result = {
            "success": True,
            "task_type": "extension",
            "reading_material": material,
            "summary": f"已生成拓展阅读材料：{material.get('title', '') or user_input}"
        }
        # 持久化到用户私有库
        ext_title = material.get("title", "拓展阅读")
        ext_id = f"ext_{hashlib.md5(ext_title.encode()).hexdigest()[:12]}"
        if isinstance(material, dict):
            material["resource_id"] = ext_id
        ext_summary = (material.get("content") or material.get("background") or "")[:300]
        await _save_to_user_store(
            user_id=user_id, task_type="extension", resource_id=ext_id,
            resource_data=material,
            summary=f"拓展阅读: {ext_title}\n{ext_summary}" if ext_summary else f"拓展阅读: {ext_title}",
            knowledge_point=user_input
        )
        return result
    return {"success": False, "error": "拓展阅读生成失败"}


# ==================== 工具：学习计划生成 ====================

_study_plan_agent = None

async def tool_generate_study_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成学习计划
    
    Args:
        params: {
            "user_input": str,    # 学习目标/时间要求
            "user_id": str        # 用户ID
        }
    """
    global _study_plan_agent
    if _study_plan_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _study_plan_agent is None:
                from Agent.children_agent.study_plan_agent import StudyPlanAgent
                _study_plan_agent = StudyPlanAgent()
    
    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    result = await _study_plan_agent.generate_plan_async(user_input, user_id)
    
    if result:
        result_data = {
            "success": True,
            "task_type": "study_plan",
            "study_plan": result,
            "summary": f"已生成学习计划：{result.get('title', '')}"
        }
        # 持久化到用户私有库
        plan_title = result.get("title", "学习计划")
        plan_id = f"plan_{hashlib.md5((str(user_id) + plan_title).encode()).hexdigest()[:12]}"
        await _save_to_user_store(
            user_id=user_id, task_type="study_plan", resource_id=plan_id,
            resource_data=result,
            summary=f"学习计划: {plan_title}",
            knowledge_point=user_input
        )
        return result_data
    return {"success": False, "error": "学习计划生成失败"}


# ==================== 工具：PPT生成 ====================

_ppt_agent = None

async def tool_generate_ppt(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成PPT
    
    Args:
        params: {
            "user_input": str,    # 主题
            "style": str,         # 风格（默认：新中式科技风）
            "page_count": int,    # 页数（默认：4）
            "user_id": str        # 用户ID
        }
    """
    global _ppt_agent
    if _ppt_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _ppt_agent is None:
                from Agent.children_agent.ppt_agent import PPTCreationAgent
                _ppt_agent = PPTCreationAgent()
    
    topic = params.get("user_input", "")
    style = params.get("style", "新中式科技风")
    page_count = params.get("page_count", 4)
    user_id = params.get("user_id", "")
    
    # 调用内部方法生成PPT
    result = await _ppt_agent.generate_ppt_async(
        topic=topic, style=style, page_count=page_count, user_id=user_id
    )
    
    if result and result.get("status") == "success":
        result_data = {
            "success": True,
            "task_type": "ppt",
            "ppt": result,
            "summary": f"已生成PPT：{topic}（{page_count}页，{style}风格）"
        }
        # 持久化到用户私有库
        ppt_info = {
            "filename": result.get("filename", ""),
            "filepath": result.get("filepath", ""),
            "markdown_path": result.get("markdown_path", ""),
            "topic": result.get("topic", topic),
            "pages": result.get("pages", page_count),
        }
        ppt_id = f"ppt_{hashlib.md5((str(user_id) + topic).encode()).hexdigest()[:12]}"
        await _save_to_user_store(
            user_id=user_id, task_type="ppt", resource_id=ppt_id,
            resource_data=ppt_info,
            summary=f"PPT: {topic} ({page_count}页)",
            knowledge_point=topic
        )
        return result_data
    return {"success": False, "error": f"PPT生成失败: {result.get('message', '') if result else '未知错误'}"}


# ==================== 工具：知识问答 ====================

_kb_agent = None

async def tool_knowledge_qa(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    基于知识库的专业知识问答
    
    Args:
        params: {
            "user_input": str,    # 问题
            "user_id": str        # 用户ID
        }
    """
    global _kb_agent
    if _kb_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _kb_agent is None:
                try:
                    from Agent.children_agent.knowledge_base_agent import KnowledgeBaseAgent
                    _kb_agent = KnowledgeBaseAgent()
                except Exception as e:
                    return {"success": False, "error": f"知识库初始化失败: {e}"}
    
    question = params.get("user_input", "")
    user_id = params.get("user_id", "")
    
    try:
        result = await _kb_agent.query_knowledge(question=question, user_id=user_id)
        if result:
            return {
                "success": True,
                "task_type": "knowledge_qa",
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "summary": f"知识库回答：{result.get('answer', '')[:100]}..."
            }
    except Exception as e:
        return {"success": False, "error": f"知识问答失败: {e}"}
    
    return {"success": False, "error": "知识库中未找到相关内容"}


# ==================== 工具：代码评判 ====================

_judge_agent = None

async def tool_judge_code(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    评判用户提交的代码——分析语法/逻辑错误，给出修复建议和解释

    Args:
        params: {
            "user_input": str,    # 用户输入的代码（可包含描述文字）
            "user_id": str        # 用户ID
        }
    """
    global _judge_agent
    if _judge_agent is None:
        lock = await _get_agent_lock()
        async with lock:
            if _judge_agent is None:
                from Agent.children_agent.judge_agent import JudgeAgent
                _judge_agent = JudgeAgent()

    user_input = params.get("user_input", "")
    user_id = params.get("user_id", "")

    result = await _judge_agent.debug_code_async(user_input)

    if result:
        has_error = result.get("has_error", False)
        error_type = result.get("error_type", "未知")
        return {
            "success": True,
            "task_type": "judge_code",
            "judge_result": result,
            "summary": f"代码评判完成：{'发现错误 - ' + error_type if has_error else '未发现明显错误'}"
        }
    return {"success": False, "error": "代码评判失败"}


# ==================== 工具：通用LLM问答 ====================

_llm_cache = None

async def tool_general_qa(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    通用知识问答 - 直接使用LLM回答用户问题
    
    Args:
        params: {
            "user_input": str,    # 问题
            "system_hint": str    # 系统提示（可选）
        }
    """
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = get_chat_openai(temperature=0.5, max_tokens=2000)
    
    question = params.get("user_input", "")
    system_hint = params.get("system_hint", "你是一个全能的AI助教，擅长回答各种学习问题。请用通俗易懂的语言回答。")
    
    messages = [
        {"role": "system", "content": system_hint},
        {"role": "user", "content": question}
    ]
    
    try:
        response = await _llm_cache.ainvoke(messages)
        answer = response.content if hasattr(response, 'content') else str(response)
        return {
            "success": True,
            "task_type": "general_qa",
            "answer": answer,
            "summary": answer[:100] + "..."
        }
    except Exception as e:
        return {"success": False, "error": f"问答失败: {e}"}


# ==================== 工具注册表 ====================

# 所有工具的注册信息（名称、描述、参数模式）
TOOL_REGISTRY = {
    "generate_practice": {
        "name": "generate_practice",
        "description": "生成编程练习题。当用户要求做编程题、写代码练习、算法练习时使用。返回包含题目描述、输入输出格式、示例等。",
        "parameters": {
            "user_input": "用户想要练习的知识点或编程概念（如：指针、循环、递归、动态规划）",
            "user_id": "用户ID"
        }
    },
    "generate_questions": {
        "name": "generate_questions",
        "description": "生成理论题（选择题、判断题、填空题、简答题）。当用户要求做题、刷题、考考我、出题时使用。返回多题型题目。",
        "parameters": {
            "user_input": "课程名称或知识点",
            "user_id": "用户ID"
        }
    },
    "generate_document": {
        "name": "generate_document",
        "description": "生成结构化的课程讲解文档/讲义。当用户要求生成文档、笔记、总结、报告时使用。返回带章节结构的详细文档。",
        "parameters": {
            "user_input": "课程名称或知识点",
            "user_id": "用户ID"
        }
    },
    "generate_mindmap": {
        "name": "generate_mindmap",
        "description": "生成思维导图JSON数据。当用户要求梳理知识结构、生成脑图、知识框架时使用。返回层级化的思维导图数据。",
        "parameters": {
            "user_input": "知识点或课程名称",
            "user_id": "用户ID"
        }
    },
    "search_video": {
        "name": "search_video",
        "description": "搜索B站教学视频。当用户要求找视频、看视频教程、推荐视频时使用。返回视频列表（含标题、链接、封面等）。",
        "parameters": {
            "user_input": "搜索关键词或知识点",
            "user_id": "用户ID"
        }
    },
    "generate_extension": {
        "name": "generate_extension",
        "description": "生成拓展阅读材料。当用户要求深入学习、拓展阅读、推荐资料时使用。返回包含背景知识、深度辨析等的阅读材料。",
        "parameters": {
            "user_input": "知识点",
            "user_id": "用户ID"
        }
    },
    "generate_study_plan": {
        "name": "generate_study_plan",
        "description": "生成学习计划。当用户要求制定学习路线、规划学习时间、安排学习进度时使用。返回分阶段的学习计划。",
        "parameters": {
            "user_input": "学习目标及时间要求（如：3个月学完Python）",
            "user_id": "用户ID"
        }
    },
    "generate_ppt": {
        "name": "generate_ppt",
        "description": "生成PPT演示文稿。当用户要求制作PPT、幻灯片、演示文稿时使用。返回PPT文件路径。",
        "parameters": {
            "user_input": "PPT主题",
            "style": "设计风格（默认：新中式科技风）",
            "page_count": "页数（默认4页）",
            "user_id": "用户ID"
        }
    },
    "knowledge_qa": {
        "name": "knowledge_qa",
        "description": "基于知识库的专业知识问答。当用户询问具体的专业知识、概念解释时，优先使用此工具从知识库检索答案。",
        "parameters": {
            "user_input": "用户的问题",
            "user_id": "用户ID"
        }
    },
    "judge_code": {
        "name": "judge_code",
        "description": '评判/调试用户提交的代码。当用户直接贴代码问「这段代码有什么问题」、「帮我debug」、「报错了看看」时使用。返回错误分析、修复建议和学习指导。',
        "parameters": {
            "user_input": "用户输入的代码片段（可包含描述文字，如：include<studio.h 这段代码有什么问题）",
            "user_id": "用户ID"
        }
    },
    "general_qa": {
        "name": "general_qa",
        "description": "通用知识问答。当用户询问一般性知识问题、概念解释、学习方法建议等，且不需要调用专门工具时使用。",
        "parameters": {
            "user_input": "用户的问题",
            "system_hint": "系统提示（可选）"
        }
    }
}

# 工具名称到函数的映射
TOOL_FUNCTIONS = {
    "generate_practice": tool_generate_practice,
    "generate_questions": tool_generate_questions,
    "generate_document": tool_generate_document,
    "generate_mindmap": tool_generate_mindmap,
    "search_video": tool_search_video,
    "generate_extension": tool_generate_extension,
    "generate_study_plan": tool_generate_study_plan,
    "generate_ppt": tool_generate_ppt,
    "knowledge_qa": tool_knowledge_qa,
    "judge_code": tool_judge_code,
    "general_qa": tool_general_qa,
}
