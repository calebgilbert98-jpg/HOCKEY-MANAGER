"""Free Agents screen: UFA/RFA player market, staff hiring, market overview.

Native port of the web UI free agents screen
(web_ui/templates/free_agents.html + web_ui/screens/free_agents.py +
web_ui/static/js/free_agents.js). Calls the game object DIRECTLY --
no Flask/HTTP, no command queue, no JSON.

3 tabs: Players, Staff, Market Overview.

Game methods / systems used (all real, same as the web bridge called):
  - league.free_agents, league.free_agent_staff (free-agent pools)
  - game.get_live_cap() / league.salary_cap_system
  - game._validate_contract_terms(p, salary, years, extension=False)
  - game.handle_contract_offer(p, extension=False, notify="inbox")
    (via native_ui/screens/contracts.py::submit_offer -- same staging
    and inbox-thread mirroring as the web v3 negotiation flow)
  - game.calculate_player_value(p) (market-value estimate)
  - salary_cap_system: base_ask_dollars, fa_market_scarcity,
    max_contract_term, league_minimum_salary, total_cap_charge
  - transaction_windows.check_window("sign_ufa", date)
  - roster_limits.can_sign_player(p)
  - trade_engine: clause_eligible, clause_demand_score
  - game_classes: staff_market_ask, team_can_afford_staff, position_label
  - game_manager.sign_free_agent_staff(target, salary, years, assignment)
    + assistant_coaches.on_assistant_hired + tactics hooks (staff hire)
  - event_day_hubs.is_free_agency_day (FA Frenzy banner)
  - league.news_log (done-deals feed)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QDoubleSpinBox, QComboBox, QLineEdit, QGroupBox, QTabWidget,
    QScrollArea, QWidget, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator

from .base import BaseScreen
from .contracts import (
    _safe, _fmt_money, _pid, _player_name, _pos_str, _live_cap,
    _resolve_gm, _user_team, _user_league, _salary_bounds, _cap_state,
    _clause_info, _offer_extras, submit_offer, NegotiationDialog,
)


# ---------------------------------------------------------------------------
# free-agent data helpers (natively ported from web_ui/screens/free_agents.py)
# ---------------------------------------------------------------------------

def _fa_type(p):
    """Best-effort UFA/RFA label. Never raises."""
    try:
        if getattr(p, "ufa", None):
            return "UFA"
        if getattr(p, "rfa", None):
            return "RFA"
        age = int(getattr(p, "age", 0) or 0)
        pro = _safe(lambda: int(getattr(p, "years_pro", 0)
                                or getattr(p, "seasons_played", 0) or 0), 0)
        if age >= 27 or pro >= 7:
            return "UFA"
        return "RFA"
    except Exception:
        return "FA"


def _fa_pos_label(p):
    """Best-effort position label (web _web_position parity). Never raises."""
    try:
        from game_classes import position_label
        label = _safe(lambda: position_label(p))
        if label and label != "?":
            return label
    except Exception:
        pass
    return _pos_str(p)


def _fa_pool(game):
    # Prefer the GameManager.free_agents property: it reads the
    # database_manager (players with team_name == "Free Agent"), while
    # league.free_agents is a legacy list that stays empty on fresh careers.
    gm = _resolve_gm(game)
    pool = _safe(lambda: list(getattr(gm, "free_agents", None) or []), None)
    if pool:
        return pool
    league = _user_league(game)
    return _safe(lambda: list(getattr(league, "free_agents", None) or []),
                 []) or []


def _find_fa(game, pid):
    pid_s = str(pid)
    for p in _fa_pool(game):
        if _pid(p) == pid_s:
            return p
    return None


def _fa_ask(game, p):
    """Read-only replica of the agent's ask from
    HockeyManagerGUI.handle_contract_offer: cap-relative base ask via
    salary_cap_system.base_ask_dollars -> demand_for with the live UFA
    scarcity multiplier, +8% clause premium when the player badly wants
    protection and none is offered. Never raises."""
    try:
        from game_classes import to_100_scale
        from salary_cap_system import (base_ask_dollars, fa_market_scarcity)
        league = _user_league(game)
        cap_sys = _safe(lambda: getattr(league, "salary_cap_system", None))
        cap = _live_cap(game)
        ovr100 = int(to_100_scale(p.overall_rating()))
        pos = getattr(p, "primary_position", "")
        pos_name = pos.value if hasattr(pos, "value") else str(pos)
        age = int(getattr(p, "age", 27) or 27)
        contract = _safe(lambda: getattr(p, "contract", None))
        on_elc = bool(_safe(lambda: getattr(contract, "entry_level", False),
                            False))
        base_pct = base_ask_dollars(ovr100, age, on_elc, pos_name) / cap
        sc = _safe(lambda: fa_market_scarcity(league, pos_name), {}) or {}
        scarcity = float(_safe(lambda: sc.get("multiplier", 1.0), 1.0))
        season = _safe(lambda: int(getattr(league, "season_year", 0) or 0), 0)
        if cap_sys is not None:
            asking = cap_sys.demand_for(base_pct, ovr100, pos_name, age,
                                        season, scarcity=scarcity)
        else:
            asking = int(base_pct * cap)
        # Floor at the season-aware league minimum (not a hardcoded $750k).
        try:
            from salary_cap_system import league_minimum_salary as _lms2
            _ask_floor2 = int(_safe(lambda: _lms2(season), 750_000) or 750_000)
        except Exception:
            _ask_floor2 = 750_000
        asking = max(int(asking), _ask_floor2)
        try:
            import trade_engine as _te
            team = _user_team(game)
            if _te.clause_demand_score(p, team, league) >= 0.65:
                asking = int(asking * 1.08)
        except Exception:
            pass
        return asking
    except Exception:
        return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)


def _player_ovr(p):
    try:
        fn = getattr(p, "overall_rating", None)
        if callable(fn):
            v = fn()
            if v:
                return int(v)
        v = getattr(p, "overall", None)
        if v:
            return int(v)
    except Exception:
        pass
    return 0


def _fa_row(game, p):
    """One free agent's row data (ask computed once). Never raises."""
    ask = _fa_ask(game, p)
    return {
        "player": p,
        "id": _pid(p),
        "name": _player_name(p),
        "position": _fa_pos_label(p),
        "pos_short": _pos_str(p),
        "fa_type": _fa_type(p),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
        "overall": _player_ovr(p),
        "ask": ask,
    }


def _fa_term_bounds():
    """(min_years, max_years) for external signings: new CBA = 6."""
    try:
        from salary_cap_system import max_contract_term
        return 1, int(max_contract_term(False))
    except Exception:
        return 1, 6


def _validate_fa_offer(game, p, salary, years):
    """Validation through the game's own shared gate
    (HockeyManagerGUI._validate_contract_terms, extension=False).
    Returns (ok, message)."""
    try:
        ok, msg = game._validate_contract_terms(p, int(salary), int(years),
                                                extension=False)
        return bool(ok), (msg or "")
    except Exception:
        return False, "Could not validate contract terms."


def _fa_window(game):
    """transaction_windows check: UFA market opens July 1.
    Returns (ok, reason)."""
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(game, "current_date", None))
        ok, why = _tw.check_window("sign_ufa", d)
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _fa_eligibility(p):
    """roster_limits.can_sign_player: Dec-1 ineligible RFAs and emergency
    fillers can't sign. Returns (ok, reason)."""
    try:
        import roster_limits as _rl
        ok, why = _rl.can_sign_player(p)
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _suggested_years(p, years_max):
    age = _safe(lambda: int(getattr(p, "age", 27) or 27), 27)
    return max(1, min(int(years_max), 3 if age >= 33 else 5))


