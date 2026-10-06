"""Stats screen: league leaders (scorers, goals, goalies)."""
from flask import Blueprint, jsonify, render_template
from web_ui.bridge import _safe

bp = Blueprint("stats", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _player_stat(p):
    """JSON-safe leader row for one player; every attr defensive."""
    def _num(attr, default=0):
        return _safe(lambda: float(getattr(p, attr, default) or 0), default) or 0

    from web_ui.bridge import _clean_position
    pos = _safe(lambda: _clean_position(getattr(p, "primary_position", "")), "?")
    return {
        "id": _safe(lambda: str(getattr(p, "id", id(p)))),
        "name": _safe(lambda: getattr(p, "full_name", "?"), "?") or "?",
        "team": _safe(lambda: getattr(p, "team", None) and getattr(p, "team").team_name, "")
               or _safe(lambda: str(getattr(p, "team_name", "") or ""), ""),
        "pos": pos,
        "gp": int(_num("games_played")),
        "g": int(_num("goals")),
        "a": int(_num("assists")),
        "pts": int(_num("points")),
        "pim": int(_num("penalty_minutes")),
        "pm": int(_safe(lambda: getattr(p, "plus_minus", 0) or 0, 0) or 0),
        "sv_pct": round(_num("save_percentage"), 3),
        "gaa": round(_num("goals_against_avg"), 2),
        "so": int(_num("shutouts")),
        "is_goalie": pos.upper() == "G",
    }


def _stats_payload(live):
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league)
    if league is None:
        return {"scorers": [], "goals": [], "goalies": []}
    teams = _safe(lambda: list(league.teams), []) or []

    skaters, goalies = [], []
    for t in teams:
        try:
            team_name = _safe(lambda: t.team_name, "")
            for p in _safe(lambda: list(t.roster), []) or []:
                try:
                    row = _player_stat(p)
                    if not row["team"]:
                        row["team"] = team_name
                    (goalies if row["is_goalie"] else skaters).append(row)
                except Exception:
                    continue
        except Exception:
            continue

    def _fmt_leader(r):
        return {"id": r.get("id"), "name": r["name"], "team": r["team"], "pos": r["pos"],
                "gp": r["gp"], "g": r["g"], "a": r["a"], "pts": r["pts"],
                "pim": r["pim"], "pm": r["pm"],
                "sv_pct": r["sv_pct"], "gaa": r["gaa"], "so": r["so"]}

    scorers = sorted([s for s in skaters if s["gp"] > 0],
                     key=lambda r: (-r["pts"], -r["g"], -r["a"], r["name"]))[:10]
    goal_leaders = sorted([s for s in skaters if s["gp"] > 0],
                          key=lambda r: (-r["g"], -r["a"], -r["pts"], r["name"]))[:5]

    # Goalie leaders: save % with a min-GP guard so one-game call-ups
    # don't top the board. Scales with how far the season has gone.
    max_gp = max([g["gp"] for g in goalies] or [0])
    min_gp = max(3, int(max_gp * 0.15))
    eligible = [g for g in goalies
                if g["gp"] >= min_gp and g.get("sv_pct", 0) > 0]
    goalie_leaders = sorted(eligible,
                            key=lambda r: (-r["sv_pct"], r["gaa"], r["name"]))[:5]

    return {
        "scorers": [_fmt_leader(r) for r in scorers],
        "goals": [_fmt_leader(r) for r in goal_leaders],
        "goalies": [_fmt_leader(r) for r in goalie_leaders],
        "goalie_min_gp": min_gp,
    }


@bp.route("/stats")
def stats_page():
    return render_template("stats.html")


@bp.route("/api/stats")
def api_stats():
    live = _live()
    if live is None:
        return jsonify({"scorers": [], "goals": [], "goalies": []})
    try:
        return jsonify(_stats_payload(live))
    except Exception:
        return jsonify({"scorers": [], "goals": [], "goalies": []})


# ------------------------------------------------------------------
# AHL tab: real farm-league data from ahl_system / ahl_league.
# ------------------------------------------------------------------

