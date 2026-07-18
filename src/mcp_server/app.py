# -*- coding: utf-8 -*-
"""MTools 内置 MCP 服务入口。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

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

mcp = FastMCP(
    "MTools",
    instructions=(
        "MTools MCP — 桌面版 63 项工具能力（不含 Markdown 查看器）。\n\n"
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
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    log_level="WARNING",
)


def configure_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> FastMCP:
    mcp.settings.host = host
    mcp.settings.port = port
    return mcp


def get_endpoint_url(host: str | None = None, port: int | None = None) -> str:
    h = host or mcp.settings.host
    p = port or mcp.settings.port
    return f"http://{h}:{p}{mcp.settings.streamable_http_path}"


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
