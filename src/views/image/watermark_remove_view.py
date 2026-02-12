# -*- coding: utf-8 -*-
"""图片去水印视图模块。

提供图片水印移除功能的用户界面。
"""

from pathlib import Path
from typing import Callable, List, Optional

import cv2
import flet as ft
import numpy as np

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_SUBTITLE_REMOVE_MODEL_KEY,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_LARGE,
    SUBTITLE_REMOVE_MODELS,
)
from services import ConfigService
from services.subtitle_remove_service import SubtitleRemoveService
from utils import format_file_size, logger, get_unique_path


class ImageWatermarkRemoveView(ft.Container):
    """图片去水印视图类。
    
    提供图片水印移除功能，包括：
    - 单文件/批量处理
    - 自定义遮罩区域
    - 实时进度显示
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', '.tiff'
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片去水印视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        self.is_processing: bool = False
        self.current_model_key: str = DEFAULT_SUBTITLE_REMOVE_MODEL_KEY
        self.file_regions: dict = {}  # 每个文件的区域设置 {file_path: [region_list]}
        
        # 处理模式: "ai" = AI修复, "mask" = 遮挡模式
        self.process_mode: str = self.config_service.get_config_value("image_watermark_process_mode", "ai")
        # 遮挡类型: "blur" = 模糊, "color" = 纯色
        self.mask_type: str = self.config_service.get_config_value("image_watermark_mask_type", "blur")
        # 遮挡颜色 (RGB)
        self.mask_color: str = self.config_service.get_config_value("image_watermark_mask_color", "#000000")
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 初始化服务
        model_dir = self.config_service.get_data_dir() / "models" / "subtitle_remove"
        self.remove_service: SubtitleRemoveService = SubtitleRemoveService()
        self.model_dir = model_dir
        
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
                ft.Text("图片去水印", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        # 初始化空状态
        self._init_empty_state()
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择图片:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=lambda _: self._on_select_files(),
                        ),
                        ft.Button(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda _: self._on_select_folder(),
                        ),
                        ft.TextButton(
                            "清空列表",
                            icon=ft.Icons.CLEAR_ALL,
                            on_click=lambda _: self._clear_files(),
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持 JPG、PNG、BMP、WebP 等常见图片格式",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=ft.padding.only(top=PADDING_SMALL),
                ),
                ft.Container(
                    content=self.file_list_view,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                    height=200,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 模型管理区域
        self.model_status_icon = ft.Icon(
            ft.Icons.HOURGLASS_EMPTY,
            size=20,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_status_text = ft.Text(
            "正在初始化...",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_download_btn = ft.Button(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            visible=False,
            on_click=lambda _: self._download_model(),
        )
        
        self.model_load_btn = ft.Button(
            "加载模型",
            icon=ft.Icons.PLAY_ARROW,
            visible=False,
            on_click=lambda _: self._load_model(),
        )
        
        self.model_unload_btn = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            visible=False,
            on_click=lambda _: self._unload_model(),
        )
        
        self.model_delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            visible=False,
            on_click=lambda _: self._delete_model(),
        )
        
        model_status_row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.model_download_btn,
                self.model_load_btn,
                self.model_unload_btn,
                self.model_delete_btn,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 模型信息
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        self.model_info_text = ft.Text(
            f"{model_info.quality} | {model_info.performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 自动加载模型选项
        auto_load_model = self.config_service.get_config_value("image_watermark_remove_auto_load_model", False)
        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        self.model_management_area = ft.Column(
            controls=[
                ft.Text("模型管理", size=14, weight=ft.FontWeight.W_500),
                model_status_row,
                self.model_info_text,
                self.auto_load_checkbox,
            ],
            spacing=PADDING_SMALL,
            visible=self.process_mode == "ai",
        )
        
        # 处理模式选择
        self.process_mode_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="ai", label="AI修复"),
                ft.Radio(value="mask", label="遮挡模式"),
            ], spacing=PADDING_MEDIUM),
            value=self.process_mode,
            on_change=self._on_process_mode_change,
        )
        
        # 遮挡类型选择
        self.mask_type_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="blur", label="模糊"),
                ft.Radio(value="color", label="纯色填充"),
            ], spacing=PADDING_MEDIUM),
            value=self.mask_type,
            on_change=self._on_mask_type_change,
        )
        
        # 颜色选择
        self.mask_color_btn = ft.Container(
            content=ft.Row([
                ft.Container(
                    width=24,
                    height=24,
                    bgcolor=self.mask_color,
                    border_radius=4,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                ),
                ft.Text("选择颜色", size=12),
            ], spacing=PADDING_SMALL),
            on_click=self._show_color_picker,
            ink=True,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4,
        )
        
        self.mask_options_row = ft.Row(
            controls=[
                ft.Text("遮挡方式:", size=13),
                self.mask_type_radio,
                self.mask_color_btn,
            ],
            spacing=PADDING_MEDIUM,
            visible=self.process_mode == "mask",
        )
        
        # 更新颜色按钮可见性
        self.mask_color_btn.visible = self.mask_type == "color"
        
        process_mode_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Text("处理模式:", size=14, weight=ft.FontWeight.W_500),
                        self.process_mode_radio,
                    ], spacing=PADDING_MEDIUM),
                    self.mask_options_row,
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 区域标注说明
        mask_settings_area = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        "默认去除底部25%区域，点击文件后的 [标注] 按钮可自定义区域",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        # 输出设置
        self.output_mode = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="same", label="输出到源文件目录"),
                ft.Radio(value="custom", label="自定义输出目录"),
            ]),
            value="same",
            on_change=lambda e: self._on_output_mode_change(),
        )
        
        # 使用配置服务的默认输出目录
        default_output_dir = str(self.config_service.get_output_dir())
        
        self.output_dir_field = ft.TextField(
            label="输出目录",
            value=default_output_dir,
            disabled=True,
            expand=True,
            read_only=True,
        )
        
        self.output_dir_btn = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="选择目录",
            disabled=True,
            on_click=lambda _: self._select_output_dir(),
        )
        
        output_settings_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode,
                    ft.Row(
                        controls=[
                            self.output_dir_field,
                            self.output_dir_btn,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 处理进度
        self.progress_text = ft.Text(
            "",
            size=14,
            weight=ft.FontWeight.W_500,
            visible=False,
        )
        
        self.progress_bar = ft.ProgressBar(
            value=0,
            visible=False,
        )
        
        # 开始处理按钮 - 与背景移除页面样式一致
        self.process_btn: ft.Container = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=24),
                        ft.Text("开始去水印", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=lambda _: self._start_processing(),
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                process_mode_area,
                self.model_management_area,
                mask_settings_area,
                output_settings_area,
                self.progress_text,
                self.progress_bar,
                ft.Container(
                    content=self.process_btn,
                    padding=ft.padding.only(top=PADDING_MEDIUM),
                ),
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        # 主布局
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
            expand=True,
        )
        
        # 检查模型状态
        self._check_model_status()
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.IMAGE_OUTLINED,
                            size=48,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "未选择文件",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "点击此处选择图片文件",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL // 2,
                ),
                height=168,
                alignment=ft.Alignment.CENTER,
                on_click=lambda _: self._on_select_files(),
                ink=True,
            )
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _on_process_mode_change(self, e: ft.ControlEvent) -> None:
        """处理模式变化事件。"""
        self.process_mode = e.control.value
        self.config_service.set_config_value("image_watermark_process_mode", self.process_mode)
        
        # 切换模式时更新UI
        is_ai_mode = self.process_mode == "ai"
        self.model_management_area.visible = is_ai_mode
        self.mask_options_row.visible = not is_ai_mode
        
        # 更新处理按钮状态
        self._update_process_button_state()
        self._page.update()
    
    def _on_mask_type_change(self, e: ft.ControlEvent) -> None:
        """遮挡类型变化事件。"""
        self.mask_type = e.control.value
        self.config_service.set_config_value("image_watermark_mask_type", self.mask_type)
        
        # 只有纯色模式才显示颜色选择
        self.mask_color_btn.visible = self.mask_type == "color"
        self._page.update()
    
    def _show_color_picker(self, e: ft.ControlEvent) -> None:
        """显示颜色选择器。"""
        def on_color_selected(color: str):
            self.mask_color = color
            self.config_service.set_config_value("image_watermark_mask_color", color)
            # 更新颜色预览
            self.mask_color_btn.content.controls[0].bgcolor = color
            self._page.close(dialog)
        
        # 预设颜色
        colors = [
            "#000000", "#FFFFFF", "#808080", "#C0C0C0",
            "#FF0000", "#00FF00", "#0000FF", "#FFFF00",
            "#FF00FF", "#00FFFF", "#FFA500", "#800080",
        ]
        
        color_grid = ft.GridView(
            runs_count=4,
            spacing=8,
            run_spacing=8,
            max_extent=50,
            controls=[
                ft.Container(
                    width=40,
                    height=40,
                    bgcolor=c,
                    border_radius=4,
                    border=ft.border.all(2, ft.Colors.OUTLINE if c != self.mask_color else ft.Colors.PRIMARY),
                    on_click=lambda e, color=c: on_color_selected(color),
                    ink=True,
                )
                for c in colors
            ],
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text("选择遮挡颜色"),
            content=ft.Container(
                content=color_grid,
                width=250,
                height=150,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self._close_dialog(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        """关闭对话框。"""
        self._page.close(dialog)
    
    async def _on_select_files(self) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "webp", "tiff", "tif"],
            allow_multiple=True,
        )
        if result:
            for f in result:
                file_path = Path(f.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
            self._check_model_status()
    
    async def _on_select_folder(self) -> None:
        """选择文件夹按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="选择包含图片的文件夹"
        )
        if folder_path:
            folder = Path(folder_path)
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
            for f in folder.iterdir():
                if f.is_file() and f.suffix.lower() in image_extensions:
                    if f not in self.selected_files:
                        self.selected_files.append(f)
            self._update_file_list()
            self._check_model_status()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if not self.selected_files:
            self._init_empty_state()
            return
        
        self.file_list_view.controls.clear()
        
        for file_path in self.selected_files:
            # 获取文件大小
            try:
                file_size = format_file_size(file_path.stat().st_size)
            except Exception:
                file_size = "未知"
            
            # 检查是否有自定义区域
            has_region = str(file_path) in self.file_regions
            region_icon = ft.Icons.CHECK_CIRCLE if has_region else ft.Icons.RADIO_BUTTON_UNCHECKED
            region_color = ft.Colors.GREEN if has_region else ft.Colors.ON_SURFACE_VARIANT
            
            file_row = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.IMAGE, size=20, color=ft.Colors.PRIMARY),
                    ft.Text(
                        file_path.name,
                        size=13,
                        expand=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        file_size,
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Icon(region_icon, size=16, color=region_color, tooltip="区域标注状态"),
                    ft.TextButton(
                        "标注",
                        on_click=lambda _, p=file_path: self._open_region_editor(p),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=16,
                        tooltip="移除",
                        on_click=lambda _, p=file_path: self._remove_file(p),
                    ),
                ],
                spacing=PADDING_SMALL,
            )
            self.file_list_view.controls.append(file_row)
        
        self._page.update()
    
    def _remove_file(self, file_path: Path) -> None:
        """从列表中移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            # 同时移除区域设置
            if str(file_path) in self.file_regions:
                del self.file_regions[str(file_path)]
        self._update_file_list()
        self._check_model_status()
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.file_regions.clear()
        self.selected_files.clear()
        self._update_file_list()
        self._check_model_status()
    
    def _read_image_unicode(self, image_path: Path) -> Optional[np.ndarray]:
        """读取图像，支持Unicode/中文路径。
        
        Args:
            image_path: 图像路径
        
        Returns:
            图像数组，如果读取失败返回None
        """
        try:
            # 使用 numpy 和 cv2.imdecode 来支持中文路径
            # cv2.imread 在 Windows 上不支持 Unicode 路径
            if not image_path.exists():
                logger.error(f"文件不存在: {image_path}")
                return None
            
            # 读取文件为字节流
            with open(image_path, 'rb') as f:
                file_data = f.read()
            
            # 转换为numpy数组
            file_array = np.frombuffer(file_data, dtype=np.uint8)
            
            # 使用cv2.imdecode解码图像
            image = cv2.imdecode(file_array, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.error(f"无法解码图像: {image_path}")
                return None
            
            return image
            
        except Exception as e:
            logger.error(f"读取图像失败: {image_path}, 错误: {e}")
            return None
    
    def _save_image_unicode(self, image: np.ndarray, output_path: Path) -> bool:
        """保存图像，支持Unicode/中文路径。
        
        Args:
            image: 图像数组
            output_path: 输出路径
        
        Returns:
            是否保存成功
        """
        try:
            # 根据文件扩展名选择编码格式
            ext = output_path.suffix.lower()
            if ext in ['.jpg', '.jpeg']:
                encode_ext = '.jpg'
            elif ext == '.png':
                encode_ext = '.png'
            elif ext == '.webp':
                encode_ext = '.webp'
            elif ext == '.bmp':
                encode_ext = '.bmp'
            else:
                encode_ext = '.png'  # 默认使用PNG
            
            # 使用 cv2.imencode 编码图像
            is_success, buffer = cv2.imencode(encode_ext, image)
            if not is_success:
                logger.error(f"编码图像失败: {output_path}")
                return False
            
            # 写入文件
            with open(output_path, 'wb') as f:
                f.write(buffer)
            
            return True
            
        except Exception as e:
            logger.error(f"保存图像失败: {output_path}, 错误: {e}")
            return False
    
    def _open_region_editor(self, file_path: Path) -> None:
        """打开可视化区域编辑器。"""
        import uuid
        
        # 读取图片（支持中文路径）
        img = self._read_image_unicode(file_path)
        if img is None:
            self._show_snackbar(f"无法读取图片: {file_path.name}")
            return
        img_height, img_width = img.shape[:2]
        
        # 临时文件目录
        temp_dir = self.config_service.get_temp_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)
        session_id = str(uuid.uuid4())[:8]
        
        # 根据页面大小计算预览尺寸
        page_width = self._page.width or 1000
        page_height = self._page.height or 700
        
        # 对话框可用高度（预留标题、按钮、底部间距）
        available_height = page_height - 200
        available_height = max(available_height, 350)
        
        # 图片预览最大尺寸
        max_img_width = min(page_width - 380, 700)
        max_img_height = available_height - 60  # 留出状态栏和底部间距
        
        # 按比例缩放图片
        scale_w = max_img_width / img_width
        scale_h = max_img_height / img_height
        scale = min(scale_w, scale_h, 1.0)
        
        display_width = int(img_width * scale)
        display_height = int(img_height * scale)
        
        # 确保最小尺寸
        display_width = max(display_width, 200)
        display_height = max(display_height, 150)
        
        # 预览图路径
        preview_path = temp_dir / f"region_preview_{session_id}.jpg"
        
        # 获取已有区域列表
        existing_regions = self.file_regions.get(str(file_path), [])
        regions_list = [r.copy() for r in existing_regions]
        
        # 状态变量
        current_image = [img.copy()]
        update_counter = [0]
        
        def save_preview_with_regions():
            """保存带区域标注的预览图，返回新路径"""
            update_counter[0] += 1
            new_path = temp_dir / f"region_preview_{session_id}_{update_counter[0]}.jpg"
            
            preview_img = current_image[0].copy()
            
            # 绘制已有区域（绿色，加粗）
            for r in regions_list:
                cv2.rectangle(preview_img, 
                    (r['left'], r['top']), 
                    (r['right'], r['bottom']), 
                    (0, 255, 0), 3)
                # 半透明填充
                overlay = preview_img.copy()
                cv2.rectangle(overlay, (r['left'], r['top']), (r['right'], r['bottom']), (0, 255, 0), -1)
                cv2.addWeighted(overlay, 0.2, preview_img, 0.8, 0, preview_img)
            
            # 缩放并保存
            img_resized = cv2.resize(preview_img, (display_width, display_height))
            cv2.imwrite(str(new_path), img_resized)
            return str(new_path)
        
        # 初始保存预览
        initial_preview = save_preview_with_regions()
        
        # 预览图控件
        preview_image = ft.Image(
            src=initial_preview,
            width=display_width,
            height=display_height,
            fit=ft.BoxFit.FILL,
        )
        
        # 选择框覆盖层（用于显示正在绘制的区域）
        selection_box = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.RED),
            border=ft.border.all(2, ft.Colors.RED),
            visible=False,
            top=0, left=0, width=0, height=0,
        )
        
        # 区域列表显示
        regions_column = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO)
        
        status_text = ft.Text(
            f"在图片上拖动鼠标框选水印区域 | 尺寸: {img_width}x{img_height}",
            size=11, color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 绘制状态
        draw_state = {'start_x': 0, 'start_y': 0, 'end_x': 0, 'end_y': 0}
        
        def refresh_preview():
            """刷新预览图"""
            new_path = save_preview_with_regions()
            preview_image.src = new_path
        
        def update_regions_display():
            """更新区域列表显示"""
            regions_column.controls.clear()
            for i, r in enumerate(regions_list):
                regions_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(width=10, height=10, bgcolor=ft.Colors.GREEN, border_radius=2),
                                ft.Text(f"区域{i+1}: ({r['left']},{r['top']})-({r['right']},{r['bottom']})", 
                                        size=11, expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE, icon_size=14,
                                    tooltip="删除",
                                    on_click=lambda _, idx=i: delete_region(idx),
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=4,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=4,
                        margin=ft.margin.only(bottom=4),
                    )
                )
            if not regions_list:
                regions_column.controls.append(
                    ft.Text("拖动鼠标在图片上框选区域", size=11, 
                            color=ft.Colors.ON_SURFACE_VARIANT, italic=True)
                )
        
        def delete_region(idx):
            if 0 <= idx < len(regions_list):
                regions_list.pop(idx)
                refresh_preview()
                update_regions_display()
                status_text.value = f"已删除区域，剩余 {len(regions_list)} 个"
                self._page.update()
        
        def on_pan_start(e: ft.DragStartEvent):
            # 限制在有效范围内
            x = max(0, min(display_width, e.local_x))
            y = max(0, min(display_height, e.local_y))
            draw_state['start_x'] = x
            draw_state['start_y'] = y
            selection_box.left = x
            selection_box.top = y
            selection_box.width = 0
            selection_box.height = 0
            selection_box.visible = True
            self._page.update()
        
        def on_pan_update(e: ft.DragUpdateEvent):
            # 限制范围
            end_x = max(0, min(display_width, e.local_x))
            end_y = max(0, min(display_height, e.local_y))
            
            # 保存当前位置
            draw_state['end_x'] = end_x
            draw_state['end_y'] = end_y
            
            # 更新选择框
            selection_box.left = min(draw_state['start_x'], end_x)
            selection_box.top = min(draw_state['start_y'], end_y)
            selection_box.width = abs(end_x - draw_state['start_x'])
            selection_box.height = abs(end_y - draw_state['start_y'])
            self._page.update()
        
        def on_pan_end(e: ft.DragEndEvent):
            selection_box.visible = False
            
            # 使用保存的最后位置
            end_x = draw_state['end_x']
            end_y = draw_state['end_y']
            
            # 计算实际坐标（转换回原始尺寸）
            x1 = int(min(draw_state['start_x'], end_x) / scale)
            y1 = int(min(draw_state['start_y'], end_y) / scale)
            x2 = int(max(draw_state['start_x'], end_x) / scale)
            y2 = int(max(draw_state['start_y'], end_y) / scale)
            
            # 确保在边界内
            x1 = max(0, min(img_width, x1))
            x2 = max(0, min(img_width, x2))
            y1 = max(0, min(img_height, y1))
            y2 = max(0, min(img_height, y2))
            
            # 最小区域限制
            if x2 - x1 > 20 and y2 - y1 > 20:
                regions_list.append({
                    'left': x1, 'top': y1, 'right': x2, 'bottom': y2,
                    'height': img_height, 'width': img_width,
                })
                status_text.value = f"✓ 已添加区域{len(regions_list)}: ({x1},{y1})-({x2},{y2})"
                status_text.color = ft.Colors.GREEN
                refresh_preview()
                update_regions_display()
            else:
                status_text.value = "区域太小（至少20x20像素），请重新框选"
                status_text.color = ft.Colors.ORANGE
            
            self._page.update()
        
        # 手势检测器 + Stack（用于叠加选择框）
        preview_stack = ft.Stack(
            controls=[
                preview_image,
                selection_box,
            ],
            width=display_width,
            height=display_height,
        )
        
        gesture_detector = ft.GestureDetector(
            content=ft.Container(
                content=preview_stack,
                border=ft.border.all(2, ft.Colors.PRIMARY),
                border_radius=4,
            ),
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
        )
        
        def close_dialog(e):
            self._page.close(dialog)
        
        def on_confirm(e):
            if regions_list:
                self.file_regions[str(file_path)] = regions_list
            elif str(file_path) in self.file_regions:
                del self.file_regions[str(file_path)]
            
            self._page.close(dialog)
            self._update_file_list()
            logger.info(f"已保存 {file_path.name} 的 {len(regions_list)} 个区域")
        
        def on_apply_to_all(e):
            """应用到所有文件"""
            if not regions_list:
                status_text.value = "请先标注区域"
                status_text.color = ft.Colors.ORANGE
                self._page.update()
                return
            
            # 保存当前文件的区域
            self.file_regions[str(file_path)] = regions_list
            
            # 应用到所有其他文件
            applied_count = 0
            for other_file in self.selected_files:
                if other_file != file_path:
                    # 复制区域设置（需要深拷贝）
                    self.file_regions[str(other_file)] = [r.copy() for r in regions_list]
                    applied_count += 1
            
            self._page.close(dialog)
            self._update_file_list()
            self._show_snackbar(f"已将区域设置应用到所有 {applied_count + 1} 个文件", ft.Colors.GREEN)
            logger.info(f"已将 {len(regions_list)} 个区域应用到 {applied_count + 1} 个文件")
        
        def on_clear_all(e):
            regions_list.clear()
            refresh_preview()
            update_regions_display()
            status_text.value = "已清空所有区域"
            status_text.color = ft.Colors.ON_SURFACE_VARIANT
            self._page.update()
        
        # 初始化区域列表
        update_regions_display()
        
        # 左侧面板：图片预览
        left_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=gesture_detector,
                        alignment=ft.Alignment.CENTER,
                    ),
                    status_text,
                ],
                spacing=8,
            ),
            width=display_width + 20,
            padding=ft.padding.only(right=12),
        )
        
        # 右侧：已标注区域列表
        right_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Text("已标注区域", size=13, weight=ft.FontWeight.W_500),
                        ft.TextButton("清空", icon=ft.Icons.DELETE_SWEEP, 
                                      icon_color=ft.Colors.ERROR,
                                      on_click=on_clear_all),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=1),
                    ft.Container(
                        content=regions_column, 
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "提示：可标注多个水印区域",
                            size=10, 
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        padding=ft.padding.only(top=8),
                    ),
                ],
                spacing=4,
            ),
            width=260,
            padding=ft.padding.only(left=12),
            border=ft.border.only(left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )
        
        # 主布局：左右分栏
        main_content = ft.Row(
            controls=[left_panel, right_panel],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=0,
        )
        
        # 创建对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.CROP, size=20),
                ft.Text(f"标注水印区域", size=16, weight=ft.FontWeight.W_500),
                ft.Text(f" - {file_path.name}", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=8),
            content=ft.Container(
                content=main_content,
                width=display_width + 305,
                height=display_height + 100,  # 多留空间避免底部被遮挡
            ),
            actions=[
                ft.TextButton("取消", on_click=close_dialog),
                ft.OutlinedButton(
                    "应用到所有文件", 
                    icon=ft.Icons.COPY_ALL, 
                    on_click=on_apply_to_all,
                    tooltip="将当前区域设置应用到列表中所有文件",
                ),
                ft.Button("保存", icon=ft.Icons.SAVE, on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.open(dialog)
    
    def _show_snackbar(self, message: str, color: str = None) -> None:
        """显示 snackbar 提示。"""
        snackbar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        self._page.open(snackbar)
    
    def _on_output_mode_change(self) -> None:
        """输出模式变化事件。"""
        is_custom = self.output_mode.value == "custom"
        self.output_dir_field.disabled = not is_custom
        self.output_dir_btn.disabled = not is_custom
        self._page.update()
    
    async def _select_output_dir(self) -> None:
        """选择输出目录。"""
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="选择输出目录"
        )
        if folder_path:
            self.output_dir_field.value = folder_path
            self._page.update()
    
    def _check_model_status(self) -> None:
        """检查模型状态。"""
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        
        # 检查模型文件是否存在
        encoder_path = self.model_dir / model_info.encoder_filename
        infer_path = self.model_dir / model_info.infer_filename
        decoder_path = self.model_dir / model_info.decoder_filename
        
        all_exist = all([
            encoder_path.exists(),
            infer_path.exists(),
            decoder_path.exists()
        ])
        
        if not all_exist:
            # 模型未下载
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"模型未下载 ({model_info.size_mb}MB)"
            self.model_status_text.color = ft.Colors.ERROR
            self.model_download_btn.visible = True
            self.model_load_btn.visible = False
            self.model_unload_btn.visible = False
            self.model_delete_btn.visible = False
        elif self.remove_service.is_model_loaded():
            # 模型已加载
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = "模型已加载"
            self.model_status_text.color = ft.Colors.GREEN
            self.model_download_btn.visible = False
            self.model_load_btn.visible = False
            self.model_unload_btn.visible = True
            self.model_delete_btn.visible = True
        else:
            # 模型已下载，未加载
            self.model_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.model_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
            self.model_status_text.value = "模型已下载，未加载"
            self.model_status_text.color = ft.Colors.ON_SURFACE_VARIANT
            self.model_download_btn.visible = False
            self.model_load_btn.visible = True
            self.model_unload_btn.visible = False
            self.model_delete_btn.visible = True
            
            # 检查是否启用自动加载
            if self.auto_load_checkbox.value:
                self._page.update()
                self._try_auto_load_model()
                return
        
        # 更新处理按钮状态
        self._update_process_button_state()
        
        self._page.update()
    
    def _update_process_button_state(self) -> None:
        """更新处理按钮状态。"""
        has_files = len(self.selected_files) > 0
        
        if self.process_mode == "mask":
            # 遮挡模式不需要模型
            self.process_btn.content.disabled = not has_files
        else:
            # AI模式需要模型已加载
            model_loaded = self.remove_service.is_model_loaded()
            self.process_btn.content.disabled = not (model_loaded and has_files)
    
    def _download_model(self) -> None:
        """下载模型。"""
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        
        # 创建模型目录
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # 确定需要下载的文件
        files_to_download = []
        encoder_path = self.model_dir / model_info.encoder_filename
        infer_path = self.model_dir / model_info.infer_filename
        decoder_path = self.model_dir / model_info.decoder_filename
        
        if not encoder_path.exists():
            files_to_download.append(("Encoder", model_info.encoder_url, encoder_path))
        if not infer_path.exists():
            files_to_download.append(("Infer", model_info.infer_url, infer_path))
        if not decoder_path.exists():
            files_to_download.append(("Decoder", model_info.decoder_url, decoder_path))
        
        if not files_to_download:
            logger.warning("模型文件已存在")
            self._check_model_status()
            return
        
        total_files = len(files_to_download)
        
        # 显示进度
        self.model_status_icon.name = ft.Icons.DOWNLOADING
        self.model_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
        self.model_status_text.value = f"正在下载 {total_files} 个文件..."
        self.model_status_text.color = ft.Colors.ON_SURFACE_VARIANT
        self.model_download_btn.disabled = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.visible = True
        self.progress_text.value = "准备下载..."
        self._page.update()
        
        async def _download_async():
            import asyncio
            self._download_finished = False
            self._pending_progress = None
            
            async def _poll():
                while not self._download_finished:
                    if self._pending_progress is not None:
                        text_val, bar_val = self._pending_progress
                        self.progress_text.value = text_val
                        if bar_val is not None:
                            self.progress_bar.value = bar_val
                        self._page.update()
                        self._pending_progress = None
                    await asyncio.sleep(0.3)
            
            def _do_download():
                import httpx
                
                for file_idx, (file_name, url, save_path) in enumerate(files_to_download):
                    self._pending_progress = (
                        f"正在下载 {file_name} ({file_idx + 1}/{total_files})...", None
                    )
                    
                    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(save_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    file_progress = downloaded / total_size
                                    overall_progress = (file_idx + file_progress) / total_files
                                    self._pending_progress = (
                                        f"正在下载 {file_name} ({file_idx + 1}/{total_files}): "
                                        f"{format_file_size(downloaded)} / {format_file_size(total_size)}",
                                        overall_progress
                                    )
            
            poll_task = asyncio.create_task(_poll())
            try:
                await asyncio.to_thread(_do_download)
            except Exception as e:
                logger.error(f"下载模型失败: {e}", exc_info=True)
                self.model_status_icon.name = ft.Icons.ERROR
                self.model_status_icon.color = ft.Colors.ERROR
                self.model_status_text.value = f"下载失败: {str(e)}"
                self.model_status_text.color = ft.Colors.ERROR
                self.progress_bar.visible = False
                self.progress_text.visible = False
                self.model_download_btn.disabled = False
                self._page.update()
                return
            finally:
                self._download_finished = True
                await poll_task
            
            # 下载完成
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self.model_download_btn.disabled = False
            self._check_model_status()
            
            # 如果启用自动加载，则加载模型
            if self.auto_load_checkbox.value:
                self._load_model()
        
        self._page.run_task(_download_async)
    
    def _load_model(self) -> None:
        """加载模型。"""
        async def _load_async():
            import asyncio
            await asyncio.sleep(0.3)

            model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
            
            # 更新状态
            self.model_status_text.value = "正在加载模型..."
            self.model_load_btn.disabled = True
            self._page.update()
            
            def _do_load():
                encoder_path = self.model_dir / model_info.encoder_filename
                infer_path = self.model_dir / model_info.infer_filename
                decoder_path = self.model_dir / model_info.decoder_filename

                self.remove_service.load_model(
                    str(encoder_path),
                    str(infer_path),
                    str(decoder_path),
                    neighbor_stride=model_info.neighbor_stride,
                    ref_length=model_info.ref_length
                )

            try:
                await asyncio.to_thread(_do_load)
                # 更新状态
                self._check_model_status()
            except Exception as e:
                logger.error(f"加载模型失败: {e}")
                self.model_status_text.value = f"加载失败: {str(e)}"
                self.model_status_text.color = ft.Colors.ERROR
                self.model_load_btn.disabled = False
                self._page.update()
        
        self._page.run_task(_load_async)
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型复选框变化事件。"""
        auto_load = self.auto_load_checkbox.value
        self.config_service.set_config_value("image_watermark_remove_auto_load_model", auto_load)
        
        # 如果启用自动加载，尝试加载模型
        if auto_load:
            self._try_auto_load_model()
    
    def _try_auto_load_model(self) -> None:
        """尝试自动加载已下载的模型。"""
        if self.remove_service.is_model_loaded():
            return
        
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        
        # 检查模型文件是否都存在
        encoder_path = self.model_dir / model_info.encoder_filename
        infer_path = self.model_dir / model_info.infer_filename
        decoder_path = self.model_dir / model_info.decoder_filename
        
        all_exist = all([
            encoder_path.exists(),
            infer_path.exists(),
            decoder_path.exists()
        ])
        
        if not all_exist:
            return
        
        # 自动加载模型
        self._load_model()
    
    def _unload_model(self) -> None:
        """卸载模型。"""
        self.remove_service.unload_model()
        self._check_model_status()
    
    def _delete_model(self) -> None:
        """删除模型文件。"""
        async def _delete_async():
            import asyncio
            
            def _do_delete():
                model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
                
                encoder_path = self.model_dir / model_info.encoder_filename
                infer_path = self.model_dir / model_info.infer_filename
                decoder_path = self.model_dir / model_info.decoder_filename
                
                # 先卸载模型
                if self.remove_service.is_model_loaded():
                    self.remove_service.unload_model()
                
                # 删除文件
                for path in [encoder_path, infer_path, decoder_path]:
                    if path.exists():
                        path.unlink()
                        logger.info(f"已删除: {path}")
            
            try:
                await asyncio.to_thread(_do_delete)
                self._check_model_status()
            except Exception as e:
                logger.error(f"删除模型失败: {e}")
                self.model_status_text.value = f"删除失败: {str(e)}"
                self.model_status_text.color = ft.Colors.ERROR
                self._page.update()
        
        self._page.run_task(_delete_async)
    
    def _create_mask(self, height: int, width: int, file_path: Optional[Path] = None) -> np.ndarray:
        """创建遮罩。
        
        Args:
            height: 图片高度
            width: 图片宽度
            file_path: 文件路径（用于获取特定文件的区域设置）
        
        Returns:
            遮罩数组
        """
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # 检查是否有该文件的自定义区域列表
        regions = []
        if file_path and str(file_path) in self.file_regions:
            regions = self.file_regions[str(file_path)]
        
        if regions:
            # 使用文件特定的区域设置
            for region in regions:
                # 如果图片尺寸与标注时不同，需要缩放
                if region.get('height', height) != height or region.get('width', width) != width:
                    scale_h = height / region.get('height', height)
                    scale_w = width / region.get('width', width)
                    
                    top = int(region['top'] * scale_h)
                    bottom = int(region['bottom'] * scale_h)
                    left = int(region['left'] * scale_w)
                    right = int(region['right'] * scale_w)
                else:
                    top = region['top']
                    bottom = region['bottom']
                    left = region['left']
                    right = region['right']
                
                # 确保边界有效
                top = max(0, min(height - 1, top))
                bottom = max(0, min(height, bottom))
                left = max(0, min(width - 1, left))
                right = max(0, min(width, right))
                
                mask[top:bottom, left:right] = 255
        else:
            # 默认模式：底部25%区域
            top = int(height * 0.75)
            mask[top:height, :] = 255
        
        return mask
    
    def _process_single_image(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """处理单张图片。
        
        使用STTN模型需要多帧输入，这里将单张图片复制多份作为输入。
        
        Args:
            image: 输入图片 (H, W, 3)
            mask: 遮罩 (H, W)
        
        Returns:
            处理后的图片
        """
        height, width = image.shape[:2]
        
        # 获取需要修复的区域
        split_h = int(width * 3 / 16)
        mask_3d = mask[:, :, None]
        inpaint_area = self.remove_service.get_inpaint_area_by_mask(height, split_h, mask_3d)
        
        if not inpaint_area:
            return image
        
        result = image.copy()
        
        # 处理每个需要修复的区域
        for from_H, to_H in inpaint_area:
            # 提取并缩放区域
            image_crop = image[from_H:to_H, :, :]
            image_resize = cv2.resize(
                image_crop,
                (self.remove_service.model_input_width, self.remove_service.model_input_height)
            )
            
            # 复制多份作为输入（模型需要多帧）
            batch_size = 10
            frames = [image_resize.copy() for _ in range(batch_size)]
            
            # 使用模型修复
            comps = self.remove_service.inpaint(frames)
            
            # 取中间帧的结果
            comp = comps[batch_size // 2]
            comp = cv2.resize(comp, (width, split_h))
            comp = cv2.cvtColor(np.array(comp).astype(np.uint8), cv2.COLOR_BGR2RGB)
            
            # 合成到原图
            mask_area = mask_3d[from_H:to_H, :]
            result[from_H:to_H, :, :] = (
                mask_area * comp +
                (1 - mask_area) * result[from_H:to_H, :, :]
            )
        
        return result
    
    def _process_single_image_mask(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """使用遮挡模式处理单张图片。
        
        Args:
            image: 输入图像 (BGR格式)
            mask: 遮罩数组
        
        Returns:
            处理后的图像
        """
        result = image.copy()
        height, width = image.shape[:2]
        
        if self.mask_type == "blur":
            # 模糊遮挡
            # 创建模糊版本的图像
            blur_strength = max(width, height) // 10  # 根据图片大小动态调整模糊强度
            blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1  # 必须是奇数
            blur_strength = max(21, blur_strength)  # 最小模糊强度
            blurred = cv2.GaussianBlur(image, (blur_strength, blur_strength), 0)
            
            # 使用遮罩合成
            mask_3d = mask[:, :, np.newaxis] / 255.0
            result = (mask_3d * blurred + (1 - mask_3d) * result).astype(np.uint8)
        else:
            # 纯色填充
            # 解析颜色
            color_hex = self.mask_color.lstrip('#')
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
            
            # 创建纯色图层
            color_layer = np.zeros_like(image)
            color_layer[:, :] = (b, g, r)  # OpenCV使用BGR格式
            
            # 使用遮罩合成
            mask_3d = mask[:, :, np.newaxis] / 255.0
            result = (mask_3d * color_layer + (1 - mask_3d) * result).astype(np.uint8)
        
        return result
    
    def _start_processing(self) -> None:
        """开始处理。"""
        if self.is_processing or not self.selected_files:
            return
        
        # 检查输出目录
        output_dir = None
        if self.output_mode.value == "custom":
            if not self.output_dir_field.value:
                logger.warning("请选择输出目录")
                return
            output_dir = Path(self.output_dir_field.value)
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
        
        self.is_processing = True
        self.process_btn.content.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self._page.update()
        
        async def _process_async():
            import asyncio
            self._process_finished = False
            self._pending_progress = None
            
            async def _poll():
                while not self._process_finished:
                    if self._pending_progress is not None:
                        text_val, bar_val = self._pending_progress
                        self.progress_text.value = text_val
                        if bar_val is not None:
                            self.progress_bar.value = bar_val
                        self._page.update()
                        self._pending_progress = None
                    await asyncio.sleep(0.3)
            
            def _do_process():
                total = len(self.selected_files)
                success_count = 0
                oom_error_count = 0
                
                for idx, file_path in enumerate(self.selected_files):
                    try:
                        # 更新进度
                        self._pending_progress = (
                            f"处理中: {file_path.name} ({idx + 1}/{total})",
                            idx / total
                        )
                        
                        # 读取图片（支持中文路径）
                        image = self._read_image_unicode(file_path)
                        if image is None:
                            continue
                        
                        height, width = image.shape[:2]
                        
                        # 创建遮罩
                        mask = self._create_mask(height, width, file_path)
                        
                        # 根据模式处理图片
                        if self.process_mode == "mask":
                            result = self._process_single_image_mask(image, mask)
                        else:
                            result = self._process_single_image(image, mask)
                        
                        # 确定输出路径
                        if output_dir:
                            output_path = output_dir / f"{file_path.stem}_no_watermark{file_path.suffix}"
                        else:
                            output_path = file_path.parent / f"{file_path.stem}_no_watermark{file_path.suffix}"
                        
                        # 根据全局设置决定是否添加序号
                        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                        output_path = get_unique_path(output_path, add_sequence=add_sequence)
                        
                        # 保存结果（支持中文路径）
                        if self._save_image_unicode(result, output_path):
                            logger.info(f"已保存: {output_path}")
                            success_count += 1
                        else:
                            logger.error(f"保存失败: {output_path}")
                    
                    except Exception as ex:
                        error_msg = str(ex)
                        logger.error(f"处理失败 {file_path.name}: {error_msg}")
                        
                        # 检测显存不足错误
                        if any(keyword in error_msg.lower() for keyword in [
                            "available memory", "out of memory", "显存不足"
                        ]):
                            oom_error_count += 1
                            self._pending_progress = (
                                f"⚠️ GPU 显存不足: {file_path.name}", None
                            )
                
                return total, success_count, oom_error_count
            
            total = 0
            success_count = 0
            oom_error_count = 0
            
            poll_task = asyncio.create_task(_poll())
            try:
                total, success_count, oom_error_count = await asyncio.to_thread(_do_process)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"处理失败: {e}", exc_info=True)
                
                # 检测显存不足错误
                if any(keyword in error_msg.lower() for keyword in [
                    "available memory", "out of memory", "显存不足"
                ]):
                    self.progress_text.value = "⚠️ GPU 显存不足"
                    self._show_snackbar(
                        "GPU 显存不足！建议：降低显存限制、处理较小图片或关闭 GPU 加速",
                        ft.Colors.ORANGE
                    )
                else:
                    self.progress_text.value = f"处理失败: {error_msg}"
            finally:
                self._process_finished = True
                await poll_task
            
            # 处理完成 - 更新UI
            self.progress_text.value = f"处理完成，成功: {success_count}/{total}"
            self.progress_bar.value = 1.0
            
            # 显示结果提示
            if oom_error_count > 0:
                self._show_snackbar(
                    f"⚠️ {oom_error_count} 个文件因 GPU 显存不足处理失败！建议：降低显存限制或关闭 GPU 加速",
                    ft.Colors.ORANGE
                )
            elif success_count > 0:
                self._show_snackbar(f"处理完成! 成功处理 {success_count} 个文件", ft.Colors.GREEN)
            
            self.is_processing = False
            self.process_btn.content.disabled = False
            self._page.update()
        
        self._page.run_task(_process_async)

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
            self._check_model_status()  # 更新处理按钮状态
            self._show_snackbar(f"已添加 {added_count} 个文件")
        elif skipped_count > 0:
            self._show_snackbar("去水印工具不支持该格式")
        
        self._page.update()

    def cleanup(self) -> None:
        """清理视图资源，释放内存。
        
        在视图被销毁时调用，确保所有资源被正确释放。
        """
        import gc
        
        try:
            # 1. 卸载去水印模型
            if self.remove_service:
                self.remove_service.unload_model()
            
            # 2. 清空文件列表
            if self.selected_files:
                self.selected_files.clear()
            
            # 3. 清空区域数据
            if hasattr(self, 'mask_regions'):
                self.mask_regions.clear()
            
            # 4. 清除回调引用，打破循环引用
            self.on_back = None
            
            # 5. 清除 UI 内容
            self.content = None
            
            # 6. 强制垃圾回收
            gc.collect()
            
            logger.info("图片去水印视图资源已清理")
        except Exception as e:
            logger.warning(f"清理图片去水印视图资源时出错: {e}")
