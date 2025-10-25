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


class AudioView(ft.Container):
    """音频处理视图类。
    
    提供音频处理相关功能的用户界面，包括：
    - 音频格式转换
    - 音频剪辑
    - 批量处理
    - 音频参数调整
    """

    def __init__(self, page: ft.Page) -> None:
        """初始化音频处理视图。
        
        Args:
            page: Flet页面对象
        """
        super().__init__()
        self.page: ft.Page = page
        self.expand: bool = True
        self.padding: int = PADDING_XLARGE
        
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
            wrap=True,
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
