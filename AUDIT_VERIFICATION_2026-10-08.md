# Fix Verification — 2026-10-08

Compared both audit specifications on `origin/copilot/audit-native-ui` with `origin/native-ui` at `4a6d5f6623a7f375e04d576bae12e8b20fb23ccf`. Findings audit baseline: `31f2995`; quality audit baseline: `333caa9`. This is a source review; no runtime tests were performed.

## Summary
- Matches: 24/55
- Partial: 29
- Missing: 2
- Better: 0
- Regressions: 3
- New issues: 1

## Results by issue

### AUDIT_FINDINGS

#### `season_flow.py`
### AUDIT_FINDINGS Issue 1 (season_flow.py)
- **Status:** MATCHES
- **Evidence:** `season_flow.py:441` now tests `_safe(auto.should_auto_advance, False)` without calling its Boolean result.

#### `watch.py`
### AUDIT_FINDINGS Issue 1 (watch.py)
- **Status:** PARTIAL
- **Evidence:** `watch.py:465–489` records the game and updates standings through `_update_standings_fast`.
- **Gap:** Watched state is written only for dictionary schedule entries (`watch.py:419–435`); tuple entries may be simulated again by day advance.

#### `waivers.py`
### AUDIT_FINDINGS Issue 1 (waivers.py)
- **Status:** PARTIAL
- **Evidence:** `waivers.py:237–258` sets a pending-claim flag and tells the user the claim will be processed by priority.
- **Gap:** It sets only `user_claim_pending`; non-host human-managed claims also require the `mp_claim_teams` marker processed by `game_manager.py:9439–9449`.

#### `roster.py`
### AUDIT_FINDINGS Issue 1 (roster.py)
- **Status:** PARTIAL
- **Evidence:** `roster.py:918–938` routes waiver-eligible demotions through waiver placement and moves exempt players directly.
- **Gap:** An eligibility lookup/import failure defaults to “not eligible,” allowing a direct demotion that bypasses waivers.

### AUDIT_FINDINGS Issue 2 (roster.py)
- **Status:** PARTIAL
- **Evidence:** `roster.py:873–877` applies a capacity check to moves into the NHL roster.
- **Gap:** It uses `len(team.roster)` rather than `roster_limits.active_roster_count()`, so IR/LTIR, waivers, emergency fillers, and inactive contracts can produce false rejections.

### AUDIT_FINDINGS Issue 3 (roster.py)
- **Status:** PARTIAL
- **Evidence:** `roster.py:970–974` uses `Team.remove_player` and `Team.add_player` instead of directly editing the user team's lists.
- **Gap:** It does not synchronize a separate affiliate `farm_team.roster`.

### AUDIT_FINDINGS Issue 4 (roster.py)
- **Status:** MATCHES
- **Evidence:** `roster.py:750–764` opens Contracts with `set_player(player, elc=elc)`, retaining both the selected player and offer mode.

#### `lines.py`
### AUDIT_FINDINGS Issue 1 (lines.py)
- **Status:** PARTIAL
- **Evidence:** `lines.py:656–707` checks duplicate player assignments during selection and again before save.
- **Gap:** `_find_dressed_slot()` scans every tab (`lines.py:459–473`), rejecting valid reuse between separately deployed power-play and penalty-kill units.

### AUDIT_FINDINGS Issue 2 (lines.py)
- **Status:** MATCHES
- **Evidence:** `lines.py:187–190,746–750,812–813` adds G2 and saves/restores it using the engine's lineup representation.

#### `scouting.py`
### AUDIT_FINDINGS Issue 1 (scouting.py)
- **Status:** MATCHES
- **Evidence:** `scouting.py:115–127` populates the scout and prospect selectors separately and stores the selected objects as combo data.

#### `player_table.py`
### AUDIT_FINDINGS Issue 1 (player_table.py)
- **Status:** MATCHES
- **Evidence:** `player_table.py:60–65,108–119` resolves the selected player from the displayed name-column item for both row actions.

#### `contracts.py`
### AUDIT_FINDINGS Issue 1 (contracts.py)
- **Status:** MATCHES
- **Evidence:** `contracts.py:595–639,683–712` snapshots staged terms and restores them after exceptions or any result that is not an accepted signing.

#### `schedule.py`
### AUDIT_FINDINGS Issue 1 (schedule.py)
- **Status:** PARTIAL
- **Evidence:** `schedule.py:321–345` records the result and calls the canonical standings updater rather than manually duplicating team-record updates.
- **Gap:** The schedule path still constructs its own partial result, including empty `player_ratings` (`schedule.py:301–320`), instead of reusing the complete normal postgame processing path.

