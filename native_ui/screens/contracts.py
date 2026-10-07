"""Contracts screen: roster contracts sorted by cap hit, with extensions,
multi-day negotiation, trade-protection clauses, comparables, and the
ELC (entry-level contract) flow.

Native port of the web UI contracts screen (web_ui/templates/contracts.html
+ web_ui/screens/contracts.py + web_ui/static/js/contracts.js). Calls the
game object DIRECTLY -- no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same as the web bridge called):
  - game._validate_contract_terms(player, salary, years, extension=...)
  - game.handle_contract_offer(player, extension=..., notify="inbox")
  - game.accept_contract_counter(inbox_message)
  - game.handle_elc_offer(player, salary, signing_bonus, performance_bonus)
  - game.send_email_to_user(EmailMessage)   (auto-negotiate digest)
  - game.get_live_cap()
  - salary_cap_system: max_contract_term, league_minimum_salary,
    total_cap_charge, elc_band, elc_prospect_ask, elc_max_annual_comp,
    ELC_SIGNING_BONUS_PCT, ELC_PERF_BONUS_MAX
  - transaction_windows.check_window("extension", date, ctx={"player": p})
  - trade_engine: clause_eligible, clause_demand_score, clause_offer_label,
    clause_annual_value, apply_clause_to_contract (via handle_contract_offer)
"""

from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QDoubleSpinBox, QComboBox, QLineEdit, QGroupBox, QTextEdit, QTabWidget,
    QMessageBox, QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator, QFont

from .base import BaseScreen
from ..widgets.player_table import PlayerTable


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


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


def _pid(p):
    return str(_safe(lambda: getattr(p, "id", id(p)), ""))


_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}


def _clean_position(pos):
    try:
        s = str(pos or "")
        if "." in s:
            s = s.split(".")[-1]
        s = s.strip().upper()
        return _POSITION_ABBR.get(s, s or "?")
    except Exception:
        return "?"


def _pos_str(p):
    pos = _safe(lambda: getattr(p, "primary_position", ""), "")
    return _clean_position(getattr(pos, "value", pos))


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


def _player_name(p):
    return _safe(lambda: getattr(p, "full_name", "?"), "?")


def _parse_money(text):
    try:
        digits = "".join(c for c in str(text or "") if c.isdigit())
        return int(digits) if digits else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# game-data helpers (ported from web_ui/screens/contracts.py)
# ---------------------------------------------------------------------------

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


def _contract_years(p):
    c = _safe(lambda: getattr(p, "contract", None))
    if c is not None:
        y = _safe(lambda: getattr(c, "years_remaining", None))
        if y is None:
            y = _safe(lambda: getattr(c, "term", None))
        return _safe(lambda: int(y), 0) or 0
    return _safe(lambda: int(getattr(p, "contract_years", 0) or 0), 0) or 0


def _contract_salary(p):
    c = _safe(lambda: getattr(p, "contract", None))
    if c is not None:
        s = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0)
        if s:
            return s
    return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0) or 0


def _contract_row(p):
    """Row data for the contracts table. Never raises."""
    years = _contract_years(p)
    salary = _contract_salary(p)
    c = _safe(lambda: getattr(p, "contract", None))
    clauses = []
    if _safe(lambda: bool(getattr(c, "no_movement_clause", False)), False):
        clauses.append("NMC")
    if _safe(lambda: bool(getattr(c, "no_trade_clause", False)), False):
        clauses.append("NTC")
    if _safe(lambda: bool(getattr(c, "two_way", False)), False):
        clauses.append("2-way")
    return {
        "player": p,
        "id": _pid(p),
        "name": _player_name(p),
        "position": _pos_str(p),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
        "overall": _player_ovr(p),
        "salary": salary,
        "cap_hit": salary,
        "years_remaining": years,
        "expiring": bool(years <= 1),
        "clauses": clauses,
    }


def _live_cap(game):
    try:
        c = int(game.get_live_cap())
        if c > 0:
            return c
    except Exception:
        pass
    return 104_000_000


def _term_bounds():
    """(min_years, max_years): new CBA = 7 to re-sign, 6 external."""
    try:
        from salary_cap_system import max_contract_term
        return 1, int(max_contract_term(True))
    except Exception:
        return 1, 7


def _salary_bounds(game):
    """(min_salary, max_salary): season-aware league minimum,
    20%-of-live-cap maximum."""
    cap = _live_cap(game)
    try:
        from salary_cap_system import league_minimum_salary
        sy = _safe(lambda: getattr(_user_league(game), "season_year", None))
        min_sal = int(league_minimum_salary(sy))
    except Exception:
        min_sal = 775_000
    return min_sal, int(0.20 * cap)


def _cap_state(game, offer_salary=0, extension=False, current_hit=0):
    """Current + projected cap via salary_cap_system.total_cap_charge.
    Extensions replace the player's existing hit instead of stacking.
    Never raises."""
    out = {"live_cap": 0, "current_charge": 0, "current_space": 0,
           "projected_charge": 0, "space_after": 0, "fits": False}
    try:
        from salary_cap_system import total_cap_charge
        cap = _live_cap(game)
        team = _user_team(game)
        charge = int(_safe(lambda: total_cap_charge(team), 0))
        proj = charge + int(offer_salary or 0)
        if extension:
            proj -= int(current_hit or 0)
        out.update(live_cap=cap, current_charge=charge,
                   current_space=cap - charge, projected_charge=proj,
                   space_after=cap - proj, fits=(cap - proj) >= 0)
    except Exception:
        pass
    return out


def _validate_extension(game, p, salary, years):
    """Validation through the game's shared gate
    (HockeyManagerGUI._validate_contract_terms with extension=True).
    Returns (ok, message). Never raises."""
    try:
        ok, msg = game._validate_contract_terms(p, int(salary), int(years),
                                                extension=True)
        return bool(ok), (msg or "")
    except Exception:
        return False, "Could not validate contract terms."


def _extension_window(game, p):
    """Extensions only in the final year of a deal
    (transaction_windows.check_window). Returns (ok, reason)."""
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(game, "current_date", None))
        ok, why = _tw.check_window("extension", d, ctx={"player": p})
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _extension_estimate(p, live_cap):
    """AAV the player would likely accept, replicating the game's own
    market-value curve (ContractExtensionsView.calculate_market_value):
    cap-relative base (ovr x $100k), age / position / potential
    modifiers, performance bonus. The desktop flow accepts 90-120% of
    the player's value (person.negotiate_contract); return the band too.
    Never raises."""
    try:
        from salary_cap_system import DEFAULT_CAP
    except Exception:
        DEFAULT_CAP = 104_000_000
    ovr = _safe(lambda: float(p.overall_rating()), 75.0) or 75.0
    age = _safe(lambda: int(getattr(p, "age", 27) or 27), 27)
    base = ovr * 100_000 * (live_cap / DEFAULT_CAP)
    age_mod = 1.2 if 23 <= age <= 29 else (
        max(0.5, 1.0 - ((age - 30) * 0.05)) if age >= 30 else 1.0)
    pos = getattr(p, "primary_position", "")
    pos_name = getattr(pos, "value", str(pos))
    pos_mod = 1.15 if pos_name == "C" else (
        1.1 if pos_name in ("LD", "RD") else 1.0)
    pot_mod = 1.0
    if age <= 25:
        pot_mod = {"A": 1.5, "B": 1.3, "C": 1.1, "D": 1.0, "F": 0.9}.get(
            _safe(lambda: getattr(p, "potential_grade", "C"), "C"), 1.0)
    perf = 0
    try:
        perf = int(p.stats.goals) * 50_000 + int(p.stats.assists) * 30_000
    except Exception:
        pass
    estimate = max(750_000, int(base * age_mod * pos_mod * pot_mod) + perf)
    try:
        value = getattr(p, "value", p.overall_rating() * 100_000)
        value = float(value or 0) or float(ovr * 100_000)
    except Exception:
        value = float(ovr * 100_000)
    return {
        "aav_estimate": estimate,
        "accept_low": int(value * 0.9),
        "accept_high": int(value * 1.2),
    }


