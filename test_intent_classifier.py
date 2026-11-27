"""
意图分类器测试脚本

交互模式（默认）:
    python test_intent_classifier.py          # 直接进入交互模式，输入句子实时判断意图
    python test_intent_classifier.py -b       # 运行预定义的批量测试用例
    python test_intent_classifier.py -i       # 旧版交互模式（保留兼容）
"""

import os, sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# ★★★ 设置控制台编码，避免中文/emoji 报错 ★★★
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def load_classifier():
    """加载完整的 IntentClassifier（含 MLP + 拼音匹配）"""
    from utils.intent_classifier import IntentClassifier
    clf = IntentClassifier()
    clf._load_model()
    return clf


def test_group(clf, cases: list, group_name: str):
    """运行一组测试用例"""
    total = len(cases)
    passed = 0
    warned = 0
    failed = 0

    print(f"\n{'=' * 60}")
    print(f"  {group_name}（共 {total} 条）")
    print(f"{'=' * 60}")

    for i, case in enumerate(cases, 1):
        text = case[0]
        expected = case[1]
        note = case[2] if len(case) > 2 else ""

        intent, conf = clf.classify(text)
        correct = intent == expected

        if correct and conf >= 0.5:
            status = "OK"
            passed += 1
        elif correct and conf < 0.5:
            status = "WARN"
            warned += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"  {status} expect={expected:<16} got={intent:<16} conf={conf:.2%}  | {text[:36]:36s}  {note}")

    print(f"\n  结果: OK={passed}  WARN={warned}  FAIL={failed}  |  通过率: {passed/total:.0%}")
    return passed, warned, failed


def detailed_classify(clf, text: str):
    """详细展示分类过程"""
    from utils.intent_classifier import INTENT_EXAMPLES

    print(f"\n  ┌─ {'=' * 50}")
    print(f"  │  输入: {text}")

    # 1. 错别字纠错
    fixed = clf._fix_common_typos(text)
    if fixed != text:
        print(f"  │  纠错: {text} → {fixed}")
    else:
        print(f"  │  纠错: 无需纠错")

    # 2. MLP 分类结果
    mlp_result = clf._classify_with_mlp(fixed) if hasattr(clf, '_classify_with_mlp') else None
    if mlp_result:
        print(f"  │  MLP:   {mlp_result[0]:<16} conf={mlp_result[1]:.2%}")

    # 3. 关键词回退结果
    kw_result = clf._keyword_fallback(fixed)
    print(f"  │  关键词: {kw_result[0]:<16} conf={kw_result[1]:.2%}")

    # 4. Query消歧检测
    from utils.intent_classifier import IntentClassifier as _IC
    query_patterns = _IC._QUERY_PATTERNS
    execute_patterns = _IC._EXECUTE_PATTERNS
    has_query = any(q in fixed for q in query_patterns)
    has_execute = any(e in fixed for e in execute_patterns)
    if has_query and not has_execute:
        print(f"  │  消歧: 检测到纯查询模式，将路由到 chat")

    # 5. 最终分类结果
    intent, conf = clf.classify(text)
    method = "embedding"
    if conf < 0.5:
        method = "keyword"
    if conf < 0.3:
        method = "chat_fallback"

    # 判断正误（只当有匹配的预期时才显示）
    known_intents = list(INTENT_EXAMPLES.keys())
    if intent in known_intents:
        label = f"意图: {intent}"
    else:
        label = f"意图: {intent}"

    status = "OK" if conf >= 0.5 else ("WARN" if conf >= 0.3 else "FAIL")
    print(f"  ├─ {'=' * 50}")
    print(f"  │  {status}  {label:<20} 置信度: {conf:.2%}  方法: {method}")
    print(f"  └─ {'=' * 50}\n")

    return intent, conf


