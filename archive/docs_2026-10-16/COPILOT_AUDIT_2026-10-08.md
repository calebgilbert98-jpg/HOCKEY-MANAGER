# Native UI Audit Findings — 2026-10-08

Audited `native-ui` at `31f299513e15fa9f890321e7a662a619f4a2ad38`, comparing sampled native screens with `web-ui` at `16764826d24c24c2b158ac0ce7282ec1deb48a28` and checking relevant engine paths. Source review only; no runtime audit was performed.

| Severity | Count |
| --- | ---: |
| Critical | 0 |
| Major | 17 |
| Minor | 15 |
| **Total** | **32** |
| **Files affected** | **19** |

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/season_flow.py`

**Issue 1: Auto-advance calls a Boolean as a function**
- **Severity:** Major
- **Lines:** 435–445
- **Current code:**
  ```python
  if not _safe(auto.should_auto_advance, False)():
  ```
- **Root cause:** `_safe` invokes the predicate and returns its Boolean result. The trailing call raises `TypeError`; the timer’s error handling stops automation.
- **Fix:**
  ```python
  if not _safe(auto.should_auto_advance, False):
  ```
- **Verify:** `python3 -m compileall -q /home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/season_flow.py`; then test that a timer tick with `should_auto_advance()` returning `True` does not stop the timer.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/watch.py`

**Issue 1: Watched games miss standings and team-record updates**
- **Severity:** Major
- **Lines:** 413–479
- **Current code:**
  ```python
  rec = getattr(game, "_record_game_result", None)
  if callable(rec):
      rec(result)
  else:
      gr = getattr(game, "game_results", None)
      if isinstance(gr, list):
          gr.append(result)
  ```
- **Root cause:** This records the result and marks the schedule entry watched, but does not apply the normal standings/team-record processing. Day simulation skips watched entries, so this path must perform the omitted postgame side effects.
- **Fix:** **NEEDS-RESEARCH:** Find the canonical postgame result-processing method called by the normal day-simulation path. Call that method here, and retain `_record_game_result` only if it is not already included in the canonical processing. Do not guess the method name or manually duplicate its standings rules.
- **Verify:** Add a regression test that watches a scheduled game and asserts the game is recorded once, both teams’ standings/records update once, and continuing the day does not simulate or count it again.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/waivers.py`

**Issue 1: Claim action executes a waiver transfer immediately**
- **Severity:** Major
- **Lines:** 184–203
- **Current code:**
  ```python
  game._execute_waiver_claim(player, team)
  ```
- **Root cause:** This transfer primitive bypasses pending-claim submission and priority resolution. A lower-priority user team can acquire a player before higher-priority claims are considered.
- **Fix:** **NEEDS-RESEARCH:** Identify the canonical API used to submit a user claim to the pending-claims queue, including its expected return/status shape. Replace the immediate transfer with that submission API and show a pending-claim result in the UI.
- **Verify:** Add a test with two claiming teams of different priority; clicking Claim must queue the user’s claim, and only the priority-resolution step may transfer the player.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/roster.py`

**Issue 1: NHL-to-AHL move bypasses waiver rules**
- **Severity:** Major
- **Lines:** 817–891
- **Current code:**
  ```python
  # NHL-to-AHL move is performed directly in the roster-move handler.
  ```
- **Root cause:** The direct move does not check waiver eligibility, placement/claim processing, or applicable consent restrictions. It bypasses the waiver screen’s eligibility and transaction checks.
- **Fix:** **NEEDS-RESEARCH:** Determine the canonical demotion/waiver-placement API and its result shape. Route eligible players through that flow; only move non-waiver-eligible players directly through the roster API.
- **Verify:** Test one waiver-eligible and one waiver-exempt player. The eligible player must enter the waiver process; the exempt player must move successfully.

**Issue 2: AHL call-up can exceed the 23-player active-roster limit**
- **Severity:** Major
- **Lines:** 817–891
- **Current code:**
  ```python
  # The active-roster limit check is only performed inside the
  # is_promotion branch; an AHL-to-NHL move does not satisfy that test.
  ```
