"""Offseason Programs: GM assigns summer training focuses (June-Aug).

Port of main.open_offseason_programs_window (Tkinter non-modal popup).

Each player gets one focus + intensity; weekly development ticks run
through July and August (no game fatigue in summer, smaller gains than
in-season programs). Results surface at training camp (Sept 12-30).
"""
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QComboBox, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt

from .base import BaseScreen

try:
    import offseason_programs as _osp
except Exception:
    _osp = None


class OffseasonProgramsScreen(BaseScreen):
    """Assign summer training focuses per player."""

    title = "Offseason"

    def _build_body(self):
        explainer = QLabel(
            "Assign a summer focus per player. Weekly development ticks run "
            "through July and August -- no game fatigue, but smaller gains "
            "than in-season programs. Results show up in camp reports.")
        explainer.setWordWrap(True)
        explainer.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._layout.addWidget(explainer)

        self._window_lbl = QLabel("")
        self._window_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._layout.addWidget(self._window_lbl)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Player", "Pos", "Focus", "Intensity"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._sync_controls)
        self._layout.addWidget(self._table, 1)

        ctrl = QHBoxLayout()
        focuses = getattr(_osp, "OFFSEASON_FOCUSES", []) if _osp else []
        intensities = (getattr(_osp, "OFFSEASON_INTENSITIES", [])
                       if _osp else ["Light", "Standard", "Intensive"])
        ctrl.addWidget(QLabel("Focus:"))
        self._focus_combo = QComboBox()
        self._focus_combo.addItems(focuses)
        self._focus_combo.setEditable(False)
        ctrl.addWidget(self._focus_combo, 1)
        ctrl.addWidget(QLabel("Intensity:"))
        self._int_combo = QComboBox()
        self._int_combo.addItems(intensities)
        self._int_combo.setEditable(False)
        self._int_combo.setCurrentText("Standard")
        ctrl.addWidget(self._int_combo)
        self._layout.addLayout(ctrl)

        btn_row = QHBoxLayout()
        self._assign_btn = QPushButton("Assign to Selected")
        self._assign_btn.setObjectName("primary-btn")
        self._assign_btn.clicked.connect(self._on_assign)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self._assign_btn)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        self._layout.addLayout(btn_row)

        self._players = []
        self.refresh()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    @staticmethod
    def _pos_str(p):
        return getattr(getattr(p, "primary_position", None), "name", "?")

    def refresh(self):
        # Window status: programs run Jul-Aug, assigning opens in June.
        try:
            today = date.today()
            open_ = _osp.is_offseason(today) if _osp else False
            if open_:
                if today.month == 6:
                    status = ("Assigning is open -- weekly development runs "
                              "July-August.")
                else:
                    status = "Offseason window: programs are running."
            else:
                status = ("Offseason window closed (June-Aug). Assignments "
                          "below are view-only until the Cup is lifted.")
            self._window_lbl.setText(status)
        except Exception:
            pass
        if self.game is None:
            return
        try:
            team = getattr(self.game, "user_team", None)
            roster = sorted(
                list(getattr(team, "roster", None) or []),
                key=lambda p: getattr(p, "full_name", ""))
        except Exception:
            roster = []
        self._players = roster
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(roster))
        for row, p in enumerate(roster):
            focus, intensity = "--", "--"
            if _osp is not None:
                try:
                    prog = _osp.get_offseason_program(p)
                    if prog:
                        focus = str(prog.get("focus", "--"))
                        intensity = str(prog.get("intensity", "--"))
                except Exception:
                    pass
            items = [
                QTableWidgetItem(getattr(p, "full_name", "?")),
                QTableWidgetItem(self._pos_str(p)),
                QTableWidgetItem(focus),
                QTableWidgetItem(intensity),
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

    def _sync_controls(self):
        """Show the selected player's current program in the combos."""
        p = self._selected_player()
        if p is None or _osp is None:
            return
        try:
            prog = _osp.get_offseason_program(p)
            if prog:
                self._focus_combo.setCurrentText(str(prog.get("focus", "")))
                self._int_combo.setCurrentText(str(prog.get("intensity", "")))
        except Exception:
            pass

    def _on_assign(self):
        p = self._selected_player()
        if p is None:
            QMessageBox.information(
                self, "Offseason", "Select a player first.")
            return
        if _osp is None:
            return
        try:
            ok, msg = _osp.assign_offseason_program(
                p, self._focus_combo.currentText(),
                self._int_combo.currentText())
        except Exception as exc:
            ok, msg = False, str(exc)
        if not ok:
            QMessageBox.warning(self, "Offseason", msg)
            return
        self.refresh()

    def _on_clear(self):
        p = self._selected_player()
        if p is None or _osp is None:
            return
        try:
            _osp.clear_offseason_program(p)
        except Exception:
            pass
        self.refresh()
