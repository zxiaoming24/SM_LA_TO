# Ppt_text_agent.py 最终可用完整版
import json
import re
from typing import Dict, Optional

def safe_parse_json(text: str) -> Optional[Dict]:
    if not text:
        print(f"❌ safe_parse_json: 文本为空")
        return None
    print(f"📊 safe_parse_json: 输入文本长度: {len(text)}")
    block = re.search(r'```(?:json)?\n([\s\S]+?)\n```', text)
    if block:
        raw = block.group(1)
        print(f"📋 safe_parse_json: 提取到代码块，长度: {len(raw)}")
    else:
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
            print(f"❌ safe_parse_json: 未找到JSON结构")
            return None
        raw = text[first_brace:last_brace + 1]
        print(f"📋 safe_parse_json: 提取到最外层JSON，长度: {len(raw)}")
    raw = re.sub(r'[\x00-\x1F\x7F]', '', raw.strip())
    print(f"📋 safe_parse_json: 清洗后长度: {len(raw)}")
    try:
        result = json.loads(raw)
        print(f"✅ safe_parse_json: JSON解析成功")
        return result
    except json.JSONDecodeError as e:
        print(f"⚠️ safe_parse_json: 首次解析失败 - {str(e)}")
        fix_raw = re.sub(r',\s*([}\]])', r'\1', raw)
        try:
            result = json.loads(fix_raw)
            print(f"✅ safe_parse_json: 修复后解析成功")
            return result
        except json.JSONDecodeError as e2:
            print(f"❌ safe_parse_json: 修复后仍失败 - {str(e2)}")
            print(f"❌ safe_parse_json: 最后500字符: {raw[-500:]}")
            return None

class PPTOutlineAgent:
    def __init__(self):
        self.llm = self._create_default_llm()
        self.base_prompt = """
严格规则：只输出纯JSON，不能加任何注释、说明、前言后语！
输出固定结构：{"title":"PPT总标题","pages":[]}
页面类型仅四种：cover/content/code/summary
【cover封面页】
type:"cover",title,subtitle(英文副标题),sections:[3个{"title":"","content":""}],key_points:[],detail_content:[]
【content内容页】
type:"content",title,key_points[3项],detail_content[3项]一一对应,layout(必填，从以下10种中选1个)
【code代码页】
type:"code",title,code_snippet(Java代码，单引号，10行以内)
【summary总结页】
type:"summary",title,key_points[3],detail_content[3]
页码要求：1封面 + 10~14内容 +3~5代码 +1总结，总15~20页

layout布局选择规则（每页content必须选1个，相邻页面尽量不重复）：
- "right_content"：左侧色条+右侧内容，适合要点3个、中等篇幅
- "top_banner"：顶部色栏+全宽内容，适合要点2-3个、简洁展示
- "center_focus"：居中大卡片，适合要点3个、重点突出
- "grid_cards"：多列卡片网格，适合要点2-3个、并列展示
- "timeline"：纵向时间线步骤，适合要点4个以上、流程/步骤类内容
- "comparison"：左右对比分栏，适合优缺点/对比类内容
- "big_number"：大数字突出，适合数据展示、3个核心指标
- "icon_row"：横向图标行，适合3-4个并列特性展示
- "quote_focus"：金句聚焦，适合核心观点、名言警句
- "list_check"：清单勾选，适合要点罗列、功能列表

PPT主题：
"""

    def _create_default_llm(self):
        from utils.llm_config import get_chat_openai
        return get_chat_openai(
            model="qwen3.7-max",
            temperature=0.2,
            max_tokens=16384,
            api_key="sk-b524efccda47492d92168ed3470593a8",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_body={"enable_thinking": False}
        )

    async def generate_async(self, topic: str, style_name: str, knowledge_list: list = None) -> Optional[Dict]:
        try:
            if knowledge_list is None:
                knowledge_list = []
            fix_style = style_name
            if fix_style == "dark_blue":
                fix_style = "dark_tech"
            prompt = self.base_prompt + f"{topic}\n版式风格：{fix_style}\n核心知识点列表：{str(knowledge_list)}"
            print(f"📝 发送给LLM的prompt长度：{len(prompt)}")
            resp = await self.llm.ainvoke(prompt)
            content = resp.content
            print(f"📤 LLM返回内容长度：{len(content) if content else 0}")
            if not content:
                print(f"❌ LLM返回内容为空")
                return None
            print(f"📋 LLM返回内容前200字符：{content[:200]}")
            print(f"📋 LLM返回内容后200字符：{content[-200:]}")
            res = safe_parse_json(content)
            if res and "title" in res and "pages" in res:
                print(f"✅大纲生成成功，总页数：{len(res['pages'])}")
            else:
                print(f"⚠️ 大模型返回原文：\n{content}")
            return res
        except Exception as e:
            print(f"❌ 大纲生成异常：{type(e).__name__} - {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def generate(self, topic: str, style_name: str, knowledge_list: list) -> Optional[Dict]:
        try:
            fix_style = style_name
            if fix_style == "dark_blue":
                fix_style = "dark_tech"
            prompt = self.base_prompt + f"{topic}\n版式风格：{fix_style}\n核心知识点列表：{str(knowledge_list)}"
            print(f"📝 发送给LLM的prompt长度：{len(prompt)}")
            resp = self.llm.invoke(prompt)
            content = resp.content
            print(f"📤 LLM返回内容长度：{len(content) if content else 0}")
            if not content:
                print(f"❌ LLM返回内容为空")
                return None
            print(f"📋 LLM返回内容前200字符：{content[:200]}")
            print(f"📋 LLM返回内容后200字符：{content[-200:]}")
            res = safe_parse_json(content)
            if res and "title" in res and "pages" in res:
                print(f"✅大纲生成成功，总页数：{len(res['pages'])}")
            else:
                print(f"⚠️ 大模型返回原文：\n{content}")
            return res
        except Exception as e:
            print(f"❌ 大纲生成异常：{type(e).__name__} - {str(e)}")
            import traceback
            traceback.print_exc()
            return None

# 测试入口
if __name__ == '__main__':
    async def main():
        from ReqParseAgent import ReqParseAgent
        req_agent = ReqParseAgent()
        info = await req_agent.run("讲解Java接口，深色科技")
        if info:
            outline_agent = PPTOutlineAgent()
            outline_data = await outline_agent.generate(info["topic"], info["style_name"], info["knowledge_list"])
            print(json.dumps(outline_data, ensure_ascii=False, indent=2))
    asyncio.run(main())
