# -*- coding: utf-8 -*-
"""macOS 文件拖放支持模块。

使用透明覆盖窗口（NSPanel）实现 Flet/Flutter 窗口的文件拖放功能。
覆盖窗口默认处于 ignoresMouseEvents=YES 状态（完全穿透，不影响任何软件），
当检测到文件拖拽进入窗口区域时，临时切换为接受事件以捕获拖放。

架构说明：
- NSPanel 必须在主线程创建（macOS 强制要求）
- ft.run() 占据主线程运行 asyncio 事件循环
- 通过 page.run_task() 将 NSPanel 创建调度到主线程的 asyncio 循环
- 周期性泵送 NSApplication 事件队列以接收拖放事件

使用方法：
    from utils.macos_drop import MacOSDropHandler
    handler = MacOSDropHandler(page=page, on_drop=callback, include_position=True)
"""

import sys
import threading
from dataclasses import dataclass
from utils.logger import logger
from typing import Callable, List, Optional, Union


@dataclass
class DropInfo:
    """拖放信息，包含文件列表和鼠标位置。"""

    files: List[str]
    x: int = 0
    y: int = 0
    screen_x: int = 0
    screen_y: int = 0


# 检查 PyObjC 可用性
_PYOBJC_AVAILABLE = False

if sys.platform == "darwin":
    try:
        import objc  # type: ignore[import-untyped]
        from AppKit import (  # type: ignore[import-untyped]
            NSApplication,
            NSBackingStoreBuffered,
            NSColor,
            NSDefaultRunLoopMode,
            NSDragOperationCopy,
            NSDragOperationNone,
            NSEvent,
            NSEventMaskLeftMouseDragged,
            NSEventMaskLeftMouseUp,
            NSFloatingWindowLevel,
            NSPanel,
            NSPasteboardTypeFileURL,
            NSScreen,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )
        from Foundation import (  # type: ignore[import-untyped]
            NSDate,
            NSPoint,
            NSRect,
            NSRunLoop,
            NSSize,
            NSURL,
        )

        _PYOBJC_AVAILABLE = True
    except ImportError:
        logger.warning("PyObjC 未安装，macOS 拖放功能不可用")


