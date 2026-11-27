"""
test_multi_object_detection.py - 多物品检测测试脚本
支持检测手机、书、水杯、瓶子等多种物品
"""

import cv2
import numpy as np
from ultralytics import YOLO
from collections import deque
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont

# COCO 数据集类别定义
COCO_CLASSES = {
    0: "person",
    39: "bottle",
    40: "wine glass",
    41: "cup",
    56: "chair",
    62: "tv",
    63: "laptop",
    64: "mouse",
    66: "keyboard",
    67: "cell phone",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
}

# 中文映射
COCO_CLASSES_CN = {
    0: "人",
    39: "瓶子",
    40: "酒杯",
    41: "杯子",
    56: "椅子",
    62: "显示器",
    63: "笔记本电脑",
    64: "鼠标",
    66: "键盘",
    67: "手机",
    73: "书",
    74: "时钟",
    75: "花瓶",
    76: "剪刀",
}

# 物品状态配置（不同物品对应不同状态）
ITEM_STATUS_CONFIG = {
    67: {"status": "分心", "type": "distraction", "message": "正在使用手机"},      # 手机 - 分心
    73: {"status": "学习中", "type": "neutral", "message": "正在看书"},           # 书 - 中性（学习）
    41: {"status": "口渴了", "type": "need_water", "message": "可能需要喝水"},    # 杯子 - 口渴
    39: {"status": "口渴了", "type": "need_water", "message": "可能需要喝水"},    # 瓶子 - 口渴
    40: {"status": "口渴了", "type": "need_water", "message": "可能需要喝水"},    # 酒杯 - 口渴
    63: {"status": "分心", "type": "distraction", "message": "正在使用电脑"},     # 笔记本 - 分心
}

# 颜色配置（BGR格式）
ITEM_COLORS = {
    67: (0, 0, 255),    # 手机 - 红色
    73: (255, 165, 0),  # 书 - 橙色
    41: (0, 255, 255),  # 杯子 - 黄色
    39: (255, 0, 255),  # 瓶子 - 紫色
    40: (255, 200, 0),  # 酒杯 - 青橙色
    63: (255, 255, 0),  # 笔记本 - 青色
}


