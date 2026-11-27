"""
PhaseResourceBridge - 学习计划阶段资源桥接

桥接学习计划和多Agent资源生成，实现"按阶段、按需、按Agent"生成学习资源。

核心流程：
  用户点击阶段中的某个Agent卡片
    → 读计划阶段（知识点+资源类型）
    → 检查ContentStore缓存
    → 未缓存 → 推荐引擎优先（查resource_db）
    → 有推荐 → 返回推荐结果
    → 无推荐 → 调用对应Agent生成 → 入库resource_db + 缓存到ContentStore
"""

from typing import Dict, Any, Optional, List
import asyncio
import json
from memory.memory_hub import MemoryHub
from memory.content_store import ContentStore
from services.shared_executors import CACHE_EXECUTOR
from utils.concurrent_executor import run_async


AGENT_REGISTRY = {
    "video": {
        "module": "Agent.children_agent.video_search_agent",
        "class": "VideoSearchAgent",
        "method": "search_videos_for_question_async",
        "param_map": {"user_question": "kp", "top_k": 5, "raw_query": True},
        "recommend_first": False,
        "resource_db_type": None,
    },
    "practice": {
        "module": "Agent.children_agent.practice_agent",
        "class": "PracticeAgent",
        "method": "generate_problem_async",
        "param_map": {"learning_problem": "kp", "user_id": "user_id"},
        "recommend_first": True,
        "resource_db_type": "question",
    },
    "question": {
        "module": "Agent.children_agent.question_generator_agent",
        "class": "QuestionGeneratorAgent",
        "method": "generate_all_questions_async",
        "param_map": {"info": "kp_info", "enable_tts": False},
        "recommend_first": True,
        "resource_db_type": "question",
    },
    "mindmap": {
        "module": "Agent.children_agent.mindmap_agent",
        "class": "MindMapAgent",
        "method": "generate_mindmap_json_async",
        "param_map": {"info": "kp_info", "enable_tts": False},
        "recommend_first": False,
        "resource_db_type": None,
    },
    "extension": {
        "module": "Agent.children_agent.extension_reading_agent",
        "class": "ExtensionReadingAgent",
        "method": "generate_reading_material_async",
        "param_map": {"info": "kp_info"},
        "recommend_first": True,
        "resource_db_type": "document",
    },
    "doc": {
        "module": "Agent.children_agent.course_doc_agent_ali",
        "class": "CourseDocAgent",
        "method": "generate_course_document_async",
        "param_map": {"student_info": "kp_info", "save_to_file": True, "user_id": "user_id"},
        "recommend_first": False,
        "resource_db_type": None,
    },
    "ppt": {
        "module": "Agent.children_agent.ppt_agent",
        "class": "PPTCreationAgent",
        "method": "generate_ppt_async",
        "param_map": {"topic": "kp", "style": "新中式科技风", "page_count": 4, "user_id": "user_id"},
        "recommend_first": False,
        "resource_db_type": None,
    },
}


