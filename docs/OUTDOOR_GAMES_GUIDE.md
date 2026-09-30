# Outdoor Games Guide (Winter Classic / Stadium Series)

Legacy events, spectacle wave item 4. One new module + hooks; additive only.

## What it does

Once per season, right after `league.generate_schedule()`:

- **Winter Classic** (Jan 1) + **2 Stadium Series** games (February Saturdays)
  are scheduled by *stamping* chosen regular-season home games — no 83rd
  game is ever added:
  `game["outdoor"] = {event, host, away, venue, capacity, attendance,
  weather, alumni, season, rivalry_weight}`
- **Hosts** rotate (no host repeats within 3 seasons, tracked via
  `league.outdoor_history`); selection weighs stadium size + narrative-ledger
  rivalry weight + noise. The **opponent** is the scheduled home opponent
  nearest the target date with the most ledger history against the host.
- **Venue**: a real stadium per franchise (`VENUES` in outdoor_games.py —
  Michigan Stadium 107,601 for Detroit, Fenway for Boston, etc.).
  Attendance lands at 93–100% of capacity.
- **Alumni game**: played the day before; named from the franchise's Hall
  of Famers when `league_history.hall_of_fame` has them, otherwise a bare
  scored result.
- **Weather**: procedural framing text only (`-8°C with light snow
  falling`). **It carries zero sim effect — by design.** The scoring band
  is not touched by spectacle.

## Game-day presentation

- **Inbox**: a `🏟️ {Event}: {away} @ {host} -- outdoors` billing card
  (headlines.py `outdoor_pregame` kind) with venue/weather line, rivalry
  line (ledger-weighted), and alumni-game result. Fires for all outdoor
  games (~3/season — never spammy).
- **Crowd**: `arena_atmosphere.pregame_crowd(..., outdoor=True)` pins the
  building near-max (+10 energy, +6 mood, "Outdoor game" driver,
  `big_game=True`). It flows through the existing two-sided crowd channel
  — loud building, same as a Game 7, no new conversion keys.
- **Watch Live**: `open_pbp_window(..., outdoor=info)` shows a venue/weather
  card at puck drop + a feed line, and applies the same crowd bump to the
  visualizer's GameSim.

## Permanent memory

`record_outdoor_result(app, info, home_score, away_score)` (called from
both the user-game loop and `_simulate_games_batch`):

- appends to `league.outdoor_history` (idempotent on season+event+host),
- records a `outdoor_game` event (weight 55, idempotent) on the narrative
  ledger, so future seasons' billing and host selection remember who met
  outdoors and who won.

## Save/load

- The stamp rides the schedule serializer (`save_load_system.py`:
  `_serialize_schedule` / `_restore_schedule` carry the `outdoor` dict).
- `league.outdoor_history` is saved/restored in the league_data block.
- Schedule *templates* (the solver cache) stay clean — stamping runs after
  `generate_schedule()` returns, so cached templates still get stamped.

## New ledger API

`NarrativeLedger.memory_weight(a, b) -> float` (0–100, saturating) — total
pair weight between two teams. This also repairs a wave-3 gap:
`arena_atmosphere` and `_grudge_week_market` were already calling it and
silently getting 0; bad-blood buildings now actually work.

## Files

- `outdoor_games.py` — NEW: venues, scheduling, presentation, memory.
- `narrative_ledger.py` — added `memory_weight`.
- `arena_atmosphere.py` — `pregame_crowd(..., outdoor=False)`.
- `headlines.py` — `outdoor_pregame` builder.
- `main.py` — schedule hook, `_deliver_outdoor_pregame`,
  `_pregame_atmosphere(outdoor=...)`, both day-sim loops,
  `_simulate_game_with_pbp_visual(outdoor=...)`.
- `pbp_visual_sim.py` — `open_pbp_window(..., outdoor=None)`.
- `save_load_system.py` — stamp + history persistence.
- `qa_outdoor_games.py` — 49/49.

## What NOT to touch

- Never add a 83rd game; the stamp must ride a real scheduled game.
- Weather stays presentation-only. If a future designer wants a weather
  *effect*, it needs Muck's explicit approval (scoring-balance boundary).
- `VENUES` keys must match `game_classes.py` team names exactly
  (note `Montréal Canadiens` with the accent).