def _fa_demands(game, p, years=0, aav=0):
    """Agent's asking price + term/salary bounds + cap preview for a free
    agent (native equivalent of /api/free_agents/demands). Never raises."""
    try:
        ask = _fa_ask(game, p)
        years_min, years_max = _fa_term_bounds()
        min_sal, max_sal = _salary_bounds(game)
        if not years:
            years = _suggested_years(p, years_max)
        if not aav:
            aav = ask
        window_ok, window_msg = _fa_window(game)
        elig_ok, elig_msg = _fa_eligibility(p)
        valid, valid_msg = _validate_fa_offer(game, p, aav, years)
        return {
            "ok": True,
            "ask": ask,
            "years_min": years_min, "years_max": years_max,
            "years_suggested": _suggested_years(p, years_max),
            "min_salary": min_sal, "max_salary": max_sal,
            "cap": _cap_state(game, offer_salary=aav, extension=False),
            "window": {"ok": window_ok, "reason": window_msg},
            "eligibility": {"ok": elig_ok, "reason": elig_msg},
            "valid": valid and window_ok and elig_ok,
            "valid_reason": valid_msg or window_msg or elig_msg,
            "note": ("Qualifying offers enter a 3-7 day UFA consideration "
                     "period -- the player fields all clubs' bids before "
                     "deciding. This is not an instant signing."),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# analysis / compare / market helpers
# ---------------------------------------------------------------------------

def _fa_analysis(game, p):
    """Market analysis for one player: value, comparables, projection."""
    try:
        mv = int(_safe(lambda: game.calculate_player_value(p), 0) or 0)
    except Exception:
        mv = 0
    ovr = _player_ovr(p)
    age = _safe(lambda: int(getattr(p, "age", 28) or 28), 28)
    ask = _fa_ask(game, p)
    if not mv:
        mv = int(max(750_000, (ovr - 60) * 450_000
                     * max(0.4, 1 - (age - 28) * 0.06)))
    diff = mv - ask
    if diff > 500_000:
        verdict, vcolor = f"UNDERVALUED by {_fmt_money(diff)}", "green"
    elif diff < -500_000:
        verdict, vcolor = f"OVERVALUED by {_fmt_money(abs(diff))}", "red"
    else:
        verdict, vcolor = "FAIRLY VALUED", "blue"
    # Comparables: same position, similar overall (+/-3), from FA pool.
    comps = []
    pos = _fa_pos_label(p)
    for q in _fa_pool(game):
        try:
            if q is p:
                continue
            if _fa_pos_label(q) != pos:
                continue
            if abs(_player_ovr(q) - ovr) > 3:
                continue
            comps.append({
                "name": _player_name(q), "overall": _player_ovr(q),
                "age": _safe(lambda: int(getattr(q, "age", 0) or 0), 0),
                "ask": _fa_ask(game, q),
            })
            if len(comps) >= 5:
                break
        except Exception:
            continue
    years_max = _fa_term_bounds()[1]
    return {
        "ok": True,
        "player_name": _player_name(p),
        "value": {"market_value": mv, "ask": ask, "verdict": verdict,
                  "color": vcolor},
        "comparables": comps,
        "projection": {
            "years": _suggested_years(p, years_max),
            "aav_low": int(mv * 0.9), "aav_high": int(mv * 1.1),
        },
    }


_COMPARE_ATTRS = ("shooting_accuracy", "passing", "skating", "checking",
                  "defensive_awareness", "offensive_awareness", "strength")


def _compare_rows(game, pids):
    """Side-by-side data for up to 3 free agents. Never raises."""
    out = []
    for pid in list(pids)[:3]:
        p = _find_fa(game, pid)
        if p is None:
            continue
        row = _fa_row(game, p)
        attrs = {}
        for a in _COMPARE_ATTRS:
            try:
                attrs[a] = int(getattr(p, a, 0) or 0)
            except Exception:
                pass
        row["compare_attrs"] = attrs
        out.append(row)
    return out


def _market_data(game):
    """Market overview: counts, top available by position, avg asking."""
    try:
        pool = _fa_pool(game)
        by_pos, by_type = {}, {"UFA": 0, "RFA": 0}
        total_ask, n_ask = 0, 0
        top = []
        for p in pool:
            try:
                d = _fa_row(game, p)
                pos = d.get("position") or "?"
                by_pos[pos] = by_pos.get(pos, 0) + 1
                ft = d.get("fa_type") or "FA"
                if ft in by_type:
                    by_type[ft] += 1
                ask = d.get("ask") or 0
                if ask:
                    total_ask += ask
                    n_ask += 1
                top.append(d)
            except Exception:
                continue
        top.sort(key=lambda d: d.get("overall", 0), reverse=True)
        return {
            "total": len(pool),
            "by_position": by_pos,
            "by_type": by_type,
            "avg_ask": int(total_ask / n_ask) if n_ask else 0,
            "top_available": top[:10],
        }
    except Exception:
        return {"total": 0, "by_position": {}, "by_type": {},
                "avg_ask": 0, "top_available": []}


# ---------------------------------------------------------------------------
# FA Frenzy helpers (event-day hub parity)
# ---------------------------------------------------------------------------

def _frenzy_active(game):
    try:
        from event_day_hubs import is_free_agency_day
        d = _safe(lambda: getattr(game, "current_date", None))
        return bool(is_free_agency_day(d))
    except Exception:
        return False


def _frenzy_data(game):
    """Signing wire, top-UFA cards, done-deals feed, cap snapshot."""
    try:
        pool = _fa_pool(game)
        try:
            from draft_generator import player_locked_by_draft as _locked
            pool = [p for p in pool if not _locked(p)]
        except Exception:
            pass
        try:
            from attribute_composites import talent_tier as _tt
        except Exception:
            _tt = None
        top = sorted(pool,
                     key=lambda p: _safe(lambda: float(p.overall_rating()),
                                         0.0) or 0.0,
                     reverse=True)[:8]
        cards = []
        for i, p in enumerate(top, 1):
            try:
                ovr = _safe(lambda: float(p.overall_rating()), 0.0) or 0.0
                cards.append({
                    "rank": i,
                    "id": _pid(p),
                    "name": _player_name(p),
                    "position": _fa_pos_label(p),
                    "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                    "tier": _safe(lambda: _tt(ovr), "") if _tt else "",
                    "season_line": _frenzy_season_line(p),
                    "ask": _fa_ask(game, p),
                    "fa_type": _fa_type(p),
                })
            except Exception:
                continue
        deals = []
        for item in reversed(list(
                _safe(lambda: getattr(game, "news_log", None) or [],
                      []) or [])):
            story = item.get("story", "") if isinstance(item, dict) \
                else str(item or "")
            low = story.lower()
            if ("signed" in low or "signing" in low) \
                    and "assign" not in low:
                deals.append(story)
            if len(deals) >= 12:
                break
        cap = 104_000_000
        charge = 0
        try:
            cap = _live_cap(game)
            team = _user_team(game)
            from salary_cap_system import total_cap_charge
            charge = int(_safe(lambda: total_cap_charge(team), 0) or 0)
        except Exception:
            pass
        return {"cards": cards, "deals": deals or ["No signings yet today."],
                "cap": cap, "committed": charge, "space": cap - charge,
                "count": len(pool)}
    except Exception:
        return {"cards": [], "deals": [], "cap": 104_000_000,
                "committed": 0, "space": 104_000_000, "count": 0}


def _frenzy_season_line(p):
    try:
        gp = int(getattr(p, "games_played", 0) or 0)
    except Exception:
        gp = 0
    if gp <= 0:
        return "No games played this season"
    pos = _safe(lambda: getattr(getattr(p, "primary_position", ""),
                                "value", ""), "")
    if pos.upper() in ("G", "GOALIE", "GOALTENDER"):
        w = getattr(p, "wins", 0) or 0
        sv = getattr(p, "save_percentage", 0) or 0
        gaa = getattr(p, "goals_against_avg", 0) or 0
        return f"{gp} GP · {w} W · {sv:.3f} SV% · {gaa:.2f} GAA"
    g = getattr(p, "goals", 0) or 0
    a = getattr(p, "assists", 0) or 0
    pts = getattr(p, "points", g + a) or 0
    return f"{gp} GP · {g} G · {a} A · {pts} P"


# ---------------------------------------------------------------------------
# staff hiring helpers (ported from web_ui/screens/free_agents.py staff tab
# + the web bridge's hire_staff op -- run synchronously here, no queue)
# ---------------------------------------------------------------------------

_STAFF_DEPTS = ("Management", "Coaching", "Development", "Scouting",
                "Medical", "Analytics")


def _staff_pool(game):
    league = _user_league(game)
    pool = _safe(lambda: list(getattr(league, "free_agent_staff", None)
                              or getattr(league, "staff_free_agents", None)
                              or []), []) or []
    return pool


def _staff_overall(s):
    try:
        ratings = []
        for attr in ("tactics", "development", "scouting", "leadership",
                     "motivation", "discipline", "man_management"):
            v = getattr(s, attr, None)
            if isinstance(v, (int, float)) and v > 0:
                ratings.append(v)
        if ratings:
            return int(sum(ratings) / len(ratings))
        return int(getattr(s, "overall", 0) or getattr(s, "rating", 0) or 0)
    except Exception:
        return 0


def _staff_row(s):
    name = _safe(lambda: getattr(s, "full_name", None)
                 or getattr(s, "name", "?"), "?")
    role = _safe(lambda: str(getattr(getattr(s, "role", ""), "value",
                                     getattr(s, "role", "")) or ""), "")
    dept = _safe(lambda: str(getattr(s, "department", "") or ""), "")
    return {
        "staff": s,
        "id": _safe(lambda: str(getattr(s, "id", "")), ""),
        "name": name,
        "role": role,
        "department": dept,
        "age": _safe(lambda: int(getattr(s, "age", 0) or 0), 0),
        "salary": _safe(lambda: int(getattr(s, "salary", 0) or 0), 0),
        "overall": _staff_overall(s),
        "experience": _safe(lambda: int(getattr(s, "experience", 0)
                                        or getattr(s, "years_experience", 0)
                                        or 0), 0),
    }


def _staff_offer_chance(game, s, salary):
    """Desktop StaffContractView._staff_offer_accept_chance parity
    (display-side estimate of the negotiate_contract roll)."""
    try:
        from game_classes import staff_market_ask, to_100_scale
        import reputation_system as _rs
        team = _user_team(game)
        ask = staff_market_ask(s)
        salary_mult = salary / max(1, ask)
        try:
            rating = to_100_scale(_safe(
                lambda: (getattr(s, "overall_rating", 60)()
                         if callable(getattr(s, "overall_rating", None))
                         else getattr(s, "overall_rating", 60)) or 60,
                60))
        except Exception:
            rating = 60
        prestige = _safe(lambda: getattr(team, "prestige", 50), 50)
        base = (0.45 + (salary_mult - 1.0) * 1.4
                + (prestige - 50) / 400 - (rating - 60) / 600)
        try:
            base += _rs.gm_staff_accept_delta(team) if team else 0
        except Exception:
            pass
        return max(0.05, min(0.98, base))
    except Exception:
        return 0.5


def _staff_conflict(game, s):
    """Unique-role conflict preview (GM / Head Coach can't double).
    Returns the conflict message or ''. Never raises."""
    try:
        from game_classes import Staff as _StaffCls
        if _StaffCls.is_unique_role(getattr(s, "role", None)):
            team = _user_team(game)
            for cur in (getattr(team, "staff", None) or []):
                if (cur is not s and getattr(cur, "role", None)
                        == getattr(s, "role", None)):
                    return (f"Team already has a "
                            f"{getattr(s.role, 'value', 'role')}: "
                            f"{getattr(cur, 'full_name', '?')}.")
    except Exception:
        pass
    return ""


def _staff_market_ask(s):
    try:
        from game_classes import staff_market_ask
        return int(staff_market_ask(s))
    except Exception:
        return 0


def _hire_staff(game, sid, salary, years, assignment="nhl"):
    """Hire a free-agent staffer: unique-role guard, staff-budget gate,
    acceptance roll (same chance math the preview shows), then
    game_manager.sign_free_agent_staff + desktop hire hooks. Returns the
    result dict (bridge op parity). Never raises."""
    result = {"kind": "hire_staff", "ok": False}
    try:
        gm = _resolve_gm(game)
        league = _user_league(game)
        team = _user_team(game)
        if league is None or team is None or not sid:
            result["error"] = "no live game or staff id"
            return result
        target = None
        for s in _staff_pool(game):
            if _safe(lambda: str(getattr(s, "id", "")), "") == str(sid):
                target = s
                break
        if target is None:
            result["error"] = "staffer no longer available"
            return result
        if salary <= 0:
            result["error"] = "enter a salary offer"
            return result
        conflict = _staff_conflict(game, target)
        if conflict:
            result["error"] = conflict + " Reassign or release them first."
            return result
        try:
            from game_classes import team_can_afford_staff as _afford
            if not _afford(team, salary):
                result["error"] = (
                    f"That offer (${salary:,}/yr) exceeds your available "
                    f"staff budget.")
                return result
        except Exception:
            pass
        chance = _staff_offer_chance(game, target, salary)
        import random as _random
        if _random.random() < chance:
            signed = False
            try:
                signed = gm.sign_free_agent_staff(
                    target, salary, years, assignment)
            except Exception:
                signed = False
            if signed:
                try:
                    import assistant_coaches as _ac
                    _ac.on_assistant_hired(team, target, app=game)
                except Exception:
                    pass
                try:
                    _role = str(getattr(
                        getattr(target, "role", None), "value", ""))
                    if "Head Coach" in _role:
                        import tactics as _tx
                        if _tx.get_tactics_control(team) == "coach":
                            _tx.install_coach_systems(team, target,
                                                      reason="hired")
                except Exception:
                    pass
                result.update(
                    ok=True, accepted=True, chance=round(chance, 3),
                    text=(f"{getattr(target, 'full_name', '?')} accepted: "
                          f"${salary:,}/yr x {years}y."))
            else:
                result.update(
                    ok=True, accepted=False, chance=round(chance, 3),
                    text=("The handshake fell through -- budget or pool "
                          "issue. Try again."))
        else:
            result.update(
                ok=True, accepted=False, chance=round(chance, 3),
                text=(f"{getattr(target, 'full_name', '?')} declined your "
                      f"offer. Consider a better salary."))
    except Exception as e:
        result["error"] = str(e)
    return result


# ---------------------------------------------------------------------------
# dialogs
# ---------------------------------------------------------------------------

class OfferDialog(QDialog):
    """Free-agent offer dialog with live term preview, clause picker,
    and cap-fit gating. Submit runs the real game.handle_contract_offer
    via the shared submit_offer helper (same negotiation map the
    contracts screen uses), then hands open talks to NegotiationDialog.

    Emits negotiation_requested(pid) when the offer draws a counter or
    enters the UFA consideration period.
    """

    negotiation_requested = Signal(str)

    def __init__(self, game, pid, parent=None):
        super().__init__(parent)
        self._game = game
        self._pid = str(pid)
        self._player = _find_fa(game, pid)
        self._primed = False
        self._clause_opts = None
        self._clause_size = 10
        self._aav_step = 250_000

        self.setWindowTitle("Sign free agent")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel("Sign free agent")
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        self._player_lbl = QLabel("")
        layout.addWidget(self._player_lbl)

        self._ask_lbl = QLabel("Loading terms…")
        self._ask_lbl.setWordWrap(True)
        layout.addWidget(self._ask_lbl)

        # --- term (years slider) ---
        years_row = QHBoxLayout()
        years_row.addWidget(QLabel("Term"))
        self._years_slider = QSlider(Qt.Horizontal)
        self._years_slider.setRange(1, 6)
        self._years_slider.setValue(4)
        self._years_slider.setTickPosition(QSlider.TicksBelow)
        self._years_slider.setTickInterval(1)
        self._years_slider.valueChanged.connect(self._schedule_preview)
        years_row.addWidget(self._years_slider, 1)
        self._years_val = QLabel("4 yrs")
        self._years_val.setMinimumWidth(60)
        years_row.addWidget(self._years_val)
        layout.addLayout(years_row)

        # --- AAV (spinbox in $M; arrows are the stepper) ---
        aav_row = QHBoxLayout()
        aav_row.addWidget(QLabel("AAV (cap hit/yr)"))
        self._aav_spin = QDoubleSpinBox()
        self._aav_spin.setPrefix("$")
        self._aav_spin.setSuffix("M")
        self._aav_spin.setDecimals(2)
        self._aav_spin.setRange(0, 30)
        self._aav_spin.setSingleStep(0.25)
        self._aav_spin.valueChanged.connect(self._schedule_preview)
        aav_row.addWidget(self._aav_spin)
        aav_row.addStretch()
        layout.addLayout(aav_row)
        self._aav_hint = QLabel("")
        self._aav_hint.setWordWrap(True)
        self._aav_hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._aav_hint)

        # --- trade protection clause ---
        clause_row = QHBoxLayout()
        clause_row.addWidget(QLabel("Trade protection"))
        self._clause_combo = QComboBox()
        self._clause_combo.setMinimumWidth(260)
        self._clause_combo.currentIndexChanged.connect(self._on_clause_changed)
        clause_row.addWidget(self._clause_combo)
        clause_row.addStretch()
        layout.addLayout(clause_row)
        self._clause_hint = QLabel("")
        self._clause_hint.setWordWrap(True)
        self._clause_hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._clause_hint)

        # M-NTC team-list size (revealed only for mntc)
        self._clause_size_box = QWidget()
        size_row = QHBoxLayout(self._clause_size_box)
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.addWidget(QLabel("No-trade list size"))
        self._clause_size_slider = QSlider(Qt.Horizontal)
        self._clause_size_slider.setRange(1, 31)
        self._clause_size_slider.setValue(10)
        self._clause_size_slider.valueChanged.connect(
            self._on_clause_size_changed)
        size_row.addWidget(self._clause_size_slider, 1)
        self._clause_size_val = QLabel("10 teams")
        size_row.addWidget(self._clause_size_val)
        self._clause_size_box.setVisible(False)
        layout.addWidget(self._clause_size_box)

        # --- signing bonus ---
        sb_row = QHBoxLayout()
        sb_row.addWidget(QLabel("Signing bonus"))
        self._sb_edit = QLineEdit("0")
        self._sb_edit.setValidator(QIntValidator(0, 999_999_999, self))
        self._sb_edit.setMaximumWidth(160)
        self._sb_edit.textChanged.connect(self._schedule_preview)
        sb_row.addWidget(self._sb_edit)
        sb_row.addStretch()
        layout.addLayout(sb_row)
        self._sb_hint = QLabel("Sweetens the offer for the player.")
        self._sb_hint.setWordWrap(True)
        self._sb_hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._sb_hint)

        # --- cap preview + note ---
        self._cap_lbl = QLabel("")
        self._cap_lbl.setWordWrap(True)
        layout.addWidget(self._cap_lbl)

        self._note_lbl = QLabel("")
        self._note_lbl.setWordWrap(True)
        self._note_lbl.setStyleSheet("color: #e5484d;")
        layout.addWidget(self._note_lbl)

        # --- actions ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        self._submit_btn = QPushButton("Sign")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setEnabled(False)
        self._submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._submit_btn)
        layout.addLayout(btn_row)

        # 250ms-debounced demand preview.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._refresh_preview)

        self._load_static()
        self._refresh_preview()

    # -- setup ----------------------------------------------------------

    def _load_static(self):
        p = self._player
        if p is None:
            self._player_lbl.setText("Player not found.")
            return
        row = _fa_row(self._game, p)
        self._player_lbl.setText(
            f"{row['name']} · {row['position']} · Age {row['age']} · "
            f"{row['overall']} OVR ({row['fa_type']})")
        self._clause_opts = _clause_info(self._game, p)
        self._clause_combo.clear()
        for i, o in enumerate(self._clause_opts.get("options", [])):
            kind = o.get("kind", "none")
            if kind == "none":
                text = "No trade protection"
            else:
                text = (f"{o.get('label', kind)} "
                        f"(≈{_fmt_money(o.get('annual_value', 0))}/yr value)")
            self._clause_combo.addItem(text, kind)
            if not self._clause_opts.get("eligible", False) \
                    and kind != "none":
                try:
                    self._clause_combo.model().item(i).setEnabled(False)
                except Exception:
                    pass
        self._clause_combo.setCurrentIndex(0)
        self._paint_clause_hint()

    # -- input handlers -------------------------------------------------

    def _terms(self):
        years = self._years_slider.value()
        aav = int(round(self._aav_spin.value() * 1_000_000))
        sb = _safe(lambda: int(
            "".join(c for c in self._sb_edit.text() if c.isdigit()) or 0), 0)
        return {"years": years, "aav": aav, "sb": sb}

    def _clause_kind(self):
        return str(self._clause_combo.currentData() or "none")

    def _schedule_preview(self, _v=None):
        self._debounce.start()

    def _on_clause_changed(self, _i):
        self._paint_clause_hint()
        self._schedule_preview()

    def _on_clause_size_changed(self, v):
        self._clause_size = int(v)
        self._clause_size_val.setText(f"{v} teams")

    def _paint_clause_hint(self):
        kind = self._clause_kind()
        self._clause_size_box.setVisible(kind == "mntc")
        d = self._clause_opts or {}
        if not d.get("eligible", False):
            self._clause_hint.setText(
                d.get("eligibility_note") or "Trade protection unavailable.")
            return
        if kind == "none":
            self._clause_hint.setText(d.get("hint") or "")
            return
        o = next((x for x in d.get("options", [])
                  if x.get("kind") == kind), None)
        if o:
            self._clause_hint.setText(
                f"Offering {o.get('label', kind)} — worth about "
                f"{_fmt_money(o.get('annual_value', 0))}/yr to him "
                f"(counts toward the effective offer).")

    # -- live demand preview --------------------------------------------

    def _refresh_preview(self):
        p = self._player
        if p is None:
            return
        game = self._game
        t = self._terms()
        d = _fa_demands(game, p, t["years"], t["aav"])
        if not d.get("ok"):
            self._ask_lbl.setText(d.get("error") or "Could not load terms")
            self._submit_btn.setEnabled(False)
            return
        years_min, years_max = d["years_min"], d["years_max"]
        min_sal, max_sal = d["min_salary"], d["max_salary"]
        if not self._primed:
            self._primed = True
            sug = d["years_suggested"]
            self._years_slider.setRange(years_min, years_max)
            self._years_slider.setValue(sug)
            span = (max_sal - min_sal) / 40
            step = max(100_000, round(span / 50_000) * 50_000)
            self._aav_step = step
            self._aav_spin.setSingleStep(step / 1_000_000)
            self._aav_spin.setValue(d["ask"] / 1_000_000)
        yrs = min(max(t["years"], years_min), years_max)
        self._years_val.setText(f"{yrs} yr{'s' if yrs > 1 else ''}")
        self._aav_hint.setText(
            f"Allowed: {_fmt_money(min_sal)} – {_fmt_money(max_sal)}/yr · "
            f"Term: {years_min}–{years_max} yrs")
        self._sb_hint.setText(
            f"Signing bonus: {_fmt_money(t['sb'])} — sweetens the offer "
            f"for the player.")
        self._ask_lbl.setText(
            f"Agent's ask: {_fmt_money(d['ask'])}/yr")
        c = d["cap"]
        fits = c["fits"] and bool(c["live_cap"])
        fit_color = "#3fb950" if fits else "#e5484d"
        self._cap_lbl.setText(
            f"Cap space: {_fmt_money(c['current_space'])} → "
            f"<b style='color:{fit_color}'>{_fmt_money(c['space_after'])} "
            f"after</b> "
            f"<span style='color:#8b95ab'>(charge "
            f"{_fmt_money(c['projected_charge'])} / "
            f"{_fmt_money(c['live_cap'])})</span>")
        reason = d["valid_reason"] or ""
        if not d["window"]["ok"]:
            reason = d["window"]["reason"]
        elif not d["eligibility"]["ok"]:
            reason = d["eligibility"]["reason"]
        can = d["valid"] and fits
        self._submit_btn.setEnabled(bool(can))
        self._note_lbl.setStyleSheet("color: #e5484d;")
        self._note_lbl.setText(
            d["note"] if can else
            (reason or "These terms do not fit under the cap."))

    # -- submit ---------------------------------------------------------

    def _on_submit(self):
        game, p = self._game, self._player
        if p is None:
            return
        t = self._terms()
        extras, err = _offer_extras({
            "clause": self._clause_kind(),
            "clause_list_size": self._clause_size,
            "signing_bonus": t["sb"],
        })
        if err:
            self._note_lbl.setText(err)
            return
        # Re-run the gates (mirrors the web endpoint's 422 checks).
        ok, msg = _validate_fa_offer(game, p, t["aav"], t["years"])
        if not ok:
            self._note_lbl.setText(msg)
            return
        wok, wmsg = _fa_window(game)
        if not wok:
            self._note_lbl.setText(wmsg)
            return
        eok, emsg = _fa_eligibility(p)
        if not eok:
            self._note_lbl.setText(emsg)
            return
        cap = _cap_state(game, offer_salary=t["aav"], extension=False)
        if not cap["fits"]:
            self._note_lbl.setText("These terms do not fit under the cap.")
            return
        if extras["clause"] != "none":
            try:
                import trade_engine as _te
                if not _te.clause_eligible(p):
                    self._note_lbl.setText(
                        "Trade protection isn't available for this player "
                        "(27+ or 7 pro seasons required).")
                    return
            except Exception:
                pass
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Sending…")
        st = submit_offer(game, p, "sign", t["years"], t["aav"], extras)
        status = st.get("status")
        if status == "accepted":
            self._note_lbl.setStyleSheet("color: #3fb950;")
            self._note_lbl.setText("Signed ✓ — the deal is filed with the "
                                   "league office.")
            QTimer.singleShot(900, self.accept)
        elif status in ("countered", "awaiting_agent"):
            # Hand the open talks to the negotiation dialog.
            self.negotiation_requested.emit(self._pid)
            self.accept()
        else:
            self._note_lbl.setStyleSheet("color: #e5484d;")
            self._note_lbl.setText(
                "Offer refused: " + (st.get("note")
                                     or "the player rejected the offer "
                                        "outright."))
            self._submit_btn.setEnabled(True)
            self._submit_btn.setText("Sign")


