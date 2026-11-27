"""
TTS/ASR 语音模块
提供 TTS（文本转语音）和 ASR（语音转文字）功能
"""

from .speech_to_text import (
    SpeechProcessor,
    text_to_speech,
    speech_to_text
)

__all__ = [
    'SpeechProcessor',
    'text_to_speech',
    'speech_to_text'
]
