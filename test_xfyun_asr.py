"""
讯飞 ASR 测试脚本

用法：
  # 从已有音频文件识别
  python test_xfyun_asr.py test.wav

  # 从麦克风录音10秒后识别
  python test_xfyun_asr.py --mic 10
"""

import sys
import os
import time

# 确保能找到项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Agent.TTS.speech_to_text import speech_to_text


def test_with_file(audio_path: str):
    """测试已有音频文件"""
    if not os.path.exists(audio_path):
        print(f"❌ 文件不存在: {audio_path}")
        return

    file_size = os.path.getsize(audio_path)
    print(f"📁 音频文件: {audio_path}")
    print(f"📊 文件大小: {file_size / 1024:.1f} KB")
    print()

    # 测试讯飞（自动降级）
    print("=" * 60)
    print("🎤 测试: method='auto'（讯飞优先 → Whisper 降级）")
    print("=" * 60)
    start = time.time()
    try:
        text = speech_to_text(
            audio_file=audio_path,
            method='auto',
            whisper_language='zh',
        )
        elapsed = time.time() - start
        print()
        if text:
            print(f"✅ 识别成功 ({elapsed:.1f}s)")
            print(f"📝 结果: {text}")
        else:
            print(f"⚠️  识别结果为空 ({elapsed:.1f}s)")
    except Exception as e:
        print(f"❌ 识别失败: {e}")


def test_with_mic(duration: int = 10):
    """从麦克风录音后识别"""
    print(f"🎤 将从麦克风录音 {duration} 秒...")
    print("  按 Ctrl+C 可提前结束")
    print()

    # 先测试 auto 模式
    print("=" * 60)
    print(f"🎤 录音 {duration}s → method='auto'")
    print("=" * 60)
    input("按 Enter 开始录音...")
    start = time.time()
    try:
        text = speech_to_text(
            duration=duration,
            method='auto',
            whisper_language='zh',
        )
        elapsed = time.time() - start
        print()
        if text:
            print(f"✅ 识别成功 ({elapsed:.1f}s)")
            print(f"📝 结果: {text}")
        else:
            print(f"⚠️  识别结果为空 ({elapsed:.1f}s)")
    except Exception as e:
        print(f"❌ 识别失败: {e}")
    print()


if __name__ == "__main__":
    # 检查是否有 .env 中的讯飞配置
    from dotenv import load_dotenv
    load_dotenv()

    xfyun_ok = all([
        os.getenv("XFYUN_APP_ID"),
        os.getenv("XFYUN_API_KEY"),
        os.getenv("XFYUN_API_SECRET"),
    ])
    print(f"{'✅' if xfyun_ok else '❌'} 讯飞 API 密钥: {'已配置' if xfyun_ok else '未配置'}")
    if not xfyun_ok:
        print("  ⚠️  未配置时将自动降级到 Whisper")
    print()

    if len(sys.argv) >= 2 and sys.argv[1] != '--mic':
        test_with_file(sys.argv[1])
    elif '--mic' in sys.argv:
        idx = sys.argv.index('--mic')
        duration = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 10
        test_with_mic(duration)
    else:
        print("用法:")
        print("  python test_xfyun_asr.py <音频文件.wav>    # 识别已有文件")
        print("  python test_xfyun_asr.py --mic [秒数]     # 麦克风录音识别")
        print()
        print("示例:")
        print("  python test_xfyun_asr.py test.wav")
        print("  python test_xfyun_asr.py --mic 15")
