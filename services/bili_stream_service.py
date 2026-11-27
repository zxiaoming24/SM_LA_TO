"""
B站视频流代理服务模块
通过B站公开API获取视频流地址，并通过自建代理转发给前端
前端使用HTML5 <video> 标签播放，可直接监听所有播放事件

用法（由 api_server.py 注册路由后自动可用）:
  GET /api/play-info?bvid=BV1xxx  → 获取视频信息和流地址
  GET /api/stream?url=xxx         → 代理B站视频流
  GET /api/proxy-image?url=xxx    → 代理B站图片
"""

import asyncio
import hashlib
import time
from typing import Dict, Any, List, Optional

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse


class BiliAPIClient:
    """B站API客户端 - 获取视频信息和流地址"""

    def __init__(self):
        self.session = requests.Session()
        uid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Origin': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        self.session.cookies.set('buvid3', f'{uid}infoc')
        self.session.cookies.set('buvid4', f'{uid}infoc')

    def get_video_info(self, bvid: str) -> Dict[str, Any]:
        """
        获取视频基本信息
        GET https://api.bilibili.com/x/web-interface/view?bvid=BV1xx
        """
        url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"B站API返回状态码: {resp.status_code}")
        data = resp.json()
        if data.get('code') != 0:
            raise Exception(f"B站API错误: {data.get('message', data.get('msg', '未知错误'))}")
        return data['data']

    def get_play_url(self, bvid: str, cid: int, qn: int = 32) -> Dict[str, Any]:
        """
        获取视频播放地址
        qn: 清晰度 32=360P 64=480P 80=1080P 116=1080P60
        fnval=0 返回 MP4 格式 (durl)，fnval=16 返回 DASH 格式
        """
        url = (f'https://api.bilibili.com/x/player/playurl?bvid={bvid}'
               f'&cid={cid}&qn={qn}&fnval=0&fnver=0&fourk=1')
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"播放地址API返回状态码: {resp.status_code}")
        data = resp.json()
        if data.get('code') != 0:
            raise Exception(f"播放地址API错误: {data.get('message', data.get('msg', '未知错误'))}")
        return data['data']

    def get_video_and_playinfo(self, bvid: str, page: int = 1) -> Dict[str, Any]:
        """获取完整视频信息（含播放地址），支持分P"""
        info = self.get_video_info(bvid)
        pages = info.get('pages', [])
        # 根据 page 参数选择对应的分P
        target_page = None
        for p in pages:
            if p.get('page') == page:
                target_page = p
                break
        if not target_page:
            target_page = pages[0] if pages else {}
        cid = target_page.get('cid', info.get('cid', 0))
        if not cid:
            raise Exception("无法获取视频 cid")

        # 尝试不同清晰度，从高到低
        play_info = None
        for qn in [80, 64, 32]:
            try:
                play_info = self.get_play_url(bvid, cid, qn=qn)
                if play_info and play_info.get('durl'):
                    break
            except Exception:
                continue

        if not play_info or not play_info.get('durl'):
            raise Exception("无法获取视频播放地址")

        result = {
            'bvid': bvid,
            'title': info.get('title', ''),
            'cover': info.get('pic', ''),
            'author': info.get('owner', {}).get('name', ''),
            'duration': info.get('duration', 0),
            'cid': cid,
            'current_page': page,
            'total_pages': len(pages),
            'pages': [
                {'cid': p.get('cid'), 'title': p.get('part'), 'page': p.get('page')}
                for p in pages
            ],
            'streams': []
        }

        for i, durl in enumerate(play_info.get('durl', [])):
            result['streams'].append({
                'order': i + 1,
                'url': durl.get('url', ''),
                'backup_urls': durl.get('backup_url', []),
                'size': durl.get('size', 0)
            })

        result['quality'] = play_info.get('quality', 0)
        result['quality_desc'] = self._quality_desc(play_info.get('quality', 0))
        return result

    def _quality_desc(self, qn: int) -> str:
        mapping = {6: '240P', 16: '360P', 32: '480P', 64: '720P', 74: '720P60',
                   80: '1080P', 112: '1080P+', 116: '1080P60', 120: '4K'}
        return mapping.get(qn, f'{qn}P')

    # ==================== 字幕相关 ====================

    def get_subtitle_list(self, bvid: str, cid: int) -> list:
        """
        获取视频的字幕列表。
        GET https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}
        返回字幕轨道列表，每个轨道包含 subtitle_url（相对或绝对路径）。
        """
        url = f'https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}'
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if data.get('code') != 0:
            return []
        subtitle_info = data.get('data', {}).get('subtitle', {})
        subtitles = subtitle_info.get('subtitles', [])
        return subtitles

    def get_subtitle_snippet(self, bvid: str, cid: int,
                             from_sec: float, to_sec: float,
                             page: int = 1) -> str:
        """
        获取视频指定时间段的字幕文本。

        流程：
        1. 获取字幕列表
        2. 取第一个AI生成或手动字幕轨道
        3. 下载字幕JSON
        4. 筛选 [from_sec, to_sec] 范围内的字幕片段
        5. 若 B站 无字幕，回退到 Whisper 本地转录（首次触发后台任务）
        6. 拼接返回文本

        Args:
            page: 分P编号（多P视频使用）

        Returns:
            str: 字幕文本（时间戳+内容），若无可返回空字符串
        """
        try:
            subtitles = self.get_subtitle_list(bvid, cid)
            if not subtitles:
                # ★★★ B站无字幕，回退到 Whisper ★★★
                return self._fallback_whisper_subtitle(bvid, cid, from_sec, to_sec, page=page)

            # 优先选AI生成的字幕（通常是最后一个，或者 lan_doc=zh-CN 的）
            subtitle_url = ''
            for sub in subtitles:
                if sub.get('lan_doc', '').startswith('中文') or sub.get('language', '').startswith('中文'):
                    subtitle_url = sub.get('subtitle_url', '')
                    break
            if not subtitle_url:
                # 取第一个可用字幕
                subtitle_url = subtitles[0].get('subtitle_url', '')
            if not subtitle_url:
                # ★★★ 有列表但无实际URL，回退到 Whisper ★★★
                return self._fallback_whisper_subtitle(bvid, cid, from_sec, to_sec, page=page)

            # 拼接完整URL（B站返回的相对路径）
            if subtitle_url.startswith('//'):
                subtitle_url = 'https:' + subtitle_url
            elif subtitle_url.startswith('/'):
                subtitle_url = 'https:' + subtitle_url

            # 下载字幕JSON
            resp = self.session.get(subtitle_url, timeout=15)
            if resp.status_code != 200:
                return self._fallback_whisper_subtitle(bvid, cid, from_sec, to_sec, page=page)
            sub_data = resp.json()
            body = sub_data.get('body', [])
            if not body:
                return self._fallback_whisper_subtitle(bvid, cid, from_sec, to_sec, page=page)

            # 筛选时间范围内的字幕
            snippet_parts = []
            for item in body:
                start = item.get('from', 0)
                end = item.get('to', 0)
                content = item.get('content', '').strip()
                if not content:
                    continue
                # 判断是否落在范围内（或与范围有重叠）
                if (start >= from_sec and start <= to_sec) or \
                   (end >= from_sec and end <= to_sec) or \
                   (start <= from_sec and end >= to_sec):
                    snippet_parts.append(
                        f'[{int(start // 60):d}:{int(start % 60):02d}] {content}'
                    )

            if not snippet_parts:
                return ''

            return '\n'.join(snippet_parts)

        except Exception as e:
            print(f'   ⚠️ 获取字幕片段失败: {e}')
            return ''

    def _fallback_whisper_subtitle(self, bvid: str, cid: int,
                                   from_sec: float, to_sec: float,
                                   page: int = 1) -> str:
        """当B站无字幕时，回退到 Whisper 本地转录"""
        try:
            from services.subtitle_service import get_subtitle_text

            # 需要获取视频流地址给 Whisper
            info = self.get_video_and_playinfo(bvid, page=page)
            stream_url = info['streams'][0]['url']

            label = f"{bvid} p{page}" if page > 1 else bvid
            print(f'   🎤 B站无字幕，回退到 Whisper 转录: {label}')
            text = get_subtitle_text(bvid, cid, stream_url, from_sec, to_sec, page=page)
            if text:
                print(f'   ✅ Whisper 字幕获取成功: {len(text)} 字符')
            else:
                print(f'   ⏳ Whisper 字幕尚在生成中（后台进行）')
            return text
        except Exception as e:
            print(f'   ⚠️ Whisper 回退失败: {e}')
            return ''