def _offer_extras(payload):
    """Parse optional clause + signing-bonus fields from an offer
    payload dict. Returns (extras dict, error). Never raises."""
    extras = {}
    clause = str(payload.get("clause") or "none").strip().lower()
    if clause not in ("none", "nmc", "ntc", "mntc"):
        return None, f"unknown clause kind: {clause!r}"
    try:
        list_size = int(payload.get("clause_list_size") or 10)
    except (TypeError, ValueError):
        list_size = 10
    list_size = max(1, min(31, list_size))
    try:
        sb = int(payload.get("signing_bonus") or 0)
    except (TypeError, ValueError):
        return None, "signing_bonus must be a number"
    if sb < 0:
        return None, "signing_bonus cannot be negative"
    extras["clause"] = clause
    extras["clause_list_size"] = list_size
    extras["signing_bonus"] = sb
    return extras, ""


def _clause_info(game, p):
    """Clause picker data for one player. Desktop parity
    (windows.py:_refresh_clause_hint, trade_engine). Never raises."""
    out = {"eligible": False, "eligibility_note": "", "demand": 0.0,
           "options": []}
    try:
        import trade_engine as te
    except Exception:
        out["eligibility_note"] = "Trade engine unavailable."
        return out
    team = _user_team(game)
    league = _user_league(game)
    eligible = bool(_safe(lambda: te.clause_eligible(p), False))
    out["eligible"] = eligible
    if not eligible:
        out["eligibility_note"] = ("Trade protection isn't available here "
                                   "-- the NHL only allows it for players "
                                   "27+ or with 7 pro seasons.")
    demand = float(_safe(lambda: te.clause_demand_score(p, team, league),
                         0.0) or 0.0)
    out["demand"] = round(demand, 2)
    for kind in ("none", "nmc", "ntc", "mntc"):
        label = _safe(lambda k=kind: te.clause_offer_label(k, 10), kind)
        val = int(_safe(lambda k=kind: te.clause_annual_value(p, k), 0) or 0)
        out["options"].append({
            "kind": kind, "label": str(label or kind),
            "annual_value": val,
            "default_list_size": 10,
        })
    if demand >= 0.65:
        out["hint"] = ("His camp is pushing hard for trade protection -- "
                       "expect to pay more without it.")
    elif demand >= 0.35:
        out["hint"] = "Trade protection would sweeten your offer."
    else:
        out["hint"] = ""
    return out


def _comparables(game, p):
    """Comparable contracts: same position, +-4 OVR, league-wide rosters
    (windows.py _comparables). Never raises."""
    try:
        my_ovr = float(p.overall_rating())
    except Exception:
        my_ovr = 75.0
    my_pos = _safe(lambda: getattr(getattr(p, "primary_position", ""),
                                   "value", ""), "")
    try:
        from attribute_composites import talent_tier as _tt
    except Exception:
        _tt = None
    league = _user_league(game)
    teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
    comps = []
    for t in teams:
        for q in _safe(lambda: list(getattr(t, "roster", None) or []),
                       []) or []:
            try:
                if q is p:
                    continue
                ovr = float(q.overall_rating())
                if abs(ovr - my_ovr) > 4:
                    continue
                qpos = _safe(lambda: getattr(
                    getattr(q, "primary_position", ""), "value", ""), "")
                if qpos != my_pos:
                    continue
                qc = _safe(lambda: getattr(q, "contract", None))
                sal = int(_safe(lambda: getattr(qc, "salary", 0)
                                or getattr(q, "salary", 0) or 0, 0) or 0)
                yrs = int(_safe(lambda: getattr(qc, "years_remaining", 0)
                                or getattr(q, "contract_years", 0) or 0,
                                0) or 0)
                comps.append({
                    "name": _player_name(q),
                    "team": _safe(lambda: getattr(t, "team_name", ""), ""),
                    "position": qpos,
                    "overall": round(ovr, 1),
                    "tier": _safe(lambda: _tt(ovr), "") if _tt else "",
                    "salary": sal,
                    "years_remaining": yrs,
                    "ovr_gap": round(abs(ovr - my_ovr), 1),
                })
            except Exception:
                continue
    comps.sort(key=lambda c: (c["ovr_gap"], -c["salary"]))
    return comps[:5]


def _find_any_player(game, pid):
    """Roster + free-agent pool + unsigned prospects by id. Never raises."""
    pid_s = str(pid)
    pools = []
    try:
        team = _user_team(game)
        league = _user_league(game)
        pools.append(list(getattr(team, "roster", None) or []))
        pools.append(list(getattr(league, "free_agents", None) or []))
        pools.append(list(getattr(team, "prospects", None) or []))
    except Exception:
        pass
    for pool in pools:
        for p in pool:
            try:
                if _pid(p) == pid_s:
                    return p
            except Exception:
                continue
    return None


def _elc_eligible_prospect(game, pid):
    """Unsigned rights-held prospect of the user's team (the exact guard
    handle_elc_offer enforces). Never raises."""
    pid_s = str(pid)
    team = _user_team(game)
    if team is None:
        return None
    tname = _safe(lambda: getattr(team, "team_name", ""), "")
    pool = _safe(lambda: list(getattr(team, "prospects", None) or []),
                 []) or []
    for p in pool:
        try:
            if _pid(p) != pid_s:
                continue
            if getattr(p, "contract", None) is not None:
                return None
            if (getattr(p, "rights_team", "") or "") != tname:
                return None
            return p
        except Exception:
            continue
    return None


def _elc_band_info(game, p):
    """ELC band via salary_cap_system.elc_band. Returns dict with
    floor/ceiling/years/bonus caps, or error. Never raises."""
    try:
        import salary_cap_system as _scs
        league = _user_league(game)
        season = _safe(lambda: getattr(league, "season_year", None))
        age = int(_safe(lambda: getattr(p, "age", 20), 20) or 20)
        floor, ceil, years = _scs.elc_band(age, season)
        max_sb_pct = float(_safe(lambda: _scs.ELC_SIGNING_BONUS_PCT, 0.10)
                           or 0.10)
        max_pb = int(_safe(lambda: _scs.ELC_PERF_BONUS_MAX, 1_000_000)
                     or 1_000_000)
        max_comp = int(_safe(
            lambda: _scs.elc_max_annual_comp(season), ceil) or ceil)
        ask = _safe(lambda: _scs.elc_prospect_ask(p, season), {}) or {}
        return {
            "ok": years > 0,
            "floor": int(floor), "ceiling": int(ceil), "years": int(years),
            "signing_bonus_max_pct": max_sb_pct,
            "perf_bonus_max": max_pb,
            "max_annual_comp": max_comp,
            "agent_ask": {
                "salary": int(ask.get("salary", 0) or 0),
                "years": int(ask.get("years", years) or years),
                "signing_bonus": int(ask.get("signing_bonus", 0) or 0),
                "performance_bonus": int(ask.get("performance_bonus", 0)
                                         or 0),
                "flavor": str(ask.get("flavor", "") or ""),
            } if isinstance(ask, dict) else {},
            "error": "" if years > 0 else
                ("Not ELC-eligible at 25+: sign him to a standard contract "
                 "instead."),
        }
    except Exception as e:
        return {"ok": False, "error": f"ELC band unavailable: {e}"}

# ---------------------------------------------------------------------------
# negotiation state (ported from web_ui/screens/contracts.py)
#
# The web kept per-player negotiation state on app._web_negotiations and
# mirrored the agent's contract_counter inbox messages into it so the
# in-page modal could show the offer thread. The native port does the same
# directly on the game object. All state mutations run on the Qt thread;
# every call is _safe-wrapped and uses real game methods only.
# ---------------------------------------------------------------------------

_NEG_STATUSES = ("awaiting_agent", "countered", "accepted", "refused",
                 "walked")


def _negotiations(game):
    """Per-player negotiation map on the game object. Never raises."""
    try:
        negs = getattr(game, "_web_negotiations", None)
        if not isinstance(negs, dict):
            negs = {}
            game._web_negotiations = negs
        return negs
    except Exception:
        return {}


