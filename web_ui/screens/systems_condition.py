"""Systems: Roster Condition.

Web port of TRACK C #2 (trackc_condition_view.py, origin/main).
The whole roster's condition on one surface, worst first. Every
number is an exact engine read (condition_system); nothing is
re-derived or invented.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, player_portrait, _resolve_gm

bp = Blueprint("systems_condition", __name__)

#: Tier colors (desktop used TEAL for GOOD; deep-blue family per UI rules).
_TIER_TONES = {"FRESH": "green", "GOOD": "blue", "WORN": "gold", "GASSED": "red"}
_TIER_RANK = {"GASSED": 0, "WORN": 1, "GOOD": 2, "FRESH": 3}


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _ctx():
    live = _live()
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    today = _safe(lambda: getattr(live, "current_date", None))
    return team, league, today


def _pos_short(p):
    pos = str(_safe(lambda: getattr(getattr(p, "primary_position", None), "name", ""), "") or "")
    return (pos.replace("LEFT_", "L").replace("RIGHT_", "R")
               .replace("_WING", "W").replace("_DEFENSE", "D")
               .replace("CENTER", "C").replace("GOALIE", "G") or "?")


@bp.route("/systems/condition")
def condition_page():
    return render_template("systems_condition.html")


@bp.route("/api/systems/condition")
def api_condition():
    team, league, today = _ctx()
    if team is None:
        return jsonify({"error": "no team"}), 503
    try:
        import condition_system as cs
    except Exception:
        return jsonify({"error": "engine unavailable"}), 503
    rows = []
    for p in list(getattr(team, "roster", None) or []):
        try:
            cond = cs.get_condition(p)
            tier = cs.condition_tier(p)
            energy = cs.get_game_energy(p)
            risk = cs.fatigue_injury_risk_mult(p)
            last_toi = float(getattr(p, "_w3_last_toi_min", 0.0) or 0.0)
            pid = str(_safe(lambda: getattr(p, "id", ""), ""))
            name = str(_safe(lambda: getattr(p, "full_name", "?"), "?"))
            rows.append({"id": pid, "name": name, "pos": _pos_short(p),
                         "portrait": player_portrait(pid),
                         "cond": round(float(cond), 0),
                         "tier": str(tier),
                         "tone": _TIER_TONES.get(str(tier), "blue"),
                         "energy": round(float(energy), 0),
                         "risk": round(float(risk), 2),
                         "last_toi": round(last_toi, 0)})
        except Exception:
            continue
    # Worst first: gassed/worn at the top so the rest call is obvious.
    rows.sort(key=lambda r: (_TIER_RANK.get(r["tier"], 4), r["cond"]))
    counts = {}
    for r in rows:
        counts[r["tier"]] = counts.get(r["tier"], 0) + 1
    gassed = [r["name"] for r in rows if r["tier"] == "GASSED"][:5]
    rest = None
    try:
        schedule = getattr(league, "schedule", None)
        rest = cs.rest_days_after(schedule, team, today)
    except Exception:
        pass
    return jsonify({"rows": rows, "counts": counts, "gassed": gassed,
                    "rest_days": rest})
