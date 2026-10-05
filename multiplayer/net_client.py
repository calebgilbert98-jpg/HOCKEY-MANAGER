# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Client-side multiplayer connection for Puck Dynasty (Phase 1).

Connects to a :class:`multiplayer.net_host.MultiplayerHost` over a
virtual LAN (Radmin VPN / ZeroTier / Hamachi). The client holds no
authority: it renders whatever STATE_SYNC snapshots the host sends
and funnels management intent back as ACTION messages.

Threading model
---------------
* One daemon receive thread decodes the stream and pushes UI-ready
  events onto ``events``. The tkinter main thread drains it with
  ``after()`` polling -- network threads never touch widgets.
* Sends are serialized with a lock; ``send_action`` returns the
  message seq so ACTION_ACK / ACTION_REJECT can be correlated.

Crash fallback
--------------
Every STATE_SYNC snapshot is also written to a single rotating file
(``saves/checkpoints/client_last_sync.hm``). If the host dies
mid-session, any client can promote that file to a new hosted game.
One file, overwritten each time -- the checkpoints folder never grows.
"""

from __future__ import annotations

import os
import queue
import socket
import threading
import time
from typing import Dict, List, Optional, Tuple

from . import PROTOCOL_VERSION
from . import protocol as P
from .protocol import MessageReader, ProtocolError

RECV_BYTES = 65536
CONNECT_TIMEOUT = 10.0
WELCOME_TIMEOUT = 10.0

#: Single rotating emergency fallback written on every STATE_SYNC.
CLIENT_FALLBACK_PATH = os.path.join("saves", "checkpoints",
                                    "client_last_sync.hm")


class ConnectionError(Exception):
    """Raised when the client cannot reach / handshake with a host."""


def get_machine_token() -> str:
    """This machine's stable multiplayer identity, persisted across sessions.

    Used as the GM token: the host stamps it on claimed teams and saves it,
    so the GM's seat survives host restarts and they reclaim their club on
    rejoin. Also used by a host to stamp its own team.
    """
    try:
        import os
        _dir = os.path.join(os.path.expanduser("~"), ".puck-dynasty")
        os.makedirs(_dir, exist_ok=True)
        _path = os.path.join(_dir, "mp_client_token")
        try:
            with open(_path, "r") as fh:
                _tok = (fh.read() or "").strip()
            if _tok:
                return _tok
        except OSError:
            pass
        import uuid as _uuid
        _tok = _uuid.uuid4().hex
        try:
            with open(_path, "w") as fh:
                fh.write(_tok)
        except OSError:
            pass
        return _tok
    except Exception:
        import uuid as _uuid
        return _uuid.uuid4().hex


class MultiplayerClient:
    """Connection to a multiplayer host. UI-agnostic; see module docstring."""

    def __init__(self, name: str,
                 fallback_path: str = CLIENT_FALLBACK_PATH):
        self.name = (name or "Player")[:32]
        self.events: "queue.Queue[Tuple[str, Dict]]" = queue.Queue()
        self._sock: Optional[socket.socket] = None
        self._reader = MessageReader()
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._running = threading.Event()
        self._recv_thread: Optional[threading.Thread] = None
        self._fallback_path = fallback_path
        self._disconnect_reported = False

        self.session_id: Optional[str] = None
        self.team_id: Optional[str] = None
        #: Port of the host we're connected to (for host-migration reuse).
        self.port: int = 0
        self.game_date: str = "unknown"
        self.managers: List[Dict[str, str]] = []
        #: Full claimable team roster from WELCOME (may be empty on old hosts).
        self.teams: List[Dict[str, str]] = []
        #: seq -> action name, for correlating ACKs.
        self._pending_actions: Dict[int, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _rejoin_token() -> str:
        """Stable client identity for rejoin, persisted across sessions.

        Stored in the user's saves dir so a dropped client is recognized
        when it reconnects and gets its team claim restored by the host.
        """
        return get_machine_token()

    def connect(self, host: str, port: int,
                timeout: float = CONNECT_TIMEOUT) -> Dict:
        """Connect + handshake. Returns the WELCOME payload.

        Raises ConnectionError on any failure (unreachable host,
        protocol mismatch, timeout waiting for WELCOME).
        """
        if self._running.is_set():
            raise ConnectionError("already connected")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
        except OSError as exc:
            sock.close()
            raise ConnectionError(f"could not reach {host}:{port} ({exc})")
        sock.settimeout(None)
        self._sock = sock
        try:
            self.port = int(port)
        except Exception:
            pass
        self._running.set()
        self._disconnect_reported = False
        self._recv_thread = threading.Thread(target=self._recv_loop,
                                             name="mp-client-recv",
                                             daemon=True)
        self._recv_thread.start()
        self._send_raw(P.encode_message(P.HELLO, self._next_seq(),
                                        P.hello(self.name, PROTOCOL_VERSION,
                                                self._rejoin_token())))
        deadline = time.time() + WELCOME_TIMEOUT
        while time.time() < deadline:
            for kind, payload in self._drain_nowait():
                if kind == "welcome":
                    return payload
                if kind == "error":
                    self.disconnect()
                    raise ConnectionError(payload.get("message",
                                                      "host refused connection"))
            time.sleep(0.05)
        self.disconnect()
        raise ConnectionError("host did not answer in time")

    def disconnect(self) -> None:
        if not self._running.is_set():
            return
        self._running.clear()
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.sendall(P.encode_message(
                    P.GOODBYE, self._next_seq(),
                    {"type": P.GOODBYE, "reason": "leaving"}))
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        self._report_disconnected("left")

    @property
    def connected(self) -> bool:
        return self._running.is_set()

    def poll_events(self) -> List[Tuple[str, Dict]]:
        """Drain queued events. Call from the tkinter main thread."""
        return self._drain_nowait()

    # ------------------------------------------------------------------
    # Outgoing
    # ------------------------------------------------------------------

    def claim_team(self, team_id: str) -> None:
        self._send(P.CLAIM_TEAM, P.claim_team(team_id))

    def send_action(self, action_name: str, params: Dict) -> int:
        """Send a management intent. Returns seq for ACK correlation."""
        if action_name not in P.SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported action: {action_name!r}")
        seq = self._next_seq()
        self._pending_actions[seq] = action_name
        self._send(P.ACTION, dict(P.action(action_name, dict(params)),
                                 seq=seq))
        return seq

    def request_state(self) -> None:
        self._send(P.REQUEST_STATE, {"type": P.REQUEST_STATE})

    def send_ready(self) -> None:
        """Mark this manager ready for the day's advance (EHM-style)."""
        self._send(P.READY, {"type": P.READY})

    def send_unready(self) -> None:
        """Rescind readiness for the day's advance."""
        self._send(P.UNREADY, {"type": P.UNREADY})

    def send_trade_response(self, offer_id: str, decision: str) -> None:
        """Answer a human-to-human trade offer: accept | reject."""
        if decision not in ("accept", "reject"):
            raise ValueError(f"bad trade decision: {decision!r}")
        self._send(P.TRADE_RESPONSE,
                   {"type": P.TRADE_RESPONSE, "offer_id": offer_id,
                    "decision": decision})

    def send_ntc_waiver_answer(self, player_id: str,
                               choice: str = "ask",
                               waiver_id: str = "") -> None:
        """Answer a no-trade/no-movement waiver prompt.

        choice: "ask" (ask the player to waive), "remove" (pull him from
        the offer), or "cancel" (kill the deal). A bare bool is still
        accepted for back-compat (True -> "ask", False -> "cancel").
        """
        if isinstance(choice, bool):
            choice = "ask" if choice else "cancel"
        if choice not in ("ask", "remove", "cancel"):
            raise ValueError(f"bad waiver choice: {choice!r}")
        self._send(P.NTC_WAIVER_ANSWER,
                   {"type": P.NTC_WAIVER_ANSWER,
                    "waiver_id": str(waiver_id),
                    "player_id": str(player_id), "choice": choice,
                    "approved": choice == "ask"})

    def send_chat(self, text: str) -> None:
        self._send(P.CHAT, P.chat_msg(self.name, text[:500]))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _next_seq(self) -> int:
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def _send(self, msg_type: str, body: Dict) -> None:
        # NOTE: send_action pre-assigns seq; every other call site lets
        # _send assign one. Keep both paths consistent.
        seq = body.pop("seq", None)
        if seq is None:
            seq = self._next_seq()
        self._send_raw(P.encode_message(msg_type, seq, body))

    def _send_raw(self, wire: bytes) -> None:
        sock = self._sock
        if sock is None or not self._running.is_set():
            raise ConnectionError("not connected")
        with self._send_lock:
            try:
                sock.sendall(wire)
            except OSError as exc:
                raise ConnectionError(f"send failed: {exc}") from exc

    def _drain_nowait(self) -> List[Tuple[str, Dict]]:
        out = []
        try:
            while True:
                out.append(self.events.get_nowait())
        except queue.Empty:
            pass
        return out

    def _report_disconnected(self, reason: str) -> None:
        if self._disconnect_reported:
            return
        self._disconnect_reported = True
        self.events.put(("disconnected", {"reason": reason}))

    def _recv_loop(self) -> None:
        try:
            while self._running.is_set():
                try:
                    data = self._sock.recv(RECV_BYTES)
                except OSError:
                    break
                if not data:
                    break
                try:
                    messages = list(self._reader.feed(data))
                except ProtocolError:
                    break
                for msg in messages:
                    self._dispatch(msg)
        finally:
            self._running.clear()
            self._report_disconnected("connection lost")

    def _dispatch(self, msg: Dict) -> None:
        mtype = msg.get("type")
        if mtype == P.PING:
            try:
                self._send_raw(P.encode_message(P.PONG, self._next_seq(),
                                                {"type": P.PONG}))
            except ConnectionError:
                pass
        elif mtype == P.WELCOME:
            self.session_id = msg.get("session_id")
            self.game_date = msg.get("game_date", "unknown")
            self.teams = msg.get("teams", []) or []
            self.events.put(("welcome", {
                "session_id": self.session_id,
                "game_date": self.game_date,
                "teams_taken": msg.get("teams_taken", {}),
                "teams": self.teams,
            }))
        elif mtype == P.LOBBY_STATE:
            self.managers = msg.get("managers", [])
            self.events.put(("lobby", {"managers": self.managers}))
        elif mtype == P.TEAM_CLAIMED:
            if msg.get("manager_name") == self.name:
                self.team_id = msg.get("team_id")
            self.events.put(("team_claimed", {
                "team_id": msg.get("team_id"),
                "manager_name": msg.get("manager_name"),
            }))
        elif mtype == P.START_GAME:
            self.events.put(("game_started", {}))
        elif mtype == P.STATE_SYNC:
            self.game_date = msg.get("game_date", self.game_date)
            save_bytes = msg.get("save_bytes", b"")
            self._write_fallback(save_bytes)
            self.events.put(("state_sync", {
                "save_bytes": save_bytes,
                "game_date": self.game_date,
                "label": msg.get("label", ""),
            }))
        elif mtype == P.CONTINUE_DAY:
            self.game_date = msg.get("game_date", self.game_date)
            self.events.put(("day_advanced", {"game_date": self.game_date}))
        elif mtype == P.ADVANCE_STATUS:
            self.events.put(("advance_status", {
                "ready": msg.get("ready", []),
                "waiting": msg.get("waiting", []),
                "ready_count": msg.get("ready_count", 0),
                "needed_count": msg.get("needed_count", 0),
                "host_ready": msg.get("host_ready", False),
                "all_ready": msg.get("all_ready", False),
            }))
        elif mtype == P.TRADE_OFFER:
            self.events.put(("trade_offer", {
                "offer_id": msg.get("offer_id", ""),
                "from_team": msg.get("from_team", ""),
                "from_manager": msg.get("from_manager", ""),
                "offer": msg.get("offer", {}),
            }))
        elif mtype == P.NTC_WAIVER_REQUEST:
            self.events.put(("ntc_waiver_request", {
                "waiver_id": msg.get("waiver_id", ""),
                "player_id": msg.get("player_id", ""),
                "player_name": msg.get("player_name", ""),
                "clause": msg.get("clause", ""),
                "dest_team": msg.get("dest_team", ""),
                "context": msg.get("context", ""),
            }))
        elif mtype == P.DRAFT_CLOCK:
            self.events.put(("draft_clock", {
                "clock_id": msg.get("clock_id", ""),
                "team_id": msg.get("team_id", ""),
                "overall": msg.get("overall", 0),
                "round_num": msg.get("round_num", 0),
                "prospects": msg.get("prospects", []) or [],
            }))
        elif mtype == P.FANTASY_DRAFT_CLOCK:
            self.events.put(("fantasy_draft_clock", {
                "clock_id": msg.get("clock_id", ""),
                "team_id": msg.get("team_id", ""),
                "overall": msg.get("overall", 0),
                "round_num": msg.get("round_num", 0),
                "available_ids": msg.get("available_ids", []) or [],
                "shortlist": msg.get("shortlist", []) or [],
            }))
        elif mtype == P.ACTION_ACK:
            seq = msg.get("action_seq")
            self.events.put(("action_ack", {
                "seq": seq,
                "action": self._pending_actions.pop(seq, "?"),
                "result": msg.get("result", ""),
            }))
        elif mtype == P.ACTION_REJECT:
            seq = msg.get("action_seq")
            self.events.put(("action_rejected", {
                "seq": seq,
                "action": self._pending_actions.pop(seq, "?"),
                "reason": msg.get("reason", ""),
            }))
        elif mtype == P.CHECKPOINT_NOTICE:
            self.events.put(("checkpoint", {
                "label": msg.get("label", ""),
                "game_date": msg.get("game_date", ""),
            }))
        elif mtype == P.CHAT:
            self.events.put(("chat", {"from": msg.get("from", "?"),
                                      "text": msg.get("text", "")}))
        elif mtype == P.ERROR:
            self.events.put(("error", {"message": msg.get("message", "")}))
        elif mtype == P.GOODBYE:
            self._running.clear()
            self._report_disconnected(msg.get("reason", "host closed"))
        # PONG and unknown types are ignored.

    def _write_fallback(self, save_bytes: bytes) -> None:
        """Best-effort emergency copy of the latest snapshot.

        A single rotating file -- never grows the checkpoints folder.
        Failures are swallowed: this must never break the recv loop.
        """
        if not save_bytes:
            return
        try:
            directory = os.path.dirname(self._fallback_path)
            os.makedirs(directory, exist_ok=True)
            tmp = self._fallback_path + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(save_bytes)
            os.replace(tmp, self._fallback_path)
        except OSError:
            pass
