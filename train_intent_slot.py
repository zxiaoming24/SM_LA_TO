"""
槽位意图分类器训练脚本（独立实验）

与 train_intent_classifier.py 的区别：
    1. 使用 slot_intent_examples.py 的模板（而非原 INTENT_EXAMPLES）
    2. 训练前用 expand_templates() 把 <CREATE>/<PLAN> 等槽位随机展开为真实动作词
    3. 训练样本量自动扩大 repeats 倍（覆盖"生成/制作/合成/搞一个"等动作词变体）
    4. 保存到独立目录 user_features/intent_slot_model/，不覆盖原模型

核心收益：
    - 动作词泛化：训练时见过"生成PPT""合成PPT""搞一个PPT"，推理时即使用户说没见过的"弄个PPT"
      也能命中（因为所有动作词在 BGE 嵌入空间里都共享同一个核心名词"PPT"）

用法:
    python train_intent_slot.py
    python train_intent_slot.py --repeats 5       # 每个模板展开 5 条
    python train_intent_slot.py --seed 123

输出:
    user_features/intent_slot_model/
        ├── mlp.pkl
        ├── label_encoder.pkl
        ├── intent_embeddings.npz
        ├── slot_config.pkl             # 槽位配置（推理时复用）
        └── training_result.png
"""

import os
import sys
import pickle
import random
import argparse
import numpy as np

# ★★★ 必须在任何 huggingface 相关 import 之前设置镜像 ★★★
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# ★★★ 控制台编码 ★★★
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ★★★ 项目根目录加入 sys.path ★★★
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

# ★★★ 独立模型保存路径 ★★★
_MODEL_DIR = os.path.join(_PROJECT_ROOT, "user_features", "intent_slot_model")
_MODEL_PATH = os.path.join(_MODEL_DIR, "mlp.pkl")
_ENCODER_PATH = os.path.join(_MODEL_DIR, "label_encoder.pkl")
_EMBEDDINGS_PATH = os.path.join(_MODEL_DIR, "intent_embeddings.npz")
_SLOT_CONFIG_PATH = os.path.join(_MODEL_DIR, "slot_config.pkl")


def load_embedding_model():
    """加载 BGE 嵌入模型。
    优先从 ModelScope 缓存目录直接加载（项目实际下载位置），
    避免每次都走 snapshot_download 检查。
    """
    print("\n[2] 加载语义嵌入模型 BAAI/bge-base-zh-v1.5...")
    from sentence_transformers import SentenceTransformer

    # ★ 项目实际从 ModelScope 下载，缓存在 .cache_models/models/BAAI--bge-base-zh-v1.5/snapshots/master/
    _MODELSCOPE_CACHE = os.path.join(
        _PROJECT_ROOT, ".cache_models", "models", "BAAI--bge-base-zh-v1.5", "snapshots", "master"
    )

    model = None

    # 尝试 1：直接从 ModelScope 已知缓存路径加载（最快，无网络开销）
    if os.path.exists(_MODELSCOPE_CACHE):
        try:
            model = SentenceTransformer(_MODELSCOPE_CACHE, local_files_only=True)
            print(f"  ✅ 从 ModelScope 本地缓存加载成功")
            print(f"     路径: {_MODELSCOPE_CACHE}")
        except Exception as e:
            print(f"  ⚠️ ModelScope 缓存路径存在但加载失败: {e}")

    # 尝试 2：HuggingFace 默认本地缓存
    if model is None:
        try:
            model = SentenceTransformer("BAAI/bge-base-zh-v1.5", local_files_only=True)
            print("  ✅ 从 HuggingFace 本地缓存加载成功")
        except Exception:
            pass

    # 尝试 3：ModelScope 在线下载（首次安装时走这里）
    if model is None:
        try:
            from modelscope import snapshot_download
            print("  ⏳ 尝试从 ModelScope 下载...")
            local_path = snapshot_download(
                "BAAI/bge-base-zh-v1.5",
                cache_dir=os.path.join(_PROJECT_ROOT, ".cache_models"),
            )
            model = SentenceTransformer(local_path)
            print("  ✅ 从 ModelScope 下载成功")
        except ImportError:
            print("  ℹ️  modelscope 未安装，跳过")
        except Exception as e:
            print(f"  ⚠️  ModelScope 下载失败: {e}")

    # 尝试 4：HuggingFace 镜像（兜底）
    if model is None:
        try:
            print("  ⏳ 尝试从 hf-mirror.com 下载...")
            model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
            print("  ✅ 从 HuggingFace 镜像下载成功")
        except Exception as e:
            print(f"  ❌ 所有下载源均失败: {e}")
            raise RuntimeError("无法下载 bge-base-zh-v1.5 模型")

    print("  ✅ 模型加载完成")
    return model


