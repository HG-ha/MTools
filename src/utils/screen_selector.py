# -*- coding: utf-8 -*-
"""屏幕区域选择模块（替代 tkinter）。

提供跨平台的屏幕区域选择功能：
  - Windows: ctypes Win32 API 原生实现
  - macOS:   PyObjC 原生实现
  - Linux:   暂不支持

功能：
  - 截取全屏（支持多显示器）
  - 暗化覆盖层
  - 鼠标悬停自动识别并高亮窗口 / 屏幕
  - 点击选择窗口、拖拽框选自定义区域
  - 选中区域显示原始亮度 + 边框 + 尺寸标注
  - ESC 取消，F / Enter 选择当前屏幕全屏
"""

import sys
from typing import Optional, Tuple, Union

from utils.logger import logger

# 返回值类型
RegionResult = Optional[Union[Tuple[int, int, int, int], Tuple[int, int, int, int, str]]]


def select_screen_region(
    hint_main: str = "点击选择窗口 | 拖拽框选区域",
    hint_sub: str = "按 F 选择当前屏幕 | ESC 取消",
    return_window_title: bool = False,
) -> RegionResult:
    """弹出全屏覆盖层，让用户交互式选择一个屏幕区域。

    Args:
        hint_main: 覆盖层上方的主提示文字
        hint_sub:  覆盖层上方的副提示文字
        return_window_title: 如果为 True，点击窗口时返回 5 元组
            ``(x, y, w, h, window_title)``；否则只返回 4 元组

    Returns:
        ``(x, y, w, h)`` — 像素坐标（全局 top-left 原点），自定义区域 / 显示器
        ``(x, y, w, h, title)`` — 像素坐标 + 窗口标题（仅 return_window_title=True 且点击窗口时）
        ``None`` — 用户取消（ESC）或发生错误
    """
    if sys.platform == "win32":
        return _select_win32(hint_main, hint_sub, return_window_title)
    elif sys.platform == "darwin":
        return _select_macos(hint_main, hint_sub, return_window_title)
    else:
        logger.warning("屏幕区域选择暂不支持当前平台: %s", sys.platform)
        return None


# ═══════════════════════════════════════════════════════════════════
#  Windows 实现（ctypes Win32 API）
# ═══════════════════════════════════════════════════════════════════

