"""Generate Saio's logo files.

    python tools/make_icons.py

Writes to saio/assets/:
    saio.svg        app icon (eye on a rounded tile) – window, installer, .exe
    saio-glyph.svg  the bare eye, larger – tray icon and small sizes
    saio.ico        multi-resolution Windows icon (16–256 px) for the future .exe
    saio-256.png    preview / README image

The SVGs avoid clipPath (Qt's SVG renderer doesn't support it): the warm
"filter lens" half of the eye is precomputed as a plain path.
"""
import pathlib
import sys

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QGuiApplication, QImage, QPainter, QPainterPath, QPolygonF
from PyQt5.QtSvg import QSvgRenderer

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "saio" / "assets"

DEFS = """  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2a2c35"/>
      <stop offset="1" stop-color="#121317"/>
    </linearGradient>
    <linearGradient id="warm" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffd18c"/>
      <stop offset="0.5" stop-color="#ff9f43"/>
      <stop offset="1" stop-color="#f05a2c"/>
    </linearGradient>
    <linearGradient id="cool" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#8fd3ff"/>
      <stop offset="1" stop-color="#6a7cff"/>
    </linearGradient>
  </defs>
"""

TILE = """  <rect x="8" y="8" width="240" height="240" rx="58" fill="url(#bg)"/>
  <rect x="9" y="9" width="238" height="238" rx="57" fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="2"/>
"""


def eye_svg(left, right, lift, iris_r):
    """Almond eye centred at (128,128): cool left, warm 'lens' over the rest, crescent pupil."""
    c = 128
    eye = QPainterPath(QPointF(left, c))
    eye.cubicTo(left + (right - left) * 0.19, c - lift, right - (right - left) * 0.19, c - lift, right, c)
    eye.cubicTo(right - (right - left) * 0.19, c + lift, left + (right - left) * 0.19, c + lift, left, c)
    eye.closeSubpath()
    lens = QPainterPath()
    lens.addPolygon(QPolygonF([QPointF(c - 18, 0), QPointF(256, 0), QPointF(256, 256), QPointF(c - 58, 256)]))
    lens.closeSubpath()

    def d(path):
        poly = list(max(path.simplified().toFillPolygons(), key=len))[:-1]
        return "M" + " L".join(f"{p.x():.1f} {p.y():.1f}" for p in poly) + " Z"

    s = iris_r / 40  # crescent geometry is designed for a 40px iris
    moon = (f"M{c + 6 * s:.1f} {c - 24 * s:.1f} A {24 * s:.1f} {24 * s:.1f} 0 1 0 {c + 24 * s:.1f} {c + 12 * s:.1f} "
            f"A {19 * s:.1f} {19 * s:.1f} 0 1 1 {c + 6 * s:.1f} {c - 24 * s:.1f} Z")
    return f"""  <path d="{d(eye)}" fill="url(#cool)"/>
  <path d="{d(eye.intersected(lens))}" fill="url(#warm)"/>
  <circle cx="{c}" cy="{c}" r="{iris_r}" fill="#15161a"/>
  <path d="{moon}" fill="url(#warm)"/>
"""


def svg(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">\n'
            + DEFS + body + "</svg>\n")


def render(path, size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(str(path)).render(p, QRectF(0, 0, size, size))
    p.end()
    return img


def main():
    QGuiApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)
    tile = ASSETS / "saio.svg"
    glyph = ASSETS / "saio-glyph.svg"
    tile.write_text(svg(TILE + eye_svg(30, 226, 66, 40)), encoding="utf-8")
    glyph.write_text(svg(eye_svg(4, 252, 92, 52)), encoding="utf-8")

    render(tile, 256).save(str(ASSETS / "saio-256.png"))
    # .ico: Qt writes one image per file, so assemble the multi-size icon by hand
    import io
    import struct
    from PyQt5.QtCore import QBuffer, QIODevice
    images = []
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        src = glyph if size <= 24 else tile
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        render(src, size).save(buf, "PNG")
        images.append((size, bytes(buf.data())))
    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for size, data in images:
        dim = 0 if size >= 256 else size
        out.write(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    for _, data in images:
        out.write(data)
    (ASSETS / "saio.ico").write_bytes(out.getvalue())
    print("icons written to", ASSETS)


if __name__ == "__main__":
    main()
