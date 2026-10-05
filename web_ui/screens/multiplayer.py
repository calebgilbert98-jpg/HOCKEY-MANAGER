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
    """Poll for game start (client side). When the host starts the game,
    the snapshot arrives via client events; this endpoint surfaces it."""
    global _mp_client_snapshot
    client = _mp_client
    if client is None:
        return jsonify({"ok": False, "error": "not connected"})
    # Drain client events for START_GAME / snapshot
    try:
        for kind, payload in client.poll_events():
            if kind == "start_game":
                _mp_client_snapshot = (
                    payload.get("save_bytes"),
                    payload.get("label") or "Joined game",
                )
    except Exception:
        pass
    started = _mp_client_snapshot is not None
    return jsonify({"ok": True, "game_started": started,
                    "connected": client.connected()})


@bp.route("/api/mp/snapshot")
def api_mp_snapshot():
    """Fetch the pending snapshot bytes (base64) for client game build."""
    import base64
    if _mp_client_snapshot is None:
        return jsonify({"ok": False, "error": "no snapshot yet"}), 404
    save_bytes, label = _mp_client_snapshot
    return jsonify({"ok": True, "label": label,
                    "save_b64": base64.b64encode(save_bytes).decode("ascii")})
