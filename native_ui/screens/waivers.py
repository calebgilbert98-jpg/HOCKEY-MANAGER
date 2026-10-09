"""Waivers screen: waiver wire claims, claim-priority strip, and placing
your own players on waivers.

Native port of the web UI waivers screen (web_ui/templates/waivers.html
+ web_ui/screens/waivers.py + web_ui/static/js/waivers.js). Calls the
game object DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same as the web bridge called):
  - game._execute_waiver_claim(player, team)   (claim)
  - game.add_news(...)                         (placement notice)
  - game.waiver_list / team.roster             (reads)
  - waiver_logic.is_waiver_eligible(p)         (exempt read)
  - waiver_logic.waiver_priority_order / waiver_priority_rank /
    waiver_priority_basis_label                 (priority strip)
  - trade_engine.clause_of(p)                  (NMC blocks placement)
  - transaction_windows.check_window("waiver_place", date)
"""

from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _pid(p):
    return str(_safe(lambda: getattr(p, "id", id(p)), ""))


def _player_name(p):
    return _safe(lambda: getattr(p, "full_name", "?"), "?")


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
        return _POSITION_ABBR.get(s.strip().upper(), s.strip().upper() or "?")
    except Exception:
        return "?"


def _player_ovr(p):
    try:
        fn = getattr(p, "overall_rating", None)
        if callable(fn):
            v = fn()
            if v:
                return int(v)
    except Exception:
        pass
    return _safe(lambda: int(getattr(p, "overall", 0) or 0), 0)


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,}"


def _deadline_str(days):
    try:
        d = int(days or 0)
    except Exception:
        d = 0
    if d <= 0:
        return "Expires today"
    return f"{d} day{'s' if d != 1 else ''} left"


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))


def _user_league(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.league)
            or _safe(lambda: getattr(game, "league", None)))


# ---------------------------------------------------------------------------
# game-data helpers (ported from web_ui/screens/waivers.py)
# ---------------------------------------------------------------------------

def _wire(game):
    wire = _safe(lambda: list(getattr(game, "waiver_list", None) or []),
                 []) or []
    wire.sort(key=lambda p: _safe(
        lambda: int(getattr(p, "waiver_days", 0) or 0), 0))
    return wire


def _eligible(game):
    """Roster players not already on waivers, with clause + exemption
    reads. Never raises."""
    team = _user_team(game)
    roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                   []) or []
    try:
        import waiver_logic as _wl
        eligible_fn = _wl.is_waiver_eligible
    except Exception:
        eligible_fn = None
    try:
        import trade_engine as _te
        clause_fn = _te.clause_of
    except Exception:
        clause_fn = None
    out = []
    for p in roster:
        try:
            if _safe(lambda: bool(getattr(p, "on_waivers", False)), False):
                continue
            kind = ""
            if clause_fn is not None:
                try:
                    kind, _detail = clause_fn(p)
                    kind = kind or ""
                except Exception:
                    kind = ""
            exempt = None
            if eligible_fn is not None:
                try:
                    exempt = not bool(eligible_fn(p))
                except Exception:
                    exempt = None
            out.append({
                "player": p,
                "clause": kind,
                "nmc_block": (kind == "NMC"),
                "waiver_exempt": bool(exempt) if exempt is not None else False,
            })
        except Exception:
            continue
    out.sort(key=lambda d: _player_ovr(d["player"]), reverse=True)
    return out


def _priority(game):
    """Claim-priority strip data: order rows, user's rank, basis label."""
    try:
        import waiver_logic as _wl
    except Exception:
        return {"order": [], "my_rank": None, "basis": ""}
    gm = _resolve_gm(game)
    league = _safe(lambda: gm.league)
    if league is None:
        return {"order": [], "my_rank": None, "basis": ""}
    today = _safe(lambda: getattr(gm, "current_date", None))
    team = _user_team(game)
    my_name = _safe(lambda: getattr(team, "team_name", ""), "")
    rows = []
    try:
        for i, t in enumerate(_wl.waiver_priority_order(league, today) or [],
                              1):
            tname = _safe(lambda: getattr(t, "team_name", "?"), "?")
            rows.append({"rank": i, "team": tname,
                         "is_user": bool(my_name and tname == my_name)})
    except Exception:
        pass
    rank = _safe(lambda: _wl.waiver_priority_rank(league, team, today))
    basis = _safe(lambda: _wl.waiver_priority_basis_label(league, today), "")
    return {"order": rows, "my_rank": rank, "basis": basis or ""}


