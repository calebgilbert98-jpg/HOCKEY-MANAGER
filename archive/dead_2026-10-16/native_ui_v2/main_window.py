"""Main window for native_ui_v2.

Minimal bootable shell: sidebar navigation + 3 core screens
(dashboard, roster, standings) + Continue button.

Design rules (lessons from v1 bundling failures):
  - Screens come from the STATIC registry in screens/__init__.py.
    No dynamic __import__, no importlib, no method-level imports.
  - QAction imported from PySide6.QtGui (Qt6), not QtWidgets.
  - No game logic at import time; GameManager is created by the
    launcher and passed in.

Import-time safe: this module creates no QApplication, no game
objects, and touches no filesystem at import time.
"""
import sys

from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from .theme import THEME_QSS
from .screens import NAV_ORDER, SCREEN_REGISTRY
from .screens.base import resolve_gm, safe


class MainWindow(QMainWindow):
    """Minimal v2 main window."""

    def __init__(self, game=None, parent=None):
        super().__init__(parent)
        self.game = game
        self._screens = {}
        self._nav_buttons = {}

        self.setWindowTitle("Puck Dynasty")
        self.setMinimumSize(1100, 700)

        # ---- top bar ----
        topbar = QWidget()
        topbar.setObjectName("topbar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(16, 8, 16, 8)

        brand = QLabel("PUCK DYNASTY")
        brand.setObjectName("brand")
        top_layout.addWidget(brand)
        top_layout.addStretch()

        self._date_lbl = QLabel("")
        self._date_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        top_layout.addWidget(self._date_lbl)

        self._continue_btn = QPushButton("Continue  ▸")
        self._continue_btn.setObjectName("primary-btn")
        self._continue_btn.clicked.connect(self.on_continue)
        top_layout.addWidget(self._continue_btn)

        self.setMenuWidget(topbar)

        # ---- body: sidebar + stacked screens ----
        central = QWidget()
        central.setObjectName("hub-central")
        body_layout = QHBoxLayout(central)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("background-color: #0d1320;")
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(8, 16, 8, 16)
        nav_layout.setSpacing(4)
        nav_layout.setAlignment(Qt.AlignTop)

        for key in NAV_ORDER:
            screen_cls = SCREEN_REGISTRY[key]
            btn = QPushButton(screen_cls.title)
            btn.setObjectName("nav-btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, k=key: self.show_screen(k))
            nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn

        nav_layout.addStretch()
        version_lbl = QLabel("v2 alpha")
        version_lbl.setStyleSheet("color: #4b5563; font-size: 11px;")
        version_lbl.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(version_lbl)

        body_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        body_layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        # ---- instantiate screens from the static registry ----
        for key in NAV_ORDER:
            screen_cls = SCREEN_REGISTRY[key]
            try:
                screen = screen_cls(game=self.game, main_window=self)
            except Exception as e:
                print(f"[v2] screen '{key}' failed to construct: {e}")
                screen = QLabel(f"Screen '{key}' failed to load: {e}")
                screen.setAlignment(Qt.AlignCenter)
            self._screens[key] = screen
            self.stack.addWidget(screen)

        # Keyboard shortcut: Space = Continue
        cont_action = QAction(self)
        cont_action.setShortcut(Qt.Key_Space)
        cont_action.triggered.connect(self.on_continue)
        self.addAction(cont_action)

        self.refresh()
        if NAV_ORDER:
            self.show_screen(NAV_ORDER[0])

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    def show_screen(self, screen_name):
        screen = self._screens.get(screen_name)
        if screen is None:
            print(f"[v2] unknown screen: {screen_name}")
            return
        try:
            if hasattr(screen, "refresh"):
                screen.refresh()
        except Exception as e:
            print(f"[v2] refresh failed for '{screen_name}': {e}")
        self.stack.setCurrentWidget(screen)
        for key, btn in self._nav_buttons.items():
            btn.setChecked(key == screen_name)

    def refresh(self):
        gm = resolve_gm(self.game)
        date = safe(lambda: str(getattr(gm, "current_date", "") or ""), "")
        self._date_lbl.setText(date)
        cur = self.stack.currentWidget()
        if cur is not None and hasattr(cur, "refresh"):
            try:
                cur.refresh()
            except Exception as e:
                print(f"[v2] refresh failed: {e}")

    # ------------------------------------------------------------------
    # game loop
    # ------------------------------------------------------------------
    def on_continue(self):
        """Advance one day. Direct Python call -- no HTTP."""
        if not self.game:
            return
        try:
            blockers = []
            if hasattr(self.game, "get_continue_state"):
                _label, blockers = self.game.get_continue_state()
            if blockers:
                n = len(blockers)
                first = safe(lambda: str(blockers[0]), "?")
                QMessageBox.information(
                    self, "Blocked",
                    f"{n} blocker(s) need attention.\n\nFirst: {first}\n\n"
                    "(Blocker UI not yet in v2 — resolve via v1 build.)")
                return
            if hasattr(self.game, "simulate_day"):
                self.game.simulate_day()
            self.refresh()
        except Exception as e:
            print(f"[v2] continue failed: {e}")
            QMessageBox.warning(self, "Continue failed", str(e))


def run(game=None):
    """Launch the v2 application. Returns the QApplication exit code."""
    app = QApplication(sys.argv)
    app.setApplicationName("Puck Dynasty")
    app.setOrganizationName("Puck Dynasty")
    app.setStyleSheet(THEME_QSS)
    window = MainWindow(game=game)
    window.showMaximized()
    return app.exec()