- **Root cause:** The roster limit check is conditional on the wrong move classification, allowing a call-up to push the active roster over its limit.
- **Fix:** **NEEDS-RESEARCH:** Verify the engine’s canonical active-roster count and eligibility API, then run its check for every move whose destination is the NHL roster, before mutating state.
- **Verify:** Test an AHL call-up with 22 active players (must pass) and with 23 active players (must be rejected without changing either roster).

**Issue 3: Direct roster-list edits bypass roster side effects**
- **Severity:** Major
- **Lines:** 817–891
- **Current code:**
  ```python
  # Move handler directly removes/appends players in roster lists.
  ```
- **Root cause:** Direct list mutation skips `Team.remove_player` / `Team.add_player` side effects, including team-name and season-history updates; it can also leave the farm team’s roster stale.
- **Fix:** **NEEDS-RESEARCH:** Review `Team.add_player` / `Team.remove_player` behavior and the canonical affiliate synchronization path, then replace list mutations with those APIs. Ensure both parent and affiliate rosters remain consistent.
- **Verify:** After a move in each direction, assert roster membership, `team_name`, season-history/stint state, and affiliate roster membership are all correct.

**Issue 4: Contract context actions lose the selected player**
- **Severity:** Minor
- **Lines:** 700–765
- **Current code:**
  ```python
  menu.addAction("Contract Extension",
                 lambda: self._open_contracts(player))
  ...
  menu.addAction("Offer ELC",
                 lambda: self._open_contracts(player, elc=True))
  ...
  def _open_contracts(self, player, elc=False):
      self.navigate_to("contracts")
  ```
- **Root cause:** The handler receives the selected player and ELC mode but discards both during navigation.
- **Fix:** **NEEDS-RESEARCH:** Confirm the Contracts screen’s supported deep-link method and navigation parameter mechanism. Pass the selected player and ELC/extension mode through that mechanism rather than only calling `navigate_to`.
- **Verify:** From a roster context menu, invoke Extension and ELC for a selected player; each must open the correct flow for that player.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/lines.py`

**Issue 1: Duplicate player assignments are allowed**
- **Severity:** Major
- **Lines:** 481–644
- **Current code:**
  ```python
  # Player selection and save write the slot map without checking
  # whether the player already occupies another deployed slot.
  ```
- **Root cause:** The same player can be assigned to multiple simultaneously deployed slots, and the engine reads each slot independently.
- **Fix:** **NEEDS-RESEARCH:** Confirm which slots are simultaneously deployed and which duplicate assignments, if any, the engine permits. Enforce that rule both when selecting a player and immediately before saving.
- **Verify:** Attempt to assign one player to two deployed slots; the second selection and a tampered save must both be rejected.

**Issue 2: Backup-goalie assignment is missing**
- **Severity:** Major
- **Lines:** 156–180
- **Current code:**
  ```python
  # Line 1 defines G1 but has no G2 slot.
  ```
- **Root cause:** Unlike the web line editor, the native editor cannot assign the backup goalie.
- **Fix:** **NEEDS-RESEARCH:** Confirm the lineup key and goalie-slot representation consumed by the engine, then add the matching G2 slot using the web editor’s equivalent behavior.
- **Verify:** Assign a backup goalie in the native editor, save, reopen, and assert the engine’s lineup contains that player in the expected G2 slot.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/scouting.py`

**Issue 1: Scout selector is never populated**
- **Severity:** Major
- **Lines:** 93–98, 113–134
- **Current code:**
  ```python
  # Staff-loading loop adds scout entries to _prospect_combo.
  ```
