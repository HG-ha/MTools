# -*- coding: utf-8 -*-
"""MCP 工具处理器注册表，供 mtools_run 统一调度。"""

from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, Callable[..., str]] = {}


def register_handler(name: str, handler: Callable[..., str]) -> None:
    _REGISTRY[name] = handler


def get_handler(name: str) -> Callable[..., str] | None:
    return _REGISTRY.get(name)


def call_handler(name: str, **kwargs: Any) -> str:
    handler = _REGISTRY.get(name)
    if handler is None:
        from mcp_server.helpers import fail
        return fail(f"未注册的 MCP 工具: {name}")
    return handler(**kwargs)
