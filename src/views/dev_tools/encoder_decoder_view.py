# -*- coding: utf-8 -*-
"""编码/解码工具视图模块。

提供常用的编码解码功能：Base64、URL、HTML、Unicode 等。
"""

import asyncio
import base64
import html
import io
import urllib.parse
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class EncoderDecoderView(ft.Container):
    """编码/解码工具视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化编码/解码工具视图。
        
        Args:
            page: Flet 页面对象
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self._page = page
        self.on_back = on_back
        self.expand = True
        self.padding = ft.Padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 控件引用
        self.encode_type = ft.Ref[ft.Dropdown]()
        self.operation = ft.Ref[ft.Dropdown]()
        self.url_mode = ft.Ref[ft.Dropdown]()  # URL 编码模式
        self.input_text = ft.Ref[ft.TextField]()
        self.output_text = ft.Ref[ft.TextField]()
        self.output_image = ft.Ref[ft.Image]()  # 图片预览
        self.output_container = ft.Ref[ft.Container]()  # 输出容器
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.Container]()
        self.ratio = 0.5
        self.left_flex = 500
        self.right_flex = 500
        self.is_dragging = False
        
        # 保存解码后的二进制数据（用于下载）
        self.decoded_binary_data = None
        
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
                ft.Text("编码/解码工具", size=28, weight=ft.FontWeight.BOLD),
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
                    ref=self.encode_type,
                    label="编码类型",
                    width=200,
                    options=[
                        ft.dropdown.Option("Base64"),
                        ft.dropdown.Option("URL"),
                        ft.dropdown.Option("HTML"),
                        ft.dropdown.Option("Unicode"),
                    ],
                    value="Base64",
                    on_select=self._on_type_change,
                ),
                ft.Dropdown(
                    ref=self.operation,
                    label="操作",
                    width=150,
                    options=[
                        ft.dropdown.Option("编码"),
                        ft.dropdown.Option("解码"),
                    ],
                    value="编码",
                ),
                ft.Dropdown(
                    ref=self.url_mode,
                    label="URL 模式",
                    width=180,
                    options=[
                        ft.dropdown.Option("标准"),
                        ft.dropdown.Option("严格"),
                        ft.dropdown.Option("Query String"),
                    ],
                    value="标准",
                    visible=False,  # 默认隐藏，只在选择 URL 时显示
                ),
                ft.Button(
                    content="转换",
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=self._on_convert,
                ),
                ft.Container(expand=True),
                ft.OutlinedButton(
                    content="清空",
                    icon=ft.Icons.CLEAR,
                    on_click=self._on_clear,
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
                            on_click=lambda _: self._page.run_task(self._copy_text, self.input_text.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.input_text,
                        multiline=True,
                        min_lines=15,
                        hint_text='在此输入需要处理的文本...',
                        text_size=13,
                        border=ft.InputBorder.NONE,
                        on_submit=lambda _: self._on_convert(None),
                    ),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
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
                            on_click=lambda _: self._page.run_task(self._copy_text, self.output_text.current.value),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD,
                            tooltip="下载文件",
                            on_click=self._download_file,
                            visible=False,
                        ),
                    ],
                ),
                ft.Container(
                    ref=self.output_container,
                    content=ft.TextField(
                        ref=self.output_text,
                        multiline=True,
                        min_lines=15,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
                    ),
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
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
                margin=ft.Margin.only(top=40, bottom=6),
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
        
        # 主列
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(),
                operation_bar,
                ft.Container(height=PADDING_SMALL),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _reset_output_to_text(self):
        """重置输出显示为文本模式。"""
        self.decoded_binary_data = None
        # 重新创建文本输出框
        self.output_container.current.content = ft.TextField(
            ref=self.output_text,
            multiline=True,
            min_lines=15,
            read_only=True,
            text_size=13,
            border=ft.InputBorder.NONE,
        )
    
    def _decode_base64(self, base64_str: str):
        """智能解码 Base64 数据。"""
        try:
            # 解码 Base64
            decoded_bytes = base64.b64decode(base64_str)
            self.decoded_binary_data = decoded_bytes
            
            # 检测是否是图片
            image_type = self._detect_image_type(decoded_bytes)
            if image_type:
                # 是图片 - 显示预览
                self._show_image_preview(decoded_bytes, image_type)
                return
            
            # 尝试解码为文本
            try:
                text_result = decoded_bytes.decode('utf-8')
                self.output_text.current.value = text_result
                self.update()
            except UnicodeDecodeError:
                # 不是文本，显示二进制信息
                self._show_binary_info(decoded_bytes)
                
        except Exception as e:
            self._show_snack(f"Base64 解码失败: {str(e)}", error=True)
    
    def _detect_image_type(self, data: bytes) -> str:
        """检测数据是否是图片，返回图片类型。"""
        # 检查文件头（魔数）
        if len(data) < 12:
            return ""
        
        # JPEG
        if data[:2] == b'\xff\xd8':
            return "jpeg"
        # PNG
        elif data[:8] == b'\x89PNG\r\n\x1a\n':
            return "png"
        # GIF
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            return "gif"
        # WebP
        elif data[8:12] == b'WEBP':
            return "webp"
        # BMP
        elif data[:2] == b'BM':
            return "bmp"
        # ICO
        elif data[:4] == b'\x00\x00\x01\x00':
            return "ico"
        
        return ""
    
    def _show_image_preview(self, image_data: bytes, image_type: str):
        """显示图片预览。"""
        # 创建图片控件
        image_preview = ft.Column(
            controls=[
                ft.Text(
                    f"📷 检测到图片 ({image_type.upper()})，大小: {len(image_data)} 字节",
                    size=13,
                    color=ft.Colors.GREEN,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=10),
                ft.Image(
                    src=base64.b64encode(image_data).decode('ascii'),
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=8,
                ),
                ft.Container(height=10),
                ft.OutlinedButton(
                    content="保存图片",
                    icon=ft.Icons.SAVE,
                    on_click=self._save_image,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 替换输出容器内容
        self.output_container.current.content = image_preview
        self.update()
    
    def _show_binary_info(self, data: bytes):
        """显示二进制数据信息。"""
        # 显示前 256 字节的十六进制
        hex_preview = ' '.join(f'{b:02x}' for b in data[:256])
        if len(data) > 256:
            hex_preview += '...'
        
        info_text = f"""🔢 检测到二进制数据

