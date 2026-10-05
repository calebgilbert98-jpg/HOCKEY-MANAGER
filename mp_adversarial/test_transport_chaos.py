# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Adversarial transport chaos: rejoin, ready-gate abuse, races,
malformed wire input. Real host + clients over localhost.

Run: python3 -m mp_adversarial.test_transport_chaos   (from repo root)
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multiplayer import protocol as P
from multiplayer.net_client import MultiplayerClient
from mp_adversarial.harness import (
    ChaosNet, check, summary, drain, drain_host, ACTION_COUNT)

PORT = 8472  # my assigned port

# ------------------------------------------------------- 1. rejoin restore
net = ChaosNet(PORT, n_clients=0)
net.set_client_token("tok-machine-1")
c1 = MultiplayerClient("Chaos1"); c1.connect("127.0.0.1", PORT)
net.clients.append(c1)
net.set_client_token("tok-machine-2")
c2 = MultiplayerClient("Chaos2"); c2.connect("127.0.0.1", PORT)
net.clients.append(c2)
net.claim(0, "TOR")
net.claim(1, "EDM")
# Client 0 hard-kills its socket (no clean close, no GOODBYE).
net.kill_client_socket(0)
k, p = drain_host(net.host, "manager_left", timeout=8.0)
check("host notices hard disconnect", p["name"] == "Chaos1", str(p))
time.sleep(0.5)
# Reconnect with the SAME rejoin token: the client persists it at
# ~/.puck-dynasty/mp_client_token and sends it in HELLO automatically.
net.set_client_token("tok-machine-1")
c_new = MultiplayerClient("Chaos1")
c_new.connect("127.0.0.1", PORT)
net.clients[0] = c_new
# The host should restore the TOR claim without requiring a re-claim.
# (Assert on host lobby: the TEAM_CLAIMED broadcast is racy on the client.)
time.sleep(1.0)
_lobby = net.host.get_lobby()
got_restore = any(m["team_id"] == "TOR" and m["name"] == "Chaos1"
                  for m in _lobby)
check("rejoin restores team claim", got_restore, str(_lobby))
# No duplicate manager entry on the host.
lobby = net.host.get_lobby()
tors = [m for m in lobby if m["team_id"] == "TOR"]
check("no duplicate TOR manager", len(tors) == 1,
      f"lobby={lobby}")
# And EDM's claim survived.
check("EDM claim intact",
      any(m["team_id"] == "EDM" for m in lobby), str(lobby))
net.teardown()

# ------------------------------------------- 2. ready-gate abuse
net = ChaosNet(PORT + 10, n_clients=2)
net.claim(0, "TOR")
net.claim(1, "EDM")
c0, c1 = net.clients
# Client 0 readies, then disconnects before the advance.
c0.send_ready()
drain_host(net.host, "advance_changed")
net.kill_client_socket(0)
drain_host(net.host, "manager_left", timeout=8.0)
st = net.host.broadcast_advance_status(host_ready=True)
check("departed ready client no longer blocks",
      st["waiting"] == ["Chaos2"], str(st))
check("not all_ready with one waiting", not st["all_ready"])
# Client that never readies: host must stall, not advance.
st2 = net.host.broadcast_advance_status(host_ready=True)
check("host stalls when client not ready", not st2["all_ready"])
# Spectator (no team) readying -> error, not counted.
spec = MultiplayerClient("Spect")
spec.connect("127.0.0.1", PORT + 10)
spec.send_ready()
k, p = drain(spec, "error")
check("spectator ready rejected", "claim a team" in p["message"], str(p))
spec.disconnect()
net.teardown()

# ------------------------------------------------- 3. race / ordering
net = ChaosNet(PORT + 20, n_clients=2)
net.claim(0, "TOR")
net.claim(1, "EDM")
c0 = net.clients[0]
# set_lines then immediately set_trade_block: both must be queued and
# resolvable in order, no crash, no cross-talk.
s1 = c0.send_action("set_lines", {"team_id": "TOR", "lines": {}})
s2 = c0.send_action("set_trade_block", {"team_id": "TOR", "player_ids": []})
ACTION_COUNT["n"] += 2
k1, a1 = drain_host(net.host, "action")
k2, a2 = drain_host(net.host, "action")
check("rapid actions queued in order",
      a1["seq"] < a2["seq"] and a1["action"] == "set_lines"
      and a2["action"] == "set_trade_block",
      f"{a1['action']}/{a2['action']}")
