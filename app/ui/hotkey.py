"""Global Windows hotkey support."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
VK_J = 0x4A


class GlobalHotkey:
    """Register CTRL+SHIFT+J on Windows."""

    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self.thread = None
        self.thread_id = None

    def start(self):
        if self.running or not hasattr(ctypes, "windll"):
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread_id and hasattr(ctypes, "windll"):
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)

    def _run(self):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered = ctypes.windll.user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_SHIFT, VK_J)
        if not registered:
            return
        msg = wintypes.MSG()
        while self.running:
            result = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            if msg.message == WM_HOTKEY:
                self.callback()
        ctypes.windll.user32.UnregisterHotKey(None, 1)
