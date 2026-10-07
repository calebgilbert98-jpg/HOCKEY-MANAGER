"""Offer Sheets screen: sign a rival club's unsigned RFA.

Native port of the web UI offer sheets screen
(web_ui/templates/offer_sheets.html + web_ui/screens/offer_sheets.py +
web_ui/static/js/offer_sheets.js). Calls the game object DIRECTLY --
no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same rulebook as the desktop
OfferSheetWindow and the July pass):
  - rfa_system: is_rfa, market_value_estimate, offer_sheet_compensation,
    own_pick_available, ai_match_decision, apply_offer_sheet_matched,
    execute_offer_sheet
  - player_decision: contract_appeal (interest read),
    player_accepts_offer_sheet (player decision)
  - salary_cap_system.cap_breakdown(team)["space"]
  - transaction_windows.check_window("offer_sheet", date)
  - attribute_composites.talent_tier
"""

from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSlider, QSplitter, QVBoxLayout, QWidget,
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


def _pos_str(p):
    pos = _safe(lambda: getattr(p, "primary_position", ""), "")
    raw = getattr(pos, "value", pos)
    try:
        return str(raw or "?").strip()
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
# game-data helpers (ported from web_ui/screens/offer_sheets.py)
# ---------------------------------------------------------------------------

def _rfa_mod():
    try:
        import rfa_system as _rfa
        return _rfa
    except Exception:
        return None


def _tier_label(ovr):
    try:
        from attribute_composites import talent_tier
        return talent_tier(int(ovr))
    except Exception:
        return "Decent"


def _targets(game):
    """Unsigned RFAs on rival NHL clubs (arbitration filers excluded --
    filing blocks offer sheets, same as the desktop and the July pass).
    Returns [(player, team, market), ...] sorted by market desc."""
    rfa = _rfa_mod()
    if rfa is None:
        return []
    league = _user_league(game)
    user = _user_team(game)
    user_name = str(_safe(lambda: getattr(user, "team_name", ""), ""))
    teams = _safe(lambda: list(getattr(league, "teams", None) or []),
                  []) or []
    out = []
    for team in teams:
        try:
            if team is user:
                continue
            if str(_safe(lambda: getattr(team, "team_name", ""),
                         "")) == user_name:
                continue
            if str(_safe(lambda: getattr(team, "league_name", ""),
                         "")) != "National Hockey League":
                continue
            for p in list(_safe(lambda: getattr(team, "roster", None)
                                or [], []) or []):
                try:
                    if not rfa.is_rfa(p):
                        continue
                    if bool(getattr(p, "arbitration_filed", False)):
                        continue
                    if bool(getattr(p, "offer_sheet_pending", False)):
                        continue
                    market = int(rfa.market_value_estimate(p) or 0)
                    out.append((p, team, market))
                except Exception:
                    continue
        except Exception:
            continue
    out.sort(key=lambda t: t[2], reverse=True)
    return out


def _cap_space(game, team):
    try:
        from salary_cap_system import cap_breakdown
        return int(_safe(lambda: cap_breakdown(team).get("space", 0),
                         0) or 0)
    except Exception:
        return 0


def _window_check(game):
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(game, "current_date", None))
        ok, why = _tw.check_window("offer_sheet", d)
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _compensation_pick_status(user_team, year, picks):
    """Port of compensation_pick_status (offer_sheet_ui.py): which required
    compensation picks the user can actually furnish (own picks, no
    double-count). Returns (lines, missing_rounds). Never raises."""
    rfa = _rfa_mod()
    lines, missing, used = [], [], set()
    if rfa is None:
        return lines, picks
    for rnd in picks:
        pk, y = None, year
        for yy in range(year, year + 7):
            cand = _safe(lambda: rfa.own_pick_available(user_team, yy, rnd))
            if cand is not None and id(cand) not in used:
                pk, y = cand, yy
                break
        if pk is None:
            missing.append(rnd)
            lines.append({"ok": False,
                          "text": f"round {rnd}: not yours to trade "
                                  f"({year}-{year + 6})"})
        else:
            used.add(id(pk))
            lines.append({"ok": True,
                          "text": f"{y} round {rnd} (your own pick)"})
    return lines, missing