def interactive_mode_v2(clf):
    """新版交互式测试——详细展示分类过程"""
    from utils.intent_classifier import INTENT_EXAMPLES

    print(f"\n{'=' * 60}")
    print(f"  意图分类 · 交互测试")
    print(f"  输入句子 → 实时判断意图（含分类过程详解）")
    print(f"{'=' * 60}")
    print(f"\n  可用意图 ({len(INTENT_EXAMPLES)} 个): {', '.join(sorted(INTENT_EXAMPLES.keys()))}")
    print(f"  命令: help=查看命令帮助  intents=查看意图示例  exit=退出\n")

    count = 0
    while True:
        try:
            raw = input("  >> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("exit", "quit"):
            break
        elif cmd in ("help", "?"):
            print(f"\n  命令:")
            print(f"    exit/quit  退出")
            print(f"    help/?     显示此帮助")
            print(f"    intents    列出所有意图及其例句数")
            print(f"    <任意句子>  直接输入句子进行意图分类\n")
            continue
        elif cmd == "intents":
            print(f"\n  意图列表（共 {len(INTENT_EXAMPLES)} 个）:")
            print(f"  {'='*50}")
            for name in sorted(INTENT_EXAMPLES.keys()):
                examples = INTENT_EXAMPLES[name]
                count_ex = len(examples)
                preview = examples[0][:40] if examples else ""
                print(f"  {name:<20} ({count_ex:3d}条)  e.g. {preview}")
            print()
            continue

        count += 1
        detailed_classify(clf, raw)

    print(f"  共测试 {count} 条\n")


def interactive_mode(clf):
    """旧版交互式测试（保留兼容）"""
    from utils.intent_classifier import INTENT_EXAMPLES

    print(f"\n{'=' * 60}")
    print(f"  交互式测试模式（旧版）")
    print(f"  输入句子，实时查看分类结果")
    print(f"  输入 'exit' 退出  |  输入 'v2' 切换到新版详细模式")
    print(f"{'=' * 60}")
    print(f"\n  可用意图: {', '.join(sorted(INTENT_EXAMPLES.keys()))}\n")

    count = 0
    while True:
        try:
            text = input("  >> 请输入: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            break
        if text.lower() == "v2":
            print("  切换到新版详细模式...")
            interactive_mode_v2(clf)
            return

        count += 1
        # 显示纠错后的文本
        fixed = clf._fix_common_typos(text)
        if fixed != text:
            print(f"     纠错前: {text}")
            print(f"     纠错后: {fixed}")

        intent, conf = clf.classify(text)
        if conf >= 0.5:
            status = "OK"
        elif conf >= 0.3:
            status = "WARN"
        else:
            status = "FAIL"
        print(f"     {status} intent={intent:<16} conf={conf:.2%}\n")

    print(f"  共测试 {count} 条\n")


# ============================================================================
# 测试用例（批量模式用）
# ============================================================================

# ── 错别字鲁棒性测试（核心测试）──
TEST_TYPOS = [
    # 视频相关错别字（时评→视频拼音混淆）
    ("我要看二叉树时评",            "video",       "shipping→shipin"),
    ("二叉树的时评教学",            "video",       "时评教学→视频教学"),
    ("二叉树时评",                  "video",       "单纯时评→视频"),
    ("看一下冒泡排序时评",          "video",       "排序时评→排序视频"),
    ("关于二叉树的世平",            "video",       "世平→视频"),
    ("帮我找一些关于二叉树的世平",  "video",       "完整句世平→视频"),
    # 学习计划相关错别字
    ("帮我制定一个学习激化",        "study_plan",  "激化→计划"),
    ("帮我指定学习计画",            "study_plan",  "指定→制定, 计画→计划"),
    ("帮我指定一个学习几乎",        "study_plan",  "指定/几乎→制定/计划"),
    ("学习路线计画",                "study_plan",  "计画→计划"),
    ("关于二叉树的学习激化",        "study_plan",  "激化→计划"),
    # 编程练习
    ("帮我写一个拍序算法",          "practice",    "拍序→排序"),
    ("做链表反转的边程练习",        "practice",    "边程→编程"),
    ("练习一下连习",                "practice",    "连习→练习"),
    # 其他
    ("帮我生呈PPT",                 "ppt",         "生呈→生成"),
    ("帮我检茶代码错误",            "judge_code",  "检茶→检查"),
]

# ── 正常意图测试（确保正常输入不受影响）──
TEST_NORMAL = [
    ("帮我写一个快速排序算法",      "practice"),
    ("练习链表操作",                "practice"),
    ("出一道循环结构的选择题",      "question_gen"),
    ("生成一套二叉树的题目",        "question_gen"),
    ("帮我检查代码错误",            "judge_code"),
    ("帮我debug一下",               "judge_code"),
    ("帮我整理知识点笔记",          "doc_gen"),
    ("帮我总结二叉树",              "doc_gen"),
    ("推荐Python的拓展阅读",        "extension"),
    ("有什么深度学习资料",          "extension"),
    ("找B站的排序视频",             "video"),
    ("推荐二叉树的视频教程",        "video"),
    ("帮我生成思维导图",            "mindmap"),
    ("画二叉树的脑图",              "mindmap"),
    ("做链表动画",                  "animation"),
    ("生成排序的HTML动画",          "animation"),
    ("帮我制定学习计划",            "study_plan"),
    ("3个月学完Python",             "study_plan"),
    ("生成PPT",                     "ppt"),
    ("帮我做一个二叉树的PPT",       "ppt"),
    ("我要注册",                    "register"),
    ("新用户注册",                  "register"),
    ("修改我的名字",                "profile_modify"),
    ("更新个人信息",                "profile_modify"),
    ("帮我提炼大纲",                "refine_ppt"),
    ("润色这个PPT",                 "refine_ppt"),
    ("学不会怎么办",                "teacher_advice"),
    ("怎么学好算法",                "teacher_advice"),
    ("今天天气怎么样",              "chat"),
    ("你好",                        "chat"),
]

# ── 边界情况测试 ──
TEST_EDGE = [
    ("帮我代码",                    "chat",        "太短无关键词"),
    ("计划",                        "chat",        "单个词"),
    ("二叉树的视频",                "video",       "精简表达"),
    ("帮我生成一个关于排序的PPT顺便出几道题", "super", "混合意图"),
]


def run_batch_tests(clf):
    """运行预定义的批量测试"""
    print("\n[2/2] 开始测试...")
    all_p, all_w, all_f = 0, 0, 0
    all_total = 0

    # 错别字测试
    p, w, f = test_group(clf, TEST_TYPOS, "1. 错别字鲁棒性测试")
    all_p += p; all_w += w; all_f += f; all_total += len(TEST_TYPOS)

    # 正常意图测试
    p, w, f = test_group(clf, TEST_NORMAL, "2. 正常意图测试")
    all_p += p; all_w += w; all_f += f; all_total += len(TEST_NORMAL)

    # 边界情况测试
    p, w, f = test_group(clf, TEST_EDGE, "3. 边界情况测试")
    all_p += p; all_w += w; all_f += f; all_total += len(TEST_EDGE)

    # 汇总
    if all_total > 0:
        print(f"\n{'=' * 60}")
        print(f"  测试汇总")
        print(f"{'=' * 60}")
        print(f"  总计: {all_total} 条")
        print(f"  OK:   {all_p} ({all_p/all_total:.0%})")
        print(f"  WARN: {all_w} ({all_w/all_total:.0%})")
        print(f"  FAIL: {all_f} ({all_f/all_total:.0%})")
        if all_f == 0:
            print(f"\n  全部通过！")
        else:
            print(f"\n  有 {all_f} 条需要检查")
    print()


def main():
    print("=" * 60)
    print("  意图分类器测试")
    print("=" * 60)

    print("\n正在加载模型...")
    clf = load_classifier()
    print("  模型加载完成\n")

    # 解析参数
    args = sys.argv[1:]
    if "-b" in args or "--batch" in args:
        run_batch_tests(clf)
    elif "-i" in args or "--interactive" in args:
        interactive_mode(clf)
    elif "-h" in args or "--help" in args:
        print("用法:")
        print("  python test_intent_classifier.py          交互模式（默认）")
        print("  python test_intent_classifier.py -b       批量测试模式")
        print("  python test_intent_classifier.py -i       旧版交互模式")
        print("  python test_intent_classifier.py -h       显示帮助")
    else:
        # 默认：新版交互模式
        interactive_mode_v2(clf)


if __name__ == "__main__":
    main()
