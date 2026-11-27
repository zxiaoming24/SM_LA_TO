"""
gaze_detector.py - MediaPipe 虹膜检测模块
功能：
1. 人脸关键点检测
2. 虹膜位置追踪
3. 视线方向估算
4. 眨眼检测
5. 注意力等级判定
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, Any, Tuple, Optional
from collections import deque
import time

from config import GazeConfig, MouthConfig
from weight_config_manager import get_weight


class GazeDetector:
    """视线检测器 - 基于MediaPipe Face Mesh"""
    
    def __init__(self):
        """初始化检测器"""
        # MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=GazeConfig.MAX_NUM_FACES,
            refine_landmarks=GazeConfig.REFINE_LANDMARKS,
            min_detection_confidence=GazeConfig.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=GazeConfig.MIN_TRACKING_CONFIDENCE
        )
        
        # 眼睛关键点索引
        # 左眼
        self.LEFT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
        self.LEFT_EYE_TOP = 386
        self.LEFT_EYE_BOTTOM = 374
        self.LEFT_EYE_LEFT = 362
        self.LEFT_EYE_RIGHT = 263
        
        # 右眼
        self.RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
        self.RIGHT_EYE_TOP = 159
        self.RIGHT_EYE_BOTTOM = 145
        self.RIGHT_EYE_LEFT = 33
        self.RIGHT_EYE_RIGHT = 133
        
        # 虹膜关键点索引
        self.LEFT_IRIS = [468, 469, 470, 471, 472]
        self.RIGHT_IRIS = [473, 474, 475, 476, 477]
        
        # ========== 头部姿态估计 ==========
        # 3D人脸模型点（毫米坐标）
        self.FACE_3D_MODEL = np.array([
            [0.0, 0.0, 0.0],        # 鼻尖 - landmark 1
            [0.0, -330.0, -65.0],   # 下巴 - landmark 152
            [-225.0, 170.0, -135.0], # 左眼左角 - landmark 33
            [225.0, 170.0, -135.0],  # 右眼右角 - landmark 263
            [-150.0, -150.0, -125.0],# 左嘴角 - landmark 61
            [150.0, -150.0, -125.0]  # 右嘴角 - landmark 291
        ], dtype=np.float64)
        
        # 对应的2D特征点索引
        self.FACE_2D_INDICES = [1, 152, 33, 263, 61, 291]
        
        # 相机矩阵（近似）
        self.CAMERA_MATRIX = None  # 在检测时动态计算
        self.DIST_COEFFS = np.zeros((4, 1), dtype=np.float64)  # 畸变系数
        
        # 状态变量
        self.blink_counter = 0
        self.blink_state = False
        self.consecutive_blink_frames = 0
        
        # 时序统计
        self.blink_times = deque(maxlen=100)  # 记录眨眼时间戳
        self.gaze_history = deque(maxlen=30)  # 视线历史
        
        # ========== 嘴部检测（打哈欠） ==========
        # 嘴部关键点索引（MediaPipe Face Mesh）
        # 上唇: 61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291
        # 下唇: 146, 91, 181, 84, 17, 314, 405, 321, 375, 78, 308
        self.MOUTH_TOP = 13          # 上唇中点
        self.MOUTH_BOTTOM = 14       # 下唇中点
        self.MOUTH_LEFT = 61         # 左嘴角
        self.MOUTH_RIGHT = 291       # 右嘴角
        
        # 打哈欠追踪
        self.yawn_counter = 0        # 哈欠总次数
        self.current_yawn_frames = 0 # 当前张嘴持续帧数
        self.is_yawn_state = False   # 是否正在打哈欠
        
        # ========== 瞌睡检测 ==========
        self.pitch_history = deque(maxlen=150)  # 最近5秒头部俯仰历史（30fps*5）
        self.drowsy_frames = 0                  # 连续瞌睡信号帧数
        self.last_yawn_time = 0                 # 上次哈欠时间
        
        # 上一次检测结果
        self.last_result = {
            "face_detected": False,
            "gaze_direction": "center",
            "attention_score": 0,
            "attention_level": "low",
            "blink_rate": 0,
            "is_blinking": False,
            "is_yawning": False,
            "is_drowsy": False,
            "drowsiness_score": 0.0,
            "head_pose": {"pitch": 0, "yaw": 0, "roll": 0},
            "iris_position": {"left": (0.5, 0.5), "right": (0.5, 0.5)}
        }
        
        # ★★★ 帧计数器：用于降频执行 CPU 密集型操作 ★★★
        self._frame_count = 0
        self._HEAD_POSE_INTERVAL = 3  # 每3帧执行一次头部姿态估计

    def _get_landmark_coords(self, landmarks, indices, image_shape):
        """获取指定索引的关键点坐标"""
        h, w = image_shape[:2]
        coords = []
        for idx in indices:
            lm = landmarks.landmark[idx]
            coords.append((int(lm.x * w), int(lm.y * h)))
        return np.array(coords, dtype=np.float32)

    def _calculate_ear(self, eye_landmarks):
        """计算眼睛纵横比 (Eye Aspect Ratio)"""
        # 垂直距离
        v1 = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
        v2 = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
        # 水平距离
        h = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
        ear = (v1 + v2) / (2.0 * h)
        return ear

    def _calculate_mar(self, landmarks, image_shape):
        """计算嘴部纵横比 (Mouth Aspect Ratio)"""
        h, w = image_shape[:2]
        
        # 获取嘴部关键点
        top = landmarks.landmark[self.MOUTH_TOP]
        bottom = landmarks.landmark[self.MOUTH_BOTTOM]
        left = landmarks.landmark[self.MOUTH_LEFT]
        right = landmarks.landmark[self.MOUTH_RIGHT]
        
        # 转换为像素坐标
        top_y = top.y * h
        bottom_y = bottom.y * h
        left_x = left.x * w
        right_x = right.x * w
        
        # 计算高度和宽度
        height = abs(bottom_y - top_y)
        width = abs(right_x - left_x)
        
        if width == 0:
            return 0.0
        
        return height / width

    def _detect_blink(self, landmarks, image_shape):
        """检测眨眼"""
        left_eye = self._get_landmark_coords(landmarks, self.LEFT_EYE, image_shape)
        right_eye = self._get_landmark_coords(landmarks, self.RIGHT_EYE, image_shape)
        
        left_ear = self._calculate_ear(left_eye)
        right_ear = self._calculate_ear(right_eye)
        
        avg_ear = (left_ear + right_ear) / 2.0
        
        is_blinking = False
        
        if avg_ear < GazeConfig.EAR_THRESHOLD:
            self.consecutive_blink_frames += 1
            if self.consecutive_blink_frames >= GazeConfig.EAR_CONSECUTIVE_FRAMES:
                if not self.blink_state:
                    self.blink_state = True
                    self.blink_counter += 1
                    self.blink_times.append(time.time())
                    is_blinking = True  # ★★★ ：检测到眨眼时设为 True ★★★
        else:
            self.consecutive_blink_frames = 0
            self.blink_state = False
        
        return is_blinking, avg_ear

    def _estimate_head_pose(self, landmarks, image_shape):
        """估计头部姿态"""
        h, w = image_shape[:2]
        
        # 初始化相机矩阵
        if self.CAMERA_MATRIX is None:
            focal_length = w
            center = (w / 2, h / 2)
            self.CAMERA_MATRIX = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
        
        # 获取2D特征点
        face_2d = []
        for idx in self.FACE_2D_INDICES:
            lm = landmarks.landmark[idx]
            face_2d.append([lm.x * w, lm.y * h])
        
        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = self.FACE_3D_MODEL
        
        # 求解位姿
        success, rotation_vec, translation_vec = cv2.solvePnP(
            face_3d, face_2d, self.CAMERA_MATRIX, self.DIST_COEFFS
        )
        
        if not success:
            return {"pitch": 0, "yaw": 0, "roll": 0}
        
        # 将旋转向量转换为欧拉角
        rotation_matrix, _ = cv2.Rodrigues(rotation_vec)
        decompose_result = cv2.decomposeProjectionMatrix(
            np.hstack((rotation_matrix, translation_vec))
        )
        angles = decompose_result[0]  # angles 是返回值的第一个元素
        
        pitch = angles[0][0]
        yaw = angles[1][0]
        roll = angles[2][0]
        
        return {"pitch": pitch, "yaw": yaw, "roll": roll}

    def _calculate_gaze_direction(self, landmarks, image_shape):
        """计算视线方向"""
        h, w = image_shape[:2]
        
        # 获取左眼虹膜中心点
        left_iris_center = np.mean([
            (landmarks.landmark[i].x * w, landmarks.landmark[i].y * h)
            for i in self.LEFT_IRIS
        ], axis=0)
        
        # 获取右眼虹膜中心点
        right_iris_center = np.mean([
            (landmarks.landmark[i].x * w, landmarks.landmark[i].y * h)
            for i in self.RIGHT_IRIS
        ], axis=0)
        
        # 获取眼睛边界
        left_eye_left = (landmarks.landmark[self.LEFT_EYE_LEFT].x * w, landmarks.landmark[self.LEFT_EYE_LEFT].y * h)
        left_eye_right = (landmarks.landmark[self.LEFT_EYE_RIGHT].x * w, landmarks.landmark[self.LEFT_EYE_RIGHT].y * h)
        left_eye_top = (landmarks.landmark[self.LEFT_EYE_TOP].x * w, landmarks.landmark[self.LEFT_EYE_TOP].y * h)
        left_eye_bottom = (landmarks.landmark[self.LEFT_EYE_BOTTOM].x * w, landmarks.landmark[self.LEFT_EYE_BOTTOM].y * h)
        
        right_eye_left = (landmarks.landmark[self.RIGHT_EYE_LEFT].x * w, landmarks.landmark[self.RIGHT_EYE_LEFT].y * h)
        right_eye_right = (landmarks.landmark[self.RIGHT_EYE_RIGHT].x * w, landmarks.landmark[self.RIGHT_EYE_RIGHT].y * h)
        right_eye_top = (landmarks.landmark[self.RIGHT_EYE_TOP].x * w, landmarks.landmark[self.RIGHT_EYE_TOP].y * h)
        right_eye_bottom = (landmarks.landmark[self.RIGHT_EYE_BOTTOM].x * w, landmarks.landmark[self.RIGHT_EYE_BOTTOM].y * h)
        
        # 计算眼睛中心和宽度
        left_eye_center_x = (left_eye_left[0] + left_eye_right[0]) / 2
        left_eye_center_y = (left_eye_top[1] + left_eye_bottom[1]) / 2
        left_eye_width = left_eye_right[0] - left_eye_left[0]
        
        right_eye_center_x = (right_eye_left[0] + right_eye_right[0]) / 2
        right_eye_center_y = (right_eye_top[1] + right_eye_bottom[1]) / 2
        right_eye_width = right_eye_right[0] - right_eye_left[0]
        
        # 计算虹膜偏移（归一化到眼睛宽度）
        left_offset_x = (left_iris_center[0] - left_eye_center_x) / left_eye_width
        left_offset_y = (left_iris_center[1] - left_eye_center_y) / left_eye_width
        
        right_offset_x = (right_iris_center[0] - right_eye_center_x) / right_eye_width
        right_offset_y = (right_iris_center[1] - right_eye_center_y) / right_eye_width
        
        # 取双眼平均值
        avg_offset_x = (left_offset_x + right_offset_x) / 2
        avg_offset_y = (left_offset_y + right_offset_y) / 2
        
        # 判断视线方向（组合水平和垂直方向）
        dir_x = "center"
        if avg_offset_x < -GazeConfig.GAZE_X_THRESHOLD:
            dir_x = "left"
        elif avg_offset_x > GazeConfig.GAZE_X_THRESHOLD:
            dir_x = "right"

        dir_y = "center"
        if avg_offset_y < -GazeConfig.GAZE_Y_THRESHOLD:
            dir_y = "up"
        elif avg_offset_y > GazeConfig.GAZE_Y_THRESHOLD:
            dir_y = "down"

        # 组合方向，省略 center 部分
        if dir_x == "center" and dir_y == "center":
            direction = "center"
        elif dir_x == "center":
            direction = dir_y
        elif dir_y == "center":
            direction = dir_x
        else:
            direction = f"{dir_x}_{dir_y}"
        
        # 计算注意力分数（基于虹膜偏移）
        offset_magnitude = np.sqrt(avg_offset_x ** 2 + avg_offset_y ** 2)
        attention_score = max(0, 100 - offset_magnitude * 200)
        
        # 归一化虹膜位置（0-1）
        iris_left_norm = (
            (left_iris_center[0] - left_eye_left[0]) / left_eye_width,
            (left_iris_center[1] - left_eye_top[1]) / (left_eye_bottom[1] - left_eye_top[1])
        )
        iris_right_norm = (
            (right_iris_center[0] - right_eye_left[0]) / right_eye_width,
            (right_iris_center[1] - right_eye_top[1]) / (right_eye_bottom[1] - right_eye_top[1])
        )
        
        return {
            "direction": direction,
            "attention_score": attention_score,
            "offset": (avg_offset_x, avg_offset_y),
            "iris_position": {
                "left": iris_left_norm,
                "right": iris_right_norm
            }
        }

    def _detect_yawn(self, landmarks, image_shape):
        """检测打哈欠"""
        mar = self._calculate_mar(landmarks, image_shape)
        
        if mar > MouthConfig.YAWN_MAR_THRESHOLD:
            self.current_yawn_frames += 1
            if self.current_yawn_frames >= MouthConfig.YAWN_CONSECUTIVE_FRAMES:
                if not self.is_yawn_state:
                    self.is_yawn_state = True
                    self.yawn_counter += 1
                    self.last_yawn_time = time.time()
                return True
        else:
            self.current_yawn_frames = 0
            self.is_yawn_state = False
        
        return self.is_yawn_state

    def _detect_drowsiness(self, head_pose):
        """检测瞌睡状态"""
        pitch = head_pose["pitch"]
        
        cfg = get_weight("gaze_detector") or {}
        dw = cfg.get("drowsiness_weights", {})
        head_down_threshold = cfg.get("head_down_angle_threshold", 15)
        yawn_cooldown = cfg.get("yawn_cooldown_seconds", 300)
        blink_low = cfg.get("blink_rate_low_threshold", 5)
        blink_high = cfg.get("blink_rate_high_threshold", 30)
        drowsiness_threshold = cfg.get("drowsiness_score_threshold", 0.45)
        
        # 记录头部俯仰角度历史
        self.pitch_history.append(pitch)
        
        # 判断是否低头（pitch > N度通常表示低头打瞌睡）
        is_drowsy_sign = pitch > head_down_threshold
        
        if is_drowsy_sign:
            self.drowsy_frames += 1
        else:
            self.drowsy_frames = 0
        
        # 计算瞌睡分数
        # 基于：1) 连续低头帧数 2) 最近是否打哈欠
        drowsiness_score = 0.0
        
        # 低头时间占比
        if len(self.pitch_history) > 0:
            head_down_ratio = sum(1 for p in self.pitch_history if p > head_down_threshold) / len(self.pitch_history)
            drowsiness_score += head_down_ratio * dw.get("head_down", 0.6)
        
        # 最近是否打哈欠
        if time.time() - self.last_yawn_time < yawn_cooldown:
            drowsiness_score += dw.get("recent_yawn", 0.3)
        
        # 眨眼频率异常（低于N次/分钟或高于N次/分钟）
        blink_rate = self._calculate_blink_rate()
        if blink_rate < blink_low or blink_rate > blink_high:
            drowsiness_score += dw.get("abnormal_blink", 0.1)
        
        drowsiness_score = min(1.0, drowsiness_score)
        is_drowsy = drowsiness_score > drowsiness_threshold
        
        return is_drowsy, drowsiness_score

    def _calculate_blink_rate(self):
        """计算眨眼频率（次/分钟）"""
        if len(self.blink_times) < 2:
            return 0
        
        # 计算最近60秒内的眨眼次数
        current_time = time.time()
        recent_blinks = [t for t in self.blink_times if current_time - t <= 60]
        
        if len(recent_blinks) < 2:
            return 0
        
        # 计算频率
        duration = current_time - recent_blinks[0]
        if duration < 0.1:
            return 0
        
        rate = (len(recent_blinks) / duration) * 60
        return round(rate, 1)

    def _determine_attention_level(self, attention_score):
        """根据注意力分数确定注意力等级"""
        if attention_score >= GazeConfig.HIGH_ATTENTION_THRESHOLD:
            return "high"
        elif attention_score >= GazeConfig.LOW_ATTENTION_THRESHOLD:
            return "medium"
        else:
            return "low"

    def detect(self, image: np.ndarray) -> Dict[str, Any]:
        """
        执行视线检测
        
        参数：
            image: 输入图像（BGR格式）
        
        返回：
            包含检测结果的字典
        """
        # 转换为RGB格式（MediaPipe要求）
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 处理图像
        results = self.face_mesh.process(image_rgb)
        
        if not results.multi_face_landmarks:
            return {
                "face_detected": False,
                "gaze_direction": "center",
                "attention_score": 0,
                "attention_level": "low",
                "blink_rate": 0,
                "is_blinking": False,
                "is_yawning": False,
                "is_drowsy": False,
                "drowsiness_score": 0.0,
                "head_pose": {"pitch": 0, "yaw": 0, "roll": 0},
                "iris_position": {"left": (0.5, 0.5), "right": (0.5, 0.5)}
            }
        
        # 获取第一个人脸的关键点
        landmarks = results.multi_face_landmarks[0]
        image_shape = image.shape
        
        # 检测眨眼
        is_blinking, _ = self._detect_blink(landmarks, image_shape)
        
        # 计算视线方向
        gaze_result = self._calculate_gaze_direction(landmarks, image_shape)
        
        # 估计头部姿态（降频执行：每3帧一次）
        self._frame_count += 1
        if self._frame_count % self._HEAD_POSE_INTERVAL == 0:
            head_pose = self._estimate_head_pose(landmarks, image_shape)
            self._cached_head_pose = head_pose
        else:
            head_pose = getattr(self, '_cached_head_pose', {"pitch": 0, "yaw": 0, "roll": 0})
        
        # 检测打哈欠
        is_yawning = self._detect_yawn(landmarks, image_shape)
        
        # 检测瞌睡
        is_drowsy, drowsiness_score = self._detect_drowsiness(head_pose)
        
        # 计算眨眼频率
        blink_rate = self._calculate_blink_rate()
        
        # 确定注意力等级
        attention_level = self._determine_attention_level(gaze_result["attention_score"])
        
        # 更新历史记录
        self.gaze_history.append({
            "direction": gaze_result["direction"],
            "score": gaze_result["attention_score"],
            "time": time.time()
        })
        
        # 保存结果
        result = {
            "face_detected": True,
            "gaze_direction": gaze_result["direction"],
            "attention_score": round(gaze_result["attention_score"], 1),
            "attention_level": attention_level,
            "blink_rate": blink_rate,
            "is_blinking": is_blinking,
            "is_yawning": is_yawning,
            "is_drowsy": is_drowsy,
            "drowsiness_score": round(drowsiness_score, 3),
            "head_pose": head_pose,
            "iris_position": gaze_result["iris_position"]
        }
        
        self.last_result = result
        return result

    def close(self):
        """释放资源"""
        if self.face_mesh:
            self.face_mesh.close()

    def get_last_result(self) -> Dict[str, Any]:
        """获取上一次检测结果"""
        return self.last_result

    def reset(self):
        """重置状态"""
        self.blink_counter = 0
        self.blink_state = False
        self.consecutive_blink_frames = 0
        self.blink_times.clear()
        self.gaze_history.clear()
        self.yawn_counter = 0
        self.current_yawn_frames = 0
        self.is_yawn_state = False
        self.pitch_history.clear()
        self.drowsy_frames = 0
        self.last_yawn_time = 0
