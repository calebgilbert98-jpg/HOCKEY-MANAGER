# NHL Preseason — Guide for calebgilbert98

**Status:** built and QA'd 2026-09-28, committed locally, unpushed (will ride
the next push with the waiver/camp + BUG-019/020 commits).
**QA:** `qa_preseason.py` — 51/51 green. Regressions: `qa_season_review.py`
40/40, `qa_board_season_review.py` 9/9.

## What Muck asked for

Real NHL-style preseason: a set slate of exhibitions every September, like the
real league, when each year builds out the season — not a cold jump from
training camp straight to opening night.

## Shape of the thing

- **96 games**, every NHL club plays **6** (3 home / 3 away, realistic 2–4
  band), **Sep 22 – Oct 5** (overflow Oct 6–7), **≤ 8 games per day**, no club
  twice in one day.
- Pairing mirrors real September travel: 2 intra-division rounds,
  2 intra-conference rounds, 2 league-wide rounds (circle method — every club
  gets exactly 6; rematches across rounds are possible, like real
  home-and-homes).
- Regular season is untouched: still 1312 games, 82 per club, starts after the
  preseason ends, zero date overlap.
- Entries are schedule dicts with **`'preseason': True`**. That one flag is
  the entire contract — everything downstream keys off it.

## Hook points

**Generation** (`game_classes.py`):
- `_generate_preseason_schedule` (~line 3717) — runs after the regular-season
  solver inside `generate_schedule`, so dates never collide.
- `SCHEDULE_CACHE_VERSION` bumped 1 → 2; template entries are now 6-tuples
  with the flag. `_apply_schedule_template` (~3560) handles 5- and 6-tuples,
  so old caches degrade gracefully instead of crashing.

**Sim footprint** (`main.py`) — preseason games are quick-simmed and leave
*no* regular-season footprint:
- `_process_todays_games` user branch (~9518): `is_preseason` computed per
  game. Viewer forced off (September hockey is never appointment viewing),
  game-day bundle skipped, milestone pregame filtered, team talk skipped
  (boost 1.0), narrative-ledger/lore block guarded, headlines/media engine
  guarded, `_career_after_user_game` (board/morale/presser) guarded,
  `stats_from_events = not is_preseason`.
- `_process_single_game_result` (~9767): new `preseason=False` param —
  standings writes skipped; the result is still stored for viewing.
- `_simulate_games_batch` (~10843): preseason forced onto the lightweight
  path (GameSim writes season stats itself — never used for exhibitions),
  `_generate_player_stats` suppressed, `_credit_nhl_games_played` and
  `_update_standings_fast` both take `preseason=` and no-op.
- `_simulate_game_lightweight` (~11128), `_update_standings_fast` (~11751),
  `_credit_nhl_games_played` (~10805): all accept `preseason=False`, all
  default to old behavior. Additive only.

**Kept deliberately:**
- Injuries still roll in preseason (~13%/team — camp injuries are real).
- Scores are stored in `game_results`, so past preseason games are viewable.
- The home-screen schedule panel shows your 6 exhibitions tagged
  `(Pre)` / `Pre`.

**Drive-by fix:** the media block used `went_ot` before assignment (it only
survived because the NameError was swallowed by the surrounding try/except).
`went_ot` is now computed before the media block — no behavior change for
regular games.

## Conventions / what-not-to-touch

- The `'preseason'` key on schedule dicts is the contract. If you add new
  schedule-entry shapes, carry the flag.
- Guard style is `if not is_preseason:` / `preseason=False` params — never
  invert to an allowlist; regular-season behavior must stay the default.
- `generate_schedule` prints a verification block; preseason counts appear
  there ("Preseason exhibitions: 96") — if that number ever isn't 96, the
  generator bailed (it prints a warning with the reason).
- Training camp (Sep 12–30) overlaps the preseason window (Sep 22+) — that's
  intentional, camp form and exhibitions run side by side like real life.

## Future hooks (not built)

- Preseason record shown on the standings screen (currently preseason is
  invisible there by design).
- Using camp ratings to weight preseason sim outcomes.
- A "final cuts" beat at preseason end (currently camp close handles it).
