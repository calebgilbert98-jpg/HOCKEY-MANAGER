"""Playoffs screen: Stanley Cup playoff bracket (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, to_web_team

bp = Blueprint("playoffs", __name__)

ROUND_LABELS = {
    "wild_card": "Round 1",
    "division_semifinals": "Round 2",
    "division_finals": "Division Finals",
    "conference_finals": "Conference Finals",
    "stanley_cup_final": "Stanley Cup Final",
}

ROUND_ORDER = ["wild_card", "division_semifinals", "division_finals",
               "conference_finals", "stanley_cup_final"]


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _abbr(team):
    t = to_web_team(team)
    return _safe(lambda: t.get("abbr") or t.get("name"), "?") or "?"


def _series_to_web(s):
    """PlayoffSeries -> JSON-safe dict."""
    t1 = _safe(lambda: s.team1)
    t2 = _safe(lambda: s.team2)
    t1_wins = _safe(lambda: int(s.team1_wins or 0), 0)
    t2_wins = _safe(lambda: int(s.team2_wins or 0), 0)
    complete = _safe(lambda: bool(s.is_complete), False)
    winner = _safe(lambda: s.winner)
    winner_name = _abbr(winner) if winner else None
    return {
        "id": _safe(lambda: str(getattr(s, "series_id", "") or ""), ""),
        "round": _safe(lambda: getattr(s, "round_name", "") or ""),
        "team1": _abbr(t1),
        "team1_name": _safe(lambda: getattr(t1, "team_name", "") or ""),
        "team2": _abbr(t2),
        "team2_name": _safe(lambda: getattr(t2, "team_name", "") or ""),
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "score": f"{t1_wins}-{t2_wins}",
        "complete": complete,
        "winner": winner_name,
        "leader": winner_name or (_abbr(t1) if t1_wins > t2_wins
                                 else _abbr(t2) if t2_wins > t1_wins else None),
    }


def _bracket_payload(app):
    """Whole bracket -> JSON-safe dict. Never raises."""
    gm = _safe(lambda: app.game_manager)
    league = _safe(lambda: gm.league) if gm else None
    bracket = _safe(lambda: getattr(league, "playoff_bracket", None)) if league else None
    if bracket is None:
        return {"started": False, "champion": None, "current_round": None,
                "rounds": []}

    series_map = _safe(lambda: dict(getattr(bracket, "playoff_series", None) or {}), {})
    rounds = []
    for key in ROUND_ORDER:
        series_list = _safe(lambda: list(series_map.get(key, []) or []), [])
        rounds.append({
            "key": key,
            "label": ROUND_LABELS.get(key, key.replace("_", " ").title()),
            "series": [_series_to_web(s) for s in series_list],
        })

    started = any(r["series"] for r in rounds)
    current_key = _safe(lambda: getattr(bracket, "current_round", ""), "")
    champion = _safe(lambda: getattr(bracket, "stanley_cup_champion", None))
    champion_abbr = _abbr(champion) if champion else None

    return {
        "started": started,
        "champion": champion_abbr,
        "current_round": ROUND_LABELS.get(current_key, current_key) if current_key else None,
        "rounds": rounds,
    }


@bp.route("/playoffs")
def playoffs_page():
    return render_template("playoffs.html")


@bp.route("/api/playoffs")
def api_playoffs():
    live = _live()
    if live is None:
        return jsonify({"started": False, "champion": None,
                        "current_round": None, "rounds": []})
    return jsonify(_bracket_payload(live))
