# International Windows — Guide (spectacle wave)

Two lightweight, instantly-resolved tournaments that give February and May
their own texture without touching the NHL schedule.

## What it is

- **Olympics** — February 10 of Olympic years (`year % 4 == 2`: 2026, 2030…).
  Best-on-best: NHL roster players by nationality (injured players stay home).
- **World Championship** — May 12 every year. Players from **non-playoff**
  NHL teams plus prospects — this is where crossovers happen.

Both resolve instantly (one pass over NHL rosters, ~ms) and deliver a single
inbox card. No games are simmed, no dates are moved.

## Design decisions (Sports Interactive veteran read)

1. **Instant resolution, not a tournament sim.** A full IIHF sim would need
   its own schedule, injuries pausing the NHL, and UI. The spectacle value
   is the *consequences* (bonds, injuries, reputation, crossovers), not
   watching fake Latvia games. Resolution: up to 8 nations, single-elim
   bracket, team strength = mean overall + noise, logistic win probability
   (`_win_prob`, slope 0.25 — a 2-point overall gap ≈ 62%, an 8-point gap ≈
   88%/game so upsets happen but stacked Canada usually wins).
2. **Roster selection is meritocratic.** 18 skaters + 2 goalies per nation,
   sorted by overall. No politics, no coach's-pick narratives — keeps it
   explainable in one line.
3. **Bonds are the NHL carry-over.** Teammates who go together gain
   `intl_bonds` (+2/tournament, cap 6), read by `line_chemistry_report` as a
   small positive driver (max +3). This is the "room gets tighter" effect.
4. **Injury risk is real but bounded.** Olympics ~6%, Worlds ~3%, scaled by
   `injury_proneness` (capped 2x), minor injuries only (1–8 games Olympics,
   1–3 Worlds). Uses the standard injury fields so the existing injury UI
   picks it up.
5. **Reputation is ratchet-safe.** Gold +8 / silver +5 / bronze +3 /
   tournament MVP +5, applied via `ensure_reputation_fields` + addition —
   never subtracted, respecting the reputation system's "veterans never
   regress" rule.
6. **Crossovers come from the Worlds.** Best U23 with reputation < 40 by
   rolled tournament production gets a "remember the name" news line +
   reputation +5. Prospects are eligible at the Worlds only.

## Files

- **`international.py`** (new, ~430 lines) — everything. Public API:
  `hold_olympics(app, year, rng=None)`, `hold_worlds(app, year, rng=None)`,
  `is_olympic_year(year)`, `intl_bond(p1, p2)`, `intl_bond_event(p1, p2)`,
  `result_card_text(res)`.
- **`player_archetypes.py`** — `line_chemistry_report` gains an additive
  bond driver (`international bond (Olympic hockey 2026)`). Import is lazy
  (inside the pair loop, guarded) to avoid cycles.
- **`headlines.py`** — `international_results` builder (single inbox card).
- **`main.py`** — day-flow hooks (Feb 10 / May 12, once per year via
  `league.intl_held`) + `_deliver_intl_card`. All wrapped; failures are
  non-fatal.
- **`game_classes.py`** — `League.intl_held` (dict), `League.intl_history`
  (list of result summaries).
- **`save_load_system.py`** — both fields persisted/restored.

## Hook points

- Day flow: after the draft-lottery block, `# International windows`.
- `_deliver_intl_card(res)` sits next to `_hold_draft_lottery`.
- Ledger: `intl_tournament` event, weight 35, idempotent per (event, year).

## What NOT to touch

- The win-probability slope (0.25) is calibrated: 60/60 for a 20-point gap
  (correct — that's all-stars vs amateurs), ~2/3 for an 8-point gap. Don't
  tune without re-running the plausibility test.
- `_pick_nations` requires 14+ skaters AND a goalie per nation; lowering
  this fields joke rosters.
- `intl_bonds` keys are `full_name()` strings — keep `_pname` as the single
  key function.

## QA

`qa_international.py` — 44/44 (fake players/teams, ~1s):
olympic-year math, nationality normalization (13 mappings), full Olympics
run (distinct medals, held/history recorded, no double-hold), bonded-pair
discovery + chemistry driver text + positive value, seeded 90%-injury run
with field checks, medal reputation bumps, Worlds playoff exclusion /
prospect inclusion, card text, forced U23 crossover, 60-seed plausibility
(stacked Canada wins most but not all), single-nation graceful None.

Regressions green: outdoor 49/49, lottery 28/28, wave3 52/52, ledger 49/49,
tactics 119/119.
