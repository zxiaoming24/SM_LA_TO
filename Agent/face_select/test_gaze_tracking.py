"""
test_gaze_tracking.py - 视线追踪与注意力分析测试
使用 MediaPipe Face Mesh 获取面部关键点和虹膜位置

功能：
1. 人脸关键点检测（468点）
2. 虹膜/瞳孔位置追踪
3. 视线方向估算
4. 眨眼检测
5. 注意力状态判断
"""

import cv2
import numpy as np
import mediapipe as mp
from collections import deque
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont


def cv2_add_chinese_text(img, text, position, text_color=(255, 255, 255), font_size=20):
    """在 OpenCV 图像上绘制中文文字"""
    if isinstance(img, np.ndarray):
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    else:
        img_pil = img
    
    draw = ImageDraw.Draw(img_pil)
    
    try:
        font = ImageFont.truetype("simsun.ttc", font_size, encoding="utf-8")
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", font_size, encoding="utf-8")
        except:
            font = ImageFont.load_default()
    
    draw.text(position, text, text_color, font=font)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


class GazeTracker:
    """视线追踪器"""
    
    def __init__(self):
        # 初始化 MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,  # 启用虹膜关键点
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 眼睛关键点索引
        self.LEFT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
        self.RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
        
        # 虹膜关键点索引（MediaPipe 0.10+）
        self.LEFT_IRIS = [474, 475, 476, 477]
        self.RIGHT_IRIS = [469, 470, 471, 472]
        
        # 面部中心点
        self.FACE_CENTER = 1  # 鼻尖
        
        # EAR 阈值
        self.EAR_THRESHOLD = 0.21
        self.EAR_CONSECUTIVE_FRAMES = 3
        
        # 眨眼计数器
        self.blink_counter = 0
        self.total_blinks = 0
        
        # 历史数据
        self.gaze_history = deque(maxlen=10)
        
    def calculate_ear(self, eye_landmarks, frame_shape: Tuple[int, int, int]) -> float:
        """计算眼睛纵横比 (Eye Aspect Ratio)"""
        h, w, _ = frame_shape
        
        # 眼睛关键点: 上(1,2)、下(5,4)、左(0)、右(3)
        #     1 2
        #    0   3
        #     4 5
        
        # 垂直距离
        v1 = np.linalg.norm([
            (eye_landmarks[1].x - eye_landmarks[5].x) * w,
            (eye_landmarks[1].y - eye_landmarks[5].y) * h
        ])
        v2 = np.linalg.norm([
            (eye_landmarks[2].x - eye_landmarks[4].x) * w,
            (eye_landmarks[2].y - eye_landmarks[4].y) * h
        ])
        
        # 水平距离
        h1 = np.linalg.norm([
            (eye_landmarks[0].x - eye_landmarks[3].x) * w,
            (eye_landmarks[0].y - eye_landmarks[3].y) * h
        ])
        
        if h1 == 0:
            return 0.0
        
        return (v1 + v2) / (2.0 * h1)
    
    def get_iris_center(self, iris_landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """获取虹膜中心点"""
        h, w, _ = frame_shape
        
        x = sum([lm.x for lm in iris_landmarks]) / len(iris_landmarks) * w
        y = sum([lm.y for lm in iris_landmarks]) / len(iris_landmarks) * h
        
        return x, y
    
    def get_eye_center(self, eye_landmarks, frame_shape: Tuple[int, int, int]) -> Tuple[float, float]:
        """获取眼睛中心点"""
        h, w, _ = frame_shape
        
        x = sum([lm.x for lm in eye_landmarks]) / len(eye_landmarks) * w
        y = sum([lm.y for lm in eye_landmarks]) / len(eye_landmarks) * h
        
        return x, y
    
    def estimate_gaze_direction(self, landmarks, frame_shape: Tuple[int, int, int]) -> dict:
        """估算视线方向"""
        h, w, _ = frame_shape
        
        # 获取眼睛和虹膜中心
        left_eye_center = self.get_eye_center(
            [landmarks[i] for i in self.LEFT_EYE[:6]],  # 只取眼睛区域
            frame_shape
        )
        right_eye_center = self.get_eye_center(
            [landmarks[i] for i in self.RIGHT_EYE[:6]],
            frame_shape
        )
        
        # 获取虹膜中心
        left_iris_center = self.get_iris_center(
            [landmarks[i] for i in self.LEFT_IRIS],
            frame_shape
        )
        right_iris_center = self.get_iris_center(
            [landmarks[i] for i in self.RIGHT_IRIS],
            frame_shape
        )
        
        # 计算虹膜相对于眼睛的偏移
        left_offset_x = left_iris_center[0] - left_eye_center[0]
        left_offset_y = left_iris_center[1] - left_eye_center[1]
        
        right_offset_x = right_iris_center[0] - right_eye_center[0]
        right_offset_y = right_iris_center[1] - right_eye_center[1]
        
        # 平均偏移
        avg_offset_x = (left_offset_x + right_offset_x) / 2
        avg_offset_y = (left_offset_y + right_offset_y) / 2
        
        # 判断方向
        direction = "center"
        offset_threshold = 8  # 像素阈值
        
        if abs(avg_offset_x) > abs(avg_offset_y):
            if avg_offset_x < -offset_threshold:
                direction = "left"
            elif avg_offset_x > offset_threshold:
                direction = "right"
        else:
            if avg_offset_y < -offset_threshold:
                direction = "up"
            elif avg_offset_y > offset_threshold:
                direction = "down"
        
        return {
            "direction": direction,
            "offset_x": avg_offset_x,
            "offset_y": avg_offset_y,
            "left_iris": left_iris_center,
            "right_iris": right_iris_center,
            "left_eye": left_eye_center,
            "right_eye": right_eye_center
        }
    
    def detect_blink(self, left_ear: float, right_ear: float) -> Tuple[bool, bool]:
        """检测眨眼"""
        left_blink = left_ear < self.EAR_THRESHOLD
        right_blink = right_ear < self.EAR_THRESHOLD
        
        if left_blink and right_blink:
            self.blink_counter += 1
        else:
            if self.blink_counter >= self.EAR_CONSECUTIVE_FRAMES:
                self.total_blinks += 1
            self.blink_counter = 0
        
        return left_blink, right_blink
    
    def analyze(self, frame: np.ndarray) -> dict:
        """分析单帧图像"""
        h, w, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = self.face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            return {
                "face_detected": False,
                "gaze": None,
                "ear": (0.0, 0.0),
                "blinking": False,
                "attention_level": "unknown"
            }
        
        landmarks = results.multi_face_landmarks[0].landmark
        
        # 计算 EAR
        left_eye_pts = [landmarks[i] for i in self.LEFT_EYE[:6]]
        right_eye_pts = [landmarks[i] for i in self.RIGHT_EYE[:6]]
        
        left_ear = self.calculate_ear(left_eye_pts, frame.shape)
        right_ear = self.calculate_ear(right_eye_pts, frame.shape)
        avg_ear = (left_ear + right_ear) / 2
        
        # 眨眼检测
        is_blinking, _ = self.detect_blink(left_ear, right_ear)
        
        # 视线方向
        gaze_info = self.estimate_gaze_direction(landmarks, frame.shape)
        
        # 注意力等级
        attention = "high"
        if is_blinking:
            attention = "low"
        elif gaze_info["direction"] != "center":
            attention = "medium"
        
        # 更新历史
        self.gaze_history.append(gaze_info["direction"])
        
        return {
            "face_detected": True,
            "gaze": gaze_info,
            "ear": (left_ear, right_ear, avg_ear),
            "blinking": is_blinking,
            "total_blinks": self.total_blinks,
            "attention_level": attention,
            "landmarks": landmarks
        }
    
    def draw_landmarks(self, frame: np.ndarray, analysis_result: dict) -> np.ndarray:
        """在画面上绘制关键点"""
        if not analysis_result["face_detected"]:
            return frame
        
        h, w, _ = frame.shape
        landmarks = analysis_result["landmarks"]
        gaze = analysis_result["gaze"]
        
        # 绘制眼睛关键点
        for idx in self.LEFT_EYE[:6]:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
        
        for idx in self.RIGHT_EYE[:6]:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
        
        # 绘制虹膜关键点
        for idx in self.LEFT_IRIS:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 1, (255, 0, 0), -1)
        
        for idx in self.RIGHT_IRIS:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 1, (255, 0, 0), -1)
        
        # 绘制虹膜中心
        if gaze:
            lx, ly = int(gaze["left_iris"][0]), int(gaze["left_iris"][1])
            rx, ry = int(gaze["right_iris"][0]), int(gaze["right_iris"][1])
            
            cv2.circle(frame, (lx, ly), 5, (0, 0, 255), -1)
            cv2.circle(frame, (rx, ry), 5, (0, 0, 255), -1)
            
            # 绘制眼睛中心
            le_x, le_y = int(gaze["left_eye"][0]), int(gaze["left_eye"][1])
            re_x, re_y = int(gaze["right_eye"][0]), int(gaze["right_eye"][1])
            
            cv2.circle(frame, (le_x, le_y), 3, (255, 255, 0), -1)
            cv2.circle(frame, (re_x, re_y), 3, (255, 255, 0), -1)
            
            # 绘制视线方向箭头
            center_x = (lx + rx) // 2
            center_y = (ly + ry) // 2
            
            arrow_len = 30
            if gaze["direction"] == "left":
                end_x, end_y = center_x - arrow_len, center_y
            elif gaze["direction"] == "right":
                end_x, end_y = center_x + arrow_len, center_y
            elif gaze["direction"] == "up":
                end_x, end_y = center_x, center_y - arrow_len
            elif gaze["direction"] == "down":
                end_x, end_y = center_x, center_y + arrow_len
            else:
                end_x, end_y = center_x, center_y - arrow_len
            
            cv2.arrowedLine(frame, (center_x, center_y), (end_x, end_y), (0, 255, 255), 3)
        
        return frame


