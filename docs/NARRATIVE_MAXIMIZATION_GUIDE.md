# Narrative/Rivalry Maximization — Guide

## What this is
A top-to-bottom audit of the narrative/rivalry stack found the single biggest
story-loss in the game: **the quick-sim engine was narratively silent**. ~99%
of games (every CPU game, every user quick-sim) generated zero brawls, zero
fights, zero controversial hits, zero hat tricks, zero shutouts, zero
statement games in any persistent store. The ledger, the rivalry weights,
grudge-week callbacks, tension, and the premeditated line-brawl script were
all starving. Fixed with a shared post-game module wired into all three
sim paths.

## New module: narrative_incidents.py
Shared post-game decision module — "one decision, two fidelities":
- `process_postgame(sim, home, away, home_score, away_score, went_ot,
  shootout, rivalries, ledger, is_playoff, series_game, roll_incidents)` —
  one call per finished game. Never raises, never touches scoring/stats.
- **Incident rolls** (`roll_incidents=True`, AdvGS only — GameSim models
  these live): fights (Poisson count around `fight_probability(tension)`,
  returned for the overhype grader, NOT stored), line brawls (only via the
  existing `brawl_probability()` script — heat + blowout + late), and
  controversial hits (<1%, tension-scaled). All writes go through the
  existing `record_game_incident()` → `league.rivalries` + ledger bridge.
- **Game stories** (BOTH engines — GameSim's `story_worthy()` was
  visualizer-only and never reached the ledger): hat tricks (15), shutouts
  (12), goalie steals 35+ saves in a win (15), statement blowouts 5+
  (10, +5 in rivalry games), OT/shootout thrillers (8, +5 in rivalry games).
  Direct `ledger.record()` writes.

### Measured rates (5,000-game samples, fresh rivalry each game)
- Heated blowout (95-intensity rivalry, 6-1): 0.60 fights/game, 0.62%
  line brawls, 0.58% controversial hits.
- Calm 3-2, no rivalry: 0.17 fights/game, 0 brawls in 5,000, 0.28% hits.
- Fights alone are never stored (too common); only true brawls earn a
  rivalry record. The ledger remembers the season's real stories, not
  every Tuesday.

## Wiring (main.py)
- `_narrative_postgame(...)` helper: runs the module, stamps the fight
  count onto the sim (`_fights_total`) so `_grudge_week_grade` sees real
  numbers, delivers `game_story` headlines for user-involved games only.
- User-game AdvGS path: `roll_incidents=True`, headlines on.
- Watch Live GameSim path: `roll_incidents=False` (live incidents kept),
  stories recorded, headlines on.
- Bulk batch path: `roll_incidents=True` unless the sim is a GameSim
  (class-name check); headlines only if the user's team played. The old
  `_gfights = 0` re-read block was removed (redundant — the hook stamps
  the sim directly).

## Headlines (headlines.py)
- New `"game_story"` kind → `_game_story_headline`: 🎩🧱🥅💥⚡ subjects,
  "Game Story" category, priority 2. Delivered only for user-involved
  games (existing no-spam rule). `DAILY_HEADLINE_CAP = 4` still applies.

## Full writer→reader map (post-change)
| Writer | Store | Readers |
|---|---|---|
| Brawls/hits (GameSim live + AdvGS post-game roll) | league.rivalries + ledger bridge | game_tension, fresh_violent_incident, grudge-week callbacks, _grudge_week_market/grade |
| Game stories (both engines) | ledger | grudge-week callbacks, pre-game billing |
| Playoff series memory | ledger | callbacks, history |
| Lottery / outdoor / international | ledger | inbox cards |
| Milestones | ledger + headlines | arena atmosphere, inbox |
| Tension engine | live only (no persistence — by design) | fight/brawl probability, INTENSITY meter |

## Known non-issues (verified, left alone)
- `record_game_incident` nests incidents inside the team_team record and
  bridges to the **module-global** active ledger (not a passed-in one) —
  by design; the save/load fix unified app/manager/global to one object.
- Incident decay (`_incident_games_ago`) runs on real-world dates, not
  game dates — caleb's design, out of scope.
- Tension itself is intentionally not persisted (live meter).

## QA
- New coverage: module unit probes (detection, rates, bridge) — see
  commit message for numbers.
- Regressions: qa_narrative_ledger.py 49/49, qa_wave3.py 52/52.
- E2E: real AdvancedGameSim game → steal detected → ledger + no crash.

## What NOT to touch
- `fight_probability` / `brawl_probability` / `game_tension` /
  `record_game_incident` / decay logic — caleb's systems, used as-is.
- Scoring, stats, sim engines — the module is strictly additive.
