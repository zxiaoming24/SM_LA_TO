import argparse
import asyncio
from logger import get_logger
import uuid
import json
from contextlib import asynccontextmanager
import os

# 【核心修复】在导入任何业务模块前，先伪造缺失的 ultralytics.nn.extra_modules
# 解决自定义 YOLO 模型（含 DCNv2 等）加载时的 ModuleNotFoundError
import sys
import types
import torch
import torch.nn as nn
from ultralytics.nn.modules import C2f, Bottleneck, Conv


class FakeModuleFactory:
    def __init__(self, name):
        self.__name__ = name
        self.__path__ = []

    def __getattr__(self, name):
        if 'C2f' in name:
            return C2f
        elif 'Bottleneck' in name:
            return Bottleneck
        elif 'Conv' in name:
            return Conv
        else:

            class Dummy(nn.Module):
                def __init__(self, *args, **kwargs):
                    super().__init__()

                def forward(self, x):
                    return x
            return Dummy


sys.modules['ultralytics.nn.extra_modules'] = FakeModuleFactory(
    'ultralytics.nn.extra_modules')
sys.modules['ultralytics.nn.extra_modules.block'] = FakeModuleFactory(
    'ultralytics.nn.extra_modules.block')
# ---------------------------------------------------------

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.signaling import object_from_string, object_to_string

from video_deal_webrtc import VideoWrapper

# 存储每个连接的信息: {session_id: {pc: RTCPeerConnection, ws: WebSocket, candidate_queue: list}}
connections = {}
pcs = set()

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


async def send_analysis_result(session_id: str, payload: dict) -> None:
    conn = connections.get(session_id)
    if conn and conn.get("ws"):
        try:
            await conn["ws"].send_json({
                "type": "analysis",
                "session_id": session_id,
                "payload": payload
            })
        except Exception as e:
            logger.debug(f"发送分析结果失败: {e}")


async def send_or_queue_candidate(session_id: str, payload: dict):
    conn = connections.get(session_id)
    if conn is None:
        return
    ws = conn.get("ws")
    if ws is not None:
        try:
            await ws.send_json(payload)
            return
        except Exception:
            pass
    # 队列化，等待 WS 注册后发送
    conn["candidate_queue"].append(payload)


async def offer(params: dict):
    from config import SittingPostureConfig, EmotionConfig, MultiModalConfig, GazeConfig

    offer_data = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    session_id = params.get("session_id", str(uuid.uuid4()))

    # 获取分析配置，默认值从 config.py 读取
    analysis_config = params.get("analysis", {
        "realtimeHint": False,
        "behaviorAnalysis": MultiModalConfig.ENABLE_MULTI_MODAL,
        "expressionAnalysis": EmotionConfig.ENABLE_EMOTION,
        "postureAnalysis": SittingPostureConfig.ENABLE_SITTING_POSTURE,
        "gazeAnalysis": GazeConfig.ENABLE_GAZE_DETECTION,
        "sessionId": None
    })

    pc = RTCPeerConnection()
    pcs.add(pc)

    # ★★★ 如果 session 已存在，先清理旧连接，但保留 WebSocket 和 pending 状态 ★★★
    old = connections.pop(session_id, None)
    if old:
        old_pc = old.get("pc")
        if old_pc:
            try:
                await old_pc.close()
            except Exception:
                pass
        old_ws = old.get("ws")
        old_queue = old.get("candidate_queue", [])
        old_pending_uid = old.get("pending_user_id", "")
    else:
        old_ws = None
        old_queue = []
        old_pending_uid = ""

    connections[session_id] = {
        "pc": pc,
        "ws": old_ws,           # ★★★ 保留已注册的 WebSocket ★★★
        "candidate_queue": old_queue,  # ★★★ 保留排队的 ICE 候选 ★★★
        "analysis": analysis_config,
        "video_wrappers": [],   # ★★★ 存储 VideoWrapper 实例，用于透传 userId ★★★
        "pending_user_id": old_pending_uid,  # ★★★ 保留待透传的 userId ★★★
    }

    await server(pc, offer_data, session_id)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
        "session_id": session_id,
    }


