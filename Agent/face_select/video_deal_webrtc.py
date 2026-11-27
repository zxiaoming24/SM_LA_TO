from aiortc import VideoStreamTrack
import asyncio
import time
import os
import json
from datetime import datetime
from collections import deque
from typing import Dict, Any, List, Tuple, Optional, Callable, Awaitable
import concurrent.futures

import cv2
import numpy as np
from face_recognition.face_recognition_service import create_face_recognition_module
from config import FaceRecognitionConfig, EmotionConfig, SittingPostureConfig, MultiModalConfig, AnomalyDetectionConfig, DatabaseConfig, GazeConfig
from logger import get_logger
from sitting_posture_interface import SittingPosturePredictor
from vllm_analysis import video_chat_async_limit_frame, analyze_learning_with_parse
from insert_sql import DatabaseInserter
from emotion_state_mapper import EmotionStateMapper
from attention_tracker import AttentionTracker
# ★★★ 综合分心检测（来自 eyesss_test_mm）★★★
from eyesss_test_mm.distraction_detector import DistractionDetector as IntegratedDetector
import eyesss_test_mm.config as _mm_config

class VideoWrapper(VideoStreamTrack):
    async def _run_in_executor(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))

    def _should_send_anomaly(self, payload_type: str, data: Any) -> List[str]:
        def _unique(items: List[str]) -> List[str]:
            seen = set()
            result = []
            for item in items:
                if item and item not in seen:
                    seen.add(item)
                    result.append(item)
            return result

        if payload_type == "posture":
            anomalies = []
            if data:
                posture_anomalies = AnomalyDetectionConfig.SITTING_POSTURE_ANOMALIES
                head = data.get("Head")
                hunch = data.get("Hunch")
                cross_leg = data.get("CrossLeg")

                if head in posture_anomalies.get("head", []):
                    anomalies.append(head)
                if hunch in posture_anomalies.get("hunch", []):
                    anomalies.append(hunch)
                if cross_leg in posture_anomalies.get("cross_leg", []):
                    anomalies.append(cross_leg)
            return _unique(anomalies)

        if payload_type == "emotion":
            if not data:
                return []

            anomalies = _unique([
                det.get("emotion")
                for det in data
                if det.get("emotion") in AnomalyDetectionConfig.EMOTION_ANOMALIES
                and float(det.get("confidence", 0)) >= AnomalyDetectionConfig.EMOTION_ANOMALY_CONFIDENCE_THRESHOLD
            ])

            return anomalies

        if payload_type == "face":
            if not data:
                return []

            unknown_threshold = AnomalyDetectionConfig.FACE_RECOGNITION_CONFIDENCE_THRESHOLD
            multiple_faces_anomaly = AnomalyDetectionConfig.FACE_RECOGNITION_ANOMALY_ENABLED
            unknown_face = any(
                (not det.get("is_known"))
                and float(det.get("confidence", 0)) > unknown_threshold
                for det in data
            )
            multiple_faces = multiple_faces_anomaly and len(data) > 1
            anomalies = []
            if unknown_face:
                anomalies.append("unknown_face")
            if multiple_faces:
                anomalies.append("multiple_faces")

            return anomalies

        if payload_type == "multi_modal":
            if not data:
                return []
            if isinstance(data, dict):
                problem_behaviors = data.get("problem_behaviors")
                if not problem_behaviors or problem_behaviors == "无":
                    return []
                if isinstance(problem_behaviors, list):
                    return _unique([str(item) for item in problem_behaviors if item])
                return [str(problem_behaviors)]
            return []

        return []

    async def _run_multi_modal_analysis(self, frames: List[np.ndarray], analysis_ts: float) -> None:
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
                    "analysis_ts": analysis_ts,
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
        result_sender: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        session_id: Optional[str] = None,
        analysis_config: Optional[Dict[str, bool]] = None,
    ):
        super().__init__()
        self.track = track
        self.logger = get_logger(__name__)
        self.window_name = f"VideoWapper_{track.id}"
        self.result_sender = result_sender
        self.session_id = session_id

        # ★★★ 文件日志目录（统一日志文件） ★★★
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
        os.makedirs(self.log_dir, exist_ok=True)
        self._log_file = os.path.join(self.log_dir, f"analysis_{self.session_id or 'unknown'}_{datetime.now().strftime('%Y%m%d')}.log")
        
        # 保存分析配置（如果未提供则使用默认值）
        # ★★★ 修复：默认值使用 config.py 真实配置，而非硬编码 False ★★★
        self.analysis_config = analysis_config or {
            "realtimeHint": False,
            "behaviorAnalysis": MultiModalConfig.ENABLE_MULTI_MODAL,
            "expressionAnalysis": EmotionConfig.ENABLE_EMOTION,
            "postureAnalysis": SittingPostureConfig.ENABLE_SITTING_POSTURE,
            "gazeAnalysis": GazeConfig.ENABLE_GAZE_DETECTION,
        }
        self.logger.info(f"VideoWrapper 分析配置: {self.analysis_config}")
        
        # 提取 interviewId 用于数据库保存
        self.interview_id = self.analysis_config.get("interviewId")
        
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
                self.logger.info(f"数据库连接已建立 [interview_id={self.interview_id}]")
            except Exception as e:
                self.logger.error(f"数据库连接失败: {e}")
                self.db_inserter = None
        
        # 帧率统计
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_log = time.time()
        
        # ★★★ 统一日志汇总：各异步模块将最新结果写入此字典，每5秒集中输出 ★★★
        self._latest_results: Dict[str, Any] = {}
        self._last_unified_log_time = time.time()

        # ★★★ 最新情绪数据缓存（供统一特征更新使用）★★★
        self._latest_emotion_data: Optional[Dict[str, Any]] = None

        # ★★★ 特征更新：累计缓冲 + 5分钟冷却 ★★★
        self._last_feature_update_time = 0.0          # 上次LLM更新的时间戳
        self._feature_update_interval = 300            # 5分钟冷却（秒）
        self._feature_update_buffer: List[Dict] = []   # 累积的检测数据快照

        # ★★★ 专注度会话定期持久化（每30秒写一次 profile JSON）★★★
        self._last_session_flush_time = time.time()
        self._session_flush_interval = 30  # 每30秒结算一次

        # 异步分析线程池（增加线程数以支持多个并发任务）
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        # 分析任务状态
        self.posture_task_in_progress = False
        self.face_task_in_progress = False
        self._integrated_task_in_progress = False
        # 坐姿分析处理控制
        self.posture_frame_counter = 0
        self.posture_process_interval = SittingPostureConfig.SITTING_POSTURE_FRAMES
        
        # 人脸识别处理控制
        self.face_frame_counter = 0
        self.face_process_interval = FaceRecognitionConfig.FACE_RECOGNITION_FRAMES
        
        # ★★★ 综合检测帧控制 ★★★
        self.integrated_frame_counter = 0
        self.integrated_process_interval = EmotionConfig.EMOTION_FRAMES

        # 多模态分析处理控制
        self.multi_modal_frame_counter = 0
        self.multi_modal_frame_interval = MultiModalConfig.MULTI_MODAL_FRAME_INTERVAL
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
        
        # 初始化人脸识别模块
        self.face_recognition_module = None
        if FaceRecognitionConfig.ENABLE_FACE_RECOGNITION:
            try:
                face_config = {
                    "threshold": FaceRecognitionConfig.FACE_DETECTION_THRESHOLD,
                    "database_path": FaceRecognitionConfig.FACE_DATABASE_PATH
                }
                self.face_recognition_module = create_face_recognition_module(face_config)
                if self.face_recognition_module:
                    self.logger.info(f"VideoWapper 人脸识别模块初始化成功 [track_id={track.id}]")
                    self.logger.info(f"人脸识别处理间隔: 每 {self.face_process_interval} 帧处理一次")
                else:
                    self.logger.warning(f"VideoWapper 人脸识别模块初始化失败 [track_id={track.id}]")
            except Exception as e:
                self.logger.error(f"VideoWapper 初始化人脸识别模块失败: {e}")
        
        # ★★★ 初始化情绪状态映射器（独立于检测模型）★★★
        self.emotion_state_mapper = EmotionStateMapper() if EmotionConfig.ENABLE_EMOTION else None

        # 初始化姿势预测器
        if SittingPostureConfig.ENABLE_SITTING_POSTURE:
            self.sitting_posture_predictor = SittingPosturePredictor()

        # ★★★ 初始化综合分心检测器（替代独立的 gaze_detector + YOLO emotion）★★★
        self.integrated_detector = None
        self.attention_tracker = None
        self.integrated_frame_counter = 0
        self.integrated_process_interval = EmotionConfig.EMOTION_FRAMES
        # ★★★ 资源上下文跟踪 ★★★
        # 计算项目根目录：video_deal_webrtc.py → Agent/face-select/ → Agent/ → 项目根目录
        _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._resource_context_path = os.path.join(
            _PROJECT_ROOT,
            "data", "user_context", f"{(self.interview_id if self.interview_id else str(self.track.id))}.json"
        )
        self._last_resource_type = "video"
        self._resource_check_counter = 0

        if GazeConfig.ENABLE_GAZE_DETECTION:
            try:
                # ★★★ 启用 YOLO 物品检测（yolov8n.pt 自动下载）★★★
                _mm_config.ObjectConfig.ENABLE_OBJECT_DETECTION = True
                _mm_config.EmotionConfig.ENABLE_EMOTION_DETECTION = EmotionConfig.ENABLE_EMOTION
                self.integrated_detector = IntegratedDetector(enable_llm=False)
                self.logger.info(f"综合分心检测器初始化成功 [track_id={track.id}]")
                
                if GazeConfig.ENABLE_ATTENTION_TRACKING:
                    self.attention_tracker = AttentionTracker()
                    self.logger.info(f"专注度追踪器初始化成功 [track_id={track.id}]")
                    # ★★★ 读取真实资源上下文，启动专注度追踪会话 ★★★
                    user_id = self.interview_id or str(self.track.id)
                    resource_type = self._load_resource_context() or "video"
                    self._last_resource_type = resource_type
                    self.attention_tracker.on_enter(user_id, resource_type, resource_id=str(self.track.id))
                    self.logger.info(f"专注度追踪会话已启动 [user_id={user_id}, resource_type={resource_type}]")
            except Exception as e:
                self.logger.error(f"综合分心检测器初始化失败: {e}", exc_info=True)

        # 视频保存相关
        self.video_writer = None
        self.video_path = None
        self._init_video_writer()

    def _init_video_writer(self) -> None:
        """初始化视频写入器（如果interviewId存在）"""
        try:
            interview_id = self.analysis_config.get("interviewId")
            if not interview_id:
                self.logger.info("未提供 interviewId，跳过视频保存")
                return
            
            # 创建视频保存目录（在当前文件所在目录下）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            save_dir = os.path.join(current_dir, "recorded_videos")
            os.makedirs(save_dir, exist_ok=True)
            
            # 使用 session_id、interviewId 和 track.id 命名视频文件
            video_filename = f"{self.session_id}_{interview_id}_{self.track.id}.mp4"
            self.video_path = os.path.join(save_dir, video_filename)
            
            # 视频参数设置
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 10  # 默认10帧
            frame_size = (640, 480)  # 默认分辨率，会在第一帧时更新
            
            self.video_writer = cv2.VideoWriter(self.video_path, fourcc, fps, frame_size)
            self.logger.info(f"视频保存已启用: {self.video_path}")
            
        except Exception as e:
            self.logger.error(f"初始化视频写入器失败: {e}", exc_info=True)
            self.video_writer = None
    
    def _write_frame(self, frame: np.ndarray) -> None:
        """写入帧到视频文件"""
        if self.video_writer is None:
            return
        
        try:
            # 如果是第一帧，根据实际帧大小重新初始化写入器
            if self.frame_count == 1 and frame.shape[:2] != (480, 640):
                h, w = frame.shape[:2]
                self.video_writer.release()
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(self.video_path, fourcc, 10, (w, h))
                self.logger.info(f"视频写入器已更新为实际分辨率: {w}x{h}")
            
            self.video_writer.write(frame)
        except Exception as e:
            self.logger.error(f"写入视频帧失败: {e}", exc_info=True)
    
    async def cleanup(self) -> None:
        """清理资源，释放视频写入器和数据库连接"""
        # ★★★ 先断开 result_sender，防止关闭过程中再发送 ★★★
        self.result_sender = None

        try:
            if self.video_writer is not None:
                self.video_writer.release()
                self.logger.info(f"视频已保存: {self.video_path}")
                self.video_writer = None
        except Exception as e:
            self.logger.error(f"释放视频写入器失败: {e}", exc_info=True)

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
                self.logger.info(f"数据库连接已关闭 [interview_id={self.interview_id}]")
                self.db_inserter = None
        except Exception as e:
            self.logger.error(f"关闭数据库连接失败: {e}", exc_info=True)

        # ★★★ 结束专注度追踪会话 ★★★
        try:
            if GazeConfig.ENABLE_ATTENTION_TRACKING and self.attention_tracker:
                user_id = self.interview_id or str(self.track.id)
                result = self.attention_tracker.on_leave(user_id)
                if result:
                    self.logger.info(f"专注度追踪会话已结束 [user_id={user_id}, immersion_score={result.get('immersion_score', 0):.2f}]")
                self.attention_tracker = None
        except Exception as e:
            self.logger.error(f"结束专注度追踪会话失败: {e}", exc_info=True)

        # ★★★ 关闭综合分心检测器 ★★★
        try:
            if self.integrated_detector is not None:
                # DistractionDetector 内部有 MediaPipe FaceMesh，需要释放
                if hasattr(self.integrated_detector, 'gaze_detector') and self.integrated_detector.gaze_detector:
                    self.integrated_detector.gaze_detector.close()
                self.integrated_detector = None
        except Exception as e:
            self.logger.error(f"关闭综合检测器失败: {e}", exc_info=True)

    async def _emit_result(self, payload: Dict[str, Any]) -> None:
        # ★★★ 清洗 payload 确保所有类型 JSON 可序列化 ★★★
        payload = self._sanitize_for_json(payload)
        # 保存到数据库（使用 interviewId 作为 session_id）
        if self.db_inserter and self.interview_id:
            try:
                payload_type = payload.get("type")
                payload_data = payload.get("data")
                analysis_ts = payload.get("analysis_ts")
                
                # 提取关键判断字段用于比较
                key_data = self._extract_key_data(payload_type, payload_data)
                key_data_json = json.dumps(key_data, ensure_ascii=False, sort_keys=True)
                
                # 生成当前分析结果的key（用于判断是否相同）
                result_key = f"{payload_type}"
                
                # 检查是否与上一次的结果相同
                last_result = self.last_analysis_result.get(result_key)
                is_same_result = (last_result is not None and last_result == key_data_json)
                
                if is_same_result:
                    # 结果相同，更新上一次结果的结束时间
                    self.db_inserter.update_analysis_data(
                        session_id=self.interview_id,
                        type=payload_type,
                        end_analysis_ts=str(analysis_ts)
                    )
                    self.logger.debug(f"更新分析结果结束时间 [type={payload_type}]")
                else:
                    # 结果不同或首次，插入新记录
                    self.db_inserter.insert_analysis_data(
                        session_id=self.interview_id,
                        type=payload_type,
                        start_analysis_ts=str(analysis_ts),
                        end_analysis_ts=str(analysis_ts),
                        data=json.dumps(payload_data, ensure_ascii=False)
                    )
                    # 更新上一次的结果记录
                    self.last_analysis_result[result_key] = key_data_json
                    self.logger.debug(f"插入新的分析结果 [type={payload_type}]")
                    
            except Exception as e:
                self.logger.error(f"保存到数据库失败: {e}")

        # ★★★ 写入文件日志 ★★★
        payload_type = payload.get("type", "unknown")
        payload_data = payload.get("data")
        analysis_ts = payload.get("analysis_ts", time.time())
        if payload_data is not None:
            self._write_analysis_log(payload_type, payload_data, analysis_ts)

        # 发送分析结果
        if not self.result_sender:
            return
        try:
            await self.result_sender(payload)
        except Exception as e:
            self.logger.debug(f"发送分析结果失败: {e}")
    
    def _extract_key_data(self, payload_type: str, data: Any) -> dict:
        """提取用于判断结果是否相同的关键数据字段"""
        if isinstance(data, list):
            return {"anomalies": data}
        if payload_type == "posture":
            # 只提取坐姿判断的关键字段
            return {
                "Head": data.get("Head") if data else None,
                "Hunch": data.get("Hunch") if data else None,
                "CrossLeg": data.get("CrossLeg") if data else None,
            }
        
        elif payload_type == "emotion":
            # 只提取情绪判断的关键信息（emotion和confidence）
            if not data:
                return {"detections": []}
            return {
                "detections": [
                    {
                        "emotion": det.get("emotion"),
                        "confidence": det.get("confidence")
                    }
                    for det in data
                ]
            }
        
        elif payload_type == "face":
            # 只提取人脸识别的关键信息（检测到的人脸名字）
            if not data:
                return {"names": []}
            return {
                "names": sorted([d.get("name", "") for d in data])
            }
        
        elif payload_type == "multi_modal":
            # 只提取多模态分析的关键字段
            if not isinstance(data, dict):
                return {"problem_behaviors": None}
            return {
                "problem_behaviors": data.get("problem_behaviors")
            }
        
        else:
            # 其他类型返回整个数据
            return {"data": data}

    async def _handle_posture_analysis(self, frame_array: np.ndarray, current_time: float) -> None:
        if self.posture_task_in_progress:
            return
        self.posture_task_in_progress = True
        try:
            annotated_frame, posture_results = await self._run_in_executor(
                self.sitting_posture_predictor.process_frame, frame_array
            )
            if posture_results:
                # ★★★ 写入共享字典，供统一日志汇总使用 ★★★
                self._latest_results["posture"] = {
                    "头部": posture_results.get("Head", "N/A"),
                    "塌腰": posture_results.get("Hunch", "N/A"),
                    "翘腿": posture_results.get("CrossLeg", "N/A"),
                }
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

    async def _handle_face_analysis(self, frame_array: np.ndarray, current_time: float) -> None:
        if self.face_task_in_progress:
            return
        self.face_task_in_progress = True
        try:
            detections = await self._run_in_executor(
                self.face_recognition_module.process_frame, frame_array
            )
            if detections:
                self.logger.debug(f"人脸识别: {','.join([d['name'] for d in detections])} ({len(detections)}人)")
                anomalies = self._should_send_anomaly("face", detections)
                if anomalies:
                    await self._emit_result({
                        "type": "face",
                        "analysis_ts": current_time,
                        "data": anomalies,
                    })
        except Exception as e:
            self.logger.error(f"人脸识别处理失败: {e}")
        finally:
            self.face_task_in_progress = False

    @staticmethod
    def _sanitize_for_json(obj: Any) -> Any:
        """递归将 numpy 类型转换为 Python 原生类型，确保 JSON 可序列化"""
        if isinstance(obj, dict):
            return {k: VideoWrapper._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [VideoWrapper._sanitize_for_json(v) for v in obj]
        elif isinstance(obj, tuple):
            return tuple(VideoWrapper._sanitize_for_json(v) for v in obj)
        elif hasattr(obj, 'dtype'):  # numpy scalar (bool_, int_, float_ etc.)
            return obj.item()
        return obj

    async def _handle_integrated_analysis(self, frame_array: np.ndarray, current_time: float) -> None:
        """
        综合检测入口（替代独立的 _handle_gaze_analysis + _handle_emotion_analysis）
        使用 eyesss_test_mm 的 DistractionDetector 统一运行：
          - 视线检测 + 瞌睡 + 哈欠 + 眨眼
          - 情绪检测
          - 行为规则分心判定
        然后将结果分发到 AttentionTracker、EmotionStateMapper、WebSocket、DB
        """
        try:
            result = await self.integrated_detector.async_detect(frame_array)
            # ★★★ 递归清洗所有 numpy 类型为 Python 原生类型，确保 JSON 可序列化 ★★★
            result = self._sanitize_for_json(result)
            gaze_data = result.get("gaze", {})
            emotion_data = result.get("emotion", {})
            final_result = result.get("final_result", {})

            # ============================================================
            # 1️⃣ 视线数据 → 写入 _latest_results + AttentionTracker + 前端
            # ============================================================
            if gaze_data.get("face_detected"):
                # eyesss_test_mm 的 gaze_direction 是中文，统一标准化
                gd = gaze_data.get("gaze_direction", "未知")
                is_distracted_gaze = gd not in ("居中", "center")
                attn_lv = gaze_data.get("attention_level", "中")
                attn_sc = gaze_data.get("attention_score", 0)
                blink_r = gaze_data.get("blink_rate", 0)
                is_drowsy = gaze_data.get("is_drowsy", False)
                drowsy_sc = gaze_data.get("drowsiness_score", 0.0)
                is_yawning = gaze_data.get("is_yawning", False)

                # 写入共享字典（统一日志用）
                self._latest_results["gaze"] = {
                    "方向": gd,
                    "注意力": attn_lv,
                    "分数": attn_sc,
                    "眨眼": blink_r,
                    "瞌睡": "是" if is_drowsy else "否",
                    "瞌睡分": round(drowsy_sc, 2),
                    "哈欠": "是" if is_yawning else "否",
                }

                # AttentionTracker（使用直接返回的 gaze_offset，eyesss_test_mm 无 iris_position）
                if GazeConfig.ENABLE_ATTENTION_TRACKING and self.attention_tracker:
                    user_id = self.interview_id or str(self.track.id)
                    avg_ox = gaze_data.get("gaze_offset_x", 0.0)
                    avg_oy = gaze_data.get("gaze_offset_y", 0.0)
                    hp = gaze_data.get("head_pose", {"pitch": 0, "yaw": 0, "roll": 0})
                    self.attention_tracker.add_gaze(
                        user_id=user_id,
                        gaze_offset_x=avg_ox,
                        gaze_offset_y=avg_oy,
                        head_pitch=hp["pitch"],
                        head_yaw=hp["yaw"],
                        is_distracted=is_distracted_gaze,
                        timestamp=current_time
                    )

                    # ★★★ 会话定期持久化：每30秒结算一次，写入 profile JSON ★★★
                    if current_time - self._last_session_flush_time >= self._session_flush_interval:
                        self._last_session_flush_time = current_time
                        session_info = self.attention_tracker.get_current_session(user_id)
                        if session_info and session_info.get("elapsed", 0) >= 15:
                            # 结束当前会话并写入 AttentionProfile
                            result_leave = self.attention_tracker.on_leave(user_id)
                            if result_leave and result_leave.get("valid"):
                                imm = result_leave["immersion_score"]
                                rtype = result_leave.get("resource_type", "video")
                                self.logger.info(
                                    f"📊 专注度会话结算 [user_id={user_id} "
                                    f"type={rtype} immersion={imm:.3f} "
                                    f"duration={result_leave.get('duration', 0):.1f}s "
                                    f"frames={result_leave.get('details', {}).get('frames', 0)}]"
                                )
                                self._latest_results["profile_flush"] = {
                                    "type": rtype,
                                    "immersion_score": round(imm, 3),
                                }
                            # 开启新会话（保持相同 resource_type）
                            new_rtype = session_info.get("resource_type", "video")
                            self.attention_tracker.on_enter(user_id, new_rtype)

                # 前端 WebSocket
                payload = {
                    "type": "gaze",
                    "analysis_ts": current_time,
                    "data": {
                        "gaze_direction": gd,
                        "attention_level": attn_lv,
                        "attention_score": attn_sc,
                        "blink_rate": blink_r,
                        "is_distracted": is_distracted_gaze,
                        "is_yawning": is_yawning,
                        "is_drowsy": is_drowsy,
                        "drowsiness_score": round(drowsy_sc, 3),
                    }
                }
                if self.result_sender:
                    await self.result_sender(payload)

                # 文件日志
                self._write_gaze_log(gaze_data, current_time)

            # ============================================================
            # 2️⃣ 情绪数据 → 写入 _latest_results + EmotionStateMapper + 异常
            # ============================================================
            if emotion_data.get("emotion_detected"):
                emo_name = emotion_data.get("emotion", "neutral")
                emo_conf = emotion_data.get("confidence", 0.0)
                self._latest_results["emotion"] = {
                    "情绪": emo_name,
                    "置信度": round(emo_conf, 3),
                }
                self.logger.debug(
                    f"综合检测-情绪: {emo_name}({emo_conf:.3f}) "
                    f"状态={emotion_data.get('state', '未知')}"
                )

                # EmotionStateMapper → 统一特征更新（后续在综合分析末尾统一调用）
                if self.emotion_state_mapper:
                    self._latest_emotion_data = {
                        "emotion": emo_name,
                        "confidence": emo_conf,
                    }

                # 情绪异常检测
                fake_detections = [{"emotion": emo_name, "confidence": emo_conf}]
                anomalies = self._should_send_anomaly("emotion", fake_detections)
                if anomalies:
                    await self._emit_result({
                        "type": "emotion",
                        "analysis_ts": current_time,
                        "data": anomalies,
                    })

            # ============================================================
            # 🔺 物品检测结果 → 写入 _latest_results + 前端
            # ============================================================
            objects_data = result.get("objects", {})
            all_objs = objects_data.get("objects") or []
            if all_objs:
                dist_objs = objects_data.get("distraction_objects") or []
                obj_names = [str(o.get("name", o.get("class_id", "?"))) for o in all_objs]
                dist_names = [str(o.get("name", o.get("class_id", "?"))) for o in dist_objs]
                self._latest_results["objects"] = {
                    "物品": obj_names,
                    "分心物品": dist_names,
                }
                # 发送前端
                if self.result_sender:
                    await self.result_sender({
                        "type": "object",
                        "analysis_ts": current_time,
                        "data": {
                            "objects": all_objs,
                            "distraction_objects": dist_objs,
                            "has_distraction": objects_data.get("has_distraction", False),
                        }
                    })

            # ============================================================
            # 3️⃣ DistractionDetector 分心结论 → 日志 + 前端
            # ============================================================
            if final_result:
                self._latest_results["distraction"] = {
                    "分心": final_result.get("is_distracted", False),
                    "等级": final_result.get("distraction_level", "none"),
                    "分数": final_result.get("attention_score", 100),
                    "原因": final_result.get("reasons", []),
                }
                # 发到前端（综合状态）
                if self.result_sender:
                    await self.result_sender({
                        "type": "distraction",
                        "analysis_ts": current_time,
                        "data": {
                            "is_distracted": final_result["is_distracted"],
                            "distraction_level": final_result["distraction_level"],
                            "attention_score": final_result["attention_score"],
                            "reasons": final_result["reasons"],
                            "suggestions": final_result["suggestions"],
                        }
                    })

            # ============================================================
            # 4️⃣ 累积检测数据，每5分钟触发一次8维度特征更新
            # ============================================================
            # 把当前帧的快照加入缓冲区
            snapshot = {
                "timestamp": current_time,
                "emotion": (self._latest_emotion_data or {}).copy(),
                "gaze": {
                    "is_drowsy": gaze_data.get("is_drowsy", False),
                    "drowsiness_score": gaze_data.get("drowsiness_score", 0.0),
                    "is_yawning": gaze_data.get("is_yawning", False),
                    "perclos": gaze_data.get("perclos", 0.0),
                    "blink_rate": gaze_data.get("blink_rate", 0),
                    "gaze_direction": gaze_data.get("gaze_direction", "未知"),
                    "attention_score": gaze_data.get("attention_score", 0),
                    "head_yaw": gaze_data.get("head_pose", {}).get("yaw", 0),
                    "head_pitch": gaze_data.get("head_pose", {}).get("pitch", 0),
                },
                "distraction": {
                    "is_distracted": final_result.get("is_distracted", False) if final_result else False,
                    "distraction_level": final_result.get("distraction_level", "none") if final_result else "none",
                    "attention_score": final_result.get("attention_score", 100) if final_result else 100,
                    "reasons": final_result.get("reasons", []) if final_result else [],
                },
            }
            self._feature_update_buffer.append(snapshot)
            # 缓冲区最多保留 3000 条（约2分钟@25fps）
            if len(self._feature_update_buffer) > 3000:
                self._feature_update_buffer = self._feature_update_buffer[-3000:]

            # 检查是否达到5分钟冷却 + 有情绪数据 + 缓冲区够量
            if (self._latest_emotion_data is not None
                    and current_time - self._last_feature_update_time >= self._feature_update_interval
                    and len(self._feature_update_buffer) >= 30):  # 至少30帧才有统计意义
                await self._update_features_from_detection(
                    buffer=self._feature_update_buffer,
                    current_time=current_time,
                )
                self._last_feature_update_time = current_time
                self._feature_update_buffer = []  # 清空缓冲区
                self._latest_emotion_data = None

        except Exception as e:
            self.logger.error(f"综合检测失败: {e}", exc_info=True)
        finally:
            self._integrated_task_in_progress = False

    async def _update_features_from_detection(
        self,
        buffer: List[Dict[str, Any]],
        current_time: float,
    ) -> None:
        """
        累积检测数据 → DynamicFeatureUpdater（8维度特征统一更新）

        将过去5分钟内累积的所有检测快照汇总为统计摘要，
        一次发给 LLM 进行智能特征调整，避免频繁调用。

        Args:
            buffer: 累积的检测快照列表，每帧一条
            current_time: 当前时间戳
        """
        try:
            import sys
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.dirname(parent_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)

            from children_agent.dynamic_feature_updater import DynamicFeatureUpdater

            user_id = self.session_id or "anonymous"
            feature_file = os.path.join(parent_dir, "children_agent",
                                         "user_features", f"{user_id}.json")
            if not os.path.exists(feature_file):
                self.logger.debug(f"特征文件不存在，跳过特征更新: {feature_file}")
                return

            with open(feature_file, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            current_features = file_data.get('current_features', {})
            if not current_features:
                return

            # ── 1. 汇总缓冲区数据为统计摘要 ──
            total = len(buffer)
            emotions_seen = {}
            distracted_count = 0
            drowsy_count = 0
            yawn_count = 0
            attn_scores = []
            drowsy_scores = []
            perclos_values = []
            blink_rates = []
            head_yaws = []
            head_pitches = []
            distraction_reasons_all = []

            for snap in buffer:
                emo = snap.get("emotion", {})
                emo_name = emo.get("emotion", "neutral")
                emo_conf = emo.get("confidence", 0.0)
                emotions_seen[emo_name] = emotions_seen.get(emo_name, 0) + 1

                gaze = snap.get("gaze", {})
                if gaze.get("is_drowsy"):
                    drowsy_count += 1
                if gaze.get("is_yawning"):
                    yawn_count += 1
                drowsy_scores.append(gaze.get("drowsiness_score", 0.0))
                perclos_values.append(gaze.get("perclos", 0.0))
                blink_rates.append(gaze.get("blink_rate", 0))
                head_yaws.append(abs(gaze.get("head_yaw", 0)))
                head_pitches.append(abs(gaze.get("head_pitch", 0)))

                dist = snap.get("distraction", {})
                if dist.get("is_distracted"):
                    distracted_count += 1
                attn_scores.append(dist.get("attention_score", 100))
                distraction_reasons_all.extend(dist.get("reasons", []))

            # 主导情绪（出现最多的）
            dominant_emotion = max(emotions_seen, key=emotions_seen.get) if emotions_seen else "neutral"
            emotion_confidence = emotions_seen.get(dominant_emotion, 1) / total if total > 0 else 0.5

            # 平均/占比统计
            distracted_ratio = distracted_count / total if total > 0 else 0
            drowsy_ratio = drowsy_count / total if total > 0 else 0
            avg_attn = sum(attn_scores) / len(attn_scores) if attn_scores else 100
            avg_drowsy = sum(drowsy_scores) / len(drowsy_scores) if drowsy_scores else 0.0
            avg_perclos = sum(perclos_values) / len(perclos_values) if perclos_values else 0.0
            avg_head_yaw = sum(head_yaws) / len(head_yaws) if head_yaws else 0
            avg_head_pitch = sum(head_pitches) / len(head_pitches) if head_pitches else 0
            max_head_yaw = max(head_yaws) if head_yaws else 0
            max_head_pitch = max(head_pitches) if head_pitches else 0

            # 去重的分心原因
            unique_reasons = list(set(distraction_reasons_all))[:5]

            # ── 2. EmotionStateMapper 计算情绪影响（用主导情绪）──
            detections = [{"emotion": dominant_emotion, "confidence": emotion_confidence}]
            emotion_result = self.emotion_state_mapper.process_emotion_detection(
                detections, current_features
            ) if self.emotion_state_mapper else {}
            emotional_update = emotion_result.get('emotional_state_update', {})
            detected_emo = emotion_result.get('detected_emotion', {})
            recommendation = emotion_result.get('recommendation', '')

            # ── 3. 构建摘要性能数据 ──
            time_range_sec = current_time - (buffer[0]["timestamp"] if buffer else current_time)
            performance_data = {
                "统计周期_秒": round(time_range_sec, 0),
                "总分析帧数": total,
                "主导情绪": f"{dominant_emotion}(占比{emotion_confidence:.0%})",
                "情绪分布": str(emotions_seen),
                "分心帧占比": f"{distracted_ratio:.1%}",
                "平均专注度分数": round(avg_attn, 1),
                "瞌睡帧占比": f"{drowsy_ratio:.1%}",
                "平均瞌睡分数": round(avg_drowsy, 3),
                "平均PERCLOS": round(avg_perclos, 4),
                "打哈欠总帧数": yawn_count,
                "平均头部偏转角_度": round(avg_head_yaw, 1),
                "最大头部偏转角_度": round(max_head_yaw, 1),
                "平均低头角_度": round(avg_head_pitch, 1),
                "最大低头角_度": round(max_head_pitch, 1),
                "主要分心原因": unique_reasons,
            }

            task_content = (
                f"过去{time_range_sec:.0f}秒摄像头检测汇总："
                f"主导情绪={dominant_emotion}，"
                f"分心帧占比={distracted_ratio:.0%}（平均专注度{avg_attn:.0f}），"
                f"瞌睡帧占比={drowsy_ratio:.0%}（平均{drowsy_ratio:.2f}），"
                f"平均PERCLOS={avg_perclos:.3f}，"
                f"最大转头角={max_head_yaw:.0f}°"
            )

            # ── 4. 调用 DynamicFeatureUpdater 的 LLM 智能更新 ──
            updater = DynamicFeatureUpdater()
            updated = await updater.update_features_async(
                current_features=current_features,
                task_type="emotion_detection",
                task_content=task_content,
                performance_data=performance_data,
                completion_quality="medium",
                time_spent=f"{time_range_sec:.0f}秒实时检测",
                user_id=user_id,
            )

            if updated.get("status") != "success":
                self.logger.warning(f"特征LLM更新未返回成功: {updated.get('status', '未知')}，回退到直接磁盘更新")
                if emotional_update:
                    import copy
                    updated_features = copy.deepcopy(current_features)
                    updated_features['emotional_state'] = emotional_update
                    update_history = file_data.get('update_history', [])
                    update_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "user_id": user_id,
                        "metadata": {
                            "task_type": "emotion_detection",
                            "source": "yolo_realtime_aggregated",
                            "detected_emotion": detected_emo,
                            "recommendation": recommendation,
                        }
                    })
                    with open(feature_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "current_features": updated_features,
                            "last_updated": datetime.now().isoformat(),
                            "update_count": len(update_history),
                            "update_history": update_history,
                        }, f, ensure_ascii=False, indent=2)

            self.logger.info(
                f"8维度特征更新 [周期={time_range_sec:.0f}s 帧数={total} "
                f"情绪={dominant_emotion} "
                f"分心占比={distracted_ratio:.0%} 专注度={avg_attn:.0f} "
                f"瞌睡占比={drowsy_ratio:.0%}]"
            )

            # ── 5. 发送前端通知 ──
            await self._emit_result({
                "type": "feature_update",
                "analysis_ts": current_time,
                "data": {
                    "user_id": user_id,
                    "update_interval_seconds": round(time_range_sec),
                    "total_frames": total,
                    "detection_summary": {
                        "dominant_emotion": dominant_emotion,
                        "distracted_ratio": round(distracted_ratio, 3),
                        "drowsy_ratio": round(drowsy_ratio, 3),
                        "avg_attention_score": round(avg_attn, 1),
                    },
                    "emotional_state_update": emotional_update,
                    "recommendation": recommendation,
                }
            })

        except Exception as e:
            self.logger.error(f"统一特征更新失败: {e}", exc_info=True)

    # ======================================================================
    # 文件日志
    # ======================================================================
    def _write_gaze_log(self, gaze_result: dict, ts: float) -> None:
        """将视线检测结果写入文件日志"""
        try:
            line = (
                f"[{datetime.fromtimestamp(ts).isoformat()}] "
                f"GAZE | dir={gaze_result.get('gaze_direction', 'N/A')} "
                f"attn={gaze_result.get('attention_level', 'N/A')}({gaze_result.get('attention_score', 0)}) "
                f"blink={gaze_result.get('blink_rate', 0)}/min "
                f"yawn={gaze_result.get('is_yawning', False)} "
                f"drowsy={gaze_result.get('is_drowsy', False)}({gaze_result.get('drowsiness_score', 0):.2f})\n"
            )
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _write_analysis_log(self, payload_type: str, data: Any, ts: float) -> None:
        """将各类分析结果写入文件日志"""
        try:
            line = (
                f"[{datetime.fromtimestamp(ts).isoformat()}] "
                f"{payload_type.upper()} | {json.dumps(data, ensure_ascii=False)}\n"
            )
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    # =====================================================================
    # 资源上下文感知（读取共享文件，获取用户当前查看的资源类型）
    # =====================================================================
    def set_user_id(self, user_id: str):
        """
        设置前端真实 userId（由 WebSocket register 透传）。
        覆盖 interviewId，确保 AttentionProfile 使用正确的 userId。
        """
        old_user_id = self.interview_id or str(self.track.id)
        if user_id == old_user_id:
            return

        self.logger.info(f"userId 更新: {old_user_id} → {user_id}")

        # 1. 更新 userId 引用
        self.interview_id = user_id

        # 2. 更新资源上下文文件路径
        _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._resource_context_path = os.path.join(
            _PROJECT_ROOT,
            "data", "user_context", f"{user_id}.json"
        )

        # 3. 如果专注度追踪已启动，需切换会话 userId
        if self.attention_tracker and self.attention_tracker.has_active_session(old_user_id):
            old_result = self.attention_tracker.on_leave(old_user_id)
            if old_result:
                self.logger.info(
                    f"userId 切换结束旧会话, 沉浸分={old_result.get('immersion_score', 0):.2f}"
                )
            # 读取当前资源类型，开启新会话
            resource_type = self._load_resource_context() or "video"
            self.attention_tracker.on_enter(user_id, resource_type, resource_id=str(self.track.id))
            self.logger.info(f"userId 切换后新会话已启动 [user_id={user_id}, resource_type={resource_type}]")

    def _load_resource_context(self) -> Optional[str]:
        """
        读取共享资源上下文文件，返回 resource_type。
        如果文件不存在或无效，返回 None（使用默认值）。
        """
        try:
            if not os.path.exists(self._resource_context_path):
                return None
            with open(self._resource_context_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rtype = data.get("resource_type", "")
            return rtype if rtype else None
        except Exception:
            return None

    def _check_resource_context(self):
        """
        周期性检查资源上下文是否变化。
        如果用户切换了资源类型（如 video → practice），
        自动结束旧会话并开始新会话。
        """
        if not self.attention_tracker:
            return
        rtype = self._load_resource_context()
        if rtype and rtype != self._last_resource_type:
            user_id = self.interview_id or str(self.track.id)
            # 结束旧会话（写入 AttentionProfile）
            old_result = self.attention_tracker.on_leave(user_id)
            if old_result:
                self.logger.info(
                    f"资源切换: {self._last_resource_type} → {rtype}, "
                    f"沉浸分={old_result.get('immersion_score', 0):.2f}"
                )
            # 开始新会话
            self.attention_tracker.on_enter(user_id, rtype, resource_id=str(self.track.id))
            self._last_resource_type = rtype
            self.logger.info(f"资源上下文已切换: resource_type={rtype}")
        elif rtype and self._last_resource_type == "video" and rtype != "video":
            # 首次从默认值切换到真实资源类型
            user_id = self.interview_id or str(self.track.id)
            self.logger.info(f"🎯 文件桥梁首次接通！resource_type={rtype}, user_id={user_id}")

    async def recv(self):
        try:
            frame = await self.track.recv()
            frame_array = frame.to_ndarray(format="bgr24")
        except Exception as e:
            self.logger.error(f"接收视频帧失败: {e}")
            raise
        
        # 更新帧计数和帧率统计
        self.frame_count += 1
        self.face_frame_counter += 1
        self.posture_frame_counter += 1
        self.integrated_frame_counter += 1
        if MultiModalConfig.ENABLE_MULTI_MODAL:
            self.multi_modal_frame_counter += 1
        current_time = time.time()
        
        # 保存视频帧
        self._write_frame(frame_array)
        
        # 每5秒输出一次帧率
        if current_time - self.last_fps_log >= 5.0:
            elapsed = current_time - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            self.logger.info(f"WebRTC 接收帧率: {fps:.2f} FPS (总帧数: {self.frame_count})")
            self.last_fps_log = current_time
        
        if MultiModalConfig.ENABLE_MULTI_MODAL:
            if self.multi_modal_frame_counter >= self.multi_modal_frame_interval:
                self.multi_modal_frame_counter = 0
                self.multi_modal_frame_cache.append(frame_array.copy())
        # 进行坐姿分析（根据 analysis_config 控制）
        if self.analysis_config.get("postureAnalysis", SittingPostureConfig.ENABLE_SITTING_POSTURE) and SittingPostureConfig.ENABLE_SITTING_POSTURE and self.sitting_posture_predictor and self.posture_frame_counter >= self.posture_process_interval:
            self.posture_frame_counter = 0  # 重置计数器
            if not self.posture_task_in_progress:
                asyncio.create_task(self._handle_posture_analysis(frame_array, current_time))
        
        # 根据间隔参数和 analysis_config 决定是否进行人脸识别
        if FaceRecognitionConfig.ENABLE_FACE_RECOGNITION  and self.face_recognition_module and self.face_frame_counter >= self.face_process_interval:
            self.face_frame_counter = 0  # 重置计数器
            if not self.face_task_in_progress:
                asyncio.create_task(self._handle_face_analysis(frame_array, current_time))
        
        # ★★★ 综合检测（视线 + 情绪 + 分心判定，替代独立的 gaze / emotion 分支）★★★
        if (self.analysis_config.get("gazeAnalysis", GazeConfig.ENABLE_GAZE_DETECTION) 
            and self.integrated_detector 
            and self.integrated_frame_counter >= self.integrated_process_interval):
            self.integrated_frame_counter = 0
            if not getattr(self, '_integrated_task_in_progress', False):
                self._integrated_task_in_progress = True
                asyncio.create_task(self._handle_integrated_analysis(frame_array, current_time))

        # ★★★ 资源上下文检查（每 ~100 帧检查一次，约 3 秒）★★★
        self._resource_check_counter += 1
        if self._resource_check_counter >= 100:
            self._resource_check_counter = 0
            self._check_resource_context()

        # 队列满后触发多模态分析
        if self.analysis_config.get("behaviorAnalysis", MultiModalConfig.ENABLE_MULTI_MODAL) and len(self.multi_modal_frame_cache) >= self.multi_modal_queue_size:
            if not self.multi_modal_in_progress:
                frames = list(self.multi_modal_frame_cache)
                self.multi_modal_frame_cache.clear()
                asyncio.create_task(self._run_multi_modal_analysis(frames, current_time))
        
        # ★★★ 统一日志汇总：每5秒输出一次综合检测结果 ★★★
        if current_time - self._last_unified_log_time >= 5.0 and self._latest_results:
            self._last_unified_log_time = current_time
            parts = []
            g = self._latest_results.get("gaze")
            if g:
                parts.append(
                    f"视线[方向={g['方向']} 注意={g['注意力']}({g['分数']}) "
                    f"眨眼={g['眨眼']}/min 瞌睡={g['瞌睡']}({g['瞌睡分']}) 哈欠={g['哈欠']}]"
                )
            e = self._latest_results.get("emotion")
            if e:
                parts.append(f"情绪[{e['情绪']}({e['置信度']})]")
            o = self._latest_results.get("objects")
            if o:
                parts.append(f"物品[{', '.join(o['物品'][:3])}]")
                if o["分心物品"]:
                    parts.append(f"分心物品[{', '.join(o['分心物品'][:3])}]")
            d = self._latest_results.get("distraction")
            if d:
                reasons_str = "、".join(d["原因"][:3]) if d["原因"] else "无"
                parts.append(
                    f"分心[状态={'是' if d['分心'] else '否'} "
                    f"等级={d['等级']} 专注度={d['分数']} 原因={reasons_str}]"
                )
            p = self._latest_results.get("posture")
            if p:
                parts.append(f"坐姿[头={p['头部']} 塌腰={p['塌腰']} 翘腿={p['翘腿']}]")
            if parts:
                self.logger.info(" | ".join(parts))

        # 【重要修复】在 WebRTC 服务端禁用 cv2.imshow，防止 GUI 冲突导致连接断开
        # 如果需要调试查看画面，请使用前端页面或保存为视频文件
        # cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
        # cv2.imshow(self.window_name, frame_array)
        # cv2.waitKey(1)

        return frame

