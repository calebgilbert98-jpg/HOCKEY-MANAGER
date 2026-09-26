"""Headless integration test for Phase 1 multiplayer + checkpoints.

Run:  python3 test_multiplayer_phase1.py
Covers: handshake, version check, team claims (incl. duplicate
rejection), ACTION queue -> resolve -> ACK + rebroadcast, STATE_SYNC
delivery, client fallback file, checkpoint ring bounds, manifest,
crash-flag lifecycle.
"""
import gzip
import json
import os
import pickle
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multiplayer import PROTOCOL_VERSION
from multiplayer.net_host import MultiplayerHost, DEFAULT_PORT
from multiplayer.net_client import MultiplayerClient, ConnectionError
import checkpoint_manager as cm

TMP = tempfile.mkdtemp(prefix="pd_mp_test_")
os.chdir(TMP)  # isolate saves/ + checkpoints/

FAKE_BLOB = gzip.compress(pickle.dumps({"league": "test", "day": 42}))
state_calls = {"n": 0}


def fake_state_provider():
    state_calls["n"] += 1
    return FAKE_BLOB, "2026-10-05", "test-sync"


# Spill buffers: poll_events() drains the whole queue, so a drain() call
# must not discard events it isn't looking for (e.g. ACTION_ACK and the
# STATE_SYNC rebroadcast arrive in the same poll window).
_drain_spill = {}


def _spill_for(key):
    return _drain_spill.setdefault(key, [])


def drain(client, want, timeout=5.0):
    """Collect client events until `want` kind seen or timeout.

    Non-matching events are spilled to a per-client buffer and re-checked
    on later calls, so back-to-back messages are never lost.
    """
    spill = _spill_for(("client", id(client)))
    deadline = time.time() + timeout
    while time.time() < deadline:
        for i, (kind, payload) in enumerate(spill):
            if kind == want:
                del spill[i]
                return kind, payload
        found = None
        for kind, payload in client.poll_events():
            if kind == want and found is None:
                found = (kind, payload)
            else:
                spill.append((kind, payload))
        if found is not None:
            return found
        time.sleep(0.05)
    raise AssertionError(
        f"timeout waiting for {want}; spill={[k for k, _ in spill]}")


def drain_host(host, want, timeout=5.0):
    spill = _spill_for(("host", id(host)))
    deadline = time.time() + timeout
    while time.time() < deadline:
        for i, (kind, payload) in enumerate(spill):
            if kind == want:
                del spill[i]
                return kind, payload
        found = None
        for kind, payload in host.poll_events():
            if kind == want and found is None:
                found = (kind, payload)
            else:
                spill.append((kind, payload))
        if found is not None:
            return found
        time.sleep(0.05)
    raise AssertionError(f"host timeout waiting for {want}")


PORT = 27199
host = MultiplayerHost(fake_state_provider, host_name="Commish", port=PORT)
host.start()
assert host.running

# --- 1. handshake + welcome -------------------------------------------
c1 = MultiplayerClient("Muck")
welcome = c1.connect("127.0.0.1", PORT)
assert welcome["game_date"] == "unknown"  # no broadcast yet
assert c1.session_id
print("1. handshake OK, session:", c1.session_id)

# --- 2. version mismatch rejected --------------------------------------
from multiplayer import protocol as P
import socket as _s
s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
s.connect(("127.0.0.1", PORT))
s.sendall(P.encode_message(P.HELLO, 1, P.hello("OldTimer", 999)))
s.settimeout(3)
data = s.recv(65536)
r = P.MessageReader()
msgs = list(r.feed(data))
assert any(m["type"] == P.ERROR and "mismatch" in m["message"] for m in msgs), msgs
s.close()
print("2. protocol-mismatch rejected OK")

# --- 3. team claims ----------------------------------------------------
c2 = MultiplayerClient("Cale")
c2.connect("127.0.0.1", PORT)
c1.claim_team("TOR")
kind, payload = drain(c1, "team_claimed")
assert payload["team_id"] == "TOR" and payload["manager_name"] == "Muck"
c2.claim_team("TOR")  # duplicate -> ERROR
kind, payload = drain(c2, "error")
assert "already managed" in payload["message"], payload
c2.claim_team("EDM")
drain(c2, "team_claimed")
# host saw both claims
kinds = {k for k, _ in host.poll_events()}
print("3. claims OK (duplicate rejected)")

# --- 4. ACTION round-trip: queue -> resolve -> ACK + rebroadcast ------
seq = c1.send_action("set_lines", {"team_id": "TOR", "lines": {"L1": ["a"]}})
kind, payload = drain_host(host, "action")
assert payload["action"] == "set_lines" and payload["manager"] == "Muck"
assert payload["params"]["team_id"] == "TOR"
host.resolve_action(payload["client_id"], payload["seq"], True, "lines updated")
kind, payload = drain(c1, "action_ack")
assert payload["seq"] == seq and payload["result"] == "lines updated"
kind, payload = drain(c1, "state_sync")  # rebroadcast after ACK
assert payload["save_bytes"] == FAKE_BLOB
print("4. action ACK + state rebroadcast OK")