# ==================== 全局客户端实例 ====================
_bili_client = BiliAPIClient()


# ==================== 路由注册函数 ====================

async def _preload_subtitle(bvid: str, info: dict):
    """
    后台预加载字幕（不阻塞 API 返回）
    用户一加载视频就开始转录，等回溯时字幕可能已经就绪
    """
    try:
        loop = asyncio.get_running_loop()
        cid = info.get('cid', 0)
        stream_url = info.get('streams', [{}])[0].get('url', '')
        page = info.get('current_page', 1)
        if not cid or not stream_url:
            return
        from services.subtitle_service import ensure_subtitle_cache
        await loop.run_in_executor(None, lambda: ensure_subtitle_cache(bvid, cid, stream_url, page=page))
    except Exception as e:
        print(f'  ⚠️ 预加载字幕失败: {e}')


def create_bili_stream_router() -> APIRouter:
    """
    创建B站视频流代理路由
    在 api_server.py 中调用: app.include_router(create_bili_stream_router())
    """
    router = APIRouter(tags=["视频流代理"])

    @router.get("/api/play-info")
    async def get_play_info(
        bvid: str = Query(..., description="B站视频BVID"),
        page: int = Query(1, description="分P编号，默认1"),
    ):
        """
        获取视频播放信息（含视频流地址）
        支持多P视频，通过 page 参数指定分P
        前端先调用此接口获取流地址，再将流地址传给 /api/stream 代理播放
        示例: GET /api/play-info?bvid=BV1e4411x7VM&page=1
        """
        try:
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, lambda: _bili_client.get_video_and_playinfo(bvid, page=page))
            # ★★★ 异步预触发字幕转录，不阻塞返回 ★★★
            asyncio.create_task(_preload_subtitle(bvid, info))
            return {"success": True, "data": info}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"获取播放信息失败: {str(e)}")

    @router.get("/api/stream")
    async def proxy_video_stream(
        url: str = Query(..., description="B站视频流URL"),
        req: Request = None
    ):
        """
        代理B站视频流 - 解决跨域问题
        前端 <video> 的 src 指向此端点: /api/stream?url=${encodeURIComponent(url)}
        支持 Range 请求头（用于拖动进度条）
        """
        try:
            loop = asyncio.get_running_loop()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.bilibili.com',
            }

            range_header = req.headers.get('range', '')
            if range_header:
                headers['Range'] = range_header

            resp = await loop.run_in_executor(None, lambda: _bili_client.session.get(url, headers=headers, stream=True, timeout=30))

            if resp.status_code >= 400:
                raise Exception(f"视频流返回状态码: {resp.status_code}")

            streaming_response = StreamingResponse(
                content=resp.iter_content(chunk_size=65536),
                status_code=resp.status_code,
                media_type=resp.headers.get('content-type', 'video/mp4'),
            )

            for header_name in ['content-range', 'content-length', 'accept-ranges', 'content-type']:
                if header_name in resp.headers:
                    streaming_response.headers[header_name] = resp.headers[header_name]

            return streaming_response

        except Exception as e:
            raise HTTPException(status_code=502, detail=f"代理视频流失败: {str(e)}")

    @router.get("/api/proxy-image")
    async def proxy_image(url: str = Query(..., description="图片URL")):
        """代理B站图片"""
        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: _bili_client.session.get(url, stream=True, timeout=10))
            if resp.status_code >= 400:
                raise Exception(f"图片返回状态码: {resp.status_code}")
            return StreamingResponse(
                content=resp.iter_content(chunk_size=65536),
                media_type=resp.headers.get('content-type', 'image/jpeg'),
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"代理图片失败: {str(e)}")

    # ==================== 视频内容总结 ====================

    @router.post("/api/video-summary")
    async def video_summary(req: Request):
        """
        基于视频字幕 + LLM 生成结构化内容总结

        Request body:
            { "bvid": "BV1xxx", "page": 1 }

        Returns:
            {
              "success": true,
              "data": {
                "summary": "整体总结",
                "key_points": ["要点1", "要点2", ...],
                "sections": [{"title": "章节名", "content": "内容总结"}, ...]
              },
              "video_title": "视频标题"
            }
        """
        import json as _json
        body = await req.json()
        bvid = body.get("bvid", "")
        page = body.get("page", 1)
        if not bvid:
            raise HTTPException(status_code=400, detail="缺少 bvid 参数")

        loop = asyncio.get_running_loop()

        # 1. 获取视频信息
        info = await loop.run_in_executor(None, lambda: _bili_client.get_video_and_playinfo(bvid, page=page))
        cid = info.get('cid', 0)
        stream_url = info['streams'][0]['url']
        video_title = info.get('title', '')

        # 2. 获取字幕全文
        from services.subtitle_service import get_subtitle_segments as _get_segments
        segments = await loop.run_in_executor(
            None, lambda: _get_segments(bvid, cid, stream_url, page=page)
        )
        if not segments:
            return {"success": False, "error": "字幕尚未就绪，请稍后重试（Whisper 转录中）"}

        # 组装全文
        full_text = "\n".join([s["text"] for s in segments])
        # 限制长度避免超出 token 限制
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "\n...（转录文本过长，已截断）"

        # 3. 调用 LLM 生成总结
        from utils.llm_config import get_chat_openai
        from langchain_core.messages import HumanMessage

        llm = get_chat_openai(temperature=0.3, max_tokens=2500)

        prompt = f"""你是一个专业的视频内容总结助手。请根据以下视频转录文本，生成结构化的中文总结。

## 视频标题
{video_title}

## 转录文本
{full_text}

## 要求
请严格按以下 JSON 格式返回（只返回 JSON，不要 markdown 标记）：
{{
  "summary": "视频整体内容的简要总结（150-250字），概括核心主题和主要内容",
  "key_points": ["要点1（带具体细节）", "要点2", "要点3", "要点4", "要点5"],
  "sections": [
    {{"title": "第一部分：主题名称", "content": "该部分的核心内容总结"}},
    {{"title": "第二部分：主题名称", "content": "该部分的核心内容总结"}}
  ]
}}
"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        result_text = response.content.strip()
        # 清理可能的 markdown 标记
        result_text = result_text.replace("```json", "").replace("```", "").strip()

        try:
            result = _json.loads(result_text)
        except Exception:
            result = {"summary": result_text, "key_points": [], "sections": []}

        return {"success": True, "data": result, "video_title": video_title}

    # ==================== 视频内容思维导图 ====================

    @router.post("/api/video-mindmap")
    async def video_mindmap(req: Request):
        """
        基于视频字幕 + LLM 生成思维导图 JSON

        Request body:
            { "bvid": "BV1xxx", "page": 1 }

        Returns:
            { "success": true, "data": { "mindmap": {...} } }
        """
        import json as _json
        body = await req.json()
        bvid = body.get("bvid", "")
        page = body.get("page", 1)
        if not bvid:
            raise HTTPException(status_code=400, detail="缺少 bvid 参数")

        loop = asyncio.get_running_loop()

        # 1. 获取视频信息
        info = await loop.run_in_executor(None, lambda: _bili_client.get_video_and_playinfo(bvid, page=page))
        cid = info.get('cid', 0)
        stream_url = info['streams'][0]['url']
        video_title = info.get('title', '')

        # 2. 获取字幕全文
        from services.subtitle_service import get_subtitle_segments as _get_segments
        segments = await loop.run_in_executor(
            None, lambda: _get_segments(bvid, cid, stream_url, page=page)
        )
        if not segments:
            return {"success": False, "error": "字幕尚未就绪，请稍后重试（Whisper 转录中）"}

        full_text = "\n".join([s["text"] for s in segments])
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "\n...（转录文本过长，已截断）"

        # 3. 调用 LLM 生成思维导图 JSON
        from utils.llm_config import get_chat_openai
        from langchain_core.messages import HumanMessage

        llm = get_chat_openai(temperature=0.3, max_tokens=4000)

        prompt = f"""你是一个知识结构化专家。请根据以下视频转录文本，生成思维导图 JSON 数据。

