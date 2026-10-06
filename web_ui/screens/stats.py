"""Stats screen: league leaders (scorers, goals, goalies)."""
from flask import Blueprint, jsonify, render_template
from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("stats", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _player_stat(p):
    """JSON-safe leader row for one player; every attr defensive."""
    def _num(attr, default=0):
        return _safe(lambda: float(getattr(p, attr, default) or 0), default) or 0

    from web_ui.bridge import _clean_position, _resolve_gm
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
    gm = _resolve_gm(live)
    league = _safe(lambda: gm.league)
    if league is None:
        return {"scorers": [], "goals": [], "goalies": []}
    teams = _safe(lambda: list(league.teams), []) or []

    # Batch C (League): global leader filters (desktop on_filter_change).
    # Optional query params; no params = unfiltered (backward compatible).
    from flask import request as _req
    fpos = (_req.args.get("pos") or "All").strip()
    try:
        fmin_gp = max(0, int(_req.args.get("min_gp") or 0))
    except (TypeError, ValueError):
        fmin_gp = 0
    fteam = (_req.args.get("team") or "All").strip() or "All"

    def _pos_group(p):
        try:
            from web_ui.bridge import _clean_position, _resolve_gm
            pos = _clean_position(getattr(p, "primary_position", ""))
            if pos.upper() == "G":
                return "G"
            if pos.upper() in ("LD", "RD", "D"):
                return "D"
            return "F"
        except Exception:
            return "F"

    skaters, goalies = [], []
    for t in teams:
        try:
            team_name = _safe(lambda: t.team_name, "")
            if fteam != "All" and team_name != fteam:
                continue
            for p in _safe(lambda: list(t.roster), []) or []:
                try:
                    row = _player_stat(p)
                    if not row["team"]:
                        row["team"] = team_name
                    if fpos != "All" and _pos_group(p) != fpos:
                        continue
                    if row["gp"] < fmin_gp:
                        continue
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
    gm = _resolve_gm(live)
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
        from web_ui.bridge import _clean_position, _resolve_gm
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
        gm = _resolve_gm(live)
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
    gm = _resolve_gm(live)
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


# ------------------------------------------------------------------
# Batch C (League): player-leader sub-tabs ported from
# stats_standings_window.py (LEADER_TABS ~57; advanced ~3189,
# breakout/rookie/award/milestone sections; global filters).
#
# Global filters (query params, all tabs): pos (F|D|G|All), min_gp,
# team (team name or All), sort override for scoring.
# ------------------------------------------------------------------

_MILESTONE_WATCH_SKATERS = [
    ('career_goals', 'goals', 'Goals', (100, 200, 300, 400, 500, 600, 700), 12),
    ('career_assists', 'assists', 'Assists', (200, 300, 400, 500, 600, 800, 1000), 12),
    ('career_points', 'points', 'Points', (500, 750, 1000, 1250, 1500), 18),
    ('career_games', 'games_played', 'Games Played', (500, 1000, 1500), 25),
]
_MILESTONE_WATCH_GOALIES = [
    ('career_wins', 'wins', 'Wins', (100, 200, 300), 8),
    ('career_shutouts', 'shutouts', 'Shutouts', (25, 50, 75, 100), 4),
    ('career_games_goalie', 'games_played', 'Games Played', (300, 500), 20),
]


def _leader_players(live):
    """All NHL skaters/goalies as (player, team_name) pairs."""
    gm = _resolve_gm(live)
    league = _safe(lambda: gm.league)
    if league is None:
        return [], {}
    teams = _safe(lambda: list(league.teams), []) or []
    pairs, team_map = [], {}
    for t in teams:
        try:
            tname = _safe(lambda: t.team_name, "")
            if tname:
                team_map[tname] = t
            for p in _safe(lambda: list(t.roster), []) or []:
                pairs.append((p, tname))
        except Exception:
            continue
    return pairs, team_map


def _is_goalie(p):
    try:
        pos = getattr(p, "primary_position", None)
        pname = getattr(pos, "name", str(pos))
        return "GOALIE" in str(pname).upper()
    except Exception:
        return False


def _pos_group(p):
    try:
        from web_ui.bridge import _clean_position, _resolve_gm
        pos = _clean_position(getattr(p, "primary_position", ""))
        if pos.upper() == "G":
            return "G"
        if pos.upper() in ("LD", "RD", "D"):
            return "D"
        return "F"
    except Exception:
        return "F"


def _apply_leader_filters(pairs, pos="All", min_gp=0, team="All"):
    out = []
    for p, tname in pairs:
        try:
            if pos != "All" and _pos_group(p) != pos:
                continue
            gp = int(getattr(p, "games_played", 0) or 0)
            if gp < min_gp:
                continue
            if team != "All" and tname != team:
                continue
            out.append((p, tname))
        except Exception:
            continue
    return out


def _leader_row(p, tname, extra=None):
    from web_ui.bridge import _clean_position, _resolve_gm
    pos = _safe(lambda: _clean_position(getattr(p, "primary_position", "")), "?")
    gp = int(getattr(p, "games_played", 0) or 0)
    g = int(getattr(p, "goals", 0) or 0)
    a = int(getattr(p, "assists", 0) or 0)
    row = {
        "id": _safe(lambda: str(getattr(p, "id", id(p)))),
        "name": _safe(lambda: getattr(p, "full_name", "?"), "?") or "?",
        "team": tname, "pos": pos, "gp": gp, "g": g, "a": a,
        "pts": g + a,
        "ppg": round((g + a) / gp, 2) if gp else 0.0,
        "pm": int(getattr(p, "plus_minus", 0) or 0),
        "pim": int(getattr(p, "penalty_minutes", 0) or 0),
        "sog": int(getattr(p, "shots", 0) or getattr(p, "shots_on_goal", 0) or 0),
        "age": int(getattr(p, "age", 0) or 0),
        "is_goalie": _is_goalie(p),
    }
    if row["is_goalie"]:
        row["w"] = int(getattr(p, "wins", 0) or 0)
        row["l"] = int(getattr(p, "losses", 0) or 0)
        row["sv_pct"] = round(float(getattr(p, "save_percentage", 0) or 0), 3)
        row["gaa"] = round(float(getattr(p, "goals_against_avg", 0) or 0), 2)
        row["so"] = int(getattr(p, "shutouts", 0) or 0)
        row["sa"] = int(getattr(p, "shots_against", 0) or 0)
    if extra:
        row.update(extra)
    return row


def _leader_filter_params():
    from flask import request as _req
    pos = (_req.args.get("pos") or "All").strip()
    if pos not in ("All", "F", "D", "G"):
        pos = "All"
    try:
        min_gp = max(0, int(_req.args.get("min_gp") or 0))
    except (TypeError, ValueError):
        min_gp = 0
    team = (_req.args.get("team") or "All").strip() or "All"
    return pos, min_gp, team


@bp.route("/api/stats/advanced")
def api_stats_advanced():
    """Advanced Stats leader tab: ixG/CF%/xGF%/PDO/P60/GSc/SH% via
    advanced_metrics (desktop ~3189). Goalies get GSAx/HDSV%."""
    live = _live()
    if live is None:
        return jsonify({"skaters": [], "goalies": []})
    pos, min_gp, team = _leader_filter_params()
    try:
        import advanced_metrics as am
        pairs, _ = _leader_players(live)
        skaters, goalies = [], []
        for p, tname in _apply_leader_filters(pairs, pos, min_gp, team):
            try:
                if _is_goalie(p):
                    m = am.goalie_advanced(p)
                    r = _leader_row(p, tname)
                    r.update({
                        "gsax": round(float(getattr(m, "gsax", 0) or 0), 1),
                        "hdsv": round(float(getattr(m, "hd_sv_pct", 0)
                                            or getattr(m, "hdsv_pct", 0) or 0), 3),
                    })
                    goalies.append(r)
                else:
                    m = am.skater_advanced(p)
                    r = _leader_row(p, tname)
                    r.update({
                        "ixg": round(float(getattr(m, "ixg", 0) or 0), 1),
                        "cf_pct": round(float(getattr(m, "cf_pct", 0) or 0), 1),
                        "xgf_pct": round(float(getattr(m, "xgf_pct", 0) or 0), 1),
                        "pdo": round(float(getattr(m, "pdo", 0) or 0), 1),
                        "p_per60": round(float(getattr(m, "p_per60", 0) or 0), 2),
                        "game_score": round(float(getattr(m, "game_score", 0) or 0), 2),
                        "sh_pct": round(float(getattr(m, "sh_pct", 0) or 0), 1),
                    })
                    skaters.append(r)
            except Exception:
                continue
        skaters.sort(key=lambda r: (-r.get("game_score", 0), -r["pts"]))
        goalies.sort(key=lambda r: (-r.get("gsax", 0), -r.get("sv_pct", 0)))
        return jsonify({"skaters": skaters[:100], "goalies": goalies[:50],
                        "filters": {"pos": pos, "min_gp": min_gp,
                                    "team": team}})
    except Exception:
        return jsonify({"skaters": [], "goalies": []})


@bp.route("/api/stats/breakout")
def api_stats_breakout():
    """Breakout Players tab: young skaters with elite process signals
    (desktop ~3883: xGF% + ixG-vs-goals regression + PDO + youth + P/60)."""
    live = _live()
    if live is None:
        return jsonify({"players": []})
    pos, min_gp, team = _leader_filter_params()
    try:
        import advanced_metrics as am
        pairs, _ = _leader_players(live)
        out = []
        for p, tname in _apply_leader_filters(pairs, pos, min_gp, team):
            try:
                if _is_goalie(p):
                    continue
                age = int(getattr(p, "age", 99) or 99)
                if age > 26:
                    continue
                m = am.skater_advanced(p)
                goals = int(getattr(p, "goals", 0) or 0)
                xgf_pct = float(getattr(m, "xgf_pct", 50) or 50)
                ixg = float(getattr(m, "ixg", 0) or 0)
                pdo = float(getattr(m, "pdo", 100) or 100)
                p60 = float(getattr(m, "p_per60", 0) or 0)
                score = ((xgf_pct - 50) * 2.0
                         + max(0, ixg - goals) * 1.5
                         + max(0, 100.0 - pdo) * 2.0
                         + max(0, 25 - age) * 1.2
                         + p60 * 3.0)
                signals = []
                if xgf_pct >= 55:
                    signals.append("Elite on-ice impact")
                if ixg - goals >= 3:
                    signals.append("Goals due (ixG > G)")
                if pdo < 98:
                    signals.append("Unlucky shooting/luck")
                if p60 >= 2.0:
                    signals.append("Top-line scoring rate")
                r = _leader_row(p, tname)
                r.update({
                    "breakout_score": round(score, 1),
                    "xgf_pct": round(xgf_pct, 1),
                    "ixg_vs_g": round(ixg - goals, 1),
                    "pdo": round(pdo, 1),
                    "p_per60": round(p60, 2),
                    "signal": "; ".join(signals) or "Watch list",
                })
                out.append(r)
            except Exception:
                continue
        out.sort(key=lambda r: -r["breakout_score"])
        return jsonify({"players": out[:50],
                        "filters": {"pos": pos, "min_gp": min_gp,
                                    "team": team}})
    except Exception:
        return jsonify({"players": []})


@bp.route("/api/stats/rookies")
def api_stats_rookies():
    """Rookie Leaders tab: Calder-eligible skaters + goalies
    (desktop ~799, via awards_race)."""
    live = _live()
    if live is None:
        return jsonify({"skaters": [], "goalies": []})
    try:
        import awards_race as ar
        pairs, _ = _leader_players(live)
        players = [p for p, _ in pairs]
        gm = _resolve_gm(live)
        d = _safe(lambda: gm.current_date)
        syr = ar.calder_season_year(d) if d is not None else None

        def _row(r, goalie=False):
            p = r["player"]
            tname = _safe(lambda: p.team.team_name, "") or \
                _safe(lambda: getattr(p, "team_name", ""), "")
            base = _leader_row(p, tname)
            if goalie:
                base["sv_pct"] = round(float(r.get("sv_pct", 0) or 0), 3)
                base["gaa"] = round(float(r.get("gaa", 0) or 0), 2)
                base["w"] = int(r.get("wins", 0) or 0)
            else:
                base["g"] = int(r.get("goals", 0) or 0)
                base["a"] = int(r.get("assists", 0) or 0)
                base["pts"] = int(r.get("points", 0) or 0)
                base["gp"] = int(r.get("gp", 0) or 0)
            return base

        skaters = [_row(r) for r in
                   ar.rookie_skaters(players, season_year=syr)[:25]]
        goalies = [_row(r, goalie=True) for r in
                   ar.rookie_goalies(players, season_year=syr)[:15]]
        return jsonify({"skaters": skaters, "goalies": goalies,
                        "season_year": syr})
    except Exception:
        return jsonify({"skaters": [], "goalies": []})


@bp.route("/api/stats/award-races")
def api_stats_award_races():
    """Award Races tab: per-award candidate rankings (desktop ~871).

    Query: award (hart|ted_lindsay|art_ross|rocket|norris|selke|byng|
    calder|vezina|jennings|adams).
    """
    live = _live()
    if live is None:
        return jsonify({"awards": [], "award": "", "rows": []})
    from flask import request as _req
    award = (_req.args.get("award") or "hart").strip()
    try:
        import awards_race as ar
        defs = [(n, d, k) for n, d, k in ar.AWARD_DEFINITIONS]
        keys = [k for _, _, k in defs]
        if award not in keys:
            award = keys[0] if keys else "hart"
        name = next((n for n, _, k in defs if k == award), award)
        desc = next((d for _, d, k in defs if k == award), "")

        pairs, team_map = _leader_players(live)
        players = [p for p, _ in pairs]
        roster_map = ar.roster_team_map(list(team_map.values()))
        team_pct = {}
        for tname, t in team_map.items():
            gp = getattr(t, "games_played", 0) or 0
            pts = getattr(t, "points", 0) or 0
            team_pct[tname] = (pts / (2 * gp)) if gp else 0.5
        gm = _resolve_gm(live)
        d = _safe(lambda: gm.current_date)

        race = []
        if award == "hart":
            race = ar.hart_race(players, team_pct, roster_map=roster_map)
        elif award == "ted_lindsay":
            race = ar.lindsay_race(players, team_pct, roster_map=roster_map)
        elif award == "art_ross":
            race = ar.art_ross_race(players)
        elif award == "rocket":
            race = ar.rocket_race(players)
        elif award == "norris":
            race = ar.norris_race(players)
        elif award == "selke":
            race = ar.selke_race(players)
        elif award == "byng":
            race = ar.byng_race(players)
        elif award == "calder":
            syr = ar.calder_season_year(d) if d is not None else None
            race = ar.calder_race(players, season_year=syr)
        elif award == "vezina":
            goalies = [p for p in players if _is_goalie(p)]
            race = ar.vezina_race(goalies)
        elif award == "jennings":
            race = ar.jennings_race(list(team_map.values()))
        elif award == "adams":
            race = ar.adams_race(list(team_map.values()))

        rows = []
        for i, r in enumerate(race[:15], 1):
            try:
                p = r.get("player")
                tname = ""
                if p is not None:
                    pid = int(getattr(p, "id", -1) or -1)
                    tname = roster_map.get(pid, "") or \
                        _safe(lambda: getattr(p, "team_name", ""), "")
                rows.append({
                    "rank": i,
                    "name": r.get("name") or
                    (_safe(lambda: getattr(p, "full_name", "?"), "?") if p is not None else "?"),
                    "team": tname,
                    "score": round(float(r.get("score", 0) or 0), 1),
                    "detail": str(r.get("detail", "") or r.get("note", "") or ""),
                    "id": _safe(lambda: str(getattr(p, "id", "")), "") if p is not None else "",
                    "is_team": p is None,
                })
            except Exception:
                continue
        return jsonify({
            "awards": [{"key": k, "name": n} for n, _, k in defs],
            "award": award, "name": name, "description": desc,
            "rows": rows,
        })
    except Exception:
        return jsonify({"awards": [], "award": award, "rows": []})


@bp.route("/api/stats/milestones")
def api_stats_milestones():
    """Milestone Watch tab: players within reach of career marks
    (desktop ~1154; defs at ~622)."""
    live = _live()
    if live is None:
        return jsonify({"watch": []})
    try:
        from web_ui.bridge import _clean_position, _resolve_gm
        pairs, _ = _leader_players(live)
        watch = []
        for p, tname in pairs:
            try:
                is_g = _is_goalie(p)
                defs = (_MILESTONE_WATCH_GOALIES if is_g
                        else _MILESTONE_WATCH_SKATERS)
                pos = _clean_position(getattr(p, "primary_position", ""))
                for career_attr, season_attr, label, marks, within in defs:
                    current = getattr(p, career_attr, 0) or 0
                    if current <= 0:
                        continue
                    upcoming = [m for m in marks if m > current]
                    if not upcoming:
                        continue
                    target = upcoming[0]
                    needed = target - current
                    if needed <= within:
                        watch.append({
                            "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                            "player": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                            "team": tname, "pos": pos,
                            "milestone": f"{target} {label}",
                            "current": int(current), "needed": int(needed),
                            "season": int(getattr(p, season_attr, 0) or 0),
                        })
            except Exception:
                continue
        watch.sort(key=lambda w: (w["needed"], -w["current"]))
        return jsonify({"watch": watch[:40]})
    except Exception:
        return jsonify({"watch": []})


# ------------------------------------------------------------------
# NHL Records (league records, NOT the franchise book): Season
# Records, Career Records, Record Chase, Achievements. Ported from
# stats_standings_window.py RECORD_TABS (~1266-1460), backed by
# game_manager.record_manager.nhl_records.
# ------------------------------------------------------------------

def _nhl_entry_dict(entry):
    try:
        return {
            "player": getattr(entry, "player_name", "?"),
            "value": getattr(entry, "value", 0),
            "season": getattr(entry, "season", ""),
            "team": getattr(entry, "team", ""),
            "games": getattr(entry, "games_played", None),
            "info": getattr(entry, "additional_info", "") or "",
        }
    except Exception:
        return None


@bp.route("/api/stats/nhl-records")
def api_stats_nhl_records():
    """League NHL records hub: season/career/current/chase/achievements."""
    live = _live()
    empty = {"season": [], "career": [], "team": [], "special": [],
             "chase": [], "achievements": [], "empty": True}
    if live is None:
        return jsonify(empty)
    try:
        gm = _resolve_gm(live)
        rm = _safe(lambda: getattr(gm, "record_manager", None))
        nhl = _safe(lambda: getattr(rm, "nhl_records", None))
        records = _safe(lambda: dict(getattr(nhl, "records", None) or {}), {}) or {}
        if not records:
            return jsonify(empty)

        def _label(key):
            return key.replace("single_season_", "").replace("career_", "") \
                .replace("team_", "").replace("_", " ").title()

        season, career, team_recs, special = [], [], [], []
        for key, rec in records.items():
            try:
                is_season = key.startswith("single_season_")
                is_career = key.startswith("career_")
                is_team = key.startswith("team_")
                main = (getattr(rec, "single_season", None)
                        or getattr(rec, "all_time", None) or rec)
                row = {"key": key, "label": _label(key),
                       "record": _nhl_entry_dict(main)}
                rookie = getattr(rec, "rookie_record", None)
                if rookie is not None:
                    row["rookie_record"] = _nhl_entry_dict(rookie)
                if is_season:
                    season.append(row)
                elif is_career:
                    career.append(row)
                elif is_team:
                    team_recs.append(row)
                else:
                    special.append(row)
            except Exception:
                continue

        # Record Chase: players >= 25% toward a season record (desktop
        # ~4353).
        chase = []
        try:
            pairs, _ = _leader_players(live)
            chase_cats = [
                ("single_season_goals", "Goals",
                 lambda p: int(getattr(p, "goals", 0) or 0)),
                ("single_season_assists", "Assists",
                 lambda p: int(getattr(p, "assists", 0) or 0)),
                ("single_season_points", "Points",
                 lambda p: (int(getattr(p, "goals", 0) or 0)
                            + int(getattr(p, "assists", 0) or 0))),
                ("single_season_wins", "Wins",
                 lambda p: int(getattr(p, "wins", 0) or 0)),
                ("single_season_shutouts", "Shutouts",
                 lambda p: int(getattr(p, "shutouts", 0) or 0)),
            ]
            from web_ui.bridge import _clean_position, _resolve_gm
            for key, label, fn in chase_cats:
                rec = records.get(key)
                entry = (getattr(rec, "single_season", None)
                         or getattr(rec, "all_time", None) or rec)
                target = getattr(entry, "value", 0) or 0
                if not target:
                    continue
                for p, tname in pairs:
                    try:
                        cur = fn(p)
                        if cur <= 0:
                            continue
                        pct = cur / target * 100
                        if pct >= 25.0:
                            chase.append({
                                "player": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                                "id": _safe(lambda: str(getattr(p, "id", id(p)))),
                                "team": tname,
                                "pos": _clean_position(getattr(p, "primary_position", "")),
                                "record": label,
                                "current": cur, "target": target,
                                "needed": target - cur,
                                "pct": round(pct, 1),
                            })
                    except Exception:
                        continue
            chase.sort(key=lambda c: -c["pct"])
            chase = chase[:20]
        except Exception:
            pass

        # Achievements: recently broken records (desktop ~4452).
        achievements = []
        try:
            recent = _safe(lambda: rm.get_recent_records(20), []) or []
            for r in recent:
                if isinstance(r, dict):
                    achievements.append({
                        "date": str(r.get("date", "") or ""),
                        "player": str(r.get("player", r.get("player_name", "")) or ""),
                        "record": str(r.get("record", r.get("record_type", "")) or ""),
                        "value": r.get("value", ""),
                        "previous": r.get("previous", ""),
                    })
        except Exception:
            pass

        n_recs = len(season) + len(career) + len(team_recs) + len(special)
        return jsonify({
            "season": season, "career": career, "team": team_recs,
            "special": special, "chase": chase,
            "achievements": achievements,
            "total": n_recs,
            "achievements_count": len(achievements),
            "empty": False,
        })
    except Exception:
        return jsonify(empty)
