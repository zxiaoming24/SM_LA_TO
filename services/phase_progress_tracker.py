"""
phase_progress_tracker.py - 学习阶段进度追踪器

综合多种信号自动计算阶段完成度，并在达标时自动推进到下一阶段。

信号来源和权重：
  - Practice 正确率 ≥ 60%（某个知识点的累计正确率）→ weight 40%
  - 资源已生成（文档/导图/视频/拓展阅读已被缓存）→ weight 30%
  - 知识点掌握度积分 ≥ 3（KnowledgeMasteryGraph）→ weight 30%
  - 总分 ≥ 60% → 该知识点标记完成
  - 阶段内所有知识点完成 → 阶段自动完成，推进到下一阶段
"""

import asyncio
import threading
from typing import Dict, Any, Optional, List
from memory.memory_hub import MemoryHub

def _run_async_safe(coro):
    """从同步上下文中安全地运行异步协程（兼容有无事件循环的情况）"""
    try:
        loop = asyncio.get_running_loop()
        # 已有运行中的事件循环 → 在新线程中创建新事件循环执行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: asyncio.run(coro))
            return future.result(timeout=120)
    except RuntimeError:
        # 没有运行中的事件循环
        return asyncio.run(coro)


class PhaseProgressTracker:
    """学习阶段进度追踪器"""

    EXAM_PASS_SCORE = 60  # 60分及格，与前端提示保持一致

    def __init__(self):
        self._hub = MemoryHub()

    # ==================== 版本族计划解析 ====================

    async def _resolve_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取活跃计划，若存在版本族则解析到版本族的活跃版本。
        确保 handle_exam_choice / submit_exam_answers 等操作的是正确版本。
        """
        plan = await self._hub.planner.get_plan_async(user_id)
        if not plan:
            return None
        plan_id = plan.get("plan_id")
        if not plan_id:
            return plan
        # 追溯母树 → 找版本族 → 加载活跃版本
        root_id = self._hub.planner._find_root_plan_id(user_id, plan_id)
        if not root_id:
            return plan
        all_plans = self._hub.planner.list_plans(user_id)
        root_in_global = any(p.get("plan_id") == root_id for p in all_plans)
        if root_in_global:
            family_ver_id = self._hub.planner.get_family_active_version_id(user_id, root_id)
            if family_ver_id and family_ver_id != plan_id:
                version_plan = await self._hub.planner.get_plan_async(user_id, family_ver_id)
                if version_plan:
                    return version_plan
        return plan

    # ==================== 公开入口 ====================

    async def on_practice_result(self, user_id: str, knowledge_points: List[str],
                                 is_correct: bool, score: float, phase_index: int = None) -> Dict[str, Any]:
        """练题结果信号：答完一道题后调用"""
        if not user_id or not knowledge_points:
            return {"updated": False}
        return await self._refresh_knowledge_point(user_id, knowledge_points[0], phase_index)

    async def on_resource_generated(self, user_id: str, knowledge_point: str,
                                    resource_type: str, phase_index: int = None) -> Dict[str, Any]:
        """资源生成信号：文档/导图/视频/拓展阅读生成后调用"""
        if not user_id or not knowledge_point:
            return {"updated": False}
        return await self._refresh_knowledge_point(user_id, knowledge_point, phase_index)

    # ==================== 核心逻辑 ====================

    async def _refresh_knowledge_point(self, user_id: str, knowledge_point: str, phase_index: int = None) -> Dict[str, Any]:
        """刷新某个知识点的完成状态，如果阶段完成则自动推进"""
        # 如果未指定阶段索引，自动查找（兼容旧调用）
        if phase_index is None:
            phase_index = await self._find_phase_for_kp(user_id, knowledge_point)
        if phase_index is None:
            return {"updated": False, "reason": "知识点不属于任何阶段"}

        # 清洗 completed_kps 中的脏数据（低于 55 分的移除）
        await self._clean_dirty_completed_kps(user_id, phase_index)

        old_completed = await self._get_completed_kps(user_id, phase_index)
        await self._recalculate_kp_completion(user_id, phase_index, knowledge_point)
        new_completed = await self._get_completed_kps(user_id, phase_index)

        updated = len(new_completed) > len(old_completed)

        # 检查是否所有知识点都完成了 → 异步推进
        advanced = False
        if await self._is_phase_complete(user_id, phase_index):
            advanced = await self._advance_to_next_phase(user_id, phase_index)

        return {
            "updated": updated,
            "phase_index": phase_index,
            "completed_kps": list(new_completed),
            "phase_complete": await self._is_phase_complete(user_id, phase_index),
            "advanced": advanced
        }

    async def _find_phase_for_kp(self, user_id: str, knowledge_point: str) -> Optional[int]:
        """查找知识点属于哪个阶段"""
        plan = await self._hub.planner.get_plan_async(user_id)
        if not plan:
            return None
        phases = plan.get("phases", [])
        for i, phase in enumerate(phases):
            kps = phase.get("knowledge_points", [])
            if knowledge_point in kps:
                return i
        return None

    async def _get_completed_kps(self, user_id: str, phase_index: int) -> set:
        """获取某阶段已标记完成的知识点"""
        plan = await self._hub.planner.get_plan_async(user_id)
        if not plan:
            return set()
        phases = plan.get("phases", [])
        if phase_index < 0 or phase_index >= len(phases):
            return set()
        return set(phases[phase_index].get("completed_kps", []))

    async def _clean_dirty_completed_kps(self, user_id: str, phase_index: int):
        """清洗 completed_kps，移除低于 55 分的脏数据"""
        completed = await self._get_completed_kps(user_id, phase_index)
        if not completed:
            return
        to_remove = set()
        for kp in completed:
            score = await self._compute_kp_score(user_id, phase_index, kp)
            if score < 10:
                to_remove.add(kp)
        if to_remove:
            cleaned = completed - to_remove
            await self._hub.planner.update_phase_progress_async(
                user_id, phase_index, completed_kps=list(cleaned)
            )
            print(f"  🧹 [进度追踪] 清洗 {len(to_remove)} 个知识点的脏标记: {to_remove}")

    async def _get_phase_kps(self, user_id: str, phase_index: int) -> List[str]:
        """获取某阶段的所有知识点"""
        plan = await self._hub.planner.get_plan_async(user_id)
        if not plan:
            return []
        phases = plan.get("phases", [])
        if phase_index < 0 or phase_index >= len(phases):
            return []
        return phases[phase_index].get("knowledge_points", [])

    async def _recalculate_kp_completion(self, user_id: str, phase_index: int, target_kp: str = None):
        """重新计算指定知识点的完成状态（不覆盖其他知识点）"""
        kps = await self._get_phase_kps(user_id, phase_index)
        if not kps:
            return

        # 获取当前已完成的知识点集合
        current_completed = await self._get_completed_kps(user_id, phase_index)

        # 确定要检查的知识点：只计算目标知识点
        kps_to_check = [target_kp] if target_kp else kps

        changed = False
        for kp in kps_to_check:
            score = await self._compute_kp_score(user_id, phase_index, kp)
            if score >= 10:
                if kp not in current_completed:
                    current_completed.add(kp)
                    changed = True
            else:
                if kp in current_completed:
                    current_completed.discard(kp)
                    changed = True

        if changed:
            await self._hub.planner.update_phase_progress_async(
                user_id, phase_index, completed_kps=list(current_completed)
            )

    async def _compute_kp_score(self, user_id: str, phase_index: int, knowledge_point: str) -> float:
        """
        计算某个知识点的综合完成度分数 (0-100)

        信号1: Practice 正确率 (60%)
        信号2: 资源已缓存 (20%)
        信号3: 掌握度等级 (20%)
        """
        score_components = []

        # — 信号1: 正确率 (40%) —
        correct_rate = self._get_kp_correct_rate(user_id, knowledge_point)
        sig1 = correct_rate * 60
        score_components.append(("正确率", sig1, 60))

        # — 信号2: 资源已生成 (30%) —
        resource_score = await self._get_kp_resource_score(user_id, phase_index, knowledge_point)
        sig2 = resource_score * 20
        score_components.append(("资源生成", sig2, 20))

        # — 信号3: 掌握度 (30%) —
        mastery_score = self._get_kp_mastery_score(user_id, knowledge_point)
        sig3 = mastery_score * 20
        score_components.append(("掌握度", sig3, 20))

        total = sig1 + sig2 + sig3

        if total > 0 and total < 100:
            names = " + ".join(f"{n}={v:.1f}" for n, v, _ in score_components if v > 0)
            print(f"  📊 [进度追踪] {knowledge_point}: 总分={total:.1f} ({names})")

        return total

    # ———— 子信号计算 ————

    def _get_kp_correct_rate(self, user_id: str, knowledge_point: str) -> float:
        """获取某个知识点的累计正确率 (0.0~1.0)"""
        try:
            mastery = self._hub.knowledge.get_mastery(user_id, knowledge_point)
            total = mastery.get("total_practiced", 0)
            if total == 0:
                return 0.0
            correct = mastery.get("total_correct", 0)
            rate = correct / total
            print(f"    📈 [进度追踪] {knowledge_point}: 练习{total}次, 正确{correct}次, 正确率={rate:.0%}")
            return min(rate, 1.0)
        except Exception as e:
            print(f"    ⚠️ [进度追踪] 获取正确率失败: {e}")
            return 0.0

    async def _get_kp_resource_score(self, user_id: str, phase_index: int, knowledge_point: str) -> float:
        """检查知识点关联的资源是否已缓存 (0.0~1.0)"""
        resource_types = ["doc", "mindmap", "video", "extension", "practice", "question","ppt"]
        cached_count = 0
        for rt in resource_types:
            cid = f"p{phase_index}_{rt}_{knowledge_point}"
            try:
                # 先查 ContentStore
                data = self._hub.content.load(user_id, f"phase_{rt}", cid)
                if data:
                    cached_count += 1
            except Exception:
                pass
        # 也查 practice（走的是 practice_xx 格式）
        try:
            plan = await self._hub.planner.get_plan_async(user_id)
            if plan:
                from pathlib import Path
                import json
                user_dir = Path(__file__).parent.parent / "user_features" / user_id / "practice"
                if user_dir.exists():
                    for f in user_dir.iterdir():
                        if f.suffix == ".json":
                            try:
                                data = json.loads(f.read_text(encoding="utf-8"))
                                kps = data.get("knowledge_points", []) if isinstance(data, dict) else []
                                if knowledge_point in kps:
                                    cached_count += 1
                                    break
                            except Exception:
                                pass
        except Exception:
            pass

        total_types = len(resource_types) + 1
        score = min(cached_count / total_types, 1.0)
        if cached_count > 0:
            print(f"    📦 [进度追踪] {knowledge_point}: 已缓存{cached_count}/{total_types}种资源")
        return score

    def _get_kp_resource_score_sync(self, user_id: str, phase_index: int, knowledge_point: str) -> float:
        """同步版 _get_kp_resource_score（用于已在线程池中的上下文，避免嵌套事件循环死锁）"""
        resource_types = ["doc", "mindmap", "video", "extension", "practice", "question", "ppt"]
        cached_count = 0
        for rt in resource_types:
            cid = f"p{phase_index}_{rt}_{knowledge_point}"
            try:
                data = self._hub.content.load(user_id, f"phase_{rt}", cid)
                if data:
                    cached_count += 1
            except Exception:
                pass
        try:
            plan = self._hub.planner.get_plan(user_id)
            if plan:
                from pathlib import Path
                import json
                user_dir = Path(__file__).parent.parent / "user_features" / user_id / "practice"
                if user_dir.exists():
                    for f in user_dir.iterdir():
                        if f.suffix == ".json":
                            try:
                                data = json.loads(f.read_text(encoding="utf-8"))
                                kps = data.get("knowledge_points", []) if isinstance(data, dict) else []
                                if knowledge_point in kps:
                                    cached_count += 1
                                    break
                            except Exception:
                                pass
        except Exception:
            pass
        total_types = len(resource_types) + 1
        return min(cached_count / total_types, 1.0)

    def _compute_kp_score_sync(self, user_id: str, phase_index: int, knowledge_point: str) -> float:
        """同步版 _compute_kp_score（用于已在线程池中的上下文，避免嵌套事件循环死锁）"""
        correct_rate = self._get_kp_correct_rate(user_id, knowledge_point)
        sig1 = correct_rate * 60

        resource_score = self._get_kp_resource_score_sync(user_id, phase_index, knowledge_point)
        sig2 = resource_score * 20

        mastery_score = self._get_kp_mastery_score(user_id, knowledge_point)
        sig3 = mastery_score * 20

        total = sig1 + sig2 + sig3
        if total > 0 and total < 100:
            names = " + ".join(f"{n}={v:.1f}" for n, v, _ in [
                ("正确率", sig1, 60), ("资源生成", sig2, 20), ("掌握度", sig3, 20)
            ] if v > 0)
            print(f"  📊 [进度追踪] {knowledge_point}: 总分={total:.1f} ({names})")
        return total

    def _get_kp_mastery_score(self, user_id: str, knowledge_point: str) -> float:
        """获取掌握度评分 (0.0~1.0)，基于 mastery_points 积分"""
        try:
            mastery = self._hub.knowledge.get_mastery(user_id, knowledge_point)
            points = float(mastery.get("mastery_points", 0.0))
            level = mastery.get("mastery_level", 0)
            # mastery_points 范围 0~10+，达到 6 分（等级3）即满分
            score = min(points / 6.0, 1.0)
            if level > 0:
                print(f"    🧠 [进度追踪] {knowledge_point}: 积分={points:.1f}, 等级={level}, 评分={score:.0%}")
            return score
        except Exception as e:
            print(f"    ⚠️ [进度追踪] 获取掌握度失败: {e}")
            return 0.0

    # ———— 阶段完成检测 ————

    async def _is_phase_complete(self, user_id: str, phase_index: int) -> bool:
        """检查阶段是否所有知识点都完成了（每个知识点必须达到10分）"""
        plan = await self._hub.planner.get_plan_async(user_id)
        if not plan:
            return False
        phases = plan.get("phases", [])
        if phase_index < 0 or phase_index >= len(phases):
            return False
        phase = phases[phase_index]
        all_kps = phase.get("knowledge_points", [])
        if not all_kps:
            return False
        
        # 验证每个知识点是否真的达到完成阈值
        for kp in all_kps:
            score = await self._compute_kp_score(user_id, phase_index, kp)
            if score < 10:
                return False
        
        return True

    async def _advance_to_next_phase(self, user_id: str, current_index: int) -> bool:
        """阶段完成时触发，异步生成考试题目（不阻塞管道）"""
        from datetime import datetime
        plan = await self._hub.planner.get_plan_async(user_id)
        if not plan:
            return False
        phases = plan.get("phases", [])
        if current_index < 0 or current_index >= len(phases):
            return False

        # ★★★ 检查当前阶段是否已推进过（已有 _notification），避免重复生成 ★★★
        existing_notif = phases[current_index].get("_notification", {})
        if existing_notif.get("phase_index") == current_index:
            # ★★★ 即使通知已存在，也要确保状态为"已完成"（防止之前 save 脏数据导致状态回退）★★★
            if phases[current_index].get("status") != "已完成":
                phases[current_index]["status"] = "已完成"
                plan["phases"] = phases
                await self._hub.planner.save_plan_async(user_id, plan)
                print(f"  🛠️ [进度追踪] 阶段{current_index+1}状态修复为已完成")
            print(f"  ⏭️ [进度追踪] 阶段{current_index+1}已完成推进（通知已存在），跳过重复生成")
            return True

        # 直接在 plan 上修改，避免独立 update_phase_progress 导致脏数据
        phases[current_index]["status"] = "已完成"

        # ★★★ 阶段完成时结算实际用时 ★★★
        active_seconds = phases[current_index].get("_total_active_seconds", 0)
        actual_hours = round(active_seconds / 3600, 2)
        phases[current_index]["_actual_hours"] = actual_hours
        estimated = phases[current_index].get("estimated_hours", "?")
        print(f"  ⏱ [进度追踪] 阶段{current_index+1}用时结算: 计划{estimated}h vs 实际{actual_hours}h")

        # ★★★ 确保所有知识点都已记入 completed_kps ★★★
        all_kps = phases[current_index].get("knowledge_points", [])
        current_completed = set(phases[current_index].get("completed_kps", []))
        missing_kps = [kp for kp in all_kps if kp not in current_completed]
        if missing_kps:
            new_completed = list(current_completed) + missing_kps
            phases[current_index]["completed_kps"] = new_completed
            print(f"  📝 [进度追踪] 同步补全 completed_kps: {missing_kps}")

        # 将通知存入当前阶段的 _notification 字段（每个阶段独立，互不覆盖）
        phases[current_index]["_notification"] = {
            "phase_index": current_index,
            "phase_name": phases[current_index].get("name", f"阶段{current_index+1}"),
            "knowledge_points": phases[current_index].get("knowledge_points", []),
            "triggered_at": datetime.now().isoformat(),
            "acknowledged": False,
            "exam_ready": False,
            "exam_data": None,
            "exam_completed": False,
            "exam_score": None,
            "exam_skipped": False,
        }
        plan["phases"] = phases
        await self._hub.planner.save_plan_async(user_id, plan)

        print(f"  🎉 [进度追踪] 阶段{current_index+1}完成! 考试待用户触发")

        # ★★★ 后台预生成下一阶段的考试题目，不阻塞管道 ★★★
        asyncio.create_task(self._async_generate_exam(user_id, current_index))

        return True

    async def _async_generate_exam(self, user_id: str, phase_index: int):
        """异步生成考试题目（在事件循环中后台运行）"""
        try:
            plan = await self._hub.planner.get_plan_async(user_id)
            if not plan:
                return
            phases = plan.get("phases", [])
            if phase_index >= len(phases):
                return
            notification = phases[phase_index].get("_notification", {})
            if notification.get("phase_index") != phase_index:
                return

            kps = notification.get("knowledge_points", [])
            print(f"  ⏳ [进度追踪] 正在为阶段{phase_index+1}生成考试题目...")
            exam_data = await self._generate_phase_exam_async(user_id, phase_index, kps)

            # 更新当前阶段的 _notification
            phases[phase_index]["_notification"]["exam_ready"] = True
            phases[phase_index]["_notification"]["exam_data"] = exam_data
            # ★★★ 考试已就绪，重置 acknowledged 让前端重新弹窗提示用户 ★★★
            # 但只对未完成考试/未跳过的阶段重置，已完成评估的阶段不受影响
            if not phases[phase_index]["_notification"].get("exam_completed"):
                phases[phase_index]["_notification"]["acknowledged"] = False
            plan["phases"] = phases
            await self._hub.planner.save_plan_async(user_id, plan)

            if exam_data:
                print(f"  ✅ [进度追踪] 阶段{phase_index+1}考试生成完成: "
                      f"{len(exam_data.get('programming_questions',[]))}道编程题 + "
                      f"{len(exam_data.get('theory_questions',[]))}道理论题")
        except Exception as e:
            print(f"  ❌ [进度追踪] 异步生成阶段{phase_index+1}考试失败: {e}")

    async def _generate_phase_exam_async(self, user_id: str, phase_index: int, knowledge_points: List[str]) -> Optional[Dict[str, Any]]:
        """
        为阶段生成考试题目（编程题+理论题）- 纯异步版本
        
        Returns:
            Dict: 包含编程题和理论题的考试数据
        """
        try:
            from Agent.children_agent.practice_agent import PracticeAgent
            from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent
            
            exam_data = {
                "phase_index": phase_index,
                "knowledge_points": knowledge_points,
                "programming_questions": [],
                "theory_questions": [],
                "generated_at": None,
                "total_score": 0
            }
            
            # 生成编程题（1-2道）
            try:
                practice_agent = PracticeAgent()
                for idx, kp in enumerate(knowledge_points[:2]):  # 每个阶段最多2道编程题
                    problem = await practice_agent.generate_problem_async(
                        f"生成一道关于{kp}的编程练习题",
                        user_id=user_id,
                    )
                    if problem and problem.get("title") and problem.get("description"):
                        exam_data["programming_questions"].append({
                            "type": "programming",
                            "knowledge_point": kp,
                            **problem
                        })
            except Exception as e:
                print(f"  ⚠️ [进度追踪] 生成编程题失败: {e}")
            
            # 生成理论题（单选、多选、判断各2道）
            try:
                question_agent = QuestionGeneratorAgent()
                for idx, kp in enumerate(knowledge_points[:3]):  # 每个阶段最多3个知识点的理论题
                    # ★★★ 带重试的理论题生成 ★★★
                    questions = None
                    for attempt in range(3):
                        try:
                            questions = await question_agent.generate_all_questions_async({
                                "user_id": user_id,
                                "course_name": f"阶段{phase_index+1}知识点",
                                "user_input": kp,
                                "learn_level": "intermediate"
                            })
                            if questions and any(q_type in questions for q_type in ["single_choice", "multiple_choice", "judge"]):
                                break
                        except Exception as e:
                            print(f"  ⚠️ [进度追踪] 第{attempt+1}次生成知识点「{kp}」理论题失败: {e}")
                            questions = None
                    if questions:
                        # 提取每种题型的前2道
                        for q_type in ["single_choice", "multiple_choice", "judge"]:
                            if q_type in questions:
                                for q in questions[q_type][:2]:
                                    exam_data["theory_questions"].append({
                                        "type": q_type,
                                        "knowledge_point": kp,
                                        **q
                                    })
            except Exception as e:
                print(f"  ⚠️ [进度追踪] 生成理论题失败: {e}")
            
            # 设置总分
            exam_data["total_score"] = max(len(exam_data["programming_questions"]) * 30 + \
                                         len(exam_data["theory_questions"]) * 10, 1)
            
            if exam_data["programming_questions"] or exam_data["theory_questions"]:
                from datetime import datetime
                exam_data["generated_at"] = datetime.now().isoformat()
                print(f"  ✅ [进度追踪] 阶段{phase_index+1}考试生成完成: {len(exam_data['programming_questions'])}道编程题 + {len(exam_data['theory_questions'])}道理论题")
                return exam_data
            else:
                print(f"  ❌ [进度追踪] 阶段{phase_index+1}考试生成失败：0道编程题 + 0道理论题 "
                      f"(知识点: {knowledge_points})")
                return None
                
        except Exception as e:
            print(f"  ❌ [进度追踪] 生成阶段考试失败: {e}")
            return None

    async def handle_exam_choice(self, user_id: str, phase_index: int, take_exam: bool) -> Dict[str, Any]:
        """
        处理用户的考试选择

        Args:
            user_id: 用户ID
            phase_index: 阶段索引
            take_exam: 是否参加考试

        Returns:
            Dict: 包含操作结果的状态信息
        """
        plan = await self._resolve_plan(user_id)
        if not plan:
            return {"success": False, "reason": "学习计划不存在"}
        
        phases = plan.get("phases", [])
        if phase_index >= len(phases):
            return {"success": False, "reason": "阶段不存在"}
        
        notification = phases[phase_index].get("_notification", {})
        if notification.get("phase_index") != phase_index:
            return {"success": False, "reason": "通知信息不匹配"}
        
        if take_exam:
            # 用户选择参加考试
            notification["exam_skipped"] = False
            
            # 检查考试是否已异步生成完成
            if notification.get("exam_ready") and notification.get("exam_data"):
                print(f"  [进度追踪] 用户选择参加阶段{phase_index+1}考试")
            else:
                # 还没生成完，立即生成（兜底，通常异步任务已经完成了）
                print(f"  [进度追踪] 用户选择参加阶段{phase_index+1}考试，考试尚未完成生成...")
                knowledge_points = notification.get("knowledge_points", [])
                exam_data = await self._generate_phase_exam_async(user_id, phase_index, knowledge_points)
                if exam_data:
                    notification["exam_ready"] = True
                    notification["exam_data"] = exam_data
                else:
                    notification["exam_ready"] = False
                    notification["exam_data"] = None
                    phases[phase_index]["_notification"] = notification
                    plan["phases"] = phases
                    await self._hub.planner.save_plan_async(user_id, plan)
                    return {"success": False, "reason": "考试生成失败，请重试", "exam_data": None}
        else:
            # 用户选择跳过考试 → 推进阶段，但标记下一阶段为"生成中"
            print(f"  [进度追踪] 用户选择跳过阶段{phase_index+1}考试，正在重新规划后续阶段...")
            notification["exam_skipped"] = True

            # ★★★ 把下一阶段标记为"生成中"，前端显示加载状态 ★★★
            next_idx = phase_index + 1
            plan_phases = plan.get("phases", [])
            if next_idx < len(plan_phases):
                plan_phases[next_idx]["status"] = "生成中"
            plan["_regenerating_phases"] = True
            await self._hub.planner.save_plan_async(user_id, plan)

            # 推进阶段（后台线程跑评估+重规划，完成后将"生成中"改为"进行中"）
            await self._complete_phase_and_advance(user_id, phase_index, None)

        # ★★★ 重载计划，避免 _complete_phase_and_advance 写入的 _continuation_pending 被覆盖 ★★★
        plan = await self._resolve_plan(user_id)
        if plan:
            phases = plan.get("phases", [])
            if phase_index < len(phases):
                phases[phase_index]["_notification"] = notification
                plan["phases"] = phases
                await self._hub.planner.save_plan_async(user_id, plan)
        
        return {
            "success": True,
            "take_exam": take_exam,
            "exam_data": notification.get("exam_data"),
            "message": "已确认" if take_exam else "已跳过考试，正在进入下一阶段"
        }

    async def submit_exam_answers(self, user_id: str, phase_index: int, answers: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交考试答案并评分
        
        Args:
            user_id: 用户ID
            phase_index: 阶段索引
            answers: 用户答案 {"question_id": "answer", ...}
            
        Returns:
            Dict: 包含得分和评估结果的信息
        """
        plan = await self._resolve_plan(user_id)
        if not plan:
            return {"success": False, "reason": "学习计划不存在"}

        phases = plan.get("phases", [])
        if phase_index >= len(phases):
            return {"success": False, "reason": "阶段不存在"}

        notification = phases[phase_index].get("_notification", {})
        exam_data = notification.get("exam_data", {})

        if notification.get("phase_index") != phase_index:
            return {"success": False, "reason": "通知信息不匹配"}

        if notification.get("exam_completed"):
            return {"success": False, "reason": "考试已完成"}

        # 计算得分
        score = 0
        total = exam_data.get("total_score", 0)
        results = []
        
        # 评分编程题（调用 PracticeAgent 真实评判）
        from Agent.children_agent.practice_agent import PracticeAgent
        practice_agent = PracticeAgent()
        for idx, pq in enumerate(exam_data.get("programming_questions", [])):
            user_answer = answers.get(f"programming_{idx}", "")
            if user_answer.strip():
                try:
                    judge_result = await practice_agent.judge_code_async(
                        problem_id=pq.get("problem_id", f"exam_{phase_index}_prog_{idx}"),
                        user_code=user_answer,
                        problem=pq,
                        language="python",
                        user_id=user_id,
                    )
                    judge_score = judge_result.get("score", 0)  # 0-100
                    mapped_score = round(judge_score * 30 / 100)  # 映射到30分
                    is_correct = judge_result.get("verdict") == "Accepted"
                    score += mapped_score
                    results.append({
                        "type": "programming",
                        "correct": is_correct,
                        "score": mapped_score,
                        "user_answer": user_answer,
                        "verdict": judge_result.get("verdict", ""),
                        "analysis": judge_result.get("analysis", {}),
                    })
                except Exception as e:
                    print(f"  ⚠️ [进度追踪] 编程题{idx}评判失败: {e}")
                    # 降级：只要有代码就给15分（一半）
                    score += 15
                    results.append({"type": "programming", "correct": False, "score": 15, "user_answer": user_answer})
            else:
                results.append({"type": "programming", "correct": False, "score": 0, "user_answer": ""})
        
        # 评分理论题
        from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent
        import hashlib
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        for idx, tq in enumerate(exam_data.get("theory_questions", [])):
            user_answer = answers.get(f"theory_{idx}", "").strip()
            # ★★★ 未作答直接判错，不给分 ★★★
            if not user_answer:
                result = {"is_correct": False, "score": 0, "correct_answer": tq.get("answer", ""), "user_answer": "", "question_type": tq.get("type", "")}
            else:
                result = await QuestionGeneratorAgent.judge_theory_answer(tq, user_answer, tq.get("type", ""))
            if result["is_correct"]:
                score += 10
            else:
                # ★★★ 错题自动加入错题本 ★★★
                q_text = tq.get("question", "")
                qid = f"exam_{hashlib.md5(q_text.encode()).hexdigest()[:12]}"
                # 从 plan 中获取阶段知识点
                plan_phases = plan.get("phases", [])
                phase_kps = plan_phases[phase_index].get("knowledge_points", []) if phase_index < len(plan_phases) else []
                wa_service.add_wrong_answer(
                    user_id=user_id,
                    question_type=tq.get("type", ""),
                    question_data=tq,
                    user_answer=user_answer,
                    correct_answer=result.get("correct_answer", ""),
                    score=0,
                    question_id=qid,
                    knowledge_points=phase_kps if phase_kps else None,
                    source="exam_theory",
                )
            results.append({
                "type": tq.get("type", ""),
                "correct": result["is_correct"],
                "score": 10 if result["is_correct"] else 0,
                "question": tq.get("question", ""),
                "user_answer": user_answer,
                "correct_answer": result["correct_answer"]
            })
        
        # 评分完成后决定是否锁定（通过才锁定，允许不及格重考）
        exam_passed = score >= self.EXAM_PASS_SCORE
        
        notification["exam_completed"] = exam_passed
        notification["exam_score"] = score
        notification["exam_results"] = results
        phases[phase_index]["_notification"] = notification
        plan["phases"] = phases
        await self._hub.planner.save_plan_async(user_id, plan)
        
        print(f"  📝 [进度追踪] 阶段{phase_index+1}考试完成，得分: {score}/{total}")
        
        if exam_passed:
            # ★★★ 通过 → 推进到下一阶段 ★★★
            await self._complete_phase_and_advance(user_id, phase_index, score)
            return {
                "success": True,
                "score": score,
                "total": total,
                "passed": True,
                "results": results,
                "message": f"恭喜！考试通过（{score}分），即将进入下一阶段"
            }
        else:
            # ★★★ 不及格不推进，exam_completed=False 允许用户重考 ★★★
            return {
                "success": True,
                "score": score,
                "total": total,
                "passed": False,
                "results": results,
                "message": f"考试未通过（{score}分），请复习后重试"
            }

    async def _complete_phase_and_advance(self, user_id: str, phase_index: int, exam_score: Optional[int] = None):
        """
        完成阶段并推进到下一阶段（内部方法）

        同时根据：
        1. 阶段性评估的建议（increase/decrease资源类型）
        2. 注意力偏好画像（眼动/行为）
        动态调整后续阶段的 resource_types
        """
        from datetime import datetime

        plan = await self._resolve_plan(user_id)
        if not plan:
            return

        phases = plan.get("phases", [])
        if phase_index < 0 or phase_index >= len(phases):
            return

        phase_name = phases[phase_index].get("name", f"阶段{phase_index+1}")
        completed_phase = phases[phase_index]

        # ★★★ 标记当前阶段为已完成 ★★★
        completed_phase["status"] = "已完成"
        plan["phases"] = phases
        await self._hub.planner.save_plan_async(user_id, plan)

        # 异步触发阶段性评估（不阻塞主流程）
        try:
            import threading
            t = threading.Thread(
                target=self._run_phase_assessment,
                args=(user_id, phase_index, phases),
                daemon=True
            )
            t.start()
        except Exception as e:
            print(f"  ⚠️ [进度追踪] 触发阶段性评估失败: {e}")

        # ★ 为已完成阶段的知识点安排复习调度 ★
        try:
            completed_kps = completed_phase.get("knowledge_points", [])
            if completed_kps:
                from Agent.children_agent.recommendation.forgetting_curve import ForgettingCurveScheduler
                scheduler = ForgettingCurveScheduler()
                scheduler.schedule_phase_review(user_id, completed_kps)
        except Exception as e:
            print(f"  ⚠️ [进度追踪] 安排阶段复习失败: {e}")

        # 激活下一阶段
        next_index = phase_index + 1
        if next_index < len(phases):
            # 如果已经标记为"生成中"，不覆盖（等待重规划完成后改为"进行中"）
            next_status = phases[next_index].get("status")
            if next_status != "生成中":
                await self._hub.planner.update_phase_progress_async(
                    user_id, next_index, status="进行中"
                )
            # ★★★ 初始化下一阶段的计时器 ★★★
            if phases[next_index].get("_total_active_seconds") is None:
                phases[next_index]["_total_active_seconds"] = 0
                await self._hub.planner.save_plan_async(user_id, plan)
            next_name = phases[next_index].get("name", f"阶段{next_index+1}")
            print(f"  🎉 [进度追踪] 阶段{phase_index+1}({phase_name})完成! 自动推进到下一阶段: {next_name}")
        else:
            print(f"  🎉 [进度追踪] 所有阶段已完成!")

            # ★★★ 所有阶段完成 → 标记续期待接收（用户手动点击"接收"后才生成，不自动触发）★★★
            try:
                plan["_continuation_pending"] = True
                plan.pop("_continuation_proposal", None)
                await self._hub.planner.save_plan_async(user_id, plan, plan_id=plan.get("plan_id"), make_active=False)
                print(f"  🔄 [进度追踪] 所有阶段完成，标记续期待用户确认接收...")
            except Exception as e:
                print(f"  ⚠️ [进度追踪] 标记续期状态失败: {e}")

    def get_exam_data(self, user_id: str, phase_index: int) -> Optional[Dict[str, Any]]:
        """
        获取阶段考试数据

        Args:
            user_id: 用户ID
            phase_index: 阶段索引

        Returns:
            Dict: 考试数据
        """
        plan = self._hub.planner.get_plan(user_id)
        if not plan:
            return None

        # ★★★ 版本族解析（同步版本）★★★
        plan_id = plan.get("plan_id")
        if plan_id:
            root_id = self._hub.planner._find_root_plan_id(user_id, plan_id)
            if root_id:
                all_plans = self._hub.planner.list_plans(user_id)
                if any(p.get("plan_id") == root_id for p in all_plans):
                    family_ver_id = self._hub.planner.get_family_active_version_id(user_id, root_id)
                    if family_ver_id and family_ver_id != plan_id:
                        version_plan = self._hub.planner.get_plan(user_id, family_ver_id)
                        if version_plan:
                            plan = version_plan

        phases = plan.get("phases", [])
        if phase_index >= len(phases):
            return None

        notification = phases[phase_index].get("_notification", {})
        if notification.get("phase_index") == phase_index:
            return notification.get("exam_data")
        return None

    def _run_phase_assessment(self, user_id: str, completed_index: int, phases: list):
        """在后台线程中运行阶段性评估，完成后自动触发后续阶段重规划"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
            agent = LearningAssessmentAgent()
            loop.run_until_complete(
                agent.generate_phase_assessment(user_id, completed_index, phases)
            )
            loop.close()
            print(f"  ✅ [进度追踪] 阶段{completed_index+1}评估完成")

            # ★★★ 评估完成后，自动触发后续阶段重规划（最后一阶段不走重规划，走续期流程）★★★
            is_last_phase = completed_index >= len(phases) - 1
            if not is_last_phase:
                try:
                    import threading
                    t = threading.Thread(
                        target=self._regenerate_remaining_phases,
                        args=(user_id, completed_index),
                        daemon=True
                    )
                    t.start()
                    print(f"  🔄 [进度追踪] 评估完成，已启动后续阶段重规划...")
                except Exception as e:
                    print(f"  ⚠️ [进度追踪] 启动重规划失败: {e}")
            else:
                print(f"  📌 [进度追踪] 最后一阶段完成，不触发重规划（等待续期流程）")

        except Exception as e:
            print(f"  ⚠️ [进度追踪] 后台评估失败: {e}")
            import traceback
            traceback.print_exc()

        return True

    def _regenerate_remaining_phases(self, user_id: str, completed_index: int):
        """在后台线程中重新规划后续阶段（调用LLM）"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from Agent.children_agent.study_plan_agent import StudyPlanAgent
            agent = StudyPlanAgent()
            result = loop.run_until_complete(
                agent.regenerate_remaining_phases_async(user_id, completed_index)
            )
            loop.close()
            if result.get("status") == "success":
                version_info = result.get("version_info", {})
                vn = version_info.get("version_number", "?")
                new_plan_id = result.get("plan_id", "")
                print(f"  ✅ [进度追踪] 已创建新版本 v{vn} (plan_id={new_plan_id})")
                print(f"      阶段数: {len(result['plan'].get('phases', []))}")

                # ★★★ 清除原计划的 _regenerating_phases 标记 ★★★
                try:
                    old_plan = self._hub.planner.get_plan(user_id)
                    if old_plan and old_plan.get("_regenerating_phases"):
                        old_plan.pop("_regenerating_phases", None)
                        self._hub.planner.save_plan(user_id, old_plan)
                        print(f"  ✅ [进度追踪] 已清除原计划的 _regenerating_phases 标记")
                except Exception as e:
                    print(f"  ⚠️ [进度追踪] 清除 _regenerating_phases 失败: {e}")

                # ★★★ 新版本计划中所有阶段状态已正确设置，无需额外修改 ★★★

            else:
                print(f"  ⚠️ [进度追踪] 重规划未完成: {result.get('message', '')}")
        except Exception as e:
            print(f"  ⚠️ [进度追踪] 后台重规划失败: {e}")
            import traceback
            traceback.print_exc()
        return True

    def _generate_continuation_proposal(self, user_id: str):
        """在后台线程中生成续期学习计划建议（所有阶段完成时调用）"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from Agent.children_agent.study_plan_agent import StudyPlanAgent
            agent = StudyPlanAgent()
            result = loop.run_until_complete(
                agent.generate_continuation_async(user_id)
            )
            loop.close()
            if result.get("status") == "success":
                proposal = result.get("proposal", {})
                print(f"  ✅ [进度追踪] 续期建议生成完成: {proposal.get('title', '')}")

                # ★★★ 更新标志 ★★★
                from memory.study_planner import StudyPlanner
                planner = StudyPlanner()
                updated_plan = planner.get_plan(user_id)
                if updated_plan:
                    updated_plan["_continuation_pending"] = False
                    updated_plan["_continuation_proposal"] = proposal
                    planner.save_plan(user_id, updated_plan, plan_id=updated_plan.get("plan_id"), make_active=False)
                    print(f"  ✅ [进度追踪] 续期建议已就绪，等待用户确认")
            else:
                print(f"  ⚠️ [进度追踪] 续期建议生成失败: {result.get('message', '')}")
        except Exception as e:
            print(f"  ⚠️ [进度追踪] 后台续期生成失败: {e}")
            import traceback
            traceback.print_exc()
        return True

    # ==================== 查询接口 ====================

    def get_phase_detail(self, user_id: str, phase_index: int) -> Optional[Dict[str, Any]]:
        """获取某阶段的详细进度"""
        plan = self._hub.planner.get_plan(user_id)
        if not plan:
            return None
        phases = plan.get("phases", [])
        if phase_index < 0 or phase_index >= len(phases):
            return None

        phase = phases[phase_index]
        all_kps = phase.get("knowledge_points", [])
        completed_kps = set(phase.get("completed_kps", []))

        kp_details = []
        for kp in all_kps:
            score = 100 if kp in completed_kps else self._compute_kp_score_sync(user_id, phase_index, kp)
            kp_details.append({
                "name": kp,
                "completed": kp in completed_kps,
                "score": score,
            })

        return {
            "phase_index": phase_index,
            "phase_name": phase.get("name", ""),
            "status": phase.get("status", "进行中"),
            "total_knowledge_points": len(all_kps),
            "completed_kps": len(completed_kps),
            "progress": f"{len(completed_kps)}/{len(all_kps)}",
            "knowledge_point_details": kp_details
        }

    def get_all_phases_progress(self, user_id: str) -> List[Dict[str, Any]]:
        """获取所有阶段的进度"""
        plan = self._hub.planner.get_plan(user_id)
        if not plan:
            return []
        phases = plan.get("phases", [])
        return [
            self.get_phase_detail(user_id, i)
            for i in range(len(phases))
        ]
