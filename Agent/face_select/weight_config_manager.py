"""
weight_config_manager.py - 权重配置管理器

集中管理所有与专注度判断、情绪影响、综合评分等相关的可调权重。
提供线程安全的读写操作，支持 JSON 持久化，运行时动态生效。

管理端可通过 /admin/weights/* 接口实时查看和修改这些权重。
"""

import json
import os
import threading
import copy
from typing import Dict, Any, Optional


# ==================== 默认权重配置 ====================

DEFAULT_WEIGHTS: Dict[str, Any] = {

    # ---------- 沉浸信号分权重 (attention_tracker.py) ----------
    "attention_tracker": {
        "immersion_weights": {
            "focus_score": 0.40,         # 注视专注度权重
            "distraction_penalty": 0.25, # 分心负分权重
            "head_stability": 0.20,      # 头部稳定性权重
            "duration_score": 0.15,      # 时长分权重
        },
        "distraction_additional_penalty": 0.2,  # 额外分心扣分系数
        "meaningful_distraction_threshold": 3,  # 有意义分心的连续帧阈值
        "max_deviation_for_focus": 0.3,         # 注视专注度归一化阈值
        "duration_seconds_for_full_score": 15,  # 时长分达到满分的秒数
    },

    # ---------- 情绪影响权重 (emotion_state_mapper.py) ----------
    "emotion_state_mapper": {
        "emotion_impact_weights": {
            "happy": {
                "interest_level": 0.3,
                "frustration_tolerance": 0.2,
                "anxiety_level": -0.4,
                "confidence_level": 0.3
            },
            "neutral": {
                "interest_level": 0.0,
                "frustration_tolerance": 0.0,
                "anxiety_level": 0.0,
                "confidence_level": 0.0
            },
            "surprise": {
                "interest_level": 0.2,
                "frustration_tolerance": -0.1,
                "anxiety_level": 0.3,
                "confidence_level": -0.1
            },
            "sad": {
                "interest_level": -0.4,
                "frustration_tolerance": -0.3,
                "anxiety_level": 0.3,
                "confidence_level": -0.4
            },
            "angry": {
                "interest_level": -0.5,
                "frustration_tolerance": -0.5,
                "anxiety_level": 0.4,
                "confidence_level": -0.3
            },
            "fear": {
                "interest_level": -0.3,
                "frustration_tolerance": -0.4,
                "anxiety_level": 0.6,
                "confidence_level": -0.5
            },
            "disgust": {
                "interest_level": -0.4,
                "frustration_tolerance": -0.3,
                "anxiety_level": 0.2,
                "confidence_level": -0.2
            }
        },
        "impact_multiplier": 10,              # 情绪影响乘以该值后累加到子维度
        "dimension_bounds": {"min": -50, "max": 150},  # 子维度内部计算范围
        "score_delta_weights": {              # score 变化量中各维度的权重
            "interest": 0.3,
            "frustration": 0.2,
            "anxiety": 0.3,     # 注意：anxiety 是负向
            "confidence": 0.2
        },
        "emotion_baseline": {                 # 各情绪类型的基准值
            "happy": {"interest": 75, "frustration": 70, "anxiety": 25, "confidence": 75},
            "surprise": {"interest": 65, "frustration": 50, "anxiety": 45, "confidence": 55},
            "neutral": {"interest": 50, "frustration": 50, "anxiety": 50, "confidence": 50},
            "sad": {"interest": 35, "frustration": 35, "anxiety": 65, "confidence": 35},
            "angry": {"interest": 30, "frustration": 30, "anxiety": 70, "confidence": 40},
            "fear": {"interest": 35, "frustration": 30, "anxiety": 80, "confidence": 30},
            "disgust": {"interest": 30, "frustration": 35, "anxiety": 60, "confidence": 35}
        }
    },

    # ---------- 综合专注度评分权重 (attention_bridge.py) ----------
    "attention_bridge": {
        "composite_score_max": 100,
        "base_score": 50,
        "immersion_max_contribution": 40,
        "distraction_max_contribution": 20,
        "valence_positive_bonus": 8,
        "valence_negative_penalty": -8,
        "confidence_min_multiplier": 0.9,
        "confidence_max_multiplier_factor": 0.1,
        "valence_positive_ratio": 1.5,    # positive 判定阈值倍数
        "valence_negative_ratio": 1.5,    # negative 判定阈值倍数
        "score_levels": [
            {"threshold": 80, "label": "高专注"},
            {"threshold": 60, "label": "中等"},
            {"threshold": 40, "label": "低专注"},
            {"threshold": 0,  "label": "分心严重"}
        ]
    },

    # ---------- 瞌睡检测权重 (gaze_detector.py) ----------
    "gaze_detector": {
        "drowsiness_weights": {
            "head_down": 0.6,      # 低头时间占比权重
            "recent_yawn": 0.3,    # 最近打哈欠权重
            "abnormal_blink": 0.1  # 眨眼频率异常权重
        },
        "head_down_angle_threshold": 15,      # 低头判定角度阈值（度）
        "yawn_cooldown_seconds": 300,         # 打哈欠检测冷却时间（秒）
        "blink_rate_low_threshold": 5,        # 眨眼频率下限（次/分钟）
        "blink_rate_high_threshold": 30,      # 眨眼频率上限（次/分钟）
        "drowsiness_score_threshold": 0.45    # 瞌睡判定阈值
    }
}


