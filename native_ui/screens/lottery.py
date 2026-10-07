"""Draft lottery reveal: native Qt port of the web UI lottery page.

Ports web_ui/templates/lottery.html + web_ui/static/js/lottery.js +
the /api/lottery endpoints in web_ui/screens/inbox_actions.py. Calls
the game object DIRECTLY -- no Flask, no HTTP.

Staged reveal (client-side theater over real data): the lottery data
arrives all at once, and the UI drips it out -- Next reveals one team
at a time (picks 16..3, then #2, then #1), Skip reveals all. Movement
arrows, reaction lines, top-2 styling, finale card with Draft / Done
buttons.

Game methods used (all real):
  - gm._pending_lottery_reveal (pending reveal rows + year)
  - league.lottery_results (persisted {year: [rows]}), latest year used
  - clearing the pending reveal mirrors the inbox_lottery_clear bridge
    op (desktop _watch_lottery_reveal clears _pending_lottery_reveal
    when the reveal screen closes).

Reaction lines are a verbatim port of draft_lottery.reaction_line
(the module itself needs customtkinter, unavailable outside the
desktop; same reason the web UI ported it verbatim).

MP fantasy-draft contract (see native_ui/MP_FANTASY_DRAFT_BUG.md):
  this is the single-player ENTRY-draft lottery. It never reads or
  writes ``pending_fantasy_draft``.
"""

