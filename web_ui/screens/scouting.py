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
    team = _safe(lambda: app.user_team)
    gm = _safe(lambda: app.game_manager)
    league = _safe(lambda: app.league) or _safe(lambda: gm.league)

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
    """Queue a new scouting assignment; the Tk main thread executes it."""
    data = request.get_json(force=True, silent=True) or {}
    prospect_id = data.get("prospect_id")
    scout_id = data.get("scout_id")
    if not prospect_id or not scout_id:
        return jsonify({"ok": False, "error": "prospect_id and scout_id required"}), 400
    ok = enqueue_command("add_scouting_assignment",
                         prospect_id=str(prospect_id), scout_id=str(scout_id))
    return jsonify({"ok": ok, "queued": "add_scouting_assignment"})
