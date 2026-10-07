"""Season Goals: GM sets per-player season targets in preseason.

Port of main.open_season_goals_window (Tkinter non-modal popup).

Hit: +4 to two relevant attributes, +5 potential, +10 morale (young
<24 who smash the goal by 20%+ can also jump a potential grade).
Miss: -5 morale, no attribute penalty -- ambition is rewarded, not
punished. Includes the nested "Set Goal" dialog (300x180-style).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QDialog, QFormLayout, QComboBox,
    QSpinBox, QDialogButtonBox, QMessageBox, QHeaderView,
)
from PySide6.QtCore import Qt

from .base import BaseScreen

try:
    import season_goals as _sg
except Exception:
    _sg = None


class _NumericItem(QTableWidgetItem):
    """Table item that sorts numerically on its stored value."""

    def __init__(self, text, value):
        super().__init__(text)
        try:
            self.setData(Qt.UserRole, float(value))
        except Exception:
            self.setData(Qt.UserRole, 0.0)

    def __lt__(self, other):
        try:
            return self.data(Qt.UserRole) < other.data(Qt.UserRole)
        except Exception:
            return super().__lt__(other)


class SetGoalDialog(QDialog):
    """Nested "Set Goal" dialog: pick goal type + target for one player."""

    def __init__(self, player, team, parent=None):
        super().__init__(parent)
        self._player = player
        self._team = team
        self.setWindowTitle("Set Goal")
        self.setFixedSize(320, 210)

        layout = QVBoxLayout(self)
        name = getattr(player, "full_name", "?")
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        name_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_lbl)

        form = QFormLayout()
        self._type_combo = QComboBox()
        self._types = {}
        if _sg is not None:
            try:
                self._types = dict(_sg.available_goal_types(player))
            except Exception:
                self._types = {}
        for key, spec in self._types.items():
            label = spec[1] if len(spec) > 1 else key
            self._type_combo.addItem(f"{key} ({label})", key)
        form.addRow("Type:", self._type_combo)

        self._target_spin = QSpinBox()
        self._target_spin.setRange(1, 999)
        self._target_spin.setValue(20)
        form.addRow("Target:", self._target_spin)
        layout.addLayout(form)

        self._reward_lbl = QLabel("")
        self._reward_lbl.setWordWrap(True)
        self._reward_lbl.setStyleSheet("color: #9aa4b8; font-size: 11px;")
        layout.addWidget(self._reward_lbl)
        self._type_combo.currentIndexChanged.connect(self._update_reward)
        self._update_reward()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_reward(self):
        key = self._type_combo.currentData()
        try:
            spec = self._types.get(key)
            attrs = spec[3] if spec and len(spec) > 3 else []
            pretty = ", ".join(a.replace("_", " ") for a in attrs[:2])
            self._reward_lbl.setText(
                f"Reward on hit: +4 {pretty}, +5 potential, morale surge. "
                "Miss: -5 morale.")
        except Exception:
            self._reward_lbl.setText("")

    def _on_ok(self):
        key = self._type_combo.currentData()
        target = int(self._target_spin.value())
        if _sg is None or not key:
            self.reject()
            return
        try:
            ok, msg = _sg.set_season_goal(
                self._player, key, target, team=self._team)
        except Exception as exc:
            ok, msg = False, str(exc)
        if not ok:
            # One-per-type rejection: keep the dialog open so the GM can
            # pick a different type instead of silently closing.
            QMessageBox.warning(self, "Goal Taken", msg)
            return
        self.accept()


class SeasonGoalsScreen(BaseScreen):
    """Set per-player season goals in preseason."""

    title = "Season Goals"

    def _build_body(self):
        explainer = QLabel(
            "Set a target per player. Hit it: +4 to two skills, +5 potential, "
            "+10 morale. Miss: -5 morale, no attribute penalty.\n"
            "One goal type per team -- a teammate must clear theirs before "
            "you reassign it.")
        explainer.setWordWrap(True)
        explainer.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._layout.addWidget(explainer)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Player", "Pos", "OVR", "Goal", "Progress"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.itemDoubleClicked.connect(self._on_set_goal)
        self._layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        self._set_btn = QPushButton("Set Goal")
        self._set_btn.setObjectName("primary-btn")
        self._set_btn.clicked.connect(self._on_set_goal)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear_goal)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self._set_btn)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        self._layout.addLayout(btn_row)

        self._players = []
        self.refresh()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _roster(self):
        try:
            team = getattr(self.game, "user_team", None)
            roster = list(getattr(team, "roster", None) or [])
            roster.sort(key=lambda p: getattr(p, "full_name", ""))
            return team, roster
        except Exception:
            return None, []

    @staticmethod
    def _pos_str(p):
        return getattr(getattr(p, "primary_position", None), "name", "?")

    @staticmethod
    def _ovr(p):
        try:
            return int(p.overall_rating())
        except Exception:
            return 0

    def _goal_text(self, p):
        """(goal label, progress text) for one player."""
        if _sg is None:
            return "--", "--"
        try:
            goal = _sg.get_season_goal(p)
            prog = _sg.goal_progress(p)
        except Exception:
            return "--", "--"
        if goal and prog:
            label = (f"{prog['label']}: {prog['target']}")
            if prog.get("hit"):
                progress = "HIT"
            else:
                progress = (f"{prog['current']}/{prog['target']} "
                            f"({prog['pct']}%)")
            return label, progress
        if goal:
            return f"{goal.get('type')}: {goal.get('target')}", "--"
        return "--", "--"

    def refresh(self):
        if self.game is None:
            return
        team, roster = self._roster()
        self._players = roster
        self._team = team
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(roster))
        for row, p in enumerate(roster):
            goal_label, progress = self._goal_text(p)
            items = [
                QTableWidgetItem(getattr(p, "full_name", "?")),
                QTableWidgetItem(self._pos_str(p)),
                _NumericItem(str(self._ovr(p)), self._ovr(p)),
                QTableWidgetItem(goal_label),
                QTableWidgetItem(progress),
            ]
            items[0].setData(Qt.UserRole + 1, p)
            for col, item in enumerate(items):
                self._table.setItem(row, col, item)
        self._table.setSortingEnabled(True)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _selected_player(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._players):
            return self._players[row]
        return None

    def _on_set_goal(self, *args):
        p = self._selected_player()
        if p is None:
            QMessageBox.information(
                self, "Season Goals", "Select a player first.")
            return
        dlg = SetGoalDialog(p, getattr(self, "_team", None), self)
        if dlg.exec():
            self.refresh()

    def _on_clear_goal(self):
        p = self._selected_player()
        if p is None or _sg is None:
            return
        try:
            _sg.clear_season_goal(p)
        except Exception:
            pass
        self.refresh()
