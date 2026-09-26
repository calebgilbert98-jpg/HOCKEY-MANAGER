"""Host-side multiplayer server for Puck Dynasty (Phase 1).

The host is authoritative: it owns the canonical game state, applies
management actions, advances days, and broadcasts full-state snapshots.
Designed for virtual-LAN play (Radmin VPN / ZeroTier / Hamachi) -- bind
to all interfaces and hand clients the host's VPN address.

Threading model
---------------
* One daemon accept thread, one daemon thread per peer, one daemon
  heartbeat monitor thread.
* ALL game-state mutation happens on the caller's (tkinter main) thread:
  incoming ACTIONs are placed on ``events`` and only applied when the
  UI calls :meth:`resolve_action`. Network threads never touch game
  objects.
* ``state_provider`` is called on the peer thread for on-demand
  REQUEST_STATE, and on the main thread for broadcasts. It must be
  safe to call concurrently (``GameSaveManager.create_save_data``
  qualifies -- it builds fresh dicts and performs no widget I/O).

Typical wiring (done by the game, not here)::

    host = MultiplayerHost(state_provider=lambda: (
        gzip.compress(pickle.dumps(save_mgr.create_save_data(),
                                   protocol=pickle.HIGHEST_PROTOCOL)),
        str(gui.current_date), "manual"))
    host.start()
    # in the tkinter event loop:
    root.after(250, poll_host_events)

Do NOT expose the host port to the open internet: the protocol uses
pickle (same trust model as the game's own save files).
"""

from __future__ import annotations

import queue
import socket
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional, Tuple

from . import PROTOCOL_VERSION
from . import protocol as P
from .protocol import MessageReader, ProtocolError

DEFAULT_PORT = 27107
HEARTBEAT_INTERVAL = 15.0
HEARTBEAT_TIMEOUT = 45.0
LISTEN_BACKLOG = 8
RECV_BYTES = 65536

#: () -> (save_bytes, game_date_display, label)
StateProvider = Callable[[], Tuple[bytes, str, str]]


class _Peer:
    __slots__ = ("sock", "addr", "reader", "session_id", "name",
                 "team_id", "seq", "last_seen", "send_lock",
                 "handshake_done", "alive")

    def __init__(self, sock: socket.socket, addr):
        self.sock = sock
        self.addr = addr
        self.reader = MessageReader()
        self.session_id = uuid.uuid4().hex[:12]
        self.name = "?"
        self.team_id: Optional[str] = None
        self.seq = 0
        self.last_seen = time.time()
        self.send_lock = threading.Lock()
        self.handshake_done = False
        self.alive = True


