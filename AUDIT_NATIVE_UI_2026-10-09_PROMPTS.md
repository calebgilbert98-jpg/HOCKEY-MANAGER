# Developer Prompts and Dispatch Plan — Native UI Follow-up — 2026-10-09

These prompts address the remaining gaps in `AUDIT_NATIVE_UI_2026-10-09.md` against `native-ui` commit `4a6d5f6623a7f375e04d576bae12e8b20fb23ccf`. One prompt owns one file. Do not assign two prompts touching a shared file in parallel. For any `NEEDS-RESEARCH` item, report the canonical API and call sites before changing code.

## Developer prompts

### `native_ui/screens/watch.py` — Major

Fix `native_ui/screens/watch.py` per Copilot audit.

**File:** `native_ui/screens/watch.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Watched games can be simulated again for schedule entries not represented as dictionaries; safe-call diagnostics omit operation context.
**Severity:** Major
**Lines:** 419–435, 465–489

**Current code:**
```python
if isinstance(entry, dict):
    entry["watched"] = True
# Result recording and standings update follow.
rec = getattr(game, "_record_game_result", None)
if callable(rec):
    rec(result)
```

**Root cause:** The UI does not persist completion through every supported schedule-entry shape or a canonical result API; failure logs omit the action context.

**Fix:** NEEDS-RESEARCH. Inspect schedule normalization and day-simulation completion checks (`game_classes.py`, `schedule_engine.py`, and callers of `simulate_day`). Identify the canonical completion/result writer, then use it for every supported entry shape. Do not record or update standings twice. Add `context="watch/<operation>"` to failure-prone `safe_call` calls in this file.

**Verify:** Watch tuple- and dict-backed fixtures, continue the day, and assert one simulation, result, and standings update for each.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/waivers.py` — Major

Fix `native_ui/screens/waivers.py` per Copilot audit.

**File:** `native_ui/screens/waivers.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Non-host multiplayer waiver claims do not enter the resolution queue.
**Severity:** Major
**Lines:** 237–258

**Current code:**
```python
player.user_claim_pending = True
return True, f"Waiver claim submitted for {pname}..."
```

**Root cause:** The UI writes only host claim state instead of using the engine's canonical host/multiplayer submission API.

**Fix:** NEEDS-RESEARCH. Grep for `user_claim_pending`, `mp_claim_teams`, `process_waivers`, and all claim submission callers in `game_classes.py`, `waiver_logic.py`, and `multiplayer/`. Confirm the API's return shape. Submit claims through it; never call the claim transfer primitive before priority resolution.

**Verify:** Compete host and non-host claims at different priorities; only the top valid claim transfers the player, once.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/roster.py` — Major

Fix `native_ui/screens/roster.py` per Copilot audit.

**File:** `native_ui/screens/roster.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Waiver lookup failures allow direct demotion; NHL capacity uses raw roster length; moves may leave affiliate roster stale; safe-call diagnostics omit operation context.
**Severity:** Major
**Lines:** 873–877, 918–938, 970–974

**Current code:**
```python
if to == "nhl" and len(
        safe_call(lambda: list(team.roster), []) or []) >= 23:
    errors.append(f"{name}: NHL roster full (23)")
    continue
try:
    import waiver_logic as _wl
    _eligible = bool(_wl.is_waiver_eligible(player))
except Exception:
    _eligible = False
team.remove_player(player)
team.add_player(player, roster_type)
```

**Root cause:** UI logic duplicates roster rules and treats unknown waiver state as exemption; affiliate state is not kept consistent.

**Fix:** Use `roster_limits.ACTIVE_ROSTER_MAX` and `active_roster_count(team)` before every NHL-destination mutation. Make waiver eligibility tri-state: eligible => canonical waiver placement; exempt => roster API; unknown/error => block with visible explanation. Inspect `Team.add_player`/`remove_player` and affiliate synchronization in `game_classes.py`/`roster_limits.py`; use the canonical path for both clubs, never direct list edits. Preserve `set_player(player, elc=elc)` context navigation. Add `context="roster/<operation>"` to failure-prone `safe_call` calls in this file.

**Verify:** Cover 22/23 active-player limits plus IR/LTIR, waived, emergency, inactive-contract players; test eligible/exempt/error demotions; move both directions and assert both rosters, team name, and history exactly once.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/lines.py` — Major

Fix `native_ui/screens/lines.py` per Copilot audit.

