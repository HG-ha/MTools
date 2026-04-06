# -*- coding: utf-8 -*-
"""WebSocket 客户端视图模块。

提供 WebSocket 连接测试功能。
"""

import asyncio
import json
from datetime import datetime
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL
from services import ConfigService
from utils import logger


class WebSocketClientView(ft.Container):
    """WebSocket 客户端视图类。
    
    提供 WebSocket 连接和消息收发测试功能。
    """
    
    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        on_back: Optional[Callable] = None
    ):
        """初始化 WebSocket 客户端视图。
        
        Args:
            page: Flet 页面对象
            config_service: 配置服务实例（可选）
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self._page = page
        self.config_service = config_service
        self.on_back = on_back
        self.expand = True
        self.padding = ft.Padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 导入 WebSocket 服务
        from services.websocket_service import WebSocketService
        self.ws_service = WebSocketService()
        
        # 设置回调
        self.ws_service.set_callbacks(
            on_message=self._on_message_received,
            on_error=self._on_error,
            on_close=self._on_connection_closed,
        )
        
        # 控件引用
        self.protocol_dropdown = ft.Ref[ft.Dropdown]()
        self.url_input = ft.Ref[ft.TextField]()
        self.version_dropdown = ft.Ref[ft.Dropdown]()  # 新增版本选择
        self.headers_input = ft.Ref[ft.TextField]()
        self.connect_button = ft.Ref[ft.ElevatedButton]()
        self.status_text = ft.Ref[ft.Text]()
        self.message_text_input = ft.Ref[ft.TextField]()
        self.message_json_input = ft.Ref[ft.TextField]()
        self.send_button = ft.Ref[ft.ElevatedButton]()
        self.message_history = ft.Ref[ft.Column]()
        self.auto_scroll = ft.Ref[ft.Checkbox]()
        
        # 消息类型选择
        self.message_type_tabs = ft.Ref[ft.Tabs]()
        
        # 布局引用（拖动调整）
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.Container]()
        self.ratio = 0.5
        self.left_flex = 500
        self.right_flex = 500
        self.is_dragging = False
        
        self._build_ui()
    
    def _on_divider_pan_start(self, e: ft.DragStartEvent):
        """开始拖动分隔条。"""
        self.is_dragging = True
        if self.divider_ref.current:
            self.divider_ref.current.bgcolor = ft.Colors.PRIMARY
            self.divider_ref.current.update()
    
    def _on_divider_pan_update(self, e: ft.DragUpdateEvent):
        """拖动分隔条时更新面板宽度。"""
        if not self.is_dragging:
            return
        
        container_width = self._page.width - PADDING_MEDIUM * 2 - 8
        if container_width <= 0:
            return
        
        delta_ratio = e.local_delta.x / container_width
        self.ratio += delta_ratio
        self.ratio = max(0.2, min(0.8, self.ratio))
        
        new_total_flex = 1000
        self.left_flex = int(self.ratio * new_total_flex)
        self.right_flex = new_total_flex - self.left_flex
        
        if self.left_panel_ref.current and self.right_panel_ref.current:
            self.left_panel_ref.current.expand = self.left_flex
            self.right_panel_ref.current.expand = self.right_flex
            self.left_panel_ref.current.update()
            self.right_panel_ref.current.update()
    
    def _on_divider_pan_end(self, e: ft.DragEndEvent):
        """结束拖动分隔条。"""
        self.is_dragging = False
        if self.divider_ref.current:
            self.divider_ref.current.bgcolor = None
            self.divider_ref.current.update()
    
    def _build_ui(self):
        """构建用户界面。"""
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self._on_back_click(),
                ),
                ft.Text("WebSocket 客户端", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 连接栏
        connection_bar = self._build_connection_bar()
        
        # 左侧面板：连接配置和消息发送
        left_panel = self._build_left_panel()
        
        # 分隔条
        divider = ft.GestureDetector(
            content=ft.Container(
                ref=self.divider_ref,
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=4, color=ft.Colors.GREY_500),
                        ft.Icon(ft.Icons.CIRCLE, size=4, color=ft.Colors.GREY_500),
                        ft.Icon(ft.Icons.CIRCLE, size=4, color=ft.Colors.GREY_500),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=3,
                ),
                width=12,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                border_radius=6,
                alignment=ft.Alignment.CENTER,
                margin=ft.Margin.only(top=50, bottom=6),
            ),
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            on_pan_start=self._on_divider_pan_start,
            on_pan_update=self._on_divider_pan_update,
            on_pan_end=self._on_divider_pan_end,
            drag_interval=10,
        )
        
        # 右侧面板：消息历史
        right_panel = self._build_right_panel()
        
        # 主内容区域（左右分栏）
        content_area = ft.Row(
            controls=[left_panel, divider, right_panel],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 主列
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(),
                connection_bar,
                ft.Container(height=PADDING_SMALL),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _build_connection_bar(self):
        """构建连接栏。"""
        # 协议选择
        protocol_dropdown = ft.Dropdown(
            ref=self.protocol_dropdown,
            width=100,
            options=[
                ft.dropdown.Option("ws://"),
                ft.dropdown.Option("wss://"),
            ],
            value="ws://",
            content_padding=10,
            text_size=13,
        )
        
        # URL 输入
        url_field = ft.TextField(
            ref=self.url_input,
            hint_text="echo.websocket.org",
            expand=True,
            on_submit=lambda _: self._on_connect_click(None),
            content_padding=10,
            text_size=13,
        )
        
        # 版本选择
        version_dropdown = ft.Dropdown(
            ref=self.version_dropdown,
            label="Version",
            width=80,
            options=[
                ft.dropdown.Option("13"),
                ft.dropdown.Option("8"),
            ],
            value="13",
            content_padding=10,
            text_size=13,
        )
        
        # 连接按钮
        connect_button = ft.ElevatedButton(
            ref=self.connect_button,
            content="连接",
            icon=ft.Icons.LINK,
            on_click=self._on_connect_click,
            style=ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: ft.Colors.WHITE},
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.GREEN,
                    ft.ControlState.HOVERED: ft.Colors.GREEN_700,
                },
                shape=ft.RoundedRectangleBorder(radius=4),
                padding=ft.Padding.symmetric(horizontal=20), # 使用水平 padding，垂直方向自适应
            ),
        )
        
        # 状态显示
        status_text = ft.Text(
            ref=self.status_text,
            value="● 未连接",
            color=ft.Colors.GREY,
            weight=ft.FontWeight.BOLD,
            size=12,
        )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    protocol_dropdown,
                    url_field,
                    version_dropdown,
                    connect_button,
                    ft.Container(width=10),
                    status_text,
                ],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(vertical=5),
        )
    
    def _on_ssl_change(self, e):
        """SSL 开关变化事件。"""
        # 已移除
        pass
    
    def _build_left_panel(self):
        """构建左侧面板。"""
        # 请求头区域
        headers_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("请求头 (可选)", weight=ft.FontWeight.BOLD, size=14),
                    ft.Container(
                        content=ft.TextField(
                            ref=self.headers_input,
                            multiline=True,
                            min_lines=3,
                            max_lines=3,
                            hint_text='Authorization: Bearer token\nCustom-Header: value',
                            text_size=13,
                            border=ft.InputBorder.NONE,
                        ),
                        border=ft.Border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_SMALL,
                    ),
                ],
                spacing=5,
            ),
        )
        
        # 消息输入区域
        message_tabs = ft.Tabs(
            ref=self.message_type_tabs,
            selected_index=0,
            length=2,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Text"),
                            ft.Tab(label="JSON"),
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(
                                content=ft.TextField(
                                    ref=self.message_text_input,
                                    multiline=True,
                                    min_lines=10,
                                    hint_text='输入要发送的文本消息...',
                                    text_size=13,
                                    border=ft.InputBorder.NONE,
                                    expand=True,
                                ),
                                padding=PADDING_SMALL,
                                border=ft.Border.all(1, ft.Colors.OUTLINE),
                                border_radius=8,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                ft.IconButton(
                                                    icon=ft.Icons.AUTO_FIX_HIGH,
                                                    tooltip="格式化 JSON",
                                                    on_click=self._format_json,
                                                    icon_size=20,
                                                ),
                                                ft.IconButton(
                                                    icon=ft.Icons.CHECK_CIRCLE,
                                                    tooltip="验证 JSON",
                                                    on_click=self._validate_json,
                                                    icon_size=20,
                                                ),
                                            ],
                                            spacing=0,
                                        ),
                                        ft.TextField(
                                            ref=self.message_json_input,
                                            multiline=True,
                                            min_lines=10,
                                            hint_text='{"type": "message", "data": "..."}',
                                            text_size=13,
                                            border=ft.InputBorder.NONE,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=0,
                                ),
                                padding=ft.Padding.only(left=PADDING_SMALL, right=PADDING_SMALL, bottom=PADDING_SMALL),
                                border=ft.Border.all(1, ft.Colors.OUTLINE),
                                border_radius=8,
                                expand=True,
                            ),
                        ],
                    ),
                ],
            ),
        )
        
        # 发送按钮
        send_button = ft.ElevatedButton(
            ref=self.send_button,
            content="发送消息",
            icon=ft.Icons.SEND,
            on_click=self._on_send_click,
            disabled=True,
            height=50,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )
        
        return ft.Container(
            ref=self.left_panel_ref,
            content=ft.Column(
                controls=[
                    headers_section,
                    ft.Text("发送消息", weight=ft.FontWeight.BOLD),
                    message_tabs,
                    send_button,
                ],
                spacing=PADDING_SMALL,
            ),
            expand=self.left_flex,
        )
    
    def _build_right_panel(self):
        """构建右侧面板。"""
        # 清空历史按钮
        clear_button = ft.OutlinedButton(
            content="清空",
            icon=ft.Icons.CLEAR_ALL,
            on_click=self._clear_history,
        )
        
        # 自动滚动选项
        auto_scroll_check = ft.Checkbox(
            ref=self.auto_scroll,
            label="自动滚动",
            value=True,
        )
        
        # 消息历史
        message_history = ft.Column(
            ref=self.message_history,
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=48, color=ft.Colors.GREY_400),
                            ft.Text("消息历史将显示在这里", color=ft.Colors.GREY_500, size=14),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        return ft.Container(
            ref=self.right_panel_ref,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("消息历史", weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            auto_scroll_check,
                            clear_button,
                        ],
                    ),
                    ft.Container(
                        content=message_history,
                        border=ft.Border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_SMALL,
                        expand=True,
                    ),
                ],
                spacing=5,
            ),
            expand=self.right_flex,
        )
    
    def _on_connect_click(self, e):
        """连接/断开按钮点击事件。"""
        if self.ws_service.is_connected:
            # 断开连接
            self._page.run_task(self._disconnect)
        else:
            # 连接
            self._page.run_task(self._connect)
    
    async def _connect(self):
        """连接到 WebSocket 服务器。"""
        url_host = self.url_input.current.value
        
        if not url_host or not url_host.strip():
            self._show_snack("请输入 WebSocket URL", error=True)
            return
        
        # 构建完整 URL
        protocol = self.protocol_dropdown.current.value
        url = protocol + url_host.strip()
        
        # 获取版本
        version = self.version_dropdown.current.value
        
        # 解析请求头
        headers = {}
        headers_text = self.headers_input.current.value
        if headers_text:
            from services.http_service import HttpService
            http_service = HttpService()
            headers = http_service.parse_headers(headers_text)
        
        # 添加版本头 (如果不是默认值或需要显式发送)
        # 注意: websockets 库通常自动处理，但如果需要显式指定，可以在这里添加
        # headers['Sec-WebSocket-Version'] = version
        
        # 更新UI
        self.connect_button.current.disabled = True
        self.status_text.current.value = "● 连接中..."
        self.status_text.current.color = ft.Colors.ORANGE
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            return
        
        # 连接
        success, message = await self.ws_service.connect(url, headers)
        
        if success:
            self.connect_button.current.text = "断开"
            self.connect_button.current.icon = ft.Icons.LINK_OFF
            self.connect_button.current.style = ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: ft.Colors.WHITE},
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.RED,
                    ft.ControlState.HOVERED: ft.Colors.RED_700,
                },
                shape=ft.RoundedRectangleBorder(radius=4),
                padding=ft.Padding.symmetric(horizontal=20),
            )
            self.status_text.current.value = "● 已连接"
            self.status_text.current.color = ft.Colors.GREEN
            self.send_button.current.disabled = False
            
            # 清空占位符
            if len(self.message_history.current.controls) == 1:
                self.message_history.current.controls.clear()
            
            self._add_system_message(f"✅ {message}")
            self._show_snack(message, error=False)
        else:
            self.status_text.current.value = "● 未连接"
            self.status_text.current.color = ft.Colors.GREY
            
            self._add_system_message(f"❌ {message}")
            self._show_snack(message, error=True)
        
        self.connect_button.current.disabled = False
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            pass
    
    async def _disconnect(self):
        """断开连接。"""
        if not self.connect_button.current:
            return
            
        self.connect_button.current.disabled = True
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            return
        
        success, message = await self.ws_service.disconnect()
        
        self.connect_button.current.text = "连接"
        self.connect_button.current.icon = ft.Icons.LINK
        self.connect_button.current.style = ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: ft.Colors.WHITE},
            bgcolor={
                ft.ControlState.DEFAULT: ft.Colors.GREEN,
                ft.ControlState.HOVERED: ft.Colors.GREEN_700,
            },
            shape=ft.RoundedRectangleBorder(radius=4),
            padding=ft.Padding.symmetric(horizontal=20),
        )
        self.status_text.current.value = "● 未连接"
        self.status_text.current.color = ft.Colors.GREY
        self.send_button.current.disabled = True
        self.connect_button.current.disabled = False
        
        self._add_system_message(f"🔌 {message}")
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            pass
    
    def _on_send_click(self, e):
        """发送消息按钮点击事件。"""
        self._page.run_task(self._send_message)
    
    async def _send_message(self):
        """发送消息。"""
        # 根据当前选中的 Tab 获取消息
        is_json = self.message_type_tabs.current.selected_index == 1
        
        if is_json:
            message = self.message_json_input.current.value
        else:
            message = self.message_text_input.current.value
        
        if not message or not message.strip():
            self._show_snack("请输入消息内容", error=True)
            return
        
        # 检查是否是 JSON 模式
        if is_json:
            # 验证 JSON
            valid, result = self.ws_service.validate_json(message)
            if not valid:
                self._show_snack(result, error=True)
                return
        
        # 发送消息
        success, result = await self.ws_service.send_message(message.strip())
        
        if success:
            self._add_sent_message(message.strip())
            
            # 清空输入框
            if is_json:
                self.message_json_input.current.value = ""
            else:
                self.message_text_input.current.value = ""
            
            try:
                self.update()
            except (AssertionError, AttributeError):
                # 视图可能已经不在页面上
                pass
        else:
            self._show_snack(result, error=True)
    
    def _on_message_received(self, message: str):
        """接收到消息的回调。"""
        self._add_received_message(message)
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            pass
    
    def _on_error(self, error: str):
        """发生错误的回调。"""
        self._add_system_message(f"❌ {error}")
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            pass
    
    def _on_connection_closed(self):
        """连接关闭的回调。"""
        if not self.connect_button.current:
            return
            
        self.connect_button.current.text = "连接"
        self.connect_button.current.icon = ft.Icons.LINK
        self.connect_button.current.style = ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: ft.Colors.WHITE},
            bgcolor={
                ft.ControlState.DEFAULT: ft.Colors.GREEN,
                ft.ControlState.HOVERED: ft.Colors.GREEN_700,
            },
            shape=ft.RoundedRectangleBorder(radius=4),
            padding=ft.Padding.symmetric(horizontal=20),
        )
        self.status_text.current.value = "● 未连接"
        self.status_text.current.color = ft.Colors.GREY
        self.send_button.current.disabled = True
        
        self._add_system_message("🔌 连接已关闭")
        try:
            self.update()
        except (AssertionError, AttributeError):
            # 视图可能已经不在页面上
            pass
    
    def _add_system_message(self, text: str):
        """添加系统消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_item = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(f"[{timestamp}]", size=11, color=ft.Colors.GREY),
                    ft.Text(text, size=13, color=ft.Colors.BLUE_GREY, italic=True),
                ],
                spacing=5,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_GREY),
            border_radius=4,
        )
        
        self.message_history.current.controls.append(message_item)
        self._auto_scroll()
    
    def _add_sent_message(self, text: str):
        """添加发送的消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_item = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ARROW_UPWARD, size=14, color=ft.Colors.GREEN),
                            ft.Text(f"发送 [{timestamp}]", size=11, color=ft.Colors.GREY),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                icon_size=14,
                                tooltip="复制",
                                on_click=lambda _, t=text: self._page.run_task(self._copy_to_clipboard, t),
                            ),
                        ],
                        spacing=3,
                    ),
                    ft.Text(text, size=13, selectable=True, font_family="Consolas,monospace"),
                ],
                spacing=2,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
            border_radius=4,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREEN)),
        )
        
        self.message_history.current.controls.append(message_item)
        self._auto_scroll()
    
    def _add_received_message(self, text: str):
        """添加接收的消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_item = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ARROW_DOWNWARD, size=14, color=ft.Colors.BLUE),
                            ft.Text(f"接收 [{timestamp}]", size=11, color=ft.Colors.GREY),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                icon_size=14,
                                tooltip="复制",
                                on_click=lambda _, t=text: self._page.run_task(self._copy_to_clipboard, t),
                            ),
                        ],
                        spacing=3,
                    ),
                    ft.Text(text, size=13, selectable=True, font_family="Consolas,monospace"),
                ],
                spacing=2,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE),
            border_radius=4,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.BLUE)),
        )
        
        self.message_history.current.controls.append(message_item)
        self._auto_scroll()
    
    def _auto_scroll(self):
        """自动滚动到底部。"""
        if self.auto_scroll.current and self.auto_scroll.current.value:
            # 触发滚动（Flet 会自动滚动到最新内容）
            if self.message_history.current:
                try:
                    self.message_history.current.scroll_to(
                        offset=-1,
                        duration=100,
                    )
                except (AssertionError, AttributeError):
                    # 控件可能已经从页面中移除，忽略错误
                    pass
    
    def _clear_history(self, e):
        """清空消息历史。"""
        self.message_history.current.controls.clear()
        # 添加占位符
        self.message_history.current.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=48, color=ft.Colors.GREY_400),
                        ft.Text("消息历史将显示在这里", color=ft.Colors.GREY_500, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                expand=True,
                alignment=ft.Alignment.CENTER,
            )
        )
        try:
            self.update()
        except (AssertionError, AttributeError):
            pass
    
    def _format_json(self, e):
        """格式化 JSON。"""
        message = self.message_json_input.current.value
        if not message:
            return
        
        valid, result = self.ws_service.validate_json(message)
        if valid:
            self.message_json_input.current.value = result
            try:
                self.update()
            except (AssertionError, AttributeError):
                pass
            self._show_snack("JSON 已格式化")
        else:
            self._show_snack(result, error=True)
    
    def _validate_json(self, e):
        """验证 JSON。"""
        message = self.message_json_input.current.value
        if not message:
            self._show_snack("请输入 JSON 内容", error=True)
            return
        
        valid, result = self.ws_service.validate_json(message)
        if valid:
            self._show_snack("✅ JSON 格式正确", error=False)
        else:
            self._show_snack(result, error=True)
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        # 如果已连接，先断开
        if self.ws_service.is_connected:
            self._page.run_task(self._disconnect)
        
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**WebSocket 客户端使用说明**

**基本用法：**
1. 选择协议 (ws:// 或 wss://)
2. 输入 WebSocket URL
3. (可选) 选择 WebSocket 版本
4. 点击"连接"按钮
5. 在左侧消息框输入内容，点击"发送消息"
6. 在右侧查看消息历史

**功能特性：**
- **协议/版本**：支持选择 ws/wss 和协议版本
- **消息类型**：支持纯文本和 JSON (带格式化验证)
- **界面优化**：
  - 左右分栏布局，可拖动调整
  - 消息历史支持一键复制
  - 消息内容使用等宽字体显示
- **自动滚动**：保持显示最新消息

**测试服务器：**
- ws://echo.websocket.org
- wss://ws.postman-echo.com/raw
        """
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("使用说明"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Markdown(
                            help_text,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=500,
                height=450,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _: self._page.pop_dialog()),
            ],
        )
        
        self._page.show_dialog(dialog)
    
    async def _copy_to_clipboard(self, text: str):
        """复制文本到剪贴板。"""
        await ft.Clipboard().set(text)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.show_dialog(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()