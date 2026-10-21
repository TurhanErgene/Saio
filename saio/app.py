"""Main control panel, tray icon and application wiring."""
import json
import os
import sys

from PyQt5.QtCore import QFileInfo, QProcess, QRect, QSettings, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QGuiApplication
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QColorDialog, QComboBox, QFileIconProvider, QGridLayout, QHBoxLayout,
    QLabel, QLayout, QMenu, QMessageBox, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import gpu, winapi
from .apps import AppFilterManager, AppRule, WindowPicker
from .filters import FILTERS, FILTERS_BY_KEY, build_matrix, flatten, identity
from .hotkeys import GlobalHotkeys
from .region import FilterRegion
from .selector import RegionSelector
from .theme import ACCENT, STYLESHEET, TEXT, dark_palette
from .widgets import Card, LabeledSlider, ToggleSwitch, app_icon, filter_preview, tray_icon

MODE_REGIONS = "regions"
MODE_FULLSCREEN = "fullscreen"

HOTKEYS = [
    ("ctrl+alt+f", "Turn filter on/off", "toggle_enabled"),
    ("ctrl+alt+r", "Add a region", "add_region"),
    ("ctrl+alt+e", "Edit regions", "toggle_editing"),
    ("ctrl+alt+a", "Filter an app", "pick_app"),
    ("ctrl+alt+plus", "More intensity", "intensity_up"),
    ("ctrl+alt+minus", "Less intensity", "intensity_down"),
]


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Saio")
        self.setWindowIcon(app_icon())
        self.settings = QSettings("Saio", os.environ.get("SAIO_PROFILE", "Saio"))  # separate profile for testing
        self.regions = []
        self.selector = None
        self.picker = None
        self._editing = False
        self._tray_hint_shown = False
        self._save_timer = QTimer(self, singleShot=True, interval=400, timeout=self.save_settings)

        self.enabled = self.settings.value("enabled", True, type=bool)
        self.filter_key = self.settings.value("filter", "warm", type=str)
        if self.filter_key not in FILTERS_BY_KEY:
            self.filter_key = "warm"
        self.custom_color = QColor(self.settings.value("custom_color", "#ffb070", type=str))
        self.mode = self.settings.value("mode", MODE_REGIONS, type=str)

        self.apps = AppFilterManager(self.matrix_for, self)
        self.apps.hostsChanged.connect(self._update_exclusions)

        self._build_ui()
        self._build_tray()
        self._register_hotkeys()
        self._restore_regions()
        self._restore_apps()
        self.apply()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SetFixedSize)  # window always hugs its content
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        # header
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Saio")
        title.setObjectName("title")
        self.status = QLabel()
        self.status.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(self.status)
        header.addLayout(titles)
        header.addStretch()
        self.power = ToggleSwitch()
        self.power.setToolTip("Turn the filter on/off  (Ctrl+Alt+F)")
        self.power.setChecked(self.enabled)
        self.power.toggled.connect(self.set_enabled)
        header.addWidget(self.power, 0, Qt.AlignVCenter)
        root.addLayout(header)

        # filters
        card = Card("Filter")
        grid = QGridLayout()
        grid.setSpacing(8)
        self.filter_group = QButtonGroup(self)
        self.filter_buttons = {}
        for i, f in enumerate(FILTERS):
            btn = self._make_tile(f)
            self.filter_group.addButton(btn)
            self.filter_buttons[f.key] = btn
            btn.clicked.connect(lambda _, k=f.key: self.set_filter(k))
            grid.addWidget(btn, i // 3, i % 3)
        self._refresh_previews()
        card.body.addLayout(grid)

        color_row = QHBoxLayout()
        self.color_label = QLabel("Tint color")
        self.color_button = QPushButton()
        self.color_button.setObjectName("swatch")
        self.color_button.setCursor(Qt.PointingHandCursor)
        self.color_button.setFixedSize(64, 28)
        self.color_button.clicked.connect(self.pick_color)
        color_row.addWidget(self.color_label)
        color_row.addStretch()
        color_row.addWidget(self.color_button)
        self.color_row = QWidget()
        self.color_row.setLayout(color_row)
        color_row.setContentsMargins(0, 0, 0, 0)
        card.body.addWidget(self.color_row)

        self.intensity = LabeledSlider("Intensity", 0, 100, self.settings.value("intensity", 60, type=int))
        self.brightness = LabeledSlider("Brightness", 20, 100, self.settings.value("brightness", 100, type=int))
        self.intensity.slider.valueChanged.connect(self.apply)
        self.brightness.slider.valueChanged.connect(self.apply)
        card.body.addWidget(self.intensity)
        card.body.addWidget(self.brightness)
        root.addWidget(card)

        # target
        card = Card("Apply to")
        seg = QHBoxLayout()
        seg.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}
        for key, label in ((MODE_REGIONS, "Regions && apps"), (MODE_FULLSCREEN, "Whole screen")):
            btn = QPushButton(label)
            btn.setObjectName("segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.set_mode(k))
            self.mode_group.addButton(btn)
            self.mode_buttons[key] = btn
            seg.addWidget(btn)
        card.body.addLayout(seg)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.btn_add = QPushButton("＋  Add region")
        self.btn_add.setObjectName("primary")
        self.btn_add.setToolTip("Drag a rectangle anywhere on screen  (Ctrl+Alt+R)")
        self.btn_add.clicked.connect(self.add_region)
        self.btn_edit = QPushButton("Move / resize")
        self.btn_edit.setCheckable(True)
        self.btn_edit.setToolTip("Unlock regions so you can drag them  (Ctrl+Alt+E)")
        self.btn_edit.clicked.connect(self.set_editing)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setToolTip("Remove all regions")
        self.btn_clear.clicked.connect(self.clear_regions)
        for b in (self.btn_add, self.btn_edit, self.btn_clear):
            b.setCursor(Qt.PointingHandCursor)
        actions.addWidget(self.btn_add, 1)
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_clear)
        self.region_actions = QWidget()
        self.region_actions.setLayout(actions)
        actions.setContentsMargins(0, 0, 0, 0)
        card.body.addWidget(self.region_actions)

        # per-app filters
        self.apps_section = QWidget()
        apps_layout = QVBoxLayout(self.apps_section)
        apps_layout.setContentsMargins(0, 6, 0, 0)
        apps_layout.setSpacing(8)
        head = QHBoxLayout()
        label = QLabel("APPS")
        label.setObjectName("section")
        head.addWidget(label)
        head.addStretch()
        pick = QPushButton("＋  Pick app")
        pick.setObjectName("small")
        pick.setCursor(Qt.PointingHandCursor)
        pick.setToolTip("Click any window – that app always gets its own filter  (Ctrl+Alt+A)")
        pick.clicked.connect(self.pick_app)
        head.addWidget(pick)
        apps_layout.addLayout(head)
        self.apps_empty = QLabel("Pick a window and every window of that app gets its own filter "
                                 "– e.g. Negative for a PDF reader.")
        self.apps_empty.setObjectName("muted")
        self.apps_empty.setWordWrap(True)
        apps_layout.addWidget(self.apps_empty)
        self.app_rows = QVBoxLayout()
        self.app_rows.setSpacing(6)
        apps_layout.addLayout(self.app_rows)
        card.body.addWidget(self.apps_section)
        root.addWidget(card)

        # footer
        footer = QHBoxLayout()
        self.hotkey_label = QLabel()
        self.hotkey_label.setObjectName("muted")
        footer.addWidget(self.hotkey_label)
        footer.addStretch()
        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("link")
        quit_btn.setCursor(Qt.PointingHandCursor)
        quit_btn.clicked.connect(self.quit)
        footer.addWidget(quit_btn)
        root.addLayout(footer)

        self.filter_buttons[self.filter_key].setChecked(True)
        self.mode_buttons[self.mode].setChecked(True)
        self._update_color_button()

    @staticmethod
    def _make_tile(f):
        """Checkable button with a live preview strip above the filter name."""
        btn = QPushButton()
        btn.setObjectName("tile")
        btn.setCheckable(True)
        btn.setToolTip(f.hint)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumSize(102, 64)
        lay = QVBoxLayout(btn)
        lay.setContentsMargins(4, 8, 4, 6)
        lay.setSpacing(5)
        btn.preview = QLabel()
        btn.name = QLabel(f.name)
        for label in (btn.preview, btn.name):
            label.setAlignment(Qt.AlignCenter)
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
            lay.addWidget(label)
        return btn

    def _refresh_previews(self, only=None):
        rgb = self._color_tuple()
        for f in FILTERS:
            if only is None or f.key == only:
                icon = filter_preview(build_matrix(f.key, 1.0, 1.0, rgb))
                self.filter_buttons[f.key].preview.setPixmap(icon.pixmap(56, 22))

    def _rebuild_app_rows(self):
        while self.app_rows.count():
            self.app_rows.takeAt(0).widget().deleteLater()
        icons = QFileIconProvider()
        rgb = self._color_tuple()
        for rule in self.apps.rules:
            row = QWidget()
            row.setObjectName("appRow")
            row.setAttribute(Qt.WA_StyledBackground)
            lay = QHBoxLayout(row)
            lay.setContentsMargins(8, 4, 4, 4)
            lay.setSpacing(8)
            icon = QLabel()
            icon.setPixmap(icons.icon(QFileInfo(rule.path)).pixmap(20, 20))
            name = QLabel(rule.name)
            name.setToolTip(rule.path)
            combo = QComboBox()
            combo.setCursor(Qt.PointingHandCursor)
            combo.setIconSize(QSize(28, 12))
            for f in FILTERS:
                combo.addItem(filter_preview(build_matrix(f.key, 1.0, 1.0, rgb), 28, 12), f.name, f.key)
            combo.setCurrentIndex(max(0, combo.findData(rule.filter_key)))
            combo.currentIndexChanged.connect(lambda _, r=rule, c=combo: self.set_app_filter(r, c.currentData()))
            remove = QPushButton("✕")
            remove.setObjectName("link")
            remove.setCursor(Qt.PointingHandCursor)
            remove.setToolTip(f"Stop filtering {rule.name}")
            remove.clicked.connect(lambda _, r=rule: self.remove_app(r))
            lay.addWidget(icon)
            lay.addWidget(name, 1)
            lay.addWidget(combo)
            lay.addWidget(remove)
            self.app_rows.addWidget(row)
        self.apps_empty.setVisible(not self.apps.rules)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(tray_icon(), self)
        menu = QMenu()
        menu.addAction("Open Saio", self.show_panel)
        menu.addSeparator()
        self.tray_toggle = menu.addAction("Filter enabled")
        self.tray_toggle.setCheckable(True)
        self.tray_toggle.triggered.connect(self.set_enabled)
        filters_menu = menu.addMenu("Filter")
        self.tray_filters = {}
        for f in FILTERS:
            act = filters_menu.addAction(f.name)
            act.setCheckable(True)
            act.triggered.connect(lambda _, k=f.key: self.set_filter(k))
            self.tray_filters[f.key] = act
        menu.addAction("Add region", self.add_region)
        menu.addAction("Filter an app…", self.pick_app)
        menu.addSeparator()
        menu.addAction("Quit", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Saio")
        self.tray.activated.connect(
            lambda reason: self.show_panel() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _register_hotkeys(self):
        self.hotkeys = GlobalHotkeys()
        lines, failed = [], []
        for combo, label, method in HOTKEYS:
            ok = self.hotkeys.register(combo, getattr(self, method))
            pretty = combo.replace("plus", "=").replace("minus", "-").title()
            (lines if ok else failed).append(f"{pretty}  —  {label}")
        tip = "Global shortcuts:\n" + "\n".join(lines)
        if failed:
            tip += "\n\nUnavailable (used by another app):\n" + "\n".join(failed)
        self.hotkey_label.setText("⌨  Shortcuts")
        self.hotkey_label.setToolTip(tip)

    # ------------------------------------------------------------- state

    def _color_tuple(self):
        c = self.custom_color
        return c.red(), c.green(), c.blue()

    def matrix_for(self, key):
        return flatten(build_matrix(
            key,
            self.intensity.slider.value() / 100,
            self.brightness.slider.value() / 100,
            self._color_tuple(),
        ))

    def current_matrix(self):
        return self.matrix_for(self.filter_key)

    def apply(self):
        """Push the current settings to the screen."""
        matrix = self.current_matrix()
        fullscreen = self.enabled and self.mode == MODE_FULLSCREEN
        winapi.set_fullscreen_color_effect(matrix if fullscreen else flatten(identity()))

        show_regions = self._editing or (self.enabled and self.mode == MODE_REGIONS)
        for r in self.regions:
            r.set_matrix(matrix)
            r.setVisible(show_regions)
        self.apps.set_active(self.enabled and self.mode == MODE_REGIONS)
        self.apps.refresh_matrices()

        self.color_row.setVisible(FILTERS_BY_KEY[self.filter_key].uses_color)
        self.region_actions.setVisible(self.mode == MODE_REGIONS)
        self.apps_section.setVisible(self.mode == MODE_REGIONS)
        self.btn_edit.setEnabled(bool(self.regions))
        self.btn_clear.setEnabled(bool(self.regions))
        self.tray_toggle.setChecked(self.enabled)
        for key, act in self.tray_filters.items():
            act.setChecked(key == self.filter_key)
        for key, btn in self.filter_buttons.items():
            btn.name.setStyleSheet(f"color: {ACCENT if key == self.filter_key else TEXT}; font-size: 9pt;")
        self._update_status()
        self._save_timer.start()

    def _update_status(self):
        name = FILTERS_BY_KEY[self.filter_key].name
        if not self.enabled:
            text = "Filter is off"
        elif self.mode == MODE_FULLSCREEN:
            text = f"{name} · whole screen"
        elif not self.regions and not self.apps.rules:
            text = f"{name} · add a region or app to begin"
        else:
            parts = [name]
            for n, word in ((len(self.regions), "region"), (len(self.apps.rules), "app")):
                if n:
                    parts.append(f"{n} {word}{'s' if n > 1 else ''}")
            text = " · ".join(parts)
        self.status.setText(text)
        self.tray.setToolTip(f"Saio — {text}")

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if self.power.isChecked() != self.enabled:
            self.power.blockSignals(True)
            self.power.setChecked(self.enabled)
            self.power.blockSignals(False)
        self.apply()

    def toggle_enabled(self):
        self.set_enabled(not self.enabled)

    def set_filter(self, key):
        self.filter_key = key
        self.filter_buttons[key].setChecked(True)
        if not self.enabled:
            self.set_enabled(True)
        else:
            self.apply()

    def set_mode(self, mode):
        self.mode = mode
        self.mode_buttons[mode].setChecked(True)
        if mode == MODE_FULLSCREEN and self._editing:
            self.set_editing(False)
        self.apply()

    def _nudge_intensity(self, delta):
        s = self.intensity.slider
        s.setValue(max(s.minimum(), min(s.maximum(), s.value() + delta)))

    def intensity_up(self):
        self._nudge_intensity(10)

    def intensity_down(self):
        self._nudge_intensity(-10)

    def pick_color(self):
        color = QColorDialog.getColor(self.custom_color, self, "Choose a tint color")
        if color.isValid():
            self.custom_color = color
            self._update_color_button()
            self._refresh_previews(only="custom")
            self._rebuild_app_rows()
            self.apply()

    def _update_color_button(self):
        self.color_button.setStyleSheet(
            f"QPushButton#swatch {{ background: {self.custom_color.name()}; border: 2px solid #3a3d46; }}"
            f"QPushButton#swatch:hover {{ border-color: #ffffff; }}")

    # ------------------------------------------------------------ regions

    def add_region(self):
        if self.selector is not None:
            return
        self.set_editing(False)
        self.selector = RegionSelector()
        self.selector.selected.connect(self._on_region_selected)
        self.selector.destroyed.connect(lambda: setattr(self, "selector", None))
        self.selector.start()

    def _on_region_selected(self, rect):
        self._create_region(rect)
        if self.mode != MODE_REGIONS:
            self.set_mode(MODE_REGIONS)
        if not self.enabled:
            self.set_enabled(True)
        self.apply()

    def _create_region(self, rect):
        region = FilterRegion(rect, self.current_matrix())
        region.removeRequested.connect(self._remove_region)
        region.editFinished.connect(lambda: self.set_editing(False))
        region.geometryEdited.connect(self._save_timer.start)
        self.regions.append(region)
        region.set_editing(self._editing)
        region.show()
        self._update_exclusions()
        return region

    def _remove_region(self, region):
        self.regions.remove(region)
        region.close()
        region.deleteLater()
        self._update_exclusions()
        if not self.regions:
            self.set_editing(False)
        self.apply()

    def clear_regions(self):
        for r in list(self.regions):
            self._remove_region(r)

    def _update_exclusions(self):
        # every magnifier must ignore every filter window, or they would filter each other
        windows = self.regions + list(self.apps.followers.values())
        hwnds = [w.hwnd for w in windows]
        for w in windows:
            w.set_excluded(hwnds)

    # --------------------------------------------------------------- apps

    def pick_app(self):
        if self.picker is not None:
            return
        self.picker = WindowPicker()
        self.picker.picked.connect(self._on_app_picked)
        self.picker.destroyed.connect(lambda: setattr(self, "picker", None))
        self.picker.start()

    def _on_app_picked(self, hwnd, path):
        exe = os.path.basename(path).lower()
        if self.apps.rule_for(exe) is None:
            self.apps.add_rule(AppRule(exe, path, self.filter_key))
            self._rebuild_app_rows()
        if self.mode != MODE_REGIONS:
            self.set_mode(MODE_REGIONS)
        if not self.enabled:
            self.set_enabled(True)
        self.apply()

    def set_app_filter(self, rule, key):
        self.apps.set_rule_filter(rule, key)
        self._save_timer.start()

    def remove_app(self, rule):
        self.apps.remove_rule(rule)
        self._rebuild_app_rows()
        self.apply()

    def _restore_apps(self):
        try:
            saved = json.loads(self.settings.value("apps", "[]", type=str))
            self.apps.rules = [AppRule.from_json(d) for d in saved]
        except (ValueError, KeyError, TypeError):
            self.apps.rules = []
        for rule in self.apps.rules:
            if rule.filter_key not in FILTERS_BY_KEY:
                rule.filter_key = "warm"
        self._rebuild_app_rows()

    def set_editing(self, editing):
        editing = bool(editing) and bool(self.regions) and self.mode == MODE_REGIONS
        self._editing = editing
        self.btn_edit.setChecked(editing)
        for r in self.regions:
            r.set_editing(editing)
        self.apply()

    def toggle_editing(self):
        self.set_editing(not self._editing)

    def _restore_regions(self):
        try:
            saved = json.loads(self.settings.value("regions", "[]", type=str))
        except ValueError:
            saved = []
        screens = [s.geometry() for s in QGuiApplication.screens()]
        for x, y, w, h in saved:
            rect = QRect(x, y, w, h)
            if any(s.intersects(rect) for s in screens):
                self._create_region(rect)

    # ------------------------------------------------------- persistence

    def save_settings(self):
        s = self.settings
        s.setValue("enabled", self.enabled)
        s.setValue("filter", self.filter_key)
        s.setValue("custom_color", self.custom_color.name())
        s.setValue("mode", self.mode)
        s.setValue("intensity", self.intensity.slider.value())
        s.setValue("brightness", self.brightness.slider.value())
        s.setValue("regions", json.dumps(
            [[r.x(), r.y(), r.width(), r.height()] for r in self.regions]))
        s.setValue("apps", json.dumps([r.to_json() for r in self.apps.rules]))

    # ---------------------------------------------------------- lifetime

    def check_gpu(self):
        """Verify the magnifier really renders (see gpu.py). The probe is an unfiltered
        copy of the panel placed exactly over it, so it's invisible to the user."""
        if not self.isVisible():
            return
        probe = FilterRegion(self.geometry(), flatten(identity()))
        probe.show()
        QTimer.singleShot(400, lambda: self._finish_gpu_check(probe))

    def _finish_gpu_check(self, probe):
        ok = gpu.window_has_content(probe.hwnd, probe.width(), probe.height())
        probe.close()
        probe.deleteLater()
        if ok:
            return
        if gpu.RETRY_FLAG not in sys.argv:
            # wrong GPU for this machine's displays: switch and restart once
            gpu.set_preference(gpu.other_preference())
            # a frozen .exe is its own sys.argv[0]; from source, argv[0] is main.py for python.exe
            args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
            QProcess.startDetached(sys.executable, args + [gpu.RETRY_FLAG])
            self.quit()
        else:
            QMessageBox.warning(
                self, "Saio",
                "Saio couldn't render filters on this graphics setup – regions and app filters may "
                "appear black.\n\n\"Whole screen\" mode still works. Try setting Python (or Saio) to the "
                "GPU your monitors are connected to in Windows Settings → Display → Graphics.")

    def show_panel(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage("Saio is still running",
                                      "Your filters stay active. Use the tray icon to reopen or quit.",
                                      app_icon(), 4000)
        else:
            self.quit()

    def quit(self):
        self.save_settings()
        self.hotkeys.unregister_all()
        self.apps.shutdown()
        winapi.set_fullscreen_color_effect(flatten(identity()))
        for r in self.regions:
            r.close()
        self.tray.hide()
        QApplication.quit()


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Saio")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLESHEET)

    gpu.prepare()  # must happen before the magnifier starts DirectX
    if not winapi.mag_initialize():
        QMessageBox.critical(None, "Saio", "The Windows Magnification API is not available on this system.")
        return 1

    window = MainWindow()
    window.show()
    QTimer.singleShot(800, window.check_gpu)
    try:
        return app.exec_()
    finally:
        winapi.set_fullscreen_color_effect(flatten(identity()))
        winapi.mag_uninitialize()