#### `tactics.py`
### AUDIT_FINDINGS Issue 1 (tactics.py)
- **Status:** PARTIAL
- **Evidence:** `tactics.py:585–603,869–883` uses the coach-suggestion flow when the reputation system is available.
- **Gap:** If `_rs` is unavailable, the screen falls back to `set_team_system` even when coach control is the default.

### AUDIT_FINDINGS Issue 2 (tactics.py)
- **Status:** MATCHES
- **Evidence:** `tactics.py:1177` labels the action “Set Weekly Practice Plan,” accurately describing that it saves a plan.

#### `morale.py`
### AUDIT_FINDINGS Issue 1 (morale.py)
- **Status:** PARTIAL
- **Evidence:** `morale.py:1039–1059` disables editing and derives rivalry and streak context.
- **Gap:** `_talk_derived_context()` defaults the score to tied (`morale.py:1107–1108,1140–1143`) instead of deriving the live intermission score.

#### `.github/workflows/build-native.yml`
### AUDIT_FINDINGS Issue 1 (build-native.yml)
- **Status:** PARTIAL
- **Evidence:** `build-native.yml:101–167` checks discovered source modules against the expected set and fails for missing modules.
- **Gap:** The PyInstaller TOC is checked only when expected source modules are missing (`:129–147`); an extra bundled module is not rejected when all expected modules are present.

#### `contract_negotiation.py`
### AUDIT_FINDINGS Issue 1 (contract_negotiation.py)
- **Status:** PARTIAL
- **Evidence:** `contract_negotiation.py:227–235,248–285` submits ELC bonuses through `handle_elc_offer` and hides bonus controls for standard offers.
- **Gap:** The clause control remains visible for ELCs (`:128–132`), but the ELC submission path does not send the clause.

#### `main_window.py`
### AUDIT_FINDINGS Issue 1 (main_window.py)
- **Status:** MATCHES
- **Evidence:** `main_window.py:2145–2160` runs simulation through `run_threaded` and refreshes after worker completion; `:2186–2202` marshals worker notifications to the UI thread.

### AUDIT_FINDINGS Issue 2 (main_window.py)
- **Status:** MATCHES
- **Evidence:** `main_window.py:1593–1597` reads goals and assists from `p.stats` rather than legacy player fields.

### AUDIT_FINDINGS Issue 3 (main_window.py)
- **Status:** MATCHES
- **Evidence:** `main_window.py:1492–1495` substitutes the default only for `None`, preserving a morale value of zero.

### AUDIT_FINDINGS Issue 4 (main_window.py)
- **Status:** PARTIAL
- **Evidence:** `main_window.py:1376–1387` uses overtime/shootout metadata rather than inferring OTL from score margin.
- **Gap:** The hub does not reliably join result metadata onto schedule entries; watched games store `watched_*_score` rather than the score/overtime fields this display reads (`watch.py:432–435`).

### AUDIT_FINDINGS Issue 5 (main_window.py)
- **Status:** MATCHES
- **Evidence:** `main_window.py:977–995` ranks goals-for and goals-against per game and handles teams with zero games played.

### AUDIT_FINDINGS Issue 6 (main_window.py)
- **Status:** PARTIAL
- **Evidence:** `main_window.py:1063–1067` includes games dated today when the schedule entry is not marked played.
- **Gap:** `_sched_played()` checks only the entry's `played` field (`:789–790`), not watched markers or separately recorded results, so completed-today games may still appear.

### AUDIT_FINDINGS Issue 7 (main_window.py)
- **Status:** MATCHES
- **Evidence:** `main_window.py:1664–1675` reads response and urgency flags from either dictionary-backed or object-backed messages.

### AUDIT_FINDINGS Issue 8 (main_window.py)
- **Status:** PARTIAL
- **Evidence:** `main_window.py:938–945` now orders tied teams consistently with the standings screen.
- **Gap:** The hub reimplements that sort tuple instead of calling a shared canonical standings-sort API.

### AUDIT_FINDINGS Issue 9 (main_window.py)
- **Status:** PARTIAL
- **Evidence:** `main_window.py:1991–2022` maps screens to top-bar state and updates the selection for mapped screens.
- **Gap:** Unmapped screens retain the prior selection, and `roster`/`lines` map to lowercase names rather than the available CLUB button.

#### `trade_block.py`
### AUDIT_FINDINGS Issue 1 (trade_block.py)
- **Status:** PARTIAL
- **Evidence:** `trade_block.py:775–804` preloads team/player context for Interest rows.
- **Gap:** The Other Teams action also calls this handler (`:830–832`), but it reads `_interest_row()` instead of the selected `_other_rows` entry.