- **Root cause:** Scouts are inserted into the prospect selector instead of `_scout_combo`, leaving the scout selection empty and preventing assignment submission.
- **Fix:** **NEEDS-RESEARCH:** Confirm the option data/value representation expected by `get_selection()`. Populate `_scout_combo` with staff and keep prospect entries in `_prospect_combo`.
- **Verify:** Open the assignment dialog with at least one prospect and scout; assert both selectors contain their respective options and a valid selection is returned.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/widgets/player_table.py`

**Issue 1: Sorting makes row actions target the wrong player**
- **Severity:** Major
- **Lines:** 29–31, 49–69, 71–79, 102–104
- **Current code:**
  ```python
  player = self._players[row]
  ...
  self.player_clicked.emit(self._players[row])
  ```
- **Root cause:** Sorting changes displayed row order, but the handlers use the original unsorted `_players` list.
- **Fix:** Replace both row lookups with the player reference stored in the name-column item:
  ```python
  item = self.item(row, 0)
  player = item.data(Qt.UserRole + 1) if item is not None else None
  if player is None:
      return
  ```
  In `_on_double_click`, emit that `player`; in `_on_context_menu`, use it for the context menu.
- **Verify:** Sort the table by a non-name column, then double-click and open the context menu on a row; assert both actions receive the player shown in that row.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/contracts.py`

**Issue 1: Rejected or countered offers leave staged terms on the player**
- **Severity:** Major
- **Lines:** 615–656
- **Current code:**
  ```python
  player.salary = int(aav)
  player.contract_years = int(years)
  ...
  result = game.handle_contract_offer(
      player, extension=(kind == "extend"), notify="inbox")
  ...
  _safe(lambda: _apply_offer_verdict(game, st, result))
  ```
- **Root cause:** Offer terms are staged on the player before the engine call and are not restored when the offer is countered, rejected, or the call raises. Clause and signing-bonus staging can also leak.
- **Fix:** **NEEDS-RESEARCH:** Confirm the exact signed/accepted result statuses and all staged attribute names consumed by the engine. Snapshot every staged attribute before mutation and restore them on exceptions and every result that is not a completed signing.
- **Verify:** Test accepted, countered, rejected, and exception outcomes; only the accepted case may retain the new contract terms.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/schedule.py`

**Issue 1: Missed-game simulation bypasses normal result processing**
- **Severity:** Major
- **Lines:** 224–359
- **Current code:**
  ```python
  game_result = {
      ...
      "player_ratings": {},
      ...
  }
  ...
  rec = getattr(game, "_record_game_result", None)
  if callable(rec):
      rec(game_result)
  ...
  home_team.update_record(...)
  away_team.update_record(...)
  ```
- **Root cause:** The path manually records a partial result and team records instead of using canonical postgame processing, so standings/league-derived state and result metadata can diverge. `GameSim.run()` does update player season stats; those are not the missing side effect.
- **Fix:** **NEEDS-RESEARCH:** Identify and use the canonical game-result processing API used by normal day simulation. Avoid manually applying records if that API already does so.
- **Verify:** Simulate a past unplayed game, then assert the result, league standings, team records, and derived indexes update exactly once.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/tactics.py`

**Issue 1: System changes bypass coach ownership consequences**
- **Severity:** Major
- **Lines:** 460–510
- **Current code:**
  ```python
  tactics.set_team_system(team, category, key)
  ```
- **Root cause:** The screen changes the team system directly instead of using the coach-ownership suggest/enforce/takeover flow, bypassing intended reputation and trust consequences.
- **Fix:** **NEEDS-RESEARCH:** Confirm the canonical reputation-system action for coach-owned system changes and its return shape. Route native module changes through that API; do not directly call `set_team_system` when the coach controls the whiteboard.
- **Verify:** Test coach-owned and GM-owned systems; the former must follow the ownership decision flow and apply its normal consequences.

**Issue 2: “Set & Run Practice” only saves a plan**
- **Severity:** Minor
- **Lines:** 1156–1201
- **Current code:**
  ```python
  dr["practice_plan"] = plan
  ```
- **Root cause:** The button says “Run,” but this handler only stores a future weekly plan; it does not execute practice immediately.
- **Fix:**
  ```python
  save = QPushButton("Set Weekly Practice Plan")
  ```
