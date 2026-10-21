"""Thin ctypes bindings for the Win32 + Magnification APIs Saio relies on.

The Magnification API is what makes real color filtering possible: instead of
painting a semi-transparent color *over* the screen (which hides what's behind
it), a magnifier control renders a live copy of the screen underneath it with a
5x5 color matrix applied, so content stays fully visible.
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    _mag = ctypes.WinDLL("Magnification", use_last_error=True)
except OSError:  # pragma: no cover - only on stripped-down Windows builds
    _mag = None

LONG_PTR = ctypes.c_ssize_t

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CLIPCHILDREN = 0x02000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x2
SW_HIDE = 0
SW_SHOWNA = 8
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
MW_FILTERMODE_EXCLUDE = 0
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000


class MAGTRANSFORM(ctypes.Structure):
    _fields_ = [("v", ctypes.c_float * 9)]


class MAGCOLOREFFECT(ctypes.Structure):
    _fields_ = [("transform", ctypes.c_float * 25)]


user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT]
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.MoveWindow.argtypes = [wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.BOOL]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

if _mag is not None:
    _mag.MagInitialize.restype = wintypes.BOOL
    _mag.MagUninitialize.restype = wintypes.BOOL
    _mag.MagSetWindowSource.argtypes = [wintypes.HWND, wintypes.RECT]
    _mag.MagSetWindowTransform.argtypes = [wintypes.HWND, ctypes.POINTER(MAGTRANSFORM)]
    _mag.MagSetColorEffect.argtypes = [wintypes.HWND, ctypes.POINTER(MAGCOLOREFFECT)]
    _mag.MagSetWindowFilterList.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_int, ctypes.POINTER(wintypes.HWND)]
    _mag.MagSetFullscreenColorEffect.argtypes = [ctypes.POINTER(MAGCOLOREFFECT)]


# --- Window style helpers ---------------------------------------------------

def update_style(hwnd, add=0, remove=0, ex=False):
    index = GWL_EXSTYLE if ex else GWL_STYLE
    style = user32.GetWindowLongPtrW(hwnd, index)
    user32.SetWindowLongPtrW(hwnd, index, (style | add) & ~remove)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)


def set_window_alpha(hwnd, alpha):
    user32.SetLayeredWindowAttributes(hwnd, 0, max(0, min(255, int(alpha))), LWA_ALPHA)


def move_window(hwnd, x, y, w, h):
    user32.MoveWindow(hwnd, x, y, w, h, True)


def show_window(hwnd, visible):
    user32.ShowWindow(hwnd, SW_SHOWNA if visible else SW_HIDE)


def window_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect


# --- Magnification ----------------------------------------------------------

def mag_initialize():
    return _mag is not None and bool(_mag.MagInitialize())


def mag_uninitialize():
    if _mag is not None:
        _mag.MagUninitialize()


def create_magnifier(parent_hwnd, width, height):
    """Create a 1:1 magnifier control filling `parent_hwnd`'s client area."""
    hwnd = user32.CreateWindowExW(
        0, "Magnifier", "SaioMagnifier", WS_CHILD | WS_VISIBLE,
        0, 0, width, height, parent_hwnd, None, kernel32.GetModuleHandleW(None), None,
    )
    if not hwnd:
        raise OSError(ctypes.get_last_error(), "Could not create magnifier control")
    identity = MAGTRANSFORM((ctypes.c_float * 9)(1, 0, 0, 0, 1, 0, 0, 0, 1))
    _mag.MagSetWindowTransform(hwnd, ctypes.byref(identity))
    return hwnd


def _color_effect(matrix):
    return MAGCOLOREFFECT((ctypes.c_float * 25)(*matrix))


def set_color_effect(mag_hwnd, matrix):
    _mag.MagSetColorEffect(mag_hwnd, ctypes.byref(_color_effect(matrix)))


def set_fullscreen_color_effect(matrix):
    return bool(_mag.MagSetFullscreenColorEffect(ctypes.byref(_color_effect(matrix))))


def set_excluded_windows(mag_hwnd, hwnds):
    """Keep our own overlay windows out of what the magnifier captures."""
    arr = (wintypes.HWND * max(1, len(hwnds)))(*hwnds)
    _mag.MagSetWindowFilterList(mag_hwnd, MW_FILTERMODE_EXCLUDE, len(hwnds), arr)


def refresh_magnifier(mag_hwnd):
    """Point the magnifier at the screen area directly beneath it and repaint."""
    _mag.MagSetWindowSource(mag_hwnd, window_rect(mag_hwnd))
    user32.InvalidateRect(mag_hwnd, None, True)


# --- Window discovery & tracking (per-app filters) --------------------------

dwmapi = ctypes.WinDLL("dwmapi")
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GW_HWNDPREV = 3
WS_EX_TOPMOST = 0x00000008
HWND_TOP, HWND_TOPMOST, HWND_NOTOPMOST = 0, -1, -2
SWP_NOOWNERZORDER = 0x200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
for _name in ("IsWindow", "IsWindowVisible", "IsIconic"):
    getattr(user32, _name).argtypes = [wintypes.HWND]
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
OWN_PID = kernel32.GetCurrentProcessId()


def top_level_windows():
    """All top-level windows, front to back (z-order)."""
    found = []
    cb = WNDENUMPROC(lambda hwnd, _: found.append(hwnd) or True)
    user32.EnumWindows(cb, 0)
    return found


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_path(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        return buf.value if ok else None
    finally:
        kernel32.CloseHandle(handle)


def window_title(hwnd):
    buf = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def is_cloaked(hwnd):
    """Windows on other virtual desktops / suspended UWP apps are 'cloaked': visible but not shown."""
    cloaked = wintypes.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return bool(cloaked.value)


def is_topmost(hwnd):
    return bool(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)


def visible_bounds(hwnd):
    """Window rect without the invisible resize borders / drop shadow."""
    rect = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)):
        return window_rect(hwnd)
    return rect


def is_on_screen(hwnd):
    return bool(user32.IsWindowVisible(hwnd)) and not user32.IsIconic(hwnd) and not is_cloaked(hwnd)


def is_app_window(hwnd):
    """A real, visible application window (not ours, not a tooltip/menu/shell surface)."""
    if not is_on_screen(hwnd) or window_pid(hwnd) == OWN_PID:
        return False
    if user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False
    if window_class(hwnd) in SHELL_CLASSES:
        return False
    r = visible_bounds(hwnd)
    return r.right - r.left >= 40 and r.bottom - r.top >= 40


def window_above(hwnd):
    return user32.GetWindow(hwnd, GW_HWNDPREV)


def place_window(hwnd, insert_after, x, y, w, h, zorder=True):
    flags = SWP_NOACTIVATE | SWP_NOOWNERZORDER | (0 if zorder else SWP_NOZORDER)
    user32.SetWindowPos(hwnd, insert_after, x, y, w, h, flags)