#### `widgets/context_menu.py`
### AUDIT_FINDINGS Issue 1 (context_menu.py)
- **Status:** PARTIAL
- **Evidence:** `context_menu.py:170–187` passes the clicked entity to `set_teams` to initialize the trade screen.
- **Gap:** A player on the user's own team resolves as the trade partner (`trades.py:1942–1957,1977–1985`), despite not being a selectable partner.

#### `shortlist.py`
### AUDIT_FINDINGS Issue 1 (shortlist.py)
- **Status:** MATCHES
- **Evidence:** `shortlist.py:168–189,245–270` saves `id` and resolves stringified IDs across team rosters, free agents, and draft prospects.

#### `requirements.txt`
### AUDIT_FINDINGS Issue 1 (requirements.txt)
- **Status:** MATCHES
- **Evidence:** `requirements.txt` pins `PySide6==6.12.0`, matching the native build workflow's version.

#### `puck_dynasty_native.py`
### AUDIT_FINDINGS Issue 1 (puck_dynasty_native.py)
- **Status:** PARTIAL
- **Evidence:** `puck_dynasty_native.py:6–9,23–24` documents installing native dependencies.
- **Gap:** It directs users to `requirements-native.txt`, which does not exist in the target tree; only `requirements.txt` is present.

### AUDIT_QUALITY

Issue numbers below are assigned in audit order across the redundancy, dead-code, code-quality, and player-experience sections.

#### Redundancies
### AUDIT_QUALITY Issue 1 — Shared safe-call wrapper
- **Status:** PARTIAL
- **Evidence:** `native_ui/safe.py:13–24` centralizes the wrapper and the ten audited screens import it.
- **Gap:** Calls omit the proposed screen/action `context`, so logs do not identify the failing screen or operation.

### AUDIT_QUALITY Issue 2 — Systems scroll helper
- **Status:** PARTIAL
- **Evidence:** `systems_common.py:135–151` adds the helper and all three Systems pages call it.
- **Gap:** Each page also calls `systems_nav_bar()` without importing it; construction raises `NameError` (see regressions).

### AUDIT_QUALITY Issue 3 — Context-menu entity-screen helper
- **Status:** MATCHES
- **Evidence:** `context_menu.py:127–203` centralizes navigation/setter handling and reports wrapper failures with warnings.

### AUDIT_QUALITY Issue 4 — Attribute-bar stylesheet
- **Status:** MATCHES
- **Evidence:** `attribute_bar.py:21–36,54–55,65–68` centralizes stylesheet creation/application for initialization and updates.

#### Dead code
### AUDIT_QUALITY Issue 5 — Unused spec import
- **Status:** MATCHES
- **Evidence:** `puck_dynasty_native.spec:5,17` no longer imports `collect_submodules`.

### AUDIT_QUALITY Issue 6 — Unused `Qt` import in `systems_discipline.py`
- **Status:** MATCHES
- **Evidence:** `systems_discipline.py:9–15` omits the unused `Qt` import.

### AUDIT_QUALITY Issue 7 — Unused `Qt` import in `systems_condition.py`
- **Status:** MATCHES
- **Evidence:** `systems_condition.py:7–15` omits the unused `Qt` import.

#### Other code-quality findings
### AUDIT_QUALITY Issue 8 — Oversized circumstance refresh
- **Status:** MATCHES
- **Evidence:** `systems_circumstance.py:100–296` extracts context, game, row, and table work into helpers, leaving `refresh()` to orchestrate.

### AUDIT_QUALITY Issue 9 — Per-player diagnostics
- **Status:** MATCHES
- **Evidence:** `systems_circumstance.py:245–252` logs invalid conversions and unexpected per-player exceptions with the player ID.

### AUDIT_QUALITY Issue 10 — Hub and shell method sizes
- **Status:** PARTIAL
- **Evidence:** `main_window.py:208,293,378,415` splits Hub construction into focused helpers.
- **Gap:** `refresh()`, screen registration, blockers, and menu construction remain large methods (`:848–939,1825–1982,2563–2702,2753–2896`); the requested decomposition is incomplete.

### AUDIT_QUALITY Issue 11 — Long screen methods
- **Status:** PARTIAL
- **Evidence:** `inbox.py:1196–1207` reduces `_actions_gameday()` to orchestration.
- **Gap:** The scouting body, missed-game simulation, and free-agent constructor/body remain at or above the audited lengths (`scouting.py:531–680`; `schedule.py:218–361`; `free_agents.py:678–816,1331–1436`).

