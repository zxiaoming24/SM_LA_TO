"""
时间维度管理服务 - 独立管理用户时间管理维度的数据

核心功能：
1. 学习打卡：传入 user_id + duration_seconds，根据等级标准自动更新
2. 查询当前时间维度数据
3. 查询变更历史
4. 生成时间管理分析报告

数据来源：复用 DynamicFeatureUpdater 的中央特征管理进行读写

等级标准（基于单次学习时长）：
  Lv.0 未学习    = 0s       → score: 0
  Lv.1 短暂      = 10min    → score: 15
  Lv.2 短时      = 30min    → score: 35
  Lv.3 基础      = 1h       → score: 55
  Lv.4 有效      = 1.5h     → score: 70
  Lv.5 高效      = 2h       → score: 85
  Lv.6 优秀      = 3h       → score: 95
  Lv.7 卓越      = 3h+      → score: 100
"""

import copy
from typing import Dict, Any
from datetime import datetime


# ──────────────────────────────────────────────
# 时长 → 等级/分数 映射表（单位：秒）
# ──────────────────────────────────────────────
# (阈值秒数, 对应分数, 等级标签, 描述)
DURATION_LEVELS = [
    (0, 0, "未学习", "今日尚未开始学习"),
    (600, 15, "短暂", "学习时间不足10分钟"),
    (1800, 35, "短时", "学习时间约30分钟"),
    (3600, 55, "基础", "学习时间约1小时"),
    (5400, 70, "有效", "学习时间约1.5小时"),
    (7200, 85, "高效", "学习时间约2小时"),
    (10800, 95, "优秀", "学习时间约3小时"),
]

# 3 小时以上额外处理
MAX_LEVEL_SCORE = 100
MAX_LEVEL_LABEL = "卓越"
MAX_DURATION = 10800  # 3小时

# 时间管理维度的字段定义
TIME_DIMENSION_FIELDS = {
    "learning_regularity": "学习规律性",
    "priority_judgment": "优先级判断",
    "procrastination_tendency": "拖延倾向",
    "time_allocation_efficiency": "时间分配效率",
}

# 默认值模板
DEFAULT_TIME_DIMENSION = {
    "learning_regularity": "信息不足",
    "priority_judgment": "信息不足",
    "procrastination_tendency": "信息不足",
    "time_allocation_efficiency": "信息不足",
    "score": 0,
    "today_duration": 0,       # 今日累计学习时长（秒）
    "last_checkin_date": "",    # 最后打卡日期
}


def _get_updater():
    """获取 DynamicFeatureUpdater 单例"""
    from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
    return DynamicFeatureUpdater()


def _duration_to_score(duration_seconds: int) -> Dict[str, Any]:
    """
    将学习时长（秒）映射为分数和等级

    采用阶梯映射 + 区间内线性插值，保证变化平滑
    """
    if duration_seconds >= MAX_DURATION:
        extra = (duration_seconds - MAX_DURATION) / MAX_DURATION
        extra_score = min(5, int(extra * 5))
        return {
            "score": min(MAX_LEVEL_SCORE, MAX_LEVEL_SCORE - 5 + extra_score),
            "level_label": MAX_LEVEL_LABEL,
            "level_description": "学习时间超过3小时，表现卓越",
        }

    for i in range(len(DURATION_LEVELS) - 1):
        lower_sec, lower_score, lower_label, lower_desc = DURATION_LEVELS[i]
        upper_sec, upper_score, upper_label, upper_desc = DURATION_LEVELS[i + 1]

        if lower_sec <= duration_seconds < upper_sec:
            if upper_sec == lower_sec:
                score = lower_score
            else:
                ratio = (duration_seconds - lower_sec) / (upper_sec - lower_sec)
                score = lower_score + int(ratio * (upper_score - lower_score))

            return {
                "score": score,
                "level_label": lower_label,
                "level_description": lower_desc,
            }

    return {"score": 0, "level_label": "未学习", "level_description": "未开始学习"}


