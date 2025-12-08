# -*- coding: utf-8 -*-
"""颜色工具视图模块。

提供颜色格式转换、颜色选择器等功能。
"""

import asyncio
import base64
import colorsys
import io
import re
from typing import Callable, Optional, Tuple

import flet as ft
from PIL import Image

from constants import PADDING_MEDIUM, PADDING_SMALL


class ColorToolView(ft.Container):
    """颜色工具视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化颜色工具视图。
        
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
        
        # 当前颜色
        self.current_color = "#3498DB"
        
        # 图片取色相关
        self.current_image = None  # PIL Image 对象
        self.current_image_path = None
        self.img_display_width = 0  # 图片实际显示宽度
        self.img_display_height = 0  # 图片实际显示高度
        self.img_display_x = 0  # 图片在容器中的 X 偏移
        self.img_display_y = 0  # 图片在容器中的 Y 偏移
        
        # 控件引用
        self.color_display = ft.Ref[ft.Container]()
        self.hex_input = ft.Ref[ft.TextField]()
        self.rgb_r = ft.Ref[ft.TextField]()
        self.rgb_g = ft.Ref[ft.TextField]()
        self.rgb_b = ft.Ref[ft.TextField]()
        self.hsl_h = ft.Ref[ft.TextField]()
        self.hsl_s = ft.Ref[ft.TextField]()
        self.hsl_l = ft.Ref[ft.TextField]()
        self.preset_colors = ft.Ref[ft.Row]()
        self.picker_image = ft.Ref[ft.Image]()
        self.picker_container = ft.Ref[ft.Container]()
        
        # 文件选择器
        self.file_picker = ft.FilePicker(on_result=self._on_file_selected)
        
        self._build_ui()
        self._update_all_formats()
    
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
                ft.Text("颜色工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 添加文件选择器到页面
        self.page.overlay.append(self.file_picker)
        
        # 颜色显示区
        color_display_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("当前颜色", weight=ft.FontWeight.BOLD, size=16),
                    ft.Container(
                        ref=self.color_display,
                        height=100,
                        border_radius=8,
                        bgcolor=self.current_color,
                        border=ft.border.all(2, ft.Colors.OUTLINE),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
        )
        
        # 图片取色器区域
        picker_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("图片取色器", weight=ft.FontWeight.BOLD, size=16),
                            ft.Container(expand=True),
                            ft.ElevatedButton(
                                text="选择图片",
                                icon=ft.Icons.IMAGE,
                                on_click=lambda _: self.file_picker.pick_files(
                                    allowed_extensions=["png", "jpg", "jpeg", "gif", "bmp", "webp"],
                                    allow_multiple=False,
                                ),
                            ),
                        ],
                    ),
                    ft.Container(
                        ref=self.picker_container,
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE, size=48, color=ft.Colors.GREY_400),
                                ft.Text('点击"选择图片"加载图片', color=ft.Colors.GREY_500, size=14),
                                ft.Text("然后点击图片上的任意位置取色", color=ft.Colors.GREY_500, size=12),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        height=300,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        alignment=ft.alignment.center,
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # HEX 格式
        hex_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("HEX 格式", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.hex_input,
                                label="HEX",
                                hint_text="#3498DB",
                                expand=True,
                                on_submit=self._on_hex_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="应用",
                                on_click=self._on_hex_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                tooltip="复制",
                                on_click=lambda _: self._copy_text(self.hex_input.current.value),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # RGB 格式
        rgb_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("RGB 格式", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.rgb_r,
                                label="R (0-255)",
                                width=100,
                                on_submit=self._on_rgb_change,
                            ),
                            ft.TextField(
                                ref=self.rgb_g,
                                label="G (0-255)",
                                width=100,
                                on_submit=self._on_rgb_change,
                            ),
                            ft.TextField(
                                ref=self.rgb_b,
                                label="B (0-255)",
                                width=100,
                                on_submit=self._on_rgb_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="应用",
                                on_click=self._on_rgb_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                tooltip="复制",
                                on_click=self._copy_rgb,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # HSL 格式
        hsl_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("HSL 格式", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.hsl_h,
                                label="H (0-360)",
                                width=100,
                                on_submit=self._on_hsl_change,
                            ),
                            ft.TextField(
                                ref=self.hsl_s,
                                label="S (0-100)",
                                width=100,
                                on_submit=self._on_hsl_change,
                            ),
                            ft.TextField(
                                ref=self.hsl_l,
                                label="L (0-100)",
                                width=100,
                                on_submit=self._on_hsl_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="应用",
                                on_click=self._on_hsl_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                tooltip="复制",
                                on_click=self._copy_hsl,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 预设颜色
        preset_colors_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预设颜色", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        ref=self.preset_colors,
                        controls=self._build_preset_colors(),
                        wrap=True,
                        spacing=5,
                        run_spacing=5,
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
                color_display_section,
                ft.Container(height=PADDING_SMALL),
                picker_section,
                ft.Container(height=PADDING_SMALL),
                hex_section,
                ft.Container(height=PADDING_SMALL),
                rgb_section,
                ft.Container(height=PADDING_SMALL),
                hsl_section,
                ft.Container(height=PADDING_SMALL),
                preset_colors_section,
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
    
    def _build_preset_colors(self):
        """构建预设颜色按钮。"""
        preset_colors = [
            "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
            "#00FFFF", "#0000FF", "#8B00FF", "#FF1493",
            "#000000", "#808080", "#C0C0C0", "#FFFFFF",
            "#E74C3C", "#3498DB", "#2ECC71", "#F39C12",
            "#9B59B6", "#1ABC9C", "#34495E", "#95A5A6",
        ]
        
        controls = []
        for color in preset_colors:
            controls.append(
                ft.Container(
                    content=ft.Text(""),
                    width=40,
                    height=40,
                    bgcolor=color,
                    border_radius=4,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    tooltip=color,
                    on_click=lambda e, c=color: self._set_color(c),
                    ink=True,
                )
            )
        
        return controls
    
    def _set_color(self, color: str):
        """设置当前颜色。"""
        self.current_color = color
        self.color_display.current.bgcolor = color
        self._update_all_formats()
        self.update()
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """HEX 转 RGB。"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """RGB 转 HEX。"""
        return f"#{r:02X}{g:02X}{b:02X}"
    
    def _rgb_to_hsl(self, r: int, g: int, b: int) -> Tuple[int, int, int]:
        """RGB 转 HSL。"""
        h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
        return (int(h * 360), int(s * 100), int(l * 100))
    
    def _hsl_to_rgb(self, h: int, s: int, l: int) -> Tuple[int, int, int]:
        """HSL 转 RGB。"""
        r, g, b = colorsys.hls_to_rgb(h/360, l/100, s/100)
        return (int(r * 255), int(g * 255), int(b * 255))
    
    def _update_all_formats(self):
        """更新所有格式显示。"""
        # 更新 HEX
        self.hex_input.current.value = self.current_color
        
        # 更新 RGB
        r, g, b = self._hex_to_rgb(self.current_color)
        self.rgb_r.current.value = str(r)
        self.rgb_g.current.value = str(g)
        self.rgb_b.current.value = str(b)
        
        # 更新 HSL
        h, s, l = self._rgb_to_hsl(r, g, b)
        self.hsl_h.current.value = str(h)
        self.hsl_s.current.value = str(s)
        self.hsl_l.current.value = str(l)
    
    def _on_hex_change(self, e):
        """HEX 值改变。"""
        hex_value = self.hex_input.current.value
        if not hex_value:
            return
        
        # 验证 HEX 格式
        if not re.match(r'^#?[0-9A-Fa-f]{6}$', hex_value):
            self._show_snack("无效的 HEX 颜色值", error=True)
            return
        
        if not hex_value.startswith('#'):
            hex_value = '#' + hex_value
        
        self._set_color(hex_value.upper())
    
    def _on_rgb_change(self, e):
        """RGB 值改变。"""
        try:
            r = int(self.rgb_r.current.value)
            g = int(self.rgb_g.current.value)
            b = int(self.rgb_b.current.value)
            
            if not all(0 <= v <= 255 for v in (r, g, b)):
                self._show_snack("RGB 值必须在 0-255 之间", error=True)
                return
            
            hex_color = self._rgb_to_hex(r, g, b)
            self._set_color(hex_color)
            
        except ValueError:
            self._show_snack("请输入有效的 RGB 值", error=True)
    
    def _on_hsl_change(self, e):
        """HSL 值改变。"""
        try:
            h = int(self.hsl_h.current.value)
            s = int(self.hsl_s.current.value)
            l = int(self.hsl_l.current.value)
            
            if not (0 <= h <= 360 and 0 <= s <= 100 and 0 <= l <= 100):
                self._show_snack("HSL 值范围不正确", error=True)
                return
            
            r, g, b = self._hsl_to_rgb(h, s, l)
            hex_color = self._rgb_to_hex(r, g, b)
            self._set_color(hex_color)
            
        except ValueError:
            self._show_snack("请输入有效的 HSL 值", error=True)
    
    def _copy_rgb(self, e):
        """复制 RGB 值。"""
        rgb_str = f"rgb({self.rgb_r.current.value}, {self.rgb_g.current.value}, {self.rgb_b.current.value})"
        self.page.set_clipboard(rgb_str)
        self._show_snack("已复制到剪贴板")
    
    def _copy_hsl(self, e):
        """复制 HSL 值。"""
        hsl_str = f"hsl({self.hsl_h.current.value}, {self.hsl_s.current.value}%, {self.hsl_l.current.value}%)"
        self.page.set_clipboard(hsl_str)
        self._show_snack("已复制到剪贴板")
    
    def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        
        self.page.set_clipboard(text)
        self._show_snack("已复制到剪贴板")
    
    def _on_file_selected(self, e: ft.FilePickerResultEvent):
        """文件选择回调。"""
        if not e.files or len(e.files) == 0:
            return
        
        try:
            # 获取选择的文件路径
            file_path = e.files[0].path
            self.current_image_path = file_path
            
            # 加载图片
            self.current_image = Image.open(file_path)
            
            # 显示图片
            self._display_picker_image()
            
            self._show_snack("图片已加载，点击图片取色")
            
        except Exception as ex:
            self._show_snack(f"加载图片失败: {str(ex)}", error=True)
    
    def _display_picker_image(self):
        """显示取色器图片。"""
        if not self.current_image:
            return
        
        # 将图片转换为 base64
        img_buffer = io.BytesIO()
        self.current_image.save(img_buffer, format='PNG')
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        # 容器固定尺寸
        container_width = 800
        container_height = 300
        
        # 计算图片在容器中的显示区域（CONTAIN 模式）
        self._calculate_image_display_bounds(container_width, container_height)
        
        # 创建一个 Stack 来叠加图片和点击区域
        clickable_stack = ft.GestureDetector(
            content=ft.Stack(
                controls=[
                    # 背景容器（用于定位）
                    ft.Container(
                        width=container_width,
                        height=container_height,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                    ),
                    # 图片（使用 CONTAIN 模式）
                    ft.Container(
                        content=ft.Image(
                            ref=self.picker_image,
                            src_base64=img_base64,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        width=container_width,
                        height=container_height,
                    ),
                ],
                width=container_width,
                height=container_height,
            ),
            on_tap_down=self._on_image_click,
        )
        
        # 更新容器内容
        self.picker_container.current.content = clickable_stack
        self.picker_container.current.height = container_height
        self.picker_container.current.alignment = None
        self.update()
    
    def _calculate_image_display_bounds(self, canvas_width: int, canvas_height: int):
        """计算图片在画布中的实际显示位置和大小（CONTAIN 模式）。"""
        if not self.current_image:
            return
        
        img_w, img_h = self.current_image.size
        img_ratio = img_w / img_h
        canvas_ratio = canvas_width / canvas_height
        
        # 根据 CONTAIN 模式计算实际显示大小
        if img_ratio > canvas_ratio:
            # 图片更宽，以画布宽度为准
            self.img_display_width = canvas_width
            self.img_display_height = canvas_width / img_ratio
            self.img_display_x = 0
            self.img_display_y = (canvas_height - self.img_display_height) / 2
        else:
            # 图片更高，以画布高度为准
            self.img_display_width = canvas_height * img_ratio
            self.img_display_height = canvas_height
            self.img_display_x = (canvas_width - self.img_display_width) / 2
            self.img_display_y = 0
    
    def _on_image_click(self, e: ft.TapEvent):
        """图片点击事件 - 取色。"""
        if not self.current_image:
            return
        
        try:
            # 获取点击位置（相对于容器）
            local_x = e.local_x
            local_y = e.local_y
            
            # 检查点击是否在图片显示区域内
            if (local_x < self.img_display_x or 
                local_x > self.img_display_x + self.img_display_width or
                local_y < self.img_display_y or 
                local_y > self.img_display_y + self.img_display_height):
                # 点击在图片外
                return
            
            # 将点击坐标转换为相对于图片显示区域的坐标
            relative_x = local_x - self.img_display_x
            relative_y = local_y - self.img_display_y
            
            # 获取原始图片尺寸
            orig_width, orig_height = self.current_image.size
            
            # 计算缩放比例（显示尺寸 → 原始尺寸）
            scale_x = orig_width / self.img_display_width
            scale_y = orig_height / self.img_display_height
            
            # 转换为原始图片坐标
            img_x = int(relative_x * scale_x)
            img_y = int(relative_y * scale_y)
            
            # 确保坐标在图片范围内
            img_x = max(0, min(img_x, orig_width - 1))
            img_y = max(0, min(img_y, orig_height - 1))
            
            # 获取像素颜色
            pixel_color = self.current_image.getpixel((img_x, img_y))
            
            # 处理不同格式的像素值
            if isinstance(pixel_color, int):
                # 灰度图
                r = g = b = pixel_color
            elif len(pixel_color) == 3:
                # RGB
                r, g, b = pixel_color
            elif len(pixel_color) == 4:
                # RGBA
                r, g, b, a = pixel_color
            else:
                return
            
            # 转换为 HEX
            hex_color = f"#{r:02X}{g:02X}{b:02X}"
            
            # 设置颜色
            self._set_color(hex_color)
            
            self._show_snack(f"已取色: {hex_color}")
            
        except Exception as ex:
            self._show_snack(f"取色失败: {str(ex)}", error=True)
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**颜色工具使用说明**

**功能：**
- 🎨 图片取色器 - 从图片中精确取色
- 颜色格式转换（HEX ↔ RGB ↔ HSL）
- 预设颜色选择
- 实时预览
- 一键复制各种格式

**图片取色使用方法：**
1. 点击"选择图片"按钮
2. 选择一张图片（支持 PNG, JPG, GIF, BMP, WebP）
3. 图片加载后，点击图片上的任意位置
4. 自动获取该位置的颜色并更新所有格式

**格式说明：**

1. **HEX (十六进制)**
   - 格式: #RRGGBB
   - 示例: #3498DB
   - 常用于 Web 开发

2. **RGB (红绿蓝)**
   - 范围: R(0-255), G(0-255), B(0-255)
   - 格式: rgb(52, 152, 219)
   - 常用于编程

3. **HSL (色相/饱和度/亮度)**
   - 范围: H(0-360), S(0-100), L(0-100)
   - 格式: hsl(204, 70%, 53%)
   - 便于调整颜色

**使用技巧：**
- 点击预设颜色快速选择
- 修改任一格式，其他格式自动更新
- 点击复制按钮复制对应格式
- 从设计稿、截图中精确提取颜色
- 支持点击图片多次取色
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

