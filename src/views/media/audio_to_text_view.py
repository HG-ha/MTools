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
    DEFAULT_SENSEVOICE_MODEL_KEY,
    DEFAULT_VAD_MODEL_KEY,
    DEFAULT_VOCAL_MODEL_KEY,
    DEFAULT_PUNCTUATION_MODEL_KEY,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_LARGE,
    WHISPER_MODELS,
    SENSEVOICE_MODELS,
    VAD_MODELS,
    VOCAL_SEPARATION_MODELS,
    PUNCTUATION_MODELS,
    SenseVoiceModelInfo,
    WhisperModelInfo,
)
from services import ConfigService, SpeechRecognitionService, FFmpegService, VADService, VocalSeparationService, AISubtitleFixService
from utils import format_file_size, logger, segments_to_srt, segments_to_vtt, segments_to_txt, segments_to_lrc, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class AudioToTextView(ft.Container):
    """音视频转文字视图类。
    
    提供音视频语音识别功能，包括："""
    
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
    
    """
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
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        self.is_processing: bool = False
        # 缓存：文件路径 -> 是否有音频流
        self._audio_stream_cache: dict = {}
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 初始化服务
        model_dir = self.config_service.get_data_dir() / "models" / "whisper"
        vad_model_dir = self.config_service.get_data_dir() / "models" / "vad"
        vocal_model_dir = self.config_service.get_data_dir() / "models" / "vocal"
        self.punctuation_model_dir = self.config_service.get_data_dir() / "models" / "punctuation"
        
        # VAD 服务
        self.vad_service: VADService = VADService(vad_model_dir)
        self.vad_loaded: bool = False
        
        # 人声分离服务（用于降噪）
        self.vocal_service: VocalSeparationService = VocalSeparationService(
            vocal_model_dir,
            ffmpeg_service=ffmpeg_service,
            config_service=config_service
        )
        self.vocal_loaded: bool = False
        
        # 语音识别服务（传入 VAD 服务）
        self.speech_service: SpeechRecognitionService = SpeechRecognitionService(
            model_dir,
            ffmpeg_service,
            vad_service=self.vad_service
        )
        # 同步字幕分段设置到服务
        self.speech_service.set_subtitle_settings(
            max_length=self.config_service.get_config_value("subtitle_max_length", 30),
            split_by_punctuation=self.config_service.get_config_value("subtitle_split_by_punctuation", True),
            keep_ending_punctuation=self.config_service.get_config_value("subtitle_keep_ending_punctuation", True)
        )
        self.model_loading: bool = False
        self.model_loaded: bool = False
        self.auto_load_model: bool = self.config_service.get_config_value("whisper_auto_load_model", True)
        
        # 标点恢复设置
        self.punctuation_loaded: bool = False
        self.use_punctuation: bool = self.config_service.get_config_value("whisper_use_punctuation", True)
        
        # VAD 和人声分离设置（默认启用，效果最好）
        self.use_vad: bool = self.config_service.get_config_value("asr_use_vad", True)
        self.use_vocal_separation: bool = self.config_service.get_config_value("asr_use_vocal_separation", True)
        self.current_vocal_model_key: str = self.config_service.get_config_value("asr_vocal_model_key", DEFAULT_VOCAL_MODEL_KEY)
        if self.current_vocal_model_key not in VOCAL_SEPARATION_MODELS:
            self.current_vocal_model_key = DEFAULT_VOCAL_MODEL_KEY
        
        # AI 字幕修复设置（默认不启用，需要配置 API Key）
        self.use_ai_fix: bool = self.config_service.get_config_value("asr_use_ai_fix", False)
        self.ai_fix_api_key: str = self.config_service.get_config_value("asr_ai_fix_api_key", "")
        self.ai_fix_service: AISubtitleFixService = AISubtitleFixService(self.ai_fix_api_key)
        
        # 字幕分段设置
        self.subtitle_max_length: int = self.config_service.get_config_value("subtitle_max_length", 30)
        self.subtitle_split_by_punctuation: bool = self.config_service.get_config_value("subtitle_split_by_punctuation", True)
        self.subtitle_keep_ending_punctuation: bool = self.config_service.get_config_value("subtitle_keep_ending_punctuation", True)
        
        # 当前选择的模型引擎（whisper 或 sensevoice）- 优先使用 SenseVoice
        self.current_engine: str = self.config_service.get_config_value("asr_engine", "sensevoice")
        if self.current_engine not in ["whisper", "sensevoice"]:
            self.current_engine = "sensevoice"
        
        # 当前选择的模型
        if self.current_engine == "whisper":
            saved_model_key = self.config_service.get_config_value(
                "whisper_model_key",
                DEFAULT_WHISPER_MODEL_KEY
            )
            if saved_model_key not in WHISPER_MODELS:
                saved_model_key = DEFAULT_WHISPER_MODEL_KEY
            self.current_model_key: str = saved_model_key
            self.current_model = WHISPER_MODELS[self.current_model_key]
        else:  # sensevoice
            saved_model_key = self.config_service.get_config_value(
                "sensevoice_model_key",
                DEFAULT_SENSEVOICE_MODEL_KEY
            )
            if saved_model_key not in SENSEVOICE_MODELS:
                saved_model_key = DEFAULT_SENSEVOICE_MODEL_KEY
            self.current_model_key: str = saved_model_key
            self.current_model = SENSEVOICE_MODELS[self.current_model_key]
        
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
                self._page,
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
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择音视频:", size=14, weight=ft.FontWeight.W_500),
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
        
        # 模型引擎选择
        self.engine_selector = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="whisper", label="Whisper（多语言）"),
                    ft.Radio(value="sensevoice", label="SenseVoice（中文优化）"),
                ],
                spacing=PADDING_LARGE,
            ),
            value=self.current_engine,
            on_change=self._on_engine_change,
        )
        
        # 模型选择区域（根据引擎动态生成）
        self.model_dropdown = ft.Dropdown(
            options=[],  # 初始为空，由 _update_model_options 填充
            value=self.current_model_key,
            label="选择模型",
            hint_text="选择语音识别模型",
            on_select=self._on_model_change,
            width=690,
            dense=True,
            text_size=13,
        )
        
        # 初始化模型选项
        self._update_model_options()
        
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
        self.download_model_button = ft.Button(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_model,
            visible=False,
        )
        
        self.load_model_button = ft.Button(
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
        
        # === VAD 模型设置 ===
        self.vad_checkbox = ft.Checkbox(
            label="启用 VAD 智能分片",
            value=self.use_vad,
            on_change=self._on_vad_change,
        )
        
        self.vad_status_icon = ft.Icon(
            ft.Icons.CLOUD_DOWNLOAD,
            size=16,
            color=ft.Colors.ORANGE,
        )
        self.vad_status_text = ft.Text(
            "未加载",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.vad_download_btn = ft.TextButton(
            "下载",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_vad,
            visible=False,
        )
        self.vad_load_btn = ft.TextButton(
            "加载",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_vad,
            visible=False,
        )
        
        vad_row = ft.Row(
            controls=[
                self.vad_checkbox,
                self.vad_status_icon,
                self.vad_status_text,
                self.vad_download_btn,
                self.vad_load_btn,
            ],
            spacing=PADDING_SMALL,
        )
        
        vad_hint = ft.Text(
            "在静音处智能分片，避免在说话中间切断（仅 Whisper 长音频需要）",
            size=10,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # === 人声分离模型设置 ===
        self.vocal_checkbox = ft.Checkbox(
            label="启用人声分离（降噪）",
            value=self.use_vocal_separation,
            on_change=self._on_vocal_change,
        )
        
        # 人声分离模型选择
        vocal_model_options = []
        for model_key, model_info in VOCAL_SEPARATION_MODELS.items():
            prefix = "[伴奏]" if model_info.invert_output else "[人声]"
            option_text = f"{prefix} {model_info.display_name}"
            vocal_model_options.append(
                ft.dropdown.Option(key=model_key, text=option_text)
            )
        
        self.vocal_model_dropdown = ft.Dropdown(
            options=vocal_model_options,
            value=self.current_vocal_model_key,
            label="降噪模型",
            hint_text="选择人声分离模型",
            on_select=self._on_vocal_model_change,
            width=380,
            dense=True,
            text_size=12,
            disabled=not self.use_vocal_separation,
        )
        
        self.vocal_status_icon = ft.Icon(
            ft.Icons.CLOUD_DOWNLOAD,
            size=16,
            color=ft.Colors.ORANGE,
        )
        self.vocal_status_text = ft.Text(
            "未加载",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.vocal_download_btn = ft.TextButton(
            "下载",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_vocal,
            visible=False,
        )
        self.vocal_load_btn = ft.TextButton(
            "加载",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_vocal,
            visible=False,
        )
        
        vocal_status_row = ft.Row(
            controls=[
                self.vocal_status_icon,
                self.vocal_status_text,
                self.vocal_download_btn,
                self.vocal_load_btn,
            ],
            spacing=PADDING_SMALL,
        )
        
        vocal_hint = ft.Text(
            "对嘈杂音频进行人声分离，去除背景音乐和噪音（处理时间会增加）",
            size=10,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 预处理设置区域
        preprocess_hint = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TIPS_AND_UPDATES, size=14, color=ft.Colors.PRIMARY),
                    ft.Text(
                        "推荐：同时启用 VAD 和人声分离可获得最佳识别效果",
                        size=11,
                        color=ft.Colors.PRIMARY,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(bottom=4),
        )
        
        # === AI 字幕修复设置 ===
        self.ai_fix_checkbox = ft.Checkbox(
            label="启用 AI 修复字幕",
            value=self.use_ai_fix,
            on_change=self._on_ai_fix_change,
        )
        
        self.ai_fix_api_key_field = ft.TextField(
            label="心流 API Key",
            value=self.ai_fix_api_key,
            password=True,
            can_reveal_password=True,
            hint_text="请输入心流开放平台 API Key",
            on_change=self._on_ai_fix_api_key_change,
            width=350,
            dense=True,
            text_size=12,
            disabled=not self.use_ai_fix,
        )
        
        ai_fix_link = ft.TextButton(
            "前往心流开放平台注册",
            icon=ft.Icons.OPEN_IN_NEW,
            url="https://platform.iflow.cn/",
            tooltip="免费注册，获取 API Key",
        )
        
        ai_fix_hint = ft.Text(
            "使用 AI 修复识别结果中的错词、同音字等问题（需注册心流开放平台，免费使用）",
            size=10,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        ai_fix_section = ft.Column(
            controls=[
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                self.ai_fix_checkbox,
                self.ai_fix_api_key_field,
                ai_fix_link,
                ai_fix_hint,
            ],
            spacing=4,
        )
        
        # === 标点恢复设置 ===
        self.punctuation_checkbox = ft.Checkbox(
            label="启用标点恢复",
            value=self.use_punctuation,
            on_change=self._on_punctuation_change,
        )
        
        self.punctuation_status_icon = ft.Icon(
            ft.Icons.CLOUD_DOWNLOAD,
            size=16,
            color=ft.Colors.ORANGE,
        )
        self.punctuation_status_text = ft.Text(
            "未加载",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.punctuation_download_btn = ft.TextButton(
            "下载",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_punctuation,
            visible=False,
        )
        self.punctuation_load_btn = ft.TextButton(
            "加载",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_punctuation,
            visible=False,
        )
        
        punctuation_status_row = ft.Row(
            controls=[
                self.punctuation_checkbox,
                self.punctuation_status_icon,
                self.punctuation_status_text,
                self.punctuation_download_btn,
                self.punctuation_load_btn,
            ],
            spacing=PADDING_SMALL,
        )
        
        punctuation_hint = ft.Text(
            "使用 AI 模型优化或添加标点符号，提升识别结果的可读性",
            size=10,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        preprocess_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预处理设置", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                    preprocess_hint,
                    vad_row,
                    vad_hint,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    self.vocal_checkbox,
                    self.vocal_model_dropdown,
                    vocal_status_row,
                    vocal_hint,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    punctuation_status_row,
                    punctuation_hint,
                    ai_fix_section,
                ],
                spacing=4,
            ),
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        # 初始化 VAD 和人声分离状态
        self._init_vad_status()
        self._init_vocal_status()
        self._init_punctuation_status()
        
        model_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("识别引擎", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                self.engine_selector,
                            ],
                            spacing=4,
                        ),
                        margin=ft.margin.only(bottom=PADDING_SMALL),
                    ),
                    self.model_dropdown,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                    self.auto_load_checkbox,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                    preprocess_section,
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
                ft.dropdown.Option(key="lrc", text="LRC 歌词文件"),
            ],
            width=180,
            dense=True,
        )
        
        # 语言选择
        saved_language = self.config_service.get_config_value("whisper_language", "auto")
        self.language_dropdown = ft.Dropdown(
            label="音频语言",
            hint_text="选择音频语言",
            value=saved_language,
            options=[
                ft.dropdown.Option(key="auto", text="自动检测 (Auto Detect)"),
                ft.dropdown.Option(key="zh", text="中文-普通话 (Mandarin)"),
                ft.dropdown.Option(key="yue", text="中文-粤语 (Cantonese)"),
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
            width=260,
            dense=True,
            on_select=self._on_language_change,
        )
        
        # 任务类型选择（Whisper 专用）
        saved_task = self.config_service.get_config_value("whisper_task", "transcribe")
        self.task_dropdown = ft.Dropdown(
            label="任务类型",
            hint_text="选择识别任务",
            value=saved_task,
            options=[
                ft.dropdown.Option(key="transcribe", text="转录（保持原语言）"),
                ft.dropdown.Option(key="translate", text="翻译（翻译为英文）"),
            ],
            width=230,
            dense=True,
            on_select=self._on_task_change,
            visible=(self.current_engine == "whisper"),  # 根据当前引擎决定是否可见
        )
        
        # 引擎特性提示
        self.engine_hint = ft.Container(
            content=ft.Column(
                controls=[
                    # Whisper 提示
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.BLUE),
                                ft.Text(
                                    "Whisper: 支持自动检测或指定语言。转录模式保持原语言，翻译模式统一翻译为英文",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=6,
                        ),
                        visible=(self.current_engine == "whisper"),  # 根据当前引擎决定是否显示
                    ),
                    # SenseVoice 提示
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.BLUE),
                                ft.Text(
                                    "SenseVoice: 支持自动语言检测（中英日韩粤等），也可指定语言提高准确度",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=6,
                        ),
                        visible=(self.current_engine == "sensevoice"),  # 根据当前引擎决定是否显示
                    ),
                ],
                spacing=4,
            ),
            margin=ft.margin.only(top=4, left=4),
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
            hint_text = "sherpa要求使用CUDA，未检测到 CUDA 支持。请下载 CUDA 或 CUDA_FULL 版本"
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
        
        # 输出设置 - 横向布局
        settings_row = ft.Row(
            controls=[
                self.output_format_dropdown,
                self.language_dropdown,
                self.task_dropdown,
                ft.Column(
                    controls=[
                        self.gpu_checkbox,
                        gpu_hint_text,
                    ],
                    spacing=4,
                ),
            ],
            spacing=PADDING_LARGE,
            wrap=True,
        )
        
        # 引擎特性提示行
        engine_hint_row = ft.Row(
            controls=[
                self.engine_hint,
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 格式说明
        format_hint = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.BLUE),
                    ft.Text(
                        "提示：SRT/VTT 格式会自动添加时间戳，适合制作视频字幕",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=6,
            ),
            margin=ft.margin.only(top=PADDING_SMALL),
        )
        
        # === 字幕分段设置 ===
        self.subtitle_split_checkbox = ft.Checkbox(
            label="在标点处自动分段",
            value=self.subtitle_split_by_punctuation,
            on_change=self._on_subtitle_split_change,
        )
        
        self.subtitle_keep_punct_checkbox = ft.Checkbox(
            label="保留结尾标点",
            value=self.subtitle_keep_ending_punctuation,
            on_change=self._on_subtitle_keep_punct_change,
        )
        
        self.subtitle_length_slider = ft.Slider(
            min=15,
            max=60,
            divisions=9,
            value=self.subtitle_max_length,
            label="{value} 字/段",
            on_change=self._on_subtitle_length_change,
            expand=True,
        )
        
        self.subtitle_length_text = ft.Text(
            f"每段最大 {self.subtitle_max_length} 字",
            size=12,
        )
        
        subtitle_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("字幕分段设置（SRT/VTT/LRC）", size=13, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=[
                            self.subtitle_split_checkbox,
                            self.subtitle_keep_punct_checkbox,
                        ],
                        spacing=PADDING_LARGE,
                    ),
                    ft.Row(
                        controls=[
                            self.subtitle_length_text,
                            self.subtitle_length_slider,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Text(
                        "较短的分段更易阅读，建议 25-35 字/段",
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        # 输出路径选项
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="same", label="保存到原文件目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="same",
            on_change=self._on_output_mode_change,
        )
        
        default_output = self.config_service.get_output_dir() / "audio_to_text"
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
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    settings_row,
                    engine_hint_row,
                    format_hint,
                    subtitle_settings,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
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
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 处理按钮区域 - 优化为大按钮样式
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PLAY_ARROW, size=24),
                        ft.Text("开始识别", size=18, weight=ft.FontWeight.W_600),
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
            alignment=ft.Alignment.CENTER,
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
                alignment=ft.Alignment.CENTER,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    def _check_all_model_files_exist(self) -> bool:
        """检查当前模型的所有必需文件是否存在。"""
        model_dir = self.speech_service.get_model_dir(self.current_model_key)
        
        # 根据模型类型检查文件
        if isinstance(self.current_model, SenseVoiceModelInfo):
            # SenseVoice/Paraformer 单文件结构: model.onnx 和 tokens.txt
            model_path = model_dir / self.current_model.model_filename
            tokens_path = model_dir / self.current_model.tokens_filename
            return model_path.exists() and tokens_path.exists()
        
        elif isinstance(self.current_model, WhisperModelInfo):
            # Whisper/Paraformer encoder-decoder 结构: encoder + decoder + tokens
            encoder_path = model_dir / self.current_model.encoder_filename
            decoder_path = model_dir / self.current_model.decoder_filename
            config_path = model_dir / self.current_model.config_filename
            
            all_exist = encoder_path.exists() and decoder_path.exists() and config_path.exists()
            
            # 检查外部权重文件（如果需要）
            if hasattr(self.current_model, 'encoder_weights_filename') and self.current_model.encoder_weights_filename:
                weights_path = model_dir / self.current_model.encoder_weights_filename
                all_exist = all_exist and weights_path.exists()
            if hasattr(self.current_model, 'decoder_weights_filename') and self.current_model.decoder_weights_filename:
                weights_path = model_dir / self.current_model.decoder_weights_filename
                all_exist = all_exist and weights_path.exists()
            
            return all_exist
        
        return False
    
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
            self._page.update()
        except:
            pass
    
    def _try_auto_load_model(self) -> None:
        """尝试自动加载模型。"""
        if self._check_all_model_files_exist() and not self.model_loaded:
            threading.Thread(target=self._load_model_thread, daemon=True).start()
    
    def _update_model_options(self) -> None:
        """根据当前引擎更新模型选项列表。"""
        model_options = []
        
        if self.current_engine == "whisper":
            for model_key, model_info in WHISPER_MODELS.items():
                option_text = f"{model_info.display_name}  |  {model_info.size_mb}MB  |  {model_info.language_support}"
                model_options.append(
                    ft.dropdown.Option(key=model_key, text=option_text)
                )
        else:  # sensevoice
            for model_key, model_info in SENSEVOICE_MODELS.items():
                option_text = f"{model_info.display_name}  |  {model_info.size_mb}MB  |  {model_info.language_support}"
                model_options.append(
                    ft.dropdown.Option(key=model_key, text=option_text)
                )
        
        self.model_dropdown.options = model_options
        
        # 更新模型信息显示
        if hasattr(self, 'model_info_text') and self.current_model:
            if self.current_engine == "whisper":
                self.model_info_text.value = f"{self.current_model.quality} | {self.current_model.performance}"
            else:
                self.model_info_text.value = f"{self.current_model.quality} | {self.current_model.performance}"
    
    def _on_engine_change(self, e: ft.ControlEvent) -> None:
        """模型引擎切换事件。"""
        new_engine = e.control.value
        if new_engine == self.current_engine:
            return
        
        # 如果有模型已加载，先卸载
        if self.model_loaded:
            self.speech_service.unload_model()
            self.model_loaded = False
        
        # 切换引擎
        self.current_engine = new_engine
        self.config_service.set_config_value("asr_engine", new_engine)
        
        # 加载对应引擎的默认模型
        if new_engine == "whisper":
            self.current_model_key = self.config_service.get_config_value(
                "whisper_model_key",
                DEFAULT_WHISPER_MODEL_KEY
            )
            self.current_model = WHISPER_MODELS.get(self.current_model_key, WHISPER_MODELS[DEFAULT_WHISPER_MODEL_KEY])
        else:  # sensevoice
            self.current_model_key = self.config_service.get_config_value(
                "sensevoice_model_key",
                DEFAULT_SENSEVOICE_MODEL_KEY
            )
            self.current_model = SENSEVOICE_MODELS.get(self.current_model_key, SENSEVOICE_MODELS[DEFAULT_SENSEVOICE_MODEL_KEY])
        
        # 更新界面
        self._update_model_options()
        self.model_dropdown.value = self.current_model_key
        self._init_model_status()
        
        # 更新控件可见性
        is_whisper = (new_engine == "whisper")
        self.task_dropdown.visible = is_whisper  # 任务类型只对 Whisper 可见
        
        # 更新提示文本可见性
        if hasattr(self.engine_hint.content, 'controls'):
            self.engine_hint.content.controls[0].visible = is_whisper  # Whisper 提示
            self.engine_hint.content.controls[1].visible = not is_whisper  # SenseVoice 提示
        
        try:
            self._page.update()
        except:
            pass
    
    def _on_model_change(self, e: ft.ControlEvent) -> None:
        """模型选择变更事件。"""
        new_key = e.control.value
        if new_key == self.current_model_key:
            return
        
        # 如果当前有模型加载，先卸载
        if self.model_loaded:
            self._unload_model()
        
        # 更新当前模型（根据引擎类型）
        self.current_model_key = new_key
        
        if self.current_engine == "whisper":
            self.current_model = WHISPER_MODELS[new_key]
            self.config_service.set_config_value("whisper_model_key", new_key)
        else:  # sensevoice
            self.current_model = SENSEVOICE_MODELS[new_key]
            self.config_service.set_config_value("sensevoice_model_key", new_key)
        
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
                self._page.update()
            except:
                pass
            
            # 下载进度回调
            def progress_callback(progress: float, message: str):
                self.model_status_text.value = message
                try:
                    self._page.update()
                except:
                    pass
            
            # 根据模型类型下载
            if isinstance(self.current_model, SenseVoiceModelInfo):
                # 下载 SenseVoice/Paraformer 单文件模型（model.onnx + tokens.txt）
                model_path, tokens_path = self.speech_service.download_sensevoice_model(
                    self.current_model_key,
                    self.current_model,
                    progress_callback
                )
                
                logger.info(f"模型下载完成: {model_path.name}, {tokens_path.name}")
            elif isinstance(self.current_model, WhisperModelInfo):
                # 下载 Whisper/Paraformer encoder-decoder 模型（encoder + decoder + tokens）
                encoder_path, decoder_path, config_path = self.speech_service.download_model(
                    self.current_model_key,
                    self.current_model,
                    progress_callback
                )
                
                logger.info(f"模型下载完成: {encoder_path.name}, {decoder_path.name}, {config_path.name}")
            
            # 更新状态
            engine_name = "SenseVoice" if self.current_engine == "sensevoice" else "Whisper"
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
                self._page.update()
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
                self._page.update()
            except:
                pass
            
            # GPU设置
            gpu_enabled = self.config_service.get_config_value("gpu_acceleration", True)
            gpu_device_id = self.config_service.get_config_value("gpu_device_id", 0)
            gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 8192)
            enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", False)
            
            # 获取选择的语言和任务类型
            language = self.config_service.get_config_value("whisper_language", "auto")
            # sherpa-onnx 使用空字符串表示自动检测
            sherpa_language = "" if language == "auto" else language
            task = self.config_service.get_config_value("whisper_task", "transcribe")
            
            # 根据模型类型加载模型
            model_dir = self.speech_service.get_model_dir(self.current_model_key)
            
            if isinstance(self.current_model, SenseVoiceModelInfo):
                # 加载 SenseVoice/Paraformer 单文件模型
                model_path = model_dir / self.current_model.model_filename
                tokens_path = model_dir / self.current_model.tokens_filename
                
                self.speech_service.load_sensevoice_model(
                    model_path=model_path,
                    tokens_path=tokens_path,
                    use_gpu=gpu_enabled,
                    gpu_device_id=gpu_device_id,
                    language=sherpa_language,
                    model_type=self.current_model.model_type,  # 传递模型类型
                )
            elif isinstance(self.current_model, WhisperModelInfo):
                # 加载 Whisper/Paraformer encoder-decoder 模型
                encoder_path = model_dir / self.current_model.encoder_filename
                decoder_path = model_dir / self.current_model.decoder_filename
                config_path = model_dir / self.current_model.config_filename
                
                # 注意：Paraformer encoder-decoder 模型暂时使用 Whisper 加载方式
                self.speech_service.load_model(
                    encoder_path,
                    decoder_path,
                    config_path,
                    use_gpu=gpu_enabled,
                    gpu_device_id=gpu_device_id,
                    gpu_memory_limit=gpu_memory_limit,
                    enable_memory_arena=enable_memory_arena,
                    language=sherpa_language,
                    task=task,  # 传递任务类型
                )
            
            self.model_loaded = True
            
            # 获取设备信息
            device_info = self.speech_service.get_device_info()
            engine_name = "SenseVoice" if self.current_engine == "sensevoice" else "Whisper"
            
            # 更新状态
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已加载 ({device_info})"
            self.load_model_button.visible = False
            self.unload_model_button.visible = True
            self.reload_model_button.visible = True
            
            logger.info(f"{engine_name}模型加载完成, 设备: {device_info}")
            
            # 如果使用了 CUDA，显示警告提示
            if "CUDA" in device_info.upper() or self.speech_service.current_provider == "cuda":
                self._show_cuda_warning()
            
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
                self._page.update()
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
                self._page.update()
            except:
                pass
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        def confirm_delete(e):
            dialog.open = False
            self._page.update()
            self._do_delete_model()
        
        def cancel_delete(e):
            dialog.open = False
            self._page.update()
        
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
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    def _do_delete_model(self) -> None:
        """执行删除模型操作。"""
        # 先卸载模型
        if self.model_loaded:
            self._unload_model()
        
        # 获取模型目录
        model_dir = self.speech_service.get_model_dir(self.current_model_key)
        
        # 根据模型类型删除对应的文件
        if isinstance(self.current_model, SenseVoiceModelInfo):
            # SenseVoice/Paraformer 单文件结构
            files_to_delete = [
                model_dir / self.current_model.model_filename,
                model_dir / self.current_model.tokens_filename,
            ]
        elif isinstance(self.current_model, WhisperModelInfo):
            # Whisper encoder-decoder 结构
            files_to_delete = [
                model_dir / self.current_model.encoder_filename,
                model_dir / self.current_model.decoder_filename,
                model_dir / self.current_model.config_filename,
            ]
            # 添加外部权重文件（如果有）
            if hasattr(self.current_model, 'encoder_weights_filename') and self.current_model.encoder_weights_filename:
                files_to_delete.append(model_dir / self.current_model.encoder_weights_filename)
            if hasattr(self.current_model, 'decoder_weights_filename') and self.current_model.decoder_weights_filename:
                files_to_delete.append(model_dir / self.current_model.decoder_weights_filename)
        else:
            files_to_delete = []
        
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
            self._page.update()
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
    
    def _on_vad_change(self, e: ft.ControlEvent) -> None:
        """VAD 选项变更事件。"""
        self.use_vad = e.control.value
        self.config_service.set_config_value("asr_use_vad", self.use_vad)
        self.speech_service.set_use_vad(self.use_vad)
    
    def _on_vocal_change(self, e: ft.ControlEvent) -> None:
        """人声分离选项变更事件。"""
        self.use_vocal_separation = e.control.value
        self.config_service.set_config_value("asr_use_vocal_separation", self.use_vocal_separation)
        
        # 更新模型下拉框的启用状态
        self.vocal_model_dropdown.disabled = not self.use_vocal_separation
        self._page.update()
    
    def _on_vocal_model_change(self, e: ft.ControlEvent) -> None:
        """人声分离模型选择变更事件。"""
        self.current_vocal_model_key = e.control.value
        self.config_service.set_config_value("asr_vocal_model_key", self.current_vocal_model_key)
        
        # 更新模型状态
        self._init_vocal_status()
    
    def _on_ai_fix_change(self, e: ft.ControlEvent) -> None:
        """AI 修复选项变更事件。"""
        self.use_ai_fix = e.control.value
        self.config_service.set_config_value("asr_use_ai_fix", self.use_ai_fix)
        self.ai_fix_api_key_field.disabled = not self.use_ai_fix
        self._page.update()
    
    def _on_ai_fix_api_key_change(self, e: ft.ControlEvent) -> None:
        """AI 修复 API Key 变更事件。"""
        self.ai_fix_api_key = e.control.value
        self.config_service.set_config_value("asr_ai_fix_api_key", self.ai_fix_api_key)
        self.ai_fix_service.set_api_key(self.ai_fix_api_key)
    
    def _init_vad_status(self) -> None:
        """初始化 VAD 模型状态。"""
        vad_model_info = VAD_MODELS[DEFAULT_VAD_MODEL_KEY]
        model_dir = self.vad_service.get_model_dir(DEFAULT_VAD_MODEL_KEY)
        model_path = model_dir / vad_model_info.filename
        
        if model_path.exists():
            self.vad_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.vad_status_icon.color = ft.Colors.GREEN
            self.vad_status_text.value = "已下载"
            self.vad_download_btn.visible = False
            self.vad_load_btn.visible = True
            
            # 自动加载 VAD 模型
            if self.use_vad and not self.vad_loaded:
                self._load_vad_model()
        else:
            self.vad_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.vad_status_icon.color = ft.Colors.ORANGE
            self.vad_status_text.value = f"未下载 ({vad_model_info.size_mb}MB)"
            self.vad_download_btn.visible = True
            self.vad_load_btn.visible = False
    
    def _init_vocal_status(self) -> None:
        """初始化人声分离模型状态。"""
        vocal_model_info = VOCAL_SEPARATION_MODELS[self.current_vocal_model_key]
        model_path = self.vocal_service.model_dir / vocal_model_info.filename
        
        if model_path.exists():
            self.vocal_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.vocal_status_icon.color = ft.Colors.GREEN
            self.vocal_status_text.value = "已下载"
            self.vocal_download_btn.visible = False
            self.vocal_load_btn.visible = True
            
            # 自动加载人声分离模型
            if self.use_vocal_separation and not self.vocal_loaded:
                self._load_vocal_model()
        else:
            self.vocal_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.vocal_status_icon.color = ft.Colors.ORANGE
            self.vocal_status_text.value = f"未下载 ({vocal_model_info.size_mb}MB)"
            self.vocal_download_btn.visible = True
            self.vocal_load_btn.visible = False
    
    def _on_download_vad(self, e: ft.ControlEvent) -> None:
        """下载 VAD 模型。"""
        self.vad_download_btn.visible = False
        self.vad_status_text.value = "下载中..."
        self._page.update()
        
        def download_task():
            try:
                vad_model_info = VAD_MODELS[DEFAULT_VAD_MODEL_KEY]
                
                def progress_callback(progress: float, message: str):
                    self.vad_status_text.value = message
                    try:
                        self._page.update()
                    except:
                        pass
                
                self.vad_service.download_model(
                    DEFAULT_VAD_MODEL_KEY,
                    vad_model_info,
                    progress_callback
                )
                
                self.vad_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.vad_status_icon.color = ft.Colors.GREEN
                self.vad_status_text.value = "已下载"
                self.vad_load_btn.visible = True
                self._page.update()
                
                # 自动加载
                self._load_vad_model()
                
            except Exception as ex:
                self.vad_status_icon.name = ft.Icons.ERROR
                self.vad_status_icon.color = ft.Colors.ERROR
                self.vad_status_text.value = f"下载失败: {ex}"
                self.vad_download_btn.visible = True
                self._page.update()
        
        self._page.run_thread(download_task)
    
    def _on_load_vad(self, e: ft.ControlEvent) -> None:
        """加载 VAD 模型。"""
        self._load_vad_model()
    
    def _load_vad_model(self) -> None:
        """加载 VAD 模型。"""
        try:
            vad_model_info = VAD_MODELS[DEFAULT_VAD_MODEL_KEY]
            model_dir = self.vad_service.get_model_dir(DEFAULT_VAD_MODEL_KEY)
            model_path = model_dir / vad_model_info.filename
            
            self.vad_service.load_model(
                model_path,
                threshold=vad_model_info.threshold,
                min_silence_duration=vad_model_info.min_silence_duration,
                min_speech_duration=vad_model_info.min_speech_duration,
                window_size=vad_model_info.window_size
            )
            
            self.vad_loaded = True
            self.vad_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.vad_status_icon.color = ft.Colors.GREEN
            self.vad_status_text.value = "已加载"
            self.vad_load_btn.visible = False
            self._page.update()
            
        except Exception as ex:
            self.vad_status_text.value = f"加载失败: {ex}"
            self.vad_status_icon.color = ft.Colors.ERROR
            self._page.update()
    
    def _on_download_vocal(self, e: ft.ControlEvent) -> None:
        """下载人声分离模型。"""
        self.vocal_download_btn.visible = False
        self.vocal_status_text.value = "下载中..."
        self._page.update()
        
        def download_task():
            try:
                vocal_model_info = VOCAL_SEPARATION_MODELS[self.current_vocal_model_key]
                
                def progress_callback(progress: float, message: str):
                    self.vocal_status_text.value = message
                    try:
                        self._page.update()
                    except:
                        pass
                
                self.vocal_service.download_model(
                    self.current_vocal_model_key,
                    vocal_model_info,
                    progress_callback
                )
                
                self.vocal_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.vocal_status_icon.color = ft.Colors.GREEN
                self.vocal_status_text.value = "已下载"
                self.vocal_load_btn.visible = True
                self._page.update()
                
                # 自动加载
                self._load_vocal_model()
                
            except Exception as ex:
                self.vocal_status_icon.name = ft.Icons.ERROR
                self.vocal_status_icon.color = ft.Colors.ERROR
                self.vocal_status_text.value = f"下载失败: {ex}"
                self.vocal_download_btn.visible = True
                self._page.update()
        
        self._page.run_thread(download_task)
    
    def _on_load_vocal(self, e: ft.ControlEvent) -> None:
        """加载人声分离模型。"""
        self._load_vocal_model()
    
    def _load_vocal_model(self) -> None:
        """加载人声分离模型。"""
        try:
            vocal_model_info = VOCAL_SEPARATION_MODELS[self.current_vocal_model_key]
            model_path = self.vocal_service.model_dir / vocal_model_info.filename
            
            self.vocal_service.load_model(
                model_path,
                invert_output=vocal_model_info.invert_output
            )
            
            self.vocal_loaded = True
            self.vocal_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.vocal_status_icon.color = ft.Colors.GREEN
            self.vocal_status_text.value = "已加载"
            self.vocal_load_btn.visible = False
            self._page.update()
            
        except Exception as ex:
            self.vocal_status_text.value = f"加载失败: {ex}"
            self.vocal_status_icon.color = ft.Colors.ERROR
            self._page.update()
    
    def _on_punctuation_change(self, e: ft.ControlEvent) -> None:
        """标点恢复开关变更事件。"""
        self.use_punctuation = e.control.value
        self.config_service.set_config_value("whisper_use_punctuation", self.use_punctuation)
        self.speech_service.use_punctuation = self.use_punctuation
        self._page.update()
    
    def _init_punctuation_status(self) -> None:
        """初始化标点恢复模型状态。"""
        punctuation_model_info = PUNCTUATION_MODELS[DEFAULT_PUNCTUATION_MODEL_KEY]
        model_dir = self.punctuation_model_dir / punctuation_model_info.name
        model_file = model_dir / punctuation_model_info.model_filename
        
        if model_file.exists():
            self.punctuation_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.punctuation_status_icon.color = ft.Colors.GREEN
            self.punctuation_status_text.value = "已下载"
            self.punctuation_download_btn.visible = False
            self.punctuation_load_btn.visible = True
            
            # 自动加载标点恢复模型
            if self.use_punctuation and not self.punctuation_loaded:
                self._load_punctuation_model()
        else:
            self.punctuation_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.punctuation_status_icon.color = ft.Colors.ORANGE
            self.punctuation_status_text.value = f"未下载 ({punctuation_model_info.size_mb}MB)"
            self.punctuation_download_btn.visible = True
            self.punctuation_load_btn.visible = False
    
    def _on_download_punctuation(self, e: ft.ControlEvent) -> None:
        """下载标点恢复模型。"""
        self.punctuation_download_btn.visible = False
        self.punctuation_status_text.value = "下载中..."
        self._page.update()
        
        def download_task():
            try:
                import requests
                
                punctuation_model_info = PUNCTUATION_MODELS[DEFAULT_PUNCTUATION_MODEL_KEY]
                
                # 确保模型目录存在
                model_dir = self.punctuation_model_dir / punctuation_model_info.name
                model_dir.mkdir(parents=True, exist_ok=True)
                
                model_path = model_dir / punctuation_model_info.model_filename
                tokens_path = model_dir / punctuation_model_info.tokens_filename
                
                # 下载模型文件
                self.punctuation_status_text.value = "下载模型文件..."
                try:
                    self._page.update()
                except:
                    pass
                
                response = requests.get(punctuation_model_info.model_url, stream=True, timeout=120)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(model_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = downloaded / total_size * 100
                                self.punctuation_status_text.value = f"下载模型... {progress:.0f}%"
                                try:
                                    self._page.update()
                                except:
                                    pass
                
                # 下载 tokens 文件
                self.punctuation_status_text.value = "下载 tokens 文件..."
                try:
                    self._page.update()
                except:
                    pass
                
                response = requests.get(punctuation_model_info.tokens_url, timeout=60)
                response.raise_for_status()
                
                with open(tokens_path, 'wb') as f:
                    f.write(response.content)
                
                self.punctuation_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.punctuation_status_icon.color = ft.Colors.GREEN
                self.punctuation_status_text.value = "已下载"
                self.punctuation_load_btn.visible = True
                self._page.update()
                
                # 自动加载
                self._load_punctuation_model()
                
            except Exception as ex:
                logger.error(f"下载标点恢复模型失败: {ex}")
                self.punctuation_status_icon.name = ft.Icons.ERROR
                self.punctuation_status_icon.color = ft.Colors.ERROR
                self.punctuation_status_text.value = f"下载失败: {ex}"
                self.punctuation_download_btn.visible = True
                self._page.update()
        
        self._page.run_thread(download_task)
    
    def _on_load_punctuation(self, e: ft.ControlEvent) -> None:
        """加载标点恢复模型。"""
        self._load_punctuation_model()
    
    def _load_punctuation_model(self) -> None:
        """加载标点恢复模型。"""
        try:
            punctuation_model_info = PUNCTUATION_MODELS[DEFAULT_PUNCTUATION_MODEL_KEY]
            model_dir = self.punctuation_model_dir / punctuation_model_info.name
            
            self.speech_service.load_punctuation_model(
                model_path=model_dir,
                use_gpu=self.config_service.get_config_value("whisper_use_gpu", True),
                num_threads=4
            )
            
            self.punctuation_loaded = True
            self.punctuation_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.punctuation_status_icon.color = ft.Colors.GREEN
            self.punctuation_status_text.value = "已加载"
            self.punctuation_load_btn.visible = False
            self._page.update()
            
        except Exception as ex:
            logger.error(f"加载标点恢复模型失败: {ex}")
            self.punctuation_status_text.value = f"加载失败: {ex}"
            self.punctuation_status_icon.color = ft.Colors.ERROR
            self._page.update()
    
    def _on_language_change(self, e: ft.ControlEvent) -> None:
        """语言选择变更事件。"""
        language = e.control.value
        self.config_service.set_config_value("whisper_language", language)
        
        # 如果当前有模型加载，提示需要重新加载
        if self.model_loaded:
            self._show_info("提示", "音频语言已更改，需要重新加载模型才能生效。")
    
    def _on_task_change(self, e: ft.ControlEvent) -> None:
        """任务类型变更事件。"""
        task = e.control.value
        self.config_service.set_config_value("whisper_task", task)
        
        # 如果当前有模型加载，提示需要重新加载
        if self.model_loaded:
            self._show_info("提示", "任务类型已更改，需要重新加载模型才能生效。")
    
    def _on_subtitle_split_change(self, e: ft.ControlEvent) -> None:
        """字幕标点分段选项变更事件。"""
        self.subtitle_split_by_punctuation = e.control.value
        self.config_service.set_config_value("subtitle_split_by_punctuation", self.subtitle_split_by_punctuation)
        self.speech_service.set_subtitle_settings(split_by_punctuation=self.subtitle_split_by_punctuation)
    
    def _on_subtitle_length_change(self, e: ft.ControlEvent) -> None:
        """字幕最大长度变更事件。"""
        self.subtitle_max_length = int(e.control.value)
        self.config_service.set_config_value("subtitle_max_length", self.subtitle_max_length)
        self.speech_service.set_subtitle_settings(max_length=self.subtitle_max_length)
        self.subtitle_length_text.value = f"每段最大 {self.subtitle_max_length} 字"
        try:
            self._page.update()
        except:
            pass
    
    def _on_subtitle_keep_punct_change(self, e: ft.ControlEvent) -> None:
        """保留结尾标点选项变更事件。"""
        self.subtitle_keep_ending_punctuation = e.control.value
        self.config_service.set_config_value("subtitle_keep_ending_punctuation", self.subtitle_keep_ending_punctuation)
        self.speech_service.set_subtitle_settings(keep_ending_punctuation=self.subtitle_keep_ending_punctuation)
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        is_custom = e.control.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        try:
            self._page.update()
        except:
            pass
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if result:
            self.custom_output_dir.value = result
            try:
                self._page.update()
            except:
                pass
    
    async def _on_select_files(self, e: ft.ControlEvent = None) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            allow_multiple=True,
            allowed_extensions=["mp3", "wav", "flac", "m4a", "aac", "ogg", "wma", "mp4", "mkv", "avi", "mov", "flv", "wmv"],
            dialog_title="选择音视频文件",
        )
        if result and result.files:
            for file in result.files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
            self._update_process_button()
    
    async def _on_select_folder(self, e: ft.ControlEvent = None) -> None:
        """选择文件夹按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择包含音视频文件的文件夹")
        if result:
            folder_path = Path(result)
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
            self._page.update()
        except:
            pass
    
    def _check_has_audio_stream(self, file_path: Path) -> bool:
        """检测文件是否包含音频流。"""
        # 音频文件默认有音频
        audio_exts = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.opus'}
        if file_path.suffix.lower() in audio_exts:
            return True
        
        cache_key = str(file_path)
        if cache_key in self._audio_stream_cache:
            return self._audio_stream_cache[cache_key]
        
        has_audio = True
        try:
            import ffmpeg
            ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
            if ffprobe_path:
                probe = ffmpeg.probe(str(file_path), cmd=ffprobe_path)
                has_audio = any(s.get('codec_type') == 'audio' for s in probe.get('streams', []))
        except Exception:
            has_audio = True
        
        self._audio_stream_cache[cache_key] = has_audio
        return has_audio
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if not self.selected_files:
            self._init_empty_state()
            return
        
        file_items = []
        no_audio_count = 0
        audio_exts = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.opus'}
        
        for file_path in self.selected_files:
            file_size = format_file_size(file_path.stat().st_size)
            is_audio_file = file_path.suffix.lower() in audio_exts
            has_audio = self._check_has_audio_stream(file_path)
            
            if not has_audio:
                no_audio_count += 1
            
            # 根据是否有音频流显示不同样式
            if has_audio:
                icon = ft.Icon(ft.Icons.AUDIOTRACK if is_audio_file else ft.Icons.VIDEO_FILE, size=20)
                subtitle = file_size
                subtitle_color = ft.Colors.ON_SURFACE_VARIANT
                border_color = ft.Colors.OUTLINE
            else:
                icon = ft.Icon(ft.Icons.VOLUME_OFF, size=20, color=ft.Colors.ORANGE)
                subtitle = f"⚠️ 无音频流 • {file_size}"
                subtitle_color = ft.Colors.ORANGE
                border_color = ft.Colors.ORANGE
            
            file_item = ft.Container(
                content=ft.Row(
                    controls=[
                        icon,
                        ft.Column(
                            controls=[
                                ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                ft.Text(subtitle, size=11, color=subtitle_color),
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
                border=ft.border.all(1, border_color),
                border_radius=BORDER_RADIUS_MEDIUM,
            )
            file_items.append(file_item)
        
        # 显示警告
        if no_audio_count > 0:
            warning = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=ft.Colors.ORANGE),
                    ft.Text(f"{no_audio_count} 个文件不包含音频流，将被跳过", size=12, color=ft.Colors.ORANGE),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
            )
            file_items.insert(0, warning)
        
        self.file_list_view.controls = file_items
        try:
            self._page.update()
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
            self._page.update()
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
                self._page.update()
            except:
                pass
            
            total_files = len(self.selected_files)
            
            for i, file_path in enumerate(self.selected_files):
                try:
                    # 更新进度
                    self.progress_text.value = f"正在处理: {file_path.name} ({i+1}/{total_files})"
                    self.progress_bar.value = i / total_files
                    try:
                        self._page.update()
                    except:
                        pass
                    
                    # 进度回调
                    def progress_callback(message: str, progress: float):
                        self.progress_text.value = f"{file_path.name}: {message}"
                        file_progress = (i + progress) / total_files
                        self.progress_bar.value = file_progress
                        try:
                            self._page.update()
                        except:
                            pass
                    
                    # 获取输出格式
                    output_format = self.output_format_dropdown.value
                    
                    # 获取识别参数
                    language = self.config_service.get_config_value("whisper_language", "auto")
                    task = self.config_service.get_config_value("whisper_task", "transcribe")

                    # === 预处理：人声分离（降噪）===
                    input_path = file_path
                    if self.use_vocal_separation:
                        if not self.vocal_loaded:
                            # 尝试自动加载（如果用户已下载模型）
                            try:
                                self._load_vocal_model()
                            except Exception as ex:
                                logger.warning(f"人声分离模型未加载，跳过降噪：{ex}")
                        if self.vocal_loaded:
                            try:
                                temp_dir = self.config_service.get_temp_dir() / "asr_vocals" / f"{file_path.stem}_{i}"
                                temp_dir.mkdir(parents=True, exist_ok=True)

                                def vocal_progress(msg: str, p: float):
                                    # 给分离留出 0.0~0.25 的进度区间
                                    progress_callback(f"降噪中：{msg}", min(0.25, 0.25 * p))

                                vocals_path, _ = self.vocal_service.separate(
                                    audio_path=file_path,
                                    output_dir=temp_dir,
                                    progress_callback=vocal_progress,
                                    output_format="wav",
                                    output_sample_rate=None,
                                )
                                input_path = vocals_path
                                logger.info(f"人声分离完成: {file_path} -> {vocals_path}")
                            except Exception as ex:
                                logger.error(f"人声分离失败，继续使用原文件识别: {ex}")
                                input_path = file_path
                    
                    # 根据输出格式选择识别方法
                    if output_format in ['srt', 'vtt', 'lrc']:
                        # 使用带时间戳的识别方法
                        segments = self.speech_service.recognize_with_timestamps(
                            input_path,
                            language=language,
                            task=task,
                            progress_callback=progress_callback
                        )
                        
                        # AI 修复字幕（如果启用）
                        if self.use_ai_fix and self.ai_fix_service.is_configured() and segments:
                            try:
                                self.progress_text.value = f"AI 修复中: {file_path.name}"
                                self._page.update()
                                
                                def ai_fix_progress(msg, prog):
                                    self.progress_text.value = f"{msg}: {file_path.name}"
                                    try:
                                        self._page.update()
                                    except:
                                        pass
                                
                                segments = self.ai_fix_service.fix_segments(
                                    segments,
                                    language=language,
                                    progress_callback=ai_fix_progress
                                )
                                logger.info(f"AI 修复完成: {file_path.name}")
                            except Exception as e:
                                logger.warning(f"AI 修复失败，使用原始结果: {e}")
                        
                        # 转换为对应的字幕格式
                        if output_format == 'srt':
                            content = segments_to_srt(segments)
                        elif output_format == 'vtt':
                            content = segments_to_vtt(segments)
                        else:  # lrc
                            # 使用文件名作为标题
                            content = segments_to_lrc(segments, title=file_path.stem)
                    else:
                        # txt 格式，使用普通识别方法
                        text = self.speech_service.recognize(
                            input_path,
                            language=language,
                            task=task,
                            progress_callback=progress_callback
                        )
                        
                        # AI 修复文本（如果启用）
                        if self.use_ai_fix and self.ai_fix_service.is_configured() and text:
                            try:
                                self.progress_text.value = f"AI 修复中: {file_path.name}"
                                self._page.update()
                                
                                def ai_fix_progress(msg, prog):
                                    self.progress_text.value = f"{msg}: {file_path.name}"
                                    try:
                                        self._page.update()
                                    except:
                                        pass
                                
                                text = self.ai_fix_service.fix_plain_text(
                                    text,
                                    language=language,
                                    progress_callback=ai_fix_progress
                                )
                                logger.info(f"AI 修复完成: {file_path.name}")
                            except Exception as e:
                                logger.warning(f"AI 修复失败，使用原始结果: {e}")
                        
                        content = text
                    
                    # 确定输出路径
                    if self.output_mode_radio.value == "custom":
                        output_dir = Path(self.custom_output_dir.value)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = output_dir / f"{file_path.stem}.{output_format}"
                    else:  # same
                        output_path = file_path.with_suffix(f".{output_format}")
                    
                    # 根据全局设置决定是否添加序号
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)
                    
                    # 保存结果
                    # 统一使用 UTF-8 with BOM 编码，确保中文正确显示
                    # UTF-8 with BOM 可以让 Windows 记事本等程序正确识别编码
                    with open(output_path, 'w', encoding='utf-8-sig') as f:
                        f.write(content)
                    used_encoding = "UTF-8 with BOM"
                    
                    logger.info(f"识别完成: {file_path} -> {output_path} (编码: {used_encoding})")
                    
                    # 清理人声分离临时目录
                    if self.use_vocal_separation and input_path != file_path:
                        try:
                            import shutil
                            temp_dir = self.config_service.get_temp_dir() / "asr_vocals" / f"{file_path.stem}_{i}"
                            if temp_dir.exists():
                                shutil.rmtree(temp_dir, ignore_errors=True)
                                logger.debug(f"已清理人声分离临时目录: {temp_dir}")
                        except:
                            pass
                    
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
                self._page.update()
            except:
                pass
    
    async def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        await self._on_select_files(e)
    
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
        self._page.overlay.append(dialog)
        dialog.open = True
        try:
            self._page.update()
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
        self._page.overlay.append(dialog)
        dialog.open = True
        try:
            self._page.update()
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
        self._page.overlay.append(dialog)
        dialog.open = True
        try:
            self._page.update()
        except:
            pass
    
    def _show_cuda_warning(self) -> None:
        """显示 CUDA 使用警告。"""
        warning_dialog = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.ORANGE, size=24),
                    ft.Text("重要提示", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "您已使用 CUDA GPU 加速加载了语音识别模型。",
                            size=14,
                        ),
                        ft.Container(height=10),
                        ft.Text(
                            "⚠️ 由于 sherpa-onnx 的适配性问题：",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ORANGE,
                        ),
                        ft.Container(height=5),
                        ft.Text(
                            "• 使用 CUDA 后，其他 AI 功能（智能抠图、人声分离等）可能无法正常工作",
                            size=13,
                        ),
                        ft.Text(
                            "• 如需使用其他 AI 功能，建议重启程序",
                            size=13,
                        ),
                        ft.Container(height=10),
                        ft.Text(
                            "💡 建议：如果需要频繁切换使用不同功能，可考虑使用 CPU 模式或 DirectML。",
                            size=13,
                            italic=True,
                            color=ft.Colors.BLUE_GREY_700,
                        ),
                    ],
                    spacing=5,
                    tight=True,
                ),
                padding=10,
            ),
            actions=[
                ft.TextButton("我知道了", on_click=lambda e: self._close_dialog(warning_dialog)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.overlay.append(warning_dialog)
        warning_dialog.open = True
        try:
            self._page.update()
        except:
            pass
    
    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        """关闭对话框。"""
        dialog.open = False
        try:
            self._page.update()
        except:
            pass
    
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
            self._update_process_button()
            snackbar = ft.SnackBar(content=ft.Text(f"已添加 {added_count} 个文件"), bgcolor=ft.Colors.GREEN)
            self._page.overlay.append(snackbar)
            snackbar.open = True
        elif skipped_count > 0:
            snackbar = ft.SnackBar(content=ft.Text("语音转文字不支持该格式"), bgcolor=ft.Colors.ORANGE)
            self._page.overlay.append(snackbar)
            snackbar.open = True
        self._page.update()
    
    def cleanup(self) -> None:
        """清理资源，释放内存。"""
        import gc
        # 清理文件列表
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        # 卸载语音识别模型
        if hasattr(self, 'speech_service') and self.speech_service:
            self.speech_service.unload_model()
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
