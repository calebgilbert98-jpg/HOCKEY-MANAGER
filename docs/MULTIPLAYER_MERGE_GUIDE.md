# Multiplayer Phase 1 — Merge Guide for Collaborators

**Purpose:** if you're building on a separate branch/machine, this is
the exact list of what Phase 1 adds and what it touches, so you can
merge without guesswork. Read this before rebasing.

**Design rationale:** `docs/MULTIPLAYER_DESIGN.md`.
**Test:** `python3 test_multiplayer_phase1.py` (11/11 passing, headless).

---

## 1. Files ADDED (new — no merge conflicts possible)

| File | What it is |
|---|---|
| `multiplayer/__init__.py` | Package marker. `PROTOCOL_VERSION = 1` lives here — **bump it** if you change the wire format; mismatched clients are rejected with an "update your game" message. |
| `multiplayer/protocol.py` | Wire framing (4-byte length + pickle), all message types, `MessageReader` (partial TCP reads), message constructors, `SUPPORTED_ACTIONS`. No game imports — safe to unit-test standalone. |
| `multiplayer/net_host.py` | `MultiplayerHost`: accept loop, lobby, team claims, action validation, state broadcast. Daemon threads only; game objects are never touched off the main thread (actions are queued for the UI to apply via `resolve_action`). |
| `multiplayer/net_client.py` | `MultiplayerClient`: connect/handshake, claim, actions, snapshot fallback. Writes `saves/checkpoints/client_last_sync.hm` on every `STATE_SYNC` (single rotating file). |
| `checkpoint_manager.py` | `CheckpointManager`: 5-slot rotating ring in `saves/checkpoints/` + `manifest.json`; atomic writes; `recover_latest()`; session-flag helpers (`mark_session_start` / `mark_clean_shutdown` / `previous_session_crashed`); `checkpoint_summary()`. |
| `test_multiplayer_phase1.py` | Headless integration test (loopback host + 2 clients, checkpoint ring, crash flag). Run it after any merge touching these files. |
| `docs/MULTIPLAYER_DESIGN.md` | This phase's architecture, protocol, and user-facing setup (Radmin VPN). |
| `docs/MULTIPLAYER_MERGE_GUIDE.md` | This file. |

**Rule:** never edit the files above to add game logic. They are
UI-agnostic infrastructure. Game-specific behaviour plugs in through
the callbacks described in section 3.

## 2. Files MODIFIED (integration hooks — merge carefully)

> **Status 2026-09-26: all hooks below are IMPLEMENTED** in the working
> tree (nothing committed yet — see section 5). The descriptions that
> follow document what was actually wired, with real locations. New
> blocks are marked `# --- MULTIPLAYER ---` in the source.

### 2a. `enhanced_launcher.py` (canonical launcher) — IMPLEMENTED

1. **`_create_action_bar`** — two `_ThemedButton`s next to START GAME:
   `"HOST MULTIPLAYER"` → `self._host_multiplayer`,
   `"JOIN MULTIPLAYER"` → `self._join_multiplayer`.
2. **New methods** (all in one `# --- MULTIPLAYER (Phase 1) ---` block
   after `_create_action_bar`):
   - `_host_multiplayer()` — dialog (display name, port) → sets
     `_mp_mode="host"` / `_mp_config` → continues through the normal
     `_start_new_game()` flow.
   - `_wire_multiplayer_host(app, gm)` — called from `_start_main_game`
     right after `HockeyManagerGUI` is built: creates
     `CheckpointManager(save_mgr, game_date_fn=...)`, attaches it to
     `app` and `gm` (`gm.checkpoint_manager` — the draft hooks read it
     there), builds `MultiplayerHost(state_provider, host_name, port,
     get_teams=...)`, starts it, checkpoints `"Game started"`,
     starts the GUI poll loop, opens the host lobby.
   - `_show_host_lobby(app, host, port)` — Toplevel with the machine's
     LAN IPs (Radmin IP highlighted in the label), live manager list
     (1s refresh), `START LEAGUE` → `host.start_game()`.
   - `_join_multiplayer()` / `_join_connect(cfg)` — dialog (name, host
     IP, port); `connect()` runs in a daemon thread with a
     "Connecting…" window (it blocks); failures show the reason.
   - `_show_client_lobby(client, welcome)` — scrollable team-claim
     buttons (from the WELCOME `teams` list, disabled when taken),
     manager list, 250ms poll; on `game_started` shows "Syncing…", on
     first `state_sync` builds the game.
   - `_claim_team()`, `_build_client_game()` — constructs
     `GameManager()`, `HockeyManagerGUI(gm, mp_client=client)`, applies
     the snapshot (see 2b), runs `mainloop()`.
   - `_check_crash_recovery()` (scheduled `after(800)` in `__init__`)
     + `_recover_from_checkpoint(entry)` — "Recover last session?"
     dialog → rebuilds the game from the latest checkpoint file.
   - `_mp_local_ips()` — candidate LAN/VPN IPs for the host lobby.
