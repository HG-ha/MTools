# -*- coding: utf-8 -*-
"""视频处理视图模块。

提供视频格式转换、编辑、批量处理等功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)


class VideoView(ft.Container):
    """视频处理视图类。
    
    提供视频处理相关功能的用户界面，包括：
    - 视频格式转换
    - 视频剪辑
    - 批量处理
    - 视频参数调整
    """

    def __init__(self, page: ft.Page) -> None:
        """初始化视频处理视图。
        
        Args:
            page: Flet页面对象
        """
        super().__init__()
        self.page: ft.Page = page
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_LARGE,
            right=PADDING_LARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域
        feature_cards: ft.Row = ft.Row(
            controls=[
                FeatureCard(
                    icon=ft.Icons.VIDEO_FILE_ROUNDED,
                    title="格式转换",
                    description="支持MP4、AVI、MKV等格式互转",
                    gradient_colors=("#A8EDEA", "#FED6E3"),
                ),
                FeatureCard(
                    icon=ft.Icons.VIDEO_CALL_ROUNDED,
                    title="视频剪辑",
                    description="裁剪、合并、添加水印",
                    gradient_colors=("#FF9A9E", "#FAD0C4"),
                ),
                FeatureCard(
                    icon=ft.Icons.HIGH_QUALITY_ROUNDED,
                    title="质量调整",
                    description="调整分辨率、码率等参数",
                    gradient_colors=("#A18CD1", "#FBC2EB"),
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
        )