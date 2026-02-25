# -*- coding: utf-8 -*-
"""文本对比工具视图模块。

提供文本对比功能。
"""

import difflib
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL, PADDING_LARGE


class TextDiffView(ft.Container):
    """文本对比工具视图类。

    使用 difflib.ndiff 提供详细的字符级差异对比。
    """

    # 颜色方案
    COLOR_ADDED = ft.Colors.with_opacity(0.2, ft.Colors.GREEN)
    COLOR_REMOVED = ft.Colors.with_opacity(0.2, ft.Colors.RED)
    COLOR_CHANGED = ft.Colors.with_opacity(0.2, ft.Colors.ORANGE)
    COLOR_EQUAL = ft.Colors.TRANSPARENT

    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None,
    ):
        super().__init__()
        self._page = page
        self.on_back = on_back
        self.expand = True
        self.padding = PADDING_MEDIUM

        # 控件引用
        self.left_input = ft.Ref[ft.TextField]()
        self.right_input = ft.Ref[ft.TextField]()
        self.diff_container = ft.Ref[ft.Column]()
        self.left_stats = ft.Ref[ft.Text]()
        self.right_stats = ft.Ref[ft.Text]()
        self.summary_text = ft.Ref[ft.Text]()
        
        # 选项
        self.ignore_case = ft.Ref[ft.Checkbox]()
        self.ignore_whitespace = ft.Ref[ft.Checkbox]()
        self.show_only_diff = ft.Ref[ft.Checkbox]()
        
        # 对比结果数据
        self.diff_results = []
        
        self._build_ui()

    def _build_ui(self):
        """构建用户界面。"""
        
        # 顶部工具栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self._on_back_click(),
                ),
                ft.Text("文本对比", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.INFO_OUTLINE,
                    tooltip="关于",
                    on_click=self._show_about,
                ),
            ],
        )

        # 操作按钮栏
        action_bar = ft.Row(
            controls=[
                ft.Button(
                    "开始对比",
                    icon=ft.Icons.COMPARE_ARROWS,
                    on_click=self._compare,
                ),
                ft.OutlinedButton(
                    "交换左右",
                    icon=ft.Icons.SWAP_HORIZ,
                    on_click=self._swap_texts,
                ),
                ft.OutlinedButton(
                    "清空全部",
                    icon=ft.Icons.CLEAR_ALL,
                    on_click=self._clear_all,
                ),
                ft.VerticalDivider(width=1),
                ft.OutlinedButton(
                    "导出HTML",
                    icon=ft.Icons.FILE_DOWNLOAD,
                    on_click=self._export_html,
                ),
                ft.Container(expand=True),
                ft.Checkbox(
                    ref=self.ignore_case,
                    label="忽略大小写",
                    value=False,
                ),
                ft.Checkbox(
                    ref=self.ignore_whitespace,
                    label="忽略空白符",
                    value=False,
                ),
                ft.Checkbox(
                    ref=self.show_only_diff,
                    label="仅显示差异",
                    value=False,
                    on_change=lambda _: self._refresh_diff_display(),
                ),
            ],
            spacing=PADDING_SMALL,
        )

        # 输入区域
        input_area = ft.Column(
            controls=[
                # 标题栏行
                ft.Row(
                    controls=[
                        ft.Container(
                            content=self._build_panel_header("左侧文本", "left"),
                            expand=True,
                        ),
                        ft.Container(width=PADDING_LARGE), # 与下方分割线宽度一致
                        ft.Container(
                            content=self._build_panel_header("右侧文本", "right"),
                            expand=True,
                        ),
                    ],
                    spacing=0,
                ),
                # 输入框行
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[self._build_text_field("左侧文本", "left")],
                            expand=True,
                            spacing=0,
                        ),
                        ft.VerticalDivider(
                            width=PADDING_LARGE,
                            thickness=1,
                            color=ft.Colors.OUTLINE_VARIANT
                        ),
                        ft.Column(
                            controls=[self._build_text_field("右侧文本", "right")],
                            expand=True,
                            spacing=0,
                        ),
                    ],
                    spacing=0,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ],
            spacing=PADDING_SMALL,
            expand=True,
        )

        # 对比结果区域
        result_header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.DIFFERENCE, size=20),
                ft.Text("对比结果", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Text(
                    "等待对比...",
                    ref=self.summary_text,
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=PADDING_SMALL,
        )

        result_area = ft.Container(
            content=ft.Column(
                ref=self.diff_container,
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.COMPARE_ARROWS, size=64, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "在上方输入文本后点击「开始对比」",
                                    size=14,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_SMALL,
                        ),
                        alignment=ft.Alignment.CENTER,
                        expand=True,
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            padding=PADDING_SMALL,
            expand=True,
        )

        # 主布局 - 让对比结果占更大空间
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(height=1),
                action_bar,
                ft.Container(
                    content=input_area,
                    height=200,  # 固定输入区高度，给结果区更多空间
                ),
                ft.Container(height=PADDING_MEDIUM),
                result_header,
                ft.Container(
                    content=result_area,
                    expand=True,  # 对比结果占据剩余所有空间
                ),
            ],
            spacing=PADDING_SMALL,
            expand=True,
        )

    def _build_panel_header(self, title: str, side: str) -> ft.Container:
        """构建面板标题栏。
        
        Args:
            title: 面板标题
            side: 'left' 或 'right'
        """
        stats_ref = self.left_stats if side == "left" else self.right_stats
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(title, weight=ft.FontWeight.BOLD, size=14),
                    ft.Container(expand=True),
                    ft.Text("0 字符, 0 行", ref=stats_ref, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN,
                        icon_size=18,
                        tooltip="从文件导入",
                        on_click=lambda _, s=side: self._import_file(s),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_PASTE,
                        icon_size=18,
                        tooltip="粘贴",
                        on_click=lambda _, s=side: self._paste_text(s),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLEAR,
                        icon_size=18,
                        tooltip="清空",
                        on_click=lambda _, s=side: self._clear_text(s),
                    ),
                ],
                spacing=4,
            ),
        )

    def _build_text_field(self, title: str, side: str) -> ft.Container:
        """构建文本输入框。
        
        Args:
            title: 面板标题
            side: 'left' 或 'right'
        """
        ref = self.left_input if side == "left" else self.right_input
        
        return ft.Container(
            content=ft.TextField(
                ref=ref,
                multiline=True,
                min_lines=1,
                hint_text=f"在此输入内容或从文件导入",
                border=ft.InputBorder.NONE,
                text_style=ft.TextStyle(
                    font_family="Consolas,Monaco,Courier New,monospace",
                    size=13,
                ),
                expand=True,
                on_change=lambda _, s=side: self._update_stats(s),
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
            expand=True,
        )

    # ==================== 对比逻辑 ==================== #
    
    def _compare(self, e):
        """执行文本对比。"""
        left_text = (self.left_input.current.value or "").strip()
        right_text = (self.right_input.current.value or "").strip()
        
        if not left_text and not right_text:
            self._show_snack("请先输入要对比的文本", error=True)
            return
        
        # 应用选项
        if self.ignore_case.current and self.ignore_case.current.value:
            left_text = left_text.lower()
            right_text = right_text.lower()
        
        if self.ignore_whitespace.current and self.ignore_whitespace.current.value:
            left_lines = [line.strip() for line in left_text.splitlines()]
            right_lines = [line.strip() for line in right_text.splitlines()]
        else:
            left_lines = left_text.splitlines()
            right_lines = right_text.splitlines()
        
        # 使用 ndiff 进行对比
        diff = list(difflib.ndiff(left_lines, right_lines))
        
        # 解析差异
        self.diff_results = self._parse_diff(diff)
        
        # 显示结果
        self._display_diff()
        
        # 更新统计
        self._update_summary()
        
        self._show_snack("对比完成")

    def _parse_diff(self, diff_lines: List[str]) -> List[dict]:
        """解析 ndiff 输出。
        
        Args:
            diff_lines: ndiff 输出的行列表
            
        Returns:
            解析后的差异列表
        """
        results = []
        i = 0
        line_num_left = 1
        line_num_right = 1
        
        while i < len(diff_lines):
            line = diff_lines[i]
            
            if line.startswith('  '):  # 相同行
                results.append({
                    'type': 'equal',
                    'left_line': line_num_left,
                    'right_line': line_num_right,
                    'content': line[2:],
                })
                line_num_left += 1
                line_num_right += 1
            elif line.startswith('- '):  # 删除行
                results.append({
                    'type': 'delete',
                    'left_line': line_num_left,
                    'right_line': None,
                    'content': line[2:],
                })
                line_num_left += 1
            elif line.startswith('+ '):  # 新增行
                results.append({
                    'type': 'insert',
                    'left_line': None,
                    'right_line': line_num_right,
                    'content': line[2:],
                })
                line_num_right += 1
            elif line.startswith('? '):  # 字符级差异提示
                # 这是 ndiff 的特殊标记，表示字符级差异
                if results:
                    results[-1]['hint'] = line[2:]
            
            i += 1
        
        return results

    def _display_diff(self):
        """显示对比结果。"""
        if not self.diff_container.current:
            return
        
        show_only = self.show_only_diff.current and self.show_only_diff.current.value
        
        controls = []
        for item in self.diff_results:
            # 如果只显示差异，跳过相同的行
            if show_only and item['type'] == 'equal':
                continue
            
            controls.append(self._create_diff_line(item))
        
        if not controls:
            controls.append(
                ft.Container(
                    content=ft.Text(
                        "没有发现差异" if show_only else "两个文本完全相同",
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=PADDING_MEDIUM,
                )
            )
        
        self.diff_container.current.controls = controls
        self.diff_container.current.update()

    def _create_diff_line(self, item: dict) -> ft.Container:
        """创建差异行显示。
        
        Args:
            item: 差异项
        """
        diff_type = item['type']
        
        # 确定背景色和图标
        if diff_type == 'equal':
            bg_color = self.COLOR_EQUAL
            icon = None
            icon_color = None
        elif diff_type == 'delete':
            bg_color = self.COLOR_REMOVED
            icon = ft.Icons.REMOVE
            icon_color = ft.Colors.RED
        elif diff_type == 'insert':
            bg_color = self.COLOR_ADDED
            icon = ft.Icons.ADD
            icon_color = ft.Colors.GREEN
        else:
            bg_color = self.COLOR_CHANGED
            icon = ft.Icons.EDIT
            icon_color = ft.Colors.ORANGE
        
        # 行号显示
        left_num = str(item['left_line']) if item['left_line'] else "-"
        right_num = str(item['right_line']) if item['right_line'] else "-"
        
        # 构建文本内容（带高亮）
        content = item['content'] if item['content'] else " "
        hint = item.get('hint')
        
        if hint:
            spans = self._get_styled_spans(content, hint, diff_type)
        else:
            spans = [ft.TextSpan(content)]

        return ft.Container(
            content=ft.Row(
                controls=[
                    # 类型图标
                    ft.Container(
                        content=ft.Icon(icon, size=16, color=icon_color) if icon else None,
                        width=24,
                    ),
                    # 左侧行号
                    ft.Text(
                        left_num,
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        width=40,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                    # 右侧行号
                    ft.Text(
                        right_num,
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        width=40,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                    # 分隔符
                    ft.VerticalDivider(width=1),
                    # 内容
                    ft.Text(
                        spans=spans,
                        size=13,
                        font_family="Consolas,Monaco,Courier New,monospace",
                        expand=True,
                        selectable=True,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            bgcolor=bg_color,
            padding=ft.padding.symmetric(horizontal=PADDING_SMALL, vertical=4),
            border=ft.border.only(bottom=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT)),
        )

    def _get_styled_spans(self, content: str, hint: str, diff_type: str) -> List[ft.TextSpan]:
        """获取带样式的文本段。"""
        if not hint:
            return [ft.TextSpan(content)]
            
        spans = []
        i = 0
        current_segment = ""
        is_highlighted = False
        
        # 高亮颜色配置
        if diff_type == 'insert':
            # 绿色背景加深
            highlight_bg = ft.Colors.with_opacity(0.5, ft.Colors.GREEN)
        elif diff_type == 'delete':
            # 红色背景加深
            highlight_bg = ft.Colors.with_opacity(0.5, ft.Colors.RED)
        else:
            highlight_bg = ft.Colors.with_opacity(0.5, ft.Colors.ORANGE)
            
        while i < len(content):
            # 检查当前字符是否需要高亮
            # hint 可能比 content 短（也可能长，但我们只关心 content 的长度）
            should_highlight = (i < len(hint)) and (hint[i] != ' ')
            
            if should_highlight != is_highlighted:
                # 状态改变，保存之前的段
                if current_segment:
                    style = ft.TextStyle(bgcolor=highlight_bg) if is_highlighted else None
                    spans.append(ft.TextSpan(current_segment, style=style))
                    current_segment = ""
                is_highlighted = should_highlight
            
            current_segment += content[i]
            i += 1
            
        # 保存最后一段
        if current_segment:
            style = ft.TextStyle(bgcolor=highlight_bg) if is_highlighted else None
            spans.append(ft.TextSpan(current_segment, style=style))
            
        return spans

    def _refresh_diff_display(self):
        """刷新差异显示（当切换"仅显示差异"时）。"""
        if self.diff_results:
            self._display_diff()

    def _update_summary(self):
        """更新统计摘要。"""
        if not self.summary_text.current:
            return
        
        added = sum(1 for item in self.diff_results if item['type'] == 'insert')
        removed = sum(1 for item in self.diff_results if item['type'] == 'delete')
        equal = sum(1 for item in self.diff_results if item['type'] == 'equal')
        
        total = len(self.diff_results)
        
        self.summary_text.current.value = (
            f"总计 {total} 行 | "
            f"新增 {added} | "
            f"删除 {removed} | "
            f"相同 {equal}"
        )
        self.summary_text.current.update()

    # ==================== 辅助功能 ==================== #
    
    def _update_stats(self, side: str):
        """更新文本统计。
        
        Args:
            side: 'left' 或 'right'
        """
        input_field = self.left_input.current if side == "left" else self.right_input.current
        stats_field = self.left_stats.current if side == "left" else self.right_stats.current
        
        if not input_field or not stats_field:
            return
        
        text = input_field.value or ""
        chars = len(text)
        lines = len(text.splitlines()) if text else 0
        
        stats_field.value = f"{chars} 字符, {lines} 行"
        stats_field.update()

    def _swap_texts(self, e):
        """交换左右文本。"""
        if not self.left_input.current or not self.right_input.current:
            return
        
        left_val = self.left_input.current.value
        right_val = self.right_input.current.value
        
        self.left_input.current.value = right_val
        self.right_input.current.value = left_val
        
        self.left_input.current.update()
        self.right_input.current.update()
        
        self._update_stats("left")
        self._update_stats("right")

    def _clear_text(self, side: str):
        """清空单侧文本。"""
        input_field = self.left_input.current if side == "left" else self.right_input.current
        
        if input_field:
            input_field.value = ""
            input_field.update()
            self._update_stats(side)

    def _clear_all(self, e):
        """清空所有内容。"""
        self._clear_text("left")
        self._clear_text("right")
        
        if self.diff_container.current:
            self.diff_container.current.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.COMPARE_ARROWS, size=64, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "已清空，请重新输入文本",
                                size=14,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=PADDING_SMALL,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            ]
            self.diff_container.current.update()
        
        if self.summary_text.current:
            self.summary_text.current.value = "等待对比..."
            self.summary_text.current.update()
        
        self.diff_results = []

    async def _import_file(self, side: str):
        """从文件导入文本。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择文本文件",
            allowed_extensions=["txt", "log", "md", "py", "js", "json", "xml", "html", "css", "java", "c", "cpp"],
        )
        
        if not result or not result.files:
            return
        
        file_path = result.files[0].path
        try:
            # 尝试 UTF-8
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试 GBK
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as ex:
                self._show_snack(f"文件读取失败: {ex}", error=True)
                return
        except Exception as ex:
            self._show_snack(f"文件读取失败: {ex}", error=True)
            return
        
        input_field = self.left_input.current if side == "left" else self.right_input.current
        if input_field:
            input_field.value = content
            input_field.update()
            self._update_stats(side)
        
        self._show_snack(f"已导入: {result.files[0].name}")

    def _paste_text(self, side: str):
        """粘贴文本。"""
        async def paste():
            text = await self._page.get_clipboard_async()
            if not text:
                self._show_snack("剪贴板为空", error=True)
                return
            
            input_field = self.left_input.current if side == "left" else self.right_input.current
            if input_field:
                input_field.value = text
                input_field.update()
                self._update_stats(side)
        
        self._page.run_task(paste)

    async def _export_html(self, e):
        """导出为 HTML 文件。"""
        if not self.diff_results:
            self._show_snack("请先执行对比", error=True)
            return
        
        left_text = (self.left_input.current.value or "").strip()
        right_text = (self.right_input.current.value or "").strip()
        
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        
        # 使用 difflib.HtmlDiff 生成 HTML
        html_diff = difflib.HtmlDiff()
        html = html_diff.make_file(
            left_lines,
            right_lines,
            fromdesc="左侧文本",
            todesc="右侧文本",
            context=True,
            numlines=3,
        )
        
        # 保存文件
        result = await ft.FilePicker().save_file(
            dialog_title="导出 HTML",
            file_name="text_diff.html",
            allowed_extensions=["html"],
        )
        
        if result:
            try:
                with open(result, 'w', encoding='utf-8') as f:
                    f.write(html)
                self._show_snack(f"已导出到: {Path(result).name}")
            except Exception as ex:
                self._show_snack(f"导出失败: {ex}", error=True)

    def _show_about(self, e):
        """显示关于信息。"""
        help_text = """
**文本对比工具**

**基于 difflib 的高级文本对比工具**

参考 [pydiff](https://github.com/yelsayd/pydiff) 项目设计理念。

**✨ 功能特性**

- 使用 ndiff 提供详细的行级和字符级差异
- 清晰的颜色高亮显示
- 实时统计信息
- 支持从文件导入
- 支持导出 HTML 格式
- 灵活的对比选项

**📖 使用说明**

1. 在左右输入框输入或导入文本
2. 点击「开始对比」查看差异
3. 可选择忽略大小写、空白符等选项
4. 支持导出为 HTML 文件分享

**🎨 颜色说明**

- 🟢 **绿色** - 新增的内容
- 🔴 **红色** - 删除的内容
- 🟠 **橙色** - 修改的内容
        """
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("关于文本对比工具"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Markdown(
                            help_text,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,  # 关键：支持滚动
                ),
                width=500,
                height=450,
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
            bgcolor=ft.Colors.ERROR if error else ft.Colors.PRIMARY,
        )
        self._page.open(snackbar)

    def _on_back_click(self):
        """返回按钮点击。"""
        if self.on_back:
            self.on_back()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件，加载到左右两个文本框。
        
        第一个文件加载到左侧，第二个文件加载到右侧。
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        # 过滤出有效的文本文件
        valid_files = [f for f in files if f.is_file()]
        
        if not valid_files:
            return
        
        def read_file_content(path) -> str:
            """读取文件内容，自动处理编码。"""
            try:
                return path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    return path.read_text(encoding='gbk')
                except Exception:
                    return path.read_text(encoding='latin-1')
        
        # 加载第一个文件到左侧
        if len(valid_files) >= 1:
            try:
                content = read_file_content(valid_files[0])
                if self.left_input.current:
                    self.left_input.current.value = content
            except Exception as e:
                self._show_snack(f"读取左侧文件失败: {e}", error=True)
                return
        
        # 加载第二个文件到右侧
        if len(valid_files) >= 2:
            try:
                content = read_file_content(valid_files[1])
                if self.right_input.current:
                    self.right_input.current.value = content
            except Exception as e:
                self._show_snack(f"读取右侧文件失败: {e}", error=True)
                return
        
        # 显示加载结果
        if len(valid_files) == 1:
            self._show_snack(f"已加载到左侧: {valid_files[0].name}")
        else:
            self._show_snack(f"已加载: {valid_files[0].name} (左) 和 {valid_files[1].name} (右)")
        
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()