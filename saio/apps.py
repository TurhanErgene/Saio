"""Per-app filters: a filter that follows every window of a chosen program."""
import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

from PyQt5.QtCore import QObject, QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

from . import winapi
from .region import FilterRegion
from .theme import ACCENT

SCAN_MS = 600   # look for new / closed windows of the chosen apps
POLL_MS = 100   # safety net; most movement is caught instantly via WinEvent hooks

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_SYSTEM_MINIMIZEEND = 0x0017
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
OBJID_WINDOW = 0

WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
                                  wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
winapi.user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
                                          wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
winapi.user32.SetWinEventHook.restype = wintypes.HANDLE
winapi.user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]


@dataclass(eq=False)
class AppRule:
    exe: str         # lower-case file name, e.g. "notepad.exe"
    path: str        # full path – used for the icon
    filter_key: str

    @property
    def name(self):
        stem = os.path.splitext(self.exe)[0]
        return stem[:1].upper() + stem[1:]

    def to_json(self):
        return {"exe": self.exe, "path": self.path, "filter": self.filter_key}

    @classmethod
    def from_json(cls, data):
        return cls(data["exe"].lower(), data.get("path", ""), data.get("filter", "warm"))


def rect_of(hwnd):
    r = winapi.visible_bounds(hwnd)
    return QRect(r.left, r.top, r.right - r.left, r.bottom - r.top)


class WindowFollower(FilterRegion):
    """A filter region glued to another app's window."""

    def __init__(self, target, rule, matrix):
        super().__init__(rect_of(target), matrix, topmost=False)
        self.target = target
        self.rule = rule
        self._last = None

    def track(self):
        """Cover the target exactly and sit directly above it in z-order, so windows
        in front of the target also stay in front of the filter."""
        r = winapi.visible_bounds(self.target)
        geom = (r.left, r.top, r.right - r.left, r.bottom - r.top)
        host = self.hwnd
        above = winapi.window_above(self.target)
        if above == host:
            if geom != self._last:
                winapi.place_window(host, None, *geom, zorder=False)
        else:
            target_topmost = winapi.is_topmost(self.target)
            if above is None:
                after = winapi.HWND_TOPMOST if target_topmost else winapi.HWND_NOTOPMOST
            elif winapi.is_topmost(above) and not target_topmost:
                after = winapi.HWND_NOTOPMOST  # top of the normal band = just above the target
            else:
                after = above
            winapi.place_window(host, after, *geom)
        self._last = geom


class AppFilterManager(QObject):
    hostsChanged = pyqtSignal()

    def __init__(self, matrix_for, parent=None):
        super().__init__(parent)
        self.rules = []
        self.followers = {}  # target hwnd -> WindowFollower
        self._matrix_for = matrix_for
        self._active = False
        self._hooks = []
        self._proc = WINEVENTPROC(self._on_win_event)  # keep a reference: ctypes callback
        self._scan_timer = QTimer(self, interval=SCAN_MS, timeout=self.scan)
        self._poll_timer = QTimer(self, interval=POLL_MS, timeout=self._track_all)

    # --- rules ---

    def rule_for(self, exe):
        return next((r for r in self.rules if r.exe == exe.lower()), None)

    def add_rule(self, rule):
        self.rules.append(rule)
        self.scan()

    def remove_rule(self, rule):
        self.rules.remove(rule)
        self.scan()

    def set_rule_filter(self, rule, key):
        rule.filter_key = key
        self.refresh_matrices()

    def refresh_matrices(self):
        for f in self.followers.values():
            f.set_matrix(self._matrix_for(f.rule.filter_key))

    def hosts(self):
        return [f.hwnd for f in self.followers.values()]

    # --- lifecycle ---

    def set_active(self, active):
        if active == self._active:
            return
        self._active = active
        if active:
            for lo, hi in ((EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_MINIMIZEEND),
                           (EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE)):
                hook = winapi.user32.SetWinEventHook(lo, hi, None, self._proc, 0, 0,
                                                     WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS)
                if hook:
                    self._hooks.append(hook)
            self._scan_timer.start()
            self._poll_timer.start()
        else:
            for hook in self._hooks:
                winapi.user32.UnhookWinEvent(hook)
            self._hooks.clear()
            self._scan_timer.stop()
            self._poll_timer.stop()
        self.scan()

    def shutdown(self):
        self.set_active(False)

    # --- tracking ---

    def scan(self):
        wanted = {}
        if self._active and self.rules:
            by_exe = {r.exe: r for r in self.rules}
            paths = {}
            for hwnd in winapi.top_level_windows():
                if not winapi.is_app_window(hwnd):
                    continue
                pid = winapi.window_pid(hwnd)
                if pid not in paths:
                    paths[pid] = winapi.process_path(pid)
                rule = paths[pid] and by_exe.get(os.path.basename(paths[pid]).lower())
                if rule:
                    wanted[hwnd] = rule

        changed = False
        for hwnd, follower in list(self.followers.items()):
            if wanted.get(hwnd) is not follower.rule:
                del self.followers[hwnd]
                follower.close()
                follower.deleteLater()
                changed = True
        for hwnd, rule in wanted.items():
            if hwnd not in self.followers:
                follower = WindowFollower(hwnd, rule, self._matrix_for(rule.filter_key))
                self.followers[hwnd] = follower
                follower.show()
                follower.track()
                changed = True
        if changed:
            self.hostsChanged.emit()

    def _track(self, follower):
        if not winapi.user32.IsWindow(follower.target):
            return  # gone – the next scan cleans it up
        on_screen = winapi.is_on_screen(follower.target)
        if on_screen != follower.isVisible():
            follower.setVisible(on_screen)
        if on_screen:
            follower.track()

    def _track_all(self):
        for follower in list(self.followers.values()):
            self._track(follower)

    def _on_win_event(self, hook, event, hwnd, id_object, id_child, thread, time):
        try:
            if id_object != OBJID_WINDOW or not hwnd:
                return
            follower = self.followers.get(hwnd)
            if follower is not None:
                self._track(follower)
            elif event == EVENT_SYSTEM_FOREGROUND:
                self._track_all()  # something came to front – re-check stacking
        except Exception as e:  # never let an exception escape into a Win32 callback
            print("Saio: window event error:", e)


