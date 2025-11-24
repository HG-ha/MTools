# -*- coding: utf-8 -*-
"""视频压缩视图模块。

提供视频压缩功能的用户界面。
"""

import re
import threading
from pathlib import Path
from typing import Callable, List, Optional

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
from services import ConfigService, FFmpegService
from utils import format_file_size
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoCompressView(ft.Container):
    """视频压缩视图类。
    
    提供视频压缩功能，包括：
    - 单文件和批量压缩
    - 恒定速率因子（CRF）调整
    - 分辨率缩放
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频压缩视图。
        
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
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            # 显示 FFmpeg 安装视图时，移除自己的 padding（避免双重 padding）
            # FFmpegInstallView 内部已经管理了 padding
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self.page,
                self.ffmpeg_service,
                on_back=self._on_back_click
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
                ft.Text("视频压缩", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        file_select_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("文件选择", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Container(expand=True),
                            ft.ElevatedButton(
                                "选择文件",
                                icon=ft.Icons.FILE_UPLOAD,
                                on_click=self._on_select_files,
                                height=36,
                            ),
                            ft.ElevatedButton(
                                "选择文件夹",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=self._on_select_folder,
                                height=36,
                            ),
                            ft.OutlinedButton(
                                "清空列表",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=self._on_clear_files,
                                height=36,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=TEXT_SECONDARY),
                                ft.Text(
                                    "支持格式: MP4, MKV, MOV, AVI, WMV, FLV, WebM, M4V, 3GP, TS, M2TS, F4V 等",
                                    size=11,
                                    color=TEXT_SECONDARY,
                                ),
                            ],
                            spacing=6,
                        ),
                        margin=ft.margin.only(bottom=PADDING_SMALL),
                    ),
                    ft.Container(
                        content=self.file_list_view,
                        height=280,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_SMALL,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.PRIMARY),
        )
        
        # 模式切换
        self.mode_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="normal", label="常规模式"),
                    ft.Radio(value="advanced", label="高级模式"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="normal",
            on_change=self._on_mode_change,
        )
        
        # CRF (质量) 控制 - 共享
        self.crf_slider = ft.Slider(
            min=18,
            max=30,
            value=23,
            divisions=12,
            label="CRF: {value}",
            on_change=self._on_crf_change,
        )
        self.crf_text = ft.Text("质量 (CRF): 23 (数值越小，质量越好)", size=14)
        
        # --- 常规模式选项 ---
        self.resolution_dropdown = ft.Dropdown(
            label="分辨率缩放",
            options=[
                ft.dropdown.Option("original", "保持原始分辨率"),
                ft.dropdown.Option("4k", "3840x2160 (4K UHD)"),
                ft.dropdown.Option("2k", "2560x1440 (2K QHD)"),
                ft.dropdown.Option("1080p", "1920x1080 (1080p FHD)"),
                ft.dropdown.Option("720p", "1280x720 (720p HD)"),
                ft.dropdown.Option("480p", "854x480 (480p SD)"),
                ft.dropdown.Option("360p", "640x360 (360p)"),
                ft.dropdown.Option("custom", "自定义分辨率"),
            ],
            value="original",
            width=250,
            on_change=self._on_resolution_change,
        )
        
        # 自定义分辨率输入
        self.custom_resolution_container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.TextField(
                        label="宽度",
                        value="1920",
                        width=100,
                        hint_text="px",
                    ),
                    ft.Text("x", size=16, color=TEXT_SECONDARY),
                    ft.TextField(
                        label="高度",
                        value="1080",
                        width=100,
                        hint_text="px",
                    ),
                ],
                spacing=PADDING_SMALL,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            visible=False,
        )
        self.custom_width_input = self.custom_resolution_container.content.controls[0]
        self.custom_height_input = self.custom_resolution_container.content.controls[2]
        
        # 常规模式的输出格式选择
        self.normal_output_format_dropdown = ft.Dropdown(
            label="输出格式",
            options=[
                ft.dropdown.Option("same", "保持原格式"),
                ft.dropdown.Option("mp4", "MP4"),
                ft.dropdown.Option("mkv", "MKV"),
                ft.dropdown.Option("webm", "WebM"),
            ],
            value="same",
            width=250,
        )

        self.normal_options_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("常规模式设置", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Row(
                        controls=[
                            self.resolution_dropdown,
                            self.normal_output_format_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    self.custom_resolution_container,
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
            visible=True, # 默认可见
        )

        # 检测GPU编码器并设置默认值（会检查配置开关）
        gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
        default_vcodec = "libx264"
        gpu_available = False
        if gpu_encoder:
            default_vcodec = gpu_encoder
            gpu_available = True
        
        # 构建编码器选项列表
        encoder_options = [
            ft.dropdown.Option("libx264", "H.264 (libx264) - 兼容性好"),
            ft.dropdown.Option("libx265", "H.265/HEVC (libx265) - 压缩率高"),
            ft.dropdown.Option("libvpx-vp9", "VP9 (libvpx-vp9) - WebM标准"),
            ft.dropdown.Option("libaom-av1", "AV1 (libaom-av1) - 最新标准"),
        ]
        
        # 添加GPU编码器选项（如果可用）
        # 检测所有可用的GPU编码器用于显示选项（不受配置开关影响，仅用于显示）
        gpu_info = self.ffmpeg_service.detect_gpu_encoders()
        if gpu_info.get("available"):
            encoders = gpu_info.get("encoders", [])
            if "h264_nvenc" in encoders:
                encoder_options.append(ft.dropdown.Option("h264_nvenc", "H.264 (NVENC) - NVIDIA显卡加速 ⚡"))
            if "hevc_nvenc" in encoders:
                encoder_options.append(ft.dropdown.Option("hevc_nvenc", "H.265 (NVENC) - NVIDIA显卡加速 ⚡"))
            if "h264_amf" in encoders:
                encoder_options.append(ft.dropdown.Option("h264_amf", "H.264 (AMF) - AMD显卡加速 ⚡"))
            if "hevc_amf" in encoders:
                encoder_options.append(ft.dropdown.Option("hevc_amf", "H.265 (AMF) - AMD显卡加速 ⚡"))
            if "av1_amf" in encoders:
                encoder_options.append(ft.dropdown.Option("av1_amf", "AV1 (AMF) - AMD显卡加速 ⚡"))
            if "h264_qsv" in encoders:
                encoder_options.append(ft.dropdown.Option("h264_qsv", "H.264 (QSV) - Intel显卡加速 ⚡"))
            if "hevc_qsv" in encoders:
                encoder_options.append(ft.dropdown.Option("hevc_qsv", "H.265 (QSV) - Intel显卡加速 ⚡"))
        
        # --- 高级模式选项 ---
        self.vcodec_dropdown = ft.Dropdown(
            label="视频编码器",
            options=encoder_options,
            value=default_vcodec,
            on_change=self._on_vcodec_change,
        )
        self.preset_dropdown = ft.Dropdown(
            label="编码预设 (速度)",
            options=[
                ft.dropdown.Option("ultrafast", "最快 (质量最低)"),
                ft.dropdown.Option("superfast", "超快"),
                ft.dropdown.Option("veryfast", "很快"),
                ft.dropdown.Option("faster", "较快"),
                ft.dropdown.Option("fast", "快"),
                ft.dropdown.Option("medium", "中等 (默认)"),
                ft.dropdown.Option("slow", "慢"),
                ft.dropdown.Option("slower", "较慢"),
                ft.dropdown.Option("veryslow", "很慢 (压缩率最高)"),
            ],
            value="medium",
        )
        self.acodec_dropdown = ft.Dropdown(
            label="音频编码器",
            options=[
                ft.dropdown.Option("copy", "直接复制 (推荐)"),
                ft.dropdown.Option("aac", "AAC (通用)"),
                ft.dropdown.Option("mp3", "MP3"),
                ft.dropdown.Option("opus", "Opus"),
            ],
            value="copy",
            on_change=self._on_acodec_change,
        )
        self.audio_bitrate_input = ft.TextField(
            label="音频比特率 (kbps)",
            value="192",
            width=150,
            visible=False, # 默认隐藏
        )
        self.pix_fmt_dropdown = ft.Dropdown(
            label="像素格式",
            options=[
                ft.dropdown.Option("yuv420p", "yuv420p (兼容性最广)"),
                ft.dropdown.Option("yuv422p", "yuv422p"),
                ft.dropdown.Option("yuv444p", "yuv444p"),
                ft.dropdown.Option("yuv420p10le", "yuv420p10le (10位)"),
                ft.dropdown.Option("yuv422p10le", "yuv422p10le (10位)"),
            ],
            value="yuv420p",
        )
        
        # 视频比特率控制
        self.bitrate_mode_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="crf", label="CRF (质量优先)"),
                    ft.Radio(value="vbr", label="VBR (可变比特率)"),
                    ft.Radio(value="cbr", label="CBR (恒定比特率)"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="crf",
            on_change=self._on_bitrate_mode_change,
        )
        
        self.video_bitrate_input = ft.TextField(
            label="视频比特率 (kbps)",
            value="5000",
            width=150,
            visible=False,
            hint_text="如: 5000",
        )
        
        self.max_bitrate_input = ft.TextField(
            label="最大比特率 (kbps)",
            value="8000",
            width=150,
            visible=False,
            hint_text="如: 8000",
        )
        
        # 帧率控制
        self.fps_mode_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="original", label="保持原始帧率"),
                    ft.Radio(value="custom", label="自定义帧率"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="original",
            on_change=self._on_fps_mode_change,
        )
        
        self.fps_input = ft.TextField(
            label="帧率 (fps)",
            value="30",
            width=150,
            visible=False,
            hint_text="如: 30",
        )
        
        # 关键帧间隔
        self.gop_input = ft.TextField(
            label="关键帧间隔 (GOP)",
            value="",
            width=150,
            hint_text="留空为自动",
        )
        
        # 输出格式选择
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            options=[
                ft.dropdown.Option("same", "保持原格式"),
                ft.dropdown.Option("mp4", "MP4 (H.264/H.265)"),
                ft.dropdown.Option("mkv", "MKV (通用容器)"),
                ft.dropdown.Option("webm", "WebM (VP9/AV1)"),
                ft.dropdown.Option("mov", "MOV (QuickTime)"),
                ft.dropdown.Option("avi", "AVI (传统格式)"),
            ],
            value="same",
        )

        # 高级模式分组
        video_settings_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("视频编码设置", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Row(
                        controls=[self.vcodec_dropdown, self.preset_dropdown],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    self.pix_fmt_dropdown,
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )
        
        bitrate_settings_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("比特率控制", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    self.bitrate_mode_radio,
                    ft.Row(
                        controls=[self.video_bitrate_input, self.max_bitrate_input],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )
        
        fps_settings_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("帧率设置", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    self.fps_mode_radio,
                    self.fps_input,
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )
        
        advanced_params_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("高级参数", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Row(
                        controls=[self.gop_input, self.output_format_dropdown],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )
        
        audio_settings_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("音频设置", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Row(
                        controls=[self.acodec_dropdown, self.audio_bitrate_input],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )

        self.advanced_options_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("高级模式设置", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    video_settings_card,
                    bitrate_settings_card,
                    fps_settings_card,
                    advanced_params_card,
                    audio_settings_card,
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
            visible=False, # 默认隐藏
        )

        # GPU加速状态提示
        gpu_status_text = None
        if gpu_available and gpu_encoder:
            gpu_encoder_name = gpu_encoder.replace("_", " ").upper()
            gpu_status_text = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SPEED, size=16, color=ft.Colors.GREEN),
                        ft.Text(
                            f"GPU加速已启用: {gpu_encoder_name}",
                            size=12,
                            color=ft.Colors.GREEN,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=6,
                ),
                margin=ft.margin.only(bottom=PADDING_SMALL),
            )
        
        # 质量设置卡片
        quality_card_controls = [
            ft.Text("质量设置", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ]
        if gpu_status_text:
            quality_card_controls.append(gpu_status_text)
        quality_card_controls.extend([
            self.crf_text,
            self.crf_slider,
        ])
        
        quality_card = ft.Container(
            content=ft.Column(
                controls=quality_card_controls,
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )
        
        # 模式选择卡片
        mode_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("压缩模式", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    self.mode_radio,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )

        compress_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("压缩设置", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    quality_card,
                    mode_card,
                    self.normal_options_container,
                    self.advanced_options_container,
                ],
                spacing=PADDING_MEDIUM,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出选项
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.file_suffix = ft.TextField(
            label="文件后缀",
            value="_compressed",
            disabled=False,
            width=200,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        output_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    self.output_mode_radio,
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.file_suffix,
                                ft.Row(
                                    controls=[self.custom_output_dir, self.browse_output_button],
                                    spacing=PADDING_SMALL,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=PADDING_MEDIUM,
                        ),
                        padding=PADDING_MEDIUM,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_MEDIUM,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=TEXT_SECONDARY)
        
        # 底部按钮
        self.compress_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COMPRESS, size=24),
                        ft.Text("开始压缩", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_compress,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.alignment.center,
        )
        
        # 进度显示容器
        progress_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    self.progress_text,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        self.progress_container = progress_container
        
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                compress_options,
                ft.Container(height=PADDING_MEDIUM),
                output_options,
                ft.Container(height=PADDING_MEDIUM),
                progress_container,
                ft.Container(height=PADDING_SMALL),
                self.compress_button,
                ft.Container(height=PADDING_LARGE),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
        )
        
        self._init_empty_state()

    def _init_empty_state(self) -> None:
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.MOVIE_OUTLINED, size=48, color=TEXT_SECONDARY),
                        ft.Text("未选择文件", color=TEXT_SECONDARY, size=14),
                        ft.Text("点击此处或选择按钮添加视频", color=TEXT_SECONDARY, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=250,  # 固定高度以确保填满显示区域
                alignment=ft.alignment.center,
                on_click=lambda e: self._on_select_files(e),
                ink=True,
                tooltip="点击选择视频文件",
            )
        )

    def _on_select_files(self, e: ft.ControlEvent) -> None:
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                new_files = [Path(f.path) for f in result.files]
                for new_file in new_files:
                    if new_file not in self.selected_files:
                        self.selected_files.append(new_file)
                self._update_file_list()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=[
                "mp4", "mkv", "mov", "avi", "wmv", "flv", "webm", 
                "m4v", "3gp", "ts", "m2ts", "f4v", "asf", "rm", "rmvb"
            ],
            allow_multiple=True,
        )

    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder = Path(result.path)
                extensions = [
                    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
                    ".m4v", ".3gp", ".ts", ".m2ts", ".f4v", ".asf", ".rm", ".rmvb"
                ]
                self.selected_files.clear()
                for ext in extensions:
                    self.selected_files.extend(folder.glob(f"**/*{ext}"))
                    self.selected_files.extend(folder.glob(f"**/*{ext.upper()}"))
                self._update_file_list()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择视频文件夹")

    def _update_file_list(self) -> None:
        self.file_list_view.controls.clear()
        if not self.selected_files:
            self._init_empty_state()
        else:
            for idx, file_path in enumerate(self.selected_files):
                file_size = file_path.stat().st_size
                size_str = format_file_size(file_size)
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.VIDEOCAM, size=20, color=ft.Colors.PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                        ft.Text(f"大小: {size_str}", size=11, color=TEXT_SECONDARY),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="移除",
                                    on_click=lambda e, i=idx: self._on_remove_file(i),
                                ),
                            ],
                            spacing=PADDING_MEDIUM,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_MEDIUM,
                    )
                )
        self.file_list_view.update()

    def _on_acodec_change(self, e: ft.ControlEvent) -> None:
        """音频编码器改变事件。"""
        self.audio_bitrate_input.visible = e.control.value != "copy"
        self.page.update()
    
    def _on_resolution_change(self, e: ft.ControlEvent) -> None:
        """分辨率选择改变事件。"""
        is_custom = e.control.value == "custom"
        self.custom_resolution_container.visible = is_custom
        self.page.update()
    
    def _on_vcodec_change(self, e: ft.ControlEvent) -> None:
        """视频编码器改变事件。"""
        vcodec = e.control.value
        # 某些编码器不支持某些预设或参数，可以在这里调整
        self.page.update()
    
    def _on_bitrate_mode_change(self, e: ft.ControlEvent) -> None:
        """比特率模式改变事件。"""
        mode = e.control.value
        if mode == "crf":
            self.video_bitrate_input.visible = False
            self.max_bitrate_input.visible = False
        elif mode == "vbr":
            self.video_bitrate_input.visible = True
            self.max_bitrate_input.visible = True
        else:  # cbr
            self.video_bitrate_input.visible = True
            self.max_bitrate_input.visible = False
        self.page.update()
    
    def _on_fps_mode_change(self, e: ft.ControlEvent) -> None:
        """帧率模式改变事件。"""
        self.fps_input.visible = e.control.value == "custom"
        self.page.update()

    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        """切换常规/高级模式。"""
        is_normal = e.control.value == "normal"
        self.normal_options_container.visible = is_normal
        self.advanced_options_container.visible = not is_normal
        self.page.update()

    def _on_remove_file(self, index: int) -> None:
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()

    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        self.selected_files.clear()
        self._update_file_list()

    def _on_crf_change(self, e: ft.ControlEvent) -> None:
        crf = int(e.control.value)
        self.crf_text.value = f"质量 (CRF): {crf} (数值越小，质量越好)"
        self.crf_text.update()

    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        mode = e.control.value
        self.file_suffix.disabled = mode != "new"
        self.custom_output_dir.disabled = mode != "custom"
        self.browse_output_button.disabled = mode != "custom"
        self.page.update()

    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_dir.value = result.path
                self.custom_output_dir.update()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")

    def _on_compress(self, e: ft.ControlEvent) -> None:
        if not self.selected_files:
            self._show_message("请先选择要压缩的视频", ft.Colors.ORANGE)
            return

        self.progress_container.visible = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备压缩..."
        self.progress_container.update()
        self.page.update()

        compression_params = {
            "mode": self.mode_radio.value,
            # 常规模式
            "crf": int(self.crf_slider.value),
            "scale": self.resolution_dropdown.value,
            "custom_width": self.custom_width_input.value if self.resolution_dropdown.value == "custom" else None,
            "custom_height": self.custom_height_input.value if self.resolution_dropdown.value == "custom" else None,
            "output_format": self.normal_output_format_dropdown.value if self.mode_radio.value == "normal" else self.output_format_dropdown.value,
            # 高级模式
            "vcodec": self.vcodec_dropdown.value,
            "preset": self.preset_dropdown.value,
            "acodec": self.acodec_dropdown.value,
            "audio_bitrate": f"{self.audio_bitrate_input.value}k" if self.audio_bitrate_input.value else "192k",
            "pix_fmt": self.pix_fmt_dropdown.value,
            "bitrate_mode": self.bitrate_mode_radio.value,
            "video_bitrate": self.video_bitrate_input.value if self.video_bitrate_input.visible else None,
            "max_bitrate": self.max_bitrate_input.value if self.max_bitrate_input.visible else None,
            "fps_mode": self.fps_mode_radio.value,
            "fps": self.fps_input.value if self.fps_input.visible else None,
            "gop": self.gop_input.value if self.gop_input.value else None,
        }
        output_mode = self.output_mode_radio.value

        def compress_task():
            total = len(self.selected_files)
            success_count = 0
            failed_files = []
            
            for i, input_path in enumerate(self.selected_files):
                try:
                    # 确定输出格式
                    output_format = compression_params.get("output_format", "same")
                    if output_mode == "new":
                        suffix = self.file_suffix.value or "_compressed"
                        if output_format == "same":
                            ext = input_path.suffix
                        else:
                            ext = f".{output_format}"
                        output_path = input_path.parent / f"{input_path.stem}{suffix}{ext}"
                    else:
                        output_dir = Path(self.custom_output_dir.value)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        if output_format == "same":
                            output_path = output_dir / input_path.name
                        else:
                            output_path = output_dir / f"{input_path.stem}.{output_format}"
                    
                    def progress_handler(progress, speed, remaining_time):
                        # 计算总体进度
                        overall_progress = (i + progress) / total
                        self.progress_bar.value = overall_progress
                        
                        # 显示详细信息
                        percent = int(progress * 100)
                        self.progress_text.value = (
                            f"正在处理 ({i+1}/{total}): {input_path.name}\n"
                            f"进度: {percent}% | 速度: {speed} | 预计剩余: {remaining_time}"
                        )
                        self.page.update()
                    
                    # 显示开始处理
                    self.progress_text.value = f"开始处理 ({i+1}/{total}): {input_path.name}..."
                    self.page.update()
                    
                    result, message = self.ffmpeg_service.compress_video(
                        input_path, output_path, compression_params, progress_handler
                    )
                    
                    if result:
                        success_count += 1
                    else:
                        failed_files.append(f"{input_path.name}: {message}")
                    
                except Exception as e:
                    failed_files.append(f"{input_path.name}: {str(e)}")

            # 完成后显示结果
            self.progress_bar.visible = False
            self.progress_container.visible = False
            
            if failed_files:
                self.progress_text.value = (
                    f"压缩完成！成功: {success_count}/{total}\n"
                    f"失败: {len(failed_files)} 个文件"
                )
                self._show_message(f"部分文件压缩失败 ({len(failed_files)}个)", ft.Colors.ORANGE)
            else:
                self.progress_text.value = f"压缩完成！成功处理 {total} 个文件。"
                self._show_message("全部压缩完成！", ft.Colors.GREEN)
            
            self.page.update()

        threading.Thread(target=compress_task, daemon=True).start()

    def _on_back_click(self, e: Optional[ft.ControlEvent] = None) -> None:
        """返回按钮点击事件。
        
        Args:
            e: 控件事件对象（可选，因为可能被直接调用）
        """
        if self.on_back:
            self.on_back()

    def _show_message(self, message: str, color: str) -> None:
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()
