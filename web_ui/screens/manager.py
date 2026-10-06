"""Manager Hub — the GM dashboard.

Ports the substance of manager_hub_window.py (Board, Press, Profile),
main.py's season-goals window (season_goals.py), gm_relationships_window.py
(reputation_system.py), and the team analytics summary (analytics_hub.py).

Sections:
  - Board: confidence, job status, season expectation + pace verdict,
    owner meeting, consequences.
  - Season goals: per-player goals from season_goals.py with progress bars
    and on-track / at-risk / behind / hit status, plus set/clear APIs.
  - Team analytics: dense at-a-glance cards from the team's recorded
    analytics games (xG for/against, finishing, chance quality, lines,
    entries, momentum) — all already-computed, no sims run.
  - GM relationships: real relationship standings from reputation_system
    (stature, respect, tier, heat, trend) with per-GM detail.
  - Profile: manager bio + career record. Press: conference history.

Every read is defensive: missing data degrades to empty-state payloads,
never 500s. Game attachment is via _web_app_ref (no game attached ->
the page still renders; APIs return empty-state payloads).
"""
from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("manager", __name__)


def _live():
    from web_ui.bridge import _web_app_ref, _resolve_gm
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _gm():
    live = _live()
    return _resolve_gm(live) if live is not None else None


def _league(gm):
    if gm is None:
        return None
    return _safe(lambda: getattr(gm, "league", None))


def _user_team(gm):
    live = _live()
    if gm is not None:
        t = _safe(lambda: getattr(gm, "user_team", None))
        if t is not None:
            return t
    if live is not None:
        return _safe(lambda: getattr(live, "user_team", None))
    return None


def _career():
    live = _live()
    if live is None:
        return None
    return _safe(lambda: getattr(live, "career", None))


def _require_game():
    live = _live()
    if live is None:
        return None, jsonify({"error": "no game"}), 503
    gm = _gm()
    team = _user_team(gm)
    if team is None:
        return None, jsonify({"error": "no user team"}), 503
    return team, None, None


# --------------------------------------------------------------------------
# Board
# --------------------------------------------------------------------------

# Rough full-season point targets per expectation (estimates, labeled as
# such — ported from manager_hub_window.ManagerHubView._EXPECTATION_TARGETS).
_EXPECTATION_TARGETS = {
    "win_cup": (108, "roughly 108+ points — a top seed and a full Cup run"),
    "contend": (100, "roughly 100+ points — a top-four seed for a deep run"),
    "playoffs": (94, "roughly 94+ points — the usual playoff cutoff range"),
    "rebuild": (None, "no points target — player development is the goal"),
}


def _expectation_payload():
    import manager_career as mc
    career = _career()
    live = _live()
    gm = _gm()
    league = _league(gm)
    out = {"available": False}
    if career is None:
        return out
    board = _safe(lambda: getattr(career, "board", None))
    if board is None:
        return out
    today = ""
    if live is not None:
        cd = _safe(lambda: getattr(live, "current_date", None))
        if cd is not None and hasattr(cd, "isoformat"):
            today = cd.isoformat()

    expectations = [
        {"key": k, "label": v["label"], "description": v["description"]}
        for k, v in mc.EXPECTATIONS.items()
    ]
    exp = _safe(lambda: getattr(board, "expectation", None)) or "playoffs"
    exp_info = mc.EXPECTATIONS.get(exp, mc.EXPECTATIONS["playoffs"])

    w = _safe(lambda: int(getattr(board, "season_wins", 0) or 0), 0)
    l = _safe(lambda: int(getattr(board, "season_losses", 0) or 0), 0)
    otl = _safe(lambda: int(getattr(board, "season_otl", 0) or 0), 0)
    gp = w + l + otl
    pts = w * 2 + otl
    slate = _safe(lambda: int(getattr(league, "season_games_count", 82) or 82), 82)
    target, note = _EXPECTATION_TARGETS.get(exp, (94, ""))

    pace = round(pts / gp * slate, 1) if gp else None
    if gp == 0:
        verdict, gap = "preseason", None
    elif target is None:
        verdict, gap = "rebuild", None
    else:
        gap = round(pace - target, 1)
        verdict = ("on_track" if gap >= -2
                   else "within_reach" if gap >= -8
                   else "off_the_pace")

    out.update({
        "available": True,
        "confidence": _safe(lambda: int(getattr(board, "confidence", 60) or 0), 60),
        "job_status": _safe(lambda: str(getattr(board, "job_status", "Stable")), "Stable"),
        "sacked": bool(_safe(lambda: getattr(board, "sacked", False), False)),
        "expectation": exp,
        "expectation_label": exp_info["label"],
        "expectation_description": exp_info["description"],
        "expectations": expectations,
        "record": {"w": w, "l": l, "otl": otl, "pts": pts, "gp": gp,
                   "slate": slate, "pace": pace},
        "verdict": verdict,
        "verdict_gap": gap,
        "target_note": note,
        "last_review": _safe(lambda: str(getattr(board, "last_review", "") or ""), ""),
        "patience_status": _safe(lambda: str(board.patience_status(today)), ""),
        "owner_archetype": _safe(lambda: str(
            getattr(getattr(board, "owner", None), "archetype", "")), ""),
        "consequences": _safe(lambda: list(board.current_consequences()), []) or [],
        "cutoff_pace": _playoff_cutoff_pace(league, slate),
    })
    return out


