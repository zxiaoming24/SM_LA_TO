"""
代码评判Agent
独立于 practice_agent 的判题功能，专门处理用户直接提问"这段代码有什么问题"的场景。
与 practice_agent.judge_code_async 不同：
  - practice_agent 的判题：已有练习题 → 用户提交代码 → 针对题目要求评分（有标准答案/测试用例）
  - judge_agent 的评判：用户直接贴代码 → 排查错误/解释问题/给出修复建议（无预期输出对比）
"""

import json
from typing import Dict, Any, Optional
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai
from utils.async_llm_caller import call_llm_with_retry


class JudgeAgent:
    """
    代码评判Agent - 分析用户提交的代码片段，排查错误并给出修复建议
    """

    def __init__(self):
        """初始化代码评判Agent"""
        self.llm = self._initialize_llm()
        self.debug_template = self._create_debug_template()

    def _initialize_llm(self):
        """初始化LLM模型"""
        try:
            return get_chat_openai(temperature=0.3, max_tokens=3000, streaming=True)
        except Exception as e:
            raise Exception(f"初始化JudgeAgent LLM失败: {e}")

    def _create_debug_template(self) -> PromptTemplate:
        """创建代码调试/纠错提示词模板"""
        template = """
你是一位经验丰富的编程导师，擅长快速定位代码中的错误并给出清晰易懂的修复指导。

**用户提交的代码/问题：**
```
{user_input}
```

**分析要求（逐步执行）：**

1. **语法检查** — 检查代码是否有编译/语法错误（如拼写错误、缺少分号、括号不匹配等）
2. **逻辑检查** — 检查代码逻辑是否合理，是否有潜在的死循环、边界条件遗漏等
3. **语义检查** — 检查代码语义是否正确（如调用未定义的函数、变量类型不匹配等）
4. **修复建议** — 给出具体、可操作的修复方案，必要时附上修正后的代码片段

**输出格式（JSON，只输出JSON，不要包含```或其他文字）：**
{{
  "has_error": true/false,
  "error_type": "语法错误/逻辑错误/语义错误/运行时错误/无错误",
  "error_summary": "简洁的一句话概括问题",
  "details": [
    {{
      "line": 出错行号（若可确定，否则填null）,
      "severity": "error/warning/advice",
      "description": "具体问题描述",
      "fix_suggestion": "如何修复该问题",
      "fixed_code": "修正后的代码片段（仅当问题明确时提供）"
    }}
  ],
  "explanation": "用通俗易懂的语言向编程学习者解释这段代码有什么问题，为什么会出现这个问题",
  "fixed_code_full": "修复后完整正确的代码（如果合适给出）",
  "learning_advice": "针对此类错误给出一条学习建议，帮助用户避免再犯同类错误"
}}

**重要原则：**
- 语气要耐心、鼓励，不要打击学习者的信心
- 对不明显的问题可以在 explanation 中补充背景知识
- 如果代码没有明显错误，但可以优化，将 error_type 设为"无错误"，在 details 中给出 optimization 建议
- 对于 `#include` 拼写错误等初学者常见问题，要特别友好地指出并解释
- 如果用户输入不是代码（如自然语言问题），has_error 设为 false，details 为空数组，explanation 说明未检测到代码
""".strip()

        return PromptTemplate.from_template(template)

    async def debug_code_async(self, user_input: str) -> Dict[str, Any]:
        """
        异步评判/调试用户代码

        Args:
            user_input: 用户的完整输入（包含代码片段和可能的描述文字）

        Returns:
            Dict: 评判结果，包含错误分析、修复建议等
        """
        try:
            prompt = self.debug_template.format(user_input=user_input)

            print("\n🔍 [JudgeAgent] 正在分析代码...")
            response = await call_llm_with_retry(self.llm, prompt, error_msg="JudgeAgent LLM调用")
            result_text = response.content if hasattr(response, 'content') else str(response)

            result = self._parse_json_response(result_text)
            if result:
                print(f"✅ [JudgeAgent] 分析完成: 存在错误={result.get('has_error', 'unknown')}, "
                      f"错误类型={result.get('error_type', 'unknown')}")
                return result

            print("❌ [JudgeAgent] JSON解析失败，使用兜底结果")
            return self._get_default_result(user_input)

        except Exception as e:
            print(f"❌ [JudgeAgent] 分析过程异常: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_result(user_input)

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """从LLM回复中提取并解析JSON"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith("```"):
            # 移除代码块标记
            lines = text.split("\n")
            cleaned = []
            in_code = False
            for line in lines:
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    cleaned.append(line)
            text = "\n".join(cleaned)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 {} 包裹的部分
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _get_default_result(self, user_input: str) -> Dict[str, Any]:
        """兜底结果"""
        return {
            "has_error": False,
            "error_type": "未知",
            "error_summary": "分析过程出现异常，无法完成代码评判",
            "details": [],
            "explanation": "很抱歉，系统在分析您的代码时遇到了问题，请稍后再试。您可以尝试将代码片段描述得更清晰一些。",
            "fixed_code_full": None,
            "learning_advice": "如果问题持续存在，可以尝试简化代码后逐步排查。"
        }


# ==================== 快捷入口 ====================

async def judge_code(user_input: str) -> Dict[str, Any]:
    """
    快捷函数：评判用户代码
    供外部直接调用，无需实例化 JudgeAgent

    Args:
        user_input: 用户的完整输入（代码+描述）

    Returns:
        Dict: 评判结果
    """
    agent = JudgeAgent()
    return await agent.debug_code_async(user_input)
