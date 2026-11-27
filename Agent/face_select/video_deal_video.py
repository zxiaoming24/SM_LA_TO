import asyncio
import time
import os
import json
from collections import deque
from typing import Dict, Any, List, Tuple, Optional, Callable, Awaitable
import concurrent.futures
import uuid

import cv2
import numpy as np
# from face_recognition.face_recognition_service import create_face_recognition_module
from config import FaceRecognitionConfig, EmotionConfig, SittingPostureConfig, MultiModalConfig, AnomalyDetectionConfig, DatabaseConfig, GazeConfig
from logger import get_logger
from ultralytics import YOLO
from sitting_posture_interface import SittingPosturePredictor
from vllm_analysis import video_chat_async_limit_frame, analyze_learning_with_parse
from insert_sql import DatabaseInserter
from gaze_detector import GazeDetector
from attention_tracker import AttentionTracker

class VideoWrapper():
    async def _run_in_executor(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))

    def _resize_for_emotion(self, frame: np.ndarray, max_side: int = 640) -> Tuple[np.ndarray, float, float]:
        h, w = frame.shape[:2]
        if max(h, w) <= max_side:
            return frame, 1.0, 1.0
        scale = max_side / float(max(h, w))
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, new_w / float(w), new_h / float(h)

    def _should_send_anomaly(self, payload_type: str, data: Any) -> List[str]:
        def _unique(items: List[str]) -> List[str]:
            seen = set()
            result = []
            for item in items:
                if item and item not in seen:
                    seen.add(item)
                    result.append(item)
            return result
        
        if not data:
                return []

        if payload_type == "posture":
            anomalies = []
            if data:
                head = data.get("Head")
                hunch = data.get("Hunch")
                cross_leg = data.get("CrossLeg")

                if head in AnomalyDetectionConfig.SITTING_POSTURE_ANOMALIES.get("head", []):
                    anomalies.append(head)
                if hunch in AnomalyDetectionConfig.SITTING_POSTURE_ANOMALIES.get("hunch", []):
                    anomalies.append(hunch)
                if cross_leg in AnomalyDetectionConfig.SITTING_POSTURE_ANOMALIES.get("cross_leg", []):
                    anomalies.append(cross_leg)
            return _unique(anomalies)

        if payload_type == "emotion":
            anomalies = _unique([
                det.get("emotion")
                for det in data
                if det.get("emotion") in AnomalyDetectionConfig.EMOTION_ANOMALIES
                and float(det.get("confidence", 0)) >= AnomalyDetectionConfig.EMOTION_ANOMALY_CONFIDENCE_THRESHOLD
            ])
            return anomalies

        if payload_type == "face":
            unknown_face = any(
                (not det.get("is_known"))
                and float(det.get("confidence", 0)) > AnomalyDetectionConfig.FACE_RECOGNITION_CONFIDENCE_THRESHOLD
                for det in data
            )
            multiple_faces = AnomalyDetectionConfig.FACE_RECOGNITION_ANOMALY_ENABLED and len(data) > 1
            anomalies = []
            if unknown_face:
                anomalies.append("unknown_face")
            if multiple_faces:
                anomalies.append("multiple_faces")
            return anomalies

        if payload_type == "multi_modal":
            if isinstance(data, dict):
                problem_behaviors = data.get("problem_behaviors")
                if not problem_behaviors or problem_behaviors == "无":
                    return []
                if isinstance(problem_behaviors, list):
                    return _unique([str(item) for item in problem_behaviors if item])
                return [str(problem_behaviors)]
            return []

        return []

    def _process_emotion_results(self, results, scale_x: float = 1.0, scale_y: float = 1.0) -> List[Dict[str, Any]]:
        """处理YOLO检测结果
        
        Args:
            results: YOLO模型的原始输出
            
        Returns:
            标准化的检测结果列表
        """
        detections = []
        try:
            for r in results:
                if not hasattr(r, 'boxes') or r.boxes is None:
                    continue
                
                for box in r.boxes:
                    try:
                        conf = float(box.conf)
                        if conf < EmotionConfig.EMOTION_CONFIDENCE:
                            continue
                        
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        cls = int(box.cls)
                        emotion_name = EmotionConfig.EMOTION_CLASS_NAMES[cls] \
                            if cls < len(EmotionConfig.EMOTION_CLASS_NAMES) else f"unknown({cls})"
                        
                        # 确保坐标有效
                        if scale_x != 1.0 or scale_y != 1.0:
                            x1, x2 = x1 / scale_x, x2 / scale_x
                            y1, y2 = y1 / scale_y, y2 / scale_y
                        x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), int(x2), int(y2)
                        
                        if x1 < x2 and y1 < y2:  # 有效的检测框
                            detections.append({
                                'emotion': emotion_name,
                                'confidence': round(conf, 3),
                                'bbox': [x1, y1, x2, y2],
                                'centroid': [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                                'size': {'width': int(x2 - x1), 'height': int(y2 - y1)}
                            })
                    except (ValueError, IndexError) as e:
                        self.logger.debug(f"处理单个检测框失败: {e}")
                        continue
        except Exception as e:
            self.logger.error(f"处理检测结果失败: {e}", exc_info=True)
        
        return detections
    
    def _draw_emotion_annotations(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> Tuple[np.ndarray, bool]:
        """在帧上绘制情绪检测框和标签
        
        Args:
            frame: 输入的视频帧
            detections: 检测结果列表
            
        Returns:
            (标注后的帧, 是否成功标注)
        """
        if not detections or frame is None:
            return frame, False
        
        try:
            annotated = frame.copy()
            h, w = frame.shape[:2]
            
            for det in detections:
                x1, y1, x2, y2 = det['bbox']
                emotion = det['emotion']
                conf = det['confidence']
                color = self._get_emotion_color(emotion)
                
                # 确保坐标在帧内
                x1 = max(0, min(x1, w))
                y1 = max(0, min(y1, h))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))
                
                if x1 >= x2 or y1 >= y2:
                    continue
                
                # 绘制检测框
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                
                # 准备标签
                label = f"{emotion}({conf:.2f})"
                text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                text_w, text_h = text_size
                
                # 计算标签位置
                y_offset = y1 - 8 if y1 - text_h - 8 > 0 else y1 + text_h + 8
                x_offset = max(0, min(x1, w - text_w - 8))
                
                # 绘制标签背景
                cv2.rectangle(annotated,
                            (x_offset, y_offset - text_h - 4),
                            (x_offset + text_w + 4, y_offset + 4),
                            color, -1)
                
                # 绘制标签文本
                cv2.putText(annotated, label, (x_offset + 2, y_offset - 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            return annotated, True
        except Exception as e:
            self.logger.error(f"绘制标注失败: {e}", exc_info=True)
            return frame, False
    
    def _get_emotion_color(self, emotion: str) -> tuple:
        """根据情绪类型返回颜色 (BGR)"""
        colors = {
            'happy': (0, 255, 0), 'sad': (255, 0, 0), 'angry': (0, 0, 255),
            'surprised': (0, 255, 255), 'fear': (255, 0, 255), 'neutral': (128, 128, 128),
        }
        return colors.get(emotion.lower(), (200, 200, 200))

    async def _run_multi_modal_analysis(
        self,
        frames: List[np.ndarray],
        start_analysis_ts: float,
        end_analysis_ts: float,
    ) -> None:
        """异步执行多模态分析"""
        if not frames:
            return

        self.multi_modal_in_progress = True
        try:
            result = await video_chat_async_limit_frame(self.multi_modal_prompt, frames)
            self.logger.info(f"多模态分析结果: {result}")
            parsed = analyze_learning_with_parse(result)
            anomalies = self._should_send_anomaly("multi_modal", parsed)
            if anomalies:
                await self._emit_result({
                    "type": "multi_modal",
                    "analysis_ts": end_analysis_ts,
                    "start_analysis_ts": start_analysis_ts,
                    "end_analysis_ts": end_analysis_ts,
                    "data": anomalies,
                })
            return parsed
        except Exception as e:
            self.logger.error(f"多模态分析处理失败: {e}")
        finally:
            self.multi_modal_in_progress = False

    kind = "video"

    def __init__(
        self,
        track,
        analysis_config: Optional[Dict[str, Any]] = None,
        video_filename: Optional[str] = None,
    ):
        super().__init__()
        self.track = track
        self.logger = get_logger(__name__)
        self.window_name = f"VideoWapper_{track.id}"
        self.video_filename = video_filename
        
        # 保存分析配置（如果未提供则使用默认值）
        self.analysis_config = analysis_config or {
            "behaviorAnalysis": False,
            "expressionAnalysis": False,
            "postureAnalysis": False,
            "display": True
        }
        self.logger.info(f"VideoWrapper 分析配置: {self.analysis_config}")

        # 是否显示实时画面
        self.display = self.analysis_config.get("display", True)
        
        # 提取 sessionId 用于数据库保存
        self.session_id = self.analysis_config.get("sessionId")
        
        # 初始化数据库连接
        self.db_inserter = None
        if DatabaseConfig.ENABLE_DATABASE:
            try:
                self.db_inserter = DatabaseInserter(
                    host=DatabaseConfig.DB_HOST,
                    user=DatabaseConfig.DB_USER,
                    password=DatabaseConfig.DB_PASSWORD,
                    database=DatabaseConfig.DB_NAME,
                    port=DatabaseConfig.DB_PORT
                )
                self.db_inserter.connect()
                self.logger.info(f"数据库连接已建立 [session_id={self.session_id}]")
            except Exception as e:
                self.logger.error(f"数据库连接失败: {e}")
                self.db_inserter = None
        
        # 帧率统计
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_log = time.time()

        # 异步分析线程池
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # 分析任务状态
        self.posture_task_in_progress = False
        self.face_task_in_progress = False
        self.emotion_task_in_progress = False
        # 坐姿分析处理控制
        self.posture_frame_counter = 0
        self.posture_process_interval = SittingPostureConfig.SITTING_POSTURE_FRAMES
        
        # 人脸识别处理控制
        self.face_frame_counter = 0
        self.face_process_interval = FaceRecognitionConfig.FACE_RECOGNITION_FRAMES
        
        # 情绪分析处理控制
        self.emotion_frame_counter = 0
        self.emotion_process_interval = EmotionConfig.EMOTION_FRAMES
        self.emotion_model = None

        # 多模态分析处理控制
        self.multi_modal_frame_counter = 0
        self.multi_modal_frame_interval = 10  # 默认每10帧进行一次多模态分析
        self.multi_modal_queue_size = MultiModalConfig.MULTI_MODAL_QUEUE_SIZE
        self.multi_modal_prompt = getattr(
            MultiModalConfig,
            "MULTI_MODAL_PROMPT",
            "请客观描述画面中的行为和特征。"
        )
        self.multi_modal_in_progress = False
        self.multi_modal_frame_cache: deque = deque(maxlen=self.multi_modal_queue_size)

        # 用于追踪上一次分析结果，用于判断是否需要更新结束时间
        self.last_analysis_result = {}  # 存储上一次的分析结果
        self.last_analysis_db_id = {}   # 存储上一次分析结果对应的session_id

        # Voting and segment merge/filter settings (seconds)
        self.vote_window_seconds = 1 * 60 # 1分钟投票窗口
        self.vote_min_samples = 2
        self.vote_majority_ratio = 0.6
        self.merge_gap_seconds = 60 # 60秒内的同类型结果视为同一片段
        self.min_segment_seconds = 5.0 # 最短片段长度，过滤过短片段
        self.vote_windows: Dict[str, deque] = {}
        # 用于合并片段的临时存储，格式: {(payload_type, label): {"start": ts, "end": ts, "last_seen": ts}}
        # 超过merge_gap_seconds未更新的片段将被终止并写入数据库
        self.active_segments: Dict[Tuple[str, str], Dict[str, float]] = {} 
        
        # 初始化人脸识别模块
        # self.face_recognition_module = None
        # if FaceRecognitionConfig.ENABLE_FACE_RECOGNITION:
        #     try:
        #         face_config = {
        #             "threshold": FaceRecognitionConfig.FACE_DETECTION_THRESHOLD,
        #             "database_path": FaceRecognitionConfig.FACE_DATABASE_PATH
        #         }
        #         self.face_recognition_module = create_face_recognition_module(face_config)
        #         if self.face_recognition_module:
        #             self.logger.info(f"VideoWapper 人脸识别模块初始化成功 [track_id={track.id}]")
        #             self.logger.info(f"人脸识别处理间隔: 每 {self.face_process_interval} 帧处理一次")
        #         else:
        #             self.logger.warning(f"VideoWapper 人脸识别模块初始化失败 [track_id={track.id}]")
        #     except Exception as e:
        #         self.logger.error(f"VideoWapper 初始化人脸识别模块失败: {e}")
        
        # 初始化情绪分析模块
        if EmotionConfig.ENABLE_EMOTION:
            try:
                self.emotion_model = YOLO(EmotionConfig.EMOTION_MODEL_PATH)
                if self.emotion_model:
                    self.logger.info(f"VideoWapper 情绪识别模块初始化成功 [track_id={track.id}]")
                    self.logger.info(f"情绪分析处理间隔: 每 {self.emotion_process_interval} 帧处理一次")
                else:
                    self.logger.warning(f"VideoWapper 情绪识别模块初始化失败 [track_id={track.id}]")
            except Exception as e:
                self.logger.error(f"VideoWapper 初始化情绪识别模块失败: {e}")

        # 初始化姿势预测器
        if SittingPostureConfig.ENABLE_SITTING_POSTURE:
            self.sitting_posture_predictor = SittingPosturePredictor()

        # ★★★ 初始化视线检测器 ★★★
        self.gaze_detector = None
        self.attention_tracker = None
        self.gaze_frame_counter = 0
        self.gaze_process_interval = GazeConfig.ATTENTION_RECORD_INTERVAL
        if GazeConfig.ENABLE_GAZE_DETECTION:
            try:
                self.gaze_detector = GazeDetector()
                self.logger.info(f"视线检测器初始化成功 [track_id={track.id}]")
                if GazeConfig.ENABLE_ATTENTION_TRACKING:
                    self.attention_tracker = AttentionTracker()
                    self.logger.info(f"专注度追踪器初始化成功 [track_id={track.id}]")
            except Exception as e:
                self.logger.error(f"视线检测器初始化失败: {e}")
        
    async def cleanup(self) -> None:
        """清理资源，释放数据库连接"""
        # Flush remaining segments before closing DB
        try:
            self._flush_segments()
        except Exception as e:
            self.logger.error(f"刷新分析片段失败: {e}", exc_info=True)
        # 关闭线程池
        try:
            if self.executor is not None:
                self.executor.shutdown(wait=False)
                self.executor = None
        except Exception as e:
            self.logger.error(f"关闭线程池失败: {e}", exc_info=True)
        
        # 关闭数据库连接
        try:
            if self.db_inserter is not None:
                self.db_inserter.close()
                self.logger.info(f"数据库连接已关闭 [session_id={self.session_id}]")
                self.db_inserter = None
        except Exception as e:
            self.logger.error(f"关闭数据库连接失败: {e}", exc_info=True)

        # ★★★ 关闭视线检测器 ★★★
        try:
            if self.gaze_detector is not None:
                self.gaze_detector.close()
                self.gaze_detector = None
        except Exception as e:
            self.logger.error(f"关闭视线检测器失败: {e}", exc_info=True)

    async def _emit_result(self, payload: Dict[str, Any]) -> None:
        try:
            payload_type = payload.get("type")
            payload_data = payload.get("data")
            analysis_ts = payload.get("analysis_ts")

            if not payload_type or analysis_ts is None or payload_data is None:
                return

            if payload_type == "multi_modal":
                start_ts = payload.get("start_analysis_ts", analysis_ts)
                end_ts = payload.get("end_analysis_ts", analysis_ts)
                if self.db_inserter and self.session_id:
                    try:
                        self.db_inserter.insert_analysis_data(
                            session_id=self.session_id,
                            type=payload_type,
                            start_analysis_ts=str(start_ts),
                            end_analysis_ts=str(end_ts),
                            data=json.dumps(payload_data, ensure_ascii=False),
                            video_name=self.video_filename
                        )
                    except Exception as e:
                        self.logger.error(f"保存到数据库失败: {e}", exc_info=True)
                return

            # 对异常标签做时间窗口投票，过滤抖动
            voted_labels = self._vote_anomalies(payload_type, payload_data, float(analysis_ts))
            if not voted_labels:
                return

            # 先让不再活跃的片段过期，再更新当前活跃片段
            self._expire_segments(payload_type, float(analysis_ts), set(voted_labels))
            self._update_segments(payload_type, voted_labels, float(analysis_ts))
        except Exception as e:
            self.logger.error(f"处理分析结果失败: {e}", exc_info=True)

    def _vote_anomalies(self, payload_type: str, labels: List[str], analysis_ts: float) -> List[str]:
        # 按类型维护滑动窗口：[(ts, {labels}), ...]
        window = self.vote_windows.setdefault(payload_type, deque())
        window.append((analysis_ts, set(labels)))

        # 移除窗口外样本
        cutoff = analysis_ts - self.vote_window_seconds
        while window and window[0][0] < cutoff:
            window.popleft()

        total_samples = len(window)
        if total_samples < self.vote_min_samples:
            return []

        # 统计窗口内各标签出现频次
        counts: Dict[str, int] = {}
        for _, label_set in window:
            for label in label_set:
                counts[label] = counts.get(label, 0) + 1

        # 过半（比例阈值）通过的标签视为有效
        voted = [
            label
            for label, count in counts.items()
            if (count / float(total_samples)) >= self.vote_majority_ratio
        ]
        return voted

    def _expire_segments(self, payload_type: str, current_ts: float, active_labels: set) -> None:
        # 找出本次未出现且超出合并间隔的片段并终止
        expired_keys: List[Tuple[str, str]] = []
        for (ptype, label), seg in self.active_segments.items():
            if ptype != payload_type:
                continue
            if label in active_labels:
                continue
            if current_ts - seg["last_seen"] > self.merge_gap_seconds:
                expired_keys.append((ptype, label))

        for key in expired_keys:
            seg = self.active_segments.pop(key, None)
            if seg:
                self._finalize_segment(key, seg)

    def _update_segments(self, payload_type: str, labels: List[str], analysis_ts: float) -> None:
        # 合并相邻片段或新开片段
        for label in labels:
            key = (payload_type, label)
            seg = self.active_segments.get(key)
            if seg:
                gap = analysis_ts - seg["last_seen"]
                if gap <= self.merge_gap_seconds:
                    seg["end"] = analysis_ts
                    seg["last_seen"] = analysis_ts
                else:
                    self._finalize_segment(key, seg)
                    self.active_segments[key] = {
                        "start": analysis_ts,
                        "end": analysis_ts,
                        "last_seen": analysis_ts,
                    }
            else:
                self.active_segments[key] = {
                    "start": analysis_ts,
                    "end": analysis_ts,
                    "last_seen": analysis_ts,
                }

    def _finalize_segment(self, key: Tuple[str, str], seg: Dict[str, float]) -> None:
        start_ts = seg["start"]
        end_ts = seg["end"]
        duration = end_ts - start_ts
        payload_type, label = key

        # 过滤过短片段，避免噪声入库
        if duration < self.min_segment_seconds:
            self.logger.debug(
                "过滤过短片段: type=%s, label=%s, duration=%.2fs",
                payload_type,
                label,
                duration,
            )
            return

        # 写入数据库（按异常类型与时间段记录）
        if self.db_inserter and self.session_id:
            try:
                self.db_inserter.insert_analysis_data(
                    session_id=self.session_id,
                    type=payload_type,
                    start_analysis_ts=str(start_ts),
                    end_analysis_ts=str(end_ts),
                    data=label,
                    video_name=self.video_filename
                )
            except Exception as e:
                self.logger.error(f"保存到数据库失败: {e}", exc_info=True)

    def _flush_segments(self) -> None:
        if not self.active_segments:
            return
        # 结束所有未关闭片段并清理
        for key, seg in list(self.active_segments.items()):
            self._finalize_segment(key, seg)
        self.active_segments.clear()
    
    async def _handle_posture_analysis(self, frame_array: np.ndarray, current_time: float) -> None:
        if self.posture_task_in_progress:
            return
        self.posture_task_in_progress = True
        try:
            annotated_frame, posture_results = await self._run_in_executor(
                self.sitting_posture_predictor.process_frame, frame_array
            )
            if posture_results:
                self.logger.debug(
                    f"坐姿分析完成 - 头部: {posture_results.get('Head', 'N/A')}, "
                    f"塌腰: {posture_results.get('Hunch', 'N/A')}, "
                    f"翘腿: {posture_results.get('CrossLeg', 'N/A')}, "
                    f"关键点: {'检测到' if posture_results.get('keypoints_available') else '未检测到'}"
                )
                anomalies = self._should_send_anomaly("posture", posture_results)
                if anomalies:
                    await self._emit_result({
                        "type": "posture",
                        "analysis_ts": current_time,
                        "data": anomalies,
                    })
        except Exception as e:
            self.logger.error(f"坐姿分析处理失败: {e}")
        finally:
            self.posture_task_in_progress = False

    # async def _handle_face_analysis(self, frame_array: np.ndarray, current_time: float) -> None:
    #     if self.face_task_in_progress:
    #         return
    #     self.face_task_in_progress = True
    #     try:
    #         detections = await self._run_in_executor(
    #             self.face_recognition_module.process_frame, frame_array
    #         )
    #         if detections:
    #             self.logger.debug(f"人脸识别: {','.join([d['name'] for d in detections])} ({len(detections)}人)")
    #             anomalies = self._should_send_anomaly("face", detections)
    #             if anomalies:
    #                 await self._emit_result({
    #                     "type": "face",
    #                     "analysis_ts": current_time,
    #                     "data": anomalies,
    #                 })
    #     except Exception as e:
    #         self.logger.error(f"人脸识别处理失败: {e}")
    #     finally:
    #         self.face_task_in_progress = False

    async def _handle_emotion_analysis(self, frame_array: np.ndarray, current_time: float) -> None:
        if self.emotion_task_in_progress:
            return
        self.emotion_task_in_progress = True
        try:
            analysis_frame, scale_x, scale_y = self._resize_for_emotion(frame_array)
            results = await self._run_in_executor(self.emotion_model, analysis_frame, verbose=False)
            detections = self._process_emotion_results(results, scale_x=scale_x, scale_y=scale_y)
            if detections:
                self.logger.debug(
                    f"情绪分析完成: {len(detections)} 个采样结果: " +
                    " ".join([f"({det.get('emotion', 'N/A')}: {det.get('confidence', 0):.2f})" for det in detections])
                )
                anomalies = self._should_send_anomaly("emotion", detections)
                if anomalies:
                    await self._emit_result({
                        "type": "emotion",
                        "analysis_ts": current_time,
                        "data": anomalies,
                    })
        except Exception as e:
            self.logger.error(f"情绪分析处理失败: {e}")
        finally:
            self.emotion_task_in_progress = False
        
    async def process_frame(self, frame_array: np.ndarray, current_time: float, schedule_tasks: bool = True) -> None:
        # 更新帧计数和帧率统计
        self.frame_count += 1
        self.face_frame_counter += 1
        self.emotion_frame_counter += 1
        self.posture_frame_counter += 1
        self.gaze_frame_counter += 1
        if MultiModalConfig.ENABLE_MULTI_MODAL:
            self.multi_modal_frame_counter += 1

        # 每5秒输出一次帧率
        if current_time - self.last_fps_log >= 5.0:
            elapsed = current_time - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            self.logger.info(f"视频处理帧率: {fps:.2f} FPS (总帧数: {self.frame_count})")
            self.last_fps_log = current_time

        if MultiModalConfig.ENABLE_MULTI_MODAL:
            if self.multi_modal_frame_counter >= self.multi_modal_frame_interval:
                self.multi_modal_frame_counter = 0
                self.multi_modal_frame_cache.append((frame_array.copy(), current_time))

        # 进行坐姿分析（根据 analysis_config 控制）
        if (
            self.analysis_config.get("postureAnalysis", SittingPostureConfig.ENABLE_SITTING_POSTURE)
            and self.sitting_posture_predictor
            and self.posture_frame_counter >= self.posture_process_interval
        ):
            self.posture_frame_counter = 0  # 重置计数器
            if not self.posture_task_in_progress:
                if schedule_tasks:
                    asyncio.create_task(self._handle_posture_analysis(frame_array, current_time))
                else:
                    await self._handle_posture_analysis(frame_array, current_time)

        # 根据间隔参数和 analysis_config 决定是否进行人脸识别
        # if (
        #     self.analysis_config.get("faceAnalysis", FaceRecognitionConfig.ENABLE_FACE_RECOGNITION)
        #     and self.face_recognition_module
        #     and self.face_frame_counter >= self.face_process_interval
        # ):
        #     self.face_frame_counter = 0  # 重置计数器
        #     if not self.face_task_in_progress:
        #         if schedule_tasks:
        #             asyncio.create_task(self._handle_face_analysis(frame_array, current_time))
        #         else:
        #             await self._handle_face_analysis(frame_array, current_time)

        # 根据间隔参数和 analysis_config 决定是否进行情绪分析
        if (
            self.analysis_config.get("expressionAnalysis", EmotionConfig.ENABLE_EMOTION)
            and self.emotion_model
            and self.emotion_frame_counter >= self.emotion_process_interval
        ):
            self.emotion_frame_counter = 0  # 重置计数器
            if not self.emotion_task_in_progress:
                if schedule_tasks:
                    asyncio.create_task(self._handle_emotion_analysis(frame_array, current_time))
                else:
                    await self._handle_emotion_analysis(frame_array, current_time)

        # 队列满后触发多模态分析
        if self.analysis_config.get("behaviorAnalysis", MultiModalConfig.ENABLE_MULTI_MODAL) and len(self.multi_modal_frame_cache) >= self.multi_modal_queue_size:
            if not self.multi_modal_in_progress:
                cached_items = list(self.multi_modal_frame_cache)
                self.multi_modal_frame_cache.clear()
                frames = [item[0] for item in cached_items]
                start_ts = cached_items[0][1]
                end_ts = cached_items[-1][1]
                if schedule_tasks:
                    asyncio.create_task(self._run_multi_modal_analysis(frames, start_ts, end_ts))
                else:
                    await self._run_multi_modal_analysis(frames, start_ts, end_ts)

        # ★★★ 视线检测与专注度追踪 ★★★
        if self.gaze_detector and self.gaze_frame_counter >= self.gaze_process_interval:
            self.gaze_frame_counter = 0
            try:
                gaze_result = await self._run_in_executor(self.gaze_detector.detect, frame_array)
                if gaze_result["face_detected"] and self.attention_tracker:
                    # 记录 gaze 数据到注意力追踪器
                    head_pose = gaze_result.get("head_pose", {})
                    is_distracted = (
                        gaze_result.get("is_drowsy", False) or
                        gaze_result.get("is_yawning", False) or
                        gaze_result.get("attention_score", 100) < 30
                    )
                    self.attention_tracker.add_gaze_frame(
                        gaze_offset_x=gaze_result.get("offset", (0, 0))[0],
                        gaze_offset_y=gaze_result.get("offset", (0, 0))[1],
                        head_pitch=head_pose.get("pitch", 0),
                        head_yaw=head_pose.get("yaw", 0),
                        is_distracted=is_distracted,
                    )
                self.logger.debug(
                        f"视线检测: 方向={gaze_result['gaze_direction']}, "
                        f"注意力={gaze_result['attention_level']}({gaze_result['attention_score']}), "
                        f"眨眼={gaze_result['blink_rate']}/min"
                    )
            except Exception as e:
                self.logger.error(f"视线检测失败: {e}")

        if self.display:
            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
            cv2.imshow(self.window_name, frame_array)
            cv2.waitKey(1)


class _FileTrack:
    kind = "video"

    def __init__(self, track_id: str):
        self.id = track_id


async def analyze_video_file(
    file_path: str,
    analysis_config: Optional[Dict[str, Any]] = None,
    video_filename: Optional[str] = None,
) -> None:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"视频文件不存在: {file_path}")

    file_name = os.path.basename(file_path)
    track = _FileTrack(f"file-{file_name}")

    wrapper = VideoWrapper(
        track,
        analysis_config=analysis_config,
        video_filename=video_filename
    )

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {file_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 30.0

    if MultiModalConfig.ENABLE_MULTI_MODAL:
        frames_per_min = max(1, int(MultiModalConfig.MULTI_MODAL_FRAMES_PER_MINUTE))
        request_interval_min = max(1, int(MultiModalConfig.MULTI_MODAL_REQUEST_INTERVAL_MINUTES))
        frame_interval = max(1, int(round(fps * 60.0 / frames_per_min)))
        queue_size = max(1, frames_per_min * request_interval_min)

        wrapper.multi_modal_frame_interval = frame_interval
        wrapper.multi_modal_queue_size = queue_size
        wrapper.multi_modal_frame_cache = deque(maxlen=queue_size)
        wrapper.multi_modal_frame_counter = 0
        wrapper.logger.info(
            "多模态分析器 上传视频抽帧配置: fps=%.2f, 每分钟%d帧, 每%d分钟分析一次, 抽帧间隔=%d帧, 队列大小=%d",
            fps,
            frames_per_min,
            request_interval_min,
            frame_interval,
            queue_size,
        )

    try:
        frame_index = 0
        while True:
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok or frame is None:
                break
            frame_index += 1
            current_time = frame_index / fps
            await wrapper.process_frame(frame, current_time, schedule_tasks=True)
            await asyncio.sleep(0)
    finally:
        cap.release()
        await wrapper.cleanup()

