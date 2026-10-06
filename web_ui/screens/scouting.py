# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Scouting screen: assignments + reports."""
from flask import Blueprint, jsonify, render_template, request
from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("scouting", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _to_web_scout(s):
    """Staff member -> JSON-safe dict (scouting view)."""
    role = _safe(lambda: str(getattr(getattr(s, "role", None), "value",
                                    getattr(s, "role", "") or "")), "")
    return {
        "id": _safe(lambda: str(getattr(s, "id", id(s)))),
        "name": _safe(lambda: getattr(s, "full_name", "?")),
        "role": role,
        "judging_ability": _safe(lambda: int(getattr(s, "judging_player_ability", 0) or 0)),
        "judging_potential": _safe(lambda: int(getattr(s, "judging_player_potential", 0) or 0)),
    }


def _to_web_scout_with_region(s, current_region=None):
    d = _to_web_scout(s)
    d["current_region"] = current_region
    return d


def _to_web_report(r):
    """ScoutingReport -> JSON-safe dict."""
    player = _safe(lambda: getattr(r, "player", None))
    scout = _safe(lambda: getattr(r, "scout", None))
    return {
        "player_id": _safe(lambda: str(getattr(player, "id", "")), ""),
        "player_name": _safe(lambda: getattr(player, "full_name", "?"), "?"),
        "player_position": _safe(lambda: getattr(player, "position", "?"), "?"),
        "player_age": _safe(lambda: int(getattr(player, "age", 0) or 0), 0),
        "scout_name": _safe(lambda: getattr(scout, "full_name", "?"), "?"),
        "accuracy": _safe(lambda: getattr(r, "accuracy", "F"), "F"),
        "viewings": _safe(lambda: int(getattr(r, "viewings", 0) or 0), 0),
        "reliability": _safe(lambda: round(float(getattr(r, "reliability", 0.0) or 0.0), 2), 0.0),
        "region": _safe(lambda: getattr(r, "region_coverage", "Unknown"), "Unknown"),
        "competition": _safe(lambda: getattr(r, "competition_level", "Unknown"), "Unknown"),
        "scouted_potential": _safe(lambda: getattr(r, "scouted_potential", None)),
        "projected_draft_position": _safe(lambda: getattr(r, "projected_draft_position", None)),
        "ceiling": _safe(lambda: int(getattr(r, "ceiling_rating", 0) or 0), 0),
        "floor": _safe(lambda: int(getattr(r, "floor_rating", 0) or 0), 0),
        "notes": _safe(lambda: getattr(r, "notes", ""), ""),
    }


def get_scouting_state(app):
    """Active assignments, reports, and candidate scouts/prospects."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: app.league)

    assignments = []
    if app is not None:
        items = _safe(lambda: list((app.scouting_assignments or {}).items()), []) or []
        reports_by_pid = _safe(lambda: dict(getattr(team, "scouting_reports", None) or {}), {}) \
            if team is not None else {}
        for player, scout in items:
            try:
                pid = _safe(lambda: getattr(player, "id", None))
                report = reports_by_pid.get(pid) if pid is not None else None
                prog = _to_web_report(report) if report is not None else None
                assignments.append({
                    "player": to_web_player(player),
                    "scout": _to_web_scout(scout),
                    "report": prog,
                })
            except Exception:
                continue

    reports = []
    if team is not None:
        all_reports = _safe(lambda: list((getattr(team, "scouting_reports", None) or {}).values()), []) or []
        for r in all_reports:
            try:
                reports.append(_to_web_report(r))
            except Exception:
                continue
        try:
            reports.sort(key=lambda x: (x.get("accuracy", "F"), -x.get("viewings", 0)))
        except Exception:
            pass

    scouts = []
    if team is not None:
        for s in _safe(lambda: list(getattr(team, "staff", None) or []), []) or []:
            try:
                role = _safe(lambda: str(getattr(getattr(s, "role", None), "value",
                                                getattr(s, "role", "") or "")), "")
                if "scout" in role.lower():
                    scouts.append(_to_web_scout(s))
            except Exception:
                continue

    prospects = []
    if league is not None:
        for p in _safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []:
            try:
                prospects.append(to_web_player(p))
            except Exception:
                continue

    return {
        "assignments": assignments,
        "reports": reports,
        "scouts": scouts,
        "prospects": prospects,
        "assignment_count": len(assignments),
    }


@bp.route("/scouting")
def scouting_page():
    return render_template("scouting.html")


@bp.route("/api/scouting")
def api_scouting():
    live = _live()
    if live is None:
        return jsonify({"assignments": [], "reports": [], "scouts": [],
                        "prospects": [], "assignment_count": 0})
    return jsonify(get_scouting_state(live))


@bp.route("/api/scouting/assignment", methods=["POST"])
def api_add_assignment():
    """Queue a new player-targeted scouting assignment (real write)."""
    data = request.get_json(force=True, silent=True) or {}
    prospect_id = data.get("prospect_id")
    scout_id = data.get("scout_id")
    if not prospect_id or not scout_id:
        return jsonify({"ok": False, "error": "prospect_id and scout_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "No live game."}), 503
    ok, msg = validate_player_assignment(live, prospect_id, scout_id)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    enqueued = enqueue_command("add_scouting_assignment",
                               prospect_id=str(prospect_id),
                               scout_id=str(scout_id))
    return jsonify({"ok": enqueued, "queued": "add_scouting_assignment"})


# ----------------------------------------------------------------------
# Regional assignments (real write path; replaces the v1 desktop fallback)
#
# The game's regional scouting model (scouting.py) is scout_id -> region on
# game_manager.scout_region_assignments, set via
# scouting.set_scout_region(gm, scout, region) and processed daily by
# scouting.process_regional_scouting(gm). Regions offered by the desktop
# window's own dropdown are scouting.ALL_SCOUT_REGIONS.
# NOTE: the real model has no "focus" or "duration" dimension -- an
# assignment persists until it is changed or recalled -- so the web flow
# only asks for scout + region (region empty = recall).
# ----------------------------------------------------------------------

def _scout_module():
    import scouting as _sc
    return _sc


def get_scouting_options(app):
    """Regions/leagues + scouts (with current region) for the assign modal."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    try:
        _sc = _scout_module()
        regions = list(getattr(_sc, "ALL_SCOUT_REGIONS", []))
        amateur = list(getattr(_sc, "SCOUT_REGIONS", []))
        pro = list(getattr(_sc, "PRO_BEATS", []))
    except Exception:
        regions, amateur, pro = [], [], []
    scouts = []
    if team is not None:
        try:
            _sc = _scout_module()
            region_map = _safe(lambda: dict(getattr(gm, "scout_region_assignments", None) or {}), {}) \
                if gm is not None else {}
            for s in _safe(lambda: list(getattr(team, "staff", None) or []), []) or []:
                try:
                    if not _sc.is_scout(s):
                        continue
                    sid = _safe(lambda: getattr(s, "id", None))
                    cur = region_map.get(sid) if sid is not None else None
                    scouts.append(_to_web_scout_with_region(s, cur))
                except Exception:
                    continue
        except Exception:
            pass
    return {
        "regions": regions,
        "amateur_regions": amateur,
        "pro_leagues": pro,
        "scouts": scouts,
    }


def _find_staff_scout(app, scout_id):
    """(scout, scouting_module, gm) or (None, None, gm) on failure."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    try:
        _sc = _scout_module()
    except Exception:
        return None, None, gm
    sid = str(scout_id or "")
    scout = None
    for s in _safe(lambda: list(getattr(team, "staff", None) or []), []) or []:
        try:
            if str(getattr(s, "id", "")) == sid and _sc.is_scout(s):
                scout = s
                break
        except Exception:
            continue
    return scout, _sc, gm


def validate_region_assignment(app, scout_id, region):
    """Read-only validation of a region assignment. Returns (ok, message)."""
    scout, _sc, gm = _find_staff_scout(app, scout_id)
    _gm_v = _safe(lambda: app.game_manager)
    if gm is None or (_safe(lambda: _gm_v.user_team) or _safe(lambda: app.user_team)) is None:
        return False, "No live game."
    if _sc is None:
        return False, "Scouting isn't available."
    if scout is None:
        return False, "That scout isn't on your staff."
    region = (region or "").strip() or None
    if region is not None and region not in getattr(_sc, "ALL_SCOUT_REGIONS", []):
        return False, f"Unknown region: {region}."
    name = _safe(lambda: getattr(scout, "full_name", "scout"), "scout")
    if region:
        return True, f"{name} assigned to {region}."
    return True, f"{name} recalled from assignment."


def apply_region_assignment(app, scout_id, region):
    """REAL region assignment: re-validates, then scouting.set_scout_region.

    Returns (ok, message). region falsy -> recall (clear assignment).
    Called by the bridge command handler on the main thread; the Flask
    route uses validate_region_assignment for immediate feedback and only
    enqueues the write.
    """
    ok, msg = validate_region_assignment(app, scout_id, region)
    if not ok:
        return False, msg
    scout, _sc, gm = _find_staff_scout(app, scout_id)
    region = (region or "").strip() or None
    try:
        _sc.set_scout_region(gm, scout, region)
    except Exception as e:
        return False, f"Assignment failed: {e}."
    return True, msg


def _find_prospect(app, prospect_id):
    """Resolve a draft-eligible prospect by id (league pool, then team)."""
    pid = str(prospect_id or "")
    _gm_r = _safe(lambda: app.game_manager)
    league = _safe(lambda: _gm_r.league) or _safe(lambda: app.league)
    team = _safe(lambda: _gm_r.user_team) or _safe(lambda: app.user_team)
    pools = []
    if league is not None:
        pools.append(_safe(lambda: list(getattr(league, "draft_prospects", None) or []), []))
    if team is not None:
        pools.append(_safe(lambda: list(getattr(team, "prospects", None) or []), []))
    for pool in pools:
        for p in pool or []:
            try:
                if str(getattr(p, "id", "")) == pid:
                    return p
            except Exception:
                continue
    return None


def validate_player_assignment(app, prospect_id, scout_id):
    """Read-only validation for a player-targeted assignment."""
    if not prospect_id or not scout_id:
        return False, "prospect_id and scout_id required."
    scout, _sc, gm = _find_staff_scout(app, scout_id)
    # Player-targeted assignments only need the team (staff lookup) and
    # the prospect pools — create_scout_assignment writes into
    # app.scouting_assignments, no game_manager required.
    _gm_p = _safe(lambda: app.game_manager)
    if (_safe(lambda: _gm_p.user_team) or _safe(lambda: app.user_team)) is None:
        return False, "No live game."
    if scout is None:
        return False, "That scout isn't on your staff."
    player = _find_prospect(app, prospect_id)
    if player is None:
        return False, "That prospect isn't available."
    try:
        assigns = _safe(lambda: dict(getattr(app, "scouting_assignments", None) or {}), {})
        if player in assigns:
            return False, (f"{getattr(player, 'full_name', 'That player')} is "
                           "already being scouted.")
    except Exception:
        pass
    return True, ""


def apply_player_assignment(app, prospect_id, scout_id):
    """REAL player-targeted assignment via scouting_window_helpers.

    This is what the old v1 desktop fallback ("add_scouting_assignment")
    did through the GUI: create_scout_assignment writes into
    app.scouting_assignments, which process_scouting_assignments
    (main.py) picks up daily. Returns (ok, message).
    """
    ok, msg = validate_player_assignment(app, prospect_id, scout_id)
    if not ok:
        return False, msg
    scout, _sc, _gm = _find_staff_scout(app, scout_id)
    player = _find_prospect(app, prospect_id)
    try:
        import scouting_window_helpers as _sh
    except Exception:
        return False, "Scouting helpers unavailable."
    try:
        return _sh.create_scout_assignment(app, player, scout)
    except Exception as e:
        return False, f"Assignment failed: {e}."


@bp.route("/api/scouting/options")
def api_scouting_options():
    live = _live()
    if live is None:
        return jsonify({"regions": [], "amateur_regions": [], "pro_leagues": [],
                        "scouts": []})
    return jsonify(get_scouting_options(live))


@bp.route("/api/scouting/assign", methods=["POST"])
def api_assign_region():
    """Assign a scout to a region (real write via command queue).

    Body: {scout_id, region}. Empty region recalls the scout. Extra keys
    (e.g. focus/duration) are ignored -- the game model has no such
    dimensions.
    """
    data = request.get_json(force=True, silent=True) or {}
    scout_id = data.get("scout_id")
    region = data.get("region")
    if not scout_id:
        return jsonify({"ok": False, "error": "scout_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "No live game."}), 503
    ok, msg = validate_region_assignment(live, scout_id, region)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    enqueued = enqueue_command("add_scouting_assignment_real",
                               scout_id=str(scout_id), region=region or "")
    return jsonify({"ok": enqueued, "message": msg})


# ----------------------------------------------------------------------
# Batch B: cancel assignment, scouting staff list, player database with
# the desktop's advanced filters (professional_scouting_window parity).
# ----------------------------------------------------------------------

@bp.route("/api/scouting/assignment/cancel", methods=["POST"])
def api_cancel_assignment():
    """Cancel a live player-targeted assignment (desktop right-click ->
    Cancel Assignment). The scout is freed; filed reports are kept."""
    data = request.get_json(force=True, silent=True) or {}
    pid = str(data.get("player_id") or "")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "No live game."}), 503
    assigns = _safe(lambda: dict(getattr(live, "scouting_assignments", None)
                                 or {}), {}) or {}
    found = False
    for pl in assigns.keys():
        try:
            if str(getattr(pl, "id", "")) == pid:
                found = True
                break
        except Exception:
            continue
    if not found:
        return jsonify({"ok": False,
                        "error": "assignment not found"}), 404
    enqueued = enqueue_command("cancel_scout_assignment", player_id=pid)
    return jsonify({"ok": enqueued, "queued": "cancel_scout_assignment"})


@bp.route("/api/scouting/result")
def api_scouting_result():
    """Poll the outcome of the last scouting write (cancel)."""
    live = _live()
    if live is None:
        return jsonify({"result": None})
    return jsonify({"result": _safe(lambda: getattr(
        live, "_web_scout_result", None))})


def _scout_record_line(s):
    try:
        import analytics_scouting as _as
        _as.ensure_analytics_fields(s)
        return _as.scout_record_line(s)
    except Exception:
        return ""


@bp.route("/api/scouting/staff")
def api_scouting_staff():
    """Scouting staff list (desktop Scouting Staff tab parity): overview
    numbers + every scout with judging ratings, current region, workload
    and track record."""
    live = _live()
    if live is None:
        return jsonify({"overview": {}, "scouts": []})
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    try:
        import scouting_window_helpers as _sh
        scouts = _sh.scouts_of(live)
    except Exception:
        scouts = []
    try:
        assigns = _safe(lambda: dict(getattr(live, "scouting_assignments",
                                             None) or {}), {}) or {}
        reports = _safe(lambda: dict(getattr(team, "scouting_reports", None)
                                     or {}), {}) or {}
    except Exception:
        assigns, reports = {}, {}
    try:
        region_map = _safe(lambda: dict(getattr(gm, "scout_region_assignments",
                                                None) or {}), {}) \
            if gm is not None else {}
    except Exception:
        region_map = {}
    # Workload: how many live assignments each scout holds.
    workload = {}
    for _pl, _sc in (assigns or {}).items():
        try:
            sid = str(getattr(_sc, "id", ""))
            workload[sid] = workload.get(sid, 0) + 1
        except Exception:
            continue
    out = []
    for s in scouts or []:
        try:
            sid = _safe(lambda: str(getattr(s, "id", id(s))))
            role = _safe(lambda: str(getattr(getattr(s, "role", None),
                                             "value",
                                             getattr(s, "role", "") or "")), "")
            out.append({
                "id": sid,
                "name": _safe(lambda: getattr(s, "full_name", "?"), "?"),
                "role": role,
                "judging_ability": _safe(
                    lambda: int(getattr(s, "judging_player_ability", 0)
                                or 0)),
                "judging_potential": _safe(
                    lambda: int(getattr(s, "judging_player_potential", 0)
                                or 0)),
                "region": region_map.get(
                    _safe(lambda: getattr(s, "id", None))) or "",
                "workload": workload.get(sid, 0),
                "track_record": _scout_record_line(s),
                "age": _safe(lambda: int(getattr(s, "age", 0) or 0), 0),
                "experience": _safe(
                    lambda: int(getattr(s, "experience", 0) or 0), 0),
                "salary": _safe(lambda: int(getattr(s, "salary", 0) or 0),
                                0),
            })
        except Exception:
            continue
    completed = sum(1 for r in (reports or {}).values()
                    if _safe(lambda: getattr(r, "accuracy", "")) == "A")
    overview = {
        "staff_count": len(out),
        "active_assignments": len(assigns or {}),
        "completed_reports": completed,
        "budget_remaining": _safe(
            lambda: team.staff_budget_remaining(), None)
        if team is not None else None,
    }
    return jsonify({"overview": overview, "scouts": out})


_POSITION_GROUPS = {
    "forwards": {"C", "LW", "RW", "Center", "Left Wing", "Right Wing",
                 "CENTER", "LEFT_WING", "RIGHT_WING"},
    "defensemen": {"D", "LD", "RD", "Defense", "Defence", "Defenseman",
                   "DEFENSE"},
    "goalies": {"G", "Goalie", "Goaltender", "GOALIE"},
}


def _db_position_group(pos):
    p = str(pos or "").strip()
    for group, vals in _POSITION_GROUPS.items():
        if p in vals:
            return group
    pl = p.lower()
    if "goal" in pl:
        return "goalies"
    if "defen" in pl or pl in ("d", "ld", "rd"):
        return "defensemen"
    if pl in ("c", "lw", "rw", "center", "wing"):
        return "forwards"
    return "forwards"


@bp.route("/api/scouting/database")
def api_player_database():
    """Player database with the desktop's advanced filters: name search,
    team, position group (All/Forwards/Defense/Goalies), status
    (NHL/AHL/Prospects/Free Agents/Draft), age range, min OVR.
    Paginated (limit/offset) -- the league-wide pool is large."""
    live = _live()
    if live is None:
        return jsonify({"players": [], "total": 0, "teams": []})
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)

    q = (request.args.get("q") or "").strip().lower()
    pos = (request.args.get("position") or "all").strip().lower()
    status = (request.args.get("status") or "all").strip().lower()
    team_f = (request.args.get("team") or "").strip()
    try:
        age_min = int(request.args.get("age_min", 16) or 16)
    except (TypeError, ValueError):
        age_min = 16
    try:
        age_max = int(request.args.get("age_max", 60) or 60)
    except (TypeError, ValueError):
        age_max = 60
    try:
        ovr_min = int(request.args.get("ovr_min", 1) or 1)
    except (TypeError, ValueError):
        ovr_min = 1
    try:
        limit = min(500, max(1, int(request.args.get("limit", 200) or 200)))
    except (TypeError, ValueError):
        limit = 200
    try:
        offset = max(0, int(request.args.get("offset", 0) or 0))
    except (TypeError, ValueError):
        offset = 0

    pools = []  # (players, status_label, team_name)
    try:
        teams = list(getattr(league, "teams", []) or [])
    except Exception:
        teams = []
    if status in ("all", "nhl"):
        for t in teams:
            pools.append((_safe(lambda: list(getattr(t, "roster", None)
                                              or []), []) or [],
                         "nhl", _safe(lambda: getattr(t, "team_name", ""),
                                      "")))
    if status in ("all", "ahl"):
        for t in teams:
            pools.append((_safe(lambda: list(getattr(t, "ahl_roster", None)
                                              or []), []) or [],
                         "ahl", _safe(lambda: getattr(t, "team_name", ""),
                                      "")))
    if status in ("all", "prospects") and team is not None:
        pools.append((_safe(lambda: list(getattr(team, "prospects", None)
                                          or []), []) or [],
                     "prospects", _safe(lambda: getattr(team, "team_name",
                                                        ""), "")))
    if status in ("all", "free_agents") and league is not None:
        pools.append((_safe(lambda: list(getattr(league, "free_agents",
                                                  None) or []), []) or [],
                     "free_agents", ""))
    if status in ("all", "draft") and league is not None:
        pools.append((_safe(lambda: list(getattr(
            league, "draft_prospects", None) or []), []) or [],
                     "draft", ""))

    team_names = sorted({tn for _, _, tn in pools if tn})
    rows = []
    seen = set()
    for plist, st, tn in pools:
        for p in plist or []:
            try:
                pid = id(p)
                if pid in seen:
                    continue
                seen.add(pid)
                if team_f and tn != team_f:
                    continue
                age = int(getattr(p, "age", 0) or 0)
                if age < age_min or age > age_max:
                    continue
                wp = to_web_player(p)
                try:
                    from web_ui.bridge import _player_ovr
                    ovr = int(_player_ovr(p) or wp.get("overall") or 0)
                except Exception:
                    ovr = int(wp.get("overall") or 0)
                if ovr < ovr_min:
                    continue
                if pos != "all" and _db_position_group(
                        wp.get("position")) != pos:
                    continue
                if q and q not in str(wp.get("name", "")).lower():
                    continue
                wp["status"] = st
                wp["team"] = tn
                wp["overall"] = ovr
                rows.append(wp)
            except Exception:
                continue
    rows.sort(key=lambda r: (-int(r.get("overall") or 0),
                             str(r.get("name") or "")))
    total = len(rows)
    return jsonify({"players": rows[offset:offset + limit], "total": total,
                    "teams": team_names,
                    "filters": {"q": q, "position": pos, "status": status,
                                "team": team_f, "age_min": age_min,
                                "age_max": age_max, "ovr_min": ovr_min,
                                "limit": limit, "offset": offset}})
