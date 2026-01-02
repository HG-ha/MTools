# -*- coding: utf-8 -*-
"""Windows 文件拖放支持模块。

使用透明覆盖窗口实现 Flet/Flutter 窗口的文件拖放功能。

使用方法：
    from utils.windows_drop import WindowsDropHandler, DropInfo
    
    # 基本用法
    drop_handler = WindowsDropHandler(
        page=page,
        on_drop=lambda files: print(f"收到文件: {files}")
    )
    
    # 高级用法：获取鼠标位置
    def handle_drop(info: DropInfo):
        print(f"文件: {info.files}")
        print(f"鼠标位置: ({info.x}, {info.y})")  # 相对于窗口的坐标
    
    drop_handler = WindowsDropHandler(
        page=page,
        on_drop=handle_drop,
        include_position=True  # 启用位置信息
    )
"""

import sys
import time
import threading
from dataclasses import dataclass
from tkinter import W
from utils.logger import logger
from typing import Callable, List, Optional, Union


@dataclass
class DropInfo:
    """拖放信息，包含文件列表和鼠标位置。
    
    Attributes:
        files: 拖放的文件路径列表
        x: 鼠标 X 坐标（相对于窗口客户区）
        y: 鼠标 Y 坐标（相对于窗口客户区）
        screen_x: 鼠标 X 坐标（屏幕坐标）
        screen_y: 鼠标 Y 坐标（屏幕坐标）
    """
    files: List[str]
    x: int = 0
    y: int = 0
    screen_x: int = 0
    screen_y: int = 0

# 仅在 Windows 上支持
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes, c_void_p

    # Windows DLL
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
    ole32 = ctypes.windll.ole32

    # 64位/32位兼容
    if ctypes.sizeof(c_void_p) == 8:
        WPARAM = ctypes.c_ulonglong
        LPARAM = ctypes.c_longlong
        LRESULT = ctypes.c_longlong
    else:
        WPARAM = wintypes.WPARAM
        LPARAM = wintypes.LPARAM
        LRESULT = ctypes.c_long

    # Windows 常量
    WM_DROPFILES = 0x0233
    WM_DESTROY = 0x0002
    WM_NCHITTEST = 0x0084
    HTTRANSPARENT = -1

    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_TOPMOST = 0x00000008
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TRANSPARENT = 0x00000020

    SWP_NOACTIVATE = 0x0010
    LWA_ALPHA = 0x02
    GWL_EXSTYLE = -20
    VK_LBUTTON = 0x01
    HWND_TOPMOST = -1
    
    # 光标相关常量
    OCR_NORMAL = 32512  # 普通箭头光标
    OCR_NO = 32648      # 禁止光标

    # 设置函数签名
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.DefWindowProcW.restype = LRESULT

    shell32.DragQueryFileW.argtypes = [c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT

    shell32.DragFinish.argtypes = [c_void_p]
    shell32.DragFinish.restype = None

    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragAcceptFiles.restype = None

    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG

    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG

    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL

    user32.PtInRect.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.POINT]
    user32.PtInRect.restype = wintypes.BOOL
    
    user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ScreenToClient.restype = wintypes.BOOL
    
    user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.MoveWindow.restype = wintypes.BOOL
    
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    
    # SetWindowPos 标志
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    
    # ShowWindow 常量
    SW_HIDE = 0
    SW_SHOW = 5
    
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    
    # 光标检测相关
    user32.GetCursor.argtypes = []
    user32.GetCursor.restype = wintypes.HANDLE  # HCURSOR 实际上是 HANDLE
    
    # LoadCursorW 的第二个参数可以是字符串或整数资源ID (MAKEINTRESOURCE)
    # 使用 c_void_p 可以同时接受两种类型
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, c_void_p]
    user32.LoadCursorW.restype = wintypes.HANDLE  # HCURSOR 实际上是 HANDLE
    
    # CURSORINFO 结构体
    class CURSORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hCursor", wintypes.HANDLE),  # HCURSOR
            ("ptScreenPos", wintypes.POINT),
        ]
    
    user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
    user32.GetCursorInfo.restype = wintypes.BOOL

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT), ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON), ("hCursor", wintypes.HICON),
            ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON),
        ]


