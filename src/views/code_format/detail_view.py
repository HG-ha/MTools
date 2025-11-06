# -*- coding: utf-8 -*-
"""代码格式化详细视图模块。

提供代码格式化功能的详细界面。
"""

from typing import Callable, Optional

import flet as ft

from constants import PADDING_LARGE, PADDING_MEDIUM, PADDING_SMALL, PADDING_XLARGE
from services import ConfigService


class CodeFormatDetailView(ft.Container):
    """代码格式化详细视图类。
    
    提供代码格式化相关功能的用户界面，包括：
    - 多语言代码格式化
    - 代码美化
    - 实时预览
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化代码格式化视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.on_back: Optional[Callable] = on_back
        self.expand: bool = True
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 返回按钮
        back_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_size=24,
            tooltip="返回",
            on_click=self._go_back,
        )
        
        # 标题
        title = ft.Text(
            "代码格式化",
            size=28,
            weight=ft.FontWeight.BOLD,
        )
        
        # 标题栏
        title_bar = ft.Container(
            content=ft.Row(
                controls=[
                    back_button,
                    title,
                ],
                spacing=PADDING_SMALL,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(
                left=PADDING_LARGE,
                right=PADDING_XLARGE,
                top=PADDING_LARGE,
                bottom=PADDING_MEDIUM,
            ),
        )
        
        # 语言选择
        self.language_dropdown = ft.Dropdown(
            label="编程语言",
            options=[
                ft.dropdown.Option("python", "Python"),
                ft.dropdown.Option("javascript", "JavaScript"),
                ft.dropdown.Option("typescript", "TypeScript"),
                ft.dropdown.Option("java", "Java"),
                ft.dropdown.Option("cpp", "C++"),
                ft.dropdown.Option("json", "JSON"),
                ft.dropdown.Option("xml", "XML"),
                ft.dropdown.Option("html", "HTML"),
                ft.dropdown.Option("css", "CSS"),
            ],
            value="python",
            width=200,
        )
        
        # 代码输入区域
        self.code_input = ft.TextField(
            label="输入代码",
            multiline=True,
            min_lines=15,
            max_lines=25,
            expand=True,
            hint_text="粘贴或输入需要格式化的代码...",
        )
        
        # 格式化按钮
        format_button = ft.ElevatedButton(
            "格式化代码",
            icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
            on_click=self._format_code,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
        )
        
        # 复制按钮
        copy_button = ft.OutlinedButton(
            "复制结果",
            icon=ft.Icons.COPY_ROUNDED,
            on_click=self._copy_result,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
        )
        
        # 输出区域
        self.output_text = ft.TextField(
            label="格式化结果",
            multiline=True,
            min_lines=15,
            max_lines=25,
            expand=True,
            read_only=True,
            value="",
        )
        
        # 提示信息
        info_card = ft.Card(
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO_ROUNDED, color=ft.Colors.BLUE_400),
                        ft.Text(
                            "功能开发中：完整的代码格式化功能将在后续版本中提供。",
                            size=14,
                            color=ft.Colors.BLUE_700,
                        ),
                    ],
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
            ),
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                title_bar,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            info_card,
                            self.language_dropdown,
                            self.code_input,
                            ft.Container(
                                content=ft.Row(
                                    controls=[format_button, copy_button],
                                    spacing=PADDING_MEDIUM,
                                ),
                                padding=ft.padding.symmetric(vertical=PADDING_SMALL),
                            ),
                            self.output_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=ft.padding.only(
                        left=PADDING_XLARGE,
                        right=PADDING_XLARGE,
                        bottom=PADDING_XLARGE,
                    ),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
    
    def _format_code(self, e: ft.ControlEvent) -> None:
        """格式化代码。"""
        code = self.code_input.value
        if not code or not code.strip():
            self._show_snackbar("请输入代码", ft.Colors.ORANGE_700)
            return
        
        language = self.language_dropdown.value
        
        # 这里是格式化逻辑的占位符
        # 在实际实现中，可以调用对应语言的格式化工具
        # 例如：autopep8 for Python, prettier for JS/TS等
        
        self.output_text.value = f"[{language}格式化功能开发中]\n\n原始代码：\n{code}"
        self._show_snackbar("格式化功能开发中", ft.Colors.BLUE_700)
        self.page.update()
    
    def _copy_result(self, e: ft.ControlEvent) -> None:
        """复制格式化结果。"""
        if self.output_text.value:
            self.page.set_clipboard(self.output_text.value)
            self._show_snackbar("已复制到剪贴板", ft.Colors.GREEN_700)
        else:
            self._show_snackbar("没有可复制的内容", ft.Colors.ORANGE_700)
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _go_back(self, e: ft.ControlEvent) -> None:
        """返回上一级视图。"""
        # 调用返回回调
        if self.on_back:
            self.on_back()

