# TACTICS_REWORK_GUIDE.md

Zone-based tactics rework for Puck Dynasty (built 2026-09-28, unpushed at time
of writing — check `git log` for the commit). Replaces the old flat
offense/defense/philosophy model with the zone-module architecture from the
NHL tactical systems doc: five even-strength zone modules + PP/PK + three
club identity presets. Shot volume is now **team-by-team, driven by tactics**.

## What changed (files)

- **`tactics.py`** — rewritten core. Seven catalogs, resolution, migration,
  presets, copycat, intermission AI (see API below).
- **`simulation.py`** — GameSim: shot-chance gate multiplies the attacking
  team's `shot_vol`; xG factor multiplies the attacking team's `shot_qual`.
- **`main.py`** — AdvancedGameSim: `_determine_event_type` scales `shot_prob`
  by the shooting team's `shot_vol`; `_resolve_shot_event` scales
  `shot_chance` by the shooting team's `shot_qual`; `_systems_matchup`
  defaults extended; offseason copycat news uses `CATALOGS` generically.
- **`tactics_window.py`** — 7 module cards + Identity preset buttons
  (Chaos & Pressure / Stranglehold / Hybrid Transition) that stage all seven
  modules as pending changes through the normal coach suggest/enforce flow.
- **`pbp_visual_sim.py`** — tactics tab rebuilt for the 7 modules
  (opponent read-out included).
- **`reputation_system.py`** — `_TACTICS_CAT_LABEL` updated to the new
  category names; the "philosophy is identity" accept-penalty is now "3+
  modules changed is an identity overhaul". (Whiteboard flow itself
  untouched.)
- **`qa_tactics.py`** (98 checks), **`qa_tactics_ui.py`** (13 checks) —
  rewritten for the new architecture; both green.

## The seven modules

| Category | Systems | What it moves |
|---|---|---|
| `forecheck` | 1-2-2, 2-1-2 Swarm | pace, shot volume, physicality |
| `neutral_zone` | 1-3-1 Trap, Regroup & Wave, Counter-Press | pace, defense, transition |
| `dzone` | Hybrid Man-to-Man, Passive Box+1, Slide & Match | defense (suppress) |
| `ozone` | Micro-Transitions, Cycle & Point Volume, Five-Man Flow, Rush, Net-Front Saturation | attack, shot volume, shot quality |
| `breakout` | Controlled, Stretch, Direct | pace, attack |
| `pp` | Umbrella, 1-3-1, Overload, Spread, Net Crash, Shoot-First, Motion | pp conversion |
| `pk` | Diamond, Passive Box, Wedge+1, Aggressive Swarm, Czech Press, Split | pk kill rate, shorthanded threat |

Identity presets (`IDENTITY_PRESETS`): **Chaos & Pressure** (swarm
forecheck, counter-press, rush ozone, stretch breakout, shoot-first PP),
**Stranglehold** (1-2-2, 1-3-1 trap, box+1, cycle ozone, direct breakout),
**Hybrid Transition** (the modern default).

## API (tactics.py)

- `ensure_team_tactics(team)` / `team_tactics(team)` → dict of 7 module keys.
  Legacy saves (old offense/defense/philosophy keys) auto-migrate via
  `_migrate_legacy_tactics`.
- `resolve_team_tactics(team)` → `{attack, defense, pace, pp, pk,
  sh_threat, physical, shot_vol, shot_qual, fit, familiarity, identity}`.
  Familiarity mutes every edge toward 1.0; memoized per game.
- `matchup_modifiers(home, away)` → adds `home/away_shot_vol`,
  `home/away_shot_qual` alongside the existing goals/pace/pp keys.
- `apply_identity_preset(team, key)` / `matching_identity(team)`.
- `set_team_system(team, category, key, mid_game=False)`,
  `tick_tactics_familiarity(team)`, `system_tradeoffs(cat, key)`,
  `describe_team_tactics(team)` (leads with `Identity: …` when a preset
  matches), `player_system_fit(player, key, category="ozone")`,
  `team_system_fit(team)` (roster average vs the ozone system, 0.92–1.08),
  `coach_tactics_fit`, `install_coach_systems`, `maybe_install_coach_systems`,
  `ai_intermission_adjustment` (now switches ozone/forecheck/neutral_zone/
  dzone), `offseason_copycat` (weights: pp .30, pk .25, ozone .20,
  forecheck .15, dzone .10), `get/set_tactics_control`,
  `save/get_preferred_tactics`.