- **Verify:** `python3 -m compileall -q /home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/tactics.py`; confirm the button saves the plan and does not claim immediate execution.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/morale.py`

**Issue 1: Team Talk accepts fabricated game context**
- **Severity:** Major
- **Lines:** 1380–1570
- **Current code:**
  ```python
  # Editable score state, rivalry status, and streak are passed to give_talk.
  ```
- **Root cause:** The engine uses these caller-provided values in tone/outcome calculations without verifying them against game state, allowing the user to fabricate advantageous context.
- **Fix:** **NEEDS-RESEARCH:** Identify canonical sources and representations for score state, rivalry, and streak. Derive those values from game state and disable editing; do not pass user-entered substitutes to `give_talk`.
- **Verify:** Altering widget values must not change the engine inputs; inputs must match the current game/standings state.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/.github/workflows/build-native.yml`

**Issue 1: Native bundle can ship with missing screen modules**
- **Severity:** Major
- **Lines:** 125–131
- **Current code:**
  ```python
  # If the screen count is below the threshold, the workflow warns;
  # the failure/exit is commented out.
  ```
- **Root cause:** A count threshold neither checks the complete expected module set nor fails the build. A missing screen import can prevent application startup.
- **Fix:** **NEEDS-RESEARCH:** Establish the authoritative expected native-screen module manifest, then make the workflow compare the discovered set to that manifest and fail on missing or unexpected modules. Do not guess the manifest from a count.
- **Verify:** Remove one expected screen from a temporary checkout and confirm the build-native validation step exits nonzero.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/contract_negotiation.py`

**Issue 1: Clause and bonus controls do not affect the offer**
- **Severity:** Major
- **Lines:** 195–350
- **Current code:**
  ```python
  self._player.salary = offer["aav"]
  self._player.contract_years = offer["years"]
  result = game.handle_contract_offer(
      self._player, extension=self._is_extension, notify="popup")
  ```
- **Root cause:** `_get_offer()` collects clause, signing-bonus, and performance-bonus values, but the counter and accept paths submit only salary and term.
- **Fix:** **NEEDS-RESEARCH:** Confirm which contract engine API accepts clauses and both bonus types, and which terms are valid for each contract type. Pass all supported values through that API and its validation; remove controls for unsupported terms rather than presenting them as applied.
- **Verify:** Submit a contract with each supported extra term and assert the resulting contract stores the exact accepted values.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/main_window.py`

**Issue 1: Day simulation blocks Qt’s UI thread**
- **Severity:** Major
- **Lines:** 2026–2058
- **Current code:**
  ```python
  if hasattr(self.game, "simulate_day"):
      self.game.simulate_day()
  ```
- **Root cause:** The synchronous simulation blocks event processing, so the loading overlay cannot animate or respond while the work runs.
- **Fix:** **NEEDS-RESEARCH:** Confirm game-state thread-safety and the application’s Qt worker/result-refresh pattern. Run simulation in a worker only if safe; marshal completion and UI refresh back to the main thread.
- **Verify:** Run a deliberately slow simulation and confirm the overlay animates and the window remains responsive until completion.

**Issue 2: Milestone panel reads legacy goal/assist fields**
- **Severity:** Minor
- **Lines:** 1520–1540
- **Current code:**
  ```python
  pts = (int(getattr(p, "goals", 0) or 0)
         + int(getattr(p, "assists", 0) or 0))
  ```
- **Root cause:** Season totals are authoritative in `p.stats`; legacy attributes can make milestone distances incorrect.
- **Fix:**
  ```python
  stats = getattr(p, "stats", None) or {}
  pts = int(stats.get("goals", 0) or 0) + int(stats.get("assists", 0) or 0)
  ```
- **Verify:** Test a player with goals/assists only in `stats`; the milestone panel must calculate the correct points distance.

**Issue 3: Zero morale is replaced by the default**
- **Severity:** Minor
- **Lines:** 1430–1453
- **Current code:**
  ```python
  mors = [float(getattr(p, "morale", 70) or 70) for p in roster]
  ```
- **Root cause:** `or 70` replaces a legitimate morale value of `0`.
- **Fix:**
  ```python
  mors = [
      float(70 if getattr(p, "morale", None) is None else p.morale)
      for p in roster
  ]
  ```
- **Verify:** Test a roster with morale values `0` and `70`; the average must preserve the zero.

