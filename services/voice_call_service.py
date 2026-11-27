"""
voice_call_service.py - 学伴语音通话服务

管理通话房间状态、通话记录存储。
信令通过 api_server.py 中的 WebSocket 端点实现。
"""

import sqlite3
import uuid
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "recommendation_data" / "companion.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_voice_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voice_call_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id         TEXT NOT NULL,
            caller_id       TEXT NOT NULL,
            callee_id       TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'initiated',
            duration_sec    REAL DEFAULT 0,
            started_at      TEXT,
            ended_at        TEXT,
            created_at      TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


_init_voice_db()


class VoiceCallRoom:
    """一个语音通话房间，管理两个用户之间的通话状态"""

    def __init__(self, room_id: str, caller_id: str, callee_id: str):
        self.room_id = room_id
        self.caller_id = caller_id
        self.callee_id = callee_id
        self.status = "initiated"  # initiated -> ringing -> connected -> ended
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.ended_at: Optional[str] = None
        # caller/callee 的 WebSocket 连接
        self.caller_ws = None
        self.callee_ws = None
        # caller/callee 的 SDP offer/answer
        self.caller_sdp: Optional[dict] = None
        self.callee_sdp: Optional[dict] = None
        # ICE candidates 暂存
        self.caller_candidates: list = []
        self.callee_candidates: list = []


