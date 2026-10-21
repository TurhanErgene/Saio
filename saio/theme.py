"""Colors and the Qt stylesheet for the control panel."""
import pathlib

ASSETS = (pathlib.Path(__file__).resolve().parent / "assets").as_posix()

ACCENT = "#ff9f43"
BG = "#15161a"
CARD = "#1e2026"
BORDER = "#2b2e36"
TEXT = "#ececf1"
MUTED = "#8b8f9c"


def dark_palette():
    from PyQt5.QtGui import QColor, QPalette
    p = QPalette()
    for role, color in (
        (QPalette.Window, BG), (QPalette.WindowText, TEXT), (QPalette.Base, CARD),
        (QPalette.AlternateBase, BG), (QPalette.Text, TEXT), (QPalette.Button, "#2a2d35"),
        (QPalette.ButtonText, TEXT), (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, "#1a1b1f"),
        (QPalette.ToolTipBase, CARD), (QPalette.ToolTipText, TEXT), (QPalette.PlaceholderText, MUTED),
    ):
        p.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor("#5d616c"))
    return p


STYLESHEET = f"""
QWidget {{
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 10pt;
}}
QLabel#title {{ font-size: 17pt; font-weight: 600; }}
QLabel#subtitle, QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#section {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#value {{ color: {ACCENT}; font-weight: 600; }}
QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel {{ background: transparent; }}

QPushButton {{
    background: #2a2d35;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 12px;
}}
QPushButton:hover {{ background: #33363f; }}
QPushButton:pressed {{ background: #24262d; }}
QPushButton:disabled {{ color: #5d616c; background: #222429; }}
QPushButton:checked {{
    background: rgba(255, 159, 67, 0.16);
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}
QPushButton#primary {{
    background: {ACCENT};
    color: #1a1b1f;
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: #ffb066; }}
QPushButton#tile {{
    padding: 8px 4px;
    text-align: center;
    font-size: 9pt;
}}
QPushButton#segment {{ border-radius: 7px; padding: 6px; }}
QPushButton#swatch {{ border-radius: 8px; min-width: 28px; }}
QPushButton#link {{
    background: transparent; border: none; color: {MUTED}; padding: 4px;
}}
QPushButton#link:hover {{ color: {TEXT}; }}
QPushButton#small {{ padding: 4px 10px; font-size: 9pt; border-radius: 7px; }}
QWidget#appRow {{ background: #262830; border-radius: 8px; }}

QComboBox {{
    background: #2f323b; border: 1px solid {BORDER}; border-radius: 7px; padding: 3px 8px;
    min-width: 108px; font-size: 9pt;
}}
QComboBox:hover {{ border-color: #4a4d58; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ image: url({ASSETS}/chevron.svg); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER}; selection-background-color: #33363f;
    selection-color: {ACCENT}; outline: none; padding: 4px;
}}

QSlider::groove:horizontal {{ height: 4px; background: #33363f; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: #ffffff; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{ background: #ffe2c4; }}

QToolTip {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px;
}}
QMenu {{ background: {CARD}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #33363f; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
"""
