from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from .overlay_window import OverlayWindow

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eye Care")
        self.setFixedSize(200, 150)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)

        # Layout
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("No region selected")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.select_btn = QPushButton("Select Region")
        self.select_btn.clicked.connect(self.select_region)

        self.toggle_btn = QPushButton("Toggle Eye Care")
        self.toggle_btn.clicked.connect(self.toggle_eye_care)
        self.toggle_btn.setEnabled(False)

        layout.addWidget(self.status_label)
        layout.addWidget(self.select_btn)
        layout.addWidget(self.toggle_btn)

        self.setLayout(layout)

        self.overlay = None
        self.region = None
        self.eye_care_on = False

    def select_region(self):
        self.overlay = OverlayWindow(self)
        self.overlay.region_selected.connect(self.region_chosen)
        self.overlay.showFullScreen()

    def region_chosen(self, region):
        self.region = region
        self.status_label.setText(f"Region: {region}")
        self.toggle_btn.setEnabled(True)

    def toggle_eye_care(self):
        if not self.overlay:
            return

        if self.eye_care_on:
            self.overlay.hide()
            self.eye_care_on = False
            self.toggle_btn.setText("Toggle Eye Care")
        else:
            self.overlay.show_overlay(self.region)
            self.eye_care_on = True
            self.toggle_btn.setText("Disable Eye Care")
