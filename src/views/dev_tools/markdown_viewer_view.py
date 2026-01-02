# -*- coding: utf-8 -*-
"""Markdown 编辑器视图模块。

提供 Markdown 编辑、实时预览和转 HTML 功能。
"""

import threading
from pathlib import Path
from typing import Callable, Optional, Dict, List

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class MarkdownViewerView(ft.Container):
    """Markdown 编辑器视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化 Markdown 编辑器视图。
        
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
        
        # 工作区状态
        self._workspace_path: Optional[Path] = None
        self._current_file: Optional[Path] = None
        self._file_modified = False
        self._md_files: List[Path] = []
        self._expanded_folders: set = set()  # 记录展开的文件夹
        
        # 标签页状态：{file_path: {"content": str, "modified": bool}}
        # 使用特殊键 "untitled" 表示未保存的新文件
        self._open_tabs: Dict[Path | str, Dict] = {}
        self._tab_order: List[Path | str] = []  # 标签页顺序
        self._untitled_counter = 0  # 未命名文件计数器
        
        # 自动保存
        self._auto_save_timer: Optional[threading.Timer] = None
        self._auto_save_interval = 3.0  # 自动保存间隔（秒）
        
        # 控件引用
        self.markdown_input = ft.Ref[ft.TextField]()
        self.markdown_preview = ft.Ref[ft.Markdown]()
        self.html_output = ft.Ref[ft.TextField]()
        self.preview_container = ft.Ref[ft.Container]()
        self.status_line_text_ref = ft.Ref[ft.Text]()
        self.status_char_text_ref = ft.Ref[ft.Text]()
        self.status_word_text_ref = ft.Ref[ft.Text]()
        self.preview_toggle_btn_ref = ft.Ref[ft.IconButton]()
        self.file_list_ref = ft.Ref[ft.Column]()
        self.workspace_name_ref = ft.Ref[ft.Text]()
        self.current_file_ref = ft.Ref[ft.Text]()
        self.sidebar_ref = ft.Ref[ft.Container]()
        self.sidebar_toggle_ref = ft.Ref[ft.IconButton]()
        self.tabs_row_ref = ft.Ref[ft.Row]()  # 标签栏引用
        
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
        self._sidebar_visible = True  # 侧边栏默认显示
        
        # 主题配置
        self._current_theme = "default"
        self._themes = {
            "default": {
                "name": "默认",
                "icon": ft.Icons.LIGHT_MODE,
                "bg_color": ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
                "text_color": None,
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
        
        # 文件选择器
        self._folder_picker = ft.FilePicker(on_result=self._on_folder_picked)
        self._save_file_picker = ft.FilePicker(on_result=self._on_save_file_picked)
        self._open_file_picker = ft.FilePicker(on_result=self._on_open_file_picked)
        self.page.overlay.append(self._folder_picker)
        self.page.overlay.append(self._save_file_picker)
        self.page.overlay.append(self._open_file_picker)
        
        # 待保存的未命名标签页 key（用于文件选择器回调）
        self._pending_save_untitled_key: Optional[str] = None
        self._pending_close_after_save: bool = False
        
        self._build_ui()
        
        # 创建初始的未命名标签页
        self._create_untitled_tab()
        
        # 启动自动保存定时器
        self._start_auto_save_timer()
        
        # 注册键盘快捷键
        self._setup_keyboard_shortcuts()
    
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
                ft.Text("Markdown 编辑器", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # ========== 侧边栏（工作区文件浏览器）==========
        sidebar_header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=ft.Colors.PRIMARY),
                    ft.Text(
                        ref=self.workspace_name_ref,
                        value="工作区",
                        size=13,
                        weight=ft.FontWeight.W_600,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.NOTE_ADD,
                        icon_size=16,
                        tooltip="新建文件",
                        style=ft.ButtonStyle(padding=4),
                        on_click=self._show_new_file_dialog,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN,
                        icon_size=16,
                        tooltip="打开文件夹",
                        style=ft.ButtonStyle(padding=4),
                        on_click=self._open_workspace,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_size=16,
                        tooltip="刷新",
                        style=ft.ButtonStyle(padding=4),
                        on_click=self._refresh_workspace,
                    ),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
        )
        
        # 文件列表
        file_list_container = ft.Container(
            content=ft.Column(
                ref=self.file_list_ref,
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_OFF, size=48, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                                ft.Text("点击上方按钮", size=12, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                                ft.Text("打开工作区文件夹", size=12, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        alignment=ft.alignment.center,
                        expand=True,
                    ),
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            padding=ft.padding.only(top=4),
        )
        
        sidebar = ft.Container(
            ref=self.sidebar_ref,
            content=ft.Column(
                controls=[
                    sidebar_header,
                    file_list_container,
                ],
                spacing=0,
                expand=True,
            ),
            width=220,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
            border=ft.border.only(right=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
            visible=self._sidebar_visible,
        )
        
        # ========== 标签栏 ==========
        tabs_bar = ft.Container(
            content=ft.Row(
                ref=self.tabs_row_ref,
                controls=[
                    # 空状态提示
                    ft.Container(
                        content=ft.Text(
                            "打开文件开始编辑",
                            size=12,
                            color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            italic=True,
                        ),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
            padding=ft.padding.only(left=4),
        )
        
        # ========== 编辑器工具栏 ==========
        editor_toolbar = ft.Container(
            content=ft.Row(
                controls=[
                    # 侧边栏切换按钮
                    ft.IconButton(
                        ref=self.sidebar_toggle_ref,
                        icon=ft.Icons.MENU,
                        tooltip="切换侧边栏",
                        icon_size=18,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=6,
                        ),
                        on_click=self._toggle_sidebar,
                    ),
                    ft.VerticalDivider(width=8, thickness=1),
                    # 打开文件按钮
                    ft.IconButton(
                        icon=ft.Icons.FILE_OPEN,
                        tooltip="打开文件 (Ctrl+O)",
                        icon_size=18,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=6,
                        ),
                        on_click=self._open_file_dialog,
                    ),
                    # 保存按钮
                    ft.IconButton(
                        icon=ft.Icons.SAVE,
                        tooltip="保存文件 (Ctrl+S)",
                        icon_size=18,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=6,
                        ),
                        on_click=self._save_current_file,
                    ),
                    ft.Container(expand=True),
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
                scroll=ft.ScrollMode.AUTO,
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
                        tabs_bar,
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
        
        # 主内容区域（编辑器 + 预览）
        editor_preview_area = ft.Row(
            ref=self.content_area_ref,
            controls=[left_panel, divider, right_panel],
            spacing=8,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 主工作区（侧边栏 + 编辑器/预览区）
        workspace_area = ft.Row(
            controls=[sidebar, editor_preview_area],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 主列
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(),
                workspace_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    # ========== 工作区相关方法 ==========
    
    def _toggle_sidebar(self, e):
        """切换侧边栏显示/隐藏。"""
        self._sidebar_visible = not self._sidebar_visible
        if self.sidebar_ref.current:
            self.sidebar_ref.current.visible = self._sidebar_visible
            try:
                self.sidebar_ref.current.update()
            except (AssertionError, AttributeError):
                pass
    
    def _open_workspace(self, e):
        """打开工作区文件夹选择器。"""
        self._folder_picker.get_directory_path(
            dialog_title="选择工作区文件夹",
        )
    
    def _on_folder_picked(self, e: ft.FilePickerResultEvent):
        """处理文件夹选择结果。"""
        if e.path:
            self._workspace_path = Path(e.path)
            self._load_workspace()
    
    def _load_workspace(self):
        """加载工作区文件列表。"""
        if not self._workspace_path or not self._workspace_path.exists():
            return
        
        # 更新工作区名称
        if self.workspace_name_ref.current:
            self.workspace_name_ref.current.value = self._workspace_path.name
            try:
                self.workspace_name_ref.current.update()
            except (AssertionError, AttributeError):
                pass
        
        # 扫描 Markdown 文件
        self._scan_md_files()
        
        # 更新文件列表 UI
        self._update_file_list_ui()
        
        self._show_snack(f"已打开工作区: {self._workspace_path.name}")
    
    def _scan_md_files(self):
        """扫描工作区中的 Markdown 文件。"""
        if not self._workspace_path:
            return
        
        md_exts = {'.md', '.markdown', '.mdown', '.mkd'}
        self._md_files = []
        
        try:
            for item in self._workspace_path.rglob('*'):
                if item.is_file() and item.suffix.lower() in md_exts:
                    self._md_files.append(item)
            
            # 按路径排序
            self._md_files.sort(key=lambda x: str(x).lower())
        except PermissionError:
            self._show_snack("部分文件夹无权限访问", error=True)
    
    def _refresh_workspace(self, e):
        """刷新工作区文件列表。"""
        if self._workspace_path:
            self._load_workspace()
        else:
            self._show_snack("请先打开工作区", error=True)
    
    def _update_file_list_ui(self):
        """更新文件列表 UI。"""
        if not self.file_list_ref.current:
            return
        
        if not self._md_files:
            # 显示空状态
            self.file_list_ref.current.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=48, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text("没有找到 Markdown 文件", size=12, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                ),
            ]
        else:
            # 构建文件树
            file_items = self._build_file_tree()
            self.file_list_ref.current.controls = file_items
        
        try:
            self.file_list_ref.current.update()
        except (AssertionError, AttributeError):
            pass
    
    def _build_file_tree(self) -> List[ft.Control]:
        """构建文件树控件列表。"""
        items = []
        
        # 按文件夹分组
        folders: Dict[Path, List[Path]] = {}
        root_files: List[Path] = []
        
        for file_path in self._md_files:
            rel_path = file_path.relative_to(self._workspace_path)
            if len(rel_path.parts) == 1:
                # 根目录文件
                root_files.append(file_path)
            else:
                # 子文件夹中的文件
                folder = file_path.parent
                if folder not in folders:
                    folders[folder] = []
                folders[folder].append(file_path)
        
        # 添加根目录文件
        for file_path in root_files:
            items.append(self._create_file_item(file_path))
        
        # 添加文件夹
        sorted_folders = sorted(folders.keys(), key=lambda x: str(x).lower())
        for folder in sorted_folders:
            items.append(self._create_folder_item(folder, folders[folder]))
        
        return items
    
    def _create_file_item(self, file_path: Path, show_delete: bool = True) -> ft.Control:
        """创建文件列表项。"""
        is_current = self._current_file == file_path
        rel_path = file_path.relative_to(self._workspace_path)
        
        controls = [
            ft.Icon(
                ft.Icons.DESCRIPTION,
                size=16,
                color=ft.Colors.PRIMARY if is_current else ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
            ),
            ft.Text(
                file_path.name,
                size=12,
                weight=ft.FontWeight.W_500 if is_current else ft.FontWeight.NORMAL,
                color=ft.Colors.PRIMARY if is_current else None,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=True,
            ),
        ]
        
        # 添加删除按钮（悬停时显示）
        if show_delete:
            controls.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_size=14,
                    icon_color=ft.Colors.ERROR,
                    tooltip="删除文件",
                    style=ft.ButtonStyle(padding=2),
                    on_click=lambda e, fp=file_path: self._confirm_delete_file(fp),
                )
            )
        
        return ft.Container(
            content=ft.Row(
                controls=controls,
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_current else None,
            on_click=lambda e, fp=file_path: self._open_file(fp),
            on_hover=lambda e: self._on_file_hover(e),
            tooltip=str(rel_path),
        )
    
    def _create_folder_item(self, folder: Path, files: List[Path]) -> ft.Control:
        """创建文件夹列表项。"""
        rel_folder = folder.relative_to(self._workspace_path)
        is_expanded = folder in self._expanded_folders
        
        # 文件夹头部
        folder_header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.FOLDER_OPEN if is_expanded else ft.Icons.FOLDER,
                        size=16,
                        color=ft.Colors.AMBER_600,
                    ),
                    ft.Text(
                        rel_folder.as_posix(),
                        size=12,
                        weight=ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.EXPAND_MORE if is_expanded else ft.Icons.CHEVRON_RIGHT,
                        size=16,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border_radius=4,
            on_click=lambda e, f=folder: self._toggle_folder(f),
            on_hover=lambda e: self._on_file_hover(e),
        )
        
        # 文件夹内容
        folder_content = []
        if is_expanded:
            for file_path in sorted(files, key=lambda x: x.name.lower()):
                folder_content.append(
                    ft.Container(
                        content=self._create_file_item(file_path),
                        padding=ft.padding.only(left=16),
                    )
                )
        
        return ft.Column(
            controls=[folder_header] + folder_content,
            spacing=0,
        )
    
    def _toggle_folder(self, folder: Path):
        """切换文件夹展开/折叠状态。"""
        if folder in self._expanded_folders:
            self._expanded_folders.remove(folder)
        else:
            self._expanded_folders.add(folder)
        self._update_file_list_ui()
    
    def _on_file_hover(self, e):
        """文件项悬停效果。"""
        if e.data == "true":
            e.control.bgcolor = ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)
        else:
            # 检查是否是当前文件
            is_current = False
            if hasattr(e.control, 'on_click') and e.control.on_click:
                pass  # 保持当前文件的高亮
            e.control.bgcolor = None
        try:
            e.control.update()
        except (AssertionError, AttributeError):
            pass
    
    def _open_file(self, file_path: Path):
        """打开指定的 Markdown 文件。"""
        # 如果文件已经在标签页中打开，直接切换
        if file_path in self._open_tabs:
            self._switch_to_tab(file_path)
            return
        
        # 保存当前文件的内容到标签页
        if self._current_file and self._current_file in self._open_tabs:
            self._save_tab_content(self._current_file)
        
        # 加载新文件
        self._load_file(file_path)
    
    def _load_file(self, file_path: Path):
        """加载文件内容到编辑器。"""
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding='gbk')
            except Exception as e:
                self._show_snack(f"读取文件失败: {e}", error=True)
                return
        except Exception as e:
            self._show_snack(f"读取文件失败: {e}", error=True)
            return
        
        # 添加到标签页
        if file_path not in self._open_tabs:
            self._open_tabs[file_path] = {
                "content": content,
                "original_content": content,  # 保存原始内容用于比较
                "modified": False,
            }
            self._tab_order.append(file_path)
        
        self._current_file = file_path
        
        # 更新编辑器内容
        if self.markdown_input.current:
            self.markdown_input.current.value = content
            try:
                self.markdown_input.current.update()
            except (AssertionError, AttributeError):
                pass
            self._on_markdown_change(None)
        
        # 更新标签栏
        self._update_tabs_ui()
        
        # 更新文件列表高亮
        self._update_file_list_ui()
        
        self._show_snack(f"已打开: {file_path.name}")
    
    def _save_tab_content(self, file_path: Path):
        """保存当前编辑器内容到标签页缓存。"""
        if file_path in self._open_tabs and self.markdown_input.current:
            self._open_tabs[file_path]["content"] = self.markdown_input.current.value or ""
    
    def _switch_to_tab(self, file_path: Path):
        """切换到指定的标签页。"""
        if file_path not in self._open_tabs:
            return
        
        # 如果点击的就是当前标签页，不需要切换
        if self._current_file == file_path:
            return
        
        # 保存当前标签页内容
        if self._current_file and self._current_file in self._open_tabs:
            self._save_tab_content(self._current_file)
        
        # 切换到新标签页
        self._current_file = file_path
        tab_data = self._open_tabs[file_path]
        
        # 更新编辑器内容
        if self.markdown_input.current:
            self.markdown_input.current.value = tab_data["content"]
            try:
                self.markdown_input.current.update()
            except (AssertionError, AttributeError):
                pass
            
            # 更新预览和统计信息
            self._on_markdown_change(None)
        
        # 更新标签栏
        self._update_tabs_ui()
        
        # 更新文件列表高亮
        self._update_file_list_ui()
    
    def _close_tab(self, file_path):
        """关闭指定的标签页。"""
        if file_path not in self._open_tabs:
            return
        
        # 检查是否有未保存的修改
        if self._open_tabs[file_path]["modified"]:
            self._show_close_tab_dialog(file_path)
            return
        
        # 移除标签页
        del self._open_tabs[file_path]
        self._tab_order.remove(file_path)
        
        # 如果关闭的是当前标签页，切换到其他标签页
        if self._current_file == file_path:
            if self._tab_order:
                # 切换到最后一个标签页
                self._switch_to_tab(self._tab_order[-1])
            else:
                # 没有打开的标签页了，创建新的未命名标签页
                self._create_untitled_tab()
        
        # 更新标签栏
        self._update_tabs_ui()
    
    def _show_close_tab_dialog(self, file_path):
        """显示关闭标签页确认对话框。"""
        is_untitled = self._is_untitled_tab(file_path)
        display_name = self._get_tab_display_name(file_path)
        
        def save_and_close(_):
            self.page.close(dialog)
            if is_untitled:
                # 未命名文件需要先选择保存位置
                self._save_untitled_and_close(file_path)
            else:
                # 已有文件直接保存
                try:
                    content = self._open_tabs[file_path]["content"]
                    file_path.write_text(content, encoding='utf-8')
                    self._open_tabs[file_path]["modified"] = False
                    self._close_tab(file_path)
                    self._show_snack(f"已保存并关闭: {display_name}")
                except Exception as e:
                    self._show_snack(f"保存失败: {e}", error=True)
        
        def discard_and_close(_):
            self.page.close(dialog)
            # 强制关闭
            self._open_tabs[file_path]["modified"] = False
            self._close_tab(file_path)
        
        def cancel(_):
            self.page.close(dialog)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("保存更改？"),
            content=ft.Text(f"文件 \"{display_name}\" 已修改，是否保存？"),
            actions=[
                ft.TextButton("保存", on_click=save_and_close),
                ft.TextButton("不保存", on_click=discard_and_close),
                ft.TextButton("取消", on_click=cancel),
            ],
        )
        self.page.open(dialog)
    
    def _save_untitled_and_close(self, untitled_key):
        """保存未命名文件并关闭标签页。"""
        self._save_untitled_file(untitled_key, close_after_save=True)
    
    def _update_tabs_ui(self):
        """更新标签栏 UI。"""
        if not self.tabs_row_ref.current:
            return
        
        if not self._tab_order:
            # 显示空状态
            self.tabs_row_ref.current.controls = [
                ft.Container(
                    content=ft.Text(
                        "打开文件开始编辑",
                        size=12,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                        italic=True,
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                ),
            ]
        else:
            # 显示标签页
            tabs = []
            for file_path in self._tab_order:
                is_current = file_path == self._current_file
                is_modified = self._open_tabs[file_path]["modified"]
                
                # 文件名显示（支持未命名标签页）
                file_name = self._get_tab_display_name(file_path)
                
                # 创建关闭按钮（独立的容器，防止事件冲突）
                close_btn = ft.Container(
                    content=ft.Icon(
                        ft.Icons.CLOSE,
                        size=14,
                        color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                    ),
                    width=20,
                    height=20,
                    border_radius=4,
                    alignment=ft.alignment.center,
                    on_click=lambda e, fp=file_path: self._close_tab(fp),
                    ink=True,
                    tooltip="关闭标签页",
                )
                
                # 修改标记（圆点）
                modified_indicator = ft.Container(
                    content=ft.Icon(
                        ft.Icons.CIRCLE,
                        size=6,
                        color=ft.Colors.ORANGE_400,
                    ),
                    visible=is_modified,
                    margin=ft.margin.only(right=4),
                )
                
                # 标签页内容
                tab_content = ft.Row(
                    controls=[
                        modified_indicator,
                        ft.Text(
                            file_name,
                            size=12,
                            weight=ft.FontWeight.W_500 if is_current else ft.FontWeight.NORMAL,
                            color=ft.Colors.PRIMARY if is_current else None,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        close_btn,
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                
                # 工具提示
                if self._is_untitled_tab(file_path):
                    tooltip_text = file_name
                elif isinstance(file_path, Path) and self._workspace_path:
                    try:
                        tooltip_text = str(file_path.relative_to(self._workspace_path))
                    except ValueError:
                        tooltip_text = str(file_path)
                else:
                    tooltip_text = str(file_path)
                
                # 标签页容器
                tab = ft.Container(
                    content=tab_content,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=ft.border_radius.only(top_left=6, top_right=6),
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_current else ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.border.only(
                        bottom=ft.BorderSide(2, ft.Colors.PRIMARY) if is_current else ft.BorderSide(1, ft.Colors.TRANSPARENT)
                    ),
                    on_click=lambda e, fp=file_path: self._switch_to_tab(fp),
                    on_hover=lambda e, c=None: self._on_tab_hover(e),
                    tooltip=tooltip_text,
                    animate=100,  # 动画持续时间（毫秒）
                )
                tabs.append(tab)
            
            self.tabs_row_ref.current.controls = tabs
        
        try:
            self.tabs_row_ref.current.update()
        except (AssertionError, AttributeError):
            pass
    
    def _on_tab_hover(self, e):
        """标签页悬停效果。"""
        if e.data == "true":
            # 悬停时增强背景色
            if e.control.bgcolor == ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE):
                e.control.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)
        else:
            # 离开时恢复
            # 检查是否是当前标签页
            is_current = False
            for file_path in self._tab_order:
                if file_path == self._current_file:
                    # 当前标签页保持高亮
                    if e.control.bgcolor != ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY):
                        e.control.bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE)
                    break
            else:
                e.control.bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE)
        
        try:
            e.control.update()
        except (AssertionError, AttributeError):
            pass
    
    def _show_save_dialog(self, next_file: Optional[Path] = None):
        """显示保存确认对话框。"""
        def save_and_continue(_):
            self.page.close(dialog)
            self._save_current_file(None)
            if next_file:
                self._load_file(next_file)
        
        def discard_and_continue(_):
            self.page.close(dialog)
            self._file_modified = False
            if next_file:
                self._load_file(next_file)
        
        def cancel(_):
            self.page.close(dialog)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("保存更改？"),
            content=ft.Text(f"文件 \"{self._current_file.name if self._current_file else '未命名'}\" 已修改，是否保存？"),
            actions=[
                ft.TextButton("保存", on_click=save_and_continue),
                ft.TextButton("不保存", on_click=discard_and_continue),
                ft.TextButton("取消", on_click=cancel),
            ],
        )
        self.page.open(dialog)
    
    def _save_current_file(self, e):
        """保存当前文件。"""
        if not self._current_file:
            self._show_snack("没有打开的文件", error=True)
            return
        
        # 检查是否是未命名文件
        if self._is_untitled_tab(self._current_file):
            self._save_untitled_file(self._current_file)
            return
        
        content = self.markdown_input.current.value if self.markdown_input.current else ""
        
        try:
            self._current_file.write_text(content, encoding='utf-8')
            
            # 更新标签页状态
            if self._current_file in self._open_tabs:
                self._open_tabs[self._current_file]["content"] = content
                self._open_tabs[self._current_file]["original_content"] = content
                self._open_tabs[self._current_file]["modified"] = False
                # 更新标签栏显示
                self._update_tabs_ui()
            
            self._show_snack(f"已保存: {self._current_file.name}")
        except Exception as ex:
            self._show_snack(f"保存失败: {ex}", error=True)
    
    def _save_untitled_file(self, untitled_key, close_after_save: bool = False):
        """保存未命名文件（弹出保存对话框）。"""
        content = self._open_tabs[untitled_key]["content"]
        default_name = self._open_tabs[untitled_key].get("name", "未命名.md")
        
        # 如果有工作区，使用简单的文件名输入对话框
        if self._workspace_path:
            self._show_save_in_workspace_dialog(untitled_key, close_after_save)
        else:
            # 没有工作区，使用系统文件保存对话框
            self._pending_save_untitled_key = untitled_key
            self._pending_close_after_save = close_after_save
            self._save_file_picker.save_file(
                dialog_title="保存 Markdown 文件",
                file_name=default_name,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["md", "markdown"],
            )
    
    def _show_save_in_workspace_dialog(self, untitled_key, close_after_save: bool = False):
        """在工作区中保存文件的对话框。"""
        content = self._open_tabs[untitled_key]["content"]
        default_name = self._open_tabs[untitled_key].get("name", "未命名.md")
        
        # 显示保存对话框
        filename_input = ft.TextField(
            label="文件名",
            value=default_name,
            autofocus=True,
        )
        
        def do_save(_):
            filename = filename_input.value.strip()
            if not filename:
                self._show_snack("请输入文件名", error=True)
                return
            
            # 确保文件名以 .md 结尾
            if not filename.lower().endswith(('.md', '.markdown', '.mdown', '.mkd')):
                filename = filename + '.md'
            
            new_file_path = self._workspace_path / filename
            
            if new_file_path.exists():
                self._show_snack(f"文件 {filename} 已存在", error=True)
                return
            
            try:
                new_file_path.write_text(content, encoding='utf-8')
                self.page.close(save_dialog)
                
                # 移除未命名标签页
                del self._open_tabs[untitled_key]
                self._tab_order.remove(untitled_key)
                
                if close_after_save:
                    # 如果是关闭时保存，切换到其他标签页或创建新标签页
                    if self._tab_order:
                        self._switch_to_tab(self._tab_order[-1])
                    else:
                        self._create_untitled_tab()
                else:
                    # 添加新文件标签页
                    self._open_tabs[new_file_path] = {
                        "content": content,
                        "original_content": content,
                        "modified": False,
                    }
                    self._tab_order.append(new_file_path)
                    self._current_file = new_file_path
                
                # 刷新文件列表
                self._scan_md_files()
                self._update_file_list_ui()
                self._update_tabs_ui()
                
                self._show_snack(f"已保存: {filename}")
            except Exception as ex:
                self._show_snack(f"保存失败: {ex}", error=True)
        
        def do_cancel(_):
            self.page.close(save_dialog)
        
        def use_system_dialog(_):
            self.page.close(save_dialog)
            # 使用系统文件保存对话框
            self._pending_save_untitled_key = untitled_key
            self._pending_close_after_save = close_after_save
            self._save_file_picker.save_file(
                dialog_title="保存 Markdown 文件",
                file_name=default_name,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["md", "markdown"],
            )
        
        save_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=22, color=ft.Colors.PRIMARY),
                    ft.Text("保存文件", size=16, weight=ft.FontWeight.W_600),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"保存到: {self._workspace_path.name}/",
                            size=12,
                            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                        ),
                        ft.Container(height=8),
                        filename_input,
                    ],
                    spacing=4,
                    tight=True,
                ),
                width=350,
            ),
            actions=[
                ft.TextButton("选择其他位置", on_click=use_system_dialog),
                ft.TextButton("取消", on_click=do_cancel),
                ft.ElevatedButton("保存", on_click=do_save),
            ],
        )
        self.page.open(save_dialog)
    
    def _on_save_file_picked(self, e: ft.FilePickerResultEvent):
        """处理文件保存对话框的结果。"""
        if not e.path or not self._pending_save_untitled_key:
            self._pending_save_untitled_key = None
            self._pending_close_after_save = False
            return
        
        untitled_key = self._pending_save_untitled_key
        close_after_save = self._pending_close_after_save
        self._pending_save_untitled_key = None
        self._pending_close_after_save = False
        
        if untitled_key not in self._open_tabs:
            return
        
        content = self._open_tabs[untitled_key]["content"]
        save_path = Path(e.path)
        
        # 确保文件名以 .md 结尾
        if not save_path.suffix.lower() in ('.md', '.markdown', '.mdown', '.mkd'):
            save_path = save_path.with_suffix('.md')
        
        try:
            save_path.write_text(content, encoding='utf-8')
            
            # 移除未命名标签页
            del self._open_tabs[untitled_key]
            self._tab_order.remove(untitled_key)
            
            if close_after_save:
                # 如果是关闭时保存，切换到其他标签页或创建新标签页
                if self._tab_order:
                    self._switch_to_tab(self._tab_order[-1])
                else:
                    self._create_untitled_tab()
            else:
                # 添加新文件标签页
                self._open_tabs[save_path] = {
                    "content": content,
                    "original_content": content,
                    "modified": False,
                }
                self._tab_order.append(save_path)
                self._current_file = save_path
            
            # 如果保存的位置在工作区内，刷新文件列表
            if self._workspace_path:
                try:
                    save_path.relative_to(self._workspace_path)
                    self._scan_md_files()
                    self._update_file_list_ui()
                except ValueError:
                    pass  # 不在工作区内，不需要刷新
            
            self._update_tabs_ui()
            self._show_snack(f"已保存: {save_path.name}")
        except Exception as ex:
            self._show_snack(f"保存失败: {ex}", error=True)
    
    def _open_file_dialog(self, e):
        """打开文件选择对话框。"""
        self._open_file_picker.pick_files(
            dialog_title="打开 Markdown 文件",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["md", "markdown", "mdown", "mkd"],
            allow_multiple=False,
        )
    
    def _on_open_file_picked(self, e: ft.FilePickerResultEvent):
        """处理打开文件对话框的结果。"""
        if not e.files or len(e.files) == 0:
            return
        
        file_path = Path(e.files[0].path)
        
        # 如果文件已经在标签页中打开，直接切换
        if file_path in self._open_tabs:
            self._switch_to_tab(file_path)
            return
        
        # 保存当前文件的内容到标签页
        if self._current_file and self._current_file in self._open_tabs:
            self._save_tab_content(self._current_file)
        
        # 加载文件
        self._load_file(file_path)
    
    def _show_new_file_dialog(self, e):
        """显示新建文件对话框。"""
        if not self._workspace_path:
            self._show_snack("请先打开工作区", error=True)
            return
        
        filename_input = ft.TextField(
            label="文件名",
            hint_text="例如: readme.md",
            suffix_text=".md",
            autofocus=True,
            on_submit=lambda e: create_file(e),
        )
        
        def create_file(_):
            filename = filename_input.value.strip()
            if not filename:
                self._show_snack("请输入文件名", error=True)
                return
            
            # 确保文件名以 .md 结尾
            if not filename.lower().endswith(('.md', '.markdown', '.mdown', '.mkd')):
                filename = filename + '.md'
            
            # 创建文件路径
            new_file_path = self._workspace_path / filename
            
            # 检查文件是否已存在
            if new_file_path.exists():
                self._show_snack(f"文件 {filename} 已存在", error=True)
                return
            
            try:
                # 创建文件，写入默认内容
                default_content = f"# {new_file_path.stem}\n\n"
                new_file_path.write_text(default_content, encoding='utf-8')
                
                self.page.close(dialog)
                
                # 刷新文件列表
                self._scan_md_files()
                self._update_file_list_ui()
                
                # 打开新创建的文件
                self._load_file(new_file_path)
                
                self._show_snack(f"已创建: {filename}")
            except Exception as ex:
                self._show_snack(f"创建文件失败: {ex}", error=True)
        
        def cancel(_):
            self.page.close(dialog)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.NOTE_ADD, size=22, color=ft.Colors.PRIMARY),
                    ft.Text("新建 Markdown 文件", size=16, weight=ft.FontWeight.W_600),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"在 {self._workspace_path.name} 中创建新文件",
                            size=12,
                            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                        ),
                        ft.Container(height=8),
                        filename_input,
                    ],
                    spacing=4,
                    tight=True,
                ),
                width=350,
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel),
                ft.ElevatedButton("创建", on_click=create_file),
            ],
        )
        self.page.open(dialog)
    
    def _confirm_delete_file(self, file_path: Path):
        """确认删除文件对话框。"""
        def delete_file(_):
            self.page.close(dialog)
            self._delete_file(file_path)
        
        def cancel(_):
            self.page.close(dialog)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING, size=22, color=ft.Colors.ERROR),
                    ft.Text("确认删除", size=16, weight=ft.FontWeight.W_600),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(f"确定要删除文件吗？"),
                        ft.Container(height=4),
                        ft.Container(
                            content=ft.Text(
                                file_path.name,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ERROR,
                            ),
                            padding=ft.padding.symmetric(horizontal=12, vertical=8),
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ERROR),
                            border_radius=4,
                        ),
                        ft.Container(height=8),
                        ft.Text(
                            "此操作不可撤销，文件将被永久删除。",
                            size=12,
                            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                        ),
                    ],
                    spacing=4,
                    tight=True,
                ),
                width=320,
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel),
                ft.ElevatedButton(
                    "删除",
                    bgcolor=ft.Colors.ERROR,
                    color=ft.Colors.WHITE,
                    on_click=delete_file,
                ),
            ],
        )
        self.page.open(dialog)
    
    def _delete_file(self, file_path: Path):
        """删除指定的文件。"""
        try:
            # 如果文件在标签页中打开，先关闭标签页
            if file_path in self._open_tabs:
                # 强制关闭标签页（不提示保存）
                self._open_tabs[file_path]["modified"] = False
                self._close_tab(file_path)
            
            # 删除文件
            file_path.unlink()
            
            # 刷新文件列表
            self._scan_md_files()
            self._update_file_list_ui()
            
            self._show_snack(f"已删除: {file_path.name}")
        except Exception as e:
            self._show_snack(f"删除失败: {e}", error=True)
    
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
        markdown_content = self.markdown_input.current.value if self.markdown_input.current else ""
        
        # 标记标签页已修改（支持未命名标签页和已打开的文件）
        if self._current_file and self._current_file in self._open_tabs:
            original_content = self._open_tabs[self._current_file].get("original_content", "")
            current_content = markdown_content or ""
            
            # 检查内容是否真的改变了
            if current_content != original_content:
                if not self._open_tabs[self._current_file]["modified"]:
                    self._open_tabs[self._current_file]["modified"] = True
                    # 更新标签栏显示
                    self._update_tabs_ui()
            else:
                if self._open_tabs[self._current_file]["modified"]:
                    self._open_tabs[self._current_file]["modified"] = False
                    # 更新标签栏显示
                    self._update_tabs_ui()
            
            # 更新缓存的内容
            self._open_tabs[self._current_file]["content"] = current_content
        
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
**Markdown 编辑器使用说明**

**功能：**
- 实时 Markdown 预览（点击工具栏眼睛图标开启）
- 支持 GitHub Flavored Markdown (GFM)
- 多种预览主题可选
- 导出 HTML 代码
- 可拖动调整左右面板
- 字数、字符、行数统计
- 每 3 秒自动保存已打开的文件

**快捷键：**
- **Ctrl+O**: 打开文件
- **Ctrl+S**: 保存当前文件
- **Ctrl+K**: 切换预览显示/隐藏
- **Ctrl+B**: 切换侧边栏显示/隐藏
- **Ctrl+N**: 新建未命名标签页
- **Ctrl+W**: 关闭当前标签页

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
        # 停止自动保存定时器
        self._stop_auto_save_timer()
        # 移除键盘事件监听
        self._remove_keyboard_shortcuts()
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除文件选择器
        if self._folder_picker in self.page.overlay:
            self.page.overlay.remove(self._folder_picker)
        if self._save_file_picker in self.page.overlay:
            self.page.overlay.remove(self._save_file_picker)
        if self._open_file_picker in self.page.overlay:
            self.page.overlay.remove(self._open_file_picker)
        # 清除 UI 内容
        self.content = None
        gc.collect()
    
    # ========== 键盘快捷键相关方法 ==========
    
    def _setup_keyboard_shortcuts(self):
        """设置键盘快捷键。"""
        self._keyboard_handler = self._on_keyboard_event
        self.page.on_keyboard_event = self._keyboard_handler
    
    def _remove_keyboard_shortcuts(self):
        """移除键盘快捷键。"""
        if hasattr(self, '_keyboard_handler') and self.page:
            self.page.on_keyboard_event = None
    
    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """处理键盘事件。"""
        # Ctrl+S: 保存文件
        if e.ctrl and e.key == "S":
            self._save_current_file(None)
            return
        
        # Ctrl+O: 打开文件
        if e.ctrl and e.key == "O":
            self._open_file_dialog(None)
            return
        
        # Ctrl+K: 切换预览
        if e.ctrl and e.key == "K":
            self._toggle_preview(None)
            return
        
        # Ctrl+B: 切换侧边栏
        if e.ctrl and e.key == "B":
            self._toggle_sidebar(None)
            return
        
        # Ctrl+N: 新建未命名标签页
        if e.ctrl and e.key == "N":
            self._create_untitled_tab()
            return
        
        # Ctrl+W: 关闭当前标签页
        if e.ctrl and e.key == "W":
            if self._current_file:
                self._close_tab(self._current_file)
            return
    
    # ========== 自动保存相关方法 ==========
    
    def _start_auto_save_timer(self):
        """启动自动保存定时器。"""
        self._stop_auto_save_timer()  # 先停止现有的定时器
        self._auto_save_timer = threading.Timer(self._auto_save_interval, self._auto_save_callback)
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()
    
    def _stop_auto_save_timer(self):
        """停止自动保存定时器。"""
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
            self._auto_save_timer = None
    
    def _auto_save_callback(self):
        """自动保存回调函数。"""
        try:
            # 执行自动保存
            self._perform_auto_save()
        except Exception:
            pass  # 忽略自动保存中的错误
        finally:
            # 重新启动定时器
            self._start_auto_save_timer()
    
    def _perform_auto_save(self):
        """执行自动保存操作。"""
        # 只保存已打开的文件（非未命名文件）
        if not self._current_file:
            return
        
        # 检查是否是真实文件（Path 对象）
        if not isinstance(self._current_file, Path):
            return
        
        # 检查是否有修改
        if self._current_file not in self._open_tabs:
            return
        
        if not self._open_tabs[self._current_file].get("modified", False):
            return
        
        # 获取当前内容
        content = self._open_tabs[self._current_file].get("content", "")
        
        try:
            # 保存到文件
            self._current_file.write_text(content, encoding='utf-8')
            
            # 更新状态
            self._open_tabs[self._current_file]["modified"] = False
            self._open_tabs[self._current_file]["original_content"] = content
            
            # 在主线程中更新 UI
            if self.page:
                self.page.run_thread_safe(self._update_tabs_ui)
                self.page.run_thread_safe(lambda: self._show_snack(f"已自动保存: {self._current_file.name}"))
        except Exception as e:
            # 自动保存失败时静默处理
            pass
    
    # ========== 未命名标签页相关方法 ==========
    
    def _create_untitled_tab(self):
        """创建一个未命名的新标签页。"""
        self._untitled_counter += 1
        untitled_key = f"untitled_{self._untitled_counter}"
        
        # 添加到标签页
        self._open_tabs[untitled_key] = {
            "content": "",
            "original_content": "",  # 原始内容用于比较是否修改
            "modified": False,
            "name": f"未命名-{self._untitled_counter}.md",
        }
        self._tab_order.append(untitled_key)
        self._current_file = untitled_key
        
        # 清空编辑器
        if self.markdown_input.current:
            self.markdown_input.current.value = ""
            try:
                self.markdown_input.current.update()
            except (AssertionError, AttributeError):
                pass
        
        # 更新标签栏
        self._update_tabs_ui()
    
    def _is_untitled_tab(self, tab_key) -> bool:
        """检查是否是未命名标签页。"""
        return isinstance(tab_key, str) and tab_key.startswith("untitled_")
    
    def _get_tab_display_name(self, tab_key) -> str:
        """获取标签页的显示名称。"""
        if self._is_untitled_tab(tab_key):
            return self._open_tabs[tab_key].get("name", "未命名.md")
        elif isinstance(tab_key, Path):
            return tab_key.name
        return str(tab_key)

