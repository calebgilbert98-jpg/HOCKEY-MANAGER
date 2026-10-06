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


# ======================================================================
# Batch D: Inbox gaps.
# Desktop parity (inbox_window.py):
#   - 6 category pills (All/Unread/Urgent/Saved + Story + the message
#     categories: Trade/Scouting/Contracts/Injuries/Media/League).
#   - Story view: unified chronological narrative surface -- active
#     storylines, hot rivalries, milestones, the Media/League feed.
#   - Search across sender/subject/content.
#   - Compose / Reply / Forward: real editor flow (desktop
#     _MessageEditor) -- a real EmailMessage is appended to the inbox;
#     reply marks the original read and clears requires_response.
#   - Mark All Read (desktop _mark_all_read).
#   - Save / Important flagging (desktop _toggle_save_current /
#     _mark_current_important).
# Writes go through bridge command ops (main-thread safe); reads are
# direct (read-only).
# ======================================================================

_INBOX_FILTERS = [
    ("All", "all"), ("Unread", "unread"), ("Urgent", "urgent"),
    ("Saved", "saved"), ("📖 Story", "story"),
    ("Trade", "Trade"), ("Scouting", "Scouting"),
    ("Contracts", "Contracts"), ("Injuries", "Injuries"),
    ("Media", "Media"), ("League", "League"),
]

_STORY_KIND_ICONS = {
    "rivalry": "🔥", "milestone": "🏆", "controversy": "⚡",
    "streak": "📈", "trade": "🔄", "injury": "🩹",
}


def _inbox_of(app):
    team = _user_team(app)
    return _safe(lambda: getattr(team, "inbox", None))


def _all_messages(app):
    inbox = _inbox_of(app)
    return _safe(lambda: list(getattr(inbox, "messages", None) or []),
                 []) or []


@bp.route("/api/inbox/filters")
def api_inbox_filters():
    """Category pills with live counts (desktop _FILTERS)."""
    live = _live()
    if live is None:
        return jsonify({"filters": []})
    msgs = _all_messages(live)
    counts = {}
    for m in msgs:
        try:
            cat = str(getattr(m, "category", "General") or "General")
            counts[cat] = counts.get(cat, 0) + 1
            if not _safe(lambda: getattr(m, "is_read", True), True):
                counts["unread"] = counts.get("unread", 0) + 1
            if _safe(lambda: getattr(m, "is_urgent", False), False):
                counts["urgent"] = counts.get("urgent", 0) + 1
            if _safe(lambda: getattr(m, "is_saved", False), False):
                counts["saved"] = counts.get("saved", 0) + 1
        except Exception:
            continue
    counts["all"] = len(msgs)
    out = []
    for label, key in _INBOX_FILTERS:
        if key == "story":
            n = None
        elif key in counts:
            n = counts[key]
        else:
            n = 0
        out.append({"label": label, "key": key, "count": n})
    return jsonify({"filters": out})


@bp.route("/api/inbox/search")
def api_inbox_search():
    """Search sender/subject/content (case-insensitive substring)."""
    live = _live()
    if live is None:
        return jsonify({"messages": []})
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"messages": []})
    out = []
    for m in _all_messages(live):
        try:
            hay = " ".join([
                str(getattr(m, "sender", "") or ""),
                str(getattr(m, "subject", "") or ""),
                str(getattr(m, "content", "") or "")[:2000],
            ]).lower()
            if q in hay:
                d = to_web_message(m)
                d["special_action"] = _inbox_special_action(
                    live, _gm(live), m)
                out.append(d)
        except Exception:
            continue
    return jsonify({"messages": out[:100], "query": q})


def _story_developing(app):
    """Live narrative state: active storylines + hot rivalries
    (desktop _collect_developing). Never raises."""
    items = []
    gm = _gm(app)
    league = _safe(lambda: getattr(gm, "league", None))
    now = _safe(lambda: getattr(gm, "current_date", None))
    try:
        for n in (getattr(league, "media_narratives", None) or []):
            try:
                heat = float(getattr(n, "heat", 0) or 0)
                kind = str(getattr(n, "kind", "") or "")
                items.append({
                    "icon": _STORY_KIND_ICONS.get(kind, "📰"),
                    "title": str(getattr(n, "title",
                                        "Developing storyline") or ""),
                    "desc": f"{getattr(n, 'team_name', '')} · "
                            f"heat {heat:.0f}/100",
                    "heat": heat,
                })
            except Exception:
                continue
    except Exception:
        pass
    try:
        ms = _safe(lambda: getattr(gm, "media_system", None))
        for s in (getattr(ms, "storylines", None) or []):
            try:
                try:
                    active = s.is_active(now) if now is not None else True
                except Exception:
                    active = True
                if not active:
                    continue
                inten = int(getattr(s, "intensity", 5) or 5)
                items.append({
                    "icon": "📰",
                    "title": str(getattr(s, "title", "") or "Storyline"),
                    "desc": f"intensity {inten}/10",
                    "heat": inten * 10.0,
                })
            except Exception:
                continue
    except Exception:
        pass
    try:
        seen = set()
        for r in (getattr(league, "rivalries", None) or []):
            try:
                if not isinstance(r, dict) or r.get("kind") != "team_team":
                    continue
                heat = float(r.get("intensity", 0) or 0)
                if heat < 50:
                    continue
                key = (r.get("a"), r.get("b"))
                if key in seen:
                    continue
                seen.add(key)
                label = "Bad blood" if heat >= 65 else "Heated"
                items.append({
                    "icon": "🔥",
                    "title": f"{r.get('a_name') or '?'} vs "
                            f"{r.get('b_name') or '?'}",
                    "desc": f"{label} · {heat:.0f}/100",
                    "heat": heat,
                })
            except Exception:
                continue
    except Exception:
        pass
    items.sort(key=lambda d: d.get("heat", 0), reverse=True)
    return items[:8]


