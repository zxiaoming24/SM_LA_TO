# -*- coding: utf-8 -*-
"""
BAAI/bge-base-zh-v1.5 + MLP  vs  普通大模型(LLM) 意图识别对比评测

对比维度：
  1. 准确率 / 宏平均F1
  2. 各类意图的识别准确率
  3. 单条耗时（均值 / P50 / P95）
  4. 置信度分布（本地模型输出概率 vs LLM 自评置信度）

用法：
    python compare_intent_approaches.py                    # 全量对比（本地 + LLM）
    python compare_intent_approaches.py --max-cases 20     # 只测前 20 条
    python compare_intent_approaches.py --skip-llm         # 只测本地模型（离线可用）
    python compare_intent_approaches.py --skip-local       # 只测 LLM
    python compare_intent_approaches.py --concurrency 3    # LLM 并发数（注意限流）

输出：
    output/intent_bge_mlp_vs_llm.png       # 2x2 对比可视化
    output/intent_compare_results.json     # 原始评测数据
"""

import os
import sys
import re
import json
import time
import asyncio

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# ★★★ 控制台编码（避免中文/emoji 打印报错）★★★
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False

# ==================== 测试集（复用现有测试用例） ====================
from test_intent_classifier import TEST_TYPOS, TEST_NORMAL, TEST_EDGE

ALL_CASES = TEST_TYPOS + TEST_NORMAL + TEST_EDGE

INTENT_CN = {
    "practice": "编程练习", "judge_code": "代码评判", "question_gen": "理论题",
    "doc_gen": "文档生成", "extension": "拓展阅读", "video": "视频学习",
    "mindmap": "思维导图", "animation": "动画生成", "study_plan": "学习计划",
    "ppt": "PPT生成", "register": "注册", "profile_modify": "画像修改",
    "refine_ppt": "大纲提炼", "teacher_advice": "学习建议", "chat": "闲聊",
    "super": "复合任务", "unrecognized": "无法识别",
}

# ==================== LLM 分类 Prompt 与解析 ====================

LLM_CLASSIFY_PROMPT = """你是一个中文教育系统的【意图分类器】。
请判断用户输入属于下列哪一个意图类别：

- practice: 编程练习/写代码/算法实现
- judge_code: 代码调试/检查错误/bug修复
- question_gen: 出理论题/测验/刷题
- doc_gen: 生成文档/笔记/总结
- extension: 拓展阅读/进阶/延伸
- video: 找视频/看教程/网课
- mindmap: 思维导图/脑图
- animation: 动画/可视化演示
- study_plan: 学习计划/学习路线
- ppt: PPT/幻灯片
- register: 用户注册
- profile_modify: 修改个人信息
- refine_ppt: PPT大纲提炼
- teacher_advice: 学习方法建议
- chat: 闲聊/与学习无关/纯查询
- super: 同时包含多个不同类别的学习任务（缺一不可，如"做PPT顺便出几道题"）

只输出一个 JSON 对象，不要输出任何其他内容：
{{"intent": "类别英文名", "confidence": 0.0到1.0之间的小数}}

用户输入：{text}"""

# LLM 可能输出别名 → 规范意图
_LLM_ALIASES = [
    ("judge_code", ["judge_code", "judge", "调试", "检查代码", "debug", "bug", "报错"]),
    ("question_gen", ["question_gen", "question", "出题", "理论题", "测验", "刷题"]),
    ("study_plan", ["study_plan", "学习计划", "计划", "路线"]),
    ("profile_modify", ["profile_modify", "个人信息", "画像修改"]),
    ("teacher_advice", ["teacher_advice", "学习建议", "怎么学"]),
    ("refine_ppt", ["refine_ppt", "提炼大纲", "润色"]),
    ("practice", ["practice", "编程练习", "写代码", "算法实现"]),
    ("doc_gen", ["doc_gen", "document", "文档", "笔记", "总结"]),
    ("extension", ["extension", "拓展", "延伸"]),
    ("animation", ["animation", "动画", "可视化"]),
    ("mindmap", ["mindmap", "思维导图", "导图", "脑图"]),
    ("register", ["register", "注册"]),
    ("unrecognized", ["unrecognized", "无法识别"]),
    ("video", ["video", "视频", "教程", "网课"]),
    ("ppt", ["ppt", "幻灯片", "PPT"]),
    ("super", ["super", "复合任务", "多任务"]),
    ("chat", ["chat", "闲聊", "聊天"]),
]

