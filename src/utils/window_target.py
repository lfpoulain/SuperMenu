"""Capture and verify the exact Windows control targeted by a paste."""

from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from ctypes import wintypes

import win32con
import win32gui
import win32process


class _GuiThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def _focused_control(thread_id: int) -> int | None:
    info = _GuiThreadInfo()
    info.cbSize = ctypes.sizeof(_GuiThreadInfo)
    if not ctypes.windll.user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return None
    return int(info.hwndFocus) if info.hwndFocus else None


@dataclass(frozen=True)
class PasteTarget:
    foreground_hwnd: int
    process_id: int
    focus_hwnd: int | None = None

    @classmethod
    def capture(cls, *, allow_current_process=False):
        try:
            hwnd = int(win32gui.GetForegroundWindow() or 0)
            if not hwnd or not win32gui.IsWindow(hwnd):
                return None
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if not allow_current_process and process_id == os.getpid():
                return None
            return cls(
                foreground_hwnd=hwnd,
                process_id=int(process_id),
                focus_hwnd=_focused_control(int(thread_id)),
            )
        except Exception:
            return None

    def activate_and_verify(self) -> bool:
        """Activate the captured window and reject any changed focus control."""
        try:
            if not win32gui.IsWindow(self.foreground_hwnd):
                return False
            thread_id, process_id = win32process.GetWindowThreadProcessId(
                self.foreground_hwnd
            )
            if int(process_id) != self.process_id:
                return False

            if win32gui.IsIconic(self.foreground_hwnd):
                win32gui.ShowWindow(self.foreground_hwnd, win32con.SW_RESTORE)
            if int(win32gui.GetForegroundWindow() or 0) != self.foreground_hwnd:
                win32gui.SetForegroundWindow(self.foreground_hwnd)
                time.sleep(0.05)
            if int(win32gui.GetForegroundWindow() or 0) != self.foreground_hwnd:
                return False

            if self.focus_hwnd is not None:
                if not win32gui.IsWindow(self.focus_hwnd):
                    return False
                if _focused_control(int(thread_id)) != self.focus_hwnd:
                    return False
            return True
        except Exception:
            return False
