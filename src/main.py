# -*- coding: utf-8 -*-
"""MyTools应用程序入口。

多功能桌面应用程序，集成了图片处理、音视频处理、编码转换、代码格式化等功能。
遵循Material Design设计原则，使用Flet框架开发。
"""

# 补丁
from utils import patch  # noqa: F401
# Nuitka 打包初始化（必须在导入 flet 之前执行）
from utils import nuitka_setup  # noqa: F401

import flet as ft

from constants import (
    APP_TITLE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from services import ConfigService
from views.main_view import MainView


def main(page: ft.Page) -> None:
    """应用主入口函数。
    
    配置页面属性并初始化主视图。
    
    Args:
        page: Flet页面对象
    """
    # 加载配置
    config_service = ConfigService()
    saved_font = config_service.get_config_value("font_family", "System")
    saved_theme_color = config_service.get_config_value("theme_color", "#667EEA")
    saved_theme_mode = config_service.get_config_value("theme_mode", "system")
    saved_left = config_service.get_config_value("window_left")
    saved_top = config_service.get_config_value("window_top")
    saved_width = config_service.get_config_value("window_width")
    saved_height = config_service.get_config_value("window_height")
    
    # 配置页面属性
    page.title = APP_TITLE
    
    # 设置窗口图标（任务栏图标）
    import sys
    from pathlib import Path
    
    # 判断是否为 Nuitka 打包后的环境（.exe 文件）
    is_compiled = Path(sys.argv[0]).suffix.lower() == '.exe'
    
    if is_compiled:
        # Nuitka 打包环境：从 exe 所在目录查找
        app_dir = Path(sys.argv[0]).parent
    else:
        # 开发环境：从源代码目录查找
        app_dir = Path(__file__).parent
    
    # 尝试多个可能的图标路径（优先使用 .ico 格式）
    possible_icon_paths = [
        # ICO 格式（Windows 任务栏最佳）
        app_dir / "src" / "assets" / "icon.ico",  # 打包后的标准路径
        app_dir / "assets" / "icon.ico",  # 开发环境
        Path(__file__).parent / "assets" / "icon.ico",  # 相对于源文件
        # PNG 格式（备用）
        app_dir / "src" / "assets" / "icon.png",
        app_dir / "assets" / "icon.png",
        Path(__file__).parent / "assets" / "icon.png",
    ]
    
    icon_path = None
    for path in possible_icon_paths:
        if path.exists():
            icon_path = path
            break
    
    if icon_path:
        page.window.icon = str(icon_path)
    
    # 设置窗口大小（使用保存的大小或默认大小）
    page.window.width = saved_width if saved_width is not None else WINDOW_WIDTH
    page.window.height = saved_height if saved_height is not None else WINDOW_HEIGHT
    # page.window.min_width = WINDOW_MIN_WIDTH
    # page.window.min_height = WINDOW_MIN_HEIGHT
    # 设置窗口最小大小
    page.window.min_width = WINDOW_WIDTH
    page.window.min_height = WINDOW_HEIGHT
    
    # 恢复窗口位置（如果有保存的位置）
    if saved_left is not None and saved_top is not None:
        page.window.left = saved_left
        page.window.top = saved_top
    
    # 隐藏系统标题栏，使用自定义标题栏
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    
    # 设置浅色主题 - 使用用户选择的主题色或默认色
    page.theme = ft.Theme(
        color_scheme_seed=saved_theme_color,  # 使用用户设置的主题色
        use_material3=True,
        font_family=saved_font,  # 使用保存的字体
        # 页面和组件颜色配置
        scaffold_bgcolor="#F8F9FA",  # 浅灰背景
        card_color="#FFFFFF",         # 白色卡片
        # 导航栏主题 - 不设置固定背景色，使用容器的半透明背景
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor=ft.Colors.TRANSPARENT,
        ),
    )
    
    # 设置深色主题
    page.dark_theme = ft.Theme(
        color_scheme_seed=saved_theme_color,  # 使用用户设置的主题色
        use_material3=True,
        font_family=saved_font,  # 使用保存的字体
        # 深色模式颜色配置
        scaffold_bgcolor="#121212",  # 深色背景
        card_color="#2C2C2C",        # 深色卡片
        # 深色导航栏主题 - 不设置固定背景色，使用容器的半透明背景
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor=ft.Colors.TRANSPARENT,
        ),
    )
    
    # 应用用户设置的主题模式
    if saved_theme_mode == "light":
        page.theme_mode = ft.ThemeMode.LIGHT
    elif saved_theme_mode == "dark":
        page.theme_mode = ft.ThemeMode.DARK
    else:  # system 或其他
        page.theme_mode = ft.ThemeMode.SYSTEM
    
    # 设置页面布局
    page.padding = 0
    page.spacing = 0
    
    # 创建并添加主视图
    main_view: MainView = MainView(page)
    page.add(main_view)
    
    # 更新页面
    page.update()
    
    # 应用窗口透明度（必须在page.update()之后）
    if hasattr(main_view, '_pending_opacity'):
        page.window.opacity = main_view._pending_opacity
        page.update()
    
    # 应用背景图片（如果有配置）
    if hasattr(main_view, '_pending_bg_image') and main_view._pending_bg_image:
        main_view.apply_background(main_view._pending_bg_image, main_view._pending_bg_fit)
    
    # 监听窗口事件（移动和调整大小时自动保存）
    def on_window_event(e):
        """处理窗口事件。"""
        # 窗口移动时保存位置
        if e.data == "moved":
            if page.window.left is not None and page.window.top is not None:
                config_service.set_config_value("window_left", page.window.left)
                config_service.set_config_value("window_top", page.window.top)
        # 窗口大小改变时保存大小
        elif e.data == "resized":
            if page.window.width is not None and page.window.height is not None:
                config_service.set_config_value("window_width", page.window.width)
                config_service.set_config_value("window_height", page.window.height)
    
    page.on_window_event = on_window_event


# 启动应用
if __name__ == "__main__":
    ft.app(target=main)
