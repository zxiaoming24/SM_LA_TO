# -*- coding: utf-8 -*-
"""
LLM 批量生成意图例句脚本

使用 DeepSeek API 为每个意图生成多样化的训练例句，包括：
- 口语化表达（"整个计划呗"）
- 极简表达（"出题"、"PPT"）
- 间接表达（"这个算法我老搞混" → teacher_advice）
- 带学科名的变体（"帮我出几道二叉树的题"）
- 不同句式（疑问、祈使、陈述）

输出：utils/intent_examples_llm.py，可被 intent_classifier.py 合并

用法:
    python generate_intent_examples.py              # 全量生成（每个意图 ~50 条）
    python generate_intent_examples.py --intent practice  # 只生成指定意图
    python generate_intent_examples.py --count 100  # 每个意图生成 100 条
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, List

# 将项目根目录加入 sys.path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ==================== 各意图的生成 Prompt ====================
# 每个意图定义一组多样化的 prompt 模板，覆盖不同表达风格

INTENT_GENERATION_CONFIG = {
    "study_plan": {
        "description": "制定学习计划、学习路线、时间安排",
        "styles": [
            "简短口语化（如：帮我整个Python学习计划）",
            "正式请求（如：请为我制定一份系统的数据结构学习方案）",
            "带时间约束（如：3个月学会Go语言）",
            "极简表达（如：学习路线、计划）",
            "带学科名（如：帮我规划Rust的学习路径）",
            "间接表达（如：我该从哪开始学算法）",
            "带错别字（如：帮我指定一个学习计画）",
        ],
    },
    "practice": {
        "description": "编程练习、写代码、实现算法",
        "styles": [
            "简短口语化（如：来道链表题）",
            "正式请求（如：请给我一道关于动态规划的编程练习）",
            "直接命令（如：写一个快排）",
            "极简表达（如：练习、写代码）",
            "带学科名（如：帮我写一个二叉树遍历的代码）",
            "带难度要求（如：来个中等难度的递归题）",
        ],
    },
    "judge_code": {
        "description": "检查代码、调试、找bug",
        "styles": [
            "简短口语化（如：帮我看看这段代码哪错了）",
            "正式请求（如：请帮我调试这个排序算法的实现）",
            "报错描述（如：代码跑出来WA了帮我看看）",
            "极简表达（如：debug、代码报错）",
            "带学科名（如：我的二叉树代码TLE了）",
            "间接表达（如：这个程序跑出来的结果不对啊）",
        ],
    },
    "question_gen": {
        "description": "生成题目、出题、刷题",
        "styles": [
            "简短口语化（如：出几道选择题）",
            "正式请求（如：请生成10道关于链表操作的判断题）",
            "直接命令（如：出题）",
            "极简表达（如：题目、刷题）",
            "带学科名（如：给我出5道二叉树相关的题目）",
            "带题型要求（如：来几道填空题考考我）",
        ],
    },
    "doc_gen": {
        "description": "生成文档、笔记、总结",
        "styles": [
            "简短口语化（如：帮我写个笔记）",
            "正式请求（如：请为我生成一份数据结构的知识总结文档）",
            "直接命令（如：写总结）",
            "极简表达（如：文档、笔记）",
            "带学科名（如：帮我整理二叉树的知识点笔记）",
            "间接表达（如：这个章节的内容帮我归纳一下）",
        ],
    },
    "extension": {
        "description": "拓展学习、延伸阅读、进阶资料",
        "styles": [
            "简短口语化（如：推荐点进阶资料）",
            "正式请求（如：请推荐一些关于深度学习的延伸阅读材料）",
            "直接命令（如：拓展）",
            "极简表达（如：进阶、深入）",
            "带学科名（如：有没有Python的高级教程推荐）",
            "间接表达（如：学完基础后该看什么）",
        ],
    },
    "video": {
        "description": "视频教程、B站、在线课程",
        "styles": [
            "简短口语化（如：找个视频看看）",
            "正式请求（如：请推荐一些关于排序算法的教学视频）",
            "直接命令（如：看视频）",
            "极简表达（如：视频、b站）",
            "带学科名（如：有没有二叉树遍历的B站视频）",
            "间接表达（如：有没有老师讲这个的网课）",
        ],
    },
    "mindmap": {
        "description": "思维导图、知识框架、脑图",
        "styles": [
            "简短口语化（如：画个脑图）",
            "正式请求（如：请为我生成一份数据结构的知识点的思维导图）",
            "直接命令（如：思维导图）",
            "极简表达（如：导图、脑图）",
            "带学科名（如：帮我画一个二叉树的思维导图）",
            "间接表达（如：帮我把知识点梳理成框架图）",
        ],
    },
    "animation": {
        "description": "动画演示、HTML动画、动态可视化",
        "styles": [
            "简短口语化（如：做个动画看看）",
            "正式请求（如：请生成一个展示冒泡排序过程的HTML动画）",
            "直接命令（如：动画演示）",
            "极简表达（如：动画、可视化）",
            "带学科名（如：帮我做一个链表插入的动画）",
            "间接表达（如：能不能动态展示一下这个过程）",
        ],
    },
    "ppt": {
        "description": "PPT、幻灯片、课件制作",
        "styles": [
            "简短口语化（如：做个PPT）",
            "正式请求（如：请帮我制作一份关于二叉搜索树的演示文稿）",
            "直接命令（如：生成PPT）",
            "极简表达（如：PPT、幻灯片）",
            "带学科名（如：做一个排序算法的课件）",
            "间接表达（如：帮我准备课堂演示用的材料）",
        ],
    },
    "register": {
        "description": "新用户注册、登记信息",
        "styles": [
            "简短口语化（如：我想注册一下）",
            "正式请求（如：我是新用户，请帮我注册账号）",
            "直接命令（如：注册）",
            "极简表达（如：新用户、注册）",
            "自我介绍式（如：我是新来的同学，怎么开始）",
            "间接表达（如：第一次用这个系统怎么弄）",
        ],
    },
    "profile_modify": {
        "description": "修改个人信息、更新资料",
        "styles": [
            "简短口语化（如：帮我改一下名字）",
            "正式请求（如：请帮我更新我的专业信息）",
            "直接命令（如：修改资料）",
            "极简表达（如：改信息、更新）",
            "具体修改（如：我想把年级改成大三）",
            "间接表达（如：我之前填的信息不对想改一下）",
        ],
    },
    "refine_ppt": {
        "description": "PPT大纲提炼、内容润色、精简",
        "styles": [
            "简短口语化（如：帮我提炼一下大纲）",
            "正式请求（如：请帮我润色这份PPT的内容）",
            "直接命令（如：精简）",
            "极简表达（如：大纲、润色）",
            "具体修改（如：这个PPT太长了帮我精简一下）",
            "间接表达（如：内容太多了能不能浓缩一下）",
        ],
    },
    "teacher_advice": {
        "description": "学习建议、方法指导、困惑咨询",
        "styles": [
            "简短口语化（如：学不会咋办）",
            "正式请求（如：请问有什么好的方法可以帮我理解递归）",
            "困惑表达（如：这个知识点我老是搞混怎么办）",
            "极简表达（如：怎么学、建议）",
            "间接表达（如：感觉学了就忘不知道该怎么提高）",
            "情感表达（如：学算法真的好难我快放弃了）",
        ],
    },
    "chat": {
        "description": "闲聊、问候、查询个人信息、系统对话",
        "styles": [
            "问候（如：早上好、你好呀）",
            "感谢/告别（如：谢谢、再见、拜拜）",
            "闲聊（如：今天天气不错、你吃了吗）",
            "查询个人信息（如：我的学习进度怎么样）",
            "系统交互（如：你是谁、你叫什么）",
            "简短回应（如：好的、明白了、收到）",
            "无特定意图的随意对话（如：哈哈哈、不错）",
        ],
    },
    "unrecognized": {
        "description": "无效输入、无意义内容、与教育无关的请求",
        "styles": [
            "键盘乱按（如：asdfghjkl）",
            "单字/语气词（如：嗯、啊、哦）",
            "纯数字（如：12345、666666）",
            "与教育完全无关的请求（如：帮我点外卖、查天气）",
            "无意义的重复（如：哈哈哈哈哈、啊啊啊啊）",
            "系统探测/攻击尝试（如：SELECT * FROM users）",
            "过于模糊无法判断（如：那个、这个、就是）",
        ],
    },
}


def generate_examples_for_intent(
    intent: str,
    config: dict,
    count: int,
    existing_count: int,
) -> List[str]:
    """为一个意图生成多样化例句"""
    from openai import OpenAI

    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")

    if not api_key:
        print("  ❌ LLM_API_KEY 未设置，请在 .env 中配置")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    styles_text = "\n".join([f"  - {s}" for s in config["styles"]])

    prompt = f"""你是一个数据生成专家。请为以下意图类别生成 {count} 条多样化的中文用户输入例句。

