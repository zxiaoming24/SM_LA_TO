"""
distraction_detector.py - 综合分心检测模块
功能：
1. 融合视线检测和物品检测数据
2. 时序统计和状态跟踪
3. 定期调用大模型分析
4. 综合判定分心状态
"""

import cv2
import numpy as np
from typing import Dict, Any, Optional
from collections import deque
import time
import asyncio

from eyesss_test_mm.config import DistractionConfig, GazeConfig, ObjectConfig, EmotionConfig
from eyesss_test_mm.gaze_detector import GazeDetector
from eyesss_test_mm.object_detector import ObjectDetector
from eyesss_test_mm.emotion_detector import EmotionDetector
from eyesss_test_mm.distraction_analyzer import DistractionAnalyzer


class DistractionDetector:
    """综合分心检测器"""
    
    def __init__(self, enable_llm: bool = True):
        """
        初始化检测器
        
        Args:
            enable_llm: 是否启用大模型分析
        """
        # 初始化子模块
        self.gaze_detector = GazeDetector() if GazeConfig.ENABLE_GAZE_DETECTION else None
        self.object_detector = ObjectDetector() if ObjectConfig.ENABLE_OBJECT_DETECTION else None
        self.emotion_detector = EmotionDetector() if EmotionConfig.ENABLE_EMOTION_DETECTION else None
        self.analyzer = DistractionAnalyzer() if enable_llm else None
        
        # 状态跟踪
        self.current_state = {
            "is_distracted": False,
            "distraction_level": "none",
            "attention_score": 100,
            "reasons": [],
            "suggestions": []
        }
        
        # 时序统计
        self.state_history = deque(maxlen=100)  # 状态历史
        self.distraction_start_time = None  # 分心开始时间
        self.last_llm_analysis_time = 0  # 上次大模型分析时间
        
        # 帧计数
        self.frame_count = 0
        self.last_detection_time = 0
        
        # ========== 行为级分心追踪状态 ==========
        
        # 规则1: 玩手机 - 手机出现且视线指向手机区域或低头
        self.phone_detected_frames = 0  # 连续检测到手机帧数
        
        # 规则2: 长时间闭眼 - EAR持续低于阈值
        self.low_ear_start_time = None  # EAR低于阈值开始时间
        
        # 规则3: 视线离开主屏幕 - 注视点超出屏幕边界
        self.gaze_out_of_bounds_start_time = None  # 视线离屏开始时间
        
        # 规则4: 头部大幅度偏转
        self.head_pose_violation_start_time = None  # 头部偏转开始时间
        
        # 大模型后台任务（避免阻塞主循环）
        self._pending_llm_task = None  # asyncio.Task, 后台运行中的大模型调用

        # ========== 状态平滑：防抖滑窗 ==========
        self._decision_history = deque(maxlen=15)  # 最近0.5秒的判定历史（30fps*0.5）
        self._smoothed_is_distracted = False
        self._smoothed_attention_scores = deque(maxlen=15)
    
    async def async_detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        异步综合检测（并行执行所有检测任务）
        
        Args:
            frame: BGR格式的图像帧
            
        Returns:
            综合检测结果
        """
        current_time = time.time()
        self.frame_count += 1
        
        # 初始化结果
        result = {
            "timestamp": current_time,
            "frame_count": self.frame_count,
            "gaze": {},
            "objects": {},
            "emotion": {},
            "statistics": None,
            "llm_analysis": None,
            "final_result": None
        }
        
        # 创建检测任务列表
        tasks = []
        
        # 1. 视线检测（同步执行，MediaPipe已在内部优化）
        if self.gaze_detector:
            gaze_result = self.gaze_detector.detect(frame)
            result["gaze"] = gaze_result
        
        # 2. 物品检测（异步）
        if self.object_detector:
            tasks.append(self.object_detector.async_detect(frame))
        
        # 3. 情绪检测（异步）
        if self.emotion_detector:
            tasks.append(self.emotion_detector.async_detect(frame))
        
        # 并行执行异步检测任务
        if tasks:
            async_results = await asyncio.gather(*tasks)
            
            # 分配结果
            for res in async_results:
                if "distraction_objects" in res:
                    result["objects"] = res
                elif "emotion_detected" in res:
                    result["emotion"] = res
        
        # 4. 时序统计
        statistics = self._calculate_statistics(result)
        result["statistics"] = statistics
        
        # 5. 先计算行为规则判定（即使没有大模型也运行）
        behavior_result = self._make_final_decision(result, statistics)
        result["final_result"] = behavior_result
        
        # 6. 大模型分析（后台任务，不阻塞主循环）
        #    先检查上次后台任务是否完成
        llm_result_ready = None
        if self._pending_llm_task is not None:
            if self._pending_llm_task.done():
                try:
                    llm_result_ready = self._pending_llm_task.result()
                except Exception:
                    llm_result_ready = None
                self._pending_llm_task = None
                self.last_llm_analysis_time = current_time
        
        if llm_result_ready is not None:
            result["llm_analysis"] = llm_result_ready
            if llm_result_ready.get("success"):
                final_result = self._merge_llm_result(behavior_result, llm_result_ready)
                result["final_result"] = final_result
        
        #    再检查是否需要启动新一轮大模型分析
        if (self.analyzer and 
            DistractionConfig.ENABLE_LLM_ANALYSIS and
            self._pending_llm_task is None and
            current_time - self.last_llm_analysis_time >= DistractionConfig.LLM_ANALYSIS_INTERVAL):
            
            self._pending_llm_task = asyncio.create_task(
                self.analyzer.async_analyze(
                    result["gaze"] or {},
                    result["objects"] or {},
                    result["emotion"] or {},
                    statistics,
                    behavior_result
                )
            )
        
        # 记录状态历史
        final_result = result.get("final_result", behavior_result)

        # ★★★ 状态平滑：用滑窗多数决防抖 ★★★
        self._decision_history.append(final_result["is_distracted"])
        self._smoothed_attention_scores.append(final_result["attention_score"])

        if len(self._decision_history) >= self._decision_history.maxlen:
            # 分心状态：近15帧中>30%判定分心才标记为分心
            distracted_ratio = sum(self._decision_history) / len(self._decision_history)
            self._smoothed_is_distracted = distracted_ratio > 0.3

            # 专注度分数：取中位数（消除单帧异常值）
            sorted_scores = sorted(self._smoothed_attention_scores)
            smoothed_score = sorted_scores[len(sorted_scores) // 2]
        else:
            # 数据不足时使用原始值
            self._smoothed_is_distracted = final_result["is_distracted"]
            smoothed_score = final_result["attention_score"]

        # 用平滑值覆盖原始结果
        final_result["is_distracted"] = self._smoothed_is_distracted
        final_result["attention_score"] = smoothed_score
        if self._smoothed_is_distracted:
            if smoothed_score < 30:
                final_result["distraction_level"] = "high"
            elif smoothed_score < 60:
                final_result["distraction_level"] = "medium"
            else:
                final_result["distraction_level"] = "low"
        else:
            final_result["distraction_level"] = "none"

        self.current_state = {k: final_result.get(k) for k in self.current_state}
        self.state_history.append({
            "timestamp": current_time,
            "is_distracted": final_result["is_distracted"],
            "attention_score": final_result["attention_score"]
        })
        
        return result
    
    def _calculate_statistics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """计算时序统计"""
        current_time = time.time()
        
        # 持续时间
        if self.distraction_start_time:
            duration = current_time - self.distraction_start_time
        else:
            duration = 0.0
        
        # 视线统计
        gaze_stats = self.gaze_detector.get_statistics() if self.gaze_detector else {}
        
        # 物品统计
        object_stats = self.object_detector.get_statistics() if self.object_detector else {}
        
        return {
            "duration": duration,
            "gaze_change": gaze_stats.get("gaze_change", "未知"),
            "blink_rate_30s": gaze_stats.get("blink_rate_30s", 0),
            "recent_objects": object_stats.get("recent_objects", {})
        }
    
    def _make_final_decision(self, result: Dict[str, Any], statistics: Dict[str, Any]) -> Dict[str, Any]:
        """
        综合判定分心状态 - 基于具体行为规则
        
        规则1: 玩手机 → 检测到手机 + 视线指向手机区域或低头
        规则2: 长时间闭眼 → EAR < 0.18 持续超过 1 秒
        规则3: 视线离开主屏幕 → 注视点超出屏幕区域超过 2 秒
        规则4: 头部大幅度偏转 → 头部欧拉角超出正常范围超过 1 秒
        """
        is_distracted = False
        distraction_level = "none"
        attention_score = 100
        reasons = []
        suggestions = []
        current_time = time.time()
        
        gaze_data = result.get("gaze", {})
        objects_data = result.get("objects", {})
        face_detected = gaze_data.get("face_detected", False)
        
        # ============================================================
        # 规则1: 玩手机 - 检测到手机即判定分心
        # 学习场景下手机出现在视野中本身就是强分心信号
        # 同时附加低头/视线指向作为辅助证据
        # ============================================================
        phone_objects = [obj for obj in objects_data.get("objects", []) 
                        if obj.get("class_id") == ObjectConfig.PHONE_CLASS_ID]
        
        if phone_objects:
            self.phone_detected_frames += 1
            phone_obj = phone_objects[0]
            phone_conf = phone_obj.get("confidence", 0)
            
            # 辅助证据: 是否低头
            is_looking_down = False
            head_pose = gaze_data.get("head_pose", {})
            if abs(head_pose.get("pitch", 0)) > DistractionConfig.LOOK_DOWN_PITCH_THRESHOLD:
                is_looking_down = True
            
            # 只要有手机就判定分心
            is_distracted = True
            distraction_level = max(distraction_level, "high")
            attention_score -= 50
            
            if is_looking_down:
                reasons.append("玩手机（低头看手机）")
            elif phone_conf > 0.5:
                reasons.append(f"玩手机（手机出现在视野中，置信度{phone_conf:.2f}）")
            else:
                reasons.append(f"玩手机（手机出现在视野中）")
            suggestions.append("请将手机移出视线范围")
        else:
            self.phone_detected_frames = 0
        
        # ============================================================
        # 规则2: 长时间闭眼 - EAR < 阈值持续超过设定时间
        # ============================================================
        if face_detected:
            avg_ear = gaze_data.get("avg_ear", 1.0)
            
            if avg_ear < DistractionConfig.LONG_EYE_CLOSE_EAR_THRESHOLD:
                if self.low_ear_start_time is None:
                    self.low_ear_start_time = current_time
                
                ear_duration = current_time - self.low_ear_start_time
                if ear_duration >= DistractionConfig.LONG_EYE_CLOSE_DURATION:
                    is_distracted = True
                    distraction_level = max(distraction_level, "high")
                    attention_score -= 60
                    reasons.append(f"长时间闭眼（{ear_duration:.1f}秒）")
                    suggestions.append("请保持睁眼状态，如有困意请适当休息")
            else:
                self.low_ear_start_time = None
        
        # ============================================================
        # 规则3: 视线离开主屏幕 - 注视点超出屏幕区域超过设定时间
        # ============================================================
        if face_detected:
            gaze_x = gaze_data.get("gaze_offset_x", 0)
            gaze_y = gaze_data.get("gaze_offset_y", 0)
            
            # 将视线偏移转换为屏幕归一化坐标（近似）
            screen_x = 0.5 + gaze_x  # 偏移转屏幕坐标
            screen_y = 0.5 + gaze_y
            
            # 判断是否超出屏幕边界
            is_out_of_bounds = (
                screen_x < DistractionConfig.SCREEN_BOUNDARY_X_MIN or
                screen_x > DistractionConfig.SCREEN_BOUNDARY_X_MAX or
                screen_y < DistractionConfig.SCREEN_BOUNDARY_Y_MIN or
                screen_y > DistractionConfig.SCREEN_BOUNDARY_Y_MAX
            )
            
            if is_out_of_bounds:
                if self.gaze_out_of_bounds_start_time is None:
                    self.gaze_out_of_bounds_start_time = current_time
                
                out_duration = current_time - self.gaze_out_of_bounds_start_time
                if out_duration >= DistractionConfig.GAZE_OUT_OF_BOUNDS_DURATION:
                    is_distracted = True
                    distraction_level = max(distraction_level, "medium")
                    attention_score -= 30
                    reasons.append(f"视线离开屏幕（已持续{out_duration:.1f}秒）")
                    suggestions.append("请将注意力放回屏幕内容")
            else:
                self.gaze_out_of_bounds_start_time = None
        
        # ============================================================
        # 规则4: 头部大幅度偏转 - 头部欧拉角超出正常范围
        # ============================================================
        if face_detected:
            head_pose = gaze_data.get("head_pose", {})
            yaw = abs(head_pose.get("yaw", 0))
            pitch = abs(head_pose.get("pitch", 0))
            
            # 判断头部姿态是否异常
            is_head_violation = (
                yaw > DistractionConfig.HEAD_YAW_THRESHOLD or
                pitch > DistractionConfig.HEAD_PITCH_THRESHOLD
            )
            
            if is_head_violation:
                if self.head_pose_violation_start_time is None:
                    self.head_pose_violation_start_time = current_time
                
                head_duration = current_time - self.head_pose_violation_start_time
                if head_duration >= DistractionConfig.HEAD_POSE_DURATION:
                    is_distracted = True
                    distraction_level = max(distraction_level, "medium")
                    attention_score -= 25
                    
                    if yaw > DistractionConfig.HEAD_YAW_THRESHOLD:
                        direction = "左" if head_pose.get("yaw", 0) < 0 else "右"
                        reasons.append(f"头部大幅度向{direction}偏转（{yaw:.0f}°）")
                    if pitch > DistractionConfig.HEAD_PITCH_THRESHOLD:
                        direction = "低" if head_pose.get("pitch", 0) > 0 else "仰"
                        reasons.append(f"头部大幅度向{direction}（{pitch:.0f}°）")
                    suggestions.append("请保持端正坐姿，正面朝向屏幕")
            else:
                self.head_pose_violation_start_time = None
        
        # ============================================================
        # 规则5: 打哈欠 - 嘴部纵横比 > 阈值并持续
        # ============================================================
        if gaze_data.get("is_yawning", False):
            yawn_duration = gaze_data.get("yawn_duration", 0)
            is_distracted = True
            distraction_level = max(distraction_level, "medium")
            attention_score -= 25
            reasons.append(f"打哈欠（持续{yawn_duration:.1f}秒）")
            suggestions.append("如有困意请适当休息")
        
        # ============================================================
        # 规则6: 打瞌睡 - 多信号综合判定
        # ============================================================
        if gaze_data.get("is_drowsy", False):
            drowsy_score = gaze_data.get("drowsiness_score", 0.0)
            nodding = gaze_data.get("nodding_intensity", 0.0)
            is_distracted = True
            distraction_level = max(distraction_level, "high")
            attention_score -= 40
            if nodding > 0.3:
                reasons.append(f"打瞌睡（头部频繁点头，强度{nodding:.2f}）")
            else:
                reasons.append("打瞌睡（综合信号疲劳）")
            suggestions.append("建议立即休息，疲劳状态下学习效率低下")
        
        # ============================================================
        # 辅助规则: 眨眼频率异常
        # ============================================================
        blink_rate = gaze_data.get("blink_rate", 0)
        if blink_rate > 25:
            attention_score -= 10
            reasons.append(f"眨眼频率过高（{blink_rate}次/分钟）")
            if "请保持睁眼状态" not in " ".join(suggestions):
                suggestions.append("建议适时眨眼缓解眼疲劳")
        
        # ============================================================
        # 辅助规则: 情绪分析影响
        # ============================================================
        emotion_data = result.get("emotion", {})
        if emotion_data.get("emotion_detected"):
            attention_impact = emotion_data.get("attention_impact", 0)
            attention_score += attention_impact
            if attention_impact < 0:
                reasons.append(f"情绪状态: {emotion_data.get('state', '未知')}")
        
        # ============================================================
        # 融合大模型分析结果（加权参考）
        # ============================================================
        llm_result = result.get("llm_analysis") or {}
        if llm_result.get("success"):
            llm_score = llm_result.get("attention_score", 50)
            attention_score = int(attention_score * 0.6 + llm_score * 0.4)
            
            if llm_result.get("is_distracted", False):
                is_distracted = True
                distraction_level = max(distraction_level, llm_result.get("distraction_level", "low"))
                # 添加大模型给出的、尚未包含的原因
                for r in llm_result.get("reasons", []):
                    if r not in reasons:
                        reasons.append(r)
            
            llm_suggestions = llm_result.get("suggestions", [])
            for s in llm_suggestions:
                if s not in suggestions:
                    suggestions.append(s)
        
        # ============================================================
        # 最终评分与等级
        # ============================================================
        attention_score = max(0, min(100, attention_score))
        
        # 更新分心时间
        if is_distracted and not self.distraction_start_time:
            self.distraction_start_time = current_time
        elif not is_distracted:
            self.distraction_start_time = None
        
        # 确定分心等级
        if not is_distracted:
            distraction_level = "none"
        elif attention_score < 30:
            distraction_level = "high"
        elif attention_score < 60:
            distraction_level = "medium"
        else:
            distraction_level = "low"
        
        return {
            "is_distracted": is_distracted,
            "distraction_level": distraction_level,
            "attention_score": attention_score,
            "reasons": reasons,
            "suggestions": suggestions
        }
    
    def _merge_llm_result(self, behavior_result: Dict[str, Any], llm_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        融合行为规则结果和大模型分析结果
        
        Args:
            behavior_result: 行为规则判定结果
            llm_result: 大模型分析结果
            
        Returns:
            融合后的最终结果
        """
        # 基础来自行为规则
        merged = dict(behavior_result)
        
        # 融合大模型分数（加权平均）
        behavior_score = behavior_result.get("attention_score", 50)
        llm_score = llm_result.get("attention_score", 50)
        merged["attention_score"] = int(behavior_score * 0.7 + llm_score * 0.3)
        
        # 如果大模型判定分心，增强等级
        if llm_result.get("is_distracted", False):
            merged["is_distracted"] = True
            merged["distraction_level"] = max(
                behavior_result.get("distraction_level", "none"),
                llm_result.get("distraction_level", "low"),
                key=lambda x: {"none": 0, "low": 1, "medium": 2, "high": 3}.get(x, 0)
            )
            # 添加大模型的补充原因
            for r in llm_result.get("reasons", []):
                if r not in merged["reasons"]:
                    merged["reasons"].append(r)
        
        # 合并建议
        for s in llm_result.get("suggestions", []):
            if s not in merged["suggestions"]:
                merged["suggestions"].append(s)
        
        # 更新当前状态
        self.current_state = merged
        
        return merged
    
    def get_current_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self.current_state
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 分心时长统计
        distracted_frames = sum(1 for s in self.state_history if s["is_distracted"])
        total_frames = len(self.state_history)
        
        distracted_ratio = distracted_frames / total_frames if total_frames > 0 else 0
        
        # 平均注意力分数
        if self.state_history:
            avg_attention = sum(s["attention_score"] for s in self.state_history) / total_frames
        else:
            avg_attention = 100
        
        return {
            "total_frames": total_frames,
            "distracted_frames": distracted_frames,
            "distracted_ratio": distracted_ratio,
            "avg_attention_score": avg_attention,
            "current_state": self.current_state
        }
    
    def close(self):
        """释放资源"""
        if self.gaze_detector:
            self.gaze_detector.close()