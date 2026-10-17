"""Base screen class for native_ui_v2.

Every screen gets a direct reference to the game object and the main
window for navigation. No HTTP, no serialization -- just Python calls.

Import-time safe: this module performs no game logic, no filesystem
access, and no heavy initialization at import time.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


def safe(fn, default=None):
    """Call fn(), return default on any exception. Shared helper."""
    try:
        return fn()
    except Exception:
        return default


def resolve_gm(game):
    """Return the GameManager from a game object or the object itself."""
    return safe(lambda: getattr(game, "game_manager", None)) or game


class BaseScreen(QWidget):
    """Base class for all v2 game screens."""

    #: Human-readable name shown in nav
    title = "Screen"
    #: Key used in the static screen registry
    screen_key = "base"

    def __init__(self, game, main_window, parent=None):
        super().__init__(parent)
        self.game = game
        self.main_window = main_window
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 16, 24, 16)
        self._layout.setSpacing(12)
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = QLabel(self.title.upper())
        header.setObjectName("section-header")
        self._layout.addWidget(header)

    def _build_body(self):
        """Override in subclasses to build the screen content."""
        placeholder = QLabel(f"{self.title} — coming soon")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #6b7488; font-size: 16px;")
        self._layout.addWidget(placeholder)
        self._layout.addStretch()

    def refresh(self):
        """Reload data from the game object. Called on navigation."""
        pass

    def navigate_to(self, screen_name):
        """Navigate to another screen."""
        self.main_window.show_screen(screen_name)
