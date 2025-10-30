# -*- coding: utf-8 -*-
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
from views.image.background_view import ImageBackgroundView
from views.image.compress_view import ImageCompressView
from views.image.crop_view import ImageCropView
from views.image.format_view import ImageFormatView
from views.image.info_view import ImageInfoView
from views.image.puzzle import ImagePuzzleView
from views.image.resize_view import ImageResizeView


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
        self.clip_behavior: ft.ClipBehavior = ft.ClipBehavior.NONE  # 关键：不裁剪溢出内容

        self.padding: ft.padding = ft.padding.only(
            left=PADDING_LARGE,
            right=PADDING_LARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建子视图（延迟创建）
        self.compress_view: Optional[ImageCompressView] = None
        self.resize_view: Optional[ImageResizeView] = None
        self.format_view: Optional[ImageFormatView] = None
        self.background_view: Optional[ImageBackgroundView] = None
        self.puzzle_view: Optional[ImagePuzzleView] = None
        self.crop_view: Optional[ImageCropView] = None
        self.info_view: Optional[ImageInfoView] = None
        
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
                    on_click=self._open_resize_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="格式转换",
                    description="支持JPG、PNG、WebP等格式互转",
                    gradient_colors=("#4FACFE", "#00F2FE"),
                    on_click=self._open_format_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.AUTO_FIX_HIGH,
                    title="背景移除",
                    description="AI智能抠图，一键去除背景",
                    gradient_colors=("#FA709A", "#FEE140"),
                    on_click=self._open_background_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.DASHBOARD_CUSTOMIZE,
                    title="图片拼接",
                    description="九宫格切分、多图合并拼接",
                    gradient_colors=("#43E97B", "#38F9D7"),
                    on_click=self._open_puzzle_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.CROP,
                    title="图片裁剪",
                    description="可视化裁剪，实时预览效果",
                    gradient_colors=("#A8EDEA", "#FED6E3"),
                    on_click=self._open_crop_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.INFO,
                    title="图片信息",
                    description="查看图片详细信息和EXIF数据",
                    gradient_colors=("#FFA8A8", "#FCFF82"),
                    on_click=self._open_info_dialog,
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
            expand=True,  # 占满整个容器
            width=float('inf'),  # 占满可用宽度
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
    
    def _open_resize_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片尺寸调整工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建尺寸调整视图（如果还没创建）
        if not self.resize_view:
            self.resize_view = ImageResizeView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.resize_view
        
        # 切换到尺寸调整视图
        self.parent_container.content = self.resize_view
        self.parent_container.update()
    
    def _open_format_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片格式转换工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建格式转换视图（如果还没创建）
        if not self.format_view:
            self.format_view = ImageFormatView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.format_view
        
        # 切换到格式转换视图
        self.parent_container.content = self.format_view
        self.parent_container.update()
    
    def _open_background_dialog(self, e: ft.ControlEvent) -> None:
        """切换到背景移除工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 使用定时器延迟切换，让点击动画先完成（Material Design 涟漪动画约150-200ms）
        import threading
        
        def delayed_create_and_switch():
            # 创建背景移除视图（如果还没创建）
            if not self.background_view:
                self.background_view = ImageBackgroundView(
                    self.page,
                    self.config_service,
                    self.image_service,
                    on_back=self._back_to_main
                )
            
            # 记录当前子视图
            self.current_sub_view = self.background_view
            
            # 切换到背景移除视图
            self.parent_container.content = self.background_view
            try:
                self.parent_container.update()
            except:
                pass
        
        # 使用定时器延迟执行，让点击动画先播放完
        timer = threading.Timer(0.2, delayed_create_and_switch)
        timer.daemon = True
        timer.start()
    
    def _open_puzzle_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片拼接工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建拼接视图（如果还没创建）
        if not self.puzzle_view:
            self.puzzle_view = ImagePuzzleView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
            # 设置拼图视图的父容器，让它可以切换到子功能
            self.puzzle_view.set_parent_container(self.parent_container)
        
        # 记录当前子视图
        self.current_sub_view = self.puzzle_view
        
        # 切换到拼接视图
        self.parent_container.content = self.puzzle_view
        self.parent_container.update()
    
    def _open_crop_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片裁剪工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建裁剪视图（如果还没创建）
        if not self.crop_view:
            self.crop_view = ImageCropView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.crop_view
        
        # 切换到裁剪视图
        self.parent_container.content = self.crop_view
        self.parent_container.update()
    
    def _open_info_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片信息查看工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 创建信息查看视图（如果还没创建）
        if not self.info_view:
            self.info_view = ImageInfoView(
                self.page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.info_view
        
        # 切换到信息查看视图
        self.parent_container.content = self.info_view
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
