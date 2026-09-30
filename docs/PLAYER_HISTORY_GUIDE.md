# Player Season History — Guide for calebgilbert98

**What it is:** Every player now keeps a permanent per-team season history.
A mid-season trade produces two stints (e.g. `OTT 41 GP` + `BOS 38 GP`)
instead of one blended row. The player profile has a new **History** tab,
and the Overview Season Stats card shows per-team splits for movers.

**Status:** Built 2026-09-28, QA `qa_player_history.py` 22/22. Additive
only — no existing logic touched.

---

## Data model (`game_classes.py`, `Player` dataclass)

- `player.season_history`: list of plain stint dicts, appended at
  `League.end_of_season`:
  `{"season": 2027, "team": "OTT", "gp": 41, "g": 12, "a": 18, "pim": 22,
    "shots": 98, "w": 0, "l": 0, "sv": 0, "sa": 0, "ga": 0, "so": 0}`
- `player.stint_anchor`: live tracker — `{"team": "OTT", "baseline": {...}}`
  while on an NHL roster, else `None`.
- `player._stint_pending`: stints sealed mid-season (trades/waivers),
  drained at `end_of_season`.

All plain dicts/lists — pickle save/load carries them via the existing
`__dict__` walk, no serializer changes. Old saves: read everything via
`getattr(player, 'season_history', [])` / `getattr(player, 'stint_anchor',
None)` — missing attributes mean "no history yet", never a crash.

## Hook points (exact)

1. **Stint helpers** — module-level in `game_classes.py` (after
   `roll_defensive_game_stats`): `open_stint(player, team_abbr)`,
   `close_stint(player)`, `current_season_splits(player)`,
   `_snapshot_stint_stats(player)`, `_team_abbr_safe(team_name)`.
   Stint stats are **deltas** (current `player.stats` minus the anchor
   baseline), so mid-season moves split cleanly. All helpers never raise.
2. **`Team.add_player`** — when `roster_type == "roster"` (NHL only),
   calls `open_stint(player, _team_abbr_safe(self.team_name))`. AHL and
   prospect adds do nothing.
3. **`Team.remove_player`** — if the player was in `self.roster` (NHL),
   calls `close_stint(player)` after removal. AHL/prospect-only players
   have no stint to seal.
4. **`League.end_of_season`** — inside the per-player loop, immediately
   **before** `player.stats = PlayerStats()`:
   - synthesizes an anchor from a zero baseline for NHL-roster players
     that never went through `add_player` (league-creation rosters);
   - seals the open stint, stamps every pending + sealed stint with
     `season_year`, appends zero-GP-filtered stints to `season_history`;
   - drains `_stint_pending`;
   - **after** the stats wipe, opens a fresh anchor for the new season
     (baseline = zeroed stats) for players still on an NHL roster.

## UI (`modern_profile.py`)

- New **History** tab (`_page_history` → `_create_history`): seasons
  newest-first, per-team stint rows, TOT line for multi-stint seasons,
  plus the in-progress season's live splits. Skaters show GP/G/A/PTS;
  goalies show GP/W-L/SV%.
- **Overview Season Stats card** (`_create_stats`): when
  `current_season_splits()` returns more than one team, per-team split
  rows are added under the total cards (e.g. `OTT 41 GP 12 G 18 A` /
  `BOS 38 GP 15 G 20 A`). Single-team players see no change.

## What NOT to touch

- **The `end_of_season` ordering is load-bearing.** The finalize block
  must run before `player.stats = PlayerStats()` (it reads the season's
  stats) and the fresh anchor must open after it (baseline = wiped
  stats). Moving either breaks the deltas.
- **`close_stint` both queues to `_stint_pending` and returns the stint.**
  The `end_of_season` hook intentionally uses only the pending list
  after calling it — do not also append the return value (double-counts).
- **NHL-only is deliberate.** Do not open stints for `roster_type="ahl"`
  or `"prospects"` — farm time must never appear in NHL season history
  (same rule as the Calder `prior_nhl_gp` archive).
- **Team codes** come from `playoff_system.team_abbr` via the lazy
  `_team_abbr_safe` wrapper (avoids a circular import). If you rename a
  club, add the new name to `TEAM_ABBREVIATIONS` there — stints store the
  code, not the full name.
- Zero-GP stints are skipped at finalization. A player who never dresses
  leaves no history row.

## QA

`qa_player_history.py` (22 checks, headless via `DISPLAY=:99`):
trade → two stints · end_of_season finalize + wipe ordering ·
serializer + pickle round-trip · AHL moves create no stints ·
call-up/send-down open/seal correctly · History tab + splits UI build.