class AnalysisDialog(QDialog):
    """Market analysis for one free agent: value, comparables,
    projections (3 sub-tabs)."""

    def __init__(self, game, pid, parent=None):
        super().__init__(parent)
        self._game = game
        p = _find_fa(game, pid)
        d = _fa_analysis(game, p) if p is not None else None

        self.setWindowTitle("Market analysis")
        self.setMinimumWidth(560)
        self.setMinimumHeight(380)

        layout = QVBoxLayout(self)
        title = QLabel(
            "Market analysis — " + ((d or {}).get("player_name") or "?"))
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        if not d:
            tabs.addTab(QLabel("Analysis unavailable."), "Value")
        else:
            v = d["value"]
            vcolor = {"green": "#3fb950", "red": "#e5484d"}.get(v["color"],
                                                               "#3B82F6")
            value_w = QWidget()
            vl = QVBoxLayout(value_w)
            vl.setSpacing(8)
            vl.addWidget(QLabel(
                f"Market value: {_fmt_money(v['market_value'])}"))
            vl.addWidget(QLabel(f"Asking: {_fmt_money(v['ask'])}"))
            verdict = QLabel(v["verdict"])
            verdict.setStyleSheet(
                f"color: {vcolor}; font-weight: 700; font-size: 15px;")
            vl.addWidget(verdict)
            vl.addStretch()
            tabs.addTab(value_w, "Value")

            comps_w = QWidget()
            cl = QVBoxLayout(comps_w)
            cl.setSpacing(6)
            if d["comparables"]:
                for c in d["comparables"]:
                    cl.addWidget(QLabel(
                        f"{c['name']} — {c['overall']} OVR, age {c['age']}, "
                        f"ask {_fmt_money(c['ask'])}/yr"))
            else:
                cl.addWidget(QLabel("No comparable players found."))
            cl.addStretch()
            tabs.addTab(comps_w, "Comparables")

            pr = d["projection"]
            proj_w = QWidget()
            pl = QVBoxLayout(proj_w)
            pl.setSpacing(8)
            pl.addWidget(QLabel(f"Suggested term: {pr['years']} years"))
            pl.addWidget(QLabel(
                f"Projected AAV range: {_fmt_money(pr['aav_low'])} – "
                f"{_fmt_money(pr['aav_high'])}/yr"))
            pl.addStretch()
            tabs.addTab(proj_w, "Projection")

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        layout.addLayout(btn_row)