class WindowPicker(QWidget):
    """Full-desktop overlay: hover highlights a window, click picks it."""
    picked = pyqtSignal(int, str)  # hwnd, exe path
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMouseTracking(True)
        desktop = QRect()
        for screen in QGuiApplication.screens():
            desktop = desktop.united(screen.geometry())
        self.setGeometry(desktop)
        self._windows = []  # front-to-back snapshot taken before we cover the screen
        for hwnd in winapi.top_level_windows():
            if winapi.is_app_window(hwnd):
                path = winapi.process_path(winapi.window_pid(hwnd))
                if path:
                    self._windows.append((hwnd, rect_of(hwnd), path, winapi.window_title(hwnd)))
        self._hover = None
        self._done = False

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._update_hover(QCursor.pos())

    def _update_hover(self, global_pos):
        self._hover = next((w for w in self._windows if w[1].contains(global_pos)), None)
        self.update()

    def mouseMoveEvent(self, event):
        self._update_hover(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._finish(None)
        elif event.button() == Qt.LeftButton and self._hover:
            self._finish(self._hover)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._finish(None)

    def _finish(self, window):
        if self._done:
            return
        self._done = True
        self.hide()
        if window is None:
            self.cancelled.emit()
        else:
            self.picked.emit(window[0], window[2])
        self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        accent = QColor(ACCENT)
        target = None
        if self._hover:
            target = self._hover[1].translated(-self.geometry().topLeft())
            hole = QPainterPath()
            hole.addRect(QRectF(target))
            shade = shade.subtracted(hole)
            p.fillRect(target, QColor(0, 0, 0, 1))  # alpha 1 keeps the area clickable
        p.fillPath(shade, QColor(8, 10, 14, 140))

        if target is not None:
            p.setPen(QPen(accent, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRect(target.adjusted(1, 1, -2, -2))
            name = os.path.splitext(os.path.basename(self._hover[2]))[0]
            title = self._hover[3]
            label = f"{name}  ·  {title}" if title else name
            p.setFont(QFont(self.font().family(), 10, QFont.DemiBold))
            label = p.fontMetrics().elidedText(label, Qt.ElideRight, 520)
            box = p.fontMetrics().boundingRect(label).adjusted(-12, -7, 12, 7)
            box.moveCenter(target.center())
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor("#1a1b1f"))
            p.drawText(box, Qt.AlignCenter, label)

        primary = QGuiApplication.primaryScreen().geometry().translated(-self.geometry().topLeft())
        p.setFont(QFont(self.font().family(), 11))
        hint = "Click a window to always filter that app  ·  Esc or right-click to cancel"
        box = p.fontMetrics().boundingRect(hint).adjusted(-16, -10, 16, 10)
        box.moveCenter(QPoint(primary.center().x(), primary.top() + 48))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(24, 26, 32, 235))
        p.drawRoundedRect(box, 10, 10)
        p.setPen(QColor("#f2f2f5"))
        p.drawText(box, Qt.AlignCenter, hint)
