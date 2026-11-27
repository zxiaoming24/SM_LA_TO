"""
专注度数据桥接模块 - 为评估系统提供统一的专注度、情绪、分心数据接口

整合 face-select 模块的所有感知数据：
1. 专注度数据（视线追踪、沉浸信号）
2. 情绪数据（YOLO情绪检测）
3. 分心数据（分心检测、瞌睡检测）
4. 头部姿态数据（俯仰角、偏航角）
"""
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta

from weight_config_manager import get_weight


class AttentionBridge:
    """专注度数据桥接器 - 连接face-select和评估系统"""
    
    def __init__(self):
        self._history_dir = Path("./data/attention_history")
        self._emotion_dir = Path("./data/emotion_history")
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._emotion_dir.mkdir(parents=True, exist_ok=True)
    
    def get_comprehensive_summary(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户综合感知数据摘要，包含：
        - 专注度偏好（资源类型偏好）
        - 最近专注度历史
        - 最近情绪历史
        - 分心统计
        """
        try:
            result = {
                "status": "success",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            }
            
            # 1. 获取注意力偏好画像
            try:
                from Agent.children_agent.recommendation.attention_profile import get_profile
                profile = get_profile(user_id)
                summary = profile.get_summary()
                result["attention_preferences"] = {
                    "preferences": summary.get("effective", {}),
                    "overall_confidence": summary.get("overall_confidence", 0),
                    "total_sessions": summary.get("total_sessions", 0),
                    "last_updated": summary.get("last_updated", ""),
                    "top_resource_type": summary.get("top_type", "unknown"),
                }
            except Exception as e:
                result["attention_preferences"] = {
                    "error": str(e)
                }
            
            # 2. 获取最近专注度历史
            result["recent_attention"] = self._get_recent_attention(user_id)
            
            # 3. 获取最近情绪历史
            result["recent_emotions"] = self._get_recent_emotions(user_id)
            
            # 4. 获取分心统计
            result["distraction_stats"] = self._get_distraction_stats(user_id)
            
            # 5. 计算综合专注度评分
            result["composite_score"] = self._calculate_composite_score(result)
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _get_recent_attention(self, user_id: str, hours: int = 24) -> Dict[str, Any]:
        """获取最近N小时的专注度历史"""
        history_file = self._history_dir / f"{user_id}.json"
        if not history_file.exists():
            return {"status": "no_history"}
        
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"status": "error", "message": "读取历史失败"}
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).timestamp()
        recent = [r for r in records if r.get("timestamp", 0) >= cutoff_time]
        
        if not recent:
            return {"status": "no_recent_data"}
        
        # 计算统计
        total_sessions = len(recent)
        avg_immersion = sum(r.get("immersion_score", 0) for r in recent) / total_sessions
        avg_duration = sum(r.get("duration", 0) for r in recent) / total_sessions
        total_distracted = sum(r.get("meaningful_distracted", 0) for r in recent)
        total_frames = sum(r.get("frames", 0) for r in recent)
        distraction_ratio = total_distracted / max(total_frames, 1)
        
        return {
            "status": "success",
            "hours_window": hours,
            "total_sessions": total_sessions,
            "avg_immersion_score": round(avg_immersion, 3),
            "avg_duration_seconds": round(avg_duration, 1),
            "distraction_ratio": round(distraction_ratio, 3),
            "latest_session": recent[-1] if recent else None,
        }
    
    def _get_recent_emotions(self, user_id: str, hours: int = 24) -> Dict[str, Any]:
        """获取最近N小时的情绪历史"""
        emotion_file = self._emotion_dir / f"{user_id}.json"
        if not emotion_file.exists():
            return {"status": "no_history"}
        
        try:
            with open(emotion_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"status": "error", "message": "读取情绪历史失败"}
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).timestamp()
        recent = [r for r in records if r.get("timestamp", 0) >= cutoff_time]
        
        if not recent:
            return {"status": "no_recent_data"}
        
        # 统计各情绪出现频率
        emotion_counts = {}
        total_confidence = {}
        
        for record in recent:
            emotion_type = record.get("emotion", "unknown")
            confidence = record.get("confidence", 0)
            
            emotion_counts[emotion_type] = emotion_counts.get(emotion_type, 0) + 1
            total_confidence[emotion_type] = total_confidence.get(emotion_type, 0) + confidence
        
        # 计算主导情绪
        total_count = len(recent)
        dominant_emotion = max(
            emotion_counts.items(),
            key=lambda x: x[1] * (total_confidence[x[0]] / x[1])
        ) if emotion_counts else ("neutral", 0)
        
        dominant_type = dominant_emotion[0]
        dominant_avg_conf = total_confidence.get(dominant_type, 0) / max(emotion_counts.get(dominant_type, 1), 1)
        
        # 计算整体效价
        positive_emotions = ['happy']
        negative_emotions = ['angry', 'disgust', 'fear', 'sad']
        
        positive_weight = sum(
            (emotion_counts.get(e, 0) / total_count) * (total_confidence.get(e, 0) / max(emotion_counts.get(e, 1), 1))
            for e in positive_emotions
        )
        negative_weight = sum(
            (emotion_counts.get(e, 0) / total_count) * (total_confidence.get(e, 0) / max(emotion_counts.get(e, 1), 1))
            for e in negative_emotions
        )
        
        overall_valence = "positive" if positive_weight > negative_weight * 1.5 else \
                         "negative" if negative_weight > positive_weight * 1.5 else "neutral"
        
        return {
            "status": "success",
            "hours_window": hours,
            "total_detections": total_count,
            "dominant_emotion": {
                "type": dominant_type,
                "avg_confidence": round(dominant_avg_conf, 3),
                "percentage": round((emotion_counts.get(dominant_type, 0) / total_count) * 100, 2),
            },
            "emotion_distribution": {
                emotion: {
                    "count": count,
                    "percentage": round((count / total_count) * 100, 2),
                    "avg_confidence": round(total_confidence[emotion] / count, 3),
                }
                for emotion, count in emotion_counts.items()
            },
            "overall_valence": overall_valence,
            "latest_emotion": recent[-1] if recent else None,
        }
    
    def _get_distraction_stats(self, user_id: str, hours: int = 24) -> Dict[str, Any]:
        """获取分心统计数据"""
        history_file = self._history_dir / f"{user_id}.json"
        if not history_file.exists():
            return {"status": "no_history"}
        
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except:
            return {"status": "error", "message": "读取历史失败"}
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).timestamp()
        recent = [r for r in records if r.get("timestamp", 0) >= cutoff_time]
        
        if not recent:
            return {"status": "no_recent_data"}
        
        # 计算分心统计
        total_sessions = len(recent)
        sessions_with_distraction = sum(1 for r in recent if r.get("meaningful_distracted", 0) > 0)
        
        total_raw_distracted = sum(r.get("raw_distracted", 0) for r in recent)
        total_meaningful_distracted = sum(r.get("meaningful_distracted", 0) for r in recent)
        total_frames = sum(r.get("frames", 0) for r in recent)
        
        avg_distraction_ratio = total_meaningful_distracted / max(total_frames, 1)
        distraction_rate = sessions_with_distraction / total_sessions
        
        # 获取最近的分心详情
        recent_distractions = []
        for record in recent[-5:]:
            if record.get("meaningful_distracted", 0) > 0:
                recent_distractions.append({
                    "timestamp": record.get("datetime", ""),
                    "resource_type": record.get("resource_type", ""),
                    "distraction_ratio": record.get("distraction_ratio", 0),
                })
        
        return {
            "status": "success",
            "hours_window": hours,
            "total_sessions": total_sessions,
            "sessions_with_distraction": sessions_with_distraction,
            "distraction_rate": round(distraction_rate, 3),
            "avg_distraction_ratio": round(avg_distraction_ratio, 3),
            "total_raw_distracted_frames": total_raw_distracted,
            "total_meaningful_distracted_frames": total_meaningful_distracted,
            "recent_distractions": recent_distractions,
        }
    
    def _calculate_composite_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算综合专注度评分（0-100）
        
        评分构成（权重可从管理端动态调整）：
        - immersion_max_contribution 沉浸信号分（注意力质量）
        - valence_positive_bonus / valence_negative_penalty 情绪效价
        - distraction_max_contribution 分心比率
        - confidence_min_multiplier / confidence_max_multiplier_factor 置信度修正
        """
        cfg = get_weight("attention_bridge") or {}
        score = cfg.get("base_score", 50)
        score_max = cfg.get("composite_score_max", 100)
        
        immersion_max = cfg.get("immersion_max_contribution", 40)
        distraction_max = cfg.get("distraction_max_contribution", 20)
        valence_bonus = cfg.get("valence_positive_bonus", 8)
        valence_penalty = cfg.get("valence_negative_penalty", -8)
        conf_min_mul = cfg.get("confidence_min_multiplier", 0.9)
        conf_mul_factor = cfg.get("confidence_max_multiplier_factor", 0.1)
        
        immersion_score_val = 0.5
        valence = "neutral"
        avg_distraction_ratio = 0
        
        # 1. 沉浸信号分
        attention = data.get("recent_attention", {})
        if attention.get("status") == "success":
            immersion_score_val = attention.get("avg_immersion_score", 0.5)
            score += immersion_score_val * immersion_max
        
        # 2. 情绪效价
        emotions = data.get("recent_emotions", {})
        if emotions.get("status") == "success":
            valence = emotions.get("overall_valence", "neutral")
            if valence == "positive":
                score += valence_bonus
            elif valence == "negative":
                score += valence_penalty
        
        # 3. 分心比率
        distraction = data.get("distraction_stats", {})
        if distraction.get("status") == "success":
            avg_distraction_ratio = distraction.get("avg_distraction_ratio", 0)
            score += (1 - avg_distraction_ratio) * distraction_max
        
        # 4. 置信度修正
        preferences = data.get("attention_preferences", {})
        confidence = preferences.get("overall_confidence", 0)
        score *= (conf_min_mul + confidence * conf_mul_factor)
        
        # 限制范围
        score = max(0, min(score_max, score))
        
        # 确定等级（从配置读取分段）
        levels = cfg.get("score_levels", [
            {"threshold": 80, "label": "高专注"},
            {"threshold": 60, "label": "中等"},
            {"threshold": 40, "label": "低专注"},
            {"threshold": 0,  "label": "分心严重"}
        ])
        level = "未知"
        for lv in sorted(levels, key=lambda x: x["threshold"], reverse=True):
            if score >= lv["threshold"]:
                level = lv["label"]
                break
        
        return {
            "score": round(score, 1),
            "level": level,
            "components": {
                "immersion_contribution": round(immersion_score_val * immersion_max, 1),
                "emotion_contribution": valence_bonus if valence == "positive" else (valence_penalty if valence == "negative" else 0),
                "distraction_contribution": round((1 - avg_distraction_ratio) * distraction_max, 1),
                "confidence_multiplier": round(conf_min_mul + confidence * conf_mul_factor, 2),
            }
        }
    
    def record_session(self, user_id: str, session_data: Dict[str, Any]):
        """
        记录一次专注度会话
        
        Args:
            user_id: 用户ID
            session_data: 会话数据，包含：
                - resource_type: 资源类型
                - immersion_score: 沉浸信号分
                - duration: 会话时长（秒）
                - frames: 总帧数
                - raw_distracted: 原始分心帧数
                - meaningful_distracted: 有意义分心帧数
                - distraction_ratio: 分心比率
                - knowledge_point: 关联知识点（可选）
        """
        history_file = self._history_dir / f"{user_id}.json"
        
        # ★★★ 修复：加文件锁，避免多进程并发写覆盖 ★★★
        import portalocker
        with portalocker.Lock(history_file, timeout=5) as fh:
            records = []
            if history_file.exists():
                try:
                    records = json.load(fh)  #  读取所有数据
                except:
                    pass
            record = {
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "user_id": user_id,
                **session_data
            }
            records.append(record)  #  追加
            records = records[-200:]
            fh.seek(0)  #  文件指针回到开头
            fh.truncate()  # 清空原内容
            json.dump(records, fh, ensure_ascii=False, indent=2)  #  重新写入--这就导致了在前面需要清空（解释为什么不使用open(history_file, "w")这样直接进行覆盖！ 因为当前使用文件锁的情况会导致锁作用域混乱  
            # 现在的做法（r+ 模式打开，先读后写）是在持有锁的同一个文件句柄（fh）上完成读写，确保整个“读-改-写”过程是原子性的，不会被其他进程打断
    
    def record_emotion(self, user_id: str, emotion_data: Dict[str, Any]):
        """
        记录一次情绪检测结果
        
        Args:
            user_id: 用户ID
            emotion_data: 情绪数据，包含：
                - emotion: 情绪类型（happy/neutral/sad/angry/fear/disgust/surprise）
                - confidence: 置信度
                - valence: 效价（positive/negative/neutral）
                - arousal: 唤醒度（high/medium/low）
        """
        emotion_file = self._emotion_dir / f"{user_id}.json"
        
        # ★★★ 修复：加文件锁，避免多进程并发写覆盖 ★★★
        import portalocker
        with portalocker.Lock(emotion_file, timeout=5) as fh:
            records = []
            if emotion_file.exists():
                try:
                    records = json.load(fh)
                except:
                    pass
            record = {
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "user_id": user_id,
                **emotion_data
            }
            records.append(record)
            records = records[-500:]
            fh.seek(0)
            fh.truncate()
            json.dump(records, fh, ensure_ascii=False, indent=2)
    
    def get_latest_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取最近一次专注度会话"""
        history_file = self._history_dir / f"{user_id}.json"
        if not history_file.exists():
            return None
        
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            return records[-1] if records else None
        except:
            return None
    
    def get_latest_emotion(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取最近一次情绪检测结果"""
        emotion_file = self._emotion_dir / f"{user_id}.json"
        if not emotion_file.exists():
            return None
        
        try:
            with open(emotion_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            return records[-1] if records else None
        except:
            return None
