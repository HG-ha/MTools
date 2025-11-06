# -*- coding: utf-8 -*-
"""图片添加水印视图模块。

提供图片添加水印功能。
"""

import base64
import io
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft
from PIL import Image, ImageDraw, ImageFont

from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService, ImageService


class ImageWatermarkView(ft.Container):
    """图片添加水印视图类。
    
    提供图片添加水印功能，包括：
    - 单个水印：9个位置选择
    - 全屏平铺水印：斜向平铺，防盗图效果
    - 自定义颜色、透明度、字体大小
    - 平铺模式支持自定义角度和间距
    - 批量处理（支持增量选择、文件夹选择）
    - 实时预览效果（批量时使用第一张图片预览）
    - 文件列表管理（单独删除、清空列表）
    """

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
        self.page: ft.Page = page
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
                ft.Text("添加水印", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.AUTO,
        )
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("选择图片文件", size=16, weight=ft.FontWeight.BOLD),
                            ft.ElevatedButton(
                                text="选择文件",
                                icon=ft.Icons.FILE_UPLOAD,
                                on_click=self._on_select_files,
                            ),
                            ft.ElevatedButton(
                                text="选择文件夹",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=self._on_select_folder,
                            ),
                            ft.TextButton(
                                text="清空列表",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=self._on_clear_files,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.file_list_view,
                        height=200,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_MEDIUM,
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
        
        self.font_size_slider = ft.Slider(
            min=10,
            max=200,
            divisions=38,
            value=40,
            label="{value}",
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
        
        color_picker_button = ft.ElevatedButton(
            text="选择颜色",
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
                    self.watermark_text_field,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("水印模式", size=12),
                    self.watermark_mode_radio,
                    ft.Container(height=PADDING_SMALL),
                    self.single_position_container,
                    self.tile_settings_container,
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
                    ft.Text("字体大小", size=12),
                    self.font_size_slider,
                    ft.Text("透明度", size=12),
                    self.opacity_slider,
                    self.margin_container,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
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
        
        self.overwrite_checkbox = ft.Checkbox(
            label="覆盖原文件",
            value=False,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            self.output_format_dropdown,
                            self.overwrite_checkbox,
                        ],
                        spacing=PADDING_MEDIUM,
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
            visible=False,
            fit=ft.ImageFit.CONTAIN,
            width=400,
            height=400,
        )
        
        self.preview_button = ft.OutlinedButton(
            text="预览效果",
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
                        alignment=ft.alignment.center,
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
        process_button = ft.ElevatedButton(
            text="添加水印",
            icon=ft.Icons.BRANDING_WATERMARK,
            on_click=self._on_process,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
            ),
        )
        
        # 进度显示
        self.progress_text = ft.Text(
            "",
            size=14,
            color=TEXT_SECONDARY,
            visible=False,
        )
        
        self.progress_bar = ft.ProgressBar(
            visible=False,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=PADDING_MEDIUM),
                file_section,
                ft.Container(height=PADDING_MEDIUM),
                watermark_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
                ft.Container(height=PADDING_MEDIUM),
                self.preview_section,
                ft.Container(height=PADDING_MEDIUM),
                process_button,
                ft.Container(height=PADDING_SMALL),
                self.progress_text,
                self.progress_bar,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )
        
        self.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE,
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
            self.page.update()
        
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
                                        ft.Text("调整RGB值:", size=12, color=TEXT_SECONDARY),
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
                ft.ElevatedButton("确定", on_click=lambda e: close_dialog(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
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
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=TEXT_SECONDARY),
                        ft.Text("未选择文件", color=TEXT_SECONDARY, size=14),
                        ft.Text("点击按钮选择图片文件或文件夹", color=TEXT_SECONDARY, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                height=152,  # 200 - 2*24(padding)
                alignment=ft.alignment.center,
            )
        )
    
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
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件（增量选择）。"""
        def on_files_picked(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                # 追加新文件，而不是替换
                new_files = [Path(f.path) for f in result.files]
                for new_file in new_files:
                    # 避免重复添加
                    if new_file not in self.selected_files:
                        self.selected_files.append(new_file)
                
                self._update_file_list()
                
                # 显示预览区域
                if self.selected_files:
                    self.preview_section.visible = True
                    self.preview_section.update()
        
        file_picker = ft.FilePicker(on_result=on_files_picked)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "webp"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder = Path(result.path)
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
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择图片文件夹")
    
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
                                        color=TEXT_SECONDARY,
                                    ),
                                    width=30,
                                    alignment=ft.alignment.center,
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
                                            color=TEXT_SECONDARY,
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
    
    def _on_preview(self, e: Optional[ft.ControlEvent]) -> None:
        """预览按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        watermark_text = self.watermark_text_field.value.strip()
        if not watermark_text:
            self._show_message("请输入水印文字", ft.Colors.ERROR)
            return
        
        try:
            # 使用第一个文件生成预览
            preview_file = self.selected_files[0]
            
            if not preview_file.exists():
                self._show_message("文件不存在", ft.Colors.ERROR)
                return
            
            # 使用当前选择的颜色
            text_color = self.current_color
            
            # 获取设置
            font_size = int(self.font_size_slider.value)
            opacity = int(self.opacity_slider.value * 255 / 100)
            watermark_mode = self.watermark_mode_radio.value
            
            # 单个水印模式的设置
            margin = int(self.margin_slider.value)
            position = self.position_dropdown.value
            
            # 平铺水印模式的设置
            tile_angle = int(self.tile_angle_slider.value)
            tile_spacing_h = int(self.tile_spacing_h_slider.value)
            tile_spacing_v = int(self.tile_spacing_v_slider.value)
            
            # 读取图片
            img = Image.open(preview_file)
            
            # 转换为RGBA模式以支持透明度
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 创建文字层
            txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            # 尝试使用系统字体
            try:
                # Windows
                font = ImageFont.truetype("msyh.ttc", font_size)  # 微软雅黑
            except:
                try:
                    # 尝试其他字体
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    # 使用默认字体
                    font = ImageFont.load_default()
            
            # 获取文字大小
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 图片尺寸
            img_width, img_height = img.size
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
            self.preview_image.src_base64 = img_base64
            self.preview_image.visible = True
            self.preview_image.update()
            self.preview_section.update()
            
            self._show_message("预览生成成功", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"预览失败: {str(ex)}", ft.Colors.ERROR)
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """处理按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        watermark_text = self.watermark_text_field.value.strip()
        if not watermark_text:
            self._show_message("请输入水印文字", ft.Colors.ERROR)
            return
        
        # 显示进度
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.progress_text.value = "准备处理..."
        self.progress_bar.value = 0
        self.page.update()
        
        try:
            # 使用当前选择的颜色
            text_color = self.current_color
            
            # 获取设置
            font_size = int(self.font_size_slider.value)
            opacity = int(self.opacity_slider.value * 255 / 100)
            watermark_mode = self.watermark_mode_radio.value
            
            # 单个水印模式的设置
            margin = int(self.margin_slider.value)
            position = self.position_dropdown.value
            
            # 平铺水印模式的设置
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
                self.page.update()
                
                try:
                    # 读取图片
                    img = Image.open(file_path)
                    
                    # 转换为RGBA模式以支持透明度
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # 创建文字层
                    txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
                    draw = ImageDraw.Draw(txt_layer)
                    
                    # 尝试使用系统字体
                    try:
                        # Windows
                        font = ImageFont.truetype("msyh.ttc", font_size)  # 微软雅黑
                    except:
                        try:
                            # 尝试其他字体
                            font = ImageFont.truetype("arial.ttf", font_size)
                        except:
                            # 使用默认字体
                            font = ImageFont.load_default()
                    
                    # 获取文字大小
                    bbox = draw.textbbox((0, 0), watermark_text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # 图片尺寸
                    img_width, img_height = img.size
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
                    watermarked = Image.alpha_composite(img, txt_layer)
                    
                    # 确定输出路径和格式
                    if self.overwrite_checkbox.value:
                        output_path = file_path
                        output_format = file_path.suffix[1:].upper()
                    else:
                        # 确定输出格式
                        if self.output_format_dropdown.value == "same":
                            output_format = file_path.suffix[1:].upper()
                            ext = file_path.suffix
                        else:
                            output_format = self.output_format_dropdown.value.upper()
                            ext = f".{self.output_format_dropdown.value}"
                        
                        # 生成新文件名
                        output_path = file_path.parent / f"{file_path.stem}_watermark{ext}"
                        counter = 1
                        while output_path.exists():
                            output_path = file_path.parent / f"{file_path.stem}_watermark_{counter}{ext}"
                            counter += 1
                    
                    # 处理JPEG格式
                    if output_format == "JPEG" or output_format == "JPG":
                        watermarked = watermarked.convert('RGB')
                        output_format = "JPEG"
                    
                    # 保存
                    watermarked.save(output_path, format=output_format)
                    success_count += 1
                
                except Exception as ex:
                    print(f"处理文件 {file_path.name} 失败: {str(ex)}")
                    continue
            
            # 完成进度显示
            self.progress_text.value = "处理完成！"
            self.progress_bar.value = 1.0
            self.page.update()
            
            # 延迟隐藏进度条，让用户看到完成状态
            import time
            time.sleep(0.5)
            
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.page.update()
            
            self._show_message(f"处理完成！成功处理 {success_count}/{total} 个文件", ft.Colors.GREEN)
        
        except Exception as ex:
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.page.update()
            self._show_message(f"处理失败: {str(ex)}", ft.Colors.ERROR)
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
        )
        self.page.snack_bar.open = True
        self.page.update()

