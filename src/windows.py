import ctypes
import sys
from ctypes import wintypes
from pathlib import Path
import subprocess


if sys.platform == "win32":
    import winreg

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetShellWindow.restype = wintypes.HWND
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MonitorInfo))


def fullscreen_on_pet_monitor(pet_hwnd):
    if sys.platform != "win32":
        return False
    window = user32.GetForegroundWindow()
    if not window or window in (pet_hwnd, user32.GetShellWindow()):
        return False
    name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(window, name, len(name))
    if name.value in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
        return False
    monitor = user32.MonitorFromWindow(window, 2)
    if not monitor or monitor != user32.MonitorFromWindow(pet_hwnd, 2):
        return False
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    rect = wintypes.RECT()
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    if not user32.GetWindowRect(window, ctypes.byref(rect)):
        return False
    bounds = info.monitor
    return (rect.left <= bounds.left and rect.top <= bounds.top
            and rect.right >= bounds.right and rect.bottom >= bounds.bottom)


def sync_startup(enabled):
    if sys.platform != "win32":
        return
    args = [sys.executable]
    if not getattr(sys, "frozen", False):
        windowless = Path(sys.executable).with_name("pythonw.exe")
        if windowless.exists():
            args[0] = str(windowless)
        args.append(str(Path(__file__).resolve().parents[1] / "main.py"))
    command = subprocess.list2cmdline(args)
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "PikachuDesktopPet", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "PikachuDesktopPet")
            except FileNotFoundError:
                pass
