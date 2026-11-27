"""
Agent协作编排器

三层调度策略：
  1. 独立模式（entry=quick）：无规划时，用户点啥出啥
  2. 管道模式（entry=plan）：有规划时，一个知识点一键生成全套资源
  3. 管道触发（trigger_pipeline）：Conduct层节点末尾自动触发，仅对有规划用户生效

核心设计：
  - SharedContext：Agent之间通过共享上下文传递信息
  - PIPELINES：定义协作模板，编排多Agent协同工作流
  - 入口决定模式，不绑定用户
  - trigger_pipeline()：从 practice_agent.judge_code_async / video_node 等位置自动调用
"""

import asyncio
from typing import Dict, Any, Optional, List
from services.phase_bridge import PhaseResourceBridge, AGENT_REGISTRY
from memory.memory_hub import MemoryHub


# ==================== 共享上下文 ====================

class SharedContext:
    """Agent协作共享上下文——前序Agent的输出可为后序Agent提供依据"""

    def __init__(self):
        self._data = {
            "generated": {},
            "analysis": {},
            "user_profile": {},
            "knowledge_point": "",
            "user_id": "",
            "phase_context": "",
        }

    def set(self, key: str, value: Any):
        keys = key.split(".")
        d = self._data
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    def get(self, key: str, default=None) -> Any:
        keys = key.split(".")
        d = self._data
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
                if d is None:
                    return default
            else:
                return default
        return d

    def get_agent_output(self, agent_type: str) -> Dict:
        return self._data["generated"].get(agent_type, {})

    def has_agent_output(self, agent_type: str) -> bool:
        return agent_type in self._data["generated"]

    def set_analysis(self, key: str, value: Any):
        self._data["analysis"][key] = value

    def get_analysis(self, key: str, default=None) -> Any:
        return self._data["analysis"].get(key, default)

    def update(self, data: Dict):
        for k, v in data.items():
            self._data[k] = v

    def reset(self):
        self._data = {
            "generated": {},
            "analysis": {},
            "user_profile": {},
            "knowledge_point": "",
            "user_id": "",
            "phase_context": "",
        }

    def snapshot(self) -> Dict:
        return dict(self._data)


# ==================== 协作编排器 ====================

