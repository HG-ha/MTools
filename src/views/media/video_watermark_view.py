# -*- coding: utf-8 -*-
"""视频添加水印视图模块。

提供视频添加水印功能。
"""

import asyncio
from pathlib import Path
from typing import Callable, List, Optional
import threading

import flet as ft

from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, FFmpegService
from utils import logger, get_unique_path

class VideoWatermarkView(ft.Container):
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    """视频添加水印视图类。
    
    提供视频添加水印功能，包括：
    - 文字水印和图片水印
    - 9个位置选择
    - 自定义字体、颜色、透明度
    - 批量处理（支持增量选择、文件夹选择）
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频添加水印视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        self.expand: bool = True
        
        self.selected_files: List[Path] = []
        self.is_processing: bool = False
        
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
                ft.Text("视频添加水印", size=28, weight=ft.FontWeight.BOLD),
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
                            ft.Text("选择视频文件", size=16, weight=ft.FontWeight.BOLD),
                            ft.Button(
                                content="选择文件",
                                icon=ft.Icons.FILE_UPLOAD,
                                on_click=lambda _: self._page.run_task(self._on_select_files),
                            ),
                            ft.Button(
                                content="选择文件夹",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda _: self._page.run_task(self._on_select_folder),
                            ),
                            ft.TextButton(
                                content="清空列表",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=self._on_clear_files,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: MP4, AVI, MKV, MOV, WMV 等 | 支持批量处理",
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
                        height=200,
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
        
        # 水印类型选择
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
        
        # 文字水印设置
        self.watermark_text_field = ft.TextField(
            label="水印文字",
            hint_text="输入水印文本",
            value="",
        )
        
        self.font_size_slider = ft.Slider(
            min=10,
            max=100,
            divisions=18,
            value=24,
            label="{value}",
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
            on_click=lambda _: self._page.run_task(self._on_select_font_file),
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
        
        # 颜色选择
        self.current_color = "white"
        self.color_dropdown = ft.Dropdown(
            label="文字颜色",
            width=200,
            options=[
                ft.dropdown.Option("white", "白色"),
                ft.dropdown.Option("black", "黑色"),
                ft.dropdown.Option("red", "红色"),
                ft.dropdown.Option("green", "绿色"),
                ft.dropdown.Option("blue", "蓝色"),
                ft.dropdown.Option("yellow", "黄色"),
            ],
            value="white",
        )
        
        self.text_watermark_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.watermark_text_field,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("字体", size=12),
                    self.font_dropdown,
                    self.custom_font_container,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("字体大小", size=12),
                    self.font_size_slider,
                    self.color_dropdown,
                ],
                spacing=PADDING_SMALL,
            ),
            visible=True,
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
                                on_click=lambda _: self._page.run_task(self._on_select_watermark_image),
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
        
        # 位置选择
        self.position_dropdown = ft.Dropdown(
            label="水印位置",
            width=200,
            options=[
                ft.dropdown.Option("top_left", "左上角"),
                ft.dropdown.Option("top_right", "右上角"),
                ft.dropdown.Option("bottom_left", "左下角"),
                ft.dropdown.Option("bottom_right", "右下角"),
                ft.dropdown.Option("center", "正中央"),
            ],
            value="bottom_right",
        )
        
        # 透明度设置
        self.opacity_slider = ft.Slider(
            min=0,
            max=100,
            divisions=20,
            value=50,
            label="{value}%",
        )
        
        # 边距设置
        self.margin_slider = ft.Slider(
            min=10,
            max=100,
            divisions=18,
            value=20,
            label="{value}px",
        )
        
        watermark_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("水印设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("水印类型", size=12),
                    self.watermark_type_radio,
                    ft.Container(height=PADDING_SMALL),
                    self.text_watermark_container,
                    self.image_watermark_container,
                    ft.Container(height=PADDING_SMALL),
                    self.position_dropdown,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("不透明度", size=12),
                    self.opacity_slider,
                    ft.Text("边距", size=12),
                    self.margin_slider,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 输出设置
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.file_suffix = ft.TextField(
            label="文件后缀",
            value="_watermark",
            disabled=False,
            width=200,
        )
        
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            width=200,
            options=[
                ft.dropdown.Option("same", "保持原格式"),
                ft.dropdown.Option("mp4", "MP4"),
                ft.dropdown.Option("avi", "AVI"),
                ft.dropdown.Option("mkv", "MKV"),
            ],
            value="same",
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: self._page.run_task(self._on_browse_output),
            disabled=True,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.output_mode_radio,
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            self.file_suffix,
                            self.output_format_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_SMALL,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 底部按钮 - 大号主按钮
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
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            ),
            alignment=ft.Alignment.CENTER,
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
                self.progress_bar,
                self.progress_text,
                self.process_button,
                ft.Container(height=PADDING_LARGE),
            ],
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
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
    
    def _init_empty_file_list(self) -> None:
        """初始化空文件列表状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_FILE, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处或选择按钮添加视频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                height=200,
                alignment=ft.Alignment.CENTER,
                on_click=lambda _: self._page.run_task(self._on_select_files),
                ink=True,
                tooltip="点击选择视频文件",
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
    
    async def _on_select_font_file(self) -> None:
        """选择字体文件按钮点击事件。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择字体文件",
            allowed_extensions=["ttf", "ttc", "otf", "TTF", "TTC", "OTF"],
            allow_multiple=False,
        )
        if files and len(files) > 0:
            self.custom_font_path = Path(files[0].path)
            self.custom_font_text.value = self.custom_font_path.name
            self.custom_font_text.update()
    
    def _get_font_path(self) -> Optional[str]:
        """获取选择的字体文件路径。
        
        Returns:
            字体文件路径（必须返回支持中文的字体）
        """
        font_choice = self.font_dropdown.value
        
        # 如果选择自定义字体
        if font_choice == "custom":
            if self.custom_font_path and self.custom_font_path.exists():
                return str(self.custom_font_path)
            else:
                # 没有选择自定义字体文件，降级到微软雅黑
                font_choice = "msyh"
        
        # 如果选择系统默认，使用微软雅黑（确保支持中文）
        if font_choice == "system":
            font_choice = "msyh"
        
        # 字体文件映射（Windows路径）
        import platform
        system = platform.system()
        
        if system == "Windows":
            fonts_dir = Path("C:/Windows/Fonts")
            font_map = {
                "msyh": ["msyh.ttc", "msyh.ttf", "msyhbd.ttc"],
                "simsun": ["simsun.ttc", "simsun.ttf"],
                "simhei": ["simhei.ttf"],
                "kaiti": ["simkai.ttf", "kaiti.ttf"],
                "arial": ["arial.ttf"],
                "times": ["times.ttf", "Times.ttf"],
                "courier": ["cour.ttf", "Courier.ttf"],
            }
            # 用于回退的中文字体列表
            fallback_fonts = [
                "msyh.ttc", "msyh.ttf", "msyhbd.ttc",  # 微软雅黑
                "simsun.ttc", "simsun.ttf",  # 宋体
                "simhei.ttf",  # 黑体
                "simkai.ttf",  # 楷体
            ]
        else:
            # macOS / Linux
            fonts_dir = Path("/usr/share/fonts") if system == "Linux" else Path("/System/Library/Fonts")
            font_map = {
                "msyh": ["Microsoft YaHei.ttf", "msyh.ttf"],
                "simsun": ["SimSun.ttf", "simsun.ttf"],
                "simhei": ["SimHei.ttf", "simhei.ttf"],
                "kaiti": ["Kaiti.ttf", "kaiti.ttf"],
                "arial": ["Arial.ttf", "arial.ttf"],
                "times": ["Times New Roman.ttf", "times.ttf"],
                "courier": ["Courier New.ttf", "cour.ttf"],
            }
            fallback_fonts = []
        
        # 尝试找到选择的字体文件
        if font_choice in font_map:
            for font_file in font_map[font_choice]:
                font_path = fonts_dir / font_file
                if font_path.exists():
                    logger.info(f"使用字体: {font_path}")
                    return str(font_path)
        
        # 如果选择的字体找不到，尝试回退到任意中文字体
        for font_file in fallback_fonts:
            font_path = fonts_dir / font_file
            if font_path.exists():
                logger.info(f"回退使用字体: {font_path}")
                return str(font_path)
        
        # 最后的回退：返回 None（可能会乱码）
        logger.warning("未找到支持中文的字体文件")
        return None
    
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
    
    async def _on_select_watermark_image(self) -> None:
        """选择水印图片按钮点击事件。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择水印图片",
            allowed_extensions=["png", "jpg", "jpeg", "gif", "PNG", "JPG", "JPEG", "GIF"],
            allow_multiple=False,
        )
        if files and len(files) > 0:
            self.watermark_image_path = Path(files[0].path)
            self.watermark_image_text.value = self.watermark_image_path.name
            self.watermark_image_text.update()
    
    async def _on_select_files(self) -> None:
        """选择文件按钮点击事件。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择视频",
            allowed_extensions=["mp4", "avi", "mkv", "mov", "wmv", "flv", "MP4", "AVI", "MKV", "MOV", "WMV", "FLV"],
            allow_multiple=True,
        )
        if files and len(files) > 0:
            new_files = [Path(f.path) for f in files]
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            self._update_file_list()
    
    async def _on_select_folder(self) -> None:
        """选择文件夹按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择视频文件夹")
        if folder_path:
            folder = Path(folder_path)
            extensions = [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"]
            for ext in extensions:
                for file_path in folder.glob(f"*{ext}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                for file_path in folder.glob(f"*{ext.upper()}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。"""
        mode = e.control.value
        self.file_suffix.disabled = mode != "new"
        self.custom_output_dir.disabled = mode != "custom"
        self.browse_output_button.disabled = mode != "custom"
        self._page.update()
    
    async def _on_browse_output(self) -> None:
        """浏览输出目录按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            self.custom_output_dir.update()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self._init_empty_file_list()
        else:
            for idx, file_path in enumerate(self.selected_files):
                try:
                    file_size = file_path.stat().st_size
                    size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB"
                except Exception:
                    size_str = "未知"
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
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
                                ft.Icon(ft.Icons.VIDEO_FILE, size=18, color=ft.Colors.PRIMARY),
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
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _build_ffmpeg_filter(self) -> str:
        """构建FFmpeg滤镜字符串。
        
        Returns:
            滤镜字符串
        """
        watermark_type = self.watermark_type_radio.value
        position = self.position_dropdown.value
        margin = int(self.margin_slider.value)
        opacity = self.opacity_slider.value / 100.0
        
        # 位置映射
        position_map = {
            "top_left": f"{margin}:{margin}",
            "top_right": f"W-w-{margin}:{margin}",
            "bottom_left": f"{margin}:H-h-{margin}",
            "bottom_right": f"W-w-{margin}:H-h-{margin}",
            "center": "(W-w)/2:(H-h)/2",
        }
        
        if watermark_type == "text":
            # 文字水印
            text = self.watermark_text_field.value.strip()
            if not text:
                raise Exception("请输入水印文字")
            
            font_size = int(self.font_size_slider.value)
            color = self.color_dropdown.value
            
            # 转义特殊字符
            text = text.replace(":", "\\:").replace("'", "\\'")
            
            # 构建drawtext滤镜
            x_pos, y_pos = position_map[position].split(':')
            filter_str = f"drawtext=text='{text}':fontsize={font_size}:fontcolor={color}@{opacity}:x={x_pos}:y={y_pos}"
            
            return filter_str
        else:
            # 图片水印
            if not self.watermark_image_path or not self.watermark_image_path.exists():
                raise Exception("请选择水印图片")
            
            # 构建overlay滤镜（使用filter_complex）
            # 返回None表示需要使用filter_complex
            return None
    
    def _process_single_video(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable] = None
    ) -> tuple[bool, str]:
        """处理单个视频文件。
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            progress_callback: 进度回调函数
            
        Returns:
            (是否成功, 消息)
        """
        import ffmpeg
        
        ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
        if not ffmpeg_path:
            return False, "未找到 FFmpeg"
        
        ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
        if not ffprobe_path:
            return False, "未找到 FFprobe"
        
        # 用于存储临时文件路径，以便在 finally 中清理
        temp_text_path = None
        
        try:
            # 先检测输入视频是否有音频流
            probe = ffmpeg.probe(str(input_path), cmd=ffprobe_path)
            has_audio = any(stream['codec_type'] == 'audio' for stream in probe['streams'])
            
            watermark_type = self.watermark_type_radio.value
            position = self.position_dropdown.value
            margin = int(self.margin_slider.value)
            opacity = self.opacity_slider.value / 100.0
            
            # 构建输入
            stream = ffmpeg.input(str(input_path))
            
            if watermark_type == "text":
                # 文字水印 - 使用 subprocess 直接调用 FFmpeg 解决中文编码问题
                import subprocess
                import tempfile
                import os
                
                text = self.watermark_text_field.value.strip()
                if not text:
                    return False, "请输入水印文字"
                
                font_size = int(self.font_size_slider.value)
                color = self.color_dropdown.value
                
                # 获取字体路径
                font_path = self._get_font_path()
                
                # 为 drawtext 构建位置表达式
                text_position_map = {
                    "top_left": (str(margin), str(margin)),
                    "top_right": (f"w-tw-{margin}", str(margin)),
                    "bottom_left": (str(margin), f"h-th-{margin}"),
                    "bottom_right": (f"w-tw-{margin}", f"h-th-{margin}"),
                    "center": ("(w-tw)/2", "(h-th)/2"),
                }
                x_pos, y_pos = text_position_map[position]
                
                # 创建临时文件存储水印文本（UTF-8 编码，不带 BOM）
                temp_text_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    suffix='.txt',
                    delete=False
                )
                temp_text_file.write(text)
                temp_text_file.close()
                temp_text_path = temp_text_file.name
                
                # 构建 drawtext 滤镜字符串
                # 使用 Windows 原生路径格式
                filter_parts = [f"fontsize={font_size}"]
                filter_parts.append(f"fontcolor={color}@{opacity}")
                filter_parts.append(f"x={x_pos}")
                filter_parts.append(f"y={y_pos}")
                
                # textfile 使用 Windows 原生路径（反斜杠需要双重转义）
                escaped_text_path = temp_text_path.replace("\\", "\\\\").replace(":", "\\:")
                filter_parts.append(f"textfile='{escaped_text_path}'")
                
                if font_path:
                    # fontfile 也需要转义
                    escaped_font_path = font_path.replace("\\", "\\\\").replace(":", "\\:")
                    filter_parts.append(f"fontfile='{escaped_font_path}'")
                    logger.info(f"FFmpeg 字体路径: {escaped_font_path}")
                else:
                    logger.warning("未指定字体路径，可能导致中文乱码")
                
                drawtext_filter = "drawtext=" + ":".join(filter_parts)
                
                # 检测GPU编码器
                gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
                
                # 构建 FFmpeg 命令
                cmd = [ffmpeg_path, '-y', '-i', str(input_path)]
                cmd.extend(['-vf', drawtext_filter])
                
                # 添加编码器参数
                if gpu_encoder:
                    cmd.extend(['-c:v', gpu_encoder])
                    if gpu_encoder.startswith("h264_nvenc") or gpu_encoder.startswith("hevc_nvenc"):
                        cmd.extend(['-preset', 'p4', '-cq', '23'])
                    elif gpu_encoder.startswith("h264_amf") or gpu_encoder.startswith("hevc_amf"):
                        cmd.extend(['-quality', 'balanced', '-rc', 'vbr_peak'])
                    elif gpu_encoder.startswith("h264_qsv") or gpu_encoder.startswith("hevc_qsv"):
                        cmd.extend(['-preset', 'medium', '-global_quality', '23'])
                else:
                    cmd.extend(['-c:v', 'libx264', '-crf', '23', '-preset', 'medium'])
                
                # 音频处理
                if has_audio:
                    cmd.extend(['-c:a', 'copy'])
                
                cmd.append(str(output_path))
                
                logger.info(f"FFmpeg 命令: {' '.join(cmd)}")
                
                # 使用 subprocess 执行 FFmpeg
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,  # 使用 bytes 模式
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                
                # 清理临时文件
                try:
                    os.unlink(temp_text_path)
                    temp_text_path = None  # 标记已清理
                except Exception:
                    pass
                
                if result.returncode != 0:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')
                    logger.error(f"FFmpeg错误: {error_msg}")
                    return False, f"FFmpeg错误: {error_msg}"
                
                return True, "处理成功"
                
            else:
                # 图片水印 - 使用 overlay 滤镜
                if not self.watermark_image_path or not self.watermark_image_path.exists():
                    return False, "请选择水印图片"
                
                # 检查是否是 GIF 文件
                is_gif = self.watermark_image_path.suffix.lower() == '.gif'
                
                # 读取水印图片 - GIF需要设置loop参数来无限循环
                if is_gif:
                    watermark = ffmpeg.input(str(self.watermark_image_path), stream_loop=-1, ignore_loop=0)
                else:
                    watermark = ffmpeg.input(str(self.watermark_image_path))
                
                # 调整图片大小
                size_mode = self.image_size_mode_radio.value
                if size_mode == "scale":
                    # 按比例缩放
                    scale_percent = int(self.image_scale_slider.value) / 100.0
                    watermark = ffmpeg.filter(watermark, 'scale', f"iw*{scale_percent}", f"ih*{scale_percent}")
                elif size_mode == "fixed":
                    # 固定宽度，高度按比例
                    try:
                        width = int(self.image_width_field.value)
                        watermark = ffmpeg.filter(watermark, 'scale', width, -1)
                    except (ValueError, TypeError):
                        return False, "请输入有效的宽度值"
                # original 模式不做处理
                
                # 如果需要调整透明度
                if opacity < 1.0:
                    watermark = ffmpeg.filter(watermark, 'format', 'rgba')
                    watermark = ffmpeg.filter(watermark, 'colorchannelmixer', aa=opacity)
                
                # 为 overlay 构建位置表达式 (使用 main_w, main_h, overlay_w, overlay_h)
                overlay_position_map = {
                    "top_left": (margin, margin),
                    "top_right": (f"main_w-overlay_w-{margin}", margin),
                    "bottom_left": (margin, f"main_h-overlay_h-{margin}"),
                    "bottom_right": (f"main_w-overlay_w-{margin}", f"main_h-overlay_h-{margin}"),
                    "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
                }
                x_pos, y_pos = overlay_position_map[position]
                
                # 应用 overlay 滤镜
                if is_gif:
                    # GIF 需要使用 shortest=1 确保输出时长与主视频一致
                    stream = ffmpeg.overlay(
                        stream, 
                        watermark, 
                        x=str(x_pos), 
                        y=str(y_pos),
                        shortest=1
                    )
                else:
                    # 静态图片
                    stream = ffmpeg.overlay(stream, watermark, x=str(x_pos), y=str(y_pos))
                
                # 检测GPU编码器
                gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
                
                output_params = {
                    'acodec': 'copy',  # 复制音频流（重要！保留原视频音频）
                }
                
                # 设置视频编码器
                if gpu_encoder:
                    output_params['vcodec'] = gpu_encoder
                    # 根据编码器类型设置参数
                    if gpu_encoder.startswith("h264_nvenc") or gpu_encoder.startswith("hevc_nvenc"):
                        output_params['preset'] = 'p4'
                        output_params['cq'] = 23
                    elif gpu_encoder.startswith("h264_amf") or gpu_encoder.startswith("hevc_amf"):
                        output_params['quality'] = 'balanced'
                        output_params['rc'] = 'vbr_peak'
                    elif gpu_encoder.startswith("h264_qsv") or gpu_encoder.startswith("hevc_qsv"):
                        output_params['preset'] = 'medium'
                        output_params['global_quality'] = 23
                else:
                    # 使用CPU编码器
                    output_params['vcodec'] = 'libx264'
                    output_params['crf'] = 23
                    output_params['preset'] = 'medium'
                
                # 根据是否有音频流决定输出方式
                video_stream = stream
                if has_audio:
                    # 有音频流：overlay 只处理视频流，音频流需要单独映射
                    audio_stream = ffmpeg.input(str(input_path)).audio
                    stream = ffmpeg.output(video_stream, audio_stream, str(output_path), **output_params)
                else:
                    # 无音频流：只输出视频
                    stream = ffmpeg.output(video_stream, str(output_path), **output_params)
            
            # 运行转换
            ffmpeg.run(
                stream,
                cmd=ffmpeg_path,
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True
            )
            
            return True, "处理成功"
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
            logger.error(f"FFmpeg错误: {error_msg}")
            return False, f"FFmpeg错误: {error_msg}"
        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            return False, str(e)
        finally:
            # 清理临时文件
            if temp_text_path:
                try:
                    import os
                    os.unlink(temp_text_path)
                except Exception:
                    pass
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """处理按钮点击事件。"""
        if self.is_processing:
            self._show_message("正在处理中，请稍候", ft.Colors.WARNING)
            return
        
        if not self.selected_files:
            self._show_message("请先选择视频文件", ft.Colors.ERROR)
            return
        
        # 验证水印设置
        watermark_type = self.watermark_type_radio.value
        if watermark_type == "text":
            if not self.watermark_text_field.value.strip():
                self._show_message("请输入水印文字", ft.Colors.ERROR)
                return
        else:
            if not self.watermark_image_path or not self.watermark_image_path.exists():
                self._show_message("请选择水印图片", ft.Colors.ERROR)
                return
        
        # 异步处理
        self._page.run_task(self._process_videos_async)
    
    async def _process_videos_async(self) -> None:
        """处理视频（异步）。"""
        self.is_processing = True
        
        # 显示进度
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.process_button.disabled = True
        self._page.update()
        
        try:
            success_count = 0
            total = len(self.selected_files)
            output_mode = self.output_mode_radio.value
            
            for idx, file_path in enumerate(self.selected_files):
                if not file_path.exists():
                    continue
                
                # 更新进度
                self.progress_text.value = f"正在添加水印: {file_path.name} ({idx + 1}/{total})"
                self.progress_bar.value = idx / total
                self._page.update()
                
                try:
                    # 确定输出格式
                    output_format = self.output_format_dropdown.value
                    
                    if output_mode == "new":
                        # 保存为新文件
                        suffix = self.file_suffix.value or "_watermark"
                        if output_format == "same":
                            ext = file_path.suffix
                        else:
                            ext = f".{output_format}"
                        output_path = file_path.parent / f"{file_path.stem}{suffix}{ext}"
                    else:
                        # 自定义输出目录
                        output_dir = Path(self.custom_output_dir.value)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        if output_format == "same":
                            output_path = output_dir / file_path.name
                        else:
                            output_path = output_dir / f"{file_path.stem}.{output_format}"
                    
                    # 根据全局设置决定是否添加序号
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)
                    
                    # 处理视频（在线程中执行CPU/IO密集操作）
                    success, message = await asyncio.to_thread(
                        self._process_single_video, file_path, output_path
                    )
                    
                    if success:
                        success_count += 1
                    else:
                        logger.error(f"处理文件 {file_path.name} 失败: {message}")
                
                except Exception as ex:
                    logger.error(f"处理文件 {file_path.name} 失败: {str(ex)}")
                    continue
            
            # 完成
            self.progress_text.value = "处理完成！"
            self.progress_bar.value = 1.0
            self._page.update()
            
            await asyncio.sleep(0.5)
            
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.process_button.disabled = False
            self._page.update()
            
            self._show_message(f"处理完成！成功处理 {success_count}/{total} 个文件", ft.Colors.GREEN)
        
        except Exception as ex:
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.process_button.disabled = False
            self._page.update()
            self._show_message(f"处理失败: {str(ex)}", ft.Colors.ERROR)
        
        finally:
            self.is_processing = False
    
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
        self._page.open(snackbar)
    
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
            self._show_message("视频水印不支持该格式", ft.Colors.ORANGE)
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