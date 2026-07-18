# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field

from mcp_server.action_guides import TOOL_GUIDES
from mcp_server.handlers import call_handler
from mcp_server.helpers import fail, ok
from mcp_server.schema_types import atomic_tool_name
from mcp_server.tool_ids import TOOL_ID_MAP

ToolId = Literal[tuple(sorted(TOOL_ID_MAP.keys()))]  # type: ignore[valid-type]

_TOOL_ID_DESC = (
    "桌面版工具 ID，共 63 项。例: image.compress, video.convert, video.ts_merge。"
    "完整列表请调 mtools_tool_ids；参数说明请调 mtools_help(tool_id)。"
    "也可直接调用原子工具如 mtools_image_compress（参数更少、schema 更清晰）。"
)


def register(mcp) -> None:
    @mcp.tool()
    def mtools_run(
        tool_id: Annotated[ToolId, Field(description=_TOOL_ID_DESC)],
        params_json: Annotated[
            str,
            Field(
                description=(
                    "JSON 参数字符串。调用前用 mtools_help(tool_id) 查看 required_params 与 example。"
                    '例: {"input_path":"C:/a.jpg","quality":"high"}'
                ),
                examples=['{"input_path": "C:/photos/a.jpg", "quality": "high"}'],
            ),
        ] = "{}",
    ) -> str:
        """统一入口：按 tool_id 执行任意 MTools 能力。

        推荐优先使用同名原子工具（如 mtools_image_compress），schema 更清晰。
        本工具适合已知道参数结构的批量调用。
        """
        if tool_id not in TOOL_ID_MAP:
            return fail(f"未知 tool_id: {tool_id}")
        mcp_tool, action = TOOL_ID_MAP[tool_id]
        try:
            params = json.loads(params_json) if params_json.strip() else {}
            if not isinstance(params, dict):
                return fail("params_json 必须是 JSON 对象")
        except json.JSONDecodeError as exc:
            return fail(f"params_json 解析失败: {exc}")

        params["action"] = action
        if tool_id == "dev.encoding" and params.get("encoding_action") == "convert":
            params["action"] = "encoding_convert"
        if tool_id == "dev.json_viewer" and params.get("json_action") == "minify":
            params["action"] = "json_minify"
        if tool_id == "dev.websocket_client":
            mcp_tool = "mtools_websocket"
            if "ws_action" in params:
                params["action"] = params.pop("ws_action")
        return call_handler(mcp_tool, **params)

    @mcp.tool()
    def mtools_tool_ids() -> str:
        """返回全部 tool_id、原子 MCP 工具名、默认 action。"""
        items = [
            {
                "tool_id": k,
                "atomic_tool": atomic_tool_name(k),
                "mcp_tool": v[0],
                "action": v[1],
                "summary": TOOL_GUIDES.get(k, {}).get("summary", ""),
            }
            for k, v in sorted(TOOL_ID_MAP.items())
        ]
        return ok({"count": len(items), "tools": items, "hint": "优先调用 atomic_tool 列出的工具名"})
