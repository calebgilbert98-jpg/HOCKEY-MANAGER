"""Standings screen: league standings grouped by conference."""
from flask import Blueprint, jsonify, render_template
from web_ui.bridge import _safe

bp = Blueprint("standings", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _standings_payload(live):
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league)
    if league is None:
        return {"conferences": {}, "user_team": None}
    table = _safe(lambda: dict(league.standings), {}) or {}
    teams = _safe(lambda: list(league.teams), []) or []
    user_team_name = _safe(lambda: league.user_team.team_name) or \
        _safe(lambda: live.user_team.team_name)

    rows = []
    for t in teams:
        try:
            name = _safe(lambda: t.team_name, "")
            if not name:
                continue
            row = _safe(lambda: table.get(name), {}) or {}
            w = _safe(lambda: int(row.get("W", 0) or 0), 0)
            l = _safe(lambda: int(row.get("L", 0) or 0), 0)
            otl = _safe(lambda: int(row.get("OTL", 0) or 0), 0)
            pts = _safe(lambda: int(row.get("Points", 0) or 0), 0)
            conf = _safe(lambda: t.conference, "") or "League"
            div = _safe(lambda: t.division, "") or ""
            is_user = _safe(lambda: bool(t.is_user_team), False) or (name == user_team_name)
            rows.append({"name": name, "division": div, "conf": conf,
                         "gp": w + l + otl, "w": w, "l": l, "otl": otl,
                         "pts": pts, "is_user": is_user})
        except Exception:
            continue

    rows.sort(key=lambda r: (-r["pts"], -r["w"], r["name"]))
    conferences = {}
    for r in rows:
        conferences.setdefault(r["conf"], []).append(r)
    return {"conferences": conferences, "user_team": user_team_name}


@bp.route("/standings")
def standings_page():
    return render_template("standings.html")


@bp.route("/api/standings")
def api_standings():
    live = _live()
    if live is None:
        return jsonify({"conferences": {}, "user_team": None})
    try:
        return jsonify(_standings_payload(live))
    except Exception:
        return jsonify({"conferences": {}, "user_team": None})