## Calibration

Seeded league is scoring-neutral by construction: attack, defense, pace,
**shot_vol, shot_qual** product-means are normalized to 1.0 across the 32
NHL seeds (via the ozone catalog). League means: attack 0.991, defense
0.991, pace 1.000, shot_vol ~1.0, shot_qual ~1.0.

### NHL shot-volume calibration (2026-09-28)

Real NHL 2016-17..2025-26 (via StatMuse): league ~29.5 SOG/team/game;
team-season means run ~24.5 (worst) to ~34 (best), std ~2. Playoffs dip
into the low 20s; single games in the low teens happen a few times a
season league-wide. The sim's raw 23.2 SOG mean was below real volume and
the raw spread (11→35) far too wide, so three constants in `tactics.py`:

- `SHOT_LIFT = 1.38` — applied in both engines' shot gates
  (`simulation.py` shot gate, `main.py` `_determine_event_type`):
  raises the league to real NHL volume.
- `SHOT_VOL_DAMPEN = 0.35` — applied in `resolve_team_tactics` as
  `vol_raw ** 0.35`: compresses the cross-team spread (0.956–1.047 after
  dampening). Don't touch the catalogs to narrow spread — tune this.
- `SHOT_QUAL_TRADEOFF = 0.35` — applied in `resolve_team_tactics` as
  `qual_raw / vol_raw ** 0.35`, plus the global `SHOT_LIFT_DILUTION`
  (`= SHOT_LIFT ** 0.35 ≈ 1.119`) in both engines' xG paths: extra shots
  are worse shots (point shots, bad angles), so scoring stays in band
  while volume rises. High-volume teams still score a touch more
  (goals ∝ vol^0.15) — matching the real NHL's modest volume/goals
  correlation.

Measured (128-game GameSim sample, seed 7, per-team GPG): **29.3 SOG**,
**3.36 GPG** (band 2.70–3.60). Conversion actually fell slightly
(11.96% → 11.49%) — the dilution works; goals rose only via volume.

Quick-sim (AdvancedGameSim) note: it has no per-tick clamp to absorb
the lift, so the full 1.38× flows into its shot gate — diluting by only
1.119 pushed it to 3.91 GPG (over band). It now dilutes by the full
`SHOT_LIFT` in `_resolve_shot_event`, landing at **3.36 GPG** —
converged with GameSim. Team volume differentiation survives via the
undiluted `shot_vol` and the qual/vol tradeoff.

Known limitation — single-game variance: the engine's tick/zone model
produces game-level SOG std ~13 (real NHL ~6). OZ ticks per team swing
53–98 for identical matchups (possession-share std ~9%) because zone
possessions come in sticky clumps, and the per-tick shot rate also
varies. Result: ~15% of team-games fall under 15 SOG vs ~0.15% in real
NHL. This is a pre-existing engine property (the zone/possession model),
not a calibration artifact — it was identical before the tactics rework.
Over a full season it washes out (std err ~1.4/game → team-season means
land in the real 24.5–34 band), but single games feel wider than real
hockey. Fixing it means reworking possession clumping in the tick loop —
separate engine surgery, flagged for Muck's sign-off, not attempted here.
The calibration deliberately keeps a small chance of 11-shot games for
ultra-defensive teams (Muck's direction); they're just more common than
real until the engine work lands.

If the measured mean misses, retune `SHOT_LIFT` (linear); if the spread
misses, retune `SHOT_VOL_DAMPEN`. Never touch the catalogs for volume
calibration.

## What NOT to touch

- caleb's systems (analytics hub, league history/records,
  reputation/dressing-room, tension/intensity, line brawl, headlines) —
  untouched by this rework.
- Goalie personality (`goalie_personality.py`, `DISABLED` kill switch) —
  separate balance lever.
- Old per-team slider attrs (`tactic_even_strength`, `tactic_power_play`,
  `tactic_penalty_kill`) are still read by legacy xG/PP branches in
  `simulation.py`/`main.py` — left alone deliberately (additive layering).
