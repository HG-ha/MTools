# -*- coding: utf-8 -*-
"""MTools 内置 MCP 服务模块。"""

from .app import configure_server, mcp
from .runtime import init_runtime

__all__ = ["mcp", "configure_server", "init_runtime"]
