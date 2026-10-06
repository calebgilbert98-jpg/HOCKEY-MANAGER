# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""AHL league hub: standings, scores, Calder Cup bracket, team view,
prospects. Ported from ahl_league_window.py (AHLLeagueView tabs) and
ahl_stats_window.py ("Who's Cooking"). The stats-tab tables already on
/api/stats/ahl stay untouched; this is the full league page.
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, _player_ovr

bp = Blueprint("ahl", __name__)

AHL_TABS = ["Standings", "Scores", "Calder Cup", "Team", "Prospects"]


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _league(live):
    gm = _safe(lambda: live.game_manager)
    return _safe(lambda: gm.league)


def _ahl_teams(league):
    try:
        from ahl_league import ahl_team_list
        return ahl_team_list(league)
    except Exception:
        return []


def _tname(teams, idx):
    try:
        from ahl_league import _tname as _tn
        return _tn(teams, idx)
    except Exception:
        try:
            return teams[idx].team_name
        except Exception:
            return f"Team {idx}"


def _standings_payload(league):
    teams = _ahl_teams(league)
    out = []
    try:
        from ahl_league import get_ahl_standings
        for idx, rec in get_ahl_standings(league):
            tname = _tname(teams, idx)
            parent = ""
            try:
                p = getattr(teams[idx], "parent_team", None)
                parent = getattr(p, "team_name", "") if p else ""
            except Exception:
                pass
            gp = int(rec.get("gp", 0) or 0)
            out.append({
                "team": tname, "idx": idx,
                "gp": gp,
                "w": int(rec.get("w", 0) or 0),
                "l": int(rec.get("l", 0) or 0),
                "otl": int(rec.get("otl", 0) or 0),
                "pts": int(rec.get("pts", 0) or 0),
                "gf": int(rec.get("gf", 0) or 0),
                "ga": int(rec.get("ga", 0) or 0),
                "pt_pct": round(int(rec.get("pts", 0) or 0) / (2 * gp), 3)
                if gp else 0.0,
                "affiliate": parent,
            })
    except Exception:
        pass
    out.sort(key=lambda r: (-r["pts"], -r["w"], r["team"]))
    return out


def _scores_payload(league, live):
    teams = _ahl_teams(league)
    recent, upcoming = [], []
    try:
        from ahl_league import get_ahl_recent_results, get_ahl_upcoming
        gm = _safe(lambda: live.game_manager)
        today = _safe(lambda: gm.current_date)
        for r in get_ahl_recent_results(league, n=20):
            try:
                hn = _tname(teams, r["home"])
                an = _tname(teams, r["away"])
                hs, aws = r["home_score"], r["away_score"]
                final = f"{aws} \u2013 {hs}"
                if r.get("ot"):
                    final += " (OT)"
                recent.append({
                    "date": str(r.get("date", ""))[5:],
                    "away": an, "home": hn, "final": final,
                })
            except Exception:
                continue
        for g in get_ahl_upcoming(league, today, n=20):
            try:
                upcoming.append({
                    "date": str(g.get("date", ""))[5:],
                    "away": g.get("away_name", ""),
                    "home": g.get("home_name", ""),
                })
            except Exception:
                continue
    except Exception:
        pass
    return {"recent": recent, "upcoming": upcoming}


def _calder_payload(league):
    teams = _ahl_teams(league)
    bracket = _safe(lambda: getattr(league, "ahl_bracket", None))
    champs = _safe(lambda: list(getattr(league, "ahl_champions", None)
                                or []), []) or []
    rounds_out = []
    champion = None
    season = ""
    if isinstance(bracket, dict) and bracket.get("rounds"):
        season = str(bracket.get("season", "") or "")
        round_names = ["First Round", "Second Round",
                       "Conference Finals", "Calder Cup Final"]
        for ri, rnd in enumerate(bracket["rounds"]):
            series = []
            for s in rnd:
                try:
                    hn = _tname(teams, s["home"])
                    an = _tname(teams, s["away"])
                    w = _tname(teams, s["winner"]) if s.get("winner") is not None else None
                    gp = s.get("games", 0)
                    series.append({
                        "away": an, "home": hn, "winner": w,
                        "games": gp,
                        "line": (f"{an} vs {hn} \u2014 "
                                 f"{w + ' wins' if w else 'TBD'}"
                                 f"{' in ' + str(gp) if gp and w else ''}"),
                    })
                except Exception:
                    continue
            rounds_out.append({
                "name": (round_names[ri] if ri < len(round_names)
                         else f"Round {ri + 1}"),
                "series": series,
            })
        ci = bracket.get("champion_idx")
        if ci is not None:
            champion = _tname(teams, ci)
    champ_hist = []
    for c in reversed(champs[-8:]):
        try:
            champ_hist.append({
                "season": c.get("season", ""),
                "champion": c.get("champion", ""),
                "runner_up": c.get("runner_up", ""),
            })
        except Exception:
            continue
    return {
        "season": season, "rounds": rounds_out, "champion": champion,
        "champions": champ_hist,
        "note": "Top 16 by points \u2014 best-of-5 series.",
        "empty": not rounds_out and not champ_hist,
    }


