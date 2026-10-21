"""A screen region that shows the content beneath it through a color filter."""
from PyQt5.QtCore import QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QMenu, QWidget

from . import winapi
from .theme import ACCENT

EDGE_MARGIN = 10
REFRESH_MS = 16  # ~60 fps


class FilterRegion(QWidget):
    """Frameless, always-on-top window hosting a Magnification API control.

    Normal mode: click-through, shows the live filtered screen.
    Edit mode:   semi-transparent frame you can drag to move or resize.
    """
    removeRequested = pyqtSignal(object)
    editFinished = pyqtSignal()
    geometryEdited = pyqtSignal()

    def __init__(self, rect: QRect, matrix, topmost=True):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if topmost:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(rect)
        self.setMouseTracking(True)
        self._matrix = matrix
        self._excluded = []
        self._editing = False
        self._mag = None
        self._timer = QTimer(self, interval=REFRESH_MS, timeout=self._refresh)

    # --- native setup ---

    @property
    def hwnd(self):
        return int(self.winId())

    def _ensure_native(self):
        if self._mag:
            return
        hwnd = self.hwnd
        winapi.update_style(hwnd, add=winapi.WS_CLIPCHILDREN)
        winapi.update_style(hwnd, ex=True, add=winapi.WS_EX_LAYERED | winapi.WS_EX_TOOLWINDOW | winapi.WS_EX_NOACTIVATE)
        winapi.set_window_alpha(hwnd, 255)
        self._mag = winapi.create_magnifier(hwnd, *self._physical_size())
        winapi.set_color_effect(self._mag, self._matrix)
        winapi.set_excluded_windows(self._mag, self._excluded or [hwnd])
        self._apply_mode()

    def _physical_size(self):
        ratio = self.devicePixelRatioF()
        return round(self.width() * ratio), round(self.height() * ratio)

    def _refresh(self):
        if self._mag and not self._editing:
            winapi.refresh_magnifier(self._mag)

    # --- public API ---

    def set_matrix(self, matrix):
        self._matrix = matrix
        if self._mag:
            winapi.set_color_effect(self._mag, matrix)

    def set_excluded(self, hwnds):
        self._excluded = list(hwnds)
        if self._mag:
            winapi.set_excluded_windows(self._mag, self._excluded)

    def is_editing(self):
        return self._editing

    def set_editing(self, editing: bool):
        if editing == self._editing:
            return
        self._editing = editing
        if self._mag:
            self._apply_mode()
        self.update()

    def _apply_mode(self):
        hwnd = self.hwnd
        if self._editing:
            winapi.show_window(self._mag, False)
            winapi.update_style(hwnd, ex=True, remove=winapi.WS_EX_TRANSPARENT)
            winapi.set_window_alpha(hwnd, 170)
        else:
            winapi.move_window(self._mag, 0, 0, *self._physical_size())
            winapi.update_style(hwnd, ex=True, add=winapi.WS_EX_TRANSPARENT)
            winapi.set_window_alpha(hwnd, 255)
            winapi.show_window(self._mag, True)
            self._refresh()

    # --- Qt events ---

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_native()
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._mag and not self._editing:
            winapi.move_window(self._mag, 0, 0, *self._physical_size())

    def paintEvent(self, event):
        if not self._editing:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        accent = QColor(ACCENT)
        p.fillRect(self.rect(), QColor(20, 22, 28))
        fill = QColor(accent)
        fill.setAlpha(40)
        p.fillRect(self.rect(), fill)
        pen = QPen(accent, 2, Qt.DashLine)
        p.setPen(pen)
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))
        # corner handles
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        for x in (0, self.width() - 8):
            for y in (0, self.height() - 8):
                p.drawRect(x, y, 8, 8)
        p.setPen(QColor("#f2f2f5"))
        f = QFont(self.font())
        f.setPointSize(10)
        p.setFont(f)
        text = (f"{self.width()} × {self.height()}\n"
                "Drag to move · drag edges to resize\nDouble-click when done · right-click to remove")
        p.drawText(self.rect(), Qt.AlignCenter, text)

    def _edges_at(self, pos):
        edges = Qt.Edges()
        if pos.x() < EDGE_MARGIN:
            edges |= Qt.LeftEdge
        elif pos.x() > self.width() - EDGE_MARGIN:
            edges |= Qt.RightEdge
        if pos.y() < EDGE_MARGIN:
            edges |= Qt.TopEdge
        elif pos.y() > self.height() - EDGE_MARGIN:
            edges |= Qt.BottomEdge
        return edges

    _CURSORS = {
        int(Qt.LeftEdge): Qt.SizeHorCursor, int(Qt.RightEdge): Qt.SizeHorCursor,
        int(Qt.TopEdge): Qt.SizeVerCursor, int(Qt.BottomEdge): Qt.SizeVerCursor,
        int(Qt.LeftEdge | Qt.TopEdge): Qt.SizeFDiagCursor, int(Qt.RightEdge | Qt.BottomEdge): Qt.SizeFDiagCursor,
        int(Qt.RightEdge | Qt.TopEdge): Qt.SizeBDiagCursor, int(Qt.LeftEdge | Qt.BottomEdge): Qt.SizeBDiagCursor,
    }

    def mouseMoveEvent(self, event):
        if self._editing:
            self.setCursor(self._CURSORS.get(int(self._edges_at(event.pos())), Qt.SizeAllCursor))

    def mousePressEvent(self, event):
        if not self._editing or event.button() != Qt.LeftButton:
            return
        edges = self._edges_at(event.pos())
        handle = self.windowHandle()
        if edges:
            handle.startSystemResize(edges)
        else:
            handle.startSystemMove()

    def mouseReleaseEvent(self, event):
        if self._editing:
            self.geometryEdited.emit()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._editing:
            self.geometryEdited.emit()

    def mouseDoubleClickEvent(self, event):
        if self._editing:
            self.editFinished.emit()

    def contextMenuEvent(self, event):
        if not self._editing:
            return
        menu = QMenu(self)
        menu.addAction("Done editing", self.editFinished.emit)
        menu.addAction("Remove this region", lambda: self.removeRequested.emit(self))
        menu.exec_(event.globalPos())
