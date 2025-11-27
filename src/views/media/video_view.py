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
from views.media.ffmpeg_install_view import FFmpegInstallView
from views.media.video_compress_view import VideoCompressView
from views.media.video_convert_view import VideoConvertView
from views.media.video_extract_audio_view import VideoExtractAudioView
from views.media.video_vocal_separation_view import VideoVocalSeparationView
from views.media.video_watermark_view import VideoWatermarkView


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
        parent_container: Optional[ft.Container] = None,
    ) -> None:
        """初始化视频处理视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.parent_container: Optional[ft.Container] = parent_container
        
        self.expand: bool = True
        
        # 子视图
        self.compress_view: Optional[VideoCompressView] = None
        self.convert_view: Optional[VideoConvertView] = None
        self.extract_audio_view: Optional[VideoExtractAudioView] = None
        self.vocal_separation_view: Optional[VideoVocalSeparationView] = None
        self.watermark_view: Optional[VideoWatermarkView] = None
        self.ffmpeg_install_view: Optional[FFmpegInstallView] = None
        
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
                    icon=ft.Icons.GRAPHIC_EQ,
                    title="人声分离",
                    description="分离视频中的人声和背景音",
                    on_click=lambda e: self._open_view('vocal_separation'),
                    gradient_colors=("#fbc2eb", "#a6c1ee"),
                ),
                FeatureCard(
                    icon=ft.Icons.BRANDING_WATERMARK,
                    title="添加水印",
                    description="为视频添加文字或图片水印",
                    on_click=lambda e: self._open_view('watermark'),
                    gradient_colors=("#ffecd2", "#fcb69f"),
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
                left=PADDING_MEDIUM,
                right=PADDING_MEDIUM,
                top=PADDING_MEDIUM,
                bottom=PADDING_MEDIUM,
            ),
        )

        self.parent_container = ft.Container(content=self.main_view, expand=True)
        self.content = self.parent_container

    def _open_view(self, view_name: str) -> None:
        """打开子视图。"""
        if view_name == 'compress':
            def open_func():
                self.compress_view = VideoCompressView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
                self.parent_container.content = self.compress_view
                self.page.update()
            self._check_ffmpeg_and_open("视频压缩", open_func)
            
        elif view_name == 'convert':
            def open_func():
                self.convert_view = VideoConvertView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
                self.parent_container.content = self.convert_view
                self.page.update()
            self._check_ffmpeg_and_open("视频格式转换", open_func)
            
        elif view_name == 'extract_audio':
            def open_func():
                self.extract_audio_view = VideoExtractAudioView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
                self.parent_container.content = self.extract_audio_view
                self.page.update()
            self._check_ffmpeg_and_open("提取音频", open_func)
            
        elif view_name == 'vocal_separation':
            def open_func():
                self.vocal_separation_view = VideoVocalSeparationView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
                self.parent_container.content = self.vocal_separation_view
                self.page.update()
            self._check_ffmpeg_and_open("视频人声分离", open_func)
            
        elif view_name == 'watermark':
            def open_func():
                self.watermark_view = VideoWatermarkView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
                self.parent_container.content = self.watermark_view
                self.page.update()
            self._check_ffmpeg_and_open("视频添加水印", open_func)
    
    def _check_ffmpeg_and_open(self, tool_name: str, open_func: Callable) -> None:
        """检查FFmpeg并打开工具（通用方法）。
        
        Args:
            tool_name: 工具名称
            open_func: 打开工具的函数
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 检查FFmpeg是否可用
        is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        
        if not is_available:
            # FFmpeg未安装，显示安装视图
            self._show_ffmpeg_install_view(tool_name)
        else:
            # FFmpeg已安装，执行打开函数
            open_func()
    
    def _show_ffmpeg_install_view(self, tool_name: str) -> None:
        """显示FFmpeg安装视图。
        
        Args:
            tool_name: 工具名称
        """
        if not self.parent_container:
            return
        
        # 创建FFmpeg安装视图
        self.ffmpeg_install_view = FFmpegInstallView(
            self.page,
            self.ffmpeg_service,
            on_installed=lambda: self._on_ffmpeg_installed(),
            on_back=self._back_to_main,
            tool_name=tool_name
        )
        
        # 切换到安装视图
        self.parent_container.content = self.ffmpeg_install_view
        self.page.update()
    
    def _on_ffmpeg_installed(self) -> None:
        """FFmpeg安装完成回调。"""
        # 返回主界面
        self._back_to_main()

    def _back_to_main(self, e: ft.ControlEvent = None) -> None:
        """返回主视图。
        
        Args:
            e: 控件事件对象（可选）
        """
        self.parent_container.content = self.main_view
        self.page.update()