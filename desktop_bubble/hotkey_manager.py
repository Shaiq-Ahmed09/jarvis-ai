"""
J.A.R.V.I.S. Global Hotkey Manager (PySide6 QObject Bridge)
===========================================================
Registers:
1. 'Alt + Space' (Overlay Toggle / Focus) system-wide across Windows.
2. 'Ctrl + Shift + Space' (Selected Text / Clipboard Context Hook).
Bridges global keyboard events safely to the PySide6 main thread via Qt Signals.
Supports 'global-hotkeys' with automatic native Win32 RegisterHotKey fallback.
"""

import sys
import time
import ctypes
from ctypes import wintypes
import threading
from PySide6.QtCore import QObject, Signal


class Win32HotkeyFallback(threading.Thread):
    """Direct Win32 RegisterHotKey thread fallback for Windows 10/11."""
    def __init__(self, toggle_callback, clipboard_callback):
        super().__init__(daemon=True)
        self.toggle_callback = toggle_callback
        self.clipboard_callback = clipboard_callback
        self.running = False
        self.id_alt_space = 9991
        self.id_ctrl_shift_space = 9992
        self.thread_id = None

    def run(self):
        self.running = True
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()

        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_SHIFT = 0x0004
        MOD_NOREPEAT = 0x4000
        VK_SPACE = 0x20

        # Register 1: Alt + Space (Toggle Overlay)
        reg1 = user32.RegisterHotKey(0, self.id_alt_space, MOD_ALT | MOD_NOREPEAT, VK_SPACE)
        if not reg1:
            user32.RegisterHotKey(0, self.id_alt_space, MOD_ALT, VK_SPACE)

        # Register 2: Ctrl + Shift + Space (Clipboard Context)
        reg2 = user32.RegisterHotKey(0, self.id_ctrl_shift_space, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_SPACE)
        if not reg2:
            user32.RegisterHotKey(0, self.id_ctrl_shift_space, MOD_CONTROL | MOD_SHIFT, VK_SPACE)

        msg = wintypes.MSG()
        while self.running:
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):  # PM_REMOVE = 1
                if msg.message == 0x0312:  # WM_HOTKEY
                    if msg.wParam == self.id_alt_space and self.toggle_callback:
                        try:
                            self.toggle_callback()
                        except Exception as e:
                            print(f"[Hotkey Alt+Space Error]: {e}")
                    elif msg.wParam == self.id_ctrl_shift_space and self.clipboard_callback:
                        try:
                            self.clipboard_callback()
                        except Exception as e:
                            print(f"[Hotkey Ctrl+Shift+Space Error]: {e}")
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.015)

        user32.UnregisterHotKey(0, self.id_alt_space)
        user32.UnregisterHotKey(0, self.id_ctrl_shift_space)

    def stop(self):
        self.running = False


class HotkeyManager(QObject):
    """Thread-safe global hotkey manager emitting Qt Signals to the UI thread."""
    hotkey_triggered = Signal()       # Alt + Space
    clipboard_triggered = Signal()    # Ctrl + Shift + Space

    def __init__(self, key_combination: str = "Alt + Space"):
        super().__init__()
        self.key_combination = key_combination
        self._win32_fallback = None
        self._using_global_hotkeys = False
        self._start_listener()

    def _on_key_event(self):
        self.hotkey_triggered.emit()

    def _on_clipboard_event(self):
        self.clipboard_triggered.emit()

    def _start_listener(self):
        # Attempt 1: global-hotkeys package
        try:
            import global_hotkeys as gh
            bindings = [
                ["alt", "space", None, self._on_key_event],
                ["control", "shift", "space", None, self._on_clipboard_event],
            ]
            gh.register_hotkeys(bindings)
            gh.start_checking_hotkeys()
            self._using_global_hotkeys = True
            print(f"[HotkeyManager] Registered 'Alt + Space' and 'Ctrl + Shift + Space' via global-hotkeys.")
            return
        except Exception as e:
            print(f"[HotkeyManager] global-hotkeys notice ({e}), engaging Win32 fallback...")

        # Attempt 2: Direct Win32 RegisterHotKey
        try:
            self._win32_fallback = Win32HotkeyFallback(self._on_key_event, self._on_clipboard_event)
            self._win32_fallback.start()
            print(f"[HotkeyManager] Registered 'Alt + Space' and 'Ctrl + Shift + Space' via native Win32 API.")
        except Exception as e:
            print(f"[HotkeyManager] Failed to register global hotkeys: {e}")

    def stop(self):
        if self._using_global_hotkeys:
            try:
                import global_hotkeys as gh
                gh.stop_checking_hotkeys()
            except Exception:
                pass
        if self._win32_fallback:
            self._win32_fallback.stop()