def _select_win32(hint_main: str, hint_sub: str, return_window_title: bool) -> RegionResult:
    """Windows: 用 ctypes 创建独立 Win32 覆盖窗口。"""
    import ctypes
    import ctypes.wintypes as wintypes
    from PIL import Image, ImageGrab

    # ── 64 位兼容 ──
    LRESULT = ctypes.c_ssize_t

    # ── Win32 常量 ──
    WS_POPUP         = 0x80000000
    WS_VISIBLE       = 0x10000000
    WS_EX_TOPMOST    = 0x00000008
    WS_EX_TOOLWINDOW = 0x00000080
    CS_HREDRAW       = 0x0002
    CS_VREDRAW       = 0x0001
    WM_DESTROY       = 0x0002
    WM_PAINT         = 0x000F
    WM_ERASEBKGND    = 0x0014
    WM_SETCURSOR     = 0x0020
    WM_KEYDOWN       = 0x0100
    WM_LBUTTONDOWN   = 0x0201
    WM_LBUTTONUP     = 0x0202
    WM_MOUSEMOVE     = 0x0200
    VK_ESCAPE        = 0x1B
    VK_F             = 0x46
    VK_RETURN        = 0x0D
    SRCCOPY          = 0x00CC0020
    DIB_RGB_COLORS   = 0
    BI_RGB           = 0
    PS_SOLID         = 0
    NULL_BRUSH       = 5
    TRANSPARENT_BG   = 1
    HTCLIENT         = 1
    IDC_CROSS        = 32515
    DT_CENTER        = 0x0001
    DT_SINGLELINE    = 0x0020
    DT_VCENTER       = 0x0004
    SM_XVIRTUALSCREEN  = 76
    SM_YVIRTUALSCREEN  = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79
    GWL_STYLE        = -16
    WS_MINIMIZE      = 0x20000000

    # ── 结构体 ──
    WNDPROC_TYPE = ctypes.WINFUNCTYPE(
        LRESULT, wintypes.HWND, wintypes.UINT,
        wintypes.WPARAM, wintypes.LPARAM,
    )
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM,
    )
    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(wintypes.RECT), ctypes.c_void_p,
    )

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT), ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC_TYPE),
            ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HICON), ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HICON),
        ]

    class PAINTSTRUCT(ctypes.Structure):
        _fields_ = [
            ("hdc", wintypes.HDC), ("fErase", wintypes.BOOL),
            ("rcPaint", wintypes.RECT), ("fRestore", wintypes.BOOL),
            ("fIncUpdate", wintypes.BOOL), ("rgbReserved", wintypes.BYTE * 32),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = LRESULT

    def _rgb(r, g, b):
        return r | (g << 8) | (b << 16)

    def _pil_to_memdc(image):
        w, h = image.size
        rgba = image.convert("RGBA")
        r, g, b, a = rgba.split()
        bgra = Image.merge("RGBA", (b, g, r, a))
        raw = bgra.tobytes()
        bmi = BITMAPINFO()
        hdr = bmi.bmiHeader
        hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        hdr.biWidth = w
        hdr.biHeight = -h
        hdr.biPlanes = 1
        hdr.biBitCount = 32
        hdr.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        screen_dc = user32.GetDC(None)
        hbitmap = gdi32.CreateDIBSection(
            screen_dc, ctypes.byref(bmi), DIB_RGB_COLORS,
            ctypes.byref(bits), None, 0,
        )
        user32.ReleaseDC(None, screen_dc)
        if not hbitmap or not bits:
            return None, None, None
        ctypes.memmove(bits, raw, len(raw))
        mem_dc = gdi32.CreateCompatibleDC(None)
        old_bmp = gdi32.SelectObject(mem_dc, hbitmap)
        return mem_dc, hbitmap, old_bmp

    def _free_memdc(mem_dc, hbitmap, old_bmp):
        if mem_dc:
            if old_bmp:
                gdi32.SelectObject(mem_dc, old_bmp)
            gdi32.DeleteDC(mem_dc)
        if hbitmap:
            gdi32.DeleteObject(hbitmap)

    def _enum_windows_win32(v_left, v_top, v_w, v_h, own_hwnd):
        rects = []
        def cb(hwnd, _lp):
            if hwnd == own_hwnd or not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_MINIMIZE:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w >= 50 and h >= 50:
                    rl = rect.left - v_left
                    rt = rect.top - v_top
                    if rl < v_w and rt < v_h and rl + w > 0 and rt + h > 0:
                        rects.append((title, rl, rt, w, h))
            return True
        cb_ref = WNDENUMPROC(cb)
        user32.EnumWindows(cb_ref, 0)
        return rects

    def _enum_monitors_win32(v_left, v_top, v_w, v_h):
        mons = []
        def cb(hMon, hdcMon, lprc, dw):
            r = lprc.contents
            mons.append((r.left - v_left, r.top - v_top,
                         r.right - v_left, r.bottom - v_top))
            return 1
        cb_ref = MONITORENUMPROC(cb)
        user32.EnumDisplayMonitors(None, None, cb_ref, 0)
        if not mons:
            mons = [(0, 0, v_w, v_h)]
        return mons

    # ── 主逻辑 ──
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    v_left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    v_top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    v_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    v_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if v_w <= 0 or v_h <= 0:
        v_left = v_top = 0
        v_w = user32.GetSystemMetrics(0)
        v_h = user32.GetSystemMetrics(1)

    try:
        screenshot = ImageGrab.grab(
            bbox=(v_left, v_top, v_left + v_w, v_top + v_h), all_screens=True,
        )
    except Exception as ex:
        logger.error("截取屏幕失败: %s", ex)
        return None

    black = Image.new("RGB", screenshot.size, (0, 0, 0))
    darkened = Image.blend(screenshot, black, 0.5)
    black.close()

    dark_dc, dark_bmp, dark_old = _pil_to_memdc(darkened)
    orig_dc, orig_bmp, orig_old = _pil_to_memdc(screenshot)
    if not dark_dc or not orig_dc:
        logger.error("创建 GDI 位图失败")
        _free_memdc(dark_dc, dark_bmp, dark_old)
        _free_memdc(orig_dc, orig_bmp, orig_old)
        darkened.close()
        screenshot.close()
        return None

    state = {
        "dragging": False, "sx": 0, "sy": 0, "cx": 0, "cy": 0,
        "result": None,
        "hover_window": None, "hover_monitor": None, "cur_monitor": -1,
    }
    window_rects = []
    monitors = []

    # ── 绘制辅助 ──
    def _draw_hint(hdc, title_text=""):
        mon_idx = max(0, state["cur_monitor"])
        if mon_idx < len(monitors):
            ml, mt, mr, mb = monitors[mon_idx]
        else:
            ml, mt, mr, mb = 0, 0, v_w, v_h
        cx = ml + (mr - ml) // 2
        bg_l, bg_t = cx - 240, 25
        bg_r, bg_b = cx + 240, 95
        bg_brush = gdi32.CreateSolidBrush(_rgb(26, 26, 26))
        bg_rect = wintypes.RECT(bg_l, bg_t, bg_r, bg_b)
        user32.FillRect(hdc, ctypes.byref(bg_rect), bg_brush)
        gdi32.DeleteObject(bg_brush)
        border_pen = gdi32.CreatePen(PS_SOLID, 1, _rgb(51, 51, 51))
        old_pen = gdi32.SelectObject(hdc, border_pen)
        old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
        gdi32.Rectangle(hdc, bg_l, bg_t, bg_r, bg_b)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.DeleteObject(border_pen)
        gdi32.SetBkMode(hdc, TRANSPARENT_BG)
        font_main = gdi32.CreateFontW(20, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 0, 0, "Microsoft YaHei")
        old_font = gdi32.SelectObject(hdc, font_main)
        gdi32.SetTextColor(hdc, _rgb(255, 255, 255))
        r1 = wintypes.RECT(bg_l, bg_t + 8, bg_r, bg_t + 38)
        user32.DrawTextW(hdc, hint_main, -1, ctypes.byref(r1), DT_CENTER | DT_SINGLELINE | DT_VCENTER)
        font_sub = gdi32.CreateFontW(16, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Microsoft YaHei")
        gdi32.SelectObject(hdc, font_sub)
        gdi32.SetTextColor(hdc, _rgb(136, 136, 136))
        r2 = wintypes.RECT(bg_l, bg_t + 38, bg_r, bg_b - 2)
        user32.DrawTextW(hdc, hint_sub, -1, ctypes.byref(r2), DT_CENTER | DT_SINGLELINE | DT_VCENTER)
        if title_text:
            font_title = gdi32.CreateFontW(18, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Microsoft YaHei")
            gdi32.SelectObject(hdc, font_title)
            gdi32.SetTextColor(hdc, _rgb(0, 191, 255))
            r3 = wintypes.RECT(bg_l - 60, bg_b + 8, bg_r + 60, bg_b + 32)
            user32.DrawTextW(hdc, title_text, -1, ctypes.byref(r3), DT_CENTER | DT_SINGLELINE | DT_VCENTER)
            gdi32.DeleteObject(font_title)
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(font_main)
        gdi32.DeleteObject(font_sub)

    def _draw_size_label(hdc, x1, y1, x2, y2):
        w, h = x2 - x1, y2 - y1
        if w < 20 or h < 20:
            return
        label = f"{w} × {h}"
        lx, ly = x1, y2 + 4
        if ly + 22 > v_h:
            ly = y1 - 22
        font = gdi32.CreateFontW(14, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Microsoft YaHei")
        old_font = gdi32.SelectObject(hdc, font)
        gdi32.SetBkMode(hdc, TRANSPARENT_BG)
        label_bg = gdi32.CreateSolidBrush(_rgb(30, 30, 30))
        lr = wintypes.RECT(lx, ly, lx + len(label) * 9 + 16, ly + 20)
        user32.FillRect(hdc, ctypes.byref(lr), label_bg)
        gdi32.DeleteObject(label_bg)
        gdi32.SetTextColor(hdc, _rgb(200, 200, 200))
        user32.DrawTextW(hdc, label, -1, ctypes.byref(lr), DT_CENTER | DT_SINGLELINE | DT_VCENTER)
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(font)

    def _draw_highlight(hdc, hl, ht, hr, hb, color):
        cl, ct = max(0, hl), max(0, ht)
        cr, cb = min(v_w, hr), min(v_h, hb)
        if cr <= cl or cb <= ct:
            return
        gdi32.BitBlt(hdc, cl, ct, cr - cl, cb - ct, orig_dc, cl, ct, SRCCOPY)
        pen = gdi32.CreatePen(PS_SOLID, 3, color)
        old_pen = gdi32.SelectObject(hdc, pen)
        old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
        gdi32.Rectangle(hdc, cl, ct, cr, cb)
        gdi32.SelectObject(hdc, old_pen)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.DeleteObject(pen)

    def _find_window_at(x, y):
        for item in window_rects:
            title, wl, wt, ww, wh = item
            if wl <= x <= wl + ww and wt <= y <= wt + wh:
                return item
        return None

    def _get_monitor_at(x, y):
        for i, (ml, mt, mr, mb) in enumerate(monitors):
            if ml <= x <= mr and mt <= y <= mb:
                return i, (ml, mt, mr - ml, mb - mt)
        return 0, (0, 0, v_w, v_h)

    def _update_hover(x, y):
        changed = False
        mon_idx, _ = _get_monitor_at(x, y)
        if state["cur_monitor"] != mon_idx:
            state["cur_monitor"] = mon_idx
            changed = True
        win = _find_window_at(x, y)
        if win != state["hover_window"]:
            state["hover_window"] = win
            changed = True
        if win:
            if state["hover_monitor"] is not None:
                state["hover_monitor"] = None
                changed = True
        else:
            new_mon = (mon_idx, *_get_monitor_at(x, y)[1])
            if state["hover_monitor"] != new_mon:
                state["hover_monitor"] = new_mon
                changed = True
        return changed

    # ── 窗口过程 ──
    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            buf = gdi32.CreateCompatibleDC(hdc)
            buf_bmp = gdi32.CreateCompatibleBitmap(hdc, v_w, v_h)
            buf_old = gdi32.SelectObject(buf, buf_bmp)
            gdi32.BitBlt(buf, 0, 0, v_w, v_h, dark_dc, 0, 0, SRCCOPY)
            title_text = ""
            if state["dragging"]:
                x1 = min(state["sx"], state["cx"])
                y1 = min(state["sy"], state["cy"])
                x2 = max(state["sx"], state["cx"])
                y2 = max(state["sy"], state["cy"])
                if x2 - x1 > 0 and y2 - y1 > 0:
                    _draw_highlight(buf, x1, y1, x2, y2, _rgb(255, 107, 107))
                    _draw_size_label(buf, x1, y1, x2, y2)
                title_text = "拖拽选择区域..."
            else:
                if state["hover_window"]:
                    title, wl, wt, ww, wh = state["hover_window"]
                    _draw_highlight(buf, wl, wt, wl + ww, wt + wh, _rgb(0, 191, 255))
                    display = title[:50] + "..." if len(title) > 50 else title
                    title_text = f"\U0001f5a5 {display}"
                elif state["hover_monitor"]:
                    idx, ml, mt, mw, mh = state["hover_monitor"]
                    _draw_highlight(buf, ml, mt, ml + mw, mt + mh, _rgb(255, 107, 107))
                    title_text = f"\U0001f5a5 屏幕 {idx + 1} ({mw}×{mh})"
            _draw_hint(buf, title_text)
            gdi32.BitBlt(hdc, 0, 0, v_w, v_h, buf, 0, 0, SRCCOPY)
            gdi32.SelectObject(buf, buf_old)
            gdi32.DeleteObject(buf_bmp)
            gdi32.DeleteDC(buf)
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        elif msg == WM_ERASEBKGND:
            return 1
        elif msg == WM_SETCURSOR:
            if (lparam & 0xFFFF) == HTCLIENT:
                user32.SetCursor(user32.LoadCursorW(None, IDC_CROSS))
                return 1
        elif msg == WM_LBUTTONDOWN:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            state["sx"] = state["cx"] = x
            state["sy"] = state["cy"] = y
            state["dragging"] = True
            user32.SetCapture(hwnd)
            return 0
        elif msg == WM_MOUSEMOVE:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            if state["dragging"]:
                state["cx"] = x
                state["cy"] = y
                user32.InvalidateRect(hwnd, None, False)
            else:
                if _update_hover(x, y):
                    user32.InvalidateRect(hwnd, None, False)
            return 0
        elif msg == WM_LBUTTONUP:
            if state["dragging"]:
                state["dragging"] = False
                user32.ReleaseCapture()
                ex = ctypes.c_short(lparam & 0xFFFF).value
                ey = ctypes.c_short((lparam >> 16) & 0xFFFF).value
                x1, y1 = min(state["sx"], ex), min(state["sy"], ey)
                x2, y2 = max(state["sx"], ex), max(state["sy"], ey)
                w, h = x2 - x1, y2 - y1
                if w >= 10 and h >= 10:
                    state["result"] = (x1 + v_left, y1 + v_top, w, h)
                    user32.DestroyWindow(hwnd)
                elif state["hover_window"]:
                    title, wl, wt, ww, wh = state["hover_window"]
                    cl, ct = max(0, wl), max(0, wt)
                    cr, cb = min(v_w, wl + ww), min(v_h, wt + wh)
                    fw, fh = cr - cl, cb - ct
                    if fw >= 10 and fh >= 10:
                        if return_window_title:
                            state["result"] = (cl + v_left, ct + v_top, fw, fh, title)
                        else:
                            state["result"] = (cl + v_left, ct + v_top, fw, fh)
                        user32.DestroyWindow(hwnd)
                elif state["hover_monitor"]:
                    idx, ml, mt, mw, mh = state["hover_monitor"]
                    state["result"] = (ml + v_left, mt + v_top, mw, mh)
                    user32.DestroyWindow(hwnd)
                else:
                    user32.InvalidateRect(hwnd, None, False)
            return 0
        elif msg == WM_KEYDOWN:
            if wparam == VK_ESCAPE:
                state["result"] = None
                user32.DestroyWindow(hwnd)
                return 0
            elif wparam in (VK_F, VK_RETURN):
                mon_idx = max(0, state["cur_monitor"])
                if mon_idx < len(monitors):
                    ml, mt, mr, mb = monitors[mon_idx]
                    state["result"] = (ml + v_left, mt + v_top, mr - ml, mb - mt)
                else:
                    state["result"] = (v_left, v_top, v_w, v_h)
                user32.DestroyWindow(hwnd)
                return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wnd_proc_cb = WNDPROC_TYPE(wnd_proc)
    h_instance = kernel32.GetModuleHandleW(None)
    class_name = "MToolsScreenSelector"

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = wnd_proc_cb
    wc.hInstance = h_instance
    wc.hCursor = user32.LoadCursorW(None, IDC_CROSS)
    wc.lpszClassName = class_name

    atom = user32.RegisterClassExW(ctypes.byref(wc))
    if not atom:
        logger.error("RegisterClassExW 失败: %s", ctypes.get_last_error())
        _free_memdc(dark_dc, dark_bmp, dark_old)
        _free_memdc(orig_dc, orig_bmp, orig_old)
        darkened.close()
        screenshot.close()
        return None

    hwnd = user32.CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW, class_name, None,
        WS_POPUP | WS_VISIBLE, v_left, v_top, v_w, v_h,
        None, None, h_instance, None,
    )
    if not hwnd:
        logger.error("CreateWindowExW 失败: %s", ctypes.get_last_error())
        user32.UnregisterClassW(class_name, h_instance)
        _free_memdc(dark_dc, dark_bmp, dark_old)
        _free_memdc(orig_dc, orig_bmp, orig_old)
        darkened.close()
        screenshot.close()
        return None

    window_rects = _enum_windows_win32(v_left, v_top, v_w, v_h, hwnd)
    monitors = _enum_monitors_win32(v_left, v_top, v_w, v_h)
    logger.debug("屏幕选择器: %d 个窗口, %d 个显示器", len(window_rects), len(monitors))

    user32.SetForegroundWindow(hwnd)
    user32.SetFocus(hwnd)

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    _free_memdc(dark_dc, dark_bmp, dark_old)
    _free_memdc(orig_dc, orig_bmp, orig_old)
    darkened.close()
    screenshot.close()
    user32.UnregisterClassW(class_name, h_instance)

    return state["result"]


# ═══════════════════════════════════════════════════════════════════
#  macOS 实现（PyObjC）
# ═══════════════════════════════════════════════════════════════════

def _select_macos(hint_main: str, hint_sub: str, return_window_title: bool) -> RegionResult:
    """macOS: 用 PyObjC 创建原生 NSWindow 覆盖层。"""
    try:
        import objc
        from AppKit import (
            NSApplication, NSApp, NSBezierPath, NSColor,
            NSCompositingOperationCopy, NSCompositingOperationSourceOver,
            NSCursor, NSEvent, NSFont, NSFontAttributeName,
            NSForegroundColorAttributeName, NSImage,
            NSParagraphStyleAttributeName, NSScreen,
            NSTrackingActiveAlways, NSTrackingArea,
            NSTrackingInVisibleRect, NSTrackingMouseMoved,
            NSView, NSWindow,
        )
        from Foundation import (
            NSAttributedString, NSDictionary, NSMakeRect, NSMakeSize,
            NSMutableParagraphStyle, NSZeroRect,
        )
        from Quartz import (
            CGRectInfinite, CGWindowListCopyWindowInfo,
            CGWindowListCreateImage, kCGNullWindowID,
            kCGWindowImageDefault, kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )
        from Quartz.CoreGraphics import (
            CGImageGetHeight, CGImageGetWidth,
            CGPreflightScreenCaptureAccess, CGRequestScreenCaptureAccess,
        )
    except ImportError:
        logger.warning("PyObjC 未安装，无法使用屏幕区域选择")
        return None

    # ── 权限检查 ──
    try:
        if not CGPreflightScreenCaptureAccess():
            CGRequestScreenCaptureAccess()
            logger.warning("需要屏幕录制权限，请在「系统设置 → 隐私与安全性 → 屏幕录制」中授权后重试")
            return None
    except Exception:
        pass

    # ── 辅助函数 ──
    def _get_all_screens_frame():
        screens = NSScreen.screens()
        if not screens:
            f = NSScreen.mainScreen().frame()
            return (f.origin.x, f.origin.y, f.size.width, f.size.height)
        min_x = min(s.frame().origin.x for s in screens)
        min_y = min(s.frame().origin.y for s in screens)
        max_x = max(s.frame().origin.x + s.frame().size.width for s in screens)
        max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
        return (min_x, min_y, max_x - min_x, max_y - min_y)

    def _get_screen_rects_display():
        primary_h = NSScreen.mainScreen().frame().size.height
        result = []
        for s in NSScreen.screens():
            f = s.frame()
            x, w, h = int(f.origin.x), int(f.size.width), int(f.size.height)
            y = int(primary_h - f.origin.y - h)
            result.append((x, y, w, h))
        return result

    def _enum_windows_mac():
        info_list = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
            kCGNullWindowID,
        )
        if not info_list:
            return []
        windows = []
        for info in info_list:
            if info.get("kCGWindowLayer", -1) != 0:
                continue
            bounds = info.get("kCGWindowBounds")
            if not bounds:
                continue
            name = info.get("kCGWindowName", "") or info.get("kCGWindowOwnerName", "")
            if not name:
                continue
            x, y = int(bounds.get("X", 0)), int(bounds.get("Y", 0))
            w, h = int(bounds.get("Width", 0)), int(bounds.get("Height", 0))
            if w >= 50 and h >= 50:
                windows.append((name, x, y, w, h))
        return windows

    # ── NSWindow 子类（无边框窗口需要接收键盘） ──
    class KeyableWindow(NSWindow):
        def canBecomeKeyWindow(self):
            return True

    # ── NSView 子类 ──
    class SelectorView(NSView):
        def initWithFrame_data_(self, frame, data):
            self = objc.super(SelectorView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._original = data["original"]
            self._darkened = data["darkened"]
            self._img_w = data["img_w"]
            self._img_h = data["img_h"]
            self._windows = data["windows"]
            self._monitors = data["monitors"]
            self._hint_main = data.get("hint_main", "")
            self._hint_sub = data.get("hint_sub", "")
            self._return_title = data.get("return_title", False)
            self._dragging = False
            self._start_x = self._start_y = 0.0
            self._cur_x = self._cur_y = 0.0
            self._hover_window = None
            self._hover_monitor = None
            self._cur_monitor = 0
            self.result = None
            tracking = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.bounds(),
                NSTrackingMouseMoved | NSTrackingActiveAlways | NSTrackingInVisibleRect,
                self, None,
            )
            self.addTrackingArea_(tracking)
            return self

        def acceptsFirstResponder(self):
            return True

        def resetCursorRects(self):
            self.addCursorRect_cursor_(self.bounds(), NSCursor.crosshairCursor())

        @objc.python_method
        def _d2c(self, dx, dy, dw, dh):
            return NSMakeRect(dx, self._img_h - dy - dh, dw, dh)

        @objc.python_method
        def _mouse_to_display(self, event):
            pt = self.convertPoint_fromView_(event.locationInWindow(), None)
            return (pt.x, self._img_h - pt.y)

        def drawRect_(self, dirty):
            full = NSMakeRect(0, 0, self._img_w, self._img_h)
            self._darkened.drawInRect_fromRect_operation_fraction_(
                full, NSZeroRect, NSCompositingOperationCopy, 1.0,
            )
            title_text = ""
            if self._dragging:
                x1 = min(self._start_x, self._cur_x)
                y1 = min(self._start_y, self._cur_y)
                x2 = max(self._start_x, self._cur_x)
                y2 = max(self._start_y, self._cur_y)
                sw, sh = x2 - x1, y2 - y1
                if sw > 0 and sh > 0:
                    self._draw_highlight(x1, y1, sw, sh,
                                         NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.42, 0.42, 1.0))
                    self._draw_size_label(x1, y1, sw, sh)
                title_text = "拖拽选择区域..."
            else:
                if self._hover_window:
                    t, wx, wy, ww, wh = self._hover_window
                    self._draw_highlight(wx, wy, ww, wh,
                                         NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.75, 1.0, 1.0))
                    display = t[:50] + "..." if len(t) > 50 else t
                    title_text = f"\U0001f5a5 {display}"
                elif self._hover_monitor:
                    idx, mx, my, mw, mh = self._hover_monitor
                    self._draw_highlight(mx, my, mw, mh,
                                         NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.42, 0.42, 1.0))
                    title_text = f"\U0001f5a5 屏幕 {idx + 1} ({mw}×{mh})"
            self._draw_hint(title_text)

        @objc.python_method
        def _draw_highlight(self, dx, dy, dw, dh, border_color):
            cocoa_rect = self._d2c(dx, dy, dw, dh)
            self._original.drawInRect_fromRect_operation_fraction_(
                cocoa_rect, cocoa_rect, NSCompositingOperationSourceOver, 1.0,
            )
            border_color.setStroke()
            path = NSBezierPath.bezierPathWithRect_(cocoa_rect)
            path.setLineWidth_(3.0)
            path.stroke()

        @objc.python_method
        def _draw_hint(self, title_text):
            if self._cur_monitor < len(self._monitors):
                mx, _, mw, _ = self._monitors[self._cur_monitor]
            else:
                mx, mw = 0, self._img_w
            cx = mx + mw / 2
            box_dw, box_dh = 480, 70
            box_dx = cx - box_dw / 2
            box_dy = 25
            box_cocoa = self._d2c(box_dx, box_dy, box_dw, box_dh)
            NSColor.colorWithCalibratedWhite_alpha_(0.1, 0.85).setFill()
            bg_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(box_cocoa, 8, 8)
            bg_path.fill()
            NSColor.colorWithCalibratedWhite_alpha_(0.3, 1.0).setStroke()
            bg_path.setLineWidth_(1.0)
            bg_path.stroke()
            bx, by = box_cocoa.origin.x, box_cocoa.origin.y
            bw, bh = box_cocoa.size.width, box_cocoa.size.height
            self._draw_text(self._hint_main,
                            NSMakeRect(bx, by + bh / 2 + 2, bw, bh / 2 - 4),
                            size=16, bold=True, color=NSColor.whiteColor())
            self._draw_text(self._hint_sub,
                            NSMakeRect(bx, by + 4, bw, bh / 2 - 4),
                            size=13, bold=False,
                            color=NSColor.colorWithCalibratedWhite_alpha_(0.55, 1.0))
            if title_text:
                title_cocoa = self._d2c(cx - 300, box_dy + box_dh + 8, 600, 24)
                self._draw_text(title_text, title_cocoa, size=14, bold=False,
                                color=NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.75, 1.0, 1.0))

        @objc.python_method
        def _draw_size_label(self, dx, dy, dw, dh):
            label = f"{int(dw)} × {int(dh)}"
            lx, ly = dx, dy + dh + 4
            if ly + 22 > self._img_h:
                ly = dy - 22
            label_w = len(label) * 9 + 16
            label_cocoa = self._d2c(lx, ly, label_w, 20)
            NSColor.colorWithCalibratedWhite_alpha_(0.12, 0.85).setFill()
            NSBezierPath.fillRect_(label_cocoa)
            self._draw_text(label, label_cocoa, size=12, bold=False,
                            color=NSColor.colorWithCalibratedWhite_alpha_(0.8, 1.0))

        @staticmethod
        def _draw_text(text, rect, size=14, bold=False, color=None):
            if color is None:
                color = NSColor.whiteColor()
            font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
            para = NSMutableParagraphStyle.alloc().init()
            para.setAlignment_(1)
            attrs = NSDictionary.dictionaryWithObjects_forKeys_(
                [font, color, para],
                [NSFontAttributeName, NSForegroundColorAttributeName, NSParagraphStyleAttributeName],
            )
            NSAttributedString.alloc().initWithString_attributes_(text, attrs).drawInRect_(rect)

        @objc.python_method
        def _find_window_at(self, x, y):
            for w in self._windows:
                title, wx, wy, ww, wh = w
                if wx <= x <= wx + ww and wy <= y <= wy + wh:
                    return w
            return None

        @objc.python_method
        def _find_monitor_at(self, x, y):
            for i, (mx, my, mw, mh) in enumerate(self._monitors):
                if mx <= x <= mx + mw and my <= y <= my + mh:
                    return i, (mx, my, mw, mh)
            return 0, (0, 0, self._img_w, self._img_h)

        @objc.python_method
        def _update_hover(self, dx, dy):
            changed = False
            idx, _ = self._find_monitor_at(dx, dy)
            if self._cur_monitor != idx:
                self._cur_monitor = idx
                changed = True
            win = self._find_window_at(dx, dy)
            if win != self._hover_window:
                self._hover_window = win
                changed = True
            if win:
                if self._hover_monitor is not None:
                    self._hover_monitor = None
                    changed = True
            else:
                mid, mrect = self._find_monitor_at(dx, dy)
                new_mon = (mid, *mrect)
                if self._hover_monitor != new_mon:
                    self._hover_monitor = new_mon
                    changed = True
            return changed

        def mouseDown_(self, event):
            dx, dy = self._mouse_to_display(event)
            self._start_x = self._cur_x = dx
            self._start_y = self._cur_y = dy
            self._dragging = True
            self.setNeedsDisplay_(True)

        def mouseDragged_(self, event):
            if self._dragging:
                self._cur_x, self._cur_y = self._mouse_to_display(event)
                self.setNeedsDisplay_(True)

        def mouseUp_(self, event):
            if not self._dragging:
                return
            self._dragging = False
            ex, ey = self._mouse_to_display(event)
            x1, y1 = int(min(self._start_x, ex)), int(min(self._start_y, ey))
            x2, y2 = int(max(self._start_x, ex)), int(max(self._start_y, ey))
            w, h = x2 - x1, y2 - y1
            if w >= 10 and h >= 10:
                self.result = (x1, y1, w, h)
                self._finish()
            elif self._hover_window:
                t, wx, wy, ww, wh = self._hover_window
                if self._return_title:
                    self.result = (wx, wy, ww, wh, t)
                else:
                    self.result = (wx, wy, ww, wh)
                self._finish()
            elif self._hover_monitor:
                _, mx, my, mw, mh = self._hover_monitor
                self.result = (mx, my, mw, mh)
                self._finish()
            else:
                self.setNeedsDisplay_(True)

        def mouseMoved_(self, event):
            dx, dy = self._mouse_to_display(event)
            if self._update_hover(dx, dy):
                self.setNeedsDisplay_(True)

        def keyDown_(self, event):
            key = event.keyCode()
            chars = event.charactersIgnoringModifiers() or ""
            if key == 53:  # ESC
                self.result = None
                self._finish()
            elif chars.lower() == "f" or key == 36:
                idx = self._cur_monitor
                if idx < len(self._monitors):
                    self.result = self._monitors[idx]
                else:
                    self.result = (0, 0, self._img_w, self._img_h)
                self._finish()

        @objc.python_method
        def _finish(self):
            self.window().orderOut_(None)
            NSApp.stop_(None)
            dummy = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                15, NSMakeRect(0, 0, 0, 0).origin, 0, 0, 0, None, 0, 0, 0,
            )
            NSApp.postEvent_atStart_(dummy, True)

    # ── 主逻辑 ──
    cg_image = CGWindowListCreateImage(
        CGRectInfinite, kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID, kCGWindowImageDefault,
    )
    if not cg_image:
        logger.error("CGWindowListCreateImage 失败")
        return None

    all_frame = _get_all_screens_frame()
    point_w, point_h = all_frame[2], all_frame[3]

    original = NSImage.alloc().initWithCGImage_size_(
        cg_image, NSMakeSize(point_w, point_h)
    )
    darkened = NSImage.alloc().initWithSize_(NSMakeSize(point_w, point_h))
    darkened.lockFocus()
    original.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, point_w, point_h), NSZeroRect,
        NSCompositingOperationCopy, 1.0,
    )
    NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.5).setFill()
    NSBezierPath.fillRect_(NSMakeRect(0, 0, point_w, point_h))
    darkened.unlockFocus()

    windows = _enum_windows_mac()
    monitors = _get_screen_rects_display()
    logger.debug("屏幕选择器: %d 个窗口, %d 个显示器", len(windows), len(monitors))

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(0)

    cocoa_frame = NSMakeRect(*all_frame)
    window = KeyableWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        cocoa_frame, 0, 2, False,
    )
    window.setLevel_(1000)
    window.setOpaque_(True)
    window.setHasShadow_(False)
    window.setBackgroundColor_(NSColor.blackColor())
    window.setCollectionBehavior_(1 << 4)

    data = {
        "original": original, "darkened": darkened,
        "img_w": int(point_w), "img_h": int(point_h),
        "windows": windows, "monitors": monitors,
        "hint_main": hint_main, "hint_sub": hint_sub,
        "return_title": return_window_title,
    }
    view_frame = NSMakeRect(0, 0, cocoa_frame.size.width, cocoa_frame.size.height)
    view = SelectorView.alloc().initWithFrame_data_(view_frame, data)
    window.setContentView_(view)
    window.makeKeyAndOrderFront_(None)
    window.makeFirstResponder_(view)
    app.activateIgnoringOtherApps_(True)
    app.run()

    result = view.result
    window.orderOut_(None)
    window.close()

    # 点坐标 → 像素坐标
    if result:
        scale = NSScreen.mainScreen().backingScaleFactor()
        if len(result) == 5:
            x, y, w, h, title = result
            result = (int(x * scale), int(y * scale), int(w * scale), int(h * scale), title)
        else:
            x, y, w, h = result
            result = (int(x * scale), int(y * scale), int(w * scale), int(h * scale))

    return result
