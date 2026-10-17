# Native UI Stub Hunt — 2026-10-08

Method: AST scan of all 85 .py files under `native_ui/` for pass-only bodies,
Ellipsis bodies, `raise NotImplementedError`, unconditional return-None/empty,
bare-except swallowers, plus manual review of button wiring, "coming soon" UI,
QMessageBox placeholders, disabled controls, and mainline (main.py /
game_manager.py) counterparts.

## LIVE STUBS (wired, reachable, do nothing — mainline has real implementations)

### 1. `native_ui/main_window.py:2206` — `_notify_team_talk`
- Body: `pass` ("Fallback hook for the Tk team-talk path; Qt returns neutral 1.0 game-side, nothing to show.")
- Mainline: `main.py:20011 `_career_team_talk`` + `_present_team_talk_screen` — full-screen pre-match team-talk card with user choice; the choice drives a sim boost multiplier via `manager_career.get_team_talk_options` / `apply_team_talk`.
- GameManager path: `game_manager.py:6590` fires `_ui_notify("team_talk", opponent)` when tkinter is unavailable (always true in native) → hits this `pass` → user never sees the talk, boost silently pinned at neutral 1.0.
- **Caveat / root cause:** currently unreachable in practice — native runs a bare `GameManager` whose `__init__` (game_manager.py:190) sets `career = SimpleNamespace(prompts_enabled=False)`, and `setup_new_game` never builds a real `ManagerCareer`. `_career_prompts_allowed()` (game_manager.py:6495) therefore returns False and `_career_team_talk` returns 1.0 before ever notifying. So the whole career-prompt layer (team talk, game-day bundle, pressers) is disabled game-side in native, not just at this stub. Fixing this stub alone does nothing until the career object exists.

### 2. `native_ui/main_window.py:2201` — `_notify_game_day_bundle`
- Body: `return False` unconditionally. Comment claims "the bundle dialog is MP-only" — **wrong**: in mainline it is a single-player interactive flow.
- Mainline: `main.py:19778 `_maybe_open_game_day_bundle`` — builds an interactive game-day inbox message (`_build_game_day_bundle`, main.py:19699): pre-match presser questions + team talk + Watch/Quick choice; pauses the day sim until the user picks (`_resolve_game_day` resumes). Base `game_manager.py:2612` returns False after firing the notify.
- Effect in native: the game-day bundle never opens; the day just sims through with no presser/team-talk/Watch-Quick choice. Same root-cause caveat as #1: `_maybe_open_game_day_bundle` in mainline Tk is gated by `_career_prompts_allowed()`, and native's shim career has prompts disabled, so the feature is dead game-side in native regardless. If prompts are ever enabled, this stub silently eats the feature.

### 3. `native_ui/screens/season_meeting.py:579` — `refresh()`
- Body: `pass`. Comment says "Re-render on return; draft persists on team" — the intent is to re-render, the body does not.
- `MainWindow.show_screen` calls `refresh()` on every revisit (main_window.py:1786, 1886). The screen has a real `_render_all()` (season_meeting.py:197) that `_seal()` calls after `_persist()`.
- Effect: navigating away and back shows stale content. Fix: `refresh()` should call `self._render_all()` (guarding for first-visit state).

## INTENTIONAL NO-OPS / FALSE POSITIVES (not stubs)

- `native_ui/screens/base.py:41` — `refresh()` pass: base-class hook; 69 screens override with real implementations. Intentional.
- `native_ui/screens/setup.py:204` — `_build_header()` pass: intentional, "Custom hero below replaces the default header." Called by `BaseScreen.__init__`.
- `native_ui/main_window.py:2178` — `_notify_mp_draft_clock` pass: genuinely MP-only. The multiplayer screen intercepts `mp_draft_clock` itself via `_on_mp_notify` (screens/multiplayer.py:582-583 → `_show_draft_clock_dialog`), so the main-window no-op only runs in single-player where the game never fires it (`_mp_draft_pick_window` is MP-only).
- `native_ui/main_window.py:2211` — `_notify_prompts_enabled` pass: matches mainline. GameManager's `prompts_enabled` (game_manager.py:17077) is an auto-generated "no-op shim" ("method not found in main.py"), and Tk's `_ui_notify` (main.py:21677) ignores the kind too. Nothing to do on either side.
- `native_ui/screens/records.py` `_redirect` except→pass: graceful fallback around a deliberate redirect to the stats records tab, not a stub.
- "Not available in this build yet" popups (screens/roster.py:509 `_try_navigate`, roster.py:686 `_open_contracts`, standings.py:306 `_open_team`, stats.py:276): dead-code defensive fallbacks — all target screens ("contracts", "team", "player") ARE registered in `_register_all_screens`, so these paths should never fire. Note roster.py:681 has a stale comment ("The contracts screen is not ported yet") — it is ported (screens/contracts.py, registered).
- Unconnected-button sweep: 11 hits, all false positives (connected via `toggled`/`stateChanged`/QButtonGroup/pill loops).

## STRUCTURAL CONCERNS (not individual stubs, but the #1 way broken code hides)

- **The `_safe(fn, default=None)` swallow pattern** (defined independently in ~40 screens + `systems_common.py` helpers): try/except-Exception → return default. Used for defensive game-data reads, but at this scale it is the try/except-that-swallows-everything pattern: a broken data path silently renders empty tables/placeholders instead of failing loudly. This is how "exists but doesn't work" hides in this codebase.
- `native_ui/screens/manager.py:642-645`: injects a fake `customtkinter` module into `sys.modules` so Tk-only `analytics_hub` imports under Qt. Works, but fragile hack — if analytics_hub ever actually uses CTkFrame, it gets `object` and breaks silently.
- `game_manager.py:17063 def career(self)` is shadowed dead code: `__init__` sets `self.career` as an instance attribute (line 190), so the lazy-`CareerState()` method never runs. Related to the root cause in #1/#2 — the real fix for career prompts is here, not in the notify stubs.

## CLEAN CHECKS
- Zero `TODO`/`FIXME`/`XXX`/`HACK` comments, zero Ellipsis bodies, zero `raise NotImplementedError` in native_ui/.
- No screens left showing base.py's "coming soon" placeholder (every screen class overrides `_build_body`).
- All 61 screens registered in `_register_all_screens` and importable.
- Context menus (widgets/context_menu.py) all wired to real actions.