def _story_feed(app, limit=60):
    """Chronological backbone: recent Media/League messages."""
    out = []
    try:
        msgs = [m for m in _all_messages(app)
                if str(getattr(m, "category", "") or "")
                in ("Media", "League")]
    except Exception:
        return out

    def _d(m):
        return (_safe(lambda: getattr(m, "game_date_sent", None))
                or _safe(lambda: getattr(m, "date_sent", None)))

    try:
        msgs.sort(key=lambda m: (_d(m) is None, _d(m)), reverse=True)
    except Exception:
        pass
    gm = _gm(app)
    for m in msgs[:limit]:
        try:
            d = to_web_message(m)
            d["special_action"] = _inbox_special_action(app, gm, m)
            d["date_iso"] = (_d(m).isoformat()
                             if hasattr(_d(m), "isoformat") else "")
            out.append(d)
        except Exception:
            continue
    return out


@bp.route("/api/inbox/story")
def api_inbox_story():
    """Season Story view: developing narratives + chronological feed."""
    live = _live()
    if live is None:
        return jsonify({"developing": [], "feed": []})
    return jsonify({
        "developing": _story_developing(live),
        "feed": _story_feed(live),
    })


def _find_msg(app, mid):
    for m in _all_messages(app):
        try:
            if str(_safe(lambda: getattr(m, "id", ""), "")) == str(mid):
                return m
        except Exception:
            continue
    return None


@bp.route("/api/inbox/mark_all_read", methods=["POST"])
def api_inbox_mark_all_read():
    """Mark every message read (desktop _mark_all_read)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    ok = enqueue_command("inbox_mark_all_read")
    return jsonify({"ok": bool(ok)})


@bp.route("/api/inbox/flag", methods=["POST"])
def api_inbox_flag():
    """Save / Important flagging: {"message_id", "flag": "saved"|
    "important", "value": bool}. Desktop _toggle_save_current /
    _mark_current_important."""
    data = request.get_json(force=True, silent=True) or {}
    mid = data.get("message_id")
    flag = str(data.get("flag") or "")
    if not mid or flag not in ("saved", "important"):
        return jsonify({"ok": False, "error": "message_id and flag "
                        "(saved|important) required"}), 400
    value = data.get("value", None)
    ok = enqueue_command("inbox_flag", message_id=str(mid), flag=flag,
                         value=None if value is None else bool(value))
    return jsonify({"ok": bool(ok)})


@bp.route("/api/inbox/read", methods=["POST"])
def api_inbox_read():
    """Mark one message read/unread: {"message_id", "read": bool}."""
    data = request.get_json(force=True, silent=True) or {}
    mid = data.get("message_id")
    if not mid:
        return jsonify({"ok": False, "error": "message_id required"}), 400
    ok = enqueue_command("inbox_read", message_id=str(mid),
                         read=bool(data.get("read", True)))
    return jsonify({"ok": bool(ok)})


def _compose_prefill(app, mid, mode):
    """Desktop _reply_to_current / _forward_current prefill."""
    m = _find_msg(app, mid) if mid else None
    if mode == "reply" and m is not None:
        subject = str(getattr(m, "subject", "") or "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        return {
            "to": str(getattr(m, "sender", "") or ""),
            "to_locked": True,
            "subject": subject,
            "body": "",
            "category": str(getattr(m, "category", "") or "General"),
        }
    if mode == "forward" and m is not None:
        subject = str(getattr(m, "subject", "") or "")
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        quoted = (f"--- Forwarded message ---\n"
                  f"From: {getattr(m, 'sender', '') or ''}\n"
                  f"Subject: {getattr(m, 'subject', '') or ''}\n\n"
                  f"{getattr(m, 'content', '') or ''}")
        return {
            "to": "", "to_locked": False, "subject": subject,
            "body": quoted,
            "category": str(getattr(m, "category", "") or "General"),
        }
    return {"to": "", "to_locked": False, "subject": "",
            "body": "", "category": "General"}


@bp.route("/api/inbox/compose_prefill")
def api_inbox_compose_prefill():
    """Editor prefill for compose (?mode=compose) / reply / forward
    (?message_id=)."""
    live = _live()
    if live is None:
        return jsonify(_compose_prefill(None, None, "compose"))
    mode = (request.args.get("mode") or "compose").lower()
    return jsonify(_compose_prefill(
        live, request.args.get("message_id"), mode))


@bp.route("/api/inbox/send", methods=["POST"])
def api_inbox_send():
    """Send a composed/replied/forwarded message: {"to", "subject",
    "body", "category", "mode", "message_id?"}. Desktop _MessageEditor
    Send: builds a real EmailMessage and appends it to the inbox; a
    reply marks the original read and clears requires_response."""
    data = request.get_json(force=True, silent=True) or {}
    subject = str(data.get("subject") or "").strip()
    body = str(data.get("body") or "").strip()
    if not subject and not body:
        return jsonify({"ok": False,
                        "error": "subject or body required"}), 400
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    ok = enqueue_command(
        "inbox_send",
        to=str(data.get("to") or ""),
        subject=subject, body=body,
        category=str(data.get("category") or "General"),
        mode=str(data.get("mode") or "compose"),
        message_id=str(data.get("message_id") or ""))
    return jsonify({"ok": bool(ok)})
