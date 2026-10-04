# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Web UI bridge (2026-10-04).

Connects the Flask web frontend to the live game. Same-process design:

- READS: Flask handlers read the live GameManager/user_team objects
  directly. Never touch a Tk widget from a Flask thread.
- WRITES: Flask POSTs enqueue command dicts on COMMAND_QUEUE; the Tk
  mainloop drains them via root.after(). This keeps all mutation on the
  main thread where Tkinter is safe.

Serialization: game objects -> plain dicts via the to_web_* helpers.
Never leak raw model objects to JSON.

Usage (from the game):
    from web_ui.bridge import start_web_server
    start_web_server(app)   # app = HockeyManagerGUI instance
"""
import queue
import threading
from datetime import date, datetime

COMMAND_QUEUE = queue.Queue()
_web_app_ref = None       # the live HockeyManagerGUI (or mock in tests)
_server_thread = None


# ------------------------------------------------------------------
# Serialization helpers
# ------------------------------------------------------------------
def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def to_web_player(p):
    """Player -> JSON-safe dict."""
    return {
        "id": _safe(lambda: str(getattr(p, "id", id(p)))),
        "name": _safe(lambda: getattr(p, "full_name", "?")),
        "position": _safe(lambda: getattr(p, "position", "?")),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
        "overall": _safe(lambda: int(getattr(p, "overall", 0) or 0)),
        "salary": _safe(lambda: int(getattr(p, "salary", 0) or 0)),
        "captaincy": _safe(lambda: getattr(p, "captaincy", "") or ""),
        "injured": _safe(lambda: bool(getattr(p, "injured", False))),
    }


def to_web_message(m):
    """EmailMessage -> JSON-safe dict (Gmail-style row data)."""
    try:
        overdue = bool(m.is_overdue())
    except Exception:
        overdue = False
    try:
        age = int(m.get_age_days())
    except Exception:
        age = 0
    if age <= 0:
        date_str = "Today"
    elif age == 1:
        date_str = "Yesterday"
    else:
        try:
            date_str = m.date_sent.strftime("%m/%d")
        except Exception:
            date_str = ""
    snippet = _safe(lambda: (getattr(m, "content", "") or "").replace("\n", " ").strip()[:120], "")
    return {
        "id": _safe(lambda: str(getattr(m, "id", ""))),
        "sender": _safe(lambda: getattr(m, "sender", "") or "(no sender)"),
        "subject": _safe(lambda: getattr(m, "subject", "") or "(no subject)"),
        "snippet": snippet,
        "category": _safe(lambda: getattr(m, "category", "General")),
        "date": date_str,
        "is_read": _safe(lambda: bool(getattr(m, "is_read", False))),
        "is_urgent": _safe(lambda: bool(getattr(m, "is_urgent", False))),
        "is_important": _safe(lambda: bool(getattr(m, "is_important", False))),
        "requires_response": _safe(lambda: bool(getattr(m, "requires_response", False))),
        "is_overdue": overdue,
        "is_saved": _safe(lambda: bool(getattr(m, "is_saved", False))),
        "priority": _safe(lambda: int(getattr(m, "priority", 1) or 1)),
    }


def to_web_team(t):
    """Team -> JSON-safe dict (hub header data)."""
    return {
        "name": _safe(lambda: getattr(t, "team_name", "?")),
        "city": _safe(lambda: getattr(t, "city", "")),
        "abbr": _safe(lambda: getattr(t, "abbreviation", "") or
                      "".join(w[0] for w in str(getattr(t, "team_name", "?")).split()[:3]).upper()),
        "wins": _safe(lambda: int(getattr(t, "wins", 0) or 0)),
        "losses": _safe(lambda: int(getattr(t, "losses", 0) or 0)),
        "otl": _safe(lambda: int(getattr(t, "ot_losses", 0) or 0)),
        "roster_size": _safe(lambda: len(getattr(t, "roster", None) or [])),
    }


def get_hub_state(app):
    """Full hub payload from the live game."""
    team = _safe(lambda: app.user_team)
    gm = _safe(lambda: app.game_manager)
    inbox = _safe(lambda: team.inbox) if team else None

    cur_date = _safe(lambda: gm.current_date)
    if isinstance(cur_date, (date, datetime)):
        date_str = cur_date.strftime("%B %d, %Y")
    else:
        date_str = str(cur_date or "")

    unread = _safe(lambda: int(getattr(inbox, "unread_count", 0) or 0), 0)
    action_needed = 0
    if inbox:
        for m in _safe(lambda: list(inbox.messages), []) or []:
            try:
                if getattr(m, "requires_response", False) or m.is_overdue():
                    action_needed += 1
            except Exception:
                pass

    t = to_web_team(team) if team else {}
    pts = t.get("wins", 0) * 2 + t.get("otl", 0)

    return {
        "team": {**t, "points": pts},
        "date": date_str,
        "inbox": {"unread": unread, "action_needed": action_needed},
        "tiles": [
            {"id": "continue", "title": "Continue", "subtitle": "Advance the day",
             "size": "hero", "icon": "▶", "accent": True},
            {"id": "roster", "title": "Roster",
             "subtitle": f"{t.get('roster_size', 0)} players",
             "size": "large", "icon": "🏒"},
            {"id": "inbox", "title": "Inbox",
             "subtitle": f"{unread} unread" +
                         (f" · {action_needed} need action" if action_needed else ""),
             "size": "medium", "icon": "✉️", "badge": unread or None},
            {"id": "schedule", "title": "Schedule", "subtitle": "Season schedule",
             "size": "medium", "icon": "📅"},
            {"id": "stats", "title": "Team Stats",
             "subtitle": f"{t.get('wins', 0)}-{t.get('losses', 0)}-{t.get('otl', 0)}",
             "size": "medium", "icon": "📊"},
            {"id": "lines", "title": "Lines", "subtitle": "Line combinations",
             "size": "small", "icon": "📋"},
            {"id": "trades", "title": "Trades", "subtitle": "Trade center",
             "size": "small", "icon": "🔄"},
            {"id": "scouting", "title": "Scouting", "subtitle": "Assignments",
             "size": "small", "icon": "🔭"},
            {"id": "staff", "title": "Staff", "subtitle": "Coaches & management",
             "size": "small", "icon": "👔"},
            {"id": "watch", "title": "Watch Game", "subtitle": "Live visualizer",
             "size": "medium", "icon": "📺"},
        ],
    }


def get_inbox_messages(app, filter_type="all"):
    """Inbox messages for the web UI, newest first."""
    team = _safe(lambda: app.user_team)
    inbox = _safe(lambda: team.inbox) if team else None
    if inbox is None:
        return []
    msgs = _safe(lambda: list(inbox.messages), []) or []
    if filter_type == "unread":
        msgs = [m for m in msgs if not _safe(lambda: m.is_read, False)]
    elif filter_type == "urgent":
        msgs = [m for m in msgs
                if _safe(lambda: m.is_urgent, False) or _safe(lambda: m.priority, 1) >= 4]
    elif filter_type == "action":
        msgs = [m for m in msgs
                if _safe(lambda: m.requires_response, False)]
    elif filter_type == "saved":
        msgs = [m for m in msgs if _safe(lambda: m.is_saved, False)]
    return [to_web_message(m) for m in msgs]


def get_roster(app):
    """User team roster for the web UI."""
    team = _safe(lambda: app.user_team)
    if team is None:
        return []
    return [to_web_player(p) for p in _safe(lambda: list(team.roster), []) or []]


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


# Blocker ID -> web page that helps resolve it (None = desktop app only).
BLOCKER_WEB_ROUTES = {
    "roster_limit_23": "/roster",
    "dress_minimum": "/roster",
    "salary_cap": "/roster",
    "salary_floor": "/roster",
    "captaincy_choice": "/roster",
    "fantasy_draft": None,
    "entry_draft": None,
    "season_integrity": None,
}


def get_continue_state(app):
    """Continue button state + JSON-safe blockers for the web modal."""
    label, blockers = _safe(lambda: app.get_continue_state(), ("Continue", [])) or ("Continue", [])
    web_blockers = []
    for b in blockers or []:
        try:
            bid = b.get("id", "")
            auto = b.get("auto_action")
            web_blockers.append({
                "id": bid,
                "title": b.get("title", ""),
                "detail": b.get("detail", ""),
                "has_auto": bool(auto),
                "auto_label": (auto[0] if isinstance(auto, (list, tuple)) and auto else "Auto-resolve"),
                "web_route": BLOCKER_WEB_ROUTES.get(bid),
            })
        except Exception:
            continue
    return {"label": label, "blocked": bool(web_blockers), "blockers": web_blockers}


def get_schedule(app, limit=40):
    """Upcoming games for the user team, chronological."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: app.user_team)
    if gm is None or team is None:
        return []
    my_name = _safe(lambda: team.team_name, "")
    today = _safe(lambda: gm.current_date)
    sched = _safe(lambda: list(getattr(getattr(gm, "league", None), "schedule", None) or []), []) or []
    out = []
    for g in sched:
        try:
            if not isinstance(g, dict):
                continue
            gd = g.get("date")
            home = _team_name(g.get("home_team"))
            away = _team_name(g.get("away_team"))
            if my_name and my_name not in (home, away):
                continue
            if today and isinstance(gd, (date, datetime)) and gd < today:
                continue
            out.append({
                "date": gd.strftime("%a %m/%d") if isinstance(gd, (date, datetime)) else str(gd),
                "home": home,
                "away": away,
                "is_home": home == my_name,
                "opponent": away if home == my_name else home,
                "preseason": bool(g.get("preseason", False)),
            })
        except Exception:
            continue
    # chronological
    try:
        out.sort(key=lambda x: x["date"])
    except Exception:
        pass
    return out[:limit]


