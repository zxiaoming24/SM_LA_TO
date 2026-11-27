"""
attention_tracker.py - 注意力追踪与沉浸信号计算

职责：
1. 管理资源页面会话（enter/leave）
2. 基于眼动数据计算"沉浸信号分"
3. 将会话结果写入 AttentionProfile（来自 children_agent 推荐系统）

沉浸信号分 (0~1) 构成：
  0.40 × 注视专注度 + 0.25 × 分心负分 + 0.20 × 头部稳定性 + 0.15 × 时长分

用法:
    tracker = AttentionTracker()
    tracker.on_enter("user_001", "video", kp="循环结构")
    tracker.add_gaze("user_001", 0.02, 0.03, 0, 0, False)
    result = tracker.on_leave("user_001")
    print(result["immersion_score"])
"""

import time
import math
from typing import Dict, Any, Optional, List
from collections import deque

# 加载动态权重配置
from weight_config_manager import get_weight


def _get_attention_profile(user_id: str):
    """延迟加载 AttentionProfile，避免启动时导入失败"""
    from Agent.children_agent.recommendation.attention_profile import get_profile
    return get_profile(user_id)


class AttentionSession:
    """一次资源页面的注视会话"""

    def __init__(self, user_id: str, resource_type: str,
                 resource_id: str = "", knowledge_point: str = ""):
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.knowledge_point = knowledge_point
        self.start_time = time.time()
        self.gaze_records: deque = deque()   #  使用双端队列  主要用于实时处理   远比之前使用的普通队列List 速度更快
        self._max_records = 9000  # ★★★ 限制最大记录数（≈5分钟@30fps）★★★

    def add_gaze_frame(self, gaze_offset_x: float, gaze_offset_y: float,
                       head_pitch: float = 0.0, head_yaw: float = 0.0,
                       is_distracted: bool = False,
                       timestamp: Optional[float] = None):
        """记录一帧眼动数据"""
        self.gaze_records.append({
            "gaze_x": gaze_offset_x,
            "gaze_y": gaze_offset_y,
            "head_pitch": head_pitch,
            "head_yaw": head_yaw,
            "is_distracted": is_distracted,
            "timestamp": timestamp or time.time()
        })
        # ★★★ 限制列表大小，避免无限增长 ★★★
        while len(self.gaze_records) > self._max_records:
            self.gaze_records.popleft()  #  之前是List配合使用的pop 之前的pop实现方式是移动一个元素后续全动（使用的是内存的连续性），但是popleft  它维护了 left 和 right 两个指针。执行 popleft() 时，只需要把 left 指针指向第二个节点，然后把第一个节点的前/后指针置空即可。  复杂度为o(1)

    def close(self) -> Dict:
        """
        结束会话，计算沉浸信号分

        Returns:
            { immersion_score, valid, details, ... }
        """
        if not self.gaze_records:
            return {"immersion_score": 0.5, "valid": False,
                    "reason": "无数据", "duration": 0}

        timestamps = [r["timestamp"] for r in self.gaze_records
                      if r["timestamp"] is not None]
        if len(timestamps) >= 2:
            duration = timestamps[-1] - timestamps[0]
        else:
            duration = 0

        if duration < 1.0:
            return {"immersion_score": 0.5, "valid": False,
                    "reason": f"数据时长不足({duration:.2f}s < 1s)",
                    "duration": round(duration, 1),
                    "frames": len(self.gaze_records)}

        # ---------- 计算各项指标 ----------

        # 1. 注视专注度：gaze_offset 越接近0越专注
        max_deviation = get_weight("attention_tracker", "max_deviation_for_focus") or 0.3
        deviations = [math.sqrt(r["gaze_x"]**2 + r["gaze_y"]**2)
                      for r in self.gaze_records]
        avg_deviation = sum(deviations) / len(deviations)
        focus_score = max(0.0, 1.0 - (avg_deviation / max_deviation))

        # 2. 分心负分（只统计"有意义分心"——连续 N 帧以上的分心才算）
        min_consecutive = get_weight("attention_tracker", "meaningful_distraction_threshold") or 3
        raw_distracted = [r["is_distracted"] for r in self.gaze_records]
        meaningful_distracted = 0
        consecutive = 0
        for d in raw_distracted:
            if d:
                consecutive += 1
            else:
                if consecutive >= min_consecutive:
                    meaningful_distracted += consecutive
                consecutive = 0
        if consecutive >= min_consecutive:
            meaningful_distracted += consecutive

        total_meaningful = meaningful_distracted
        distraction_ratio = total_meaningful / len(self.gaze_records) if len(self.gaze_records) > 0 else 0
        distraction_penalty = max(0.0, 1.0 - distraction_ratio * 2)

        # 3. 头部稳定性
        pitches = [r["head_pitch"] for r in self.gaze_records]
        yaws = [r["head_yaw"] for r in self.gaze_records]
        pitch_std = self._std(pitches)
        yaw_std = self._std(yaws)
        head_stability = max(0.0, 1.0 - ((pitch_std + yaw_std) / 2 / 10.0))

        # 4. 时长分（N秒及以上满分）
        full_score_duration = get_weight("attention_tracker", "duration_seconds_for_full_score") or 15.0
        duration_score = min(duration / full_score_duration, 1.0)

        # 加权基础分（动态权重）
        iw = get_weight("attention_tracker", "immersion_weights") or {}
        immersion_score = (
            (iw.get("focus_score", 0.40)) * focus_score +
            (iw.get("distraction_penalty", 0.25)) * distraction_penalty +
            (iw.get("head_stability", 0.20)) * head_stability +
            (iw.get("duration_score", 0.15)) * duration_score
        )

        # 分心负向偏移
        add_penalty = get_weight("attention_tracker", "distraction_additional_penalty") or 0.2
        immersion_score -= distraction_ratio * add_penalty
        immersion_score = max(0.0, min(1.0, immersion_score))

        details = {
            "duration": round(duration, 1),
            "frames": len(self.gaze_records),
            "avg_deviation": round(avg_deviation, 4),
            "focus_score": round(focus_score, 3),
            "raw_distracted": sum(raw_distracted),
            "meaningful_distracted": total_meaningful,
            "distraction_ratio": round(distraction_ratio, 3),
            "distraction_penalty": round(distraction_penalty, 3),
            "head_stability": round(head_stability, 3),
            "duration_score": round(duration_score, 3),
            "immersion_score": round(immersion_score, 3),
        }

        return {"immersion_score": immersion_score, "valid": True,
                "details": details, "duration": round(duration, 1)}

    @staticmethod
    def _std(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(var)


class AttentionTracker:
    """
    注意力追踪器（管理用户当前会话）

    管理用户的 AttentionSession，在 on_leave 时自动计算沉浸信号
    并调用 AttentionProfile.update_preference() 持久化。
    """

    def __init__(self):
        self._sessions: Dict[str, AttentionSession] = {}

    def on_enter(self, user_id: str, resource_type: str,
                 resource_id: str = "", knowledge_point: str = "") -> bool:
        """用户进入一个资源页面，开始追踪注意力"""
        if user_id in self._sessions:
            old = self._sessions.pop(user_id)
            old.close()
        self._sessions[user_id] = AttentionSession(
            user_id, resource_type, resource_id, knowledge_point)
        return True

    def add_gaze(self, user_id: str, gaze_offset_x: float, gaze_offset_y: float,
                 head_pitch: float = 0.0, head_yaw: float = 0.0,
                 is_distracted: bool = False,
                 timestamp: Optional[float] = None) -> bool:
        """记录一帧眼动数据到当前会话"""
        session = self._sessions.get(user_id)
        if session is None:
            return False
        session.add_gaze_frame(gaze_offset_x, gaze_offset_y,
                               head_pitch, head_yaw, is_distracted,
                               timestamp=timestamp)
        return True

    def on_leave(self, user_id: str) -> Optional[Dict]:
        """
        用户离开资源页面。

        计算沉浸信号分，更新 AttentionProfile。

        Returns:
            { immersion_score, valid, details, profile_update, ... }
            如果无活跃会话返回 None
        """
        session = self._sessions.pop(user_id, None)
        if session is None:
            return None

        result = session.close()

        if result["valid"]:
            try:
                profile = _get_attention_profile(session.user_id)
                update_info = profile.update_preference(
                    session.resource_type, result["immersion_score"])
                result["profile_update"] = update_info
            except Exception:
                result["profile_update"] = None
            result["resource_type"] = session.resource_type
            result["knowledge_point"] = session.knowledge_point

        return result

    def get_current_session(self, user_id: str) -> Optional[Dict]:
        """获取当前会话的摘要信息"""
        session = self._sessions.get(user_id)
        if session is None:
            return None
        return {
            "resource_type": session.resource_type,
            "resource_id": session.resource_id,
            "elapsed": round(time.time() - session.start_time, 1),
            "frames": len(session.gaze_records),
        }

    def has_active_session(self, user_id: str) -> bool:
        return user_id in self._sessions
