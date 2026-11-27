"""
槽位意图模板数据（独立实验，不修改原 INTENT_EXAMPLES）

核心思想：
    - 不存储"生成PPT""制作PPT""合成PPT"等同义表达
    - 只存储带槽位的原型 "<CREATE>PPT"
    - 训练/推理时把 <CREATE> 随机/固定替换为真实动作词后再编码
    - 动作词差异被抹平，分类器聚焦在核心名词上

关键设计：
    - 区分 <CREATE>（执行类动作，需泛化）和保留词（如"是什么""查看我的"等 Query 信号，不动）
    - 所有 CREATE_SLOT_VARIANTS 都只表示"创建"语义，不引入歧义
"""

# ============================================================================
# 槽位定义
# ============================================================================

# <CREATE> 槽位：执行类动作词，语义等价，泛化时随机替换
CREATE_SLOT_VARIANTS = [
    "生成", "制作", "合成", "搞一个", "整一个", "弄个", "做一",
    "做个", "来个", "来一份", "建一个", "建个", "出一份",
    "输出", "产出", "构造", "搭建", "形成",
]

# <PLAN> 槽位：规划类动作词（study_plan 专用）
PLAN_SLOT_VARIANTS = [
    "制定", "规划", "安排", "设计", "帮我做", "生成",
    "做个", "规划个", "安排个", "设计一份",
]

# <FIX> 槽位：修改类动作词（refine_ppt / profile_modify 共用）
FIX_SLOT_VARIANTS = [
    "修改", "更新", "完善", "调整", "优化", "润色", "精简",
    "改一下", "调整一下", "改一改",
]

# <ASK> 槽位：求教类动作词（teacher_advice 专用）
ASK_SLOT_VARIANTS = [
    "给点", "提供", "教教", "说说", "讲讲", "给我",
    "帮帮", "指点", "分享",
]

# 保留词（不进槽位归一化）：
#   - "是什么""有哪些""查看我的""我的进度"等 Query 强信号
#   - chat 意图的寒暄词
#   - register 意图的"注册""新用户"等专有词
#   这些词必须保留原样，供 _disambiguate_query 使用

SLOT_VARIANTS = {
    "<CREATE>": CREATE_SLOT_VARIANTS,
    "<PLAN>":   PLAN_SLOT_VARIANTS,
    "<FIX>":    FIX_SLOT_VARIANTS,
    "<ASK>":    ASK_SLOT_VARIANTS,
}


# ============================================================================
# 意图模板（带槽位的原型句子）
# ============================================================================