_KNOWN_INTENTS = {a[0] for a in _LLM_ALIASES}


def _parse_llm_output(content: str):
    """从 LLM 输出中解析 (intent, confidence)"""
    text = content.strip()
    # 提取 JSON
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    intent, conf = None, 0.0
    if match:
        try:
            data = json.loads(match.group())
            intent = str(data.get("intent", "")).strip().lower()
            try:
                conf = float(data.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
        except json.JSONDecodeError:
            pass
    if not intent:
        # 直接输出英文意图名的情况
        for known in _KNOWN_INTENTS:
            if known in text.lower():
                intent = known
                break
    if intent:
        intent = intent.lower()
        if intent not in _KNOWN_INTENTS:
            for canonical, aliases in _LLM_ALIASES:
                if any(a in intent for a in aliases):
                    intent = canonical
                    break
    conf = max(0.0, min(1.0, conf))
    return intent, conf


async def classify_with_llm(llm, text: str):
    """调用普通大模型分类，返回 (intent, confidence, latency, error)"""
    start = time.perf_counter()
    try:
        resp = await llm.ainvoke(LLM_CLASSIFY_PROMPT.format(text=text))
        content = resp.content if hasattr(resp, "content") else str(resp)
        intent, conf = _parse_llm_output(content)
        return intent, conf, time.perf_counter() - start, None
    except Exception as e:
        return None, 0.0, time.perf_counter() - start, str(e)


# ==================== 本地模型加载（魔塔 ModelScope） ====================

def load_local_classifier_via_modelscope():
    """
    使用魔塔(ModelScope)加载 BAAI/bge-base-zh-v1.5，并组装 IntentClassifier。
    国内网络环境下比 HuggingFace 更稳定。
    """
    import modelscope
    from modelscope import snapshot_download
    from sentence_transformers import SentenceTransformer
    from utils.intent_classifier import IntentClassifier

    clf = IntentClassifier()

    # ★★★ 魔塔下载模型（国内稳定），缓存到 .cache_models ★★★
    print("  ⏳ 正在通过魔塔(ModelScope)下载/加载 BAAI/bge-base-zh-v1.5 ...")
    local_path = snapshot_download(
        "BAAI/bge-base-zh-v1.5",
        cache_dir=os.path.join(_ROOT, ".cache_models"),
    )
    clf._model = SentenceTransformer(local_path)
    print(f"  ✅ 魔塔模型加载成功: {local_path}")

    # ★★★ 加载预计算意图向量（磁盘缓存，秒级）；不存在则实时编码并落盘 ★★★
    if not clf._load_precomputed_embeddings():
        print("  ⏳ 未找到预计算 embeddings，正在实时编码所有意图例句...")
        clf._precompute_embeddings()
        clf._save_precomputed_embeddings()

    # ★★★ 加载 MLP 分类头 ★★★
    clf._load_mlp_model()
    return clf


# ==================== 评测执行 ====================

def run_local(clf, cases):
    """本地 BAAI/bge + MLP（关闭 LLM 兜底，隔离纯本地能力）"""
    results = []
    for case in cases:
        text, expected = case[0], case[1]
        start = time.perf_counter()
        try:
            intent, conf = clf.classify(text, use_llm_fallback=False)
            err = None
        except Exception as e:
            intent, conf, err = None, 0.0, str(e)
        results.append({
            "text": text, "expected": expected, "pred": intent,
            "confidence": float(conf), "latency": time.perf_counter() - start, "error": err,
        })
    return results


async def run_llm(llm, cases, concurrency=1):
    """普通大模型分类（支持并发）"""
    sem = asyncio.Semaphore(concurrency)

    async def one(case):
        async with sem:
            intent, conf, latency, err = await classify_with_llm(llm, case[0])
            return {
                "text": case[0], "expected": case[1], "pred": intent,
                "confidence": conf, "latency": latency, "error": err,
            }

    return await asyncio.gather(*[one(c) for c in cases])


def compute_metrics(results, name: str) -> dict:
    """统计准确率 / 宏平均F1 / 各类准确率 / 耗时 / 置信度"""
    total = len(results)
    correct = sum(1 for r in results if r["pred"] == r["expected"])
    accuracy = correct / total if total else 0.0

    # 按类别统计 tp / fp / fn（宏平均 F1）
    intents = sorted({r["expected"] for r in results} | {r["pred"] for r in results if r["pred"]})
    f1s = []
    per_intent = {}
    for it in intents:
        tp = sum(1 for r in results if r["pred"] == it and r["expected"] == it)
        fp = sum(1 for r in results if r["pred"] == it and r["expected"] != it)
        fn = sum(1 for r in results if r["expected"] == it and r["pred"] != it)
        n = sum(1 for r in results if r["expected"] == it)
        p = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * rec / (p + rec) if (p + rec) else 0.0
        if (tp + fp + fn) > 0:
            f1s.append(f1)
        per_intent[it] = {"n": n, "correct": tp, "accuracy": tp / n if n else 0.0, "f1": f1}

    latencies = [r["latency"] for r in results if r["latency"] is not None]
    confs = [r["confidence"] for r in results if r["confidence"] is not None]
    errors = sum(1 for r in results if r["error"])
    lat = np.array(latencies) if latencies else np.array([0.0])

    return {
        "name": name, "total": total, "correct": correct, "accuracy": accuracy,
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
        "latency_ms": {
            "avg": float(lat.mean()) * 1000 if len(lat) else 0.0,
            "p50": float(np.median(lat)) * 1000 if len(lat) else 0.0,
            "p95": float(np.percentile(lat, 95)) * 1000 if len(lat) else 0.0,
            "total": float(lat.sum()) if len(lat) else 0.0,
        },
        "confidence": {"avg": float(np.mean(confs)) if confs else 0.0,
                       "p50": float(np.median(confs)) if confs else 0.0,
                       "values": confs},
        "call_errors": errors, "per_intent": per_intent,
    }


# ==================== 可视化 ====================

def plot_results(local_m: dict, llm_m: dict, out_png: str):
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle("BAAI/bge-base-zh-v1.5 + MLP  vs  普通大模型(LLM) 意图识别对比", fontsize=16, fontweight="bold")

    names = [local_m["name"], llm_m["name"]]
    colors = ["#4C72B0", "#DD8452"]

    # ---- 图1：整体准确率 & 宏平均F1 ----
    ax = axes[0][0]
    accs = [local_m["accuracy"], llm_m["accuracy"]]
    f1s = [local_m["macro_f1"], llm_m["macro_f1"]]
    x = np.arange(2)
    w = 0.32
    b1 = ax.bar(x - w / 2, accs, w, label="准确率 (Accuracy)", color=colors)
    b2 = ax.bar(x + w / 2, f1s, w, label="宏平均F1", color=colors, alpha=0.7)
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("得分")
    ax.set_title("整体准确率 & 宏平均F1")
    ax.legend()
    for bar in list(b1) + list(b2):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{bar.get_height():.1%}", ha="center", fontsize=10)

    # ---- 图2：各类意图准确率对比 ----
    ax = axes[0][1]
    intents = sorted(
        local_m["per_intent"].keys() | llm_m["per_intent"].keys(),
        key=lambda i: -(local_m["per_intent"].get(i, {}).get("n", 0) + llm_m["per_intent"].get(i, {}).get("n", 0)),
    )
    intents = [i for i in intents if (local_m["per_intent"].get(i, {}).get("n", 0) +
                                      llm_m["per_intent"].get(i, {}).get("n", 0)) >= 2]
    y = np.arange(len(intents))
    h = 0.36
    l_acc = [local_m["per_intent"].get(i, {}).get("accuracy", 0.0) for i in intents]
    g_acc = [llm_m["per_intent"].get(i, {}).get("accuracy", 0.0) for i in intents]
    ax.barh(y + h / 2, l_acc, h, label=local_m["name"], color=colors[0])
    ax.barh(y - h / 2, g_acc, h, label=llm_m["name"], color=colors[1])
    ax.set_yticks(y)
    ax.set_yticklabels([f"{INTENT_CN.get(i, i)} ({i})" for i in intents])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("准确率")
    ax.set_title("各类意图准确率对比（样本数≥2）")
    ax.legend()
    for yi, (la, ga) in enumerate(zip(l_acc, g_acc)):
        if la > 0: ax.text(la + 0.02, yi + h / 2, f"{la:.0%}", va="center", fontsize=9, color=colors[0])
        if ga > 0: ax.text(ga + 0.02, yi - h / 2, f"{ga:.0%}", va="center", fontsize=9, color=colors[1])

    # ---- 图3：耗时对比（对数坐标）----
    ax = axes[1][0]
    metrics = ["avg", "p50", "p95"]
    labels = ["平均耗时", "P50", "P95"]
    x = np.arange(len(metrics))
    w = 0.32
    l_t = [local_m["latency_ms"][m] for m in metrics]
    g_t = [llm_m["latency_ms"][m] for m in metrics]
    b1 = ax.bar(x - w / 2, l_t, w, label=local_m["name"], color=colors[0])
    b2 = ax.bar(x + w / 2, g_t, w, label=llm_m["name"], color=colors[1])
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_yscale("log")
    ax.set_ylabel("毫秒 (log)")
    ax.set_title("单条识别耗时对比（对数坐标）")
    ax.legend()
    for bar, vals in ((b1, l_t), (b2, g_t)):
        for bar_, v in zip(bar, vals):
            ax.text(bar_.get_x() + bar_.get_width() / 2, bar_.get_height() * 1.15,
                    f"{v:.0f}ms", ha="center", fontsize=9)
    # 备注总耗时
    note = (f"本地总耗时: {local_m['latency_ms']['total']/1000:.1f}s   "
            f"LLM总耗时: {llm_m['latency_ms']['total']/1000:.1f}s")
    ax.text(0.01, 0.96, note, transform=ax.transAxes, fontsize=10, va="top",
            bbox=dict(facecolor="#FFF3CD", alpha=0.8))

    # ---- 图4：置信度分布对比 ----
    ax = axes[1][1]
    bins = np.linspace(0, 1, 21)
    l_conf = local_m["confidence"]["values"]
    g_conf = llm_m["confidence"]["values"]
    if l_conf:
        ax.hist(l_conf, bins=bins, alpha=0.6, color=colors[0], label=f"{local_m['name']} (均值{local_m['confidence']['avg']:.2f})")
    if g_conf:
        ax.hist(g_conf, bins=bins, alpha=0.6, color=colors[1], label=f"{llm_m['name']} (均值{llm_m['confidence']['avg']:.2f})")
    ax.set_xlabel("置信度")
    ax.set_ylabel("样本数")
    ax.set_title("置信度分布对比")
    ax.legend()

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n📊 对比图已保存: {out_png}")


def print_report(local_m: dict, llm_m: dict):
    print("\n" + "=" * 72)
    print("  对比评测报告")
    print("=" * 72)
    print(f"{'指标':<18}{local_m['name']:<24}{llm_m['name']}")
    print("-" * 72)
    print(f"{'准确率':<18}{local_m['accuracy']:.2%}{'':<14}{llm_m['accuracy']:.2%}")
    print(f"{'宏平均F1':<18}{local_m['macro_f1']:.2%}{'':<14}{llm_m['macro_f1']:.2%}")
    print(f"{'平均耗时(ms)':<18}{local_m['latency_ms']['avg']:>8.1f}ms{'':<11}{llm_m['latency_ms']['avg']:>8.1f}ms")
    print(f"{'P50耗时(ms)':<18}{local_m['latency_ms']['p50']:>8.1f}ms{'':<11}{llm_m['latency_ms']['p50']:>8.1f}ms")
    print(f"{'P95耗时(ms)':<18}{local_m['latency_ms']['p95']:>8.1f}ms{'':<11}{llm_m['latency_ms']['p95']:>8.1f}ms")
    print(f"{'总耗时(s)':<18}{local_m['latency_ms']['total']/1000:>8.1f}s{'':<11}{llm_m['latency_ms']['total']/1000:>8.1f}s")
    print(f"{'平均置信度':<18}{local_m['confidence']['avg']:.2f}{'':<14}{llm_m['confidence']['avg']:.2f}")
    print(f"{'调用失败数':<18}{local_m['call_errors']:<24}{llm_m['call_errors']}")
    print("-" * 72)
    speedup = local_m["latency_ms"]["avg"] / llm_m["latency_ms"]["avg"] if llm_m["latency_ms"]["avg"] > 0 else float("inf")
    print(f"  ▶ 本地模型平均快 {speedup:.1f}x，但准确率差 "
          f"{(local_m['accuracy'] - llm_m['accuracy']):+.2%}（复合任务super类本地模型无该类别，需LLM层兜底）")
    print("=" * 72 + "\n")


# ==================== 主流程 ====================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="BAAI/bge+MLP vs LLM 意图识别对比")
    parser.add_argument("--max-cases", type=int, default=None, help="只测前 N 条")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 评测（离线）")
    parser.add_argument("--skip-local", action="store_true", help="跳过本地模型评测")
    parser.add_argument("--concurrency", type=int, default=1, help="LLM 并发数")
    args = parser.parse_args()

    cases = ALL_CASES if not args.max_cases else ALL_CASES[:args.max_cases]
    print(f"📋 测试用例: {len(cases)} 条（错别字 {len(TEST_TYPOS)} + 正常 {len(TEST_NORMAL)} + 边界 {len(TEST_EDGE)} 的子集）")

    results = {}

    # ---------- 本地模型 ----------
    if not args.skip_local:
        print("\n🔧 正在通过魔塔(ModelScope)加载本地模型 BAAI/bge-base-zh-v1.5 + MLP ...")
        clf = load_local_classifier_via_modelscope()
        t0 = time.perf_counter()
        local_results = run_local(clf, cases)
        print(f"✅ 本地模型评测完成，用时 {time.perf_counter() - t0:.1f}s")
        results["local"] = compute_metrics(local_results, "BAAI/bge+MLP")
        results["local"]["cases"] = local_results

    # ---------- 普通大模型 ----------
    if not args.skip_llm:
        print("\n🤖 正在调用普通大模型进行意图分类 ...")
        from utils.llm_config import get_chat_openai
        llm = get_chat_openai(temperature=0.0, max_tokens=30, timeout=30)
        t0 = time.perf_counter()
        llm_results = await run_llm(llm, cases, concurrency=args.concurrency)
        print(f"✅ LLM 评测完成，用时 {time.perf_counter() - t0:.1f}s")
        results["llm"] = compute_metrics(llm_results, "普通大模型(LLM)")
        results["llm"]["cases"] = llm_results

    # ---------- 输出 ----------
    if "local" in results and "llm" in results:
        print_report(results["local"], results["llm"])
        plot_results(results["local"], results["llm"], os.path.join(_ROOT, "output", "intent_bge_mlp_vs_llm.png"))
    elif "local" in results:
        print_report(results["local"], results["local"])
        plot_results(results["local"], results["local"], os.path.join(_ROOT, "output", "intent_bge_mlp_vs_llm.png"))
        print("⚠️  仅评测了本地模型（--skip-llm），图内 LLM 列与本地一致")
    elif "llm" in results:
        print_report(results["llm"], results["llm"])
        plot_results(results["llm"], results["llm"], os.path.join(_ROOT, "output", "intent_bge_mlp_vs_llm.png"))
        print("⚠️  仅评测了 LLM（--skip-local），图内本地列与 LLM 一致")

    # 保存原始数据
    out_json = os.path.join(_ROOT, "output", "intent_compare_results.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    dump = {k: {kk: vv for kk, vv in v.items() if kk != "cases"} for k, v in results.items()}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)
    print(f"📄 原始数据已保存: {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
