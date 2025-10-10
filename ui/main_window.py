from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel, QSlider, QComboBox
from PyQt5.QtCore import Qt
from .overlay_window import OverlayWindow
from core.settings import Settings


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eye Care")
        self.setFixedSize(250, 250)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)

        # Create settings
        self.settings = Settings()

        # Layout
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # Status
        self.status_label = QLabel("No region selected")
        self.status_label.setAlignment(Qt.AlignCenter)

        # Buttons
        self.select_btn = QPushButton("Select Region")
        self.select_btn.clicked.connect(self.select_region)

        self.toggle_btn = QPushButton("Toggle Eye Care")
        self.toggle_btn.clicked.connect(self.toggle_eye_care)
        self.toggle_btn.setEnabled(False)

        # Color temp dropdown
        self.color_dropdown = QComboBox()
        self.color_dropdown.addItems(["Warm", "Neutral", "Cool"])
        self.color_dropdown.currentIndexChanged.connect(self.change_color_temp)

        # Opacity slider
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.settings.opacity * 100))
        self.opacity_slider.valueChanged.connect(self.change_opacity)

        self.opacity_label = QLabel(f"Opacity: {self.opacity_slider.value()}%")
        self.opacity_label.setAlignment(Qt.AlignCenter)

        # Add to layout
        layout.addWidget(self.status_label)
        layout.addWidget(self.select_btn)
        layout.addWidget(self.toggle_btn)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Color Temperature:"))
        layout.addWidget(self.color_dropdown)
        layout.addSpacing(5)
        layout.addWidget(self.opacity_label)
        layout.addWidget(self.opacity_slider)

        self.setLayout(layout)

        self.overlay = None
        self.region = None
        self.eye_care_on = False

    def select_region(self):
        print("Select region triggered")
        self.overlay = OverlayWindow(self.settings, self)
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

    def change_color_temp(self, index):
        if index == 0:   # Warm
            self.settings.set_color((255, 170, 100))
        elif index == 1: # Neutral
            self.settings.set_color((255, 255, 240))
        elif index == 2: # Cool
            self.settings.set_color((150, 200, 255))

        if self.eye_care_on and self.overlay:
            self.overlay.update_overlay()

    def change_opacity(self, value):
        self.settings.set_opacity(value / 100.0)
        self.opacity_label.setText(f"Opacity: {value}%")
        if self.eye_care_on and self.overlay:
            self.overlay.update_overlay()
