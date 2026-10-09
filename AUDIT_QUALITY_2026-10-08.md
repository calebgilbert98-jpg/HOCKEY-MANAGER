# Quality & Player-Experience Audit — 2026-10-08

Reviewed `native-ui` at `333caa9f94a823ed96ed9ee5c1e13f31bf052886`. This was targeted source review, not runtime testing or a complete lint/unused-symbol scan.

## Summary
- Redundancies: 4
- Dead code items: 3
- Player-experience issues: 8
- Other code-quality findings: 8

## Code redundancies

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/standings.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/finances.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/trades.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/roster.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/watch.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/schedule.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/draft.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/inbox.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/scouting.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/tactics.py`

**Issue 1: Every screen reimplements the same exception-to-default wrapper**
- **Lines:** `standings.py:38-43`; `finances.py:62-67`; `trades.py:62-67`; `roster.py:33-38`; `watch.py:51-56`; `schedule.py:30-35`; `draft.py:55-60`; `inbox.py:48-53`; `scouting.py:55-60`; `tactics.py:46-51`
- **What's duplicated:** Each defines the same `_safe(fn, default=None)` with `try: return fn()` and `except Exception: return default`. Copying it across screens makes error visibility and fallback semantics drift; it also silently hides unexpected failures.
- **Proposed shared helper:** Add `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/safe.py`:
  ```python
  import logging

  _logger = logging.getLogger(__name__)

  def safe_call(fn, default=None, *, context=""):
      try:
          return fn()
      except Exception:
          _logger.exception("Native UI operation failed%s",
                            f" ({context})" if context else "")
          return default
  ```
  Replace each local wrapper with `from native_ui.safe import safe_call` and use `safe_call(operation, default, context="screen/action")`.

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/systems_discipline.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/systems_condition.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/systems_circumstance.py`

**Issue 2: Systems pages duplicate scroll-container construction**
- **Lines:** `systems_discipline.py:22-32`; `systems_condition.py:27-37`; `systems_circumstance.py:32-41`
- **What's duplicated:** Each page creates a `QScrollArea`, configures it, creates an inner `QWidget` and `QVBoxLayout`, sets spacing, installs the widget, and adds the scroll area to the page layout.
- **Proposed shared helper:** Add to `systems_common.py`:
  ```python
  from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

  def add_scroll_content(screen, spacing=12):
      scroll = QScrollArea(screen)
      scroll.setWidgetResizable(True)
      scroll.setFrameShape(QScrollArea.NoFrame)
      inner = QWidget()
      content = QVBoxLayout(inner)
      content.setSpacing(spacing)
      scroll.setWidget(inner)
      screen._layout.addWidget(scroll)
      return content
  ```
  Replace each repeated setup with `self._content = add_scroll_content(self)`.

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/widgets/context_menu.py`

**Issue 3: Entity-screen opening and setter calls are copy-pasted**
- **Lines:** 119-155
- **What's duplicated:** `_open_compare`, `_open_contracts`, and `_open_staff_detail` each navigate, look up the screen, unwrap its scroll widget, test for a setter, call it, and silently ignore exceptions.
- **Proposed shared helper:**
  ```python
  @staticmethod
  def _open_entity_screen(main_window, screen_name, setter_name, entity):
      main_window.show_screen(screen_name)
      screen = main_window._screens.get(screen_name)
      widget = screen.widget() if screen and hasattr(screen, "widget") else screen
      setter = getattr(widget, setter_name, None)
      if callable(setter):
          setter(entity)
      else:
          raise RuntimeError(
              f"{screen_name} screen cannot load the selected entity")
  ```
  Each wrapper should call this helper with its screen, setter, and entity. Catch and display/log an actionable error at the UI boundary rather than swallowing it.

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/widgets/attribute_bar.py`

