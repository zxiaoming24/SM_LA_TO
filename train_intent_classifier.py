"""
MLP 意图分类器训练脚本

独立训练意图分类 MLP 模型，保存到 user_features/intent_mlp_model/，
供 IntentClassifier 在启动时直接加载。

用法:
    python train_intent_classifier.py

输出:
    user_features/intent_mlp_model/
        ├── mlp.pkl              # 训练好的 MLPClassifier
        └── label_encoder.pkl    # LabelEncoder（意图名 ↔ 整数标签）
"""

import os

# ★★★ 必须在任何 huggingface 相关 import 之前设置镜像 ★★★
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import sys
import pickle
import numpy as np

# ★★★ 设置控制台编码为 utf-8，避免 emoji 打印报错 ★★★
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# ★★★ 将项目根目录加入 sys.path，确保能导入 utils.intent_classifier ★★★
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

# ★★★ 模型保存路径（与 IntentClassifier._load_mlp_model 一致）★★★
_MODEL_DIR = os.path.join(_PROJECT_ROOT, "user_features", "intent_mlp_model")
_MODEL_PATH = os.path.join(_MODEL_DIR, "mlp.pkl")
_ENCODER_PATH = os.path.join(_MODEL_DIR, "label_encoder.pkl")


def main():
    print("=" * 60)
    print("  MLP 意图分类器训练脚本")
    print("=" * 60)

    # ---------- 1. 加载意图例句 ----------
    print("\n[1/5] 加载 INTENT_EXAMPLES...")
    from utils.intent_classifier import INTENT_EXAMPLES
    intents = sorted(INTENT_EXAMPLES.keys())
    print(f"  → {len(intents)} 个意图类别，共 {sum(len(v) for v in INTENT_EXAMPLES.values())} 条例句")

    # ---------- 2. 加载嵌入模型 ----------
    print("\n[2/5] 加载语义嵌入模型 BAAI/bge-base-zh-v1.5...")
    from sentence_transformers import SentenceTransformer
    model = None
    # 尝试 1：本地缓存
    try:
        model = SentenceTransformer("BAAI/bge-base-zh-v1.5", local_files_only=True)
        print("  ✅ 从本地缓存加载成功")
    except Exception:
        pass
    # 尝试 2：ModelScope（国内稳定）
    if model is None:
        try:
            from modelscope import snapshot_download
            print("  ⏳ 尝试从 ModelScope 下载...")
            local_path = snapshot_download("BAAI/bge-base-zh-v1.5", cache_dir=os.path.join(_PROJECT_ROOT, ".cache_models"))
            model = SentenceTransformer(local_path)
            print("  ✅ 从 ModelScope 下载成功")
        except ImportError:
            print("  ℹ️  modelscope 未安装，跳过")
        except Exception as e:
            print(f"  ⚠️  ModelScope 下载失败: {e}")
    # 尝试 3：HuggingFace 镜像
    if model is None:
        try:
            print("  ⏳ 尝试从 hf-mirror.com 下载...")
            model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
            print("  ✅ 从 HuggingFace 镜像下载成功")
        except Exception as e:
            print(f"  ❌ 所有下载源均失败: {e}")
            raise RuntimeError("无法下载 bge-base-zh-v1.5 模型，请检查网络或手动下载")
    print("  ✅ 模型加载完成")

    # ---------- 3. 编码所有例句 ----------
    print("\n[3/5] 编码例句生成训练集...")

    # ★ P1: 清洗跨意图重复例句 —— 同一归一化文本出现在多个意图下时，只保留首次出现的意图 ★
    import re
    _norm_text = lambda s: re.sub(r"[\s，。！？,.!?]", "", s).lower()
    _seen_norm: dict = {}
    _duplicates: list = []
    for _intent in intents:
        _examples = INTENT_EXAMPLES[_intent]
        _cleaned = []
        for _ex in _examples:
            _key = _norm_text(_ex)
            if _key in _seen_norm and _seen_norm[_key] != _intent:
                # 跨意图重复：删除当前，保留首次出现的意图
                _duplicates.append((_ex, _seen_norm[_key], _intent))
                continue
            if _key not in _seen_norm:
                _seen_norm[_key] = _intent
            _cleaned.append(_ex)
        INTENT_EXAMPLES[_intent] = _cleaned

    if _duplicates:
        print(f"  ⚠️ 发现 {len(_duplicates)} 条跨意图重复例句，已删除：")
        for _ex, _src, _dst in _duplicates:
            print(f"     '{_ex}' 同时在 '{_src}' 和 '{_dst}' 中，保留 '{_src}'")
    else:
        print(f"  ✅ 未发现跨意图重复例句")
    print(f"  → 清洗后样本数: {sum(len(v) for v in INTENT_EXAMPLES.values())}")

    X_list, y_list = [], []
    for intent in intents:
        examples = INTENT_EXAMPLES[intent]
        embs = model.encode(examples, normalize_embeddings=True, show_progress_bar=True)
        X_list.append(embs)
        y_list.extend([intent] * len(examples))

    X = np.vstack(X_list)
    y = np.array(y_list)
    print(f"  → 训练集形状: X={X.shape}, y={y.shape}")

    # ---------- 4. 训练 MLP 分类头 ----------
    print("\n[4/5] 训练 MLP 分类头 (512 → 256 → 128 → {})...".format(len(intents)))
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import LabelEncoder
    import sklearn as _sk

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    # ★ P0-2: 类别平衡加权 —— 仅 sklearn >= 1.2 支持 class_weight 参数 ★
    # 1.2 以下版本传入会抛 TypeError，先做版本探测
    _sk_ver = tuple(int(x) for x in _sk.__version__.split(".")[:2])
    _mlp_kwargs = dict(
        hidden_layer_sizes=(256, 128),
        activation="relu",
        max_iter=2000,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        verbose=True,
    )
    if _sk_ver >= (1, 2):
        _mlp_kwargs["class_weight"] = "balanced"
        print(f"  ✅ sklearn {_sk.__version__} ≥ 1.2，启用 class_weight='balanced'")
    else:
        print(f"  ⚠️ sklearn {_sk.__version__} < 1.2，跳过 class_weight（不支持）")

    mlp = MLPClassifier(**_mlp_kwargs)
    mlp.fit(X, y_encoded)

    train_acc = mlp.score(X, y_encoded)
    print(f"  ✅ 训练完成 | 共 {mlp.n_iter_} 轮 | 训练集准确率: {train_acc:.2%}")

    # ---------- 5. 可视化结果 ----------
    print("\n[5/5] 可视化训练结果...")
    try:
        import matplotlib
        matplotlib.use("Agg")  # 非交互后端，兼容无 GUI 环境
        import matplotlib.pyplot as plt
        # ★★★ 设置中文字体 ★★★
        for _font_name in ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]:
            try:
                matplotlib.font_manager.findfont(_font_name, fallback_to_default=False)
                plt.rcParams["font.sans-serif"] = [_font_name]
                break
            except Exception:
                continue
        plt.rcParams["axes.unicode_minus"] = False

        from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report

        y_pred = mlp.predict(X)
        y_pred_labels = label_encoder.inverse_transform(y_pred)
        intents_display = [c.replace("_", "\n") for c in intents]

        fig, axes = plt.subplots(1, 3, figsize=(20, 6))

        # ---- 图1: Loss 曲线 ----
        ax1 = axes[0]
        ax1.plot(mlp.loss_curve_, linewidth=1.5)
        ax1.set_title("Training Loss Curve", fontsize=13)
        ax1.set_xlabel("Iteration")
        ax1.set_ylabel("Loss")
        ax1.grid(True, alpha=0.3)
        ax1.axvline(mlp.n_iter_, color="red", linestyle="--", alpha=0.5, label=f"stop={mlp.n_iter_}")
        ax1.legend()

        # ---- 图2: 混淆矩阵 ----
        cm = confusion_matrix(y_encoded, y_pred)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=intents_display)
        disp.plot(ax=axes[1], cmap="Blues", colorbar=False, values_format="d")
        axes[1].set_title("Confusion Matrix", fontsize=13)
        axes[1].tick_params(axis="x", rotation=45, labelsize=7)
        axes[1].tick_params(axis="y", labelsize=7)

        # ---- 图3: 每类准确率 ----
        ax3 = axes[2]
        per_class_acc = cm.diagonal() / cm.sum(axis=1)
        colors = ["#2ecc71" if a >= 0.9 else "#f39c12" if a >= 0.7 else "#e74c3c" for a in per_class_acc]
        bars = ax3.barh(range(len(intents)), per_class_acc, color=colors, height=0.6)
        ax3.set_yticks(range(len(intents)))
        ax3.set_yticklabels(intents, fontsize=8)
        ax3.set_xlim(0, 1.05)
        ax3.set_title("Per-Class Accuracy", fontsize=13)
        ax3.set_xlabel("Accuracy")
        ax3.axvline(0.9, color="green", linestyle="--", alpha=0.4, label="90%")
        ax3.axvline(0.98, color="orange", linestyle="--", alpha=0.4, label="98%")
        ax3.legend(fontsize=8)
        for bar, acc in zip(bars, per_class_acc):
            ax3.text(acc + 0.01, bar.get_y() + bar.get_height() / 2, f"{acc:.1%}",
                     va="center", fontsize=7)

        plt.tight_layout()
        plot_path = os.path.join(_MODEL_DIR, "training_result.png")
        fig.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  📊 可视化结果已保存: {plot_path}")

        # 打印分类报告
        report = classification_report(y_encoded, y_pred, target_names=intents, digits=4)
        print(f"\n  分类报告:\n{report}")

    except ImportError:
        print("  ⚠️ matplotlib 未安装，跳过可视化")
    except Exception as e:
        print(f"  ⚠️ 可视化失败: {e}")

    # ---------- 6. 保存模型 ----------
    print("\n[6/6] 保存模型到磁盘...")
    os.makedirs(_MODEL_DIR, exist_ok=True)

    with open(_MODEL_PATH, "wb") as f:
        pickle.dump(mlp, f)
    with open(_ENCODER_PATH, "wb") as f:
        pickle.dump(label_encoder, f)

    print(f"  💾 mlp.pkl          → {_MODEL_PATH}")
    print(f"  💾 label_encoder.pkl → {_ENCODER_PATH}")

    # ---------- 7. 保存预计算 embeddings（加速系统启动） ----------
    print("\n[7/7] 保存预计算 embeddings（加速系统启动）...")
    _EMBEDDINGS_PATH = os.path.join(_MODEL_DIR, "intent_embeddings.npz")
    save_dict = {}
    for i, intent in enumerate(intents):
        save_dict[intent] = X_list[i]
    np.savez_compressed(_EMBEDDINGS_PATH, **save_dict)
    print(f"  💾 intent_embeddings.npz → {_EMBEDDINGS_PATH}")
    print(f"     共 {len(intents)} 个意图，{sum(e.shape[0] for e in X_list)} 条预编码向量")
    print(f"{'=' * 60}")
    print(f"  ✅ 全部完成！共 {len(intents)} 类，{X.shape[0]} 样本")
    print(f"  📁 模型已保存到: {_MODEL_DIR}")
    if os.path.exists(os.path.join(_MODEL_DIR, "training_result.png")):
        print(f"  📊 可视化结果: {os.path.join(_MODEL_DIR, 'training_result.png')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
