from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import sys


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds() -> float:
    """Seconds since last mouse/keyboard input. 0 if the OS call fails."""
    if sys.platform != "win32":
        return 0.0
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    get_tick = ctypes.windll.kernel32.GetTickCount
    get_tick.restype = wintypes.DWORD
    millis = (int(get_tick()) - int(info.dwTime)) & 0xFFFFFFFF
    return millis / 1000.0


def pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
    )
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def terminate_pid(pid: int | None) -> None:
    if not pid or not pid_running(pid):
        return
    if sys.platform == "win32":
        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
        return
    os.kill(pid, 15)
