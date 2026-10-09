# Native UI Follow-up Audit — 2026-10-09

## Scope and method

This follow-up consolidates `AUDIT_FINDINGS_2026-10-08.md` (32 issues), `AUDIT_QUALITY_2026-10-08.md` (23 issues), and their verification against `native-ui` commit `4a6d5f6623a7f375e04d576bae12e8b20fb23ccf`. The verification covered source code only; it did not include runtime interaction tests. The original 55 findings are classified in `AUDIT_VERIFICATION_2026-10-08.md`.

## Summary

- Matches: 24/55
- Partial: 29
- Missing: 2
- Better: 0
- Regressions: 3
- Additional issue: 1 (also reflected in the launcher finding below)

The verified open work is detailed below. Severity is carried forward from the originating audit; regression-only items are Major unless stated otherwise.

## Open issues

### 1. Watched game can be simulated again
- **File:** `native_ui/screens/watch.py`
- **Severity:** Major
- **Lines:** 419–435, 465–489
- **What's wrong:** Result and standings updates occur, but the watched marker is reliably applied only to dictionary schedule entries.
- **Root cause:** The watched-game guard and schedule storage do not cover every supported entry shape; day simulation can revisit a tuple entry.
- **Fix:** Research how schedule entries are normalized and how the day simulator identifies completed games. Persist the watched result/marker through the canonical schedule/result API for every entry shape; avoid adding a second independent result record.
- **Verify:** Watch a game for each supported schedule-entry shape, continue the day, and assert one simulation, one result record, and one standings update.

### 2. Waiver claim queue omits multiplayer claim state
- **File:** `native_ui/screens/waivers.py`
- **Severity:** Major
- **Lines:** 237–258
- **What's wrong:** The UI sets `user_claim_pending`, but a non-host human-managed team is not represented by the `mp_claim_teams` marker consumed by waiver resolution.
- **Root cause:** The UI reproduces only the host claim state instead of calling the canonical claim-submission API.
- **Fix:** Search `game_classes.py`, `waiver_logic.py`, `multiplayer/`, and callers of `process_waivers` for the host and multiplayer submission paths. Route through their shared submission API, preserving its return/status shape; never execute the claim-transfer primitive from the UI.
- **Verify:** Submit claims as host and non-host teams with competing priority; resolution must award once to the highest-priority valid claim.

### 3. Demotion eligibility failure bypasses waivers
- **File:** `native_ui/screens/roster.py`
- **Severity:** Major
- **Lines:** 918–938
- **What's wrong:** A waiver eligibility lookup failure is treated as exemption, allowing a direct demotion.
- **Root cause:** Failure to determine eligibility is indistinguishable from confirmed ineligibility.
- **Fix:** Make eligibility tri-state: eligible routes to canonical waiver placement; confirmed exempt routes to the roster API; unknown/error blocks the move and presents an actionable message. Confirm APIs in `waiver_logic.py` and existing transaction handlers first.
- **Verify:** Test eligible, exempt, and injected eligibility-error cases; the error case must mutate neither roster.

### 4. Active roster capacity uses raw list length
- **File:** `native_ui/screens/roster.py`
- **Severity:** Major
- **Lines:** 873–877
- **What's wrong:** A call-up uses `len(team.roster)` and may reject a valid move or allow an invalid active count.
- **Root cause:** Raw roster length does not implement the engine's active-roster counting rules.
- **Fix:** Import and use `roster_limits.ACTIVE_ROSTER_MAX` and `active_roster_count(team)` for every move into the NHL roster, before mutation. Do not count emergency fillers, waived players, inactive-contract players, or IR/LTIR players independently.
- **Verify:** At 22 active players a call-up succeeds; at 23 it fails without mutation. Include IR/LTIR, waivers, and emergency-filler cases.

### 5. Roster move leaves affiliate stale
- **File:** `native_ui/screens/roster.py`
- **Severity:** Major
- **Lines:** 970–974
- **What's wrong:** Team APIs update the parent team's records, but an independently stored farm-team roster may not be synchronized.
- **Root cause:** The move path handles the user club but not its affiliate relationship.
- **Fix:** Trace the canonical affiliate synchronization in `game_classes.py` and `roster_limits.py`; use that same operation after `Team.remove_player`/`Team.add_player`. Do not mutate either roster list directly.
- **Verify:** Move players in both directions and assert parent roster, affiliate roster, `team_name`, history/stint state, and single membership.

