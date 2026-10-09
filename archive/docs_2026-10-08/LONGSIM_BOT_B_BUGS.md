# LONG-SIM BOT B — Bug Report (Report-Only Mode)

**Branch:** native-ui | **Date:** 2026-10-07
**Mission:** 2-year (730-day) continuous sim, season-transition focus. Report issues, do not fix.
**Complements:** `LONGSIM_BOT_A_BUGS.md` (Bot A: daily sim focus)

---

## FIXES ALREADY APPLIED (before report-only directive, need serial review)

### B-F1: `database_manager.py` — generate goalies when team has zero anywhere
- **File:** `database_manager.py`, `populate_nhl_teams()` post-pass
- **Problem:** The existing post-pass recalled AHL goalies to reach 2 NHL
  goalies, but `break` gave up when the AHL also had none (random generation
  produces this). Teams started with zero goalies → day-one `dress_minimum`
  blocker.
- **Fix applied:** When no AHL goalies exist, generate new ones via
  `PlayerGenerator.create_player(position=PlayerPosition.GOALIE)`.
- **Status:** In tree (may overlap Bot A F-4 — coordinate).

### B-F2: `trade_engine.py::execute_trade` — dress-minimum guard on trades
- **File:** `trade_engine.py`, `execute_trade()` (~line 3021)
- **Problem:** AI market traded BOTH of Anaheim's goalies to Florida on day 1
  for a defenseman, leaving Anaheim with zero goalies. `would_break_dress_minimum`
  existed in `roster_limits.py` but was never called on the trade path.
- **Fix applied:** Preflight check in `execute_trade` (central chokepoint):
  blocks any trade leaving either club unable to dress 18+2, using
  `roster_limits.would_break_dress_minimum()`. Incoming assets count toward
  the post-deal lineup (1-for-1 swaps stay legal).
- **Status:** In tree. Needs review.

---

## OPEN ISSUES (found, NOT fixed — report only)

### B-O1: AI trades away both goalies DESPITE the dress-minimum guard (day 65)
- **File:** `trade_engine.py::execute_trade` (~line 3021)
- **Problem:** Philadelphia Flyers lost BOTH NHL goalies on day 65 with zero
  coming back, even though B-F2's guard is committed and active. The guard
  did not prevent it.
- **Possible holes:**
  - Trade may bypass `execute_trade` (audit all AI trade entry points)
  - `would_break_dress_minimum` uses `is_available()` (requires active
    contract); expired/invalid contracts may break the count logic
  - Assets from `ahl_roster`/`prospects` allowed by ownership check, but
    guard only counts NHL `roster`
  - Two same-day trades each leaving 1 goalie (verify per-trade enforcement)
- **Evidence:** `GOALIE-MOVE day 65 Philadelphia Flyers: LOST ['Eero Lehtonen',
  'Luke King'], now has []`
- **Suggested fix:** Audit trade entry points; add post-trade assertion with
  rollback if either team drops below 1 NHL goalie.

### B-O2: `dress_minimum` auto-recall loops without resolving (day 77)
- **File:** `roster_limits.py`, `_auto_recall` (~line 362)
- **Problem:** User team hits `dress_minimum` blocker; `auto_action`
  (`_auto_recall`) runs but `get_continue_state()` still reports the blocker
  next check — infinite loop in headless sim.
- **Suspected causes:**
  - Recalled players fail `is_available()` despite `recall_candidates()`
    filtering for it
  - `_ft = getattr(_t, 'farm_team', None)` removal targets different list
    than `team.ahl_roster`
  - `can_dress_lineup()` re-check races the recall
- **Suggested fix:** After `_auto_recall`, verify `can_dress_lineup(team)`;
  if still False, fall back to `ensure_dressed_lineup_auto()` instead of
  re-presenting. Ensure removal from `ahl_roster`.
- **Related:** Bot A O-2 (dress_minimum ↔ roster_limit_23 ping-pong).

### B-O3: `_show_season_summary` instantiates Tkinter `InGamePopup` (day 228)
- **File:** `game_manager.py`, `_show_season_summary` (~line 9771-9820)
- **Problem:** `end_of_season()` → `_show_season_summary()` does
  `summary_window = InGamePopup(self)` — Tkinter Toplevel, not imported
  headless → `NameError`, crashes every season transition.
- **Suggested fix:** Replace with `self._ui_notify('season_summary', ...)`
  (cf. `open_playoffs_window` pattern at ~line 9822). Compute data, notify;
  never create UI directly.

### B-O4: Season soft-locks if `playoffs_mode` dialog unanswered (date stall)
- **File:** `game_manager.py`, `end_of_season` (~line 5750-5810)
- **Problem:** Post-season `playoffs_mode` dialog (Interactive vs Quick Sim).
  If unanswered, `_season_end_handled_year` guard blocks re-entry,
  `_playoffs_complete()` stays False, `simulate_day()` early-returns daily
  without advancing — 280 "days" at 2027-04-20, false CLEAN.
- **Suggested fix:** Default to quick-sim after N unanswered days; extend
  the `_bulk_simming` headless path (`_simulate_playoffs_headless()`) to
  cover it. Add date-stall watchdog in UI.

### B-O5: `_calculate_team_strength` missing from GameManager (non-fatal but degrades sim)
- **File:** `game_manager.py`, `_simulate_game_lightweight` (~line 14865)
- **Problem:** `self._calculate_team_strength(home_team)` → `AttributeError`.
  Never moved from `HockeyManagerGUI` (Bot A F-3 missed it). Caught by except
  (non-fatal), but every lightweight game sim fails at strength calc — 120
  occurrences in 50 days. Games fall back to degraded logic.
- **Evidence:** `AttributeError: 'GameManager' object has no attribute
  '_calculate_team_strength'. Did you mean: '_career_team_strength'?`
- **Suggested fix:** Copy from `main.py` `HockeyManagerGUI` (Bot A F-3 pattern).
  Related to Bot A O-6.

---

## SIM STATUS

- **Furthest honest run:** Day 228 (season end) — blocked by B-O3.
- **False CLEAN:** 730 "days" with date frozen at 2027-04-20 (B-O4) — not valid.
- **Harness workarounds** (test-only, not game fixes): goalie recall/generate
  on NO GOALIE; `ensure_dressed_lineup_auto` fallback on dress_minimum;
  `_show_season_summary` no-op; `_bulk_simming = True`; date-stall detection.
- **UI logic tested via Qt stubs:** `do_draft_pick`, FA/waiver helpers import
  clean (cannot instantiate Qt widgets without libEGL).
