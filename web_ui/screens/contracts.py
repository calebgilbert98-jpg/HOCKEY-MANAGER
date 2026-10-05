"""Contracts screen: roster contracts sorted by cap hit, with extensions.

v1: table of user-team roster contracts showing player, position, cap
hit, term remaining and an expiring flag. "Extend" enqueues the
"extend_contract" command (the parent must wire that op into
bridge._execute_command / the game's extension path).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("contracts", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


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


def _to_web_contract(p):
    d = to_web_player(p)
    d["position"] = _web_position(p)
    contract = _safe(lambda: getattr(p, "contract", None))
    salary = _safe(lambda: int(getattr(contract, "salary", 0) or 0), 0)
    years = _safe(lambda: getattr(contract, "years_remaining", None))
    if years is None:
        years = _safe(lambda: getattr(contract, "term", None))
    years = _safe(lambda: int(years), 0)
    d["salary"] = salary
    d["cap_hit"] = salary
    d["years_remaining"] = years
    d["expiring"] = bool(years <= 1)
    # clause flags for the tooltip line
    d["no_trade"] = _safe(lambda: bool(getattr(contract, "no_trade_clause", False)), False)
    d["no_movement"] = _safe(lambda: bool(getattr(contract, "no_movement_clause", False)), False)
    d["two_way"] = _safe(lambda: bool(getattr(contract, "two_way", False)), False)
    return d


@bp.route("/contracts")
def contracts_page():
    return render_template("contracts.html")


@bp.route("/api/contracts")
def api_contracts():
    live = _live()
    if live is None:
        return jsonify({"contracts": [], "summary": {}})
    roster = _safe(lambda: list(getattr(live.user_team, "roster", None) or []), []) or []
    rows = []
    for p in roster:
        try:
            rows.append(_to_web_contract(p))
        except Exception:
            continue
    try:
        rows.sort(key=lambda d: d.get("cap_hit", 0), reverse=True)
    except Exception:
        pass
    total = _safe(lambda: sum(r.get("cap_hit", 0) for r in rows), 0)
    cap = _safe(lambda: int(getattr(live.game_manager.league, "salary_cap", 0) or 0), 0)
    return jsonify({
        "contracts": rows,
        "summary": {
            "total_cap_hit": total,
            "cap_ceiling": cap,
            "player_count": len(rows),
        },
    })


# ------------------------------------------------------------------
# v2 contract flow: extension terms, cap preview, validated re-signs
# ------------------------------------------------------------------

@bp.route("/api/contracts/result")
def api_contracts_result():
    """Last queued sign/extend outcome (stashed by the Tk-thread handler)."""
    live = _live()
    result = _safe(lambda: getattr(live, "_web_contract_result", None)) \
        if live else None
    return jsonify({"result": result})

def _find_roster_player(live, pid):
    """Roster player by id. Never raises."""
    try:
        roster = _safe(lambda: list(getattr(live.user_team, "roster", None)
                                    or []), []) or []
        for p in roster:
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
    return 104_000_000


def _term_bounds(live, extension):
    """(min_years, max_years): new CBA = 7 to re-sign, 6 external."""
    try:
        from salary_cap_system import max_contract_term
        return 1, int(max_contract_term(bool(extension)))
    except Exception:
        return 1, 7 if extension else 6


def _salary_bounds(live):
    """(min_salary, max_salary) for a new deal: season-aware league
    minimum, 20%-of-live-cap maximum."""
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
    """Current + projected cap via salary_cap_system.total_cap_charge.
    Extensions replace the player's existing hit instead of stacking.
    Never raises."""
    out = {"live_cap": 0, "current_charge": 0, "current_space": 0,
           "projected_charge": 0, "space_after": 0, "fits": False}
    try:
        from salary_cap_system import total_cap_charge
        cap = _live_cap(live)
        team = _safe(lambda: live.user_team)
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


def _validate_extension(live, p, salary, years):
    """Server-side validation through the game's shared gate
    (HockeyManagerGUI._validate_contract_terms with extension=True).
    Returns (ok, message)."""
    try:
        ok, msg = live._validate_contract_terms(p, int(salary), int(years),
                                                extension=True)
        return bool(ok), (msg or "")
    except Exception:
        return False, "Could not validate contract terms."


def _extension_window(live, p):
    """Extensions only in the final year of a deal
    (transaction_windows.check_window). Returns (ok, reason)."""
    try:
        import transaction_windows as _tw
        d = _safe(lambda: getattr(live, "current_date", None))
        ok, why = _tw.check_window("extension", d, ctx={"player": p})
        return bool(ok), (why or "")
    except Exception:
        return True, ""


def _extension_estimate(p, live_cap):
    """AAV the player would likely accept, replicating the game's own
    market-value curve (ContractExtensionsView.calculate_market_value,
    main.py): cap-relative base (ovr x $100k), age / position /
    potential modifiers, performance bonus. The desktop flow accepts
    90-120% of the player's value (person.negotiate_contract); return
    the band too."""
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
    # Desktop acceptance band: 90-120% of value (negotiate_contract).
    try:
        value = getattr(p, "value",
                        p.overall_rating() * 100_000)
        value = float(value or 0) or float(ovr * 100_000)
    except Exception:
        value = float(ovr * 100_000)
    return {
        "aav_estimate": estimate,
        "accept_low": int(value * 0.9),
        "accept_high": int(value * 1.2),
    }


@bp.route("/api/contracts/extension_terms")
def api_contracts_extension_terms():
    """Current contract + reasonable extension ranges (years, AAV) +
    cap preview. Optional query params years / aav preview exact terms."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    pid = request.args.get("player_id")
    p = _find_roster_player(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    years_min, years_max = _term_bounds(live, extension=True)
    min_sal, max_sal = _salary_bounds(live)
    cur = _to_web_contract(p)
    est = _extension_estimate(p, _live_cap(live))
    try:
        years = int(request.args.get("years") or 0)
    except (TypeError, ValueError):
        years = 0
    try:
        aav = int(float(request.args.get("aav") or 0))
    except (TypeError, ValueError):
        aav = 0
    if not years:
        years = min(years_max, 5 if _safe(lambda: int(getattr(p, "age", 27) or 27), 27) < 33 else 3)
    if not aav:
        aav = est["aav_estimate"]
    win_ok, win_msg = _extension_window(live, p)
    valid, valid_msg = _validate_extension(live, p, aav, years)
    return jsonify({
        "ok": True,
        "player": cur,
        "years_min": years_min,
        "years_max": years_max,
        "min_salary": min_sal,
        "max_salary": max_sal,
        "aav_estimate": est["aav_estimate"],
        "accept_band": {"low": est["accept_low"], "high": est["accept_high"]},
        "preview": {
            "years": years, "aav": aav,
            **_cap_state(live, offer_salary=aav, extension=True,
                         current_hit=cur.get("salary", 0)),
        },
        "window": {"ok": win_ok, "reason": win_msg},
        "valid": valid and win_ok,
        "valid_reason": valid_msg or win_msg,
        "note": ("Extensions apply instantly (no UFA consideration "
                 "period) when the player accepts."),
    })


@bp.route("/api/contracts/extend_real", methods=["POST"])
def api_contracts_extend_real():
    """Queue a real contract extension (years + AAV). Validated twice:
    here through the game's _validate_contract_terms + the extension
    window, and again on the main thread before
    HockeyManagerGUI.handle_contract_offer(extension=True) runs."""
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
    p = _find_roster_player(live, pid)
    if p is None:
        return jsonify({"ok": False, "error": "player not found"}), 404
    ok, msg = _validate_extension(live, p, aav, years)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    ok, msg = _extension_window(live, p)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    queued = enqueue_command("extend_contract_real",
                             player_id=str(pid), years=years, aav=aav)
    return jsonify({"ok": bool(queued), "queued": "extend_contract_real"})
