# -*- coding: utf-8 -*-
"""图像增强视图模块。

提供图像超分辨率增强功能的用户界面。
"""

import gc
import threading
import webbrowser
from pathlib import Path
from typing import Callable, List, Optional, Dict
from utils import logger

import flet as ft

from constants import (
    IMAGE_ENHANCE_MODELS,
    BORDER_RADIUS_MEDIUM,
    DEFAULT_ENHANCE_MODEL_KEY,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from constants.model_config import ImageEnhanceModelInfo
from services import ConfigService, ImageService
from services.image_service import ImageEnhancer
from utils import format_file_size


class ImageEnhanceView(ft.Container):
    """图像增强视图类。
    
    提供图像超分辨率增强功能，包括：
    - 单文件和批量处理
    - Real-ESRGAN x4 放大
    - 自动下载ONNX模型
    - 处理进度显示
    - 支持多种图片格式
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图像增强视图。
        
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
        self.enhancer: Optional[ImageEnhancer] = None
        self.is_model_loading: bool = False
        
        # 当前选择的模型
        saved_model_key = self.config_service.get_config_value("enhance_model_key", DEFAULT_ENHANCE_MODEL_KEY)
        if saved_model_key not in IMAGE_ENHANCE_MODELS:
            saved_model_key = DEFAULT_ENHANCE_MODEL_KEY
        self.current_model_key: str = saved_model_key
        self.current_model: ImageEnhanceModelInfo = IMAGE_ENHANCE_MODELS[self.current_model_key]
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 获取模型路径
        self.model_path: Path = self._get_model_path()
        self.data_path: Optional[Path] = self._get_data_path()
        
        # 标记UI是否已构建
        self._ui_built: bool = False
        
        # 先创建加载界面
        self._build_loading_ui()
        
        # 延迟构建完整UI
        threading.Thread(target=self._build_ui_async, daemon=True).start()
    
    def _get_model_path(self) -> Path:
        """获取当前选择的模型文件路径。
        
        Returns:
            模型文件路径
        """
        data_dir = self.config_service.get_data_dir()
        models_dir = data_dir / "models" / "image_enhance" / self.current_model.version
        return models_dir / self.current_model.filename
    
    def _get_data_path(self) -> Optional[Path]:
        """获取当前模型的数据文件路径（如果有）。
        
        Returns:
            数据文件路径，如果不需要则返回None
        """
        if not self.current_model.data_filename:
            return None
        data_dir = self.config_service.get_data_dir()
        models_dir = data_dir / "models" / "image_enhance" / self.current_model.version
        return models_dir / self.current_model.data_filename
    
    def _ensure_model_dir(self) -> None:
        """确保模型目录存在。"""
        model_dir = self.model_path.parent
        model_dir.mkdir(parents=True, exist_ok=True)
    
    def _build_loading_ui(self) -> None:
        """构建简单的加载界面。"""
        loading_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(),
                    ft.Text("正在加载图像增强功能...", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_LARGE,
            ),
            expand=True,
            alignment=ft.alignment.center,
        )
        self.content = loading_content
    
    def _build_ui_async(self) -> None:
        """异步构建完整UI。"""
        import time
        time.sleep(0.05)
        self._build_ui()
        self._ui_built = True
        try:
            self.update()
        except:
            pass
    
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
                ft.Text("图像增强", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view: ft.Column = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
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
                ),
                # 支持格式说明
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                f"支持格式: JPG, PNG, WebP, BMP 等 | 将放大 {self.current_model.scale}x | 适合清晰化模糊图片",
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
                    expand=True,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 模型选择下拉框
        model_options = []
        for key, model in IMAGE_ENHANCE_MODELS.items():
            if model.size_mb < 100:
                size_text = f"{model.size_mb}MB  "
            elif model.size_mb < 1000:
                size_text = f"{model.size_mb}MB "
            else:
                size_text = f"{model.size_mb}MB"
            
            option_text = f"{model.display_name}  |  {size_text}"
            model_options.append(
                ft.dropdown.Option(key=key, text=option_text)
            )
        
        self.model_selector: ft.Dropdown = ft.Dropdown(
            options=model_options,
            value=self.current_model_key,
            label="选择模型",
            hint_text="选择图像增强模型",
            on_change=self._on_model_select_change,
            width=320,
            dense=True,
            text_size=13,
        )
        
        # 模型信息显示
        self.model_info_text: ft.Text = ft.Text(
            f"放大: {self.current_model.scale}x | {self.current_model.quality} | {self.current_model.performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 模型状态显示
        self.model_status_icon: ft.Icon = ft.Icon(
            ft.Icons.HOURGLASS_EMPTY,
            size=20,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_status_text: ft.Text = ft.Text(
            "正在初始化...",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 下载按钮
        self.download_model_button: ft.ElevatedButton = ft.ElevatedButton(
            text="下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._start_download_model,
            visible=False,
        )
        
        # 加载模型按钮
        self.load_model_button: ft.ElevatedButton = ft.ElevatedButton(
            text="加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model,
            visible=False,
        )
        
        # 卸载模型按钮
        self.unload_model_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            on_click=self._on_unload_model,
            visible=False,
        )
        
        # 删除模型按钮
        self.delete_model_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            on_click=self._on_delete_model,
            visible=False,
        )
        
        model_status_row: ft.Row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.download_model_button,
                self.load_model_button,
                self.unload_model_button,
                self.delete_model_button,
            ],
            spacing=PADDING_MEDIUM // 2,
        )
        
        # 自动加载模型设置
        auto_load_model = self.config_service.get_config_value("enhance_auto_load_model", True)
        self.auto_load_checkbox: ft.Checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        # 放大倍率设置
        saved_scale = self.config_service.get_config_value("enhance_scale", self.current_model.scale)
        self.scale_slider: ft.Slider = ft.Slider(
            min=self.current_model.min_scale,
            max=self.current_model.max_scale,
            divisions=int((self.current_model.max_scale - self.current_model.min_scale) * 10),
            value=saved_scale,
            label="{value}x",
            on_change=self._on_scale_change,
        )
        
        self.scale_value_text: ft.Text = ft.Text(
            f"{saved_scale:.1f}x",
            size=13,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.PRIMARY,
        )
        
        scale_control: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("放大倍率:", size=13, weight=ft.FontWeight.W_500),
                            self.scale_value_text,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    self.scale_slider,
                    ft.Text(
                        f"范围: {self.current_model.min_scale}x - {self.current_model.max_scale}x",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.PRIMARY),
        )
        
        # 图像增强参数
        saved_denoise = self.config_service.get_config_value("enhance_denoise_strength", 0)
        self.denoise_slider: ft.Slider = ft.Slider(
            min=0,
            max=100,
            divisions=10,
            value=saved_denoise,
            label="{value}%",
            on_change=self._on_denoise_change,
        )
        
        saved_sharpen = self.config_service.get_config_value("enhance_sharpen_strength", 0)
        self.sharpen_slider: ft.Slider = ft.Slider(
            min=0,
            max=100,
            divisions=10,
            value=saved_sharpen,
            label="{value}%",
            on_change=self._on_sharpen_change,
        )
        
        saved_quality = self.config_service.get_config_value("enhance_output_quality", 95)
        self.quality_slider: ft.Slider = ft.Slider(
            min=60,
            max=100,
            divisions=8,
            value=saved_quality,
            label="{value}%",
            on_change=self._on_quality_change,
        )
        
        enhance_params: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("增强参数:", size=13, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL // 2),
                    
                    # 降噪强度
                    ft.Text("降噪强度:", size=12),
                    self.denoise_slider,
                    ft.Text("减少图像噪点（0=关闭，推荐20-40）", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    
                    ft.Container(height=PADDING_SMALL),
                    
                    # 锐化强度
                    ft.Text("锐化强度:", size=12),
                    self.sharpen_slider,
                    ft.Text("增强细节清晰度（0=关闭，推荐10-30）", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    
                    ft.Container(height=PADDING_SMALL),
                    
                    # 输出质量
                    ft.Text("输出质量:", size=12),
                    self.quality_slider,
                    ft.Text("保存质量（推荐90-95，100=无损）", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 处理选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀 _enhanced）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir: ft.TextField = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_data_dir() / "image_enhanced"),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        process_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("处理选项:", size=14, weight=ft.FontWeight.W_500),
                    self.model_selector,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                    self.auto_load_checkbox,
                    ft.Container(height=PADDING_SMALL),
                    scale_control,
                    ft.Container(height=PADDING_SMALL),
                    enhance_params,
                    ft.Container(height=PADDING_SMALL),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
                scroll=ft.ScrollMode.AUTO,  # 添加滚动支持
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 左右分栏布局
        main_content: ft.Row = ft.Row(
            controls=[
                ft.Container(
                    content=file_select_area,
                    expand=3,
                    height=380,
                ),
                ft.Container(
                    content=process_options,
                    expand=2,
                    height=380,  # 保持高度，内部Column可滚动
                ),
            ],
            spacing=PADDING_LARGE,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # 进度显示
        self.progress_bar: ft.ProgressBar = ft.ProgressBar(value=0, visible=False)
        self.progress_text: ft.Text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        progress_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    self.progress_text,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
        )
        
        # 底部大按钮
        self.process_button: ft.Container = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=24),
                        ft.Text("开始增强", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process,
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.alignment.center,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                main_content,
                ft.Container(height=PADDING_LARGE),
                progress_container,
                ft.Container(height=PADDING_MEDIUM),
                self.process_button,
                ft.Container(height=PADDING_LARGE),
            ],
            spacing=0,
            scroll=ft.ScrollMode.ADAPTIVE,
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
        self._update_file_list()
        
        # 延迟检查模型状态
        threading.Thread(target=self._check_model_status_async, daemon=True).start()
    
    def _check_model_status_async(self) -> None:
        """异步检查模型状态。"""
        import time
        time.sleep(0.05)
        self._check_model_status()
    
    def _check_model_status(self) -> None:
        """检查模型状态。"""
        auto_load = self.config_service.get_config_value("enhance_auto_load_model", True)
        
        # 检查主模型文件和数据文件是否都存在
        model_exists = self.model_path.exists()
        data_exists = True if not self.data_path else self.data_path.exists()
        
        if model_exists and data_exists:
            if auto_load:
                self._update_model_status("loading", "正在加载模型...")
                threading.Thread(target=self._load_model_async, daemon=True).start()
            else:
                self._update_model_status("unloaded", "模型已下载，未加载")
        else:
            # 显示需要下载哪些文件
            if not model_exists and not data_exists:
                self._update_model_status("need_download", "需要下载模型文件和数据文件")
            elif not model_exists:
                self._update_model_status("need_download", "需要下载模型文件")
            else:
                self._update_model_status("need_download", "需要下载数据文件")
    
    def _load_model_async(self) -> None:
        """异步加载模型。"""
        try:
            use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
            gpu_device_id = self.config_service.get_config_value("gpu_device_id", 0)
            gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 2048)
            enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", True)
            
            self.enhancer = ImageEnhancer(
                self.model_path,
                data_path=self.data_path,
                use_gpu=use_gpu,
                gpu_device_id=gpu_device_id,
                gpu_memory_limit=gpu_memory_limit,
                enable_memory_arena=enable_memory_arena,
                scale=self.current_model.scale
            )
            self._on_model_loaded(True, None)
        except Exception as e:
            self._on_model_loaded(False, str(e))
    
    def _start_download_model(self, e: ft.ControlEvent = None) -> None:
        """开始下载模型文件。"""
        if self.is_model_loading:
            return
        
        self.is_model_loading = True
        
        # 确定需要下载的文件
        files_to_download = []
        if not self.model_path.exists():
            files_to_download.append(("模型文件", self.current_model.url, self.model_path))
        if self.data_path and not self.data_path.exists():
            files_to_download.append(("数据文件", self.current_model.data_url, self.data_path))
        
        if not files_to_download:
            self._show_snackbar("模型文件已存在", ft.Colors.ORANGE)
            self.is_model_loading = False
            return
        
        total_files = len(files_to_download)
        self._update_model_status("downloading", f"正在下载 {total_files} 个文件...")
        
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.visible = True
        self.progress_text.value = "准备下载..."
        try:
            self.progress_bar.update()
            self.progress_text.update()
        except:
            pass
        
        def download_task():
            try:
                self._ensure_model_dir()
                import httpx
                
                for file_idx, (file_name, url, save_path) in enumerate(files_to_download):
                    self.progress_text.value = f"正在下载 {file_name} ({file_idx + 1}/{total_files})..."
                    try:
                        self.progress_text.update()
                    except:
                        pass
                    
                    with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(save_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    
                                    if total_size > 0:
                                        file_progress = downloaded / total_size
                                        overall_progress = (file_idx + file_progress) / total_files
                                        percent = overall_progress * 100
                                        
                                        downloaded_mb = downloaded / (1024 * 1024)
                                        total_mb = total_size / (1024 * 1024)
                                        
                                        self.progress_bar.value = overall_progress
                                        self.progress_text.value = (
                                            f"下载 {file_name}: {downloaded_mb:.1f}MB / {total_mb:.1f}MB "
                                            f"({file_idx + 1}/{total_files}) - 总进度: {percent:.1f}%"
                                        )
                                        self.model_status_text.value = f"正在下载... {percent:.1f}%"
                                        
                                        try:
                                            self.progress_bar.update()
                                            self.progress_text.update()
                                            self.model_status_text.update()
                                        except:
                                            pass
                
                # 下载完成
                self.progress_bar.visible = False
                self.progress_text.visible = False
                try:
                    self.progress_bar.update()
                    self.progress_text.update()
                except:
                    pass
                
                # 加载模型
                use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
                gpu_device_id = self.config_service.get_config_value("gpu_device_id", 0)
                gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 2048)
                enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", True)
                
                self.enhancer = ImageEnhancer(
                    self.model_path,
                    data_path=self.data_path,
                    use_gpu=use_gpu,
                    gpu_device_id=gpu_device_id,
                    gpu_memory_limit=gpu_memory_limit,
                    enable_memory_arena=enable_memory_arena,
                    scale=self.current_model.scale
                )
                self._on_model_loaded(True, None)
            except Exception as e:
                self.progress_bar.visible = False
                self.progress_text.visible = False
                try:
                    self.progress_bar.update()
                    self.progress_text.update()
                except:
                    pass
                self._on_download_failed(str(e))
        
        threading.Thread(target=download_task, daemon=True).start()
    
    def _on_model_loaded(self, success: bool, error: Optional[str]) -> None:
        """模型加载完成回调。"""
        self.is_model_loading = False
        if success:
            device_info = "未知设备"
            if self.enhancer:
                device_info = self.enhancer.get_device_info()
                # 设置当前的放大倍率
                current_scale = self.scale_slider.value
                self.enhancer.set_scale(current_scale)
            
            self._update_model_status("ready", f"模型就绪 ({device_info})")
            self._update_process_button()
            self._show_snackbar(f"模型加载成功，使用设备: {device_info}", ft.Colors.GREEN)
        else:
            self._update_model_status("error", f"模型加载失败: {error}")
            self._show_snackbar(f"模型加载失败: {error}", ft.Colors.RED)
    
    def _on_download_failed(self, error: str) -> None:
        """模型下载失败回调。"""
        self.is_model_loading = False
        self._update_model_status("need_download", "下载失败，请重试")
        self._show_snackbar(f"模型下载失败: {error}", ft.Colors.RED)
        self._show_manual_download_dialog(error)
    
    def _update_model_status(self, status: str, message: str) -> None:
        """更新模型状态显示。"""
        if status == "loading":
            self.model_status_icon.name = ft.Icons.HOURGLASS_EMPTY
            self.model_status_icon.color = ft.Colors.BLUE
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "downloading":
            self.model_status_icon.name = ft.Icons.DOWNLOAD
            self.model_status_icon.color = ft.Colors.BLUE
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "ready":
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = True
            self.delete_model_button.visible = True
        elif status == "unloaded":
            self.model_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.model_status_icon.color = ft.Colors.GREY
            self.download_model_button.visible = False
            self.load_model_button.visible = True
            self.unload_model_button.visible = False
            self.delete_model_button.visible = True
        elif status == "error":
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.RED
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "need_download":
            self.model_status_icon.name = ft.Icons.WARNING
            self.model_status_icon.color = ft.Colors.ORANGE
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        
        self.model_status_text.value = message
        
        try:
            self.model_status_icon.update()
            self.model_status_text.update()
            self.download_model_button.update()
            self.load_model_button.update()
            self.unload_model_button.update()
            self.delete_model_button.update()
        except:
            pass
    
    def _show_manual_download_dialog(self, error: str) -> None:
        """显示手动下载对话框。"""
        def close_dialog(e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        def open_url_and_close(e: ft.ControlEvent, url: str) -> None:
            webbrowser.open(url)
        
        # 构建下载说明
        download_instructions = [
            ft.Text(f"自动下载模型失败: {error}", color=ft.Colors.RED),
            ft.Container(height=PADDING_MEDIUM),
            ft.Text("请手动下载以下文件：", weight=ft.FontWeight.W_500),
            ft.Container(height=PADDING_MEDIUM // 2),
        ]
        
        # 模型文件
        download_instructions.extend([
            ft.Text("1. 模型文件:"),
            ft.ElevatedButton(
                f"下载 {self.current_model.filename}",
                icon=ft.Icons.DOWNLOAD,
                on_click=lambda e: open_url_and_close(e, self.current_model.url),
            ),
            ft.Container(
                content=ft.Text(f"保存到: {self.model_path}", size=10, selectable=True),
                padding=PADDING_SMALL,
                bgcolor=ft.Colors.SECONDARY_CONTAINER,
                border_radius=BORDER_RADIUS_MEDIUM,
            ),
        ])
        
        # 数据文件（如果有）
        if self.data_path:
            download_instructions.extend([
                ft.Container(height=PADDING_SMALL),
                ft.Text("2. 数据文件:"),
                ft.ElevatedButton(
                    f"下载 {self.current_model.data_filename}",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda e: open_url_and_close(e, self.current_model.data_url),
                ),
                ft.Container(
                    content=ft.Text(f"保存到: {self.data_path}", size=10, selectable=True),
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.SECONDARY_CONTAINER,
                    border_radius=BORDER_RADIUS_MEDIUM,
                ),
            ])
        
        download_instructions.extend([
            ft.Container(height=PADDING_MEDIUM // 2),
            ft.Text("3. 重新打开此界面即可使用", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
        ])
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("自动下载失败"),
            content=ft.Column(
                controls=download_instructions,
                tight=True,
                spacing=PADDING_MEDIUM // 2,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("关闭", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _on_model_select_change(self, e: ft.ControlEvent) -> None:
        """模型选择变化事件。"""
        new_model_key = e.control.value
        if new_model_key == self.current_model_key:
            return
        
        if self.enhancer:
            def confirm_switch(confirm_e: ft.ControlEvent) -> None:
                dialog.open = False
                self.page.update()
                self._switch_model(new_model_key)
            
            def cancel_switch(cancel_e: ft.ControlEvent) -> None:
                dialog.open = False
                self.model_selector.value = self.current_model_key
                self.model_selector.update()
                self.page.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("确认切换模型"),
                content=ft.Text("切换模型将卸载当前已加载的模型。是否继续？", size=14),
                actions=[
                    ft.TextButton("取消", on_click=cancel_switch),
                    ft.ElevatedButton("切换", on_click=confirm_switch),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
        else:
            self._switch_model(new_model_key)
    
    def _switch_model(self, new_model_key: str) -> None:
        """切换到新模型。"""
        if self.enhancer:
            self.enhancer = None
            gc.collect()
        
        self.current_model_key = new_model_key
        self.current_model = IMAGE_ENHANCE_MODELS[new_model_key]
        self.config_service.set_config_value("enhance_model_key", new_model_key)
        
        self.model_path = self._get_model_path()
        self.data_path = self._get_data_path()
        
        self.model_info_text.value = f"放大: {self.current_model.scale}x | {self.current_model.quality} | {self.current_model.performance}"
        self.model_info_text.update()
        
        # 更新倍率滑块范围
        self.scale_slider.min = self.current_model.min_scale
        self.scale_slider.max = self.current_model.max_scale
        self.scale_slider.divisions = int((self.current_model.max_scale - self.current_model.min_scale) * 10)
        # 重置为模型默认倍率
        self.scale_slider.value = self.current_model.scale
        self.scale_value_text.value = f"{self.current_model.scale:.1f}x"
        self.config_service.set_config_value("enhance_scale", self.current_model.scale)
        self.scale_slider.update()
        self.scale_value_text.update()
        
        self._check_model_status()
        self._update_process_button()
        self._update_file_list()  # 更新文件列表以显示新的放大倍率
        self._show_snackbar(f"已切换到: {self.current_model.display_name}", ft.Colors.GREEN)
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型复选框变化事件。"""
        auto_load = self.auto_load_checkbox.value
        self.config_service.set_config_value("enhance_auto_load_model", auto_load)
        
        if auto_load and self.model_path.exists() and not self.enhancer:
            if not self.data_path or self.data_path.exists():
                self._update_model_status("loading", "正在加载模型...")
                threading.Thread(target=self._load_model_async, daemon=True).start()
    
    def _on_scale_change(self, e: ft.ControlEvent) -> None:
        """放大倍率滑块变化事件。"""
        scale = self.scale_slider.value
        self.scale_value_text.value = f"{scale:.1f}x"
        self.scale_value_text.update()
        
        # 保存到配置
        self.config_service.set_config_value("enhance_scale", scale)
        
        # 如果模型已加载，更新增强器的倍率
        if self.enhancer:
            self.enhancer.set_scale(scale)
        
        # 更新文件列表显示（刷新预览尺寸）
        self._update_file_list()
    
    def _on_denoise_change(self, e: ft.ControlEvent) -> None:
        """降噪强度滑块变化事件。"""
        strength = self.denoise_slider.value
        self.config_service.set_config_value("enhance_denoise_strength", strength)
    
    def _on_sharpen_change(self, e: ft.ControlEvent) -> None:
        """锐化强度滑块变化事件。"""
        strength = self.sharpen_slider.value
        self.config_service.set_config_value("enhance_sharpen_strength", strength)
    
    def _on_quality_change(self, e: ft.ControlEvent) -> None:
        """输出质量滑块变化事件。"""
        quality = self.quality_slider.value
        self.config_service.set_config_value("enhance_output_quality", quality)
    
    def _on_load_model(self, e: ft.ControlEvent) -> None:
        """加载模型按钮点击事件。"""
        model_exists = self.model_path.exists()
        data_exists = True if not self.data_path else self.data_path.exists()
        
        if model_exists and data_exists and not self.enhancer:
            self._update_model_status("loading", "正在加载模型...")
            threading.Thread(target=self._load_model_async, daemon=True).start()
        elif self.enhancer:
            self._show_snackbar("模型已加载", ft.Colors.ORANGE)
        else:
            self._show_snackbar("模型文件不完整", ft.Colors.RED)
    
    def _on_unload_model(self, e: ft.ControlEvent) -> None:
        """卸载模型按钮点击事件。"""
        def confirm_unload(confirm_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
            
            if self.enhancer:
                self.enhancer = None
                gc.collect()
                self._show_snackbar("模型已卸载", ft.Colors.GREEN)
                self._update_model_status("unloaded", "模型已下载，未加载")
                self._update_process_button()
            else:
                self._show_snackbar("模型未加载", ft.Colors.ORANGE)
        
        def cancel_unload(cancel_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        estimated_memory = int(self.current_model.size_mb * 1.2)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认卸载模型"),
            content=ft.Text(
                f"此操作将释放约{estimated_memory}MB内存，不会删除模型文件。需要时可以重新加载。",
                size=14
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel_unload),
                ft.ElevatedButton("卸载", icon=ft.Icons.POWER_SETTINGS_NEW, on_click=confirm_unload),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        def confirm_delete(confirm_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
            
            if self.enhancer:
                self.enhancer = None
                gc.collect()
            
            try:
                deleted_files = []
                if self.model_path.exists():
                    self.model_path.unlink()
                    deleted_files.append(self.current_model.filename)
                if self.data_path and self.data_path.exists():
                    self.data_path.unlink()
                    deleted_files.append(self.current_model.data_filename)
                
                if deleted_files:
                    self._show_snackbar(f"已删除: {', '.join(deleted_files)}", ft.Colors.GREEN)
                    self._update_model_status("need_download", "需要下载模型才能使用")
                    self._update_process_button()
                else:
                    self._show_snackbar("模型文件不存在", ft.Colors.ORANGE)
            except Exception as ex:
                self._show_snackbar(f"删除模型失败: {ex}", ft.Colors.RED)
        
        def cancel_delete(cancel_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除模型文件"),
            content=ft.Text(
                f"确定要删除图像增强模型文件吗？（约{self.current_model.size_mb}MB）删除后需要重新下载才能使用。",
                size=14
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.ElevatedButton(
                    "删除",
                    icon=ft.Icons.DELETE,
                    bgcolor=ft.Colors.ERROR,
                    color=ft.Colors.ON_ERROR,
                    on_click=confirm_delete,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                for file in result.files:
                    file_path = Path(file.path)
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "bmp", "webp", "tiff"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder_path = Path(result.path)
                image_extensions = {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".webp", ".tiff", ".tif"}
                for file_path in folder_path.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                        if file_path not in self.selected_files:
                            self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
                
                if self.selected_files:
                    self._show_snackbar(f"已添加 {len(self.selected_files)} 个文件", ft.Colors.GREEN)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择包含图片的文件夹")
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表按钮点击事件。"""
        self.selected_files.clear()
        self._update_file_list()
        self._update_process_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
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
                    height=280,
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
                    # 计算增强后的大小（使用当前倍率）
                    current_scale = self.scale_slider.value
                    enhanced_width = int(file_info['width'] * current_scale)
                    enhanced_height = int(file_info['height'] * current_scale)
                    info_text = f"{file_info['width']}×{file_info['height']} → {enhanced_width}×{enhanced_height} ({current_scale:.1f}x) · {size_str}"
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
        
        try:
            self.file_list_view.update()
        except:
            pass
    
    def _on_remove_file(self, index: int) -> None:
        """移除文件列表中的文件。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
            self._update_process_button()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。"""
        is_custom = self.output_mode_radio.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        self.custom_output_dir.update()
        self.browse_output_button.update()
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_dir.value = result.path
                self.custom_output_dir.update()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")
    
    def _update_process_button(self) -> None:
        """更新处理按钮状态。"""
        button = self.process_button.content
        button.disabled = not (self.selected_files and self.enhancer)
        self.process_button.update()
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。"""
        if not self.selected_files:
            self._show_snackbar("请先选择图片文件", ft.Colors.ORANGE)
            return
        
        if not self.enhancer:
            self._show_snackbar("模型未加载，请稍候", ft.Colors.RED)
            return
        
        # 确定输出目录
        if self.output_mode_radio.value == "custom":
            output_dir = Path(self.custom_output_dir.value)
        else:
            output_dir = self.config_service.get_data_dir() / "image_enhanced"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 禁用处理按钮并显示进度
        button = self.process_button.content
        button.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备处理..."
        
        try:
            self.page.update()
        except:
            pass
        
        # 后台线程处理
        def process_task():
            total_files = len(self.selected_files)
            success_count = 0
            
            for i, file_path in enumerate(self.selected_files):
                try:
                    progress = i / total_files
                    self._update_progress(progress, f"正在增强: {file_path.name} ({i+1}/{total_files})")
                    
                    # 读取图片
                    from PIL import Image
                    import cv2
                    import numpy as np
                    
                    image = Image.open(file_path)
                    
                    # 增强图像
                    result = self.enhancer.enhance_image(image)
                    
                    # 应用后处理（如果启用）
                    denoise_strength = int(self.denoise_slider.value)
                    sharpen_strength = int(self.sharpen_slider.value)
                    
                    if denoise_strength > 0 or sharpen_strength > 0:
                        # 转换为numpy数组进行处理
                        result_np = np.array(result)
                        result_np = cv2.cvtColor(result_np, cv2.COLOR_RGB2BGR)
                        
                        # 应用降噪
                        if denoise_strength > 0:
                            result_np = self.image_service.apply_denoise(result_np, denoise_strength)
                        
                        # 应用锐化
                        if sharpen_strength > 0:
                            result_np = self.image_service.apply_sharpen(result_np, sharpen_strength)
                        
                        # 转换回PIL
                        result_np = cv2.cvtColor(result_np, cv2.COLOR_BGR2RGB)
                        result = Image.fromarray(result_np)
                    
                    # 生成输出文件名
                    if self.output_mode_radio.value == "new":
                        output_filename = f"{file_path.stem}_enhanced{file_path.suffix}"
                        output_path = file_path.parent / output_filename
                    else:
                        output_filename = f"{file_path.stem}_enhanced{file_path.suffix}"
                        output_path = output_dir / output_filename
                    
                    # 获取输出质量
                    quality = int(self.quality_slider.value)
                    
                    # 保存结果
                    if output_path.suffix.lower() in ['.jpg', '.jpeg']:
                        result.save(output_path, quality=quality, optimize=True)
                    elif output_path.suffix.lower() == '.png':
                        result.save(output_path, optimize=True, compress_level=9)
                    elif output_path.suffix.lower() == '.webp':
                        result.save(output_path, quality=quality, method=6)
                    else:
                        result.save(output_path, quality=quality, optimize=True)
                    
                    success_count += 1
                    
                except Exception as ex:
                    logger.error(f"处理失败 {file_path.name}: {ex}")
            
            # 处理完成
            self._on_process_complete(success_count, total_files, output_dir)
        
        threading.Thread(target=process_task, daemon=True).start()
    
    def _update_progress(self, value: float, text: str) -> None:
        """更新进度显示。"""
        self.progress_bar.value = value
        self.progress_text.value = text
        try:
            self.page.update()
        except:
            pass
    
    def _on_process_complete(self, success_count: int, total: int, output_dir: Path) -> None:
        """处理完成回调。"""
        self.progress_bar.value = 1.0
        self.progress_text.value = f"处理完成! 成功: {success_count}/{total}"
        button = self.process_button.content
        button.disabled = False
        
        try:
            self.page.update()
        except:
            pass
        
        if self.output_mode_radio.value == "new":
            self._show_snackbar(
                f"处理完成! 成功增强 {success_count} 个文件，保存在原文件旁边",
                ft.Colors.GREEN
            )
        else:
            self._show_snackbar(
                f"处理完成! 成功增强 {success_count} 个文件，保存到: {output_dir}",
                ft.Colors.GREEN
            )
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。"""
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        try:
            self.page.update()
        except:
            pass
