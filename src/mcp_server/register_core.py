# -*- coding: utf-8 -*-
import json

from mcp_server.action_guides import get_help
from mcp_server.capabilities import CAPABILITIES, all_tool_count
from mcp_server.helpers import ok
from mcp_server.runtime import get_config_service, get_ffmpeg_service, get_models_dir, get_output_dir


def register(mcp, get_endpoint_url) -> None:
    @mcp.tool()
    def mtools_status() -> str:
        """检查 MTools MCP 运行环境。"""
        cfg = get_config_service()
        ffmpeg = get_ffmpeg_service()
        available, msg = ffmpeg.is_ffmpeg_available()
        return ok({
            "data_dir": str(cfg.get_data_dir()),
            "output_dir": str(get_output_dir()),
            "models_dir": str(get_models_dir()),
            "ffmpeg_available": available,
            "ffmpeg_message": msg,
            "ffmpeg_path": ffmpeg.get_ffmpeg_path() or "",
            "endpoint": get_endpoint_url(),
            "tool_count": all_tool_count(),
        })

    @mcp.tool()
    def mtools_list_capabilities() -> str:
        """列出 MTools 全部 MCP 能力分类。查具体参数请用 mtools_help(tool_id)。"""
        return ok({
            "capabilities": CAPABILITIES,
            "total_tools": all_tool_count(),
            "hint": "调用 mtools_help() 查看推荐用法；mtools_help('image.compress') 查看参数与示例",
        })

    @mcp.tool()
    def mtools_help(tool_id: str = "") -> str:
        """查询工具调用说明：必填/可选参数、示例、注意事项。

        不带 tool_id：返回总体用法与规范。
        带 tool_id（如 image.compress）：返回该工具的参数说明与 call_example。
        AI Agent 应在首次调用某工具前先查此接口。
        """
        return json.dumps(get_help(tool_id), ensure_ascii=False, indent=2)