**File:** `native_ui/screens/lines.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Duplicate guard blocks valid use of the same player in separate PP/PK units.
**Severity:** Major
**Lines:** 459–473, 656–707

**Current code:**
```python
for tab in self._line_tabs.values():
    for sid, s in tab._slots.items():
        if exclude_slot is not None and s is exclude_slot:
            continue
        p = s.player
        if p is not None and str(getattr(p, "id", id(p))) == player_id:
            return sid
```

**Root cause:** The guard treats every editor tab as simultaneously deployed.

**Fix:** NEEDS-RESEARCH. Compare lineup slot groups consumed together in the engine and web editor. Scope both selection-time and pre-save validation to simultaneously deployed groups only; preserve validation against tampered saves. Do not remove the G2 slot or its save/restore behavior.

**Verify:** Permit reuse between independent PP/PK groups; reject duplicate even-strength deployment and a tampered duplicate save.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/schedule.py` — Major / Minor

Fix `native_ui/screens/schedule.py` per Copilot audit.

**File:** `native_ui/screens/schedule.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Missed-game simulation assembles partial result data; League schedule lacks team/opponent search; safe-call diagnostics omit operation context.
**Severity:** Major (result path); Minor (filter)
**Lines:** 301–345, 383–408, 451–457

**Current code:**
```python
"player_ratings": {},
...
rec = getattr(game, "_record_game_result", None)
if callable(rec):
    rec(game_result)
# standings update is applied separately
```

**Root cause:** Schedule UI maintains a partial postgame path and the League tab exposes only month/team-user filters.

**Fix:** For result processing, NEEDS-RESEARCH: trace normal day simulation and use its canonical result-processing API and complete result shape exactly once; remove duplicate updates only after confirming the canonical API includes them. Add searchable home/away team filtering across scheduled and completed entries with a clear reset. Add `context="schedule/<operation>"` to failure-prone `safe_call` calls in this file.

**Verify:** Compare missed-game result, player stats, records, standings, and indexes to normal simulation; search both teams across future and completed games and reset.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/tactics.py` — Major

Fix `native_ui/screens/tactics.py` per Copilot audit.

**File:** `native_ui/screens/tactics.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Missing reputation service falls back to direct system mutation despite coach ownership; safe-call diagnostics omit operation context.
**Severity:** Major
**Lines:** 585–603, 869–883

**Current code:**
```python
control = "coach"
if _tx is not None:
    control = safe_call(lambda: _tx.get_tactics_control(team), "coach")
if control == "gm" or _rs is None:
    _tx.set_team_system(team, cat, skey)
else:
    res = _rs.suggest_tactics_to_coach(
        team, {cat: skey}, self._team_context()) or {}
```

**Root cause:** Service failure is treated as proof the GM owns the whiteboard.

**Fix:** NEEDS-RESEARCH. Find the canonical ownership decision and return shape in `reputation_system.py` and existing tactics handlers. If coach-owned, require that flow; if the service is unavailable, block mutation and show an actionable error. Permit direct mutation only after explicit GM-ownership confirmation. Add `context="tactics/<operation>"` to failure-prone `safe_call` calls in this file.

**Verify:** Coach-owned, GM-owned, and unavailable-service tests; assert consequences occur only on canonical ownership path.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/morale.py` — Major

Fix `native_ui/screens/morale.py` per Copilot audit.

**File:** `native_ui/screens/morale.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Team Talk derives rivalry/streak but defaults live score to tied.
**Severity:** Major
**Lines:** 1039–1059, 1107–1143

**Current code:**
```python
ctx = {"score_state": "tied", "rival": False, "streak": 0}
# Intermission score lookup is not implemented; the method returns tied.
```

**Root cause:** Current game/intermission score is not read from canonical game state.

**Fix:** NEEDS-RESEARCH. Trace active game/intermission score and result representations; derive from the authoritative current game. If no authoritative score exists, mark score context unavailable and do not feed a fabricated tie to `give_talk`. Keep inputs read-only.

**Verify:** Test tied and non-tied intermissions; inspect `give_talk` arguments and verify widget edits cannot change them.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `.github/workflows/build-native.yml` — Major

Fix `.github/workflows/build-native.yml` per Copilot audit.

**File:** `.github/workflows/build-native.yml` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Packaged TOC validation does not reject unexpected modules when source modules are all present.
**Severity:** Major
**Lines:** 101–167

**Current code:**
```python
if missing_source_modules:
    # inspect TOC here; packaged-module check is conditional
