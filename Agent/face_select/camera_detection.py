"""
本地摄像头检测脚本
支持：坐姿分析、人脸识别、情绪分析
"""

import cv2
import numpy as np
from typing import Optional
import time
from config import (
    FaceRecognitionConfig, 
    EmotionConfig, 
    SittingPostureConfig,
    GazeConfig
)
from logger import get_logger
from ultralytics import YOLO
from sitting_posture_interface import SittingPosturePredictor
from face_recognition.face_recognition_service import create_face_recognition_module
from gaze_detector import GazeDetector
from attention_tracker import AttentionTracker

logger = get_logger(__name__)


class LocalCameraDetection:
    """本地摄像头检测类"""
    
    def __init__(self, camera_id: int = 0, enable_posture: bool = True, 
                 enable_face: bool = True, enable_emotion: bool = True,
                 enable_gaze: bool = True):
        """
        初始化摄像头检测
        
        Args:
            camera_id: 摄像头ID (0为默认摄像头)
            enable_posture: 是否启用坐姿分析
            enable_face: 是否启用人脸识别
            enable_emotion: 是否启用情绪分析
            enable_gaze: 是否启用视线检测与专注度追踪
        """
        self.camera_id = camera_id
        self.cap = cv2.VideoCapture(camera_id)
        
        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开摄像头 {camera_id}")
        
        logger.info(f"摄像头 {camera_id} 已打开")
        
        # 初始化检测模块
        self.enable_posture = enable_posture and SittingPostureConfig.ENABLE_SITTING_POSTURE
        self.enable_face = enable_face and FaceRecognitionConfig.ENABLE_FACE_RECOGNITION
        self.enable_emotion = enable_emotion and EmotionConfig.ENABLE_EMOTION
        self.enable_gaze = enable_gaze and GazeConfig.ENABLE_GAZE_DETECTION
        
        # 坐姿分析器
        self.sitting_posture_predictor: Optional[SittingPosturePredictor] = None
        if self.enable_posture:
            try:
                self.sitting_posture_predictor = SittingPosturePredictor()
                logger.info("坐姿分析器初始化成功")
            except Exception as e:
                logger.error(f"坐姿分析器初始化失败: {e}")
                self.enable_posture = False
        
        # 人脸识别模块
        self.face_recognition_module = None
        if self.enable_face:
            try:
                face_config = {
                    "threshold": FaceRecognitionConfig.FACE_DETECTION_THRESHOLD,
                    "database_path": FaceRecognitionConfig.FACE_DATABASE_PATH
                }
                self.face_recognition_module = create_face_recognition_module(face_config)
                logger.info("人脸识别模块初始化成功")
            except Exception as e:
                logger.error(f"人脸识别模块初始化失败: {e}")
                self.enable_face = False
        
        # 情绪分析模型
        self.emotion_model = None
        if self.enable_emotion:
            try:
                self.emotion_model = YOLO(EmotionConfig.EMOTION_MODEL_PATH)
                logger.info("情绪分析模型初始化成功")
            except Exception as e:
                logger.error(f"情绪分析模型初始化失败: {e}")
                self.enable_emotion = False
        
        # 帧计数器
        self.frame_count = 0
        self.posture_frame_counter = 0
        self.face_frame_counter = 0
        self.emotion_frame_counter = 0
        
        # 处理间隔
        self.posture_process_interval = SittingPostureConfig.SITTING_POSTURE_FRAMES
        self.face_process_interval = FaceRecognitionConfig.FACE_RECOGNITION_FRAMES
        self.emotion_process_interval = EmotionConfig.EMOTION_FRAMES

        # ★★★ 视线检测与专注度追踪 ★★★
        self.gaze_detector = None
        self.attention_tracker = None
        self.gaze_frame_counter = 0
        self.gaze_process_interval = GazeConfig.ATTENTION_RECORD_INTERVAL
        if self.enable_gaze:
            try:
                self.gaze_detector = GazeDetector()
                logger.info("视线检测器初始化成功")
                if GazeConfig.ENABLE_ATTENTION_TRACKING:
                    self.attention_tracker = AttentionTracker()
                    logger.info("专注度追踪器初始化成功")
            except Exception as e:
                logger.error(f"视线检测器初始化失败: {e}")
                self.enable_gaze = False
        
        # 性能统计
        self.start_time = time.time()
        self.last_fps_log = time.time()
    
    def _get_emotion_color(self, emotion: str) -> tuple:
        """根据情绪类型返回颜色 (BGR)"""
        colors = {
            'happy': (0, 255, 0), 'sad': (255, 0, 0), 'angry': (0, 0, 255),
            'surprised': (0, 255, 255), 'fear': (255, 0, 255), 'neutral': (128, 128, 128),
        }
        return colors.get(emotion.lower(), (200, 200, 200))
    
    def _draw_emotion_detections(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """在画面上绘制情绪检测结果"""
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
            
            # 绘制标签
            label = f"{emotion}({conf:.2f})"
            text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            text_w, text_h = text_size
            
            y_offset = y1 - 8 if y1 - text_h - 8 > 0 else y1 + text_h + 8
            x_offset = max(0, min(x1, w - text_w - 8))
            
            cv2.rectangle(annotated,
                        (x_offset, y_offset - text_h - 4),
                        (x_offset + text_w + 4, y_offset + 4),
                        color, -1)
            
            cv2.putText(annotated, label, (x_offset + 2, y_offset - 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return annotated
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """处理单一帧，进行各种检测"""
        display_frame = frame.copy()
        self.frame_count += 1
        self.posture_frame_counter += 1
        self.face_frame_counter += 1
        self.emotion_frame_counter += 1
        self.gaze_frame_counter += 1
        
        current_time = time.time()
        
        # 每5秒输出一次统计信息
        if current_time - self.last_fps_log >= 5.0:
            elapsed = current_time - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            logger.info(f"处理帧率: {fps:.2f} FPS (总帧数: {self.frame_count})")
            self.last_fps_log = current_time
        
        # 坐姿分析
        if self.enable_posture and self.posture_frame_counter >= self.posture_process_interval:
            self.posture_frame_counter = 0
            try:
                annotated_frame, posture_results = self.sitting_posture_predictor.process_frame(frame)
                if posture_results:
                    display_frame = annotated_frame
                    logger.info(f"坐姿: 头部={posture_results.get('Head')}, "
                              f"塌腰={posture_results.get('Hunch')}, "
                              f"翘腿={posture_results.get('CrossLeg')}")
            except Exception as e:
                logger.error(f"坐姿分析失败: {e}")
        
        # 人脸识别
        if self.enable_face and self.face_frame_counter >= self.face_process_interval:
            self.face_frame_counter = 0
            try:
                detections = self.face_recognition_module.process_frame(frame)
                if detections:
                    display_frame = self.face_recognition_module.annotate_frame(display_frame, detections)
                    names = ','.join([d['name'] for d in detections])
                    logger.info(f"检测到人脸: {names}")
            except Exception as e:
                logger.error(f"人脸识别失败: {e}")
        
        # 情绪分析
        if self.enable_emotion and self.emotion_frame_counter >= self.emotion_process_interval:
            self.emotion_frame_counter = 0
            try:
                results = self.emotion_model(frame, verbose=False)
                detections = []
                
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
                            
                            x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), int(x2), int(y2)
                            
                            if x1 < x2 and y1 < y2:
                                detections.append({
                                    'emotion': emotion_name,
                                    'confidence': round(conf, 3),
                                    'bbox': [x1, y1, x2, y2],
                                })
                        except (ValueError, IndexError):
                            continue
                
                if detections:
                    display_frame = self._draw_emotion_detections(display_frame, detections)
                    emotions_str = ", ".join([f"{d['emotion']}({d['confidence']:.2f})" for d in detections])
                    logger.info(f"情绪分析: {emotions_str}")
            except Exception as e:
                logger.error(f"情绪分析失败: {e}")

        # ★★★ 视线检测与专注度分析 ★★★
        if self.enable_gaze and self.gaze_detector and self.gaze_frame_counter >= self.gaze_process_interval:
            self.gaze_frame_counter = 0
            try:
                gaze_result = self.gaze_detector.detect(frame)
                if gaze_result["face_detected"]:
                    logger.info(
                        f"视线: {gaze_result['gaze_direction']}, "
                        f"专注: {gaze_result['attention_level']}({gaze_result['attention_score']}), "
                        f"眨眼: {gaze_result['blink_rate']}/min"
                    )
                    # 在画面上叠加视线信息
                    cv2.putText(display_frame,
                                f"Gaze: {gaze_result['gaze_direction']}",
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    cv2.putText(display_frame,
                                f"Attn: {gaze_result['attention_level']}({gaze_result['attention_score']})",
                                (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    cv2.putText(display_frame,
                                f"Blink: {gaze_result['blink_rate']}/min",
                                (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            except Exception as e:
                logger.error(f"视线检测失败: {e}")

        return display_frame
    
    def run(self):
        """运行摄像头检测循环"""
        logger.info("启动摄像头检测 (按 'q' 键退出)")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.error("无法从摄像头读取帧")
                    break
                
                # 处理帧
                display_frame = self.process_frame(frame)
                
                # 显示
                cv2.imshow("Camera Detection", display_frame)
                
                # 按 'q' 退出
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("用户按下 'q' 键，退出")
                    break
        
        except KeyboardInterrupt:
            logger.info("检测被中断")
        finally:
            self.release()
    
    def release(self):
        """释放资源"""
        self.cap.release()
        cv2.destroyAllWindows()
        # ★★★ 关闭视线检测器 ★★★
        if self.gaze_detector is not None:
            try:
                self.gaze_detector.close()
            except Exception as e:
                logger.error(f"关闭视线检测器失败: {e}")
        logger.info("摄像头已关闭，资源已释放")


def main():
    """主函数"""
    try:
        # 创建检测器实例
        detector = LocalCameraDetection(
            camera_id=1,
            enable_posture=False,      # 启用坐姿分析
            enable_face=False,         # 启用人脸识别
            enable_emotion=True       # 启用情绪分析
        )
        
        # 运行检测
        detector.run()
    
    except Exception as e:
        logger.error(f"摄像头检测失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
