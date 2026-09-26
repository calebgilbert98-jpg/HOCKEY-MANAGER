# Puck Dynasty UI Modernization — Scope Document

**Goal:** Capture the *feel* of Football Manager 24's ease of access and
Sleeper's visual language — without chasing FM24's animation engine or
drag-and-drop. Point-click, everything in one place, customizable
priorities, easy navigation.

**Guiding principle:** every primary task reachable in **one click** from
anywhere; every key screen answers its questions **without opening a
second window**.

This doc is the build spec. It lives next to the merge guide so both
developers build the same UI.

---

## 1. Non-goals (explicit)

- No drag-and-drop anywhere (user decision — point-click selection only).
- No 60fps animation engine. Transitions are limited to cheap fades /
  instant swaps; tkinter is CPU-drawn and we design within that.
- No GPU tactics pitch. The lines editor stays a clean schematic, not an
  animated rink.
- No rewrite of the sim, data model, or save format. This is
  presentation-layer work; game logic is untouched.

## 2. Current state (what we build on)

- `modern_ui.py`: `AppColors` (charcoal `#0e0e11` / teal `#00ceb8`),
  `AppFonts`, `AppCard`, `StatCard`, `PlayerRow`, `PillBadge`,
  `AppButton`, `NavBar`, `apply_app_theme()`.
- `dashboard_home.py`: `HomeDashboard` — header, stat strip, jump-to
  pills, main grid in a scrollable canvas. Information-dense already,
  but not customizable and not the app's navigation hub.
- `main.py`: `_create_enhanced_top_bar` (team info + Continue +
  season controls); navigation today is top-bar menus.

## 3. Work packages

### WP1 — Persistent left sidebar (the FM24 feel)

Replace menu-hunting with a permanent sidebar, always visible:

- Sections: **Home, Inbox, Roster, Lines, Schedule, Stats, Front Office,
  Finances, Settings**. Each is one click; the active section gets the
  teal indicator.
- **Badges**: unread inbox count on Inbox; trade-deadline day dot on
  Front Office; injuries count on Roster.
- **Keyboard shortcuts**: `Ctrl+1..9` jump to sections; `Space` = Continue
  (already exists); `Esc` = back to Home.
- Sidebar is collapsible to icons-only (persisted in settings).
- Implementation: new `sidebar.py` with a `SideBar` class reusing
  `NavBar` button patterns from `modern_ui.py`, vertical layout.
  `main.py` gains a content-area swapper: `show_section(name)` destroys
  / hides the current panel and builds the new one (lazy-build each
  section once, then `pack_forget`/`pack` — no rebuild cost on revisit).

### WP2 — "Everything in one place" screens

The three screens a GM lives on, redesigned as dense single-screen
layouts. No modal-hopping for the common tasks.

**Team Hub (Home)** — the FM24 "home" screen:
- Left column: next game card (opponent, date, home/away, recent form
  W/L dots), last-5 results strip, upcoming 5 fixtures.
- Middle column: record + streak, cap space bar, top-3 team leaders,
  injury list.
- Right column: inbox preview (top 3 unread), league news headlines.
- The existing `HomeDashboard` sections become these cards; layout
  becomes a 3-column grid instead of one long scroll.

**Roster + Lines (one screen, two panes)** — FM24's tactics screen is
the reference: pitch on the left, player list on the right, everything
visible.
- Left pane: lines schematic (already exists as lines editor — embed it
  instead of opening a window).
- Right pane: roster list with role/line filters; **click a player in
  either pane → the other pane highlights him** (point-click selection,
  §5).
- Line changes apply in place; no "editor window" separate from the
  roster.

**Schedule screen** — month strip + results list + standings mini-table
side by side (reuses the `ScheduleWindow` content, now embedded as a
section instead of a popup).

### WP3 — Customizable priorities (widget system)

The user's core request: *choose what shows, and navigate between
priorities easily.*

- Team Hub is a **widget grid**. Each card (Next Game, Cap Space,
  Injuries, Prospects, Inbox, Form, Leaders, News) is a widget with a
  stable id.