```

**Root cause:** Source and packaged manifest checks are not independent.

**Fix:** Define one explicit expected module manifest. Always compare discovered source modules and PyInstaller TOC modules against it; fail on missing or unexpected entries. Keep manifest aligned with screen registration.

**Verify:** In temporary fixtures, remove an expected module and add an unexpected TOC module; both cases must fail the validation step.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/contract_negotiation.py` — Major / Minor

Fix `native_ui/screens/contract_negotiation.py` per Copilot audit.

**File:** `native_ui/screens/contract_negotiation.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** ELC clause is visible but not submitted; term/bonus UI caps are partly hardcoded and not sourced from engine rules.
**Severity:** Major (misleading offer term); Minor (limits)
**Lines:** 30–37, 103–144, 128–132, 227–285, 487–488

**Current code:**
```python
# ELC clause control remains visible
# offer seeding still contains hardcoded term/AAV caps
```

**Root cause:** UI options and seed values are not fully aligned with canonical offer validation.

**Fix:** NEEDS-RESEARCH. Trace `handle_elc_offer` and standard offer validation to confirm supported terms and limits. Hide/disable any unsupported ELC clause or submit it through the validated API if supported. Replace remaining literals with canonical shared limits; do not raise limits beyond engine policy.

**Verify:** Boundary tests for years/AAV/bonuses and ELC terms; saved contract must match every accepted, displayed term.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/main_window.py` — Minor

Fix `native_ui/main_window.py` per Copilot audit.

**File:** `native_ui/main_window.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Result metadata joins, completed-today detection, shared standings sort, complete navigation state, and oversized shell methods remain incomplete.
**Severity:** Minor
**Lines:** 789–790, 848–939, 938–945, 977–995, 1063–1067, 1376–1387, 1825–1982, 1991–2022, 2563–2702, 2753–2896

**Current code:**
```python
# _sched_played checks entry["played"] only
# hub locally recreates standings ordering and reads schedule metadata directly
# show_screen leaves prior selection for unmapped screens
```

**Root cause:** Hub, schedule, and navigation independently derive state and duplicate policy.

**Fix:** Assign one owner to this file. Reuse canonical schedule/result join and standings sorter. Determine completion from normal and watched results; distinguish OT/SO losses by authoritative metadata. Complete screen-to-section mapping with explicit no-active-section behavior and actual top-bar keys. Extract refresh/registry/blocker/menu helpers while preserving registered screens.

**Verify:** Test normal and watched completed/unplayed today games, regulation/OT/SO losses, tied standings, every direct navigation route, and hub/blocker/menu smoke flows. Compare registry keys before/after refactor.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/trade_block.py` — Minor

Fix `native_ui/screens/trade_block.py` per Copilot audit.

**File:** `native_ui/screens/trade_block.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Negotiate from Other Teams reads the Interest selection.
**Severity:** Minor
**Lines:** 775–804, 830–832

**Current code:**
```python
def _on_negotiate(self):
    row = self._interest_row()
    ...
```

**Root cause:** One handler assumes all callers originate in the Interest tab.

**Fix:** Pass the selected row/entity from each tab explicitly into the trade initialization API; preserve the Interest behavior and use `_other_rows` for Other Teams.

**Verify:** Select different rows in both tabs and assert each opens a trade with the corresponding selected entity.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/widgets/context_menu.py` — Minor

Fix `native_ui/widgets/context_menu.py` per Copilot audit.

**File:** `native_ui/widgets/context_menu.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Own-team player context can be preselected as an invalid trade partner.
**Severity:** Minor
**Lines:** 170–187

**Current code:**
```python
main_window.show_screen("trades")
screen.set_teams(..., selected_player=player)
```

**Root cause:** Context preselection does not distinguish user-side assets from eligible opponent partners.

**Fix:** Check player team and trade builder's side semantics. Put own-team player on the user side; preselect only eligible opponent partners. Surface a useful warning when the entity cannot be traded. Keep contract/staff navigation error handling intact.

**Verify:** Launch trade from own-team player, opponent player, and team menus; assert correct side and valid partner.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `puck_dynasty_native.py` — Minor

Fix `puck_dynasty_native.py` per Copilot audit.

**File:** `puck_dynasty_native.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Launcher instructions refer to a missing `requirements-native.txt`.
**Severity:** Minor
**Lines:** 23–24

**Current code:**
```python
# install requirements-native.txt
```

**Root cause:** The documented dependency filename does not exist.

