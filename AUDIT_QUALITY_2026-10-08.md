# Quality & Player-Experience Audit — 2026-10-08

## Summary
- Redundancies: 2
- Dead code items: 2
- Player-experience issues: 5

The findings below focus on production UI and the transaction paths it calls. Line ranges refer to the current `copilot/native-ui-audit` branch.

## Code redundancies

### FILE: `windows.py`, `offer_sheet_ui.py`, `roster_limits.py`
**Issue 1: Roster capacity is reimplemented differently by each screen**
- `windows.py:2166-2173` blocks prospect promotion using `len(team.roster) >= 23`.
- `offer_sheet_ui.py:548-552, 648-655` repeats the same raw-list/23 check for its preview and submission.
- `roster_limits.py:32, 96-109` already defines `ACTIVE_ROSTER_MAX` and `active_roster_count()`. That helper excludes unsigned players, emergency fillers, waivers, and IR/LTIR players, so the UI checks can incorrectly report a full roster or block an eligible move.
- **Fix:** use the existing shared rule in both screens:

  ```python
  import roster_limits as _rl

  if _rl.active_roster_count(team) >= _rl.ACTIVE_ROSTER_MAX:
      # Show the screen's existing roster-full feedback.
      return
  ```

  Use the same helper for the offer-sheet preview count so the displayed count and submit-time check agree.

### FILE: `buyout_window.py`, `offer_sheet_ui.py`
**Issue 2: Currency formatting is duplicated**
- `buyout_window.py:46-50` and `offer_sheet_ui.py:29-33` each define `_money()` with the same integer-to-`$` formatting and broad exception handling; only their fallback strings differ.
- **Fix:** define one shared formatter (for example in an existing UI utility module) and let callers choose their fallback:

  ```python
  def format_currency(value, fallback="$?"):
      try:
          return f"${int(value):,}"
      except (TypeError, ValueError, OverflowError):
          return fallback
  ```

  Replace both local helpers with imports; pass `fallback="$0"` where that behavior is intentional.

## Dead code

- `windows.py:7` — `confirm_card` is imported but has no references in this module. Remove it from the import list.
- `trade_deadline_center.py:10` — `time` is imported but never used as a name. Remove the import.

No unused methods or disabled code blocks were confidently identified in the production UI paths reviewed.

## Inconsistent patterns

### FILE: `awards_ceremony.py`, `fantasy_draft.py`, `windows.py`, `offer_sheet_ui.py`
**Issue 1: In-game dialogs bypass the shared dialog facade, and recoverable errors use mixed presentation**
- `popup_system.py:4-7, 19-24` establishes `popup_system.messagebox` as the in-game dialog facade. Most screens use it, but `awards_ceremony.py:513-517` and `fantasy_draft.py:1724-1727` import `tkinter.messagebox` directly, producing native OS dialogs in otherwise in-game UI.
- Input/eligibility feedback also varies: contract negotiation uses an in-view banner (`windows.py:15009-15027, 15068-15081`), while offer-sheet validation uses blocking `showinfo` dialogs (`offer_sheet_ui.py:603-655`).
- **Fix:** route all in-game dialogs through `popup_system.messagebox`. Use a persistent in-view status/banner for recoverable validation errors and reserve styled dialogs for decisions or outcomes requiring interruption.

## Overly long methods

These production UI and daily-flow methods exceed 100 lines and combine separable responsibilities:

| File and lines | Method | Length | Suggested split |
|---|---|---:|---|
| `main.py:2578-3039` | `HockeyManagerGUI.__init__` | 462 lines | Separate app state/setup, theme and container construction, screen initialization, and event/shortcut binding. |
| `windows.py:7390-7765` | `DraftView.__init__` | 376 lines | Keep constructor to state initialization; move header, board, ticker, shortlist, and action-panel construction into dedicated builders. |
| `main.py:3919-4170` | `_create_enhanced_menu_bar` | 252 lines | Extract navigation groups, central Continue control, and date/save/settings area into focused builders. |
| `windows.py:2126-2339` | `RosterView.move_player` | 214 lines | Split roster-transition validation (eligibility, cap/slots, agreement rules) from the actual move and the UI feedback. |
| `windows.py:5195-5407` | `TradeWindow.__init__` | 213 lines | Separate negotiation/session state, header, asset lists, and offer controls. |
| `main.py:7933-8587` | `simulate_day` | 655 lines | Extract blocker handling, date/maintenance updates, game simulation, and end-of-day transitions into named phases. |

## Magic numbers and strings

