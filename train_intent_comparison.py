"""
意图分类器对比训练脚本

对同一数据集训练三种模型进行对比：
  1. 修复版 MLP   (加正则化 + train/test分割 + 缩小网络)
  2. SVM          (LinearSVC, 泛化能力更强)
  3. LogisticRegression (逻辑回归, 轻量快速)

所有模型独立保存，互不影响原有的 train_intent_classifier.py 产物。

用法:
    python train_intent_comparison.py

输出:
    user_features/intent_comparison/
        ├── mlp/               # 修复版 MLP
        ├── svm/               # SVM
        ├── lr/                # 逻辑回归
        └── comparison_report.png  # 对比可视化图
"""

import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import sys
import pickle
import time
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif hasattr(sys.stdout, "buffer"):
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

_COMPARE_DIR = os.path.join(_PROJECT_ROOT, "user_features", "intent_comparison")


def _load_intent_examples():
    """加载所有例句（含错别字变体和LLM扩充）"""
    from utils.intent_classifier import INTENT_EXAMPLES
    # 合并错别字变体
    try:
        from utils.intent_examples_typo import INTENT_EXAMPLES_TYPO
        for _intent, _examples in INTENT_EXAMPLES_TYPO.items():
            if _intent in INTENT_EXAMPLES:
                _existing = set(INTENT_EXAMPLES[_intent])
                for ex in _examples:
                    if ex not in _existing:
                        INTENT_EXAMPLES[_intent].append(ex)
                        _existing.add(ex)
    except ImportError:
        pass
    # 合并LLM扩充例句
    try:
        from utils.intent_examples_llm import INTENT_EXAMPLES_LLM
        for _intent, _examples in INTENT_EXAMPLES_LLM.items():
            if _intent in INTENT_EXAMPLES:
                _existing = set(INTENT_EXAMPLES[_intent])
                for ex in _examples:
                    if ex not in _existing:
                        INTENT_EXAMPLES[_intent].append(ex)
                        _existing.add(ex)
    except ImportError:
        pass
    return INTENT_EXAMPLES


def _load_embedding_model():
    """加载 BGE 嵌入模型（仅使用 ModelScope 魔塔）"""
    from sentence_transformers import SentenceTransformer
    model = None
    cache_dir = os.path.join(_PROJECT_ROOT, ".cache_models")

    try:
        model = SentenceTransformer("BAAI/bge-base-zh-v1.5", local_files_only=True)
        print("  ✅ 从本地缓存加载成功")
        return model
    except Exception:
        pass

    try:
        from modelscope import snapshot_download
        print("  ⏳ 从 ModelScope 魔塔下载 bge-base-zh-v1.5 ...")
        local_path = snapshot_download("BAAI/bge-base-zh-v1.5", cache_dir=cache_dir)
        model = SentenceTransformer(local_path)
        print("  ✅ 从 ModelScope 下载成功")
        return model
    except ImportError:
        raise RuntimeError("未安装 modelscope，请运行: pip install modelscope")
    except Exception as e:
        raise RuntimeError(f"ModelScope 下载失败: {e}")


def _prepare_data(model, INTENT_EXAMPLES):
    """编码所有例句，返回 (X, y, intents_list)"""
    intents = sorted(INTENT_EXAMPLES.keys())
    X_list, y_list = [], []
    for intent in intents:
        examples = INTENT_EXAMPLES[intent]
        embs = model.encode(examples, normalize_embeddings=True, show_progress_bar=False)
        X_list.append(embs)
        y_list.extend([intent] * len(examples))
    X = np.vstack(X_list)
    y = np.array(y_list)
    return X, y, intents


