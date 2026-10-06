"""Standings screen: league standings grouped by conference."""
from flask import Blueprint, jsonify, render_template
from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("standings", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _standings_payload(live):
    gm = _resolve_gm(live)
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


# ------------------------------------------------------------------
# Batch C (League): standings view modes + team analytics + division
# analysis + divisions grid. Ported from stats_standings_window.py
# (view modes at ~462/504-554/2689, team analytics ~504, division
# analysis ~1512, divisions grid ~1541).
# ------------------------------------------------------------------

_STANDINGS_VIEWS = [
    "League Overview", "Eastern Conference", "Western Conference",
    "Wild Card Race", "Division Leaders", "Playoff Picture",
]


def _rich_team_rows(live):
    """One row per NHL team with points, GF/GA/diff, streak, conf/div.

    Mirrors StatsStandingsView's enhanced standings table data.
    """
    gm = _resolve_gm(live)
    league = _safe(lambda: gm.league)
    if league is None:
        return [], None
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
            gf = _safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0)
            ga = _safe(lambda: int(getattr(t, "goals_against", 0) or 0), 0)
            gp = w + l + otl
            conf = _safe(lambda: t.conference, "") or ""
            div = _safe(lambda: t.division, "") or ""
            streak = _safe(lambda: getattr(t, "streak", "") or "", "")
            is_user = _safe(lambda: bool(t.is_user_team), False) or \
                (name == user_team_name)
            rows.append({
                "name": name, "division": div, "conf": conf,
                "gp": gp, "w": w, "l": l, "otl": otl, "pts": pts,
                "gf": gf, "ga": ga, "diff": gf - ga,
                "pt_pct": round(pts / (2 * gp), 3) if gp else 0.0,
                "streak": streak,
                "is_user": is_user,
            })
        except Exception:
            continue
    return rows, user_team_name


def _standings_view_teams(rows, view):
    """Filter team rows per the desktop's 6 view modes (line ~2689)."""
    by_points = sorted(rows, key=lambda r: (-r["pts"], -r["w"], r["name"]))
    if view == "Eastern Conference":
        return [r for r in by_points if r["conf"] == "Eastern"]
    if view == "Western Conference":
        return [r for r in by_points if r["conf"] == "Western"]
    if view == "Wild Card Race":
        out = []
        for conf in ("Eastern", "Western"):
            conf_teams = [r for r in by_points if r["conf"] == conf]
            out.extend(conf_teams[3:8])  # wild-card bubble: 4th-8th
        return out
    if view == "Division Leaders":
        seen = {}
        for r in by_points:
            div = r["division"] or "Unknown"
            if div not in seen:
                seen[div] = r
        return [seen[d] for d in sorted(seen)]
    if view == "Playoff Picture":
        out = []
        for conf in ("Eastern", "Western"):
            conf_teams = [r for r in by_points if r["conf"] == conf]
            out.extend(conf_teams[:8])
        return out
    return by_points  # League Overview


def _apply_standings_sort(rows, sort):
    if sort == "Wins":
        return sorted(rows, key=lambda r: (-r["w"], -r["pts"], r["name"]))
    if sort == "Goal Differential":
        return sorted(rows, key=lambda r: (-r["diff"], -r["pts"], r["name"]))
    return sorted(rows, key=lambda r: (-r["pts"], -r["w"], r["name"]))


@bp.route("/api/standings/views")
def api_standings_views():
    """Enhanced standings: 6 view modes, sort modes, advanced metrics.

    Query params: view (one of _STANDINGS_VIEWS), sort
    (Points|Wins|Goal Differential), advanced (0/1).
    """
    live = _live()
    if live is None:
        return jsonify({"views": _STANDINGS_VIEWS, "view": "League Overview",
                        "rows": [], "user_team": None})
    from flask import request as _req
    view = _req.args.get("view", "League Overview")
    if view not in _STANDINGS_VIEWS:
        view = "League Overview"
    sort = _req.args.get("sort", "Points")
    advanced = _req.args.get("advanced", "1") != "0"
    try:
        rows, user_team = _rich_team_rows(live)
        rows = _standings_view_teams(rows, view)
        rows = _apply_standings_sort(rows, sort)
        # Playoff-cutoff marker: annotate rows inside/outside the line
        # for the race views (desktop marks the playoff line).
        cutoff = None
        if view in ("Wild Card Race", "Playoff Picture"):
            cutoff = 2 if view == "Wild Card Race" else 8
        return jsonify({
            "views": _STANDINGS_VIEWS,
            "view": view, "sort": sort, "advanced": advanced,
            "cutoff": cutoff,
            "rows": rows, "user_team": user_team,
        })
    except Exception:
        return jsonify({"views": _STANDINGS_VIEWS, "view": view,
                        "rows": [], "user_team": None})


# --- Team Analytics ---------------------------------------------------

