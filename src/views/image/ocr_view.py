# -*- coding: utf-8 -*-
"""OCR视图模块。

提供图片文字识别功能的用户界面。
"""

import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import flet as ft
import numpy as np

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_OCR_MODEL_KEY,
    OCR_MODELS,
    OCRModelInfo,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, OCRService
from utils import format_file_size, logger, get_unique_path


class OCRView(ft.Container):
    """OCR视图类。
    
    提供图片文字识别功能，包括：
    - 图片选择（支持批量）
    - 模型选择和下载
    - 文字识别
    - 结果展示和导出
    - 快捷键截图识别
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化OCR视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.on_back: Optional[Callable] = on_back
        
        self.ocr_service: OCRService = OCRService(config_service)
        self.selected_files: List[Path] = []
        # 存储每个文件的OCR结果: {文件路径: 结果列表}
        self.ocr_results: Dict[str, List[Tuple[List, str, float]]] = {}
        self.is_processing: bool = False
        
        # 当前选择的模型
        saved_model_key = self.config_service.get_config_value("ocr_model_key", DEFAULT_OCR_MODEL_KEY)
        if saved_model_key not in OCR_MODELS:
            saved_model_key = DEFAULT_OCR_MODEL_KEY
        self.current_model_key: str = saved_model_key
        self.current_model: OCRModelInfo = OCR_MODELS[self.current_model_key]
        
        self.expand: bool = True
        # 与其他视图保持一致的 padding 设置
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
        # 顶部：标题和返回按钮（与其他视图保持一致，直接用 Row）
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("OCR 文字识别", size=28, weight=ft.FontWeight.BOLD),
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
                                "支持格式: JPG, PNG, WebP, BMP, TIFF 等",
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
                    height=280,  # 文件列表高度
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 模型设置区域
        model_options = []
        for key, model_info in OCR_MODELS.items():
            option_text = f"{model_info.display_name}  |  {model_info.size_mb}MB  |  {model_info.language_support}"
            model_options.append(
                ft.dropdown.Option(key=key, text=option_text)
            )
        
        self.model_dropdown = ft.Dropdown(
            label="选择模型",
            hint_text="选择OCR识别模型",
            options=model_options,
            value=self.current_model_key,
            on_select=self._on_model_change,
            width=600,
            dense=True,
            text_size=13,
        )
        
        # 模型信息
        self.model_info_text = ft.Text(
            f"{self.current_model.quality} | {self.current_model.performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 模型状态图标和文本
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
        
        # 下载模型按钮
        self.download_model_button = ft.Button(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_model,
            visible=False,
        )
        
        # 加载模型按钮
        self.load_model_button = ft.Button(
            "加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model,
            visible=False,
        )
        
        # 卸载模型按钮
        self.unload_model_button = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            on_click=self._on_unload_model,
            visible=False,
        )
        
        # 删除模型按钮
        self.delete_model_button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件（如果模型损坏，可删除后重新下载）",
            on_click=self._on_delete_model,
            visible=False,
        )
        
        model_status_row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.download_model_button,
                self.load_model_button,
                self.unload_model_button,
                self.delete_model_button,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 自动加载模型选项
        auto_load_model = self.config_service.get_config_value("ocr_auto_load_model", True)
        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        # GPU加速设置
        gpu_enabled = self.config_service.get_config_value("gpu_acceleration", True)
        self.gpu_checkbox = ft.Checkbox(
            label="启用 GPU 加速",
            value=gpu_enabled,
            on_change=self._on_gpu_change,
        )
        
        # 模型下载/加载进度显示（在模型区域内）
        self.model_progress_bar = ft.ProgressBar(visible=False)
        self.model_progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        model_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    self.model_dropdown,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                    ft.Row(
                        controls=[
                            self.auto_load_checkbox,
                            self.gpu_checkbox,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    # 模型操作进度条
                    self.model_progress_bar,
                    self.model_progress_text,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出设置区域
        # 输出格式选择（复选框）
        saved_formats = self.config_service.get_config_value("ocr_output_formats", ["txt", "json"])
        
        self.output_txt_checkbox = ft.Checkbox(
            label="TXT 文本文件",
            value="txt" in saved_formats,
            on_change=self._on_output_format_change,
        )
        
        self.output_json_checkbox = ft.Checkbox(
            label="JSON 结构化数据",
            value="json" in saved_formats,
            on_change=self._on_output_format_change,
        )
        
        # 输出可视化结果图
        output_image = self.config_service.get_config_value("ocr_output_image", False)
        self.output_image_checkbox = ft.Checkbox(
            label="识别结果图",
            value=output_image,
            on_change=self._on_output_image_change,
        )
        
        output_format_row = ft.Row(
            controls=[
                ft.Text("输出格式:", size=13, weight=ft.FontWeight.W_500),
                self.output_txt_checkbox,
                self.output_json_checkbox,
                self.output_image_checkbox,
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 输出模式
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="same", label="保存到原文件目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="same",
            on_change=self._on_output_mode_change,
        )
        
        # 文件后缀
        self.file_suffix = ft.TextField(
            label="文件后缀",
            value="_ocr",
            hint_text="例如: _ocr, _text, _result",
            width=200,
            dense=True,
        )
        
        # 输出目录
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
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
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    output_format_row,
                    ft.Container(height=PADDING_SMALL),
                    self.file_suffix,
                    ft.Container(height=PADDING_SMALL),
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
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        # 处理按钮区域 - 大号按钮样式
        self.recognize_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TEXT_FIELDS, size=24),
                        ft.Text("开始识别", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_recognize,
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
                ft.Container(
                    content=ft.Column(
                        controls=[
                            file_select_area,
                            ft.Container(height=PADDING_MEDIUM),
                            model_section,
                            ft.Container(height=PADDING_MEDIUM),
                            output_section,
                            ft.Container(height=PADDING_MEDIUM),
                            # 操作按钮区域
                            self.recognize_button,
                            ft.Container(height=PADDING_SMALL),
                            self.progress_bar,
                            self.progress_text,
                            ft.Container(height=PADDING_LARGE),  # 底部间距
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=ft.padding.only(
                        left=PADDING_MEDIUM,
                        right=PADDING_MEDIUM,
                        top=PADDING_SMALL,
                        bottom=PADDING_MEDIUM,
                    ),
                ),
            ],
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条，但仍可滚动
            expand=True,
        )
        
        # 组装主界面 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,  # 取消间距，让布局更紧凑
        )
        
        # 初始化模型状态
        self._init_model_status()
        
        # 如果设置了自动加载，尝试自动加载模型
        if auto_load_model:
            self._try_auto_load_model()
        
        # 初始化空文件列表状态
        self._init_empty_state()
    
    def _init_empty_state(self) -> None:
        """初始化空文件列表状态。"""
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
                            "点击此处选择图片",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                height=232,  # 280 - 2*24(padding) = 232
                alignment=ft.Alignment.CENTER,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    async def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        await self._on_select_files(e)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件事件。"""
        result = await ft.FilePicker().pick_files(
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"],
            dialog_title="选择图片",
            allow_multiple=True,
        )
        
        if result:
            for file in result:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择文件夹")
        
        if result:
            folder_path = Path(result)
            # 支持的图片格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
            
            # 遍历文件夹中的所有图片文件
            for ext in image_extensions:
                for file_path in folder_path.glob(f"*{ext}"):
                    if file_path.is_file() and file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                # 大写扩展名
                for file_path in folder_path.glob(f"*{ext.upper()}"):
                    if file_path.is_file() and file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            
            self._update_file_list()
    
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self.ocr_results.clear()
        self._update_file_list()
        self._page.update()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            # 空列表时显示可点击的占位区域
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
                                "点击此处选择图片",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_SMALL,
                    ),
                    height=232,  # 280 - 2*24(padding) = 232
                    alignment=ft.Alignment.CENTER,
                    on_click=self._on_empty_area_click,
                    ink=True,
                )
            )
            self.recognize_button.content.disabled = True
        else:
            for i, file_path in enumerate(self.selected_files):
                # 获取文件状态标识
                status_icon = ft.Icons.IMAGE
                status_color = ft.Colors.ON_SURFACE
                
                # 如果已经识别过，显示不同的图标
                if str(file_path) in self.ocr_results:
                    status_icon = ft.Icons.CHECK_CIRCLE
                    status_color = ft.Colors.GREEN
                
                file_row = ft.Row(
                    controls=[
                        ft.Icon(status_icon, size=20, color=status_color),
                        ft.Text(
                            f"{file_path.name}",
                            size=12,
                            expand=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_size=16,
                            tooltip="移除",
                            on_click=lambda e, idx=i: self._remove_file(idx),
                        ),
                    ],
                    spacing=PADDING_SMALL,
                )
                self.file_list_view.controls.append(file_row)
            
            self.recognize_button.content.disabled = False
        
        self._page.update()
    
    def _remove_file(self, index: int) -> None:
        """移除指定索引的文件。"""
        if 0 <= index < len(self.selected_files):
            file_path = self.selected_files[index]
            self.selected_files.pop(index)
            
            # 同时移除对应的OCR结果
            if str(file_path) in self.ocr_results:
                del self.ocr_results[str(file_path)]
            
            self._update_file_list()
    
    def _on_model_change(self, e: ft.ControlEvent) -> None:
        """模型选择改变事件。"""
        self.current_model_key = e.control.value
        self.current_model = OCR_MODELS[self.current_model_key]
        
        # 更新模型信息
        self.model_info_text.value = (
            f"质量: {self.current_model.quality} | "
            f"性能: {self.current_model.performance}"
        )
        
        # 保存配置
        self.config_service.set_config_value("ocr_model_key", self.current_model_key)
        self.config_service.save_config()
        
        # 重新检查模型状态
        self._check_model_status()
        
        self._page.update()
    
    def _check_all_model_files_exist(self) -> bool:
        """检查当前模型的所有文件是否存在。"""
        model_dir = self.ocr_service.get_model_dir(self.current_model_key)
        det_path = model_dir / self.current_model.det_filename
        rec_path = model_dir / self.current_model.rec_filename
        dict_path = model_dir / self.current_model.dict_filename
        
        return det_path.exists() and rec_path.exists() and dict_path.exists()
    
    def _init_model_status(self) -> None:
        """初始化模型状态显示。"""
        all_exist = self._check_all_model_files_exist()
        
        if all_exist:
            # 模型已下载
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已下载 ({self.current_model.size_mb}MB)"
            self.download_model_button.visible = False
            self.load_model_button.visible = True
            self.delete_model_button.visible = True
            self.unload_model_button.visible = False  # 只有加载后才显示
        else:
            # 模型未下载
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ORANGE
            self.model_status_text.value = "未下载"
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.delete_model_button.visible = False
            self.unload_model_button.visible = False
        
        try:
            self._page.update()
        except Exception:
            pass
    
    def _try_auto_load_model(self) -> None:
        """尝试自动加载模型。"""
        if not self._check_all_model_files_exist():
            return
        
        async def _auto_load_async():
            import asyncio
            await asyncio.sleep(0.3)
            
            def _do_load():
                def progress_callback(progress: float, message: str):
                    pass  # 自动加载时不显示进度
                
                use_gpu = self.gpu_checkbox.value
                return self.ocr_service.load_model(
                    self.current_model_key,
                    use_gpu=use_gpu,
                    progress_callback=progress_callback
                )
            
            success, message = await asyncio.to_thread(_do_load)
            
            if success:
                # 获取设备信息
                device_info = self.ocr_service.get_device_info()
                
                self.model_status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
                self.model_status_icon.color = ft.Colors.BLUE
                self.model_status_text.value = f"已加载 ({device_info})"
                self.load_model_button.visible = False
                self.unload_model_button.visible = True
                
                try:
                    self._page.update()
                except Exception:
                    pass
        
        self._page.run_task(_auto_load_async)
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载选项改变。"""
        self.config_service.set_config_value("ocr_auto_load_model", e.control.value)
        self.config_service.save_config()
    
    def _on_gpu_change(self, e: ft.ControlEvent) -> None:
        """GPU加速选项改变。"""
        self.config_service.set_config_value("gpu_acceleration", e.control.value)
        self.config_service.save_config()
    
    def _on_output_format_change(self, e: ft.ControlEvent) -> None:
        """输出格式选项改变。"""
        # 获取当前选中的格式
        selected_formats = []
        if self.output_txt_checkbox.value:
            selected_formats.append("txt")
        if self.output_json_checkbox.value:
            selected_formats.append("json")
        
        # 至少选择一种格式（如果没有勾选图片输出的话）
        if not selected_formats and not self.output_image_checkbox.value:
            # 如果用户取消了所有选择，恢复到TXT
            self.output_txt_checkbox.value = True
            selected_formats = ["txt"]
            self._show_snackbar("至少需要选择一种输出格式", ft.Colors.ORANGE)
            try:
                self._page.update()
            except Exception:
                pass
        
        # 保存配置
        self.config_service.set_config_value("ocr_output_formats", selected_formats)
        self.config_service.save_config()
    
    def _on_output_image_change(self, e: ft.ControlEvent) -> None:
        """输出识别结果图选项改变。"""
        self.config_service.set_config_value("ocr_output_image", e.control.value)
        self.config_service.save_config()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode = e.control.value
        is_custom = mode == "custom"
        
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        
        try:
            self._page.update()
        except Exception:
            pass
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        
        if result:
            self.custom_output_dir.value = result
            try:
                self._page.update()
            except Exception:
                pass
    
    def _on_download_model(self, e: ft.ControlEvent) -> None:
        """下载模型。"""
        # 禁用按钮
        self.download_model_button.disabled = True
        self.load_model_button.disabled = True
        self.model_progress_bar.visible = True
        self.model_progress_text.visible = True
        self._page.update()
        
        async def _download_async():
            import asyncio
            self._download_finished = False
            self._pending_progress = None
            
            async def _poll():
                while not self._download_finished:
                    if self._pending_progress is not None:
                        progress, msg = self._pending_progress
                        self.model_progress_bar.value = progress
                        self.model_progress_text.value = msg
                        self._page.update()
                        self._pending_progress = None
                    await asyncio.sleep(0.3)
            
            def _do_download():
                def progress_callback(progress: float, message: str):
                    self._pending_progress = (progress, message)
                
                return self.ocr_service.download_model(
                    self.current_model_key,
                    progress_callback=progress_callback
                )
            
            poll_task = asyncio.create_task(_poll())
            try:
                success, message = await asyncio.to_thread(_do_download)
            finally:
                self._download_finished = True
                await poll_task
            
            # 更新UI
            self.download_model_button.disabled = False
            self.load_model_button.disabled = False
            self.model_progress_bar.visible = False
            self.model_progress_text.visible = False
            
            if success:
                self._init_model_status()
                self._show_snackbar("模型下载成功！", ft.Colors.GREEN)
            else:
                self._show_snackbar(f"模型下载失败: {message}", ft.Colors.RED)
            
            self._page.update()
        
        self._page.run_task(_download_async)
    
    def _on_load_model(self, e: ft.ControlEvent) -> None:
        """加载模型。"""
        # 禁用按钮
        self.load_model_button.disabled = True
        self.model_progress_bar.visible = True
        self.model_progress_text.visible = True
        self._page.update()
        
        async def _load_async():
            import asyncio
            self._load_finished = False
            self._pending_progress = None
            
            async def _poll():
                while not self._load_finished:
                    if self._pending_progress is not None:
                        progress, msg = self._pending_progress
                        self.model_progress_bar.value = progress
                        self.model_progress_text.value = msg
                        self._page.update()
                        self._pending_progress = None
                    await asyncio.sleep(0.3)
            
            def _do_load():
                def progress_callback(progress: float, message: str):
                    self._pending_progress = (progress, message)
                
                use_gpu = self.gpu_checkbox.value
                return self.ocr_service.load_model(
                    self.current_model_key,
                    use_gpu=use_gpu,
                    progress_callback=progress_callback
                )
            
            poll_task = asyncio.create_task(_poll())
            try:
                success, message = await asyncio.to_thread(_do_load)
            finally:
                self._load_finished = True
                await poll_task
            
            # 更新UI
            self.load_model_button.disabled = False
            self.model_progress_bar.visible = False
            self.model_progress_text.visible = False
            
            if success:
                # 获取设备信息
                device_info = self.ocr_service.get_device_info()
                
                self.model_status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
                self.model_status_icon.color = ft.Colors.BLUE
                self.model_status_text.value = f"已加载 ({device_info})"
                self.load_model_button.visible = False
                self.unload_model_button.visible = True
                self._show_snackbar(f"模型加载成功，使用设备: {device_info}", ft.Colors.GREEN)
            else:
                self._show_snackbar(f"模型加载失败: {message}", ft.Colors.RED)
            
            self._page.update()
        
        self._page.run_task(_load_async)
    
    def _on_unload_model(self, e: ft.ControlEvent) -> None:
        """卸载模型。"""
        try:
            self.ocr_service.unload_model()
            
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已下载 ({self.current_model.size_mb}MB)"
            self.load_model_button.visible = True
            self.unload_model_button.visible = False
            
            self._show_snackbar("模型已卸载", ft.Colors.GREEN)
            self._page.update()
        except Exception as ex:
            logger.error(f"卸载模型失败: {ex}")
            self._show_snackbar(f"卸载失败: {str(ex)}", ft.Colors.RED)
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型文件。"""
        def confirm_delete(confirmed: bool):
            if not confirmed:
                return
            
            try:
                # 先卸载模型
                if self.ocr_service.det_session or self.ocr_service.rec_session:
                    self.ocr_service.unload_model()
                
                # 删除模型文件
                model_dir = self.ocr_service.get_model_dir(self.current_model_key)
                det_path = model_dir / self.current_model.det_filename
                rec_path = model_dir / self.current_model.rec_filename
                dict_path = model_dir / self.current_model.dict_filename
                
                if det_path.exists():
                    det_path.unlink()
                if rec_path.exists():
                    rec_path.unlink()
                if dict_path.exists():
                    dict_path.unlink()
                
                # 更新状态
                self._init_model_status()
                self._show_snackbar("模型文件已删除", ft.Colors.GREEN)
            except Exception as ex:
                logger.error(f"删除模型失败: {ex}")
                self._show_snackbar(f"删除失败: {str(ex)}", ft.Colors.RED)
        
        # 显示确认对话框
        dialog = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要删除模型 {self.current_model.display_name} 吗？\n删除后需要重新下载才能使用。"),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self._page.close(dialog)),
                ft.TextButton("删除", on_click=lambda _: (self._page.close(dialog), confirm_delete(True), self._page.update())),
            ],
        )
        self._page.open(dialog)
    
    def _on_recognize(self, e: ft.ControlEvent) -> None:
        """开始识别。"""
        if not self.selected_files:
            self._show_snackbar("请先选择图片", ft.Colors.ORANGE)
            return
        
        if self.is_processing:
            self._show_snackbar("正在处理中，请稍候", ft.Colors.ORANGE)
            return
        
        # 禁用按钮
        self.is_processing = True
        self.recognize_button.content.disabled = True
        self.progress_bar.visible = True
        self.progress_bar.value = None  # 显示不确定进度
        self.progress_text.visible = True
        self._page.update()
        
        async def _recognize_async():
            import asyncio
            self._recognize_finished = False
            self._pending_progress = None
            self._pending_file_list_update = False
            self._pending_model_loaded = None
            
            async def _poll():
                while not self._recognize_finished:
                    needs_update = False
                    if self._pending_progress is not None:
                        bar_val, text_val = self._pending_progress
                        self.progress_bar.value = bar_val
                        self.progress_text.value = text_val
                        self._pending_progress = None
                        needs_update = True
                    if self._pending_model_loaded is not None:
                        device_info = self._pending_model_loaded
                        self.model_status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
                        self.model_status_icon.color = ft.Colors.BLUE
                        self.model_status_text.value = f"已加载 ({device_info})"
                        self.load_model_button.visible = False
                        self.unload_model_button.visible = True
                        self._pending_model_loaded = None
                        needs_update = True
                    if self._pending_file_list_update:
                        self._pending_file_list_update = False
                        self._update_file_list()
                    elif needs_update:
                        self._page.update()
                    await asyncio.sleep(0.3)
            
            def _do_recognize():
                total_files = len(self.selected_files)
                success_count = 0
                fail_count = 0
                
                # 如果模型未加载，先加载
                if not self.ocr_service.det_session or not self.ocr_service.rec_session:
                    def load_progress_callback(progress: float, message: str):
                        self._pending_progress = (progress * 0.1, f"正在加载模型: {message}")
                    
                    use_gpu = self.gpu_checkbox.value
                    success, message = self.ocr_service.load_model(
                        self.current_model_key,
                        use_gpu=use_gpu,
                        progress_callback=load_progress_callback
                    )
                    
                    if success:
                        device_info = self.ocr_service.get_device_info()
                        self._pending_model_loaded = device_info
                    else:
                        return 0, 0, True, message
                
                # 逐个处理文件
                for i, file_path in enumerate(self.selected_files):
                    def file_progress_callback(progress: float, message: str):
                        file_base_progress = 0.1 + (i / total_files) * 0.9
                        file_delta_progress = (progress / total_files) * 0.9
                        total_progress = file_base_progress + file_delta_progress
                        self._pending_progress = (total_progress, f"正在处理 {i+1}/{total_files}: {file_path.name} - {message}")
                    
                    # 执行OCR
                    ocr_success, results = self.ocr_service.ocr(
                        str(file_path),
                        progress_callback=file_progress_callback
                    )
                    
                    if ocr_success:
                        self.ocr_results[str(file_path)] = results
                        
                        # 自动保存结果到文件
                        if self._save_single_result(file_path, results):
                            success_count += 1
                        else:
                            # 保存失败但识别成功，仍计为成功
                            success_count += 1
                            logger.warning(f"识别成功但保存失败: {file_path}")
                    else:
                        fail_count += 1
                        logger.error(f"OCR识别失败: {file_path}")
                    
                    # 标记需要更新文件列表
                    self._pending_file_list_update = True
                
                return success_count, fail_count, False, ""
            
            success_count = 0
            fail_count = 0
            load_failed = False
            load_error = ""
            
            poll_task = asyncio.create_task(_poll())
            try:
                success_count, fail_count, load_failed, load_error = await asyncio.to_thread(_do_recognize)
            except Exception as ex:
                logger.error(f"批量OCR识别出错: {ex}")
                self._show_snackbar(f"识别出错: {str(ex)}", ft.Colors.RED)
            finally:
                self._recognize_finished = True
                await poll_task
            
            if load_failed:
                self._show_snackbar(f"模型加载失败: {load_error}", ft.Colors.RED)
            elif success_count > 0 or fail_count > 0:
                # 显示完成消息
                output_mode = self.output_mode_radio.value
                
                if output_mode == "same":
                    output_desc = "原文件目录"
                else:
                    output_desc = Path(self.custom_output_dir.value).name
                
                # 获取输出格式描述
                format_desc = []
                if self.output_txt_checkbox.value:
                    format_desc.append("TXT")
                if self.output_json_checkbox.value:
                    format_desc.append("JSON")
                if self.output_image_checkbox.value:
                    format_desc.append("图片")
                format_str = "+".join(format_desc) if format_desc else "TXT"
                
                if fail_count == 0:
                    self._show_snackbar(
                        f"全部完成！成功识别 {success_count} 个文件，已保存到{output_desc}（{format_str}）",
                        ft.Colors.GREEN
                    )
                else:
                    self._show_snackbar(
                        f"处理完成！成功: {success_count}, 失败: {fail_count}",
                        ft.Colors.ORANGE
                    )
            
            # 最终更新文件列表和恢复UI
            self._update_file_list()
            self.is_processing = False
            self.recognize_button.content.disabled = False
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self._page.update()
        
        self._page.run_task(_recognize_async)
    
    
    def _get_output_path(self, input_file: Path, output_format: str) -> Path:
        """获取输出文件路径。
        
        Args:
            input_file: 输入文件路径
            output_format: 输出格式（txt/json）
        
        Returns:
            输出文件路径
        """
        output_mode = self.output_mode_radio.value
        suffix = self.file_suffix.value or "_ocr"
        
        if output_mode == "same":
            # 保存到原文件目录
            output_dir = input_file.parent
        else:
            # 自定义输出目录
            output_dir = Path(self.custom_output_dir.value)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成输出文件名
        output_name = f"{input_file.stem}{suffix}.{output_format}"
        output_path = output_dir / output_name
        
        # 根据全局设置决定是否添加序号
        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
        return get_unique_path(output_path, add_sequence=add_sequence)
    
    def _save_single_result(self, input_file: Path, results: List[Tuple[List, str, float]]) -> bool:
        """保存单个文件的识别结果（根据用户选择的格式）。
        
        Args:
            input_file: 输入文件路径
            results: OCR结果列表
        
        Returns:
            是否成功
        """
        try:
            # 获取用户选择的输出格式
            selected_formats = []
            if self.output_txt_checkbox.value:
                selected_formats.append("txt")
            if self.output_json_checkbox.value:
                selected_formats.append("json")
            
            # 检查是否至少选择了一种输出方式
            has_output = selected_formats or self.output_image_checkbox.value
            if not has_output:
                # 如果什么都没选，默认保存TXT
                selected_formats = ["txt"]
            
            success_count = 0
            total_formats = len(selected_formats)
            
            # 保存TXT格式
            if "txt" in selected_formats:
                txt_path = self._get_output_path(input_file, "txt")
                with open(txt_path, 'w', encoding='utf-8') as f:
                    if not results:
                        f.write("未识别到文字\n")
                    else:
                        # 按位置从上到下、从左到右排序
                        sorted_results = sorted(
                            results,
                            key=lambda x: (min(pt[1] for pt in x[0]), min(pt[0] for pt in x[0]))
                        )
                        
                        for box, text, confidence in sorted_results:
                            f.write(f"{text}\n")
                
                logger.info(f"TXT结果已保存: {txt_path}")
                success_count += 1
            
            # 保存JSON格式
            if "json" in selected_formats:
                json_path = self._get_output_path(input_file, "json")
                data = {
                    "image": str(input_file),
                    "model": self.current_model_key,
                    "results": [
                        {
                            "box": box,
                            "text": text,
                            "confidence": confidence
                        }
                        for box, text, confidence in results
                    ]
                }
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"JSON结果已保存: {json_path}")
                success_count += 1
            
            # 保存识别结果图
            if self.output_image_checkbox.value:
                image_path = self._get_output_path(input_file, "png")
                if self._draw_ocr_result(input_file, results, image_path):
                    logger.info(f"识别结果图已保存: {image_path}")
                    total_formats += 1
                    success_count += 1
            
            return success_count == total_formats
            
        except Exception as ex:
            logger.error(f"保存结果失败: {input_file.name}, 错误: {ex}")
            return False
    
    def _draw_ocr_result(self, input_file: Path, results: List[Tuple[List, str, float]], output_path: Path) -> bool:
        """绘制OCR识别结果对比图（左边检测框标注，右边识别文字）。
        
        Args:
            input_file: 输入图片路径
            results: OCR结果列表
            output_path: 输出图片路径
        
        Returns:
            是否成功
        """
        try:
            # 读取原图
            image = cv2.imdecode(np.fromfile(str(input_file), dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                logger.error(f"无法读取图像: {input_file}")
                return False
            
            h, w = image.shape[:2]
            
            # 左侧：原图 + 检测框标注
            left_image = image.copy()
            
            # 右侧：白色背景 + 识别文字（按原位置排版）
            right_image = np.ones((h, w, 3), dtype=np.uint8) * 255  # 白色背景
            
            # 按位置排序
            sorted_results = sorted(
                results,
                key=lambda x: (min(pt[1] for pt in x[0]), min(pt[0] for pt in x[0]))
            )
            
            # 定义颜色（BGR格式）
            box_color = (0, 255, 0)  # 绿色框
            number_bg_color = (0, 200, 0)  # 深绿色背景（序号）
            number_color = (255, 255, 255)  # 白色文字（序号）
            text_color = (0, 0, 0)  # 黑色文字（右侧文本）
            
            for idx, (box, text, confidence) in enumerate(sorted_results, 1):
                box_array = np.array(box, dtype=np.int32)
                
                # 左侧：绘制检测框和序号
                cv2.polylines(left_image, [box_array], True, box_color, 2)
                
                # 计算框的左上角位置（用于放置序号）
                min_x = int(min(pt[0] for pt in box))
                min_y = int(min(pt[1] for pt in box))
                
                # 将序号放在框的左上角外侧（不遮挡内容）
                circle_radius = 15
                # 序号圆圈位置：左上角的左上方
                circle_x = max(circle_radius, min_x - 5)
                circle_y = max(circle_radius, min_y - 5)
                
                # 绘制序号（圆形背景）
                cv2.circle(left_image, (circle_x, circle_y), circle_radius, number_bg_color, -1)
                cv2.circle(left_image, (circle_x, circle_y), circle_radius, box_color, 2)
                
                # 绘制序号文字
                number_text = str(idx)
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                (text_width, text_height), _ = cv2.getTextSize(number_text, font, font_scale, thickness)
                text_x = circle_x - text_width // 2
                text_y = circle_y + text_height // 2
                cv2.putText(
                    left_image,
                    number_text,
                    (text_x, text_y),
                    font,
                    font_scale,
                    number_color,
                    thickness,
                    cv2.LINE_AA
                )
                
                # 右侧：绘制识别出的文字（按原位置）
                # 计算文本框的左上角位置
                text_x = int(min(pt[0] for pt in box))
                text_y = int(min(pt[1] for pt in box))
                
                # 绘制浅色参考框（虚线效果）
                cv2.polylines(right_image, [box_array], True, (200, 200, 200), 1, cv2.LINE_AA)
                
                # 绘制序号
                number_with_colon = f"{idx}."
                cv2.putText(
                    right_image,
                    number_with_colon,
                    (text_x, text_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (100, 100, 100),  # 灰色序号
                    1,
                    cv2.LINE_AA
                )
                
                # 尝试使用PIL绘制中文文字（如果文本包含中文）
                # 由于OpenCV不支持中文，这里先绘制简化版本
                # 如果包含中文，显示文字内容（简化处理）
                display_text = text if text else ""
                
                # 计算合适的字体大小（基于框的高度）
                box_height = int(max(
                    np.linalg.norm(box_array[0] - box_array[3]),
                    np.linalg.norm(box_array[1] - box_array[2])
                ))
                text_font_scale = min(box_height / 40.0, 1.0)
                
                # 对于纯ASCII文本，使用OpenCV绘制
                if display_text.isascii():
                    cv2.putText(
                        right_image,
                        display_text,
                        (text_x + 5, text_y + box_height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        text_font_scale,
                        text_color,
                        2,
                        cv2.LINE_AA
                    )
                else:
                    # 对于中文，使用PIL绘制
                    from PIL import Image, ImageDraw, ImageFont
                    
                    # 转换为PIL图像
                    right_pil = Image.fromarray(cv2.cvtColor(right_image, cv2.COLOR_BGR2RGB))
                    draw = ImageDraw.Draw(right_pil)
                    
                    # 使用系统字体（Windows）
                    try:
                        font_size = max(int(box_height * 0.8), 12)
                        # Windows 中文字体
                        pil_font = ImageFont.truetype("msyh.ttc", font_size)  # 微软雅黑
                    except Exception:
                        try:
                            pil_font = ImageFont.truetype("simhei.ttf", font_size)  # 黑体
                        except Exception:
                            pil_font = ImageFont.load_default()
                    
                    # 绘制文字
                    draw.text(
                        (text_x + 5, text_y + 5),
                        display_text,
                        font=pil_font,
                        fill=(0, 0, 0)  # 黑色
                    )
                    
                    # 转换回OpenCV格式
                    right_image = cv2.cvtColor(np.array(right_pil), cv2.COLOR_RGB2BGR)
            
            # 在左侧图左上角添加总结信息
            summary_text = f"Detected: {len(results)} texts"
            cv2.rectangle(left_image, (5, 5), (280, 45), (0, 0, 0), -1)
            cv2.putText(
                left_image,
                summary_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA
            )
            
            # 创建对比图：左边检测框，右边文字
            separator_width = 4
            separator = np.ones((h, separator_width, 3), dtype=np.uint8) * 128  # 灰色分割线
            
            # 水平拼接
            comparison_image = np.hstack([left_image, separator, right_image])
            
            # 在顶部添加标题
            title_height = 40
            title_bar = np.ones((title_height, comparison_image.shape[1], 3), dtype=np.uint8) * 50
            
            # 绘制标题文字
            cv2.putText(
                title_bar,
                "Detection",
                (w // 2 - 70, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
            cv2.putText(
                title_bar,
                "Recognition",
                (w + separator_width + w // 2 - 90, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
            
            # 垂直拼接标题栏和对比图
            final_image = np.vstack([title_bar, comparison_image])
            
            # 保存图片（支持中文路径）
            is_success, buffer = cv2.imencode('.png', final_image)
            if is_success:
                with open(output_path, 'wb') as f:
                    f.write(buffer)
                return True
            else:
                logger.error(f"编码图像失败: {output_path}")
                return False
            
        except Exception as ex:
            logger.error(f"绘制识别结果图失败: {ex}")
            return False
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示消息提示。"""
        snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
        )
        self._page.open(snack_bar)
    
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
            self._show_snackbar(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_snackbar("OCR工具不支持该格式", ft.Colors.ORANGE)
        
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。
        
        在视图被销毁时调用，确保所有资源被正确释放。
        """
        import gc
        
        try:
            # 1. 卸载 OCR 模型
            if self.ocr_service:
                self.ocr_service.unload_model()
            
            # 2. 清空识别结果（可能包含大量数据）
            if self.ocr_results:
                self.ocr_results.clear()
            
            # 3. 清空文件列表
            if self.selected_files:
                self.selected_files.clear()
            
            # 4. 清空预览图片引用
            if hasattr(self, 'current_preview_images'):
                self.current_preview_images = []
            
            # 5. 清除回调引用，打破循环引用
            self.on_back = None
            
            # 6. 清除 UI 内容
            self.content = None
            
            # 7. 强制垃圾回收
            gc.collect()
            
            logger.info("OCR视图资源已清理")
        except Exception as e:
            logger.warning(f"清理OCR视图资源时出错: {e}")