class VoiceCallManager:
    """管理所有语音通话房间"""

    def __init__(self):
        self._rooms: Dict[str, VoiceCallRoom] = {}
        self._user_rooms: Dict[str, str] = {}  # user_id -> room_id (用户当前所在房间)
        self._user_ws: Dict[str, any] = {}  # user_id -> WebSocket (用户在线连接)
        self._lock = asyncio.Lock()
        self._ring_timeout_tasks: Dict[str, asyncio.Task] = {}  # room_id -> asyncio task

    async def start_ring_timeout(self, room_id: str, timeout_sec: int = 30, on_timeout=None):
        """启动响铃超时，超时后自动结束通话

        Args:
            room_id: 通话房间ID
            timeout_sec: 超时秒数
            on_timeout: 超时回调函数，异步函数，接收参数 (room_id, caller_id, callee_id)
        """
        async def _on_timeout():
            await asyncio.sleep(timeout_sec)
            async with self._lock:
                room = self._rooms.get(room_id)
                if room and room.status in ("initiated", "ringing"):
                    caller_id = room.caller_id
                    callee_id = room.callee_id
                    # 结束通话
                    room.status = "ended"
                    room.ended_at = datetime.now().isoformat()
                    # 清理用户房间映射
                    self._user_rooms.pop(caller_id, None)
                    self._user_rooms.pop(callee_id, None)
                    # 更新数据库
                    conn = _get_conn()
                    conn.execute(
                        "UPDATE voice_call_history SET status='no_answer', ended_at=? WHERE room_id=?",
                        (room.ended_at, room_id),
                    )
                    conn.commit()
                    conn.close()
                    # 调用回调通知双方
                    if on_timeout:
                        await on_timeout(room_id, caller_id, callee_id)

        task = asyncio.create_task(_on_timeout())
        self._ring_timeout_tasks[room_id] = task

    def cancel_ring_timeout(self, room_id: str):
        """取消响铃超时"""
        task = self._ring_timeout_tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def register_user_ws(self, user_id: str, ws):
        """注册用户 WebSocket 连接（用户上线时调用）"""
        self._user_ws[user_id] = ws

    def unregister_user_ws(self, user_id: str, ws=None):
        """注销用户 WebSocket 连接（用户下线时调用）

        Args:
            user_id: 用户ID
            ws: 要注销的 WebSocket 对象，如果提供且与当前注册的不一致则不注销
        """
        if ws is not None:
            current = self._user_ws.get(user_id)
            if current is not ws:
                # 当前注册的不是这个 WS（多标签页情况），不注销
                return
        self._user_ws.pop(user_id, None)

    def get_user_ws(self, user_id: str):
        """获取用户的 WebSocket 连接"""
        return self._user_ws.get(user_id)

    async def create_room(self, caller_id: str, callee_id: str) -> VoiceCallRoom:
        async with self._lock:
            # 检查是否已有进行中的通话
            if caller_id in self._user_rooms:
                raise ValueError(f"用户 {caller_id} 已在通话中")
            if callee_id in self._user_rooms:
                raise ValueError(f"用户 {callee_id} 已在通话中")

            room_id = f"call_{uuid.uuid4().hex[:12]}"
            room = VoiceCallRoom(room_id, caller_id, callee_id)
            self._rooms[room_id] = room
            self._user_rooms[caller_id] = room_id
            self._user_rooms[callee_id] = room_id

            # 记录到数据库
            conn = _get_conn()
            conn.execute(
                "INSERT INTO voice_call_history (room_id, caller_id, callee_id, status, created_at) VALUES (?,?,?,?,?)",
                (room_id, caller_id, callee_id, "initiated", room.created_at),
            )
            conn.commit()
            conn.close()
            return room

    def get_room(self, room_id: str) -> Optional[VoiceCallRoom]:
        return self._rooms.get(room_id)

    def get_user_room(self, user_id: str) -> Optional[VoiceCallRoom]:
        room_id = self._user_rooms.get(user_id)
        if room_id:
            return self._rooms.get(room_id)
        return None

    def set_caller_ws(self, room_id: str, ws):
        room = self._rooms.get(room_id)
        if room:
            room.caller_ws = ws

    def set_callee_ws(self, room_id: str, ws):
        room = self._rooms.get(room_id)
        if room:
            room.callee_ws = ws

    def get_peer_ws(self, room_id: str, user_id: str):
        """获取对方的 WebSocket"""
        room = self._rooms.get(room_id)
        if not room:
            return None
        if user_id == room.caller_id:
            return room.callee_ws
        elif user_id == room.callee_id:
            return room.caller_ws
        return None

    def update_status(self, room_id: str, status: str):
        room = self._rooms.get(room_id)
        if not room:
            return
        room.status = status
        now = datetime.now().isoformat()

        if status == "connected":
            room.started_at = now
        elif status == "ended":
            room.ended_at = now

        conn = _get_conn()
        if status == "connected":
            conn.execute(
                "UPDATE voice_call_history SET status=?, started_at=? WHERE room_id=?",
                (status, now, room_id),
            )
        elif status == "ended":
            duration = 0
            if room.started_at:
                try:
                    t0 = datetime.fromisoformat(room.started_at)
                    t1 = datetime.fromisoformat(now)
                    duration = (t1 - t0).total_seconds()
                except Exception:
                    pass
            conn.execute(
                "UPDATE voice_call_history SET status=?, ended_at=?, duration_sec=? WHERE room_id=?",
                (status, now, duration, room_id),
            )
        else:
            conn.execute(
                "UPDATE voice_call_history SET status=? WHERE room_id=?",
                (status, room_id),
            )
        conn.commit()
        conn.close()

    async def end_call(self, room_id: str):
        """结束通话并清理房间"""
        room = self._rooms.get(room_id)
        if not room:
            return
        self.update_status(room_id, "ended")
        async with self._lock:
            self._user_rooms.pop(room.caller_id, None)
            self._user_rooms.pop(room.callee_id, None)
            self._rooms.pop(room_id, None)

    async def reject_call(self, room_id: str):
        """拒绝通话"""
        self.update_status(room_id, "rejected")
        room = self._rooms.get(room_id)
        if room:
            async with self._lock:
                self._user_rooms.pop(room.caller_id, None)
                self._user_rooms.pop(room.callee_id, None)
                self._rooms.pop(room_id, None)

    def get_call_history(self, user_id: str, limit: int = 20) -> list:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT * FROM voice_call_history
               WHERE caller_id = ? OR callee_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, user_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# 全局单例
voice_call_manager = VoiceCallManager()
