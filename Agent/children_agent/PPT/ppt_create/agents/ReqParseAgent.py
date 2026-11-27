import json
import re
import asyncio
from typing import Optional, Dict
from langchain_openai import ChatOpenAI

class ReqParseAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="qwen3.7-max",
            api_key="sk-b524efccda47492d92168ed3470593a8",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.2,
            extra_body={"enable_thinking": False}
        )
        self.base_prompt = '''你是PPT需求解析专家，根据用户输入，提取三项内容：
1.topic：PPT完整主题名称
2.style_name：只能从以下四种风格中选择：
   - business_blue：商务蓝色，适合正式商务场景
   - dark_tech：深色科技，适合技术/编程主题
   - warm_minimal：简约温馨，适合轻松友好的话题
   - ink_wash：水墨风格，适合中国传统文化相关主题
   用户没说明默认business_blue
3.knowledge_list：核心知识点列表，3~6个

严格只输出JSON，无任何多余文字，格式：
{
    "topic":"xxx",
    "style_name":"xxx",
    "knowledge_list":["知识点1","知识点2"]
}

用户内容：'''

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            res = re.search(r"\{[\s\S]+\}", text)
            if not res:
                return None
            raw = re.sub(r'[\x00-\x1f]', '', res.group())
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def run(self, user_input: str) -> Optional[Dict]:
        prompt = self.base_prompt + user_input
        resp = await self.llm.ainvoke(prompt)
        data = self._parse_json(resp.content)
        if data:
            print("✅需求解析成功：", data)
        else:
            print("❌解析失败")
        return data

#测试
if __name__ == "__main__":
    async def main():
        agent = ReqParseAgent()
        res = await agent.run("讲解Java接口，深色科技风格")
        print(res)
    asyncio.run(main())