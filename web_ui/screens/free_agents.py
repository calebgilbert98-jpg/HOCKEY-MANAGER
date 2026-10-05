"""Free agents screen: UFA/RFA list with make-offer buttons.

v1: sortable/filterable list of players in league.free_agents with
overall color bars and an asking-price display. "Make offer" enqueues
the "sign_free_agent" command (the parent must wire that op into
bridge._execute_command / the game's signing path).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("free_agents", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _fa_type(p):
    """Best-effort UFA/RFA label. Never raises."""
    try:
        if getattr(p, "ufa", None):
            return "UFA"
        if getattr(p, "rfa", None):
            return "RFA"
        age = int(getattr(p, "age", 0) or 0)
        # NHL rule of thumb: 27+ years old or 7+ pro seasons -> unrestricted.
        pro = _safe(lambda: int(getattr(p, "years_pro", 0) or getattr(p, "seasons_played", 0) or 0), 0)
        if age >= 27 or pro >= 7:
            return "UFA"
        return "RFA"
    except Exception:
        return "FA"


def _web_position(p):
    """Best-effort position label. Never raises."""
    try:
        from game_classes import position_label
        label = _safe(lambda: position_label(p))
        if label and label != "?":
            return label
    except Exception:
        pass
    return _safe(lambda: str(getattr(p, "position", "?") or "?"), "?")


def _to_web_fa(p):
    d = to_web_player(p)
    d["position"] = _web_position(p)
    d["fa_type"] = _fa_type(p)
    # asking price: contract.salary on FA players is their demand
    contract = _safe(lambda: getattr(p, "contract", None))
    ask = _safe(lambda: int(getattr(contract, "salary", 0) or getattr(p, "salary", 0) or 0), 0)
    d["ask"] = ask
    d["salary"] = ask
    return d


@bp.route("/free_agents")
def free_agents_page():
    return render_template("free_agents.html")


@bp.route("/api/free_agents")
def api_free_agents():
    live = _live()
    if live is None:
        return jsonify({"players": []})
    league = _safe(lambda: live.game_manager.league)
    pool = _safe(lambda: list(getattr(league, "free_agents", None) or []), []) or []
    players = []
    for p in pool:
        try:
            players.append(_to_web_fa(p))
        except Exception:
            continue
    return jsonify({"players": players})


@bp.route("/api/free_agents/offer", methods=["POST"])
def api_free_agents_offer():
    """Queue a real free-agent offer (years + AAV). v2 contract flow.

    Server-side re-validation (term bounds, league min/max salary, live-cap
    compliance via the game's own _validate_contract_terms, the UFA
    signing window, roster_limits.can_sign_player) before anything is
    queued. The main-thread handler re-validates again before calling
    HockeyManagerGUI.handle_contract_offer().
    """
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    try:
        years = int(data.get("years"))
        aav = int(data.get("aav"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "years and aav must be integers"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    p = _find_fa(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    ok, msg = _validate_offer(live, p, aav, years, extension=False)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    ok, msg = _window_check(live, p, extension=False)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    ok, msg = _sign_eligibility(live, p)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    queued = enqueue_command("sign_free_agent_real",
                             player_id=str(pid), years=years, aav=aav)
    return jsonify({"ok": bool(queued), "queued": "sign_free_agent_real"})


# ------------------------------------------------------------------
# v2 contract flow: real demands, cap preview, validated offers
# ------------------------------------------------------------------

def _find_fa(live, pid):
    """Free agent from league.free_agents by id. Never raises."""
    try:
        league = _safe(lambda: live.game_manager.league)
        pool = _safe(lambda: list(getattr(league, "free_agents", None) or []), []) or []
        for p in pool:
            if str(_safe(lambda: getattr(p, "id", id(p)), "")) == str(pid):
                return p
    except Exception:
        pass
    return None


def _live_cap(live):
    try:
        c = int(live.get_live_cap())
        if c > 0:
            return c
    except Exception:
        pass
    return _safe(lambda: int(getattr(getattr(getattr(live, "game_manager", None),
                                            "league", None), "salary_cap_system",
                                    None).current_cap or 0), 0) or 104_000_000


def _ask_price(p, live):
    """Read-only replica of the agent's ask from
    HockeyManagerGUI.handle_contract_offer (main.py): cap-relative base
    ask via salary_cap_system.base_ask_dollars -> demand_for with the
    live UFA scarcity multiplier, +8% clause premium when the player
    badly wants protection and none is offered.
    """
    try:
        from game_classes import to_100_scale
        from salary_cap_system import (base_ask_dollars, fa_market_scarcity)
        league = _safe(lambda: live.game_manager.league)
        cap_sys = _safe(lambda: getattr(league, "salary_cap_system", None))
        cap = _live_cap(live)
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
        asking = max(int(asking), 750_000)
        try:
            import trade_engine as _te
            team = _safe(lambda: live.user_team)
            if _te.clause_demand_score(p, team, league) >= 0.65:
                asking = int(asking * 1.08)
        except Exception:
            pass
        return asking
    except Exception:
        return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)


def _term_bounds(live, extension):
    """(min_years, max_years) from salary_cap_system.max_contract_term:
    new CBA = 7 to re-sign, 6 external."""
    try:
        from salary_cap_system import max_contract_term
        return 1, int(max_contract_term(bool(extension)))
    except Exception:
        return 1, 7 if extension else 6


def _salary_bounds(live):
    """(min_salary, max_salary) for a new deal: season-aware league
    minimum, and 20%-of-live-cap maximum (per _validate_contract_terms)."""
    cap = _live_cap(live)
    try:
        from salary_cap_system import league_minimum_salary
        sy = _safe(lambda: getattr(getattr(live, "game_manager", None),
                                  "league", None).season_year)
        min_sal = int(league_minimum_salary(sy))
    except Exception:
        min_sal = 775_000
    return min_sal, int(0.20 * cap)


def _cap_state(live, offer_salary=0, extension=False, current_hit=0):
    """Current + projected cap numbers using the central cap accounting
    (salary_cap_system.total_cap_charge), exactly as _validate_contract_terms
    computes them. Never raises."""
    out = {"live_cap": 0, "current_charge": 0, "current_space": 0,
           "projected_charge": 0, "space_after": 0, "fits": False}
    try:
        from salary_cap_system import total_cap_charge
        cap = _live_cap(live)
        team = _safe(lambda: live.user_team)
        charge = int(_safe(lambda: total_cap_charge(team), 0))
        proj = charge + int(offer_salary or 0)
        if extension:
            proj -= int(current_hit or 0)  # extension replaces, not stacks
        out.update(live_cap=cap, current_charge=charge,
                   current_space=cap - charge, projected_charge=proj,
                   space_after=cap - proj, fits=(cap - proj) >= 0)
    except Exception:
        pass
    return out


def _validate_offer(live, p, salary, years, extension):
    """Server-side validation through the game's own shared gate
    (HockeyManagerGUI._validate_contract_terms, main.py). Returns
    (ok, message)."""
    try:
        ok, msg = live._validate_contract_terms(p, int(salary), int(years),
                                                extension=bool(extension))
        return bool(ok), (msg or "")
    except Exception:
        return False, "Could not validate contract terms."


def _window_check(live, p, extension):
    """transaction_windows check: UFA market opens July 1; extensions only
    in the final year of a deal. Returns (ok, reason)."""
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(live, "current_date", None))
        if extension:
            ok, why = _tw.check_window("extension", d, ctx={"player": p})
        else:
            ok, why = _tw.check_window("sign_ufa", d)
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _sign_eligibility(live, p):
    """roster_limits.can_sign_player: Dec-1 ineligible RFAs and emergency
    fillers can't sign. Returns (ok, reason)."""
    try:
        import roster_limits as _rl
        ok, why = _rl.can_sign_player(p)
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _suggested_years(p, years_max):
    try:
        age = int(getattr(p, "age", 27) or 27)
    except Exception:
        age = 27
    suggested = 3 if age >= 33 else 5
    return max(1, min(int(years_max), suggested))