**Issue 4: Progress-bar stylesheet is duplicated**
- **Lines:** 35-45, 54-67
- **What's duplicated:** The same `QProgressBar` stylesheet is assembled once in `__init__` and again in `set_value`; visual fixes must be repeated and can diverge.
- **Proposed shared helper:**
  ```python
  @staticmethod
  def _bar_stylesheet(color):
      return f"""
          QProgressBar {{
              background-color: #1a2338;
              border: none;
              border-radius: 5px;
          }}
          QProgressBar::chunk {{
              background-color: {color};
              border-radius: 5px;
          }}
      """

  def _apply_bar_color(self, color):
      self._bar.setStyleSheet(self._bar_stylesheet(color))
  ```
  Call `_apply_bar_color(color)` from both initialization and `set_value`.

## Dead code

- **`/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/puck_dynasty_native.spec:17` — unused import.** `collect_submodules` is imported as `_collect_submodules` but never used; the spec uses `_collect_screens()` instead. Delete the import and its “kept for reference” noqa comment.
- **`/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/systems_discipline.py:9` — unused `Qt` import.** Remove `from PySide6.QtCore import Qt`.
- **`/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/systems_condition.py:10` — unused `Qt` import.** Remove `from PySide6.QtCore import Qt`.

## Other code-quality findings

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/systems_circumstance.py`

**Issue 1: Oversized refresh method**
- **Lines:** 105-261 (157 lines)
- **What's wrong:** `refresh()` performs game-context discovery, opponent display, per-player engine calculations, row construction, and table rendering in one method.
- **Specific fix:** Extract `_build_game_context()`, `_render_next_game(body, context)`, `_build_player_shift_rows(team, context, composite)`, and `_render_shift_table(body, rows)`. Keep `refresh()` as orchestration that clears the layout, obtains the context, and calls those helpers.
- **Refactor shape:**
  ```python
  def refresh(self):
      body = getattr(self, "_body", None)
      if body is None:
          return
      clear_layout(body)
      context = self._build_game_context()
      if context is None:
          body.addWidget(no_game_label())
          return
      self._render_next_game(body, context)
      rows = self._build_player_shift_rows(
          context.team, context.sim, self._combo.currentData())
      self._render_shift_table(body, rows)
  ```

**Issue 2: Per-player errors disappear without a diagnostic**
- **Lines:** 195-230
- **What's wrong:** A broad `except Exception: continue` skips a player's row after any error, making engine/data defects look like ordinary missing data.
- **Specific fix:** Catch only expected conversion errors where recoverable; log the player's ID and traceback for unexpected exceptions:
  ```python
  except (TypeError, ValueError) as exc:
      _logger.warning("Skipping invalid circumstance data for %s: %s",
                      getattr(p, "id", "?"), exc)
  except Exception:
      _logger.exception("Failed to calculate circumstance row for %s",
                        getattr(p, "id", "?"))
  ```

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/main_window.py`

**Issue 3: Hub and application-shell methods exceed 100 lines**
- **Lines:** `HubPage.__init__:186-439` (254 lines); `HubPage.refresh:817-1078` (262 lines); `MainWindow._register_all_screens:1751-1908` (158 lines); `MainWindow.show_blockers:2404-2543` (140 lines); `MainWindow._setup_menu_nav:2594-2737` (144 lines)
- **What's wrong:** Construction, navigation registration, blocker selection/action handling, and dashboard refresh each mix multiple independent responsibilities. This makes review, testing, and changes risky.
- **Specific fix:** Split `HubPage.__init__` into `_build_header`, `_build_tiles`, `_build_panels`, and `_build_ticker`; split `refresh` into `_refresh_summary`, `_refresh_next_game`, and `_refresh_panels`; split screen registration into categorized registry builders; split blocker rendering from action dispatch; split menu construction by menu/section. Keep public entry points as short orchestration methods.
- **Refactor shape:**
  ```python
  def refresh(self, game=None):
      self._refresh_summary(game)
      self._refresh_next_game(game)
      self._refresh_panels(game)
      self._refresh_ticker(game)

  def _register_all_screens(self):
      for registry in (
          self._core_screen_registry(),
          self._league_screen_registry(),
          self._management_screen_registry(),
      ):
          self._screen_classes.update(registry)
  ```

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/scouting.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/inbox.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/schedule.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/free_agents.py`

**Issue 4: Screen methods exceed 100 lines**
- **Lines:** `scouting.py:533-682` (`_build_body`, 150 lines); `inbox.py:1063-1174` (`_actions_gameday`, 112 lines); `schedule.py:223-361` (`_sim_missed_game`, 139 lines); `free_agents.py:676-814` (`__init__`, 139 lines) and `1331-1436` (`_build_body`, 106 lines)
- **What's wrong:** UI construction, business decisions, and multi-step actions are concentrated in large methods.
- **Specific fix:** Extract dialog/form sections and action handlers into purpose-specific helpers. For `_sim_missed_game`, separate validation/schedule lookup, simulation, and result recording. Keep each entry method responsible only for orchestration.
- **Refactor shape:**
  ```python
  def _sim_missed_game(game, date_iso, home_name, away_name):
      context = _validate_and_resolve_fixture(
          game, date_iso, home_name, away_name)
      if context is None:
          return
      sim = _simulate_fixture(context)
      _record_fixture_result(context, sim)
  ```

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/scouting.py`

