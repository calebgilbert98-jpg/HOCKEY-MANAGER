"""Roster screen (v2): user team roster with real player data.

Lists every player on the user's NHL roster: name, position, overall,
age. Data read directly from the GameManager.

Import-time safe: no game logic runs at import time.
"""
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
)
from PySide6.QtCore import Qt

from .base import BaseScreen, resolve_gm, safe


_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}


def _clean_position(pos):
    try:
        s = str(pos or "")
        if "." in s:
            s = s.split(".")[-1]
        return _POSITION_ABBR.get(s.strip().upper(), s.strip().upper() or "?")
    except Exception:
        return "?"


class RosterScreen(BaseScreen):
    """User team roster table."""

    title = "Roster"
    screen_key = "roster"

    def _build_body(self):
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(self._count_lbl)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["PLAYER", "POS", "OVR", "AGE"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._layout.addWidget(self._table)

        self.refresh()

    def refresh(self):
        gm = resolve_gm(self.game)
        team = safe(lambda: gm.user_team)
        players = safe(lambda: list(team.roster), []) if team else []

        # Sort: skaters by overall desc, goalies last
        def _sort_key(p):
            ovr = safe(lambda: int(p.overall_rating()), 0)
            pos = _clean_position(safe(lambda: p.position, ""))
            return (0 if pos != "G" else 1, -ovr)

        try:
            players = sorted(players, key=_sort_key)
        except Exception:
            pass

        self._table.setRowCount(len(players))
        for i, p in enumerate(players):
            name = safe(lambda: str(p.name), "?")
            pos = _clean_position(safe(lambda: p.position, ""))
            ovr = safe(lambda: int(p.overall_rating()), 0)
            age = safe(lambda: int(getattr(p, "age", 0) or 0), 0)
            for col, val in enumerate([name, pos, str(ovr), str(age) if age else "--"]):
                item = QTableWidgetItem(val)
                if col >= 1:
                    item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(i, col, item)

        team_name = safe(lambda: team.team_name, "Unknown") if team else "No team"
        self._count_lbl.setText(f"{team_name} — {len(players)} players")
