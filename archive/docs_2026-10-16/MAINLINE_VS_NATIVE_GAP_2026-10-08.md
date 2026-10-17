# Mainline vs Native UI Gap Audit — 2026-10-08

**Standing rule:** "No native-ui release gets cut until it's been diffed against mainline — compare, port all missing logic, verify."

**Method:** 4 parallel workers diffed all 19 mainline Tkinter windows (`*_window.py`) plus ~20 feature/UI modules against `native_ui/screens/`, `native_ui/dialogs/`, `native_ui/widgets/`. Every claimed gap was verified with grep (no inferred absences). The game engine (`game_manager.py`, `trade_engine.py`, etc.) is shared — gaps are only where native fails to EXPOSE or CALL engine logic that mainline exposes. Supplemental engine-reference sweep by coordinator.

**Scope note:** visual polish differences are NOT gaps. A missing button that calls real engine logic IS a gap.

---

## CRITICAL — silent logic bugs (native drops engine consequences)

These are the worst kind: the UI looks like it works, but engine side-effects never fire.

### 1. Season meeting: coach trust deltas never applied
- Mainline `coach_meeting_window.py:1473` calls `apply_trust_delta(coach, delta)` (moves `gm_trust`, 0–100 clamp) on every beat.
- Native `native_ui/screens/season_meeting.py:471` computes the delta and only **logs** it — `gm_trust` is never modified. Grep: `gm_trust`/`apply_trust_delta` appear ZERO times in native season_meeting.py.
- The finalizer runs with `per_beat_applied=True` semantics, so it skips applying trust too → a completed season meeting changes coach trust by exactly **0**. The conversation is consequence-free.
- Related: deployer-stage reaction not called — native substitutes hard-coded `"Understood."` with delta 0 instead of `_deployer_reaction()` (no situational text, no `deployer_note`/`misaligned` recorded). Deployer stage is also unconditional in native but conditional in mainline (only when `lines_owner == "gm" AND tactics_owner == "gm"`).

### 2. Morale screen: "Take the lines" bypasses `rs.set_line_control`
- Mainline routes through coach-aware `LineControlPopup` (`morale_window.py:776-862`) → `reputation_system.set_line_control(team, 'gm'/'coach', ...)` — computes morale consequences (strong personalities furious when seizing on a winning team, happiness shifts, team-event feed entry).
- Native `morale.py:1819-1823` flips `team.line_control` directly. **No morale/happiness consequences, no team-event feed entry.** The room-reaction engine call is skipped.

### 3. Tactics screen: takeover/enforce bypasses personality flow
- Mainline uses `rs.take_over_tactics` / `rs.hand_back_tactics` / `rs.enforce_tactics` (`reputation_system.py:2724+`): control_need reactions, trust changes, room events, morale deltas, news.
- Native `tactics.py:955-989` calls `tx.set_tactics_control()` directly — coach-personality consequences skipped.

---

## MAJOR — features with no native path at all

### 4. Manager Hub: Weekly Training Schedule tab missing entirely
- Mainline `manager_hub_window.py:381-463`: training presets (`TRAINING_PRESETS`), per-unit intensity/focus (`training.set_unit`), weekly-effects preview (`training.weekly_effects()` → `development_mult`, `injury_risk_mult`, `morale_delta`).
- Engine consumes it (`game_manager.py:7564, 14533, 16125`). Zero hits for `TRAINING_PRESETS`/`set_preset`/`set_unit`/`weekly_effects` anywhere in native_ui.
- The native GM **cannot influence those engine multipliers at all**. (`practice_center.py` is the separate drill system — different feature.)

### 5. Manager Hub: private player chats missing
- Mainline `_do_chat` (`manager_hub_window.py:349-357`): buttons for every `CHAT_ACTIONS` → `chat_with_player(p, action, ...)` with personality-scaled morale/happiness effects.
- Zero hits for `chat_with_player`/`CHAT_ACTIONS` in all of native_ui. This is the **only** caller of that engine function — the whole feature is absent.

### 6. Scouting: no scout hiring / staff-detail editing path
- Mainline `_hire_scout`/`_edit_scout` route to Staff Management's free-agent staff market and staff details.
- Native `staff.py` has list/org/report/assistant pages and Release, but **no staff hiring and no staff detail editing**. A native team with zero scouts has no in-game way to hire any.

### 7. Player context menu: IR place/activate missing
- Mainline `_ir_place` (`player_context_menu.py:1181`) calls `ir_system.place_on_ir(team, player, today)`.
- Native `roster.py:120` shows IR/LTIR badges but there is **NO place/activate action anywhere in native_ui**.

### 8. Automated season flow: entire surface missing
- Mainline `season_flow_ui.py`: SeasonFlowControlPanel (mode/speed, start/stop, Next Game / Next Milestone / Skip Week / Skip Month), AutomationSettingsView (pause at milestones/user games, skip offseason), MilestoneNotificationView.
- Engine `automated_season_flow.py` exists but is unexposed in native. (Native hub shows milestones as display-only.)

