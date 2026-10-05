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
_last_heartbeat = 0.0      # last time the browser tab pinged
_heartbeat_seen = False   # True once the tab has checked in at least once
_shutting_down = False


def set_app(game_app):
    """Attach the live game after web setup completes."""
    global _web_app_ref
    _web_app_ref = game_app


def server_running():
    """True if the Flask thread is already up (web setup flow)."""
    return _server_thread is not None and _server_thread.is_alive()


def note_heartbeat():
    global _last_heartbeat, _heartbeat_seen
    import time
    _last_heartbeat = time.time()
    _heartbeat_seen = True


def heartbeat_expired(timeout_s=150):
    """True if the browser tab has gone silent (closed/crashed)."""
    import time
    return (_heartbeat_seen and not _shutting_down
            and time.time() - _last_heartbeat > timeout_s)


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
        "position": _safe(lambda: str(getattr(p, "primary_position", "") or "") or "?"),
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
    wins = _safe(lambda: int(getattr(t, "wins", 0) or 0), 0)
    losses = _safe(lambda: int(getattr(t, "losses", 0) or 0), 0)
    otl = _safe(lambda: int(getattr(t, "ot_losses", 0) or 0), 0)
    return {
        "name": _safe(lambda: getattr(t, "team_name", "?")),
        "city": _safe(lambda: getattr(t, "city", "")),
        "abbr": _safe(lambda: getattr(t, "abbreviation", "") or
                      "".join(w[0] for w in str(getattr(t, "team_name", "?")).split()[:3]).upper()),
        "wins": wins,
        "losses": losses,
        "otl": otl,
        # JS hub expects team.record.{w,l,otl} (matches mock shape)
        "record": {"w": wins, "l": losses, "otl": otl},
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
    Uses the live _web_app_ref when set (web setup attaches the game late).
    """
    live = _web_app_ref if _web_app_ref is not None else app
    try:
        while True:
            try:
                cmd = COMMAND_QUEUE.get_nowait()
            except queue.Empty:
                break
            _execute_command(live, cmd)
    except Exception:
        pass
    # Browser tab gone silent? Shut the game down cleanly so no ghost
    # process lingers (the Sept-2026 exit-hang lesson, web edition).
    if _web_app_ref is not None and heartbeat_expired():
        try:
            _shutdown(root)
        except Exception:
            pass
        return
    try:
        root.after(250, lambda: drain_commands(app, root))
    except Exception:
        pass


_setup_root = None  # the hidden Tk root whose mainloop pumps commands


def _shutdown(root):
    """Quit the Tk mainloop and tear down roots so the process exits."""
    global _shutting_down
    _shutting_down = True
    roots = []
    try:
        if _setup_root is not None:
            roots.append(_setup_root)
    except Exception:
        pass
    try:
        if _web_app_ref is not None and _web_app_ref not in roots:
            roots.append(_web_app_ref)
    except Exception:
        pass
    if root is not None and root not in roots:
        roots.append(root)
    for r in roots:
        try:
            r.quit()      # stop whichever mainloop is running
        except Exception:
            pass
    for r in roots:
        try:
            r.destroy()   # tear down so the process can exit
        except Exception:
            pass


_web_setup_status = {"status": "idle"}  # idle|generating|ready|error


def _do_setup_new_game(cmd):
    """Create a new career from the web setup page (main thread)."""
    global _web_setup_status
    _web_setup_status = {"status": "generating", "detail": "Building league..."}
    try:
        import main as _main
        team = cmd.get("team") or "Boston Bruins"
        settings = {
            'database_size': 'Standard',
            'fantasy_draft': False,
            'user_team': team,
            'user_league': 'NHL',
            'gm_name': cmd.get("gm_name") or "General Manager",
            'fog_of_war': True,
            'sim_detail': {'NHL': 'full'},
            'playoff_format': 'divisional',
        }
        _web_setup_status = {"status": "generating",
                             "detail": "Generating players..."}
        gm = _main.GameManager()
        gm.apply_startup_settings(settings)
        gm.set_user_team(team)
        _web_setup_status = {"status": "generating",
                             "detail": "Starting game..."}
        app = _main.HockeyManagerGUI(gm)
        try:
            app.withdraw()  # the browser tab is the window
        except Exception:
            pass
        try:
            app.startup_settings = settings
        except Exception:
            pass
        set_app(app)
        _web_setup_status = {"status": "ready"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _web_setup_status = {"status": "error", "detail": str(e)}


def _do_setup_load_game(cmd):
    """Load a save from the web setup page (main thread)."""
    global _web_setup_status
    _web_setup_status = {"status": "generating", "detail": "Loading save..."}
    try:
        import main as _main
        from save_load_system import GameSaveManager
        path = cmd.get("path")
        gm = _main.GameManager()
        save_mgr = GameSaveManager(gm)
        if not path or not save_mgr.load_game(path):
            _web_setup_status = {"status": "error",
                                 "detail": "Could not load save."}
            return
        app = _main.HockeyManagerGUI(gm)
        try:
            app.withdraw()
        except Exception:
            pass
        if hasattr(app.game_manager, 'current_date'):
            app.current_date = app.game_manager.current_date
        if hasattr(app.game_manager, 'user_team'):
            app.user_team = app.game_manager.user_team
        try:
            app.update_all_views()
        except Exception:
            pass
        set_app(app)
        _web_setup_status = {"status": "ready"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _web_setup_status = {"status": "error", "detail": str(e)}


def _execute_command(app, cmd):
    """Run one queued command on the main thread. Never raises."""
    try:
        op = cmd.get("op")
        if op == "exit_game":
            _shutdown(_setup_root)
            return
        elif op == "setup_new_game":
            _do_setup_new_game(cmd)
            return
        elif op == "setup_load_game":
            _do_setup_load_game(cmd)
            return
        elif op == "advance_day":
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
        elif op == "claim_waiver":
            pid = cmd.get("player_id")
            try:
                team = getattr(app, "user_team", None)
                wire = getattr(app, "waiver_list", None) or []
                player = next((p for p in wire
                               if str(getattr(p, "id", "")) == str(pid)), None)
                if player is not None and team is not None:
                    fn = getattr(app, "_execute_waiver_claim", None)
                    if callable(fn):
                        fn(player, team)
            except Exception:
                pass
        elif op == "set_captains":
            try:
                team = getattr(app, "user_team", None)
                roster = list(getattr(team, "roster", None) or [])
                by_id = {str(getattr(p, "id", "")): p for p in roster}
                # clear existing letters first
                for p in roster:
                    if getattr(p, "captaincy", "") in ("C", "A"):
                        p.captaincy = ""
                cap = by_id.get(str(cmd.get("captain_id")))
                a1 = by_id.get(str(cmd.get("alt1_id")))
                a2 = by_id.get(str(cmd.get("alt2_id")))
                if cap is not None:
                    cap.captaincy = "C"
                for a in (a1, a2):
                    if a is not None and a is not cap:
                        a.captaincy = "A"
                try:
                    gm = getattr(app, "game_manager", None)
                    if gm is not None:
                        gm._captaincy_choice_pending = False
                except Exception:
                    pass
            except Exception:
                pass
        elif op == "save_game":
            try:
                fn = getattr(app, "open_save_window", None)
                if callable(fn):
                    fn()
            except Exception:
                pass
        elif op == "load_game":
            try:
                fn = getattr(app, "open_load_window", None)
                if callable(fn):
                    fn()
            except Exception:
                pass
        elif op == "sign_free_agent_real":
            # v2 web contract flow: validated UFA offer (years + AAV) from
            # the in-page modal. Re-validates with the real game gates,
            # then runs the real signing path:
            # HockeyManagerGUI.handle_contract_offer (main.py:21978).
            # Outcome stashed on app._web_contract_result for
            # GET /api/contracts/result polling (in-page, no OS popup).
            def _wc_store(ok, summary):
                try:
                    app._web_contract_result = {
                        "marker": "sign_free_agent_real",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                    }
                except Exception:
                    pass

            pid = cmd.get("player_id")
            try:
                years = int(cmd.get("years", 1))
            except (TypeError, ValueError):
                years = 0
            try:
                aav = int(cmd.get("aav", 0))
            except (TypeError, ValueError):
                aav = 0
            try:
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                team = getattr(app, "user_team", None)
                pool = list(getattr(league, "free_agents", None) or [])
                player = next((p for p in pool
                               if str(getattr(p, "id", id(p))) == str(pid)),
                              None)
                ok, reason = True, ""
                if player is None or team is None:
                    ok, reason = False, "Player not found."
                if ok:
                    import roster_limits as _rl
                    ok, reason = _rl.can_sign_player(player)
                if ok:
                    import transaction_windows as _tw
                    ok, reason = _tw.check_window(
                        "sign_ufa", getattr(app, "current_date", None))
                if ok:
                    ok, reason = app._validate_contract_terms(
                        player, aav, years, extension=False)
                if ok:
                    # Same staging as ContractNegotiationView.submit_offer
                    # (windows.py): the offer rides on the player object.
                    player.salary = aav
                    player.contract_years = years
                    # v3 multi-day negotiation: run the offer through the
                    # negotiation hook so a counter is stashed on
                    # app._web_negotiations (in addition to the inbox
                    # message) for the in-page modal. The hook itself
                    # calls the real handle_contract_offer(notify="inbox").
                    try:
                        from web_ui.screens import contracts as _neg_mod
                        _neg_mod.handle_offer_command(
                            app, pid, player, "sign", years, aav)
                    except Exception:
                        pass
                    _wc_store(True, "Offer submitted — the response will "
                                    "arrive in your inbox.")
                elif reason:
                    _wc_store(False, reason)
            except Exception:
                pass
        elif op == "extend_contract_real":
            # v2 web contract flow: validated extension (years + AAV) from
            # the in-page modal. Re-validates with the real game gates,
            # then runs the real re-sign path:
            # handle_contract_offer(extension=True) (main.py:21978).
            def _wc_store(ok, summary):
                try:
                    app._web_contract_result = {
                        "marker": "extend_contract_real",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                    }
                except Exception:
                    pass

            pid = cmd.get("player_id")
            try:
                years = int(cmd.get("years", 1))
            except (TypeError, ValueError):
                years = 0
            try:
                aav = int(cmd.get("aav", 0))
            except (TypeError, ValueError):
                aav = 0
            try:
                team = getattr(app, "user_team", None)
                roster = list(getattr(team, "roster", None) or [])
                player = next((p for p in roster
                               if str(getattr(p, "id", id(p))) == str(pid)),
                              None)
                ok, reason = True, ""
                if player is None or team is None:
                    ok, reason = False, "Player not found."
                if ok:
                    import transaction_windows as _tw
                    ok, reason = _tw.check_window(
                        "extension", getattr(app, "current_date", None),
                        ctx={"player": player})
                if ok:
                    ok, reason = app._validate_contract_terms(
                        player, aav, years, extension=True)
                if ok:
                    # Same staging as the desktop extension flow.
                    player.salary = aav
                    player.contract_years = years
                    # v3 multi-day negotiation: run the offer through the
                    # negotiation hook so a counter is stashed on
                    # app._web_negotiations (in addition to the inbox
                    # message) for the in-page modal. The hook itself
                    # calls the real handle_contract_offer(notify="inbox").
                    try:
                        from web_ui.screens import contracts as _neg_mod
                        _neg_mod.handle_offer_command(
                            app, pid, player, "extend", years, aav)
                    except Exception:
                        pass
                    _wc_store(True, "Extension submitted — the response "
                                    "will arrive in your inbox.")
                elif reason:
                    _wc_store(False, reason)
            except Exception:
                pass
        elif op == "negotiate_counter":
            # v3 multi-day negotiation: new counter-offer into an open
            # contract talk. Thin delegation: all logic lives in
            # web_ui/screens/contracts.py::handle_negotiation_command.
            try:
                from web_ui.screens import contracts as _neg_mod
                _neg_mod.handle_negotiation_command(app, cmd)
            except Exception:
                pass
        elif op == "negotiate_accept":
            # v3: accept the agent's counter as-is (real
            # HockeyManagerGUI.accept_contract_counter, main.py:22456).
            try:
                from web_ui.screens import contracts as _neg_mod
                _neg_mod.handle_negotiation_command(app, cmd)
            except Exception:
                pass
        elif op == "negotiate_walk":
            # v3: walk away (desktop equivalent:
            # inbox_window._on_contract_counter_walkaway ->
            # message.action_done = True; nothing happens to the game).
            try:
                from web_ui.screens import contracts as _neg_mod
                _neg_mod.handle_negotiation_command(app, cmd)
            except Exception:
                pass
        elif op == "add_scouting_assignment_real":
            # Web region assignment (replaces the v1 desktop fallback):
            # scout -> region on game_manager.scout_region_assignments
            # via scouting.set_scout_region (scouting.py:132).
            try:
                from web_ui.screens.scouting import apply_region_assignment
                apply_region_assignment(app, cmd.get("scout_id"),
                                        cmd.get("region"))
            except Exception:
                pass
        elif op == "add_scouting_assignment":
            # Replaces the old v1 desktop fallback ("open_scouting_window"):
            # real player-targeted assignment into app.scouting_assignments
            # via scouting_window_helpers.create_scout_assignment.
            try:
                from web_ui.screens.scouting import apply_player_assignment
                apply_player_assignment(app, cmd.get("prospect_id"),
                                        cmd.get("scout_id"))
            except Exception:
                pass
        elif op == "set_lines_real":
            # Web line editor: re-validate server-side, then apply through
            # the real machinery (quick_sim.flatten_lineup, same as the
            # desktop editor and _mp_set_lines).
            try:
                from web_ui.screens.lines import (validate_lines_payload,
                                                  apply_lines_payload)
                team = getattr(app, "user_team", None)
                slot_lines = cmd.get("lines") or {}
                ok, err, resolved = validate_lines_payload(team, slot_lines)
                if ok and resolved is not None:
                    apply_lines_payload(team, resolved)
            except Exception:
                pass
        elif op == "execute_trade":
            # Web trade builder (v2 modal): re-validate with the REAL AI
            # verdict, then call the REAL trade_engine.execute_trade().
            # Never executes a deal the AI rejects. Stashes the outcome on
            # app._web_trade_result for GET /api/trades/result polling.
            try:
                import trade_engine as _te
            except Exception:
                _te = None

            def _wt_store(ok, summary, verdict=""):
                try:
                    app._web_trade_result = {
                        "marker": "execute_trade",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                        "verdict": str(verdict or ""),
                    }
                except Exception:
                    pass

            try:
                if _te is None:
                    _wt_store(False, "Trade engine unavailable.", "")
                    return

                user_team = getattr(app, "user_team", None)
                gm = getattr(app, "game_manager", None)
                league = (getattr(gm, "league", None)
                          or getattr(app, "league", None))

                # Find the partner team (abbr, name, team_name, "City Name").
                target_id = str(cmd.get("target_team_id") or "").strip().lower()
                partner = None
                for _t in (getattr(league, "teams", None) or []):
                    _nm = str(getattr(_t, "team_name", "") or "")
                    _cands = {
                        str(getattr(_t, "abbreviation", "") or "").lower(),
                        _nm.lower(),
                        f"{getattr(_t, 'city', '')} {_nm}".strip().lower(),
                    }
                    if target_id and target_id in _cands:
                        partner = _t
                        break
                if user_team is None or partner is None:
                    _wt_store(False, "Could not resolve teams.", "")
                    return

                # Resolve asset ids -> live objects (players + picks).
                _pid_want = {str(x) for x in (cmd.get("give_pids") or [])}
                _pick_want = {str(x) for x in (cmd.get("give_picks") or [])}
                _pid_get = {str(x) for x in (cmd.get("want_pids") or [])}
                _pick_get = {str(x) for x in (cmd.get("want_picks") or [])}

                def _resolve(team, pid_set, pick_set):
                    _players, _picks = [], []
                    for _attr in ("roster", "ahl_roster", "prospects"):
                        for _p in (getattr(team, _attr, None) or []):
                            if str(getattr(_p, "id", "")) in pid_set:
                                _players.append(_p)
                    _by_year = getattr(team, "draft_picks", None) or {}
                    for _pk_list in _by_year.values():
                        for _pk in (_pk_list or []):
                            if str(getattr(_pk, "id", "")) in pick_set:
                                _picks.append(_pk)
                    return _players + _picks

                give_assets = _resolve(user_team, _pid_want, _pick_want)
                want_assets = _resolve(partner, _pid_get, _pick_get)
                if not give_assets and not want_assets:
                    _wt_store(False, "Empty proposal.", "")
                    return

                # Gap 2: salary retention + pick protection terms from the
                # web trade builder (cmd["retention"], cmd["pick_protection"]).
                # Server-side re-validation (the /api/trades/propose route
                # already validated; never trust the client twice):
                #   - pct must be 0 < pct <= MAX_RETENTION_PCT (engine: 50)
                #   - protection codes limited to the engine's real set
                #     ("top-3" | "top-10" | "lottery")
                #   - terms dropped for stale assets (not in this deal)
                #   - retention dry-run through the engine's own
                #     apply_retention_dry_run (3-slot club limit counting
                #     the deal's other terms via `extra`, 75-day
                #     double-retention clock, two-club rule) — a bad term
                #     fails here with a clear message, not BLOCKED later.
                try:
                    from game_classes import DraftPick as _DP_gap2
                except Exception:
                    _DP_gap2 = ()
                _wt_retention, _wt_protection = {}, {}
                try:
                    _give_pids = {str(getattr(_p, "id", ""))
                                  for _p in give_assets
                                  if not isinstance(_p, _DP_gap2)}
                    _give_pickids = {str(getattr(_p, "id", ""))
                                     for _p in give_assets
                                     if isinstance(_p, _DP_gap2)}
                    _raw_ret = cmd.get("retention") or {}
                    if isinstance(_raw_ret, dict):
                        for _k, _v in _raw_ret.items():
                            try:
                                _pct = float(_v)
                            except Exception:
                                continue
                            if 0 < _pct <= _te.MAX_RETENTION_PCT \
                                    and str(_k) in _give_pids:
                                _wt_retention[str(_k)] = _pct
                    _raw_prot = cmd.get("pick_protection") or {}
                    if isinstance(_raw_prot, dict):
                        for _k, _v in _raw_prot.items():
                            if str(_v) in ("top-3", "top-10", "lottery") \
                                    and str(_k) in _give_pickids:
                                _wt_protection[str(_k)] = str(_v)
                    if _wt_retention:
                        _by_id = {str(getattr(_p, "id", "")): _p
                                  for _p in give_assets
                                  if not isinstance(_p, _DP_gap2)}
                        for _pid, _pct in _wt_retention.items():
                            _pl = _by_id.get(_pid)
                            _extra = {k: v for k, v in _wt_retention.items()
                                      if k != _pid}
                            _ok2, _msg2 = _te.apply_retention_dry_run(
                                user_team, _pl, _pct, extra=_extra)
                            if not _ok2:
                                _wt_store(
                                    False,
                                    "Retained-salary term on "
                                    f"{getattr(_pl, 'full_name', _pid)} is "
                                    f"illegal ({_msg2}).",
                                    "")
                                return
                except Exception:
                    pass

                # RE-VALIDATE with the real AI before any mutation.
                # Retention is passed through: the AI's cap check prices
                # the reduced incoming hit exactly like a real GM pricing
                # retained money.
                try:
                    resp = _te.ai_consider_trade(
                        partner, give_assets, want_assets,
                        user_team=user_team, retention=_wt_retention)
                    verdict = str(getattr(resp, "decision", "") or "")
                    message = str(getattr(resp, "message", "") or "")
                except Exception:
                    _wt_store(False, "AI evaluation failed.", "")
                    return
                if verdict != "accept":
                    _wt_store(False,
                              f"GM rejected the deal: {message}", verdict)
                    return

                # Real execution on the Tk main thread (same call the
                # desktop flow uses via trade_negotiation._complete).
                from datetime import date as _dt
                _cur = getattr(gm, "current_date", None)
                date_str = str(_cur) if _cur else str(_dt.today())
                _board = getattr(getattr(app, "career", None), "board", None)
                # Gap 2: stamp pick protections on the live DraftPick objects
                # BEFORE execution (desktop flow: trade_negotiation
                # ._neg_terms(stamp=True)). Only reached after the AI
                # accepted, so a declined deal leaves no flags.
                for _pk in give_assets:
                    if not isinstance(_pk, _DP_gap2):
                        continue
                    _prot = _wt_protection.get(
                        str(getattr(_pk, "id", "")))
                    if _prot:
                        try:
                            _pk.protection = _prot
                            _pk.is_conditional = True
                            _pk.condition = (
                                f"{_te.protection_label(_prot)}: if this pick "
                                f"falls in the protected range, "
                                f"{getattr(_pk, 'original_team', 'the original club')} "
                                f"keeps it and the holder receives their "
                                f"next-year 1st-rounder instead.")
                        except Exception:
                            pass
                trade = _te.execute_trade(
                    user_team, partner, give_assets, want_assets,
                    date_str, league=league, board=_board,
                    retention=_wt_retention)
                summary = str(getattr(trade, "summary", "") or "")
                if summary.startswith("BLOCKED:"):
                    _wt_store(False, summary[8:].strip(), verdict)
                    return
                try:
                    if not hasattr(gm, "trade_history"):
                        gm.trade_history = []
                    gm.trade_history.append(trade)
                except Exception:
                    pass
                _wt_store(True, summary or "Trade completed.", verdict)
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

    @app.route("/api/heartbeat", methods=["POST"])
    def heartbeat():
        note_heartbeat()
        return jsonify({"ok": True})

    @app.route("/api/exit", methods=["POST"])
    def exit_game():
        # User clicked Exit in the web UI: shut down cleanly.
        enqueue_command("exit_game")
        return jsonify({"ok": True})

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
