# TTS/ASR 语音处理模块

本模块提供 **TTS（文本转语音）** 和 **ASR（语音转文字）** 功能，支持用户通过语音与系统交互。

## 📦 功能特性

- ✅ **TTS**: 使用 Edge TTS 将文本转换为自然流畅的语音
- ✅ **ASR**: 支持多种语音识别服务（Whisper、Azure、百度）
- ✅ **离线**: Whisper 支持离线运行，无需网络
- ✅ **集成**: 与 `user_info_extractor.py` 无缝集成
- ✅ **灵活**: 支持麦克风实时录音和音频文件识别

## 🚀 快速开始

### 1. 安装依赖

```bash
# 基础依赖（TTS）
pip install edge-tts>=6.1.0

# ASR 依赖（根据需要选择）
pip install openai-whisper pyaudio     # Whisper（推荐，离线）
pip install azure-cognitiveservices-speech  # Azure
pip install baidu-aip                      # 百度

# Windows 用户安装 pyaudio
pip install pyaudio-wheel
```

### 2. 测试 TTS

```bash
cd E:\PY\all_tame_channel\Agent\TTS
python test_tts.py
```

### 3. 配置 ASR（可选）

**Whisper（推荐，离线使用）：**
```bash
# 安装依赖
pip install openai-whisper pyaudio

# Windows 用户
pip install pyaudio-wheel

# 使用（无需配置，开箱即用）
python -c "from Agent.TTS.speech_to_text import speech_to_text; print(speech_to_text(duration=5))"
```

**Azure Speech Service：**
```bash
# Windows PowerShell
$env:AZURE_SPEECH_KEY="your_key"
$env:AZURE_SPEECH_REGION="eastasia"

# Linux/Mac
export AZURE_SPEECH_KEY=your_key
export AZURE_SPEECH_REGION=eastasia
```

**百度语音识别：**
```bash
export BAIDU_APP_ID=your_app_id
export BAIDU_API_KEY=your_api_key
export BAIDU_SECRET_KEY=your_secret_key
```

## 🎯 功能说明

### 1. TTS - 文本转语音

```python
from Agent.TTS.speech_to_text import text_to_speech

# 将文本转换为语音
audio_file = text_to_speech("你好，这是一个测试")
print(f"音频文件: {audio_file}")
```

### 2. ASR - 语音转文字

#### 方式1: 从麦克风录音并识别

```python
from Agent.TTS.speech_to_text import speech_to_text

# 从麦克风录音10秒并识别（默认简体中文）
text = speech_to_text(duration=10, method='whisper')
print(f"识别结果: {text}")

# 强制指定为英文
text = speech_to_text(duration=10, method='whisper', whisper_language='en')

# 调整录音灵敏度（避免背景噪音）
# silence_threshold: 0-32767，值越大越不灵敏，默认100（较灵敏）
text = speech_to_text(duration=10, silence_threshold=1000)  # 更不灵敏（安静环境）
text = speech_to_text(duration=10, silence_threshold=100)   # 默认（平衡）
text = speech_to_text(duration=10, silence_threshold=50)    # 更灵敏（嘈杂环境）
```

#### 方式2: 从音频文件识别

```python
# 从音频文件识别
text = speech_to_text(audio_file='test.wav', method='azure')
print(f"识别结果: {text}")
```

### 3. 与 user_info_extractor 集成

```python
from Agent.TTS.speech_to_text import speech_to_text
from Agent.children_agent.user_info_extractor import extract_user_info

# 步骤1: 语音识别
text = speech_to_text(duration=10, method='azure')

# 步骤2: 信息抽取
info = extract_user_info(text)

print(f"姓名: {info.get('name')}")
print(f"专业: {info.get('major')}")
print(f"年级: {info.get('grade')}")
```

## 📁 文件说明

- `speech_to_text.py` - 核心模块
  - `SpeechProcessor` - 语音处理器（集成 TTS 和 ASR）
  - `text_to_speech()` - TTS 便捷函数
  - `speech_to_text()` - ASR 便捷函数
  
- `test_tts.py` - 测试脚本
  - 测试 TTS 功能
  - 显示 ASR 配置说明
  - 可选的完整流程测试
  
- `README.md` - 本文档

## 💡 ASR 服务对比

| 服务 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Whisper** | 离线运行，准确率高，支持多语言 | 首次加载模型较慢 | **推荐日常使用** |
| **Azure** | 准确率高，支持实时识别 | 需要付费，需网络 | 生产环境 |
| **百度** | 中文效果好，免费额度高 | 需要音频文件 | 国内应用 |

## ⚠️ 注意事项

1. **Whisper 首次使用**：会自动下载模型文件（约 150MB），请确保网络畅通
2. **离线运行**：Whisper 下载模型后可完全离线使用
3. **麦克风权限**：使用麦克风录音时需要授予权限
4. **模型选择**：Whisper 提供多种模型，越大越准确但速度越慢

## 🔧 故障排除

### 问题1：Whisper 模型下载失败

**解决方案：**
- 检查网络连接
- 手动下载模型：https://openaipublic.blob.core.windows.net/openai-whisper/
- 将模型文件放到 `~/.cache/whisper/` 目录

### 问题2：pyaudio 安装失败

**解决方案：**
- Windows: `pip install pyaudio-wheel`
- Linux: `sudo apt-get install portaudio19-dev`
- Mac: `brew install portaudio`

### 问题3：无法识别语音

**解决方案：**
- 检查麦克风是否正常工作
- 确认已正确配置 ASR 服务的密钥（如果使用 Azure/百度）
- 检查网络连接（Whisper 离线使用不需要网络）

### 问题4：Azure 认证失败

**解决方案：**
- 确认环境变量 `AZURE_SPEECH_KEY` 和 `AZURE_SPEECH_REGION` 已正确设置
- 检查订阅密钥是否有效
- 确认区域代码正确（如：eastasia, westus2）

### 问题5：Edge TTS 生成音频失败

**解决方案：**
- 检查网络连接
- 确认语言代码正确（如：zh-CN, en-US）
- 更新 edge-tts 包：`pip install --upgrade edge-tts`

## 📚 相关文档

- [Whisper GitHub](https://github.com/openai/whisper)
- [Edge TTS GitHub](https://github.com/rany2/edge-tts)
- [Azure Speech Service](https://docs.microsoft.com/azure/cognitive-services/speech-service/)
- [百度语音识别](https://ai.baidu.com/tech/speech/asr)