def _pending_counter_message(game, pid):
    """Latest unanswered contract_counter inbox message for a player
    (messages append chronologically, so last match wins). Never raises."""
    try:
        team = _user_team(game)
        inbox = getattr(team, "inbox", None)
        msgs = list(getattr(inbox, "messages", None) or [])
        pid_s = str(pid)
        best = None
        for m in msgs:
            try:
                if getattr(m, "action_type", "") != "contract_counter":
                    continue
                if getattr(m, "action_done", False):
                    continue
                data = getattr(m, "action_data", None) or {}
                if str(data.get("player_id", "")) != pid_s:
                    continue
                best = m
            except Exception:
                continue
        return best
    except Exception:
        return None


def _apply_offer_verdict(game, st, result):
    """Map handle_contract_offer's return onto the negotiation state:
    True -> accepted; "consideration" -> awaiting_agent (the UFA bid
    period); False -> countered when a fresh contract_counter inbox
    message exists, refused otherwise."""
    if result is True:
        st["status"] = "accepted"
        return
    if result == "consideration":
        st["status"] = "awaiting_agent"
        st["note"] = ("Qualifying offer: the player fields bids from every "
                      "club for 3-7 days before deciding.")
        return
    counter = _pending_counter_message(game, st.get("player_id"))
    if counter is not None:
        data = getattr(counter, "action_data", None) or {}
        st["agent_ask"] = _safe(lambda: int(data.get("asking_price", 0)
                                            or 0), 0)
        st["counter_terms"] = {
            "years": _safe(lambda: int(data.get("years", 1) or 1), 1),
            "aav": _safe(lambda: int(data.get("asking_price", 0) or 0), 0),
        }
        st["status"] = "countered"
    else:
        st["status"] = "refused"


def _find_neg_person(game, pid, kind):
    """Player by id: roster for extensions, free-agent pool for signings.
    Never raises."""
    try:
        if kind == "extend":
            team = _user_team(game)
            pool = list(getattr(team, "roster", None) or [])
        else:
            league = _user_league(game)
            pool = list(getattr(league, "free_agents", None) or [])
        for p in pool:
            if _pid(p) == str(pid):
                return p
    except Exception:
        pass
    return None


def _neg_kind_for(game, pid):
    """sign vs extend for a player: existing negotiation state wins,
    else derive from where the player lives. Never raises."""
    try:
        st = _negotiations(game).get(str(pid))
        if st and st.get("kind") in ("sign", "extend"):
            return st["kind"]
    except Exception:
        pass
    try:
        team = _user_team(game)
        roster = list(getattr(team, "roster", None) or [])
        for p in roster:
            if _pid(p) == str(pid):
                return "extend"
    except Exception:
        pass
    return "sign"


def submit_offer(game, player, kind, years, aav, extras=None):
    """Native equivalent of the web's handle_offer_command: stage the
    offer on the player (desktop submit_offer parity), run the real
    game.handle_contract_offer(notify="inbox"), and mirror the verdict
    into the negotiation map. Returns the state dict. Never raises."""
    pid_s = _pid(player)
    negs = _negotiations(game)
    st = negs.get(pid_s) or {}
    name = _player_name(player)
    st.update(
        player_id=pid_s,
        player_name=st.get("player_name") or name,
        kind=kind,
        your_offers=list(st.get("your_offers") or []) + [
            {"years": int(years), "aav": int(aav)}],
        agent_ask=st.get("agent_ask"),
        counter_terms=st.get("counter_terms"),
        status="awaiting_agent",
        note="",
    )
    negs[pid_s] = st
    # Same staging as the desktop extension flow (web bridge parity).
    try:
        player.salary = int(aav)
        player.contract_years = int(years)
    except Exception:
        pass
    if extras:
        try:
            player.offered_clause_kind = extras.get("clause", "none")
            player.offered_clause_list_size = int(
                extras.get("clause_list_size", 10) or 10)
            player.offered_signing_bonus = int(
                extras.get("signing_bonus", 0) or 0)
        except Exception:
            pass
    try:
        result = game.handle_contract_offer(
            player, extension=(kind == "extend"), notify="inbox")
    except Exception:
        return st
    _safe(lambda: _apply_offer_verdict(game, st, result))
    return st


def negotiate_counter(game, pid, years, aav, extras=None):
    """New offer into an open negotiation: desktop 'New Offer' semantics
    (inbox_window._on_contract_counter_new_offer): the pending counter is
    answered by the fresh offer, which runs the same real offer path and
    re-stashes the new verdict. Returns (ok, message). Never raises."""
    pid_s = str(pid)
    try:
        years = int(years)
    except (TypeError, ValueError):
        years = 0
    try:
        aav = int(aav)
    except (TypeError, ValueError):
        aav = 0
    if years < 1 or aav <= 0:
        return False, "Enter a valid counter-offer (term and AAV)."
    kind = _neg_kind_for(game, pid_s)
    extension = (kind == "extend")
    player = _find_neg_person(game, pid_s, kind)
    if player is None:
        return False, "Player not found."
    st = _negotiations(game).get(pid_s)
    if st is None or st.get("status") != "countered":
        return False, "No open negotiation for this player."
    # Re-validate through the game's own gate (the desktop counter path
    # gates accept too: main.py:22456).
    ok, reason = _safe(
        lambda: game._validate_contract_terms(player, aav, years,
                                              extension=extension),
        (False, "Could not validate contract terms."))
    if not ok:
        st["note"] = str(reason or "")
        st["status"] = "countered"  # talks stay open
        return False, str(reason or "Invalid counter-offer.")
    if extension:
        wok, wmsg = _extension_window(game, player)
        if not wok:
            st["note"] = wmsg
            return False, wmsg
    old = _pending_counter_message(game, pid_s)
    if old is not None:
        _safe(lambda: setattr(old, "action_done", True))
    submit_offer(game, player, kind, years, aav, extras)
    return True, ""


def negotiate_accept(game, pid):
    """Accept the agent's counter as-is: the real
    HockeyManagerGUI.accept_contract_counter. Extensions sign instantly;
    UFA counters open a consideration bid window.
    Returns (ok, message). Never raises."""
    pid_s = str(pid)
    st = _negotiations(game).get(pid_s)
    if st is None or st.get("status") != "countered":
        return False, "No open negotiation for this player."
    counter = _pending_counter_message(game, pid_s)
    if counter is None:
        return False, "The agent's counter is no longer on the table."
    try:
        ok = game.accept_contract_counter(counter)
    except Exception:
        return False, "Could not accept the counter."
    kind = st.get("kind") or _neg_kind_for(game, pid_s)
    if ok:
        if kind == "extend":
            st["status"] = "accepted"
            st["note"] = ""
        else:
            st["status"] = "awaiting_agent"
            st["note"] = ("Counter accepted -- your bid is in; the agent "
                          "decides after the consideration period.")
    else:
        # League-office veto path (desktop _inbox_contract_result
        # "rejected" with reject_note).
        st["status"] = "refused"
        st["note"] = ("The league office rejected the counter terms -- "
                      "his camp must come back with a compliant number.")
    return True, ""


def negotiate_walk(game, pid):
    """Walk away: the desktop equivalent
    (inbox_window._on_contract_counter_walkaway) only marks the message
    done -- nothing happens to the game. We do the same and close the
    negotiation state. Never raises."""
    pid_s = str(pid)
    try:
        counter = _pending_counter_message(game, pid_s)
        if counter is not None:
            _safe(lambda: setattr(counter, "action_done", True))
        st = _negotiations(game).get(pid_s)
        if st is not None:
            st["status"] = "walked"
    except Exception:
        pass
    return True

# ---------------------------------------------------------------------------
# extension / ELC dialog (native port of the web extension modal)
# ---------------------------------------------------------------------------

