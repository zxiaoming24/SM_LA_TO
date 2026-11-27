"""
语音处理模块 - 提供 TTS（文本转语音）和 ASR（语音转文字）功能
支持 Edge TTS 和 VoxCPM 语音合成（含声音设计、音色克隆）
"""

import os
import sys
import asyncio
from typing import Optional, Dict, Any
import tempfile


class SpeechProcessor:
    """
    语音处理器 - 集成 TTS 和 ASR 功能
    """
    
    def __init__(self, language: str = 'zh-CN'):
        """
        初始化语音处理器
        
        Args:
            language: 语言代码，默认中文 (zh-CN)
        """
        self.language = language
        self.voice_map = {
            'zh-CN': 'zh-CN-YunxiNeural',  # 中文男声
            'en-US': 'en-US-GuyNeural',     # 英文男声
            'ja-JP': 'ja-JP-KeitaNeural',   # 日文男声
        }
        
    async def text_to_speech(
        self,
        text: str,
        output_file: str = None,
        method: str = 'edge_tts',
        voice_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        TTS: 文本转语音

        Args:
            text: 要转换的文本
            output_file: 输出音频文件路径，如果为None则生成临时文件
            method: 生成方式 ('edge_tts' 或 'voxcpm')
            voice_profile: VoxCPM 音色配置（method='voxcpm' 时使用）

                voice_profile 支持以下模式:
                - design (声音设计):
                    {"mode": "design", "control": "温柔女声", ...}
                - clone (可控克隆):
                    {"mode": "clone", "reference_audio": "/path/to/audio.wav", "control": "...", ...}
                - ultimate_clone (极致克隆):
                    {"mode": "ultimate_clone", "reference_audio": "/path/to/audio.wav",
                     "prompt_text": "音频转录文本", ...}

                通用参数:
                    server_url (str): VoxCPM 服务地址，默认 http://localhost:8800
                    cfg_value (float): CFG 引导强度，默认 2.0
                    inference_timesteps (int): 扩散步数，默认 10
                    denoise (bool): 是否对参考音频降噪，默认 False
                    normalize (bool): 是否文本规范化，默认 False

        Returns:
            str: 生成的音频文件路径
        """
        if method == 'voxcpm':
            return await self._voxcpm_tts(text, output_file, voice_profile or {})

        # 默认走 edge-tts
        try:
            import edge_tts

            if not text or not text.strip():
                raise ValueError("文本内容为空")

            text = ' '.join(text.split())
            if len(text) < 3:
                raise ValueError("文本内容太短")

            voice = self.voice_map.get(self.language, 'zh-CN-YunxiNeural')

            if output_file is None:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                output_file = temp_file.name
                temp_file.close()

            print(f"🎤 开始TTS生成...")
            print(f"   文本长度: {len(text)} 字符")
            print(f"   语音: {voice}")
            print(f"   输出文件: {output_file}")

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate="+0%",
                volume="+0%",
                pitch="+0Hz"
            )

            await communicate.save(output_file)

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                file_size = os.path.getsize(output_file)
                print(f"✅ 音频已保存到: {output_file} ({file_size} bytes)")
                return output_file
            else:
                raise Exception("音频文件生成失败或文件为空")

        except ImportError:
            raise Exception("请安装 edge-tts: pip install edge-tts")
        except ValueError as e:
            print(f"❌ 文本验证失败: {e}")
            raise
        except Exception as e:
            print(f"❌ 文本转语音失败: {e}")
            print(f"   错误类型: {type(e).__name__}")
            if "No audio was received" in str(e):
                print("   💡 可能是网络连接问题，请检查:")
                print("      1. 网络连接是否正常")
                print("      2. 是否可以访问微软Edge服务")
                print("      3. 是否有防火墙或代理阻止连接")
            raise

    # ------------------------------------------------------------------
    #  VoxCPM 客户端
    # ------------------------------------------------------------------

    async def _voxcpm_tts(
        self,
        text: str,
        output_file: str,
        profile: Dict[str, Any],
    ) -> str:
        """通过 VoxCPM 服务生成语音（声音设计 / 音色克隆）。"""
        server_url = profile.get('server_url', 'http://localhost:8800').rstrip('/')
        mode = profile.get('mode', 'design')
        cfg_value = profile.get('cfg_value', 2.0)
        inference_timesteps = profile.get('inference_timesteps', 10)
        do_normalize = profile.get('normalize', False)
        do_denoise = profile.get('denoise', False)

        import requests

        if output_file is None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            output_file = temp_file.name
            temp_file.close()

        print(f"🎤 开始 VoxCPM 生成...")
        print(f"   模式: {mode}")
        print(f"   服务: {server_url}")
        print(f"   文本: {text[:80]}{'...' if len(text) > 80 else ''}")

        import asyncio
        try:
            if mode == 'design':
                resp = await asyncio.to_thread(
                    lambda: requests.post(
                        f"{server_url}/api/voice-design",
                        data={
                            'text': text,
                            'control': profile.get('control', ''),
                            'cfg_value': cfg_value,
                            'inference_timesteps': inference_timesteps,
                            'normalize': do_normalize,
                        },
                        timeout=120,
                    )
                )
                resp.raise_for_status()

            elif mode == 'clone':
                ref_audio = profile.get('reference_audio')
                if not ref_audio or not os.path.isfile(ref_audio):
                    raise ValueError(f"可控克隆需要有效的 reference_audio 文件: {ref_audio}")

                with open(ref_audio, 'rb') as f:
                    ref_data = f.read()
                resp = await asyncio.to_thread(
                    lambda: requests.post(
                        f"{server_url}/api/clone",
                        data={
                            'text': text,
                            'control': profile.get('control', ''),
                            'cfg_value': cfg_value,
                            'inference_timesteps': inference_timesteps,
                            'normalize': do_normalize,
                            'denoise': do_denoise,
                        },
                        files={'reference_audio': (os.path.basename(ref_audio), ref_data, 'audio/wav')},
                        timeout=120,
                    )
                )
                resp.raise_for_status()

            elif mode == 'ultimate_clone':
                ref_audio = profile.get('reference_audio')
                if not ref_audio or not os.path.isfile(ref_audio):
                    raise ValueError(f"极致克隆需要有效的 reference_audio 文件: {ref_audio}")

                with open(ref_audio, 'rb') as f:
                    ref_data = f.read()
                resp = await asyncio.to_thread(
                    lambda: requests.post(
                        f"{server_url}/api/ultimate-clone",
                        data={
                            'text': text,
                            'prompt_text': profile.get('prompt_text', ''),
                            'cfg_value': cfg_value,
                            'inference_timesteps': inference_timesteps,
                            'normalize': do_normalize,
                            'denoise': do_denoise,
                        },
                        files={'reference_audio': (os.path.basename(ref_audio), ref_data, 'audio/wav')},
                        timeout=120,
                    )
                )
                resp.raise_for_status()

            else:
                raise ValueError(f"不支持的 VoxCPM 模式: {mode}，可选: design / clone / ultimate_clone")

            with open(output_file, 'wb') as f:
                f.write(resp.content)

            if os.path.getsize(output_file) > 0:
                file_size = os.path.getsize(output_file)
                print(f"✅ VoxCPM 音频已保存: {output_file} ({file_size} bytes)")
                return output_file
            else:
                raise Exception("VoxCPM 返回的音频文件为空")

        except requests.ConnectionError:
            print(f"❌ 无法连接到 VoxCPM 服务 ({server_url})，请确认服务已启动")
            print(f"   💡 启动方式: python server.py --port 8800")
            raise Exception(f"VoxCPM 服务连接失败: {server_url}")
        except requests.Timeout:
            print(f"❌ VoxCPM 服务响应超时")
            raise Exception("VoxCPM 服务响应超时")
        except requests.HTTPError as e:
            print(f"❌ VoxCPM 服务返回错误: {e}")
            raise
        except Exception as e:
            print(f"❌ VoxCPM 生成失败: {e}")
            raise
    
    def speech_to_text(self, audio_file: str = None, duration: int = 10, 
                      method: str = 'whisper', language: str = None,
                      silence_threshold: int = 100) -> str:
        """
        ASR: 语音转文字（支持多种识别服务）
        
        Args:
            audio_file: 音频文件路径（如果为None则从麦克风录音）
            duration: 录音时长（秒），仅在使用麦克风时有效
            method: 识别方法 ('whisper', 'azure', 'baidu', 'xfyun')
            language: 语言代码（如 'zh', 'en'），Whisper 默认简体中文
            silence_threshold: 静音阈值（0-32767），值越大越不灵敏，默认100
            
        Returns:
            str: 识别出的文字
        """
        if method == 'whisper':
            return self._whisper_asr(audio_file, duration, language, silence_threshold)
        elif method == 'xfyun':
            return self._xfyun_asr(audio_file, duration, silence_threshold)
        elif method == 'auto':
            return self.speech_to_text_with_fallback(audio_file, duration, language, silence_threshold)
        else:
            raise ValueError(f"不支持的识别方法: {method}")

    def speech_to_text_with_fallback(self, audio_file: str = None, duration: int = 10,
                                     language: str = None, silence_threshold: int = 50) -> str:
        """
        自动选择识别引擎：讯飞优先 → Whisper 降级

        判断逻辑：
          1. 检查是否配置了讯飞 API 密钥
          2. 有密钥 → 尝试讯飞
          3. 讯飞失败或无密钥 → 回退 Whisper

        Args:
            同 speech_to_text

        Returns:
            str: 识别出的文字
        """
        import os
        xfyun_configured = all([
            os.getenv("XFYUN_APP_ID"),
            os.getenv("XFYUN_API_KEY"),
            os.getenv("XFYUN_API_SECRET"),
        ])

        if xfyun_configured:
            try:
                print("🎤 尝试使用讯飞 ASR...")
                return self._xfyun_asr(audio_file, duration, silence_threshold)
            except Exception as e:
                print(f"  ⚠️ 讯飞 ASR 失败，降级到 Whisper: {e}")
        else:
            print("  ℹ️ 未配置讯飞 API，使用 Whisper")

        return self._whisper_asr(audio_file, duration, language, silence_threshold)
    
    def _whisper_asr(self, audio_file: str = None, duration: int = 10, 
                    language: str = None, silence_threshold: int = 50) -> str:
        """
        使用 OpenAI Whisper 进行语音识别（离线，推荐）

        【30秒限制处理】
        Whisper 原生训练数据以 30 秒片段为单位，长音频会有失真。
        本方法自动检测音频长度，超过 30 秒时分片处理再合并结果。

        Args:
            audio_file: 音频文件路径（如果为None则从麦克风录音）
            duration: 录音时长（秒）
            language: 语言代码（如 'zh', 'en'），设为 None 则默认为简体中文
            silence_threshold: 静音阈值（0-32767），值越大越不灵敏，默认100

        Returns:
            str: 识别出的文字
        """
        try:
            import whisper
            import tempfile
            import wave
            import pyaudio
            import os
            import math

            # 如果没有提供音频文件，则从麦克风录音
            if audio_file is None:
                print(f"🎤 请开始说话（{duration}秒）...")
                audio_file = self._record_audio(duration, silence_threshold)

            # 默认使用中文，如果未指定语言
            if language is None:
                language = 'zh'
                print("💡 默认使用中文识别，如需英文请设置 language='en'")

            # 加载 Whisper 模型
            print("⏳ 正在加载 Whisper 模型...")
            model = whisper.load_model("base")

            # ★★★ 检测音频时长，超过30秒时进行分片处理 ★★★
            audio_duration = self._get_audio_duration(audio_file)
            print(f"📊 音频时长: {audio_duration:.1f} 秒")

            if audio_duration > 30:
                print(f"🔪 音频超过30秒，进行分片识别（每段30秒）...")
                texts = []
                num_chunks = math.ceil(audio_duration / 30)
                for i in range(num_chunks):
                    chunk_file = self._split_audio(audio_file, i * 30, min((i + 1) * 30, audio_duration))
                    if chunk_file:
                        print(f"   📄 分片 {i + 1}/{num_chunks}...")
                        chunk_result = model.transcribe(
                            chunk_file,
                            language=language,
                            verbose=False,
                            initial_prompt="以下是需要语音转文字的普通话内容。" if language == 'zh' else None,
                        )
                        chunk_text = chunk_result.get('text', '').strip()
                        if chunk_text:
                            texts.append(chunk_text)
                        # 清理临时分片文件
                        try:
                            os.remove(chunk_file)
                        except Exception:
                            pass
                full_text = ' '.join(texts)
                print(f"✅ 分片识别完成，共 {len(texts)} 段")
            else:
                # 短音频直接识别
                print("⏳ 正在识别语音（语言: {language}）...")
                result = model.transcribe(
                    audio_file,
                    language=language,
                    verbose=False
                )
                full_text = result.get('text', '').strip()

            print(f"✅ 识别结果: {full_text}")
            return full_text

        except ImportError as e:
            raise Exception(
                "请安装依赖:\n"
                "  pip install openai-whisper pyaudio\n"
                "注意: pyaudio 可能需要系统依赖，Windows 用户可使用:\n"
                "  pip install pyaudio-wheel"
            )
        except Exception as e:
            print(f"❌ Whisper 语音识别失败: {e}")
            raise

    @staticmethod
    def _get_audio_duration(audio_file: str) -> float:
        """获取音频文件时长（秒）"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_file)
            return len(audio) / 1000.0
        except ImportError:
            # 回退：用 wave 模块获取 wav 时长
            try:
                with wave.open(audio_file, 'r') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return frames / float(rate)
            except Exception:
                # 实在拿不到就假设较短，不走分片
                return 10

    @staticmethod
    def _split_audio(audio_file: str, start_sec: float, end_sec: float) -> Optional[str]:
        """
        截取音频的一段并保存到临时文件

        Args:
            audio_file: 原音频文件路径
            start_sec: 开始时间（秒）
            end_sec: 结束时间（秒）

        Returns:
            str: 临时分片文件路径，失败返回 None
        """
        try:
            from pydub import AudioSegment
            import tempfile

            audio = AudioSegment.from_file(audio_file)
            segment = audio[int(start_sec * 1000):int(end_sec * 1000)]

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            tmp_path = tmp.name
            tmp.close()
            segment.export(tmp_path, format='wav')
            return tmp_path
        except ImportError:
            # 没有 pydub 的话用 ffmpeg 命令
            import subprocess
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            tmp_path = tmp.name
            tmp.close()
            try:
                subprocess.run([
                    'ffmpeg', '-i', audio_file,
                    '-ss', str(start_sec), '-to', str(end_sec),
                    '-c', 'copy', '-y', tmp_path
                ], capture_output=True, check=True)
                return tmp_path
            except Exception:
                return None
    
    def _record_audio(self, duration: int = 10, silence_threshold: int = 50) -> str:
        """
        从麦克风录制音频
        
        Args:
            duration: 录音时长（秒）
            silence_threshold: 静音阈值（0-32767），值越大越不灵敏，默认500
            
        Returns:
            str: 录制的音频文件路径（wav格式）
        """
        import pyaudio
        import wave
        import struct
        
        # 音频参数
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1024
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        output_file = temp_file.name
        temp_file.close()
        
        # 初始化 PyAudio
        audio = pyaudio.PyAudio()
        
        # 开始录音
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        print("🔴 录音中...")
        print(f"   静音阈值: {silence_threshold} (值越大越不灵敏)")
        frames = []
        silent_chunks = 0
        max_silent_chunks = int(RATE / CHUNK * 0.5)  # 允许0.5秒的静音
        
        for i in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            
            # 计算音量（RMS）
            if silence_threshold > 0:
                # 将二进制数据转换为short类型
                shorts = struct.unpack('<' + 'h' * (len(data) // 2), data)
                # 计算 RMS (均方根)
                rms = int((sum(x * x for x in shorts) / len(shorts)) ** 0.5)
                
                # 如果音量低于阈值，认为是静音
                if rms < silence_threshold:
                    silent_chunks += 1
                    # 如果连续静音超过限制，跳过该段
                    if silent_chunks > max_silent_chunks:
                        continue
                else:
                    silent_chunks = 0
            
            frames.append(data)
        
        print("⏹️  录音结束")
        
        # 停止录音
        stream.stop_stream()
        stream.close()   #  这不就是关流吗
        audio.terminate()
        
        # 保存音频文件
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        
        print(f"✅ 音频已保存到: {output_file}")
        return output_file

    '''
    def _azure_asr(self, audio_file: str = None, duration: int = 10) -> str:
        """
        使用 Azure Speech Service 进行语音识别
        
        Args:
            audio_file: 音频文件路径（如果为None则从麦克风录音）
            duration: 录音时长（秒）
            
        Returns:
            str: 识别出的文字
        """
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            subscription_key = os.getenv('AZURE_SPEECH_KEY')
            region = os.getenv('AZURE_SPEECH_REGION')
            
            if not subscription_key or not region:
                raise Exception("请设置环境变量 AZURE_SPEECH_KEY 和 AZURE_SPEECH_REGION")
            
            speech_config = speechsdk.SpeechConfig(
                subscription=subscription_key, 
                region=region
            )
            speech_config.speech_recognition_language = self.language
            
            if audio_file:
                audio_config = speechsdk.AudioConfig(filename=audio_file)
            else:
                audio_config = speechsdk.AudioConfig(use_default_microphone=True)
                print(f"🎤 请开始说话（{duration}秒）...")
            
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            result = recognizer.recognize_once_async().get()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"✅ 识别结果: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                print("❌ 未能识别语音")
                return ""
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                print(f"❌ 识别取消: {cancellation.reason}")
                return ""
                
        except ImportError:
            raise Exception("请安装 azure-cognitiveservices-speech: pip install azure-cognitiveservices-speech")
        except Exception as e:
            print(f"❌ Azure 语音识别失败: {e}")
            raise
    
    def _baidu_asr(self, audio_file: str) -> str:
        """
        使用百度语音识别 API
        
        Args:
            audio_file: 音频文件路径（wav格式，16k采样率）
            
        Returns:
            str: 识别出的文字
        """
        try:
            from aip import AipSpeech
            
            APP_ID = os.getenv('BAIDU_APP_ID')
            API_KEY = os.getenv('BAIDU_API_KEY')
            SECRET_KEY = os.getenv('BAIDU_SECRET_KEY')
            
            if not all([APP_ID, API_KEY, SECRET_KEY]):
                raise Exception("请设置环境变量 BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY")
            
            client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)
            
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
            
            result = client.asr(audio_data, 'wav', 16000, {'dev_pid': 1537})
            
            if result.get('err_no') == 0:
                text = result['result'][0]
                print(f"✅ 识别结果: {text}")
                return text
            else:
                print(f"❌ 识别失败: {result.get('err_msg')}")
                return ""
                
        except ImportError:
            raise Exception("请安装 baidu-aip: pip install baidu-aip")
        except Exception as e:
            print(f"❌ 百度语音识别失败: {e}")
            raise
    '''

    def _xfyun_asr(self, audio_file: str = None, duration: int = 10,
                    silence_threshold: int = 50) -> str:
        """
        使用讯飞语音识别 API（WebSocket 实时流式识别）

        环境变量配置（在 .env 或系统环境变量中设置）:
            XFYUN_APP_ID:     讯飞应用 ID（必填）
            XFYUN_API_KEY:    讯飞 API Key（必填）
            XFYUN_API_SECRET: 讯飞 API Secret（必填）

        Args:
            audio_file: 音频文件路径（wav 格式，16kHz 采样率最佳）

        Returns:
            str: 识别出的文字

        Raises:
            ValueError: 缺少 API 配置
            Exception: 识别失败
        """
        import json
        import time
        import base64
        import hashlib
        import hmac
        import uuid
        from datetime import datetime
        from urllib.parse import urlparse, urlencode

        # 读取 API 配置
        app_id = os.getenv("XFYUN_APP_ID", "")
        api_key = os.getenv("XFYUN_API_KEY", "")
        api_secret = os.getenv("XFYUN_API_SECRET", "")

        if not app_id or not api_key or not api_secret:
            raise ValueError(
                "讯飞 ASR 需要配置以下环境变量:\n"
                "  XFYUN_APP_ID: 讯飞应用 ID\n"
                "  XFYUN_API_KEY: 讯飞 API Key\n"
                "  XFYUN_API_SECRET: 讯飞 API Secret\n"
                "可在 .env 文件中设置，或直接在环境变量中配置。"
            )

        # 讯飞 WebSocket 地址
        host = "iat-api.xfyun.cn"
        path = "/v2/iat"
        url = f"wss://{host}{path}"

        # ----- 生成鉴权 URL -----
        # 参考讯飞官方文档：https://www.xfyun.cn/doc/asr/voicedictation/API.html
        now = datetime.utcnow()
        date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256
        ).digest()
        signature_base64 = base64.b64encode(signature).decode("utf-8")

        authorization_origin = (
            f'api_key="{api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature_base64}"'
        )
        authorization_base64 = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        ws_url = f"{url}?{urlencode({'authorization': authorization_base64, 'date': date, 'host': host})}"

        # ----- 读取音频文件（None 时从麦克风录音）-----
        import wave
        import tempfile as _tf
        _actual_file = audio_file
        if _actual_file is None:
            # 从麦克风录音
            _recorded = self._record_audio(duration, silence_threshold)
            _actual_file = _recorded
            print(f"  🎤 录音完成: {_actual_file}")

        # 统一转成 16kHz 单声道 WAV（讯飞要求的格式）
        _converted = None
        try:
            from pydub import AudioSegment
            _audio = AudioSegment.from_file(_actual_file)
            _audio = _audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            _converted = _tf.NamedTemporaryFile(delete=False, suffix='.wav').name
            _audio.export(_converted, format='wav')
            print(f"  🔄 音频转码完成: {_converted}")
        except Exception:
            # 无 ffmpeg 或格式不支持时，用原文件（仅 wav 可读，否则会抛给降级）
            print(f"  ⚠️ 转码失败，直接使用原文件（需 wav 格式）")
            _converted = _actual_file

        with wave.open(_converted, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()

        # 清理临时转码文件
        if _converted and _converted != _actual_file and os.path.exists(_converted):
            try:
                os.remove(_converted)
            except Exception:
                pass

        # ----- WebSocket 连接并发送音频 -----
        try:
            import websocket
        except ImportError:
            raise Exception(
                "使用讯飞 ASR 需要安装 websocket-client:\n"
                "  pip install websocket-client"
            )

        result_text = ""
        _last_sentence = ""  # ★★★ 追踪上一句完整结果，处理 wpgs 动态修正 ★★★
        ws = None

        def on_message(ws_, message):
            nonlocal result_text, _last_sentence
            try:
                data = json.loads(message)
                code = data.get("code", 0)
                if code != 0:
                    print(f"  ⚠️ 讯飞返回错误: code={code}, message={data.get('message', '')}")
                    return

                result = data.get("data", {}).get("result", {})
                candidates = result.get("ws", [])
                pgs = result.get("pgs", "apl")  # wpgs 模式：rpl=替换上一句, apl=追加
                status = data.get("data", {}).get("status", 0)

                # 解析当前结果
                current_text = ""
                for ws_item in candidates:
                    for cw in ws_item.get("cw", []):
                        w = cw.get("w", "")
                        if w:
                            current_text += w

                if not current_text:
                    return

                # ★★★ 处理动态修正 ★★★
                if pgs == "rpl":
                    # 替换上一句：移除上次追加的内容，换上新结果
                    if _last_sentence and result_text.endswith(_last_sentence):
                        result_text = result_text[:-len(_last_sentence)]
                    _last_sentence = current_text
                    result_text += current_text
                else:  # "apl" 或首次
                    _last_sentence = current_text
                    result_text += current_text

                # 判断是否结束
                if status == 2:
                    ws_.close()
            except json.JSONDecodeError:
                pass

        def on_error(ws_, error):
            print(f"  ⚠️ 讯飞 WebSocket 错误: {error}")

        def on_close(ws_, close_status_code, close_msg):
            print(f"  ℹ️ 讯飞连接关闭: code={close_status_code}")

        def on_open(ws_):
            print(f"  ✅ 讯飞 WebSocket 连接成功")

            # 发送业务参数（JSON 文本帧）
            business = {
                "common": {"app_id": app_id},
                "business": {
                    "language": "zh_cn",
                    "domain": "iat",
                    "accent": "mandarin",
                    "vad_eos": 1000,  # 1秒静音即结束（默认3000=3秒）
                    "dwa": "wpgs",  # 动态修正
                    "ptt": 0,       # 标点
                    "nunum": 0,     # 数字不归一化，保留原样
                },
                "data": {
                    "status": 0,  # 第一帧
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": "",
                }
            }
            # 先发业务参数
            ws_.send(json.dumps(business))

            # 发送音频数据（二进制帧）
            status = 1
            chunk_size = 1280  # 每帧 1280 字节
            total_sent = 0
            for i in range(0, len(frames), chunk_size):
                chunk = frames[i:i + chunk_size]
                is_last = (i + chunk_size >= len(frames))
                audio_base64 = base64.b64encode(chunk).decode("utf-8")
                audio_data = {
                    "data": {
                        "status": 2 if is_last else status,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": audio_base64,
                    }
                }
                ws_.send(json.dumps(audio_data))
                total_sent += len(chunk)
                # 小间隔防止服务器读超时（256倍速≈0.00015s，这里用0.005s保稳）
                time.sleep(0.005)
                if is_last:
                    break

        try:
            import ssl
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            # 阻塞运行直到连接关闭
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=10, ping_timeout=5)
        except Exception as e:
            raise Exception(f"讯飞 WebSocket 异常: {e}")

        if not result_text:
            raise Exception("讯飞识别结果为空")

        print(f"✅ 讯飞识别成功: {result_text}")
        return result_text


# ==================== 便捷函数 ====================

def text_to_speech(
    text: str,
    language: str = 'zh-CN',
    output_file: str = None,
    method: str = 'edge_tts',
    voice_profile: Optional[Dict[str, Any]] = None,
) -> str:
    """
    TTS: 便捷的文本转语音函数

    Args:
        text: 要转换的文本
        language: 语言代码
        output_file: 输出文件路径
        method: 生成方式 ('edge_tts' 或 'voxcpm')
        voice_profile: VoxCPM 音色配置（参考 SpeechProcessor.text_to_speech）

    Returns:
        str: 音频文件路径
    """
    processor = SpeechProcessor(language=language)
    return asyncio.run(processor.text_to_speech(text, output_file, method, voice_profile))


def speech_to_text(audio_file: str = None, duration: int = 10, 
                  language: str = 'zh-CN', method: str = 'auto', 
                  whisper_language: str = 'zh', silence_threshold: int = 50) -> str:     #  100
    """
    ASR: 便捷的语音转文字函数
    
    Args:
        audio_file: 音频文件路径（如果为None则从麦克风录音）
        duration: 录音时长（秒）
        language: 语言代码（用于 TTS，如 'zh-CN'）
        method: 识别方法 ('whisper', 'azure', 'baidu', 'xfyun')
        whisper_language: Whisper 识别语言（'zh'=简体中文, 'en'=英文），默认简体中文
        silence_threshold: 静音阈值（0-32767），值越大越不灵敏，默认100
        
    Returns:
        str: 识别出的文字
    """
    processor = SpeechProcessor(language=language)
    return processor.speech_to_text(audio_file, duration, method, whisper_language, silence_threshold)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("="*70)
    print("🎤 语音处理模块测试")
    print("="*70)
    
    # 测试1: TTS - 文本转语音
    print("\n📝 测试1: TTS - 文本转语音")
    print("-"*70)
    
    test_text = "你好，这是一个语音处理模块的测试。"
    try:
        audio_file = text_to_speech(test_text)
        print(f"✅ TTS 成功，音频文件: {audio_file}")
    except Exception as e:
        print(f"❌ TTS 失败: {e}")
    
    # 测试2: ASR - 语音转文字说明
    print("\n🎙️  测试2: ASR - 语音转文字")
    print("-"*70)
    print("\n支持的 ASR 服务：")
    print("1. Azure Speech Service（推荐）")
    print("   - 设置环境变量: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION")
    print("   - 安装: pip install azure-cognitiveservices-speech")
    print("   - 使用: speech_to_text(method='azure')")
    print("\n2. 百度语音识别")
    print("   - 设置环境变量: BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY")
    print("   - 安装: pip install baidu-aip")
    print("   - 使用: speech_to_text(method='baidu')")
    print("\n3. 讯飞语音识别")
    print("   - 参考官方文档实现")
    print("   - 使用: speech_to_text(method='xfyun')")
    print("\n💡 示例代码：")
    print("   from Agent.TTS.speech_to_text import speech_to_text")
    print("   # 从麦克风录音并识别")
    print("   text = speech_to_text(duration=10, method='azure')")
    print("   # 从音频文件识别")
    print("   text = speech_to_text(audio_file='test.wav', method='azure')")
