# -*- coding: utf-8 -*-
"""全局热键服务模块。

在应用启动时注册全局热键，支持 OCR 截图识别和屏幕录制功能。
"""

import gc
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from utils import logger

# 跨平台图像处理模块
try:
    from PIL import Image, ImageGrab
except ImportError:
    Image = None
    ImageGrab = None
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

# Windows 专用模块（条件导入）
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes, POINTER
else:
    ctypes = None
    wintypes = None
    POINTER = None


class GlobalHotkeyService:
    """全局热键服务类。
    
    管理应用级别的全局热键注册和响应。
    """
    
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
    
    # 热键 ID
    HOTKEY_OCR = 1001
    HOTKEY_SCREEN_RECORD = 1002
    
    def __init__(self, config_service, page=None):
        """初始化全局热键服务。
        
        Args:
            config_service: 配置服务实例
            page: Flet 页面对象（用于 UI 回调）
        """
        self.config_service = config_service
        self._page = page
        
        self._hotkey_thread: Optional[threading.Thread] = None
        self._hotkey_stop_event: Optional[threading.Event] = None
        self._hotkey_thread_id: Optional[int] = None
        
        # 回调函数
        self._callbacks: Dict[int, Callable] = {}
        
        # OCR 服务（延迟初始化）
        self._ocr_service = None
        self._ocr_unload_timer: Optional[threading.Timer] = None
        self._ocr_unload_delay = 300  # 5 分钟后自动卸载模型
        
        # OCR 区域选择锁，防止同时运行多个
        self._ocr_selecting = False
    
    def set_page(self, page) -> None:
        """设置页面对象。"""
        self._page = page
    
    def set_callback(self, hotkey_id: int, callback: Callable) -> None:
        """设置热键回调函数。"""
        self._callbacks[hotkey_id] = callback
    
    def _preload_ocr(self) -> None:
        """预加载 OCR 模型。"""
        def load():
            try:
                from services import OCRService
                from constants import DEFAULT_OCR_MODEL_KEY
                
                if self._ocr_service is not None:
                    return  # 已加载
                
                ocr_service = OCRService(self.config_service)
                model_key = self.config_service.get_config_value("ocr_model_key", DEFAULT_OCR_MODEL_KEY)
                use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
                
                success, message = ocr_service.load_model(
                    model_key,
                    use_gpu=use_gpu,
                    progress_callback=lambda p, m: None
                )
                
                if success:
                    self._ocr_service = ocr_service
                    logger.info("OCR 模型已预加载")
                else:
                    logger.warning(f"OCR 模型预加载失败: {message}")
            except Exception as ex:
                logger.error(f"预加载 OCR 模型失败: {ex}")
        
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
    
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
    
    # ── macOS 辅助功能权限检查 ──────────────────────────────────
    @staticmethod
    def _check_accessibility_permission() -> bool:
        """检查并请求 macOS 辅助功能权限（pynput 全局热键必需）。
        
        使用 ctypes 调用 AXIsProcessTrusted()，避免依赖 pyobjc-framework-ApplicationServices。
        未授权时通过 subprocess 打开系统设置引导用户授权。
        
        Returns:
            True 表示已获得权限，False 表示未授权
        """
        import ctypes
        import ctypes.util

        try:
            lib_path = ctypes.util.find_library('ApplicationServices')
            if not lib_path:
                logger.warning("未找到 ApplicationServices framework")
                return False
            lib = ctypes.cdll.LoadLibrary(lib_path)
            lib.AXIsProcessTrusted.restype = ctypes.c_bool
            lib.AXIsProcessTrusted.argtypes = []
            return bool(lib.AXIsProcessTrusted())
        except Exception as ex:
            logger.warning(f"检查辅助功能权限失败: {ex}")
            return False

    @staticmethod
    def _prompt_accessibility_settings() -> None:
        """打开系统设置的辅助功能权限页面，引导用户授权。"""
        try:
            import subprocess
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:"
                "com.apple.preference.security?Privacy_Accessibility",
            ])
        except Exception as ex:
            logger.debug(f"打开系统设置失败: {ex}")
    
    # macOS 虚拟键码映射（与 Windows VK_CODES 对应）
    _MAC_KEY_CODES = {
        "A": 0, "S": 1, "D": 2, "F": 3, "H": 4, "G": 5, "Z": 6, "X": 7,
        "C": 8, "V": 9, "B": 11, "Q": 12, "W": 13, "E": 14, "R": 15,
        "Y": 16, "T": 17, "U": 32, "I": 34, "O": 31, "P": 35,
        "J": 38, "K": 40, "L": 37, "N": 45, "M": 46,
        "1": 18, "2": 19, "3": 20, "4": 21, "5": 23,
        "6": 22, "7": 26, "8": 28, "9": 25, "0": 29,
        "F1": 122, "F2": 120, "F3": 99, "F4": 118, "F5": 96, "F6": 97,
        "F7": 98, "F8": 100, "F9": 101, "F10": 109, "F11": 103, "F12": 111,
    }

    def start(self) -> bool:
        """启动全局热键监听。
        
        Returns:
            是否成功启动
        """
        if sys.platform not in ('win32', 'darwin'):
            logger.info("全局热键仅支持 Windows / macOS 系统")
            return False
        
        # 检查是否有任何功能启用
        ocr_enabled = self.config_service.get_config_value("ocr_hotkey_enabled", True)
        record_enabled = self.config_service.get_config_value("screen_record_hotkey_enabled", True)
        
        if not ocr_enabled and not record_enabled:
            logger.info("所有全局热键功能已禁用")
            return False
        
        if self._hotkey_thread and self._hotkey_thread.is_alive():
            return True
        
        # 预加载 OCR 模型（如果配置了且 OCR 功能启用）
        if ocr_enabled:
            preload_ocr = self.config_service.get_config_value("preload_ocr_model", False)
            if preload_ocr:
                self._preload_ocr()
        
        # 加载快捷键配置
        ocr_config = self.config_service.get_config_value("ocr_hotkey", {
            "ctrl": True, "shift": True, "alt": False, "key": "Q"
        })
        record_config = self.config_service.get_config_value("screen_record_hotkey", {
            "ctrl": True, "shift": True, "alt": False, "key": "C"
        })
        
        self._hotkey_stop_event = threading.Event()
        
        if sys.platform == 'darwin':
            return self._start_macos(ocr_enabled, record_enabled, ocr_config, record_config)
        else:
            return self._start_win32(ocr_enabled, record_enabled, ocr_config, record_config)
    
    # ── Windows 热键启动（原有逻辑） ─────────────────────────────
    def _start_win32(self, ocr_enabled, record_enabled, ocr_config, record_config) -> bool:
        """Windows 平台热键启动。"""
        def hotkey_loop():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            WM_HOTKEY = 0x0312
            MOD_ALT = 0x0001
            MOD_CTRL = 0x0002
            MOD_SHIFT = 0x0004
            MOD_NOREPEAT = 0x4000
            
            msg = wintypes.MSG()
            try:
                user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            except Exception:
                pass
            
            self._hotkey_thread_id = kernel32.GetCurrentThreadId()
            
            registered = []
            
            # 只有启用时才注册 OCR 快捷键
            if ocr_enabled:
                ocr_mods = MOD_NOREPEAT
                if ocr_config.get("ctrl"):
                    ocr_mods |= MOD_CTRL
                if ocr_config.get("alt"):
                    ocr_mods |= MOD_ALT
                if ocr_config.get("shift"):
                    ocr_mods |= MOD_SHIFT
                ocr_vk = self.VK_CODES.get(ocr_config.get("key", "Q"), 0x51)
                
                if user32.RegisterHotKey(None, self.HOTKEY_OCR, ocr_mods, ocr_vk):
                    registered.append(self.HOTKEY_OCR)
                    logger.info(f"全局热键已注册: OCR 截图识别 ({self._get_hotkey_display(ocr_config)})")
                else:
                    logger.warning(f"全局热键注册失败: OCR ({self._get_hotkey_display(ocr_config)})")
            
            # 只有启用时才注册录屏快捷键
            if record_enabled:
                record_mods = MOD_NOREPEAT
                if record_config.get("ctrl"):
                    record_mods |= MOD_CTRL
                if record_config.get("alt"):
                    record_mods |= MOD_ALT
                if record_config.get("shift"):
                    record_mods |= MOD_SHIFT
                record_vk = self.VK_CODES.get(record_config.get("key", "C"), 0x43)
                
                if user32.RegisterHotKey(None, self.HOTKEY_SCREEN_RECORD, record_mods, record_vk):
                    registered.append(self.HOTKEY_SCREEN_RECORD)
                    logger.info(f"全局热键已注册: 屏幕录制 ({self._get_hotkey_display(record_config)})")
                else:
                    logger.warning(f"全局热键注册失败: 屏幕录制 ({self._get_hotkey_display(record_config)})")
            
            if not registered:
                self._hotkey_thread_id = None
                return
            
            try:
                while not self._hotkey_stop_event.is_set():
                    ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if ret == 0:  # WM_QUIT
                        break
                    if ret == -1:
                        continue
                    
                    if msg.message == WM_HOTKEY:
                        hotkey_id = int(msg.wParam)
                        logger.debug(f"收到热键消息: msg.wParam={msg.wParam}, hotkey_id={hotkey_id}")
                        try:
                            self._handle_hotkey(hotkey_id)
                        except Exception as ex:
                            logger.error(f"热键处理异常: {ex}", exc_info=True)
                    
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            finally:
                for hk_id in registered:
                    try:
                        user32.UnregisterHotKey(None, hk_id)
                    except Exception:
                        pass
                logger.info("全局热键已注销")
                self._hotkey_thread_id = None
        
        self._hotkey_thread = threading.Thread(target=hotkey_loop, daemon=True)
        self._hotkey_thread.start()
        return True
    
    # ── macOS 热键启动（NSEvent） ─────────────────────────────────
    def _start_macos(self, ocr_enabled, record_enabled, ocr_config, record_config) -> bool:
        """macOS 平台使用 NSEvent 全局监听器监听热键。
        
        替代 pynput（CGEventTap）以避免在 Flutter 打包应用中崩溃。
        """
        # 1. 检查辅助功能权限
        if not self._check_accessibility_permission():
            logger.warning("macOS 辅助功能权限未授予，全局热键不可用。"
                           "请在 系统设置 > 隐私与安全性 > 辅助功能 中授权本应用，然后重启。")
            self._prompt_accessibility_settings()
            self._show_notification(
                "需要辅助功能权限才能使用全局热键，请在系统设置中授权后重启应用"
            )
            return False

        try:
            from AppKit import NSEvent
            from Foundation import NSRunLoop, NSDate, NSDefaultRunLoopMode
        except ImportError:
            logger.error("AppKit/Foundation 未安装，macOS 全局热键不可用")
            return False

        # 2. 构建 (keycode, ctrl, alt, shift) -> handler 映射
        _NSControlKeyMask = 1 << 18
        _NSAlternateKeyMask = 1 << 19
        _NSShiftKeyMask = 1 << 17

        hotkey_map: dict[tuple, Callable] = {}

        if ocr_enabled:
            kc = self._MAC_KEY_CODES.get(ocr_config.get("key", "Q").upper())
            if kc is not None:
                entry = (kc, bool(ocr_config.get("ctrl")),
                         bool(ocr_config.get("alt")), bool(ocr_config.get("shift")))
                hotkey_map[entry] = lambda: self._handle_hotkey(self.HOTKEY_OCR)
                logger.info(f"全局热键已注册: OCR 截图识别 ({self._get_hotkey_display(ocr_config)})")

        if record_enabled:
            kc = self._MAC_KEY_CODES.get(record_config.get("key", "C").upper())
            if kc is not None:
                entry = (kc, bool(record_config.get("ctrl")),
                         bool(record_config.get("alt")), bool(record_config.get("shift")))
                hotkey_map[entry] = lambda: self._handle_hotkey(self.HOTKEY_SCREEN_RECORD)
                logger.info(f"全局热键已注册: 屏幕录制 ({self._get_hotkey_display(record_config)})")

        if not hotkey_map:
            logger.warning("没有可注册的 macOS 热键")
            return False

        # 3. 在后台线程运行 NSEvent 全局监听
        self._hotkey_stop_event = threading.Event()

        def _monitor_loop():
            try:
                NSKeyDownMask = 1 << 10

                def _on_global_key(event):
                    try:
                        keycode = event.keyCode()
                        flags = event.modifierFlags()
                        key = (
                            keycode,
                            bool(flags & _NSControlKeyMask),
                            bool(flags & _NSAlternateKeyMask),
                            bool(flags & _NSShiftKeyMask),
                        )
                        cb = hotkey_map.get(key)
                        if cb:
                            threading.Thread(target=cb, daemon=True).start()
                    except Exception as ex:
                        logger.error(f"热键事件处理异常: {ex}")

                global_mon = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    NSKeyDownMask, _on_global_key)

                local_mon = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                    NSKeyDownMask, lambda evt: (_on_global_key(evt), evt)[1])

                if not global_mon:
                    logger.error("NSEvent 全局监听器创建失败")
                    return

                run_loop = NSRunLoop.currentRunLoop()
                while not self._hotkey_stop_event.is_set():
                    run_loop.runMode_beforeDate_(
                        NSDefaultRunLoopMode,
                        NSDate.dateWithTimeIntervalSinceNow_(0.5),
                    )

                if global_mon:
                    NSEvent.removeMonitor_(global_mon)
                if local_mon:
                    NSEvent.removeMonitor_(local_mon)
            except Exception as ex:
                logger.error(f"macOS 全局热键监听异常: {ex}", exc_info=True)

        self._hotkey_thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._hotkey_thread.start()

        logger.info("macOS 全局热键监听已启动 (NSEvent)")
        return True
    
    def stop(self) -> None:
        """停止全局热键监听。"""
        # 取消 OCR 卸载定时器
        if self._ocr_unload_timer is not None:
            try:
                self._ocr_unload_timer.cancel()
            except Exception:
                pass
            self._ocr_unload_timer = None
        
        # 卸载 OCR 模型
        if self._ocr_service is not None:
            try:
                self._ocr_service.unload_model()
            except Exception:
                pass
            self._ocr_service = None
        
        if not self._hotkey_thread:
            return
        
        # macOS: 通知 NSEvent 监听线程退出
        if sys.platform == 'darwin':
            if self._hotkey_stop_event:
                self._hotkey_stop_event.set()
        else:
            # Windows: 发送 WM_QUIT 消息
            try:
                if self._hotkey_stop_event:
                    self._hotkey_stop_event.set()
            except Exception:
                pass
            
            try:
                user32 = ctypes.windll.user32
                WM_QUIT = 0x0012
                if self._hotkey_thread_id:
                    user32.PostThreadMessageW(int(self._hotkey_thread_id), WM_QUIT, 0, 0)
            except Exception:
                pass
        
        self._hotkey_thread = None
        self._hotkey_stop_event = None
        self._hotkey_thread_id = None
    
    def restart(self) -> None:
        """重启热键监听（配置更改后调用）。"""
        self.stop()
        # 等待线程结束
        time.sleep(0.1)
        self.start()
    
    def _handle_hotkey(self, hotkey_id: int) -> None:
        """处理热键触发。"""
        logger.info(f"热键触发: ID={hotkey_id}")
        
        # 优先使用自定义回调
        if hotkey_id in self._callbacks:
            try:
                logger.debug(f"执行自定义回调: {hotkey_id}")
                self._callbacks[hotkey_id]()
            except Exception as ex:
                logger.error(f"热键回调执行失败: {ex}", exc_info=True)
            return
        
        # 默认处理
        if hotkey_id == self.HOTKEY_OCR:
            logger.info("触发 OCR 功能")
            self._trigger_ocr()
        elif hotkey_id == self.HOTKEY_SCREEN_RECORD:
            logger.info("触发屏幕录制功能")
            self._trigger_screen_record()
        else:
            logger.warning(f"未知热键 ID: {hotkey_id}")
    
    def _trigger_ocr(self) -> None:
        """触发 OCR 截图识别。"""
        logger.info("OCR 快捷键触发")
        
        # 检查是否正在进行区域选择，防止重复触发
        if self._ocr_selecting:
            logger.warning("OCR 区域选择正在进行中，忽略此次触发")
            return
        
        def do_ocr():
            logger.info("OCR 线程开始执行")
            selected = None
            img_array = None
            img_bgr = None
            should_unload = False
            
            try:
                logger.info("开始区域选择...")
                # 设置区域选择锁
                self._ocr_selecting = True
                try:
                    from utils.screen_selector import select_screen_region
                    region = select_screen_region(
                        hint_main="🔤 点击选择窗口  |  拖拽框选区域",
                        hint_sub="按 F 识别当前屏幕  |  ESC 取消",
                    )
                finally:
                    # 释放区域选择锁
                    self._ocr_selecting = False
                logger.info(f"区域选择结果: {region}")
                
                if region is None:
                    return
                
                x, y, w, h = region
                if w < 10 or h < 10:
                    self._show_notification("选择区域太小")
                    return
                
                # 截取选中区域（all_screens=True 支持多屏幕）
                # macOS: ImageGrab 使用 screencapture，期望点坐标而非像素坐标
                if sys.platform == 'darwin':
                    try:
                        from AppKit import NSScreen
                        scale = NSScreen.mainScreen().backingScaleFactor()
                    except Exception:
                        scale = 1.0
                    grab_bbox = (int(x / scale), int(y / scale), int((x + w) / scale), int((y + h) / scale))
                else:
                    grab_bbox = (x, y, x + w, y + h)
                selected = ImageGrab.grab(bbox=grab_bbox, all_screens=True)
                img_array = np.array(selected)
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # 立即释放不再需要的图像数据
                del selected
                selected = None
                del img_array
                img_array = None
                
                # 检查是否预加载模式（预加载模式下不卸载模型）
                preload_ocr = self.config_service.get_config_value("preload_ocr_model", False)
                # 非预加载模式，使用后应该卸载模型释放内存
                should_unload = not preload_ocr
                
                # 初始化 OCR 服务
                if self._ocr_service is None:
                    from services import OCRService
                    self._ocr_service = OCRService(self.config_service)
                
                # 加载模型（如果需要）
                if not self._ocr_service.det_session or not self._ocr_service.rec_session:
                    from constants import DEFAULT_OCR_MODEL_KEY
                    model_key = self.config_service.get_config_value("ocr_model_key", DEFAULT_OCR_MODEL_KEY)
                    use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
                    
                    success, message = self._ocr_service.load_model(
                        model_key,
                        use_gpu=use_gpu,
                        progress_callback=lambda p, m: None
                    )
                    if not success:
                        self._show_notification(f"OCR 模型加载失败: {message}")
                        return
                
                # 执行识别
                success, results = self._ocr_service.ocr_image(img_bgr)
                
                # 释放图像数据
                del img_bgr
                img_bgr = None
                
                # 用于跟踪需要清理的变量
                sorted_results = None
                text_lines = None
                full_text = None
                line_count = 0
                
                if success and results:
                    sorted_results = sorted(
                        results,
                        key=lambda x: (min(pt[1] for pt in x[0]), min(pt[0] for pt in x[0]))
                    )
                    text_lines = [text for _, text, _ in sorted_results]
                    line_count = len(text_lines)
                    full_text = "\n".join(text_lines)
                    
                    # 清理 results（包含大量坐标数据）
                    results.clear() if hasattr(results, 'clear') else None
                    del results
                    results = None
                    
                    # 复制到剪切板（使用 Windows 原生 API）
                    clipboard_success = False
                    try:
                        clipboard_success = self._copy_to_clipboard(full_text)
                    except Exception as e:
                        logger.warning(f"Windows API 剪切板失败: {e}")
                    
                    # 清理中间变量
                    if sorted_results:
                        sorted_results.clear() if hasattr(sorted_results, 'clear') else None
                        del sorted_results
                        sorted_results = None
                    if text_lines:
                        text_lines.clear() if hasattr(text_lines, 'clear') else None
                        del text_lines
                        text_lines = None
                    
                    if clipboard_success:
                        self._show_notification(f"已识别 {line_count} 行文字并复制到剪切板")
                        logger.info(f"OCR 识别完成，已复制 {line_count} 行文字")
                    else:
                        self._show_notification(f"已识别 {line_count} 行，但复制到剪切板失败")
                    
                    # 清理 full_text
                    del full_text
                    full_text = None
                else:
                    # 清理 results
                    if results:
                        results.clear() if hasattr(results, 'clear') else None
                        del results
                        results = None
                    self._show_notification("未识别到文字")
                    
            except Exception as ex:
                logger.error(f"OCR 截图识别失败: {ex}", exc_info=True)
                self._show_notification(f"识别失败: {str(ex)}")
            finally:
                # 清理资源
                try:
                    if selected is not None:
                        del selected
                    if img_array is not None:
                        del img_array
                    if img_bgr is not None:
                        del img_bgr
                except Exception:
                    pass
                
                if self._ocr_service is not None:
                    if should_unload:
                        # 非预加载模式：用完即卸载，尽快回收 ORT/DML 资源
                        try:
                            self._ocr_service.unload_model()
                        except Exception:
                            pass
                        self._ocr_service = None
                    else:
                        # 预加载模式：仍然安排空闲卸载，避免模型一直常驻占用高水位
                        self._schedule_ocr_unload()
                
                # 激进垃圾回收（回收所有代）
                try:
                    gc.collect(0)
                    gc.collect(1)
                    gc.collect(2)
                    gc.collect()
                except Exception:
                    pass
        
        thread = threading.Thread(target=do_ocr, daemon=True)
        thread.start()
    
    def _schedule_ocr_unload(self) -> None:
        """安排 OCR 模型延迟卸载。
        
        如果已有定时器在运行，会先取消再重新安排。
        这样连续使用时会不断重置定时器，只有空闲一段时间后才会卸载。
        """
        # 取消已有的定时器
        if self._ocr_unload_timer is not None:
            try:
                self._ocr_unload_timer.cancel()
            except Exception:
                pass
            self._ocr_unload_timer = None
        
        # 启动新的延迟卸载定时器
        self._ocr_unload_timer = threading.Timer(
            self._ocr_unload_delay,
            self._do_ocr_unload
        )
        self._ocr_unload_timer.daemon = True
        self._ocr_unload_timer.start()
        logger.debug(f"OCR 模型将在 {self._ocr_unload_delay} 秒后自动卸载")
    
    def _do_ocr_unload(self) -> None:
        """执行 OCR 模型卸载。"""
        try:
            if self._ocr_service is not None:
                self._ocr_service.unload_model()
                del self._ocr_service
                self._ocr_service = None
                logger.info("OCR 模型已自动卸载，内存已释放")
            
            # 激进垃圾回收（确保循环引用被清理）
            gc.collect(0)
            gc.collect(1)
            gc.collect(2)
            gc.collect()
            gc.collect()  # 再来一次确保彻底
        except Exception as e:
            logger.warning(f"自动卸载 OCR 模型失败: {e}")
        finally:
            self._ocr_unload_timer = None
    
    def _trigger_screen_record(self) -> None:
        """触发屏幕录制 - 直接框选区域并开始录制。"""
        def do_screen_record():
            try:
                import subprocess
                
                from utils.screen_selector import select_screen_region
                region = select_screen_region(
                    hint_main="🎬 点击选择窗口  |  拖拽框选区域",
                    hint_sub="按 F 录制当前屏幕  |  ESC 取消",
                )
                
                if region is None:
                    return
                
                x, y, w, h = region
                if w < 10 or h < 10:
                    self._show_notification("选择区域太小")
                    return
                
                # 确保宽高为偶数（FFmpeg 要求）
                w = w if w % 2 == 0 else w - 1
                h = h if h % 2 == 0 else h - 1
                
                # 获取 FFmpeg 路径
                from services import FFmpegService
                ffmpeg_service = FFmpegService(self.config_service)
                ffmpeg_path = ffmpeg_service.get_ffmpeg_path()
                
                if not ffmpeg_path:
                    self._show_notification("FFmpeg 未安装，无法录制")
                    return
                
                # 生成输出文件名
                if sys.platform == 'darwin':
                    default_output = str(Path.home() / "Movies" / "MTools" / "录屏")
                else:
                    default_output = str(Path.home() / "Videos" / "MTools" / "录屏")
                output_dir = Path(self.config_service.get_config_value(
                    "screen_record_output_dir", default_output
                ))
                output_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_file = output_dir / f"screen_record_{timestamp}.mp4"
                
                # 使用 ffmpeg-python 构建录制流
                import ffmpeg
                
                # 检测可用的 GPU 编码器
                encoder = "libx264"
                encoder_opts = {"preset": "ultrafast", "crf": 23}
                
                gpu_encoders = ffmpeg_service.detect_gpu_encoders()
                if gpu_encoders:
                    preferred = ["h264_videotoolbox"] if sys.platform == 'darwin' else [
                        "h264_nvenc", "h264_amf", "h264_qsv"
                    ]
                    for gpu_enc in preferred:
                        if gpu_enc in gpu_encoders:
                            encoder = gpu_enc
                            if gpu_enc == "h264_videotoolbox":
                                encoder_opts = {"q:v": 65}  # VT 质量 0-100
                            elif gpu_enc == "h264_nvenc":
                                encoder_opts = {"preset": "p4", "cq": 23}
                            elif gpu_enc == "h264_amf":
                                encoder_opts = {"quality": "speed", "rc": "cqp", "qp": 23}
                            elif gpu_enc == "h264_qsv":
                                encoder_opts = {"preset": "veryfast", "global_quality": 23}
                            break
                
                logger.info(f"屏幕录制使用编码器: {encoder}")
                
                # ── 构建 FFmpeg 流（平台差异） ─────────────────────
                if sys.platform == 'darwin':
                    # macOS: avfoundation 捕获整个屏幕，再用 crop 裁剪
                    stream = ffmpeg.input(
                        "1:none",
                        format="avfoundation",
                        framerate=30,
                        capture_cursor=1,
                    )
                    stream = stream.filter("crop", w, h, x, y)
                else:
                    # Windows: gdigrab 支持直接指定区域
                    input_kwargs = {
                        "f": "gdigrab",
                        "framerate": 30,
                        "offset_x": x,
                        "offset_y": y,
                        "s": f"{w}x{h}",
                    }
                    stream = ffmpeg.input("desktop", **input_kwargs)
                
                # 统一：确保输出尺寸为偶数（编码器要求）
                stream = stream.filter("scale", "trunc(iw/2)*2", "trunc(ih/2)*2")
                stream = ffmpeg.output(
                    stream,
                    str(output_file),
                    vcodec=encoder,
                    pix_fmt="yuv420p",
                    **encoder_opts
                )
                
                # 获取完整命令用于日志
                cmd_args = ffmpeg.compile(stream, cmd=str(ffmpeg_path), overwrite_output=True)
                logger.info(f"FFmpeg 命令: {' '.join(cmd_args)}")
                
                # 使用 ffmpeg-python 启动异步进程（这样 stdin 会正确设置）
                self._recording_process = ffmpeg.run_async(
                    stream,
                    cmd=str(ffmpeg_path),
                    pipe_stdin=True,
                    pipe_stderr=True,
                    overwrite_output=True,
                )
                
                # 启动线程监控 FFmpeg 输出
                self._stderr_output = []
                def read_stderr():
                    try:
                        for line in iter(self._recording_process.stderr.readline, b''):
                            if line:
                                decoded = line.decode('utf-8', errors='replace').strip()
                                self._stderr_output.append(decoded)
                                if 'error' in decoded.lower() or 'failed' in decoded.lower():
                                    logger.error(f"FFmpeg: {decoded}")
                    except Exception:
                        pass
                
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stderr_thread.start()
                
                # 等待一小段时间检查进程是否正常启动
                time.sleep(0.5)
                if self._recording_process.poll() is not None:
                    # 进程已结束，说明启动失败
                    error_output = '\n'.join(self._stderr_output[-5:]) if self._stderr_output else "未知错误"
                    logger.error(f"FFmpeg 启动失败: {error_output}")
                    self._recording_process = None
                    self._show_notification(f"录制启动失败: {error_output[:50]}")
                    return
                
                self._recording_output_file = output_file
                self._is_recording = True
                
                self._show_notification(f"开始录制... 按 {self._get_hotkey_display(self.config_service.get_config_value('screen_record_hotkey', {}))} 停止")
                logger.info(f"屏幕录制已开始: {output_file}")
                
            except Exception as ex:
                logger.error(f"屏幕录制启动失败: {ex}", exc_info=True)
                self._show_notification(f"录制失败: {str(ex)}")
        
        # 检查是否正在录制
        if hasattr(self, '_is_recording') and self._is_recording:
            # 停止录制
            self._stop_screen_record()
        else:
            # 开始录制
            thread = threading.Thread(target=do_screen_record, daemon=True)
            thread.start()
    
    def _stop_screen_record(self) -> None:
        """停止屏幕录制。"""
        def do_stop():
            try:
                if hasattr(self, '_recording_process') and self._recording_process:
                    proc = self._recording_process
                    
                    # 检查进程是否还在运行
                    if proc.poll() is None:
                        # 方法1: 发送 'q' 命令让 FFmpeg 正常退出
                        try:
                            if proc.stdin:
                                proc.stdin.write(b'q\n')
                                proc.stdin.flush()
                        except Exception as e:
                            logger.debug(f"发送 q 命令失败: {e}")
                        
                        # 等待进程结束（3秒）
                        try:
                            proc.wait(timeout=3)
                            logger.info("FFmpeg 正常退出")
                        except Exception:
                            # 方法2: 如果 'q' 命令无效，使用 terminate
                            logger.info("发送 terminate 信号...")
                            proc.terminate()
                            try:
                                proc.wait(timeout=3)
                            except Exception:
                                # 方法3: 最后使用 kill 强制终止
                                logger.info("发送 kill 信号...")
                                proc.kill()
                                try:
                                    proc.wait(timeout=2)
                                except Exception:
                                    pass
                    
                    # 关闭管道
                    try:
                        if proc.stdin:
                            proc.stdin.close()
                        if proc.stderr:
                            proc.stderr.close()
                    except Exception:
                        pass
                    
                    self._recording_process = None
                
                self._is_recording = False
                
                # 清理 stderr 输出列表，释放内存
                if hasattr(self, '_stderr_output'):
                    self._stderr_output.clear()
                    self._stderr_output = None
                
                if hasattr(self, '_recording_output_file') and self._recording_output_file:
                    output_file = self._recording_output_file
                    self._recording_output_file = None
                    
                    # 检查文件是否有效
                    time.sleep(0.3)  # 等待文件系统同步
                    
                    if output_file.exists() and output_file.stat().st_size > 1000:
                        self._show_notification(f"录制完成: {output_file.name}")
                        logger.info(f"屏幕录制已完成: {output_file}")
                    else:
                        self._show_notification("录制完成，但文件可能不完整")
                        logger.warning(f"录制文件可能不完整: {output_file}")
                else:
                    self._show_notification("录制已停止")
                    
            except Exception as ex:
                logger.error(f"停止录制失败: {ex}", exc_info=True)
                self._show_notification(f"停止失败: {str(ex)}")
        
        # 在后台线程中停止（避免阻塞热键线程）
        thread = threading.Thread(target=do_stop, daemon=True)
        thread.start()
    
    def _copy_to_clipboard(self, text: str) -> bool:
        """复制文本到剪切板（跨平台）。
        
        Args:
            text: 要复制的文本
            
        Returns:
            是否成功
        """
        if sys.platform == 'darwin':
            return self._copy_to_clipboard_macos(text)
        
        if sys.platform != 'win32':
            logger.warning("剪切板功能仅支持 Windows / macOS")
            return False
        
        if not text:
            logger.warning("剪切板复制：文本为空")
            return False
        
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # 正确设置函数参数和返回类型
            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            user32.SetClipboardData.restype = wintypes.HANDLE
            
            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL
            kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalFree.restype = wintypes.HGLOBAL
            
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002
            
            # 打开剪切板（最多尝试 3 次）
            opened = False
            for _ in range(3):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.1)
            
            if not opened:
                logger.warning("无法打开剪切板（可能被其他程序占用）")
                return False
            
            try:
                # 清空剪切板
                user32.EmptyClipboard()
                
                # 分配内存（UTF-16 编码）
                text_bytes = (text + '\0').encode('utf-16-le')
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if not h_mem:
                    logger.warning("剪切板内存分配失败")
                    return False
                
                # 锁定内存并复制数据
                ptr = kernel32.GlobalLock(h_mem)
                if ptr:
                    ctypes.memmove(ptr, text_bytes, len(text_bytes))
                    kernel32.GlobalUnlock(h_mem)
                    
                    # 设置剪切板数据
                    result = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    if result:
                        logger.info(f"剪切板复制成功: {len(text)} 字符")
                        return True
                    else:
                        error_code = ctypes.get_last_error()
                        logger.warning(f"SetClipboardData 失败, 错误码: {error_code}")
                        kernel32.GlobalFree(h_mem)
                        return False
                else:
                    logger.warning("GlobalLock 失败")
                    kernel32.GlobalFree(h_mem)
                    return False
                    
            finally:
                user32.CloseClipboard()
                
        except Exception as ex:
            logger.warning(f"复制到剪切板失败: {ex}", exc_info=True)
            return False
    
    def _copy_to_clipboard_macos(self, text: str) -> bool:
        """macOS: 使用 pbcopy 复制文本到剪切板。"""
        if not text:
            logger.warning("剪切板复制：文本为空")
            return False
        try:
            import subprocess
            proc = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                env={"LANG": "en_US.UTF-8"},
            )
            proc.communicate(text.encode("utf-8"))
            if proc.returncode == 0:
                logger.info(f"剪切板复制成功 (pbcopy): {len(text)} 字符")
                return True
            else:
                logger.warning(f"pbcopy 返回码: {proc.returncode}")
                return False
        except Exception as ex:
            logger.warning(f"macOS 剪切板复制失败: {ex}", exc_info=True)
            return False
    
    def _show_notification(self, message: str) -> None:
        """显示通知。窗口不在前台时跳过 UI 提示，避免下次打开窗口时弹出过期消息。"""
        logger.info(f"通知: {message}")
        if self._page:
            try:
                window_focused = getattr(self._page.window, "focused", None)
                if window_focused is False:
                    logger.debug("窗口未聚焦，跳过 SnackBar")
                    return

                def show():
                    try:
                        import flet as ft
                        snack = ft.SnackBar(content=ft.Text(message), duration=3000)
                        self._page.open(snack)
                    except Exception as e:
                        logger.debug(f"显示通知失败: {e}")

                if hasattr(self._page, "call_from_thread"):
                    self._page.call_from_thread(show)
                else:
                    show()
            except Exception:
                pass

