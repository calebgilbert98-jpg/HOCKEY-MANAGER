"""Playoffs screen: Stanley Cup playoff bracket (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, to_web_team, _resolve_gm

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
                "rounds": [], "is_projection": True,
                "projection_url": "/api/playoffs/projection"}

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
        # Projection banner (desktop _set_projection_banner ~2221): before
        # Round 1 the bracket is a standings projection, not the real thing.
        "is_projection": not started,
        "projection_url": "/api/playoffs/projection",
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


# ------------------------------------------------------------------
# Batch C (League): series detail + pre-playoff projection.
# Ported from playoff_system.py (SeriesDetailPopup / _open_series_detail
# ~2695, build_series_detail_content ~3022, projection banner ~2221).
# ------------------------------------------------------------------

def _series_index(live):
    """Map series id -> (series, bracket) for detail lookup."""
    gm = _resolve_gm(live)
    league = _safe(lambda: gm.league) if gm else None
    bracket = _safe(lambda: getattr(league, "playoff_bracket", None)) \
        if league else None
    idx = {}
    if bracket is not None:
        sm = _safe(lambda: dict(getattr(bracket, "playoff_series", None)
                                or {}), {}) or {}
        for key, series_list in sm.items():
            for s in _safe(lambda: list(series_list or []), []) or []:
                sid = _safe(lambda: str(getattr(s, "series_id", "") or ""))
                if sid:
                    idx[sid] = (s, bracket)
    return idx


def _projection_bracket(live):
    """Standings-based projection bracket (desktop _build_projection_bracket
    ~2209): Round 1 shown as a projection before the playoffs start."""
    gm = _resolve_gm(live)
    league = _safe(lambda: gm.league) if gm else None
    if league is None:
        return None
    try:
        import playoff_system as ps
        bracket = _safe(lambda: getattr(league, "playoff_bracket", None))
        if bracket is None:
            bracket = ps.PlayoffBracket()
        # Mirror the desktop: build a projection copy, never the real one.
        proj = ps.PlayoffBracket()
        try:
            proj.build_projection()
        except Exception:
            return None
        return proj
    except Exception:
        return None


def _projection_payload(live):
    proj = _projection_bracket(live)
    if proj is None:
        return {"available": False, "rounds": []}
    sm = _safe(lambda: dict(getattr(proj, "playoff_series", None) or {}),
               {}) or {}
    rounds = []
    for key in ROUND_ORDER:
        series_list = _safe(lambda: list(sm.get(key, []) or []), [])
        rounds.append({
            "key": key,
            "label": ROUND_LABELS.get(key, key.replace("_", " ").title()),
            "series": [_series_to_web(s) for s in series_list],
        })
    return {"available": any(r["series"] for r in rounds), "rounds": rounds}


@bp.route("/api/playoffs/projection")
def api_playoffs_projection():
    live = _live()
    if live is None:
        return jsonify({"available": False, "rounds": []})
    return jsonify(_projection_payload(live))


@bp.route("/api/playoffs/series/<series_id>")
def api_playoffs_series(series_id):
    """Series detail: status, tale of the tape, games, storylines,
    players to watch, road ahead. Mirrors build_series_detail_content."""
    live = _live()
    if live is None:
        return jsonify({"found": False})
    found = _series_index(live).get(series_id)
    if found is None:
        # Maybe it's a projection series id.
        proj = _projection_bracket(live)
        if proj is not None:
            sm = _safe(lambda: dict(getattr(proj, "playoff_series", None)
                                    or {}), {}) or {}
            for key, series_list in sm.items():
                for s in _safe(lambda: list(series_list or []), []) or []:
                    if _safe(lambda: str(getattr(s, "series_id", "") or "")) \
                            == series_id:
                        found = (s, proj)
                        break
                if found:
                    break
    if found is None:
        return jsonify({"found": False})
    series, bracket = found
    projected = bool(_safe(lambda: getattr(bracket, "is_projection", False),
                           False))
    try:
        import playoff_system as ps

        t1 = _safe(lambda: series.team1)
        t2 = _safe(lambda: series.team2)
        status, _dec = ps.series_status_text(series)

        def _team_card(t):
            nm = _safe(lambda: getattr(t, "team_name", "") or "", "")
            pos = _safe(lambda: getattr(t, "standings_position", ""), "")
            return {
                "name": nm, "abbr": _abbr(t), "seed": pos,
                "record": {
                    "w": _safe(lambda: int(getattr(t, "wins", 0) or 0), 0),
                    "l": _safe(lambda: int(getattr(t, "losses", 0) or 0), 0),
                    "otl": _safe(lambda: int(getattr(t, "ot_losses", 0)
                                             or getattr(t, "otl", 0) or 0), 0),
                },
                "gf": _safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0),
                "ga": _safe(lambda: int(getattr(t, "goals_against", 0) or 0),
                            0),
            }

        detail = {
            "found": True,
            "id": series_id,
            "projected": projected,
            "round": _safe(lambda: getattr(series, "round_name", "") or ""),
            "teams": [_team_card(t1), _team_card(t2)],
            "score": _series_to_web(series),
            "status": status or "Not started",
            "storylines": _safe(
                lambda: list(ps._series_storylines(series)), []) or [],
            "players_to_watch": [],
            "games": [],
            "road_ahead": None,
        }

        # Games in the series.
        for g in _safe(lambda: list(getattr(series, "game_results", None)
                                    or []), []) or []:
            try:
                detail["games"].append({
                    "game": g.get("game_number", len(detail["games"]) + 1),
                    "team1_won": bool(g.get("team1_won")),
                    "score": str(g.get("score", "") or ""),
                    "ot": bool(g.get("ot", False)),
                })
            except Exception:
                continue

        # Players to watch (playoff scoring to date).
        if not projected:
            for t in (t1, t2):
                for pts, name, g, a in ps._top_playoff_scorers(t, n=3):
                    detail["players_to_watch"].append({
                        "team": _abbr(t), "name": name,
                        "pts": pts, "g": g, "a": a,
                    })

        # Road ahead: next-round series this feeds into.
        try:
            nxt_key, nxt = ps.series_target(bracket, series)
            if nxt_key:
                detail["road_ahead"] = {
                    "round": ROUND_LABELS.get(
                        nxt_key, nxt_key.replace("_", " ").title()),
                    "series_id": (_safe(lambda: str(
                        getattr(nxt, "series_id", "") or ""), "")
                        if nxt is not None else None),
                    "opponent": (_abbr(nxt.team1) + " vs " +
                                 _abbr(nxt.team2)) if nxt is not None
                                 else "TBD",
                }
        except Exception:
            pass
        return jsonify(detail)
    except Exception:
        return jsonify({"found": False})
