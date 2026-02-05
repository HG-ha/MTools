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
from views.image.watermark_remove_view import ImageWatermarkRemoveView
from views.image.border_view import ImageBorderView


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
        self._page: ft.Page = page
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
        self.watermark_remove_view = None  # 图片去水印视图
        self.search_view = None  # 图片搜索视图
        self.ocr_view = None  # OCR视图
        self.color_space_view = None  # 颜色空间转换视图
        self.border_view = None  # 图片边框视图
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        # 记录当前子视图的类型（用于销毁）
        self.current_sub_view_type: Optional[str] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _safe_page_update(self) -> None:
        """安全地更新页面,处理布局重建后页面引用丢失的情况。"""
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
    
    def _hide_search_button(self) -> None:
        """隐藏主视图的搜索按钮。"""
        if hasattr(self._page, '_main_view'):
            self._page._main_view.hide_search_button()
    
    def _show_search_button(self) -> None:
        """显示主视图的搜索按钮。"""
        if hasattr(self._page, '_main_view'):
            self._page._main_view.show_search_button()
    
    def _on_pin_change(self, tool_id: str, is_pinned: bool) -> None:
        """处理置顶状态变化。"""
        if is_pinned:
            self.config_service.pin_tool(tool_id)
            self._show_snackbar("已置顶到推荐")
        else:
            self.config_service.unpin_tool(tool_id)
            self._show_snackbar("已取消置顶")
        
        # 刷新推荐视图
        if hasattr(self._page, '_main_view') and self._page._main_view.recommendations_view:
            self._page._main_view.recommendations_view.refresh()
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(content=ft.Text(message), duration=2000)
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def _create_card(self, icon, title, description, gradient_colors, on_click, tool_id) -> FeatureCard:
        """创建带置顶功能的卡片。"""
        return FeatureCard(
            icon=icon,
            title=title,
            description=description,
            gradient_colors=gradient_colors,
            on_click=on_click,
            tool_id=tool_id,
            is_pinned=self.config_service.is_tool_pinned(tool_id),
            on_pin_change=self._on_pin_change,
        )
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域 - 自适应布局，确保从左到右、从上到下排列
        feature_cards: ft.Row = ft.Row(
            controls=[
                self._create_card(
                    icon=ft.Icons.COMPRESS_ROUNDED,
                    title="图片压缩",
                    description="专业压缩工具，最高减小80%体积",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_compress_dialog,
                    tool_id="image.compress",
                ),
                self._create_card(
                    icon=ft.Icons.PHOTO_SIZE_SELECT_LARGE_ROUNDED,
                    title="尺寸调整",
                    description="批量调整图片尺寸和分辨率",
                    gradient_colors=("#F093FB", "#F5576C"),
                    on_click=self._open_resize_dialog,
                    tool_id="image.resize",
                ),
                self._create_card(
                    icon=ft.Icons.TRANSFORM_ROUNDED,
                    title="格式转换",
                    description="支持JPG、PNG、WebP等格式互转",
                    gradient_colors=("#4FACFE", "#00F2FE"),
                    on_click=self._open_format_dialog,
                    tool_id="image.format",
                ),
                self._create_card(
                    icon=ft.Icons.AUTO_FIX_HIGH,
                    title="背景移除",
                    description="AI智能抠图，一键去除背景",
                    gradient_colors=("#FA709A", "#FEE140"),
                    on_click=self._open_background_dialog,
                    tool_id="image.background",
                ),
                self._create_card(
                    icon=ft.Icons.AUTO_AWESOME,
                    title="图像增强",
                    description="AI超分辨率，4倍放大清晰化",
                    gradient_colors=("#30CFD0", "#330867"),
                    on_click=self._open_enhance_dialog,
                    tool_id="image.enhance",
                ),
                self._create_card(
                    icon=ft.Icons.GRID_ON,
                    title="单图切分",
                    description="单图切分为九宫格，可设置间距",
                    gradient_colors=("#FF6B6B", "#FFE66D"),
                    on_click=self._open_split_dialog,
                    tool_id="image.puzzle.split",
                ),
                self._create_card(
                    icon=ft.Icons.VIEW_MODULE,
                    title="多图拼接",
                    description="横向、纵向、网格拼接图片",
                    gradient_colors=("#4ECDC4", "#44A08D"),
                    on_click=self._open_merge_dialog,
                    tool_id="image.puzzle.merge",
                ),
                self._create_card(
                    icon=ft.Icons.CROP,
                    title="图片裁剪",
                    description="可视化裁剪，实时预览效果",
                    gradient_colors=("#A8EDEA", "#FED6E3"),
                    on_click=self._open_crop_dialog,
                    tool_id="image.crop",
                ),
                self._create_card(
                    icon=ft.Icons.INFO,
                    title="图片信息",
                    description="查看图片详细信息和EXIF数据",
                    gradient_colors=("#FFA8A8", "#FCFF82"),
                    on_click=self._open_info_dialog,
                    tool_id="image.info",
                ),
                self._create_card(
                    icon=ft.Icons.GIF_BOX,
                    title="GIF/Live Photo 编辑",
                    description="调整 GIF / 实况图的速度、循环等参数，支持导出为视频",
                    gradient_colors=("#FF9A9E", "#FAD0C4"),
                    on_click=self._open_gif_adjustment_dialog,
                    tool_id="image.gif",
                ),
                self._create_card(
                    icon=ft.Icons.CODE,
                    title="图片转Base64",
                    description="将图片转换为Base64编码，支持Data URI格式",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_to_base64_dialog,
                    tool_id="image.to_base64",
                ),
                self._create_card(
                    icon=ft.Icons.ROTATE_90_DEGREES_CCW,
                    title="旋转/翻转",
                    description="支持GIF动图、实时预览、自定义角度、批量处理",
                    gradient_colors=("#F77062", "#FE5196"),
                    on_click=self._open_rotate_dialog,
                    tool_id="image.rotate",
                ),
                self._create_card(
                    icon=ft.Icons.SECURITY,
                    title="去除EXIF",
                    description="删除图片元数据，保护隐私",
                    gradient_colors=("#C471F5", "#FA71CD"),
                    on_click=self._open_remove_exif_dialog,
                    tool_id="image.exif",
                ),
                self._create_card(
                    icon=ft.Icons.QR_CODE_2,
                    title="二维码生成",
                    description="生成二维码，支持自定义样式",
                    gradient_colors=("#20E2D7", "#F9FEA5"),
                    on_click=self._open_qrcode_dialog,
                    tool_id="image.qrcode",
                ),
                self._create_card(
                    icon=ft.Icons.BRANDING_WATERMARK,
                    title="添加水印",
                    description="支持单个水印和全屏平铺水印，批量处理，实时预览",
                    gradient_colors=("#FF6FD8", "#3813C2"),
                    on_click=self._open_watermark_dialog,
                    tool_id="image.watermark",
                ),
                self._create_card(
                    icon=ft.Icons.AUTO_FIX_HIGH,
                    title="去水印",
                    description="AI智能去除图片水印，支持自定义区域",
                    gradient_colors=("#11998E", "#38EF7D"),
                    on_click=self._open_watermark_remove_dialog,
                    tool_id="image.watermark_remove",
                ),
                self._create_card(
                    icon=ft.Icons.IMAGE_SEARCH,
                    title="图片搜索",
                    description="以图搜图，搜索相似图片",
                    gradient_colors=("#FFA726", "#FB8C00"),
                    on_click=self._open_search_dialog,
                    tool_id="image.search",
                ),
                self._create_card(
                    icon=ft.Icons.TEXT_FIELDS,
                    title="OCR 文字识别",
                    description="AI识别图片中的文字，支持中英文",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=self._open_ocr_dialog,
                    tool_id="image.ocr",
                ),
                self._create_card(
                    icon=ft.Icons.COLOR_LENS,
                    title="颜色空间转换",
                    description="批量转换图片颜色空间，灰度、反色、复古等",
                    gradient_colors=("#00B4DB", "#0083B0"),
                    on_click=self._open_color_space_dialog,
                    tool_id="image.color_space",
                ),
                self._create_card(
                    icon=ft.Icons.BORDER_ALL,
                    title="图片边框",
                    description="添加边框，支持圆角、透明、按百分比设置",
                    gradient_colors=("#8E2DE2", "#4A00E0"),
                    on_click=self._open_border_dialog,
                    tool_id="image.border",
                ),
            ],
            wrap=True,  # 自动换行
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,  # 从左开始排列
            vertical_alignment=ft.CrossAxisAlignment.START,  # 从上开始排列
        )
        
        # 滚动偏移量跟踪
        self._scroll_offset_y = 0.0
        
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
            on_scroll=self._on_scroll,  # 跟踪滚动位置
        )
        
        # 初始化工具拖放映射（工具名、支持的格式、打开方法、视图属性名）
        # 通用图片格式
        _img_exts = {'.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.ico', '.avif', '.heic', '.heif'}
        _img_no_gif = {'.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', '.tiff', '.tif', '.ico', '.avif', '.heic', '.heif'}
        
        self._drop_tool_map = [
            ("图片压缩", _img_exts, self._open_compress_dialog, "compress_view"),
            ("尺寸调整", _img_exts, self._open_resize_dialog, "resize_view"),
            ("格式转换", _img_exts, self._open_format_dialog, "format_view"),
            ("背景移除", _img_no_gif, self._open_background_dialog, "background_view"),
            ("图像增强", _img_no_gif, self._open_enhance_dialog, "enhance_view"),
            ("单图切分", _img_no_gif, self._open_split_dialog, "split_view"),
            ("多图拼接", _img_no_gif, self._open_merge_dialog, "merge_view"),
            ("图片裁剪", _img_no_gif, self._open_crop_dialog, "crop_view"),
            ("图片信息", _img_exts, self._open_info_dialog, "info_view"),
            ("GIF/Live Photo 编辑", {'.gif', '.mov', '.mp4'}, self._open_gif_adjustment_dialog, "gif_adjustment_view"),
            ("图片转Base64", _img_exts, self._open_to_base64_dialog, "to_base64_view"),
            ("旋转/翻转", _img_exts, self._open_rotate_dialog, "rotate_view"),
            ("去除EXIF", {'.jpg', '.jpeg', '.png', '.tiff'}, self._open_remove_exif_dialog, "remove_exif_view"),
            ("二维码生成", set(), None, None),  # 不接受拖放文件
            ("添加水印", _img_no_gif, self._open_watermark_dialog, "watermark_view"),
            ("去水印", _img_no_gif, self._open_watermark_remove_dialog, "watermark_remove_view"),
            ("图片搜索", _img_exts, self._open_search_dialog, "search_view"),
            ("OCR 文字识别", _img_no_gif, self._open_ocr_dialog, "ocr_view"),
            ("颜色空间转换", _img_no_gif, self._open_color_space_dialog, "color_space_view"),
            ("图片边框", _img_exts, self._open_border_dialog, "border_view"),
        ]
        
        # 卡片布局参数（需要与 FeatureCard 的实际尺寸匹配）
        # FeatureCard: width=280, height=220, margin=only(left=5, right=0, top=5, bottom=10)
        # Row: spacing=PADDING_LARGE(24), run_spacing=PADDING_LARGE(24)
        self._card_margin_left = 5
        self._card_margin_top = 5
        self._card_margin_bottom = 10
        self._card_width = 280   # FeatureCard.width
        self._card_height = 220  # FeatureCard.height
        # 卡片间的实际步进距离：margin_left + width + margin_right + spacing
        self._card_step_x = self._card_margin_left + self._card_width + 0 + PADDING_LARGE  # 5+280+0+24=309
        self._card_step_y = self._card_margin_top + self._card_height + self._card_margin_bottom + PADDING_LARGE  # 5+220+10+24=259
        self._content_padding = PADDING_MEDIUM
    
    def handle_dropped_files_at(self, files: list, x: int, y: int) -> None:
        """处理拖放到指定位置的文件。
        
        Args:
            files: 文件路径列表（Path 对象）
            x: 鼠标 X 坐标（相对于窗口客户区）
            y: 鼠标 Y 坐标（相对于窗口客户区）
        """
        # 如果当前显示的是子视图，让子视图处理
        if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
            self.current_sub_view.add_files(files)
            return
        
        # 计算点击的是哪个工具卡片
        # 注意：需要考虑导航栏宽度和标题栏高度
        nav_width = 100  # 导航栏宽度
        title_height = 32  # 自定义标题栏高度
        
        # 调整坐标（减去导航栏、标题栏和内容padding，加上滚动偏移量）
        local_x = x - nav_width - self._content_padding
        local_y = y - title_height - self._content_padding + self._scroll_offset_y
        
        
        if local_x < 0 or local_y < 0:
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        # 计算行列（考虑卡片的 margin 和 spacing）
        col = int(local_x // self._card_step_x)
        row = int(local_y // self._card_step_y)
        
        # 根据实际窗口宽度计算每行卡片数
        window_width = self._page.window.width or 1000
        content_width = window_width - nav_width - self._content_padding * 2
        cols_per_row = max(1, int(content_width // self._card_step_x))
        
        index = row * cols_per_row + col
        
        if index < 0 or index >= len(self._drop_tool_map):
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        tool_name, supported_exts, open_func, view_attr = self._drop_tool_map[index]
        
        if not supported_exts or not open_func:
            self._show_snackbar(f"「{tool_name}」不支持文件拖放")
            return
        
        # 展开文件夹（只获取顶级目录下的文件）
        all_files = []
        for f in files:
            if f.is_dir():
                for item in f.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(f)
        
        # 过滤出支持的文件
        supported_files = [f for f in all_files if f.suffix.lower() in supported_exts]
        
        if not supported_files:
            self._show_snackbar(f"「{tool_name}」不支持该格式")
            return
        
        # 保存待处理的文件
        self._pending_drop_files = supported_files
        self._pending_view_attr = view_attr
        
        # 打开工具
        open_func(None)
        
        # 导入文件到工具
        self._import_pending_files()
    
    def _import_pending_files(self) -> None:
        """将待处理文件导入到当前工具视图。"""
        if not hasattr(self, '_pending_drop_files') or not self._pending_drop_files:
            return
        
        view_attr = getattr(self, '_pending_view_attr', None)
        pending_files = self._pending_drop_files
        
        # 清空待处理状态
        self._pending_drop_files = []
        self._pending_view_attr = None
        
        if not view_attr:
            return
        
        def delayed_import():
            """延迟导入，等待视图创建完成（某些视图使用 Timer 延迟创建）"""
            import time
            max_wait = 1.0  # 最多等待1秒
            wait_interval = 0.05  # 每50ms检查一次
            waited = 0
            
            while waited < max_wait:
                view = getattr(self, view_attr, None)
                if view and hasattr(view, 'add_files'):
                    view.add_files(pending_files)
                    return
                time.sleep(wait_interval)
                waited += wait_interval
        
        # 在后台线程中执行延迟导入
        import threading
        threading.Thread(target=delayed_import, daemon=True).start()
    
    def _on_scroll(self, e: ft.OnScrollEvent) -> None:
        """跟踪滚动位置。"""
        self._scroll_offset_y = e.pixels
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            duration=3000,
        )
        self._saved_page.overlay.append(snackbar)
        snackbar.open = True
        self._saved_page.update()
    
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
    
    def _open_watermark_remove_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片去水印工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建图片去水印视图（如果还没创建）
        if not self.watermark_remove_view:
            self.watermark_remove_view = ImageWatermarkRemoveView(
                self._saved_page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.watermark_remove_view
        self.current_sub_view_type = "watermark_remove"
        
        # 切换到图片去水印视图
        self.parent_container.content = self.watermark_remove_view
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
    
    def _open_ocr_dialog(self, e: ft.ControlEvent) -> None:
        """切换到OCR工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建OCR视图（如果还没创建）
        if not self.ocr_view:
            from views.image.ocr_view import OCRView
            self.ocr_view = OCRView(
                self._saved_page,
                self.config_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.ocr_view
        self.current_sub_view_type = "ocr"
        
        # 切换到OCR视图
        self.parent_container.content = self.ocr_view
        self._safe_page_update()
    
    def _open_color_space_dialog(self, e: ft.ControlEvent) -> None:
        """切换到颜色空间转换工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建颜色空间转换视图（如果还没创建）
        if not self.color_space_view:
            from views.image.color_space_view import ColorSpaceView
            self.color_space_view = ColorSpaceView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.color_space_view
        self.current_sub_view_type = "color_space"
        
        # 切换到颜色空间转换视图
        self.parent_container.content = self.color_space_view
        self._safe_page_update()
    
    def _open_border_dialog(self, e: ft.ControlEvent) -> None:
        """切换到图片边框工具界面。
        
        Args:
            e: 控件事件对象
        """
        if not self.parent_container:
            logger.error("错误: 未设置父容器")
            return
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        # 创建图片边框视图（如果还没创建）
        if not self.border_view:
            self.border_view = ImageBorderView(
                self._saved_page,
                self.config_service,
                self.image_service,
                on_back=self._back_to_main
            )
        
        # 记录当前子视图
        self.current_sub_view = self.border_view
        self.current_sub_view_type = "border"
        
        # 切换到图片边框视图
        self.parent_container.content = self.border_view
        self._safe_page_update()
    
    def _back_to_main(self, e: ft.ControlEvent = None) -> None:
        """返回主界面（使用路由导航）。
        
        Args:
            e: 控件事件对象（可选）
        """
        import gc
        
        # 销毁当前子视图
        if self.current_sub_view_type:
            view_map = {
                "compress": "compress_view",
                "resize": "resize_view",
                "format": "format_view",
                "background": "background_view",
                "enhance": "enhance_view",
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
                "watermark_remove": "watermark_remove_view",
                "search": "search_view",
                "ocr": "ocr_view",
                "color_space": "color_space_view",
                "border": "border_view",
                "image_tools_install": "image_tools_install_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                view_instance = getattr(self, view_attr, None)
                if view_instance:
                    # 统一调用 cleanup 方法（每个视图自己负责清理资源和卸载模型）
                    if hasattr(view_instance, 'cleanup'):
                        try:
                            view_instance.cleanup()
                        except Exception as ex:
                            logger.warning(f"清理视图资源失败: {ex}")
                # 清空引用
                setattr(self, view_attr, None)
        
        # 清除子视图状态
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        # 强制垃圾回收释放内存
        gc.collect()
        
        # 直接恢复主界面（不依赖路由，因为打开工具时也是直接切换内容的）
        if self.parent_container:
            self.parent_container.content = self
            self._show_search_button()
            self._safe_page_update()
    
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
        # tool_name 到 current_sub_view_type 的映射（处理不一致的命名）
        tool_to_view_type = {
            "gif": "gif_adjustment",
            "exif": "remove_exif",
            "puzzle.merge": "merge",
            "puzzle.split": "split",
        }
        expected_view_type = tool_to_view_type.get(tool_name, tool_name)
        
        # 如果当前已经打开了该工具，直接返回现有视图，不创建新实例
        if self.current_sub_view_type == expected_view_type and self.current_sub_view is not None:
            # 确保当前视图显示在容器中
            if self.parent_container and self.parent_container.content != self.current_sub_view:
                self.parent_container.content = self.current_sub_view
                self._safe_page_update()
            return
        
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
            "watermark_remove": self._open_watermark_remove_dialog,
            "info": self._open_info_dialog,
            "exif": self._open_remove_exif_dialog,
            "qrcode": self._open_qrcode_dialog,
            "to_base64": self._open_to_base64_dialog,
            "gif": self._open_gif_adjustment_dialog,
            "puzzle.merge": self._open_merge_dialog,
            "puzzle.split": self._open_split_dialog,
            "search": self._open_search_dialog,
            "ocr": self._open_ocr_dialog,
            "enhance": self._open_enhance_dialog,
            "color_space": self._open_color_space_dialog,
            "border": self._open_border_dialog,
        }
        
        # 查找并调用对应的方法
        if tool_name in tool_map:
            tool_map[tool_name](None)  # 传递 None 作为事件参数
            
            # 处理从推荐视图传递的待处理文件
            if hasattr(self._saved_page, '_pending_drop_files') and self._saved_page._pending_drop_files:
                pending_files = self._saved_page._pending_drop_files
                self._saved_page._pending_drop_files = None
                self._saved_page._pending_tool_id = None
                
                # 让当前子视图处理文件
                if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
                    self.current_sub_view.add_files(pending_files)