SLOT_INTENT_EXAMPLES = {
    # ── study_plan ──
    "study_plan": [
        "<PLAN>Rust的学习计划",
        "<PLAN>操作系统的学习方案",
        "<PLAN>排序的系统学习计划",
        "<PLAN>二叉树的学习阶段",
        "<PLAN>算法的学习路径",
        "<PLAN>数据结构的学习方案",
        "<PLAN>链表的学习路线",
        "<PLAN>算法的学习进度",
        "<PLAN>前端的学习阶段",
        "<PLAN>网络协议的学习计划",
        "<PLAN>Go的学习路线",
        "<PLAN>SQL的学习方案",
        "<PLAN>深度学习的学习阶段",
        "<PLAN>排序的学习指南",
        "<PLAN>栈的学习路线",
        "学习阶段的安排",
        "学习路线规划",
        "3个月学完Python",
        "多久能学会二叉树",
        "从零开始学算法",
        "系统学习路线",
        "新手入门计划",
    ],

    # ── ppt ──
    "ppt": [
        "<CREATE>PPT",
        "<CREATE>二叉树的PPT",
        "<CREATE>排序的PPT",
        "<CREATE>链表的PPT",
        "<CREATE>栈的PPT",
        "<CREATE>队列的PPT",
        "<CREATE>算法的PPT",
        "<CREATE>数据结构的PPT",
        "<CREATE>Rust的PPT",
        "<CREATE>Python的PPT",
        "<CREATE>答辩PPT",
        "<CREATE>汇报PPT",
        "<CREATE>课堂PPT",
        "<CREATE>幻灯片",
        "<CREATE>课件",
        "<CREATE>演示文稿",
        "<CREATE>二叉树的课件",
        "<CREATE>排序的幻灯片",
    ],

    # ── mindmap ──
    "mindmap": [
        "<CREATE>思维导图",
        "<CREATE>Go的思维导图",
        "<CREATE>二叉树的脑图",
        "<CREATE>排序的导图",
        "<CREATE>链表的思维导图",
        "<CREATE>数据结构的知识框架",
        "<CREATE>算法的导图",
        "<CREATE>栈的知识图谱",
        "<CREATE>队列的概念图",
        "<CREATE>Rust的思维图",
        "<CREATE>知识树",
        "<CREATE>框架图",
        "<CREATE>知识架构",
        "<CREATE>脉络图",
    ],

    # ── animation ──
    "animation": [
        "<CREATE>排序动画",
        "<CREATE>链表动画",
        "<CREATE>二叉树动画",
        "<CREATE>指针动画",
        "<CREATE>算法动画",
        "<CREATE>栈的动画",
        "<CREATE>队列的动画",
        "<CREATE>HTML动画",
        "<CREATE>动态演示",
        "<CREATE>可视化演示",
        "<CREATE>动态过程",
        "<CREATE>流程动画",
        "<CREATE>步骤动画",
        "<CREATE>网页动画",
    ],

    # ── doc_gen ──
    "doc_gen": [
        "<CREATE>数据结构的报告",
        "<CREATE>二叉树的笔记",
        "<CREATE>排序的总结",
        "<CREATE>链表的文档",
        "<CREATE>算法的学习笔记",
        "<CREATE>知识总结",
        "<CREATE>课堂笔记",
        "<CREATE>复习笔记",
        "<CREATE>知识点整理",
        "<CREATE>复习资料",
        "<CREATE>报告",
        "<CREATE>word文档",
        "<CREATE>技术文档",
        "<CREATE>知识梳理文档",
    ],

    # ── question_gen ──
    "question_gen": [
        "<CREATE>选择题",
        "<CREATE>判断题",
        "<CREATE>二叉树的题目",
        "<CREATE>排序的题目",
        "<CREATE>链表的题目",
        "<CREATE>算法题",
        "<CREATE>简答题",
        "<CREATE>填空题",
        "<CREATE>论述题",
        "<CREATE>面试题",
        "<CREATE>笔试题",
        "<CREATE>考题",
        "<CREATE>几道题",
        "<CREATE>一套题",
        "<CREATE>测验题",
        "<CREATE>概念题",
    ],

    # ── practice ──
    "practice": [
        "<CREATE>一个排序算法",
        "<CREATE>链表反转的程序",
        "<CREATE>二叉树的代码",
        "<CREATE>快速排序",
        "<CREATE>归并排序",
        "<CREATE>一个数据库相关的程序",
        "<CREATE>一个函数",
        "<CREATE>栈的实现",
        "<CREATE>队列的实现",
        "<CREATE>算法",
        "<CREATE>代码练习",
        "<CREATE>编程题",
        "<CREATE>实操题",
        "<CREATE>算法题",
    ],

    # ── judge_code ──
    "judge_code": [
        "检查代码错误",
        "debug一下",
        "帮我调试",
        "代码运行不对",
        "报错了",
        "编译失败",
        "找bug",
        "代码有问题",
        "运行报错",
        "帮我看看代码",
        "段错误",
        "为什么报错",
        "修复代码",
        "排查错误",
        "代码崩了",
        "超时了",
        "结果不对",
    ],

    # ── extension ──
    "extension": [
        "推荐Python的拓展阅读",
        "深度学习资料",
        "C++的高级教程",
        "二叉树的进阶资料",
        "算法的原理深入",
        "源码解析",
        "面试准备资料",
        "课外补充",
        "参考文献",
        "技术博客推荐",
        "开源项目推荐",
        "经典书籍",
        "进阶学习路径",
        "底层原理",
    ],

    # ── video ──
    "video": [
        "找二叉树的视频",
        "排序视频教程",
        "链表视频讲解",
        "算法视频教学",
        "B站排序视频",
        "二叉树视频课程",
        "栈的视频资源",
        "队列视频推荐",
        "数据结构网课",
        "算法公开课",
        "二叉树录播",
        "指针视频",
        "链表动画视频",
        "排序演示视频",
    ],

    # ── refine_ppt ──
    "refine_ppt": [
        "<FIX>PPT大纲",
        "<FIX>PPT内容",
        "<FIX>PPT结构",
        "<FIX>PPT排版",
        "<FIX>PPT布局",
        "提炼PPT要点",
        "精简PPT",
        "润色这个PPT",
        "优化PPT",
        "整理PPT大纲",
        "完善PPT逻辑",
        "PPT提炼",
        "PPT摘要",
        "PPT层次梳理",
    ],

    # ── profile_modify ──
    "profile_modify": [
        "<FIX>我的名字",
        "<FIX>我的专业",
        "<FIX>我的年级",
        "<FIX>个人信息",
        "<FIX>我的资料",
        "修改我的信息",
        "更新我的资料",
        "完善个人信息",
        "补充信息",
        "改一下名字",
        "换专业",
        "改班级",
        "更新手机",
        "改密码",
    ],

    # ── register ──
    "register": [
        "我要注册",
        "新用户注册",
        "我是新用户",
        "注册账号",
        "创建账户",
        "新同学",
        "新人报道",
        "新来的",
        "第一次用",
        "开个号",
        "注册一下",
        "我想注册",
        "怎么注册",
    ],

    # ── teacher_advice ──
    "teacher_advice": [
        "<ASK>学二叉树的建议",
        "<ASK>Python的学习方法",
        "<ASK>C++的学习技巧",
        "<ASK>SQL的经验",
        "怎么学好算法",
        "学不会怎么办",
        "感觉好难",
        "学习瓶颈",
        "怎么入门二叉树",
        "怎么提升Python水平",
        "JavaScript怎么学效率高",
        "学Rust有什么好方法",
        "学习建议",
        "怎么克服算法的困难",
    ],

    # ── chat（不槽位化，保留 Query 信号）──
    "chat": [
        "你好", "您好", "嗨", "在吗", "谢谢", "再见",
        "天气怎么样", "讲个笑话", "你是谁",
        "早上好", "下午好", "晚上好",
        "好的", "OK", "明白了", "知道了",
        "PPT是什么",
        "什么是二叉树",
        "有哪些算法",
        "查看我的进度",
        "我的成绩怎么样",
        "我的名字是什么",
        "你知道我是谁",
        "我的学习情况",
        "记得我吗",
    ],

    # ── unrecognized ──
    "unrecognized": [
        "asdf", "qwerty", "12345",
        "嗯", "啊", "哦", "额",
        "今天星期几", "现在几点",
        "帮我订外卖", "打车", "发红包",
        "hello world", "foo bar",
        "111", "222", "999",
        "随便", "都行", "无所谓",
    ],
}


