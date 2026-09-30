# Changelog

All notable changes to Puck Dynasty are documented here. Dates are in
America/Halifax time.

## [Unreleased] - Multiplayer Phase 1 (online career)

Authoritative-host multiplayer over virtual LAN (Radmin VPN; the game
just sees a LAN). One machine hosts the canonical league; friends join,
claim teams, and stay in sync through full-state snapshots. See
`docs/MULTIPLAYER_DESIGN.md` (architecture + setup) and
`docs/MULTIPLAYER_MERGE_GUIDE.md` (exact merge surface for collaborators).

### Networking (`multiplayer/` package, new)
- `protocol.py`: 4-byte length-prefixed pickle framing, `MessageReader`
  for partial TCP reads, message constructors, `SUPPORTED_ACTIONS`;
  `PROTOCOL_VERSION = 1` (mismatched clients rejected with an
  "update your game" message). `WELCOME` carries an additive optional
  `teams` roster for the lobby.
- `net_host.py`: `MultiplayerHost` (port 27107) — accept loop, lobby,
  team claims, ACTION validation (own-team-only, supported-action-only),
  queued intents resolved on the main thread via `resolve_action`,
  full-state `STATE_SYNC` broadcasts. Daemon threads; game objects are
  never touched off the main thread.
- `net_client.py`: `MultiplayerClient` — connect/handshake, team claim,
  actions with ACK/REJECT, snapshot apply. Every `STATE_SYNC` is also
  written to a single rotating `saves/checkpoints/client_last_sync.hm`
  fallback (one file, never grows) so a client keeps its last synced
  state if the host dies.
- Pickle-over-TCP trust model: LAN/VPN only, never the open internet.

### Launcher (`enhanced_launcher.py`, `launcher.py`)
- New `HOST MULTIPLAYER` / `JOIN MULTIPLAYER` buttons in the action bar.
- Host flow: name/port dialog → normal new-game setup → host lobby
  (shows LAN/Radmin IPs, live manager list) → `START LEAGUE` syncs
  everyone with a full snapshot.
- Join flow: connect (worker thread) → lobby with team-claim buttons →
  game is built from the host's first snapshot; the client's Continue
  button is disabled (only the host advances days).
- Crash recovery: `launcher.py` writes a session flag at startup and
  clears it on clean exit (`atexit`); a leftover flag triggers a
  "Recover last session?" prompt that rebuilds the game from the latest
  checkpoint.

### Crash-safe checkpoints (`checkpoint_manager.py`, new)
- 5-slot rotating ring in `saves/checkpoints/` + `manifest.json`
  (atomic writes, monotonic sequence numbers). Bounded by design — the
  old unbounded every-7-day autosave is left alone.
- Triggers: game start, every Continue (day advance), before the
  fantasy draft (taken *before* rosters are wiped), and after each
  completed fantasy draft round (via a one-time `make_pick` wrapper
  covering all human + AI pick sites).
- Clients are notified of host checkpoints; toasts surface sync,
  day-advance, and action ACK/reject events in-game.

### Game integration (`main.py`, `fantasy_draft.py`)
- `HockeyManagerGUI(game_manager, mp_host=None, mp_client=None)`;
  `_poll_multiplayer()` 250ms main-thread bridge (the only path between
  network threads and the UI); `_apply_multiplayer_snapshot()`;
  `_apply_multiplayer_action()` dispatch.
- Phase-1 scoping: `set_lines`/`set_tactics` stay local (lineup state is
  GUI session state, not serialized — each manager sets lines on their
  own screen); roster/cap mutations are validated stubs returning a
  clean "not implemented yet (Phase 1b)" rejection, ready for
  incremental implementation.
- `test_multiplayer_phase1.py`: 12/12 headless integration tests
  (handshake, version mismatch, team claims, ACTION round-trip,
  cross-team/unsupported rejection, chat, day announce, client fallback,
  disconnect, ring bounds, crash-flag lifecycle, async snapshot).

### Performance (audit -> implementation, 2026-09-26)
- MP snapshot off the main thread: `NetHost.broadcast_state_async()`
  serializes on a worker (coalescing while busy); `simulate_day` toasts
  and returns while busy, defers client actions to `snapshot_done`.
  Fixed `NetHost.stop()` never waking `accept()` (EADDRINUSE on rebind).
- Player browser: 250 rows/page, precomputed display rows, 200 ms
  filter debounce (filter pass 1.1 s -> 0.05 s under 12k players).
