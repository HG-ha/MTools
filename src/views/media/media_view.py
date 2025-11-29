# -*- coding: utf-8 -*-
"""媒体处理视图模块。

提供音频和视频处理相关功能的统一用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
)
from services import AudioService, ConfigService, FFmpegService
from views.media.audio_compress_view import AudioCompressView
from views.media.audio_format_view import AudioFormatView
from views.media.audio_speed_view import AudioSpeedView
from views.media.ffmpeg_install_view import FFmpegInstallView
from views.media.video_compress_view import VideoCompressView
from views.media.video_convert_view import VideoConvertView
from views.media.video_extract_audio_view import VideoExtractAudioView
from views.media.video_repair_view import VideoRepairView
from views.media.video_speed_view import VideoSpeedView
from views.media.video_vocal_separation_view import VideoVocalSeparationView
from views.media.video_watermark_view import VideoWatermarkView


class MediaView(ft.Container):
    """媒体处理视图类。
    
    提供音频和视频处理相关功能的统一用户界面，包括：
    - 音频格式转换
    - 音频压缩
    - 人声提取
    - 视频压缩
    - 视频格式转换
    - 视频提取音频
    - 视频倍速调整
    - 视频人声分离
    - 视频添加水印
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化媒体处理视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self._saved_page: ft.Page = page  # 保存页面引用
        self.config_service: ConfigService = config_service if config_service else ConfigService()
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 创建服务
        self.ffmpeg_service: FFmpegService = FFmpegService(self.config_service)
        self.audio_service: AudioService = AudioService(self.ffmpeg_service)
        
        # 创建音频子视图（延迟创建）
        self.audio_format_view: Optional[AudioFormatView] = None
        self.audio_compress_view: Optional[AudioCompressView] = None
        self.audio_speed_view: Optional[AudioSpeedView] = None
        self.vocal_extraction_view = None  # 人声提取视图
        
        # 创建视频子视图（延迟创建）
        self.video_compress_view: Optional[VideoCompressView] = None
        self.video_convert_view: Optional[VideoConvertView] = None
        self.video_extract_audio_view: Optional[VideoExtractAudioView] = None
        self.video_repair_view: Optional[VideoRepairView] = None
        self.video_speed_view: Optional[VideoSpeedView] = None
        self.video_vocal_separation_view: Optional[VideoVocalSeparationView] = None
        self.video_watermark_view: Optional[VideoWatermarkView] = None
        
        # FFmpeg安装视图
        self.ffmpeg_install_view: Optional[FFmpegInstallView] = None
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        # 记录当前子视图的类型（用于销毁）
        self.current_sub_view_type: Optional[str] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _safe_page_update(self) -> None:
        """安全地更新页面。"""
        page = getattr(self, '_saved_page', self.page)
        if page:
            page.update()
    
    def _hide_search_button(self) -> None:
        """隐藏主视图的搜索按钮。"""
        if hasattr(self.page, '_main_view'):
            self.page._main_view.hide_search_button()
    
    def _show_search_button(self) -> None:
        """显示主视图的搜索按钮。"""
        if hasattr(self.page, '_main_view'):
            self.page._main_view.show_search_button()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 所有媒体处理功能卡片
        feature_cards = [
            # 音频处理
            FeatureCard(
                icon=ft.Icons.AUDIO_FILE_ROUNDED,
                title="音频格式转换",
                description="转换音频格式(MP3/WAV/AAC等)",
                on_click=lambda e: self._open_view('audio_format'),
                gradient_colors=("#a8edea", "#fed6e3"),
            ),
            FeatureCard(
                icon=ft.Icons.COMPRESS,
                title="音频压缩",
                description="压缩音频文件大小",
                on_click=lambda e: self._open_view('audio_compress'),
                gradient_colors=("#fbc2eb", "#a6c1ee"),
            ),
            FeatureCard(
                icon=ft.Icons.SPEED,
                title="音频倍速调整",
                description="调整音频播放速度(0.1x-10x)",
                on_click=lambda e: self._open_view('audio_speed'),
                gradient_colors=("#f093fb", "#f5576c"),
            ),
            FeatureCard(
                icon=ft.Icons.MUSIC_NOTE,
                title="人声提取",
                description="AI智能分离人声和伴奏",
                on_click=lambda e: self._open_view('vocal_extraction'),
                gradient_colors=("#ffecd2", "#fcb69f"),
            ),
            # 视频处理
            FeatureCard(
                icon=ft.Icons.COMPRESS,
                title="视频压缩",
                description="减小视频文件大小，支持CRF和分辨率调整",
                on_click=lambda e: self._open_view('video_compress'),
                gradient_colors=("#84fab0", "#8fd3f4"),
            ),
            FeatureCard(
                icon=ft.Icons.VIDEO_FILE_ROUNDED,
                title="视频格式转换",
                description="支持MP4、AVI、MKV等格式互转",
                on_click=lambda e: self._open_view('video_convert'),
                gradient_colors=("#a8edea", "#fed6e3"),
            ),
            FeatureCard(
                icon=ft.Icons.AUDIO_FILE_ROUNDED,
                title="视频提取音频",
                description="从视频中提取音频轨道",
                on_click=lambda e: self._open_view('video_extract_audio'),
                gradient_colors=("#ff9a9e", "#fad0c4"),
            ),
            FeatureCard(
                icon=ft.Icons.SPEED,
                title="视频倍速调整",
                description="调整视频播放速度(0.1x-10x)",
                on_click=lambda e: self._open_view('video_speed'),
                gradient_colors=("#667eea", "#764ba2"),
            ),
            FeatureCard(
                icon=ft.Icons.GRAPHIC_EQ,
                title="视频人声分离",
                description="分离视频中的人声和背景音",
                on_click=lambda e: self._open_view('video_vocal_separation'),
                gradient_colors=("#fbc2eb", "#a6c1ee"),
            ),
            FeatureCard(
                icon=ft.Icons.BRANDING_WATERMARK,
                title="视频添加水印",
                description="为视频添加文字或图片水印",
                on_click=lambda e: self._open_view('video_watermark'),
                gradient_colors=("#ffecd2", "#fcb69f"),
            ),
            FeatureCard(
                icon=ft.Icons.HEALING,
                title="视频修复",
                description="修复损坏、卡顿、无法播放的视频",
                on_click=lambda e: self._open_view('video_repair'),
                gradient_colors=("#fa709a", "#fee140"),
            ),
            # 工具类
            FeatureCard(
                icon=ft.Icons.TERMINAL,
                title="FFmpeg 终端",
                description="配置环境变量并打开命令行",
                on_click=lambda e: self._open_ffmpeg_terminal(),
                gradient_colors=("#4facfe", "#00f2fe"),
            ),
        ]
        
        # 统一展示所有功能卡片
        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=feature_cards,
                    wrap=True,
                    spacing=PADDING_LARGE,
                    run_spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _open_view(self, view_name: str) -> None:
        """打开子视图。
        
        Args:
            view_name: 视图名称
        """
        # 检查FFmpeg是否可用
        is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_available:
            self._show_ffmpeg_install_view()
            return
        
        # 根据视图名称创建或切换到对应的子视图
        if view_name == 'audio_format':
            if not self.audio_format_view:
                self.audio_format_view = AudioFormatView(
                    self.page,
                    self.config_service,
                    self.audio_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_format_view, 'audio_format')
            
        elif view_name == 'audio_compress':
            if not self.audio_compress_view:
                self.audio_compress_view = AudioCompressView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_compress_view, 'audio_compress')
            
        elif view_name == 'audio_speed':
            if not self.audio_speed_view:
                self.audio_speed_view = AudioSpeedView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_speed_view, 'audio_speed')
            
        elif view_name == 'vocal_extraction':
            if not self.vocal_extraction_view:
                from views.media.vocal_extraction_view import VocalExtractionView
                self.vocal_extraction_view = VocalExtractionView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.vocal_extraction_view, 'vocal_extraction')
            
        elif view_name == 'video_compress':
            if not self.video_compress_view:
                self.video_compress_view = VideoCompressView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_compress_view, 'video_compress')
            
        elif view_name == 'video_convert':
            if not self.video_convert_view:
                self.video_convert_view = VideoConvertView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_convert_view, 'video_convert')
            
        elif view_name == 'video_extract_audio':
            if not self.video_extract_audio_view:
                self.video_extract_audio_view = VideoExtractAudioView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_extract_audio_view, 'video_extract_audio')
            
        elif view_name == 'video_speed':
            if not self.video_speed_view:
                self.video_speed_view = VideoSpeedView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_speed_view, 'video_speed')
            
        elif view_name == 'video_vocal_separation':
            if not self.video_vocal_separation_view:
                self.video_vocal_separation_view = VideoVocalSeparationView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_vocal_separation_view, 'video_vocal_separation')
            
        elif view_name == 'video_watermark':
            if not self.video_watermark_view:
                self.video_watermark_view = VideoWatermarkView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_watermark_view, 'video_watermark')
            
        elif view_name == 'video_repair':
            if not self.video_repair_view:
                self.video_repair_view = VideoRepairView(
                    self.page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_repair_view, 'video_repair')
    
    def _show_ffmpeg_install_view(self) -> None:
        """显示FFmpeg安装提示视图。"""
        if not self.ffmpeg_install_view:
            self.ffmpeg_install_view = FFmpegInstallView(
                self.page,
                self.ffmpeg_service,
                on_back=self._back_to_main,
                on_installed=self._on_ffmpeg_installed
            )
        self._switch_to_sub_view(self.ffmpeg_install_view, 'ffmpeg_install')
    
    def _on_ffmpeg_installed(self, e=None) -> None:
        """FFmpeg安装完成回调。
        
        Args:
            e: 事件对象（可选）
        """
        # 返回主视图
        self._back_to_main()
    
    def _switch_to_sub_view(self, view: ft.Container, view_type: str) -> None:
        """切换到子视图。
        
        Args:
            view: 子视图容器
            view_type: 视图类型
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 记录当前子视图
        self.current_sub_view = view
        self.current_sub_view_type = view_type
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 切换视图
        self.parent_container.content = view
        self._safe_page_update()
    
    def _back_to_main(self, e=None) -> None:
        """返回主视图。
        
        Args:
            e: 事件对象（可选）
        """
        if not self.parent_container:
            return
        
        # 销毁当前子视图（而不是保留）
        if self.current_sub_view_type:
            view_map = {
                "audio_format": "audio_format_view",
                "audio_compress": "audio_compress_view",
                "audio_speed": "audio_speed_view",
                "vocal_extraction": "vocal_extraction_view",
                "video_compress": "video_compress_view",
                "video_convert": "video_convert_view",
                "video_extract_audio": "video_extract_audio_view",
                "video_repair": "video_repair_view",
                "video_speed": "video_speed_view",
                "video_vocal_separation": "video_vocal_separation_view",
                "video_watermark": "video_watermark_view",
                "ffmpeg_install": "ffmpeg_install_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                setattr(self, view_attr, None)
        
        # 清空当前子视图记录
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        # 切换回主视图
        self.parent_container.content = self
        self._safe_page_update()
        
        # 显示搜索按钮（在页面更新之后）
        self._show_search_button()
    
    def _open_ffmpeg_terminal(self) -> None:
        """打开FFmpeg终端。"""
        import os
        import subprocess
        from pathlib import Path
        
        try:
            # 检查FFmpeg是否可用
            is_available, location = self.ffmpeg_service.is_ffmpeg_available()
            if not is_available:
                # 如果FFmpeg不可用，显示安装视图
                self._show_ffmpeg_install_view()
                return
            
            # 获取FFmpeg路径
            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
            
            # 准备环境变量
            env = os.environ.copy()
            
            # 如果使用本地FFmpeg，需要添加到PATH
            if self.ffmpeg_service.ffmpeg_exe.exists():
                ffmpeg_bin_dir = str(self.ffmpeg_service.ffmpeg_bin)
                # 将FFmpeg bin目录添加到PATH的最前面
                if 'PATH' in env:
                    env['PATH'] = f"{ffmpeg_bin_dir};{env['PATH']}"
                else:
                    env['PATH'] = ffmpeg_bin_dir
            
            # 获取用户主目录作为工作目录
            work_dir = str(Path.home())
            
            # 创建启动脚本
            startup_script = f"""@echo off
