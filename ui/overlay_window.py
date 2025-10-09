from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor

class OverlayWindow(QWidget):
    region_selected = pyqtSignal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_pos = None
        self.end_pos = None
        self.selection_done = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.overlay_rect = None

    def mousePressEvent(self, event):
        self.start_pos = event.pos()
        self.end_pos = None
        self.selection_done = False
        self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start_pos and self.end_pos:
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = self.end_pos.x(), self.end_pos.y()
            self.overlay_rect = QRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            self.region_selected.emit((self.overlay_rect.x(), self.overlay_rect.y(),
                                       self.overlay_rect.width(), self.overlay_rect.height()))
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.start_pos and self.end_pos:
            painter.setBrush(QColor(0, 120, 255, 50))
            painter.setPen(QColor(0, 120, 255, 200))
            painter.drawRect(QRect(self.start_pos, self.end_pos))

        if self.selection_done and self.overlay_rect:
            painter.setBrush(QColor(255, 200, 100, 100))
            painter.drawRect(self.overlay_rect)

    def show_overlay(self, region):
        x, y, w, h = region
        self.setGeometry(x, y, w, h)
        self.setWindowOpacity(0.4)
        self.setStyleSheet("background-color: rgba(255, 160, 100, 100);")
        self.show()
