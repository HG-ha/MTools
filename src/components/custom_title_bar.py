# -*- coding: utf-8 -*-
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
from services.weather_service import WeatherService


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
        
        # 初始化天气服务
        self.weather_service: WeatherService = WeatherService()
        self.weather_data: Optional[dict] = None
        
        # 获取用户设置的主题色
        if self.config_service:
            self.theme_color: str = self.config_service.get_config_value("theme_color", "#667EEA")
        else:
            self.theme_color = "#667EEA"
        
        # 构建标题栏
        self._build_title_bar()
        
        # 异步加载天气数据
        self.page.run_task(self._load_weather_data)
    
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
        
        # 右侧：天气 + 主题切换 + 窗口控制按钮
        
        # 天气显示组件
        self.weather_icon: ft.Icon = ft.Icon(
            name=ft.Icons.WB_CLOUDY,
            size=18,
            color=ft.Colors.WHITE,
        )
        
        self.weather_text: ft.Text = ft.Text(
            value="加载中...",
            size=12,
            color=ft.Colors.WHITE,
        )
        
        self.weather_container: ft.Container = ft.Container(
            content=ft.Row(
                controls=[
                    self.weather_icon,
                    self.weather_text,
                ],
                spacing=4,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8),
            tooltip="天气信息",
        )
        
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
                self.weather_container,
                self.theme_icon,
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
        self.height = 42  # 减小标题栏高度
        self.padding = ft.padding.symmetric(horizontal=PADDING_MEDIUM)
        # 使用用户设置的主题色创建半透明渐变
        self.gradient = self._create_gradient()
        # 添加半透明背景色,避免完全不透明
        self.bgcolor = ft.Colors.with_opacity(0.95, self.theme_color)  # 95% 不透明度
        # 移除渐变,改用纯色半透明背景
        self.gradient = None
        
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
        
        # 保存最大化状态
        if self.config_service:
            self.config_service.set_config_value("window_maximized", self.page.window.maximized)
    
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
        # 在关闭前保存窗口位置、大小和最大化状态
        if self.config_service:
            # 保存最大化状态
            self.config_service.set_config_value("window_maximized", self.page.window.maximized)
            
            # 只在非最大化时保存窗口位置和大小
            if not self.page.window.maximized:
                if self.page.window.left is not None and self.page.window.top is not None:
                    self.config_service.set_config_value("window_left", self.page.window.left)
                    self.config_service.set_config_value("window_top", self.page.window.top)
                if self.page.window.width is not None and self.page.window.height is not None:
                    self.config_service.set_config_value("window_width", self.page.window.width)
                    self.config_service.set_config_value("window_height", self.page.window.height)
        
        # 关闭天气服务
        if self.weather_service:
            import asyncio
            try:
                # 获取当前事件循环
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果循环正在运行，创建任务
                    asyncio.create_task(self.weather_service.close())
                else:
                    # 如果循环未运行，直接运行协程
                    loop.run_until_complete(self.weather_service.close())
            except Exception as ex:
                # 如果上述方法都失败，尝试创建新的事件循环
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.weather_service.close())
                    loop.close()
                except:
                    pass
        
        # 关闭窗口
        self.page.window.close()
    
    async def _load_weather_data(self):
        """加载天气数据"""
        try:
            # 显示加载状态
            self.weather_text.value = "加载中..."
            self.weather_icon.name = ft.Icons.REFRESH
            self.page.update()
            
            # 获取用户设置的城市
            preferred_city = None
            if self.config_service:
                preferred_city = self.config_service.get_config_value("weather_city", None)
            
            # 获取天气数据
            weather = await self.weather_service.get_current_location_weather(preferred_city)
            
            if weather:
                self.weather_data = weather
                # 更新显示
                temp = weather.get('temperature')
                condition = weather.get('condition', '未知')
                icon_name = weather.get('icon', 'WB_CLOUDY')
                
                if temp is not None:
                    self.weather_text.value = f"{temp}°C"
                else:
                    self.weather_text.value = condition
                
                # 更新图标
                self.weather_icon.name = getattr(ft.Icons, icon_name, ft.Icons.WB_CLOUDY)
                
                # 更新 tooltip
                location = weather.get('location', '未知')
                feels_like = weather.get('feels_like')
                humidity = weather.get('humidity')
                
                tooltip_parts = [f"{location}: {condition}"]
                if temp is not None:
                    tooltip_parts.append(f"温度: {temp}°C")
                if feels_like is not None:
                    tooltip_parts.append(f"体感: {feels_like}°C")
                if humidity is not None:
                    tooltip_parts.append(f"湿度: {humidity}%")
                
                self.weather_container.tooltip = "\n".join(tooltip_parts)
            else:
                self.weather_text.value = "获取失败"
                self.weather_icon.name = ft.Icons.ERROR_OUTLINE
                self.weather_container.tooltip = "天气数据获取失败"
            
            self.page.update()
            
        except Exception as e:
            self.weather_text.value = "加载失败"
            self.weather_icon.name = ft.Icons.ERROR_OUTLINE
            self.weather_container.tooltip = f"错误: {str(e)}"
            self.page.update()
    
    def _show_city_dialog(self, e: ft.ControlEvent = None):
        """显示城市设置对话框"""
        # 获取当前设置的城市
        current_city = ""
        if self.config_service:
            current_city = self.config_service.get_config_value("weather_city", "")
        
        # 创建输入框
        city_input = ft.TextField(
            label="城市名称",
            hint_text="例如: 北京、上海、广州",
            value=current_city,
            autofocus=True,
        )
        
        def save_city(e):
            city = city_input.value.strip()
            if city:
                # 保存到配置
                if self.config_service:
                    self.config_service.set_config_value("weather_city", city)
                # 关闭对话框
                dialog.open = False
                self.page.update()
                # 重新加载天气
                self.page.run_task(self._load_weather_data)
            else:
                city_input.error_text = "请输入城市名称"
                self.page.update()
        
        def clear_city(e):
            # 清除城市设置，使用自动定位
            if self.config_service:
                self.config_service.set_config_value("weather_city", "")
            dialog.open = False
            self.page.update()
            # 重新加载天气
            self.page.run_task(self._load_weather_data)
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        # 创建对话框
        dialog = ft.AlertDialog(
            title=ft.Text("设置天气城市"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        city_input,
                        ft.Text(
                            "提示: 留空则自动根据 IP 定位",
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=300,
            ),
            actions=[
                ft.TextButton("清除并自动定位", on_click=clear_city),
                ft.TextButton("取消", on_click=close_dialog),
                ft.FilledButton("确定", on_click=save_city),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