# ============================================================================
# 槽位填充函数
# ============================================================================

import random
from typing import List


def fill_slots(text: str, rng: random.Random = None, strategy: str = "random") -> str:
    """
    把模板中的 <CREATE> <PLAN> <FIX> <ASK> 槽位替换为真实动作词。

    Args:
        text:     含槽位占位符的模板句子
        rng:      random.Random 实例（控制随机性，便于复现）
        strategy: "random" = 随机选一个变体；"first" = 固定取第一个（用于推理时确定性）

    Returns:
        填充后的真实句子
    """
    if rng is None:
        rng = random.Random(42)

    out = text
    for slot, variants in SLOT_VARIANTS.items():
        while slot in out:
            if strategy == "first":
                pick = variants[0]
            else:
                pick = rng.choice(variants)
            out = out.replace(slot, pick, 1)
    return out


def expand_templates(rng_seed: int = 42, repeats: int = 3) -> dict:
    """
    把每个模板展开为多个真实句子（用于训练集扩充）。

    Args:
        rng_seed: 随机种子
        repeats:  每个模板展开为多少条不同的真实句子

    Returns:
        { intent: [real_sentence, ...], ... }
    """
    rng = random.Random(rng_seed)
    expanded = {}
    for intent, templates in SLOT_INTENT_EXAMPLES.items():
        sentences = []
        for tmpl in templates:
            # 无槽位的模板直接加入
            if not any(slot in tmpl for slot in SLOT_VARIANTS):
                sentences.append(tmpl)
                continue

            # 有槽位的模板：重复 repeats 次，每次随机填充
            seen = set()
            for _ in range(repeats):
                filled = fill_slots(tmpl, rng=rng, strategy="random")
                if filled not in seen:
                    seen.add(filled)
                    sentences.append(filled)

            # 兜底：至少加一个 first 策略的，保证不为空
            if not seen:
                sentences.append(fill_slots(tmpl, strategy="first"))

        expanded[intent] = sentences
    return expanded


# ============================================================================
# 自检
# ============================================================================

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("  槽位意图模板 · 自检")
    print("=" * 60)

    # 1. 展示模板数
    total_templates = sum(len(v) for v in SLOT_INTENT_EXAMPLES.values())
    print(f"\n[1] 模板数: {len(SLOT_INTENT_EXAMPLES)} 个意图，共 {total_templates} 条模板")

    # 2. 展开示例
    print(f"\n[2] 展开示例（repeats=3，seed=42）:")
    expanded = expand_templates(rng_seed=42, repeats=3)
    for intent in ["ppt", "study_plan", "mindmap"]:
        print(f"\n  ── {intent} ──")
        print(f"     模板数: {len(SLOT_INTENT_EXAMPLES[intent])}")
        print(f"     展开后: {len(expanded[intent])} 条")
        for s in expanded[intent][:5]:
            print(f"       • {s}")

    total_expanded = sum(len(v) for v in expanded.values())
    print(f"\n  总计: {total_templates} 模板 → {total_expanded} 条训练样本")

    # 3. 槽位填充演示
    print(f"\n[3] 槽位填充演示:")
    demo_templates = [
        "<CREATE>PPT",
        "<PLAN>Rust的学习计划",
        "<FIX>PPT大纲",
        "<ASK>学二叉树的建议",
    ]
    rng = random.Random(0)
    for t in demo_templates:
        samples = [fill_slots(t, rng=rng, strategy="random") for _ in range(4)]
        print(f"  {t}")
        for s in samples:
            print(f"    → {s}")

    print(f"\n{'=' * 60}")
    print(f"  ✅ 自检完成")
    print(f"{'=' * 60}")
