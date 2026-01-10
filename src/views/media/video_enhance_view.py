# -*- coding: utf-8 -*-
"""视频增强视图模块。

提供视频超分辨率增强功能的用户界面。

性能等待优化
"""

import gc
import tempfile
import threading
from pathlib import Path
from typing import Callable, List, Optional
from utils import logger

import flet as ft

from constants import (
    IMAGE_ENHANCE_MODELS,
    BORDER_RADIUS_MEDIUM,
    DEFAULT_ENHANCE_MODEL_KEY,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from constants.model_config import ImageEnhanceModelInfo
from services import ConfigService, FFmpegService
from services.image_service import ImageEnhancer
from utils import format_file_size, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoEnhanceView(ft.Container):
    """视频增强视图类。
    
    提供视频超分辨率增强功能，包括："""
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg'}
    
    """
    - 单文件和批量处理
    - Real-ESRGAN 模型增强
    - 自动下载ONNX模型
    - 处理进度显示
    - GPU加速支持
    - 支持多种视频格式
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频增强视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        self.enhancer: Optional[ImageEnhancer] = None
        self.is_model_loading: bool = False
        self.is_processing: bool = False
        self.should_cancel: bool = False
        self.is_destroyed: bool = False  # 视图是否已被销毁
        
        # 当前选择的模型
        saved_model_key = self.config_service.get_config_value("video_enhance_model_key", DEFAULT_ENHANCE_MODEL_KEY)
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
        
        # 待处理的拖放文件（UI构建完成前收到的文件）
        self._pending_files: List[Path] = []
        
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
                    ft.Text("正在加载视频增强功能...", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
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
        
        # 处理UI构建前收到的待处理文件
        if self._pending_files and hasattr(self, 'file_list_view'):
            self._process_pending_files()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            # 显示 FFmpeg 安装视图
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self.page,
                self.ffmpeg_service,
                on_back=self._on_back_click,
                tool_name="视频增强"
            )
            return
        
        # 顶部：标题和返回按钮
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("视频增强", size=28, weight=ft.FontWeight.BOLD),
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
                        ft.Text("选择视频:", size=14, weight=ft.FontWeight.W_500),
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
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(
                                        f"支持格式: MP4, MKV, MOV, AVI, WebM 等 | 将放大 {self.current_model.scale}x | 适合提升视频画质",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.SPEED, size=16, color=ft.Colors.GREEN),
                                    ft.Text(
                                        "性能优化：使用管道模式处理，完全在内存中操作，无临时文件产生，GPU解码+增强+编码全流程加速",
                                        size=11,
                                        color=ft.Colors.GREEN,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=ft.Colors.ORANGE),
                                    ft.Text(
                                        "GPU编码器限制：输出分辨率超过4096x4096时将自动使用CPU编码（较慢）。建议调低放大倍率",
                                        size=11,
                                        color=ft.Colors.ORANGE,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINED, size=16, color=ft.Colors.BLUE),
                                    ft.Text(
                                        "提示：如需更快的处理速度，建议使用 ",
                                        size=11,
                                        color=ft.Colors.BLUE,
                                    ),
                                    ft.TextButton(
                                        "Video2X",
                                        url="https://github.com/k4yt3x/video2x/releases",
                                        style=ft.ButtonStyle(
                                            padding=0,
                                            color=ft.Colors.BLUE,
                                        ),
                                    ),
                                    ft.Text(
                                        "（目前我们的代码还未优化）",
                                        size=11,
                                        color=ft.Colors.BLUE,
                                    ),
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=4,
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
        
        # 模型选择下拉框（只显示适合视频的模型）
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
            hint_text="选择视频增强模型",
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
        auto_load_model = self.config_service.get_config_value("video_enhance_auto_load_model", True)
        self.auto_load_checkbox: ft.Checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        # 放大倍率设置
        saved_scale = self.config_service.get_config_value("video_enhance_scale", self.current_model.scale)
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
        
        # 视频输出设置
        saved_quality = self.config_service.get_config_value("video_enhance_output_quality", 23)
        self.quality_slider: ft.Slider = ft.Slider(
            min=18,
            max=30,
            divisions=12,
            value=saved_quality,
            label="CRF: {value}",
            on_change=self._on_quality_change,
        )
        
        self.quality_value_text: ft.Text = ft.Text(
            f"CRF: {saved_quality} (数值越小质量越好)",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 输出格式选择
        self.output_format_dropdown: ft.Dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("same", "保持原格式"),
                ft.dropdown.Option("mp4", "MP4 (H.264)"),
                ft.dropdown.Option("mkv", "MKV (H.264)"),
                ft.dropdown.Option("webm", "WebM (VP9)"),
            ],
            value="same",
            label="输出格式",
            width=200,
        )
        
        video_params: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("视频输出参数:", size=13, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL // 2),
                    
                    # 输出质量
                    ft.Text("输出质量 (CRF):", size=12),
                    self.quality_slider,
                    self.quality_value_text,
                    
                    ft.Container(height=PADDING_SMALL),
                    
                    # 输出格式
                    self.output_format_dropdown,
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
            value=str(self.config_service.get_data_dir() / "video_enhanced"),
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
                    video_params,
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
                scroll=ft.ScrollMode.AUTO,
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
                    height=380,
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
        
        # 取消按钮
        self.cancel_button: ft.Container = ft.Container(
            content=ft.OutlinedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CANCEL, size=20),
                        ft.Text("取消处理", size=14),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                on_click=self._on_cancel,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.alignment.center,
            visible=False,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                main_content,
                ft.Container(height=PADDING_LARGE),
                progress_container,
                ft.Container(height=PADDING_MEDIUM),
                self.process_button,
                self.cancel_button,
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
        auto_load = self.config_service.get_config_value("video_enhance_auto_load_model", True)
        
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
            gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 8192)
            enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", False)
            
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
                gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 8192)
                enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", False)
                
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
        if self.is_destroyed:
            logger.info("视图已销毁，跳过模型加载回调")
            return  # 视图已销毁，不更新UI
        
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
        if self.is_destroyed:
            logger.info("视图已销毁，跳过下载失败回调")
            return
        
        self.is_model_loading = False
        self._update_model_status("need_download", "下载失败，请重试")
        self._show_snackbar(f"模型下载失败: {error}", ft.Colors.RED)
    
    def _update_model_status(self, status: str, message: str) -> None:
        """更新模型状态显示。"""
        if self.is_destroyed:
            return  # 视图已销毁，不更新UI
        
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
    
    def _on_back_click(self, e: ft.ControlEvent = None) -> None:
        """返回按钮点击事件。"""
        # 检查是否有任务正在运行
        if self.is_processing:
            # 显示确认对话框
            def confirm_exit(confirm_e: ft.ControlEvent) -> None:
                dialog.open = False
                self.page.update()
                
                # 清理资源并取消任务
                self.cleanup()
                
                # 返回
                if self.on_back:
                    self.on_back()
            
            def cancel_exit(cancel_e: ft.ControlEvent) -> None:
                dialog.open = False
                self.page.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("确认退出"),
                content=ft.Text(
                    "视频增强任务正在进行中，退出将取消任务。是否确认退出？",
                    size=14
                ),
                actions=[
                    ft.TextButton("继续处理", on_click=cancel_exit),
                    ft.ElevatedButton(
                        "退出并取消",
                        icon=ft.Icons.EXIT_TO_APP,
                        on_click=confirm_exit
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
        else:
            # 没有任务在运行，直接返回
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
        self.config_service.set_config_value("video_enhance_model_key", new_model_key)
        
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
        self.config_service.set_config_value("video_enhance_scale", self.current_model.scale)
        self.scale_slider.update()
        self.scale_value_text.update()
        
        self._check_model_status()
        self._update_process_button()
        self._update_file_list()
        self._show_snackbar(f"已切换到: {self.current_model.display_name}", ft.Colors.GREEN)
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型复选框变化事件。"""
        auto_load = self.auto_load_checkbox.value
        self.config_service.set_config_value("video_enhance_auto_load_model", auto_load)
        
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
        self.config_service.set_config_value("video_enhance_scale", scale)
        
        # 如果模型已加载，更新增强器的倍率
        if self.enhancer:
            self.enhancer.set_scale(scale)
        
        # 更新文件列表显示
        self._update_file_list()
    
    def _on_quality_change(self, e: ft.ControlEvent) -> None:
        """输出质量滑块变化事件。"""
        quality = int(self.quality_slider.value)
        self.quality_value_text.value = f"CRF: {quality} (数值越小质量越好)"
        self.quality_value_text.update()
        self.config_service.set_config_value("video_enhance_output_quality", quality)
    
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
                f"确定要删除视频增强模型文件吗？（约{self.current_model.size_mb}MB）删除后需要重新下载才能使用。",
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
            dialog_title="选择视频文件",
            allowed_extensions=["mp4", "mkv", "mov", "avi", "wmv", "flv", "webm", "m4v", "3gp", "ts", "m2ts"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder_path = Path(result.path)
                video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ts", ".m2ts"}
                for file_path in folder_path.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                        if file_path not in self.selected_files:
                            self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
                
                if self.selected_files:
                    self._show_snackbar(f"已添加 {len(self.selected_files)} 个文件", ft.Colors.GREEN)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择包含视频的文件夹")
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表按钮点击事件。"""
        self.selected_files.clear()
        self._update_file_list()
        self._update_process_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if self.is_destroyed:
            return  # 视图已销毁，不更新UI
        
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.MOVIE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击选择按钮或点击此处选择视频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=280,
                    alignment=ft.alignment.center,
                    on_click=self._on_select_files,
                    tooltip="点击选择视频",
                )
            )
        else:
            for i, file_path in enumerate(self.selected_files):
                try:
                    file_size = file_path.stat().st_size
                    size_str = format_file_size(file_size)
                    
                    # 获取视频信息
                    video_info = self.ffmpeg_service.safe_probe(str(file_path))
                    info_text = f"大小: {size_str}"
                    
                    if video_info:
                        # 获取视频流信息
                        video_stream = None
                        for stream in video_info.get('streams', []):
                            if stream.get('codec_type') == 'video':
                                video_stream = stream
                                break
                        
                        if video_stream:
                            width = video_stream.get('width', 0)
                            height = video_stream.get('height', 0)
                            current_scale = self.scale_slider.value
                            enhanced_width = int(width * current_scale)
                            enhanced_height = int(height * current_scale)
                            info_text = f"{width}×{height} → {enhanced_width}×{enhanced_height} ({current_scale:.1f}x) · {size_str}"
                    
                    icon_color = ft.Colors.PRIMARY
                except Exception:
                    info_text = "无法读取文件信息"
                    icon_color = ft.Colors.RED
                
                file_item: ft.Container = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MOVIE, size=20, color=icon_color),
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
        if self.is_destroyed:
            return  # 视图已销毁，不更新UI
        
        try:
            button = self.process_button.content
            button.disabled = not (self.selected_files and self.enhancer)
            self.process_button.update()
        except:
            pass
    
    def _on_cancel(self, e: ft.ControlEvent) -> None:
        """取消处理按钮点击事件。"""
        self.should_cancel = True
        
        # 立即更新UI状态
        self.cancel_button.content.disabled = True  # 禁用取消按钮防止重复点击
        self.progress_text.value = "⚠️ 正在取消并清理资源..."
        try:
            self.cancel_button.update()
            self.progress_text.update()
        except:
            pass
        
        self._show_snackbar("正在取消处理，立即停止并清理资源...", ft.Colors.ORANGE)
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。"""
        if not self.selected_files:
            self._show_snackbar("请先选择视频文件", ft.Colors.ORANGE)
            return
        
        if not self.enhancer:
            self._show_snackbar("模型未加载，请稍候", ft.Colors.RED)
            return
        
        # 确定输出目录
        if self.output_mode_radio.value == "custom":
            output_dir = Path(self.custom_output_dir.value)
        else:
            output_dir = self.config_service.get_data_dir() / "video_enhanced"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 禁用处理按钮并显示进度
        self.is_processing = True
        self.should_cancel = False
        button = self.process_button.content
        button.disabled = True
        self.cancel_button.visible = True
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
            
            for file_idx, file_path in enumerate(self.selected_files):
                if self.should_cancel:
                    self._update_progress(0, "处理已取消")
                    break
                
                try:
                    self._update_progress(
                        file_idx / total_files,
                        f"正在处理: {file_path.name} ({file_idx+1}/{total_files})"
                    )
                    
                    # 处理单个视频
                    success = self._process_single_video(file_path, output_dir, file_idx, total_files)
                    
                    if success:
                        success_count += 1
                    
                except Exception as ex:
                    logger.error(f"处理失败 {file_path.name}: {ex}")
            
            # 处理完成
            self._on_process_complete(success_count, total_files, output_dir)
        
        threading.Thread(target=process_task, daemon=True).start()
    
    def _process_single_video(self, input_path: Path, output_dir: Path, file_idx: int, total_files: int) -> bool:
        """处理单个视频文件（使用管道方式，避免临时文件）。
        
        Args:
            input_path: 输入视频路径
            output_dir: 输出目录
            file_idx: 当前文件索引
            total_files: 总文件数
            
        Returns:
            是否成功
        """
        import ffmpeg
        from PIL import Image
        import numpy as np
        import subprocess
        
        temp_audio_file = None
        try:
            # 获取视频信息
            video_info = self.ffmpeg_service.safe_probe(str(input_path))
            if not video_info:
                logger.error(f"无法获取视频信息: {input_path}")
                return False
            
            # 获取视频流信息
            video_stream = None
            for stream in video_info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                logger.error(f"视频没有视频流: {input_path}")
                return False
            
            # 获取视频参数
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            
            # 获取帧率（处理分数形式）
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den)
            else:
                fps = float(fps_str)
            
            duration = float(video_info.get('format', {}).get('duration', 0))
            total_frames = int(duration * fps)
            
            if total_frames == 0:
                logger.error(f"无法计算视频帧数: {input_path}")
                return False
            
            # 获取增强倍率
            scale = self.scale_slider.value
            enhanced_width = int(width * scale)
            enhanced_height = int(height * scale)
            
            # 生成输出路径
            output_format = self.output_format_dropdown.value
            if output_format == "same":
                output_ext = input_path.suffix
            else:
                output_ext = f".{output_format}"
            
            if self.output_mode_radio.value == "new":
                output_filename = f"{input_path.stem}_enhanced{output_ext}"
                output_path = input_path.parent / output_filename
            else:
                output_filename = f"{input_path.stem}_enhanced{output_ext}"
                output_path = output_dir / output_filename
            
            # 根据全局设置决定是否添加序号
            add_sequence = self.config_service.get_config_value("output_add_sequence", False)
            output_path = get_unique_path(output_path, add_sequence=add_sequence)
            
            # 内存安全检查
            frame_memory_mb = (width * height * 3 + enhanced_width * enhanced_height * 3) / (1024 * 1024)
            
            logger.info("=" * 80)
            logger.info("✓ 使用管道模式处理视频（零临时文件，完全在内存中操作）")
            logger.info(f"输入: {width}x{height} → 输出: {enhanced_width}x{enhanced_height}")
            logger.info(f"单帧大小: {frame_memory_mb:.2f} MB")
            
            # 内存风险警告
            try:
                import psutil
                available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)
                estimated_peak_mb = frame_memory_mb * 10
                
                if estimated_peak_mb > available_memory_mb * 0.5:
                    logger.warning(f"⚠️  高内存占用警告: 估算峰值 {estimated_peak_mb:.0f}MB / 可用 {available_memory_mb:.0f}MB")
                    logger.warning("建议：关闭其他程序或降低视频分辨率")
            except:
                pass
            
            logger.info("=" * 80)
            
            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
            
            # 检测可用的硬件加速方式（用于视频解码）
            decoder_kwargs = {}
            use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
            if use_gpu:
                hw_accels = self.ffmpeg_service.detect_hw_accels()
                
                # 获取视频编码格式，以选择对应的硬件解码器
                video_codec = video_stream.get('codec_name', '').lower()
                logger.info(f"视频编码格式: {video_codec}")
                
                # 按优先级选择硬件加速方式
                if 'cuda' in hw_accels:
                    # NVIDIA CUDA 硬件解码
                    decoder_kwargs['hwaccel'] = 'cuda'
                    # 根据视频编码选择对应的 CUVID 解码器
                    if video_codec in ['h264', 'avc']:
                        decoder_kwargs['c:v'] = 'h264_cuvid'
                    elif video_codec in ['hevc', 'h265']:
                        decoder_kwargs['c:v'] = 'hevc_cuvid'
                    elif video_codec == 'vp9':
                        decoder_kwargs['c:v'] = 'vp9_cuvid'
                    elif video_codec in ['av1']:
                        decoder_kwargs['c:v'] = 'av1_cuvid'
                    elif video_codec in ['mpeg4']:
                        decoder_kwargs['c:v'] = 'mpeg4_cuvid'
                    elif video_codec in ['mpeg2video', 'mpeg2']:
                        decoder_kwargs['c:v'] = 'mpeg2_cuvid'
                    logger.info(f"✓ CUDA 硬件解码: {decoder_kwargs.get('c:v', 'auto')}")
                elif 'qsv' in hw_accels:
                    # Intel Quick Sync Video 硬件解码
                    decoder_kwargs['hwaccel'] = 'qsv'
                    if video_codec in ['h264', 'avc']:
                        decoder_kwargs['c:v'] = 'h264_qsv'
                    elif video_codec in ['hevc', 'h265']:
                        decoder_kwargs['c:v'] = 'hevc_qsv'
                    logger.info(f"✓ QSV 硬件解码: {decoder_kwargs.get('c:v', 'auto')}")
                elif 'd3d11va' in hw_accels:
                    decoder_kwargs['hwaccel'] = 'd3d11va'
                    logger.info("✓ D3D11VA 硬件加速解码")
                elif 'dxva2' in hw_accels:
                    decoder_kwargs['hwaccel'] = 'dxva2'
                    logger.info("✓ DXVA2 硬件加速解码")
            
            # 步骤1：创建解码器管道（视频 → 原始帧数据）
            self._update_progress(
                file_idx / total_files,
                f"[{file_idx+1}/{total_files}] 启动解码器..."
            )
            
            # 构建解码器输入
            decoder_input = ffmpeg.input(str(input_path), **decoder_kwargs)
            
            # 解码为原始 RGB24 数据并通过管道输出
            decoder_stream = decoder_input.output(
                'pipe:',
                format='rawvideo',
                pix_fmt='rgb24',
                vsync=0  # 不丢帧
            ).global_args('-hide_banner', '-loglevel', 'error')
            
            # 启动解码器进程
            logger.info("启动解码器管道...")
            decoder_process = decoder_stream.run_async(
                cmd=ffmpeg_path,
                pipe_stdout=True,
                pipe_stderr=True
            )
            
            # 步骤2：处理音频（如果有）
            has_audio = any(s.get('codec_type') == 'audio' for s in video_info.get('streams', []))
            if has_audio:
                # 提取音频到临时文件（因为管道模式下需要同步视频和音频）
                temp_audio_file = Path(tempfile.gettempdir()) / f"temp_audio_{input_path.stem}.aac"
                logger.info(f"提取音频到临时文件: {temp_audio_file}")
                
                audio_stream = ffmpeg.input(str(input_path)).output(
                    str(temp_audio_file),
                    acodec='copy',
                    vn=None
                ).global_args('-hide_banner', '-loglevel', 'error')
                
                ffmpeg.run(audio_stream, cmd=ffmpeg_path, overwrite_output=True)
            
            # 步骤3：创建编码器管道（原始帧数据 → 视频）
            logger.info("启动编码器管道...")
            
            # 获取输出质量参数
            crf = int(self.quality_slider.value)
            
            # 🔍 检查分辨率是否超过GPU编码器限制
            # NVENC/AMF 通常最大支持 4096x4096
            max_gpu_dimension = 4096
            resolution_too_large = enhanced_width > max_gpu_dimension or enhanced_height > max_gpu_dimension
            
            # 检测GPU编码器
            vcodec = 'libx264'
            preset = 'medium'
            gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
            
            if resolution_too_large:
                logger.warning("=" * 80)
                logger.warning(f"⚠️  输出分辨率 {enhanced_width}x{enhanced_height} 超过GPU编码器限制 ({max_gpu_dimension}x{max_gpu_dimension})")
                logger.warning("⚠️  自动回退到CPU编码器（libx264），速度会较慢")
                logger.warning("⚠️  建议：降低放大倍率以使用GPU加速编码")
                logger.warning("=" * 80)
                vcodec = 'libx264'
                preset = 'slow'  # 使用更好的压缩
            elif gpu_encoder:
                vcodec = gpu_encoder
                if gpu_encoder.startswith("h264_nvenc") or gpu_encoder.startswith("hevc_nvenc"):
                    preset = "p4"
                    logger.info(f"✓ NVENC 硬件编码: {vcodec}")
                elif gpu_encoder.startswith("h264_amf") or gpu_encoder.startswith("hevc_amf"):
                    preset = "balanced"
                    logger.info(f"✓ AMF 硬件编码: {vcodec}")
                elif gpu_encoder.startswith("h264_qsv") or gpu_encoder.startswith("hevc_qsv"):
                    logger.info(f"✓ QSV 硬件编码: {vcodec}")
            else:
                logger.info("使用CPU编码器: libx264")
            
            # 构建编码器输出参数
            encoder_output_params = {
                'vcodec': vcodec,
                'pix_fmt': 'yuv420p',
                'r': fps,
            }
            
            # 根据编码器设置质量参数
            if vcodec in ["libx264", "libx265"]:
                encoder_output_params['crf'] = crf
                encoder_output_params['preset'] = preset
            elif vcodec.startswith("h264_nvenc") or vcodec.startswith("hevc_nvenc"):
                encoder_output_params['cq'] = crf
                encoder_output_params['preset'] = preset
            elif vcodec.startswith("h264_amf") or vcodec.startswith("hevc_amf"):
                encoder_output_params['quality'] = preset
                encoder_output_params['rc'] = 'vbr_peak'
                encoder_output_params['qmin'] = max(18, crf - 5)
                encoder_output_params['qmax'] = min(28, crf + 5)
            elif vcodec.startswith("h264_qsv") or vcodec.startswith("hevc_qsv"):
                encoder_output_params['global_quality'] = crf
                encoder_output_params['preset'] = preset
            
            # 编码器输入（从管道接收原始帧数据）
            encoder_input = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt='rgb24',
                s=f'{enhanced_width}x{enhanced_height}',
                r=fps
            )
            
            # 如果有音频，合成音频和视频
            if has_audio and temp_audio_file.exists():
                audio_input = ffmpeg.input(str(temp_audio_file))
                encoder_stream = ffmpeg.output(
                    encoder_input,
                    audio_input.audio,
                    str(output_path),
                    acodec='aac',
                    audio_bitrate='192k',
                    **encoder_output_params
                ).global_args('-hide_banner', '-loglevel', 'error')
            else:
                encoder_stream = ffmpeg.output(
                    encoder_input,
                    str(output_path),
                    **encoder_output_params
                ).global_args('-hide_banner', '-loglevel', 'error')
            
            # 启动编码器进程
            encoder_process = encoder_stream.run_async(
                cmd=ffmpeg_path,
                pipe_stdin=True,
                pipe_stderr=True,
                overwrite_output=True
            )
            
            # 步骤4：异步流水线处理（解码 ⟷ 批量增强 ⟷ 编码 并行执行）
            logger.info("=" * 80)
            logger.info("🚀 使用异步流水线模式")
            
            frame_size = width * height * 3  # RGB24 格式
            enhanced_frame_size = enhanced_width * enhanced_height * 3
            
            # 内存监控
            frame_size_mb = frame_size / (1024 * 1024)
            enhanced_frame_size_mb = enhanced_frame_size / (1024 * 1024)
            logger.info(f"原始帧大小: {frame_size_mb:.2f} MB, 增强后: {enhanced_frame_size_mb:.2f} MB")
            
            # 🔥 关键优化：计算帧批量大小和队列深度
            # 根据分辨率和显存自动调整 - 增大批量以提高GPU利用率
            if enhanced_frame_size_mb > 50:  # 8K+
                frame_batch_size = 2  # 从1增加到2
                queue_depth = 4  # 从3增加到4
                logger.warning("⚠️  超高分辨率，小批量+浅队列")
                gc_interval = 10
                flush_interval = 5
            elif enhanced_frame_size_mb > 20:  # 4K
                frame_batch_size = 4  # 从2增加到4
                queue_depth = 6  # 从4增加到6
                logger.info("⚡ 4K分辨率，批量=4, 队列深度=6")
                gc_interval = 20
                flush_interval = 10
            elif enhanced_frame_size_mb > 8:  # 1440p
                frame_batch_size = 8  # 从4增加到8
                queue_depth = 10  # 从6增加到10
                logger.info("⚡ 2K分辨率，批量=8, 队列深度=10")
                gc_interval = 30
                flush_interval = 15
            else:  # 1080p及以下
                frame_batch_size = 12  # 从6增加到12
                queue_depth = 16  # 从8增加到16
                logger.info("✓ 1080p及以下，批量=12, 队列深度=16")
                gc_interval = 40
                flush_interval = 20
            
            logger.info(f"✓ 批量大小: {frame_batch_size}, 队列深度: {queue_depth} (保持GPU持续忙碌)")
            logger.info("✓ 异步流水线: 解码 ⟷ 推理 ⟷ 编码 并行执行")
            logger.info("=" * 80)
            
            frame_idx = 0
            last_gc_time = 0
            
            # 🔥 异步流水线：使用队列实现生产者-消费者模式
            from queue import Queue
            from threading import Thread, Event, Lock
            
            raw_frame_queue = Queue(maxsize=queue_depth)  # 原始帧队列
            enhanced_frame_queue = Queue(maxsize=queue_depth)  # 增强后帧队列
            stop_event = Event()  # 停止信号
            error_event = Event()  # 错误信号
            error_msg = []  # 错误消息
            
            # 解码线程：读取帧 → raw_frame_queue
            def decoder_worker():
                try:
                    while not self.should_cancel and not stop_event.is_set():
                        raw_frame = decoder_process.stdout.read(frame_size)
                        
                        if len(raw_frame) != frame_size:
                            break  # EOF
                        
                        frame_array = np.frombuffer(raw_frame, dtype=np.uint8).reshape([height, width, 3])
                        raw_frame_queue.put(frame_array)  # 阻塞直到队列有空间
                    
                    raw_frame_queue.put(None)  # EOF信号
                except Exception as e:
                    logger.error(f"解码线程错误: {e}")
                    error_msg.append(str(e))
                    error_event.set()
                    raw_frame_queue.put(None)
            
            # 推理线程：raw_frame_queue → 批量增强 → enhanced_frame_queue
            # 🔥 关键优化：使用激进的批量收集策略，最大化GPU利用率
            def inference_worker():
                try:
                    import time
                    
                    while not self.should_cancel and not error_event.is_set():
                        frame_buffer = []
                        
                        # 🚀 激进策略：尽可能快地收集帧，不等待
                        # 第一帧用阻塞等待
                        first_frame = raw_frame_queue.get()
                        
                        if first_frame is None:  # EOF
                            enhanced_frame_queue.put(None)
                            break
                        
                        frame_buffer.append(first_frame)
                        
                        # 后续帧用非阻塞方式快速收集，最多等待10ms
                        start_time = time.time()
                        max_wait = 0.01  # 10ms超时，避免GPU空闲
                        
                        while len(frame_buffer) < frame_batch_size:
                            elapsed = time.time() - start_time
                            if elapsed > max_wait:
                                break  # 超时，立即处理已有的帧
                            
                            try:
                                # 非阻塞获取，最多等1ms
                                frame = raw_frame_queue.get(timeout=0.001)
                                if frame is None:  # EOF
                                    # 处理buffer中的帧，然后退出
                                    if frame_buffer:
                                        enhanced_frames = self._batch_enhance_frames(
                                            frame_buffer, enhanced_width, enhanced_height
                                        )
                                        for ef in enhanced_frames:
                                            enhanced_frame_queue.put(ef)
                                    enhanced_frame_queue.put(None)
                                    return
                                frame_buffer.append(frame)
                            except:
                                break  # 队列空，立即处理
                        
                        # 立即处理收集到的帧（即使不满batch_size）
                        if frame_buffer:
                            enhanced_frames = self._batch_enhance_frames(
                                frame_buffer, enhanced_width, enhanced_height
                            )
                            
                            if not enhanced_frames:
                                raise RuntimeError("批量增强失败")
                            
                            for ef in enhanced_frames:
                                enhanced_frame_queue.put(ef)
                
                except Exception as e:
                    logger.error(f"推理线程错误: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    error_msg.append(str(e))
                    error_event.set()
                    enhanced_frame_queue.put(None)
            
            # 启动工作线程
            # 注意：DirectML不支持多线程并发推理，所以使用单推理线程
            # 但使用激进的帧收集策略（10ms超时）来最大化GPU利用率
            
            decoder_thread = Thread(target=decoder_worker, daemon=True, name="Decoder")
            inference_thread = Thread(target=inference_worker, daemon=True, name="Inference")
            
            decoder_thread.start()
            inference_thread.start()
            
            logger.info("✓ 异步流水线已启动：解码线程 + 推理线程并行运行")
            logger.info("✓ 使用激进帧收集策略（10ms超时），最小化GPU等待时间")
            
            # 主线程：enhanced_frame_queue → 编码器（不阻塞）
            try:
                while True:
                    # 检查取消和错误
                    if self.should_cancel:
                        logger.warning("用户取消处理")
                        stop_event.set()
                        break
                    
                    if error_event.is_set():
                        logger.error(f"工作线程错误: {error_msg}")
                        return False
                    
                    # 🔥 从队列获取增强后的帧（非阻塞检查）
                    try:
                        enhanced_array = enhanced_frame_queue.get(timeout=0.1)
                    except:
                        continue  # 队列空，继续等待
                    
                    # EOF信号
                    if enhanced_array is None:
                        logger.info("所有帧处理完成")
                        break
                    
                    # 验证帧
                    if enhanced_array.shape != (enhanced_height, enhanced_width, 3):
                        logger.error(f"增强后的帧尺寸不匹配: {enhanced_array.shape}")
                        stop_event.set()
                        return False
                    
                    # 确保数据类型正确
                    if enhanced_array.dtype != np.uint8:
                        enhanced_array = enhanced_array.astype(np.uint8)
                    
                    # 写入编码器
                    try:
                        encoder_process.stdin.write(enhanced_array.tobytes())
                    except BrokenPipeError:
                        logger.error("编码器管道断开")
                        try:
                            encoder_stderr = encoder_process.stderr.read().decode('utf-8', errors='ignore')
                            if encoder_stderr:
                                logger.error(f"编码器错误信息: {encoder_stderr}")
                        except:
                            pass
                        stop_event.set()
                        return False
                    except Exception as e:
                        logger.error(f"写入编码器失败: {e}")
                        stop_event.set()
                        return False
                    
                    frame_idx += 1
                    
                    # 定期刷新管道
                    if frame_idx % flush_interval == 0:
                        encoder_process.stdin.flush()
                    
                    # 定期垃圾回收和进度更新
                    if frame_idx % gc_interval == 0:
                        gc.collect()
                        if frame_idx % (gc_interval * 3) == 0:
                            try:
                                import psutil
                                process = psutil.Process()
                                memory_mb = process.memory_info().rss / (1024 * 1024)
                                logger.info(f"内存占用: {memory_mb:.1f} MB (已处理 {frame_idx} 帧)")
                            except:
                                pass
                    
                    # 更新进度
                    if frame_idx % 10 == 0 or frame_idx == 1:
                        file_progress = file_idx / total_files
                        frame_progress = min(frame_idx / total_frames, 1.0) if total_frames > 0 else 0
                        overall_progress = file_progress + (frame_progress / total_files)
                        
                        # 显示队列状态
                        queue_info = f"队列: {raw_frame_queue.qsize()}/{enhanced_frame_queue.qsize()}"
                        
                        self._update_progress(
                            overall_progress,
                            f"[{file_idx+1}/{total_files}] 处理帧 {frame_idx}/{total_frames} | {queue_info}"
                        )
                
            except MemoryError:
                logger.error("❌ 内存不足！建议：1)关闭其他程序 2)降低batch_size")
                stop_event.set()
                return False
            except Exception as e:
                logger.error(f"处理帧时发生错误: {e}")
                import traceback
                logger.error(traceback.format_exc())
                stop_event.set()
                return False
            finally:
                # 等待工作线程结束
                stop_event.set()
                logger.info("等待工作线程结束...")
                decoder_thread.join(timeout=2)
                inference_thread.join(timeout=2)
                logger.info("工作线程已结束")
            
            
            # 步骤5：关闭管道并等待进程完成
            if self.should_cancel:
                # 用户取消：立即终止所有进程
                logger.warning("=" * 80)
                logger.warning("⚠️  用户取消，立即终止所有进程...")
                logger.warning("=" * 80)
                
                try:
                    decoder_process.terminate()
                    encoder_process.terminate()
                    
                    # 给进程1秒时间优雅退出
                    import time
                    time.sleep(0.5)
                    
                    # 如果还没退出，强制杀死
                    try:
                        decoder_process.kill()
                    except:
                        pass
                    try:
                        encoder_process.kill()
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"终止进程时出错: {e}")
                
                # 删除不完整的输出文件
                if output_path.exists():
                    try:
                        output_path.unlink()
                        logger.info(f"已删除不完整的输出文件: {output_path}")
                    except Exception as e:
                        logger.warning(f"删除不完整文件失败: {e}")
                
                logger.info(f"✓ 已取消，共处理了 {frame_idx} 帧")
                return False
            
            # 正常完成：等待进程完成
            logger.info(f"共处理 {frame_idx} 帧，等待编码器完成...")
            
            # 关闭编码器输入（触发编码器完成）
            try:
                encoder_process.stdin.close()
            except:
                pass
            
            # 等待解码器完成
            decoder_process.wait()
            decoder_stderr = decoder_process.stderr.read().decode('utf-8', errors='ignore')
            if decoder_stderr:
                logger.warning(f"解码器输出: {decoder_stderr}")
            
            # 等待编码器完成
            encoder_returncode = encoder_process.wait()
            encoder_stderr = encoder_process.stderr.read().decode('utf-8', errors='ignore')
            
            if encoder_returncode != 0:
                logger.error(f"编码器失败 (返回码 {encoder_returncode}): {encoder_stderr}")
                return False
            
            if encoder_stderr:
                logger.info(f"编码器输出: {encoder_stderr}")
            
            logger.info("=" * 80)
            logger.info(f"✓ 视频处理完成: {output_path}")
            logger.info(f"✓ 处理了 {frame_idx} 帧，无临时文件产生")
            logger.info("=" * 80)
            
            return True
            
        except Exception as ex:
            logger.error(f"处理视频失败 {input_path}: {ex}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 发生错误时也要终止进程
            try:
                if 'decoder_process' in locals():
                    decoder_process.terminate()
                    try:
                        decoder_process.kill()
                    except:
                        pass
            except:
                pass
            
            try:
                if 'encoder_process' in locals():
                    encoder_process.terminate()
                    try:
                        encoder_process.kill()
                    except:
                        pass
            except:
                pass
            
            return False
        finally:
            # 确保进程被终止（最后的保险）
            try:
                if 'decoder_process' in locals() and decoder_process.poll() is None:
                    logger.warning("清理残留的解码器进程...")
                    decoder_process.kill()
            except:
                pass
            
            try:
                if 'encoder_process' in locals() and encoder_process.poll() is None:
                    logger.warning("清理残留的编码器进程...")
                    encoder_process.kill()
            except:
                pass
            
            # 清理临时音频文件
            if temp_audio_file and temp_audio_file.exists():
                try:
                    temp_audio_file.unlink()
                    logger.info(f"清理临时音频文件: {temp_audio_file}")
                except Exception:
                    pass
    
    def _batch_enhance_frames(
        self,
        frame_arrays: list,
        enhanced_width: int,
        enhanced_height: int
    ) -> list:
        """批量增强多帧（关键性能优化）。
        
        Args:
            frame_arrays: 输入帧数组列表 [(H, W, 3), ...]，RGB格式
            enhanced_width: 增强后的宽度
            enhanced_height: 增强后的高度
        
        Returns:
            增强后的帧数组列表 [(H', W', 3), ...]，RGB格式
        """
        from PIL import Image
        import numpy as np
        
        enhanced_frames = []
        
        try:
            # 验证输入
            if not frame_arrays:
                logger.error("_batch_enhance_frames: 输入帧数组为空")
                return []
            
            logger.debug(f"批量增强 {len(frame_arrays)} 帧，目标尺寸: {enhanced_width}x{enhanced_height}")
            
            # 将numpy数组转换为PIL Images
            frame_images = []
            for idx, frame_array in enumerate(frame_arrays):
                if frame_array is None:
                    logger.error(f"帧 {idx} 为 None")
                    return []
                
                if len(frame_array.shape) != 3 or frame_array.shape[2] != 3:
                    logger.error(f"帧 {idx} 形状错误: {frame_array.shape}")
                    return []
                
                frame_image = Image.fromarray(frame_array, mode='RGB')
                frame_images.append(frame_image)
            
            logger.debug(f"已转换 {len(frame_images)} 个PIL图像，开始增强...")
            
            # 🚀 批量增强（关键：这会在tile级别使用批量推理）
            enhanced_images = self.enhancer.enhance_image_batch(frame_images)
            
            if not enhanced_images:
                logger.error("enhance_image_batch 返回空列表")
                raise RuntimeError("批量增强返回空结果")
            
            if len(enhanced_images) != len(frame_images):
                logger.error(f"增强结果数量不匹配: {len(enhanced_images)} vs {len(frame_images)}")
                raise RuntimeError("批量增强结果数量不匹配")
            
            logger.debug(f"批量增强完成，转换回numpy数组...")
            
            # 转换回numpy数组
            for idx, enhanced_image in enumerate(enhanced_images):
                if enhanced_image is None:
                    logger.error(f"增强图像 {idx} 为 None")
                    raise RuntimeError(f"增强图像 {idx} 为 None")
                
                enhanced_array = np.array(enhanced_image, dtype=np.uint8)
                
                # 验证尺寸
                if enhanced_array.shape != (enhanced_height, enhanced_width, 3):
                    logger.error(f"增强帧 {idx} 尺寸错误: {enhanced_array.shape} vs ({enhanced_height}, {enhanced_width}, 3)")
                    raise RuntimeError(f"增强帧尺寸错误")
                
                enhanced_frames.append(enhanced_array)
            
            logger.debug(f"✓ 批量增强成功，返回 {len(enhanced_frames)} 帧")
            return enhanced_frames
            
        except Exception as e:
            # 如果批量处理失败，回退到逐个处理
            error_msg = str(e)
            
            # 检测显存不足错误
            if any(keyword in error_msg.lower() for keyword in [
                "available memory", "out of memory", "显存不足"
            ]):
                logger.warning(f"GPU 显存不足，回退到逐帧处理...")
            else:
                logger.warning(f"帧批量增强失败，回退到逐帧处理: {e}")
                import traceback
                logger.warning(traceback.format_exc())
            
            enhanced_frames.clear()
            
            try:
                for idx, frame_image in enumerate(frame_images):
                    logger.debug(f"逐帧处理: {idx+1}/{len(frame_images)}")
                    enhanced_image = self.enhancer.enhance_image(frame_image)
                    enhanced_array = np.array(enhanced_image, dtype=np.uint8)
                    
                    # 验证尺寸
                    if enhanced_array.shape != (enhanced_height, enhanced_width, 3):
                        logger.error(f"逐帧增强后尺寸错误: {enhanced_array.shape}")
                        return []
                    
                    enhanced_frames.append(enhanced_array)
                
                logger.info(f"✓ 逐帧处理完成，返回 {len(enhanced_frames)} 帧")
                return enhanced_frames
            except Exception as e2:
                error_msg = str(e2)
                # 检测显存不足错误并给出友好提示
                if any(keyword in error_msg.lower() for keyword in [
                    "available memory", "out of memory", "显存不足"
                ]):
                    logger.error(f"GPU 显存不足，无法处理。建议：降低内存限制、处理较小视频或使用 CPU 模式")
                else:
                    logger.error(f"逐帧处理也失败: {e2}")
                    import traceback
                    logger.error(traceback.format_exc())
                return []
    
    def _update_progress(self, value: float, text: str) -> None:
        """更新进度显示。"""
        if self.is_destroyed:
            return  # 视图已销毁，不更新UI
        
        self.progress_bar.value = value
        self.progress_text.value = text
        try:
            self.page.update()
        except:
            pass
    
    def _on_process_complete(self, success_count: int, total: int, output_dir: Path) -> None:
        """处理完成回调。"""
        if self.is_destroyed:
            logger.info(f"视图已销毁，跳过完成回调（成功: {success_count}/{total}）")
            return  # 视图已销毁，不更新UI
        
        self.is_processing = False
        self.progress_bar.value = 1.0
        
        if self.should_cancel:
            self.progress_text.value = f"处理已取消! 已完成: {success_count}/{total}"
        else:
            self.progress_text.value = f"处理完成! 成功: {success_count}/{total}"
        
        button = self.process_button.content
        button.disabled = False
        self.cancel_button.visible = False
        
        try:
            self.page.update()
        except:
            pass
        
        if self.should_cancel:
            self._show_snackbar(f"处理已取消，已完成 {success_count} 个文件", ft.Colors.ORANGE)
        elif self.output_mode_radio.value == "new":
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
        if self.is_destroyed or not self.page:
            logger.debug(f"视图已销毁，跳过snackbar: {message}")
            return  # 视图已销毁或page不存在，不显示消息
        
        try:
            snackbar: ft.SnackBar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=color,
                duration=3000,
            )
            self.page.overlay.append(snackbar)
            snackbar.open = True
            self.page.update()
        except Exception as e:
            logger.debug(f"显示snackbar失败（可能视图已销毁）: {e}")
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。"""
        # 如果UI尚未构建完成，保存文件待后续处理
        if not self._ui_built or not hasattr(self, 'file_list_view'):
            self._pending_files.extend(files)
            return
        
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
            self._show_snackbar("视频增强不支持该格式", ft.Colors.ORANGE)
        self.page.update()
    
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
            self._show_snackbar(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        try:
            self.page.update()
        except:
            pass
    
    def cleanup(self) -> None:
        """清理资源，停止所有后台任务。"""
        logger.info("开始清理视频增强视图...")
        
        # 标记视图已销毁，防止后台线程更新UI
        self.is_destroyed = True
        
        if self.is_processing:
            logger.warning("视图被销毁，取消正在进行的任务...")
            self.should_cancel = True
            
            # 等待一小段时间让任务清理
            import time
            time.sleep(0.5)
        
        # 清理文件列表
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        
        # 卸载增强模型（使用 unload_model 更彻底地释放内存）
        if hasattr(self, 'enhancer') and self.enhancer:
            if hasattr(self.enhancer, 'unload_model'):
                self.enhancer.unload_model()
            self.enhancer = None
        
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        
        gc.collect()
        logger.info("✓ 视频增强视图已清理")