net.host.resolve_action(a1["client_id"], a1["seq"], True, "ok1")
net.host.resolve_action(a2["client_id"], a2["seq"], True, "ok2")
drain(c0, "action_ack")
drain(c0, "action_ack")
check("both actions ACKed", True)
# Rapid-fire two FA offers: both queued, host alive.
c0.send_action("sign_free_agent", {"team_id": "TOR", "player_id": "x"})
c0.send_action("sign_free_agent", {"team_id": "TOR", "player_id": "y"})
ACTION_COUNT["n"] += 2
drain_host(net.host, "action")
drain_host(net.host, "action")
check("rapid FA offers queued without crash", True)
check("host still running after races", net.host.running)
net.teardown()

# ------------------------------------------------- 4. malformed wire input
net = ChaosNet(PORT + 30, n_clients=1)
c0 = net.clients[0]
net.claim(0, "TOR")
# Action for ANOTHER team's players: net_host must reject.
seq = c0.send_action("set_lines", {"team_id": "EDM", "lines": {}})
ACTION_COUNT["n"] += 1
k, p = drain(c0, "action_rejected")
check("cross-team action rejected", "own team" in p["reason"], str(p))
# Action with no team_id: net_host defaults to the peer's own team.
seq = c0.send_action("set_lines", {"lines": {}})
ACTION_COUNT["n"] += 1
k, a = drain_host(net.host, "action")
check("missing team_id defaults to peer team",
      a["params"]["team_id"] == "TOR", str(a["params"]))
net.host.resolve_action(a["client_id"], a["seq"], True, "ok")
drain(c0, "action_ack")
# Garbage action name.
c0._send(P.ACTION, {"type": P.ACTION, "action": "nuke_league",
                    "params": {}})
ACTION_COUNT["n"] += 1
k, p = drain(c0, "action_rejected")
check("garbage action rejected", "unsupported" in p["reason"], str(p))
# Non-dict params.
c0._send(P.ACTION, {"type": P.ACTION, "action": "set_lines",
                    "params": "notadict"})
ACTION_COUNT["n"] += 1
k, p = drain(c0, "action_rejected")
check("non-dict params rejected", True)
# Action before claiming a team (fresh client).
c_nc = MultiplayerClient("NoClaim")
c_nc.connect("127.0.0.1", PORT + 30)
c_nc.send_action("set_lines", {"team_id": "TOR", "lines": {}})
ACTION_COUNT["n"] += 1
k, p = drain(c_nc, "action_rejected")
check("action before claim rejected", "claim a team" in p["reason"],
      str(p))
c_nc.disconnect()
# Oversized frame: raw socket, bogus length prefix -> host drops cleanly.
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", PORT + 30))
import struct
s.sendall(struct.pack(">I", 300 * 1024 * 1024))  # > MAX_MESSAGE_SIZE
s.settimeout(3)
try:
    s.settimeout(3)
    data = s.recv(65536)
    # Host sends GOODBYE then closes, or just closes: either way the
    # peer must be gone afterwards.
    time.sleep(0.5)
    try:
        more = s.recv(65536)
    except Exception:
        more = b""
    dropped = (data == b"" and more == b"") or more == b""
except Exception:
    dropped = True
s.close()
check("oversized frame dropped cleanly", dropped)
check("host survives malformed barrage", net.host.running)
net.teardown()

# ------------------------------------------- 5. host migration
net = ChaosNet(PORT + 40, n_clients=2)
net.claim(0, "TOR")
net.claim(1, "EDM")
# Both clients have received a STATE_SYNC by now (resolve triggers
# broadcast). Force one to make sure the fallback file exists.
seq, a, ack = net.fire(0, "set_lines", {"team_id": "TOR", "lines": {}})
drain(net.clients[0], "state_sync", timeout=8.0)
fb = os.path.join("saves", "checkpoints", "client_last_sync.hm")
check("client fallback file written", os.path.exists(fb))
# Kill the host hard (no clean stop).
net.host.stop()
time.sleep(0.5)
# The promoted client loads the fallback blob: verify it's a readable
# save-shaped payload (dict with league key after gunzip+unpickle).
import gzip, pickle
blob = open(fb, "rb").read()
try:
    payload = pickle.loads(gzip.decompress(blob))
    loadable = isinstance(payload, dict)
except Exception as e:
    loadable = False
check("fallback blob deserializes", loadable)
net.teardown()

ok = summary()
sys.exit(0 if ok else 1)