def _playoff_cutoff_pace(league, slate):
    """Approximate full-slate pace of the 16th-place team, or None.

    Ported from manager_hub_window.ManagerHubView._playoff_cutoff_pace.
    """
    try:
        if league is None:
            return None
        gm = _gm()
        standings = (_safe(lambda: getattr(league, "standings", None))
                     or _safe(lambda: getattr(gm, "standings", None)))
        if not standings or len(standings) < 16:
            return None
        paces = []
        for s in standings.values():
            g = s.get("W", 0) + s.get("L", 0) + s.get("OTL", 0)
            if g > 0:
                paces.append(s.get("Points", 0) / g * slate)
        if len(paces) < 16:
            return None
        return round(sorted(paces, reverse=True)[15], 0)
    except Exception:
        return None


# --------------------------------------------------------------------------
# Season goals (season_goals.py — per-player targets)
# --------------------------------------------------------------------------

def _goals_payload():
    import season_goals as sg
    team, err, code = _require_game()
    if err:
        return {"available": False, "goals": [], "players": []}
    career = _career()
    board = _safe(lambda: getattr(career, "board", None)) if career else None
    w = _safe(lambda: int(getattr(board, "season_wins", 0) or 0), 0)
    l = _safe(lambda: int(getattr(board, "season_losses", 0) or 0), 0)
    otl = _safe(lambda: int(getattr(board, "season_otl", 0) or 0), 0)
    gp = w + l + otl
    gm = _gm()
    league = _league(gm)
    slate = _safe(lambda: int(getattr(league, "season_games_count", 82) or 82), 82)
    expected_pct = (gp / slate * 100) if gp and slate else 0

    roster = _safe(lambda: list(getattr(team, "roster", []) or []), []) or []
    goals, players = [], []
    for p in roster:
        pid = _safe(lambda: str(getattr(p, "id", "")), "")
        name = _safe(lambda: getattr(p, "full_name", "?"), "?")
        prog = _safe(lambda: sg.goal_progress(p))
        if prog:
            pct = prog.get("pct", 0) or 0
            if prog.get("hit"):
                status = "hit"
            elif not gp:
                status = "preseason"
            elif pct >= expected_pct * 0.9:
                status = "on_track"
            elif pct >= expected_pct * 0.5:
                status = "at_risk"
            else:
                status = "behind"
            _, _, _, reward_attrs = sg.ALL_GOAL_TYPES.get(
                prog["type"], (None, None, None, []))
            goals.append({
                "player_id": pid,
                "name": name,
                "type": prog["type"],
                "label": prog["label"],
                "target": prog["target"],
                "current": prog["current"],
                "pct": pct,
                "hit": bool(prog["hit"]),
                "status": status,
                "expected_pct": round(expected_pct, 1),
                "set_date": str(_safe(
                    lambda: (sg.get_season_goal(p) or {}).get("set_date", ""), "")),
                "reward_attrs": list(reward_attrs or []),
            })
        else:
            pos = _safe(lambda: str(getattr(p, "primary_position", "")), "")
            players.append({"id": pid, "name": name, "position": pos})
    players.sort(key=lambda x: x["name"])
    goals.sort(key=lambda g: (g["status"] != "hit", -g["pct"]))
    return {
        "available": True,
        "goals": goals,
        "players_without_goals": players,
        "goal_types": [
            {"key": k, "label": v[1]}
            for k, v in sorted(sg.SKATER_GOALS.items(),
                               key=lambda kv: kv[1][1])
        ],
        "goalie_goal_types": [
            {"key": k, "label": v[1]}
            for k, v in sorted(sg.GOALIE_GOALS.items(),
                               key=lambda kv: kv[1][1])
        ],
        "games_played": gp,
        "slate": slate,
    }


