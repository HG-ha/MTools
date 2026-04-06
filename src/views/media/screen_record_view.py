# -*- coding: utf-8 -*-
"""屏幕录制视图模块。

使用 FFmpeg 实现屏幕录制功能。
"""

import asyncio
import gc
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import flet as ft
import ffmpeg

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, FFmpegService
from utils.logger import logger
from utils import get_unique_path
from utils.file_utils import get_directory_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class ScreenRecordView(ft.Container):
    """屏幕录制视图类。
    
    使用 FFmpeg 录制屏幕，支持：
    - 全屏录制
    - 指定窗口录制
    - 自定义区域录制
    - 音频设备选择
    - 多种输出格式
    - 帧率设置
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化屏幕录制视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        
        # 录制状态
        self.is_recording: bool = False
        self.is_paused: bool = False
        self.recording_process: Optional[subprocess.Popen] = None
        self.recording_start_time: Optional[float] = None
        self.pause_duration: float = 0.0
        self.pause_start_time: Optional[float] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.should_stop_timer: bool = False
        
        # 输出文件
        self.output_file: Optional[Path] = None
        
        # 设备列表缓存
        self.audio_devices: List[Tuple[str, str]] = []  # (device_id, display_name)
        self.window_list: List[Tuple[str, str]] = []  # (window_id, title)
        
        self.expand: bool = True
        self.padding: ft.padding = ft.Padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 交互式选区（拖拽框选）
        self.pick_region_btn = None
        
        # 构建界面
        self._build_ui()
        
        # 注意：全局热键由 GlobalHotkeyService 在应用启动时注册
        # 这里不再重复注册，避免冲突
    
    def _get_platform(self) -> str:
        """获取当前平台。"""
        if sys.platform == 'win32':
            return 'windows'
        elif sys.platform == 'darwin':
            return 'macos'
        else:
            return 'linux'

    def _ensure_windows_dpi_aware(self) -> None:
        """尽量启用 DPI aware，避免多屏/缩放下坐标不一致。"""
        if self._get_platform() != "windows":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # 老 API，足够让 GetSystemMetrics/GetWindowRect 返回真实像素
            user32.SetProcessDPIAware()
        except Exception:
            pass

    def _get_virtual_screen_rect_windows(self) -> Tuple[int, int, int, int]:
        """Windows：获取虚拟桌面矩形 (left, top, width, height)。支持多屏与负坐标。"""
        self._ensure_windows_dpi_aware()
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        # 方案 1（首选）：EnumDisplayMonitors 求所有显示器矩形并集（最可靠）
        try:
            monitors = []
            
            def _monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                try:
                    rect = lprcMonitor.contents
                    monitors.append({
                        'left': int(rect.left),
                        'top': int(rect.top),
                        'right': int(rect.right),
                        'bottom': int(rect.bottom),
                    })
                except Exception as ex:
                    logger.warning(f"枚举显示器回调异常: {ex}")
                return True  # 继续枚举
            
            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_int,  # BOOL
                ctypes.c_void_p,  # HMONITOR
                ctypes.c_void_p,  # HDC
                ctypes.POINTER(wintypes.RECT),  # LPRECT
                ctypes.c_long,  # LPARAM
            )
            callback = MONITORENUMPROC(_monitor_enum_proc)
            user32.EnumDisplayMonitors(None, None, callback, 0)
            
            if monitors:
                left = min(m['left'] for m in monitors)
                top = min(m['top'] for m in monitors)
                right = max(m['right'] for m in monitors)
                bottom = max(m['bottom'] for m in monitors)
                width = right - left
                height = bottom - top
                if width >= 200 and height >= 200:
                    logger.info(f"虚拟桌面 (EnumDisplayMonitors): {width}x{height}, offset=({left},{top}), 显示器={len(monitors)}")
                    return left, top, width, height
                else:
                    logger.warning(f"EnumDisplayMonitors 返回异常尺寸: {width}x{height}, monitors={monitors}")
            else:
                logger.warning("EnumDisplayMonitors 未枚举到任何显示器")
        except Exception as ex:
            logger.warning(f"EnumDisplayMonitors 失败: {ex}")

        # 方案 2：GetSystemMetrics（备选）
        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79
        left2 = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
        top2 = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
        width2 = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
        height2 = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        logger.info(f"GetSystemMetrics 虚拟桌面: {width2}x{height2}, offset=({left2},{top2})")

        if width2 >= 200 and height2 >= 200:
            return left2, top2, width2, height2

        logger.warning(f"虚拟桌面尺寸异常（{width2}x{height2}），尝试主屏尺寸。")

        # 方案 3：退回主屏尺寸
        SM_CXSCREEN = 0
        SM_CYSCREEN = 1
        width3 = int(user32.GetSystemMetrics(SM_CXSCREEN))
        height3 = int(user32.GetSystemMetrics(SM_CYSCREEN))
        logger.info(f"主屏尺寸: {width3}x{height3}")
        if width3 >= 200 and height3 >= 200:
            return 0, 0, width3, height3

        # 最后兜底：给一个常见分辨率，避免崩溃
        logger.warning("无法获取屏幕尺寸，回退到 1920x1080")
        return 0, 0, 1920, 1080

    def _get_window_rect_windows(self, window_title: str) -> Optional[Tuple[int, int, int, int]]:
        """Windows：根据窗口标题获取窗口矩形 (left, top, width, height)。
        
        优先选择尺寸最大的匹配窗口，避免匹配到托盘图标等小窗口。
        """
        if self._get_platform() != "windows":
            return None
        if not window_title:
            return None

        self._ensure_windows_dpi_aware()
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            # 收集所有匹配的窗口及其尺寸，选择最大的那个
            candidates = []  # [(hwnd, left, top, w, h, area), ...]
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def cb(h, lparam):
                if user32.IsWindowVisible(h):
                    length = user32.GetWindowTextLengthW(h)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(h, buf, length + 1)
                        title = buf.value
                        # 精确匹配或包含匹配
                        if title and (title == window_title or window_title in title):
                            rect = wintypes.RECT()
                            if user32.GetWindowRect(h, ctypes.byref(rect)):
                                left = int(rect.left)
                                top = int(rect.top)
                                w = int(rect.right) - left
                                h_size = int(rect.bottom) - top
                                # 只考虑足够大的窗口（排除托盘图标等）
                                if w >= 100 and h_size >= 100:
                                    area = w * h_size
                                    candidates.append((h, left, top, w, h_size, area))
                return True

            user32.EnumWindows(EnumWindowsProc(cb), 0)

            if not candidates:
                logger.warning(f"未找到尺寸 ≥ 100x100 的窗口 '{window_title}'")
                return None

            # 选择面积最大的窗口
            candidates.sort(key=lambda x: x[5], reverse=True)
            best = candidates[0]
            logger.info(f"找到 {len(candidates)} 个匹配窗口，选择最大的: {best[3]}x{best[4]}")
            return best[1], best[2], best[3], best[4]
        except Exception as ex:
            logger.warning(f"获取窗口矩形失败: {ex}")
            return None
    
    def _get_all_window_rects_windows(self) -> List[Tuple[str, int, int, int, int]]:
        """获取所有可见窗口的矩形信息。
        
        Returns:
            窗口列表，每项为 (窗口标题, left, top, width, height)
            按 Z-order 排序（顶层窗口在前）
        """
        if self._get_platform() != "windows":
            return []
        
        self._ensure_windows_dpi_aware()
        windows = []
        
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # 系统窗口黑名单
            blacklist = {
                'Program Manager', 'Windows Input Experience',
                'Microsoft Text Input Application', 'Settings',
                'Windows Shell Experience Host', 'NVIDIA GeForce Overlay',
                'AMD Link Server', 'PopupHost', '',
            }
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            
            def callback(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        
                        if title and title not in blacklist:
                            rect = wintypes.RECT()
                            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                                left = int(rect.left)
                                top = int(rect.top)
                                w = int(rect.right) - left
                                h = int(rect.bottom) - top
                                # 只添加尺寸足够大的窗口
                                if w >= 50 and h >= 50:
                                    windows.append((title, left, top, w, h))
                return True
            
            user32.EnumWindows(EnumWindowsProc(callback), 0)
            
        except Exception as ex:
            logger.warning(f"获取窗口列表失败: {ex}")
        
        return windows
    
    def _invoke_ui(self, fn) -> None:
        """尽量安全地从后台线程回到 UI 线程执行。"""
        try:
            if hasattr(self._page, "call_from_thread"):
                self._page.call_from_thread(fn)
                return
        except Exception:
            pass
        # 回退：直接调用（当前项目里已有后台线程直接 page.update 的用法）
        try:
            fn()
        except Exception:
            pass
    
    def _get_audio_devices(self) -> List[Tuple[str, str]]:
        """获取可用的音频设备列表。
        
        Returns:
            音频设备列表，每项为 (设备ID, 显示名称)
        """
        return self.ffmpeg_service.list_audio_devices()
    
    def _get_audio_devices_categorized(self) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """获取分类的音频设备列表。
        
        Returns:
            (麦克风设备列表, 系统音频/输出设备列表)
        """
        all_devices = self._get_audio_devices()
        
        mic_devices = []
        system_devices = []
        
        # 麦克风设备的关键词
        mic_keywords = [
            'microphone', 'mic', '麦克风', '话筒', 'headset',
            '耳机', '耳麦', 'webcam', 'camera', '摄像头',
        ]
        
        # 系统音频/输出设备的关键词（优先识别为系统音频）
        system_audio_keywords = [
            '立体声混音', 'stereo mix', 'what u hear', 'wave out',
            'loopback', '混音', 'mix', 'wasapi', 'virtual cable',
            'vb-audio', 'voicemeeter', 'blackhole', 'soundflower',
            'speaker', 'headphone', '扬声器', '耳机', 'realtek',
            'nvidia', 'hdmi', 'displayport', 'output', '输出',
        ]
        
        for device_id, display_name in all_devices:
            name_lower = display_name.lower()
            
            # 优先检查是否是麦克风
            is_mic = any(keyword in name_lower for keyword in mic_keywords)
            # 再检查是否是系统音频
            is_system = any(keyword in name_lower for keyword in system_audio_keywords)
            
            if is_mic and not is_system:
                mic_devices.append((device_id, display_name))
            else:
                # 其他设备都归类到系统音频，让用户自己选择
                system_devices.append((device_id, display_name))
        
        # 如果系统音频设备列表为空，把所有设备都放进去让用户选
        if not system_devices:
            system_devices = all_devices[:]
        
        logger.info(f"分类结果: {len(mic_devices)} 个麦克风, {len(system_devices)} 个系统音频设备")
        return mic_devices, system_devices
    
    def _get_window_list(self) -> List[Tuple[str, str]]:
        """获取可用的窗口列表（仅 Windows）。
        
        只返回在屏幕上可见且尺寸 ≥ 100x100 的窗口，排除托盘图标等。
        
        Returns:
            窗口列表，每项为 (窗口标题, 显示名称)
        """
        windows = []
        platform = self._get_platform()
        
        if platform != 'windows':
            return windows
        
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            self._ensure_windows_dpi_aware()
            
            # 系统窗口黑名单
            blacklist = {
                'Program Manager', 'Windows Input Experience', 
                'Microsoft Text Input Application', 'Settings',
                'Windows Shell Experience Host', 'Microsoft Store',
                'NVIDIA GeForce Overlay', 'AMD Link Server',
            }
            
            # 枚举窗口回调
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HWND,
                wintypes.LPARAM
            )
            
            def enum_windows_callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        title = buffer.value
                        if title and len(title) > 1 and title not in blacklist:
                            # 检查窗口尺寸，排除托盘图标等小窗口
                            rect = wintypes.RECT()
                            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                                w = int(rect.right) - int(rect.left)
                                h = int(rect.bottom) - int(rect.top)
                                # 只添加尺寸足够大的窗口
                                if w >= 100 and h >= 100:
                                    display_name = f"{title[:40]}{'...' if len(title) > 40 else ''} ({w}x{h})"
                                    windows.append((title, display_name))
                return True
            
            user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
            
        except Exception as ex:
            logger.warning(f"获取窗口列表失败: {ex}")
        
        return windows
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            self.padding = ft.Padding.all(0)
            self.content = FFmpegInstallView(
                self._page,
                self.ffmpeg_service,
                on_back=self._on_back_click,
                tool_name="屏幕录制"
            )
            return

        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("屏幕录制", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 录制计时显示
        self.timer_text = ft.Text(
            "00:00:00",
            size=48,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        
        self.status_text = ft.Text(
            "准备就绪",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        )
        
        self.recording_indicator = ft.Container(
            content=ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, color=ft.Colors.GREY, size=16),
            visible=True,
        )
        
        timer_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self.recording_indicator,
                            self.timer_text,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_SMALL,
                    ),
                    self.status_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
        )
        
        # ===== 录制源设置 =====
        platform = self._get_platform()
        
        # 录制目标选择
        area_options = [
            ft.dropdown.Option("fullscreen", "全屏"),
            ft.dropdown.Option("custom", "自定义区域"),
        ]
        
        # Windows 支持录制特定窗口
        if platform == 'windows':
            area_options.insert(1, ft.dropdown.Option("window", "指定窗口"))
        
        # 保存选择的录制区域信息
        self.selected_region = None  # (x, y, w, h) 或 None 表示全屏
        self.selected_region_type = "fullscreen"  # fullscreen, window, custom
        self.selected_window_title = None  # 选择的窗口标题（用于显示）
        
        # 三合一选择按钮
        self.pick_area_btn = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SCREENSHOT_MONITOR, size=20),
                    ft.Text("选择录制区域", size=14, weight=ft.FontWeight.W_500),
                ],
                spacing=8,
            ),
            on_click=self._on_pick_area_click,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            ),
        )
        
        # 当前选择的区域显示
        self.region_info_text = ft.Text(
            "🖥️ 当前：全屏录制",
            size=13,
            weight=ft.FontWeight.W_500,
        )
        
        self.region_detail_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 用于显示选区预览（可选）
        self.region_preview_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.region_info_text,
                    self.region_detail_text,
                ],
                spacing=2,
            ),
        )
        
        # 兼容旧代码的隐藏变量
        self.area_dropdown = ft.Dropdown(
            label="录制目标",
            value="fullscreen",
            options=area_options,
            width=200,
            visible=False,  # 隐藏，用新的三合一按钮替代
        )
        self.window_dropdown = ft.Dropdown(visible=False)
        self.refresh_windows_btn = ft.IconButton(icon=ft.Icons.REFRESH, visible=False)
        self.window_row = ft.Row(visible=False)
        self.offset_x = ft.TextField(value="0", visible=False)
        self.offset_y = ft.TextField(value="0", visible=False)
        self.width_field = ft.TextField(value="1920", visible=False)
        self.height_field = ft.TextField(value="1080", visible=False)
        self.custom_area_row = ft.Row(visible=False)
        self.pick_region_btn = ft.Button(visible=False)
        self.pick_region_hint = ft.Text(visible=False)
        
        # 录制源信息卡片（现代化设计）
        source_area = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.VIDEOCAM, size=28, color=ft.Colors.WHITE),
                        padding=12,
                        bgcolor=ft.Colors.RED_600,
                        border_radius=10,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("录制区域选择", size=15, weight=ft.FontWeight.W_600),
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Text("🖥️ 全屏", size=11),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                        border_radius=4,
                                    ),
                                    ft.Container(
                                        content=ft.Text("🪟 窗口", size=11),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                        border_radius=4,
                                    ),
                                    ft.Container(
                                        content=ft.Text("📐 区域", size=11),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                                        border_radius=4,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Text(
                                "点击开始录制后，在屏幕上选择要录制的区域",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                italic=True,
                            ),
                        ],
                        spacing=6,
                        expand=True,
                    ),
                ],
                spacing=PADDING_LARGE,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=PADDING_LARGE,
            border_radius=12,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
                    ft.Colors.with_opacity(0.02, ft.Colors.SECONDARY),
                ],
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY)),
        )
        
        # ===== 音频设置 =====
        # 麦克风录制
        self.record_mic = ft.Checkbox(
            label="录制麦克风",
            value=False,
            on_change=self._on_mic_checkbox_change,
        )
        
        self.mic_device_dropdown = ft.Dropdown(
            label="麦克风设备",
            width=280,
            visible=False,
        )
        
        self.refresh_mic_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="刷新麦克风列表",
            on_click=self._on_refresh_audio_devices,
            visible=False,
        )
        
        self.mic_device_row = ft.Row(
            controls=[
                self.mic_device_dropdown,
                self.refresh_mic_btn,
            ],
            spacing=PADDING_SMALL,
            visible=False,
        )
        
        # 扬声器/电脑声音录制（立体声混音）
        self.record_system_audio = ft.Checkbox(
            label="录制电脑声音 (扬声器)",
            value=False,
            on_change=self._on_system_audio_checkbox_change,
        )
        
        self.system_audio_dropdown = ft.Dropdown(
            label="音频输出设备",
            width=280,
            visible=False,
        )
        
        self.refresh_system_audio_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="刷新设备列表",
            on_click=self._on_refresh_audio_devices,
            visible=False,
        )
        
        self.system_audio_row = ft.Row(
            controls=[
                self.system_audio_dropdown,
                self.refresh_system_audio_btn,
            ],
            spacing=PADDING_SMALL,
            visible=False,
        )
        
        # 系统音频提示
        self.system_audio_tip = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=14, color=ft.Colors.PRIMARY),
                            ft.Text(
                                "选择「立体声混音」或「Stereo Mix」可录制电脑播放的所有声音",
                                size=11,
                                color=ft.Colors.PRIMARY,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "如果看不到「立体声混音」：右键音量图标 → 声音设置 → 更多设置 → 录制 → 右键空白处 → 显示禁用设备 → 启用",
                                size=10,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=4,
            ),
            visible=False,
        )
        
        # 兼容旧代码的属性别名
        self.record_audio = self.record_mic
        self.audio_device_dropdown = self.mic_device_dropdown
        
        audio_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("音频设置", size=18, weight=ft.FontWeight.W_600),
                    self.record_mic,
                    self.mic_device_row,
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                    self.record_system_audio,
                    self.system_audio_row,
                    self.system_audio_tip,
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_LARGE,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.PRIMARY),
        )
        
        # ===== 视频设置 =====
        # 帧率选择
        # 注意：Windows gdigrab 实际最高只能稳定达到 30-60 FPS
        # 高于 60 FPS 的选项仅在录制游戏窗口或高刷显示器时有意义
        self.fps_dropdown = ft.Dropdown(
            label="帧率 (FPS)",
            value="30",
            options=[
                ft.dropdown.Option("15", "15 FPS - 省资源"),
                ft.dropdown.Option("24", "24 FPS - 电影"),
                ft.dropdown.Option("30", "30 FPS - 标准 (推荐)"),
                ft.dropdown.Option("60", "60 FPS - 流畅"),
            ],
            width=180,
        )
        
        # 帧率提示
        self.fps_hint = ft.Text(
            "提示：Windows 屏幕录制实际帧率受限于 GDI 抓屏效率，通常最高 30-60 FPS",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 输出格式
        self.format_dropdown = ft.Dropdown(
            label="输出格式",
            value="mp4",
            options=[
                ft.dropdown.Option("mp4", "MP4 (推荐)"),
                ft.dropdown.Option("mkv", "MKV"),
                ft.dropdown.Option("avi", "AVI"),
                ft.dropdown.Option("mov", "MOV"),
                ft.dropdown.Option("webm", "WebM"),
            ],
            width=180,
        )
        
        # 视频编码器 - 检测 GPU 编码器
        encoder_options = [
            ft.dropdown.Option("libx264", "H.264 (CPU)"),
            ft.dropdown.Option("libx265", "H.265 (CPU)"),
            ft.dropdown.Option("libvpx-vp9", "VP9 (CPU)"),
        ]
        
        # 检测 GPU 编码器
        gpu_info = self.ffmpeg_service.detect_gpu_encoders()
        self.gpu_encoders_available = gpu_info.get("available", False)
        gpu_encoders = gpu_info.get("encoders", [])
        listed_encoders = gpu_info.get("listed_encoders", [])
        
        # 日志：显示检测结果
        if listed_encoders:
            logger.info(f"FFmpeg 支持的 GPU 编码器: {listed_encoders}")
            if gpu_encoders:
                logger.info(f"验证可用的 GPU 编码器: {gpu_encoders}")
            else:
                logger.warning(f"GPU 编码器验证全部失败，可能是驱动问题")
        
        if self.gpu_encoders_available:
            if "h264_nvenc" in gpu_encoders:
                encoder_options.insert(0, ft.dropdown.Option("h264_nvenc", "H.264 (NVENC) - NVIDIA ⚡"))
            if "hevc_nvenc" in gpu_encoders:
                encoder_options.insert(1, ft.dropdown.Option("hevc_nvenc", "H.265 (NVENC) - NVIDIA ⚡"))
            if "h264_amf" in gpu_encoders:
                encoder_options.insert(0, ft.dropdown.Option("h264_amf", "H.264 (AMF) - AMD ⚡"))
            if "hevc_amf" in gpu_encoders:
                encoder_options.insert(1, ft.dropdown.Option("hevc_amf", "H.265 (AMF) - AMD ⚡"))
            if "h264_qsv" in gpu_encoders:
                encoder_options.insert(0, ft.dropdown.Option("h264_qsv", "H.264 (QSV) - Intel ⚡"))
            if "hevc_qsv" in gpu_encoders:
                encoder_options.insert(1, ft.dropdown.Option("hevc_qsv", "H.265 (QSV) - Intel ⚡"))
            if "h264_videotoolbox" in gpu_encoders:
                encoder_options.insert(0, ft.dropdown.Option("h264_videotoolbox", "H.264 (VideoToolbox) - Apple ⚡"))
            if "hevc_videotoolbox" in gpu_encoders:
                encoder_options.insert(1, ft.dropdown.Option("hevc_videotoolbox", "H.265 (VideoToolbox) - Apple ⚡"))
        
        # 默认选择 GPU 编码器（如果可用）
        default_encoder = "libx264"
        if "h264_videotoolbox" in gpu_encoders:
            default_encoder = "h264_videotoolbox"
        elif "h264_nvenc" in gpu_encoders:
            default_encoder = "h264_nvenc"
        elif "h264_amf" in gpu_encoders:
            default_encoder = "h264_amf"
        elif "h264_qsv" in gpu_encoders:
            default_encoder = "h264_qsv"
        
        self.encoder_dropdown = ft.Dropdown(
            label="视频编码器",
            value=default_encoder,
            options=encoder_options,
            width=250,
            on_select=self._on_encoder_change,
        )
        
        # 编码预设 - 根据默认编码器初始化
        if default_encoder.endswith("_nvenc"):
            preset_options = [
                ft.dropdown.Option("p1", "P1 - 最快"),
                ft.dropdown.Option("p2", "P2 - 很快"),
                ft.dropdown.Option("p3", "P3 - 快"),
                ft.dropdown.Option("p4", "P4 - 中等 (推荐)"),
                ft.dropdown.Option("p5", "P5 - 慢"),
                ft.dropdown.Option("p6", "P6 - 较慢"),
                ft.dropdown.Option("p7", "P7 - 最慢 (质量最好)"),
            ]
            default_preset = "p4"
        elif default_encoder.endswith("_amf"):
            preset_options = [
                ft.dropdown.Option("speed", "速度优先"),
                ft.dropdown.Option("balanced", "平衡 (推荐)"),
                ft.dropdown.Option("quality", "质量优先"),
            ]
            default_preset = "balanced"
        elif default_encoder.endswith("_qsv"):
            preset_options = [
                ft.dropdown.Option("veryfast", "很快"),
                ft.dropdown.Option("faster", "较快"),
                ft.dropdown.Option("fast", "快"),
                ft.dropdown.Option("medium", "中等 (推荐)"),
                ft.dropdown.Option("slow", "慢"),
            ]
            default_preset = "medium"
        elif default_encoder.endswith("_videotoolbox"):
            preset_options = [
                ft.dropdown.Option("default", "默认"),
            ]
            default_preset = "default"
        else:
            preset_options = [
                ft.dropdown.Option("ultrafast", "最快 (质量最低)"),
                ft.dropdown.Option("superfast", "超快"),
                ft.dropdown.Option("veryfast", "很快"),
                ft.dropdown.Option("faster", "较快"),
                ft.dropdown.Option("fast", "快 (推荐)"),
                ft.dropdown.Option("medium", "中等"),
                ft.dropdown.Option("slow", "慢 (质量更好)"),
            ]
            default_preset = "fast"
        
        self.preset_dropdown = ft.Dropdown(
            label="编码预设",
            value=default_preset,
            options=preset_options,
            width=200,
        )
        
        # 质量设置 (CRF/CQ)
        self.quality_slider = ft.Slider(
            min=15,
            max=35,
            value=23,
            divisions=20,
            label="{value}",
            on_change=self._on_quality_change,
            expand=True,
        )
        self.quality_text = ft.Text("质量: 23 (数值越小，质量越好，文件越大)", size=12)
        
        # GPU 状态提示
        gpu_status = ""
        if self.gpu_encoders_available:
            gpu_list = []
            if any("nvenc" in e for e in gpu_encoders):
                gpu_list.append("NVIDIA")
            if any("amf" in e for e in gpu_encoders):
                gpu_list.append("AMD")
            if any("qsv" in e for e in gpu_encoders):
                gpu_list.append("Intel")
            gpu_status = f"✅ 已检测到 GPU 加速: {', '.join(gpu_list)}"
        else:
            gpu_status = "⚠️ 未检测到 GPU 加速，将使用 CPU 编码"
        
        self.gpu_status_text = ft.Text(gpu_status, size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        video_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("视频设置", size=18, weight=ft.FontWeight.W_600),
                    self.gpu_status_text,
                    ft.Row(
                        controls=[
                            self.fps_dropdown,
                            self.format_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                        wrap=True,
                    ),
                    self.fps_hint,
                    ft.Row(
                        controls=[
                            self.encoder_dropdown,
                            self.preset_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                        wrap=True,
                    ),
                    ft.Column(
                        controls=[
                            self.quality_text,
                            self.quality_slider,
                        ],
                        spacing=0,
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_LARGE,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.PRIMARY),
        )
        
        # ===== 输出设置 =====
        # 默认保存到 用户目录/Videos/MTools/录屏
        default_output = Path.home() / "Videos" / "MTools" / "录屏"
        try:
            default_output.mkdir(parents=True, exist_ok=True)
        except Exception:
            # 如果无法创建，使用用户视频目录
            default_output = Path.home() / "Videos"
            if not default_output.exists():
                default_output = Path.home()
        
        self.output_path_field = ft.TextField(
            label="保存位置",
            value=str(default_output),
            expand=True,
            read_only=True,
        )
        
        # 打开输出文件夹按钮（小型）
        self.open_folder_btn = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="打开输出文件夹",
            on_click=self._on_open_folder,
        )
        
        output_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=18, weight=ft.FontWeight.W_600),
                    ft.Row(
                        controls=[
                            self.output_path_field,
                            ft.IconButton(
                                icon=ft.Icons.CREATE_NEW_FOLDER,
                                tooltip="选择文件夹",
                                on_click=self._on_select_folder,
                            ),
                            self.open_folder_btn,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_LARGE,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.PRIMARY),
        )
        
        # 控制按钮（开始/停止 二合一）- 现代化设计
        self.record_btn = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, size=24, color=ft.Colors.WHITE),
                        ft.Text("开始录制", size=18, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                on_click=self._on_record_toggle,
                style=ft.ButtonStyle(
                    bgcolor={
                        ft.ControlState.DEFAULT: ft.Colors.RED_600,
                        ft.ControlState.HOVERED: ft.Colors.RED_700,
                        ft.ControlState.PRESSED: ft.Colors.RED_800,
                    },
                    color=ft.Colors.WHITE,
                    elevation={"default": 4, "hovered": 8},
                    animation_duration=200,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(horizontal=32, vertical=16),
                ),
                height=60,
            ),
        )
        
        control_area = ft.Container(
            content=ft.Column(
                controls=[
                    self.record_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=PADDING_MEDIUM,
            ),
            padding=ft.Padding.symmetric(vertical=PADDING_LARGE),
        )
        
        # 平台提示
        platform_info = {
            'windows': '当前系统: Windows - 使用 GDI 屏幕捕获，支持录制指定窗口',
            'macos': '当前系统: macOS - 使用 AVFoundation 屏幕捕获',
            'linux': '当前系统: Linux - 使用 X11 屏幕捕获',
        }
        
        platform_note = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.PRIMARY),
                    ft.Text(
                        platform_info.get(platform, '未知系统'),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=PADDING_MEDIUM),
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                timer_area,
                source_area,
                audio_area,
                video_area,
                output_area,
                platform_note,
                control_area,  # 放到最后
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
        
        # 组装主界面 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,  # 取消间距，让布局更紧凑
        )
    
    def _on_back_click(self, e=None) -> None:
        """处理返回按钮点击。"""
        # 如果正在录制，先停止
        if self.is_recording:
            self._stop_recording()
        
        if self.on_back:
            self.on_back()
    
    def _on_area_change(self, e) -> None:
        """处理录制目标选择变化。"""
        value = e.control.value
        
        # 窗口选择（仅 Windows）
        self.window_row.visible = (value == "window")
        self.window_dropdown.visible = (value == "window")
        self.refresh_windows_btn.visible = (value == "window")
        
        # 如果选择窗口，加载窗口列表
        if value == "window" and not self.window_dropdown.options:
            self._load_window_list()
        
        # 自定义区域
        self.custom_area_row.visible = (value == "custom")

        # 交互式框选按钮仅在自定义区域时显示（Windows 下可用；其它平台也可用但体验一般）
        if hasattr(self, "pick_region_btn") and self.pick_region_btn:
            self.pick_region_btn.visible = (value == "custom")
        if hasattr(self, "pick_region_hint") and self.pick_region_hint:
            self.pick_region_hint.visible = (value == "custom")
        
        self._page.update()

    def _on_pick_area_click(self, e) -> None:
        """三合一选择录制区域：全屏/窗口/自定义区域。"""
        self.pick_area_btn.disabled = True
        self._page.update()

        async def _pick_area_async():
            from utils.screen_selector import select_screen_region
            result = await asyncio.to_thread(
                select_screen_region,
                hint_main="🎯 点击选择窗口  |  拖拽框选区域",
                hint_sub="按 F 选择当前屏幕  |  ESC 取消",
                return_window_title=True,
            )

            try:
                if result is None:
                    # 用户取消
                    self._show_message("已取消选择", ft.Colors.ORANGE)
                elif isinstance(result, tuple) and len(result) == 5:
                    # 窗口模式：(x, y, w, h, window_title)
                    x, y, w, h, title = result
                    self.selected_region = (x, y, w, h)
                    self.selected_region_type = "window"
                    self.selected_window_title = title
                    display_title = title[:30] + "..." if len(title) > 30 else title
                    self.region_info_text.value = f"🪟 当前：窗口录制"
                    self.region_detail_text.value = f"{display_title} ({w}×{h})"
                    self._show_message(f"已选择窗口：{display_title}", ft.Colors.GREEN)
                elif isinstance(result, tuple) and len(result) == 4:
                    # 自定义区域 / 全屏 / 显示器
                    x, y, w, h = result
                    self.selected_region = (x, y, w, h)
                    self.selected_region_type = "custom"
                    self.selected_window_title = None
                    self.region_info_text.value = f"📐 当前：自定义区域"
                    self.region_detail_text.value = f"位置 ({x}, {y}) 尺寸 {w}×{h}"
                    self._show_message(f"已选择区域：{w}×{h}", ft.Colors.GREEN)
            finally:
                self.pick_area_btn.disabled = False
                self._page.update()

        self._page.run_task(_pick_area_async)

    def _on_pick_region_click(self, e) -> None:
        """交互式拖拽框选区域（兼容旧代码）。"""
        self._on_pick_area_click(e)
    
    def _on_mic_checkbox_change(self, e) -> None:
        """处理麦克风复选框变化。"""
        self.mic_device_row.visible = e.control.value
        self.mic_device_dropdown.visible = e.control.value
        self.refresh_mic_btn.visible = e.control.value
        
        # 如果勾选录制麦克风，加载设备列表
        if e.control.value and not self.mic_device_dropdown.options:
            self._load_audio_devices()
        
        self._page.update()
    
    def _on_system_audio_checkbox_change(self, e) -> None:
        """处理系统音频复选框变化。"""
        self.system_audio_row.visible = e.control.value
        self.system_audio_dropdown.visible = e.control.value
        self.refresh_system_audio_btn.visible = e.control.value
        self.system_audio_tip.visible = e.control.value
        
        # 如果勾选录制系统音频，加载设备列表
        if e.control.value and not self.system_audio_dropdown.options:
            self._load_audio_devices()
        
        self._page.update()
    
    def _on_audio_checkbox_change(self, e) -> None:
        """兼容旧代码的回调。"""
        self._on_mic_checkbox_change(e)
    
    def _load_audio_devices(self) -> None:
        """加载音频设备列表。"""
        mic_devices, system_devices = self._get_audio_devices_categorized()
        
        # 麦克风设备
        mic_options = []
        for device_id, display_name in mic_devices:
            mic_options.append(ft.dropdown.Option(device_id, display_name))
        
        if mic_options:
            self.mic_device_dropdown.options = mic_options
            self.mic_device_dropdown.value = mic_options[0].key
        else:
            self.mic_device_dropdown.options = [
                ft.dropdown.Option("none", "未找到麦克风设备")
            ]
            self.mic_device_dropdown.value = "none"
        
        # 系统音频设备
        system_options = []
        for device_id, display_name in system_devices:
            system_options.append(ft.dropdown.Option(device_id, display_name))
        
        if system_options:
            self.system_audio_dropdown.options = system_options
            self.system_audio_dropdown.value = system_options[0].key
        else:
            self.system_audio_dropdown.options = [
                ft.dropdown.Option("none", "未找到设备 (需在系统中启用立体声混音)")
            ]
            self.system_audio_dropdown.value = "none"
        
        self._page.update()
    
    def _load_window_list(self) -> None:
        """加载窗口列表。"""
        self.window_list = self._get_window_list()
        
        options = []
        for window_id, display_name in self.window_list:
            options.append(ft.dropdown.Option(window_id, display_name))
        
        if options:
            self.window_dropdown.options = options
            self.window_dropdown.value = options[0].key
        else:
            self.window_dropdown.options = [
                ft.dropdown.Option("none", "未找到可用窗口")
            ]
            self.window_dropdown.value = "none"
        
        self._page.update()
    
    def _on_refresh_audio_devices(self, e) -> None:
        """刷新音频设备列表。"""
        self._load_audio_devices()
        self._show_message("音频设备列表已刷新", ft.Colors.GREEN)
    
    def _on_refresh_windows(self, e) -> None:
        """刷新窗口列表。"""
        self._load_window_list()
        self._show_message("窗口列表已刷新", ft.Colors.GREEN)
    
    def _on_encoder_change(self, e) -> None:
        """处理编码器选择变化。"""
        encoder = e.control.value
        
        # 根据编码器类型更新预设选项
        if encoder.endswith("_nvenc"):
            # NVIDIA 编码器预设
            self.preset_dropdown.options = [
                ft.dropdown.Option("p1", "P1 - 最快"),
                ft.dropdown.Option("p2", "P2 - 很快"),
                ft.dropdown.Option("p3", "P3 - 快"),
                ft.dropdown.Option("p4", "P4 - 中等 (推荐)"),
                ft.dropdown.Option("p5", "P5 - 慢"),
                ft.dropdown.Option("p6", "P6 - 较慢"),
                ft.dropdown.Option("p7", "P7 - 最慢 (质量最好)"),
            ]
            self.preset_dropdown.value = "p4"
        elif encoder.endswith("_amf"):
            # AMD 编码器预设
            self.preset_dropdown.options = [
                ft.dropdown.Option("speed", "速度优先"),
                ft.dropdown.Option("balanced", "平衡 (推荐)"),
                ft.dropdown.Option("quality", "质量优先"),
            ]
            self.preset_dropdown.value = "balanced"
        elif encoder.endswith("_qsv"):
            # Intel 编码器预设
            self.preset_dropdown.options = [
                ft.dropdown.Option("veryfast", "很快"),
                ft.dropdown.Option("faster", "较快"),
                ft.dropdown.Option("fast", "快"),
                ft.dropdown.Option("medium", "中等 (推荐)"),
                ft.dropdown.Option("slow", "慢"),
            ]
            self.preset_dropdown.value = "medium"
        elif encoder.endswith("_videotoolbox"):
            # Apple VideoToolbox 没有预设概念，隐藏预设选项
            self.preset_dropdown.options = [
                ft.dropdown.Option("default", "默认"),
            ]
            self.preset_dropdown.value = "default"
        else:
            # CPU 编码器预设
            self.preset_dropdown.options = [
                ft.dropdown.Option("ultrafast", "最快 (质量最低)"),
                ft.dropdown.Option("superfast", "超快"),
                ft.dropdown.Option("veryfast", "很快"),
                ft.dropdown.Option("faster", "较快"),
                ft.dropdown.Option("fast", "快 (推荐)"),
                ft.dropdown.Option("medium", "中等"),
                ft.dropdown.Option("slow", "慢 (质量更好)"),
            ]
            self.preset_dropdown.value = "fast"
        
        self._page.update()
    
    def _on_quality_change(self, e) -> None:
        """处理质量滑块变化。"""
        quality = int(e.control.value)
        self.quality_text.value = f"质量: {quality} (数值越小，质量越好，文件越大)"
        self._page.update()
    
    async def _on_select_folder(self, e) -> None:
        """选择输出文件夹。"""
        result = await get_directory_path(self._page, dialog_title="选择保存位置")
        if result:
            self.output_path_field.value = result
            self._page.update()
    
    def _on_open_folder(self, e) -> None:
        """打开输出文件夹。"""
        import os
        output_path = self.output_path_field.value
        if output_path and Path(output_path).exists():
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', output_path])
            else:
                subprocess.run(['xdg-open', output_path])
    
    def _build_ffmpeg_stream(self) -> Optional[Tuple]:
        """构建 FFmpeg 录制流。
        
        Returns:
            (stream, output_file) 元组，如果 FFmpeg 不可用则返回 None
        """
        platform = self._get_platform()
        
        # 生成输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(self.output_path_field.value)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_format = self.format_dropdown.value
        self.output_file = output_dir / f"screen_record_{timestamp}.{output_format}"
        
        fps = self.fps_dropdown.value
        encoder = self.encoder_dropdown.value
        preset = self.preset_dropdown.value
        quality = int(self.quality_slider.value)
        
        streams = []
        
        if platform == 'windows':
            # 构建视频输入参数
            input_kwargs = {
                'format': 'gdigrab',
                'framerate': fps,
            }
            input_name = "desktop"
            
            # 使用新的三合一选择结果
            if self.selected_region and self.selected_region_type in ("window", "custom"):
                # 窗口或自定义区域模式
                x, y, w, h = self.selected_region
                # 确保宽高为偶数（编码器要求），最小 64x64
                w = max(64, (w // 2) * 2)
                h = max(64, (h // 2) * 2)
                
                if x < -10000 or y < -10000:
                    logger.warning(f"选区坐标异常 ({x},{y})，录制全屏")
                else:
                    input_kwargs["offset_x"] = x
                    input_kwargs["offset_y"] = y
                    input_kwargs["s"] = f"{w}x{h}"
                    mode_name = "窗口" if self.selected_region_type == "window" else "自定义区域"
                    logger.info(f"{mode_name}直接抓取: offset=({x},{y}), size={w}x{h}")
            else:
                # 全屏模式：不传任何参数，让 FFmpeg 自动检测
                logger.info("全屏录制模式：使用 FFmpeg 默认行为")

            video_stream = ffmpeg.input(input_name, **input_kwargs)
            # 不再需要 crop 滤镜！

            # 统一处理：确保输出尺寸为偶数（yuv420p / 多数编码器要求）
            video_stream = video_stream.filter("scale", "trunc(iw/2)*2", "trunc(ih/2)*2")
            streams.append(video_stream)
            
            # 音频输入 - 支持麦克风和系统音频
            audio_inputs = []
            
            if self.record_mic.value:
                mic_device = self.mic_device_dropdown.value
                if mic_device and mic_device != "none":
                    audio_inputs.append(f'audio={mic_device}')
            
            if self.record_system_audio.value:
                sys_device = self.system_audio_dropdown.value
                if sys_device and sys_device != "none":
                    audio_inputs.append(f'audio={sys_device}')
            
            # 如果有多个音频源，需要使用 amix 混音
            if len(audio_inputs) == 1:
                audio_stream = ffmpeg.input(audio_inputs[0], format='dshow')
                streams.append(audio_stream)
            elif len(audio_inputs) > 1:
                # 多个音频源混音
                audio_streams = [ffmpeg.input(dev, format='dshow') for dev in audio_inputs]
                streams.extend(audio_streams)
                
        elif platform == 'macos':
            # macOS: 组合音频设备 ID
            audio_device = "none"
            if self.record_mic.value:
                mic_device = self.mic_device_dropdown.value
                if mic_device and mic_device != "none":
                    audio_device = mic_device
            elif self.record_system_audio.value:
                sys_device = self.system_audio_dropdown.value
                if sys_device and sys_device != "none":
                    audio_device = sys_device
            
            video_stream = ffmpeg.input(
                f'1:{audio_device}',
                format='avfoundation',
                framerate=fps,
                capture_cursor=1,
            )
            
            # avfoundation 不支持直接指定区域，需要 crop 滤镜
            if self.selected_region and self.selected_region_type in ("window", "custom"):
                rx, ry, rw, rh = self.selected_region
                rw = max(64, (rw // 2) * 2)
                rh = max(64, (rh // 2) * 2)
                video_stream = video_stream.filter("crop", rw, rh, rx, ry)
                mode_name = "窗口" if self.selected_region_type == "window" else "自定义区域"
                logger.info(f"macOS {mode_name} crop: x={rx}, y={ry}, {rw}x{rh}")
            
            # 确保输出尺寸为偶数
            video_stream = video_stream.filter("scale", "trunc(iw/2)*2", "trunc(ih/2)*2")
            streams.append(video_stream)
                
        else:
            # Linux 使用 x11grab
            display = ':0.0'
            
            input_kwargs = {
                'format': 'x11grab',
                'framerate': fps,
            }
            
            if self.selected_region and self.selected_region_type == "custom":
                x, y, w, h = self.selected_region
                input_kwargs['video_size'] = f'{w}x{h}'
                input_name = f'{display}+{x},{y}'
            else:
                input_name = display
            
            video_stream = ffmpeg.input(input_name, **input_kwargs)
            streams.append(video_stream)
            
            # Linux 音频使用 pulse
            if self.record_mic.value:
                mic_device = self.mic_device_dropdown.value or "default"
                audio_stream = ffmpeg.input(mic_device, format='pulse')
                streams.append(audio_stream)
            elif self.record_system_audio.value:
                sys_device = self.system_audio_dropdown.value or "default"
                audio_stream = ffmpeg.input(sys_device, format='pulse')
                streams.append(audio_stream)
        
        # 输出参数
        output_kwargs = {
            'vcodec': encoder,
            'pix_fmt': 'yuv420p',
        }
        
        # 根据编码器类型设置参数
        if encoder.endswith("_nvenc"):
            # NVENC 编码器 - 与项目其他地方保持一致
            output_kwargs['preset'] = preset
            output_kwargs['cq'] = quality
        elif encoder.endswith("_amf"):
            output_kwargs['quality'] = preset
            output_kwargs['rc'] = 'cqp'
            output_kwargs['qp_i'] = quality
            output_kwargs['qp_p'] = quality
        elif encoder.endswith("_qsv"):
            output_kwargs['preset'] = preset
            output_kwargs['global_quality'] = quality
        elif encoder.endswith("_videotoolbox"):
            # Apple VideoToolbox - 质量范围 1-100（越大越好）
            output_kwargs['q:v'] = quality
        else:
            output_kwargs['preset'] = preset
            output_kwargs['crf'] = quality
        
        # 音频编码
        has_audio = self.record_mic.value or self.record_system_audio.value
        if has_audio and len(streams) > 1:
            output_kwargs['acodec'] = 'aac'
            output_kwargs['b:a'] = '192k'
            
            # 如果有多个音频流（麦克风+系统音频），需要混音
            if len(streams) > 2:
                # Windows 多音轨混音: 使用 filter_complex
                output_kwargs['filter_complex'] = f'[1:a][2:a]amix=inputs=2:duration=longest[aout]'
                output_kwargs['map'] = ['0:v', '[aout]']
        
        # 构建输出
        if len(streams) == 1:
            stream = ffmpeg.output(streams[0], str(self.output_file), **output_kwargs)
        else:
            stream = ffmpeg.output(*streams, str(self.output_file), **output_kwargs)
        
        return stream, self.output_file
    
    def _on_record_toggle(self, e) -> None:
        """切换录制状态（开始/停止）。"""
        if self.is_recording:
            self._stop_recording()
        else:
            # 每次开始录制前，先选择录制区域
            self._start_recording_with_region_select()
    
    def _start_recording_with_region_select(self) -> None:
        """先选择录制区域，然后开始录制。"""
        self.record_btn.disabled = True
        self._page.update()
        
        async def _select_and_record_async():
            from utils.screen_selector import select_screen_region
            result = await asyncio.to_thread(
                select_screen_region,
                hint_main="🎬 点击选择窗口  |  拖拽框选区域",
                hint_sub="按 F 录制当前屏幕  |  ESC 取消",
                return_window_title=True,
            )
            
            self.record_btn.disabled = False
            
            if result is None:
                # 用户取消
                self._show_message("已取消录制", ft.Colors.ORANGE)
                self._page.update()
                return
            
            # 更新选择结果
            if isinstance(result, tuple) and len(result) == 5:
                x, y, w, h, title = result
                self.selected_region = (x, y, w, h)
                self.selected_region_type = "window"
                self.selected_window_title = title
                display_title = title[:25] + "..." if len(title) > 25 else title
                self.region_info_text.value = f"🪟 {display_title}"
                self.region_detail_text.value = f"{w}×{h}"
            elif isinstance(result, tuple) and len(result) == 4:
                x, y, w, h = result
                self.selected_region = (x, y, w, h)
                self.selected_region_type = "custom"
                self.selected_window_title = None
                self.region_info_text.value = f"📐 自定义区域"
                self.region_detail_text.value = f"{w}×{h}"
            
            self._page.update()
            
            # 选择完成后，直接开始录制
            await self._on_start_recording(None)
        
        self._page.run_task(_select_and_record_async)

    async def _on_start_recording(self, e) -> None:
        """开始录制。"""
        try:
            # 再次检查 FFmpeg 可用性
            is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
            if not is_available:
                self._show_message("FFmpeg 不可用，请先安装", ft.Colors.RED)
                return
            
            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
            if not ffmpeg_path:
                self._show_message("未找到 FFmpeg 路径", ft.Colors.RED)
                return
            
            selected_encoder = self.encoder_dropdown.value

            result = self._build_ffmpeg_stream()
            if not result:
                self._show_message("无法构建 FFmpeg 命令", ft.Colors.RED)
                return
            
            stream, output_file = result
            
            # 获取完整命令用于日志
            cmd_args = ffmpeg.compile(stream, cmd=str(ffmpeg_path), overwrite_output=True)
            logger.info(f"开始录制，命令: {' '.join(cmd_args)}")
            
            # 使用 ffmpeg-python 启动异步进程
            self.recording_process = ffmpeg.run_async(
                stream,
                cmd=str(ffmpeg_path),
                pipe_stdin=True,
                pipe_stderr=True,
                overwrite_output=True,
            )
            
            # 启动线程监控 FFmpeg 输出（不更新UI，可保留为线程）
            self.stderr_output = []
            def read_stderr():
                try:
                    for line in iter(self.recording_process.stderr.readline, b''):
                        if line:
                            decoded = line.decode('utf-8', errors='replace').strip()
                            self.stderr_output.append(decoded)
                            if 'error' in decoded.lower() or 'failed' in decoded.lower():
                                logger.error(f"FFmpeg: {decoded}")
                except Exception:
                    pass
            
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # 等待一小段时间检查进程是否正常启动
            await asyncio.sleep(0.5)
            if self.recording_process.poll() is not None:
                # 进程已结束，说明启动失败
                error_output = '\n'.join(self.stderr_output[-5:]) if self.stderr_output else "未知错误"
                logger.error(f"FFmpeg 启动失败: {error_output}")
                self.recording_process = None

                # 硬件编码器常见：encoders 列表存在，但驱动/硬件不可用 -> 直接报错退出
                # 这里做一次自动回退到 CPU 编码（libx264），提升可用性
                if selected_encoder and (
                    selected_encoder.endswith("_nvenc")
                    or selected_encoder.endswith("_amf")
                    or selected_encoder.endswith("_qsv")
                ):
                    logger.warning(f"硬件编码器启动失败，自动回退到 libx264。原编码器: {selected_encoder}")

                    # 更新 UI 选择并同步预设选项
                    self.encoder_dropdown.value = "libx264"
                    try:
                        self._on_encoder_change(None)
                    except Exception:
                        pass

                    self._show_message("GPU 编码启动失败，已自动切换为 CPU 编码(libx264)，请重新开始录制", ft.Colors.ORANGE)
                    return

                self._show_message(f"FFmpeg 启动失败: {error_output[:100]}", ft.Colors.RED)
                return
            
            self.is_recording = True
            self.is_paused = False
            self.recording_start_time = time.time()
            self.pause_duration = 0.0
            self.should_stop_timer = False
            
            # 更新 UI
            self._update_ui_state()
            
            # 启动异步计时器
            self._page.run_task(self._timer_loop_async)
            
            self._show_message("录制已开始，点击停止按钮结束录制", ft.Colors.GREEN)
            
        except Exception as ex:
            logger.error(f"启动录制失败: {ex}", exc_info=True)
            self._show_message(f"启动录制失败: {ex}", ft.Colors.RED)
    
    def _on_pause_recording(self, e) -> None:
        """暂停/继续录制。"""
        # 注意：FFmpeg 的 gdigrab 不直接支持暂停
        # 这里通过向进程发送信号来模拟暂停（仅 Unix 系统支持）
        if self._get_platform() != 'windows':
            if self.recording_process:
                import signal
                if self.is_paused:
                    # 继续
                    self.recording_process.send_signal(signal.SIGCONT)
                    self.is_paused = False
                    self.pause_duration += time.time() - self.pause_start_time
                    self.pause_btn.text = "暂停"
                    self.pause_btn.icon = ft.Icons.PAUSE
                    self._show_message("录制已继续", ft.Colors.GREEN)
                else:
                    # 暂停
                    self.recording_process.send_signal(signal.SIGSTOP)
                    self.is_paused = True
                    self.pause_start_time = time.time()
                    self.pause_btn.text = "继续"
                    self.pause_btn.icon = ft.Icons.PLAY_ARROW
                    self._show_message("录制已暂停", ft.Colors.ORANGE)
                self._page.update()
        else:
            self._show_message("Windows 平台暂不支持暂停功能", ft.Colors.ORANGE)
    
    def _on_stop_recording(self, e) -> None:
        """停止录制。"""
        self._stop_recording()
    
    def _stop_recording(self) -> None:
        """停止录制进程。"""
        if self.recording_process:
            try:
                # 检查进程是否还在运行
                if self.recording_process.poll() is None:
                    # 方法1: 尝试发送 'q' 命令让 FFmpeg 正常退出
                    try:
                        if self.recording_process.stdin:
                            self.recording_process.stdin.write(b'q\n')
                            self.recording_process.stdin.flush()
                    except Exception as ex:
                        logger.debug(f"发送 q 命令失败: {ex}")
                    
                    # 等待进程结束
                    try:
                        self.recording_process.wait(timeout=3)
                        logger.info("FFmpeg 正常退出")
                    except subprocess.TimeoutExpired:
                        # 方法2: 如果 'q' 命令无效，使用 terminate
                        logger.info("发送 terminate 信号...")
                        self.recording_process.terminate()
                        try:
                            self.recording_process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            # 方法3: 最后使用 kill 强制终止
                            logger.info("发送 kill 信号...")
                            self.recording_process.kill()
                            self.recording_process.wait(timeout=2)
                else:
                    # 进程已经结束
                    exit_code = self.recording_process.returncode
                    logger.warning(f"FFmpeg 进程已结束，退出码: {exit_code}")
                    # 输出收集到的错误信息
                    if hasattr(self, 'stderr_output') and self.stderr_output:
                        logger.error(f"FFmpeg 输出: {self.stderr_output[-10:]}")
                
            except Exception as ex:
                logger.warning(f"停止录制时出错: {ex}")
                try:
                    self.recording_process.kill()
                except Exception:
                    pass
            finally:
                # 关闭所有管道
                try:
                    if self.recording_process.stdin:
                        self.recording_process.stdin.close()
                    if self.recording_process.stdout:
                        self.recording_process.stdout.close()
                    if self.recording_process.stderr:
                        self.recording_process.stderr.close()
                except Exception:
                    pass
                self.recording_process = None
        
        self.is_recording = False
        self.is_paused = False
        self.should_stop_timer = True
        
        # 更新 UI
        self._update_ui_state()
        
        if self.output_file and self.output_file.exists():
            file_size = self.output_file.stat().st_size
            size_mb = file_size / (1024 * 1024)
            self._show_message(f"录制完成！文件大小: {size_mb:.1f} MB", ft.Colors.GREEN)
            self.open_folder_btn.visible = True
            self._page.update()
        else:
            self._show_message("录制已停止", ft.Colors.ORANGE)
    
    async def _timer_loop_async(self) -> None:
        """异步计时器循环。"""
        while not self.should_stop_timer and self.is_recording:
            if not self.is_paused:
                elapsed = time.time() - self.recording_start_time - self.pause_duration
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                
                # 更新 UI（在事件循环中，可安全更新）
                self.timer_text.value = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                # 闪烁录制指示器
                if hasattr(self, 'recording_indicator'):
                    self.recording_indicator.content = ft.Icon(
                        ft.Icons.FIBER_MANUAL_RECORD,
                        color=ft.Colors.RED if int(elapsed) % 2 == 0 else ft.Colors.RED_200,
                        size=16,
                    )
                
                try:
                    self._page.update()
                except Exception:
                    break
            
            await asyncio.sleep(0.5)
    
    def _update_ui_state(self) -> None:
        """更新 UI 状态。"""
        # 获取按钮引用（Container 里的 ElevatedButton）
        btn = self.record_btn.content
        
        if self.is_recording:
            # 录制中：按钮变为"停止录制"
            btn.content = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.STOP_CIRCLE, size=24, color=ft.Colors.WHITE),
                    ),
                    ft.Text("停止录制", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=12,
                alignment=ft.MainAxisAlignment.CENTER,
            )
            btn.style = ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.GREY_700,
                    ft.ControlState.HOVERED: ft.Colors.GREY_800,
                },
                color=ft.Colors.WHITE,
                elevation={"default": 2, "hovered": 4},
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding.symmetric(horizontal=32, vertical=16),
            )
            self.status_text.value = "● 正在录制..."
            self.status_text.color = ft.Colors.RED
            self.recording_indicator.content = ft.Icon(
                ft.Icons.FIBER_MANUAL_RECORD, color=ft.Colors.RED, size=16
            )
            # 禁用设置
            self.fps_dropdown.disabled = True
            self.format_dropdown.disabled = True
            self.encoder_dropdown.disabled = True
            self.preset_dropdown.disabled = True
            self.quality_slider.disabled = True
            self.record_mic.disabled = True
            self.mic_device_dropdown.disabled = True
            self.record_system_audio.disabled = True
            self.system_audio_dropdown.disabled = True
        else:
            # 准备就绪：按钮变为"开始录制"
            btn.content = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, size=24, color=ft.Colors.WHITE),
                    ),
                    ft.Text("开始录制", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=12,
                alignment=ft.MainAxisAlignment.CENTER,
            )
            btn.style = ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.RED_600,
                    ft.ControlState.HOVERED: ft.Colors.RED_700,
                    ft.ControlState.PRESSED: ft.Colors.RED_800,
                },
                color=ft.Colors.WHITE,
                elevation={"default": 4, "hovered": 8},
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding.symmetric(horizontal=32, vertical=16),
            )
            self.status_text.value = "准备就绪"
            self.status_text.color = ft.Colors.ON_SURFACE_VARIANT
            self.recording_indicator.content = ft.Icon(
                ft.Icons.FIBER_MANUAL_RECORD, color=ft.Colors.GREY, size=16
            )
            # 启用设置
            self.fps_dropdown.disabled = False
            self.format_dropdown.disabled = False
            self.encoder_dropdown.disabled = False
            self.preset_dropdown.disabled = False
            self.quality_slider.disabled = False
            self.record_mic.disabled = False
            self.mic_device_dropdown.disabled = False
            self.record_system_audio.disabled = False
            self.system_audio_dropdown.disabled = False
        
        self._page.update()
    
    def _show_message(self, message: str, color: str = ft.Colors.PRIMARY) -> None:
        """显示消息提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=3000,
        )
        self._page.show_dialog(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        # 停止录制
        if self.is_recording:
            self._stop_recording()
        
        self.should_stop_timer = True
        
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        
        gc.collect()
        logger.info("屏幕录制视图资源已清理")
