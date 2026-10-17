"""Staff screen: coaches & management (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, enqueue_command, _resolve_gm

bp = Blueprint("staff", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _staff_role(s):
    role = _safe(lambda: getattr(s, "role", None), None)
    if role is None:
        return _safe(lambda: str(getattr(s, "role", "Staff")), "Staff")
    return _safe(lambda: getattr(role, "value", None) or str(role), "Staff")


def to_web_staff(s):
    """Staff -> JSON-safe dict. All access defensive."""
    name = _safe(lambda: getattr(s, "full_name", None), None)
    if not name:
        fn = _safe(lambda: getattr(s, "first_name", ""), "")
        ln = _safe(lambda: getattr(s, "last_name", ""), "")
        name = f"{fn} {ln}".strip() or "?"
    salary = _safe(lambda: int(getattr(s, "salary", 0) or 0), 0)
    return {
        "id": _safe(lambda: str(getattr(s, "id", id(s)))),
        "name": name,
        "role": _staff_role(s),
        "rating": _safe(lambda: int(getattr(s, "overall_rating", 0) or 0), 0),
        "morale": _safe(lambda: int(getattr(s, "morale", 0) or 0), 0),
        "age": _safe(lambda: int(getattr(s, "age", 0) or 0), 0),
        "nationality": _safe(lambda: getattr(s, "nationality", ""), "") or "",
        "experience": _safe(lambda: int(getattr(s, "experience", 0) or 0), 0),
        "years_with_team": _safe(lambda: int(getattr(s, "years_with_team", 0) or 0), 0),
        "salary": salary,
    }


@bp.route("/staff")
def staff_page():
    return render_template("staff.html")


@bp.route("/api/staff")
def api_staff():
    live = _live()
    if live is None:
        return jsonify({"staff": [], "count": 0})
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    staff = _safe(lambda: list(team.staff), []) or [] if team else []
    out = []
    for s in staff:
        try:
            out.append(to_web_staff(s))
        except Exception:
            continue
    return jsonify({"staff": out, "count": len(out)})


@bp.route("/api/staff/release", methods=["POST"])
def api_staff_release():
    """Release a staff member from the user's team."""
    from flask import request
    data = request.get_json(force=True, silent=True) or {}
    sid = data.get("staff_id")
    if not sid:
        return jsonify({"ok": False, "error": "staff_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    staff = _safe(lambda: list(getattr(team, "staff", None) or []), []) or [] \
        if team else []
    if not any(str(_safe(lambda: getattr(s, "id", ""), "")) == str(sid)
               for s in staff):
        return jsonify({"ok": False, "error": "staff not found"}), 404
    ok = enqueue_command("release_staff", staff_id=str(sid))
    return jsonify({"ok": ok, "queued": "release_staff"})


def _staff_roles():
    """All reassignable roles: (enum_name, display_value). Never raises."""
    try:
        from game_classes import StaffRole
        return [(r.name, r.value) for r in StaffRole]
    except Exception:
        return []


@bp.route("/api/staff/roles")
def api_staff_roles():
    """List of roles for the reassign dialog."""
    return jsonify({"roles": [{"name": n, "label": v}
                              for (n, v) in _staff_roles()]})


@bp.route("/api/staff/reassign", methods=["POST"])
def api_staff_reassign():
    """Reassign a staff member to a new role. Server validates the role
    and the unique-role guard (GM / Head Coach); the main-thread op
    applies it."""
    from flask import request
    data = request.get_json(force=True, silent=True) or {}
    sid = data.get("staff_id")
    role_name = data.get("role")
    if not sid or not role_name:
        return jsonify({"ok": False,
                        "error": "staff_id and role required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    try:
        from game_classes import StaffRole, Staff
        new_role = StaffRole[str(role_name)]
    except Exception:
        return jsonify({"ok": False,
                        "error": f"unknown role: {role_name}"}), 422
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    staff = _safe(lambda: list(getattr(team, "staff", None) or []), []) or [] \
        if team else []
    target = next((s for s in staff
                   if str(_safe(lambda: getattr(s, "id", ""), "")) == str(sid)),
                  None)
    if target is None:
        return jsonify({"ok": False, "error": "staff not found"}), 404
    if _safe(lambda: getattr(target, "role", None)) == new_role:
        return jsonify({"ok": False,
                        "error": "already in that role"}), 422
    if _safe(lambda: Staff.is_unique_role(new_role), False):
        conflict = [s for s in staff
                    if s is not target
                    and _safe(lambda: getattr(s, "role", None)) == new_role]
        if conflict:
            cname = _safe(lambda: getattr(conflict[0], "full_name", "?"), "?")
            return jsonify({"ok": False,
                            "error": f"Team already has a {new_role.value}: "
                                     f"{cname}. Reassign or release them first."}), 422
    queued = enqueue_command("reassign_staff", staff_id=str(sid),
                             role=str(role_name))
    return jsonify({"ok": bool(queued), "queued": "reassign_staff"})
