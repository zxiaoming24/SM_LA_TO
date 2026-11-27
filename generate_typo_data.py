"""
为 INTENT_EXAMPLES 生成错别字变体数据，用于 MLP 训练。

策略：
1. 直接解析 intent_classifier.py 源码提取 INTENT_EXAMPLES（无需 import numpy）
2. 对原有例句中的每个中文字，查找同音/近音字
3. 每个例句随机替换 1-2 个字，生成 2-3 个错别字变体
4. 确保生成的变体与原文不同

输出：utils/intent_examples_typo.py（仅错别字变体，不含原文）
"""

import os, sys, random, re, ast
from collections import defaultdict

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_CLASSIFIER_PATH = os.path.join(_PROJECT_ROOT, "utils", "intent_classifier.py")


def _is_chinese(ch: str) -> bool:
    return '\u4e00' <= ch <= '\u9fff'


def _parse_intent_examples() -> dict:
    """直接从源码解析 INTENT_EXAMPLES 字典，不依赖 import"""
    with open(_CLASSIFIER_PATH, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "INTENT_EXAMPLES":
            val = node.value
            data = {}
            if isinstance(val, ast.Dict):
                for key, val_node in zip(val.keys, val.values):
                    if isinstance(key, ast.Constant) and isinstance(val_node, ast.List):
                        k = key.value
                        items = [elt.value for elt in val_node.elts if isinstance(elt, ast.Constant)]
                        data[k] = items
            return data
    raise ValueError("未找到 INTENT_EXAMPLES 定义")


def build_homophone_dict(intent_examples: dict) -> dict:
    """构建 {拼音: [同音字列表]} 字典"""
    from pypinyin import pinyin as _pypinyin_func, Style as _PinyinStyle

    all_chars = set()
    for examples in intent_examples.values():
        for sent in examples:
            for ch in sent:
                if _is_chinese(ch):
                    all_chars.add(ch)
    all_chars = sorted(all_chars)
    print(f"  → 从例句中提取 {len(all_chars)} 个不同汉字")

    char_to_py = {}
    for ch in all_chars:
        try:
            syllables = _pypinyin_func(ch, style=_PinyinStyle.TONE2)
            py = re.sub(r'\d', '', syllables[0][0]) if syllables else ""
            char_to_py[ch] = py
        except Exception:
            continue

    py_to_chars = defaultdict(list)
    for ch, py in char_to_py.items():
        if py:
            py_to_chars[py].append(ch)

    result = {py: list(chars) for py, chars in py_to_chars.items()}
    print(f"  → 构建了 {len(result)} 个拼音分组")
    for py, chars in sorted(result.items(), key=lambda x: -len(x[1]))[:5]:
        print(f"    {py}: {''.join(chars[:10])}{'...' if len(chars) > 10 else ''}")
    return result


def generate_typo_variants(text: str, homophones: dict, max_variants: int = 3) -> list:
    """
    对单个句子生成错别字变体。
    - 找出句中所有中文字
    - 随机选择 1-2 个位置
    - 如果该字有同音字（不同字），则替换
    """
    from pypinyin import pinyin as _pypinyin_func, Style as _PinyinStyle

    chars = list(text)
    chinese_positions = [i for i, ch in enumerate(chars) if _is_chinese(ch)]
    if len(chinese_positions) < 1:
        return []

    def _get_py(ch):
        try:
            syllables = _pypinyin_func(ch, style=_PinyinStyle.TONE2)
            return re.sub(r'\d', '', syllables[0][0]) if syllables else ""
        except Exception:
            return ""

    variants = []
    seen = set()

    attempts = 0
    while len(variants) < max_variants and attempts < max_variants * 8:
        attempts += 1
        n_replace = 1 if random.random() < 0.5 else 2
        positions = random.sample(chinese_positions, min(n_replace, len(chinese_positions)))

        new_chars = list(text)
        replaced = False
        for pos in positions:
            original = chars[pos]
            py = _get_py(original)
            candidates = homophones.get(py, [])
            candidates = [c for c in candidates if c != original]
            if candidates:
                new_chars[pos] = random.choice(candidates)
                replaced = True

        if not replaced:
            continue

        new_text = "".join(new_chars)
        if new_text != text and new_text not in seen:
            seen.add(new_text)
            variants.append(new_text)

    return variants


def main():
    random.seed(42)
    print("=" * 60)
    print("  错别字变体数据生成")
    print("=" * 60)

    print("\n[1/3] 解析 INTENT_EXAMPLES...")
    intent_examples = _parse_intent_examples()
    total_original = sum(len(v) for v in intent_examples.values())
    intent_counts = {k: len(v) for k, v in intent_examples.items()}
    print(f"  → {len(intent_examples)} 个意图类别，共 {total_original} 条例句")
    for k in sorted(intent_counts.keys()):
        print(f"    {k:20s}: {intent_counts[k]:4d}条")

    print("\n[2/3] 构建同音字字典...")
    homophones = build_homophone_dict(intent_examples)

    print("\n[3/3] 生成错别字变体...")
    typo_data = {}
    target_per_intent = 250
    total_generated = 0

    for intent in sorted(intent_examples.keys()):
        originals = intent_examples[intent]
        variants_set = set()

        # ★★★ unrecognized 类别需要更多训练样本（拦截节点需要更高的鲁棒性）★★★
        need = 400 if intent == "unrecognized" else 250

        for sent in originals:
            if len(variants_set) >= need:
                break
            variants_set.update(generate_typo_variants(sent, homophones, max_variants=3))

        # 不够的话再来几轮
        extra_rounds = 0
        while len(variants_set) < need and extra_rounds < 10:
            extra_rounds += 1
            for sent in originals:
                if len(variants_set) >= need:
                    break
                variants_set.update(generate_typo_variants(sent, homophones, max_variants=2))

        typo_data[intent] = sorted(variants_set)[:need]
        n = len(typo_data[intent])
        total_generated += n
        print(f"  {intent:20s}: 原 {intent_counts[intent]:4d}条 + 错别字 {n:4d}条  (轮数={extra_rounds})")

    print(f"\n  {'─' * 40}")
    print(f"  {'总计':20s}: 原 {total_original:4d}条 + 错别字 {total_generated:4d}条")

    output_path = os.path.join(_PROJECT_ROOT, "utils", "intent_examples_typo.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write("# 自动生成的错别字变体数据（由 generate_typo_data.py 生成）\n")
        f.write("# 用于扩充训练数据，提高 MLP 对错别字的鲁棒性\n\n")
        f.write("INTENT_EXAMPLES_TYPO = {\n")
        for intent in sorted(typo_data.keys()):
            items = typo_data[intent]
            f.write(f'    "{intent}": [\n')
            for item in items:
                escaped = item.replace('\\', '\\\\').replace('"', '\\"')
                f.write(f'        "{escaped}",\n')
            f.write("    ],\n")
        f.write("}\n")

    print(f"\n  ✅ 已保存到: {output_path}")
    print()


if __name__ == "__main__":
    main()
