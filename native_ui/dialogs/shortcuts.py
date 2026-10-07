"""Keyboard shortcuts cheat-sheet dialog.

Ports main.py show_shortcuts_dialog. A simple reference dialog listing
every keyboard shortcut available in the native app.
"""
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QPushButton, QVBoxLayout,
)
from PySide6.QtCore import Qt

# Shortcut definitions: (key label, description)
SHORTCUT_ROWS = [
    ("Space", "Continue — advance to the next day"),
    ("Ctrl+S", "Quick save the game"),
    ("Esc", "Back to the hub (closes this dialog)"),
    ("?", "Show this cheat sheet"),
    ("1", "Hub"),
    ("2", "Roster"),
    ("3", "Lines"),
    ("4", "Team"),
    ("5", "Inbox"),
    ("6", "Standings"),
    ("7", "Stats"),
    ("8", "Trades"),
    ("9", "Schedule"),
]


class ShortcutsDialog(QDialog):
    """Modal cheat-sheet listing all keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        title = QLabel("Keyboard Shortcuts")
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        note = QLabel("Shortcuts stay quiet while you are typing in a text field.")
        note.setObjectName("dialog-note")
        note.setStyleSheet("color: #71717a; font-style: italic;")
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        for i, (key, desc) in enumerate(SHORTCUT_ROWS):
            key_label = QLabel(key)
            key_label.setObjectName("shortcut-key")
            key_label.setAlignment(Qt.AlignCenter)
            key_label.setMinimumWidth(70)
            key_label.setStyleSheet(
                "background: #1e1e24; color: #3B82F6; font-weight: bold; "
                "padding: 6px 10px; border-radius: 4px;"
            )
            grid.addWidget(key_label, i, 0)

            desc_label = QLabel(desc)
            desc_label.setObjectName("shortcut-desc")
            desc_label.setStyleSheet("color: #a1a1aa;")
            grid.addWidget(desc_label, i, 1)

        layout.addLayout(grid)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary-btn")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)


def show_shortcuts(parent=None):
    """Show the shortcuts cheat-sheet dialog."""
    dlg = ShortcutsDialog(parent)
    dlg.exec()