class CollaborationOrchestrator:
    """
    Agent协作编排器

    功能：
    - generate_resource()：统一入口，根据 entry 参数路由
    - run_pipeline()：执行管道，顺序调用多个Agent
    - trigger_pipeline()：模块级工具函数，Conduct层节点自动调用，仅对有规划用户生效
    """

    PIPELINES = {
        "full_knowledge_set": {
            "description": "知识点全套资源（文档→导图→练题→视频→拓展→PPT）",
            "trigger": "knowledge_point_clicked",
            "steps": ["doc", "mindmap", "practice", "video", "extension", "ppt"],
        },
        "wrong_answer_remediation": {
            "description": "答错题自动补学（错题解析→巩固题→调整计划）",
            "trigger": "practice_score < 60 or theory_wrong",
            "steps": ["doc", "practice"],
        },
        "post_video_consolidation": {
            "description": "看完视频后理论题巩固",
            "trigger": "video_watch_completed",
            "steps": ["question"],
            "force_refresh": True,
        },
    }

    def __init__(self):
        self._bridge = PhaseResourceBridge()
        self._context = SharedContext()
        self._hub = MemoryHub()

    def _has_active_plan(self, user_id: str) -> bool:
        try:
            return self._hub.planner.has_plan(user_id)
        except Exception:
            return False

    def _get_phase_res_types(self, user_id: str, phase_index: int) -> List[str]:
        try:
            phases = self._bridge.get_plan_phases(user_id)
            if phases and phase_index < len(phases):
                return phases[phase_index].get("resource_types", [])
        except Exception:
            pass
        return ["doc", "mindmap", "practice", "video", "extension"]

    async def generate_resource(
        self,
        user_id: str,
        phase_index: int,
        resource_type: str,
        knowledge_point: str,
        entry: str = "quick",
        cached_only: bool = False,
    ) -> Dict[str, Any]:
        """
        统一资源生成入口

        决策逻辑（由 entry 参数决定，不依赖后端自动推断）：
          1. entry="plan" → 管道模式：用户从学习计划页面点击知识点
             自动生成全套关联资源（文档→导图→练题→视频→拓展）
          2. entry="quick" → 独立模式：用户从智能助手/快速入口
             点啥出啥，只生成指定的一个资源类型

        当 cached_only=True 时，仅查缓存返回，不调用任何Agent。
        """
        if cached_only:
            # ★★★ cached_only: 只查缓存，不生成 ★★★
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, self._load_cached_resources,
                user_id, phase_index, knowledge_point
            )

        if entry == "plan":
            return await self.run_pipeline(
                pipeline_name="full_knowledge_set",
                user_id=user_id,
                phase_index=phase_index,
                knowledge_point=knowledge_point,
            )
        else:
            return await self._bridge.generate_phase_resource(
                user_id=user_id,
                phase_index=phase_index,
                resource_type=resource_type,
                knowledge_point=knowledge_point,
            )

    async def run_pipeline(
        self,
        pipeline_name: str,
        user_id: str,
        phase_index: int,
        knowledge_point: str,
        context: Optional[Dict] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        执行协作管道

        流程：
        1. 查找管道定义
        2. 初始化共享上下文
        3. 顺序执行每个Agent步骤
        4. 汇总结果

        Args:
            force_refresh: 是否强制重新生成，跳过缓存检查
        """
        pipeline = self.PIPELINES.get(pipeline_name)
        if not pipeline:
            return {"success": False, "error": f"未知管道: {pipeline_name}"}
        
        force_refresh = force_refresh or pipeline.get("force_refresh", False)

        self._context.reset()
        self._context.update({
            "user_id": user_id,
            "knowledge_point": knowledge_point,
            "phase_index": phase_index,
        })
        if context:
            self._context.update(context)

        phase_context = ""
        try:
            phases = self._bridge.get_plan_phases(user_id)
            if phases and phase_index < len(phases):
                phase_context = phases[phase_index].get("name", "")
                self._context.set("phase_context", phase_context)
        except Exception:
            pass

        print(f"\n{'='*60}")
        print(f"  🚀 [编排器] 启动管道: {pipeline_name} ({pipeline['description']})")
        print(f"  用户: {user_id} | 知识点: {knowledge_point}")
        print(f"{'='*60}")

        step_results = []
        all_generated = {}

        for step_type in pipeline["steps"]:
            # 检查是否已在管道前序步骤中生成过
            cached = self._context.get_agent_output(step_type)
            if cached:
                print(f"  ⏭️ [编排器] {step_type} 已在上下文中，跳过")
                step_results.append({"agent": step_type, "success": True, "cached": True})
                continue

            cached_data = None
            if not force_refresh:
                # 检查缓存
                cid = f"p{phase_index}_{step_type}_{knowledge_point}"
                cached_data = self._hub.content.load(user_id, f"phase_{step_type}", cid)
                if cached_data:
                    # ★★★ 检查 PPT 缓存是否实际失败（图片生成不完整等）★★★
                    if step_type == "ppt":
                        ppt_inner = cached_data.get("ppt", cached_data)
                        if ppt_inner.get("status") == "error":
                            print(f"  ⚠️ [编排器] PPT 缓存记录为失败({ppt_inner.get('message', '')})，重新生成")
                            cached_data = None
                    # ★★★ 检查 extension 内容是否为空 ★★★
                    if step_type == "extension" and cached_data:
                        material = cached_data.get("material", cached_data)
                        if not material.get("content") and not material.get("title"):
                            print(f"  ⚠️ [编排器] extension 缓存内容为空，重新生成")
                            cached_data = None
                        elif not material.get("content"):
                            # 尝试从子字段拼接 content
                            sections = []
                            for key in ["background", "knowledge_distinguish", "principle_extend",
                                         "mistake_avoid", "application_scene", "personal_suggest"]:
                                val = material.get(key, "")
                                if val:
                                    sections.append(val)
                            if sections:
                                material["content"] = "\n\n".join(sections)
                                cached_data["material"] = material
                            else:
                                print(f"  ⚠️ [编排器] extension 缓存无有效内容字段，重新生成")
                                cached_data = None
            if cached_data:
                print(f"  ⏭️ [编排器] {step_type} 已缓存，跳过")
                # ★★★ 对旧缓存中的 PPT 补充 OSS 上传 ★★★
                if step_type == "ppt":
                    ppt_inner = cached_data.get("ppt", cached_data)
                    filepath = ppt_inner.get("filepath", "") or cached_data.get("filepath", "")
                    oss_url = ppt_inner.get("oss_url", "") or cached_data.get("oss_url", "")
                    if filepath and not oss_url and user_id:
                        try:
                            from services.oss_storage import upload_file as oss_upload
                            oss_key = oss_upload(
                                local_path=filepath,
                                user_id=user_id,
                                resource_type="ppt",
                                filename=ppt_inner.get("filename", ""),
                            )
                            if oss_key:
                                from services.oss_storage import get_public_url
                                oss_url = get_public_url(oss_key)
                                cached_data["oss_url"] = oss_url
                                self._hub.content.save(user_id, f"phase_{step_type}", cid, cached_data)
                                print(f"  ✅ [编排器] PPT 补传 OSS 完成: {oss_url}")
                        except Exception as e:
                            print(f"  ⚠️ [编排器] PPT 补传 OSS 失败: {e}")
                all_generated[step_type] = cached_data
                self._context.set(f"generated.{step_type}", cached_data)
                step_results.append({"agent": step_type, "success": True, "cached": True})
                continue

            print(f"\n  ▶️ [编排器] 步骤: {step_type}")
            result = await self._bridge.generate_phase_resource(
                user_id=user_id,
                phase_index=phase_index,
                resource_type=step_type,
                knowledge_point=knowledge_point,
                force_generate=force_refresh,
            )

            success = result.get("success", False)
            step_results.append({
                "agent": step_type,
                "success": success,
                "cached": result.get("cached", False),
            })

            if success:
                res_data = result.get("resource", {})
                all_generated[step_type] = res_data
                self._context.set(f"generated.{step_type}", res_data)
                print(f"  ✅ [编排器] {step_type} 完成")
            else:
                print(f"  ⚠️ [编排器] {step_type} 失败: {result.get('error', '未知')}")

        total = len(pipeline["steps"])
        succeeded = sum(1 for r in step_results if r["success"])

        # ★★★ 管道结束，清洗脏数据 + 检查阶段是否完成 ★★★
        try:
            from services.phase_progress_tracker import PhaseProgressTracker
            tracker = PhaseProgressTracker()
            await tracker._clean_dirty_completed_kps(user_id, phase_index)
            # 触发阶段完成检查（缓存跳过时 on_resource_generated 不会走，需要这里补）
            await tracker._refresh_knowledge_point(user_id, knowledge_point, phase_index)
        except Exception as e:
            print(f"  ⚠️ [编排器] 进度检查失败: {e}")

        summary = {
            "success": succeeded > 0,
            "pipeline": pipeline_name,
            "total_steps": total,
            "completed": succeeded,
            "failed": total - succeeded,
            "step_results": step_results,
            "generated_resources": all_generated,
            "knowledge_point": knowledge_point,
            "phase_index": phase_index,
        }

        print(f"\n{'='*60}")
        print(f"  ✅ [编排器] 管道完成: {succeeded}/{total} 步骤成功")
        print(f"{'='*60}")

        return summary

    def _load_cached_resources(self, user_id: str, phase_index: int,
                                knowledge_point: str) -> Dict[str, Any]:
        """
        只查 ContentStore 缓存，返回所有已缓存的资源。
        不调用任何 Agent 生成。
        """
        pipeline = self.PIPELINES.get("full_knowledge_set", {})
        steps = pipeline.get("steps", ["doc", "mindmap", "practice", "video", "extension"])

        all_generated = {}
        step_results = []

        for step_type in steps:
            cid = f"p{phase_index}_{step_type}_{knowledge_point}"
            cached_data = self._hub.content.load(user_id, f"phase_{step_type}", cid)
            step_results.append({
                "agent": step_type,
                "success": cached_data is not None,
                "cached": cached_data is not None,
            })
            if cached_data:
                all_generated[step_type] = cached_data

        succeeded = sum(1 for r in step_results if r["success"])
        return {
            "success": succeeded > 0,
            "pipeline": "full_knowledge_set",
            "cached_only": True,
            "total_steps": len(steps),
            "completed": succeeded,
            "failed": len(steps) - succeeded,
            "step_results": step_results,
            "generated_resources": all_generated,
            "knowledge_point": knowledge_point,
            "phase_index": phase_index,
        }

    def select_pipeline_for_type(self, resource_type: str) -> str:
        """根据资源类型选择管道"""
        resource_to_pipeline = {
            "full": "full_knowledge_set",
            "doc": "full_knowledge_set",
            "practice": "full_knowledge_set",
            "video": "full_knowledge_set",
        }
        return resource_to_pipeline.get(resource_type, "full_knowledge_set")

    async def warmup_phase(self, user_id: str, phase_index: int) -> Dict[str, Any]:
        """
        预热某个阶段的所有知识点（供计划加载时后台自动调用）
        """
        loop = asyncio.get_running_loop()
        phases = await loop.run_in_executor(
            None, self._bridge.get_plan_phases, user_id
        )
        if not phases or phase_index >= len(phases):
            return {"error": "阶段不存在"}
        phase = phases[phase_index]
        results = {}
        for kp in phase.get("knowledge_points", []):
            results[kp] = await self.run_pipeline(
                pipeline_name="full_knowledge_set",
                user_id=user_id,
                phase_index=phase_index,
                knowledge_point=kp,
            )
        return {"phase_index": phase_index, "phase_name": phase.get("name", ""), "results": results}

    def get_pipeline_status(self, user_id: str) -> Dict[str, Any]:
        """获取用户当前的管道状态摘要"""
        has_plan = self._has_active_plan(user_id)
        plan_title = ""
        current_phase = None
        if has_plan:
            try:
                summary = self._hub.planner.get_plan_summary(user_id)
                if summary:
                    plan_title = summary.get("title", "")
                    current_phase = summary.get("current_phase", {})
            except Exception:
                pass
        return {
            "has_plan": has_plan,
            "plan_title": plan_title,
            "current_phase": current_phase,
            "pipeline_mode": "pipeline" if has_plan else "independent",
        }


# ==================== 模块级工具函数 ====================


def trigger_pipeline(
    event_type: str,
    user_id: str,
    knowledge_point: str = "",
    context: dict = None,
):
    """
    触发管道（同步 fire-and-forget 版）——仅当用户有学习规划时才执行。
    无规划时静默跳过。

    如需等待执行结果，请使用 trigger_pipeline_async。
    """
    try:
        print(f"\n  🔔 [管道] 收到触发请求: event_type={event_type}, user_id={user_id}")

        orch = CollaborationOrchestrator()
        if not orch._has_active_plan(user_id):
            print(f"  🔔 [管道] 用户无学习计划，跳过触发")
            return

        pipeline_name, kp, phase_index, ctx = _prepare_pipeline_params(
            event_type, user_id, knowledge_point, context
        )
        if not pipeline_name:
            return

        # fire-and-forget：在独立线程或已有事件循环中异步运行
        print(f"  [管道] 启动: {event_type} → {pipeline_name} [知识点: {kp}]")
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(orch.run_pipeline(
                pipeline_name=pipeline_name, user_id=user_id,
                phase_index=phase_index, knowledge_point=kp, context=ctx,
            ), loop)
        except RuntimeError:
            import threading
            def _run():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(orch.run_pipeline(
                        pipeline_name=pipeline_name, user_id=user_id,
                        phase_index=phase_index, knowledge_point=kp, context=ctx,
                    ))
                finally:
                    new_loop.close()
            threading.Thread(target=_run, daemon=True).start()
        print(f"  ✅ [管道] 异步任务已创建")
    except Exception as e:
        print(f"  ❌ [管道] 触发失败: {e}")
        import traceback
        traceback.print_exc()


async def trigger_pipeline_async(
    event_type: str,
    user_id: str,
    knowledge_point: str = "",
    context: dict = None,
) -> Dict[str, Any]:
    """
    触发管道（异步版）——仅当用户有学习规划时才执行。
    返回管道执行结果，方便 API 层获取生成的内容。

    Args:
        event_type: 事件类型，支持 practice_failed / video_completed
        user_id: 用户ID
        knowledge_point: 关联知识点
        context: 额外上下文数据

    Returns:
        管道执行结果 dict，无计划或无事件映射时返回 {"skipped": True, "reason": "..."}
    """
    try:
        print(f"\n  🔔 [管道-异步] 收到触发请求: event_type={event_type}, user_id={user_id}")

        orch = CollaborationOrchestrator()
        if not orch._has_active_plan(user_id):
            print(f"  🔔 [管道-异步] 用户无学习计划，跳过触发")
            return {"skipped": True, "reason": "no_plan", "success": False}

        pipeline_name, kp, phase_index, ctx = _prepare_pipeline_params(
            event_type, user_id, knowledge_point, context
        )
        if not pipeline_name:
            return {"skipped": True, "reason": "unknown_event", "success": False}

        print(f"  [管道-异步] 启动: {event_type} → {pipeline_name} [知识点: {kp}]")
        result = await orch.run_pipeline(
            pipeline_name=pipeline_name,
            user_id=user_id,
            phase_index=phase_index,
            knowledge_point=kp,
            context=ctx,
        )
        print(f"  ✅ [管道-异步] 执行完成: success={result.get('success', False)}")
        return result

    except Exception as e:
        print(f"  ❌ [管道-异步] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def _prepare_pipeline_params(
    event_type: str,
    user_id: str,
    knowledge_point: str = "",
    context: dict = None,
):
    """解析管道参数：事件→管道名、知识点、阶段索引、上下文"""
    event_to_pipeline = {
        "practice_failed": "wrong_answer_remediation",
        "video_completed": "post_video_consolidation",
    }
    pipeline_name = event_to_pipeline.get(event_type)
    print(f"  🔔 [管道] 事件映射: {event_type} → {pipeline_name}")
    if not pipeline_name:
        print(f"  🔔 [管道] 未知事件类型，跳过")
        return None, None, None, None

    kp = knowledge_point or ""
    if not kp and context:
        kp = context.get("knowledge_point", "") or context.get("kp", "")
    
    # ★★★ 用 bvid 从 ResourceDB 检索视频对应的原始知识点（最准确）★★★
    if not kp and context:
        bvid_raw = context.get("bvid", "")
        if bvid_raw:
            bvid = bvid_raw.split("-p")[0] if "-p" in bvid_raw else bvid_raw
            try:
                from Agent.children_agent.recommendation.resource_db import ResourceDB
                _rdb = ResourceDB()
                video = _rdb.get_video(bvid)
                if video and video.get("topic"):
                    kp = video["topic"]
                    print(f"  🔔 [管道] 从 ResourceDB(bvid={bvid}) 检索到知识点: {kp}")
            except Exception as e:
                print(f"  ⚠️ [管道] ResourceDB 检索失败: {e}")

    # ★★★ 兜底：从视频标题提取知识点 ★★★
    if not kp and context:
        video_title = context.get("video_title", "")
        topic = context.get("topic", "")
        if video_title:
            kp = _extract_knowledge_point_from_title(video_title)
            print(f"  ⚠️ [管道] DB无记录，从标题提取知识点: {kp}")
        elif topic:
            kp = topic[:50]
    if not kp:
        kp = "编程"
    print(f"  🔔 [管道] 知识点: {kp}")

    ctx = dict(context or {})
    ctx["event_type"] = event_type

    phase_index = 0
    try:
        orch = CollaborationOrchestrator()
        current = orch._hub.planner.get_current_phase(user_id)
        if current:
            phase_index = current.get("_index", 0)
    except Exception as e:
        print(f"  ⚠️ [管道] 获取阶段索引失败: {e}")
    print(f"  🔔 [管道] 当前阶段索引: {phase_index}")

    return pipeline_name, kp, phase_index, ctx


def _extract_knowledge_point_from_title(title: str) -> str:
    """
    从视频标题中提取知识点。
    优先级：
    1. 括号内的主题关键词（如 (Python全栈开发教程) → Python全栈开发）
    2. "xxx教程/课程/入门到精通" 中的主题部分
    3. 截取标题第一个分隔符前的有意义的短句
    """
    import re
    if not title:
        return "编程"

    # 1. 尝试提取括号内的内容（去掉"教程""课程"等后缀）
    for pattern in [r'\(([^)]*?教程[^)]*?)\)', r'[（]([^）]*?教程[^）]*?)[）]',
                    r'\(([^)]*?课程[^)]*?)\)', r'[（]([^）]*?课程[^）]*?)[）]',
                    r'\(([^)]*?入门[^)]*?)\)', r'[（]([^）]*?入门[^）]*?)[）]']:
        m = re.search(pattern, title)
        if m:
            topic = m.group(1)
            # 去掉尾部冗余词
            for suffix in ["教程", "课程", "入门到精通", "从入门到精通", "入门"]:
                if topic.endswith(suffix):
                    topic = topic[:-len(suffix)]
                    break
            topic = topic.strip()
            if topic and len(topic) <= 30:
                return topic

    # 2. 提取 "xxx教程"/"xxx课程"/"xxx从入门到精通" 模式
    for pattern in [r'([\u4e00-\u9fa5\w]+)[:：]?\s*教程',
                    r'([\u4e00-\u9fa5\w]+)[:：]?\s*课程',
                    r'([\u4e00-\u9fa5\w]+?)(?:从入门到精通|入门到精通)']:
        m = re.search(pattern, title)
        if m:
            topic = m.group(1).strip()
            if topic and len(topic) <= 30:
                return topic

    # 3. 取第一个逗号/分隔符前的内容（去除非知识性前缀）
    for sep in ['，', ',', '！', '!', '——', ' ', '  ']:
        if sep in title:
            parts = title.split(sep)
            # 跳过纯营销话术的前缀
            for part in parts:
                part = part.strip()
                if any(kw in part for kw in ["教程", "课程", "入门", "精通",
                                              "Python", "Java", "前端", "后端",
                                              "编程", "算法", "数据"]):
                    return part[:30]
            break

    # 4. 直接取前 20 个字符，去掉末尾可能的碎片
    raw = title[:20].rstrip("，, Pp1234567890-")
    if raw:
        return raw
    return "编程"