class MacOSDropHandler:
    """macOS 文件拖放处理器。

    通过 page.run_task() 在主线程创建 NSPanel 覆盖窗口，
    并周期性泵送 NSApplication 事件队列以处理拖放事件。
    """

    _active_callback: Optional[Callable] = None
    _include_position: bool = False
    _panel: Optional[object] = None
    _methods_injected: bool = False

    def __init__(
        self,
        page,
        on_drop: Union[Callable[[List[str]], None], Callable[[DropInfo], None]],
        auto_enable: bool = True,
        enable_delay: float = 2.0,
        include_position: bool = False,
    ):
        self._page = page
        self.on_drop = on_drop
        self.enabled = False
        self.include_position = include_position
        self._enable_delay = enable_delay
        self._stop_event = threading.Event()

        MacOSDropHandler._active_callback = on_drop
        MacOSDropHandler._include_position = include_position

        if not _PYOBJC_AVAILABLE:
            logger.warning("MacOSDropHandler: PyObjC 不可用")
            return

        if auto_enable:
            self._page.run_task(self._async_init)

    async def _async_init(self):
        """在主线程（asyncio 事件循环）上初始化拖放覆盖窗口。"""
        import asyncio

        # 等待窗口完全初始化
        await asyncio.sleep(self._enable_delay)

        # 等待 Flet 窗口尺寸就绪
        for _ in range(30):
            try:
                w = self._page.window.width
                h = self._page.window.height
                if w and h and w > 0 and h > 0:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)

        try:
            # 初始化 NSApplication（设为 Accessory 避免 Dock 图标）
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory

            # 创建 NSPanel（此刻在主线程，满足 macOS 要求）
            self._create_overlay()

            if not MacOSDropHandler._panel:
                logger.warning("MacOSDropHandler: 覆盖窗口创建失败")
                return

            logger.info("MacOSDropHandler: 覆盖窗口已创建（主线程）")

            # 设置事件监听（全局鼠标拖拽 / 鼠标抬起）
            self._setup_event_monitors()

            # 启动事件泵送 + 位置追踪循环
            asyncio.get_event_loop().create_task(self._pump_events())

            self.enabled = True
            logger.info("MacOSDropHandler: 拖放功能已启用")

        except Exception as e:
            logger.error(f"MacOSDropHandler: 初始化失败 - {e}")

    async def _pump_events(self):
        """周期性泵送 NSApplication 事件队列并同步覆盖窗口位置。

        在主线程 asyncio 循环中运行，每 ~20ms 处理一次：
        1. 处理所有待处理的 macOS 应用事件（包括拖放）
        2. 泵送 NSRunLoop（处理事件监听器回调）
        3. 同步覆盖窗口位置到 Flet 窗口
        """
        import asyncio

        app = NSApplication.sharedApplication()
        last_frame = None

        while not self._stop_event.is_set():
            try:
                # 1. 处理所有待处理的 macOS 事件
                while True:
                    event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                        0xFFFFFFFF,  # NSEventMaskAny
                        NSDate.distantPast(),  # 不等待，立即返回
                        NSDefaultRunLoopMode,
                        True,
                    )
                    if not event:
                        break
                    app.sendEvent_(event)

                # 2. 泵送 NSRunLoop（处理事件监听器等）
                NSRunLoop.mainRunLoop().runMode_beforeDate_(
                    NSDefaultRunLoopMode, NSDate.distantPast()
                )

                # 3. 同步覆盖窗口位置
                panel = MacOSDropHandler._panel
                if panel:
                    frame_data = self._get_window_frame()
                    if frame_data and frame_data != last_frame:
                        x, y, w, h = frame_data
                        panel.setFrame_display_(
                            NSRect(NSPoint(x, y), NSSize(w, h)), False
                        )
                        last_frame = frame_data

            except Exception as e:
                logger.debug(f"MacOSDropHandler: 事件泵送异常 - {e}")

            await asyncio.sleep(0.02)  # ~50Hz

    def _get_window_frame(self) -> Optional[tuple]:
        """获取 Flet 窗口在 macOS 坐标系中的位置和尺寸。"""
        try:
            flet_x = self._page.window.left or 0
            flet_y = self._page.window.top or 0
            flet_w = self._page.window.width or 800
            flet_h = self._page.window.height or 600

            screen = NSScreen.mainScreen()
            screen_h = screen.frame().size.height
            ns_y = screen_h - flet_y - flet_h

            return (flet_x, ns_y, flet_w, flet_h)
        except Exception:
            return None

    def _create_overlay(self):
        """创建透明覆盖 NSPanel（必须在主线程调用）。"""
        frame_data = self._get_window_frame()
        if not frame_data:
            frame_data = (100, 100, 800, 600)

        x, y, w, h = frame_data
        frame = NSRect(NSPoint(x, y), NSSize(w, h))

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setAlphaValue_(0.01)
        panel.setHasShadow_(False)
        panel.setIgnoresMouseEvents_(True)
        panel.setCollectionBehavior_(1 << 4)  # Transient
        panel.setReleasedWhenClosed_(False)

        # 注册拖放类型
        content_view = panel.contentView()
        content_view.registerForDraggedTypes_([NSPasteboardTypeFileURL])

        # 注入拖放方法
        if not MacOSDropHandler._methods_injected:
            self._inject_drag_methods(content_view)
            MacOSDropHandler._methods_injected = True

        panel.orderFront_(None)
        MacOSDropHandler._panel = panel

    def _inject_drag_methods(self, view):
        """向 NSView 注入 NSDraggingDestination 协议方法。"""
        view_class = type(view)

        def _dragging_entered(self, sender):
            logger.debug("MacOSDropHandler: draggingEntered")
            return NSDragOperationCopy

        def _dragging_updated(self, sender):
            return NSDragOperationCopy

        def _dragging_exited(self, sender):
            logger.debug("MacOSDropHandler: draggingExited")
            panel = MacOSDropHandler._panel
            if panel:
                panel.setIgnoresMouseEvents_(True)
                panel.setAlphaValue_(0.01)

        def _perform_drag_operation(self, sender):
            try:
                pb = sender.draggingPasteboard()
                items = pb.pasteboardItems()
                if not items:
                    return False

                files = []
                for item in items:
                    url_str = item.stringForType_(NSPasteboardTypeFileURL)
                    if url_str:
                        url = NSURL.URLWithString_(url_str)
                        if url and url.path():
                            files.append(str(url.path()))

                if not files:
                    return False

                logger.info(f"MacOSDropHandler: 收到 {len(files)} 个文件")

                callback = MacOSDropHandler._active_callback
                if not callback:
                    return False

                if MacOSDropHandler._include_position:
                    drop_point = sender.draggingLocation()
                    window = sender.draggingDestinationWindow()
                    x, y, screen_x, screen_y = 0, 0, 0, 0

                    if window:
                        cv = window.contentView()
                        if cv:
                            fr = cv.frame()
                            x = int(drop_point.x)
                            y = int(fr.size.height - drop_point.y)

                        screen_point = window.convertPointToScreen_(
                            drop_point
                        )
                        screen_x = int(screen_point.x)
                        screen_obj = window.screen()
                        if screen_obj:
                            sf = screen_obj.frame()
                            screen_y = int(sf.size.height - screen_point.y)

                    info = DropInfo(
                        files=files,
                        x=x, y=y,
                        screen_x=screen_x, screen_y=screen_y,
                    )
                    threading.Thread(
                        target=callback, args=(info,), daemon=True
                    ).start()
                else:
                    threading.Thread(
                        target=callback, args=(files,), daemon=True
                    ).start()

                return True

            except Exception as e:
                logger.error(f"MacOSDropHandler: 处理拖放失败 - {e}")
                return False
            finally:
                panel = MacOSDropHandler._panel
                if panel:
                    panel.setIgnoresMouseEvents_(True)
                    panel.setAlphaValue_(0.01)

        methods = [
            (b"draggingEntered:", _dragging_entered, b"Q@:@"),
            (b"draggingUpdated:", _dragging_updated, b"Q@:@"),
            (b"draggingExited:", _dragging_exited, b"v@:@"),
            (b"performDragOperation:", _perform_drag_operation, b"B@:@"),
        ]

        for sel_name, func, signature in methods:
            try:
                if not view.respondsToSelector_(sel_name):
                    sel = objc.selector(
                        func, selector=sel_name, signature=signature
                    )
                    objc.classAddMethod(view_class, sel_name, sel)
            except Exception as e:
                logger.warning(
                    f"MacOSDropHandler: 注入 {sel_name.decode()} 失败: {e}"
                )

    def _setup_event_monitors(self):
        """设置全局事件监听：检测到拖拽时立即激活覆盖窗口，鼠标抬起时恢复穿透。

        关键：必须在拖拽游标到达窗口区域 **之前** 就设置 ignoresMouseEvents=False，
        否则 macOS 拖放系统会跳过该窗口（它在游标进入窗口帧时就已决定是否接受拖放）。
        因此，只要检测到屏幕上任何位置的拖拽就立即激活，而非等到进入区域。
        """
        panel = MacOSDropHandler._panel
        if not panel:
            return

        def on_drag(event):
            p = panel
            if not p:
                return
            # 检测到任何拖拽就立即激活覆盖窗口，确保在游标到达前就准备好
            if p.ignoresMouseEvents():
                p.setIgnoresMouseEvents_(False)
                p.setAlphaValue_(0.05)
                logger.debug("MacOSDropHandler: 检测到拖拽，激活覆盖窗口")

        def on_mouseup(event):
            p = panel
            if p and not p.ignoresMouseEvents():
                p.setIgnoresMouseEvents_(True)
                p.setAlphaValue_(0.01)
                logger.debug("MacOSDropHandler: 拖拽结束，恢复穿透")

        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskLeftMouseDragged, on_drag
        )
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskLeftMouseUp, on_mouseup
        )

    def disable(self):
        """禁用拖放功能并清理资源。"""
        self._stop_event.set()
        MacOSDropHandler._active_callback = None
        panel = MacOSDropHandler._panel
        if panel:
            panel.orderOut_(None)
            MacOSDropHandler._panel = None
        self.enabled = False
