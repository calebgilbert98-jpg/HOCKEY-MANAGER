"""Puck Dynasty multiplayer package (Phase 1).

Authoritative-host model over TCP, designed for virtual-LAN play
(Radmin VPN / ZeroTier / Hamachi). One player hosts the canonical
game state; clients connect, claim a team, and send management
actions. The host applies actions, advances days, and broadcasts
the full game state.

Modules:
    protocol   -- wire framing + message types (no game imports)
    net_host   -- host-side server (accept loop, lobby, broadcast)
    net_client -- client-side connection

Threading rule (hard): all socket I/O lives on daemon threads.
tkinter UI updates are NEVER done from network threads -- push
events into a queue.Queue and let the main thread drain it via
``after()`` polling.
"""

__version__ = "0.1.0"
PROTOCOL_VERSION = 1
