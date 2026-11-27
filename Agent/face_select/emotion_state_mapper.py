"""
情绪分析结果处理器
将YOLO情绪检测结果转换为8维度特征中的emotional_state维度更新
"""

import json
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

from weight_config_manager import get_weight


class EmotionStateMapper:
    """情绪状态映射器 - 将实时情绪检测结果映射到8维度特征的emotional_state"""
    
    # YOLO情绪类别到中文描述的映射
    EMOTION_MAP = {
        'angry': {'chinese': '愤怒', 'valence': 'negative', 'arousal': 'high'},
        'disgust': {'chinese': '厌恶', 'valence': 'negative', 'arousal': 'medium'},
        'fear': {'chinese': '恐惧', 'valence': 'negative', 'arousal': 'high'},
        'happy': {'chinese': '快乐', 'valence': 'positive', 'arousal': 'medium'},
        'neutral': {'chinese': '中性', 'valence': 'neutral', 'arousal': 'low'},
        'sad': {'chinese': '悲伤', 'valence': 'negative', 'arousal': 'low'},
        'surprise': {'chinese': '惊讶', 'valence': 'neutral', 'arousal': 'high'}
    }
    
    # 情绪基线值 fallback（当动态配置无对应情绪类型时使用）
    EMOTION_BASELINE_FALLBACK = {
        'happy': {'interest': 60, 'frustration': 40, 'anxiety': 30, 'confidence': 70},
        'neutral': {'interest': 50, 'frustration': 50, 'anxiety': 50, 'confidence': 50},
        'surprise': {'interest': 70, 'frustration': 40, 'anxiety': 60, 'confidence': 40},
        'sad': {'interest': 30, 'frustration': 60, 'anxiety': 70, 'confidence': 30},
        'angry': {'interest': 40, 'frustration': 80, 'anxiety': 60, 'confidence': 50},
        'fear': {'interest': 30, 'frustration': 50, 'anxiety': 80, 'confidence': 20},
        'disgust': {'interest': 30, 'frustration': 70, 'anxiety': 50, 'confidence': 40}
    }

    # 情绪对emotional_state各子维度的影响权重
    EMOTION_IMPACT_WEIGHTS = {
        'happy': {
            'interest_level': +0.3,      # 兴趣水平提升
            'frustration_tolerance': +0.2,  # 挫折承受力提升
            'anxiety_level': -0.4,       # 焦虑水平降低
            'confidence_level': +0.3     # 自信心提升
        },
        'neutral': {
            'interest_level': 0.0,
            'frustration_tolerance': 0.0,
            'anxiety_level': 0.0,
            'confidence_level': 0.0
        },
        'surprise': {
            'interest_level': +0.2,      # ★★★ 适度提升兴趣（好奇）★★★
            'frustration_tolerance': -0.1,
            'anxiety_level': +0.3,       # ★★★ 增加焦虑 ★★★
            'confidence_level': -0.1
        },
        'sad': {
            'interest_level': -0.4,      # 兴趣降低
            'frustration_tolerance': -0.3,
            'anxiety_level': +0.3,       # 焦虑增加
            'confidence_level': -0.4     # 自信降低
        },
        'angry': {
            'interest_level': -0.5,      # 兴趣大幅降低
            'frustration_tolerance': -0.5,  # 挫折承受力降低
            'anxiety_level': +0.4,       # 焦虑增加
            'confidence_level': -0.3
        },
        'fear': {
            'interest_level': -0.3,
            'frustration_tolerance': -0.4,
            'anxiety_level': +0.6,       # 焦虑大幅增加
            'confidence_level': -0.5     # 自信大幅降低
        },
        'disgust': {
            'interest_level': -0.4,
            'frustration_tolerance': -0.3,
            'anxiety_level': +0.2,
            'confidence_level': -0.2
        }
    }
    
    def __init__(self):
        """初始化情绪状态映射器"""
        self.emotion_history = []  # 存储历史情绪检测结果
        self.window_size = 10  # 滑动窗口大小（最近10次检测）
        
    def process_emotion_detection(
        self, 
        emotion_data: List[Dict[str, Any]],
        current_features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理单次情绪检测结果
        
        Args:
            emotion_data: YOLO情绪检测结果列表，格式如:
                [
                    {
                        "emotion": "surprise",
                        "confidence": 0.705,
                        "bbox": [237, 156, 370, 320],
                        "centroid": [303, 238],
                        "size": {"width": 133, "height": 164}
                    }
                ]
            current_features: 当前8维度特征（可选）
            
        Returns:
            Dict: 包含情绪分析和对emotional_state维度影响的字典
        """
        if not emotion_data:
            return {
                "status": "no_detection",
                "message": "未检测到情绪",
                "emotional_state_impact": None
            }
        
        # 取置信度最高的情绪
        dominant_emotion = max(emotion_data, key=lambda x: x.get('confidence', 0))
        emotion_type = dominant_emotion.get('emotion', 'neutral')
        confidence = dominant_emotion.get('confidence', 0)
        
        # 记录到历史
        self.emotion_history.append({
            'timestamp': time.time(),
            'emotion': emotion_type,
            'confidence': confidence
        })
        
        # 保持窗口大小
        if len(self.emotion_history) > self.window_size:
            self.emotion_history = self.emotion_history[-self.window_size:]
        
        # 计算对emotional_state各子维度的影响
        impact = self._calculate_dimension_impact(emotion_type, confidence)
        
        # ★★★ 关键修复：即使没有当前特征，也生成默认的情绪状态更新 ★★★
        if current_features and 'emotional_state' in current_features:
            # 有当前特征，基于现有值更新
            emotional_state_update = self._update_emotional_state_score(
                current_features['emotional_state'],
                impact
            )
        else:
            # 没有当前特征，生成基于情绪的默认值
            emotional_state_update = self._generate_default_emotional_state(emotion_type, confidence)
        
        result = {
            "status": "success",
            "detected_emotion": {
                "type": emotion_type,
                "chinese_name": self.EMOTION_MAP.get(emotion_type, {}).get('chinese', '未知'),
                "confidence": confidence,
                "valence": self.EMOTION_MAP.get(emotion_type, {}).get('valence', 'neutral'),
                "arousal": self.EMOTION_MAP.get(emotion_type, {}).get('arousal', 'low')
            },
            "dimension_impact": impact,
            "emotional_state_update": emotional_state_update,
            "recommendation": self._generate_recommendation(emotion_type, confidence)
        }
        
        return result
    
    def aggregate_emotions_over_time(
        self,
        time_window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        聚合时间窗口内的情绪数据
        
        Args:
            time_window_seconds: 时间窗口（秒）
            
        Returns:
            Dict: 聚合后的情绪统计
        """
        if not self.emotion_history:
            return {
                "status": "no_data",
                "message": "无历史情绪数据"
            }
        
        current_time = time.time()
        window_start = current_time - time_window_seconds
        
        # 过滤时间窗口内的数据
        recent_emotions = [
            e for e in self.emotion_history
            if e['timestamp'] >= window_start
        ]
        
        if not recent_emotions:
            return {
                "status": "no_recent_data",
                "message": f"最近{time_window_seconds}秒内无情绪数据"
            }
        
        # 统计各情绪出现频率和平均置信度
        emotion_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})
        
        for entry in recent_emotions:
            emotion = entry['emotion']
            conf = entry['confidence']
            emotion_stats[emotion]['count'] += 1
            emotion_stats[emotion]['total_confidence'] += conf
        
        # 计算主导情绪
        total_count = len(recent_emotions)
        dominant_emotion = max(
            emotion_stats.items(),
            key=lambda x: x[1]['count'] * (x[1]['total_confidence'] / x[1]['count'])
        )
        
        dominant_type = dominant_emotion[0]
        dominant_avg_conf = dominant_emotion[1]['total_confidence'] / dominant_emotion[1]['count']
        
        # 计算情绪分布
        emotion_distribution = {
            emotion: {
                'percentage': stats['count'] / total_count * 100,
                'avg_confidence': stats['total_confidence'] / stats['count']
            }
            for emotion, stats in emotion_stats.items()
        }
        
        # 计算整体效价和唤醒度
        overall_valence = self._calculate_overall_valence(emotion_distribution)
        overall_arousal = self._calculate_overall_arousal(emotion_distribution)
        
        return {
            "status": "success",
            "time_window": time_window_seconds,
            "total_detections": total_count,
            "dominant_emotion": {
                "type": dominant_type,
                "chinese_name": self.EMOTION_MAP.get(dominant_type, {}).get('chinese', '未知'),
                "avg_confidence": round(dominant_avg_conf, 3),
                "percentage": round(emotion_distribution[dominant_type]['percentage'], 2)
            },
            "emotion_distribution": emotion_distribution,
            "overall_valence": overall_valence,
            "overall_arousal": overall_arousal,
            "trend_analysis": self._analyze_trend(recent_emotions)
        }
    
    def _get_dynamic_emotion_weights(self, emotion_type: str) -> Dict[str, float]:
        """从动态配置中获取情绪影响权重，找不到则 fallback 到 EMOTION_IMPACT_WEIGHTS"""
        all_weights = get_weight("emotion_state_mapper", "emotion_impact_weights") or {}
        dynamic = all_weights.get(emotion_type)
        if dynamic is not None:
            return dynamic
        return self.EMOTION_IMPACT_WEIGHTS.get(emotion_type, {})

    def _get_dynamic_emotion_baseline(self, emotion_type: str) -> Dict[str, float]:
        """从动态配置中获取情绪基线值"""
        baselines = get_weight("emotion_state_mapper", "emotion_baseline") or {}
        return baselines.get(emotion_type) or self.EMOTION_BASELINE_FALLBACK.get(emotion_type, 
            {'interest': 50, 'frustration': 50, 'anxiety': 50, 'confidence': 50})

    def _get_impact_multiplier(self) -> float:
        return get_weight("emotion_state_mapper", "impact_multiplier") or 10.0

    def _get_dimension_bounds(self) -> tuple:
        bounds = get_weight("emotion_state_mapper", "dimension_bounds") or {"min": -50, "max": 150}
        return bounds.get("min", -50), bounds.get("max", 150)

    def _get_score_delta_weights(self) -> Dict[str, float]:
        return get_weight("emotion_state_mapper", "score_delta_weights") or {
            "interest": 0.3, "frustration": 0.2, "anxiety": 0.3, "confidence": 0.2
        }

    def _calculate_dimension_impact(
        self, 
        emotion_type: str, 
        confidence: float
    ) -> Dict[str, float]:
        """
        计算情绪对各子维度的影响
        
        Args:
            emotion_type: 情绪类型
            confidence: 置信度
            
        Returns:
            Dict: 各维度的影响值
        """
        base_impact = self._get_dynamic_emotion_weights(emotion_type)
        
        # 根据置信度调整影响强度
        adjusted_impact = {}
        for dimension, weight in base_impact.items():
            # 置信度越高，影响越大（线性缩放）
            adjusted_impact[dimension] = round(weight * confidence, 3)
        
        return adjusted_impact
    
    def _update_emotional_state_score(
        self,
        current_emotional_state: Dict[str, Any],
        impact: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        更新emotional_state维度的评分
        
        Args:
            current_emotional_state: 当前情绪状态
            impact: 各子维度的影响值
            
        Returns:
            Dict: 更新后的情绪状态
        """
        # 获取当前各子维度值
        interest = current_emotional_state.get('interest_level', '中等')
        frustration = current_emotional_state.get('frustration_tolerance', '中等')
        anxiety = current_emotional_state.get('anxiety_level', '中等')
        confidence = current_emotional_state.get('confidence_level', '中等')
        current_score = current_emotional_state.get('score', 50)
        
        # ★★★ 文本到数值的映射表（始终可用）★★★
        text_to_num = {
            '极低': 10, '很低': 20, '低': 30, '较低': 40,
            '中等': 50, '较高': 60, '高': 70, '很高': 80, '极高': 90
        }
        num_to_text = {v: k for k, v in text_to_num.items()}
        
        # ★★★ 优先使用保存的精确数值，如果没有则从文本转换 ★★★
        if '_interest_num' in current_emotional_state:
            interest_num = current_emotional_state['_interest_num']
            frustration_num = current_emotional_state['_frustration_num']
            anxiety_num = current_emotional_state['_anxiety_num']
            confidence_num = current_emotional_state['_confidence_num']
            print(f"🔍 [EmotionMapper] 使用保存的精确数值: interest={interest_num}, frustration={frustration_num}, anxiety={anxiety_num}, confidence={confidence_num}")
        else:
            # ★★★ 增强：支持模糊匹配文本描述 ★★★
            def fuzzy_text_to_num(text, default=50):
                """模糊匹配文本到数值，支持包含括号的描述"""
                if not text or not isinstance(text, str):
                    return default
                
                # 先尝试精确匹配
                if text in text_to_num:
                    print(f"   📝 [FuzzyMatch] '{text}' → 精确匹配 → {text_to_num[text]}")
                    return text_to_num[text]
                
                # 提取关键词（去除括号内容）
                clean_text = text.split('（')[0].split('(')[0].strip()
                if clean_text in text_to_num:
                    print(f"   📝 [FuzzyMatch] '{text}' → 提取关键词'{clean_text}' → {text_to_num[clean_text]}")
                    return text_to_num[clean_text]
                
                # 尝试部分匹配
                for key, value in text_to_num.items():
                    if key in text or text in key:
                        print(f"   📝 [FuzzyMatch] '{text}' → 部分匹配'{key}' → {value}")
                        return value
                
                print(f"   ⚠️ [FuzzyMatch] '{text}' → 未匹配，使用默认值 {default}")
                return default
            
            # 计算各子维度的新值
            print(f"🔍 [EmotionMapper] 开始转换文本到数值:")
            interest_num = fuzzy_text_to_num(interest)
            frustration_num = fuzzy_text_to_num(frustration)
            anxiety_num = fuzzy_text_to_num(anxiety)
            confidence_num = fuzzy_text_to_num(confidence)
            print(f"🔍 [EmotionMapper] 转换结果: interest={interest_num}, frustration={frustration_num}, anxiety={anxiety_num}, confidence={confidence_num}")
        
        # 应用影响（注意：anxiety是负向指标，需要反向处理）
        multiplier = self._get_impact_multiplier()
        interest_num += impact.get('interest_level', 0) * multiplier
        frustration_num += impact.get('frustration_tolerance', 0) * multiplier
        anxiety_num -= impact.get('anxiety_level', 0) * multiplier  # 焦虑增加=分数降低
        confidence_num += impact.get('confidence_level', 0) * multiplier
        
        print(f"🔍 [EmotionMapper] Impact系数: {impact}")
        print(f"🔍 [EmotionMapper] 应用影响后: interest={interest_num:.1f}, frustration={frustration_num:.1f}, anxiety={anxiety_num:.1f}, confidence={confidence_num:.1f}")
        
        # ★★★ 限制在动态配置的范围内 ★★★
        dmin, dmax = self._get_dimension_bounds()
        interest_num = max(dmin, min(dmax, interest_num))
        frustration_num = max(dmin, min(dmax, frustration_num))
        anxiety_num = max(dmin, min(dmax, anxiety_num))
        confidence_num = max(dmin, min(dmax, confidence_num))
        
        # 转换回文本描述（找最接近的）
        def num_to_closest_text(num):
            # ★★★ 先限制在映射表的范围内 ★★★
            clamped_num = max(10, min(90, num))
            closest = min(num_to_text.keys(), key=lambda x: abs(x - clamped_num))
            return num_to_text[closest]
        
        # ★★★ 核心修复：基于增量计算score，而不是重新计算 ★★★
        if '_yolo_updated' in current_emotional_state and '_previous_score' in current_emotional_state:
            # 已经有历史数据，基于上一次score计算变化量
            previous_score = current_emotional_state['_previous_score']
            
            # 获取旧的子维度数值
            old_interest = current_emotional_state.get('_interest_num', 70)
            old_frustration = current_emotional_state.get('_frustration_num', 50)
            old_anxiety = current_emotional_state.get('_anxiety_num', 60)
            old_confidence = current_emotional_state.get('_confidence_num', 50)
            
            # 计算变化量（使用动态权重）
            dw = self._get_score_delta_weights()
            delta_interest = (interest_num - old_interest) * dw.get("interest", 0.3)
            delta_frustration = (frustration_num - old_frustration) * dw.get("frustration", 0.2)
            delta_anxiety = -(anxiety_num - old_anxiety) * dw.get("anxiety", 0.3)  # 注意负号
            delta_confidence = (confidence_num - old_confidence) * dw.get("confidence", 0.2)
            
            total_delta = delta_interest + delta_frustration + delta_anxiety + delta_confidence
            new_score = round(previous_score + total_delta)  # ★★★ 使用round而不是int，避免小数截断 ★★★
            
            print(f"🔍 [EmotionMapper] Score增量计算: {previous_score} + {total_delta:.2f} = {new_score}")
        else:
            # 第一次YOLO更新，保留原始score
            new_score = current_score
            print(f"🔍 [EmotionMapper] 首次YOLO更新，保留初始score: {new_score}")
        
        # 限制score在0-100范围
        new_score = max(0, min(100, new_score))
        
        updated_emotional_state = {
            'interest_level': num_to_closest_text(interest_num),
            'frustration_tolerance': num_to_closest_text(frustration_num),
            'anxiety_level': num_to_closest_text(anxiety_num),
            'confidence_level': num_to_closest_text(confidence_num),
            'score': new_score,
            # ★★★ 新增：保存精确数值、更新标志和上一次score ★★★
            '_interest_num': round(interest_num, 2),
            '_frustration_num': round(frustration_num, 2),
            '_anxiety_num': round(anxiety_num, 2),
            '_confidence_num': round(confidence_num, 2),
            '_yolo_updated': True,  # ★★★ 标记已完成首次YOLO更新 ★★★
            '_previous_score': new_score  # ★★★ 保存本次score供下次使用 ★★★
        }
        
        return updated_emotional_state
    
    def _generate_default_emotional_state(
        self,
        emotion_type: str,
        confidence: float
    ) -> Dict[str, Any]:
        """
        生成默认的情绪状态（当没有历史数据时）
        
        Args:
            emotion_type: 检测到的情绪类型
            confidence: 置信度
            
        Returns:
            Dict: 基于情绪的默认情绪状态
        """
        # 根据情绪类型设置基准值（优先从动态配置获取）
        baseline = self._get_dynamic_emotion_baseline(emotion_type)
        
        # 根据置信度调整（置信度越高，偏离中性越远）
        adjustment = (confidence - 0.5) * 20  # 范围: -10 to +10
        
        interest = max(0, min(100, baseline['interest'] + adjustment))
        frustration = max(0, min(100, baseline['frustration'] + adjustment))
        anxiety = max(0, min(100, baseline['anxiety'] - adjustment))  # 负相关
        conf_level = max(0, min(100, baseline['confidence'] + adjustment))
        
        # 转换为文本描述
        def num_to_text(num):
            if num >= 80: return '很高'
            elif num >= 70: return '高'
            elif num >= 60: return '较高'
            elif num >= 40: return '中等'
            elif num >= 30: return '较低'
            elif num >= 20: return '低'
            else: return '很低'
        
        # 计算综合评分（加权平均）
        score = int(interest * 0.3 + frustration * 0.2 + (100 - anxiety) * 0.3 + conf_level * 0.2)
        
        return {
            'interest_level': num_to_text(interest),
            'frustration_tolerance': num_to_text(frustration),
            'anxiety_level': num_to_text(anxiety),
            'confidence_level': num_to_text(conf_level),
            'score': score
        }
    
    def _calculate_overall_valence(self, distribution: Dict) -> str:
        """计算整体效价（积极/消极/中性）"""
        positive_emotions = ['happy']
        negative_emotions = ['angry', 'disgust', 'fear', 'sad']
        neutral_emotions = ['neutral', 'surprise']
        
        positive_weight = sum(
            distribution.get(e, {}).get('percentage', 0)
            for e in positive_emotions
        )
        negative_weight = sum(
            distribution.get(e, {}).get('percentage', 0)
            for e in negative_emotions
        )
        
        if positive_weight > negative_weight * 1.5:
            return 'positive'
        elif negative_weight > positive_weight * 1.5:
            return 'negative'
        else:
            return 'neutral'
    
    def _calculate_overall_arousal(self, distribution: Dict) -> str:
        """计算整体唤醒度（高/中/低）"""
        high_arousal = ['angry', 'fear', 'surprise']
        medium_arousal = ['happy', 'disgust']
        low_arousal = ['sad', 'neutral']
        
        high_weight = sum(
            distribution.get(e, {}).get('percentage', 0)
            for e in high_arousal
        )
        low_weight = sum(
            distribution.get(e, {}).get('percentage', 0)
            for e in low_arousal
        )
        
        if high_weight > 50:
            return 'high'
        elif low_weight > 50:
            return 'low'
        else:
            return 'medium'
    
    def _analyze_trend(self, recent_emotions: List[Dict]) -> str:
        """分析情绪趋势"""
        if len(recent_emotions) < 3:
            return 'insufficient_data'
        
        # 简单趋势分析：比较前后半段的主导情绪
        mid_point = len(recent_emotions) // 2
        first_half = recent_emotions[:mid_point]
        second_half = recent_emotions[mid_point:]
        
        first_dominant = max(
            set(e['emotion'] for e in first_half),
            key=lambda x: sum(1 for e in first_half if e['emotion'] == x)
        )
        second_dominant = max(
            set(e['emotion'] for e in second_half),
            key=lambda x: sum(1 for e in second_half if e['emotion'] == x)
        )
        
        if first_dominant == second_dominant:
            return 'stable'
        else:
            # 判断是变好还是变坏
            valence_order = {
                'happy': 3, 'neutral': 2, 'surprise': 2,
                'sad': 1, 'angry': 0, 'fear': 0, 'disgust': 0
            }
            
            first_valence = valence_order.get(first_dominant, 2)
            second_valence = valence_order.get(second_dominant, 2)
            
            if second_valence > first_valence:
                return 'improving'
            elif second_valence < first_valence:
                return 'declining'
            else:
                return 'fluctuating'
    
    def _generate_recommendation(self, emotion_type: str, confidence: float) -> str:
        """生成建议"""
        recommendations = {
            'happy': '学生情绪积极，适合进行挑战性学习任务',
            'neutral': '学生情绪平稳，可正常推进教学内容',
            'surprise': '学生对内容感到新奇，可适当增加互动元素',
            'sad': '检测到低落情绪，建议给予鼓励或适当休息',
            'angry': '检测到愤怒情绪，建议暂停学习，进行情绪调节',
            'fear': '检测到恐惧/焦虑情绪，建议降低难度，增强安全感',
            'disgust': '检测到厌恶情绪，建议更换教学方式或内容'
        }
        
        base_rec = recommendations.get(emotion_type, '继续观察')
        
        if confidence < 0.5:
            return f"{base_rec}（置信度较低，需进一步观察）"
        else:
            return base_rec


# 使用示例
if __name__ == "__main__":
    mapper = EmotionStateMapper()
    
    # 模拟YOLO检测结果
    sample_emotion_data = [
        {
            "emotion": "surprise",
            "confidence": 0.705,
            "bbox": [237, 156, 370, 320],
            "centroid": [303, 238],
            "size": {"width": 133, "height": 164}
        }
    ]
    
    # 当前情绪状态
    current_emotional_state = {
        "interest_level": "高",
        "frustration_tolerance": "中等",
        "anxiety_level": "低",
        "confidence_level": "较高",
        "score": 72
    }
    
    # 处理单次检测
    result = mapper.process_emotion_detection(
        sample_emotion_data,
        {"emotional_state": current_emotional_state}
    )
    
    print("📊 单次情绪检测结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 模拟多次检测
    print("\n\n📈 模拟10次情绪检测...")
    import random
    
    emotions = ['happy', 'neutral', 'surprise', 'sad', 'angry']
    for i in range(10):
        emo = random.choice(emotions)
        conf = random.uniform(0.5, 0.9)
        data = [{"emotion": emo, "confidence": conf}]
        mapper.process_emotion_detection(data)
        time.sleep(0.1)
    
    # 聚合分析
    aggregated = mapper.aggregate_emotions_over_time(time_window_seconds=60)
    print("\n📊 聚合情绪分析结果:")
    print(json.dumps(aggregated, ensure_ascii=False, indent=2))
