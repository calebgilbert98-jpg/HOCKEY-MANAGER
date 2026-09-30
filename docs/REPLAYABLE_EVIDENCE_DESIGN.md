# Replayable Evidence — Design

## Problem
The visualizer is watch-once: the event buffer (`self.events`) and shot map
(`self._shotmap`) die when the window closes. You can't click a goal in the
feed to re-watch it, and you can't pull up last night's shot chart from the
schedule screen. For a management sim, post-game evidence (where did the
goals come from, who got caved in) is the credibility layer — it's what makes
the sim feel real rather than a random score generator.

## Target
1. **Click-to-replay.** Every feed item in the visualizer becomes clickable:
   clicking jumps the rink cursor to that event and renders its frozen
   positions (`ev["positions"]` already rides on every event). Works during
   live sim (pauses the stream at that moment; a "jump to live" pill resumes)
   and after the game ends. Keyboard: ←/→ steps event-by-event.
2. **Persistent shot charts.** At game end, the visualizer exports
   `{game_id, date, home, away, shots: [(x, y, team, result, period, shooter)]}`.
   Stored on the career (cap: last 50 games, ring buffer). Viewable from:
   - the schedule/results screen ("chart" affordance on final scores),
   - team pages (last-5-games aggregate shot map),
   - player profiles (individual shot map for the season).
3. **Evidence in the feed.** Goal/penalty feed lines get a ⌖ marker when a
   replay slice exists; clicking the line replays from 5 seconds before the
   event (the buffer already holds it).

## Implementation plan
- `pbp_visual_sim.py`:
  - Feed widget: bind click on feed lines → `_jump_to_event(idx)`; renders
    `events[idx]["positions"]`, sets a `review_mode` flag that pauses the
    live cursor; "LIVE" pill clears it.
  - `_export_shot_chart()`: at `game_end`, build the dict from `self._shotmap`
    (+ shooter/period from the paired events) and hand to the app/career.
- New `shot_charts.py` (or extend `sim_progress.py`? no — standalone):
  `ShotChartStore` {`games: deque(maxlen=50)`}, `add(game_dict)`,
  `for_team(name, last_n)`, `for_player(pid)`, save/load dict.
- `main.py`: own the store on the career object; wire the visualizer's export
  at game end; add chart affordances to the results/schedule UI and team
  pages. Shot-chart viewer reuses the visualizer's rink-drawing code
  (extract `_draw_shotmap(canvas, shots)` into a shared helper).
- Coordinates are already in rink units on every shot event — no sim changes.

## Engine boundary
Zero sim changes. This is purely capture + presentation of data the engine
already emits.

## QA
- Full game in visualizer: click 5 feed items → rink shows correct frozen
  positions each time; LIVE resumes.
- Game end → chart exported; reopen from results screen → identical chart.
- 50-game ring buffer: game 51 evicts game 1, memory flat.
- Save/load round-trip preserves charts.
