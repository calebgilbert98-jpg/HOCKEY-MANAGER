# Puck Dynasty

A hockey management simulator inspired by Eastside Hockey Manager and
Football Manager. Take over an NHL franchise: manage the roster, set
tactics and lines, develop prospects, work the trade market, and watch
every game unfold in a broadcast-style visualizer.

**Version:** 0.9.0 (see `CHANGELOG.md`)

## Features

**Management**
- Full 32-team NHL structure with 82-game seasons, playoffs, draft,
  free agency, and the trade deadline
- Roster management with line chemistry, player archetypes, and morale
- Player development, training, and scouting systems
- Finances, staff, owner expectations, and media climate
- Contract negotiations and extensions
- Save/load system with multiple slots

**Simulation engine**
- Zone-based gameplay (offensive / neutral / defensive) with forechecking,
  breakouts, cycles, dump-and-chase, and special teams
- EHM-style tactical positioning: formation slots for even strength,
  power play (umbrella), and penalty kill (box)
- Line rotation with fatigue, icing rules, and aggressive line matching
- Realistic shot distribution across the lineup; weighted rebound scrambles
- Overtime (3v3) and shootouts; broadcast milestones (hat-trick watch,
  shutout bids)

**Broadcast visualizer**
- TV score bug, win-probability meter, and momentum tracker
- Puck-follow camera, slow-mo goal replays, and Three Stars
- Faceoff ceremonies after every stoppage (goals, offsides, icing, penalties)
- Puck-carrier ring, shot trails, shot map, skate marks, hit bursts,
  goalie reactions, and clickable player dots
- Play-by-play feed with period summaries and Next Big Moment jumps
- Adjustable speed (1x/2x/4x/Auto) and pause

## How to run

1. **Prerequisites:** Python 3.8+
2. **Launch:** run `python main.py` (or `python3 main.py` on macOS/Linux)
3. **New game:** pick your team in the setup wizard, set your lines,
   and drop the puck.

Save files live in `saves/`. Settings are stored automatically.

## Project layout

- `main.py` — application entry point and management UI
- `simulation.py` — the game simulation engine
- `pbp_visual_sim.py` — the broadcast game visualizer
- `game_classes.py` — core data model (players, teams, league)
- `player_generator.py` — procedural player/database generation
- `validate_season.py` — headless 1,312-game season validation harness

## Status

Actively developed. The EHM roster-import framework is shelved for now
(see `CHANGELOG.md`). Known limitation: no goalie-pulling/empty-net
system yet.
