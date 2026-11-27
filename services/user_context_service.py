"""
user_context_service.py - 用户实时上下文聚合服务

核心功能：
1. 从多个数据源聚合用户实时上下文（错题、练题结果、掌握度、页面状态等）
2. 为 ChatAgent 提供"环境感知"能力
3. 接收并存储前端上报的页面上下文

数据源整合：
- MemoryHub → 知识点掌握度、学习统计、特征画像、复习计划
- WrongAnswerService → 最近错题记录
- 前端上报 → 用户当前页面、当前操作

重要设计原则：
- 所有可能阻塞的 IO 操作必须异步执行（asyncio.to_thread）
- 单点故障不扩散：每个数据源独立 try/except
- 有超时保护：超过 1.5s 返回空上下文，不阻塞主流程
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime


# 上下文聚合超时（秒）：超过这个时间就返回空，不阻塞对话
# 注意：recall_three_tier 会读取 ChromaDB（磁盘IO），5s 是合理阈值
CONTEXT_TIMEOUT_SECONDS = 5.0


# ==================== 内存存储：前端页面上下文 ====================
# 键: user_id, 值: 最近一次上报的页面上下文
_page_context_store: Dict[str, Dict[str, Any]] = {}
_context_lock: Optional[asyncio.Lock] = None

def _get_context_lock() -> asyncio.Lock:
    """延迟创建 asyncio.Lock，确保绑定到当前运行的事件循环"""
    global _context_lock
    if _context_lock is None:
        _context_lock = asyncio.Lock()
    return _context_lock


class UserContextService:
    """
    用户上下文聚合服务
    提供统一的"用户现在在做什么、状态如何"查询接口
    所有可能阻塞的操作都是异步的。
    """

    def __init__(self):
        self._memory_hub = None
        self._wrong_answer_service = None
        self._loop = None

    # ------------------------------------------------------------------
    # 延迟加载依赖（避免循环导入）
    # ------------------------------------------------------------------

    @property
    def memory_hub(self):
        if self._memory_hub is None:
            from memory import get_shared_memory_hub
            self._memory_hub = get_shared_memory_hub()
        return self._memory_hub

    @property
    def wrong_answer_service(self):
        if self._wrong_answer_service is None:
            from services.wrong_answer_service import WrongAnswerService
            self._wrong_answer_service = WrongAnswerService()
        return self._wrong_answer_service

    # ------------------------------------------------------------------
    # 页面上下文管理（纯内存操作，同步即可，现在已经修改为异步情况）
    # ------------------------------------------------------------------

    async def update_page_context(self, user_id: str, context: Dict[str, Any]) -> bool:
        """接收前端上报的页面上下文"""
        global _page_context_store
        context["_updated_at"] = datetime.now().isoformat()
        async with _get_context_lock():
            _page_context_store[user_id] = context
        return True

    async def get_page_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户最近一次上报的页面上下文（5分钟内有效）"""
        async with _get_context_lock():
            ctx = _page_context_store.get(user_id)
            if ctx:
                try:
                    updated = datetime.fromisoformat(ctx["_updated_at"])
                    if (datetime.now() - updated).total_seconds() > 300:
                        return None
                except Exception:
                    pass
            return ctx

    # ------------------------------------------------------------------
    # 核心：异步构建完整用户上下文
    # ------------------------------------------------------------------

    async def build_full_context_async(self, user_id: str) -> Dict[str, Any]:
        """
        异步构建完整的用户实时上下文（所有阻塞操作在线程池中执行）

        Args:
            user_id: 用户ID

        Returns:
            Dict 包含所有上下文信息（部分数据源失败不影响整体）
        """
        result = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "page_context": (await self.get_page_context(user_id)) or {},
        }

        # ===== 并发执行多个数据源获取 =====
        async def _fetch_memory():
            try:
                recall = await asyncio.to_thread(
                    self.memory_hub.recall,
                    user_id=user_id,
                    include_working=True,
                    include_knowledge=True,
                    include_features=True,
                    include_stats=True,
                    include_reviews=True,
                    include_study_plan=True,
                )
                result["memory"] = recall
            except Exception as e:
                result["memory"] = {"error": str(e)}

        async def _fetch_wrong_answers():
            try:
                wrong = await asyncio.to_thread(
                    self.wrong_answer_service.get_wrong_answers,
                    user_id=user_id,
                    page=1,
                    page_size=5,
                    show_resolved=False,
                )
                records = wrong.get("records", [])
                recent_wrong = []
                for r in records[:3]:
                    recent_wrong.append({
                        "id": r.get("record_id", ""),
                        "type": r.get("question_type", ""),
                        "score": r.get("score", 0),
                        "attempts": r.get("attempt_count", 1),
                        "knowledge_points": r.get("knowledge_points", "").split(",") if r.get("knowledge_points") else [],
                        "created_at": r.get("created_at", ""),
                    })
                result["recent_wrong_answers"] = recent_wrong
                result["wrong_answer_count"] = wrong.get("total", 0)
            except Exception as e:
                result["recent_wrong_answers"] = []
                result["wrong_answer_count"] = 0

        async def _fetch_wrong_stats():
            """获取错题统计数据（总待巩固数、总已掌握数、各类型分布）"""
            try:
                # 待巩固数量
                pending = await asyncio.to_thread(
                    self.wrong_answer_service.get_wrong_answers,
                    user_id=user_id, page=1, page_size=1, show_resolved=False,
                )
                pending_total = pending.get("total", 0)

                # 已掌握数量
                mastered = await asyncio.to_thread(
                    self.wrong_answer_service.get_mastered_answers,
                    user_id=user_id, page=1, page_size=1,
                )
                mastered_total = mastered.get("total", 0)

                result["wrong_answer_stats"] = {
                    "pending_count": pending_total,
                    "mastered_count": mastered_total,
                    "total_count": pending_total + mastered_total,
                }
            except Exception as e:
                result["wrong_answer_stats"] = {"error": str(e)}

        await asyncio.gather(
            _fetch_memory(),
            _fetch_wrong_answers(),
            _fetch_wrong_stats(),
            return_exceptions=True,
        )
        return result

    # ------------------------------------------------------------------
    # 异步构建可直接拼入 LLM Prompt 的上下文文本
    # ------------------------------------------------------------------

    async def build_context_prompt_async(self, user_id: str) -> str:
        """
        异步构建可注入 ChatAgent prompt 的上下文文本。
        带超时保护：超过 CONTEXT_TIMEOUT_SECONDS 返回空字符串。

        Returns:
            str: 格式化的上下文文本（超时返回空）
        """
        # ★★★ 每次构建上下文时后台清理超过1天的旧聊天记录 ★★★
        try:
            from memory.comprehensive_user_memory import UserMemoryManager
            asyncio.ensure_future(asyncio.to_thread(
                lambda: UserMemoryManager()._auto_cleanup_if_needed(user_id, max_age_days=1)
            ))
        except Exception:
            pass

        try:
            ctx = await asyncio.wait_for(
                self.build_full_context_async(user_id),
                timeout=CONTEXT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            print(f"   ⏰ 用户上下文聚合超时（>{CONTEXT_TIMEOUT_SECONDS}s），跳过上下文注入")
            return ""
        except Exception as e:
            print(f"   ⚠️ 用户上下文聚合失败: {e}")
            return ""

        if not ctx:
            return ""

        parts = []

        # ===== 1. 页面上下文 =====
        page_ctx = ctx.get("page_context", {})
        if page_ctx:
            page_parts = ["【用户当前页面】"]
            page = page_ctx.get("page", "unknown")
            title = page_ctx.get("title", "")
            action = page_ctx.get("action", "")
            detail = page_ctx.get("detail", "")

            page_names = {
                "agent_test": "智能助手",
                "study_plan": "学习计划",
                "wrong_answers": "错题本",
                "community": "学习社区",
                "assessment": "学习评估",
                "companion": "学伴匹配",
            }
            page_parts.append(f"  当前页面: {page_names.get(page, page)}")
            if title:
                page_parts.append(f"  页面标题: {title}")
            if action:
                page_parts.append(f"  当前操作: {action}")
            if detail and detail != "得分: ":
                page_parts.append(f"  操作详情: {detail}")
            parts.append("\n".join(page_parts))

        # ===== 2. 错题统计概览 =====
        wrong_stats = ctx.get("wrong_answer_stats", {})
        if wrong_stats and "error" not in wrong_stats:
            total = wrong_stats.get("total_count", 0)
            pending = wrong_stats.get("pending_count", 0)
            mastered = wrong_stats.get("mastered_count", 0)
            if total > 0:
                parts.append(f"【错题统计】共 {total} 道错题记录，待巩固 {pending} 道，已掌握 {mastered} 道")

        # ===== 3. 最近做题结果 =====
        wrong_list = ctx.get("recent_wrong_answers", [])
        if wrong_list:
            wrong_parts = ["【最近做题情况】"]
            for w in wrong_list[:3]:
                kp_str = "、".join(w.get("knowledge_points", [])) if w.get("knowledge_points") else "未知"
                wrong_parts.append(
                    f"  - 题目类型: {w['type']}, 得分: {w['score']}/100, "
                    f"已错{w['attempts']}次, 知识点: {kp_str}"
                )
            if ctx.get("wrong_answer_count", 0) > 3:
                wrong_parts.append(f"  (还有{ctx['wrong_answer_count'] - 3}道错题待巩固)")
            parts.append("\n".join(wrong_parts))

        # ===== 3~6: 从 MemoryHub recall 结果中提取 =====
        memory = ctx.get("memory", {})
        if not memory or "error" in memory:
            return "\n\n".join(parts) if parts else ""

        km = memory.get("knowledge_mastery", {})
        if km and "error" not in km:
            weak = km.get("weak_points", [])
            due = km.get("due_reviews", [])
            if weak:
                weak_parts = ["【薄弱知识点】"]
                for w in weak[:3]:
                    weak_parts.append(f"  - {w.get('knowledge_point', '')} "
                                     f"(掌握度: {w.get('mastery_level', 0)}/10)")
                parts.append("\n".join(weak_parts))
            if due and len(due) > 0:
                due_names = [d.get('knowledge_point', '') for d in due[:5] if d.get('knowledge_point')]
                due_text = "、".join(due_names) if due_names else ""
                parts.append(f"【知识点复习提醒】有 {len(due)} 个知识点到遗忘曲线复习时间{'：' + due_text if due_text else ''}")

        # ===== 复习计划（资源级） =====
        rs = memory.get("review_schedule", {})
        if rs and "error" not in rs:
            due_today = rs.get("due_today", 0)
            mastered = rs.get("mastered", 0)
            if due_today > 0 or mastered > 0:
                parts.append(f"【资源复习统计】待复习 {due_today} 个，已掌握 {mastered} 个")

        ls = memory.get("learning_stats", {})
        if ls and "error" not in ls:
            total = ls.get("total_solved", 0)
            acc = ls.get("accuracy", 0)
            if total > 0:
                parts.append(f"【学习统计】共做题 {total} 道, 正确率 {acc}%")

        # ===== 工作记忆（最近生成的资源，优先于学习计划展示） =====
        wm = memory.get("working_memory", {})
        session_ctx = wm.get("session_context", "") if wm and "error" not in wm else ""
        if session_ctx and "视频回溯" in session_ctx:
            # ★★★ 视频回溯上下文 — 用户刚标记困惑，需优先处理 ★★★
            parts.append(
                "【⚠️ 视频回溯-用户刚标记困惑，优先处理】\n"
                f"{session_ctx}"
            )
        elif session_ctx:
            parts.append(session_ctx)

        sp = memory.get("study_plan", {})
        if sp and "error" not in sp:
            sp_parts = ["【学习计划】"]
            title = sp.get("title", "")
            if title:
                sp_parts.append(f"  计划: {title}")
            progress = sp.get("progress", "")
            if progress:
                sp_parts.append(f"  进度: {progress} 阶段完成")
            total_duration = sp.get("total_duration", "")
            if total_duration:
                sp_parts.append(f"  周期: {total_duration}")
            cur = sp.get("current_phase", {})
            if isinstance(cur, dict):
                cur_name = cur.get("name", "")
                if cur_name:
                    sp_parts.append(f"  当前阶段: {cur_name}")
                cur_kps = cur.get("knowledge_points", [])
                if cur_kps:
                    kp_str = "、".join(cur_kps[:5])
                    sp_parts.append(f"  阶段知识点: {kp_str}")
                cur_status = cur.get("status", "")
                if cur_status:
                    sp_parts.append(f"  阶段状态: {cur_status}")
            if len(sp_parts) > 1:
                parts.append("\n".join(sp_parts))

        feat = memory.get("features", {})
        if feat and "error" not in feat:
            emotion = feat.get("emotional_state", {})
            emotion_items = []
            if emotion.get("interest_level"):
                emotion_items.append(f"兴趣={emotion['interest_level']}")
            if emotion.get("confidence_level"):
                emotion_items.append(f"自信={emotion['confidence_level']}")
            if emotion.get("anxiety_level"):
                emotion_items.append(f"焦虑={emotion['anxiety_level']}")
            if emotion_items:
                parts.append(f"【情绪状态】{' '.join(emotion_items)}")

        return "\n\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # 【三层记忆架构】异步构建 Prompt
    # ------------------------------------------------------------------

    async def build_three_tier_prompt_async(self, user_id: str) -> str:
        """
        基于三层记忆架构异步构建 Prompt 上下文文本。
        带超时保护：超过 CONTEXT_TIMEOUT_SECONDS 返回空字符串。

        相比 build_context_prompt_async()：
        - 显式区分短期/中期/长期记忆
        - 中期记忆按时间窗口（今天/昨天/本周/更早）组织
        - LLM 更容易理解信息的时效性
        """
        try:
            ctx = await asyncio.wait_for(
                asyncio.to_thread(
                    self.memory_hub.build_three_tier_prompt,
                    user_id
                ),
                timeout=CONTEXT_TIMEOUT_SECONDS
            )
            # 检测视频回溯事件，添加优先级标记
            if "视频回溯" in ctx:
                ctx = "【⚠️ 视频回溯-用户刚标记困惑，优先处理】\n" + ctx
            return ctx
        except asyncio.TimeoutError:
            print(f"   ⏰ 三层上下文聚合超时（>{CONTEXT_TIMEOUT_SECONDS}s），降级使用传统上下文")
            return await self.build_context_prompt_async(user_id)
        except Exception as e:
            print(f"   ⚠️ 三层上下文构建失败: {e}")
            return await self.build_context_prompt_async(user_id)

    # ------------------------------------------------------------------
    # 同步版本保留给不需要异步的场景（不推荐新代码使用）
    # ------------------------------------------------------------------

    def build_full_context(self, user_id: str) -> Dict[str, Any]:
        """同步版本 - 已废弃，请使用 build_full_context_async"""
        # ★★★ 修复：检测是否已有运行中的事件循环，避免 asyncio.run() 崩溃 ★★★
        try:
            asyncio.get_running_loop()
            # 已有事件循环 → 在独立线程中运行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(lambda: asyncio.run(self.build_full_context_async(user_id)))
                return future.result()
        except RuntimeError:
            # 无事件循环 → 可直接使用 asyncio.run()
            return asyncio.run(self.build_full_context_async(user_id))

    def build_context_prompt(self, user_id: str) -> str:
        """同步版本 - 已废弃，请使用 build_context_prompt_async"""
        try:
            try:
                asyncio.get_running_loop()
                # 已有事件循环 → 在独立线程中运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        lambda: asyncio.run(
                            asyncio.wait_for(
                                self.build_context_prompt_async(user_id),
                                timeout=CONTEXT_TIMEOUT_SECONDS
                            )
                        )
                    )
                    return future.result()
            except RuntimeError:
                # 无事件循环 → 可直接使用 asyncio.run()
                return asyncio.run(
                    asyncio.wait_for(
                        self.build_context_prompt_async(user_id),
                        timeout=CONTEXT_TIMEOUT_SECONDS
                    )
                )
        except (asyncio.TimeoutError, Exception):
            return ""
