# style_test_agent.py 修复完毕
import json
import re
from typing import Optional, Dict

class StyleAgent:
    def __init__(self):
        self.llm = self._create_default_llm()
        self.base = """你是PPT配色师，严格要求：
1. content_title_color固定#1A1A1A，text_body固定#333333，section_content_color固定#333333不能改
2. 全部色值6位#十六进制
3. 只输出纯JSON，无任何多余文字
{
    "cover_main_title_color": "#xxxxxx",
    "cover_subtitle_color": "#xxxxxx",
    "section_title_color": "#xxxxxx",
    "section_content_color": "#333333",
    "content_title_color": "#1A1A1A",
    "accent": "#xxxxxx",
    "text_body": "#333333"
}
风格："""

    def _create_default_llm(self):
        from utils.llm_config import get_chat_openai
        return get_chat_openai(
            model="qwen3.7-max",
            temperature=0.2,
            max_tokens=1024,
            api_key="sk-b524efccda47492d92168ed3470593a8",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_body={"enable_thinking": False}
        )

    def _safe_parse(self, text):
        code = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
        if code:
            raw = code.group(1)
        else:
            all_json = re.search(r'\{[\s\S]*\}', text)
            if not all_json:
                return None
            raw = all_json.group()
        raw = re.sub(r'[\x00-\x1f]','',raw.strip())
        raw = re.sub(r',\s*([}\]])',r'\1',raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def generate_async(self, topic: str, style_name: str):
        prompt = self.base + style_name
        res = await self.llm.ainvoke(prompt)
        color_data = self._safe_parse(res.content)
        if color_data:
            print("✅配色生成完成", color_data)
        else:
            print("❌配色解析失败，原始返回：", res.content)
        return color_data

    async def get_color(self, style_name: str):
        prompt = self.base + style_name
        res = await self.llm.ainvoke(prompt)
        color_data = self._safe_parse(res.content)
        if color_data:
            print("✅配色生成完成",color_data)
        else:
            print("❌配色解析失败，原始返回：",res.content)
        return color_data

# 测试
if __name__ == '__main__':
    async def main():
        agent = StyleAgent()
        await agent.get_color("dark_tech")
    asyncio.run(main())
