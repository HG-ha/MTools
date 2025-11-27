# -*- coding: utf-8 -*-
"""其他工具视图模块。

提供其他类别工具的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
)
from services import ConfigService


class OthersView(ft.Container):
    """其他工具视图类。
    
    提供其他工具相关功能的用户界面。
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化其他工具视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self._saved_page: ft.Page = page  # 保存页面引用
        self.config_service: ConfigService = config_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
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
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域
        feature_cards: ft.Row = ft.Row(
            controls=[
                # 预留位置，后续添加具体工具
                FeatureCard(
                    icon=ft.Icons.CONSTRUCTION_ROUNDED,
                    title="敬请期待",
                    description="更多实用工具即将上线",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=lambda _: self._show_message("功能开发中..."),
                ),
            ],
            wrap=True,
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    
    def _show_message(self, message: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
        """
        snack_bar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000,
        )
        self.page.snack_bar = snack_bar
        snack_bar.open = True
        self.page.update()
    
    def restore_state(self) -> None:
        """恢复视图状态。
        
        当用户从其他类型视图返回时，恢复之前的状态。
        """
        if self.current_sub_view and self.parent_container:
            # 恢复到子视图
            self.parent_container.content = self.current_sub_view
            self._safe_page_update()
    
    def cleanup(self) -> None:
        """清理视图资源。
        
        当视图被切换走时调用，释放不需要的资源。
        """
        # 可以在这里添加资源清理逻辑
        pass
