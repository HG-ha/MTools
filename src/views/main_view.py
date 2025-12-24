# -*- coding: utf-8 -*-
"""主视图模块。

提供应用的主界面，包含导航栏和各功能视图的切换。
"""

import threading
import webbrowser
from typing import Optional

import flet as ft

from components import CustomTitleBar, ToolInfo, ToolSearchDialog
from constants import APP_VERSION, BUILD_CUDA_VARIANT, DOWNLOAD_URL_GITHUB, DOWNLOAD_URL_CHINA
from services import ConfigService, EncodingService, ImageService, FFmpegService, UpdateService, UpdateStatus
from utils.tool_registry import register_all_tools
from utils import get_all_tools


def get_full_version_string() -> str:
    """获取完整的版本字符串（包含 CUDA 变体信息）。
    
    Returns:
        完整版本字符串，例如：
        - "0.0.2-beta" (标准版)
        - "0.0.2-beta (CUDA)" (CUDA版)
        - "0.0.2-beta (CUDA Full)" (CUDA Full版)
    """
    version = APP_VERSION
    
    if BUILD_CUDA_VARIANT == 'cuda':
        return f"{version} (CUDA)"
    elif BUILD_CUDA_VARIANT == 'cuda_full':
        return f"{version} (CUDA Full)"
    else:
        return version
from views.media import MediaView
from views.dev_tools import DevToolsView
from views.others import OthersView
from views.image import ImageView
from views.settings_view import SettingsView
from views.recommendations_view import RecommendationsView