- `game_results` capped at 4000 / `news_log` at 1000, with derived
  date + matchup indexes and `find_game_result()` O(1) lookup.
- Schedule template cache (`saves/schedule_cache/`): new-game
  schedule build 13 s -> 0.01 s on cache hit (validated, falls back
  to generation on mismatch).
- Weekly AI free agency: `overall_rating()` computed once per FA per
  team (was up to 4x) via optional `overall=` params; `get_free_agents`
  scan measured at 3.25 ms and kept as the correct source of truth.
- `ScheduleWindow`: schedule parsed once per refresh; per-game result
  lookup via index instead of O(games x results) nested scan.
- `get_settings()` no longer constructs a `SettingsWindow`;
  `settings_window.load_settings()` reads JSON directly.
- Deleted dead modules: `modern_dashboard.py`, `modern_nav.py`,
  `modern_roster.py`, `page_navigator.py`, `db_importer.py`
  (+ unused `ModernDashboard` import in `main.py`).

## [0.9.0] - 2026-09-26

### Simulation engine
- Realistic shot distribution: recent-shooter rotation and flattened
  shoot-tendency weighting so shot generation spreads across the lineup
  instead of funneling to one star (top-shooter share 0.358 -> 0.306 over
  100-game samples; hat-trick rate 0.112 -> 0.089).
- Rebound recipients now use a weighted lottery instead of always going
  to the highest anticipation/awareness player.
- Offensive-zone base shot chance raised 0.36 -> 0.40 to preserve
  shot/scoring volume after the distribution changes.
- Line rotations unified: a clock-phase flip now forces a stored-unit
  refresh (previously a desynced random timer), so every part of the sim
  agrees on who is on the ice.
- Possession transfers to the same-position player on the fresh line when
  lines change; a benched player can no longer carry the puck.
- Broadcast milestones (presentation only): hat-trick watch/banner and
  shutout-bid banner with lower-thirds and feed messages.

### Broadcast visualizer
- Tactical positioning engine: EHM-style formation slots (offensive-zone
  spread, breakout support lanes, neutral-zone 1-2-2, defensive-zone
  wedge-plus-one, 2-1-2 forecheck, PP umbrella, PK box, weak-side
  integrity, limited loose-puck pursuit, teammate separation).
- Authoritative on-ice sync: the visualizer's dots now follow the sim's
  real on-ice units (line rotation, PP/PK, icing, line matching) instead
  of an independent, desynchronized rotation. Measured: puck carrier
  among the dots went from 74% wrong to 0% wrong.
- Puck-carrier ring: subtle pulsing halo so the eye tracks the play,
  with a fallback that slots an undotted carrier into his position's dot.
- Faceoff ceremony (4.2s real-time: whistle, skate to dot, set, drop),
  pause-safe and blocking; slower broadcast pace (GAME_RATE 12 -> 8).
- TV score bug, win-probability meter, puck-follow camera with toggle,
  animated lower-thirds, period broadcast cards, goal celebrations with
  slow-mo replays and deferred victory laps, skate marks, hit bursts,
  goalie lunges, Three Stars, shot trails and shot map, clickable dots.

### UI
- All legacy windows modernized to the charcoal/teal theme
  (#0e0e11 / #00ceb8); emoji stripped from UI chrome.
- Faces v5 (11 hairstyles, 6 facial hair styles, age effects).
- Live sim upgrades: on-ice lines, momentum, Next Big Moment, period
  summaries, richer commentary, live goalie stats.
- QoL: Space/Ctrl+S/Esc/? shortcuts, styled confirms, tooltips,
  sortable tables, empty states, lines-editor face thumbnails.
- Settings window restyled (dark UI, custom tab bar, teal checkboxes);
  Simulation tab scrollable; scoring-level setting (Low/Medium/High).

## [0.8.x] - 2026-09-25 and earlier

- Full 1,312-game season validation (32x82, W+L+OTL==GP, GF==GA,
  no 3-in-a-row, sane goalie SV%).
- Scoring-level setting calibrated via paired 50-game batches
  (Low ~5.5, Medium ~6.0, High 7+ goals/game).
- Ratings display on 1-100 scale; player generator attribute fix.
- Lines editor with canonical chemistry and archetype display.
- Settings crash fix; top-bar menus verified; trade center reachable.
- EHM roster import framework committed (shelved; not wired to real
  ECK databases yet).