class MultiplayerHost:
    """Authoritative multiplayer host."""

    def __init__(self, state_provider: StateProvider,
                 host_name: str = "Host",
                 port: int = DEFAULT_PORT,
                 get_teams: Optional[Callable[[], List[Dict[str, str]]]] = None):
        self._state_provider = state_provider
        self.host_name = host_name
        self.port = port
        # () -> [{"id":..., "name":...}] claimable teams, for the lobby.
        self._get_teams = get_teams
        self.events: "queue.Queue[Tuple[str, Dict]]" = queue.Queue()
        self._peers: Dict[str, _Peer] = {}
        self._peers_lock = threading.Lock()
        self._running = threading.Event()
        self._listener: Optional[socket.socket] = None
        self._threads: List[threading.Thread] = []
        self._last_game_date = "unknown"
        # Async snapshot state: only one serialization worker runs at a
        # time; extra requests coalesce into _snapshot_pending (latest wins).
        self._snapshot_lock = threading.Lock()
        self._snapshot_busy = False
        self._snapshot_pending: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bind and begin accepting clients. Raises OSError if the port is busy."""
        if self._running.is_set():
            return
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", self.port))
        listener.listen(LISTEN_BACKLOG)
        listener.settimeout(1.0)
        self._listener = listener
        self._running.set()
        self._spawn(self._accept_loop, "mp-accept")
        self._spawn(self._heartbeat_loop, "mp-heartbeat")

    def stop(self) -> None:
        self._running.clear()
        with self._peers_lock:
            peers = list(self._peers.values())
        for peer in peers:
            self._drop_peer(peer, "host shutting down", notify=False)
        if self._listener is not None:
            try:
                # shutdown() first: it wakes the accept thread blocked in
                # accept() immediately. close() alone does NOT interrupt a
                # thread stuck in accept(), so the bind would linger ~1s
                # (the socket timeout) and a prompt restart on the same
                # port would fail with EADDRINUSE.
                self._listener.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def peer_count(self) -> int:
        with self._peers_lock:
            return len(self._peers)

    def get_lobby(self) -> List[Dict[str, str]]:
        with self._peers_lock:
            return [{"session_id": p.session_id, "name": p.name,
                     "team_id": p.team_id or ""}
                    for p in self._peers.values() if p.handshake_done]

    def poll_events(self) -> List[Tuple[str, Dict]]:
        """Drain queued events. Call from the tkinter main thread via after()."""
        out = []
        try:
            while True:
                out.append(self.events.get_nowait())
        except queue.Empty:
            pass
        return out

    # ------------------------------------------------------------------
    # Outgoing (call from the main thread)
    # ------------------------------------------------------------------

    def broadcast_state(self, label: str = "") -> None:
        """Snapshot via state_provider and push STATE_SYNC to every client.

        Synchronous: runs create_save_data + pickle + gzip on the calling
        thread. Prefer broadcast_state_async() from UI code so the main
        thread never freezes; this variant stays for tests and one-shot
        callers that already own their thread.
        """
        save_bytes, game_date, _auto_label = self._state_provider()
        self._last_game_date = game_date
        self._broadcast(P.STATE_SYNC,
                        P.state_sync(save_bytes, game_date, label or _auto_label))

    @property
    def snapshot_busy(self) -> bool:
        """True while a snapshot worker is serializing game state.

        The GUI must not mutate game objects while this is set (no day
        advance, no action application); see broadcast_state_async.
        """
        with self._snapshot_lock:
            return self._snapshot_busy

    def broadcast_state_async(self, label: str = "",
                              pre_broadcast: Optional[Callable[[], None]] = None
                              ) -> bool:
        """Serialize + broadcast STATE_SYNC on a worker thread.

        ``pre_broadcast`` (e.g. the host's checkpoint-to-disk) runs first
        on the same worker, so one serialization window covers both.

        Returns True if a worker was started. If one is already running,
        the request is coalesced into a single pending snapshot (latest
        label wins) and False is returned. Completion (or failure) is
        reported as a ("snapshot_done", {}) / ("error", ...) event on the
        normal poll queue, so the main thread can resume mutations then.

        Threading contract: while snapshot_busy is True, NOBODY may mutate
        the game objects the state_provider reads -- the GUI enforces this
        by deferring client actions and refusing day advances.
        """
        with self._snapshot_lock:
            if self._snapshot_busy:
                self._snapshot_pending = label
                return False
            self._snapshot_busy = True
        self._spawn(
            lambda: self._snapshot_worker(label, pre_broadcast),
            "mp-snapshot")
        return True

    def _snapshot_worker(self, label: str,
                         pre_broadcast: Optional[Callable[[], None]]) -> None:
        try:
            if pre_broadcast is not None:
                pre_broadcast()
            save_bytes, game_date, auto_label = self._state_provider()
            self._last_game_date = game_date
            self._broadcast(P.STATE_SYNC,
                            P.state_sync(save_bytes, game_date,
                                         label or auto_label))
        except Exception as e:
            self.events.put(("error",
                             {"message": f"state snapshot failed: {e}"}))
        finally:
            with self._snapshot_lock:
                self._snapshot_busy = False
                pending, self._snapshot_pending = self._snapshot_pending, None
            # Main-thread bridge: mutations may resume on this event.
            self.events.put(("snapshot_done", {}))
            if pending:
                self.broadcast_state_async(pending)

    def start_game(self) -> None:
        """Leave the lobby: tell clients the game is starting, then sync state."""
        self._broadcast(P.START_GAME, {"type": P.START_GAME})
        self.broadcast_state_async("Game started")

    def announce_day(self, game_date: str) -> None:
        """Call right after the host advances a day, then broadcast_state()."""
        self._last_game_date = game_date
        self._broadcast(P.CONTINUE_DAY, P.continue_day(game_date))

    def notify_checkpoint(self, label: str, game_date: str) -> None:
        self._broadcast(P.CHECKPOINT_NOTICE,
                        P.checkpoint_notice(label, game_date))

    def broadcast_chat(self, text: str) -> None:
        self._broadcast(P.CHAT, P.chat_msg(self.host_name, text))

    def resolve_action(self, client_id: str, msg_seq: int, ok: bool,
                       detail: str = "", broadcast: bool = True) -> None:
        """Answer a queued ACTION. Call from the main thread after applying it.

        ``ok`` True  -> ACTION_ACK (+ fresh STATE_SYNC to everyone).
        ``ok`` False -> ACTION_REJECT with ``detail`` as the reason.
        """
        peer = self._find_peer(client_id)
        if peer is None:
            return
        if ok:
            self._send(peer, P.ACTION_ACK,
                       {"type": P.ACTION_ACK, "action_seq": msg_seq,
                        "result": detail})
            if broadcast:
                self.broadcast_state_async(
                    f"After action ({detail})" if detail else "State update")
        else:
            self._send(peer, P.ACTION_REJECT,
                       {"type": P.ACTION_REJECT, "action_seq": msg_seq,
                        "reason": detail or "rejected by host"})

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _spawn(self, target, name: str) -> None:
        t = threading.Thread(target=target, name=name, daemon=True)
        self._threads.append(t)
        t.start()

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, addr = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            peer = _Peer(conn, addr)
            with self._peers_lock:
                self._peers[peer.session_id] = peer
            self._spawn(lambda p=peer: self._peer_loop(p),
                        f"mp-peer-{peer.session_id}")

    def _heartbeat_loop(self) -> None:
        while self._running.is_set():
            time.sleep(HEARTBEAT_INTERVAL)
            now = time.time()
            with self._peers_lock:
                peers = list(self._peers.values())
            for peer in peers:
                if now - peer.last_seen > HEARTBEAT_TIMEOUT:
                    self._drop_peer(peer, "heartbeat timeout")
                else:
                    self._send(peer, P.PING, {"type": P.PING})

    def _peer_loop(self, peer: _Peer) -> None:
        try:
            while self._running.is_set() and peer.alive:
                try:
                    data = peer.sock.recv(RECV_BYTES)
                except OSError:
                    break
                if not data:
                    break  # clean close
                peer.last_seen = time.time()
                try:
                    messages = list(peer.reader.feed(data))
                except ProtocolError:
                    break  # corrupt stream -> drop
                for msg in messages:
                    self._dispatch(peer, msg)
        finally:
            self._drop_peer(peer, "disconnected")

    def _dispatch(self, peer: _Peer, msg: Dict) -> None:
        mtype = msg.get("type")
        if mtype == P.PING:
            self._send(peer, P.PONG, {"type": P.PONG})
        elif mtype == P.PONG:
            pass
        elif mtype == P.HELLO:
            self._on_hello(peer, msg)
        elif not peer.handshake_done:
            self._send(peer, P.ERROR,
                       P.error_msg("handshake required: send HELLO first"))
        elif mtype == P.CLAIM_TEAM:
            self._on_claim_team(peer, msg)
        elif mtype == P.ACTION:
            self._on_action(peer, msg)
        elif mtype == P.REQUEST_STATE:
            self._send_state_to(peer, "Requested sync")
        elif mtype == P.CHAT:
            text = str(msg.get("text", ""))[:500]
            self.events.put(("chat", {"from": peer.name, "text": text}))
            self._broadcast(P.CHAT, P.chat_msg(peer.name, text),
                            exclude=peer.session_id)
        elif mtype == P.GOODBYE:
            peer.alive = False
        else:
            self._send(peer, P.ERROR,
                       P.error_msg(f"unsupported message: {mtype!r}"))

    def _on_hello(self, peer: _Peer, msg: Dict) -> None:
        name = str(msg.get("name", "Player"))[:32] or "Player"
        version = msg.get("version")
        if version != PROTOCOL_VERSION:
            self._send(peer, P.ERROR, P.error_msg(
                f"protocol mismatch: host speaks v{PROTOCOL_VERSION}, "
                f"client sent v{version}. Update your game."))
            peer.alive = False
            return
        # Unique-ify duplicate display names.
        with self._peers_lock:
            taken = {p.name for p in self._peers.values() if p is not peer}
        base, i = name, 2
        while name in taken:
            name = f"{base} ({i})"
            i += 1
        peer.name = name
        peer.handshake_done = True
        try:
            teams = self._get_teams() if self._get_teams else []
        except Exception:
            teams = []
        self._send(peer, P.WELCOME,
                   P.welcome(peer.session_id, self._last_game_date,
                             self._teams_taken(), teams))
        self._send(peer, P.LOBBY_STATE,
                   P.lobby_state(self.get_lobby()))
        self.events.put(("manager_joined",
                         {"session_id": peer.session_id, "name": name}))

    def _on_claim_team(self, peer: _Peer, msg: Dict) -> None:
        team_id = str(msg.get("team_id", ""))
        if not team_id:
            self._send(peer, P.ERROR, P.error_msg("no team specified"))
            return
        taken = self._teams_taken()
        if team_id in taken:
            self._send(peer, P.ERROR, P.error_msg(
                f"{team_id} is already managed by {taken[team_id]}"))
            return
        peer.team_id = team_id
        self._broadcast(P.TEAM_CLAIMED, P.team_claimed(team_id, peer.name))
        self._broadcast(P.LOBBY_STATE, P.lobby_state(self.get_lobby()))
        self.events.put(("team_claimed",
                         {"session_id": peer.session_id,
                          "name": peer.name, "team_id": team_id}))

    def _on_action(self, peer: _Peer, msg: Dict) -> None:
        action = msg.get("action")
        params = msg.get("params")
        if peer.team_id is None:
            self._send(peer, P.ACTION_REJECT,
                       {"type": P.ACTION_REJECT,
                        "action_seq": msg.get("seq", 0),
                        "reason": "claim a team before managing it"})
            return
        if action not in P.SUPPORTED_ACTIONS or not isinstance(params, dict):
            self._send(peer, P.ACTION_REJECT,
                       {"type": P.ACTION_REJECT,
                        "action_seq": msg.get("seq", 0),
                        "reason": f"unsupported action: {action!r}"})
            return
        # A manager may only act on their own club.
        if "team_id" in params and params["team_id"] != peer.team_id:
            self._send(peer, P.ACTION_REJECT,
                       {"type": P.ACTION_REJECT,
                        "action_seq": msg.get("seq", 0),
                        "reason": "you can only manage your own team"})
            return
        params = dict(params)
        params.setdefault("team_id", peer.team_id)
        # Queue for the main thread -- game objects are never touched here.
        self.events.put(("action", {
            "client_id": peer.session_id,
            "seq": msg.get("seq", 0),
            "action": action,
            "params": params,
            "manager": peer.name,
        }))

    # -- sending helpers -------------------------------------------------

    def _teams_taken(self) -> Dict[str, str]:
        with self._peers_lock:
            return {p.team_id: p.name for p in self._peers.values()
                    if p.team_id}

    def _find_peer(self, session_id: str) -> Optional[_Peer]:
        with self._peers_lock:
            return self._peers.get(session_id)

    def _next_seq(self, peer: _Peer) -> int:
        peer.seq += 1
        return peer.seq

    def _send(self, peer: _Peer, msg_type: str, body: Dict) -> bool:
        try:
            wire = P.encode_message(msg_type, self._next_seq(peer), body)
        except P.ProtocolError:
            return False
        with peer.send_lock:
            try:
                peer.sock.sendall(wire)
                return True
            except OSError:
                pass
        self._drop_peer(peer, "send failed")
        return False

    def _broadcast(self, msg_type: str, body: Dict,
                   exclude: Optional[str] = None) -> None:
        with self._peers_lock:
            peers = [p for p in self._peers.values()
                     if p.handshake_done and p.session_id != exclude]
        for peer in peers:
            self._send(peer, msg_type, body)

    def _send_state_to(self, peer: _Peer, label: str) -> None:
        try:
            save_bytes, game_date, _ = self._state_provider()
        except Exception as exc:  # never kill a peer thread over a snapshot
            self._send(peer, P.ERROR,
                       P.error_msg(f"state snapshot failed: {exc}"))
            return
        self._send(peer, P.STATE_SYNC,
                   P.state_sync(save_bytes, game_date, label))

    def _drop_peer(self, peer: _Peer, reason: str, notify: bool = True) -> None:
        with self._peers_lock:
            gone = self._peers.pop(peer.session_id, None)
        if gone is None:
            return
        peer.alive = False
        try:
            if notify:
                with peer.send_lock:
                    try:
                        peer.sock.sendall(P.encode_message(
                            P.GOODBYE, self._next_seq(peer),
                            {"type": P.GOODBYE, "reason": reason}))
                    except OSError:
                        pass
            peer.sock.close()
        except OSError:
            pass
        self.events.put(("manager_left",
                         {"session_id": peer.session_id,
                          "name": peer.name, "reason": reason}))
        self._broadcast(P.LOBBY_STATE, P.lobby_state(self.get_lobby()))
