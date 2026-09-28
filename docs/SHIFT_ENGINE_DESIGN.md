# Real Shift Engine — Design

## Problem
Skaters currently move event-to-event with no real shift logic. `_get_on_ice()`
derives the on-ice unit from pure clock math (`(clock // 45) % 4 + 1` for
forwards, `(clock // 60) % 3 + 1` for D). There is no shift state, no memory of
who just played, no on-the-fly changes, and line matching only reacts to score
state (±2 goals, home team, `tactic_line_matching == 'Aggressive'` only) —
never to the opponent's personnel. Line changes are invisible: no feed event,
no visualizer display.

## Target behavior
1. **Conditional 20–40s shifts.** A shift ends when one of these fires:
   - Whistle → change, except: icing team is frozen (already handled via
     `_no_line_change_team`); offensive-zone draw → coach may keep the unit
     out; defensive-zone draw with a tired unit → must change.
   - Live play → change on the fly when shift age > ~30s AND puck is in the
     neutral or defensive zone AND no scoring chance / odd-man rush is in
     progress. Forwards and D change independently (staggered, like real
     hockey — D often stay out through a forward change).
   - Sustained offensive-zone pressure extends a shift to ~45s; the unit
     stays out to keep the cycle alive.
   - Hard cap: no skater stays out > 60s without a whistle (except goalie).
2. **Line matching (last change).** At stoppages, the away team declares its
   unit first; the home team responds:
   - vs away 1st line → home 3rd line + 1st D pair (checking assignment)
   - vs away 4th line → home 1st line (exploit the mismatch)
   - vs 2nd/3rd → roll rotation
   The away team always rolls its rotation (no last change on the road).
   The existing score-state behavior (chase/protect) layers on top, not
   instead: e.g. trailing by 2 late, the home team shortens to top-six
   regardless of matchup.
3. **Fatigue linkage.** Shift length already drains `player_fatigue`
   per-minute. Add: shifts > 40s drain at 1.5×, which pushes skaters into
   `tired` impact tiers via the impact system — long shifts visibly hurt.
4. **Visible changes.**
   - Emit a `LINE_CHANGE` feed event on wholesale changes:
     "Second line over the boards for Boston." (Wholesale = 3+ skaters;
     staggered on-the-fly swaps stay quiet to avoid feed spam.)
   - Visualizer Tactics tab shows current on-ice units per team, live.
   - Coach's corner: last-10 shift lengths + any shift > 50s flagged.

## Implementation plan
- New `ShiftState` per team on `GameSim`: `f_line`, `d_pair`, `shift_start`
  (clock), per-player shift TOI. Replaces the clock-math derivation in
  `_get_on_ice()` — the unit comes from state, the clock only seeds the
  opening faceoff.
- `_should_change_lines()` becomes `_update_shifts()`: evaluates the
  whistle/live-play conditions above, handles staggered F/D changes, enforces
  the icing freeze and the 60s hard cap.
- Stoppage matching: hook the faceoff setup — away commits unit first, home
  answers per the matching table.
- `_select_starting_lines()` keeps its possession-handoff logic; it now
  applies the state-chosen unit instead of recomputing from the clock.
- Special teams: PP/PK units keep rotating on their own rhythm (45s), but
  through the same shift-state mechanism so the visualizer can display them.

## Engine boundary (do not touch)
Goal probabilities, shot math, save logic, tactics multipliers, fatigue
drain rates — none of that changes. This only changes WHO is on the ice and
WHEN they change. Expected effect on scoring: near-zero league-wide (both
teams get the same logic); the visible win is realism and coaching decisions
mattering (matching, tired legs late in long shifts).

## QA
- 20-game headless sim: assert mean shift length in [20, 40]s, zero shifts
  > 60s without a whistle, home matching table honored at > 90% of
  stoppages (unit test with scripted faceoffs).
- Visualizer smoke: Tactics tab shows live units, LINE_CHANGE events appear
  in feed, no tk errors over a full game.
- Regression: MP suite 12/12, pressure battery 8/8, `qa_tactics.py` 80/80.