**Issue 4: One-goal regulation losses are shown as OTL**
- **Severity:** Minor
- **Lines:** 1323–1330
- **Current code:**
  ```python
  wl = "W" if mine > theirs else ("OTL" if abs(mine - theirs) == 1 else "L")
  ```
- **Root cause:** Score margin does not establish whether the game went to overtime.
- **Fix:** **NEEDS-RESEARCH:** Confirm how schedule entries expose overtime/shootout results and use those fields to distinguish OTL from regulation loss.
- **Verify:** Test equal-margin regulation and overtime losses; only the overtime loss should display OTL.

**Issue 5: Offense/defense ranks sort total goals**
- **Severity:** Minor
- **Lines:** 923–955
- **Current code:**
  ```python
  _by_off = sorted(
      _teams, key=lambda t: getattr(t, "goals_for", 0) or 0,
      reverse=True)
  _by_def = sorted(
      _teams, key=lambda t: getattr(t, "goals_against", 0) or 0)
  ```
- **Root cause:** The panel displays per-game rates but ranks raw totals; teams with different games played are not comparable.
- **Fix:** **NEEDS-RESEARCH:** Confirm the authoritative games-played field for each team, then rank by goals-for per game descending and goals-against per game ascending, with defined handling for zero games.
- **Verify:** Test teams with different games played but equal per-game rates; rankings must use rates, not totals.

**Issue 6: “Next Game” omits unplayed games scheduled today**
- **Severity:** Minor
- **Lines:** 1002–1038
- **Current code:**
  ```python
  if today is not None and gd <= today:
      continue
  ```
- **Root cause:** The engine simulates games dated `current_date`, but the hub excludes games on that date.
- **Fix:** **NEEDS-RESEARCH:** Confirm how to distinguish an unplayed game dated today from one already completed. Include today’s game only when it remains unplayed.
- **Verify:** With an unplayed user-team game dated today, assert it appears as Next Game; a completed game must not.

**Issue 7: Inbox badges fail for dictionary messages**
- **Severity:** Minor
- **Lines:** 1577–1605
- **Current code:**
  ```python
  if getattr(m, "requires_response", False):
      prefix += "🔴 "
  if getattr(m, "is_urgent", False):
      prefix += "🟡 "
  ```
- **Root cause:** The panel handles dict-backed messages for subject/read state but uses attribute-only lookup for response and urgency.
- **Fix:**
  ```python
  requires_response = (
      m.get("requires_response", False) if isinstance(m, dict)
      else getattr(m, "requires_response", False)
  )
  is_urgent = (
      m.get("is_urgent", False) if isinstance(m, dict)
      else getattr(m, "is_urgent", False)
  )
  if requires_response:
      prefix += "🔴 "
  if is_urgent:
      prefix += "🟡 "
  ```
- **Verify:** Render equivalent object-backed and dict-backed messages with both flags set; both must show the same badges.

**Issue 8: Division ties use no league tiebreaker**
- **Severity:** Minor
- **Lines:** 903–912
- **Current code:**
  ```python
  def _pts(t):
      return (getattr(t, "wins", 0) or 0) * 2 + (getattr(t, "otl", 0) or 0)
  div_teams.sort(key=_pts, reverse=True)
  ```
- **Root cause:** Teams tied on points retain incidental input order rather than league standings order.
- **Fix:** **NEEDS-RESEARCH:** Identify the canonical league standings sort/tiebreak API and use it rather than reimplementing tie rules in the hub.
- **Verify:** Construct tied teams whose secondary tiebreakers differ; the hub’s rank must match the standings screen.

**Issue 9: Direct navigation leaves top-bar selection stale**
- **Severity:** Minor
- **Lines:** 1914–1945, 1978–1999
- **Current code:**
  ```python
  def show_screen(self, name):
      ...
      self.stack.setCurrentWidget(...)
  ```
