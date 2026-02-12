# -*- coding: utf-8 -*-
"""图片旋转/翻转视图模块。

提供图片旋转和翻转功能。
"""

from pathlib import Path
from typing import Callable, List, Optional

import flet as ft
from PIL import Image, ImageSequence

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from utils import get_unique_path


class ImageRotateView(ft.Container):
    """图片旋转/翻转视图类。
    
    提供图片旋转和翻转功能，包括：
    - 90°/180°/270°旋转
    - 自定义角度旋转（0-360°）
    - 水平/垂直翻转
    - 自定义填充颜色
    - 支持 GIF 动图（保留动画效果）
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', 
        '.gif', '.tiff', '.tif', '.ico', '.avif', '.heic', '.heif'
    }


    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片旋转/翻转视图。
        
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
        self.current_operation: str = "rotate_90"  # 当前操作
        self.preview_update_pending: bool = False  # 防抖标志
        self.current_fill_color: tuple = (255, 255, 255, 255)  # 当前填充颜色 (R, G, B, A)
        
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
                ft.Text("图片旋转/翻转", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_text = ft.Text(
            "未选择文件",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        select_button = ft.Button(
            content="选择图片",
            icon=ft.Icons.IMAGE_OUTLINED,
            on_click=self._on_select_files,
        )
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("选择图片文件", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            select_button,
                            self.file_list_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # 支持格式说明
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: JPG, PNG, WebP, GIF, BMP, TIFF 等 | GIF动图将保留动画效果",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=8),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 操作选择区域 - 两行显示（3个一行）
        self.operation_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Radio(value="rotate_90", label="顺时针90°"),
                            ft.Radio(value="rotate_180", label="180°"),
                            ft.Radio(value="rotate_270", label="逆时针90°"),
                        ],
                        spacing=PADDING_LARGE,
                    ),
                    ft.Row(
                        controls=[
                            ft.Radio(value="flip_horizontal", label="水平翻转"),
                            ft.Radio(value="flip_vertical", label="垂直翻转"),
                            ft.Radio(value="rotate_custom", label="自定义角度"),
                        ],
                        spacing=PADDING_LARGE,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            value="rotate_90",
            on_change=self._on_operation_change,
        )
        
        # 自定义角度设置（默认隐藏）
        self.custom_angle_slider = ft.Slider(
            min=0,
            max=360,
            divisions=360,
            value=45,
            label="{value}°",
            on_change=self._on_angle_slider_change,
        )
        
        self.custom_angle_field = ft.TextField(
            label="角度",
            hint_text="0-360",
            value="45",
            width=100,
            on_change=self._on_angle_field_change,
        )
        
        # 填充颜色选择
        self.fill_color_preview = ft.Container(
            width=40,
            height=40,
            bgcolor="#ffffff",
            border_radius=8,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        self.fill_color_field = ft.TextField(
            label="RGBA值",
            hint_text="RGB(255,255,255) 不透明度100%",
            value="RGB(255,255,255) 不透明度100%",
            width=200,
            read_only=True,
        )
        
        fill_color_button = ft.Button(
            content="选择颜色",
            icon=ft.Icons.PALETTE,
            on_click=self._open_fill_color_picker,
        )
        
        self.custom_angle_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("旋转角度：", size=14, width=80),
                            ft.Container(content=self.custom_angle_slider, expand=True),
                            self.custom_angle_field,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            ft.Text("填充颜色：", size=14, width=80),
                            self.fill_color_preview,
                            self.fill_color_field,
                            fill_color_button,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,
        )
        
        operation_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("选择操作", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.operation_radio,
                    ft.Container(height=PADDING_SMALL),
                    self.custom_angle_section,
                    ft.Text(
                        "提示：自定义角度旋转时，空白区域将使用填充颜色",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        visible=False,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        self.custom_angle_hint = operation_section.content.controls[-1]
        
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
        
        default_output = self.config_service.get_output_dir() / "rotated_images"
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
        
        # 预览区域 - 左右对比
        self.original_image = ft.Image(
            "",
            visible=False,
            fit=ft.BoxFit.CONTAIN,
            width=350,
            height=350,
        )
        
        self.preview_image = ft.Image(
            "",
            visible=False,
            fit=ft.BoxFit.CONTAIN,
            width=350,
            height=350,
        )
        
        self.preview_status_text = ft.Text(
            "选择图片后将自动显示预览",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        )
        
        preview_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("实时预览", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    # 左右对比区域
                    ft.Row(
                        controls=[
                            # 左侧：原图
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            "原图",
                                            size=14,
                                            weight=ft.FontWeight.W_500,
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        ft.Container(height=PADDING_SMALL),
                                        ft.Container(
                                            content=self.original_image,
                                            alignment=ft.Alignment.CENTER,
                                            border=ft.border.all(1, ft.Colors.OUTLINE),
                                            border_radius=8,
                                            padding=PADDING_MEDIUM,
                                            height=370,
                                        ),
                                    ],
                                    spacing=0,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                expand=True,
                            ),
                            ft.Container(width=PADDING_LARGE),
                            # 右侧：效果图
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            "效果图",
                                            size=14,
                                            weight=ft.FontWeight.W_500,
                                            text_align=ft.TextAlign.CENTER,
                                        ),
                                        ft.Container(height=PADDING_SMALL),
                                        ft.Container(
                                            content=self.preview_image,
                                            alignment=ft.Alignment.CENTER,
                                            border=ft.border.all(1, ft.Colors.OUTLINE),
                                            border_radius=8,
                                            padding=PADDING_MEDIUM,
                                            height=370,
                                        ),
                                    ],
                                    spacing=0,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                expand=True,
                            ),
                        ],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    self.preview_status_text,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        self.preview_section = preview_section
        
        # 处理按钮
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PLAY_ARROW, size=24),
                        ft.Text("开始处理", size=18, weight=ft.FontWeight.W_600),
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
            value=0,
            visible=False,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_section,
                ft.Container(height=PADDING_MEDIUM),
                preview_section,
                ft.Container(height=PADDING_MEDIUM),
                operation_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
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
    
    def _update_fill_color_display(self) -> None:
        """更新填充颜色显示。"""
        self.fill_color_preview.bgcolor = self._rgb_to_hex(self.current_fill_color[0], self.current_fill_color[1], self.current_fill_color[2])
        opacity_percent = int(self.current_fill_color[3] / 255 * 100)
        self.fill_color_field.value = f"RGB({self.current_fill_color[0]},{self.current_fill_color[1]},{self.current_fill_color[2]}) 不透明度{opacity_percent}%"
        self._page.update()
    
    def _open_fill_color_picker(self, e: ft.ControlEvent) -> None:
        """打开填充颜色选择器对话框。"""
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
        
        # RGBA 滑块
        r_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_fill_color[0],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                int(a_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        g_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_fill_color[1],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                int(a_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        b_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_fill_color[2],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                int(a_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        a_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=self.current_fill_color[3],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                int(a_slider.value),
                preview_box,
                rgb_text
            ),
        )
        
        # 预览框
        preview_box = ft.Container(
            width=100,
            height=100,
            bgcolor=self._rgb_to_hex(self.current_fill_color[0], self.current_fill_color[1], self.current_fill_color[2]),
            border_radius=12,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        opacity_percent = int(self.current_fill_color[3] / 255 * 100)
        rgb_text = ft.Text(
            f"RGBA({self.current_fill_color[0]}, {self.current_fill_color[1]}, {self.current_fill_color[2]}, {self.current_fill_color[3]})\n不透明度: {opacity_percent}%",
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
                                on_click=lambda e, c=color: self._apply_preset_fill_color(
                                    c, r_slider, g_slider, b_slider, a_slider, preview_box, rgb_text
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
                # 应用选择的颜色（包含透明度）
                self.current_fill_color = (
                    int(r_slider.value),
                    int(g_slider.value),
                    int(b_slider.value),
                    int(a_slider.value),
                )
                self._update_fill_color_display()
                # 更新预览
                self._update_preview()
            self._page.close(dialog)
        
        # 创建对话框
        dialog = ft.AlertDialog(
            title=ft.Text("选择填充颜色"),
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
                        # RGBA滑块
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("R:", width=30, color=ft.Colors.RED),
                                        ft.Container(content=r_slider, expand=True),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("G:", width=30, color=ft.Colors.GREEN),
                                        ft.Container(content=g_slider, expand=True),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("B:", width=30, color=ft.Colors.BLUE),
                                        ft.Container(content=b_slider, expand=True),
                                    ],
                                    spacing=PADDING_SMALL,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("不透明度:", width=60, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Container(content=a_slider, expand=True),
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
        
        self._page.open(dialog)
    
    def _update_color_preview_in_dialog(
        self,
        r: int,
        g: int,
        b: int,
        a: int,
        preview_box: ft.Container,
        rgb_text: ft.Text
    ) -> None:
        """更新对话框中的颜色预览。"""
        preview_box.bgcolor = self._rgb_to_hex(r, g, b)
        opacity_percent = int(a / 255 * 100)
        rgb_text.value = f"RGBA({r}, {g}, {b}, {a})\n不透明度: {opacity_percent}%"
        self._page.update()
    
    def _apply_preset_fill_color(
        self,
        color: tuple,
        r_slider: ft.Slider,
        g_slider: ft.Slider,
        b_slider: ft.Slider,
        a_slider: ft.Slider,
        preview_box: ft.Container,
        rgb_text: ft.Text
    ) -> None:
        """应用预设填充颜色。"""
        r_slider.value = color[0]
        g_slider.value = color[1]
        b_slider.value = color[2]
        a_slider.value = 255  # 预设颜色默认完全不透明（100%）
        self._page.update()
        self._update_color_preview_in_dialog(
            color[0], color[1], color[2], 255, preview_box, rgb_text
        )
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "gif", "bmp", "webp"],
            allow_multiple=True,
        )
        if result and len(result) > 0:
            self.selected_files = [Path(f.path) for f in result]
            count = len(self.selected_files)
            if count == 1:
                self.file_list_text.value = self.selected_files[0].name
            else:
                self.file_list_text.value = f"已选择 {count} 个文件"
            self._page.update()
            
            # 显示预览区域并自动生成预览
            self.preview_section.visible = True
            self._page.update()
            self._update_preview()
    
    def _on_operation_change(self, e: ft.ControlEvent) -> None:
        """操作选择改变事件。"""
        self.current_operation = e.control.value
        
        # 显示或隐藏自定义角度设置
        if self.current_operation == "rotate_custom":
            self.custom_angle_section.visible = True
            self.custom_angle_hint.visible = True
        else:
            self.custom_angle_section.visible = False
            self.custom_angle_hint.visible = False
        
        self._page.update()
        
        # 实时更新预览
        self._update_preview()
    
    def _on_angle_slider_change(self, e: ft.ControlEvent) -> None:
        """角度滑块改变事件。"""
        # 同步更新文本框
        self.custom_angle_field.value = str(int(self.custom_angle_slider.value))
        self._page.update()
        
        # 实时更新预览
        self._debounced_update_preview()
    
    def _on_angle_field_change(self, e: ft.ControlEvent) -> None:
        """角度文本框改变事件。"""
        try:
            angle = float(self.custom_angle_field.value)
            if 0 <= angle <= 360:
                # 同步更新滑块
                self.custom_angle_slider.value = angle
                self._page.update()
                
                # 实时更新预览
                self._debounced_update_preview()
        except Exception:
            pass
    
    def _debounced_update_preview(self) -> None:
        """防抖更新预览。"""
        if not self.preview_update_pending:
            self.preview_update_pending = True
            
            async def _delayed_update():
                import asyncio
                await asyncio.sleep(0.3)  # 等待300ms
                self.preview_update_pending = False
                self._update_preview()
            
            self._page.run_task(_delayed_update)
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        is_custom = e.control.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        try:
            self._page.update()
        except Exception:
            pass
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            try:
                self._page.update()
            except Exception:
                pass
    
    def _update_preview(self) -> None:
        """更新预览（实时）。"""
        if not self.selected_files:
            return
        
        # 只预览第一张图片
        file_path = self.selected_files[0]
        
        if not file_path.exists():
            self.preview_status_text.value = "文件不存在"
            self._page.update()
            return
        
        try:
            self.preview_status_text.value = "正在生成预览..."
            self._page.update()
            
            # 读取原图
            img = Image.open(file_path)
            is_gif = getattr(img, "is_animated", False)
            
            # 获取第一帧作为原图预览
            if is_gif:
                original_img = img.copy().convert('RGB')
            else:
                original_img = img.copy()
            
            # 生成原图预览（调整大小）
            original_preview = original_img.copy()
            original_preview.thumbnail((350, 350), Image.Resampling.LANCZOS)
            
            # 处理第一帧生成预览
            if is_gif:
                frame = img.copy().convert('RGB')
            else:
                frame = img
            
            # 执行操作
            if self.current_operation == "rotate_90":
                preview_img = frame.rotate(-90, expand=True)
            elif self.current_operation == "rotate_180":
                preview_img = frame.rotate(180, expand=True)
            elif self.current_operation == "rotate_270":
                preview_img = frame.rotate(90, expand=True)
            elif self.current_operation == "flip_horizontal":
                preview_img = frame.transpose(Image.FLIP_LEFT_RIGHT)
            elif self.current_operation == "flip_vertical":
                preview_img = frame.transpose(Image.FLIP_TOP_BOTTOM)
            elif self.current_operation == "rotate_custom":
                # 自定义角度旋转
                try:
                    angle = float(self.custom_angle_field.value)
                except:
                    angle = 0
                
                # 使用当前填充颜色
                fill_color = self.current_fill_color
                
                preview_img = frame.rotate(angle, expand=True, fillcolor=fill_color)
            else:
                preview_img = frame
            
            # 调整效果图大小（最大350x350）
            preview_img.thumbnail((350, 350), Image.Resampling.LANCZOS)
            
            # 转换原图为base64
            import io
            import base64
            
            # 原图
            original_buffer = io.BytesIO()
            original_preview.save(original_buffer, format='PNG')
            original_base64 = base64.b64encode(original_buffer.getvalue()).decode()
            
            # 效果图
            preview_buffer = io.BytesIO()
            preview_img.save(preview_buffer, format='PNG')
            preview_base64 = base64.b64encode(preview_buffer.getvalue()).decode()
            
            # 显示原图和效果图
            self.original_image.src = original_base64
            self.original_image.visible = True
            self.preview_image.src = preview_base64
            self.preview_image.visible = True
            
            # 更新状态文本
            count = len(self.selected_files)
            gif_hint = " (GIF动图)" if is_gif else ""
            if count == 1:
                self.preview_status_text.value = f"预览：当前图片{gif_hint}"
            else:
                self.preview_status_text.value = f"预览：第1张图片（共{count}张）{gif_hint}"
            
            self._page.update()
        
        except Exception as ex:
            self.preview_status_text.value = f"预览失败: {str(ex)}"
            self.original_image.visible = False
            self.preview_image.visible = False
            self._page.update()
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """处理按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        # 显示进度
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.progress_text.value = "准备处理..."
        self.progress_bar.value = 0
        self._page.update()
        
        try:
            success_count = 0
            total = len(self.selected_files)
            
            for idx, file_path in enumerate(self.selected_files):
                if not file_path.exists():
                    continue
                
                # 更新进度
                self.progress_text.value = f"正在处理: {file_path.name} ({idx + 1}/{total})"
                self.progress_bar.value = idx / total
                self._page.update()
                
                try:
                    # 读取图片
                    img = Image.open(file_path)
                    is_gif = getattr(img, "is_animated", False)
                    
                    if is_gif:
                        # 处理 GIF 动图
                        frames = []
                        durations = []
                        
                        for frame in ImageSequence.Iterator(img):
                            frame = frame.copy()
                            
                            # 执行操作
                            if self.current_operation == "rotate_90":
                                processed_frame = frame.rotate(-90, expand=True)
                            elif self.current_operation == "rotate_180":
                                processed_frame = frame.rotate(180, expand=True)
                            elif self.current_operation == "rotate_270":
                                processed_frame = frame.rotate(90, expand=True)
                            elif self.current_operation == "flip_horizontal":
                                processed_frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
                            elif self.current_operation == "flip_vertical":
                                processed_frame = frame.transpose(Image.FLIP_TOP_BOTTOM)
                            elif self.current_operation == "rotate_custom":
                                # 自定义角度旋转
                                try:
                                    angle = float(self.custom_angle_field.value)
                                except:
                                    angle = 0
                                
                                # 使用当前填充颜色
                                fill_color = self.current_fill_color
                                
                                processed_frame = frame.rotate(angle, expand=True, fillcolor=fill_color)
                            else:
                                processed_frame = frame
                            
                            frames.append(processed_frame)
                            durations.append(frame.info.get('duration', 100))
                        
                        # GIF 处理完成，保存所有帧
                        img = frames[0]  # 用于后续保存
                        
                    else:
                        # 处理静态图片
                        # 执行操作
                        if self.current_operation == "rotate_90":
                            img = img.rotate(-90, expand=True)
                        elif self.current_operation == "rotate_180":
                            img = img.rotate(180, expand=True)
                        elif self.current_operation == "rotate_270":
                            img = img.rotate(90, expand=True)
                        elif self.current_operation == "flip_horizontal":
                            img = img.transpose(Image.FLIP_LEFT_RIGHT)
                        elif self.current_operation == "flip_vertical":
                            img = img.transpose(Image.FLIP_TOP_BOTTOM)
                        elif self.current_operation == "rotate_custom":
                            # 自定义角度旋转
                            try:
                                angle = float(self.custom_angle_field.value)
                            except:
                                angle = 0
                            
                            # 使用当前填充颜色
                            fill_color = self.current_fill_color
                            
                            # 旋转图片
                            # expand=True 会自动扩展画布以容纳旋转后的图片
                            img = img.rotate(angle, expand=True, fillcolor=fill_color)
                    
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
                        output_path = file_path.parent / f"{file_path.stem}_rotated{ext}"
                    
                    # 根据全局设置决定是否添加序号（覆盖模式除外）
                    if output_mode != "overwrite":
                        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                        output_path = get_unique_path(output_path, add_sequence=add_sequence)
                    
                    # 保存
                    if is_gif and output_format == "GIF":
                        # 保存 GIF 动图
                        frames[0].save(
                            output_path,
                            format='GIF',
                            save_all=True,
                            append_images=frames[1:],
                            duration=durations,
                            loop=0,
                            optimize=False,
                        )
                    else:
                        # 处理JPEG格式的RGBA图片
                        if output_format == "JPEG" or output_format == "JPG":
                            if img.mode in ("RGBA", "LA", "P"):
                                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                                if img.mode == "P":
                                    img = img.convert("RGBA")
                                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                                img = rgb_img
                            output_format = "JPEG"
                        
                        # 保存静态图片
                        img.save(output_path, format=output_format)
                    
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
            # 更新文件列表显示
            count = len(self.selected_files)
            if count == 1:
                self.file_list_text.value = self.selected_files[0].name
            else:
                self.file_list_text.value = f"已选择 {count} 个文件"
            # 显示预览区域并自动生成预览
            self.preview_section.visible = True
            self._update_preview()
            self._show_message(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_message("旋转/翻转工具不支持该格式", ft.Colors.ORANGE)
        
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
