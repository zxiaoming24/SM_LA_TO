"""
槽位意图分类器测试脚本（独立实验）

对比原 MLP 分类器 vs 槽位 MLP 分类器，在同批次测试用例上的表现差异。
重点关注：训练时**没见过**的动作词（如"整一个""弄个"）能否正确泛化。

用法:
    python test_intent_slot.py              # 默认批量测试
    python test_intent_slot.py -i           # 交互模式
    python test_intent_slot.py -b           # 强制批量模式

前置条件:
    1. 已运行 train_intent_classifier.py   → user_features/intent_mlp_model/
    2. 已运行 train_intent_slot.py          → user_features/intent_slot_model/
"""

import os, sys, pickle

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 模型路径
_ORIG_MODEL_DIR = os.path.join(_PROJECT_ROOT, "user_features", "intent_mlp_model")
_SLOT_MODEL_DIR = os.path.join(_PROJECT_ROOT, "user_features", "intent_slot_model")


# ============================================================================
# 分类器加载
# ============================================================================

def _load_bge_model():
    """加载 BGE 嵌入模型（与训练脚本同样的优先级策略）"""
    from sentence_transformers import SentenceTransformer

    _MODELSCOPE_CACHE = os.path.join(
        _PROJECT_ROOT, ".cache_models", "models", "BAAI--bge-base-zh-v1.5", "snapshots", "master"
    )

    # 1: ModelScope 已知缓存路径（项目实际下载位置）
    if os.path.exists(_MODELSCOPE_CACHE):
        try:
            return SentenceTransformer(_MODELSCOPE_CACHE, local_files_only=True)
        except Exception:
            pass

    # 2: HuggingFace 默认缓存
    try:
        return SentenceTransformer("BAAI/bge-base-zh-v1.5", local_files_only=True)
    except Exception:
        pass

    # 3: ModelScope 在线下载
    try:
        from modelscope import snapshot_download
        local_path = snapshot_download(
            "BAAI/bge-base-zh-v1.5",
            cache_dir=os.path.join(_PROJECT_ROOT, ".cache_models"),
        )
        return SentenceTransformer(local_path)
    except Exception as e:
        raise RuntimeError(f"无法加载 BGE 模型: {e}")


class OrigClassifier:
    """加载原版 MLP 模型（无槽位）"""
    def __init__(self):
        self.name = "原版MLP"
        self.model = None
        self.mlp = None
        self.label_encoder = None

    def load(self):
        print(f"  [{self.name}] 加载嵌入模型...")
        self.model = _load_bge_model()
        mlp_path = os.path.join(_ORIG_MODEL_DIR, "mlp.pkl")
        enc_path = os.path.join(_ORIG_MODEL_DIR, "label_encoder.pkl")
        if not os.path.exists(mlp_path):
            raise FileNotFoundError(f"原版模型不存在: {mlp_path}\n请先运行 train_intent_classifier.py")
        with open(mlp_path, "rb") as f:
            self.mlp = pickle.load(f)
        with open(enc_path, "rb") as f:
            self.label_encoder = pickle.load(f)
        print(f"  [{self.name}] ✅ 加载完成（{len(self.label_encoder.classes_)} 类）")

    def classify(self, text: str):
        import numpy as np
        vec = self.model.encode(text, normalize_embeddings=True).reshape(1, -1)
        probs = self.mlp.predict_proba(vec)[0]
        best_idx = int(np.argmax(probs))
        intent = str(self.label_encoder.inverse_transform([best_idx])[0])
        conf = float(probs[best_idx])
        return intent, conf


