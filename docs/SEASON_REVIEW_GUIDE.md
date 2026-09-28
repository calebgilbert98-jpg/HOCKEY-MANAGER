# Season Review — Guide for calebgilbert98

End-of-season inbox card + the continuity machinery underneath it.
Pushed as: board-review wiring (`8279d59`) + this feature (see git log).

## What the user gets

At season's end (before stats are wiped), one inbox email from the
League Office: `"{season} Season Review: {team}"` (category League,
important + milestone). Sections:

- **The year in one line** — record, final league rank, vs the preseason media poll
- **Story of the season** — longest win streak, playoff run, top-5 ledger moments
- **Stood out / Tough go** — top-3 by points (+career-year flags); bottom-3 regulars by production vs career pace (a player can't appear in both)
- **Rookie watch** — club rookies in the Calder race + league rookie goal leader
- **Hardware** — major award winners, club winners flagged `<-- YOURS`
- **Pipeline report** — every prospect whose rights are held: age, current → potential, outlook label (Blue-chip / On track / Project / Long shot), development text
- **How the season netted out** — four-corner score (Media / Fans / Owner / Room), each graded F..A, plus a composite SEASON GRADE

## Retention: every club keeps its own history

`deliver_season_review(app)` builds a card for **every NHL club** (not just
the user's) and archives each on that club: `team.season_reviews[year]` =
`{season, label, lines, scores, meta}` (plain dicts — pickles with the
save). Every season from here on is retained, each club under its own
respective history. Only the user's club gets the inbox email and the
`last_season` player snapshots.

Non-user clubs get minimal board facts (Cup-win flag from the archives);
their Owner corner is skipped when there's no board review on file, and
the `<-- YOURS` hardware flag never appears on another club's card.

Read them back any later season: **League History → Season Reviews tab**
(club picker + season picker, newest first; defaults to your club).

## Module: season_review.py

All functions defensive — a missing data source skips its section, never
breaks delivery.

| Function | Role |
|---|---|
| `build_review(app, team=None)` | Assembles sections → `{subject, lines, scores, meta, year, label}`; team defaults to the user's club |
| `_archive_review(team, review)` | Stores the card on `team.season_reviews[year]` |
| `deliver_season_review(app)` | Loops all 32 NHL clubs (build + archive each); user's club additionally gets last-season stashes, season_story events, and the inbox EmailMessage via `app.send_email_to_user`. **Call pre-wipe.** Returns bool. |
| `snapshot_preseason_predictions(league)` | Ranks NHL clubs by opening-night roster strength → `league.preseason_predictions` (plain dict, pickles with the save) |
| `stash_last_season_lines(players)` | `p.last_season = {gp,g,a,pts,plus_minus,w,sv_pct,gaa,shutouts}` |
| `roster_strength(team)` | Mean overall of best 20 roster players |

Media score = predicted rank vs actual rank. Fans = dynamics-feed tone
(`reputation_system.get_dynamics_feed`, tone up/down) ± playoff swing.
Owner = board mandate + confidence delta (from `app._season_review_board`).
Room = `team.team_chemistry` × 0.55 + avg morale × 0.45.

`season_story` ledger events (weight 45, one per NHL club) are recorded
at delivery — future seasons and headline callbacks can reference them.

## Hook points (all in place)

- `main.py::_offseason_board_review` → calls `deliver_season_review(self)`
  after the board review. Runs in `_start_offseason` before
  `league.end_of_season()` wipes stats.
- `game_classes.py::League.end_of_season` → calls
  `snapshot_preseason_predictions(self)` at the very end (rosters final).
- `main.py::_record_season_to_history` → standings snapshot keeps **all 32**
  clubs with final `rank` (was top-16); franchise block also calls
  `FranchiseRecords.record_streak(team, "win", longest, season_label)`.
- `game_classes.py::League.end_of_season` → `reset_season_record()` per team
  (fixes cross-season accumulation of `team.wins/losses`).
- `game_classes.py::Team.update_record` → tracks `win_streak` /
  `longest_win_streak` (new dataclass fields, defaults 0).
- `milestones.py` → `led.add(...)` corrected to `led.record(...)` (the old
  call silently no-oped; milestone entries never reached the ledger).

## Data contracts

- Preseason poll: `league.preseason_predictions = {team_name: {rank, strength, season}}`.
  Saves predating it grade Media against the board mandate instead.
- `p.last_season` dict (see above) — compare vs last year, not just career.
- Ledger kinds the story section reads: `incident, hat_trick, blowout,
  goalie_steal, ot_thriller, shutout, outdoor_game, milestone` (+ the new
  `season_story`).

## What NOT to touch

- `Team.update_record(result, overtime)` is the single canonical per-game
  hook (bulk sim goes through `main._update_standings_fast`, which now also
  calls it). Don't add a second streak tracker.
- Don't move `deliver_season_review` after `end_of_season()` — it reads
  per-season stats.
- `_grade()` bands are a starting point; tune there, not in the sections.

## QA

- `qa_season_review.py` — 32/32 (fake season: 44-30-8, 10-game streak,
  50-goal rookie, Hart/Calder winners; asserts every section, email
  metadata, 32 season_story events, preseason snapshot, graceful
  degradation on empty/thin data; every club's own card archived across
  two seasons; Season Reviews tab renders headless with club+season
  pickers).
- `qa_board_season_review.py` — 9/9 (board wiring underneath).
- `qa_narrative_ledger.py` — 49/49 (ledger regression).
- Full `League.end_of_season()` smoke: records reset, 32-club poll.
