"""
学习效果评估Agent
实时跟踪学习行为、练习测试、资源使用反馈等数据，
依托大模型分析能力实现多维度精准评估，
并根据评估结果动态调整学习资源推送策略和学习计划。
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai
from utils.async_llm_caller import call_llm_with_retry
from memory.memory_hub import MemoryHub


class LearningAssessmentAgent:
    """学习效果评估Agent"""

    def __init__(self):
        self.llm = get_chat_openai(temperature=0.3, max_tokens=4000)
        self.template = self._create_template()
        self._hub = MemoryHub()

    def _create_template(self) -> PromptTemplate:
        template = """
你是一位资深教育评估专家，擅长基于多维度数据对学生的学习效果进行精准分析，并提供可执行的改进建议。

## 用户当前学习数据

### 1. 8维度特征画像
{feature_profile}

### 2. 特征变化趋势（近期更新记录）
{feature_trends}

### 3. 知识点掌握情况
{knowledge_mastery}

### 4. 学习统计
{learning_stats}

### 5. 错题本概况
{wrong_answer_stats}

### 6. 当前学习计划
{study_plan}

### 7. 近期对话上下文
{recent_context}

### 8. 专注度与情绪数据（摄像头检测）
{attention_data}

### 9. 上一阶段评估结果（如有，作为本阶段评估的参考上下文）
{phase_context}

---

## 分析任务

请基于以上数据，从以下维度进行全面评估：

### 一、学习效果综合评估
- 总体学习效果评分（0-100）
- 学习状态判断（快速进步/稳步提升/遇到瓶颈/需要干预）
- 结合专注度数据评估学习投入质量

### 二、分维度分析（每个维度独立评估）
1. **基础知识掌握度**：当前知识储备是否扎实，薄弱知识点
2. **学习行为与习惯**：学习节奏、持续性、资源利用效率
3. **目标完成进度**：计划执行情况、阶段性目标达成
4. **问题解决能力**：编程题得分趋势、错题模式分析
5. **专注度与情绪状态**：
   - 综合专注度等级和沉浸度
   - 分心频率和持续时间
   - 情绪倾向（积极/中性/消极）及主导情绪
   - 学习兴趣、自信心、焦虑程度
6. **时间利用效率**：学习投入与产出比，结合专注度评估实际有效学习时间

### 三、薄弱环节定位
- 精准定位当前最需要改善的3个薄弱点
- 每个薄弱点说明具体表现和可能原因
- 结合专注度数据分析分心原因（如资源类型不匹配、难度不当等）

### 四、动态调整建议
1. **学习资源调整**：结合专注度偏好数据，应增加/减少哪些类型的资源（视频/练题/文档/思维导图）
2. **难度调整**：当前难度是否合适，需要调高还是调低（考虑分心程度）
3. **知识点优先级**：建议优先攻克哪些知识点
4. **学习节奏建议**：加快/保持/放慢当前节奏（结合专注度波动情况）

### 五、学习计划优化建议
- 当前计划是否需要调整
- 具体修改建议（增加阶段/调整顺序/修改里程碑）
- 根据专注度数据建议学习时段安排

---

## 输出格式（JSON，严格遵循）

{{
  "assessment_id": "自动生成的时间戳ID",
  "generated_at": "当前时间",

  "overall": {{
    "score": 综合评分0-100,
    "status": "快速进步/稳步提升/遇到瓶颈/需要干预",
    "summary": "200字以内的总体评估总结"
  }},

  "dimensions": [
    {{
      "name": "维度名称",
      "score": 评分0-100,
      "analysis": "分析说明",
      "trend": "上升/下降/稳定"
    }}
  ],

  "weak_points": [
    {{
      "point": "薄弱点描述",
      "performance": "具体表现",
      "possible_reason": "可能原因",
      "priority": "高/中/低"
    }}
  ],

  "adjustments": {{
    "resource_adjustment": {{
      "increase": ["建议增加的资源类型"],
      "decrease": ["建议减少的资源类型"],
      "reason": "调整原因"
    }},
    "difficulty_adjustment": {{
      "action": "调高/调低/保持",
      "reason": "调整理由"
    }},
    "knowledge_priority": ["按优先级排序的知识点"],
    "pace_advice": "加快/保持/放慢，并说明原因"
  }},

  "plan_optimization": {{
    "needs_adjustment": true/false,
    "suggestions": ["具体的计划修改建议"]
  }}
}}

