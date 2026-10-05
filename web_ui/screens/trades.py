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

    v1 payload (team, give_ids, get_ids) -> queues "propose_trade"
    (the actual trade logic and AI evaluation live in Python; the parent
    wires "propose_trade" in _execute_command); this route only enqueues.

    v2 trade-builder payload (target_team_id, give_pids, give_picks,
    want_pids, want_picks) -> queues "execute_trade". The Tk-thread
    handler re-validates with the REAL ai_consider_trade() before calling
    the real trade_engine.execute_trade(); it never executes a deal the
    AI rejects.
    """
    data = request.get_json(force=True, silent=True) or {}

    # -- v2: trade-builder modal payload (players + picks, AI-gated) -----
    if "target_team_id" in data:
        team_id = data.get("target_team_id")
        give_pids = [str(x) for x in (data.get("give_pids") or [])]
        give_picks = [str(x) for x in (data.get("give_picks") or [])]
        want_pids = [str(x) for x in (data.get("want_pids") or [])]
        want_picks = [str(x) for x in (data.get("want_picks") or [])]
        if not team_id:
            return jsonify({"ok": False, "error": "missing target_team_id"}), 400
        if not give_pids and not give_picks and not want_pids and not want_picks:
            return jsonify({"ok": False, "error": "empty proposal"}), 400
        ok = enqueue_command(
            "execute_trade",
            target_team_id=str(team_id),
            give_pids=give_pids,
            give_picks=give_picks,
            want_pids=want_pids,
            want_picks=want_picks,
        )
        return jsonify({"ok": ok, "queued": "execute_trade", "team": team_id})

    # -- v1: original payload -------------------------------------------------
    # The v1 desktop-window flow is retired (no OS popups): trades now go
    # through the in-page Trade Builder modal (v2 above) with live AI
    # evaluation. This branch returns an in-page error the v1 JS renders
    # in its note area.
    team = data.get("team")
    if team or data.get("give_ids") or data.get("get_ids"):
        return jsonify({
            "ok": False,
            "error": "Use the Trade Builder modal — it evaluates with "
                     "the live AI and executes accepted deals.",
        }), 400
    return jsonify({"ok": False, "error": "empty proposal"}), 400


# ======================================================================
# Trade builder v2 (2026-10-04): interactive in-page modal + real AI eval.
# Appended; the v1 routes above are untouched.
#
# New routes:
# - GET /api/trades/assets?team_id=X — players + draft picks for a team.
# - GET /api/trades/evaluate — read-only REAL AI verdict via
#   trade_engine.ai_consider_trade() (accept/reject/counter + reason + values).
# - POST /api/trades/propose — extended additively: the new-style payload
#   (target_team_id + give_pids/give_picks/want_pids/want_picks) enqueues
#   "execute_trade"; the v1 payload keeps its old "propose_trade" behavior.
# - GET /api/trades/result — poll the last queued execute_trade outcome
#   (the Tk-thread handler stashes it on app._web_trade_result).
#
# Writes ONLY go through enqueue_command(). The coordinator wires
# "execute_trade" in bridge._execute_command(): it re-validates AI acceptance
# and calls the real trade_engine.execute_trade() there.
# ======================================================================


def _round_suffix(r):
    try:
        r = int(r)
    except Exception:
        return ""
    if 11 <= (r % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(r % 10, "th")


def _to_web_pick(pk):
    """DraftPick -> JSON-safe dict."""
    year = _safe(lambda: int(getattr(pk, "year", 0) or 0), 0)
    rnd = _safe(lambda: int(getattr(pk, "round", 0) or 0), 0)
    orig = _safe(lambda: str(getattr(pk, "original_team", "") or ""), "")
    cur = _safe(lambda: str(getattr(pk, "current_team", "") or ""), "")
    if orig and cur and orig != cur:
        label = f"{year} {rnd}{_round_suffix(rnd)} (from {orig})"
    else:
        label = f"{year} {rnd}{_round_suffix(rnd)}"
    return {
        "kind": "pick",
        "id": _safe(lambda: str(getattr(pk, "id", "")), ""),
        "year": year,
        "round": rnd,
        "original_team": orig,
        "current_team": cur,
        "protection": _safe(lambda: str(getattr(pk, "protection", "") or ""), ""),
        "label": label,
    }


def _team_trade_lists(team):
    """(players, picks) the game lets a team trade: roster, ahl_roster,
    prospects, and draft_picks {year: [DraftPick]}."""
    players = []
    for attr, level in (("roster", "NHL"), ("ahl_roster", "AHL"),
                        ("prospects", "Prospects")):
        for p in _safe(lambda: list(getattr(team, attr, None) or []), []) or []:
            players.append((p, level))
    picks = []
    by_year = _safe(lambda: dict(getattr(team, "draft_picks", None) or {}), {}) or {}
    for year in sorted(by_year.keys()):
        for pk in _safe(lambda: list(by_year.get(year) or []), []) or []:
            picks.append(pk)
    return players, picks


def _find_team(live, team_id):
    """Match a team by abbreviation, name, team_name, or 'City Name'."""
    if not team_id:
        return None
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []
    want = str(team_id).strip().lower()
    for t in teams:
        d = to_web_team(t)
        cands = {
            str(d.get("abbr") or "").lower(),
            str(d.get("name") or "").lower(),
            str(_team_name(t) or "").lower(),
            f"{d.get('city', '')} {d.get('name', '')}".strip().lower(),
        }
        if want in cands:
            return t
    return None


def _resolve_assets(team, pids, pick_ids):
    """Map id strings -> live game objects (players, picks)."""
    pid_set = {str(x) for x in (pids or [])}
    pick_set = {str(x) for x in (pick_ids or [])}
    players, picks = _team_trade_lists(team)
    out_players = [p for p, _lvl in players if str(getattr(p, "id", "")) in pid_set]
    out_picks = [pk for pk in picks if str(getattr(pk, "id", "")) in pick_set]
    return out_players, out_picks


def _trade_engine():
    """Lazy import of the game's trade engine (keeps Flask import light)."""
    try:
        import trade_engine
        return trade_engine
    except Exception:
        return None


