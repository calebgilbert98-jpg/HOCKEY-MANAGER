"""Draft Recap screen -- round-by-round review of completed drafts.

Shows every completed draft stored in ``league.draft_recap_history``
(see draft_recap.py): the one-time fantasy draft plus each annual entry
draft. Sections:

- Top 10 picks (quick glance)
- Your picks with the draft grade
- Best values (highest value returned vs pick-slot expectation)
- Biggest reaches (lowest value returned vs pick-slot expectation)
- Positional breakdown
- Full draft board, browsable round by round

Grading and value analysis come from the recap data itself, which was
built with draft_night.draft_grades / pick_slot_value /
drafted_player_value -- nothing is re-graded here.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QFrame, QPushButton,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _league(game):
    return _safe(lambda: _gm(game).league)


def _draft_label(key):
    if key == "fantasy":
        return "Fantasy Draft"
    return f"{key} Entry Draft"


def _grade_color(grade):
    try:
        from draft_night import grade_color
        return grade_color(grade)
    except Exception:
        return "#e8ecf4"


class DraftRecapScreen(BaseScreen):
    title = "Draft Recap"

    PICK_COLS = ["Pick", "Rd", "Player", "OVR", "Age", "Pot", "Pos",
                 "Team", "Value"]

    def _build_body(self):
        # -- controls ------------------------------------------------
        ctl = QHBoxLayout()
        d_lbl = QLabel("Draft")
        d_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(d_lbl)
        self._draft_combo = QComboBox()
        self._draft_combo.currentIndexChanged.connect(
            lambda _i: self._on_draft_changed())
        ctl.addWidget(self._draft_combo)
        r_lbl = QLabel("Round")
        r_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(r_lbl)
        self._round_combo = QComboBox()
        self._round_combo.currentIndexChanged.connect(
            lambda _i: self._render_board())
        ctl.addWidget(self._round_combo)
        ctl.addStretch()
        self._layout.addLayout(ctl)

        self._empty = QLabel("")
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet("color: #6b7488; font-size: 15px;")
        self._empty.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._empty)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)
        self._layout.addWidget(self._content)
        self._layout.addStretch()

        self._recap = None
        self._recap_key = ""

    # -- data ----------------------------------------------------------

    def _recaps(self):
        league = _league(self.game)
        try:
            import draft_recap as dr
            keys = dr.list_draft_recaps(league)
            latest = str(getattr(league, "draft_recap_latest", "") or "")
            return keys, latest, league
        except Exception:
            return [], "", league

    def refresh(self):
        keys, latest, _league_obj = self._recaps()
        combo = self._draft_combo
        combo.blockSignals(True)
        combo.clear()
        for k in keys:
            combo.addItem(_draft_label(k), k)
        combo.blockSignals(False)
        if not keys:
            self._recap = None
            self._recap_key = ""
            self._render()
            return
        pick = latest if latest in keys else keys[-1]
        combo.setCurrentIndex(combo.findData(pick))
        self._on_draft_changed()

    def _on_draft_changed(self):
        key = self._draft_combo.currentData() or ""
        league = _league(self.game)
        try:
            import draft_recap as dr
            self._recap = dr.get_draft_recap(league, key)
        except Exception:
            self._recap = None
        self._recap_key = key
        # rebuild round selector
        rc = self._round_combo
        rc.blockSignals(True)
        rc.clear()
        n_rounds = int((self._recap or {}).get("num_rounds") or 0)
        for r in range(1, n_rounds + 1):
            rc.addItem(f"Round {r}", r)
        rc.blockSignals(False)
        if n_rounds:
            rc.setCurrentIndex(0)
        self._render()

    # -- rendering -----------------------------------------------------

    def _clear_content(self):
        layout = self._content_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _section_title(self, text):
        lab = QLabel(text.upper())
        lab.setStyleSheet("color: #9aa4b8; font-size: 12px; font-weight: bold;"
                          " letter-spacing: 1px;")
        self._content_layout.addWidget(lab)

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #2a3142;")
        self._content_layout.addWidget(line)

    @staticmethod
    def _fmt_value(v):
        if v is None:
            return "--"
        try:
            return f"{float(v):.2f}x"
        except Exception:
            return "--"

    def _pick_row(self, p):
        age = p.get("age")
        pot = p.get("potential")
        ovr = p.get("overall_rating")
        return [
            f"#{p.get('overall_pick')}",
            str(p.get("round") or ""),
            str(p.get("player_name") or "?"),
            str(ovr) if ovr is not None else "--",
            str(age) if age is not None else "--",
            str(pot) if pot is not None else "--",
            str(p.get("position") or "?"),
            str(p.get("team_name") or "?"),
            self._fmt_value(p.get("value_ratio")),
        ]

    def _make_table(self, columns, rows):
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for col, txt in enumerate(row):
                table.setItem(i, col, QTableWidgetItem(str(txt)))
        table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.Stretch)
        return table

    def _user_team_name(self):
        league = _league(self.game)
        try:
            for t in (getattr(league, "teams", None) or []):
                if bool(getattr(t, "is_user_team", False)):
                    return str(getattr(t, "team_name", "") or "")
        except Exception:
            pass
        gm = _gm(self.game)
        return str(_safe(lambda: getattr(
            getattr(gm, "user_team", None), "team_name", ""), "") or "")

    def _render(self):
        self._clear_content()
        recap = self._recap
        if not recap or not (recap.get("picks") or []):
            self._empty.setText(
                "No draft recaps yet.\nComplete a fantasy draft or an entry "
                "draft and the full round-by-round recap will appear here.")
            self._empty.setVisible(True)
            self._content.setVisible(False)
            return
        self._empty.setVisible(False)
        self._content.setVisible(True)

        picks = recap["picks"]
        user = self._user_team_name()

        # -- headline ------------------------------------------------
        dtype = recap.get("draft_type", "entry")
        year = recap.get("year", "")
        head = (f"FANTASY DRAFT RECAP" if dtype == "fantasy"
                else f"{year} ENTRY DRAFT RECAP")
        sub = (f"{recap.get('num_picks', 0)} picks - "
               f"{recap.get('num_teams', 0)} teams - "
               f"{recap.get('num_rounds', 0)} rounds")
        h = QLabel(head)
        h.setStyleSheet("font-size: 20px; font-weight: bold;")
        self._content_layout.addWidget(h)
        s = QLabel(sub)
        s.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._content_layout.addWidget(s)
        self._sep()

        # -- top 10 quick glance --------------------------------------
        self._section_title("Top 10 -- quick glance")
        self._content_layout.addWidget(self._make_table(
            self.PICK_COLS, [self._pick_row(p) for p in picks[:10]]))
        self._sep()

        # -- user picks with grade ------------------------------------
        grades = {t: g for t, g, _r in (recap.get("grades") or [])}
        my_grade = grades.get(user, "") if user else ""
        self._section_title(
            f"Your picks{(' -- grade ' + my_grade) if my_grade else ''}")
        if my_grade:
            gl = QLabel(f"Draft grade: {my_grade}")
            gl.setStyleSheet(
                f"font-size: 18px; font-weight: bold; "
                f"color: {_grade_color(my_grade)};")
            self._content_layout.addWidget(gl)
        mine = [p for p in picks if p["team_name"] == user] if user else []
        if mine:
            self._content_layout.addWidget(self._make_table(
                self.PICK_COLS, [self._pick_row(p) for p in mine]))
        else:
            nl = QLabel("No picks found for your club in this draft.")
            nl.setStyleSheet("color: #6b7488; font-size: 13px;")
            self._content_layout.addWidget(nl)
        self._sep()

        # -- best values / biggest reaches -----------------------------
        valued = [p for p in picks if p.get("value_ratio") is not None]
        best = sorted(valued, key=lambda p: p["value_ratio"],
                      reverse=True)[:8]
        reach = sorted(valued, key=lambda p: p["value_ratio"])[:8]
        self._section_title("Best values -- late-round steals")
        if best:
            self._content_layout.addWidget(self._make_table(
                self.PICK_COLS, [self._pick_row(p) for p in best]))
        self._section_title("Biggest reaches -- early picks, low return")
        if reach:
            self._content_layout.addWidget(self._make_table(
                self.PICK_COLS, [self._pick_row(p) for p in reach]))
        note = QLabel("Value = drafted value vs pick-slot expectation "
                      "(>1.00x is a steal, <1.00x is a reach).")
        note.setStyleSheet("color: #6b7488; font-size: 12px; "
                           "font-style: italic;")
        self._content_layout.addWidget(note)
        self._sep()

        # -- positional breakdown --------------------------------------
        bd = recap.get("positional_breakdown") or {}
        self._section_title("Positional breakdown")
        bl = QLabel("   ".join(
            f"{pos}: {bd.get(pos, 0)}" for pos in ("C", "W", "D", "G")))
        bl.setStyleSheet("font-size: 15px;")
        self._content_layout.addWidget(bl)
        self._sep()

        # -- full board, round by round --------------------------------
        self._section_title("Full draft board -- by round")
        self._board_host = QWidget()
        self._board_layout = QVBoxLayout(self._board_host)
        self._board_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self._board_host)
        self._render_board()

    def _render_board(self):
        if not hasattr(self, "_board_layout") or self._recap is None:
            return
        layout = self._board_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        rnd = self._round_combo.currentData()
        if rnd is None:
            return
        picks = [p for p in (self._recap.get("picks") or [])
                 if int(p.get("round") or 0) == int(rnd)]
        rl = QLabel(f"Round {rnd} -- {len(picks)} picks")
        rl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        layout.addWidget(rl)
        layout.addWidget(self._make_table(
            self.PICK_COLS, [self._pick_row(p) for p in picks]))