只输出JSON格式，不要包含其他内容。
""".strip()
        return PromptTemplate.from_template(template)

    async def generate_assessment(self, user_id: str, phase_context: Optional[str] = None) -> Dict[str, Any]:
        """生成用户学习效果评估报告"""
        try:
            data = await self._collect_all_data(user_id)

            prompt = self.template.format(
                feature_profile=data.get("feature_profile", "暂无数据"),
                feature_trends=data.get("feature_trends", "暂无数据"),
                knowledge_mastery=data.get("knowledge_mastery", "暂无数据"),
                learning_stats=data.get("learning_stats", "暂无数据"),
                wrong_answer_stats=data.get("wrong_answer_stats", "暂无数据"),
                study_plan=data.get("study_plan", "暂无数据"),
                recent_context=data.get("recent_context", "暂无数据"),
                attention_data=data.get("attention_data", "暂无数据"),
                phase_context=phase_context or "暂无",
            )

            response = await call_llm_with_retry(self.llm, prompt, error_msg="评估Agent生成评估LLM调用")
            result_text = response.content if hasattr(response, 'content') else str(response)

            assessment = self._parse_assessment(result_text)
            if assessment:
                assessment["assessment_id"] = f"assess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                assessment["generated_at"] = datetime.now().isoformat()

                self._save_assessment(user_id, assessment)

                # ★★★ 评估结论反哺特征画像（异步，不阻塞返回） ★★★
                asyncio.create_task(self._update_features_from_assessment(user_id, assessment))

                return assessment

            return self._fallback_assessment("评估报告生成解析失败")

        except Exception as e:
            print(f"❌ [评估Agent] 生成评估报告失败: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_assessment(str(e))

    # ==================== 评估结论反哺特征画像（异步） ====================

    async def _update_features_from_assessment(self, user_id: str, assessment: Dict[str, Any]):
        """
        将评估报告的维度评分反哺到特征画像中
        使练题、视频、文档等所有子Agent能立即感知评估结论。
        """
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        except ImportError:
            from children_agent.dynamic_feature_updater import DynamicFeatureUpdater

        dims = assessment.get("dimensions", [])
        if not dims:
            return

        # 评估维度 → 特征维度映射
        DIMENSION_MAP = {
            "基础知识掌握度": "academic_background",
            "学习行为与习惯": "learning_behavior",
            "目标完成进度": "goal_motivation",
            "问题解决能力": "cognitive_abilities",
            "专注度与情绪状态": "emotional_state",
            "时间利用效率": "time_management",
            "社交互动": "social_interaction",
            "创新创造": "creativity_innovation",
        }

        updater = DynamicFeatureUpdater()
        features = await updater.get_latest_features_async(user_id)
        if not features:
            print("  ⚠️ [评估Agent] 无特征画像可更新")
            return

        changed = False
        for dim_result in dims:
            dim_name = dim_result.get("name", "")
            target_dim = DIMENSION_MAP.get(dim_name)
            if not target_dim or target_dim not in features:
                continue

            assess_score = dim_result.get("score")
            if assess_score is None or not isinstance(assess_score, (int, float)):
                continue

            # 只当评估分数与当前特征分差异 > 5 时才更新，避免微调抖动
            current_score = features[target_dim].get("score", 50)
            diff = abs(assess_score - current_score)
            if diff <= 5:
                continue

            features[target_dim]["score"] = max(0, min(100, int(assess_score)))
            features[target_dim]["change_reason"] = f"评估报告: {dim_result.get('analysis', '')[:50]}"
            features[target_dim]["confidence"] = min(100, features[target_dim].get("confidence", 50) + 5)
            changed = True

        if changed:
            await asyncio.to_thread(
                updater.update_and_save_features,
                user_id, features,
                update_metadata={
                    "task_type": "assessment",
                    "assessment_id": assessment.get("assessment_id", ""),
                    "source": "LearningAssessmentAgent"
                }
            )
            print(f"  ✅ [评估Agent] 评估结论已反哺特征画像: {assessment.get('assessment_id', '')}")

            # ★★★ 将薄弱点加入遗忘曲线复习调度 ★★★
            await self._schedule_weak_points_review(user_id, assessment)
            
            # ★★★ 发送评估报告推送通知 ★★★
            await self._send_assessment_notification(user_id, assessment)

    async def _schedule_weak_points_review(self, user_id: str, assessment: Dict[str, Any]):
        """
        将评估识别的薄弱点加入遗忘曲线复习调度，确保用户能及时复习。
        """
        try:
            from Agent.children_agent.recommendation.forgetting_curve import ForgettingCurveScheduler
        except ImportError:
            try:
                from children_agent.recommendation.forgetting_curve import ForgettingCurveScheduler
            except ImportError:
                return

        weak_points = assessment.get("weak_points", [])
        if not weak_points:
            return

        scheduler = ForgettingCurveScheduler()
        
        # 为每个高优先级薄弱点安排紧急复习
        for wp in weak_points:
            priority = wp.get("priority", "中")
            # 高优先级薄弱点立即安排复习（间隔0天，即今日）
            if priority == "高":
                kp = wp.get("point", "")
                if kp:
                    # 将薄弱点作为资源安排复习
                    scheduler.schedule_review(
                        user_id=user_id,
                        resource_type="weak_point",
                        resource_id=f"weak_{kp[:32]}",
                        is_correct=False,  # 标记为未掌握
                        time_spent=0,
                        metadata={
                            "weak_point": kp,
                            "performance": wp.get("performance", ""),
                            "possible_reason": wp.get("possible_reason", ""),
                            "assessment_id": assessment.get("assessment_id", "")
                        }
                    )
                    print(f"  📅 [评估Agent] 高优先级薄弱点已加入复习调度: {kp}")

        # 如果有知识点掌握情况，也更新知识点级遗忘曲线
        try:
            from memory.knowledge_mastery import KnowledgeMasteryGraph
            kg = KnowledgeMasteryGraph()
            kp_analysis = assessment.get("knowledge_point_analysis", [])
            if kp_analysis:
                for kp in kp_analysis:
                    kp_name = kp.get("name", "")
                    score = kp.get("score", 50)
                    if kp_name and score < 70:  # 掌握度低于70分需要加强复习
                        kg.record_activity(
                            user_id=user_id,
                            knowledge_point=kp_name,
                            correct=False,
                            activity_type="assessment_weak",
                            difficulty="高",
                            time_spent=0
                        )
                        print(f"  🧠 [评估Agent] 知识点掌握度不足已记录: {kp_name} ({score}分)")
        except Exception as e:
            print(f"  ⚠️ [评估Agent] 更新知识点掌握度失败: {e}")

    async def _send_assessment_notification(self, user_id: str, assessment: Dict[str, Any]):
        """发送评估报告推送通知"""
        try:
            from .assessment_notifier import get_assessment_notifier
            notifier = get_assessment_notifier()
            await notifier.notify_new_assessment(user_id, assessment)
            print(f"  🔔 [评估Agent] 已发送评估报告通知")
        except Exception as e:
            print(f"  ⚠️ [评估Agent] 发送通知失败: {e}")

    async def _collect_all_data(self, user_id: str) -> Dict[str, Any]:
        """采集所有学习数据（并行化采集，减少延迟）"""
        result = {}

        # ★★★ 第零步：先获取 recall（其他数据源依赖它）★★★
        try:
            recall = self._hub.recall(user_id, query="学习评估")
        except Exception as e:
            print(f"⚠️ [评估Agent] 采集数据失败: {e}")
            recall = {}

        # ★★★ 第一步：recall 依赖项（纯内存操作，很快，保持同步）★★★

        # 1. 特征画像
        try:
            feat = recall.get("features", {})
            if feat and "error" not in feat:
                result["feature_profile"] = (
                    f"综合评分: {feat.get('overall_score', '无')}/100\n"
                    f"各维度: {feat.get('dimension_scores', '无')}\n"
                    f"情绪状态: {feat.get('emotional_state', '无')}"
                )
            else:
                result["feature_profile"] = "暂无特征数据"
        except Exception:
            result["feature_profile"] = "暂无特征数据"

        # 3. 知识点掌握
        try:
            km = recall.get("knowledge_mastery", {})
            if km and "error" not in km:
                parts = []
                summary = km.get("summary", "")
                if summary:
                    parts.append(summary)
                weak = km.get("weak_points", [])
                if weak:
                    parts.append("薄弱知识点: " + ", ".join(
                        [f"{w['knowledge_point']}(掌握度{w.get('mastery_level', '?')}/4)" for w in weak[:5]]
                    ))
                result["knowledge_mastery"] = "\n".join(parts) if parts else "暂无数据"
            else:
                result["knowledge_mastery"] = "暂无知识点数据"
        except Exception:
            result["knowledge_mastery"] = "暂无知识点数据"

        # 4. 学习统计
        try:
            ls = recall.get("learning_stats", {})
            if ls and "error" not in ls:
                result["learning_stats"] = (
                    f"总做题: {ls.get('total_solved', 0)}道\n"
                    f"正确: {ls.get('total_correct', 0)}道\n"
                    f"正确率: {ls.get('accuracy', 0)}%\n"
                    f"薄弱主题: {ls.get('weak_topics', '无')}"
                )
            else:
                result["learning_stats"] = "暂无学习统计"
        except Exception:
            result["learning_stats"] = "暂无学习统计"

        # 6. 学习计划
        try:
            sp = recall.get("study_plan", {})
            if sp and "error" not in sp:
                result["study_plan"] = (
                    f"计划: {sp.get('title', '无')}\n"
                    f"进度: {sp.get('progress', '无')}\n"
                    f"当前阶段: {sp.get('current_phase', {}).get('name', '无')}"
                )
            else:
                result["study_plan"] = "暂无学习计划"
        except Exception:
            result["study_plan"] = "暂无学习计划"

        # 8. 专注度与情绪数据
        try:
            attention = recall.get("attention_data", {})
            if attention and attention.get("status") == "success":
                parts = []

                composite = attention.get("composite_score", {})
                if composite:
                    parts.append(f"综合专注度评分: {composite.get('score', 0)}/100 ({composite.get('level', '')})")

                prefs = attention.get("attention_preferences", {})
                if prefs:
                    pref_items = [f"{k}: {v:.2f}" for k, v in prefs.get("preferences", {}).items()]
                    parts.append(f"资源偏好: {', '.join(pref_items)}")
                    parts.append(f"偏好置信度: {prefs.get('overall_confidence', 0):.2f}")

                recent_att = attention.get("recent_attention", {})
                if recent_att.get("status") == "success":
                    parts.append(f"最近24h沉浸度: {recent_att.get('avg_immersion_score', 0):.3f}")
                    parts.append(f"最近24h会话数: {recent_att.get('total_sessions', 0)}次")
                    parts.append(f"最近24h分心率: {recent_att.get('distraction_ratio', 0):.3f}")

                emotions = attention.get("recent_emotions", {})
                if emotions.get("status") == "success":
                    dominant = emotions.get("dominant_emotion", {})
                    parts.append(f"主导情绪: {dominant.get('type', '')} ({dominant.get('percentage', 0)}%)")
                    parts.append(f"整体情绪倾向: {emotions.get('overall_valence', '')}")

                distraction = attention.get("distraction_stats", {})
                if distraction.get("status") == "success":
                    parts.append(f"分心会话率: {distraction.get('distraction_rate', 0):.3f}")

                result["attention_data"] = "\n".join(parts) if parts else "暂无详细数据"
            else:
                result["attention_data"] = "暂无专注度数据"
        except Exception as e:
            result["attention_data"] = f"获取专注度数据失败: {str(e)}"

        # ★★★ 第二步：IO 密集型的 4 个数据源用 asyncio.gather 并行采集 ★★★
        async def _collect_trends():
            try:
                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                updater = DynamicFeatureUpdater()
                history = await asyncio.to_thread(updater.get_update_history, user_id, 20)
                if history:
                    lines = []
                    for rec in history[-10:]:
                        ts = rec.get("timestamp", "")[5:16] if rec.get("timestamp") else ""
                        meta = rec.get("metadata", {})
                        task = meta.get("task_type", "未知")
                        old = rec.get("old_scores", {})
                        new = rec.get("new_scores", {})
                        changes = []
                        for dim in old:
                            if dim in new and old[dim] != new[dim]:
                                changes.append(f"{dim}:{old[dim]}→{new[dim]}")
                        if changes:
                            lines.append(f"  [{ts}] {task}: {', '.join(changes)}")
                    return "特征变化记录:\n" + "\n".join(lines[-8:]) if lines else "暂无显著变化"
                return "暂无特征变化记录"
            except Exception:
                return "暂无特征变化记录"

        async def _collect_wrong_answer_stats():
            try:
                from services.wrong_answer_service import WrongAnswerService
                wa = WrongAnswerService()
                stats = await asyncio.to_thread(wa.get_wrong_answer_stats, user_id)
                return (
                    f"累计错题: {stats.get('total', 0)}道\n"
                    f"待巩固: {stats.get('pending', 0)}道\n"
                    f"已掌握: {stats.get('resolved', 0)}道\n"
                    f"按类型: {stats.get('by_type', {})}\n"
                    f"按来源: {stats.get('by_source', {})}"
                )
            except Exception:
                return "暂无错题数据"

        async def _collect_recent_context():
            try:
                ctx = await asyncio.to_thread(self._hub.build_prompt_context, user_id, "学习评估")
                return ctx if ctx else "暂无近期交互数据"
            except Exception:
                return "暂无近期交互数据"

        async def _collect_time_efficiency():
            try:
                from memory.study_planner import StudyPlanner
                planner = StudyPlanner()
                plan = await asyncio.to_thread(planner.get_plan, user_id)
                if plan:
                    phases = plan.get("phases", [])
                    time_lines = []
                    for i, p in enumerate(phases):
                        estimated = p.get("estimated_hours", "?")
                        actual = p.get("_actual_hours")
                        status = p.get("status", "")
                        if actual is not None:
                            ratio = actual / estimated if isinstance(estimated, (int, float)) and estimated > 0 else None
                            eval_text = "提前完成" if ratio and ratio < 0.8 else ("超时" if ratio and ratio > 1.2 else "按计划完成")
                            time_lines.append(f"阶段{i+1} [{status}]: 计划{estimated}h, 实际{actual}h ({eval_text})")
                        else:
                            time_lines.append(f"阶段{i+1} [{status}]: 计划{estimated}h, 实际暂无数据")
                    return "\n".join(time_lines) if time_lines else "暂无时间数据"
                return "暂无学习计划"
            except Exception:
                return "暂无时间数据"

        # 并行执行 4 个 IO 数据源
        trends_result, wrong_answer_result, context_result, time_result = await asyncio.gather(
            _collect_trends(),
            _collect_wrong_answer_stats(),
            _collect_recent_context(),
            _collect_time_efficiency(),
        )

        result["feature_trends"] = trends_result
        result["wrong_answer_stats"] = wrong_answer_result
        result["recent_context"] = context_result
        result["time_efficiency"] = time_result

        return result

    def _parse_assessment(self, text: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的JSON评估报告（多层容错）"""
        import re
        try:
            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            match = json_pattern.search(text)
            if match:
                raw = match.group(1).strip()
                result = self._robust_json_loads(raw)
                if result:
                    return result
            obj_pattern = re.compile(r'\{.*\}', re.DOTALL)
            match = obj_pattern.search(text)
            if match:
                raw = match.group(0).strip()
                result = self._robust_json_loads(raw)
                if result:
                    return result
            text = text.strip()
            if text.startswith('{') and text.endswith('}'):
                result = self._robust_json_loads(text)
                if result:
                    return result
            return None
        except Exception as e:
            print(f"⚠️ [评估Agent] JSON解析失败: {e}")
            return None

    def _robust_json_loads(self, text: str) -> Optional[Dict[str, Any]]:
        """多层容错JSON解析，处理LLM常见的JSON格式问题"""
        import re, json

        if not text:
            return None

        text = re.sub(r'[\x00-\x1f\x7f]', '', text)

        # 第1层：直接尝试标准解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 第2层：修复尾部多余逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 第3层：将单引号替换为双引号（但保留字符串内的转义）
        single_fixed = re.sub(r"(?<!\\)'", '"', text)
        single_fixed = re.sub(r',\s*([}\]])', r'\1', single_fixed)
        try:
            return json.loads(single_fixed)
        except json.JSONDecodeError:
            pass

        # 第4层：修复未加引号的属性名（Python对象样式 key: value → "key": value）
        # 匹配 {key: 或 ,key: 的 pattern，给 key 加双引号
        unquoted_fixed = re.sub(
            r'(?<=[{,])\s*([a-zA-Z_]\w*)\s*:',
            r'"\1":',
            single_fixed
        )
        try:
            return json.loads(unquoted_fixed)
        except json.JSONDecodeError:
            pass

        # 第5层：进一步修复 — 处理 undefined → null
        undef_fixed = re.sub(r':\s*undefined', ': null', unquoted_fixed, flags=re.IGNORECASE)
        undef_fixed = re.sub(r':\s*None', ': null', undef_fixed, flags=re.IGNORECASE)
        undef_fixed = re.sub(r':\s*True', ': true', undef_fixed, flags=re.IGNORECASE)
        undef_fixed = re.sub(r':\s*False', ': false', undef_fixed, flags=re.IGNORECASE)
        try:
            return json.loads(undef_fixed)
        except json.JSONDecodeError:
            pass

        # 第6层：Extra Data 容错 — 多个JSON拼在一起，取第一个
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(undef_fixed)
            return obj
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    # ==================== 阶段性评估（阶段完成时自动触发） ====================

    def _create_phase_template(self) -> PromptTemplate:
        template = """
你是一位资深教育评估专家，负责在学生完成一个学习阶段后，进行阶段性总结评估。

## 完成阶段信息

当前已完成阶段：第 {completed_phase_index} 阶段 - 「{completed_phase_name}」
阶段计划知识点：{phase_knowledge_points}

## 所有学习阶段概览
{all_phases_overview}

## 阶段性权重说明
- 当前完成阶段权重 60%（主要评估对象）
- 上一阶段（如有）权重 25%（作为基础对比）
- 更早阶段（如有）权重 15%（历史趋势参考）

## 用户当前学习数据

### 1. 8维度特征画像
{feature_profile}

### 2. 特征变化趋势
{feature_trends}

### 3. 知识点掌握情况
{knowledge_mastery}

### 4. 学习统计
{learning_stats}

### 5. 错题本概况
{wrong_answer_stats}

### 6. 当前学习计划
{study_plan}

### 7. 时间效率数据
{time_efficiency}

---

## 分析任务

请基于以上数据，侧重以下维度进行**阶段性评估**：

### 一、本阶段综合评估
- 本阶段学习效果评分（0-100）
- 本阶段学习状态（快速进步/稳步提升/勉强通过/需要回炉）
- 本阶段任务完成摘要

### 二、本阶段知识点分析
- 每个计划知识点的掌握程度和具体表现
- 哪些知识点掌握扎实，哪些只是"勉强通过 70 分线"

### 三、阶段性薄弱点定位
- 本阶段中最需要巩固的 2-3 个薄弱点
- 这些薄弱点对下一阶段的影响

### 四、阶段间进步分析
- 与上一阶段相比的进步/退步
- 学习能力和习惯的改善情况

### 五、下一阶段准备度评估
- 当前基础是否足以进入下一阶段（评分 0-100）
- 建议进入下一阶段前应该补足什么
- 针对下一阶段的学习策略建议

### 六、动态调整建议（如果分数<80 则需要调整）
1. 本阶段是否需要补习
2. 下一阶段资源调整建议
3. 难度调整建议

### 七、时间效率分析
- 计划用时：{estimated_hours} 小时
- 实际活跃用时：{actual_hours} 小时（基于心跳累加）
- 效率评价（提前完成 / 按计划完成 / 超时）
- 如果实际用时远少于计划：评估是否真的掌握了所有知识点，还是跳过了练习环节
- 如果实际用时远超计划：分析卡点原因（难度过高？练习不足？中途分心？）

---

## 输出格式（JSON，严格遵循）

{{
  "assessment_id": "自动生成的时间戳ID",
  "generated_at": "当前时间",
  "type": "phase_assessment",

  "phase_summary": {{
    "phase_index": {completed_phase_index},
    "phase_name": "{completed_phase_name}",
    "score": 本阶段综合评分0-100,
    "status": "快速进步/稳步提升/勉强通过/需要回炉",
    "summary": "200字以内的阶段总结",
    "time_efficiency": {{
      "planned_hours": {estimated_hours},
      "actual_hours": {actual_hours},
      "evaluation": "提前完成/按计划完成/超时"
    }}
  }},

  "knowledge_point_analysis": [
    {{
      "name": "知识点名称",
      "score": 掌握度评分0-100,
      "mastery": "扎实/一般/薄弱",
      "comment": "分析说明"
    }}
  ],

  "weak_points": [
    {{
      "point": "薄弱点描述",
      "impact_on_next_phase": "对下一阶段的影响"
    }}
  ],

  "improvement_analysis": {{
    "compared_to_previous": "进步/退步/保持",
    "details": "与上一阶段对比分析说明"
  }},

  "readiness": {{
    "score": 下一阶段准备度0-100,
    "ready": true/false,
    "gaps": ["进入下一阶段前需要补足的内容"],
    "suggestions": ["下一阶段学习策略建议"]
  }},

  "adjustments": {{
    "needs_remedy": true/false,
    "remedy_suggestions": ["如果分数低，本阶段补习建议"],
    "resource_adjustment_for_next": {{
      "increase": ["建议下一阶段增加的资源类型"],
      "decrease": ["建议下一阶段减少的资源类型"],
      "reason": "调整原因"
    }},
    "difficulty_adjustment": {{
      "action": "调高/调低/保持",
      "reason": "调整理由"
    }}
  }}
}}

只输出JSON格式，不要包含其他内容。
""".strip()
        return PromptTemplate.from_template(template)

    async def generate_phase_assessment(
        self, user_id: str, completed_phase_index: int, all_phases: list
    ) -> Dict[str, Any]:
        """生成阶段性评估报告（阶段完成时自动触发）"""
        try:
            from memory.study_planner import StudyPlanner
            planner = StudyPlanner()
            plan = await asyncio.to_thread(planner.get_plan, user_id)
            phases = plan.get("phases", []) if plan else []

            completed_phase = phases[completed_phase_index] if completed_phase_index < len(phases) else {}
            completed_phase_name = completed_phase.get("name", f"阶段{completed_phase_index+1}")
            phase_kps = ", ".join(completed_phase.get("knowledge_points", []))

            all_phases_lines = []
            for i, p in enumerate(phases):
                status = p.get("status", "未开始")
                kps = ", ".join(p.get("knowledge_points", []))
                all_phases_lines.append(f"阶段{i+1}: {p.get('name','')} [{status}] 知识点: {kps}")
            all_phases_overview = "\n".join(all_phases_lines)

            data = await self._collect_all_data(user_id)

            prompt_template = self._create_phase_template()
            prompt = prompt_template.format(
                completed_phase_index=completed_phase_index,
                completed_phase_name=completed_phase_name,
                phase_knowledge_points=phase_kps,
                all_phases_overview=all_phases_overview,
                feature_profile=data.get("feature_profile", "暂无数据"),
                feature_trends=data.get("feature_trends", "暂无数据"),
                knowledge_mastery=data.get("knowledge_mastery", "暂无数据"),
                learning_stats=data.get("learning_stats", "暂无数据"),
                wrong_answer_stats=data.get("wrong_answer_stats", "暂无数据"),
                study_plan=data.get("study_plan", "暂无数据"),
                # 时间效率
                time_efficiency=data.get("time_efficiency", "暂无时间数据"),
                estimated_hours=completed_phase.get("estimated_hours", "未知"),
                actual_hours=completed_phase.get("_actual_hours", "暂无数据"),
            )

            response = await call_llm_with_retry(self.llm, prompt, error_msg="评估Agent生成阶段性评估LLM调用")
            result_text = response.content if hasattr(response, 'content') else str(response)
            assessment = self._parse_assessment(result_text)

            if assessment:
                assessment["assessment_id"] = f"phase_assess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                assessment["generated_at"] = datetime.now().isoformat()
                assessment["type"] = "phase_assessment"
                await self._save_phase_assessment(user_id, completed_phase_index, assessment)
                return assessment

            return self._fallback_assessment("阶段性评估解析失败")

        except Exception as e:
            print(f"❌ [评估Agent] 生成阶段性评估失败: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_assessment(str(e))

    async def _save_phase_assessment(self, user_id: str, phase_index: int, assessment: Dict[str, Any]):
        """保存阶段性评估到学习计划中"""
        try:
            from memory.study_planner import StudyPlanner
            planner = StudyPlanner()
            plan = await asyncio.to_thread(planner.get_plan, user_id)
            if not plan:
                return
            phases = plan.get("phases", [])
            if phase_index < len(phases):
                phases[phase_index]["phase_assessment"] = assessment
                plan["phases"] = phases
                await asyncio.to_thread(planner.save_plan, user_id, plan)
        except Exception as e:
            print(f"  ⚠️ [评估Agent] 保存阶段性评估失败: {e}")

    def _fallback_assessment(self, reason: str) -> Dict[str, Any]:
        """生成降级评估报告"""
        return {
            "assessment_id": f"assess_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "overall": {
                "score": 0,
                "status": "评估失败",
                "summary": f"因以下原因无法生成评估报告: {reason}"
            },
            "dimensions": [],
            "weak_points": [],
            "adjustments": {
                "resource_adjustment": {"increase": [], "decrease": [], "reason": "无法评估"},
                "difficulty_adjustment": {"action": "保持", "reason": "无法评估"},
                "knowledge_priority": [],
                "pace_advice": "无法评估"
            },
            "plan_optimization": {
                "needs_adjustment": False,
                "suggestions": []
            }
        }

    def _save_assessment(self, user_id: str, assessment: Dict[str, Any]):
        """保存评估报告到用户目录"""
        import json as j
        from pathlib import Path
        assess_dir = Path(f"./user_assessments/{user_id}")
        assess_dir.mkdir(parents=True, exist_ok=True)
        aid = assessment.get("assessment_id", f"assess_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        filepath = assess_dir / f"{aid}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            j.dump(assessment, f, ensure_ascii=False, indent=2)
        print(f"✅ [评估Agent] 评估报告已保存: {filepath}")

    def get_latest_assessment(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户最新的评估报告"""
        import json as j
        from pathlib import Path
        assess_dir = Path(f"./user_assessments/{user_id}")
        if not assess_dir.exists():
            return None
        files = sorted(assess_dir.glob("assess_*.json"), reverse=True)
        if not files:
            return None
        with open(files[0], "r", encoding="utf-8") as f:
            return j.load(f)

    def get_assessment_by_id(self, user_id: str, assessment_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取评估报告"""
        import json as j
        from pathlib import Path
        assess_file = Path(f"./user_assessments/{user_id}/assess_{assessment_id}.json")
        if assess_file.exists():
            with open(assess_file, "r", encoding="utf-8") as f:
                return j.load(f)
        return None

    def get_feature_weak_points(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户最新的薄弱点列表（供其他Agent调用）"""
        assessment = self.get_latest_assessment(user_id)
        if assessment:
            return assessment.get("weak_points", [])
        return []

    async def regenerate_assessment_part(
        self, 
        user_id: str, 
        assessment_id: str,
        part_type: str,
        part_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        局部重新评估：只重新生成评估报告中的指定部分，其他部分保持不变
        
        Args:
            user_id: 用户ID
            assessment_id: 要修改的评估报告ID
            part_type: 要重新生成的部分类型
                - "dimension": 重新生成某个维度的评估
                - "weak_point": 重新生成某个薄弱点
                - "suggestion": 重新生成某条建议
                - "overall": 重新生成总体评估等级
            part_index: 要重新生成的部分索引（从0开始），如果为None则重新生成所有该类型
        
        Returns:
            更新后的完整评估报告
        """
        try:
            # 读取现有评估报告
            import json as j
            from pathlib import Path
            assess_dir = Path(f"./user_assessments/{user_id}")
            assess_file = assess_dir / f"assess_{assessment_id}.json"
            
            if not assess_file.exists():
                # 如果找不到指定的评估报告，获取最新的
                latest = self.get_latest_assessment(user_id)
                if not latest:
                    return {"status": "error", "message": "找不到评估报告"}
                assessment = latest
                assessment_id = latest.get("assessment_id", assessment_id)
            else:
                with open(assess_file, "r", encoding="utf-8") as fp:
                    assessment = j.load(fp)
            
            # 收集用户数据
            data = await self._collect_all_data(user_id)
            
            # 根据类型重新生成指定部分
            if part_type == "dimension":
                await self._regenerate_dimension(assessment, data, part_index)
            elif part_type == "weak_point":
                await self._regenerate_weak_point(assessment, data, part_index)
            elif part_type == "suggestion":
                await self._regenerate_suggestion(assessment, data, part_index)
            elif part_type == "overall":
                await self._regenerate_overall(assessment, data)
            else:
                return {"status": "error", "message": f"不支持的部分类型: {part_type}"}
            
            # 更新生成时间
            assessment["regenerated_at"] = datetime.now().isoformat()
            assessment["regenerated_parts"] = assessment.get("regenerated_parts", []) + [
                {"part_type": part_type, "part_index": part_index, "time": datetime.now().isoformat()}
            ]
            
            # 保存更新后的评估报告
            self._save_assessment(user_id, assessment)
            
            # 异步更新特征画像
            asyncio.create_task(self._update_features_from_assessment(user_id, assessment))
            
            return {"status": "success", "assessment": assessment, "message": f"已重新生成{part_type}部分"}
            
        except Exception as e:
            print(f"❌ [评估Agent] 局部重新评估失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    async def _regenerate_dimension(self, assessment: Dict[str, Any], data: Dict[str, Any], index: Optional[int]):
        """重新生成维度评估"""
        dims = assessment.get("dimensions", [])
        
        if index is not None and (index < 0 or index >= len(dims)):
            return
        
        prompt = f"""
你是一位教育评估专家，请基于以下数据重新评估：

## 用户数据
特征画像：{data.get('feature_profile', '')}
特征趋势：{data.get('feature_trends', '')}
学习统计：{data.get('learning_stats', '')}

## 当前评估维度
{json.dumps(dims, ensure_ascii=False)}

## 任务
{"重新生成第" + str(index + 1) + "个维度" if index is not None else "重新生成所有维度"}

## 输出格式
请输出JSON格式，包含一个dimensions数组：
{{
  "dimensions": [
    {{
      "name": "维度名称",
      "score": 0-100,
      "level": "优秀/良好/中等/需加强",
      "analysis": "分析说明",
      "suggestions": ["建议1", "建议2"]
    }}
  ]
}}
"""
        
        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)
        result = self._parse_assessment(result_text)
        
        if result and result.get("dimensions"):
            if index is not None:
                dims[index] = result["dimensions"][0]
            else:
                assessment["dimensions"] = result["dimensions"]

    async def _regenerate_weak_point(self, assessment: Dict[str, Any], data: Dict[str, Any], index: Optional[int]):
        """重新生成薄弱点"""
        weak_points = assessment.get("weak_points", [])
        
        if index is not None and (index < 0 or index >= len(weak_points)):
            return
        
        prompt = f"""
你是一位教育评估专家，请基于以下数据重新识别薄弱点：

## 用户数据
知识点掌握：{data.get('knowledge_mastery', '')}
学习统计：{data.get('learning_stats', '')}
错题统计：{data.get('wrong_answer_stats', '')}
特征画像：{data.get('feature_profile', '')}

## 当前薄弱点
{json.dumps(weak_points, ensure_ascii=False)}

## 任务
{"重新生成第" + str(index + 1) + "个薄弱点" if index is not None else "重新生成所有薄弱点"}

## 输出格式
请输出JSON格式：
{{
  "weak_points": [
    {{
      "point": "薄弱点描述",
      "performance": "表现描述",
      "possible_reason": "可能原因",
      "priority": "高/中/低",
      "suggestions": ["改进建议"]
    }}
  ]
}}
"""
        
        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)
        result = self._parse_assessment(result_text)
        
        if result and result.get("weak_points"):
            if index is not None:
                weak_points[index] = result["weak_points"][0]
            else:
                assessment["weak_points"] = result["weak_points"]

    async def _regenerate_suggestion(self, assessment: Dict[str, Any], data: Dict[str, Any], index: Optional[int]):
        """重新生成建议"""
        suggestions = assessment.get("suggestions", [])
        
        if index is not None and (index < 0 or index >= len(suggestions)):
            return
        
        prompt = f"""
你是一位教育评估专家，请基于以下数据重新生成学习建议：

## 用户数据
特征画像：{data.get('feature_profile', '')}
学习统计：{data.get('learning_stats', '')}
当前评估：{json.dumps(assessment.get('dimensions', []), ensure_ascii=False)}
薄弱点：{json.dumps(assessment.get('weak_points', []), ensure_ascii=False)}

## 当前建议
{json.dumps(suggestions, ensure_ascii=False)}

## 任务
{"重新生成第" + str(index + 1) + "条建议" if index is not None else "重新生成所有建议"}

## 输出格式
请输出JSON格式：
{{
  "suggestions": [
    {{
      "suggestion": "建议内容",
      "type": "练习/视频/文档/复习/计划调整",
      "expected_improvement": "预期改进"
    }}
  ]
}}
"""
        
        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)
        result = self._parse_assessment(result_text)
        
        if result and result.get("suggestions"):
            if index is not None:
                suggestions[index] = result["suggestions"][0]
            else:
                assessment["suggestions"] = result["suggestions"]

    async def _regenerate_overall(self, assessment: Dict[str, Any], data: Dict[str, Any]):
        """重新生成总体评估"""
        prompt = f"""
你是一位教育评估专家，请基于以下数据重新评估总体等级：

## 用户数据
特征画像：{data.get('feature_profile', '')}
学习统计：{data.get('learning_stats', '')}
维度评估：{json.dumps(assessment.get('dimensions', []), ensure_ascii=False)}
薄弱点：{json.dumps(assessment.get('weak_points', []), ensure_ascii=False)}

## 任务
重新生成总体评估等级

## 输出格式
请输出JSON格式：
{{
  "overall_level": "S/A/B/C/D（对应优秀/良好/中等/及格/需加强）",
  "overall_score": 0-100,
  "overall_summary": "总体评估总结"
}}
"""
        
        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)
        result = self._parse_assessment(result_text)
        
        if result:
            if "overall_level" in result:
                assessment["overall_level"] = result["overall_level"]
            if "overall_score" in result:
                assessment["overall_score"] = result["overall_score"]
            if "overall_summary" in result:
                assessment["overall_summary"] = result["overall_summary"]

    def get_assessment_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户的评估报告历史"""
        import json as j
        from pathlib import Path
        assess_dir = Path(f"./user_assessments/{user_id}")
        if not assess_dir.exists():
            return []
        files = sorted(assess_dir.glob("assess_*.json"), reverse=True)[:limit]
        results = []
        for f in files:
            with open(f, "r", encoding="utf-8") as fp:
                results.append(j.load(fp))
        return results

    async def apply_adjustments(self, user_id: str, assessment: Dict[str, Any]) -> Dict[str, Any]:
        """
        接受阶段性评估报告：将阶段评估作为上下文，触发一次完整的学习评估
        评估结果会自动保存并影响后续推荐
        """
        result = {"applied": [], "failed": []}

        try:
            phase_summary = assessment.get("phase_summary", {})
            phase_index = phase_summary.get("phase_index", 0)
            phase_name = phase_summary.get("phase_name", f"阶段{phase_index+1}")
            score = phase_summary.get("score", 0)
            status = phase_summary.get("status", "未知")
            summary_text = phase_summary.get("summary", "")

            kp_analysis = assessment.get("knowledge_point_analysis", [])
            kp_text = "；".join(
                [f"{kp.get('name','')}: {kp.get('score',0)}分({kp.get('mastery','')})" for kp in kp_analysis]
            ) if kp_analysis else "无"

            weak_points = assessment.get("weak_points", [])
            weak_text = "；".join([wp.get("point", "") for wp in weak_points]) if weak_points else "无"

            readiness = assessment.get("readiness", {})
            readiness_score = readiness.get("score", 0)
            readiness_ready = readiness.get("ready", False)
            gaps_text = "；".join(readiness.get("gaps", [])) if readiness.get("gaps") else "无"
            suggestions_text = "；".join(readiness.get("suggestions", [])) if readiness.get("suggestions") else "无"

            improvements = assessment.get("improvement_analysis", {})
            compared = improvements.get("compared_to_previous", "未知")
            improvement_details = improvements.get("details", "")

            adjustments = assessment.get("adjustments", {})
            remedy_suggestions = "；".join(adjustments.get("remedy_suggestions", [])) if adjustments.get("remedy_suggestions") else "无"
            diff_action = adjustments.get("difficulty_adjustment", {}).get("action", "保持")

            phase_context = f"""
