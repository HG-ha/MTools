# -*- coding: utf-8 -*-
"""视频配字幕视图模块。

提供视频自动配字幕功能的用户界面。
"""

import os
import tempfile
import threading
from pathlib import Path
from typing import Callable, List, Optional, Dict, Any

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_LARGE,
    WHISPER_MODELS,
    SENSEVOICE_MODELS,
    DEFAULT_WHISPER_MODEL_KEY,
    DEFAULT_SENSEVOICE_MODEL_KEY,
    DEFAULT_VAD_MODEL_KEY,
    DEFAULT_VOCAL_MODEL_KEY,
    VAD_MODELS,
    VOCAL_SEPARATION_MODELS,
    SenseVoiceModelInfo,
    WhisperModelInfo,
)
from services import ConfigService, FFmpegService, SpeechRecognitionService, TranslateService, VADService, VocalSeparationService, SUPPORTED_LANGUAGES
from utils import format_file_size, logger, get_system_fonts
from utils.subtitle_utils import segments_to_srt
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoSubtitleView(ft.Container):
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    """视频配字幕视图类。
    
    提供视频自动配字幕功能，包括：
    - 语音识别生成字幕
    - 自定义字幕样式（字体、大小、颜色等）
    - 将字幕烧录到视频中
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频配字幕视图。
        
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
        
        # 每个视频的独立字幕设置 {file_path: {setting_key: value}}
        self.video_settings: Dict[str, Dict[str, Any]] = {}
        
        # 语音识别相关 - 优先使用 SenseVoice
        self.current_engine: str = self.config_service.get_config_value("video_subtitle_engine", "sensevoice")
        if self.current_engine not in ["whisper", "sensevoice"]:
            self.current_engine = "sensevoice"
        
        if self.current_engine == "sensevoice":
            self.current_model_key: str = DEFAULT_SENSEVOICE_MODEL_KEY
            self.current_model = SENSEVOICE_MODELS[self.current_model_key]
        else:
            self.current_model_key: str = DEFAULT_WHISPER_MODEL_KEY
            self.current_model = WHISPER_MODELS[self.current_model_key]
        
        self.model_loaded: bool = False
        self.model_loading: bool = False
        self.auto_load_model: bool = self.config_service.get_config_value("video_subtitle_auto_load_model", True)
        
        # 初始化服务
        model_dir = self.config_service.get_data_dir() / "models" / "whisper"
        vad_model_dir = self.config_service.get_data_dir() / "models" / "vad"
        vocal_model_dir = self.config_service.get_data_dir() / "models" / "vocal"
        
        # VAD 服务
        self.vad_service: VADService = VADService(vad_model_dir)
        self.vad_loaded: bool = False
        
        # 人声分离服务（用于降噪）
        self.vocal_service: VocalSeparationService = VocalSeparationService(
            vocal_model_dir, 
            ffmpeg_service=self.ffmpeg_service,
            config_service=self.config_service
        )
        self.vocal_loaded: bool = False
        
        # VAD 和人声分离设置（默认启用，效果最好）
        self.use_vad: bool = self.config_service.get_config_value("video_subtitle_use_vad", True)
        self.use_vocal_separation: bool = self.config_service.get_config_value("video_subtitle_use_vocal_separation", True)
        self.current_vocal_model_key: str = self.config_service.get_config_value("video_subtitle_vocal_model_key", DEFAULT_VOCAL_MODEL_KEY)
        if self.current_vocal_model_key not in VOCAL_SEPARATION_MODELS:
            self.current_vocal_model_key = DEFAULT_VOCAL_MODEL_KEY
        
        # 初始化语音识别服务（传入 VAD 服务）
        self.speech_service: SpeechRecognitionService = SpeechRecognitionService(
            model_dir,
            self.ffmpeg_service,
            vad_service=self.vad_service
        )
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 获取系统字体列表
        self.system_fonts = get_system_fonts()
        
        # 翻译服务
        self.translate_service = TranslateService()
        self.enable_translation: bool = False
        self.target_language: str = "en"  # 默认翻译目标语言
        
        # 构建界面
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self.page,
                self.ffmpeg_service,
                on_back=self._on_back_click,
                tool_name="视频配字幕"
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
                ft.Text("视频配字幕", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        self._init_empty_state()
        
        self.file_picker = ft.FilePicker(
            on_result=self._on_files_selected
        )
        self.page.overlay.append(self.file_picker)
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择视频:", size=14, weight=ft.FontWeight.W_500),
                        ft.ElevatedButton(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=lambda _: self._on_select_files(),
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
                                "支持 MP4、AVI、MKV、MOV 等常见视频格式",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    margin=ft.margin.only(left=4, bottom=4),
                ),
                ft.Container(
                    content=self.file_list_view,
                    height=150,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 语音识别引擎选择
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
        
        # 模型选择 - 根据当前引擎初始化
        if self.current_engine == "sensevoice":
            model_options = [
                ft.dropdown.Option(key=k, text=v.display_name)
                for k, v in SENSEVOICE_MODELS.items()
            ]
        else:
            model_options = [
                ft.dropdown.Option(key=k, text=v.display_name)
                for k, v in WHISPER_MODELS.items()
            ]
        
        self.model_dropdown = ft.Dropdown(
            label="选择模型",
            width=420,
            options=model_options,
            value=self.current_model_key,
            on_change=self._on_model_change,
        )
        
        # 模型状态
        self.model_status_icon = ft.Icon(
            ft.Icons.HOURGLASS_EMPTY,
            size=20,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.model_status_text = ft.Text(
            "正在检查模型...",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.model_download_btn = ft.ElevatedButton(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            visible=False,
            on_click=self._on_download_model,
        )
        self.model_load_btn = ft.ElevatedButton(
            "加载模型",
            icon=ft.Icons.PLAY_ARROW,
            visible=False,
            on_click=self._on_load_model,
        )
        self.model_unload_btn = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型",
            visible=False,
            on_click=self._on_unload_model,
        )
        
        self.model_reload_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="重新加载模型",
            visible=False,
            on_click=self._on_load_model,
        )
        
        self.model_delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件（如果模型损坏，可删除后重新下载）",
            visible=False,
            on_click=self._on_delete_model,
        )
        
        model_status_row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.model_download_btn,
                self.model_load_btn,
                self.model_unload_btn,
                self.model_reload_btn,
                self.model_delete_btn,
            ],
            spacing=PADDING_SMALL,
        )
        
        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=self.auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        # GPU 加速提示
        cuda_available = self._check_cuda_available()
        if cuda_available:
            gpu_hint_text = "检测到 CUDA 支持，可使用 NVIDIA GPU 加速"
            gpu_hint_icon = ft.Icons.CHECK_CIRCLE
            gpu_hint_color = ft.Colors.GREEN
        else:
            gpu_hint_text = "sherpa要求使用CUDA，未检测到 CUDA 支持。请下载 CUDA 或 CUDA_FULL 版本"
            gpu_hint_icon = ft.Icons.INFO_OUTLINE
            gpu_hint_color = ft.Colors.ORANGE
        
        gpu_hint = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(gpu_hint_icon, size=14, color=gpu_hint_color),
                    ft.Text(gpu_hint_text, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=6,
            ),
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        recognition_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("语音识别设置", size=14, weight=ft.FontWeight.W_500),
                    self.engine_selector,
                    ft.Row(
                        controls=[self.model_dropdown],
                        spacing=PADDING_MEDIUM,
                    ),
                    model_status_row,
                    self.auto_load_checkbox,
                    gpu_hint,
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # === 预处理设置 ===
        # VAD 设置
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
            "在静音处智能分片，避免在说话中间切断",
            size=10,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 人声分离设置
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
            on_change=self._on_vocal_model_change,
            width=300,
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
        
        preprocess_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预处理设置", size=14, weight=ft.FontWeight.W_500),
                    preprocess_hint,
                    vad_row,
                    vad_hint,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    self.vocal_checkbox,
                    self.vocal_model_dropdown,
                    vocal_status_row,
                    vocal_hint,
                ],
                spacing=4,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 字幕样式设置
        # 字体选择 - 当前选择的字体
        self.current_font_key = self.system_fonts[0][0] if self.system_fonts else "System"
        self.current_font_display = self.system_fonts[0][1] if self.system_fonts else "系统默认"
        self.custom_font_path = None  # 自定义字体文件路径（临时使用）
        
        # 字体选择器显示当前字体
        self.font_display_text = ft.Text(
            self.current_font_display,
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        
        self.font_selector_tile = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FONT_DOWNLOAD_OUTLINED, size=20, color=ft.Colors.PRIMARY),
                    ft.Container(width=8),
                    ft.Column(
                        controls=[
                            ft.Text("字体", size=13, weight=ft.FontWeight.W_500),
                            self.font_display_text,
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=ft.Colors.OUTLINE),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            ink=True,
            on_click=self._open_font_selector_dialog,
            width=200,
        )
        
        # 字体预览
        self.font_preview = ft.Container(
            content=ft.Text(
                "字幕预览 Subtitle Preview 123",
                size=18,
                weight=ft.FontWeight.W_500,
                font_family=self.current_font_key,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.BLACK54,
            padding=ft.padding.symmetric(horizontal=PADDING_MEDIUM, vertical=PADDING_SMALL),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 字体文件选择器
        self.font_file_picker = ft.FilePicker(
            on_result=self._on_font_file_picked
        )
        self.page.overlay.append(self.font_file_picker)
        
        # 字体大小
        self.font_size_field = ft.TextField(
            label="字号",
            value="24",
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        # 字体颜色
        self.font_color_dropdown = ft.Dropdown(
            label="颜色",
            width=120,
            options=[
                ft.dropdown.Option(key="&HFFFFFF", text="白色"),
                ft.dropdown.Option(key="&H00FFFF", text="黄色"),
                ft.dropdown.Option(key="&H00FF00", text="绿色"),
                ft.dropdown.Option(key="&HFF0000", text="蓝色"),
                ft.dropdown.Option(key="&H0000FF", text="红色"),
                ft.dropdown.Option(key="&H000000", text="黑色"),
            ],
            value="&HFFFFFF",
        )
        
        # 字体粗细
        self.font_weight_dropdown = ft.Dropdown(
            label="粗细",
            width=100,
            options=[
                ft.dropdown.Option(key="normal", text="常规"),
                ft.dropdown.Option(key="bold", text="粗体"),
                ft.dropdown.Option(key="light", text="细体"),
            ],
            value="normal",
        )
        
        # 描边宽度（支持无描边）
        self.outline_width_dropdown = ft.Dropdown(
            label="描边",
            width=100,
            options=[
                ft.dropdown.Option(key="0", text="无描边"),
                ft.dropdown.Option(key="1", text="细 (1px)"),
                ft.dropdown.Option(key="2", text="中 (2px)"),
                ft.dropdown.Option(key="3", text="粗 (3px)"),
                ft.dropdown.Option(key="4", text="超粗 (4px)"),
            ],
            value="2",
        )
        
        # 描边颜色
        self.outline_color_dropdown = ft.Dropdown(
            label="描边颜色",
            width=110,
            options=[
                ft.dropdown.Option(key="&H000000", text="黑色"),
                ft.dropdown.Option(key="&HFFFFFF", text="白色"),
                ft.dropdown.Option(key="&H404040", text="深灰色"),
            ],
            value="&H000000",
        )
        
        # 字幕位置
        self.position_dropdown = ft.Dropdown(
            label="位置",
            width=100,
            options=[
                ft.dropdown.Option(key="bottom", text="底部"),
                ft.dropdown.Option(key="top", text="顶部"),
                ft.dropdown.Option(key="center", text="居中"),
            ],
            value="bottom",
        )
        
        # 边距
        self.margin_field = ft.TextField(
            label="边距",
            value="20",
            width=70,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="px",
        )
        
        # 最大宽度（自动换行）
        self.max_width_field = ft.TextField(
            label="最大宽度",
            value="80",
            width=90,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="%",
            tooltip="超过此宽度自动换行",
        )
        
        # 左侧：字体和样式设置
        style_left_column = ft.Column(
            controls=[
                ft.Row([
                    self.font_selector_tile,
                    self.font_size_field,
                    self.font_weight_dropdown,
                ], spacing=PADDING_SMALL),
                ft.Row([
                    self.font_color_dropdown,
                    self.outline_width_dropdown,
                    self.outline_color_dropdown,
                ], spacing=PADDING_SMALL),
                ft.Row([
                    self.position_dropdown,
                    self.margin_field,
                    self.max_width_field,
                ], spacing=PADDING_SMALL),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 右侧：预览效果
        style_right_column = ft.Container(
            content=ft.Column([
                ft.Text("预览效果:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                self.font_preview,
            ], spacing=PADDING_SMALL, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            alignment=ft.alignment.center,
        )
        
        subtitle_style_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("字幕样式", size=14, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=[
                            style_left_column,
                            ft.VerticalDivider(width=1),
                            style_right_column,
                        ],
                        spacing=PADDING_MEDIUM,
                        expand=True,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 多语言翻译设置
        self.translate_checkbox = ft.Checkbox(
            label="启用字幕翻译",
            value=self.enable_translation,
            on_change=self._on_translate_toggle,
        )
        
        # 语言选项
        language_options = [
            ft.dropdown.Option(key=code, text=name) 
            for code, name in SUPPORTED_LANGUAGES.items()
        ]
        
        self.target_lang_dropdown = ft.Dropdown(
            label="目标语言",
            width=150,
            options=language_options,
            value=self.target_language,
            disabled=True,  # 默认禁用，勾选启用翻译后才可用
            on_change=self._on_target_lang_change,
        )
        
        # 翻译模式选项
        self.translate_mode_dropdown = ft.Dropdown(
            label="字幕模式",
            width=180,
            options=[
                ft.dropdown.Option(key="replace", text="替换原文"),
                ft.dropdown.Option(key="bilingual", text="双语字幕"),
                ft.dropdown.Option(key="bilingual_top", text="双语(译文在上)"),
            ],
            value="bilingual",
            disabled=True,
            tooltip="替换原文仅显示翻译，双语同时显示原文和翻译",
        )
        
        translate_settings_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Text("多语言字幕", size=14, weight=ft.FontWeight.W_500),
                        ft.Container(expand=True),
                        ft.Text("使用 Bing 翻译 API", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ]),
                    ft.Row([
                        self.translate_checkbox,
                        self.target_lang_dropdown,
                        self.translate_mode_dropdown,
                    ], spacing=PADDING_MEDIUM),
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
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
        
        self.output_dir_picker = ft.FilePicker(
            on_result=self._on_output_dir_selected
        )
        self.page.overlay.append(self.output_dir_picker)
        
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
        
        # 开始处理按钮
        self.process_btn: ft.Container = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SUBTITLES, size=24),
                        ft.Text("开始配字幕", size=18, weight=ft.FontWeight.W_600),
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
            alignment=ft.alignment.center,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                recognition_area,
                preprocess_area,
                subtitle_style_area,
                translate_settings_area,
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
        
        # 初始化模型状态
        self._init_model_status()
        
        # 初始化 VAD 和人声分离 UI 状态（并自动加载已下载的模型）
        self._init_vad_status(auto_load=True)
        self._init_vocal_status(auto_load=True)
        
        # 自动加载模型
        if self.auto_load_model:
            self._try_auto_load_model()
    
    def _init_empty_state(self) -> None:
        """初始化空文件列表状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.VIDEO_FILE,
                            size=48,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "未选择文件",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "点击此处选择视频文件",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL // 2,
                ),
                height=118,
                alignment=ft.alignment.center,
                on_click=lambda _: self._on_select_files(),
                ink=True,
            )
        )
    
    def _check_cuda_available(self) -> bool:
        """检测是否支持 CUDA。
        
        Returns:
            是否支持 CUDA
        """
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            return 'CUDAExecutionProvider' in available_providers
        except ImportError:
            return False
        except Exception:
            return False
    
    def _on_back_click(self, e: ft.ControlEvent = None) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _on_select_files(self) -> None:
        """选择文件。"""
        self.file_picker.pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=["mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v"],
            allow_multiple=True,
        )
    
    def _on_files_selected(self, e: ft.FilePickerResultEvent) -> None:
        """文件选择结果处理。"""
        if e.files:
            for f in e.files:
                file_path = Path(f.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
            self._update_process_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if not self.selected_files:
            self._init_empty_state()
            return
        
        self.file_list_view.controls.clear()
        
        for file_path in self.selected_files:
            try:
                file_size = format_file_size(file_path.stat().st_size)
            except Exception:
                file_size = "未知"
            
            # 检查是否有自定义设置
            file_key = str(file_path)
            has_custom_settings = file_key in self.video_settings
            
            file_row = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.VIDEO_FILE, size=20, color=ft.Colors.PRIMARY),
                    ft.Text(
                        file_path.name,
                        size=13,
                        expand=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(file_size, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    # 自定义设置标记
                    ft.Container(
                        content=ft.Text("已设置", size=10, color=ft.Colors.PRIMARY),
                        bgcolor=ft.Colors.PRIMARY_CONTAINER,
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        visible=has_custom_settings,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.TUNE,
                        icon_size=18,
                        tooltip="单独设置字幕样式",
                        icon_color=ft.Colors.PRIMARY if has_custom_settings else None,
                        on_click=lambda _, p=file_path: self._open_video_settings_dialog(p),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.PREVIEW,
                        icon_size=18,
                        tooltip="预览字幕效果",
                        on_click=lambda _, p=file_path: self._preview_subtitle_effect(p),
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
        
        self.page.update()
    
    def _preview_subtitle_effect(self, file_path: Path) -> None:
        """预览字幕效果。
        
        提取视频第一帧并在上面渲染当前字幕样式。
        
        Args:
            file_path: 视频文件路径
        """
        import cv2
        import base64
        import numpy as np
        
        try:
            # 打开视频获取第一帧
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                self._show_snackbar("无法打开视频文件")
                return
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                self._show_snackbar("无法读取视频帧")
                return
            
            # 获取视频尺寸
            height, width = frame.shape[:2]
            
            # 获取该视频的字幕设置（优先使用单独设置）
            settings = self._get_video_settings(file_path)
            
            # 准备字幕样式参数
            font_size = int(settings["font_size"])
            position = settings["position"]
            margin = int(settings["margin"])
            max_width_percent = int(settings["max_width"])
            outline_width = int(settings["outline_width"])
            font_weight = settings["font_weight"]
            is_bold = font_weight == "bold"
            custom_font_path = settings.get("custom_font_path")
            font_key = settings["font_key"]
            font_display = settings["font_display"]
            font_color = settings["font_color"]
            outline_color = settings["outline_color"]
            
            # 解析颜色（ASS 格式 &HBBGGRR 转 BGR）
            def parse_ass_color(ass_color: str) -> tuple:
                """将 ASS 颜色转换为 BGR。"""
                color_hex = ass_color.replace("&H", "").replace("&h", "")
                if len(color_hex) == 6:
                    b = int(color_hex[0:2], 16)
                    g = int(color_hex[2:4], 16)
                    r = int(color_hex[4:6], 16)
                    return (b, g, r)
                return (255, 255, 255)
            
            font_color_bgr = parse_ass_color(font_color)
            outline_color_bgr = parse_ass_color(outline_color)
            
            # 示例字幕文本（根据翻译设置显示不同内容）
            if self.enable_translation:
                translate_mode = self.translate_mode_dropdown.value
                if translate_mode == "replace":
                    sample_text = "This is a subtitle preview"  # 只显示译文
                elif translate_mode == "bilingual":
                    sample_text = "这是字幕预览效果\nThis is a subtitle preview"
                elif translate_mode == "bilingual_top":
                    sample_text = "This is a subtitle preview\n这是字幕预览效果"
                else:
                    sample_text = "这是字幕预览效果 Subtitle Preview"
            else:
                sample_text = "这是字幕预览效果 Subtitle Preview"
            
            # 计算最大字符数（用于换行演示）
            estimated_char_width = font_size * 0.6
            max_line_width = width * max_width_percent / 100
            max_chars = int(max_line_width / estimated_char_width)
            max_chars = max(10, min(max_chars, 50))
            
            # 自动换行
            lines = []
            if len(sample_text) > max_chars:
                current_line = ""
                for char in sample_text:
                    current_line += char
                    if len(current_line) >= max_chars:
                        lines.append(current_line)
                        current_line = ""
                if current_line:
                    lines.append(current_line)
            else:
                lines = [sample_text]
            
            # 使用 OpenCV 渲染文字（使用 putText，支持有限）
            # 注意：OpenCV 的 putText 对中文支持有限，这里使用 PIL 来渲染
            try:
                from PIL import Image, ImageDraw, ImageFont
                
                # 转换为 PIL Image
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                draw = ImageDraw.Draw(pil_image)
                
                # 尝试加载字体
                try:
                    if custom_font_path:
                        font = ImageFont.truetype(custom_font_path, font_size)
                    else:
                        # 尝试加载系统字体
                        font_name = font_key
                        # Windows 字体路径
                        import platform
                        if platform.system() == "Windows":
                            import os
                            font_paths = [
                                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", f"{font_name}.ttf"),
                                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", f"{font_name}.ttc"),
                                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "msyh.ttc"),  # 微软雅黑
                                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "simhei.ttf"),  # 黑体
                            ]
                            font = None
                            for fp in font_paths:
                                if os.path.exists(fp):
                                    try:
                                        font = ImageFont.truetype(fp, font_size)
                                        break
                                    except:
                                        continue
                            if font is None:
                                font = ImageFont.load_default()
                        else:
                            font = ImageFont.truetype(font_name, font_size)
                except Exception:
                    font = ImageFont.load_default()
                
                # 计算文本位置
                line_height = font_size + 4
                total_text_height = line_height * len(lines)
                
                if position == "bottom":
                    y_start = height - margin - total_text_height
                elif position == "top":
                    y_start = margin
                else:  # center
                    y_start = (height - total_text_height) // 2
                
                # 渲染每行文字
                for i, line in enumerate(lines):
                    # 计算文本宽度以居中
                    try:
                        bbox = draw.textbbox((0, 0), line, font=font)
                        text_width = bbox[2] - bbox[0]
                    except:
                        text_width = len(line) * font_size
                    
                    x = (width - text_width) // 2
                    y = y_start + i * line_height
                    
                    # 绘制描边（通过在多个方向绘制文字）
                    outline_rgb = (outline_color_bgr[2], outline_color_bgr[1], outline_color_bgr[0])
                    font_rgb = (font_color_bgr[2], font_color_bgr[1], font_color_bgr[0])
                    
                    # 只有描边宽度>0时才绘制描边
                    if outline_width > 0:
                        for dx in range(-outline_width, outline_width + 1):
                            for dy in range(-outline_width, outline_width + 1):
                                if dx != 0 or dy != 0:
                                    draw.text((x + dx, y + dy), line, font=font, fill=outline_rgb)
                    
                    # 绘制文字
                    draw.text((x, y), line, font=font, fill=font_rgb)
                    
                    # 模拟粗体效果（绘制两次，偏移1像素）
                    if is_bold:
                        draw.text((x + 1, y), line, font=font, fill=font_rgb)
                
                # 转回 OpenCV 格式
                frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                
            except ImportError:
                # 如果没有 PIL，使用简单的 OpenCV 渲染（不支持中文）
                font_color_bgr_tuple = font_color_bgr
                font_scale = font_size / 24
                
                if position == "bottom":
                    y_pos = height - margin
                elif position == "top":
                    y_pos = margin + font_size
                else:
                    y_pos = height // 2
                
                # 计算文本宽度以居中
                text_size = cv2.getTextSize(sample_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)[0]
                x_pos = (width - text_size[0]) // 2
                
                # 绘制描边
                cv2.putText(frame, sample_text, (x_pos, y_pos), cv2.FONT_HERSHEY_SIMPLEX,
                           font_scale, outline_color_bgr, outline_width * 2 + 2, cv2.LINE_AA)
                # 绘制文字
                cv2.putText(frame, sample_text, (x_pos, y_pos), cv2.FONT_HERSHEY_SIMPLEX,
                           font_scale, font_color_bgr_tuple, 2, cv2.LINE_AA)
            
            # 获取页面尺寸，计算最大预览尺寸（留出边距）
            page_width = self.page.width or 1200
            page_height = self.page.height or 800
            max_preview_width = int(page_width - 100)
            max_preview_height = int(page_height - 200)
            
            # 缩放预览图
            scale = min(max_preview_width / width, max_preview_height / height, 1.0)
            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
            else:
                new_width = width
                new_height = height
            
            # 转换为 base64 用于显示
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # 显示预览对话框（接近全屏）
            dialog_width = min(new_width + 60, page_width - 40)
            dialog_height = min(new_height + 150, page_height - 40)
            
            preview_dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Text("字幕效果预览", size=18, weight=ft.FontWeight.W_500),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        on_click=lambda e: self._close_preview_dialog(preview_dialog),
                    ),
                ]),
                content=ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Image(
                                src_base64=img_base64,
                                fit=ft.ImageFit.CONTAIN,
                                width=new_width,
                                height=new_height,
                            ),
                            alignment=ft.alignment.center,
                        ),
                        ft.Container(height=PADDING_SMALL),
                        ft.Row([
                            ft.Text(
                                f"📹 {file_path.name}",
                                size=13,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                f"字体: {font_display} | 字号: {font_size} | 位置: {position}",
                                size=13,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ]),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=dialog_width - 40,
                    padding=PADDING_MEDIUM,
                ),
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
            )
            
            self.page.overlay.append(preview_dialog)
            preview_dialog.open = True
            self.page.update()
            
        except Exception as ex:
            logger.error(f"预览字幕效果失败: {ex}", exc_info=True)
            self._show_snackbar(f"预览失败: {str(ex)}")
    
    def _close_preview_dialog(self, dialog: ft.AlertDialog) -> None:
        """关闭预览对话框。"""
        dialog.open = False
        self.page.update()
    
    def _get_video_settings(self, file_path: Path) -> Dict[str, Any]:
        """获取视频的字幕设置（如果有自定义设置则使用，否则使用全局设置）。"""
        file_key = str(file_path)
        if file_key in self.video_settings:
            return self.video_settings[file_key]
        
        # 返回当前全局设置
        return {
            "font_key": self.current_font_key,
            "font_display": self.current_font_display,
            "custom_font_path": self.custom_font_path,
            "font_size": self.font_size_field.value or "24",
            "font_weight": self.font_weight_dropdown.value or "normal",
            "font_color": self.font_color_dropdown.value or "&HFFFFFF",
            "outline_width": self.outline_width_dropdown.value or "2",
            "outline_color": self.outline_color_dropdown.value or "&H000000",
            "position": self.position_dropdown.value or "bottom",
            "margin": self.margin_field.value or "20",
            "max_width": self.max_width_field.value or "80",
        }
    
    def _open_video_settings_dialog(self, file_path: Path) -> None:
        """打开单个视频的字幕设置对话框（带实时预览）。"""
        import cv2
        import base64
        import numpy as np
        
        file_key = str(file_path)
        
        # 获取当前设置
        settings = self._get_video_settings(file_path)
        
        # 获取视频信息
        cap = cv2.VideoCapture(str(file_path))
        if not cap.isOpened():
            self._show_snackbar("无法打开视频文件")
            return
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration = total_frames / fps if fps > 0 else 0
        video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # 读取第一帧
        ret, first_frame = cap.read()
        cap.release()
        
        if not ret or first_frame is None:
            self._show_snackbar("无法读取视频帧")
            return
        
        # 存储当前帧用于预览更新
        current_frame = [first_frame.copy()]  # 使用列表以便在闭包中修改
        current_time = [0.0]
        
        # 计算页面尺寸，动态调整预览区域大小（接近全屏）
        page_width = self.page.width or 1200
        page_height = self.page.height or 800
        
        # 对话框尺寸（留出边距）
        dialog_width = int(page_width - 80)
        dialog_height = int(page_height - 100)
        
        # 设置面板宽度（增大以容纳更多控件）
        settings_panel_width = 400
        
        # 预览区域尺寸（对话框宽度 - 设置面板 - 边距）
        preview_panel_width = dialog_width - settings_panel_width - 100
        preview_panel_height = dialog_height - 180
        
        # 根据视频比例计算预览图像尺寸
        video_aspect = video_width / video_height if video_height > 0 else 16/9
        preview_max_width = preview_panel_width - 20
        preview_max_height = preview_panel_height - 100
        
        if preview_max_width / video_aspect <= preview_max_height:
            preview_img_width = preview_max_width
            preview_img_height = int(preview_max_width / video_aspect)
        else:
            preview_img_height = preview_max_height
            preview_img_width = int(preview_max_height * video_aspect)
        
        # 预览图像控件
        preview_image = ft.Image(
            fit=ft.ImageFit.CONTAIN,
            width=preview_img_width,
            height=preview_img_height,
        )
        
        # 时间显示
        time_text = ft.Text(
            f"00:00 / {int(duration // 60):02d}:{int(duration % 60):02d}",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 进度条
        time_slider = ft.Slider(
            min=0,
            max=max(1, duration),
            value=0,
            label="{value:.1f}s",
            expand=True,
        )
        
        def render_preview():
            """渲染当前帧的字幕预览。"""
            try:
                from PIL import Image, ImageDraw, ImageFont
                
                frame = current_frame[0].copy()
                h, w = frame.shape[:2]
                
                # 获取当前设置值
                font_size = int(font_size_field.value or "24")
                position = position_dropdown.value or "bottom"
                margin = int(margin_field.value or "20")
                outline_width = int(outline_width_dropdown.value or "2")
                is_bold = font_weight_dropdown.value == "bold"
                
                # 颜色解析
                def parse_color(c):
                    c = c.replace("&H", "").replace("&h", "")
                    if len(c) == 6:
                        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
                    return (255, 255, 255)
                
                font_color = parse_color(current_font_color[0] or "&HFFFFFF")
                outline_color = parse_color(current_outline_color[0] or "&H000000")
                
                # 转为 RGB
                font_rgb = (font_color[2], font_color[1], font_color[0])
                outline_rgb = (outline_color[2], outline_color[1], outline_color[0])
                
                # 示例文本（根据翻译设置显示不同内容）
                if self.enable_translation:
                    translate_mode = self.translate_mode_dropdown.value
                    if translate_mode == "replace":
                        sample_text = "This is a subtitle preview text"
                    elif translate_mode == "bilingual":
                        sample_text = "这是字幕预览效果\nThis is a subtitle preview"
                    elif translate_mode == "bilingual_top":
                        sample_text = "This is a subtitle preview\n这是字幕预览效果"
                    else:
                        sample_text = "这是一段较长的字幕预览效果文本 This is a subtitle preview text"
                else:
                    sample_text = "这是一段较长的字幕预览效果文本 This is a subtitle preview text"
                
                # 获取最大宽度百分比
                max_width_pct = int(max_width_field.value or "80")
                max_line_width = w * max_width_pct / 100
                
                # 使用 PIL 渲染
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                draw = ImageDraw.Draw(pil_image)
                
                # 加载字体（使用当前选择的字体）
                try:
                    font_path = current_custom_font_path[0]
                    if font_path and os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, font_size)
                    else:
                        font_paths = [
                            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "msyh.ttc"),
                            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "simhei.ttf"),
                        ]
                        font = None
                        for fp in font_paths:
                            if os.path.exists(fp):
                                try:
                                    font = ImageFont.truetype(fp, font_size)
                                    break
                                except:
                                    continue
                        if font is None:
                            font = ImageFont.load_default()
                except:
                    font = ImageFont.load_default()
                
                # 自动换行
                def wrap_text_by_width(text, font, max_width):
                    """根据最大宽度自动换行。"""
                    lines = []
                    current_line = ""
                    for char in text:
                        test_line = current_line + char
                        try:
                            bbox = draw.textbbox((0, 0), test_line, font=font)
                            line_width = bbox[2] - bbox[0]
                        except:
                            line_width = len(test_line) * font_size * 0.6
                        
                        if line_width <= max_width:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = char
                    if current_line:
                        lines.append(current_line)
                    return lines if lines else [text]
                
                lines = wrap_text_by_width(sample_text, font, max_line_width)
                line_height = font_size + 4
                total_text_height = len(lines) * line_height
                
                # 计算起始 Y 位置
                if position == "bottom":
                    start_y = h - margin - total_text_height
                elif position == "top":
                    start_y = margin
                else:
                    start_y = (h - total_text_height) // 2
                
                # 绘制每行文字
                for i, line in enumerate(lines):
                    try:
                        bbox = draw.textbbox((0, 0), line, font=font)
                        text_width = bbox[2] - bbox[0]
                    except:
                        text_width = len(line) * font_size * 0.6
                    
                    x = (w - text_width) // 2
                    y = start_y + i * line_height
                    
                    # 绘制描边
                    if outline_width > 0:
                        for dx in range(-outline_width, outline_width + 1):
                            for dy in range(-outline_width, outline_width + 1):
                                if dx != 0 or dy != 0:
                                    draw.text((x + dx, y + dy), line, font=font, fill=outline_rgb)
                    
                    # 绘制文字
                    draw.text((x, y), line, font=font, fill=font_rgb)
                    if is_bold:
                        draw.text((x + 1, y), line, font=font, fill=font_rgb)
                
                # 转回 OpenCV 并缩放
                frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                
                # 缩放到动态计算的预览尺寸（使用更高质量的插值算法）
                scale = min(preview_img_width / w, preview_img_height / h)
                new_w, new_h = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                
                # 转为 base64（更高质量）
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                
                preview_image.src_base64 = img_base64
                self.page.update()
                
            except Exception as ex:
                logger.error(f"渲染预览失败: {ex}")
        
        def on_slider_change(e):
            """进度条变化时更新预览。"""
            seek_time = e.control.value
            current_time[0] = seek_time
            
            # 更新时间显示
            time_text.value = f"{int(seek_time // 60):02d}:{int(seek_time % 60):02d} / {int(duration // 60):02d}:{int(duration % 60):02d}"
            
            # 读取对应帧
            cap = cv2.VideoCapture(str(file_path))
            if cap.isOpened():
                frame_num = int(seek_time * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                cap.release()
                
                if ret and frame is not None:
                    current_frame[0] = frame
                    render_preview()
        
        def on_setting_change(e):
            """设置变化时更新预览。"""
            render_preview()
        
        time_slider.on_change = on_slider_change
        
        # 当前字体设置
        current_font_key = [settings["font_key"]]
        current_font_display = [settings["font_display"]]
        current_custom_font_path = [settings.get("custom_font_path")]
        
        # 当前颜色设置
        current_font_color = [settings["font_color"]]
        current_outline_color = [settings["outline_color"]]
        
        # 构建字体查找表
        font_lookup = {}
        windows_fonts_dir = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts")
        
        for font_key, display_name in self.system_fonts:
            font_path = None
            if font_key != "System":
                # 尝试多种方式查找字体文件
                possible_names = [font_key]
                # 添加常见的变体名称
                if " " in font_key:
                    possible_names.append(font_key.replace(" ", ""))
                
                for name in possible_names:
                    for ext in [".ttf", ".ttc", ".otf", ".TTF", ".TTC", ".OTF"]:
                        test_path = os.path.join(windows_fonts_dir, name + ext)
                        if os.path.exists(test_path):
                            font_path = test_path
                            break
                    if font_path:
                        break
            
            font_lookup[font_key] = {"display_name": display_name, "path": font_path}
        
        # ASS颜色转换为十六进制RGB
        def ass_to_hex(ass_color: str) -> str:
            """将ASS颜色(&HBBGGRR)转换为#RRGGBB格式。"""
            c = ass_color.replace("&H", "").replace("&h", "")
            if len(c) == 6:
                return f"#{c[4:6]}{c[2:4]}{c[0:2]}"
            return "#FFFFFF"
        
        def hex_to_ass(hex_color: str) -> str:
            """将#RRGGBB转换为ASS颜色(&HBBGGRR)格式。"""
            c = hex_color.replace("#", "")
            if len(c) == 6:
                return f"&H{c[4:6]}{c[2:4]}{c[0:2]}"
            return "&HFFFFFF"
        
        # ===== 字体选择区域（直接嵌入界面） =====
        font_list_column = ft.Column(controls=[], spacing=0, scroll=ft.ScrollMode.AUTO)
        
        # 分页参数
        font_page_size = 30  # 每页显示数量
        font_loaded_count = [0]  # 已加载数量
        font_filter_text = [""]  # 当前搜索文本
        
        def select_font(key, name, path=None):
            """选择字体。"""
            current_font_key[0] = key
            current_font_display[0] = name
            current_custom_font_path[0] = path
            update_font_list(font_filter_text[0], keep_selection=True)
            render_preview()
        
        def get_filtered_fonts(filter_text=""):
            """获取过滤后的字体列表。"""
            if not filter_text:
                return list(self.system_fonts)
            return [(fk, dn) for fk, dn in self.system_fonts 
                    if filter_text.lower() in dn.lower() or filter_text.lower() in fk.lower()]
        
        def update_font_list(filter_text="", keep_selection=False):
            """更新字体列表显示（分页加载）。"""
            font_filter_text[0] = filter_text
            font_list_column.controls.clear()
            
            filtered = get_filtered_fonts(filter_text)
            total_count = len(filtered)
            
            # 搜索时显示更多结果，否则只显示初始数量
            display_count = min(font_page_size, total_count) if not filter_text else min(50, total_count)
            font_loaded_count[0] = display_count
            
            for fk, dn in filtered[:display_count]:
                is_selected = fk == current_font_key[0]
                font_path = font_lookup.get(fk, {}).get("path")
                font_list_column.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(dn, size=12, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Icon(ft.Icons.CHECK, size=14, color=ft.Colors.PRIMARY) if is_selected else ft.Container(width=14),
                        ]),
                        padding=ft.padding.symmetric(horizontal=8, vertical=6),
                        ink=True,
                        on_click=lambda _, key=fk, name=dn, p=font_path: select_font(key, name, p),
                        bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
                        border_radius=4,
                    )
                )
            
            # 如果还有更多字体，添加"加载更多"按钮
            if display_count < total_count:
                font_list_column.controls.append(
                    ft.Container(
                        content=ft.Text(
                            f"显示 {display_count}/{total_count} 个，输入搜索查找更多",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        padding=ft.padding.symmetric(vertical=8),
                        alignment=ft.alignment.center,
                    )
                )
            
            self.page.update()
        
        # 字体搜索框
        font_search_field = ft.TextField(
            hint_text="搜索字体...",
            prefix_icon=ft.Icons.SEARCH,
            height=36,
            content_padding=8,
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=True,
            on_change=lambda e: update_font_list(e.control.value),
        )
        
        # 对话框内的字体文件选择器
        dialog_font_picker = ft.FilePicker()
        
        def on_dialog_font_picked(e: ft.FilePickerResultEvent):
            """对话框内字体文件选择结果处理。"""
            if e.files and len(e.files) > 0:
                font_file_path = e.files[0].path
                try:
                    font_file = Path(font_file_path)
                    if font_file.exists():
                        font_name = font_file.stem
                        custom_font_key = f"CustomFont_{font_name}"
                        
                        if not hasattr(self.page, 'fonts') or self.page.fonts is None:
                            self.page.fonts = {}
                        self.page.fonts[custom_font_key] = str(font_file)
                        
                        current_font_key[0] = custom_font_key
                        current_font_display[0] = f"{font_name} (外部)"
                        current_custom_font_path[0] = str(font_file)
                        
                        update_font_list()
                        render_preview()
                        
                        logger.info(f"对话框内加载外部字体: {font_file_path}")
                except Exception as ex:
                    logger.error(f"加载字体文件失败: {ex}")
                    self._show_snackbar(f"加载字体失败: {ex}")
        
        dialog_font_picker.on_result = on_dialog_font_picked
        self.page.overlay.append(dialog_font_picker)
        
        def pick_font_file(e):
            """打开字体文件选择器。"""
            dialog_font_picker.pick_files(
                dialog_title="选择字体文件",
                allowed_extensions=["ttf", "otf", "ttc", "woff", "woff2"],
                allow_multiple=False,
            )
        
        # 导入字体按钮
        import_font_btn = ft.ElevatedButton(
            "导入",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=pick_font_file,
            height=36,
        )
        
        # 字体列表容器
        font_list_container = ft.Container(
            content=font_list_column,
            height=120,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=4,
        )
        
        # 初始化字体列表
        update_font_list()
        
        # ===== 颜色选择区域（直接嵌入界面） =====
        # 解析当前颜色的 RGB 值
        def parse_hex_to_rgb(hex_color):
            hex_val = hex_color.replace("#", "")
            r = int(hex_val[0:2], 16) if len(hex_val) >= 2 else 255
            g = int(hex_val[2:4], 16) if len(hex_val) >= 4 else 255
            b = int(hex_val[4:6], 16) if len(hex_val) >= 6 else 255
            return r, g, b
        
        # 字体颜色 RGB 值
        fc_hex = ass_to_hex(current_font_color[0])
        fc_r, fc_g, fc_b = parse_hex_to_rgb(fc_hex)
        font_color_rgb = [fc_r, fc_g, fc_b]
        
        # 描边颜色 RGB 值  
        oc_hex = ass_to_hex(current_outline_color[0])
        oc_r, oc_g, oc_b = parse_hex_to_rgb(oc_hex)
        outline_color_rgb = [oc_r, oc_g, oc_b]
        
        # 字体颜色预览块
        font_color_preview = ft.Container(
            width=32, height=32,
            bgcolor=fc_hex,
            border_radius=4,
            border=ft.border.all(1, ft.Colors.OUTLINE),
        )
        
        # 描边颜色预览块
        outline_color_preview = ft.Container(
            width=32, height=32,
            bgcolor=oc_hex,
            border_radius=4,
            border=ft.border.all(1, ft.Colors.OUTLINE),
        )
        
        # 字体颜色滑动条
        def update_font_color():
            new_hex = f"#{font_color_rgb[0]:02X}{font_color_rgb[1]:02X}{font_color_rgb[2]:02X}"
            font_color_preview.bgcolor = new_hex
            current_font_color[0] = hex_to_ass(new_hex)
            self.page.update()
            render_preview()
        
        def on_fc_r_change(e):
            font_color_rgb[0] = int(e.control.value)
            update_font_color()
        
        def on_fc_g_change(e):
            font_color_rgb[1] = int(e.control.value)
            update_font_color()
        
        def on_fc_b_change(e):
            font_color_rgb[2] = int(e.control.value)
            update_font_color()
        
        fc_r_slider = ft.Slider(min=0, max=255, value=fc_r, active_color=ft.Colors.RED, on_change=on_fc_r_change, expand=True)
        fc_g_slider = ft.Slider(min=0, max=255, value=fc_g, active_color=ft.Colors.GREEN, on_change=on_fc_g_change, expand=True)
        fc_b_slider = ft.Slider(min=0, max=255, value=fc_b, active_color=ft.Colors.BLUE, on_change=on_fc_b_change, expand=True)
        
        # 描边颜色滑动条
        def update_outline_color():
            new_hex = f"#{outline_color_rgb[0]:02X}{outline_color_rgb[1]:02X}{outline_color_rgb[2]:02X}"
            outline_color_preview.bgcolor = new_hex
            current_outline_color[0] = hex_to_ass(new_hex)
            self.page.update()
            render_preview()
        
        def on_oc_r_change(e):
            outline_color_rgb[0] = int(e.control.value)
            update_outline_color()
        
        def on_oc_g_change(e):
            outline_color_rgb[1] = int(e.control.value)
            update_outline_color()
        
        def on_oc_b_change(e):
            outline_color_rgb[2] = int(e.control.value)
            update_outline_color()
        
        oc_r_slider = ft.Slider(min=0, max=255, value=oc_r, active_color=ft.Colors.RED, on_change=on_oc_r_change, expand=True)
        oc_g_slider = ft.Slider(min=0, max=255, value=oc_g, active_color=ft.Colors.GREEN, on_change=on_oc_g_change, expand=True)
        oc_b_slider = ft.Slider(min=0, max=255, value=oc_b, active_color=ft.Colors.BLUE, on_change=on_oc_b_change, expand=True)
        
        # 预设颜色
        preset_colors = ["#FFFFFF", "#000000", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]
        
        def apply_preset_to_font(hex_c):
            r, g, b = parse_hex_to_rgb(hex_c)
            font_color_rgb[0], font_color_rgb[1], font_color_rgb[2] = r, g, b
            fc_r_slider.value, fc_g_slider.value, fc_b_slider.value = r, g, b
            update_font_color()
        
        def apply_preset_to_outline(hex_c):
            r, g, b = parse_hex_to_rgb(hex_c)
            outline_color_rgb[0], outline_color_rgb[1], outline_color_rgb[2] = r, g, b
            oc_r_slider.value, oc_g_slider.value, oc_b_slider.value = r, g, b
            update_outline_color()
        
        font_preset_row = ft.Row([
            ft.Container(width=16, height=16, bgcolor=c, border_radius=2, border=ft.border.all(1, ft.Colors.OUTLINE), 
                        ink=True, on_click=lambda _, hc=c: apply_preset_to_font(hc)) for c in preset_colors
        ], spacing=2)
        
        outline_preset_row = ft.Row([
            ft.Container(width=16, height=16, bgcolor=c, border_radius=2, border=ft.border.all(1, ft.Colors.OUTLINE),
                        ink=True, on_click=lambda _, hc=c: apply_preset_to_outline(hc)) for c in preset_colors
        ], spacing=2)
        
        # 字体颜色区域
        font_color_area = ft.Column([
            ft.Row([
                font_color_preview,
                ft.Column([
                    ft.Row([ft.Text("R", size=10, color=ft.Colors.RED, width=12), fc_r_slider], spacing=2),
                    ft.Row([ft.Text("G", size=10, color=ft.Colors.GREEN, width=12), fc_g_slider], spacing=2),
                    ft.Row([ft.Text("B", size=10, color=ft.Colors.BLUE, width=12), fc_b_slider], spacing=2),
                ], spacing=0, expand=True),
            ], spacing=8),
            font_preset_row,
        ], spacing=4)
        
        # 描边颜色区域
        outline_color_area = ft.Column([
            ft.Row([
                outline_color_preview,
                ft.Column([
                    ft.Row([ft.Text("R", size=10, color=ft.Colors.RED, width=12), oc_r_slider], spacing=2),
                    ft.Row([ft.Text("G", size=10, color=ft.Colors.GREEN, width=12), oc_g_slider], spacing=2),
                    ft.Row([ft.Text("B", size=10, color=ft.Colors.BLUE, width=12), oc_b_slider], spacing=2),
                ], spacing=0, expand=True),
            ], spacing=8),
            outline_preset_row,
        ], spacing=4)
        
        # 创建设置控件（添加 on_change 回调）
        font_size_field = ft.TextField(
            label="字号",
            value=settings["font_size"],
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=on_setting_change,
        )
        
        font_weight_dropdown = ft.Dropdown(
            label="粗细",
            width=100,
            options=[
                ft.dropdown.Option(key="normal", text="常规"),
                ft.dropdown.Option(key="bold", text="粗体"),
                ft.dropdown.Option(key="light", text="细体"),
            ],
            value=settings["font_weight"],
            on_change=on_setting_change,
        )
        
        outline_width_dropdown = ft.Dropdown(
            label="描边",
            width=100,
            options=[
                ft.dropdown.Option(key="0", text="无描边"),
                ft.dropdown.Option(key="1", text="细 (1px)"),
                ft.dropdown.Option(key="2", text="中 (2px)"),
                ft.dropdown.Option(key="3", text="粗 (3px)"),
                ft.dropdown.Option(key="4", text="超粗 (4px)"),
            ],
            value=settings["outline_width"],
            on_change=on_setting_change,
        )
        
        position_dropdown = ft.Dropdown(
            label="位置",
            width=90,
            options=[
                ft.dropdown.Option(key="bottom", text="底部"),
                ft.dropdown.Option(key="top", text="顶部"),
                ft.dropdown.Option(key="center", text="居中"),
            ],
            value=settings["position"],
            on_change=on_setting_change,
        )
        
        margin_field = ft.TextField(
            label="边距",
            value=settings["margin"],
            width=70,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="px",
            on_change=on_setting_change,
        )
        
        max_width_field = ft.TextField(
            label="最大宽度",
            value=settings["max_width"],
            width=90,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="%",
            on_change=on_setting_change,
        )
        
        def cleanup_and_close():
            """清理资源并关闭对话框。"""
            # 从 overlay 中移除 font picker
            if dialog_font_picker in self.page.overlay:
                self.page.overlay.remove(dialog_font_picker)
            dialog.open = False
            self.page.update()
        
        def save_settings(e):
            """保存设置。"""
            saved_settings = {
                "font_key": current_font_key[0],
                "font_display": current_font_display[0],
                "custom_font_path": current_custom_font_path[0],
                "font_size": font_size_field.value,
                "font_weight": font_weight_dropdown.value,
                "font_color": current_font_color[0],
                "outline_width": outline_width_dropdown.value,
                "outline_color": current_outline_color[0],
                "position": position_dropdown.value,
                "margin": margin_field.value,
                "max_width": max_width_field.value,
            }
            self.video_settings[file_key] = saved_settings
            logger.info(f"保存视频字幕设置: {file_path.name} -> 字体: {current_font_display[0]}, 路径: {current_custom_font_path[0]}")
            cleanup_and_close()
            self._update_file_list()
            self._show_snackbar("已保存该视频的字幕设置")
        
        def use_global_settings(e):
            """使用全局设置。"""
            if file_key in self.video_settings:
                del self.video_settings[file_key]
            cleanup_and_close()
            self._update_file_list()
            self._show_snackbar("已恢复使用全局设置")
        
        def close_dialog(e):
            cleanup_and_close()
        
        # 左侧设置面板（直接嵌入字体和颜色选择）
        settings_panel = ft.Column([
            ft.Text(f"📹 {file_path.name}", size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=settings_panel_width - 20),
            ft.Container(height=8),
            
            # 字体选择区域
            ft.Text("字体", size=13, weight=ft.FontWeight.W_500),
            ft.Row([font_search_field, import_font_btn], spacing=PADDING_SMALL),
            font_list_container,
            ft.Container(height=12),
            ft.Row([font_size_field, font_weight_dropdown], spacing=PADDING_SMALL),
            ft.Container(height=10),
            
            # 字体颜色
            ft.Text("字体颜色", size=13, weight=ft.FontWeight.W_500),
            font_color_area,
            ft.Container(height=6),
            
            # 描边颜色
            ft.Text("描边颜色", size=13, weight=ft.FontWeight.W_500),
            outline_color_area,
            ft.Container(height=6),
            
            # 描边和位置
            ft.Text("描边和位置", size=13, weight=ft.FontWeight.W_500),
            ft.Row([outline_width_dropdown, position_dropdown, margin_field, max_width_field], spacing=PADDING_SMALL, wrap=True),
        ], spacing=4, width=settings_panel_width, scroll=ft.ScrollMode.AUTO)
        
        # 右侧预览面板
        preview_panel = ft.Column([
            ft.Text("实时预览", size=14, weight=ft.FontWeight.W_500),
            ft.Container(
                content=preview_image,
                bgcolor=ft.Colors.BLACK,
                border_radius=BORDER_RADIUS_MEDIUM,
                padding=4,
                alignment=ft.alignment.center,
            ),
            ft.Container(height=PADDING_SMALL),
            ft.Row([
                time_text,
                time_slider,
            ], spacing=PADDING_SMALL, vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
        ], spacing=PADDING_SMALL, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        
        # 对话框内容
        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.TUNE, size=24),
                ft.Container(width=8),
                ft.Text("字幕样式设置", size=18, weight=ft.FontWeight.W_500),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.CLOSE, on_click=close_dialog),
            ]),
            content=ft.Container(
                content=ft.Row([
                    settings_panel,
                    ft.VerticalDivider(width=1),
                    preview_panel,
                ], spacing=PADDING_LARGE, expand=True),
                width=dialog_width - 60,
                height=dialog_height - 120,
                padding=PADDING_MEDIUM,
            ),
            actions=[
                ft.TextButton("使用全局设置", on_click=use_global_settings),
                ft.Container(expand=True),
                ft.ElevatedButton("保存设置", on_click=save_settings),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
        
        # 初始渲染预览
        render_preview()
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
        # 清理该视频的自定义设置
        file_key = str(file_path)
        if file_key in self.video_settings:
            del self.video_settings[file_key]
        self._update_file_list()
        self._update_process_button()
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
        self._update_process_button()
    
    def _on_engine_change(self, e: ft.ControlEvent) -> None:
        """语音识别引擎变更。"""
        new_engine = e.control.value
        if new_engine == self.current_engine:
            return
        
        self.current_engine = new_engine
        # 保存引擎选择
        self.config_service.set_config_value("video_subtitle_engine", new_engine)
        
        # 更新模型下拉列表
        if new_engine == "whisper":
            self.model_dropdown.options = [
                ft.dropdown.Option(key=k, text=v.display_name)
                for k, v in WHISPER_MODELS.items()
            ]
            self.current_model_key = DEFAULT_WHISPER_MODEL_KEY
            self.current_model = WHISPER_MODELS[self.current_model_key]
        else:
            self.model_dropdown.options = [
                ft.dropdown.Option(key=k, text=v.display_name)
                for k, v in SENSEVOICE_MODELS.items()
            ]
            self.current_model_key = DEFAULT_SENSEVOICE_MODEL_KEY
            self.current_model = SENSEVOICE_MODELS[self.current_model_key]
        
        self.model_dropdown.value = self.current_model_key
        self.model_loaded = False
        
        self._init_model_status()
        self.page.update()
        
        # 如果启用自动加载，尝试加载新模型
        if self.auto_load_model:
            self._try_auto_load_model()
    
    def _on_model_change(self, e: ft.ControlEvent) -> None:
        """模型选择变更。"""
        new_key = e.control.value
        if new_key == self.current_model_key:
            return
        
        self.current_model_key = new_key
        if self.current_engine == "whisper":
            self.current_model = WHISPER_MODELS[new_key]
        else:
            self.current_model = SENSEVOICE_MODELS[new_key]
        
        self.model_loaded = False
        self._init_model_status()
        
        # 如果启用自动加载，尝试加载新模型
        if self.auto_load_model:
            self._try_auto_load_model()
    
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
        """初始化模型状态。"""
        all_exist = self._check_all_model_files_exist()
        
        if all_exist:
            if self.model_loaded:
                self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.model_status_icon.color = ft.Colors.GREEN
                self.model_status_text.value = "模型已加载"
                self.model_status_text.color = ft.Colors.GREEN
                self.model_download_btn.visible = False
                self.model_load_btn.visible = False
                self.model_unload_btn.visible = True
                self.model_reload_btn.visible = True
                self.model_delete_btn.visible = True
            else:
                self.model_status_icon.name = ft.Icons.DOWNLOAD_DONE
                self.model_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
                self.model_status_text.value = f"已下载 ({self.current_model.size_mb}MB)"
                self.model_status_text.color = ft.Colors.ON_SURFACE_VARIANT
                self.model_download_btn.visible = False
                self.model_load_btn.visible = True
                self.model_unload_btn.visible = False
                self.model_reload_btn.visible = False
                self.model_delete_btn.visible = True
        else:
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ORANGE
            self.model_status_text.value = f"模型未下载 ({self.current_model.size_mb}MB)"
            self.model_status_text.color = ft.Colors.ORANGE
            self.model_download_btn.visible = True
            self.model_load_btn.visible = False
            self.model_unload_btn.visible = False
            self.model_reload_btn.visible = False
            self.model_delete_btn.visible = False
        
        self._update_process_button()
        
        try:
            self.page.update()
        except:
            pass
    
    def _init_vad_status(self, auto_load: bool = False) -> None:
        """初始化 VAD 模型状态。
        
        Args:
            auto_load: 是否自动加载模型（如果已下载且已启用）
        """
        vad_model_info = VAD_MODELS[DEFAULT_VAD_MODEL_KEY]
        model_dir = self.vad_service.get_model_dir(DEFAULT_VAD_MODEL_KEY)
        model_path = model_dir / vad_model_info.filename
        
        if model_path.exists():
            if self.vad_loaded:
                self.vad_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.vad_status_icon.color = ft.Colors.GREEN
                self.vad_status_text.value = "已加载"
                self.vad_download_btn.visible = False
                self.vad_load_btn.visible = False
            else:
                self.vad_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.vad_status_icon.color = ft.Colors.GREEN
                self.vad_status_text.value = "已下载"
                self.vad_download_btn.visible = False
                self.vad_load_btn.visible = True
                
                # 自动加载（如果启用且未加载）
                if auto_load and self.use_vad:
                    self._load_vad_model()
        else:
            self.vad_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.vad_status_icon.color = ft.Colors.ORANGE
            self.vad_status_text.value = f"未下载 ({vad_model_info.size_mb}MB)"
            self.vad_download_btn.visible = True
            self.vad_load_btn.visible = False
    
    def _init_vocal_status(self, auto_load: bool = False) -> None:
        """初始化人声分离模型状态。
        
        Args:
            auto_load: 是否自动加载模型（如果已下载且已启用）
        """
        vocal_model_info = VOCAL_SEPARATION_MODELS[self.current_vocal_model_key]
        model_path = self.vocal_service.model_dir / vocal_model_info.filename
        
        if model_path.exists():
            if self.vocal_loaded:
                self.vocal_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.vocal_status_icon.color = ft.Colors.GREEN
                self.vocal_status_text.value = "已加载"
                self.vocal_download_btn.visible = False
                self.vocal_load_btn.visible = False
            else:
                self.vocal_status_icon.name = ft.Icons.CHECK_CIRCLE
                self.vocal_status_icon.color = ft.Colors.GREEN
                self.vocal_status_text.value = "已下载"
                self.vocal_download_btn.visible = False
                self.vocal_load_btn.visible = True
                
                # 自动加载（如果启用且未加载）
                if auto_load and self.use_vocal_separation:
                    self._load_vocal_model()
        else:
            self.vocal_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.vocal_status_icon.color = ft.Colors.ORANGE
            self.vocal_status_text.value = f"未下载 ({vocal_model_info.size_mb}MB)"
            self.vocal_download_btn.visible = True
            self.vocal_load_btn.visible = False
    
    def _on_vad_change(self, e: ft.ControlEvent) -> None:
        """VAD 选项变更事件。"""
        self.use_vad = e.control.value
        self.config_service.set_config_value("video_subtitle_use_vad", self.use_vad)
        self.speech_service.set_use_vad(self.use_vad)
    
    def _on_vocal_change(self, e: ft.ControlEvent) -> None:
        """人声分离选项变更事件。"""
        self.use_vocal_separation = e.control.value
        self.config_service.set_config_value("video_subtitle_use_vocal_separation", self.use_vocal_separation)
        self.vocal_model_dropdown.disabled = not self.use_vocal_separation
        self.page.update()
    
    def _on_vocal_model_change(self, e: ft.ControlEvent) -> None:
        """人声分离模型选择变更事件。"""
        self.current_vocal_model_key = e.control.value
        self.config_service.set_config_value("video_subtitle_vocal_model_key", self.current_vocal_model_key)
        self._init_vocal_status()
    
    def _on_download_vad(self, e: ft.ControlEvent) -> None:
        """下载 VAD 模型。"""
        self.vad_download_btn.visible = False
        self.vad_status_text.value = "下载中..."
        self.page.update()
        
        def download_task():
            try:
                vad_model_info = VAD_MODELS[DEFAULT_VAD_MODEL_KEY]
                
                def progress_callback(progress: float, message: str):
                    self.vad_status_text.value = message
                    try:
                        self.page.update()
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
                self.page.update()
                
                # 自动加载
                self._load_vad_model()
                
            except Exception as ex:
                self.vad_status_icon.name = ft.Icons.ERROR
                self.vad_status_icon.color = ft.Colors.ERROR
                self.vad_status_text.value = f"下载失败: {ex}"
                self.vad_download_btn.visible = True
                self.page.update()
        
        self.page.run_thread(download_task)
    
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
            self.speech_service.set_use_vad(True)
            self.vad_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.vad_status_icon.color = ft.Colors.GREEN
            self.vad_status_text.value = "已加载"
            self.vad_load_btn.visible = False
            self.page.update()
            
        except Exception as ex:
            self.vad_status_text.value = f"加载失败: {ex}"
            self.vad_status_icon.color = ft.Colors.ERROR
            self.page.update()
    
    def _on_download_vocal(self, e: ft.ControlEvent) -> None:
        """下载人声分离模型。"""
        self.vocal_download_btn.visible = False
        self.vocal_status_text.value = "下载中..."
        self.page.update()
        
        def download_task():
            try:
                vocal_model_info = VOCAL_SEPARATION_MODELS[self.current_vocal_model_key]
                
                def progress_callback(progress: float, message: str):
                    self.vocal_status_text.value = message
                    try:
                        self.page.update()
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
                self.page.update()
                
                # 自动加载
                self._load_vocal_model()
                
            except Exception as ex:
                self.vocal_status_icon.name = ft.Icons.ERROR
                self.vocal_status_icon.color = ft.Colors.ERROR
                self.vocal_status_text.value = f"下载失败: {ex}"
                self.vocal_download_btn.visible = True
                self.page.update()
        
        self.page.run_thread(download_task)
    
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
            self.page.update()
            
        except Exception as ex:
            self.vocal_status_text.value = f"加载失败: {ex}"
            self.vocal_status_icon.color = ft.Colors.ERROR
            self.page.update()
    
    def _try_auto_load_model(self) -> None:
        """尝试自动加载模型。"""
        if self._check_all_model_files_exist() and not self.model_loaded:
            threading.Thread(target=self._auto_load_thread, daemon=True).start()
    
    def _auto_load_thread(self) -> None:
        """自动加载模型的线程。"""
        try:
            model_dir = self.speech_service.get_model_dir(self.current_model_key)
            
            if isinstance(self.current_model, SenseVoiceModelInfo):
                model_path = model_dir / self.current_model.model_filename
                tokens_path = model_dir / self.current_model.tokens_filename
                
                self.speech_service.load_sensevoice_model(
                    model_path=model_path,
                    tokens_path=tokens_path,
                    use_gpu=False,
                    language="auto",
                )
            elif isinstance(self.current_model, WhisperModelInfo):
                encoder_path = model_dir / self.current_model.encoder_filename
                decoder_path = model_dir / self.current_model.decoder_filename
                config_path = model_dir / self.current_model.config_filename
                
                self.speech_service.load_model(
                    encoder_path,
                    decoder_path,
                    config_path,
                    use_gpu=False,
                    language="auto",
                )
            
            self.model_loaded = True
            self._init_model_status()
            
        except Exception as ex:
            logger.error(f"自动加载模型失败: {ex}")
    
    def _open_font_selector_dialog(self, e: ft.ControlEvent = None) -> None:
        """打开字体选择对话框。"""
        # 分页参数
        self.font_page_size = 20
        self.font_current_page = 0
        self.filtered_fonts = list(self.system_fonts)
        
        # 搜索框
        self.font_search_field = ft.TextField(
            hint_text="搜索字体...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._filter_font_list,
            expand=True,
            height=40,
            content_padding=10,
            border_radius=BORDER_RADIUS_MEDIUM,
            text_size=14,
        )
        
        # 导入文件按钮
        import_btn = ft.ElevatedButton(
            "导入字体文件",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self._pick_font_file(),
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=16, vertical=0),
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
            ),
        )
        
        # 字体列表容器
        self.font_list_column = ft.Column(
            controls=[],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
        
        font_list_container = ft.Container(
            content=self.font_list_column,
            height=280,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=4,
        )
        
        # 分页控制
        self.font_page_info = ft.Text("", size=12)
        self.font_prev_btn = ft.IconButton(
            ft.Icons.CHEVRON_LEFT,
            on_click=lambda e: self._change_font_page(-1),
        )
        self.font_next_btn = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT,
            on_click=lambda e: self._change_font_page(1),
        )
        
        # 预览区域
        self.dialog_font_preview = ft.Container(
            content=ft.Text(
                "字幕预览 Subtitle Preview 123",
                size=18,
                weight=ft.FontWeight.W_500,
                font_family=self.current_font_key,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.BLACK54,
            padding=ft.padding.symmetric(horizontal=PADDING_MEDIUM, vertical=PADDING_SMALL),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 对话框内容
        dialog_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("选择字体", size=18, weight=ft.FontWeight.W_600),
                            ft.IconButton(ft.Icons.CLOSE, on_click=lambda e: self._close_font_selector_dialog()),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        controls=[self.font_search_field, import_btn],
                        spacing=10,
                    ),
                    ft.Container(height=8),
                    ft.Text(f"共 {len(self.system_fonts)} 个字体", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=4),
                    font_list_container,
                    ft.Row(
                        controls=[
                            self.font_prev_btn,
                            self.font_page_info,
                            self.font_next_btn,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.Text("预览效果:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    self.dialog_font_preview,
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            width=500,
        )
        
        # 创建对话框
        self.font_selector_dialog = ft.AlertDialog(
            content=dialog_content,
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
            content_padding=0,
        )
        
        self.page.overlay.append(self.font_selector_dialog)
        self.font_selector_dialog.open = True
        self.page.update()
        
        # 加载第一页
        self._update_font_page()
    
    def _close_font_selector_dialog(self) -> None:
        """关闭字体选择对话框。"""
        if hasattr(self, 'font_selector_dialog'):
            self.font_selector_dialog.open = False
            self.page.update()
    
    def _filter_font_list(self, e: ft.ControlEvent) -> None:
        """筛选字体列表。"""
        search_text = e.control.value.lower() if e.control.value else ""
        
        if not search_text:
            self.filtered_fonts = list(self.system_fonts)
        else:
            self.filtered_fonts = [
                (key, display) for key, display in self.system_fonts
                if search_text in key.lower() or search_text in display.lower()
            ]
        
        self.font_current_page = 0
        self._update_font_page()
    
    def _change_font_page(self, delta: int) -> None:
        """切换字体列表页码。"""
        new_page = self.font_current_page + delta
        max_page = max(0, (len(self.filtered_fonts) - 1) // self.font_page_size)
        
        if 0 <= new_page <= max_page:
            self.font_current_page = new_page
            self._update_font_page()
    
    def _update_font_page(self) -> None:
        """更新字体列表页面。"""
        start_idx = self.font_current_page * self.font_page_size
        end_idx = start_idx + self.font_page_size
        page_fonts = self.filtered_fonts[start_idx:end_idx]
        
        self.font_list_column.controls.clear()
        
        for font_key, font_display in page_fonts:
            is_selected = font_key == self.current_font_key
            
            font_item = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            font_display,
                            size=14,
                            font_family=font_key,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Icon(
                            ft.Icons.CHECK,
                            size=18,
                            color=ft.Colors.PRIMARY,
                            visible=is_selected,
                        ),
                    ],
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=BORDER_RADIUS_MEDIUM,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
                ink=True,
                on_click=lambda e, key=font_key, display=font_display: self._select_font(key, display),
                on_hover=lambda e, key=font_key: self._preview_font(key) if e.data == "true" else None,
            )
            self.font_list_column.controls.append(font_item)
        
        # 更新分页信息
        total = len(self.filtered_fonts)
        total_pages = max(1, (total + self.font_page_size - 1) // self.font_page_size)
        self.font_page_info.value = f"{self.font_current_page + 1} / {total_pages}"
        self.font_prev_btn.disabled = self.font_current_page == 0
        self.font_next_btn.disabled = self.font_current_page >= total_pages - 1
        
        self.page.update()
    
    def _preview_font(self, font_key: str) -> None:
        """预览字体（悬停时）。"""
        if hasattr(self, 'dialog_font_preview'):
            self.dialog_font_preview.content.font_family = font_key
            self.page.update()
    
    def _select_font(self, font_key: str, font_display: str) -> None:
        """选择字体。"""
        self.current_font_key = font_key
        self.current_font_display = font_display
        self.custom_font_path = None  # 清除自定义字体路径
        
        # 更新显示
        self.font_display_text.value = font_display
        self.font_preview.content.font_family = font_key
        
        # 关闭对话框
        self._close_font_selector_dialog()
        self.page.update()
    
    def _pick_font_file(self) -> None:
        """打开文件选择器选择字体文件。"""
        self.font_file_picker.pick_files(
            dialog_title="选择字体文件",
            allowed_extensions=["ttf", "otf", "ttc", "woff", "woff2"],
            allow_multiple=False,
        )
    
    def _on_font_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """字体文件选择结果处理。"""
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            self._load_custom_font_file(file_path)
    
    def _load_custom_font_file(self, file_path: str) -> None:
        """加载自定义字体文件（临时使用，不永久保存）。"""
        try:
            font_file = Path(file_path)
            if not font_file.exists():
                self._show_snackbar("字体文件不存在")
                return
            
            # 获取字体名称
            font_name = font_file.stem
            custom_font_key = f"CustomFont_{font_name}"
            
            # 将字体添加到页面（临时使用）
            if not hasattr(self.page, 'fonts') or self.page.fonts is None:
                self.page.fonts = {}
            
            self.page.fonts[custom_font_key] = str(font_file)
            self.page.update()
            
            # 更新当前选择
            self.current_font_key = custom_font_key
            self.current_font_display = f"{font_name} (外部)"
            self.custom_font_path = str(font_file)
            
            # 更新显示
            self.font_display_text.value = self.current_font_display
            self.font_preview.content.font_family = custom_font_key
            
            # 关闭对话框
            self._close_font_selector_dialog()
            self.page.update()
            
            logger.info(f"已加载外部字体: {file_path}")
            
        except Exception as ex:
            logger.error(f"加载字体文件失败: {ex}")
            self._show_snackbar(f"加载字体失败: {ex}")
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型选项变更事件。"""
        self.auto_load_model = e.control.value
        self.config_service.set_config_value("video_subtitle_auto_load_model", self.auto_load_model)
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        def confirm_delete(e):
            dialog.open = False
            self.page.update()
            self._do_delete_model()
        
        def cancel_delete(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要删除模型 {self.current_model.display_name} 吗？\n\n删除后需要重新下载才能使用。"),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.ElevatedButton("删除", on_click=confirm_delete, bgcolor=ft.Colors.ERROR, color=ft.Colors.WHITE),
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
            self.speech_service.unload_model()
            self.model_loaded = False
        
        model_dir = self.speech_service.get_model_dir(self.current_model_key)
        
        try:
            # 删除模型文件
            if isinstance(self.current_model, SenseVoiceModelInfo):
                files_to_delete = [
                    model_dir / self.current_model.model_filename,
                    model_dir / self.current_model.tokens_filename,
                ]
            elif isinstance(self.current_model, WhisperModelInfo):
                files_to_delete = [
                    model_dir / self.current_model.encoder_filename,
                    model_dir / self.current_model.decoder_filename,
                    model_dir / self.current_model.config_filename,
                ]
                if hasattr(self.current_model, 'encoder_weights_filename') and self.current_model.encoder_weights_filename:
                    files_to_delete.append(model_dir / self.current_model.encoder_weights_filename)
                if hasattr(self.current_model, 'decoder_weights_filename') and self.current_model.decoder_weights_filename:
                    files_to_delete.append(model_dir / self.current_model.decoder_weights_filename)
            else:
                files_to_delete = []
            
            for file_path in files_to_delete:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"已删除模型文件: {file_path.name}")
            
            # 如果模型目录为空，也删除目录
            try:
                if model_dir.exists() and not any(model_dir.iterdir()):
                    model_dir.rmdir()
                    logger.info(f"模型目录已删除: {model_dir.name}")
            except:
                pass
            
            # 更新状态
            self._init_model_status()
            
        except Exception as e:
            logger.error(f"删除模型文件失败: {e}")
            self._show_snackbar(f"删除失败: {str(e)}")
    
    def _on_download_model(self, e: ft.ControlEvent) -> None:
        """下载模型。"""
        if self.model_loading:
            return
        
        self.model_loading = True
        self.model_download_btn.disabled = True
        self.model_status_text.value = "正在下载模型..."
        self.page.update()
        
        def download_thread():
            try:
                def progress_callback(progress: float, message: str):
                    self.model_status_text.value = f"下载中: {message} ({progress:.1%})"
                    try:
                        self.page.update()
                    except:
                        pass
                
                # 根据模型类型下载
                if isinstance(self.current_model, SenseVoiceModelInfo):
                    # 下载 SenseVoice/Paraformer 单文件模型
                    model_path, tokens_path = self.speech_service.download_sensevoice_model(
                        self.current_model_key,
                        self.current_model,
                        progress_callback
                    )
                    logger.info(f"模型下载完成: {model_path.name}, {tokens_path.name}")
                elif isinstance(self.current_model, WhisperModelInfo):
                    # 下载 Whisper 模型
                    encoder_path, decoder_path, config_path = self.speech_service.download_model(
                        self.current_model_key,
                        self.current_model,
                        progress_callback
                    )
                    logger.info(f"模型下载完成: {encoder_path.name}, {decoder_path.name}, {config_path.name}")
                
                self.model_status_text.value = "下载完成"
                self._init_model_status()
                
                # 如果启用自动加载，立即加载模型
                if self.auto_load_model:
                    self._auto_load_thread()
                
            except Exception as ex:
                self.model_status_text.value = f"下载失败: {ex}"
                self.model_status_text.color = ft.Colors.ERROR
                self.model_download_btn.disabled = False
            finally:
                self.model_loading = False
                try:
                    self.page.update()
                except:
                    pass
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def _on_load_model(self, e: ft.ControlEvent) -> None:
        """加载模型。"""
        if self.model_loading:
            return
        
        self.model_loading = True
        self.model_load_btn.disabled = True
        self.model_status_text.value = "正在加载模型..."
        self.page.update()
        
        def load_thread():
            try:
                model_dir = self.speech_service.get_model_dir(self.current_model_key)
                
                if isinstance(self.current_model, SenseVoiceModelInfo):
                    # 加载 SenseVoice/Paraformer 单文件模型
                    model_path = model_dir / self.current_model.model_filename
                    tokens_path = model_dir / self.current_model.tokens_filename
                    
                    self.speech_service.load_sensevoice_model(
                        model_path=model_path,
                        tokens_path=tokens_path,
                        use_gpu=False,  # 默认使用 CPU
                        language="auto",
                    )
                elif isinstance(self.current_model, WhisperModelInfo):
                    # 加载 Whisper 模型
                    encoder_path = model_dir / self.current_model.encoder_filename
                    decoder_path = model_dir / self.current_model.decoder_filename
                    config_path = model_dir / self.current_model.config_filename
                    
                    self.speech_service.load_model(
                        encoder_path,
                        decoder_path,
                        config_path,
                        use_gpu=False,  # 默认使用 CPU
                        language="auto",
                    )
                
                self.model_loaded = True
                self._init_model_status()
                
            except Exception as ex:
                self.model_status_text.value = f"加载失败: {ex}"
                self.model_status_text.color = ft.Colors.ERROR
                self.model_load_btn.disabled = False
            finally:
                self.model_loading = False
                try:
                    self.page.update()
                except:
                    pass
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _on_unload_model(self, e: ft.ControlEvent) -> None:
        """卸载模型。"""
        self.speech_service.unload_model()
        self.model_loaded = False
        self._init_model_status()
    
    def _update_process_button(self) -> None:
        """更新处理按钮状态。"""
        can_process = (
            len(self.selected_files) > 0 and
            self.model_loaded and
            not self.is_processing
        )
        self.process_btn.content.disabled = not can_process
        try:
            self.page.update()
        except:
            pass
    
    def _on_translate_toggle(self, e) -> None:
        """翻译开关变化事件。"""
        self.enable_translation = e.control.value
        self.target_lang_dropdown.disabled = not self.enable_translation
        self.translate_mode_dropdown.disabled = not self.enable_translation
        self.page.update()
    
    def _on_target_lang_change(self, e) -> None:
        """目标语言变化事件。"""
        self.target_language = e.control.value
    
    async def _translate_segments(
        self, 
        segments: list, 
        target_lang: str,
        progress_callback=None
    ) -> list:
        """翻译识别结果分段（异步）。
        
        Args:
            segments: 识别结果分段列表，每个分段包含 text, start, end
            target_lang: 目标语言代码
            progress_callback: 进度回调函数 (current, total, message)
        
        Returns:
            翻译后的分段列表，每个分段额外包含 translated_text 字段
        """
        import asyncio
        
        total = len(segments)
        translated_segments = []
        
        for i, segment in enumerate(segments):
            text = segment.get("text", "").strip()
            if not text:
                segment["translated_text"] = ""
                translated_segments.append(segment)
                continue
            
            # 调用翻译 API（异步）
            result = await self.translate_service.translate(
                text=text,
                target_lang=target_lang,
                source_lang=""  # 自动检测源语言
            )
            
            if result["code"] == 200:
                segment["translated_text"] = result["data"]["text"]
            else:
                # 翻译失败，保留原文
                logger.warning(f"翻译失败: {result['message']}, 保留原文")
                segment["translated_text"] = text
            
            translated_segments.append(segment)
            
            if progress_callback:
                progress_callback(i + 1, total, f"翻译中... ({i + 1}/{total})")
            
            # 添加小延迟避免请求过于频繁
            if i < total - 1:
                await asyncio.sleep(0.05)
        
        return translated_segments
    
    def _on_output_mode_change(self) -> None:
        """输出模式变化事件。"""
        is_custom = self.output_mode.value == "custom"
        self.output_dir_field.disabled = not is_custom
        self.output_dir_btn.disabled = not is_custom
        self.page.update()
    
    def _select_output_dir(self) -> None:
        """选择输出目录。"""
        self.output_dir_picker.get_directory_path(
            dialog_title="选择输出目录"
        )
    
    def _on_output_dir_selected(self, e: ft.FilePickerResultEvent) -> None:
        """输出目录选择结果处理。"""
        if e.path:
            self.output_dir_field.value = e.path
            self.page.update()
    
    def _generate_ass_style(self, video_width: int, video_height: int, file_path: Path = None) -> str:
        """生成 ASS 字幕样式。
        
        Args:
            video_width: 视频宽度
            video_height: 视频高度
            file_path: 视频文件路径（用于获取单独设置）
        
        Returns:
            ASS 样式字符串
        """
        # 获取该视频的设置
        if file_path:
            settings = self._get_video_settings(file_path)
        else:
            settings = self._get_video_settings(Path(""))  # 使用全局设置
        
        # 获取字体名称 - FFmpeg 需要使用字体的显示名称
        custom_font_path = settings.get("custom_font_path")
        font_display = settings.get("font_display", "")
        font_key = settings.get("font_key", "")
        
        logger.info(f"生成ASS样式 - font_key: {font_key}, font_display: {font_display}, custom_font_path: {custom_font_path}")
        
        if custom_font_path and Path(custom_font_path).exists():
            # 自定义字体：使用字体文件名（不含扩展名）作为字体名
            font_name = Path(custom_font_path).stem
            logger.info(f"使用自定义字体文件: {font_name}")
        else:
            # 系统字体：优先使用 font_key（字体名称），这通常是 FFmpeg 能识别的格式
            if font_key and font_key not in ["System", "system_default"]:
                font_name = font_key
            elif font_display and font_display not in ["系统默认"]:
                font_name = font_display
            else:
                font_name = "Microsoft YaHei"
            logger.info(f"使用系统字体: {font_name}")
        
        font_size = int(settings["font_size"])
        primary_color = settings["font_color"]
        outline_color = settings["outline_color"]
        outline_width = int(settings["outline_width"])
        position = settings["position"]
        margin = int(settings["margin"])
        
        # 字体粗细：normal=0, bold=1 (ASS格式中 Bold 字段)
        font_weight = settings["font_weight"]
        bold = 1 if font_weight == "bold" else 0
        
        # 位置对齐：底部=2, 顶部=8, 居中=5
        alignment_map = {"bottom": 2, "top": 8, "center": 5}
        alignment = alignment_map.get(position, 2)
        
        # MarginV 根据位置设置
        margin_v = margin
        
        style = f"""[Script Info]
Title: Auto Generated Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H00000000,{bold},0,0,0,100,100,0,0,1,{outline_width},0,{alignment},10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        return style
    
    def _segments_to_ass_events(self, segments: List[Dict[str, Any]], max_chars_per_line: int = 30) -> str:
        """将分段结果转换为 ASS 事件。
        
        Args:
            segments: 分段结果
            max_chars_per_line: 每行最大字符数（用于自动换行）
        
        Returns:
            ASS 事件字符串
        """
        events = []
        
        # 获取翻译模式
        translate_mode = self.translate_mode_dropdown.value if self.enable_translation else "replace"
        
        for segment in segments:
            text = segment['text'].strip()
            if not text:
                continue
            
            start = segment['start']
            end = segment['end']
            
            # 格式化时间
            start_str = self._format_ass_time(start)
            end_str = self._format_ass_time(end)
            
            # 获取翻译文本
            translated_text = segment.get('translated_text', '').strip()
            
            # 根据翻译模式生成字幕文本
            if self.enable_translation and translated_text:
                if translate_mode == "replace":
                    # 替换原文：只显示翻译
                    display_text = translated_text
                elif translate_mode == "bilingual":
                    # 双语字幕（原文在上，译文在下）
                    wrapped_original = self._wrap_text(text, max_chars_per_line)
                    wrapped_translated = self._wrap_text(translated_text, max_chars_per_line)
                    display_text = f"{wrapped_original}\\N{wrapped_translated}"
                elif translate_mode == "bilingual_top":
                    # 双语字幕（译文在上，原文在下）
                    wrapped_original = self._wrap_text(text, max_chars_per_line)
                    wrapped_translated = self._wrap_text(translated_text, max_chars_per_line)
                    display_text = f"{wrapped_translated}\\N{wrapped_original}"
                else:
                    display_text = self._wrap_text(text, max_chars_per_line)
            else:
                # 无翻译，使用原文
                display_text = self._wrap_text(text, max_chars_per_line)
            
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{display_text}")
        
        return "\n".join(events)
    
    def _format_ass_time(self, seconds: float) -> str:
        """格式化 ASS 时间戳。"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
    
    def _wrap_text(self, text: str, max_chars: int) -> str:
        """自动换行文本。
        
        Args:
            text: 原始文本
            max_chars: 每行最大字符数
        
        Returns:
            使用 \\N 换行的文本
        """
        if len(text) <= max_chars:
            return text
        
        lines = []
        current_line = ""
        
        for char in text:
            current_line += char
            if len(current_line) >= max_chars:
                lines.append(current_line)
                current_line = ""
        
        if current_line:
            lines.append(current_line)
        
        return "\\N".join(lines)
    
    def _start_processing(self) -> None:
        """开始处理。"""
        if self.is_processing or not self.selected_files:
            return
        
        if not self.model_loaded:
            self._show_snackbar("请先加载模型")
            return
        
        # 检查输出目录
        output_dir = None
        if self.output_mode.value == "custom":
            if not self.output_dir_field.value:
                self._show_snackbar("请选择输出目录")
                return
            output_dir = Path(self.output_dir_field.value)
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
        
        self.is_processing = True
        self.process_btn.content.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.page.update()
        
        def process_task():
            try:
                total = len(self.selected_files)
                
                for idx, file_path in enumerate(self.selected_files):
                    self.progress_text.value = f"处理中: {file_path.name} ({idx + 1}/{total})"
                    self.progress_bar.value = idx / total
                    self.page.update()
                    
                    try:
                        # 步骤1：提取音频
                        self.progress_text.value = f"[{idx + 1}/{total}] 提取音频..."
                        self.page.update()
                        
                        temp_audio = Path(tempfile.gettempdir()) / f"temp_audio_{file_path.stem}.wav"
                        self._extract_audio(file_path, temp_audio)
                        
                        # 步骤1.5：人声分离（如果启用）
                        audio_for_recognition = temp_audio
                        if self.use_vocal_separation and self.vocal_loaded:
                            self.progress_text.value = f"[{idx + 1}/{total}] 人声分离..."
                            self.page.update()
                            
                            try:
                                # 创建临时目录存放分离结果
                                vocal_temp_dir = self.config_service.get_temp_dir() / "video_subtitle_vocals" / f"{file_path.stem}_{idx}"
                                vocal_temp_dir.mkdir(parents=True, exist_ok=True)
                                
                                # 执行人声分离
                                vocals_path, _ = self.vocal_service.separate(
                                    temp_audio,
                                    vocal_temp_dir,
                                    output_format='wav'
                                )
                                
                                audio_for_recognition = vocals_path
                                logger.info(f"人声分离完成: {temp_audio} -> {vocals_path}")
                            except Exception as e:
                                logger.warning(f"人声分离失败，使用原始音频: {e}")
                                audio_for_recognition = temp_audio
                        
                        # 步骤2：语音识别
                        self.progress_text.value = f"[{idx + 1}/{total}] 语音识别中..."
                        self.page.update()
                        
                        def recognition_progress(message: str, progress: float):
                            self.progress_text.value = f"[{idx + 1}/{total}] {message}"
                            self.progress_bar.value = (idx + progress * 0.5) / total
                            try:
                                self.page.update()
                            except:
                                pass
                        
                        segments = self.speech_service.recognize_with_timestamps(
                            audio_for_recognition,
                            progress_callback=recognition_progress
                        )
                        
                        if not segments:
                            logger.error(f"语音识别失败: {file_path}")
                            continue
                        
                        # 步骤3：获取视频信息
                        video_info = self.ffmpeg_service.safe_probe(str(file_path))
                        if not video_info:
                            logger.error(f"无法获取视频信息: {file_path}")
                            continue
                        
                        video_stream = next(
                            (s for s in video_info.get('streams', []) if s.get('codec_type') == 'video'),
                            None
                        )
                        if not video_stream:
                            logger.error(f"未找到视频流: {file_path}")
                            continue
                        
                        video_width = video_stream.get('width', 1920)
                        video_height = video_stream.get('height', 1080)
                        
                        # 步骤3.5：如果启用翻译，进行翻译
                        if self.enable_translation:
                            self.progress_text.value = f"[{idx + 1}/{total}] 翻译字幕..."
                            self.page.update()
                            
                            import asyncio
                            
                            def translate_progress(current, total_items, msg):
                                self.progress_text.value = f"[{idx + 1}/{total}] {msg}"
                                self.page.update()
                            
                            # 异步翻译
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                segments = loop.run_until_complete(
                                    self._translate_segments(
                                        segments, 
                                        self.target_language,
                                        translate_progress
                                    )
                                )
                            finally:
                                loop.close()
                        
                        # 获取该视频的设置
                        video_settings = self._get_video_settings(file_path)
                        
                        # 计算每行最大字符数
                        font_size = int(video_settings["font_size"])
                        max_width_pct = int(video_settings["max_width"])
                        estimated_char_width = font_size * 0.6  # 估算字符宽度
                        max_line_width = video_width * max_width_pct / 100
                        max_chars_per_line = int(max_line_width / estimated_char_width)
                        max_chars_per_line = max(10, min(max_chars_per_line, 50))  # 限制范围
                        
                        # 步骤4：生成 ASS 字幕
                        self.progress_text.value = f"[{idx + 1}/{total}] 生成字幕..."
                        self.page.update()
                        
                        ass_style = self._generate_ass_style(video_width, video_height, file_path)
                        ass_events = self._segments_to_ass_events(segments, max_chars_per_line)
                        ass_content = ass_style + ass_events
                        
                        temp_ass = Path(tempfile.gettempdir()) / f"temp_subtitle_{file_path.stem}.ass"
                        with open(temp_ass, 'w', encoding='utf-8') as f:
                            f.write(ass_content)
                        
                        # 步骤5：烧录字幕到视频
                        self.progress_text.value = f"[{idx + 1}/{total}] 烧录字幕..."
                        self.progress_bar.value = (idx + 0.7) / total
                        self.page.update()
                        
                        if output_dir:
                            output_path = output_dir / f"{file_path.stem}_subtitled.mp4"
                        else:
                            output_path = file_path.parent / f"{file_path.stem}_subtitled.mp4"
                        
                        # 获取字体目录（如果使用外部字体）
                        font_dir = None
                        custom_font_path = video_settings.get("custom_font_path")
                        if custom_font_path and Path(custom_font_path).exists():
                            font_dir = str(Path(custom_font_path).parent)
                        
                        self._burn_subtitles(file_path, temp_ass, output_path, font_dir)
                        
                        # 清理临时文件
                        try:
                            temp_audio.unlink()
                            temp_ass.unlink()
                        except:
                            pass
                        
                        logger.info(f"处理完成: {output_path}")
                        
                    except Exception as ex:
                        logger.error(f"处理文件失败 {file_path}: {ex}", exc_info=True)
                        continue
                
                self.progress_text.value = f"处理完成，共处理 {total} 个文件"
                self.progress_bar.value = 1.0
                self.page.update()
                
            except Exception as e:
                logger.error(f"处理失败: {e}", exc_info=True)
                self.progress_text.value = f"处理失败: {str(e)}"
                self.page.update()
            finally:
                self.is_processing = False
                self.process_btn.content.disabled = False
                self._update_process_button()
                self.page.update()
        
        threading.Thread(target=process_task, daemon=True).start()
    
    def _extract_audio(self, video_path: Path, audio_path: Path) -> None:
        """从视频中提取音频。"""
        import ffmpeg
        
        ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
        
        stream = ffmpeg.input(str(video_path))
        stream = ffmpeg.output(stream, str(audio_path), acodec='pcm_s16le', ar='16000', ac=1)
        stream = stream.global_args('-hide_banner', '-loglevel', 'error')
        
        ffmpeg.run(stream, cmd=ffmpeg_path, overwrite_output=True)
    
    def _burn_subtitles(self, video_path: Path, ass_path: Path, output_path: Path, font_dir: str = None) -> None:
        """将字幕烧录到视频中。
        
        Args:
            video_path: 输入视频路径
            ass_path: ASS 字幕文件路径
            output_path: 输出视频路径
            font_dir: 字体目录（用于外部字体）
        """
        import ffmpeg
        
        ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
        
        # 使用 ass 滤镜烧录字幕
        # 注意：Windows 路径需要转义
        ass_path_escaped = str(ass_path).replace('\\', '/').replace(':', '\\:')
        
        # 构建 ass 滤镜参数
        if font_dir:
            # 指定字体目录，让 FFmpeg 能找到外部字体
            font_dir_escaped = font_dir.replace('\\', '/').replace(':', '\\:')
            vf_filter = f"ass='{ass_path_escaped}':fontsdir='{font_dir_escaped}'"
            logger.info(f"使用字体目录: {font_dir}")
        else:
            vf_filter = f"ass='{ass_path_escaped}'"
        
        stream = ffmpeg.input(str(video_path))
        stream = ffmpeg.output(
            stream,
            str(output_path),
            vf=vf_filter,
            acodec='copy',
            vcodec='libx264',
            preset='medium',
            crf=23,
        )
        stream = stream.global_args('-hide_banner', '-loglevel', 'error')
        
        ffmpeg.run(stream, cmd=ffmpeg_path, overwrite_output=True)
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()
    
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
            self._show_snackbar(f"已添加 {added_count} 个文件")
        elif skipped_count > 0:
            snackbar = ft.SnackBar(content=ft.Text("视频字幕不支持该格式"), bgcolor=ft.Colors.ORANGE)
            self.page.overlay.append(snackbar)
            snackbar.open = True
        self.page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
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
