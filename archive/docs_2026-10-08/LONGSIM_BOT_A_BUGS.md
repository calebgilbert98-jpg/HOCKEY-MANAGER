# LONG-SIM BOT A — Bug Report (Report-Only Mode)

**Branch:** native-ui | **Date:** 2026-10-07
**Mission:** 2-year (730-day) continuous sim, zero bugs. Report issues, do not fix.

---

## FIXES ALREADY APPLIED (in working tree, need serial review)

These were applied before the report-only directive. They are required for the
sim to progress at all. A single dev should review and re-apply serially.

### F-1: `game_manager.py` — `GameManager.__init__` missing `game_results`
- **File:** `game_manager.py`, `__init__` (~line 97)
- **Problem:** `_trim_history_logs()` (line ~5899) does `len(self.game_results)` but
  `game_results` was never initialized → `AttributeError` crash on `simulate_day()`.
- **Fix applied:** Added `self.game_results = []` in `__init__` (ported from
  `main.py:288` `HockeyManagerGUI`).
- **Status:** In tree. Needs review.

### F-2: `game_manager.py` — `__init__` missing `memory_optimizer` / `lazy_manager`
- **File:** `game_manager.py`, `__init__` (~line 141)
- **Problem:** Line ~7703 does `if self.memory_optimizer` → `AttributeError`
  (attribute never assigned). Ported from `main.py:14062-14066`
  (`_initialize_phase2_systems`).
- **Fix applied:** Added `self.memory_optimizer = None` and `self.lazy_manager = None`.
- **Status:** In tree. Needs review.

### F-3: `game_manager.py` — ~34 methods called but never moved from `HockeyManagerGUI`
- **File:** `game_manager.py` (inserted before `_log_slate_fallback`, ~line 13540)
- **Problem:** AST scan found 42 `self.X` calls with no definition in `GameManager`.
  30+ existed in `main.py` `HockeyManagerGUI` and were never moved. Each one is a
  crash waiting for its code path (sim, offseason, draft, awards, etc.).
- **Methods copied from main.py:**
  - `_slate_deterministic_result` (crashed `_sim_game_guaranteed` line ~8771)
  - `_simulate_game_lightweight` (crashed `_sim_game_guaranteed`)
  - `_simulate_game_full_batch`
  - `_hold_draft_lottery`, `_hold_entry_draft` (offseason)
  - `_calculate_season_awards` (season end)
  - `_guarantee_offseason_tentpoles`, `_offseason_board_review`, `_offseason_immortality`
  - `_record_season_to_history`, `_validate_season_continuity`
  - `_update_offseason_reputations`, `_weekly_coaching_mults`
  - `_daily_international_window`, `_league_sim_detail`
  - `_career_matchday_pre`, `_career_star_of_game`, `_career_team_games`,
    `_career_team_strength`, `_career_user_game_today`, `_career_weekly_update`
  - `_consume_team_talk_session`, `_present_team_talk_screen`, `_prune_team_talk_sessions`
  - `_create_awards_section`, `_create_leaders_section`, `_create_team_summary_section`
  - `_get_developable_attributes`
  - `_mp_offer_to_host`, `_mp_serialize_offer`, `_mp_swapped_user_team`
  - `_try_ai_ai_deadline_deal`
  - `generate_trade_package`, `present_trade_offers`
  - (`get_settings` and `_generate_daily_emails` were added by another bot)
- **Status:** In tree. Needs review. Copy-paste port; shims not decomposed.

### F-4: `database_manager.py` — roster generation leaves teams with <2 NHL goalies
- **File:** `database_manager.py`, `populate_nhl_teams()` (after "NHL teams populated successfully")
- **Problem:** 11/32 teams ended up with 0–1 NHL goalies. The position draft
  distributes 2 goalies per team, but the second-pass roster-size trim
  (`if len(target_team.roster) > 23: move lowest-rated to AHL`) demoted 2nd
  goalies to the AHL. Result: day-one `dress_minimum` blocker, sim cannot advance.
- **Fix applied:** Post-pass: while any team has <2 NHL goalies, recall best AHL
  goalie; if roster exceeds 23, demote lowest-rated skater to AHL.
- **Status:** In tree. Needs review.

### F-5: `game_manager.py` — AI roster safety net in `_process_daily_maintenance`
- **File:** `game_manager.py`, `_process_daily_maintenance()` (~line 4860)
- **Problem:** AI trades can leave AI clubs with <18 NHL players (observed:
  Seattle 21→19→17 over days 66–69 with zero injuries). No auto-correction exists.
  (User team is covered by `user_roster_compliance` + blockers; AI teams are not.)
- **Fix applied:** Daily loop over AI teams: if NHL roster <18, recall best
  available from AHL by overall rating until 18.