**Fix:** **DO THIS AFTER:** `requirements.txt`. Use the actual selected dependency file or add the documented native file and maintain it; keep PySide6 aligned with the native build workflow.

**Verify:** Confirm the named file exists, install it in a clean environment, and run `python3 -c "import PySide6; import native_ui.main_window"`.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/systems_discipline.py` — Major

Fix `native_ui/screens/systems_discipline.py` per Copilot audit.

**File:** `native_ui/screens/systems_discipline.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Missing `systems_nav_bar` import crashes screen construction.
**Severity:** Major
**Lines:** 12–25

**Current code:**
```python
from .systems_common import (..., add_scroll_content)
# _build_body calls systems_nav_bar(self)
```

**Root cause:** Scroll refactor omitted a distinct navigation helper import.

**Fix:** **DO THIS AFTER:** `native_ui/screens/systems_common.py` (coordinate the shared API across the three Systems screens). Import `systems_nav_bar` from `.systems_common`.

**Verify:** Compile and instantiate this screen; confirm nav bar and scroll content both render.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/systems_condition.py` — Major

Fix `native_ui/screens/systems_condition.py` per Copilot audit.

**File:** `native_ui/screens/systems_condition.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Missing `systems_nav_bar` import crashes screen construction.
**Severity:** Major
**Lines:** 12–30

**Current code:**
```python
from .systems_common import (..., add_scroll_content)
# _build_body calls systems_nav_bar(self)
```

**Root cause:** Scroll refactor omitted a distinct navigation helper import.

**Fix:** **DO THIS AFTER:** `native_ui/screens/systems_common.py` (coordinate the shared API across the three Systems screens). Import `systems_nav_bar` from `.systems_common`.

**Verify:** Compile and instantiate this screen; confirm nav bar and scroll content both render.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/systems_circumstance.py` — Major

Fix `native_ui/screens/systems_circumstance.py` per Copilot audit.

**File:** `native_ui/screens/systems_circumstance.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Missing `systems_nav_bar` import crashes screen construction.
**Severity:** Major
**Lines:** 19–45

**Current code:**
```python
from .systems_common import (..., add_scroll_content)
# _build_body calls systems_nav_bar(self)
```

**Root cause:** Scroll refactor omitted a distinct navigation helper import.

**Fix:** **DO THIS AFTER:** `native_ui/screens/systems_common.py` (coordinate the shared API across the three Systems screens). Import `systems_nav_bar` from `.systems_common`.

**Verify:** Compile and instantiate this screen; confirm nav bar and scroll content both render.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/inbox.py` — Minor

Fix `native_ui/screens/inbox.py` per Copilot audit.

**File:** `native_ui/screens/inbox.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Retrieval failure can masquerade as an empty inbox; Important button lacks semantic checked state; safe-call diagnostics omit operation context.
**Severity:** Minor
**Lines:** 77–80, 644–650, 695–708, 729–741

**Current code:**
```python
def _all_messages(game):
    return safe_call(lambda: list(...), []) or []
# handler interprets an empty result as "No unread messages."
```

**Root cause:** Fail-soft fallback conflates retrieval failure with valid empty data; UI toggle has no accessible state.

**Fix:** Keep action-level retrieval success/error distinguishable and show a warning on failure; do not change safe rendering behavior globally. Make Important control checkable and synchronize checked/accessibility state with the model. Confirm success count after mark-all-read. Add `context="inbox/<operation>"` to failure-prone `safe_call` calls in this file.

**Verify:** Test empty/unread/error retrieval, toggle twice, inspect accessible state, and verify persisted importance.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/scouting.py` — Minor

Fix `native_ui/screens/scouting.py` per Copilot audit.

**File:** `native_ui/screens/scouting.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Prospect assignment picker is capped and non-searchable; some screen methods remain oversized; safe-call diagnostics lack context labels.
**Severity:** Minor
**Lines:** 55–56, 93–102, 115–119, 531–680

**Current code:**
```python
prospects = prospects[:MAX_ASSIGNMENT_PROSPECTS]
# assignment selector is a flat combo with no search/count
```

**Root cause:** Named cap still silently excludes players; assignment UI and body remain difficult to discover/test.

**Fix:** Replace capped flat selector with searchable/paged selection, visible match count, and selection preservation. If a cap remains, visibly explain it. Extract body construction into focused helpers. Add meaningful `context=` values to safe-call sites owned by this file.

