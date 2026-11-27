"""
使用 LLM 生成增强训练数据（难负例 + 变体）

策略：
1. 对每个意图类别，生成更多正例
2. 生成难负例（看似属于某意图但实际不属于）
3. 生成错别字/同义变体
4. 生成边界模糊的混合意图

输出：utils/intent_examples_augmented.py
"""

import os, sys, json, random

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def load_llm_client():
    """加载 LLM 客户端"""
    from utils.llm_config import get_chat_openai
    return get_chat_openai(temperature=0.8, max_tokens=1000, timeout=60)


def generate_positive_examples(llm, intent: str, existing_examples: list, count: int = 20):
    """生成正例：与现有意图匹配的新句子"""
    existing_str = "\n".join(existing_examples[:10]) if existing_examples else ""
    
    prompt = f"""你是一个数据生成专家。请为意图类别 "{intent}" 生成 {count} 个新的用户输入句子。

现有示例（仅参考风格）：
{existing_str}

要求：
1. 句子必须符合 "{intent}" 的意图
2. 使用多样化的表达方式
3. 避免与现有示例重复
4. 每个句子单独一行，不要编号

输出格式：
<句子1>
<句子2>
..."""
    
    try:
        response = llm.invoke(prompt)
        lines = [l.strip() for l in response.content.strip().split('\n') if l.strip()]
        return [l for l in lines if l not in existing_examples][:count]
    except Exception as e:
        print(f"  ⚠️ 生成正例失败: {e}")
        return []


def generate_hard_negatives(llm, intent: str, all_intents: list, count: int = 15):
    """生成难负例：看似属于某意图但实际不属于"""
    other_intents = [i for i in all_intents if i != intent]
    random.shuffle(other_intents)
    target_others = other_intents[:5]
    
    prompt = f"""你是一个数据生成专家。请生成 {count} 个"难负例"句子，这些句子看似属于意图 "{intent}"，但实际上属于其他意图。

目标混淆意图：{', '.join(target_others)}

要求：
1. 句子中包含 "{intent}" 相关的关键词或表达方式
2. 但整体语义偏向其他意图
3. 具有迷惑性，让简单的关键词匹配会出错
4. 每个句子单独一行，不要编号

输出格式：
<难负例句子1>
<难负例句子2>
..."""
    
    try:
        response = llm.invoke(prompt)
        lines = [l.strip() for l in response.content.strip().split('\n') if l.strip()]
        return lines[:count]
    except Exception as e:
        print(f"  ⚠️ 生成难负例失败: {e}")
        return []


def generate_typo_variants(llm, examples: list, count: int = 10):
    """生成错别字变体"""
    sample = random.sample(examples, min(5, len(examples)))
    sample_str = "\n".join(sample)
    
    prompt = f"""你是一个数据生成专家。请为以下句子生成错别字变体。

原句：
{sample_str}

要求：
1. 每个句子生成 1-2 个变体
2. 只替换 1-2 个字为同音或形近字
3. 保持整体语义可辨认但有错别字
4. 每个变体单独一行，不要编号

输出格式：
<变体1>
<变体2>
..."""
    
    try:
        response = llm.invoke(prompt)
        lines = [l.strip() for l in response.content.strip().split('\n') if l.strip()]
        return lines[:count]
    except Exception as e:
        print(f"  ⚠️ 生成错别字变体失败: {e}")
        return []


def generate_boundary_cases(llm, intent: str, count: int = 5):
    """生成边界模糊的混合意图句子"""
    prompt = f"""你是一个数据生成专家。请生成 {count} 个边界模糊的句子。

目标意图：{intent}

要求：
1. 句子包含多个意图的元素
2. 语义模糊，难以确定单一意图
3. 可能需要结合上下文才能判断
4. 每个句子单独一行，不要编号

输出格式：
<边界句子1>
<边界句子2>
..."""
    
    try:
        response = llm.invoke(prompt)
        lines = [l.strip() for l in response.content.strip().split('\n') if l.strip()]
        return lines[:count]
    except Exception as e:
        print(f"  ⚠️ 生成边界案例失败: {e}")
        return []


def main():
    print("=" * 60)
    print("  使用 LLM 生成增强训练数据")
    print("=" * 60)
    
    from utils.intent_classifier import INTENT_EXAMPLES
    
    print("\n[1/3] 加载 LLM 客户端...")
    llm = load_llm_client()
    print("  ✓ LLM 客户端加载完成")
    
    print("\n[2/3] 生成增强数据...")
    augmented_data = {}
    all_intents = list(INTENT_EXAMPLES.keys())
    
    total_generated = 0
    for intent in sorted(all_intents):
        print(f"\n  {intent}:")
        
        existing = INTENT_EXAMPLES[intent]
        augmented = set(existing)
        
        pos_examples = generate_positive_examples(llm, intent, existing, count=20)
        if pos_examples:
            augmented.update(pos_examples)
            print(f"    + {len(pos_examples)} 条正例")
        
        if intent != "unrecognized":
            hard_neg = generate_hard_negatives(llm, intent, all_intents, count=15)
            if hard_neg:
                augmented.update(hard_neg)
                print(f"    + {len(hard_neg)} 条难负例")
        
        typo_vars = generate_typo_variants(llm, existing, count=10)
        if typo_vars:
            augmented.update(typo_vars)
            print(f"    + {len(typo_vars)} 条错别字变体")
        
        boundary = generate_boundary_cases(llm, intent, count=5)
        if boundary:
            augmented.update(boundary)
            print(f"    + {len(boundary)} 条边界案例")
        
        augmented_data[intent] = sorted(augmented)
        new_count = len(augmented_data[intent]) - len(existing)
        total_generated += new_count
        print(f"    总计: {len(existing)} → {len(augmented_data[intent])} (+{new_count})")
    
    print(f"\n  总共生成: {total_generated} 条增强数据")
    
    print("\n[3/3] 保存增强数据...")
    output_path = os.path.join(_PROJECT_ROOT, "utils", "intent_examples_augmented.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write("# 自动生成的增强训练数据（由 generate_augmented_data.py 生成）\n")
        f.write("# 包含正例、难负例、错别字变体、边界案例\n\n")
        
        f.write("INTENT_EXAMPLES_AUGMENTED = {\n")
        for intent in sorted(augmented_data.keys()):
            items = augmented_data[intent]
            f.write(f'    "{intent}": [\n')
            for item in items:
                escaped = item.replace('\\', '\\\\').replace('"', '\\"')
                f.write(f'        "{escaped}",\n')
            f.write("    ],\n")
        f.write("}\n")
    
    print(f"  ✅ 已保存到: {output_path}")
    
    print("\n[4/4] 更新 INTENT_EXAMPLES 使用增强数据...")
    classifier_path = os.path.join(_PROJECT_ROOT, "utils", "intent_classifier.py")
    with open(classifier_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "from utils.intent_examples_augmented import INTENT_EXAMPLES_AUGMENTED" not in content:
        import re
        content = re.sub(
            r'INTENT_EXAMPLES = \{',
            'from utils.intent_examples_augmented import INTENT_EXAMPLES_AUGMENTED\nINTENT_EXAMPLES = INTENT_EXAMPLES_AUGMENTED\n',
            content,
            count=1
        )
        
        with open(classifier_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print("  ✅ 已更新 intent_classifier.py 使用增强数据")
    else:
        print("  ⏭️ 已使用增强数据，跳过更新")
    
    print("\n完成！请重新运行 train_intent_classifier.py 训练 MLP 模型。")


if __name__ == "__main__":
    main()
