# -*- coding: utf-8 -*-
"""正则表达式测试器视图模块。

提供正则表达式匹配测试和实时预览功能。
"""

import re
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class RegexTesterView(ft.Container):
    """正则表达式测试器视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化正则表达式测试器视图。
        
        Args:
            page: Flet 页面对象
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self.page = page
        self.on_back = on_back
        self.expand = True
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 控件引用
        self.regex_input = ft.Ref[ft.TextField]()
        self.test_text = ft.Ref[ft.TextField]()
        self.match_results = ft.Ref[ft.Column]()
        self.flags_ignorecase = ft.Ref[ft.Checkbox]()
        self.flags_multiline = ft.Ref[ft.Checkbox]()
        self.flags_dotall = ft.Ref[ft.Checkbox]()
        self.match_mode = ft.Ref[ft.Dropdown]()
        
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
                ft.Text("正则表达式测试器", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 正则表达式输入区
        regex_section = ft.Column(
            controls=[
                ft.Text("正则表达式", weight=ft.FontWeight.BOLD, size=16),
                ft.Container(
                    content=ft.TextField(
                        ref=self.regex_input,
                        hint_text=r'例如: \d{3}-\d{4}',
                        text_size=14,
                        border=ft.InputBorder.NONE,
                        on_change=lambda _: self._on_test(),
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                ),
            ],
            spacing=5,
        )
        
        # 选项栏
        options_section = ft.Row(
            controls=[
                ft.Text("选项:", weight=ft.FontWeight.BOLD),
                ft.Checkbox(
                    ref=self.flags_ignorecase,
                    label="忽略大小写 (i)",
                    on_change=lambda _: self._on_test(),
                ),
                ft.Checkbox(
                    ref=self.flags_multiline,
                    label="多行模式 (m)",
                    on_change=lambda _: self._on_test(),
                ),
                ft.Checkbox(
                    ref=self.flags_dotall,
                    label="点匹配所有 (s)",
                    on_change=lambda _: self._on_test(),
                ),
                ft.Container(width=20),
                ft.Dropdown(
                    ref=self.match_mode,
                    label="匹配模式",
                    width=150,
                    options=[
                        ft.dropdown.Option("全部匹配"),
                        ft.dropdown.Option("首次匹配"),
                    ],
                    value="全部匹配",
                    on_change=lambda _: self._on_test(),
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 测试文本区
        test_text_section = ft.Column(
            controls=[
                ft.Text("测试文本", weight=ft.FontWeight.BOLD, size=16),
                ft.Container(
                    content=ft.TextField(
                        ref=self.test_text,
                        multiline=True,
                        min_lines=10,
                        hint_text='在此输入要测试的文本...',
                        text_size=13,
                        border=ft.InputBorder.NONE,
                        on_change=lambda _: self._on_test(),
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    expand=True,
                ),
            ],
            spacing=5,
            expand=True,
        )
        
        # 匹配结果区
        match_results_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("匹配结果", weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(expand=True),
                        ft.OutlinedButton(
                            text="清空",
                            icon=ft.Icons.CLEAR,
                            on_click=self._on_clear,
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.Column(
                        ref=self.match_results,
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Icon(ft.Icons.SEARCH, size=48, color=ft.Colors.GREY_400),
                                        ft.Text("匹配结果将显示在这里", color=ft.Colors.GREY_500, size=14),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                expand=True,
                                alignment=ft.alignment.center,
                            ),
                        ],
                        spacing=5,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    expand=True,
                ),
            ],
            spacing=5,
            expand=True,
        )
        
        # 左右分栏
        content_area = ft.Row(
            controls=[
                ft.Container(content=test_text_section, expand=1),
                ft.Container(content=match_results_section, expand=1),
            ],
            spacing=PADDING_MEDIUM,
            expand=True,
        )
        
        # 主列
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(),
                regex_section,
                options_section,
                ft.Container(height=PADDING_SMALL),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _on_test(self):
        """执行正则匹配测试。"""
        regex_pattern = self.regex_input.current.value
        test_text = self.test_text.current.value
        
        # 清空之前的结果
        self.match_results.current.controls.clear()
        
        if not regex_pattern:
            self.match_results.current.controls.append(
                ft.Container(
                    content=ft.Text("请输入正则表达式", color=ft.Colors.GREY_500),
                    padding=10,
                )
            )
            self.update()
            return
        
        if not test_text:
            self.match_results.current.controls.append(
                ft.Container(
                    content=ft.Text("请输入测试文本", color=ft.Colors.GREY_500),
                    padding=10,
                )
            )
            self.update()
            return
        
        # 构建标志
        flags = 0
        if self.flags_ignorecase.current.value:
            flags |= re.IGNORECASE
        if self.flags_multiline.current.value:
            flags |= re.MULTILINE
        if self.flags_dotall.current.value:
            flags |= re.DOTALL
        
        try:
            # 编译正则表达式
            pattern = re.compile(regex_pattern, flags)
            
            # 执行匹配
            if self.match_mode.current.value == "全部匹配":
                matches = list(pattern.finditer(test_text))
            else:
                match = pattern.search(test_text)
                matches = [match] if match else []
            
            if not matches:
                self.match_results.current.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CLOSE, color=ft.Colors.RED, size=20),
                                ft.Text("没有找到匹配", color=ft.Colors.RED),
                            ],
                            spacing=5,
                        ),
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
                        border_radius=4,
                    )
                )
            else:
                # 显示匹配统计
                self.match_results.current.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=20),
                                ft.Text(f"找到 {len(matches)} 个匹配", color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=5,
                        ),
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
                        border_radius=4,
                    )
                )
                
                # 显示每个匹配
                for i, match in enumerate(matches, 1):
                    # 匹配项
                    match_item = ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(f"匹配 {i}", weight=ft.FontWeight.BOLD, size=13),
                                    ft.Container(expand=True),
                                    ft.IconButton(
                                        icon=ft.Icons.COPY,
                                        icon_size=16,
                                        tooltip="复制",
                                        on_click=lambda _, m=match.group(0): self._copy_text(m),
                                    ),
                                ],
                            ),
                            ft.Container(
                                content=ft.Text(
                                    match.group(0),
                                    selectable=True,
                                    color=ft.Colors.BLUE,
                                    font_family="Consolas,monospace",
                                ),
                                padding=5,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE),
                                border_radius=4,
                            ),
                            ft.Text(
                                f"位置: {match.start()} - {match.end()}",
                                size=11,
                                color=ft.Colors.GREY,
                            ),
                        ],
                        spacing=3,
                    )
                    
                    # 如果有分组，显示分组
                    if match.groups():
                        groups_info = []
                        for j, group in enumerate(match.groups(), 1):
                            if group is not None:
                                groups_info.append(
                                    ft.Text(
                                        f"  组 {j}: {group}",
                                        size=12,
                                        color=ft.Colors.PURPLE,
                                        font_family="Consolas,monospace",
                                    )
                                )
                        if groups_info:
                            match_item.controls.append(
                                ft.Column(controls=groups_info, spacing=2)
                            )
                    
                    self.match_results.current.controls.append(
                        ft.Container(
                            content=match_item,
                            padding=10,
                            border=ft.border.all(1, ft.Colors.OUTLINE),
                            border_radius=4,
                        )
                    )
            
            self.update()
            
        except re.error as e:
            self.match_results.current.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=20),
                                    ft.Text("正则表达式错误", color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
                                ],
                                spacing=5,
                            ),
                            ft.Text(str(e), size=12, color=ft.Colors.RED),
                        ],
                        spacing=5,
                    ),
                    padding=10,
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
                    border_radius=4,
                )
            )
            self.update()
    
    def _on_clear(self, e):
        """清空所有输入。"""
        self.regex_input.current.value = ""
        self.test_text.current.value = ""
        self.match_results.current.controls.clear()
        self.match_results.current.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SEARCH, size=48, color=ft.Colors.GREY_400),
                        ft.Text("匹配结果将显示在这里", color=ft.Colors.GREY_500, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                expand=True,
                alignment=ft.alignment.center,
            )
        )
        self.update()
    
    def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
        self.page.set_clipboard(text)
        self._show_snack("已复制到剪贴板")
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**正则表达式测试器使用说明**

**基本用法：**
1. 在顶部输入正则表达式
2. 选择匹配选项（忽略大小写、多行模式等）
3. 在左侧输入要测试的文本
4. 实时查看右侧的匹配结果

**匹配选项：**
- **忽略大小写 (i)**: 不区分大小写
- **多行模式 (m)**: ^ 和 $ 匹配每行的开始和结束
- **点匹配所有 (s)**: . 可以匹配换行符
- **匹配模式**: 全部匹配 或 仅首次匹配

**常用正则表达式示例：**

- **邮箱**: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}`
- **手机号**: `1[3-9]\\d{9}`
- **URL**: `https?://[\\w\\-]+(\\.[\\w\\-]+)+[/#?]?.*$`
- **IP 地址**: `\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b`
- **日期**: `\\d{4}-\\d{2}-\\d{2}`
- **时间**: `\\d{2}:\\d{2}(:\\d{2})?`

**分组捕获：**
使用括号 `()` 创建捕获组，匹配结果会显示每个组的内容。

例如：`(\\d{3})-(\\d{4})` 匹配 "123-4567" 会显示：
- 组 1: 123
- 组 2: 4567
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
                width=550,
                height=450,
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

