"""
attention_profile.py - 用户注意力偏好画像（测试版）

核心功能：
1. 管理用户对各资源类型的偏好分数（指数滑动平均）
2. 置信度机制（数据量少时趋于中性）
3. JSON 持久化（存储在本地）

偏好分数范围：0.0 ~ 1.0
- >0.6 偏好
- 0.4~0.6 中性
- <0.4 不偏好
"""

import os
import json
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path


class AttentionProfile:
    """
    用户注意力偏好画像

    用法:
        profile = AttentionProfile("test_user_01")
        profile.update_preference("video", 0.78)
        profile.update_preference("doc", 0.35)
        prefs = profile.get_effective_preferences()
    """

    RESOURCE_TYPES = ["video", "practice", "doc", "mindmap", "extension", "animation"]
    DEFAULT_ALPHA = 0.3        # 新用户（快速学习）
    STABLE_ALPHA = 0.15        # 有足够数据后（平稳更新）
    CONFIDENCE_BASELINE = 10   # 多少次行为后置信度=1

    def __init__(self, user_id: str, storage_dir: Optional[Path] = None):
        self.user_id = user_id
        self.storage_dir = storage_dir or Path("./attention_profiles")
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

    def get_confidence(self, resource_type: str) -> float:
        """获取某资源类型的置信度 (0~1)"""
        count = self.type_sessions.get(resource_type, 0)
        return min(count / self.CONFIDENCE_BASELINE, 1.0)

    def get_overall_confidence(self) -> float:
        """获取整体置信度"""
        return min(self.total_sessions / (self.CONFIDENCE_BASELINE * 2), 1.0)

    def get_summary(self) -> Dict:
        """获取可读的偏好摘要"""
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
        """重置偏好（测试用）"""
        self.preferences = {t: 0.5 for t in self.RESOURCE_TYPES}
        self.type_sessions = {t: 0 for t in self.RESOURCE_TYPES}
        self.total_sessions = 0
        self.last_updated = ""
        self._save()

    def _best_match(self, resource_type: str) -> str:
        rtype_lower = resource_type.lower()
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


# 全局缓存
_profile_cache: Dict[str, AttentionProfile] = {}

def get_profile(user_id: str) -> AttentionProfile:
    if user_id not in _profile_cache:
        _profile_cache[user_id] = AttentionProfile(user_id)
    return _profile_cache[user_id]
