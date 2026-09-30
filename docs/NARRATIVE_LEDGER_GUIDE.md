# Narrative Ledger — Wave 3 (Rivalries + Narrative) Guide

**For:** calebgilbert98 · **Status:** foundation live on main · **Date:** 2026-09-28

Implements the "new system suggestion" from the Wave 3 design docs: **one
normalized event record** that rivalry, media, fans, reputation, history and
inbox all read. Facts stored once; each audience interprets them.

## What exists now

**`narrative_ledger.py`** (new) — `NarrativeLedger`: append-only, indexed,
capped event store.

- Event: `{id, kind, season, day, teams[], players[], facts{}, weight 0-100,
  text, last_callback_day, ref_count}`
- Kinds: `incident`, `playoff_series`, `milestone_watch`, `milestone`,
  `ceremony`
- Indexes: by team-pair, by player, by kind. Every read is an index lookup +
  a scan of that pair's own short list — nothing ever scans the full ledger.
- `interpret(event, audience, perspective_team)` — **one event, four
  viewpoints**: room / fans / media / league. The league only speaks when
  `weight >= 70` (reputation only when the event is large enough).
- Cooldowns: `callback_candidate()` honors `CALLBACK_COOLDOWN_DAYS` (21) and
  `MEMORY_WINDOW_DAYS` (150) — history feels remembered, not repeated. First
  reference renders "First meeting since…", later ones "Another chapter in…".
- Caps: `MAX_EVENTS` 4000; overflow rolls oldest/lowest-weight into a compact
  per-pair `archive` (counts + seasons, no detail). `advance_season()` keeps
  full detail for the last 3 seasons or weight ≥ 40.
- Save/load: `to_dict()` / `from_dict()`; wired in `save_load_system.py`
  mirroring `league_history`. Old saves backfill empty — history is never
  invented (integrity rule).
- `get_ledger(app)` lazily attaches `app.narrative_ledger` (mirrors
  `league_history`); `set_active_ledger()` / `active_ledger()` is the bridge
  for code paths that can't reach the app (controversy, playoffs).

**Wired so far:**

1. **Playoff-series memory** (`playoff_system.py`): `PlayoffSeries` gains an
   additive `game_results` log; `simulate_playoff_game` records per-game
   facts (scores, OT via `period > 3`, goalie steal = 32+ saves @ .935+).
   `advance_to_next_round` derives beats — sweep, 0-2/1-3 comeback, blown
   2-0/3-1 lead, seven-gamer, OT winners, steals, upset by seed, clincher —
   and records one `playoff_series` event (idempotent via
   `_ledger_recorded`). Later tension is weighted by what actually happened.
2. **Incident bridge** (`reputation_system.record_game_incident`): every
   rivalry incident also lands in the ledger with its `INCIDENT_WEIGHTS`
   weight. The rivalry store stays the system of record; the ledger is the
   normalized read model.
3. **Incident callbacks** (`main.py` + `headlines.py`): pre-game, one dict
   lookup per game. New `grudge_callback` headline renders the four
   viewpoints. Fires for the user's games always, for other games only when
   weight ≥ 60 (genuine league-wide feuds) — the inbox never spams.
4. **Clock** (`_process_daily_maintenance`): sets ledger season/day once per
   day; season rollover prunes once per season.

## Performance contract (do not break)

- No per-tick work. Hooks only at: incident logged, series completed,
  pre-game (1 lookup), daily maintenance (clock), season rollover.
- `qa_narrative_ledger.py`: 4200 writes in 0.37s; `between` +
  `callback_candidate` ≈ 51µs/op. Keep queries sub-ms.

## What's next (Wave 3, not yet built)

- **Milestone watches**: start the narrative *before* the event (500th goal,
  1000th game); venue note (home / vs former club / inside a rivalry).
- **Grudge-week presentation**: scheduling, marketing/attendance effects,
  crowd energy, player response; overhyping a weak feud should feel hollow.
- **History/immortality**: HOF induction voting (career score, borderline
  debate, limited classes), retired numbers (franchise philosophy, no
  duplicate use), era arguments (SRS/Cups/path as a case, not an answer),
  ceremonies with bounded temporary consequences.
- All of the above should **read the ledger**, not build parallel stores.

## What not to touch

- The rivalry incident log in `reputation_system.py` (system of record).
- `trade_engine` verdict logic, analytics/scouting, tension/line-brawl —
  the usual boundaries.

## QA

`python3 qa_narrative_ledger.py` → 49/49 headless. PlayoffSeries extension
smoke-tested. Full suites for headlines/reputation/playoffs unchanged and
passing (no signature changes — everything is additive).
