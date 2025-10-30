# -*- coding: utf-8 -*-
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
from services import ConfigService, EncodingService
from views.encoding.convert_view import EncodingConvertView


class EncodingView(ft.Container):
    """编码转换视图类。
    
    提供编码转换相关功能的用户界面，包括：
    - 自动检测文件编码
    - 编码格式转换
    - 批量转换
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        encoding_service: EncodingService,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化编码转换视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            encoding_service: 编码服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.encoding_service: EncodingService = encoding_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        # 右侧多留一些空间
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建子视图（延迟创建）
        self.convert_view: Optional[EncodingConvertView] = None
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域 - 自适应布局，确保从左到右、从上到下排列
        feature_cards: ft.Row = ft.Row(
            controls=[
                FeatureCard(
                    icon=ft.Icons.FIND_IN_PAGE_ROUNDED,
                    title="编码检测",
                    description="自动检测文件编码格式",
                    gradient_colors=("#FFD89B", "#19547B"),
                    on_click=self._open_convert_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="编码转换",
                    description="支持UTF-8、GBK、GB2312等",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_convert_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                    title="批量处理",
                    description="批量转换整个文件夹",
                    gradient_colors=("#89F7FE", "#66A6FF"),
                    on_click=self._open_convert_dialog,
                ),
            ],
            wrap=True,  # 自动换行
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,  # 从左开始排列
            vertical_alignment=ft.CrossAxisAlignment.START,  # 从上开始排列
        )
        
        # 组装视图 - 确保内容从左上角开始排列
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,  # 允许滚动
            horizontal_alignment=ft.CrossAxisAlignment.START,  # 从左对齐
            alignment=ft.MainAxisAlignment.START,  # 从上对齐
        )
    
    def _open_convert_dialog(self, e: ft.ControlEvent) -> None:
        """切换到编码转换工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建转换视图（如果还没创建）
        if not self.convert_view:
            self.convert_view = EncodingConvertView(
                self.page,
                self.config_service,
                self.encoding_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.convert_view
        
        # 切换到转换视图
        self.parent_container.content = self.convert_view
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