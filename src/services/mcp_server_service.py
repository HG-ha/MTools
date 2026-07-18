# -*- coding: utf-8 -*-
"""MTools 内置 MCP 服务生命周期管理。"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Optional, Tuple

from utils import logger

from .config_service import ConfigService

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class McpServerService:
    """在 MTools 进程内启动/停止 MCP HTTP 服务。"""

    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service
        self._thread: Optional[threading.Thread] = None
        self._uvicorn_server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started_event = threading.Event()
        self._error_message: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return (
            self._started_event.is_set()
            and self._error_message is None
            and self._thread is not None
            and self._thread.is_alive()
        )

    def get_host(self) -> str:
        return str(self.config_service.get_config_value("mcp_host", DEFAULT_HOST))

    def get_port(self) -> int:
        return int(self.config_service.get_config_value("mcp_port", DEFAULT_PORT))

    def get_endpoint_url(self) -> str:
        from mcp_server.app import get_endpoint_url

        return get_endpoint_url(self.get_host(), self.get_port())

    def get_last_error(self) -> Optional[str]:
        return self._error_message

    def start(self) -> Tuple[bool, str]:
        """若配置已启用则启动 MCP 服务。"""
        with self._lock:
            if not self.config_service.get_config_value("mcp_enabled", False):
                return False, "MCP 服务未启用"

            if self.is_running:
                return True, f"MCP 服务已在运行: {self.get_endpoint_url()}"

            self._error_message = None
            self._started_event.clear()

            from mcp_server import configure_server, init_runtime

            init_runtime(self.config_service)
            configure_server(self.get_host(), self.get_port())

            self._thread = threading.Thread(
                target=self._run_server,
                name="McpServer",
                daemon=True,
            )
            self._thread.start()

        for _ in range(50):
            if self._error_message:
                return False, self._error_message
            if self.is_running:
                return True, f"MCP 服务已启动: {self.get_endpoint_url()}"
            time.sleep(0.1)

        return False, self._error_message or "MCP 服务启动超时"

    def stop(self) -> None:
        """停止 MCP 服务。"""
        try:
            from mcp_server.websocket_manager import WebSocketSessionManager
            WebSocketSessionManager.get().disconnect_all()
        except Exception:
            pass

        with self._lock:
            server = self._uvicorn_server
            loop = self._loop
            thread = self._thread

        if server is not None and loop is not None and loop.is_running():
            async def _shutdown() -> None:
                server.should_exit = True
                await server.shutdown()

            try:
                fut = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
                fut.result(timeout=5.0)
            except Exception:
                server.should_exit = True
                try:
                    loop.call_soon_threadsafe(loop.stop)
                except Exception:
                    pass

        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)

        with self._lock:
            self._thread = None
            self._uvicorn_server = None
            self._loop = None
            self._started_event.clear()

    def restart(self) -> Tuple[bool, str]:
        """重启 MCP 服务。"""
        self.stop()
        return self.start()

    def sync_with_config(self) -> Tuple[bool, str]:
        """根据当前配置启停服务。"""
        if self.config_service.get_config_value("mcp_enabled", False):
            if self.is_running:
                current_port = self.get_port()
                current_host = self.get_host()
                from mcp_server.app import mcp

                if mcp.settings.port != current_port or mcp.settings.host != current_host:
                    return self.restart()
                return True, f"MCP 服务运行中: {self.get_endpoint_url()}"
            return self.start()
        self.stop()
        return False, "MCP 服务已停止"

    @staticmethod
    def _cleanup_loop(loop: asyncio.AbstractEventLoop) -> None:
        try:
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass

    def _run_server(self) -> None:
        import uvicorn

        from mcp_server.app import mcp

        async def serve() -> None:
            app = mcp.streamable_http_app()
            config = uvicorn.Config(
                app,
                host=mcp.settings.host,
                port=mcp.settings.port,
                log_level="warning",
            )
            self._uvicorn_server = uvicorn.Server(config)
            self._started_event.set()
            try:
                await self._uvicorn_server.serve()
            finally:
                self._started_event.clear()
                self._uvicorn_server = None

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(serve())
        except OSError as exc:
            self._error_message = f"端口 {self.get_port()} 无法绑定: {exc}"
            logger.error("MCP 服务启动失败: %s", self._error_message)
            self._started_event.set()
        except Exception as exc:
            self._error_message = str(exc)
            logger.error("MCP 服务异常退出: %s", exc)
            self._started_event.set()
        finally:
            if self._loop is not None and not self._loop.is_closed():
                self._cleanup_loop(self._loop)
                try:
                    self._loop.close()
                except Exception:
                    pass
            self._loop = None
