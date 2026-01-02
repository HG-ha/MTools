# -*- coding: utf-8 -*-
"""Markdown 预览器视图模块。

提供 Markdown 实时预览和转 HTML 功能。
"""

from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class MarkdownViewerView(ft.Container):
    """Markdown 预览器视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化 Markdown 预览器视图。
        
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
        self.markdown_input = ft.Ref[ft.TextField]()
        self.markdown_preview = ft.Ref[ft.Markdown]()
        self.html_output = ft.Ref[ft.TextField]()
        self.preview_container = ft.Ref[ft.Container]()
        self.status_line_text_ref = ft.Ref[ft.Text]()
        self.status_char_text_ref = ft.Ref[ft.Text]()
        self.status_word_text_ref = ft.Ref[ft.Text]()
        self.preview_toggle_btn_ref = ft.Ref[ft.IconButton]()
        
        # 布局引用（拖动调整）
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.GestureDetector]()
        self.content_area_ref = ft.Ref[ft.Row]()
        self.ratio = 0.5
        self.left_flex = 500
        self.right_flex = 500
        self.is_dragging = False
        
        # 编辑器状态
        self._line_count = 1
        self._preview_visible = False  # 默认关闭预览
        
        # 主题配置
        self._current_theme = "default"
        self._themes = {
            "default": {
                "name": "默认",
                "icon": ft.Icons.LIGHT_MODE,
                "bg_color": ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                "text_color": None,  # 使用系统默认
                "code_bg": ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            },
            "github": {
                "name": "GitHub",
                "icon": ft.Icons.CODE,
                "bg_color": "#ffffff",
                "text_color": "#24292f",
                "code_bg": "#f6f8fa",
            },
            "dark": {
                "name": "暗黑",
                "icon": ft.Icons.DARK_MODE,
                "bg_color": "#1e1e1e",
                "text_color": "#d4d4d4",
                "code_bg": "#2d2d2d",
            },
            "sepia": {
                "name": "护眼",
                "icon": ft.Icons.REMOVE_RED_EYE,
                "bg_color": "#f4ecd8",
                "text_color": "#5b4636",
                "code_bg": "#e8dcc8",
            },
            "nord": {
                "name": "Nord",
                "icon": ft.Icons.AC_UNIT,
                "bg_color": "#2e3440",
                "text_color": "#eceff4",
                "code_bg": "#3b4252",
            },
            "solarized_light": {
                "name": "Solarized",
                "icon": ft.Icons.WB_SUNNY,
                "bg_color": "#fdf6e3",
                "text_color": "#657b83",
                "code_bg": "#eee8d5",
            },
            "dracula": {
                "name": "Dracula",
                "icon": ft.Icons.NIGHTLIGHT,
                "bg_color": "#282a36",
                "text_color": "#f8f8f2",
                "code_bg": "#44475a",
            },
            "monokai": {
                "name": "Monokai",
                "icon": ft.Icons.TERMINAL,
                "bg_color": "#272822",
                "text_color": "#f8f8f2",
                "code_bg": "#3e3d32",
            },
        }
        self.preview_content_ref = ft.Ref[ft.Container]()
        self.theme_name_ref = ft.Ref[ft.Text]()
        
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
        
        container_width = self.page.width - PADDING_MEDIUM * 2 - 8
        if container_width <= 0:
            return
        
        delta_ratio = e.delta_x / container_width
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
                ft.Text("Markdown 预览器", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 编辑器工具栏
        editor_toolbar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.EDIT_NOTE, size=18, color=ft.Colors.PRIMARY),
                                ft.Text("编辑器", weight=ft.FontWeight.W_600, size=14),
                            ],
                            spacing=6,
                        ),
                    ),
                    ft.VerticalDivider(width=12, thickness=1),
                    # 格式化工具按钮组 - 文本样式
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.FORMAT_BOLD,
                                    tooltip="粗体 **text**",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_format("**", "**"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FORMAT_ITALIC,
                                    tooltip="斜体 *text*",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_format("*", "*"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FORMAT_STRIKETHROUGH,
                                    tooltip="删除线 ~~text~~",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_format("~~", "~~"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CODE,
                                    tooltip="行内代码 `code`",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_format("`", "`"),
                                ),
                            ],
                            spacing=0,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=2, vertical=2),
                    ),
                    # 结构元素按钮组
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.TITLE,
                                    tooltip="标题",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=self._show_heading_menu,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FORMAT_LIST_BULLETED,
                                    tooltip="无序列表",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("- "),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FORMAT_LIST_NUMBERED,
                                    tooltip="有序列表",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("1. "),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CHECKLIST,
                                    tooltip="任务列表",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("- [ ] "),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FORMAT_QUOTE,
                                    tooltip="引用",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("> "),
                                ),
                            ],
                            spacing=0,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=2, vertical=2),
                    ),
                    # 插入元素按钮组
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.LINK,
                                    tooltip="链接 [text](url)",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("[链接文字](https://example.com)"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.IMAGE,
                                    tooltip="图片 ![alt](url)",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("![图片描述](https://example.com/image.png)"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.TABLE_CHART,
                                    tooltip="表格",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_table(),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DATA_OBJECT,
                                    tooltip="代码块",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=self._show_code_block_menu,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.HORIZONTAL_RULE,
                                    tooltip="分割线",
                                    icon_size=18,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=6,
                                    ),
                                    on_click=lambda _: self._insert_text("\n---\n"),
                                ),
                            ],
                            spacing=0,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=2, vertical=2),
                    ),
                    ft.VerticalDivider(width=8, thickness=1),
                    # 预览切换按钮
                    ft.IconButton(
                        ref=self.preview_toggle_btn_ref,
                        icon=ft.Icons.VISIBILITY_OFF,
                        tooltip="打开预览",
                        icon_size=18,
                        icon_color=ft.Colors.SECONDARY,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=6,
                        ),
                        on_click=self._toggle_preview,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="清空内容",
                        icon_size=18,
                        icon_color=ft.Colors.ERROR,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=6,
                        ),
                        on_click=self._on_clear,
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,  # 允许工具栏横向滚动
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))),
        )
        
        # 编辑器主体（移除行号列，因为无法同步滚动）
        editor_body = ft.Container(
            content=ft.TextField(
                ref=self.markdown_input,
                multiline=True,
                min_lines=20,
                hint_text='# Hello Markdown\n\n在此输入 Markdown 内容...\n\n支持 GitHub Flavored Markdown 语法',
                hint_style=ft.TextStyle(
                    color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE),
                    italic=True,
                ),
                text_size=14,
                text_style=ft.TextStyle(
                    font_family="Consolas, Monaco, 'Courier New', monospace",
                    height=1.5,
                ),
                border=ft.InputBorder.NONE,
                cursor_color=ft.Colors.PRIMARY,
                cursor_width=2,
                selection_color=ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY),
                on_change=self._on_markdown_change,
                content_padding=ft.padding.all(16),
            ),
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        )
        
        # 编辑器状态栏
        editor_statusbar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text("Markdown", size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    ft.Container(width=8),
                    ft.Container(
                        content=ft.Text("UTF-8", size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    ),
                    ft.Container(width=8),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CIRCLE, size=6, color=ft.Colors.GREEN_400),
                                ft.Text("GFM", size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                            ],
                            spacing=4,
                        ),
                        tooltip="GitHub Flavored Markdown",
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        ref=self.status_word_text_ref,
                        value="字数: 0",
                        size=11,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                    ),
                    ft.Container(width=12),
                    ft.Text(
                        ref=self.status_char_text_ref,
                        value="字符: 0",
                        size=11,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                    ),
                    ft.Container(width=12),
                    ft.Text(
                        ref=self.status_line_text_ref,
                        value="行: 1",
                        size=11,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                    ),
                ],
                spacing=0,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
        )
        
        # 左侧：Markdown 编辑器（现代化设计）
        left_panel = ft.Container(
            ref=self.left_panel_ref,
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        editor_toolbar,
                        editor_body,
                        editor_statusbar,
                    ],
                    spacing=0,
                    expand=True,
                ),
                border=ft.border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                border_radius=10,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor=ft.Colors.SURFACE,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                expand=True,
            ),
            expand=self.left_flex,
        )
        
        # 分隔条
        divider = ft.GestureDetector(
            ref=self.divider_ref,
            content=ft.Container(
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
                margin=ft.margin.only(top=6, bottom=6),
            ),
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            on_pan_start=self._on_divider_pan_start,
            on_pan_update=self._on_divider_pan_update,
            on_pan_end=self._on_divider_pan_end,
            drag_interval=10,
            visible=False,  # 默认隐藏
        )
        
        # 预览区工具栏
        preview_toolbar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.PREVIEW, size=18, color=ft.Colors.SECONDARY),
                                ft.Text("预览", weight=ft.FontWeight.W_600, size=14),
                            ],
                            spacing=6,
                        ),
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                # 主题选择按钮
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.PALETTE, size=16, color=ft.Colors.SECONDARY),
                                            ft.Text(
                                                ref=self.theme_name_ref,
                                                value="默认",
                                                size=12,
                                                color=ft.Colors.SECONDARY,
                                            ),
                                            ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=ft.Colors.SECONDARY),
                                        ],
                                        spacing=4,
                                    ),
                                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                    border_radius=6,
                                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.SECONDARY),
                                    on_click=self._show_theme_menu,
                                    tooltip="选择预览主题",
                                ),
                                ft.Container(width=8),
                                ft.TextButton(
                                    text="复制 HTML",
                                    icon=ft.Icons.CODE,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                    ),
                                    on_click=self._copy_html,
                                ),
                            ],
                            spacing=4,
                        ),
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))),
        )
        
        # 右侧：预览区（现代化设计）
        right_panel = ft.Container(
            ref=self.right_panel_ref,
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        preview_toolbar,
                        ft.Container(
                            ref=self.preview_container,
                            content=ft.Column(
                                controls=[
                                    ft.Container(
                                        ref=self.preview_content_ref,
                                        content=ft.Markdown(
                                            ref=self.markdown_preview,
                                            value="# Hello Markdown\n\n在左侧输入 Markdown 内容，这里会实时显示预览。",
                                            selectable=True,
                                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                            on_tap_link=lambda e: self.page.launch_url(e.data),
                                            expand=True,
                                        ),
                                        expand=True,
                                        padding=ft.padding.all(20),
                                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                                        border_radius=8,
                                        margin=ft.margin.all(8),
                                    ),
                                ],
                                scroll=ft.ScrollMode.AUTO,
                                expand=True,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                            expand=True,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        ),
                    ],
                    spacing=0,
                    expand=True,
                ),
                border=ft.border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                border_radius=10,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor=ft.Colors.SURFACE,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                expand=True,
            ),
            expand=self.right_flex,
            visible=False,  # 默认隐藏
        )
        
        # 主内容区域
        content_area = ft.Row(
            ref=self.content_area_ref,
            controls=[left_panel, divider, right_panel],
            spacing=8,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
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
    
    def _toggle_preview(self, e):
        """切换预览面板的显示/隐藏。"""
        self._preview_visible = not self._preview_visible
        
        if self.right_panel_ref.current:
            self.right_panel_ref.current.visible = self._preview_visible
        if self.divider_ref.current:
            self.divider_ref.current.visible = self._preview_visible
        if self.preview_toggle_btn_ref.current:
            self.preview_toggle_btn_ref.current.icon = (
                ft.Icons.VISIBILITY if self._preview_visible else ft.Icons.VISIBILITY_OFF
            )
            self.preview_toggle_btn_ref.current.tooltip = (
                "关闭预览" if self._preview_visible else "打开预览"
            )
        
        # 如果打开预览，同步当前内容
        if self._preview_visible and self.markdown_input.current:
            markdown_content = self.markdown_input.current.value
            if markdown_content:
                self.markdown_preview.current.value = markdown_content
            else:
                self.markdown_preview.current.value = "*空白文档*"
        
        try:
            self.update()
        except (AssertionError, AttributeError):
            pass
    
    def _show_heading_menu(self, e):
        """显示标题级别选择菜单。"""
        def insert_heading(level):
            def handler(_):
                self.page.close(menu_dialog)
                self._insert_text("#" * level + " ")
            return handler
        
        menu_dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text("选择标题级别", size=16, weight=ft.FontWeight.W_600),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ListTile(
                            leading=ft.Text("H1", weight=ft.FontWeight.BOLD, size=20),
                            title=ft.Text("一级标题", size=14),
                            subtitle=ft.Text("# 标题", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_heading(1),
                        ),
                        ft.ListTile(
                            leading=ft.Text("H2", weight=ft.FontWeight.BOLD, size=18),
                            title=ft.Text("二级标题", size=14),
                            subtitle=ft.Text("## 标题", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_heading(2),
                        ),
                        ft.ListTile(
                            leading=ft.Text("H3", weight=ft.FontWeight.BOLD, size=16),
                            title=ft.Text("三级标题", size=14),
                            subtitle=ft.Text("### 标题", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_heading(3),
                        ),
                        ft.ListTile(
                            leading=ft.Text("H4", weight=ft.FontWeight.BOLD, size=15),
                            title=ft.Text("四级标题", size=14),
                            subtitle=ft.Text("#### 标题", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_heading(4),
                        ),
                        ft.ListTile(
                            leading=ft.Text("H5", weight=ft.FontWeight.BOLD, size=14),
                            title=ft.Text("五级标题", size=14),
                            subtitle=ft.Text("##### 标题", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_heading(5),
                        ),
                        ft.ListTile(
                            leading=ft.Text("H6", weight=ft.FontWeight.BOLD, size=13),
                            title=ft.Text("六级标题", size=14),
                            subtitle=ft.Text("###### 标题", size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_heading(6),
                        ),
                    ],
                    spacing=0,
                    tight=True,
                ),
                width=280,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self.page.close(menu_dialog)),
            ],
        )
        self.page.open(menu_dialog)
    
    def _show_code_block_menu(self, e):
        """显示代码块语言选择菜单。"""
        languages = [
            ("Python", "python"),
            ("JavaScript", "javascript"),
            ("TypeScript", "typescript"),
            ("Java", "java"),
            ("C/C++", "cpp"),
            ("C#", "csharp"),
            ("Go", "go"),
            ("Rust", "rust"),
            ("SQL", "sql"),
            ("HTML", "html"),
            ("CSS", "css"),
            ("JSON", "json"),
            ("YAML", "yaml"),
            ("Bash/Shell", "bash"),
            ("Markdown", "markdown"),
            ("纯文本", ""),
        ]
        
        def insert_code_block(lang):
            def handler(_):
                self.page.close(menu_dialog)
                self._insert_text(f"```{lang}\n代码\n```\n")
            return handler
        
        menu_dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text("选择代码语言", size=16, weight=ft.FontWeight.W_600),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.CODE, size=20),
                            title=ft.Text(name, size=14),
                            subtitle=ft.Text(f"```{lang}" if lang else "```", size=12, 
                                           color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                            on_click=insert_code_block(lang),
                            dense=True,
                        )
                        for name, lang in languages
                    ],
                    spacing=0,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=280,
                height=400,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self.page.close(menu_dialog)),
            ],
        )
        self.page.open(menu_dialog)
    
    def _insert_table(self):
        """插入表格模板。"""
        table_template = """| 列1 | 列2 | 列3 |