def _farm_fake_league(league, idx=None):
    """Adapter so ahl_system helpers run over farm teams (desktop
    _FakeLeague pattern)."""
    teams = _ahl_teams(league)
    if idx is not None and 0 <= idx < len(teams):
        teams = [teams[idx]]

    class _FakeLeague:
        def __init__(self, teams):
            self.teams = teams

    return _FakeLeague(teams)


def _pos_str(p):
    try:
        return str(p.primary_position.value)
    except Exception:
        return str(getattr(p, "primary_position", ""))[:2]


def _pname(p):
    return (getattr(p, "full_name", None) or getattr(p, "name", None)
            or "Unknown")


def _prospects_payload(league):
    farm = _farm_fake_league(league)
    skaters, cooks, goalies = [], [], []
    try:
        import ahl_system as _ahl
        for i, (p, tname, led) in enumerate(
                _ahl.top_skaters(farm, limit=20), 1):
            gp = max(1, int(getattr(led, "games_played", 0) or 0))
            pts = int(getattr(led, "goals", 0) or 0) + int(
                getattr(led, "assists", 0) or 0)
            skaters.append({
                "rank": i, "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                "player": _pname(p), "team": tname,
                "pos": _pos_str(p), "age": getattr(p, "age", ""),
                "gp": int(getattr(led, "games_played", 0) or 0),
                "g": int(getattr(led, "goals", 0) or 0),
                "a": int(getattr(led, "assists", 0) or 0),
                "pts": pts, "ppg": round(pts / gp, 2),
            })
        for i, (p, tname, led, ppg) in enumerate(
                _ahl.cooking(farm, limit=12), 1):
            skaters_pts = (int(getattr(led, "goals", 0) or 0)
                           + int(getattr(led, "assists", 0) or 0))
            cooks.append({
                "rank": i, "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                "player": _pname(p), "team": tname,
                "pos": _pos_str(p), "age": getattr(p, "age", ""),
                "gp": int(getattr(led, "games_played", 0) or 0),
                "pts": skaters_pts, "ppg": round(float(ppg or 0), 2),
            })
        for i, (p, tname, led) in enumerate(
                _ahl.top_goalies(farm, limit=12), 1):
            svp = getattr(led, "save_percentage", 0) or 0
            goalies.append({
                "rank": i, "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                "player": _pname(p), "team": tname,
                "gp": int(getattr(led, "games_played", 0) or 0),
                "w": int(getattr(led, "wins", 0) or 0),
                "gaa": round(float(getattr(led, "goals_against_avg", 0)
                                   or 0), 2),
                "svp": round(float(svp), 3),
            })
    except Exception:
        pass
    return {"skaters": skaters, "cooking": cooks, "goalies": goalies}


