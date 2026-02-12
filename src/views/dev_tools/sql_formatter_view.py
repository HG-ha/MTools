# -*- coding: utf-8 -*-
"""SQL格式化工具视图模块。

提供SQL语句格式化和压缩功能。
"""

from typing import Callable, Optional

import flet as ft
import sqlparse

from constants import PADDING_MEDIUM, PADDING_SMALL


class SqlFormatterView(ft.Container):
    """SQL格式化工具视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
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
        self.input_text = ft.Ref[ft.TextField]()
        self.output_text = ft.Ref[ft.TextField]()
        self.keyword_case = ft.Ref[ft.Dropdown]()
        self.indent_width = ft.Ref[ft.Dropdown]()
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.Container]()
        self.ratio = 0.5
        self.left_flex = 500
        self.right_flex = 500
        self.is_dragging = False
        
        self._build_ui()
    
    def _build_ui(self):
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self._on_back_click(),
                ),
                ft.Text("SQL 格式化工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 操作栏
        operation_bar = ft.Row(
            controls=[
                ft.Dropdown(
                    ref=self.keyword_case,
                    label="关键字大小写",
                    width=150,
                    options=[
                        ft.dropdown.Option("upper", "大写"),
                        ft.dropdown.Option("lower", "小写"),
                        ft.dropdown.Option("capitalize", "首字母大写"),
                    ],
                    value="upper",
                ),
                ft.Dropdown(
                    ref=self.indent_width,
                    label="缩进宽度",
                    width=120,
                    options=[
                        ft.dropdown.Option("2"),
                        ft.dropdown.Option("4"),
                    ],
                    value="4",
                ),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    content="格式化",
                    icon=ft.Icons.AUTO_FIX_HIGH,
                    on_click=lambda _: self._format_sql(False),
                ),
                ft.ElevatedButton(
                    content="压缩",
                    icon=ft.Icons.COMPRESS,
                    on_click=lambda _: self._format_sql(True),
                ),
                ft.OutlinedButton(
                    content="清空",
                    icon=ft.Icons.CLEAR,
                    on_click=self._clear,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 输入区域
        input_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("输入", weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            icon_size=16,
                            on_click=lambda _: self._copy_text(self.input_text.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.input_text,
                        multiline=True,
                        min_lines=20,
                        hint_text="输入 SQL 语句...",
                        text_size=13,
                        border=ft.InputBorder.NONE,
                        text_style=ft.TextStyle(font_family="Consolas,Monospace"),
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
        
        # 输出区域
        output_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("输出", weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            icon_size=16,
                            on_click=lambda _: self._copy_text(self.output_text.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.output_text,
                        multiline=True,
                        min_lines=20,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
                        text_style=ft.TextStyle(font_family="Consolas,Monospace"),
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
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
        left_panel = ft.Container(ref=self.left_panel_ref, content=input_section, expand=self.left_flex)
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
                margin=ft.margin.only(top=40, bottom=6),
            ),
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            on_pan_start=self._on_divider_pan_start,
            on_pan_update=self._on_divider_pan_update,
            on_pan_end=self._on_divider_pan_end,
            drag_interval=10,
        )
        right_panel = ft.Container(ref=self.right_panel_ref, content=output_section, expand=self.right_flex)
        
        content_area = ft.Row(
            controls=[
                left_panel,
                divider,
                right_panel,
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Container(height=PADDING_SMALL),
                operation_bar,
                ft.Container(height=PADDING_SMALL),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
    
    def _format_sql(self, compress: bool = False):
        """格式化或压缩SQL。"""
        sql = self.input_text.current.value
        
        if not sql:
            self._show_snack("请输入 SQL 语句", error=True)
            return
        
        try:
            if compress:
                # 压缩：去除注释和多余空格
                result = sqlparse.format(
                    sql,
                    strip_comments=True,
                    strip_whitespace=True,
                )
            else:
                # 格式化：美化SQL
                keyword_case = self.keyword_case.current.value
                indent_width = int(self.indent_width.current.value)
                
                result = sqlparse.format(
                    sql,
                    reindent=True,
                    keyword_case=keyword_case,
                    indent_width=indent_width,
                    wrap_after=80,
                )
            
            self.output_text.current.value = result
            self.output_text.current.update()
            self._show_snack("处理完成")
            
        except Exception as e:
            error_msg = f"❌ 处理失败\n\n"
            error_msg += f"错误类型: {type(e).__name__}\n"
            error_msg += f"错误信息: {str(e)}\n\n"
            error_msg += "提示：\n"
            error_msg += "- 请检查 SQL 语法是否正确\n"
            error_msg += "- 工具支持大多数 SQL 方言（MySQL, PostgreSQL, SQLite等）\n"
            
            self.output_text.current.value = error_msg
            self.output_text.current.update()
            self._show_snack(f"错误: {str(e)}", error=True)
    
    def _clear(self, e):
        self.input_text.current.value = ""
        self.output_text.current.value = ""
        self.update()
    
    async def _copy_text(self, text: str):
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        await ft.Clipboard().set(text)
        self._show_snack("已复制到剪贴板")
    
    def _on_divider_pan_start(self, e: ft.DragStartEvent):
        """开始拖动分隔条。"""
        self.is_dragging = True
        if self.divider_ref.current:
            self.divider_ref.current.bgcolor = ft.Colors.PRIMARY
            self.divider_ref.current.update()
    
    def _on_divider_pan_update(self, e: ft.DragUpdateEvent):
        """拖动分隔条时更新左右宽度。"""
        if not self.is_dragging:
            return
        
        container_width = self._page.width - PADDING_MEDIUM * 2 - 12
        if container_width <= 0:
            return
        
        delta_ratio = e.delta_x / container_width
        self.ratio = max(0.2, min(0.8, self.ratio + delta_ratio))
        
        total = 1000
        self.left_flex = int(self.ratio * total)
        self.right_flex = total - self.left_flex
        
        if self.left_panel_ref.current and self.right_panel_ref.current:
            self.left_panel_ref.current.expand = self.left_flex
            self.right_panel_ref.current.expand = self.right_flex
            self.left_panel_ref.current.update()
            self.right_panel_ref.current.update()
    
    def _on_divider_pan_end(self, e: ft.DragEndEvent):
        """结束拖动分隔条。"""
        self.is_dragging = False
        if self.divider_ref.current:
            self.divider_ref.current.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
            self.divider_ref.current.update()
    
    def _on_back_click(self):
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**SQL 格式化工具使用说明**

**功能说明：**
- **格式化**：将压缩的 SQL 语句美化，添加缩进和换行
- **压缩**：删除注释和多余空格，生成紧凑的 SQL

**使用步骤：**
1. 在左侧输入框粘贴 SQL 语句
2. 选择关键字大小写和缩进宽度（格式化时使用）
3. 点击"格式化"或"压缩"
4. 在右侧查看处理后的 SQL

**选项说明：**

**关键字大小写：**
- **大写**：SELECT, FROM, WHERE（推荐）
- **小写**：select, from, where
- **首字母大写**：Select, From, Where

**缩进宽度：**
- **2 空格**：紧凑风格
- **4 空格**：标准风格（推荐）

**使用场景：**
- 从日志复制的单行 SQL，格式化后便于阅读
- 美化从ORM生成的SQL
- 压缩 SQL 以减少文件大小
- 统一团队的 SQL 代码风格

**示例：**

**格式化前：**
```sql
select u.id,u.name,o.order_id from users u join orders o on u.id=o.user_id where u.status=1
```

**格式化后：**
```sql
SELECT u.id,
       u.name,
       o.order_id
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.status = 1
```
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
                            code_theme="atom-one-dark",
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=550,
                height=500,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _: self._page.close(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.open(snackbar)
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件，加载第一个 SQL 文件内容。
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        # 只处理第一个 SQL 文件
        sql_file = None
        for f in files:
            if f.suffix.lower() == '.sql' and f.is_file():
                sql_file = f
                break
        
        if not sql_file:
            return
        
        try:
            content = sql_file.read_text(encoding='utf-8')
            if self.input_text.current:
                self.input_text.current.value = content
            self._show_snack(f"已加载: {sql_file.name}")
            self._page.update()
        except UnicodeDecodeError:
            try:
                content = sql_file.read_text(encoding='gbk')
                if self.input_text.current:
                    self.input_text.current.value = content
                self._show_snack(f"已加载: {sql_file.name}")
                self._page.update()
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
