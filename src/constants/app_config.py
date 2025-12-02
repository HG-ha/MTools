# -*- coding: utf-8 -*-
"""应用配置常量定义。

本模块定义了应用的全局配置常量，包括颜色、尺寸、标题等。
遵循Material Design设计原则，追求柔和、现代的视觉效果。
"""

from typing import Final

# 应用基本信息
APP_TITLE: Final[str] = "MTools - 多功能工具箱"
APP_VERSION: Final[str] = "0.1.1"
APP_DESCRIPTION: Final[str] = "一个多功能工具箱，集成了图片处理、音视频处理、编码转换、代码格式化等功能"

# 窗口配置
WINDOW_WIDTH: Final[int] = 1070
WINDOW_HEIGHT: Final[int] = 700
WINDOW_MIN_WIDTH: Final[int] = 800
WINDOW_MIN_HEIGHT: Final[int] = 600

# 颜色配置 - 柔和的Material Design调色板
PRIMARY_COLOR: Final[str] = "#667EEA"  # 柔和的蓝紫色
PRIMARY_LIGHT: Final[str] = "#9FA8EA"  # 浅色主色
PRIMARY_DARK: Final[str] = "#4C5FD5"   # 深色主色
SECONDARY_COLOR: Final[str] = "#64B5F6"  # 柔和的蓝色
ACCENT_COLOR: Final[str] = "#F093FB"   # 粉紫色强调色
ERROR_COLOR: Final[str] = "#EF5350"    # 柔和的红色
SUCCESS_COLOR: Final[str] = "#66BB6A"  # 柔和的绿色
WARNING_COLOR: Final[str] = "#FFA726"  # 柔和的橙色

# 背景和表面颜色 - 浅色模式
BACKGROUND_COLOR: Final[str] = "#F8F9FA"     # 浅灰背景
SURFACE_COLOR: Final[str] = "#FFFFFF"        # 白色表面
SURFACE_VARIANT: Final[str] = "#F0F2F5"      # 变体表面
CARD_BACKGROUND: Final[str] = "#FFFFFF"      # 卡片背景

# 背景和表面颜色 - 深色模式
DARK_BACKGROUND_COLOR: Final[str] = "#121212"    # 深色背景
DARK_SURFACE_COLOR: Final[str] = "#1E1E1E"       # 深色表面
DARK_SURFACE_VARIANT: Final[str] = "#2C2C2C"     # 深色变体表面
DARK_CARD_BACKGROUND: Final[str] = "#2C2C2C"     # 深色卡片背景

# 文本颜色
TEXT_PRIMARY: Final[str] = "#1F2937"         # 主要文本
TEXT_SECONDARY: Final[str] = "#6B7280"       # 次要文本
TEXT_DISABLED: Final[str] = "#9CA3AF"        # 禁用文本

# 渐变色配置
GRADIENT_START: Final[str] = "#667EEA"       # 渐变起始色
GRADIENT_END: Final[str] = "#764BA2"         # 渐变结束色

# 导航配置
NAVIGATION_RAIL_WIDTH: Final[int] = 100
NAVIGATION_RAIL_EXTENDED_WIDTH: Final[int] = 200
NAVIGATION_BG_COLOR: Final[str] = "#FFFFFF"

# 间距配置
PADDING_SMALL: Final[int] = 8
PADDING_MEDIUM: Final[int] = 16
PADDING_LARGE: Final[int] = 24
PADDING_XLARGE: Final[int] = 32

# 圆角配置
BORDER_RADIUS_SMALL: Final[int] = 8
BORDER_RADIUS_MEDIUM: Final[int] = 12
BORDER_RADIUS_LARGE: Final[int] = 16
BORDER_RADIUS_XLARGE: Final[int] = 20

# 阴影配置
CARD_ELEVATION: Final[int] = 2
CARD_HOVER_ELEVATION: Final[int] = 8

# 图标尺寸
ICON_SIZE_SMALL: Final[int] = 20
ICON_SIZE_MEDIUM: Final[int] = 32
ICON_SIZE_LARGE: Final[int] = 48
ICON_SIZE_XLARGE: Final[int] = 64

