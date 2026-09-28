# Scoring Fidelity Guide

**Status:** Implemented 2026-09-28 (uncommitted). Covers Part A (15 divergence fixes) + Part B (assist rework).

## The Principle: One Decision, Two Fidelities

GameSim (full-detail, viewed games) is canonical. AdvancedGameSim (quick-sim, season sim) is the speed-optimized approximation. They apply the SAME scoring logic through shared helpers in `mesh_system.py`. Never two copies of a decision.

## Part A: The 15 Divergences (all fixed)

| # | Divergence | Fix |
|---|-----------|-----|
| 1 | PP conversion | PP conversion ×2.2 after the clamp (was pre-clamp, capped away) |
| 2 | Shooter composite | `shooter_skill_composite(shooter, shooting_base)` — ONE formula, both engines |
| 3 | Pass→shot selection | Shared `assist_weight` (passer's playmaking × scorer's finishing × relationship × chemistry) |
| 4 | Passer playmaking | `playmaking_score` — ONE formula, used everywhere |
| 5 | Goalie composite | `goalie_skill_composite` — ONE formula (0.40/0.25/0.20/0.10/0.05), both engines |
| 6 | Pace | Quick-sim pace from actual line data (was a fixed constant) |
| 7 | Fatigue | Fatigue moved to shot VOLUME (was double-counted on conversion) |
| 8 | Parity | Parity multiplier on conversion (was volume-only, muted underdog scoring) |
| 9 | Hot goalie | Shared `hot_goalie_multiplier` (both engines check the same streak state) |
| 10 | Chemistry | `chemistry_mult` — ONE function, shared |
| 11 | Rivalry | `rivalry_mult` — ONE function, shared |
| 12 | Clutch | `clutch_mult` — ONE function, shared |
| 13 | Rebound control | `rebound_control_score` — ONE function, shared |
| 14 | Breakaway | `breakaway_conversion` — ONE function, shared |
| 15 | Empty net | `empty_net_conversion` — ONE function, shared |

## Part B: The Assist Rework

### The problem
The old assist credit was a tangle: primary from a mechanical `assist_potential` flag (only set on completed passes, so carriers/shooters who created their own shot got nothing), secondary at a flat rate, rebound goals got `[]`, and the two engines disagreed.

### The fix: `_award_assists` (GameSim) + selected-passer fallback (quick-sim)

**GameSim** (`simulation.py::_award_assists`): the entire assist decision in one helper.
- Primary: the mechanical passer if one exists; otherwise a **selected setup man** (0.75 probability) chosen by shared `assist_weight` (passer's playmaking × relationship × chemistry).
- Secondary: rolled at **0.78**, attribute-weighted via the same `assist_weight`.
- Every (passer, scorer) pair is ledgered for the analytics hub.
- Rebound goals now get assists (were `[]`; rebounds are ~11% of goals).
- Penalty shots, shootouts, and empty-netters correctly get none.

**Quick-sim** (`quick_sim.py`): the same logic, approximated.
- Selected-passer fallback at **0.60** when no mechanical passer.
- Secondary at **0.78**.

### The passing-bonus guardrail
A pre-existing scoring mechanic gives the shooter a bonus from the passer's passing (`shot_skill_bonus = passer.passing * 0.3`, cutting save probability ~12% at passing=80). The reworked pass branch initially threaded this 5× more often than the old calibrated rate, inflating GameSim GPG 2.85→5.30. Fixed by recalibrating the thread rate to ~0.15–0.20 (`0.08 + 0.14 * playmaking/100`). The primary-assist *rate* is handled separately by `_award_assists` — decoupled from the scoring bonus.

### Tuning (measured)
- **Quick-sim** (100 games, NHL-only, seeds 1000-1099): A/G=1.55, GPG/team=3.42
- **Quick-sim** (100 games, slot matchups): A/G=1.58, GPG/team=2.98
- **GameSim** (50 games): A/G=1.61, GPG/team=2.76
- All in their bands (GPG 2.70-3.60, A/G 1.55-1.70).

### The baseline recalibration
`SKILL_DIFF_BASELINE` (−14.8, set 2026-09-27 on generated talent) no longer matched live rosters: in-game adjusted differential averages −26.7 (starters + danger/shot-type adjustments). Recalibrated to −26.7 on 2026-09-28 (n=834 shots, s2_deadline save). Re-measure if rosters or goalie adjustments change.

## What NOT to touch
- The `shot_skill_bonus` mechanic (pre-existing, caleb's code) — only the thread rate was recalibrated, not the bonus itself.
- `BASE_SAVE_TUNE` (scoring_balance.py) — the explicit scoring knob. Currently 0.95. Tune in small steps if GPG drifts.
- The assist probabilities (0.75/0.60/0.78) — tuned to the 1.55–1.70 A/G band. Retune only with 100+ game samples.

## Validation
- `qa_scoring_fidelity.py`: 9/9 (shared composites, attribute dominance, engine integration, ledger, smoke test).
- Regressions: `qa_preseason.py` 51/51, `qa_season_review.py` 40/40, `qa_board_season_review.py` 9/9.
- Full-season (1,312 games): confounded by injury accumulation (no roster management in the harness — stars get hurt and stay hurt). Use the 100-game samples above for scoring metrics. The harness (`validate_scoring_season.py`) is kept for structure, not for tuning.

## For calebgilbert98
All changes are additive. The shared helpers in `mesh_system.py` are the contract — if you change a formula there, both engines pick it up. The assist ledger (`record_assist_pair`) feeds your analytics hub; the deque is bounded (4000) and never raises.
