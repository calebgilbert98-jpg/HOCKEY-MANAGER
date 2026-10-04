# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Entry draft screen: draft board with pick order and results."""
from flask import Blueprint, jsonify, render_template
from web_ui.bridge import _safe

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
    league = _safe(lambda: app.league) or _safe(lambda: gm.league)
    team = _safe(lambda: app.user_team)
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
            "position": _safe(lambda: getattr(p, "position", "?")),
            "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
            "overall": _safe(lambda: int(getattr(p, "overall", 0) or 0)),
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