### 9. Sim progress: no cancellable progress / heavy-sim confirmations
- Mainline `sim_progress.py`: cancellable `SimProgressDialog`, `run_threaded` worker, `ask_heavy_sim`/`confirm_heavy_sim`, `create_fallback_save`. Zero hits in native_ui.
- Related: `day_sim_loading.py` — no day-sim loading overlay, no ESC-stop hint.

### 10. Scouting: custom scouting profiles — whole subsystem missing
- Mainline `scouting_profiles.py` + `scouting_profile_dialog.py`: `ScoutingProfile` model, `list_profiles`, `save_custom_profile`, attribute-weight profiles, `meets_profile`/`match_score`/`filter_by_profile`. Zero matches in native_ui.

---

## MODERATE — significant but narrower gaps

### Watch / game-viewing experience (mainline `pbp_visual_sim.py` vs native `watch.py`)
Native has the live rink visualizer, but mainline's is substantially richer. All verified 0 matches in native `watch.py`:
- In-game tactics tab (EHM-style whiteboard, mid-game instructions via `rs.suggest_tactics_to_coach`)
- Win-probability meter, momentum panel, game-intensity (tension) meter
- Matchup panel / line shadowing (also absent from native `lines.py`)
- Goal replays + saved/playable highlights (native only links to the text replay screen)
- Sim-to-end / "End Game" pill
- Click-on-dot player card
- No `InGamePopup` milestone/fight banners during watch
- Minor: watch doesn't pass `rivalries`/`outdoor` into sim context

### Animated game replay (mainline `GAME_VIEWER.py` vs native `replay.py`)
- Native `replay.py` has picker + text feed + highlights filter + box score. **No animated rink playback**: no play/pause/reset, no speed control, no rink/text view modes, no animated player/puck movement, no goal celebrations.

### Scouting gaps (mainline `modern_scouting_window.py` vs native `scouting.py`)
- **No Cancel Assignment** — `app.scouting_assignments` entries can't be rescinded natively.
- **No scout-suggestion refresh** — `trade_market.refresh_scout_suggestions` never called natively; native Trade Targets has no refresh action or scout-confidence display.
- No advanced analysis (scout-filtered attribute bands, strengths/weaknesses, comparables, projection).
- No scouting profiles manager (saved column-profile presets).
- No assignment ETA / 30-assignment cap messaging (`scouting_window_helpers.create_scout_assignment`, `estimate_completion_days`).

### Trade deadline depth (mainline `trade_deadline_center.py` vs native `deadline.py`)
- Emergency trade / fire-sale flow (`EmergencyTradeInterface`, `_fire_sale`) — 0 matches
- Market analytics: position analysis, trade predictions, salary-cap analysis — 0 matches
- Player movement tracker + movement stats — 0 matches
- Deadline quick-trade builder with session persistence (general trade building exists in `trades.py`)

### Calendar (mainline `calendar_window.py` vs native `calendar.py`)
- **Marquee/holiday/break events not on grid**: All-Star break, Christmas Day/break, jersey-retirement ceremonies (`immortality.ceremony_schedule_for`), Olympic window/roster/medal games (`international.is_olympic_year`), New Year's Day/Winter Classic, Valentine's Day, Playoffs Begin, Free Agency July 1. Native only emits deadline/draft/season-bound events.
- **Day details lack enrichment**: no result description, recent-form lines, season-series lines, matchup narrative (mainline `_describe_user_result`, `_recent_form_lines`, `_season_series_lines`, `_insert_matchup_narrative`).
- Contextual quick-actions absent (deadline-day "TRADE DEADLINE CENTER" buttons etc.) — minor, all targets exist as screens.

### Staff management (mainline `staff_management_window.py` vs native `staff.py`)
- **Negotiate-chain persist/resume missing** — mainline parks half-finished multi-staff chains in Tier-B session `"staff_negotiate_chain"`. Zero native references.
- Declare-rival for non-head-coach staff missing (native morale.py only offers head-coach beef picker).

### Tactics extras
- Preferred-tactics save/load unexposed (`tx.save_preferred_tactics`/`get_preferred_tactics`, mainline `_on_save_pref`/`_on_load_pref`).

### Player context menu extras (mainline `player_context_menu.py` vs native `widgets/context_menu.py`)
- Assign training focus dialog — 0 matches
- View development history — 0 matches (also missing from native `development.py`)
- Scout-assignment dialog from menu — 0 matches
- Physio report — 0 matches
- Trade-value reasoning breakdown (`trade_engine.player_trade_value_breakdown()`; native `trades.py` only calls `pick_trade_value`)
- Propose Trade doesn't pre-load the player (mainline opens trade window with preset)
- Recently-viewed players — 0 matches
- Add-to-shortlist missing from right-click menu (exists on shortlist screen)

### Setup: roster import mode missing
- Mainline `new_game_setup.py:662-716` → `roster_import_wizard` (EHM .db / CSV source selection, template download, column mapping, preview).
- Zero native references. **Note:** Caleb deferred EHM roster import Oct 6 — may be intentional; flagged for the record.

---

## MINOR

- **Settings**: no "Reset to defaults" (mainline `_reset_to_defaults`).
- **Stats/St
...[truncated 2948 chars]