### 6. Lineup duplicate guard rejects valid PP/PK reuse
- **File:** `native_ui/screens/lines.py`
- **Severity:** Major — regression
- **Lines:** 459–473, 656–707
- **What's wrong:** The duplicate guard scans every tab and prevents a player from appearing in separate power-play and penalty-kill units.
- **Root cause:** It equates all editor tabs with slots deployed simultaneously.
- **Fix:** Compare the editor's slot groups with the engine lineup consumer and web editor. Reject duplicates only among slots that can be active at the same time, both during selection and before save. Preserve rejection of tampered duplicate saves.
- **Verify:** A player can be assigned across separate PP/PK groups, but cannot occupy two simultaneous even-strength slots; repeat with a tampered save.

### 7. Missed-game path builds partial game results
- **File:** `native_ui/screens/schedule.py`
- **Severity:** Major
- **Lines:** 301–345
- **What's wrong:** The result uses an empty `player_ratings` map and locally assembles result data before separately updating standings.
- **Root cause:** The screen has not fully adopted the canonical postgame processing path.
- **Fix:** Find the normal day-simulation result-processing method and its complete result shape. Route the simulated game through it once, removing duplicated standings/team-record updates only after confirming the canonical method includes them.
- **Verify:** Simulate a past unplayed game; compare result fields, player stats, records, standings, and derived indexes to a normal game, each updated exactly once.

### 8. Coach-owned system can bypass ownership flow
- **File:** `native_ui/screens/tactics.py`
- **Severity:** Major
- **Lines:** 585–603, 869–883
- **What's wrong:** If the reputation/coach-ownership API (`_rs`) is unavailable, the screen calls `set_team_system` directly even when coach control is the default.
- **Root cause:** Missing service is treated as permission to bypass the ownership rules.
- **Fix:** Confirm the canonical coach ownership method and result shape in `reputation_system.py` and `tactics.py`. When coach-controlled, fail closed with a visible error if the service is unavailable; use direct mutation only when GM ownership is explicitly established.
- **Verify:** Test coach-owned, GM-owned, and unavailable-service cases; only GM-owned changes may bypass the coach decision flow.

### 9. Team Talk uses tied score instead of live score
- **File:** `native_ui/screens/morale.py`
- **Severity:** Major
- **Lines:** 1039–1059, 1107–1143
- **What's wrong:** Score editing is disabled and rivalry/streak are derived, but score context defaults to a tie rather than reading the current game.
- **Root cause:** The score source/representation for an active intermission is not joined to the talk context.
- **Fix:** Trace live game/intermission state and result representations; derive score from the canonical current-game state, or disable score-dependent context when no authoritative score exists. Keep all context fields read-only and do not pass widget substitutes to `give_talk`.
- **Verify:** Compare engine inputs with current game state for tied and non-tied intermissions; altering UI state must not affect inputs.

### 10. Bundle validation misses extra packaged screens
- **File:** `.github/workflows/build-native.yml`
- **Severity:** Major
- **Lines:** 101–167
- **What's wrong:** The expected module set is enforced against source files, but the PyInstaller TOC is checked only when expected source modules are missing.
- **Root cause:** Source discovery and packaged-module validation are conditional rather than independent checks.
- **Fix:** Keep one authoritative expected-screen manifest; unconditionally compare both discovered source modules and bundled TOC modules to it, failing on missing and unexpected entries. Do not restore a count-only threshold.
- **Verify:** In temporary checkouts, omit one expected module and inject one unexpected packaged module; both validations must fail.

### 11. ELC clause control advertises an unapplied term
- **File:** `native_ui/screens/contract_negotiation.py`
- **Severity:** Major
- **Lines:** 128–132, 227–285
- **What's wrong:** Clause remains visible for ELC offers, but the ELC submission path does not send it.
- **Root cause:** The UI exposes a term unsupported by the selected engine API.
- **Fix:** Confirm which terms `handle_elc_offer` validates/stores. Include clause only if supported by that API; otherwise hide/disable it for ELCs and state that it is unavailable. Apply the same rule to counter and accept paths.
- **Verify:** Submit and reopen ELC offers with every displayed term; assert saved terms equal accepted terms and unsupported terms are not offered.