3. **Session flag** lives in **`launcher.py:main()`** (the true entry):
   `mark_session_start()` at launch + `atexit.register(mark_clean_shutdown)`
   — so a leftover flag at next launch means the game died uncleanly.
   The launcher itself only *reads* the flag (see above).

### 2b. `main.py` — `HockeyManagerGUI` — IMPLEMENTED

1. **`__init__(self, game_manager, mp_host=None, mp_client=None)`** —
   stores both; sets `self.checkpoint_manager = None` (attached by the
   launcher, not a constructor kwarg — keeps the signature stable for
   the other call sites in `launch_game.py`, `simple_launcher.py`,
   etc.); starts `after(400, self._poll_multiplayer)` when either is set.
   All `None` → single-player path untouched.
2. **`simulate_day`** (the Continue handler, synchronous on the main
   thread): at the end of the `try` block — so it runs **only on a
   successful day advance** (the fantasy-draft guard and
   end-of-season early returns skip it):
   `checkpoint_manager.checkpoint(f"Day {self.current_date}")`
   (+ `notify_checkpoint` to clients), then
   `mp_host.announce_day(...)` + `mp_host.broadcast_state(...)`.
   Every step is wrapped so a network/checkpoint failure can never
   break the sim.
3. **Main-thread bridge** (new methods after `simulate_day`):
   - `_poll_multiplayer()` — `after(250)` loop; the ONLY bridge between
     network threads and the UI. Drains `mp_host.poll_events()` /
     `mp_client.poll_events()`.
   - `_handle_host_event()` — `("action", …)` →
     `_apply_multiplayer_action(...)` →
     `mp_host.resolve_action(client_id, seq, ok, detail)`;
     joins/leaves/claims/chat → toast.
   - `_handle_client_event()` — `state_sync` →
     `_apply_multiplayer_snapshot`; day/checkpoint/chat → toast;
     `disconnected` → error dialog + stops the poll loop.
   - `_apply_multiplayer_snapshot(save_bytes, label)` — decompress →
     `save_manager._restore_game_state(data)` → re-syncs the GUI
     mirrors `__init__` seeded from defaults (`current_date`, `league`,
     `user_team`; clients get their *claimed* team as `user_team`) →
     `update_all_views()`.
   - `_apply_multiplayer_action(action, params, manager)` → `(ok,
     detail)`. **Deliberate Phase-1 scoping:** `set_lines`/`set_tactics`
     return `(False, "managed locally in Phase 1")` — lineup state lives
     in GUI session state (`self.lineup`) and is *not* serialized, so
     each manager sets lines on their own screen. Roster/cap mutations
     (`sign_free_agent`, `propose_trade`, `release_player`,
     `send_to_minors`, `call_up`) return `(False, "not implemented yet
     (Phase 1b)")` — the protocol already surfaces that as a clean
     client-side rejection. See section 3.
   - `_apply_multiplayer_role_ui()` — disables the client's Continue
     button (only the host advances days).
   - `_mp_toast(text)` — small auto-dismissing notification + console
     log. `_mp_find_team(team_id)` — canonical team lookup.
4. **Never touch widgets from network threads** — the poll loop above
   is the only bridge (unchanged rule, now implemented).

### 2c. `fantasy_draft.py` — IMPLEMENTED

Crash-mid-draft is the headline recovery scenario
(`clear_all_team_rosters_completely` wipes rosters at draft start).

1. **`begin_fantasy_draft`**: `"Before Fantasy Draft"` checkpoint at the
   **very top, before the roster wipe** — recovery lands on an intact
   league, not a half-drafted one.
2. **Per-round checkpoints**: `make_pick` is wrapped **once** in
   `begin_fantasy_draft` (guarded by `draft_manager._checkpoint_wrapped`
   so re-entry is safe). The wrapper records the round before the pick
   and checkpoints `f"Fantasy Draft - Round {n}"` when the round
   advances — covering all six pick call sites (human +
   `draft_specific_player` + four AI sites) without touching them.