class ExtensionDialog(QDialog):
    """Contract extension dialog with live term preview, clause picker,
    comparables and cap-fit gating. With elc=True it becomes the
    entry-level contract flow: term locked by signing age, bonus inputs,
    and the ELC validation chain.

    Emits open_negotiation(pid) when an offer draws an agent counter so
    the parent can hand off to NegotiationDialog.
    """

    open_negotiation = Signal(str)

    def __init__(self, game, player, elc=False, parent=None):
        super().__init__(parent)
        self._game = game
        self._player = player
        self._pid = _pid(player)
        self._elc = bool(elc)
        self._primed = False
        self._clause_opts = None
        self._clause_size = 10
        self._elc_band = None
        self._elc_ok = True

        self.setWindowTitle(
            "Entry-level contract" if self._elc else "Contract extension")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._title_lbl = QLabel(
            "Entry-level contract" if self._elc else "Contract extension")
        self._title_lbl.setObjectName("dialog-title")
        layout.addWidget(self._title_lbl)

        self._player_lbl = QLabel("")
        layout.addWidget(self._player_lbl)

        self._ask_lbl = QLabel("Loading terms…")
        self._ask_lbl.setWordWrap(True)
        layout.addWidget(self._ask_lbl)

        # --- term (years slider) ---
        years_row = QHBoxLayout()
        years_row.addWidget(QLabel("Term"))
        self._years_slider = QSlider(Qt.Horizontal)
        self._years_slider.setRange(1, 7)
        self._years_slider.setValue(4)
        self._years_slider.setTickPosition(QSlider.TicksBelow)
        self._years_slider.setTickInterval(1)
        self._years_slider.valueChanged.connect(self._on_years_changed)
        years_row.addWidget(self._years_slider, 1)
        self._years_val = QLabel("4 yrs")
        self._years_val.setMinimumWidth(150)
        years_row.addWidget(self._years_val)
        layout.addLayout(years_row)

        # --- AAV (spinbox in $M) ---
        aav_row = QHBoxLayout()
        aav_row.addWidget(QLabel("AAV (cap hit/yr)"))
        self._aav_spin = QDoubleSpinBox()
        self._aav_spin.setPrefix("$")
        self._aav_spin.setSuffix("M")
        self._aav_spin.setDecimals(2)
        self._aav_spin.setRange(0, 30)
        self._aav_spin.setSingleStep(0.25)
        self._aav_spin.valueChanged.connect(self._on_aav_changed)
        aav_row.addWidget(self._aav_spin)
        aav_row.addStretch()
        layout.addLayout(aav_row)
        self._aav_hint = QLabel("")
        self._aav_hint.setWordWrap(True)
        self._aav_hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._aav_hint)

        # --- trade protection clause ---
        self._clause_row = QHBoxLayout()
        self._clause_row.addWidget(QLabel("Trade protection"))
        self._clause_combo = QComboBox()
        self._clause_combo.setMinimumWidth(260)
        self._clause_combo.currentIndexChanged.connect(self._on_clause_changed)
        self._clause_row.addWidget(self._clause_combo)
        self._clause_row.addStretch()
        layout.addLayout(self._clause_row)
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
        self._sb_edit.textChanged.connect(self._on_bonus_changed)
        sb_row.addWidget(self._sb_edit)
        sb_row.addStretch()
        layout.addLayout(sb_row)
        self._sb_hint = QLabel("Sweetens the offer for the player.")
        self._sb_hint.setWordWrap(True)
        self._sb_hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._sb_hint)

        # --- performance bonus (ELC only) ---
        self._perf_box = QWidget()
        perf_layout = QVBoxLayout(self._perf_box)
        perf_layout.setContentsMargins(0, 0, 0, 0)
        perf_layout.setSpacing(4)
        pb_row = QHBoxLayout()
        pb_row.addWidget(QLabel("Performance bonus"))
        self._pb_edit = QLineEdit("0")
        self._pb_edit.setValidator(QIntValidator(0, 999_999_999, self))
        self._pb_edit.setMaximumWidth(160)
        self._pb_edit.textChanged.connect(self._on_bonus_changed)
        pb_row.addWidget(self._pb_edit)
        pb_row.addStretch()
        perf_layout.addLayout(pb_row)
        self._pb_hint = QLabel("")
        self._pb_hint.setWordWrap(True)
        self._pb_hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        perf_layout.addWidget(self._pb_hint)
        self._perf_box.setVisible(self._elc)
        layout.addWidget(self._perf_box)

        # --- comparables ---
        self._comps_box = QGroupBox("Comparable contracts")
        self._comps_layout = QVBoxLayout(self._comps_box)
        self._comps_layout.addWidget(QLabel("Loading…"))
        self._comps_box.setVisible(not self._elc)
        layout.addWidget(self._comps_box)

        # --- ELC agent-counter box (hidden unless the agent counters) ---
        self._counter_box = QGroupBox("Agent's counter")
        counter_layout = QVBoxLayout(self._counter_box)
        self._counter_lbl = QLabel("")
        self._counter_lbl.setWordWrap(True)
        counter_layout.addWidget(self._counter_lbl)
        self._meet_btn = QPushButton("Meet the ask")
        self._meet_btn.setObjectName("primary-btn")
        self._meet_btn.clicked.connect(self._on_meet_ask)
        counter_layout.addWidget(self._meet_btn)
        self._counter_box.setVisible(False)
        layout.addWidget(self._counter_box)

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
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        self._submit_btn = QPushButton("Offer ELC" if self._elc else "Extend")
        self._submit_btn.setObjectName("primary-btn")
        self._submit_btn.setEnabled(False)
        self._submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._submit_btn)
        layout.addLayout(btn_row)

        # ELC mode: no trade protection, term locked by signing age.
        if self._elc:
            self._clause_row.itemAt(0).widget().setVisible(False)
            self._clause_combo.setVisible(False)
            self._clause_hint.setVisible(False)
            self._years_slider.setEnabled(False)

        self._load_static()
        self._refresh_terms()

    # -- setup ----------------------------------------------------------

    def _load_static(self):
        game, p = self._game, self._player
        if self._elc:
            band = _elc_band_info(game, p)
            self._elc_band = band
            ok = bool(band.get("ok"))
            elig = _elc_eligible_prospect(game, self._pid) is not None
            self._elc_ok = ok and elig
            if not elig:
                self._note_lbl.setText(
                    "Not your unsigned rights-held prospect.")
            elif not ok:
                self._note_lbl.setText(
                    band.get("error") or "Not ELC-eligible.")
            self._player_lbl.setText(
                f"{_player_name(p)} · {_pos_str(p)} · Age "
                f"{_safe(lambda: int(getattr(p, 'age', 0) or 0), 0)} · "
                f"POT {_safe(lambda: getattr(p, 'potential_grade', '?'), '?')}")
        else:
            self._player_lbl.setText(
                f"{_player_name(p)} · {_pos_str(p)} · Age "
                f"{_safe(lambda: int(getattr(p, 'age', 0) or 0), 0)} · "
                f"{_player_ovr(p)} OVR")
            self._clause_opts = _clause_info(game, p)
            self._fill_clause_combo()
            self._fill_comparables()

    def _fill_clause_combo(self):
        opts = (self._clause_opts or {}).get("options", [])
        self._clause_combo.clear()
        for i, o in enumerate(opts):
            kind = o.get("kind", "none")
            if kind == "none":
                text = "No trade protection"
            else:
                text = (f"{o.get('label', kind)} "
                        f"(≈{_fmt_money(o.get('annual_value', 0))}/yr value)")
            self._clause_combo.addItem(text, kind)
            if not (self._clause_opts or {}).get("eligible", False) \
                    and kind != "none":
                try:
                    self._clause_combo.model().item(i).setEnabled(False)
                except Exception:
                    pass
        self._clause_combo.setCurrentIndex(0)
        self._paint_clause_hint()

    def _fill_comparables(self):
        while self._comps_layout.count():
            child = self._comps_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        comps = _comparables(self._game, self._player)
        if not comps:
            lab = QLabel("No close comparables found.")
            lab.setStyleSheet("color: #8b95ab; font-size: 12px;")
            self._comps_layout.addWidget(lab)
            return
        for c in comps:
            meta = " ".join(x for x in (c.get("tier"), c.get("team"))
                            if x).strip()
            lab = QLabel(
                f"{c.get('name', '?')}  ·  {meta}  —  "
                f"{_fmt_money(c.get('salary', 0))}/yr × "
                f"{c.get('years_remaining', 0)}")
            lab.setStyleSheet("font-size: 12px;")
            self._comps_layout.addWidget(lab)

    # -- input handlers -------------------------------------------------

    def _terms(self):
        years = self._years_slider.value()
        aav = int(round(self._aav_spin.value() * 1_000_000))
        sb = _parse_money(self._sb_edit.text())
        pb = _parse_money(self._pb_edit.text())
        return {"years": years, "aav": aav, "sb": sb, "pb": pb}

    def _clause_kind(self):
        return str(self._clause_combo.currentData() or "none")

    def _on_years_changed(self, _v):
        self._refresh_terms()

    def _on_aav_changed(self, _v):
        self._refresh_terms()

    def _on_bonus_changed(self, _t):
        self._refresh_terms()

    def _on_clause_changed(self, _i):
        self._paint_clause_hint()
        self._refresh_terms()

    def _on_clause_size_changed(self, v):
        self._clause_size = int(v)
        self._clause_size_val.setText(f"{v} teams")

    def _paint_clause_hint(self):
        kind = self._clause_kind()
        self._clause_size_box.setVisible(kind == "mntc")
        hint = self._clause_hint
        d = self._clause_opts or {}
        if not d.get("eligible", False):
            hint.setText(d.get("eligibility_note")
                         or "Trade protection unavailable.")
            return
        if kind == "none":
            hint.setText(d.get("hint") or "")
            return
        o = next((x for x in d.get("options", [])
                  if x.get("kind") == kind), None)
        if o:
            hint.setText(
                f"Offering {o.get('label', kind)} — worth about "
                f"{_fmt_money(o.get('annual_value', 0))}/yr to him "
                f"(counts toward the effective offer).")

    # -- live term preview ----------------------------------------------

    def _refresh_terms(self):
        if self._elc:
            self._refresh_elc()
        else:
            self._refresh_extension()

    def _refresh_extension(self):
        game, p = self._game, self._player
        years_min, years_max = _term_bounds()
        min_sal, max_sal = _salary_bounds(game)
        cur = _contract_row(p)
        est = _extension_estimate(p, _live_cap(game))
        if not self._primed:
            self._primed = True
            sug = min(years_max, 5)
            self._years_slider.setRange(years_min, years_max)
            self._years_slider.setValue(sug)
            span = (max_sal - min_sal) / 40
            step = max(100_000, round(span / 50_000) * 50_000)
            self._aav_spin.setSingleStep(step / 1_000_000)
            self._aav_spin.setValue(est["aav_estimate"] / 1_000_000)
        t = self._terms()
        years = min(max(t["years"], years_min), years_max)
        aav = t["aav"]
        sb = t["sb"]
        self._years_val.setText(f"{years} yr{'s' if years > 1 else ''}")
        self._aav_hint.setText(
            f"Allowed: {_fmt_money(min_sal)} – {_fmt_money(max_sal)}/yr · "
            f"Term: {years_min}–{years_max} yrs")
        self._sb_hint.setText(
            f"Signing bonus: {_fmt_money(sb)} — sweetens the offer for "
            f"the player.")
        self._ask_lbl.setText(
            f"Current: {_fmt_money(cur['cap_hit'])}/yr × "
            f"{cur['years_remaining']} left · Likely accepts "
            f"{_fmt_money(est['accept_low'])}–{_fmt_money(est['accept_high'])}/yr")
        cap = _cap_state(game, offer_salary=aav, extension=True,
                         current_hit=cur["salary"])
        fits = cap["fits"]
        self._cap_lbl.setText(
            f"Cap space: {_fmt_money(cap['current_space'])} → "
            f"{_fmt_money(cap['space_after'])} after "
            f"(replaces {_fmt_money(cur['salary'])}; charge "
            f"{_fmt_money(cap['projected_charge'])} / "
            f"{_fmt_money(cap['live_cap'])})")
        valid, valid_msg = _validate_extension(game, p, aav, years)
        win_ok, win_msg = _extension_window(game, p)
        reason = valid_msg or ""
        if not win_ok:
            reason = win_msg
        can = valid and win_ok and fits
        self._submit_btn.setEnabled(bool(can))
        self._note_lbl.setText(
            "" if can else (reason or "These terms do not fit under the cap."))

    def _refresh_elc(self):
        band = self._elc_band or {}
        if not band.get("ok") or not self._elc_ok:
            if not self._note_lbl.text():
                self._note_lbl.setText(
                    band.get("error") or "Not ELC-eligible.")
            self._submit_btn.setEnabled(False)
            return
        years = int(band["years"])
        floor, ceil = band["floor"], band["ceiling"]
        if not self._primed:
            self._primed = True
            self._years_slider.setRange(years, years)
            self._years_slider.setValue(years)
            ask = (band.get("agent_ask") or {}).get("salary", 0) or \
                (floor + ceil) // 2
            self._aav_spin.setRange(floor / 1_000_000, ceil / 1_000_000)
            self._aav_spin.setSingleStep(0.025)
            self._aav_spin.setValue(
                min(max(ask, floor), ceil) / 1_000_000)
        self._years_val.setText(f"{years} yr{'s' if years > 1 else ''} "
                                f"(locked by signing age)")
        base = int(round(self._aav_spin.value() * 1_000_000))
        sb = _parse_money(self._sb_edit.text())
        pb = _parse_money(self._pb_edit.text())
        max_sb = int(round(base * band["signing_bonus_max_pct"]))
        self._aav_hint.setText(
            f"ELC band: {_fmt_money(floor)} – {_fmt_money(ceil)}/yr base "
            f"(CBA entry-level scale)")
        self._sb_hint.setText(
            f"Signing bonus: {_fmt_money(sb)} — capped at 10% of base "
            f"({_fmt_money(max_sb)}/yr at this base).")
        self._pb_hint.setText(
            f"Performance bonus: {_fmt_money(pb)} — capped at "
            f"{_fmt_money(band['perf_bonus_max'])}/yr (Schedule A + B).")
        ask = band.get("agent_ask") or {}
        if ask.get("salary"):
            parts = [f"Agent's ask: {_fmt_money(ask['salary'])}/yr × "
                     f"{ask.get('years', years)} yr"]
            if ask.get("signing_bonus"):
                parts.append(f"+ {_fmt_money(ask['signing_bonus'])} SB")
            if ask.get("performance_bonus"):
                parts.append(f"+ {_fmt_money(ask['performance_bonus'])}/yr perf")
            if ask.get("flavor"):
                parts.append(f"— {ask['flavor']}")
            self._ask_lbl.setText(" ".join(parts))
        else:
            self._ask_lbl.setText(
                "Entry-level deal — term is fixed, negotiate the base "
                "and bonuses.")
        total = (base + sb + pb) * years
        self._cap_lbl.setText(
            f"Total package: {_fmt_money(total)} "
            f"({_fmt_money(base)}/yr + {_fmt_money(sb)} SB + "
            f"{_fmt_money(pb)} perf × {years} yr)")
        ok, reason = True, ""
        if not (floor <= base <= ceil):
            ok, reason = False, (
                f"Base must sit inside {_fmt_money(floor)}–"
                f"{_fmt_money(ceil)}/yr.")
        elif sb > max_sb:
            ok, reason = False, (
                f"Signing bonus capped at {_fmt_money(max_sb)}/yr.")
        elif pb > band["perf_bonus_max"]:
            ok, reason = False, (
                f"Performance bonus capped at "
                f"{_fmt_money(band['perf_bonus_max'])}/yr.")
        elif base + sb > band["max_annual_comp"]:
            ok, reason = False, (
                "Base + signing bonus exceeds the ELC max annual "
                "compensation.")
        self._submit_btn.setEnabled(bool(ok))
        self._note_lbl.setText("" if ok else reason)

    # -- submit ---------------------------------------------------------

    def _on_submit(self):
        if self._elc:
            self._submit_elc()
        else:
            self._submit_extension()

    def _submit_extension(self):
        game, p = self._game, self._player
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
        ok, msg = _validate_extension(game, p, t["aav"], t["years"])
        if not ok:
            self._note_lbl.setText(msg)
            return
        wok, wmsg = _extension_window(game, p)
        if not wok:
            self._note_lbl.setText(wmsg)
            return
        cap = _cap_state(game, offer_salary=t["aav"], extension=True,
                         current_hit=_contract_salary(p))
        if not cap["fits"]:
            self._note_lbl.setText(
                "These terms do not fit under the cap.")
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
        st = submit_offer(game, p, "extend", t["years"], t["aav"], extras)
        status = st.get("status")
        if status == "accepted":
            self._note_lbl.setStyleSheet("color: #3fb950;")
            self._note_lbl.setText(
                "Signed ✓ — the extension is filed with the league office.")
            QTimer.singleShot(900, self.accept)
        elif status == "countered":
            # Hand the open talks to the negotiation dialog.
            self.open_negotiation.emit(self._pid)
            self.accept()
        else:
            self._note_lbl.setStyleSheet("color: #e5484d;")
            self._note_lbl.setText(
                "Extension refused: " +
                (st.get("note") or
                 "the player rejected the offer outright."))
            self._submit_btn.setEnabled(True)
            self._submit_btn.setText("Extend")

    def _submit_elc(self):
        game, p = self._game, self._player
        band = self._elc_band or {}
        base = int(round(self._aav_spin.value() * 1_000_000))
        sb = _parse_money(self._sb_edit.text())
        pb = _parse_money(self._pb_edit.text())
        # Band re-validation (mirrors the web endpoint's 422 checks).
        if not band.get("ok") or not self._elc_ok:
            self._note_lbl.setText(
                band.get("error") or "Not ELC-eligible.")
            return
        floor, ceil = band["floor"], band["ceiling"]
        max_sb = int(round(base * band["signing_bonus_max_pct"]))
        if not (floor <= base <= ceil):
            self._note_lbl.setText(
                f"ELC base must sit inside {_fmt_money(floor)} - "
                f"{_fmt_money(ceil)}/yr.")
            return
        if not (0 <= sb <= max_sb):
            self._note_lbl.setText(
                f"Signing bonus capped at 10% of base "
                f"({_fmt_money(max_sb)}/yr).")
            return
        if not (0 <= pb <= band["perf_bonus_max"]):
            self._note_lbl.setText(
                f"Performance bonus capped at "
                f"{_fmt_money(band['perf_bonus_max'])}/yr.")
            return
        if base + sb > band["max_annual_comp"]:
            self._note_lbl.setText(
                "Base + signing bonus exceeds the ELC max annual "
                "compensation.")
            return
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Sending…")
        try:
            res = game.handle_elc_offer(p, salary=base, signing_bonus=sb,
                                        performance_bonus=pb)
        except Exception as e:
            self._note_lbl.setText(f"Could not send ELC offer: {e}")
            self._submit_btn.setEnabled(True)
            self._submit_btn.setText("Offer ELC")
            return
        verdict = (res or {}).get("verdict")
        note = (res or {}).get("note") or ""
        if verdict == "accepted":
            self._note_lbl.setStyleSheet("color: #3fb950;")
            self._note_lbl.setText(note or "Signed.")
            QTimer.singleShot(900, self.accept)
        elif verdict == "counter":
            counter = (res or {}).get("counter") or {}
            self._counter_terms = {
                "salary": int(counter.get("salary", 0) or 0),
                "signing_bonus": int(counter.get("signing_bonus", 0) or 0),
                "performance_bonus": int(
                    counter.get("performance_bonus", 0) or 0),
            }
            ct = self._counter_terms
            self._counter_lbl.setText(
                f"{note}\nCounter: {_fmt_money(ct['salary'])}/yr + "
                f"{_fmt_money(ct['signing_bonus'])} SB + "
                f"{_fmt_money(ct['performance_bonus'])}/yr perf.")
            self._counter_box.setVisible(True)
            self._note_lbl.setText("")
            self._submit_btn.setEnabled(True)
            self._submit_btn.setText("Offer ELC")
        else:
            self._note_lbl.setStyleSheet("color: #e5484d;")
            self._note_lbl.setText(note or "The ELC offer was rejected.")
            self._submit_btn.setEnabled(True)
            self._submit_btn.setText("Offer ELC")

    def _on_meet_ask(self):
        ct = getattr(self, "_counter_terms", None)
        if not ct:
            return
        band = self._elc_band or {}
        floor, ceil = band.get("floor", 0), band.get("ceiling", 0)
        sal = min(max(ct["salary"], floor), ceil) if ceil else ct["salary"]
        self._aav_spin.setValue(sal / 1_000_000)
        self._sb_edit.setText(str(ct["signing_bonus"]))
        self._pb_edit.setText(str(ct["performance_bonus"]))
        self._counter_box.setVisible(False)
        self._refresh_terms()