def _preview(game, player, aav, years):
    """Live preview: compensation, checks, qualitative interest read
    (no roll revealed -- desktop rule). Mirrors
    OfferSheetWindow._update_preview. Returns dict; never raises."""
    out = {"ok": False, "error": "", "compensation": None, "checks": [],
           "valid": False, "interest": "", "market": 0}
    rfa = _rfa_mod()
    user = _user_team(game)
    league = _user_league(game)
    if rfa is None or user is None or league is None:
        out["error"] = "Offer-sheet engine unavailable."
        return out
    try:
        label, picks = rfa.offer_sheet_compensation(aav)
    except Exception:
        label, picks = "?", []
    year = int(_safe(lambda: getattr(league, "season_year", 2026),
                     2026) or 2026) + 1
    comp_lines, missing = _compensation_pick_status(user, year, picks)
    out["compensation"] = {"label": label or "No compensation",
                           "lines": comp_lines, "missing": missing}
    checks = []
    space = _cap_space(game, user)
    checks.append({"ok": space >= aav,
                   "text": f"Cap space {_fmt_money(space)} vs "
                           f"{_fmt_money(aav)}/yr"})
    n_roster = _safe(lambda: len(list(getattr(user, "roster", None) or [])),
                     0)
    checks.append({"ok": n_roster < 23,
                   "text": f"Roster {n_roster}/23"})
    if missing:
        checks.append({"ok": False,
                       "text": "Missing own picks — sheet can't be signed"})
    win_ok, win_msg = _window_check(game)
    checks.append({"ok": win_ok,
                   "text": ("Offer-sheet window open" if win_ok
                            else f"Window closed — {win_msg}")})
    out["checks"] = checks
    out["valid"] = bool(all(c["ok"] for c in checks))
    # Qualitative interest read (no roll revealed) -- desktop rule.
    try:
        import player_decision as _pd
        original_team = None
        for (p, t, _m) in _targets(game):
            if _pid(p) == _pid(player):
                original_team = t
                break
        appeal, _reasons = _pd.contract_appeal(
            player, user, aav, years, current_team=original_team,
            league=league, app=game, is_offer_sheet=True)
        if appeal >= 0.7:
            out["interest"] = "His camp is listening closely."
        elif appeal >= 0.52:
            out["interest"] = "His camp is lukewarm — money talks."
        elif appeal >= 0.35:
            out["interest"] = "His camp sounds cool on the idea."
        else:
            out["interest"] = "His camp wants nothing to do with this."
    except Exception:
        pass
    try:
        out["market"] = int(rfa.market_value_estimate(player) or 0)
    except Exception:
        pass
    out["ok"] = True
    return out