# ==================== 持久化文件路径 ====================

_WEIGHTS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "custom_weights.json"
)
_DEFAULT_WEIGHTS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "default_weights.json"
)


# ==================== 线程安全存储 ====================

_lock = threading.Lock()
_current_weights: Dict[str, Any] = {}
_initialized = False


def _ensure_data_dir():
    """确保 data 目录存在"""
    data_dir = os.path.dirname(_WEIGHTS_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)


def _load_from_disk() -> Dict[str, Any]:
    """从磁盘加载权重配置，若文件不存在则返回 None"""
    if os.path.exists(_WEIGHTS_FILE):
        try:
            with open(_WEIGHTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_to_disk(weights: Dict[str, Any]):
    """持久化权重配置到磁盘"""
    _ensure_data_dir()
    try:
        with open(_WEIGHTS_FILE, "w", encoding="utf-8") as f:
            json.dump(weights, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WeightConfig] 持久化权重失败: {e}")


def _init():
    """初始化权重配置（首次加载时调用）"""
    global _current_weights, _initialized
    if _initialized:
        return

    # 先保存一份默认配置到独立文件（供前端 schema 参考）
    _ensure_data_dir()
    try:
        with open(_DEFAULT_WEIGHTS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_WEIGHTS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # 尝试加载用户自定义配置
    custom = _load_from_disk()
    if custom:
        # 合并：以自定义配置覆盖默认值的对应字段
        merged = _deep_merge(copy.deepcopy(DEFAULT_WEIGHTS), custom)
        _current_weights = merged
        print(f"[WeightConfig] 已加载自定义权重配置")
    else:
        _current_weights = copy.deepcopy(DEFAULT_WEIGHTS)
        print(f"[WeightConfig] 使用默认权重配置")

    _initialized = True


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典，override 覆盖 base"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


# ==================== 公开 API ====================

def get_weights(category: Optional[str] = None) -> Dict[str, Any]:
    """
    获取当前权重配置

    Args:
        category: 分类名（attention_tracker / emotion_state_mapper / attention_bridge / gaze_detector）
                  若为 None 则返回全部配置

    Returns:
        Dict: 权重配置的深拷贝，防止外部修改
    """
    with _lock:
        if not _initialized:
            _init()
        if category:
            return copy.deepcopy(_current_weights.get(category, {}))
        return copy.deepcopy(_current_weights)


def get_weight(category: str, *keys: str) -> Any:
    """
    获取具体某个权重的值

    Args:
        category: 分类名
        keys: 嵌套键路径，如 get_weight("attention_tracker", "immersion_weights", "focus_score")

    Returns:
        权重的值（原始引用，不拷贝），若不存在返回 None
    """
    with _lock:
        if not _initialized:
            _init()
        section = _current_weights.get(category)
        if section is None:
            return None
        current = section
        for k in keys:
            if isinstance(current, dict):
                current = current.get(k)
                if current is None:
                    return None
            else:
                return None
        return current


def update_weights(category: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新指定分类的权重配置

    Args:
        category: 分类名
        updates: 要更新的键值对（支持嵌套更新）

    Returns:
        Dict: 更新后的完整权重配置

    Raises:
        ValueError: 分类名不存在
    """
    with _lock:
        if not _initialized:
            _init()
        if category not in _current_weights:
            raise ValueError(f"未知的权重分类: {category}，可选: {list(_current_weights.keys())}")

        # 深度合并更新
        _deep_merge(_current_weights[category], updates)

        # 持久化
        _save_to_disk(_current_weights)

        return copy.deepcopy(_current_weights[category])


def reset_weights(category: Optional[str] = None) -> Dict[str, Any]:
    """
    重置权重配置为默认值

    Args:
        category: 分类名，若为 None 则重置全部

    Returns:
        Dict: 重置后的配置
    """
    with _lock:
        if not _initialized:
            _init()
        if category:
            if category in DEFAULT_WEIGHTS:
                _current_weights[category] = copy.deepcopy(DEFAULT_WEIGHTS[category])
            else:
                raise ValueError(f"未知的权重分类: {category}")
        else:
            _current_weights = copy.deepcopy(DEFAULT_WEIGHTS)

        # 持久化
        _save_to_disk(_current_weights)

        return copy.deepcopy(_current_weights.get(category) if category else _current_weights)


def get_weight_schema() -> Dict[str, Any]:
    """
    获取权重配置的完整结构（包含默认值和分类说明）

    Returns:
        Dict: 带注释的完整配置结构
    """
    schema = {
        "description": "专注度判断与学习状态识别权重配置管理",
        "categories": {
            "attention_tracker": {
                "description": "沉浸信号分权重（attention_tracker.py）",
                "fields": {
                    "immersion_weights": "注视专注度/分心负分/头部稳定性/时长分 的加权系数，总和应为1.0",
                    "distraction_additional_penalty": "有意义分心率额外扣分系数",
                    "meaningful_distraction_threshold": "连续多少帧分心才算有意义分心",
                    "max_deviation_for_focus": "注视专注度归一化阈值，偏移越大专注越低",
                    "duration_seconds_for_full_score": "超过该秒数的学习时长即可获得满分"
                },
                "defaults": DEFAULT_WEIGHTS.get("attention_tracker", {})
            },
            "emotion_state_mapper": {
                "description": "情绪影响权重（emotion_state_mapper.py）",
                "fields": {
                    "emotion_impact_weights": "各情绪类型对各子维度的影响系数",
                    "impact_multiplier": "情绪影响值乘以该系数后累加到子维度数值",
                    "dimension_bounds": "子维度内部计算范围的上下限",
                    "score_delta_weights": "各子维度变化量在综合评分中的权重",
                    "emotion_baseline": "各情绪类型对应的默认子维度基准值"
                },
                "defaults": DEFAULT_WEIGHTS.get("emotion_state_mapper", {})
            },
            "attention_bridge": {
                "description": "综合专注度评分权重（attention_bridge.py）",
                "fields": {
                    "composite_score_max": "综合评分最大值",
                    "base_score": "基础分",
                    "immersion_max_contribution": "沉浸信号最大贡献分",
                    "distraction_max_contribution": "分心比率最大贡献分",
                    "valence_positive_bonus": "积极情绪加分",
                    "valence_negative_penalty": "消极情绪减分",
                    "confidence_min_multiplier": "置信度最小乘数",
                    "score_levels": "评分等级分段"
                },
                "defaults": DEFAULT_WEIGHTS.get("attention_bridge", {})
            },
            "gaze_detector": {
                "description": "瞌睡检测权重（gaze_detector.py）",
                "fields": {
                    "drowsiness_weights": "瞌睡检测各因素权重",
                    "head_down_angle_threshold": "低头判定角度阈值",
                    "yawn_cooldown_seconds": "打哈欠冷却时间",
                    "blink_rate_low_threshold": "眨眼频率下限",
                    "blink_rate_high_threshold": "眨眼频率上限"
                },
                "defaults": DEFAULT_WEIGHTS.get("gaze_detector", {})
            }
        },
        "all_defaults": copy.deepcopy(DEFAULT_WEIGHTS)
    }
    return schema