# --- 5. cross-team action rejected --------------------------------------
seq2 = c2.send_action("release_player", {"team_id": "TOR", "player_id": "x"})
kind, payload = drain(c2, "action_rejected")
assert payload["seq"] == seq2 and "own team" in payload["reason"]
print("5. cross-team action rejected OK")

# --- 6. unsupported action rejected -------------------------------------
c1._send(P.ACTION, {"type": P.ACTION, "action": "nuke_league", "params": {}})
kind, payload = drain(c1, "action_rejected")
assert "unsupported action" in payload["reason"]
print("6. unsupported action rejected OK")

# --- 7. chat + day announce ---------------------------------------------
c2.send_chat("gg")
kind, payload = drain(c1, "chat")
assert payload["from"] == "Cale" and payload["text"] == "gg"
host.announce_day("2026-10-06")
host.broadcast_state("Day advanced")
kind, payload = drain(c1, "day_advanced")
assert payload["game_date"] == "2026-10-06"
drain(c1, "state_sync")
print("7. chat + day announce OK")

# --- 8. client fallback file --------------------------------------------
fb = os.path.join("saves", "checkpoints", "client_last_sync.hm")
assert os.path.exists(fb) and open(fb, "rb").read() == FAKE_BLOB
print("8. client fallback file OK")

# --- 9. disconnect -------------------------------------------------------
c2.disconnect()
kind, payload = drain_host(host, "manager_left")
assert payload["name"] == "Cale"
print("9. disconnect OK")

host.stop()
c1.disconnect()

# --- 10. checkpoint ring --------------------------------------------------
class FakeSaveManager:
    def __init__(self):
        self.day = 0
    def create_save_data(self):
        return {"day": self.day, "teams": ["TOR"]}
    def load_game(self, path):
        assert os.path.exists(path)
        return True

fsm = FakeSaveManager()
cpm = cm.CheckpointManager(fsm, slots=3,
                           game_date_fn=lambda: f"Day {fsm.day}")
paths = []
for i in range(7):  # more than slots -> ring must bound the folder
    fsm.day = i
    paths.append(cpm.checkpoint(f"Day {i}"))
files = [f for f in os.listdir(os.path.join("saves", "checkpoints"))
         if f.startswith("checkpoint_") and f.endswith(".hm")]
assert len(files) == 3, files
entries = cpm.list_checkpoints()
assert len(entries) == 3 and entries[0]["label"] == "Day 6", entries
assert cpm.latest()["label"] == "Day 6"
assert cpm.recover_latest()["label"] == "Day 6"
# manifest is valid JSON and bounded
man = json.load(open(os.path.join("saves", "checkpoints", "manifest.json")))
assert len(man["entries"]) == 3
print("10. checkpoint ring bounded OK (7 writes -> 3 files)")

# --- 11. crash flag lifecycle ----------------------------------------------
assert not cm.previous_session_crashed()
cm.mark_session_start()
assert cm.previous_session_crashed()
cm.mark_clean_shutdown()
assert not cm.previous_session_crashed()
print("11. crash-flag lifecycle OK")

# --- 12. async snapshot: non-blocking, busy flag, coalescing ------------
gate = threading.Event()
pre_ran = {"n": 0}
gated_calls = {"n": 0}


def gated_provider():
    gated_calls["n"] += 1
    assert gate.wait(5.0), "snapshot worker never released"
    return FAKE_BLOB, "2026-10-05", "gated-sync"


def pre_fn():
    pre_ran["n"] += 1


host2 = MultiplayerHost(gated_provider, host_name="Commish2", port=PORT)
host2.start()
c3 = MultiplayerClient("Async")
c3.connect("127.0.0.1", PORT)

t0 = time.time()
assert host2.broadcast_state_async("first", pre_broadcast=pre_fn) is True
assert time.time() - t0 < 1.0, "async broadcast blocked the caller"
assert host2.snapshot_busy is True
# A second request while busy coalesces instead of spawning a worker.
assert host2.broadcast_state_async("second") is False
assert gated_calls["n"] == 1
gate.set()  # release the worker
drain_host(host2, "snapshot_done", timeout=5.0)
assert host2.snapshot_busy is False
assert pre_ran["n"] == 1, pre_ran
# Both snapshots were delivered, in order; pending carried no pre_broadcast.
k1, p1 = drain(c3, "state_sync")
assert p1["label"] == "first" and p1["save_bytes"] == FAKE_BLOB, p1
k2, p2 = drain(c3, "state_sync")
assert p2["label"] == "second", p2
assert gated_calls["n"] == 2, gated_calls
host2.stop()
c3.disconnect()
print("12. async snapshot (non-blocking, coalesced) OK")

shutil.rmtree(TMP, ignore_errors=True)
print(f"\nALL PHASE-1 INTEGRATION TESTS PASSED (state_provider calls: {state_calls['n']})")
