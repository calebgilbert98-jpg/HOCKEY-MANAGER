# Bloat Audit — Puck Dynasty Repo (2026-10-08)

**Scope:** `~/workspace/hockey-manager` root directory
**Method:** AST-based import graph from entry points (`puck_dynasty_native.py` → `native_ui.main_window` → `game_manager`), transitive closure over all first-party imports, plus grep verification for dynamic references.

## Summary

| Category | Count | Size | Action |
|----------|-------|------|--------|
| CORE (live game code) | 216 .py | — | Keep |
| QA scripts (dead) | 275 .py | 3.2 MB | Archive |
| DEAD clusters (safe to archive) | 25 .py | ~500 KB | Archive |
| UNCERTAIN (dev tools) | 12 .py | ~100 KB | Caleb decides |
| **Total root .py** | **528** | | |
| Current docs | 10 .md | — | Keep |
| Old docs (archive) | 19 .md | — | Archive |
| web_ui/ dead weight | ~57 .py + assets | ~11.7 MB | Partial (see below) |
| telemetry/games.jsonl | 1 file | 106 MB | Truncate or gitignore |

**Bottom line:** 300 of 528 root Python files (57%) are dead code with zero live importers.

---

## 1. CORE — Live Game Code (216 files, KEEP)

Reachable from `puck_dynasty_native.py` via static import closure. Includes:
- `game_manager.py` and all engine modules it imports (~140 modules: simulation, trade_engine, scouting, draft systems, etc.)
- Modules imported by `native_ui/` screens/dialogs (72 root modules)
- `multiplayer/` package (imported by game_manager — still live)
- `native_ui/`, `web_ui/bridge.py` (3 helper functions used by native_ui)

No action needed.

---

## 2. QA Scripts — DEAD (275 files, 3.2 MB, ARCHIVE)

All `qa_*.py` files. Verified: **zero** are imported by any live (non-qa, non-test) code. The only two with any importers (`qa_screens`, `qa_trade_market`) are imported solely by other dead files (`shots_screens.py`, `shot_unified_targets.py`).

These are one-off verification scripts from previous audit/fix cycles. They served their purpose and are now stale.

**All 275 files** (full list in appendix). Examples:
- `qa_ahl_*` (12 files) — AHL feature verification
- `qa_analytics_*` (8 files) — analytics hub verification
- `qa_coach_*` (6 files) — coaching feature verification
- `qa_trade_*`, `qa_cap_*`, `qa_contract_*` — trade/cap verification
- ... and 200+ more single-purpose checks

**Recommendation:** Move to `archive/qa_2026-10-08/`. They are excluded from the PyInstaller spec already (`qa_` prefix filter), so removing them won't affect builds — but it will make the repo navigable.

---

## 3. DEAD Clusters — Safe to Archive (25 files, ~500 KB)

Verified with word-boundary grep across the entire repo (including `native_ui/`, `tests/`, `web_ui/`). Zero importers from live code. These form dead clusters that only import each other:

### Old Playtest Harness (10 files)
Dead sim-driver cluster from before the GM bot regime. They import each other but nothing live imports them.
- `playtest_campaign.py`, `playtest_campaign6.py`, `playtest_driver.py`
- `playtest_fantasy.py`, `playtest_mid.py`, `playtest_offseason.py`
- `playtest_resume_a.py`, `playtest_run.py`, `playtest_season.py`, `playtest_systems.py`

### Old Launchers (5 files)
Pre-native launcher experiments. The current entry point is `puck_dynasty_native.py`.
- `launch_game.py`, `launcher.py`, `simple_launcher.py`, `splash_launcher.py`, `enhanced_launcher.py`

### Abandoned EHM Import (2 files)
EHM roster import was deferred by Caleb (Oct 6). Nothing references this.
- `ehm_simulation_engine.py`, `enhanced_player_system.py`

### Old Schedule System (3 files)
Superseded by the current schedule engine.
- `schedule_engine.py`, `simple_schedule_data.py`, `simple_schedule_interfaces.py`

### Dead Screens/Features (3 files)
- `press_conference_page.py` — old Tkinter page, not used by native_ui
- `shot_unified_targets.py`, `shots_screens.py` — shot chart experiments, superseded

### Other (2 files)
- `scenario_narrative.py` — only imported by dead `qa_scenario_narrative.py`
- `test_multiplayer_phase1.py` — old multiplayer test (multiplayer/ package itself is live)

**Recommendation:** Move to `archive/dead_2026-10-08/`. **Important:** These 25 files ARE currently force-bundled by the PyInstaller spec (`_first_party` glob includes all non-qa root .py files). Removing them will reduce PyInstaller analysis time.

---

## 4. UNCERTAIN — Dev Tools (12 files, ~100 KB, CALEB DECIDES)

These have zero live importers but might be run manually as standalone dev tools. Flag for Caleb:

| File | Likely Purpose |
|------|---------------|
| `sim_integrity.py` | Sim validation tool |
| `validate_sim.py` | Sim validation |
| `validate_season.py` | Season validation |
| `validate_scoring_season.py` | Scoring validation |
| `validate_release.py` | Release validation |
| `balance_validate.py` | Game balance checker |
| `bench_load_times.py` | Performance benchmarking |
| `analyze_telemetry.py` | Telemetry log analyzer |
| `advanced_stats_analytics.py` | Stats analysis tool |
| `verify_roster_limits_live.py` | Roster rules verifier |
| `verify_scarcity_live.py` | Scarcity verifier |
| `verify_slate_headless.py` | Headless test verifier |

**Recommendation:** If Caleb doesn't recognize/use these, archive them too. If any are still used, move to `tools/` directory to keep them out of the PyInstaller bundle.

---

## 5. Markdown Files (29 total)

### Current — KEEP (10)
- `README.md` — project readme
- `CHANGELOG.md` — changelog
- `RELEASE_CHECKLIST.md` — release process (Oct 7)
- `STATE_OF_THE_GAME.md` — overview (Oct 4)
- `STUB_HUNT_NATIVE_UI_2026-10-08.md` — today's audit
- `DESIGN_roster_limits.md` — active design doc
- `D41_SCOPE.md`, `D41_PHASE2.md` — AHL feature docs
- `draft_ux_proposal.md` — design proposal
- `deadcap_2026_27_reference.md` — reference data

### Old — ARCHIVE (19)
Old fix reports, migration docs, and stale guides:
- `APPLICATION_ICON_FIX.md`, `CONTENT_STRETCHING_FIX.md`, `CONTRACT_WINDOW_FIX.md`, `PLAYER_DEVELOPMENT_LAYOUT_FIX.md` — old Tkinter fix reports
- `BETA_DISTRIBUTION_SUMMARY.md`, `ONLINE_DISTRIBUTION_GUIDE.md` — old distribution docs
- `CUSTOMTKINTER_MIGRATION.md` — abandoned migration
- `GITHUB_COLLABORATION_GUIDE.md` — stale setup guide
- `LAUNCHER_README.md` — old launcher docs
- `LONGSIM_BOT_A_BUGS.md`, `LONGSIM_BOT_B_BUGS.md` — Oct 7 bot reports (superseded)
- `MIGRATION_AUDIT.md`, `MIGRATION_PLAN.md` — Tkinter→Web migration (superseded by native pivot)
- `PHASE1_ANALYSIS_REPORT.md`, `PHASE2_ARCHITECTURE_DESIGN.md`, `PHASE3_COMPLETION_REPORT.md` — old phase reports
- `PUSH5_ISSUES.md` — Oct 7 bot report (superseded)
- `S3_REANCHOR.md`, `SAVE_STRESS_REPORT.md` — old reports

**Note:** `PORT_GAP_AUDIT_2026-10-06.md` is already on the do-not-commit list per standing rules.

---

## 6. web_ui/ Directory (12 MB)

**Status:** Mostly dead, partially needed.

- `web_ui/bridge.py` (296 KB) — **NEEDED**. Five `native_ui` files lazily import 3 helpers from it: `TEAM_ABBR`, `_clean_position`, `to_web_team`. (Long-term: these should be moved to a shared util module.)
- `web_ui/server.py`, `web_ui/shell.py` — dead (Flask server, not used by native)
- `web_ui/screens/` (916 KB, ~50 files) — dead (old web screens, ported to native_ui)
- `web_ui/templates/` (288 KB) — dead
- `web_ui/static/` (9.9 MB) — dead (web assets, not bundled by spec)
- `web_ui/test_*.py` (10 files) — dead test scripts

**Recommendation:** Keep `bridge.py`, archive the rest. This saves ~11.7 MB and removes 57 dead .py files from the repo. The 3 helper functions should eventually be extracted to `native_ui/utils.py` or similar.

---

## 7. Other Bloat

| Path | Size | Issue |
|------|------|-------|
| `telemetry/games.jsonl` | 106 MB | Giant telemetry log. Not bundled, but bloats every `git clone`. Should be gitignored or truncated. |
| `__pycache__/` | 9.3 MB | Should be in `.gitignore`, not committed. |
| `saves/` | 3.3 MB | Dev save files in repo. Should be gitignored. |
| `mp_adversarial/` | 44 KB | Old adversarial test dir. Check if needed. |
| `playthrough_harness_A/B/` | 48 KB | Old harness dirs. Likely dead. |
| `qtstub/` | 76 KB | Qt stub files. Check if needed for tests. |
| `ux_mockups/` | 20 KB | Design mockups. Probably keep. |
| `qa_output/`, `qa_shots_draft/`, etc. | small | QA output dirs. Archive. |

---

## 8. PyInstaller Build Impact

The spec's `_first_party` glob force-adds **251** root .py modules to `hiddenimports`:
```python
_first_party = sorted(
    _f[:-3] for _f in _os.listdir(_spec_dir)
    if _f.endswith('.py')
    and _f not in ('main.py', 'puck_dynasty_native.py')
    and not _f.startswith(('qa_', 'pt'))
)
```