|------|------|------|
| 内容 | 内容 | 内容 |
| 内容 | 内容 | 内容 |
"""
        self._insert_text(table_template)
    
    def _show_theme_menu(self, e):
        """显示主题选择菜单。"""
        def apply_theme(theme_key):
            def handler(_):
                self.page.close(menu_dialog)
                self._apply_theme(theme_key)
            return handler
        
        theme_items = []
        for key, theme in self._themes.items():
            is_current = key == self._current_theme
            theme_items.append(
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(
                            theme["icon"], 
                            size=20,
                            color=ft.Colors.PRIMARY if is_current else ft.Colors.ON_SURFACE,
                        ),
                        width=36,
                        height=36,
                        border_radius=8,
                        bgcolor=theme["bg_color"] if isinstance(theme["bg_color"], str) else None,
                        border=ft.border.all(2, ft.Colors.PRIMARY) if is_current else ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                        alignment=ft.alignment.center,
                    ),
                    title=ft.Text(
                        theme["name"], 
                        size=14,
                        weight=ft.FontWeight.W_600 if is_current else ft.FontWeight.NORMAL,
                        color=ft.Colors.PRIMARY if is_current else None,
                    ),
                    trailing=ft.Icon(ft.Icons.CHECK, size=18, color=ft.Colors.PRIMARY) if is_current else None,
                    on_click=apply_theme(key),
                    dense=True,
                )
            )
        
        menu_dialog = ft.AlertDialog(
            modal=False,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PALETTE, size=22, color=ft.Colors.PRIMARY),
                    ft.Text("选择预览主题", size=16, weight=ft.FontWeight.W_600),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=theme_items,
                    spacing=2,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=300,
                height=400,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self.page.close(menu_dialog)),
            ],
        )
        self.page.open(menu_dialog)
    
    def _apply_theme(self, theme_key: str):
        """应用指定的主题到预览区。"""
        if theme_key not in self._themes:
            return
        
        self._current_theme = theme_key
        theme = self._themes[theme_key]
        
        # 更新主题名称显示
        if self.theme_name_ref.current:
            self.theme_name_ref.current.value = theme["name"]
            try:
                self.theme_name_ref.current.update()
            except (AssertionError, AttributeError):
                pass
        
        # 更新预览内容区域的样式
        if self.preview_content_ref.current:
            self.preview_content_ref.current.bgcolor = theme["bg_color"]
            try:
                self.preview_content_ref.current.update()
            except (AssertionError, AttributeError):
                pass
        
        # 更新 Markdown 组件的样式（如果支持）
        if self.markdown_preview.current and theme["text_color"]:
            # Flet 的 Markdown 组件样式通过 code_style 等属性设置
            # 这里主要通过容器背景色来实现主题效果
            pass
        
        self._show_snack(f"已切换到「{theme['name']}」主题")
    
    def _insert_format(self, prefix: str, suffix: str):
        """在光标位置插入格式化标记。"""
        if self.markdown_input.current:
            current_value = self.markdown_input.current.value or ""
            # 简单实现：在末尾添加格式化文本
            new_text = f"{prefix}文本{suffix}"
            self.markdown_input.current.value = current_value + new_text
            self._on_markdown_change(None)
            self.markdown_input.current.focus()
    
    def _insert_text(self, text: str):
        """在光标位置插入文本。"""
        if self.markdown_input.current:
            current_value = self.markdown_input.current.value or ""
            # 如果当前内容不为空且不以换行结尾，先添加换行
            if current_value and not current_value.endswith('\n'):
                text = '\n' + text
            self.markdown_input.current.value = current_value + text
            self._on_markdown_change(None)
            self.markdown_input.current.focus()
    
    def _update_line_numbers(self, text: str):
        """更新统计信息。"""
        lines = text.split('\n') if text else ['']
        line_count = len(lines)
        
        # 更新统计信息
        char_count = len(text)
        # 计算字数（中文按字计算，英文按单词计算）
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        word_count = chinese_chars + english_words
        
        # 更新状态栏文本
        if self.status_line_text_ref.current:
            self.status_line_text_ref.current.value = f"行: {line_count}"
            try:
                self.status_line_text_ref.current.update()
            except (AssertionError, AttributeError):
                pass
        
        if self.status_char_text_ref.current:
            self.status_char_text_ref.current.value = f"字符: {char_count}"
            try:
                self.status_char_text_ref.current.update()
            except (AssertionError, AttributeError):
                pass
        
        if self.status_word_text_ref.current:
            self.status_word_text_ref.current.value = f"字数: {word_count}"
            try:
                self.status_word_text_ref.current.update()
            except (AssertionError, AttributeError):
                pass
    
    def _on_markdown_change(self, e):
        """Markdown 内容改变时更新预览。"""
        markdown_content = self.markdown_input.current.value
        
        # 只在预览可见时更新预览内容
        if self._preview_visible:
            if markdown_content:
                self.markdown_preview.current.value = markdown_content
            else:
                self.markdown_preview.current.value = "*空白文档*"
            
            try:
                self.markdown_preview.current.update()
            except (AssertionError, AttributeError):
                pass
        
        # 始终更新行号和统计信息
        self._update_line_numbers(markdown_content or "")
    
    def _on_clear(self, e):
        """清空编辑器。"""
        self.markdown_input.current.value = ""
        self.markdown_preview.current.value = "*空白文档*"
        self._line_count = 0  # 重置行数以强制更新
        self._update_line_numbers("")
        self.update()
    
    def _copy_html(self, e):
        """复制 HTML 代码。"""
        markdown_content = self.markdown_input.current.value
        if not markdown_content:
            self._show_snack("没有可转换的内容", error=True)
            return
        
        # 使用简单的 Markdown 转 HTML（基础实现）
        html_content = self._markdown_to_html(markdown_content)
        
        self.page.set_clipboard(html_content)
        self._show_snack("HTML 已复制到剪贴板")
    
    def _markdown_to_html(self, markdown: str) -> str:
        """简单的 Markdown 转 HTML 转换。"""
        # 这是一个非常简化的实现
        # 实际生产环境建议使用 markdown 库
        import re
        
        html = markdown
        
        # 标题
        html = re.sub(r'^######\s+(.+)$', r'<h6>\1</h6>', html, flags=re.MULTILINE)
        html = re.sub(r'^#####\s+(.+)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
        html = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # 粗体和斜体
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
        html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)
        
        # 代码
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
        
        # 链接
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
        
        # 换行
        html = html.replace('\n\n', '</p><p>')
        html = html.replace('\n', '<br>')
        
        # 包装
        html = f'<div>\n<p>{html}</p>\n</div>'
        
        return html
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = r"""
**Markdown 预览器使用说明**

