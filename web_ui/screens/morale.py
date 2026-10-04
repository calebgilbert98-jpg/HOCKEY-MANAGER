"""Morale screen: dressing room / team morale (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, enqueue_command

bp = Blueprint("morale", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _player_morale(p):
    """Morale on the 1-100 scale; clamp anything out of range."""
    m = _safe(lambda: getattr(p, "morale", None), None)
    try:
        m = int(float(m)) if m is not None else None
    except Exception:
        m = None
    if m is None:
        return None
    return max(1, min(100, m))


@bp.route("/morale")
def morale_page():
    return render_template("morale.html")


@bp.route("/api/morale")
def api_morale():
    live = _live()
    if live is None:
        return jsonify({"players": [], "count": 0, "average": None,
                        "team_chemistry": None})
    team = _safe(lambda: live.user_team)
    roster = _safe(lambda: list(team.roster), []) or [] if team else []
    players = []
    for p in roster:
        try:
            m = _player_morale(p)
            players.append({
                "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?") or "?",
                "position": _safe(lambda: getattr(p, "position", "?"), "?") or "?",
                "morale": m,
                "captaincy": _safe(lambda: getattr(p, "captaincy", ""), "") or "",
                "injured": _safe(lambda: bool(getattr(p, "injured", False)), False),
            })
        except Exception:
            continue
    # lowest morale first so problem players surface at the top
    players.sort(key=lambda x: (x["morale"] is None, x["morale"] if x["morale"] is not None else 0))
    values = [p["morale"] for p in players if p["morale"] is not None]
    avg = round(sum(values) / len(values)) if values else None
    chemistry = _safe(lambda: team.team_chemistry())
    try:
        chemistry = int(chemistry) if chemistry is not None else None
    except Exception:
        chemistry = None
    return jsonify({
        "players": players,
        "count": len(players),
        "average": avg,
        "team_chemistry": chemistry,
    })
