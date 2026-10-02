# D41 Scope: Real AHL League

**Investigation date:** 2026-10-02
**Status:** Scoping only — no code changes

---

## 1. What's There Now (Abstract Sim)

The AHL is simulated abstractly by design. From `ahl_system.py` (576 lines):

> "Roll one day of AHL stat lines for every farm roster in the league. Called from the daily maintenance path in main.py. **Cheap by design: a probability roll per player**, and only players who 'played' get a generated line. **No standings, no schedules, nothing persisted beyond the per-player ledger.**"

**Architecture:**
- Each NHL team has an `ahl_roster` (list of Player) — the farm roster lives on the NHL team object
- 30 AHL Team objects exist (level 2) with 1:1 NHL affiliations (`_assign_ahl_affiliations`), but they're **shells** — no rosters of their own, no games
- `simulate_ahl_day()` (main.py:11304, daily maintenance): per-player probability roll → generated stat line in `player.ahl_stats` ledger
- `ahl_stats_window.py` (293 lines): displays per-player AHL stat leaders, "cooking" prospects
- No team-vs-team games. No standings. No schedule. No Calder Cup.

**What it does well:** Player development tracking — you can see who's producing on the farm, who to recall. Cheap (one probability roll per player per day).

---

## 2. What "Real" Would Mean

A real AHL league means:

| System | Current | Real |
|--------|---------|------|
| Games | Probability rolls per player | Actual team-vs-team sims (GameSim/AdvGS) |
| Schedule | None | ~72-game AHL schedule, 30 teams |
| Standings | None | Division/conference tables |
| Stats | Per-player ledgers | Team + player, leaders |
| Playoffs | None | Calder Cup bracket |
| Watchable | No | User can watch AHL games |
| Rosters | NHL team's `ahl_roster` list | Real AHL team rosters |

**New systems needed:**
1. **AHL schedule generator** (`ahl_schedule.py` — new): 30 teams, balanced schedule
2. **AHL game sim integration**: hook AHL games into the daily sim loop alongside NHL games
3. **AHL standings**: extend `league_history.py` or new `ahl_standings.py`
4. **AHL playoffs**: Calder Cup bracket (extend playoff system)
5. **Roster model change**: AHL players move from NHL team's `ahl_roster` to actual AHL team rosters — **this is the big refactor**
6. **AI roster management**: AI GMs manage AHL lineups, signings, recalls
7. **UI**: AHL standings screen, AHL schedule screen, watchable AHL games

**Estimated files touched:** `ahl_system.py` (rewrite), `main.py` (daily loop), `game_classes.py` (roster model), `league_history.py`, new `ahl_schedule.py`, `ahl_standings.py`, `ai_team_management.py`, `ahl_stats_window.py` (expand), schedule/rules.

---

## 3. Player Pool Structure (Muck's Scope)

### Current pools

| Pool | Size | Notes |
|------|------|-------|
| FA pool (`league.free_agents`) | **~1200** | Flat list, quality 0.6-0.9 modifier, age 22-40. Muck: this number is GOOD, don't trim. |
| Draft class | 224 → **320-350** (draft-depth branch) | 224 picks/year → **~100+ undrafted/year** once expanded |
| Undrafted flow | — | Re-enter draft if still eligible; else become FAs (`undrafted_pool` → `free_agents`) |
| Euro | Batch | `euro_free_agents.py`: undrafted European FA batches → FA pool. No real Euro teams/leagues playing games. |
| AHL rosters | 32 × ~20 | Live on NHL teams' `ahl_roster` |

### The structural problem

The 1200 FA pool is a **flat list** — NHL-caliber veterans, AHL tweeners, and Euro depth are all mixed together. With a real AHL, this needs structure.

### Recommended pool structure (around 1200, no cuts)

**Three-tier FA pool** (tags, not separate lists — keeps save format stable):

| Tier | Est. Count | Profile | Who signs them |
|------|-----------|---------|----------------|
| **NHL FA** | ~200 | 75+ overall, veterans, proven | NHL teams (1-way deals) |
| **AHL FA** | ~600 | 65-75 overall, tweeners, young | AHL teams (AHL deals), NHL teams (2-way) |
| **Depth/Euro** | ~400 | <65 overall, projects, Euro imports | AHL teams (fill), Euro path |

**Implementation:** Add `fa_tier` attribute to Player (old-save safe default). AI signing logic filters by tier. UI can filter the FA screen by tier.

### Undrafted prospect flow (with real AHL)

```
Draft (320-350 prospects, 224 picks)
  ├── Drafted → NHL team → prospects pool → AHL/NHL
  └── Undrafted (~100+/year)
       ├── Still eligible → re-enter next draft (existing rule)
       └── Aged out → FA pool as AHL-tier FAs
            ├── Sign AHL deal → real AHL roster (like EHM)
            ├── Sign Euro deal → Euro path (abstract, no Euro league sim)
            └── Unsigned → remain in AHL FA tier
```

**This is the EHM model Muck wants:** not everyone gets drafted, undrafted guys sign AHL deals or go to Europe. The 100+/year undrafted flow feeds the AHL FA tier naturally.

### Euro teams

Currently: no real Euro leagues with simmed games — just Euro-sourced FA batches. **Recommendation:** keep Euro abstract (no Euro league sim). Euro is a *source* of players and a *destination* for unsigned depth, not a simmed league. Building real Euro leagues is out of scope for D41.

---

## 4. Recommendation: Partial Build, Phased

**Don't build the full real AHL now.** The roster-model refactor (moving players from NHL `ahl_roster` to real AHL team rosters) is the kind of deep change that ripples through recalls, waivers, IR/LTIR, AI management, and save format. It needs its own dedicated build, not a side task.

**Recommended phases:**

### Phase 1 (this D41 — low risk, high value)
- **Tier the FA pool** (NHL/AHL/Depth tags) — enables all downstream work
- **Undrafted → AHL FA flow** — undrafted aged-out prospects enter as AHL-tier FAs
- **AHL team shells → real rosters (read-only)**: populate AHL Team objects' rosters from NHL `ahl_roster` (mirror, don't move) — lets UI show real AHL team pages
- **AHL standings from abstract sim**: derive lightweight standings from the existing probability sim (W/L based on roster strength) — gives the *feel* of a league without the sim cost

### Phase 2 (dedicated build — needs Muck's word)
- Real AHL schedule + team-vs-team game sims
- Calder Cup playoffs
- Full roster model migration (AHL players live on AHL teams)
- Watchable AHL games
- AI AHL roster management

### Phase 3 (only if Phase 2 lands well)
- ECHL (currently in league structures but same abstract treatment)
- Euro league sim (currently abstract — likely stays abstract permanently)

**Why phased:** Phase 1 delivers 80% of the *feel* (structured pools, real AHL team pages, standings) for 20% of the risk. Phase 2 is a multi-system refactor that deserves its own QA cycle and shouldn't ride alongside other builds.

---

## 5. Load/Performance Note

- FA tier tags: negligible (one string attribute per player)
- AHL standings derivation: one pass over 30 teams per day — trivial
- Phase 2 full sim: 15 AHL games/day × ~0.10s = ~1.5s/day extra — acceptable, but doubles daily sim time. Worth measuring in Phase 2 QA.
