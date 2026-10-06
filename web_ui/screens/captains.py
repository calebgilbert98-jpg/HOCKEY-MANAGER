"""Captains screen: set the team captain and alternates.

GET  /api/captains -> {captain, alternates, candidates}
POST /api/captains {captain_id, alt1_id, alt2_id} ->
    enqueue_command("set_captains", ...) so the main thread mutates roster.

NOTE for the parent: bridge._execute_command needs a "set_captains" op
handler that finds the players by id on app.user_team.roster, clears the
old C/A flags, and sets .captaincy = 'C' / 'A' / '' accordingly.
"""
from flask import Blueprint, jsonify, render_template, request
from web_ui.bridge import _safe, to_web_player, enqueue_command

bp = Blueprint("captains", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _web_candidate(p):
    d = to_web_player(p)
    d["leadership"] = _safe(lambda: int(getattr(p, "leadership", 0) or 0), 0)
    return d


def get_captains(app):
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if team is None:
        return {"captain": None, "alternates": [], "candidates": []}
    roster = _safe(lambda: list(team.roster), []) or []
    captain, alts, cands = None, [], []
    for p in roster:
        try:
            w = _web_candidate(p)
            cands.append(w)
            cap = _safe(lambda: getattr(p, "captaincy", "") or "", "")
            if cap == "C" and captain is None:
                captain = w
            elif cap == "A":
                alts.append(w)
        except Exception:
            continue
    cands.sort(key=lambda w: (-w.get("leadership", 0), -w.get("overall", 0)))
    return {"captain": captain, "alternates": alts[:2], "candidates": cands}


@bp.route("/captains")
def captains_page():
    return render_template("captains.html")


@bp.route("/api/captains")
def api_captains():
    live = _live()
    if live is None:
        return jsonify({"captain": None, "alternates": [], "candidates": []})
    return jsonify(get_captains(live))


@bp.route("/api/captains", methods=["POST"])
def api_captains_set():
    data = request.get_json(force=True, silent=True) or {}
    ok = enqueue_command(
        "set_captains",
        captain_id=data.get("captain_id"),
        alt1_id=data.get("alt1_id"),
        alt2_id=data.get("alt2_id"),
    )
    return jsonify({"ok": ok, "queued": "set_captains"} if ok
                   else {"ok": False, "error": "queue failed"}), (200 if ok else 500)
