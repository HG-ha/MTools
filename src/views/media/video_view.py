# -*- coding: utf-8 -*-
"""视频处理视图模块。

提供视频格式转换、编辑、批量处理等功能的用户界面。
"""

from typing import Callable, Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import ConfigService, FFmpegService
from views.media.video_compress_view import VideoCompressView
from views.media.video_convert_view import VideoConvertView
from views.media.video_extract_audio_view import VideoExtractAudioView


class VideoView(ft.Container):
    """视频处理视图类。
    
    提供视频处理相关功能的用户界面，包括：
    - 视频压缩
    - 视频格式转换
    - 视频剪辑
    - 批量处理
    - 视频参数调整
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
    ) -> None:
        """初始化视频处理视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        
        self.expand: bool = True
        
        # 子视图
        self.compress_view: Optional[VideoCompressView] = None
        self.convert_view: Optional[VideoConvertView] = None
        self.extract_audio_view: Optional[VideoExtractAudioView] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        self.feature_cards = ft.Row(
            controls=[
                FeatureCard(
                    icon=ft.Icons.COMPRESS,
                    title="视频压缩",
                    description="减小视频文件大小，支持CRF和分辨率调整",
                    on_click=lambda e: self._open_view('compress'),
                    gradient_colors=("#84fab0", "#8fd3f4"),
                ),
                FeatureCard(
                    icon=ft.Icons.VIDEO_FILE_ROUNDED,
                    title="格式转换",
                    description="支持MP4、AVI、MKV等格式互转",
                    on_click=lambda e: self._open_view('convert'),
                    gradient_colors=("#a8edea", "#fed6e3"),
                ),
                FeatureCard(
                    icon=ft.Icons.AUDIO_FILE_ROUNDED,
                    title="提取音频",
                    description="从视频中提取音频轨道",
                    on_click=lambda e: self._open_view('extract_audio'),
                    gradient_colors=("#ff9a9e", "#fad0c4"),
                ),
                FeatureCard(
                    icon=ft.Icons.VIDEO_CALL_ROUNDED,
                    title="视频剪辑",
                    description="裁剪、合并、添加水印 (开发中)",
                    gradient_colors=("#fbc2eb", "#a6c1ee"),
                ),
            ],
            wrap=True,
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        self.main_view = ft.Container(
            content=ft.Column(
                controls=[self.feature_cards],
                spacing=PADDING_MEDIUM,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.padding.only(
                left=PADDING_LARGE,
                right=PADDING_LARGE,
                top=PADDING_XLARGE,
                bottom=PADDING_XLARGE,
            ),
        )

        self.parent_container = ft.Container(content=self.main_view, expand=True)
        self.content = self.parent_container

    def _open_view(self, view_name: str) -> None:
        """打开子视图。"""
        if view_name == 'compress':
            self.compress_view = VideoCompressView(
                self.page,
                self.config_service,
                self.ffmpeg_service,
                on_back=self._back_to_main
            )
            self.parent_container.content = self.compress_view
            self.page.update()
        elif view_name == 'convert':
            self.convert_view = VideoConvertView(
                self.page,
                self.config_service,
                self.ffmpeg_service,
                on_back=self._back_to_main
            )
            self.parent_container.content = self.convert_view
            self.page.update()
        elif view_name == 'extract_audio':
            self.extract_audio_view = VideoExtractAudioView(
                self.page,
                self.config_service,
                self.ffmpeg_service,
                on_back=self._back_to_main
            )
            self.parent_container.content = self.extract_audio_view
            self.page.update()

    def _back_to_main(self) -> None:
        """返回主视图。"""
        self.parent_container.content = self.main_view
        self.page.update()