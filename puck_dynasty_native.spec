# PyInstaller spec for Puck Dynasty NATIVE (PySide6/Qt).
# Built by GitHub Actions on push to native-ui branch.
# No Flask, no browser, no web_ui -- pure Qt native application.

import os as _os

# Collect every native_ui screen/widget submodule.  Screens are loaded via
# dynamic __import__ in MainWindow._register_all_screens, which PyInstaller's
# static analysis cannot see -- without this, the Windows bundle ships with
# NO screens (setup wizard never appears, all nav clicks silently fail).
#
# NOTE: We scan the filesystem directly instead of using
# PyInstaller.utils.hooks.collect_submodules, because collect_submodules
# needs the package importable at spec-parse time and can return empty
# silently on the GitHub runner.  This scan cannot fail silently.

block_cipher = None

_spec_dir = _os.path.dirname(_os.path.abspath(SPEC))
# R18: explicit engine allowlist.  Replaces the old glob that collected
# EVERY root .py (including ~70 tkinter-dependent modules).  This list is
# the exact static-import closure of the entry script (puck_dynasty_native)
# + native_ui: no module here has any static (top-level or deferred)
# tkinter/customtkinter import, so nothing bundled triggers the spec's
# tkinter/customtkinter hard-excludes.  Tkinter-dependent modules are
# reached only via importlib.import_module (invisible to PyInstaller's
# analysis) and are excluded from the bundle.  Regenerate with the r18
# closure analyzer (tests/test_r18_bundle_hygiene.py asserts completeness).
_ENGINE_ALLOWLIST = [
    "accolades",
    "adaptive_rivals",
    "advanced_metrics",
    "ahl_league",
    "ahl_narratives",
    "ahl_system",
    "ai_extension_planning",
    "ai_gm_identity",
    "ai_team_management",
    "all_star",
    "analytics",
    "analytics_hub",
    "analytics_scouting",
    "arena_atmosphere",
    "assistant_coaches",
    "attribute_composites",
    "auto_resolve",
    "automated_season_flow",
    "awards_race",
    "buyout_math",
    "buyout_window",
    "captaincy_change",
    "captaincy_growth",
    "clutch",
    "coach_checkins",
    "coach_practice",
    "coach_records",
    "coach_season_meeting",
    "condition_system",
    "condition_ui",
    "controversy_system",
    "coordinate_simulation",
    "daily_news",
    "database_generator",
    "database_manager",
    "deployment_policy",
    "draft_day_trades",
    "draft_generator",
    "draft_lottery",
    "draft_night",
    "draft_recap",
    "draft_stories",
    "drama_events",
    "euro_free_agents",
    "fan_narratives",
    "fan_sentiment",
    "franchise_records_seed",
    "game_classes",
    "game_manager",
    "goalie_personality",
    "goalie_pull",
    "headlines",
    "iconic_games",
    "immortality",
    "impact_system",
    "injury_data",
    "international",
    "ir_system",
    "league_digest",
    "league_history",
    "line_chemistry",
    "manager_career",
    "matchups",
    "media_engine",
    "media_rumors",
    "media_system",
    "mesh_system",
    "milestones",
    "momentum",
    "mp_routes",
    "multiplayer",
    "multiplayer.net_client",
    "multiplayer.net_host",
    "multiplayer.protocol",
    "name_safety",
    "narrative_incidents",
    "narrative_ledger",
    "native_ui",
    "native_ui.dialogs",
    "native_ui.dialogs.boxscore",
    "native_ui.dialogs.daily_results",
    "native_ui.dialogs.modal",
    "native_ui.dialogs.recall_picker",
    "native_ui.dialogs.shortcuts",
    "native_ui.dialogs.sim_progress",
    "native_ui.main_window",
    "native_ui.safe",
    "native_ui.screens",
    "native_ui.screens.ahl",
    "native_ui.screens.analytics",
    "native_ui.screens.awards_ceremony",
    "native_ui.screens.base",
    "native_ui.screens.calendar",
    "native_ui.screens.camp",
    "native_ui.screens.captains",
    "native_ui.screens.coach_checkin",
    "native_ui.screens.compare",
    "native_ui.screens.contract_negotiation",
    "native_ui.screens.contracts",
    "native_ui.screens.deadline",
    "native_ui.screens.development",
    "native_ui.screens.draft",
    "native_ui.screens.draft_central",
    "native_ui.screens.draft_recap",
    "native_ui.screens.dressing_room",
    "native_ui.screens.fa_frenzy",
    "native_ui.screens.fantasy_draft",
    "native_ui.screens.finances",
    "native_ui.screens.free_agents",
    "native_ui.screens.gm_options",
    "native_ui.screens.gm_relationships",
    "native_ui.screens.history",
    "native_ui.screens.inbox",
    "native_ui.screens.jersey_numbers",
    "native_ui.screens.lines",
    "native_ui.screens.lottery",
    "native_ui.screens.manager",
    "native_ui.screens.media_center",
    "native_ui.screens.morale",
    "native_ui.screens.multiplayer",
    "native_ui.screens.news",
    "native_ui.screens.offer_sheets",
    "native_ui.screens.offseason_programs",
    "native_ui.screens.player_profile",
    "native_ui.screens.playoffs",
    "native_ui.screens.practice_center",
    "native_ui.screens.recall_picker",
    "native_ui.screens.records",
    "native_ui.screens.replay",
    "native_ui.screens.roster",
    "native_ui.screens.save",
    "native_ui.screens.schedule",
    "native_ui.screens.scouting",
    "native_ui.screens.season_flow",
    "native_ui.screens.season_goals",
    "native_ui.screens.season_meeting",
    "native_ui.screens.season_summary",
    "native_ui.screens.settings",
    "native_ui.screens.setup",
    "native_ui.screens.shortlist",
    "native_ui.screens.shot_chart_viewer",
    "native_ui.screens.staff",
    "native_ui.screens.staff_detail",
    "native_ui.screens.standings",
    "native_ui.screens.stats",
    "native_ui.screens.systems_circumstance",
    "native_ui.screens.systems_clutch",
    "native_ui.screens.systems_common",
    "native_ui.screens.systems_condition",
    "native_ui.screens.systems_deployment",
    "native_ui.screens.systems_discipline",
    "native_ui.screens.systems_rivalry",
    "native_ui.screens.tactics",
    "native_ui.screens.team",
    "native_ui.screens.team_analytics",
    "native_ui.screens.trade_block",
    "native_ui.screens.trades",
    "native_ui.screens.waivers",
    "native_ui.screens.watch",
    "native_ui.theme",
    "native_ui.utils",
    "native_ui.widgets",
    "native_ui.widgets.attribute_bar",
    "native_ui.widgets.context_menu",
    "native_ui.widgets.player_table",
    "nhl_records",
    "nhl_schedule_rules",
    "nhl_teams",
    "offseason_programs",
    "ot_drama",
    "outdoor_games",
    "parity_engine",
    "performance_optimizations",
    "physicality",
    "player_archetypes",
    "player_decision",
    "player_development_system",
    "player_generator",
    "player_traits",
    "player_views",
    "position_specific_attributes",
    "position_training",
    "possession_model",
    "prospect_accolades",
    "prospect_development",
    "quick_sim",
    "real_cap_data",
    "real_ntc_data",
    "reputation_system",
    "rfa_system",
    "roster_limits",
    "salary_cap_system",
    "save_realism",
    "scenario_composites",
    "scoring_balance",
    "scout_perception",
    "scout_tiering",
    "scouting",
    "scouting_profiles",
    "season_goals",
    "season_intensity",
    "season_review",
    "shift_engine",
    "shot_charts",
    "simulation",
    "six_on_five",
    "staff_morale",
    "staff_poaching",
    "staff_renewals",
    "star_development",
    "stars",
    "story_arcs",
    "tactics",
    "team_clutch",
    "team_draft_boards",
    "team_fatigue",
    "team_identity_system",
    "telemetry",
    "trade_deadline_manager",
    "trade_engine",
    "trade_market",
    "trade_negotiation",
    "trade_storylines",
    "training_camp",
    "transaction_windows",
    "ufa_consideration",
    "waiver_logic",
]
_first_party = _ENGINE_ALLOWLIST