# ---------------------------------------------------------------------------
# negotiation dialog (native port of the web negotiation modal)
# ---------------------------------------------------------------------------

def _offer_str(o):
    yrs = int(o.get("years", 1) or 1)
    return (f"{yrs} yr{'s' if yrs > 1 else ''} × "
            f"{_fmt_money(o.get('aav', 0))}/yr")


class NegotiationDialog(QDialog):
    """Multi-day contract negotiation: offer thread (your offers vs the
    agent's counter) with Walk Away / Counter / Accept.

    Counter is two-step: the first click reveals the fields, the second
    sends. While open, a QTimer re-syncs the thread every 3s (replaces
    the web's polling) so talks advanced elsewhere stay current.
    """

    def __init__(self, game, pid, parent=None):
        super().__init__(parent)
        self._game = game
        self._pid = str(pid)
        self._state = None
        self._busy = False
        self._counter_mode = False
        self._last_sig = None

        self.setWindowTitle("Contract negotiation")
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel("Contract negotiation")
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        self._player_lbl = QLabel("—")
        layout.addWidget(self._player_lbl)

        self._ask_lbl = QLabel("")
        self._ask_lbl.setWordWrap(True)
        layout.addWidget(self._ask_lbl)

        self._thread = QTextEdit()
        self._thread.setReadOnly(True)
        layout.addWidget(self._thread, 1)

        # Counter fields (hidden until the first Counter click).
        self._counter_box = QGroupBox("Your counter")
        counter_layout = QVBoxLayout(self._counter_box)
        cy_row = QHBoxLayout()
        cy_row.addWidget(QLabel("Term"))
        self._cy_slider = QSlider(Qt.Horizontal)
        self._cy_slider.setRange(1, 7)
        self._cy_slider.setValue(4)
        self._cy_slider.setTickPosition(QSlider.TicksBelow)
        self._cy_slider.setTickInterval(1)
        self._cy_slider.valueChanged.connect(self._paint_counter_fields)
        cy_row.addWidget(self._cy_slider, 1)
        self._cy_val = QLabel("4 yrs")
        self._cy_val.setMinimumWidth(70)
        cy_row.addWidget(self._cy_val)
        counter_layout.addLayout(cy_row)
        ca_row = QHBoxLayout()
        ca_row.addWidget(QLabel("AAV"))
        self._ca_spin = QDoubleSpinBox()
        self._ca_spin.setPrefix("$")
        self._ca_spin.setSuffix("M")
        self._ca_spin.setDecimals(2)
        self._ca_spin.setRange(0, 30)
        self._ca_spin.setSingleStep(0.10)
        self._ca_spin.valueChanged.connect(self._paint_counter_fields)
        ca_row.addWidget(self._ca_spin)
        ca_row.addStretch()
        counter_layout.addLayout(ca_row)
        hint = QLabel("The game re-validates terms (league min/max, term, "
                      "cap) before sending.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b95ab; font-size: 12px;")
        counter_layout.addWidget(hint)
        self._counter_box.setVisible(False)
        layout.addWidget(self._counter_box)

        self._note_lbl = QLabel("")
        self._note_lbl.setWordWrap(True)
        self._note_lbl.setStyleSheet("color: #e5484d;")
        layout.addWidget(self._note_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._walk_btn = QPushButton("Walk away")
        self._walk_btn.clicked.connect(self._on_walk)
        btn_row.addWidget(self._walk_btn)
        self._counter_btn = QPushButton("Counter")
        self._counter_btn.clicked.connect(self._on_counter)
        btn_row.addWidget(self._counter_btn)
        self._accept_btn = QPushButton("Accept")
        self._accept_btn.setObjectName("primary-btn")
        self._accept_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(self._accept_btn)
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setVisible(False)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        # Live-sync: re-read the negotiation state every 3s (replaces
        # the web's polling loop).
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._live_sync)
        self._timer.start(3000)

        self._reload()

    def closeEvent(self, event):
        try:
            self._timer.stop()
        except Exception:
            pass
        super().closeEvent(event)

    # -- state ----------------------------------------------------------

    def _reload(self):
        self._state = _negotiations(self._game).get(self._pid)
        self._last_sig = self._signature(self._state)
        self._paint()

    def _signature(self, st):
        if not st:
            return None
        return (st.get("status"), len(st.get("your_offers") or []),
                repr(st.get("counter_terms")), st.get("note"))

    def _live_sync(self):
        """Re-sync the thread while open (talks can also advance via the
        inbox). Never raises."""
        if self._busy or not self.isVisible():
            return
        try:
            st = _negotiations(self._game).get(self._pid)
            changed = False
            if st is not None and st.get("status") in ("awaiting_agent",
                                                      "countered"):
                counter = _pending_counter_message(self._game, self._pid)
                if counter is not None:
                    data = getattr(counter, "action_data", None) or {}
                    terms = {
                        "years": _safe(
                            lambda: int(data.get("years", 1) or 1), 1),
                        "aav": _safe(
                            lambda: int(data.get("asking_price", 0) or 0), 0),
                    }
                    if st.get("status") != "countered" or \
                            st.get("counter_terms") != terms:
                        st["agent_ask"] = terms["aav"]
                        st["counter_terms"] = terms
                        st["status"] = "countered"
                        changed = True
            sig = self._signature(st)
            if changed or sig != self._last_sig:
                self._state = st
                self._last_sig = sig
                self._paint()
        except Exception:
            pass

    # -- rendering ------------------------------------------------------

    def _thread_html(self, st):
        parts = []
        for i, o in enumerate(st.get("your_offers") or []):
            parts.append(f"<div><b>You · offer {i + 1}:</b> "
                         f"{_offer_str(o)}</div>")
        c = st.get("counter_terms")
        status = st.get("status")
        if status == "countered" and c:
            parts.append(f"<div><b>Agent · counter:</b> Wants "
                         f"{_offer_str(c)}</div>")
        elif st.get("agent_ask") and not (st.get("your_offers") or []):
            parts.append(f"<div><b>Agent · ask:</b> "
                         f"{_fmt_money(st['agent_ask'])}/yr</div>")
        if status == "accepted":
            parts.append("<div><b>Deal agreed ✓</b></div>")
        elif status == "refused":
            parts.append("<div>Talks broke down.</div>")
        elif status == "walked":
            parts.append("<div>You walked away — talks closed.</div>")
        elif status == "awaiting_agent":
            parts.append("<div>Waiting on the agent…</div>")
        return "<br>".join(parts) or "No offers yet."

    def _paint(self):
        st = self._state
        if not st:
            self._player_lbl.setText("—")
            self._ask_lbl.setText("No negotiation found for this player.")
            self._thread.setHtml("No offers yet.")
            self._set_actions_visible(False)
            return
        self._player_lbl.setText(st.get("player_name") or "—")
        c = st.get("counter_terms")
        active = st.get("status") == "countered"
        if active and c:
            self._ask_lbl.setText(f"Agent's counter: {_offer_str(c)}")
        else:
            self._ask_lbl.setText(st.get("note") or "Contract negotiation")
        self._thread.setHtml(self._thread_html(st))
        self._set_actions_visible(active)
        if active and c:
            self._accept_btn.setText(f"Accept {_fmt_money(c['aav'])}/yr")
            if not self._counter_mode:
                self._cy_slider.setValue(min(7, max(1, int(c.get("years", 4)
                                                           or 4))))
                self._ca_spin.setValue((c.get("aav", 0) or 0) / 1_000_000)
        if not active and st.get("note"):
            self._note_lbl.setText(st.get("note"))
        self._paint_counter_fields()

    def _set_actions_visible(self, active):
        for b in (self._walk_btn, self._counter_btn, self._accept_btn):
            b.setVisible(active)
        self._close_btn.setVisible(not active)

    def _paint_counter_fields(self):
        yrs = self._cy_slider.value()
        self._cy_val.setText(f"{yrs} yr{'s' if yrs > 1 else ''}")

    def _set_busy(self, b):
        for btn in (self._walk_btn, self._counter_btn, self._accept_btn):
            btn.setEnabled(not b)

    # -- actions ---------------------------------------------------------

    def _on_accept(self):
        if self._busy:
            return
        self._busy = True
        self._set_busy(True)
        self._note_lbl.setText("Accepting the counter…")
        ok, msg = negotiate_accept(self._game, self._pid)
        if not ok:
            self._note_lbl.setText(msg)
        self._reload()
        self._busy = False
        self._set_busy(False)

    def _on_counter(self):
        if self._busy:
            return
        # Two-step counter flow: first click reveals the fields, the
        # second sends.
        if not self._counter_mode:
            self._counter_mode = True
            self._counter_box.setVisible(True)
            self._counter_btn.setText("Send counter")
            self._paint_counter_fields()
            return
        years = self._cy_slider.value()
        aav = int(round(self._ca_spin.value() * 1_000_000))
        if aav <= 0:
            self._note_lbl.setText("Enter an AAV for your counter-offer.")
            return
        # Preserve the trade protection the user originally offered (it
        # rides the counter message: "still on the table").
        counter = _pending_counter_message(self._game, self._pid)
        data = getattr(counter, "action_data", None) or {}
        extras = {
            "clause": str(data.get("clause_kind") or "none"),
            "clause_list_size": int(data.get("clause_list_size", 10) or 10),
            "signing_bonus": 0,
        }
        self._busy = True
        self._set_busy(True)
        self._note_lbl.setText("Sending your counter…")
        ok, msg = negotiate_counter(self._game, self._pid, years, aav,
                                    extras)
        if ok:
            self._counter_mode = False
            self._counter_box.setVisible(False)
            self._counter_btn.setText("Counter")
        else:
            self._note_lbl.setText(msg)
        self._reload()
        self._busy = False
        self._set_busy(False)

    def _on_walk(self):
        if self._busy:
            return
        self._busy = True
        self._set_busy(True)
        self._note_lbl.setText("Walking away…")
        negotiate_walk(self._game, self._pid)
        self._reload()
        self._busy = False
        self._set_busy(False)

