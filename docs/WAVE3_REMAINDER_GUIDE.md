# Wave 3 Remainder — Guide for calebgilbert98

Commit `7944c6a` (on top of `99d4b53`, the narrative-ledger commit). Everything
below is additive; no existing system was overridden.

## 1. Crowd as a two-sided factor (`arena_atmosphere.py`, new)

Muck's direction: the crowd must scale with all factors and can be positive
OR negative. Big games matter; home advantage matters.

- `pregame_crowd(home, away, ledger, is_playoff, series_game, elimination_game,
  milestone_home, ceremony)` → `{energy 0-100, mood -100..+100 (home
  perspective), drivers[], big_game}`. Drivers: ledger memory ("Bad blood in
  this building"), playoff ramp incl. elimination/Game 7, milestone/ceremony
  nights, home losing-skid nerves (a 4+ skid turns the building restless).
- `live_crowd_update(state, scorer_is_home, home_score, away_score, period)` —
  call on every goal. Home goals erupt (bigger when cutting a 2+ deficit);
  away goals quiet it; visitors taking a 3rd-period lead make it nervous.
- `crowd_effects(energy, mood, away_avg_age)` → `(home_mult, away_mult)` in
  [0.97, 1.03]. Loud + behind you lifts (max +2%); loud + toxic/nervous
  drags (min −2%); young visitors (avg age ≤26) get rattled in hostile barns,
  veterans (≥28.5) shrug.
- `crowd_hype_for_tension(energy, mood)` → 0-100 for the tension engine.

### Wiring (all additive, own channels)
- `impact_system.ImpactContext` gains `crowd_energy` / `crowd_mood`
  (actor-relative). All three tier classifiers multiply big-tier odds by
  `1 + 0.08·energy + 0.12·mood` (mood outweighs noise), clamped 0.85–1.20.
- `reputation_system.game_tension_breakdown(..., crowd_hype=0.0)` — new
  optional param; default 0 = old behavior exactly. Electric barns add
  points, flat ones subtract.
- `GameSim(..., crowd_hype=0.0, atmosphere=None)` — hype feeds the tension
  base; `_handle_goal` swings the live crowd; `build_context` picks it up
  automatically via `sim._crowd_energy/_crowd_mood`.
- `AdvancedGameSim(..., atmosphere=None)` — the old flat +0.5% home shot edge
  is now structural +0.25% plus the circumstantial crowd mult (same average,
  can go negative). `_crowd_on_goal` after every goal.
- `main._pregame_atmosphere(...)` builds it once per game (ledger via the
  `active_ledger()` bridge). Playoff site (`playoff_system.py`) passes
  elimination/Game 7 stakes.

## 2. Milestones (`milestones.py`, new)

500th goal / 1,000th game / 300th win (goalie). `scan_watches(league)` once
per day (integer reads off `career_*` totals); `_milestone_pregame` emits
watch news within 2 ("tonight could be the night") with venue notes — at
home, vs former club, inside a feud (ledger). `_milestone_postgame` (before
the date advances) records hits into the ledger (weight 70) and delivers a
`milestone_hit` four-viewpoint headline. Celebration tracking on
`league._milestone_celebrated` — idempotent. `milestone_home` feeds the
atmosphere's milestone-night lift.

## 3. Grudge week (`main.py` helpers)

`_grudge_week_market` — ledger `memory_weight ≥ 60` → pre-game sellout news.
`_grudge_week_grade` — post-game: marketed + blowout (4+) + no OT + no fights
→ "All that hype for this?" news. Tracked per (home, away, date); hollow
overhype for weak feuds gets called out, genuine ones never do.

## 4. Immortality (`immortality.py`, new)

- **Retirement**: the game had no retirement flow. One conservative offseason
  pass (skaters 36+, goalies 38+, rising probability) snapshots careers into
  `league.retired_players` (plain data, save-safe).
- **HOF voting**: `hof_ballot(league, history, year)` — 3-year wait, 12
  voters, 9/12 required, class cap 4, borderline (7–8) stays with debate news,
  rejection-then-induction arcs noted ("after N years on the ballot"). Uses
  the existing `league_history.induct()` — previously never called.
- **Retired numbers**: criteria (career score ≥65 + 800 games/Cup/hardware) →
  `team.retired_numbers`, rafter ceremony queued, number blocked in the
  assign-jersey dialog. `assign_jersey_number(team, player)` helper for
  generated players.
- **Era arguments**: `greatness_score` from recorded standings + playoff
  dominance; fires only on coronation (new best) or genuine debate (within
  8). A weak champion gets no argument — history stays honest.
- **Ceremonies**: `consume_ceremony(app, home_team, sim)` pre-game —
  electric building (atmosphere flag) + bounded one-game 1.02 home finishing
  bump, then cleared.

Hooked in `_start_offseason` after `_record_season_to_history`, before
`league.end_of_season()` wipes stats — via `_offseason_immortality()`.

## QA
- `qa_wave3.py`: 52/52 (crowd math, tension, impact nudge, milestones,
  retirement/HOF/numbers/ceremonies/era).
- Regression: `qa_narrative_ledger.py` 49/49, `qa_tactics.py` 119/119.
- Perf: unchanged shape — one ledger lookup + arithmetic per game pre-game,
  a few float ops per goal live. Nothing per-tick.

## Not touched
Your analytics wave (scout track records/departments/arms race/market
ecology), league history/records, reputation/dressing-room, tension/
line-brawl, headlines core, trade engine. `game_tension_breakdown`'s new
param defaults to old behavior.
