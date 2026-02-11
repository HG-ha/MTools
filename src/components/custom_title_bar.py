# -*- coding: utf-8 -*-
"""自定义标题栏组件模块。

提供自定义标题栏，包含窗口控制、主题切换等功能。
"""

import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import flet as ft
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

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


def _get_icon_path() -> str:
    """获取应用图标的 Flet assets 相对路径（用于 ft.Image）。
    
    Returns:
        相对于 assets_dir 的路径
    """
    return "icon.png"


def _get_icon_abs_path() -> str:
    """获取应用图标的绝对文件路径（用于 pystray 等需要文件路径的场景）。
    
    Returns:
        图标文件的绝对路径
    """
    # 尝试从源代码目录查找
    path = Path(__file__).parent.parent / "assets" / "icon.png"
    if path.exists():
        return str(path)
    
    # 打包环境：从 exe 所在目录查找
    app_dir = Path(sys.argv[0]).parent
    for p in [app_dir / "src" / "assets" / "icon.png", app_dir / "assets" / "icon.png"]:
        if p.exists():
            return str(p)
    
    return "icon.png"


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
        self._page: ft.Page = page
        self.config_service: Optional[ConfigService] = config_service
        
        # 初始化天气服务
        self.weather_service: WeatherService = WeatherService()
        self.weather_data: Optional[dict] = None
        
        # 托盘图标相关
        self.tray_icon: Optional[Icon] = None
        self.minimize_to_tray: bool = False  # 是否启用最小化到托盘
        
        # 获取用户设置的主题色、天气显示和托盘配置
        if self.config_service:
            self.theme_color: str = self.config_service.get_config_value("theme_color", "#667EEA")
            self.show_weather: bool = self.config_service.get_config_value("show_weather", True)
            self.minimize_to_tray = self.config_service.get_config_value("minimize_to_tray", False)
        else:
            self.theme_color = "#667EEA"
            self.show_weather = True
        
        # 构建标题栏
        self._build_title_bar()
        
        # 初始化系统托盘（如果启用）
        if self.minimize_to_tray:
            self._setup_tray_icon()
        
        # 异步加载天气数据（如果启用）
        if self.show_weather:
            self._page.run_task(self._load_weather_data)
    
    def _get_page(self) -> Optional[ft.Page]:
        """获取页面引用（带容错）。
        
        Returns:
            页面对象，如果不存在则返回 None
        """
        return self._page
    
    def _build_title_bar(self) -> None:
        """构建标题栏UI。"""
        # 左侧：应用图标 + 标题（可拖动，支持双击最大化）
        drag_area: ft.WindowDragArea = ft.WindowDragArea(
            content=ft.GestureDetector(
                content=ft.Row(
                    controls=[
                        ft.Image(
                            src=_get_icon_path(),
                            width=22,
                            height=22,
                            fit=ft.BoxFit.CONTAIN,
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
            icon=ft.Icons.WB_CLOUDY,
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
            visible=self.show_weather,  # 根据配置决定是否显示
            opacity=1.0,
            scale=1.0,
            animate_opacity=200,  # 200ms 淡入淡出动画
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),  # 缩放动画
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
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
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
        page = self._get_page()
        if not page:
            return
        
        # 一键切换主题，所有组件自动更新
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
        
        self._update_theme_icon()
        page.update()
    
    def _update_theme_icon(self) -> None:
        """更新主题图标。"""
        page = self._get_page()
        if not page:
            return
            
        if page.theme_mode == ft.ThemeMode.LIGHT:
            self.theme_icon.icon = ft.Icons.LIGHT_MODE_OUTLINED
            self.theme_icon.tooltip = "切换到深色模式"
        else:
            self.theme_icon.icon = ft.Icons.DARK_MODE_OUTLINED
            self.theme_icon.tooltip = "切换到浅色模式"
    
    def update_theme_color(self, color: str) -> None:
        """更新标题栏主题色。
        
        Args:
            color: 新的主题色（十六进制颜色值）
        """
        self.theme_color = color
        self.bgcolor = ft.Colors.with_opacity(0.95, color)
        try:
            if self._page:
                self.update()
        except:
            pass
    
    def _minimize_window(self, e: ft.ControlEvent) -> None:
        """最小化窗口。
        
        Args:
            e: 控件事件对象
        """
        page = self._get_page()
        if not page:
            return
            
        page.window.minimized = True
        page.update()
    
    def _toggle_maximize(self, e: ft.ControlEvent = None) -> None:
        """切换最大化/还原窗口。
        
        Args:
            e: 控件事件对象（可选，支持双击调用）
        """
        self._page.window.maximized = not self._page.window.maximized
        self._page.update()
        
        # 更新按钮图标
        self._update_maximize_button()
        
        # 保存最大化状态
        if self.config_service:
            self.config_service.set_config_value("window_maximized", self._page.window.maximized)
    
    def _update_maximize_button(self) -> None:
        """根据窗口当前状态更新最大化/还原按钮图标。"""
        try:
            if self._page.window.maximized:
                self.maximize_button.icon = ft.Icons.FILTER_NONE
                self.maximize_button.tooltip = "还原"
            else:
                self.maximize_button.icon = ft.Icons.CROP_SQUARE
                self.maximize_button.tooltip = "最大化"
            self.maximize_button.update()
        except Exception:
            pass  # 忽略更新错误
    
    def _create_tray_icon_image(self) -> Image.Image:
        """创建托盘图标图像。
        
        Returns:
            PIL Image 对象
        """
        # 尝试加载应用图标（pystray 需要绝对文件路径）
        icon_path = _get_icon_abs_path()
        
        try:
            if Path(icon_path).exists():
                icon_image = Image.open(icon_path)
                # 调整图标大小为适合托盘的尺寸
                icon_image = icon_image.resize((64, 64), Image.Resampling.LANCZOS)
                return icon_image
        except Exception:
            pass
        
        # 如果加载失败，创建一个简单的图标
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), '#667EEA')
        dc = ImageDraw.Draw(image)
        
        # 绘制一个简单的字母 M
        dc.text((width // 4, height // 4), 'M', fill='white')
        
        return image
    
    def _setup_tray_icon(self) -> None:
        """设置系统托盘图标。"""
        if self.tray_icon is not None:
            return  # 已经初始化过了
        
        try:
            # 创建托盘图标图像
            icon_image = self._create_tray_icon_image()
            
            # 创建托盘菜单
            menu = Menu(
                MenuItem("显示窗口", self._show_window_from_tray, default=True),
                MenuItem("退出应用", self._exit_app_from_tray)
            )
            
            # 创建托盘图标
            self.tray_icon = Icon(APP_TITLE, icon_image, APP_TITLE, menu)
            
            # 在单独的线程中运行托盘图标
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
            
        except Exception as e:
            from utils import logger
            logger.error(f"设置系统托盘失败: {e}")
            self.tray_icon = None
    
    def _show_window_from_tray(self, icon=None, item=None) -> None:
        """从托盘显示窗口（带淡入动画）。
        
        Args:
            icon: 托盘图标对象
            item: 菜单项对象
        """
        try:
            # 获取用户配置的透明度
            target_opacity = 1.0
            if self.config_service:
                target_opacity = self.config_service.get_config_value("window_opacity", 1.0)
            
            # 先显示窗口但设置为透明
            self._page.window.opacity = 0.0
            self._page.window.visible = True
            self._page.update()
            
            # 使用定时器实现淡入动画
            import time
            def fade_in():
                try:
                    # 分10步淡入，总耗时约150ms
                    for i in range(1, 11):
                        self._page.window.opacity = (i / 10.0) * target_opacity
                        self._page.update()
                        time.sleep(0.015)
                    
                    # 确保最终透明度准确
                    self._page.window.opacity = target_opacity
                    self._page.update()
                except Exception:
                    pass
            
            # 在后台线程执行动画
            threading.Thread(target=fade_in, daemon=True).start()
        except Exception:
            pass
    
    def _hide_to_tray(self) -> None:
        """隐藏窗口到托盘（带淡出动画）。"""
        try:
            import time
            
            # 获取用户配置的透明度（作为动画起始值）
            start_opacity = 1.0
            if self.config_service:
                start_opacity = self.config_service.get_config_value("window_opacity", 1.0)
            
            # 淡出动画
            def fade_out():
                try:
                    # 分10步淡出，总耗时约150ms
                    for i in range(9, -1, -1):
                        self._page.window.opacity = (i / 10.0) * start_opacity
                        self._page.update()
                        time.sleep(0.015)
                    
                    # 动画结束后隐藏窗口
                    self._page.window.visible = False
                    self._page.update()
                    
                    # 恢复用户设置的透明度（下次显示时使用）
                    self._page.window.opacity = start_opacity
                except Exception:
                    pass
            
            # 在后台线程执行动画
            threading.Thread(target=fade_out, daemon=True).start()
        except Exception:
            pass
    
    def _exit_app_from_tray(self, icon=None, item=None) -> None:
        """从托盘退出应用。
        
        Args:
            icon: 托盘图标对象
            item: 菜单项对象
        """
        try:
            # 如果窗口当前不可见，先显示窗口（不带动画，直接显示）
            if not self._page.window.visible:
                # 获取用户配置的透明度
                target_opacity = 1.0
                if self.config_service:
                    target_opacity = self.config_service.get_config_value("window_opacity", 1.0)
                
                self._page.window.opacity = target_opacity
                self._page.window.visible = True
                self._page.update()
            
            # 停止托盘图标
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
            
            # 执行真正的关闭流程（传递 force=True 强制退出）
            self._close_window(None, force=True)
        except Exception as e:
            # 如果出错，确保能退出
            import sys
            sys.exit(0)
    
    def set_minimize_to_tray(self, enabled: bool) -> None:
        """设置是否启用最小化到托盘。
        
        Args:
            enabled: 是否启用
        """
        self.minimize_to_tray = enabled
        
        if enabled:
            # 启用托盘功能
            if self.tray_icon is None:
                self._setup_tray_icon()
        else:
            # 禁用托盘功能
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
    
    def _close_window(self, e: Optional[ft.ControlEvent], force: bool = False) -> None:
        """关闭窗口。
        
        Args:
            e: 控件事件对象
            force: 是否强制退出（True时忽略托盘设置，直接退出应用）
        """
        # 如果启用了托盘功能且不是强制退出，则隐藏到托盘而不是关闭
        if not force and self.minimize_to_tray and self.tray_icon:
            self._hide_to_tray()
            return
        
        page = self._get_page()
        if not page:
            # 如果页面引用丢失，强制退出
            sys.exit(0)
            return
        
        # 设置关闭标记，防止后台任务继续操作 page
        if hasattr(page, '_main_view') and hasattr(page._main_view, '_is_closing'):
            page._main_view._is_closing = True
        
        # 在关闭前保存窗口位置、大小和最大化状态
        if self.config_service:
            # 保存最大化状态
            self.config_service.set_config_value("window_maximized", page.window.maximized)
            
            # 只在非最大化时保存窗口位置和大小
            if not page.window.maximized:
                if page.window.left is not None and page.window.top is not None:
                    self.config_service.set_config_value("window_left", page.window.left)
                    self.config_service.set_config_value("window_top", page.window.top)
                if page.window.width is not None and page.window.height is not None:
                    self.config_service.set_config_value("window_width", page.window.width)
                    self.config_service.set_config_value("window_height", page.window.height)
        
        # 停止托盘图标
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        
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
        
        # 关闭窗口 (异步方法，使用 run_task)
        async def _do_close():
            try:
                await page.window.close()
            except RuntimeError:
                pass  # Session closed
        page.run_task(_do_close)
    
    async def _load_weather_data(self):
        """加载天气数据"""
        try:
            # 显示加载状态
            self.weather_text.value = "加载中..."
            self.weather_icon.icon = ft.Icons.REFRESH
            self._page.update()
            
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
                self.weather_icon.icon = getattr(ft.Icons, icon_name, ft.Icons.WB_CLOUDY)
                
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
                self.weather_icon.icon = ft.Icons.ERROR_OUTLINE
                self.weather_container.tooltip = "天气数据获取失败"
            
            self._page.update()
            
        except Exception as e:
            self.weather_text.value = "加载失败"
            self.weather_icon.icon = ft.Icons.ERROR_OUTLINE
            self.weather_container.tooltip = f"错误: {str(e)}"
            self._page.update()
    
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
                self._page.update()
                # 重新加载天气
                self._page.run_task(self._load_weather_data)
            else:
                city_input.error_text = "请输入城市名称"
                self._page.update()
        
        def clear_city(e):
            # 清除城市设置，使用自动定位
            if self.config_service:
                self.config_service.set_config_value("weather_city", "")
            dialog.open = False
            self._page.update()
            # 重新加载天气
            self._page.run_task(self._load_weather_data)
        
        def close_dialog(e):
            dialog.open = False
            self._page.update()
        
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
        
        self._page.dialog = dialog
        dialog.open = True
        self._page.update()
    
    def set_weather_visibility(self, visible: bool) -> None:
        """设置天气显示状态
        
        Args:
            visible: 是否显示天气
        """
        self.show_weather = visible
        
        page = self._get_page()
        if not page:
            return
        
        if visible:
            # 显示天气：先设为可见但透明，然后淡入+缩放
            self.weather_container.visible = True
            self.weather_container.opacity = 0
            self.weather_container.scale = 0.8
            page.update()
            
            # 使用定时器实现非阻塞动画
            import threading
            def show_animation():
                import time
                time.sleep(0.05)
                self.weather_container.opacity = 1.0
                self.weather_container.scale = 1.0
                p = self._get_page()
                if p:
                    p.update()
            
            timer = threading.Timer(0.001, show_animation)
            timer.daemon = True
            timer.start()
            
            # 如果还没有加载数据，则加载
            if self.weather_data is None:
                page.run_task(self._load_weather_data)
        else:
            # 隐藏天气：淡出+缩小
            self.weather_container.opacity = 0
            self.weather_container.scale = 0.8
            page.update()
            
            # 使用定时器延迟隐藏
            import threading
            def hide_animation():
                import time
                time.sleep(0.2)
                self.weather_container.visible = False
                p = self._get_page()
                if p:
                    p.update()
            
            timer = threading.Timer(0.001, hide_animation)
            timer.daemon = True
            timer.start()

