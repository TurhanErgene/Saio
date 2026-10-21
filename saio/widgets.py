"""Small custom widgets and generated graphics."""
import pathlib

from PyQt5.QtCore import QPropertyAnimation, QRectF, QSize, Qt, pyqtProperty
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from .filters import apply_to_rgb
from .theme import ACCENT


class ToggleSwitch(QAbstractButton):
    """iOS/Windows 11 style on/off switch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self, duration=140)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(44, 24)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    @pyqtProperty(float)
    def knob(self):
        return self._pos

    @knob.setter
    def knob(self, value):
        self._pos = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        off, on = QColor("#3a3d46"), QColor(ACCENT)
        t = self._pos
        track = QColor(
            round(off.red() + (on.red() - off.red()) * t),
            round(off.green() + (on.green() - off.green()) * t),
            round(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Card(QFrame):
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(14, 12, 14, 14)
        self.body.setSpacing(10)
        if title:
            label = QLabel(title.upper())
            label.setObjectName("section")
            self.body.addWidget(label)


class LabeledSlider(QFrame):
    def __init__(self, title, minimum, maximum, value, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(QLabel(title))
        head.addStretch()
        self.value_label = QLabel()
        self.value_label.setObjectName("value")
        head.addWidget(self.value_label)
        layout.addLayout(head)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(lambda v: self.value_label.setText(f"{v}%"))
        self.slider.setValue(value)
        self.value_label.setText(f"{value}%")
        layout.addWidget(self.slider)


def filter_preview(matrix, w=56, h=22):
    """A rounded rainbow strip with `matrix` applied – shows what a filter does."""
    img = QImage(w, h, QImage.Format_ARGB32)
    for x in range(w):
        hue = QColor.fromHsvF(x / w * 0.92, 0.75, 1.0)
        for y in range(h):
            shade = 1.0 - (y / h) * 0.45
            r, g, b = apply_to_rgb(matrix, hue.red() * shade, hue.green() * shade, hue.blue() * shade)
            img.setPixel(x, y, QColor(r, g, b).rgb())
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), 6, 6)
    p.setClipPath(path)
    p.drawImage(0, 0, img)
    p.end()
    return QIcon(pix)


ASSETS = pathlib.Path(__file__).resolve().parent / "assets"


def _svg_icon(sizes):
    """Render the logo SVGs into a multi-size QIcon (small sizes use the bolder glyph)."""
    icon = QIcon()
    for size, name in sizes:
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        QSvgRenderer(str(ASSETS / name)).render(p, QRectF(0, 0, size, size))
        p.end()
        icon.addPixmap(pix)
    return icon


def app_icon():
    return _svg_icon([(16, "saio-glyph.svg"), (24, "saio-glyph.svg"), (32, "saio.svg"),
                      (48, "saio.svg"), (64, "saio.svg"), (256, "saio.svg")])


def tray_icon():
    return _svg_icon([(size, "saio-glyph.svg") for size in (16, 20, 24, 32, 48)])