- **Customize mode**: toggle button on the Hub ("Customize") → widgets
  show ✕ to remove; an "Add widget" picker lists hidden ones; up/down
  arrows reorder (no drag-and-drop — click-to-move, per the brief).
- Layout persisted in `settings.json` under `ui_preferences.dashboard`
  as an ordered id list; unknown ids ignored (forward-compatible).
- Sidebar sections pinnable: right-click a sidebar item → pin to top /
  unpin (persisted likewise). Unpinned-but-available sections live under
  a "More" expander.
- Defaults ship the current layout, so existing users see zero change
  until they customize.

### WP4 — Sleeper visual pass

Extend `modern_ui.py` (no new design-system file):

- **Palette**: keep charcoal/teal; add Sleeper-style surface steps
  (`BG`, `BG_ELEVATED`, `BG_CARD`) and semantic colors (win green,
  loss red, warning amber) as named constants. No hard-coded hex
  outside `AppColors` after this pass.
- **Cards**: 12px corner radius, 1px border `BORDER`, 16–20px padding —
  one `AppCard` style used everywhere (audit and unify the ~10 ad-hoc
  card styles in windows.py).
- **Numerals**: big stat numbers use a tabular, larger font
  (`AppFonts.STAT_LARGE`); Sleeper shows `0.5 PTS` huge — we do the same
  for G/A/P, cap hit, ratings.
- **Matchup rows**: schedule/results rows become the Sleeper pattern —
  logo dot + team name + record left, score/time right, status pill.
  New `MatchupRow` widget in `modern_ui.py`.
- **Density**: 8px base spacing scale; section headers get the small
  caps tertiary-label treatment Sleeper uses.
- **PlayerRow**: unify the 3 existing player-row implementations
  (browser, roster, context menu targets) on the one in `modern_ui.py`.

### WP5 — Point-click selection model

One consistent rule: **click selects, and selection is visible
everywhere that object appears.**

- New `selection.py` (small): a `SelectionModel` holding
  `{kind, id}` + subscriber callbacks. Panes subscribe; clicking a
  player in the roster pane highlights him in the lines pane and vice
  versa.
- Clicking a player anywhere opens the existing player context card
  (unify on `player_context_menu.py` — no new popup designs).
- Selected row style: teal left-border + elevated background, defined
  once in `AppColors`/`AppFonts`, applied by `PlayerRow` and
  `MatchupRow`.
- Esc clears selection.

## 4. Phased plan

1. **Phase A — skeleton**: WP1 sidebar + content swapper; existing
   screens mount as sections unchanged. (Biggest feel win, lowest risk.)
2. **Phase B — visuals**: WP4 design-system extension + apply to
   sidebar, Hub, and one screen end-to-end as the reference.
3. **Phase C — consolidation**: WP2 screens (Hub grid, Roster+Lines,
   Schedule section).
4. **Phase D — customization**: WP3 widget system + sidebar pinning.
5. **Phase E — selection**: WP5 selection model wired through the
   consolidated screens.

Each phase is independently shippable on the feature branch.

## 5. Acceptance criteria

- Every primary section reachable in one click / one shortcut from
  anywhere, with no menu diving.
- Team Hub shows next game, form, cap, injuries, inbox preview with
  zero scrolling on a 1440×900 window.
- Roster+Lines: change a line without opening a second window.
- Customize mode: remove, re-add, and reorder a Hub widget; layout
  survives restart.
- No screen in the new flow opens a modal for a task the old flow did
  in one window — consolidation must strictly reduce window count.
- Full-repo `compileall` clean; existing MP test suite still 12/12.

## 6. Risks / constraints

- **tkinter canvas text rendering**: big numerals are fine; custom fonts
  need family fallbacks (Windows ships Segoe UI — use it, fall back to
  TkDefaultFont).
- **Sidebar + existing top bar**: the top bar keeps team info/Continue/
  date; the sidebar owns navigation. Don't duplicate controls.
- **Performance**: Hub widgets must reuse the indexes from the perf
  pass (`find_game_result`, parsed-schedule cache, paged browser) —
  no new full-list scans in refresh paths.
- **Scope discipline**: if a widget needs new sim data, it waits for a
  later phase. Presentation only.
