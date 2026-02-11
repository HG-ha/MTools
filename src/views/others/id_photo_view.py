# -*- coding: utf-8 -*-
"""AI证件照视图模块。

提供AI证件照生成功能的用户界面。
"""

import gc
import threading
import uuid
from pathlib import Path
from typing import Optional, List, Callable, Tuple, TYPE_CHECKING, Dict

import cv2
import numpy as np
from PIL import Image
import flet as ft

from constants import (
    BACKGROUND_REMOVAL_MODELS,
    FACE_DETECTION_MODELS,
    BORDER_RADIUS_MEDIUM,
    DEFAULT_MODEL_KEY,
    DEFAULT_FACE_DETECTION_MODEL_KEY,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import IDPhotoService, IDPhotoParams, IDPhotoResult
from utils import logger, format_file_size, get_unique_path

if TYPE_CHECKING:
    from services.config_service import ConfigService


# 预设尺寸列表 (名称, 高度px, 宽度px)
PRESET_SIZES: List[tuple] = [
    ("一寸", 413, 295),
    ("二寸", 626, 413),
    ("小一寸", 378, 260),
    ("小二寸", 531, 413),
    ("大一寸", 567, 390),
    ("大二寸", 626, 413),
    ("五寸", 1499, 1050),
    ("教师资格证", 413, 295),
    ("国家公务员考试", 413, 295),
    ("初级会计考试", 413, 295),
    ("英语四六级考试", 192, 144),
    ("计算机等级考试", 567, 390),
    ("研究生考试", 709, 531),
    ("社保卡", 441, 358),
    ("电子驾驶证", 378, 260),
    ("美国签证", 600, 600),
    ("日本签证", 413, 295),
    ("韩国签证", 531, 413),
]

# 预设背景颜色
PRESET_COLORS: List[tuple] = [
    ("蓝色", (67, 142, 219)),
    ("白色", (255, 255, 255)),
    ("红色", (255, 0, 0)),
]


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """将 HEX 颜色转换为 RGB。"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class IDPhotoView(ft.Container):
    """AI证件照视图类。"""
    
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.heic', '.heif'}

    def __init__(
        self,
        page: ft.Page,
        config_service: Optional['ConfigService'] = None,
        on_back: Optional[Callable] = None
    ) -> None:
        super().__init__()
        self._page: ft.Page = page
        self.config_service = config_service
        self.on_back: Optional[Callable] = on_back
        
        # 服务实例
        self.id_photo_service = IDPhotoService(config_service)
        
        # 状态变量
        self.selected_files: List[Path] = []
        self.is_processing: bool = False
        self.is_model_loading: bool = False
        self.processing_results: Dict[str, IDPhotoResult] = {}  # 文件路径 -> 结果
        
        # 当前选择的背景移除模型
        saved_bg_model = DEFAULT_MODEL_KEY
        if config_service:
            saved_bg_model = config_service.get_config_value("id_photo_bg_model", DEFAULT_MODEL_KEY)
        self.current_bg_model_key: str = saved_bg_model
        
        # 设置容器属性
        self.expand = True
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        self._ui_built: bool = False
        
        # 待处理的拖放文件（UI构建完成前收到的文件）
        self._pending_files: List[Path] = []
        
        # 直接构建UI
        self._build_ui()
        self._ui_built = True
    
    def _get_model_path(self, model_type: str, model_key: str = None) -> Path:
        """获取模型文件路径。"""
        if self.config_service:
            data_dir = self.config_service.get_data_dir()
        else:
            from utils.file_utils import get_app_root
            data_dir = get_app_root() / "storage" / "data"
        
        if model_type == "background":
            key = model_key or self.current_bg_model_key
            model_info = BACKGROUND_REMOVAL_MODELS[key]
            return data_dir / "models" / "background_removal" / model_info.version / model_info.filename
        elif model_type == "face":
            model_info = FACE_DETECTION_MODELS[DEFAULT_FACE_DETECTION_MODEL_KEY]
            return data_dir / "models" / "face_detection" / model_info.version / model_info.filename
        else:
            raise ValueError(f"未知模型类型: {model_type}")
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # ==================== 顶部标题 ====================
        header = ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="返回", on_click=self._on_back_click),
                ft.Text("AI证件照", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # ==================== 文件选择区域 ====================
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,  # 确保 Column 填充父容器
        )
        
        file_select_area = ft.Column(
            controls=[
                    ft.Row(
                        controls=[
                            ft.Text("选择照片:", size=14, weight=ft.FontWeight.W_500),
                            ft.Button("选择文件", icon=ft.Icons.FILE_UPLOAD, on_click=self._on_select_files),
                            ft.Button("选择文件夹", icon=ft.Icons.FOLDER_OPEN, on_click=self._on_select_folder),
                            ft.TextButton("清空列表", icon=ft.Icons.CLEAR_ALL, on_click=self._on_clear_files),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持格式: JPG, PNG, WebP, BMP, TIFF, HEIC 等",
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
                    height=280,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_SMALL,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # ==================== 模型管理区域 ====================
        # 背景移除模型选择
        bg_model_options = []
        for key, model in BACKGROUND_REMOVAL_MODELS.items():
            size_text = f"{model.size_mb}MB" if model.size_mb < 100 else f"{model.size_mb}MB"
            option_text = f"{model.display_name}  |  {size_text}"
            bg_model_options.append(ft.dropdown.Option(key=key, text=option_text))
        
        self.bg_model_selector = ft.Dropdown(
            options=bg_model_options,
            value=self.current_bg_model_key,
            label="背景移除模型",
            hint_text="选择背景移除模型",
            on_select=self._on_bg_model_change,
            width=320,
            dense=True,
            text_size=13,
        )
        
        self.bg_model_info = ft.Text(
            f"质量: {BACKGROUND_REMOVAL_MODELS[self.current_bg_model_key].quality} | 性能: {BACKGROUND_REMOVAL_MODELS[self.current_bg_model_key].performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 背景模型状态
        self.bg_status_icon = ft.Icon(ft.Icons.HOURGLASS_EMPTY, size=20, color=ft.Colors.ON_SURFACE_VARIANT)
        self.bg_status_text = ft.Text("正在检查模型...", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.download_bg_btn = ft.Button("下载模型", icon=ft.Icons.DOWNLOAD, on_click=lambda _: self._start_download_model("background"), visible=False)
        self.load_bg_btn = ft.Button("加载模型", icon=ft.Icons.PLAY_ARROW, on_click=lambda _: self._on_load_model("background"), visible=False)
        self.unload_bg_btn = ft.IconButton(icon=ft.Icons.POWER_SETTINGS_NEW, icon_color=ft.Colors.ORANGE, tooltip="卸载模型", on_click=lambda _: self._on_unload_model("background"), visible=False)
        self.delete_bg_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED, tooltip="删除模型", on_click=lambda _: self._on_delete_model("background"), visible=False)
        
        bg_status_row = ft.Row(
            controls=[self.bg_status_icon, self.bg_status_text, self.download_bg_btn, self.load_bg_btn, self.unload_bg_btn, self.delete_bg_btn],
            spacing=PADDING_SMALL,
        )
        
        # 人脸检测模型
        face_info = FACE_DETECTION_MODELS[DEFAULT_FACE_DETECTION_MODEL_KEY]
        self.face_model_text = ft.Text(f"人脸检测模型: {face_info.display_name}", size=13)
        self.face_status_icon = ft.Icon(ft.Icons.HOURGLASS_EMPTY, size=20, color=ft.Colors.ON_SURFACE_VARIANT)
        self.face_status_text = ft.Text("正在检查模型...", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.download_face_btn = ft.Button(f"下载模型 ({face_info.size_mb}MB)", icon=ft.Icons.DOWNLOAD, on_click=lambda _: self._start_download_model("face"), visible=False)
        self.load_face_btn = ft.Button("加载模型", icon=ft.Icons.PLAY_ARROW, on_click=lambda _: self._on_load_model("face"), visible=False)
        self.unload_face_btn = ft.IconButton(icon=ft.Icons.POWER_SETTINGS_NEW, icon_color=ft.Colors.ORANGE, tooltip="卸载模型", on_click=lambda _: self._on_unload_model("face"), visible=False)
        self.delete_face_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED, tooltip="删除模型", on_click=lambda _: self._on_delete_model("face"), visible=False)
        
        face_status_row = ft.Row(
            controls=[self.face_status_icon, self.face_status_text, self.download_face_btn, self.load_face_btn, self.unload_face_btn, self.delete_face_btn],
            spacing=PADDING_SMALL,
        )
        
        # 自动加载选项
        auto_load = True
        if self.config_service:
            auto_load = self.config_service.get_config_value("id_photo_auto_load_model", True)
        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load,
            on_change=self._on_auto_load_change,
        )
        
        # 模型下载进度条（放在模型区域）
        self.model_download_progress = ft.ProgressBar(value=0, visible=False)
        self.model_download_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        model_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型管理:", size=14, weight=ft.FontWeight.W_500),
                    self.bg_model_selector,
                    self.bg_model_info,
                    bg_status_row,
                    ft.Container(height=4),
                    self.face_model_text,
                    face_status_row,
                    self.auto_load_checkbox,
                    self.model_download_progress,
                    self.model_download_text,
                ],
                spacing=4,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # ==================== 参数设置区域 ====================
        # 尺寸设置
        self.size_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="preset", label="预设尺寸"),
                    ft.Radio(value="custom", label="自定义尺寸"),
                    ft.Radio(value="only_matting", label="仅换底色"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="preset",
            on_change=self._on_size_mode_change,
        )
        
        self.preset_size_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(text=f"{name} ({w}×{h})", key=name) for name, h, w in PRESET_SIZES],
            value="一寸",
            dense=True,
            width=200,
            text_size=12,
        )
        
        self.custom_width = ft.TextField(label="宽(px)", value="295", width=90, dense=True, text_size=12)
        self.custom_height = ft.TextField(label="高(px)", value="413", width=90, dense=True, text_size=12)
        self.custom_size_row = ft.Row([self.custom_width, self.custom_height], spacing=PADDING_SMALL, visible=False)
        
        size_section = ft.Column(
            controls=[
                ft.Text("尺寸规格:", size=14, weight=ft.FontWeight.W_500),
                self.size_mode_radio,
                self.preset_size_dropdown,
                self.custom_size_row,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 背景设置
        self.bg_color_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="蓝色", label="蓝色"),
                    ft.Radio(value="白色", label="白色"),
                    ft.Radio(value="红色", label="红色"),
                    ft.Radio(value="custom", label="自定义"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="蓝色",
            on_change=self._on_bg_color_change,
        )
        
        self.custom_color_input = ft.TextField(label="HEX颜色", value="438edb", prefix="#", width=120, dense=True, text_size=12, visible=False)
        
        self.render_mode_dropdown = ft.Dropdown(
            label="渲染模式",
            options=[
                ft.dropdown.Option("solid", "纯色"),
                ft.dropdown.Option("gradient_up", "向上渐变"),
                ft.dropdown.Option("gradient_down", "向下渐变"),
            ],
            value="solid",
            dense=True,
            width=140,
            text_size=12,
        )
        
        bg_section = ft.Column(
            controls=[
                ft.Text("背景设置:", size=14, weight=ft.FontWeight.W_500),
                self.bg_color_radio,
                ft.Row([self.custom_color_input, self.render_mode_dropdown], spacing=PADDING_MEDIUM),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 美颜调整
        self.whitening_slider = ft.Slider(min=0, max=15, value=2, divisions=15, label="{value}", width=180)
        self.brightness_slider = ft.Slider(min=-5, max=25, value=0, divisions=30, label="{value}", width=180)
        
        beauty_subsection = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("美颜调整", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ft.Row([ft.Text("美白强度", size=12, width=60), self.whitening_slider], spacing=PADDING_SMALL),
                    ft.Row([ft.Text("亮度调整", size=12, width=60), self.brightness_slider], spacing=PADDING_SMALL),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 人脸矫正
        self.face_alignment_checkbox = ft.Checkbox(label="自动矫正人脸", value=False)
        
        # 输出选项
        self.layout_checkbox = ft.Checkbox(label="生成排版照", value=True, on_change=self._on_layout_checkbox_change)
        
        # 排版尺寸选择
        self.layout_size_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(text="六寸相纸 (1205×1795)", key="6inch"),
                ft.dropdown.Option(text="五寸相纸 (1051×1500)", key="5inch"),
                ft.dropdown.Option(text="A4纸 (2479×3508)", key="a4"),
            ],
            value="6inch",
            dense=True,
            width=180,
            text_size=12,
        )
        
        # KB限制选项
        self.kb_limit_checkbox = ft.Checkbox(label="限制文件大小", value=True, on_change=self._on_kb_limit_change)
        self.kb_value_field = ft.TextField(
            label="",
            value="50",
            width=70,
            dense=True,
            text_size=12,
            suffix="KB",
        )
        
        output_subsection = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    self.face_alignment_checkbox,
                    self.layout_checkbox,
                    ft.Row([ft.Text("　排版尺寸", size=12, width=68), self.layout_size_dropdown], spacing=PADDING_SMALL),
                    ft.Row([self.kb_limit_checkbox, self.kb_value_field], spacing=PADDING_SMALL),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        beauty_section = ft.Column(
            controls=[
                beauty_subsection,
                output_subsection,
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 参数设置区域布局
        settings_area = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(content=size_section, expand=True),
                    ft.Container(content=bg_section, expand=True),
                    ft.Container(content=beauty_section, expand=True),
                ],
                spacing=PADDING_LARGE,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # ==================== 输出选项 ====================
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="same", label="输出到同目录（添加后缀 _id）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="same",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_data_dir() / "id_photos") if self.config_service else "",
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        output_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[self.custom_output_dir, self.browse_output_button],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # ==================== 左右布局 ====================
        main_content = ft.Row(
            controls=[
                ft.Container(content=file_select_area, expand=3, height=340),
                ft.Container(content=model_area, expand=2, height=340),
            ],
            spacing=PADDING_LARGE,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # ==================== 进度和生成按钮 ====================
        self.progress_bar = ft.ProgressBar(value=0, visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        progress_container = ft.Container(
            content=ft.Column(
                controls=[self.progress_bar, self.progress_text],
                spacing=PADDING_SMALL // 2,
            ),
        )
        
        self.generate_button: ft.Container = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=24),
                        ft.Text("批量生成证件照", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_generate_click,
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # ==================== 组装界面 ====================
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                main_content,
                ft.Container(height=PADDING_MEDIUM),
                settings_area,
                ft.Container(height=PADDING_MEDIUM),
                output_area,
                ft.Container(height=PADDING_LARGE),
                progress_container,
                ft.Container(height=PADDING_MEDIUM),
                self.generate_button,
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
        
        # 初始化文件列表
        self._update_file_list()
    
    # ==================== 文件操作 ====================
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择人像照片",
            allowed_extensions=["jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "heic", "heif"],
            allow_multiple=True,
        )
        if result:
            for file in result:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
            self._update_generate_button()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择包含照片的文件夹")
        if folder_path:
            folder = Path(folder_path)
            for ext in ["jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "heic", "heif"]:
                for file_path in folder.glob(f"*.{ext}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                for file_path in folder.glob(f"*.{ext.upper()}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
            self._update_generate_button()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self.processing_results.clear()
        self._update_file_list()
        self._update_generate_button()
    
    def _on_remove_file(self, index: int) -> None:
        """移除单个文件。"""
        if 0 <= index < len(self.selected_files):
            file_path = self.selected_files.pop(index)
            # 同时删除处理结果
            if str(file_path) in self.processing_results:
                del self.processing_results[str(file_path)]
            self._update_file_list()
            self._update_generate_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("点击选择照片", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("支持选择多个文件或文件夹", size=12, color=ft.Colors.OUTLINE),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    height=260,  # 设置固定高度以填充区域
                    alignment=ft.Alignment.CENTER,
                    on_click=self._on_select_files,
                    ink=True,
                    border_radius=BORDER_RADIUS_MEDIUM,
                )
            )
        else:
            for idx, file_path in enumerate(self.selected_files):
                # 获取文件信息
                try:
                    file_size = file_path.stat().st_size
                    size_str = format_file_size(file_size)
                except:
                    size_str = "未知"
                
                # 检查是否已处理
                is_processed = str(file_path) in self.processing_results
                
                # 创建预览按钮（仅处理完成后显示）
                preview_btn = ft.IconButton(
                    icon=ft.Icons.PREVIEW,
                    icon_size=18,
                    tooltip="预览结果",
                    on_click=lambda e, fp=file_path: self._on_preview_result(fp),
                    visible=is_processed,
                )
                
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
                                ft.Icon(ft.Icons.PERSON, size=20, color=ft.Colors.PRIMARY),
                                # 文件信息
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
                                                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(size_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(file_path.suffix.upper(), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ],
                                            spacing=4,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                # 状态指示器
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE if is_processed else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                    size=20,
                                    color=ft.Colors.GREEN if is_processed else ft.Colors.OUTLINE,
                                ),
                                # 预览按钮
                                preview_btn,
                                # 删除按钮
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="移除",
                                    on_click=lambda e, i=idx: self._on_remove_file(i),
                                ),
                            ],
                            spacing=PADDING_SMALL,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_MEDIUM,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if idx % 2 == 0 else None,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.OUTLINE)),
                    )
                )
        
        try:
            self.file_list_view.update()
        except:
            pass
    
    def _on_preview_result(self, file_path: Path) -> None:
        """预览处理结果。"""
        result = self.processing_results.get(str(file_path))
        if not result:
            return
        
        # 创建预览对话框
        def close_dialog(e):
            dialog.open = False
            self._page.update()
        
        # 保存临时预览图
        if self.config_service:
            temp_dir = self.config_service.get_temp_dir()
        else:
            from utils.file_utils import get_app_root
            temp_dir = get_app_root() / "storage" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        session_id = str(uuid.uuid4())[:8]
        standard_path = temp_dir / f"preview_standard_{session_id}.png"
        hd_path = temp_dir / f"preview_hd_{session_id}.png"
        layout_path = temp_dir / f"preview_layout_{session_id}.png" if result.layout is not None else None
        
        # 使用 imencode 支持中文路径
        is_success, buffer = cv2.imencode('.png', result.standard)
        if is_success:
            with open(standard_path, 'wb') as f:
                f.write(buffer)
        
        is_success, buffer = cv2.imencode('.png', result.hd)
        if is_success:
            with open(hd_path, 'wb') as f:
                f.write(buffer)
        
        if layout_path:
            is_success, buffer = cv2.imencode('.png', result.layout)
            if is_success:
                with open(layout_path, 'wb') as f:
                    f.write(buffer)
        
        # 创建预览内容
        preview_content = ft.Column(
            controls=[
                ft.Text(f"预览: {file_path.name}", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=PADDING_SMALL),
                ft.Row(
                    controls=[
                        ft.Column([
                            ft.Text("标准照", size=12, weight=ft.FontWeight.W_500),
                            ft.Image(src=str(standard_path), width=170, height=220, fit=ft.BoxFit.CONTAIN, border_radius=6),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        ft.Column([
                            ft.Text("高清照", size=12, weight=ft.FontWeight.W_500),
                            ft.Image(src=str(hd_path), width=170, height=220, fit=ft.BoxFit.CONTAIN, border_radius=6),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    ],
                    spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=PADDING_SMALL),
                ft.Column([
                    ft.Text("排版照", size=12, weight=ft.FontWeight.W_500),
                    ft.Image(src=str(layout_path) if layout_path else "", width=380, height=240, fit=ft.BoxFit.CONTAIN, border_radius=6) if layout_path else ft.Text("未生成", color=ft.Colors.OUTLINE),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4) if layout_path else ft.Container(),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("证件照预览"),
            content=preview_content,
            actions=[
                ft.TextButton("关闭", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    # ==================== 模型管理 ====================
    
    def _check_model_status_async(self) -> None:
        import time
        time.sleep(0.05)
        self._check_model_status()
    
    def _check_model_status(self) -> None:
        """检查模型状态。"""
        bg_exists = self._get_model_path("background").exists()
        face_exists = self._get_model_path("face").exists()
        
        # 背景模型状态
        bg_loaded = self.id_photo_service.is_background_model_loaded()
        if bg_loaded:
            self.bg_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.bg_status_icon.color = ft.Colors.GREEN
            self.bg_status_text.value = "模型已加载"
            self.bg_status_text.color = ft.Colors.GREEN
            self.download_bg_btn.visible = False
            self.load_bg_btn.visible = False
            self.unload_bg_btn.visible = True
            self.delete_bg_btn.visible = False  # 加载时不显示删除按钮
        elif bg_exists:
            self.bg_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.bg_status_icon.color = ft.Colors.BLUE
            self.bg_status_text.value = "模型已下载，需加载"
            self.bg_status_text.color = ft.Colors.BLUE
            self.download_bg_btn.visible = False
            self.load_bg_btn.visible = True
            self.unload_bg_btn.visible = False
            self.delete_bg_btn.visible = True  # 已下载但未加载时可删除
        else:
            self.bg_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.bg_status_icon.color = ft.Colors.ORANGE
            self.bg_status_text.value = "需要下载模型"
            self.bg_status_text.color = ft.Colors.ORANGE
            self.download_bg_btn.visible = True
            self.load_bg_btn.visible = False
            self.unload_bg_btn.visible = False
            self.delete_bg_btn.visible = False  # 未下载时不显示删除按钮
        
        # 人脸模型状态
        face_loaded = self.id_photo_service.is_face_model_loaded()
        if face_loaded:
            self.face_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.face_status_icon.color = ft.Colors.GREEN
            self.face_status_text.value = "模型已加载"
            self.face_status_text.color = ft.Colors.GREEN
            self.download_face_btn.visible = False
            self.load_face_btn.visible = False
            self.unload_face_btn.visible = True
            self.delete_face_btn.visible = False  # 加载时不显示删除按钮
        elif face_exists:
            self.face_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.face_status_icon.color = ft.Colors.BLUE
            self.face_status_text.value = "模型已下载，需加载"
            self.face_status_text.color = ft.Colors.BLUE
            self.download_face_btn.visible = False
            self.load_face_btn.visible = True
            self.unload_face_btn.visible = False
            self.delete_face_btn.visible = True  # 已下载但未加载时可删除
        else:
            self.face_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.face_status_icon.color = ft.Colors.ORANGE
            self.face_status_text.value = "需要下载模型"
            self.face_status_text.color = ft.Colors.ORANGE
            self.download_face_btn.visible = True
            self.load_face_btn.visible = False
            self.unload_face_btn.visible = False
            self.delete_face_btn.visible = False  # 未下载时不显示删除按钮
        
        # 自动加载（分别检查每个模型，但要确保不在加载中）
        if self.auto_load_checkbox.value and not self.is_model_loading:
            need_load_bg = bg_exists and not bg_loaded
            need_load_face = face_exists and not face_loaded
            
            if need_load_bg and need_load_face:
                self._on_load_model("both")
            elif need_load_bg:
                self._on_load_model("background")
            elif need_load_face:
                self._on_load_model("face")
        
        self._update_generate_button()
        self._safe_update()
    
    def _on_bg_model_change(self, e: ft.ControlEvent) -> None:
        """背景模型选择变化。"""
        new_key = e.control.value
        if new_key == self.current_bg_model_key:
            return
        
        if self.id_photo_service.is_background_model_loaded():
            self.id_photo_service.unload_background_model()
        
        self.current_bg_model_key = new_key
        if self.config_service:
            self.config_service.set_config_value("id_photo_bg_model", new_key)
        
        # 更新模型信息
        model = BACKGROUND_REMOVAL_MODELS[new_key]
        self.bg_model_info.value = f"质量: {model.quality} | 性能: {model.performance}"
        
        self._check_model_status()
    
    def _start_download_model(self, model_type: str) -> None:
        """开始下载模型。"""
        if self.is_model_loading:
            return
        
        self.is_model_loading = True
        
        if model_type == "background":
            model_info = BACKGROUND_REMOVAL_MODELS[self.current_bg_model_key]
            model_path = self._get_model_path("background")
        else:
            model_info = FACE_DETECTION_MODELS[DEFAULT_FACE_DETECTION_MODEL_KEY]
            model_path = self._get_model_path("face")
        
        self.model_download_text.value = f"正在下载 {model_info.display_name}..."
        self.model_download_text.visible = True
        self.model_download_progress.visible = True
        self.model_download_progress.value = 0
        self._safe_update()
        
        def download_task():
            try:
                import httpx
                model_path.parent.mkdir(parents=True, exist_ok=True)
                
                with httpx.stream("GET", model_info.url, follow_redirects=True, timeout=120.0) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(model_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    self.model_download_progress.value = downloaded / total_size
                                    self.model_download_text.value = f"下载中: {downloaded / 1024 / 1024:.1f} / {total_size / 1024 / 1024:.1f} MB"
                                    self._safe_update()
                
                self.model_download_progress.visible = False
                self.model_download_text.visible = False
                self.is_model_loading = False
                self._show_snackbar(f"{model_info.display_name} 下载完成", ft.Colors.GREEN)
                
                # 如果启用自动加载，直接加载模型
                if self.auto_load_checkbox.value:
                    self._load_model_after_download(model_type)
                else:
                    self._check_model_status()
                
            except Exception as e:
                self.model_download_progress.visible = False
                self.model_download_text.visible = False
                self.is_model_loading = False
                self._show_snackbar(f"下载失败: {e}", ft.Colors.RED)
                self._check_model_status()
        
        threading.Thread(target=download_task, daemon=True).start()
    
    def _load_model_after_download(self, model_type: str) -> None:
        """下载完成后直接加载模型（在下载线程中调用）。"""
        self.model_download_text.value = "正在加载模型..."
        self.model_download_text.visible = True
        self._safe_update()
        
        try:
            if model_type == "background":
                bg_path = self._get_model_path("background")
                if bg_path.exists():
                    self.id_photo_service.load_background_model(self.current_bg_model_key)
            elif model_type == "face":
                face_path = self._get_model_path("face")
                if face_path.exists():
                    self.id_photo_service.load_face_model()
            
            self.model_download_text.visible = False
            self._show_snackbar("模型加载成功", ft.Colors.GREEN)
            self._check_model_status()
            
        except Exception as ex:
            self.model_download_text.visible = False
            self._show_snackbar(f"模型加载失败: {ex}", ft.Colors.RED)
            self._check_model_status()
    
    def _on_load_model(self, model_type: str, e: ft.ControlEvent = None) -> None:
        """加载模型。"""
        if self.is_model_loading:
            return
        
        self.is_model_loading = True
        self.model_download_text.value = "正在加载模型..."
        self.model_download_text.visible = True
        self._safe_update()
        
        def load_task():
            try:
                if model_type in ["background", "both"]:
                    bg_path = self._get_model_path("background")
                    if bg_path.exists() and not self.id_photo_service.is_background_model_loaded():
                        self.id_photo_service.load_background_model(self.current_bg_model_key)
                
                if model_type in ["face", "both"]:
                    face_path = self._get_model_path("face")
                    if face_path.exists() and not self.id_photo_service.is_face_model_loaded():
                        self.id_photo_service.load_face_model()
                
                self.is_model_loading = False
                self.model_download_text.visible = False
                self._show_snackbar("模型加载成功", ft.Colors.GREEN)
                self._check_model_status()
                
            except Exception as ex:
                self.is_model_loading = False
                self.model_download_text.visible = False
                self._show_snackbar(f"模型加载失败: {ex}", ft.Colors.RED)
                self._check_model_status()
        
        threading.Thread(target=load_task, daemon=True).start()
    
    def _on_unload_model(self, model_type: str, e: ft.ControlEvent = None) -> None:
        """卸载模型。"""
        if model_type == "background":
            self.id_photo_service.unload_background_model()
        elif model_type == "face":
            self.id_photo_service.unload_face_model()
        
        self._show_snackbar("模型已卸载", ft.Colors.GREEN)
        self._check_model_status()
    
    def _on_delete_model(self, model_type: str) -> None:
        """删除模型（带确认弹窗）。"""
        if model_type == "background":
            model_info = BACKGROUND_REMOVAL_MODELS[self.current_bg_model_key]
            model_name = model_info.display_name
        else:
            model_info = FACE_DETECTION_MODELS[DEFAULT_FACE_DETECTION_MODEL_KEY]
            model_name = model_info.display_name
        
        def close_dialog(e):
            dialog.open = False
            self._page.update()
        
        def confirm_delete(e):
            dialog.open = False
            self._page.update()
            self._do_delete_model(model_type)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要删除模型 {model_name} 吗？\n删除后需要重新下载才能使用。"),
            actions=[
                ft.TextButton("取消", on_click=close_dialog),
                ft.TextButton("删除", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    def _do_delete_model(self, model_type: str) -> None:
        """执行删除模型。"""
        try:
            # 先卸载模型
            if model_type == "background":
                if self.id_photo_service.is_background_model_loaded():
                    self.id_photo_service.unload_background_model()
                model_path = self._get_model_path("background")
            else:
                if self.id_photo_service.is_face_model_loaded():
                    self.id_photo_service.unload_face_model()
                model_path = self._get_model_path("face")
            
            # 删除文件
            if model_path.exists():
                model_path.unlink()
                self._show_snackbar("模型已删除", ft.Colors.GREEN)
            else:
                self._show_snackbar("模型文件不存在", ft.Colors.ORANGE)
            
            self._check_model_status()
        except Exception as ex:
            logger.error(f"删除模型失败: {ex}")
            self._show_snackbar(f"删除失败: {ex}", ft.Colors.RED)
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载选项变化。"""
        if self.config_service:
            self.config_service.set_config_value("id_photo_auto_load_model", e.control.value)
    
    # ==================== 参数变更 ====================
    
    def _on_size_mode_change(self, e: ft.ControlEvent) -> None:
        mode = e.control.value
        self.preset_size_dropdown.visible = (mode == "preset")
        self.custom_size_row.visible = (mode == "custom")
        self._safe_update()
    
    def _on_bg_color_change(self, e: ft.ControlEvent) -> None:
        self.custom_color_input.visible = (e.control.value == "custom")
        self._safe_update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化。"""
        mode = e.control.value
        is_custom = mode == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        self._safe_update()
    
    def _on_layout_checkbox_change(self, e: ft.ControlEvent) -> None:
        """排版照复选框变化，控制排版尺寸选择器的可见性。"""
        # 目前排版尺寸选择器始终可见，这里可以根据需要调整
        pass
    
    def _on_kb_limit_change(self, e: ft.ControlEvent) -> None:
        """KB限制复选框变化，控制KB输入框的启用状态。"""
        self.kb_value_field.disabled = not self.kb_limit_checkbox.value
        self._safe_update()
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            self.custom_output_dir.update()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        if self.on_back:
            self.on_back()
    
    # ==================== 生成证件照 ====================
    
    def _update_generate_button(self) -> None:
        """更新生成按钮状态。"""
        models_ready = (
            self.id_photo_service.is_background_model_loaded() and 
            self.id_photo_service.is_face_model_loaded()
        )
        self.generate_button.content.disabled = not (self.selected_files and models_ready)
        self._safe_update()
    
    def _get_params(self) -> Tuple[IDPhotoParams, Tuple[int, int, int], str]:
        """获取当前参数。"""
        size_mode = self.size_mode_radio.value
        if size_mode == "preset":
            preset_name = self.preset_size_dropdown.value
            name_only = preset_name.split(" ")[0] if " " in preset_name else preset_name
            size = next((h, w) for name, h, w in PRESET_SIZES if name == name_only)
        elif size_mode == "custom":
            try:
                width = int(self.custom_width.value)
                height = int(self.custom_height.value)
                size = (height, width)
            except ValueError:
                size = (413, 295)
        else:
            size = (413, 295)
        
        bg_color_name = self.bg_color_radio.value
        if bg_color_name == "custom":
            try:
                bg_color = hex_to_rgb(self.custom_color_input.value)
            except:
                bg_color = (67, 142, 219)
        else:
            bg_color = next((c for name, c in PRESET_COLORS if name == bg_color_name), (67, 142, 219))
        
        render_mode = self.render_mode_dropdown.value or "solid"
        
        params = IDPhotoParams(
            size=size,
            change_bg_only=(size_mode == "only_matting"),
            head_measure_ratio=0.2,
            head_height_ratio=0.45,
            head_top_range=(0.12, 0.10),
            whitening_strength=int(self.whitening_slider.value),
            brightness_strength=int(self.brightness_slider.value),
            face_alignment=self.face_alignment_checkbox.value,
        )
        
        return params, bg_color, render_mode
    
    def _get_output_path(self, input_file: Path, suffix: str) -> Path:
        """获取输出文件路径。"""
        output_mode = self.output_mode_radio.value
        
        if output_mode == "same":
            # 输出到同目录
            output_path = input_file.parent / f"{input_file.stem}_id{suffix}.png"
        else:
            # 自定义输出目录
            output_dir = Path(self.custom_output_dir.value)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{input_file.stem}_id{suffix}.png"
        
        # 根据全局设置决定是否添加序号
        add_sequence = self.config_service.get_config_value("output_add_sequence", False) if self.config_service else False
        return get_unique_path(output_path, add_sequence=add_sequence)
    
    def _on_generate_click(self, e: ft.ControlEvent) -> None:
        """批量生成证件照。"""
        if not self.selected_files or self.is_processing:
            return
        
        self.is_processing = True
        self.generate_button.content.disabled = True
        self.progress_text.value = "正在处理..."
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self._safe_update()
        
        params, bg_color, render_mode = self._get_params()
        generate_layout = self.layout_checkbox.value
        
        # 获取排版尺寸
        layout_size_map = {
            "6inch": (1205, 1795),  # 六寸相纸
            "5inch": (1051, 1500),  # 五寸相纸
            "a4": (2479, 3508),     # A4纸
        }
        layout_size = layout_size_map.get(self.layout_size_dropdown.value, (1205, 1795))
        
        def process_all_task():
            total_files = len(self.selected_files)
            success_count = 0
            failed_count = 0
            
            for idx, file_path in enumerate(self.selected_files):
                try:
                    # 更新进度
                    self.progress_bar.value = idx / total_files
                    self.progress_text.value = f"正在处理 ({idx + 1}/{total_files}): {file_path.name}"
                    self._safe_update()
                    
                    # 读取图片
                    if not file_path.exists():
                        raise ValueError(f"文件不存在: {file_path}")
                    
                    file_ext = file_path.suffix.lower()
                    if file_ext in ['.heic', '.heif']:
                        from PIL import Image as PILImage
                        pil_image = PILImage.open(file_path)
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')
                        image = np.array(pil_image)
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                    else:
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                        file_array = np.frombuffer(file_data, dtype=np.uint8)
                        image = cv2.imdecode(file_array, cv2.IMREAD_COLOR)
                    
                    if image is None:
                        raise ValueError("无法读取图片文件")
                    
                    # 处理
                    result = self.id_photo_service.process(
                        image=image,
                        params=params,
                        bg_color=bg_color,
                        render_mode=render_mode,
                        generate_layout=generate_layout,
                        layout_size=layout_size,
                        progress_callback=None,
                    )
                    
                    # 保存结果
                    standard_path = self._get_output_path(file_path, "_standard")
                    hd_path = self._get_output_path(file_path, "_hd")
                    
                    # 标准照：根据KB限制选项决定格式和压缩
                    if self.kb_limit_checkbox.value:
                        # 启用KB限制，压缩为JPEG
                        try:
                            target_kb = int(self.kb_value_field.value)
                            if target_kb <= 0:
                                target_kb = 48
                        except ValueError:
                            target_kb = 48
                        
                        standard_compressed = self.id_photo_service.compress_image_to_kb(result.standard, target_kb=target_kb)
                        # 对 JPG 路径也应用序号设置
                        jpg_path = standard_path.with_suffix('.jpg')
                        add_sequence = self.config_service.get_config_value("output_add_sequence", False) if self.config_service else False
                        jpg_path = get_unique_path(jpg_path, add_sequence=add_sequence)
                        with open(jpg_path, 'wb') as f:
                            f.write(standard_compressed)
                    else:
                        # 不限制KB，保存为PNG
                        is_success, buffer = cv2.imencode('.png', result.standard)
                        if is_success:
                            with open(standard_path, 'wb') as f:
                                f.write(buffer)
                    
                    # 高清照保存为PNG格式（无损）
                    is_success, buffer = cv2.imencode('.png', result.hd)
                    if is_success:
                        with open(hd_path, 'wb') as f:
                            f.write(buffer)
                    
                    if result.layout is not None:
                        layout_path = self._get_output_path(file_path, "_layout")
                        is_success, buffer = cv2.imencode('.png', result.layout)
                        if is_success:
                            with open(layout_path, 'wb') as f:
                                f.write(buffer)
                    
                    # 保存到结果字典
                    self.processing_results[str(file_path)] = result
                    success_count += 1
                    
                except Exception as ex:
                    logger.error(f"处理失败 {file_path.name}: {ex}")
                    failed_count += 1
            
            # 完成
            self.is_processing = False
            self.generate_button.content.disabled = False
            self.progress_bar.value = 1.0
            self.progress_text.value = f"处理完成！成功: {success_count}, 失败: {failed_count}"
            
            # 更新文件列表以显示预览按钮
            self._update_file_list()
            
            if success_count > 0:
                self._show_snackbar(f"成功生成 {success_count} 张证件照", ft.Colors.GREEN)
            if failed_count > 0:
                self._show_snackbar(f"{failed_count} 张照片处理失败", ft.Colors.ORANGE)
            
            self._safe_update()
        
        threading.Thread(target=process_all_task, daemon=True).start()
    
    # ==================== 工具方法 ====================
    
    def _safe_update(self) -> None:
        """安全更新UI。"""
        try:
            self.update()
        except:
            pass
    
    def _show_snackbar(self, message: str, color: str = None) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(content=ft.Text(message), bgcolor=color, duration=3000)
        self._page.overlay.append(snackbar)
        snackbar.open = True
        try:
            self._page.update()
        except:
            pass
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。"""
        # 如果UI尚未构建完成，保存文件待后续处理
        if not self._ui_built or not hasattr(self, 'file_list_view'):
            self._pending_files.extend(files)
            return
        
        added_count = 0
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                if path not in self.selected_files:
                    self.selected_files.append(path)
                    added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            self._update_generate_button()
            snackbar = ft.SnackBar(content=ft.Text(f"已添加 {added_count} 个文件"), bgcolor=ft.Colors.GREEN)
            self._page.overlay.append(snackbar)
            snackbar.open = True
        self._page.update()
    
    def _process_pending_files(self) -> None:
        """处理UI构建完成前收到的待处理文件。"""
        if not self._pending_files:
            return
        
        pending = self._pending_files.copy()
        self._pending_files.clear()
        
        added_count = 0
        all_files = []
        for path in pending:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                if path not in self.selected_files:
                    self.selected_files.append(path)
                    added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            self._update_generate_button()
            snackbar = ft.SnackBar(content=ft.Text(f"已添加 {added_count} 个文件"), bgcolor=ft.Colors.GREEN)
            self._page.overlay.append(snackbar)
            snackbar.open = True
        try:
            self._page.update()
        except:
            pass
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。
        
        在视图被销毁时调用，确保所有资源被正确释放。
        """
        import gc
        
        try:
            # 1. 卸载所有 AI 模型（背景移除 + 人脸检测）
            if self.id_photo_service:
                self.id_photo_service.unload_all_models()
            
            # 2. 清空文件列表
            if self.selected_files:
                self.selected_files.clear()
            
            # 3. 清空处理结果
            if hasattr(self, 'processed_results'):
                self.processed_results.clear()
            
            # 4. 清除回调引用，打破循环引用
            self.on_back = None
            
            # 5. 清除 UI 内容
            self.content = None
            
            # 6. 强制垃圾回收
            gc.collect()
            
            logger.info("AI证件照视图资源已清理")
        except Exception as e:
            logger.warning(f"清理AI证件照视图资源时出错: {e}")