def _collect_screens():
    """Scan native_ui/screens/*.py and native_ui/widgets/*.py directly."""
    mods = []
    for pkg, subdir in [('native_ui.screens', 'native_ui/screens'),
                        ('native_ui.widgets', 'native_ui/widgets')]:
        d = _os.path.join(_spec_dir, subdir)
        if _os.path.isdir(d):
            for f in _os.listdir(d):
                if f.endswith('.py') and f != '__init__.py':
                    mods.append(f"{pkg}.{f[:-3]}")
    return sorted(mods)

_screen_mods = _collect_screens()

# Fail fast at spec-parse time if the scan found nothing -- a broken
# bundle (0 screens) is worse than a failed build.  This turns the
# silent v0.26.25-v0.26.28 failure into a loud build error.
if not _screen_mods:
    raise RuntimeError(
        "FATAL: _collect_screens() found 0 modules in native_ui/screens/ "
        f"and native_ui/widgets/ under {_spec_dir}. Refusing to build a "
        "bundle with no screens."
    )
print(f"### puck_dynasty_native.spec: {_screen_mods.__len__()} screen/widget modules will be bundled as hiddenimports")

a = Analysis(
    ['puck_dynasty_native.py'],
    # Explicit pathex: PyInstaller must resolve hiddenimports like
    # 'native_ui.screens.setup' against the repo root.  Relying on the
    # implicit script-dir entry proved fragile (2 modules silently
    # dropped in v0.26.29).
    pathex=[_spec_dir],
    binaries=[],
    datas=[
        ('*.png', '.'),
        ('icons', 'icons'),
        ('assets', 'assets'),
        ('puck_dynasty_icon.ico', '.'),
    ],
    hiddenimports=[
        'PIL', 'PIL.Image', 'PIL.ImageDraw',
        'PIL.ImageFont', 'PIL.ImageOps',
        'PySide6', 'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui',
        'native_ui', 'native_ui.main_window', 'native_ui.theme',
        'native_ui.screens', 'native_ui.screens.base',
        # Explicit: these two were silently dropped by PyInstaller in v0.26.38
        # despite being in _screen_mods. Force them.
        'native_ui.screens.draft', 'native_ui.screens.morale',
        'native_ui.widgets', 'native_ui.widgets.player_table',
        'native_ui.widgets.attribute_bar',
        # Explicit: dialog modules. Some are imported inside functions
        # (deferred), which PyInstaller's static analysis can miss.
        # R17: native_ui/utils.py is only imported inside functions too
        # (to_web_team / TEAM_ABBR / _clean_position), so force it here.
        'native_ui.utils',
        'native_ui.dialogs', 'native_ui.dialogs.modal',
        'native_ui.dialogs.sim_progress', 'native_ui.dialogs.daily_results',
        'native_ui.dialogs.boxscore', 'native_ui.dialogs.recall_picker',
        'native_ui.dialogs.shortcuts',
    ] + _screen_mods \
      + _first_party,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'flask', 'werkzeug', 'jinja2',
        'tkinter', 'customtkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PuckDynasty',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='puck_dynasty_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PuckDynasty',
)
