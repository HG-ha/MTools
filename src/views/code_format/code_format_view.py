"""代码格式化视图模块。

提供代码格式化、美化等功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)


class CodeFormatView(ft.Container):
    """代码格式化视图类。
    
    提供代码格式化相关功能的用户界面，包括：
    - 多语言代码格式化
    - 代码美化
    - 批量处理
    """

    def __init__(self, page: ft.Page) -> None:
        """初始化代码格式化视图。
        
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
                    icon=ft.Icons.CODE_ROUNDED,
                    title="代码格式化",
                    description="支持Python、Java、C++等语言",
                    gradient_colors=("#FA8BFF", "#2BD2FF"),
                ),
                FeatureCard(
                    icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                    title="代码美化",
                    description="自动调整缩进和代码风格",
                    gradient_colors=("#2AF598", "#009EFD"),
                ),
                FeatureCard(
                    icon=ft.Icons.FOLDER_COPY_ROUNDED,
                    title="批量格式化",
                    description="批量处理整个项目",
                    gradient_colors=("#CE9FFC", "#7367F0"),
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