### AUDIT_QUALITY Issue 12 — Magic prospect limit
- **Status:** PARTIAL
- **Evidence:** `scouting.py:55–56` names the 200-player cap.
- **Gap:** `_load_options()` still truncates at 200 without a visible count/notice or searchable/paged selection (`:115–119`).

### AUDIT_QUALITY Issue 13 — Contract market limits
- **Status:** PARTIAL
- **Evidence:** `contract_negotiation.py:30–37,103–144` centralizes and applies contract-term widget limits.
- **Gap:** Seeding still hardcodes the term/AAV caps (`:487–488`), and the UI limits are not sourced from engine validation rules.

### AUDIT_QUALITY Issue 14 — Context-menu error reporting
- **Status:** MATCHES
- **Evidence:** `context_menu.py:127–203` routes the entity-screen actions through a helper and displays failures as warnings.

### AUDIT_QUALITY Issue 15 — Contract-offer outcome wording
- **Status:** PARTIAL
- **Evidence:** `contract_negotiation.py:40–54` defines shared outcome text used by negotiation and free-agent acceptance/rejection flows.
- **Gap:** Extension outcomes in `contracts.py:1310–1326,1373–1398` still use separate wording.

#### Player-experience issues
### AUDIT_QUALITY Issue 16 — Scouting assignment search
- **Status:** MISSING
- **Evidence:** `scouting.py:97–102,115–119` still uses a flat combo and caps the prospect list at 200.
- **Gap:** No searchable/paged selector, matching count, or filter-preserved selection is present.

### AUDIT_QUALITY Issue 17 — Inbox Important control
- **Status:** PARTIAL
- **Evidence:** `inbox.py:644–650,729–741` enables the row control and toggles importance with visual feedback.
- **Gap:** It does not expose a checked or accessible state.

### AUDIT_QUALITY Issue 18 — Mark all read feedback
- **Status:** MATCHES
- **Evidence:** `inbox.py:695–727` confirms the action, reports the number changed, and shows an actionable failure; the model provides no undo operation (`game_classes.py:3477–3482`).

### AUDIT_QUALITY Issue 19 — Trade asset filters
- **Status:** PARTIAL
- **Evidence:** `trades.py:609–649,943–953` adds search to all four asset lists and preserves checked assets while filtering.
- **Gap:** No selected-asset count is shown; the labels at `:1031–1041` count retention slots instead.

### AUDIT_QUALITY Issue 20 — Free-agent offer wording
- **Status:** PARTIAL
- **Evidence:** `free_agents.py:799,989–993` says “Submit Offer” and reserves “Signed” for acceptance.
- **Gap:** Counter/pending outcomes hand off to another dialog and close the offer panel (`:994–997`) rather than displaying status in the same panel.

### AUDIT_QUALITY Issue 21 — League schedule filter
- **Status:** MISSING
- **Evidence:** `schedule.py:383–408,451–457` provides month and user-team filters only.
- **Gap:** No searchable team/opponent filter or clear/reset control is present.

### AUDIT_QUALITY Issue 22 — Draft pick trade navigation
- **Status:** PARTIAL
- **Evidence:** `draft_central.py:64–68,154–160` opens Trades and has a tooltip describing the destination.
- **Gap:** The button still says “Trade This Pick” and does not pass the current pick or partner to a trade-up flow.

### AUDIT_QUALITY Issue 23 — Context-menu trade preselection
- **Status:** MATCHES
- **Evidence:** `context_menu.py:60–62,108–110,170–191` passes player/team context and preselects the clicked entity through `set_teams`.

## Regressions
1. **Systems page construction fails** in `systems_discipline.py:12–25`, `systems_condition.py:12–30`, and `systems_circumstance.py:19–45`: all three call `systems_nav_bar()` but no longer import it. The scroll-helper refactor therefore breaks all three screens.
2. **Valid player reuse across non-simultaneous units is rejected** by `lines.py:459–473,656–707`: the new duplicate guard scans all tabs, including separate PP/PK units.
3. **Mark-all-read can falsely report “No unread messages”** in `inbox.py:77–80,695–708`: `_all_messages()` converts retrieval exceptions to an empty list, which the handler treats as proof there are no unread messages.

## New issues
1. `puck_dynasty_native.py:23–24` directs users to install `requirements-native.txt`, but that file is absent from `origin/native-ui`; the documented installation path is unusable.

## Verdict
The work is not yet acceptable against the audit specifications: only 24 of 55 fixes match, 29 are partial, and two player-experience fixes are missing. The three regressions must be corrected, the launcher dependency instructions must point to an existing requirements file, and the remaining partial gaps should be resolved before treating the audits as complete.