def _train_mlp_fixed(X_train, y_train, X_test, y_test, intents):
    """
    修复版 MLP:
    - 缩小网络 (64, 32) 防止过拟合
    - L2 正则化 alpha=0.01
    - 训练/测试分离评估
    """
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import classification_report, confusion_matrix

    print("\n" + "=" * 50)
    print("  [1/3] 训练修复版 MLP ...")
    print("=" * 50)

    label_encoder = LabelEncoder()
    y_train_enc = label_encoder.fit_transform(y_train)
    y_test_enc = label_encoder.transform(y_test)

    mlp = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        alpha=0.01,
        learning_rate="adaptive",
        max_iter=2000,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.15,
        verbose=False,
    )

    t0 = time.time()
    mlp.fit(X_train, y_train_enc)
    train_time = time.time() - t0

    train_acc = mlp.score(X_train, y_train_enc)
    test_acc = mlp.score(X_test, y_test_enc)

    y_pred_train = mlp.predict(X_train)
    y_pred_test = mlp.predict(X_test)

    print(f"  训练轮次: {mlp.n_iter_}")
    print(f"  训练耗时: {train_time:.2f}s")
    print(f"  训练集准确率: {train_acc:.2%}")
    print(f"  测试集准确率: {test_acc:.2%}")
    print(f"  过拟合差距:   {train_acc - test_acc:.2%}")

    report = classification_report(y_test_enc, y_pred_test, target_names=intents, digits=4)
    print(f"\n  测试集分类报告:\n{report}")

    cm = confusion_matrix(y_test_enc, y_pred_test)

    # 保存模型
    save_dir = os.path.join(_COMPARE_DIR, "mlp")
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "model.pkl"), "wb") as f:
        pickle.dump(mlp, f)
    with open(os.path.join(save_dir, "label_encoder.pkl"), "wb") as f:
        pickle.dump(label_encoder, f)

    return {
        "name": "MLP (修复版)",
        "model": mlp,
        "label_encoder": label_encoder,
        "train_acc": train_acc,
        "test_acc": test_acc,
        "train_time": train_time,
        "cm": cm,
        "report": report,
        "y_test": y_test_enc,
        "y_pred": y_pred_test,
    }


def _train_svm(X_train, y_train, X_test, y_test, intents):
    """
    LinearSVM:
    - C=0.1 较大正则化
    - class_weight='balanced' 平衡类别
    """
    from sklearn.svm import LinearSVC
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import classification_report, confusion_matrix

    print("\n" + "=" * 50)
    print("  [2/3] 训练 SVM (LinearSVC) ...")
    print("=" * 50)

    label_encoder = LabelEncoder()
    y_train_enc = label_encoder.fit_transform(y_train)
    y_test_enc = label_encoder.transform(y_test)

    svm = LinearSVC(
        C=0.1,
        class_weight="balanced",
        max_iter=5000,
        random_state=42,
        dual="auto",
    )

    t0 = time.time()
    svm.fit(X_train, y_train_enc)
    train_time = time.time() - t0

    train_acc = svm.score(X_train, y_train_enc)
    test_acc = svm.score(X_test, y_test_enc)

    y_pred_train = svm.predict(X_train)
    y_pred_test = svm.predict(X_test)

    print(f"  训练耗时: {train_time:.2f}s")
    print(f"  训练集准确率: {train_acc:.2%}")
    print(f"  测试集准确率: {test_acc:.2%}")
    print(f"  过拟合差距:   {train_acc - test_acc:.2%}")

    report = classification_report(y_test_enc, y_pred_test, target_names=intents, digits=4)
    print(f"\n  测试集分类报告:\n{report}")

    cm = confusion_matrix(y_test_enc, y_pred_test)

    save_dir = os.path.join(_COMPARE_DIR, "svm")
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "model.pkl"), "wb") as f:
        pickle.dump(svm, f)
    with open(os.path.join(save_dir, "label_encoder.pkl"), "wb") as f:
        pickle.dump(label_encoder, f)

    return {
        "name": "SVM (LinearSVC)",
        "model": svm,
        "label_encoder": label_encoder,
        "train_acc": train_acc,
        "test_acc": test_acc,
        "train_time": train_time,
        "cm": cm,
        "report": report,
        "y_test": y_test_enc,
        "y_pred": y_pred_test,
    }