class SlotClassifier:
    """加载槽位 MLP 模型，推理时对输入做槽位归一化"""
    def __init__(self):
        self.name = "槽位MLP"
        self.model = None
        self.mlp = None
        self.label_encoder = None
        self.slot_variants = None
        self.fill_strategy = "first"

    def load(self):
        from slot_intent_examples import SLOT_VARIANTS

        print(f"  [{self.name}] 加载嵌入模型...")
        self.model = _load_bge_model()
        mlp_path = os.path.join(_SLOT_MODEL_DIR, "mlp.pkl")
        enc_path = os.path.join(_SLOT_MODEL_DIR, "label_encoder.pkl")
        if not os.path.exists(mlp_path):
            raise FileNotFoundError(f"槽位模型不存在: {mlp_path}\n请先运行 train_intent_slot.py")
        with open(mlp_path, "rb") as f:
            self.mlp = pickle.load(f)
        with open(enc_path, "rb") as f:
            self.label_encoder = pickle.load(f)
        self.slot_variants = SLOT_VARIANTS
        print(f"  [{self.name}] ✅ 加载完成（{len(self.label_encoder.classes_)} 类）")

    def _normalize_input(self, text: str) -> str:
        """
        推理时把用户输入中的真实动作词**逆向**替换为槽位占位符，
        再用 fill_slots(strategy='first') 重新填充为标准动作词。
        这样用户说"整一个PPT"会被归一化为训练时见过的"生成PPT"。
        """
        from slot_intent_examples import fill_slots
        import re

        # Step 1: 把所有已知动作词替换为 <CREATE>/<PLAN>/<FIX>/<ASK>
        normalized = text
        for slot, variants in self.slot_variants.items():
            for v in variants:
                # 长词优先（避免"搞一个"被"搞"截断），用占位符替代真实词
                normalized = normalized.replace(v, slot)

        # Step 2: 用 first 策略填回标准动作词（确定性）
        # 如果原文本里没有动作词，Step 1 不会产生槽位，Step 2 直接返回原文
        normalized = fill_slots(normalized, strategy=self.fill_strategy)

        return normalized

    def classify(self, text: str):
        import numpy as np
        normalized = self._normalize_input(text)
        vec = self.model.encode(normalized, normalize_embeddings=True).reshape(1, -1)
        probs = self.mlp.predict_proba(vec)[0]
        best_idx = int(np.argmax(probs))
        intent = str(self.label_encoder.inverse_transform([best_idx])[0])
        conf = float(probs[best_idx])
        return intent, conf


# ============================================================================
# 测试用例
# ============================================================================

