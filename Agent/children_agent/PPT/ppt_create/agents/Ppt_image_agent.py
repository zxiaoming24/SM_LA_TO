# Ppt_image_agent.py - 只为封面和尾页生成背景图
import json
import re
from typing import Optional, Dict

class ImageDescAgent:
    def __init__(self):
        self.llm = self._create_default_llm()
        self.base_prompt = """
你是PPT背景图提示词工程师，只需要为封面页和最后一页（总结页）生成背景图提示词。
输入：PPT主题、风格、配色
输出固定JSON结构：
{
    "cover_bg_prompt":"封面背景英文prompt",
    "last_bg_prompt":"尾页背景英文prompt"
}
规则：
- 只生成2张背景图：封面和尾页
- 背景图必须是纯装饰性图片，无任何文字、无字母、无符号、无代码、无设备
- 风格：简约抽象渐变背景，配合PPT主题的专业感，色调与配色方案一致
- 封面：大气、有冲击力，适合放标题
- 尾页：简洁、留白多，适合放总结要点
- 全部用英文描述，16:9比例
- 禁止出现任何文字/字母/数字/代码/人物/设备

PPT主题：
"""

    def _create_default_llm(self):
        from utils.llm_config import get_chat_openai
        return get_chat_openai(
            model="qwen3.7-max",
            temperature=0.2,
            api_key="sk-b524efccda47492d92168ed3470593a8",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_body={"enable_thinking": False}
        )

    def _safe_parse(self, text):
        code = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
        if code:
            raw = code.group(1)
        else:
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
                return None
            raw = text[first_brace:last_brace + 1]
        raw = re.sub(r'[\x00-\x1F\x7F]', '', raw.strip())
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def generate(self, topic: str, style_name: str, color_dict: dict, outline: dict = None):
        full_input = f"{topic}\n风格：{style_name}\n配色：{str(color_dict)}"
        prompt = self.base_prompt + full_input
        resp = await self.llm.ainvoke(prompt)
        bg_res = self._safe_parse(resp.content)
        if bg_res:
            print("✅封面背景提示词：", bg_res.get("cover_bg_prompt", ""))
            print("✅尾页背景提示词：", bg_res.get("last_bg_prompt", ""))
        # 如果有输入 outline，在其基础上叠加背景提示词，返回完整的 outline 结构
        if outline and "pages" in outline:
            enhanced = {**outline, **(bg_res or {})}
            return enhanced
        return bg_res

# 测试
if __name__ == "__main__":
    import asyncio
    from ReqParseAgent import ReqParseAgent
    from Ppt_text_agent import PPTOutlineAgent
    from style_test_agent import StyleAgent
    req = ReqParseAgent()
    info = asyncio.run(req.run("讲解Java接口，深色科技"))
    color = asyncio.run(StyleAgent().get_color("dark_tech"))
    agent = ImageDescAgent()
    result = asyncio.run(agent.generate(info["topic"], info["style_name"], color))
    print(result)
