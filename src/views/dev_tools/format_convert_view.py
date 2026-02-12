# -*- coding: utf-8 -*-
"""数据格式转换工具视图模块。

提供 JSON、YAML、XML、TOML 之间的相互转换。
"""

import json
import tomllib  # Python 3.11+ 内置
from typing import Callable, Optional

import flet as ft
import tomli_w
import yaml
import xmltodict

from constants import PADDING_MEDIUM, PADDING_SMALL


class FormatConvertView(ft.Container):
    """数据格式转换工具视图类。"""
    
    FORMATS = ["JSON", "YAML", "XML", "TOML"]
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化数据格式转换工具视图。"""
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
        self.source_format = ft.Ref[ft.Dropdown]()
        self.target_format = ft.Ref[ft.Dropdown]()
        self.input_text = ft.Ref[ft.TextField]()
        self.output_text = ft.Ref[ft.TextField]()
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.Container]()
        self.ratio = 0.5
        self.left_flex = 500
        self.right_flex = 500
        self.is_dragging = False
        
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
                ft.Text("数据格式转换", size=28, weight=ft.FontWeight.BOLD),
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
                    ref=self.source_format,
                    label="源格式",
                    width=120,
                    options=[ft.dropdown.Option(f) for f in self.FORMATS],
                    value="JSON",
                ),
                ft.Icon(ft.Icons.ARROW_FORWARD, size=20, color=ft.Colors.OUTLINE),
                ft.Dropdown(
                    ref=self.target_format,
                    label="目标格式",
                    width=120,
                    options=[ft.dropdown.Option(f) for f in self.FORMATS],
                    value="YAML",
                ),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    content="转换",
                    icon=ft.Icons.TRANSFORM,
                    on_click=self._convert,
                ),
                ft.OutlinedButton(
                    content="交换",
                    icon=ft.Icons.SWAP_HORIZ,
                    on_click=self._swap_formats,
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
                            icon=ft.Icons.PASTE,
                            tooltip="粘贴",
                            icon_size=16,
                            on_click=lambda _: self._paste_text(),
                        ),
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
                        hint_text="在此输入源数据...",
                        text_size=13,
                        border=ft.InputBorder.NONE,
                        text_style=ft.TextStyle(font_family="Consolas,Monospace"),
                        keyboard_type=ft.KeyboardType.MULTILINE,
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
        
        # 左右分栏（可拖动调整宽度）
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

    def _convert(self, e):
        """执行转换。"""
        source_fmt = self.source_format.current.value
        target_fmt = self.target_format.current.value
        input_val = self.input_text.current.value
        
        if not input_val:
            self._show_snack("请输入源数据", error=True)
            return
            
        try:
            # 1. 解析为 Python 对象
            data = None
            if source_fmt == "JSON":
                data = json.loads(input_val)
            elif source_fmt == "YAML":
                data = yaml.safe_load(input_val)
            elif source_fmt == "XML":
                data = xmltodict.parse(input_val)
            elif source_fmt == "TOML":
                data = tomllib.loads(input_val)
            
            if data is None:
                raise ValueError("解析结果为空")
                
            # 2. 转换为目标格式
            output_val = ""
            if target_fmt == "JSON":
                output_val = json.dumps(data, indent=2, ensure_ascii=False)
            elif target_fmt == "YAML":
                output_val = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
            elif target_fmt == "XML":
                # XML需要一个根节点
                if isinstance(data, list):
                    data = {"root": {"item": data}}
                elif isinstance(data, dict) and len(data.keys()) > 1:
                    data = {"root": data}
                output_val = xmltodict.unparse(data, pretty=True)
            elif target_fmt == "TOML":
                output_val = tomli_w.dumps(data)
            
            self.output_text.current.value = output_val
            self.output_text.current.update()
            self._show_snack("转换成功")
            
        except Exception as e:
            # 在输出框显示详细错误信息
            error_msg = f"❌ 转换失败\n\n"
            error_msg += f"源格式: {source_fmt}\n"
            error_msg += f"目标格式: {target_fmt}\n"
            error_msg += f"错误类型: {type(e).__name__}\n"
            error_msg += f"错误信息: {str(e)}\n\n"
            error_msg += "提示：\n"
            error_msg += f"- 请检查输入内容是否为有效的 {source_fmt} 格式\n"
            error_msg += "- JSON 需要正确的语法（引号、逗号、括号等）\n"
            error_msg += "- YAML 需要正确的缩进\n"
            error_msg += "- XML 需要正确的标签结构\n"
            error_msg += "- TOML 需要正确的键值对格式\n"
            
            self.output_text.current.value = error_msg
            self.output_text.current.update()
            self._show_snack(f"转换失败: {str(e)}", error=True)

    def _swap_formats(self, e):
        """交换源格式和目标格式。"""
        s = self.source_format.current.value
        t = self.target_format.current.value
        self.source_format.current.value = t
        self.target_format.current.value = s
        
        # 同时交换内容
        in_val = self.input_text.current.value
        out_val = self.output_text.current.value
        if out_val:
            self.input_text.current.value = out_val
            self.output_text.current.value = ""
        
        self.update()

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
        
    def _paste_text(self):
        try:
            self._page.run_task(self._async_paste)
        except Exception as e:
            self._show_snack(f"粘贴失败: {str(e)}", error=True)
    
    async def _async_paste(self):
        text = await self._page.get_clipboard_async()
        if text:
            self.input_text.current.value = text
            self.input_text.current.update()

    def _on_back_click(self):
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**数据格式转换工具使用说明**

**支持的格式：**
- **JSON**: JavaScript Object Notation
- **YAML**: YAML Ain't Markup Language
- **XML**: eXtensible Markup Language
- **TOML**: Tom's Obvious Minimal Language

**使用步骤：**
1. 选择源格式和目标格式
2. 在左侧输入框粘贴或输入源数据
3. 点击"转换"按钮
4. 在右侧查看转换结果

**快捷操作：**
- **交换**：一键交换源格式和目标格式，同时交换输入输出内容
- **粘贴**：快速从剪贴板粘贴数据
- **复制**：复制输入或输出内容到剪贴板
- **清空**：清空输入和输出框

**示例：**

**JSON 格式：**
```json
{
  "name": "张三",
  "age": 25,
  "skills": ["Python", "JavaScript"]
}
```

**YAML 格式：**
```yaml
name: 张三
age: 25
skills:
  - Python
  - JavaScript
```

**XML 格式：**
```xml
<root>
  <name>张三</name>
  <age>25</age>
  <skills>
    <item>Python</item>
    <item>JavaScript</item>
  </skills>
</root>
```

**TOML 格式：**
```toml
name = "张三"
age = 25
skills = ["Python", "JavaScript"]
```

**注意事项：**
- JSON 转 XML 时，如果有多个根元素会自动包裹 `<root>` 标签
- TOML 不支持顶层数组，转换时请确保数据结构符合 TOML 规范
- 转换时会自动美化格式（缩进、换行）
- 确保输入数据语法正确
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
        """从拖放添加文件，加载第一个数据文件内容并自动检测格式。
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        # 文件扩展名到格式的映射
        ext_to_format = {
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.xml': 'XML',
            '.toml': 'TOML',
        }
        
        # 找到第一个支持的文件
        data_file = None
        detected_format = None
        for f in files:
            ext = f.suffix.lower()
            if ext in ext_to_format and f.is_file():
                data_file = f
                detected_format = ext_to_format[ext]
                break
        
        if not data_file:
            return
        
        try:
            content = data_file.read_text(encoding='utf-8')
            if self.input_text.current:
                self.input_text.current.value = content
            
            # 自动设置源格式
            if self.source_format.current and detected_format:
                self.source_format.current.value = detected_format
            
            self._show_snack(f"已加载: {data_file.name} (检测为 {detected_format})")
            self._page.update()
        except UnicodeDecodeError:
            try:
                content = data_file.read_text(encoding='gbk')
                if self.input_text.current:
                    self.input_text.current.value = content
                if self.source_format.current and detected_format:
                    self.source_format.current.value = detected_format
                self._show_snack(f"已加载: {data_file.name} (检测为 {detected_format})")
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