# ── 泛化测试：训练时**没见过**这些动作词组合，检验能否泛化 ──
TEST_GENERALIZATION = [
    # (输入, 期望意图, 备注)
    # ppt 泛化（训练见过"生成PPT"，推理来了"整一个PPT"）
    ("生成PPT",                       "ppt",          "训练已见"),
    ("合成PPT",                       "ppt",          "训练已见"),
    ("搞一个PPT",                     "ppt",          "训练已见"),
    ("整一个PPT",                     "ppt",          "未见过"),
    ("弄个PPT",                       "ppt",          "未见过"),
    ("来一份PPT",                     "ppt",          "未见过"),
    ("做一个二叉树的PPT",             "ppt",          "未见过"),
    ("弄个排序的幻灯片",              "ppt",          "未见过"),
    ("整一个答辩PPT",                 "ppt",          "未见过"),

    # study_plan 泛化
    ("制定Rust的学习计划",            "study_plan",   "训练已见"),
    ("安排算法的学习进度",            "study_plan",   "训练已见"),
    ("规划二叉树的学习路径",          "study_plan",   "未见过"),
    ("设计数据结构的学习方案",        "study_plan",   "未见过"),
    ("帮我做Python的学习计划",        "study_plan",   "未见过"),

    # mindmap 泛化
    ("生成思维导图",                  "mindmap",      "训练已见"),
    ("制作Go的思维导图",              "mindmap",      "训练已见"),
    ("搞一个二叉树的脑图",            "mindmap",      "未见过"),
    ("整一个排序的导图",              "mindmap",      "未见过"),
    ("弄个链表的思维导图",            "mindmap",      "未见过"),

    # animation 泛化
    ("制作排序动画",                  "animation",    "训练已见"),
    ("搞一个链表动画",                "animation",    "未见过"),
    ("整一个二叉树动画",              "animation",    "未见过"),
    ("弄个指针动画",                  "animation",    "未见过"),

    # doc_gen 泛化
    ("生成二叉树的笔记",              "doc_gen",       "训练已见"),
    ("搞一个算法的学习笔记",          "doc_gen",       "未见过"),
    ("整一份数据结构的知识总结",      "doc_gen",       "未见过"),

    # question_gen 泛化
    ("生成选择题",                    "question_gen",  "训练已见"),
    ("搞几道二叉树的题目",            "question_gen",  "未见过"),
    ("整一套排序的题",                "question_gen",  "未见过"),

    # practice 泛化
    ("写一个快速排序算法",            "practice",     "训练已见"),
    ("搞一个链表反转的程序",          "practice",     "未见过"),
    ("整一个数据库相关的程序",        "practice",     "未见过"),
    ("弄个二叉树的代码",              "practice",     "未见过"),

    # refine_ppt 泛化
    ("修改PPT大纲",                   "refine_ppt",   "训练已见"),
    ("调整PPT排版",                   "refine_ppt",   "未见过"),
    ("优化PPT布局",                   "refine_ppt",   "未见过"),
    ("润色这个PPT",                   "refine_ppt",   "训练已见"),

    # teacher_advice 泛化
    ("给点学二叉树的建议",            "teacher_advice", "训练已见"),
    ("分享Python的学习方法",          "teacher_advice", "未见过"),
    ("指点一下C++的学习技巧",         "teacher_advice", "未见过"),

    # profile_modify 泛化
    ("更新我的名字",                  "profile_modify", "训练已见"),
    ("修改我的专业",                  "profile_modify", "训练已见"),
    ("完善个人信息",                  "profile_modify", "训练已见"),

    # chat（不槽位化，应正常工作）
    ("你好",                          "chat",          "训练已见"),
    ("PPT是什么",                     "chat",          "训练已见"),
    ("查看我的进度",                  "chat",          "训练已见"),
]

# ── 消歧保护测试：Query 信号不应被动作词归一化破坏 ──
TEST_DISAMBIGUATION = [
    ("PPT是什么",                     "chat",          "Query信号，不应判ppt"),
    ("有哪些算法",                    "chat",          "Query信号"),
    ("我的进度怎么样",                "chat",          "Query信号"),
    ("查看我的资料",                  "chat",          "Query信号"),
]


# ============================================================================
# 测试执行
# ============================================================================

def run_comparison(orig: OrigClassifier, slot: SlotClassifier, cases, group_name: str):
    """对比测试"""
    total = len(cases)
    print(f"\n{'=' * 70}")
    print(f"  {group_name}（共 {total} 条）")
    print(f"{'=' * 70}")
    print(f"  {'#':>3}  {'期望':<16}  {'原版MLP':<28}  {'槽位MLP':<28}  {'备注'}")
    print(f"  {'-'*3}  {'-'*16}  {'-'*28}  {'-'*28}  {'-'*20}")

    orig_pass = 0
    slot_pass = 0
    slot_better = 0  # 槽位正确但原版错误
    orig_better = 0  # 原版正确但槽位错误

    for i, case in enumerate(cases, 1):
        text = case[0]
        expected = case[1]
        note = case[2] if len(case) > 2 else ""

        orig_intent, orig_conf = orig.classify(text)
        slot_intent, slot_conf = slot.classify(text)

        orig_ok = orig_intent == expected
        slot_ok = slot_intent == expected

        if orig_ok: orig_pass += 1
        if slot_ok: slot_pass += 1
        if slot_ok and not orig_ok: slot_better += 1
        if orig_ok and not slot_ok: orig_better += 1

        orig_mark = "✅" if orig_ok else "❌"
        slot_mark = "✅" if slot_ok else "❌"

        print(f"  {i:>3}  {expected:<16}  {orig_mark} {orig_intent:<12} {orig_conf:.0%}  "
              f"{slot_mark} {slot_intent:<12} {slot_conf:.0%}  {note}")

    print(f"\n  结果汇总:")
    print(f"    原版MLP 通过: {orig_pass}/{total} ({orig_pass/total:.0%})")
    print(f"    槽位MLP 通过: {slot_pass}/{total} ({slot_pass/total:.0%})")
    print(f"    槽位更好（原版错/槽位对）: {slot_better}")
    print(f"    原版更好（槽位错/原版对）: {orig_better}")
    delta = slot_pass - orig_pass
    if delta > 0:
        print(f"    🎯 槽位净优势: +{delta} 条")
    elif delta < 0:
        print(f"    ⚠️ 槽位净劣势: {delta} 条")
    else:
        print(f"    ➖ 持平")
    return orig_pass, slot_pass, total


