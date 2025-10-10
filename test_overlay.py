from PyQt5.QtWidgets import QApplication
from ui.overlay_window import OverlayWindow
from core.settings import Settings
import sys

app = QApplication(sys.argv)
w = OverlayWindow(Settings())
w.showFullScreen()
sys.exit(app.exec_())
