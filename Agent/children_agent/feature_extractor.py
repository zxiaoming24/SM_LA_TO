import os
import json
import re
import asyncio
from typing import Dict, Any, Union, Optional, List
from utils.prompt_loader import PromptLoader
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai


class StudentFeatureExtractor:
    """
    学生特征提取器，使用LLM从学生信息中自动抽取特征并进行维度评分
    """

    def __init__(self, prompt_filename: str = None):
        """
        初始化特征提取器

        Args:

            prompt_filename: 提示词文件名（可选，默认为 prompts/student_feature_extraction_prompt.txt）
        """
        # 获取项目根目录（all_tame_channel）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        prompts_dir = os.path.join(project_root, "prompts")

        # 初始化提示词加载器（指定 prompts 目录）
        self.prompt_loader = PromptLoader(base_dir=prompts_dir)

        # 设置默认提示词文件名
        if prompt_filename is None:
            prompt_filename = "student_feature_extraction_prompt.txt"

        # 1. 获取提示词内容 - 优先使用文件，失败时使用内置安全模板
        self.prompt_template_str = self._get_prompt_content(prompt_filename)

        # 2. 创建提示模板 - 使用获取到的内容
        self.prompt_template = self._create_prompt_template()

        # 3. 初始化LLM
        self.llm = self._initialize_llm()

        # 4. JSON解析的正则表达式
        self.json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
        self.json_only_pattern = re.compile(r'\{.*\}', re.DOTALL)

    def _get_prompt_content(self, filename: str) -> str:
        """获取提示词内容，优先从文件加载，失败时使用内置安全模板"""
        try:
            content = self.prompt_loader.load_prompt(filename)
            print(f"✅ 成功加载提示词文件: {filename}")
            return content
        except FileNotFoundError:
            print(f"⚠️  提示词文件不存在: {filename}")
            return self._get_safe_prompt_template()  # 直接使用安全模板
        except Exception as e:
            print(f"⚠️  加载提示词文件失败: {e}")
            return self._get_safe_prompt_template()  # 直接使用安全模板

    def _create_prompt_template(self) -> PromptTemplate:
        """创建提示模板，处理格式化问题"""
        try:
            # 预处理：确保JSON部分的大括号被正确转义
            safe_template = self._sanitize_template(self.prompt_template_str)
            template = PromptTemplate.from_template(safe_template)
            print("✅ 成功创建提示模板")
            return template
        except ValueError as e:
            if "Invalid format specifier" in str(e):
                print(f"⚠️  提示词格式错误: {e}")
                print("🔄 修复格式后重试...")
                fixed_template = self._fix_template_format(self.prompt_template_str)
                return PromptTemplate.from_template(fixed_template)
            else:
                raise
        except Exception as e:
            print(f"⚠️  创建提示模板时出错: {e}")
            # 使用安全模板重新创建
            safe_template = self._get_safe_prompt_template()
            return PromptTemplate.from_template(safe_template)

    def _sanitize_template(self, template_str: str) -> str:
        """预处理模板字符串，转义JSON部分的大括号"""
        # 如果已经转义过了（包含 {{ 或 }}），跳过避免二次转义
        if '{{' in template_str and '}}' in template_str:
            return template_str
        # 分割模板，只处理JSON部分
        parts = template_str.split('**输出格式要求：**')
        if len(parts) > 1:
            # 保留前面部分不变
            prefix = parts[0]
            # 处理JSON部分
            json_part = parts[1]
            # 转义大括号，但保留{student_input}
            json_part = json_part.replace('{', '{{').replace('}', '}}')
            json_part = json_part.replace('{{student_input}}', '{student_input}')
            return prefix + '**输出格式要求：**' + json_part
        return template_str

    def _fix_template_format(self, template_str: str) -> str:
        """修复提示词格式问题"""
        # 如果已经转义过了，跳过避免二次转义
        if '{{' in template_str and '}}' in template_str:
            return template_str
        # 简单修复：转义所有大括号，但保留变量
        fixed = template_str.replace('{', '{{').replace('}', '}}')
        fixed = fixed.replace('{{student_input}}', '{student_input}')
        return fixed

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.3, max_tokens=2000)
        except Exception as e:
            raise Exception(f"初始化LLM失败: {e}")

    def _get_safe_prompt_template(self) -> str:
        """获取内置的安全提示词模板（带评分功能）"""
        return """
你是一位专业的教育数据分析师，请从以下学生信息中自动抽取关键特征，按照指定维度进行结构化输出，并为每个维度计算0-100分的综合评分。

**学生信息：**
{student_input}

**特征提取维度：**
1. 学术背景维度
   - 专业领域偏好：学生感兴趣的学科领域
   - 学科知识掌握：基础学科知识水平
   - 学术能力倾向：理论研究/实践应用倾向
   - 学习基础水平：入门/中级/高级

2. 学习行为维度
   - 学习风格：视觉型/听觉型/动手型/混合型
   - 学习节奏：快速学习者/深度思考者/稳定学习者
   - 互动参与度：高/中/低
   - 资源使用偏好：视频/文本/实践/讨论

3. 目标动机维度
   - 短期学习目标：1-6个月内具体学习目标
   - 长期职业规划：3-5年职业发展期望
   - 学习动机强度：内在动机/外在动机/混合动机
   - 成就期望水平：高/中/低

4. 认知能力维度
   - 逻辑思维能力：分析推理能力评估
   - 创造性思维：创新解决问题能力
   - 问题解决策略：系统性/直觉性/试错性
   - 元认知能力：自我监控调节能力

**评分规则：**
- 每个维度根据特征表现计算0-100分的综合评分
- 评分标准：
  * 90-100分：维度表现优秀，特征明显且积极
  * 80-89分：维度表现良好，特征较为突出
  * 70-79分：维度表现中等，特征基本符合
  * 60-69分：维度表现一般，特征不够明显
  * 0-59分：维度表现较弱，特征不明显或缺失
- 评分必须基于学生信息中的具体表现，不能主观臆断

**输出格式要求：**
请严格按照以下JSON格式输出，确保每个维度都有对应特征和评分（只输出JSON，不要包含任何其他内容）：
{{
  "academic_background": {{
    "major_preference": "",
    "knowledge_level": "",
    "ability_tendency": "",
    "foundation_level": "",
    "score": 0
  }},
  "learning_behavior": {{
    "learning_style": "",
    "learning_pace": "",
    "interaction_level": "",
    "resource_preference": "",
    "score": 0
  }},
  "goal_motivation": {{
    "short_term_goals": "",
    "long_term_career": "",
    "motivation_strength": "",
    "achievement_expectation": "",
    "score": 0
  }},
  "cognitive_abilities": {{
    "logical_thinking": "",
    "creative_thinking": "",
    "problem_solving": "",
    "metacognition": "",
    "score": 0
  }},
  "summary_scores": {{
    "dimension_scores": [50, 50, 50, 50],
    "overall_score": 50
  }}
}}

**重要提醒：**
- 仅基于提供的学生信息进行特征提取和评分
- 保持客观分析，避免主观臆断
- 如果某维度信息不足，特征用"信息不足"标记，评分设为50分
- 评分必须是整数，范围0-100
- 输出必须是纯JSON格式，无其他内容
- summary_scores中的dimension_scores数组必须严格按照[学术背景, 学习行为, 目标动机, 认知能力]的顺序
- 不要包含任何解释、注释或额外文本
""".strip()

    async def extract_features_async(self, student_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """异步从学生数据中提取特征"""
        try:
            student_text = self._format_student_data(student_data)

            prompt = self.prompt_template.format(student_input=student_text)

            print("\n=== 生成的提示词 ===")
            print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
            print("=" * 50)

            # ★★★ 使用异步调用 ★★★
            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            print("\n=== LLM 响应 ===")
            print(response_text[:500] + "..." if len(response_text) > 500 else response_text)
            print("=" * 50)

            return self._parse_llm_response(response_text)

        except Exception as e:
            print(f"特征提取失败: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_features_with_scores()

    def _format_student_data(self, data: Union[Dict[str, Any], str]) -> str:
        """格式化学生数据为文本"""
        if isinstance(data, str):
            return data.strip()

        if isinstance(data, dict):
            formatted_lines = []
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    value_str = json.dumps(value, ensure_ascii=False, indent=2)
                else:
                    value_str = str(value)
                formatted_lines.append(f"{key}: {value_str}")
            return "\n".join(formatted_lines)

        return str(data)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应，提取JSON内容并验证评分格式"""
        try:
            # 尝试提取JSON块
            json_match = self.json_pattern.search(response)
            if json_match:
                json_str = json_match.group(1)
                print("✅ 找到JSON代码块")
            else:
                # 尝试直接匹配JSON对象
                json_match = self.json_only_pattern.search(response)
                if json_match:
                    json_str = json_match.group(0)
                    print("✅ 找到直接JSON对象")
                else:
                    cleaned_response = response.strip()
                    if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                        json_str = cleaned_response
                        print("✅ 响应本身就是JSON")
                    else:
                        print("❌ 未找到有效的JSON格式")
                        return self._get_default_features_with_scores()

            json_str = json_str.strip()
            features = json.loads(json_str)

            # ★★★ 验证并补全全部8维度 ★★★
            all_8_dims = [
                "academic_background", "learning_behavior", "goal_motivation",
                "cognitive_abilities", "emotional_state", "social_interaction",
                "time_management", "creativity_innovation"
            ]
            missing_dims = [d for d in all_8_dims if d not in features]
            if missing_dims:
                print(f"⚠️  LLM返回缺少维度: {missing_dims}，使用默认值补全")
                for dim in missing_dims:
                    features[dim] = {"score": 50, "note": "LLM未返回，使用默认值"}

            # ★★★ 计算所有8维度的评分汇总 ★★★
            dim_scores = []
            for dim in all_8_dims:
                score = features.get(dim, {}).get('score', 50)
                # 确保评分在 0-100 范围内
                try:
                    score = max(0, min(100, int(score)))
                except (ValueError, TypeError):
                    score = 50
                dim_scores.append(score)

            # 计算总分（8维度平均）
            overall_score = sum(dim_scores) // len(dim_scores)
            features['summary_scores'] = {
                'dimension_scores': dim_scores,
                'overall_score': overall_score
            }
            print(f"✅ 8维度评分计算完成 - 总体评分: {overall_score}/100")

            return features    #  将评分进行内置到feature中返回

        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return self._get_default_features_with_scores()
        except Exception as e:
            print(f"❌ 解析响应时发生错误: {e}")
            return self._get_default_features_with_scores()

    def _get_default_features_with_scores(self) -> Dict[str, Any]:
        """获取带默认评分的特征模板（8个维度）"""
        return {
            "academic_background": {
                "major_preference": "信息不足",
                "knowledge_level": "信息不足",
                "ability_tendency": "信息不足",
                "foundation_level": "信息不足",
                "score": 50
            },
            "learning_behavior": {
                "learning_style": "信息不足",
                "learning_pace": "信息不足",
                "interaction_level": "信息不足",
                "resource_preference": "信息不足",
                "score": 50
            },
            "goal_motivation": {
                "short_term_goals": "信息不足",
                "long_term_career": "信息不足",
                "motivation_strength": "信息不足",
                "achievement_expectation": "信息不足",
                "score": 50
            },
            "cognitive_abilities": {
                "logical_thinking": "信息不足",
                "creative_thinking": "信息不足",
                "problem_solving": "信息不足",
                "metacognition": "信息不足",
                "score": 50
            },
            "emotional_state": {
                "interest_level": "信息不足",
                "frustration_tolerance": "信息不足",
                "anxiety_level": "信息不足",
                "confidence_level": "信息不足",
                "score": 50
            },
            "social_interaction": {
                "collaboration_tendency": "信息不足",
                "help_seeking_pattern": "信息不足",
                "knowledge_sharing_willingness": "信息不足",
                "peer_influence": "信息不足",
                "score": 50
            },
            "time_management": {
                "learning_regularity": "信息不足",
                "priority_judgment": "信息不足",
                "procrastination_tendency": "信息不足",
                "time_allocation_efficiency": "信息不足",
                "score": 50
            },
            "creativity_innovation": {
                "divergent_thinking": "信息不足",
                "cross_domain_association": "信息不足",
                "experimental_exploration": "信息不足",
                "original_expression": "信息不足",
                "score": 50
            },
            "summary_scores": {
                "dimension_scores": [50, 50, 50, 50, 50, 50, 50, 50],
                "overall_score": 50
            }
        }

    def get_dimension_scores(self, features: Dict[str, Any]) -> List[int]:
        """
        获取八个维度的评分数组

        Returns:
            List[int]: [学术背景, 学习行为, 目标动机, 认知能力, 情绪状态, 社交互动, 时间管理, 创新创造] 的评分
        """
        if 'summary_scores' in features and 'dimension_scores' in features['summary_scores']:
            scores = features['summary_scores']['dimension_scores']
            if isinstance(scores, list) and len(scores) == 8:
                return [max(0, min(100, int(score))) for score in scores]

        # 从各维度提取评分
        return [
            features.get('academic_background', {}).get('score', 50),
            features.get('learning_behavior', {}).get('score', 50),
            features.get('goal_motivation', {}).get('score', 50),
            features.get('cognitive_abilities', {}).get('score', 50),
            features.get('emotional_state', {}).get('score', 50),
            features.get('social_interaction', {}).get('score', 50),
            features.get('time_management', {}).get('score', 50),
            features.get('creativity_innovation', {}).get('score', 50)
        ]

    def get_score_array(self, features: Dict[str, Any], max_value: int = 100) -> List[int]:
        """
        获取标准化的评分数组，用于图表展示

        Args:
            features: 特征数据
            max_value: 满分值，默认100

        Returns:
            List[int]: 标准化的评分数组
        """
        raw_scores = self.get_dimension_scores(features)
        # 标准化到指定范围
        return [int((score / 100) * max_value) for score in raw_scores]   #  显然返回的是列表

    def validate_features(self, features: Dict[str, Any]) -> bool:
        """验证特征数据的完整性（8个维度）"""
        required_keys = [
            "academic_background", "learning_behavior",
            "goal_motivation", "cognitive_abilities",
            "emotional_state", "social_interaction",
            "time_management", "creativity_innovation",
            "summary_scores"
        ]

        for key in required_keys:
            if key not in features:
                print(f"❌ 缺少必需的维度: {key}")
                return False

        return True

    def save_prompt_template(self, filename: str = None):     #   没有提示词的时候采用
        """保存当前使用的提示词模板"""
        if filename is None:
            filename = "student_feature_extraction_prompt.txt"

        try:
            self.prompt_loader.save_prompt(filename, self.prompt_template_str)
            print(f"✅ 提示词模板已保存到: {filename}")
        except Exception as e:
            print(f"❌ 保存提示词模板失败: {e}")