意图类别: {intent}
含义: {config["description"]}
当前已有例句数: {existing_count}

要求：
1. 必须覆盖以下所有表达风格，每种风格至少生成 {max(3, count // len(config["styles"]))} 条：
{styles_text}

2. 例句应该：
   - 模拟真实用户的自然表达
   - 长度从 2 字到 30 字不等
   - 包含不同句式（疑问句、祈使句、陈述句、省略句）
   - 包含不同学科/主题的变体（算法、数据结构、编程语言、操作系统等）
   - 部分例句可以包含常见的口语化表达和轻微错别字

3. 输出格式：每行一条例句，不要编号，不要其他任何内容，不要解释。
4. 确保 {count} 条例句互不重复。

请直接输出 {count} 条例句："""

    print(f"  ⏳ 正在为 {intent} 生成 {count} 条例句...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.95,  # 高温保证多样性
            max_tokens=4000,
        )
        result_text = response.choices[0].message.content.strip()
        # 按行分割，过滤空行
        examples = [line.strip() for line in result_text.split("\n") if line.strip()]
        # 移除可能的编号前缀（如 "1. " 或 "1) "）
        import re
        cleaned = []
        for ex in examples:
            ex = re.sub(r"^\d+[\.\)]\s*", "", ex)
            ex = re.sub(r"^[-•]\s*", "", ex)
            if ex:
                cleaned.append(ex)
        print(f"  ✅ {intent}: 生成 {len(cleaned)} 条")
        return cleaned
    except Exception as e:
        print(f"  ❌ {intent}: 生成失败 - {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="LLM 批量生成意图例句")
    parser.add_argument("--intent", type=str, help="只生成指定意图的例句")
    parser.add_argument("--count", type=int, default=50, help="每个意图生成的例句数（默认50）")
    parser.add_argument("--output", type=str, default="utils/intent_examples_llm.py",
                        help="输出文件路径（默认 utils/intent_examples_llm.py）")
    args = parser.parse_args()

    print("=" * 60)
    print("  LLM 批量生成意图例句")
    print("=" * 60)

    # 加载现有例句数量
    from utils.intent_classifier import INTENT_EXAMPLES

    intents_to_generate = (
        {args.intent: INTENT_GENERATION_CONFIG[args.intent]}
        if args.intent
        else INTENT_GENERATION_CONFIG
    )

    if args.intent and args.intent not in INTENT_GENERATION_CONFIG:
        print(f"  ❌ 未知意图: {args.intent}")
        print(f"  可用意图: {', '.join(INTENT_GENERATION_CONFIG.keys())}")
        sys.exit(1)

    all_examples: Dict[str, List[str]] = {}
    total_generated = 0

    for intent, config in intents_to_generate.items():
        existing_count = len(INTENT_EXAMPLES.get(intent, []))
        examples = generate_examples_for_intent(intent, config, args.count, existing_count)
        if examples:
            all_examples[intent] = examples
            total_generated += len(examples)
        # 避免 API 限流
        time.sleep(0.5)

    # 写入输出文件
    output_path = os.path.join(_PROJECT_ROOT, args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write("# 由 generate_intent_examples.py 自动生成的 LLM 扩充例句\n")
        f.write("# 用于增强 MLP 训练数据的多样性，提高意图分类覆盖率\n\n")
        f.write("INTENT_EXAMPLES_LLM = {\n")
        for intent, examples in all_examples.items():
            f.write(f'    "{intent}": [\n')
            for ex in examples:
                # 转义引号
                ex_escaped = ex.replace("\\", "\\\\").replace('"', '\\"')
                f.write(f'        "{ex_escaped}",\n')
            f.write("    ],\n")
        f.write("}\n")

    print(f"\n{'=' * 60}")
    print(f"  生成完成!")
    print(f"  总计: {len(all_examples)} 个意图, {total_generated} 条例句")
    print(f"  输出: {output_path}")
    print(f"{'=' * 60}")
    print(f"\n下一步: 在 intent_classifier.py 中合并此文件:")
    print(f"  try:")
    print(f"      from .intent_examples_llm import INTENT_EXAMPLES_LLM")
    print(f"      for intent, examples in INTENT_EXAMPLES_LLM.items():")
    print(f"          if intent in INTENT_EXAMPLES:")
    print(f"              existing = set(INTENT_EXAMPLES[intent])")
    print(f"              new = [s for s in examples if s not in existing]")
    print(f"              INTENT_EXAMPLES[intent].extend(new)")
    print(f"  except (ImportError, FileNotFoundError):")
    print(f"      pass")


if __name__ == "__main__":
    main()
