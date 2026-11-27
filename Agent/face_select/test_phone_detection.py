"""
test_phone_detection.py - 手机检测功能测试脚本
基于 YOLOv8 官方预训练模型进行手机检测测试
"""

import cv2
import numpy as np
from ultralytics import YOLO
from collections import deque

def test_phone_detection():
    """快速测试手机检测功能"""
    
    print("=" * 60)
    print("手机检测功能测试")
    print("=" * 60)
    
    # 加载官方预训练模型（首次运行会自动下载 yolov8n.pt）
    print("\n正在加载 YOLOv8 模型...")
    try:
        model = YOLO('yolov8n.pt')
        print("✅ 模型加载成功！")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        return
    
    # COCO 数据集中手机类别 ID 是 67
    PHONE_CLASS_ID = 67
    
    # 检测参数
    CONF_THRESHOLD = 0.4        # 检测置信度阈值
    DISTRACTED_FRAMES = 10      # 连续多少帧检测到手机算分心
    
    # 状态变量
    phone_detected_frames = 0
    focus_score = 100
    is_distracted = False
    
    # 帧率统计
    frame_count = 0
    fps_history = deque(maxlen=30)
    
    # 打开摄像头
    print("\n正在打开摄像头...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ 无法打开摄像头，请检查设备")
        return
    
    # 设置摄像头参数
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print("✅ 摄像头已打开")
    print("\n" + "=" * 60)
    print("使用说明:")
    print("  - 将手机放在摄像头前测试检测效果")
    print("  - 连续检测到手机 10 帧后会判定为分心")
    print("  - 按 'q' 键退出测试")
    print("=" * 60 + "\n")
    
    import time
    start_time = time.time()
    last_time = start_time
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ 无法读取摄像头画面")
            break
        
        # 计算帧率
        current_time = time.time()
        if current_time - last_time > 0:
            fps = 1.0 / (current_time - last_time)
            fps_history.append(fps)
        last_time = current_time
        frame_count += 1
        
        # 运行 YOLO 检测
        results = model(frame, conf=CONF_THRESHOLD, verbose=False)
        
        phone_detected = False
        phone_conf = 0
        phone_boxes = []
        
        # 遍历检测结果，找出手机
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id == PHONE_CLASS_ID:
                phone_detected = True
                phone_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                phone_boxes.append((x1, y1, x2, y2, phone_conf))
                
                # 绘制红框和文字
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"Phone {phone_conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # 时序平滑：连续多帧检测到手机才判定为分心
        if phone_detected:
            phone_detected_frames += 1
        else:
            phone_detected_frames = max(0, phone_detected_frames - 2)  # 快速恢复
        
        # 计算专注度评分
        if phone_detected_frames >= DISTRACTED_FRAMES:
            is_distracted = True
            focus_score = 0
            status = "DISTRACTED - Phone in use!"
            color = (0, 0, 255)  # 红色
        else:
            is_distracted = False
            # 根据检测到的置信度逐渐扣分
            if phone_detected:
                focus_score = max(0, 100 - phone_conf * 100)
            else:
                focus_score = min(100, focus_score + 5)  # 慢慢恢复
            status = f"FOCUSED - Score: {focus_score:.0f}"
            color = (0, 255, 0)  # 绿色
        
        # 在画面上显示信息
        # 状态信息
        cv2.putText(frame, status, (30, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        
        # 帧计数
        cv2.putText(frame, f"Phone frames: {phone_detected_frames}/{DISTRACTED_FRAMES}", 
                   (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # FPS
        avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0
        cv2.putText(frame, f"FPS: {avg_fps:.1f}", 
                   (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 检测到的手机数量
        cv2.putText(frame, f"Phones detected: {len(phone_boxes)}", 
                   (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 显示结果
        cv2.imshow("Phone Detection Test", frame)
        
        # 按 'q' 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n用户按下 'q' 键，退出测试")
            break
    
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
    print("=" * 60)


if __name__ == "__main__":
    test_phone_detection()