class PhaseResourceBridge:
    """学习计划阶段资源桥接"""

    def __init__(self):
        self._hub = MemoryHub()
        self._store = ContentStore()
        self._agents = {}
        self._recommender = None
        self._feature_updater = None

    def _get_agent(self, agent_key: str):
        if agent_key not in self._agents:
            import importlib
            info = AGENT_REGISTRY[agent_key]
            module = importlib.import_module(info["module"])
            cls = getattr(module, info["class"])
            self._agents[agent_key] = cls()
        return self._agents[agent_key]

    def _get_recommender(self):
        if self._recommender is None:
            try:
                from Agent.children_agent.recommendation import PersonalizedRecommender
                self._recommender = PersonalizedRecommender()
            except Exception as e:
                print(f"  ⚠️ [PhaseBridge] 推荐引擎初始化失败: {e}")
                return None
        return self._recommender

    def _get_features(self, user_id: str):
        if self._feature_updater is None:
            try:
                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                self._feature_updater = DynamicFeatureUpdater()
            except Exception:
                return None
        return self._feature_updater.get_latest_features(user_id)

    def get_plan_phases(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户学习计划的所有阶段（已根据注意力偏好扩容）"""
        try:
            plan = self._hub.planner.get_plan(user_id)
            if not plan:
                return []
            phases = plan.get("phases", [])

            # ★★★ 检测重规划是否已完成 ★★★
            # 如果已完成阶段有评估，但后续阶段内容仍是旧的（与评估建议不匹配）
            # 说明重规划还在后台执行中
            plan_title = plan.get("title", "")
            for i, phase in enumerate(phases):
                if phase.get("status") == "已完成" and "phase_assessment" in phase:
                    # 检查该阶段评估是否已触发重规划
                    assessment = phase.get("phase_assessment", {})
                    adjustments = assessment.get("adjustments", {})
                    res_adj = adjustments.get("resource_adjustment_for_next", {})
                    has_suggestions = bool(res_adj.get("increase") or res_adj.get("decrease"))
                    
                    if has_suggestions:
                        # 检查后续阶段是否已更新（新的阶段名通常包含"补救"/"补强"等关键词）
                        next_phase = phases[i + 1] if i + 1 < len(phases) else None
                        if next_phase:
                            next_name = next_phase.get("name", "")
                            # 如果后续阶段名还跟原计划一样，说明重规划尚未完成
                            is_updated = any(kw in next_name for kw in ["补救", "补强", "回炉"])
                            if not is_updated:
                                # 返回一个特殊标记
                                phases[i]["_regenerating_phases"] = True

            # ★★★ 读取注意力偏好，扩容 resource_types ★★★
            try:
                plan_data = self._hub.planner.get_plan(user_id)
                if plan_data and plan_data.get("_disable_attention_expansion"):
                    # 直接使用模式，跳过注意力偏好扩容
                    pass
                else:
                    from Agent.children_agent.recommendation.attention_profile import get_profile
                    profile = get_profile(user_id)
                    for phase in phases:
                        base_types = phase.get("resource_types", [])
                        if base_types:
                            expanded = profile.get_weighted_resource_types(
                                base_types=base_types, extra_slots=2,
                                remove_below=0.43
                            )
                            phase["resource_types"] = expanded
                            phase["_preference_expanded"] = True
            except Exception:
                pass

            for i, phase in enumerate(phases):
                phase["phase_index"] = i
            return phases
        except Exception as e:
            print(f"⚠️ [PhaseBridge] 获取计划失败: {e}")
            return []

    def get_phase_resource_status(self, user_id: str, phase_index: int) -> Dict[str, Any]:
        phases = self.get_plan_phases(user_id)
        if not phases or phase_index >= len(phases):
            return {"error": "阶段不存在"}
        phase = phases[phase_index]
        status = {}
        for res_type in phase.get("resource_types", []):
            status[res_type] = {}
            for kp in phase.get("knowledge_points", []):
                cid = self._cache_id(user_id, phase_index, res_type, kp)
                cached = self._store.load(user_id, f"phase_{res_type}", cid)
                status[res_type][kp] = {
                    "cached": cached is not None,
                    "content_id": cid,
                }
        return {"phase_index": phase_index, "phase_name": phase.get("name", ""), "resources": status}

    def _get_phase_context(self, user_id: str, phase_index: int) -> str:
        try:
            phases = self.get_plan_phases(user_id)
            if phases and phase_index < len(phases):
                return phases[phase_index].get("name", "")
        except Exception:
            pass
        return ""

    async def generate_phase_resource(
        self, user_id: str, phase_index: int, resource_type: str, knowledge_point: str,
        force_generate: bool = False
    ) -> Dict[str, Any]:
        cid = self._cache_id(user_id, phase_index, resource_type, knowledge_point)
        loop = asyncio.get_running_loop()

        # 1. 查ContentStore缓存（强制生成时跳过）
        if not force_generate:
            cached = await loop.run_in_executor(CACHE_EXECUTOR, self._store.load, user_id, f"phase_{resource_type}", cid)
            if cached:
                return {"success": True, "cached": True, "resource": cached, "agent": resource_type}

        # 直接使用模式：不允许动态生成
        try:
            plan = self._hub.planner.get_plan(user_id)
            if plan and plan.get("_direct_use"):
                return {"success": False, "cached": False, "error": "直接使用模式不支持动态生成资源"}
        except Exception:
            pass

        if resource_type not in AGENT_REGISTRY:
            return {"success": False, "cached": False, "error": f"未知资源类型: {resource_type}"}

        info = AGENT_REGISTRY[resource_type]
        phase_context = None if force_generate else await loop.run_in_executor(None, self._get_phase_context, user_id, phase_index)

        # 2. 推荐引擎优先（如果该资源类型支持，且未强制生成）
        if info.get("recommend_first") and not force_generate:
            try:
                recommender = self._get_recommender()
                if recommender:
                    db_type = info["resource_db_type"]
                    features = await loop.run_in_executor(None, self._get_features, user_id)
                    rec_result = await loop.run_in_executor(None, lambda: recommender.recommend(
                        user_id=user_id,
                        resource_type=db_type,
                        user_features=features,
                        topic=knowledge_point,
                        n=3,
                        exclude_done=True,
                    ))
                    if rec_result.get("count", 0) > 0:
                        source = rec_result.get("primary_source", "recommender")
                        recommendations = rec_result.get("recommendations", [])
                        print(f"  ✅ [PhaseBridge] 推荐引擎命中: {rec_result['count']}项, 来源={source}")

                        # ★★★ 后端统一归一化：推荐结果字段对齐到Agent生成格式 ★★★
                        # 前端统一认 title/description/problem_id/knowledge_points，不区分来源
                        normalized_recs = []
                        for item in recommendations:
                            kps_raw = item.get("knowledge_points", "")
                            if isinstance(kps_raw, str):
                                kps_list = [k.strip() for k in kps_raw.split(",") if k.strip()]
                            elif isinstance(kps_raw, list):
                                kps_list = kps_raw
                            else:
                                kps_list = [knowledge_point]

                            # ★★★ 每个item独立判断来源：是复习还是推荐 ★★★
                            reason = item.get("recommendation_reason", "") or ""
                            if "复习" in reason:
                                item_source = "forgetting_curve"
                            elif source == "collaborative":
                                item_source = "collaborative"
                            elif source in ("content_based", "random"):
                                item_source = "content_based"
                            else:
                                item_source = source

                            # ★★★ 携带采纳建议的影响标记 ★★★
                            adoption_reasons = item.get("_adoption_reasons", [])
                            if adoption_reasons:
                                if reason:
                                    reason = reason + " | " + " | ".join(adoption_reasons)
                                else:
                                    reason = " | ".join(adoption_reasons)

                            normalized_recs.append({
                                "title": item.get("topic", "") or item.get("title", "推荐题目"),
                                "description": item.get("content", "")[:500],
                                "problem_id": item.get("id", ""),
                                "difficulty": item.get("difficulty", 3),
                                "knowledge_points": kps_list,
                                "recommendation_reason": reason,
                                "_source_type": item_source,
                            })    #   直接将后端返回数据格式强制映射到前端，当然值在测试才可以这样做

                        resource = {
                            "type": resource_type,
                            "knowledge_point": knowledge_point,
                            "from_recommender": True,
                            "primary_source": source,
                            "recommendations": normalized_recs,
                            "recommendation_count": len(normalized_recs),
                        }
                        # ★★★ 对齐前端期望：从 recommendations[0] 提取 problem 字段 ★★★
                        if normalized_recs:
                            first = normalized_recs[0]
                            resource["problem"] = {
                                "title": first.get("title", "编程练习题"),
                                "description": first.get("content", first.get("description", "")),
                                "knowledge_points": first.get("knowledge_points", [knowledge_point]),
                                "difficulty": first.get("difficulty", "中等"),
                                "examples": first.get("examples", []),
                                "hints": first.get("hints", []),
                                "problem_id": first.get("problem_id", first.get("_id", "")),
                            }
                        if phase_context:
                            resource["phase_context"] = phase_context

                        # ★★★ 推荐引擎路径：将题目也入库到 ResourceDB，供后续 /resource/question/{id} 查询 ★★★
                        if resource_type == "practice" and normalized_recs:
                            problem_data = resource["problem"]
                            await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "question", {
                                "problem_id": problem_data.get("problem_id", ""),
                                "difficulty": problem_data.get("difficulty", "中等"),
                                "knowledge_points": problem_data.get("knowledge_points", [knowledge_point]),
                                "description": problem_data.get("description", ""),
                                "title": problem_data.get("title", "编程练习题"),
                            }, knowledge_point))

                        # 缓存推荐结果
                        await loop.run_in_executor(None, self._store.save, user_id, f"phase_{resource_type}", cid, resource)

                        # ★ 资源已可用 → 触发进度追踪刷新
                        try:
                            from services.phase_progress_tracker import PhaseProgressTracker
                            await PhaseProgressTracker().on_resource_generated(user_id, knowledge_point, resource_type, phase_index)
                        except Exception as e:
                            print(f"  ⚠️ [PhaseBridge] 进度追踪刷新失败（不影响主流程）: {e}")

                        return {
                            "success": True,
                            "cached": False,
                            "resource": resource,
                            "agent": f"recommender_{source}",
                        }
                    else:
                        print(f"  ⚠️ [PhaseBridge] 推荐引擎无匹配，降级到Agent生成")
            except Exception as e:
                print(f"  ⚠️ [PhaseBridge] 推荐引擎查询失败: {e}，降级到Agent生成")

        # 3. Agent 兜底生成
        try:
            if phase_context:
                enhanced_kp = f"{knowledge_point}（{phase_context}）"
                print(f"  🔗 [PhaseBridge] 阶段上下文增强: '{knowledge_point}' → '{enhanced_kp}'")
            else:
                enhanced_kp = knowledge_point

            agent = self._get_agent(resource_type)
            method = getattr(agent, info["method"])

            kwargs = {}
            for param, source in info["param_map"].items():
                if source == "kp":
                    kwargs[param] = enhanced_kp
                elif source == "user_id":
                    kwargs[param] = user_id
                elif source == "kp_info":
                    # ★★★ 补充 student_feature，使理论题能根据学生画像个性化生成 ★★★
                    _features = (await loop.run_in_executor(None, self._get_features, user_id)) or {}
                    kwargs[param] = {"topic": knowledge_point, "course_name": knowledge_point,
                                     "user_input": knowledge_point,
                                     "student_feature": _features,
                                     "phase_context": phase_context, "user_id": user_id}
                else:
                    kwargs[param] = source

            print(f"  🤖 [PhaseBridge] 调度Agent: {resource_type}, 参数: {kwargs}")

            if resource_type == "mindmap":
                result = await method(**kwargs)
                resource = {"type": "mindmap", "knowledge_point": knowledge_point, "mindmap": result}
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "mindmap", result, knowledge_point))
            elif resource_type == "video":
                result = await method(**kwargs)
                resource = {"type": "video", "knowledge_point": knowledge_point, "videos": result.get("videos", [])}
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "video", result, knowledge_point))
            elif resource_type == "practice":
                result = await method(**kwargs)
                resource = {"type": "practice", "knowledge_point": knowledge_point, "problem": result}
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "question", result, knowledge_point))
            elif resource_type == "doc":
                result = await method(**kwargs)
                if result is None:
                    raise RuntimeError(f"doc 生成失败：Agent 返回空结果")
                # ★★★ Agent 返回的是平铺 dict（doc_title/doc_content/file_path/oss_url 在顶层）★★★
                resource = {"type": "doc", "knowledge_point": knowledge_point, "document": result}
                # ★★★ 传播 file_path 和 oss_url 到顶层，供收藏/分享使用 ★★★
                file_path = result.get("file_path", "") or ""
                oss_url = result.get("oss_url", "") or ""
                if file_path:
                    resource["file_path"] = file_path
                if oss_url:
                    resource["oss_url"] = oss_url
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "document", result, knowledge_point))
            elif resource_type == "extension":
                result = await method(**kwargs)
                # ★★★ Agent 直接返回 title/background/principle_extend 等字段，不是 {reading_material: ...} ★★★
                material = result if isinstance(result, dict) else {}
                if not material.get("content"):
                    sections = []
                    for key in ["background", "knowledge_distinguish", "principle_extend",
                                 "mistake_avoid", "application_scene", "personal_suggest"]:
                        val = material.get(key, "")
                        if val:
                            sections.append(val)
                    if sections:
                        material["content"] = "\n\n".join(sections)
                resource = {"type": "extension", "knowledge_point": knowledge_point, "material": material}
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "extension", material, knowledge_point))
            elif resource_type == "question":
                result = await method(**kwargs)
                resource = {"type": "question", "knowledge_point": knowledge_point, "questions": result}
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "question", result, knowledge_point))
            elif resource_type == "ppt":
                result = await method(**kwargs)
                # ★★★ 检查 PPT 是否生成成功，失败时不缓存 ★★★
                if result.get("status") == "error":
                    return {"success": False, "cached": False, "error": result.get("message", "PPT生成失败"), "agent": "ppt"}
                resource = {"type": "ppt", "knowledge_point": knowledge_point, "ppt": result}
                # ★★★ PPT 上传 OSS，供收藏/分享使用 ★★★
                filepath = result.get("filepath", "")
                if filepath and user_id:
                    try:
                        from services.oss_storage import upload_file as oss_upload
                        oss_key = oss_upload(
                            local_path=filepath,
                            user_id=user_id,
                            resource_type="ppt",
                            filename=result.get("filename", ""),
                        )
                        if oss_key:
                            from services.oss_storage import get_public_url
                            oss_url = get_public_url(oss_key)
                            resource["oss_url"] = oss_url
                            resource["oss_key"] = oss_key  # ★★★ 存 key 供后续刷新 URL ★★★
                            resource["filepath"] = filepath
                            print(f"  ✅ [PhaseBridge] PPT 已上传 OSS: {oss_url}")
                    except Exception as e:
                        print(f"  ⚠️ [PhaseBridge] PPT 上传 OSS 失败（不影响本地）: {e}")
                        if filepath:
                            resource["filepath"] = filepath
                await loop.run_in_executor(None, lambda: self._save_to_resource_db(user_id, "ppt", result, knowledge_point))
            else:
                result = await method(**kwargs)
                resource = {"type": resource_type, "knowledge_point": knowledge_point, "data": result}

            resource["_agent"] = resource_type
            resource["_knowledge_point"] = knowledge_point
            resource["from_recommender"] = False

            # 强制生成时跳过缓存和进度追踪（仅返回结果）
            if not force_generate:
                # 4. 缓存到ContentStore
                await loop.run_in_executor(None, self._store.save, user_id, f"phase_{resource_type}", cid, resource)

                # ★ 资源已生成 → 触发进度追踪刷新
                try:
                    from services.phase_progress_tracker import PhaseProgressTracker
                    await PhaseProgressTracker().on_resource_generated(user_id, knowledge_point, resource_type, phase_index)
                except Exception as e:
                    print(f"  ⚠️ [PhaseBridge] 进度追踪刷新失败（不影响主流程）: {e}")

            print(f"  ✅ [PhaseBridge] Agent {resource_type} 调度完成")
            return {"success": True, "cached": False, "resource": resource, "agent": resource_type}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "cached": False, "error": str(e), "agent": resource_type}

    def _save_to_resource_db(self, user_id: str, db_type: str, data: Dict, topic: str):
        """Agent生成的内容自动入库到resource_db + ChromaDB，供后续推荐引擎使用"""
        try:
            recommender = self._get_recommender()
            if not recommender or not recommender.resource_db:
                return
            db = recommender.resource_db

            # ★★★ 同时尝试加载 ChromaDB ★★★
            semantic = None
            try:
                from Agent.children_agent.recommendation.semantic_store import SemanticStore
                semantic = SemanticStore()
            except Exception:
                pass

            if db_type == "question":
                pid = data.get("problem_id", "") or data.get("id", "")
                if not pid:
                    import hashlib
                    pid = f"g_{hashlib.md5(str(user_id + topic).encode()).hexdigest()[:12]}"
                diff_map = {"简单": 1, "中等偏易": 2, "中等": 3, "中等偏难": 4, "困难": 5, "挑战": 5}
                difficulty = diff_map.get(data.get("difficulty", "中等"), 3)
                kps = data.get("knowledge_points", [topic])
                content = data.get("description", "") or data.get("content", "") or str(data)
                pid = db.upsert_question(
                    qid=pid, topic=topic, sub_topic="programming",
                    difficulty=difficulty, knowledge_points=kps,
                    title=data.get("title", ""),
                    content=content, solution=data.get("solution", ""),
                    metadata={"source": "agent_generated", "generated_by": "phase_bridge"},
                )
                print(f"  📦 [PhaseBridge] 题目 {pid} 已入库resource_db（含 metadata.source）")
                # ★★★ 同步写入 ChromaDB ★★★
                if semantic:
                    try:
                        semantic.store_question(
                            qid=pid, topic=topic, sub_topic="programming",
                            difficulty=difficulty, knowledge_points=kps,
                            content=content,
                        )
                    except Exception:
                        pass
            elif db_type == "document":
                doc_id = data.get("doc_id", "") or data.get("id", "")
                if not doc_id:
                    import hashlib
                    doc_id = f"d_{hashlib.md5(str(user_id + topic).encode()).hexdigest()[:12]}"
                db.upsert_document(
                    did=doc_id, category=topic, title=data.get("title", "") or data.get("doc_title", ""),
                    topic=topic, difficulty=3,
                    content=data.get("content", "") or data.get("doc_content", ""),
                )
                print(f"  📦 [PhaseBridge] 文档 {doc_id} 已入库resource_db")
        except Exception as e:
            print(f"  ⚠️ [PhaseBridge] 入库失败（不影响主流程）: {e}")

    async def generate_all_pending(self, user_id: str, phase_index: int) -> Dict[str, Any]:
        phases = self.get_plan_phases(user_id)
        if not phases or phase_index >= len(phases):
            return {"error": "阶段不存在"}
        phase = phases[phase_index]
        result = {"generated": [], "cached": [], "failed": []}
        # ★★★ 对 resource_types 去重（注意力扩容后可能有重复）★★★
        seen_types = set()
        unique_types = []
        for rt in phase.get("resource_types", []):
            if rt not in seen_types:
                seen_types.add(rt)
                unique_types.append(rt)
        for res_type in unique_types:
            for kp in phase.get("knowledge_points", []):
                status = await self.generate_phase_resource(user_id, phase_index, res_type, kp)
                if status["success"]:
                    if status["cached"]:
                        result["cached"].append(status["resource"])
                    else:
                        result["generated"].append(status["resource"])
                else:
                    result["failed"].append({"type": res_type, "kp": kp, "error": status.get("error")})
        return result

    def _cache_id(self, user_id: str, phase_index: int, res_type: str, kp: str) -> str:
        return f"p{phase_index}_{res_type}_{kp}"

    def clear_phase_cache(self, user_id: str, phase_index: int):
        import shutil
        from pathlib import Path
        from memory.content_store import USER_FEATURES_DIR
        user_dir = USER_FEATURES_DIR / user_id / "content"
        if user_dir.exists():
            for f in user_dir.glob(f"phase_*_p{phase_index}_*"):
                f.unlink()
