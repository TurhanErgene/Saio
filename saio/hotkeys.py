"""System-wide keyboard shortcuts via RegisterHotKey."""
from ctypes import wintypes

from PyQt5.QtCore import QAbstractEventDispatcher, QAbstractNativeEventFilter

from . import winapi

MODIFIERS = {"ctrl": winapi.MOD_CONTROL, "alt": winapi.MOD_ALT, "shift": winapi.MOD_SHIFT}
KEYS = {"plus": 0xBB, "minus": 0xBD}


class GlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(self):
        super().__init__()
        self._callbacks = {}
        QAbstractEventDispatcher.instance().installNativeEventFilter(self)

    def register(self, combo: str, callback) -> bool:
        """`combo` like "ctrl+alt+f". Returns False if another app already owns it."""
        *mods, key = combo.lower().split("+")
        flags = winapi.MOD_NOREPEAT
        for m in mods:
            flags |= MODIFIERS[m]
        vk = KEYS.get(key) or ord(key.upper())
        hotkey_id = len(self._callbacks) + 1
        if not winapi.user32.RegisterHotKey(None, hotkey_id, flags, vk):
            return False
        self._callbacks[hotkey_id] = callback
        return True

    def unregister_all(self):
        for hotkey_id in self._callbacks:
            winapi.user32.UnregisterHotKey(None, hotkey_id)
        self._callbacks.clear()

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == winapi.WM_HOTKEY and msg.wParam in self._callbacks:
                self._callbacks[msg.wParam]()
                return True, 0
        return False, 0