@bp.route("/api/free_agents/demands")
def api_free_agents_demands():
    """Agent's real asking price + term/salary bounds + cap preview for a
    free agent. Optional query params years / aav preview those exact
    terms (defaults: ask AAV, sensible term).
    """
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    pid = request.args.get("player_id")
    p = _find_fa(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    ask = _ask_price(p, live)
    years_min, years_max = _term_bounds(live, extension=False)
    min_sal, max_sal = _salary_bounds(live)
    try:
        years = int(request.args.get("years") or 0)
    except (TypeError, ValueError):
        years = 0
    try:
        aav = int(float(request.args.get("aav") or 0))
    except (TypeError, ValueError):
        aav = 0
    if not years:
        years = _suggested_years(p, years_max)
    if not aav:
        aav = ask
    window_ok, window_msg = _window_check(live, p, extension=False)
    elig_ok, elig_msg = _sign_eligibility(live, p)
    valid, valid_msg = _validate_offer(live, p, aav, years, extension=False)
    return jsonify({
        "ok": True,
        "player": _to_web_fa(p),
        "ask": ask,
        "years_min": years_min,
        "years_max": years_max,
        "years_suggested": _suggested_years(p, years_max),
        "min_salary": min_sal,
        "max_salary": max_sal,
        "preview": {
            "years": years, "aav": aav,
            **_cap_state(live, offer_salary=aav, extension=False),
        },
        "window": {"ok": window_ok, "reason": window_msg},
        "eligibility": {"ok": elig_ok, "reason": elig_msg},
        "valid": valid and window_ok and elig_ok,
        "valid_reason": valid_msg or window_msg or elig_msg,
        # Honest UX note: qualifying UFA offers become consideration bids,
        # not instant signings (ufa_consideration, main.py).
        "note": ("Qualifying offers enter a 3-7 day UFA consideration "
                 "period -- the player fields all clubs' bids before "
                 "deciding. This is not an instant signing."),
    })