def _duration_to_readable(seconds: int) -> str:
    """将秒数转换为可读的时间字符串"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if secs > 0 and hours == 0:
        parts.append(f"{secs}秒")
    return "".join(parts) if parts else "0秒"


def _score_to_smooth_target(current_score: int, session_score: int, update_count: int) -> int:
    """
    使用指数移动平均平滑更新分数，避免单次剧烈波动
    """
    alpha = max(0.2, min(0.8, 1.0 / (1 + update_count * 0.1)))
    new_score = current_score * (1 - alpha) + session_score * alpha
    return max(0, min(100, int(round(new_score))))


# ──────────────────────────────────────────────
# 核心业务方法（均复用 DynamicFeatureUpdater）
# ──────────────────────────────────────────────

def check_in(user_id: str, duration_seconds: int) -> Dict[str, Any]:
    """
    学习打卡 - 传入学习时长（秒），自动更新时间管理维度

    通过 DynamicFeatureUpdater 进行：
      - get_latest_features() 读取当前特征
      - update_and_save_features() 持久化特征（含锁、原子写入、ChromaDB 同步）
      - append_update_history() 记录时间维度专属历史

    Args:
        user_id: 用户ID
        duration_seconds: 本次学习时长（秒）

    Returns:
        Dict: 更新后的时间维度数据和本次打卡信息
    """
    if duration_seconds is None or duration_seconds < 0:
        raise ValueError(f"duration_seconds 不能为负数，当前值: {duration_seconds}")
    if not isinstance(duration_seconds, (int, float)):
        raise ValueError(f"duration_seconds 必须为数字，当前类型: {type(duration_seconds)}")

    duration_seconds = int(duration_seconds)

    # 1. 通过 DynamicFeatureUpdater 获取当前特征
    updater = _get_updater()
    features = updater.get_latest_features(user_id)
    if not features:
        raise FileNotFoundError(f"用户 {user_id} 的特征不存在")

    # 2. 获取当前 time_management 数据
    old_time_dim = copy.deepcopy(features.get("time_management", {}))
    if not old_time_dim:
        old_time_dim = dict(DEFAULT_TIME_DIMENSION)
        old_time_dim["score"] = 0
        old_time_dim["today_duration"] = 0

    # 3. 计算本次时长对应的分数和等级
    level_info = _duration_to_score(duration_seconds)
    session_score = level_info["score"]
    session_label = level_info["level_label"]
    readable_duration = _duration_to_readable(duration_seconds)

    # 4. 处理今日累计时长
    today = datetime.now().strftime("%Y-%m-%d")
    is_new_day = old_time_dim.get("last_checkin_date", "") != today
    if is_new_day:
        accumulated_duration = duration_seconds
    else:
        accumulated_duration = old_time_dim.get("today_duration", 0) + duration_seconds

    # 5. 根据累计时长计算目标分数
    target_level_info = _duration_to_score(accumulated_duration)
    target_score = target_level_info["score"]

    # 6. 平滑更新分数
    update_count = old_time_dim.get("_update_count", 0)
    current_score = old_time_dim.get("score", 0)
    new_score = _score_to_smooth_target(current_score, target_score, update_count)

    # 7. 构建新的 time_management 数据
    new_time_dim = copy.deepcopy(old_time_dim)
    new_time_dim["score"] = new_score
    new_time_dim["today_duration"] = accumulated_duration
    new_time_dim["last_checkin_date"] = today
    new_time_dim["_update_count"] = update_count + 1

    # 更新 learning_regularity
    if accumulated_duration >= 7200:
        new_time_dim["learning_regularity"] = f"规律（今日累计学习{_duration_to_readable(accumulated_duration)}）"
    elif accumulated_duration >= 3600:
        new_time_dim["learning_regularity"] = f"较规律（今日累计学习{_duration_to_readable(accumulated_duration)}）"
    elif accumulated_duration >= 1800:
        new_time_dim["learning_regularity"] = f"一般（今日累计学习{_duration_to_readable(accumulated_duration)}）"
    else:
        new_time_dim["learning_regularity"] = f"不足（今日累计学习{_duration_to_readable(accumulated_duration)}）"

    # 更新 time_allocation_efficiency
    if accumulated_duration >= 5400:
        new_time_dim["time_allocation_efficiency"] = "高效（单次学习时长充足）"
    elif accumulated_duration >= 1800:
        new_time_dim["time_allocation_efficiency"] = "一般（建议增加学习时长）"
    else:
        new_time_dim["time_allocation_efficiency"] = "待提升（学习时长偏短）"

    # 8. 写入特征文件（通过 DynamicFeatureUpdater）
    features["time_management"] = new_time_dim

    # 同步更新 summary_scores
    if "summary_scores" in features:
        dim_scores = features["summary_scores"].get("dimension_scores", [])
        if len(dim_scores) == 8:
            dim_scores[6] = new_score
            features["summary_scores"]["dimension_scores"] = dim_scores
            features["summary_scores"]["overall_score"] = sum(dim_scores) // 8

    # 9. 记录时间维度专用历史（通过 append_update_history）
    update_record = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "dimension": "time_management",
        "action": "check_in",
        "change_reason": f"学习打卡：本次{readable_duration}，今日累计{_duration_to_readable(accumulated_duration)}",
        "duration_seconds": duration_seconds,
        "accumulated_duration": accumulated_duration,
        "session_level": session_label,
        "session_score": session_score,
        "old_values": {k: v for k, v in old_time_dim.items() if k != "_update_count"},
        "new_values": {k: v for k, v in new_time_dim.items() if k != "_update_count"},
        "changed_fields": ["score", "learning_regularity", "time_allocation_efficiency", "today_duration"],
    }
    updater.append_update_history(user_id, update_record)

    # 10. 通过中央管理器保存（含锁、原子写入、ChromaDB）
    metadata = {
        "task_type": "time_check_in",
        "source": "time_dimension_service",
        "evidence_quality": "high",
        "timestamp": datetime.now().isoformat(),
    }
    updater.update_and_save_features(
        user_id=user_id,
        updated_features=features,
        update_metadata=metadata,
    )

    return {
        "success": True,
        "user_id": user_id,
        "action": "check_in",
        "check_in": {
            "duration_seconds": duration_seconds,
            "accumulated_duration": accumulated_duration,
            "duration_readable": readable_duration,
            "accumulated_readable": _duration_to_readable(accumulated_duration),
            "session_level": session_label,
            "session_score": session_score,
        },
        "time_dimension": {k: v for k, v in new_time_dim.items() if k != "_update_count"},
        "score_change": {
            "old_score": current_score,
            "new_score": new_score,
            "delta": new_score - current_score,
        },
        "update_record": update_record,
    }
