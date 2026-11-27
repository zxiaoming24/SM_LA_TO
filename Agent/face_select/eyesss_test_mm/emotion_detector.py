"""
emotion_detector.py - 情绪检测模块
基于YOLO模型的情绪分析
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import Optional, Dict, List
import asyncio

from eyesss_test_mm.config import EmotionConfig


class EmotionDetector:
    """情绪检测器"""
    
    def __init__(self):
        self.model = None
        self.enabled = EmotionConfig.ENABLE_EMOTION_DETECTION
        self.frame_count = 0
        self.last_result = None
        
        if self.enabled:
            try:
                self.model = YOLO(EmotionConfig.MODEL_PATH)
                print("✅ 情绪分析模型加载成功")
            except Exception as e:
                print(f"❌ 情绪分析模型加载失败: {e}")
                self.enabled = False
    
    async def async_detect(self, frame: np.ndarray) -> Dict:
        """
        异步检测情绪（支持跳帧处理）
        
        Args:
            frame: 输入帧
            
        Returns:
            dict: 情绪检测结果
        """
        self.frame_count += 1
        
        # 跳帧处理：不是每帧都检测
        if self.frame_count % EmotionConfig.DETECTION_INTERVAL != 0:
            if self.last_result is not None:
                return self.last_result
        
        # 在线程池中执行情绪检测，避免阻塞事件循环
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, 
            self._detect_sync, 
            frame.copy()
        )
        return result
    
    def _detect_sync(self, frame: np.ndarray) -> Dict:
        """
        同步检测核心逻辑（供异步调用使用）
        """
        result = {
            "emotion_detected": False,
            "emotion": "neutral",
            "confidence": 0.0,
            "state": "平静",
            "attention_impact": 0,
            "bbox": None
        }
        
        if not self.enabled or self.model is None:
            return result
        
        try:
            # 检测情绪
            results = self.model(frame, verbose=False)
            
            if results and len(results[0].boxes) > 0:
                # 获取置信度最高的检测结果
                boxes = results[0].boxes
                max_conf_idx = 0
                max_conf = float(boxes[0].conf[0]) if len(boxes) > 0 else 0
                
                for i, box in enumerate(boxes):
                    current_conf = float(box.conf[0])
                    if current_conf > max_conf:
                        max_conf = current_conf
                        max_conf_idx = i
                
                best_box = boxes[max_conf_idx]
                cls_id = int(best_box.cls[0])
                x1, y1, x2, y2 = map(int, best_box.xyxy[0].tolist())
                
                if max_conf >= EmotionConfig.CONFIDENCE_THRESHOLD and cls_id < len(EmotionConfig.CLASS_NAMES):
                    emotion = EmotionConfig.CLASS_NAMES[cls_id]
                    emotion_info = EmotionConfig.EMOTION_STATE_MAP.get(emotion, {})
                    
                    result.update({
                        "emotion_detected": True,
                        "emotion": emotion,
                        "confidence": max_conf,
                        "state": emotion_info.get("state", "平静"),
                        "attention_impact": emotion_info.get("attention_impact", 0),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)]
                    })
        
        except Exception as e:
            print(f"情绪检测异常: {e}")
        
        # 保存最后结果用于跳帧返回
        self.last_result = result
        return result
    
    def annotate_frame(self, frame: np.ndarray, emotion_data: Dict) -> np.ndarray:
        """
        在画面上绘制情绪检测结果
        
        Args:
            frame: 输入帧
            emotion_data: 情绪检测数据
            
        Returns:
            np.ndarray: 标注后的帧
        """
        annotated = frame.copy()
        
        if emotion_data.get("emotion_detected"):
            emotion = emotion_data["emotion"]
            confidence = emotion_data["confidence"]
            bbox = emotion_data.get("bbox")
            
            # 获取情绪颜色
            color = self._get_emotion_color(emotion)
            
            # 绘制检测框
            if bbox:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                
                # 绘制标签
                label = f"{emotion}({confidence:.2f})"
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                text_x, text_y = x1, y1 - 10 if y1 > 10 else y1 + 20
                
                # 绘制标签背景
                cv2.rectangle(annotated, (text_x, text_y - text_size[1] - 5), 
                             (text_x + text_size[0] + 5, text_y + 5), color, -1)
                cv2.putText(annotated, label, (text_x + 2, text_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return annotated
    
    def _get_emotion_color(self, emotion: str) -> tuple:
        """根据情绪类型返回颜色 (BGR)"""
        colors = {
            'happy': (0, 255, 0),      # 绿色
            'sad': (255, 0, 0),        # 蓝色
            'angry': (0, 0, 255),      # 红色
            'surprised': (0, 255, 255), # 黄色
            'fear': (255, 0, 255),     # 紫色
            'disgust': (0, 128, 0),    # 深绿色
            'neutral': (128, 128, 128), # 灰色
        }
        return colors.get(emotion.lower(), (200, 200, 200))