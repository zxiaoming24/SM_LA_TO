"""
学习路径规划Agent
负责根据用户的时间目标和学习需求，生成结构化的分阶段学习计划
并自动保存到 MemoryHub 的 StudyPlanner 中（用户私有）
"""

import json
import re
import copy
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai
from memory.memory_hub import MemoryHub


class StudyPlanAgent:
    """学习路径规划Agent"""

    def __init__(self):
        self.llm = self._initialize_llm()
        self.template = self._create_template()
        self._hub = MemoryHub()

    def _initialize_llm(self):
        try:
            return get_chat_openai(temperature=0.4, max_tokens=3000, streaming=True)
        except Exception as e:
            raise Exception(f"初始化StudyPlanAgent LLM失败: {e}")

    def _create_template(self) -> PromptTemplate:
        template = """
你是一位资深的课程设计专家和教育规划师，擅长为学生制定个性化的学习路径规划。

**用户画像（当前学习状态）：**
{student_profile}

**用户需求：**
{user_input}

**任务：**
根据用户的时间目标和学习内容需求，制定一份详细、可执行的分阶段学习计划。

**要求：**
1. 计划必须包含多个学习阶段，每个阶段有明确的周数/时间范围
2. 每个阶段列出要掌握的知识点（使用标准中文术语）
3. 为每个阶段推荐合适的学习资源类型（视频/练题/文档/思维导图等）
4. 设置明确的里程碑目标（完成什么算通过这个阶段）
5. 考虑用户画像中的学习风格和节奏（快速学习者 vs 深度思考者等）
6. 难度递进合理，前一个阶段是后一个阶段的基础

**输出格式（JSON，严格遵循）：**
{{
  "title": "计划标题（如：3个月Python入门到实战）",
  "total_duration": "总时长描述（如：3个月）",
  "difficulty": "简单/中等/困难",
  "description": "计划的总体说明（200字以内）",
  "phases": [
    {{
      "phase": 1,
      "name": "阶段名称",
      "weeks": "时间范围描述（如：预计2小时、第1-2周）",
      "description": "本阶段学习目标",
      "knowledge_points": ["知识点1", "知识点2"],
      "resource_types": ["video", "practice", "doc"],
      "milestone": "阶段里程碑（完成什么算通过）",
      "estimated_hours": 10,
      "difficulty": "简单/中等/困难"
    }}
  ],
  "total_estimated_hours": "总预估学习小时数",
  "prerequisites": "前置知识要求"
}}

**说明：**
- knowledge_points 根据用户学习目标和当前领域的标准知识体系来生成，使用业界通用的中文术语命名（如：用户学Python则用"函数定义、列表操作、字典、文件I/O"；学Java则用"集合框架、JVM、多线程、Spring Boot"；学前端的则用"HTML语义化、CSS布局、JavaScript异步编程、React组件"等）
- resource_types 可选：video（看视频）、practice（练题）、doc（读文档）、mindmap（思维导图）
- 阶段数量建议 3-6 个，不宜过多
- 总时长应合理，不要承诺"XX天精通"

只输出JSON格式，不要包含其他内容。
""".strip()
        return PromptTemplate.from_template(template)

    def _build_student_profile(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "新用户，尚无学习记录"
        try:
            hub = MemoryHub()
            feat = hub.features.get_latest_features(user_id)
            if not feat:
                return "新用户，尚无学习记录"

            dims = feat.get("summary_scores", {}).get("dimension_scores", [])
            dim_names = ["学术背景", "学习行为", "目标动机", "认知能力",
                         "情绪状态", "社交互动", "时间管理", "创新创造"]
            lines = [f"{n}={s}" for n, s in zip(dim_names, dims) if dims]
            profile = "\n".join(lines) if lines else "暂无详细画像"

            knowledge = hub.knowledge.get_all_mastery(user_id)[:5]
            if knowledge:
                kp_lines = [f"  {k['knowledge_point']}: 掌握度={k['mastery_level']}" for k in knowledge]
                profile += "\n知识点掌握情况:\n" + "\n".join(kp_lines)

            return profile
        except Exception as e:
            return f"获取画像失败: {e}"

    def _check_weak_points(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """检查用户最新的薄弱点"""
        try:
            from .learning_assessment_agent import LearningAssessmentAgent
            agent = LearningAssessmentAgent()
            weak_points = agent.get_feature_weak_points(user_id)
            # 只返回优先级为"高"的薄弱点
            high_priority = [wp for wp in weak_points if wp.get("priority") == "高"]
            return high_priority if high_priority else None
        except Exception as e:
            print(f"  ⚠️ [学习规划] 检查薄弱点失败: {e}")
            return None

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            match = json_pattern.search(text)
            if match:
                return json.loads(match.group(1))
            obj_pattern = re.compile(r'\{.*\}', re.DOTALL)
            match = obj_pattern.search(text)
            if match:
                return json.loads(match.group(0))
            text = text.strip()
            if text.startswith('{') and text.endswith('}'):
                return json.loads(text)
            return None
        except Exception as e:
            print(f"  ❌ JSON解析失败: {e}")
            return None

    async def generate_plan_async(self, user_input: str, user_id: Optional[str] = None,
                                    ignore_weak_points: bool = False,
                                    focus_weak_points: bool = False) -> Dict[str, Any]:
        try:
            # ★★★ 第一步：检查用户是否有薄弱点（仅在首次调用且无标记时）★★★
            weak_points_info = None
            if user_id and not ignore_weak_points and not focus_weak_points:
                weak_points_info = self._check_weak_points(user_id)
                if weak_points_info:
                    # ★★★ 返回薄弱点信息，让前端弹窗让用户选择 ★★★
                    print(f"  ⚠️ [学习规划] 检测到{len(weak_points_info)}项薄弱点，等待用户确认")
                    return {
                        "status": "weak_points_detected",
                        "weak_points_info": weak_points_info,
                        "message": f"检测到{len(weak_points_info)}个薄弱环节，是否针对这些问题制定学习计划？",
                        "has_weak_points": True
                    }

            profile = self._build_student_profile(user_id)

            # ★★★ 如果用户接受（focus_weak_points），用薄弱点替换用户输入 ★★★
            if focus_weak_points:
                wp_list = self._check_weak_points(user_id)
                if wp_list:
                    wp_text = "\n".join([f"- {w.get('point','')} (优先级: {w.get('priority','')})" for w in wp_list])
                    # ★★★ 完全替换用户输入为薄弱点专项计划 🎯 ★★★
                    user_input = f"""
用户需要重点突破以下薄弱环节，请制定一个专注于解决这些问题的学习计划：

{wp_text}

要求：
- 计划必须围绕上述薄弱点设计，每个阶段都要针对性地解决这些问题
- 在 milestones 中设置针对薄弱点的检验标准
- 优先安排薄弱知识点的学习和练习
"""

            prompt = self.template.format(
                student_profile=profile,
                user_input=user_input
            )

            print("\n📋 [学习规划] 正在生成学习路径计划...")
            response = await self.llm.ainvoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)

            plan = self._parse_json(text)
            if not plan:
                return {"status": "error", "message": "计划生成解析失败"}

            if user_id:
                plan["_user_id"] = user_id
                plan["_created_at"] = datetime.now().isoformat()

                # ★★★ 初始化版本信息（v1 原始方案）★★★
                plan["version_info"] = {
                    "version_number": 1,
                    "parent_plan_id": None,
                    "parent_version_number": None,
                    "trigger_type": "initial",
                    "trigger_description": "原始学习计划",
                    "fork_phase_index": None,
                    "fork_phase_name": None,
                    "created_at": plan["_created_at"],
                }

                for phase in plan.get("phases", []):
                    phase.setdefault("status", "进行中")
                    phase.setdefault("completed_kps", [])

                # ★★★ 异步保存（不阻塞事件循环）★★★
                plan_id = plan.get("plan_id", "")
                saved = await self._hub.planner.save_plan_async(user_id, plan,
                                                                make_active=False,
                                                                root_dir=plan_id)
                if saved:
                    # ★★★ 创建版本族初始条目（v1 为自己祖先）★★★
                    await self._hub.planner.add_version_to_family_async(user_id, plan_id, {
                        "plan_id": plan_id,
                        "version_number": 1,
                        "parent_plan_id": None,
                        "parent_version_number": None,
                        "trigger_type": "initial",
                        "trigger_description": "原始学习计划",
                        "created_at": plan["_created_at"],
                        "phase_count": len(plan.get("phases", [])),
                        "completed_phase_count": 0,
                    })
                    # ★★★ 设置 v1 为族内当前执行中版本 ★★★
                    await self._hub.planner.set_family_active_version_async(user_id, plan_id, plan_id)
                    print(f"  ✅ [学习规划] 已保存到 {user_id} 的私有学习计划")
                else:
                    print(f"  ⚠️ [学习规划] 保存失败")

                # ★★★ 异步记录工作记忆（不阻塞）★★★
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None,
                        self._hub.working.set_current_task,
                        user_id, "study_plan",
                        f"制定了学习计划: {plan.get('title', '')}"
                    )
                except Exception:
                    pass

            return {
                "status": "success",
                "plan": plan,
                "plan_id": plan.get("plan_id", ""),
                "message": f"学习计划「{plan.get('title', '')}」已生成！"
            }

        except Exception as e:
            print(f"  ❌ [学习规划] 生成失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _create_regenerate_template(self) -> PromptTemplate:
        """创建阶段重规划的提示词模板"""
        template = """
你是一位资深的课程设计专家和教育规划师，负责根据学生的已完成阶段表现，动态调整后续学习计划。

**用户画像（当前学习状态）：**
{student_profile}

**原计划信息：**
- 计划标题：{plan_title}
- 计划说明：{plan_description}

**已完成阶段及评估结果：**
{completed_phases_info}

**未完成阶段（需要重新规划）：**
{remaining_phases_info}

**注意力偏好（用户对不同资源类型的投入度）：**
{attention_preferences}

**任务：**
根据已完成阶段的评估结果和用户注意力偏好，重新设计后续未完成的学习阶段。

**要求：**
1. 如果已完成阶段评估分数 < 60，后续阶段应降低难度、增加基础练习
2. 调整各阶段的 resource_types 配比，让用户偏好的资源类型出现更多
3. 避免用户不喜欢的资源类型
4. 确保难度递进合理
5. 为每个阶段设置清晰、可达成的里程碑
6. 总阶段数量可以增减（与原计划不必相同）
7. 必须保留已完成的阶段信息不变

**输出格式（JSON，严格遵循）：**
{{
  "title": "原计划标题（保持不变）",
  "total_duration": "总时长描述",
  "difficulty": "简单/中等/困难",
  "description": "计划的总体说明",
  "phases": [
    {{
      "phase": 在原计划中的阶段编号（已完成阶段保持不变）
    }},
    {{
      "phase": "重新规划后的阶段编号",
      "name": "阶段名称",
      "weeks": "时间范围（如：预计2小时、第X-Y周）",
      "description": "本阶段学习目标",
      "knowledge_points": ["知识点1", "知识点2"],
      "resource_types": ["video", "practice", "doc"],
      "milestone": "阶段里程碑",
      "estimated_hours": "预估小时数",
      "difficulty": "简单/中等/困难",
      "status": "进行中",
      "completed_kps": []
    }}
  ],
  "total_estimated_hours": "总预估学习小时数",
  "prerequisites": "前置知识要求"
}}

只输出JSON格式，不要包含其他内容。
""".strip()
        return PromptTemplate.from_template(template)

    def _get_next_version_number(self, user_id: str, root_plan_id: str) -> int:
        """计算版本族中下一个版本号"""
        try:
            family = self._hub.planner.get_or_create_family(user_id, root_plan_id)
            versions = family.get("versions", [])
            if not versions:
                return 1
            max_v = 0
            for v in versions:
                vn = v.get("version_number", 0) or 0
                if vn > max_v:
                    max_v = vn
            return max_v + 1
        except Exception:
            return 1

    def _generate_version_plan_id(self, title: str, version: int) -> str:
        """为新版本生成唯一 plan_id（含版本号便于识别）"""
        import hashlib
        import threading
        time_part = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw = f"{title}_v{version}_{datetime.now().timestamp()}_{threading.get_ident()}"
        short_hash = hashlib.md5(raw.encode()).hexdigest()[:6]
        return f"plan_{time_part}_v{version}_{short_hash}"

    async def regenerate_phase_async(self, user_id: str,
                                   target_phase_index: int,
                                   plan_id: Optional[str] = None) -> Dict[str, Any]:
        """
        直接修改当前计划中进行中阶段的内容

        适用于用户觉得当前阶段内容不合适、难度不当等场景。
        直接在原计划上修改，不创建新版本，不影响全局计划列表。

        Args:
            user_id: 用户ID
            target_phase_index: 目标阶段索引（从0开始）
            plan_id: 当前计划ID（用于版本族场景，不传则取全局活跃计划）

        Returns:
            {"status": "success", "plan": 更新后的计划, "message": ...}
        """
        try:
            plan = await self._hub.planner.get_plan_async(user_id, plan_id)
            if not plan:
                return {"status": "error", "message": "无学习计划"}

            phases = plan.get("phases", [])
            if target_phase_index >= len(phases):
                return {"status": "error", "message": "阶段索引越界"}

            target_phase = phases[target_phase_index]
            target_status = target_phase.get("status", "")
            if target_status == "已完成":
                return {"status": "error", "message": "已完成阶段不支持重新生成"}

            preserved_lines = []
            for i, p in enumerate(phases[:target_phase_index]):
                assessment = p.get("phase_assessment", {})
                ps = assessment.get("phase_summary", {})
                score = ps.get("score", "N/A")
                preserved_lines.append(
                    f"阶段{i+1}: {p.get('name','')}\n"
                    f"  状态: {p.get('status','')}\n"
                    f"  知识点: {p.get('knowledge_points', [])}\n"
                    f"  评估分数: {score}\n"
                )
            preserved_phases_info = "\n".join(preserved_lines)

            current_phase_info = f"阶段{target_phase_index + 1}: {target_phase.get('name','')}\n" \
                                f"  当前知识点: {target_phase.get('knowledge_points', [])}\n" \
                                f"  当前资源类型: {target_phase.get('resource_types', [])}\n" \
                                f"  当前难度: {target_phase.get('difficulty', '')}\n" \
                                f"  当前里程碑: {target_phase.get('milestone', '')}"

            remaining_lines = []
            for i, p in enumerate(phases[target_phase_index + 1:], start=target_phase_index + 2):
                remaining_lines.append(
                    f"阶段{i}: {p.get('name','')}\n"
                    f"  知识点: {p.get('knowledge_points', [])}\n"
                    f"  难度: {p.get('difficulty', '')}\n"
                )
            remaining_info = "\n".join(remaining_lines) if remaining_lines else "无后续阶段"

            try:
                from Agent.children_agent.recommendation.attention_profile import get_profile
                profile = get_profile(user_id)
                prefs_summary = profile.get_summary()
                attention_preferences = json.dumps(prefs_summary.get("effective", {}), ensure_ascii=False)
            except Exception:
                attention_preferences = "暂无数据"

            profile_str = self._build_student_profile(user_id)

            regenerate_template = self._create_single_phase_regenerate_template()
            prompt = regenerate_template.format(
                student_profile=profile_str,
                plan_title=plan.get("title", ""),
                plan_description=plan.get("description", ""),
                preserved_phases_info=preserved_phases_info,
                target_phase_name=target_phase.get("name", ""),
                target_phase_index=target_phase_index + 1,
                current_phase_info=current_phase_info,
                remaining_phases_info=remaining_info,
                attention_preferences=attention_preferences,
            )

            print(f"\n📋 [学习规划] 正在重新生成阶段{target_phase_index+1}...")
            response = await self.llm.ainvoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)

            llm_result = self._parse_json(text)
            if not llm_result:
                return {"status": "error", "message": "重新生成解析失败"}

            llm_phases = llm_result.get("phases", [])
            if not llm_phases:
                return {"status": "error", "message": "LLM未返回阶段数据"}

            regenerated_phase = llm_phases[0]

            phases[target_phase_index]["name"] = regenerated_phase.get("name", target_phase["name"])
            phases[target_phase_index]["description"] = regenerated_phase.get("description", target_phase.get("description", ""))
            phases[target_phase_index]["knowledge_points"] = regenerated_phase.get("knowledge_points", target_phase["knowledge_points"])
            phases[target_phase_index]["resource_types"] = regenerated_phase.get("resource_types", target_phase.get("resource_types", []))
            phases[target_phase_index]["milestone"] = regenerated_phase.get("milestone", target_phase.get("milestone", ""))
            phases[target_phase_index]["estimated_hours"] = regenerated_phase.get("estimated_hours", target_phase.get("estimated_hours", ""))
            phases[target_phase_index]["difficulty"] = regenerated_phase.get("difficulty", target_phase.get("difficulty", ""))
            phases[target_phase_index]["weeks"] = regenerated_phase.get("weeks", target_phase.get("weeks", ""))

            plan["phases"] = phases

            plan_id = plan.get("plan_id")
            if not plan_id:
                return {"status": "error", "message": "计划ID不存在"}

            root_id = self._hub.planner._find_root_plan_id(user_id, plan_id)
            if root_id and root_id != plan_id:
                saved = await self._hub.planner.save_plan_async(
                    user_id, plan,
                    plan_id=plan_id, make_active=False,
                    root_dir=root_id
                )
                if saved:
                    await self._hub.planner.set_family_active_version_async(user_id, root_id, plan_id)
            else:
                saved = await self._hub.planner.save_plan_async(
                    user_id, plan,
                    plan_id=plan_id, make_active=True
                )
            if not saved:
                return {"status": "error", "message": "保存失败"}

            print(f"  ✅ [学习规划] 已更新阶段{target_phase_index+1}: {phases[target_phase_index]['name']}")

            return {
                "status": "success",
                "plan": plan,
                "plan_id": plan_id,
                "message": f"已重新生成阶段{target_phase_index+1}的内容！"
            }

        except Exception as e:
            print(f"  ❌ [学习规划] 重新生成阶段失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _create_single_phase_regenerate_template(self) -> PromptTemplate:
        """创建单个阶段重新生成的提示词模板"""
        template = """
你是一位资深的课程设计专家和教育规划师，负责根据学生反馈重新设计学习计划中的单个阶段。

**用户画像（当前学习状态）：**
{student_profile}

**原计划信息：**
- 计划标题：{plan_title}
- 计划说明：{plan_description}

**已完成阶段（保留不变）：**
{preserved_phases_info}

**当前需要重新生成的阶段：**
{current_phase_info}

**后续阶段（保持不变，仅作为参考）：**
{remaining_phases_info}

**注意力偏好（用户对不同资源类型的投入度）：**
{attention_preferences}

**任务：**
仅重新设计阶段{target_phase_index}（{target_phase_name}）的内容，后续阶段保持不变。

**要求：**
1. 仅重新生成阶段{target_phase_index}的内容，后续阶段完全保持不变
2. 根据用户画像和注意力偏好调整内容难度和资源类型配比
3. 确保与已完成阶段衔接顺畅，难度递进合理
4. 设置清晰、可达成的里程碑
5. 阶段编号必须为{target_phase_index}

**输出格式（JSON，严格遵循）：**
{{
  "title": "原计划标题（保持不变）",
  "total_duration": "总时长描述",
  "difficulty": "简单/中等/困难",
  "description": "计划的总体说明",
  "phases": [
    {{
      "phase": "{target_phase_index}",
      "name": "阶段名称",
      "weeks": "时间范围（如：预计2小时、第X-Y周）",
      "description": "本阶段学习目标",
      "knowledge_points": ["知识点1", "知识点2"],
      "resource_types": ["video", "practice", "doc"],
      "milestone": "阶段里程碑",
      "estimated_hours": "预估小时数",
      "difficulty": "简单/中等/困难",
      "status": "进行中",
      "completed_kps": []
    }}
  ],
  "total_estimated_hours": "总预估学习小时数",
  "prerequisites": "前置知识要求"
}}

只输出JSON格式，不要包含其他内容。
""".strip()
        return PromptTemplate.from_template(template)

    async def regenerate_remaining_phases_async(self, user_id: str,
                                                 completed_phase_index: int) -> Dict[str, Any]:
        """
        根据已完成阶段的评估结果 + 注意力偏好，创建新版本学习计划

        每次调用都会创建一个全新的计划版本（v2, v3, ...），
        所有历史版本完整保留，通过 version_info 形成版本树。
        新版本自动设为活跃计划。

        Args:
            user_id: 用户ID
            completed_phase_index: 刚完成的阶段索引（从0开始）

        Returns:
            {"status": "success", "plan": 新版本计划, "version_info": ...}
        """
        try:
            plan = await self._hub.planner.get_plan_async(user_id)
            if not plan:
                return {"status": "error", "message": "无学习计划"}

            # 检查是否禁用版本树（直接使用模式）
            if plan.get("_disable_version_tree"):
                return {"status": "skipped", "message": "直接使用模式不支持版本树"}

            phases = plan.get("phases", [])
            if completed_phase_index >= len(phases):
                return {"status": "error", "message": "阶段索引越界"}

            # 1. 构建已完成阶段信息（给LLM的上下文）
            completed_lines = []
            for i in range(completed_phase_index + 1):
                p = phases[i]
                assessment = p.get("phase_assessment", {})
                ps = assessment.get("phase_summary", {})
                score = ps.get("score", "N/A")
                status_str = ps.get("status", "N/A")
                adjustments = assessment.get("adjustments", {})

                completed_lines.append(
                    f"阶段{i+1}: {p.get('name','')}\n"
                    f"  状态: {p.get('status','')}\n"
                    f"  知识点: {p.get('knowledge_points', [])}\n"
                    f"  评估分数: {score}\n"
                    f"  评估状态: {status_str}\n"
                    f"  调整建议: {json.dumps(adjustments, ensure_ascii=False)}\n"
                )
            completed_phases_info = "\n".join(completed_lines)

            # 2. 构建未完成阶段信息（给LLM的上下文）
            remaining_lines = []
            for i in range(completed_phase_index + 1, len(phases)):
                p = phases[i]
                remaining_lines.append(
                    f"阶段{i+1}: {p.get('name','')}\n"
                    f"  知识点: {p.get('knowledge_points', [])}\n"
                    f"  资源类型: {p.get('resource_types', [])}\n"
                    f"  难度: {p.get('difficulty', '')}\n"
                    f"  里程碑: {p.get('milestone', '')}\n"
                )
            remaining_phases_info = "\n".join(remaining_lines) if remaining_lines else "无（所有阶段已完成）"

            # 3. 读取注意力偏好
            try:
                from Agent.children_agent.recommendation.attention_profile import get_profile
                profile = get_profile(user_id)
                prefs_summary = profile.get_summary()
                attention_preferences = json.dumps(prefs_summary.get("effective", {}), ensure_ascii=False)
            except Exception:
                attention_preferences = "暂无数据"

            # 4. 构建prompt
            profile_str = self._build_student_profile(user_id)
            prompt = self._create_regenerate_template().format(
                student_profile=profile_str,
                plan_title=plan.get("title", ""),
                plan_description=plan.get("description", ""),
                completed_phases_info=completed_phases_info,
                remaining_phases_info=remaining_phases_info,
                attention_preferences=attention_preferences,
            )

            print(f"\n📋 [学习规划] 正在根据阶段{completed_phase_index+1}评估结果重规划后续阶段...")
            response = await self.llm.ainvoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)

            llm_result = self._parse_json(text)
            if not llm_result:
                return {"status": "error", "message": "重规划解析失败"}

            llm_phases = llm_result.get("phases", [])
            if len(llm_phases) <= completed_phase_index:
                return {"status": "error", "message": "LLM返回的阶段数不足"}

            # ========================================================
            # ★★★ 新版本逻辑：创建全新计划版本，保留所有历史 ★★★
            # ========================================================

            # 5a. Deep copy 已完成阶段（保留评估数据）
            completed_phases = copy.deepcopy(phases[:completed_phase_index + 1])
            # ★★★ 修复已完成阶段在新版本中的状态：考试已完成但 status 可能还是"进行中"
            #   deep copy 时存在时序问题，原版的 status 可能没来得及设为"已完成"
            #   同时设 acknowledged=True 避免重复弹窗 ★★★
            for cp in completed_phases:
                notif = cp.get("_notification", {})
                if notif.get("exam_completed"):
                    notif["acknowledged"] = True
                    if cp.get("status") != "已完成":
                        cp["status"] = "已完成"

            # 5b. 取 LLM 生成的后续阶段
            remaining_new_phases = copy.deepcopy(llm_phases[completed_phase_index + 1:])

            # 5c. 确定版本号
            parent_version_info = plan.get("version_info", {})
            parent_version = parent_version_info.get("version_number", 1)
            root_id = self._hub.planner._find_root_plan_id(user_id, plan.get("plan_id"))
            if not root_id:
                root_id = plan.get("plan_id")
            next_version = self._get_next_version_number(user_id, root_id)

            # 5d. 构建新版本计划
            now_iso = datetime.now().isoformat()
            new_version_plan = {
                "title": plan.get("title", ""),
                "total_duration": llm_result.get("total_duration", plan.get("total_duration", "")),
                "difficulty": llm_result.get("difficulty", plan.get("difficulty", "")),
                "description": llm_result.get("description", plan.get("description", "")),
                "phases": completed_phases + remaining_new_phases,
                "total_estimated_hours": llm_result.get("total_estimated_hours",
                                                        plan.get("total_estimated_hours", "")),
                "prerequisites": plan.get("prerequisites", ""),
                "version_info": {
                    "version_number": next_version,
                    "parent_plan_id": plan.get("plan_id"),
                    "parent_version_number": parent_version,
                    "trigger_type": "phase_completed",
                    "trigger_description": f"完成阶段{completed_phase_index + 1}：{phases[completed_phase_index].get('name', '')}后调整",
                    "fork_phase_index": completed_phase_index,
                    "fork_phase_name": phases[completed_phase_index].get("name", ""),
                    "created_at": now_iso,
                },
                "_user_id": user_id,
                "_created_at": now_iso,
            }

            # 确保每个阶段有默认字段
            for phase in new_version_plan["phases"]:
                phase.setdefault("status", "进行中")
                phase.setdefault("completed_kps", [])

            # 5e. 生成新 plan_id（含版本号便于识别）
            new_plan_id = self._generate_version_plan_id(
                plan.get("title", ""), next_version
            )

            # 5f. 保存为新计划（不改变全局活跃计划）
            root_id = self._hub.planner._find_root_plan_id(user_id, plan.get("plan_id"))
            if not root_id:
                root_id = plan.get("plan_id")
            saved = await self._hub.planner.save_plan_async(
                user_id, new_version_plan,
                plan_id=new_plan_id, make_active=False,
                root_dir=root_id
            )
            if not saved:
                return {"status": "error", "message": "新版本保存失败"}

            # 5g. 写入版本族文件
            completed_count = sum(1 for p in new_version_plan["phases"]
                                   if p.get("status") == "已完成")

            await self._hub.planner.add_version_to_family_async(user_id, root_id, {
                "plan_id": new_plan_id,
                "version_number": next_version,
                "parent_plan_id": plan.get("plan_id"),
                "parent_version_number": parent_version,
                "trigger_type": "phase_completed",
                "trigger_description": f"完成阶段{completed_phase_index + 1}：{phases[completed_phase_index].get('name', '')}后调整",
                "created_at": now_iso,
                "phase_count": len(new_version_plan["phases"]),
                "completed_phase_count": completed_count,
            })

            # 5h. 设置族内当前执行中版本
            await self._hub.planner.set_family_active_version_async(user_id, root_id, new_plan_id)

            print(f"  ✅ [学习规划] 已创建新版本 v{next_version} (plan_id={new_plan_id})")
            print(f"      parent: v{parent_version} ({plan.get('plan_id', '')})")
            print(f"      触发: {new_version_plan['version_info']['trigger_description']}")

            return {
                "status": "success",
                "plan": new_version_plan,
                "plan_id": new_plan_id,
                "version_info": new_version_plan["version_info"],
                "message": f"基于阶段{completed_phase_index+1}评估结果，已创建新版本 v{next_version}！"
            }

        except Exception as e:
            print(f"  ❌ [学习规划] 重规划失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # ==================== 版本树管理 ====================

    async def get_plan_version_tree_async(self, user_id: str,
                                            plan_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定计划的版本族树结构

        通过版本族文件（_version_families/family_<root>.json）读取数据，
        每个根计划独立存储，互不干扰。

        Args:
            user_id: 用户ID
            plan_id: 当前查看的计划ID。用于定位版本族根。

        Returns:
            {"status": "success", "versions": [...], "active_version_plan_id": "...",
             "active_version": 3, "has_tree": true, "root_plan_id": "..."}
        """
        try:
            if not plan_id:
                return {"status": "success", "versions": [], "active_version_plan_id": None,
                        "active_version": None, "has_tree": False, "root_plan_id": None}

            root_id = self._hub.planner._find_root_plan_id(user_id, plan_id)
            if not root_id:
                root_id = plan_id

            loop = asyncio.get_event_loop()
            family = await loop.run_in_executor(
                None, self._hub.planner.get_or_create_family, user_id, root_id
            )
            versions = family.get("versions", [])
            if not versions:
                return {"status": "success", "versions": [], "active_version_plan_id": None,
                        "active_version": None, "has_tree": False, "root_plan_id": root_id}

            active_version_id = family.get("active_version_id")

            # 补充 is_active 标记和排序
            versions.sort(key=lambda v: v.get("version_number", 1))
            for v in versions:
                v["is_active"] = (v.get("plan_id") == active_version_id)

            active_version = None
            for v in versions:
                if v["is_active"]:
                    active_version = v["version_number"]
                    break

            return {
                "status": "success",
                "versions": versions,
                "active_version_plan_id": active_version_id,
                "active_version": active_version,
                "has_tree": len(versions) >= 1,
                "root_plan_id": root_id,
            }

        except Exception as e:
            print(f"  ❌ [学习规划] 获取版本树失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    async def switch_plan_version_async(self, user_id: str, plan_id: str) -> Dict[str, Any]:
        """
        切换到指定版本计划（仅更新版本树的"当前执行中"指针，不影响全局活跃计划）

        Args:
            user_id: 用户ID
            plan_id: 目标版本的 plan_id

        Returns:
            {"status": "success", "plan": 目标计划, "message": "..."}
        """
        try:
            # 验证计划存在
            plan = await self._hub.planner.get_plan_async(user_id, plan_id)
            if not plan:
                return {"status": "error", "message": "目标版本计划不存在"}

            # ★★★ 定位版本族根，切换族内活跃指针 ★★★
            root_id = self._hub.planner._find_root_plan_id(user_id, plan_id)
            if not root_id:
                root_id = plan_id

            success = await self._hub.planner.set_family_active_version_async(user_id, root_id, plan_id)
            if not success:
                return {"status": "error", "message": "设置版本指针失败"}

            version_info = plan.get("version_info", {})
            version_number = version_info.get("version_number", "?")

            # 更新工作记忆
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    self._hub.working.set_current_task,
                    user_id, "study_plan",
                    f"切换到学习计划 v{version_number}: {plan.get('title', '')}"
                )
            except Exception:
                pass

            return {
                "status": "success",
                "plan": plan,
                "plan_id": plan_id,
                "version_info": version_info,
                "message": f"已切换到 v{version_number} 版本！",
            }

        except Exception as e:
            print(f"  ❌ [学习规划] 切换版本失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _create_continuation_template(self) -> PromptTemplate:
        """创建续期学习计划的提示词模板"""
        template = """
你是一位资深的课程设计专家和教育规划师，负责为学生设计进阶学习路径。

**用户已完成的学习计划：**
- 计划标题：{plan_title}
- 计划说明：{plan_description}
- 总时长：{total_duration}

**已完成阶段：**
{completed_phases_info}

**用户画像（当前学习状态）：**
{student_profile}

**任务：**
用户已成功完成上述学习计划的所有阶段，需要你根据已学内容，设计一个合理的进阶学习计划（续期计划）。

**要求：**
1. 基于已学知识体系，推荐合理的进阶方向
2. 新计划的总时长应当与原计划时长相当或略长
3. 难度应从原计划的最后一个阶段的难度开始，合理递进
4. 每个阶段列出要掌握的知识点，使用业界通用的中文术语
5. 包含 3-6 个阶段
6. 为每个阶段设置清晰的里程碑

**输出格式（JSON，严格遵循）：**
{{
  "title": "续期计划标题（如：Python进阶：Web开发与数据分析）",
  "total_duration": "总时长描述",
  "difficulty": "中等/困难",
  "description": "续期计划的总体说明（200字以内）",
  "phases": [
    {{
      "phase": 1,
      "name": "阶段名称",
      "weeks": "时间范围描述",
      "description": "本阶段学习目标",
      "knowledge_points": ["知识点1", "知识点2"],
      "resource_types": ["video", "practice", "doc"],
      "milestone": "阶段里程碑",
      "estimated_hours": 10,
      "difficulty": "中等/困难"
    }}
  ],
  "total_estimated_hours": "总预估学习小时数",
  "prerequisites": "前置知识要求（基于用户已学内容）"
}}

只输出JSON格式，不要包含其他内容。
""".strip()
        return PromptTemplate.from_template(template)

    async def generate_continuation_async(self, user_id: str) -> Dict[str, Any]:
        """
        当用户完成所有阶段后，生成续期学习计划建议

        Args:
            user_id: 用户ID

        Returns:
            {"status": "success", "proposal": 续期建议, "plan": 新计划} 或 error
        """
        try:
            plan = await self._hub.planner.get_plan_async(user_id)
            if not plan:
                return {"status": "error", "message": "无学习计划"}

            phases = plan.get("phases", [])
            if not phases:
                return {"status": "error", "message": "计划阶段为空"}

            # 检查是否全部完成
            all_completed = all(p.get("status") == "已完成" for p in phases)
            if not all_completed:
                return {"status": "error", "message": "尚有阶段未完成"}

            # 1. 构建已完成阶段信息
            completed_lines = []
            for i, p in enumerate(phases):
                assessment = p.get("phase_assessment", {})
                ps = assessment.get("phase_summary", {})
                score = ps.get("score", "N/A")
                completed_lines.append(
                    f"阶段{i+1}: {p.get('name','')}\n"
                    f"  知识点: {', '.join(p.get('knowledge_points', []))}\n"
                    f"  评估分数: {score}\n"
                    f"  完成用时: {p.get('_actual_hours', 'N/A')} 小时\n"
                )
            completed_phases_info = "\n".join(completed_lines)

            # 2. 构建用户画像
            profile_str = self._build_student_profile(user_id)

            # 3. 构建 prompt
            prompt = self._create_continuation_template().format(
                plan_title=plan.get("title", ""),
                plan_description=plan.get("description", ""),
                total_duration=plan.get("total_duration", ""),
                completed_phases_info=completed_phases_info,
                student_profile=profile_str,
            )

            print(f"\n📋 [学习规划] 正在根据已完成计划生成续期建议...")
            response = await self.llm.ainvoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)

            proposal = self._parse_json(text)
            if not proposal:
                return {"status": "error", "message": "续期建议生成解析失败"}

            print(f"  ✅ [学习规划] 续期学习建议已生成")

            return {
                "status": "success",
                "proposal": proposal,
                "message": f"续期建议「{proposal.get('title', '')}」已生成！",
            }

        except Exception as e:
            print(f"  ❌ [学习规划] 续期建议生成失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def generate_plan(self, user_input: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        from utils.concurrent_executor import run_async
        return run_async(self.generate_plan_async(user_input, user_id))

    def get_plan_version_tree(self, user_id: str,
                               plan_id: Optional[str] = None) -> Dict[str, Any]:
        """同步获取版本树（包装 async 方法）"""
        from utils.concurrent_executor import run_async
        return run_async(self.get_plan_version_tree_async(user_id, plan_id=plan_id))

    def switch_plan_version(self, user_id: str, plan_id: str) -> Dict[str, Any]:
        """同步切换版本（包装 async 方法）"""
        from utils.concurrent_executor import run_async
        return run_async(self.switch_plan_version_async(user_id, plan_id))

    def regenerate_phase(self, user_id: str, target_phase_index: int) -> Dict[str, Any]:
        """同步重新生成阶段（包装 async 方法）"""
        from utils.concurrent_executor import run_async
        return run_async(self.regenerate_phase_async(user_id, target_phase_index))
