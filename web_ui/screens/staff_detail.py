"""Staff detail screen: quick profile for a coach/staff member.

Header: name, role, department, rating. Facts: age, nationality,
experience, years with team, salary, morale. All defensive.
"""
from flask import Blueprint, jsonify, render_template

bp = Blueprint("staff_detail", __name__)


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _find_staff(sid):
    live = _live()
    if live is None:
        return None
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    staff = _safe(lambda: list(getattr(team, "staff", []) or []), []) or []
    for s in staff:
        if str(_safe(lambda: getattr(s, "id", ""), "")) == str(sid):
            return s
    return None


@bp.route("/staff/<sid>")
def staff_detail_page(sid):
    return render_template("staff_detail.html", sid=sid)


@bp.route("/api/staff/<sid>")
def api_staff_detail(sid):
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    s = _find_staff(sid)
    if s is None:
        return jsonify({"error": "not found"}), 404
    from web_ui.screens.staff import to_web_staff
    d = to_web_staff(s)
    # Extra detail fields
    d["department"] = _safe(lambda: getattr(s, "department", ""), "") or ""
    d["contract_years"] = _safe(lambda: int(getattr(s, "contract_years", 0) or 0), 0)
    d["specialty"] = _safe(lambda: getattr(s, "specialty", ""), "") or ""
    d["reputation"] = _safe(lambda: getattr(s, "reputation", ""), "") or ""
    d["tactics"] = _safe(lambda: getattr(s, "tactics", ""), "") or ""
    return jsonify(d)
