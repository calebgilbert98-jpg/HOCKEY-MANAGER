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
    return _safe(lambda: str(getattr(p, "primary_position", "?") or "?"), "?")


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
            gm = _safe(lambda: live.game_manager)
            team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
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
        gm = _safe(lambda: live.game_manager)
        team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
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


# --- Staff tab ----------------------------------------------------------


def _to_web_staff(s):
    """Staff member -> JSON-safe dict."""
    try:
        name = _safe(lambda: getattr(s, "full_name", None) or getattr(s, "name", "?"), "?")
        role = _safe(lambda: str(getattr(getattr(s, "role", ""), "value", getattr(s, "role", "")) or ""), "")
        dept = _safe(lambda: str(getattr(s, "department", "") or ""), "")
        age = _safe(lambda: int(getattr(s, "age", 0) or 0), 0)
        sal = _safe(lambda: int(getattr(s, "salary", 0) or 0), 0)
        # Overall: average of key ratings or a rating attribute
        ovr = 0
        try:
            ratings = []
            for attr in ("tactics", "development", "scouting", "leadership",
                         "motivation", "discipline", "man_management"):
                v = getattr(s, attr, None)
                if isinstance(v, (int, float)) and v > 0:
                    ratings.append(v)
            if ratings:
                ovr = int(sum(ratings) / len(ratings))
            else:
                ovr = int(getattr(s, "overall", 0) or getattr(s, "rating", 0) or 0)
        except Exception:
            pass
        exp = _safe(lambda: int(getattr(s, "experience", 0) or getattr(s, "years_experience", 0) or 0), 0)
        sid = _safe(lambda: str(getattr(s, "id", "")), "")
        return {"id": sid, "name": name, "role": role, "department": dept,
                "age": age, "salary": sal, "overall": ovr, "experience": exp}
    except Exception:
        return {"id": "", "name": "?", "role": "", "department": "",
                "age": 0, "salary": 0, "overall": 0, "experience": 0}


@bp.route("/api/free_agents/staff")
def api_free_agents_staff():
    """Free-agent staff with filters: role, department, search."""
    live = _live()
    if live is None:
        return jsonify({"staff": []})
    league = _safe(lambda: getattr(getattr(live, "game_manager", None), "league", None))
    pool = _safe(lambda: list(getattr(league, "free_agent_staff", None)
                              or getattr(league, "staff_free_agents", None) or []), []) or []
    role = (request.args.get("role") or "All").strip()
    dept = (request.args.get("department") or "All").strip()
    q = (request.args.get("q") or "").strip().lower()
    out = []
    for s in pool:
        try:
            d = _to_web_staff(s)
            if role != "All" and d["role"] != role:
                continue
            if dept != "All" and d["department"] != dept:
                continue
            if q and q not in d["name"].lower():
                continue
            out.append(d)
        except Exception:
            continue
    try:
        out.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return jsonify({"staff": out})


