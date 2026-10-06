"""Player comparison screen: side-by-side comparison of 2-4 players.

Routes:
  /compare                 - page (prefill via ?p1=<id>&p2=<id>&p3=&p4=)
  /api/compare?ids=a,b,c   - comparison data (max 4 players)
  /api/compare/search?q=   - player search for the add-player slots

Reuses attribute field lists and helpers from screens/player.py, and
_player_ovr / player_portrait from web_ui.bridge. All reads defensive.
"""
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("compare", __name__)

MAX_PLAYERS = 4


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M".rstrip("0").rstrip(".")
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v}" if v else "--"


def _player_payload(pid):
    """Full comparison payload for one player id, or None if not found."""
    from web_ui.screens.player import (
        _find_player, _is_goalie, _to100,
        _SKATER_TECHNICAL, _SKATER_MENTAL, _SKATER_PHYSICAL,
        _GOALIE_TECHNICAL, _GOALIE_MENTAL, _GOALIE_PHYSICAL,
    )
    from web_ui.bridge import _player_ovr, player_portrait, _resolve_gm

    p, team, list_name = _find_player(pid)
    if p is None:
        return None
    goalie = _is_goalie(p)
    pid_s = str(_safe(lambda: getattr(p, "id", ""), "") or pid)
    name = _safe(lambda: f"{p.first_name} {p.last_name}",
                 str(_safe(lambda: getattr(p, "full_name", "?"), "?")))
    team_name = (_safe(lambda: getattr(team, "team_name", None))
                 or str(_safe(lambda: getattr(p, "team_name", ""), "") or "")
                 or "Free Agent")

    # --- season stats ---
    st = _safe(lambda: getattr(p, "stats", None))
    if goalie:
        sv = _safe(lambda: float(getattr(st, "save_percentage", 0) or 0), 0.0)
        gaa = _safe(lambda: float(getattr(st, "goals_against_avg", 0) or 0), 0.0)
        stats = [
            {"key": "GP", "label": "Games Played", "value": _safe(lambda: int(getattr(st, "games_played", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "W", "label": "Wins", "value": _safe(lambda: int(getattr(st, "wins", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "SV%", "label": "Save %", "value": f"{sv:.3f}", "numval": sv, "num": True, "higher_better": True},
            {"key": "GAA", "label": "Goals Against Avg", "value": f"{gaa:.2f}", "numval": gaa, "num": True, "higher_better": False},
            {"key": "SO", "label": "Shutouts", "value": _safe(lambda: int(getattr(st, "shutouts", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "SA", "label": "Shots Against", "value": _safe(lambda: int(getattr(st, "shots_against", 0) or 0), 0), "num": True, "higher_better": True},
        ]
    else:
        g = _safe(lambda: int(getattr(st, "goals", 0) or 0), 0)
        a = _safe(lambda: int(getattr(st, "assists", 0) or 0), 0)
        stats = [
            {"key": "GP", "label": "Games Played", "value": _safe(lambda: int(getattr(st, "games_played", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "G", "label": "Goals", "value": g, "num": True, "higher_better": True},
            {"key": "A", "label": "Assists", "value": a, "num": True, "higher_better": True},
            {"key": "PTS", "label": "Points", "value": g + a, "num": True, "higher_better": True},
            {"key": "+/-", "label": "Plus/Minus", "value": _safe(lambda: int(getattr(p, "plus_minus", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "PIM", "label": "Penalty Minutes", "value": _safe(lambda: int(getattr(st, "penalties_in_minutes", 0) or 0), 0), "num": True, "higher_better": False},
            {"key": "HIT", "label": "Hits", "value": _safe(lambda: int(getattr(st, "hits", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "BLK", "label": "Blocked Shots", "value": _safe(lambda: int(getattr(st, "blocked_shots", 0) or 0), 0), "num": True, "higher_better": True},
            {"key": "SOG", "label": "Shots on Goal", "value": _safe(lambda: int(getattr(st, "shots", 0) or 0), 0), "num": True, "higher_better": True},
        ]

    # --- contract ---
    c = _safe(lambda: getattr(p, "contract", None))
    sal = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0) if c is not None else 0
    yrs = _safe(lambda: getattr(c, "years_remaining", None), None) if c is not None else None
    contract = [
        {"key": "CAPHIT", "label": "Cap Hit", "value": _fmt_money(sal) if sal else "--",
         "numval": sal, "num": True, "higher_better": False},
        {"key": "TERM", "label": "Term Remaining",
         "value": f"{yrs} yr{'s' if yrs != 1 else ''}" if yrs is not None else "--",
         "numval": yrs if yrs is not None else -1, "num": True, "higher_better": False},
    ]

    # --- attribute groups ---
    lists = ([("Technical", _GOALIE_TECHNICAL),
              ("Mental", _GOALIE_MENTAL),
              ("Physical", _GOALIE_PHYSICAL)] if goalie else
             [("Technical", _SKATER_TECHNICAL),
              ("Mental", _SKATER_MENTAL),
              ("Physical", _SKATER_PHYSICAL)])
    attr_groups = []
    for gname, fields in lists:
        rows = []
        for label, field in fields:
            val = _safe(lambda: getattr(p, field, None))
            if val is None and field in ("offensive_positioning",
                                         "defensive_positioning"):
                val = _safe(lambda: getattr(p, "positioning", None))
            if val is None:
                continue
            v100 = _to100(val)
            rows.append({"label": label, "value": v100, "num": True,
                         "higher_better": True, "bar": True})
        attr_groups.append({"name": gname, "rows": rows})

    pos = _safe(lambda: str(getattr(p, "primary_position", "") or ""), "")
    return {
        "id": pid_s,
        "name": name,
        "team": team_name,
        "position": pos,
        "pos_class": "G" if goalie else ("D" if "DEFENSE" in pos.upper() else "F"),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
        "overall": _player_ovr(p),
        "portrait": player_portrait(pid_s),
        "is_goalie": goalie,
        "stats": stats,
        "contract": contract,
        "attr_groups": attr_groups,
    }


@bp.route("/compare")
def compare_page():
    return render_template("compare.html")


@bp.route("/api/compare")
def api_compare():
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    raw = request.args.get("ids", "") or ""
    ids = [i.strip() for i in raw.split(",") if i.strip()][:MAX_PLAYERS]
    # also accept p1..p4 style params
    if not ids:
        for k in ("p1", "p2", "p3", "p4"):
            v = (request.args.get(k) or "").strip()
            if v:
                ids.append(v)
        ids = ids[:MAX_PLAYERS]
    # dedupe, preserve order
    seen_ids = set()
    ids = [i for i in ids if not (i in seen_ids or seen_ids.add(i))]
    players = []
    missing = []
    for pid in ids:
        try:
            payload = _player_payload(pid)
        except Exception:
            payload = None
        if payload is None:
            missing.append(pid)
        else:
            players.append(payload)
    return jsonify({"players": players, "missing": missing})


@bp.route("/api/compare/search")
def api_compare_search():
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    from web_ui.bridge import _player_ovr, player_portrait, _resolve_gm
    q = (request.args.get("q", "") or "").strip().lower()
    if len(q) < 2:
        return jsonify({"results": []})
    gm = _safe(lambda: getattr(live, "game_manager", None))
    league = (_safe(lambda: getattr(gm, "league", None))
              or _safe(lambda: getattr(live, "league", None)))
    teams = _safe(lambda: list(getattr(league, "teams", []) or []), []) or []
    user_team = (_safe(lambda: getattr(gm, "user_team", None))
                 or _safe(lambda: getattr(live, "user_team", None)))
    if user_team is not None and all(t is not user_team for t in teams):
        teams = [user_team] + teams
    results = []
    seen = set()
    for team in teams:
        tname = _safe(lambda: str(getattr(team, "team_name", "")), "")
        for lname in ("roster", "ahl_roster", "prospects"):
            lst = _safe(lambda: list(getattr(team, lname, []) or []), []) or []
            for p in lst:
                try:
                    pid = str(_safe(lambda: getattr(p, "id", ""), ""))
                    if not pid or pid in seen:
                        continue
                    name = _safe(lambda: getattr(p, "full_name", ""), "") or ""
                    if q not in name.lower():
                        continue
                    seen.add(pid)
                    results.append({
                        "id": pid,
                        "name": name,
                        "team": tname,
                        "position": _safe(lambda: str(getattr(p, "primary_position", "") or ""), ""),
                        "overall": _player_ovr(p),
                        "portrait": player_portrait(pid),
                    })
                    if len(results) >= 15:
                        return jsonify({"results": results})
                except Exception:
                    continue
    return jsonify({"results": results})
