"""Finances screen: salary cap, payroll, owner budget (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _web_app_ref, _safe, enqueue_command

bp = Blueprint("finances", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _load_salary_cap_helpers():
    """Defensive import of salary_cap_system helpers (may fail in tests)."""
    try:
        import salary_cap_system as _scs
        return {
            "cap_breakdown": getattr(_scs, "cap_breakdown", None),
            "cap_space": getattr(_scs, "cap_space", None),
            "total_cap_charge": getattr(_scs, "total_cap_charge", None),
            "floor": getattr(_scs, "SALARY_CAP_FLOOR", 78_000_000),
            "default_cap": getattr(_scs, "DEFAULT_CAP", 104_000_000),
        }
    except Exception:
        return None


def _player_cap_hit(p):
    """Best-effort per-player cap hit: contract AAV first, then .salary."""
    hit = _safe(lambda: int(getattr(getattr(p, "contract", None), "salary", 0) or 0)
                + int(getattr(getattr(p, "contract", None), "signing_bonus", 0) or 0)
                - int(getattr(p, "retained_amount", 0) or 0), None)
    if hit is not None and hit > 0:
        return max(0, hit)
    return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)


@bp.route("/finances")
def finances_page():
    return render_template("finances.html")


@bp.route("/api/finances")
def api_finances():
    live = _live()
    if live is None:
        return jsonify({"error": "no live game bound", "cap": None})
    team = _safe(lambda: live.user_team)
    if team is None:
        return jsonify({"error": "no user team"})

    scs = _load_salary_cap_helpers()
    default_cap = (scs or {}).get("default_cap", 104_000_000) if scs else 104_000_000
    floor = (scs or {}).get("floor", 78_000_000) if scs else 78_000_000

    cap = _safe(lambda: int(getattr(team, "salary_cap", default_cap) or default_cap),
                default_cap)

    # --- Cap breakdown: real module first, sum-of-salaries fallback -------
    breakdown = None
    if scs and scs.get("cap_breakdown"):
        breakdown = _safe(lambda: scs["cap_breakdown"](team))
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    sum_hits = _safe(lambda: sum(_player_cap_hit(p) for p in roster), 0)
    if (not isinstance(breakdown, dict)
            or (_safe(lambda: int(breakdown.get("total", 0) or 0), 0) == 0
                and sum_hits > 0)):
        # No contract data (e.g. tests) or module unavailable: fall back to
        # summing player cap hits.
        roster_charge = sum_hits
        breakdown = {
            "cap": cap, "roster": roster_charge, "buried": 0,
            "waivers_shed": 0, "buyouts": 0, "seeded_buyout": 0,
            "seeded_retained": 0, "seeded_overage": 0, "retained": 0,
            "retention_slots": "0/3", "dead_cap": 0, "total": roster_charge,
            "space": cap - roster_charge, "over_cap": (cap - roster_charge) < 0,
            "floor": floor, "floor_space": roster_charge - floor,
            "under_floor": roster_charge < floor,
        }

    total = _safe(lambda: int(breakdown.get("total", 0) or 0), 0)
    space = _safe(lambda: int(breakdown.get("space", cap - total) or 0), 0)
    dead_cap = _safe(lambda: int(breakdown.get("dead_cap", 0) or 0), 0)
    roster_charge = _safe(lambda: int(breakdown.get("roster", 0) or 0), 0)
    over_cap = _safe(lambda: bool(breakdown.get("over_cap", space < 0)), space < 0)
    under_floor = _safe(lambda: bool(breakdown.get("under_floor", total < floor)),
                        total < floor)

    # status: green comfortable / yellow tight / red over-or-under-floor
    pct_free = (space / cap) if cap else 0
    if over_cap:
        status = "over"
    elif under_floor:
        status = "under_floor"
    elif pct_free < 0.03:
        status = "tight"
    else:
        status = "comfortable"

    # --- Payroll breakdown by player (top cap hits) -----------------------
    hits = []
    for p in roster:
        try:
            hits.append({
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": _safe(lambda: getattr(p, "position", "?"), "?"),
                "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                "overall": _safe(lambda: int(getattr(p, "overall", 0) or 0), 0),
                "salary": _player_cap_hit(p),
                "injured": _safe(lambda: bool(getattr(p, "injured", False)), False),
            })
        except Exception:
            continue
    hits.sort(key=lambda h: h["salary"], reverse=True)
    top_hits = hits[:15]

    # --- Owner budget ------------------------------------------------------
    budget = _safe(lambda: int(getattr(team, "player_budget", 0) or 0), 0)
    bonus_spent = _safe(lambda: int(getattr(team, "bonus_spent", 0) or 0), 0)
    budget_remaining = _safe(lambda: int(team.player_budget_remaining()),
                             budget - bonus_spent)

    return jsonify({
        "team": _safe(lambda: getattr(team, "team_name", ""), ""),
        "cap": cap,
        "floor": floor,
        "total": total,
        "space": space,
        "dead_cap": dead_cap,
        "roster_charge": roster_charge,
        "over_cap": over_cap,
        "under_floor": under_floor,
        "status": status,
        "pct_free": pct_free,
        "breakdown": breakdown,
        "top_hits": top_hits,
        "roster_count": len(hits),
        "owner_budget": {
            "budget": budget,
            "spent": bonus_spent,
            "remaining": budget_remaining,
        },
    })