- **Status:** In tree. Needs review. This is a band-aid; the root cause is AI
  trade validation allowing roster-depleting deals.

### F-6: `native_ui/screens/save.py` — wrong `QShortcut` import
- **File:** `native_ui/screens/save.py`, line ~29
- **Problem:** `QShortcut` imported from `PySide6.QtWidgets`; it lives in
  `PySide6.QtGui` → `ImportError`, screen cannot load.
- **Fix applied:** Moved `QShortcut` to the `PySide6.QtGui` import.
- **Status:** In tree. Needs review.

### F-7: `native_ui/screens/watch.py` — wrong `QShortcut` import
- **File:** `native_ui/screens/watch.py`, line ~26
- **Problem:** Same as F-6.
- **Fix applied:** Moved `QShortcut` to the `PySide6.QtGui` import.
- **Status:** In tree. Needs review.

### F-8: `native_ui/screens/standings.py` — `None` widget in layout rebuild
- **File:** `native_ui/screens/standings.py`, `_rebuild_view_pills()` (~line 559)
- **Problem:** `lay.addWidget(inner.takeAt(0).widget())` — if `takeAt(0)` returns
  an item whose `widget()` is `None` (spacer/nested layout), `addWidget(None)`
  raises `Invalid parameter None passed to addLayoutOwnership()`. Crashes
  `refresh()` → `_render_overview()`.
- **Fix applied:** Guard: only `addWidget` when widget is not None.
- **Status:** In tree. Needs review.

### F-9: `native_ui/screens/team.py` — `setStyleSheet` on `QTableWidgetItem`
- **File:** `native_ui/screens/team.py` (~line 287)
- **Problem:** `QTableWidgetItem.setStyleSheet("font-weight: 700;")` —
  `QTableWidgetItem` has no `setStyleSheet` → `AttributeError` in `refresh()`.
- **Fix applied:** Use `QFont` bold via `item.setFont()` instead.
- **Status:** In tree. Needs review.

---

## OPEN ISSUES (found, NOT fixed — report only)

### O-1: Intermittent 0%-CPU stall ~day 50–70 (UNDER INVESTIGATION)
- **Symptom:** Sim process drops to 0% CPU and stops advancing days. Last log
  lines are usually `market deal blocked` or `blocker-timing` entries. Not a
  crash — process stays alive but idle.
- **What it is NOT:**
  - Not a Python infinite loop (would show high CPU).
  - Not the date-blocker issue (blockers return immediately; this is idle).
- **Hypotheses:**
  1. `signal.alarm`-based timeouts may interact badly with the sim (but the
     stall was observed before any alarm was installed).
  2. Possible deadlock in trade logic (`_try_ai_ai_deadline_deal` was just
     copied in; untested).
  3. Possible catastrophic slowdown misread as hang (but 0% CPU contradicts).
- **Evidence:**
  - Watchdog thread dumps placed the main thread in
    `simulation.py:_ppos_ensure` ← `_defense_tick` ← `_resolve_offensive_zone_play`
    ← `_resolve_zone_based_event` ← `_simulate_period` ← `run`
    ← `game_manager.py:_simulate_game_full_batch` ← `_sim_game_guaranteed`.
    (Single sample; `_ppos_ensure` is a fast init — the sample likely caught a
    call boundary, not the true hotspot.)
  - Per-game timing repro (40 days) showed no single game >5s; days varied
    0.1s–7.8s.
  - The stall did NOT reproduce in the 40-day per-game timing run.
- **Repro:** Intermittent. Observed in attempts 7, 8, 9 (~day 50–70 each time,
  different random seeds).
- **Suggested next step:** Run with `faulthandler.dump_traceback_later(60,
  exit=True)` to capture the true stack at stall time; or bisect by disabling
  AI trade evaluation for a run to isolate.
- **Status:** OPEN. Blocking 730-day completion.

### O-2: `dress_minimum` ↔ `roster_limit_23` blocker ping-pong (day ~35)
- **Symptom:** 4 injuries → `dress_minimum` blocker → auto-recall from AHL →
  roster hits 24 → `roster_limit_23` blocker.
- **Root cause:** `active_roster_count()` in `roster_limits.py` excludes IR/LTIR
  players, but injured players are not auto-placed on IR. A human would IR them;
  the auto-resolve path does not.
- **Workaround used in harness:** Place injured players on IR via
  `ir_system.place_on_ir()` before resolving `dress_minimum`.
- **Suggested fix:** In the `dress_minimum` auto-action (or
  `user_roster_compliance`), auto-place long-term injured players on IR before
  recalling, mirroring real NHL roster management.
- **Status:** OPEN (game-logic issue). Harness works around it.