def cv2_add_chinese_text(img, text, position, text_color=(255, 255, 255), font_size=20):
    """在 OpenCV 图像上绘制中文文字"""
    # 转换为 PIL 图像
    if isinstance(img, np.ndarray):
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    else:
        img_pil = img
    
    draw = ImageDraw.Draw(img_pil)
    
    # 尝试加载中文字体
    try:
        font = ImageFont.truetype("simsun.ttc", font_size, encoding="utf-8")
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", font_size, encoding="utf-8")
        except:
            font = ImageFont.load_default()
    
    # 绘制文字
    draw.text(position, text, text_color, font=font)
    
    # 转换回 OpenCV 格式
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def test_multi_object_detection():
    """多物品检测测试"""
    
    print("=" * 60)
    print("多物品检测功能测试")
    print("=" * 60)
    
    # 要检测的物品类别（可以自定义）
    # 添加更多杯子相关类别：cup(41)、bottle(39)、wine glass(40)
    TARGET_CLASSES = [67, 73, 41, 39, 40, 63]  # 手机、书、杯子、瓶子、酒杯、笔记本
    
    print("\n将检测以下物品:")
    for cls_id in TARGET_CLASSES:
        print(f"  - {COCO_CLASSES_CN.get(cls_id, COCO_CLASSES.get(cls_id, '未知'))} (ID: {cls_id})")
    
    # 加载模型
    print("\n正在加载 YOLOv8 模型...")
    print("使用 yolov8m.pt (中等模型，精度更高)")
    try:
        # 使用 yolov8m.pt 提高精度
        model = YOLO('yolov8m.pt')
        print("✅ 模型加载成功！")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        return
    
    # 检测参数
    CONF_THRESHOLD = 0.25      # 检测置信度阈值（降低以提高召回率）
    DETECTED_FRAMES_THRESHOLD = 10  # 连续多少帧检测到物品算确认
    
    # 状态变量（记录每个物品的连续检测帧数）
    item_frame_count: Dict[int, int] = {cls_id: 0 for cls_id in ITEM_STATUS_CONFIG.keys()}
    
    # 帧率统计
    frame_count = 0
    fps_history = deque(maxlen=30)
    
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
    print("  - 将物品放在摄像头前测试检测效果")
    print("  - 不同物品对应不同状态:")
    for cls_id, config in ITEM_STATUS_CONFIG.items():
        item_name = COCO_CLASSES_CN.get(cls_id, "?")
        print(f"    {item_name}: {config['status']} - {config['message']}")
    print("  - 按 'q' 键退出测试")
    print("  - 按 's' 键保存截图")
    print("=" * 60 + "\n")
    
    import time
    start_time = time.time()
    last_time = start_time
    screenshot_count = 0
    
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
        
        # 运行 YOLO 检测
        results = model(frame, conf=CONF_THRESHOLD, verbose=False)
        
        detected_items: Dict[int, List[Tuple]] = {cls_id: [] for cls_id in TARGET_CLASSES}
        
        # 遍历检测结果
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            
            if cls_id in TARGET_CLASSES:
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                detected_items[cls_id].append((x1, y1, x2, y2, conf))
                
                # 获取颜色
                color = ITEM_COLORS.get(cls_id, (200, 200, 200))
                
                # 绘制检测框
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # 标签文字（使用 PIL 绘制中文）
                label = f"{COCO_CLASSES_CN.get(cls_id, COCO_CLASSES.get(cls_id, '?'))} {conf:.2f}"
                frame = cv2_add_chinese_text(frame, label, (x1 + 5, y1 - 25), color, 18)
        
        # 分心检测逻辑
        confirmed_items = []  # 确认检测到的物品
        
        for cls_id in ITEM_STATUS_CONFIG.keys():
            if detected_items.get(cls_id):
                item_frame_count[cls_id] += 1
            else:
                item_frame_count[cls_id] = max(0, item_frame_count[cls_id] - 2)
            
            # 连续检测到足够帧数，确认该物品
            if item_frame_count[cls_id] >= DETECTED_FRAMES_THRESHOLD:
                confirmed_items.append(cls_id)
        
        # 根据检测到的物品判断状态
        status_messages = []
        status_color = (0, 255, 0)  # 默认绿色（专注）
        
        if confirmed_items:
            # 按优先级排序：分心 > 口渴 > 学习中
            priority_order = {"distraction": 3, "need_water": 2, "neutral": 1}
            
            # 找出最高优先级的状态类型
            max_priority = 0
            for cls_id in confirmed_items:
                item_type = ITEM_STATUS_CONFIG[cls_id]["type"]
                priority = priority_order.get(item_type, 0)
                if priority > max_priority:
                    max_priority = priority
            
            # 收集所有该优先级的物品信息
            for cls_id in confirmed_items:
                config = ITEM_STATUS_CONFIG[cls_id]
                item_type = config["type"]
                if priority_order.get(item_type, 0) == max_priority:
                    item_name = COCO_CLASSES_CN.get(cls_id, "?")
                    status_messages.append(f"{item_name}: {config['message']}")
                    
                    # 设置颜色
                    if item_type == "distraction":
                        status_color = (0, 0, 255)  # 红色
                    elif item_type == "need_water":
                        status_color = (255, 165, 0)  # 橙色
                    else:
                        status_color = (255, 255, 0)  # 青色
        
        # ========== 在画面上显示信息 ==========
        
        # 状态栏背景
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 180), (0, 0, 0), -1)
        
        # 状态信息
        if status_messages:
            # 显示主状态
            main_status = ITEM_STATUS_CONFIG[confirmed_items[0]]["status"]
            frame = cv2_add_chinese_text(frame, f"状态: {main_status}", (30, 15), status_color, 24)
            
            # 显示详细信息
            for idx, msg in enumerate(status_messages[:3]):  # 最多显示3条
                frame = cv2_add_chinese_text(frame, msg, (30, 50 + idx * 30), (255, 255, 255), 18)
        else:
            frame = cv2_add_chinese_text(frame, "状态: 专注", (30, 15), status_color, 24)
            frame = cv2_add_chinese_text(frame, "未检测到异常物品", (30, 50), (255, 255, 255), 18)
        
        # FPS
        avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0
        cv2.putText(frame, f"FPS: {avg_fps:.1f}", 
                   (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 检测到的物品列表
        detected_summary = []
        for cls_id, items in detected_items.items():
            if items:
                name = COCO_CLASSES_CN.get(cls_id, COCO_CLASSES.get(cls_id, '?'))
                detected_summary.append(f"{name}x{len(items)}")
        
        if detected_summary:
            detected_text = f"实时检测: {', '.join(detected_summary)}"
            frame = cv2_add_chinese_text(frame, detected_text, (frame.shape[1] - 300, 15), (200, 200, 200), 16)
        
        # 显示结果
        cv2.imshow("Multi-Object Detection Test", frame)
        
        # 按键处理
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n用户按下 'q' 键，退出测试")
            break
        elif key == ord('s'):
            # 保存截图
            screenshot_count += 1
            filename = f"detection_screenshot_{screenshot_count}.jpg"
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
    print("=" * 60)


def show_all_coco_classes():
    """显示所有 COCO 类别"""
    print("\n" + "=" * 60)
    print("COCO 数据集完整类别列表 (共 80 类)")
    print("=" * 60)
    
    # COCO 完整类别
    all_classes = [
        (0, "person", "人"),
        (1, "bicycle", "自行车"),
        (2, "car", "汽车"),
        (3, "motorcycle", "摩托车"),
        (4, "airplane", "飞机"),
        (5, "bus", "公交车"),
        (6, "train", "火车"),
        (7, "truck", "卡车"),
        (8, "boat", "船"),
        (9, "traffic light", "红绿灯"),
        (10, "fire hydrant", "消防栓"),
        (11, "stop sign", "停止标志"),
        (12, "parking meter", "停车计时器"),
        (13, "bench", "长椅"),
        (14, "bird", "鸟"),
        (15, "cat", "猫"),
        (16, "dog", "狗"),
        (17, "horse", "马"),
        (18, "sheep", "羊"),
        (19, "cow", "牛"),
        (20, "elephant", "大象"),
        (21, "bear", "熊"),
        (22, "zebra", "斑马"),
        (23, "giraffe", "长颈鹿"),
        (24, "backpack", "背包"),
        (25, "umbrella", "雨伞"),
        (26, "handbag", "手提包"),
        (27, "tie", "领带"),
        (28, "suitcase", "行李箱"),
        (29, "frisbee", "飞盘"),
        (30, "skis", "滑雪板"),
        (31, "snowboard", "滑雪板"),
        (32, "sports ball", "运动球"),
        (33, "kite", "风筝"),
        (34, "baseball bat", "棒球棒"),
        (35, "baseball glove", "棒球手套"),
        (36, "skateboard", "滑板"),
        (37, "surfboard", "冲浪板"),
        (38, "tennis racket", "网球拍"),
        (39, "bottle", "瓶子"),
        (40, "wine glass", "酒杯"),
        (41, "cup", "杯子"),
        (42, "fork", "叉子"),
        (43, "knife", "刀"),
        (44, "spoon", "勺子"),
        (45, "bowl", "碗"),
        (46, "banana", "香蕉"),
        (47, "apple", "苹果"),
        (48, "sandwich", "三明治"),
        (49, "orange", "橙子"),
        (50, "broccoli", "西兰花"),
        (51, "carrot", "胡萝卜"),
        (52, "hot dog", "热狗"),
        (53, "pizza", "披萨"),
        (54, "donut", "甜甜圈"),
        (55, "cake", "蛋糕"),
        (56, "chair", "椅子"),
        (57, "couch", "沙发"),
        (58, "potted plant", "盆栽"),
        (59, "bed", "床"),
        (60, "dining table", "餐桌"),
        (61, "toilet", "马桶"),
        (62, "tv", "电视"),
        (63, "laptop", "笔记本电脑"),
        (64, "mouse", "鼠标"),
        (65, "remote", "遥控器"),
        (66, "keyboard", "键盘"),
        (67, "cell phone", "手机"),
        (68, "microwave", "微波炉"),
        (69, "oven", "烤箱"),
        (70, "toaster", "烤面包机"),
        (71, "sink", "水槽"),
        (72, "refrigerator", "冰箱"),
        (73, "book", "书"),
        (74, "clock", "时钟"),
        (75, "vase", "花瓶"),
        (76, "scissors", "剪刀"),
        (77, "teddy bear", "泰迪熊"),
        (78, "hair drier", "吹风机"),
        (79, "toothbrush", "牙刷"),
    ]
    
    for cls_id, en_name, cn_name in all_classes:
        print(f"  {cls_id:2d}: {cn_name:8s} ({en_name})")
    
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        show_all_coco_classes()
    else:
        test_multi_object_detection()