# ---------------------------------------------------------------------------
# contracts table (per-row Extend / Talks buttons)
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtGui import QColor


class ContractsTable(PlayerTable):
    """Contract rows sorted by cap hit (desc), with a per-row Extend
    button (or Talks… when a negotiation is open). Sorting is disabled
    on purpose: QTableWidget cell widgets do not follow row moves, and
    the web list was cap-hit sorted."""

    extend_requested = Signal(object)  # player object
    talks_requested = Signal(str)      # player id -> negotiation dialog

    COLUMNS = [
        ("name", "PLAYER", 200),
        ("pos", "POS", 60),
        ("age", "AGE", 55),
        ("ovr", "OVR", 60),
        ("cap_hit", "CAP HIT", 110),
        ("term", "TERM", 130),
        ("action", "", 120),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortingEnabled(False)
        self._rows = []

    def set_rows(self, rows):
        """Populate from _contract_row dicts (pre-sorted by cap hit)."""
        self._rows = list(rows or [])
        self.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            self._fill_row(r, row)

    def _fill_row(self, r, row):
        p = row["player"]
        vals = {
            "name": row["name"],
            "pos": row["position"],
            "age": str(row["age"]),
            "ovr": str(row["overall"]),
            "cap_hit": _fmt_money(row["cap_hit"]),
            "term": ("Expiring ⚠" if row["expiring"]
                     else f"{row['years_remaining']} yrs left"),
        }
        for col, (key, _, _) in enumerate(self.COLUMNS):
            if key == "action":
                continue
            item = QTableWidgetItem(vals[key])
            if key == "name":
                item.setData(Qt.UserRole + 1, p)
                clauses = row.get("clauses") or []
                if clauses:
                    item.setToolTip("Clauses: " + " · ".join(clauses))
            if key == "term" and row["expiring"]:
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor("#e5484d"))
            self.setItem(r, col, item)
        # Per-row action button.
        btn = QPushButton("Talks…" if row.get("talks") else "Extend")
        btn.setCursor(Qt.PointingHandCursor)
        if row.get("talks"):
            font = QFont()
            font.setBold(True)
            btn.setFont(font)
            btn.clicked.connect(
                lambda checked=False, _pid=row["id"]:
                self.talks_requested.emit(_pid))
            btn.setToolTip("Open the ongoing negotiation")
        else:
            btn.clicked.connect(
                lambda checked=False, _p=p:
                self.extend_requested.emit(_p))
            btn.setToolTip("Open the contract extension dialog")
        self.setCellWidget(r, 6, btn)

    def _on_double_click(self, row, _col):
        if 0 <= row < len(self._rows):
            self.player_clicked.emit(self._rows[row]["player"])


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class ContractsScreen(BaseScreen):
    """Roster contracts sorted by cap hit, with extension talks, the
    negotiation modal, clauses, comparables and the ELC flow."""

    title = "Contracts"

    def _build_body(self):
        self._pending = None  # deep-link: (player, elc) opened on refresh

        self._cap_line = QLabel("")
        self._cap_line.setWordWrap(True)
        self._layout.addWidget(self._cap_line)

        self._tabs = QTabWidget()
        self._table_all = ContractsTable()
        self._table_exp = ContractsTable()
        for t in (self._table_all, self._table_exp):
            t.extend_requested.connect(self._on_extend_clicked)
            t.talks_requested.connect(self._open_negotiation)
            t.player_clicked.connect(self._open_profile)
        self._tabs.addTab(self._table_all, "All Contracts")
        self._tabs.addTab(self._table_exp, "Expiring")
        self._layout.addWidget(self._tabs, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self._auto_btn = QPushButton("Auto-Negotiate All Expiring")
        self._auto_btn.setObjectName("primary-btn")
        self._auto_btn.setCursor(Qt.PointingHandCursor)
        self._auto_btn.clicked.connect(self._auto_negotiate)
        actions.addWidget(self._auto_btn)
        self._layout.addLayout(actions)

    # -- deep-link ------------------------------------------------------

    def set_player(self, player, elc=False):
        """Deep-link entry (web /contracts?player=<id>[&elc=1]): open the
        extension dialog — or the ELC flow — for a player. Accepts a
        player object or an id string. If the screen isn't visible yet,
        the dialog opens on the next refresh (i.e. on navigation)."""
        p = player if not isinstance(player, str) else _find_any_player(
            self.game, player)
        if p is None:
            QMessageBox.warning(self, "Contracts", "Player not found.")
            return
        if self.isVisible():
            self._open_extension(p, elc=elc)
        else:
            self._pending = (p, elc)

    # -- data -----------------------------------------------------------

    def refresh(self):
        self._load()
        if self._pending is not None:
            player, elc = self._pending
            self._pending = None
            self._open_extension(player, elc=elc)

    def _load(self):
        team = _user_team(self.game)
        if team is None:
            self._cap_line.setText("No team loaded.")
            self._table_all.set_rows([])
            self._table_exp.set_rows([])
            return
        players = []
        for lst in ("roster", "ahl_roster"):
            players.extend(
                _safe(lambda: list(getattr(team, lst, None) or []),
                      []) or [])
        rows = [_contract_row(p) for p in players]
        for r in rows:
            st = _negotiations(self.game).get(r["id"])
            r["talks"] = bool(
                st and st.get("status") in ("countered", "awaiting_agent"))
        rows.sort(key=lambda d: d["cap_hit"], reverse=True)
        expiring = [r for r in rows if r["expiring"]]
        self._table_all.set_rows(rows)
        self._table_exp.set_rows(expiring)

        cap = _live_cap(self.game)
        try:
            from salary_cap_system import total_cap_charge
            used = int(total_cap_charge(team))
        except Exception:
            used = sum(r["cap_hit"] for r in rows)
        pct = round(used / cap * 100) if cap else 0
        self._cap_line.setText(
            f"Cap hit: {_fmt_money(used)} / {_fmt_money(cap)} "
            f"({pct}% used) — roster contracts sorted by cap hit.")
        self._tabs.setTabText(0, f"All Contracts ({len(rows)})")
        self._tabs.setTabText(1, f"Expiring ({len(expiring)})")

    # -- dialogs --------------------------------------------------------

    def _on_extend_clicked(self, player):
        self._open_extension(player, elc=False)

    def _open_extension(self, player, elc=False):
        st = _negotiations(self.game).get(_pid(player))
        if st and st.get("status") == "countered" and not elc:
            self._open_negotiation(_pid(player))
            return
        dlg = ExtensionDialog(self.game, player, elc=elc, parent=self)
        dlg.open_negotiation.connect(self._open_negotiation)
        dlg.finished.connect(lambda _r: self.refresh())
        dlg.exec()

    def _open_negotiation(self, pid):
        dlg = NegotiationDialog(self.game, pid, parent=self)
        dlg.finished.connect(lambda _r: self.refresh())
        dlg.exec()

    def _open_profile(self, player):
        try:
            self.main_window.show_player(player)
        except Exception:
            try:
                self.navigate_to("player")
            except Exception:
                pass

    # -- auto-negotiate --------------------------------------------------

    def _auto_negotiate(self):
        """Auto-negotiate extensions with every expiring deal.

        Native equivalent of the game's auto_negotiate_extensions, minus
        the Tk messageboxes (which must never pop in the Qt UI): offers
        are pre-validated through the game's own gates, run through the
        real handle_contract_offer(notify="quiet"), and the results land
        in one inbox digest. Confirm-gated like the web button.
        """
        game = self.game
        team = _user_team(game)
        if team is None:
            QMessageBox.warning(self, "Auto-Negotiate", "No team loaded.")
            return
        players = []
        for lst in ("roster", "ahl_roster"):
            players.extend(
                _safe(lambda: list(getattr(team, lst, None) or []),
                      []) or [])
        expiring_players = [p for p in players if _contract_years(p) == 1]
        expiring_staff = [
            s for s in _safe(lambda: list(getattr(team, "staff", None)
                                          or []), []) or []
            if _safe(lambda: int(getattr(s, "contract_years", 0) or 0),
                     0) == 1]
        n = len(expiring_players) + len(expiring_staff)
        if n == 0:
            QMessageBox.information(
                self, "Auto-Negotiate", "No expiring contracts found.")
            return
        reply = QMessageBox.question(
            self, "Auto-Negotiate",
            f"Auto-negotiate extensions with {n} expiring contract(s)? "
            f"Results will arrive in your inbox.")
        if reply != QMessageBox.Yes:
            return
        results = []
        for person in expiring_players + expiring_staff:
            name = _safe(lambda: getattr(person, "full_name", None),
                         None) or _safe(
                             lambda: getattr(person, "name", "Unknown"),
                             "Unknown")
            salary = _contract_salary(person) or _safe(
                lambda: int(getattr(person, "salary", 750_000)
                            or 750_000), 750_000)
            years = _contract_years(person) or _safe(
                lambda: int(getattr(person, "contract_years", 1) or 1), 1)
            # Pre-validate through the game's own gate so the offer path
            # never reaches its Tk messagebox fallback.
            ok, reason = _safe(
                lambda: game._validate_contract_terms(
                    person, salary, years, extension=True),
                (False, "validation failed"))
            if not ok:
                results.append(f"{name}: Skipped ({reason})")
                continue
            try:
                person.salary = salary
                person.contract_years = years
            except Exception:
                pass
            try:
                accepted = game.handle_contract_offer(
                    person, extension=True, notify="quiet")
            except Exception as e:
                results.append(f"{name}: Error ({e})")
                continue
            results.append(
                f"{name}: {'Accepted' if accepted else 'Rejected'}")
        try:
            from game_classes import EmailMessage
            game.send_email_to_user(EmailMessage(
                sender="System", sender_type="System", date_sent=date.today(),
                category="Contracts", priority=2,
                subject="Auto-Negotiation Results",
                content="Automatic extension negotiations complete:\n" +
                        "\n".join(f"\u2022 {r}" for r in results)))
        except Exception:
            pass
        QMessageBox.information(
            self, "Auto-Negotiate",
            "Auto-negotiation complete — check your inbox for results.")
        self.refresh()
