"""
人脸识别服务模块
提供简洁、高内聚的人脸识别功能接口
解耦视频处理器与人脸识别的具体实现
"""

import logging
import numpy as np
from typing import List, Dict, Optional
from face_recognition.face_reco_from_camera_ot import FaceRecognitionService as _FaceRecognitionService


class FaceRecognitionModule:
    """
    人脸识别模块外观类
    为视频处理器提供简洁、稳定的人脸识别接口
    隐藏内部实现细节，降低耦合度
    """

    def __init__(self, database_path: Optional[str] = None, threshold: float = 0.4):
        """
        初始化人脸识别模块

        Args:
            database_path: 人脸数据库路径（可选）
            threshold: 人脸识别阈值
        """
        self.service = _FaceRecognitionService(threshold=threshold)
        self.is_initialized = False
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> bool:
        """
        初始化人脸识别服务

        Returns:
            bool: 是否初始化成功
        """
        try:
            if self.is_initialized:
                return True

            success = self.service.load_face_database()
            self.is_initialized = success

            if success:
                self.logger.info("人脸识别模块初始化成功")
            else:
                self.logger.warning("人脸识别模块初始化失败：无法加载人脸数据库")

            return success
        except Exception as e:
            self.logger.error(f"人脸识别模块初始化失败: {e}")
            self.is_initialized = False
            return False

    def process_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        处理单个视频帧

        Args:
            frame: 视频帧图像

        Returns:
            List[Dict]: 人脸识别结果列表
        """
        if not self.is_initialized:
            self.logger.warning("人脸识别模块未初始化，返回空结果")
            return []

        try:
            return self.service.analyze_frame(frame)
        except Exception as e:
            self.logger.error(f"人脸识别处理失败: {e}")
            return []

    def annotate_frame(self, frame: np.ndarray, results: List[Dict]) -> np.ndarray:
        """
        在帧上绘制识别结果

        Args:
            frame: 原始帧
            results: 识别结果

        Returns:
            np.ndarray: 标注后的帧
        """
        try:
            return self.service.annotate_frame(frame, results)
        except Exception as e:
            self.logger.error(f"标注帧失败: {e}")
            return frame

    def check_anomaly(self, results: List[Dict],
                     unknown_threshold: float = 0.6,
                     multiple_faces_anomaly: bool = True) -> bool:
        """
        检查结果是否有异常

        Args:
            results: 识别结果
            unknown_threshold: 未知人脸置信度阈值
            multiple_faces_anomaly: 多个脸是否算异常

        Returns:
            bool: 是否有异常
        """
        try:
            return self.service.is_anomaly(results, unknown_threshold, multiple_faces_anomaly)
        except Exception as e:
            self.logger.error(f"异常检测失败: {e}")
            return False

    def get_status(self) -> Dict:
        """
        获取模块状态

        Returns:
            Dict: 模块状态信息
        """
        return {
            "initialized": self.is_initialized,
            "service_loaded": self.service.is_loaded if hasattr(self.service, 'is_loaded') else False
        }

    def cleanup(self):
        """清理资源"""
        self.is_initialized = False
        self.logger.info("人脸识别模块已清理")


def create_face_recognition_module(config: Optional[Dict] = None) -> Optional[FaceRecognitionModule]:
    """
    工厂函数：创建并初始化人脸识别模块
    
    Args:
        config: 配置字典，包含以下可选项:
            - threshold: 人脸识别阈值（默认0.4）
            - database_path: 人脸数据库路径
    
    Returns:
        FaceRecognitionModule: 初始化成功的模块实例，若失败则返回 None
    """
    if config is None:
        config = {}
    
    try:
        threshold = config.get("threshold", 0.4)
        database_path = config.get("database_path", None)
        
        module = FaceRecognitionModule(database_path=database_path, threshold=threshold)
        
        if module.initialize():
            return module
        else:
            logging.getLogger(__name__).warning("人脸识别模块初始化失败")
            return None
    except Exception as e:
        logging.getLogger(__name__).error(f"创建人脸识别模块失败: {e}")
        return None