Of these 251, **37 are dead** (25 DEAD + 12 UNCERTAIN). PyInstaller must analyze each module's imports during the Analysis phase, even though they're never used at runtime.

**Estimated impact of removing all 300 dead .py files:**
- Analysis phase: ~15-20% faster (fewer modules to scan for imports)
- Cleaner build logs (less noise from analyzing dead code)
- Reduced risk of false "missing module" warnings from dead code with broken imports
- The `qa_` files are already excluded, so the main win is from the 37 non-qa dead files

**Bigger win:** Moving dev tools (`validate_*`, `sim_integrity.py`, etc.) to a `tools/` subdirectory would permanently keep them out of the spec glob.

---

## 9. Recommended Actions

1. **Archive QA scripts:** `mkdir -p archive/qa_2026-10-08 && mv qa_*.py archive/qa_2026-10-08/`
2. **Archive DEAD clusters:** `mkdir -p archive/dead_2026-10-08 && mv [25 files] archive/dead_2026-10-08/`
3. **Archive old docs:** `mkdir -p archive/docs_2026-10-08 && mv [19 .md files] archive/docs_2026-10-08/`
4. **Trim web_ui:** Keep `bridge.py`, archive rest to `archive/web_ui_2026-10-08/`
5. **Gitignore:** Add `telemetry/games.jsonl`, `__pycache__/`, `saves/`, `*.pyc` to `.gitignore`
6. **Decide on UNCERTAIN:** Caleb reviews the 12 dev tools — keep in `tools/` or archive
7. **Long-term:** Extract the 3 `web_ui.bridge` helpers to a native module, then delete `web_ui/` entirely

**Total removable:** ~300 .py files (3.7 MB) + 19 .md files + ~11.7 MB web_ui + 106 MB telemetry = **~121 MB** of bloat.

---

## Appendix: Full Dead File Lists

### All 275 qa_*.py files
```
qa_accolades.py, qa_advanced_stats.py, qa_advs_parity.py, qa_ahl_align.py,
qa_ahl_confidence.py, qa_ahl_league.py, qa_ahl_recall_gate.py, qa_ahl_staff.py,
qa_ahl_ui.py, qa_ai_extension_planning.py, qa_ai_extensions.py,
qa_ai_gm_identity.py, qa_ai_waivers.py, qa_all_star.py, qa_analytics_ahl.py,
qa_analytics_all_players.py, qa_analytics_hardening.py, qa_analytics_hub.py,
qa_analytics_integration.py, qa_analytics_scouting.py, qa_analytics_ui_smoke.py,
qa_analytics_wave1.py, qa_archetype_card.py, qa_assistant_coaches.py,
qa_asst_ui.py, qa_audit_fixes.py, qa_auto_advance.py, qa_awards_race.py,
qa_batch2_views.py, qa_board_patience.py, qa_board_season_review.py,
qa_bracket_fit.py, qa_bracket_tree.py, qa_bug001_none_team_guard.py,
qa_bug021_ufa_lowball.py, qa_bug022_goalie_stats.py, qa_buyout_window.py,
qa_calder_accolades.py, qa_calendar_marquee.py, qa_cap_trade.py,
qa_captaincy_change.py, qa_captaincy_growth.py, qa_captaincy_growth_hook.py,
qa_captaincy_startup.py, qa_card_info.py, qa_card_injuries.py,
qa_cards_inbox.py, qa_career_moments.py, qa_ceremonies_cup.py,
qa_chance_grading.py, qa_chemistry_names.py, qa_coach_carousel.py,
qa_coach_checkin_ui.py, qa_coach_checkins.py, qa_coach_job_seeking.py,
qa_coach_meeting.py, qa_coach_practice.py, qa_coach_season_meeting.py,
qa_composite_toggle.py, qa_condition_wear.py
... (and 200+ more — full list available in /tmp/unreachable.txt)
```

### All 25 DEAD cluster files
```
playtest_campaign.py, playtest_campaign6.py, playtest_driver.py,
playtest_fantasy.py, playtest_mid.py, playtest_offseason.py,
playtest_resume_a.py, playtest_run.py, playtest_season.py, playtest_systems.py,
launch_game.py, launcher.py, simple_launcher.py, splash_launcher.py,
enhanced_launcher.py, ehm_simulation_engine.py, enhanced_player_system.py,
press_conference_page.py, schedule_engine.py, simple_schedule_data.py,
simple_schedule_interfaces.py, scenario_narrative.py, shot_unified_targets.py,
shots_screens.py, test_multiplayer_phase1.py
```

### All 12 UNCERTAIN dev tools
```
advanced_stats_analytics.py, analyze_telemetry.py, balance_validate.py,
bench_load_times.py, sim_integrity.py, validate_release.py,
validate_scoring_season.py, validate_season.py, validate_sim.py,
verify_roster_limits_live.py, verify_scarcity_live.py, verify_slate_headless.py
```
