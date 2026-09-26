"""Wire protocol for Puck Dynasty multiplayer (Phase 1).

Framing: every message on the wire is::

    +------------------+-------------------------+
    | 4-byte BE length | pickle payload (length) |
    +------------------+-------------------------+

The unpickled payload is always a dict with at least::

    {"type": <MSG_* constant>, "seq": <int>, "ts": <float>}

``seq`` is a per-connection monotonically increasing number assigned
by the sender. ``ts`` is time.time() at send.

Message types
-------------
Handshake / lobby:
    HELLO          client -> host   {name, version}
    WELCOME        host -> client   {session_id, game_date, teams_taken,
                                    your_team}
    CLAIM_TEAM     client -> host   {team_id}
    TEAM_CLAIMED   host -> all      {team_id, manager_name}
    LOBBY_STATE    host -> all      {managers: [{name, team_id}], can_start}
    START_GAME     host -> all      {} (+ STATE_SYNC follows)

Gameplay:
    ACTION         client -> host   {action, params}
    ACTION_ACK     host -> client   {action, result}
    ACTION_REJECT  host -> client   {action, reason}
    REQUEST_STATE  client -> host   {}
    STATE_SYNC     host -> client   {save_bytes, game_date, label}
    CONTINUE_DAY   host -> all      {game_date}      (day was advanced;
                                                     STATE_SYNC follows)
    CHECKPOINT_NOTICE host -> all   {label, game_date}

Utility:
    CHAT           either -> all    {from, text}      (Phase 2 UI)
    PING           either -> either {}
    PONG           either -> either {}
    ERROR          host -> client   {message}
    GOODBYE        either -> either {reason}

Design notes (from the SI playbook):
* Full-state sync, not deltas. The save blob is a few MB; on a LAN
  that is milliseconds. Deltas are a Phase-2 optimisation and a
  Phase-1 bug farm.
* Pickle is used because the game's own save format is pickle and
  this is a trusted-LAN feature (same trust model as the save
  files). Do NOT expose the host port to the open internet.
* ACTION messages carry *intent* ("sign free agent X to 2yr deal"),
  never mutated state. The host is the only writer of truth.
"""

from __future__ import annotations

import pickle
import struct
import time
from typing import Any, Dict, Iterator, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEADER_FMT = ">I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

#: Refuse any single message larger than this (corrupt-stream guard).
MAX_MESSAGE_SIZE = 256 * 1024 * 1024  # 256 MB

# Message types: handshake / lobby
HELLO = "hello"
WELCOME = "welcome"
CLAIM_TEAM = "claim_team"
TEAM_CLAIMED = "team_claimed"
LOBBY_STATE = "lobby_state"
START_GAME = "start_game"

# Message types: gameplay
ACTION = "action"
ACTION_ACK = "action_ack"
ACTION_REJECT = "action_reject"
REQUEST_STATE = "request_state"
STATE_SYNC = "state_sync"
CONTINUE_DAY = "continue_day"
CHECKPOINT_NOTICE = "checkpoint_notice"

# Message types: utility
CHAT = "chat"
PING = "ping"
PONG = "pong"
ERROR = "error"
GOODBYE = "goodbye"

ALL_TYPES = {
    HELLO, WELCOME, CLAIM_TEAM, TEAM_CLAIMED, LOBBY_STATE, START_GAME,
    ACTION, ACTION_ACK, ACTION_REJECT, REQUEST_STATE, STATE_SYNC,
    CONTINUE_DAY, CHECKPOINT_NOTICE,
    CHAT, PING, PONG, ERROR, GOODBYE,
}

# Phase-1 supported ACTION names (intent strings the host knows how to apply).
# Anything else -> ACTION_REJECT "unsupported_action".
SUPPORTED_ACTIONS = {
    "set_lines",        # params: {team_id, lines: {...}}
    "set_tactics",      # params: {team_id, tactics: {...}}
    "sign_free_agent",  # params: {team_id, player_id, contract: {...}}
    "propose_trade",    # params: {team_id, partner_team_id, offer: {...}}
    "release_player",   # params: {team_id, player_id}
    "send_to_minors",   # params: {team_id, player_id}
    "call_up",          # params: {team_id, player_id}
}


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

