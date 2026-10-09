"""Dashboard screen (v2): team overview with real game data.

Shows the user's team name, record, goals for/against, and streak.
All data read directly from the GameManager -- no placeholders.

Import-time safe: no game logic runs at import time.
"""
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from .base import BaseScreen, resolve_gm, safe


class DashboardScreen(BaseScreen):
    """Team dashboard: record, goals, streak at a glance."""

    title = "Dashboard"
    screen_key = "dashboard"

    def _build_body(self):
        self._tiles = {}
        grid = QGridLayout()
        grid.setSpacing(12)

        for i, (key, label) in enumerate([
            ("record", "RECORD"),
            ("points", "POINTS"),
            ("goals", "GOALS FOR / AGAINST"),
            ("streak", "STREAK"),
        ]):
            tile = QFrame()
            tile.setObjectName("tile")
            vbox = QVBoxLayout(tile)
            title_lbl = QLabel(label)
            title_lbl.setObjectName("tile-title")
            value_lbl = QLabel("--")
            value_lbl.setObjectName("tile-value")
            sub_lbl = QLabel("")
            sub_lbl.setObjectName("tile-sub")
            vbox.addWidget(title_lbl)
            vbox.addWidget(value_lbl)
            vbox.addWidget(sub_lbl)
            grid.addWidget(tile, 0, i)
            self._tiles[key] = (value_lbl, sub_lbl)

        self._layout.addLayout(grid)

        # Team info line
        self._team_lbl = QLabel("")
        self._team_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(self._team_lbl)
        self._layout.addStretch()

        self.refresh()

    def refresh(self):
        gm = resolve_gm(self.game)
        team = safe(lambda: gm.user_team)
        if team is None:
            for value_lbl, sub_lbl in self._tiles.values():
                value_lbl.setText("--")
                sub_lbl.setText("no career started")
            self._team_lbl.setText("Start a new career to see your dashboard.")
            return

        team_name = safe(lambda: team.team_name, "Unknown")
        league = safe(lambda: gm.league)
        standings = safe(lambda: dict(league.standings), {}) if league else {}
        row = standings.get(team_name, {})

        w = safe(lambda: int(row.get("W", 0) or 0), 0)
        l = safe(lambda: int(row.get("L", 0) or 0), 0)
        otl = safe(lambda: int(row.get("OTL", 0) or 0), 0)
        pts = safe(lambda: int(row.get("Points", 0) or 0), 0)
        gf = safe(lambda: int(getattr(team, "goals_for", 0) or 0), 0)
        ga = safe(lambda: int(getattr(team, "goals_against", 0) or 0), 0)
        streak = safe(lambda: str(getattr(team, "streak", "") or ""), "")
        date = safe(lambda: str(getattr(gm, "current_date", "") or ""), "")

        self._tiles["record"][0].setText(f"{w}-{l}-{otl}")
        self._tiles["record"][1].setText(f"{w + l + otl} games played")
        self._tiles["points"][0].setText(str(pts))
        self._tiles["points"][1].setText(
            f"{pts / (2 * (w + l + otl)):.3f} pts%" if (w + l + otl) else "")
        self._tiles["goals"][0].setText(f"{gf} / {ga}")
        self._tiles["goals"][1].setText(f"{gf - ga:+d} differential")
        self._tiles["streak"][0].setText(streak or "--")
        self._tiles["streak"][1].setText("current streak")

        self._team_lbl.setText(f"{team_name}  •  {date}")
