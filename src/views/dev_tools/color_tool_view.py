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
        self._page = page
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
        self.cmyk_c = ft.Ref[ft.TextField]()
        self.cmyk_m = ft.Ref[ft.TextField]()
        self.cmyk_y = ft.Ref[ft.TextField]()
        self.cmyk_k = ft.Ref[ft.TextField]()
        self.preset_colors = ft.Ref[ft.Row]()
        self.picker_image = ft.Ref[ft.Image]()
        self.picker_container = ft.Ref[ft.Container]()
        
        # 用于防止循环更新的标志
        self._updating = False
        
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
                            ft.Button(
                                content="选择图片",
                                icon=ft.Icons.IMAGE,
                                on_click=self._on_select_image,
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
                        alignment=ft.Alignment.CENTER,
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
                                on_change=self._on_hex_change,
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
                                on_change=self._on_rgb_change,
                            ),
                            ft.TextField(
                                ref=self.rgb_g,
                                label="G (0-255)",
                                width=100,
                                on_change=self._on_rgb_change,
                            ),
                            ft.TextField(
                                ref=self.rgb_b,
                                label="B (0-255)",
                                width=100,
                                on_change=self._on_rgb_change,
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
                                on_change=self._on_hsl_change,
                            ),
                            ft.TextField(
                                ref=self.hsl_s,
                                label="S (0-100)",
                                width=100,
                                on_change=self._on_hsl_change,
                            ),
                            ft.TextField(
                                ref=self.hsl_l,
                                label="L (0-100)",
                                width=100,
                                on_change=self._on_hsl_change,
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
        
        # CMYK 格式
        cmyk_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("CMYK 格式", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.cmyk_c,
                                label="C (0-100)",
                                width=100,
                                on_change=self._on_cmyk_change,
                            ),
                            ft.TextField(
                                ref=self.cmyk_m,
                                label="M (0-100)",
                                width=100,
                                on_change=self._on_cmyk_change,
                            ),
                            ft.TextField(
                                ref=self.cmyk_y,
                                label="Y (0-100)",
                                width=100,
                                on_change=self._on_cmyk_change,
                            ),
                            ft.TextField(
                                ref=self.cmyk_k,
                                label="K (0-100)",
                                width=100,
                                on_change=self._on_cmyk_change,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                tooltip="复制",
                                on_click=self._copy_cmyk,
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
                cmyk_section,
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
    
    def _set_color_from_input(self, color: str, source: str):
        """从输入框设置颜色，排除触发源以避免干扰用户输入。
        
        Args:
            color: HEX 颜色值
            source: 触发源 ("hex", "rgb", "hsl", "cmyk")
        """
        self._updating = True
        try:
            self.current_color = color
            self.color_display.current.bgcolor = color
            
            # 获取 RGB 值
            r, g, b = self._hex_to_rgb(color)
            
            # 更新 HEX（如果不是来源）
            if source != "hex":
                self.hex_input.current.value = color
            
            # 更新 RGB（如果不是来源）
            if source != "rgb":
                self.rgb_r.current.value = str(r)
                self.rgb_g.current.value = str(g)
                self.rgb_b.current.value = str(b)
            
            # 更新 HSL（如果不是来源）
            if source != "hsl":
                h, s, l = self._rgb_to_hsl(r, g, b)
                self.hsl_h.current.value = str(h)
                self.hsl_s.current.value = str(s)
                self.hsl_l.current.value = str(l)
            
            # 更新 CMYK（如果不是来源）
            if source != "cmyk":
                c, m, y, k = self._rgb_to_cmyk(r, g, b)
                self.cmyk_c.current.value = str(c)
                self.cmyk_m.current.value = str(m)
                self.cmyk_y.current.value = str(y)
                self.cmyk_k.current.value = str(k)
            
            self.update()
        finally:
            self._updating = False
    
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
    
    def _rgb_to_cmyk(self, r: int, g: int, b: int) -> Tuple[int, int, int, int]:
        """RGB 转 CMYK。"""
        if r == 0 and g == 0 and b == 0:
            return (0, 0, 0, 100)
        
        # 将 RGB 归一化到 0-1
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0
        
        # 计算 K
        k = 1 - max(r_norm, g_norm, b_norm)
        
        if k == 1:
            return (0, 0, 0, 100)
        
        # 计算 CMY
        c = (1 - r_norm - k) / (1 - k)
        m = (1 - g_norm - k) / (1 - k)
        y = (1 - b_norm - k) / (1 - k)
        
        return (int(c * 100), int(m * 100), int(y * 100), int(k * 100))
    
    def _cmyk_to_rgb(self, c: int, m: int, y: int, k: int) -> Tuple[int, int, int]:
        """CMYK 转 RGB。"""
        # 将 CMYK 归一化到 0-1
        c_norm = c / 100.0
        m_norm = m / 100.0
        y_norm = y / 100.0
        k_norm = k / 100.0
        
        # 计算 RGB
        r = 255 * (1 - c_norm) * (1 - k_norm)
        g = 255 * (1 - m_norm) * (1 - k_norm)
        b = 255 * (1 - y_norm) * (1 - k_norm)
        
        return (int(r), int(g), int(b))
    
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
        
        # 更新 CMYK
        c, m, y, k = self._rgb_to_cmyk(r, g, b)
        self.cmyk_c.current.value = str(c)
        self.cmyk_m.current.value = str(m)
        self.cmyk_y.current.value = str(y)
        self.cmyk_k.current.value = str(k)
    
    def _on_hex_change(self, e):
        """HEX 值改变。"""
        if self._updating:
            return
        
        hex_value = self.hex_input.current.value
        if not hex_value:
            return
        
        # 验证 HEX 格式
        if not re.match(r'^#?[0-9A-Fa-f]{6}$', hex_value):
            return
        
        if not hex_value.startswith('#'):
            hex_value = '#' + hex_value
        
        self._set_color_from_input(hex_value.upper(), "hex")
    
    def _on_rgb_change(self, e):
        """RGB 值改变。"""
        if self._updating:
            return
        
        try:
            r_val = self.rgb_r.current.value
            g_val = self.rgb_g.current.value
            b_val = self.rgb_b.current.value
            
            if not r_val or not g_val or not b_val:
                return
            
            r = int(r_val)
            g = int(g_val)
            b = int(b_val)
            
            if not all(0 <= v <= 255 for v in (r, g, b)):
                return
            
            hex_color = self._rgb_to_hex(r, g, b)
            self._set_color_from_input(hex_color, "rgb")
            
        except ValueError:
            pass
    
    def _on_hsl_change(self, e):
        """HSL 值改变。"""
        if self._updating:
            return
        
        try:
            h_val = self.hsl_h.current.value
            s_val = self.hsl_s.current.value
            l_val = self.hsl_l.current.value
            
            if not h_val or not s_val or not l_val:
                return
            
            h = int(h_val)
            s = int(s_val)
            l = int(l_val)
            
            if not (0 <= h <= 360 and 0 <= s <= 100 and 0 <= l <= 100):
                return
            
            r, g, b = self._hsl_to_rgb(h, s, l)
            hex_color = self._rgb_to_hex(r, g, b)
            self._set_color_from_input(hex_color, "hsl")
            
        except ValueError:
            pass
    
    def _on_cmyk_change(self, e):
        """CMYK 值改变。"""
        if self._updating:
            return
        
        try:
            c_val = self.cmyk_c.current.value
            m_val = self.cmyk_m.current.value
            y_val = self.cmyk_y.current.value
            k_val = self.cmyk_k.current.value
            
            if not c_val or not m_val or not y_val or not k_val:
                return
            
            c = int(c_val)
            m = int(m_val)
            y = int(y_val)
            k = int(k_val)
            
            if not all(0 <= v <= 100 for v in (c, m, y, k)):
                return
            
            r, g, b = self._cmyk_to_rgb(c, m, y, k)
            hex_color = self._rgb_to_hex(r, g, b)
            self._set_color_from_input(hex_color, "cmyk")
            
        except ValueError:
            pass
    
    async def _copy_rgb(self, e):
        """复制 RGB 值。"""
        rgb_str = f"rgb({self.rgb_r.current.value}, {self.rgb_g.current.value}, {self.rgb_b.current.value})"
        await ft.Clipboard().set(rgb_str)
        self._show_snack("已复制到剪贴板")
    
    async def _copy_hsl(self, e):
        """复制 HSL 值。"""
        hsl_str = f"hsl({self.hsl_h.current.value}, {self.hsl_s.current.value}%, {self.hsl_l.current.value}%)"
        await ft.Clipboard().set(hsl_str)
        self._show_snack("已复制到剪贴板")
    
    async def _copy_cmyk(self, e):
        """复制 CMYK 值。"""
        cmyk_str = f"cmyk({self.cmyk_c.current.value}%, {self.cmyk_m.current.value}%, {self.cmyk_y.current.value}%, {self.cmyk_k.current.value}%)"
        await ft.Clipboard().set(cmyk_str)
        self._show_snack("已复制到剪贴板")
    
    async def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        
        await ft.Clipboard().set(text)
        self._show_snack("已复制到剪贴板")
    
    async def _on_select_image(self, e):
        """选择图片按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            allowed_extensions=["png", "jpg", "jpeg", "gif", "bmp", "webp"],
            allow_multiple=False,
        )
        
        if not result or not result.files:
            return
        
        try:
            # 获取选择的文件路径
            file_path = result.files[0].path
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
                            src=img_base64,
                            fit=ft.BoxFit.CONTAIN,
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
- 颜色格式转换（HEX ↔ RGB ↔ HSL ↔ CMYK）
- 预设颜色选择
- 实时预览与自动同步
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

4. **CMYK (印刷四色)**
   - 范围: C(0-100), M(0-100), Y(0-100), K(0-100)
   - 格式: cmyk(78%, 32%, 0%, 14%)
   - 常用于印刷设计

**使用技巧：**
- 点击预设颜色快速选择
- 修改任一格式，其他格式自动同步更新
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
                ft.TextButton("关闭", on_click=lambda _: self._page.close(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.snack_bar.open = True
        self._page.update()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件（图片取色）。
        
        支持图片格式：png, jpg, jpeg, gif, bmp, webp
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        from pathlib import Path
        
        # 支持的图片扩展名
        supported_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        
        # 收集所有文件
        all_files = []
        for f in files:
            path = Path(f) if not isinstance(f, Path) else f
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        # 过滤支持的图片文件
        image_files = [f for f in all_files if f.suffix.lower() in supported_exts]
        
        if not image_files:
            self._show_snack("请拖放图片文件（PNG, JPG, GIF 等）", error=True)
            return
        
        # 只处理第一个图片
        file_path = image_files[0]
        
        try:
            self.current_image_path = str(file_path)
            self.current_image = Image.open(file_path)
            self._display_picker_image()
            self._show_snack(f"已加载图片，点击图片取色")
        except Exception as ex:
            self._show_snack(f"加载图片失败: {str(ex)}", error=True)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