def _present(game, player, aav, years):
    """Run the desktop present-offer-sheet flow on the Qt thread:
    revalidate window/picks/cap/roster, then the real engine
    (player_accepts_offer_sheet -> ai_match_decision ->
    apply_offer_sheet_matched / execute_offer_sheet).
    Port of handle_present_offer_sheet_command. Returns (ok, summary)."""
    rfa = _rfa_mod()
    if rfa is None:
        return False, "Offer-sheet engine unavailable."
    league = _user_league(game)
    user = _user_team(game)
    pname = _player_name(player)
    if user is None or league is None:
        return False, f"{pname} is no longer an available target."
    # 1. Window gate.
    win_ok, win_msg = _window_check(game)
    if not win_ok:
        return False, (win_msg or "Offer-sheet window closed.")
    # 2. Compensation + own picks.
    try:
        label, picks = rfa.offer_sheet_compensation(aav)
    except Exception as e:
        return False, f"Could not price compensation: {e}"
    year = int(_safe(lambda: getattr(league, "season_year", 2026),
                     2026) or 2026) + 1
    _lines, missing = _compensation_pick_status(user, year, picks)
    if missing:
        return False, (f"You don't hold your own picks for the required "
                       f"compensation ({label}). Without them the sheet "
                       "can't be signed.")
    # 3. Cap + roster room.
    space = _cap_space(game, user)
    if space < aav:
        return False, (f"Not enough cap space: {_fmt_money(space)} "
                       f"available vs {_fmt_money(aav)}/yr.")
    n_roster = _safe(lambda: len(list(getattr(user, "roster", None) or [])),
                     0)
    if n_roster >= 23:
        return False, "Your NHL roster is full (23/23)."
    # 4. The player must agree to sign (real engine).
    try:
        import player_decision as _pd
        original_team = None
        for (p, t, _m) in _targets(game):
            if _pid(p) == _pid(player):
                original_team = t
                break
        rng = _safe(lambda: getattr(game, "_rng", None))
        willing, _appeal, reasons = _pd.player_accepts_offer_sheet(
            player, user, aav, years, original_team,
            league=league, app=game, rng=rng)
    except Exception:
        willing, reasons = True, []
    if not willing:
        why = f" {reasons[0]}" if reasons else ""
        try:
            news = getattr(game, "add_news", None)
            if callable(news):
                news(f"{pname} rejects your offer sheet "
                     f"({_fmt_money(aav)}/yr x {years}y).{why}")
        except Exception:
            pass
        return False, f"{pname} won't sign.{why}"
    # 5. The original club matches or declines -- ai_match_decision,
    #    the same the July pass uses. One rulebook.
    try:
        tname = (_safe(lambda: getattr(original_team, "team_name", "?"),
                       "?") if original_team is not None else "?")
        if rfa.ai_match_decision(original_team, player, aav, label):
            mres = rfa.apply_offer_sheet_matched(
                league, user, original_team, player, aav, years, app=game)
            story = mres.get("story", "") if isinstance(mres, dict) else ""
            msg = f"{tname} matched. He stays."
            if story:
                msg += f" {story}"
            return True, msg
        res = rfa.execute_offer_sheet(
            league, user, original_team, player, aav, years,
            app=game, rng=_safe(lambda: getattr(game, "_rng", None)))
        if isinstance(res, dict) and not res.get("ok"):
            return False, (f"The sheet failed: "
                           f"{res.get('reason', 'unknown')}.")
        story = res.get("story", "") if isinstance(res, dict) else ""
        msg = f"He's yours! {label} goes to {tname}."
        if story:
            msg += f" {story}"
        return True, msg
    except Exception as e:
        return False, f"Offer sheet failed: {e}"


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class OfferSheetsScreen(BaseScreen):
    """Sign a rival club's unsigned RFA: pick a target, tune AAV/term,
    watch the live compensation preview, present the sheet."""

    title = "Offer Sheets"

    _AAV_MIN = 1.0
    _AAV_MAX = 12.0

    def _build_body(self):
        self._selected = None  # (player, team, market)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        splitter = QSplitter(Qt.Horizontal)
        self._layout.addWidget(splitter, 1)

        # --- left: target list ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_group = QGroupBox("Unsigned RFAs")
        lg = QVBoxLayout(left_group)
        self._count_lbl = QLabel("")
        lg.addWidget(self._count_lbl)
        self._target_list = QListWidget()
        self._target_list.currentRowChanged.connect(self._on_select)
        lg.addWidget(self._target_list)
        left_layout.addWidget(left_group)
        splitter.addWidget(left)

        # --- right: detail + terms ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_group = QGroupBox("Target")
        dg = QVBoxLayout(detail_group)
        self._detail_lbl = QLabel("Select a player on the left.")
        self._detail_lbl.setWordWrap(True)
        dg.addWidget(self._detail_lbl)
        right_layout.addWidget(detail_group)

        terms_group = QGroupBox("Terms")
        tg = QVBoxLayout(terms_group)

        aav_row = QHBoxLayout()
        aav_row.addWidget(QLabel("AAV"))
        self._aav_slider = QSlider(Qt.Horizontal)
        self._aav_slider.setRange(int(self._AAV_MIN * 10),
                                 int(self._AAV_MAX * 10))
        self._aav_slider.setValue(40)
        self._aav_slider.setTickPosition(QSlider.TicksBelow)
        self._aav_slider.setTickInterval(10)
        self._aav_slider.valueChanged.connect(self._on_terms_changed)
        aav_row.addWidget(self._aav_slider, 1)
        self._aav_val = QLabel("$4.0M")
        self._aav_val.setMinimumWidth(70)
        aav_row.addWidget(self._aav_val)
        tg.addLayout(aav_row)

        yrs_row = QHBoxLayout()
        yrs_row.addWidget(QLabel("Term"))
        self._yrs_slider = QSlider(Qt.Horizontal)
        self._yrs_slider.setRange(1, 5)
        self._yrs_slider.setValue(4)
        self._yrs_slider.setTickPosition(QSlider.TicksBelow)
        self._yrs_slider.setTickInterval(1)
        self._yrs_slider.valueChanged.connect(self._on_terms_changed)
        yrs_row.addWidget(self._yrs_slider, 1)
        self._yrs_val = QLabel("4 yrs")
        self._yrs_val.setMinimumWidth(70)
        yrs_row.addWidget(self._yrs_val)
        tg.addLayout(yrs_row)
        right_layout.addWidget(terms_group)

        comp_group = QGroupBox("Compensation preview")
        cg = QVBoxLayout(comp_group)
        self._comp_lbl = QLabel("Select a target to preview compensation.")
        self._comp_lbl.setWordWrap(True)
        cg.addWidget(self._comp_lbl)
        right_layout.addWidget(comp_group)

        checks_group = QGroupBox("Eligibility checks")
        chg = QVBoxLayout(checks_group)
        self._checks_lbl = QLabel("")
        self._checks_lbl.setWordWrap(True)
        chg.addWidget(self._checks_lbl)
        right_layout.addWidget(checks_group)

        self._interest_lbl = QLabel("")
        self._interest_lbl.setWordWrap(True)
        right_layout.addWidget(self._interest_lbl)

        self._result_lbl = QLabel("")
        self._result_lbl.setWordWrap(True)
        right_layout.addWidget(self._result_lbl)

        self._present_btn = QPushButton("Present Offer Sheet")
        self._present_btn.setObjectName("primary-btn")
        self._present_btn.setEnabled(False)
        self._present_btn.clicked.connect(self._on_present)
        right_layout.addWidget(self._present_btn)

        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([320, 520])

        self.refresh()

    # -- data ----------------------------------------------------------

    def refresh(self):
        try:
            self._load_targets()
        except Exception:
            pass

    def _load_targets(self):
        game = self.game
        targets = _targets(game)
        win_ok, win_msg = _window_check(game)
        user = _user_team(game)
        space = _cap_space(game, user)
        self._target_list.clear()
        self._items = []
        for (p, team, market) in targets:
            tname = _safe(lambda: getattr(team, "team_name", "?"), "?")
            text = (f"{_player_name(p)} — {_pos_str(p)}, age "
                    f"{_safe(lambda: int(getattr(p, 'age', 0) or 0), 0)}, "
                    f"{tname}, {_tier_label(_player_ovr(p))}\n"
                    f"Est. value {_fmt_money(market)}/yr")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, _pid(p))
            self._target_list.addItem(item)
            self._items.append((p, team, market))
        n = len(targets)
        self._count_lbl.setText(
            f"{n} target{'s' if n != 1 else ''}")
        win_txt = ("window OPEN (Jul 1 – Dec 1)" if win_ok
                   else f"window CLOSED — {win_msg or 'unknown reason'}")
        self._status_lbl.setText(
            f"{win_txt}  •  {n} unsigned RFA{'s' if n != 1 else ''} on "
            f"the market  •  Your cap space: {_fmt_money(space)}")
        if self._selected is not None:
            sel_pid = _pid(self._selected[0])
            still = [t for t in targets if _pid(t[0]) == sel_pid]
            self._selected = still[0] if still else None
            if self._selected is None:
                self._detail_lbl.setText("Select a player on the left.")
                self._present_btn.setEnabled(False)

    # -- selection ------------------------------------------------------

    def _on_select(self, row):
        if row < 0 or row >= len(getattr(self, "_items", [])):
            self._selected = None
            return
        self._selected = self._items[row]
        player, team, market = self._selected
        self._result_lbl.setText("")
        tname = _safe(lambda: getattr(team, "team_name", "?"), "?")
        self._detail_lbl.setText(
            f"{_player_name(player)} — {_pos_str(player)}, age "
            f"{_safe(lambda: int(getattr(player, 'age', 0) or 0), 0)}, "
            f"{_tier_label(_player_ovr(player))}\n"
            f"Rights held by: {tname}\n"
            f"Engine's market read: {_fmt_money(market)}/yr")
        # Start the AAV at his market read (desktop behavior).
        aav = max(self._AAV_MIN, min(self._AAV_MAX, market / 1_000_000))
        self._aav_slider.setValue(int(round(aav * 10)))
        self._schedule_preview()

    # -- terms -----------------------------------------------------------

    def _current_terms(self):
        aav = self._aav_slider.value() / 10.0
        years = self._yrs_slider.value()
        self._aav_val.setText(f"${aav:.1f}M")
        self._yrs_val.setText(f"{years} yr{'s' if years != 1 else ''}")
        return int(round(aav * 1_000_000)), years

    def _on_terms_changed(self, _v):
        self._current_terms()
        self._schedule_preview()

    def _schedule_preview(self):
        self._preview_timer.stop()
        self._preview_timer.start(250)  # 250ms debounce

    def _refresh_preview(self):
        if self._selected is None:
            return
        player, _team, _market = self._selected
        aav, years = self._current_terms()
        self._present_btn.setEnabled(False)
        pv = _preview(self.game, player, aav, years)
        if not pv.get("ok"):
            self._comp_lbl.setText(pv.get("error")
                                   or "Preview unavailable.")
            return
        comp = pv.get("compensation") or {}
        lines = [f"{'✅' if l['ok'] else '❌'} {l['text']}"
                 for l in comp.get("lines") or []]
        if not lines:
            lines = ["No picks change hands."]
        self._comp_lbl.setText(
            (comp.get("label") or "") + "\n" + "\n".join(lines))
        checks = [f"{'✅' if c['ok'] else '❌'} {c['text']}"
                  for c in pv.get("checks") or []]
        self._checks_lbl.setText("\n".join(checks))
        interest = pv.get("interest") or ""
        self._interest_lbl.setText(f"📣 {interest}" if interest else "")
        self._present_btn.setEnabled(bool(pv.get("valid")))

    # -- present ----------------------------------------------------------

    def _on_present(self):
        if self._selected is None:
            return
        player, _team, _market = self._selected
        aav, years = self._current_terms()
        name = _player_name(player)
        ret = QMessageBox.question(
            self, "Present offer sheet",
            f"Present an offer sheet to {name} "
            f"({_fmt_money(aav)}/yr × {years}y)?")
        if ret != QMessageBox.Yes:
            return
        self._present_btn.setEnabled(False)
        self._result_lbl.setText("Presenting…")
        ok, summary = _present(self.game, player, aav, years)
        if ok:
            self._result_lbl.setText(f"🎉 {summary}")
            self._selected = None
            self._detail_lbl.setText("Select a player on the left.")
            self.refresh()
        else:
            self._result_lbl.setText(f"❌ {summary}")
            self._refresh_preview()