def interactive_mode(orig: OrigClassifier, slot: SlotClassifier):
    """交互式对比"""
    print(f"\n{'=' * 70}")
    print(f"  槽位分类器 · 交互对比测试")
    print(f"  输入句子 → 实时对比原版 vs 槽位")
    print(f"  命令: exit=退出  help=帮助")
    print(f"{'=' * 70}\n")

    count = 0
    while True:
        try:
            text = input("  >> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            break
        if text.lower() in ("help", "?"):
            print("  输入任意句子查看两个分类器的对比结果")
            continue

        count += 1
        orig_intent, orig_conf = orig.classify(text)
        slot_intent, slot_conf = slot.classify(text)

        # 展示槽位归一化过程
        normalized = slot._normalize_input(text)
        if normalized != text:
            print(f"  归一化: {text} → {normalized}")

        print(f"  原版MLP: {orig_intent:<16} conf={orig_conf:.2%}")
        print(f"  槽位MLP: {slot_intent:<16} conf={slot_conf:.2%}")
        if orig_intent == slot_intent:
            print(f"  ✅ 一致")
        else:
            print(f"  ⚡ 分歧")
        print()

    print(f"  共测试 {count} 条\n")


def main():
    print("=" * 70)
    print("  槽位意图分类器对比测试")
    print("=" * 70)

    print("\n正在加载模型...")
    orig = OrigClassifier()
    orig.load()
    slot = SlotClassifier()
    slot.load()
    print()

    args = sys.argv[1:]
    if "-i" in args or "--interactive" in args:
        interactive_mode(orig, slot)
    elif "-h" in args or "--help" in args:
        print("用法:")
        print("  python test_intent_slot.py          批量对比测试（默认）")
        print("  python test_intent_slot.py -i       交互对比模式")
        print("  python test_intent_slot.py -h       显示帮助")
    else:
        # 批量测试
        o1, s1, t1 = run_comparison(orig, slot, TEST_GENERALIZATION, "1. 泛化测试（训练未见动作词）")
        o2, s2, t2 = run_comparison(orig, slot, TEST_DISAMBIGUATION, "2. 消歧保护测试（Query 信号）")

        # 总览
        total_o = o1 + o2
        total_s = s1 + s2
        total_all = t1 + t2
        print(f"\n{'=' * 70}")
        print(f"  总览")
        print(f"{'=' * 70}")
        print(f"  原版MLP: {total_o}/{total_all} ({total_o/total_all:.0%})")
        print(f"  槽位MLP: {total_s}/{total_all} ({total_s/total_all:.0%})")
        delta = total_s - total_o
        if delta > 0:
            print(f"  🎯 槽位净优势: +{delta} 条")
        elif delta < 0:
            print(f"  ⚠️ 槽位净劣势: {delta} 条")
        else:
            print(f"  ➖ 持平")
        print()


if __name__ == "__main__":
    main()