class CompareDialog(QDialog):
    """Side-by-side comparison of up to 3 free agents."""

    def __init__(self, game, pids, parent=None):
        super().__init__(parent)
        rows = _compare_rows(game, pids)
        self.setWindowTitle("Compare free agents")
        self.setMinimumWidth(680)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        title = QLabel("Compare free agents")
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        table = QTableWidget()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        attrs = [("overall", "OVERALL"), ("age", "AGE"), ("ask", "ASK")]
        attrs += [(a, a.replace("_", " ").upper()) for a in _COMPARE_ATTRS]
        table.setColumnCount(len(rows) + 1)
        table.setRowCount(len(attrs))
        table.setHorizontalHeaderLabels(
            [""] + [r["name"] for r in rows])
        for ri, (key, label) in enumerate(attrs):
            table.setItem(ri, 0, QTableWidgetItem(label))
            for ci, r in enumerate(rows):
                v = r.get(key)
                if v is None:
                    v = (r.get("compare_attrs") or {}).get(key)
                text = "—" if v is None else (
                    _fmt_money(v) + "/yr" if key == "ask" else str(v))
                table.setItem(ri, ci + 1, QTableWidgetItem(text))
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        layout.addWidget(table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        layout.addLayout(btn_row)


class HireDialog(QDialog):
    """Hire a free-agent staffer: contract-length picker, salary entry,
    350ms-debounced acceptance-chance preview, conflict + budget guards."""

    def __init__(self, game, staff_row, on_done=None, parent=None):
        super().__init__(parent)
        self._game = game
        self._staff_row = staff_row
        self._on_done = on_done
        self._years = 3
        s = staff_row["staff"]

        self.setWindowTitle("Hire staffer")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(f"Hire {staff_row['name']}")
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        self._ask_lbl = QLabel("Loading market ask…")
        self._ask_lbl.setWordWrap(True)
        layout.addWidget(self._ask_lbl)

        self._budget_lbl = QLabel("")
        self._budget_lbl.setWordWrap(True)
        self._budget_lbl.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._budget_lbl)

        self._conflict_lbl = QLabel("")
        self._conflict_lbl.setWordWrap(True)
        self._conflict_lbl.setStyleSheet("color: #e5484d;")
        layout.addWidget(self._conflict_lbl)

        # --- years picker ---
        years_row = QHBoxLayout()
        years_row.addWidget(QLabel("Contract length (years)"))
        self._year_btns = []
        for y in (1, 2, 3, 4, 5):
            b = QPushButton(str(y))
            b.setCheckable(True)
            b.setChecked(y == 3)
            b.clicked.connect(lambda _c, v=y: self._set_years(v))
            self._year_btns.append(b)
            years_row.addWidget(b)
        years_row.addStretch()
        layout.addLayout(years_row)

        # --- NHL / AHL assignment ---
        asg_row = QHBoxLayout()
        asg_row.addWidget(QLabel("Assignment"))
        self._asg_combo = QComboBox()
        self._asg_combo.addItems(["nhl", "ahl"])
        asg_row.addWidget(self._asg_combo)
        asg_row.addStretch()
        layout.addLayout(asg_row)

        # --- salary ---
        sal_row = QHBoxLayout()
        sal_row.addWidget(QLabel("Salary offer ($ / year)"))
        self._salary_edit = QLineEdit()
        self._salary_edit.setPlaceholderText("e.g. 150000")
        self._salary_edit.setValidator(QIntValidator(0, 999_999_999, self))
        self._salary_edit.textChanged.connect(self._schedule_preview)
        sal_row.addWidget(self._salary_edit, 1)
        layout.addLayout(sal_row)

        self._chance_lbl = QLabel("")
        self._chance_lbl.setWordWrap(True)
        layout.addWidget(self._chance_lbl)

        self._result_lbl = QLabel("")
        self._result_lbl.setWordWrap(True)
        layout.addWidget(self._result_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        self._submit_btn = QPushButton("Make Offer")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._submit_btn)
        layout.addLayout(btn_row)

        # 350ms-debounced acceptance-chance preview.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._refresh_preview)

        self._refresh_preview()

    def _set_years(self, v):
        self._years = int(v)
        for b, y in zip(self._year_btns, (1, 2, 3, 4, 5)):
            b.setChecked(y == int(v))

    def _schedule_preview(self, _t=None):
        self._debounce.start()

    def _salary(self):
        return _safe(lambda: int(
            "".join(c for c in self._salary_edit.text() if c.isdigit())
            or 0), 0)

    def _refresh_preview(self):
        game = self._game
        s = self._staff_row["staff"]
        ask = _staff_market_ask(s)
        team = _user_team(game)
        budget = _safe(lambda: team.staff_budget_remaining(), None) \
            if team is not None else None
        conflict = _staff_conflict(game, s)
        role = self._staff_row.get("role", "")
        self._ask_lbl.setText(
            f"Market ask: {_fmt_money(ask)}/yr · {role}")
        self._budget_lbl.setText(
            f"Club staff budget available: {_fmt_money(budget)}/yr."
            if budget is not None else "")
        self._conflict_lbl.setText(conflict)
        self._submit_btn.setEnabled(not conflict)
        offer = self._salary()
        if offer > 0:
            chance = _staff_offer_chance(game, s, offer)
            color = "#3fb950" if chance >= 0.75 else (
                "#eab308" if chance >= 0.45 else "#e5484d")
            self._chance_lbl.setText(
                f"Estimated acceptance chance: "
                f"<b style='color:{color}'>{int(round(chance * 100))}%</b>")
        else:
            self._chance_lbl.setText(
                "Enter an offer to see his likely response.")

    def _on_submit(self):
        offer = self._salary()
        if not offer:
            self._result_lbl.setText("Enter an offer amount.")
            return
        self._submit_btn.setEnabled(False)
        self._result_lbl.setStyleSheet("")
        self._result_lbl.setText("Making offer…")
        res = _hire_staff(self._game, self._staff_row["id"], offer,
                          self._years,
                          self._asg_combo.currentText())
        if res.get("ok"):
            color = "#3fb950" if res.get("accepted") else "#eab308"
            self._result_lbl.setText(
                f"<b style='color:{color}'>{res.get('text', '')}</b>")
            if res.get("accepted"):
                def _done():
                    try:
                        self.accept()
                    finally:
                        if self._on_done:
                            self._on_done()
                QTimer.singleShot(1400, _done)
            else:
                self._submit_btn.setEnabled(True)
        else:
            self._result_lbl.setStyleSheet("color: #e5484d;")
            self._result_lbl.setText(
                f"Could not send: {res.get('error') or 'unknown error'}")
            self._submit_btn.setEnabled(True)