_TEAM_ANALYTICS_CATS = [
    "Overall Performance", "Offensive Stats", "Defensive Stats",
    "Goaltending", "Advanced Analytics",
]


def _team_analytics_rows(live, category):
    """Category table for Team Analytics tab (desktop ~2781-3015).

    All from real team attributes; no fabricated rates.
    """
    rows, user_team = _rich_team_rows(live)
    gm = _resolve_gm(live)
    league = _safe(lambda: gm.league)
    teams_by_name = {}
    if league is not None:
        for t in (_safe(lambda: list(league.teams), []) or []):
            n = _safe(lambda: t.team_name, "")
            if n:
                teams_by_name[n] = t

    def _pp_pk(tname):
        t = teams_by_name.get(tname)
        pp = _safe(lambda: float(getattr(t, "power_play_pct", 0) or 0), 0)
        pk = _safe(lambda: float(getattr(t, "penalty_kill_pct", 0) or 0), 0)
        return pp, pk

    out = []
    for r in rows:
        t = teams_by_name.get(r["name"])
        gp = max(1, r["gp"])
        pp, pk = _pp_pk(r["name"])
        gaa_team = _safe(lambda: float(getattr(t, "team_gaa", 0) or 0), 0)
        svp_team = _safe(lambda: float(getattr(t, "team_save_pct", 0) or 0), 0)
        row = {
            "name": r["name"], "division": r["division"], "conf": r["conf"],
            "gp": r["gp"], "w": r["w"], "l": r["l"], "otl": r["otl"],
            "pts": r["pts"], "is_user": r["is_user"],
            "gf": r["gf"], "ga": r["ga"], "diff": r["diff"],
            "gf_gp": round(r["gf"] / gp, 2),
            "ga_gp": round(r["ga"] / gp, 2),
            "pp_pct": round(pp, 1), "pk_pct": round(pk, 1),
            "team_gaa": round(gaa_team, 2), "team_sv_pct": round(svp_team, 3),
        }
        # Advanced: goal-share + pythagorean expectation (desktop's
        # "Advanced Analytics" category is expected-points territory).
        gf, ga = r["gf"], r["ga"]
        row["goal_share"] = round(gf / (gf + ga) * 100, 1) if (gf + ga) else 0.0
        exp = (gf ** 2) / ((gf ** 2) + (ga ** 2)) if (gf or ga) else 0.5
        row["pythag_pts"] = round(exp * 2 * r["gp"], 1)
        out.append(row)

    # League averages for the "vs League Average" comparison mode.
    avgs = {}
    if out:
        for k in ("gf_gp", "ga_gp", "pp_pct", "pk_pct", "goal_share"):
            avgs[k] = round(sum(r[k] for r in out) / len(out), 2)

    if category == "Offensive Stats":
        out.sort(key=lambda r: (-r["gf_gp"], -r["gf"]))
    elif category == "Defensive Stats":
        out.sort(key=lambda r: (r["ga_gp"], r["ga"]))
    elif category == "Goaltending":
        out.sort(key=lambda r: (-r["team_sv_pct"], r["team_gaa"]))
    elif category == "Advanced Analytics":
        out.sort(key=lambda r: (-r["goal_share"], -r["diff"]))
    else:
        out.sort(key=lambda r: (-r["pts"], -r["w"]))
    return out, avgs, user_team


@bp.route("/api/standings/team-analytics")
def api_standings_team_analytics():
    """Team Analytics tab: category + view-mode (rankings vs average)."""
    live = _live()
    if live is None:
        return jsonify({"categories": _TEAM_ANALYTICS_CATS, "rows": [],
                        "averages": {}, "user_team": None})
    from flask import request as _req
    category = _req.args.get("category", "Overall Performance")
    if category not in _TEAM_ANALYTICS_CATS:
        category = "Overall Performance"
    mode = _req.args.get("mode", "League Rankings")
    team_filter = _req.args.get("team_filter", "All Teams")
    try:
        rows, avgs, user_team = _team_analytics_rows(live, category)
        if team_filter in ("Eastern Conference", "Western Conference"):
            rows = [r for r in rows if r["conf"] == team_filter]
        elif team_filter == "Division Rivals" and user_team:
            udiv = next((r["division"] for r in rows
                         if r["name"] == user_team), "")
            rows = [r for r in rows if r["division"] == udiv]
        elif team_filter == "Playoff Teams":
            # top 8 per conference by points
            keep = set()
            for conf in ("Eastern", "Western"):
                cr = sorted([r for r in rows if r["conf"] == conf],
                            key=lambda r: (-r["pts"], -r["w"]))[:8]
                keep.update(r["name"] for r in cr)
            rows = [r for r in rows if r["name"] in keep]
        return jsonify({
            "categories": _TEAM_ANALYTICS_CATS,
            "category": category, "mode": mode, "team_filter": team_filter,
            "rows": rows, "averages": avgs, "user_team": user_team,
        })
    except Exception:
        return jsonify({"categories": _TEAM_ANALYTICS_CATS, "rows": [],
                        "averages": {}, "user_team": None})


