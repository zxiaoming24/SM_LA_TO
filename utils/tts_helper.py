"""
通用异步TTS辅助函数
为所有Agent提供统一的文本转语音集成接口
支持 Edge TTS（默认）和 VoxCPM 声音设计/音色克隆
自动读取用户的音色偏好配置（方案B）
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Set

# TTS音频输出目录（统一存放）
TTS_OUTPUT_DIR = Path(__file__).parent.parent / "Agent" / "children_agent" / "static" / "tts_audio"

# 用户音色偏好存储目录
USER_VOICES_DIR = Path(__file__).parent.parent / "user_voices"


def _get_user_voice_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """从磁盘读取用户的音色偏好配置。"""
    if not user_id:
        return None
    profile_path = USER_VOICES_DIR / f"{user_id}.json"
    if profile_path.exists():
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 读取用户音色配置失败 ({user_id}): {e}")
    return None


async def generate_tts_audio(
    text: str,
    agent_name: str = "agent",
    language: str = "zh-CN",
    output_dir: Optional[str] = None,
    max_text_length: int = 2000,
    method: str = "edge_tts",
    voice_profile: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """
    异步生成TTS音频文件

    如果未指定 method/voice_profile，但提供了 user_id，
    会自动从用户音色偏好配置中读取。

    Args:
        text: 要转换的文本内容
        agent_name: Agent名称（用于生成文件名）
        language: 语言代码，默认中文
        output_dir: 输出目录，默认使用统一目录
        max_text_length: 最大文本长度，超出则截断
        method: 生成方式 ('edge_tts' 或 'voxcpm')
        voice_profile: VoxCPM 音色配置字典

            voice_profile 支持以下模式:
            - design (声音设计):
                {"mode": "design", "control": "温柔女声"}
            - clone (可控克隆):
                {"mode": "clone", "reference_audio": "/path/to/audio.wav"}
            - ultimate_clone (极致克隆):
                {"mode": "ultimate_clone", "reference_audio": "/path/to/audio.wav",
                 "prompt_text": "音频转录文本"}

            通用参数:
                server_url (str): VoxCPM 服务地址，默认 http://localhost:8800

        user_id: 用户ID（可选）。如果提供且未指定 voice_profile，自动加载用户音色偏好

    Returns:
        str: 音频文件的相对URL路径（如 /static/tts_audio/xxx.mp3），失败返回 None
    """
    if not text or not text.strip():
        print(f"⚠️ [{agent_name}] TTS跳过：文本为空")
        return None

    loop = asyncio.get_running_loop()

    # ★★★ 方案B：如果未指定音色配置但有 user_id，自动从用户偏好加载 ★★★
    resolved_method = method
    resolved_profile = voice_profile
    if user_id and method == "edge_tts" and voice_profile is None:
        saved = await loop.run_in_executor(None, lambda: _get_user_voice_profile(user_id))
        if saved and saved.get("method") == "voxcpm":
            resolved_method = "voxcpm"
            resolved_profile = {k: v for k, v in saved.items() if k != "method"}
            print(f"🎯 [{agent_name}] 检测到用户 {user_id} 的音色偏好，自动切换至 VoxCPM")

    try:
        from Agent.TTS.speech_to_text import SpeechProcessor

        if len(text) > max_text_length:
            text = text[:max_text_length]
            print(f"⚠️ [{agent_name}] TTS文本过长，已截断为 {max_text_length} 字符")

        if output_dir:
            out_path = Path(output_dir)
        else:
            out_path = TTS_OUTPUT_DIR
        await loop.run_in_executor(None, lambda: out_path.mkdir(parents=True, exist_ok=True))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suffix = ".wav" if resolved_method == "voxcpm" else ".mp3"
        audio_filename = f"tts_{agent_name}_{timestamp}{suffix}"
        audio_filepath = str(out_path / audio_filename)

        processor = SpeechProcessor(language=language)
        audio_path = await processor.text_to_speech(
            text,
            output_file=audio_filepath,
            method=resolved_method,
            voice_profile=resolved_profile,
        )

        if audio_path and await loop.run_in_executor(None, lambda: os.path.exists(audio_path)):
            relative_url = f"/static/tts_audio/{audio_filename}"
            print(f"✅ [{agent_name}] TTS音频已生成: {relative_url}")
            return relative_url
        else:
            print(f"❌ [{agent_name}] TTS音频文件生成失败")
            return None

    except ImportError:
        print(f"❌ [{agent_name}] TTS模块未安装，请执行: pip install edge-tts")
        return None
    except Exception as e:
        print(f"⚠️ [{agent_name}] TTS生成失败（不影响主功能）: {e}")
        return None


def extract_tts_path(result: dict) -> str:
    """从结果中递归提取 TTS 音频路径"""
    if not isinstance(result, dict):
        return ""

    def _search(d: dict, visited: Set) -> str:
        if not isinstance(d, dict):
            return ""
        d_id = id(d)
        if d_id in visited:
            return ""
        visited.add(d_id)
        path = d.get("tts_audio_path", "")
        if isinstance(path, str) and path:
            return path
        for v in d.values():
            if isinstance(v, dict):
                found = _search(v, visited)
                if found:
                    return found
        return ""

    return _search(result, visited=set())


def result_has_tts(result: dict) -> bool:
    """递归检查返回结果中是否已包含 TTS 音频路径"""
    if not isinstance(result, dict):
        return False
    if result.get("tts_audio_path"):
        return True

    data = result.get("data", {})
    if not isinstance(data, dict):
        return False
    if data.get("tts_audio_path"):
        return True

    for key in ("document", "practice", "problem", "mindmap", "mindmap_json",
                "extension", "reading_material", "video", "questions"):
        item = data.get(key)
        if isinstance(item, dict) and item.get("tts_audio_path"):
            return True

    raw = data.get("metadata", {}).get("raw_results", {})
    if isinstance(raw, dict):
        for v in raw.values():
            if isinstance(v, dict):
                if v.get("tts_audio_path"):
                    return True
                for inner_key in ("document", "problem", "practice",
                                  "mindmap", "mindmap_json", "reading_material", "videos"):
                    inner = v.get(inner_key)
                    if isinstance(inner, dict) and inner.get("tts_audio_path"):
                        return True
    return False


def extract_tts_text(result: dict) -> str:
    """从结果中递归提取适合 TTS 的文本"""
    if not isinstance(result, dict):
        return ""

    reply = result.get("reply", "")
    if reply:
        return reply

    def _search(d: dict, visited: Set = None) -> str:
        if not isinstance(d, dict) or visited is None:
            return ""
        d_id = id(d)
        if d_id in visited:
            return ""
        visited.add(d_id)

        doc_c = d.get("doc_content", "")
        if isinstance(doc_c, str) and doc_c:
            title = d.get("doc_title", "") or ""
            return f"{title}。{doc_c[:500]}" if title else doc_c[:500]

        doc = d.get("document", "")
        if isinstance(doc, dict):
            t = doc.get("doc_title", "") or d.get("doc_title", "")
            c = doc.get("doc_content", "") or doc.get("content", "")
            if isinstance(c, str) and c:
                return f"{t}。{c[:500]}" if t else c[:500]

        practice = d.get("practice", {})
        if isinstance(practice, dict) and practice.get("title"):
            return f"{practice['title']}。{practice.get('description', '')[:300]}"

        mindmap = d.get("mindmap", {}) or d.get("mindmap_json", {})
        if isinstance(mindmap, dict) and mindmap.get("name"):
            return f"思维导图：{mindmap.get('name', '')}"

        reading = d.get("reading_material", {})
        if isinstance(reading, dict):
            title = reading.get("title", "")
            bg = reading.get("background", "")[:300]
            if title or bg:
                return f"{title}。{bg}" if bg else title

        videos = d.get("videos", []) or (d.get("result", {}) or {}).get("videos", [])
        if isinstance(videos, list) and videos:
            first = videos[0]
            return f"视频搜索结果：{first.get('title', first.get('name', '未命名视频'))[:200]}"

        final = d.get("final_result", {})
        if isinstance(final, dict):
            for key in ("answer", "content", "summary", "reply", "message"):
                v = final.get(key)
                if v:
                    return str(v)[:500]

        questions = d.get("questions", {})
        if isinstance(questions, dict):
            for q_type in ('single_choice', 'short_answer', 'code_practice'):
                qs = questions.get(q_type, [])
                if isinstance(qs, list) and qs and isinstance(qs[0], dict):
                    q_text = qs[0].get("question", "")
                    if q_text:
                        return f"练习题：{q_text[:200]}"

        for v in d.values():
            if isinstance(v, dict):
                found = _search(v, visited)
                if found:
                    return found
        return ""

    data = result.get("data", {})
    return _search(data, visited=set())


async def ensure_tts_in_result(result: dict, user_id: Optional[str] = None) -> dict:
    """
    确保结果中包含 TTS 音频路径：
    如果已存在则提取到顶层，否则生成兜底TTS

    Args:
        result: 处理结果字典
        user_id: 用户ID（用于音色偏好）

    Returns:
        更新后的结果字典
    """
    if not result.get("tts_audio_path"):
        tts_path = extract_tts_path(result)
        if tts_path:
            result["tts_audio_path"] = tts_path

    if not result.get("tts_audio_path"):
        tts_text = extract_tts_text(result)
        if tts_text:
            tts_path = await generate_tts_audio(
                text=tts_text,
                agent_name="fallback",
                user_id=user_id
            )
            if tts_path:
                result["tts_audio_path"] = tts_path

    return result
