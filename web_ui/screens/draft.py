# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Entry draft screen: draft board with pick order and results."""
from flask import Blueprint, jsonify, render_template, request
from web_ui.bridge import _safe, _player_ovr

bp = Blueprint("draft", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _prospect_index(league):
    """Every draftable prospect by id: live class + already-drafted ones on
    team lists (mirrors EntryDraftSession._prospect_index, read-only)."""
    idx = {}
    for p in _safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []:
        try:
            pid = getattr(p, "id", None)
            if pid is not None:
                idx.setdefault(pid, p)
        except Exception:
            continue
    for t in _safe(lambda: list(getattr(league, "teams", None) or []), []) or []:
        for attr in ("prospects", "roster", "ahl_roster"):
            for p in _safe(lambda: list(getattr(t, attr, None) or []), []) or []:
                try:
                    pid = getattr(p, "id", None)
                    if pid is not None:
                        idx.setdefault(pid, p)
                except Exception:
                    continue
    return idx


def get_draft_state(app):
    """Serialize the entry draft session for the board."""
    gm = _safe(lambda: app.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: app.league)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if league is None:
        return {"active": False}

    session = _safe(lambda: getattr(league, "entry_draft_session", None))
    if session is None or _safe(lambda: bool(session.is_complete()), True):
        return {"active": False}

    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    slots = _safe(lambda: list(getattr(session, "slots", None) or []), []) or []
    picks = _safe(lambda: list(getattr(session, "picks", None) or []), []) or []
    cur_idx = _safe(lambda: int(getattr(session, "current_pick", 0) or 0), 0)
    user_name = _safe(lambda: getattr(team, "team_name", ""), "") or ""

    pick_by_overall = {}
    for p in picks:
        try:
            pick_by_overall[int(p.get("overall", -1))] = p
        except Exception:
            continue

    prospects = _prospect_index(league)

    def _to_web_prospect(p):
        return {
            "id": _safe(lambda: str(getattr(p, "id", id(p)))),
            "name": _safe(lambda: getattr(p, "full_name", "?")),
            "position": _safe(lambda: getattr(p, "primary_position", "?")),
            "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
            "overall": _player_ovr(p),
        }

    board = []
    rounds = set()
    for s in slots:
        try:
            overall = int(s.get("overall", 0) or 0)
            rnd = int(s.get("round", 0) or 0)
            rounds.add(rnd)
            owner = str(s.get("owner", "") or "")
            rec = pick_by_overall.get(overall)
            prospect = None
            if rec is not None:
                prospect = prospects.get(rec.get("player_id"))
            board.append({
                "overall": overall,
                "round": rnd,
                "owner": owner,
                "is_user_pick": bool(user_name and owner == user_name),
                "is_current": overall == cur_idx + 1,
                "made": rec is not None,
                "team": str(rec.get("team", "")) if rec is not None else None,
                "prospect": _to_web_prospect(prospect) if prospect is not None else None,
            })
        except Exception:
            continue

    made_count = len(pick_by_overall)
    user_picks = sorted(
        [b["overall"] for b in board if b["is_user_pick"] and not b["made"]])
    return {
        "active": True,
        "year": year,
        "current_overall": cur_idx + 1,
        "total_slots": len(board),
        "made_count": made_count,
        "rounds": sorted(rounds),
        "user_picks": user_picks,
        "board": board,
    }


@bp.route("/draft")
def draft_page():
    return render_template("draft.html")


@bp.route("/api/draft")
def api_draft():
    live = _live()
    if live is None:
        return jsonify({"active": False})
    return jsonify(get_draft_state(live))


# --- War room: available / my picks / scout report -----------------------


def _draft_session(live):
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    return _safe(lambda: getattr(league, "entry_draft_session", None))


def _prospect_pos(p):
    """Position string from primary_position enum or position attr."""
    try:
        pp = getattr(p, "primary_position", None)
        if pp is not None:
            v = getattr(pp, "value", None) or str(pp)
            # "PlayerPosition.RIGHT_DEFENSE" -> "RD"; value is already "RD"
            v = str(v).split(".")[-1].replace("RIGHT_", "R").replace("LEFT_", "L").replace("_DEFENSE", "D").replace("_WING", "W").replace("CENTER", "C").replace("GOALIE", "G")
            return v
    except Exception:
        pass
    return _safe(lambda: str(getattr(p, "primary_position", "?") or "?"), "?")


def _available_prospects(live):
    """Draftable prospects not yet picked."""
    gm = _safe(lambda: live.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: live.league)
    if league is None:
        return []
    session = _draft_session(live)
    picked_ids = set()
    if session is not None:
        for p in (_safe(lambda: list(getattr(session, "picks", None) or []), []) or []):
            try:
                picked_ids.add(str(p.get("player_id")))
            except Exception:
                pass
    prospects = _safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []
    out = []
    for p in prospects:
        try:
            pid = str(getattr(p, "id", ""))
            if pid in picked_ids:
                continue
            out.append({
                "id": pid,
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": _prospect_pos(p),
                "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                "overall": _player_ovr(p),
                "potential": _safe(lambda: str(getattr(p, "potential_grade", "?") or "?"), "?"),
            })
        except Exception:
            continue
    try:
        out.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return out


@bp.route("/api/draft/available")
def api_draft_available():
    live = _live()
    if live is None:
        return jsonify({"prospects": []})
    pos = (request.args.get("pos") or "All").strip()
    q = (request.args.get("q") or "").strip().lower()
    prospects = _available_prospects(live)
    if pos != "All":
        prospects = [p for p in prospects
                     if (p.get("position") or "").upper() == pos
                     or (pos == "D" and (p.get("position") or "").upper() in ("LD", "RD"))
                     or (pos == "W" and (p.get("position") or "").upper() in ("LW", "RW"))]
    if q:
        prospects = [p for p in prospects if q in (p.get("name") or "").lower()]
    return jsonify({"prospects": prospects})


@bp.route("/api/draft/scout_report")
def api_draft_scout_report():
    """Scout report for one prospect."""
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    pid = str(request.args.get("player_id") or "")
    target = None
    for p in _available_prospects(live):
        if p["id"] == pid:
            # Find the real object for attributes
            gm = _safe(lambda: live.game_manager)
            league = _safe(lambda: gm.league) or _safe(lambda: live.league)
            for q in (_safe(lambda: list(getattr(league, "draft_prospects", None) or []), []) or []):
                if str(getattr(q, "id", "")) == pid:
                    target = q
                    break
            break
    if target is None:
        return jsonify({"error": "prospect not found"}), 404
    attrs = {}
    for a in ("shooting_accuracy", "shooting_power", "passing", "skating",
              "checking", "defensive_awareness", "offensive_awareness",
              "strength", "hockey_iq", "potential_grade"):
        try:
            v = getattr(target, a, None)
            if v is not None:
                attrs[a] = v if isinstance(v, str) else int(v)
        except Exception:
            pass
    report = _safe(lambda: getattr(target, "scout_report", "") or "", "")
    strengths = _safe(lambda: list(getattr(target, "strengths", None) or []), []) or []
    weaknesses = _safe(lambda: list(getattr(target, "weaknesses", None) or []), []) or []
    return jsonify({
        "id": pid,
        "name": _safe(lambda: getattr(target, "full_name", "?"), "?"),
        "position": _prospect_pos(target),
        "age": _safe(lambda: int(getattr(target, "age", 0) or 0), 0),
        "overall": _safe(lambda: int(getattr(target, "overall", 0) or 0), 0),
        "attributes": attrs,
        "report": report,
        "strengths": strengths,
        "weaknesses": weaknesses,
    })


@bp.route("/api/draft/pick", methods=["POST"])
def api_draft_pick():
    """Draft Selected: queue a user pick (2-step confirm on client)."""
    data = request.get_json(force=True, silent=True) or {}
    pid = str(data.get("player_id") or "")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    import web_ui.bridge as _b
    _b.enqueue_command({"op": "draft_pick", "player_id": pid})
    return jsonify({"ok": True})


@bp.route("/api/draft/sim_pick", methods=["POST"])
def api_draft_sim_pick():
    """Sim Pick: AI selects for the current slot."""
    import web_ui.bridge as _b
    _b.enqueue_command({"op": "draft_sim_pick"})
    return jsonify({"ok": True})
