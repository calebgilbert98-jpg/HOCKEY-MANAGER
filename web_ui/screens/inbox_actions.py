"""Inbox interactive actions API (Batch A, 2026-10-05).

Ports the v0.18.4 desktop inbox action types to the web UI:
game_day, postmatch_presser, rfa_qualifying, offer_sheet_match,
offer_sheet_trade_alt, arbitration_walkaway, buyout_window,
staff_renewal, media_fine_response, plus the START FANTASY DRAFT and
WATCH THE REVEAL special buttons.

Writes go through the command queue (bridge._execute_command), exactly
like the existing inbox ops; this blueprint owns the read APIs and the
two full pages (fantasy draft, lottery reveal).
"""
from flask import Blueprint, jsonify, render_template, request

import web_ui.bridge as _bridge
from web_ui.bridge import (
    _safe, _inbox_special_action, _player_ovr,
    enqueue_command, to_web_message, to_web_player,
)

bp = Blueprint("inbox_actions", __name__)


def _live():
    return _bridge._web_app_ref


def _gm(app):
    return _safe(lambda: app.game_manager)


def _user_team(app):
    gm = _gm(app)
    return _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)


def _message_detail(app, mid):
    """Single web message + the extras the action renderers need."""
    gm = _gm(app)
    team = _user_team(app)
    inbox = _safe(lambda: getattr(team, "inbox", None))
    msg = None
    if inbox is not None and mid:
        for m in _safe(lambda: list(inbox.messages), []) or []:
            if str(_safe(lambda: getattr(m, "id", ""), "")) == str(mid):
                msg = m
                break
    if msg is None:
        return None
    d = to_web_message(msg)
    d["special_action"] = _inbox_special_action(app, gm, msg)
    today = _safe(lambda: gm.current_date) or _safe(lambda: app.current_date)
    try:
        d["today"] = today.isoformat() if hasattr(today, "isoformat") else str(today or "")
    except Exception:
        d["today"] = ""
    d["user_team_name"] = _safe(lambda: team.team_name, "") or ""
    if d.get("action_type") == "game_day":
        d["is_preseason"] = _gameday_is_preseason(app, gm, team, today)
    return d


def _gameday_is_preseason(app, gm, team, today):
    """Mirror of inbox_window._is_preseason_game_day: today's user-team
    game is a preseason exhibition."""
    try:
        if team is None or today is None:
            return False
        league = _safe(lambda: gm.league) if gm else None
        tname = _safe(lambda: getattr(team, "team_name", ""))
        for item in (getattr(league, "schedule", None) or []):
            try:
                if isinstance(item, dict):
                    d, h, a = (item.get("date"), item.get("home_team"),
                               item.get("away_team"))
                elif isinstance(item, (tuple, list)) and len(item) >= 3:
                    d, h, a = item[0], item[1], item[2]
                else:
                    continue
                hn = getattr(h, "team_name", h) if h else ""
                an = getattr(a, "team_name", a) if a else ""
                if d == today and (h is team or a is team
                                   or hn == tname or an == tname):
                    return bool(item.get("preseason")) \
                        if isinstance(item, dict) else False
            except Exception:
                continue
    except Exception:
        pass
    return False


@bp.route("/api/inbox/message/<mid>")
def api_inbox_message(mid):
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 404
    d = _message_detail(live, mid)
    if d is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(d)


# ------------------------------------------------------------------
# Fantasy draft (simplified snake UI; real FantasyDraftManager logic)
# ------------------------------------------------------------------
@bp.route("/fantasy_draft")
def fantasy_draft_page():
    return render_template("fantasy_draft.html")