title FFmpeg Terminal
echo ========================================
echo FFmpeg Terminal - Ready
echo ========================================
echo.
echo FFmpeg: {ffmpeg_path}
echo Working Directory: {work_dir}
echo.
echo You can now use ffmpeg and ffprobe commands.
echo Type 'ffmpeg -version' to verify.
echo.
cd /d "{work_dir}"
"""
            
            # 保存临时启动脚本
            temp_script = Path(self.config_service.get_temp_dir()) / "ffmpeg_terminal_startup.bat"
            temp_script.write_text(startup_script, encoding='utf-8')
            
            # 打开CMD并执行启动脚本
            subprocess.Popen(
                ['cmd.exe', '/K', str(temp_script)],
                env=env,
                cwd=work_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # 显示成功消息
            snackbar = ft.SnackBar(
                content=ft.Text("FFmpeg 终端已打开！"),
                bgcolor=ft.Colors.GREEN,
                duration=2000,
            )
            self.page.overlay.append(snackbar)
            snackbar.open = True
            self.page.update()
            
        except Exception as e:
            # 显示错误消息
            snackbar = ft.SnackBar(
                content=ft.Text(f"打开终端失败: {str(e)}"),
                bgcolor=ft.Colors.ERROR,
                duration=3000,
            )
            self.page.overlay.append(snackbar)
            snackbar.open = True
            self.page.update()
    
    def restore_state(self) -> bool:
        """恢复视图状态。
        
        Returns:
            是否成功恢复了子视图
        """
        if self.current_sub_view and self.current_sub_view_type:
            # 恢复到之前的子视图
            self._switch_to_sub_view(self.current_sub_view, self.current_sub_view_type)
            return True
        return False
