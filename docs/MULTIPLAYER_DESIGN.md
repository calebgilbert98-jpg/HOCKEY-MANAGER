# Puck Dynasty — Multiplayer Phase 1: Design Document

**Status:** core networking + checkpoint infrastructure built and tested
(`test_multiplayer_phase1.py` — 11/11 passing). UI wiring (launcher,
Continue hook, draft hooks) is the remaining integration work, tracked
in `MULTIPLAYER_MERGE_GUIDE.md`.

**Model:** authoritative host, FM-online-career style. One player hosts
the canonical game state; clients connect over a virtual LAN, claim a
team, and send management intents. The host applies them, advances days,
and broadcasts full-state snapshots.

---

## 1. Why this architecture

Three options were evaluated (SI design-review style):

| Option | Verdict |
|---|---|
| Virtual LAN (Radmin VPN / ZeroTier / Hamachi) + TCP host | **Chosen.** Zero port-forwarding, plain sockets, works with the existing pickle save format. |
| Cloud dedicated server (Fly.io / Render free tier) | Deferred to Phase 3. Requires decoupling the sim from tkinter (`main.py` is ~14k lines with logic and UI intertwined) — a refactor project on its own. |
| Delta/state-diff sync | Rejected for Phase 1. Full-state snapshots (a few MB, milliseconds on LAN) are dead simple and bulletproof. Deltas are a Phase-2 optimisation and a Phase-1 bug farm. |

**Hamachi vs Radmin:** Hamachi's free tier caps at 5 users/network and
LogMeIn has let it wither. **Radmin VPN is the recommendation** — free,
no user cap, same virtual-LAN trick. ZeroTier is the backup pick. The
game code doesn't care which one; it just sees a LAN.

## 2. Module map (all new files, zero merge conflicts)

```
multiplayer/
    __init__.py        package marker, PROTOCOL_VERSION = 1
    protocol.py        wire framing + message types + constructors
    net_host.py        MultiplayerHost — accept loop, lobby, broadcast
    net_client.py      MultiplayerClient — connect, claim, actions, fallback
checkpoint_manager.py  rotating crash-recovery checkpoints + session flag
test_multiplayer_phase1.py   headless integration test (11 checks)
```

### 2.1 Wire protocol (`multiplayer/protocol.py`)

Every frame: `4-byte big-endian length + pickle(dict)`.
Payload is always `{"type", "seq", "ts", ...}`. `MessageReader.feed()`
handles partial TCP reads. Pickle is used deliberately — the game's own
save format is pickle, so this keeps the same trust model (trusted LAN
only; **do not expose the port to the open internet**).

Message types:

- **Handshake/lobby:** `HELLO` → `WELCOME` (version-checked; mismatch =
  polite rejection telling the client to update), `CLAIM_TEAM` →
  `TEAM_CLAIMED` + `LOBBY_STATE` broadcast, `START_GAME`.
- **Gameplay:** `ACTION` (intent only, never mutated state) →
  `ACTION_ACK` / `ACTION_REJECT`; `REQUEST_STATE` → `STATE_SYNC`
  (full save blob + game date + label); `CONTINUE_DAY` (host advanced;
  `STATE_SYNC` follows); `CHECKPOINT_NOTICE`.
- **Utility:** `CHAT` (Phase-2 UI), `PING`/`PONG` heartbeat (15s
  interval, 45s timeout), `ERROR`, `GOODBYE`.

Phase-1 `SUPPORTED_ACTIONS`: `set_lines`, `set_tactics`,
`sign_free_agent`, `propose_trade`, `release_player`, `send_to_minors`,
`call_up`. Anything else → `ACTION_REJECT("unsupported_action")`.

### 2.2 Host (`multiplayer/net_host.py`)

`MultiplayerHost(state_provider, host_name, port=27107)`.

- Daemon accept thread + one daemon thread per peer + heartbeat monitor.
- **Hard threading rule:** network threads never touch game objects.
  Incoming `ACTION`s go onto `host.events` (a `queue.Queue`); the
  tkinter main thread drains it via `after()` polling, applies the
  action to the real game, then calls
  `host.resolve_action(client_id, seq, ok, detail)` → sends
  `ACTION_ACK`/`ACTION_REJECT` and rebroadcasts fresh state on success.
- Security checks on every action: sender must have claimed a team;
  `params["team_id"]` must equal the sender's team (no managing other
  clubs); action must be in `SUPPORTED_ACTIONS`.
- `broadcast_state(label)` — snapshot via `state_provider` and push to
  all clients. Called after Continue and after applied actions.
- `announce_day(game_date)` + `broadcast_state()` = the Continue flow.
- `notify_checkpoint(label, game_date)` tells clients the host wrote a
  crash checkpoint (UI toast).

