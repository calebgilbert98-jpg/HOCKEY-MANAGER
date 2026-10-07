"""Setup wizard: GM profile, team select, quick start.

Ports web_ui/templates/setup.html. First screen shown when no career
is loaded.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QStackedWidget, QListWidget, QListWidgetItem, QMessageBox,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


class SetupScreen(BaseScreen):
    title = "Setup"

    def _build_body(self):
        # Title
        title = QLabel("PUCK DYNASTY")
        title.setStyleSheet(
            "font-size: 48px; font-weight: 900; color: #ffffff; "
            "letter-spacing: 4px;")
        title.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(title)

        sub = QLabel("HOCKEY MANAGER")
        sub.setObjectName("brand-sub")
        sub.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(sub)
        self._layout.addSpacing(24)

        # GM name
        form = QVBoxLayout()
        form.setSpacing(12)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("GM Name:"))
        self._gm_name = QLineEdit()
        self._gm_name.setPlaceholderText("Enter your name")
        name_row.addWidget(self._gm_name, 1)
        form.addLayout(name_row)

        # Team select
        team_row = QHBoxLayout()
        team_row.addWidget(QLabel("Team:"))
        self._team_combo = QComboBox()
        self._team_combo.setMinimumWidth(300)
        team_row.addWidget(self._team_combo, 1)
        form.addLayout(team_row)

        self._layout.addLayout(form)
        self._layout.addSpacing(24)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.addStretch()

        quick_btn = QPushButton("Quick Start")
        quick_btn.setObjectName("primary-btn")
        quick_btn.setCursor(Qt.PointingHandCursor)
        quick_btn.setToolTip(
            "Random GM + random team, default settings, start immediately")
        quick_btn.clicked.connect(self._quick_start)
        btn_row.addWidget(quick_btn)

        start_btn = QPushButton("Start Career")
        start_btn.setObjectName("primary-btn")
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.setEnabled(False)
        start_btn.clicked.connect(self._start_career)
        btn_row.addWidget(start_btn)
        self._start_btn = start_btn

        btn_row.addStretch()
        self._layout.addLayout(btn_row)
        self._layout.addStretch()

        # Enable Start when team selected
        self._team_combo.currentIndexChanged.connect(self._on_team_changed)
        self._gm_name.textChanged.connect(self._on_team_changed)

    def _on_team_changed(self):
        has_team = self._team_combo.currentIndex() >= 0
        has_name = bool(self._gm_name.text().strip())
        self._start_btn.setEnabled(has_team and has_name)

    def _quick_start(self):
        """Randomize GM profile and team, start immediately."""
        try:
            import random
            # TODO: call game.new_career with random settings
            QMessageBox.information(
                self, "Quick Start",
                "Quick Start will create a random career.")
        except Exception as e:
            QMessageBox.warning(self, "Quick Start", f"Failed: {e}")

    def _start_career(self):
        """Start a new career with the selected options."""
        try:
            gm_name = self._gm_name.text().strip()
            team = self._team_combo.currentData()
            # TODO: call game.new_career(gm_name, team)
            QMessageBox.information(
                self, "New Career",
                f"Starting career as {gm_name}...")
        except Exception as e:
            QMessageBox.warning(self, "New Career", f"Failed: {e}")

    def refresh(self):
        """Populate team list."""
        try:
            self._team_combo.clear()
            # TODO: get team list from game
            # For now, placeholder
            pass
        except Exception:
            pass
