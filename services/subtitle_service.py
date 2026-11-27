"""
统一字幕服务

整合字幕来源：
  1. B站 API 字幕（最快）
  2. faster-whisper 本地转录（回退方案，带缓存）

缓存结构：
  - 单P视频: data/subtitle_cache/BV1xxx.json
  - 多P视频: data/subtitle_cache/BV1xxx/p1.json, p2.json, ...

供 api_server.py 的回溯事件处理使用，对调用方透明。
"""

import asyncio
import os
import json
import threading
from typing import Optional, List, Dict, Any

import requests

# Whisper 转录器（从 video_ww 复用）
try:
    from video_ww.whisper_transcriber import WhisperTranscriber, SubtitleSegment
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'video_ww'))
    from whisper_transcriber import WhisperTranscriber, SubtitleSegment

# 线程锁：保护 _whisper 懒加载和 _pending_tasks 并发写入
_whisper_lock = threading.Lock()
_pending_tasks_lock = threading.Lock()


# ==================== 配置 ====================

_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'subtitle_cache')
os.makedirs(_CACHE_DIR, exist_ok=True)

# Whisper 转录器（全局单例，懒加载）
_whisper: Optional[WhisperTranscriber] = None

# 后台任务跟踪: "bvid" -> "running" | "done" | "error"
# 多P时用 "bvid_pN" 区分
_pending_tasks: Dict[str, str] = {}

# B站 API session（复用 headers）
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com',
})


def _cache_path(bvid: str, page: int = 1) -> str:
    """
    缓存路径：
      page=1 → data/subtitle_cache/BV1xxx.json（兼容旧文件）
      page>1 → data/subtitle_cache/BV1xxx/pN.json
    """
    if page <= 1:
        # 单P用旧路径兼容
        p = os.path.join(_CACHE_DIR, f"{bvid}.json")
        if os.path.exists(p):
            return p
        # 不存在则检查多P目录
        dir_path = os.path.join(_CACHE_DIR, bvid)
        single_path = os.path.join(dir_path, "p1.json")
        if os.path.exists(single_path):
            return single_path
        return p
    else:
        dir_path = os.path.join(_CACHE_DIR, bvid)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"p{page}.json")


def _task_key(bvid: str, page: int = 1) -> str:
    """后台任务跟踪key"""
    return f"{bvid}_p{page}" if page > 1 else bvid


def _get_whisper() -> WhisperTranscriber:
    """懒加载 Whisper 转录器（自动检测 GPU），线程安全"""
    global _whisper
    with _whisper_lock:
        if _whisper is not None:
            return _whisper
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except ImportError:
            has_cuda = False

        if has_cuda:
            device = "cuda"
            compute_type = "float16"
            model_size = "small"
            gpu_name = torch.cuda.get_device_name(0)
            print(f"  [字幕服务] 检测到 CUDA GPU: {gpu_name}")
        else:
            device = "cpu"
            compute_type = "int8"
            model_size = "tiny"
            print("  [字幕服务] 未检测到 GPU，使用 CPU int8")

        print(f"  [字幕服务] 初始化 Whisper (model={model_size}, device={device}, compute={compute_type})")
        _whisper = WhisperTranscriber(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )
        return _whisper


def _fetch_bili_subtitle(bvid: str, cid: int) -> Optional[List[Dict]]:
    """从 B站 API 获取字幕段列表"""
    try:
        url = f'https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}'
        resp = _session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('code') != 0:
            return None

        subtitles = data.get('data', {}).get('subtitle', {}).get('subtitles', [])
        if not subtitles:
            return None

        sub_url = ''
        for sub in subtitles:
            if sub.get('lan_doc', '').startswith('中文'):
                sub_url = sub.get('subtitle_url', '')
                break
        if not sub_url:
            sub_url = subtitles[0].get('subtitle_url', '')
        if not sub_url:
            return None

        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url
        elif sub_url.startswith('/'):
            sub_url = 'https:' + sub_url

        resp = _session.get(sub_url, timeout=15)
        if resp.status_code != 200:
            return None
        body = resp.json().get('body', [])
        if not body:
            return None

        return [
            {"start": item["from"], "end": item["to"], "text": item["content"].strip()}
            for item in body if item.get("content", "").strip()
        ]
    except Exception:
        return None


