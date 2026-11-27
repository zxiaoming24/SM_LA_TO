import math
import os
import sys

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from joblib import load

# 从其他模块导入
try:
    from sitting_posture.to_xlsx.PicProcess import detect_pose
except ImportError:
    print("警告: 无法导入 detect_pose 函数")
    def detect_pose(*args, **kwargs):
        return False, None


def get_font(font_size=30):
    """
    尝试加载中文字体，如果失败则使用默认字体
    """
    # 尝试不同系统的常见中文字体路径
    font_paths = [
        "simsun.ttc",  # Windows
        "/System/Library/Fonts/STHeiti Light.ttc",  # macOS
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
    ]
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, font_size, encoding="utf-8")
        except:
            continue
    
    # 如果都失败，使用默认字体
    print("警告: 未找到中文字体，使用默认字体")
    return ImageFont.load_default()


def rotation_matrix_to_angles(rotation_matrix):
    """
    Calculate Euler angles from rotation matrix.
    :param rotation_matrix: A 3 * 3 matrix with the following structure
    [Cosz*Cosy  Cosz*Siny*Sinx - Sinz*Cosx  Cosz*Siny*Cosx + Sinz*Sinx]
    [Sinz*Cosy  Sinz*Siny*Sinx + Sinz*Cosx  Sinz*Siny*Cosx - Cosz*Sinx]
    [  -Siny             CosySinx                   Cosy*Cosx         ]
    :return: Angles in degrees for each axis
    """
    x = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
    y = math.atan2(-rotation_matrix[2, 0], math.sqrt(rotation_matrix[0, 0] ** 2 +
                                                     rotation_matrix[1, 0] ** 2))
    z = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    return np.array([x, y, z]) * 180. / math.pi


# 初始化 MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# 面部关键点在真实世界中的坐标（单位：mm）
face_coordination_in_real_world = np.array([
    [285, 528, 200],
    [285, 371, 152],
    [197, 574, 128],
    [173, 425, 108],
    [360, 574, 128],
    [391, 425, 108]
], dtype=np.float64)


def HeadInfo(image):
    """
    从图像中检测头部姿态
    返回: pitch, yaw, roll 角度
    """
    if image is None or image.size == 0:
        return 0.0, 0.0, 0.0
    
    # 转换颜色空间
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # 进行面部检测
    results = face_mesh.process(image_rgb)
    
    h, w, _ = image.shape
    face_coordination_in_image = []

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            for idx, lm in enumerate(face_landmarks.landmark):
                if idx in [1, 9, 57, 130, 287, 359]:
                    x, y = int(lm.x * w), int(lm.y * h)
                    face_coordination_in_image.append([x, y])

            if len(face_coordination_in_image) == 6:
                face_coordination_in_image = np.array(face_coordination_in_image, 
                                                      dtype=np.float64)

                # 相机内参矩阵
                focal_length = 1.0 * w
                cam_matrix = np.array([[focal_length, 0, w / 2],
                                       [0, focal_length, h / 2],
                                       [0, 0, 1]])

                # 畸变系数（假设无畸变）
                dist_matrix = np.zeros((4, 1), dtype=np.float64)

                # 使用 solvePnP 获取旋转向量
                success, rotation_vec, transition_vec = cv2.solvePnP(
                    face_coordination_in_real_world, 
                    face_coordination_in_image,
                    cam_matrix, 
                    dist_matrix
                )

                if success:
                    # 将旋转向量转换为旋转矩阵
                    rotation_matrix, _ = cv2.Rodrigues(rotation_vec)
                    result = rotation_matrix_to_angles(rotation_matrix)
                    
                    pitch, yaw, roll = result[0], result[1], result[2]
                    return float(pitch), float(yaw), float(roll)
    
    # 检测失败时返回默认值
    return 0.0, 0.0, 0.0


def cv2AddChineseText(img, text, position, textColor=(0, 255, 0), font=None, textSize=30):
    """
    在OpenCV图像上添加中文文本
    """
    if img is None:
        return None
    
    if font is None:
        font = get_font(textSize)
    
    if isinstance(img, np.ndarray):
        # 转换为PIL格式
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    else:
        img_pil = img
    
    draw = ImageDraw.Draw(img_pil)
    
    # 绘制文本
    draw.text(position, text, font=font, fill=textColor)
    
    # 转换回OpenCV格式
    return cv2.cvtColor(np.asarray(img_pil), cv2.COLOR_RGB2BGR)


