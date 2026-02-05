# -*- coding: utf-8 -*-
"""图片边框视图模块。

提供给图片添加边框功能的用户界面。
"""

from pathlib import Path
from typing import List, Optional, Dict, Tuple

import flet as ft
from PIL import Image, ImageDraw

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils, get_unique_path


class ImageBorderView(ft.Container):
    """图片边框视图类。
    
    提供给图片添加边框功能，包括：
    - 自定义边框颜色（包括透明色）
    - 自定义边框宽度
    - 支持分别设置四边宽度
    - 批量处理
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
        on_back: Optional[callable] = None
    ) -> None:
        """初始化图片边框视图。
        
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
        self.on_back: Optional[callable] = on_back
        
        self.selected_files: List[Path] = []
        # GIF 文件映射：{文件路径: (是否GIF, 帧数)}
        self.gif_info: Dict[str, tuple] = {}
        
        # 边框颜色（默认黑色）
        self.border_color: Tuple[int, int, int, int] = (0, 0, 0, 255)  # RGBA
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 构建界面
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("图片边框", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.AUTO,
        )
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择图片:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_files,
                        ),
                        ft.Button(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self._on_select_folder,
                        ),
                        ft.TextButton(
                            "清空列表",
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
                                "支持格式: JPG, PNG, WebP, GIF, TIFF, BMP, ICO, AVIF, HEIC 等",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.margin.only(left=4, bottom=4),
                ),
                ft.Container(
                    content=self.file_list_view,
                    height=240,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 边框模式选项
        self.border_mode = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="uniform", label="统一边框"),
                    ft.Radio(value="custom", label="分别设置四边"),
                ],
                spacing=PADDING_LARGE,
            ),
            value="uniform",
            on_change=self._on_border_mode_change,
        )
        
        # 边框单位选项
        self.border_unit = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="px", label="像素 (px)"),
                    ft.Radio(value="percent", label="百分比 (%)"),
                ],
                spacing=PADDING_LARGE,
            ),
            value="px",
            on_change=self._on_border_unit_change,
        )
        
        # 统一边框宽度
        self.uniform_width_field = ft.TextField(
            label="边框宽度 (px)",
            hint_text="例如: 20",
            value="20",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
        )
        
        # 分别设置四边宽度
        self.top_width_field = ft.TextField(
            label="上边框 (px)",
            hint_text="20",
            value="20",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            visible=False,
        )
        self.bottom_width_field = ft.TextField(
            label="下边框 (px)",
            hint_text="20",
            value="20",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            visible=False,
        )
        self.left_width_field = ft.TextField(
            label="左边框 (px)",
            hint_text="20",
            value="20",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            visible=False,
        )
        self.right_width_field = ft.TextField(
            label="右边框 (px)",
            hint_text="20",
            value="20",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            visible=False,
        )
        
        # 圆角设置
        self.corner_radius_field = ft.TextField(
            label="圆角半径 (px)",
            hint_text="0 表示直角",
            value="0",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
        )
        
        self.corner_radius_tip = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        "圆角将应用于整张图片（包括边框）",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            ),
        )
        
        # 边框颜色选择
        self.color_preview = ft.Container(
            width=40,
            height=40,
            bgcolor="#000000",
            border_radius=8,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        self.color_hex_field = ft.TextField(
            label="颜色值",
            hint_text="#000000",
            value="#000000",
            width=120,
            on_change=self._on_color_hex_change,
        )
        
        self.color_picker_button = ft.Button(
            "选择颜色",
            icon=ft.Icons.COLOR_LENS,
            on_click=self._open_color_picker,
        )
        
        # 透明度滑块
        self.opacity_slider = ft.Slider(
            min=0,
            max=100,
            value=100,
            divisions=100,
            label="{value}%",
            on_change=self._on_opacity_change,
            width=200,
        )
        
        self.opacity_text = ft.Text("不透明度: 100%", size=14)
        
        # 透明边框提示
        self.transparent_tip = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.PRIMARY),
                    ft.Text(
                        "透明边框仅对PNG格式有效，其他格式将转换为PNG保存",
                        size=12,
                        color=ft.Colors.PRIMARY,
                    ),
                ],
                spacing=8,
            ),
            visible=False,
            margin=ft.margin.only(top=8),
        )
        
        self.border_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("边框设置:", size=14, weight=ft.FontWeight.W_500),
                    self.border_mode,
                    self.border_unit,
                    ft.Row(
                        controls=[
                            self.uniform_width_field,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Row(
                        controls=[
                            self.top_width_field,
                            self.bottom_width_field,
                            self.left_width_field,
                            self.right_width_field,
                        ],
                        spacing=PADDING_MEDIUM,
                        wrap=True,
                    ),
                    ft.Row(
                        controls=[
                            self.corner_radius_field,
                            self.corner_radius_tip,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("边框颜色:", size=14, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=[
                            self.color_preview,
                            self.color_hex_field,
                            self.color_picker_button,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            self.opacity_text,
                            self.opacity_slider,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.transparent_tip,
                ],
                spacing=PADDING_MEDIUM // 2,
                scroll=ft.ScrollMode.AUTO,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            expand=1,
        )
        
        # 输出选项
        self.output_mode = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new_file", label="保存为新文件"),
                    ft.Radio(value="custom_dir", label="保存到指定目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new_file",
            on_change=self._on_output_mode_change,
        )
        
        self.file_suffix = ft.TextField(
            label="文件后缀",
            hint_text="例如: _bordered",
            value="_bordered",
            width=200,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            hint_text="选择输出目录",
            value=str(self.config_service.get_output_dir()),
            read_only=True,
            expand=True,
            visible=False,
        )
        
        self.browse_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            visible=False,
        )
        
        self.output_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode,
                    self.file_suffix,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_button,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            expand=1,
        )
        
        # GIF 信息提示（初始隐藏）
        self.gif_info_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.GIF_BOX, size=20, color=ft.Colors.PRIMARY),
                    ft.Text(
                        "检测到 GIF 文件，将自动为所有帧添加边框",
                        size=13,
                    ),
                ],
                spacing=8,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.PRIMARY),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            visible=False,
        )
        
        # 底部按钮
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.BORDER_ALL, size=24),
                        ft.Text("添加边框", size=18, weight=ft.FontWeight.W_600),
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
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                self.gif_info_banner,
                ft.Row(
                    controls=[
                        self.border_options,
                        self.output_options,
                    ],
                    spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                self.progress_bar,
                self.progress_text,
                self.process_button,
                ft.Container(height=PADDING_LARGE),
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装主界面
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
        )
        
        # 初始化文件列表
        self._init_empty_state()
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=192,
                alignment=ft.Alignment.CENTER,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    async def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        await self._on_select_files(e)
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "webp", "bmp", "gif", "tiff", "tif", "ico", "avif", "heic", "heif"],
            allow_multiple=True,
        )
        if result:
            new_files = [Path(f.path) for f in result]
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择图片文件夹")
        if folder_path:
            folder = Path(folder_path)
            extensions = [".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif", ".ico", ".avif", ".heic", ".heif"]
            self.selected_files = []
            for ext in extensions:
                self.selected_files.extend(folder.glob(f"*{ext}"))
                self.selected_files.extend(folder.glob(f"*{ext.upper()}"))
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        self.gif_info.clear()
        
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=192,
                    alignment=ft.Alignment.CENTER,
                    on_click=self._on_empty_area_click,
                    ink=True,
                )
            )
        else:
            for idx, file_path in enumerate(self.selected_files):
                file_size = file_path.stat().st_size
                size_str = format_file_size(file_size)
                
                img_info = self.image_service.get_image_info(file_path)
                
                # 检测是否为 GIF
                is_gif = GifUtils.is_animated_gif(file_path)
                if is_gif:
                    frame_count = GifUtils.get_frame_count(file_path)
                    self.gif_info[str(file_path)] = (True, frame_count)
                
                if 'error' not in img_info:
                    format_str = img_info.get('format', '未知')
                    width = img_info.get('width', 0)
                    height = img_info.get('height', 0)
                    if is_gif:
                        dimension_str = f"{width} × {height} · {frame_count}帧"
                    else:
                        dimension_str = f"{width} × {height}"
                else:
                    format_str = file_path.suffix.upper().lstrip('.')
                    dimension_str = "无法读取"
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(
                                        str(idx + 1),
                                        size=14,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    width=30,
                                    alignment=ft.Alignment.CENTER,
                                ),
                                ft.Icon(ft.Icons.IMAGE, size=20, color=ft.Colors.PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            file_path.name,
                                            size=13,
                                            weight=ft.FontWeight.W_500,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.PHOTO_SIZE_SELECT_ACTUAL, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(dimension_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(size_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(format_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ],
                                            spacing=4,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="移除",
                                    on_click=lambda e, path=file_path: self._remove_file(path),
                                ),
                            ],
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        padding=ft.padding.symmetric(vertical=8, horizontal=PADDING_MEDIUM),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        ink=True,
                    )
                )
        
        self.file_list_view.update()
        
        # 更新 GIF 提示横幅
        if self.gif_info:
            gif_count = len(self.gif_info)
            total_frames = sum(info[1] for info in self.gif_info.values())
            self.gif_info_banner.content.controls[1].value = (
                f"检测到 {gif_count} 个 GIF 文件（共 {total_frames} 帧），将自动为所有帧添加边框"
            )
            self.gif_info_banner.visible = True
        else:
            self.gif_info_banner.visible = False
        
        try:
            self.gif_info_banner.update()
        except:
            pass
    
    def _remove_file(self, file_path: Path) -> None:
        """移除单个文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _on_border_mode_change(self, e: ft.ControlEvent) -> None:
        """边框模式变化事件。"""
        mode = self.border_mode.value
        
        if mode == "uniform":
            self.uniform_width_field.visible = True
            self.top_width_field.visible = False
            self.bottom_width_field.visible = False
            self.left_width_field.visible = False
            self.right_width_field.visible = False
        else:
            self.uniform_width_field.visible = False
            self.top_width_field.visible = True
            self.bottom_width_field.visible = True
            self.left_width_field.visible = True
            self.right_width_field.visible = True
        
        self.border_options.update()
    
    def _on_border_unit_change(self, e: ft.ControlEvent) -> None:
        """边框单位变化事件。"""
        unit = self.border_unit.value
        unit_label = "px" if unit == "px" else "%"
        
        # 更新所有边框宽度字段的标签
        self.uniform_width_field.label = f"边框宽度 ({unit_label})"
        self.top_width_field.label = f"上边框 ({unit_label})"
        self.bottom_width_field.label = f"下边框 ({unit_label})"
        self.left_width_field.label = f"左边框 ({unit_label})"
        self.right_width_field.label = f"右边框 ({unit_label})"
        
        # 更新提示文字
        if unit == "percent":
            self.uniform_width_field.hint_text = "例如: 5"
            self.top_width_field.hint_text = "5"
            self.bottom_width_field.hint_text = "5"
            self.left_width_field.hint_text = "5"
            self.right_width_field.hint_text = "5"
            # 更新默认值为百分比
            if self.uniform_width_field.value == "20":
                self.uniform_width_field.value = "5"
            if self.top_width_field.value == "20":
                self.top_width_field.value = "5"
            if self.bottom_width_field.value == "20":
                self.bottom_width_field.value = "5"
            if self.left_width_field.value == "20":
                self.left_width_field.value = "5"
            if self.right_width_field.value == "20":
                self.right_width_field.value = "5"
        else:
            self.uniform_width_field.hint_text = "例如: 20"
            self.top_width_field.hint_text = "20"
            self.bottom_width_field.hint_text = "20"
            self.left_width_field.hint_text = "20"
            self.right_width_field.hint_text = "20"
            # 更新默认值为像素
            if self.uniform_width_field.value == "5":
                self.uniform_width_field.value = "20"
            if self.top_width_field.value == "5":
                self.top_width_field.value = "20"
            if self.bottom_width_field.value == "5":
                self.bottom_width_field.value = "20"
            if self.left_width_field.value == "5":
                self.left_width_field.value = "20"
            if self.right_width_field.value == "5":
                self.right_width_field.value = "20"
        
        self.border_options.update()
    
    def _on_color_hex_change(self, e: ft.ControlEvent) -> None:
        """颜色值输入变化事件。"""
        hex_value = self.color_hex_field.value.strip()
        if hex_value.startswith("#"):
            hex_value = hex_value[1:]
        
        try:
            if len(hex_value) == 6:
                r = int(hex_value[0:2], 16)
                g = int(hex_value[2:4], 16)
                b = int(hex_value[4:6], 16)
                self.border_color = (r, g, b, int(self.opacity_slider.value * 255 / 100))
                self.color_preview.bgcolor = f"#{hex_value}"
                self.color_preview.update()
        except ValueError:
            pass
    
    def _on_opacity_change(self, e: ft.ControlEvent) -> None:
        """不透明度变化事件。"""
        opacity = int(self.opacity_slider.value)
        self.opacity_text.value = f"不透明度: {opacity}%"
        self.opacity_text.update()
        
        # 更新边框颜色的透明度
        r, g, b, _ = self.border_color
        self.border_color = (r, g, b, int(opacity * 255 / 100))
        
        # 显示/隐藏透明提示
        self.transparent_tip.visible = opacity < 100
        self.transparent_tip.update()
    
    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """RGB 转 HEX 颜色值。"""
        return f"#{r:02X}{g:02X}{b:02X}"
    
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
        
        # 当前颜色 (RGB)
        current_r, current_g, current_b, _ = self.border_color
        
        # 预览框
        preview_box = ft.Container(
            width=80,
            height=80,
            bgcolor=self._rgb_to_hex(current_r, current_g, current_b),
            border_radius=12,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        rgb_text = ft.Text(
            f"RGB({current_r}, {current_g}, {current_b})",
            size=14,
            weight=ft.FontWeight.W_500,
        )
        
        hex_text = ft.Text(
            self._rgb_to_hex(current_r, current_g, current_b),
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # RGB 滑块
        r_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=current_r,
            label="{value}",
            active_color=ft.Colors.RED,
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text,
                hex_text
            ),
        )
        
        g_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=current_g,
            label="{value}",
            active_color=ft.Colors.GREEN,
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text,
                hex_text
            ),
        )
        
        b_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=current_b,
            label="{value}",
            active_color=ft.Colors.BLUE,
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text,
                hex_text
            ),
        )
        
        # 常用颜色按钮
        preset_buttons = []
        for name, color in preset_colors:
            preset_buttons.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                width=40,
                                height=40,
                                bgcolor=self._rgb_to_hex(*color),
                                border_radius=8,
                                border=ft.border.all(2, ft.Colors.OUTLINE),
                                ink=True,
                                on_click=lambda e, c=color: self._apply_preset_color(
                                    c, r_slider, g_slider, b_slider, preview_box, rgb_text, hex_text
                                ),
                            ),
                            ft.Text(name, size=10, text_align=ft.TextAlign.CENTER),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=2,
                )
            )
        
        def close_dialog(apply: bool):
            if apply:
                # 应用选择的颜色
                r = int(r_slider.value)
                g = int(g_slider.value)
                b = int(b_slider.value)
                opacity = int(self.opacity_slider.value * 255 / 100)
                self.border_color = (r, g, b, opacity)
                
                # 更新 UI
                hex_color = self._rgb_to_hex(r, g, b)
                self.color_hex_field.value = hex_color
                self.color_preview.bgcolor = hex_color
                self.color_hex_field.update()
                self.color_preview.update()
            
            dialog.open = False
            self._page.update()
        
        # 创建对话框
        dialog = ft.AlertDialog(
            title=ft.Text("选择边框颜色"),
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
                                        hex_text,
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
                width=450,
                height=420,
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
        rgb_text: ft.Text,
        hex_text: ft.Text
    ) -> None:
        """更新对话框中的颜色预览。"""
        hex_color = self._rgb_to_hex(r, g, b)
        preview_box.bgcolor = hex_color
        rgb_text.value = f"RGB({r}, {g}, {b})"
        hex_text.value = hex_color
        preview_box.update()
        rgb_text.update()
        hex_text.update()
    
    def _apply_preset_color(
        self,
        color: Tuple[int, int, int],
        r_slider: ft.Slider,
        g_slider: ft.Slider,
        b_slider: ft.Slider,
        preview_box: ft.Container,
        rgb_text: ft.Text,
        hex_text: ft.Text
    ) -> None:
        """应用预设颜色到滑块和预览框。"""
        r, g, b = color
        r_slider.value = r
        g_slider.value = g
        b_slider.value = b
        self._update_color_preview_in_dialog(r, g, b, preview_box, rgb_text, hex_text)
        r_slider.update()
        g_slider.update()
        b_slider.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode = self.output_mode.value
        
        if mode == "new_file":
            self.file_suffix.visible = True
            self.custom_output_dir.visible = False
            self.browse_button.visible = False
        else:  # custom_dir
            self.file_suffix.visible = False
            self.custom_output_dir.visible = True
            self.browse_button.visible = True
        
        self.output_options.update()
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            self.custom_output_dir.update()
    
    def _get_border_widths_raw(self) -> Tuple[float, float, float, float]:
        """获取原始边框宽度值（上、下、左、右）。"""
        if self.border_mode.value == "uniform":
            try:
                width = float(self.uniform_width_field.value or 0)
            except ValueError:
                width = 0
            return (width, width, width, width)
        else:
            try:
                top = float(self.top_width_field.value or 0)
                bottom = float(self.bottom_width_field.value or 0)
                left = float(self.left_width_field.value or 0)
                right = float(self.right_width_field.value or 0)
            except ValueError:
                top = bottom = left = right = 0
            return (top, bottom, left, right)
    
    def _calculate_border_widths(self, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """根据图片尺寸计算实际边框宽度（上、下、左、右）。
        
        Args:
            img_width: 图片宽度
            img_height: 图片高度
            
        Returns:
            实际边框宽度（像素）
        """
        top, bottom, left, right = self._get_border_widths_raw()
        
        if self.border_unit.value == "percent":
            # 按百分比计算：上下边框基于高度，左右边框基于宽度
            top = int(img_height * top / 100)
            bottom = int(img_height * bottom / 100)
            left = int(img_width * left / 100)
            right = int(img_width * right / 100)
        else:
            top = int(top)
            bottom = int(bottom)
            left = int(left)
            right = int(right)
        
        return (top, bottom, left, right)
    
    def _get_corner_radius(self) -> int:
        """获取圆角半径。"""
        try:
            return int(self.corner_radius_field.value or 0)
        except ValueError:
            return 0
    
    def _create_rounded_mask(self, size: Tuple[int, int], radius: int) -> Image.Image:
        """创建圆角蒙版。
        
        Args:
            size: 蒙版尺寸 (width, height)
            radius: 圆角半径
            
        Returns:
            圆角蒙版图片（L模式）
        """
        width, height = size
        # 确保圆角不超过图片尺寸的一半
        radius = min(radius, width // 2, height // 2)
        
        # 创建蒙版
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        
        # 绘制圆角矩形
        draw.rounded_rectangle(
            [(0, 0), (width - 1, height - 1)],
            radius=radius,
            fill=255
        )
        
        return mask
    
    def _add_border_to_image(self, img: Image.Image, top: int, bottom: int, left: int, right: int, corner_radius: int = 0) -> Image.Image:
        """给图片添加边框。
        
        Args:
            img: PIL Image对象
            top: 上边框宽度
            bottom: 下边框宽度
            left: 左边框宽度
            right: 右边框宽度
            corner_radius: 圆角半径
            
        Returns:
            添加边框后的图片
        """
        orig_width, orig_height = img.size
        new_width = orig_width + left + right
        new_height = orig_height + top + bottom
        
        # 检查是否需要透明背景
        has_transparency = self.border_color[3] < 255
        has_corner_radius = corner_radius > 0
        
        # 如果有圆角，需要使用 RGBA 模式
        if has_transparency or has_corner_radius:
            # 创建 RGBA 图片
            new_img = Image.new("RGBA", (new_width, new_height), self.border_color)
            # 确保原图是 RGBA 模式
            if img.mode != "RGBA":
                img = img.convert("RGBA")
        else:
            # 创建 RGB 图片
            rgb_color = self.border_color[:3]
            new_img = Image.new("RGB", (new_width, new_height), rgb_color)
            # 确保原图是 RGB 模式
            if img.mode == "RGBA":
                # 如果原图有透明通道，需要合成到边框颜色上
                background = Image.new("RGB", img.size, rgb_color)
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
        
        # 将原图粘贴到中间
        new_img.paste(img, (left, top))
        
        # 应用圆角
        if has_corner_radius:
            # 创建圆角蒙版
            mask = self._create_rounded_mask((new_width, new_height), corner_radius)
            
            # 创建透明背景
            result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
            
            # 使用蒙版合成
            if new_img.mode != "RGBA":
                new_img = new_img.convert("RGBA")
            result.paste(new_img, mask=mask)
            
            return result
        
        return new_img
    
    def _add_border_to_gif(self, input_path: Path, output_path: Path, top: int, bottom: int, left: int, right: int, corner_radius: int = 0) -> bool:
        """给 GIF 所有帧添加边框。
        
        Args:
            input_path: 输入 GIF 路径
            output_path: 输出 GIF 路径
            top: 上边框宽度
            bottom: 下边框宽度
            left: 左边框宽度
            right: 右边框宽度
            corner_radius: 圆角半径
            
        Returns:
            是否成功
        """
        try:
            with Image.open(input_path) as gif:
                duration = gif.info.get('duration', 100)
                loop = gif.info.get('loop', 0)
                
                frames = GifUtils.extract_all_frames(input_path)
                if not frames:
                    return False
                
                bordered_frames = []
                for frame in frames:
                    bordered = self._add_border_to_image(frame, top, bottom, left, right, corner_radius)
                    # GIF 需要转换为 P 模式
                    if bordered.mode == "RGBA":
                        bordered = bordered.convert("P", palette=Image.ADAPTIVE)
                    bordered_frames.append(bordered)
                
                if bordered_frames:
                    bordered_frames[0].save(
                        output_path,
                        save_all=True,
                        append_images=bordered_frames[1:],
                        duration=duration,
                        loop=loop,
                        optimize=False,
                    )
                    return True
                
                return False
        except Exception:
            return False
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。"""
        if not self.selected_files:
            self.progress_text.value = "❌ 请先选择图片文件"
            self.progress_text.update()
            return
        
        # 获取原始边框宽度值（用于验证）
        raw_top, raw_bottom, raw_left, raw_right = self._get_border_widths_raw()
        if raw_top == 0 and raw_bottom == 0 and raw_left == 0 and raw_right == 0:
            self.progress_text.value = "❌ 请设置边框宽度"
            self.progress_text.update()
            return
        
        # 获取圆角半径
        corner_radius = self._get_corner_radius()
        
        # 检查是否需要透明（有透明度或有圆角）
        has_transparency = self.border_color[3] < 255
        has_corner_radius = corner_radius > 0
        needs_png = has_transparency or has_corner_radius
        
        # 显示进度条
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.process_button.visible = False
        self.progress_text.value = "开始处理..."
        self.update()
        
        # 处理文件
        success_count = 0
        fail_count = 0
        total = len(self.selected_files)
        
        for idx, file_path in enumerate(self.selected_files):
            try:
                # 读取图片获取尺寸，用于计算百分比边框
                with Image.open(file_path) as img:
                    img_width, img_height = img.size
                
                # 根据图片尺寸计算实际边框宽度
                top, bottom, left, right = self._calculate_border_widths(img_width, img_height)
                
                # 确定输出路径
                output_mode = self.output_mode.value
                suffix = self.file_suffix.value or "_bordered"
                
                # 如果需要透明或有圆角，输出为 PNG
                if needs_png and file_path.suffix.lower() not in ['.png', '.gif']:
                    output_ext = ".png"
                else:
                    output_ext = file_path.suffix
                
                if output_mode == "new_file":
                    output_path = file_path.parent / f"{file_path.stem}{suffix}{output_ext}"
                else:  # custom_dir
                    output_dir = Path(self.custom_output_dir.value) if self.custom_output_dir.value else file_path.parent
                    output_path = output_dir / f"{file_path.stem}{output_ext}"
                
                # 根据全局设置决定是否添加序号
                add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                output_path = get_unique_path(output_path, add_sequence=add_sequence)
                
                # 检查是否为 GIF
                is_gif = str(file_path) in self.gif_info
                
                if is_gif:
                    gif_data = self.gif_info.get(str(file_path))
                    frame_count = gif_data[1] if gif_data else 0
                    if frame_count > 0:
                        self.progress_text.value = f"正在处理 GIF ({frame_count} 帧)..."
                        self.progress_text.update()
                    result = self._add_border_to_gif(file_path, output_path, top, bottom, left, right, corner_radius)
                else:
                    # 普通图片处理
                    with Image.open(file_path) as img:
                        bordered_img = self._add_border_to_image(img, top, bottom, left, right, corner_radius)
                        bordered_img.save(output_path)
                        result = True
                
                if result:
                    success_count += 1
                else:
                    fail_count += 1
                
            except Exception:
                fail_count += 1
            
            # 更新进度
            progress = (idx + 1) / total
            self.progress_bar.value = progress
            self.progress_text.value = f"处理中... {idx + 1}/{total}"
            self.update()
        
        # 完成
        self.progress_bar.visible = False
        self.process_button.visible = True
        self.progress_text.value = f"✅ 完成！成功: {success_count}, 失败: {fail_count}"
        self.update()
        
        # 3秒后清除消息
        import time
        time.sleep(3)
        self.progress_text.value = ""
        self.update()
    
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
            self._show_message("图片边框工具不支持该格式", ft.Colors.ORANGE)
        
        self._page.update()
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        self.on_back = None
        self.content = None
        gc.collect()