async def websocket_handler(websocket: WebSocket):
    """处理 WebSocket 连接"""
    session_id = None
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"WebSocket accept 失败: {e}")
        return

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "register":
                new_sid = raw.get("session_id")
                if not new_sid:
                    await websocket.send_json(
                        {"type": "error", "message": "Missing session_id"})
                    continue

                # ★★★ 更新 session_id（同一 connection 可能换 session）★★★
                session_id = new_sid

                # ★★★ 如果该 session 之前有 WS，先关闭旧的 ★★★
                conn = connections.get(session_id)
                if conn:
                    old_ws = conn.get("ws")
                    if old_ws and old_ws is not websocket:
                        try:
                            await old_ws.close()
                        except Exception:
                            pass
                    conn["ws"] = websocket
                else:
                    # ★★★ WebSocket 先于 /offer 到达，创建占位记录 ★★★
                    connections[session_id] = {
                        "pc": None,
                        "ws": websocket,
                        "candidate_queue": [],
                        "analysis": {},
                        "video_wrappers": [],
                    }
                    user_id = raw.get("user_id", "")
                    if user_id:
                        connections[session_id]["pending_user_id"] = user_id
                    logger.info(f"创建占位 session [{session_id}]，等待 /offer 到达")
                    conn = connections[session_id]

                logger.info(f"WebSocket connected for session {session_id}")

                # ★★★ 透传前端 userId 到 VideoWrapper（覆盖 interviewId）★★★
                user_id = raw.get("user_id", "")
                if user_id and conn:
                    wrappers = conn.get("video_wrappers", [])
                    if wrappers:
                        for wrapper in wrappers:
                            try:
                                wrapper.set_user_id(user_id)
                            except Exception as e:
                                logger.error(f"透传 userId 到 VideoWrapper 失败: {e}")
                        logger.info(f"已透传 userId={user_id} 到 {len(wrappers)} 个 VideoWrapper")
                    else:
                        # ★★★ video_wrappers 尚未创建，存为 pending，等 track 到来时自动应用 ★★★
                        conn["pending_user_id"] = user_id
                        logger.info(f"video_wrappers 尚未就绪，已暂存 pending_user_id={user_id}")

                await websocket.send_json({
                    "type": "registered", "session_id": session_id
                })

                # ★★★ 发送排队的 ICE 候选 ★★★
                queue = conn.get("candidate_queue", [])
                if queue:
                    logger.info(f"发送 {len(queue)} 个排队的 ICE 候选")
                    for payload in queue:
                        try:
                            await websocket.send_json(payload)
                        except Exception:
                            conn["candidate_queue"].append(payload)
                    conn["candidate_queue"] = []

            elif msg_type == "candidate":
                sid = raw.get("session_id", session_id)
                conn = connections.get(sid)
                if conn and conn.get("pc"):
                    try:
                        candidate_obj = object_from_string(json.dumps(raw))
                        await conn["pc"].addIceCandidate(candidate_obj)
                        # logger.info(f"Added ICE candidate from client for {sid}")
                    except Exception as e:
                        logger.error(f"添加 ICE 候选失败: {e}")

    except WebSocketDisconnect:
        if session_id and session_id in connections:
            connections[session_id]["ws"] = None
            logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if session_id and session_id in connections:
            connections[session_id]["ws"] = None


async def server(pc, offer, session_id):
    video_wrappers = []

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState} [{session_id}]")
        if pc.connectionState in ("failed", "closed"):
            for wrapper in video_wrappers:
                await wrapper.cleanup()
            await pc.close()
            pcs.discard(pc)
            if session_id in connections:
                del connections[session_id]

    @pc.on("icegatheringstatechange")
    async def on_ice_gathering_state_change():
        if pc.iceGatheringState == "complete":
            try:
                candidates = []
                for transceiver in pc.getTransceivers():
                    sender = getattr(transceiver, 'sender', None)
                    if sender is None:
                        continue
                    transport = getattr(sender, 'transport', None)
                    if transport is None:
                        continue
                    ice_gatherer = getattr(
                        transport.transport, 'iceGatherer', None)
                    if ice_gatherer is None:
                        continue
                    for cand in ice_gatherer.getLocalCandidates():
                        cand.sdpMid = transceiver.mid
                        candidates.append(cand)

                for cand in candidates:
                    msg = object_to_string(cand)
                    payload = json.loads(msg)
                    await send_or_queue_candidate(session_id, payload)
            except Exception as e:
                logger.error(f"ICE gathering 完成但发送失败: {e}")

    @pc.on("track")
    def on_track(track):
        logger.info(f"收到 track: kind={track.kind} id={track.id}")
        if track.kind == "video":
            async def _sender(payload: dict):
                await send_analysis_result(session_id, payload)

            analysis_config = connections.get(
                session_id, {}).get("analysis", {})
            t = VideoWrapper(
                track,
                result_sender=_sender,
                session_id=session_id,
                analysis_config=analysis_config
            )
            video_wrappers.append(t)
            # ★★★ 同步存入 connections 供 WS register 透传 userId ★★★
            conn = connections.get(session_id)
            if conn:
                conn.setdefault("video_wrappers", []).append(t)
                # ★★★ 检查是否有 pending 的 userId，立即应用 ★★★
                pending_uid = conn.get("pending_user_id", "")
                if pending_uid:
                    try:
                        t.set_user_id(pending_uid)
                        logger.info(f"已从 pending 应用 userId={pending_uid} 到新创建的 VideoWrapper")
                    except Exception as e:
                        logger.error(f"应用 pending userId 失败: {e}")
            pc.addTrack(t)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)


# ==================== FastAPI 应用 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（替代已弃用的 @app.on_event）"""
    logger.info("Application startup complete")
    yield
    # shutdown
    logger.info("Shutting down...")
    for pc in pcs.copy():
        try:
            await pc.close()
        except Exception:
            pass
    pcs.clear()
    connections.clear()


def create_app():
    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ★★★ 根路径 → 前端页面 ★★★
    @app.get("/")
    async def index():
        html_path = os.path.join(_BASE_DIR, "test_webrtc_simple.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return {"error": "前端页面未找到"}

    @app.post("/offer")
    async def offer_endpoint(params: dict):
        return await offer(params)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        return await websocket_handler(websocket)

    return app


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8081,
        help="Port for HTTP server (default: 8081)"
    )
    args = parser.parse_args()

    app = create_app()

    print("\n" + "=" * 60)
    print("  WebRTC 多模态实时分析服务")
    print("=" * 60)
    print(f"  🌐 前端页面: http://localhost:{args.port}/")
    print(f"  📡 WebSocket: ws://localhost:{args.port}/ws")
    print(f"  🔌 Offer:     POST http://localhost:{args.port}/offer")
    print("=" * 60 + "\n")

    uvicorn.run(app, host=args.host, port=args.port)
