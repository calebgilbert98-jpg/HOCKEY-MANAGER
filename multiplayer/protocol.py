# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
* Pickle is used because the game's own save format is pickle, but frames
  are decoded with a restricted unpickler that only allows plain data
  types (dict/list/str/int/float/bool/bytes/None) -- a malicious peer
  cannot execute code via the wire protocol. Do NOT expose the host port
  to the open internet regardless.
* ACTION messages carry *intent* ("sign free agent X to 2yr deal"),
  never mutated state. The host is the only writer of truth.
"""

from __future__ import annotations

import io
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

# Message types: EHM-style advance sync (all human managers ready up).
# Every active manager -- host included -- marks themselves ready for the
# day to advance; the host advances only when everyone is ready.
READY = "ready"                    # client -> host   {} (done for today)
UNREADY = "unready"                # client -> host   {} (rescind readiness)
ADVANCE_STATUS = "advance_status"  # host -> all      {ready, waiting,
                                   #  ready_count, needed_count, host_ready}

# Message types: human-to-human trade negotiation.
TRADE_OFFER = "trade_offer"        # host -> client   {offer_id, from_team,
                                   #  from_manager, offer: {...}}
TRADE_RESPONSE = "trade_response"  # client -> host   {offer_id,
                                   #  decision: accept|reject}

# Message types: NTC/NMC waiver prompts for a client's player.
# Mirrors the single-player askyesnocancel: the client answers "ask" (ask
# the player to waive), "remove" (pull him from the offer) or "cancel".
NTC_WAIVER_REQUEST = "ntc_waiver_request"  # host -> client {waiver_id,
                                           #  player_id, player_name,
                                           #  clause, dest_team,
                                           #  context: trade|waivers}
NTC_WAIVER_ANSWER = "ntc_waiver_answer"    # client -> host {waiver_id,
                                          #  player_id, choice:
                                          #  ask|remove|cancel}

# Message types: entry-draft pick clock for a client's team.
DRAFT_CLOCK = "draft_clock"        # host -> client   {clock_id, team_id,
                                   #  overall, round_num, prospects:
                                   #  [{id, name, pos, ranking}]}

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
    READY, UNREADY, ADVANCE_STATUS,
    TRADE_OFFER, TRADE_RESPONSE,
    NTC_WAIVER_REQUEST, NTC_WAIVER_ANSWER,
    DRAFT_CLOCK,
    CHAT, PING, PONG, ERROR, GOODBYE,
}

# Phase-1 supported ACTION names (intent strings the host knows how to apply).
# Anything else -> ACTION_REJECT "unsupported_action".
SUPPORTED_ACTIONS = {
    "set_lines",        # params: {team_id, lines: {...}}
    "set_tactics",      # params: {team_id, tactics: {...}}
    "set_captaincy",    # params: {team_id, captain_id, alt_ids: [...]}
    "set_trade_block",  # params: {team_id, player_ids: [...]}
    "sign_free_agent",  # params: {team_id, player_id, contract: {...}}
    "propose_trade",    # params: {team_id, partner_team_id, offer: {...}}
    "release_player",   # params: {team_id, player_id}
    "send_to_minors",   # params: {team_id, player_id}
    "call_up",          # params: {team_id, player_id}
    # Morale / coaching-room actions (Phase 2): mutate the canonical room
    # state on the host; every manager sees the effects via STATE_SYNC.
    "advise_coach",     # params: {team_id, advice_type, target_player_id?}
    "unfeature_player", # params: {team_id, player_id}
    "team_event",       # params: {team_id, event: bag_skate|inspiring_speech|great_practice}
    "set_line_control", # params: {team_id, holder: coach|gm, approach?: discuss|seize}
    "declare_rivalry",  # params: {team_id, target_team, target_kind: team|coach}
    "renounce_rivalry", # params: {team_id, target_team, target_kind: team|coach}
    # Roster management (Phase 2): the client's daily GM verbs, applied to
    # the host's canonical state with the same validation the host's own
    # windows use.
    "sign_free_agent",  # params: {team_id, player_id, salary, years}
    "release_player",   # params: {team_id, player_id}
    "send_to_minors",   # params: {team_id, player_id}; NMC consent is
                       # host-side (NTC_WAIVER_REQUEST, context="waivers")
    "call_up",          # params: {team_id, player_id}
    "claim_waivers",    # params: {team_id, player_id}
    "buyout_player",    # params: {team_id, player_id}
    "extend_contract",  # params: {team_id, player_id, salary, years,
                        #          clause?: none|ntc|nmc|mntc, clause_teams?: int}
    "propose_trade",    # params: {team_id, partner_team_id, offer: {...}}
    "trade_response",   # params: {team_id, offer_id, decision: accept|reject}
    "ntc_waiver_answer",# params: {team_id, player_id, approved: bool}
    # Staff / scouting / practice / room (Phase 2).
    "hire_staff",       # params: {team_id, staff_id, role, salary, years, assignment: nhl|ahl}
    "fire_staff",       # params: {team_id, staff_id}
    "assign_scout",     # params: {team_id, scout_id, region}
    "set_practice",
    "start_practice_plan",  # params: {team_id, player_id, practice_type,
                           #          intensity, total_sessions}
    "offer_sheet",        # params: {team_id, player_id, aav, years}     # params: {team_id, focus, intensity}
    "practice_session", # params: {team_id, player_id, practice_type, intensity, duration, trainer_quality}
    "team_talk",        # params: {team_id, tone, situation, speaker?}
    "press_conference", # params: {team_id, stance, topic?}
    "draft_pick",       # params: {team_id, player_id} (entry draft, on the clock)
    "return_to_junior", # params: {team_id, player_id}
}


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

class ProtocolError(Exception):
    """Raised when a byte stream violates the wire protocol."""


class _SafeUnpickler(pickle.Unpickler):
    """Unpickler restricted to plain protocol data types.

    ``pickle.loads`` on network bytes is remote code execution: a malicious
    peer can run arbitrary Python while the payload decodes. The protocol
    only ever carries plain data (dicts, lists, strings, numbers, bytes,
    booleans, None), so every class lookup outside that allowlist is
    rejected. The wire format is unchanged -- safe peers interoperate.
    """

    _SAFE = frozenset({
        ("builtins", "dict"), ("builtins", "list"), ("builtins", "tuple"),
        ("builtins", "set"), ("builtins", "frozenset"),
        ("builtins", "str"), ("builtins", "int"), ("builtins", "float"),
        ("builtins", "bool"), ("builtins", "bytes"), ("builtins", "bytearray"),
        ("builtins", "complex"),
    })

    def find_class(self, module: str, name: str):
        if (module, name) in self._SAFE:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"blocked unpickle of {module}.{name}: "
            f"not a protocol data type")


def _safe_loads(blob: bytes) -> Any:
    """Decode a protocol frame without allowing code execution."""
    return _SafeUnpickler(io.BytesIO(blob)).load()


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
                msg = _safe_loads(blob)
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


def advance_status(ready: List[str], waiting: List[str],
                   host_ready: bool, all_ready: bool = False) -> Dict[str, Any]:
    """ADVANCE_STATUS payload: who has readied for the day's advance."""
    return {"type": ADVANCE_STATUS, "ready": ready, "waiting": waiting,
            "ready_count": len(ready) + (1 if host_ready else 0),
            "needed_count": len(ready) + len(waiting) + 1,
            "host_ready": host_ready, "all_ready": all_ready}


def trade_offer_msg(offer_id: str, from_team: str, from_manager: str,
                    offer: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": TRADE_OFFER, "offer_id": offer_id,
            "from_team": from_team, "from_manager": from_manager,
            "offer": offer}


def ntc_waiver_request_msg(waiver_id: str, player_id: str, player_name: str,
                           clause: str, dest_team: str,
                           context: str) -> Dict[str, Any]:
    return {"type": NTC_WAIVER_REQUEST, "waiver_id": waiver_id,
            "player_id": player_id, "player_name": player_name,
            "clause": clause, "dest_team": dest_team, "context": context}


def draft_clock_msg(clock_id: str, team_id: str, overall: int,
                    round_num: int,
                    prospects: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"type": DRAFT_CLOCK, "clock_id": clock_id, "team_id": team_id,
            "overall": overall, "round_num": round_num,
            "prospects": prospects}


def error_msg(message: str) -> Dict[str, Any]:
    return {"type": ERROR, "message": message}
