# -*- coding: utf-8 -*-
"""音视频转文字视图模块。

提供音视频语音识别转文字功能的用户界面。
"""

import threading
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_WHISPER_MODEL_KEY,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_LARGE,
    WHISPER_MODELS,
)
from services import ConfigService, SpeechRecognitionService, FFmpegService
from utils import format_file_size, logger
from views.media.ffmpeg_install_view import FFmpegInstallView


class AudioToTextView(ft.Container):
    """音视频转文字视图类。
    
    提供音视频语音识别功能，包括：
    - 单文件处理
    - 批量处理
    - 实时进度显示
    - 支持多种音频/视频格式
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化音视频转文字视图。
        
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
        self.is_processing: bool = False
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 初始化服务
        model_dir = self.config_service.get_data_dir() / "models" / "whisper"
        self.speech_service: SpeechRecognitionService = SpeechRecognitionService(
            model_dir,
            ffmpeg_service
        )
        self.model_loading: bool = False
        self.model_loaded: bool = False
        self.auto_load_model: bool = self.config_service.get_config_value("whisper_auto_load_model", True)
        
        # 当前选择的模型
        saved_model_key = self.config_service.get_config_value(
            "whisper_model_key",
            DEFAULT_WHISPER_MODEL_KEY
        )
        if saved_model_key not in WHISPER_MODELS:
            saved_model_key = DEFAULT_WHISPER_MODEL_KEY
        self.current_model_key: str = saved_model_key
        self.current_model = WHISPER_MODELS[self.current_model_key]
        
        # 构建界面
        self._build_ui()
    
    def _check_cuda_available(self) -> bool:
        """检测是否支持 CUDA。
        
        Returns:
            True 如果支持 CUDA，否则 False
        """
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            return 'CUDAExecutionProvider' in available_providers
        except ImportError:
            return False
        except Exception as e:
            logger.warning(f"检测 CUDA 支持时出错: {e}")
            return False
    
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
                tool_name="音视频转文字"
            )
            return
        
        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("音视频转文字", size=28, weight=ft.FontWeight.BOLD),
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
        
        # 文件选择器
        self.file_picker = ft.FilePicker(
            on_result=self._on_files_selected
        )
        self.page.overlay.append(self.file_picker)
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择音视频:", size=14, weight=ft.FontWeight.W_500),
                        ft.ElevatedButton(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=lambda _: self._on_select_files(),
                        ),
                        ft.ElevatedButton(
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
                                "支持格式: MP3, WAV, FLAC, M4A, MP4, MKV, AVI 等音视频格式",
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
                    height=220,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 模型选择区域
        model_options = []
        for model_key, model_info in WHISPER_MODELS.items():
            option_text = f"{model_info.display_name}  |  {model_info.size_mb}MB  |  {model_info.language_support}"
            model_options.append(
                ft.dropdown.Option(key=model_key, text=option_text)
            )
        
        self.model_dropdown = ft.Dropdown(
            options=model_options,
            value=self.current_model_key,
            label="选择模型",
            hint_text="选择语音识别模型",
            on_change=self._on_model_change,
            width=600,
            dense=True,
            text_size=13,
        )
        
        # 模型信息显示
        self.model_info_text = ft.Text(
            f"{self.current_model.quality} | {self.current_model.performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 模型状态显示
        self.model_status_icon = ft.Icon(
            ft.Icons.CLOUD_DOWNLOAD,
            size=20,
            color=ft.Colors.ORANGE,
        )
        
        self.model_status_text = ft.Text(
            "未下载",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 下载模型按钮
        self.download_model_button = ft.ElevatedButton(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_model,
            visible=False,
        )
        
        self.load_model_button = ft.ElevatedButton(
            "加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model_click,
            visible=False,
        )

        self.unload_model_button = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型",
            on_click=self._on_unload_model_click,
            visible=False,
        )

        # 重载模型按钮
        self.reload_model_button = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_color=ft.Colors.BLUE,
            tooltip="重新加载模型",
            on_click=self._on_reload_model_click,
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
                self.reload_model_button,
                self.delete_model_button,
            ],
            spacing=PADDING_SMALL,
        )

        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=self.auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        model_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    self.model_dropdown,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                    self.auto_load_checkbox,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 初始化模型状态
        self._init_model_status()
        if self.auto_load_model:
            self._try_auto_load_model()
        
        # 输出设置区域
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            hint_text="选择输出文件格式",
            value="txt",
            options=[
                ft.dropdown.Option(key="txt", text="TXT 文本文件"),
                ft.dropdown.Option(key="srt", text="SRT 字幕文件"),
                ft.dropdown.Option(key="vtt", text="VTT 字幕文件"),
            ],
            width=200,
            dense=True,
        )
        
        # 语言选择
        saved_language = self.config_service.get_config_value("whisper_language", "zh")
        self.language_dropdown = ft.Dropdown(
            label="输出语言",
            hint_text="选择音频语言",
            value=saved_language,
            options=[
                ft.dropdown.Option(key="zh", text="中文 (Chinese)"),
                ft.dropdown.Option(key="en", text="英语 (English)"),
                ft.dropdown.Option(key="ja", text="日语 (Japanese)"),
                ft.dropdown.Option(key="ko", text="韩语 (Korean)"),
                ft.dropdown.Option(key="fr", text="法语 (French)"),
                ft.dropdown.Option(key="de", text="德语 (German)"),
                ft.dropdown.Option(key="es", text="西班牙语 (Spanish)"),
                ft.dropdown.Option(key="ru", text="俄语 (Russian)"),
                ft.dropdown.Option(key="ar", text="阿拉伯语 (Arabic)"),
                ft.dropdown.Option(key="pt", text="葡萄牙语 (Portuguese)"),
            ],
            width=180,
            dense=True,
            on_change=self._on_language_change,
        )
        
        # GPU加速设置
        # 检测是否支持 CUDA
        cuda_available = self._check_cuda_available()
        gpu_enabled = self.config_service.get_config_value("gpu_acceleration", True) if cuda_available else False
        
        self.gpu_checkbox = ft.Checkbox(
            label="启用 GPU 加速 (CUDA)" if cuda_available else "启用 GPU 加速 (不可用)",
            value=gpu_enabled,
            on_change=self._on_gpu_change,
            disabled=not cuda_available,
        )
        
        # GPU 加速提示
        if cuda_available:
            hint_text = "检测到 CUDA 支持，可使用 NVIDIA GPU 加速"
            hint_icon = ft.Icons.CHECK_CIRCLE
            hint_color = ft.Colors.GREEN
        else:
            hint_text = "sherpa要求使用CUDA，未检测到 CUDA 支持。请下载 MTools_Windows_CUDA 或 MTools_Linux_CUDA 版本"
            hint_icon = ft.Icons.INFO_OUTLINE
            hint_color = ft.Colors.ORANGE
        
        gpu_hint_text = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(hint_icon, size=14, color=hint_color),
                    ft.Text(
                        hint_text,
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(left=28),  # 对齐 checkbox
        )
        
        settings_row = ft.Row(
            controls=[
                self.output_format_dropdown,
                self.language_dropdown,
                ft.Column(
                    controls=[
                        self.gpu_checkbox,
                        gpu_hint_text,
                    ],
                    spacing=4,
                ),
            ],
            spacing=PADDING_MEDIUM,
            wrap=True,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    settings_row,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 处理按钮区域
        self.process_button = ft.Container(
            content=ft.ElevatedButton(
                "开始识别",
                icon=ft.Icons.PLAY_ARROW,
                on_click=self._on_process,
                disabled=True,
            ),
            alignment=ft.alignment.center,
        )
        
        # 进度显示区域
        self.progress_text = ft.Text(
            "",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.progress_bar = ft.ProgressBar(
            value=0,
            visible=False,
        )
        
        progress_section = ft.Column(
            controls=[
                self.progress_text,
                self.progress_bar,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                model_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
                ft.Container(height=PADDING_MEDIUM),
                self.process_button,
                ft.Container(height=PADDING_SMALL),
                progress_section,
                ft.Container(height=PADDING_LARGE),  # 底部留白
            ],
            spacing=0,
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
    
    def _init_empty_state(self) -> None:
        """初始化空文件列表状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.UPLOAD_FILE,
                            size=48,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "未选择文件",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "点击此处选择音视频文件",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL // 2,
                ),
                height=188,
                alignment=ft.alignment.center,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    def _check_all_model_files_exist(self) -> bool:
        """检查当前模型的所有必需文件是否存在。"""
        model_dir = self.speech_service.get_model_dir(self.current_model_key)
        encoder_path = model_dir / self.current_model.encoder_filename
        decoder_path = model_dir / self.current_model.decoder_filename
        config_path = model_dir / self.current_model.config_filename
        
        all_exist = encoder_path.exists() and decoder_path.exists() and config_path.exists()
        
        # 检查外部权重文件（如果需要）
        if self.current_model.encoder_weights_filename:
            weights_path = model_dir / self.current_model.encoder_weights_filename
            all_exist = all_exist and weights_path.exists()
        if self.current_model.decoder_weights_filename:
            weights_path = model_dir / self.current_model.decoder_weights_filename
            all_exist = all_exist and weights_path.exists()
        
        return all_exist
    
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
            self.reload_model_button.visible = False  # 只有加载后才显示
        else:
            # 模型未下载或不完整
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ORANGE
            self.model_status_text.value = "未下载"
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.delete_model_button.visible = False
            self.reload_model_button.visible = False
        
        try:
            self.page.update()
        except:
            pass
    
    def _try_auto_load_model(self) -> None:
        """尝试自动加载模型。"""
        if self._check_all_model_files_exist() and not self.model_loaded:
            threading.Thread(target=self._load_model_thread, daemon=True).start()
    
    def _on_model_change(self, e: ft.ControlEvent) -> None:
        """模型选择变更事件。"""
        new_key = e.control.value
        if new_key == self.current_model_key:
            return
        
        # 如果当前有模型加载，先卸载
        if self.model_loaded:
            self._unload_model()
        
        # 更新当前模型
        self.current_model_key = new_key
        self.current_model = WHISPER_MODELS[new_key]
        self.config_service.set_config_value("whisper_model_key", new_key)
        
        # 更新模型信息
        self.model_info_text.value = f"{self.current_model.quality} | {self.current_model.performance}"
        
        # 更新模型状态
        self._init_model_status()
        
        # 如果启用自动加载，尝试加载新模型
        if self.auto_load_model:
            self._try_auto_load_model()
    
    def _on_download_model(self, e: ft.ControlEvent) -> None:
        """下载模型按钮点击事件。"""
        if self.model_loading:
            return
        
        # 在后台线程中下载
        threading.Thread(target=self._download_model_thread, daemon=True).start()
    
    def _download_model_thread(self) -> None:
        """在后台线程中下载模型。"""
        try:
            self.model_loading = True
            
            # 更新UI
            self.download_model_button.disabled = True
            self.model_status_icon.name = ft.Icons.DOWNLOADING
            self.model_status_icon.color = ft.Colors.BLUE
            self.model_status_text.value = "正在下载..."
            try:
                self.page.update()
            except:
                pass
            
            # 下载进度回调
            def progress_callback(progress: float, message: str):
                self.model_status_text.value = message
                try:
                    self.page.update()
                except:
                    pass
            
            # 下载模型（encoder + decoder + config）
            encoder_path, decoder_path, config_path = self.speech_service.download_model(
                self.current_model_key,
                self.current_model,
                progress_callback
            )
            
            logger.info(f"Whisper模型下载完成: {encoder_path.name}, {decoder_path.name}, {config_path.name}")
            
            # 更新状态
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"下载完成 ({self.current_model.size_mb}MB)"
            self.download_model_button.visible = False
            self.load_model_button.visible = True
            self.delete_model_button.visible = True
            self.reload_model_button.visible = False  # 下载完成后还未加载
            
            # 如果启用自动加载，立即加载模型
            if self.auto_load_model:
                self._load_model_thread()
            
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"下载失败: {str(e)}"
            self.download_model_button.visible = True
        
        finally:
            self.model_loading = False
            self.download_model_button.disabled = False
            try:
                self.page.update()
            except:
                pass
    
    def _on_load_model_click(self, e: ft.ControlEvent) -> None:
        """加载模型按钮点击事件。"""
        if self.model_loading or self.model_loaded:
            return
        
        threading.Thread(target=self._load_model_thread, daemon=True).start()
    
    def _load_model_thread(self) -> None:
        """在后台线程中加载模型。"""
        try:
            self.model_loading = True
            
            # 更新UI
            self.load_model_button.disabled = True
            self.model_status_icon.name = ft.Icons.HOURGLASS_EMPTY
            self.model_status_icon.color = ft.Colors.BLUE
            self.model_status_text.value = "正在加载..."
            try:
                self.page.update()
            except:
                pass
            
            # 获取模型路径
            model_dir = self.speech_service.get_model_dir(self.current_model_key)
            encoder_path = model_dir / self.current_model.encoder_filename
            decoder_path = model_dir / self.current_model.decoder_filename
            config_path = model_dir / self.current_model.config_filename
            
            # GPU设置
            gpu_enabled = self.config_service.get_config_value("gpu_acceleration", True)
            gpu_device_id = self.config_service.get_config_value("gpu_device_id", 0)
            gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 2048)
            enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", True)
            
            # 获取选择的语言
            language = self.config_service.get_config_value("whisper_language", "zh")
            
            # 加载模型
            self.speech_service.load_model(
                encoder_path,
                decoder_path,
                config_path,
                use_gpu=gpu_enabled,
                gpu_device_id=gpu_device_id,
                gpu_memory_limit=gpu_memory_limit,
                enable_memory_arena=enable_memory_arena,
                language=language,  # 使用用户选择的语言
            )
            
            self.model_loaded = True
            
            # 获取设备信息
            device_info = self.speech_service.get_device_info()
            
            # 更新状态
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已加载 ({device_info})"
            self.load_model_button.visible = False
            self.unload_model_button.visible = True
            self.reload_model_button.visible = True
            
            logger.info(f"Whisper模型加载完成, 设备: {device_info}")
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"加载失败: {str(e)}"
            self.model_loaded = False
        
        finally:
            self.model_loading = False
            self.load_model_button.disabled = False
            self._update_process_button()
            try:
                self.page.update()
            except:
                pass
    
    def _on_unload_model_click(self, e: ft.ControlEvent) -> None:
        """卸载模型按钮点击事件。"""
        self._unload_model()
    
    def _on_reload_model_click(self, e: ft.ControlEvent) -> None:
        """重载模型按钮点击事件。"""
        if self.model_loading:
            return
        
        threading.Thread(target=self._reload_model_thread, daemon=True).start()
    
    def _reload_model_thread(self) -> None:
        """在后台线程中重载模型。"""
        try:
            logger.info("开始重载模型...")
            
            # 先卸载模型
            if self.model_loaded:
                self._unload_model()
            
            # 短暂延迟,确保资源释放
            import time
            time.sleep(0.5)
            
            # 重新加载模型
            self._load_model_thread()
            
        except Exception as e:
            logger.error(f"重载模型失败: {e}")
            self._show_error("重载失败", f"无法重载模型: {str(e)}")
    
    def _unload_model(self) -> None:
        """卸载模型。"""
        if not self.model_loaded:
            return
        
        try:
            self.speech_service.unload_model()
            self.model_loaded = False
            
            # 更新状态
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已下载 ({self.current_model.size_mb}MB)"
            self.load_model_button.visible = True
            self.unload_model_button.visible = False
            self.reload_model_button.visible = False
            
            logger.info("模型已卸载")
            
        except Exception as e:
            logger.error(f"卸载模型失败: {e}")
        
        finally:
            self._update_process_button()
            try:
                self.page.update()
            except:
                pass
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        def confirm_delete(e):
            dialog.open = False
            self.page.update()
            self._do_delete_model()
        
        def cancel_delete(e):
            dialog.open = False
            self.page.update()
        
        # 显示确认对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除模型"),
            content=ft.Text(
                "确定要删除此模型吗？\n\n"
                "删除后，您可以重新下载模型。\n"
                "如果模型损坏或加载失败（如 Protobuf parsing failed 错误），"
                "删除后重新下载可以解决问题。",
                size=14
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.TextButton("删除", on_click=confirm_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _do_delete_model(self) -> None:
        """执行删除模型操作。"""
        # 先卸载模型
        if self.model_loaded:
            self._unload_model()
        
        # 获取模型目录
        model_dir = self.speech_service.get_model_dir(self.current_model_key)
        
        # 删除所有模型文件
        encoder_path = model_dir / self.current_model.encoder_filename
        decoder_path = model_dir / self.current_model.decoder_filename
        config_path = model_dir / self.current_model.config_filename
        
        files_to_delete = [encoder_path, decoder_path, config_path]
        
        # 添加外部权重文件（如果有）
        if self.current_model.encoder_weights_filename:
            files_to_delete.append(model_dir / self.current_model.encoder_weights_filename)
        if self.current_model.decoder_weights_filename:
            files_to_delete.append(model_dir / self.current_model.decoder_weights_filename)
        
        try:
            deleted_files = []
            for file_path in files_to_delete:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(file_path.name)
            
            if deleted_files:
                logger.info(f"模型文件已删除: {', '.join(deleted_files)}")
            
            # 如果模型目录为空,也删除目录
            try:
                if model_dir.exists() and not any(model_dir.iterdir()):
                    model_dir.rmdir()
                    logger.info(f"模型目录已删除: {model_dir.name}")
            except:
                pass
            
            # 更新状态
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ORANGE
            self.model_status_text.value = "未下载"
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.reload_model_button.visible = False
            self.delete_model_button.visible = False
            
        except Exception as e:
            logger.error(f"删除模型文件失败: {e}")
            self._show_error("删除失败", f"无法删除模型文件: {str(e)}")
        
        try:
            self.page.update()
        except:
            pass
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型选项变更事件。"""
        self.auto_load_model = e.control.value
        self.config_service.set_config_value("whisper_auto_load_model", self.auto_load_model)
    
    def _on_gpu_change(self, e: ft.ControlEvent) -> None:
        """GPU加速选项变更事件。"""
        gpu_enabled = e.control.value
        self.config_service.set_config_value("gpu_acceleration", gpu_enabled)
        
        # 如果当前有模型加载，提示需要重新加载
        if self.model_loaded:
            self._show_info("提示", "GPU设置已更改，需要重新加载模型才能生效。")
    
    def _on_language_change(self, e: ft.ControlEvent) -> None:
        """语言选择变更事件。"""
        language = e.control.value
        self.config_service.set_config_value("whisper_language", language)
        
        # 如果当前有模型加载，提示需要重新加载
        if self.model_loaded:
            self._show_info("提示", "识别语言已更改，需要重新加载模型才能生效。")
    
    def _on_select_files(self) -> None:
        """选择文件按钮点击事件。"""
        self.file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=["mp3", "wav", "flac", "m4a", "aac", "ogg", "wma", "mp4", "mkv", "avi", "mov", "flv", "wmv"],
            dialog_title="选择音视频文件",
        )
    
    def _on_select_folder(self) -> None:
        """选择文件夹按钮点击事件。"""
        self.file_picker.get_directory_path(dialog_title="选择包含音视频文件的文件夹")
    
    def _on_files_selected(self, e: ft.FilePickerResultEvent) -> None:
        """文件选择完成事件。"""
        if e.files:
            # 添加文件到列表
            for file in e.files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            
            self._update_file_list()
            self._update_process_button()
        
        elif e.path:
            # 选择了文件夹
            folder_path = Path(e.path)
            audio_extensions = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
            video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
            
            for file_path in folder_path.iterdir():
                if file_path.suffix.lower() in audio_extensions | video_extensions:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            
            self._update_file_list()
            self._update_process_button()
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._init_empty_state()
        self._update_process_button()
        try:
            self.page.update()
        except:
            pass
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if not self.selected_files:
            self._init_empty_state()
            return
        
        file_items = []
        for file_path in self.selected_files:
            file_size = format_file_size(file_path.stat().st_size)
            
            file_item = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUDIOTRACK if file_path.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a"] else ft.Icons.VIDEO_FILE, size=20),
                        ft.Column(
                            controls=[
                                ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                ft.Text(file_size, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_size=16,
                            tooltip="移除",
                            on_click=lambda e, fp=file_path: self._remove_file(fp),
                        ),
                    ],
                    spacing=PADDING_SMALL,
                ),
                padding=PADDING_SMALL,
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            file_items.append(file_item)
        
        self.file_list_view.controls = file_items
        try:
            self.page.update()
        except:
            pass
    
    def _remove_file(self, file_path: Path) -> None:
        """从列表中移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
            self._update_process_button()
    
    def _update_process_button(self) -> None:
        """更新处理按钮状态。"""
        button = self.process_button.content
        button.disabled = not (self.selected_files and self.model_loaded and not self.is_processing)
        try:
            self.page.update()
        except:
            pass
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。"""
        if self.is_processing or not self.selected_files or not self.model_loaded:
            return
        
        # 在后台线程中处理
        threading.Thread(target=self._process_files_thread, daemon=True).start()
    
    def _process_files_thread(self) -> None:
        """在后台线程中处理文件。"""
        try:
            self.is_processing = True
            self._update_process_button()
            
            # 显示进度条
            self.progress_bar.visible = True
            self.progress_bar.value = 0
            try:
                self.page.update()
            except:
                pass
            
            total_files = len(self.selected_files)
            
            for i, file_path in enumerate(self.selected_files):
                try:
                    # 更新进度
                    self.progress_text.value = f"正在处理: {file_path.name} ({i+1}/{total_files})"
                    self.progress_bar.value = i / total_files
                    try:
                        self.page.update()
                    except:
                        pass
                    
                    # 进度回调
                    def progress_callback(message: str, progress: float):
                        self.progress_text.value = f"{file_path.name}: {message}"
                        file_progress = (i + progress) / total_files
                        self.progress_bar.value = file_progress
                        try:
                            self.page.update()
                        except:
                            pass
                    
                    # 识别语音
                    text = self.speech_service.recognize(file_path, progress_callback)
                    
                    # 保存结果
                    output_format = self.output_format_dropdown.value
                    output_path = file_path.with_suffix(f".{output_format}")
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    
                    logger.info(f"识别完成: {file_path} -> {output_path}")
                    
                except Exception as e:
                    logger.error(f"处理文件失败 {file_path}: {e}")
                    self._show_error("处理失败", f"文件 {file_path.name} 处理失败: {str(e)}")
            
            # 完成
            self.progress_text.value = f"全部完成! 共处理 {total_files} 个文件"
            self.progress_bar.value = 1.0
            
            self._show_success("处理完成", f"成功处理 {total_files} 个文件")
            
        except Exception as e:
            logger.error(f"批量处理失败: {e}")
            self._show_error("处理失败", str(e))
        
        finally:
            self.is_processing = False
            self._update_process_button()
            
            # 隐藏进度条
            self.progress_bar.visible = False
            try:
                self.page.update()
            except:
                pass
    
    def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        self._on_select_files()
    
    def _on_back_click(self, e: ft.ControlEvent = None) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back(e)
    
    def _show_error(self, title: str, message: str) -> None:
        """显示错误对话框。"""
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("确定", on_click=lambda e: self._close_dialog(dialog)),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        try:
            self.page.update()
        except:
            pass
    
    def _show_success(self, title: str, message: str) -> None:
        """显示成功对话框。"""
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("确定", on_click=lambda e: self._close_dialog(dialog)),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        try:
            self.page.update()
        except:
            pass
    
    def _show_info(self, title: str, message: str) -> None:
        """显示信息对话框。"""
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("确定", on_click=lambda e: self._close_dialog(dialog)),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        try:
            self.page.update()
        except:
            pass
    
    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        """关闭对话框。"""
        dialog.open = False
        try:
            self.page.update()
        except:
            pass
    
    def cleanup(self) -> None:
        """清理资源。"""
        if self.speech_service:
            self.speech_service.cleanup()