- **Root cause:** `show_screen()` changes the displayed screen without updating active top-bar state; only `show_section()` does.
- **Fix:** **NEEDS-RESEARCH:** Confirm the complete screen-to-section mapping and which screens should have no active top-bar item. Centralize that mapping and update top-bar state from `show_screen()`.
- **Verify:** Navigate to a screen from each direct-navigation action and assert the displayed screen and active top-bar item agree.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/trade_block.py`

**Issue 1: “Negotiate” discards the selected trade-block context**
- **Severity:** Minor
- **Lines:** 650–720
- **Current code:**
  ```python
  def _on_negotiate(self):
      self.navigate_to("trades")
  ```
- **Root cause:** The handler does not read the selected interest/team/player row, so the trade builder opens without the context the user selected.
- **Fix:** **NEEDS-RESEARCH:** Confirm the trade screen’s supported initialization API and selection data for both tabs. Pass the selected team/player through that API when navigating.
- **Verify:** Select a row in each tab and invoke Negotiate; assert the trade screen is initialized with that row’s team/player.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/widgets/context_menu.py`

**Issue 1: “Propose Trade” does not seed the selected entity**
- **Severity:** Minor
- **Lines:** 37–53, 67–74
- **Current code:**
  ```python
  # Player/team action opens the trade screen without passing the entity.
  ```
- **Root cause:** The context action discards the clicked player/team, leaving the trade builder uninitialized.
- **Fix:** **NEEDS-RESEARCH:** Confirm the trade screen’s supported initialization method for a selected player versus team, then pass the clicked entity through that method.
- **Verify:** Invoke Propose Trade from both player and team context menus; assert the appropriate entity is preselected.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/shortlist.py`

**Issue 1: Double-click cannot open free agents or draft prospects**
- **Severity:** Minor
- **Lines:** 60–88, 190–252
- **Current code:**
  ```python
  for team in getattr(league, "teams", []):
      for p in getattr(team, "roster", []):
          if str(getattr(p, "player_id", "")) == str(pid):
              player_obj = p
  ```
- **Root cause:** Add Player sources free agents and draft prospects, but refresh searches only team rosters and matches `player_id` although entries store `id`.
- **Fix:** **NEEDS-RESEARCH:** Confirm all canonical player-pool locations and whether IDs are uniformly stringifiable. Resolve shortlist IDs across the same pools used by Add Player and compare the same ID attribute used when saving.
- **Verify:** Add one free agent and one draft prospect, refresh, and double-click each; both must open their player profile.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/requirements.txt`

**Issue 1: Base dependencies omit PySide6**
- **Severity:** Minor
- **Lines:** 1–17
- **Current code:**
  ```text
  # PySide6 is not included in the base requirements.
  ```
- **Root cause:** The native source launcher imports the PySide6 application, so a base dependency installation is insufficient.
- **Fix:** **NEEDS-RESEARCH:** Confirm supported Python/platform combinations and the version used by the native build workflow, then add a compatible PySide6 dependency or a documented native requirements file.
- **Verify:** In a clean environment, install the documented native requirements and run `python3 -c "import PySide6; import native_ui.main_window"`.

---

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/puck_dynasty_native.py`

**Issue 1: Native launcher requires an undeclared dependency**
- **Severity:** Minor
- **Lines:** 6–12
- **Current code:**
  ```python
  from native_ui.main_window import ...
  ```
- **Root cause:** Importing the launcher loads modules requiring PySide6, which the base requirements do not install.
- **Fix:** **Depends on:** `requirements.txt` Issue 1. Align launcher documentation with the native dependency installation chosen there.
- **Verify:** Run the source launcher’s import check in a clean environment after installing the documented native dependencies.

---

## PATTERN-level root causes

- **Engine/postgame processing is bypassed or duplicated:** `watch.py`, `schedule.py`, `roster.py`, `tactics.py`, and `morale.py`. Identify canonical engine APIs and side effects before changing these paths.
- **Navigation discards selected context:** `roster.py`, `trade_block.py`, and `widgets/context_menu.py`. Establish one supported context-passing contract for screen navigation.
- **UI-derived state disagrees with authoritative engine state:** `main_window.py` and `shortlist.py`. Prefer canonical stats, IDs, result metadata, and roster/pool APIs.

## Totals

- **Total issue count:** 32
- **Files affected:** 19
- **Critical:** 0
- **Major:** 17
- **Minor:** 15
