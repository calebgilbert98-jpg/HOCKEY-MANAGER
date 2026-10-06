# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Web multiplayer: host/join lobbies for the web setup page.

Wraps multiplayer.net_host / net_client (same TCP protocol as the
v0.18.4 desktop launcher). The host's game is created through the
normal setup flow with multiplayer_host=True; _do_setup_new_game
wires the MultiplayerHost after the game exists.
"""
import socket
import threading

from flask import Blueprint, jsonify, request

bp = Blueprint("multiplayer", __name__)

# Module state (single host or client at a time)
_mp_host = None
_mp_host_thread = None
_mp_client = None
_mp_client_thread = None
_mp_client_snapshot = None  # (save_bytes, label) when host starts the game
_mp_pending_config = None  # {name, port} for host wiring after setup


def _local_ips():
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


def get_pending_host_config():
    """Consumed by _do_setup_new_game after the game is created."""
    global _mp_pending_config
    cfg = _mp_pending_config
    _mp_pending_config = None
    return cfg


def get_host():
    return _mp_host


def get_client():
    return _mp_client


def clear_client_snapshot():
    """Consume the pending start-game snapshot (after it was applied)."""
    global _mp_client_snapshot
    _mp_client_snapshot = None


def consume_last_sync():
    """Pop the latest STATE_SYNC bytes (client side re-sync)."""
    global _mp_client_last_sync
    out = _mp_client_last_sync
    _mp_client_last_sync = None
    return out


@bp.route("/api/mp/host", methods=["POST"])
def api_mp_host():
    """Stage a host config; the actual MultiplayerHost starts after setup."""
    global _mp_pending_config
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "Host").strip() or "Host"
    try:
        port = int(data.get("port") or 27107)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "port must be a number"}), 400
    _mp_pending_config = {"name": name, "port": port}
    return jsonify({"ok": True, "name": name, "port": port,
                    "ips": _local_ips(),
                    "note": "Configure your game, then Start — the lobby opens after."})


def wire_host(app, gm, name, port):
    """Attach a MultiplayerHost to a freshly created game (main thread)."""
    global _mp_host
    import gzip
    import pickle
    from multiplayer.net_host import MultiplayerHost
    try:
        save_mgr = app.save_manager
    except AttributeError:
        return None, "no save manager"

    def _state_provider():
        blob = gzip.compress(pickle.dumps(
            save_mgr.create_save_data(),
            protocol=pickle.HIGHEST_PROTOCOL))
        return blob, str(app.current_date), "host-sync"

    def _get_teams():
        try:
            return [{"id": t.team_name, "name": t.team_name}
                    for t in gm.league.teams]
        except Exception:
            return []

    try:
        host = MultiplayerHost(_state_provider, host_name=name,
                               port=port, get_teams=_get_teams)
        host.start()
    except OSError as e:
        return None, f"could not bind port {port}: {e}"
    except Exception as e:
        return None, str(e)
    _mp_host = host
    try:
        app.mp_host = host
    except Exception:
        pass
    # Desktop parity (enhanced_launcher._start_mp_host): the host manages
    # the picked team locally; seed GM reservations so seats survive
    # restarts; mark web mode so _mp_offer_to_host stashes offers for the
    # in-page Accept/Reject card instead of a blocking Tk dialog.
    # (Batch E, 2026-10-06. The MP network queues are pumped by
    # bridge._pump_mp_web on the setup root's mainloop -- this root runs
    # no mainloop of its own, so after()-scheduled polling never fires.)
    try:
        _htm = getattr(app, "user_team", None)
        if _htm is not None:
            host.host_team_id = _htm.team_name
    except Exception:
        pass
    try:
        app._mp_web_host_offers = {}
    except Exception:
        pass
    try:
        _seed = getattr(app, "_mp_seed_host_reservations", None)
        if callable(_seed):
            _seed(host)
    except Exception:
        pass
    return host, None


@bp.route("/api/mp/lobby")
def api_mp_lobby():
    host = _mp_host
    if host is None:
        return jsonify({"ok": False, "error": "not hosting"})
    try:
        members = host.get_lobby()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "members": members,
                    "count": len(members)})


@bp.route("/api/mp/start", methods=["POST"])
def api_mp_start():
    """Host starts the league: broadcast START_GAME + snapshot."""
    host = _mp_host
    if host is None:
        return jsonify({"ok": False, "error": "not hosting"}), 400
    try:
        host.start_game()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/mp/join", methods=["POST"])
def api_mp_join():
    """Connect to a host as a client."""
    global _mp_client
    data = request.get_json(force=True, silent=True) or {}
    ip = (data.get("ip") or "").strip()
    name = (data.get("name") or "Guest").strip() or "Guest"
    try:
        port = int(data.get("port") or 27107)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "port must be a number"}), 400
    if not ip:
        return jsonify({"ok": False, "error": "host IP required"}), 400
    from multiplayer.net_client import MultiplayerClient
    # Disconnect any previous client
    if _mp_client is not None:
        try:
            _mp_client.disconnect()
        except Exception:
            pass
    client = MultiplayerClient(name)
    try:
        welcome = client.connect(ip, port)
    except Exception as e:
        return jsonify({"ok": False, "error": f"connect failed: {e}"}), 500
    _mp_client = client
    teams = []
    try:
        teams = (welcome or {}).get("teams") or []
    except Exception:
        pass
    claimed = set()
    try:
        # lobby info may include claimed teams
        lobby = (welcome or {}).get("lobby") or []
        for m in lobby:
            if m.get("team_id"):
                claimed.add(m["team_id"])
    except Exception:
        pass
    return jsonify({"ok": True,
                    "teams": [{"id": t.get("id"), "name": t.get("name"),
                               "claimed": t.get("id") in claimed}
                              for t in teams]})


@bp.route("/api/mp/claim", methods=["POST"])
def api_mp_claim():
    client = _mp_client
    if client is None:
        return jsonify({"ok": False, "error": "not connected"}), 400
    data = request.get_json(force=True, silent=True) or {}
    team_id = data.get("team_id")
    if not team_id:
        return jsonify({"ok": False, "error": "team_id required"}), 400
    try:
        client.claim_team(team_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/mp/status")
def api_mp_status():
    """Poll for game start (client side, setup page -- no game yet).

    The client's network queue is drained here directly (the Tk-thread
    pump only runs once a game exists). START_GAME arrives as
    "game_started"; the snapshot itself rides the follow-up STATE_SYNC
    ("state_sync"). Both are captured into _mp_client_snapshot for the
    setup page to fetch via /api/mp/snapshot.
    """
    global _mp_client_snapshot
    client = _mp_client
    if client is None:
        return jsonify({"ok": False, "error": "not connected"})
    try:
        for kind, payload in client.poll_events():
            if kind == "state_sync":
                _mp_client_snapshot = (
                    payload.get("save_bytes"),
                    payload.get("label") or "Joined game",
                )
            elif kind == "game_started":
                # Snapshot follows via state_sync; mark intent so a bare
                # START_GAME (no sync, e.g. mid-draft starts) still flips
                # the flag -- /api/mp/sync covers the bytes when present.
                if _mp_client_snapshot is None:
                    _mp_client_snapshot = (b"", "Game started")
    except Exception:
        pass
    started = _mp_client_snapshot is not None and \
        _mp_client_snapshot[0] is not None
    return jsonify({"ok": True, "game_started": started,
                    "connected": client.connected()})


@bp.route("/api/mp/snapshot")
def api_mp_snapshot():
    """Fetch the pending snapshot bytes (base64) for client game build."""
    import base64
    if _mp_client_snapshot is None:
        return jsonify({"ok": False, "error": "no snapshot yet"}), 404
    save_bytes, label = _mp_client_snapshot
    if not save_bytes:
        # START_GAME arrived but STATE_SYNC hasn't landed yet.
        return jsonify({"ok": False, "error": "snapshot syncing",
                        "retry": True}), 404
    return jsonify({"ok": True, "label": label,
                    "save_b64": base64.b64encode(save_bytes).decode("ascii")})


# ======================================================================
# Batch E (2026-10-06): in-game multiplayer web layer.
#
# The host/client network objects live in module state here; the Tk
# main thread pumps their event queues via bridge._pump_mp_web (the
# web game root never runs its own mainloop, so the desktop
# after()-scheduled _poll_multiplayer never fires).
#
# Client events are JSON-safe-copied into _mp_web_inbox and drained by
# GET /api/mp/game (the desktop _handle_client_event pops Tk dialogs,
# which don't exist in the web client). Host events go through the
# app's existing _handle_host_event (client intents applied to
# canonical state by the _mp_* handlers, exactly like the desktop).
# ======================================================================
import threading as _threading

_mp_web_inbox = []          # [{kind, payload}] drained by /api/mp/game
_mp_web_inbox_lock = _threading.Lock()
_mp_web_inbox_cap = 200
_mp_client_last_sync = None  # (save_bytes, label) from STATE_SYNC
_mp_client_disconnected = None  # reason string once the host is gone


def _inbox_push(kind, payload):
    with _mp_web_inbox_lock:
        _mp_web_inbox.append({"kind": kind, "payload": payload})
        while len(_mp_web_inbox) > _mp_web_inbox_cap:
            _mp_web_inbox.pop(0)


def _jsonable(value, _depth=0):
    """Deep-convert a client event payload to JSON-safe primitives."""
    if _depth > 6:
        return None
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v, _depth + 1) for v in value]
    nm = getattr(value, "full_name", None) or getattr(value, "name", None)
    if nm:
        return str(nm)
    return str(value)


def web_client_event(app, kind, payload):
    """Route one drained MultiplayerClient event (main thread).

    Called from bridge._pump_mp_web. Replicates the non-UI parts of
    HockeyManagerGUI._handle_client_event; everything UI-facing goes
    to the web inbox for /api/mp/game polling.
    """
    global _mp_client_last_sync, _mp_client_disconnected
    try:
        if kind == "state_sync":
            _mp_client_last_sync = (payload.get("save_bytes", b""),
                                    payload.get("label", ""))
            _inbox_push("state_sync", {
                "label": payload.get("label", ""),
                "game_date": payload.get("game_date", ""),
            })
        elif kind == "day_advanced":
            try:
                app._mp_client_ready = False
            except Exception:
                pass
            _inbox_push("day_advanced",
                        {"game_date": payload.get("game_date", "")})
        elif kind == "disconnected":
            _mp_client_disconnected = str(payload.get("reason", ""))
            _inbox_push("disconnected", {"reason": _mp_client_disconnected})
        else:
            _inbox_push(kind, _jsonable(payload if isinstance(payload, dict)
                                       else {"value": payload}))
    except Exception:
        pass


def mirror_host_event(kind, payload):
    """Copy a host-side event into the web inbox (chat only).

    The host pump routes events through the desktop _handle_host_event
    (toasts); the host's web UI also wants to SEE chat messages, so
    they are mirrored into the same JSON-safe inbox the client uses.
    """
    try:
        _inbox_push(str(kind), payload)
    except Exception:
        pass


def drain_web_inbox():
    """Pop and return all pending web client events."""
    with _mp_web_inbox_lock:
        out = list(_mp_web_inbox)
        del _mp_web_inbox[:]
    return out


def _live_app():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _mp_role(app):
    """host | client | spectator | none for this machine."""
    if app is None:
        return "none"
    if getattr(app, "mp_host", None) is not None:
        return "host"
    if getattr(app, "mp_client", None) is not None:
        return ("spectator"
                if getattr(app, "_mp_spectator", False) else "client")
    # Pre-game: hosting or joining from the setup page.
    if _mp_host is not None:
        return "host"
    if _mp_client is not None:
        return "client"
    return "none"


def _human_teams(app):
    """Team names currently run by a human (host or synced client)."""
    out = []
    try:
        gm = getattr(app, "game_manager", None)
        league = getattr(gm, "league", None) or getattr(app, "league", None)
        for t in (getattr(league, "teams", None) or []):
            if getattr(t, "is_human_managed", False):
                tn = str(getattr(t, "team_name", ""))
                abbr = ""
                try:
                    from web_ui.bridge import TEAM_ABBR, _resolve_gm
                    abbr = TEAM_ABBR.get(tn, "")
                except Exception:
                    pass
                out.append({"name": tn, "abbr": abbr})
    except Exception:
        pass
    # Fall back to the lobby when no game is loaded yet (setup page).
    if not out and _mp_host is not None:
        try:
            for m in _mp_host.get_lobby():
                if m.get("team_id"):
                    out.append({"name": str(m["team_id"]), "abbr": ""})
        except Exception:
            pass
    return [t for t in out if t.get("name")]


@bp.route("/api/mp/state")
def api_mp_state():
    """Lightweight MP role probe for the global MP bar / hub.

    Non-draining: safe to poll often (unlike /api/mp/game, which pops
    the event inbox). Includes the ready-gate advance snapshot.
    """
    app = _live_app()
    role = _mp_role(app)
    my_team = None
    try:
        my_team = str(getattr(getattr(app, "user_team", None),
                              "team_name", "") or "") or None
    except Exception:
        pass
    connected = False
    try:
        if role == "host" and _mp_host is not None:
            connected = True
        elif role in ("client", "spectator") and _mp_client is not None:
            connected = bool(_mp_client.connected())
    except Exception:
        pass
    return jsonify({"ok": True, "role": role, "my_team": my_team,
                    "connected": connected,
                    "advance": _advance_payload(app, role),
                    "disconnected": _mp_client_disconnected})


def _advance_payload(app, role):
    """Ready-gate snapshot without draining the event inbox."""
    try:
        if role == "host":
            host = getattr(app, "mp_host", None) or _mp_host
            if host is not None:
                hr = bool(getattr(app, "_mp_host_ready", False))
                adv = host._advance_status_payload(hr)
                adv["me_ready"] = hr
                return adv
        elif role in ("client", "spectator"):
            adv = {"me_ready": bool(getattr(app, "_mp_client_ready", False))}
            # Fold in the latest host-pushed ADVANCE_STATUS without
            # consuming it: peek at the inbox tail.
            try:
                with _mp_web_inbox_lock:
                    for ev in reversed(_mp_web_inbox):
                        if ev.get("kind") == "advance_status":
                            adv.update(ev.get("payload") or {})
                            adv["me_ready"] = bool(
                                getattr(app, "_mp_client_ready", False))
                            break
            except Exception:
                pass
            return adv
    except Exception:
        pass
    return None


@bp.route("/api/mp/game")
def api_mp_game():
    """In-game MP polling: pending events + readiness + connection state.

    The browser polls this every ~2s. Events: chat, day_advanced,
    state_sync (snapshot waiting), trade_offer, ntc_waiver_request,
    draft_clock, fantasy_draft_clock, draft_update, action_ack,
    action_rejected, checkpoint, error, advance_status, disconnected,
    host_trade_offer (host's own club was offered a deal).
    """
    app = _live_app()
    role = _mp_role(app)
    events = drain_web_inbox()
    # Host-side web offers (stashed by main._mp_offer_to_host's web guard)
    # surface here too so the host can answer in-page.
    try:
        offers = getattr(app, "_mp_web_host_offers", None)
        if isinstance(offers, dict) and offers:
            for oid, entry in list(offers.items()):
                events.append({"kind": "host_trade_offer",
                               "payload": _serialize_host_offer(oid, entry)})
    except Exception:
        pass
    advance = _advance_payload(app, role)
    # Client readiness is local state (not in the host's payload).
    try:
        if advance is not None and role in ("client", "spectator"):
            advance["me_ready"] = bool(
                getattr(app, "_mp_client_ready", False))
    except Exception:
        pass
    connected = False
    try:
        if role == "host":
            connected = _mp_host is not None or \
                getattr(app, "mp_host", None) is not None
        elif role in ("client", "spectator") and _mp_client is not None:
            connected = bool(_mp_client.connected())
    except Exception:
        pass
    sync_pending = _mp_client_last_sync is not None
    return jsonify({"ok": True, "role": role, "events": events,
                    "advance": advance, "connected": connected,
                    "sync_pending": sync_pending,
                    "disconnected": _mp_client_disconnected})


def _serialize_host_offer(offer_id, entry):
    """JSON-safe view of a trade offer targeting the host's own club."""
    try:
        from web_ui.bridge import _safe, _resolve_gm
        proposal = (entry or {}).get("proposal") or {}
        offer = {"offer_id": offer_id,
                 "from_team": proposal.get("proposer_team_id", ""),
                 "from_manager": proposal.get("manager", ""),
                 "players_out": [], "players_in": [],
                 "picks_out": [], "picks_in": []}
        for p in (proposal.get("_out_players") or []):
            offer["players_out"].append({
                "name": _safe(lambda: p.full_name, "?"),
                "pos": str(_safe(lambda: p.primary_position.value, "?")),
                "ovr": int(_safe(lambda: p.overall, 0) or 0)})
        for p in (proposal.get("_in_players") or []):
            offer["players_in"].append({
                "name": _safe(lambda: p.full_name, "?"),
                "pos": str(_safe(lambda: p.primary_position.value, "?")),
                "ovr": int(_safe(lambda: p.overall, 0) or 0)})
        for k in (proposal.get("_out_picks") or []):
            offer["picks_out"].append(
                f"{_safe(lambda: k.year, '?')} R{_safe(lambda: k.round, '?')}")
        for k in (proposal.get("_in_picks") or []):
            offer["picks_in"].append(
                f"{_safe(lambda: k.year, '?')} R{_safe(lambda: k.round, '?')}")
        return offer
    except Exception:
        return {"offer_id": offer_id}


@bp.route("/api/mp/humans")
def api_mp_humans():
    """Human-managed teams (for human-to-human trade routing) + my team."""
    app = _live_app()
    my_team = None
    try:
        my_team = str(getattr(getattr(app, "user_team", None),
                              "team_name", "") or "") or None
    except Exception:
        pass
    return jsonify({"ok": True, "humans": _human_teams(app),
                    "my_team": my_team, "role": _mp_role(app)})


@bp.route("/api/mp/ready", methods=["POST"])
def api_mp_ready():
    """Toggle this machine's ready vote (EHM ready gate)."""
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    nonce = _uuid.uuid4().hex[:12]
    ok = enqueue_command("mp_toggle_ready", nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/mp/result")
def api_mp_result():
    """Poll the outcome of a queued MP op (?nonce=)."""
    live = _live_app()
    nonce = (request.args.get("nonce") or "").strip()
    r = None
    try:
        r = getattr(live, "_web_mp_result", None)
    except Exception:
        pass
    if not r or (nonce and str(r.get("nonce") or "") != nonce):
        return jsonify({"pending": True})
    return jsonify({"pending": False, "result": {
        "ok": bool(r.get("ok")),
        "message": str(r.get("message") or ""),
        "blocked": bool(r.get("blocked")),
        "blockers": r.get("blockers") or [],
    }})


@bp.route("/api/mp/chat", methods=["POST"])
def api_mp_chat():
    """Send a chat message to the other managers."""
    data = request.get_json(force=True, silent=True) or {}
    text = str(data.get("text") or "").strip()[:500]
    if not text:
        return jsonify({"ok": False, "error": "empty message"}), 400
    app = _live_app()
    try:
        host = getattr(app, "mp_host", None) or _mp_host
        if host is not None:
            host.broadcast_chat(text)
            return jsonify({"ok": True, "from": "you"})
        if _mp_client is not None:
            _mp_client.send_chat(text)
            return jsonify({"ok": True, "from": "you"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": False, "error": "not in a multiplayer game"}), 400


@bp.route("/api/mp/trade/propose", methods=["POST"])
def api_mp_trade_propose():
    """Propose a human-to-human trade.

    Client machine: sends the propose_trade ACTION intent to the host
    (validated + routed by the host's _mp_* handlers). Host machine:
    enqueues mp_trade_propose for the main thread, which runs the same
    _mp_propose_trade path the desktop uses.
    Payload: {partner_team_id, give_pids, give_picks, want_pids,
    want_picks, retention?, pick_protection?}
    """
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    data = request.get_json(force=True, silent=True) or {}
    app = _live_app()
    partner = str(data.get("partner_team_id") or "")
    offer = {
        "players_out": [str(x) for x in (data.get("give_pids") or [])],
        "players_in": [str(x) for x in (data.get("want_pids") or [])],
        "picks_out": [str(x) for x in (data.get("give_picks") or [])],
        "picks_in": [str(x) for x in (data.get("want_picks") or [])],
        "retention": {str(k): v for k, v in
                      (data.get("retention") or {}).items()},
        "pick_protection": {str(k): v for k, v in
                            (data.get("pick_protection") or {}).items()},
    }
    if not partner:
        return jsonify({"ok": False, "error": "partner_team_id required"}), 400
    my_team = None
    try:
        my_team = str(getattr(getattr(app, "user_team", None),
                              "team_name", "") or "")
    except Exception:
        pass
    if not my_team:
        return jsonify({"ok": False, "error": "no team loaded"}), 400
    # Client machine: intent goes to the host over the wire.
    if _mp_client is not None and \
            getattr(app, "mp_host", None) is None:
        try:
            _mp_client.send_action("propose_trade", {
                "team_id": my_team, "partner_team_id": partner,
                "offer": offer})
            return jsonify({"ok": True, "via": "host",
                            "note": "Offer sent to the host for routing."})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    # Host machine: run the real _mp_propose_trade on the main thread.
    nonce = _uuid.uuid4().hex[:12]
    ok = enqueue_command("mp_trade_propose", nonce=nonce, team_id=my_team,
                         partner_team_id=partner, offer=offer)
    return jsonify({"ok": bool(ok), "nonce": nonce, "via": "local"})


@bp.route("/api/mp/trade/respond", methods=["POST"])
def api_mp_trade_respond():
    """Answer an incoming human trade offer (client machine)."""
    data = request.get_json(force=True, silent=True) or {}
    offer_id = str(data.get("offer_id") or "")
    decision = str(data.get("decision") or "")
    if decision not in ("accept", "reject"):
        return jsonify({"ok": False, "error": "decision must be accept|reject"}), 400
    if _mp_client is None:
        return jsonify({"ok": False, "error": "not connected"}), 400
    try:
        _mp_client.send_trade_response(offer_id, decision)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/mp/trade/respond_host", methods=["POST"])
def api_mp_trade_respond_host():
    """Answer an offer targeting the host's own club (host machine)."""
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    data = request.get_json(force=True, silent=True) or {}
    decision = str(data.get("decision") or "")
    offer_id = str(data.get("offer_id") or "")
    if decision not in ("accept", "reject") or not offer_id:
        return jsonify({"ok": False, "error": "offer_id + decision required"}), 400
    nonce = _uuid.uuid4().hex[:12]
    ok = enqueue_command("mp_trade_answer", nonce=nonce,
                         offer_id=offer_id, decision=decision)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/mp/ntc_answer", methods=["POST"])
def api_mp_ntc_answer():
    """Answer a no-trade/no-movement waiver prompt (client machine)."""
    data = request.get_json(force=True, silent=True) or {}
    choice = str(data.get("choice") or "")
    if choice not in ("ask", "remove", "cancel"):
        return jsonify({"ok": False, "error": "choice must be ask|remove|cancel"}), 400
    if _mp_client is None:
        return jsonify({"ok": False, "error": "not connected"}), 400
    try:
        _mp_client.send_ntc_waiver_answer(
            str(data.get("player_id") or ""), choice,
            str(data.get("waiver_id") or ""))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/mp/action", methods=["POST"])
def api_mp_action():
    """Generic MP action passthrough (client machine).

    Sends any protocol SUPPORTED_ACTIONS intent to the host, where the
    existing _mp_* handlers validate and apply it. {action, params}.
    The ACK/reject arrives via /api/mp/game polling.
    """
    from multiplayer import protocol as _p
    data = request.get_json(force=True, silent=True) or {}
    action = str(data.get("action") or "")
    params = data.get("params") or {}
    if action not in _p.SUPPORTED_ACTIONS:
        return jsonify({"ok": False,
                        "error": f"unsupported action: {action}"}), 400
    if _mp_client is None or not isinstance(params, dict):
        return jsonify({"ok": False,
                        "error": "not connected or bad params"}), 400
    # Stamp the client's own team when the caller didn't.
    app = _live_app()
    if "team_id" not in params:
        try:
            params["team_id"] = str(getattr(
                getattr(app, "user_team", None), "team_name", "") or "")
        except Exception:
            pass
    try:
        seq = _mp_client.send_action(action, params)
        return jsonify({"ok": True, "seq": seq})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/mp/sync")
def api_mp_sync():
    """Fetch the latest STATE_SYNC snapshot bytes (base64, client side)."""
    import base64
    if _mp_client_last_sync is None:
        return jsonify({"ok": False, "error": "no sync available"}), 404
    save_bytes, label = _mp_client_last_sync
    return jsonify({"ok": True, "label": label,
                    "save_b64": base64.b64encode(save_bytes).decode("ascii")})


@bp.route("/api/mp/promote", methods=["POST"])
def api_mp_promote():
    """Promote this client to host after a host disconnect (host migration)."""
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    nonce = _uuid.uuid4().hex[:12]
    ok = enqueue_command("mp_promote", nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/mp/force", methods=["POST"])
def api_mp_force():
    """Host override: advance the day even if some managers aren't ready."""
    import uuid as _uuid
    from web_ui.bridge import enqueue_command, _resolve_gm
    nonce = _uuid.uuid4().hex[:12]
    ok = enqueue_command("mp_force_advance", nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/mp/draft_players", methods=["POST"])
def api_mp_draft_players():
    """Resolve draft-pick player ids to card data (MP draft clock).

    The host sends available_ids; the client resolves them against its
    synced snapshot for the in-page pick list.
    """
    data = request.get_json(force=True, silent=True) or {}
    ids = [str(x) for x in (data.get("ids") or [])][:600]
    want = set(ids)
    app = _live_app()
    out = []

    def _pos(p):
        try:
            return str(getattr(getattr(p, "primary_position", None),
                               "value", "?") or "?")
        except Exception:
            return "?"

    try:
        gm = getattr(app, "game_manager", None)
        league = getattr(gm, "league", None) or getattr(app, "league", None)
        seen = set()
        pools = []
        for t in (getattr(league, "teams", None) or []):
            for attr in ("roster", "ahl_roster", "prospects"):
                pools.extend(getattr(t, attr, None) or [])
        pools.extend(getattr(league, "free_agents", None) or [])
        for p in pools:
            try:
                pid = str(getattr(p, "id", ""))
            except Exception:
                continue
            if pid not in want or pid in seen:
                continue
            seen.add(pid)
            try:
                ovr = getattr(p, "overall", None)
                if callable(ovr):
                    ovr = ovr()
            except Exception:
                ovr = 0
            out.append({
                "id": pid,
                "name": str(getattr(p, "full_name", None)
                            or getattr(p, "name", "?")),
                "pos": _pos(p),
                "ranking": int(getattr(p, "draft_ranking", 0) or 0),
                "ovr": int(ovr or 0),
                "age": int(getattr(p, "age", 0) or 0),
            })
    except Exception:
        pass
    order = {pid: i for i, pid in enumerate(ids)}
    out.sort(key=lambda x: order.get(x["id"], 9999))
    return jsonify({"ok": True, "players": out})