def _claim_waiver(game, player):
    """Submit a waiver claim to the pending-claims queue.

    Mirrors the desktop Tk UI (windows.py): the claim is QUEUED via
    player.user_claim_pending and resolved at the next waiver run
    (game_manager.process_waivers) in priority order -- never granted
    instantly. Returns (ok, message). Never raises."""
    team = _user_team(game)
    if team is None:
        return False, "No team to claim with."
    gm = _resolve_gm(game)
    wire = _safe(lambda: list(getattr(game, "waiver_list", None) or []),
                 []) or []
    if player not in wire:
        return False, "Player is no longer on the wire."
    # Roster space check (matches desktop UI).
    if len(_safe(lambda: list(getattr(team, "roster", None) or []), [])
           or []) >= 23:
        return False, ("Your NHL roster is full. Release or reassign a "
                       "player before claiming from waivers.")
    # Cap space check (matches desktop UI).
    try:
        salary = int(getattr(getattr(player, "contract", None),
                             "salary", 0) or 0)
        cap = _safe(lambda: getattr(team, "cap_space", 0), 0) or 0
        if salary > cap:
            return False, (f"You don't have enough cap space to add "
                           f"${salary:,} in salary.")
    except Exception:
        pass
    # Already pending check (matches desktop UI).
    if _safe(lambda: bool(getattr(player, "user_claim_pending",
                                  False)), False):
        return True, (f"You already have a pending claim on "
                      f"{_safe(lambda: getattr(player, 'full_name', 'him'), 'him')}. "
                      f"It will be processed in waiver priority order.")
    # Queue the claim -- do NOT call _execute_waiver_claim directly.
    # That is the transfer primitive for when a claim WINS at
    # process_waivers time. Calling it here bypasses priority
    # resolution and lets a lower-priority club steal the player.
    try:
        player.user_claim_pending = True
    except Exception as e:
        return False, f"Claim failed: {e}"
    # News entry (matches desktop UI).
    try:
        tname = _safe(lambda: getattr(team, "team_name", ""), "")
        pname = _safe(lambda: getattr(player, "full_name", ""), "")
        add_news = getattr(gm, "add_news", None)
        if callable(add_news) and tname and pname:
            add_news(f"{tname} submitted a waiver claim for {pname}.")
    except Exception:
        pass
    pname = _safe(lambda: getattr(player, "full_name", "him"), "him")
    return True, (f"Waiver claim submitted for {pname}. It will be "
                  f"processed at the next waiver run in priority order -- "
                  f"a higher-priority club that also claims him gets him "
                  f"first.")


def _place_on_waivers(game, player):
    """Place a roster player on the wire (mirrors the bridge op:
    window gate, NMC block, 2-day wire, news). Returns (ok, message)."""
    gm = _resolve_gm(game)
    team = (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))
    if team is None:
        return False, "No user team."
    try:
        import transaction_windows as _tw
        ok, why = _tw.check_window(
            "waiver_place", _safe(lambda: getattr(game, "current_date",
                                                  None)))
        if not ok:
            return False, str(why or "Waiver placement window closed.")
    except Exception:
        pass
    try:
        import trade_engine as _te
        kind, _detail = _te.clause_of(player)
        if kind == "NMC":
            return False, (f"{_player_name(player)} has a no-movement "
                           "clause — placement blocked.")
    except Exception:
        pass
    try:
        player.on_waivers = True
        player.waiver_days = 2
        wire = getattr(game, "waiver_list", None)
        if wire is not None and player not in wire:
            wire.append(player)
        news = getattr(game, "add_news", None)
        if callable(news):
            news(f"{_player_name(player)} placed on waivers by "
                 f"{_safe(lambda: getattr(team, 'team_name', 'your team'), 'your team')}.")
    except Exception as e:
        return False, f"Could not place on waivers: {e}"
    return True, ""


