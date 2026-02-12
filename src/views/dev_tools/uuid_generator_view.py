# -*- coding: utf-8 -*-
"""UUID/随机数生成器视图模块。

提供 UUID 生成、随机字符串、随机密码等功能。
"""

import random
import secrets
import string
import uuid
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class UuidGeneratorView(ft.Container):
    """UUID/随机数生成器视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化 UUID/随机数生成器视图。
        
        Args:
            page: Flet 页面对象
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self._page = page
        self.on_back = on_back
        self.expand = True
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 控件引用
        self.uuid_result = ft.Ref[ft.TextField]()
        self.random_length = ft.Ref[ft.TextField]()
        self.random_charset = ft.Ref[ft.Dropdown]()
        self.random_result = ft.Ref[ft.TextField]()
        self.password_length = ft.Ref[ft.TextField]()
        self.password_include_upper = ft.Ref[ft.Checkbox]()
        self.password_include_lower = ft.Ref[ft.Checkbox]()
        self.password_include_digits = ft.Ref[ft.Checkbox]()
        self.password_include_symbols = ft.Ref[ft.Checkbox]()
        self.password_result = ft.Ref[ft.TextField]()
        
        self._build_ui()
    
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
                ft.Text("UUID/随机数生成器", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # UUID 生成器
        uuid_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("UUID 生成器", weight=ft.FontWeight.BOLD, size=16),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content="生成 UUID v4 (随机)",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _: self._generate_uuid(4),
                            ),
                            ft.ElevatedButton(
                                content="生成 UUID v1 (时间戳)",
                                icon=ft.Icons.ACCESS_TIME,
                                on_click=lambda _: self._generate_uuid(1),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.TextField(
                        ref=self.uuid_result,
                        label="生成结果",
                        read_only=True,
                        suffix=ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.uuid_result.current.value),
                        ),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 随机字符串生成器
        random_string_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("随机字符串生成器", weight=ft.FontWeight.BOLD, size=16),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.random_length,
                                label="长度",
                                value="16",
                                width=100,
                            ),
                            ft.Dropdown(
                                ref=self.random_charset,
                                label="字符集",
                                width=250,
                                options=[
                                    ft.dropdown.Option("数字 (0-9)"),
                                    ft.dropdown.Option("小写字母 (a-z)"),
                                    ft.dropdown.Option("大写字母 (A-Z)"),
                                    ft.dropdown.Option("字母 (a-zA-Z)"),
                                    ft.dropdown.Option("字母+数字 (a-zA-Z0-9)"),
                                    ft.dropdown.Option("十六进制 (0-9a-f)"),
                                ],
                                value="字母+数字 (a-zA-Z0-9)",
                            ),
                            ft.ElevatedButton(
                                content="生成",
                                icon=ft.Icons.REFRESH,
                                on_click=self._generate_random_string,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.TextField(
                        ref=self.random_result,
                        label="生成结果",
                        read_only=True,
                        suffix=ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.random_result.current.value),
                        ),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 随机密码生成器
        password_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("随机密码生成器", weight=ft.FontWeight.BOLD, size=16),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.password_length,
                                label="长度",
                                value="16",
                                width=100,
                            ),
                            ft.Checkbox(
                                ref=self.password_include_upper,
                                label="大写字母 (A-Z)",
                                value=True,
                            ),
                            ft.Checkbox(
                                ref=self.password_include_lower,
                                label="小写字母 (a-z)",
                                value=True,
                            ),
                            ft.Checkbox(
                                ref=self.password_include_digits,
                                label="数字 (0-9)",
                                value=True,
                            ),
                            ft.Checkbox(
                                ref=self.password_include_symbols,
                                label="符号 (!@#$...)",
                                value=True,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                        wrap=True,
                    ),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content="生成密码",
                                icon=ft.Icons.LOCK,
                                on_click=self._generate_password,
                            ),
                        ],
                    ),
                    ft.TextField(
                        ref=self.password_result,
                        label="生成结果",
                        read_only=True,
                        password=True,
                        can_reveal_password=True,
                        suffix=ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.password_result.current.value),
                        ),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 布局
        content_area = ft.Column(
            controls=[
                uuid_section,
                ft.Container(height=PADDING_SMALL),
                random_string_section,
                ft.Container(height=PADDING_SMALL),
                password_section,
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 主列
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _generate_uuid(self, version: int):
        """生成 UUID。"""
        if version == 1:
            result = str(uuid.uuid1())
        else:  # version 4
            result = str(uuid.uuid4())
        
        self.uuid_result.current.value = result
        self.update()
        self._show_snack("UUID 已生成")
    
    def _generate_random_string(self, e):
        """生成随机字符串。"""
        try:
            length = int(self.random_length.current.value)
            if length <= 0 or length > 10000:
                self._show_snack("长度必须在 1-10000 之间", error=True)
                return
            
            charset_option = self.random_charset.current.value
            
            # 根据选项确定字符集
            if charset_option == "数字 (0-9)":
                charset = string.digits
            elif charset_option == "小写字母 (a-z)":
                charset = string.ascii_lowercase
            elif charset_option == "大写字母 (A-Z)":
                charset = string.ascii_uppercase
            elif charset_option == "字母 (a-zA-Z)":
                charset = string.ascii_letters
            elif charset_option == "字母+数字 (a-zA-Z0-9)":
                charset = string.ascii_letters + string.digits
            elif charset_option == "十六进制 (0-9a-f)":
                charset = string.hexdigits[:16]  # 0-9a-f
            else:
                charset = string.ascii_letters + string.digits
            
            # 使用 secrets 生成安全的随机字符串
            result = ''.join(secrets.choice(charset) for _ in range(length))
            
            self.random_result.current.value = result
            self.update()
            self._show_snack("随机字符串已生成")
            
        except ValueError:
            self._show_snack("请输入有效的长度", error=True)
    
    def _generate_password(self, e):
        """生成随机密码。"""
        try:
            length = int(self.password_length.current.value)
            if length <= 0 or length > 10000:
                self._show_snack("长度必须在 1-10000 之间", error=True)
                return
            
            # 构建字符集
            charset = ""
            if self.password_include_upper.current.value:
                charset += string.ascii_uppercase
            if self.password_include_lower.current.value:
                charset += string.ascii_lowercase
            if self.password_include_digits.current.value:
                charset += string.digits
            if self.password_include_symbols.current.value:
                charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"
            
            if not charset:
                self._show_snack("请至少选择一种字符类型", error=True)
                return
            
            # 使用 secrets 生成安全的密码
            result = ''.join(secrets.choice(charset) for _ in range(length))
            
            self.password_result.current.value = result
            self.update()
            self._show_snack("密码已生成")
            
        except ValueError:
            self._show_snack("请输入有效的长度", error=True)
    
    async def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        
        await ft.Clipboard().set(text)
        self._show_snack("已复制到剪贴板")
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**UUID/随机数生成器使用说明**

**1. UUID 生成器**
- **UUID v4 (随机)**：基于随机数生成，最常用
- **UUID v1 (时间戳)**：基于时间戳和 MAC 地址

**2. 随机字符串生成器**
- 支持多种字符集：数字、字母、字母+数字、十六进制
- 最大长度 10000 字符
- 使用加密安全的随机数生成器

**3. 随机密码生成器**
- 可自定义包含的字符类型
- 支持大小写字母、数字、符号
- 使用 secrets 模块（加密安全）
- 适合生成强密码

**安全说明**：
所有随机生成均使用 Python 的 `secrets` 模块，
适用于密码、令牌等安全敏感场景。
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
                ft.TextButton("关闭", on_click=lambda _: self._page.close(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.open(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
