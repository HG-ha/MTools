# -*- coding: utf-8 -*-
"""音频处理视图模块。

提供音频格式转换、编辑、批量处理等功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import AudioService, ConfigService, FFmpegService
from views.media.audio_format_view import AudioFormatView


class AudioView(ft.Container):
    """音频处理视图类。
    
    提供音频处理相关功能的用户界面，包括：
    - 音频格式转换
    - 音频剪辑
    - 批量处理
    - 音频参数调整
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化音频处理视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service if config_service else ConfigService()
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_LARGE,
            right=PADDING_LARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建服务
        self.ffmpeg_service: FFmpegService = FFmpegService(self.config_service)
        self.audio_service: AudioService = AudioService(self.ffmpeg_service)
        
        # 创建子视图（延迟创建）
        self.format_view: Optional[AudioFormatView] = None
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域
        feature_cards: ft.Row = ft.Row(
            controls=[
                FeatureCard(
                    icon=ft.Icons.AUDIO_FILE_ROUNDED,
                    title="格式转换",
                    description="支持MP3、WAV、AAC等格式互转",
                    gradient_colors=("#43E97B", "#38F9D7"),
                    on_click=self._open_format_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.CONTENT_CUT_ROUNDED,
                    title="音频剪辑",
                    description="裁剪、合并音频文件",
                    gradient_colors=("#FA709A", "#FEE140"),
                ),
                FeatureCard(
                    icon=ft.Icons.TUNE_ROUNDED,
                    title="参数调整",
                    description="调整比特率、采样率等参数",
                    gradient_colors=("#30CFD0", "#330867"),
                ),
            ],
            wrap=True,  # 自动换行
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,  # 从左开始排列
            vertical_alignment=ft.CrossAxisAlignment.START,  # 从上开始排列
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,  # 允许滚动
            horizontal_alignment=ft.CrossAxisAlignment.START,  # 从左对齐
            alignment=ft.MainAxisAlignment.START,  # 从上对齐
            expand=True,
            width=float('inf'),
        )
    
    def _open_format_dialog(self, e: ft.ControlEvent) -> None:
        """切换到音频格式转换工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建格式转换视图（如果还没创建）
        if not self.format_view:
            self.format_view = AudioFormatView(
                self.page,
                self.config_service,
                self.audio_service,
                self.ffmpeg_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.format_view
        
        # 切换到格式转换视图
        self.parent_container.content = self.format_view
        self.parent_container.update()
    
    def _back_to_main(self) -> None:
        """返回主界面。"""
        # 清除子视图状态
        self.current_sub_view = None
        
        if self.parent_container:
            self.parent_container.content = self
            self.parent_container.update()
    
    def restore_state(self) -> bool:
        """恢复视图状态（从其他页面切换回来时调用）。
        
        Returns:
            是否恢复了子视图（True表示已恢复子视图，False表示需要显示主视图）
        """
        if self.parent_container and self.current_sub_view:
            # 如果之前在子视图中，恢复到子视图
            self.parent_container.content = self.current_sub_view
            self.parent_container.update()
            return True
        return False
