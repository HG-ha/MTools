"""MyTools应用程序入口。

多功能桌面应用程序，集成了图片处理、音视频处理、编码转换、代码格式化等功能。
遵循Material Design设计原则，使用Flet框架开发。
"""

import flet as ft

from constants import (
    APP_TITLE,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
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
    
    # 配置页面属性
    page.title = APP_TITLE
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.min_width = WINDOW_MIN_WIDTH
    page.window.min_height = WINDOW_MIN_HEIGHT
    
    # 隐藏系统标题栏，使用自定义标题栏
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    
    # 设置浅色主题 - 使用柔和的Material Design 3
    page.theme = ft.Theme(
        color_scheme_seed="#667EEA",  # 柔和的蓝紫色
        use_material3=True,
        font_family=saved_font,  # 使用保存的字体
        # 页面和组件颜色配置
        scaffold_bgcolor="#F8F9FA",  # 浅灰背景
        card_color="#FFFFFF",         # 白色卡片
        # 导航栏主题
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor="#FFFFFF",
        ),
    )
    
    # 设置深色主题
    page.dark_theme = ft.Theme(
        color_scheme_seed="#667EEA",  # 使用相同的种子色
        use_material3=True,
        font_family=saved_font,  # 使用保存的字体
        # 深色模式颜色配置
        scaffold_bgcolor="#121212",  # 深色背景
        card_color="#2C2C2C",        # 深色卡片
        # 深色导航栏主题
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor="#1E1E1E",
        ),
    )
    
    # 默认跟随系统主题
    page.theme_mode = ft.ThemeMode.SYSTEM
    
    # 设置页面布局
    page.padding = 0
    page.spacing = 0
    
    # 创建并添加主视图
    main_view: MainView = MainView(page)
    page.add(main_view)
    
    # 更新页面
    page.update()


# 启动应用
if __name__ == "__main__":
    ft.app(target=main)