def _train_lr(X_train, y_train, X_test, y_test, intents):
    """
    Logistic Regression:
    - L1 正则化做特征选择
    - C=0.5 适中正则化
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import classification_report, confusion_matrix

    print("\n" + "=" * 50)
    print("  [3/3] 训练 LogisticRegression ...")
    print("=" * 50)

    label_encoder = LabelEncoder()
    y_train_enc = label_encoder.fit_transform(y_train)
    y_test_enc = label_encoder.transform(y_test)

    lr = LogisticRegression(
        l1_ratio=1.0,
        C=0.5,
        solver="saga",
        max_iter=5000,
        random_state=42,
    )

    t0 = time.time()
    lr.fit(X_train, y_train_enc)
    train_time = time.time() - t0

    train_acc = lr.score(X_train, y_train_enc)
    test_acc = lr.score(X_test, y_test_enc)

    y_pred_train = lr.predict(X_train)
    y_pred_test = lr.predict(X_test)

    print(f"  训练耗时: {train_time:.2f}s")
    print(f"  训练集准确率: {train_acc:.2%}")
    print(f"  测试集准确率: {test_acc:.2%}")
    print(f"  过拟合差距:   {train_acc - test_acc:.2%}")

    report = classification_report(y_test_enc, y_pred_test, target_names=intents, digits=4)
    print(f"\n  测试集分类报告:\n{report}")

    cm = confusion_matrix(y_test_enc, y_pred_test)

    save_dir = os.path.join(_COMPARE_DIR, "lr")
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "model.pkl"), "wb") as f:
        pickle.dump(lr, f)
    with open(os.path.join(save_dir, "label_encoder.pkl"), "wb") as f:
        pickle.dump(label_encoder, f)

    return {
        "name": "LogisticRegression",
        "model": lr,
        "label_encoder": label_encoder,
        "train_acc": train_acc,
        "test_acc": test_acc,
        "train_time": train_time,
        "cm": cm,
        "report": report,
        "y_test": y_test_enc,
        "y_pred": y_pred_test,
    }


def _visualize(results, intents):
    """生成对比可视化图"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        for _font_name in ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]:
            try:
                matplotlib.font_manager.findfont(_font_name, fallback_to_default=False)
                plt.rcParams["font.sans-serif"] = [_font_name]
                break
            except Exception:
                continue
        plt.rcParams["axes.unicode_minus"] = False
    except ImportError:
        print("  ⚠️ matplotlib 未安装，跳过可视化")
        return

    fig = plt.figure(figsize=(24, 18))
    fig.suptitle("意图分类器对比报告", fontsize=18, fontweight="bold", y=0.98)

    # ---- 图1: 准确率柱状对比 ----
    ax1 = fig.add_subplot(2, 3, 1)
    names = [r["name"] for r in results]
    train_accs = [r["train_acc"] for r in results]
    test_accs = [r["test_acc"] for r in results]
    x = np.arange(len(names))
    width = 0.35

    bars1 = ax1.bar(x - width / 2, train_accs, width, label="训练集", color="#3498db", alpha=0.85)
    bars2 = ax1.bar(x + width / 2, test_accs, width, label="测试集", color="#e74c3c", alpha=0.85)

    ax1.set_ylabel("准确率", fontsize=11)
    ax1.set_title("准确率对比 (训练集 vs 测试集)", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, fontsize=9, rotation=15)
    ax1.legend(fontsize=9)
    ax1.set_ylim(0, 1.1)
    ax1.axhline(y=0.9, color="green", linestyle="--", alpha=0.5, label="90%基线")

    for bar in bars1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., h + 0.01,
                 f"{h:.1%}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    for bar in bars2:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., h + 0.01,
                 f"{h:.1%}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    # ---- 图2: 过拟合差距对比 ----
    ax2 = fig.add_subplot(2, 3, 2)
    gaps = [r["train_acc"] - r["test_acc"] for r in results]
    colors = ["#2ecc71" if g < 0.03 else "#f39c12" if g < 0.06 else "#e74c3c" for g in gaps]
    bars3 = ax2.bar(x, gaps, color=colors, alpha=0.85)
    ax2.set_ylabel("过拟合差距 (训练-测试)", fontsize=11)
    ax2.set_title("过拟合程度对比", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, fontsize=9, rotation=15)
    ax2.axhline(y=0.05, color="red", linestyle="--", alpha=0.5, label="5%警戒线")
    for bar, g in zip(bars3, gaps):
        ax2.text(bar.get_x() + bar.get_width() / 2., g + 0.002,
                 f"{g:.2%}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax2.legend(fontsize=8)

    # ---- 图3: 训练耗时对比 ----
    ax3 = fig.add_subplot(2, 3, 3)
    times = [r["train_time"] for r in results]
    colors3 = ["#2ecc71" if t < 5 else "#f39c12" if t < 15 else "#e74c3c" for t in times]
    bars4 = ax3.bar(x, times, color=colors3, alpha=0.85)
    ax3.set_ylabel("训练耗时 (秒)", fontsize=11)
    ax3.set_title("训练效率对比", fontsize=12, fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(names, fontsize=9, rotation=15)
    for bar, t in zip(bars4, times):
        ax3.text(bar.get_x() + bar.get_width() / 2., t + 0.05,
                 f"{t:.2f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # ---- 图4-6: 各模型混淆矩阵 ----
    short_labels = [c.replace("_", "\n") for c in intents]
    for i, result in enumerate(results):
        ax = fig.add_subplot(2, 3, 4 + i)
        cm = result["cm"]
        im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
        ax.set_title(f"{result['name']}\n混淆矩阵", fontsize=11, fontweight="bold")
        tick_marks = range(len(intents))
        ax.set_xticks(tick_marks)
        ax.set_xticklabels(short_labels, fontsize=7, rotation=45)
        ax.set_yticks(tick_marks)
        ax.set_yticklabels(short_labels, fontsize=7)
        thresh = cm.max() / 2.
        for ii in range(cm.shape[0]):
            for jj in range(cm.shape[1]):
                ax.text(jj, ii, str(cm[ii, jj]),
                        ha="center", va="center",
                        color="white" if cm[ii, jj] > thresh else "black",
                        fontsize=8)
        plt.colorbar(im, ax=ax, shrink=0.8)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save_path = os.path.join(_COMPARE_DIR, "comparison_report.png")
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  📊 对比报告已保存: {save_path}")


def main():
    print("=" * 60)
    print("  意图分类器对比训练脚本")
    print("  对比三种模型: 修复版MLP / SVM / LogisticRegression")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/5] 加载例句数据...")
    INTENT_EXAMPLES = _load_intent_examples()
    intents = sorted(INTENT_EXAMPLES.keys())
    total = sum(len(v) for v in INTENT_EXAMPLES.values())
    print(f"  → {len(intents)} 类意图，共 {total} 条例句")
    for k, v in INTENT_EXAMPLES.items():
        print(f"    {k}: {len(v)} 条")

    # 2. 加载嵌入模型
    print("\n[2/5] 加载语义嵌入模型 BAAI/bge-base-zh-v1.5...")
    model = _load_embedding_model()

    # 3. 编码数据
    print("\n[3/5] 编码例句生成训练集...")
    X, y, intents = _prepare_data(model, INTENT_EXAMPLES)
    print(f"  → X={X.shape}, y={y.shape}")

    # 4. 切分 train/test
    print("\n[4/5] 划分训练集/测试集 (80%/20%, 分层抽样)...")
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  训练集: {X_train.shape[0]} 条")
    print(f"  测试集: {X_test.shape[0]} 条")

    # 5. 训练三种模型
    print("\n[5/5] 训练三种模型...")
    results = []

    result_mlp = _train_mlp_fixed(X_train, y_train, X_test, y_test, intents)
    results.append(result_mlp)

    result_svm = _train_svm(X_train, y_train, X_test, y_test, intents)
    results.append(result_svm)

    result_lr = _train_lr(X_train, y_train, X_test, y_test, intents)
    results.append(result_lr)

    # 6. 可视化
    print("\n" + "=" * 60)
    print("  生成对比可视化报告...")
    print("=" * 60)
    _visualize(results, intents)

    # 7. 汇总
    print("\n" + "=" * 60)
    print("  📋 最终对比汇总")
    print("=" * 60)
    print(f"  {'模型':<20} {'训练准确率':>10} {'测试准确率':>10} {'过拟合差距':>10} {'训练耗时':>10}")
    print(f"  {'-'*60}")
    for r in results:
        gap = r["train_acc"] - r["test_acc"]
        print(f"  {r['name']:<20} {r['train_acc']:>9.2%} {r['test_acc']:>9.2%} {gap:>9.2%} {r['train_time']:>9.2f}s")

    # 找出最优模型
    best = max(results, key=lambda r: r["test_acc"] - (r["train_acc"] - r["test_acc"]))
    print(f"\n  🏆 推荐模型: {best['name']}")
    print(f"     测试准确率: {best['test_acc']:.2%}")
    print(f"     过拟合差距: {best['train_acc'] - best['test_acc']:.2%}")
    print(f"\n  💾 所有模型已保存到: {_COMPARE_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()