- `offer_sheet_ui.py:548-552, 651-655` — hardcoded `23` and `"23/23"` duplicate the roster limit and bypass the active-roster counting rules. Use `roster_limits.ACTIVE_ROSTER_MAX` and `active_roster_count()` as above.
- `player_browser.py:47-49` — `page_size = 250` is a user-visible paging/performance policy embedded in instance setup. Define a named `DEFAULT_PAGE_SIZE` constant (and use it for the page label/navigation calculations) so the tuning point is explicit.
- `windows.py:15011-15017` — the exception fallback `850000` duplicates a season-dependent league minimum. Keep the minimum in `salary_cap_system`; if it cannot be retrieved, show a validation error rather than silently applying a possibly stale salary floor.

## Sloppy error handling

### FILE: `trade_deadline_center.py`
**Issue 1: Trade Center launch errors disappear**
- `trade_deadline_center.py:1607-1619` catches every exception from `open_trade_window()` and silently passes. If opening the workbench fails, the player receives no feedback.
- **Fix:** preserve the exception and show an actionable in-game error:

  ```python
  except Exception as exc:
      messagebox.showerror(
          "Trade Center",
          f"Could not open the Trade Center: {exc}\nTry again or reload the screen.",
      )
  ```

**Issue 2: Cap-validation failures fail open**
- `trade_deadline_center.py:1661-1674` silently ignores exceptions from `_cap_ok_after()` and continues to send the trade. A validation failure is treated as permission to proceed.
- **Fix:** report that the cap check could not be completed and return without sending; only send after an explicit successful validation.

### FILE: `offer_sheet_ui.py`
**Issue 3: Player-decision errors are converted into automatic willingness**
- `offer_sheet_ui.py:670-679` catches any failure in `player_accepts_offer_sheet()` and sets `willing = True`, allowing the signing flow to continue without a successful decision check.
- **Fix:** fail closed: show an actionable error in the offer-sheet view, preserve the draft for retry, and return before matching or executing the offer sheet.

## Player-experience issues

### Screen: Main navigation
**Scenario:** “I'm trying to open my roster or make a trade from another screen.”
**Problem:** The main destinations are grouped under dropdowns (`main.py:3965-4015`); reaching Roster or Trade Center requires opening a category menu and then selecting the destination. The back/forward arrows help with history, but do not make primary destinations directly visible.
**Fix:** keep the most-used screens (Roster, Lines, Schedule, Transactions) directly reachable from a persistent navigation strip or quick-jump control, while retaining the existing grouped menus for less-frequent screens.

### Screen: Transactions menu / Trade Deadline Center
**Scenario:** “I'm trying to prepare for the trade deadline.”
**Problem:** Trade Deadline Center is listed unconditionally in the Transactions menu (`main.py:4003-4011`), despite the nearby comment saying it is “Only visible on deadline day.” Outside the window, `open_trade_deadline_center()` only says to check back later (`main.py:20777-20783`); it does not say when.
**Fix:** either hide/disable the entry until it is available, or leave it visible with the next deadline date and days remaining in its label/help text. Make the behavior match the menu comment.

### Screen: Offer Sheets — roster preview
**Scenario:** “I'm trying to offer-sheet an RFA while my roster has emergency or injured players.”
**Problem:** The screen displays `len(user_team.roster)/23` and blocks at 23 (`offer_sheet_ui.py:548-552, 648-655`), although the game's roster rules exclude emergency fillers, unsigned players, waivers, and IR/LTIR (`roster_limits.py:96-109`). The player can be told the roster is full even when the game's actual count allows the move.
**Fix:** derive both the displayed count and eligibility from `active_roster_count()` and `ACTIVE_ROSTER_MAX`; explain which counted players occupy the remaining slots.

### Screen: Free Agency → contract negotiation
**Scenario:** “I'm trying to make an offer to a free agent.”
**Problem:** The player must open Transactions, choose Free Agents, select a row, choose “Sign Selected Player,” then enter and submit a separate contract offer (`main.py:4003-4009`; `windows.py:3024, 3809-3830, 13676-13723`). The flow offers no quick path for a straightforward market-value offer.
**Fix:** add a clearly labeled “Quick offer” action on the selected-player detail/list, prefilled with the market estimate and minimum term; keep “Customize offer” for bonuses and clauses. Show whether the result is accepted, rejected, or still under consideration before leaving the workflow.

### Screen: Trade Deadline Center → Trade Center
**Scenario:** “I'm trying to continue a trade from the deadline hub.”
**Problem:** If the full Trade Center fails to open, `_open_full_trade_center()` suppresses the exception (`trade_deadline_center.py:1607-1619`), so the click appears to do nothing.
**Fix:** show an in-game error with the reason and a recovery action (retry or return to the deadline hub), rather than silently swallowing the exception.
