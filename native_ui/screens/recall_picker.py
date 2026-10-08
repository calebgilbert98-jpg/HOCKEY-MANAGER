"""Recall Picker screen: when the NHL club can't dress 18+2 and the farm
has recallable players, show them best-first with one-click Recall.

Native port of HockeyManagerGUI.open_recall_picker (main branch, main.py).
Calls the game object DIRECTLY -- no Flask/HTTP, no command queue.

Game methods used (all real, same as the Tkinter version):
  - roster_limits.lineup_shortfall(team)        (skaters, goalies needed)
  - roster_limits.recall_candidates(team, ...)  (best-first candidates)
  - roster_limits._overall(p)                   (display OVR)
  - roster_limits._player_nhl_salary(p)         (recall cap hit)
  - roster_limits._recall_fits_cap(team, p)     (cap note per row)
  - roster_limits.ensure_dressed_lineup_auto(team)  (emergency fillers)
  - game.call_up_to_nhl(player)                 (one-click recall;
      returns (success, message) on GameManager)

Non-modal in spirit: refresh() re-reads the shortfall every time the
screen is shown, and the screen auto-shows the healthy state once the
lineup is covered. Never raises.
"""

from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))


_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}


def _pos_str(p):
    pos = _safe(lambda: getattr(p, "primary_position", ""), "")
    raw = getattr(pos, "value", pos)
    try:
        s = str(raw or "")
        if "." in s:
            s = s.split(".")[-1]
        return _POSITION_ABBR.get(s.strip().upper(),
                                  s.strip().upper() or "?")
    except Exception:
        return "?"


def _player_name(p):
    first = _safe(lambda: getattr(p, "first_name", ""), "") or ""
    last = _safe(lambda: getattr(p, "last_name", ""), "") or ""
    full = _safe(lambda: getattr(p, "full_name", ""), "") or ""
    name = full or (first + " " + last).strip()
    return name or "?"


