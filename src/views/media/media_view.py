# -*- coding: utf-8 -*-
"""媒体处理视图模块。

提供音频和视频处理相关功能的统一用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from utils.logger import logger
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
)
from services import AudioService, ConfigService, FFmpegService
from views.media.audio_compress_view import AudioCompressView
from views.media.audio_format_view import AudioFormatView
from views.media.audio_speed_view import AudioSpeedView
from views.media.audio_to_text_view import AudioToTextView
from views.media.ffmpeg_install_view import FFmpegInstallView
from views.media.video_compress_view import VideoCompressView
from views.media.video_convert_view import VideoConvertView
from views.media.video_enhance_view import VideoEnhanceView
from views.media.video_extract_audio_view import VideoExtractAudioView
from views.media.video_interpolation_view import VideoInterpolationView
from views.media.video_repair_view import VideoRepairView
from views.media.video_speed_view import VideoSpeedView
from views.media.video_vocal_separation_view import VideoVocalSeparationView
from views.media.video_watermark_view import VideoWatermarkView
from views.media.subtitle_remove_view import SubtitleRemoveView
from views.media.video_subtitle_view import VideoSubtitleView
from views.media.screen_record_view import ScreenRecordView


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
        self.audio_to_text_view: Optional[AudioToTextView] = None  # 音视频转文字视图
        
        # 创建视频子视图（延迟创建）
        self.video_compress_view: Optional[VideoCompressView] = None
        self.video_convert_view: Optional[VideoConvertView] = None
        self.video_enhance_view: Optional[VideoEnhanceView] = None
        self.video_interpolation_view: Optional[VideoInterpolationView] = None
        self.video_extract_audio_view: Optional[VideoExtractAudioView] = None
        self.video_repair_view: Optional[VideoRepairView] = None
        self.video_speed_view: Optional[VideoSpeedView] = None
        self.video_vocal_separation_view: Optional[VideoVocalSeparationView] = None
        self.video_watermark_view: Optional[VideoWatermarkView] = None
        self.subtitle_remove_view: Optional[SubtitleRemoveView] = None
        self.video_subtitle_view: Optional[VideoSubtitleView] = None
        self.screen_record_view: Optional[ScreenRecordView] = None
        
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
    
    def _on_pin_change(self, tool_id: str, is_pinned: bool) -> None:
        """处理置顶状态变化。"""
        if is_pinned:
            self.config_service.pin_tool(tool_id)
            self._show_snackbar("已置顶到推荐")
        else:
            self.config_service.unpin_tool(tool_id)
            self._show_snackbar("已取消置顶")
        
        # 刷新推荐视图
        if hasattr(self.page, '_main_view') and self.page._main_view.recommendations_view:
            self.page._main_view.recommendations_view.refresh()
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(content=ft.Text(message), duration=2000)
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()
    
    def _create_card(self, icon, title, description, gradient_colors, on_click, tool_id) -> FeatureCard:
        """创建带置顶功能的卡片。"""
        return FeatureCard(
            icon=icon,
            title=title,
            description=description,
            gradient_colors=gradient_colors,
            on_click=on_click,
            tool_id=tool_id,
            is_pinned=self.config_service.is_tool_pinned(tool_id),
            on_pin_change=self._on_pin_change,
        )
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 所有媒体处理功能卡片
        feature_cards = [
            # 音频处理
            self._create_card(
                icon=ft.Icons.AUDIO_FILE_ROUNDED,
                title="音频格式转换",
                description="转换音频格式(MP3/WAV/AAC等)",
                on_click=lambda e: self._open_view('audio_format'),
                gradient_colors=("#a8edea", "#fed6e3"),
                tool_id="audio.format",
            ),
            self._create_card(
                icon=ft.Icons.COMPRESS,
                title="音频压缩",
                description="压缩音频文件大小",
                on_click=lambda e: self._open_view('audio_compress'),
                gradient_colors=("#fbc2eb", "#a6c1ee"),
                tool_id="audio.compress",
            ),
            self._create_card(
                icon=ft.Icons.SPEED,
                title="音频倍速调整",
                description="调整音频播放速度(0.1x-10x)",
                on_click=lambda e: self._open_view('audio_speed'),
                gradient_colors=("#f093fb", "#f5576c"),
                tool_id="audio.speed",
            ),
            self._create_card(
                icon=ft.Icons.MUSIC_NOTE,
                title="人声提取",
                description="AI智能分离人声和伴奏",
                on_click=lambda e: self._open_view('vocal_extraction'),
                gradient_colors=("#ffecd2", "#fcb69f"),
                tool_id="audio.vocal_extraction",
            ),
            self._create_card(
                icon=ft.Icons.TRANSCRIBE,
                title="音视频转文字",
                description="AI语音识别，音视频转文字字幕",
                on_click=lambda e: self._open_view('audio_to_text'),
                gradient_colors=("#a8c0ff", "#3f2b96"),
                tool_id="audio.to_text",
            ),
            # 视频处理
            self._create_card(
                icon=ft.Icons.AUTO_AWESOME,
                title="视频增强",
                description="AI视频超分辨率增强，提升画质清晰度",
                on_click=lambda e: self._open_view('video_enhance'),
                gradient_colors=("#fa709a", "#fee140"),
                tool_id="video.enhance",
            ),
            self._create_card(
                icon=ft.Icons.SLOW_MOTION_VIDEO,
                title="视频插帧",
                description="AI帧率提升，让视频更流畅",
                on_click=lambda e: self._open_view('video_interpolation'),
                gradient_colors=("#667eea", "#764ba2"),
                tool_id="video.interpolation",
            ),
            self._create_card(
                icon=ft.Icons.AUTO_FIX_HIGH,
                title="视频去字幕/水印",
                description="AI智能移除视频字幕和水印",
                on_click=lambda e: self._open_view('subtitle_remove'),
                gradient_colors=("#FA709A", "#FEE140"),
                tool_id="video.subtitle_remove",
            ),
            self._create_card(
                icon=ft.Icons.SUBTITLES,
                title="视频配字幕",
                description="AI语音识别自动生成字幕并烧录到视频",
                on_click=lambda e: self._open_view('video_subtitle'),
                gradient_colors=("#4776E6", "#8E54E9"),
                tool_id="video.subtitle",
            ),
            self._create_card(
                icon=ft.Icons.COMPRESS,
                title="视频压缩",
                description="减小视频文件大小，支持CRF和分辨率调整",
                on_click=lambda e: self._open_view('video_compress'),
                gradient_colors=("#84fab0", "#8fd3f4"),
                tool_id="video.compress",
            ),
            self._create_card(
                icon=ft.Icons.VIDEO_FILE_ROUNDED,
                title="视频格式转换",
                description="支持MP4、AVI、MKV等格式互转",
                on_click=lambda e: self._open_view('video_convert'),
                gradient_colors=("#a8edea", "#fed6e3"),
                tool_id="video.convert",
            ),
            self._create_card(
                icon=ft.Icons.AUDIO_FILE_ROUNDED,
                title="视频提取音频",
                description="从视频中提取音频轨道",
                on_click=lambda e: self._open_view('video_extract_audio'),
                gradient_colors=("#ff9a9e", "#fad0c4"),
                tool_id="video.extract_audio",
            ),
            self._create_card(
                icon=ft.Icons.SPEED,
                title="视频倍速调整",
                description="调整视频播放速度(0.1x-10x)",
                on_click=lambda e: self._open_view('video_speed'),
                gradient_colors=("#667eea", "#764ba2"),
                tool_id="video.speed",
            ),
            self._create_card(
                icon=ft.Icons.GRAPHIC_EQ,
                title="视频人声分离",
                description="分离视频中的人声和背景音",
                on_click=lambda e: self._open_view('video_vocal_separation'),
                gradient_colors=("#fbc2eb", "#a6c1ee"),
                tool_id="video.vocal_separation",
            ),
            self._create_card(
                icon=ft.Icons.BRANDING_WATERMARK,
                title="视频添加水印",
                description="为视频添加文字或图片水印",
                on_click=lambda e: self._open_view('video_watermark'),
                gradient_colors=("#ffecd2", "#fcb69f"),
                tool_id="video.watermark",
            ),
            self._create_card(
                icon=ft.Icons.HEALING,
                title="视频修复",
                description="修复损坏、卡顿、无法播放的视频",
                on_click=lambda e: self._open_view('video_repair'),
                gradient_colors=("#30cfd0", "#330867"),
                tool_id="video.repair",
            ),
            self._create_card(
                icon=ft.Icons.VIDEOCAM,
                title="屏幕录制",
                description="使用 FFmpeg 录制屏幕，支持多种格式",
                on_click=lambda e: self._open_view('screen_record'),
                gradient_colors=("#FF416C", "#FF4B2B"),
                tool_id="video.screen_record",
            ),
            # 工具类（FFmpeg 终端不需要置顶功能）
            FeatureCard(
                icon=ft.Icons.TERMINAL,
                title="FFmpeg 终端",
                description="配置环境变量并打开命令行",
                on_click=lambda e: self._open_ffmpeg_terminal(),
                gradient_colors=("#4facfe", "#00f2fe"),
            ),
        ]
        
        # 初始化拖放工具映射
        self._init_drop_tool_map()
        
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
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
            expand=True,
            width=float('inf'),  # 占满可用宽度
            on_scroll=self._on_scroll,  # 跟踪滚动位置
        )

    def _open_view(self, view_name: str) -> None:
        """打开子视图。
        
        Args:
            view_name: 视图名称
        """
        # 记录工具使用次数
        from utils import get_tool
        # 将view_name转换为tool_id格式 (如 "audio_format" -> "audio.format")
        if view_name.startswith("audio_"):
            tool_id = "audio." + view_name.replace("audio_", "")
        elif view_name.startswith("video_"):
            tool_id = "video." + view_name.replace("video_", "")
        else:
            tool_id = None
        
        if tool_id:
            tool_meta = get_tool(tool_id)
            if tool_meta:
                self.config_service.record_tool_usage(tool_meta.name)
        
        # 检查FFmpeg是否可用
        is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_available:
            self._show_ffmpeg_install_view()
            return
        
        # 根据视图名称创建或切换到对应的子视图
        if view_name == 'audio_format':
            if not self.audio_format_view:
                self.audio_format_view = AudioFormatView(
                    self._saved_page,
                    self.config_service,
                    self.audio_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_format_view, 'audio_format')
            
        elif view_name == 'audio_compress':
            if not self.audio_compress_view:
                self.audio_compress_view = AudioCompressView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_compress_view, 'audio_compress')
            
        elif view_name == 'audio_speed':
            if not self.audio_speed_view:
                self.audio_speed_view = AudioSpeedView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_speed_view, 'audio_speed')
            
        elif view_name == 'vocal_extraction':
            if not self.vocal_extraction_view:
                from views.media.vocal_extraction_view import VocalExtractionView
                self.vocal_extraction_view = VocalExtractionView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.vocal_extraction_view, 'vocal_extraction')
            
        elif view_name == 'audio_to_text':
            if not self.audio_to_text_view:
                self.audio_to_text_view = AudioToTextView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.audio_to_text_view, 'audio_to_text')
            
        elif view_name == 'video_compress':
            if not self.video_compress_view:
                self.video_compress_view = VideoCompressView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_compress_view, 'video_compress')
            
        elif view_name == 'video_convert':
            if not self.video_convert_view:
                self.video_convert_view = VideoConvertView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_convert_view, 'video_convert')
            
        elif view_name == 'video_enhance':
            if not self.video_enhance_view:
                self.video_enhance_view = VideoEnhanceView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_enhance_view, 'video_enhance')
            
        elif view_name == 'video_interpolation':
            if not self.video_interpolation_view:
                self.video_interpolation_view = VideoInterpolationView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_interpolation_view, 'video_interpolation')
        
        elif view_name == 'subtitle_remove':
            if not self.subtitle_remove_view:
                self.subtitle_remove_view = SubtitleRemoveView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.subtitle_remove_view, 'subtitle_remove')
        
        elif view_name == 'video_subtitle':
            if not self.video_subtitle_view:
                self.video_subtitle_view = VideoSubtitleView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_subtitle_view, 'video_subtitle')
            
        elif view_name == 'video_extract_audio':
            if not self.video_extract_audio_view:
                self.video_extract_audio_view = VideoExtractAudioView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_extract_audio_view, 'video_extract_audio')
            
        elif view_name == 'video_speed':
            if not self.video_speed_view:
                self.video_speed_view = VideoSpeedView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_speed_view, 'video_speed')
            
        elif view_name == 'video_vocal_separation':
            if not self.video_vocal_separation_view:
                self.video_vocal_separation_view = VideoVocalSeparationView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_vocal_separation_view, 'video_vocal_separation')
            
        elif view_name == 'video_watermark':
            if not self.video_watermark_view:
                self.video_watermark_view = VideoWatermarkView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_watermark_view, 'video_watermark')
            
        elif view_name == 'video_repair':
            if not self.video_repair_view:
                self.video_repair_view = VideoRepairView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.video_repair_view, 'video_repair')
        
        elif view_name == 'screen_record':
            if not self.screen_record_view:
                self.screen_record_view = ScreenRecordView(
                    self._saved_page,
                    self.config_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            self._switch_to_sub_view(self.screen_record_view, 'screen_record')
    
    def _show_ffmpeg_install_view(self) -> None:
        """显示FFmpeg安装提示视图。"""
        if not self.ffmpeg_install_view:
            self.ffmpeg_install_view = FFmpegInstallView(
                self._saved_page,
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
            return
        
        # 如果当前已经是该视图，直接返回，避免重复切换
        if self.current_sub_view_type == view_type and self.current_sub_view == view:
            # 确保视图显示在容器中
            if self.parent_container.content != view:
                self.parent_container.content = view
                self._safe_page_update()
            return
        
        # 记录当前子视图
        self.current_sub_view = view
        self.current_sub_view_type = view_type
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 切换视图
        self.parent_container.content = view
        self._safe_page_update()
        
        # 处理从推荐视图传递的待处理文件
        if hasattr(self._saved_page, '_pending_drop_files') and self._saved_page._pending_drop_files:
            pending_files = self._saved_page._pending_drop_files
            self._saved_page._pending_drop_files = None
            self._saved_page._pending_tool_id = None
            
            # 让当前子视图处理文件
            if view and hasattr(view, 'add_files'):
                view.add_files(pending_files)
    
    def _back_to_main(self, e=None) -> None:
        """返回主视图（使用路由导航）。
        
        Args:
            e: 事件对象（可选）
        """
        import gc
        
        if not self.parent_container:
            return
        
        # 销毁当前子视图（而不是保留）
        if self.current_sub_view_type:
            view_map = {
                "audio_format": "audio_format_view",
                "audio_compress": "audio_compress_view",
                "audio_speed": "audio_speed_view",
                "vocal_extraction": "vocal_extraction_view",
                "audio_to_text": "audio_to_text_view",
                "video_compress": "video_compress_view",
                "video_convert": "video_convert_view",
                "video_enhance": "video_enhance_view",
                "video_interpolation": "video_interpolation_view",
                "subtitle_remove": "subtitle_remove_view",
                "video_subtitle": "video_subtitle_view",
                "video_extract_audio": "video_extract_audio_view",
                "video_repair": "video_repair_view",
                "video_speed": "video_speed_view",
                "video_vocal_separation": "video_vocal_separation_view",
                "video_watermark": "video_watermark_view",
                "screen_record": "screen_record_view",
                "ffmpeg_install": "ffmpeg_install_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                view_instance = getattr(self, view_attr, None)
                if view_instance:
                    # 统一调用 cleanup 方法（每个视图自己负责清理资源和卸载模型）
                    if hasattr(view_instance, 'cleanup'):
                        try:
                            view_instance.cleanup()
                        except Exception as ex:
                            logger.warning(f"清理视图 {view_attr} 时出错: {ex}")
                
                setattr(self, view_attr, None)
        
        # 清空当前子视图记录
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        # 强制垃圾回收释放内存
        gc.collect()
        
        # 直接恢复主界面（不依赖路由，因为打开工具时也是直接切换内容的）
        if self.parent_container:
            self.parent_container.content = self
            self._show_search_button()
            self._safe_page_update()
    
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
    
    def _init_drop_tool_map(self) -> None:
        """初始化拖放工具映射。"""
        # 音频格式
        _audio_exts = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff', '.ape'}
        # 视频格式
        _video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg', '.3gp'}
        # 音视频混合
        _media_exts = _audio_exts | _video_exts
        
        self._drop_tool_map = [
            # 音频工具
            ("音频格式转换", _audio_exts, 'audio_format', "audio_format_view"),
            ("音频压缩", _audio_exts, 'audio_compress', "audio_compress_view"),
            ("音频倍速调整", _audio_exts, 'audio_speed', "audio_speed_view"),
            ("人声提取", _audio_exts, 'vocal_extraction', "vocal_extraction_view"),
            ("音视频转文字", _media_exts, 'audio_to_text', "audio_to_text_view"),
            # 视频工具
            ("视频增强", _video_exts, 'video_enhance', "video_enhance_view"),
            ("视频插帧", _video_exts, 'video_interpolation', "video_interpolation_view"),
            ("视频去字幕/水印", _video_exts, 'subtitle_remove', "subtitle_remove_view"),
            ("视频配字幕", _video_exts, 'video_subtitle', "video_subtitle_view"),
            ("视频压缩", _video_exts, 'video_compress', "video_compress_view"),
            ("视频格式转换", _video_exts, 'video_convert', "video_convert_view"),
            ("视频提取音频", _video_exts, 'video_extract_audio', "video_extract_audio_view"),
            ("视频倍速调整", _video_exts, 'video_speed', "video_speed_view"),
            ("视频人声分离", _video_exts, 'video_vocal_separation', "video_vocal_separation_view"),
            ("视频添加水印", _video_exts, 'video_watermark', "video_watermark_view"),
            ("视频修复", _video_exts, 'video_repair', "video_repair_view"),
            ("屏幕录制", set(), None, None),  # 不接受拖放
            ("FFmpeg 终端", set(), None, None),  # 不接受拖放
        ]
        
        # 卡片布局参数（与 FeatureCard 一致）
        self._card_margin_left = 5
        self._card_margin_top = 5
        self._card_margin_bottom = 10
        self._card_width = 280
        self._card_height = 220
        self._card_step_x = self._card_margin_left + self._card_width + 0 + PADDING_LARGE
        self._card_step_y = self._card_margin_top + self._card_height + self._card_margin_bottom + PADDING_LARGE
        self._content_padding = PADDING_MEDIUM
        self._scroll_offset_y = 0.0
    
    def _on_scroll(self, e: ft.OnScrollEvent) -> None:
        """跟踪滚动位置。"""
        self._scroll_offset_y = e.pixels
    
    def handle_dropped_files_at(self, files: list, x: int, y: int) -> None:
        """处理拖放到指定位置的文件。"""
        from pathlib import Path
        
        # 如果当前显示的是子视图，让子视图处理
        if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
            self.current_sub_view.add_files(files)
            return
        
        # 初始化工具映射（如果还没初始化）
        if not hasattr(self, '_drop_tool_map'):
            self._init_drop_tool_map()
        
        # 计算点击的是哪个工具卡片
        nav_width = 100
        title_height = 32
        
        local_x = x - nav_width - self._content_padding
        local_y = y - title_height - self._content_padding + self._scroll_offset_y
        
        if local_x < 0 or local_y < 0:
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        col = int(local_x // self._card_step_x)
        row = int(local_y // self._card_step_y)
        
        window_width = self.page.window.width or 1000
        content_width = window_width - nav_width - self._content_padding * 2
        cols_per_row = max(1, int(content_width // self._card_step_x))
        
        index = row * cols_per_row + col
        
        if index < 0 or index >= len(self._drop_tool_map):
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        tool_name, supported_exts, view_name, view_attr = self._drop_tool_map[index]
        
        if not supported_exts or not view_name:
            self._show_snackbar(f"「{tool_name}」不支持文件拖放")
            return
        
        # 展开文件夹
        all_files = []
        for f in files:
            if f.is_dir():
                for item in f.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(f)
        
        # 过滤支持的文件
        supported_files = [f for f in all_files if f.suffix.lower() in supported_exts]
        
        if not supported_files:
            self._show_snackbar(f"「{tool_name}」不支持该格式")
            return
        
        # 保存待导入的文件
        self._pending_drop_files = supported_files
        self._pending_view_attr = view_attr
        
        # 打开工具
        self._open_view(view_name)
        
        # 导入文件
        self._import_pending_files()
    
    def _import_pending_files(self) -> None:
        """导入待处理的拖放文件。"""
        if not hasattr(self, '_pending_drop_files') or not self._pending_drop_files:
            return
        
        view_attr = getattr(self, '_pending_view_attr', None)
        if view_attr:
            view = getattr(self, view_attr, None)
            if view and hasattr(view, 'add_files'):
                view.add_files(self._pending_drop_files)
        
        self._pending_drop_files = []
        self._pending_view_attr = None
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            duration=3000,
        )
        self._saved_page.overlay.append(snackbar)
        snackbar.open = True
        self._saved_page.update()