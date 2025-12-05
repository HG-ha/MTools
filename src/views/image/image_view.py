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
from utils import logger
from views.image.background_view import ImageBackgroundView
from views.image.compress_view import ImageCompressView
from views.image.crop_view import ImageCropView
from views.image.enhance_view import ImageEnhanceView
from views.image.format_view import ImageFormatView
from views.image.gif_adjustment_view import GifAdjustmentView
from views.image.info_view import ImageInfoView
from views.image.puzzle.split_view import ImagePuzzleSplitView
from views.image.puzzle.merge_view import ImagePuzzleMergeView
from views.image.resize_view import ImageResizeView
from views.image.search_view import ImageSearchView


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
        self._saved_page: ft.Page = page  # 保存页面引用,防止布局重建后丢失
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.clip_behavior: ft.ClipBehavior = ft.ClipBehavior.NONE  # 关键：不裁剪溢出内容

        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 创建子视图（延迟创建）
        self.compress_view: Optional[ImageCompressView] = None
        self.image_tools_install_view: Optional[object] = None  # 图片工具安装视图
        self.resize_view: Optional[ImageResizeView] = None
        self.format_view: Optional[ImageFormatView] = None
        self.background_view: Optional[ImageBackgroundView] = None
        self.enhance_view: Optional[ImageEnhanceView] = None
        self.split_view = None  # 九宫格切分视图
        self.merge_view = None  # 多图合并视图
        self.crop_view: Optional[ImageCropView] = None
        self.info_view: Optional[ImageInfoView] = None
        self.gif_adjustment_view: Optional[GifAdjustmentView] = None
        self.to_base64_view = None  # 图片转Base64视图
        self.rotate_view = None  # 图片旋转/翻转视图
        self.remove_exif_view = None  # 去除EXIF视图
        self.qrcode_view = None  # 二维码生成视图
        self.watermark_view = None  # 添加水印视图
        self.search_view = None  # 图片搜索视图
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        # 记录当前子视图的类型（用于销毁）
        self.current_sub_view_type: Optional[str] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _safe_page_update(self) -> None:
        """安全地更新页面,处理布局重建后页面引用丢失的情况。"""
        page = getattr(self, '_saved_page', self.page)
        if page:
            page.update()
    
    def _hide_search_button(self) -> None:
        """隐藏主视图的搜索按钮。"""
        if hasattr(self.page, '_main_view'):
            self.page._main_view.hide_search_button()
    
    def _show_search_button(self) -> None:
        """显示主视图的搜索按钮。"""
        if hasattr(self.page, '_main_view'):
            self.page._main_view.show_search_button()
    
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
                    icon=ft.Icons.AUTO_AWESOME,
                    title="图像增强",
                    description="AI超分辨率，4倍放大清晰化",
                    gradient_colors=("#30CFD0", "#330867"),
                    on_click=self._open_enhance_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.GRID_ON,
                    title="单图切分",
                    description="单图切分为九宫格，可设置间距",
                    gradient_colors=("#FF6B6B", "#FFE66D"),
                    on_click=self._open_split_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.VIEW_MODULE,
                    title="多图拼接",
                    description="横向、纵向、网格拼接图片",
                    gradient_colors=("#4ECDC4", "#44A08D"),
                    on_click=self._open_merge_dialog,
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
                FeatureCard(
                    icon=ft.Icons.GIF_BOX,
                    title="GIF/Live Photo 编辑",
                    description="调整 GIF / 实况图的速度、循环等参数，支持导出为视频",
                    gradient_colors=("#FF9A9E", "#FAD0C4"),
                    on_click=self._open_gif_adjustment_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.CODE,
                    title="图片转Base64",
                    description="将图片转换为Base64编码，支持Data URI格式",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_to_base64_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.ROTATE_90_DEGREES_CCW,
                    title="旋转/翻转",
                    description="支持GIF动图、实时预览、自定义角度、批量处理",
                    gradient_colors=("#F77062", "#FE5196"),
                    on_click=self._open_rotate_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.SECURITY,
                    title="去除EXIF",
                    description="删除图片元数据，保护隐私",
                    gradient_colors=("#C471F5", "#FA71CD"),
                    on_click=self._open_remove_exif_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.QR_CODE_2,
                    title="二维码生成",
                    description="生成二维码，支持自定义样式",
                    gradient_colors=("#20E2D7", "#F9FEA5"),
                    on_click=self._open_qrcode_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.BRANDING_WATERMARK,
                    title="添加水印",
                    description="支持单个水印和全屏平铺水印，批量处理，实时预览",
                    gradient_colors=("#FF6FD8", "#3813C2"),
                    on_click=self._open_watermark_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.IMAGE_SEARCH,
                    title="图片搜索",
                    description="以图搜图，搜索相似图片",
                    gradient_colors=("#FFA726", "#FB8C00"),
                    on_click=self._open_search_dialog,
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
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 检查工具是否已安装
        tools_status = self.image_service.check_tools_installed()
        if not tools_status["all_installed"]:
            # 显示安装视图
            self._show_image_tools_install_view()
            return
        
        # 创建压缩视图（如果还没创建）
        if not self.compress_view:
            self.compress_view = ImageCompressView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.compress_view
        self.current_sub_view_type = "compress"
        
        # 切换到压缩视图
        self.parent_container.content = self.compress_view
        
        self._safe_page_update()
    
    def _open_resize_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片尺寸调整工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建尺寸调整视图（如果还没创建）
        if not self.resize_view:
            self.resize_view = ImageResizeView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.resize_view
        self.current_sub_view_type = "resize"
        
        # 切换到尺寸调整视图
        self.parent_container.content = self.resize_view
        self._safe_page_update()
    
    def _open_format_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片格式转换工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建格式转换视图（如果还没创建）
        if not self.format_view:
            self.format_view = ImageFormatView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.format_view
        self.current_sub_view_type = "format"
        
        # 切换到格式转换视图
        self.parent_container.content = self.format_view
        self._safe_page_update()
    
    def _open_background_dialog(self, e: ft.ControlEvent) -> None:
        """切换到背景移除工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 使用定时器延迟切换，让点击动画先完成（Material Design 涟漪动画约150-200ms）
        import threading
        
        def delayed_create_and_switch():
            # 创建背景移除视图（如果还没创建）
            if not self.background_view:
                self.background_view = ImageBackgroundView(
                    self._saved_page,
                    self.config_service,
                    self.image_service,
                    on_back=self._back_to_main
                )
            
            # 记录当前子视图
            self.current_sub_view = self.background_view
            self.current_sub_view_type = "background"
            
            # 切换到背景移除视图
            self.parent_container.content = self.background_view
            self._safe_page_update()
        
        # 使用定时器延迟执行，让点击动画先播放完
        timer = threading.Timer(0.2, delayed_create_and_switch)
        timer.daemon = True
        timer.start()
    
    def _open_enhance_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图像增强工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        import threading
        
        def delayed_create_and_switch():
            # 创建图像增强视图（如果还没创建）
            if not self.enhance_view:
                self.enhance_view = ImageEnhanceView(
                    self._saved_page,
                    self.config_service,
                    self.image_service,
                    on_back=self._back_to_main
                )
            
            # 记录当前子视图
            self.current_sub_view = self.enhance_view
            self.current_sub_view_type = "enhance"
            
            # 切换到图像增强视图
            self.parent_container.content = self.enhance_view
            self._safe_page_update()
        
        timer = threading.Timer(0.2, delayed_create_and_switch)
        timer.daemon = True
        timer.start()
    
    def _open_split_dialog(self, e: ft.ControlEvent) -> None:
        """切换到九宫格切分工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建切分视图（如果还没创建）
        if not self.split_view:
            self.split_view = ImagePuzzleSplitView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.split_view
        self.current_sub_view_type = "split"
        
        # 切换到切分视图
        self.parent_container.content = self.split_view
        self._safe_page_update()
    
    def _open_merge_dialog(self, e: ft.ControlEvent) -> None:
        """切换到多图合并工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建合并视图（如果还没创建）
        if not self.merge_view:
            self.merge_view = ImagePuzzleMergeView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.merge_view
        self.current_sub_view_type = "merge"
        
        # 切换到合并视图
        self.parent_container.content = self.merge_view
        self._safe_page_update()
    
    def _open_crop_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片裁剪工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建裁剪视图（如果还没创建）
        if not self.crop_view:
            self.crop_view = ImageCropView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.crop_view
        self.current_sub_view_type = "crop"
        
        # 切换到裁剪视图
        self.parent_container.content = self.crop_view
        self._safe_page_update()
    
    def _open_info_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片信息查看工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建信息查看视图（如果还没创建）
        if not self.info_view:
            self.info_view = ImageInfoView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.info_view
        self.current_sub_view_type = "info"
        
        # 切换到信息查看视图
        self.parent_container.content = self.info_view
        self._safe_page_update()
    
    def _open_gif_adjustment_dialog(self, e: ft.ControlEvent) -> None:
        """切换到 GIF 调整工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建 GIF 调整视图（如果还没创建）
        if not self.gif_adjustment_view:
            self.gif_adjustment_view = GifAdjustmentView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main,
                parent_container=self.parent_container
            )
        
        # 记录当前子视图
        self.current_sub_view = self.gif_adjustment_view
        self.current_sub_view_type = "gif_adjustment"
        
        # 切换到 GIF 调整视图
        self.parent_container.content = self.gif_adjustment_view
        self._safe_page_update()
    
    def _open_to_base64_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片转Base64工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建图片转Base64视图（如果还没创建）
        if not self.to_base64_view:
            from views.image.to_base64_view import ImageToBase64View
            self.to_base64_view = ImageToBase64View(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.to_base64_view
        self.current_sub_view_type = "to_base64"
        
        # 切换到图片转Base64视图
        self.parent_container.content = self.to_base64_view
        self._safe_page_update()
    
    def _open_rotate_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片旋转/翻转工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建图片旋转视图（如果还没创建）
        if not self.rotate_view:
            from views.image.rotate_view import ImageRotateView
            self.rotate_view = ImageRotateView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.rotate_view
        self.current_sub_view_type = "rotate"
        
        # 切换到旋转视图
        self.parent_container.content = self.rotate_view
        self._safe_page_update()
    
    def _open_remove_exif_dialog(self, e: ft.ControlEvent) -> None:
        """切换到去除EXIF工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建去除EXIF视图（如果还没创建）
        if not self.remove_exif_view:
            from views.image.remove_exif_view import ImageRemoveExifView
            self.remove_exif_view = ImageRemoveExifView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.remove_exif_view
        self.current_sub_view_type = "remove_exif"
        
        # 切换到去除EXIF视图
        self.parent_container.content = self.remove_exif_view
        self._safe_page_update()
    
    def _open_qrcode_dialog(self, e: ft.ControlEvent) -> None:
        """切换到二维码生成工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建二维码生成视图（如果还没创建）
        if not self.qrcode_view:
            from views.image.qrcode_view import QRCodeGeneratorView
            self.qrcode_view = QRCodeGeneratorView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.qrcode_view
        self.current_sub_view_type = "qrcode"
        
        # 切换到二维码生成视图
        self.parent_container.content = self.qrcode_view
        self._safe_page_update()
    
    def _open_watermark_dialog(self, e: ft.ControlEvent) -> None:
        """切换到添加水印工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建添加水印视图（如果还没创建）
        if not self.watermark_view:
            from views.image.watermark_view import ImageWatermarkView
            self.watermark_view = ImageWatermarkView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.watermark_view
        self.current_sub_view_type = "watermark"
        
        # 切换到添加水印视图
        self.parent_container.content = self.watermark_view
        self._safe_page_update()
    
    def _open_search_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片搜索工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建图片搜索视图（如果还没创建）
        if not self.search_view:
            self.search_view = ImageSearchView(
                self._saved_page,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.search_view
        self.current_sub_view_type = "search"
        
        # 切换到图片搜索视图
        self.parent_container.content = self.search_view
        self._safe_page_update()
    
    def _back_to_main(self, e: ft.ControlEvent = None) -> None:
        """返回主界面。
        
        Args:
            e: 控件事件对象（可选）
        """
        # 销毁当前子视图（除了压缩视图保留）
        if self.current_sub_view_type:
            view_map = {
                "compress": None,  # 保留压缩视图
                "resize": "resize_view",
                "format": "format_view",
                "background": "background_view",
                "split": "split_view",
                "merge": "merge_view",
                "crop": "crop_view",
                "info": "info_view",
                "gif_adjustment": "gif_adjustment_view",
                "to_base64": "to_base64_view",
                "rotate": "rotate_view",
                "remove_exif": "remove_exif_view",
                "qrcode": "qrcode_view",
                "watermark": "watermark_view",
                "search": "search_view",
                "image_tools_install": "image_tools_install_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                setattr(self, view_attr, None)
        
        # 清除子视图状态
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        # 先恢复容器内容
        if self.parent_container:
            self.parent_container.content = self
            # 使用安全的页面更新方法，而不是直接更新容器
            self._safe_page_update()
        
        # 显示搜索按钮
        self._show_search_button()
    
    def _show_image_tools_install_view(self) -> None:
        """显示图片压缩工具安装视图。"""
        from views.image.image_tools_install_view import ImageToolsInstallView
        
        if not self.image_tools_install_view:
            self.image_tools_install_view = ImageToolsInstallView(
                self._saved_page,
                self.image_service,
                on_back=self._back_to_main,
                on_installed=self._on_image_tools_installed
            )
        
        # 记录当前子视图
        self.current_sub_view = self.image_tools_install_view
        self.current_sub_view_type = "image_tools_install"
        
        # 切换到安装视图
        self.parent_container.content = self.image_tools_install_view
        self._safe_page_update()
    
    def _on_image_tools_installed(self, e=None) -> None:
        """图片工具安装完成回调。"""
        # 返回主视图
        self._back_to_main()
    
    def restore_state(self) -> bool:
        """恢复视图状态（从其他页面切换回来时调用）。
        
        Returns:
            是否恢复了子视图（True表示已恢复子视图，False表示需要显示主视图）
        """
        if self.parent_container and self.current_sub_view:
            # 如果之前在子视图中，恢复到子视图
            self.parent_container.content = self.current_sub_view
            
            self._safe_page_update()
            return True
        return False
    
    def open_tool(self, tool_name: str) -> None:
        """根据工具名称打开对应的工具。
        
        Args:
            tool_name: 工具名称，如 "compress", "resize", "format" 等
        """
        # 记录工具使用次数
        from utils import get_tool
        tool_id = f"image.{tool_name}"
        tool_meta = get_tool(tool_id)
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 工具名称到方法的映射
        tool_map = {
            "compress": self._open_compress_dialog,
            "resize": self._open_resize_dialog,
            "format": self._open_format_dialog,
            "crop": self._open_crop_dialog,
            "rotate": self._open_rotate_dialog,
            "background": self._open_background_dialog,
            "watermark": self._open_watermark_dialog,
            "info": self._open_info_dialog,
            "exif": self._open_remove_exif_dialog,
            "qrcode": self._open_qrcode_dialog,
            "to_base64": self._open_to_base64_dialog,
            "gif": self._open_gif_adjustment_dialog,
            "puzzle.merge": self._open_merge_dialog,
            "puzzle.split": self._open_split_dialog,
            "search": self._open_search_dialog,
        }
        
        # 查找并调用对应的方法
        if tool_name in tool_map:
            tool_map[tool_name](None)  # 传递 None 作为事件参数
