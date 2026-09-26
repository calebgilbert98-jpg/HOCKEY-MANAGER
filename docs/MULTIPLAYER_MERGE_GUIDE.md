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

`python3 test_multiplayer_phase1.py` — **12/12 passing** (was 11/11 at
Phase-1 ship; test 12 covers the async snapshot added in §5a),
3 consecutive runs green (headless: loopback host + 2 clients,
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

## 5. Performance work (2026-09-26 — audit → implementation)

After Phase 1 shipped, a three-agent audit produced 10 ranked perf items.
All were worked through; what follows is what changed, what was measured
and deliberately *not* changed, and why. Nothing here alters game logic —
only how fast the same answers are computed.

### 5a. Multiplayer snapshot off the main thread (item 1, HIGH)

`NetHost.broadcast_state()` pickled + gzipped the full league state on
the tkinter main thread (~1–2 s freeze per Continue click in MP games).
Now:

- `multiplayer/net_host.py`: new `broadcast_state_async(label, pre_broadcast=None)`.
  Serialization runs on a worker thread; `_broadcast`/`_send` were already
  thread-safe (per-peer locks), so the network path is unchanged.
  Concurrent requests while busy coalesce — the latest label wins and is
  chained after the in-flight one. Completion/failure surfaces on the
  existing poll queue as `("snapshot_done", {})` / `("error", ...)`.
  `start_game()` and `resolve_action()` use the async path; the sync
  `broadcast_state()` is kept for tests/one-shot callers.
- `main.py::simulate_day`: early-returns with a "Syncing with clients"
  toast while `mp_host.snapshot_busy`; the end-of-day block does the
  checkpoint write + snapshot in **one** worker via `pre_broadcast`;
  client actions arriving mid-snapshot are deferred in
  `_mp_deferred_actions` and replayed on `snapshot_done`.
- Hard rule going forward: **no thread but the main thread touches
  tkinter, and nobody mutates game objects while `snapshot_busy`.**

A real bug was found while testing: `NetHost.stop()` never woke the
`accept()` thread, so rebinding the same port failed with EADDRINUSE for
~1.5 s. Fixed with `shutdown(SHUT_RDWR)` before `close()` (comment in code).

### 5b. Player browser paging (item 2, HIGH)

`player_browser.py` rendered all ~12k players into the Treeview at once
(~1 s open, **~1.1 s per keystroke** while filtering). Now: display rows
are precomputed once in `__init__`, filters scan the precomputed rows
with a 200 ms debounce, and the Treeview renders **250 rows/page** with
◀ Prev / Next ▶ buttons (selection index is global). Measured under xvfb
with 12k fake players: open+render 1.0 s → 0.5 s, filter pass 1.1 s →
**0.05 s (~20×)**, page turn ~0 ms.

### 5c. `game_results` / `news_log` caps + result index (item 3, HIGH)

`main.py`: `_record_game_result()` appends and incrementally maintains two
derived indexes — `_results_by_date` and `_results_by_matchup` (keyed by
normalized date + `id()` of the team objects), rebuilt lazily if
`load_game` swaps the list. `_trim_history_logs()` caps results at 4000
(trim 500) and news at 1000 (trim 200), called at end of `simulate_day`.
The daily-results window's full list scan and the past-games panel's
matchup scan are now O(1) lookups. New helper `find_game_result(date,
home, away)` exposes the matchup lookup (used by the schedule window,
§7e). Semantics were verified identical to the old nested scan
(hit/miss/swapped-teams/datetime-normalization) by an AST-extracted
headless test.

### 5d. Schedule template cache (item 4, HIGH)

`game_classes.py::League.generate_schedule` re-rolled the 1317-entry
schedule from scratch on every new game (~13 s). Now: a versioned
(`SCHEDULE_CACHE_VERSION = 1`) template cache in `saves/schedule_cache/`,
keyed by sha1 of version + season year + rotation seed + sorted team
names/leagues. On a hit, entries are mapped onto the new league's live
Team objects and validated (82 games/NHL team); any mismatch falls back
to generation. Cached only when `rotation_seed is None`. Verified: second
league build loaded from cache in **0.01 s**, byte-identical games.

### 5e. Free-agent lookups + AI rating recompute (item 5, MED)

Measured before deciding. `database_manager.get_free_agents()` scans
~12k players in **3.25 ms** — it is the *correct* source of truth (the
maintained `database_manager.free_agents` list goes stale on signings,
and `PlayerIndex` in `database_indexing.py` is never refreshed after
`initialize()`), so wiring either index would have been a regression for
no meaningful gain. Left as-is.

The real cost was in `ai_team_management._evaluate_free_agency` (runs per
team per week): `overall_rating()` — ~30 lines of arithmetic — was
recomputed up to **4× per FA** (sort key, priority ×2, offer details).
Now computed once per FA and threaded through new optional
`overall=` params on `_estimate_player_salary()` and
`_calculate_fa_priority()` (backward compatible; priority math verified
bit-identical by a headless regression test).

The 14 `full_name ==` name-scans across 7 files were audited: all are in
UI click handlers (context menus, compare dialogs, captain selection),
none in sim/AI loops — a shared index would add staleness risk for
microseconds. Deliberately not changed.

Also fixed while here: `ScheduleWindow.update_views` (windows.py) scanned
the full 1317-entry schedule **twice** per refresh (months + rows) and,
for every past game, did a **linear scan of the whole `game_results`
list** — O(games × results), worst ~5M comparisons per window open, and
this runs on every Continue click while the window is open. Now: schedule
entries are parsed once per refresh via `_parsed_schedule()` (cache
invalidated when the schedule list is replaced), and result lookup goes
through `find_game_result()` — O(1) per game. (The audit's "schedule
panel" premise turned out to be dormant code — the two panel updaters in
main.py no-op because their Treeviews are never created — but the live
`ScheduleWindow` had the real cost.)

### 5f. `get_settings` without constructing a window (item 7, MED)

`main.get_settings()` built a full `SettingsWindow` (flashing GUI, widget
construction) just to read its `.settings` dict. `settings_window.py` now
exposes module-level `default_settings()`, `_merge_settings()`, and
`load_settings(path=None)`; the window's `_load_settings` delegates to
it, and `main.get_settings()` reads the JSON directly — verified
headless, merge semantics unchanged.

### 5g. Dead code removed (item 8, LOW)

`git rm`: `modern_dashboard.py` (only reference was an unused import at
`main.py:37`, also removed), `modern_nav.py`, `modern_roster.py`,
`page_navigator.py`, `db_importer.py`. `simple_launcher.py` was checked
and is **live** (`launcher.py` imports `PuckDynastyLauncher` from it) —
kept. Full-repo `compileall` clean; no dangling references.

### 5h. Test report (perf work)

- `python3 test_multiplayer_phase1.py` — **12/12 passing**, 3 consecutive
  runs (new test 12 covers the async snapshot: non-blocking, busy flag,
  coalescing, ordered delivery, pre-broadcast runs once).
- Headless logic tests: result-index semantics (5 checks), `find_game_result`
  (5 checks), `load_settings` merge, AI FA priority math — all green.
- Full-repo `compileall` clean after the deletions.

## 6. What NOT to touch

- `multiplayer/*` internals — extend via the callbacks, not edits.
- The checkpoint ring size/location contract (`saves/checkpoints/`,
  5 slots): the recovery dialog and the client fallback both assume it.
- `PROTOCOL_VERSION`: bump on any wire change; never silently alter
  message shapes.
- Pickle-over-TCP stays LAN-only. If anyone proposes internet hosting
  without a VPN, that needs auth + encryption first (Phase 3 scope).

## 7. Branch / version guidance

- Develop multiplayer on a feature branch (e.g. `feature/multiplayer-phase1`).
- New files merge cleanly; conflicts will concentrate in
  `enhanced_launcher.py::_create_action_bar`, `main.py::simulate_day`,
  and `fantasy_draft.py` pick sites — all marked with
  `# --- MULTIPLAYER ---` comments.
- After merging, run `python3 test_multiplayer_phase1.py` and the
  existing `validate_season.py` harness before pushing.
