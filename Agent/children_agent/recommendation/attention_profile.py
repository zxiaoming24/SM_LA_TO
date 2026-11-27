"""
attention_profile.py - 用户注意力偏好画像

核心功能：
1. 管理用户对各资源类型的偏好分数（指数滑动平均）
2. 置信度机制（数据量少时趋于中性）
3. JSON 持久化

偏好分数范围：0.0 ~ 1.0
- >0.6 偏好
- 0.4~0.6 中性
- <0.4 不偏好

用法:
    from .attention_profile import get_profile
    profile = get_profile("user_001")
    prefs = profile.get_effective_preferences()
    # {'video': 0.66, 'doc': 0.46, 'practice': 0.45, ...}
    
    # 也可以直接获取按偏好扩容后的资源类型列表
    types = profile.get_weighted_resource_types(base_types=['video','doc','practice'])
    # -> ['video', 'video', 'doc', 'practice']  (偏好的类型多一次)
"""

import os
import json
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path


# 默认存储路径（与 PhaseBridge 共用）—— 使用项目根目录的绝对路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # Agent/children_agent/recommendation/ → 项目根目录
DEFAULT_STORAGE_DIR = _PROJECT_ROOT / "data" / "attention_profiles"


class AttentionProfile:
    """
    用户注意力偏好画像
    """

    RESOURCE_TYPES = ["video", "practice", "doc", "mindmap", "extension", "animation"]
    DEFAULT_ALPHA = 0.3
    STABLE_ALPHA = 0.15
    CONFIDENCE_BASELINE = 3  # 降低门槛，3次即置信度1.0

    def __init__(self, user_id: str, storage_dir: Optional[Path] = None):
        self.user_id = user_id
        self.storage_dir = storage_dir or DEFAULT_STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.preferences: Dict[str, float] = {t: 0.5 for t in self.RESOURCE_TYPES}
        self.total_sessions: int = 0
        self.type_sessions: Dict[str, int] = {t: 0 for t in self.RESOURCE_TYPES}
        self.last_updated: str = ""

        self._load()

    def update_preference(self, resource_type: str, immersion_score: float) -> Dict:
        """用一次观测到的沉浸信号更新偏好（指数滑动平均）"""
        if resource_type not in self.preferences:
            resource_type = self._best_match(resource_type)

        old_score = self.preferences.get(resource_type, 0.5)

        self.type_sessions[resource_type] = self.type_sessions.get(resource_type, 0) + 1
        self.total_sessions += 1

        alpha = self.DEFAULT_ALPHA if self.total_sessions < 20 else self.STABLE_ALPHA
        new_score = alpha * immersion_score + (1 - alpha) * old_score
        new_score = max(0.0, min(1.0, new_score))

        self.preferences[resource_type] = new_score
        self.last_updated = datetime.now().isoformat()
        self._save()

        return {
            "resource_type": resource_type,
            "old_score": round(old_score, 3),
            "new_score": round(new_score, 3),
            "immersion_score": round(immersion_score, 3),
            "confidence": self.get_confidence(resource_type),
        }

    def get_effective_preferences(self) -> Dict[str, float]:
        """获取生效偏好（考虑置信度），置信度低时趋向 0.5"""
        effective = {}
        for rtype in self.RESOURCE_TYPES:
            conf = self.get_confidence(rtype)
            raw = self.preferences.get(rtype, 0.5)
            effective[rtype] = round(raw * conf + 0.5 * (1 - conf), 3)
        return effective

    def get_weighted_resource_types(self, base_types: List[str] = None,
                                     extra_slots: int = 2,
                                     remove_below: float = 0.45) -> List[str]:
        """
        根据偏好对资源类型扩容，极低偏好的直接移除

        Args:
            base_types: 基础资源类型列表，如 ['video','doc','practice']
            extra_slots: 额外分配的总槽位数
            remove_below: 低于此阈值则直接移除该类型（默认 0.45）

        Returns:
            扩容后的资源类型列表，如 ['video','video','doc','practice']
        """
        if not base_types:
            base_types = ["video", "doc", "practice"]

        effective = self.get_effective_preferences()

        # 1. 先过滤掉极低偏好的类型
        filtered = [t for t in base_types if effective.get(t, 0.5) >= remove_below]

        # 2. 如果全部被过滤了（极端情况），保留最高的一个兜底
        if not filtered:
            sorted_types = sorted(
                [(t, effective.get(t, 0.5)) for t in base_types],
                key=lambda x: x[1], reverse=True
            )
            filtered = [sorted_types[0][0]]

        # 3. 每个类型至少 1 个
        result = list(filtered)

        # 4. 额外分配
        relevant = {t: effective.get(t, 0.5) for t in filtered}
        total_pref = sum(relevant.values())

        if total_pref <= 0:
            return result

        sorted_types = sorted(relevant.items(), key=lambda x: x[1], reverse=True)
        remaining = extra_slots

        for rtype, pref in sorted_types:
            if remaining <= 0:
                break
            raw_count = extra_slots * (pref / total_pref)
            count = max(0, round(raw_count))
            count = min(count, remaining)
            result.extend([rtype] * count)
            remaining -= count

        return result

    def get_confidence(self, resource_type: str) -> float:
        count = self.type_sessions.get(resource_type, 0)
        return min(count / self.CONFIDENCE_BASELINE, 1.0)

    def get_overall_confidence(self) -> float:
        return min(self.total_sessions / (self.CONFIDENCE_BASELINE * 2), 1.0)

    def get_summary(self) -> Dict:
        effective = self.get_effective_preferences()
        sorted_prefs = sorted(effective.items(), key=lambda x: x[1], reverse=True)
        return {
            "user_id": self.user_id,
            "preferences": {k: round(v, 3) for k, v in self.preferences.items()},
            "effective": effective,
            "confidence": {k: round(self.get_confidence(k), 3) for k in self.RESOURCE_TYPES},
            "total_sessions": self.total_sessions,
            "type_sessions": self.type_sessions,
            "last_updated": self.last_updated,
            "overall_confidence": round(self.get_overall_confidence(), 3),
            "top_type": sorted_prefs[0][0] if sorted_prefs else "unknown",
        }

    def reset(self):
        self.preferences = {t: 0.5 for t in self.RESOURCE_TYPES}
        self.type_sessions = {t: 0 for t in self.RESOURCE_TYPES}
        self.total_sessions = 0
        self.last_updated = ""
        self._save()

    def _best_match(self, resource_type: str) -> str:
        rtype_lower = resource_type.lower()
        # 别名映射
        alias = {"question": "practice", "ppt": "doc", "pptx": "doc"}
        if rtype_lower in alias:
            return alias[rtype_lower]
        for t in self.RESOURCE_TYPES:
            if t in rtype_lower or rtype_lower in t:
                return t
        return "doc"

    def _save(self):
        path = self._get_path()
        data = {
            "user_id": self.user_id,
            "preferences": self.preferences,
            "total_sessions": self.total_sessions,
            "type_sessions": self.type_sessions,
            "last_updated": self.last_updated,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        path = self._get_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.preferences.update(data.get("preferences", {}))
                self.total_sessions = data.get("total_sessions", 0)
                self.type_sessions.update(data.get("type_sessions", {}))
                self.last_updated = data.get("last_updated", "")
                for t in self.RESOURCE_TYPES:
                    self.preferences.setdefault(t, 0.5)
                    self.type_sessions.setdefault(t, 0)
            except (json.JSONDecodeError, KeyError):
                pass

    def _get_path(self) -> Path:
        return self.storage_dir / f"{self.user_id}.json"


_profile_cache: Dict[str, AttentionProfile] = {}

def get_profile(user_id: str) -> AttentionProfile:
    if user_id not in _profile_cache:
        _profile_cache[user_id] = AttentionProfile(user_id)
    return _profile_cache[user_id]
