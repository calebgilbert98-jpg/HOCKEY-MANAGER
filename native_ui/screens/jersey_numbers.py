"""Jersey Numbers: full roster, click to reassign.

Port of main.open_jersey_numbers_window. The Tkinter version opens as a
NON-MODAL popup; for native this is a regular screen (simpler, fine).

Rules (same as main.assign_jersey_number):
- Numbers are 1-98, validated client-side.
- Retired numbers stay retired -- the rafters are not negotiable.
- Goalie numbers stay with goalies (1 and 30 are skater-barred).
- Duplicates are blocked across the NHL + AHL rosters (shared pool).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QInputDialog, QMessageBox,
    QHeaderView,
)
from PySide6.QtCore import Qt

from .base import BaseScreen

try:
    import immortality as _im
except Exception:
    _im = None


class _NumericItem(QTableWidgetItem):
    """Table item that sorts numerically on its stored value."""

    def __init__(self, text, value):
        super().__init__(text)
        try:
            self.setData(Qt.UserRole, int(value))
        except Exception:
            self.setData(Qt.UserRole, 0)

    def __lt__(self, other):
        try:
            return self.data(Qt.UserRole) < other.data(Qt.UserRole)
        except Exception:
            return super().__lt__(other)


class JerseyNumbersScreen(BaseScreen):
    """Click-to-reassign jersey numbers for the full roster."""

    title = "Jersey Numbers"

    def _build_body(self):
        explainer = QLabel(
            "Click a player (or double-click the row) to reassign their "
            "number. Numbers 1-98 only. Retired numbers stay retired, "
            "goalie numbers (1, 30) stay with goalies, duplicates blocked.")
        explainer.setWordWrap(True)
        explainer.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._layout.addWidget(explainer)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["#", "C", "Player", "Pos", "OVR"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for col, width in ((0, 60), (1, 40), (3, 90), (4, 70)):
            self._table.setColumnWidth(col, width)
        self._table.setAlternatingRowColors(True)
        self._table.itemDoubleClicked.connect(self._on_reassign)
        self._layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        self._reassign_btn = QPushButton("Reassign Selected")
        self._reassign_btn.setObjectName("primary-btn")
        self._reassign_btn.clicked.connect(self._on_reassign)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self._reassign_btn)
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        self._layout.addLayout(btn_row)

        self._retired_lbl = QLabel("")
        self._retired_lbl.setWordWrap(True)
        self._retired_lbl.setStyleSheet("color: #9aa4b8; font-size: 11px;")
        self._layout.addWidget(self._retired_lbl)

        self._players = []
        self.refresh()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    @staticmethod
    def _pos_str(p):
        return getattr(getattr(p, "primary_position", None), "name", "?")

    @staticmethod
    def _ovr(p):
        try:
            return int(p.overall_rating())
        except Exception:
            return 0

    @staticmethod
    def _is_goalie(p):
        try:
            from game_classes import PlayerPosition as _PP
            return getattr(p, "primary_position", None) == _PP.GOALIE
        except Exception:
            return False

    def refresh(self):
        if self.game is None:
            return
        try:
            team = getattr(self.game, "user_team", None)
            roster = sorted(
                list(getattr(team, "roster", None) or []),
                key=lambda p: (int(getattr(p, "jersey_number", 99) or 99),
                               getattr(p, "full_name", "") or ""))
        except Exception:
            team, roster = None, []
        self._players = roster
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(roster))
        for row, p in enumerate(roster):
            num = int(getattr(p, "jersey_number", 0) or 0)
            cap = getattr(p, "captaincy", "") or ""
            items = [
                _NumericItem(f"#{num}", num),
                QTableWidgetItem(str(cap)),
                QTableWidgetItem(getattr(p, "full_name", "?")),
                QTableWidgetItem(self._pos_str(p)),
                _NumericItem(str(self._ovr(p)), self._ovr(p)),
            ]
            items[2].setData(Qt.UserRole + 1, p)
            for col, item in enumerate(items):
                self._table.setItem(row, col, item)
        self._table.setSortingEnabled(True)
        # Footer: team's retired numbers, for reference.
        try:
            retired = _im.retired_numbers(team) if _im else []
            nums = sorted(
                {int(r.get("number")) for r in (retired or [])
                 if str(r.get("number", "")).isdigit()})
            if nums:
                tname = getattr(team, "team_name", "Team")
                self._retired_lbl.setText(
                    f"Retired by {tname}: "
                    + ", ".join(f"#{n}" for n in nums))
            else:
                self._retired_lbl.setText("")
        except Exception:
            self._retired_lbl.setText("")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _selected_player(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._players):
            return self._players[row]
        return None

    def _on_reassign(self, *args):
        p = self._selected_player()
        if p is None:
            QMessageBox.information(
                self, "Jersey Numbers", "Select a player first.")
            return
        name = getattr(p, "full_name", "?")
        current = int(getattr(p, "jersey_number", 0) or 0)
        # Client-side validation: 1-98 enforced by the dialog bounds.
        new_number, ok = QInputDialog.getInt(
            self, "Assign Jersey Number",
            f"Enter a new jersey number for {name}:",
            value=current if current else 1, min=1, max=98)
        if not ok:
            return
        team = getattr(self.game, "user_team", None)
        goalie = self._is_goalie(p)
        blocked_reason = None
        if _im is not None:
            try:
                if not _im.number_selectable(team, new_number, goalie):
                    if (_im.is_number_retired(team, new_number)):
                        blocked_reason = (
                            "Retired Number",
                            f"No. {new_number} is retired by "
                            f"{getattr(team, 'team_name', 'the team')} "
                            "-- pick another.")
                    elif (not goalie
                          and int(new_number)
                          in _im.SKATER_BARRED_NUMBERS):
                        blocked_reason = (
                            "Goalie Number",
                            f"No. {new_number} is reserved for "
                            "goaltenders -- pick another.")
                    else:
                        blocked_reason = (
                            "Number Taken",
                            f"No. {new_number} is unavailable "
                            "-- pick another.")
            except Exception:
                pass
        if blocked_reason:
            QMessageBox.warning(self, blocked_reason[0], blocked_reason[1])
            return
        try:
            p.jersey_number = int(new_number)
            try:
                p.jersey_number_since = int(
                    getattr(getattr(self.game, "league", None),
                            "season_year", 2026))
            except Exception:
                pass
            QMessageBox.information(
                self, "Jersey Numbers",
                f"{name} now wears No. {new_number}.")
        except Exception as exc:
            QMessageBox.warning(self, "Jersey Numbers",
                                f"Could not assign: {exc}")
            return
        self.refresh()