def load_head_model(model_path):
    """
    加载头部姿态模型
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    
    try:
        model = load(model_path)
        print(f"模型加载成功: {model_path}")
        return model
    except Exception as e:
        raise Exception(f"加载模型失败: {e}")


def get_posture_label(prediction, pitch, yaw, roll):
    """
    根据模型预测和角度值判断姿势
    """
    # 将numpy标量转换为Python整数
    if hasattr(prediction, 'item'):
        pred_value = int(prediction.item())
    else:
        pred_value = int(prediction)
    
    # 姿势判断逻辑
    if pred_value == 1 or pitch < -20:
        return "Lower one's head", pred_value
    elif pred_value == 2:
        return "Tilted neck", pred_value
    elif pred_value == 3:
        return "Stretch one's neck", pred_value
    else:
        return "Normal sitting posture", pred_value


def main():
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 加载字体
    try:
        font = get_font(20)
        title_font = get_font(24)
    except Exception as e:
        print(f"字体加载失败: {e}")
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
    
    # 加载模型
    model_path = os.path.join(script_dir, 'model3/model/ModelHead.pkl')
    try:
        modelHead = load_head_model(model_path)
    except Exception as e:
        print(f"错误: {e}")
        print("将使用角度阈值进行姿势判断")
        modelHead = None
    
    # 初始化摄像头
    video = cv2.VideoCapture(1)
    if not video.isOpened():
        print("无法打开摄像头，请检查摄像头连接")
        
        # 尝试打开默认视频文件
        video_path = os.path.join(script_dir, 'video/Normal1.mp4')
        if os.path.exists(video_path):
            print(f"尝试打开视频文件: {video_path}")
            video = cv2.VideoCapture(video_path)
        else:
            print("没有找到可用的视频源")
            return
    
    print("摄像头/视频打开成功")
    
    # 设置显示尺寸
    display_width, display_height = 640, 480
    
    # 初始化姿势检测
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    # 帧率统计
    fps = 0
    frame_count = 0
    start_time = cv2.getTickCount()
    
    try:
        while video.isOpened():
            success, frame = video.read()
            if not success:
                print("无法读取帧，退出")
                break
            
            # 翻转图像（镜像效果）
            frame = cv2.flip(frame, 1)
            
            # 创建显示用的图像副本
            display_frame = cv2.resize(frame, (display_width, display_height))
            
            # 头部姿态检测
            pitch, yaw, roll = HeadInfo(display_frame)
            
            # 姿势判断
            if modelHead is not None:
                Headtest = [[pitch, yaw, roll]]
                try:
                    prediction = modelHead.predict(Headtest)[0]
                except Exception as e:
                    print(f"模型预测失败: {e}")
                    prediction = 0
            else:
                # 如果没有模型，使用简单阈值
                prediction = 0
                if pitch < -20:
                    prediction = 1
            
            # 获取姿势标签
            posture_label, pred_value = get_posture_label(prediction, pitch, yaw, roll)
            
            # 计算帧率
            frame_count += 1
            if frame_count >= 30:
                end_time = cv2.getTickCount()
                elapsed_time = (end_time - start_time) / cv2.getTickFrequency()
                fps = frame_count / elapsed_time
                frame_count = 0
                start_time = end_time
            
            # 在图像上绘制信息
            # 绘制标题
            display_frame = cv2AddChineseText(
                display_frame, 
                "Sitting Posture Detection System", 
                (10, 10), 
                (0, 0, 255), 
                title_font, 
                24
            )
            
            # 绘制姿势状态
            color = (0, 255, 0) if posture_label == "正常坐姿" else (0, 0, 255)
            display_frame = cv2AddChineseText(
                display_frame, 
                f"Posture: {posture_label}", 
                (10, 50), 
                color, 
                font, 
                20
            )
            
            # 绘制角度信息
            display_frame = cv2AddChineseText(
                display_frame, 
                f"Pitch: {pitch:6.1f}°", 
                (10, 80), 
                (255, 200, 0), 
                font, 
                20
            )
            display_frame = cv2AddChineseText(
                display_frame, 
                f"Yaw:   {yaw:6.1f}°", 
                (10, 110), 
                (255, 200, 0), 
                font, 
                20
            )
            display_frame = cv2AddChineseText(
                display_frame, 
                f"Roll:  {roll:6.1f}°", 
                (10, 140), 
                (255, 200, 0), 
                font, 
                20
            )
            
            # 绘制模型预测结果
            display_frame = cv2AddChineseText(
                display_frame, 
                f"Model Prediction: {pred_value}", 
                (10, 170), 
                (200, 100, 255), 
                font, 
                20
            )
            
            # 绘制帧率
            display_frame = cv2AddChineseText(
                display_frame, 
                f"FPS: {fps:5.1f}", 
                (display_width - 120, 20), 
                (0, 255, 255), 
                font, 
                20
            )
            
            # 绘制提示信息
            display_frame = cv2AddChineseText(
                display_frame, 
                "Press 'q' to quit", 
                (10, display_height - 30), 
                (200, 200, 200), 
                font, 
                18
            )
            
            # 显示图像
            cv2.imshow('Sitting Posture Detection System', display_frame)
            
            # 处理键盘输入
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("用户退出")
                break
            elif key == ord(' '):
                # 空格键暂停/继续
                while True:
                    key2 = cv2.waitKey(1) & 0xFF
                    if key2 == ord(' '):
                        break
                    elif key2 == ord('q'):
                        cv2.destroyAllWindows()
                        return
                    
    except KeyboardInterrupt:
        print("程序被中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 释放资源
        print("正在释放资源...")
        video.release()
        cv2.destroyAllWindows()
        if 'pose' in locals():
            pose.close()
        if 'face_mesh' in globals():
            face_mesh.close()
        print("程序退出")


if __name__ == '__main__':
    main()