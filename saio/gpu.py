"""Keep Saio on the GPU that drives the displays.

On hybrid-graphics laptops (e.g. AMD/Intel iGPU + NVIDIA dGPU) the Magnification
API renders pure black when our process runs on a different GPU than the one the
monitors are connected to. Windows lets every executable choose a GPU through the
per-user "Graphics settings" list (UserGpuPreferences), and the choice is read
when DirectX first starts in the process – so we set it before MagInitialize(),
verify with a probe that the magnifier really renders, and if it doesn't, flip
the preference and restart once.
"""
import ctypes
import re
import sys
import winreg
from ctypes import wintypes

KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
POWER_SAVING, HIGH_PERFORMANCE = 1, 2
RETRY_FLAG = "--gpu-retry"

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
PW_RENDERFULLCONTENT = 2


def executable():
    # a venv's python.exe only relaunches the base interpreter – the GPU is chosen for that one
    return getattr(sys, "_base_executable", None) or sys.executable


def get_preference():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            value, _ = winreg.QueryValueEx(key, executable())
    except OSError:
        return None
    match = re.search(r"GpuPreference=(\d+)", value)
    return int(match.group(1)) if match else None


def set_preference(pref):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        winreg.SetValueEx(key, executable(), 0, winreg.REG_SZ, f"GpuPreference={pref};")


def prepare():
    """Call before MagInitialize(). Default to the power-saving GPU, which drives
    the displays on most hybrid laptops; probe() corrects it if that's wrong."""
    if get_preference() not in (POWER_SAVING, HIGH_PERFORMANCE):
        set_preference(POWER_SAVING)


def other_preference():
    return HIGH_PERFORMANCE if get_preference() == POWER_SAVING else POWER_SAVING


def window_has_content(hwnd, width, height):
    """True if the window renders anything but black (a broken magnifier is solid black)."""
    screen = user32.GetDC(None)
    dc = gdi32.CreateCompatibleDC(screen)
    bmp = gdi32.CreateCompatibleBitmap(screen, width, height)
    old = gdi32.SelectObject(dc, bmp)
    try:
        user32.PrintWindow(hwnd, dc, PW_RENDERFULLCONTENT)
        for i in range(1, 8):
            for j in range(1, 8):
                c = gdi32.GetPixel(dc, width * i // 8, height * j // 8)
                if c != 0xFFFFFFFF and max(c & 255, (c >> 8) & 255, (c >> 16) & 255) > 24:
                    return True
        return False
    finally:
        gdi32.SelectObject(dc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, screen)
