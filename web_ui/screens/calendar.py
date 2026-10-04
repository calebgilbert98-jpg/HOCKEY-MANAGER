"""Calendar screen: month calendar view of the season schedule (read-only v1)."""
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _team_name

bp = Blueprint("calendar", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _iso(d):
    """datetime/date -> 'YYYY-MM-DD' string; anything else -> str fallback."""
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if d is None:
        return ""
    return _safe(lambda: str(d), "") or ""


def _calendar_payload(app):
    """Full schedule -> JSON-safe payload. Never raises."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: app.user_team)
    my_name = _safe(lambda: team.team_name, "") if team else ""

    today = _safe(lambda: gm.current_date) if gm else None
    today_iso = _iso(today)

    sched = []
    if gm is not None:
        league = _safe(lambda: gm.league)
        raw = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
        for g in raw:
            try:
                if not isinstance(g, dict):
                    continue
                home = _team_name(g.get("home_team"))
                away = _team_name(g.get("away_team"))
                gd = g.get("date")
                mine = bool(my_name) and my_name in (home, away)
                sched.append({
                    "date": _iso(gd),
                    "home": home,
                    "away": away,
                    "is_home": bool(mine) and home == my_name,
                    "opponent": away if home == my_name else (home if mine else ""),
                    "mine": mine,
                    "preseason": bool(g.get("preseason", False)),
                })
            except Exception:
                continue

    # chronological where possible (fall back to original order on weird data)
    try:
        sched.sort(key=lambda x: x["date"])
    except Exception:
        pass

    return {
        "today": today_iso,
        "team": my_name or "",
        "games": sched,
    }


@bp.route("/calendar")
def calendar_page():
    return render_template("calendar.html")


@bp.route("/api/calendar")
def api_calendar():
    live = _live()
    if live is None:
        return jsonify({"today": "", "team": "", "games": []})
    return jsonify(_calendar_payload(live))