**Verify:** Search/assign a prospect beyond 200, preserve selection through filtering, and run scouting screen smoke checks.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/trades.py` — Minor

Fix `native_ui/screens/trades.py` per Copilot audit.

**File:** `native_ui/screens/trades.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Trade asset filters do not display selected asset counts; shared `safe_call` calls omit operation context.
**Severity:** Minor
**Lines:** 609–649, 943–953, 1031–1041

**Current code:**
```python
# labels at 1031–1041 report retention slots, not selected trade assets
```

**Root cause:** The visible counts represent a different concept than checked trade assets.

**Fix:** Add selected player and pick counts for both sides, updating on toggles and preserving selected assets across filtering. Do not replace retention-slot counts if they serve another purpose. Add stable `context="trades/<operation>"` labels at failure-prone `safe_call` call sites; retain the shared helper and fallback values.

**Verify:** Select assets, filter them out of view, and assert counts and submitted trade remain correct.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/free_agents.py` — Minor

Fix `native_ui/screens/free_agents.py` per Copilot audit.

**File:** `native_ui/screens/free_agents.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issues:** Counter/pending outcome status is not retained in the offer panel; several methods remain oversized.
**Severity:** Minor
**Lines:** 678–816, 799, 989–997, 1331–1436

**Current code:**
```python
# counter/pending result launches another dialog and closes the offer panel
```

**Root cause:** Result classification and UI lifetime are split across dialogs; UI builders/actions are monolithic.

**Fix:** Use shared offer outcome classification and render every result in the same panel; reserve “Signed” for confirmed acceptance. Extract UI sections/actions into focused helpers.

**Verify:** Exercise accepted, countered, awaiting, consideration, and rejected paths; verify each state appears in the originating panel and existing offer behavior remains correct.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/contracts.py` — Minor

Fix `native_ui/screens/contracts.py` per Copilot audit.

**File:** `native_ui/screens/contracts.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Extension offer messages do not use the shared outcome wording.
**Severity:** Minor
**Lines:** 1310–1326, 1373–1398

**Current code:**
```python
# extension outcomes use local strings instead of shared outcome mapping
```

**Root cause:** Extension flows were not migrated to the common classifier.

**Fix:** **DO THIS AFTER:** `native_ui/screens/contract_negotiation.py`. Import/use the shared status classifier/text map for all extension results; do not call an offer “Signed” before confirmed acceptance.

**Verify:** Test accepted, countered, consideration, awaiting, and rejected outcomes and compare wording/status to the negotiation screen.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/draft_central.py` — Minor

Fix `native_ui/screens/draft_central.py` per Copilot audit.

**File:** `native_ui/screens/draft_central.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** “Trade This Pick” opens generic Trades without passing the current pick.
**Severity:** Minor
**Lines:** 64–68, 154–160

**Current code:**
```python
# opens Trades but carries no current-pick context
```

**Root cause:** Button label and destination do not match an initialized trade-up flow.

**Fix:** NEEDS-RESEARCH. Inspect `TradesScreen` initialization and draft trade-up flows. If a trade-up flow exists, preload current pick and partner; otherwise rename the button/tooltip to accurately describe generic Trades navigation.

**Verify:** Confirm label/destination consistency and, when supported, current-pick preselection.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/standings.py` — Minor

Fix `native_ui/screens/standings.py` per Copilot audit.

**File:** `native_ui/screens/standings.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Shared `safe_call` exists, but screen/action context is omitted at standings call sites.
**Severity:** Minor
**Lines:** `standings.py:38–43` and failure-prone `safe_call` call sites.

**Current code:**
```python
return safe_call(operation, default)  # no operation context
```

**Root cause:** Helper consolidation was not followed by diagnostic context at operation boundaries.

**Fix:** Add stable `context="standings/<operation>"` labels at failure-prone call sites. Keep the shared helper and fallback values; do not recreate a local wrapper.

**Verify:** Inject a failing standings operation and confirm the log includes operation context and traceback; run standings smoke checks.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/finances.py` — Minor

Fix `native_ui/screens/finances.py` per Copilot audit.

**File:** `native_ui/screens/finances.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Shared `safe_call` exists, but screen/action context is omitted at finance call sites.
**Severity:** Minor
**Lines:** `finances.py:62–67` and failure-prone `safe_call` call sites.

**Current code:**
```python
return safe_call(operation, default)  # no operation context
```

**Root cause:** Helper consolidation was not followed by diagnostic context at operation boundaries.

**Fix:** Add stable `context="finances/<operation>"` labels at failure-prone call sites. Keep the shared helper and fallback values; do not recreate a local wrapper.

