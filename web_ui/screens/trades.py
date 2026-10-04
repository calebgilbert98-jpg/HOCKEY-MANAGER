"""Trades screen: trade center proposal builder (v1, read-only-friendly)."""
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import (
    _safe,
    enqueue_command,
    to_web_player,
    to_web_team,
)

bp = Blueprint("trades", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


@bp.route("/trades")
def trades_page():
    return render_template("trades.html")


@bp.route("/api/trades/teams")
def api_trades_teams():
    """All 32 teams, flagging the user team and teams with players on the block."""
    live = _live()
    if live is None:
        return jsonify({"teams": [], "user_team": None, "trade_block_count": 0})
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []
    my_name = _safe(lambda: live.user_team.team_name)

    # Which teams have players listed in app.trade_block?
    block = _safe(lambda: list(getattr(live, "trade_block", None) or []), []) or []
    block_teams = set()
    for p in block:
        try:
            owner = getattr(p, "team", None) or getattr(p, "team_name", None)
            block_teams.add(_team_name(owner))
        except Exception:
            continue

    out = []
    for t in teams:
        d = to_web_team(t)
        tn = _team_name(t)
        d["is_user"] = bool(my_name) and tn == my_name
        d["on_block"] = tn in block_teams
        out.append(d)
    return jsonify({
        "teams": out,
        "user_team": my_name,
        "trade_block_count": len(block),
    })


@bp.route("/api/trades/roster")
def api_trades_roster():
    """Roster for the named trade partner plus the user's own roster."""
    live = _live()
    if live is None:
        return jsonify({"team": None, "players": [], "my_roster": []})
    want = request.args.get("team", "")
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []

    target = None
    for t in teams:
        if _team_name(t) == want:
            target = t
            break

    players = []
    if target is not None:
        players = [to_web_player(p)
                   for p in _safe(lambda: list(target.roster), []) or []]
    my = _safe(lambda: live.user_team)
    mine = [to_web_player(p)
            for p in _safe(lambda: list(my.roster), []) or []] if my else []
    return jsonify({"team": want, "players": players, "my_roster": mine})


@bp.route("/api/trades/propose", methods=["POST"])
def api_trades_propose():
    """Queue a trade proposal for the Tk main thread to evaluate/execute.

    The actual trade logic and AI evaluation live in Python (parent wires
    "propose_trade" in _execute_command); this route only enqueues.
    """
    data = request.get_json(force=True, silent=True) or {}
    team = data.get("team")
    give_ids = data.get("give_ids") or []
    get_ids = data.get("get_ids") or []
    if not team:
        return jsonify({"ok": False, "error": "missing team"}), 400
    if not give_ids and not get_ids:
        return jsonify({"ok": False, "error": "empty proposal"}), 400
    ok = enqueue_command(
        "propose_trade",
        team=team,
        give_ids=[str(x) for x in give_ids],
        get_ids=[str(x) for x in get_ids],
    )
    return jsonify({"ok": ok, "queued": "propose_trade", "team": team})
