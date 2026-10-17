# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Season Summary + Awards Ceremony hub.

Ported from main.py _show_season_summary (~19203: Awards / League
Leaders / Your Team tabs) and awards_ceremony.py (~255: the full
ceremony script with finalists, winner reveals, voting stories).

The ceremony script is built by the engine's own
awards_ceremony.build_ceremony_data over a thin proxy; the web page
presents it as the dramatic reveal experience. The summary also shows
when the season is actually over (regular season complete).
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("season_end", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _league(live):
    gm = _resolve_gm(live)
    return _safe(lambda: gm.league)


def _season_label(league):
    y = _safe(lambda: int(getattr(league, "season_year", 0) or 0), 0)
    return f"{y}-{y + 1}" if y else ""


def _players(league):
    out = []
    for t in (_safe(lambda: list(league.teams), []) or []):
        for p in (_safe(lambda: list(t.roster), []) or []):
            out.append(p)
    return out


def _roster_map(league):
    try:
        import awards_race as ar
        return ar.roster_team_map(
            _safe(lambda: list(league.teams), []) or [])
    except Exception:
        return {}


def _calc_season_awards(league):
    """Web mirror of main.py _calculate_season_awards: the same
    awards_race rankings decide the trophies (no display-vs-reality
    split)."""
    import awards_race as ar
    players = _players(league)
    teams = _safe(lambda: list(league.teams), []) or []
    team_pct = {}
    for t in teams:
        gp = getattr(t, "games_played", 0) or 0
        pts = getattr(t, "points", 0) or 0
        team_pct[getattr(t, "team_name", "")] = (pts / (2 * gp)) if gp else 0.5
    roster_map = _roster_map(league)

    def _info(entry):
        if not entry:
            return None
        p = entry.get("player")
        if p is None:
            return {"name": entry.get("team") or entry.get("coach") or "?",
                    "team": entry.get("team", "?"), "stats": ""}
        name = getattr(p, "full_name", getattr(p, "name", "?"))
        try:
            pid = int(getattr(p, "id", -1) or -1)
        except Exception:
            pid = -1
        team = roster_map.get(pid) or getattr(p, "team_name", "Unknown") \
            or "Unknown"
        g = int(getattr(p, "goals", 0) or 0)
        a = int(getattr(p, "assists", 0) or 0)
        gp = int(getattr(p, "games_played", 0) or 0)
        return {"name": name, "team": team,
                "stats": f"{g}G {a}A, {g + a} pts in {gp} GP",
                "id": str(getattr(p, "id", ""))}

    def _top(race_fn):
        try:
            r = race_fn()
            return _info(r[0]) if r else None
        except Exception:
            return None

    gm = None
    try:
        import web_ui.bridge as _b
        gm = _b._web_app_ref.game_manager
    except Exception:
        pass
    d = _safe(lambda: getattr(gm, "current_date", None))

    awards = {}
    awards["Hart Trophy (MVP)"] = _top(
        lambda: ar.hart_race(players, team_pct, roster_map=roster_map))
    awards["Ted Lindsay Award (Most Outstanding Player)"] = _top(
        lambda: ar.lindsay_race(players, team_pct, roster_map=roster_map))
    awards["Art Ross Trophy (Scoring Leader)"] = _top(
        lambda: ar.art_ross_race(players))
    awards['Maurice "Rocket" Richard Trophy'] = _top(
        lambda: ar.rocket_race(players))
    goalies = [p for p in players
               if "GOALIE" in str(getattr(getattr(p, "primary_position", None),
                                          "name", "")).upper()]
    awards["Vezina Trophy (Best Goalie)"] = _top(
        lambda: ar.vezina_race(goalies))
    awards["Norris Trophy (Best Defenseman)"] = _top(
        lambda: ar.norris_race(players))
    awards["Selke Trophy (Defensive Forward)"] = _top(
        lambda: ar.selke_race(players))
    awards["Lady Byng Trophy (Sportsmanship)"] = _top(
        lambda: ar.byng_race(players))
    syr = ar.calder_season_year(d) if d is not None else None
    awards["Calder Trophy (Rookie of the Year)"] = _top(
        lambda: ar.calder_race(players, season_year=syr))
    je = _top(lambda: ar.jennings_race(teams))
    awards["Jennings Trophy (Fewest GA)"] = je
    ad = _top(lambda: ar.adams_race(teams))
    awards["Jack Adams (Best Coach)"] = ad
    return awards


def _ceremony_proxy(live, league):
    """Thin proxy so awards_ceremony.build_ceremony_data(gui) runs on web."""
    gm = _resolve_gm(live)

    class _Proxy:
        pass

    p = _Proxy()
    p.league = league
    p.current_date = _safe(lambda: getattr(gm, "current_date", None))
    p._playoff_bracket = _safe(
        lambda: getattr(league, "playoff_bracket", None))

    def _calc(players):
        return _calc_season_awards(league)

    p._calculate_season_awards = _calc
    return p


def _ceremony_script(live, league):
    """Engine's full ceremony script, JSON-safe."""
    try:
        import awards_ceremony as ac
        proxy = _ceremony_proxy(live, league)
        script = ac.build_ceremony_data(proxy)
    except Exception:
        return []
    out = []
    for e in script or []:
        try:
            w = e.get("winner")
            if isinstance(w, str):
                winner = {"name": w, "team": e.get("winner_team", ""),
                          "stats": e.get("winner_stats", "")}
            elif w is not None:
                winner = {
                    "name": getattr(w, "full_name",
                                    getattr(w, "name", "?")),
                    "id": str(getattr(w, "id", "")),
                    "team": e.get("winner_team", ""),
                    "stats": e.get("winner_stats", ""),
                }
            else:
                continue
            finalists = []
            for f in e.get("finalists", []) or []:
                fp = f.get("player")
                finalists.append({
                    "name": f.get("name", "?"),
                    "id": str(getattr(fp, "id", "")) if fp is not None else "",
                    "team": f.get("team", ""),
                    "stats": f.get("stats", ""),
                })
            out.append({
                "award_key": e.get("award_key", ""),
                "trophy": e.get("trophy", ""),
                "flavor": e.get("flavor", ""),
                "winner": winner,
                "finalists": finalists,
                "electorate": e.get("electorate") or "",
                "vote_story": e.get("vote_story") or "",
                "is_team_award": bool(e.get("is_team_award", False)),
            })
        except Exception:
            continue
    return out


def _season_over(league):
    """True when the regular season is complete (desktop shows the
    summary at season end)."""
    try:
        # The engine banks champions into LeagueHistory at Cup win; also
        # check the schedule for unplayed games.
        sched = _safe(lambda: list(getattr(league, "schedule", None)
                                   or []), []) or []
        if sched:
            return not any(not g.get("played", False)
                           for g in sched if isinstance(g, dict))
        bracket = _safe(lambda: getattr(league, "playoff_bracket", None))
        champ = _safe(lambda: getattr(bracket, "stanley_cup_champion", None))
        return champ is not None
    except Exception:
        return False


@bp.route("/season-summary")
def season_summary_page():
    return render_template("season_summary.html")


@bp.route("/api/season-summary")
def api_season_summary():
    """Season Summary: season-over flag, awards, league leaders, your team."""
    live = _live()
    if live is None:
        return jsonify({"season_over": False, "season": "",
                        "awards": {}, "leaders": {}, "team": None})
    league = _league(live)
    if league is None:
        return jsonify({"season_over": False, "season": "",
                        "awards": {}, "leaders": {}, "team": None})
    try:
        season = _season_label(league)
        over = _season_over(league)
        awards = _calc_season_awards(league) if over else {}

        # League leaders (desktop _create_leaders_section).
        players = _players(league)
        roster_map = _roster_map(league)
        leaders = {}
        try:
            def _lead(key, fn, fmt):
                top = sorted(players, key=fn, reverse=True)[:5]
                rows = []
                for p in top:
                    try:
                        pid = int(getattr(p, "id", -1) or -1)
                    except Exception:
                        pid = -1
                    rows.append({
                        "name": getattr(p, "full_name", "?"),
                        "id": str(getattr(p, "id", "")),
                        "team": roster_map.get(pid, ""),
                        "value": fmt(p),
                    })
                leaders[key] = rows

            _lead("Points", lambda p: int(getattr(p, "goals", 0) or 0)
                  + int(getattr(p, "assists", 0) or 0),
                  lambda p: int(getattr(p, "goals", 0) or 0)
                  + int(getattr(p, "assists", 0) or 0))
            _lead("Goals", lambda p: int(getattr(p, "goals", 0) or 0),
                  lambda p: int(getattr(p, "goals", 0) or 0))
            _lead("Assists", lambda p: int(getattr(p, "assists", 0) or 0),
                  lambda p: int(getattr(p, "assists", 0) or 0))
            goalies = [p for p in players
                       if "GOALIE" in str(getattr(
                           getattr(p, "primary_position", None),
                           "name", "")).upper()]
            _lead("Save %", lambda p: float(
                getattr(p, "save_percentage", 0) or 0),
                lambda p: round(float(
                    getattr(p, "save_percentage", 0) or 0), 3))
        except Exception:
            pass

        # Your team (desktop _create_team_summary_section).
        team_info = None
        try:
            gm = _resolve_gm(live)
            ut = _safe(lambda: gm.user_team) or \
                _safe(lambda: live.user_team)
            if ut is not None:
                w = int(getattr(ut, "wins", 0) or 0)
                l = int(getattr(ut, "losses", 0) or 0)
                otl = int(getattr(ut, "ot_losses", 0)
                          or getattr(ut, "otl", 0) or 0)
                pts = int(getattr(ut, "points", 0) or 0)
                table = _safe(lambda: dict(league.standings), {}) or {}
                ordered = sorted(
                    table.items(),
                    key=lambda kv: (-int(kv[1].get("Points", 0) or 0),
                                    -int(kv[1].get("W", 0) or 0)))
                names = [k for k, _ in ordered]
                pos = names.index(ut.team_name) + 1 if \
                    ut.team_name in names else None
                tscorers = sorted(
                    [p for p in (_safe(lambda: list(ut.roster), []) or [])
                     if "GOALIE" not in str(getattr(
                         getattr(p, "primary_position", None),
                         "name", "")).upper()],
                    key=lambda p: (int(getattr(p, "goals", 0) or 0)
                                   + int(getattr(p, "assists", 0) or 0)),
                    reverse=True)[:5]
                team_info = {
                    "name": ut.team_name,
                    "record": f"{w}-{l}-{otl} ({pts} pts)",
                    "position": pos, "of_teams": len(names),
                    "top_scorers": [{
                        "name": getattr(p, "full_name", "?"),
                        "id": str(getattr(p, "id", "")),
                        "line": (f"{int(getattr(p, 'goals', 0) or 0)}G "
                                 f"{int(getattr(p, 'assists', 0) or 0)}A = "
                                 f"{int(getattr(p, 'goals', 0) or 0) + int(getattr(p, 'assists', 0) or 0)} pts"),
                    } for p in tscorers],
                }
        except Exception:
            pass

        return jsonify({
            "season_over": over, "season": season,
            "awards": awards, "leaders": leaders, "team": team_info,
        })
    except Exception:
        return jsonify({"season_over": False, "season": "",
                        "awards": {}, "leaders": {}, "team": None})


@bp.route("/api/awards-ceremony")
def api_awards_ceremony():
    """Full awards ceremony script (finalists, winners, voting stories)."""
    live = _live()
    if live is None:
        return jsonify({"season": "", "script": []})
    league = _league(live)
    if league is None:
        return jsonify({"season": "", "script": []})
    return jsonify({"season": _season_label(league),
                    "script": _ceremony_script(live, league)})
