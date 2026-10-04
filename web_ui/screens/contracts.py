"""Contracts screen: roster contracts sorted by cap hit, with extensions.

v1: table of user-team roster contracts showing player, position, cap
hit, term remaining and an expiring flag. "Extend" enqueues the
"extend_contract" command (the parent must wire that op into
bridge._execute_command / the game's extension path).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("contracts", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _web_position(p):
    """Best-effort position label. Never raises."""
    try:
        from game_classes import position_label
        label = _safe(lambda: position_label(p))
        if label and label != "?":
            return label
    except Exception:
        pass
    return _safe(lambda: str(getattr(p, "position", "?") or "?"), "?")


def _to_web_contract(p):
    d = to_web_player(p)
    d["position"] = _web_position(p)
    contract = _safe(lambda: getattr(p, "contract", None))
    salary = _safe(lambda: int(getattr(contract, "salary", 0) or 0), 0)
    years = _safe(lambda: getattr(contract, "years_remaining", None))
    if years is None:
        years = _safe(lambda: getattr(contract, "term", None))
    years = _safe(lambda: int(years), 0)
    d["salary"] = salary
    d["cap_hit"] = salary
    d["years_remaining"] = years
    d["expiring"] = bool(years <= 1)
    # clause flags for the tooltip line
    d["no_trade"] = _safe(lambda: bool(getattr(contract, "no_trade_clause", False)), False)
    d["no_movement"] = _safe(lambda: bool(getattr(contract, "no_movement_clause", False)), False)
    d["two_way"] = _safe(lambda: bool(getattr(contract, "two_way", False)), False)
    return d


@bp.route("/contracts")
def contracts_page():
    return render_template("contracts.html")


@bp.route("/api/contracts")
def api_contracts():
    live = _live()
    if live is None:
        return jsonify({"contracts": [], "summary": {}})
    roster = _safe(lambda: list(getattr(live.user_team, "roster", None) or []), []) or []
    rows = []
    for p in roster:
        try:
            rows.append(_to_web_contract(p))
        except Exception:
            continue
    try:
        rows.sort(key=lambda d: d.get("cap_hit", 0), reverse=True)
    except Exception:
        pass
    total = _safe(lambda: sum(r.get("cap_hit", 0) for r in rows), 0)
    cap = _safe(lambda: int(getattr(live.game_manager.league, "salary_cap", 0) or 0), 0)
    return jsonify({
        "contracts": rows,
        "summary": {
            "total_cap_hit": total,
            "cap_ceiling": cap,
            "player_count": len(rows),
        },
    })


@bp.route("/api/contracts/extend", methods=["POST"])
def api_contracts_extend():
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    ok = enqueue_command("extend_contract", player_id=str(pid))
    return jsonify({"ok": ok, "queued": "extend_contract"})
