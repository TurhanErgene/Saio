import sys
import ctypes
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtCore import Qt, QRect, QTimer, QPoint
from PyQt5.QtGui import QPainter, QColor, QCursor


# --- Windows API setup for true click-through ---
def set_click_through(hwnd, enable: bool):
    """Use Win32 API to make a window click-through."""
    try:
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x20
        WS_EX_LAYERED = 0x80000

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception as e:
        print("Click-through not supported:", e)


class RegionOverlay(QWidget):
    """Tinted overlay that can be moved or made click-through."""
    def __init__(self, x, y, w, h, color=(255, 170, 100), opacity=0.45):
        super().__init__()
        self.setGeometry(x, y, w, h)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.tint = QColor(*color, int(opacity * 255))

        self._dragging = False
        self._drag_start = QPoint()
        self._window_start = QPoint()

        self.pass_through = True
        QTimer.singleShot(100, self.enable_pass_through)

    def enable_pass_through(self):
        """Apply native click-through (Windows only)."""
        hwnd = int(self.winId())
        set_click_through(hwnd, True)

    def disable_pass_through(self):
        """Disable click-through (allow dragging)."""
        hwnd = int(self.winId())
        set_click_through(hwnd, False)

    def set_pass_through(self, enable: bool):
        """Toggle between click-through and interactive."""
        self.pass_through = enable
        if enable:
            self.enable_pass_through()
            self.setCursor(QCursor(Qt.ArrowCursor))
        else:
            self.disable_pass_through()
            self.setCursor(QCursor(Qt.SizeAllCursor))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.tint)

    def mousePressEvent(self, event):
        if self.pass_through or event.button() != Qt.LeftButton:
            return
        self._dragging = True
        self._drag_start = event.globalPos()
        self._window_start = self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.pass_through or not self._dragging:
            return
        delta = event.globalPos() - self._drag_start
        self.move(self._window_start + delta)

    def mouseReleaseEvent(self, event):
        self._dragging = False


class RegionSelector(QWidget):
    """Fullscreen overlay for selecting a region."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.start_pos = None
        self.end_pos = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CrossCursor))
        QTimer.singleShot(50, self._bring_to_front)

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
        p.fillRect(self.rect(), QColor(0, 0, 0, 50))
        if self.start_pos and self.end_pos:
            p.setBrush(QColor(0, 120, 255, 60))
            p.setPen(QColor(0, 120, 255, 200))
            p.drawRect(QRect(self.start_pos, self.end_pos))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eye Care")
        self.setFixedSize(220, 150)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout()
        self.btn_select = QPushButton("Select Region")
        self.btn_toggle = QPushButton("Click-through: ON")
        self.btn_toggle.setEnabled(False)

        layout.addWidget(self.btn_select)
        layout.addWidget(self.btn_toggle)
        self.setLayout(layout)

        self.selector = None
        self.overlay = None

        self.btn_select.clicked.connect(self.select_region)
        self.btn_toggle.clicked.connect(self.toggle_pass_through)

    def select_region(self):
        print("Select region clicked")
        if self.selector and self.selector.isVisible():
            self.selector.close()
        self.selector = RegionSelector(self.apply_eye_care)
        self.selector.show()

    def apply_eye_care(self, rect):
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        print("Applying tint to:", rect)
        if self.overlay:
            self.overlay.close()
        self.overlay = RegionOverlay(x, y, w, h)
        self.overlay.show()
        self.btn_toggle.setEnabled(True)

    def toggle_pass_through(self):
        if not self.overlay:
            return
        new_state = not self.overlay.pass_through
        self.overlay.set_pass_through(new_state)
        self.btn_toggle.setText(f"Click-through: {'ON' if new_state else 'OFF'}")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
