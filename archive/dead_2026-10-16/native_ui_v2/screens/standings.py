"""Standings screen (v2): league standings with real game data.

Full 32-team table: GP, W, L, OTL, PTS, GF, GA, diff, streak.
User's team row is highlighted. Data read directly from the GameManager.

Import-time safe: no game logic runs at import time.
"""
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen, resolve_gm, safe


class StandingsScreen(BaseScreen):
    """League standings table with conference filter."""

    title = "Standings"
    screen_key = "standings"

    def _build_body(self):
        # Filter row
        filter_row = QHBoxLayout()
        filter_lbl = QLabel("Conference:")
        filter_lbl.setStyleSheet("color: #9aa4b8;")
        self._conf_combo = QComboBox()
        self._conf_combo.addItems(["All", "Eastern", "Western"])
        self._conf_combo.currentTextChanged.connect(self.refresh)
        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(self._conf_combo)
        filter_row.addStretch()
        self._layout.addLayout(filter_row)

        self._table = QTableWidget()
        self._table.setColumnCount(10)
        self._table.setHorizontalHeaderLabels(
            ["TEAM", "GP", "W", "L", "OTL", "PTS", "GF", "GA", "DIFF", "STRK"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._layout.addWidget(self._table)

        self.refresh()

    def _rows(self):
        gm = resolve_gm(self.game)
        league = safe(lambda: gm.league)
        if league is None:
            return [], None
        table = safe(lambda: dict(league.standings), {}) or {}
        teams = safe(lambda: list(league.teams), []) or []
        user_team_name = safe(lambda: league.user_team.team_name, "")

        rows = []
        for t in teams:
            try:
                name = safe(lambda: t.team_name, "")
                if not name:
                    continue
                row = table.get(name, {})
                w = safe(lambda: int(row.get("W", 0) or 0), 0)
                l = safe(lambda: int(row.get("L", 0) or 0), 0)
                otl = safe(lambda: int(row.get("OTL", 0) or 0), 0)
                pts = safe(lambda: int(row.get("Points", 0) or 0), 0)
                gf = safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0)
                ga = safe(lambda: int(getattr(t, "goals_against", 0) or 0), 0)
                rows.append({
                    "name": name,
                    "conf": safe(lambda: t.conference, "") or "",
                    "gp": w + l + otl, "w": w, "l": l, "otl": otl,
                    "pts": pts, "gf": gf, "ga": ga, "diff": gf - ga,
                    "streak": safe(lambda: str(getattr(t, "streak", "") or ""), ""),
                    "is_user": (safe(lambda: bool(t.is_user_team), False)
                                or name == user_team_name),
                })
            except Exception:
                continue
        rows.sort(key=lambda r: (-r["pts"], -r["w"], r["name"]))
        return rows, user_team_name

    def refresh(self):
        rows, user_team_name = self._rows()
        conf_filter = self._conf_combo.currentText()
        if conf_filter != "All":
            rows = [r for r in rows if r["conf"] == conf_filter]

        highlight = QColor(30, 58, 95)  # user team row
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r["name"], str(r["gp"]), str(r["w"]), str(r["l"]),
                    str(r["otl"]), str(r["pts"]), str(r["gf"]), str(r["ga"]),
                    f"{r['diff']:+d}", r["streak"]]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col >= 1:
                    item.setTextAlignment(Qt.AlignCenter)
                if r["is_user"]:
                    item.setBackground(highlight)
                self._table.setItem(i, col, item)