def test_gaze_tracking():
    """视线追踪测试"""
    
    print("=" * 60)
    print("视线追踪与注意力分析测试")
    print("=" * 60)
    
    # 初始化追踪器
    print("\n正在初始化 MediaPipe Face Mesh...")
    tracker = GazeTracker()
    print("✅ 初始化成功！")
    
    # 打开摄像头
    print("\n正在打开摄像头...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ 无法打开摄像头，请检查设备")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    print("✅ 摄像头已打开")
    print("\n" + "=" * 60)
    print("使用说明:")
    print("  - 移动头部或眼球，观察视线方向变化")
    print("  - 眨眼时会被检测到")
    print("  - 注意力等级会根据眨眼和视线方向变化")
    print("  - 按 'q' 键退出测试")
    print("  - 按 's' 键保存截图")
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
        
        # 计算帧率
        current_time = time.time()
        if current_time - last_time > 0:
            fps = 1.0 / (current_time - last_time)
            fps_history.append(fps)
        last_time = current_time
        frame_count += 1
        
        # 分析图像
        result = tracker.analyze(frame)
        
        # 绘制关键点
        frame = tracker.draw_landmarks(frame, result)
        
        # 状态栏背景
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 200), (0, 0, 0), -1)
        
        # 显示分析结果
        if result["face_detected"]:
            # 视线方向
            gaze_dir = result["gaze"]["direction"] if result["gaze"] else "unknown"
            gaze_cn = {
                "center": "正前方",
                "left": "看左边",
                "right": "看右边",
                "up": "看上边",
                "down": "看下边"
            }
            
            # 注意力等级
            attention = result["attention_level"]
            attention_cn = {
                "high": "高",
                "medium": "中",
                "low": "低"
            }
            
            # EAR
            left_ear, right_ear, avg_ear = result["ear"]
            
            # 显示信息
            frame = cv2_add_chinese_text(
                frame,
                f"视线方向: {gaze_cn.get(gaze_dir, gaze_dir)}",
                (30, 30),
                (255, 255, 0),
                22
            )
            
            frame = cv2_add_chinese_text(
                frame,
                f"注意力等级: {attention_cn.get(attention, attention)}",
                (30, 65),
                (0, 255, 255) if attention == "high" else (0, 165, 255) if attention == "medium" else (0, 0, 255),
                22
            )
            
            frame = cv2_add_chinese_text(
                frame,
                f"眨眼次数: {result['total_blinks']}",
                (30, 100),
                (255, 255, 255),
                20
            )
            
            frame = cv2_add_chinese_text(
                frame,
                f"眼睛纵横比(EAR): {avg_ear:.3f}",
                (30, 130),
                (200, 200, 200),
                18
            )
            
            # 眨眼状态
            if result["blinking"]:
                frame = cv2_add_chinese_text(
                    frame,
                    "眨眼中...",
                    (frame.shape[1] - 150, 30),
                    (0, 255, 255),
                    20
                )
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
                   (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 显示结果
        cv2.imshow("Gaze Tracking Test", frame)
        
        # 按键处理
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n用户按下 'q' 键，退出测试")
            break
        elif key == ord('s'):
            screenshot_count = sum(1 for f in __import__('os').listdir('.') if f.startswith('gaze_screenshot'))
            filename = f"gaze_screenshot_{screenshot_count + 1}.jpg"
            cv2.imwrite(filename, frame)
            print(f"📸 截图已保存: {filename}")
    
    # 清理资源
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出统计信息
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("测试结束")
    print(f"总帧数: {frame_count}")
    print(f"运行时间: {elapsed:.2f} 秒")
    print(f"平均帧率: {frame_count/elapsed:.2f} FPS")
    print(f"检测到的眨眼次数: {tracker.total_blinks}")
    print("=" * 60)


if __name__ == "__main__":
    test_gaze_tracking()