class ProtocolError(Exception):
    """Raised when a byte stream violates the wire protocol."""


def encode_message(msg_type: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> bytes:
    """Serialize one message to length-prefixed bytes ready for send()."""
    if msg_type not in ALL_TYPES:
        raise ProtocolError(f"unknown message type: {msg_type!r}")
    body = {"type": msg_type, "seq": seq, "ts": time.time()}
    if payload:
        body.update(payload)
    blob = pickle.dumps(body, protocol=pickle.HIGHEST_PROTOCOL)
    if len(blob) > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"message too large: {len(blob)} bytes")
    return struct.pack(HEADER_FMT, len(blob)) + blob


class MessageReader:
    """Incremental decoder for the length-prefixed stream.

    TCP gives you arbitrary chunks; feed() whatever arrives and
    iterate the generator for each complete message decoded::

        reader = MessageReader()
        for msg in reader.feed(sock.recv(65536)):
            handle(msg)
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> Iterator[Dict[str, Any]]:
        if data:
            self._buf.extend(data)
        while True:
            if len(self._buf) < HEADER_SIZE:
                return
            (length,) = struct.unpack_from(HEADER_FMT, self._buf)
            if length > MAX_MESSAGE_SIZE:
                raise ProtocolError(f"frame too large: {length} bytes")
            if len(self._buf) < HEADER_SIZE + length:
                return  # wait for more bytes
            blob = bytes(self._buf[HEADER_SIZE:HEADER_SIZE + length])
            del self._buf[:HEADER_SIZE + length]
            try:
                msg = pickle.loads(blob)
            except Exception as exc:  # corrupt frame -> drop connection
                raise ProtocolError(f"unpicklable frame: {exc}") from exc
            if not isinstance(msg, dict) or "type" not in msg:
                raise ProtocolError("malformed message: not a protocol dict")
            yield msg

    def reset(self) -> None:
        self._buf.clear()


# ---------------------------------------------------------------------------
# Message constructors (keeps call sites honest about required fields)
# ---------------------------------------------------------------------------

def hello(name: str, version: int) -> Dict[str, Any]:
    return {"type": HELLO, "name": name, "version": version}


def welcome(session_id: str, game_date: str, teams_taken: Dict[str, str],
            teams: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """WELCOME payload. ``teams`` is the full claimable roster
    (additive optional field -- older hosts simply omit it)."""
    return {"type": WELCOME, "session_id": session_id,
            "game_date": game_date, "teams_taken": teams_taken,
            "teams": teams or []}


def claim_team(team_id: str) -> Dict[str, Any]:
    return {"type": CLAIM_TEAM, "team_id": team_id}


def team_claimed(team_id: str, manager_name: str) -> Dict[str, Any]:
    return {"type": TEAM_CLAIMED, "team_id": team_id, "manager_name": manager_name}


def lobby_state(managers: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"type": LOBBY_STATE, "managers": managers}


def action(action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": ACTION, "action": action_name, "params": params}


def state_sync(save_bytes: bytes, game_date: str, label: str) -> Dict[str, Any]:
    return {"type": STATE_SYNC, "save_bytes": save_bytes,
            "game_date": game_date, "label": label}


def continue_day(game_date: str) -> Dict[str, Any]:
    return {"type": CONTINUE_DAY, "game_date": game_date}


def checkpoint_notice(label: str, game_date: str) -> Dict[str, Any]:
    return {"type": CHECKPOINT_NOTICE, "label": label, "game_date": game_date}


def chat_msg(from_name: str, text: str) -> Dict[str, Any]:
    return {"type": CHAT, "from": from_name, "text": text}


def error_msg(message: str) -> Dict[str, Any]:
    return {"type": ERROR, "message": message}