def _fantasy_status(app):
    """JSON status of the league-owned fantasy draft session."""
    gm = _gm(app)
    pending = bool(_safe(lambda: getattr(gm, "pending_fantasy_draft", False), False))
    mgr, _err = _bridge._fantasy_draft_manager(app, create=False)
    if mgr is None:
        done_info = _safe(lambda: getattr(gm, "_web_fantasy_completed", None))
        if done_info:
            return {"active": False, "pending": False, "started": False,
                    "completed": True,
                    "rounds": done_info.get("rounds", 0),
                    "total_picks": done_info.get("total_picks", 0)}
        return {"active": False, "pending": pending, "started": False}
    try:
        cur = mgr.get_current_pick()
    except Exception:
        cur = None
    complete = bool(_safe(lambda: mgr.is_draft_complete(), False))
    user_team = getattr(mgr, "user_team", None) or _user_team(app)
    uname = _safe(lambda: getattr(user_team, "team_name", ""), "")
    status = {
        "active": True,
        "pending": pending,
        "started": bool(getattr(mgr, "draft_started", False)),
        "complete": complete,
        "completed": False,
        "rounds": _safe(lambda: int(getattr(getattr(mgr, "config", None), "rounds", 0) or 0), 0),
        "total_picks": _safe(lambda: len(getattr(mgr, "draft_picks", None) or []), 0),
        "picks_made": _safe(lambda: int(getattr(mgr, "current_pick", 0) or 0), 0),
        "user_team": uname,
    }
    if cur is not None and not complete:
        cteam = getattr(cur, "team", None)
        cname = _safe(lambda: getattr(cteam, "team_name", "?"), "?")
        status["current"] = {
            "overall": _safe(lambda: int(getattr(cur, "overall_pick", 0) or 0), 0),
            "round": _safe(lambda: int(getattr(cur, "round_num", 0) or 0), 0),
            "team": cname,
            "is_user_pick": _bridge._same_team(cteam, user_team),
        }
    try:
        order = [ _safe(lambda t=t: getattr(t, "team_name", "?"), "?")
                  for t in (getattr(mgr, "draft_order", None) or []) ]
        status["draft_order"] = order
    except Exception:
        status["draft_order"] = []
    # Available players: top 60 by overall (uses the real rating method).
    try:
        avail = mgr.get_available_players() or []
        scored = sorted(
            (( _player_ovr(p), p) for p in avail),
            key=lambda t: t[0], reverse=True)
        players = []
        for ovr, p in scored[:60]:
            d = to_web_player(p)
            d["overall"] = int(ovr)
            d["former_team"] = _safe(lambda: getattr(p, "former_team", ""), "") or ""
            players.append(d)
        status["available"] = players
        status["available_count"] = len(avail)
    except Exception:
        status["available"] = []
        status["available_count"] = 0
    # Recent picks (last 12) for the draft board ticker.
    try:
        picks = getattr(mgr, "draft_picks", None) or []
        done = [pk for pk in picks
                if _safe(lambda: getattr(pk, "player", None)) is not None]
        recent = []
        for pk in done[-12:]:
            pl = pk.player
            recent.append({
                "overall": _safe(lambda: int(getattr(pk, "overall_pick", 0) or 0), 0),
                "team": _safe(lambda: getattr(getattr(pk, "team", None), "team_name", "?"), "?"),
                "player": _safe(lambda: getattr(pl, "full_name", "?"), "?"),
                "ovr": _player_ovr(pl),
            })
        status["recent_picks"] = recent
        # User team's haul so far.
        mine = [ {"overall": _safe(lambda: int(getattr(pk, "overall_pick", 0) or 0), 0),
                  "player": _safe(lambda: getattr(pk.player, "full_name", "?"), "?"),
                  "ovr": _player_ovr(pk.player)}
                 for pk in done
                 if _safe(lambda: getattr(getattr(pk, "team", None), "team_name", ""), "") == uname ]
        status["my_picks"] = mine
    except Exception:
        status["recent_picks"] = []
        status["my_picks"] = []
    return status


@bp.route("/api/fantasy_draft")
def api_fantasy_draft():
    live = _live()
    if live is None:
        return jsonify({"active": False, "pending": False})
    try:
        return jsonify(_fantasy_status(live))
    except Exception as e:
        return jsonify({"active": False, "error": str(e)})


