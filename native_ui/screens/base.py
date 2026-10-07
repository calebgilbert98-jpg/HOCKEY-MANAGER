"""Base screen class for all native UI pages.

Every screen gets a direct reference to the game object and a reference
to the main window for navigation. No HTTP, no serialization -- just
Python method calls.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class BaseScreen(QWidget):
    """Base class for all game screens."""

    #: Human-readable name shown in nav
    title = "Screen"

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
        """Screen title header."""
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
