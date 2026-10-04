"""Free agents screen: UFA/RFA list with make-offer buttons.

v1: sortable/filterable list of players in league.free_agents with
overall color bars and an asking-price display. "Make offer" enqueues
the "sign_free_agent" command (the parent must wire that op into
bridge._execute_command / the game's signing path).
"""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("free_agents", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _fa_type(p):
    """Best-effort UFA/RFA label. Never raises."""
    try:
        if getattr(p, "ufa", None):
            return "UFA"
        if getattr(p, "rfa", None):
            return "RFA"
        age = int(getattr(p, "age", 0) or 0)
        # NHL rule of thumb: 27+ years old or 7+ pro seasons -> unrestricted.
        pro = _safe(lambda: int(getattr(p, "years_pro", 0) or getattr(p, "seasons_played", 0) or 0), 0)
        if age >= 27 or pro >= 7:
            return "UFA"
        return "RFA"
    except Exception:
        return "FA"


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


def _to_web_fa(p):
    d = to_web_player(p)
    d["position"] = _web_position(p)
    d["fa_type"] = _fa_type(p)
    # asking price: contract.salary on FA players is their demand
    contract = _safe(lambda: getattr(p, "contract", None))
    ask = _safe(lambda: int(getattr(contract, "salary", 0) or getattr(p, "salary", 0) or 0), 0)
    d["ask"] = ask
    d["salary"] = ask
    return d


@bp.route("/free_agents")
def free_agents_page():
    return render_template("free_agents.html")


@bp.route("/api/free_agents")
def api_free_agents():
    live = _live()
    if live is None:
        return jsonify({"players": []})
    league = _safe(lambda: live.game_manager.league)
    pool = _safe(lambda: list(getattr(league, "free_agents", None) or []), []) or []
    players = []
    for p in pool:
        try:
            players.append(_to_web_fa(p))
        except Exception:
            continue
    return jsonify({"players": players})


@bp.route("/api/free_agents/offer", methods=["POST"])
def api_free_agents_offer():
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    offer = _safe(lambda: int(data.get("salary") or 0), 0)
    ok = enqueue_command("sign_free_agent", player_id=str(pid), salary=offer)
    return jsonify({"ok": ok, "queued": "sign_free_agent"})