def _whisper_task(bvid: str, stream_url: str, page: int = 1):
    """后台 Whisper 转录任务（按分P）"""
    task_id = _task_key(bvid, page)
    try:
        with _pending_tasks_lock:
            _pending_tasks[task_id] = "running"
        label = f"{bvid} p{page}" if page > 1 else bvid
        print(f"  [字幕服务] 后台 Whisper 转录开始: {label}")
        transcriber = _get_whisper()
        cache_path = _cache_path(bvid, page)
        transcriber.transcribe_video_full(
            stream_url, language="zh", cache_path=cache_path,
            session=_session,
        )
        with _pending_tasks_lock:
            _pending_tasks[task_id] = "done"
        print(f"  [字幕服务] Whisper 转录完成: {label}")
    except Exception as e:
        with _pending_tasks_lock:
            _pending_tasks[task_id] = "error"
        print(f"  [字幕服务] Whisper 转录失败: {label} - {e}")


def get_subtitle_segments(
    bvid: str,
    cid: int,
    stream_url: str,
    from_sec: Optional[float] = None,
    to_sec: Optional[float] = None,
    page: int = 1,
) -> List[Dict]:
    """
    获取视频字幕段列表（B站API → Whisper 回退）
    支持多P视频。
    """
    # 1. 先查 B站 API
    segments = _fetch_bili_subtitle(bvid, cid)
    if segments:
        print(f"  [字幕服务] 使用 B站 API 字幕: {bvid} ({len(segments)} 段)")
        return _filter_segments(segments, from_sec, to_sec)

    # 2. 查本地缓存（带分P）
    cache_path = _cache_path(bvid, page)
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            segments = json.load(f)
        label = f"{bvid} p{page}" if page > 1 else bvid
        print(f"  [字幕服务] 使用 Whisper 缓存: {label} ({len(segments)} 段)")
        return _filter_segments(segments, from_sec, to_sec)

    # 3. 启动后台 Whisper 转录
    task_id = _task_key(bvid, page)
    with _pending_tasks_lock:
        should_start = task_id not in _pending_tasks or _pending_tasks[task_id] in ("error",)
        if should_start:
            _pending_tasks[task_id] = "pending"
    if should_start:
        t = threading.Thread(target=_whisper_task, args=(bvid, stream_url, page), daemon=True)
        t.start()
        label = f"{bvid} p{page}" if page > 1 else bvid
        print(f"  [字幕服务] 启动后台 Whisper 转录: {label}")

    return []


def get_subtitle_text(
    bvid: str,
    cid: int,
    stream_url: str,
    from_sec: float,
    to_sec: float,
    page: int = 1,
) -> str:
    """
    获取指定时间段字幕文本（供 api_server.py 调用）
    支持多P。
    """
    segments = get_subtitle_segments(bvid, cid, stream_url, from_sec, to_sec, page=page)
    if not segments:
        return ""

    lines = []
    for seg in segments:
        m, s = divmod(int(seg["start"]), 60)
        lines.append(f'[{m}:{s:02d}] {seg["text"]}')

    return "\n".join(lines)


def _filter_segments(
    segments: List[Dict],
    from_sec: Optional[float],
    to_sec: Optional[float],
) -> List[Dict]:
    """按时间段筛选字幕段"""
    if from_sec is None and to_sec is None:
        return segments
    f = from_sec or 0
    t = to_sec or 999999
    return [
        s for s in segments
        if (s["start"] >= f and s["start"] <= t) or
           (s["end"] >= f and s["end"] <= t) or
           (s["start"] <= f and s["end"] >= t)
    ]


def get_transcription_status(bvid: str, page: int = 1) -> str:
    """查询后台转录状态"""
    with _pending_tasks_lock:
        return _pending_tasks.get(_task_key(bvid, page), "none")


def ensure_subtitle_cache(bvid: str, cid: int, stream_url: str, page: int = 1):
    """
    确保字幕缓存存在
    适用于播放器预加载场景
    """
    if _fetch_bili_subtitle(bvid, cid):
        return True
    if os.path.exists(_cache_path(bvid, page)):
        return True
    task_id = _task_key(bvid, page)
    with _pending_tasks_lock:
        should_start = task_id not in _pending_tasks or _pending_tasks[task_id] in ("error",)
    if should_start:
        t = threading.Thread(target=_whisper_task, args=(bvid, stream_url, page), daemon=True)
        t.start()
    return False
