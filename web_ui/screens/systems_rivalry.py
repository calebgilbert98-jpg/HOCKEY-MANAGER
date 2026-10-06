"""Systems: Rivalry Dashboard.

Web port of TRACK C #4 (trackc_rivalry_view.py, origin/main).
Your team's rivalries ranked by intensity (with the story behind
each) plus the league's hottest team feuds. Reads the live rivalry
store (league.rivalries) via reputation_system.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("systems_rivalry", __name__)

_KIND_LABELS = {
    "team_team": "Team feud",
    "gm_coach": "You vs their coach",
    "coach_coach": "Coaches' feud",
    "gm_gm": "GM feud",
    "gm_respect": "Mutual respect",
    "fan_player": "Fan storyline",
}


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _ctx():
    live = _live()
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    return team, league


def _store(league):
    try:
        import reputation_system as rs
        return rs._rivalry_store(league)
    except Exception:
        return list(getattr(league, "rivalries", None) or [])


def _heat_band(intensity):
    # No teal per UI rules; cooling band uses slate.
    if intensity >= 80:
        return "WHITE HOT", "red"
    if intensity >= 60:
        return "Heated", "gold"
    if intensity >= 40:
        return "Simmering", "blue"
    return "Cooling", "slate"


def _rec_to_json(r):
    try:
        a = str(r.get("a_name", "?"))
        b = str(r.get("b_name", "?"))
        intensity = int(float(r.get("intensity", 0) or 0))
        grudge = int(float(r.get("grudge", 0) or 0))
        kind = _KIND_LABELS.get(r.get("kind"), str(r.get("kind", "")))
        origin = str(r.get("origin", "") or "")
        story = str(r.get("story", "") or "").strip()[:280]
        date = str(r.get("date", "") or "")
    except Exception:
        return None
    band, tone = _heat_band(intensity)
    return {"a": a, "b": b, "intensity": intensity, "grudge": grudge,
            "kind": kind, "origin": origin, "story": story, "date": date,
            "band": band, "tone": tone}


@bp.route("/systems/rivalry")
def rivalry_page():
    return render_template("systems_rivalry.html")


@bp.route("/api/systems/rivalry")
def api_rivalry():
    team, league = _ctx()
    if team is None or league is None:
        return jsonify({"error": "no league"}), 503
    try:
        import reputation_system as rs
        store = _store(league)
        mine = rs.get_rivalries_for(store, team)
    except Exception:
        mine = []
    my_name = getattr(team, "team_name", "")
    try:
        recs = [r for r in _store(league)
                if isinstance(r, dict) and r.get("kind") == "team_team"
                and my_name not in (r.get("a_name"), r.get("b_name"))]
        recs.sort(key=lambda r: -float(r.get("intensity", 0) or 0))
        hottest = recs[:8]
    except Exception:
        hottest = []
    mine_j = [j for j in (_rec_to_json(r) for r in mine[:12]) if j]
    hot_j = [j for j in (_rec_to_json(r) for r in hottest) if j]
    return jsonify({"mine": mine_j, "hottest": hot_j})
