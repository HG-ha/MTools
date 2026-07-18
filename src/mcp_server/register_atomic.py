# -*- coding: utf-8 -*-
"""为每个 tool_id 注册独立 MCP 工具（精简 schema + 参数 description，供 AI 直接调用）。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from mcp_server.action_guides import TOOL_GUIDES
from mcp_server.handlers import call_handler
from mcp_server.schema_types import PARAM_SPECS, atomic_tool_name
from mcp_server.tool_ids import TOOL_ID_MAP

# 不走原子工具、改用专用 MCP 工具或 GUI
_SKIP_ATOMIC = frozenset({"dev.websocket_client"})


def _param_lines(required: list[str], optional: list[str]) -> list[str]:
    lines = []
    for p in required + optional:
        if p not in PARAM_SPECS:
            continue
        py_type, _, default_repr, desc = PARAM_SPECS[p]
        ann = f"Annotated[{py_type}, Field(description={desc!r})]"
        if p in required:
            lines.append(f"{p}: {ann}")
        else:
            lines.append(f"{p}: {ann} = {default_repr}")
    return lines


def _action_override(tool_id: str, kwargs_var: str = "_kwargs") -> str:
    if tool_id == "dev.encoding":
        return (
            f'    if {kwargs_var}.get("encoding_action") == "convert":\n'
            f'        {kwargs_var}["action"] = "encoding_convert"\n'
        )
    if tool_id == "dev.json_viewer":
        return (
            f'    if {kwargs_var}.get("json_action") == "minify":\n'
            f'        {kwargs_var}["action"] = "json_minify"\n'
        )
    return ""


def _register_one(mcp, tool_id: str) -> None:
    mcp_tool, action = TOOL_ID_MAP[tool_id]
    guide = TOOL_GUIDES.get(tool_id, {})
    required = list(guide.get("required_params", []))
    optional = list(guide.get("optional_params", []))
    all_params = [p for p in required + optional if p in PARAM_SPECS]

    name = atomic_tool_name(tool_id)
    params_sig = ", ".join(_param_lines(required, optional))
    example = guide.get("example", {})
    notes = guide.get("notes", "")
    summary = guide.get("summary", tool_id)
    doc = (
        f"{summary} | tool_id={tool_id} | "
        f"必填={required} | 示例={example}"
        + (f" | 注意={notes}" if notes else "")
    )

    collect = [f"    _kwargs[{p!r}] = {p}" for p in all_params]
    override = _action_override(tool_id)
    body = "\n".join([
        "    _kwargs = {}",
        *collect,
        f"    _kwargs['action'] = {action!r}",
        override.rstrip(),
        f"    return call_handler({mcp_tool!r}, **_kwargs)",
    ])

    code = f"def {name}({params_sig}) -> str:\n{body}\n"
    local: dict = {
        "Annotated": Annotated,
        "Field": Field,
        "Literal": Literal,
        "call_handler": call_handler,
    }
    exec(code, local, local)  # noqa: S102 — globals=locals 以便 FastMCP 解析 Annotated
    fn = local[name]
    fn.__doc__ = doc
    mcp.tool(name=name, description=doc)(fn)


def register(mcp) -> None:
    for tool_id in TOOL_ID_MAP:
        if tool_id in _SKIP_ATOMIC:
            _register_websocket_stub(mcp)
            continue
        if tool_id == "video.screen_record":
            _register_screen_record_stub(mcp)
            continue
        _register_one(mcp, tool_id)


def _register_screen_record_stub(mcp) -> None:
    name = atomic_tool_name("video.screen_record")
    doc = "录屏仅支持 MTools 桌面版 GUI/热键，MCP 不可调用。"

    @mcp.tool(name=name, description=doc)
    def mtools_video_screen_record() -> str:
        from mcp_server.helpers import fail
        return fail("录屏请使用 MTools 桌面版：设置 → 快捷功能 → 屏幕录制")


def _register_websocket_stub(mcp) -> None:
    name = atomic_tool_name("dev.websocket_client")
    doc = "WebSocket 请使用 mtools_websocket（connect/send/receive/disconnect，session_id 保持会话）。"

    @mcp.tool(name=name, description=doc)
    def mtools_dev_websocket_client() -> str:
        from mcp_server.helpers import fail
        return fail("请使用 mtools_websocket，例如 action=connect, url=ws://host:port")