class WindowsDropHandler:
    """Windows 文件拖放处理器。
    
    为 Flet 应用提供原生文件拖放支持。
    
    Attributes:
        page: Flet 页面对象
        on_drop: 文件拖放回调函数
        enabled: 是否已启用
        include_position: 是否包含鼠标位置信息
    
    Example:
        ```python
        # 基本用法
        def handle_drop(files: List[str]):
            for file in files:
                print(f"拖入文件: {file}")
        
        handler = WindowsDropHandler(page, on_drop=handle_drop)
        
        # 高级用法：获取鼠标位置
        def handle_drop_with_pos(info: DropInfo):
            print(f"位置: ({info.x}, {info.y})")
            for file in info.files:
                print(f"拖入文件: {file}")
        
        handler = WindowsDropHandler(
            page, 
            on_drop=handle_drop_with_pos,
            include_position=True
        )
        ```
    """
    
    # 类级别的全局引用，防止垃圾回收
    _wndproc_ref = None
    _drop_callback = None
    _stop_event = None
    _class_registered = False
    _instance_counter = 0
    _include_position = False
    _parent_hwnd_global = None
    
    CLASS_NAME_BASE = "FletDropOverlay"
    
    def __init__(
        self,
        page,
        on_drop: Union[Callable[[List[str]], None], Callable[[DropInfo], None]],
        auto_enable: bool = True,
        enable_delay: float = 1.5,
        include_position: bool = False
    ):
        """初始化拖放处理器。
        
        Args:
            page: Flet 页面对象
            on_drop: 文件拖放回调函数。
                     如果 include_position=False，接收 List[str]
                     如果 include_position=True，接收 DropInfo
            auto_enable: 是否自动启用（默认 True）
            enable_delay: 自动启用的延迟秒数（默认 1.5 秒）
            include_position: 是否在回调中包含鼠标位置信息（默认 False）
        """
        self.page = page
        self.on_drop = on_drop
        self.enabled = False
        self._overlay_hwnd = None
        self._parent_hwnd = None
        self._enable_delay = enable_delay
        self._include_position = include_position
        
        # 生成唯一的类名
        WindowsDropHandler._instance_counter += 1
        self._class_name = f"{self.CLASS_NAME_BASE}_{WindowsDropHandler._instance_counter}"
        
        if auto_enable and sys.platform == "win32":
            threading.Thread(target=self._auto_enable, daemon=True).start()
    
    def _auto_enable(self):
        """自动启用（延迟执行，带重试）"""
        time.sleep(self._enable_delay)
        
        # 尝试多次，因为窗口可能还在初始化
        # max_retries = 50
        # for i in range(max_retries):
        #     if self.enable():
        #         return
        #     logger.debug(f"WindowsDropHandler 重试 {i + 1}/{max_retries}...")
        #     time.sleep(0.1)
        # 重试直到成功
        while not self.enable():
            time.sleep(0.1)
            # logger.debug("WindowsDropHandler 重试...")
        logger.debug("WindowsDropHandler 启用成功")
    
    def enable(self) -> bool:
        """启用拖放支持。
        
        Returns:
            是否成功启用
        """
        if sys.platform != "win32":
            return False
        
        if self.enabled:
            return True
        
        # 查找 Flet 窗口
        hwnd = user32.FindWindowW(None, self.page.title)
        if not hwnd:
            return False
        
        self._parent_hwnd = hwnd
        
        # 创建覆盖窗口
        WindowsDropHandler._stop_event = threading.Event()
        WindowsDropHandler._drop_callback = self.on_drop
        WindowsDropHandler._include_position = self._include_position
        WindowsDropHandler._parent_hwnd_global = hwnd
        
        thread = threading.Thread(target=self._run_overlay_window, daemon=True)
        thread.start()
        
        time.sleep(0.5)
        self.enabled = self._overlay_hwnd is not None
        
        if self.enabled:
            logger.debug(f"WindowsDropHandler 拖放已启用，覆盖窗口 HWND={self._overlay_hwnd}")
        else:
            logger.warning("WindowsDropHandler 创建覆盖窗口失败")
        
        return self.enabled
    
    def disable(self):
        """禁用拖放支持。"""
        if WindowsDropHandler._stop_event:
            WindowsDropHandler._stop_event.set()
        if self._overlay_hwnd:
            user32.DestroyWindow(self._overlay_hwnd)
            self._overlay_hwnd = None
        self.enabled = False
    
    def _run_overlay_window(self):
        """运行覆盖窗口（在独立线程中）"""
        hInstance = kernel32.GetModuleHandleW(None)
        
        # 窗口过程
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                try:
                    files = self._extract_files(wparam)
                    if files and WindowsDropHandler._drop_callback:
                        if WindowsDropHandler._include_position:
                            # 获取鼠标位置
                            pt = wintypes.POINT()
                            user32.GetCursorPos(ctypes.byref(pt))
                            screen_x, screen_y = pt.x, pt.y
                            
                            # 转换为窗口客户区坐标
                            if WindowsDropHandler._parent_hwnd_global:
                                user32.ScreenToClient(
                                    WindowsDropHandler._parent_hwnd_global,
                                    ctypes.byref(pt)
                                )
                            
                            info = DropInfo(
                                files=files,
                                x=pt.x,
                                y=pt.y,
                                screen_x=screen_x,
                                screen_y=screen_y
                            )
                            threading.Thread(
                                target=WindowsDropHandler._drop_callback,
                                args=(info,),
                                daemon=True
                            ).start()
                        else:
                            # 简单模式，只传文件列表
                            threading.Thread(
                                target=WindowsDropHandler._drop_callback,
                                args=(files,),
                                daemon=True
                            ).start()
                except Exception:
                    pass
                return 0
            elif msg == WM_NCHITTEST:
                return HTTRANSPARENT
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        
        WindowsDropHandler._wndproc_ref = WNDPROC(wnd_proc)
        
        # 注册窗口类
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = WindowsDropHandler._wndproc_ref
        wc.hInstance = hInstance
        wc.hCursor = user32.LoadCursorW(None, 32512)
        wc.lpszClassName = self._class_name
        
        user32.RegisterClassExW(ctypes.byref(wc))
        
        # 获取父窗口位置
        rect = wintypes.RECT()
        user32.GetWindowRect(self._parent_hwnd, ctypes.byref(rect))
        
        # 创建覆盖窗口
        ex_style = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
        
        self._overlay_hwnd = user32.CreateWindowExW(
            ex_style, self._class_name, "DropOverlay", WS_POPUP | WS_VISIBLE,
            rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
            None, None, hInstance, None
        )
        
        if self._overlay_hwnd:
            user32.SetLayeredWindowAttributes(self._overlay_hwnd, 0, 1, LWA_ALPHA)
            shell32.DragAcceptFiles(self._overlay_hwnd, True)
            self._start_position_tracker()
            self._start_drag_detector()
        
        # 消息循环
        msg = wintypes.MSG()
        while not WindowsDropHandler._stop_event.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)
    
    def _start_position_tracker(self):
        """跟踪父窗口位置和大小，并根据父窗口可见性显示/隐藏覆盖窗口"""
        def track():
            last_rect = None
            last_visible = True
            while not WindowsDropHandler._stop_event.is_set():
                time.sleep(0.016)  # ~60 FPS，更快响应窗口大小变化
                if not user32.IsWindow(self._parent_hwnd):
                    break
                if not user32.IsWindow(self._overlay_hwnd):
                    break
                
                # 检测父窗口是否可见（包括最小化和隐藏到托盘的情况）
                is_visible = user32.IsWindowVisible(self._parent_hwnd)
                is_minimized = user32.IsIconic(self._parent_hwnd)
                should_show = is_visible and not is_minimized
                
                # 可见性变化时，显示或隐藏覆盖窗口
                if should_show != last_visible:
                    if should_show:
                        user32.ShowWindow(self._overlay_hwnd, SW_SHOW)
                    else:
                        user32.ShowWindow(self._overlay_hwnd, SW_HIDE)
                    last_visible = should_show
                
                # 如果不可见，跳过位置更新
                if not should_show:
                    continue
                
                rect = wintypes.RECT()
                user32.GetWindowRect(self._parent_hwnd, ctypes.byref(rect))
                # 仅在位置或大小变化时更新，减少不必要的调用
                current = (rect.left, rect.top, rect.right, rect.bottom)
                if current != last_rect:
                    # 使用 MoveWindow 调整窗口大小
                    user32.MoveWindow(
                        self._overlay_hwnd,
                        rect.left, rect.top,
                        rect.right - rect.left, rect.bottom - rect.top,
                        False  # 不重绘（透明窗口不需要）
                    )
                    # 确保保持在最顶层
                    user32.SetWindowPos(
                        self._overlay_hwnd, HWND_TOPMOST,
                        0, 0, 0, 0,
                        SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE
                    )
                    # 重新启用拖放接受（确保新区域也能接收拖放）
                    shell32.DragAcceptFiles(self._overlay_hwnd, True)
                    last_rect = current
        threading.Thread(target=track, daemon=True).start()
    
    def _is_occluded_by_foreground(self) -> bool:
        """检测我们的窗口是否被前台窗口遮挡
        
        通过检查前台窗口是否是我们的应用来判断。
        如果前台窗口不是我们的应用，说明用户正在操作其他软件，
        此时应该隐藏覆盖窗口避免干扰。
        
        Returns:
            True 如果被其他窗口遮挡（前台窗口不是我们的应用）
        """
        foreground_hwnd = user32.GetForegroundWindow()
        
        if not foreground_hwnd:
            return False
        
        # 如果前台窗口就是我们的父窗口，没有遮挡
        if foreground_hwnd == self._parent_hwnd:
            return False
        
        # 获取前台窗口的根窗口
        foreground_root = user32.GetAncestor(foreground_hwnd, 2)  # GA_ROOT = 2
        
        # 如果前台窗口的根窗口是我们的父窗口，没有遮挡
        if foreground_root == self._parent_hwnd:
            return False
        
        # 前台窗口不是我们的应用，认为被遮挡
        return True
    
    def _is_drag_drop_cursor(self) -> bool:
        """检测当前光标是否是拖放相关的光标
        
        当进行文件拖放时，光标会变成特殊的拖放光标（带有文件图标或禁止符号）。
        普通的窗口拖动使用的是标准箭头光标。
        
        Returns:
            True 如果当前光标是拖放光标
        """
        try:
            # 获取当前光标
            current_cursor = user32.GetCursor()
            if not current_cursor:
                return False
            
            # 获取标准光标
            arrow_cursor = user32.LoadCursorW(None, OCR_NORMAL)
            
            # 如果当前光标不是标准箭头光标，可能是拖放光标
            # 拖放时光标通常会变成：
            # - 带有文件图标的光标
            # - 禁止符号光标（当目标不接受拖放时）
            # - 复制/移动光标
            if current_cursor != arrow_cursor:
                return True
            
            return False
        except Exception:
            return False
    
    def _start_drag_detector(self):
        """检测拖放操作，动态切换透明状态和覆盖窗口可见性
        
        改进策略：
        1. 当前台窗口是其他应用且不是拖放操作时，隐藏覆盖窗口避免干扰
        2. 通过检测光标类型来区分文件拖放和窗口拖动
        3. 当检测到拖放光标时，显示覆盖窗口并变为不透明以接收拖放
        4. 增加按下持续时间检测，避免快速双击被误判为拖放
        """
        def detect():
            is_transparent = True
            is_overlay_hidden = False  # 覆盖窗口是否被隐藏
            restore_delay = 0
            lbutton_down_duration = 0  # 鼠标左键按下持续时间计数
            DRAG_THRESHOLD = 8  # 约 128ms (8 * 16ms)，需要按住这么久才认为是拖放
            
            while not WindowsDropHandler._stop_event.is_set():
                time.sleep(0.016)
                
                if not user32.IsWindow(self._overlay_hwnd):
                    break
                
                # 检查父窗口是否可见
                if not user32.IsWindowVisible(self._parent_hwnd) or user32.IsIconic(self._parent_hwnd):
                    # 父窗口不可见时，由 position_tracker 处理隐藏
                    lbutton_down_duration = 0
                    continue
                
                # 检查鼠标左键状态
                lbutton_down = (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0
                
                # 更新按下持续时间
                if lbutton_down:
                    lbutton_down_duration += 1
                else:
                    lbutton_down_duration = 0
                
                # 获取鼠标位置
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                
                # 获取窗口区域
                rect = wintypes.RECT()
                user32.GetWindowRect(self._parent_hwnd, ctypes.byref(rect))
                
                # 检测鼠标是否在窗口内部
                in_window = user32.PtInRect(ctypes.byref(rect), pt)
                
                # 检测是否被前台窗口遮挡（前台窗口不是我们的应用）
                is_other_app_foreground = self._is_occluded_by_foreground()
                
                # 检测是否是拖放光标（关键：区分文件拖放和窗口拖动）
                is_drag_cursor = self._is_drag_drop_cursor()
                
                # 判断是否是有效的文件拖放操作
                # 条件：左键按下 + 按下持续时间超过阈值 + 在窗口内 + 是拖放光标
                # 增加持续时间检测，避免快速双击被误判为拖放操作
                is_valid_drag = (
                    lbutton_down and 
                    lbutton_down_duration >= DRAG_THRESHOLD and  # 必须按住足够长时间
                    in_window and
                    is_drag_cursor  # 必须是拖放光标
                )
                
                # 决定覆盖窗口的可见性
                # 当前台窗口是其他应用，且鼠标在窗口内，且不是拖放操作时，隐藏覆盖窗口
                # 这样可以让用户正常操作覆盖在上面的其他窗口
                should_hide_overlay = is_other_app_foreground and in_window and not is_valid_drag
                
                if should_hide_overlay and not is_overlay_hidden:
                    # 隐藏覆盖窗口，让用户可以正常操作上层窗口
                    user32.ShowWindow(self._overlay_hwnd, SW_HIDE)
                    is_overlay_hidden = True
                elif not should_hide_overlay and is_overlay_hidden:
                    # 恢复显示覆盖窗口
                    user32.ShowWindow(self._overlay_hwnd, SW_SHOW)
                    # 重新确保在最顶层
                    user32.SetWindowPos(
                        self._overlay_hwnd, HWND_TOPMOST,
                        0, 0, 0, 0,
                        SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE
                    )
                    is_overlay_hidden = False
                
                # 决定透明状态（只有在覆盖窗口可见时才有意义）
                if not is_overlay_hidden:
                    if is_valid_drag and is_transparent:
                        # 有效拖放，变为不透明以接收拖放
                        style = user32.GetWindowLongW(self._overlay_hwnd, GWL_EXSTYLE)
                        user32.SetWindowLongW(self._overlay_hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
                        is_transparent = False
                        restore_delay = 0
                    
                    elif is_valid_drag and not is_transparent:
                        restore_delay = 0
                    
                    elif not is_valid_drag and not is_transparent:
                        restore_delay += 1
                        if restore_delay > 6:  # 约 100ms
                            style = user32.GetWindowLongW(self._overlay_hwnd, GWL_EXSTYLE)
                            user32.SetWindowLongW(self._overlay_hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT)
                            is_transparent = True
                            restore_delay = 0
        
        threading.Thread(target=detect, daemon=True).start()
    
    def _extract_files(self, hdrop) -> List[str]:
        """从 HDROP 句柄提取文件列表"""
        files = []
        hdrop_ptr = ctypes.c_void_p(hdrop)
        file_count = shell32.DragQueryFileW(hdrop_ptr, 0xFFFFFFFF, None, 0)
        for i in range(file_count):
            length = shell32.DragQueryFileW(hdrop_ptr, i, None, 0)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                shell32.DragQueryFileW(hdrop_ptr, i, buffer, length + 1)
                files.append(buffer.value)
        shell32.DragFinish(hdrop_ptr)
        return files