@bp.route("/api/trades/assets")
def api_trades_assets():
    """Tradeable assets of one team: players (roster/AHL/prospects) + picks."""
    live = _live()
    if live is None:
        return jsonify({"team": None, "players": [], "picks": []})
    team = _find_team(live, request.args.get("team_id", ""))
    if team is None:
        return jsonify({"error": "unknown team"}), 404
    players, picks = _team_trade_lists(team)
    return jsonify({
        "team": _team_name(team),
        "players": [{**to_web_player(p),
                     "level": lvl} for p, lvl in players],
        "picks": [_to_web_pick(pk) for pk in picks],
    })


@bp.route("/api/trades/evaluate")
def api_trades_evaluate():
    """Read-only REAL AI verdict on a hypothetical deal.

    Query params: give_pids, give_picks, want_pids, want_picks (comma ids),
    target_team_id. No state mutation: only calls trade_engine's
    read-only ai_consider_trade() + evaluate_trade().
    """
    live = _live()

    def _csv(name):
        raw = request.args.get(name, "") or ""
        return [s.strip() for s in raw.split(",") if s.strip()]

    target_id = request.args.get("target_team_id", "")
    give_pids, give_picks = _csv("give_pids"), _csv("give_picks")
    want_pids, want_picks = _csv("want_pids"), _csv("want_picks")

    if live is None:
        # Mock/demo mode: no game loaded — clearly labeled.
        return jsonify({
            "verdict": "reject",
            "reason": "Demo mode — connect a live game for a real AI verdict.",
            "mock": True,
            "give_value": 0, "get_value": 0, "diff": 0, "ratio": 0.0,
            "label": "Demo",
        })

    user_team = _safe(lambda: live.user_team)
    partner = _find_team(live, target_id)
    te = _trade_engine()
    if user_team is None or partner is None or te is None:
        return jsonify({"verdict": "reject",
                        "reason": "Could not resolve teams or trade engine.",
                        "give_value": 0, "get_value": 0, "diff": 0,
                        "ratio": 0.0, "label": "Incomplete"})

    give_players, give_pick_objs = _resolve_assets(user_team, give_pids, give_picks)
    want_players, want_pick_objs = _resolve_assets(partner, want_pids, want_picks)
    give_assets = give_players + give_pick_objs
    want_assets = want_players + want_pick_objs

    if not give_assets and not want_assets:
        return jsonify({"verdict": "reject",
                        "reason": "There's nothing on the table yet.",
                        "give_value": 0, "get_value": 0, "diff": 0,
                        "ratio": 0.0, "label": "Incomplete"})

    # Value breakdown (pure math, no AI opinion).
    ev = _safe(lambda: te.evaluate_trade(
        give_assets, want_assets,
        user_team=user_team, partner_team=partner,
        perceiver_team=partner))
    give_value = _safe(lambda: ev.user_value, 0) or 0
    get_value = _safe(lambda: ev.partner_value, 0) or 0
    diff = _safe(lambda: ev.diff, give_value - get_value) or 0
    ratio = _safe(lambda: ev.ratio, 0.0) or 0.0
    label = _safe(lambda: ev.label, "Incomplete") or "Incomplete"

    # REAL AI verdict — read-only; ai_consider_trade never mutates.
    resp = _safe(lambda: te.ai_consider_trade(
        partner, give_assets, want_assets, user_team=user_team))
    verdict = _safe(lambda: resp.decision, "reject") or "reject"
    reason = _safe(lambda: resp.message, "") or ""

    return jsonify({
        "verdict": verdict,          # accept | reject | counter
        "reason": reason,
        "give_value": give_value,    # what we give up (trade points)
        "get_value": get_value,      # what we receive (trade points)
        "diff": diff,
        "ratio": ratio,
        "label": label,
        "give_count": len(give_assets),
        "get_count": len(want_assets),
    })


@bp.route("/api/trades/result")
def api_trades_result():
    """Last queued execute_trade outcome (stashed by the Tk-thread handler)."""
    live = _live()
    result = _safe(lambda: getattr(live, "_web_trade_result", None)) if live else None
    return jsonify({"result": result})