@bp.route("/api/fantasy_draft/begin", methods=["POST"])
def api_fantasy_draft_begin():
    ok = enqueue_command("fantasy_draft_begin")
    return jsonify({"ok": ok, "queued": "fantasy_draft_begin"})


@bp.route("/api/fantasy_draft/pick", methods=["POST"])
def api_fantasy_draft_pick():
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    if not pid:
        return jsonify({"ok": False, "error": "player_id required"}), 400
    ok = enqueue_command("fantasy_draft_pick", player_id=str(pid))
    return jsonify({"ok": ok, "queued": "fantasy_draft_pick"})


# ------------------------------------------------------------------
# Draft lottery reveal (simplified televised countdown)
# ------------------------------------------------------------------
@bp.route("/lottery")
def lottery_page():
    return render_template("lottery.html")


def _reaction_line(row):
    """Verbatim port of draft_lottery.reaction_line (pure dict logic;
    the module itself needs customtkinter, unavailable on the server)."""
    mv, team, pick = row["movement"], row["team"], row["pick"]
    if pick == 1:
        return f"{team} wins the lottery \u2014 #1 overall!"
    if pick == 2:
        return f"{team} takes #2 \u2014 the consolation prize nobody hates."
    if mv >= 5:
        return f"{team} leaps {mv} spots to #{pick} \u2014 the room erupts!"
    if mv >= 2:
        return f"{team} jumps to #{pick} (+{mv})."
    if mv <= -3:
        return f"{team} slides to #{pick} ({mv}) \u2014 groans in the war room."
    if mv < 0:
        return f"{team} falls to #{pick}."
    return f"{team} holds at #{pick}."


def _lottery_rows(app):
    """Pending reveal rows, else the stored league result (latest year)."""
    gm = _gm(app)
    pending = _safe(lambda: getattr(gm, "_pending_lottery_reveal", None))
    if pending:
        return (_safe(lambda: int(pending.get("year", 0)) or 0),
                [dict(r) for r in (pending.get("rows") or [])])
    league = _safe(lambda: gm.league) if gm else None
    stored = _safe(lambda: getattr(league, "lottery_results", None) or {}, {})
    years = [y for y in stored.keys() if stored.get(y)]
    if not years:
        return 0, []
    year = max(years)
    return year, [dict(r) for r in stored[year]]


@bp.route("/api/lottery")
def api_lottery():
    live = _live()
    if live is None:
        return jsonify({"active": False, "rows": []})
    try:
        year, rows = _lottery_rows(live)
        web_rows = []
        for r in rows:
            try:
                web_rows.append({
                    "pick": int(r.get("pick", 0) or 0),
                    "team": str(r.get("team", "?")),
                    "odds_pct": float(r.get("odds_pct", 0) or 0),
                    "movement": int(r.get("movement", 0) or 0),
                    "reaction": _reaction_line({
                        "pick": int(r.get("pick", 0) or 0),
                        "team": str(r.get("team", "?")),
                        "movement": int(r.get("movement", 0) or 0)}),
                })
            except Exception:
                continue
        # Reveal order mirrors the desktop countdown: 16..3, then #2/#1.
        tail = sorted([r for r in web_rows if r["pick"] >= 3],
                      key=lambda r: -r["pick"])
        head = sorted([r for r in web_rows if r["pick"] < 3],
                      key=lambda r: -r["pick"])
        return jsonify({"active": bool(web_rows), "year": year,
                        "reveal_order": tail + head,
                        "rows": sorted(web_rows, key=lambda r: r["pick"])})
    except Exception as e:
        return jsonify({"active": False, "rows": [], "error": str(e)})


@bp.route("/api/lottery/clear", methods=["POST"])
def api_lottery_clear():
    ok = enqueue_command("inbox_lottery_clear")
    return jsonify({"ok": ok, "queued": "inbox_lottery_clear"})