### 12. Overtime metadata is not consistently joined
- **File:** `native_ui/main_window.py`
- **Severity:** Minor
- **Lines:** 1376–1387
- **What's wrong:** Display logic uses overtime/shootout metadata, but schedule entries may not receive those fields; watched games use `watched_*_score`.
- **Root cause:** The hub reads schedule fields without consistently joining the authoritative result record.
- **Fix:** Use the same schedule/result join as `schedule.py:136–156`, including watched results, and classify OTL only from canonical overtime/shootout metadata.
- **Verify:** Test one-goal regulation and overtime losses, shootout losses, and watched results; only OT/SO losses display OTL.

### 13. Next Game can show completed games
- **File:** `native_ui/main_window.py`
- **Severity:** Minor
- **Lines:** 789–790, 1063–1067
- **What's wrong:** Today's unplayed games are included, but `_sched_played()` only checks `played`; watched flags and recorded results may be missed.
- **Root cause:** Completion is inferred from one schedule flag instead of canonical result state.
- **Fix:** Determine completion using the canonical schedule/result lookup for normal and watched games. Include today only when no completed result exists.
- **Verify:** An unplayed game today appears; normal and watched completed games today do not.

### 14. Hub duplicates standings tie-break logic
- **File:** `native_ui/main_window.py`
- **Severity:** Minor
- **Lines:** 938–945
- **What's wrong:** The hub recreates the standings sort tuple locally.
- **Root cause:** No shared canonical sorter is used for both hub and standings screen.
- **Fix:** Search `standings.py` and league standings APIs for the canonical sorter. Reuse it; do not duplicate the rules in the hub.
- **Verify:** Feed tied teams with distinct secondary criteria to both screens and assert identical ordering.

### 15. Direct navigation leaves stale top-bar state
- **File:** `native_ui/main_window.py`
- **Severity:** Minor
- **Lines:** 1991–2022
- **What's wrong:** Unmapped screens leave the prior section selected, and roster/lines map to lowercase identifiers rather than the CLUB button.
- **Root cause:** Incomplete screen-to-section mapping and no explicit no-selection behavior.
- **Fix:** Enumerate registered screens and navigation actions; define one complete mapping to actual top-bar keys plus an explicit no-active-item value. Update state in `show_screen()` from that map.
- **Verify:** Navigate from each menu/context action and assert screen and active top-bar item; unmapped screens must clear stale selection.

### 16. Trade Block Other Teams action reads wrong row
- **File:** `native_ui/screens/trade_block.py`
- **Severity:** Minor — regression
- **Lines:** 775–804, 830–832
- **What's wrong:** The Other Teams tab calls a handler that reads the Interest tab selection.
- **Root cause:** A shared action handler assumes the source tab is always Interest.
- **Fix:** Pass the selected team/player explicitly from each tab into the trade screen initialization API; keep each tab's row lookup separate.
- **Verify:** Invoke Negotiate from both tabs with different selected entities and assert the correct entity is preloaded.

### 17. Own-team player can seed an invalid trade partner
- **File:** `native_ui/widgets/context_menu.py`
- **Severity:** Minor
- **Lines:** 170–187
- **What's wrong:** A player from the user's club may be resolved as the partner team, although the trade screen excludes that club as a selectable partner.
- **Root cause:** Context preselection does not distinguish own-team assets from opponent assets.
- **Fix:** Determine the clicked player's team and the trade builder's user/partner side contract. Put a user-roster player on the user side; only preselect a partner for an eligible opponent entity. Show a useful message if the clicked team is not tradable.
- **Verify:** Launch from own-team player, opponent player, and team context menus; preselection must be valid and on the correct side.

### 18. Native launcher points to a nonexistent requirements file
- **File:** `puck_dynasty_native.py`
- **Severity:** Minor — additional issue
- **Lines:** 23–24
- **What's wrong:** Instructions say to install `requirements-native.txt`, which is absent; the project has `requirements.txt`.
- **Root cause:** Documentation was updated without matching the actual dependency-file choice.
- **Fix:** Point to the existing dependency file selected by the project, or add and maintain the documented native requirements file. Keep its PySide6 version aligned with the build workflow.
- **Verify:** Confirm the named file exists and in a clean environment run the documented install followed by `python3 -c "import PySide6; import native_ui.main_window"`.

### 19. Systems pages fail at construction
- **Files:** `native_ui/screens/systems_discipline.py`, `native_ui/screens/systems_condition.py`, `native_ui/screens/systems_circumstance.py`
- **Severity:** Major — regression
- **Lines:** discipline 12–25; condition 12–30; circumstance 19–45
- **What's wrong:** All three call `systems_nav_bar()` after the scroll-helper refactor, but none imports it.
- **Root cause:** Refactoring scroll-container setup removed/omitted a separate navigation helper import.
- **Fix:** Add `systems_nav_bar` to the `.systems_common` imports in all three modules. Keep file ownership coordinated because all three use the shared Systems navigation API.
- **Verify:** Compile the three modules and instantiate each Systems page in the native UI smoke check; no `NameError` may occur.

