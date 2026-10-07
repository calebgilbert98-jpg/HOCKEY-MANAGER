"""Captains: current C/A display, picker dropdowns, candidate list.

Calls the game object directly -- no Flask/HTTP. Validation uses the
real game validators when available
(GameManager._validate_captaincy_pick / _persist_captaincy_pick, the
same by-name flow the manual Set Captains tool uses), with a
client-side fallback (same player cannot hold two letters) and a
manual captaincy-flag fallback when the game methods are missing.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


class CaptainsScreen(BaseScreen):
    title = "Captains"

    def _build_body(self):
        # Current C/A display block
        self._current_slots = {}
        cur_row = QHBoxLayout()
        cur_row.setSpacing(16)
        for slot_id, letter in (("c", "C"), ("a1", "A"), ("a2", "A")):
            frame = QFrame()
            frame.setObjectName("tile")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(18, 12, 18, 12)
            letter_lbl = QLabel(letter)
            letter_lbl.setStyleSheet(
                "color: #3B82F6; font-size: 36px; font-weight: 800;")
            letter_lbl.setAlignment(Qt.AlignCenter)
            name_lbl = QLabel("—")
            name_lbl.setStyleSheet(
                "color: #ffffff; font-size: 15px; font-weight: 700;")
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setWordWrap(True)
            layout.addWidget(letter_lbl)
            layout.addWidget(name_lbl)
            cur_row.addWidget(frame, 1)
            self._current_slots[slot_id] = name_lbl
        self._layout.addLayout(cur_row)

        # Picker
        pick_head = QLabel("CHOOSE NEW CAPTAINCY")
        pick_head.setObjectName("section-header")
        self._layout.addWidget(pick_head)
        picker = QHBoxLayout()
        picker.setSpacing(16)
        self._combos = {}
        for slot_id, label in (("c", "Captain (C)"),
                               ("a1", "Alternate (A)"),
                               ("a2", "Alternate (A)")):
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            lab = QLabel(label)
            lab.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            combo = QComboBox()
            combo.setMinimumWidth(220)
            wrap_layout.addWidget(lab)
            wrap_layout.addWidget(combo)
            picker.addWidget(wrap)
            self._combos[slot_id] = combo
        picker.addStretch()
        self._layout.addLayout(picker)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Set captains")
        save_btn.setObjectName("primary-btn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #eab308; font-size: 13px;")
        self._status.setWordWrap(True)
        btn_row.addWidget(self._status, 1)
        self._layout.addLayout(btn_row)

        # Candidates (ranked by leadership, then overall)
        cand_head = QLabel("CANDIDATES")
        cand_head.setObjectName("section-header")
        self._layout.addWidget(cand_head)
        note = QLabel("Ranked by leadership, then overall.")
        note.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(note)

        self._cand_table = QTableWidget()
        self._cand_table.setColumnCount(4)
        self._cand_table.setHorizontalHeaderLabels(
            ["PLAYER", "POS", "OVR", "LEADERSHIP"])
        self._cand_table.verticalHeader().setVisible(False)
        self._cand_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._cand_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._cand_table.setSortingEnabled(True)
        header = self._cand_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self._cand_table.setMinimumHeight(200)
        self._layout.addWidget(self._cand_table, 1)

    # --- game access -------------------------------------------------------
    def _team(self):
        for src in (self.game,
                    getattr(self.game, "game_manager", None)
                    if self.game is not None else None):
            if src is None:
                continue
            try:
                team = getattr(src, "user_team", None)
            except Exception:
                team = None
            if team is not None:
                return team
        return None

    def _roster(self):
        team = self._team()
        try:
            return list(getattr(team, "roster", None) or [])
        except Exception:
            return []

    @staticmethod
    def _leadership(p):
        try:
            return int(getattr(p, "leadership", 0) or 0)
        except Exception:
            return 0

    @staticmethod
    def _overall(p):
        try:
            return int(getattr(p, "overall_rating")())
        except Exception:
            try:
                return int(getattr(p, "overall", 50))
            except Exception:
                return 50

    @staticmethod
    def _pos_str(p):
        pos = getattr(p, "position", getattr(p, "primary_position", "?"))
        return getattr(pos, "value", str(pos))

    # --- refresh -----------------------------------------------------------
    def refresh(self):
        roster = self._roster()

        # Current letters
        cur = {"c": None, "a1": None, "a2": None}
        alts = []
        for p in roster:
            letter = (getattr(p, "captaincy", "") or "").strip()
            if letter == "C" and cur["c"] is None:
                cur["c"] = p
            elif letter == "A":
                alts.append(p)
        if alts:
            cur["a1"] = alts[0]
        if len(alts) > 1:
            cur["a2"] = alts[1]
        for slot_id, name_lbl in self._current_slots.items():
            p = cur[slot_id]
            name_lbl.setText(getattr(p, "full_name", "—") if p else "—")

        # Dropdowns (leadership-sorted, current holders preselected)
        ordered = sorted(roster,
                         key=lambda p: (-self._leadership(p),
                                        -self._overall(p),
                                        getattr(p, "full_name", "") or ""))
        for slot_id, combo in self._combos.items():
            combo.blockSignals(True)
            combo.clear()
            selected = 0
            for i, p in enumerate(ordered):
                label = getattr(p, "full_name", "?") or "?"
                letter = (getattr(p, "captaincy", "") or "").strip()
                if letter in ("C", "A"):
                    label = f"{label} ({letter})"
                combo.addItem(label, p)
                if cur[slot_id] is not None and p is cur[slot_id]:
                    selected = i
            if ordered:
                combo.setCurrentIndex(selected)
            combo.blockSignals(False)

        # Candidate table
        self._cand_table.setSortingEnabled(False)
        self._cand_table.setRowCount(len(ordered))
        for row, p in enumerate(ordered):
            vals = [
                getattr(p, "full_name", "?") or "?",
                self._pos_str(p),
                str(self._overall(p)),
                str(self._leadership(p)),
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col >= 2:
                    try:
                        item.setData(Qt.UserRole, int(val))
                    except (ValueError, TypeError):
                        pass
                self._cand_table.setItem(row, col, item)
        self._cand_table.setSortingEnabled(True)
        self._cand_table.sortByColumn(3, Qt.DescendingOrder)

    # --- save ---------------------------------------------------------------
    def _validate_pick(self, cap, a1, a2):
        """Client-side validation: same player cannot hold two letters."""
        names = {
            "captain": getattr(cap, "full_name", "") or "",
            "alt1": getattr(a1, "full_name", "") or "",
            "alt2": getattr(a2, "full_name", "") or "",
        }
        if not cap or not a1 or not a2:
            return "Select a player for the C and both As."
        if cap is a1 or cap is a2:
            return ("One player cannot wear both the C and an A — "
                    "pick a different alternate.")
        if a1 is a2:
            return "Pick two different alternate captains."
        # Full game validation (goalie letter rules, etc.) when available.
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            validate = getattr(gm, "_validate_captaincy_pick", None)
            if validate is not None and self._team() is not None:
                err = validate(self._team(), names["captain"],
                               names["alt1"], names["alt2"])
                if err:
                    return str(err)
        except Exception:
            pass
        return None

    def _save(self):
        cap = self._combos["c"].currentData()
        a1 = self._combos["a1"].currentData()
        a2 = self._combos["a2"].currentData()

        err = self._validate_pick(cap, a1, a2)
        if err:
            self._status.setText(err)
            return

        team = self._team()
        if team is None:
            self._status.setText("No team loaded.")
            return

        names = [getattr(p, "full_name", "") or ""
                 for p in (cap, a1, a2)]
        persisted = False
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            persist = getattr(gm, "_persist_captaincy_pick", None)
            if persist is not None:
                persist(team, *names)
                persisted = True
        except Exception as e:
            self._status.setText(f"Save failed: {e}")
            return

        if not persisted:
            # Manual fallback: mirror the bridge set_captains op.
            try:
                roster = self._roster()
                for p in roster:
                    if (getattr(p, "captaincy", "") or "") in ("C", "A"):
                        p.captaincy = ""
                by_name = {getattr(p, "full_name", ""): p for p in roster}
                if names[0] in by_name:
                    by_name[names[0]].captaincy = "C"
                for n in names[1:]:
                    q = by_name.get(n)
                    if q is not None and q is not by_name.get(names[0]):
                        q.captaincy = "A"
                try:
                    team._captaincy_auto_assigned = False
                except Exception:
                    pass
            except Exception as e:
                self._status.setText(f"Save failed: {e}")
                return

        # Same as the bridge op: clear the pending-captaincy blocker flag.
        try:
            gm = getattr(self.game, "game_manager", None)
            if gm is not None:
                gm._captaincy_choice_pending = False
        except Exception:
            pass

        self._status.setText("")
        QMessageBox.information(
            self, "Captains",
            f"Captaincy set:\nC — {names[0]}\nA — {names[1]}\nA — {names[2]}")
        self.refresh()
