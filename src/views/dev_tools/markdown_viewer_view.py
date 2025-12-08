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
        
        # 左侧：Markdown 编辑器
        left_panel = ft.Container(
            ref=self.left_panel_ref,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Markdown 编辑器", weight=ft.FontWeight.BOLD, size=16),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CLEAR,
                                tooltip="清空",
                                on_click=self._on_clear,
                            ),
                        ],
                    ),
                    ft.Container(
                        content=ft.TextField(
                            ref=self.markdown_input,
                            multiline=True,
                            min_lines=20,
                            hint_text='# Hello Markdown\n\n在此输入 Markdown 内容...',
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            on_change=self._on_markdown_change,
                        ),
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_SMALL,
                        expand=True,
                    ),
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
        
        # 右侧：预览区
        right_panel = ft.Container(
            ref=self.right_panel_ref,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("预览", weight=ft.FontWeight.BOLD, size=16),
                            ft.Container(expand=True),
                            ft.OutlinedButton(
                                text="复制 HTML",
                                icon=ft.Icons.CODE,
                                on_click=self._copy_html,
                            ),
                        ],
                    ),
                    ft.Container(
                        ref=self.preview_container,
                        content=ft.Column(
                            controls=[
                                ft.Markdown(
                                    ref=self.markdown_preview,
                                    value="# Hello Markdown\n\n在左侧输入 Markdown 内容，这里会实时显示预览。",
                                    selectable=True,
                                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                    on_tap_link=lambda e: self.page.launch_url(e.data),
                                ),
                            ],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        expand=True,
                    ),
                ],
                spacing=5,
            ),
            expand=self.right_flex,
        )
        
        # 主内容区域
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
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _on_markdown_change(self, e):
        """Markdown 内容改变时更新预览。"""
        markdown_content = self.markdown_input.current.value
        if markdown_content:
            self.markdown_preview.current.value = markdown_content
        else:
            self.markdown_preview.current.value = "*空白文档*"
        
        try:
            self.markdown_preview.current.update()
        except (AssertionError, AttributeError):
            pass
    
    def _on_clear(self, e):
        """清空编辑器。"""
        self.markdown_input.current.value = ""
        self.markdown_preview.current.value = "*空白文档*"
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
        help_text = """
**Markdown 预览器使用说明**

**功能：**
- 实时 Markdown 预览
- 支持 GitHub Flavored Markdown (GFM)
- 导出 HTML 代码
- 可拖动调整左右面板

**支持的 Markdown 语法：**

```markdown
# 标题 1
## 标题 2
### 标题 3

**粗体** 或 __粗体__
*斜体* 或 _斜体_

[链接文字](https://example.com)

`代码`

- 列表项 1
- 列表项 2

1. 有序列表 1
2. 有序列表 2

> 引用文本

\`\`\`python
# 代码块
print("Hello")
\`\`\`
```

**快捷功能：**
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