def _team_payload(league, live, idx):
    teams = _ahl_teams(league)
    if not (0 <= idx < len(teams)):
        return {"teams": [], "selected": None}
    team = teams[idx]
    tname = _tname(teams, idx)
    names = [{"idx": i, "name": _tname(teams, i)}
             for i in range(len(teams))]
    rec = {}
    try:
        from ahl_league import get_ahl_standings
        rec = dict(get_ahl_standings(league)).get(idx, {}) or {}
    except Exception:
        pass
    roster = []
    try:
        from ahl_league import get_ahl_roster
        for p in get_ahl_roster(team) or []:
            try:
                led = getattr(p, "ahl_stats", None)
                gp = g = a = 0
                if led is not None:
                    gp = int(getattr(led, "games_played", 0) or 0)
                    g = int(getattr(led, "goals", 0) or 0)
                    a = int(getattr(led, "assists", 0) or 0)
                roster.append({
                    "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                    "player": _pname(p), "pos": _pos_str(p),
                    "age": getattr(p, "age", ""),
                    "ovr": _safe(lambda: int(p.overall_rating()), ""),
                    "gp": gp, "g": g, "a": a, "pts": g + a,
                })
            except Exception:
                continue
    except Exception:
        pass
    sched = []
    try:
        from ahl_league import get_ahl_team_schedule
        gm = _safe(lambda: live.game_manager)
        today = _safe(lambda: gm.current_date)
        for g in get_ahl_team_schedule(league, idx, today, n=12):
            sched.append({
                "date": str(g.get("date", ""))[5:],
                "opponent": g.get("opponent", ""),
                "home": bool(g.get("home")),
            })
    except Exception:
        pass
    parent = getattr(team, "parent_team", None)
    return {
        "teams": names,
        "selected": {
            "idx": idx, "name": tname,
            "record": {
                "w": int(rec.get("w", 0) or 0),
                "l": int(rec.get("l", 0) or 0),
                "otl": int(rec.get("otl", 0) or 0),
                "pts": int(rec.get("pts", 0) or 0),
            },
            "affiliate": getattr(parent, "team_name", "") if parent else "",
            "roster": roster,
            "schedule": sched,
        },
    }


def _user_farm_idx(league, live):
    """Index of the user's farm club (desktop _user_farm_idx)."""
    try:
        gm = _safe(lambda: live.game_manager)
        user = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
        uname = _safe(lambda: user.team_name, "")
        teams = _ahl_teams(league)
        for i, t in enumerate(teams):
            parent = getattr(t, "parent_team", None)
            if parent is not None and \
                    getattr(parent, "team_name", "") == uname:
                return i
    except Exception:
        pass
    return None


@bp.route("/ahl")
def ahl_page():
    return render_template("ahl.html")


@bp.route("/api/ahl/overview")
def api_ahl_overview():
    """Landing payload: tabs, user farm index, team list."""
    live = _live()
    if live is None:
        return jsonify({"tabs": AHL_TABS, "teams": [], "user_farm_idx": None,
                        "empty": True})
    league = _league(live)
    if league is None:
        return jsonify({"tabs": AHL_TABS, "teams": [], "user_farm_idx": None,
                        "empty": True})
    teams = _ahl_teams(league)
    return jsonify({
        "tabs": AHL_TABS,
        "teams": [{"idx": i, "name": _tname(teams, i)}
                  for i in range(len(teams))],
        "user_farm_idx": _user_farm_idx(league, live),
        "empty": not teams,
    })


@bp.route("/api/ahl/standings")
def api_ahl_standings():
    live = _live()
    league = _league(live) if live else None
    if league is None:
        return jsonify({"standings": []})
    return jsonify({"standings": _standings_payload(league)})


@bp.route("/api/ahl/scores")
def api_ahl_scores():
    live = _live()
    league = _league(live) if live else None
    if league is None:
        return jsonify({"recent": [], "upcoming": []})
    return jsonify(_scores_payload(league, live))


@bp.route("/api/ahl/calder")
def api_ahl_calder():
    live = _live()
    league = _league(live) if live else None
    if league is None:
        return jsonify({"rounds": [], "champions": [], "empty": True})
    return jsonify(_calder_payload(league))


@bp.route("/api/ahl/team")
def api_ahl_team():
    live = _live()
    league = _league(live) if live else None
    if league is None:
        return jsonify({"teams": [], "selected": None})
    try:
        idx = int(request.args.get("idx", -1))
    except (TypeError, ValueError):
        idx = -1
    if idx < 0:
        idx = _user_farm_idx(league, live)
        if idx is None:
            idx = 0
    return jsonify(_team_payload(league, live, idx))


@bp.route("/api/ahl/prospects")
def api_ahl_prospects():
    live = _live()
    league = _league(live) if live else None
    if league is None:
        return jsonify({"skaters": [], "cooking": [], "goalies": []})
    return jsonify(_prospects_payload(league))
