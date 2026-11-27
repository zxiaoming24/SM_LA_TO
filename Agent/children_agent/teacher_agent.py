"""
高深老师子Agent
负责以资深教师的身份提供专业指导和建议
"""

import os
import asyncio
from typing import Dict, Any, Optional
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai
from utils.async_llm_caller import call_llm_with_retry

# TTS辅助函数
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio


class TeacherAgent:
    """
    高深老师Agent - 专业的教育指导专家
    """

    def __init__(self):
        """初始化教师Agent"""
        self.llm = self._initialize_llm()
        self.prompt_template = self._create_prompt_template()

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.7, max_tokens=1500)
        except Exception as e:
            raise Exception(f"初始化教师Agent LLM失败: {e}")

    def _create_prompt_template(self) -> PromptTemplate:
        """创建教师角色的提示词模板"""
        template = """
你是一位拥有30年教学经验的资深教育家，精通教育学、心理学和学科教学法。你的特点是：

**角色定位：**
- 深厚的学术功底和丰富的教学经验
- 善于因材施教，能够根据学生特点制定个性化方案
- 注重启发式教学，引导学生独立思考
- 既严谨又温和，既有深度又易于理解

**教学理念：**
1. 以学生为中心，尊重个体差异
2. 理论与实践相结合
3. 培养批判性思维和创新能力
4. 注重学习方法和思维习惯的养成

**当前学生特征：**
{student_features}

**用户问题/需求：**
{user_query}

**请基于以上信息，以资深教师的身份提供：**
1. 对学生现状的专业分析
2. 针对性的学习建议和改进方案
3. 具体的行动步骤和资源推荐
4. 鼓励和引导性的话语

要求：
- 语言专业但不晦涩，深入浅出
- 建议具体可行，避免空泛
- 体现教育智慧和人文关怀
- 适当引用教育理论或成功案例
- 保持积极正向的态度

请以自然流畅的方式回应，展现资深教师的专业素养和教育情怀。
""".strip()

        return PromptTemplate.from_template(template)

    async def provide_guidance_async(
        self,
        student_features: Dict[str, Any],
        user_query: str,
        enable_tts: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        异步基于学生特征提供专业指导

        Args:
            student_features: 学生的特征数据（来自特征提取器）
            user_query: 用户的具体问题或需求
            enable_tts: 是否启用TTS语音合成
            user_id: 用户ID（可选，用于个性化音色）

        Returns:
            Dict: 包含guidance文本和可选的tts_audio_path
        """
        try:
            # 格式化学生特征
            features_text = self._format_student_features(student_features)

            # 生成提示词
            prompt = self.prompt_template.format(
                student_features=features_text,
                user_query=user_query
            )

            print("\n🎓 [教师Agent] 正在思考教学方案...")

            # 调用LLM获取建议(异步)
            response = await call_llm_with_retry(self.llm, prompt, error_msg="教师Agent LLM调用")
            guidance = response.content if hasattr(response, 'content') else str(response)

            print("✅ [教师Agent] 已生成专业指导")
            
            result = {
                "status": "success",
                "guidance": guidance
            }
            
            # TTS语音合成（可选）
            if enable_tts:
                tts_path = await generate_tts_audio(
                    text=guidance,
                    agent_name="teacher_agent",
                    user_id=user_id
                )
                if tts_path:
                    result["tts_audio_path"] = tts_path
            
            return result

        except Exception as e:
            error_msg = f"教师Agent执行失败: {e}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "guidance": f"抱歉，我在分析时遇到了一些问题。请稍后重试。错误信息：{str(e)}",
                "error": str(e)
            }

    async def provide_quick_advice_async(self, question: str, enable_tts: bool = False, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        异步快速回答教育相关问题（不需要学生特征）

        Args:
            question: 教育相关的问题
            enable_tts: 是否启用TTS语音合成
            user_id: 用户ID（可选，用于TTS音色）

        Returns:
            Dict: 包含advice文本和可选的tts_audio_path
        """
        try:
            template = PromptTemplate.from_template("""
你是一位经验丰富的资深教师。请简洁专业地回答以下教育相关问题：

问题：{question}

要求：
- 回答要专业、准确、实用
- 控制在200字以内
- 体现教育智慧
""")

            prompt = template.format(question=question)
            response = await call_llm_with_retry(self.llm, prompt, error_msg="教师Agent快速建议LLM调用")
            advice = response.content if hasattr(response, 'content') else str(response)

            result = {
                "status": "success",
                "advice": advice
            }
            
            # TTS语音合成（可选）
            if enable_tts:
                tts_path = await generate_tts_audio(
                    text=advice,
                    agent_name="teacher_agent_quick",
                    user_id=user_id
                )
                if tts_path:
                    result["tts_audio_path"] = tts_path
            
            return result

        except Exception as e:
            return {
                "status": "error",
                "advice": f"抱歉，我暂时无法回答这个问题。错误：{str(e)}",
                "error": str(e)
            }

    def _format_student_features(self, features: Dict[str, Any]) -> str:
        """将学生特征数据格式化为可读文本"""
        if not features:
            return "暂无学生特征数据"

        lines = []

        # 学术背景
        if 'academic_background' in features:
            ab = features['academic_background']
            lines.append("【学术背景】")
            lines.append(f"  - 专业偏好: {ab.get('major_preference', '未知')}")
            lines.append(f"  - 知识水平: {ab.get('knowledge_level', '未知')}")
            lines.append(f"  - 能力倾向: {ab.get('ability_tendency', '未知')}")
            lines.append(f"  - 基础水平: {ab.get('foundation_level', '未知')}")
            lines.append(f"  - 评分: {ab.get('score', 0)}/100")
            lines.append("")

        # 学习行为
        if 'learning_behavior' in features:
            lb = features['learning_behavior']
            lines.append("【学习行为】")
            lines.append(f"  - 学习风格: {lb.get('learning_style', '未知')}")
            lines.append(f"  - 学习节奏: {lb.get('learning_pace', '未知')}")
            lines.append(f"  - 互动参与: {lb.get('interaction_level', '未知')}")
            lines.append(f"  - 资源偏好: {lb.get('resource_preference', '未知')}")
            lines.append(f"  - 评分: {lb.get('score', 0)}/100")
            lines.append("")

        # 目标动机
        if 'goal_motivation' in features:
            gm = features['goal_motivation']
            lines.append("【目标动机】")
            lines.append(f"  - 短期目标: {gm.get('short_term_goals', '未知')}")
            lines.append(f"  - 长期规划: {gm.get('long_term_career', '未知')}")
            lines.append(f"  - 动机强度: {gm.get('motivation_strength', '未知')}")
            lines.append(f"  - 成就期望: {gm.get('achievement_expectation', '未知')}")
            lines.append(f"  - 评分: {gm.get('score', 0)}/100")
            lines.append("")

        # 认知能力
        if 'cognitive_abilities' in features:
            ca = features['cognitive_abilities']
            lines.append("【认知能力】")
            lines.append(f"  - 逻辑思维: {ca.get('logical_thinking', '未知')}")
            lines.append(f"  - 创造性思维: {ca.get('creative_thinking', '未知')}")
            lines.append(f"  - 问题解决: {ca.get('problem_solving', '未知')}")
            lines.append(f"  - 元认知能力: {ca.get('metacognition', '未知')}")
            lines.append(f"  - 评分: {ca.get('score', 0)}/100")
            lines.append("")

        # 综合评分
        if 'summary_scores' in features:
            ss = features['summary_scores']
            lines.append("【综合评估】")
            dim_scores = ss.get('dimension_scores', [])
            if len(dim_scores) == 4:
                lines.append(f"  - 各维度评分: 学术背景={dim_scores[0]}, 学习行为={dim_scores[1]}, "
                           f"目标动机={dim_scores[2]}, 认知能力={dim_scores[3]}")
            lines.append(f"  - 总体评分: {ss.get('overall_score', 0)}/100")

        return "\n".join(lines)

    async def generate_plan_options(
        self,
        student_features: Dict[str, Any],
        user_query: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成3套各具特色的学习方案供用户选择。

        Args:
            student_features: 学生特征数据
            user_query: 用户的问题/需求
            user_id: 用户ID

        Returns:
            Dict: 包含 plans 列表，每套方案含 name, description, style_tags, difficulty, focus, detail
        """
        try:
            features_text = self._format_student_features(student_features)

            prompt = f"""你是一位拥有30年教学经验的资深教育规划专家。请根据以下学生信息，设计3套截然不同的学习方案。

## 学生信息
{features_text}

## 学生需求
{user_query}

## 要求
请设计3套各具特色的学习方案，每套方案要有明确的定位和风格差异。

输出格式（严格的JSON列表，不要加额外说明）：
[
  {{
    "plan_id": "A",
    "name": "方案名称（2-4字，如"稳扎稳打"）",
    "subtitle": "一句话副标题（10字以内）",
    "description": "方案简介（30字以内，说明适合什么类型的学生）",
    "style_tags": ["标签1", "标签2", "标签3"],
    "difficulty": "easy/medium/hard",
    "focus": "侧重点（如'基础巩固+循序渐进'）",
    "detail": "方案详细说明（80字以内，包括学习节奏、资源类型、练习策略等）",
    "estimated_effort": "预估每日投入时间"
  }},
  ...
]

3套方案应差异化明显，例如：
- 方案A：系统性、循序渐进、适合基础薄弱的学生
- 方案B：实践驱动、项目导向、适合动手能力强的学生  
- 方案C：高效突击、重点突破、适合需要快速见效的学生

直接输出JSON数组，不要包含```json等标记。"""
            
            print("\n🎓 [教师Agent] 正在生成3套学习方案...")
            response = await call_llm_with_retry(self.llm, prompt, error_msg="教师Agent学习方案LLM调用")
            text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON
            import json
            import re
            
            # 尝试直接解析
            plans = None
            try:
                plans = json.loads(text)
            except json.JSONDecodeError:
                # 尝试提取JSON数组
                match = re.search(r'\[[\s\S]*\]', text)
                if match:
                    try:
                        plans = json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
            
            if not plans or not isinstance(plans, list) or len(plans) < 3:
                # 兜底：返回3套默认方案
                plans = [
                    {
                        "plan_id": "A",
                        "name": "稳扎稳打",
                        "subtitle": "系统学习打基础",
                        "description": "适合基础薄弱，需要系统学习的学生",
                        "style_tags": ["系统性", "循序渐进", "扎实"],
                        "difficulty": "easy",
                        "focus": "基础巩固+循序渐进",
                        "detail": "从基础概念开始，逐步深入；每章配练习题巩固；适合每天固定时间学习",
                        "estimated_effort": "每天1-2小时"
                    },
                    {
                        "plan_id": "B",
                        "name": "实践驱动",
                        "subtitle": "项目中学真本事",
                        "description": "适合动手能力强，喜欢在实践中学习的学生",
                        "style_tags": ["实践", "项目导向", "互动"],
                        "difficulty": "medium",
                        "focus": "项目实战+边做边学",
                        "detail": "通过实际项目驱动学习，在做中学；遇到问题再查理论；适合喜欢挑战的学生",
                        "estimated_effort": "每天2-3小时"
                    },
                    {
                        "plan_id": "C",
                        "name": "高效突击",
                        "subtitle": "重点突破快提升",
                        "description": "适合时间紧张，需要快速掌握核心的学生",
                        "style_tags": ["高效", "重点突破", "精讲"],
                        "difficulty": "hard",
                        "focus": "核心知识点+高频考点",
                        "detail": "聚焦核心知识点和高频考点；以题带学，快速建立知识框架；适合有基础想快速提升的学生",
                        "estimated_effort": "每天1-1.5小时"
                    }
                ]

            return {
                "status": "success",
                "plans": plans[:3]  # 最多3套
            }

        except Exception as e:
            print(f"❌ [教师Agent] 方案生成失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "plans": [],
                "error": str(e)
            }

    def get_agent_info(self) -> Dict[str, str]:
        """获取Agent的基本信息"""
        return {
            "name": "高深老师",
            "role": "资深教育专家",
            "description": "拥有30年教学经验的资深教育家，擅长因材施教和启发式教学",
            "capabilities": [
                "学生特征分析与诊断",
                "个性化学习方案制定",
                "教育问题咨询",
                "学习方法指导",
                "心理疏导与激励"
            ]
        }