def main():
    parser = argparse.ArgumentParser(description="槽位意图分类器训练")
    parser.add_argument("--repeats", type=int, default=3,
                        help="每个模板展开为多少条样本（默认 3）")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子（默认 42）")
    args = parser.parse_args()

    print("=" * 60)
    print("  槽位意图分类器训练（独立实验）")
    print(f"  repeats={args.repeats}  seed={args.seed}")
    print("=" * 60)

    # ---------- 1. 加载槽位模板并展开 ----------
    print("\n[1] 加载并展开槽位模板...")
    from slot_intent_examples import (
        SLOT_INTENT_EXAMPLES,
        SLOT_VARIANTS,
        expand_templates,
        fill_slots,
    )

    intents = sorted(SLOT_INTENT_EXAMPLES.keys())
    total_templates = sum(len(v) for v in SLOT_INTENT_EXAMPLES.values())
    print(f"  → {len(intents)} 个意图，{total_templates} 条原始模板")

    expanded = expand_templates(rng_seed=args.seed, repeats=args.repeats)
    total_samples = sum(len(v) for v in expanded.values())
    print(f"  → 展开后 {total_samples} 条训练样本（{args.repeats}x 扩展）")

    # 各意图样本数
    print(f"\n  各意图样本数:")
    for intent in intents:
        n_template = len(SLOT_INTENT_EXAMPLES[intent])
        n_expanded = len(expanded[intent])
        print(f"    {intent:<20} 模板={n_template:3d}  展开={n_expanded:3d}")

    # ---------- 2. 加载嵌入模型 ----------
    model = load_embedding_model()

    # ---------- 3. 编码所有样本 ----------
    print(f"\n[3] 编码展开后的训练样本...")
    X_list, y_list = [], []
    for intent in intents:
        sentences = expanded[intent]
        embs = model.encode(sentences, normalize_embeddings=True, show_progress_bar=True)
        X_list.append(embs)
        y_list.extend([intent] * len(sentences))

    X = np.vstack(X_list)
    y = np.array(y_list)
    print(f"  → 训练集形状: X={X.shape}, y={y.shape}")

    # ---------- 4. 训练 MLP ----------
    print(f"\n[4] 训练 MLP 分类头 (512 → 256 → 128 → {len(intents)})...")
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.utils.class_weight import compute_sample_weight
    import sklearn as _sk

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    # ★ MLPClassifier 不支持 class_weight 参数（issue #9113 至今未实现）
    # 用 compute_sample_weight('balanced', y) 在 fit() 时传入 sample_weight 实现等价效果
    _mlp_kwargs = dict(
        hidden_layer_sizes=(256, 128),
        activation="relu",
        max_iter=2000,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        verbose=True,
    )
    mlp = MLPClassifier(**_mlp_kwargs)

    # 计算每个样本的权重（少数类样本权重更高）
    sample_w = compute_sample_weight("balanced", y_encoded)
    print(f"  ✅ sklearn {_sk.__version__}，使用 sample_weight='balanced'（等效 class_weight）")

    # 打印各类权重示意
    import numpy as _np
    _unique_classes, _class_counts = _np.unique(y_encoded, return_counts=True)
    _class_sample_w = [_np.mean(sample_w[y_encoded == c]) for c in _unique_classes]
    print(f"  各类样本数 / 权重示意:")
    for _cls_idx, _cls_name in enumerate(label_encoder.classes_):
        _cnt = _class_counts[_cls_idx]
        _w = _class_sample_w[_cls_idx]
        print(f"    {_cls_name:<20} 样本={_cnt:4d}  权重={_w:.3f}")

    mlp.fit(X, y_encoded, sample_weight=sample_w)

    train_acc = mlp.score(X, y_encoded)
    print(f"  ✅ 训练完成 | 共 {mlp.n_iter_} 轮 | 训练集准确率: {train_acc:.2%}")

    # ---------- 5. 可视化 ----------
    print(f"\n[5] 可视化训练结果...")
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

        from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report

        y_pred = mlp.predict(X)
        intents_display = [c.replace("_", "\n") for c in intents]

        fig, axes = plt.subplots(1, 3, figsize=(20, 6))

        # 图1: Loss 曲线
        ax1 = axes[0]
        ax1.plot(mlp.loss_curve_, linewidth=1.5)
        ax1.set_title("Training Loss Curve", fontsize=13)
        ax1.set_xlabel("Iteration")
        ax1.set_ylabel("Loss")
        ax1.grid(True, alpha=0.3)
        ax1.axvline(mlp.n_iter_, color="red", linestyle="--", alpha=0.5, label=f"stop={mlp.n_iter_}")
        ax1.legend()

        # 图2: 混淆矩阵
        cm = confusion_matrix(y_encoded, y_pred)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=intents_display)
        disp.plot(ax=axes[1], cmap="Blues", colorbar=False, values_format="d")
        axes[1].set_title("Confusion Matrix (Slot)", fontsize=13)
        axes[1].tick_params(axis="x", rotation=45, labelsize=7)
        axes[1].tick_params(axis="y", labelsize=7)

        # 图3: 每类准确率
        ax3 = axes[2]
        per_class_acc = cm.diagonal() / cm.sum(axis=1)
        colors = ["#2ecc71" if a >= 0.9 else "#f39c12" if a >= 0.7 else "#e74c3c" for a in per_class_acc]
        bars = ax3.barh(range(len(intents)), per_class_acc, color=colors, height=0.6)
        ax3.set_yticks(range(len(intents)))
        ax3.set_yticklabels(intents, fontsize=8)
        ax3.set_xlim(0, 1.05)
        ax3.set_title("Per-Class Accuracy (Slot)", fontsize=13)
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
        print(f"  📊 可视化结果: {plot_path}")

        report = classification_report(y_encoded, y_pred, target_names=intents, digits=4)
        print(f"\n  分类报告:\n{report}")

    except ImportError:
        print("  ⚠️ matplotlib 未安装，跳过可视化")
    except Exception as e:
        print(f"  ⚠️ 可视化失败: {e}")

    # ---------- 6. 保存模型 ----------
    print(f"\n[6] 保存模型到磁盘...")
    os.makedirs(_MODEL_DIR, exist_ok=True)

    with open(_MODEL_PATH, "wb") as f:
        pickle.dump(mlp, f)
    with open(_ENCODER_PATH, "wb") as f:
        pickle.dump(label_encoder, f)

    # ★ 保存槽位配置（推理时需要用同样的 fill_slots 做归一化）★
    slot_config = {
        "SLOT_VARIANTS": SLOT_VARIANTS,
        "fill_strategy": "first",  # 推理时用 first 策略（确定性）
    }
    with open(_SLOT_CONFIG_PATH, "wb") as f:
        pickle.dump(slot_config, f)

    print(f"  💾 mlp.pkl              → {_MODEL_PATH}")
    print(f"  💾 label_encoder.pkl    → {_ENCODER_PATH}")
    print(f"  💾 slot_config.pkl      → {_SLOT_CONFIG_PATH}")

    # ---------- 7. 保存预计算 embeddings ----------
    print(f"\n[7] 保存预计算 embeddings...")
    save_dict = {}
    for i, intent in enumerate(intents):
        save_dict[intent] = X_list[i]
    np.savez_compressed(_EMBEDDINGS_PATH, **save_dict)
    print(f"  💾 intent_embeddings.npz → {_EMBEDDINGS_PATH}")
    print(f"     共 {len(intents)} 个意图，{sum(e.shape[0] for e in X_list)} 条预编码向量")

    print(f"\n{'=' * 60}")
    print(f"  ✅ 全部完成！")
    print(f"  📁 模型: {_MODEL_DIR}")
    print(f"  📊 混淆矩阵: {os.path.join(_MODEL_DIR, 'training_result.png')}")
    print(f"  💡 对比测试: python test_intent_slot.py")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