def _demote_exempt(game, player):
    """Waiver-exempt demote straight to the AHL (desktop waive-and-assign
    destination, web /api/roster/move mirror). Returns (ok, message)."""
    team = _user_team(game)
    if team is None:
        return False, "No user team."
    try:
        roster = list(getattr(team, "roster", None) or [])
        if player not in roster:
            return False, "Player is no longer on your NHL roster."
        roster.remove(player)
        try:
            team.roster[:] = roster
        except Exception:
            team.roster = roster
        ahl = _safe(lambda: list(getattr(team, "ahl_roster", None)), None)
        if ahl is not None:
            ahl.append(player)
            team.ahl_roster = ahl
        try:
            player.playing_where = "AHL"
        except Exception:
            pass
        news = getattr(game, "add_news", None)
        if callable(news):
            news(f"{_player_name(player)} assigned to the AHL "
                 f"(waiver-exempt).")
    except Exception as e:
        return False, f"Could not demote: {e}"
    return True, ""


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class WaiversScreen(BaseScreen):
    """Waiver wire with claims, claim-priority strip, and your own
    waiver-eligible players."""

    title = "Waivers"

    def _build_body(self):
        # --- claim priority strip ---
        self._prio_group = QGroupBox("Claim priority")
        prio_layout = QVBoxLayout(self._prio_group)
        self._prio_strip = QLabel("")
        self._prio_strip.setWordWrap(True)
        prio_layout.addWidget(self._prio_strip)
        self._layout.addWidget(self._prio_group)

        # --- wire list ---
        self._wire_group = QGroupBox("Waiver wire")
        wire_layout = QVBoxLayout(self._wire_group)
        self._wire_count = QLabel("")
        wire_layout.addWidget(self._wire_count)
        self._wire_scroll = QScrollArea()
        self._wire_scroll.setWidgetResizable(True)
        self._wire_body = QWidget()
        self._wire_rows = QVBoxLayout(self._wire_body)
        self._wire_rows.setSpacing(6)
        self._wire_scroll.setWidget(self._wire_body)
        wire_layout.addWidget(self._wire_scroll)
        self._layout.addWidget(self._wire_group)

        # --- eligible to waive ---
        self._elig_group = QGroupBox("Place on waivers")
        elig_layout = QVBoxLayout(self._elig_group)
        self._elig_scroll = QScrollArea()
        self._elig_scroll.setWidgetResizable(True)
        self._elig_body = QWidget()
        self._elig_rows = QVBoxLayout(self._elig_body)
        self._elig_rows.setSpacing(6)
        self._elig_scroll.setWidget(self._elig_body)
        elig_layout.addWidget(self._elig_scroll)
        self._layout.addWidget(self._elig_group)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        self.refresh()

    # -- rows ---------------------------------------------------------

    def _clear_rows(self, rows):
        while rows.count():
            child = rows.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

    def _make_row(self):
        row = QFrame()
        row.setObjectName("tile")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 6, 10, 6)
        return row, lay

    # -- refresh --------------------------------------------------------

    def refresh(self):
        try:
            self._refresh_priority()
        except Exception:
            pass
        try:
            self._refresh_wire()
        except Exception:
            pass
        try:
            self._refresh_eligible()
        except Exception:
            pass

    def _refresh_priority(self):
        data = _priority(self.game)
        order = data.get("order") or []
        if order:
            parts = []
            for t in order:
                rank, name = t["rank"], t["team"]
                if t.get("is_user"):
                    parts.append(f"**#{rank} {name}**")
                else:
                    parts.append(f"#{rank} {name}")
            text = " → ".join(parts)
        else:
            text = "Priority order unavailable."
        basis = data.get("basis") or ""
        rank = data.get("my_rank")
        suffix = []
        if basis:
            suffix.append(basis)
        if rank:
            suffix.append(f"your claim rank: #{rank}")
        if suffix:
            text += "\n" + " · ".join(suffix)
        self._prio_strip.setText(text)

    def _refresh_wire(self):
        self._clear_rows(self._wire_rows)
        wire = _wire(self.game)
        self._wire_count.setText(
            f"{len(wire)} player{'s' if len(wire) != 1 else ''} on waivers")
        if not wire:
            self._wire_rows.addWidget(
                QLabel("The waiver wire is empty."))
            return
        for p in wire:
            row, lay = self._make_row()
            ovr = QLabel(str(_player_ovr(p)))
            ovr.setObjectName("section-header")
            ovr.setMinimumWidth(36)
            lay.addWidget(ovr)

            name = _player_name(p)
            wteam = _safe(lambda: getattr(p, "waiver_team", ""), "") or ""
            sub = (f"{_pos_str(p)} · Age "
                   f"{_safe(lambda: int(getattr(p, 'age', 0) or 0), 0)} · "
                   f"{_fmt_money(_safe(lambda: int(getattr(p, 'salary', 0) or 0), 0))}"
                   + (f" · from {wteam}" if wteam else ""))
            info = QLabel(f"{name}\n{sub}")
            info.setWordWrap(True)
            lay.addWidget(info, 1)

            clock = QLabel("⏱ " + _deadline_str(
                _safe(lambda: int(getattr(p, "waiver_days", 0) or 0), 0)))
            lay.addWidget(clock)

            btn = QPushButton("Claim")
            btn.setObjectName("primary-btn")
            btn.clicked.connect(
                lambda _c, b=btn, pl=p: self._on_claim(b, pl))
            lay.addWidget(btn)
            self._wire_rows.addWidget(row)

    def _refresh_eligible(self):
        self._clear_rows(self._elig_rows)
        elig = _eligible(self.game)
        if not elig:
            self._elig_rows.addWidget(
                QLabel("No waiver-eligible players on your roster."))
            return
        for d in elig:
            p = d["player"]
            row, lay = self._make_row()
            ovr = QLabel(str(_player_ovr(p)))
            ovr.setMinimumWidth(36)
            lay.addWidget(ovr)

            tags = ""
            if d.get("nmc_block"):
                tags += "  [NMC]"
            elif d.get("clause") == "NTC":
                tags += "  [NTC]"
            name = _player_name(p) + tags
            sub = (f"{_pos_str(p)} · Age "
                   f"{_safe(lambda: int(getattr(p, 'age', 0) or 0), 0)} · "
                   f"{_fmt_money(_safe(lambda: int(getattr(p, 'salary', 0) or 0), 0))}"
                   + (" · exempt — demotes freely"
                      if d.get("waiver_exempt") else ""))
            info = QLabel(f"{name}\n{sub}")
            info.setWordWrap(True)
            lay.addWidget(info, 1)

            btn = QPushButton("Demote" if d.get("waiver_exempt") else "Waive")
            if d.get("nmc_block"):
                btn.setEnabled(False)
                btn.setToolTip(
                    "No-movement clause blocks waiver placement")
            else:
                btn.clicked.connect(
                    lambda _c, b=btn, pl=p,
                           ex=d.get("waiver_exempt"): self._on_waive(b, pl, ex))
            lay.addWidget(btn)
            self._elig_rows.addWidget(row)

    # -- actions --------------------------------------------------------

    def _on_claim(self, btn, player):
        name = _player_name(player)
        btn.setEnabled(False)
        btn.setText("Claiming…")
        ok, msg = _claim_waiver(self.game, player)
        if ok:
            btn.setText("Pending ⏳")
            self._status(f"Claim submitted for {name}. ⏳ "
                         f"Processed at next waiver run in priority order.")
            if msg:
                self._status(msg)
            QTimer.singleShot(800, self.refresh)
        else:
            btn.setText("Claim")
            btn.setEnabled(True)
            self._status(f"❌ {msg}")

    def _on_waive(self, btn, player, exempt):
        name = _player_name(player)
        if exempt:
            ret = QMessageBox.question(
                self, "Demote",
                f"Send {name} to the AHL? He is waiver-exempt and "
                "clears freely.")
            if ret != QMessageBox.Yes:
                return
            btn.setEnabled(False)
            btn.setText("Sending…")
            ok, msg = _demote_exempt(self.game, player)
            if ok:
                btn.setText("Sent ✓")
                self._status(f"{name} assigned to the AHL. ✓")
                QTimer.singleShot(800, self.refresh)
            else:
                btn.setText("Demote")
                btn.setEnabled(True)
                self._status(f"❌ {msg}")
            return
        ret = QMessageBox.question(
            self, "Place on waivers",
            f"Place {name} on waivers? Other teams will have a chance "
            "to claim him (2-day wire).")
        if ret != QMessageBox.Yes:
            return
        btn.setEnabled(False)
        btn.setText("Waiving…")
        ok, msg = _place_on_waivers(self.game, player)
        if ok:
            btn.setText("On Waivers ✓")
            self._status(f"{name} placed on waivers. ✓")
            QTimer.singleShot(800, self.refresh)
        else:
            btn.setText("Waive")
            btn.setEnabled(True)
            self._status(f"❌ {msg}")

    def _status(self, text):
        self._status_lbl.setText(text)