class MainView(ft.Column):
    """主视图类。
    
    提供应用的主界面布局，包含：
    - 自定义标题栏
    - 侧边导航栏
    - 内容区域
    - 功能视图切换
    """

    def __init__(self, page: ft.Page) -> None:
        """初始化主视图。
        
        Args:
            page: Flet页面对象
        """
        super().__init__()
        self.page: ft.Page = page
        self.expand: bool = True
        self.spacing: int = 0
        
        # 创建服务
        self.config_service: ConfigService = ConfigService()
        self.image_service: ImageService = ImageService(self.config_service)
        self.encoding_service: EncodingService = EncodingService()
        self.ffmpeg_service: FFmpegService = FFmpegService(self.config_service)
        
        # 创建自定义标题栏（传递配置服务以保存窗口状态）
        self.title_bar: CustomTitleBar = CustomTitleBar(page, self.config_service)
        
        # 创建内容容器（稍后创建视图时需要）
        self.content_container: Optional[ft.Container] = None
        
        # 创建各功能视图
        self.recommendations_view: Optional[RecommendationsView] = None  # 推荐视图
        self.image_view: Optional[ImageView] = None
        self.dev_tools_view: Optional[DevToolsView] = None
        self.media_view: Optional[MediaView] = None  # 统一的媒体处理视图
        self.others_view: Optional[OthersView] = None
        self.settings_view: SettingsView = SettingsView(page, self.config_service)
        
        # 创建UI组件
        self._build_ui()
        
        # 保存主视图引用到page，供设置视图调用
        self.page._main_view = self
        
        # 保存透明度配置，延迟到页面加载后应用
        self._pending_opacity = self.config_service.get_config_value("window_opacity", 1.0)
        
        # 保存背景图片配置，延迟到页面加载后应用
        self._pending_bg_image = self.config_service.get_config_value("background_image", None)
        self._pending_bg_fit = self.config_service.get_config_value("background_image_fit", "cover")
        
        # 启动时自动检测更新（如果配置允许）
        auto_check_update = self.config_service.get_config_value("auto_check_update", True)
        if auto_check_update:
            self._check_update_on_startup()
        
        # 初始化全局拖放支持（Windows）
        self._init_drop_handler()
    
    def _init_drop_handler(self) -> None:
        """初始化全局文件拖放支持（仅 Windows 10/11）。"""
        from utils import supports_file_drop
        
        if not supports_file_drop():
            return
        
        from utils import WindowsDropHandler
        
        self._drop_handler = WindowsDropHandler(
            page=self.page,
            on_drop=self._on_global_files_dropped,
            auto_enable=True,
            enable_delay=0.1,  # 初始延迟，重试机制会确保可靠性
            include_position=True  # 获取鼠标位置
        )
    
    def _on_global_files_dropped(self, info) -> None:
        """处理全局文件拖放 - 根据鼠标位置分发到对应视图。"""
        from pathlib import Path
        
        if not info.files:
            return
        
        files = [Path(f) for f in info.files]
        drop_x, drop_y = info.x, info.y
        
        def dispatch():
            # 获取当前显示的视图
            current_view = self.content_container.content
            
            # 1. 如果当前视图直接支持 add_files（工具界面）
            if hasattr(current_view, 'add_files'):
                current_view.add_files(files)
                return
            
            # 2. 如果当前视图是分类视图，且有子视图正在显示
            if hasattr(current_view, 'current_sub_view') and current_view.current_sub_view:
                sub_view = current_view.current_sub_view
                if hasattr(sub_view, 'add_files'):
                    sub_view.add_files(files)
                    return
            
            # 3. 如果当前视图支持根据位置处理拖放（分类界面）
            if hasattr(current_view, 'handle_dropped_files_at'):
                current_view.handle_dropped_files_at(files, drop_x, drop_y)
                return
            
            # 备用：显示提示
            self._show_drop_hint("当前页面不支持文件拖放")
        
        self.page.run_thread(dispatch)
    
    def _show_drop_hint(self, message: str) -> None:
        """显示拖放提示。"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检查是否显示推荐工具页面
        show_recommendations = self.config_service.get_config_value("show_recommendations_page", True)
        
        # 构建导航栏目的地
        destinations = []
        
        # 如果启用推荐工具页面，添加到导航栏
        if show_recommendations:
            destinations.append(
                ft.NavigationRailDestination(
                    icon=ft.Icons.LIGHTBULB_OUTLINE,
                    selected_icon=ft.Icons.LIGHTBULB,
                    label="推荐工具",
                )
            )
        
        # 添加其他固定的导航项
        destinations.extend([
            ft.NavigationRailDestination(
                icon=ft.Icons.IMAGE_OUTLINED,
                selected_icon=ft.Icons.IMAGE_ROUNDED,
                label="图片处理",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PERM_MEDIA_OUTLINED,
                selected_icon=ft.Icons.PERM_MEDIA_ROUNDED,
                label="媒体处理",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.DEVELOPER_MODE_OUTLINED,
                selected_icon=ft.Icons.DEVELOPER_MODE_ROUNDED,
                label="开发工具",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.EXTENSION_OUTLINED,
                selected_icon=ft.Icons.EXTENSION_ROUNDED,
                label="其他工具",
            ),
        ])
        
        # 创建导航栏
        self.navigation_rail: ft.NavigationRail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            group_alignment=-0.9,
            expand=True,
            destinations=destinations,
            on_change=self._on_navigation_change,
        )
        
        # 保存是否显示推荐页面的状态
        self.show_recommendations = show_recommendations
        
        # 设置按钮（放在导航栏底部）
        self.settings_button_container: ft.Container = ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.SETTINGS_OUTLINED,
                icon_size=24,
                tooltip="设置",
                on_click=self._open_settings,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(vertical=8),  # 减小垂直padding
            width=100,  # 与导航栏宽度一致
            bgcolor=ft.Colors.TRANSPARENT,  # 设为透明,与导航栏一致
        )
        
        # 导航栏区域（导航栏 + 设置按钮）
        navigation_column: ft.Column = ft.Column(
            controls=[
                self.navigation_rail,
                self.settings_button_container,
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            expand=True,
        )
        
        # 导航栏容器（添加阴影效果，背景半透明以显示背景图）
        self.navigation_container: ft.Container = ft.Container(
            content=navigation_column,
            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.SURFACE),  # 半透明背景
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                offset=ft.Offset(2, 0),
            ),
        )
        
        # 创建内容容器（先创建占位容器，带动画）
        self.content_container = ft.Container(
            expand=True,
            alignment=ft.alignment.top_left,  # 内容从左上角开始
            width=float('inf'),  # 占满可用宽度
            height=float('inf'),  # 占满可用高度
            opacity=1.0,
            animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),  # 250ms 淡入淡出动画
        )
        
        # 注册所有工具（需要在创建视图前注册）
        register_all_tools()
        
        # 创建推荐视图（首页需要立即创建）
        self.recommendations_view = RecommendationsView(
            self.page,
            self.config_service,
            on_tool_click=self._open_tool_by_id,
        )
        
        # 懒加载：主视图在需要时才创建，减少启动内存占用
        # 注意：不再在启动时创建所有视图
        
        # 设置初始内容（如果显示推荐页则使用推荐页，否则按需创建图片处理页）
        show_recommendations = self.config_service.get_config_value("show_recommendations_page", True)
        if show_recommendations:
            self.content_container.content = self.recommendations_view
        else:
            # 按需创建图片视图
            self.image_view = ImageView(
                self.page, 
                self.config_service, 
                self.image_service, 
                self.content_container,
            )
            self.content_container.content = self.image_view
        
        # 注册键盘快捷键
        self.page.on_keyboard_event = self._on_keyboard
        
        # 主内容区域（导航栏 + 内容）
        main_content: ft.Row = ft.Row(
            controls=[
                self.navigation_container,
                self.content_container,
            ],
            spacing=0,
            expand=True,
        )
        
        # 创建悬浮搜索按钮（半透明背景）
        self.fab_search = ft.FloatingActionButton(
            icon=ft.Icons.SEARCH,
            tooltip="搜索工具 (Ctrl+K)",
            on_click=self._open_search,
            bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.PRIMARY),  # 90% 不透明度
            foreground_color=ft.Colors.ON_PRIMARY,
        )
        
        # 组装主视图（标题栏 + 主内容）
        self.controls = [
            self.title_bar,
            main_content,
        ]
        
        # 注意：FAB需要添加到 page.overlay 或 page.floating_action_button
        # 我们将在初始化完成后添加
        self.page.floating_action_button = self.fab_search
    
    def _get_or_create_image_view(self) -> ImageView:
        """获取或创建图片视图（懒加载）。"""
        if self.image_view is None:
            self.image_view = ImageView(
                self.page, 
                self.config_service, 
                self.image_service, 
                self.content_container,
            )
        return self.image_view
    
    def _get_or_create_media_view(self) -> MediaView:
        """获取或创建媒体视图（懒加载）。"""
        if self.media_view is None:
            self.media_view = MediaView(
                self.page, 
                self.config_service, 
                self.content_container,
            )
        return self.media_view
    
    def _get_or_create_dev_tools_view(self) -> DevToolsView:
        """获取或创建开发工具视图（懒加载）。"""
        if self.dev_tools_view is None:
            self.dev_tools_view = DevToolsView(
                self.page, 
                self.config_service, 
                self.encoding_service, 
                self.content_container,
            )
        return self.dev_tools_view
    
    def _get_or_create_others_view(self) -> OthersView:
        """获取或创建其他工具视图（懒加载）。"""
        if self.others_view is None:
            self.others_view = OthersView(
                self.page, 
                self.config_service, 
                self.content_container,
            )
        return self.others_view
    
    def _on_navigation_change(self, e: ft.ControlEvent) -> None:
        """导航变更事件处理。
        
        Args:
            e: 控件事件对象
        """
        selected_index: int = e.control.selected_index
        
        # 标记是否恢复了子视图
        restored = False
        
        # 如果没有显示推荐页面，所有索引需要偏移
        offset = 0 if self.show_recommendations else -1
        
        # 根据选中的索引切换视图（懒加载：按需创建）
        if selected_index == 0 and self.show_recommendations:
            # 推荐
            view = self.recommendations_view
            # 刷新推荐列表（获取最新的使用统计）
            if hasattr(view, 'refresh'):
                view.refresh()
            # 确保内容已设置
            if self.content_container.content != view:
                self.content_container.content = view
        elif selected_index == 1 + offset:
            # 图片处理（懒加载）
            view = self._get_or_create_image_view()
            # 尝试恢复图片处理页面的状态（如果之前在子视图中）
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            # 如果没有恢复子视图，则显示主视图
            if not restored:
                self.content_container.content = view
        elif selected_index == 2 + offset:
            # 媒体处理（懒加载）
            view = self._get_or_create_media_view()
            # 尝试恢复媒体处理页面的状态
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            if not restored:
                self.content_container.content = view
        elif selected_index == 3 + offset:
            # 开发工具（懒加载）
            view = self._get_or_create_dev_tools_view()
            # 尝试恢复开发工具页面的状态
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            if not restored:
                self.content_container.content = view
        elif selected_index == 4 + offset:
            # 其他工具（懒加载）
            view = self._get_or_create_others_view()
            # 尝试恢复其他工具页面的状态
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            if not restored:
                self.content_container.content = view
        else:
            return
        
        # 如果恢复了子视图（在具体工具中），隐藏搜索按钮；否则显示
        if restored:
            self.hide_search_button()
        else:
            self.show_search_button()
        
        # 统一使用page.update()更新整个页面
        if self.page:
            self.page.update()
    
    def _open_tool_by_id(self, tool_id: str) -> None:
        """根据工具ID打开工具。
        
        Args:
            tool_id: 工具ID，格式如 "image.compress", "audio.format"
        """
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool(tool_id)
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 解析工具ID
        parts = tool_id.split(".")
        if len(parts) < 2:
            return
        
        category = parts[0]
        tool_name = ".".join(parts[1:])  # 支持多级，如 "puzzle.merge"
        
        # 计算索引偏移（如果没有推荐页面，索引会减1）
        offset = 0 if self.show_recommendations else -1
        
        # 先切换到对应的分类（使用懒加载获取视图）
        if category == "image":
            self.navigation_rail.selected_index = 1 + offset  # 图片处理
            view = self._get_or_create_image_view()
            self.content_container.content = view
            # 调用图片视图的方法打开子工具
            if hasattr(view, 'open_tool'):
                view.open_tool(tool_name)
        elif category == "audio" or category == "video":
            # 音频和视频都属于媒体处理
            self.navigation_rail.selected_index = 2 + offset  # 媒体处理
            view = self._get_or_create_media_view()
            self.content_container.content = view
            # 媒体视图使用 _open_view 方法
            if hasattr(view, '_open_view'):
                # 根据原始分类和工具名转换为媒体视图的view_name
                if category == "audio":
                    if tool_name == "format":
                        view._open_view('audio_format')
                    elif tool_name == "compress":
                        view._open_view('audio_compress')
                    elif tool_name == "speed":
                        view._open_view('audio_speed')
                    elif tool_name == "vocal_extraction":
                        view._open_view('vocal_extraction')
                    elif tool_name == "to_text":
                        view._open_view('audio_to_text')
                elif category == "video":
                    if tool_name == "compress":
                        view._open_view('video_compress')
                    elif tool_name == "convert":
                        view._open_view('video_convert')
                    elif tool_name == "extract_audio":
                        view._open_view('video_extract_audio')
                    elif tool_name == "repair":
                        view._open_view('video_repair')
                    elif tool_name == "speed":
                        view._open_view('video_speed')
                    elif tool_name == "vocal_separation":
                        view._open_view('video_vocal_separation')
                    elif tool_name == "watermark":
                        view._open_view('video_watermark')
                    elif tool_name == "enhance":
                        view._open_view('video_enhance')
                    elif tool_name == "interpolation":
                        view._open_view('video_interpolation')
                    elif tool_name == "subtitle":
                        view._open_view('video_subtitle')
                    elif tool_name == "subtitle_remove":
                        view._open_view('subtitle_remove')
        elif category == "dev":
            self.navigation_rail.selected_index = 3 + offset  # 开发工具
            view = self._get_or_create_dev_tools_view()
            self.content_container.content = view
            if hasattr(view, 'open_tool'):
                view.open_tool(tool_name)
        elif category == "others":
            self.navigation_rail.selected_index = 4 + offset  # 其他工具
            view = self._get_or_create_others_view()
            self.content_container.content = view
            if hasattr(view, 'open_tool'):
                view.open_tool(tool_name)
        
        # 打开具体工具时隐藏搜索按钮
        self.hide_search_button()
        
        # 使用page.update()而不是单独更新控件
        if self.page:
            self.page.update()
        
        # 注意：从推荐视图传递的待处理文件由各分类视图的 open_tool 方法处理
    
    def _open_search(self, e: ft.ControlEvent = None) -> None:
        """打开搜索对话框。"""
        # 从全局注册表获取工具并转换为ToolInfo
        tools_metadata = get_all_tools()
        tools = []
        for metadata in tools_metadata:
            # 获取图标对象
            icon = getattr(ft.Icons, metadata.icon, ft.Icons.HELP_OUTLINE)
            
            tool_info = ToolInfo(
                name=metadata.name,
                description=metadata.description,
                category=metadata.category,
                keywords=metadata.keywords,
                icon=icon,
                on_click=lambda tid=metadata.tool_id: self._open_tool_by_id(tid),
            )
            tools.append(tool_info)
        
        search_dialog = ToolSearchDialog(self.page, tools, self.config_service)
        self.page.overlay.append(search_dialog)
        search_dialog.open = True
        self.page.update()
    
    def _on_keyboard(self, e: ft.KeyboardEvent) -> None:
        """键盘事件处理。"""
        # Ctrl+K 打开搜索
        if e.key == "K" and e.ctrl and not e.shift and not e.alt:
            self._open_search()
    
    def show_search_button(self) -> None:
        """显示搜索按钮。"""
        if self.fab_search and self.page:
            self.page.floating_action_button = self.fab_search
            self.page.update()
    
    def hide_search_button(self) -> None:
        """隐藏搜索按钮。"""
        if self.page:
            self.page.floating_action_button = None
            self.page.update()
    
    def navigate_to_screen_record(self) -> None:
        """导航到屏幕录制工具（供全局热键调用）。"""
        try:
            # 计算导航索引偏移
            offset = 0 if self.show_recommendations else -1
            
            # 切换到媒体处理视图
            self.navigation_rail.selected_index = 2 + offset
            view = self._get_or_create_media_view()
            self.content_container.content = view
            
            # 打开屏幕录制子视图
            if hasattr(view, '_open_view'):
                view._open_view('screen_record')
            
            # 隐藏搜索按钮
            self.hide_search_button()
            
            if self.page:
                self.page.update()
                
        except Exception as ex:
            from utils import logger
            logger.error(f"导航到屏幕录制失败: {ex}")
    
    def update_recommendations_visibility(self, show: bool) -> None:
        """更新推荐工具页面的显示状态
        
        Args:
            show: 是否显示推荐工具页面
        """
        # 如果状态没有变化，不需要更新
        if self.show_recommendations == show:
            return
        
        # 保存当前选中的索引（处理可能的空值）
        try:
            current_index = self.navigation_rail.selected_index
            if current_index is None:
                current_index = 0
        except (ValueError, TypeError):
            current_index = 0
        
        # 更新状态
        self.show_recommendations = show
        
        # 重建导航栏目的地
        destinations = []
        
        # 如果启用推荐工具页面，添加到导航栏
        if show:
            destinations.append(
                ft.NavigationRailDestination(
                    icon=ft.Icons.LIGHTBULB_OUTLINE,
                    selected_icon=ft.Icons.LIGHTBULB,
                    label="推荐工具",
                )
            )
        
        # 添加其他固定的导航项
        destinations.extend([
            ft.NavigationRailDestination(
                icon=ft.Icons.IMAGE_OUTLINED,
                selected_icon=ft.Icons.IMAGE_ROUNDED,
                label="图片处理",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PERM_MEDIA_OUTLINED,
                selected_icon=ft.Icons.PERM_MEDIA_ROUNDED,
                label="媒体处理",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.DEVELOPER_MODE_OUTLINED,
                selected_icon=ft.Icons.DEVELOPER_MODE_ROUNDED,
                label="开发工具",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.EXTENSION_OUTLINED,
                selected_icon=ft.Icons.EXTENSION_ROUNDED,
                label="其他工具",
            ),
        ])
        
        # 更新导航栏的 destinations
        self.navigation_rail.destinations = destinations
        
        # 调整选中的索引
        # 检查当前是否在设置页面
        is_in_settings = self.content_container.content == self.settings_view
        
        # 更新导航栏内容
        if show and not is_in_settings:
            self.navigation_rail.selected_index = 0
        elif not show and not is_in_settings:
            if current_index == 0:
                self.navigation_rail.selected_index = 0
            elif current_index > 0:
                self.navigation_rail.selected_index = current_index - 1
        
        self.page.update()
        
        # 内容切换
        if show:
            # 显示推荐页面
            if not is_in_settings:
                # 刷新推荐列表
                if hasattr(self.recommendations_view, 'refresh'):
                    self.recommendations_view.refresh()
                self._switch_content_with_animation(self.recommendations_view)
        else:
            # 隐藏推荐页面
            if not is_in_settings and current_index == 0:
                # 使用懒加载获取图片视图
                self._switch_content_with_animation(self._get_or_create_image_view())
    
    def _switch_content_with_animation(self, new_content):
        """带动画切换内容
        
        Args:
            new_content: 新的内容控件
        """
        # 淡出当前内容
        self.content_container.opacity = 0
        self.page.update()
        
        # 使用定时器实现非阻塞动画
        import threading
        def switch_content():
            import time
            time.sleep(0.15)  # 等待淡出动画完成
            self.content_container.content = new_content
            time.sleep(0.05)  # 短暂延迟
            self.content_container.opacity = 1.0
            self.page.update()
        
        timer = threading.Timer(0.001, switch_content)
        timer.daemon = True
        timer.start()
    
    
    def _open_settings(self, e: ft.ControlEvent) -> None:
        """打开设置视图。
        
        Args:
            e: 控件事件对象
        """
        # 取消导航栏的选中状态
        self.navigation_rail.selected_index = None
        
        # 隐藏搜索按钮
        self.hide_search_button()
        
        # 切换到设置视图
        self.content_container.content = self.settings_view
        
        # 使用page.update()而不是单独更新控件
        if self.page:
            self.page.update()
    
    def _check_update_on_startup(self) -> None:
        """启动时在后台检测更新。"""
        def check_task():
            try:
                from utils import logger
                logger.info("[Update] 开始检查更新...")
                
                update_service = UpdateService()
                update_info = update_service.check_update()
                
                logger.info(f"[Update] 检查结果: {update_info.status.value}")
                
                # 只在有新版本时提示
                if update_info.status == UpdateStatus.UPDATE_AVAILABLE:
                    logger.info(f"[Update] 发现新版本: {update_info.latest_version}")
                    # 在主线程中显示更新对话框
                    self._show_update_dialog(update_info)
                elif update_info.status == UpdateStatus.ERROR:
                    logger.warning(f"[Update] 检查更新失败: {update_info.error_message}")
            except Exception as e:
                # 记录错误但不打扰用户
                from utils import logger
                logger.error(f"[Update] 检查更新时发生异常: {e}", exc_info=True)
        
        # 延迟2秒后开始检测，避免影响启动速度
        def delayed_check():
            import time
            time.sleep(2)
            check_task()
        
        thread = threading.Thread(target=delayed_check, daemon=True)
        thread.start()
    
    def _show_update_dialog(self, update_info) -> None:
        """显示更新提示对话框（带自动更新功能）。
        
        Args:
            update_info: 更新信息对象
        """
        from services.auto_updater import AutoUpdater
        import time
        
        # 检查是否跳过了这个版本
        skipped_version = self.config_service.get_config_value("skipped_version", "")
        if skipped_version == update_info.latest_version:
            return  # 用户已选择跳过此版本
        
        # 构建更新日志内容（最多显示500字符）
        release_notes = update_info.release_notes or "暂无更新说明"
        if len(release_notes) > 500:
            release_notes = release_notes[:500] + "..."
        
        # 创建进度条
        progress_bar = ft.ProgressBar(value=0, visible=False)
        progress_text = ft.Text("", size=12, visible=False)
        
        # 创建按钮
        auto_update_btn = ft.ElevatedButton(
            text="立即更新",
            icon=ft.Icons.SYSTEM_UPDATE,
        )
        
        manual_download_btn = ft.OutlinedButton(
            text="手动下载",
            icon=ft.Icons.OPEN_IN_BROWSER,
        )
        
        skip_btn = ft.TextButton(
            text="跳过此版本",
        )
        
        later_btn = ft.TextButton(
            text="稍后提醒",
        )
        
        # 创建对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"🎉 发现新版本 {update_info.latest_version}"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"当前版本: {get_full_version_string()}  →  最新版本: {update_info.latest_version}",
                            size=14,
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Container(height=8),
                        ft.Text("更新内容:", size=13, weight=ft.FontWeight.W_500),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Markdown(
                                        value=release_notes,
                                        selectable=True,
                                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                        on_tap_link=lambda e: webbrowser.open(e.data),
                                    ),
                                ],
                                scroll=ft.ScrollMode.AUTO,
                                expand=True,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                            border_radius=8,
                            padding=12,
                            width=400,
                            height=300,
                        ),
                        ft.Container(height=8),
                        progress_bar,
                        progress_text,
                    ],
                    spacing=4,
                    tight=True,
                ),
                width=420,
            ),
            actions=[
                auto_update_btn,
                manual_download_btn,
                skip_btn,
                later_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        # 定义按钮事件处理
        def on_auto_update(e):
            """自动更新"""
            auto_update_btn.disabled = True
            manual_download_btn.disabled = True
            skip_btn.disabled = True
            later_btn.disabled = True
            
            progress_bar.visible = True
            progress_text.visible = True
            progress_text.value = "正在下载更新..."
            self.page.update()
            
            def update_task():
                try:
                    import asyncio
                    from utils import logger
                    
                    updater = AutoUpdater()
                    
                    def progress_callback(downloaded: int, total: int):
                        if total > 0:
                            progress = downloaded / total
                            progress_bar.value = progress
                            downloaded_mb = downloaded / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            progress_text.value = f"下载中: {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({progress*100:.0f}%)  如果更新失败请尝试管理员权限运行程序"
                            self.page.update()
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    download_path = loop.run_until_complete(
                        updater.download_update(update_info.download_url, progress_callback)
                    )
                    
                    progress_text.value = "正在解压更新..."
                    progress_bar.value = None
                    self.page.update()
                    
                    extract_dir = updater.extract_update(download_path)
                    
                    progress_text.value = "正在应用更新，应用即将重启..."
                    self.page.update()
                    
                    time.sleep(1)
                    
                    # 定义优雅退出回调
                    def exit_callback():
                        """使用标题栏的关闭方法优雅退出"""
                        try:
                            # 使用当前视图的标题栏关闭方法（force=True 强制退出，不最小化到托盘）
                            if hasattr(self, 'title_bar') and self.title_bar:
                                self.title_bar._close_window(None, force=True)
                            else:
                                # 后备：直接关闭窗口
                                self.page.window.close()
                        except Exception as e:
                            logger.warning(f"优雅退出失败: {e}")
                            # 如果失败，让 apply_update 使用强制退出
                            raise
                    
                    updater.apply_update(extract_dir, exit_callback)
                    
                except Exception as ex:
                    logger.error(f"自动更新失败: {ex}")
                    auto_update_btn.disabled = False
                    manual_download_btn.disabled = False
                    skip_btn.disabled = False
                    later_btn.disabled = False
                    progress_bar.visible = False
                    progress_text.value = f"更新失败: {str(ex)}"
                    progress_text.color = ft.Colors.RED
                    progress_text.visible = True
                    self.page.update()
            
            threading.Thread(target=update_task, daemon=True).start()
        
        def on_manual_download(e):
            """手动下载 - 显示下载选项"""
            dialog.open = False
            self.page.update()
            
            # 显示下载选项对话框
            download_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("选择下载方式"),
                content=ft.Text("请选择合适的下载渠道"),
                actions=[
                    ft.FilledButton(
                        "国内镜像（推荐）",
                        icon=ft.Icons.ROCKET_LAUNCH,
                        on_click=lambda _: self._open_china_download(update_info, download_dialog),
                    ),
                    ft.OutlinedButton(
                        "GitHub Release",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=lambda _: self._open_github_download(download_dialog),
                    ),
                    ft.TextButton(
                        "取消",
                        on_click=lambda _: self._close_download_dialog(download_dialog),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            self.page.overlay.append(download_dialog)
            download_dialog.open = True
            self.page.update()
        
        def on_skip(e):
            """跳过此版本"""
            self.config_service.set_config_value("skipped_version", update_info.latest_version)
            dialog.open = False
            self.page.update()
        
        def on_later(e):
            """稍后提醒"""
            dialog.open = False
            self.page.update()
        
        auto_update_btn.on_click = on_auto_update
        manual_download_btn.on_click = on_manual_download
        skip_btn.on_click = on_skip
        later_btn.on_click = on_later
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _open_china_download(self, update_info, dialog):
        """打开国内镜像下载"""
        dialog.open = False
        self.page.update()
        
        version = update_info.latest_version
        if not version.startswith('v'):
            version = f'v{version}'
        url = f"{DOWNLOAD_URL_CHINA}/{version}"
        webbrowser.open(url)
    
    def _open_github_download(self, dialog):
        """打开GitHub下载"""
        dialog.open = False
        self.page.update()
        webbrowser.open(DOWNLOAD_URL_GITHUB)
    
    def _close_download_dialog(self, dialog):
        """关闭下载对话框"""
        dialog.open = False
        self.page.update()
    
    def apply_background(self, image_path: Optional[str], fit_mode: Optional[str]) -> None:
        """应用背景图片到主界面。
        
        Args:
            image_path: 背景图片路径，None表示清除背景
            fit_mode: 图片适应模式 (cover, contain, fill, none)
        """
        if image_path:
            # 转换适应模式
            fit_map = {
                "cover": ft.ImageFit.COVER,
                "contain": ft.ImageFit.CONTAIN,
                "fill": ft.ImageFit.FILL,
                "none": ft.ImageFit.NONE,
            }
            fit = fit_map.get(fit_mode, ft.ImageFit.COVER)
            
            # 创建带背景的Stack
            if not hasattr(self, '_background_stack'):
                # 首次创建背景层
                # 找到main_content (ft.Row)
                old_main_content = None
                for i, control in enumerate(self.controls):
                    if isinstance(control, ft.Row):
                        old_main_content = control
                        self._main_content_index = i
                        break
                
                if old_main_content:
                    # 创建背景图片控件
                    self._background_image_control = ft.Image(
                        src=image_path,
                        fit=fit,
                        opacity=0.20,  # 背景图片透明度(20%),避免影响内容可读性
                        width=float('inf'),  # 占满宽度
                        height=float('inf'),  # 占满高度
                    )
                    
                    # 背景容器,确保填满整个区域
                    self._background_container = ft.Container(
                        content=self._background_image_control,
                        expand=True,
                        alignment=ft.alignment.center,
                    )
                    
                    # 使用Stack层叠布局
                    self._background_stack = ft.Stack(
                        controls=[
                            self._background_container,  # 背景层
                            old_main_content,  # 内容层
                        ],
                        expand=True,
                    )
                    
                    # 替换controls中的main_content为stack
                    self.controls[self._main_content_index] = self._background_stack
                    if self.page:
                        self.page.update()
            else:
                # 更新现有背景图片
                if hasattr(self, '_background_image_control'):
                    self._background_image_control.src = image_path
                    self._background_image_control.fit = fit
                    if self.page:
                        self.page.update()
        else:
            # 清除背景图片
            if hasattr(self, '_background_stack') and hasattr(self, '_main_content_index'):
                # 恢复原始布局
                # 获取内容层（main_content）- 第二个控件
                if len(self._background_stack.controls) >= 2:
                    main_content = self._background_stack.controls[1]
                    
                    # 替换stack为main_content
                    self.controls[self._main_content_index] = main_content
                    
                    # 删除背景相关属性
                    delattr(self, '_background_stack')
                    delattr(self, '_background_image_control')
                    if hasattr(self, '_background_container'):
                        delattr(self, '_background_container')
                    delattr(self, '_main_content_index')
                    
                    if self.page:
                        self.page.update()
