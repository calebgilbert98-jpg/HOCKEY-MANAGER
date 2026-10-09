# s3 Re-anchor for 84-Game Slate

## s3 Frontier (82-game baseline)
- **GPG:** ~2.58 (per-game metric — should NOT change with season length)
- **Art Ross:** 137 points
- **50-goal scorers:** 8 (max 83G)
- **D-share:** 18.8% (0 defensemen in top-10)
- **A/G:** 1.534 (assists per goal)

## Pace-Adjusted Targets (84 games)

Per-game metrics are invariant to season length. Season totals scale by 84/82 = 1.0244.

| Metric | 82-game (s3) | 84-game target | Notes |
|--------|--------------|----------------|-------|
| GPG | 2.58 | **2.58** | Per-game; must hold |
| Art Ross | 137 | **~140** | 137 × 1.0244 = 140.3 |
| 50G scorers | 8 | **8-10** | 50G slightly easier in 84 GP |
| Max goals | 83 | **~85** | 83 × 1.0244 = 85.0 |
| D-share | 18.8% | **18.8%** | Percentage; must hold |
| A/G | 1.534 | **1.534** | Ratio; must hold |

## Muck's Band
- GPG band: 2.70–3.60 (s3's 2.58 is BELOW this — flag)
- Goals target: at minimum one 50-goal scorer per season (50–65 range, not 84-goal cartoon)

## Protected Levers (NEVER TOUCH)
- `finishing_rating()` — 13-member harmonic blend
- `personal_grade_ceiling()` — grade ceiling scaling
- `ceiling_scenario_mult()` — scenario multipliers
- Grade ceilings (0.18 for 95+)
- Finishing constants

## Available Levers (if adjustment needed)
- `SHOT_BASE_CHANCE` = 0.12 (base shot conversion)
- `SHOT_TALENT_SENS_MID` = 0.003 / `SHOT_TALENT_SENS_TOP` = 0.006
- `GOALIE_PARITY_MEAN` = 92.6 / `GOALIE_PARITY_K` = 0.5
- Shot volume (shots per game in sim engines)

## Results

### Smoke Tests (4×128 games, different seeds)
| Seed | GPG | Goalie SV% |
|------|-----|------------|
| 20260927 | 2.27 | 0.8843 |
| 111 | 2.344 | 0.8793 |
| 222 | 2.32 | 0.8768 |
| 333 | 2.254 | 0.8822 |
| **Average** | **2.297** | **0.8807** |

**Finding:** Consistent ~2.30 GPG across 512 games — NOT sampling noise. Systematic 11% shortfall vs s3 target (2.58).

**Root cause:** s3 was accepted on QuickSim (2.58 GPG). GameSim uses different scoring mechanics:
- QuickSim: `SHOT_BASE_CHANCE` (0.12) additive base
- GameSim: Location-based xG (e.g., Crease 0.28, High Slot 0.09) with multiplicative `shooter_finish_mult`

The two engines are NOT at parity. GameSim scores ~11% lower.

### Full Season (1,344 games)
_Pending..._
