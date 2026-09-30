# Season Soak Bug Log — 2026-09-28 re-run (Oct 2026 → Oct 2027)

Run context: full 301-day season soak with all committed fixes live (cap fix `34a6c37`, save/load fixes `3290d3b`)
plus the OT/SV%/scoring-balance tune in the working tree (treated live per Muck's call).
Harness: `~/workspace/.pressure/soak_season.py` (Carolina, Small DB, quick-sim, prompts disabled).

Gamebreaking bugs found and patched during this run are recorded below in the playthrough-bug-log format.

---

## Attempts

| # | Result | Notes |
|---|--------|-------|
| 1 | aborted (clean) | Reached day 60 (Nov 30) with zero errors; stopped to add Muck-requested milestone screenshots + story log |
| 2 | superseded | Reached day 300 (Sep 19 2027) with zero sim errors; killed by VM restart. Post-mortem found BUG-001 (draft/lottery skipped) — see below |
| 3 | complete | Full 312-day season, zero errors/hangs. BUG-001 fix verified live (lottery + draft ran). Harness gaps in milestone capture (see attempt 4/5 notes) |
| 4 | complete | Full 312-day season, zero errors/hangs. Complete story captured: CAR wins Presidents' Trophy (135 pts) — Cup champion read failed in harness (fixed for attempt 5) |
| 5 | complete | Full 312-day season, zero errors/hangs. **Complete story: Carolina wins Presidents' Trophy (120 pts, 59-21-2) AND the Stanley Cup.** Lottery top-5 + full draft top-10 captured. Screenshots partially covered by stale popups (fixed for attempt 6) |
| 6 | running | Final clean-screenshot pass (InGamePopup-aware window tidy + longer view settle) |

## Bugs patched

### BUG-002 — Stats & Standings view shows 0-0-0 for every team (UI, not gamebreaking)
- **Found:** 2026-09-28 ~11:30 EDT, reviewing attempt-6 screenshots. The Stats & Standings window rendered every team at 0 GP / 0 PTS at both the trade deadline and season end, while `league.standings` held the real records (story text correct).
- **Root cause:** two standings channels. The bulk sim writes results only to `league.standings[name]` (`_update_standings_fast`, main.py); `Team.wins`/`Team.losses` are only touched by the single-game `update_record()` path (windows.py). `StatsStandingsView.get_league_standings()` (stats_standings_window.py) computed points from `team.wins` — always 0 after a bulk sim.
- **Fix (stats_standings_window.py, uncommitted):** `get_league_standings` now prefers the `league.standings` entry (W/L/OTL/Points) when present, falling back to the team attributes otherwise. Verified by unit test: 120 pts / 59-21-2 from the standings dict; fallback path unchanged (41-30 → 93 pts).
- **Severity:** display-only. Sim, dashboard, and all downstream readers of `league.standings` were correct throughout.

### BUG-001 (GAMEBREAKING): Entry draft + draft lottery silently skipped every season
- **Found:** 2026-09-28 ~10:40 EDT, during milestone run attempt 2 (post-season audit).
- **Symptom:** The 2027 NHL Entry Draft never ran — no "ENTRY DRAFT 2027 BEGINS!" in the log, no draft results; the "Generated a new draft class" line in the log was the *2028* class being generated for next season.
- **Root cause:** The lottery (May 8) and entry draft (June 23–25) are date-triggered in `_check_for_event_day` (main.py), but `_start_offseason()` fires immediately when the playoffs complete and jumps `current_date` straight to July 1. Those calendar dates are therefore never simulated in ANY path (interactive, bulk, or playoff-skip) — the lottery only survived in the narrow case of a day-by-day playoff sim landing on May 8. Net effect: zero prospects ever entered the league; the league would age out and die over a few seasons.
- **Fix (main.py):** New `_guarantee_offseason_tentpoles()` called from `_start_offseason()` BEFORE `league.end_of_season()` (which wipes the standings the draft order is built from) and before the next class is generated. Runs `_hold_draft_lottery()` (date-set to May 8) and `_hold_entry_draft()` (date-set to June 24) when the per-year guards (`lottery_held_years` / `draft_held_years`) show the date path missed them — a no-op otherwise. Picks are auto-conducted headlessly by new `_auto_conduct_entry_draft()`, which mirrors `DraftView.ai_make_pick` exactly (top-12 candidates, `trade_engine.team_needs` weighting ×1.08, goalie round-1 penalty ×0.80, ±6% jitter) and `execute_pick`'s `team.add_player(p, "prospects")`. Guard writes added for the lottery (previously only written by the date path).
- **Verification:** `/tmp/test_tentpoles.py` headless smoke — 434 picks conducted (62 clubs × 7 rounds, matching the board's own `get_draft_order`), +224 prospects into NHL pools, guards set, second call fully idempotent. **Design follow-up for Muck:** interactive per-pick drafting via Draft Day Central instead of auto-conducting the user's picks.
- **Status:** patched, smoke-tested green; full season re-running with the fix (attempt 3).