# --------------------------------------------------------------------------
# Team analytics summary (analytics_hub.py — already-computed records)
# --------------------------------------------------------------------------

def _analytics_hub():
    """Import analytics_hub, or None.

    analytics_hub's only hard GUI dependency is the Tk view class at the
    bottom of the file; all the aggregation functions we use are pure.
    If customtkinter is unavailable (headless env), stub it so the module
    still imports.
    """
    try:
        import analytics_hub as ah
        return ah
    except Exception:
        pass
    try:
        import sys
        import types
        stub = types.ModuleType("customtkinter")
        stub.CTkFrame = object
        sys.modules.setdefault("customtkinter", stub)
        sys.modules.pop("analytics_hub", None)
        import analytics_hub as ah
        return ah
    except Exception:
        return None


def _analytics_payload():
    team, err, code = _require_game()
    if err:
        return {"available": False, "message": "No game attached."}
    ah = _analytics_hub()
    if ah is None:
        return {"available": False, "message": "Analytics module unavailable."}
    name = _safe(lambda: str(getattr(team, "team_name", "")), "")
    games = _safe(lambda: ah.team_games(team), []) or []
    recent = games[-5:]
    if not recent:
        return {"available": False,
                "message": "Play a game and the analyst will have something "
                           "to work with."}

    per_game, all_shots, all_opp_shots, all_entries = [], [], [], []
    for rec in recent:
        shots = _safe(lambda: ah.shots_for(rec, name), []) or []
        try:
            home, away = str(rec.get("home", "")), str(rec.get("away", ""))
            opp = away if name == home else home
        except Exception:
            opp = ""
        opp_shots = [s for s in (rec.get("shots") or [])
                     if str(s.get("team", "")) == opp]
        xg = round(sum(float(s.get("xg", 0) or 0) for s in shots), 2)
        gf = sum(1 for s in shots if s.get("outcome") == "goal")
        xga = round(sum(float(s.get("xg", 0) or 0) for s in opp_shots), 2)
        per_game.append({
            "label": _safe(lambda: ah.game_label(rec, name), "game"),
            "xg_for": xg,
            "goals_for": gf,
            "xg_against": xga,
            "shots": len(shots),
        })
        all_shots.extend(shots)
        all_opp_shots.extend(opp_shots)
        all_entries.extend(_safe(lambda: ah.entries_for(rec, name), []) or [])

    xg_for = round(sum(g["xg_for"] for g in per_game), 2)
    goals_for = sum(g["goals_for"] for g in per_game)
    xg_against = round(sum(g["xg_against"] for g in per_game), 2)
    n_shots = sum(g["shots"] for g in per_game)
    diff = round(goals_for - xg_for, 2)
    hd = sum(1 for s in all_shots if float(s.get("xg", 0) or 0) >= 0.12)
    eb = _safe(lambda: ah.entry_breakdown(all_entries),
               {"controlled": 0, "total": 0, "controlled_pct": 0.0}) or {}
    lx = []
    latest = recent[-1]
    try:
        lx = ah.line_xg_rows(
            _safe(lambda: ah.shots_for(latest, name), []) or [],
            _safe(lambda: latest.get("lines"), None))
    except Exception:
        lx = []
    shooters = _safe(lambda: ah.player_xg_rows(all_shots), []) or []
    grades = _safe(lambda: ah.grade_xg_rows(all_shots), []) or []
    mpts = _safe(lambda: ah.momentum_points(latest, name), []) or []
    mom = None
    if mpts:
        vals = [p.get("value", 0) for p in mpts]
        mom = {"shifts": len(mpts), "swing": max(vals) - min(vals),
               "latest": vals[-1]}

    return {
        "available": True,
        "team": name,
        "games": per_game,
        "window": len(recent),
        "xg_for": xg_for,
        "goals_for": goals_for,
        "xg_against": xg_against,
        "shots": n_shots,
        "diff": diff,
        "avg_chance_quality": round(xg_for / n_shots, 3) if n_shots else 0.0,
        "high_danger_share": round(hd / n_shots, 3) if n_shots else 0.0,
        "high_danger_count": hd,
        "controlled_entries_pct": eb.get("controlled_pct", 0.0),
        "entries_total": eb.get("total", 0),
        "lines": lx,
        "hot_shooter": shooters[0] if shooters else None,
        "grades": grades,
        "momentum": mom,
    }


