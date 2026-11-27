"""
语音处理模块测试脚本
测试 TTS（文本转语音）和 ASR（语音转文字）功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.TTS.speech_to_text import text_to_speech, speech_to_text
from Agent.children_agent.user_info_extractor import extract_user_info


def test_tts():
    """测试 TTS - 文本转语音功能"""
    print("="*70)
    print("🔊 测试1: TTS - 文本转语音")
    print("="*70)
    
    test_texts = [
        "你好，这是一个测试",
        "欢迎使用智能教育系统",
        "我叫张三，是计算机专业的学生"
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n测试 {i}: {text}")
        try:
            audio_file = text_to_speech(text)
            print(f"✅ 成功生成音频: {audio_file}")
        except Exception as e:
            print(f"❌ 失败: {e}")


def print_asr_config():
    """显示 ASR 配置说明"""
    print("\n" + "="*70)
    print("🎙️  测试2: ASR - 语音转文字配置说明")
    print("="*70)
    
    print("\n支持的 ASR 服务：")
    print("\n1. Whisper（推荐，离线使用）")
    print("   - 优点：离线运行，准确率高，支持多语言")
    print("   - 安装: pip install openai-whisper pyaudio")
    print("   - Windows 用户: pip install pyaudio-wheel")
    print("   - 使用: speech_to_text(method='whisper')")
    print("   - 模型: tiny, base, small, medium, large（越大越准但越慢）")
    
    print("\n2. Azure Speech Service")
    print("   - 优点：准确率高，支持实时识别")
    print("   - 设置环境变量:")
    print("     Windows: $env:AZURE_SPEECH_KEY='your_key'")
    print("              $env:AZURE_SPEECH_REGION='eastasia'")
    print("     Linux:   export AZURE_SPEECH_KEY=your_key")
    print("              export AZURE_SPEECH_REGION=eastasia")
    print("   - 安装: pip install azure-cognitiveservices-speech")
    print("   - 使用: speech_to_text(method='azure')")
    
    print("\n3. 百度语音识别")
    print("   - 优点：中文识别效果好，免费额度高")
    print("   - 设置环境变量:")
    print("     export BAIDU_APP_ID=your_app_id")
    print("     export BAIDU_API_KEY=your_api_key")
    print("     export BAIDU_SECRET_KEY=your_secret_key")
    print("   - 安装: pip install baidu-aip")
    print("   - 使用: speech_to_text(audio_file='test.wav', method='baidu')")


def test_asr_with_user_info():
    """测试 ASR + 用户信息抽取的完整流程"""
    print("\n" + "="*70)
    print("🎤 测试3: ASR + 用户信息抽取完整流程")
    print("="*70)
    
    print("\n💡 这个测试演示完整的语音输入流程：")
    print("   1. 用户说话")
    print("   2. 语音识别为文字")
    print("   3. 提取结构化用户信息")
    print("\n⚠️  需要配置 ASR 服务才能运行此测试")
    print("\n请选择 ASR 服务：")
    print("1. Whisper（推荐，离线）")
    print("2. Azure Speech Service")
    print("3. 百度语音识别")
    print("4. 跳过此测试")
    
    choice = input("\n请选择 (1-4): ").strip()
    
    if choice == '4':
        print("⏭️  跳过 ASR 测试")
        return
    
    method_map = {'1': 'whisper', '2': 'azure', '3': 'baidu'}
    method = method_map.get(choice)
    
    if not method:
        print("❌ 无效选择")
        return
    
    print(f"\n🎤 请对着麦克风说出你的信息（10秒）...")
    print("例如：'我叫李四，是软件工程专业大三的学生'")
    
    input("按 Enter 键开始录音...")
    
    try:
        # 步骤1: 语音识别
        recognized_text = speech_to_text(duration=10, method=method)
        
        if not recognized_text:
            print("❌ 未能识别到语音")
            return
        
        print(f"\n✅ 识别结果: {recognized_text}")
        
        # 步骤2: 信息抽取
        print("\n🔍 正在提取用户信息...")
        extracted_info = extract_user_info(recognized_text)
        
        print("\n📋 提取的结构化信息:")
        print(f"   姓名: {extracted_info.get('name', '未知')}")
        print(f"   专业: {extracted_info.get('major', '未知')}")
        print(f"   年级: {extracted_info.get('grade', '未知')}")
        print(f"   学习目标: {extracted_info.get('learning_goal', '未知')}")
        
        history = extracted_info.get('learning_history', [])
        if history:
            print(f"\n   📚 学习历史:")
            for h in history:
                print(f"     - {h.get('课程', '未知')}: {h.get('成绩', '未知')}分")
        
        questions = extracted_info.get('follow_up_questions', [])
        if questions:
            print(f"\n❓ 需要补充的信息:")
            for i, q in enumerate(questions, 1):
                print(f"   {i}. {q}")
        
        print("\n✅ 完整流程测试成功！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🌟 语音处理模块测试")
    print("="*70)
    print("="*70)

    # 测试1: TTS
    test_tts()
    
    # 测试2: ASR 配置说明
    print_asr_config()
    
    # 测试3: 完整流程（可选）
    print("\n" + "="*70)
    run_full_test = input("是否运行完整的 ASR + 信息抽取测试？(y/n): ").strip().lower()
    if run_full_test == 'y':
        test_asr_with_user_info()
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70)