**Issue 5: Magic prospect limit**
- **Lines:** 93-98
- **What's wrong:** The assignment picker silently truncates its prospect source using the literal `200`; the cap is not named or explained and also hides eligible players.
- **Specific fix:** Prefer a searchable/paged model without dropping prospects. If a product cap is intentional, name and document it:
  ```python
  MAX_ASSIGNMENT_PROSPECTS = 200
  ```
  Then show a visible count and an explicit notice that the list is limited.

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/contract_negotiation.py`

**Issue 6: Contract controls embed unexplained market limits**
- **Lines:** 70-112
- **What's wrong:** Contract-term widgets hardcode the 1–7 year range, $0.75M–$15M AAV range, $5M signing bonus range, and $2M performance-bonus range. These literals are difficult to audit against league/engine policy, and the $15M ceiling can prevent users from entering a higher offer even if the engine allows it.
- **Specific fix:** Centralize the values and, before changing them, verify each against the engine's contract-term rules:
  ```python
  MIN_CONTRACT_YEARS = 1
  MAX_CONTRACT_YEARS = 7
  MIN_OFFER_AAV_M = 0.75
  MAX_OFFER_AAV_M = 15.0
  MAX_SIGNING_BONUS_M = 5.0
  MAX_PERFORMANCE_BONUS_M = 2.0
  ```
  Use these constants in every corresponding widget range; preferably source the limits from the same engine rules used by offer validation.

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/widgets/context_menu.py`

**Issue 7: Screen-opening errors are silently swallowed**
- **Lines:** 119-155
- **What's wrong:** The entity setters are wrapped in broad `except Exception: pass`; a stale screen contract or setter failure leaves the player with no explanation and no log.
- **Specific fix:** Use the shared `_open_entity_screen` helper from Code redundancies Issue 3, and report a clear failure:
  ```python
  try:
      EntityContextMenu._open_entity_screen(
          main_window, "contracts", "set_player", player)
  except Exception as exc:
      QMessageBox.warning(
          main_window, "Could not open contracts",
          f"The selected player's contract screen could not be opened: {exc}")
  ```

### FILE: `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/free_agents.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/contracts.py`, `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/contract_negotiation.py`

**Issue 8: Contract-offer outcomes use inconsistent presentation and wording**
- **Lines:** `free_agents.py:798, 989-1005`; `contracts.py:1214-1269`; `contract_negotiation.py:250-340`
- **What's wrong:** Free-agent offers and extensions report outcomes in inline labels, while the dedicated negotiation flow uses modal dialogs. Similar outcomes also use different language for acceptance, counter, and pending consideration. Players must infer whether the contract is signed or only under consideration.
- **Specific fix:** Centralize outcome classification and wording, then let each screen render that same classification in its surface:
  ```python
  OFFER_OUTCOME_TEXT = {
      "accepted": "Signed — the contract is filed.",
      "countered": "The player countered. Review the proposed terms.",
      "awaiting_agent": "Offer submitted; awaiting the agent's response.",
      "consideration": "Offer is under consideration; no contract is signed.",
      "rejected": "Offer rejected. No contract was signed.",
  }

  def offer_outcome_text(status):
      return OFFER_OUTCOME_TEXT.get(status, "Offer status unavailable.")
  ```
  Use this shared status/message mapping for inline labels and dialogs; reserve “Signed” for confirmed acceptance.

