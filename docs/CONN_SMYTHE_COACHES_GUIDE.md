# Conn Smythe + Coach Records + Reputation Fine-Tune — Handoff Guide

**For:** calebgilbert98 — pass along untouched.
**Commit:** (this stack) on top of `033974c` (accolades). Unpushed per Muck's token rule.
**QA:** `qa_smythe_coaches.py` — 40/40. Integration `/tmp/integ_rollover.py` — 19/19
(real `_update_offseason_reputations` bound to a mock league, incl. idempotent re-run).
Regressions: `qa_accolades` 17/17, `qa_career_moments` 18/18, `qa_assistant_coaches` 38/38,
`qa_coach_practice` 61/61.

## What was asked

1. The Conn Smythe must exist, awarded by **real-life criteria**.
2. **Jack Adams** banking + **per-year coach record histories** on staff cards for
   head coaches **and** assistant coaches, to inform hiring/firing.
3. Fine-tune **how these build into the reputation system** and how
   staff/players perceive each other.

## 1. Playoff stat ledger (the missing foundation)

Nothing tracked playoff stats before — `GameSim.game_stats` was discarded after
each playoff game. Now:

- `Player.playoff_stats: PlayerStats` (game_classes.py) — folded every playoff game
  by `PlayoffBracket._fold_playoff_stats` (playoff_system.py): GP/g/a for skaters;
  GP/saves/shots against/goals against/shutouts for goalies; **W/L for the two
  starters** (winning team's selected goalie takes the win — the criterion voters
  actually watch). Old-save safe (`getattr` guards; players without the field are
  skipped, not crashed).
- Reset in `league.end_of_season()` alongside `stats`; round-trips through
  `save_load_system` (`_serialize_player` / `_restore_player` handle
  `playoff_stats` like `stats`).

## 2. Conn Smythe — real-life criteria

Decided at the Cup-win moment (`_create_conference_finals` → champion set →
`_decide_conn_smythe()`), while the full playoff ledger is in memory:

- **The rule:** the champion's playoff scoring leader (points, tiebreak goals)
  wins — **unless** a goalie authored an all-time run: **SV% ≥ .935 with 12+ wins**
  (the Giguere '03 / Hextall '87 / Vasilevskiy '21 bar). Spot-checked against
  recent real winners: Vasilevskiy '21 → goalie ✓, Makar '22 → skater ✓,
  Marchessault '23 → skater ✓, Hedman '20 → skater ✓, O'Reilly '19 → skater ✓.
  (The McDavid '24 losing-team exception is not modeled — the Smythe stays on
  the champion, as it does ~95% of the time.)
- Banked immediately via `accolades.bank_accolade(w, "conn_smythe", "2026-27")`
  (idempotent), stashed on the bracket as `conn_smythe_winner` /
  `conn_smythe_name`.
- Season history: injected into the rollover `awards` dict before
  `hist.record_season(...)` — the history viewer's `season['conn_smythe']` slot
  finally has a value. (The awards calculator only covers the regular season,
  so the injection is the correct seam — do not add a playoff path to
  `_calculate_season_awards`.)
- **Tune it here:** `PlayoffBracket._SMYTHE_GOALIE_SV` / `_SMYTHE_GOALIE_WINS`.

## 3. Coach season records + Jack Adams

New module **`coach_records.py`** (the whole feature's home):

- `Staff.career_record` — plain-dict entries
  `{season, team, role, w, l, otl, playoff, jack_adams}`, one per season per
  coach, recorded at rollover for **every coaching role** (head, assistant,
  associate, goalie, PP, PK). Assistants get their own role stamped — a great
  PP coach's record travels with him. Idempotent per (season, team); capped at
  40 entries.
- `playoff_result_for_team()` — "Won Stanley Cup" / "Lost Stanley Cup Final" /
  "Lost Division Finals" / "Lost Division Semifinals" / "Lost Wild Card Round" /
  "Missed playoffs", from the bracket (None-safe).
- `find_coach()` — matches the Adams winner (name+team) to a `Staff` object,
  with sensible fallbacks so the award always lands on a person.
- `career_totals()` — W/L/OTL, win%, seasons, Cups, Adams count.

**Jack Adams** (in `_update_offseason_reputations`): the existing
`adams_race` (points% vs roster-strength expectation — the "did more with less"
ballot) picks the winner; the winning coach gets the Adams banked
(`"jack_adams"`, new key in `accolades.ACCOLADE_LABELS`), `jack_adams: True` on
his season entry, and **+8 career_reputation** (`update_staff_reputation(...,
jack_adams=True)` — the strongest single-season signal after a Cup's +12).
Champion-team coaches also bank `"stanley_cup"`.

**Staff card "Record" tab** (staff_management_window.py): appears for coaching
roles only. Career totals card, Honours card (grouped accolades —
"Stanley Cup Winner: 2024-25", "Jack Adams Award Winner: 2024-25"), and a
season-by-season table (most recent first; 🏆 marks Adams years, gold marks Cup
years). Empty-state line for coaches hired before their first rollover.

## 4. Reputation fine-tune (what changed and why)

| Flow | Before | After |
|---|---|---|
| Conn Smythe → player rep | slot existed, always None | banked at Cup time; at rollover the winner's reputation is **recomputed from the trophy case** (single source of truth) so the Smythe's +12 **stacks** with regular-season awards instead of overwriting them. Ratchet-safe (never decreases). |
| Playoff success → rep | only Cup winners (+8 flat) | every playoff team's players get `playoff_rounds_won` (4/3/2/1/0 from the bracket) → up to +15 scaled by round |
| Jack Adams → staff rep | nothing | +8 career_reputation; flows into `league_perception` (0.50 weight) automatically |
| Room's view of a coach (`team_perception`, the "lost the room" input) | attributes + win% only | **track-record cushion**: +2 per banked Cup/Adams, capped +8 — a proven winner gets the benefit of the doubt in a bad year, but the hot-seat mechanic still bites |
| League's view (`league_perception`) | — | unchanged: awards already flow through `reputation` (players) and `career_reputation` (staff). No double-counting. |

Deliberately **not** changed: `award_values` numbers, the ratchet, controversy
math, `update_player_reputation`'s signature. The fine-tune is wiring, not
re-weighting — say the word if you want the weights moved.

## Perf note (Muck's constraint)

Per playoff game: one pass over the finished `game_stats` table (~40 entries)
— microseconds, no extra simulation. Per rollover: one `adams_race` pass over
32 teams + one bracket walk per team + one reputation recompute per playoff
player. No per-day cost. Nothing touches load times.

## Files

- NEW `coach_records.py`, NEW `qa_smythe_coaches.py`
- `game_classes.py` — `Player.playoff_stats`, `Staff.career_record` /
  `career_accolades`, playoff reset in `end_of_season`
- `playoff_system.py` — `_fold_playoff_stats`, `_decide_conn_smythe` (+`Any` import)
- `main.py` — rollover: Adams winner, coach records, Cup/Adams banking, playoff
  reputation recompute; history: Smythe injection into `awards`
- `reputation_system.py` — `update_staff_reputation(jack_adams=...)`,
  `team_perception` track-record cushion
- `accolades.py` — `"jack_adams"` label + order
- `save_load_system.py` — `playoff_stats` round-trip
- `staff_management_window.py` — "Record" tab for coaching roles

## What NOT to touch

`adams_race` team-strength expectations, `award_championship`, the
`update_player_reputation` ratchet, `GameSim.game_stats` key names, the
`_calculate_season_awards` regular-season scope.
