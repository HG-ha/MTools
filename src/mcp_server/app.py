# -*- coding: utf-8 -*-
"""MTools 内置 MCP 服务入口。"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from mcp_server import (
    register_atomic,
    register_core,
    register_dev,
    register_dispatch,
    register_image,
    register_media,
    register_others,
    register_websocket,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STREAMABLE_HTTP_PATH = "/mcp"

# host/port 在 MCP 2.x 里不再属于服务器构造参数，启动 HTTP 时再使用。
_bind_host = DEFAULT_HOST
_bind_port = DEFAULT_PORT

mcp = MCPServer(
    "MTools",
    instructions=(
        "MTools MCP — 桌面版 65 项工具能力（不含 Markdown 查看器）。\n\n"
        "【AI 调用规范 — 请严格遵守】\n"
        "1. 优先使用原子工具（mtools_image_compress、mtools_video_convert 等），"
        "每个工具只有该场景需要的参数，JSON Schema 含 description。\n"
        "2. 不确定参数时：mtools_help('image.compress') 查看必填项与 example。\n"
        "3. 查全部能力：mtools_tool_ids()。\n"
        "4. 统一入口：mtools_run(tool_id, params_json)（备选）。\n"
        "5. WebSocket：mtools_websocket，流程 connect→send→receive→disconnect，用 session_id 保持会话。\n"
        "6. 文件路径必须是用户本机绝对路径；AI/ONNX 需用户先在 MTools 下载模型。\n"
        "7. 返回 JSON 字符串，检查 ok 字段判断成功与否。"
    ),
    log_level="WARNING",
)


def get_bind() -> tuple[str, int]:
    return _bind_host, _bind_port


def configure_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> MCPServer:
    global _bind_host, _bind_port
    _bind_host = host
    _bind_port = port
    return mcp


def get_endpoint_url(host: str | None = None, port: int | None = None) -> str:
    h = host or _bind_host
    p = port or _bind_port
    return f"http://{h}:{p}{STREAMABLE_HTTP_PATH}"


def create_asgi_app():
    """构建 Streamable HTTP 应用。本机地址会打开 DNS 重绑定防护。"""
    return mcp.streamable_http_app(
        streamable_http_path=STREAMABLE_HTTP_PATH,
        host=_bind_host,
    )


def _register_all() -> None:
    # 内部 handler（供 mtools_run / 原子工具调度，不对外暴露大工具）
    register_image.register_handlers_only()
    register_media.register_handlers_only()
    register_dev.register_handlers_only()
    register_others.register_handlers_only()

    register_core.register(mcp, get_endpoint_url)
    register_atomic.register(mcp)
    register_media.register_subtitle_only(mcp)
    register_others.register_ai_subtitle_only(mcp)
    register_websocket.register(mcp)
    register_dispatch.register(mcp)


_register_all()