# --- Division Analysis + Divisions grid --------------------------------

_DIVISION_ANALYSIS_TYPES = [
    "Standings", "Head-to-Head", "Strength of Schedule", "Division vs League",
]


@bp.route("/api/standings/division-analysis")
def api_standings_division_analysis():
    """Division Analysis tab: per-division deep dive.

    Query: division (name or "All Divisions"), analysis (one of
    _DIVISION_ANALYSIS_TYPES).
    """
    live = _live()
    if live is None:
        return jsonify({"divisions": [], "rows": [], "analysis": "Standings"})
    from flask import request as _req
    analysis = _req.args.get("analysis", "Standings")
    if analysis not in _DIVISION_ANALYSIS_TYPES:
        analysis = "Standings"
    try:
        rows, user_team = _rich_team_rows(live)
        divisions = sorted({r["division"] for r in rows if r["division"]})
        division = _req.args.get("division", "All Divisions")
        if division != "All Divisions" and division not in divisions:
            division = "All Divisions"

        div_rows = [r for r in rows
                    if division == "All Divisions" or r["division"] == division]
        div_rows.sort(key=lambda r: (-r["pts"], -r["w"], r["name"]))

        payload = {
            "divisions": divisions, "division": division,
            "analysis": analysis, "user_team": user_team,
            "rows": div_rows,
        }
        if analysis == "Division vs League":
            # Per-division aggregates vs league averages.
            divs = {}
            for r in rows:
                d = divs.setdefault(r["division"] or "Unknown",
                                    {"teams": 0, "pts": 0, "gf": 0, "ga": 0})
                d["teams"] += 1
                d["pts"] += r["pts"]; d["gf"] += r["gf"]; d["ga"] += r["ga"]
            lg_gp = sum(r["gp"] for r in rows) or 1
            lg_pts = sum(r["pts"] for r in rows)
            payload["division_compare"] = [
                {"division": d,
                 "teams": v["teams"],
                 "avg_pts": round(v["pts"] / v["teams"], 1),
                 "avg_gf": round(v["gf"] / v["teams"], 1),
                 "avg_ga": round(v["ga"] / v["teams"], 1),
                 "goal_share": round(v["gf"] / (v["gf"] + v["ga"]) * 100, 1)
                 if (v["gf"] + v["ga"]) else 0.0}
                for d, v in sorted(divs.items())
            ]
            payload["league_avg_pts_per_game"] = round(
                lg_pts / lg_gp, 2)
        elif analysis == "Strength of Schedule":
            # Remaining-schedule difficulty from opponent point pct.
            gm = _resolve_gm(live)
            league = _safe(lambda: gm.league)
            sched = _safe(lambda: list(getattr(league, "schedule", None)
                                       or []), []) or []
            pct = {r["name"]: r["pt_pct"] for r in rows}
            rem = {}
            for g in sched:
                try:
                    if not isinstance(g, dict):
                        continue
                    home = _safe(lambda: str(g.get("home_team", "") or ""), "")
                    away = _safe(lambda: str(g.get("away_team", "") or ""), "")
                    if g.get("played"):
                        continue
                    for me, opp in ((home, away), (away, home)):
                        if me:
                            rem.setdefault(me, []).append(pct.get(opp, 0.5))
                except Exception:
                    continue
            payload["sos"] = [
                {"name": r["name"], "division": r["division"],
                 "games_left": len(rem.get(r["name"], [])),
                 "opp_pt_pct": round(
                     sum(rem.get(r["name"], [])) /
                     max(1, len(rem.get(r["name"], []))), 3)}
                for r in div_rows
            ]
        elif analysis == "Head-to-Head":
            payload["note"] = ("Head-to-head records are not tracked by the "
                               "sim engine; showing intra-division goal "
                               "differential instead.")
        return jsonify(payload)
    except Exception:
        return jsonify({"divisions": [], "rows": [],
                        "analysis": analysis})


@bp.route("/api/standings/divisions-grid")
def api_standings_divisions_grid():
    """Divisions grid tab: all divisions side by side (desktop ~1541)."""
    live = _live()
    if live is None:
        return jsonify({"divisions": [], "user_team": None})
    try:
        rows, user_team = _rich_team_rows(live)
        grid = {}
        for r in sorted(rows, key=lambda r: (-r["pts"], -r["w"], r["name"])):
            grid.setdefault(r["division"] or "Unknown", []).append(r)
        return jsonify({
            "divisions": [{"name": d, "rows": rs}
                          for d, rs in sorted(grid.items())],
            "user_team": user_team,
        })
    except Exception:
        return jsonify({"divisions": [], "user_team": None})
