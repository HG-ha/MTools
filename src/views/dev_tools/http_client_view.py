# -*- coding: utf-8 -*-
"""HTTP 客户端视图模块。

提供发送 HTTP 请求和查看响应的功能。
"""

import json
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL
from services import ConfigService
from utils import logger


class HttpClientView(ft.Container):
    """HTTP 客户端视图类。
    
    提供 HTTP 请求测试功能。
    """
    
    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        on_back: Optional[Callable] = None
    ):
        """初始化 HTTP 客户端视图。
        
        Args:
            page: Flet 页面对象
            config_service: 配置服务实例（可选）
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self.page = page
        self.config_service = config_service
        self.on_back = on_back
        self.expand = True
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 导入 HTTP 服务
        from services.http_service import HttpService
        self.http_service = HttpService()
        
        # 控件引用
        self.method_dropdown = ft.Ref[ft.Dropdown]()
        self.url_input = ft.Ref[ft.TextField]()
        self.proxy_input = ft.Ref[ft.TextField]()
        self.headers_input = ft.Ref[ft.TextField]()
        self.params_input = ft.Ref[ft.TextField]()
        # 分离三种请求体的 Ref
        self.body_raw_input = ft.Ref[ft.TextField]()
        self.body_json_input = ft.Ref[ft.TextField]()
        self.body_form_input = ft.Ref[ft.TextField]()
        # Multipart 相关
        self.multipart_files_list = ft.Ref[ft.Column]()
        self.files_dict = {}  # {field_name: file_path}
        
        self.body_type_tabs = ft.Ref[ft.Tabs]()
        self.send_button = ft.Ref[ft.ElevatedButton]()
        
        # 文件选择器
        self.file_picker = ft.FilePicker(on_result=self._on_file_selected)
        self.page.overlay.append(self.file_picker)
        self.current_file_field = None  # 当前正在选择文件的字段名
        self.response_tabs = ft.Ref[ft.Tabs]()
        self.response_status = ft.Ref[ft.Text]()
        self.response_time = ft.Ref[ft.Text]()
        self.response_size = ft.Ref[ft.Text]()
        self.response_body = ft.Ref[ft.TextField]()
        self.response_headers = ft.Ref[ft.TextField]()
        self.curl_command = ft.Ref[ft.TextField]()
        self.loading_indicator = ft.Ref[ft.ProgressRing]()
        
        # 布局引用（用于拖动调整）
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.Container]()
        self.ratio = 0.5  # 初始比例 5:5
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
        
        # 获取容器宽度
        container_width = self.page.width - PADDING_MEDIUM * 2 - 8
        if container_width <= 0:
            return
        
        # 计算拖动产生的比例变化
        delta_ratio = e.delta_x / container_width
        self.ratio += delta_ratio
        
        # 限制比例范围 (0.2 到 0.8)
        self.ratio = max(0.2, min(0.8, self.ratio))
        
        # 更新 flex 值
        new_total_flex = 1000
        self.left_flex = int(self.ratio * new_total_flex)
        self.right_flex = new_total_flex - self.left_flex
        
        # 更新面板
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
                    on_click=lambda _: self.on_back() if self.on_back else None,
                ),
                ft.Text("HTTP 客户端", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),  # 占位符
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 顶部请求栏
        method_selector = ft.Dropdown(
            ref=self.method_dropdown,
            value="GET",
            options=[
                ft.dropdown.Option("GET"),
                ft.dropdown.Option("POST"),
                ft.dropdown.Option("PUT"),
                ft.dropdown.Option("DELETE"),
                ft.dropdown.Option("PATCH"),
                ft.dropdown.Option("HEAD"),
                ft.dropdown.Option("OPTIONS"),
            ],
            width=120,
            border_radius=ft.border_radius.only(top_left=8, bottom_left=8),
            content_padding=10,
        )
        
        # URL 输入框 (移除左侧圆角，与下拉框连接)
        url_field = ft.TextField(
            ref=self.url_input,
            hint_text="https://api.example.com/endpoint",
            expand=True,
            on_submit=self._on_send_request,
            border_radius=0,
            content_padding=10,
        )
        
        # 发送按钮 (移除左侧圆角，与输入框连接)
        send_button = ft.ElevatedButton(
            ref=self.send_button,
            text="发送",
            icon=ft.Icons.SEND,
            on_click=self._on_send_request,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=ft.border_radius.only(top_right=8, bottom_right=8)),
                color={
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.BLUE,
                    ft.ControlState.HOVERED: ft.Colors.BLUE_700,
                },
                padding=20,
            ),
        )
        
        loading_ring = ft.ProgressRing(
            ref=self.loading_indicator,
            visible=False,
            width=20,
            height=20,
        )
        
        # 代理输入框
        proxy_field = ft.TextField(
            ref=self.proxy_input,
            label="代理 (可选)",
            hint_text="http://127.0.0.1:8080 或 socks5://127.0.0.1:1080",
            width=350,
            dense=True,
            text_size=13,
        )
        
        # 组合请求栏：下拉框 + 输入框 + 按钮
        request_bar = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    method_selector,
                                    url_field,
                                    send_button,
                                ],
                                spacing=0,
                            ),
                            expand=True,
                        ),
                        loading_ring,
                    ],
                    spacing=PADDING_SMALL,
                ),
                proxy_field,
            ],
            spacing=5,
        )
        
        # 左侧：请求配置
        request_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Params",
                    content=ft.Container(
                        content=ft.TextField(
                            ref=self.params_input,
                            multiline=True,
                            min_lines=15,
                            hint_text='Query Params\npage=1\nlimit=10',
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            expand=True,
                        ),
                        padding=PADDING_SMALL,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Headers",
                    content=ft.Container(
                        content=ft.TextField(
                            ref=self.headers_input,
                            multiline=True,
                            min_lines=15,
                            hint_text='Headers\nContent-Type: application/json\nAuthorization: Bearer token',
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            expand=True,
                        ),
                        padding=PADDING_SMALL,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Body",
                    content=self._build_body_tab(),
                ),
            ],
            expand=True,
        )
        
        left_panel = ft.Container(
            ref=self.left_panel_ref,
            content=ft.Column(
                controls=[
                    ft.Text("请求", weight=ft.FontWeight.BOLD),
                    request_tabs,
                ],
                spacing=5,
            ),
            expand=self.left_flex,
        )
        
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
                alignment=ft.alignment.center,
            ),
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            on_pan_start=self._on_divider_pan_start,
            on_pan_update=self._on_divider_pan_update,
            on_pan_end=self._on_divider_pan_end,
            drag_interval=10,
        )
        
        # 右侧：响应显示
        response_section = self._build_response_section()
        
        right_panel = ft.Container(
            ref=self.right_panel_ref,
            content=response_section,
            expand=self.right_flex,
        )
        
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
                request_bar,
                ft.Container(height=PADDING_SMALL),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _add_multipart_file(self, e):
        """添加文件字段对话框。"""
        field_name_ref = ft.Ref[ft.TextField]()
        
        def confirm_add(e):
            name = field_name_ref.current.value
            if not name:
                self._show_snack("请输入字段名", error=True)
                return
            
            self.current_file_field = name
            self.page.close(dialog)
            self.file_picker.pick_files(allow_multiple=False)
            
        dialog = ft.AlertDialog(
            title=ft.Text("添加文件"),
            content=ft.TextField(
                ref=field_name_ref,
                label="字段名 (Key)",
                autofocus=True,
                on_submit=confirm_add,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self.page.close(dialog)),
                ft.TextButton("选择文件", on_click=confirm_add),
            ],
        )
        self.page.open(dialog)
    
    def _on_file_selected(self, e: ft.FilePickerResultEvent):
        """文件选择回调。"""
        if not e.files or not self.current_file_field:
            return
            
        file_path = e.files[0].path
        self.files_dict[self.current_file_field] = file_path
        self._update_multipart_list()
        self.current_file_field = None
    
    def _remove_multipart_file(self, field_name):
        """移除文件字段。"""
        if field_name in self.files_dict:
            del self.files_dict[field_name]
            self._update_multipart_list()
            
    def _update_multipart_list(self):
        """更新 Multipart 文件列表显示。"""
        if not self.multipart_files_list.current:
            return
            
        controls = []
        for name, path in self.files_dict.items():
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ATTACH_FILE, size=16, color=ft.Colors.BLUE),
                            ft.Text(f"{name}:", weight=ft.FontWeight.BOLD),
                            ft.Text(path, size=12, color=ft.Colors.GREY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_size=18,
                                icon_color=ft.Colors.RED_400,
                                tooltip="移除",
                                on_click=lambda _, n=name: self._remove_multipart_file(n)
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=4,
                )
            )
            
        self.multipart_files_list.current.controls = controls
        self.multipart_files_list.current.update()

    def _build_body_tab(self):
        """构建请求体标签页。"""
        body_type_tabs = ft.Tabs(
            ref=self.body_type_tabs,
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(
                    text="Raw",
                    content=ft.Container(
                        content=ft.TextField(
                            ref=self.body_raw_input,
                            multiline=True,
                            min_lines=12,
                            hint_text='请求体内容... (Text, XML, etc.)',
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            expand=True,
                        ),
                        padding=PADDING_SMALL,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="JSON",
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.AUTO_FIX_HIGH,
                                            tooltip="格式化 JSON",
                                            on_click=self._format_json_body,
                                            icon_size=20,
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.COMPRESS,
                                            tooltip="压缩 JSON",
                                            on_click=self._compress_json_body,
                                            icon_size=20,
                                        ),
                                    ],
                                    spacing=0,
                                ),
                                ft.TextField(
                                    ref=self.body_json_input,
                                    multiline=True,
                                    min_lines=12,
                                    hint_text='{"key": "value"}',
                                    text_size=13,
                                    border=ft.InputBorder.NONE,
                                    expand=True,
                                ),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.only(left=PADDING_SMALL, right=PADDING_SMALL, bottom=PADDING_SMALL),
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Form",
                    content=ft.Container(
                        content=ft.TextField(
                            ref=self.body_form_input,
                            multiline=True,
                            min_lines=12,
                            hint_text='username=admin\npassword=123',
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            expand=True,
                        ),
                        padding=PADDING_SMALL,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Multipart",
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.TextButton(
                                                "添加文件",
                                                icon=ft.Icons.ADD,
                                                on_click=self._add_multipart_file
                                            ),
                                            ft.Text("配合 Form Tab 使用，Form 内容将作为字段发送", size=12, color=ft.Colors.GREY),
                                        ],
                                    ),
                                    padding=ft.padding.only(bottom=5),
                                ),
                                ft.Column(
                                    ref=self.multipart_files_list,
                                    scroll=ft.ScrollMode.AUTO,
                                    expand=True,
                                    spacing=2,
                                ),
                            ],
                        ),
                        padding=PADDING_SMALL,
                        expand=True,
                    ),
                ),
            ],
            expand=True,
        )
        
        return ft.Container(
            content=body_type_tabs,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            padding=0,
            expand=True,
        )
    
    def _build_response_section(self):
        """构建响应区域。"""
        # 响应状态徽章
        def get_status_badge(text, color):
            return ft.Container(
                content=ft.Text(text, color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=color,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=4,
            )
        
        # 状态行
        status_row = ft.Row(
            controls=[
                ft.Text(ref=self.response_status, value="Status: --", weight=ft.FontWeight.BOLD, color=ft.Colors.GREY),
                ft.VerticalDivider(width=10),
                ft.Text(ref=self.response_time, value="Time: -- ms", size=12, color=ft.Colors.GREY),
                ft.VerticalDivider(width=10),
                ft.Text(ref=self.response_size, value="Size: -- B", size=12, color=ft.Colors.GREY),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=5,
        )
        
        # 响应标签页
        response_tabs = ft.Tabs(
            ref=self.response_tabs,
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Body",
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.COPY,
                                            tooltip="复制",
                                            on_click=self._copy_response_body,
                                            icon_size=20,
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.AUTO_FIX_HIGH,
                                            tooltip="格式化",
                                            on_click=self._format_response_body,
                                            icon_size=20,
                                        ),
                                    ],
                                    spacing=0,
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                                ft.TextField(
                                    ref=self.response_body,
                                    multiline=True,
                                    read_only=True,
                                    min_lines=15,
                                    text_size=13,
                                    border=ft.InputBorder.NONE,
                                    expand=True,
                                ),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.only(left=PADDING_SMALL, right=PADDING_SMALL, bottom=PADDING_SMALL),
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Headers",
                    content=ft.Container(
                        content=ft.TextField(
                            ref=self.response_headers,
                            multiline=True,
                            read_only=True,
                            min_lines=15,
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            expand=True,
                        ),
                        padding=PADDING_SMALL,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="cURL",
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.COPY,
                                            tooltip="复制",
                                            on_click=self._copy_curl,
                                            icon_size=20,
                                        ),
                                    ],
                                    spacing=0,
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                                ft.TextField(
                                    ref=self.curl_command,
                                    multiline=True,
                                    read_only=True,
                                    min_lines=15,
                                    text_size=13,
                                    border=ft.InputBorder.NONE,
                                    expand=True,
                                ),
                            ],
                            spacing=0,
                        ),
                        padding=ft.padding.only(left=PADDING_SMALL, right=PADDING_SMALL, bottom=PADDING_SMALL),
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        expand=True,
                    ),
                ),
            ],
            expand=True,
        )
        
        return ft.Column(
            controls=[
                ft.Row([ft.Text("响应", weight=ft.FontWeight.BOLD), ft.Container(expand=True), status_row]),
                response_tabs,
            ],
            spacing=5,
            expand=True,
        )
    
    def _on_send_request(self, e):
        """发送 HTTP 请求。"""
        # 获取参数
        method = self.method_dropdown.current.value
        url = self.url_input.current.value
        proxy = self.proxy_input.current.value
        headers_text = self.headers_input.current.value
        params_text = self.params_input.current.value
        
        # 判断请求体类型并获取对应内容
        body_type_index = self.body_type_tabs.current.selected_index if self.body_type_tabs.current else 0
        body_type_map = {0: "raw", 1: "json", 2: "form", 3: "multipart"}
        body_type = body_type_map.get(body_type_index, "raw")
        
        body = ""
        files = None
        
        if body_type == "raw":
            body = self.body_raw_input.current.value
        elif body_type == "json":
            body = self.body_json_input.current.value
        elif body_type == "form":
            body = self.body_form_input.current.value
        elif body_type == "multipart":
            # Multipart 模式下，同时使用 Form 的内容作为文本字段，以及 Files 字典
            body = self.body_form_input.current.value
            files = self.files_dict
        
        # 验证 URL
        if not url or not url.strip():
            self._show_snack("请输入请求 URL", error=True)
            return
        
        # 解析请求头和参数
        headers = self.http_service.parse_headers(headers_text or "")
        params = self.http_service.parse_query_params(params_text or "")
        
        # 生成 cURL 命令
        curl_cmd = self.http_service.get_curl_command(
            method=method,
            url=url.strip(),
            headers=headers,
            params=params,
            body=body,
            body_type=body_type if body_type != "multipart" else "form",
            files=files,
        )
        self.curl_command.current.value = curl_cmd
        
        # 显示加载状态
        self.send_button.current.disabled = True
        self.send_button.current.text = "发送中..."
        self.loading_indicator.current.visible = True
        self.update()
        
        # 发送请求
        success, result = self.http_service.send_request(
            method=method,
            url=url.strip(),
            headers=headers,
            params=params,
            body=body,
            body_type=body_type if body_type != "multipart" else "form", # Multipart 模式下 body 是 form 格式
            files=files,
            proxy=proxy,
        )
        
        # 隐藏加载状态
        self.send_button.current.disabled = False
        self.send_button.current.text = "发送"
        self.loading_indicator.current.visible = False
        
        if success:
            # 显示响应
            status_code = result.get("status_code", 0)
            status_text = result.get("status_text", "")
            time_ms = result.get('time_ms', 0)
            size_bytes = result.get('size_bytes', 0)
            
            # 状态码颜色
            if 200 <= status_code < 300:
                status_color = ft.Colors.GREEN
            elif 300 <= status_code < 400:
                status_color = ft.Colors.BLUE
            elif 400 <= status_code < 500:
                status_color = ft.Colors.ORANGE
            else:
                status_color = ft.Colors.RED
            
            self.response_status.current.value = f"{status_code} {status_text}"
            self.response_status.current.color = status_color
            self.response_time.current.value = f"{time_ms} ms"
            
            # 格式化大小
            if size_bytes < 1024:
                size_text = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_text = f"{size_bytes / 1024:.2f} KB"
            else:
                size_text = f"{size_bytes / (1024 * 1024):.2f} MB"
            self.response_size.current.value = size_text
            
            # 响应体
            self.response_body.current.value = result.get("body", "")
            
            # 响应头
            headers_dict = result.get("headers", {})
            headers_lines = [f"{k}: {v}" for k, v in headers_dict.items()]
            self.response_headers.current.value = "\n".join(headers_lines)
            
            self._show_snack("请求成功", error=False)
        else:
            # 显示错误
            error_msg = result.get("error", "未知错误")
            self.response_status.current.value = "ERROR"
            self.response_status.current.color = ft.Colors.RED
            self.response_time.current.value = "--"
            self.response_size.current.value = "--"
            self.response_body.current.value = f"❌ {error_msg}"
            self.response_headers.current.value = ""
            
            self._show_snack(f"请求失败: {error_msg}", error=True)
        
        self.update()
    
    def _format_json_body(self, e):
        """格式化 JSON 请求体。"""
        try:
            body = self.body_json_input.current.value
            if not body:
                return
            
            data = json.loads(body)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            self.body_json_input.current.value = formatted
            self.update()
            self._show_snack("JSON 已格式化")
        except json.JSONDecodeError as ex:
            self._show_snack(f"JSON 格式错误: {str(ex)}", error=True)
    
    def _compress_json_body(self, e):
        """压缩 JSON 请求体。"""
        try:
            body = self.body_json_input.current.value
            if not body:
                return
            
            data = json.loads(body)
            compressed = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            self.body_json_input.current.value = compressed
            self.update()
            self._show_snack("JSON 已压缩")
        except json.JSONDecodeError as ex:
            self._show_snack(f"JSON 格式错误: {str(ex)}", error=True)
    
    def _format_response_body(self, e):
        """格式化响应体（如果是 JSON）。"""
        try:
            body = self.response_body.current.value
            if not body:
                return
            
            data = json.loads(body)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            self.response_body.current.value = formatted
            self.update()
            self._show_snack("响应已格式化")
        except json.JSONDecodeError:
            self._show_snack("响应不是有效的 JSON", error=True)
    
    def _copy_response_body(self, e):
        """复制响应体。"""
        body = self.response_body.current.value
        if body:
            self.page.set_clipboard(body)
            self._show_snack("响应体已复制")
    
    def _copy_curl(self, e):
        """复制 cURL 命令。"""
        curl = self.curl_command.current.value
        if curl:
            self.page.set_clipboard(curl)
            self._show_snack("cURL 命令已复制")
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**HTTP 客户端使用说明**

**基本用法：**
1. 选择 HTTP 方法（GET, POST 等）
2. 输入请求 URL
3. 可选：配置代理
4. 在左侧面板配置请求（Params, Headers, Body）
5. 点击"发送"
6. 在右侧面板查看响应

**代理配置：**
支持多种代理协议：
```
http://127.0.0.1:8080
https://proxy.example.com:3128
socks5://127.0.0.1:1080
http://user:pass@proxy.com:8080
```

**请求体类型：**
- **Raw**: 纯文本、XML 等
- **JSON**: 自动设置 Content-Type，支持格式化
- **Form**: URL 编码表单（key=value）
- **Multipart**: 文件上传 + 表单字段

**Multipart 文件上传：**
1. 在 Form 标签页输入文本字段（如 `reqtype=fileupload`）
2. 切换到 Multipart 标签页
3. 点击"添加文件"，输入字段名，选择文件
4. 发送请求（会自动使用 multipart/form-data）

**特色功能：**
- ✅ 拖动中间分隔条调整左右宽度
- ✅ 支持 HTTP/HTTPS/SOCKS5 代理
- ✅ 文件上传支持
- ✅ JSON 格式化和压缩
- ✅ 响应状态码颜色提示
- ✅ 一键生成 cURL 命令
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
                height=400,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _: self.page.close(dialog)),
            ],
        )
        
        self.page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self.page.snack_bar.open = True
        self.page.update()