# ---------------------------------------------------------------------------
# main screen
# ---------------------------------------------------------------------------

_POS_PILLS = ("ALL", "C", "LW", "RW", "D", "G")
_TYPE_PILLS = ("ALL", "UFA", "RFA")
_SORTS = (("overall", "Sort: Overall ↓"),
          ("ask-asc", "Sort: Asking price ↑"),
          ("ask-desc", "Sort: Asking price ↓"),
          ("age", "Sort: Age ↑"))


class FreeAgentsScreen(BaseScreen):
    """Free-agent market with 3 tabs: Players, Staff, Market Overview.

    Players: position + UFA/RFA pills, sort, player cards with Offer /
    Analysis buttons and compare checkboxes (max 3). Staff: search +
    department filter with hire dialog. Market: size/ask/position/top
    cards. FA Frenzy banner appears when the market event is live, and
    set_offer_player(pid) opens the offer dialog (the ?offer= deep-link
    equivalent).
    """

    title = "Free Agents"

    def __init__(self, game, main_window, parent=None):
        self._fa_rows = []
        self._pos_filter = "ALL"
        self._type_filter = "ALL"
        self._sort = "overall"
        self._cmp = []  # compare selection, max 3 player ids
        self._staff_rows = []
        super().__init__(game, main_window, parent)

    # -- build ----------------------------------------------------------

    def _build_body(self):
        # FA Frenzy banner (hidden unless the event is live).
        self._banner_btn = QPushButton(
            "FREE AGENT FRENZY — the market is open. Click for details.")
        self._banner_btn.setObjectName("primary-btn")
        self._banner_btn.setVisible(False)
        self._banner_btn.clicked.connect(self._open_frenzy)
        self._layout.addWidget(self._banner_btn)

        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, 1)

        # --- Players tab ---
        ptab = QWidget()
        pl = QVBoxLayout(ptab)
        pl.setSpacing(8)
        pl.setContentsMargins(0, 0, 0, 0)

        filter_row = QHBoxLayout()
        self._pos_pills = self._make_pills(
            _POS_PILLS, self._on_pos_filter)
        filter_row.addWidget(self._pos_pills)
        self._type_pills = self._make_pills(
            _TYPE_PILLS, self._on_type_filter, labels={
                "ALL": "UFA + RFA", "UFA": "UFA", "RFA": "RFA"})
        filter_row.addWidget(self._type_pills)
        self._sort_combo = QComboBox()
        for key, label in _SORTS:
            self._sort_combo.addItem(label, key)
        self._sort_combo.currentIndexChanged.connect(self._on_sort)
        filter_row.addWidget(self._sort_combo)
        filter_row.addStretch()
        pl.addLayout(filter_row)

        cmp_row = QHBoxLayout()
        self._count_lbl = QLabel("")
        cmp_row.addWidget(self._count_lbl)
        cmp_row.addStretch()
        self._cmp_btn = QPushButton("Compare Selected (0)")
        self._cmp_btn.setEnabled(False)
        self._cmp_btn.clicked.connect(self._open_compare)
        cmp_row.addWidget(self._cmp_btn)
        pl.addLayout(cmp_row)
        self._cmp_note = QLabel("")
        self._cmp_note.setStyleSheet("color: #eab308; font-size: 12px;")
        pl.addWidget(self._cmp_note)

        self._fa_scroll = QScrollArea()
        self._fa_scroll.setWidgetResizable(True)
        self._fa_body = QWidget()
        self._fa_list = QVBoxLayout(self._fa_body)
        self._fa_list.setSpacing(8)
        self._fa_list.setContentsMargins(4, 4, 4, 4)
        self._fa_scroll.setWidget(self._fa_body)
        pl.addWidget(self._fa_scroll, 1)
        self._tabs.addTab(ptab, "Players")

        # --- Staff tab ---
        stab = QWidget()
        sl = QVBoxLayout(stab)
        sl.setSpacing(8)
        sl.setContentsMargins(0, 0, 0, 0)
        sfilter = QHBoxLayout()
        self._staff_search = QLineEdit()
        self._staff_search.setPlaceholderText("Search staff by name…")
        self._staff_search.textChanged.connect(self._on_staff_filter)
        sfilter.addWidget(self._staff_search, 1)
        self._staff_dept = QComboBox()
        self._staff_dept.addItem("All departments", "All")
        for dpt in _STAFF_DEPTS:
            self._staff_dept.addItem(dpt, dpt)
        self._staff_dept.currentIndexChanged.connect(self._on_staff_filter)
        sfilter.addWidget(self._staff_dept)
        sl.addLayout(sfilter)
        self._staff_scroll = QScrollArea()
        self._staff_scroll.setWidgetResizable(True)
        self._staff_body = QWidget()
        self._staff_list = QVBoxLayout(self._staff_body)
        self._staff_list.setSpacing(8)
        self._staff_list.setContentsMargins(4, 4, 4, 4)
        self._staff_scroll.setWidget(self._staff_body)
        sl.addWidget(self._staff_scroll, 1)
        self._tabs.addTab(stab, "Staff")

        # --- Market tab ---
        mtab = QWidget()
        ml = QVBoxLayout(mtab)
        ml.setSpacing(10)
        ml.setContentsMargins(0, 0, 0, 0)
        mrow1 = QHBoxLayout()
        self._mk_size = self._market_card("Market Size")
        self._mk_ask = self._market_card("Avg Asking")
        mrow1.addWidget(self._mk_size, 1)
        mrow1.addWidget(self._mk_ask, 1)
        ml.addLayout(mrow1)
        mrow2 = QHBoxLayout()
        self._mk_pos = self._market_card("By Position")
        self._mk_top = self._market_card("Top Available")
        mrow2.addWidget(self._mk_pos, 1)
        mrow2.addWidget(self._mk_top, 1)
        ml.addLayout(mrow2)
        ml.addStretch()
        self._tabs.addTab(mtab, "Market Overview")

        self.refresh()

    def _make_pills(self, keys, on_change, labels=None):
        from PySide6.QtWidgets import QButtonGroup
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        group = QButtonGroup(box)
        group.setExclusive(True)
        for key in keys:
            b = QPushButton((labels or {}).get(key, key))
            b.setCheckable(True)
            b.setChecked(key == "ALL")
            b.setProperty("pill_key", key)
            b.setStyleSheet(
                "QPushButton { padding: 4px 12px; border-radius: 12px; "
                "border: 1px solid #2a3350; background: #141b2e; "
                "color: #9aa4b8; }"
                "QPushButton:checked { background: #3B82F6; color: white; "
                "border: 1px solid #3B82F6; font-weight: 700; }")
            b.toggled.connect(
                lambda checked, k=key: on_change(k) if checked else None)
            group.addButton(b)
            row.addWidget(b)
        return box

    def _market_card(self, heading):
        card = QGroupBox(heading)
        lay = QVBoxLayout(card)
        lay.setSpacing(4)
        return card

    def _card_body(self, card):
        while card.layout().count():
            child = card.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # -- players tab ----------------------------------------------------

    def _on_pos_filter(self, key):
        self._pos_filter = key
        self._render_players()

    def _on_type_filter(self, key):
        self._type_filter = key
        self._render_players()

    def _on_sort(self, _i):
        self._sort = self._sort_combo.currentData()
        self._render_players()

    def _matches_pos(self, short):
        if self._pos_filter == "ALL":
            return True
        if self._pos_filter == "D":
            return short in ("D", "LD", "RD", "DEF")
        return short == self._pos_filter

    def _filtered_rows(self):
        rows = [r for r in self._fa_rows
                if self._matches_pos(r["pos_short"])
                and (self._type_filter == "ALL"
                     or r["fa_type"] == self._type_filter)]
        if self._sort == "ask-asc":
            rows.sort(key=lambda r: r["ask"])
        elif self._sort == "ask-desc":
            rows.sort(key=lambda r: r["ask"], reverse=True)
        elif self._sort == "age":
            rows.sort(key=lambda r: r["age"])
        else:
            rows.sort(key=lambda r: r["overall"], reverse=True)
        return rows

    def _ovr_badge(self, ovr):
        color = "#3fb950" if ovr >= 80 else ("#eab308" if ovr >= 60
                                            else "#e5484d")
        lab = QLabel(str(ovr))
        lab.setMinimumWidth(52)
        lab.setAlignment(Qt.AlignCenter)
        f = lab.font()
        f.setPointSize(20)
        f.setBold(True)
        lab.setFont(f)
        lab.setStyleSheet(f"color: {color};")
        return lab

    def _render_players(self):
        while self._fa_list.count():
            child = self._fa_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        rows = self._filtered_rows()
        n = len(rows)
        self._count_lbl.setText(
            f"{n} player{'s' if n != 1 else ''} available")
        if not rows:
            empty = QLabel("No free agents match the current filters.")
            empty.setStyleSheet("color: #8b95ab;")
            self._fa_list.addWidget(empty)
        for r in rows:
            self._fa_list.addWidget(self._player_card(r))
        self._fa_list.addStretch()
        self._paint_cmp()

    def _player_card(self, r):
        card = QWidget()
        card.setObjectName("tile")
        row = QHBoxLayout(card)
        row.setSpacing(10)
        row.addWidget(self._ovr_badge(r["overall"]))
        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(f"{r['name']}  [{r['fa_type']}]")
        name.setStyleSheet("font-weight: 700; font-size: 14px;")
        info.addWidget(name)
        sub = QLabel(f"{r['position']} · Age {r['age']} · Asking "
                     f"{_fmt_money(r['ask'])}/yr")
        sub.setStyleSheet("color: #8b95ab; font-size: 12px;")
        info.addWidget(sub)
        row.addLayout(info, 1)
        offer = QPushButton("Offer")
        offer.setObjectName("primary-btn")
        offer.clicked.connect(lambda _c, pid=r["id"]: self.open_offer(pid))
        row.addWidget(offer)
        analysis = QPushButton("Analysis")
        analysis.clicked.connect(
            lambda _c, pid=r["id"]: self._open_analysis(pid))
        row.addWidget(analysis)
        cmp = QCheckBox("Compare")
        cmp.setChecked(r["id"] in self._cmp)
        cmp.stateChanged.connect(
            lambda _s, pid=r["id"], cb=cmp: self._toggle_compare(pid, cb))
        row.addWidget(cmp)
        return card

    # -- compare selection (max 3 enforced, auto-uncheck extras) --------

    def _toggle_compare(self, pid, checkbox):
        if checkbox.isChecked():
            if len(self._cmp) >= 3:
                checkbox.setChecked(False)
                self._cmp_note.setText(
                    "Compare is limited to 3 players — uncheck one first.")
                QTimer.singleShot(2500, lambda: self._cmp_note.setText(""))
                return
            self._cmp.append(pid)
        else:
            if pid in self._cmp:
                self._cmp.remove(pid)
        self._paint_cmp()

    def _paint_cmp(self):
        n = len(self._cmp)
        self._cmp_btn.setText(f"Compare Selected ({n})")
        self._cmp_btn.setEnabled(n > 0)

    def _open_compare(self):
        if not self._cmp:
            return
        dlg = CompareDialog(self.game, list(self._cmp), self)
        dlg.exec()

    # -- staff tab ------------------------------------------------------

    def _on_staff_filter(self, _v=None):
        self._render_staff()

    def _render_staff(self):
        while self._staff_list.count():
            child = self._staff_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        q = self._staff_search.text().strip().lower()
        dept = self._staff_dept.currentData()
        rows = []
        for s in self._staff_rows:
            if dept != "All" and s["department"] != dept:
                continue
            if q and q not in s["name"].lower():
                continue
            rows.append(s)
        if not rows:
            empty = QLabel("No free-agent staff found.")
            empty.setStyleSheet("color: #8b95ab;")
            self._staff_list.addWidget(empty)
        for s in rows:
            card = QWidget()
            card.setObjectName("tile")
            row = QHBoxLayout(card)
            row.setSpacing(10)
            row.addWidget(self._ovr_badge(s["overall"]))
            info = QVBoxLayout()
            info.setSpacing(2)
            name = QLabel(s["name"])
            name.setStyleSheet("font-weight: 700; font-size: 14px;")
            info.addWidget(name)
            sub = QLabel(f"{s['role']} · {s['department']} · "
                         f"{s['experience']} yrs exp · Age {s['age']}")
            sub.setStyleSheet("color: #8b95ab; font-size: 12px;")
            info.addWidget(sub)
            row.addLayout(info, 1)
            hire = QPushButton("Hire")
            hire.setObjectName("primary-btn")
            hire.clicked.connect(
                lambda _c, sr=s: self._open_hire(sr))
            row.addWidget(hire)
            self._staff_list.addWidget(card)
        self._staff_list.addStretch()

    def _open_hire(self, staff_row):
        dlg = HireDialog(self.game, staff_row,
                         on_done=self.refresh, parent=self)
        dlg.exec()

    # -- market tab -----------------------------------------------------

    def _render_market(self):
        d = _market_data(self.game)
        for card, key in ((self._mk_size, "size"), (self._mk_ask, "ask"),
                          (self._mk_pos, "pos"), (self._mk_top, "top")):
            self._card_body(card)
            lay = card.layout()
            if key == "size":
                big = QLabel(str(d["total"]))
                f = big.font()
                f.setPointSize(28)
                f.setBold(True)
                big.setFont(f)
                lay.addWidget(big)
                lay.addWidget(QLabel(
                    f"{d['by_type'].get('UFA', 0)} UFA · "
                    f"{d['by_type'].get('RFA', 0)} RFA"))
            elif key == "ask":
                big = QLabel(_fmt_money(d["avg_ask"]) + "/yr")
                f = big.font()
                f.setPointSize(28)
                f.setBold(True)
                big.setFont(f)
                lay.addWidget(big)
                lay.addWidget(QLabel("average asking price"))
            elif key == "pos":
                for pos, count in sorted(d["by_position"].items(),
                                         key=lambda kv: kv[1],
                                         reverse=True):
                    r = QHBoxLayout()
                    r.addWidget(QLabel(pos), 1)
                    r.addWidget(QLabel(str(count)))
                    w = QWidget()
                    w.setLayout(r)
                    lay.addWidget(w)
                if not d["by_position"]:
                    lay.addWidget(QLabel("—"))
            else:
                for p in d["top_available"]:
                    lab = QLabel(
                        f"{p['name']}  ({p['position']} · {p['overall']} OVR) "
                        f"— {_fmt_money(p['ask'])}/yr")
                    lab.setWordWrap(True)
                    lay.addWidget(lab)
                if not d["top_available"]:
                    lay.addWidget(QLabel("—"))

    # -- actions --------------------------------------------------------

    def open_offer(self, pid):
        """Open the offer dialog for a free agent."""
        p = _find_fa(self.game, pid)
        if p is None:
            QMessageBox.warning(self, "Free agents",
                                "That player is no longer a free agent.")
            self.refresh()
            return
        dlg = OfferDialog(self.game, _pid(p), self)
        dlg.negotiation_requested.connect(self._open_negotiation)
        dlg.finished.connect(lambda _r: self.refresh())
        dlg.exec()

    def set_offer_player(self, player_id):
        """Deep-link equivalent of the web ?offer=<id>: open the offer
        dialog for a free agent (used by the FA Frenzy hub)."""
        self._tabs.setCurrentIndex(0)
        self.open_offer(player_id)

    def _open_analysis(self, pid):
        dlg = AnalysisDialog(self.game, pid, self)
        dlg.exec()

    def _open_negotiation(self, pid):
        dlg = NegotiationDialog(self.game, pid, self)
        dlg.finished.connect(lambda _r: self.refresh())
        dlg.exec()

    def _open_frenzy(self):
        # Single path: the registered FA Frenzy screen (fa_frenzy).
        # The old banner dialog was removed; its Offer deep-link is
        # ported into FaFrenzyScreen._on_offer.
        self.navigate_to("fa_frenzy")

    # -- refresh --------------------------------------------------------

    def refresh(self):
        """Reload pools from the game object. Called on navigation."""
        try:
            self._fa_rows = [_fa_row(self.game, p)
                             for p in _fa_pool(self.game)]
        except Exception:
            self._fa_rows = []
        try:
            self._staff_rows = sorted(
                (_staff_row(s) for s in _staff_pool(self.game)),
                key=lambda s: s["overall"], reverse=True)
        except Exception:
            self._staff_rows = []
        try:
            self._banner_btn.setVisible(_frenzy_active(self.game))
        except Exception:
            self._banner_btn.setVisible(False)
        self._render_players()
        self._render_staff()
        self._render_market()
