"""
test_distraction.py - 综合分心检测 + 注意力偏好测试
功能：
1. 实时检测视线和物品
2. 定期调用大模型分析
3. 综合判定分心状态
4. 可视化显示结果
5. 键盘模拟进入资源页面 → 通过眼动计算偏好
"""

import cv2
import numpy as np
import time
import asyncio
from collections import deque
import argparse

from eyesss_test_mm.distraction_detector import DistractionDetector
from eyesss_test_mm.config import DistractionConfig
from eyesss_test_mm.attention_tracker import AttentionTracker
from eyesss_test_mm.attention_profile import get_profile

# 资源类型映射
RESOURCE_KEY_MAP = {
    ord('1'): "video",
    ord('2'): "doc",
    ord('3'): "practice",
    ord('4'): "mindmap",
    ord('5'): "extension",
    ord('6'): "animation",
}

RESOURCE_HELP = {
    "video": "1-视频",
    "doc": "2-文档",
    "practice": "3-练习",
    "mindmap": "4-思维导图",
    "extension": "5-拓展",
    "animation": "6-动画",
}


def cv2_add_chinese_text(img, text, position, font_size=20, color=(255, 255, 255)):
    """在OpenCV图像上绘制中文文字"""
    from PIL import Image, ImageDraw, ImageFont
    
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    font = None
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except:
            continue
    
    if font is None:
        font = ImageFont.load_default()
    
    draw.text(position, text, font=font, fill=color[::-1])
    
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def draw_attention_bar(img, score, position, width=200, height=20):
    """绘制注意力进度条"""
    x, y = position
    cv2.rectangle(img, (x, y), (x + width, y + height), (50, 50, 50), -1)
    progress_width = int(width * score / 100)
    
    if score >= 80:
        color = (0, 255, 0)
    elif score >= 60:
        color = (0, 255, 255)
    else:
        color = (0, 0, 255)
    
    cv2.rectangle(img, (x, y), (x + progress_width, y + height), color, -1)
    cv2.rectangle(img, (x, y), (x + width, y + height), (255, 255, 255), 1)
    cv2.putText(img, f"{score}%", (x + width + 10, y + height - 5),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def draw_preference_bar(img, pref_value, position, width=150, height=12,
                        label="", color=(0, 255, 0)):
    """绘制偏好值小横条"""
    x, y = position
    # 背景
    cv2.rectangle(img, (x, y), (x + width, y + height), (40, 40, 40), -1)
    # 进度：pref_value 范围 0~1
    pw = int(width * pref_value)
    bar_color = (0, 255, 0) if pref_value > 0.6 else \
                (0, 255, 255) if pref_value > 0.4 else (0, 0, 255)
    cv2.rectangle(img, (x, y), (x + pw, y + height), bar_color, -1)
    cv2.rectangle(img, (x, y), (x + width, y + height), (100, 100, 100), 1)
    # 标签
    text_x = x + width + 5
    cv2.putText(img, f"{label}:{pref_value:.2f}", (text_x, y + height - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)


async def async_test_distraction_detection(enable_llm: bool = True):
    """异步测试综合分心检测 + 注意力偏好"""
    
    print("=" * 60)
    print("综合分心检测 + 注意力偏好测试")
    print("=" * 60)
    
    # 初始化检测器
    print("\n正在初始化检测器...")
    detector = DistractionDetector(enable_llm=enable_llm)
    print("检测器初始化完成")
    
    # 初始化注意力追踪
    tracker = AttentionTracker()
    current_user = "test_user_001"
    profile = get_profile(current_user)
    print(f"注意力画像已加载: {profile.total_sessions} 次历史记录")
    
    # 打开摄像头
    print("\n正在打开摄像头...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    print("摄像头已打开")
    
    # 状态变量
    frame_count = 0
    fps_history = deque(maxlen=30)
    start_time = time.time()
    last_time = start_time
    current_resource_type = ""
    last_leave_notification = ""  # 最近一次离开的提示
    notification_time = 0
    
    print("\n使用说明:")
    print("  [按键]")
    print("  1-视频  2-文档  3-练习  4-思维导图  5-拓展  6-动画")
    print("  0-离开当前资源  s-画像摘要  q-退出")
    
    # 主循环
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        current_time = time.time()
        if current_time - last_time > 0:
            fps = 1.0 / (current_time - last_time)
            fps_history.append(fps)
        last_time = current_time
        frame_count += 1
        
        # 异步综合检测
        result = await detector.async_detect(frame)
        
        # ========== 获取眼动数据 并 推入追踪器 ==========
        gaze_data = result.get("gaze", {})
        if gaze_data.get("face_detected") and tracker.has_active_session(current_user):
            tracker.add_gaze(
                current_user,
                gaze_data.get("gaze_offset_x", 0),
                gaze_data.get("gaze_offset_y", 0),
                gaze_data.get("head_pose", {}).get("pitch", 0),
                gaze_data.get("head_pose", {}).get("yaw", 0),
                final_result.get("is_distracted", False),
                timestamp=current_time,
            )
        
        # 获取最终结果
        final_result = result.get("final_result", {})
        is_distracted = final_result.get("is_distracted", False)
        distraction_level = final_result.get("distraction_level", "none")
        attention_score = final_result.get("attention_score", 100)
        reasons = final_result.get("reasons", [])
        
        # 绘制检测结果
        annotated = frame.copy()
        
        # 1. 物品检测框
        if result.get("objects") and detector.object_detector:
            annotated = detector.object_detector.annotate_frame(annotated, result["objects"])
        
        # 2. 视线方向指示
        if gaze_data.get("face_detected"):
            gx = gaze_data.get("gaze_offset_x", 0)
            gy = gaze_data.get("gaze_offset_y", 0)
            cx, cy = annotated.shape[1] // 2, annotated.shape[0] // 2
            ex = int(cx + gx * 100)
            ey = int(cy + gy * 100)
            cv2.circle(annotated, (cx, cy), 5, (0, 255, 0), -1)
            cv2.arrowedLine(annotated, (cx, cy), (ex, ey), (0, 255, 255), 2, tipLength=0.3)
        
        # ========== 左上区域：分心状态 ==========
        y_offset = 30
        
        # 分心状态
        if is_distracted:
            status_text = f"状态: 分心 ({distraction_level})"
            status_color = (0, 0, 255)
        else:
            status_text = "状态: 专注"
            status_color = (0, 255, 0)
        annotated = cv2_add_chinese_text(annotated, status_text, (30, y_offset),
                                         font_size=24, color=status_color)
        y_offset += 40
        
        # 注意力分数 + 进度条
        annotated = cv2_add_chinese_text(annotated, f"注意力分数: {attention_score}",
                                         (30, y_offset), font_size=20)
        y_offset += 30
        draw_attention_bar(annotated, attention_score, (30, y_offset))
        y_offset += 40
        
        # 分心原因
        if reasons:
            annotated = cv2_add_chinese_text(annotated, "原因:", (30, y_offset), font_size=18)
            y_offset += 25
            for reason in reasons[:3]:
                annotated = cv2_add_chinese_text(annotated, f"  - {reason}",
                                                 (30, y_offset), font_size=16)
                y_offset += 22
        
        # ========== 中左区域：偏好画像 ==========
        y_offset += 10
        annotated = cv2_add_chinese_text(annotated, "--- 资源偏好 ---", (30, y_offset), font_size=18, color=(0, 255, 255))
        y_offset += 25
        
        pref_summary = profile.get_summary()
        # 绘制前3个偏好条形图
        sorted_prefs = sorted(pref_summary["effective"].items(), key=lambda x: x[1], reverse=True)
        for rtype, val in sorted_prefs:
            cn = RESOURCE_HELP.get(rtype, rtype)
            draw_preference_bar(annotated, val, (30, y_offset), width=150,
                                label=cn, color=(0, 255, 0))
            y_offset += 17
        
        conf_text = f"总次数:{pref_summary['total_sessions']} 置信度:{pref_summary['overall_confidence']:.2f}"
        annotated = cv2_add_chinese_text(annotated, conf_text, (30, y_offset), font_size=14, color=(180, 180, 180))
        
        # ========== 右上区域：当前会话状态 ==========
        session = tracker.get_current_session(current_user)
        if session:
            sx = annotated.shape[1] - 280
            sy = 30
            annotated = cv2_add_chinese_text(annotated,
                f"当前: {RESOURCE_HELP.get(session['resource_type'], session['resource_type'])}",
                (sx, sy), font_size=20, color=(0, 255, 255))
            sy += 25
            annotated = cv2_add_chinese_text(annotated,
                f"已采集: {session['elapsed']:.1f}s / {session['frames']}帧",
                (sx, sy), font_size=18, color=(200, 200, 200))
        else:
            cv2.putText(annotated, "当前: 无会话",
                       (annotated.shape[1] - 200, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        
        # 离开提示（显示5秒）
        if last_leave_notification and current_time - notification_time < 5:
            cv2.putText(annotated, last_leave_notification,
                       (annotated.shape[1] - 350, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # ========== 底部信息 ==========
        hh = annotated.shape[0]
        if gaze_data.get("face_detected"):
            face_info = f"视线: {gaze_data.get('gaze_direction', '')}"
            annotated = cv2_add_chinese_text(annotated, face_info,
                                             (30, hh - 80), font_size=18)
            blink_info = f"眨眼: {gaze_data.get('blink_rate', 0):.1f}次/分"
            annotated = cv2_add_chinese_text(annotated, blink_info,
                                             (30, hh - 55), font_size=18)
        annotated = cv2_add_chinese_text(annotated, "按键: 1视频 2文档 3练习 4导图 0离开",
                                         (30, hh - 25), font_size=14, color=(150, 150, 150))
        
        avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0
        cv2.putText(annotated, f"FPS: {avg_fps:.1f}",
                   (annotated.shape[1] - 120, hh - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 显示结果
        cv2.imshow("Distraction Detection + Attention Preference", annotated)
        
        # ========== 键盘控制 ==========
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n退出测试")
            break
        
        elif key == ord('0'):
            # 离开当前资源
            if tracker.has_active_session(current_user):
                result_leave = tracker.on_leave(current_user)
                if result_leave and result_leave.get("valid"):
                    imm = result_leave["immersion_score"]
                    rt = result_leave["resource_type"]
                    pu = result_leave.get("profile_update", {})
                    print(f"\n[离开] {RESOURCE_HELP.get(rt, rt)}"
                          f"  沉浸分={imm:.3f}"
                          f"  偏好:{pu.get('old_score', 0.5):.3f}->{pu.get('new_score', 0.5):.3f}")
                    last_leave_notification = (f"{RESOURCE_HELP.get(rt, rt)}离开"
                                               f" 沉浸:{imm:.2f} 偏好:{pu.get('new_score', 0):.2f}")
                    notification_time = current_time
                elif result_leave:
                    print(f"\n[离开] 数据不足({result_leave.get('reason', '')})，未更新偏好")
                    last_leave_notification = f"数据不足，未更新偏好"
                    notification_time = current_time
                else:
                    print("\n[离开] 无活跃会话")
            else:
                print("\n[离开] 当前无活跃会话")
        
        elif key in RESOURCE_KEY_MAP:
            # 进入资源页面
            rtype = RESOURCE_KEY_MAP[key]
            tracker.on_enter(current_user, rtype, knowledge_point="实时测试")
            print(f"\n[进入] 开始采集 {RESOURCE_HELP.get(rtype, rtype)} 的眼动数据...")
            last_leave_notification = f"采集 {RESOURCE_HELP.get(rtype, rtype)}..."
            notification_time = current_time
        
        elif key == ord('s'):
            # 显示完整画像
            s = profile.get_summary()
            print("\n" + "=" * 50)
            print(f"  偏好画像 ({current_user})")
            print("=" * 50)
            for k, v in s["effective"].items():
                print(f"  {RESOURCE_HELP.get(k, k)}: {v:.3f}  (原始:{s['preferences'].get(k, 0.5):.3f}, 置信度:{s['confidence'].get(k, 0):.3f})")
            print(f"  总行为次数: {s['total_sessions']}")
            print(f"  最喜欢: {RESOURCE_HELP.get(s['top_type'], s['top_type'])}")
            print("=" * 50)
    
    # 清理
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出最终报告
    s = profile.get_summary()
    print("\n" + "=" * 60)
    print("测试结束 - 注意力偏好报告")
    print("=" * 60)
    print(f"  用户: {current_user}")
    print(f"  总行为次数: {s['total_sessions']}")
    print(f"  最喜欢类型: {RESOURCE_HELP.get(s['top_type'], s['top_type'])}")
    print(f"  偏好排序:")
    sorted_prefs = sorted(s["effective"].items(), key=lambda x: x[1], reverse=True)
    for rtype, val in sorted_prefs:
        print(f"    {RESOURCE_HELP.get(rtype, rtype)}: {val:.3f}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="综合分心检测 + 注意力偏好测试")
    parser.add_argument("--no-llm", action="store_true", help="禁用大模型分析")
    args = parser.parse_args()
    asyncio.run(async_test_distraction_detection(enable_llm=not args.no_llm))


if __name__ == "__main__":
    main()