@bp.route("/api/free_agents/staff/<sid>/offer-preview")
def api_free_agents_staff_offer_preview(sid):
    """Hiring negotiation preview (StaffContractView parity): the staffer's
    market ask, the club's staff budget, and the acceptance-chance estimate
    for a given salary offer."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    pool = _safe(lambda: list(getattr(league, "free_agent_staff", None)
                             or []), []) or []
    target = next((s for s in pool
                   if str(_safe(lambda: getattr(s, "id", ""), "")) == str(sid)),
                  None)
    if target is None:
        return jsonify({"error": "staffer no longer available"}), 404
    try:
        from game_classes import staff_market_ask
        ask = int(staff_market_ask(target))
    except Exception:
        ask = 0
    try:
        from web_ui.screens.staff_detail import _staff_offer_chance
        offer = int(request.args.get("salary") or 0)
        chance = round(_staff_offer_chance(target, offer), 3) if offer else None
    except Exception:
        chance = None
    budget = _safe(lambda: team.staff_budget_remaining(), None) \
        if team is not None else None
    # Unique-role conflict preview (GM / Head Coach can't double).
    conflict = ""
    try:
        from game_classes import Staff as _StaffCls
        if _StaffCls.is_unique_role(getattr(target, "role", None)):
            holders = [s for s in (getattr(team, "staff", None) or [])
                       if s is not target
                       and getattr(s, "role", None)
                       == getattr(target, "role", None)]
            if holders:
                conflict = (f"Team already has a "
                            f"{getattr(target.role, 'value', 'role')}: "
                            f"{getattr(holders[0], 'full_name', '?')}.")
    except Exception:
        pass
    return jsonify({
        "name": _safe(lambda: getattr(target, "full_name", "?"), "?"),
        "role": _safe(lambda: str(getattr(getattr(target, "role", None),
                                          "value", "")), ""),
        "market_ask": ask,
        "budget_remaining": budget,
        "chance": chance,
        "conflict": conflict,
    })


@bp.route("/api/free_agents/staff/hire", methods=["POST"])
def api_free_agents_staff_hire():
    """Queue hiring a free-agent staff member."""
    data = request.get_json(force=True, silent=True) or {}
    sid = str(data.get("staff_id") or "")
    if not sid:
        return jsonify({"ok": False, "error": "staff_id required"}), 400
    # NOTE: enqueue_command(op, **kwargs) -- never the dict-as-first-arg
    # form, which builds {"op": {...}} and silently never dispatches.
    enqueue_command("hire_staff", staff_id=sid,
                    salary=int(data.get("salary") or 0),
                    years=int(data.get("years") or 3),
                    assignment=str(data.get("assignment") or "nhl"))
    return jsonify({"ok": True, "queued": "hire_staff"})


# --- Market Overview tab -------------------------------------------------


@bp.route("/api/free_agents/market")
def api_free_agents_market():
    """Market overview: counts, top available by position, avg asking."""
    live = _live()
    if live is None:
        return jsonify({})
    league = _safe(lambda: getattr(getattr(live, "game_manager", None), "league", None))
    pool = _safe(lambda: list(getattr(league, "free_agents", None) or []), []) or []
    by_pos, by_type = {}, {"UFA": 0, "RFA": 0}
    total_ask, n_ask = 0, 0
    top = []
    for p in pool:
        try:
            d = _to_web_fa(p)
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
    try:
        top.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return jsonify({
        "total": len(pool),
        "by_position": by_pos,
        "by_type": by_type,
        "avg_ask": int(total_ask / n_ask) if n_ask else 0,
        "top_available": top[:10],
    })


# --- Market Analysis -------------------------------------------------------


@bp.route("/api/free_agents/analysis")
def api_free_agents_analysis():
    """Market analysis for one player: value, comparables, projection."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    pid = request.args.get("player_id")
    p = _find_fa(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    d = _to_web_fa(p)
    ask = d.get("ask") or 0
    # Market value: use the game's valuation when available
    try:
        mv = int(_safe(lambda: live.calculate_player_value(p), 0) or 0)
    except Exception:
        mv = 0
    if not mv:
        # Fallback: rough value from overall/age
        ovr = d.get("overall") or 70
        age = d.get("age") or 28
        mv = int(max(750000, (ovr - 60) * 450000 * max(0.4, 1 - (age - 28) * 0.06)))
    diff = mv - ask
    if diff > 500000:
        verdict, vcolor = f"UNDERVALUED by ${diff:,}", "green"
    elif diff < -500000:
        verdict, vcolor = f"OVERVALUED by ${abs(diff):,}", "red"
    else:
        verdict, vcolor = "FAIRLY VALUED", "blue"
    # Comparables: same position, similar overall (+/-3), from FA pool
    comps = []
    try:
        league = _safe(lambda: getattr(getattr(live, "game_manager", None), "league", None))
        pool = _safe(lambda: list(getattr(league, "free_agents", None) or []), []) or []
        pos, ovr = d.get("position"), d.get("overall") or 70
        for q in pool:
            try:
                if q is p:
                    continue
                qd = _to_web_fa(q)
                if qd.get("position") != pos:
                    continue
                if abs((qd.get("overall") or 0) - ovr) > 3:
                    continue
                comps.append({"name": qd.get("name"), "overall": qd.get("overall"),
                              "age": qd.get("age"), "ask": qd.get("ask")})
                if len(comps) >= 5:
                    break
            except Exception:
                continue
    except Exception:
        pass
    # Projection: suggested term + AAV range
    age = d.get("age") or 28
    years_max = _term_bounds(live, extension=False)[1]
    suggested_years = _suggested_years(p, years_max)
    proj_low = int(mv * 0.9)
    proj_high = int(mv * 1.1)
    return jsonify({
        "ok": True,
        "player": d,
        "value": {"market_value": mv, "ask": ask, "verdict": verdict,
                  "color": vcolor},
        "comparables": comps,
        "projection": {"years": suggested_years,
                       "aav_low": proj_low, "aav_high": proj_high},
    })


# --- Compare Players -------------------------------------------------------


@bp.route("/api/free_agents/compare")
def api_free_agents_compare():
    """Side-by-side comparison of 2-3 free agents."""
    live = _live()
    if live is None:
        return jsonify({"players": []})
    pids = [p for p in (request.args.get("player_ids") or "").split(",") if p][:3]
    out = []
    for pid in pids:
        p = _find_fa(live, pid)
        if p is None:
            continue
        try:
            d = _to_web_fa(p)
            # Add key attributes for comparison
            attrs = {}
            for a in ("shooting_accuracy", "passing", "skating", "checking",
                      "defensive_awareness", "offensive_awareness", "strength"):
                try:
                    attrs[a] = int(getattr(p, a, 0) or 0)
                except Exception:
                    pass
            d["compare_attrs"] = attrs
            out.append(d)
        except Exception:
            continue
    return jsonify({"players": out})
