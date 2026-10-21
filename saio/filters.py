"""Color filters expressed as 5x5 color matrices.

Convention (same as the Windows Magnification API): rows are input channels
(R, G, B, A, constant), columns are output channels, i.e.
    out_j = sum_i in_i * M[i][j]
"""
from dataclasses import dataclass
from typing import Callable

Matrix = list  # 5x5 nested list of floats

_LUMA = (0.2126, 0.7152, 0.0722)


def identity():
    return [[1.0 if i == j else 0.0 for j in range(5)] for i in range(5)]


def multiply(r, g, b):
    """Multiply each channel – like a tinted glass, nothing gets hidden."""
    m = identity()
    m[0][0], m[1][1], m[2][2] = r, g, b
    return m


def _from_rows(rows):
    m = identity()
    for i, row in enumerate(rows):
        m[i][:3] = list(row)
    return m


def grayscale():
    return _from_rows([(c, c, c) for c in _LUMA])


def invert():
    m = multiply(-1, -1, -1)
    m[4][:3] = [1.0, 1.0, 1.0]
    return m


def inverted_grayscale():
    m = _from_rows([(-c, -c, -c) for c in _LUMA])
    m[4][:3] = [1.0, 1.0, 1.0]
    return m


def sepia():
    return _from_rows([(0.393, 0.349, 0.272), (0.769, 0.686, 0.534), (0.189, 0.168, 0.131)])


def red_night():
    """Everything rendered in red – preserves night vision."""
    return _from_rows([(c, 0, 0) for c in _LUMA])


# Color-vision deficiency simulation (Machado et al. 2009, full severity), column form: out = S @ in
_CVD = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
# Where the colour information a viewer can't see gets moved to (daltonization)
_SHIFT_RED_GREEN = ((0, 0, 0), (0.7, 1, 0), (0.7, 0, 1))
_SHIFT_BLUE = ((1, 0, 0.7), (0, 1, 0.7), (0, 0, 0))


def color_assist(kind):
    """Daltonize: corrected = in + E·(in − S·in), folded into one matrix."""
    sim = _CVD[kind]
    shift = _SHIFT_BLUE if kind == "tritan" else _SHIFT_RED_GREEN
    lost = [[(1.0 if r == c else 0.0) - sim[r][c] for c in range(3)] for r in range(3)]
    col = [[(1.0 if r == c else 0.0) + sum(shift[r][k] * lost[k][c] for k in range(3))
            for c in range(3)] for r in range(3)]
    return _from_rows([[col[out][inp] for out in range(3)] for inp in range(3)])  # to row-input form


@dataclass(frozen=True)
class Filter:
    key: str
    name: str
    hint: str
    build: Callable  # (QColor-like rgb tuple) -> Matrix
    uses_color: bool = False


FILTERS = [
    Filter("warm", "Warm", "Gentle blue-light reduction", lambda c: multiply(1.0, 0.82, 0.6)),
    Filter("amber", "Amber", "Strong blue-light reduction for late nights", lambda c: multiply(1.0, 0.62, 0.22)),
    Filter("custom", "Custom", "Tint with any color you like", lambda c: multiply(*(v / 255 for v in c)), True),
    Filter("red", "Red night", "Monochrome red – keeps night vision", lambda c: red_night()),
    Filter("dim", "Dim only", "No color change – just use the brightness slider", lambda c: identity()),
    Filter("sepia", "Sepia", "Warm, paper-like reading tone", lambda c: sepia()),
    Filter("grayscale", "Grayscale", "Remove all color – less distracting", lambda c: grayscale()),
    Filter("invert", "Negative", "Invert all colors", lambda c: invert()),
    Filter("invert_gray", "Dark paper", "Inverted grayscale – white pages become dark", lambda c: inverted_grayscale()),
    Filter("protan", "Red-weak", "Color-vision assist for protanopia / protanomaly (reds look dark or muddy)",
           lambda c: color_assist("protan")),
    Filter("deutan", "Green-weak", "Color-vision assist for deuteranopia / deuteranomaly (most common red-green type)",
           lambda c: color_assist("deutan")),
    Filter("tritan", "Blue-weak", "Color-vision assist for tritanopia (blue/yellow confusion)",
           lambda c: color_assist("tritan")),
]
FILTERS_BY_KEY = {f.key: f for f in FILTERS}


def build_matrix(key, intensity, brightness, color):
    """Blend from identity to the filter by `intensity` (0–1), then scale by `brightness` (0–1)."""
    target = FILTERS_BY_KEY[key].build(color)
    base = identity()
    m = [[base[i][j] + (target[i][j] - base[i][j]) * intensity for j in range(5)] for i in range(5)]
    for i in range(5):
        for j in range(3):
            m[i][j] *= brightness
    return m


def flatten(m):
    return [v for row in m for v in row]


def apply_to_rgb(m, r, g, b):
    """Apply a matrix to an 8-bit RGB triple (used for UI previews)."""
    src = (r / 255, g / 255, b / 255, 1.0, 1.0)
    out = [sum(src[i] * m[i][j] for i in range(5)) for j in range(3)]
    return tuple(max(0, min(255, round(v * 255))) for v in out)