### 20. Mark-all-read may falsely report no unread messages
- **File:** `native_ui/screens/inbox.py`
- **Severity:** Minor — regression
- **Lines:** 77–80, 695–708
- **What's wrong:** `_all_messages()` converts retrieval failure into `[]`; the handler reports “No unread messages” without knowing retrieval succeeded.
- **Root cause:** Failure fallback is indistinguishable from a valid empty inbox.
- **Fix:** Preserve retrieval success/error separately for this action. On retrieval failure, show a warning and do not claim there are no unread messages; retain fail-soft behavior for unrelated rendering paths.
- **Verify:** Test empty inbox, unread inbox, and injected message-read failure; only a successfully read empty inbox reports no unread messages.

### 21. Shared safe-call logs lack operation context
- **Files:** ten screens listed in `AUDIT_QUALITY_2026-10-08.md`
- **Severity:** Minor
- **Lines:** source audit locations at `standings.py:38–43`, `finances.py:62–67`, `trades.py:62–67`, `roster.py:33–38`, `watch.py:51–56`, `schedule.py:30–35`, `draft.py:55–60`, `inbox.py:48–53`, `scouting.py:55–60`, `tactics.py:46–51`
- **What's wrong:** The local wrappers were consolidated, but the proposed `context=` labels are not passed at call sites.
- **Root cause:** Central helper adoption did not provide operation-specific diagnostic context.
- **Fix:** Use `native_ui.safe.safe_call` everywhere and add stable screen/action labels to failure-prone calls. Do not reintroduce local `_safe` wrappers.
- **Verify:** Inject one failing operation per representative screen and confirm logs name the screen/action and include the traceback.

### 22. Hub and application-shell methods remain oversized
- **File:** `native_ui/main_window.py`
- **Severity:** Minor
- **Lines:** 848–939, 1825–1982, 2563–2702, 2753–2896
- **What's wrong:** Hub refresh, screen registration, blocker handling, and menu construction remain large and multi-responsibility.
- **Root cause:** Construction helpers were extracted, but the requested orchestration boundaries were not completed.
- **Fix:** Split refresh into summary/next-game/panels/ticker helpers; screen registration into categorized registries; blocker selection from action dispatch; menus by menu/section. Preserve existing behavior and entry points.
- **Verify:** Compare screen registry keys and navigation behavior before/after; run hub refresh and blocker/menu smoke tests.

### 23. Long screen methods remain concentrated
- **Files:** `native_ui/screens/scouting.py`, `native_ui/screens/inbox.py`, `native_ui/screens/schedule.py`, `native_ui/screens/free_agents.py`
- **Severity:** Minor
- **Lines:** scouting 531–680; inbox 1196–1207 (already improved; verify no regression); schedule 218–361; free agents 678–816 and 1331–1436
- **What's wrong:** Several builders/actions still mix UI construction, validation, business decisions, and rendering.
- **Root cause:** Extraction was partial and uneven.
- **Fix:** Extract purpose-specific helpers for UI sections and workflow stages. Keep public entry points as orchestration; do not change transaction behavior while refactoring.
- **Verify:** Run existing screen smoke tests and compare relevant state/results before and after.

### 24. Scouting assignment selector hides prospects
- **File:** `native_ui/screens/scouting.py`
- **Severity:** Minor
- **Lines:** 55–56, 97–102, 115–119
- **What's wrong:** The named 200-player cap still truncates the flat selector without visible count or notice.
- **Root cause:** Naming the cap did not solve the missing-prospect/searchability problem.
- **Fix:** Prefer searchable/paged selection with matching count and selection preservation; if a product cap remains, show it explicitly and explain the cap.
- **Verify:** Assign a scout to a prospect beyond the first 200 and confirm selection survives filter changes.

### 25. Contract UI market caps are only partly centralized
- **File:** `native_ui/screens/contract_negotiation.py`
- **Severity:** Minor
- **Lines:** 30–37, 103–144, 487–488
- **What's wrong:** Constants drive widget ranges, but seed values still hardcode caps and the values are not sourced from engine validation rules.
- **Root cause:** UI constants were introduced without tracing policy ownership.
- **Fix:** Confirm valid term/AAV/bonus limits in offer validation and source shared constants from the canonical rules; replace remaining literals with those constants.
- **Verify:** Test boundary values and a valid offer above the prior UI ceiling when the engine permits it.

