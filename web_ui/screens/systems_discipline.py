"""Systems: Discipline List.

Web port of TRACK C #3b (trackc_discipline_view.py, origin/main).
The league-wide DoPS ledger: who's suspended right now (games
remaining) and each club's season suspension history. Reads
Player.suspension_games_remaining and the controversy_history
suspension events (the same source the year-end Discipline Report
reads).
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, player_portrait

bp = Blueprint("systems_discipline", __name__)


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _league():
    live = _live()
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: gm.league) or _safe(lambda: live.league)


def _player_name(p):
    return str(_safe(lambda: getattr(p, "full_name", "?"), "?"))


@bp.route("/systems/discipline")
def discipline_page():
    return render_template("systems_discipline.html")


@bp.route("/api/systems/discipline")
def api_discipline():
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    league = _league()
    if league is None:
        return jsonify({"error": "no league"}), 503
    active, history = [], {}
    for team in list(getattr(league, "teams", None) or []):
        tname = str(getattr(team, "team_name", "?"))
        for p in list(getattr(team, "roster", None) or []):
            try:
                rem = int(getattr(p, "suspension_games_remaining", 0) or 0)
            except (TypeError, ValueError):
                rem = 0
            pid = str(_safe(lambda: getattr(p, "id", ""), ""))
            if rem > 0:
                active.append({"id": pid, "name": _player_name(p),
                               "portrait": player_portrait(pid),
                               "team": tname, "games": rem})
            susp_evs = []
            for e in (getattr(p, "controversy_history", None) or []):
                if not isinstance(e, dict):
                    continue
                if str(e.get("type", "") or "").lower() == "suspension":
                    susp_evs.append(e)
            if susp_evs:
                latest = susp_evs[-1]
                history.setdefault(tname, []).append({
                    "id": pid, "name": _player_name(p),
                    "count": len(susp_evs),
                    "desc": str(latest.get("description", "") or "").strip()[:90],
                    "date": str(latest.get("date", "") or ""),
                })
    active.sort(key=lambda a: -a["games"])
    hist = [{"team": t,
             "entries": sorted(v, key=lambda e: -e["count"])[:6]}
            for t, v in sorted(history.items())]
    return jsonify({"active": active, "history": hist})
