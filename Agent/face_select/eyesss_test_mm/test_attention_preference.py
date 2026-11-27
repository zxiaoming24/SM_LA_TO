"""
test_attention_preference.py - 注意力偏好算法测试

用模拟眼动数据验证核心算法的正确性。
覆盖 7 个场景:
  A: 视频 -> 高度专注（应该偏好 up）
  B: 文档 -> 分心严重（应该偏好 down）
  C: 练习 -> 中等投入（应该中等）
  D: 多次视频 -> 验证指数滑动平均收敛
  E: 混合行为 -> 偏好分化
  F: 极短会话 -> 无效数据过滤
  G: 持久化 -> 重启后数据不丢失

运行: python test_attention_preference.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eyesss_test_mm.attention_tracker import AttentionTracker
from eyesss_test_mm.attention_profile import AttentionProfile, get_profile


def simulate_gaze_focused(num_frames: int, fps: float = 30, base_time: float = 0) -> list:
    """高度专注：gaze_offset 小且稳定，头部稳定，不分心"""
    data = []
    for i in range(num_frames):
        t = base_time + i / fps
        data.append({
            "gaze_x": random.uniform(-0.05, 0.05),
            "gaze_y": random.uniform(-0.05, 0.05),
            "head_pitch": random.uniform(-2, 2),
            "head_yaw": random.uniform(-2, 2),
            "is_distracted": False,
            "timestamp": t,
        })
    return data


def simulate_gaze_distracted(num_frames: int, fps: float = 30, base_time: float = 0) -> list:
    """分心：gaze_offset 大且不稳定，头部频繁转动，分心呈爆发式出现"""
    data = []
    for i in range(num_frames):
        t = base_time + i / fps
        # 每 3 秒循环：第 1 秒持续分心，后 2 秒正常（但偏移仍大）
        cycle_pos = (i % int(fps * 3)) / fps
        is_distracted = cycle_pos < 1.0
        data.append({
            "gaze_x": random.uniform(-0.3, 0.3),
            "gaze_y": random.uniform(-0.2, 0.2),
            "head_pitch": random.uniform(-8, 8),
            "head_yaw": random.uniform(-10, 10),
            "is_distracted": is_distracted,
            "timestamp": t,
        })
    return data


def simulate_gaze_moderate(num_frames: int, fps: float = 30, base_time: float = 0) -> list:
    """中等投入：gaze_offset 中等，偶尔转头，偶尔分心（每6秒中有0.5秒）"""
    data = []
    for i in range(num_frames):
        t = base_time + i / fps
        cycle_pos = (i % int(fps * 6)) / fps
        is_distracted = 0.5 <= cycle_pos < 1.0  # 每6秒中有0.5秒分心
        data.append({
            "gaze_x": random.uniform(-0.12, 0.12),
            "gaze_y": random.uniform(-0.08, 0.08),
            "head_pitch": random.uniform(-4, 4),
            "head_yaw": random.uniform(-5, 5),
            "is_distracted": is_distracted,
            "timestamp": t,
        })
    return data


def run_session(tracker: AttentionTracker, user_id: str,
                resource_type: str, gaze_data: list,
                knowledge_point: str = "") -> dict:
    """模拟一次完整的资源页面访问->返回分析结果"""
    tracker.on_enter(user_id, resource_type,
                     resource_id=f"{resource_type}_test",
                     knowledge_point=knowledge_point)
    for frame in gaze_data:
        tracker.add_gaze(user_id,
                         frame["gaze_x"], frame["gaze_y"],
                         frame["head_pitch"], frame["head_yaw"],
                         frame["is_distracted"],
                         timestamp=frame["timestamp"])
    return tracker.on_leave(user_id)


def print_sep(title: str):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def test_a_video_focused():
    """场景A：视频高度专注 -> 沉浸分应 > 0.6"""
    print_sep("场景A：视频 - 高度专注 (预期: >0.6)")

    tracker = AttentionTracker()
    profile = get_profile("test_a")
    profile.reset()

    gaze_data = simulate_gaze_focused(300)  # 10秒 @ 30fps
    result = run_session(tracker, "test_a", "video", gaze_data, "循环结构")

    print(f"  沉浸分: {result['immersion_score']:.3f}")
    if result.get("details"):
        for k, v in result["details"].items():
            print(f"    {k}: {v}")

    assert result["immersion_score"] > 0.6, f"应 >0.6，实际 {result['immersion_score']}"
    assert result["valid"] is True
    print("  [OK] 通过")


def test_b_doc_distracted():
    """场景B：文档分心 -> 沉浸分应 < 0.5"""
    print_sep("场景B：文档 - 分心严重 (预期: <0.5)")

    tracker = AttentionTracker()
    profile = get_profile("test_b")
    profile.reset()

    gaze_data = simulate_gaze_distracted(300)
    result = run_session(tracker, "test_b", "doc", gaze_data, "函数定义")

    print(f"  沉浸分: {result['immersion_score']:.3f}")
    if result.get("details"):
        for k, v in result["details"].items():
            print(f"    {k}: {v}")

    assert result["immersion_score"] < 0.5, f"应 <0.5，实际 {result['immersion_score']}"
    print("  [OK] 通过")


def test_c_practice_moderate():
    """场景C：练习中等投入 -> 沉浸分在 0.3~0.8"""
    print_sep("场景C：练习 - 中等投入 (预期: 0.3~0.8)")

    tracker = AttentionTracker()
    gaze_data = simulate_gaze_moderate(300)
    result = run_session(tracker, "test_c", "practice", gaze_data, "数组操作")

    print(f"  沉浸分: {result['immersion_score']:.3f}")
    if result.get("details"):
        for k, v in result["details"].items():
            print(f"    {k}: {v}")

    assert 0.3 < result["immersion_score"] < 0.8, f"应在 0.3~0.8，实际 {result['immersion_score']}"
    print("  [OK] 通过")


def test_d_ema_convergence():
    """场景D：8次视频高度专注 -> 偏好从 0.5 收敛到 >0.7"""
    print_sep("场景D：8次视频高度专注 -> 偏好收敛")

    tracker = AttentionTracker()
    profile = get_profile("test_d")
    profile.reset()

    for i in range(8):
        g = simulate_gaze_focused(300)
        result = run_session(tracker, "test_d", "video", g, f"知识点{i+1}")
        effective = profile.get_effective_preferences()
        print(f"  第{i+1}次: 沉浸={result['immersion_score']:.3f} "
              f"-> video偏好={effective['video']:.3f} "
              f"(置信度={profile.get_confidence('video'):.3f})")

    final = profile.get_summary()
    assert final["preferences"]["video"] > 0.7, f"video偏好应 >0.7，实际 {final['preferences']['video']}"
    assert final["confidence"]["video"] > 0.7, f"视频置信度应 >0.7，实际 {final['confidence']['video']}"
    print("  [OK] 通过")


def test_e_mixed_preferences():
    """场景E：5次视频专注 + 3次文档分心 + 2次练习中等 -> video > doc"""
    print_sep("场景E：混合行为 -> video > doc")

    tracker = AttentionTracker()
    profile = get_profile("test_e")
    profile.reset()

    for i in range(5):
        run_session(tracker, "test_e", "video",
                    simulate_gaze_focused(300), f"视频{i+1}")
    for i in range(3):
        run_session(tracker, "test_e", "doc",
                    simulate_gaze_distracted(300), f"文档{i+1}")
    for i in range(2):
        run_session(tracker, "test_e", "practice",
                    simulate_gaze_moderate(300), f"练习{i+1}")

    summary = profile.get_summary()
    prefs = summary["preferences"]

    print(f"  原始偏好: video={prefs['video']:.3f}, doc={prefs['doc']:.3f}, practice={prefs['practice']:.3f}")
    print(f"  生效偏好: {summary['effective']}")
    print(f"  最喜欢类型: {summary['top_type']}")

    assert prefs["video"] > prefs["doc"], f"video({prefs['video']:.3f}) 应 > doc({prefs['doc']:.3f})"
    print("  [OK] 通过")


def test_f_short_session():
    """场景F：极短会话(<1秒) -> 无效"""
    print_sep("场景F：极短会话 -> 无效数据过滤")

    tracker = AttentionTracker()
    gaze_data = simulate_gaze_focused(10)  # 不到1秒
    result = run_session(tracker, "test_f", "video", gaze_data)

    print(f"  沉浸分: {result.get('immersion_score')}")
    print(f"  有效: {result.get('valid')}")
    print(f"  原因: {result.get('reason')}")

    assert result["valid"] is False
    print("  [OK] 通过")


def test_g_persistence():
    """场景G：验证持久化"""
    print_sep("场景G：持久化验证")

    p1 = get_profile("test_g")
    p1.reset()
    p1.update_preference("video", 0.85)
    p1.update_preference("doc", 0.25)

    # 重新加载（模拟重启）
    p2 = AttentionProfile("test_g")
    print(f"  写入: video={p1.preferences['video']:.3f}, doc={p1.preferences['doc']:.3f}")
    print(f"  读取: video={p2.preferences['video']:.3f}, doc={p2.preferences['doc']:.3f}")

    assert abs(p1.preferences["video"] - p2.preferences["video"]) < 0.001
    assert abs(p1.preferences["doc"] - p2.preferences["doc"]) < 0.001
    print("  [OK] 通过")


def print_summary():
    print()
    print("=" * 65)
    print("  所有用户最终画像")
    print("=" * 65)
    for uid in ["test_a", "test_b", "test_c", "test_d", "test_e"]:
        s = get_profile(uid).get_summary()
        eff = " | ".join([f"{k}={v:.2f}" for k, v in s["effective"].items()])
        print(f"  {uid}: [{eff}]  top={s['top_type']}  "
              f"total={s['total_sessions']}")


if __name__ == "__main__":
    random.seed(42)

    print()
    print("=" * 65)
    print("  注意力偏好算法测试 (eyesss_test_mm)")
    print("  用模拟眼动数据验证核心逻辑")
    print("=" * 65)

    test_a_video_focused()
    test_b_doc_distracted()
    test_c_practice_moderate()
    test_d_ema_convergence()
    test_e_mixed_preferences()
    test_f_short_session()
    test_g_persistence()

    print_summary()

    print()
    print("=" * 65)
    print("  全部测试通过 [OK]")
    print("=" * 65)
    print()
