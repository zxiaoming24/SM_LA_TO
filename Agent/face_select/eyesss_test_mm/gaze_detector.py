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
from collections import deque, Counter
import time

from eyesss_test_mm.config import GazeConfig, MouthConfig


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
        
        # ========== PERCLOS 眼睑闭合检测 ==========
        self.ear_history = deque(maxlen=300)    # 最近10秒EAR记录（30fps*10）
        self.ear_history_window = 150           # PERCLOS 计算窗口（5秒，30fps*5）
        self.perclos_threshold = 0.25           # PERCLOS > 25% 视为疲劳信号（严格标准）

        # ========== 视线平滑滤波 ==========
        self.smoothed_offset_x = 0.0            # 低通滤波后的视线偏移X
        self.smoothed_offset_y = 0.0            # 低通滤波后的视线偏移Y
        self.smoothing_alpha = 0.3              # 滤波系数（0.1~0.5，越小越平滑）
        self.gaze_dead_zone = 0.05              # 视线死区：微小偏移不扣分

        # ========== 视线方向防抖 ==========
        self._direction_history = deque(maxlen=15)  # 最近0.5秒方向判断历史（30fps*0.5）
        self._last_direction = "居中"               # 上次稳定的方向
        
        # 上一次检测结果
        self.last_result = None
    
    def _calculate_ear(self, landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """计算眼睛纵横比 (Eye Aspect Ratio)"""
        h, w, _ = frame_shape
        
        # 左眼EAR
        left_top = np.array([landmarks[self.LEFT_EYE_TOP].x * w, 
                            landmarks[self.LEFT_EYE_TOP].y * h])
        left_bottom = np.array([landmarks[self.LEFT_EYE_BOTTOM].x * w, 
                               landmarks[self.LEFT_EYE_BOTTOM].y * h])
        left_left = np.array([landmarks[self.LEFT_EYE_LEFT].x * w, 
                             landmarks[self.LEFT_EYE_LEFT].y * h])
        left_right = np.array([landmarks[self.LEFT_EYE_RIGHT].x * w, 
                              landmarks[self.LEFT_EYE_RIGHT].y * h])
        
        left_vertical = np.linalg.norm(left_top - left_bottom)
        left_horizontal = np.linalg.norm(left_left - left_right)
        left_ear = left_vertical / (left_horizontal + 1e-6)
        
        # 右眼EAR
        right_top = np.array([landmarks[self.RIGHT_EYE_TOP].x * w, 
                             landmarks[self.RIGHT_EYE_TOP].y * h])
        right_bottom = np.array([landmarks[self.RIGHT_EYE_BOTTOM].x * w, 
                                landmarks[self.RIGHT_EYE_BOTTOM].y * h])
        right_left = np.array([landmarks[self.RIGHT_EYE_LEFT].x * w, 
                              landmarks[self.RIGHT_EYE_LEFT].y * h])
        right_right = np.array([landmarks[self.RIGHT_EYE_RIGHT].x * w, 
                               landmarks[self.RIGHT_EYE_RIGHT].y * h])
        
        right_vertical = np.linalg.norm(right_top - right_bottom)
        right_horizontal = np.linalg.norm(right_left - right_right)
        right_ear = right_vertical / (right_horizontal + 1e-6)
        
        return left_ear, right_ear
    
    def _calculate_mar(self, landmarks, frame_shape: Tuple[int, int, int]) -> float:
        """
        计算嘴部纵横比 (Mouth Aspect Ratio)
        MAR = 垂直距离 / 水平距离 → 张嘴时变大
        
        Returns:
            MAR值，正常闭合时约0.1~0.2，打哈欠时>0.5
        """
        h, w, _ = frame_shape
        
        # 上唇中点 - 下唇中点（垂直距离）
        top = np.array([landmarks[self.MOUTH_TOP].x * w, 
                       landmarks[self.MOUTH_TOP].y * h])
        bottom = np.array([landmarks[self.MOUTH_BOTTOM].x * w, 
                          landmarks[self.MOUTH_BOTTOM].y * h])
        vertical = np.linalg.norm(top - bottom)
        
        # 左嘴角 - 右嘴角（水平距离）
        left = np.array([landmarks[self.MOUTH_LEFT].x * w, 
                        landmarks[self.MOUTH_LEFT].y * h])
        right = np.array([landmarks[self.MOUTH_RIGHT].x * w, 
                         landmarks[self.MOUTH_RIGHT].y * h])
        horizontal = np.linalg.norm(left - right)
        
        mar = vertical / (horizontal + 1e-6)
        return mar
    
    def _detect_yawn(self, mar: float, current_time: float) -> Dict[str, Any]:
        """
        检测打哈欠
        
        规则：MAR > 阈值 且 持续超过一定帧数 → 判定为打哈欠
        """
        
        result = {
            "is_yawning": False,
            "mar": mar,
            "yawn_count": self.yawn_counter,
            "yawn_duration": 0.0
        }
        
        if mar > MouthConfig.YAWN_MAR_THRESHOLD:
            self.current_yawn_frames += 1
            if self.current_yawn_frames >= MouthConfig.YAWN_CONSECUTIVE_FRAMES:
                if not self.is_yawn_state:
                    self.yawn_counter += 1
                    self.last_yawn_time = current_time
                    self.is_yawn_state = True
                result["is_yawning"] = True
                result["yawn_count"] = self.yawn_counter
                result["yawn_duration"] = self.current_yawn_frames / 30.0  # 近似秒数
        else:
            self.current_yawn_frames = 0
            self.is_yawn_state = False
        
        return result
    
    def _detect_drowsiness(self, pitch_deg: float, blink_rate: float,
                           is_yawn_state: bool, current_time: float,
                           avg_ear: float = 1.0) -> Dict[str, Any]:
        """
        检测瞌睡状态（多信号融合 + PERCLOS）

        信号1：PERCLOS 眼睑闭合时间占比（行业金标准P80）
        信号2：头部反复点头（俯仰角频繁变化）
        信号3：眨眼频率极低（困了眨眼变慢）或极高（频繁眨眼强撑）
        信号4：刚打过哈欠
        """

        result = {
            "is_drowsy": False,
            "drowsiness_score": 0.0,
            "nodding_intensity": 0.0,
            "perclos": 0.0
        }

        # 记录俯仰角历史
        self.pitch_history.append(pitch_deg)

        # ★★★ PERCLOS：眼睑闭合帧占比（EAR < 0.15 视为真正闭眼，严格标准）★★★
        self.ear_history.append(avg_ear)
        perclos = 0.0
        if len(self.ear_history) >= 30:  # 至少有1秒数据才计算
            window = list(self.ear_history)[-self.ear_history_window:]
            closed_frames = sum(1 for e in window if e < 0.15)
            perclos = closed_frames / len(window)
        result["perclos"] = round(perclos, 4)

        # 信号1：头部点头强度（俯仰角高频变化幅度）
        nodding = 0.0
        if len(self.pitch_history) >= 30:
            recent = list(self.pitch_history)[-30:]  # 最近1秒
            # 计算俯仰角变化频率（标准差衡量波动）
            pitch_std = np.std(recent)
            # 计算方向变化次数（正负交替次数）
            directions = [1 if p > 0 else -1 for p in recent]
            changes = sum(1 for i in range(1, len(directions)) if directions[i] != directions[i-1])
            nodding = (pitch_std * changes) / 100.0
            result["nodding_intensity"] = min(1.0, nodding)
        else:
            result["nodding_intensity"] = 0.0

        # 综合瞌睡分数
        score = 0.0
        # PERCLOS 贡献（最大0.3，降低权重避免误报）
        score += min(perclos / self.perclos_threshold, 1.0) * 0.3
        # 点头贡献（最大0.3）
        score += nodding * 0.3
        # 眨眼异常贡献（眨眼 < 5 或 > 30，最大0.2）
        if blink_rate > 0:  # 有脸时
            if blink_rate < 5:
                score += 0.2  # 眨眼太少→可能呆滞
            elif blink_rate > 30:
                score += 0.1  # 眨眼太多→可能疲劳强撑
        # 哈欠贡献（最大0.15）
        if is_yawn_state:
            score += 0.15
        elif current_time - self.last_yawn_time < 10:
            score += 0.08  # 10秒内打过哈欠

        result["drowsiness_score"] = min(1.0, score)
        result["is_drowsy"] = score > MouthConfig.DROWSINESS_SCORE_THRESHOLD
        
        return result
    
    def _get_eye_center(self, eye_indices: list, landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """计算眼睛中心点"""
        h, w, _ = frame_shape
        x_coords = [landmarks[i].x * w for i in eye_indices]
        y_coords = [landmarks[i].y * h for i in eye_indices]
        return np.mean(x_coords), np.mean(y_coords)
    
    def _get_iris_center(self, iris_indices: list, landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """计算虹膜中心点"""
        h, w, _ = frame_shape
        x_coords = [landmarks[i].x * w for i in iris_indices]
        y_coords = [landmarks[i].y * h for i in iris_indices]
        return np.mean(x_coords), np.mean(y_coords)
    
    def _calculate_gaze_offset(self, landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """计算视线偏移向量（归一化到眼睛宽度）"""
        # 获取眼睛和虹膜中心
        left_eye = self._get_eye_center(self.LEFT_EYE, landmarks, frame_shape)
        right_eye = self._get_eye_center(self.RIGHT_EYE, landmarks, frame_shape)
        
        left_iris = self._get_iris_center(self.LEFT_IRIS, landmarks, frame_shape)
        right_iris = self._get_iris_center(self.RIGHT_IRIS, landmarks, frame_shape)
        
        # 计算相对偏移（像素）
        left_offset_x = left_iris[0] - left_eye[0]
        left_offset_y = left_iris[1] - left_eye[1]
        
        right_offset_x = right_iris[0] - right_eye[0]
        right_offset_y = right_iris[1] - right_eye[1]
        
        # 平均偏移
        avg_offset_x = (left_offset_x + right_offset_x) / 2
        avg_offset_y = (left_offset_y + right_offset_y) / 2
        
        # 计算眼睛宽度用于归一化
        h, w, _ = frame_shape
        left_eye_width = abs(landmarks[self.LEFT_EYE_LEFT].x - landmarks[self.LEFT_EYE_RIGHT].x) * w
        right_eye_width = abs(landmarks[self.RIGHT_EYE_LEFT].x - landmarks[self.RIGHT_EYE_RIGHT].x) * w
        avg_eye_width = (left_eye_width + right_eye_width) / 2
        
        # 归一化：偏移 / 眼睛宽度
        if avg_eye_width > 0:
            norm_offset_x = avg_offset_x / avg_eye_width
            norm_offset_y = avg_offset_y / avg_eye_width
        else:
            norm_offset_x = 0.0
            norm_offset_y = 0.0

        # ★★★ 一阶低通滤波：消除单帧抖动 ★★★
        self.smoothed_offset_x = self.smoothing_alpha * norm_offset_x + (1 - self.smoothing_alpha) * self.smoothed_offset_x
        self.smoothed_offset_y = self.smoothing_alpha * norm_offset_y + (1 - self.smoothing_alpha) * self.smoothed_offset_y

        return self.smoothed_offset_x, self.smoothed_offset_y
    
    def _determine_gaze_direction(self, gaze_x: float, gaze_y: float,
                                  head_pose: dict = None) -> str:
        """判断视线方向（含头部姿态补偿+防抖）"""
        x_threshold = GazeConfig.GAZE_X_THRESHOLD
        y_threshold = GazeConfig.GAZE_Y_THRESHOLD

        # 先算原始方向
        raw_direction = "居中"

        # ★★★ 头部姿态补偿：转头超过阈值即判定 ★★★
        if head_pose:
            yaw = head_pose.get("yaw", 0)
            pitch = head_pose.get("pitch", 0)
            if yaw > 28:
                raw_direction = "向右"
            elif yaw < -28:
                raw_direction = "向左"
            elif pitch > 22:
                raw_direction = "向下"
            elif pitch < -22:
                raw_direction = "向上"

        # 如果头部姿态没触发，走虹膜偏移判断
        if raw_direction == "居中":
            if gaze_y < -y_threshold:
                raw_direction = "向上"
            elif gaze_y > y_threshold:
                raw_direction = "向下"
            elif gaze_x < -x_threshold:
                raw_direction = "向左"
            elif gaze_x > x_threshold:
                raw_direction = "向右"

        # ★★★ 防抖：记录历史，多数一致才切换（避免单帧抖动）★★★
        self._direction_history.append(raw_direction)

        if len(self._direction_history) >= self._direction_history.maxlen:
            # 统计最近15帧的方向分布
            non_center = [d for d in self._direction_history if d != "居中"]
            if non_center:
                counter = Counter(non_center)
                top_dir, top_count = counter.most_common(1)[0]
                # 超过40%的帧一致 → 切换方向
                if top_count / len(self._direction_history) > 0.4:
                    self._last_direction = top_dir
                else:
                    self._last_direction = "居中"
            else:
                self._last_direction = "居中"
        else:
            # ★★★ 数据不足时直接用原始方向（不再死等15帧）★★★
            self._last_direction = raw_direction

        return self._last_direction
    
    def _calculate_attention_level(self, gaze_x: float, gaze_y: float, 
                                   is_blinking: bool, blink_rate: float,
                                   head_pose: dict = None) -> Tuple[str, int]:
        """计算注意力等级（含死区+非线性+头部姿态补偿）"""
        # 基础分数
        score = 100
        
        # ★★★ 死区：正常生理晃动不扣分 ★★★
        gaze_deviation = np.sqrt(gaze_x**2 + gaze_y**2)
        effective_deviation = max(0.0, gaze_deviation - self.gaze_dead_zone)
        
        # ★★★ 非线性映射：微小偏移少扣，大幅偏移狠扣 ★★★
        score -= int((effective_deviation * 200) ** 1.3)
        
        # ★★★ 头部姿态扣分：转头等于分心 ★★★
        if head_pose:
            yaw = abs(head_pose.get("yaw", 0))
            pitch = abs(head_pose.get("pitch", 0))
            # yaw > 30° 或 pitch > 25° 开始扣分（提高阈值避免正常坐姿微调误扣）
            if yaw > 30:
                score -= int((yaw - 30) * 1.5)
            if pitch > 25:
                score -= int((pitch - 25) * 1.2)
        
        # 眨眼扣分
        if is_blinking:
            score -= 10
        
        # 眨眼频率过高扣分
        if blink_rate > 20:  # 每分钟超过20次
            score -= 5
        
        # 限制范围
        score = max(0, min(100, score))
        
        # 等级判定
        if score >= GazeConfig.HIGH_ATTENTION_THRESHOLD:
            level = "高"
        elif score >= GazeConfig.LOW_ATTENTION_THRESHOLD:
            level = "中"
        else:
            level = "低"
        
        return level, score
    
    def _calculate_head_pose(self, landmarks, frame_shape: Tuple[int, int, int]) -> Dict[str, float]:
        """
        计算头部姿态（欧拉角）
        使用 solvePnP 估算头部旋转角度
        
        Returns:
            dict: yaw（水平旋转）, pitch（俯仰）, roll（翻滚）
        """
        h, w, _ = frame_shape
        
        # 动态初始化相机矩阵
        if self.CAMERA_MATRIX is None:
            self.CAMERA_MATRIX = np.array([
                [w, 0, w // 2],
                [0, w, h // 2],
                [0, 0, 1]
            ], dtype=np.float64)
        
        # 获取2D特征点坐标
        face_2d = []
        for idx in self.FACE_2D_INDICES:
            lm = landmarks[idx]
            face_2d.append([lm.x * w, lm.y * h])
        face_2d = np.array(face_2d, dtype=np.float64)
        
        # solvePnP求解旋转向量
        success, rotation_vec, _ = cv2.solvePnP(
            self.FACE_3D_MODEL,
            face_2d,
            self.CAMERA_MATRIX,
            self.DIST_COEFFS,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}
        
        # 将旋转向量转换为旋转矩阵
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)
        
        # 从旋转矩阵正确提取欧拉角
        # 旋转矩阵 R = Rx(roll) * Ry(pitch) * Rz(yaw)
        # pitch 绕 Y 轴（点头/仰头），yaw 绕 Z 轴（左右摇头），roll 绕 X 轴（歪头）
        # 参考标准头姿态估计算法
        sy = np.sqrt(rotation_mat[0, 0] * rotation_mat[0, 0] + 
                     rotation_mat[1, 0] * rotation_mat[1, 0])
        singular = sy < 1e-6
        
        if not singular:
            pitch = np.arctan2(-rotation_mat[2, 0], sy)     # 俯仰（低头/仰头）
            yaw = np.arctan2(rotation_mat[1, 0], rotation_mat[0, 0])   # 水平偏转（左右）
            roll = np.arctan2(rotation_mat[2, 1], rotation_mat[2, 2])  # 翻滚（歪头）
        else:
            pitch = np.arctan2(-rotation_mat[2, 0], sy)
            yaw = 0
            roll = np.arctan2(-rotation_mat[1, 2], rotation_mat[1, 1])
        
        # 转换为角度
        pitch_deg = float(np.degrees(pitch))
        yaw_deg = float(np.degrees(yaw))
        roll_deg = float(np.degrees(roll))
        
        # 限制合理范围（正常人头部活动范围）
        # yaw: -60°~60°, pitch: -30°~45°, roll: -30°~30°
        pitch_deg = max(-45.0, min(45.0, pitch_deg))
        yaw_deg = max(-60.0, min(60.0, yaw_deg))
        roll_deg = max(-30.0, min(30.0, roll_deg))
        
        return {
            "yaw": yaw_deg,       # 水平旋转（左右转头，正=右）
            "pitch": pitch_deg,    # 俯仰（正=低头，负=仰头）
            "roll": roll_deg       # 翻滚（歪头）
        }
    
    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        检测视线和注意力状态
        
        Args:
            frame: BGR格式的图像帧
            
        Returns:
            包含检测结果的字典
        """
        # 转换为RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 运行MediaPipe
        results = self.face_mesh.process(rgb_frame)
        
        # 初始化结果
        result = {
            "face_detected": False,
            "gaze_offset_x": 0.0,
            "gaze_offset_y": 0.0,
            "gaze_direction": "未知",
            "left_ear": 0.0,
            "right_ear": 0.0,
            "avg_ear": 0.0,
            "is_blinking": False,
            "blink_count": self.blink_counter,
            "blink_rate": 0.0,  # 每分钟眨眼次数
            "attention_level": "未知",
            "attention_score": 0,
            "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},  # 头部姿态
            "mouth_mar": 0.0,              # 嘴部纵横比
            "is_yawning": False,           # 是否正在打哈欠
            "yawn_count": self.yawn_counter,  # 哈欠总次数
            "yawn_duration": 0.0,          # 哈欠持续时间
            "is_drowsy": False,            # 是否瞌睡
            "drowsiness_score": 0.0,       # 瞌睡分数
            "nodding_intensity": 0.0,      # 点头强度
            "perclos": 0.0,                # PERCLOS 眼睑闭合占比
            "timestamp": time.time()
        }
        
        if not results.multi_face_landmarks:
            self.last_result = result
            return result
        
        # 获取第一个人的关键点
        landmarks = results.multi_face_landmarks[0].landmark
        h, w, _ = frame.shape
        
        result["face_detected"] = True
        current_time = time.time()
        
        # 1. 计算眼睛纵横比
        left_ear, right_ear = self._calculate_ear(landmarks, frame.shape)
        avg_ear = (left_ear + right_ear) / 2
        
        result["left_ear"] = left_ear
        result["right_ear"] = right_ear
        result["avg_ear"] = avg_ear
        
        # 2. 眨眼检测
        is_blinking = avg_ear < GazeConfig.EAR_THRESHOLD
        
        if is_blinking:
            self.consecutive_blink_frames += 1
            if self.consecutive_blink_frames >= GazeConfig.EAR_CONSECUTIVE_FRAMES:
                if not self.blink_state:
                    self.blink_counter += 1
                    self.blink_times.append(time.time())
                    self.blink_state = True
        else:
            self.consecutive_blink_frames = 0
            self.blink_state = False
        
        result["is_blinking"] = is_blinking
        result["blink_count"] = self.blink_counter
        
        # 计算眨眼频率（每分钟）
        current_time = time.time()
        recent_blinks = [t for t in self.blink_times if current_time - t < 60]
        blink_rate = len(recent_blinks)
        result["blink_rate"] = blink_rate
        
        # 3. 计算头部姿态
        head_pose = self._calculate_head_pose(landmarks, frame.shape)
        result["head_pose"] = head_pose
        
        # 4. 计算视线偏移
        gaze_x, gaze_y = self._calculate_gaze_offset(landmarks, frame.shape)
        
        result["gaze_offset_x"] = gaze_x
        result["gaze_offset_y"] = gaze_y
        
        # 记录视线历史
        self.gaze_history.append((gaze_x, gaze_y))
        
        # 5. 判断视线方向（含头部姿态补偿）
        gaze_direction = self._determine_gaze_direction(gaze_x, gaze_y, head_pose)
        result["gaze_direction"] = gaze_direction
        
        # 5.5 嘴部检测（打哈欠）
        mar = self._calculate_mar(landmarks, frame.shape)
        result["mouth_mar"] = mar
        yawn_result = self._detect_yawn(mar, current_time)
        result["is_yawning"] = yawn_result["is_yawning"]
        result["yawn_count"] = yawn_result["yawn_count"]
        result["yawn_duration"] = yawn_result["yawn_duration"]
        
        # 5.6 瞌睡检测（含 PERCLOS）
        head_pitch = head_pose.get("pitch", 0.0)
        drowsy_result = self._detect_drowsiness(
            head_pitch, blink_rate, yawn_result["is_yawning"], current_time, avg_ear
        )
        result["is_drowsy"] = drowsy_result["is_drowsy"]
        result["drowsiness_score"] = drowsy_result["drowsiness_score"]
        result["nodding_intensity"] = drowsy_result["nodding_intensity"]
        
        # 6. 计算注意力等级（含头部姿态补偿）
        attention_level, attention_score = self._calculate_attention_level(
            gaze_x, gaze_y, is_blinking, blink_rate, head_pose
        )
        result["attention_level"] = attention_level
        result["attention_score"] = attention_score
        
        self.last_result = result
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取时序统计信息"""
        current_time = time.time()
        
        # 眨眼统计
        recent_blinks = [t for t in self.blink_times if current_time - t < 30]
        blink_rate_30s = len(recent_blinks) * 2  # 每分钟
        
        # 视线变化统计
        if len(self.gaze_history) > 1:
            gaze_array = np.array(list(self.gaze_history))
            gaze_std_x = np.std(gaze_array[:, 0])
            gaze_std_y = np.std(gaze_array[:, 1])
            gaze_change = f"X变化={gaze_std_x:.3f}, Y变化={gaze_std_y:.3f}"
        else:
            gaze_change = "数据不足"
        
        return {
            "blink_rate_30s": blink_rate_30s,
            "gaze_change": gaze_change,
            "total_blinks": self.blink_counter
        }
    
    def close(self):
        """释放资源"""
        self.face_mesh.close()
