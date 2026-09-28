# Playoff Bracket Tree — Handoff Guide

## What it is
The Playoff screen now renders the tournament as a **real bracket tree**
instead of a flat list: one column per round, series cards with seeds,
per-game scores and live status lines, and elbow connector lines showing
exactly which series feeds which. Before the playoffs kick off, the tree
shows **projections** from the current standings so the screen is never
empty or stale.

## Files
- `playoff_system.py` — all of it (tree, projections, detail panel, listeners)
- `save_load_system.py` — bracket serialize/restore (`_serialize_playoff_bracket` / `_restore_playoff_bracket`)
- `stats_standings_window.py` — one-line fix: `division_finals` round label now "Conf. Final"
- `qa_bracket_tree.py` — 67 headless checks (DISPLAY=:99)

## How it works
- `PlayoffBracket.build_projection()` builds a projected Round 1
  (1v8 / 2v7 / 3v6 / 4v5 per conference) from `league.standings`. It is
  display-only — never fed into the sim.
- `PlayoffView._tree_bracket()` returns the live bracket when one exists,
  else the projection. A 🔮 PROJECTION banner labels projection mode.
- The view adopts `league.playoff_bracket` on open, and the bracket object
  stamps `league.playoff_bracket` on generation — reopening mid-playoffs
  can never show a stale projection.
- Cards: seed + abbr, series wins, per-game rows (winner-first score, OT
  tag), status line ("BOS leads 3–2" / "Series tied 2–2" / "FLA wins 4–2"
  / "Not started"), gold border on decided series, champion marker.
- Connectors: `series_target(bracket, series)` matches each series to its
  next-round series by winner-first, then team identity. R1→R2→R3→SCF
  verified; SCF is terminal.
- Click a card → `SeriesDetailPopup` (via `build_series_detail_content`):
  game-by-game, splits table (W/L/GF/GA/GF-G/biggest win/OT), storylines
  (streaks, elimination games, Game 7, sweeps, 0–2 comebacks, OT counts,
  goalie steals), players to watch (top-3 playoff scorers per team),
  road ahead (next-round matchup + sibling series).
- Live updates: `simulate_playoff_game` notifies listeners after each
  game; the view coalesces bursts into one 250 ms throttled refresh
  (safe on the threaded sim-all path). `refresh_bracket()` is public.

## Save/load
The bracket persists as plain dicts (same pattern as `rivalries`):
every series, game result, score, winner, and current round survives a
mid-tournament save. Round-trip verified 15/15.

## What NOT to touch
- `generate_playoff_bracket` / `advance_to_next_round` / series sim logic:
  untouched, only read.
- The projection is read-only display; don't let it leak into sim state.

## Gotchas learned
- customtkinter rejects `tkinter.font.Font` — use the `_cfont()` helper
  (plain tuples / `ctk.CTkFont`).
- `PlayoffSeries` dataclass instances are unhashable — key canvas-card
  maps by `id()`, never the object.
- `CTkLabel.winfo_class()` reports "Frame" (text lives in a child
  tk.Label) — headless label assertions must recurse into children.
