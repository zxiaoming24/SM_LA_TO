"""
test_gaze_calibration.py - 带屏幕标定的视线追踪系统
实现将视线映射到屏幕坐标系的精细方案

功能：
1. 标定过程（4点或9点）
2. 实时视线映射到屏幕
3. 区域兴趣分析（图片区、文字区等）
"""

import cv2
import numpy as np
import mediapipe as mp
from collections import deque
from typing import Tuple, List, Optional, Dict
from PIL import Image, ImageDraw, ImageFont
import json
import os


def cv2_add_chinese_text(img, text, position, text_color=(255, 255, 255), font_size=20):
    """在 OpenCV 图像上绘制中文文字"""
    if isinstance(img, np.ndarray):
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    else:
        img_pil = img
    
    draw = ImageDraw.Draw(img_pil)
    
    # 尝试多种中文字体
    font_paths = [
        "simhei.ttf",  # 黑体
        "simsun.ttc",  # 宋体
        "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
        "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
        "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
        "C:/Windows/Fonts/arial.ttf",    # 备用
    ]
    
    font = None
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size, encoding="utf-8")
            break
        except:
            continue
    
    if font is None:
        font = ImageFont.load_default()
    
    draw.text(position, text, text_color, font=font)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


class GazeCalibrator:
    """视线标定器"""
    
    def __init__(self, screen_width=1920, screen_height=1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # 标定数据
        self.calibration_points = []  # 虹膜偏移向量
        self.screen_points = []       # 对应屏幕坐标
        
        # 变换矩阵
        self.transform_matrix = None
        self.is_calibrated = False
        
        # 9点标定坐标（屏幕上的位置）
        self.calibration_targets_9 = [
            (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),  # 上左、中、右
            (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),  # 中左、中、中右
            (0.1, 0.9), (0.5, 0.9), (0.9, 0.9)   # 下左、中、右
        ]
        
        # 4点标定坐标
        self.calibration_targets_4 = [
            (0.1, 0.1), (0.9, 0.1),  # 左上、右上
            (0.1, 0.9), (0.9, 0.9)   # 左下、右下
        ]
    
    def get_calibration_target_screen_coords(self, index: int, mode: str = "9") -> Tuple[int, int]:
        """获取标定点的屏幕坐标"""
        if mode == "9":
            ratio_x, ratio_y = self.calibration_targets_9[index]
        else:
            ratio_x, ratio_y = self.calibration_targets_4[index]
        
        return int(ratio_x * self.screen_width), int(ratio_y * self.screen_height)
    
    def add_calibration_point(self, gaze_offset: Tuple[float, float], screen_coord: Tuple[int, int]):
        """添加一个标定点"""
        self.calibration_points.append(gaze_offset)
        self.screen_points.append(screen_coord)
    
    def compute_transform(self) -> bool:
        """计算透视变换矩阵"""
        if len(self.calibration_points) < 4:
            return False
        
        try:
            # 将标定数据转换为numpy数组
            src_points = np.array(self.calibration_points, dtype=np.float32)
            dst_points = np.array(self.screen_points, dtype=np.float32)
            
            # 归一化屏幕坐标到 0-1
            dst_points[:, 0] /= self.screen_width
            dst_points[:, 1] /= self.screen_height
            
            # 计算透视变换矩阵
            self.transform_matrix, _ = cv2.findHomography(src_points, dst_points)
            
            if self.transform_matrix is not None:
                self.is_calibrated = True
                return True
            
        except Exception as e:
            print(f"标定失败: {e}")
        
        return False
    
    def map_gaze_to_screen(self, gaze_offset: Tuple[float, float]) -> Tuple[float, float]:
        """将视线偏移映射到屏幕坐标"""
        if not self.is_calibrated or self.transform_matrix is None:
            return 0.5, 0.5  # 默认屏幕中心
        
        try:
            # 构建齐次坐标
            point = np.array([[[gaze_offset[0], gaze_offset[1], 1.0]]], dtype=np.float32)
            
            # 应用透视变换
            transformed = cv2.perspectiveTransform(point, self.transform_matrix)
            
            # 提取结果
            screen_x = float(transformed[0][0][0])
            screen_y = float(transformed[0][0][1])
            
            # 限制在屏幕范围内
            screen_x = max(0, min(1, screen_x))
            screen_y = max(0, min(1, screen_y))
            
            return screen_x, screen_y
            
        except Exception:
            return 0.5, 0.5
    
    def save_calibration(self, filepath: str = "calibration_data.json"):
        """保存标定数据"""
        data = {
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "calibration_points": self.calibration_points,
            "screen_points": self.screen_points,
            "transform_matrix": self.transform_matrix.tolist() if self.transform_matrix is not None else None,
            "is_calibrated": self.is_calibrated
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        print(f"标定数据已保存: {filepath}")
    
    def load_calibration(self, filepath: str = "calibration_data.json") -> bool:
        """加载标定数据"""
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.screen_width = data["screen_width"]
            self.screen_height = data["screen_height"]
            self.calibration_points = data["calibration_points"]
            self.screen_points = data["screen_points"]
            
            if data["transform_matrix"] is not None:
                self.transform_matrix = np.array(data["transform_matrix"])
                self.is_calibrated = True
                return True
            
        except Exception as e:
            print(f"加载标定数据失败: {e}")
        
        return False


class GazeTrackerWithCalibration:
    """带标定功能的视线追踪器"""
    
    def __init__(self, screen_width=1920, screen_height=1080):
        # 初始化 MediaPipe
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 关键点索引
        self.LEFT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
        self.RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
        self.LEFT_IRIS = [474, 475, 476, 477]
        self.RIGHT_IRIS = [469, 470, 471, 472]
        
        # EAR 阈值
        self.EAR_THRESHOLD = 0.21
        
        # 眨眼统计
        self.blink_counter = 0
        self.total_blinks = 0
        self.is_blinking = False
        
        # 标定器
        self.calibrator = GazeCalibrator(screen_width, screen_height)
        
        # 历史数据
        self.gaze_history = deque(maxlen=5)
        
        # 当前分析结果
        self.current_gaze_offset = (0.0, 0.0)
        self.current_screen_point = (0.5, 0.5)
    
    def get_eye_center(self, eye_indices: List[int], landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """获取眼睛中心"""
        h, w, _ = frame_shape
        eye_pts = [landmarks[i] for i in eye_indices[:6]]
        
        x = sum([pt.x for pt in eye_pts]) / len(eye_pts) * w
        y = sum([pt.y for pt in eye_pts]) / len(eye_pts) * h
        
        return x, y
    
    def get_iris_center(self, iris_indices: List[int], landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """获取虹膜中心"""
        h, w, _ = frame_shape
        iris_pts = [landmarks[i] for i in iris_indices]
        
        x = sum([pt.x for pt in iris_pts]) / len(iris_pts) * w
        y = sum([pt.y for pt in iris_pts]) / len(iris_pts) * h
        
        return x, y
    
    def get_gaze_offset(self, landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """计算视线偏移向量（归一化到眼睛大小比例）"""
        h, w, _ = frame_shape
        
        # 获取眼睛和虹膜中心
        left_eye = self.get_eye_center(self.LEFT_EYE, landmarks, frame_shape)
        right_eye = self.get_eye_center(self.RIGHT_EYE, landmarks, frame_shape)
        
        left_iris = self.get_iris_center(self.LEFT_IRIS, landmarks, frame_shape)
        right_iris = self.get_iris_center(self.RIGHT_IRIS, landmarks, frame_shape)
        
        # 计算相对偏移（像素）
        left_offset_x = left_iris[0] - left_eye[0]
        left_offset_y = left_iris[1] - left_eye[1]
        
        right_offset_x = right_iris[0] - right_eye[0]
        right_offset_y = right_iris[1] - right_eye[1]
        
        # 平均偏移
        avg_offset_x = (left_offset_x + right_offset_x) / 2
        avg_offset_y = (left_offset_y + right_offset_y) / 2
        
        # 计算眼睛宽度用于归一化
        left_eye_width = abs(landmarks[self.LEFT_EYE[0]].x - landmarks[self.LEFT_EYE[8]].x) * w
        right_eye_width = abs(landmarks[self.RIGHT_EYE[0]].x - landmarks[self.RIGHT_EYE[8]].x) * w
        avg_eye_width = (left_eye_width + right_eye_width) / 2
        
        # 归一化：偏移 / 眼睛宽度
        # 这样阈值设置更直观：0.1 = 眼睛宽度的10%
        if avg_eye_width > 0:
            norm_offset_x = avg_offset_x / avg_eye_width
            norm_offset_y = avg_offset_y / avg_eye_width
        else:
            norm_offset_x = 0.0
            norm_offset_y = 0.0
        
        return norm_offset_x, norm_offset_y
    
    def calculate_ear(self, eye_indices: List[int], landmarks, frame_shape: Tuple[int, int, int]) -> float:
        """计算眼睛纵横比"""
        h, w, _ = frame_shape
        eye_pts = [landmarks[i] for i in eye_indices[:6]]
        
        # 垂直距离
        v1 = np.linalg.norm([
            (eye_pts[1].x - eye_pts[5].x) * w,
            (eye_pts[1].y - eye_pts[5].y) * h
        ])
        v2 = np.linalg.norm([
            (eye_pts[2].x - eye_pts[4].x) * w,
            (eye_pts[2].y - eye_pts[4].y) * h
        ])
        
        # 水平距离
        h1 = np.linalg.norm([
            (eye_pts[0].x - eye_pts[3].x) * w,
            (eye_pts[0].y - eye_pts[3].y) * h
        ])
        
        if h1 == 0:
            return 0.0
        
        return (v1 + v2) / (2.0 * h1)
    
    def analyze(self, frame: np.ndarray, do_calibration: bool = False, calibration_index: int = -1) -> dict:
        """分析图像"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        result = {
            "face_detected": False,
            "gaze_offset": (0.0, 0.0),
            "screen_point": (0.5, 0.5),
            "ear": 0.0,
            "left_ear": 0.0,
            "right_ear": 0.0,
            "blinking": False,
            "attention_level": "unknown"
        }
        
        if not results.multi_face_landmarks:
            return result
        
        result["face_detected"] = True
        landmarks = results.multi_face_landmarks[0].landmark
        
        # 计算 EAR
        left_ear = self.calculate_ear(self.LEFT_EYE, landmarks, frame.shape)
        right_ear = self.calculate_ear(self.RIGHT_EYE, landmarks, frame.shape)
        result["ear"] = (left_ear + right_ear) / 2
        result["left_ear"] = left_ear
        result["right_ear"] = right_ear
        
        # 眨眼检测
        if left_ear < self.EAR_THRESHOLD and right_ear < self.EAR_THRESHOLD:
            self.blink_counter += 1
            self.is_blinking = True
        else:
            if self.blink_counter >= 3:
                self.total_blinks += 1
            self.blink_counter = 0
            self.is_blinking = False
        
        result["blinking"] = self.is_blinking
        
        # 视线偏移
        gaze_offset = self.get_gaze_offset(landmarks, frame.shape)
        result["gaze_offset"] = gaze_offset
        self.current_gaze_offset = gaze_offset
        
        # 映射到屏幕坐标
        if self.calibrator.is_calibrated:
            screen_point = self.calibrator.map_gaze_to_screen(gaze_offset)
            result["screen_point"] = screen_point
            self.current_screen_point = screen_point
            self.gaze_history.append(screen_point)
        
        # 注意力等级
        if self.is_blinking:
            result["attention_level"] = "low"
        else:
            result["attention_level"] = "high"
        
        # 标定数据采集
        if do_calibration and calibration_index >= 0:
            screen_coords = self.calibrator.get_calibration_target_screen_coords(calibration_index, mode="4")
            self.calibrator.add_calibration_point(gaze_offset, screen_coords)
        
        return result


class CalibrationWindow:
    """标定窗口"""
    
    def __init__(self, tracker: GazeTrackerWithCalibration, mode: str = "4"):
        self.tracker = tracker
        self.mode = mode  # "4" 或 "9"
        
        # 标定点
        if mode == "9":
            self.targets = [
                (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
                (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),
                (0.1, 0.9), (0.5, 0.9), (0.9, 0.9)
            ]
        else:
            self.targets = [
                (0.1, 0.1), (0.9, 0.1),
                (0.1, 0.9), (0.9, 0.9)
            ]
        
        self.current_index = 0
        self.frame_counter = 0
        self.required_frames = 30  # 每个点需要采集的帧数
        self.calibration_started = False
        self.calibration_complete = False
        
        # 窗口
        self.window_name = "Gaze Calibration"
        
    def run(self):
        """运行标定过程"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        print(f"\n{'='*60}")
        print(f"视线标定过程 ({self.mode}点标定)")
        print(f"{'='*60}")
        print(f"请将视线依次对准屏幕上的红点，每次保持2-3秒")
        print(f"共 {len(self.targets)} 个标定点")
        print("按 'q' 键退出标定")
        print(f"{'='*60}\n")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 绘制标定点
            frame = self.draw_calibration_target(frame)
            
            cv2.imshow(self.window_name, frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # 计算变换矩阵
        if len(self.tracker.calibrator.calibration_points) >= 4:
            if self.tracker.calibrator.compute_transform():
                print("\n✅ 标定成功！")
                self.tracker.calibrator.save_calibration()
            else:
                print("\n❌ 标定失败，请重试")
    
    def draw_calibration_target(self, frame: np.ndarray) -> np.ndarray:
        """绘制标定点"""
        h, w, _ = frame.shape
        screen_w, screen_h = self.tracker.calibrator.screen_width, self.tracker.calibrator.screen_height
        
        # 计算缩放比例
        scale_x = w / screen_w
        scale_y = h / screen_h
        
        # 如果还没有开始标定，等待用户准备好
        if not self.calibration_started:
            frame = cv2_add_chinese_text(
                frame,
                "按任意键开始标定...",
                (w//2 - 150, h//2),
                (255, 255, 255),
                24
            )
            
            if self.current_index == 0 and self.frame_counter == 0:
                self.calibration_started = True
            
            return frame
        
        # 绘制所有标定点
        for i, (ratio_x, ratio_y) in enumerate(self.targets):
            x = int(ratio_x * w)
            y = int(ratio_y * h)
            
            if i < self.current_index:
                # 已完成的点 - 绿色
                cv2.circle(frame, (x, y), 20, (0, 255, 0), -1)
                cv2.putText(frame, "✓", (x-8, y+8), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            elif i == self.current_index:
                # 当前点 - 红色闪烁
                color = (0, 0, 255) if (self.frame_counter // 10) % 2 == 0 else (0, 128, 255)
                cv2.circle(frame, (x, y), 30, color, 3)
                cv2.circle(frame, (x, y), 5, color, -1)
                
                # 提示文字
                progress = self.frame_counter / self.required_frames * 100
                cv2.putText(frame, f"{progress:.0f}%", (x+40, y+10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                
                # 采集数据
                result = self.tracker.analyze(frame, do_calibration=True, calibration_index=self.current_index)
                
                self.frame_counter += 1
                
                # 切换到下一个点
                if self.frame_counter >= self.required_frames:
                    self.current_index += 1
                    self.frame_counter = 0
                    print(f"✓ 第 {self.current_index}/{len(self.targets)} 点采集完成")
            else:
                # 未完成的点 - 灰色
                cv2.circle(frame, (x, y), 15, (100, 100, 100), -1)
        
        # 显示进度
        progress_text = f"标定进度: {self.current_index}/{len(self.targets)}"
        cv2.putText(frame, progress_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return frame


def test_with_calibration():
    """带标定的视线追踪测试"""
    
    print("=" * 60)
    print("带屏幕标定的视线追踪系统")
    print("=" * 60)
    
    # 初始化追踪器
    tracker = GazeTrackerWithCalibration(screen_width=1920, screen_height=1080)
    
    # 尝试加载已有标定数据
    if tracker.calibrator.load_calibration():
        print("✅ 已加载之前的标定数据")
    else:
        print("⚠️ 未找到标定数据，将使用默认映射")
    
    # 检查是否需要重新标定
    if not tracker.calibrator.is_calibrated:
        print("\n建议进行标定以提高精度")
        print("标定过程：将视线对准屏幕上的4个点")
        print("按 'c' 键可在运行时开始标定")
        print("按 Enter 键跳过，直接进入测试...")
        input()  # 等待用户按 Enter
    
    # 打开摄像头进行测试
    print("\n正在打开摄像头...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return
    
    print("✅ 摄像头已打开")
    print("\n" + "=" * 60)
    print("功能说明:")
    print("  - 视线追踪：显示当前视线在屏幕上的位置")
    print("  - 区域判断：图片区、文字区、标题区等")
    print("  - 按 'q' 退出")
    print("  - 按 'c' 重新标定")
    print("=" * 60 + "\n")
    
    import time
    start_time = time.time()
    frame_count = 0
    fps_history = deque(maxlen=30)
    last_time = start_time
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        current_time = time.time()
        fps = 1.0 / (current_time - last_time) if current_time - last_time > 0 else 0
        fps_history.append(fps)
        last_time = current_time
        frame_count += 1
        
        # 分析
        result = tracker.analyze(frame)
        
        # 状态栏背景
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 220), (0, 0, 0), -1)
        
        if result["face_detected"]:
            # 视线位置 - 使用 gaze_offset 直接判断方向
            gaze_x, gaze_y = result["gaze_offset"]
            
            # 调试信息：打印原始偏移值
            print(f"视线偏移: gaze_x={gaze_x:.3f}, gaze_y={gaze_y:.3f}", end='\r')
            
            # ========== 在线教育场景区域划分 ==========
            # 基于 gaze_offset 的方向判断
            # gaze_x < 0: 视线向左；gaze_x > 0: 视线向右
            # gaze_y < 0: 视线向上；gaze_y > 0: 视线向下
            
            region = "未知区域"
            region_color = (200, 200, 200)
            interest_level = 0  # 兴趣度 0-100
            
            # 根据视线偏移方向判断区域
            # 归一化后：值表示眼睛宽度的比例 (眼睛宽度约60-80像素)
            # 0.12 = 眼睛宽度的12% 约 7-10 像素（小幅移动）
            if gaze_y < -0.12:
                # 视线向上
                region = "标题栏"
                region_color = (255, 200, 0)
                interest_level = 30
            elif gaze_y > 0.12:
                # 视线向下
                region = "控制栏"
                region_color = (0, 200, 200)
                interest_level = 40
            elif gaze_x < -0.15:
                # 视线向左 - 视频区
                region = "视频区"
                region_color = (0, 200, 100)
                interest_level = 80
            elif gaze_x > 0.15:
                # 视线向右 - 互动区
                region = "互动区"
                region_color = (200, 100, 0)
                interest_level = 60
            else:
                # 视线居中 - 课程内容
                region = "课程内容"
                region_color = (100, 100, 255)
                interest_level = 90
            
            # 注意力状态
            if interest_level >= 80:
                attention_text = "高度专注！"
                attention_color = (0, 255, 0)
            elif interest_level >= 50:
                attention_text = "专注"
                attention_color = (0, 255, 255)
            else:
                attention_text = "注意力分散"
                attention_color = (0, 0, 255)
            
            # 显示信息
            frame = cv2_add_chinese_text(
                frame,
                f"当前区域: {region}",
                (30, 50),
                region_color,
                22
            )
            
            # 视线方向
            direction_text = "居中"
            if gaze_x < -0.2:
                direction_text = "看左边"
            elif gaze_x > 0.2:
                direction_text = "看右边"
            
            if gaze_y < -0.15:
                direction_text += " + 看上面"
            elif gaze_y > 0.15:
                direction_text += " + 看下面"
            
            frame = cv2_add_chinese_text(
                frame,
                f"视线方向: {direction_text}",
                (30, 80),
                (255, 255, 255),
                18
            )
            
            frame = cv2_add_chinese_text(
                frame,
                f"视线偏移: ({gaze_x:.3f}, {gaze_y:.3f})",
                (30, 105),
                (200, 200, 200),
                16
            )
            
            # 调试信息：显示左右眼 EAR
            frame = cv2_add_chinese_text(
                frame,
                f"左眼EAR: {result['left_ear']:.3f} 右眼EAR: {result['right_ear']:.3f}",
                (30, 135),
                (150, 150, 150),
                14
            )
            
            frame = cv2_add_chinese_text(
                frame,
                f"眨眼次数: {tracker.total_blinks}",
                (30, 135),
                (255, 255, 255),
                18
            )
            
            frame = cv2_add_chinese_text(
                frame,
                f"注意力: {attention_text}",
                (30, 170),
                attention_color,
                20
            )
            
            # 兴趣度条
            bar_width = 200
            bar_height = 15
            bar_x, bar_y = 30, 195
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (50, 50, 50), -1)
            filled_width = int(bar_width * interest_level / 100)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled_width, bar_y + bar_height), attention_color, -1)
            cv2.putText(frame, f"兴趣度: {interest_level}%", (bar_x + bar_width + 10, bar_y + 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            # 在画面上绘制视线方向指示
            # 将 gaze_offset 映射到画面上的箭头
            center_x, center_y = frame.shape[1] // 2, frame.shape[0] // 2
            arrow_length = 50  # 箭头长度
            
            # 计算箭头终点
            end_x = int(center_x + gaze_x * arrow_length * 2)
            end_y = int(center_y - gaze_y * arrow_length * 2)  # y轴翻转
            
            # 绘制中心点
            cv2.circle(frame, (center_x, center_y), 5, (0, 255, 0), -1)
            # 绘制箭头
            cv2.arrowedLine(frame, (center_x, center_y), (end_x, end_y), (0, 255, 255), 2)
            
            # 显示区域标签在箭头终点
            cv2.putText(frame, region, (end_x + 10, end_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, region_color, 2)
            
        else:
            frame = cv2_add_chinese_text(
                frame,
                "未检测到人脸",
                (30, 30),
                (0, 0, 255),
                24
            )
        
        # FPS
        avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0
        cv2.putText(frame, f"FPS: {avg_fps:.1f}", 
                   (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 绘制区域布局示意图
        legend_x = frame.shape[1] - 220
        legend_y = 50
        
        # 图例标题
        cv2.putText(frame, "屏幕区域划分:", (legend_x, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 区域颜色块
        legend_items = [
            ("视频区", (0, 200, 100)),
            ("课程内容", (100, 100, 255)),
            ("互动区", (200, 100, 0)),
            ("标题栏", (255, 200, 0)),
            ("控制栏", (0, 200, 200)),
        ]
        
        for i, (name, color) in enumerate(legend_items):
            y_pos = legend_y + 25 + i * 22
            cv2.rectangle(frame, (legend_x, y_pos), (legend_x + 20, y_pos + 15), color, -1)
            cv2.putText(frame, name, (legend_x + 28, y_pos + 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 标定状态
        if tracker.calibrator.is_calibrated:
            cv2.putText(frame, "已标定", (frame.shape[1]-100, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "未标定", (frame.shape[1]-100, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        cv2.imshow("Gaze Tracking with Calibration", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            print("\n重新标定...")
            calibrator_window = CalibrationWindow(tracker, mode="4")
            calibrator_window.run()
    
    cap.release()
    cv2.destroyAllWindows()
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("测试结束")
    print(f"总帧数: {frame_count}")
    print(f"运行时间: {elapsed:.2f} 秒")
    print(f"平均帧率: {frame_count/elapsed:.2f} FPS")
    print(f"检测到的眨眼次数: {tracker.total_blinks}")
    print("=" * 60)


if __name__ == "__main__":
    test_with_calibration()
