# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Shared fixtures for adversarial multiplayer testing.

Two layers:
  * Transport layer: real MultiplayerHost + MultiplayerClient pairs over
    localhost sockets, fake state providers. For rejoin, migration,
    ready-gate, race, and malformed-input chaos.
  * Handler layer: the real HockeyManagerGUI._mp_* host handlers bound to
    a fake app (SimpleNamespace, like qa_mp_parity.py) with synthetic
    teams/players. For malformed params, authz, and event-boundary chaos.
"""
import gzip
import json
import os
import pickle
import shutil
import socket
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multiplayer.net_host import MultiplayerHost
from multiplayer.net_client import MultiplayerClient
from multiplayer import protocol as P

PASS, FAIL = [], []
ACTION_COUNT = {"n": 0}


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))
    return bool(cond)


def summary():
    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed, "
          f"{ACTION_COUNT['n']} actions fired ===")
    if FAIL:
        print("FAILURES:")
        for f in FAIL:
            print(f"  - {f}")
    return len(FAIL) == 0


# ---------------------------------------------------------------------------
# Transport fixtures
# ---------------------------------------------------------------------------

FAKE_BLOB = gzip.compress(pickle.dumps({"league": "chaos", "day": 1}))


def fake_state_provider(label="chaos-sync"):
    def _p():
        return FAKE_BLOB, "2026-10-05", label
    return _p


_drain_spill = {}


def drain(client, want, timeout=5.0):
    """Collect client events until `want` seen; spill the rest."""
    spill = _drain_spill.setdefault(("c", id(client)), [])
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
    spill = _drain_spill.setdefault(("h", id(host)), [])
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


class ChaosNet:
    """One host + N clients on a private port, temp cwd."""

    def __init__(self, port, host_name="ChaosHost", n_clients=2):
        self.port = port
        self.tmp = tempfile.mkdtemp(prefix="pd_chaos_")
        self._old_cwd = os.getcwd()
        os.chdir(self.tmp)
        self.host = MultiplayerHost(fake_state_provider(), host_name=host_name,
                                    port=port)
        self.host.start()
        assert self.host.running
        self.clients = []
        for i in range(n_clients):
            c = MultiplayerClient(f"Chaos{i+1}")
            c.connect("127.0.0.1", port)
            self.clients.append(c)

    def claim(self, client_idx, team_id):
        c = self.clients[client_idx]
        c.claim_team(team_id)
        # TEAM_CLAIMED broadcasts to everyone; wait for OUR claim.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            k, p = drain(c, "team_claimed", timeout=1.0)
            if p["team_id"] == team_id:
                return p
        raise AssertionError(f"timeout waiting for claim of {team_id}")

    def fire(self, client_idx, action, params, auto_resolve=True,
             ok=True, detail="chaos-ok"):
        """Send an action; optionally auto-resolve it on the host side."""
        ACTION_COUNT["n"] += 1
        c = self.clients[client_idx]
        seq = c.send_action(action, params)
        k, payload = drain_host(self.host, "action")
        if auto_resolve:
            self.host.resolve_action(payload["client_id"], payload["seq"],
                                     ok, detail)
            want = "action_ack" if ok else "action_rejected"
            k2, p2 = drain(c, want)
            return seq, payload, p2
        return seq, payload, None

    def kill_client_socket(self, client_idx):
        """Hard-kill a client's socket without a clean close (pull the plug)."""
        c = self.clients[client_idx]
        try:
            c._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            c._sock.close()
        except Exception:
            pass

    def set_client_token(self, token):
        """Write a distinct rejoin token (simulates another machine)."""
        import os as _os
        _dir = _os.path.join(_os.path.expanduser("~"), ".puck-dynasty")
        _os.makedirs(_dir, exist_ok=True)
        with open(_os.path.join(_dir, "mp_client_token"), "w") as fh:
            fh.write(token)

    def teardown(self):
        for c in self.clients:
            try:
                c.disconnect()
            except Exception:
                pass
        try:
            self.host.stop()
        except Exception:
            pass
        os.chdir(self._old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)
        # The client persists its rejoin token at ~/.puck-dynasty/ --
        # keep it (rejoin tests need it) but note it.
