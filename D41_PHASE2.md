# D41 Phase 2: Real AHL League — Audit, Design & Build

## 1. Audit: How Built is the AHL Now?

**Current state: stat ledger only, deliberately not a league sim.**

| Component | Status | Location |
|-----------|--------|----------|
| Per-player stat rolls | ✅ Built | `ahl_system.py::simulate_ahl_day()` — probability roll per player on each NHL team's `ahl_roster` (0.39/day ≈ 72 games/season) |
| AHL stat ledger | ✅ Built | `player.ahl_stats` (PlayerStats, never mixed with NHL numbers) |
| AHL team shells | ✅ Exist | 30 `Team` objects ("American Hockey League", level 2), linked via `affiliate_team`/`parent_team` |
| NHL↔AHL affiliation | ✅ Built | `database_generator.py::_assign_ahl_affiliations` — 1:1 for first 30 NHL teams; NHL teams 31-32 have NO affiliate |
| Schedule | ❌ None | No games scheduled |
| Standings | ❌ None | No W/L records |
| Team-vs-team sims | ❌ None | No games played |
| Calder Cup playoffs | ❌ None | No postseason |
| AHL team rosters | ❌ None | Players live on NHL `team.ahl_roster`, not on AHL Team objects |

**Key insight:** The 30 AHL Team objects are shells — they have names and affiliations but no rosters, no schedules, no standings.

**NHL roster management touchpoints (MUST NOT BREAK):**
- `team.ahl_roster` — source of truth for farm players
- Callups/senddowns move players between `team.roster` ↔ `team.ahl_roster`
- Waivers, cap, development all read from these lists
- `simulate_ahl_day` is called from `main.py:11304` in daily maintenance

## 2. Design

### 2.1 Roster Aliasing (NO Migration)

**Decision: Do NOT migrate players to AHL team rosters.**

The D41 scope doc flagged roster migration as the "deep, risky refactor." We avoid it entirely:

- AHL Team's game roster = `parent_team.ahl_roster` (read dynamically, not copied)
- Callups/senddowns automatically update the AHL team's lineup (same list object)
- Zero sync issues, zero conflicts with NHL roster management
- The 2 NHL teams without affiliates: their `ahl_roster` players don't play AHL games (no team to play for) — they keep getting stat rolls via the existing ledger, just no standings impact

### 2.2 Schedule (Light)

- **48 games per team** (not 72 — Muck said "keep it light"; 48 gives meaningful standings at 2/3 the cost)
- 30 teams × 48 games ÷ 2 = **720 games/season**
- Generated at season start, spread Oct–Apr
- Stored as lightweight list of `(date_str, home_ahl_idx, away_ahl_idx)` on league
- ~720 tuples — negligible save size

### 2.3 Game Sim (Ultra-Fast, Background Only)

- **Quick-sim only.** No PBP, no visualizer, no per-game narratives.
- Team strength = average overall of dressed players from `parent_team.ahl_roster`
- Score via simple Poisson-ish generation on strength differential
- Updates standings only: W/L/OTL, PTS, GF, GA
- **Estimated cost:** 720 games × ~0.001s = <1s per AHL season. Invisible.

### 2.4 Standings & Calder Cup

- Standings dict on league: `{ahl_team_id: {w, l, otl, pts, gf, ga}}`
- **Calder Cup:** Top 16 by points → 4 rounds → best-of-5 series (short, fast)
- Champion recorded in league history (feeds the story system lightly)
- No per-series narratives — just the champion headline

### 2.5 Existing Stat Ledger (Untouched)

- `simulate_ahl_day`'s per-player stat rolls continue as-is
- Player development reads `ahl_stats` — no change
- The new game layer is additive: standings/narrative only
- Minor note: individual stats and team scores won't perfectly align (a player scores 2 in a 1-0 "loss"). At background fidelity, this is invisible and acceptable.

### 2.6 Save/Load & Old Saves

- Schedule, standings, playoff bracket persist on league (tiny)
- Old saves: backfill schedule + empty standings on load (never raises)

### 2.7 ECHL/Euro (Phase 3) — Confirmed Abstract & Unplayable

- No ECHL league objects exist; Euro is a destination tag only
- Verified: no code changes needed. They stay as-is.

## 3. No-Conflict Guarantees

| NHL System | How We Avoid Conflict |
|------------|----------------------|
| Callups/senddowns | We read `ahl_roster` dynamically; never copy or cache |
| Waivers | Untouched — we don't touch waiver logic |
| Cap | Untouched — AHL games don't affect cap |
| Development | Reads `ahl_stats` as before; we don't change the ledger |
| Save format | Additive fields only, getattr defaults for old saves |

## 4. Build Checklist

- [x] `ahl_league.py` (new): schedule gen, game sim, standings, Calder Cup
- [x] Hook into `simulate_ahl_day` (or daily maintenance alongside it)
- [x] AHL Team roster property → `parent_team.ahl_roster`
- [x] Save/load for schedule/standings/bracket
- [x] Old-save backfill
- [x] `qa_ahl_league.py`: schedule gen, game sim speed, standings correctness, no NHL conflicts, old-save backfill

## 5. Build Notes (2026-10-02)

**Phase 1 coexistence:** Phase 1's abstract `simulate_ahl_standings_day`
is kept as a *fallback*, not removed. The daily hook prefers the Phase 2
schedule when one is live for the current season; the abstract path only
fires if schedule generation fails (<2 AHL clubs, garbage league). Phase 2
standings live on the league (`ahl_standings` dict keyed by AHL-team index);
Phase 1's `team.ahl_record` on NHL clubs is untouched, so the two paths
can never cross-contaminate.

**Rollover:** `League.end_of_season` calls `ahl_league.ahl_season_rollover`
(guarded): backstop Calder Cup for the season just ended (if the daily
trigger never fired and real games were played), then a fresh 48-game
schedule + zeroed standings for the new `season_year`. The Calder Cup also
auto-fires from the daily hook when the last scheduled game completes, and
`maybe_run_calder_cup` runs as a daily backstop so the Cup can't be
swallowed by the NHL-playoffs gate. It never crowns from an unplayed
schedule (e.g. a save first opened mid-offseason).

**QA results:** `qa_ahl_league.py` 56/56 green. Full 720-game AHL season
sims in ~6ms (~8µs/game — two orders of magnitude under the 0.001s/game
target). Schedule is deterministic per `season_year` (locally seeded, so
the global RNG stream is untouched). Save/load verified via pickle
round-trip of every new league field. `qa_d41_phase1.py` still 26/26.