def _fmt_salary(sal):
    try:
        return f"${int(sal or 0) / 1e6:.2f}M"
    except Exception:
        return "--"


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class RecallPickerScreen(BaseScreen):
    """Tier-2 recall picker: cover a dressed-lineup shortfall from the farm."""

    title = "Recall Picker"

    def _build_body(self):
        # --- shortfall banner ---
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setObjectName("section-header")
        self._layout.addWidget(self._banner)

        self._sub = QLabel(
            "Recall from your farm team -- same as real NHL clubs do. "
            "Emergency fill-ins stay the last resort.")
        self._sub.setWordWrap(True)
        self._layout.addWidget(self._sub)

        # --- candidate list ---
        self._cand_group = QGroupBox("Farm recalls (best first)")
        cand_layout = QVBoxLayout(self._cand_group)
        self._cand_count = QLabel("")
        cand_layout.addWidget(self._cand_count)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._body = QWidget()
        self._rows = QVBoxLayout(self._body)
        self._rows.setSpacing(6)
        self._rows.addStretch()
        self._scroll.setWidget(self._body)
        cand_layout.addWidget(self._scroll)
        self._layout.addWidget(self._cand_group)

        # --- bottom bar: filler escape hatch ---
        bottom = QHBoxLayout()
        self._filler_btn = QPushButton("Summon emergency fillers instead")
        self._filler_btn.clicked.connect(self._summon_fillers)
        bottom.addWidget(self._filler_btn)
        bottom.addStretch()
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(
            lambda: self.navigate_to("hub"))
        bottom.addWidget(self._close_btn)
        self._layout.addLayout(bottom)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._layout.addWidget(self._status)

        self.refresh()

    # -- rows ---------------------------------------------------------

    def _clear_rows(self):
        while self._rows.count():
            child = self._rows.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
        self._rows.addStretch()

    def _make_row(self):
        row = QFrame()
        row.setObjectName("tile")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 6, 10, 6)
        return row, lay

    # -- refresh -------------------------------------------------------

    def refresh(self):
        try:
            self._refresh_all()
        except Exception as e:
            self._status.setText(f"Couldn't load recall data: {e}")

    def _refresh_all(self):
        import roster_limits as _rl

        team = _user_team(self.game)
        if team is None:
            self._banner.setText("No active team.")
            self._clear_rows()
            self._cand_count.setText("")
            self._filler_btn.setEnabled(False)
            return

        sk_need, go_need = _rl.lineup_shortfall(team)

        if sk_need <= 0 and go_need <= 0:
            self._banner.setText("LINEUP HEALTHY")
            self._sub.setText(
                "The club can dress a full 18+2 lineup. "
                "No recalls needed right now.")
            self._clear_rows()
            self._cand_count.setText("No shortfall.")
            self._filler_btn.setEnabled(False)
            return

        bits = []
        if sk_need:
            bits.append(f"{sk_need} skater{'s' if sk_need != 1 else ''}")
        if go_need:
            bits.append(f"{go_need} goalie{'s' if go_need != 1 else ''}")
        self._banner.setText(f"SHORT-HANDED: {', '.join(bits)} needed "
                             "to dress a lineup")
        self._sub.setText(
            "Recall from your farm team -- same as real NHL clubs do. "
            "Emergency fill-ins stay the last resort.")

        cands = _rl.recall_candidates(team, sk_need, go_need) or []
        self._filler_btn.setEnabled(True)
        self._clear_rows()

        if not cands:
            self._cand_count.setText(
                "No recallable players on the farm -- emergency "
                "fillers are the only option.")
            self._rows.addWidget(
                QLabel("Nobody on the farm is available for recall "
                       "(injured, blocked, or ineligible)."))
            return

        shown = cands[:12]
        self._cand_count.setText(
            f"{len(shown)} candidate{'s' if len(shown) != 1 else ''} "
            "(best first)")
        for p in shown:
            self._add_candidate_row(_rl, team, p)

    def _add_candidate_row(self, _rl, team, p):
        try:
            row, lay = self._make_row()

            ovr = QLabel(str(_rl._overall(p)))
            ovr.setObjectName("section-header")
            ovr.setMinimumWidth(36)
            lay.addWidget(ovr)

            sal = _rl._player_nhl_salary(p)
            two_way = bool(_safe(
                lambda: getattr(getattr(p, "contract", None),
                                "two_way", False), False))
            fits = _rl._recall_fits_cap(team, p)

            name = _player_name(p)
            sub = (f"{_pos_str(p)} · {_fmt_salary(sal)}"
                   + (" · 2-way" if two_way else "")
                   + (" · OVER CAP" if not fits else ""))
            info = QLabel(f"{name}\n{sub}")
            info.setWordWrap(True)
            lay.addWidget(info, 1)

            btn = QPushButton("Recall")
            btn.setObjectName("primary-btn")
            btn.setEnabled(bool(fits))
            btn.clicked.connect(
                lambda _checked=False, _p=p: self._do_recall(_p))
            lay.addWidget(btn)

            self._rows.insertWidget(self._rows.count() - 1, row)
        except Exception:
            pass

    # -- actions -------------------------------------------------------

    def _do_recall(self, player):
        try:
            result = self.game.call_up_to_nhl(player)
        except Exception as e:
            self._status.setText(f"Recall failed: {e}")
            return
        # GameManager returns (success, message); Tkinter's returns None.
        if isinstance(result, tuple):
            ok, msg = result
            if not ok:
                self._status.setText(f"Recall blocked: {msg or 'unknown'}")
                return
        self._status.setText(f"Recalled {_player_name(player)}.")
        self.refresh()

    def _summon_fillers(self):
        try:
            import roster_limits as _rl
            team = _user_team(self.game)
            if team is not None:
                _rl.ensure_dressed_lineup_auto(team)
            self._status.setText(
                "Emergency fill-ins summoned (league-minimum, released "
                "automatically when the lineup is healthy).")
        except Exception as e:
            self._status.setText(f"Couldn't summon fillers: {e}")
        self.refresh()
