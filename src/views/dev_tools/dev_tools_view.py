# -*- coding: utf-8 -*-
"""开发工具视图模块。

提供开发者工具相关功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import ConfigService, EncodingService
from views.dev_tools.encoding_convert_view import EncodingConvertView


class DevToolsView(ft.Container):
    """开发工具视图类。
    
    提供开发工具相关功能的用户界面，包括：
    - 编码转换
    - 代码格式化
    - Base64转图片
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        encoding_service: EncodingService,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化开发工具视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            encoding_service: 编码服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self._saved_page: ft.Page = page  # 保存页面引用
        self.config_service: ConfigService = config_service
        self.encoding_service: EncodingService = encoding_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 创建子视图（延迟创建）
        self.encoding_convert_view: Optional[EncodingConvertView] = None
        self.base64_to_image_view: Optional[ft.Container] = None
        self.http_client_view: Optional[ft.Container] = None
        self.websocket_client_view: Optional[ft.Container] = None
        self.encoder_decoder_view: Optional[ft.Container] = None
        self.regex_tester_view: Optional[ft.Container] = None
        self.timestamp_tool_view: Optional[ft.Container] = None
        self.jwt_tool_view: Optional[ft.Container] = None
        self.uuid_generator_view: Optional[ft.Container] = None
        self.color_tool_view: Optional[ft.Container] = None
        self.markdown_viewer_view: Optional[ft.Container] = None
        self.dns_lookup_view: Optional[ft.Container] = None
        self.port_scanner_view: Optional[ft.Container] = None
        self.format_convert_view: Optional[ft.Container] = None
        self.text_diff_view: Optional[ft.Container] = None
        self.crypto_tool_view: Optional[ft.Container] = None
        self.sql_formatter_view: Optional[ft.Container] = None
        self.cron_tool_view: Optional[ft.Container] = None
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        # 记录当前子视图的类型（用于销毁）
        self.current_sub_view_type: Optional[str] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _safe_page_update(self) -> None:
        """安全地更新页面。"""
        page = getattr(self, '_saved_page', self.page)
        if page:
            page.update()
    
    def _hide_search_button(self) -> None:
        """隐藏主视图的搜索按钮。"""
        if hasattr(self.page, '_main_view'):
            self.page._main_view.hide_search_button()
    
    def _show_search_button(self) -> None:
        """显示主视图的搜索按钮。"""
        if hasattr(self.page, '_main_view'):
            self.page._main_view.show_search_button()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域
        feature_cards: ft.Row = ft.Row(
            controls=[
                # 编码转换
                FeatureCard(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="编码转换",
                    description="检测和转换文件编码格式",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_encoding_convert,
                ),
                # JSON 查看器
                FeatureCard(
                    icon=ft.Icons.DATA_OBJECT,
                    title="JSON 查看器",
                    description="格式化并以树形结构查看 JSON",
                    gradient_colors=("#FA8BFF", "#2BD2FF"),
                    on_click=self._open_json_viewer,
                ),
                # Base64转图片
                FeatureCard(
                    icon=ft.Icons.IMAGE_OUTLINED,
                    title="Base64转图片",
                    description="Base64转图片，自动识别格式",
                    gradient_colors=("#4FACFE", "#00F2FE"),
                    on_click=self._open_base64_to_image,
                ),
                # HTTP 客户端
                FeatureCard(
                    icon=ft.Icons.HTTP,
                    title="HTTP 客户端",
                    description="发送 HTTP 请求，测试 API 接口",
                    gradient_colors=("#F093FB", "#F5576C"),
                    on_click=self._open_http_client,
                ),
                # WebSocket 客户端
                FeatureCard(
                    icon=ft.Icons.CABLE,
                    title="WebSocket 客户端",
                    description="连接 WebSocket，实时收发消息",
                    gradient_colors=("#A8EDEA", "#FED6E3"),
                    on_click=self._open_websocket_client,
                ),
                # 编码/解码工具
                FeatureCard(
                    icon=ft.Icons.LOCK_OPEN,
                    title="编码/解码",
                    description="Base64、URL、HTML、Unicode 编解码",
                    gradient_colors=("#FFD89B", "#19547B"),
                    on_click=self._open_encoder_decoder,
                ),
                # 正则表达式测试器
                FeatureCard(
                    icon=ft.Icons.PATTERN,
                    title="正则表达式测试器",
                    description="实时测试正则表达式，可视化匹配结果",
                    gradient_colors=("#FC466B", "#3F5EFB"),
                    on_click=self._open_regex_tester,
                ),
                # 时间工具
                FeatureCard(
                    icon=ft.Icons.ACCESS_TIME,
                    title="时间工具",
                    description="时间戳转换、时间计算、格式转换",
                    gradient_colors=("#11998E", "#38EF7D"),
                    on_click=self._open_timestamp_tool,
                ),
                # JWT 工具
                FeatureCard(
                    icon=ft.Icons.KEY,
                    title="JWT 工具",
                    description="解析 JWT Token，查看头部和载荷",
                    gradient_colors=("#00C9FF", "#92FE9D"),
                    on_click=self._open_jwt_tool,
                ),
                # UUID 生成器
                FeatureCard(
                    icon=ft.Icons.FINGERPRINT,
                    title="UUID/随机数生成器",
                    description="生成 UUID、随机字符串、随机密码",
                    gradient_colors=("#F857A6", "#FF5858"),
                    on_click=self._open_uuid_generator,
                ),
                # 颜色工具
                FeatureCard(
                    icon=ft.Icons.PALETTE,
                    title="颜色工具",
                    description="颜色格式转换、图片取色器、调色板",
                    gradient_colors=("#FF9A9E", "#FAD0C4"),
                    on_click=self._open_color_tool,
                ),
                # Markdown 预览器
                FeatureCard(
                    icon=ft.Icons.DESCRIPTION,
                    title="Markdown 预览器",
                    description="实时预览 Markdown，导出 HTML",
                    gradient_colors=("#A8CABA", "#5D4E6D"),
                    on_click=self._open_markdown_viewer,
                ),
                # DNS 查询
                FeatureCard(
                    icon=ft.Icons.DNS,
                    title="DNS 查询",
                    description="多种记录类型、反向查询、批量查询、指定服务器",
                    gradient_colors=("#4CA1AF", "#C4E0E5"),
                    on_click=self._open_dns_lookup,
                ),
                # 端口扫描
                FeatureCard(
                    icon=ft.Icons.ROUTER,
                    title="端口扫描",
                    description="端口检测、批量端口、常用端口、范围扫描",
                    gradient_colors=("#FC466B", "#3F5EFB"),
                    on_click=self._open_port_scanner,
                ),
                # 数据格式转换
                FeatureCard(
                    icon=ft.Icons.SWAP_HORIZ,
                    title="数据格式转换",
                    description="JSON、YAML、XML、TOML 互转",
                    gradient_colors=("#11998E", "#38EF7D"),
                    on_click=self._open_format_convert,
                ),
                # 文本对比
                FeatureCard(
                    icon=ft.Icons.COMPARE,
                    title="文本对比",
                    description="左右分栏、高亮显示差异",
                    gradient_colors=("#3A7BD5", "#00D2FF"),
                    on_click=self._open_text_diff,
                ),
                # 加解密工具
                FeatureCard(
                    icon=ft.Icons.SECURITY,
                    title="加解密工具",
                    description="AES, DES, RC4, MD5, SHA 等",
                    gradient_colors=("#2C3E50", "#4CA1AF"),
                    on_click=self._open_crypto_tool,
                ),
                # SQL 格式化
                FeatureCard(
                    icon=ft.Icons.CODE,
                    title="SQL 格式化",
                    description="格式化/压缩 SQL，支持多种方言",
                    gradient_colors=("#1FA2FF", "#12D8FA"),
                    on_click=self._open_sql_formatter,
                ),
                # Cron 表达式工具
                FeatureCard(
                    icon=ft.Icons.SCHEDULE,
                    title="Cron 表达式",
                    description="解析 Cron 表达式，预测执行时间",
                    gradient_colors=("#A770EF", "#CF8BF3"),
                    on_click=self._open_cron_tool,
                ),
            ],
            wrap=True,
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
            expand=True,
            width=float('inf'),  # 占满可用宽度
            on_scroll=self._on_scroll,
        )
        
        # 拖放工具映射：(工具名, 支持的扩展名集合, 打开方法, 视图属性名)
        # 顺序必须与上面 feature_cards 中的卡片顺序一致
        _text_exts = {'.txt', '.log', '.ini', '.cfg', '.conf', '.properties'}
        _json_exts = {'.json'}
        _md_exts = {'.md', '.markdown', '.mdown', '.mkd'}
        _data_exts = {'.json', '.yaml', '.yml', '.xml', '.toml'}
        _sql_exts = {'.sql'}
        _base64_exts = {'.txt', '.base64', '.b64', '.text'}
        _any_file = set()  # 空集合表示接受任意文件类型（编码转换）
        
        self._drop_tool_map = [
            ("编码转换", _any_file, self._open_encoding_convert, "encoding_convert_view", True),  # True 表示接受任意文件
            ("JSON 查看器", _json_exts, self._open_json_viewer, "json_viewer_view", False),
            ("Base64转图片", _base64_exts, self._open_base64_to_image, "base64_to_image_view", False),
            ("HTTP 客户端", set(), None, None, False),
            ("WebSocket 客户端", set(), None, None, False),
            ("编码/解码", set(), None, None, False),
            ("正则表达式测试器", set(), None, None, False),
            ("时间工具", set(), None, None, False),
            ("JWT 工具", set(), None, None, False),
            ("UUID/随机数生成器", set(), None, None, False),
            ("颜色工具", set(), None, None, False),
            ("Markdown 预览器", _md_exts, self._open_markdown_viewer, "markdown_viewer_view", False),
            ("DNS 查询", set(), None, None, False),
            ("端口扫描", set(), None, None, False),
            ("数据格式转换", _data_exts, self._open_format_convert, "format_convert_view", False),
            ("文本对比", _text_exts | _json_exts | _md_exts | _data_exts | _sql_exts, self._open_text_diff, "text_diff_view", False),
            ("加解密工具", set(), None, None, False),
            ("SQL 格式化", _sql_exts, self._open_sql_formatter, "sql_formatter_view", False),
            ("Cron 表达式", set(), None, None, False),
        ]
        
        # 卡片布局参数
        self._card_margin_left = 5
        self._card_margin_top = 5
        self._card_margin_bottom = 10
        self._card_width = 280
        self._card_height = 220
        self._card_step_x = self._card_margin_left + self._card_width + 0 + PADDING_LARGE
        self._card_step_y = self._card_margin_top + self._card_height + self._card_margin_bottom + PADDING_LARGE
        self._content_padding = PADDING_MEDIUM
        self._scroll_offset_y = 0
    
    def _open_encoding_convert(self, e: ft.ControlEvent) -> None:
        """打开编码转换。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.encoding_convert_view is None:
            self.encoding_convert_view = EncodingConvertView(
                self._saved_page,
                self.config_service,
                self.encoding_service,
                on_back=self._back_to_main
            )
        
        # 切换到编码转换视图
        if self.parent_container:
            self.current_sub_view = self.encoding_convert_view
            self.current_sub_view_type = "encoding_convert"
            self.parent_container.content = self.encoding_convert_view
        self._safe_page_update()
    
    def _open_json_viewer(self, e: ft.ControlEvent) -> None:
        """打开 JSON 查看器。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.dev_tools.json_viewer_view import JsonViewerView
        
        json_viewer = JsonViewerView(
            self._saved_page,
            self.config_service,
            on_back=self._back_to_main
        )
        
        # 切换到 JSON 查看器视图
        if self.parent_container:
            self.current_sub_view = json_viewer
            self.current_sub_view_type = "json_viewer"
            self.parent_container.content = json_viewer
        self._safe_page_update()
    
    def _open_base64_to_image(self, e: ft.ControlEvent) -> None:
        """打开Base64转图片。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.base64_to_image_view is None:
            from views.dev_tools.base64_to_image_view import Base64ToImageView
            self.base64_to_image_view = Base64ToImageView(
                self._saved_page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 切换到Base64转图片视图
        if self.parent_container:
            self.current_sub_view = self.base64_to_image_view
            self.current_sub_view_type = "base64_to_image"
            self.parent_container.content = self.base64_to_image_view
        self._safe_page_update()
    
    def _open_http_client(self, e: ft.ControlEvent) -> None:
        """打开 HTTP 客户端。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.http_client_view is None:
            from views.dev_tools.http_client_view import HttpClientView
            self.http_client_view = HttpClientView(
                self._saved_page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 切换到 HTTP 客户端视图
        if self.parent_container:
            self.current_sub_view = self.http_client_view
            self.current_sub_view_type = "http_client"
            self.parent_container.content = self.http_client_view
        self._safe_page_update()
    
    def _open_websocket_client(self, e: ft.ControlEvent) -> None:
        """打开 WebSocket 客户端。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.websocket_client_view is None:
            from views.dev_tools.websocket_client_view import WebSocketClientView
            self.websocket_client_view = WebSocketClientView(
                self._saved_page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 切换到 WebSocket 客户端视图
        if self.parent_container:
            self.current_sub_view = self.websocket_client_view
            self.current_sub_view_type = "websocket_client"
            self.parent_container.content = self.websocket_client_view
        self._safe_page_update()
    
    def _open_encoder_decoder(self, e: ft.ControlEvent) -> None:
        """打开编码/解码工具。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.encoder_decoder_view is None:
            from views.dev_tools.encoder_decoder_view import EncoderDecoderView
            self.encoder_decoder_view = EncoderDecoderView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        # 切换到编码/解码工具视图
        if self.parent_container:
            self.current_sub_view = self.encoder_decoder_view
            self.current_sub_view_type = "encoder_decoder"
            self.parent_container.content = self.encoder_decoder_view
        self._safe_page_update()
    
    def _open_regex_tester(self, e: ft.ControlEvent) -> None:
        """打开正则表达式测试器。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.regex_tester_view is None:
            from views.dev_tools.regex_tester_view import RegexTesterView
            self.regex_tester_view = RegexTesterView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        # 切换到正则表达式测试器视图
        if self.parent_container:
            self.current_sub_view = self.regex_tester_view
            self.current_sub_view_type = "regex_tester"
            self.parent_container.content = self.regex_tester_view
        self._safe_page_update()
    
    def _open_timestamp_tool(self, e: ft.ControlEvent) -> None:
        """打开时间工具。"""
        # 隐藏搜索按钮
        self._hide_search_button()
        
        if self.timestamp_tool_view is None:
            from views.dev_tools.timestamp_tool_view import TimestampToolView
            self.timestamp_tool_view = TimestampToolView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        # 切换到时间工具视图
        if self.parent_container:
            self.current_sub_view = self.timestamp_tool_view
            self.current_sub_view_type = "timestamp_tool"
            self.parent_container.content = self.timestamp_tool_view
        self._safe_page_update()
    
    def _open_jwt_tool(self, e: ft.ControlEvent) -> None:
        """打开 JWT 工具。"""
        self._hide_search_button()
        
        if self.jwt_tool_view is None:
            from views.dev_tools.jwt_tool_view import JwtToolView
            self.jwt_tool_view = JwtToolView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.jwt_tool_view
            self.current_sub_view_type = "jwt_tool"
            self.parent_container.content = self.jwt_tool_view
        self._safe_page_update()
    
    def _open_uuid_generator(self, e: ft.ControlEvent) -> None:
        """打开 UUID 生成器。"""
        self._hide_search_button()
        
        if self.uuid_generator_view is None:
            from views.dev_tools.uuid_generator_view import UuidGeneratorView
            self.uuid_generator_view = UuidGeneratorView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.uuid_generator_view
            self.current_sub_view_type = "uuid_generator"
            self.parent_container.content = self.uuid_generator_view
        self._safe_page_update()
    
    def _open_color_tool(self, e: ft.ControlEvent) -> None:
        """打开颜色工具。"""
        self._hide_search_button()
        
        if self.color_tool_view is None:
            from views.dev_tools.color_tool_view import ColorToolView
            self.color_tool_view = ColorToolView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.color_tool_view
            self.current_sub_view_type = "color_tool"
            self.parent_container.content = self.color_tool_view
        self._safe_page_update()
    
    def _open_markdown_viewer(self, e: ft.ControlEvent) -> None:
        """打开 Markdown 预览器。"""
        self._hide_search_button()
        
        if self.markdown_viewer_view is None:
            from views.dev_tools.markdown_viewer_view import MarkdownViewerView
            self.markdown_viewer_view = MarkdownViewerView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.markdown_viewer_view
            self.current_sub_view_type = "markdown_viewer"
            self.parent_container.content = self.markdown_viewer_view
        self._safe_page_update()
    
    def _open_dns_lookup(self, e: ft.ControlEvent) -> None:
        """打开 DNS 查询工具。"""
        self._hide_search_button()
        
        if self.dns_lookup_view is None:
            from views.dev_tools.dns_lookup_view import DnsLookupView
            self.dns_lookup_view = DnsLookupView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.dns_lookup_view
            self.current_sub_view_type = "dns_lookup"
            self.parent_container.content = self.dns_lookup_view
        self._safe_page_update()
    
    def _open_port_scanner(self, e: ft.ControlEvent) -> None:
        """打开端口扫描工具。"""
        self._hide_search_button()
        
        if self.port_scanner_view is None:
            from views.dev_tools.port_scanner_view import PortScannerView
            self.port_scanner_view = PortScannerView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.port_scanner_view
            self.current_sub_view_type = "port_scanner"
            self.parent_container.content = self.port_scanner_view
        self._safe_page_update()

    def _open_format_convert(self, e: ft.ControlEvent) -> None:
        """打开数据格式转换工具。"""
        self._hide_search_button()
        
        if self.format_convert_view is None:
            from views.dev_tools.format_convert_view import FormatConvertView
            self.format_convert_view = FormatConvertView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.format_convert_view
            self.current_sub_view_type = "format_convert"
            self.parent_container.content = self.format_convert_view
        self._safe_page_update()

    def _open_text_diff(self, e: ft.ControlEvent) -> None:
        """打开文本对比工具。"""
        self._hide_search_button()

        if self.text_diff_view is None:
            from views.dev_tools.text_diff_view import TextDiffView
            self.text_diff_view = TextDiffView(
                self._saved_page,
                on_back=self._back_to_main
            )

        if self.parent_container:
            self.current_sub_view = self.text_diff_view
            self.current_sub_view_type = "text_diff"
            self.parent_container.content = self.text_diff_view
        self._safe_page_update()

    def _open_crypto_tool(self, e: ft.ControlEvent) -> None:
        """打开加解密工具。"""
        self._hide_search_button()
        
        if self.crypto_tool_view is None:
            from views.dev_tools.crypto_tool_view import CryptoToolView
            self.crypto_tool_view = CryptoToolView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.crypto_tool_view
            self.current_sub_view_type = "crypto_tool"
            self.parent_container.content = self.crypto_tool_view
        self._safe_page_update()
    
    def _open_sql_formatter(self, e: ft.ControlEvent) -> None:
        """打开SQL格式化工具。"""
        self._hide_search_button()
        
        if self.sql_formatter_view is None:
            from views.dev_tools.sql_formatter_view import SqlFormatterView
            self.sql_formatter_view = SqlFormatterView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.sql_formatter_view
            self.current_sub_view_type = "sql_formatter"
            self.parent_container.content = self.sql_formatter_view
        self._safe_page_update()
    
    def _open_cron_tool(self, e: ft.ControlEvent) -> None:
        """打开Cron表达式工具。"""
        self._hide_search_button()
        
        if self.cron_tool_view is None:
            from views.dev_tools.cron_tool_view import CronToolView
            self.cron_tool_view = CronToolView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        if self.parent_container:
            self.current_sub_view = self.cron_tool_view
            self.current_sub_view_type = "cron_tool"
            self.parent_container.content = self.cron_tool_view
        self._safe_page_update()
    
    def _back_to_main(self) -> None:
        """返回主界面（使用路由导航）。"""
        import gc
        
        # 销毁当前子视图（而不是保留）
        if self.current_sub_view_type:
            view_map = {
                "encoding_convert": "encoding_convert_view",
                "base64_to_image": "base64_to_image_view",
                "http_client": "http_client_view",
                "websocket_client": "websocket_client_view",
                "encoder_decoder": "encoder_decoder_view",
                "regex_tester": "regex_tester_view",
                "timestamp_tool": "timestamp_tool_view",
                "jwt_tool": "jwt_tool_view",
                "uuid_generator": "uuid_generator_view",
                "color_tool": "color_tool_view",
                "markdown_viewer": "markdown_viewer_view",
                "dns_lookup": "dns_lookup_view",
                "port_scanner": "port_scanner_view",
                "format_convert": "format_convert_view",
                "text_diff": "text_diff_view",
                "crypto_tool": "crypto_tool_view",
                "sql_formatter": "sql_formatter_view",
                "cron_tool": "cron_tool_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                # 在销毁前调用 cleanup 方法（如果存在）
                view_instance = getattr(self, view_attr, None)
                if view_instance and hasattr(view_instance, 'cleanup'):
                    try:
                        view_instance.cleanup()
                    except Exception:
                        pass
                setattr(self, view_attr, None)
        
        # 清除子视图状态
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        # 强制垃圾回收释放内存
        gc.collect()
        
        # 直接恢复主界面（不依赖路由，因为打开工具时也是直接切换内容的）
        if self.parent_container:
            self.parent_container.content = self
            self._show_search_button()
            self._safe_page_update()
    
    def restore_state(self) -> bool:
        """恢复之前的视图状态。
        
        Returns:
            是否成功恢复到子视图
        """
        if self.current_sub_view and self.parent_container:
            self.parent_container.content = self.current_sub_view
            self._safe_page_update()
            return True
        return False
    
    def open_tool(self, tool_name: str) -> None:
        """根据工具名称打开对应的工具。
        
        Args:
            tool_name: 工具名称，如 "encoding", "json_viewer", "base64_to_image", "http_client", "websocket_client" 等
        """
        # tool_name 到 current_sub_view_type 的映射（处理不一致的命名）
        tool_to_view_type = {
            "encoding": "encoding_convert",
        }
        expected_view_type = tool_to_view_type.get(tool_name, tool_name)
        
        # 如果当前已经打开了该工具，直接返回现有视图，不创建新实例
        if self.current_sub_view_type == expected_view_type and self.current_sub_view is not None:
            # 确保当前视图显示在容器中
            if self.parent_container and self.parent_container.content != self.current_sub_view:
                self.parent_container.content = self.current_sub_view
                self._safe_page_update()
            return
        
        # 记录工具使用次数
        from utils import get_tool
        tool_id = f"dev.{tool_name}"
        tool_meta = get_tool(tool_id)
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 工具名称到方法的映射
        tool_map = {
            "encoding": self._open_encoding_convert,
            "json_viewer": self._open_json_viewer,
            "base64_to_image": self._open_base64_to_image,
            "http_client": self._open_http_client,
            "websocket_client": self._open_websocket_client,
            "encoder_decoder": self._open_encoder_decoder,
            "regex_tester": self._open_regex_tester,
            "timestamp_tool": self._open_timestamp_tool,
            "jwt_tool": self._open_jwt_tool,
            "uuid_generator": self._open_uuid_generator,
            "color_tool": self._open_color_tool,
            "markdown_viewer": self._open_markdown_viewer,
            "dns_lookup": self._open_dns_lookup,
            "port_scanner": self._open_port_scanner,
            "format_convert": self._open_format_convert,
            "text_diff": self._open_text_diff,
            "crypto_tool": self._open_crypto_tool,
            "sql_formatter": self._open_sql_formatter,
            "cron_tool": self._open_cron_tool,
        }
        
        # 查找并调用对应的方法
        if tool_name in tool_map:
            tool_map[tool_name](None)  # 传递 None 作为事件参数
            
            # 处理从推荐视图传递的待处理文件
            if hasattr(self._saved_page, '_pending_drop_files') and self._saved_page._pending_drop_files:
                pending_files = self._saved_page._pending_drop_files
                self._saved_page._pending_drop_files = None
                self._saved_page._pending_tool_id = None
                
                # 让当前子视图处理文件
                if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
                    self.current_sub_view.add_files(pending_files)
    
    def _on_scroll(self, e: ft.OnScrollEvent) -> None:
        """跟踪滚动位置。"""
        self._scroll_offset_y = e.pixels
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            duration=3000,
        )
        self._saved_page.overlay.append(snackbar)
        snackbar.open = True
        self._saved_page.update()
    
    def handle_dropped_files_at(self, files: list, x: int, y: int) -> None:
        """处理拖放到指定位置的文件。
        
        Args:
            files: 文件路径列表（Path 对象）
            x: 鼠标 X 坐标（相对于窗口客户区）
            y: 鼠标 Y 坐标（相对于窗口客户区）
        """
        # 如果当前显示的是子视图，让子视图处理
        if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
            self.current_sub_view.add_files(files)
            return
        
        # 计算点击的是哪个工具卡片
        nav_width = 100  # 导航栏宽度
        title_height = 32  # 系统标题栏高度
        category_header_height = 60  # 分类标题区域高度
        
        # 调整坐标
        local_x = x - nav_width - self._content_padding
        local_y = y - title_height - category_header_height - self._content_padding + self._scroll_offset_y
        
        if local_x < 0 or local_y < 0:
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        # 计算行列
        col = int(local_x // self._card_step_x)
        row = int(local_y // self._card_step_y)
        
        # 根据实际窗口宽度计算每行卡片数
        window_width = self._saved_page.window.width or 1000
        content_width = window_width - nav_width - self._content_padding * 2
        cols_per_row = max(1, int(content_width // self._card_step_x))
        
        index = row * cols_per_row + col
        
        if index < 0 or index >= len(self._drop_tool_map):
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        tool_name, supported_exts, open_func, view_attr, accept_any = self._drop_tool_map[index]
        
        if not open_func:
            self._show_snackbar(f"「{tool_name}」不支持文件拖放")
            return
        
        # 展开文件夹
        all_files = []
        for f in files:
            if f.is_dir():
                for item in f.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(f)
        
        # 过滤文件（如果 accept_any 为 True，则接受所有文件）
        if accept_any:
            supported_files = all_files
        else:
            supported_files = [f for f in all_files if f.suffix.lower() in supported_exts]
        
        if not supported_files:
            self._show_snackbar(f"「{tool_name}」不支持该格式")
            return
        
        # 保存待处理的文件
        self._pending_drop_files = supported_files
        self._pending_view_attr = view_attr
        
        # 打开工具
        open_func(None)
        
        # 导入文件到工具
        self._import_pending_files()
    
    def _import_pending_files(self) -> None:
        """将待处理文件导入到当前工具视图。"""
        if not hasattr(self, '_pending_drop_files') or not self._pending_drop_files:
            return
        
        # 直接使用 current_sub_view，因为有些视图（如 JSON 查看器）没有保存到类属性
        if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
            self.current_sub_view.add_files(self._pending_drop_files)
        
        self._pending_drop_files = []
        self._pending_view_attr = None
