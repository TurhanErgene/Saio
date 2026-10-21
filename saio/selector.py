"""Full-desktop rubber-band selector (spans every monitor)."""
from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

from .theme import ACCENT

MIN_SIZE = 20


class RegionSelector(QWidget):
    selected = pyqtSignal(QRect)   # global screen coordinates
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setMouseTracking(True)
        desktop = QRect()
        for screen in QGuiApplication.screens():
            desktop = desktop.united(screen.geometry())
        self.setGeometry(desktop)
        self._start = None
        self._end = None
        self._done = False

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _selection(self):
        if self._start is None or self._end is None:
            return QRect()
        x1, x2 = sorted((self._start.x(), self._end.x()))
        y1, y2 = sorted((self._start.y(), self._end.y()))
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._finish(None)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._finish(None)
        elif event.button() == Qt.LeftButton:
            self._start = self._end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._start is None:
            return
        self._end = event.pos()
        sel = self._selection()
        if sel.width() < MIN_SIZE or sel.height() < MIN_SIZE:
            self._start = self._end = None  # treat as a stray click
            self.update()
            return
        self._finish(sel.translated(self.geometry().topLeft()))

    def _finish(self, rect):
        if self._done:
            return
        self._done = True
        self.hide()
        if rect is None:
            self.cancelled.emit()
        else:
            self.selected.emit(rect)
        self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        sel = self._selection()

        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        if not sel.isNull():
            hole = QPainterPath()
            hole.addRect(QRectF(sel))
            shade = shade.subtracted(hole)
            # alpha 1, not 0: fully transparent pixels would let clicks fall through
            p.fillRect(sel, QColor(0, 0, 0, 1))
        p.fillPath(shade, QColor(8, 10, 14, 120))

        accent = QColor(ACCENT)
        if not sel.isNull():
            p.setPen(QPen(accent, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(sel)
            label = f"{sel.width()} × {sel.height()}"
            p.setFont(QFont(self.font().family(), 9, QFont.DemiBold))
            box = p.fontMetrics().boundingRect(label).adjusted(-8, -4, 8, 4)
            box.moveTopLeft(sel.bottomRight() - QPoint(box.width(), -6))
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor("#1a1b1f"))
            p.drawText(box, Qt.AlignCenter, label)

        # instructions at the top of the primary screen
        primary = QGuiApplication.primaryScreen().geometry().translated(-self.geometry().topLeft())
        p.setFont(QFont(self.font().family(), 11))
        hint = "Drag to select the area to filter  ·  Esc or right-click to cancel"
        box = p.fontMetrics().boundingRect(hint).adjusted(-16, -10, 16, 10)
        box.moveCenter(QPoint(primary.center().x(), primary.top() + 48))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(24, 26, 32, 230))
        p.drawRoundedRect(box, 10, 10)
        p.setPen(QColor("#f2f2f5"))
        p.drawText(box, Qt.AlignCenter, hint)