## 视频标题
{video_title}

## 转录文本
{full_text}

## 要求
请将视频内容组织为树形结构的思维导图 JSON，严格遵循以下格式（只返回 JSON，不要 markdown 标记）：

{{
  "name": "知识主题（视频主题名称）",
  "children": [
    {{
      "name": "一级知识点1",
      "children": [
        {{
          "name": "二级知识点1.1",
          "content": "该知识点的详细内容解释"
        }},
        {{
          "name": "二级知识点1.2",
          "content": "该知识点的详细内容解释"
        }}
      ]
    }},
    {{
      "name": "一级知识点2",
      "children": [
        {{
          "name": "二级知识点2.1",
          "content": "该知识点的详细内容解释"
        }}
      ]
    }}
  ]
}}

注意：
- 每个节点必须有 name 字段
- 叶子节点必须有 content 字段（详细解释）
- 结构层次 2-3 层，不宜过深
- 内容需忠实于视频转录文本，不要编造
- 用中文输出
"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        result_text = response.content.strip()
        result_text = result_text.replace("```json", "").replace("```", "").strip()

        try:
            mindmap_json = _json.loads(result_text)
        except Exception:
            mindmap_json = {"name": video_title, "children": []}

        return {"success": True, "data": {"mindmap": mindmap_json, "video_title": video_title}}

    return router
