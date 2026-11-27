"""
object_detector.py - YOLOv8 物品检测模块
功能：
1. 检测画面中的物品（手机、书、杯子等）
2. 判断物品是否为分心物品
3. 时序统计
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import Dict, Any, List
from collections import defaultdict
import time
import asyncio

from eyesss_test_mm.config import ObjectConfig


class ObjectDetector:
    """物品检测器 - 基于YOLOv8"""
    
    def __init__(self):
        """初始化检测器"""
        self.model = None
        self.frame_count = 0
        
        if ObjectConfig.ENABLE_OBJECT_DETECTION:
            try:
                self.model = YOLO(ObjectConfig.MODEL_PATH)
                print(f"✅ YOLO模型加载成功: {ObjectConfig.MODEL_PATH}")
            except Exception as e:
                print(f"❌ YOLO模型加载失败: {e}")
        
        # 时序统计
        self.detection_history = defaultdict(list)  # 物品检测历史
        self.last_result = None
    
    async def async_detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        异步检测画面中的物品（支持跳帧处理）
        
        Args:
            frame: BGR格式的图像帧
            
        Returns:
            包含检测结果的字典
        """
        self.frame_count += 1
        
        # 跳帧处理：不是每帧都检测
        if self.frame_count % ObjectConfig.DETECTION_INTERVAL != 0:
            if self.last_result is not None:
                return self.last_result
        
        # 在线程池中执行YOLO检测，避免阻塞事件循环
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, 
            self._detect_sync, 
            frame.copy()
        )
        return result
    
    def _detect_sync(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        同步检测核心逻辑（供异步调用使用）
        """
        if self.model is None:
            return {
                "detected": False,
                "objects": [],
                "distraction_objects": [],
                "state_objects": [],
                "has_distraction": False
            }
        
        try:
            # 运行YOLO检测（启用 ByteTrack 追踪，保持跨帧稳定性）
            if ObjectConfig.ENABLE_TRACKING:
                results = self.model.track(
                    frame,
                    conf=ObjectConfig.CONFIDENCE_THRESHOLD,
                    persist=True,
                    tracker=ObjectConfig.TRACKER_CONFIG,
                    verbose=False
                )
            else:
                results = self.model(
                    frame,
                    conf=ObjectConfig.CONFIDENCE_THRESHOLD,
                    verbose=False
                )
            
            detected_objects = []
            distraction_objects = []
            state_objects = []
            
            # 遍历检测结果
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                
                obj_info = {
                    "class_id": cls_id,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "centroid": [(x1 + x2) // 2, (y1 + y2) // 2]
                }
                
                # 判断是否为分心物品
                for key, item_info in ObjectConfig.DISTRACTION_OBJECTS.items():
                    if cls_id == item_info["id"]:
                        obj_info["name"] = item_info["name"]
                        obj_info["severity"] = item_info["severity"]
                        obj_info["type"] = "distraction"
                        distraction_objects.append(obj_info)
                        break
                
                # 判断是否为状态物品
                for key, item_info in ObjectConfig.STATE_OBJECTS.items():
                    if cls_id == item_info["id"]:
                        obj_info["name"] = item_info["name"]
                        obj_info["state"] = item_info["state"]
                        obj_info["type"] = "state"
                        state_objects.append(obj_info)
                        break
                
                # 如果都不是，记录为其他物品
                if "type" not in obj_info:
                    obj_info["name"] = f"物品_{cls_id}"
                    obj_info["type"] = "other"
                
                detected_objects.append(obj_info)
                
                # 记录检测历史
                self.detection_history[cls_id].append(time.time())
            
            # 清理过期的检测历史（保留最近30秒）
            current_time = time.time()
            for cls_id in list(self.detection_history.keys()):
                self.detection_history[cls_id] = [
                    t for t in self.detection_history[cls_id] 
                    if current_time - t < 30
                ]
            
            result = {
                "detected": len(detected_objects) > 0,
                "objects": detected_objects,
                "distraction_objects": distraction_objects,
                "state_objects": state_objects,
                "has_distraction": len(distraction_objects) > 0,
                "timestamp": time.time()
            }
            
            self.last_result = result
            return result
            
        except Exception as e:
            print(f"❌ 物品检测失败: {e}")
            return {
                "detected": False,
                "objects": [],
                "distraction_objects": [],
                "state_objects": [],
                "has_distraction": False
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取时序统计信息"""
        current_time = time.time()
        
        # 统计最近30秒检测到的物品
        recent_objects = defaultdict(int)
        for cls_id, times in self.detection_history.items():
            recent_times = [t for t in times if current_time - t < 30]
            recent_objects[cls_id] = len(recent_times)
        
        # 转换为物品名称
        recent_objects_named = {}
        for cls_id, count in recent_objects.items():
            name = f"物品_{cls_id}"
            # 查找名称
            for item_info in ObjectConfig.DISTRACTION_OBJECTS.values():
                if cls_id == item_info["id"]:
                    name = item_info["name"]
                    break
            for item_info in ObjectConfig.STATE_OBJECTS.values():
                if cls_id == item_info["id"]:
                    name = item_info["name"]
                    break
            recent_objects_named[name] = count
        
        return {
            "recent_objects": recent_objects_named,
            "total_detections": sum(recent_objects.values())
        }
    
    def annotate_frame(self, frame: np.ndarray, detection_result: Dict[str, Any]) -> np.ndarray:
        """
        在画面上绘制检测结果
        
        Args:
            frame: 原始帧
            detection_result: async_detect()返回的结果
            
        Returns:
            标注后的帧
        """
        annotated = frame.copy()
        
        # 绘制所有检测到的物品
        for obj in detection_result.get("objects", []):
            x1, y1, x2, y2 = obj["bbox"]
            conf = obj["confidence"]
            name = obj.get("name", f"物品_{obj['class_id']}")
            
            # 根据类型选择颜色
            if obj.get("type") == "distraction":
                color = (0, 0, 255)  # 红色
            elif obj.get("type") == "state":
                color = (0, 165, 255)  # 橙色
            else:
                color = (128, 128, 128)  # 灰色
            
            # 绘制边界框
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            label = f"{name} {conf:.2f}"
            cv2.putText(annotated, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return annotated