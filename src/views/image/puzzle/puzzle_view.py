"""图片拼接主视图模块。

提供图片拼接功能的主菜单界面。
"""

from typing import Callable, Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from views.image.puzzle.split_view import ImagePuzzleSplitView
from views.image.puzzle.merge_view import ImagePuzzleMergeView


class ImagePuzzleView(ft.Container):
    """图片拼接主视图类。
    
    显示拼接功能的子功能入口：
    - 单图切分（九宫格）
    - 多图合并
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片拼接主视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable] = on_back
        
        # 子视图（延迟创建）
        self.split_view: Optional[ImagePuzzleSplitView] = None
        self.merge_view: Optional[ImagePuzzleMergeView] = None
        self.parent_container: Optional[ft.Container] = None
        self.current_sub_view: Optional[ft.Container] = None
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 构建界面
        self._build_ui()
    
    def set_parent_container(self, container: ft.Container) -> None:
        """设置父容器，用于子视图切换。
        
        Args:
            container: 父容器
        """
        self.parent_container = container
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 顶部：标题和返回按钮
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("图片拼接", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 功能卡片
        feature_cards: ft.Row = ft.Row(
            controls=[
                FeatureCard(
                    icon=ft.Icons.GRID_ON,
                    title="单图切分",
                    description="九宫格切分，可设置间距和背景色",
                    gradient_colors=("#FF6B6B", "#FFE66D"),
                    on_click=self._open_split_view,
                ),
                FeatureCard(
                    icon=ft.Icons.VIEW_MODULE,
                    title="多图合并",
                    description="横向、纵向、网格拼接多张图片",
                    gradient_colors=("#4ECDC4", "#44A08D"),
                    on_click=self._open_merge_view,
                ),
            ],
            wrap=True,
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=PADDING_LARGE),
                feature_cards,
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _open_split_view(self, e: ft.ControlEvent) -> None:
        """打开单图切分视图。"""
        if not self.parent_container:
            # 如果没有父容器，使用自己作为容器
            self.parent_container = self
        
        # 创建切分视图（如果还没创建）
        if not self.split_view:
            self.split_view = ImagePuzzleSplitView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.split_view
        
        # 切换到切分视图
        self.parent_container.content = self.split_view
        self.parent_container.update()
    
    def _open_merge_view(self, e: ft.ControlEvent) -> None:
        """打开多图合并视图。"""
        if not self.parent_container:
            # 如果没有父容器，使用自己作为容器
            self.parent_container = self
        
        # 创建合并视图（如果还没创建）
        if not self.merge_view:
            self.merge_view = ImagePuzzleMergeView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.merge_view
        
        # 切换到合并视图
        self.parent_container.content = self.merge_view
        self.parent_container.update()
    
    def _back_to_main(self) -> None:
        """返回主菜单。"""
        # 清除子视图状态
        self.current_sub_view = None
        
        if self.parent_container:
            self.parent_container.content = self
            self.parent_container.update()
    
    def restore_state(self) -> bool:
        """恢复视图状态（从其他页面切换回来时调用）。
        
        Returns:
            是否恢复了子视图
        """
        if self.parent_container and self.current_sub_view:
            # 如果之前在子视图中，恢复到子视图
            self.parent_container.content = self.current_sub_view
            self.parent_container.update()
            return True
        return False