3. The checkpoint manager is read via
   `getattr(self.game_manager, 'checkpoint_manager', None)` — the draft
   module stays decoupled from multiplayer; solo play just skips.

### 2d. `save_load_system.py`

**No changes required.** `create_save_data()` (no file I/O, no dialogs)
is the snapshot primitive; `load_game(path)` is the recovery path;
`_restore_game_state` is reused for client snapshots. Do not add
`messagebox` calls to these paths — the host snapshots from the main
thread today, but the contract is "no UI in the snapshot path".

### 2e. Wire-format note (additive change, no version bump)

`WELCOME` gained an **additive optional** field: `teams`
(`[{"id","name"}]`, the claimable roster), and `MultiplayerHost` takes
an optional `get_teams` callable. Old hosts omit it; new clients use
`msg.get("teams", [])`. Rule going forward: **additive optional fields
don't require a `PROTOCOL_VERSION` bump**; any change to existing
fields or required semantics does.

> Note: the pre-existing `GameSaveManager.autosave()` (every 7 days,
> unbounded files in `saves/`) is intentionally left alone. The
> checkpoint ring is the bounded replacement for crash-safety; the
> old autosave remains the player's opt-in long-term backup.

## 3. What remains (game-logic surface — Phase 1b)

The infrastructure, UI wiring, and plumbing are done and tested. What
remains is game-specific logic — deliberately deferred because it needs
real games to validate against, not headless tests:

1. **`_apply_multiplayer_action(action, params, manager)`** (main.py):
   real handlers for `sign_free_agent`, `propose_trade`,
   `release_player`, `send_to_minors`, `call_up`. Each handler mutates
   the host's canonical `Team` objects and returns `(True, "…")` or
   `(False, reason)`. **Validate every param** — clients are trusted
   LAN peers, not trusted code. The current stubs return
   `(False, "…not implemented yet (Phase 1b)")` and the protocol already
   surfaces that as a clean client-side rejection, so this can land
   incrementally, one action at a time.
2. **`set_lines` / `set_tactics` — intentionally local.** Lineup state
   (`self.lineup` in main.py) lives in GUI session state and is *not*
   part of the serialized save, so there is nothing to sync. Each
   manager sets lines on their own screen in Phase 1. If lines ever
   become serialized game state, revisit.
3. **Lobby UI exists** (launcher): manager list, team-claim buttons,
   Start. Poll-based (`after(250, …)`), no threads touching tkinter.

## 4. Test report (2026-09-26)

`python3 test_multiplayer_phase1.py` — **11/11 passing**, 13/13
consecutive runs green (headless: loopback host + 2 clients,
checkpoint ring bounds, crash-flag lifecycle).

One real bug was found *in the test itself* during this work and fixed:
the `drain()` helper called `poll_events()` (which empties the whole
queue), returned on the first match, and silently discarded the rest of
the batch. The host sends `ACTION_ACK` and the `STATE_SYNC` rebroadcast
microseconds apart, so they routinely landed in the same poll window —
`drain(c, "action_ack")` ate the `state_sync` and the next drain timed
out. Fixed with per-client/per-host spill buffers: non-matching events
(including the remainder of a batch after a match) are retained and
re-checked. Lesson for future tests: **never treat `poll_events()` as
a peek — it's a drain.**

A second real bug was found in a static review of the launcher UI and
fixed before commit: `_join_connect`'s success path showed the client
lobby but never destroyed the "Connecting" window (only the failure
path did). Fixed with a `_join_succeeded` method that destroys the
wait window before opening the lobby.

## 5. What NOT to touch

- `multiplayer/*` internals — extend via the callbacks, not edits.
- The checkpoint ring size/location contract (`saves/checkpoints/`,
  5 slots): the recovery dialog and the client fallback both assume it.
- `PROTOCOL_VERSION`: bump on any wire change; never silently alter
  message shapes.
- Pickle-over-TCP stays LAN-only. If anyone proposes internet hosting
  without a VPN, that needs auth + encryption first (Phase 3 scope).

## 6. Branch / version guidance

- Develop multiplayer on a feature branch (e.g. `feature/multiplayer-phase1`).
- New files merge cleanly; conflicts will concentrate in
  `enhanced_launcher.py::_create_action_bar`, `main.py::simulate_day`,
  and `fantasy_draft.py` pick sites — all marked with
  `# --- MULTIPLAYER ---` comments.
- After merging, run `python3 test_multiplayer_phase1.py` and the
  existing `validate_season.py` harness before pushing.