from PySide6.QtWidgets import (
    QDialogButtonBox, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _reaction_line(pick, team, movement):
    """Verbatim port of draft_lottery.reaction_line (pure logic)."""
    if pick == 1:
        return f"{team} wins the lottery \u2014 #1 overall!"
    if pick == 2:
        return f"{team} takes #2 \u2014 the consolation prize nobody hates."
    if movement >= 5:
        return f"{team} leaps {movement} spots to #{pick} \u2014 the room erupts!"
    if movement >= 2:
        return f"{team} jumps to #{pick} (+{movement})."
    if movement <= -3:
        return f"{team} slides to #{pick} ({movement}) \u2014 groans in the war room."
    if movement < 0:
        return f"{team} falls to #{pick}."
    return f"{team} holds at #{pick}."


def get_lottery_data(game):
    """Lottery rows: pending reveal first, else the stored league result
    for the latest year (port of _lottery_rows + api_lottery)."""
    gm = _resolve_gm(game)
    pending = _safe(lambda: getattr(gm, "_pending_lottery_reveal", None))
    year, rows = 0, []
    if pending:
        year = _safe(lambda: int(pending.get("year", 0)) or 0, 0)
        rows = [dict(r) for r in (pending.get("rows") or [])]
    else:
        league = _safe(lambda: gm.league) if gm else None
        stored = _safe(lambda: getattr(league, "lottery_results",
                                      None) or {}, {}) or {}
        years = [y for y in stored.keys() if stored.get(y)]
        if years:
            year = max(years)
            rows = [dict(r) for r in stored[year]]
    web_rows = []
    for r in rows:
        try:
            pick = int(r.get("pick", 0) or 0)
            team = str(r.get("team", "?"))
            mv = int(r.get("movement", 0) or 0)
            web_rows.append({
                "pick": pick,
                "team": team,
                "odds_pct": float(r.get("odds_pct", 0) or 0),
                "movement": mv,
                "reaction": _reaction_line(pick, team, mv),
            })
        except Exception:
            continue
    # Reveal order mirrors the desktop countdown: 16..3, then #2/#1.
    tail = sorted([r for r in web_rows if r["pick"] >= 3],
                  key=lambda r: -r["pick"])
    head = sorted([r for r in web_rows if r["pick"] < 3],
                  key=lambda r: -r["pick"])
    return {
        "active": bool(web_rows),
        "year": year,
        "reveal_order": tail + head,
        "rows": sorted(web_rows, key=lambda r: r["pick"]),
    }


def clear_pending_reveal(game):
    """Clear the pending lottery reveal (port of inbox_lottery_clear)."""
    gm = _resolve_gm(game)
    try:
        if (gm is not None
                and getattr(gm, "_pending_lottery_reveal", None)
                is not None):
            delattr(gm, "_pending_lottery_reveal")
    except Exception:
        pass


def _mv_text(mv):
    if mv > 0:
        return f"(+{mv} \u25b2)"
    if mv < 0:
        return f"({mv} \u25bc)"
    return ""


class LotteryScreen(BaseScreen):
    """Draft lottery: televised staged reveal."""

    title = "Lottery"

    def _build_body(self):
        sub = QLabel("The televised reveal \u00b7 picks 16 to 1")
        sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(sub)

        # Stage: the big televised moment
        stage = QVBoxLayout()
        self._stage_pick = QLabel("...")
        self._stage_pick.setAlignment(Qt.AlignCenter)
        self._stage_pick.setStyleSheet(
            "font-size: 56px; font-weight: bold; color: #e8ecf4;")
        stage.addWidget(self._stage_pick)
        self._stage_team = QLabel("The balls are in the machine...")
        self._stage_team.setAlignment(Qt.AlignCenter)
        self._stage_team.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: #7cc4ff;")
        self._stage_team.setWordWrap(True)
        stage.addWidget(self._stage_team)
        self._stage_detail = QLabel("")
        self._stage_detail.setAlignment(Qt.AlignCenter)
        self._stage_detail.setStyleSheet(
            "font-size: 14px; color: #9aa4b8;")
        self._stage_detail.setWordWrap(True)
        stage.addWidget(self._stage_detail)
        stage_wrap = QWidget()
        stage_wrap.setLayout(stage)
        stage_wrap.setStyleSheet(
            "background: #141b2e; border: 1px solid #2b365c; "
            "border-radius: 12px; padding: 24px;")
        self._layout.addWidget(stage_wrap)

        # Controls
        ctrls = QHBoxLayout()
        ctrls.addStretch()
        self._btn_next = QPushButton("Reveal next pick")
        self._btn_next.setObjectName("primary-btn")
        self._btn_next.clicked.connect(self._reveal_next)
        ctrls.addWidget(self._btn_next)
        self._btn_skip = QPushButton("Skip to results")
        self._btn_skip.clicked.connect(self._reveal_all)
        ctrls.addWidget(self._btn_skip)
        ctrls.addStretch()
        self._layout.addLayout(ctrls)

        # Results board
        bh = QLabel("Results board")
        bh.setObjectName("section-header")
        self._layout.addWidget(bh)
        self._board_scroll = QScrollArea()
        self._board_scroll.setWidgetResizable(True)
        self._board_inner = QWidget()
        self._board_layout = QVBoxLayout(self._board_inner)
        self._board_layout.setAlignment(Qt.AlignTop)
        self._board_scroll.setWidget(self._board_inner)
        self._layout.addWidget(self._board_scroll, 1)

        # Finale card
        self._finale = QWidget()
        fl = QHBoxLayout(self._finale)
        fl.addStretch()
        self._btn_draft = QPushButton("Open Draft Central")
        self._btn_draft.setObjectName("primary-btn")
        self._btn_draft.clicked.connect(self._on_draft)
        fl.addWidget(self._btn_draft)
        self._btn_done = QPushButton("Done")
        self._btn_done.clicked.connect(self._on_done)
        fl.addWidget(self._btn_done)
        fl.addStretch()
        self._finale.setVisible(False)
        self._layout.addWidget(self._finale)

        # Reveal-drama timer: the stage "rolls the balls" briefly before
        # each reveal lands (client-side theater only).
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._land_reveal)

        self._data = None
        self._idx = 0
        self._done_flag = False
        self._pending_row = None

    # -- navigation helper -------------------------------------------
    def _navigate(self, name):
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn(name)
            except Exception:
                pass

    def refresh(self):
        self._data = get_lottery_data(self.game)
        self._idx = 0
        self._done_flag = False
        self._pending_row = None
        self._reveal_timer.stop()
        while self._board_layout.count():
            item = self._board_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._finale.setVisible(False)
        if not self._data.get("active"):
            self._stage_pick.setText("...")
            self._stage_team.setText("No lottery results available.")
            self._stage_detail.setText("")
            self._btn_next.setEnabled(False)
            self._btn_skip.setEnabled(False)
            return
        self._btn_next.setEnabled(True)
        self._btn_skip.setEnabled(True)
        self._stage_pick.setText("...")
        self._stage_team.setText("The balls are in the machine...")
        self._stage_detail.setText("")
        # Auto-start the drama on first open (web reveals on load).
        self._reveal_next()

    def _reveal_next(self):
        if self._done_flag:
            return
        order = (self._data or {}).get("reveal_order") or []
        if self._idx >= len(order):
            self._finish()
            return
        row = order[self._idx]
        self._pending_row = row
        # Brief suspense before the card lands.
        self._stage_pick.setText("...")
        self._stage_team.setText("The balls are tumbling...")
        self._stage_detail.setText("")
        self._btn_next.setEnabled(False)
        self._reveal_timer.start(450)

    def _land_reveal(self):
        row = self._pending_row
        if row is None or self._done_flag:
            return
        pick = row["pick"]
        self._stage_pick.setText(f"#{pick}")
        self._stage_team.setText(row["team"])
        self._stage_detail.setText(
            f"{row['odds_pct']:.1f}% odds {_mv_text(row['movement'])}"
            f" \u2014 {row['reaction']}")
        if pick <= 2:
            self._stage_pick.setStyleSheet(
                "font-size: 72px; font-weight: bold; color: #e8b93c;")
            self._stage_team.setStyleSheet(
                "font-size: 30px; font-weight: bold; color: #e8b93c;")
        else:
            self._stage_pick.setStyleSheet(
                "font-size: 56px; font-weight: bold; color: #e8ecf4;")
            self._stage_team.setStyleSheet(
                "font-size: 26px; font-weight: bold; color: #7cc4ff;")
        self._add_board_row(row)
        self._idx += 1
        self._pending_row = None
        order = (self._data or {}).get("reveal_order") or []
        if self._idx >= len(order):
            self._finish()
        else:
            self._btn_next.setEnabled(True)

    def _add_board_row(self, row):
        h = QHBoxLayout()
        num = QLabel(f"#{row['pick']}")
        num.setFixedWidth(60)
        num.setStyleSheet("font-weight: bold;")
        h.addWidget(num)
        team = QLabel(row["team"])
        team.setStyleSheet("font-weight: bold;")
        h.addWidget(team, 1)
        mv = QLabel(_mv_text(row["movement"]))
        mv.setStyleSheet("color: #9aa4b8;")
        h.addWidget(mv)
        wrap = QWidget()
        wrap.setLayout(h)
        if row["pick"] <= 2:
            wrap.setStyleSheet(
                "background: #2a2410; border: 1px solid #e8b93c; "
                "border-radius: 6px;")
        self._board_layout.insertWidget(0, wrap)

    def _reveal_all(self):
        self._reveal_timer.stop()
        order = (self._data or {}).get("reveal_order") or []
        while self._idx < len(order):
            row = order[self._idx]
            self._add_board_row(row)
            self._idx += 1
        if order:
            last = order[-1]
            self._stage_pick.setText(f"#{last['pick']}")
            self._stage_team.setText(last["team"])
            self._stage_detail.setText(
                f"{last['odds_pct']:.1f}% odds "
                f"{_mv_text(last['movement'])} \u2014 {last['reaction']}")
            self._stage_pick.setStyleSheet(
                "font-size: 72px; font-weight: bold; color: #e8b93c;")
            self._stage_team.setStyleSheet(
                "font-size: 30px; font-weight: bold; color: #e8b93c;")
        self._finish()

    def _finish(self):
        if self._done_flag:
            return
        self._done_flag = True
        self._reveal_timer.stop()
        self._btn_next.setEnabled(False)
        self._btn_skip.setEnabled(False)
        self._finale.setVisible(True)

    def _clear_and_go(self, target):
        clear_pending_reveal(self.game)
        self._navigate(target)

    def _on_draft(self):
        self._clear_and_go("draft")

    def _on_done(self):
        self._clear_and_go("hub")
