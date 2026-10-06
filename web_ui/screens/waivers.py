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


@bp.route("/api/waivers/place", methods=["POST"])
def api_waivers_place():
    """Place one of the user's own players on waivers."""
    from flask import request
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    # Pre-flight the same gates the bridge enforces, so the UI can say
    # why a placement is refused instead of queueing into silence.
    try:
        import transaction_windows as _tw
        ok, why = _tw.check_window(
            "waiver_place", _safe(lambda: getattr(live, "current_date", None)))
        if not ok:
            return jsonify({"ok": False, "error": why}), 422
    except Exception:
        pass
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    player = next((p for p in roster
                   if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid)),
                  None)
    if player is None:
        return jsonify({"ok": False, "error": "player not on roster"}), 404
    if _safe(lambda: bool(getattr(player, "on_waivers", False)), False):
        return jsonify({"ok": False, "error": "already on waivers"}), 409
    try:
        import trade_engine as _te
        _kind, _detail = _te.clause_of(player)
        if _kind == "NMC":
            return jsonify({"ok": False,
                            "error": f"{_safe(lambda: getattr(player, 'full_name', '?'), '?')} has a "
                                     f"no-movement clause — placement blocked."}), 422
    except Exception:
        pass
    ok = enqueue_command("place_on_waivers", player_id=str(pid))
    return jsonify({"ok": ok, "queued": "place_on_waivers"})


def _clause_of(p):
    """(kind, detail) — NMC blocks waiver placement (safe default without
    the desktop ask-card); NTC alone does not."""
    try:
        import trade_engine as _te
        kind, detail = _te.clause_of(p)
        return kind or "", detail or ""
    except Exception:
        return "", ""


@bp.route("/api/waivers/eligible")
def api_waivers_eligible():
    """The user's roster players available to place on waivers, with the
    real waiver-eligibility read (waiver_logic.is_waiver_eligible) and
    clause flags. Placement itself always runs the wire; exemption is
    informational (real NHL: exempt players skip the wire)."""
    live = _live()
    if live is None:
        return jsonify({"players": [], "error": "no live game"}), 503
    gm = _safe(lambda: live.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    try:
        import waiver_logic as _wl
        eligible_fn = _wl.is_waiver_eligible
    except Exception:
        eligible_fn = None
    out = []
    for p in roster:
        try:
            if _safe(lambda: bool(getattr(p, "on_waivers", False)), False):
                continue
            kind, _detail = _clause_of(p)
            exempt = None
            if eligible_fn is not None:
                try:
                    exempt = not bool(eligible_fn(p))
                except Exception:
                    exempt = None
            d = to_web_player(p)
            d["waiver_exempt"] = exempt
            d["clause"] = kind
            d["nmc_block"] = (kind == "NMC")
            out.append(d)
        except Exception:
            continue
    return jsonify({"players": out})
