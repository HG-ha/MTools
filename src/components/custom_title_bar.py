"""自定义标题栏组件模块。

提供自定义标题栏，包含窗口控制、主题切换等功能。
"""

from typing import Callable, Optional

import flet as ft

from constants import (
    APP_TITLE,
    BORDER_RADIUS_SMALL,
    GRADIENT_END,
    GRADIENT_START,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService


class CustomTitleBar(ft.Container):
    """自定义标题栏类。
    
    提供现代化的自定义标题栏，包含：
    - 应用图标和标题
    - 窗口拖动区域
    - 主题切换按钮
    - 窗口控制按钮（最小化、最大化、关闭）
    """

    def __init__(self, page: ft.Page, config_service: Optional[ConfigService] = None) -> None:
        """初始化自定义标题栏。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例（用于保存窗口状态）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: Optional[ConfigService] = config_service
        
        # 获取用户设置的主题色
        if self.config_service:
            self.theme_color: str = self.config_service.get_config_value("theme_color", "#667EEA")
        else:
            self.theme_color = "#667EEA"
        
        # 构建标题栏
        self._build_title_bar()
    
    def _build_title_bar(self) -> None:
        """构建标题栏UI。"""
        # 左侧：应用图标 + 标题（可拖动，支持双击最大化）
        drag_area: ft.WindowDragArea = ft.WindowDragArea(
            content=ft.GestureDetector(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            name=ft.Icons.APPS_ROUNDED,
                            size=24,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Container(width=PADDING_SMALL),
                        ft.Text(
                            APP_TITLE,
                            size=14,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    spacing=0,
                ),
                on_double_tap=self._toggle_maximize,
            ),
            expand=True,
        )
        
        # 右侧：主题切换 + 窗口控制按钮
        self.theme_icon: ft.IconButton = ft.IconButton(
            icon=ft.Icons.LIGHT_MODE_OUTLINED,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            tooltip="切换主题",
            on_click=self._toggle_theme,
            style=ft.ButtonStyle(
                padding=10,
            ),
        )
        
        minimize_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.HORIZONTAL_RULE,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            tooltip="最小化",
            on_click=self._minimize_window,
            style=ft.ButtonStyle(
                padding=10,
            ),
        )
        
        self.maximize_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.CROP_SQUARE,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            tooltip="最大化",
            on_click=self._toggle_maximize,
            style=ft.ButtonStyle(
                padding=10,
            ),
        )
        
        close_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            tooltip="关闭",
            on_click=self._close_window,
            style=ft.ButtonStyle(
                padding=10,
            ),
            hover_color=ft.Colors.with_opacity(0.2, ft.Colors.RED),
        )
        
        right_section: ft.Row = ft.Row(
            controls=[
                self.theme_icon,
                ft.VerticalDivider(
                    width=1,
                    thickness=1,
                    color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                ),
                minimize_button,
                self.maximize_button,
                close_button,
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.END,
        )
        
        # 组装标题栏
        title_bar_content: ft.Row = ft.Row(
            controls=[
                drag_area,
                right_section,
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        # 配置容器属性
        self.content = title_bar_content
        self.height = 48
        self.padding = ft.padding.symmetric(horizontal=PADDING_MEDIUM)
        # 使用用户设置的主题色创建渐变（或使用默认渐变）
        self.gradient = self._create_gradient()
        
        # 初始化主题图标
        self._update_theme_icon()
    
    def _create_gradient(self) -> ft.LinearGradient:
        """根据主题色创建渐变。
        
        Returns:
            线性渐变对象
        """
        # 使用主题色作为渐变起始色
        # 计算一个稍深的结束色（通过简单的色调偏移）
        return ft.LinearGradient(
            begin=ft.alignment.center_left,
            end=ft.alignment.center_right,
            colors=[
                self.theme_color,
                self.theme_color,  # 使用相同颜色，Material Design 会自动处理渐变
            ],
        )
    
    def _toggle_theme(self, e: ft.ControlEvent) -> None:
        """切换主题模式。
        
        Args:
            e: 控件事件对象
        """
        # 一键切换主题，所有组件自动更新
        if self.page.theme_mode == ft.ThemeMode.LIGHT:
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT
        
        self._update_theme_icon()
        self.page.update()
    
    def _update_theme_icon(self) -> None:
        """更新主题图标。"""
        if self.page.theme_mode == ft.ThemeMode.LIGHT:
            self.theme_icon.icon = ft.Icons.LIGHT_MODE_OUTLINED
            self.theme_icon.tooltip = "切换到深色模式"
        else:
            self.theme_icon.icon = ft.Icons.DARK_MODE_OUTLINED
            self.theme_icon.tooltip = "切换到浅色模式"
    
    def _minimize_window(self, e: ft.ControlEvent) -> None:
        """最小化窗口。
        
        Args:
            e: 控件事件对象
        """
        self.page.window.minimized = True
        self.page.update()
    
    def _toggle_maximize(self, e: ft.ControlEvent = None) -> None:
        """切换最大化/还原窗口。
        
        Args:
            e: 控件事件对象（可选，支持双击调用）
        """
        self.page.window.maximized = not self.page.window.maximized
        self.page.update()
        
        # 更新按钮图标
        self._update_maximize_button()
    
    def _update_maximize_button(self) -> None:
        """根据窗口当前状态更新最大化/还原按钮图标。"""
        try:
            if self.page.window.maximized:
                self.maximize_button.icon = ft.Icons.FILTER_NONE
                self.maximize_button.tooltip = "还原"
            else:
                self.maximize_button.icon = ft.Icons.CROP_SQUARE
                self.maximize_button.tooltip = "最大化"
            self.maximize_button.update()
        except Exception:
            pass  # 忽略更新错误
    
    def _close_window(self, e: ft.ControlEvent) -> None:
        """关闭窗口。
        
        Args:
            e: 控件事件对象
        """
        # 在关闭前保存窗口位置和大小
        if self.config_service:
            if self.page.window.left is not None and self.page.window.top is not None:
                self.config_service.set_config_value("window_left", self.page.window.left)
                self.config_service.set_config_value("window_top", self.page.window.top)
            if self.page.window.width is not None and self.page.window.height is not None:
                self.config_service.set_config_value("window_width", self.page.window.width)
                self.config_service.set_config_value("window_height", self.page.window.height)
        
        # 关闭窗口
        self.page.window.close()

