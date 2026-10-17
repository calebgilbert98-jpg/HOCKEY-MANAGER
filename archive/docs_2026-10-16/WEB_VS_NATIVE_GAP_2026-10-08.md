# Web UI → Native UI Feature Gap Audit — 2026-10-08

**Scope:** 51 web templates (`web_ui/templates/`) vs 72 native screens (`native_ui/screens/`).
**Method:** 3 parallel auditors compared each web template + web screen handler against the native screen file — cataloging tabs, buttons, filters, dialogs, actions, and stubs (TODO/FIXME/`pass` bodies/placeholder dialogs).

**Bottom line:** The port is remarkably complete. **~43 of 51 screens have zero functional gaps** — several natives are supersets. The remaining gaps are mostly small navigation/fidelity items. **One screen has a serious problem: `lines`** (dead Overview tab + missing toolbar/filters).

---

## 🔴 HIGH PRIORITY — lines (serious functional gaps)

Native: `native_ui/screens/lines.py`. Web: `lines.html` + handlers.

1. **Overview tab is dead** — `_render_overview()` early-returns because `_overview_label` is never created; the tab always shows placeholder text and never renders.
2. **Missing toolbar buttons: Auto Best, Clear (empty tab), Cancel (revert unsaved).**
3. **Missing roster sidebar** — the picker dialog has only a bare player table: no search, no position/streak filters (All/F/D/G/HOT/COLD), no sort dropdown (Overall/Points/Hot streak/Age/Name).
4. **No position-fit legend / out-of-position coloring** (green/yellow/red).
5. **No way to remove a player from a slot** — picker has no "clear slot" option (web drags back to roster).

---

## 🟡 MEDIUM PRIORITY

### scouting — missing beat-recall + filter fidelity
- **No Recall button** in the Regional Beat dialog (web lets you pull a scout off a beat; native only Assign/Cancel).
- **No Clear button** to reset DB filters.
- DB status filter is coarser: All / Draft eligible / Signed / Free agent — **missing NHL rosters / AHL rosters / Prospects** as separate statuses.
- Age bands lack U18; OVR bands lack 90+.

### watch — missing overlay + camera follow + profile click-through
- **No stats overlay** — the web's 📊 toggle (Goals/Hits/Penalties/Fights panel over the rink) has no native equivalent.
- **No click-a-player-to-follow** on the rink (web camera can follow a skater; native is follow-puck / full-rink only).
- Box-score tab rows are **not clickable to player profiles** (web supports click-through).

### schedule — Watch action degraded + stale message
- `_watch_game()` navigates to the watch screen **without passing game context** (web opens today's specific game).
- Stale fallback message remains: "The Watch screen has not been ported to the native UI yet." — but `watch.py` exists and is registered. Dead text, should be cleaned up.

---

## 🟢 LOW PRIORITY (small navigation fidelity)

### calendar — missing action links on event markers
- Web event markers have **action links** (→ Open Deadline Center / → Open Draft Day Central); native shows labels only (only the countdown banner's deadline button exists).
- No "Open Draft Day Central" path from draft-day cells or the day-detail dialog.
- Web's clickable opponent names (→ team pages) have no native equivalent.

### boxscore — header names not clickable
- Team names in the `BoxscoreDialog` header are plain text; web's are links to team pages.
- Player rows in the dialog are not clickable to profiles (same as watch gap).

### roster — captaincy-crisis banner missing
- Web shows the crisis banner on roster with resolution via morale; native roster has no banner.

### index (dashboard hub) — minor routing note
- Hub Injuries/Morale panels link to `dressing_room` in native vs `/morale` in web. Native has both screens; verify which is canonical.

---

## ⚪ DELIBERATE EXCLUSIONS (not gaps)

### inbox — compose/reply/forward intentionally omitted
Per Caleb's order (v0.26.16): native inbox is RECEIVE-ONLY. No compose editor. Documented in `native_ui/screens/inbox.py:7`.

---

## ✅ CLEAN SCREENS (zero functional gaps found)

**Chunk 1:** ahl, camp, captains, coach_checkin, compare, contracts, deadline, development, draft, fa_frenzy, fantasy_draft, finances, free_agents, history
**Chunk 2:** lottery, manager, morale, news, offer_sheets, player (player_profile.py), playoffs, replay, save, season_summary, settings, setup
**Chunk 3:** staff, staff_detail, standings, stats, systems_circumstance, systems_clutch, systems_condition, systems_deployment, systems_discipline, systems_rivalry, tactics, team, trade_block, trades, waivers

Notes:
- camp, deadline, finances, history, staff natives are **supersets** (extra tabs/sections beyond web).
- settings: field-for-field diff of `_FIELDS` between web and native = **zero differences**.
- Zero TODO/FIXME markers found in any audited native file; `pass` hits are only in `except` handlers; QMessageBox uses are legit confirms/feedback.
- boxscore has no standalone native screen but is **fully covered** as `native_ui/dialogs/boxscore.py` (904 lines, all 4 tabs) launched from schedule/replay/watch.

---

## Prioritized fix order (recommended)

1. **lines** — restore Overview render, add Auto Best/Clear/Cancel, picker search + filters + sort, position-fit legend, clear-slot option.
2. **scouting** — add Recall button, Clear-filters button, NHL/AHL/Prospects status options, U18 age band, 90+ OVR band.
3. **watch** — stats overlay toggle, click-to-follow camera, profile click-through on box-score rows.
4. **schedule** — pass game context to watch screen, remove stale "not ported" message.
5. **calendar** — action links on event markers (deadline center / draft day central), clickable opponent names.
6. **boxscore** — clickable team names + player rows in dialog.
7. **roster** — captaincy-crisis banner.
8. **index** — confirm Injuries/Morale routing target.

---

*Audited 2026-10-08 by 3 parallel workers; ~51 web templates × native comparison.*