### 26. Contract outcome wording is inconsistent
- **Files:** `native_ui/screens/free_agents.py`, `native_ui/screens/contracts.py`, `native_ui/screens/contract_negotiation.py`
- **Severity:** Minor
- **Lines:** free agents 989–1001; contracts 1310–1326, 1373–1398; negotiation 40–54
- **What's wrong:** Shared wording is used in some flows, but extension outcomes still have separate wording and counter/pending free-agent outcomes close the panel before status is shown there.
- **Root cause:** Outcome mapping was not adopted by every contract flow/surface.
- **Fix:** Use one shared outcome classifier/text map for all offer paths. Display accepted, countered, awaiting, consideration, and rejected states in the originating panel; “Signed” must mean accepted only.
- **Verify:** Exercise each engine status through free-agent, extension, and negotiation surfaces; assert equivalent classification and accurate text.

### 27. Inbox Important control lacks accessible checked state
- **File:** `native_ui/screens/inbox.py`
- **Severity:** Minor
- **Lines:** 644–650, 729–741
- **What's wrong:** The control toggles and shows visual feedback but not a checked/accessibility state.
- **Root cause:** Visual state was implemented without semantic state for assistive technology.
- **Fix:** Use a checkable control or equivalent accessible state, update it with the message model, and keep the label/icon synchronized.
- **Verify:** Toggle twice and inspect checked state, accessible name/state, and persisted message importance.

### 28. Trade builder filters omit selected asset counts
- **File:** `native_ui/screens/trades.py`
- **Severity:** Minor
- **Lines:** 609–649, 943–953, 1031–1041
- **What's wrong:** Search and selection preservation exist, but displayed counts describe retention slots rather than selected trade assets.
- **Root cause:** The visible count is attached to the wrong quantity.
- **Fix:** Add selected player/pick counts per side, update after toggles and filtering, and keep filters from changing selected assets.
- **Verify:** Select multiple assets, filter them out of view, and assert selected counts and final offer remain unchanged.

### 29. Free-agent pending outcomes leave the originating panel
- **File:** `native_ui/screens/free_agents.py`
- **Severity:** Minor
- **Lines:** 799, 989–997
- **What's wrong:** “Submit Offer” and accepted wording are corrected, but counter/pending outcomes hand off to another dialog and close the offer panel.
- **Root cause:** Status reporting is not kept in the initiating panel.
- **Fix:** Keep the panel open and render the shared result status there; only close after a confirmed accepted signing or explicit user dismissal.
- **Verify:** Simulate accepted, countered, awaiting, consideration, and rejected outcomes; each must show the correct state in the same panel.

### 30. League schedule cannot filter opponent/team
- **File:** `native_ui/screens/schedule.py`
- **Severity:** Minor — missing
- **Lines:** 383–408, 451–457
- **What's wrong:** League tab filters by month but not by team/opponent.
- **Root cause:** The league view lacks searchable fixture filtering.
- **Fix:** Add searchable team/opponent filtering across scheduled games and results, with a clear reset action.
- **Verify:** Filter both future matchups and completed results by home/away team; reset restores all month results.

### 31. Draft trade action does not describe or carry its context
- **File:** `native_ui/screens/draft_central.py`
- **Severity:** Minor
- **Lines:** 64–68, 154–160
- **What's wrong:** The button says “Trade This Pick” but opens generic Trades without carrying the current pick.
- **Root cause:** Navigation destination and label imply a flow that is not initialized.
- **Fix:** Prefer a trade-up flow initialized with current pick and partner; if unavailable, rename the action to describe generic trade navigation.
- **Verify:** The label matches the destination; if trade-up exists, verify current pick is preselected.

## Regressions

1. **Major:** Three Systems pages fail construction because `systems_nav_bar` is not imported.
2. **Major:** Lineup duplicate guard rejects legitimate PP/PK reuse.
3. **Minor:** Mark-all-read can report no unread messages after retrieval failure.

## Verdict

The branch is not ready to call the Oct. 8 audits fully resolved: 31 of 55 classifications remain partial or missing, and three regressions were identified. Resolve the regressions first, then the engine-state and transaction issues, and finally the UX/maintainability gaps. Runtime checks are required before closure; this document records source-review evidence only.
