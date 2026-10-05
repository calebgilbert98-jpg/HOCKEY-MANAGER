"""Team overview screen: quick at-a-glance page for any league team.

Header: team name, record, division/conference rank, streak.
Sections: team leaders (points/goals/assists), recent form, roster list
(linking to player profiles).

All data computed server-side in /api/team/<name>, rendered by team.js.
Every read defensive: missing data degrades gracefully, never 500s.
"""
from flask import Blueprint, jsonify, render_template
from urllib.parse import unquote

bp = Blueprint("team", __name__)


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _find_team(name):
    """Find a Team object by team_name (URL-decoded)."""
    live = _live()
    if live is None:
        return None
    name = unquote(name).strip().lower()
    league = _safe(lambda: getattr(live, "league", None))
    teams = _safe(lambda: list(getattr(league, "teams", []) or []), []) or []
    user_team = _safe(lambda: getattr(live, "user_team", None))
    if user_team is not None and all(t is not user_team for t in teams):
        teams = [user_team] + teams
    for t in teams:
        tn = _safe(lambda: str(getattr(t, "team_name", "")).strip().lower(), "")
        if tn == name:
            return t
    return None


def _team_payload(t):
    from web_ui.bridge import to_web_player, player_portrait, _safe as _bsafe
    live = _live()
    league = _safe(lambda: getattr(live, "league", None))
    user_team = _safe(lambda: getattr(live, "user_team", None))

    name = _safe(lambda: getattr(t, "team_name", "?"), "?")
    w = _safe(lambda: int(getattr(t, "wins", 0) or 0), 0)
    l = _safe(lambda: int(getattr(t, "losses", 0) or 0), 0)
    otl = _safe(lambda: int(getattr(t, "otl", 0) or getattr(t, "overtime_losses", 0) or 0), 0)
    pts = w * 2 + otl
    gp = w + l + otl

    # Division rank
    division = _safe(lambda: getattr(t, "division", ""), "")
    div_rank = None
    standings = _safe(lambda: list(getattr(league, "standings", []) or []), []) or []
    if standings and division:
        div_teams = []
        for s in standings:
            try:
                st = s.get("team") if isinstance(s, dict) else s
                if _safe(lambda: getattr(st, "division", ""), "") == division:
                    sw = _safe(lambda: int(getattr(st, "wins", 0) or 0), 0)
                    so = _safe(lambda: int(getattr(st, "otl", 0) or getattr(st, "overtime_losses", 0) or 0), 0)
                    div_teams.append((_safe(lambda: getattr(st, "team_name", ""), ""), sw * 2 + so))
            except Exception:
                continue
        div_teams.sort(key=lambda x: -x[1])
        for i, (tn, _) in enumerate(div_teams):
            if tn == name:
                div_rank = i + 1
                break

    # Roster + leaders
    roster = _safe(lambda: list(getattr(t, "roster", []) or []), []) or []
    skaters = [p for p in roster if _safe(lambda: getattr(p, "primary_position", "").upper(), "") != "G"]
    def _pts(p):
        return _safe(lambda: int(getattr(p, "points", 0) or 0), 0)
    def _g(p):
        return _safe(lambda: int(getattr(p, "goals", 0) or 0), 0)
    def _a(p):
        return _safe(lambda: int(getattr(p, "assists", 0) or 0), 0)
    by_pts = sorted(skaters, key=lambda p: (-_pts(p), -_g(p)))[:5]
    leaders = []
    for p in by_pts:
        pid = _safe(lambda: str(getattr(p, "id", "")), "")
        leaders.append({
            "id": pid,
            "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
            "position": _safe(lambda: getattr(p, "primary_position", ""), ""),
            "gp": _safe(lambda: int(getattr(p, "games_played", 0) or 0), 0),
            "g": _g(p), "a": _a(p), "pts": _pts(p),
            "portrait": player_portrait(pid) if pid else None,
        })

    # Recent form: last 5 completed games involving this team
    sched = _safe(lambda: list(getattr(league, "schedule", []) or []), []) or []
    form = []
    for g in reversed(sched):
        try:
            if not isinstance(g, dict):
                continue
            hs = g.get("home_score")
            if hs is None:
                continue
            hn = _safe(lambda: str(getattr(g.get("home_team"), "team_name", g.get("home_team", ""))), "")
            an = _safe(lambda: str(getattr(g.get("away_team"), "team_name", g.get("away_team", ""))), "")
            if name not in (hn, an):
                continue
            aws = g.get("away_score", 0) or 0
            mine = hs if hn == name else aws
            theirs = aws if hn == name else hs
            res = "W" if mine > theirs else ("OTL" if abs(mine - theirs) == 1 else "L")
            form.append({"res": res, "score": f"{mine}-{theirs}",
                         "opp": an if hn == name else hn,
                         "vs": "vs" if hn == name else "@"})
            if len(form) >= 5:
                break
        except Exception:
            continue

    # Streak
    streak, n = "", 0
    for f in form:
        r = "W" if f["res"] == "W" else "L"
        if not streak:
            streak, n = r, 1
        elif r == streak:
            n += 1
        else:
            break
    streak_txt = f"{streak}{n}" if streak else "—"

    # Roster list (lightweight)
    players = []
    for p in roster:
        try:
            pid = _safe(lambda: str(getattr(p, "id", "")), "")
            players.append({
                "id": pid,
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": _safe(lambda: getattr(p, "primary_position", ""), ""),
                "overall": _safe(lambda: int(getattr(p, "overall", 0) or 0), 0),
                "portrait": player_portrait(pid) if pid else None,
            })
        except Exception:
            continue
    players.sort(key=lambda x: (-x["overall"], x["name"]))

    return {
        "name": name,
        "is_user": t is user_team,
        "division": division,
        "conference": _safe(lambda: getattr(t, "conference", ""), ""),
        "record": {"w": w, "l": l, "otl": otl, "pts": pts, "gp": gp},
        "div_rank": div_rank,
        "streak": streak_txt,
        "cap_space": _safe(lambda: int(getattr(t, "cap_space", 0) or 0), 0),
        "leaders": leaders,
        "form": form,
        "players": players,
        "player_count": len(players),
    }


@bp.route("/team/<path:name>")
def team_page(name):
    return render_template("team.html", team_name=name)


@bp.route("/api/team/<path:name>")
def api_team(name):
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    t = _find_team(name)
    if t is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_team_payload(t))
