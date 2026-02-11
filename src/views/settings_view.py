# -*- coding: utf-8 -*-
"""设置视图模块。

提供应用设置界面，包括数据目录设置、主题设置等。
等待后续优化...
"""

from pathlib import Path
from typing import Optional, List, Dict
import threading
import time
import sys
import platform
import webbrowser
from utils import logger
from utils.file_utils import get_system_fonts

import flet as ft
import httpx

from constants import (
    APP_VERSION,
    BUILD_CUDA_VARIANT,
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, UpdateService, UpdateInfo, UpdateStatus
from services.auto_updater import AutoUpdater
from constants import APP_DESCRIPTION


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


class SettingsView(ft.Container):
    """设置视图类。
    
    提供应用设置功能，包括：
    - 数据存储目录设置
    - 默认/自定义目录切换
    - 目录浏览和选择
    """

    def __init__(self, page: ft.Page, config_service: ConfigService) -> None:
        """初始化设置视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
        """
        super().__init__()
        self._page: ft.Page = page
        self._saved_page: ft.Page = page  # 保存页面引用,防止在布局重建后丢失
        self.config_service: ConfigService = config_service
        self.expand: bool = True
        # 左右边距使用 PADDING_LARGE
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 必应壁纸相关变量
        self.bing_wallpapers: List[Dict] = []  # 存储8张壁纸信息
        self.current_wallpaper_index: int = 0  # 当前壁纸索引
        self.auto_switch_timer: Optional[threading.Timer] = None  # 自动切换定时器
        
        # 恢复自定义字体（如果之前已设置）- 提前调用以验证字体有效性
        self._restore_custom_font()
        
        # 创建UI组件
        self._build_ui()
        
        # 恢复自动切换状态（如果之前已启用）
        self._restore_auto_switch_state()
        
        # 初始化文件选择器
        self._init_file_picker()

    def _init_file_picker(self) -> None:
        """初始化文件选择器（Flet 1.0 不再需要预先创建）。"""
        # Flet 1.0 使用 await ft.FilePicker().pick_files() 方式，不再需要预先创建
        pass
    
    def _restore_custom_font(self) -> None:
        """恢复自定义字体（在初始化时调用）。"""
        try:
            custom_font_file = self.config_service.get_config_value("custom_font_file", None)
            
            if custom_font_file:
                from pathlib import Path
                font_path = Path(custom_font_file)
                
                # 获取字体名称
                font_name = font_path.stem
                custom_font_key = f"CustomFont_{font_name}"
                
                # 检查当前使用的字体是否是这个自定义字体
                current_font = self.config_service.get_config_value("font_family", "System")
                is_using_custom_font = current_font == custom_font_key
                
                if font_path.exists():
                    # 将字体添加到页面（即使当前不使用，也加载以便切换时可用）
                    if not hasattr(self._page, 'fonts') or self._page.fonts is None:
                        self._page.fonts = {}
                    
                    self._page.fonts[custom_font_key] = str(font_path)
                    # 不在 init 阶段调用 page.update()，让外部统一刷新
                    
                    # 只有当前正在使用这个自定义字体时，才记录恢复日志
                    if is_using_custom_font:
                        logger.info(f"成功恢复自定义字体: {custom_font_file}")
                else:
                    logger.warning(f"自定义字体文件不存在: {custom_font_file}")
                    # 清除无效的字体配置
                    self.config_service.set_config_value("custom_font_file", None)
                    
                    # 如果当前字体设置了这个自定义字体，重置为系统默认
                    if is_using_custom_font:
                        self.config_service.set_config_value("font_family", "System")
                        logger.info("因自定义字体文件丢失，已重置为系统默认字体")
                    
        except Exception as e:
            logger.error(f"恢复自定义字体失败: {e}")
    
    def _restore_auto_switch_state(self) -> None:
        """恢复自动切换状态（在初始化时调用）。"""
        auto_switch_enabled = self.config_service.get_config_value("wallpaper_auto_switch", False)
        current_bg = self.config_service.get_config_value("background_image", None)
        
        # 检查当前背景是否是必应壁纸URL（包含bing.com）
        is_bing_wallpaper = current_bg and isinstance(current_bg, str) and "bing.com" in current_bg.lower()
        
        if auto_switch_enabled or is_bing_wallpaper:
            # 如果启用了自动切换，或者当前使用的是必应壁纸，则自动获取壁纸列表
            # 使用异步任务获取，避免阻塞UI启动
            async def async_fetch_wallpapers():
                import asyncio
                wallpapers = await asyncio.to_thread(self._fetch_bing_wallpaper)
                if wallpapers:
                    self.bing_wallpapers = wallpapers
                    
                    # 尝试找到当前壁纸在列表中的位置
                    if is_bing_wallpaper:
                        for i, wp in enumerate(wallpapers):
                            if wp["url"] == current_bg:
                                self.current_wallpaper_index = i
                                break
                    
                    # 更新UI
                    self._update_wallpaper_info_ui()
                    
                    # 如果启用了自动切换，启动定时器
                    if auto_switch_enabled:
                        interval = self.config_service.get_config_value("wallpaper_switch_interval", 30)
                        self._start_auto_switch(interval)
            
            self._page.run_task(async_fetch_wallpapers)
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 页面标题
        title: ft.Text = ft.Text(
            "设置",
            size=32,
            weight=ft.FontWeight.BOLD,
        )
        
        # 快捷功能设置部分（放在顶部）
        hotkey_section: ft.Container = self._build_hotkey_section()
        
        # 数据目录设置部分
        data_dir_section: ft.Container = self._build_data_dir_section()
        
        # 输出文件设置部分
        output_settings_section: ft.Container = self._build_output_settings_section()
        
        # 主题模式设置部分
        theme_mode_section: ft.Container = self._build_theme_mode_section()
        
        # 主题色设置部分
        theme_color_section: ft.Container = self._build_theme_color_section()
        
        # 外观设置部分（透明度和背景图片）
        appearance_section: ft.Container = self._build_appearance_section()
        
        # 界面设置部分
        interface_section: ft.Container = self._build_interface_section()
        
        # GPU加速设置部分
        gpu_acceleration_section: ft.Container = self._build_gpu_acceleration_section()
        
        # 性能优化设置部分
        performance_section: ft.Container = self._build_performance_optimization_section()
        
        # 字体设置部分
        font_section: ft.Container = self._build_font_section()
        
        # 关于部分
        about_section: ft.Container = self._build_about_section()
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                title,
                ft.Container(height=PADDING_LARGE),
                hotkey_section,
                ft.Container(height=PADDING_LARGE),
                data_dir_section,
                ft.Container(height=PADDING_LARGE),
                output_settings_section,
                ft.Container(height=PADDING_LARGE),
                theme_mode_section,
                ft.Container(height=PADDING_LARGE),
                theme_color_section,
                ft.Container(height=PADDING_LARGE),
                appearance_section,
                ft.Container(height=PADDING_LARGE),
                interface_section,
                ft.Container(height=PADDING_LARGE),
                gpu_acceleration_section,
                ft.Container(height=PADDING_LARGE),
                performance_section,
                ft.Container(height=PADDING_LARGE),
                font_section,
                ft.Container(height=PADDING_LARGE),
                about_section,
            ],
            spacing=0,
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
            expand=True,
            width=float('inf'),  # 占满可用宽度
        )
    
    def _build_theme_mode_section(self) -> ft.Container:
        """构建主题模式设置部分。
        
        Returns:
            主题模式设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "主题模式",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 获取当前保存的主题模式
        saved_theme_mode = self.config_service.get_config_value("theme_mode", "system")
        
        # 主题模式单选按钮
        self.theme_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.BRIGHTNESS_AUTO, size=32, ),
                                ft.Text("跟随系统", size=14, weight=ft.FontWeight.W_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        data="system",
                        width=120,
                        height=100,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        border=ft.border.all(2 if saved_theme_mode == "system" else 1, ft.Colors.PRIMARY if saved_theme_mode == "system" else ft.Colors.OUTLINE),
                        padding=PADDING_MEDIUM,
                        ink=True,
                        on_click=lambda e: self._on_theme_mode_container_click("system"),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.LIGHT_MODE, size=32, ),
                                ft.Text("浅色模式", size=14, weight=ft.FontWeight.W_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        data="light",
                        width=120,
                        height=100,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        border=ft.border.all(2 if saved_theme_mode == "light" else 1, ft.Colors.PRIMARY if saved_theme_mode == "light" else ft.Colors.OUTLINE),
                        padding=PADDING_MEDIUM,
                        ink=True,
                        on_click=lambda e: self._on_theme_mode_container_click("light"),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.DARK_MODE, size=32, ),
                                ft.Text("深色模式", size=14, weight=ft.FontWeight.W_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        data="dark",
                        width=120,
                        height=100,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        border=ft.border.all(2 if saved_theme_mode == "dark" else 1, ft.Colors.PRIMARY if saved_theme_mode == "dark" else ft.Colors.OUTLINE),
                        padding=PADDING_MEDIUM,
                        ink=True,
                        on_click=lambda e: self._on_theme_mode_container_click("dark"),
                    ),
                ],
                spacing=PADDING_LARGE,
            ),
            value=saved_theme_mode,
        )
        
        # 保存主题模式容器的引用，用于更新样式
        self.theme_mode_containers: list = [
            self.theme_mode_radio.content.controls[0],
            self.theme_mode_radio.content.controls[1],
            self.theme_mode_radio.content.controls[2],
        ]
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "主题模式会立即生效",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 组装主题模式设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.theme_mode_radio,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_theme_mode_container_click(self, mode: str) -> None:
        """主题模式容器点击事件处理。
        
        Args:
            mode: 主题模式 ("system", "light", "dark")
        """
        # 更新RadioGroup的值
        self.theme_mode_radio.value = mode
        
        # 保存到配置
        if self.config_service.set_config_value("theme_mode", mode):
            # 通过 _saved_page 获取页面引用(因为 self._page 可能在布局重建后失效)
            page = getattr(self, '_saved_page', self._page)
            # 立即应用主题模式
            if page:
                if mode == "system":
                    page.theme_mode = ft.ThemeMode.SYSTEM
                elif mode == "light":
                    page.theme_mode = ft.ThemeMode.LIGHT
                else:  # dark
                    page.theme_mode = ft.ThemeMode.DARK
            
            # 更新所有容器的边框样式
            for container in self.theme_mode_containers:
                is_selected = container.data == mode
                container.border = ft.border.all(
                    2 if is_selected else 1,
                    ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE
                )
            
            if page:
                page.update()
            self._show_snackbar(f"已切换到{self._get_mode_name(mode)}", ft.Colors.GREEN)
        else:
            self._show_snackbar("主题模式更新失败", ft.Colors.RED)
    
    def _get_mode_name(self, mode: str) -> str:
        """获取主题模式的中文名称。
        
        Args:
            mode: 主题模式
        
        Returns:
            中文名称
        """
        mode_names = {
            "system": "跟随系统",
            "light": "浅色模式",
            "dark": "深色模式",
        }
        return mode_names.get(mode, mode)
    
    # ========== 快捷功能相关 ==========
    
    # 可用的主键列表
    AVAILABLE_KEYS = [
        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
        "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    ]
    
    # Windows 虚拟键码映射
    VK_CODES = {
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
        "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
        "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45, "F": 0x46,
        "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A, "K": 0x4B, "L": 0x4C,
        "M": 0x4D, "N": 0x4E, "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52,
        "S": 0x53, "T": 0x54, "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58,
        "Y": 0x59, "Z": 0x5A,
        "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
        "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    }
    
    def _get_hotkey_display(self, config: dict) -> str:
        """获取快捷键显示文本（macOS 使用符号）。"""
        is_mac = sys.platform == 'darwin'
        parts = []
        if config.get("ctrl"):
            parts.append("⌃" if is_mac else "Ctrl")
        if config.get("alt"):
            parts.append("⌥" if is_mac else "Alt")
        if config.get("shift"):
            parts.append("⇧" if is_mac else "Shift")
        parts.append(config.get("key", ""))
        return "+".join(parts) if parts else "未设置"
    
    def _build_hotkey_section(self) -> ft.Container:
        """构建快捷功能设置部分。"""
        # 分区标题
        section_title = ft.Text(
            "快捷功能",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 检查平台支持（Windows + macOS）
        is_hotkey_supported = sys.platform in ('win32', 'darwin')
        is_mac = sys.platform == 'darwin'
        # 兼容旧变量名：整个方法中大量使用 is_windows
        is_windows = is_hotkey_supported
        # macOS 修饰键标签
        _ctrl_label = "⌃ Control" if is_mac else "Ctrl"
        _alt_label = "⌥ Option" if is_mac else "Alt"
        _shift_label = "⇧ Shift" if is_mac else "Shift"
        platform_hint = ""
        if not is_hotkey_supported:
            platform_hint = "（当前系统不支持全局快捷键）"
        
        section_desc = ft.Text(
            f"通过快捷键快速调用功能，无需打开工具界面{platform_hint}",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 加载已保存的快捷键配置
        ocr_hotkey = self.config_service.get_config_value("ocr_hotkey", {
            "ctrl": True, "shift": True, "alt": False, "key": "Q"
        })
        ocr_hotkey_enabled = self.config_service.get_config_value("ocr_hotkey_enabled", True)
        
        screen_record_hotkey = self.config_service.get_config_value("screen_record_hotkey", {
            "ctrl": True, "shift": True, "alt": False, "key": "C"
        })
        screen_record_hotkey_enabled = self.config_service.get_config_value("screen_record_hotkey_enabled", True)
        
        # 预加载 OCR 模型开关
        preload_ocr = self.config_service.get_config_value("preload_ocr_model", False)
        
        # OCR 快捷键开关
        self.ocr_hotkey_switch = ft.Switch(
            value=ocr_hotkey_enabled and is_windows,
            on_change=lambda e: self._on_hotkey_enabled_change("ocr", e),
            disabled=not is_windows,
        )
        
        # OCR 快捷键配置
        self.ocr_ctrl_cb = ft.Checkbox(label=_ctrl_label, value=ocr_hotkey.get("ctrl", True), 
                                        on_change=lambda e: self._on_hotkey_change("ocr"), 
                                        disabled=not is_windows or not ocr_hotkey_enabled)
        self.ocr_alt_cb = ft.Checkbox(label=_alt_label, value=ocr_hotkey.get("alt", False),
                                       on_change=lambda e: self._on_hotkey_change("ocr"), 
                                       disabled=not is_windows or not ocr_hotkey_enabled)
        self.ocr_shift_cb = ft.Checkbox(label=_shift_label, value=ocr_hotkey.get("shift", True),
                                         on_change=lambda e: self._on_hotkey_change("ocr"), 
                                         disabled=not is_windows or not ocr_hotkey_enabled)
        self.ocr_key_dropdown = ft.Dropdown(
            value=ocr_hotkey.get("key", "Q"),
            options=[ft.dropdown.Option(k) for k in self.AVAILABLE_KEYS],
            on_select=lambda e: self._on_hotkey_change("ocr"),
            width=80,
            dense=True,
            disabled=not is_windows or not ocr_hotkey_enabled,
        )
        
        # 预加载开关
        self.preload_ocr_switch = ft.Checkbox(
            label="预加载模型",
            value=preload_ocr,
            on_change=self._on_preload_ocr_change,
            disabled=not is_windows or not ocr_hotkey_enabled,
        )
        
        # OCR 功能卡片
        ocr_hotkey_row = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            # 固定宽度的开关容器，确保对齐
                            ft.Container(
                                content=self.ocr_hotkey_switch,
                                width=60,
                                alignment=ft.Alignment.CENTER_LEFT,
                            ),
                            ft.Icon(ft.Icons.TEXT_FIELDS, size=20, color=ft.Colors.PRIMARY),
                            ft.Text("OCR 截图识别", size=14, weight=ft.FontWeight.W_500),
                            ft.Container(expand=True),
                            ft.Text(
                                f"{self._get_hotkey_display(ocr_hotkey)}",
                                size=12,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.PRIMARY if ocr_hotkey_enabled else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(width=60),  # 与开关对齐
                            self.ocr_ctrl_cb,
                            self.ocr_alt_cb,
                            self.ocr_shift_cb,
                            ft.Text("+", size=12),
                            self.ocr_key_dropdown,
                            ft.Container(width=30),
                            self.preload_ocr_switch,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        visible=ocr_hotkey_enabled,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(12),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
            border_radius=8,
        )
        self.ocr_hotkey_label = ocr_hotkey_row.content.controls[0].controls[-1]
        self.ocr_config_row = ocr_hotkey_row.content.controls[1]
        
        # 录屏快捷键开关
        self.record_hotkey_switch = ft.Switch(
            value=screen_record_hotkey_enabled and is_windows,
            on_change=lambda e: self._on_hotkey_enabled_change("screen_record", e),
            disabled=not is_windows,
        )
        
        # 录屏快捷键配置
        self.record_ctrl_cb = ft.Checkbox(label=_ctrl_label, value=screen_record_hotkey.get("ctrl", True),
                                           on_change=lambda e: self._on_hotkey_change("screen_record"), 
                                           disabled=not is_windows or not screen_record_hotkey_enabled)
        self.record_alt_cb = ft.Checkbox(label=_alt_label, value=screen_record_hotkey.get("alt", False),
                                          on_change=lambda e: self._on_hotkey_change("screen_record"), 
                                          disabled=not is_windows or not screen_record_hotkey_enabled)
        self.record_shift_cb = ft.Checkbox(label=_shift_label, value=screen_record_hotkey.get("shift", True),
                                            on_change=lambda e: self._on_hotkey_change("screen_record"), 
                                            disabled=not is_windows or not screen_record_hotkey_enabled)
        self.record_key_dropdown = ft.Dropdown(
            value=screen_record_hotkey.get("key", "C"),
            options=[ft.dropdown.Option(k) for k in self.AVAILABLE_KEYS],
            on_select=lambda e: self._on_hotkey_change("screen_record"),
            width=80,
            dense=True,
            disabled=not is_windows or not screen_record_hotkey_enabled,
        )
        
        # 录屏功能卡片
        record_hotkey_row = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            # 固定宽度的开关容器，确保对齐
                            ft.Container(
                                content=self.record_hotkey_switch,
                                width=60,
                                alignment=ft.Alignment.CENTER_LEFT,
                            ),
                            ft.Icon(ft.Icons.VIDEOCAM, size=20, color=ft.Colors.PRIMARY),
                            ft.Text("屏幕录制", size=14, weight=ft.FontWeight.W_500),
                            ft.Container(expand=True),
                            ft.Text(
                                f"{self._get_hotkey_display(screen_record_hotkey)}",
                                size=12,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.PRIMARY if screen_record_hotkey_enabled else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(width=60),  # 与开关对齐
                            self.record_ctrl_cb,
                            self.record_alt_cb,
                            self.record_shift_cb,
                            ft.Text("+", size=12),
                            self.record_key_dropdown,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        visible=screen_record_hotkey_enabled,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(12),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
            border_radius=8,
        )
        self.record_hotkey_label = record_hotkey_row.content.controls[0].controls[-1]
        self.record_config_row = record_hotkey_row.content.controls[1]
        
        # 提示信息
        hint_row = ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.INFO_OUTLINE if is_hotkey_supported else ft.Icons.WARNING_AMBER,
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT if is_hotkey_supported else ft.Colors.ORANGE,
                ),
                ft.Text(
                    "快捷键在全局生效，可在任意应用中使用。" if is_hotkey_supported else "全局快捷键功能仅支持 Windows / macOS 系统。",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT if is_hotkey_supported else ft.Colors.ORANGE,
                ),
            ],
            spacing=6,
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    section_desc,
                    ft.Container(height=8),
                    ocr_hotkey_row,
                    ft.Container(height=8),  # 间距
                    record_hotkey_row,
                    ft.Container(height=12),
                    hint_row,
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_hotkey_change(self, hotkey_type: str) -> None:
        """处理快捷键变化。"""
        if hotkey_type == "ocr":
            config = {
                "ctrl": self.ocr_ctrl_cb.value,
                "alt": self.ocr_alt_cb.value,
                "shift": self.ocr_shift_cb.value,
                "key": self.ocr_key_dropdown.value,
            }
            self.config_service.set_config_value("ocr_hotkey", config)
            if hasattr(self, 'ocr_hotkey_label'):
                self.ocr_hotkey_label.value = self._get_hotkey_display(config)
        elif hotkey_type == "screen_record":
            config = {
                "ctrl": self.record_ctrl_cb.value,
                "alt": self.record_alt_cb.value,
                "shift": self.record_shift_cb.value,
                "key": self.record_key_dropdown.value,
            }
            self.config_service.set_config_value("screen_record_hotkey", config)
            if hasattr(self, 'record_hotkey_label'):
                self.record_hotkey_label.value = self._get_hotkey_display(config)
        
        self.config_service.save_config()
        
        # 重启全局热键服务以应用新配置
        self._restart_global_hotkey_service()
        
        try:
            self._page.update()
        except Exception:
            pass
    
    def _restart_global_hotkey_service(self) -> None:
        """重启全局热键服务。"""
        try:
            # 尝试从 main_view 获取全局热键服务
            if self._page and self._page.controls:
                main_view = self._page.controls[0]
                if hasattr(main_view, 'global_hotkey_service'):
                    service = main_view.global_hotkey_service
                    if service:
                        # 检查是否有任一功能启用
                        ocr_enabled = self.config_service.get_config_value("ocr_hotkey_enabled", True)
                        record_enabled = self.config_service.get_config_value("screen_record_hotkey_enabled", True)
                        
                        if ocr_enabled or record_enabled:
                            service.restart()
                            logger.info("全局热键服务已重启")
                        else:
                            service.stop()
                            logger.info("全局热键服务已停止")
        except Exception as ex:
            logger.warning(f"重启全局热键服务失败: {ex}")
    
    def _on_hotkey_enabled_change(self, func_type: str, e) -> None:
        """处理快捷功能开关变化。
        
        Args:
            func_type: 功能类型，"ocr" 或 "screen_record"
            e: 事件对象
        """
        enabled = e.control.value
        config_key = f"{func_type}_hotkey_enabled"
        self.config_service.set_config_value(config_key, enabled)
        self.config_service.save_config()
        
        if func_type == "ocr":
            # 更新 OCR 相关控件状态
            if hasattr(self, 'ocr_ctrl_cb'):
                self.ocr_ctrl_cb.disabled = not enabled
                self.ocr_alt_cb.disabled = not enabled
                self.ocr_shift_cb.disabled = not enabled
                self.ocr_key_dropdown.disabled = not enabled
            if hasattr(self, 'preload_ocr_switch'):
                self.preload_ocr_switch.disabled = not enabled
            if hasattr(self, 'ocr_config_row'):
                self.ocr_config_row.visible = enabled
            if hasattr(self, 'ocr_hotkey_label'):
                self.ocr_hotkey_label.color = ft.Colors.PRIMARY if enabled else ft.Colors.ON_SURFACE_VARIANT
        elif func_type == "screen_record":
            # 更新录屏相关控件状态
            if hasattr(self, 'record_ctrl_cb'):
                self.record_ctrl_cb.disabled = not enabled
                self.record_alt_cb.disabled = not enabled
                self.record_shift_cb.disabled = not enabled
                self.record_key_dropdown.disabled = not enabled
            if hasattr(self, 'record_config_row'):
                self.record_config_row.visible = enabled
            if hasattr(self, 'record_hotkey_label'):
                self.record_hotkey_label.color = ft.Colors.PRIMARY if enabled else ft.Colors.ON_SURFACE_VARIANT
        
        # 重启热键服务
        self._restart_global_hotkey_service()
        
        try:
            self._page.update()
        except Exception:
            pass
    
    def _on_preload_ocr_change(self, e) -> None:
        """处理预加载 OCR 模型开关变化。"""
        preload = e.control.value
        self.config_service.set_config_value("preload_ocr_model", preload)
        self.config_service.save_config()
        
        if preload:
            # 立即预加载 OCR 模型
            self._preload_ocr_model()
    
    def _preload_ocr_model(self) -> None:
        """预加载 OCR 模型。"""
        import threading
        
        def load():
            try:
                from services import OCRService
                from constants import DEFAULT_OCR_MODEL_KEY
                
                ocr_service = OCRService(self.config_service)
                model_key = self.config_service.get_config_value("ocr_model_key", DEFAULT_OCR_MODEL_KEY)
                use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
                
                success, message = ocr_service.load_model(
                    model_key,
                    use_gpu=use_gpu,
                    progress_callback=lambda p, m: None
                )
                
                if success:
                    # 保存到全局热键服务
                    if self._page and self._page.controls:
                        main_view = self._page.controls[0]
                        if hasattr(main_view, 'global_hotkey_service'):
                            main_view.global_hotkey_service._ocr_service = ocr_service
                    logger.info("OCR 模型已预加载")
                else:
                    logger.warning(f"OCR 模型预加载失败: {message}")
            except Exception as ex:
                logger.error(f"预加载 OCR 模型失败: {ex}")
        
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
    
    def _build_data_dir_section(self) -> ft.Container:
        """构建数据目录设置部分。
        
        Returns:
            数据目录设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "数据存储",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 当前数据目录显示
        current_dir: Path = self.config_service.get_data_dir()
        default_dir: Path = self.config_service._get_default_data_dir()
        
        # 实际检查目录是否为默认目录
        is_custom: bool = (current_dir != default_dir)
        
        # 如果配置与实际不符，更新配置
        config_is_custom = self.config_service.get_config_value("use_custom_dir", False)
        if config_is_custom != is_custom:
            self.config_service.set_config_value("use_custom_dir", is_custom)
        
        self.data_dir_text: ft.Text = ft.Text(
            str(current_dir),
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
            selectable=True,
        )
        
        # 目录类型单选按钮
        self.dir_type_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value="default",
                        label="默认路径",
                    ),
                    ft.Radio(
                        value="custom",
                        label="自定义路径",
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="custom" if is_custom else "default",
            on_change=self._on_dir_type_change,
        )
        
        # 浏览按钮
        browse_button: ft.Button = ft.Button(
            content="浏览...",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._on_browse_click,
            disabled=not is_custom,
        )
        
        self.browse_button: ft.Button = browse_button
        
        # 打开目录按钮
        open_dir_button: ft.OutlinedButton = ft.OutlinedButton(
            content="打开数据目录",
            icon=ft.Icons.FOLDER,
            on_click=self._on_open_dir_click,
        )
        
        # 按钮行
        button_row: ft.Row = ft.Row(
            controls=[browse_button, open_dir_button],
            spacing=PADDING_MEDIUM,
        )
        
        # 目录路径容器
        dir_path_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("当前数据目录:", size=14, weight=ft.FontWeight.W_500),
                    self.data_dir_text,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "数据目录用于存储应用的模型文件、处理结果和临时文件，建议选择存储空间较大的目录。请确保放到一个单独的目录中，避免与其他应用的数据混淆。",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 组装数据目录部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.dir_type_radio,
                    ft.Container(height=PADDING_MEDIUM),
                    dir_path_container,
                    ft.Container(height=PADDING_MEDIUM),
                    button_row,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _build_output_settings_section(self) -> ft.Container:
        """构建输出文件设置部分。
        
        Returns:
            输出文件设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "输出文件",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 获取当前设置
        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
        
        # 文件已存在时添加序号选项
        self.add_sequence_checkbox = ft.Checkbox(
            label="文件已存在时添加序号（不覆盖原文件）",
            value=add_sequence,
            on_change=self._on_add_sequence_change,
        )
        
        # 说明文字
        info_row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(
                    "启用后，当输出文件已存在时会自动添加序号（如 file_1.mp4），否则直接覆盖原文件。此设置对所有工具生效。",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    expand=True,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 组装输出文件设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.add_sequence_checkbox,
                    ft.Container(height=PADDING_SMALL),
                    info_row,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_add_sequence_change(self, e: ft.ControlEvent) -> None:
        """文件已存在时添加序号选项变更。"""
        self.config_service.set_config_value("output_add_sequence", e.control.value)
    
    def _get_gpu_device_options(self) -> list:
        """获取可用的GPU设备选项列表。
        
        根据当前的加速方式（CUDA/DirectML/CoreML）返回对应的设备列表：
        - CUDA: 只显示 NVIDIA GPU（因为 CUDA 只能看到 NVIDIA 设备）
        - DirectML: 显示所有 GPU，但设备选择不生效
        - 其他: 显示所有检测到的 GPU
        
        Returns:
            GPU设备选项列表
        """
        from utils import get_available_compute_devices, get_primary_provider
        
        gpu_options = []
        primary_provider = get_primary_provider()
        
        try:
            # 获取计算设备信息（硬件 + ONNX Runtime Provider）
            compute_info = get_available_compute_devices()
            gpus = compute_info.get("gpus", [])
            
            # CUDA 模式：使用 nvidia-smi 获取准确的 CUDA 设备列表
            if primary_provider == "CUDA":
                from utils import get_cuda_devices
                cuda_gpus = get_cuda_devices()
                
                if cuda_gpus:
                    for gpu in cuda_gpus:
                        cuda_idx = gpu.get("index", 0)
                        name = gpu.get("name", "Unknown GPU")
                        display_text = f"🎮 CUDA {cuda_idx}: {name}"
                        gpu_options.append(ft.dropdown.Option(str(cuda_idx), display_text))
                    return gpu_options
                else:
                    # 没有检测到 NVIDIA GPU，但用户使用的是 CUDA 版本
                    # 显示提示选项，程序会自动回退到 CPU
                    return [
                        ft.dropdown.Option("0", "⚠️ 未检测到 NVIDIA GPU (将使用 CPU)"),
                    ]
            
            # 其他模式：显示所有 GPU
            for gpu in gpus:
                index = gpu.get("index", 0)
                name = gpu.get("name", "Unknown GPU")
                acceleration = gpu.get("acceleration", [])
                
                # 构建显示文本
                if acceleration:
                    accel_text = "/".join(acceleration)
                    display_text = f"🎮 GPU {index}: {name} ({accel_text})"
                else:
                    display_text = f"🎮 GPU {index}: {name} (CPU 回退)"
                
                gpu_options.append(ft.dropdown.Option(str(index), display_text))
            
            if gpu_options:
                return gpu_options
                
        except Exception as e:
            logger.warning(f"获取 GPU 设备列表失败: {e}")
        
        # 后备选项（如果检测失败）
        return [
            ft.dropdown.Option("0", "🎮 GPU 0 (默认)"),
        ]
    
    def _build_appearance_section(self) -> ft.Container:
        """构建外观设置部分（透明度和背景图片）。
        
        Returns:
            外观设置容器
        """
        section_title = ft.Text(
            "外观",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 获取当前配置
        current_opacity = self.config_service.get_config_value("window_opacity", 1.0)
        current_bg_image = self.config_service.get_config_value("background_image", None)
        current_bg_fit = self.config_service.get_config_value("background_image_fit", "cover")
        
        # 不透明度滑块
        self.opacity_value_text = ft.Text(
            f"{int(current_opacity * 100)}%",
            size=13,
            text_align=ft.TextAlign.END,
            width=60,
        )
        
        self.opacity_slider = ft.Slider(
            min=0.3,
            max=1.0,
            value=current_opacity,
            divisions=14,
            # label 不使用,因为格式化不够灵活,使用右侧文本显示
            on_change=self._on_opacity_change,
        )
        
        opacity_row = ft.Row(
            controls=[
                ft.Text("窗口不透明度", size=13),  # 改为"不透明度"更准确
                self.opacity_value_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        opacity_container = ft.Column(
            controls=[
                opacity_row,
                self.opacity_slider,
                ft.Text(
                    "调整窗口的不透明度（30%-100%，数值越低越透明）",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 背景图片设置
        # 如果当前背景是必应壁纸，显示友好的提示文本
        bg_text_display = current_bg_image if current_bg_image else "未设置"
        if current_bg_image and isinstance(current_bg_image, str) and "bing.com" in current_bg_image.lower():
            bg_text_display = "必应壁纸"  # 先显示"必应壁纸"，等信息加载后再更新具体标题
        
        self.bg_image_text = ft.Text(
            bg_text_display,
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )
        
        bg_image_row = ft.Row(
            controls=[
                ft.Text("背景图片:", size=13),
                self.bg_image_text,
                ft.IconButton(
                    icon=ft.Icons.FOLDER_OPEN,
                    tooltip="选择背景图片",
                    on_click=self._on_pick_bg_image,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLEAR,
                    tooltip="清除背景图片",
                    on_click=self._on_clear_bg_image,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 背景图片适应模式
        self.bg_fit_dropdown = ft.Dropdown(
            width=280,
            value=current_bg_fit,
            options=[
                ft.dropdown.Option("cover", "覆盖 - 填满窗口(可能裁剪)"),
                ft.dropdown.Option("contain", "适应 - 完整显示(可能留白)"),
                ft.dropdown.Option("fill", "拉伸 - 填满窗口(可能变形)"),
                ft.dropdown.Option("none", "原始尺寸 - 不缩放"),
            ],
            dense=True,
            on_select=self._on_bg_fit_change,
        )
        
        bg_fit_row = ft.Row(
            controls=[
                ft.Text("适应模式:", size=13),
                self.bg_fit_dropdown,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 创建壁纸计数和信息文本控件
        self.wallpaper_count_text = ft.Text(
            "0 / 0",
            size=12,
            weight=ft.FontWeight.W_500,
        )
        
        self.wallpaper_info_text = ft.Text(
            "点击「获取壁纸」从必应获取精美壁纸",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        
        self.switch_interval_text = ft.Text(
            f"{self.config_service.get_config_value('wallpaper_switch_interval', 30)} 分钟",
            size=12,
        )
        
        bg_image_container = ft.Column(
            controls=[
                bg_image_row,
                bg_fit_row,
                ft.Divider(height=PADDING_MEDIUM),
                # 必应壁纸部分
                ft.Text("必应壁纸", size=14, weight=ft.FontWeight.W_500),
                ft.Row(
                    controls=[
                        ft.Button(
                            content="获取壁纸",
                            icon=ft.Icons.CLOUD_DOWNLOAD,
                            on_click=self._on_random_wallpaper,
                            tooltip="从必应获取8张壁纸",
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK,
                            tooltip="上一张",
                            on_click=self._previous_wallpaper,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_FORWARD,
                            tooltip="下一张",
                            on_click=self._next_wallpaper,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD,
                            tooltip="下载当前壁纸",
                            on_click=self._on_download_wallpaper,
                        ),
                    ],
                    spacing=PADDING_SMALL,
                ),
                # 壁纸信息显示
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text("当前:", size=12),
                                    self.wallpaper_count_text,
                                ],
                                spacing=PADDING_SMALL,
                            ),
                            self.wallpaper_info_text,
                        ],
                        spacing=PADDING_SMALL // 2,
                    ),
                    padding=PADDING_SMALL,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                ),
                # 自动切换设置
                ft.Row(
                    controls=[
                        ft.Switch(
                            label="自动切换",
                            value=self.config_service.get_config_value("wallpaper_auto_switch", False),
                            on_change=self._on_auto_switch_change,
                        ),
                        self.switch_interval_text,
                    ],
                    spacing=PADDING_SMALL,
                ),
                ft.Slider(
                    min=5,
                    max=120,
                    divisions=23,
                    value=self.config_service.get_config_value("wallpaper_switch_interval", 30),
                    label="{value}分钟",
                    on_change=self._on_switch_interval_change,
                ),
                ft.Text(
                    "启用自动切换后，壁纸会按设定的时间间隔自动轮换（5-120分钟）",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    opacity_container,
                    ft.Container(height=PADDING_MEDIUM),
                    bg_image_container,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_opacity_change(self, e: ft.ControlEvent) -> None:
        """透明度改变事件。"""
        value = e.control.value
        self.opacity_value_text.value = f"{int(value * 100)}%"
        
        # 保存配置
        self.config_service.set_config_value("window_opacity", value)
        
        # 使用保存的页面引用
        page = getattr(self, '_saved_page', self._page)
        if not page:
            return
        
        # 立即应用透明度 - 使用 window.opacity
        page.window.opacity = value
        
        # 同时更新导航栏的透明度
        if hasattr(page, '_main_view') and hasattr(page._main_view, 'navigation_container'):
            # 根据窗口透明度调整导航栏背景透明度
            # 调整为与窗口透明度一致，避免视觉差异过大
            nav_opacity = 0.95 * value  # 从0.85改为0.95，让导航栏更接近窗口透明度
            page._main_view.navigation_container.bgcolor = ft.Colors.with_opacity(
                nav_opacity, 
                ft.Colors.SURFACE
            )
        
        # 同时更新 FAB 的透明度
        if hasattr(page, 'floating_action_button') and page.floating_action_button:
            fab_opacity = 0.9 * value  # FAB 保持较高的可见度
            page.floating_action_button.bgcolor = ft.Colors.with_opacity(
                fab_opacity,
                ft.Colors.PRIMARY
            )
        
        # 同时更新标题栏的透明度
        if hasattr(page, '_main_view') and hasattr(page._main_view, 'title_bar'):
            # 标题栏保持较高的不透明度以保持可读性
            title_bar_opacity = 0.95 * value
            theme_color = page._main_view.title_bar.theme_color
            page._main_view.title_bar.bgcolor = ft.Colors.with_opacity(
                title_bar_opacity,
                theme_color
            )
        
        page.update()
    
    async def _on_pick_bg_image(self, e: ft.ControlEvent) -> None:
        """选择背景图片。"""
        result = await ft.FilePicker().pick_files(
            allowed_extensions=["png", "jpg", "jpeg", "webp", "bmp"],
            dialog_title="选择背景图片"
        )
        if result and len(result) > 0:
            image_path = result[0].path
            self.bg_image_text.value = image_path
            
            # 保存配置
            self.config_service.set_config_value("background_image", image_path)
            
            # 立即应用背景图片
            self._apply_background_image(image_path, self.bg_fit_dropdown.value)
            
            # 更新页面
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
    
    def _on_clear_bg_image(self, e: ft.ControlEvent) -> None:
        """清除背景图片事件。"""
        self.bg_image_text.value = "未设置"
        
        # 保存配置
        self.config_service.set_config_value("background_image", None)
        
        # 清除背景图片
        self._apply_background_image(None, None)
        
        # 更新页面
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
    
    def _on_bg_fit_change(self, e: ft.ControlEvent) -> None:
        """背景图片适应模式改变事件。"""
        fit_mode = e.control.value
        
        # 保存配置
        self.config_service.set_config_value("background_image_fit", fit_mode)
        
        # 重新应用背景图片
        bg_image = self.config_service.get_config_value("background_image", None)
        if bg_image:
            self._apply_background_image(bg_image, fit_mode)
    
    def _apply_background_image(self, image_path: Optional[str], fit_mode: Optional[str]) -> None:
        """应用背景图片。"""
        # 通过 _saved_page 获取页面引用(因为 self._page 可能在布局重建后失效)
        page = getattr(self, '_saved_page', self._page)
        
        if not page:
            return
            
        # 应用背景图片
        if hasattr(page, '_main_view') and hasattr(page._main_view, 'apply_background'):
            page._main_view.apply_background(image_path, fit_mode)
            
        # 应用背景后,重新应用当前的窗口透明度和各组件的透明度
        current_opacity = self.config_service.get_config_value("window_opacity", 1.0)
        
        # 重新应用窗口透明度
        page.window.opacity = current_opacity
        
        # 重新应用导航栏透明度
        if hasattr(page, '_main_view') and hasattr(page._main_view, 'navigation_container'):
            nav_opacity = 0.85 * current_opacity
            page._main_view.navigation_container.bgcolor = ft.Colors.with_opacity(
                nav_opacity, 
                ft.Colors.SURFACE
            )
        
        # 重新应用 FAB 透明度
        if hasattr(page, 'floating_action_button') and page.floating_action_button:
            fab_opacity = 0.9 * current_opacity
            page.floating_action_button.bgcolor = ft.Colors.with_opacity(
                fab_opacity,
                ft.Colors.PRIMARY
            )
        
        # 重新应用标题栏透明度
        if hasattr(page, '_main_view') and hasattr(page._main_view, 'title_bar'):
            title_bar_opacity = 0.95 * current_opacity
            theme_color = page._main_view.title_bar.theme_color
            page._main_view.title_bar.bgcolor = ft.Colors.with_opacity(
                title_bar_opacity,
                theme_color
            )
        
        page.update()

    def _fetch_bing_wallpaper(self, n: int = 8) -> Optional[List[Dict]]:
        """使用 httpx 从必应壁纸 API 获取最近 n 张壁纸的信息。

        Args:
            n: 获取最近 n 张壁纸（默认8）

        Returns:
            壁纸信息列表，每项包含 url、title、copyright 等字段，失败时返回 None
        """
        try:
            api = f"https://www.bing.com/HPImageArchive.aspx?format=js&n={n}&mkt=zh-CN"
            resp = httpx.get(api, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            images = data.get("images", [])
            if not images:
                return None
            
            # 处理图片URL，确保是完整的URL
            wallpapers = []
            for img in images:
                url = img.get("url", "")
                if url:
                    # 如果是相对路径，拼接主域名
                    if not url.startswith("http"):
                        url = "https://www.bing.com" + url
                    wallpapers.append({
                        "url": url,
                        "title": img.get("title", ""),
                        "copyright": img.get("copyright", ""),
                        "startdate": img.get("startdate", ""),
                    })
            
            return wallpapers if wallpapers else None
        except Exception:
            return None

    def _on_random_wallpaper(self, e: ft.ControlEvent) -> None:
        """事件处理：从必应获取随机壁纸并应用。"""
        # 显示提示
        self._show_snackbar("正在从必应获取壁纸...", ft.Colors.BLUE)

        # 直接同步请求（请求较快），若担心阻塞可改为后台线程
        wallpapers = self._fetch_bing_wallpaper()
        if wallpapers:
            # 保存壁纸列表
            self.bing_wallpapers = wallpapers
            self.current_wallpaper_index = 0
            
            # 应用第一张壁纸
            self._apply_wallpaper(0)
            
            # 更新UI
            self._update_wallpaper_info_ui()
            
            self._show_snackbar(f"已获取{len(wallpapers)}张必应壁纸", ft.Colors.GREEN)
            
            # 如果自动切换已启用，启动定时器
            auto_switch_enabled = self.config_service.get_config_value("wallpaper_auto_switch", False)
            if auto_switch_enabled:
                interval = self.config_service.get_config_value("wallpaper_switch_interval", 30)
                self._start_auto_switch(interval)
        else:
            self._show_snackbar("获取壁纸失败，请检查网络或稍后重试", ft.Colors.RED)
    
    def _apply_wallpaper(self, index: int) -> None:
        """应用指定索引的壁纸。
        
        Args:
            index: 壁纸索引
        """
        if not self.bing_wallpapers or index < 0 or index >= len(self.bing_wallpapers):
            return
        
        wallpaper = self.bing_wallpapers[index]
        url = wallpaper["url"]
        
        # 更新UI文本（背景图片显示友好的标题）
        try:
            self.bg_image_text.value = f"必应壁纸: {wallpaper['title']}"
            # 使用 page.update() 而不是控件的 update()
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
        except Exception:
            pass
        
        # 保存配置
        self.config_service.set_config_value("background_image", url)
        self.current_wallpaper_index = index
        
        # 立即应用
        self._apply_background_image(url, self.bg_fit_dropdown.value)
    
    def _next_wallpaper(self, e: Optional[ft.ControlEvent] = None) -> None:
        """切换到下一张壁纸。"""
        if not self.bing_wallpapers:
            self._show_snackbar("请先获取必应壁纸", ft.Colors.ORANGE)
            return
        
        self.current_wallpaper_index = (self.current_wallpaper_index + 1) % len(self.bing_wallpapers)
        self._apply_wallpaper(self.current_wallpaper_index)
        self._update_wallpaper_info_ui()
    
    def _previous_wallpaper(self, e: Optional[ft.ControlEvent] = None) -> None:
        """切换到上一张壁纸。"""
        if not self.bing_wallpapers:
            self._show_snackbar("请先获取必应壁纸", ft.Colors.ORANGE)
            return
        
        self.current_wallpaper_index = (self.current_wallpaper_index - 1) % len(self.bing_wallpapers)
        self._apply_wallpaper(self.current_wallpaper_index)
        self._update_wallpaper_info_ui()
    
    def _update_wallpaper_info_ui(self) -> None:
        """更新壁纸信息UI。"""
        if not self.bing_wallpapers:
            return
        
        try:
            wallpaper = self.bing_wallpapers[self.current_wallpaper_index]
            
            # 更新壁纸计数显示
            if hasattr(self, 'wallpaper_count_text'):
                self.wallpaper_count_text.value = f"{self.current_wallpaper_index + 1} / {len(self.bing_wallpapers)}"
            
            # 更新壁纸信息
            if hasattr(self, 'wallpaper_info_text'):
                self.wallpaper_info_text.value = f"{wallpaper['title']}\n{wallpaper['copyright']}"
            
            # 更新背景图片文本显示（显示友好的标题而不是URL）
            if hasattr(self, 'bg_image_text'):
                self.bg_image_text.value = f"必应壁纸: {wallpaper['title']}"
            
            # 使用 page.update() 统一更新，避免在后台线程中直接调用控件的 update()
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
        except Exception as e:
            # 如果更新失败，至少确保不显示"加载中"
            logger.error(f"更新壁纸UI信息失败: {e}")
            if hasattr(self, 'bg_image_text'):
                # 如果更新失败，显示通用的"必应壁纸"
                if "加载中" in self.bg_image_text.value or self.bg_image_text.value.startswith("http"):
                    self.bg_image_text.value = "必应壁纸"
                    try:
                        page = getattr(self, '_saved_page', self._page)
                        if page:
                            page.update()
                    except:
                        pass
    
    def _on_download_wallpaper(self, e: Optional[ft.ControlEvent] = None) -> None:
        """下载当前壁纸到浏览器。"""
        if not self.bing_wallpapers:
            self._show_snackbar("请先获取必应壁纸", ft.Colors.ORANGE)
            return
        
        try:
            import webbrowser
            wallpaper = self.bing_wallpapers[self.current_wallpaper_index]
            url = wallpaper["url"]
            
            # 在浏览器中打开壁纸URL
            webbrowser.open(url)
            self._show_snackbar("已在浏览器中打开壁纸下载页面", ft.Colors.GREEN)
        except Exception as ex:
            self._show_snackbar(f"打开浏览器失败: {str(ex)}", ft.Colors.RED)
    
    def _on_auto_switch_change(self, e: ft.ControlEvent) -> None:
        """自动切换开关改变事件。"""
        enabled = e.control.value
        self.config_service.set_config_value("wallpaper_auto_switch", enabled)
        
        if enabled:
            # 启动自动切换
            interval = self.config_service.get_config_value("wallpaper_switch_interval", 30)
            self._start_auto_switch(interval)
            self._show_snackbar(f"已启用自动切换壁纸，间隔{interval}分钟", ft.Colors.GREEN)
        else:
            # 停止自动切换
            self._stop_auto_switch()
            self._show_snackbar("已关闭自动切换壁纸", ft.Colors.ORANGE)
    
    def _on_switch_interval_change(self, e: ft.ControlEvent) -> None:
        """切换间隔改变事件。"""
        interval = int(e.control.value)
        self.config_service.set_config_value("wallpaper_switch_interval", interval)
        
        # 如果自动切换已启用，重新启动定时器
        if self.config_service.get_config_value("wallpaper_auto_switch", False):
            self._start_auto_switch(interval)
        
        # 更新显示
        if hasattr(self, 'switch_interval_text'):
            self.switch_interval_text.value = f"{interval} 分钟"
            try:
                self._page.update()
            except Exception:
                pass
    
    def _start_auto_switch(self, interval_minutes: int) -> None:
        """启动自动切换定时器。
        
        Args:
            interval_minutes: 切换间隔（分钟）
        """
        # 先停止现有定时器
        self._stop_auto_switch()
        
        # 使用代数计数器来安全地取消旧的异步任务
        self._auto_switch_generation = getattr(self, '_auto_switch_generation', 0) + 1
        current_gen = self._auto_switch_generation
        
        async def switch_task():
            import asyncio
            await asyncio.sleep(interval_minutes * 60)
            # 仅当代数未变（未被 stop 或新 start 取消）时才执行
            if getattr(self, '_auto_switch_generation', -1) == current_gen:
                if self.bing_wallpapers:
                    self._next_wallpaper()
                # 递归调用，继续下一次定时
                self._start_auto_switch(interval_minutes)
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.run_task(switch_task)
    
    def _stop_auto_switch(self) -> None:
        """停止自动切换定时器。"""
        # 递增代数计数器，使所有正在等待的异步定时任务失效
        self._auto_switch_generation = getattr(self, '_auto_switch_generation', 0) + 1
        if self.auto_switch_timer:
            self.auto_switch_timer.cancel()
            self.auto_switch_timer = None
    
    def _build_interface_section(self) -> ft.Container:
        """构建界面设置部分。
        
        Returns:
            界面设置容器
        """
        section_title = ft.Text(
            "界面设置",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 获取当前配置
        show_recommendations = self.config_service.get_config_value("show_recommendations_page", True)
        save_logs = self.config_service.get_config_value("save_logs", False)
        show_weather = self.config_service.get_config_value("show_weather", True)
        minimize_to_tray = self.config_service.get_config_value("minimize_to_tray", False)
        
        # 推荐工具页面开关
        self.recommendations_switch = ft.Switch(
            label="显示推荐工具页面",
            value=show_recommendations,
            on_change=self._on_recommendations_switch_change,
        )
        
        # 说明文字
        recommendations_info_text = ft.Text(
            "开启或关闭推荐工具页面在导航栏中的显示",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 日志保存开关
        self.save_logs_switch = ft.Switch(
            label="保存日志到文件",
            value=save_logs,
            on_change=self._on_save_logs_switch_change,
        )
        
        # 日志说明文字
        logs_info_text = ft.Text(
            "开启后，应用运行日志将保存到 logs 目录，方便调试和问题排查",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 天气显示开关
        self.show_weather_switch = ft.Switch(
            label="显示天气信息",
            value=show_weather,
            on_change=self._on_show_weather_switch_change,
        )
        
        # 天气说明文字
        weather_info_text = ft.Text(
            "开启后，在标题栏右上角显示当前天气信息",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 最小化到托盘开关
        self.minimize_to_tray_switch = ft.Switch(
            label="最小化到系统托盘",
            value=minimize_to_tray,
            on_change=self._on_minimize_to_tray_switch_change,
        )
        
        # 托盘说明文字
        tray_info_text = ft.Text(
            "开启后，点击关闭按钮将隐藏到系统托盘，而不是退出应用",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 开机自启动（仅编译后生效）
        auto_start = self.config_service.get_config_value("auto_start", False)
        is_compiled = self._is_compiled()
        
        self.auto_start_switch = ft.Switch(
            label="开机自启动",
            value=auto_start if is_compiled else False,
            on_change=self._on_auto_start_switch_change,
            disabled=not is_compiled,
        )
        
        # 开机自启动说明文字
        auto_start_info = ft.Text(
            "开启后，系统启动时自动运行并最小化到托盘" if is_compiled else "此功能仅在编译后的版本中可用",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT if is_compiled else ft.Colors.ORANGE,
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.recommendations_switch,
                    ft.Container(height=PADDING_SMALL),
                    recommendations_info_text,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Divider(),
                    ft.Container(height=PADDING_MEDIUM),
                    self.save_logs_switch,
                    ft.Container(height=PADDING_SMALL),
                    logs_info_text,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Divider(),
                    ft.Container(height=PADDING_MEDIUM),
                    self.show_weather_switch,
                    ft.Container(height=PADDING_SMALL),
                    weather_info_text,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Divider(),
                    ft.Container(height=PADDING_MEDIUM),
                    self.minimize_to_tray_switch,
                    ft.Container(height=PADDING_SMALL),
                    tray_info_text,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Divider(),
                    ft.Container(height=PADDING_MEDIUM),
                    self.auto_start_switch,
                    ft.Container(height=PADDING_SMALL),
                    auto_start_info,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_recommendations_switch_change(self, e: ft.ControlEvent) -> None:
        """推荐工具页面开关改变事件。"""
        enabled = e.control.value
        if self.config_service.set_config_value("show_recommendations_page", enabled):
            # 立即更新推荐工具页面显示状态
            if hasattr(self._page, '_main_view'):
                self._page._main_view.update_recommendations_visibility(enabled)
            
            status = "已显示" if enabled else "已隐藏"
            self._show_snackbar(f"推荐工具页面{status}", ft.Colors.GREEN)
        else:
            self._show_snackbar("设置更新失败", ft.Colors.RED)
    
    def _on_save_logs_switch_change(self, e: ft.ControlEvent) -> None:
        """日志保存开关改变事件。"""
        from utils import logger
        
        enabled = e.control.value
        if self.config_service.set_config_value("save_logs", enabled):
            # 立即启用或禁用文件日志
            if enabled:
                logger.enable_file_logging()
                self._show_snackbar("日志保存已启用，日志文件将保存到 logs 目录", ft.Colors.GREEN)
            else:
                logger.disable_file_logging()
                self._show_snackbar("日志保存已禁用", ft.Colors.GREEN)
        else:
            self._show_snackbar("设置更新失败", ft.Colors.RED)
    
    def _on_show_weather_switch_change(self, e: ft.ControlEvent) -> None:
        """天气显示开关改变事件。"""
        enabled = e.control.value
        if self.config_service.set_config_value("show_weather", enabled):
            # 立即更新天气显示状态
            if hasattr(self._page, '_main_view') and hasattr(self._page._main_view, 'title_bar'):
                self._page._main_view.title_bar.set_weather_visibility(enabled)
            
            status = "已显示" if enabled else "已隐藏"
            self._show_snackbar(f"天气信息{status}", ft.Colors.GREEN)
        else:
            self._show_snackbar("设置更新失败", ft.Colors.RED)
    
    def _on_minimize_to_tray_switch_change(self, e: ft.ControlEvent) -> None:
        """最小化到托盘开关改变事件。"""
        enabled = e.control.value
        if self.config_service.set_config_value("minimize_to_tray", enabled):
            # 立即更新托盘功能状态
            if hasattr(self._page, '_main_view') and hasattr(self._page._main_view, 'title_bar'):
                self._page._main_view.title_bar.set_minimize_to_tray(enabled)
            
            status = "已启用" if enabled else "已禁用"
            self._show_snackbar(f"最小化到系统托盘{status}", ft.Colors.GREEN)
        else:
            self._show_snackbar("设置更新失败", ft.Colors.RED)
    
    def _is_compiled(self) -> bool:
        """检查是否为编译后的版本。"""
        from pathlib import Path
        return Path(sys.argv[0]).suffix.lower() == '.exe'
    
    def _on_auto_start_switch_change(self, e: ft.ControlEvent) -> None:
        """开机自启动开关改变事件。"""
        enabled = e.control.value
        
        if not self._is_compiled():
            self._show_snackbar("此功能仅在编译后的版本中可用", ft.Colors.ORANGE)
            e.control.value = False
            self._page.update()
            return
        
        # 设置注册表
        success = self._set_auto_start(enabled)
        
        if success:
            self.config_service.set_config_value("auto_start", enabled)
            status = "已启用" if enabled else "已禁用"
            self._show_snackbar(f"开机自启动{status}", ft.Colors.GREEN)
        else:
            self._show_snackbar("设置开机自启动失败，请检查权限", ft.Colors.RED)
            e.control.value = not enabled
            self._page.update()
    
    def _set_auto_start(self, enable: bool) -> bool:
        """设置开机自启动（注册表方式）。
        
        Args:
            enable: 是否启用
            
        Returns:
            是否成功
        """
        if sys.platform != 'win32':
            return False
        
        try:
            import winreg
            from pathlib import Path
            
            app_name = "MTools"
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            )
            
            if enable:
                # 获取可执行文件路径，添加 --minimized 参数
                exe_path = sys.argv[0]
                if Path(exe_path).suffix.lower() == '.exe':
                    # 使用 --minimized 参数启动时最小化到托盘
                    startup_cmd = f'"{exe_path}" --minimized'
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, startup_cmd)
                    logger.info(f"开机自启动已设置: {startup_cmd}")
                else:
                    winreg.CloseKey(key)
                    return False
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logger.info("开机自启动已移除")
                except FileNotFoundError:
                    pass  # 不存在也视为成功
            
            winreg.CloseKey(key)
            return True
            
        except Exception as e:
            logger.error(f"设置开机自启动失败: {e}")
            return False
    
    def _build_gpu_acceleration_section(self) -> ft.Container:
        """构建GPU加速设置部分，包括高级参数配置。"""

        # 标题与当前配置
        section_title = ft.Text(
            "GPU加速",
            size=20,
            weight=ft.FontWeight.W_600,
        )

        import platform as _platform
        _is_macos = _platform.system() == "Darwin"
        gpu_enabled = self.config_service.get_config_value("gpu_acceleration", not _is_macos)
        gpu_memory_limit = self.config_service.get_config_value("gpu_memory_limit", 8192)
        gpu_device_id = self.config_service.get_config_value("gpu_device_id", 0)
        enable_memory_arena = self.config_service.get_config_value("gpu_enable_memory_arena", False)

        # GPU开关（macOS 上禁用）
        if _is_macos:
            gpu_enabled = False
            self.gpu_acceleration_switch = ft.Switch(
                label="启用GPU加速",
                value=False,
                disabled=True,
            )
            status_text = ft.Text(
                "macOS 暂不支持 GPU 加速，当前使用 CPU 模式。\n"
                "CoreML 编译模型时会阻塞主线程导致界面卡死，待后续版本优化后开放。",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        else:
            self.gpu_acceleration_switch = ft.Switch(
                label="启用GPU加速",
                value=gpu_enabled,
                on_change=self._on_gpu_acceleration_change,
            )

            # 检测ONNX Runtime的GPU支持（用于AI功能：智能抠图、人声分离）
            try:
                import onnxruntime as ort
                available_providers = ort.get_available_providers()
                
                gpu_providers = []
                if 'CUDAExecutionProvider' in available_providers:
                    gpu_providers.append("NVIDIA CUDA")
                if 'DmlExecutionProvider' in available_providers:
                    gpu_providers.append("DirectML")
                if 'ROCMExecutionProvider' in available_providers:
                    gpu_providers.append("AMD ROCm")
                
                if gpu_providers:
                    provider_text = "、".join(gpu_providers)
                    status_text = ft.Text(
                        f"检测到GPU加速支持: {provider_text}",
                        size=12,
                        color=ft.Colors.GREEN,
                    )
                else:
                    status_text = ft.Text(
                        "未检测到GPU加速支持，将使用CPU模式",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
            except Exception:
                status_text = ft.Text(
                    "未检测到GPU加速支持，将使用CPU模式",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )

        # macOS 不显示高级参数，直接返回简化版
        if _is_macos:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        section_title,
                        ft.Container(height=PADDING_MEDIUM),
                        self.gpu_acceleration_switch,
                        ft.Container(height=PADDING_SMALL),
                        status_text,
                    ],
                    spacing=0,
                ),
                padding=PADDING_LARGE,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=BORDER_RADIUS_MEDIUM,
            )

        # 高级设置控件
        self.gpu_memory_value_text = ft.Text(
            f"{gpu_memory_limit} MB",
            size=13,
            text_align=ft.TextAlign.END,
            width=80,
        )

        memory_label_row = ft.Row(
            controls=[
                ft.Text("GPU内存限制", size=13),
                self.gpu_memory_value_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.gpu_memory_slider = ft.Slider(
            min=512,
            max=24576,  # 24GB
            divisions=47,  # (24576-512)/512 ≈ 47，每512MB一个刻度
            value=gpu_memory_limit,
            label=None,
            on_change=self._on_gpu_memory_change,
        )

        # GPU 内存限制说明（DirectML 不支持内存限制）
        self.gpu_memory_hint = ft.Text(
            "⚠️ 此设置限制 ONNX 内存池大小，不包括模型权重和 cuDNN 工作空间。\n"
            "如遇显存不足，请降低此值或处理较小尺寸的图片。DirectML 版本不支持此设置。",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        # 动态检测GPU设备数量
        gpu_device_options = self._get_gpu_device_options()

        # 检查 Provider 模式和 CUDA 设备可用性
        from utils import get_primary_provider, get_cuda_devices
        primary_provider = get_primary_provider()
        is_directml = primary_provider == "DirectML"
        is_cuda = primary_provider == "CUDA"
        cuda_available = bool(get_cuda_devices()) if is_cuda else False
        
        # 确定是否禁用 GPU 设备选择
        disable_gpu_select = is_directml or (is_cuda and not cuda_available)
        
        self.gpu_device_dropdown = ft.Dropdown(
            label="GPU设备",
            hint_text="在多GPU系统中选择一个设备" if not disable_gpu_select else (
                "DirectML 模式不支持设备选择" if is_directml else "未检测到 NVIDIA GPU"
            ),
            value=str(gpu_device_id) if cuda_available or not is_cuda else "0",
            options=gpu_device_options,
            on_select=self._on_gpu_device_change,
            width=500,
            disabled=disable_gpu_select,
        )
        
        # GPU 设备选择提示
        if is_directml:
            hint_text = (
                "DirectML 不支持设备选择，默认使用 Windows 设置中的首要 GPU。\n"
                "如需切换 GPU，请在 Windows 设置 > 显示 > 图形 中配置应用程序的 GPU 首选项。"
            )
            hint_color = ft.Colors.ORANGE
        elif is_cuda and not cuda_available:
            hint_text = (
                "您使用的是 CUDA 版本，但未检测到 NVIDIA GPU。程序将自动使用 CPU 运行。\n"
                "如需 GPU 加速，请确保安装了 NVIDIA 显卡和驱动，或下载 DirectML 普通版本。"
            )
            hint_color = ft.Colors.ORANGE
        else:
            hint_text = "CUDA/ROCm 支持多 GPU 选择，可在此指定使用的 GPU 设备。"
            hint_color = ft.Colors.ON_SURFACE_VARIANT
        
        self.gpu_device_hint = ft.Text(
            hint_text,
            size=11,
            color=hint_color,
        )

        self.memory_arena_switch = ft.Switch(
            label="启用内存池优化",
            value=enable_memory_arena,
            on_change=self._on_memory_arena_change,
        )

        advanced_content = ft.Column(
            controls=[
                memory_label_row,
                self.gpu_memory_slider,
                self.gpu_memory_hint,
                self.gpu_device_dropdown,
                self.gpu_device_hint,
                self.memory_arena_switch,
            ],
            spacing=16,
        )

        self.gpu_advanced_title = ft.Text(
            "高级参数",
            size=14,
            weight=ft.FontWeight.W_500,
        )

        self.gpu_advanced_container = ft.Container(
            content=advanced_content,
            padding=ft.padding.all(PADDING_MEDIUM),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        )

        info_text = ft.Text(
            "启用GPU加速可显著提升图像与视频处理速度。建议根据实际GPU显存设置限制，推荐为总显存的60-80%。",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        # 初始状态同步
        if not gpu_enabled:
            for ctrl in (self.gpu_memory_slider, self.gpu_device_dropdown, self.memory_arena_switch):
                ctrl.disabled = True
            self.gpu_memory_value_text.opacity = 0.6
            self.gpu_advanced_container.opacity = 0.6
        else:
            self.gpu_memory_value_text.opacity = 1.0
            self.gpu_advanced_container.opacity = 1.0

        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.gpu_acceleration_switch,
                    ft.Container(height=PADDING_SMALL),
                    status_text,
                    ft.Container(height=PADDING_MEDIUM),
                    self.gpu_advanced_title,
                    ft.Container(height=PADDING_SMALL),
                    self.gpu_advanced_container,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _build_performance_optimization_section(self) -> ft.Container:
        """构建性能优化设置部分。"""
        
        # 标题
        section_title = ft.Text(
            "性能优化",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 获取当前配置
        cpu_threads = self.config_service.get_config_value("onnx_cpu_threads", 0)
        execution_mode = self.config_service.get_config_value("onnx_execution_mode", "sequential")
        enable_model_cache = self.config_service.get_config_value("onnx_enable_model_cache", False)
        
        # CPU线程数设置
        self.cpu_threads_value_text = ft.Text(
            f"{cpu_threads if cpu_threads > 0 else '自动'}",
            size=13,
            text_align=ft.TextAlign.END,
            width=80,
        )
        
        threads_label_row = ft.Row(
            controls=[
                ft.Text("CPU推理线程数", size=13),
                self.cpu_threads_value_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        self.cpu_threads_slider = ft.Slider(
            min=0,
            max=16,
            divisions=16,
            value=cpu_threads,
            label=None,
            on_change=self._on_cpu_threads_change,
        )
        
        threads_hint = ft.Text(
            "0=自动检测 | CPU推理时使用的并行线程数，多核CPU可提升性能",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 执行模式设置
        self.execution_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value="sequential",
                        label="顺序执行 (节省内存，默认推荐)"
                    ),
                    ft.Radio(
                        value="parallel",
                        label="并行执行 (多核CPU性能更好，但占用更多内存)"
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            value=execution_mode,
            on_change=self._on_execution_mode_change,
        )
        
        # 模型缓存设置
        self.model_cache_switch = ft.Switch(
            label="启用模型缓存优化 (首次加载较慢，后续启动更快)",
            value=enable_model_cache,
            on_change=self._on_model_cache_change,
        )
        
        info_text = ft.Text(
            "这些设置影响AI模型的推理性能。建议GPU用户保持默认，CPU用户可调整线程数和执行模式。",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text("执行模式", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.execution_mode_radio,
                    ft.Container(height=PADDING_MEDIUM),
                    threads_label_row,
                    self.cpu_threads_slider,
                    threads_hint,
                    ft.Container(height=PADDING_MEDIUM),
                    self.model_cache_switch,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_gpu_acceleration_change(self, e: ft.ControlEvent) -> None:
        """GPU加速开关改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        enabled = e.control.value
        if self.config_service.set_config_value("gpu_acceleration", enabled):
            status = "已启用" if enabled else "已禁用"
            self._show_snackbar(f"GPU加速{status}，需重新加载模型生效", ft.Colors.GREEN)
            self._update_gpu_controls_state(enabled)
        else:
            self._show_snackbar("GPU加速设置更新失败", ft.Colors.RED)
    
    def _on_gpu_memory_change(self, e: ft.ControlEvent) -> None:
        """GPU内存限制改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        memory_limit = int(e.control.value)
        if self.config_service.set_config_value("gpu_memory_limit", memory_limit):
            self.gpu_memory_value_text.value = f"{memory_limit} MB"
            self._show_snackbar(f"GPU内存限制已设置为 {memory_limit} MB，需重新加载模型生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("GPU内存限制设置更新失败", ft.Colors.RED)
    
    def _on_gpu_device_change(self, e: ft.ControlEvent) -> None:
        """GPU设备ID改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        device_id = int(e.control.value)
        if self.config_service.set_config_value("gpu_device_id", device_id):
            self._show_snackbar(f"GPU设备已设置为 GPU {device_id}，需重新加载模型生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("GPU设备设置更新失败", ft.Colors.RED)
    
    def _on_memory_arena_change(self, e: ft.ControlEvent) -> None:
        """内存池优化开关改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        enabled = e.control.value
        if self.config_service.set_config_value("gpu_enable_memory_arena", enabled):
            status = "已启用" if enabled else "已禁用"
            self._show_snackbar(f"内存池优化{status}，需重新加载模型生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("内存池优化设置更新失败", ft.Colors.RED)
    
    def _on_cpu_threads_change(self, e: ft.ControlEvent) -> None:
        """CPU线程数改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        threads = int(e.control.value)
        if self.config_service.set_config_value("onnx_cpu_threads", threads):
            self.cpu_threads_value_text.value = f"{threads if threads > 0 else '自动'}"
            try:
                self._page.update()
            except:
                pass
            
            display_text = f"自动检测" if threads == 0 else f"{threads} 个线程"
            self._show_snackbar(f"CPU推理线程数已设置为 {display_text}", ft.Colors.GREEN)
        else:
            self._show_snackbar("CPU线程数设置更新失败", ft.Colors.RED)
    
    def _on_execution_mode_change(self, e: ft.ControlEvent) -> None:
        """执行模式改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        mode = e.control.value
        if self.config_service.set_config_value("onnx_execution_mode", mode):
            mode_text = "顺序执行" if mode == "sequential" else "并行执行"
            self._show_snackbar(f"执行模式已设置为 {mode_text}", ft.Colors.GREEN)
        else:
            self._show_snackbar("执行模式设置更新失败", ft.Colors.RED)
    
    def _on_model_cache_change(self, e: ft.ControlEvent) -> None:
        """模型缓存开关改变事件处理。
        
        Args:
            e: 控件事件对象
        """
        enabled = e.control.value
        if self.config_service.set_config_value("onnx_enable_model_cache", enabled):
            status = "已启用" if enabled else "已禁用"
            hint = "（首次加载会较慢，后续启动更快）" if enabled else ""
            self._show_snackbar(f"模型缓存优化{status}{hint}", ft.Colors.GREEN)
        else:
            self._show_snackbar("模型缓存设置更新失败", ft.Colors.RED)

    def _update_gpu_controls_state(self, enabled: bool) -> None:
        """根据GPU加速开关更新高级参数控件的可用状态。"""

        for ctrl in (self.gpu_memory_slider, self.gpu_device_dropdown, self.memory_arena_switch):
            ctrl.disabled = not enabled
            ctrl.opacity = 1.0 if enabled else 0.6

        self.gpu_advanced_container.opacity = 1.0 if enabled else 0.5
        self.gpu_memory_value_text.opacity = 1.0 if enabled else 0.6
        self.gpu_advanced_title.opacity = 1.0 if enabled else 0.6

        try:
            self._page.update()
        except Exception:
            pass
    
    def _build_theme_color_section(self) -> ft.Container:
        """构建主题色设置部分。
        
        Returns:
            主题色设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "主题颜色",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 预定义的主题色
        theme_colors = [
            ("#667EEA", "蓝紫色", "默认"),
            ("#6366F1", "靛蓝色", "科技感"),
            ("#8B5CF6", "紫色", "优雅"),
            ("#EC4899", "粉红色", "活力"),
            ("#F43F5E", "玫瑰红", "激情"),
            ("#D2D5E1", "浅灰蓝", "柔和"),
            ("#F97316", "橙色", "温暖"),
            ("#F59E0B", "琥珀色", "明亮"),
            ("#10B981", "绿色", "清新"),
            ("#14B8A6", "青色", "自然"),
            ("#06B6D4", "天蓝色", "清爽"),
            ("#0EA5E9", "天空蓝", "开阔"),
            ("#6B7280", "灰色", "稳重"),
            ("#1F2937", "深灰", "专业"),
            ("#000000", "黑色", "经典"),
        ]
        
        # 获取当前主题色
        current_theme_color = self.config_service.get_config_value("theme_color", "#667EEA")
        
        # 创建主题色卡片
        self.theme_color_cards: list = []
        
        theme_cards_row: ft.Row = ft.Row(
            controls=[],
            wrap=True,
            spacing=PADDING_MEDIUM,
            run_spacing=PADDING_MEDIUM,
        )
        
        for color, name, desc in theme_colors:
            card = self._create_theme_color_card(color, name, desc, color == current_theme_color)
            self.theme_color_cards.append(card)
            theme_cards_row.controls.append(card)
        
        # 添加自定义颜色选项
        custom_color_card = self._create_custom_color_card(current_theme_color)
        self.theme_color_cards.append(custom_color_card)
        theme_cards_row.controls.append(custom_color_card)
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "主题色会立即生效，包括标题栏和所有界面元素。点击「自定义」可以使用调色盘选择任意颜色",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 组装主题色设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    theme_cards_row,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _create_theme_color_card(self, color: str, name: str, desc: str, is_selected: bool) -> ft.Container:
        """创建主题色选择卡片。
        
        Args:
            color: 颜色值
            name: 颜色名称
            desc: 颜色描述
            is_selected: 是否选中
        
        Returns:
            主题色卡片容器
        """
        # 颜色圆圈
        color_circle = ft.Container(
            width=40,
            height=40,
            border_radius=20,
            bgcolor=color,
            border=ft.border.all(3, ft.Colors.WHITE) if is_selected else ft.border.all(1, ft.Colors.OUTLINE),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.3, color),
                offset=ft.Offset(0, 2),
            ) if is_selected else None,
        )
        
        # 选中标记
        check_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE,
            size=16,
            color=color,
        ) if is_selected else None
        
        card = ft.Container(
            content=ft.Column(
                controls=[
                    color_circle,
                    ft.Container(height=4),
                    ft.Text(
                        name,
                        size=12,
                        weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        desc,
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    check_icon if check_icon else ft.Container(height=16),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            width=90,
            height=110,
            padding=PADDING_MEDIUM // 2,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, color) if is_selected else None,
            border=ft.border.all(
                2 if is_selected else 1,
                color if is_selected else ft.Colors.OUTLINE
            ),
            data=color,  # 存储颜色值
            on_click=self._on_theme_color_click,
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        
        return card
    
    def _create_custom_color_card(self, current_theme_color: str) -> ft.Container:
        """创建自定义颜色卡片。
        
        Args:
            current_theme_color: 当前主题色
        
        Returns:
            自定义颜色卡片容器
        """
        card: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.COLOR_LENS,
                        size=32,
                    ),
                    ft.Container(height=4),
                    ft.Text(
                        "自定义",
                        size=12,
                        weight=ft.FontWeight.W_600,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "点击选择",
                        size=10,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=90,
            height=110,
            padding=PADDING_MEDIUM // 2,
            border_radius=BORDER_RADIUS_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            data="custom",
            on_click=self._open_color_picker,
            ink=True,
        )
        
        return card
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """将十六进制颜色转换为RGB值。
        
        Args:
            hex_color: 十六进制颜色值（如#667EEA）
        
        Returns:
            RGB元组 (r, g, b)
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """将RGB值转换为十六进制颜色。
        
        Args:
            r: 红色值 (0-255)
            g: 绿色值 (0-255)
            b: 蓝色值 (0-255)
        
        Returns:
            十六进制颜色值（如#667EEA）
        """
        return f"#{r:02x}{g:02x}{b:02x}".upper()
    
    def _open_color_picker(self, e: ft.ControlEvent) -> None:
        """打开调色盘对话框。
        
        Args:
            e: 控件事件对象
        """
        # 当前主题色
        current_color_hex = self.config_service.get_config_value("theme_color", "#667EEA")
        current_color_rgb = self._hex_to_rgb(current_color_hex)
        
        # 颜色预览框
        preview_box = ft.Container(
            width=100,
            height=100,
            bgcolor=current_color_hex,
            border_radius=12,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        # RGB文本显示
        rgb_text = ft.Text(
            f"RGB({current_color_rgb[0]}, {current_color_rgb[1]}, {current_color_rgb[2]})",
            size=14,
            weight=ft.FontWeight.W_500,
        )
        
        # 颜色代码输入框
        color_input = ft.TextField(
            label="颜色代码",
            hint_text="#667EEA",
            value=current_color_hex,
            width=200,
        )
        
        # RGB 滑块
        r_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=current_color_rgb[0],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text,
                color_input
            ),
        )
        
        g_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=current_color_rgb[1],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text,
                color_input
            ),
        )
        
        b_slider = ft.Slider(
            min=0,
            max=255,
            divisions=255,
            value=current_color_rgb[2],
            label="{value}",
            on_change=lambda e: self._update_color_preview_in_dialog(
                int(r_slider.value),
                int(g_slider.value),
                int(b_slider.value),
                preview_box,
                rgb_text,
                color_input
            ),
        )
        
        # 常用颜色预设
        preset_colors = [
            ("#667EEA", "蓝紫色", "默认"),
            ("#6366F1", "靛蓝色", "科技感"),
            ("#8B5CF6", "紫色", "优雅"),
            ("#EC4899", "粉红色", "活力"),
            ("#F43F5E", "玫瑰红", "激情"),
            ("#EF4444", "红色", "热烈"),
            ("#F97316", "橙色", "温暖"),
            ("#F59E0B", "琥珀色", "明亮"),
            ("#10B981", "绿色", "清新"),
            ("#14B8A6", "青色", "自然"),
            ("#06B6D4", "天蓝色", "清爽"),
            ("#0EA5E9", "天空蓝", "开阔"),
            ("#6B7280", "灰色", "稳重"),
            ("#1F2937", "深灰", "专业"),
            ("#000000", "黑色", "经典"),
            ("#FFFFFF", "白色", "纯净"),
        ]
        
        preset_buttons = []
        for hex_color, name, desc in preset_colors:
            rgb = self._hex_to_rgb(hex_color)
            preset_buttons.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                width=50,
                                height=50,
                                bgcolor=hex_color,
                                border_radius=8,
                                border=ft.border.all(2, ft.Colors.OUTLINE),
                                ink=True,
                                on_click=lambda e, c=hex_color, r=rgb[0], g=rgb[1], b=rgb[2]: self._apply_preset_color(
                                    c, r, g, b, r_slider, g_slider, b_slider, preview_box, rgb_text, color_input
                                ),
                            ),
                            ft.Text(name, size=10, text_align=ft.TextAlign.CENTER),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=4,
                )
            )
        
        # 颜色输入框变化事件
        def on_color_input_change(e: ft.ControlEvent):
            color_value = e.control.value.strip()
            if color_value and not color_value.startswith("#"):
                color_value = "#" + color_value
            
            # 验证颜色格式并更新
            import re
            if re.match(r'^#[0-9A-Fa-f]{6}$', color_value):
                rgb = self._hex_to_rgb(color_value)
                r_slider.value = rgb[0]
                g_slider.value = rgb[1]
                b_slider.value = rgb[2]
                self._update_color_preview_in_dialog(
                    rgb[0], rgb[1], rgb[2], preview_box, rgb_text, color_input
                )
        
        color_input.on_change = on_color_input_change
        
        # 对话框内容
        dialog_content = ft.Container(
            content=ft.Column(
                controls=[
                    # 预览区域
                    ft.Row(
                        controls=[
                            preview_box,
                            ft.Column(
                                controls=[
                                    rgb_text,
                                    color_input,
                                    ft.Text("调整RGB值或输入颜色代码", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=PADDING_SMALL,
                            ),
                        ],
                        spacing=PADDING_LARGE,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Divider(),
                    # RGB滑块
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text("R:", width=20, color=ft.Colors.RED),
                                    ft.Container(content=r_slider, expand=True),
                                ],
                                spacing=PADDING_SMALL,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text("G:", width=20, color=ft.Colors.GREEN),
                                    ft.Container(content=g_slider, expand=True),
                                ],
                                spacing=PADDING_SMALL,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text("B:", width=20, color=ft.Colors.BLUE),
                                    ft.Container(content=b_slider, expand=True),
                                ],
                                spacing=PADDING_SMALL,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Divider(),
                    # 常用颜色
                    ft.Text("常用颜色:", size=12, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=preset_buttons,
                        wrap=True,
                        spacing=PADDING_SMALL,
                        run_spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_MEDIUM,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=500,
            height=500,
        )
        
        # 创建对话框
        def close_dialog(apply: bool = False):
            if apply:
                color_value = color_input.value.strip()
                if color_value:
                    self._apply_custom_color(color_value)
            self.color_picker_dialog.open = False
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
        
        self.color_picker_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("选择自定义颜色"),
            content=dialog_content,
            actions=[
                ft.TextButton("取消", on_click=lambda e: close_dialog(False)),
                ft.Button("应用", on_click=lambda e: close_dialog(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.overlay.append(self.color_picker_dialog)
            self.color_picker_dialog.open = True
            page.update()
    
    def _update_color_preview_in_dialog(
        self,
        r: int,
        g: int,
        b: int,
        preview_box: ft.Container,
        rgb_text: ft.Text,
        color_input: ft.TextField
    ) -> None:
        """更新对话框中的颜色预览。
        
        Args:
            r: 红色值
            g: 绿色值
            b: 蓝色值
            preview_box: 预览框容器
            rgb_text: RGB文本控件
            color_input: 颜色输入框
        """
        hex_color = self._rgb_to_hex(r, g, b)
        preview_box.bgcolor = hex_color
        rgb_text.value = f"RGB({r}, {g}, {b})"
        color_input.value = hex_color
        try:
            self._page.update()
        except Exception:
            pass
    
    def _apply_preset_color(
        self,
        hex_color: str,
        r: int,
        g: int,
        b: int,
        r_slider: ft.Slider,
        g_slider: ft.Slider,
        b_slider: ft.Slider,
        preview_box: ft.Container,
        rgb_text: ft.Text,
        color_input: ft.TextField
    ) -> None:
        """应用预设颜色。
        
        Args:
            hex_color: 十六进制颜色值
            r: 红色值
            g: 绿色值
            b: 蓝色值
            r_slider: R滑块
            g_slider: G滑块
            b_slider: B滑块
            preview_box: 预览框容器
            rgb_text: RGB文本控件
            color_input: 颜色输入框
        """
        r_slider.value = r
        g_slider.value = g
        b_slider.value = b
        self._update_color_preview_in_dialog(r, g, b, preview_box, rgb_text, color_input)
    
    
    def _apply_custom_color(self, color_value: str) -> None:
        """应用自定义颜色。
        
        Args:
            color_value: 颜色值
        """
        # 确保以#开头
        if not color_value.startswith("#"):
            color_value = "#" + color_value
        
        # 验证颜色格式
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color_value):
            self._show_snackbar("颜色格式错误，请使用#RRGGBB格式（如#667EEA）", ft.Colors.RED)
            return
        
        # 保存并应用颜色
        if self.config_service.set_config_value("theme_color", color_value.upper()):
            # 通过 _saved_page 获取页面引用(因为 self._page 可能在布局重建后失效)
            page = getattr(self, '_saved_page', self._page)
            # 立即更新页面主题色
            if page and page.theme:
                page.theme.color_scheme_seed = color_value
            if page and page.dark_theme:
                page.dark_theme.color_scheme_seed = color_value
            
            # 更新标题栏颜色
            self._update_title_bar_color(color_value)
            
            # 更新所有预定义颜色卡片为未选中状态
            for card in self.theme_color_cards:
                if card.data != "custom":
                    card.border = ft.border.all(1, ft.Colors.OUTLINE)
                    card.bgcolor = None
                    
                    if card.content and isinstance(card.content, ft.Column):
                        color_circle = card.content.controls[0]
                        if isinstance(color_circle, ft.Container):
                            color_circle.border = ft.border.all(1, ft.Colors.OUTLINE)
                            color_circle.shadow = None
                        
                        name_text = card.content.controls[2]
                        if isinstance(name_text, ft.Text):
                            name_text.weight = ft.FontWeight.NORMAL
                        
                        if len(card.content.controls) > 4:
                            card.content.controls[4] = ft.Container(height=16)
                    
            # 更新整个页面（无需逐个卡片 update，page.update 会统一刷新）
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
            self._show_snackbar(f"自定义主题色已应用: {color_value}", ft.Colors.GREEN)
        else:
            self._show_snackbar("主题色更新失败", ft.Colors.RED)
    
    def _on_theme_color_click(self, e: ft.ControlEvent) -> None:
        """主题色卡片点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        clicked_color: str = e.control.data
        current_color = self.config_service.get_config_value("theme_color", "#667EEA")
        
        if clicked_color == current_color:
            return  # 已选中，无需更新
        
        # 保存主题色设置
        if self.config_service.set_config_value("theme_color", clicked_color):
            # 通过 _saved_page 获取页面引用(因为 self._page 可能在布局重建后失效)
            page = getattr(self, '_saved_page', self._page)
            # 立即更新页面主题色
            if page and page.theme:
                page.theme.color_scheme_seed = clicked_color
            if page and page.dark_theme:
                page.dark_theme.color_scheme_seed = clicked_color
            
            # 更新标题栏颜色（如果标题栏存在）
            self._update_title_bar_color(clicked_color)
            
            # 更新所有卡片的样式
            for card in self.theme_color_cards:
                # 跳过自定义颜色卡片（它的结构不同）
                if card.data == "custom":
                    continue
                
                is_selected = card.data == clicked_color
                color = card.data
                
                # 更新边框和背景
                card.border = ft.border.all(
                    2 if is_selected else 1,
                    color if is_selected else ft.Colors.OUTLINE
                )
                card.bgcolor = ft.Colors.with_opacity(0.05, color) if is_selected else None
                
                # 更新内容
                if card.content and isinstance(card.content, ft.Column):
                    # 更新颜色圆圈
                    color_circle = card.content.controls[0]
                    if isinstance(color_circle, ft.Container):
                        color_circle.border = ft.border.all(3, ft.Colors.WHITE) if is_selected else ft.border.all(1, ft.Colors.OUTLINE)
                        color_circle.shadow = ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=8,
                            color=ft.Colors.with_opacity(0.3, color),
                            offset=ft.Offset(0, 2),
                        ) if is_selected else None
                    
                    # 更新名称文字粗细
                    name_text = card.content.controls[2]
                    if isinstance(name_text, ft.Text):
                        name_text.weight = ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL
                    
                    # 更新选中标记（只有预定义颜色卡片有这个元素）
                    if len(card.content.controls) > 4:
                        if is_selected:
                            card.content.controls[4] = ft.Icon(
                                ft.Icons.CHECK_CIRCLE,
                                size=16,
                                color=color,
                            )
                        else:
                            card.content.controls[4] = ft.Container(height=16)
                
            # 更新整个页面（无需逐个卡片 update，page.update 会统一刷新）
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
            self._show_snackbar("主题色已更新", ft.Colors.GREEN)
        else:
            self._show_snackbar("主题色更新失败", ft.Colors.RED)
    
    def _update_title_bar_color(self, color: str) -> None:
        """更新标题栏颜色。
        
        Args:
            color: 新的主题色
        """
        # 通过 _saved_page 获取页面引用
        page = getattr(self, '_saved_page', self._page)
        
        # 尝试找到标题栏组件并更新颜色
        try:
            # 通过 MainView 访问标题栏
            if page and hasattr(page, '_main_view') and hasattr(page._main_view, 'title_bar'):
                page._main_view.title_bar.update_theme_color(color)
        except Exception:
            pass  # 如果更新失败也不影响其他功能
    
    def _build_font_section(self) -> ft.Container:
        """构建字体设置部分。
        
        Returns:
            字体设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "字体设置",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        
        # 获取系统已安装的字体列表（保存为实例变量）
        self.system_fonts = get_system_fonts()
        
        # 获取当前字体
        current_font = self.config_service.get_config_value("font_family", "System")
        current_scale = self.config_service.get_config_value("font_scale", 1.0)
        
        # 确保当前字体在列表中（如果不在，添加它）
        font_keys = [font[0] for font in self.system_fonts]
        if current_font and current_font not in font_keys:
            # 只有当 current_font 有效时才添加
            self.system_fonts.insert(1, (current_font, current_font))
        
        # 获取当前字体的显示名称
        current_font_display = current_font
        for font_key, font_name in self.system_fonts:
            if font_key == current_font:
                current_font_display = font_name
                break
        
        # 当前字体显示文本
        self.current_font_text = ft.Text(
            current_font_display,
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        
        # 字体选择区域（重新设计为卡片样式）
        self.font_selector_tile = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.FONT_DOWNLOAD_OUTLINED, size=24, color=ft.Colors.PRIMARY),
                        padding=10,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                        border_radius=8,
                    ),
                    ft.Container(width=12),
                    ft.Column(
                        controls=[
                            ft.Text("字体系列", size=15, weight=ft.FontWeight.W_500),
                            self.current_font_text,
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20, color=ft.Colors.OUTLINE),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            ink=True,
            on_click=self._open_font_selector_dialog,
        )
        
        # 字体大小滑块
        self.font_scale_text = ft.Text(
            f"{int(current_scale * 100)}%",
            size=13,
            weight=ft.FontWeight.W_500,
        )
        
        self.font_scale_slider = ft.Slider(
            min=80,
            max=150,
            divisions=14,
            value=current_scale * 100,
            label="{value}%",
            on_change=self._on_font_scale_change,
        )
        
        # 字体大小容器
        font_size_container = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("字体大小", size=14, weight=ft.FontWeight.W_500),
                        self.font_scale_text,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.font_scale_slider,
                ft.Text(
                    "80% (较小) - 100% (标准) - 150% (特大)",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 预览文本
        base_preview_size = 16
        preview_size = int(base_preview_size * current_scale)
        self.font_preview_text = ft.Text(
            "字体预览文本 Font Preview Text 0123456789",
            size=preview_size,
            font_family=current_font,
        )
        
        # 预览容器
        preview_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预览:", size=14, weight=ft.FontWeight.W_500),
                    self.font_preview_text,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        )
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "更改字体和字体大小后需要重启应用才能完全生效",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 组装字体设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.font_selector_tile,
                    ft.Container(height=PADDING_LARGE),
                    font_size_container,
                    ft.Container(height=PADDING_LARGE),
                    preview_container,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _build_about_section(self) -> ft.Container:
        """构建关于部分。
        
        Returns:
            关于部分容器
        """
        section_title: ft.Text = ft.Text(
            "关于",
            size=20,
            weight=ft.FontWeight.W_600,
        )
        import webbrowser
        
        # 更新状态显示组件
        self.update_status_text: ft.Text = ft.Text(
            "",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        self.update_status_icon: ft.Icon = ft.Icon(
            ft.Icons.INFO_OUTLINE,
            size=16,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        # 更新按钮（当有新版本时显示）
        self.update_download_button: ft.TextButton = ft.TextButton(
            "查看更新",
            icon=ft.Icons.SYSTEM_UPDATE,
            visible=False,
            on_click=self._on_open_download_page,
            tooltip="查看更新详情并选择更新方式",
        )
        
        # 更新状态行
        self.update_status_row: ft.Row = ft.Row(
            controls=[
                self.update_status_icon,
                self.update_status_text,
                self.update_download_button,
            ],
            spacing=PADDING_SMALL,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 检查更新按钮
        self.check_update_button: ft.OutlinedButton = ft.OutlinedButton(
            content="检查更新",
            icon=ft.Icons.REFRESH,
            on_click=self._on_check_update,
            tooltip="检查是否有新版本",
        )
        
        # 检查更新进度指示器
        self.update_progress: ft.ProgressRing = ft.ProgressRing(
            width=16,
            height=16,
            stroke_width=2,
            visible=False,
        )
        
        # 启动时自动检测更新开关
        auto_check_update = self.config_service.get_config_value("auto_check_update", True)
        self.auto_check_update_switch: ft.Switch = ft.Switch(
            label="启动时自动检测更新",
            value=auto_check_update,
            on_change=self._on_auto_check_update_change,
        )
        
        app_info: ft.Column = ft.Column(
            controls=[
                ft.Text("MTools - 多功能工具箱", size=16, weight=ft.FontWeight.W_500),
                ft.Row(
                    controls=[
                        ft.Text(f"版本: {get_full_version_string()}", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        self.update_progress,
                    ],
                    spacing=PADDING_SMALL,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.update_status_row,
                ft.Text("By：一铭"),
                ft.Text("QQ交流群：1029212047"),
                ft.Container(height=PADDING_MEDIUM // 2),
                ft.Text(
                    APP_DESCRIPTION,
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                # 点击访问软件发布页，用浏览器打开
                ft.TextButton(
                    "国内访问下载页",
                    on_click=lambda e: webbrowser.open("https://openlist.wer.plus/MTools"),
                    icon=ft.Icons.LINK,
                    tooltip="国内访问下载页",
                ),
                ft.TextButton(
                    "Github",
                    on_click=lambda e: webbrowser.open("https://github.com/HG-ha/MTools"),
                    icon=ft.Icons.LINK,
                    tooltip="Github",
                ),
            ],
            spacing=PADDING_MEDIUM // 2,
        )
        
        # 重置窗口按钮
        reset_window_button: ft.OutlinedButton = ft.OutlinedButton(
            content="重置窗口位置和大小",
            icon=ft.Icons.RESTORE,
            on_click=self._on_reset_window_position,
            tooltip="将窗口位置和大小重置为默认值",
        )
        
        # 创建桌面快捷方式按钮（仅 Windows 打包环境可用）
        create_shortcut_button: ft.OutlinedButton = ft.OutlinedButton(
            content="创建桌面快捷方式",
            icon=ft.Icons.SHORTCUT,
            on_click=self._on_create_desktop_shortcut,
            tooltip="在桌面创建应用快捷方式",
            visible=platform.system() == "Windows" and sys.argv[0].endswith('.exe'),
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    app_info,
                    ft.Container(height=PADDING_MEDIUM),
                    self.auto_check_update_switch,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Row(
                        controls=[
                            self.check_update_button,
                            reset_window_button,
                            create_shortcut_button,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_check_update(self, e: ft.ControlEvent) -> None:
        """检查更新按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        # 显示进度指示器
        self.update_progress.visible = True
        self.check_update_button.disabled = True
        self.update_status_text.visible = False
        self.update_status_icon.visible = False
        self.update_download_button.visible = False
        
        # 更新 UI
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
        
        # 在异步任务中检查更新
        async def check_update_task():
            import asyncio
            try:
                update_service = UpdateService()
                update_info = await asyncio.to_thread(update_service.check_update)
                
                # 在主线程中更新UI
                self._update_check_result(update_info)
            except Exception as ex:
                logger.error(f"检查更新出错: {ex}")
                self._update_check_result(UpdateInfo(
                    status=UpdateStatus.ERROR,
                    current_version=APP_VERSION,
                    error_message=f"检查更新出错: {str(ex)}",
                ))
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.run_task(check_update_task)
    
    def _update_check_result(self, update_info: UpdateInfo) -> None:
        """更新检查结果到UI。
        
        Args:
            update_info: 更新信息对象
        """
        # 保存更新信息用于下载
        self._latest_update_info = update_info
        
        # 隐藏进度指示器
        self.update_progress.visible = False
        self.check_update_button.disabled = False
        
        # 根据状态更新UI
        if update_info.status == UpdateStatus.UP_TO_DATE:
            self.update_status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
            self.update_status_icon.color = ft.Colors.GREEN
            self.update_status_text.value = "已是最新版本"
            self.update_status_text.color = ft.Colors.GREEN
            self.update_download_button.visible = False
            
        elif update_info.status == UpdateStatus.UPDATE_AVAILABLE:
            self.update_status_icon.name = ft.Icons.NEW_RELEASES
            self.update_status_icon.color = ft.Colors.ORANGE
            self.update_status_text.value = f"发现新版本: {update_info.latest_version}"
            self.update_status_text.color = ft.Colors.ORANGE
            self.update_download_button.visible = True
            
        elif update_info.status == UpdateStatus.ERROR:
            self.update_status_icon.name = ft.Icons.ERROR_OUTLINE
            self.update_status_icon.color = ft.Colors.RED
            self.update_status_text.value = update_info.error_message or "检查更新失败"
            self.update_status_text.color = ft.Colors.RED
            self.update_download_button.visible = False
        
        self.update_status_icon.visible = True
        self.update_status_text.visible = True
        
        # 使用保存的页面引用更新 UI
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
    
    def _on_open_download_page(self, e: ft.ControlEvent) -> None:
        """打开下载页面或开始自动更新。
        
        Args:
            e: 控件事件对象
        """
        if not hasattr(self, '_latest_update_info') or not self._latest_update_info:
            return
        
        update_info = self._latest_update_info
        
        # 如果有下载链接，显示对话框让用户选择
        if update_info.download_url:
            self._show_update_dialog(update_info)
        else:
            # 没有下载链接，打开浏览器
            import webbrowser
            url = update_info.release_url or "https://github.com/HG-ha/MTools/releases"
            webbrowser.open(url)
    
    def _show_update_dialog(self, update_info: UpdateInfo) -> None:
        """显示更新对话框。
        
        Args:
            update_info: 更新信息
        """
        # 创建更新说明文本
        release_notes = update_info.release_notes or "暂无更新说明"
        if len(release_notes) > 500:
            release_notes = release_notes[:500] + "..."
        
        # 创建进度条
        progress_bar = ft.ProgressBar(value=0, visible=False)
        progress_text = ft.Text("", size=12, visible=False)
        
        # 创建按钮
        auto_update_btn = ft.Button(
            content="自动更新",
            icon=ft.Icons.SYSTEM_UPDATE,
            on_click=lambda _: self._start_auto_update(
                update_info, 
                dialog, 
                auto_update_btn, 
                manual_btn, 
                progress_bar, 
                progress_text
            ),
        )
        
        manual_btn = ft.OutlinedButton(
            content="手动下载",
            icon=ft.Icons.OPEN_IN_BROWSER,
            on_click=lambda _: self._open_release_page(update_info, dialog),
        )
        
        cancel_btn = ft.TextButton(
            content="取消",
            on_click=lambda _: self._close_dialog(dialog),
        )
        
        # 创建对话框
        dialog = ft.AlertDialog(
            title=ft.Text(f"发现新版本 {update_info.latest_version}"),
            content=ft.Column(
                controls=[
                    ft.Text("更新说明:", weight=ft.FontWeight.BOLD, size=14),
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
                        padding=PADDING_SMALL,
                        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        height=300,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    progress_bar,
                    progress_text,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                auto_update_btn,
                manual_btn,
                cancel_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
    
    def _start_auto_update(
        self, 
        update_info: UpdateInfo,
        dialog: ft.AlertDialog,
        auto_btn: ft.Button,
        manual_btn: ft.OutlinedButton,
        progress_bar: ft.ProgressBar,
        progress_text: ft.Text
    ) -> None:
        """开始自动更新。
        
        Args:
            update_info: 更新信息
            dialog: 对话框
            auto_btn: 自动更新按钮
            manual_btn: 手动下载按钮
            progress_bar: 进度条
            progress_text: 进度文本
        """
        # 禁用按钮
        auto_btn.disabled = True
        manual_btn.disabled = True
        
        # 显示进度条
        progress_bar.visible = True
        progress_text.visible = True
        progress_text.value = "正在下载更新..."
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
        
        # 在异步任务中下载和安装更新
        async def update_task():
            try:
                import asyncio
                updater = AutoUpdater()
                
                # 定义进度回调（从 download_update 的异步上下文中调用，安全更新UI）
                def progress_callback(downloaded: int, total: int):
                    if total > 0:
                        progress = downloaded / total
                        async def _update_dl_progress():
                            progress_bar.value = progress
                            downloaded_mb = downloaded / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            progress_text.value = f"下载中: {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({progress*100:.0f}%)"
                            if page:
                                page.update()
                        try:
                            if page:
                                page.run_task(_update_dl_progress)
                        except Exception:
                            pass
                
                # 下载更新
                download_path = await updater.download_update(update_info.download_url, progress_callback)
                
                # 解压
                progress_text.value = "正在解压更新..."
                progress_bar.value = None  # 不确定进度
                if page:
                    page.update()
                
                extract_dir = await asyncio.to_thread(updater.extract_update, download_path)
                
                # 应用更新
                progress_text.value = "正在应用更新，应用即将重启..."
                if page:
                    page.update()
                
                await asyncio.sleep(1)  # 让用户看到提示
                
                # 定义优雅退出回调
                def exit_callback():
                    """使用标题栏的关闭方法优雅退出"""
                    try:
                        # 获取主视图
                        from views.main_view import MainView
                        main_view = getattr(page, 'main_view', None)
                        if main_view and hasattr(main_view, 'title_bar'):
                            # 使用标题栏的关闭方法（force=True 强制退出，不最小化到托盘）
                            main_view.title_bar._close_window(None, force=True)
                        else:
                            # 后备：直接关闭窗口
                            page.window.close()
                    except Exception as e:
                        logger.warning(f"优雅退出失败: {e}")
                        # 如果失败，让 apply_update 使用强制退出
                        raise
                
                # 应用更新会退出应用
                await asyncio.to_thread(updater.apply_update, extract_dir, exit_callback)
                
            except Exception as ex:
                logger.error(f"自动更新失败: {ex}")
                
                # 恢复按钮状态
                auto_btn.disabled = False
                manual_btn.disabled = False
                progress_bar.visible = False
                progress_text.visible = False
                
                # 显示错误信息
                progress_text.value = f"更新失败: {str(ex)}"
                progress_text.color = ft.Colors.RED
                progress_text.visible = True
                
                if page:
                    page.update()
        
        if page:
            page.run_task(update_task)
    
    def _open_release_page(self, update_info: UpdateInfo, dialog: ft.AlertDialog) -> None:
        """打开 Release 页面。
        
        Args:
            update_info: 更新信息
            dialog: 对话框
        """
        import webbrowser
        url = update_info.release_url or "https://github.com/HG-ha/MTools/releases"
        webbrowser.open(url)
        self._close_dialog(dialog)
    
    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        """关闭对话框。
        
        Args:
            dialog: 要关闭的对话框
        """
        dialog.open = False
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
    
    def _on_auto_check_update_change(self, e: ft.ControlEvent) -> None:
        """自动检测更新开关状态变化事件。
        
        Args:
            e: 控件事件对象
        """
        self.config_service.set_config_value("auto_check_update", e.control.value)
        
        # 如果关闭自动检测，同时清除跳过的版本记录
        if not e.control.value:
            self.config_service.set_config_value("skipped_version", "")
        
        self._show_snackbar(
            "已开启启动时自动检测更新" if e.control.value else "已关闭启动时自动检测更新",
            ft.Colors.GREEN
        )
    
    def _on_dir_type_change(self, e: ft.ControlEvent) -> None:
        """目录类型切换事件处理。
        
        Args:
            e: 控件事件对象
        """
        is_custom: bool = e.control.value == "custom"
        
        if not is_custom:
            # 切换到默认目录
            old_dir = self.config_service.get_data_dir()
            default_dir = self.config_service._get_default_data_dir()
            
            # 如果新旧目录相同，不做任何操作
            if old_dir == default_dir:
                # 重置单选按钮为自定义（因为当前已经是默认目录）
                self.dir_type_radio.value = "custom"
                self.browse_button.disabled = False
                self.dir_type_radio.update()
                self.browse_button.update()
                self._show_snackbar("当前已经是默认目录", ft.Colors.ORANGE)
                return
            
            # 更新浏览按钮状态
            self.browse_button.disabled = True
            self.browse_button.update()
            
            # 检查旧目录是否有数据
            has_old_data = self.config_service.check_data_exists(old_dir)
            
            if has_old_data:
                # 有数据，询问是否迁移
                self._show_migrate_dialog(old_dir, default_dir)
            else:
                # 没有数据，直接切换
                if self.config_service.reset_to_default_dir():
                    self.data_dir_text.value = str(self.config_service.get_data_dir())
                    self.data_dir_text.update()
                    # 单选按钮已经在用户点击时更新了，这里不需要再更新
                    self._show_snackbar("已切换到默认数据目录", ft.Colors.GREEN)
                else:
                    # 切换失败，恢复单选按钮状态
                    self.dir_type_radio.value = "custom"
                    self.browse_button.disabled = False
                    self.dir_type_radio.update()
                    self.browse_button.update()
                    self._show_snackbar("切换失败", ft.Colors.RED)
        else:
            # 切换到自定义路径
            self.browse_button.disabled = False
            self.browse_button.update()
    
    async def _on_browse_click(self, e: ft.ControlEvent) -> None:
        """浏览按钮点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择数据存储目录")
        if folder_path:
            # 检查是否需要迁移数据
            old_dir = self.config_service.get_data_dir()
            new_dir = Path(folder_path)
            
            # 如果新旧目录相同，不做任何操作
            if old_dir == new_dir:
                self._show_snackbar("新目录与当前目录相同", ft.Colors.ORANGE)
                return
            
            # 检查旧目录是否有数据
            has_old_data = self.config_service.check_data_exists(old_dir)
            
            if has_old_data:
                # 有数据，询问是否迁移
                self._show_migrate_dialog(old_dir, new_dir)
            else:
                # 没有数据，直接更改目录
                if self.config_service.set_data_dir(folder_path, is_custom=True):
                    self.data_dir_text.value = folder_path
                    self.data_dir_text.update()
                    
                    # 更新单选按钮状态
                    default_dir = self.config_service._get_default_data_dir()
                    is_custom_dir = (new_dir != default_dir)
                    self.dir_type_radio.value = "custom" if is_custom_dir else "default"
                    self.browse_button.disabled = not is_custom_dir
                    self.dir_type_radio.update()
                    self.browse_button.update()
                    
                    self._show_snackbar("数据目录已更新", ft.Colors.GREEN)
                else:
                    self._show_snackbar("更新数据目录失败", ft.Colors.RED)
    
    def _show_migrate_dialog(self, old_dir: Path, new_dir: Path) -> None:
        """显示数据迁移确认对话框。
        
        Args:
            old_dir: 旧数据目录
            new_dir: 新数据目录
        """
        def on_migrate(e):
            """选择迁移数据"""
            dialog.open = False
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
            # 显示迁移进度对话框
            self._show_migrate_progress_dialog(old_dir, new_dir)
        
        def on_no_migrate(e):
            """不迁移数据"""
            dialog.open = False
            page = getattr(self, '_saved_page', self._page)
            if page:
                page.update()
            # 直接更改目录
            if self.config_service.set_data_dir(str(new_dir), is_custom=True):
                self.data_dir_text.value = str(new_dir)
                self.data_dir_text.update()
                
                # 更新单选按钮状态
                default_dir = self.config_service._get_default_data_dir()
                is_custom_dir = (new_dir != default_dir)
                self.dir_type_radio.value = "custom" if is_custom_dir else "default"
                self.browse_button.disabled = not is_custom_dir
                self.dir_type_radio.update()
                self.browse_button.update()
                
                self._show_snackbar("数据目录已更新（未迁移旧数据）", ft.Colors.ORANGE)
            else:
                self._show_snackbar("更新数据目录失败", ft.Colors.RED)
        
        def on_cancel(e):
            """取消操作"""
            dialog.open = False
            self._page.update()
            
            # 恢复单选按钮状态（因为用户取消了操作）
            current_dir = self.config_service.get_data_dir()
            default_dir = self.config_service._get_default_data_dir()
            is_custom_dir = (current_dir != default_dir)
            self.dir_type_radio.value = "custom" if is_custom_dir else "default"
            self.browse_button.disabled = not is_custom_dir
            self.dir_type_radio.update()
            self.browse_button.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("发现旧数据", size=18, weight=ft.FontWeight.W_600),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "旧数据目录中包含数据，是否迁移到新目录？",
                            size=14,
                        ),
                        ft.Container(height=PADDING_MEDIUM),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text("旧目录:", size=12, weight=ft.FontWeight.W_500),
                                    ft.Text(str(old_dir), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Container(height=PADDING_SMALL),
                                    ft.Text("新目录:", size=12, weight=ft.FontWeight.W_500),
                                    ft.Text(str(new_dir), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=PADDING_SMALL // 2,
                            ),
                            padding=PADDING_MEDIUM,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=BORDER_RADIUS_MEDIUM,
                        ),
                        ft.Container(height=PADDING_MEDIUM),
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.BLUE),
                                ft.Text(
                                    "建议迁移数据以保留工具、模型等",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=PADDING_SMALL,
                        ),
                    ],
                    spacing=0,
                    tight=True,
                ),
                width=500,
            ),
            actions=[
                ft.TextButton("取消", on_click=on_cancel),
                ft.TextButton("不迁移", on_click=on_no_migrate),
                ft.Button(
                    content="迁移数据",
                    on_click=on_migrate,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.ON_PRIMARY,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
    
    def _show_migrate_progress_dialog(self, old_dir: Path, new_dir: Path) -> None:
        """显示数据迁移进度对话框。
        
        Args:
            old_dir: 旧数据目录
            new_dir: 新数据目录
        """
        progress_bar = ft.ProgressBar(width=400, value=0)
        progress_text = ft.Text("准备迁移...", size=14)
        
        dialog = ft.AlertDialog(
            title=ft.Text("正在迁移数据", size=18, weight=ft.FontWeight.W_600),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        progress_text,
                        ft.Container(height=PADDING_MEDIUM),
                        progress_bar,
                    ],
                    spacing=0,
                    tight=True,
                ),
                width=500,
            ),
            actions=[],  # 迁移时不显示按钮
        )
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
        
        # 在异步任务中执行迁移
        async def migrate_task():
            import asyncio
            
            def progress_callback(current, total, message):
                """进度回调 - 通过 run_task 安全地更新UI"""
                async def _update_migrate_progress():
                    progress_bar.value = current / total if total > 0 else 0
                    progress_text.value = message
                    try:
                        _page = getattr(self, '_saved_page', self._page)
                        if _page:
                            _page.update()
                    except Exception:
                        pass
                try:
                    _page = getattr(self, '_saved_page', self._page)
                    if _page:
                        _page.run_task(_update_migrate_progress)
                except Exception:
                    pass
            
            # 执行迁移
            success, message = await asyncio.to_thread(
                self.config_service.migrate_data,
                old_dir, new_dir, progress_callback
            )
            
            # 关闭进度对话框
            dialog.open = False
            try:
                _page = getattr(self, '_saved_page', self._page)
                if _page:
                    _page.update()
            except Exception:
                pass
            
            if success:
                # 更新配置
                if self.config_service.set_data_dir(str(new_dir), is_custom=True):
                    self.data_dir_text.value = str(new_dir)
                    
                    # 更新单选按钮状态
                    default_dir = self.config_service._get_default_data_dir()
                    is_custom_dir = (new_dir != default_dir)
                    self.dir_type_radio.value = "custom" if is_custom_dir else "default"
                    self.browse_button.disabled = not is_custom_dir
                    
                    _page = getattr(self, '_saved_page', self._page)
                    if _page:
                        _page.update()
                    
                    self._show_snackbar(f"✓ {message}", ft.Colors.GREEN)
                    
                    # 询问是否删除旧数据
                    await asyncio.sleep(0.5)  # 稍微延迟一下，让用户看到成功消息
                    self._show_delete_old_data_dialog(old_dir)
                else:
                    self._show_snackbar("更新配置失败", ft.Colors.RED)
            else:
                self._show_snackbar(f"✗ {message}", ft.Colors.RED)
        
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.run_task(migrate_task)
    
    def _show_delete_old_data_dialog(self, old_dir: Path) -> None:
        """显示删除旧数据确认对话框。
        
        Args:
            old_dir: 旧数据目录
        """
        def on_delete(e):
            """删除旧数据"""
            dialog.open = False
            self._page.update()
            
            # 在异步任务中执行删除
            async def delete_task():
                import asyncio
                try:
                    import shutil
                    
                    if not old_dir.exists():
                        self._show_snackbar("旧目录不存在", ft.Colors.ORANGE)
                        return
                    
                    # 删除旧数据目录中的内容，但保留 config.json
                    def _do_delete():
                        count = 0
                        for item in old_dir.iterdir():
                            if item.name == "config.json":
                                continue
                            try:
                                if item.is_dir():
                                    shutil.rmtree(item)
                                else:
                                    item.unlink()
                                count += 1
                            except Exception as e:
                                logger.error(f"删除 {item.name} 失败: {e}")
                        return count
                    
                    deleted_count = await asyncio.to_thread(_do_delete)
                    
                    if deleted_count > 0:
                        self._show_snackbar(f"已删除 {deleted_count} 项旧数据（保留了 config.json）", ft.Colors.GREEN)
                    else:
                        self._show_snackbar("没有需要删除的数据", ft.Colors.ORANGE)
                except Exception as e:
                    self._show_snackbar(f"删除失败: {str(e)}", ft.Colors.RED)
            
            self._page.run_task(delete_task)
        
        def on_keep(e):
            """保留旧数据"""
            dialog.open = False
            self._page.update()
            self._show_snackbar("已保留旧数据", ft.Colors.BLUE)
        
        dialog = ft.AlertDialog(
            title=ft.Text("删除旧数据？", size=18, weight=ft.FontWeight.W_600),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "数据已成功迁移到新目录。",
                            size=14,
                        ),
                        ft.Text(
                            "是否删除旧目录中的数据以释放磁盘空间？",
                            size=14,
                        ),
                        ft.Container(height=PADDING_MEDIUM),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text("旧目录:", size=12, weight=ft.FontWeight.W_500),
                                    ft.Text(str(old_dir), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=PADDING_SMALL // 2,
                            ),
                            padding=PADDING_MEDIUM,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=BORDER_RADIUS_MEDIUM,
                        ),
                        ft.Container(height=PADDING_MEDIUM),
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.BLUE),
                                ft.Text(
                                    "将保留 config.json 配置文件",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=PADDING_SMALL,
                        ),
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=ft.Colors.ORANGE),
                                ft.Text(
                                    "删除后无法恢复，请确认数据已成功迁移",
                                    size=12,
                                    color=ft.Colors.ORANGE,
                                ),
                            ],
                            spacing=PADDING_SMALL,
                        ),
                    ],
                    spacing=PADDING_SMALL // 2,
                    tight=True,
                ),
                width=500,
            ),
            actions=[
                ft.TextButton("保留", on_click=on_keep),
                ft.Button(
                    content="删除",
                    on_click=on_delete,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.ORANGE,
                        color=ft.Colors.WHITE,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    def _on_open_dir_click(self, e: ft.ControlEvent) -> None:
        """打开目录按钮点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        import subprocess
        import platform
        
        data_dir: Path = self.config_service.get_data_dir()
        
        try:
            system: str = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", str(data_dir)])
            elif system == "Darwin":
                subprocess.run(["open", str(data_dir)])
            else:
                subprocess.run(["xdg-open", str(data_dir)])
        except Exception as ex:
            self._show_snackbar(f"打开目录失败: {ex}", ft.Colors.RED)
    
    def _create_font_tile(self, font_key: str, font_display: str) -> ft.Container:
        """创建字体列表项。
        
        Args:
            font_key: 字体键名
            font_display: 字体显示名
            
        Returns:
            字体列表项容器
        """
        current_font = self.config_service.get_config_value("font_family", "System")
        is_selected = font_key == current_font
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    # 左侧：字体信息
                    ft.Column(
                        controls=[
                            ft.Text(
                                font_display,
                                size=14,
                                weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL,
                                color=ft.Colors.PRIMARY if is_selected else ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                "The quick brown fox jumps over the lazy dog",
                                size=13,
                                font_family=font_key,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    # 右侧：选中标记
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE,
                        color=ft.Colors.PRIMARY,
                        size=24,
                        visible=is_selected,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.all(12),
            ink=True,
            on_click=lambda e, fk=font_key, fd=font_display: self._apply_font_selection(fk, fd),
            border=ft.border.all(1, ft.Colors.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_selected else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        )

    def _open_font_selector_dialog(self, e: ft.ControlEvent) -> None:
        """打开字体选择对话框。
        
        Args:
            e: 控件事件对象
        """
        # 确保文件选择器在页面overlay中
        if hasattr(self, 'font_file_picker') and self.font_file_picker not in self._page.overlay:
            self._page.overlay.append(self.font_file_picker)
            self._page.update()
        
        # 搜索框
        search_field = ft.TextField(
            hint_text="搜索字体...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self._filter_font_list(e.control.value),
            expand=True,
            height=40,
            content_padding=10,
            border_radius=BORDER_RADIUS_MEDIUM,
            text_size=14,
        )
        
        # 导入文件按钮
        import_btn = ft.Button(
            "导入字体文件",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._pick_font_file,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=16, vertical=0),
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
            ),
            height=40,
        )
        
        # 初始化分页相关变量
        self.filtered_fonts = self.system_fonts
        self.current_page = 0
        self.PAGE_SIZE = 15  # 每页显示15个字体
        
        # 字体列表列
        self.font_list_column = ft.Column(
            controls=[],
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        # 翻页控制组件
        self._page_info_text = ft.Text("0 / 0", size=12)
        
        self.first_page_btn = ft.IconButton(
            ft.Icons.FIRST_PAGE,
            on_click=lambda e: self._goto_first_page(),
            disabled=True,
            tooltip="首页",
            icon_size=20,
        )
        
        self.prev_page_btn = ft.IconButton(
            ft.Icons.CHEVRON_LEFT,
            on_click=lambda e: self._change_font_page(-1),
            disabled=True,
            tooltip="上一页",
            icon_size=20,
        )
        
        self.next_page_btn = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT,
            on_click=lambda e: self._change_font_page(1),
            disabled=True,
            tooltip="下一页",
            icon_size=20,
        )
        
        self.last_page_btn = ft.IconButton(
            ft.Icons.LAST_PAGE,
            on_click=lambda e: self._goto_last_page(),
            disabled=True,
            tooltip="尾页",
            icon_size=20,
        )
        
        # 字体列表容器
        font_list_container = ft.Container(
            content=self.font_list_column,
            expand=True,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=4,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.ON_SURFACE),
        )
        
        # 对话框内容
        dialog_content = ft.Container(
            width=600,
            height=700,
            padding=PADDING_MEDIUM,
            content=ft.Column(
                controls=[
                    # 标题栏
                    ft.Row(
                        controls=[
                            ft.Text("选择字体", size=20, weight=ft.FontWeight.W_600),
                            ft.IconButton(ft.Icons.CLOSE, on_click=lambda e: self._close_font_selector_dialog()),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=10),
                    
                    # 搜索栏和导入按钮
                    ft.Row(
                        controls=[
                            search_field,
                            import_btn,
                        ],
                        spacing=10,
                    ),
                    ft.Container(height=10),
                    ft.Text(f"共 {len(self.system_fonts)} 个字体", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=5),
                    
                    # 列表区域
                    font_list_container,
                    
                    # 底部区域（分页）
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                self.first_page_btn,
                                self.prev_page_btn,
                                self._page_info_text,
                                self.next_page_btn,
                                self.last_page_btn,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.only(top=PADDING_SMALL),
                    ),
                ],
                spacing=0,
            )
        )
        
        # 创建对话框
        self.font_selector_dialog = ft.AlertDialog(
            content=dialog_content,
            modal=True, # 模态对话框
            shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
            content_padding=0,
        )
        
        # 显示对话框
        self._page.overlay.append(self.font_selector_dialog)
        self.font_selector_dialog.open = True
        self._page.update()
        
        # 初始加载第一页数据
        self._update_font_page()
    
    def _change_font_page(self, delta: int) -> None:
        """切换字体列表页码。
        
        Args:
            delta: 页码变化值（+1 或 -1）
        """
        new_page = self.current_page + delta
        max_page = max(0, (len(self.filtered_fonts) - 1) // self.PAGE_SIZE)
        
        if 0 <= new_page <= max_page:
            self.current_page = new_page
            self._update_font_page()
            
    def _goto_first_page(self) -> None:
        """跳转到第一页。"""
        self.current_page = 0
        self._update_font_page()
        
    def _goto_last_page(self) -> None:
        """跳转到最后一页。"""
        total_fonts = len(self.filtered_fonts)
        total_pages = max(1, (total_fonts + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.current_page = max(0, total_pages - 1)
        self._update_font_page()
            
    def _update_font_page(self) -> None:
        """更新当前页的字体列表。"""
        start_index = self.current_page * self.PAGE_SIZE
        end_index = start_index + self.PAGE_SIZE
        
        # 获取当前页的字体
        current_batch = self.filtered_fonts[start_index:end_index]
        
        # 创建控件
        new_tiles = [self._create_font_tile(font[0], font[1]) for font in current_batch]
        self.font_list_column.controls = new_tiles
        self.font_list_column.update()
        
        # 更新分页信息
        total_fonts = len(self.filtered_fonts)
        total_pages = max(1, (total_fonts + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page_info_text.value = f"{self.current_page + 1} / {total_pages}"
        self._page_info_text.update()
        
        # 更新按钮状态
        is_first = self.current_page <= 0
        is_last = self.current_page >= total_pages - 1
        
        self.first_page_btn.disabled = is_first
        self.prev_page_btn.disabled = is_first
        self.next_page_btn.disabled = is_last
        self.last_page_btn.disabled = is_last
        
        self.first_page_btn.update()
        self.prev_page_btn.update()
        self.next_page_btn.update()
        self.last_page_btn.update()
    
    def _filter_font_list(self, search_text: str) -> None:
        """过滤字体列表。
        
        Args:
            search_text: 搜索文本
        """
        search_text = search_text.lower().strip()
        
        if not search_text:
            # 显示所有字体
            self.filtered_fonts = self.system_fonts
        else:
            # 根据搜索文本过滤
            self.filtered_fonts = [
                font for font in self.system_fonts
                if search_text in font[0].lower() or search_text in font[1].lower()
            ]
        
        # 重置到第一页
        self.current_page = 0
        self._update_font_page()
    
    def _apply_font_selection(self, font_key: str, font_display: str) -> None:
        """应用选中的字体。
        
        Args:
            font_key: 字体键名
            font_display: 字体显示名
        """
        # 保存字体设置
        if self.config_service.set_config_value("font_family", font_key):
            # 更新当前字体显示
            self.current_font_text.value = font_display
            self.current_font_text.update()
            
            # 更新预览文本字体
            self.font_preview_text.font_family = font_key
            self.font_preview_text.update()
            
            # 尝试更新页面字体（部分生效）
            if self._page.theme:
                self._page.theme.font_family = font_key
            if self._page.dark_theme:
                self._page.dark_theme.font_family = font_key
            self._page.update()
            
            # 关闭对话框
            self._close_font_selector_dialog()
            
            self._show_snackbar("字体已更新，重启应用后完全生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("字体更新失败", ft.Colors.RED)
    
    def _close_font_selector_dialog(self) -> None:
        """关闭字体选择对话框。"""
        if hasattr(self, 'font_selector_dialog'):
            self.font_selector_dialog.open = False
            self._page.update()
    
    async def _pick_font_file(self) -> None:
        """打开文件选择器选择字体文件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择字体文件",
            allowed_extensions=["ttf", "otf", "ttc", "woff", "woff2"],
            allow_multiple=False,
        )
        if result and len(result) > 0:
            file_path = result[0].path
            self._load_custom_font_file(file_path)
    
    def _load_custom_font_file(self, file_path: str) -> None:
        """加载自定义字体文件。
        
        Args:
            file_path: 字体文件路径
        """
        try:
            from pathlib import Path
            import shutil
            
            font_file = Path(file_path)
            if not font_file.exists():
                self._show_snackbar("字体文件不存在", ft.Colors.RED)
                return
            
            # 获取字体文件名（不含扩展名）
            font_name = font_file.stem
            
            # 创建自定义字体目录
            # 将字体文件保存在数据目录下的 custom_fonts 子目录中
            data_dir = self.config_service.get_data_dir()
            custom_fonts_dir = data_dir / "custom_fonts"
            custom_fonts_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制字体文件到自定义字体目录
            dest_font_file = custom_fonts_dir / font_file.name
            shutil.copy2(font_file, dest_font_file)
            
            # 保存字体文件路径到配置
            self.config_service.set_config_value("custom_font_file", str(dest_font_file))
            
            # 在Flet中注册字体
            try:
                # 为字体创建一个唯一名称
                custom_font_key = f"CustomFont_{font_name}"
                
                # 将字体添加到页面
                if not hasattr(self._page, 'fonts') or self._page.fonts is None:
                    self._page.fonts = {}
                
                self._page.fonts[custom_font_key] = str(dest_font_file)
                
                # 应用字体
                self._apply_font_selection(custom_font_key, f"{font_name} (自定义)")
                
                logger.info(f"成功加载字体文件: {file_path}")
                
            except Exception as e:
                logger.error(f"注册字体失败: {e}")
                self._show_snackbar(f"注册字体失败: {e}", ft.Colors.RED)
                
        except Exception as e:
            logger.error(f"加载字体文件失败: {e}")
            self._show_snackbar(f"加载字体文件失败: {e}", ft.Colors.RED)
    
    def _on_font_change(self, e: ft.ControlEvent) -> None:
        """字体更改事件处理。
        
        Args:
            e: 控件事件对象
        """
        selected_font = e.control.value
        
        # 保存字体设置
        if self.config_service.set_config_value("font_family", selected_font):
            # 更新预览文本字体
            self.font_preview_text.font_family = selected_font
            self.font_preview_text.update()
            
            # 尝试更新页面字体（部分生效）
            if self._page.theme:
                self._page.theme.font_family = selected_font
            if self._page.dark_theme:
                self._page.dark_theme.font_family = selected_font
            self._page.update()
            
            self._show_snackbar("字体已更新，重启应用后完全生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("字体更新失败", ft.Colors.RED)
    
    def _on_font_scale_change(self, e: ft.ControlEvent) -> None:
        """字体大小更改事件处理。
        
        Args:
            e: 控件事件对象
        """
        scale_percent = int(e.control.value)
        scale = scale_percent / 100.0
        
        # 更新文本显示
        self.font_scale_text.value = f"字体大小: {scale_percent}%"
        self.font_scale_text.update()
        
        # 保存字体大小设置
        if self.config_service.set_config_value("font_scale", scale):
            # 更新预览文本大小
            base_size = 16
            new_size = int(base_size * scale)
            self.font_preview_text.size = new_size
            self.font_preview_text.update()
            
            self._show_snackbar(f"字体大小已设置为 {scale_percent}%，重启应用后完全生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("字体大小更新失败", ft.Colors.RED)
    
    def _on_reset_window_position(self, e: ft.ControlEvent) -> None:
        """重置窗口位置和大小事件处理。
        
        Args:
            e: 控件事件对象
        """
        from constants import WINDOW_WIDTH, WINDOW_HEIGHT
        
        # 清除保存的窗口位置、大小和最大化状态
        self.config_service.set_config_value("window_left", None)
        self.config_service.set_config_value("window_top", None)
        self.config_service.set_config_value("window_width", None)
        self.config_service.set_config_value("window_height", None)
        self.config_service.set_config_value("window_maximized", False)
        
        # 取消最大化状态
        self._page.window.maximized = False
        
        # 重置窗口大小为默认值
        self._page.window.width = WINDOW_WIDTH
        self._page.window.height = WINDOW_HEIGHT
        
        # 将窗口移动到屏幕中央
        self._page.window.center()
        self._page.update()
        
        self._show_snackbar("窗口位置和大小已重置为默认值", ft.Colors.GREEN)
    
    def _on_create_desktop_shortcut(self, e: ft.ControlEvent) -> None:
        """创建桌面快捷方式。
        
        Args:
            e: 控件事件对象
        """
        from utils.file_utils import create_desktop_shortcut
        
        # 调用工具函数创建快捷方式
        success, message = create_desktop_shortcut()
        
        # 显示结果
        color = ft.Colors.GREEN if success else (ft.Colors.BLUE if "已存在" in message else ft.Colors.ORANGE)
        self._show_snackbar(message, color)
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        try:
            snackbar: ft.SnackBar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=color,
                duration=2000,
            )
            # 使用保存的页面引用作为回退（有时候 self._page 在后台线程中为 None）
            page = getattr(self, '_saved_page', None) or getattr(self, 'page', None)
            if not page:
                return
            # 将 snackbar 添加到 overlay 并刷新页面
            try:
                page.overlay.append(snackbar)
                snackbar.open = True
                page.update()
            except Exception:
                # 如果 overlay 不可用或在后台线程中引发错误，则尝试安全地设置一个简单替代：
                # 将消息打印到控制台（避免抛出未捕获异常）
                logger.error(f"Snackbar show failed: {message}")
        except Exception:
            # 最后兜底，避免线程未捕获异常终止程序
            try:
                logger.error(f"_show_snackbar error: {message}")
            except Exception:
                pass

