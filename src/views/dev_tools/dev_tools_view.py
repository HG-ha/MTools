# -*- coding: utf-8 -*-
"""开发工具视图模块。

提供开发者工具相关功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import ConfigService, EncodingService
from views.encoding import EncodingConvertView


class DevToolsView(ft.Container):
    """开发工具视图类。
    
    提供开发工具相关功能的用户界面，包括：
    - 编码转换
    - 代码格式化
    - Base64转图片
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        encoding_service: EncodingService,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化开发工具视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            encoding_service: 编码服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self._saved_page: ft.Page = page  # 保存页面引用
        self.config_service: ConfigService = config_service
        self.encoding_service: EncodingService = encoding_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 创建子视图（延迟创建）
        self.encoding_convert_view: Optional[EncodingConvertView] = None
        self.code_format_view: Optional[ft.Container] = None
        self.base64_to_image_view: Optional[ft.Container] = None
        
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
                # 编码转换
                FeatureCard(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="编码转换",
                    description="检测和转换文件编码格式",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_encoding_convert,
                ),
                # 代码格式化
                FeatureCard(
                    icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                    title="代码格式化",
                    description="格式化和美化代码",
                    gradient_colors=("#FA8BFF", "#2BD2FF"),
                    on_click=self._open_code_format,
                ),
                # Base64转图片
                FeatureCard(
                    icon=ft.Icons.IMAGE_OUTLINED,
                    title="Base64转图片",
                    description="Base64转图片，自动识别格式",
                    gradient_colors=("#4FACFE", "#00F2FE"),
                    on_click=self._open_base64_to_image,
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
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
        )
    
    def _open_encoding_convert(self, e: ft.ControlEvent) -> None:
        """打开编码转换。"""
        if self.encoding_convert_view is None:
            self.encoding_convert_view = EncodingConvertView(
                self.page,
                self.config_service,
                self.encoding_service,
                on_back=self._back_to_main
            )
        
        # 切换到编码转换视图
        if self.parent_container:
            self.current_sub_view = self.encoding_convert_view
            self.current_sub_view_type = "encoding_convert"
            self.parent_container.content = self.encoding_convert_view
        self._safe_page_update()
    
    def _open_code_format(self, e: ft.ControlEvent) -> None:
        """打开代码格式化。"""
        if self.code_format_view is None:
            from views.code_format.detail_view import CodeFormatDetailView
            self.code_format_view = CodeFormatDetailView(
                self.page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 切换到代码格式化视图
        if self.parent_container:
            self.current_sub_view = self.code_format_view
            self.current_sub_view_type = "code_format"
            self.parent_container.content = self.code_format_view
        self._safe_page_update()
    
    def _open_base64_to_image(self, e: ft.ControlEvent) -> None:
        """打开Base64转图片。"""
        if self.base64_to_image_view is None:
            from views.dev_tools.base64_to_image_view import Base64ToImageView
            self.base64_to_image_view = Base64ToImageView(
                self.page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 切换到Base64转图片视图
        if self.parent_container:
            self.current_sub_view = self.base64_to_image_view
            self.current_sub_view_type = "base64_to_image"
            self.parent_container.content = self.base64_to_image_view
        self._safe_page_update()
    
    def _back_to_main(self) -> None:
        """返回主界面。"""
        # 销毁当前子视图（而不是保留）
        if self.current_sub_view_type:
            view_map = {
                "encoding_convert": "encoding_convert_view",
                "code_format": "code_format_view",
                "base64_to_image": "base64_to_image_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                setattr(self, view_attr, None)
        
        # 清除子视图状态
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        if self.parent_container:
            self.parent_container.content = self
        self._safe_page_update()
    
    def restore_state(self) -> bool:
        """恢复之前的视图状态。
        
        Returns:
            是否成功恢复到子视图
        """
        if self.current_sub_view and self.parent_container:
            self.parent_container.content = self.current_sub_view
            self._safe_page_update()
            return True
        return False

