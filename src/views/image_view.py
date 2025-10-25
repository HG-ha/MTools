"""图片处理视图模块。

提供图片格式转换、尺寸调整、滤镜效果等功能的用户界面。
"""

from typing import Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from views.image_compress_view import ImageCompressView


class ImageView(ft.Container):
    """图片处理视图类。
    
    提供图片处理相关功能的用户界面，包括：
    - 图片格式转换
    - 尺寸调整
    - 批量处理
    - 滤镜效果
    """

    def __init__(self, page: ft.Page, config_service: ConfigService, image_service: ImageService, parent_container: Optional[ft.Container] = None) -> None:
        """初始化图片处理视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        # 右侧多留一些空间
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE + 16,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建压缩视图（延迟创建）
        self.compress_view: Optional[ImageCompressView] = None
        
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
                    icon=ft.Icons.COMPRESS_ROUNDED,
                    title="图片压缩",
                    description="专业压缩工具，最高减小80%体积",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_compress_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.PHOTO_SIZE_SELECT_LARGE_ROUNDED,
                    title="尺寸调整",
                    description="批量调整图片尺寸和分辨率",
                    gradient_colors=("#F093FB", "#F5576C"),
                ),
                FeatureCard(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="格式转换",
                    description="支持JPG、PNG、WebP等格式互转",
                    gradient_colors=("#4FACFE", "#00F2FE"),
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
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    
    def _open_compress_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片压缩工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建压缩视图（如果还没创建）
        if not self.compress_view:
            self.compress_view = ImageCompressView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.compress_view
        
        # 切换到压缩视图
        self.parent_container.content = self.compress_view
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
        