def _ahl_payload(live):
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league)
    if league is None:
        return {"skaters": [], "goalies": [], "standings": []}
    try:
        from ahl_system import top_skaters, top_goalies
        from ahl_league import get_ahl_standings, ahl_team_list
    except Exception:
        return {"skaters": [], "goalies": [], "standings": [],
                "error": "AHL module unavailable"}

    def _row(p, team_name, ledger, goalie=False):
        def _n(a, d=0):
            try:
                return float(getattr(ledger, a, d) or 0)
            except Exception:
                return d
        from web_ui.bridge import _clean_position
        pos = _safe(lambda: _clean_position(getattr(p, "primary_position", "")), "?")
        gp = int(_n("games_played"))
        base = {
            "id": _safe(lambda: str(getattr(p, "id", id(p)))),
            "name": _safe(lambda: getattr(p, "full_name", "?"), "?") or "?",
            "team": team_name, "pos": pos, "gp": gp,
        }
        if goalie:
            sv = _n("saves"); sa = _n("shots_against")
            base.update({
                "w": int(_n("wins")), "sv_pct": round(sv / sa, 3) if sa else 0.0,
                "gaa": round(_n("goals_against_avg"), 2),
                "so": int(_n("shutouts")),
            })
        else:
            g = int(_n("goals")); a = int(_n("assists"))
            base.update({"g": g, "a": a, "pts": g + a,
                         "pim": int(_n("penalty_minutes"))})
        return base

    skaters, goalies, standings = [], [], []
    try:
        for p, tname, ledger in top_skaters(league, limit=25):
            skaters.append(_row(p, tname, ledger))
    except Exception:
        pass
    try:
        for p, tname, ledger in top_goalies(league, limit=15, min_gp=5):
            goalies.append(_row(p, tname, ledger, goalie=True))
    except Exception:
        pass
    try:
        teams = ahl_team_list(league)
        for idx, rec in get_ahl_standings(league):
            tname = ""
            try:
                tname = teams[idx].team_name if 0 <= idx < len(teams) else ""
            except Exception:
                pass
            standings.append({
                "team": tname,
                "gp": int(rec.get("gp", 0) or 0),
                "w": int(rec.get("w", 0) or 0),
                "l": int(rec.get("l", 0) or 0),
                "otl": int(rec.get("otl", 0) or 0),
                "pts": int(rec.get("pts", 0) or 0),
                "gf": int(rec.get("gf", 0) or 0),
                "ga": int(rec.get("ga", 0) or 0),
            })
    except Exception:
        pass
    return {"skaters": skaters, "goalies": goalies, "standings": standings}


@bp.route("/api/stats/ahl")
def api_stats_ahl():
    live = _live()
    if live is None:
        return jsonify({"skaters": [], "goalies": [], "standings": []})
    try:
        return jsonify(_ahl_payload(live))
    except Exception:
        return jsonify({"skaters": [], "goalies": [], "standings": []})


# ------------------------------------------------------------------
# RECORDS tab: franchise record book from LeagueHistory.
# ------------------------------------------------------------------

_RECORD_LABELS = {
    "goals": "Goals", "assists": "Assists", "points": "Points",
    "games": "Games Played", "wins": "Wins", "shutouts": "Shutouts",
    "saves": "Saves", "save_pct": "Save %",
    "points_season": "Points", "wins_season": "Wins",
    "championships": "Stanley Cups",
}

_TEAM_RECORD_LABELS = {
    "wins": "Most Wins", "points": "Most Points", "goals_for": "Most Goals For",
    "goals_against": "Fewest Goals Against",
}