### 2.3 Client (`multiplayer/net_client.py`)

`MultiplayerClient(name)` → `connect(host_ip, port)` blocks until
`WELCOME` (or raises `ConnectionError`).

- One daemon recv thread → `client.events` queue → main-thread polling.
- `claim_team(team_id)`, `send_action(name, params)` → returns seq for
  ACK correlation, `request_state()`, `send_chat(text)`, `disconnect()`.
- **Crash fallback:** every `STATE_SYNC` is also written to a single
  rotating file `saves/checkpoints/client_last_sync.hm` (one file,
  overwritten — never grows). If the host dies, any client can promote
  that file into a new hosted game.

### 2.4 Applying a snapshot (game-side wiring)

Host side — `state_provider` (called on main thread for broadcasts):

```python
import gzip, pickle
def state_provider():
    blob = gzip.compress(pickle.dumps(
        save_mgr.create_save_data(), protocol=pickle.HIGHEST_PROTOCOL))
    return blob, str(gui.current_date), "label"
```

Client side — on `("state_sync", ...)` event (main thread):

```python
save_data = pickle.loads(gzip.decompress(payload["save_bytes"]))
save_mgr._restore_game_state(save_data)   # then gui.update_all_views()
```

`create_save_data()` performs no file I/O and no dialogs (verified in
`save_load_system.py`) — the one main-thread-safe snapshot primitive.

## 3. Crash-safety: the checkpoint system

**Requirement:** a crash mid fantasy-draft (or anywhere) must never
mean starting over — but the host's save folder must not fill up.

Design (`checkpoint_manager.py`):

- Checkpoints live in `saves/checkpoints/` — **never** in `saves/`
  next to manual saves. Manual saves are never touched.
- Fixed ring of 5 slots (`checkpoint_00..04.hm`) + `manifest.json`.
  The oldest entry is overwritten; the folder can never exceed 5
  files + manifest. Atomic writes (temp + `os.replace`) so a crash
  *during* a checkpoint can't corrupt the previous one.
- Manifest entry: slot, filename, label, game date, timestamp,
  monotonic seq (for same-second write ordering), byte size.
- **Checkpoint triggers:**
  - game start → `"Game started"`
  - after every Continue → `"Day <date>"`
  - before fantasy draft → `"Before Fantasy Draft"`
  - every draft round → `"Fantasy Draft - Round <n>"`
  - trade deadline day → `"Trade Deadline"`
- **Crash detection:** `mark_session_start()` writes
  `saves/session.flag` at launch; `mark_clean_shutdown()` removes it
  on tidy exit. A leftover flag at next launch = unclean exit → the
  launcher offers one-click recovery (`recover_latest()` → newest
  checkpoint).
- Multiplayer: the host owns checkpointing; clients get
  `CHECKPOINT_NOTICE`.

Why per-round draft checkpoints: `clear_all_team_rosters_completely`
wipes rosters at draft start, so a mid-draft crash leaves the league
torn. `create_save_data()` reads live objects, so a checkpoint
captures even a half-finished draft — recovery resumes the draft
where it died.

## 4. How to play together (user-facing)

1. Everyone installs **Radmin VPN** (free) and joins the same network.
2. The host notes their Radmin IP (e.g. `26.x.x.x`), starts
   Puck Dynasty → **Host Multiplayer Game**, picks their team.
   The game shows the IP + port (default `27107`).
3. Friends → **Join Multiplayer Game**, enter the host's Radmin IP,
   pick a display name, claim a free team.
4. Host presses **Start** → everyone gets the full league state.
5. Everyone manages their own club; the host's **Continue** advances
   the day for the whole league.

## 5. Test report

`python3 test_multiplayer_phase1.py` (headless, loopback, isolated
temp dir) — 11/11 passing:

1. handshake + session id
2. protocol-mismatch rejection
3. team claims (duplicate claim rejected)
4. ACTION → host queue → `resolve_action` → ACK + state rebroadcast
5. cross-team action rejected
6. unsupported action rejected
7. chat relay + day announce
8. client fallback file written
9. disconnect handling
10. checkpoint ring bounded (7 writes → 3 files, newest-first manifest)
11. crash-flag lifecycle

## 6. Roadmap

- **Phase 1b (UI wiring):** launcher Host/Join buttons + lobby window,
  Continue hook (host broadcast + checkpoint), draft checkpoint hooks,
  client snapshot-apply, crash-recovery prompt. See merge guide.
- **Phase 2:** human-to-human trade negotiation, in-game chat UI,
  Continue voting instead of host-only, delta sync optimisation.
- **Phase 3:** headless dedicated server for 24/7 cloud leagues
  (requires sim/UI decoupling).