# --------------------------------------------------------------------------
# GM relationships (reputation_system.py)
# --------------------------------------------------------------------------

_TREND_ARROW = {"warming": "↑", "cooling": "↓", "steady": "→"}


def _relationships_payload():
    gm = _gm()
    team = _user_team(gm)
    league = _league(gm)
    if team is None:
        return {"available": False, "rows": []}
    try:
        import reputation_system as rs
    except Exception:
        return {"available": False, "rows": []}
    teams = _safe(lambda: list(getattr(league, "teams", []) or []), []) or []
    uid = _safe(lambda: getattr(team, "id", None))
    rows = []
    for t in teams:
        try:
            tid = _safe(lambda: getattr(t, "id", None))
            if (tid is not None and tid == uid) or t is team:
                continue
            stature = _safe(lambda: int(rs.gm_stature(t)), 50)
            respect = _safe(lambda: int(rs.gm_gm_respect(league, team, t)), 50)
            heat = _safe(lambda: int(rs.gm_gm_heat(league, team, t)), 0)
            tier = _safe(lambda: str(rs.respect_tier_label(respect)), "wary")
            trend = _safe(lambda: str(rs.respect_trend(league, team, t)), "steady")
            staff = _safe(lambda: rs._team_gm_staff(t))
            gm_name = _safe(lambda: getattr(staff, "full_name", None)) \
                or _safe(lambda: getattr(staff, "name", None)) \
                or f"{_safe(lambda: getattr(t, 'team_name', 'Unknown'), 'Unknown')} GM"
            rows.append({
                "team": _safe(lambda: str(getattr(t, "team_name", "Unknown")), "Unknown"),
                "team_id": "" if tid is None else str(tid),
                "gm": str(gm_name),
                "stature": stature,
                "respect": respect,
                "tier": tier,
                "heat": heat,
                "trend": trend,
                "arrow": _TREND_ARROW.get(trend, "→"),
            })
        except Exception:
            continue
    rows.sort(key=lambda r: -r["respect"])
    own = {
        "stature": _safe(lambda: int(rs.gm_stature(team)), 50),
        "team": _safe(lambda: str(getattr(team, "team_name", "")), ""),
    }
    return {"available": True, "own": own, "rows": rows}


def _gm_detail_payload(team_key):
    gm = _gm()
    team = _user_team(gm)
    league = _league(gm)
    if team is None:
        return None
    try:
        import reputation_system as rs
    except Exception:
        return None
    key = (team_key or "").strip().lower()
    target = None
    for t in (_safe(lambda: list(getattr(league, "teams", []) or []), []) or []):
        tn = _safe(lambda: str(getattr(t, "team_name", "")).strip().lower(), "")
        tid = _safe(lambda: str(getattr(t, "id", "")), "")
        if tn == key or tid == key:
            target = t
            break
    if target is None:
        return None
    stature = _safe(lambda: int(rs.gm_stature(target)), 50)
    respect = _safe(lambda: int(rs.gm_gm_respect(league, team, target)), 50)
    heat = _safe(lambda: int(rs.gm_gm_heat(league, team, target)), 0)
    tier = _safe(lambda: str(rs.respect_tier_label(respect)), "wary")
    trend = _safe(lambda: str(rs.respect_trend(league, team, target)), "steady")
    baseline = _safe(lambda: float(rs.respect_baseline_for(target)), None)
    staff = _safe(lambda: rs._team_gm_staff(target))
    gm_name = _safe(lambda: getattr(staff, "full_name", None)) \
        or _safe(lambda: getattr(staff, "name", None)) \
        or f"{_safe(lambda: getattr(target, 'team_name', 'Unknown'), 'Unknown')} GM"
    return {
        "team": _safe(lambda: str(getattr(target, "team_name", "Unknown")), "Unknown"),
        "gm": str(gm_name),
        "stature": stature,
        "respect": respect,
        "tier": tier,
        "heat": heat,
        "trend": trend,
        "arrow": _TREND_ARROW.get(trend, "→"),
        "respect_baseline": baseline,
    }