大小: {len(data)} 字节

十六进制预览 (前 256 字节):
{hex_preview}

这可能是文件、音频、视频或其他二进制数据。
您可以点击下载按钮保存为文件。"""
        
        self.output_text.current.value = info_text
        self.update()
    
    def _save_image(self, e):
        """保存图片到文件。"""
        if not self.decoded_binary_data:
            return
        
        # 使用文件选择器保存
        self._page.run_task(self._save_image_async)
    
    async def _save_image_async(self):
        """异步保存图片。"""
        try:
            from utils import logger
            import tempfile
            import os
            
            # 检测图片类型
            image_type = self._detect_image_type(self.decoded_binary_data)
            ext = f".{image_type}" if image_type else ".bin"
            
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_file.write(self.decoded_binary_data)
            temp_file.close()
            
            # 打开文件所在文件夹
            import subprocess
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', '/select,', temp_file.name])
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['open', '-R', temp_file.name])
            
            self._show_snack(f"已保存到: {temp_file.name}")
            
        except Exception as e:
            self._show_snack(f"保存失败: {str(e)}", error=True)
    
    def _download_file(self, e):
        """下载二进制文件。"""
        if not self.decoded_binary_data:
            return
        
        self._page.run_task(self._save_image_async)
    
    def _on_type_change(self, e):
        """编码类型改变时的处理。"""
        # 只在选择 URL 类型时显示 URL 模式选择器
        if self.encode_type.current.value == "URL":
            self.url_mode.current.visible = True
        else:
            self.url_mode.current.visible = False
        self.update()
    
    def _on_convert(self, e):
        """执行转换操作。"""
        input_value = self.input_text.current.value
        if not input_value:
            self._show_snack("请输入要处理的文本", error=True)
            return
        
        encode_type = self.encode_type.current.value
        operation = self.operation.current.value
        
        # 重置输出显示为文本模式
        self._reset_output_to_text()
        
        try:
            if encode_type == "Base64":
                if operation == "编码":
                    result = base64.b64encode(input_value.encode('utf-8')).decode('ascii')
                    self.output_text.current.value = result
                else:
                    # Base64 解码 - 需要检测数据类型
                    self._decode_base64(input_value)
                    return  # _decode_base64 会处理输出显示
            
            elif encode_type == "URL":
                url_mode = self.url_mode.current.value
                if operation == "编码":
                    if url_mode == "标准":
                        # 标准模式：保留常用字符 (/, :, ? 等)
                        result = urllib.parse.quote(input_value, safe='/:?#[]@!$&\'()*+,;=')
                    elif url_mode == "严格":
                        # 严格模式：编码所有特殊字符
                        result = urllib.parse.quote(input_value, safe='')
                    else:  # Query String
                        # Query String 模式：空格转为 +
                        result = urllib.parse.quote_plus(input_value)
                else:
                    # 解码时自动处理所有模式
                    if url_mode == "Query String":
                        result = urllib.parse.unquote_plus(input_value)
                    else:
                        result = urllib.parse.unquote(input_value)
            
            elif encode_type == "HTML":
                if operation == "编码":
                    result = html.escape(input_value)
                else:
                    result = html.unescape(input_value)
            
            elif encode_type == "Unicode":
                if operation == "编码":
                    # 转换为 \uXXXX 格式
                    result = input_value.encode('unicode_escape').decode('ascii')
                else:
                    # 从 \uXXXX 格式解码
                    result = input_value.encode('ascii').decode('unicode_escape')
            
            self.output_text.current.value = result
            self.update()
            
        except Exception as e:
            self._show_snack(f"转换失败: {str(e)}", error=True)
    
    def _on_clear(self, e):
        """清空输入和输出。"""
        self.input_text.current.value = ""
        self._reset_output_to_text()
        self.output_text.current.value = ""
        self.decoded_binary_data = None
        self.update()
    
    async def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
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
        
        delta_ratio = e.local_delta.x / container_width
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
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**编码/解码工具使用说明**

**支持的编码类型：**

1. **Base64**
   - 编码：将文本转换为 Base64 格式
   - 解码：智能识别数据类型
     - **图片**：自动显示预览（支持 JPEG, PNG, GIF, WebP, BMP, ICO）
     - **文本**：显示解码后的文本
     - **其他二进制**：显示十六进制预览和文件信息
   - 可保存解码后的图片或文件
   - 常用于二进制数据传输

2. **URL**
   - **标准模式**：保留常用字符（/, :, ?, # 等）
     - 示例：`https://example.com/path` → `https://example.com/path`
   - **严格模式**：编码所有特殊字符（包括 /）
     - 示例：`https://example.com/path` → `https%3A%2F%2Fexample.com%2Fpath`
   - **Query String 模式**：空格转为 `+`，适合表单数据
     - 示例：`hello world` → `hello+world`
   - 常用于 URL 参数传递

3. **HTML**
   - 编码：将特殊字符转换为 HTML 实体（如 &lt; &gt;）
   - 解码：将 HTML 实体还原为原始字符
   - 常用于网页内容显示

4. **Unicode**
   - 编码：将文本转换为 \\uXXXX 格式
   - 解码：将 \\uXXXX 格式还原为文本
   - 常用于跨平台文本传输

**使用步骤：**
1. 选择编码类型
2. 选择操作（编码/解码）
3. 在左侧输入框输入文本
4. 点击"转换"按钮
5. 在右侧查看结果
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
                ft.TextButton("关闭", on_click=lambda _: self._page.pop_dialog()),
            ],
        )
        
        self._page.show_dialog(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.show_dialog(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
