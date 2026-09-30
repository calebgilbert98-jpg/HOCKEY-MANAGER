# Parity Engine — Handoff Guide

## What it is
`parity_engine.py`: competitive compression with cross-game team momentum.
Solves the measured problem from the 2026-09-28 balance run: 144-point
super-teams and 18-point cellar-dwellers (real NHL spread is ~55-125).

## Design (read this before tuning)
Deliberately asymmetric: **form momentum is weaker than the corrective
forces**, so streaks are felt but the table compresses.

- **Form** (-100..+100, x0.96 decay/game): results carry across games.
  Win +8 (OT win +6, OTL +1, loss -8; streak bonus +2/game beyond 2,
  capped +6). Applies at most **+/-4%** to chance generation.
- **Corrective forces** (stronger than form, from coaches + players):
  - *Coach adjustment*: 4+ game winless skid -> up to +6.4%, scaled by the
    coach's motivating/man-management (0.6x-1.4x). Better coaches adjust
    better (unit-tested).
  - *New-coach bounce*: +5% decaying linearly over 10 games after a hire.
    Detected via `team.head_coach` identity change; hooks into the
    dressing-room carousel with zero coupling (no import).
  - *Player pride*: leadership-75+ veterans give up to +2% on 3+ skids.
  - *Target on your back*: non-top-8 teams get +2% vs top-5 teams.
  - *Trap-game flatness*: top-8 teams go -1.5% vs bottom-8, suppressed by
    coaches with discipline 70+.
- Net: spiraling bad team vs hot team gets ~+10% vs ~+0.5%.

## "One decision, two fidelities"
Both engines call `parity_engine.pregame_multiplier(team, opponent,
playoffs=...)` (the shared decision). Application differs:
- **GameSim** (`simulation.py`): `_parity_factor()` cached per game,
  applied on the xG shot-quality gate next to `_team_tactics_xg_factor`.
- **AdvancedGameSim** (`quick_sim.py`): `_init_parity_edge()` in
  `__init__`, applied on `shot_prob` in `_determine_event_type` next to
  the tactics `shot_vol` scaling.
- Post-game: `record_result()` called once per game from each engine's
  `run()` (GameSim: after the mesh block; AdvGS: `_record_parity_result`
  at both return paths, shootout => went_ot=True).

## State
- Per-team form/streaks live on `team._parity_state` (survives across
  games; reset each season by `League.generate_schedule()`).
- Season table (W/L/OTL/points per team name) is module-level, built
  purely from `record_result()` calls -- works in the season driver,
  playoffs, and the balance harness with zero wiring. `new_season()`
  clears it. Tiers need 15+ GP before they activate (early season is
  genuinely uncertain).
- Kill switch: `parity_engine.DISABLED = True` (same pattern as
  goalie_personality). Every public function never raises; multiplier
  clamped to [0.90, 1.12].

## What NOT to touch
- The asymmetry (corrective > momentum) is the whole design. Do not
  "simplify" to a symmetric rubber band.
- `record_result()` must be called exactly once per finished game per
  engine. Do not also call it from main.py's `_record_game_result`
  (double-counting).
- The 15-game tier gate and the playoff gating on target/trap are
  load-bearing for realism.

## QA
- `qa_parity.py` 47/47: form math, streak bonuses, decay, caps, coach
  quality scaling, bounce trigger/decay/re-trigger, pride, target/trap,
  discipline suppression, playoff + young-table gating, kill switch,
  both-engine smoke.
- Regressions green: advs_parity 32, tactics 119, goalie_pull 31,
  wave3 52, momentum 33, narrative_ledger 49.
- Full 1,312-game `balance_validate.py` re-run measures the real
  compression (targets: first_place <= 135, last_place >= 42, GPG stays
  2.70-3.60). Tune constants in the header block if the spread is still
  wide -- start with COACH_ADJ_PER_GAME and TARGET_BOOST.