**Verify:** Inject a failing finance operation and confirm the log includes operation context and traceback; run finance smoke checks.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

### `native_ui/screens/draft.py` — Minor

Fix `native_ui/screens/draft.py` per Copilot audit.

**File:** `native_ui/screens/draft.py` (YOU OWN THIS FILE - no other agent is editing it)

**Issue:** Shared `safe_call` exists, but screen/action context is omitted at draft call sites.
**Severity:** Minor
**Lines:** `draft.py:55–60` and failure-prone `safe_call` call sites.

**Current code:**
```python
return safe_call(operation, default)  # no operation context
```

**Root cause:** Helper consolidation was not followed by diagnostic context at operation boundaries.

**Fix:** Add stable `context="draft/<operation>"` labels at failure-prone call sites. Keep the shared helper and fallback values; do not recreate a local wrapper.

**Verify:** Inject a failing draft operation and confirm the log includes operation context and traceback; run draft smoke checks.

**Follow dev process:** 3 reviewers, integration check, commit and push to `native-ui` when done.

## Dispatch Plan

**Batch 1 (independent, dispatch together):**
- `native_ui/screens/watch.py` — 2 issues, Major/Minor
- `native_ui/screens/waivers.py` — 1 issue, Major
- `native_ui/screens/lines.py` — 1 issue, Major
- `native_ui/screens/morale.py` — 1 issue, Major
- `.github/workflows/build-native.yml` — 1 issue, Major
- `native_ui/screens/trade_block.py` — 1 issue, Minor
- `native_ui/screens/trades.py` — 2 issues, Minor
- `native_ui/screens/draft_central.py` — 1 issue, Minor
- `puck_dynasty_native.py` — 1 issue, Minor; wait for the dependency-file choice in `requirements.txt`

**Batch 2 (depends on Batch 1 or shared APIs):**
- `native_ui/screens/roster.py` — 1 owner for all roster findings; coordinate use of the canonical waiver/roster APIs with waiver work.
- `native_ui/screens/schedule.py` — 1 owner for result processing and League filters.
- `native_ui/screens/tactics.py` — 1 issue, Major; complete API research before implementation.
- `native_ui/screens/contract_negotiation.py` — 1 owner for ELC terms and shared contract limits.
- `native_ui/screens/free_agents.py` — shared contract outcome classifier; after classifier/contract UI API agreement.
- `native_ui/screens/contracts.py` — after outcome classifier is agreed.
- `native_ui/screens/scouting.py` — 1 owner for assignment UX, local refactor, and safe-call context.
- `native_ui/screens/inbox.py` — 1 owner for retrieval and accessibility states.
- `native_ui/screens/systems_discipline.py`, `systems_condition.py`, `systems_circumstance.py` — assign one coordinated group or implement imports as a single atomic patch; these screens share the Systems navigation API.

**Batch 3 (shared shell integration; one owner):**
- `native_ui/main_window.py` — all hub/results/navigation issues belong to one owner because they touch shared shell state and methods.
- `native_ui/screens/standings.py`, `native_ui/screens/finances.py`, and `native_ui/screens/draft.py` — separate one-file prompts for context labels; do not alter the shared helper.
- Integration reviewer verifies all Batch 1/2 changes together before this batch closes.

**Do not dispatch together (shared dependencies):**
- `systems_discipline.py` + `systems_condition.py` + `systems_circumstance.py` — same `systems_nav_bar` import/API; coordinate as one change.
- `contract_negotiation.py` + `free_agents.py` + `contracts.py` — shared outcome classifications and contract-term semantics.
- `main_window.py` + `schedule.py` + `watch.py` — schedule completion and result metadata must have one agreed canonical shape.
- `roster.py` + `waivers.py` — waiver placement, claim state, and roster mutation semantics overlap.
- The ten `safe_call` call-site modules have individual file prompts in this pack; do not edit the shared helper or change fallback values.

## Execution order

1. Assign one owner per file and share the target `native-ui` commit hash.
2. Complete `NEEDS-RESEARCH`/API discovery before code edits; post the canonical method and callers to the integration reviewer.
3. Implement regression fixes first (Systems imports, PP/PK duplicate semantics, inbox retrieval distinction).
4. Run focused verification, then integration checks across schedule, roster/waivers, contracts, and navigation.
5. Obtain three reviews: code correctness, logic/design, hockey realism. Resolve findings before commit/push.
