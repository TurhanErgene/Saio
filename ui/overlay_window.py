from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QCursor


class OverlayWindow(QWidget):
    region_selected = pyqtSignal(tuple)

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.start_pos = None
        self.end_pos = None
        self.overlay_rect = None

        # --- IMPORTANT: no transparency yet, just visible window ---
        self.setWindowTitle("OverlayWindow DEBUG")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: rgba(50, 50, 50, 180);")
        self.setCursor(QCursor(Qt.CrossCursor))

    def mousePressEvent(self, event):
        self.start_pos = event.pos()
        self.end_pos = None
        self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start_pos and self.end_pos:
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = self.end_pos.x(), self.end_pos.y()
            rect = QRect(min(x1, x2), min(y1, y2),
                         abs(x2 - x1), abs(y2 - y1))
            print("Region selected:", rect)
            self.region_selected.emit(
                (rect.x(), rect.y(), rect.width(), rect.height())
            )
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.start_pos and self.end_pos:
            painter.setBrush(QColor(0, 120, 255, 60))
            painter.setPen(QColor(0, 120, 255, 200))
            painter.drawRect(QRect(self.start_pos, self.end_pos))
