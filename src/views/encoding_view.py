"""编码转换视图模块。

提供文件编码检测和转换功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)


class EncodingView(ft.Container):
    """编码转换视图类。
    
    提供编码转换相关功能的用户界面，包括：
    - 自动检测文件编码
    - 编码格式转换
    - 批量转换
    """

    def __init__(self, page: ft.Page) -> None:
        """初始化编码转换视图。
        
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
                    icon=ft.Icons.FIND_IN_PAGE_ROUNDED,
                    title="编码检测",
                    description="自动检测文件编码格式",
                    gradient_colors=("#FFD89B", "#19547B"),
                ),
                FeatureCard(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="编码转换",
                    description="支持UTF-8、GBK、GB2312等",
                    gradient_colors=("#667EEA", "#764BA2"),
                ),
                FeatureCard(
                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                    title="批量处理",
                    description="批量转换整个文件夹",
                    gradient_colors=("#89F7FE", "#66A6FF"),
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