# -*- coding: utf-8 -*-
"""主视图模块。

提供应用的主界面，包含导航栏和各功能视图的切换。
"""

import threading
import webbrowser
from typing import Optional, TYPE_CHECKING

import flet as ft

import flet_dropzone as ftd  # type: ignore[import-untyped]

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
if TYPE_CHECKING:
    from views.media.media_view import MediaView
    from views.dev_tools.dev_tools_view import DevToolsView
    from views.others.others_view import OthersView
    from views.image.image_view import ImageView
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
        self._page: ft.Page = page  # Flet 1.0: page 是只读属性，用 _page 存储
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
        self.recommendations_view: Optional["RecommendationsView"] = None  # 推荐视图
        self.image_view: Optional["ImageView"] = None
        self.dev_tools_view: Optional["DevToolsView"] = None
        self.media_view: Optional["MediaView"] = None  # 统一的媒体处理视图
        self.others_view: Optional["OthersView"] = None
        self.settings_view: Optional["SettingsView"] = None  # 懒加载，首次打开时创建
        
        # 创建UI组件
        self._build_ui()
        
        # 保存主视图引用到page，供设置视图调用
        self._page._main_view = self
        
        # 关闭标记：防止关闭过程中后台任务继续操作 page
        self._is_closing: bool = False
        
        # 保存透明度配置，延迟到页面加载后应用
        self._pending_opacity = self.config_service.get_config_value("window_opacity", 1.0)
        
        # 保存背景图片配置，延迟到页面加载后应用
        self._pending_bg_image = self.config_service.get_config_value("background_image", None)
        self._pending_bg_fit = self.config_service.get_config_value("background_image_fit", "cover")
        
        # 路由打开任务序号：用于取消过期的异步打开请求
        self._route_open_ticket: int = 0
        
        # 启动时自动检测更新（如果配置允许）
        auto_check_update = self.config_service.get_config_value("auto_check_update", True)
        if auto_check_update:
            self._check_update_on_startup()
        
    def _on_files_dropped(self, e) -> None:
        """处理 flet-dropzone 拖放事件 - 分发文件到当前视图。"""
        from pathlib import Path
        from utils import logger
        
        logger.info(f"Dropzone: on_dropped 触发, event={e}")
        logger.info(f"Dropzone: e.files={getattr(e, 'files', 'N/A')}, e.data={getattr(e, 'data', 'N/A')}")
        
        files_list = getattr(e, 'files', None) or []
        if not files_list:
            logger.warning("Dropzone: 没有收到文件")
            return
        
        files = [Path(f) for f in files_list]
        logger.info(f"Dropzone: 收到 {len(files)} 个文件: {files}")
        
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
            
            # 备用：显示提示
            self._show_drop_hint("当前页面不支持文件拖放")
        
        self._page.run_thread(dispatch)
    
    def _show_drop_hint(self, message: str) -> None:
        """显示拖放提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000,
        )
        self._page.show_dialog(snackbar)
    
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
            bgcolor=ft.Colors.TRANSPARENT,
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
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(vertical=8),  # 减小垂直padding
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
            bgcolor=ft.Colors.with_opacity(1.0, ft.Colors.SURFACE),
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
            alignment=ft.Alignment.TOP_LEFT,  # 内容从左上角开始
            width=float('inf'),  # 占满可用宽度
            height=float('inf'),  # 占满可用高度
            opacity=1.0,
            animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),  # 250ms 淡入淡出动画
        )
        
        # 注册所有工具（需要在创建视图前注册）
        register_all_tools()
        
        # 创建推荐视图（首页需要立即创建）
        from views.recommendations_view import RecommendationsView

        self.recommendations_view = RecommendationsView(
            self._page,
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
            from views.image.image_view import ImageView

            self.image_view = ImageView(
                self._page, 
                self.config_service, 
                self.image_service, 
                self.content_container,
            )
            self.content_container.content = self.image_view
        
        # 注册键盘快捷键
        self._page.on_keyboard_event = self._on_keyboard
        
        # 用 flet-dropzone 包裹内容区域以支持文件拖放（需要 flet build）
        self.dropzone_wrapper = ftd.Dropzone(
            content=self.content_container,
            on_dropped=self._on_files_dropped,
            expand=True,
        )
        # 设置页常驻层：切换设置时仅显隐，减少大组件树反复替换造成的卡顿
        self.settings_layer = ft.Container(
            visible=False,
            expand=True,
        )
        self.content_stack = ft.Stack(
            controls=[
                self.dropzone_wrapper,
                self.settings_layer,
            ],
            expand=True,
        )
        self.content_bg = ft.Container(
            content=self.content_stack,
            expand=True,
        )
        content_area = self.content_bg
        
        # 主内容区域（导航栏 + 内容）
        main_content: ft.Row = ft.Row(
            controls=[
                self.navigation_container,
                content_area,
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
        
        # 通过 overlay 挂载 FAB，避免 Flet 0.84 page.floating_action_button diff bug
        # (FloatingActionButton 实例无 floating_action_button 属性导致 AttributeError)
        self.fab_search.bottom = 16
        self.fab_search.right = 16
        self._page.overlay.append(self.fab_search)
        
        # 共享 FilePicker：Flet 0.84 中 FilePicker 是 Service，需注册到 page.services
        shared_fp = ft.FilePicker()
        self._page.services.append(shared_fp)
        self._page._shared_file_picker = shared_fp
    
    def _get_or_create_image_view(self) -> "ImageView":
        """获取或创建图片视图（懒加载）。"""
        if self.image_view is None:
            from views.image.image_view import ImageView

            self.image_view = ImageView(
                self._page, 
                self.config_service, 
                self.image_service, 
                self.content_container,
            )
        return self.image_view
    
    def _get_or_create_media_view(self) -> "MediaView":
        """获取或创建媒体视图（懒加载）。"""
        if self.media_view is None:
            from views.media.media_view import MediaView

            self.media_view = MediaView(
                self._page, 
                self.config_service, 
                self.content_container,
            )
        return self.media_view
    
    def _get_or_create_dev_tools_view(self) -> "DevToolsView":
        """获取或创建开发工具视图（懒加载）。"""
        if self.dev_tools_view is None:
            from views.dev_tools.dev_tools_view import DevToolsView

            self.dev_tools_view = DevToolsView(
                self._page, 
                self.config_service, 
                self.encoding_service, 
                self.content_container,
            )
        return self.dev_tools_view
    
    def _get_or_create_others_view(self) -> "OthersView":
        """获取或创建其他工具视图（懒加载）。"""
        if self.others_view is None:
            from views.others.others_view import OthersView

            self.others_view = OthersView(
                self._page, 
                self.config_service, 
                self.content_container,
            )
        return self.others_view
    
    def _safe_go(self, route: str) -> None:
        """安全的路由跳转，关闭过程中不再操作 page。"""
        if self._is_closing:
            return
        
        async def _push():
            try:
                await self._page.push_route(route)
            except RuntimeError:
                pass  # Session closed
        
        self._page.run_task(_push)
    
    def _show_route_loading(self, title: str) -> None:
        """显示路由级加载占位，降低切换时的卡顿感。"""
        self._hide_settings_layer()
        self.content_container.content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(width=28, height=28, stroke_width=3),
                    ft.Text(title),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
        self._page.update()
    
    def _schedule_route_open(self, route: str, ticket: int, loading_title: str, open_fn) -> None:
        """异步执行工具打开，允许路由快速切换时取消过期请求。"""
        self._show_route_loading(loading_title)
        
        async def open_later():
            import asyncio
            await asyncio.sleep(0.03)  # 先让 loading 帧渲染出来
            if self._is_closing:
                return
            if ticket != self._route_open_ticket:
                return
            if self._page.route != route:
                return
            open_fn()
        
        self._page.run_task(open_later)
    
    def _open_settings_view(self) -> None:
        """打开设置页面。"""
        if self.settings_view is None:
            from views.settings_view import SettingsView
            self.settings_view = SettingsView(self._page, self.config_service)
        self._show_settings_layer()
        self._page.update()
    
    def _show_settings_layer(self) -> None:
        """显示设置常驻层。"""
        if self.settings_view is None:
            return
        # 延迟挂载：仅在进入设置页时把大组件树挂回页面
        self.settings_layer.content = self.settings_view
        self.settings_layer.visible = True
        self.dropzone_wrapper.visible = False
    
    def _hide_settings_layer(self) -> None:
        """隐藏设置常驻层并显示主内容层。"""
        self.settings_layer.visible = False
        # 卸载设置层内容，避免后续任意 page.update 都遍历巨大设置组件树
        self.settings_layer.content = None
        self.dropzone_wrapper.visible = True
    
    def handle_route_change(self, route: str) -> None:
        """处理路由变更。
        
        Args:
            route: 路由路径，如 "/", "/image", "/media", "/image/compress" 等
        
        注意：为了兼容桌面应用，不使用 page.views 栈，
        而是直接更新 content_container 的内容。
        这样可以避免 Flet 路由系统导致的 page 引用丢失问题。
        """
        # 使用保存的页面引用
        page = self._page
        if not page or self._is_closing:
            return
        
        # 防止重复处理相同路由
        if hasattr(self, '_last_route') and self._last_route == route:
            return
        self._last_route = route
        
        # 新路由到来，递增任务序号，取消之前未执行的打开任务
        self._route_open_ticket += 1
        current_ticket = self._route_open_ticket
        
        # 解析路由
        parts = route.strip("/").split("/") if route.strip("/") else []
        if not parts or parts[0] != "settings":
            self._hide_settings_layer()
        
        # 根据路由路径确定要显示的内容和导航栏选中项
        if not parts or parts[0] == "":
            # 根路径 "/" - 推荐页
            if self.show_recommendations:
                self.content_container.content = self.recommendations_view
                self.navigation_rail.selected_index = 0
                self.show_search_button(update=False)
                # 刷新推荐列表
                if hasattr(self.recommendations_view, 'refresh'):
                    self.recommendations_view.refresh()
            else:
                # 如果不显示推荐页，重定向到图片处理
                self._last_route = None  # 清除记录，允许重定向
                self._safe_go("/image")
                return
        
        elif parts[0] == "image":
            # 图片处理路由
            offset = 0 if self.show_recommendations else -1
            self.navigation_rail.selected_index = 1 + offset
            
            view = self._get_or_create_image_view()
            
            if len(parts) == 1:
                # 只有 "/image"，尝试恢复之前的工具子视图
                if hasattr(view, 'current_sub_view') and view.current_sub_view:
                    # 有之前打开的工具，恢复它
                    self.content_container.content = view.current_sub_view
                    self.hide_search_button(update=False)
                else:
                    # 没有之前打开的工具，显示主视图
                    self.content_container.content = view
                    self.show_search_button(update=False)
            else:
                # 有子路径，如 "/image/compress"
                tool_name = "/".join(parts[1:])
                if hasattr(view, 'open_tool'):
                    self._schedule_route_open(
                        route=route,
                        ticket=current_ticket,
                        loading_title=f"正在打开图片工具: {tool_name}",
                        open_fn=lambda: view.open_tool(tool_name),
                    )
                self.hide_search_button(update=False)
        
        elif parts[0] == "media":
            # 媒体处理路由
            offset = 0 if self.show_recommendations else -1
            self.navigation_rail.selected_index = 2 + offset
            
            view = self._get_or_create_media_view()
            
            if len(parts) == 1:
                # 只有 "/media"，尝试恢复之前的工具子视图
                if hasattr(view, 'current_sub_view') and view.current_sub_view:
                    # 有之前打开的工具，恢复它
                    self.content_container.content = view.current_sub_view
                    self.hide_search_button(update=False)
                else:
                    # 没有之前打开的工具，显示主视图
                    self.content_container.content = view
                    self.show_search_button(update=False)
            else:
                # 有子路径，如 "/media/video_compress"
                sub_view_name = parts[1]
                if hasattr(view, '_open_view'):
                    self._schedule_route_open(
                        route=route,
                        ticket=current_ticket,
                        loading_title=f"正在打开媒体工具: {sub_view_name}",
                        open_fn=lambda: view._open_view(sub_view_name),
                    )
                self.hide_search_button(update=False)
        
        elif parts[0] == "dev":
            # 开发工具路由
            offset = 0 if self.show_recommendations else -1
            self.navigation_rail.selected_index = 3 + offset
            
            view = self._get_or_create_dev_tools_view()
            
            if len(parts) == 1:
                # 只有 "/dev"，尝试恢复之前的工具子视图
                if hasattr(view, 'current_sub_view') and view.current_sub_view:
                    # 有之前打开的工具，恢复它
                    self.content_container.content = view.current_sub_view
                    self.hide_search_button(update=False)
                else:
                    # 没有之前打开的工具，显示主视图
                    self.content_container.content = view
                    self.show_search_button(update=False)
            else:
                # 有子路径，如 "/dev/json_viewer"
                tool_name = "/".join(parts[1:])
                if hasattr(view, 'open_tool'):
                    self._schedule_route_open(
                        route=route,
                        ticket=current_ticket,
                        loading_title=f"正在打开开发工具: {tool_name}",
                        open_fn=lambda: view.open_tool(tool_name),
                    )
                self.hide_search_button(update=False)
        
        elif parts[0] == "others":
            # 其他工具路由
            offset = 0 if self.show_recommendations else -1
            self.navigation_rail.selected_index = 4 + offset
            
            view = self._get_or_create_others_view()
            
            if len(parts) == 1:
                # 只有 "/others"，尝试恢复之前的工具子视图
                if hasattr(view, 'current_sub_view') and view.current_sub_view:
                    # 有之前打开的工具，恢复它
                    self.content_container.content = view.current_sub_view
                    self.hide_search_button(update=False)
                else:
                    # 没有之前打开的工具，显示主视图
                    self.content_container.content = view
                    self.show_search_button(update=False)
            else:
                # 有子路径，如 "/others/weather"
                tool_name = "/".join(parts[1:])
                if hasattr(view, 'open_tool'):
                    self._schedule_route_open(
                        route=route,
                        ticket=current_ticket,
                        loading_title=f"正在打开其他工具: {tool_name}",
                        open_fn=lambda: view.open_tool(tool_name),
                    )
                self.hide_search_button(update=False)
        
        elif parts[0] == "settings":
            # 设置页面路由（懒加载）
            self.navigation_rail.selected_index = None
            self.hide_search_button(update=False)
            if self.settings_view is None:
                self._schedule_route_open(
                    route=route,
                    ticket=current_ticket,
                    loading_title="正在打开设置...",
                    open_fn=self._open_settings_view,
                )
            else:
                self._show_settings_layer()
        
        else:
            # 未知路由，重定向到首页
            self._last_route = None  # 清除记录，允许重定向
            if self.show_recommendations:
                self._safe_go("/")
            else:
                self._safe_go("/image")
            return
        
        # 更新页面
        page.update()
    
    def _on_navigation_change(self, e: ft.ControlEvent) -> None:
        """导航变更事件处理（使用路由系统）。
        
        Args:
            e: 控件事件对象
        """
        selected_index: int = e.control.selected_index
        
        # 使用保存的页面引用
        page = self._page
        if not page:
            return
        
        # 如果当前在设置页，先立即卸载设置层的巨大控件树，
        # 避免 Flet 自动 page.update() 时序列化整棵设置树导致卡顿
        if self.settings_layer.visible:
            self._hide_settings_layer()
        
        # 如果没有显示推荐页面，所有索引需要偏移
        offset = 0 if self.show_recommendations else -1
        
        # 根据选中的索引导航到对应路由
        if selected_index == 0 and self.show_recommendations:
            # 推荐页
            self._safe_go("/")
        elif selected_index == 1 + offset:
            # 图片处理
            self._safe_go("/image")
        elif selected_index == 2 + offset:
            # 媒体处理
            self._safe_go("/media")
        elif selected_index == 3 + offset:
            # 开发工具
            self._safe_go("/dev")
        elif selected_index == 4 + offset:
            # 其他工具
            self._safe_go("/others")
    
    def _open_tool_by_id(self, tool_id: str) -> None:
        """根据工具ID打开工具（使用路由导航）。
        
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
        
        # 使用保存的页面引用
        page = self._page
        if not page:
            return
        
        # 保存待处理的文件（如果有）
        if hasattr(page, '_pending_drop_files'):
            # 待处理文件会在路由处理时被对应视图处理
            pass
        
        # 根据分类构建路由路径
        if category == "image":
            self._safe_go(f"/image/{tool_name}")
        elif category == "audio":
            # 音频工具映射到媒体视图的子路径
            audio_tool_map = {
                "format": "audio_format",
                "compress": "audio_compress",
                "speed": "audio_speed",
                "vocal_extraction": "vocal_extraction",
                "to_text": "audio_to_text",
            }
            sub_view = audio_tool_map.get(tool_name, tool_name)
            self._safe_go(f"/media/{sub_view}")
        elif category == "video":
            # 视频工具映射到媒体视图的子路径
            video_tool_map = {
                "compress": "video_compress",
                "convert": "video_convert",
                "extract_audio": "video_extract_audio",
                "repair": "video_repair",
                "speed": "video_speed",
                "vocal_separation": "video_vocal_separation",
                "watermark": "video_watermark",
                "enhance": "video_enhance",
                "interpolation": "video_interpolation",
                "subtitle": "video_subtitle",
                "subtitle_remove": "subtitle_remove",
            }
            sub_view = video_tool_map.get(tool_name, tool_name)
            self._safe_go(f"/media/{sub_view}")
        elif category == "dev":
            self._safe_go(f"/dev/{tool_name}")
        elif category == "others":
            self._safe_go(f"/others/{tool_name}")
    
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
        
        search_dialog = ToolSearchDialog(self._page, tools, self.config_service)
        self._page.show_dialog(search_dialog)
    
    def _on_keyboard(self, e: ft.KeyboardEvent) -> None:
        """键盘事件处理。"""
        # Ctrl+K 打开搜索
        if e.key == "K" and e.ctrl and not e.shift and not e.alt:
            self._open_search()
    
    def show_search_button(self, update: bool = True) -> None:
        """显示搜索按钮。"""
        if self.fab_search:
            self.fab_search.visible = True
            if update and self._page:
                self._page.update()
    
    def hide_search_button(self, update: bool = True) -> None:
        """隐藏搜索按钮。"""
        if self.fab_search:
            self.fab_search.visible = False
            if update and self._page:
                self._page.update()
    
    def navigate_to_screen_record(self) -> None:
        """导航到屏幕录制工具（供全局热键调用，使用路由）。"""
        try:
            # 使用保存的页面引用
            page = self._page
            if page:
                self._safe_go("/media/screen_record")
        except Exception as ex:
            from utils import logger
            logger.error(f"导航到屏幕录制失败: {ex}")
    
    def update_recommendations_visibility(self, show: bool) -> None:
        """更新推荐工具页面的显示状态（使用路由系统）。
        
        Args:
            show: 是否显示推荐工具页面
        """
        # 如果状态没有变化，不需要更新
        if self.show_recommendations == show:
            return
        
        # 使用保存的页面引用
        page = self._page
        if not page:
            return
        
        # 获取当前路由
        current_route = page.route
        
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
        
        # 使用保存的页面引用
        page = self._page
        if not page:
            return
        
        # 如果隐藏推荐页且当前在根路由，重定向到图片处理
        if not show and (not current_route or current_route == "/"):
            self._safe_go("/image")
        elif show and not current_route.startswith("/image") and not current_route.startswith("/media") and not current_route.startswith("/dev") and not current_route.startswith("/others") and not current_route.startswith("/settings"):
            # 如果显示推荐页且当前不在其他页面，导航到首页
            self._safe_go("/")
        else:
            # 重新处理当前路由以更新导航栏选中状态
            self.handle_route_change(current_route)
    
    def _switch_content_with_animation(self, new_content):
        """带动画切换内容
        
        Args:
            new_content: 新的内容控件
        """
        # 淡出当前内容
        self.content_container.opacity = 0
        self._page.update()
        
        # 使用异步任务实现非阻塞动画
        async def switch_content():
            import asyncio
            await asyncio.sleep(0.15)  # 等待淡出动画完成
            self.content_container.content = new_content
            await asyncio.sleep(0.05)  # 短暂延迟
            self.content_container.opacity = 1.0
            self._page.update()
        
        self._page.run_task(switch_content)
    
    
    def _open_settings(self, e: ft.ControlEvent) -> None:
        """打开设置视图（使用路由导航）。
        
        Args:
            e: 控件事件对象
        """
        page = self._page
        if page:
            self._safe_go("/settings")

    def _check_update_on_startup(self) -> None:
        """启动时在后台检测更新。"""
        async def delayed_check():
            import asyncio
            await asyncio.sleep(2)
            try:
                from utils import logger
                logger.info("[Update] 开始检查更新...")
                
                update_service = UpdateService()
                update_info = await asyncio.to_thread(update_service.check_update)
                
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
        
        self._page.run_task(delayed_check)
    
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
        auto_update_btn = ft.Button(
            content="立即更新",
            icon=ft.Icons.SYSTEM_UPDATE,
        )
        
        manual_download_btn = ft.OutlinedButton(
            content="手动下载",
            icon=ft.Icons.OPEN_IN_BROWSER,
        )
        
        skip_btn = ft.TextButton(
            content="跳过此版本",
        )
        
        later_btn = ft.TextButton(
            content="稍后提醒",
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
            import sys as _sys
            from utils import is_admin, request_admin_restart

            # macOS: 更新脚本通过 osascript 自行提权，无需预先检查管理员
            # Windows: 需要 UAC 提权
            if _sys.platform != "darwin" and not is_admin():
                admin_dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("需要管理员权限"),
                    content=ft.Column(
                        controls=[
                            ft.Text("自动更新需要管理员权限才能正确替换程序文件。"),
                            ft.Text(""),
                            ft.Text("请选择：", weight=ft.FontWeight.W_500),
                            ft.Text("• 点击「以管理员身份重启」自动提权重启"),
                            ft.Text("• 或手动右键程序 → 以管理员身份运行"),
                        ],
                        tight=True,
                        spacing=4,
                    ),
                    actions=[
                        ft.FilledButton(
                            "以管理员身份重启",
                            icon=ft.Icons.ADMIN_PANEL_SETTINGS,
                            on_click=lambda _: request_admin_restart(),
                        ),
                        ft.TextButton(
                            "取消",
                            on_click=lambda _: self._page.pop_dialog(),
                        ),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                self._page.show_dialog(admin_dialog)
                return
            
            auto_update_btn.disabled = True
            manual_download_btn.disabled = True
            skip_btn.disabled = True
            later_btn.disabled = True
            
            progress_bar.visible = True
            progress_text.visible = True
            progress_text.value = "正在下载更新..."
            self._page.update()
            
            async def update_task():
                try:
                    import asyncio
                    from utils import logger
                    
                    updater = AutoUpdater()
                    
                    def progress_callback(downloaded: int, total: int):
                        if total > 0:
                            progress = downloaded / total
                            async def _update_dl_progress():
                                progress_bar.value = progress
                                downloaded_mb = downloaded / 1024 / 1024
                                total_mb = total / 1024 / 1024
                                progress_text.value = f"下载中: {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({progress*100:.0f}%)"
                                self._page.update()
                            try:
                                self._page.run_task(_update_dl_progress)
                            except Exception:
                                pass
                    
                    download_path = await updater.download_update(update_info.download_url, progress_callback)
                    
                    progress_text.value = "正在解压更新..."
                    progress_bar.value = None
                    self._page.update()
                    
                    extract_dir = await asyncio.to_thread(updater.extract_update, download_path)
                    
                    progress_text.value = "正在应用更新，应用即将重启..."
                    self._page.update()
                    
                    await asyncio.sleep(1)
                    
                    # 定义优雅退出回调
                    def exit_callback():
                        """使用标题栏的关闭方法优雅退出"""
                        try:
                            # 使用当前视图的标题栏关闭方法（force=True 强制退出，不最小化到托盘）
                            if hasattr(self, 'title_bar') and self.title_bar:
                                self.title_bar._close_window(None, force=True)
                            else:
                                # 后备：直接关闭窗口
                                self._page.window.close()
                        except Exception as e:
                            logger.warning(f"优雅退出失败: {e}")
                            # 如果失败，让 apply_update 使用强制退出
                            raise
                    
                    await asyncio.to_thread(updater.apply_update, extract_dir, exit_callback)
                    
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
                    self._page.update()
            
            self._page.run_task(update_task)
        
        def on_manual_download(e):
            """手动下载 - 显示下载选项"""
            self._page.pop_dialog()
            
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
            
            self._page.show_dialog(download_dialog)
        
        def on_skip(e):
            """跳过此版本"""
            self.config_service.set_config_value("skipped_version", update_info.latest_version)
            self._page.pop_dialog()
        
        def on_later(e):
            """稍后提醒"""
            self._page.pop_dialog()
        
        auto_update_btn.on_click = on_auto_update
        manual_download_btn.on_click = on_manual_download
        skip_btn.on_click = on_skip
        later_btn.on_click = on_later
        
        self._page.show_dialog(dialog)
    
    def _open_china_download(self, update_info, dialog):
        """打开国内镜像下载"""
        self._page.pop_dialog()
        
        version = update_info.latest_version
        if not version.startswith('v'):
            version = f'v{version}'
        url = f"{DOWNLOAD_URL_CHINA}/{version}"
        webbrowser.open(url)
    
    def _open_github_download(self, dialog):
        """打开GitHub下载"""
        self._page.pop_dialog()
        webbrowser.open(DOWNLOAD_URL_GITHUB)
    
    def _close_download_dialog(self, dialog):
        """关闭下载对话框"""
        self._page.pop_dialog()
    
    def _apply_bg_opacity_from_config(self) -> None:
        """根据配置更新标题栏、导航栏、内容区的透明度。"""
        has_bg = hasattr(self, '_bg_wrapper')
        cs = self.config_service

        if has_bg:
            if cs.get_config_value("bg_titlebar_transparent", True):
                t_op = cs.get_config_value("bg_titlebar_opacity", 0.55)
            else:
                t_op = 0.95
            self.title_bar.bgcolor = ft.Colors.with_opacity(
                t_op, self.title_bar.theme_color
            )

            if cs.get_config_value("bg_navbar_transparent", True):
                n_op = cs.get_config_value("bg_navbar_opacity", 0.25)
            else:
                n_op = 1.0
            self.navigation_container.bgcolor = ft.Colors.with_opacity(
                n_op, ft.Colors.SURFACE
            )

            if cs.get_config_value("bg_content_transparent", True):
                c_op = cs.get_config_value("bg_content_opacity", 0.10)
            else:
                c_op = 1.0
            self.content_bg.bgcolor = ft.Colors.with_opacity(
                c_op, ft.Colors.SURFACE
            )
        else:
            self.title_bar.bgcolor = ft.Colors.with_opacity(
                0.95, self.title_bar.theme_color
            )
            self.navigation_container.bgcolor = ft.Colors.with_opacity(
                1.0, ft.Colors.SURFACE
            )
            self.content_bg.bgcolor = None

    def apply_background(self, image_path: Optional[str], fit_mode: Optional[str]) -> None:
        """应用背景图片到主界面。

        使用 Container + DecorationImage 作为背景层，覆盖整个窗口
        （包括标题栏和导航栏），各层通过半透明 bgcolor 让背景透出。

        Args:
            image_path: 背景图片路径，None表示清除背景
            fit_mode: 图片适应模式 (cover, contain, fill, none)
        """
        if image_path:
            fit_map = {
                "cover": ft.BoxFit.COVER,
                "contain": ft.BoxFit.CONTAIN,
                "fill": ft.BoxFit.FILL,
                "none": ft.BoxFit.NONE,
            }
            fit = fit_map.get(fit_mode, ft.BoxFit.COVER)

            if not hasattr(self, '_bg_wrapper'):
                self._original_controls = list(self.controls)

                self._bg_decoration = ft.DecorationImage(
                    src=image_path,
                    fit=fit,
                    opacity=0.20,
                )

                # 用一个 Container 包裹全部原始内容，Container 自带背景图
                self._bg_wrapper = ft.Container(
                    content=ft.Column(
                        controls=self._original_controls,
                        spacing=0,
                        expand=True,
                    ),
                    image=self._bg_decoration,
                    expand=True,
                    padding=0,
                )

                self.controls = [self._bg_wrapper]
                self._apply_bg_opacity_from_config()
                if self._page:
                    self._page.update()
            else:
                self._bg_decoration.src = image_path
                self._bg_decoration.fit = fit
                self._apply_bg_opacity_from_config()
                if self._page:
                    self._page.update()
        else:
            if hasattr(self, '_bg_wrapper') and hasattr(self, '_original_controls'):
                self.controls = self._original_controls

                delattr(self, '_bg_wrapper')
                delattr(self, '_bg_decoration')
                delattr(self, '_original_controls')

                self._apply_bg_opacity_from_config()
                if self._page:
                    self._page.update()