# ------------------------------------------------------------------
# Command queue (web -> game writes, drained on the Tk main thread)
# ------------------------------------------------------------------
def enqueue_command(op, **kwargs):
    """Queue a write op for the main thread. Never raises."""
    try:
        COMMAND_QUEUE.put({"op": op, **kwargs})
        return True
    except Exception:
        return False


def drain_commands(app, root):
    """Drain the queue on the Tk main thread; reschedules itself.

    Call once from the GUI: root.after(100, lambda: drain_commands(app, root))
    """
    try:
        while True:
            try:
                cmd = COMMAND_QUEUE.get_nowait()
            except queue.Empty:
                break
            _execute_command(app, cmd)
    except Exception:
        pass
    try:
        root.after(250, lambda: drain_commands(app, root))
    except Exception:
        pass


def _execute_command(app, cmd):
    """Run one queued command on the main thread. Never raises."""
    try:
        op = cmd.get("op")
        if op == "advance_day":
            fn = getattr(app, "advance_day", None) or getattr(app, "_on_continue", None)
            if callable(fn):
                fn()
        elif op == "mark_read":
            mid = cmd.get("message_id")
            team = getattr(app, "user_team", None)
            inbox = getattr(team, "inbox", None)
            if inbox and mid:
                try:
                    inbox.mark_message_read(mid)
                except Exception:
                    pass
        elif op == "resolve_blocker":
            bid = cmd.get("blocker_id")
            kind = cmd.get("kind", "auto")  # auto | primary | secondary
            try:
                _, blockers = app.get_continue_state()
                for b in blockers or []:
                    if b.get("id") != bid:
                        continue
                    key = {"auto": "auto_action", "primary": "action",
                           "secondary": "secondary_action"}.get(kind, "auto_action")
                    act = b.get(key)
                    fn = act[1] if isinstance(act, (list, tuple)) and len(act) > 1 else None
                    if callable(fn):
                        fn()
                    break
            except Exception:
                pass
        elif op == "delete_message":
            mid = cmd.get("message_id")
            team = getattr(app, "user_team", None)
            inbox = getattr(team, "inbox", None)
            if inbox and mid:
                try:
                    inbox.delete_message(mid)
                except Exception:
                    pass
    except Exception:
        pass


