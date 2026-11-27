"""
问题提炼子Agent
负责将用户的学习问题提炼为精确的PPT大纲标题（20字以内）
"""

import os
import asyncio
from typing import Dict, Any
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai


class QuestionRefinerAgent:
    """
    问题提炼Agent - 将学习问题精炼为简洁的大纲标题
    """

    def __init__(self):
        """初始化问题提炼Agent"""
        self.llm = self._initialize_llm()
        self.prompt_template = self._create_prompt_template()

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.3, max_tokens=100)
        except Exception as e:
            raise Exception(f"初始化问题提炼Agent LLM失败: {e}")

    def _create_prompt_template(self) -> PromptTemplate:
        """创建问题提炼的提示词模板"""
        template = """
你是一位专业的教育内容分析师，擅长将学生的学习问题提炼为精确、简洁的知识点标题。

**任务说明：**
将用户提出的学习问题或疑惑，提炼为一个精确的PPT大纲标题。

**要求：**
1. 标题必须准确反映用户要学习的核心知识点
2. 字数严格控制在20字以内（含标点符号）
3. 去掉口语化表达，使用专业术语
4. 保持简洁明了，突出核心概念
5. 只输出提炼后的标题，不要有任何解释或其他内容

**示例：**
- 输入："指针这里不会，搞不懂怎么用"
  输出："指针的概念与使用方法"

- 输入："我不太理解递归是怎么工作的"
  输出："递归算法的工作原理"

- 输入："PyTorch自动求导原理不太懂"
  输出："PyTorch自动求导"

- 输入："Transformer的注意力机制原理"
  输出："注意力机制原理"

**用户问题：**
{user_question}

**请输出提炼后的标题（20字以内）：**
""".strip()

        return PromptTemplate.from_template(template)

    async def refine_question_async(self, user_question: str) -> str:
        """
        异步将用户问题提炼为精确的大纲标题
        
        Args:
            user_question: 用户提出的学习问题
            
        Returns:
            str: 提炼后的标题（20字以内）
        """
        try:
            prompt = self.prompt_template.format(user_question=user_question)
            
            print("\n🔍 [问题提炼Agent] 正在提炼问题...")
            
            # 调用LLM获取提炼结果(异步)
            response = await self.llm.ainvoke(prompt)
            refined_title = response.content if hasattr(response, 'content') else str(response)
            
            # 清理结果：去除多余空格和换行
            refined_title = refined_title.strip().replace('\n', '').replace('"', '')
            
            # 确保不超过20字
            if len(refined_title) > 20:
                refined_title = refined_title[:20]
            
            print(f"✅ 问题提炼完成: {refined_title}")   #   之后前端调用pptx的时候传递的就是它
            
            return refined_title
            
        except Exception as e:
            error_msg = f"问题提炼Agent执行失败: {e}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            
            # 失败时使用简化策略：直接截取前20字
            return user_question[:20]

    async def generate_outline_from_question(self, user_question: str) -> Dict[str, Any]:

          #   注意在前端进行调用pptx的时候所需要的大纲信息  直接从上面函数返回的信息中得到就行，当前函数只是测试的时候出现
        """
        基于用户问题生成简化的PPT大纲结构
        
        Args:
            user_question: 用户提出的学习问题
            
        Returns:
            Dict: 包含提炼标题和简单大纲的结构
        """
        # 提炼标题（异步）
        refined_title = await self.refine_question_async(user_question)
        
        # 构建简单的大纲结构
        outline = {
            "refined_title": refined_title,
            "original_question": user_question,
            "title_length": len(refined_title),
            "outline_structure": [
                {
                    "section": "一、概念定义",
                    "description": f"{refined_title}的基本概念"
                },
                {
                    "section": "二、核心原理",
                    "description": f"{refined_title}的工作原理"
                },
                {
                    "section": "三、实际应用",
                    "description": f"{refined_title}的使用场景"
                },
                {
                    "section": "四、常见问题",
                    "description": f"{refined_title}的常见误区"
                },
                {
                    "section": "五、总结回顾",
                    "description": f"{refined_title}的要点总结"
                }
            ]
        }
        return outline

