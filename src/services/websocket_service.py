# -*- coding: utf-8 -*-
"""WebSocket 服务模块。

提供 WebSocket 客户端连接和消息处理功能。
"""

import asyncio
import json
from typing import Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol

from utils import logger


class WebSocketService:
    """WebSocket 服务类。
    
    提供 WebSocket 连接管理和消息收发功能。
    """
    
    def __init__(self):
        """初始化 WebSocket 服务。"""
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.receive_task: Optional[asyncio.Task] = None
        self.on_message_callback: Optional[Callable[[str], None]] = None
        self.on_error_callback: Optional[Callable[[str], None]] = None
        self.on_close_callback: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_message: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_close: Optional[Callable] = None
    ):
        """设置回调函数。
        
        Args:
            on_message: 接收消息时的回调函数
            on_error: 发生错误时的回调函数
            on_close: 连接关闭时的回调函数
        """
        self.on_message_callback = on_message
        self.on_error_callback = on_error
        self.on_close_callback = on_close
    
    async def connect(self, url: str, headers: Optional[dict] = None) -> tuple[bool, str]:
        """连接到 WebSocket 服务器。
        
        Args:
            url: WebSocket URL (ws:// 或 wss://)
            headers: 可选的请求头
            
        Returns:
            (是否成功, 消息)
        """
        if self.is_connected:
            return False, "已经连接，请先断开"
        
        # 验证 URL
        if not url.startswith(('ws://', 'wss://')):
            return False, "URL 必须以 ws:// 或 wss:// 开头"
        
        try:
            # 连接到 WebSocket 服务器
            extra_headers = headers if headers else {}
            self.websocket = await websockets.connect(
                url,
                extra_headers=extra_headers,
                ping_interval=20,
                ping_timeout=10,
            )
            
            self.is_connected = True
            
            # 启动接收消息的任务
            self.receive_task = asyncio.create_task(self._receive_messages())
            
            logger.info(f"WebSocket 连接成功: {url}")
            return True, f"连接成功: {url}"
            
        except websockets.exceptions.InvalidURI:
            return False, "无效的 WebSocket URL"
        except websockets.exceptions.InvalidHandshake:
            return False, "握手失败，请检查 URL 和服务器状态"
        except ConnectionRefusedError:
            return False, "连接被拒绝，服务器可能未运行"
        except Exception as e:
            logger.error(f"WebSocket 连接错误: {e}")
            return False, f"连接失败: {str(e)}"
    
    async def _receive_messages(self):
        """接收消息的后台任务。"""
        try:
            async for message in self.websocket:
                if self.on_message_callback:
                    # 在主线程中调用回调
                    try:
                        self.on_message_callback(message)
                    except Exception as e:
                        logger.error(f"消息回调错误: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket 连接已关闭")
            self.is_connected = False
            if self.on_close_callback:
                try:
                    self.on_close_callback()
                except Exception as e:
                    logger.error(f"关闭回调错误: {e}")
                    
        except Exception as e:
            logger.error(f"接收消息错误: {e}")
            self.is_connected = False
            if self.on_error_callback:
                try:
                    self.on_error_callback(f"接收消息错误: {str(e)}")
                except Exception as e:
                    logger.error(f"错误回调错误: {e}")
    
    async def send_message(self, message: str) -> tuple[bool, str]:
        """发送消息。
        
        Args:
            message: 要发送的消息
            
        Returns:
            (是否成功, 消息)
        """
        if not self.is_connected or not self.websocket:
            return False, "未连接到服务器"
        
        try:
            await self.websocket.send(message)
            return True, "发送成功"
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            return False, "连接已关闭"
        except Exception as e:
            logger.error(f"发送消息错误: {e}")
            return False, f"发送失败: {str(e)}"
    
    async def disconnect(self) -> tuple[bool, str]:
        """断开连接。
        
        Returns:
            (是否成功, 消息)
        """
        if not self.is_connected:
            return False, "未连接"
        
        try:
            # 取消接收任务
            if self.receive_task:
                self.receive_task.cancel()
                try:
                    await self.receive_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭 WebSocket 连接
            if self.websocket:
                await self.websocket.close()
            
            self.is_connected = False
            self.websocket = None
            
            logger.info("WebSocket 连接已断开")
            return True, "已断开连接"
            
        except Exception as e:
            logger.error(f"断开连接错误: {e}")
            return False, f"断开失败: {str(e)}"
    
    def validate_json(self, text: str) -> tuple[bool, str]:
        """验证 JSON 格式。
        
        Args:
            text: 要验证的文本
            
        Returns:
            (是否有效, 错误消息或格式化后的 JSON)
        """
        try:
            obj = json.loads(text)
            formatted = json.dumps(obj, ensure_ascii=False, indent=2)
            return True, formatted
        except json.JSONDecodeError as e:
            return False, f"JSON 格式错误: {str(e)}"