# ------------------------------------------------------------------
# Flask app factory
# ------------------------------------------------------------------
def create_app(game_app=None):
    """Build the Flask app bound to a game app (or None for mock mode)."""
    import os
    from flask import Flask, jsonify, render_template, request

    global _web_app_ref
    if game_app is not None:
        _web_app_ref = game_app

    here = os.path.dirname(__file__)
    app = Flask(__name__,
                template_folder=os.path.join(here, "templates"),
                static_folder=os.path.join(here, "static"))

    # Screen blueprints: each screen is self-contained (API + page route)
    # in web_ui/screens/<name>.py so parallel work never conflicts.
    try:
        import importlib, pkgutil
        import web_ui.screens as _screens_pkg
        for _mod in pkgutil.iter_modules(_screens_pkg.__path__):
            try:
                _m = importlib.import_module(f"web_ui.screens.{_mod.name}")
                _bp = getattr(_m, "bp", None)
                if _bp is not None:
                    app.register_blueprint(_bp)
            except Exception as e:
                print(f"Web UI screen '{_mod.name}' failed to load: {e}")
    except Exception:
        pass

    def _live():
        return _web_app_ref

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/inbox")
    def inbox_page():
        return render_template("inbox.html")

    @app.route("/roster")
    def roster_page():
        return render_template("roster.html")

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True,
                        "mode": "live" if _live() else "mock"})

    @app.route("/api/state")
    def state():
        live = _live()
        if live is None:
            # mock fallback (POC data)
            from web_ui.server import MOCK_STATE  # noqa
            return jsonify(MOCK_STATE)
        return jsonify(get_hub_state(live))

    @app.route("/api/inbox")
    def inbox():
        live = _live()
        if live is None:
            return jsonify([])
        f = request.args.get("filter", "all")
        return jsonify(get_inbox_messages(live, f))

    @app.route("/api/roster")
    def roster():
        live = _live()
        if live is None:
            return jsonify([])
        return jsonify(get_roster(live))

    @app.route("/api/schedule")
    def schedule():
        live = _live()
        if live is None:
            return jsonify([])
        return jsonify(get_schedule(live))

    @app.route("/schedule")
    def schedule_page():
        return render_template("schedule.html")

    @app.route("/api/continue_state")
    def continue_state():
        live = _live()
        if live is None:
            return jsonify({"label": "Continue", "blocked": False, "blockers": []})
        return jsonify(get_continue_state(live))

    @app.route("/api/command", methods=["POST"])
    def command():
        data = request.get_json(force=True, silent=True) or {}
        op = data.get("op")
        if not op:
            return jsonify({"ok": False, "error": "no op"}), 400
        ok = enqueue_command(op, **{k: v for k, v in data.items() if k != "op"})
        return jsonify({"ok": ok, "queued": op})

    return app


def start_web_server(game_app, port=5050):
    """Start Flask in a background thread bound to the live game."""
    global _server_thread
    if _server_thread is not None and _server_thread.is_alive():
        return _server_thread
    app = create_app(game_app)

    def _run():
        try:
            app.run(host="127.0.0.1", port=port, threaded=True,
                    use_reloader=False)
        except Exception as e:
            print(f"Web UI server failed: {e}")

    _server_thread = threading.Thread(target=_run, daemon=True,
                                      name="puck-web-ui")
    _server_thread.start()
    return _server_thread
