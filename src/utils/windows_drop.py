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
    
    # SetWindowPos 标志
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001

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
        max_retries = 50
        for i in range(max_retries):
            if self.enable():
                return
            logger.debug(f"WindowsDropHandler 重试 {i + 1}/{max_retries}...")
            time.sleep(0.5)
    
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
        """跟踪父窗口位置和大小"""
        def track():
            last_rect = None
            while not WindowsDropHandler._stop_event.is_set():
                time.sleep(0.016)  # ~60 FPS，更快响应窗口大小变化
                if not user32.IsWindow(self._parent_hwnd):
                    break
                if not user32.IsWindow(self._overlay_hwnd):
                    break
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
    
    def _start_drag_detector(self):
        """检测拖放操作，动态切换透明状态
        
        简化策略：左键按下且鼠标在扩展区域内时变为不透明
        标题栏保护：检测鼠标是否在标题栏区域，如果是则不改变透明状态
        """
        def detect():
            is_transparent = True
            restore_delay = 0
            
            while not WindowsDropHandler._stop_event.is_set():
                time.sleep(0.016)
                
                if not user32.IsWindow(self._overlay_hwnd):
                    break
                
                # 检查鼠标左键状态
                lbutton_down = (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0
                
                # 获取鼠标位置和窗口区域
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                
                rect = wintypes.RECT()
                user32.GetWindowRect(self._overlay_hwnd, ctypes.byref(rect))
                
                # 扩展区域（窗口外围）
                expanded_rect = wintypes.RECT()
                expanded_rect.left = rect.left - 50
                expanded_rect.top = rect.top - 50
                expanded_rect.right = rect.right + 50
                expanded_rect.bottom = rect.bottom + 50
                
                in_expanded = user32.PtInRect(ctypes.byref(expanded_rect), pt)
                
                # 左键按下且在扩展区域内时变为不透明
                should_be_opaque = lbutton_down and in_expanded
                
                if should_be_opaque and is_transparent:
                    style = user32.GetWindowLongW(self._overlay_hwnd, GWL_EXSTYLE)
                    user32.SetWindowLongW(self._overlay_hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
                    is_transparent = False
                    restore_delay = 0
                
                elif should_be_opaque and not is_transparent:
                    restore_delay = 0
                
                elif not should_be_opaque and not is_transparent:
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

