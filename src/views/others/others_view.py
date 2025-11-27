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
                FeatureCard(
                    icon=ft.Icons.UPDATE_DISABLED,
                    title="Windows更新管理",
                    description="禁用或恢复Windows自动更新",
                    gradient_colors=("#FF6B6B", "#FFA500"),
                    on_click=lambda _: self._open_windows_update_view(),
                ),
                FeatureCard(
                    icon=ft.Icons.LINK,
                    title="图片转URL",
                    description="上传图片生成分享链接",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=lambda _: self._open_image_to_url_view(),
                ),
                FeatureCard(
                    icon=ft.Icons.UPLOAD_FILE,
                    title="文件转URL",
                    description="上传文件获取分享链接",
                    gradient_colors=("#F093FB", "#F5576C"),
                    on_click=lambda _: self._open_file_to_url_view(),
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
    
    def _open_windows_update_view(self) -> None:
        """打开Windows更新管理视图。"""
        from views.others import WindowsUpdateView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建Windows更新视图
        windows_update_view = WindowsUpdateView(
            page=self.page,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = windows_update_view
        self.current_sub_view_type = "windows_update"
        
        # 切换到子视图
        self.parent_container.content = windows_update_view
        self._safe_page_update()
    
    def _open_image_to_url_view(self) -> None:
        """打开图片转URL视图。"""
        from views.others import ImageToUrlView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建图片转URL视图
        image_to_url_view = ImageToUrlView(
            page=self.page,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = image_to_url_view
        self.current_sub_view_type = "image_to_url"
        
        # 切换到子视图
        self.parent_container.content = image_to_url_view
        self._safe_page_update()
    
    def _open_file_to_url_view(self) -> None:
        """打开文件转URL视图。"""
        from views.others import FileToUrlView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建文件转URL视图
        file_to_url_view = FileToUrlView(
            page=self.page,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = file_to_url_view
        self.current_sub_view_type = "file_to_url"
        
        # 切换到子视图
        self.parent_container.content = file_to_url_view
        self._safe_page_update()
    
    def _restore_main_view(self) -> None:
        """恢复到主视图。"""
        if self.parent_container:
            self.current_sub_view = None
            self.current_sub_view_type = None
            self.parent_container.content = self
            self._safe_page_update()
    
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
