# -*- coding: utf-8 -*-
"""MTools 内置 MCP 服务生命周期管理。"""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time
from typing import Optional, Tuple

from utils import logger

from .config_service import ConfigService

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
# 配置的端口被占用时，最多往后尝试这么多个端口。
PORT_SCAN_LIMIT = 20


class _NoExitSys:
    """给 Uvicorn 用的 sys 代理，``exit`` 只抛 ``SystemExit``。

    打包后的 Flet 把 ``sys.exit`` 换成直接结束整个进程。Uvicorn 出错时会调用
    ``sys.exit(1)``，如果不拦住，MCP 启动失败会把窗口一起关掉。
    """

    def __getattr__(self, name: str):
        return getattr(sys, name)

    @staticmethod
    def exit(code: int = 0) -> None:
        raise SystemExit(code)


def _guard_uvicorn_exit() -> None:
    import uvicorn.config
    import uvicorn.server

    for module in (uvicorn.config, uvicorn.server):
        if not isinstance(getattr(module, "sys", None), _NoExitSys):
            module.sys = _NoExitSys()


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
        self._requested_host: Optional[str] = None
        self._requested_port: Optional[int] = None
        self._bound_port: Optional[int] = None

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
        """配置里的端口（用户希望使用的端口）。"""
        return int(self.config_service.get_config_value("mcp_port", DEFAULT_PORT))

    def get_bound_port(self) -> Optional[int]:
        """实际监听的端口。服务未运行时为 None。"""
        return self._bound_port if self.is_running else None

    def get_port_fallback_note(self) -> Optional[str]:
        """配置端口被占用、自动改用其他端口时返回提示文字。"""
        bound = self.get_bound_port()
        if bound is None or self._requested_port is None or bound == self._requested_port:
            return None
        return f"端口 {self._requested_port} 被占用，已自动改用 {bound}"

    def get_endpoint_url(self) -> str:
        from mcp_server.app import get_endpoint_url

        bound = self.get_bound_port()
        if bound is not None:
            return get_endpoint_url(self._requested_host or self.get_host(), bound)
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

            host = self.get_host()
            requested_port = self.get_port()
            try:
                sock, port = self._bind_available_port(host, requested_port)
            except OSError as exc:
                last_port = min(requested_port + PORT_SCAN_LIMIT - 1, 65535)
                self._error_message = (
                    f"端口 {requested_port}-{last_port} 都无法绑定: {exc}"
                )
                logger.error("MCP 服务启动失败: %s", self._error_message)
                return False, self._error_message

            if port != requested_port:
                logger.warning("MCP 端口 %s 被占用，已自动改用 %s", requested_port, port)

            try:
                from mcp_server import configure_server, init_runtime

                init_runtime(self.config_service)
                configure_server(host, port)
            except Exception as exc:
                sock.close()
                self._error_message = str(exc)
                return False, self._error_message

            self._requested_host = host
            self._requested_port = requested_port
            self._bound_port = port
            self._thread = threading.Thread(
                target=self._run_server,
                args=(sock,),
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
            self._bound_port = None
            self._started_event.clear()

    def restart(self) -> Tuple[bool, str]:
        """重启 MCP 服务。"""
        self.stop()
        return self.start()

    def sync_with_config(self) -> Tuple[bool, str]:
        """根据当前配置启停服务。"""
        if self.config_service.get_config_value("mcp_enabled", False):
            if self.is_running:
                # 和启动时“想要的”端口比，而不是实际端口，
                # 否则自动顺延后每次同步都会重启。
                if (
                    self._requested_port != self.get_port()
                    or self._requested_host != self.get_host()
                ):
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

    @staticmethod
    def _bind_server_socket(host: str, port: int) -> socket.socket:
        """绑定并监听一个端口，失败时抛 OSError。"""
        ipv6 = ":" in host
        family = socket.AF_INET6 if ipv6 else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            if ipv6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            # Windows 上 SO_REUSEADDR 会让已被占用的端口也绑定成功，
            # 这里不设置，才能发现冲突。
            sock.bind((host.strip("[]"), port))
            sock.listen(2048)
            sock.setblocking(False)
            return sock
        except Exception:
            sock.close()
            raise

    @classmethod
    def _bind_available_port(cls, host: str, port: int) -> Tuple[socket.socket, int]:
        """从配置端口开始往后找第一个能绑定的端口。"""
        last_error: Optional[OSError] = None
        for candidate in range(port, min(port + PORT_SCAN_LIMIT, 65536)):
            try:
                return cls._bind_server_socket(host, candidate), candidate
            except OSError as exc:
                last_error = exc
        raise last_error or OSError(f"端口 {port} 无效")

    def _run_server(self, sock: socket.socket) -> None:
        import uvicorn

        from mcp_server.app import create_asgi_app, get_bind

        _guard_uvicorn_exit()

        async def serve() -> None:
            host, port = get_bind()
            app = create_asgi_app()
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="warning",
            )
            self._uvicorn_server = uvicorn.Server(config)
            self._started_event.set()
            try:
                await self._uvicorn_server.serve(sockets=[sock])
            finally:
                self._started_event.clear()
                self._uvicorn_server = None

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(serve())
        except SystemExit as exc:
            self._error_message = f"MCP 服务意外退出 (exit {exc.code})"
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
            try:
                sock.close()
            except Exception:
                pass