# --------------------------------------------------------------------------
# Profile + press
# --------------------------------------------------------------------------

def _profile_payload():
    career = _career()
    gm = _gm()
    team = _user_team(gm)
    out = {"available": False}
    if career is None:
        return out
    prof = _safe(lambda: getattr(career, "profile", None))
    gmp = _safe(lambda: getattr(team, "gm_profile", None)) if team else None
    board = _safe(lambda: getattr(career, "board", None))
    profile = {}
    if prof is not None:
        profile = {
            "reputation": _safe(lambda: int(getattr(prof, "reputation", 0) or 0), 0),
            "level": _safe(lambda: str(getattr(prof, "level", "")), ""),
            "career_wins": _safe(lambda: int(getattr(prof, "career_wins", 0) or 0), 0),
            "career_losses": _safe(lambda: int(getattr(prof, "career_losses", 0) or 0), 0),
            "career_otl": _safe(lambda: int(getattr(prof, "career_otl", 0) or 0), 0),
            "titles_won": _safe(lambda: int(getattr(prof, "titles_won", 0) or 0), 0),
            "playoff_appearances": _safe(lambda: int(getattr(prof, "playoff_appearances", 0) or 0), 0),
            "seasons_managed": _safe(lambda: int(getattr(prof, "seasons_managed", 0) or 0), 0),
        }
    bio = []
    if gmp is not None:
        for label, attr in (("Age", "age"), ("Birthplace", "birthplace"),
                            ("Nationality", "nationality"),
                            ("Education", "education_level")):
            v = _safe(lambda: getattr(gmp, attr, None))
            if v:
                bio.append(f"{label}: {v}")
        bio.append("")
        for label, attr in (("Style", "management_style"),
                            ("Risk tolerance", "risk_tolerance"),
                            ("Loyalty to players", "loyalty_to_players"),
                            ("Media savvy", "media_savvy")):
            v = _safe(lambda: getattr(gmp, attr, None))
            if v:
                bio.append(f"{label}: {v}")
        if _safe(lambda: getattr(gmp, "former_player", False), False):
            bio.append("")
            bio.append(
                f"Former {_safe(lambda: getattr(gmp, 'playing_position', 'player'), 'player')}: "
                f"{_safe(lambda: getattr(gmp, 'nhl_games_played', 0), 0)} NHL games, "
                f"{_safe(lambda: getattr(gmp, 'career_points', 0), 0)} career points.")
        if _safe(lambda: getattr(gmp, "coaching_experience", False), False):
            bio.append(
                f"{_safe(lambda: getattr(gmp, 'years_coaching', 0), 0)} years coaching experience.")
        if _safe(lambda: getattr(gmp, "assistant_gm_experience", False), False):
            bio.append(
                f"{_safe(lambda: getattr(gmp, 'years_as_assistant', 0), 0)} years as an assistant GM.")
    appt = {}
    if team is not None:
        appt["club"] = _safe(lambda: str(getattr(team, "team_name", "")), "")
    start = _safe(lambda: getattr(career, "career_start_date", ""), "") or ""
    if start:
        appt["since"] = str(start)
    out.update({"available": True, "profile": profile, "bio": bio,
                "appointment": appt,
                "season_record": None if board is None else {
                    "w": _safe(lambda: int(getattr(board, "season_wins", 0) or 0), 0),
                    "l": _safe(lambda: int(getattr(board, "season_losses", 0) or 0), 0),
                    "otl": _safe(lambda: int(getattr(board, "season_otl", 0) or 0), 0),
                }})
    return out