## Player-experience issues

### Screen: Scouting assignments
**Scenario:** "I'm trying to assign a scout to a prospect."
**Problem:** The picker exposes only `prospects[:200]` and has no search control. Prospects outside the first 200 are unavailable, and finding one in the visible flat combo requires scrolling.
**Fix:** Replace the capped combo with a searchable, paged prospect selector; show the total matching count and preserve the chosen prospect while changing filters.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/scouting.py:93-98, 113-134`

### Screen: Inbox
**Scenario:** "I'm trying to mark a message important from the message list."
**Problem:** The row-level Important control is disabled unless the message is already important, even though its handler toggles the state. Users must open the message to mark it important.
**Fix:** Keep the row control enabled for every eligible message and reflect the current important state through its label/icon and accessible checked state.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/inbox.py:535-660`

### Screen: Inbox
**Scenario:** "I'm trying to clear the unread count quickly."
**Problem:** “Mark all read” runs without confirmation, success feedback, undo, or a visible error; exceptions are suppressed.
**Fix:** Confirm the bulk action, display how many messages changed, offer undo if the model supports it, and show an actionable failure instead of silently refreshing.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/inbox.py:635-670`

### Screen: Trade builder
**Scenario:** "I'm trying to assemble a trade with several assets."
**Problem:** Team search exists, but the player/pick asset lists have no search or position/level filters. Large rosters require repeated scanning and scrolling.
**Fix:** Add a search/filter row for each side's player and pick lists; keep checked assets selected as the filters change and show selected-asset counts.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/trades.py:760-930`

### Screen: Free Agents
**Scenario:** "I'm trying to sign a free agent."
**Problem:** The button says “Sign,” but clicking it submits an offer that may be countered, await an agent, or be refused. The label implies an immediate signing.
**Fix:** Label the action “Submit Offer”; use “Signed” only after the engine confirms the contract was accepted, and show pending/counter/rejected status in the same panel.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/free_agents.py:760-970`

### Screen: Schedule — League tab
**Scenario:** "I'm trying to find one team's games in the league schedule."
**Problem:** The League view has no team/opponent filter, so finding a club's fixtures requires scanning all rows for the selected month.
**Fix:** Add a searchable team/opponent filter that applies to both scheduled matchups and results, with a clear reset control.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/schedule.py:375-430`

### Screen: Draft Day Central
**Scenario:** "I'm trying to trade the current draft pick."
**Problem:** “Trade This Pick” navigates to the same draft screen as “Draft Board / War Room”; it neither opens trade negotiation nor carries the current pick into the destination.
**Fix:** Open a trade-up flow preloaded with the current pick and partner selection; if that flow is not available, rename the button to describe its actual destination.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/screens/draft_central.py:54-60`

### Screen: Player/team context menu
**Scenario:** "I'm trying to propose a trade for the player or team I right-clicked."
**Problem:** “Propose Trade” opens the generic trade screen without passing the clicked entity, so the player/team must be found and selected again.
**Fix:** Pass the context entity to a trade-screen initialization method and preselect it in the correct side of the builder.
**Lines:** `/home/runner/work/HOCKEY-MANAGER/HOCKEY-MANAGER/native_ui/widgets/context_menu.py:37-53, 67-74`

## Scope note

The source sample covered shared widgets, Systems screens, hub/navigation, scouting, inbox, roster, trades, free agents, schedule, and draft-day navigation. No runtime interaction tests were performed. No verified unreachable method was found in this targeted pass; the dead-code section lists only unused imports confirmed by inspection.
