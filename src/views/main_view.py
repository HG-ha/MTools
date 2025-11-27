# -*- coding: utf-8 -*-
"""主视图模块。

提供应用的主界面，包含导航栏和各功能视图的切换。
"""

from typing import Optional

import flet as ft

from components import CustomTitleBar, ToolInfo, ToolSearchDialog
from services import ConfigService, EncodingService, ImageService, FFmpegService
from utils.tool_registry import register_all_tools
from utils import get_all_tools
from views.media import AudioView, VideoView
from views.dev_tools import DevToolsView
from views.others import OthersView
from views.image import ImageView
from views.settings_view import SettingsView


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
        self.image_service: ImageService = ImageService()
        self.encoding_service: EncodingService = EncodingService()
        self.ffmpeg_service: FFmpegService = FFmpegService(self.config_service)
        
        # 创建自定义标题栏（传递配置服务以保存窗口状态）
        self.title_bar: CustomTitleBar = CustomTitleBar(page, self.config_service)
        
        # 创建内容容器（稍后创建视图时需要）
        self.content_container: Optional[ft.Container] = None
        
        # 创建各功能视图
        self.image_view: Optional[ImageView] = None
        self.dev_tools_view: Optional[DevToolsView] = None
        self.audio_view: Optional[AudioView] = None
        self.video_view: VideoView = VideoView(page, self.config_service, self.ffmpeg_service)
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
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 创建导航栏
        self.navigation_rail: ft.NavigationRail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            group_alignment=-0.9,
            expand=True,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.IMAGE_OUTLINED,
                    selected_icon=ft.Icons.IMAGE_ROUNDED,
                    label="图片处理",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.AUDIOTRACK_OUTLINED,
                    selected_icon=ft.Icons.AUDIOTRACK_ROUNDED,
                    label="音频处理",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.VIDEO_LIBRARY_OUTLINED,
                    selected_icon=ft.Icons.VIDEO_LIBRARY_ROUNDED,
                    label="视频处理",
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
            ],
            on_change=self._on_navigation_change,
        )
        
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
        
        # 创建内容容器（先创建占位容器）
        self.content_container = ft.Container(
            expand=True,
            alignment=ft.alignment.top_left,  # 内容从左上角开始
            width=float('inf'),  # 占满可用宽度
            height=float('inf'),  # 占满可用高度
        )
        
        # 创建图片视图、音频视图、视频视图、开发工具视图和其他工具视图，并传递容器引用
        self.image_view = ImageView(self.page, self.config_service, self.image_service, self.content_container)
        self.audio_view = AudioView(self.page, self.config_service, self.content_container)
        self.video_view = VideoView(self.page, self.config_service, self.ffmpeg_service, self.content_container)
        self.dev_tools_view = DevToolsView(self.page, self.config_service, self.encoding_service, self.content_container)
        self.others_view = OthersView(self.page, self.config_service, self.content_container)
        
        # 设置初始内容
        self.content_container.content = self.image_view
        
        # 注册所有工具（自动注册）
        register_all_tools()
        
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
    
    def _on_navigation_change(self, e: ft.ControlEvent) -> None:
        """导航变更事件处理。
        
        Args:
            e: 控件事件对象
        """
        selected_index: int = e.control.selected_index
        
        # 标记是否恢复了子视图
        restored = False
        
        # 根据选中的索引切换视图
        if selected_index == 0:
            view = self.image_view
            # 尝试恢复图片处理页面的状态（如果之前在子视图中）
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            # 如果没有恢复子视图，则显示主视图
            if not restored:
                self.content_container.content = view
        elif selected_index == 1:
            view = self.audio_view
            # 尝试恢复音频处理页面的状态
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            if not restored:
                self.content_container.content = view
        elif selected_index == 2:
            view = self.video_view
            self.content_container.content = view
        elif selected_index == 3:
            view = self.dev_tools_view
            # 尝试恢复开发工具页面的状态
            if hasattr(view, 'restore_state'):
                restored = view.restore_state()
            
            if not restored:
                self.content_container.content = view
        elif selected_index == 4:
            view = self.others_view
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
        # 解析工具ID
        parts = tool_id.split(".")
        if len(parts) < 2:
            return
        
        category = parts[0]
        tool_name = ".".join(parts[1:])  # 支持多级，如 "puzzle.merge"
        
        # 先切换到对应的分类
        if category == "image":
            self.navigation_rail.selected_index = 0
            self.content_container.content = self.image_view
            # 调用图片视图的方法打开子工具
            if hasattr(self.image_view, 'open_tool'):
                self.image_view.open_tool(tool_name)
        elif category == "audio":
            self.navigation_rail.selected_index = 1
            self.content_container.content = self.audio_view
            if hasattr(self.audio_view, 'open_tool'):
                self.audio_view.open_tool(tool_name)
        elif category == "video":
            self.navigation_rail.selected_index = 2
            self.content_container.content = self.video_view
            # 视频视图使用 _open_view 方法
            self.video_view._open_view(tool_name)
        elif category == "dev":
            self.navigation_rail.selected_index = 3
            self.content_container.content = self.dev_tools_view
            if hasattr(self.dev_tools_view, 'open_tool'):
                self.dev_tools_view.open_tool(tool_name)
        elif category == "others":
            self.navigation_rail.selected_index = 4
            self.content_container.content = self.others_view
            if hasattr(self.others_view, 'open_tool'):
                self.others_view.open_tool(tool_name)
        
        # 使用page.update()而不是单独更新控件
        if self.page:
            self.page.update()
    
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