**功能：**
- 实时 Markdown 预览（点击工具栏眼睛图标开启）
- 支持 GitHub Flavored Markdown (GFM)
- 多种预览主题可选
- 导出 HTML 代码
- 可拖动调整左右面板
- 字数、字符、行数统计

**支持的 Markdown 语法：**

```markdown
# 标题 1 ~ ###### 标题 6

**粗体** 或 __粗体__
*斜体* 或 _斜体_
~~删除线~~

[链接文字](https://example.com)
![图片](https://example.com/img.png)

`行内代码`

- 无序列表
1. 有序列表
- [ ] 任务列表

> 引用文本

| 表头1 | 表头2 |
|-------|-------|
| 内容  | 内容  |

---

\`\`\`python
# 代码块
print("Hello")
\`\`\`
```

**注意：** 本预览器使用 GitHub Flavored Markdown 标准，不支持 `==高亮==` 等扩展语法。

**快捷功能：**
- **预览切换**: 点击眼睛图标开启/关闭实时预览
- **主题切换**: 在预览区选择不同的显示主题
- **复制 HTML**: 将 Markdown 转换为 HTML 并复制
- **清空**: 清空编辑器内容
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
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件，加载第一个 Markdown 文件内容。
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        # 只处理第一个 Markdown 文件
        md_file = None
        md_exts = {'.md', '.markdown', '.mdown', '.mkd'}
        for f in files:
            if f.suffix.lower() in md_exts and f.is_file():
                md_file = f
                break
        
        if not md_file:
            return
        
        try:
            content = md_file.read_text(encoding='utf-8')
            if self.markdown_input.current:
                self.markdown_input.current.value = content
                self._on_markdown_change(None)  # 触发预览更新
            self._show_snack(f"已加载: {md_file.name}")
        except UnicodeDecodeError:
            try:
                content = md_file.read_text(encoding='gbk')
                if self.markdown_input.current:
                    self.markdown_input.current.value = content
                    self._on_markdown_change(None)
                self._show_snack(f"已加载: {md_file.name}")
            except Exception as e:
                self._show_snack(f"读取文件失败: {e}", error=True)
        except Exception as e:
            self._show_snack(f"读取文件失败: {e}", error=True)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
