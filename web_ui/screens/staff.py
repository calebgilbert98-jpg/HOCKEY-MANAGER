"""Staff screen: coaches & management (read-only v1)."""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, enqueue_command

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
    team = _safe(lambda: live.user_team)
    staff = _safe(lambda: list(team.staff), []) or [] if team else []
    out = []
    for s in staff:
        try:
            out.append(to_web_staff(s))
        except Exception:
            continue
    return jsonify({"staff": out, "count": len(out)})
