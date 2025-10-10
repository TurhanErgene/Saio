from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import QPainter, QColor, QCursor
import sys


class RegionOverlay(QWidget):
    """Tinted overlay over a specific region."""
    def __init__(self, x, y, w, h, color=(255, 170, 100), opacity=0.4):
        super().__init__()
        self.setGeometry(x, y, w, h)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        r, g, b = color
        a = int(opacity * 255)
        self.tint = QColor(r, g, b, a)

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), self.tint)


class RegionSelector(QWidget):
    """Fullscreen transparent overlay for selecting a region."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.start_pos = None
        self.end_pos = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CrossCursor))
        # Windows z-order nudge
        QTimer.singleShot(80, self._bring_to_front)

    def _bring_to_front(self):
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

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
            rect = QRect(
                min(self.start_pos.x(), self.end_pos.x()),
                min(self.start_pos.y(), self.end_pos.y()),
                abs(self.start_pos.x() - self.end_pos.x()),
                abs(self.start_pos.y() - self.end_pos.y())
            )
            print(f"Selected region: x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}")
            self.hide()
            self.callback(rect)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 50))  # dim screen
        if self.start_pos and self.end_pos:
            p.setBrush(QColor(0, 120, 255, 60))
            p.setPen(QColor(0, 120, 255, 200))
            p.drawRect(QRect(self.start_pos, self.end_pos))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eye Care")
        self.setFixedSize(200, 120)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout()
        self.select_button = QPushButton("Select Region")
        self.select_button.clicked.connect(self.select_region)
        layout.addWidget(self.select_button)
        self.setLayout(layout)

        self.selector = None   # keep references!
        self.overlay = None

    def select_region(self):
        print("Select region clicked")
        # ensure only one selector at a time
        if self.selector and self.selector.isVisible():
            self.selector.close()
        self.selector = RegionSelector(self.apply_eye_care)
        self.selector.show()   # _bring_to_front will make it fullscreen/top

    def apply_eye_care(self, rect):
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        print("Applying eye-care tint to:", rect)
        if self.overlay and self.overlay.isVisible():
            self.overlay.close()
        self.overlay = RegionOverlay(x, y, w, h)
        self.overlay.show()
        self.overlay.raise_()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
