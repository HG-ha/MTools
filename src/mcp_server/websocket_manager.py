# -*- coding: utf-8 -*-
"""MCP WebSocket 会话管理 — 跨多次 tool 调用保持连接与消息缓冲。"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from services.websocket_service import WebSocketService
from utils import logger


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class WebSocketSession:
    """单个 WebSocket 连接会话（独立 asyncio 事件循环线程）。"""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.url = ""
        self._service = WebSocketService()
        self._incoming: Deque[dict[str, Any]] = deque(maxlen=500)
        self._outgoing: Deque[dict[str, Any]] = deque(maxlen=500)
        self._events: Deque[dict[str, Any]] = deque(maxlen=100)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._closed = False
        self._lock = threading.Lock()

        self._service.set_callbacks(
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    @property
    def is_connected(self) -> bool:
        return self._service.is_connected and not self._closed

    def _ensure_loop_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._started.clear()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"WsSession-{self.session_id[:8]}",
            daemon=True,
        )
        self._thread.start()
        if not self._started.wait(timeout=5.0):
            raise RuntimeError("WebSocket 事件循环启动超时")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._started.set()
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    def _run_coro(self, coro, timeout: float = 30.0):
        self._ensure_loop_thread()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _append_event(self, event: str, detail: str = "") -> None:
        with self._lock:
            self._events.append({"time": _utc_now(), "event": event, "detail": detail})

    def _on_message(self, message: str) -> None:
        with self._lock:
            self._incoming.append({"time": _utc_now(), "direction": "in", "data": message})
        self._append_event("message_received")

    def _on_error(self, error: str) -> None:
        self._append_event("error", error)

    def _on_close(self) -> None:
        self._append_event("closed")
        self._closed = True

    def connect(self, url: str, headers: Optional[dict] = None) -> tuple[bool, str]:
        if self.is_connected:
            return False, "会话已连接，请先 disconnect"
        self._closed = False
        ok, msg = self._run_coro(self._service.connect(url, headers))
        if ok:
            self.url = url
            self._append_event("connected", url)
        return ok, msg

    def send(self, message: str) -> tuple[bool, str]:
        if not self.is_connected:
            return False, "未连接"
        ok, msg = self._run_coro(self._service.send_message(message))
        if ok:
            with self._lock:
                self._outgoing.append({"time": _utc_now(), "direction": "out", "data": message})
        return ok, msg

    def receive(self, max_messages: int = 20, clear: bool = True) -> List[dict[str, Any]]:
        with self._lock:
            items = list(self._incoming)
            if clear:
                self._incoming.clear()
        return items[-max_messages:] if max_messages > 0 else items

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "url": self.url,
                "connected": self.is_connected,
                "pending_incoming": len(self._incoming),
                "sent_count": len(self._outgoing),
                "recent_events": list(self._events)[-10:],
            }

    def disconnect(self) -> tuple[bool, str]:
        if not self._service.is_connected and self._closed:
            return True, "已断开"
        try:
            ok, msg = self._run_coro(self._service.disconnect())
            self._closed = True
            self._append_event("disconnected")
            return ok, msg
        except Exception as exc:
            self._closed = True
            return False, str(exc)

    def shutdown(self) -> None:
        try:
            if self._service.is_connected:
                self._run_coro(self._service.disconnect(), timeout=5.0)
        except Exception:
            pass
        self._closed = True
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)


class WebSocketSessionManager:
    """全局 WebSocket 会话池（MCP 进程内单例）。"""

    _instance: Optional["WebSocketSessionManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._sessions: Dict[str, WebSocketSession] = {}

    @classmethod
    def get(cls) -> "WebSocketSessionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def connect(self, url: str, headers: Optional[dict] = None) -> tuple[str, bool, str]:
        session = WebSocketSession(str(uuid.uuid4()))
        ok, msg = session.connect(url, headers)
        if not ok:
            session.shutdown()
            return "", False, msg
        with self._lock:
            self._sessions[session.session_id] = session
        logger.info("MCP WebSocket 会话已创建: %s -> %s", session.session_id, url)
        return session.session_id, True, msg

    def get_session(self, session_id: str) -> Optional[WebSocketSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def disconnect(self, session_id: str) -> tuple[bool, str]:
        session = self.get_session(session_id)
        if not session:
            return False, f"会话不存在: {session_id}"
        ok, msg = session.disconnect()
        session.shutdown()
        with self._lock:
            self._sessions.pop(session_id, None)
        return ok, msg

    def disconnect_all(self) -> int:
        with self._lock:
            ids = list(self._sessions.keys())
        count = 0
        for sid in ids:
            ok, _ = self.disconnect(sid)
            if ok:
                count += 1
        return count

    def list_sessions(self) -> List[dict[str, Any]]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [s.status() for s in sessions]