def _press_payload():
    career = _career()
    hist = _safe(lambda: list(getattr(career, "press_history", []) or []), []) or []
    return {"entries": [
        {"date": str(e.get("date", "")),
         "type": str(e.get("type", "")),
         "summary": str(e.get("summary", ""))}
        for e in reversed(hist[-20:])
    ]}


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@bp.route("/manager")
def manager_page():
    return render_template("manager.html")


@bp.route("/api/manager/board")
def api_board():
    live = _live()
    if live is None:
        return jsonify({"available": False})
    return jsonify(_expectation_payload())


@bp.route("/api/manager/board/expectation", methods=["POST"])
def api_set_expectation():
    import manager_career as mc
    live = _live()
    career = _career()
    board = _safe(lambda: getattr(career, "board", None)) if career else None
    if live is None or board is None:
        return jsonify({"error": "no game"}), 503
    data = request.get_json(silent=True) or {}
    key = str(data.get("expectation", "")).strip()
    if key not in mc.EXPECTATIONS:
        return jsonify({"error": "unknown expectation"}), 400
    try:
        board.set_expectation(key)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True, "expectation": key,
                    "label": mc.EXPECTATIONS[key]["label"]})


@bp.route("/api/manager/board/patience", methods=["POST"])
def api_request_patience():
    live = _live()
    career = _career()
    gm = _gm()
    team = _user_team(gm)
    board = _safe(lambda: getattr(career, "board", None)) if career else None
    if live is None or board is None:
        return jsonify({"error": "no game"}), 503
    today = ""
    cd = _safe(lambda: getattr(live, "current_date", None))
    if cd is not None and hasattr(cd, "isoformat"):
        today = cd.isoformat()
    try:
        granted, headline, body = board.request_patience(today)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    if granted and team is not None:
        # Mirror the Tk hub: the room settles knowing the manager is safe.
        for p in (_safe(lambda: list(getattr(team, "roster", []) or []), []) or []):
            try:
                m = float(getattr(p, "morale", 70) or 70)
                p.morale = min(100.0, m + 2)
            except Exception:
                pass
    return jsonify({"ok": True, "granted": bool(granted),
                    "headline": headline, "body": body})


@bp.route("/api/manager/goals")
def api_goals():
    return jsonify(_goals_payload())


@bp.route("/api/manager/goals", methods=["POST"])
def api_set_goal():
    import season_goals as sg
    team, err, code = _require_game()
    if err:
        return err, code
    data = request.get_json(silent=True) or {}
    pid = str(data.get("player_id", "")).strip()
    gtype = str(data.get("goal_type", "")).strip()
    roster = _safe(lambda: list(getattr(team, "roster", []) or []), []) or []
    player = next((p for p in roster
                   if str(_safe(lambda: getattr(p, "id", ""), "")) == pid), None)
    if player is None:
        return jsonify({"error": "player not found"}), 404
    try:
        target = int(data.get("target", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "target must be a number"}), 400
    ok, msg = _safe(lambda: sg.set_season_goal(player, gtype, target, team=team),
                    (False, "could not set goal"))
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@bp.route("/api/manager/goals/<player_id>", methods=["DELETE"])
def api_clear_goal(player_id):
    import season_goals as sg
    team, err, code = _require_game()
    if err:
        return err, code
    roster = _safe(lambda: list(getattr(team, "roster", []) or []), []) or []
    player = next((p for p in roster
                   if str(_safe(lambda: getattr(p, "id", ""), "")) == str(player_id)),
                  None)
    if player is None:
        return jsonify({"error": "player not found"}), 404
    _safe(lambda: sg.clear_season_goal(player))
    return jsonify({"ok": True})


@bp.route("/api/manager/analytics")
def api_analytics():
    return jsonify(_analytics_payload())


@bp.route("/api/manager/relationships")
def api_relationships():
    return jsonify(_relationships_payload())


@bp.route("/api/manager/relationships/<path:team_key>")
def api_relationship_detail(team_key):
    d = _gm_detail_payload(team_key)
    if d is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(d)


@bp.route("/api/manager/profile")
def api_profile():
    live = _live()
    if live is None:
        return jsonify({"available": False})
    return jsonify(_profile_payload())


@bp.route("/api/manager/press")
def api_press():
    live = _live()
    if live is None:
        return jsonify({"entries": []})
    return jsonify(_press_payload())
