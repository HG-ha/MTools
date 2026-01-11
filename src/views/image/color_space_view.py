# -*- coding: utf-8 -*-
"""图片颜色空间转换视图模块。

提供图片颜色空间转换功能的用户界面。
"""

from pathlib import Path
from typing import Callable, List, Optional
from concurrent.futures import ThreadPoolExecutor

import flet as ft
import numpy as np
from PIL import Image

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, ImageService
from utils import format_file_size, logger, get_unique_path


class ColorSpaceView(ft.Container):
    """图片颜色空间转换视图类。
    
    提供图片颜色空间转换功能，包括：
    - RGB ↔ 灰度
    - RGB ↔ CMYK
    - RGB ↔ HSV/HSL
    - RGB ↔ LAB
    - 反色处理
    - 批量处理
    """

    # 支持的颜色空间转换
    COLOR_SPACES = [
        ("grayscale", "灰度图", "将彩色图片转换为灰度图"),
        ("rgba", "RGBA", "添加/保留透明通道"),
        ("rgb", "RGB", "移除透明通道，转换为RGB"),
        ("cmyk", "CMYK", "转换为印刷色彩模式（青、品红、黄、黑）"),
        ("lab", "LAB", "转换为CIE LAB色彩空间"),
        ("hsv", "HSV", "转换为色相-饱和度-明度模式"),
        ("invert", "反色", "反转图片颜色"),
        ("sepia", "复古棕褐色", "应用复古棕褐色调效果"),
        ("binary", "二值化", "转换为纯黑白图像"),
    ]
    
    # 支持的输入格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', 
        '.tiff', '.tif', '.ico', '.avif', '.heic', '.heif'
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化颜色空间转换视图。
        
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
        
        self.selected_files: List[Path] = []
        self.target_color_space: str = "grayscale"
        self.binary_threshold: int = 128  # 二值化阈值
        
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
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("颜色空间转换", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域 - 文件列表
        self.file_list_view: ft.Column = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 文件选择按钮行
        file_buttons_row = ft.Row(
            controls=[
                ft.Text("选择图片:", size=14, weight=ft.FontWeight.W_500),
                ft.ElevatedButton(
                    "选择文件",
                    icon=ft.Icons.FILE_UPLOAD,
                    on_click=self._on_select_files,
                ),
                ft.ElevatedButton(
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
        )
        
        # 文件列表容器（带边框）
        self.file_list_container = ft.Container(
            content=self.file_list_view,
            height=300,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        file_select_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    file_buttons_row,
                    # 支持格式说明
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: JPG, PNG, WebP, BMP, TIFF, ICO, AVIF, HEIC 等",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, bottom=4),
                    ),
                    self.file_list_container,
                ],
                spacing=PADDING_MEDIUM,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 颜色空间选择区域
        self.color_space_dropdown = ft.Dropdown(
            label="目标颜色空间",
            value="grayscale",
            options=[
                ft.dropdown.Option(key=cs[0], text=f"{cs[1]} - {cs[2]}")
                for cs in self.COLOR_SPACES
            ],
            on_change=self._on_color_space_change,
            expand=True,
        )
        
        # 输出格式选择
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            value="png",
            options=[
                ft.dropdown.Option("original", "保持原格式"),
                ft.dropdown.Option("png", "PNG（推荐，支持透明）"),
                ft.dropdown.Option("jpg", "JPEG"),
                ft.dropdown.Option("webp", "WebP"),
                ft.dropdown.Option("tiff", "TIFF"),
            ],
            width=200,
        )
        
        # 二值化阈值滑块（仅在选择二值化时显示）
        self.threshold_text = ft.Text("阈值: 128", size=14)
        self.threshold_slider = ft.Slider(
            min=0,
            max=255,
            value=128,
            divisions=255,
            label="{value}",
            on_change=self._on_threshold_change,
            expand=True,
        )
        
        self.threshold_container = ft.Container(
            content=ft.Row(
                controls=[
                    self.threshold_text,
                    self.threshold_slider,
                ],
                spacing=PADDING_MEDIUM,
            ),
            visible=False,  # 默认隐藏
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        color_space_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("转换设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=[
                            self.color_space_dropdown,
                            self.output_format_dropdown,
                        ],
                        spacing=PADDING_LARGE,
                    ),
                    self.threshold_container,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="same_dir", label="保存到原目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_LARGE,
            ),
            value="same_dir",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir: ft.TextField = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_select_output_dir,
            disabled=True,
        )
        
        output_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项:", size=14, weight=ft.FontWeight.W_500),
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
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度区域
        self.progress_bar = ft.ProgressBar(
            visible=False,
            width=float('inf'),
        )
        
        self.progress_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        progress_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    self.progress_text,
                ],
                spacing=PADDING_SMALL,
            ),
        )
        
        # 转换按钮
        self.convert_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TRANSFORM),
                    ft.Text("开始转换", size=16),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                padding=ft.padding.symmetric(horizontal=32, vertical=16),
            ),
            on_click=self._on_convert,
            disabled=True,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                ft.Container(height=PADDING_SMALL),
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                color_space_area,
                ft.Container(height=PADDING_MEDIUM),
                output_options,
                ft.Container(height=PADDING_LARGE),
                progress_container,
                ft.Container(height=PADDING_MEDIUM),
                ft.Container(
                    content=self.convert_btn,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=0,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        # 组装主界面 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
        )
        
        # 文件选择器
        self.file_picker = ft.FilePicker(on_result=self._on_files_selected)
        self.folder_picker = ft.FilePicker(on_result=self._on_folder_selected)
        self.output_dir_picker = ft.FilePicker(on_result=self._on_output_dir_selected)
        
        # 初始化文件列表显示（显示空状态）
        self._update_file_list()
    
    def did_mount(self) -> None:
        """组件挂载后添加文件选择器到overlay。"""
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
        if self.folder_picker not in self.page.overlay:
            self.page.overlay.append(self.folder_picker)
        if self.output_dir_picker not in self.page.overlay:
            self.page.overlay.append(self.output_dir_picker)
        self.page.update()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """处理返回按钮点击。"""
        if self.on_back:
            self.on_back()
    
    def _on_select_files(self, e: ft.ControlEvent = None) -> None:
        """打开文件选择对话框。"""
        self.file_picker.pick_files(
            allowed_extensions=[ext.lstrip('.') for ext in self.SUPPORTED_EXTENSIONS],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """打开文件夹选择对话框。"""
        self.folder_picker.get_directory_path()
    
    def _on_select_output_dir(self, e: ft.ControlEvent) -> None:
        """打开输出目录选择对话框。"""
        self.output_dir_picker.get_directory_path()
    
    def _on_files_selected(self, e: ft.FilePickerResultEvent) -> None:
        """处理文件选择结果。"""
        if e.files:
            for f in e.files:
                path = Path(f.path)
                if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    if path not in self.selected_files:
                        self.selected_files.append(path)
            self._update_file_list()
    
    def _on_folder_selected(self, e: ft.FilePickerResultEvent) -> None:
        """处理文件夹选择结果。"""
        if e.path:
            folder = Path(e.path)
            for ext in self.SUPPORTED_EXTENSIONS:
                for file in folder.glob(f"*{ext}"):
                    if file not in self.selected_files:
                        self.selected_files.append(file)
                for file in folder.glob(f"*{ext.upper()}"):
                    if file not in self.selected_files:
                        self.selected_files.append(file)
            self._update_file_list()
    
    def _on_output_dir_selected(self, e: ft.FilePickerResultEvent) -> None:
        """处理输出目录选择结果。"""
        if e.path:
            self.custom_output_dir.value = e.path
            self.page.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """处理输出模式变化。"""
        is_custom = e.control.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        self.page.update()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            # 空状态提示（固定高度以实现居中）
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击选择按钮或点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=250,
                    alignment=ft.alignment.center,
                    on_click=self._on_select_files,
                    tooltip="点击选择图片",
                )
            )
        else:
            for i, file_path in enumerate(self.selected_files):
                file_info = self.image_service.get_image_info(file_path)
                
                if 'error' in file_info:
                    info_text = f"错误: {file_info['error']}"
                    icon_color = ft.Colors.RED
                else:
                    size_str = format_file_size(file_info['file_size'])
                    info_text = f"{file_info['width']}×{file_info['height']} · {size_str}"
                    icon_color = ft.Colors.PRIMARY
                
                file_item: ft.Container = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE, size=20, color=icon_color),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        file_path.name,
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(info_text, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=16,
                                tooltip="移除",
                                on_click=lambda e, idx=i: self._on_remove_file(idx),
                            ),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    padding=PADDING_MEDIUM // 2,
                    border_radius=BORDER_RADIUS_MEDIUM,
                    bgcolor=ft.Colors.SECONDARY_CONTAINER,
                )
                
                self.file_list_view.controls.append(file_item)
        
        # 更新按钮状态
        self.convert_btn.disabled = len(self.selected_files) == 0
        
        try:
            self.page.update()
        except Exception:
            pass
    
    def _on_remove_file(self, index: int) -> None:
        """移除文件列表中的文件。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
    
    def _on_color_space_change(self, e: ft.ControlEvent) -> None:
        """处理颜色空间选择变化。"""
        self.target_color_space = e.control.value
        # 显示/隐藏二值化阈值设置
        self.threshold_container.visible = (self.target_color_space == "binary")
        
        # CMYK 模式只支持 JPEG 和 TIFF 格式
        if self.target_color_space == "cmyk":
            if self.output_format_dropdown.value not in ("jpg", "tiff"):
                self.output_format_dropdown.value = "tiff"
                self._show_snackbar("CMYK 模式仅支持 JPEG 和 TIFF 格式，已自动切换", ft.Colors.ORANGE)
        
        self.page.update()
    
    def _show_snackbar(self, message: str, bgcolor: str = None) -> None:
        """显示提示消息。"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=bgcolor,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _on_threshold_change(self, e: ft.ControlEvent) -> None:
        """处理二值化阈值变化。"""
        self.binary_threshold = int(e.control.value)
        self.threshold_text.value = f"阈值: {self.binary_threshold}"
        self.page.update()
    
    def add_files(self, files: List[Path]) -> None:
        """添加文件到列表（供外部调用）。
        
        Args:
            files: 文件路径列表
        """
        for file in files:
            if file.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                if file not in self.selected_files:
                    self.selected_files.append(file)
        self._update_file_list()
    
    def _on_convert(self, e: ft.ControlEvent) -> None:
        """开始颜色空间转换。"""
        if not self.selected_files:
            return
        
        # 禁用按钮，显示进度
        self.convert_btn.disabled = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.page.update()
        
        # 在后台线程执行转换
        def do_convert():
            total = len(self.selected_files)
            success_count = 0
            error_count = 0
            
            # 确定输出目录
            if self.output_mode_radio.value == "custom":
                output_dir = Path(self.custom_output_dir.value) if self.custom_output_dir.value else None
            else:
                output_dir = None
            
            output_format = self.output_format_dropdown.value
            
            for i, file in enumerate(self.selected_files):
                try:
                    # 更新进度
                    self.progress_text.value = f"正在处理: {file.name} ({i + 1}/{total})"
                    self.progress_bar.value = i / total
                    self.page.update()
                    
                    # 执行转换
                    self._convert_image(file, output_dir, output_format)
                    success_count += 1
                    
                except Exception as ex:
                    logger.error(f"转换失败 {file.name}: {ex}")
                    error_count += 1
            
            # 完成
            self.progress_bar.value = 1.0
            self.progress_text.value = f"完成！成功: {success_count}, 失败: {error_count}"
            self.convert_btn.disabled = False
            self.page.update()
            
            # 显示完成提示
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"颜色空间转换完成！成功: {success_count}, 失败: {error_count}"),
                bgcolor=ft.Colors.GREEN if error_count == 0 else ft.Colors.ORANGE,
            )
            self.page.snack_bar.open = True
            self.page.update()
        
        # 使用线程池执行
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(do_convert)
    
    def _convert_image(self, file: Path, output_dir: Optional[Path], output_format: str) -> None:
        """转换单张图片的颜色空间。
        
        Args:
            file: 输入文件路径
            output_dir: 输出目录（None则使用原目录）
            output_format: 输出格式
        """
        # 打开图片
        img = Image.open(file)
        
        # 根据目标颜色空间进行转换
        if self.target_color_space == "grayscale":
            result = img.convert("L")
        elif self.target_color_space == "rgba":
            result = img.convert("RGBA")
        elif self.target_color_space == "rgb":
            result = img.convert("RGB")
        elif self.target_color_space == "cmyk":
            result = img.convert("CMYK")
        elif self.target_color_space == "lab":
            result = self._convert_to_lab(img)
        elif self.target_color_space == "hsv":
            result = self._convert_to_hsv(img)
        elif self.target_color_space == "invert":
            result = self._invert_colors(img)
        elif self.target_color_space == "sepia":
            result = self._apply_sepia(img)
        elif self.target_color_space == "binary":
            result = self._convert_to_binary(img, self.binary_threshold)
        else:
            result = img
        
        # 确定输出路径和格式
        if output_format == "original":
            ext = file.suffix
        else:
            ext = f".{output_format}"
        
        # 确定输出目录
        if output_dir:
            out_path = output_dir / f"{file.stem}_converted{ext}"
        else:
            out_path = file.parent / f"{file.stem}_converted{ext}"
        
        # 确保路径唯一
        out_path = get_unique_path(out_path)
        
        # 保存时处理格式兼容性
        save_format = ext.lstrip('.').upper()
        if save_format == "JPG":
            save_format = "JPEG"
        
        # JPEG 不支持透明通道，需要转换
        if save_format == "JPEG" and result.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", result.size, (255, 255, 255))
            if result.mode == "P":
                result = result.convert("RGBA")
            background.paste(result, mask=result.split()[-1] if result.mode == "RGBA" else None)
            result = background
        elif save_format == "JPEG" and result.mode == "L":
            result = result.convert("RGB")
        
        # CMYK 图像只能保存为 JPEG 或 TIFF
        if result.mode == "CMYK" and save_format not in ("JPEG", "TIFF"):
            save_format = "TIFF"
            out_path = out_path.with_suffix(".tiff")
        
        result.save(out_path, format=save_format)
        logger.info(f"已保存: {out_path}")
    
    def _convert_to_lab(self, img: Image.Image) -> Image.Image:
        """将图片转换为 LAB 色彩空间。
        
        注意：PIL 不直接支持 LAB 保存，这里转换后再转回 RGB 以便保存。
        """
        import cv2
        
        # 转换为 RGB
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # 使用 OpenCV 进行 LAB 转换
        img_array = np.array(img)
        lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
        # 转回 RGB 以便保存（LAB 可视化）
        rgb_back = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        return Image.fromarray(rgb_back)
    
    def _convert_to_hsv(self, img: Image.Image) -> Image.Image:
        """将图片转换为 HSV 色彩空间并可视化。"""
        import cv2
        
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        img_array = np.array(img)
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        # HSV 直接作为 RGB 显示会产生独特的视觉效果
        
        return Image.fromarray(hsv)
    
    def _invert_colors(self, img: Image.Image) -> Image.Image:
        """反转图片颜色。"""
        from PIL import ImageOps
        
        # 处理带透明通道的图片
        if img.mode == "RGBA":
            r, g, b, a = img.split()
            rgb = Image.merge("RGB", (r, g, b))
            inverted = ImageOps.invert(rgb)
            r2, g2, b2 = inverted.split()
            return Image.merge("RGBA", (r2, g2, b2, a))
        elif img.mode in ("L", "RGB"):
            return ImageOps.invert(img)
        else:
            # 转换为 RGB 再反转
            rgb = img.convert("RGB")
            return ImageOps.invert(rgb)
    
    def _apply_sepia(self, img: Image.Image) -> Image.Image:
        """应用复古棕褐色调效果。"""
        # 转换为 RGB
        if img.mode != "RGB":
            if img.mode == "RGBA":
                alpha = img.split()[-1]
            else:
                alpha = None
            img = img.convert("RGB")
        else:
            alpha = None
        
        img_array = np.array(img, dtype=np.float32)
        
        # Sepia 转换矩阵
        sepia_matrix = np.array([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131]
        ])
        
        # 应用矩阵
        sepia = img_array @ sepia_matrix.T
        sepia = np.clip(sepia, 0, 255).astype(np.uint8)
        
        result = Image.fromarray(sepia)
        
        # 恢复透明通道
        if alpha:
            result = result.convert("RGBA")
            r, g, b, _ = result.split()
            result = Image.merge("RGBA", (r, g, b, alpha))
        
        return result
    
    def _convert_to_binary(self, img: Image.Image, threshold: int = 128) -> Image.Image:
        """将图片转换为二值图像。
        
        Args:
            img: 输入图片
            threshold: 二值化阈值 (0-255)
        """
        # 先转为灰度
        gray = img.convert("L")
        # 应用阈值
        binary = gray.point(lambda x: 255 if x > threshold else 0, mode='1')
        return binary.convert("L")  # 转回 L 模式以便保存
    
    def release_resources(self) -> None:
        """释放资源。"""
        self.selected_files.clear()
        import gc
        gc.collect()
