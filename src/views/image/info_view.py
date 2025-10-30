# -*- coding: utf-8 -*-
"""图片信息查看视图模块。

提供图片详细信息查看功能的用户界面。
"""

from pathlib import Path
from typing import Callable, Optional, Any

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService, ImageService
from utils import format_file_size


class ImageInfoView(ft.Container):
    """图片信息查看视图类。
    
    提供图片详细信息查看功能，包括：
    - 基本信息（文件名、路径、格式、大小等）
    - 尺寸与像素信息（宽高、宽高比、总像素、百万像素、DPI等）
    - 颜色信息（颜色模式、位深度、调色板、透明度、ICC配置文件、色彩统计等）
    - 动画信息（GIF帧数等）
    - 压缩信息（JPEG质量、渐进式、PNG交错等）
    - 拍摄参数（相机型号、镜头、曝光、光圈、ISO、焦距等）
    - GPS信息（拍摄位置坐标）
    - 文件哈希（MD5、SHA256）
    - 时间信息（创建时间、修改时间）
    - EXIF 元数据（详细的EXIF标签信息）
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片信息查看视图。
        
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
        
        self.selected_file: Optional[Path] = None
        self.current_info: dict = {}
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
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
                ft.Text("图片信息查看", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域和操作按钮
        self.copy_all_button = ft.ElevatedButton(
            "复制全部信息",
            icon=ft.Icons.CONTENT_COPY,
            on_click=self._copy_all_info,
            visible=False,
        )
        
        file_select_row: ft.Row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "选择图片",
                    icon=ft.Icons.FILE_UPLOAD,
                    on_click=self._on_select_file,
                ),
                self.copy_all_button,
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 图片预览区域
        self.image_preview: ft.Image = ft.Image(
            src="",
            width=400,
            height=400,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        
        preview_container: ft.Container = ft.Container(
            content=self.image_preview,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            alignment=ft.alignment.center,
            height=450,
        )
        
        # 信息显示区域
        self.info_column: ft.Column = ft.Column(
            controls=[],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,
        )
        
        info_container: ft.Container = ft.Container(
            content=self.info_column,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            expand=True,
        )
        
        # 主内容区域 - 左右分栏
        main_content: ft.Row = ft.Row(
            controls=[
                ft.Container(
                    content=preview_container,
                    expand=1,
                ),
                ft.Container(
                    content=info_container,
                    expand=2,
                ),
            ],
            spacing=PADDING_LARGE,
            expand=True,
        )
        
        # 初始化空状态
        self._init_empty_state()
        
        # 组装主界面
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                file_select_row,
                main_content,
            ],
            spacing=PADDING_MEDIUM,
            expand=True,
        )
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.info_column.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=64, color=TEXT_SECONDARY),
                        ft.Text("未选择图片", color=TEXT_SECONDARY, size=16),
                        ft.Text("请选择一张图片以查看详细信息", color=TEXT_SECONDARY, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                alignment=ft.alignment.center,
                expand=True,
            )
        )
    
    def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                file_path: Path = Path(result.files[0].path)
                self.selected_file = file_path
                self._load_and_display_info()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "webp", "bmp", "gif", "tiff", "tif", "ico", "heic", "heif", "avif"],
            allow_multiple=False,
        )
    
    def _load_and_display_info(self) -> None:
        """加载并显示图片信息。"""
        if not self.selected_file or not self.selected_file.exists():
            self._show_message("文件不存在", ft.Colors.RED)
            return
        
        # 获取详细信息
        self.current_info = self.image_service.get_detailed_image_info(self.selected_file)
        
        if 'error' in self.current_info:
            self._show_message(f"读取图片失败: {self.current_info['error']}", ft.Colors.RED)
            return
        
        # 显示图片预览
        self.image_preview.src = str(self.selected_file)
        self.image_preview.visible = True
        self.image_preview.update()
        
        # 显示复制全部按钮
        self.copy_all_button.visible = True
        self.copy_all_button.update()
        
        # 显示信息
        self._display_info()
    
    def _display_info(self) -> None:
        """显示图片信息。"""
        self.info_column.controls.clear()
        
        # 基本信息部分
        basic_info_controls = [
            self._create_section_title("基本信息", ft.Icons.IMAGE),
            self._create_info_row("文件名", self.current_info.get('filename', '-'), copyable=True),
            self._create_info_row("文件路径", self.current_info.get('filepath', '-'), copyable=True),
            self._create_info_row("文件大小", format_file_size(self.current_info.get('file_size', 0)), copyable=True),
            self._create_info_row("格式", self.current_info.get('format', '-'), copyable=True),
        ]
        
        # 添加格式描述（如果有）
        if self.current_info.get('format_description'):
            basic_info_controls.append(
                self._create_info_row("格式描述", self.current_info.get('format_description', ''), copyable=True)
            )
        
        basic_info_section = ft.Container(
            content=ft.Column(
                controls=basic_info_controls,
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        self.info_column.controls.append(basic_info_section)
        
        # 尺寸与像素信息部分
        dimension_controls = [
            self._create_section_title("尺寸与像素信息", ft.Icons.ASPECT_RATIO),
            self._create_info_row("宽度", f"{self.current_info.get('width', 0)} px", copyable=True),
            self._create_info_row("高度", f"{self.current_info.get('height', 0)} px", copyable=True),
            self._create_info_row("宽高比", self.current_info.get('aspect_ratio_simplified', '-'), copyable=True),
        ]
        
        # 添加像素统计
        if 'total_pixels' in self.current_info:
            dimension_controls.append(
                self._create_info_row("总像素", f"{self.current_info.get('total_pixels', 0):,} 像素", copyable=True)
            )
        if 'megapixels' in self.current_info:
            dimension_controls.append(
                self._create_info_row("百万像素", f"{self.current_info.get('megapixels', 0)} MP", copyable=True)
            )
        
        dimension_controls.append(self._create_info_row("DPI", self.current_info.get('dpi', '未指定'), copyable=True))
        
        dimension_section = ft.Container(
            content=ft.Column(
                controls=dimension_controls,
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        self.info_column.controls.append(dimension_section)
        
        # 颜色信息部分
        color_controls = [
            self._create_section_title("颜色信息", ft.Icons.PALETTE),
            self._create_info_row("颜色模式", self.current_info.get('mode', '-'), copyable=True),
            self._create_info_row("模式描述", self.current_info.get('color_mode_description', '-'), copyable=True),
        ]
        
        # 添加位深度
        if 'bit_depth' in self.current_info:
            color_controls.append(
                self._create_info_row("位深度", f"{self.current_info.get('bit_depth', '-')} 位", copyable=True)
            )
        
        # 添加调色板信息（如果有）
        if 'palette_size' in self.current_info:
            color_controls.append(
                self._create_info_row("调色板大小", f"{self.current_info.get('palette_size', 0)} 色", copyable=True)
            )
        
        # 添加透明度信息
        if 'has_transparency' in self.current_info:
            transparency_text = "是" if self.current_info.get('has_transparency') else "否"
            color_controls.append(
                self._create_info_row("支持透明度", transparency_text, copyable=True)
            )
        
        # 添加ICC配置文件信息
        if 'has_icc_profile' in self.current_info:
            if self.current_info.get('has_icc_profile'):
                icc_size = format_file_size(self.current_info.get('icc_profile_size', 0))
                color_controls.append(
                    self._create_info_row("ICC配置文件", f"有 ({icc_size})", copyable=True)
                )
            else:
                color_controls.append(
                    self._create_info_row("ICC配置文件", "无")
                )
        
        # 添加色彩统计（如果有）
        if 'average_color' in self.current_info:
            avg_color = self.current_info['average_color']
            color_str = f"R:{avg_color['R']}, G:{avg_color['G']}, B:{avg_color['B']}"
            color_controls.append(
                self._create_info_row("平均颜色", color_str, copyable=True)
            )
        
        if 'average_brightness' in self.current_info:
            color_controls.append(
                self._create_info_row("平均亮度", f"{self.current_info.get('average_brightness', 0)}", copyable=True)
            )
        
        if 'std_deviation' in self.current_info:
            color_controls.append(
                self._create_info_row("标准差", f"{self.current_info.get('std_deviation', 0)}", copyable=True)
            )
        
        color_section = ft.Container(
            content=ft.Column(
                controls=color_controls,
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        self.info_column.controls.append(color_section)
        
        # 动画信息（如果是动画）
        if self.current_info.get('is_animated', False):
            animation_section = ft.Container(
                content=ft.Column(
                    controls=[
                        self._create_section_title("动画信息", ft.Icons.GIF_BOX),
                        self._create_info_row("是否动画", "是"),
                        self._create_info_row("帧数", str(self.current_info.get('n_frames', 1))),
                    ],
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            self.info_column.controls.append(animation_section)
        
        # 压缩和质量信息
        compression_controls = []
        has_compression_info = False
        
        if 'jpeg_quality' in self.current_info:
            if not compression_controls:
                compression_controls.append(self._create_section_title("压缩信息", ft.Icons.COMPRESS))
            compression_controls.append(
                self._create_info_row("JPEG质量", str(self.current_info.get('jpeg_quality')))
            )
            has_compression_info = True
        
        if 'progressive' in self.current_info:
            if not compression_controls:
                compression_controls.append(self._create_section_title("压缩信息", ft.Icons.COMPRESS))
            progressive_text = "是" if self.current_info.get('progressive') else "否"
            compression_controls.append(
                self._create_info_row("渐进式JPEG", progressive_text)
            )
            has_compression_info = True
        
        if 'interlaced' in self.current_info:
            if not compression_controls:
                compression_controls.append(self._create_section_title("压缩信息", ft.Icons.COMPRESS))
            interlaced_text = "是" if self.current_info.get('interlaced') else "否"
            compression_controls.append(
                self._create_info_row("交错PNG", interlaced_text)
            )
            has_compression_info = True
        
        if has_compression_info:
            compression_section = ft.Container(
                content=ft.Column(
                    controls=compression_controls,
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            self.info_column.controls.append(compression_section)
        
        # 相机参数信息（如果有）
        camera_data = self.current_info.get('camera', {})
        if camera_data:
            camera_controls = [self._create_section_title("拍摄参数", ft.Icons.CAMERA_ALT)]
            
            for label, value in camera_data.items():
                camera_controls.append(
                    self._create_info_row(label, value, copyable=True)
                )
            
            camera_section = ft.Container(
                content=ft.Column(
                    controls=camera_controls,
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            self.info_column.controls.append(camera_section)
        
        # GPS信息（如果有）
        if 'gps_coordinates' in self.current_info:
            gps_controls = [
                self._create_section_title("GPS信息", ft.Icons.LOCATION_ON),
                self._create_info_row("坐标", self.current_info.get('gps_coordinates', '-'), copyable=True),
                self._create_info_row("纬度", f"{self.current_info.get('gps_latitude', 0):.6f}"),
                self._create_info_row("经度", f"{self.current_info.get('gps_longitude', 0):.6f}"),
            ]
            
            gps_section = ft.Container(
                content=ft.Column(
                    controls=gps_controls,
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            self.info_column.controls.append(gps_section)
        
        # 文件哈希信息
        if 'md5' in self.current_info or 'sha256' in self.current_info:
            hash_controls = [self._create_section_title("文件哈希", ft.Icons.FINGERPRINT)]
            
            if 'md5' in self.current_info:
                hash_controls.append(
                    self._create_info_row("MD5", self.current_info.get('md5', '-'), copyable=True)
                )
            
            if 'sha256' in self.current_info:
                hash_controls.append(
                    self._create_info_row("SHA256", self.current_info.get('sha256', '-'), copyable=True)
                )
            
            hash_section = ft.Container(
                content=ft.Column(
                    controls=hash_controls,
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            self.info_column.controls.append(hash_section)
        
        # 文件时间信息
        time_section = ft.Container(
            content=ft.Column(
                controls=[
                    self._create_section_title("时间信息", ft.Icons.ACCESS_TIME),
                    self._create_info_row("创建时间", self.current_info.get('created_time', '-'), copyable=True),
                    self._create_info_row("修改时间", self.current_info.get('modified_time', '-'), copyable=True),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        self.info_column.controls.append(time_section)
        
        # EXIF 信息（如果有）
        exif_data = self.current_info.get('exif', {})
        if exif_data:
            exif_controls = [self._create_section_title("EXIF 信息", ft.Icons.CAMERA)]
            
            # 常见的 EXIF 标签优先显示
            priority_tags = [
                'Make', 'Model', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
                'ExposureTime', 'FNumber', 'ISO', 'ISOSpeedRatings', 'FocalLength',
                'Flash', 'WhiteBalance', 'MeteringMode', 'ExposureProgram',
                'LensModel', 'LensMake', 'Software', 'Artist', 'Copyright',
                'ImageDescription', 'Orientation', 'XResolution', 'YResolution',
                'ResolutionUnit', 'ColorSpace', 'ExifImageWidth', 'ExifImageHeight'
            ]
            
            # 先显示优先标签
            for tag in priority_tags:
                if tag in exif_data:
                    value = exif_data[tag]
                    # 处理特殊值
                    if isinstance(value, (tuple, list)) and len(value) == 2:
                        # 可能是分数格式
                        try:
                            if value[1] != 0:
                                value = f"{value[0]}/{value[1]}"
                            else:
                                value = str(value[0])
                        except:
                            value = str(value)
                    else:
                        value = str(value)
                    
                    exif_controls.append(
                        self._create_info_row(self._format_exif_tag(tag), value, copyable=True)
                    )
            
            # 显示其他标签
            other_tags = [tag for tag in exif_data.keys() if tag not in priority_tags]
            if other_tags:
                # 创建可折叠的其他 EXIF 信息
                other_exif_controls = []
                for tag in sorted(other_tags):
                    value = str(exif_data[tag])
                    # 限制值的长度
                    if len(value) > 100:
                        value = value[:100] + "..."
                    other_exif_controls.append(
                        self._create_info_row(self._format_exif_tag(tag), value, copyable=True)
                    )
                
                if other_exif_controls:
                    exif_controls.append(ft.Divider(height=1))
                    exif_controls.append(
                        ft.Text("其他 EXIF 信息", size=12, weight=ft.FontWeight.W_500, color=TEXT_SECONDARY)
                    )
                    exif_controls.extend(other_exif_controls)
            
            exif_section = ft.Container(
                content=ft.Column(
                    controls=exif_controls,
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_MEDIUM,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            self.info_column.controls.append(exif_section)
        
        self.info_column.update()
    
    def _create_section_title(self, title: str, icon: str) -> ft.Row:
        """创建分组标题。
        
        Args:
            title: 标题文本
            icon: 图标
        
        Returns:
            标题行控件
        """
        return ft.Row(
            controls=[
                ft.Icon(icon, size=20, color=ft.Colors.PRIMARY),
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_SMALL,
        )
    
    def _create_info_row(self, label: str, value: Any, copyable: bool = False) -> ft.Container:
        """创建信息行。
        
        Args:
            label: 标签文本
            value: 值文本
            copyable: 是否可复制
        
        Returns:
            信息行容器
        """
        value_str = str(value) if value is not None else '-'
        
        controls = [
            ft.Container(
                content=ft.Text(label, size=13, weight=ft.FontWeight.W_500, color=TEXT_SECONDARY),
                width=120,
            ),
            ft.Container(
                content=ft.Text(
                    value_str,
                    size=13,
                    color=TEXT_PRIMARY,
                    selectable=True,
                ),
                expand=True,
            ),
        ]
        
        if copyable:
            controls.append(
                ft.IconButton(
                    icon=ft.Icons.COPY,
                    icon_size=16,
                    tooltip="复制",
                    on_click=lambda e, v=value_str: self._copy_to_clipboard(v),
                )
            )
        
        return ft.Container(
            content=ft.Row(
                controls=controls,
                spacing=PADDING_SMALL,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.padding.symmetric(vertical=4),
        )
    
    def _format_exif_tag(self, tag: str) -> str:
        """格式化 EXIF 标签名称。
        
        Args:
            tag: 标签名
        
        Returns:
            格式化后的标签名
        """
        # 常见标签的中文翻译
        translations = {
            'Make': '制造商',
            'Model': '型号',
            'DateTime': '日期时间',
            'DateTimeOriginal': '拍摄时间',
            'DateTimeDigitized': '数字化时间',
            'ExposureTime': '曝光时间',
            'FNumber': '光圈',
            'ISO': 'ISO',
            'ISOSpeedRatings': 'ISO感光度',
            'FocalLength': '焦距',
            'Flash': '闪光灯',
            'WhiteBalance': '白平衡',
            'MeteringMode': '测光模式',
            'ExposureProgram': '曝光程序',
            'LensModel': '镜头型号',
            'LensMake': '镜头制造商',
            'Software': '软件',
            'Artist': '作者',
            'Copyright': '版权',
            'ImageDescription': '图片描述',
            'Orientation': '方向',
            'XResolution': 'X分辨率',
            'YResolution': 'Y分辨率',
            'ResolutionUnit': '分辨率单位',
            'ColorSpace': '色彩空间',
            'ExifImageWidth': 'EXIF图片宽度',
            'ExifImageHeight': 'EXIF图片高度',
        }
        return translations.get(tag, tag)
    
    def _copy_to_clipboard(self, text: str) -> None:
        """复制文本到剪贴板。
        
        Args:
            text: 要复制的文本
        """
        self.page.set_clipboard(text)
        self._show_message("已复制到剪贴板", ft.Colors.GREEN)
    
    def _copy_all_info(self, e: ft.ControlEvent) -> None:
        """复制全部信息到剪贴板。
        
        Args:
            e: 控件事件对象
        """
        if not self.current_info:
            self._show_message("没有可复制的信息", ft.Colors.ORANGE)
            return
        
        # 格式化所有信息为可读文本
        lines = []
        lines.append("=" * 60)
        lines.append("图片详细信息")
        lines.append("=" * 60)
        lines.append("")
        
        # 基本信息
        lines.append("【基本信息】")
        lines.append(f"  文件名: {self.current_info.get('filename', '-')}")
        lines.append(f"  文件路径: {self.current_info.get('filepath', '-')}")
        lines.append(f"  文件大小: {format_file_size(self.current_info.get('file_size', 0))}")
        lines.append(f"  格式: {self.current_info.get('format', '-')}")
        if self.current_info.get('format_description'):
            lines.append(f"  格式描述: {self.current_info.get('format_description')}")
        lines.append("")
        
        # 尺寸与像素信息
        lines.append("【尺寸与像素信息】")
        lines.append(f"  宽度: {self.current_info.get('width', 0)} px")
        lines.append(f"  高度: {self.current_info.get('height', 0)} px")
        lines.append(f"  宽高比: {self.current_info.get('aspect_ratio_simplified', '-')}")
        if 'total_pixels' in self.current_info:
            lines.append(f"  总像素: {self.current_info.get('total_pixels', 0):,} 像素")
        if 'megapixels' in self.current_info:
            lines.append(f"  百万像素: {self.current_info.get('megapixels', 0)} MP")
        lines.append(f"  DPI: {self.current_info.get('dpi', '未指定')}")
        lines.append("")
        
        # 颜色信息
        lines.append("【颜色信息】")
        lines.append(f"  颜色模式: {self.current_info.get('mode', '-')}")
        lines.append(f"  模式描述: {self.current_info.get('color_mode_description', '-')}")
        if 'bit_depth' in self.current_info:
            lines.append(f"  位深度: {self.current_info.get('bit_depth', '-')} 位")
        if 'palette_size' in self.current_info:
            lines.append(f"  调色板大小: {self.current_info.get('palette_size', 0)} 色")
        if 'has_transparency' in self.current_info:
            transparency = "是" if self.current_info.get('has_transparency') else "否"
            lines.append(f"  支持透明度: {transparency}")
        if 'has_icc_profile' in self.current_info:
            if self.current_info.get('has_icc_profile'):
                icc_size = format_file_size(self.current_info.get('icc_profile_size', 0))
                lines.append(f"  ICC配置文件: 有 ({icc_size})")
            else:
                lines.append(f"  ICC配置文件: 无")
        if 'average_color' in self.current_info:
            avg_color = self.current_info['average_color']
            lines.append(f"  平均颜色: R:{avg_color['R']}, G:{avg_color['G']}, B:{avg_color['B']}")
        if 'average_brightness' in self.current_info:
            lines.append(f"  平均亮度: {self.current_info.get('average_brightness', 0)}")
        if 'std_deviation' in self.current_info:
            lines.append(f"  标准差: {self.current_info.get('std_deviation', 0)}")
        lines.append("")
        
        # 动画信息
        if self.current_info.get('is_animated', False):
            lines.append("【动画信息】")
            lines.append(f"  是否动画: 是")
            lines.append(f"  帧数: {self.current_info.get('n_frames', 1)}")
            lines.append("")
        
        # 压缩信息
        has_compression = False
        compression_lines = []
        if 'jpeg_quality' in self.current_info:
            compression_lines.append(f"  JPEG质量: {self.current_info.get('jpeg_quality')}")
            has_compression = True
        if 'progressive' in self.current_info:
            progressive = "是" if self.current_info.get('progressive') else "否"
            compression_lines.append(f"  渐进式JPEG: {progressive}")
            has_compression = True
        if 'interlaced' in self.current_info:
            interlaced = "是" if self.current_info.get('interlaced') else "否"
            compression_lines.append(f"  交错PNG: {interlaced}")
            has_compression = True
        
        if has_compression:
            lines.append("【压缩信息】")
            lines.extend(compression_lines)
            lines.append("")
        
        # 拍摄参数
        camera_data = self.current_info.get('camera', {})
        if camera_data:
            lines.append("【拍摄参数】")
            for label, value in camera_data.items():
                lines.append(f"  {label}: {value}")
            lines.append("")
        
        # GPS信息
        if 'gps_coordinates' in self.current_info:
            lines.append("【GPS信息】")
            lines.append(f"  坐标: {self.current_info.get('gps_coordinates', '-')}")
            lines.append(f"  纬度: {self.current_info.get('gps_latitude', 0):.6f}")
            lines.append(f"  经度: {self.current_info.get('gps_longitude', 0):.6f}")
            lines.append("")
        
        # 文件哈希
        if 'md5' in self.current_info or 'sha256' in self.current_info:
            lines.append("【文件哈希】")
            if 'md5' in self.current_info:
                lines.append(f"  MD5: {self.current_info.get('md5', '-')}")
            if 'sha256' in self.current_info:
                lines.append(f"  SHA256: {self.current_info.get('sha256', '-')}")
            lines.append("")
        
        # 时间信息
        lines.append("【时间信息】")
        lines.append(f"  创建时间: {self.current_info.get('created_time', '-')}")
        lines.append(f"  修改时间: {self.current_info.get('modified_time', '-')}")
        lines.append("")
        
        # EXIF信息（只包含主要标签）
        exif_data = self.current_info.get('exif', {})
        if exif_data:
            lines.append("【EXIF 主要信息】")
            priority_tags = [
                'Make', 'Model', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
                'ExposureTime', 'FNumber', 'ISO', 'ISOSpeedRatings', 'FocalLength',
                'Flash', 'WhiteBalance', 'MeteringMode', 'ExposureProgram',
                'LensModel', 'LensMake', 'Software', 'Artist', 'Copyright'
            ]
            
            for tag in priority_tags:
                if tag in exif_data:
                    value = exif_data[tag]
                    if isinstance(value, (tuple, list)) and len(value) == 2:
                        try:
                            if value[1] != 0:
                                value = f"{value[0]}/{value[1]}"
                            else:
                                value = str(value[0])
                        except:
                            value = str(value)
                    else:
                        value = str(value)
                    
                    tag_name = self._format_exif_tag(tag)
                    lines.append(f"  {tag_name}: {value}")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append(f"导出时间: {self.current_info.get('modified_time', '-')}")
        lines.append("=" * 60)
        
        # 合并所有行并复制到剪贴板
        full_text = "\n".join(lines)
        self.page.set_clipboard(full_text)
        self._show_message("已复制全部信息到剪贴板", ft.Colors.GREEN)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if self.on_back:
            self.on_back()
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
            color: 背景颜色
        """
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()