def _records_payload(live):
    hist = _safe(lambda: getattr(live, "league_history", None))
    if hist is None:
        gm = _safe(lambda: live.game_manager)
        hist = _safe(lambda: getattr(gm, "league_history", None))
    if hist is None:
        return {"teams": [], "champions": [], "empty": True}
    fr = _safe(lambda: hist.franchise_records)
    if fr is None:
        return {"teams": [], "champions": [], "empty": True}

    def _fmt_rec(rec):
        if not isinstance(rec, dict):
            return None
        v = rec.get("value", 0)
        try:
            v = round(float(v), 3) if float(v) != int(float(v)) else int(float(v))
        except Exception:
            pass
        return {
            "player": rec.get("player", "?"),
            "player_id": rec.get("player_id"),
            "value": v,
            "season": rec.get("season", ""),
        }

    teams = []
    try:
        stores = [
            ("career_records", "Skater — Career"),
            ("season_records", "Skater — Single Season"),
            ("goalie_career_records", "Goalie — Career"),
            ("goalie_season_records", "Goalie — Single Season"),
        ]
        all_teams = set()
        for attr, _ in stores:
            all_teams |= set(_safe(lambda: getattr(fr, attr, {}).keys(), []) or [])
        all_teams |= set(_safe(lambda: getattr(fr, "team_season_records", {}).keys(), []) or [])
        for tname in sorted(all_teams):
            groups = []
            for attr, label in stores:
                store = _safe(lambda: getattr(fr, attr, {}).get(tname, {}), {}) or {}
                cats = []
                for cat, rec in store.items():
                    r = _fmt_rec(rec)
                    if r:
                        r["category"] = _RECORD_LABELS.get(cat, cat.replace("_", " ").title())
                        cats.append(r)
                if cats:
                    groups.append({"label": label, "records": cats})
            tstore = _safe(lambda: getattr(fr, "team_season_records", {}).get(tname, {}), {}) or {}
            tcats = []
            for cat, rec in tstore.items():
                r = _fmt_rec(rec)
                if r:
                    r["category"] = _TEAM_RECORD_LABELS.get(cat, cat.replace("_", " ").title())
                    tcats.append(r)
            if tcats:
                groups.append({"label": "Team — Single Season", "records": tcats})
            if groups:
                teams.append({"team": tname, "groups": groups})
    except Exception:
        pass

    champions = []
    try:
        for s in hist.champions_list():
            champions.append({
                "year": s.get("year"), "champion": s.get("champion"),
                "runner_up": s.get("runner_up"),
                "series": s.get("series_score"),
                "smythe": s.get("conn_smythe"),
            })
    except Exception:
        pass
    return {"teams": teams, "champions": champions,
            "empty": not teams and not champions}


@bp.route("/api/stats/records")
def api_stats_records():
    live = _live()
    if live is None:
        return jsonify({"teams": [], "champions": [], "empty": True})
    try:
        return jsonify(_records_payload(live))
    except Exception:
        return jsonify({"teams": [], "champions": [], "empty": True})


# ------------------------------------------------------------------
# xG / ANALYTICS hub: real expected-goals from the latest tracked game.
# ------------------------------------------------------------------

def _zone_from_coords(x, y, attacking_right=True):
    """Map rink coords (feet, 200x85) to an analytics LOCATION_XG zone.

    Normalizes so the attacked net is at x=189 (right).
    """
    try:
        x = float(x); y = float(y)
    except Exception:
        return "point"
    if not attacking_right:
        x = 200.0 - x
    nx, ny = 189.0, 42.5
    dx, dy = nx - x, ny - y
    dist = (dx * dx + dy * dy) ** 0.5
    off = abs(dy)
    if dist <= 14 and off <= 11:
        return "crease"
    if x >= 150 and off <= 24:
        return "low_slot"
    if x >= 128 and off <= 28:
        return "high_slot"
    if 115 <= x <= 162 and 14 <= off <= 34:
        return "right_circle" if dy < 0 else "left_circle"
    if x >= 100 and off <= 40:
        return "point"
    if x >= 60:
        return "right_wing" if dy < 0 else "left_wing"
    return "behind_net"


