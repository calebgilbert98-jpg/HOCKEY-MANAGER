"""Puck Dynasty native main window (PySide6).

Steam-style native application shell. Hosts the hub dashboard and all
game screens as Qt widgets. No browser, no HTTP -- direct Python calls
into the game logic.
"""
import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame, QGridLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from .theme import THEME_QSS


class TopBar(QWidget):
    """Application header: brand + nav + inbox/save."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self._main = main_window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # Brand
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand = QLabel("PUCK DYNASTY")
        brand.setObjectName("brand")
        brand_sub = QLabel("HOCKEY MANAGER")
        brand_sub.setObjectName("brand-sub")
        brand_box.addWidget(brand)
        brand_box.addWidget(brand_sub)
        layout.addLayout(brand_box)
        layout.addSpacing(24)

        # Nav buttons
        self._nav_buttons = {}
        for name in ["CLUB", "PERSONNEL", "LEAGUE", "TRANSACTIONS",
                     "FINANCES", "SYSTEMS"]:
            btn = QPushButton(name)
            btn.setObjectName("nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked, n=name: self._main.show_section(n))
            layout.addWidget(btn)
            self._nav_buttons[name] = btn

        layout.addStretch()

        # Inbox + Save
        self.inbox_btn = QPushButton("INBOX")
        self.inbox_btn.setObjectName("nav-btn")
        self.inbox_btn.setCursor(Qt.PointingHandCursor)
        self.inbox_btn.clicked.connect(self._main.show_inbox)
        layout.addWidget(self.inbox_btn)

        self.save_btn = QPushButton("SAVE")
        self.save_btn.setObjectName("nav-btn")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._main.save_game)
        layout.addWidget(self.save_btn)

    def set_active(self, name):
        for n, btn in self._nav_buttons.items():
            btn.setChecked(n == name)


class HubPage(QWidget):
    """Main dashboard: team header, tiles, standings, leaders, ticker."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self.setObjectName("hub-central")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(16)

        # Team header
        self.team_label = QLabel("—")
        self.team_label.setStyleSheet(
            "font-size: 32px; font-weight: 900; color: #ffffff;")
        self.record_label = QLabel("—")
        self.record_label.setStyleSheet(
            "font-size: 14px; color: #8b95ab;")
        outer.addWidget(self.team_label)
        outer.addWidget(self.record_label)

        # Continue button row
        btn_row = QHBoxLayout()
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setObjectName("primary-btn")
        self.continue_btn.setCursor(Qt.PointingHandCursor)
        self.continue_btn.clicked.connect(self._main.on_continue)
        btn_row.addWidget(self.continue_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        # Tile grid
        tile_grid = QGridLayout()
        tile_grid.setSpacing(12)
        self._tiles = {}
        tile_defs = [
            ("record", "RECORD", 0, 0),
            ("standing", "DIVISION", 0, 1),
            ("streak", "STREAK", 0, 2),
            ("cap", "CAP SPACE", 0, 3),
            ("next_game", "NEXT GAME", 1, 0),
            ("top_scorer", "TOP SCORER", 1, 1),
            ("injuries", "INJURIES", 1, 2),
            ("morale", "MORALE", 1, 3),
        ]
        for key, title, r, c in tile_defs:
            tile = self._make_tile(title)
            tile_grid.addWidget(tile, r, c)
            self._tiles[key] = tile
        outer.addLayout(tile_grid)

        outer.addStretch()

        # Ticker at bottom
        self.ticker = QLabel("Loading scores…")
        self.ticker.setObjectName("ticker")
        self.ticker.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.ticker)

    def _make_tile(self, title):
        frame = QFrame()
        frame.setObjectName("tile")
        frame.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        t = QLabel(title)
        t.setObjectName("tile-title")
        v = QLabel("—")
        v.setObjectName("tile-value")
        s = QLabel("")
        s.setObjectName("tile-sub")
        layout.addWidget(t)
        layout.addWidget(v)
        layout.addWidget(s)
        frame.mousePressEvent = lambda e, t=title: self._main.on_tile_click(t)
        # Store refs for updates
        frame._value_label = v
        frame._sub_label = s
        return frame

    def set_tile(self, key, value, sub=""):
        if key in self._tiles:
            self._tiles[key]._value_label.setText(str(value))
            self._tiles[key]._sub_label.setText(str(sub))

    def refresh(self, game):
        """Populate from the live game object. Direct Python access --
        no HTTP, no serialization."""
        try:
            team = getattr(game, "user_team", None)
            if team:
                self.team_label.setText(
                    getattr(team, "team_name", "—").upper())
            # TODO: wire real values from game state
            self.set_tile("record", "0-0-0", "Season record")
        except Exception:
            pass


class MainWindow(QMainWindow):
    """Puck Dynasty native application window."""

    def __init__(self, game=None):
        super().__init__()
        self.game = game  # HockeyManagerGUI or game manager instance
        self.setWindowTitle("Puck Dynasty")
        self.setMinimumSize(1280, 800)

        # Top bar
        self.topbar = TopBar(self)
        self.addToolBar(Qt.TopToolBarArea, self._wrap_topbar())

        # Central stacked widget for screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Hub page
        self.hub = HubPage(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.hub)
        scroll.setFrameShape(QFrame.NoFrame)
        self.stack.addWidget(scroll)

        # Apply theme
        self.setStyleSheet(THEME_QSS)

    def _wrap_topbar(self):
        from PySide6.QtWidgets import QToolBar
        tb = QToolBar()
        tb.setMovable(False)
        tb.addWidget(self.topbar)
        tb.setStyleSheet("QToolBar { border: none; padding: 0; margin: 0; }")
        return tb

    # --- Navigation ---
    def show_section(self, name):
        self.topbar.set_active(name)
        # TODO: switch to section pages
        print(f"[native] show_section: {name}")

    def show_inbox(self):
        print("[native] show_inbox")

    def save_game(self):
        print("[native] save_game")

    def on_tile_click(self, title):
        print(f"[native] tile clicked: {title}")

    def on_continue(self):
        """Direct Python call -- no HTTP round-trip."""
        if not self.game:
            return
        try:
            label, blockers = self.game.get_continue_state()
            if blockers:
                self.show_blockers(blockers)
            else:
                # TODO: advance day
                print(f"[native] continue: {label}")
        except Exception as e:
            print(f"[native] continue failed: {e}")

    def show_blockers(self, blockers):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("Can't advance yet")
        dlg.setMinimumWidth(600)
        layout = QVBoxLayout(dlg)
        title = QLabel(f"{len(blockers)} things need your attention")
        title.setObjectName("dialog-title")
        layout.addWidget(title)
        for b in blockers:
            card = QFrame()
            card.setObjectName("blocker-card")
            cl = QVBoxLayout(card)
            t = QLabel(b.get("title", "Blocker"))
            t.setObjectName("blocker-title")
            d = QLabel(b.get("detail", ""))
            d.setObjectName("blocker-detail")
            d.setWordWrap(True)
            cl.addWidget(t)
            cl.addWidget(d)
            layout.addWidget(card)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        dlg.exec()

    def refresh(self):
        if self.game:
            self.hub.refresh(self.game)


def run(game=None):
    """Launch the native Puck Dynasty application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Puck Dynasty")
    app.setOrganizationName("Puck Dynasty")
    window = MainWindow(game=game)
    window.showMaximized()
    window.refresh()
    return app.exec()
