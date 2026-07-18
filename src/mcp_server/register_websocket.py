# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field

from mcp_server.handlers import register_handler
from mcp_server.helpers import fail, ok
from mcp_server.websocket_manager import WebSocketSessionManager


def register(mcp) -> None:
    def mtools_websocket(
        action: Annotated[
            Literal["connect", "send", "receive", "status", "disconnect", "list_sessions", "disconnect_all"],
            Field(description="操作：connect 建连 / send 发送 / receive 收消息 / status 状态 / disconnect 断开"),
        ],
        url: Annotated[str, Field(default="", description="WebSocket 地址 ws:// 或 wss://（connect 时必填）")] = "",
        session_id: Annotated[str, Field(default="", description="connect 返回的会话 ID，后续 send/receive 等需传入")] = "",
        message: Annotated[str, Field(default="", description="要发送的文本消息（send 时必填）")] = "",
        headers_json: Annotated[str, Field(default="{}", description="connect 时的请求头 JSON 对象字符串")] = "{}",
        max_messages: Annotated[int, Field(default=20, description="receive 时最多返回的消息条数")] = 20,
        clear_buffer: Annotated[bool, Field(default=True, description="receive 后是否清空缓冲区")] = True,
    ) -> str:
        """WebSocket 客户端 — 完整生命周期管理（会话跨多次调用保持）。

        典型流程:
          1. connect(url) -> 返回 session_id
          2. send(session_id, message) -> 发送消息
          3. receive(session_id) -> 拉取服务端推送的消息
          4. status(session_id) -> 查看连接状态
          5. disconnect(session_id) -> 断开并销毁会话

        list_sessions: 列出所有活跃会话
        disconnect_all: 断开全部会话
        """
        try:
            mgr = WebSocketSessionManager.get()

            if action == "connect":
                if not url.strip():
                    return fail("connect 需要 url（ws:// 或 wss://）")
                headers = json.loads(headers_json) if headers_json.strip() else {}
                if not isinstance(headers, dict):
                    return fail("headers_json 必须是 JSON 对象")
                sid, ok_conn, msg = mgr.connect(url.strip(), headers)
                if not ok_conn:
                    return fail(msg)
                return ok({"session_id": sid, "message": msg, "url": url.strip()})

            if action == "list_sessions":
                return ok({"sessions": mgr.list_sessions(), "count": len(mgr.list_sessions())})

            if action == "disconnect_all":
                count = mgr.disconnect_all()
                return ok({"disconnected": count})

            if not session_id.strip():
                return fail("需要 session_id（先 connect 获取）")

            session = mgr.get_session(session_id.strip())
            if not session:
                return fail(f"会话不存在或已断开: {session_id}")

            if action == "send":
                if not message:
                    return fail("send 需要 message")
                ok_send, msg = session.send(message)
                return ok({"message": msg}) if ok_send else fail(msg)

            if action == "receive":
                messages = session.receive(max_messages=max_messages, clear=clear_buffer)
                return ok({"messages": messages, "count": len(messages)})

            if action == "status":
                return ok(session.status())

            if action == "disconnect":
                ok_disc, msg = mgr.disconnect(session_id.strip())
                return ok({"message": msg}) if ok_disc else fail(msg)

            return fail(f"未知 action: {action}")
        except json.JSONDecodeError as exc:
            return fail(f"headers_json 解析失败: {exc}")
        except Exception as exc:
            return fail(str(exc))

    mcp.tool()(mtools_websocket)
    register_handler("mtools_websocket", mtools_websocket)