def _analytics_from_sim(sim, home, away):
    """xG hub payload from a live GameSim's real shot/momentum logs."""
    import analytics as _an
    try:
        shot_log = list(getattr(sim, "shot_log", None) or [])
    except Exception:
        shot_log = []
    try:
        mom_hist = list(getattr(sim, "momentum_history", None) or [])
    except Exception:
        mom_hist = []
    try:
        xg_totals = dict(getattr(sim, "expected_goals", None) or {})
    except Exception:
        xg_totals = {}

    teams = [home, away]
    per_team = {}
    pbp = []
    for t in teams:
        per_team[t] = {"xg": 0.0, "shots": 0, "goals": 0, "zones": {}}
    for s in shot_log:
        try:
            t = s.get("team") or ""
            if t not in per_team:
                continue
            xg = float(s.get("xg", 0) or 0)
            loc = str(s.get("location", "")).lower()
            if loc not in _an.LOCATION_XG:
                loc = "point"
            out = str(s.get("outcome", "")).lower()
            pt = per_team[t]
            pt["shots"] += 1
            if out == "goal":
                pt["goals"] += 1
            pt["zones"][loc] = pt["zones"].get(loc, 0) + 1
            pbp.append({"event": "shot", "location": loc,
                        "attacking_team": t, "shooter_quality": 50,
                        "situation": "even"})
        except Exception:
            continue
    for t in teams:
        # Prefer the sim's own running xG totals; fall back to summed log.
        tot = xg_totals.get(t)
        per_team[t]["xg"] = round(float(tot), 2) if tot is not None else \
            round(sum(_an.shot_xg(p["location"]) for p in pbp
                      if p["attacking_team"] == t), 2)

    # Momentum series for the chart: (timestamp, -3..+3).
    mom = []
    try:
        for e in mom_hist:
            v = e.get("momentum", "neutral")
            v = v.value if hasattr(v, "value") else str(v)
            ts = e.get("timestamp", e.get("time", 0))
            per = e.get("period", 1)
            mom.append({"t": ts, "period": per, "v": v})
    except Exception:
        pass

    try:
        hs = int(getattr(sim, "home_score", 0) or 0)
        aws = int(getattr(sim, "away_score", 0) or 0)
    except Exception:
        hs, aws = 0, 0
    report = _an.analyst_report({
        "home_team": home, "away_team": away,
        "home_score": hs, "away_score": aws,
        "pbp_events": pbp, "momentum_history": mom_hist,
    })
    return {
        "empty": False, "source": "live",
        "game": {"home": home, "away": away},
        "score": {"home": hs, "away": aws},
        "teams": [{"name": t, **per_team[t]} for t in teams],
        "momentum": mom,
        "report": report,
    }


def _analytics_from_archive(g):
    """xG hub payload from an archived shot-chart game (no team split)."""
    import analytics as _an
    home = g.get("home", "Home"); away = g.get("away", "Away")
    shots = g.get("shots", []) or []
    total_xg, n_goals = 0.0, 0
    zone_counts, zone_xg = {}, {}
    for s in shots:
        try:
            side = str(s.get("side", "")).lower()
            zone = _zone_from_coords(s.get("x"), s.get("y"),
                                     attacking_right=side in ("right", "r", "away"))
            xg = _an.shot_xg(zone)
            total_xg += xg
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
            zone_xg[zone] = round(zone_xg.get(zone, 0.0) + xg, 2)
            if str(s.get("result", "")).lower() == "goal":
                n_goals += 1
        except Exception:
            continue
    return {
        "empty": False, "source": "archive",
        "game": {"home": home, "away": away, "date": g.get("date"),
                 "game_id": g.get("game_id")},
        "total_xg": round(total_xg, 2), "shots": len(shots),
        "goals": n_goals, "zone_counts": zone_counts, "zone_xg": zone_xg,
        "report": (f"Final tracked: {home} vs {away}.\n"
                   f"Total expected goals: {total_xg:.2f} on {len(shots)} attempts.\n"
                   f"Archived shot charts predate team attribution, so xG is "
                   f"shown game-wide — watch a game live for the per-team split."),
    }


def _analytics_payload(live):
    # 1. Prefer the live watch sim: full per-team shot + momentum logs.
    try:
        from web_ui.screens.watch import _watch, _watch_lock
        with _watch_lock:
            sim = _watch.get("sim")
            home = _watch.get("home", "")
            away = _watch.get("away", "")
            running = (_watch.get("thread") is not None
                       and _watch["thread"].is_alive())
        if sim is not None and running and home and away:
            return _analytics_from_sim(sim, home, away)
    except Exception:
        pass
    # 2. Fall back to the most recent archived shot-chart game.
    gm = _safe(lambda: live.game_manager)
    store = _safe(lambda: getattr(gm, "shot_chart_store", None))
    games = _safe(lambda: list(getattr(store, "games", []) or []), []) or []
    if games:
        try:
            return _analytics_from_archive(games[-1])
        except Exception:
            pass
    return {"empty": True,
            "reason": "No tracked games yet — watch a game to generate analytics."}


@bp.route("/api/stats/analytics")
def api_stats_analytics():
    live = _live()
    if live is None:
        return jsonify({"empty": True, "reason": "No live game loaded."})
    try:
        return jsonify(_analytics_payload(live))
    except Exception:
        return jsonify({"empty": True, "reason": "Analytics failed to load."})