## 上一阶段（{phase_name}）评估结果

### 综合评分
- 分数: {score}/100
- 状态: {status}
- 总结: {summary_text}

### 知识点掌握情况
{kp_text}

### 薄弱点
{weak_text}

### 阶段间进步分析
- 相对上一阶段: {compared}
- 详情: {improvement_details}

### 下一阶段准备度
- 准备度评分: {readiness_score}/100
- 是否准备好: {"是" if readiness_ready else "否"}
- 需补足内容: {gaps_text}
- 学习策略建议: {suggestions_text}

### 动态调整建议
- 难度调整: {diff_action}
- 补习建议: {remedy_suggestions}
""".strip()

            print(f"\n  🔄 [评估Agent] 用户保存阶段{phase_index+1}评估，触发完整学习评估...")

            full_assessment = await self.generate_assessment(user_id, phase_context=phase_context)

            if full_assessment and full_assessment.get("overall", {}).get("score", 0) > 0:
                result["applied"].append("完整学习评估报告已生成并保存")
                print(f"  ✅ [评估Agent] 完整学习评估完成: {full_assessment.get('assessment_id', '')}")

                await self._save_phase_assessment(user_id, phase_index, assessment)
                result["applied"].append("阶段评估建议已保存")
            else:
                result["failed"].append("学习评估生成失败，使用降级方案")
                assessment["type"] = assessment.get("type", "phase_assessment")
                if "assessment_id" not in assessment:
                    assessment["assessment_id"] = f"phase_assess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if "generated_at" not in assessment:
                    assessment["generated_at"] = datetime.now().isoformat()
                self._save_assessment(user_id, assessment)
                result["applied"].append("阶段评估报告已保存到评估页面（降级）")

        except Exception as e:
            print(f"  ❌ [评估Agent] 应用评估失败: {e}")
            import traceback
            traceback.print_exc()
            result["failed"].append(f"应用评估报告失败: {e}")

        return result

    # ★★★ 采纳建议（带权重） ★★★
    def adopt_suggestion(self, user_id: str, suggestion_type: str,
                         content: str, weight: float = 0.7) -> Dict[str, Any]:
        """
        采纳一条评估建议

        Args:
            user_id: 用户ID
            suggestion_type: 建议类型 (resource_adjustment/difficulty_adjustment/knowledge_priority/pace_advice)
            content: 建议内容
            weight: 采纳权重 0.0~1.0（默认0.7）

        Returns:
            {"success": True, "adopted_suggestions": [...]}
        """
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        except ImportError:
            from children_agent.dynamic_feature_updater import DynamicFeatureUpdater

        updater = DynamicFeatureUpdater()
        adopted = updater.get_adopted_suggestions(user_id)

        # 去重：同类型同内容的合并
        for i, s in enumerate(adopted):
            if s["type"] == suggestion_type and s["content"] == content:
                adopted[i]["weight"] = min(1.0, adopted[i]["weight"] + 0.1)
                adopted[i]["adopted_at"] = datetime.now().isoformat()
                adopted[i]["renewed_at"] = datetime.now().isoformat()
                break
        else:
            adopted.append({
                "type": suggestion_type,
                "content": content,
                "weight": weight,
                "adopted_at": datetime.now().isoformat(),
                "renewed_at": datetime.now().isoformat(),
                "source_assessment_id": (self.get_latest_assessment(user_id) or {}).get("assessment_id", "")  # or判空防止崩溃
            })

        # 保留最近 20 条，按时间倒序
        adopted.sort(key=lambda x: x.get("adopted_at", ""), reverse=True)
        adopted = adopted[:20]

        updater.save_adopted_suggestions(user_id, adopted)
        return {"success": True, "adopted_suggestions": adopted}

    # ★★★ 拒绝/撤销一条采纳建议 ★★★
    def reject_suggestion(self, user_id: str, suggestion_type: str, content: str) -> Dict[str, Any]:
        """拒绝/撤销一条已采纳的建议"""
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        except ImportError:
            from children_agent.dynamic_feature_updater import DynamicFeatureUpdater

        updater = DynamicFeatureUpdater()
        adopted = updater.get_adopted_suggestions(user_id)
        before = len(adopted)
        adopted = [s for s in adopted if not (s["type"] == suggestion_type and s["content"] == content)]
        if len(adopted) < before:
            updater.save_adopted_suggestions(user_id, adopted)
            return {"success": True, "removed": True, "adopted_suggestions": adopted}
        return {"success": True, "removed": False, "adopted_suggestions": adopted}

    # ★★★ 获取所有已采纳的建议 ★★★
    def get_adopted_suggestions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有已采纳的评估建议"""
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        except ImportError:
            from children_agent.dynamic_feature_updater import DynamicFeatureUpdater

        updater = DynamicFeatureUpdater()
        return updater.get_adopted_suggestions(user_id)

    # ★★★ 根据已采纳建议调整推荐权重 ★★★
    def build_adoption_weights(self, user_id: str) -> Dict[str, Any]:
        """
        根据已采纳的建议构建推荐权重配置

        Returns:
            {
                "increase_resource_types": ["practice", "video"],  # 应增加的类型
                "decrease_resource_types": ["doc"],                 # 应减少的类型
                "difficulty": "调高" / "调低" / "保持",
                "knowledge_priority": ["知识点1", "知识点2"],       # 优先知识点
                "pace_advice": "..."
            }
        """
        adopted = self.get_adopted_suggestions(user_id)
        weights = {
            "increase_resource_types": [],
            "decrease_resource_types": [],
            "difficulty": None,
            "knowledge_priority": [],
            "pace_advice": ""
        }

        type_resource_map = {
            "练习": "practice", "编程": "practice", "刷题": "practice",
            "文档": "doc", "阅读": "doc",
            "视频": "video", "看视频": "video",
            "思维导图": "mindmap", "脑图": "mindmap",
            "动画": "animation",
            "拓展": "extension", "扩展": "extension",
            "理论题": "question_gen", "选择题": "question_gen"
        }

        for s in adopted:
            if s["type"] == "resource_adjustment":
                content = s["content"]
                w = s.get("weight", 0.5)
                # 判断是增加还是减少
                for kw, rt in type_resource_map.items():
                    if kw in content:
                        if "增加" in content or "多" in content:
                            if rt not in weights["increase_resource_types"]:
                                weights["increase_resource_types"].append(rt)
                        elif "减少" in content or "少" in content:
                            if rt not in weights["decrease_resource_types"]:
                                weights["decrease_resource_types"].append(rt)

            elif s["type"] == "difficulty_adjustment":
                w = s.get("weight", 0.5)
                if w >= 0.5:
                    content = s["content"]
                    if "调高" in content or "提高难度" in content or "难" in content:
                        weights["difficulty"] = "调高"
                    elif "调低" in content or "降低难度" in content or "简单" in content:
                        weights["difficulty"] = "调低"
                    else:
                        weights["difficulty"] = weights["difficulty"] or "保持"

            elif s["type"] == "knowledge_priority":
                w = s.get("weight", 0.5)
                if w >= 0.3:
                    weights["knowledge_priority"].append(s["content"])

            elif s["type"] == "pace_advice":
                weights["pace_advice"] = s["content"]

        return weights
