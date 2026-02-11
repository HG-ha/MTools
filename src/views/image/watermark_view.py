# -*- coding: utf-8 -*-
"""图片添加水印视图模块。

提供图片添加水印功能。
"""

import asyncio
import base64
import io
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft
from PIL import Image, ImageDraw, ImageFont

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from utils import get_unique_path


class ImageWatermarkView(ft.Container):
    """图片添加水印视图类。
    
    提供图片添加水印功能，包括：
    - 单个水印：9个位置选择
    - 全屏平铺水印：斜向平铺，防盗图效果
    - 自定义颜色、透明度、字体大小
    - 平铺模式支持自定义角度和间距
    - 批量处理（支持增量选择、文件夹选择）
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', '.tiff'
    }


    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片添加水印视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable] = on_back
        self.expand: bool = True
        
        self.selected_files: List[Path] = []
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 标题栏
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("添加水印", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("选择图片文件", size=16, weight=ft.FontWeight.BOLD),
                            ft.Button(
                                content="选择文件",
                                icon=ft.Icons.FILE_UPLOAD,
                                on_click=self._on_select_files,
                            ),
                            ft.Button(
                                content="选择文件夹",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=self._on_select_folder,
                            ),
                            ft.TextButton(
                                content="清空列表",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=self._on_clear_files,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    # 支持格式说明
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: JPG, PNG, WebP, BMP, TIFF 等 | 支持批量处理",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=4),
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.file_list_view,
                        height=250,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 初始化空状态
        self._init_empty_file_list()
        
        # 水印类型选择（文字/图片）
        self.watermark_type_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="text", label="文字水印"),
                    ft.Radio(value="image", label="图片水印"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="text",
            on_change=self._on_watermark_type_change,
        )
        
        # 水印设置
        self.watermark_text_field = ft.TextField(
            label="水印文字",
            hint_text="输入水印文本",
            value="",
        )
        
        # 水印模式选择
        self.watermark_mode_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="single", label="单个水印"),
                    ft.Radio(value="tile", label="全屏平铺"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="single",
            on_change=self._on_mode_change,
        )
        
        # 单个水印位置
        self.position_dropdown = ft.Dropdown(
            label="位置",
            width=200,
            options=[
                ft.dropdown.Option("top_left", "左上角"),
                ft.dropdown.Option("top_center", "顶部居中"),
                ft.dropdown.Option("top_right", "右上角"),
                ft.dropdown.Option("middle_left", "左侧居中"),
                ft.dropdown.Option("center", "正中央"),
                ft.dropdown.Option("middle_right", "右侧居中"),
                ft.dropdown.Option("bottom_left", "左下角"),
                ft.dropdown.Option("bottom_center", "底部居中"),
                ft.dropdown.Option("bottom_right", "右下角"),
            ],
            value="bottom_right",
        )
        
        self.single_position_container = ft.Container(
            content=self.position_dropdown,
            visible=True,
        )
        
        # 平铺水印设置
        self.tile_angle_slider = ft.Slider(
            min=-45,
            max=45,
            divisions=18,
            value=-30,
            label="{value}°",
        )
        
        self.tile_spacing_h_slider = ft.Slider(
            min=50,
            max=300,
            divisions=25,
            value=150,
            label="{value}px",
        )
        
        self.tile_spacing_v_slider = ft.Slider(
            min=50,
            max=300,
            divisions=25,
            value=100,
            label="{value}px",
        )
        
        self.tile_settings_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("旋转角度", size=12),
                    self.tile_angle_slider,
                    ft.Text("水平间距", size=12),
                    self.tile_spacing_h_slider,
                    ft.Text("垂直间距", size=12),
                    self.tile_spacing_v_slider,
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,
        )
        
        # 图片水印设置
        self.watermark_image_path: Optional[Path] = None
        self.watermark_image_text = ft.Text(
            "未选择水印图片",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 图片水印大小设置
        self.image_size_mode_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="original", label="原始大小"),
                    ft.Radio(value="scale", label="缩放比例"),
                    ft.Radio(value="fixed", label="固定宽度"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="original",
            on_change=self._on_image_size_mode_change,
        )
        
        self.image_scale_slider = ft.Slider(
            min=10,
            max=200,
            divisions=19,
            value=100,
            label="{value}%",
            disabled=True,
        )
        
        self.image_width_field = ft.TextField(
            label="宽度 (像素)",
            hint_text="如: 200",
            value="200",
            width=150,
            disabled=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        self.image_watermark_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Button(
                                content="选择水印图片",
                                icon=ft.Icons.IMAGE,
                                on_click=self._on_select_watermark_image,
                            ),
                            self.watermark_image_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: PNG (推荐透明背景), JPG, GIF (动态水印)",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=4,
                        ),
                        margin=ft.margin.only(top=4),
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("图片大小", size=12),
                    self.image_size_mode_radio,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("缩放比例", size=12),
                    self.image_scale_slider,
                    self.image_width_field,
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,
        )
        
        # 字体选择
        self.font_dropdown = ft.Dropdown(
            label="字体",
            width=200,
            options=[
                ft.dropdown.Option("system", "系统默认"),
                ft.dropdown.Option("msyh", "微软雅黑"),
                ft.dropdown.Option("simsun", "宋体"),
                ft.dropdown.Option("simhei", "黑体"),
                ft.dropdown.Option("kaiti", "楷体"),
                ft.dropdown.Option("arial", "Arial"),
                ft.dropdown.Option("times", "Times New Roman"),
                ft.dropdown.Option("courier", "Courier New"),
                ft.dropdown.Option("custom", "📁 自定义字体..."),
            ],
            value="msyh",
            on_select=self._on_font_change,
        )
        
        # 自定义字体文件路径
        self.custom_font_path: Optional[Path] = None
        
        # 自定义字体显示
        self.custom_font_text = ft.Text(
            "未选择字体文件",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        custom_font_button = ft.Button(
            content="选择字体文件",
            icon=ft.Icons.FONT_DOWNLOAD,
            on_click=self._on_select_font_file,
            height=36,
        )
        
        self.custom_font_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            custom_font_button,
                            self.custom_font_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: TTF, TTC, OTF",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=4,
                        ),
                        margin=ft.margin.only(top=4),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,
        )
        
        # 字体大小模式
        self.font_size_mode_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="fixed", label="固定大小"),
                    ft.Radio(value="auto", label="自适应大小"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="fixed",
            on_change=self._on_font_size_mode_change,
        )
        
        # 固定大小滑块
        self.font_size_slider = ft.Slider(
            min=10,
            max=200,
            divisions=38,
            value=40,
            label="{value}px",
            on_change=lambda e: self._update_preview(),
        )
        
        # 自适应大小滑块（百分比）
        self.font_size_ratio_slider = ft.Slider(
            min=1,
            max=20,
            divisions=19,
            value=5,
            label="{value}%",
            on_change=lambda e: self._update_preview(),
        )
        
        # 固定大小容器
        self.font_size_fixed_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("字体大小（像素）", size=12),
                    self.font_size_slider,
                ],
                spacing=PADDING_SMALL,
            ),
            visible=True,
        )
        
        # 自适应大小容器
        self.font_size_auto_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("字体大小（图片宽度的百分比）", size=12),
                    self.font_size_ratio_slider,
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "自适应模式会根据图片宽度自动调整字体大小",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=4,
                        ),
                        margin=ft.margin.only(top=4),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,
        )
        
        self.opacity_slider = ft.Slider(
            min=0,
            max=100,
            divisions=20,
            value=50,
            label="{value}%",
        )
        
        # 颜色选择
        self.current_color = (255, 255, 255)  # 默认白色
        self.color_preview = ft.Container(
            width=40,
            height=40,
            bgcolor="#ffffff",  # 默认白色
            border_radius=8,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        self.color_field = ft.TextField(
            label="RGB值",
            hint_text="255,255,255",
            value="255,255,255",
            width=150,
            read_only=True,
        )
        
        color_picker_button = ft.Button(
            content="选择颜色",
            icon=ft.Icons.PALETTE,
            on_click=self._open_color_picker,
        )
        
        self.margin_slider = ft.Slider(
            min=10,
            max=100,
            divisions=18,
            value=20,
            label="{value}px",
        )
        
        # 边距容器（仅单个水印模式显示）
        self.margin_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("边距", size=12),
                    self.margin_slider,
                ],
                spacing=0,
            ),
            visible=True,
        )
        
        watermark_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("水印设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("水印类型", size=12),
                    self.watermark_type_radio,
                    ft.Container(height=PADDING_SMALL),
                    # 文字水印设置区域
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.watermark_text_field,
                                ft.Container(height=PADDING_SMALL),
                                ft.Text("水印模式", size=12),
                                self.watermark_mode_radio,
                                ft.Container(height=PADDING_SMALL),
                                self.single_position_container,
                                self.tile_settings_container,
                                ft.Container(height=PADDING_SMALL),
                                ft.Text("字体", size=12),
                                self.font_dropdown,
                                self.custom_font_container,
                                ft.Container(height=PADDING_SMALL),
                                ft.Text("文字颜色", size=12),
                                ft.Row(
                                    controls=[
                                        self.color_preview,
                                        self.color_field,
                                        color_picker_button,
                                    ],
                                    spacing=PADDING_MEDIUM,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Container(height=PADDING_SMALL),
                                ft.Text("字体大小模式", size=12),
                                self.font_size_mode_radio,
                                self.font_size_fixed_container,
                                self.font_size_auto_container,
                            ],
                            spacing=PADDING_SMALL,
                        ),
                        visible=True,
                        ref=ft.Ref[ft.Container](),
                    ),
                    # 图片水印设置区域
                    self.image_watermark_container,
                    # 通用设置（透明度和边距）
                    ft.Text("不透明度", size=12),
                    self.opacity_slider,
                    self.margin_container,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 保存文字水印容器引用
        self.text_watermark_container = watermark_section.content.controls[5]
        
        # 输出设置
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            width=200,
            options=[
                ft.dropdown.Option("same", "保持原格式"),
                ft.dropdown.Option("jpg", "JPEG"),
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("webp", "WebP"),
            ],
            value="same",
        )
        
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="overwrite", label="覆盖原文件"),
                    ft.Radio(value="same", label="保存到原文件目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="same",
            on_change=self._on_output_mode_change,
        )
        
        default_output = self.config_service.get_output_dir() / "watermarked_images"
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(default_output),
            disabled=True,
            expand=True,
            dense=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.output_format_dropdown,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("输出路径:", size=13),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 预览区域
        self.preview_image = ft.Image(
            "",
            visible=False,
            fit=ft.BoxFit.CONTAIN,
            width=400,
            height=400,
        )
        
        self.preview_button = ft.OutlinedButton(
            content="预览效果",
            icon=ft.Icons.PREVIEW,
            on_click=self._on_preview,
        )
        
        self.preview_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预览", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.preview_button,
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.preview_image,
                        alignment=ft.Alignment.CENTER,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_LARGE,
                    ),
                ],
                spacing=PADDING_SMALL,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        # 处理按钮
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.BRANDING_WATERMARK, size=24),
                        ft.Text("添加水印", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 进度显示
        self.progress_text = ft.Text(
            "",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        self.progress_bar = ft.ProgressBar(
            visible=False,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_section,
                ft.Container(height=PADDING_MEDIUM),
                watermark_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
                ft.Container(height=PADDING_MEDIUM),
                self.preview_section,
                ft.Container(height=PADDING_SMALL),
                self.progress_text,
                self.progress_bar,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装视图 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
        )
        
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """将RGB值转换为十六进制颜色。"""
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """将十六进制颜色转换为RGB值。"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _open_color_picker(self, e: ft.ControlEvent) -> None:
        """打开颜色选择器对话框。"""
        # 常用颜色预设
        preset_colors = [
            ("白色", (255, 255, 255)),
            ("黑色", (0, 0, 0)),
            ("红色", (255, 0, 0)),
            ("绿色", (0, 255, 0)),
            ("蓝色", (0, 0, 255)),
            ("黄色", (255, 255, 0)),
            ("青色", (0, 255, 255)),
            ("品红", (255, 0, 255)),
            ("橙色", (255, 165, 0)),
            ("紫色", (128, 0, 128)),
            ("灰色", (128, 128, 128)),
            ("深灰", (64, 64, 64)),
        ]
        
        # RGB 滑块
        r_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_color[0],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        g_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_color[1],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        b_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_color[2],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        # 预览框
        preview_box = ft.Container(
            width=100,
            height=100,
            bgcolor=self._rgb_to_hex(*self.current_color),
            border_radius=12,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        rgb_text = ft.Text(
            f"RGB({self.current_color[0]}, {self.current_color[1]}, {self.current_color[2]})",
            size=14,
            weight=ft.FontWeight.W_500,
        )
        
        # 常用颜色按钮
        preset_buttons = []
        for name, color in preset_colors:
            preset_buttons.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                width=50,
                                height=50,
                                bgcolor=self._rgb_to_hex(*color),
                                border_radius=8,
                                border=ft.border.all(2, ft.Colors.OUTLINE),
                                ink=True,
                                on_click=lambda e, c=color: self._apply_preset_color(
                                    c, r_slider, g_slider, b_slider, preview_box, rgb_text
                                ),
                            ),
                            ft.Text(name, size=10, text_align=ft.TextAlign.CENTER),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=4,
                )
            )
        
        def close_dialog(apply: bool):
            if apply:
                # 应用选择的颜色
                self.current_color = (
                    int(r_slider.value),
                    int(g_slider.value),
                    int(b_slider.value),
                )
                self._update_color_display()
            dialog.open = False
            self._page.update()
        
        # 创建对话框
        dialog = ft.AlertDialog(
            title=ft.Text("选择水印颜色"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        # 预览区域
                        ft.Row(
                            controls=[
                                preview_box,
                                ft.Column(
                                    controls=[
                                        rgb_text,
                                        ft.Text("调整RGB值:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                            ],
                            spacing=PADDING_LARGE,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Divider(),
                        # RGB滑块
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("R:", width=20, color=ft.Colors.RED),
                                        ft.Container(content=r_slider, expand=True),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("G:", width=20, color=ft.Colors.GREEN),
                                        ft.Container(content=g_slider, expand=True),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("B:", width=20, color=ft.Colors.BLUE),
                                        ft.Container(content=b_slider, expand=True),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                            ],
                            spacing=PADDING_SMALL,
                        ),
                        ft.Divider(),
                        # 常用颜色
                        ft.Text("常用颜色:", size=12, weight=ft.FontWeight.W_500),
                        ft.Row(
                            controls=preset_buttons,
                            wrap=True,
                            spacing=PADDING_SMALL,
                            run_spacing=PADDING_SMALL,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=500,
                height=500,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: close_dialog(False)),
                ft.Button("确定", on_click=lambda e: close_dialog(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    def _update_color_preview_in_dialog(
        self,
        r: int,
        g: int,
        b: int,
        preview_box: ft.Container,
        rgb_text: ft.Text
    ) -> None:
        """更新对话框中的颜色预览。"""
        preview_box.bgcolor = self._rgb_to_hex(r, g, b)
        rgb_text.value = f"RGB({r}, {g}, {b})"
        preview_box.update()
        rgb_text.update()
    
    def _apply_preset_color(
        self,
        color: tuple,
        r_slider: ft.Slider,
        g_slider: ft.Slider,
        b_slider: ft.Slider,
        preview_box: ft.Container,
        rgb_text: ft.Text
    ) -> None:
        """应用预设颜色。"""
        r_slider.value = color[0]
        g_slider.value = color[1]
        b_slider.value = color[2]
        r_slider.update()
        g_slider.update()
        b_slider.update()
        self._update_color_preview_in_dialog(
            color[0], color[1], color[2], preview_box, rgb_text
        )
    
    def _update_color_display(self) -> None:
        """更新颜色显示。"""
        self.color_preview.bgcolor = self._rgb_to_hex(*self.current_color)
        self.color_field.value = f"{self.current_color[0]},{self.current_color[1]},{self.current_color[2]}"
        self.color_preview.update()
        self.color_field.update()
    
    def _init_empty_file_list(self) -> None:
        """初始化空文件列表状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处或选择按钮添加图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                height=250,  # 固定高度以确保填满显示区域
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._on_select_files(e),
                ink=True,
                tooltip="点击选择图片文件",
            )
        )
    
    def _on_watermark_type_change(self, e: ft.ControlEvent) -> None:
        """水印类型改变事件。"""
        watermark_type = e.control.value
        
        if watermark_type == "text":
            self.text_watermark_container.visible = True
            self.image_watermark_container.visible = False
        else:
            self.text_watermark_container.visible = False
            self.image_watermark_container.visible = True
        
        self.text_watermark_container.update()
        self.image_watermark_container.update()
    
    async def _on_select_watermark_image(self, e: ft.ControlEvent) -> None:
        """选择水印图片按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择水印图片",
            allowed_extensions=["png", "jpg", "jpeg", "gif", "PNG", "JPG", "JPEG", "GIF"],
            allow_multiple=False,
        )
        if result and len(result) > 0:
            self.watermark_image_path = Path(result[0].path)
            self.watermark_image_text.value = self.watermark_image_path.name
            self.watermark_image_text.update()
            
            # 更新预览
            self._update_preview()
    
    def _on_image_size_mode_change(self, e: ft.ControlEvent) -> None:
        """图片大小模式改变事件。"""
        mode = e.control.value
        
        if mode == "original":
            self.image_scale_slider.disabled = True
            self.image_width_field.disabled = True
        elif mode == "scale":
            self.image_scale_slider.disabled = False
            self.image_width_field.disabled = True
        else:  # fixed
            self.image_scale_slider.disabled = True
            self.image_width_field.disabled = False
        
        self.image_scale_slider.update()
        self.image_width_field.update()
        
        # 更新预览
        self._update_preview()
    
    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """水印模式改变事件。"""
        mode = e.control.value
        
        if mode == "single":
            # 单个水印模式
            self.single_position_container.visible = True
            self.tile_settings_container.visible = False
            self.margin_container.visible = True
        else:
            # 平铺水印模式
            self.single_position_container.visible = False
            self.tile_settings_container.visible = True
            self.margin_container.visible = False
        
        self.single_position_container.update()
        self.tile_settings_container.update()
        self.margin_container.update()
    
    def _on_font_change(self, e: ft.ControlEvent) -> None:
        """字体选择改变事件。"""
        font_choice = e.control.value
        
        if font_choice == "custom":
            # 显示自定义字体选择区域
            self.custom_font_container.visible = True
        else:
            # 隐藏自定义字体选择区域
            self.custom_font_container.visible = False
        
        self.custom_font_container.update()
        
        # 更新预览
        self._update_preview()
    
    async def _on_select_font_file(self, e: ft.ControlEvent) -> None:
        """选择字体文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择字体文件",
            allowed_extensions=["ttf", "ttc", "otf", "TTF", "TTC", "OTF"],
            allow_multiple=False,
        )
        if result and len(result) > 0:
            self.custom_font_path = Path(result[0].path)
            self.custom_font_text.value = self.custom_font_path.name
            self.custom_font_text.update()
            
            # 更新预览
            self._update_preview()
    
    def _on_font_size_mode_change(self, e: ft.ControlEvent) -> None:
        """字体大小模式改变事件。"""
        mode = e.control.value
        if mode == "fixed":
            self.font_size_fixed_container.visible = True
            self.font_size_auto_container.visible = False
        else:
            self.font_size_fixed_container.visible = False
            self.font_size_auto_container.visible = True
        
        self.font_size_fixed_container.update()
        self.font_size_auto_container.update()
        
        # 更新预览
        self._update_preview()
    
    def _update_preview(self) -> None:
        """更新预览（当设置改变时自动调用）。"""
        # 如果已经选择了文件，自动生成预览
        if self.selected_files and self.preview_section.visible:
            async def _delayed():
                await asyncio.sleep(0.1)  # 100ms延迟
                try:
                    self._on_preview(None)
                except Exception:
                    pass
            self._page.run_task(_delayed)
    
    def _get_font(self, font_size: int) -> ImageFont.FreeTypeFont:
        """获取选择的字体。
        
        Args:
            font_size: 字体大小
        
        Returns:
            字体对象
        """
        font_choice = self.font_dropdown.value
        
        # 如果选择自定义字体
        if font_choice == "custom":
            if self.custom_font_path and self.custom_font_path.exists():
                try:
                    return ImageFont.truetype(str(self.custom_font_path), font_size)
                except Exception as e:
                    # 加载失败，降级到微软雅黑
                    pass
            else:
                # 没有选择自定义字体文件，降级到微软雅黑
                pass
        
        # 字体文件映射
        font_map = {
            "msyh": ["msyh.ttc", "msyh.ttf"],  # 微软雅黑
            "simsun": ["simsun.ttc", "simsun.ttf"],  # 宋体
            "simhei": ["simhei.ttf"],  # 黑体
            "kaiti": ["simkai.ttf", "kaiti.ttf"],  # 楷体
            "arial": ["arial.ttf", "Arial.ttf"],  # Arial
            "times": ["times.ttf", "Times New Roman.ttf"],  # Times New Roman
            "courier": ["cour.ttf", "Courier New.ttf"],  # Courier New
        }
        
        # 如果选择系统默认，直接返回默认字体
        if font_choice == "system":
            return ImageFont.load_default()
        
        # 尝试加载选择的字体
        if font_choice in font_map:
            for font_file in font_map[font_choice]:
                try:
                    return ImageFont.truetype(font_file, font_size)
                except:
                    continue
        
        # 如果选择的字体加载失败，尝试微软雅黑
        try:
            return ImageFont.truetype("msyh.ttc", font_size)
        except:
            pass
        
        # 最后尝试 Arial
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except:
            pass
        
        # 都失败了，返回默认字体
        return ImageFont.load_default()
    
    def _calculate_font_size(self, img_width: int) -> int:
        """计算字体大小。
        
        Args:
            img_width: 图片宽度
        
        Returns:
            计算后的字体大小
        """
        font_size_mode = self.font_size_mode_radio.value
        
        if font_size_mode == "fixed":
            # 固定大小模式
            return int(self.font_size_slider.value)
        else:
            # 自适应大小模式（按图片宽度百分比）
            ratio = self.font_size_ratio_slider.value / 100
            calculated_size = int(img_width * ratio)
            # 限制最小和最大值
            return max(10, min(500, calculated_size))
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件（增量选择）。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "webp"],
            allow_multiple=True,
        )
        if result and len(result) > 0:
            # 追加新文件，而不是替换
            new_files = [Path(f.path) for f in result]
            for new_file in new_files:
                # 避免重复添加
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            
            self._update_file_list()
            
            # 显示预览区域
            if self.selected_files:
                self.preview_section.visible = True
                self.preview_section.update()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择图片文件夹")
        if folder_path:
            folder = Path(folder_path)
            # 获取文件夹中的所有图片
            extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
            for ext in extensions:
                for file_path in folder.glob(f"*{ext}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                for file_path in folder.glob(f"*{ext.upper()}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            
            self._update_file_list()
            
            # 显示预览区域
            if self.selected_files:
                self.preview_section.visible = True
                self.preview_section.update()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
        
        # 隐藏预览区域
        self.preview_section.visible = False
        self.preview_image.visible = False
        self.preview_section.update()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            # 空状态
            self._init_empty_file_list()
        else:
            # 显示文件列表
            for idx, file_path in enumerate(self.selected_files):
                # 获取文件信息
                try:
                    file_size = file_path.stat().st_size
                    size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB"
                except:
                    size_str = "未知"
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                # 序号
                                ft.Container(
                                    content=ft.Text(
                                        str(idx + 1),
                                        size=12,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    width=30,
                                    alignment=ft.Alignment.CENTER,
                                ),
                                # 文件图标
                                ft.Icon(ft.Icons.IMAGE, size=18, color=ft.Colors.PRIMARY),
                                # 文件信息
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            file_path.name,
                                            size=12,
                                            weight=ft.FontWeight.W_500,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            size_str,
                                            size=10,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                # 删除按钮
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=18,
                                    tooltip="删除",
                                    on_click=lambda e, path=file_path: self._on_remove_file(path),
                                ),
                            ],
                            spacing=PADDING_SMALL,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=PADDING_SMALL, vertical=4),
                        border_radius=4,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY) if idx % 2 == 0 else None,
                    )
                )
        
        self.file_list_view.update()
    
    def _on_remove_file(self, file_path: Path) -> None:
        """移除单个文件。"""
        if file_path in self.selected_files:
            # 记录删除的是否是第一个文件
            was_first = (self.selected_files[0] == file_path) if self.selected_files else False
            
            self.selected_files.remove(file_path)
            self._update_file_list()
            
            # 如果没有文件了，隐藏预览区域
            if not self.selected_files:
                self.preview_section.visible = False
                self.preview_image.visible = False
                self.preview_section.update()
            # 如果删除的是第一个文件，且预览当前可见，自动重新生成预览
            elif was_first and self.preview_image.visible:
                self._on_preview(None)
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        is_custom = e.control.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        try:
            self._page.update()
        except:
            pass
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            try:
                self._page.update()
            except:
                pass
    
    def _on_preview(self, e: Optional[ft.ControlEvent]) -> None:
        """预览按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        watermark_type = self.watermark_type_radio.value
        
        # 检查水印内容
        if watermark_type == "text":
            watermark_text = self.watermark_text_field.value.strip()
            if not watermark_text:
                self._show_message("请输入水印文字", ft.Colors.ERROR)
                return
        else:
            if not self.watermark_image_path or not self.watermark_image_path.exists():
                self._show_message("请选择水印图片", ft.Colors.ERROR)
                return
        
        try:
            # 使用第一个文件生成预览
            preview_file = self.selected_files[0]
            
            if not preview_file.exists():
                self._show_message("文件不存在", ft.Colors.ERROR)
                return
            
            # 读取图片
            img = Image.open(preview_file)
            
            # 转换为RGBA模式以支持透明度
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 获取图片尺寸
            img_width, img_height = img.size
            
            # 获取设置
            opacity = int(self.opacity_slider.value * 255 / 100)
            watermark_mode = self.watermark_mode_radio.value
            
            if watermark_type == "text":
                # 文字水印处理
                watermark_text = self.watermark_text_field.value.strip()
                text_color = self.current_color
                
                # 单个水印模式的设置
                margin = int(self.margin_slider.value)
                position = self.position_dropdown.value
                
                # 平铺水印模式的设置
                tile_angle = int(self.tile_angle_slider.value)
                tile_spacing_h = int(self.tile_spacing_h_slider.value)
                tile_spacing_v = int(self.tile_spacing_v_slider.value)
                
                # 计算字体大小（根据模式：固定或自适应）
                font_size = self._calculate_font_size(img_width)
                
                # 创建文字层
                txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(txt_layer)
                
                # 加载选择的字体
                font = self._get_font(font_size)
                
                # 获取文字大小
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                text_color_with_alpha = text_color + (opacity,)
                
                if watermark_mode == "single":
                    # 单个水印模式
                    if position == "top_left":
                        x, y = margin, margin
                    elif position == "top_center":
                        x, y = (img_width - text_width) // 2, margin
                    elif position == "top_right":
                        x, y = img_width - text_width - margin, margin
                    elif position == "middle_left":
                        x, y = margin, (img_height - text_height) // 2
                    elif position == "center":
                        x, y = (img_width - text_width) // 2, (img_height - text_height) // 2
                    elif position == "middle_right":
                        x, y = img_width - text_width - margin, (img_height - text_height) // 2
                    elif position == "bottom_left":
                        x, y = margin, img_height - text_height - margin
                    elif position == "bottom_center":
                        x, y = (img_width - text_width) // 2, img_height - text_height - margin
                    else:  # bottom_right
                        x, y = img_width - text_width - margin, img_height - text_height - margin
                    
                    # 绘制单个文字
                    draw.text((x, y), watermark_text, font=font, fill=text_color_with_alpha)
                
                else:
                    # 平铺水印模式
                    # 创建一个临时图层用于旋转文字
                    temp_layer = Image.new('RGBA', (text_width + 50, text_height + 50), (255, 255, 255, 0))
                    temp_draw = ImageDraw.Draw(temp_layer)
                    temp_draw.text((25, 25), watermark_text, font=font, fill=text_color_with_alpha)
                    
                    # 旋转文字
                    if tile_angle != 0:
                        temp_layer = temp_layer.rotate(tile_angle, expand=True)
                    
                    rotated_width, rotated_height = temp_layer.size
                    
                    # 计算需要平铺的行列数
                    cols = (img_width // tile_spacing_h) + 2
                    rows = (img_height // tile_spacing_v) + 2
                    
                    # 平铺水印
                    for row in range(rows):
                        for col in range(cols):
                            x = col * tile_spacing_h - rotated_width // 2
                            y = row * tile_spacing_v - rotated_height // 2
                            
                            # 确保在图片范围内
                            if x + rotated_width > 0 and x < img_width and y + rotated_height > 0 and y < img_height:
                                txt_layer.paste(temp_layer, (x, y), temp_layer)
                
                # 合并图层
                preview_img = Image.alpha_composite(img, txt_layer)
            
            else:
                # 图片水印处理
                watermark_img = Image.open(self.watermark_image_path)
                
                # 转换为RGBA模式
                if watermark_img.mode != 'RGBA':
                    watermark_img = watermark_img.convert('RGBA')
                
                # 调整图片水印大小
                size_mode = self.image_size_mode_radio.value
                if size_mode == "scale":
                    # 按比例缩放
                    scale_percent = int(self.image_scale_slider.value) / 100.0
                    new_width = int(watermark_img.width * scale_percent)
                    new_height = int(watermark_img.height * scale_percent)
                    watermark_img = watermark_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                elif size_mode == "fixed":
                    # 固定宽度，高度按比例
                    try:
                        width = int(self.image_width_field.value)
                        ratio = width / watermark_img.width
                        height = int(watermark_img.height * ratio)
                        watermark_img = watermark_img.resize((width, height), Image.Resampling.LANCZOS)
                    except (ValueError, TypeError):
                        pass  # 保持原始大小
                # original 模式不做处理
                
                # 调整透明度
                if opacity < 255:
                    alpha = watermark_img.split()[3]
                    alpha = Image.eval(alpha, lambda a: int(a * opacity / 255))
                    watermark_img.putalpha(alpha)
                
                # 创建水印层
                txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
                
                # 只支持单个水印模式（图片水印不支持平铺）
                margin = int(self.margin_slider.value)
                position = self.position_dropdown.value
                
                wm_width, wm_height = watermark_img.size
                
                if position == "top_left":
                    x, y = margin, margin
                elif position == "top_center":
                    x, y = (img_width - wm_width) // 2, margin
                elif position == "top_right":
                    x, y = img_width - wm_width - margin, margin
                elif position == "middle_left":
                    x, y = margin, (img_height - wm_height) // 2
                elif position == "center":
                    x, y = (img_width - wm_width) // 2, (img_height - wm_height) // 2
                elif position == "middle_right":
                    x, y = img_width - wm_width - margin, (img_height - wm_height) // 2
                elif position == "bottom_left":
                    x, y = margin, img_height - wm_height - margin
                elif position == "bottom_center":
                    x, y = (img_width - wm_width) // 2, img_height - wm_height - margin
                else:  # bottom_right
                    x, y = img_width - wm_width - margin, img_height - wm_height - margin
                
                # 粘贴水印图片
                txt_layer.paste(watermark_img, (x, y), watermark_img)
                
                # 合并图层
                preview_img = Image.alpha_composite(img, txt_layer)
            
            # 调整预览图片大小
            preview_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # 转换为base64
            buffer = io.BytesIO()
            # 转换为RGB以保存为PNG
            if preview_img.mode == 'RGBA':
                # 创建白色背景
                background = Image.new('RGB', preview_img.size, (255, 255, 255))
                background.paste(preview_img, mask=preview_img.split()[3])
                background.save(buffer, format='PNG')
            else:
                preview_img.save(buffer, format='PNG')
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # 显示预览
            self.preview_image.src = img_base64
            self.preview_image.visible = True
            self._page.update()
            
            self._show_message("预览生成成功", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"预览失败: {str(ex)}", ft.Colors.ERROR)
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """处理按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        watermark_type = self.watermark_type_radio.value
        
        # 检查水印内容
        if watermark_type == "text":
            watermark_text = self.watermark_text_field.value.strip()
            if not watermark_text:
                self._show_message("请输入水印文字", ft.Colors.ERROR)
                return
        else:
            if not self.watermark_image_path or not self.watermark_image_path.exists():
                self._show_message("请选择水印图片", ft.Colors.ERROR)
                return
        
        # 显示进度
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.progress_text.value = "准备处理..."
        self.progress_bar.value = 0
        self._page.update()
        
        try:
            # 获取设置
            opacity = int(self.opacity_slider.value * 255 / 100)
            watermark_mode = self.watermark_mode_radio.value
            margin = int(self.margin_slider.value)
            position = self.position_dropdown.value
            
            # 平铺水印模式的设置（文字水印专用）
            tile_angle = int(self.tile_angle_slider.value)
            tile_spacing_h = int(self.tile_spacing_h_slider.value)
            tile_spacing_v = int(self.tile_spacing_v_slider.value)
            
            success_count = 0
            total = len(self.selected_files)
            
            for idx, file_path in enumerate(self.selected_files):
                if not file_path.exists():
                    continue
                
                # 更新进度
                self.progress_text.value = f"正在添加水印: {file_path.name} ({idx + 1}/{total})"
                self.progress_bar.value = idx / total
                self._page.update()
                
                try:
                    # 读取图片
                    img = Image.open(file_path)
                    
                    # 转换为RGBA模式以支持透明度
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # 获取图片尺寸
                    img_width, img_height = img.size
                    
                    # 创建水印层
                    txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
                    
                    if watermark_type == "text":
                        # 文字水印处理
                        watermark_text = self.watermark_text_field.value.strip()
                        text_color = self.current_color
                        
                        # 计算字体大小（根据模式：固定或自适应）
                        font_size = self._calculate_font_size(img_width)
                        
                        draw = ImageDraw.Draw(txt_layer)
                        
                        # 加载选择的字体
                        font = self._get_font(font_size)
                        
                        # 获取文字大小
                        bbox = draw.textbbox((0, 0), watermark_text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        
                        text_color_with_alpha = text_color + (opacity,)
                        
                        if watermark_mode == "single":
                            # 单个水印模式
                            if position == "top_left":
                                x, y = margin, margin
                            elif position == "top_center":
                                x, y = (img_width - text_width) // 2, margin
                            elif position == "top_right":
                                x, y = img_width - text_width - margin, margin
                            elif position == "middle_left":
                                x, y = margin, (img_height - text_height) // 2
                            elif position == "center":
                                x, y = (img_width - text_width) // 2, (img_height - text_height) // 2
                            elif position == "middle_right":
                                x, y = img_width - text_width - margin, (img_height - text_height) // 2
                            elif position == "bottom_left":
                                x, y = margin, img_height - text_height - margin
                            elif position == "bottom_center":
                                x, y = (img_width - text_width) // 2, img_height - text_height - margin
                            else:  # bottom_right
                                x, y = img_width - text_width - margin, img_height - text_height - margin
                            
                            # 绘制单个文字
                            draw.text((x, y), watermark_text, font=font, fill=text_color_with_alpha)
                        
                        else:
                            # 平铺水印模式
                            # 创建一个临时图层用于旋转文字
                            temp_layer = Image.new('RGBA', (text_width + 50, text_height + 50), (255, 255, 255, 0))
                            temp_draw = ImageDraw.Draw(temp_layer)
                            temp_draw.text((25, 25), watermark_text, font=font, fill=text_color_with_alpha)
                            
                            # 旋转文字
                            if tile_angle != 0:
                                temp_layer = temp_layer.rotate(tile_angle, expand=True)
                            
                            rotated_width, rotated_height = temp_layer.size
                            
                            # 计算需要平铺的行列数
                            cols = (img_width // tile_spacing_h) + 2
                            rows = (img_height // tile_spacing_v) + 2
                            
                            # 平铺水印
                            for row in range(rows):
                                for col in range(cols):
                                    x = col * tile_spacing_h - rotated_width // 2
                                    y = row * tile_spacing_v - rotated_height // 2
                                    
                                    # 确保在图片范围内
                                    if x + rotated_width > 0 and x < img_width and y + rotated_height > 0 and y < img_height:
                                        txt_layer.paste(temp_layer, (x, y), temp_layer)
                    
                    else:
                        # 图片水印处理
                        watermark_img = Image.open(self.watermark_image_path)
                        
                        # 转换为RGBA模式
                        if watermark_img.mode != 'RGBA':
                            watermark_img = watermark_img.convert('RGBA')
                        
                        # 调整图片水印大小
                        size_mode = self.image_size_mode_radio.value
                        if size_mode == "scale":
                            # 按比例缩放
                            scale_percent = int(self.image_scale_slider.value) / 100.0
                            new_width = int(watermark_img.width * scale_percent)
                            new_height = int(watermark_img.height * scale_percent)
                            watermark_img = watermark_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        elif size_mode == "fixed":
                            # 固定宽度，高度按比例
                            try:
                                width = int(self.image_width_field.value)
                                ratio = width / watermark_img.width
                                height = int(watermark_img.height * ratio)
                                watermark_img = watermark_img.resize((width, height), Image.Resampling.LANCZOS)
                            except (ValueError, TypeError):
                                pass  # 保持原始大小
                        # original 模式不做处理
                        
                        # 调整透明度
                        if opacity < 255:
                            alpha = watermark_img.split()[3]
                            alpha = Image.eval(alpha, lambda a: int(a * opacity / 255))
                            watermark_img.putalpha(alpha)
                        
                        # 只支持单个水印模式（图片水印不支持平铺）
                        wm_width, wm_height = watermark_img.size
                        
                        if position == "top_left":
                            x, y = margin, margin
                        elif position == "top_center":
                            x, y = (img_width - wm_width) // 2, margin
                        elif position == "top_right":
                            x, y = img_width - wm_width - margin, margin
                        elif position == "middle_left":
                            x, y = margin, (img_height - wm_height) // 2
                        elif position == "center":
                            x, y = (img_width - wm_width) // 2, (img_height - wm_height) // 2
                        elif position == "middle_right":
                            x, y = img_width - wm_width - margin, (img_height - wm_height) // 2
                        elif position == "bottom_left":
                            x, y = margin, img_height - wm_height - margin
                        elif position == "bottom_center":
                            x, y = (img_width - wm_width) // 2, img_height - wm_height - margin
                        else:  # bottom_right
                            x, y = img_width - wm_width - margin, img_height - wm_height - margin
                        
                        # 粘贴水印图片
                        txt_layer.paste(watermark_img, (x, y), watermark_img)
                    
                    # 合并图层
                    watermarked = Image.alpha_composite(img, txt_layer)
                    
                    # 确定输出路径和格式
                    output_mode = self.output_mode_radio.value
                    
                    # 确定输出格式和扩展名
                    if self.output_format_dropdown.value == "same":
                        output_format = file_path.suffix[1:].upper()
                        ext = file_path.suffix
                    else:
                        output_format = self.output_format_dropdown.value.upper()
                        ext = f".{self.output_format_dropdown.value}"
                    
                    if output_mode == "overwrite":
                        output_path = file_path
                        output_format = file_path.suffix[1:].upper()
                    elif output_mode == "custom":
                        output_dir = Path(self.custom_output_dir.value)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = output_dir / f"{file_path.stem}{ext}"
                    else:  # same
                        # 生成新文件名
                        output_path = file_path.parent / f"{file_path.stem}_watermark{ext}"
                    
                    # 根据全局设置决定是否添加序号（覆盖模式除外）
                    if output_mode != "overwrite":
                        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                        output_path = get_unique_path(output_path, add_sequence=add_sequence)
                    
                    # 处理JPEG格式
                    if output_format == "JPEG" or output_format == "JPG":
                        watermarked = watermarked.convert('RGB')
                        output_format = "JPEG"
                    
                    # 保存
                    watermarked.save(output_path, format=output_format)
                    success_count += 1
                
                except Exception as ex:
                    continue
            
            # 完成进度显示
            self.progress_text.value = "处理完成！"
            self.progress_bar.value = 1.0
            self._page.update()
            
            # 延迟隐藏进度条，让用户看到完成状态
            import time
            time.sleep(0.5)
            
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self._page.update()
            
            self._show_message(f"处理完成！成功处理 {success_count}/{total} 个文件", ft.Colors.GREEN)
        
        except Exception as ex:
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self._page.update()
            self._show_message(f"处理失败: {str(ex)}", ft.Colors.ERROR)
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。"""
        added_count = 0
        skipped_count = 0
        
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                skipped_count += 1
                continue
            if path not in self.selected_files:
                self.selected_files.append(path)
                added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            self._show_message(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_message("添加水印工具不支持该格式", ft.Colors.ORANGE)
        
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
