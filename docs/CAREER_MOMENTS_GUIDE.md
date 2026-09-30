# Career Moments ("Signature Games") — Handoff Guide

**For:** calebgilbert98 · **Date:** 2026-09-28 · **Status:** built, QA green, committed unpushed

## What it is

Every player now carries a bounded career game log — `Player.career_moments` —
of signature single-game performances. Muck's use case: a kid has a huge night,
veterans come back from injury, he gets sent down circumstantially — his best
night must not be forgotten when he's the next man up or a trade chip at the
deadline. The log lives on the player and shows on his profile card, so it's
visible wherever call-up / trade evaluation happens.

## What's significant (deliberately tight — no system overload)

| Kind | Threshold | Significance |
|---|---|---|
| Hat trick | 3+ goals | 40 |
| 5-point night | 5+ points (outranks hat-trick path) | 50 |
| 4-point night | 4+ points | 35 |
| Shutout | goalie, 0 allowed | 30 |
| 40-save night | 40+ saves, any result | 35 |
| Stole the game | 35+ saves in a win (non-shutout) | 30 |

- **One moment per player per game** — the best kind wins (a 3-goal 5-point night logs once, as a 5-point night).
- **Playoff bump:** +20 significance in the postseason — playoff heroics outrank regular-season ones when pruning.
- **Cap:** 20 entries per player, pruned lowest-significance-first, then oldest. Typical players carry 0–5; the cap is a backstop, not a target.
- A 2-goal night, a 37-save loss, a 30-save win: nothing logged. The thresholds are the anti-overload mechanism.

## How it works

**Detection** — `narrative_incidents.log_player_moments(sim, home, away,
home_score, away_score, game_date, is_playoff)`:

- Normalizes per-player lines from **both engines**: AdvGS via
  `sim.stats[team][pid]` (`goals/assists/saves`); GameSim via
  `sim.game_stats[pid]` (`g/a/player`). Goalie saves aren't per-game in
  GameSim's `game_stats`, so watched-game goalie moments come from AdvGS
  only — accepted limitation, noted here rather than hidden.
- Resolves the player's side from the stat line's team key (falls back to
  roster membership), so the W/L and opponent in the detail line are correct.
- Appends a plain dict: `{date, kind, label, detail, opp, score, playoff,
  sig}`. Plain dicts = pickle/JSON-safe, no new serialization code.
- Never raises; never touches scoring or stats.

**Wiring** — `process_postgame()` gained `game_date=None` and calls
`log_player_moments` every game, both engines. `main._narrative_postgame`
takes `game_date=None` and all three sim paths pass it (user quick-sim,
Watch Live, bulk batch).

**Storage** — `Player.career_moments: list = field(default_factory=list)`
(game_classes.py). Save/load round-trips automatically: `_serialize_player`
walks `__dict__`, `_restore_player` setattrs it back — plain dicts survive.
Old saves: read via `getattr(player, 'career_moments', [])` everywhere.

**UI** — `PlayerProfileView._create_career_moments` adds a "Signature Games"
panel to the Overview tab's left (career) column, after Career Progression:
emoji + label + date per moment, `(playoffs)` tag, one-line detail
("3 G, 1 A vs Sabres (5-1 W)"), newest first, top 6 with a "+N more" count.
Empty state: "No signature games yet." The profile view is what trade screens
and roster views open, so the log is visible at every evaluation point.

## Perf

One pass over the game's stat lines per game (already in memory), a handful
of dict appends. No queries, no I/O, no per-day scans. Zero measurable impact
on sim speed or load times.

## QA

- `qa_career_moments.py` — 18/18: thresholds, goalie save tiers, negative
  cases (2-pt night, 37-save loss log nothing), one-per-game dedup, 20-cap,
  playoff-priority pruning, GameSim shape, junk-input safety,
  save/load round-trip.
- Regressions: `qa_narrative_ledger` 49/49, `qa_wave3` 52/52,
  `qa_player_cards` 11/11; headless profile render verified
  ("Signature Games" + playoff tag + detail line present).

## What NOT to touch

- The thresholds in `_MOMENT_KINDS` are Muck's anti-overload line. Loosening
  them (2-goal games, 30-save nights) needs his explicit call.
- `_MOMENT_CAP = 20` and `_PLAYOFF_BUMP = 20` live in narrative_incidents.py.
- Don't log from anywhere but `process_postgame` — one decision point,
  or the one-per-game dedup can't do its job.
