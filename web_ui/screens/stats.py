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