### O-3: `auto_resolve.auto_choose_captains` does not apply the picks
- **File:** `auto_resolve.py`, `auto_choose_captains()` (line ~89)
- **Problem:** Returns `(captain, alternates), None` but never sets
  `player.captaincy`. The blocker's `auto_action` closure in `game_manager.py`
  (~line 3165 `_auto_captains`) does the assignment itself, so the UI path
  works — but any direct caller of `auto_choose_captains` gets picks that are
  never applied (blocker persists).
- **Suggested fix:** Either make `auto_choose_captains` apply the letters
  itself, or document that callers must apply. Prefer applying inside (single
  responsibility).
- **Status:** OPEN. Harness works around by applying manually.

### O-4: `season_meeting` blocker has no `auto_action`
- **File:** `coach_season_meeting.py`, `season_meeting_blocker()` (line ~963)
- **Problem:** Returns dict with only `action` (opens UI window). No
  `auto_action`, so headless/auto sims cannot resolve it. The completion call
  is `store_mandate(team, fields)` (line ~873).
- **Suggested fix:** Add `auto_action` that calls `store_mandate` with sensible
  defaults (matching the AI path).
- **Status:** OPEN. Harness works around via direct `store_mandate` call.

### O-5: `Player` has no `position` attribute (only `primary_position`)
- **File:** `game_classes.py` (`Player`), `database_manager.py`, various
- **Problem:** `Player` exposes `primary_position` (a `PlayerPosition` enum).
  Some code paths use `getattr(p, 'position', '') == 'G'` or compare
  `primary_position == 'G'` (enum vs str — always False). E.g.
  `atmospheric_dashboard.py:850` compares `primary_position == 'G'` (broken).
- **Suggested fix:** Add a `position` property to `Player` returning
  `self.primary_position.value`, and audit all `== 'G'` comparisons to use
  the enum or the property consistently.
- **Status:** OPEN. Core sim uses `primary_position` correctly; UI/helpers are
  inconsistent.

### O-6: Remaining ~12 `self.X` calls in `game_manager.py` with no definition
- **Problem:** After the F-3 bulk copy, ~12 called-but-undefined attributes
  remain (mostly `_career_*`, `_alert_coach_hot_seat`, `_auto_fix_cap`,
  `show_screen`). Some may be false positives (dynamic attrs); others will
  crash when their code paths execute (career mode, offseason).
- **Suggested fix:** Same AST scan should be re-run after F-3; each remaining
  name triaged (copy from `main.py`, stub via `_ui_notify`, or confirm dead).
- **Status:** OPEN.

---

## SIM STATUS

- **Furthest clean run:** Day 107 (attempt 3) — stopped by Seattle roster bug (now F-5).
- **Current blocker:** O-1 intermittent stall ~day 50–70. No 730-day completion yet.
- **Blockers auto-resolved by harness:** `captaincy_choice`, `season_meeting`,
  `dress_minimum` (+IR placement), `roster_limit_23` (via its auto_action).
- **UI screens refresh-tested OK:** Roster, News, Inbox, Schedule, FreeAgents,
  Waivers, Lines, Finances, Draft (plus F-6–F-9 fixes for Save, Watch,
  Standings, Team).

---

## FILES CHANGED (working tree, uncommitted)

- `game_manager.py` (+2605 lines: F-1, F-2, F-3, F-5)
- `database_manager.py` (+40 lines: F-4)
- `native_ui/screens/save.py` (F-6)
- `native_ui/screens/watch.py` (F-7)
- `native_ui/screens/standings.py` (F-8)
- `native_ui/screens/team.py` (F-9)

---

## ADDITIONAL FINDINGS (report-only phase)

### O-7: `self.db_manager` vs `self.database_manager` mismatch
- **Symptom:** `Phase 2 maintenance error: 'GameManager' object has no attribute 'db_manager'`
- **File:** `game_manager.py` (Phase 2 maintenance section)
- **Problem:** Code references `self.db_manager` but `__init__` sets `self.database_manager`.
- **Suggested fix:** Add `self.db_manager = self.database_manager` alias in `__init__`,
  or update the reference to use `database_manager`.
- **Severity:** LOW (caught by except, non-fatal). But indicates incomplete port.

### O-1 UPDATE: Stall confirmed, faulthandler cannot interrupt
- **New data:** Report-only run with `faulthandler.dump_traceback_later(180, exit=True)`
  stalled at day 51. The 180s timer did NOT fire. SIGABRT killed the process
  without a traceback dump.
- **Interpretation:** The hang is below the Python signal-handling layer — either
  a C-extension call that never returns, or a tight loop that starves signal
  delivery. Not a Python-level infinite loop (would show CPU >0%).
- **Consistent repro:** Day ~50-51 across multiple random seeds.
- **Suggested next step:** Run under `gdb` with `thread apply all bt` at stall time
  to get the C-level stack. Or bisect: disable AI trade evaluation (`market deal
  blocked` messages dominate the pre-stall log) for one run.
