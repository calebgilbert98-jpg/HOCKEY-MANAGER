"""Waivers screen: view the waiver wire and claim players.

v1: read-only list of players on the wire with claim buttons. Claiming
enqueues the "claim_waiver" command (the parent must wire that op into
bridge._execute_command / the game's waiver claim path).
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("waivers", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _to_web_waiver(p):
    """Player -> JSON dict with wire metadata."""
    d = to_web_player(p)
    d["waiver_days"] = _safe(lambda: int(getattr(p, "waiver_days", 0) or 0), 0)
    d["waiver_team"] = _safe(
        lambda: getattr(p, "waiver_team", "") or getattr(p, "team_name", "") or "", "")
    return d


@bp.route("/waivers")
def waivers_page():
    return render_template("waivers.html")


@bp.route("/api/waivers")
def api_waivers():
    live = _live()
    if live is None:
        return jsonify({"players": []})
    wire = _safe(lambda: list(getattr(live, "waiver_list", None) or []), []) or []
    players = []
    for p in wire:
        try:
            players.append(_to_web_waiver(p))
        except Exception:
            continue
    # soonest-to-expire first
    try:
        players.sort(key=lambda d: d.get("waiver_days", 0))
    except Exception:
        pass
    return jsonify({"players": players})


@bp.route("/api/waivers/claim", methods=["POST"])
def api_waivers_claim():
    from flask import request
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    ok = enqueue_command("claim_waiver", player_id=str(pid))
    return jsonify({"ok": ok, "queued": "claim_waiver"})
