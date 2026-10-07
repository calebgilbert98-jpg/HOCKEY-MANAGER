"""Puck Dynasty game manager - UI-agnostic game logic.

This module contains the GameManager class which holds all game state
and pure game logic. It has NO Tkinter, NO Qt, NO UI dependencies.
It can be imported and instantiated without any display.

The Tkinter UI (HockeyManagerGUI in main.py) wraps GameManager.
The native Qt UI (native_ui/) uses GameManager directly.
"""
import random
from datetime import date, timedelta, datetime

from game_classes import (
    League, Player, PlayerPosition, Staff, StaffRole,
    ScoutingReport, to_100_scale, position_label,
)
from game_classes import debug_print

try:
    from database_manager import initialize_game_database
except ImportError:
    initialize_game_database = None

try:
    from media_system import MediaSystem
except ImportError:
    MediaSystem = None

SALARY_CAP = 104_000_000  # 2026-27 NHL cap (modern day)

START_DATE = date(datetime.now().year, 9, 1)  # start of preseason


# --- Blocker app registry (for headless/UI-agnostic blocker flows) ---
_BLOCKERS_APP = None


def _set_blockers_app(app):
    global _BLOCKERS_APP
    _BLOCKERS_APP = app


def _blockers_app():
    app = _BLOCKERS_APP
    if app is not None:
        return app
    try:
        import tkinter as _tk
        _root = _tk._default_root
        if _root is not None and hasattr(_root, "get_continue_state"):
            return _root
    except Exception:
        pass
    return None


class GameManager:
    RESULTS_HISTORY_CAP = 4000   # ~3 seasons of games
    RESULTS_TRIM_BATCH = 500
    NEWS_HISTORY_CAP = 1000
    NEWS_TRIM_BATCH = 200
    """Manages the overall game state, including setup and season progression."""

    def __init__(self, league_name="EHM Clone Hockey League"):
        self.league = League(league_name)
        self.league.set_game_manager(self)  # Set reference for database access
        self.user_team = None
        self.startup_settings = None
        # Item 7: set when the human club still needs its mandatory
        # captaincy choice but no display exists to ask (headless new-game
        # setup). The GUI raises the blocker on startup and clears it.
        self._captaincy_choice_pending = False

        # New-game setup options (filled by apply_startup_settings)
        self.fog_of_war = True
        self.sim_detail = {}
        self.user_league = 'NHL'
        self.gm_name = 'General Manager'

        # Active training programs (player_id -> dict with focus, intensity,
        # assigned game-date, player_name). Owned here so they persist in
        # saves; mirrored into enhanced_practice_system.ACTIVE_TRAINING_PROGRAMS
        # for the Development Center window.
        self.training_programs = {}

        # Game calendar date. The GUI syncs its own current_date here on
        # startup; default keeps headless/engine paths working.
        self.current_date = START_DATE
        # News log for league stories
        self.news_log = [{'date': self.current_date,
                          'story': "Welcome to the new season!"}]
        # Waiver wire and trade block (game state, not UI state)
        self.waiver_list = []
        self.trade_block = []
        # Completed game results for viewing (ported from HockeyManagerGUI).
        # Initialized here so headless/native paths never hit AttributeError.
        self.game_results = []
        # Derived lookup indexes over game_results (rebuilt lazily)
        self._results_by_date = {}
        self._results_by_matchup = {}
        self._results_index_src = self.game_results
        # D10: reputation_system stamps everything in GAME time. Register
        # the providers once here; the module falls back to wall-clock
        # when headless/unregistered.
        try:
            import reputation_system as _rs10

            def _gm_date():
                try:
                    return self.current_date
                except Exception:
                    from datetime import date as _d
                    return _d.today()

            def _gm_games_elapsed():
                try:
                    today = self.current_date
                    played = 0
                    for _e in (getattr(self.league, "schedule", None) or []):
                        try:
                            if _e and _e[0] <= today:
                                played += 1
                        except Exception:
                            pass
                    # 32 clubs, 2 per game: per-team average = played / 16.
                    return played // 16
                except Exception:
                    return 0

            _rs10.register_date_provider(_gm_date)
            _rs10.register_games_provider(_gm_games_elapsed)
        except Exception:
            pass
        
        # Initialize records system lazily to avoid blocking startup
        self._record_manager = None
        
        # Initialize AI team manager (for CPU team decisions)
        self._ai_manager = None

        # Phase 2 systems (ported from HockeyManagerGUI._initialize_phase2_systems)
        self.memory_optimizer = None
        self.lazy_manager = None

        # --- Attributes referenced by moved sim methods (safe defaults) ---
        self._abort_day_sim = False
        self._continue_after_bundle = False
        self._captaincy_checked_phase = None
        self._renewals_resolved_year = None
        self._season_last_game_date = None
        self._schedule_cache = {}
        self._strength_cache = {}
        self._milestone_watches = {}
        self._milestone_watch_teams = set()
        self._dev_engine = None
        self._draft_beats_posted = set()
        self._fantasy_draft_deferred = False
        self._game_day_resolution = None
        self._refresh_dashboard = False
        self._end_of_season_flag = False
        self.mp_host = None
        self.mp_client = None
        # MP event-handling state (extracted from HockeyManagerGUI, Bot #19).
        self._mp_deferred_actions = []
        self._mp_pending_ntc = {}
        self._mp_pending_offers = {}
        self._mp_gate_pending = False
        self._mp_host_ready = False
        self._mp_client_ready = False
        self._mp_advance_authorized = False
        self._mp_last_host_port = 0
        self._mp_spectator = False
        self._mp_swapped_user_team = None
        self._mp_dashboard_pending = False
        self._mp_fantasy_clock = None
        # MP fantasy draft flag (set during setup; checked by MP start).
        self.pending_fantasy_draft = False
        # UI-compat shims: HockeyManagerGUI sets these; on a bare GameManager
        # they are safe no-ops so moved methods don't AttributeError.
        self.open_windows = {}
        # Career shim: headless has no GM career object; provide safe defaults
        # so self.career.prompts_enabled and self.career.board.sacked work.
        from types import SimpleNamespace as _SN
        self.career = _SN(prompts_enabled=False,
                          board=_SN(sacked=False))
        self.dashboard = None  # UI shim: headless has no dashboard
        self._season_end_handled_year = None
        self.game_manager = self  # self-reference for gm.X compatibility

        # Save system: attach a GameSaveManager so the native Qt app (and
        # any headless use) can save/load. Required for MP state_provider.
        self.save_manager = None
        try:
            from save_load_system import GameSaveManager as _GSM
            self.save_manager = _GSM(self)
        except Exception:
            pass
        
        # Don't setup game immediately - wait for startup settings
        
    @property

    def ai_manager(self):
        """Lazy initialization of AI team manager"""
        if self._ai_manager is None:
            from ai_team_management import AITeamManager
            self._ai_manager = AITeamManager()
            # Initialize strategies for all teams (excluding user team)
            if hasattr(self, 'league') and self.league.teams:
                self._ai_manager.initialize_team_strategies(self.league.teams)
            # Attach salary cap system for cap-relative contract demands
            try:
                cap_sys = getattr(getattr(self, 'league', None),
                                  'salary_cap_system', None)
                if cap_sys:
                    self._ai_manager.set_cap_system(
                        cap_sys, league=getattr(self, 'league', None))
            except Exception:
                pass
        return self._ai_manager

    def get_live_cap(self) -> int:
        """Current league salary cap (grows each season). Falls back to
        the SALARY_CAP constant if no league/cap system is attached."""
        try:
            cap_sys = getattr(getattr(self, 'league', None),
                              'salary_cap_system', None)
            if cap_sys and getattr(cap_sys, 'current_cap', 0):
                return int(cap_sys.current_cap)
        except Exception:
            pass
        return SALARY_CAP
        
    @property

    def record_manager(self):
        """Lazy initialization of record manager to avoid blocking startup"""
        if self._record_manager is None:
            from nhl_records import RecordManager
            self._record_manager = RecordManager()
        return self._record_manager
        
    def apply_startup_settings(self, settings):
        """Apply settings from startup window and generate database"""
        debug_print("DEBUG: apply_startup_settings called!")
        debug_print(f"DEBUG: Settings received: {settings}")
        
        self.startup_settings = settings
        print(f"Applying startup settings: {settings}")
        
        # Generate database based on selected size
        database_size = settings.get('database_size', 'Small')
        print(f"Generating {database_size} database...")
        
        try:
            debug_print("DEBUG: Attempting to import progress_window...")
            # Import progress window
            from progress_window import DatabaseGenerationProgress
            debug_print("DEBUG: Progress window import successful")
            
            debug_print("DEBUG: Attempting to import database_generator...")
            # Generate the comprehensive database with progress tracking
            from database_generator import generate_database, DatabaseGenerator, DATABASE_CONFIGURATIONS
            debug_print("DEBUG: Database generator import successful")
            
            debug_print(f"DEBUG: Available database configurations: {list(DATABASE_CONFIGURATIONS.keys())}")
            
            # Always generate database regardless of existing league
            debug_print("DEBUG: Generating new database with full roster population...")
            # Show progress window during database generation
            with DatabaseGenerationProgress() as progress:
                def progress_callback(percentage, status, detail=""):
                    progress.update(percentage, status, detail)
                    debug_print(f"DEBUG: Progress - {percentage}% - {status} - {detail}")
                
                # New-game setup wizard can supply a custom DatabaseConfig
                # (league selection); otherwise use the size preset.
                # NOTE (2026-10-06): the size lookup must stay inside the else
                # branch — a supplied database_config must not require a valid
                # size key. The web launcher once passed 'Standard' here and
                # the KeyError silently fell back to a staff-less/AHL-less
                # bare league.
                db_config = settings.get('database_config')
                if db_config is not None:
                    debug_print(f"DEBUG: Using wizard database config: {db_config.name}")
                    generator = DatabaseGenerator(db_config)
                else:
                    config = DATABASE_CONFIGURATIONS[database_size]
                    debug_print(f"DEBUG: Using config: {config.name}")
                    generator = DatabaseGenerator(config)
                # Fantasy-draft starts are an even playing field: the
                # generator skips the real-life day-one cap situations so
                # the draft pool is unshaped (cap compliance is also not
                # enforced during the draft itself).
                generator.fantasy_draft_mode = settings.get('fantasy_draft', False)
                debug_print("DEBUG: DatabaseGenerator created, starting generation...")
                self.league = generator.generate_comprehensive_database(progress_callback)
                debug_print("DEBUG: Database generation completed")
                self.league.set_game_manager(self)
                # Rebuild standings from the generated teams: generation may
                # rename/replace the template teams, leaving stale keys.
                self.league.initialize_standings()

                # New-game wizard options (stored for the session)
                self.fog_of_war = settings.get('fog_of_war', True)
                self.sim_detail = settings.get('sim_detail', {}) or {}
                # Playoff seeding format (setup-only; lives on the league so
                # the bracket and save/load both read one source of truth).
                try:
                    _pf = settings.get('playoff_format', 'divisional')
                    self.league.playoff_format = (
                        _pf if _pf in ("divisional", "conference")
                        else "divisional")
                except Exception:
                    pass
                self.user_league = settings.get('user_league', 'NHL')
                self.gm_name = settings.get('gm_name', 'General Manager')
                try:
                    import scouting_profiles
                    scouting_profiles.FOG_OF_WAR_OVERRIDE = self.fog_of_war
                except Exception:
                    pass
                
                # Initialize draft picks for all teams
                print("Initializing draft picks for all teams...")
                self.league.initialize_all_draft_picks()
                print("Draft picks initialized!")

                # Real-life cap finances: seed each club's actual 2026-27
                # dead-cap penalties (buyouts + retained salary + bonus
                # overages), unless the user chose "start without cap
                # penalties". Only for 2026-27 starts -- the research is
                # season-specific. Fantasy-draft starts skip the seeding
                # entirely: the draft assumes cap rules (the $104M ceiling
                # still applies after) but not cap penalties, so every
                # club begins on an even playing field.
                try:
                    import real_cap_data
                    season_yr = getattr(self.league, 'season_year', 2026)
                    if settings.get('start_without_cap_penalties', False):
                        real_cap_data.clear_dead_cap(self.league)
                        print("Cap penalties cleared (start without cap penalties).")
                    elif not real_cap_data.should_seed_dead_cap(season_yr, settings):
                        print("Cap penalties not seeded for this start "
                              "(fantasy draft: cap rules apply, penalties don't).")
                    else:
                        n = real_cap_data.seed_real_dead_cap(self.league)
                        print(f"Seeded real-life dead-cap penalties for {n} teams.")
                except Exception as e:
                    print(f"Dead-cap seeding skipped: {e}")
                # Real-life trade protection: stamp actual 2026-27 NTC/NMC/
                # M-NTC clauses onto matching players (only when the player
                # is on the listed team -- real-life moves never leak stale
                # clauses into the game).
                try:
                    import real_ntc_data
                    if getattr(self.league, 'season_year', 2026) == real_ntc_data.SEASON:
                        n = real_ntc_data.seed_real_clauses(self.league)
                        print(f"Seeded real-life trade clauses for {n} players.")
                except Exception as e:
                    print(f"Trade-clause seeding skipped: {e}")
                # Day-1 cap guarantee, re-run after dead-cap seeding: real
                # buyouts/retained salary land after generation and can tip a
                # borderline roster over the cap (which would fire the
                # cap-compliance Continue blocker before day one).
                try:
                    from database_generator import DatabaseGenerator
                    DatabaseGenerator._enforce_nhl_cap_compliance(
                        getattr(self.league, 'teams', []) or [])
                except Exception as e:
                    print(f"Cap-compliance pass skipped: {e}")
            
            # Apply comprehensive game settings
            debug_print("DEBUG: Applying game settings...")
            self.apply_all_game_settings(settings)
            debug_print("DEBUG: Game settings applied successfully")
            
            # Handle fantasy draft if enabled
            _fd = settings.get('fantasy_draft', False)
            if _fd:
                print("Fantasy draft enabled - will start after game loads...")
                # Set the flag now; the GUI starts the draft once fully loaded
                # (the inbox isn't ready during apply_startup_settings).
                self.pending_fantasy_draft = True
                self._fantasy_draft_deferred = True
            
            # Generate league schedule
            print("Generating league schedule...")
            if hasattr(self.league, 'generate_schedule'):
                self.league.generate_schedule()
            
            # Rivalry lifecycle: seed the regional feuds (Battle of
            # Alberta, Original Six bad blood, ...) for a brand-new
            # league. Guarded: existing saves keep their lived-in state.
            try:
                self._seed_regional_rivalries()
            except Exception as e:
                print(f"Regional rivalry seeding skipped: {e}")

            print(f"Database generation complete! {len(self.league.get_all_players())} total players.")
            print(f"Teams with players: {len([t for t in self.league.teams if len(t.roster) > 0])}")
            print(f"Teams with staff: {len([t for t in self.league.teams if len(t.staff) > 0])}")
            
        except Exception as e:
            print(f"Error generating database: {e}")
            import traceback
            traceback.print_exc()
            debug_print("DEBUG: Falling back to old system...")
            
            # Initialize a basic league if none exists
            if not hasattr(self, 'league') or self.league is None:
                debug_print("DEBUG: Creating basic league structure...")
                from game_classes import League
                self.league = League("NHL")
                # Add basic NHL teams
                from nhl_teams import NHL_TEAMS
                from game_classes import Team
                for team_name in NHL_TEAMS:
                    team = Team(team_name=team_name, city=team_name.split()[-1])
                    self.league.add_team(team)
                debug_print(f"DEBUG: Created {len(self.league.teams)} basic teams")
                
                # Initialize draft picks for basic teams
                self.league.initialize_all_draft_picks()
                print("Draft picks initialized for basic teams!")
            
            # Fallback to old system
            self.setup_new_game()
    
    def apply_game_difficulty(self, difficulty):
        """Apply difficulty settings to game mechanics"""
        if difficulty == "Rookie":
            self.salary_cap_enforcement = 0.8  # Relaxed cap enforcement
            self.trade_difficulty = 0.7
            self.injury_frequency = 0.5
        elif difficulty == "Normal":
            self.salary_cap_enforcement = 1.0
            self.trade_difficulty = 1.0
            self.injury_frequency = 1.0
        elif difficulty == "Veteran":
            self.salary_cap_enforcement = 1.2
            self.trade_difficulty = 1.3
            self.injury_frequency = 1.2
        elif difficulty == "Legend":
            self.salary_cap_enforcement = 1.5
            self.trade_difficulty = 1.5
            self.injury_frequency = 1.5
    
    def configure_season_length(self, season_length):
        """Configure the number of games in the season"""
        _sl = (season_length or "").lower()
        if "20 games" in _sl:
            self.games_per_season = 20
        elif "41 games" in _sl:
            self.games_per_season = 41
        else:
            self.games_per_season = 84
            
        print(f"Season configured for {self.games_per_season} games")
    
    
    def conduct_fantasy_draft(self):
        """Conduct a serpentine fantasy draft to redistribute all NHL players among teams"""
        print("Starting Fantasy Draft...")
        
        # Collect all NHL players from all teams
        all_nhl_players = []
        nhl_teams = [team for team in self.league.teams if team.league_name == "National Hockey League"]
        
        for team in nhl_teams:
            all_nhl_players.extend(team.roster)
            all_nhl_players.extend(team.ahl_roster)
            all_nhl_players.extend(team.prospects)
            
            # Clear team rosters
            team.roster.clear()
            team.ahl_roster.clear()
            team.prospects.clear()
        
        print(f"Collected {len(all_nhl_players)} players for fantasy draft")
        
        # Sort players by overall rating (best first for fair distribution)
        all_nhl_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Set up serpentine draft order (reverse every round)
        draft_rounds = len(all_nhl_players) // len(nhl_teams) + 1
        current_player_index = 0
        
        for round_num in range(draft_rounds):
            if current_player_index >= len(all_nhl_players):
                break
                
            # Determine team order for this round (serpentine)
            if round_num % 2 == 0:
                # Even rounds: normal order
                team_order = nhl_teams
            else:
                # Odd rounds: reverse order
                team_order = list(reversed(nhl_teams))
            
            for team in team_order:
                if current_player_index >= len(all_nhl_players):
                    break
                    
                player = all_nhl_players[current_player_index]
                
                # Assign to appropriate roster based on rating
                if player.overall_rating() >= 38:
                    team.roster.append(player)
                elif player.overall_rating() >= 33:
                    team.ahl_roster.append(player)
                else:
                    team.prospects.append(player)
                
                # Update player's team
                player.team_name = team.team_name
                current_player_index += 1
        
        print(f"Fantasy draft complete! Redistributed {current_player_index} players")
        
        # News story about fantasy draft (simplified)
        print("Fantasy draft news: A historic fantasy draft has been completed!")
        print(f"All {current_player_index} NHL players have been redistributed among the 32 teams using a serpentine draft format.")
    
    def start_interactive_fantasy_draft(self):
        """Start the interactive fantasy draft system"""
        print("Initializing interactive fantasy draft system...")
        
        # Set flag for delayed draft start
        self.pending_fantasy_draft = True
        
        # Add fantasy draft notification to user's inbox
        self.add_fantasy_draft_inbox_message()
        
        print("Fantasy draft notification added to inbox. Check your messages to begin the draft!")
    
    def apply_all_game_settings(self, settings):
        """Apply all comprehensive game settings from startup window"""
        print("Applying comprehensive game settings...")
        
        # Set user team first so inbox messages work properly
        selected_team_name = settings.get('selected_team')
        debug_print(f"DEBUG apply_all_game_settings: selected_team_name = '{selected_team_name}'")
        if selected_team_name and hasattr(self, 'league') and self.league:
            debug_print(f"DEBUG: Looking for team in {len(self.league.teams)} teams...")
            team_found = False
            for team in self.league.teams:
                debug_print(f"DEBUG: Checking team '{team.team_name}' == '{selected_team_name}'")
                if team.team_name == selected_team_name:
                    self.user_team = team
                    team.is_user_team = True
                    team_found = True
                    print(f"User team set to: {selected_team_name}")
                    break
            if not team_found:
                print(f"WARNING: Could not find team '{selected_team_name}' in league teams!")
            else:
                # Item 7 follow-up: the human club's letters must be the
                # user's choice, never inherited auto-repair.
                self._claim_user_team_captaincy(self.user_team)
                # Pre-season coach expectations meeting (new save): the user
                # club arms its season meeting; every AI club resolves its
                # meeting immediately. Defers while a fantasy draft is
                # pending (startup_settings check -- the draft completion
                # re-arms with real rosters). Guarded and idempotent.
                try:
                    from coach_season_meeting import on_new_save
                    on_new_save(self, self.user_team)
                except Exception:
                    pass
        else:
            debug_print(f"DEBUG: No team to set - selected_team_name={selected_team_name}, has league={hasattr(self, 'league') and self.league is not None}")
        
        # Basic game settings
        self.apply_game_difficulty(settings.get('difficulty', 'Normal'))
        self.configure_season_length(settings.get('season_length', 'Full Season (84 games)'))
        
        # Financial and realism settings
        self.financial_realism_enabled = settings.get('financial_realism', True)
        self.salary_cap_enabled = settings.get('salary_cap', True)
        
        # Player development and trades
        self.rookie_development_rate = self.get_development_rate(settings.get('rookie_development', 'Realistic'))
        self.trade_difficulty_modifier = self.get_trade_difficulty_modifier(settings.get('trade_difficulty', 'Realistic'))
        
        # System toggles
        self.injuries_enabled = settings.get('injuries_enabled', True)
        self.trades_enabled = settings.get('trades_enabled', True)
        self.draft_enabled = settings.get('draft_enabled', True)
        self.playoffs_enabled = settings.get('playoffs', True)
        
        # Advanced systems
        self.morale_system_enabled = settings.get('morale_system', True)
        self.player_personalities_enabled = settings.get('player_personalities', True)
        self.media_pressure_enabled = settings.get('media_pressure', True)
        # Display-only toggle (new-save advanced setting): Composite Ratings
        # visibility on the player card. The sim always uses composites;
        # this never touches logic.
        self.show_composite_ratings = settings.get('show_composite_ratings', True)
        
        # Media System Configuration
        media_engagement = settings.get('media_engagement', 'Standard')
        if hasattr(self, 'media_system'):
            self.media_system.set_engagement_level(media_engagement)
        
        # Season configuration
        self.season_start_type = settings.get('season_start', 'Regular Season Start')
        
        # Apply settings to game mechanics
        self.configure_game_mechanics()
        
        print("Game settings applied successfully!")
        
    def get_development_rate(self, setting):
        """Convert development setting to rate multiplier"""
        rates = {
            'Accelerated': 1.5,
            'Realistic': 1.0,
            'Slow': 0.7
        }
        return rates.get(setting, 1.0)
        
    def get_trade_difficulty_modifier(self, setting):
        """Convert trade difficulty setting to modifier"""
        modifiers = {
            'Easy': 0.7,
            'Realistic': 1.0,
            'Hard': 1.3,
            'Very Hard': 1.6
        }
        return modifiers.get(setting, 1.0)
        
    def configure_game_mechanics(self):
        """Configure game mechanics based on settings"""
        # Apply salary cap settings
        if hasattr(self, 'league') and self.league.teams:
            for team in self.league.teams:
                if team.league_name == "National Hockey League":
                    if self.salary_cap_enabled:
                        team.salary_cap = 104000000  # Standard NHL cap (2026-27)
                    else:
                        team.salary_cap = 999999999  # Effectively unlimited
        
        # Configure injury system
        if hasattr(self, 'injury_frequency'):
            if not self.injuries_enabled:
                self.injury_frequency = 0.0
                
        # Configure trade system
        if hasattr(self, 'trade_difficulty'):
            self.trade_difficulty *= self.trade_difficulty_modifier
            
        print("Game mechanics configured based on settings")
    
    def add_fantasy_draft_inbox_message(self):
        """Add a fantasy draft notification message to the user's inbox"""
        if not self.user_team:
            return
            
        from game_classes import EmailMessage
        from datetime import date
        
        # Create the fantasy draft email
        draft_email = EmailMessage(
            sender="NHL Commissioner",
            sender_type="League",
            subject="🏒 FANTASY DRAFT - Ready to Begin!",
            content="""Dear General Manager,

The NHL is pleased to announce that a Fantasy Draft has been scheduled for your league!

In this special draft, ALL NHL players will be redistributed among the 32 teams using a fair serpentine draft format. This is your chance to build your dream team from scratch!

DRAFT DETAILS:
• 25 rounds of drafting
• Serpentine format (draft order reverses each round) 
• All current NHL players available
• Players assigned to appropriate rosters based on ratings

To begin the Fantasy Draft, simply click the "START DRAFT" button below or access it through the Transactions menu.

Good luck building your championship roster!

Sincerely,
NHL League Office""",
            date_sent=date.today(),
            is_important=True,
            is_urgent=True,
            category="League",
            priority=4,  # Urgent
            requires_response=True,
            response_deadline=None
        )
        
        # Add to user team's inbox
        self.user_team.inbox.add_message(draft_email)
        print(f"Fantasy draft message added to {self.user_team.team_name} inbox")

    def _seed_regional_rivalries(self):
        """Seed regional rivalries for a brand-new league.

        Guarded so existing saves keep their lived-in state: only runs
        when the league's rivalry ledger is empty. Idempotent -- the
        underlying add is merge-by-max, so a double call can't duplicate.
        """
        league = getattr(self, "league", None)
        if league is None:
            return
        rivs = getattr(league, "rivalries", None)
        if not isinstance(rivs, list) or rivs:
            return
        teams = list(getattr(league, "teams", []) or [])
        if not teams:
            return
        try:
            from reputation_system import seed_regional_rivalries
            n = seed_regional_rivalries(rivs, teams)
            if n:
                print(f"Seeded {n} regional rivalries.")
        except Exception:
            pass

    def setup_new_game(self):
        """Initializes a new game world with teams, players, and staff using the comprehensive database system."""
        print("Setting up a new game with comprehensive player database...")
        
        # Initialize the comprehensive database system
        if initialize_game_database is None:
            raise RuntimeError(
                "database_manager module not available -- cannot set up new game")
        self.database_manager = initialize_game_database(self.league.teams)

        # P-5 is handled at creation time by name_safety (star-surname
        # filter in the name generators) -- no post-hoc scrub: there is no
        # real/fictional flag, so a scrub could not tell a generated
        # "Mikko Rantanen" from the real one.
        
        # Initialize media system
        if MediaSystem is not None:
            self.media_system = MediaSystem(self)
        else:
            self.media_system = None
        
        # Generate league schedule
        self.league.generate_schedule()
        # Legacy events: stamp the Winter Classic + Stadium Series onto
        # chosen regular-season home games (no 83rd game is added).
        try:
            import outdoor_games as _og
            _og.schedule_outdoor_games(self.league)
        except Exception as e:
            print(f"⚠️ Outdoor-game scheduling skipped: {e}")

        # New-save realism (Muck 2026-10-02; camp-start 2026-10-04):
        # run training camp (Sep 12-30) during setup and start the game
        # September 15 -- camp ratings, camp storylines, and camp invites
        # (bubble players pushing rosters over 23) are in place, while
        # preseason exhibitions stay on the schedule for the player to
        # play through. Never blocks setup on failure.
        try:
            import save_realism as _sr
            _sr.simulate_camp_and_preseason(self)
        except Exception as e:
            print(f"⚠️ Camp/preseason sim skipped: {e}")
        
        # Initialize all teams with 0 season records for new season start
        print("Initializing clean season records...")
        for team in self.league.teams:
            if team.league_name == "National Hockey League":  # Only for NHL teams
                # Reset all season stats to 0 for new season
                team.wins = 0
                team.losses = 0
                team.ot_losses = 0
                # Note: points is calculated from wins/losses/ot_losses, no need to set directly
                team.goals_for = 0
                team.goals_against = 0
                team.games_played = 0
        print("Clean season records initialized for NHL teams")

        # NHL Rule 6.1: every club must have 1C+2As before opening night.
        # Setup does NOT enforce this -- the game starts at preseason and
        # the phase check (first preseason + first regular-season game day)
        # handles it. AI clubs get silent auto-repair here so they're valid
        # from day one; the human club is left alone (no blocker at setup)
        # and will be prompted during preseason.
        for team in self.league.teams:
            if team.league_name == "National Hockey League":
                try:
                    if team is not getattr(self, "user_team", None):
                        self._ensure_captaincy(team)
                except Exception:
                    pass

        # Real-life jersey retirement ceremonies, staged in the first
        # season on the real month/day (Dec 1 / Jan 30 / Feb 24). Absolute
        # dates anchored to the inaugural season_year, persisted on the
        # league so the rafters match reality whenever the game is started.
        try:
            import immortality as _im_sched
            self.league.ceremony_schedule = _im_sched.ceremony_schedule_for(
                getattr(self.league, "season_year", 2026))
        except Exception:
            pass
        
        # Set draft prospects from database manager
        self.league.draft_prospects = self.database_manager.draft_eligibles
        
        # Check for position-specific attributes system
        try:
            from position_specific_attributes import Player as PlayerV2, convert_to_v2
            self.has_position_specific_attributes = True
            self.PlayerV2 = PlayerV2
            self.convert_to_v2 = convert_to_v2
        except ImportError:
            self.has_position_specific_attributes = False
            
        print("Game setup complete with comprehensive player database.")
        print(f"Total players in database: {len(self.database_manager.all_players)}")
        print(f"Free agents available: {len(self.database_manager.get_free_agents())}")
        print(f"International players: {len(self.database_manager.international_players)}")
        print(f"Draft eligible players: {len(self.database_manager.draft_eligibles)}")
        # Rivalry lifecycle: seed the regional feuds for a brand-new
        # league. Guarded: existing saves keep their lived-in state.
        try:
            self._seed_regional_rivalries()
        except Exception as e:
            print(f"Regional rivalry seeding skipped: {e}")

    def _generate_players(self, count):
        """
        Generates a pool of hockey players with realistic attributes and contracts.
        Ensures proper distribution of positions and realistic salaries based on skill level.
        Uses the position-specific attribute system when available.
        """
        players = []
        
        # Determine position distribution: goalies are ~10%, defensemen ~30%, forwards ~60%
        goalie_count = int(count * 0.1)
        defense_count = int(count * 0.3)
        forward_count = count - goalie_count - defense_count
        
        # Generate players by position
        # 1. Goalies
        for _ in range(goalie_count):
            age = max(18, min(40, int(random.gauss(27, 4))))  # Goalies peak a bit later
            
            if POSITION_SPECIFIC_ATTRIBUTES_AVAILABLE:
                # Use the new position-specific player system
                goalie = PlayerV2(
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    age=age,
                    primary_position=PlayerPosition.GOALIE
                )
                # Set the highest attributes for goalies
                # (The system automatically handles other attributes)
                setattr(goalie, "reflexes", random.randint(50, 90))
                setattr(goalie, "positioning", random.randint(50, 90))
                setattr(goalie, "rebound_control", random.randint(50, 90))
            else:
                # Position-specific base attributes (legacy system)
                goalie_attrs = {
                    "goaltending": random.randint(50, 90),
                    "reflexes": random.randint(50, 100),
                    "positioning": random.randint(50, 100),
                    "rebound_control": random.randint(40, 100),
                    "puck_handling": random.randint(25, 90),
                    "glove_hand": random.randint(40, 90),
                    "stick_side": random.randint(40, 90),
                    "breakaway_skill": random.randint(40, 90),
                }
                
                # Generate common attributes
                common_attrs = self._generate_common_attributes(age)
                
                # Create goalie using the legacy system
                kwargs = {
                    "first_name": random.choice(FIRST_NAMES),
                    "last_name": random.choice(LAST_NAMES),
                    "age": age,
                    "primary_position": PlayerPosition.GOALIE,
                    **common_attrs,
                    **goalie_attrs
                }
                goalie = Player(**kwargs)
            
            # Generate appropriate contract
            self._generate_contract(goalie)
            players.append(goalie)
        
        # 2. Defensemen
        defense_positions = [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]
        for _ in range(defense_count):
            age = max(18, min(40, int(random.gauss(26, 5))))
            
            if POSITION_SPECIFIC_ATTRIBUTES_AVAILABLE:
                # Use the new position-specific player system
                # Map legacy positions to new system if needed
                if defense_positions[0] == PlayerPosition.LEFT_DEFENSE:
                    # Handle older enum format
                    position = PlayerPosition.DEFENSE
                else:
                    position = random.choice(defense_positions)
                    
                defenseman = PlayerV2(
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    age=age,
                    primary_position=position
                )
                # Set the highest attributes for defensemen
                setattr(defenseman, "checking", random.randint(50, 90))
                setattr(defenseman, "defensive_awareness", random.randint(50, 90))
                setattr(defenseman, "shot_blocking", random.randint(50, 90))
                setattr(defenseman, "strength", random.randint(50, 90))
            else:
                # Position-specific base attributes (legacy system)
                defense_attrs = {
                    "checking": random.randint(50, 90),
                    "defensive_awareness": random.randint(50, 90),
                    "shot_blocking": random.randint(50, 90),
                    "stickhandling": random.randint(40, 90),
                    "passing": random.randint(40, 90),
                    "skating": random.randint(50, 90),
                    "strength": random.randint(50, 90),
                }
                
                # Common attributes
                common_attrs = self._generate_common_attributes(age)
                
                # Create defenseman using legacy system
                kwargs = {
                    "first_name": random.choice(FIRST_NAMES),
                    "last_name": random.choice(LAST_NAMES),
                    "age": age,
                    "primary_position": random.choice(defense_positions),
                    **common_attrs,
                    **defense_attrs
                }
                defenseman = Player(**kwargs)
            
            # Generate appropriate contract
            self._generate_contract(defenseman)
            players.append(defenseman)
        
        # 3. Forwards
        forward_positions = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]
        for _ in range(forward_count):
            age = max(18, min(40, int(random.gauss(25, 5))))
            
            # Select position
            position = random.choice(forward_positions)
            
            if POSITION_SPECIFIC_ATTRIBUTES_AVAILABLE:
                # Use the new position-specific player system
                forward = PlayerV2(
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    age=age,
                    primary_position=position
                )
                # Set the highest attributes for forwards
                setattr(forward, "shooting", random.randint(50, 90))
                setattr(forward, "passing", random.randint(50, 90))
                setattr(forward, "offensive_awareness", random.randint(50, 90))
                setattr(forward, "stickhandling", random.randint(50, 90))
                
                # Enhance centers with better faceoff skills
                if position == PlayerPosition.CENTER:
                    setattr(forward, "faceoffs", random.randint(50, 90))
            else:
                # Position-specific base attributes (legacy system)
                forward_attrs = {
                    "shooting": random.randint(40, 90),
                    "passing": random.randint(40, 90),
                    "offensive_awareness": random.randint(50, 90),
                    "deking": random.randint(40, 90),
                    "stickhandling": random.randint(40, 90),
                    "skating": random.randint(50, 90),
                }
                
                # Enhance centers with better faceoff skills
                if position == PlayerPosition.CENTER:
                    forward_attrs["faceoffs"] = random.randint(50, 90)
                
                # Common attributes
                common_attrs = self._generate_common_attributes(age)
                
                # Create forward using legacy system
                kwargs = {
                    "first_name": random.choice(FIRST_NAMES),
                    "last_name": random.choice(LAST_NAMES),
                    "age": age,
                    "primary_position": position,
                    **common_attrs,
                    **forward_attrs
                }
                forward = Player(**kwargs)
            
            # Generate appropriate contract
            self._generate_contract(forward)
            players.append(forward)
        
        return players
    
    def _generate_common_attributes(self, age):
        """Generate common attributes for all players with age-appropriate values."""
        # Young players have more development potential
        youth_bonus = max(0, 23 - age) * 0.1
        # Veterans have experience but declining physical traits
        veteran_penalty = max(0, age - 30) * 0.05
        
        return {
            # Mental attributes
            "determination": random.randint(25, 100),
            "teamwork": random.randint(25, 100),
            "leadership": random.randint(25, 100),
            "discipline": random.randint(25, 100),
            "flair": random.randint(25, 100),
            "consistency": random.randint(25, 100),
            "important_matches": random.randint(25, 100),
            "morale": 10,
            
            # Physical attributes (affected by age)
            "strength": min(100, max(25, int(random.randint(40, 90) * (1 + youth_bonus - veteran_penalty)))),
            "injury_proneness": min(100, max(5, int(random.randint(5, 75) * (1 - youth_bonus + veteran_penalty)))),
            "endurance": min(100, max(25, int(random.randint(40, 90) * (1 + youth_bonus - veteran_penalty)))),
            "stamina": min(100, max(25, int(random.randint(40, 90) * (1 + youth_bonus - veteran_penalty)))),
            "speed": min(100, max(25, int(random.randint(40, 90) * (1 + youth_bonus - veteran_penalty)))),
            "durability": min(100, max(25, int(random.randint(40, 90) * (1 - youth_bonus + veteran_penalty)))),
            
            # Advanced attributes
            "vision": random.randint(25, 100),
            "shooting_accuracy": random.randint(25, 100),
            "shooting_power": random.randint(25, 100),
            "passing_accuracy": random.randint(25, 100),
            "passing_creativity": random.randint(25, 100),
            "puck_protection": random.randint(25, 100),
            "deflections": random.randint(25, 100),
            "hockey_iq": random.randint(25, 100),
            "composure": random.randint(25, 100),
            "aggressiveness": random.randint(25, 100),
            "work_rate": random.randint(25, 100),
            "anticipation": random.randint(25, 100),
            "decision_making": random.randint(25, 100),
            "focus": random.randint(25, 100),
            "confidence": random.randint(25, 100),
            "acceleration": random.randint(25, 100),
            "balance": random.randint(25, 100),
            "agility": random.randint(25, 100),
            
            # Tendencies
            "shoot_pass_tendency": random.randint(0, 100),
            "hitting_tendency": random.randint(0, 100),
            
            # Potential
            "potential_grade": random.choice(['A', 'B', 'C', 'D', 'F']),
        }
    
    def _generate_contract(self, player):
        """Generate realistic contract details based on player age, skill, and position."""
        ovr = player.overall_rating()
        age = player.age
        position = player.primary_position
        
        # Base salary calculation
        if ovr >= 50:  # Star player
            base_salary = random.randint(8_000_000, 12_000_000)
        elif ovr >= 47:  # First line player
            base_salary = random.randint(5_000_000, 8_000_000)
        elif ovr >= 44:  # Second line player
            base_salary = random.randint(3_000_000, 5_000_000)
        elif ovr >= 40:  # Third line player
            base_salary = random.randint(1_500_000, 3_000_000)
        else:  # Fourth line or depth player
            base_salary = random.randint(750_000, 1_500_000)
        
        # Position adjustment
        if position == PlayerPosition.GOALIE:
            if ovr >= 50:  # Elite goalies command premium
                base_salary *= 1.2
            elif ovr < 44:  # Backup goalies get less
                base_salary *= 0.8
        elif position == PlayerPosition.CENTER:
            base_salary *= 1.1  # Centers slightly more valuable
        
        # Age adjustment
        if age < 25:  # Entry-level and bridge deals
            base_salary *= 0.8
            max_years = 3
        elif 25 <= age <= 30:  # Prime years, longer deals
            max_years = 8
        else:  # Veterans, shorter deals
            base_salary *= (1.0 - min(0.3, (age - 30) * 0.05))  # 5% reduction per year over 30, max 30%
            max_years = max(1, 8 - (age - 30))
        
        # Contract length
        if ovr >= 50:
            years = random.randint(max(1, max_years - 2), max_years)
        elif ovr >= 44:
            years = random.randint(max(1, max_years - 4), max_years - 1)
        else:
            years = random.randint(1, min(3, max_years))
        
        # Ensure minimum salary
        salary = max(750_000, int(base_salary))
        
        # Apply contract details
        player.contract.salary = salary
        player.contract.years_remaining = years
        
        # Trade protection: the same demand model the user negotiates
        # against (trade_engine.clause_demand_score) -- stars with leverage
        # get clauses, kids don't, no flat dice roll.
        import trade_engine as _te
        _demand = _te.clause_demand_score(player)
        if random.random() < _demand * 0.85:
            if ovr >= 86 and random.random() < 0.35:
                player.contract.no_movement_clause = True
            else:
                player.contract.no_trade_clause = True
                if random.random() < 0.55:
                    player.contract.modified_ntc_teams = random.choice(
                        [8, 10, 12, 15, 16, 20])

    def _generate_staff(self, count):
        """Generate staff with strategic role distribution for EHM-style management"""
        staff_list = []
        
        # Calculate how many of each core role we need (at least 1 per team for essential roles)
        teams_count = 32
        
        # Define role priorities and restrictions
        unique_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH
        ]
        
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH, 
            StaffRole.GOALIE_COACH,
            StaffRole.ASSISTANT_GENERAL_MANAGER,
            StaffRole.HEAD_SCOUT
        ]
        
        common_roles = [
            StaffRole.ASSISTANT_COACH,
            StaffRole.ASSOCIATE_COACH,
            StaffRole.SKILLS_COACH,
            StaffRole.CONDITIONING_COACH,
            StaffRole.STRENGTH_COACH,
            StaffRole.PROFESSIONAL_SCOUT,
            StaffRole.AMATEUR_SCOUT,
            StaffRole.TEAM_DOCTOR,
            StaffRole.PHYSIOTHERAPIST,
            StaffRole.EQUIPMENT_MANAGER,
            StaffRole.SKATING_COACH,
            StaffRole.VIDEO_COACH,
            StaffRole.ANALYTICS_DIRECTOR,
        ]
        
        # Create exact number needed for unique roles (one per team + extras)
        for role in unique_roles:
            for _ in range(teams_count + 3):  # Small buffer for unique roles
                staff_list.append(Staff(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), role))
        
        # Create sufficient essential roles (at least 2 per team for flexibility)
        for role in essential_roles:
            if role not in unique_roles:  # Don't double-count unique roles
                for _ in range(teams_count * 2 + 5):  # More buffer for essential roles
                    staff_list.append(Staff(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), role))
        
        # Fill remaining with common roles
        remaining_count = count - len(staff_list)
        for _ in range(remaining_count):
            role = random.choice(common_roles)
            staff_list.append(Staff(random.choice(FIRST_NAMES), random.choice(LAST_NAMES), role))
        
        return staff_list

    def _distribute_staff(self, staff):
        """
        Distributes staff to teams ensuring each team has essential EHM-style staff with proper role distribution.
        """
        # Shuffle staff to randomize distribution
        random.shuffle(staff)
        
        # Process each team
        for team in self.league.teams:
            # Add staff - Ensure each team has essential EHM-style staff with proper role distribution
            team.staff = []  # Reset staff list to ensure clean assignment
            
            # Define role assignment priorities and restrictions
            unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
            essential_roles = [
                StaffRole.GENERAL_MANAGER,
                StaffRole.HEAD_COACH,
                StaffRole.ASSISTANT_COACH,
                StaffRole.GOALIE_COACH,
                StaffRole.ASSISTANT_GENERAL_MANAGER,
                StaffRole.HEAD_SCOUT
            ]
            
            # Additional roles that can be assigned (allowing multiples)
            additional_roles = [
                StaffRole.ASSOCIATE_COACH,
                StaffRole.POWER_PLAY_COACH,
                StaffRole.PENALTY_KILL_COACH,
                StaffRole.SKILLS_COACH,
                StaffRole.CONDITIONING_COACH,
                StaffRole.SKATING_COACH,
                StaffRole.PROFESSIONAL_SCOUT,
                StaffRole.AMATEUR_SCOUT,
                StaffRole.EUROPEAN_SCOUT,
                StaffRole.ADVANCE_SCOUT,
                StaffRole.VIDEO_COACH,
                StaffRole.EQUIPMENT_MANAGER,
                StaffRole.TEAM_DOCTOR,
                StaffRole.PHYSIOTHERAPIST,
                StaffRole.STRENGTH_COACH,
                StaffRole.STATISTICIAN,
                StaffRole.MEDIA_RELATIONS
            ]
            
            assigned_unique_roles = set()
            staff_count = 0
            max_staff_per_team = 25  # Realistic staff size for hockey organization
            
            # First, assign essential roles (one per team for unique roles)
            for role in essential_roles:
                if staff_count >= max_staff_per_team:
                    break
                    
                # Find staff member for this role
                for staff_member in staff:
                    if (staff_member.role == role and 
                        staff_member not in [s for team_check in self.league.teams for s in team_check.staff] and
                        (role not in unique_roles or role not in assigned_unique_roles)):
                        
                        team.staff.append(staff_member)
                        staff_count += 1
                        
                        if role in unique_roles:
                            assigned_unique_roles.add(role)
                        break
            
            # Then assign additional staff up to the team limit
            available_staff = [s for s in staff if s not in [staff_check for team_check in self.league.teams for staff_check in team_check.staff]]
            random.shuffle(available_staff)
            
            for staff_member in available_staff:
                if staff_count >= max_staff_per_team:
                    break
                    
                # Skip if it's a unique role that's already assigned
                if (staff_member.role in unique_roles and 
                    staff_member.role in assigned_unique_roles):
                    continue
                
                team.staff.append(staff_member)
                staff_count += 1
                
                if staff_member.role in unique_roles:
                    assigned_unique_roles.add(staff_member.role)
        
        # Create free agent staff pool from remaining unassigned staff
        assigned_staff = [staff_member for team in self.league.teams for staff_member in team.staff]
        unassigned_staff = [s for s in staff if s not in assigned_staff]
        
        # Add remaining staff to free agent pool
        self.league.free_agent_staff = unassigned_staff
        
        print(f"Staff distribution complete. Each team has an average of {sum(len(team.staff) for team in self.league.teams) / len(self.league.teams):.1f} staff members.")
        print(f"Free agent staff available: {len(self.league.free_agent_staff)}")
    
    @property

    def free_agents(self):
        """Get free agents from the database manager."""
        if hasattr(self, 'database_manager'):
            return self.database_manager.get_free_agents()
        else:
            return self.league.free_agents  # Fallback to old system
    
    def get_all_players(self):
        """Get all players from the database manager."""
        if hasattr(self, 'database_manager'):
            return list(self.database_manager.all_players.values())
        else:
            # Fallback: collect from teams and free agents
            all_players = list(self.league.free_agents)
            for team in self.league.teams:
                all_players.extend(team.roster)
                all_players.extend(team.ahl_roster)  # Fixed: use ahl_roster instead of ahl
                all_players.extend(team.prospects)
            return all_players

    def _validate_staff_assignments(self, team):
        """Validate that a team has proper staff assignments with no duplicate unique roles"""
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        role_count = {}
        
        # Count occurrences of each role
        for staff_member in team.staff:
            role = staff_member.role
            role_count[role] = role_count.get(role, 0) + 1
        
        # Check for violations of unique role constraints
        violations = []
        for role in unique_roles:
            count = role_count.get(role, 0)
            if count == 0:
                violations.append(f"Missing {role.value}")
            elif count > 1:
                violations.append(f"Multiple {role.value}s ({count})")
        
        if violations:
            print(f"WARNING - {team.team_name} staff violations: {', '.join(violations)}")
            # Fix violations by reassigning duplicate unique roles
            self._fix_staff_violations(team, role_count)
    
    def _fix_staff_violations(self, team, role_count):
        """Fix staff role violations by reassigning duplicate unique roles"""
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        fallback_roles = [
            StaffRole.ASSISTANT_COACH,
            StaffRole.ASSOCIATE_COACH,
            StaffRole.SKILLS_COACH,
            StaffRole.PROFESSIONAL_SCOUT,
            StaffRole.CONDITIONING_COACH
        ]
        
        for role in unique_roles:
            count = role_count.get(role, 0)
            if count > 1:
                # Find all staff with this role
                duplicate_staff = [s for s in team.staff if s.role == role]
                # Keep the first one, reassign the others
                for i in range(1, len(duplicate_staff)):
                    staff_to_reassign = duplicate_staff[i]
                    new_role = random.choice(fallback_roles)
                    print(f"  Reassigning {staff_to_reassign.full_name} from {role.value} to {new_role.value}")
                    staff_to_reassign.role = new_role
    
    def _get_staff_breakdown(self, staff_list):
        """Get a breakdown of staff roles for reporting"""
        role_count = {}
        for staff_member in staff_list:
            role = staff_member.role
            role_count[role] = role_count.get(role, 0) + 1
        
        # Create readable breakdown
        breakdown_parts = []
        important_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH
        ]
        
        for role in important_roles:
            count = role_count.get(role, 0)
            if count > 0:
                role_name = role.value
                if count > 1:
                    breakdown_parts.append(f"{count} {role_name}s")
                else:
                    breakdown_parts.append(f"1 {role_name}")
        
        # Add count of other roles
        other_count = sum(role_count.get(role, 0) for role in role_count if role not in important_roles)
        if other_count > 0:
            breakdown_parts.append(f"{other_count} others")
        
        return ", ".join(breakdown_parts)

    def sign_free_agent_staff(self, staff, salary, years, assignment="nhl"):
        """Hire a free-agent staffer onto the user's team.

        (Previously missing -- the staff contract dialog called this and
        crashed. Now implemented.) Firing/hiring an Analytics Director
        refreshes the club's analytics department quality via
        refresh_analytics_quality(); hiring a pro scout gives the user a
        new eye with a blank track record to build.

        assignment: "nhl" (default) or "ahl" -- which club the staffer
        joins. Lets the user hire an AHL GM / AHL coach directly.
        """
        try:
            team = getattr(self, "user_team", None)
            league = getattr(self, "league", None)
            if team is None or staff is None:
                return False
            assignment = (str(assignment or "nhl").lower()
                          if str(assignment or "").lower() in ("nhl", "ahl")
                          else "nhl")
            # League-wide staff budget: the offer must fit the club's
            # remaining budget. Applies to every hiring path through here.
            try:
                from game_classes import team_can_afford_staff as _afford
                if not _afford(team, salary):
                    return False
            except Exception:
                pass
            pool = getattr(league, "free_agent_staff", None)
            if pool is not None and staff in pool:
                pool.remove(staff)
            # Muck 2026-10-02: a coaching-carousel hire leaves the
            # carousel, so the AI doesn't hire the same coach too.
            try:
                from reputation_system import drop_from_carousel as _drop
                _drop(staff)
            except Exception:
                pass
            try:
                staff.salary = int(salary)
                staff.contract_years = int(years)
            except Exception:
                pass
            if staff not in list(getattr(team, "staff", []) or []):
                team.staff.append(staff)
                # Stamp which club the hire joins (NHL club or AHL affiliate).
                try:
                    staff.assignment = assignment
                except Exception:
                    pass
            try:
                import analytics_scouting as _as
                _as.refresh_analytics_quality(team)
            except Exception:
                pass
            # Pre-season coach expectations meeting: a new head coach means
            # a new meeting. The hire lands on the user's team here, so arm
            # the user club (guarded; never breaks the signing).
            try:
                from game_classes import StaffRole as _SR
                if (getattr(staff, "role", None) == _SR.HEAD_COACH
                        and str(assignment).lower() == "nhl"):
                    from coach_season_meeting import on_coach_hired
                    on_coach_hired(team, game_manager=self)
            except Exception:
                pass
            # D41 Phase 1: a new head scout means new eyes on the FA pool --
            # re-tier through the new scout's judgment.
            try:
                from game_classes import StaffRole as _SR2
                from scout_tiering import retier_on_scout_change as _retier
                if getattr(staff, "role", None) == _SR2.HEAD_SCOUT:
                    _retier(team, league)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def release_staff(self, staff):
        """Release a staffer from the user's team back to the free-agent pool.

        P15: firing is no longer free -- the club owes severance (dead
        money against the staff budget) and the room's trust in the GM
        takes a hit. See game_classes.process_staff_severance.
        """
        try:
            team = getattr(self, "user_team", None)
            league = getattr(self, "league", None)
            if team is None or staff is None:
                return False
            if staff in list(getattr(team, "staff", []) or []):
                try:
                    from game_classes import process_staff_severance
                    _sev = process_staff_severance(team, staff)
                except Exception:
                    _sev = {}
                team.staff.remove(staff)
                try:
                    _sname = (f"{getattr(staff, 'first_name', '')} "
                              f"{getattr(staff, 'last_name', '')}").strip()
                    if _sev and hasattr(self, "news_log"):
                        self.news_log.append({
                            "date": self.current_date,
                            "story": (f"📋 {_sname or 'Staffer'} released -- "
                                      f"${_sev.get('amount', 0):,} in "
                                      f"severance counts against the staff "
                                      f"budget."),
                        })
                except Exception:
                    pass
            pool = getattr(league, "free_agent_staff", None)
            if pool is not None and staff not in pool:
                pool.append(staff)
            try:
                import analytics_scouting as _as
                _as.refresh_analytics_quality(team)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _assign_captaincy(self, team):
        """Assigns captain and alternate captains based on leadership attributes."""
        if not team.roster:
            return
            
        # Sort players by leadership
        leaders = sorted(team.roster, key=lambda p: p.leadership, reverse=True)
        
        # Assign captain (highest leadership)
        if leaders:
            leaders[0].captaincy = 'C'
            
        # Assign alternates (next two highest)
        if len(leaders) > 1:
            leaders[1].captaincy = 'A'
        if len(leaders) > 2:
            leaders[2].captaincy = 'A'
    
    def get_captaincy_deadline_info(self):
        """Days until opening night (first regular-season game) and deadline date.

        Used for the visible preseason captaincy timeline. Returns
        (days_remaining, deadline_date) or (None, None) if the schedule
        isn't available. Display-free, headless-safe.
        """
        try:
            from datetime import date as _date
            today = getattr(self, "current_date", None)
            if today is None:
                return None, None
            sched = getattr(getattr(self, "league", None), "schedule", None)
            if not sched:
                return None, None
            # Find the earliest non-preseason game on/after today.
            best = None
            for g in sched:
                try:
                    if isinstance(g, dict):
                        gd = g.get("date")
                        is_pre = bool(g.get("preseason"))
                    else:
                        gd = g[0] if len(g) > 0 else None
                        is_pre = False
                        # tuple schedules don't flag preseason; infer by
                        # month: September games are preseason.
                        try:
                            if getattr(gd, "month", 10) == 9:
                                is_pre = True
                        except Exception:
                            pass
                    if is_pre or gd is None or gd < today:
                        continue
                    if best is None or gd < best:
                        best = gd
                except Exception:
                    continue
            if best is None:
                return None, None
            days = (best - today).days
            return max(0, days), best
        except Exception:
            return None, None

    def _ensure_captaincy(self, team) -> "str | None":
        """NHL Rule 6.1: every club must have exactly one captain -- and it
        can't be a goaltender. Idempotent: a valid existing captain is
        never overwritten, alternates are only topped up to two. Returns
        the new captain's name when one had to be named, else None."""
        try:
            from game_classes import PlayerPosition as _PP
        except Exception:
            _PP = None
        roster = list(getattr(team, "roster", None) or [])
        if not roster:
            return None

        def _is_goalie(p):
            try:
                return _PP is not None and getattr(p, "primary_position", None) == _PP.GOALIE
            except Exception:
                return False

        def _lead(p):
            try:
                return int(getattr(p, "leadership", 50) or 50)
            except Exception:
                return 50

        def _tenure(p):
            try:
                return int(getattr(p, "team_tenure_years", 0) or 0)
            except Exception:
                return 0

        # Strip invalid letters first: goalie captains, duplicate Cs.
        changed = False
        for p in roster:
            if getattr(p, "captaincy", "") == "C" and _is_goalie(p):
                try:
                    p.captaincy = ""
                    changed = True
                except Exception:
                    pass
        captains = [p for p in roster if getattr(p, "captaincy", "") == "C"]
        new_captain = None
        if len(captains) != 1:
            for p in captains:
                try:
                    p.captaincy = ""
                except Exception:
                    pass
            skaters = [p for p in roster if not _is_goalie(p)]
            pool = skaters or roster

            def _ovr(p):
                try:
                    return int(p.overall_rating())
                except Exception:
                    return 0

            pick = max(pool, key=lambda p: (_lead(p), _tenure(p), _ovr(p)))
            try:
                pick.captaincy = "C"
            except Exception:
                pass
            new_captain = getattr(pick, "full_name", "A new captain")
            changed = True
        # Top up alternates to two among non-captain skaters.
        try:
            alternates = [p for p in roster
                          if getattr(p, "captaincy", "") == "A"]
            if len(alternates) < 2:
                cands = sorted(
                    (p for p in roster
                     if getattr(p, "captaincy", "") not in ("C", "A")
                     and not _is_goalie(p)),
                    key=lambda p: (_lead(p), _tenure(p)), reverse=True)
                for p in cands[:2 - len(alternates)]:
                    p.captaincy = "A"
                    changed = True
        except Exception:
            pass
        if changed:
            # Item 7 follow-up: stamp letters dealt by auto-repair so the
            # human club can later be told apart from a human choice.
            try:
                team._captaincy_auto_assigned = True
            except Exception:
                pass
        return new_captain

    # --- Item 7: mandatory captaincy user-choice blocker -------------------
    @staticmethod
    def _cap_letter_is_goalie(p) -> bool:
        """NHL Rule 6.1 goalie check shared by the captaincy helpers."""
        try:
            from game_classes import PlayerPosition as _PP
            return getattr(p, "primary_position", None) == _PP.GOALIE
        except Exception:
            return False

    def _captaincy_needs_choice(self, team) -> bool:
        """True when the club does not already wear exactly 1 C + 2 As.

        Goalie-held letters count as invalid (NHL Rule 6.1). Display-free,
        so headless QA can exercise the firing logic without a display.
        """
        roster = list(getattr(team, "roster", None) or [])
        if not roster:
            return False
        caps = [p for p in roster if getattr(p, "captaincy", "") == "C"]
        alts = [p for p in roster if getattr(p, "captaincy", "") == "A"]
        if len(caps) != 1 or len(alts) != 2:
            return True
        if self._cap_letter_is_goalie(caps[0]):
            return True
        return any(self._cap_letter_is_goalie(p) for p in alts)

    def _captaincy_mandatory_window_open(self, team) -> bool:
        """True only while the mandatory captains picker may still fire
        for this club: before its first REGULAR-SEASON game of the
        season. R1(a): the dialog must never interrupt a season in
        progress -- past opening night, missing letters are repaired
        quietly via _ensure_captaincy instead.

        Signal: league.standings is rebuilt to 0-0-0 at season init and
        preseason exhibitions never touch it, so W+L+OTL > 0 means this
        club has started its regular season. Display-free, headless-QA
        safe. Fail-open (True) when the standings are unavailable so a
        weird state can never silently skip the pre-season prompt.
        """
        try:
            standings = getattr(getattr(self, "league", None),
                                "standings", None) or {}
            st = standings.get(getattr(team, "team_name", ""), None) or {}
            gp = (int(st.get("W", 0) or 0) + int(st.get("L", 0) or 0)
                  + int(st.get("OTL", 0) or 0))
            return gp == 0
        except Exception:
            return True

    def _validate_captaincy_pick(self, team, captain_name,
                                 alt1_name, alt2_name):
        """Validate a 1C+2A pick. Returns an error string when the pick is
        illegal, None when it is legal. Display-free, headless-QA safe."""
        by_name = {}
        for p in (getattr(team, "roster", None) or []):
            by_name.setdefault(getattr(p, "full_name", ""), p)
        c = (captain_name or "").strip()
        a1 = (alt1_name or "").strip()
        a2 = (alt2_name or "").strip()
        if not c or c not in by_name:
            return "Choose a captain (C) to continue."
        if not a1 or a1 not in by_name or not a2 or a2 not in by_name:
            return "Choose two alternate captains (A) to continue."
        if c == a1 or c == a2:
            return ("One player cannot wear both the C and an A \u2014 "
                    "pick a different alternate.")
        if a1 == a2:
            return "Pick two different alternate captains."
        if self._cap_letter_is_goalie(by_name[c]):
            return ("NHL Rule 6.1: a goaltender cannot be captain \u2014 "
                    "choose a skater for the C.")
        if (self._cap_letter_is_goalie(by_name[a1])
                or self._cap_letter_is_goalie(by_name[a2])):
            return ("NHL Rule 6.1: a goaltender cannot wear a letter \u2014 "
                    "choose skaters for the As.")
        return None

    def _persist_captaincy_pick(self, team, captain_name,
                                alt1_name, alt2_name):
        """Write a validated 1C+2A pick onto the roster's captaincy field,
        the same by-name way the manual Set Captains tool does."""
        c = (captain_name or "").strip()
        a1 = (alt1_name or "").strip()
        a2 = (alt2_name or "").strip()
        roster = list(getattr(team, "roster", None) or [])
        for p in roster:
            p.captaincy = None
        for p in roster:
            name = getattr(p, "full_name", "")
            if name == c:
                p.captaincy = "C"
            elif name == a1 or name == a2:
                p.captaincy = "A"
        # A human just chose these letters: never mistake them for
        # auto-repair later.
        try:
            team._captaincy_auto_assigned = False
        except Exception:
            pass

    def _opening_night_captaincy_check(self, team, user_team):
        """One club's captaincy step. Returns the new captain's name when
        auto-repair named one (for the news story), else None.

        Phase-aware: during preseason the human club gets a non-blocking
        reminder (inbox task) instead of the modal picker -- captains are
        required before opening night, not before preseason. At the
        regular-season phase the mandatory picker blocks until the user
        chooses. AI clubs always take the silent auto-repair path.
        """
        if team is user_team and self._captaincy_needs_choice(team):
            phase = getattr(self, "_captaincy_check_phase", "regular")
            if phase == "preseason":
                # Non-blocking: remind the user to name captains before
                # opening night. The regular-season phase will enforce it.
                try:
                    self._captaincy_choice_pending = True
                except Exception:
                    pass
                return None
            self._require_captaincy_choice(team)
            return None
        return self._ensure_captaincy(team)

    def _require_captaincy_choice(self, team) -> bool:
        """Item 7: modal continuation blocker for the human club.

        Raises the non-dismissible captain picker and blocks until the
        user confirms exactly 1 C + 2 As. Returns True when a valid choice
        was made and persisted. When no display/popup manager is available
        (headless new-game setup), arms _captaincy_choice_pending instead
        so the GUI raises the blocker on startup -- never crashes.

        R1(a): the modal fires only before the club's first game of the
        season. Past that point the picker is never raised; missing
        letters are repaired quietly via _ensure_captaincy so the dialog
        can never interrupt a season in progress.
        """
        if not self._captaincy_needs_choice(team):
            self._captaincy_choice_pending = False
            return True
        if not self._captaincy_mandatory_window_open(team):
            try:
                self._ensure_captaincy(team)
            except Exception:
                pass
            ok = not self._captaincy_needs_choice(team)
            self._captaincy_choice_pending = not ok
            return ok
        app = getattr(self, "app", None)
        mgr = getattr(app, "popup_manager", None) if app is not None else None
        if mgr is None:
            self._captaincy_choice_pending = True
            return False
        try:
            from windows import MandatoryCaptainsWindow
            win = MandatoryCaptainsWindow(app, team=team)
            win.grab_set()
            win.wait_window()
        except Exception:
            self._captaincy_choice_pending = True
            return False
        ok = not self._captaincy_needs_choice(team)
        self._captaincy_choice_pending = not ok
        if ok:
            try:
                caps = [p for p in (getattr(team, "roster", None) or [])
                        if getattr(p, "captaincy", "") == "C"]
                if caps:
                    _story = (
                        f"\u00a9 {caps[0].full_name} has been named captain of "
                        f"the {getattr(team, 'team_name', 'club')}.")
                    # add_news lives on the GUI; the manager only holds it
                    # via .app.
                    _add = getattr(getattr(self, "app", None),
                                   "add_news", None)
                    if callable(_add):
                        _add(_story)
            except Exception:
                pass
        return ok

    def _claim_user_team_captaincy(self, team) -> bool:
        """Reclaim the human club's letters from auto-repair.

        New-game setup auto-repairs every club before the user's team is
        known; without this, the user would silently inherit those letters
        and never be asked. When the club's letters came from auto-repair
        (stamped by _ensure_captaincy), strip them so the user picks during
        preseason. The picker is NOT armed here -- captaincy is required
        before opening night, not at setup. The phase check (first
        preseason + first regular-season game day) prompts the user.
        Returns True when letters were stripped.
        """
        if team is None:
            return False
        try:
            if getattr(team, "_captaincy_auto_assigned", False):
                for p in (getattr(team, "roster", None) or []):
                    try:
                        p.captaincy = None
                    except Exception:
                        pass
                try:
                    team._captaincy_auto_assigned = False
                except Exception:
                    pass
                # Do NOT arm _captaincy_choice_pending -- no blocker at
                # setup. The preseason phase check will prompt the user.
                return True
            # If the club has no valid letters, leave it letter-less; the
            # preseason phase check will prompt. Never auto-repair the
            # human club, never block at setup.
            if self._captaincy_needs_choice(team):
                return True
        except Exception:
            pass
        return False

    def _captaincy_blocker_suppressed(self) -> bool:
        """Display-free: True while the mandatory-captains Continue blocker
        must stay suppressed. That is the fantasy draft itself (its own
        blocker covers it) and the post-fantasy-draft deferral window:
        rosters are letter-less by design until the first preseason game
        day arms the picker. Headless-QA safe."""
        if getattr(self, 'pending_fantasy_draft', False):
            return True
        return bool(getattr(self, '_fantasy_draft_captaincy_deferred', False))

    def set_user_team(self, team_name):
        """Set the user's selected team"""
        # Find the team by name
        user_team = None
        for team in self.league.teams:
            if team.team_name == team_name:
                user_team = team
                break
        
        if user_team:
            self.user_team = user_team
            print(f"User team set to: {team_name}")
            # Item 7 follow-up: setup auto-repairs every club before the
            # user's team is known -- reclaim the human club so the user
            # picks its captains instead of inheriting auto-repair.
            self._claim_user_team_captaincy(user_team)
            # Pre-season coach expectations meeting (new save): the user
            # club arms its season meeting; every AI club resolves its
            # meeting immediately. Defers while a fantasy draft is pending
            # (the draft completion re-arms with real rosters). Guarded:
            # a meeting failure must never break new-game setup.
            try:
                from coach_season_meeting import on_new_save
                on_new_save(self, user_team)
            except Exception:
                pass
            # Update team colors in UI if the UI is already set up
            if hasattr(self, 'modern_theme') and hasattr(self, 'style'):
                self._update_team_colors()
            # D41 Phase 1: tier the FA pool through the user's head scout's
            # eyes -- new eyes, new reads on who's NHL/AHL/Euro material.
            try:
                from scout_tiering import tier_free_agents as _tier_fa
                _tier_fa(self.league, user_team)
            except Exception:
                pass
        else:
            print(f"Warning: Could not find team '{team_name}'. Available teams:")
            for team in self.league.teams:
                print(f"  - {team.team_name}")

    def _heal_injured_player(self, team, player, _inj):
        """Clear every injury flag on a recovered player. (Extracted so the
        BUG-026 zero-counter path and the normal countdown path share one
        heal sequence.) Never raises."""
        try:
            # Player is healed!
            player.is_injured = False
            player.injury_type = "None"
            player.games_remaining_injured = 0
            # B18 (fixed 2026-09-30): keep the legacy string consistent --
            # stale injury_status values from the old hit path must not
            # linger after recovery.
            try:
                player.injury_status = "Healthy"
            except Exception:
                pass
            try:
                player.in_concussion_protocol = False
                # Re-aggravation window opens on return.
                player.games_since_return = 0
            except Exception:
                pass
            if _inj is not None:
                try:
                    _inj.clear_injury_flag(team, player)
                except Exception:
                    pass
            print(f"✅ {player.first_name} {player.last_name} has recovered from injury!")

            # Notify if it's the user's team
            if hasattr(self, 'user_team') and team == self.user_team:
                if hasattr(self, 'news_log'):
                    self.news_log.append({'date': self.current_date, 'story': f"🏥 {player.first_name} {player.last_name} has recovered from injury and is available."})
            # IR/LTIR return flow (ir_system.py, Muck 2026-10-02): a healed
            # player on IR/LTIR must be activated. IR needs the 7-day minimum;
            # LTIR needs cap room for the returning hit. Never raises.
            try:
                import ir_system as _irs
                _st = _irs.ir_status_of(player)
                if _st in ("IR", "LTIR"):
                    _is_user = (hasattr(self, 'user_team')
                                and team == self.user_team)
                    ok, reason = _irs.activate_player(
                        team, player, getattr(self, 'current_date', None))
                    if ok:
                        if hasattr(self, 'news_log'):
                            self.news_log.append({
                                'date': self.current_date,
                                'story': (
                                    f"📋 {player.first_name} {player.last_name} "
                                    f"activated from {_st}.")})
                    elif _is_user and hasattr(self, 'news_log'):
                        # Healed but blocked (IR minimum or LTIR cap room):
                        # surface it so the GM knows what to do.
                        self.news_log.append({
                            'date': self.current_date,
                            'story': (
                                f"📋 {player.first_name} {player.last_name} "
                                f"is healthy but cannot come off {_st} yet: "
                                f"{reason}")})
            except Exception:
                pass
        except Exception:
            pass

    def _process_injury_recovery(self, teams_played=None):
        """Process injury recovery for all players.

        Decrements games_remaining_injured once per GAME PLAYED (not per day):
        only players whose team played today count down, and players hurt in
        today's game start counting down with their next missed game.

        W4 (icetime-ecosystem): no longer a pure countdown --
          * rehab setbacks (injury_data.roll_setback): injuries can get worse
            before they get better; medical-staff quality modifies the odds;
          * days_missed / career_games_missed increment on every tick (they
            were seeded at generation and never updated);
          * recovered players start a re-aggravation window
            (games_since_return) during which the general injury roll hits
            them harder -- the mechanic behind the physio report's
            "rushing him back risks re-injury" warning;
          * concussion-protocol flag clears on return.
        """
        try:
            import injury_data as _inj
        except Exception:
            _inj = None
        for team in self.league.teams:
            if teams_played is not None and team.team_name not in teams_played:
                continue
            for player in team.roster:
                if not getattr(player, 'is_injured', False):
                    # Re-aggravation clock ticks for healthy recently-returned
                    # players (one tick per team game, like recovery).
                    try:
                        gsr = getattr(player, 'games_since_return', None)
                        if gsr is not None:
                            player.games_since_return = gsr + 1
                    except Exception:
                        pass
                    continue
                # Hurt today? Countdown starts with the next game they miss.
                if getattr(player, 'injured_today', False):
                    player.injured_today = False
                    continue
                # Rehab setback? (staff-modified; additive -- the old code was
                # a pure countdown)
                if _inj is not None:
                    try:
                        _added = _inj.roll_setback(player, team)
                    except Exception:
                        _added = 0
                    if _added:
                        try:
                            player.games_remaining_injured = (
                                getattr(player, 'games_remaining_injured', 0)
                                or 0) + _added
                            if (hasattr(self, 'user_team')
                                    and team == self.user_team
                                    and hasattr(self, 'news_log')):
                                self.news_log.append({
                                    'date': self.current_date,
                                    'story': (
                                        f"🏥 Setback: {player.first_name} "
                                        f"{player.last_name} "
                                        f"({player.injury_type}) -- out "
                                        f"{_added} more games.")})
                        except Exception:
                            pass
                remaining = getattr(player, 'games_remaining_injured', 0) or 0
                if remaining <= 0:
                    # BUG-026: seeded injuries (database_generator flags
                    # is_injured=True with no countdown left) arrive here
                    # with a zero counter. An injury with no games remaining
                    # is over -- heal instead of stranding the player
                    # sidelined forever (the decrement branch below only
                    # fires on positive counters).
                    self._heal_injured_player(team, player, _inj)
                    continue
                if remaining > 0:
                    player.games_remaining_injured = remaining - 1
                    # In-season stat honesty: every countdown tick is a game
                    # missed. (These were seeded at generation, never updated.)
                    try:
                        player.days_missed = (
                            getattr(player, 'days_missed', 0) or 0) + 1
                        player.career_games_missed = (
                            getattr(player, 'career_games_missed', 0) or 0) + 1
                    except Exception:
                        pass

                    if player.games_remaining_injured <= 0:
                        self._heal_injured_player(team, player, _inj)
            # IR/LTIR (ir_system.py, Muck 2026-10-02): AI GMs stash their
            # long-term injuries and activate the healed, same as a human
            # would. User team is managed by the player. Never raises.
            try:
                if not (hasattr(self, 'user_team')
                        and team == self.user_team):
                    import ir_system as _irs
                    _irs.ai_manage_ir(team, getattr(self, 'current_date', None))
            except Exception:
                pass

    def _process_suspension_service(self, teams_played=None):
        """Tick down DoPS suspensions once per GAME PLAYED (not per day).

        Mirrors _process_injury_recovery exactly: only players whose team
        played today serve a game, and a suspension issued after today's
        game (suspended_today) starts counting with the next one. At zero
        the player is eligible again. Never raises.
        """
        try:
            for team in self.league.teams:
                if teams_played is not None and team.team_name not in teams_played:
                    continue
                for player in team.roster:
                    try:
                        remaining = getattr(player, 'suspension_games_remaining', 0) or 0
                        if remaining <= 0:
                            continue
                        # Suspended after today's game? Service starts with
                        # the next game they miss.
                        if getattr(player, 'suspended_today', False):
                            player.suspended_today = False
                            continue
                        player.suspension_games_remaining = remaining - 1
                        if player.suspension_games_remaining <= 0:
                            player.suspension_games_remaining = 0
                            player.suspension_reason = ""
                            # Notify if it's the user's team
                            if hasattr(self, 'user_team') and team == self.user_team:
                                if hasattr(self, 'news_log'):
                                    self.news_log.append({'date': self.current_date, 'story': f"✅ {player.first_name} {player.last_name} has served his suspension and is eligible to return."})
                    except Exception:
                        continue
        except Exception:
            pass

    def _process_monthly_development(self):
        """Run monthly player development for all players league-wide.
        
        Young players grow toward potential; veterans decline with age.
        Notable changes for the user's team get logged as news.
        """
        if not hasattr(self, '_dev_engine'):
            self._dev_engine = PlayerDevelopmentEngine()
        
        notable = []
        for team in self.league.teams:
            # Assistant coaches: effectiveness drifts with results, mesh and
            # shelf life (icons exempt -- legacy cemented); the room feels it
            # through morale. See assistant_coaches.
            try:
                import assistant_coaches as _ac
                _st = (getattr(self.league, "standings", None) or {}).get(
                    getattr(team, "team_name", ""), {}) or {}
                _g = ((_st.get("W", 0) or 0) + (_st.get("L", 0) or 0)
                      + (_st.get("OTL", 0) or 0))
                _wp = (((_st.get("W", 0) or 0)
                        + 0.5 * (_st.get("OTL", 0) or 0)) / _g) if _g else None
                for _line in _ac.assistants_monthly_tick(team, win_pct=_wp):
                    if team == self.user_team:
                        notable.append("\U0001f4cb " + _line)
            except Exception:
                pass
            # Staff morale audit (2026-09-30): morale is a living system now
            # -- drifts toward its target from results, job security,
            # contract, ambition fit, controversy. See staff_morale.
            try:
                import staff_morale as _sm
                for _line in _sm.staff_morale_tick(team, win_pct=_wp):
                    if team == self.user_team:
                        notable.append("\U0001f4cb " + _line)
            except Exception:
                pass
            for roster_name in ('roster', 'prospects'):
                for player in getattr(team, roster_name, []) or []:
                    # team= enables the archetype/system coaching
                    # dimensions (additive; legacy formula unchanged).
                    changes = self._dev_engine.process_monthly_development(
                        player, coach=getattr(team, 'head_coach', None),
                        team=team)
                    # Item 8: season star counts nudge development -- young
                    # players starring break out, starring veterans resist
                    # decline. Additive wrapper around the engine (its
                    # internals are untouched); with no stars this is a
                    # no-op. Merged before the empty-check so a star-only
                    # month still flows into archetype refresh + news.
                    try:
                        from star_development import (
                            apply_star_monthly_nudge as _star_nudge)
                        _star_deltas = _star_nudge(player, changes)
                        for _a, _c in _star_deltas.items():
                            changes[_a] = changes.get(_a, 0) + _c
                    except Exception:
                        pass
                    if not changes:
                        continue
                    # Refresh archetype as attributes develop (e.g. prospect
                    # grows into a Power Forward)
                    try:
                        from player_archetypes import refresh_archetype
                        old_arch = getattr(player, 'archetype', None)
                        new_arch = refresh_archetype(player)
                        if (team == self.user_team and old_arch and
                                new_arch != old_arch and
                                not str(new_arch).startswith('Depth') and
                                'Backup' not in str(new_arch)):
                            notable.append(
                                f"🏒 {player.first_name} {player.last_name} "
                                f"has developed into a {new_arch}"
                            )
                    except Exception:
                        pass
                    # Track meaningful growth for user's team
                    if team == self.user_team:
                        ups = {a: c for a, c in changes.items() if c >= 2}
                        for attr, delta in ups.items():
                            notable.append(
                                f"📈 {player.first_name} {player.last_name} "
                                f"{attr.replace('_', ' ')} +{delta} (now {getattr(player, attr)})"
                            )
        
        # Cap news spam; show the most interesting ones
        for story in notable[:5]:
            if hasattr(self, 'news_log'):
                self.news_log.append({'date': self.current_date, 'story': story})
        if notable:
            print(f"📈 Monthly development: {len(notable)} notable improvements")



    def _validate_contract_terms(self, person, salary, years, extension=False,
                                   team=None):
        """Shared signing gates for every contract path (offer window,
        inbox counter-accept, MP). Returns (ok, error_message).

        One rulebook: new-CBA league-minimum salary (season-aware:
        $850k in 2026-27 rising to $1M by 2029-30), 20%-of-live-cap
        maximum, 7/6-year max term (new CBA: 7 to re-sign, 6 externally),
        live-cap budget check on CENTRAL cap accounting (not the stale
        Team.payroll / $92M PLAYER_BUDGET constant, which blocked legal
        spending up to the real cap), and the draft-eligibility lock.
        Existing contracts are grandfathered -- the minimum and term
        limits gate NEW deals only.
        """
        try:
            from salary_cap_system import league_minimum_salary as _min_fn
            _sy = getattr(getattr(self, 'league', None), 'season_year', None)
            min_salary = _min_fn(_sy)
        except Exception:
            min_salary = 775_000
        _cap_sys = getattr(getattr(self, 'league', None),
                           'salary_cap_system', None)
        _live_cap = _cap_sys.current_cap if _cap_sys else SALARY_CAP
        max_salary = int(0.20 * _live_cap)
        try:
            from salary_cap_system import max_contract_term as _mct
            max_years = _mct(extension)
        except Exception:
            max_years = 7 if extension else 6
        _team = team if team is not None else getattr(self, "user_team", None)

        try:
            salary = int(salary)
        except Exception:
            return False, "Invalid salary."
        try:
            years = int(years)
        except Exception:
            return False, "Invalid term."

        if salary < min_salary:
            return False, f"Minimum salary is ${min_salary:,}."
        if salary > max_salary:
            return False, f"Maximum salary is ${max_salary:,}."
        if years < 1 or years > max_years:
            return False, f"Maximum contract length is {max_years} years."

        # Budget check on the central cap charge (waiver shed, retention,
        # burial, dead cap all accounted). Extensions replace the player's
        # existing hit rather than stacking on top of it.
        try:
            from salary_cap_system import total_cap_charge as _tcc
            _charge = int(_tcc(_team)) if _team is not None else 0
            if extension:
                _cur = getattr(getattr(person, "contract", None),
                               "salary", 0) or 0
                _charge -= int(_cur)
            if _charge + salary > _live_cap:
                return False, ("This contract would put the club over "
                               f"the ${_live_cap:,} salary cap.")
        except Exception:
            pass

        # Draft lock: a draft-eligible player can't be signed as a free
        # agent -- that would sidestep the draft. Extensions (already under
        # club control) are unaffected.
        if not extension:
            try:
                from draft_generator import player_locked_by_draft as _locked
                if _locked(person):
                    return False, (
                        f"{getattr(person, 'full_name', 'This player')} is "
                        f"eligible for the upcoming NHL Entry Draft and "
                        f"can't be signed as a free agent. Draft him -- "
                        f"don't sidestep the rules.")
            except Exception:
                pass
        return True, ""

    # ------------------------------------------------------------------
    # AHL call-up (extracted from HockeyManagerGUI — UI-agnostic)
    # ------------------------------------------------------------------
    def _mp_client_mode(self):
        """True when running as a multiplayer client (not host)."""
        return getattr(self, 'mp_client', None) is not None \
            and getattr(self, 'mp_host', None) is None

    def call_up_to_nhl(self, player):
        """Recall a player from the AHL roster to the NHL roster.

        Returns (success: bool, message: str|None).
        UI-agnostic: no messagebox, no view updates. Callers handle UI.
        """
        if player is None:
            return False, "No player selected."
        if self._mp_client_mode():
            try:
                from windows import _mp_route as _route
                if _route(self, "call_up",
                          {"player_id": str(getattr(player, "id", ""))}):
                    return True, None
            except Exception:
                pass
        try:
            import ahl_system as _ahl_gate
            _block = _ahl_gate.ahl_recall_block_reason(player)
        except Exception:
            _block = None
        if _block:
            return False, _block
        try:
            self.user_team.ahl_roster.remove(player)
        except (ValueError, AttributeError):
            pass
        try:
            self.user_team.roster.append(player)
        except AttributeError:
            return False, "No active roster available."
        try:
            import dressing_room as _dr_arr
            _dr_arr.cascade_on_arrival(
                self.user_team, player, how="callup",
                date_str=str(getattr(self, "current_date", "")))
        except Exception:
            pass
        try:
            player.nhl_audition = {
                "goals": getattr(player, "goals", 0) or 0,
                "assists": getattr(player, "assists", 0) or 0,
                "games_played": getattr(player, "games_played", 0) or 0,
            }
        except Exception:
            try:
                player.nhl_audition = None
            except Exception:
                pass
        return True, None

    def _ui_notify(self, kind, *args, **kwargs):
        """UI notification hook. Overridden by UI subclasses.

        kind: "warning" | "error" | "info" | "contract_result"
        """
        pass

    # --- UI helper stubs (overridden by UI subclasses) ---
    # These are called by simulate_day and other game logic. The base
    # implementation routes through _ui_notify; UI subclasses override
    # with actual dialog/display implementations.


    # --- UI-compat shims (no-ops on headless GameManager) ---
    # These exist on HockeyManagerGUI; moved methods may call them.
    # Base implementations are safe no-ops; UI subclasses override.
    def update_all_views(self, *args, **kwargs):
        self._ui_notify("update_views")

    def update_news_panel(self, *args, **kwargs):
        pass

    def refresh_next_day_button(self, *args, **kwargs):
        pass

    def after_idle(self, fn, *args, **kwargs):
        """Tk's after_idle: run when idle. Headless: run immediately."""
        try:
            fn(*args, **kwargs)
        except Exception:
            pass

    def _show_continue_blockers(self, blockers, *args, **kwargs):
        """Display blocker dialog. UI subclasses override."""
        self._ui_notify("blockers", blockers)

    def _set_continue_feedback(self, busy, status=""):
        """Update continue button state. UI subclasses override."""
        self._ui_notify("continue_feedback", busy, status)

    def _mp_toast(self, msg):
        """Show multiplayer toast. UI subclasses override."""
        self._ui_notify("info", msg)

    def _mp_refresh_continue_ui(self, *args, **kwargs):
        """Refresh MP continue UI. UI subclasses override."""
        self._ui_notify("mp_refresh")

    def _maybe_open_game_day_bundle(self, *args, **kwargs):
        """Open game day bundle dialog if applicable. UI subclasses override."""
        self._ui_notify("game_day_bundle")
        return False

    def _post_advance_landing(self):
        """Handle post-advance UI landing. UI subclasses override."""
        self._ui_notify("post_advance")

    def _mp_toggle_host_ready(self):
        """Toggle host ready state. UI subclasses override."""
        self._ui_notify("mp_host_ready_toggle")

    def _mp_host_ready(self):
        """Check if host is ready. UI subclasses override."""
        return False

    def _clear_offered_clause(self, person):
        """Staged clause terms are single-use: never leak into a later deal."""
        for _attr in ("offered_clause_kind", "offered_clause_list_size"):
            try:
                if hasattr(person, _attr):
                    delattr(person, _attr)
            except Exception:
                pass

    def _execute_waiver_claim(self, player, claiming_team):
        """Complete a waiver claim transfer (shared by AI and user wins).

        Removes the player from his original club, adds him to the
        claiming club, fires the rivalry/dressing-room hooks, resets
        waiver state, and drops the claimant to the bottom of the waiver
        priority order (waiver_logic.note_waiver_claim).
        """
        original_team = next(
            (t for t in self.league.teams
             if t.team_name == player.team_name), None)
        if original_team:
            if player in original_team.roster:
                original_team.remove_player(player)
            elif hasattr(original_team, 'ahl_roster') and \
                    player in original_team.ahl_roster:
                original_team.ahl_roster.remove(player)

        # Add to claiming team
        claiming_team.add_player(player)
        player.team_name = claiming_team.team_name

        # Pending claims are spent when they resolve -- fulfilled or
        # beaten by a higher-priority club. The legacy host flag keeps its
        # behavior; client clubs track in player.mp_claim_teams.
        try:
            _user_pending = bool(getattr(player, "user_claim_pending", False))
        except Exception:
            _user_pending = False
        try:
            player.user_claim_pending = False
        except Exception:
            pass
        try:
            import game_classes as _gc
            _user_won = bool(_gc.is_human_managed(claiming_team))
        except Exception:
            _user_won = bool(getattr(claiming_team, 'is_user_team', False))
        if _user_pending and not _user_won:
            try:
                import waiver_logic as _wl
                _rank = _wl.waiver_priority_rank(
                    self.league, claiming_team, self.current_date)
                self.add_news(
                    f"Your waiver claim for {player.full_name} was beaten "
                    f"by {claiming_team.team_name} "
                    f"(waiver priority #{_rank}).")
            except Exception:
                pass
        try:
            _mp_pending = list(getattr(player, "mp_claim_teams", None) or [])
        except Exception:
            _mp_pending = []
        for _loser in _mp_pending:
            if _loser == getattr(claiming_team, "team_name", ""):
                continue
            try:
                self.add_news(
                    f"{_loser}'s waiver claim for {player.full_name} was "
                    f"beaten by {claiming_team.team_name} (priority order).")
            except Exception:
                pass
        try:
            player.mp_claim_teams = []
        except Exception:
            pass

        # Successful claim: the club drops to the bottom of the waiver
        # priority order (NHL rule -- priority spent).
        try:
            import waiver_logic as _wl
            _wl.note_waiver_claim(self.league, claiming_team)
        except Exception:
            pass

        # Rivalry lifecycle: a waiver claim is a transfer -- his
        # personal beefs follow him; ambient noise stays behind.
        try:
            from reputation_system import on_player_transfer as _opt
            _rivs = getattr(getattr(self, "league", None),
                            "rivalries", None)
            if isinstance(_rivs, list):
                _opt(_rivs, player, from_team=original_team,
                     to_team=claiming_team)
        except Exception:
            pass
        # Dressing room: the room reacts to WHO arrives, bounded.
        try:
            import dressing_room as _dr_arr
            _dr_arr.cascade_on_arrival(
                claiming_team, player, how="waiver claim",
                date_str=str(getattr(self, "current_date", "")))
        except Exception:
            pass

        # Reset waiver status
        player.on_waivers = False
        player.waiver_days = 0

        # Add to news log
        self.add_news(f"{player.full_name} claimed off waivers by {claiming_team.team_name}.")

    def _mp_propose_trade(self, params, team, manager):
        """Route a client's trade proposal: validate + resolve assets
        against canonical state, clear movement-clause waivers (the
        single-player askyesnocancel flow, over the wire), then send the
        offer to an AI club, the host's club, or another human's club."""
        import trade_engine as te
        partner = self._mp_find_team(params.get("partner_team_id", ""))
        if partner is None:
            return False, "Unknown partner team."
        if partner is team:
            return False, "You can't trade with yourself."
        # Event boundary: the trade freeze / deadline applies to MP
        # proposals exactly like the SP trade UI (te.trades_allowed).
        try:
            if not te.trades_allowed(str(getattr(self, "current_date", "")),
                                     getattr(self, "league", None)):
                return False, ("Trading is frozen right now "
                               "(trade freeze / deadline).")
        except Exception:
            pass
        offer = params.get("offer") or {}
        if not isinstance(offer, dict):
            return False, "Malformed offer."

        def _ids(key):
            v = offer.get(key) or []
            return [str(x) for x in v] if isinstance(v, list) else []

        out_pids, in_pids = _ids("players_out"), _ids("players_in")
        out_kids, in_kids = _ids("picks_out"), _ids("picks_in")
        if not out_pids and not out_kids:
            return False, "You're not offering anything."
        if not in_pids and not in_kids:
            return False, "You're not asking for anything."
        out_players = [self._mp_team_player(team, pid) for pid in out_pids]
        in_players = [self._mp_team_player(partner, pid) for pid in in_pids]
        out_picks = [self._mp_team_pick(team, kid) for kid in out_kids]
        in_picks = [self._mp_team_pick(partner, kid) for kid in in_kids]
        if any(p is None for p in out_players):
            return False, "One of your offered players isn't on your roster."
        if any(p is None for p in in_players):
            return False, \
                "One of the requested players isn't on their roster."
        if any(k is None for k in out_picks):
            return False, "One of your offered picks isn't yours."
        if any(k is None for k in in_picks):
            return False, "One of the requested picks isn't theirs."
        retention = {}
        for pid, pct in (offer.get("retention") or {}).items():
            try:
                pct = float(pct)
            except (TypeError, ValueError):
                return False, "Invalid retention term."
            if not 0 < pct <= 50:
                return False, "Retention must be 1-50%."
            if str(pid) not in out_pids:
                return False, "Retention on a player you're not moving."
            retention[str(pid)] = pct
        protection = {}
        for kid, prot in (offer.get("pick_protection") or {}).items():
            if prot not in ("", "top-3", "top-10", "lottery"):
                return False, f"Unknown pick protection: {prot}."
            if prot and str(kid) not in out_kids:
                return False, "Protection on a pick you're not moving."
            if prot:
                protection[str(kid)] = prot

        proposal = {
            "proposer_team_id": team.team_name,
            "partner_team_id": partner.team_name,
            "manager": manager,
            "players_out": out_pids,
            "players_in": in_pids,
            "picks_out": out_kids,
            "picks_in": in_kids,
            "retention": retention,
            "pick_protection": protection,
        }
        # Movement-clause preflight on the proposer's own players, exactly
        # like the trade screen's askyesnocancel: ask him / remove him /
        # cancel. Over the wire this becomes NTC_WAIVER_REQUEST prompts.
        league = getattr(self, "league", None)
        try:
            vetoes = te.trade_vetoes(team, partner, out_players, league)
        except Exception:
            vetoes = []
        if vetoes:
            return self._mp_begin_waiver_flow(proposal, team, partner,
                                              vetoes, manager)
        return self._mp_route_trade_offer(proposal)

    def accept_contract_counter(self, message):
        """Inbox action: accept the agent's counter-offer as-is."""
        data = message.action_data or {}
        # MP: route to host instead of mutating the snapshot.
        if self._mp_client_mode():
            from windows import _mp_route as _route
            _pid = str(getattr(self._find_inbox_player(data), "id", ""))
            if _route(self, "extend_contract", {
                    "player_id": _pid,
                    "salary": data.get("asking_price", 0),
                    "years": data.get("years", 1),
            }):
                message.action_done = True
                return True
        person = self._find_inbox_player(data)
        if person is None:
            message.action_done = True
            return False
        asking = data.get("asking_price", 0)
        years = data.get("years", 1)
        extension = data.get("is_extension", False)
        # The counter travels through the same gates as a fresh offer:
        # an agent can't smuggle in a sub-minimum, over-max, over-term,
        # over-cap, or draft-sidestepping deal via the inbox.
        ok, err = self._validate_contract_terms(person, asking, years,
                                                extension=bool(extension))
        if not ok:
            self._inbox_contract_result(
                "rejected", person,
                getattr(person, "full_name", "The player"),
                asking, years, asking, extension,
                clause_kind="none", clause_list_size=10,
                reject_note=(
                    f"The league office rejected {getattr(person, 'full_name', 'the player')}'s "
                    f"counter-offer of ${int(asking):,} x {int(years)} year(s): {err}\n\n"
                    f"Illegal terms can't be filed -- his camp will need to come back "
                    f"with a compliant number."))
            message.action_done = True
            return False
        # The clause the user offered travels with the counter: re-stage it
        # so the signed deal carries the protection, then clear (single-use).
        person.offered_clause_kind = data.get("clause_kind", "none") or "none"
        try:
            person.offered_clause_list_size = int(
                data.get("clause_list_size", 10) or 10)
        except Exception:
            person.offered_clause_list_size = 10
        # UFA consideration period (Muck 2026-10-02): accepting the
        # counter opens a bidding window -- it doesn't sign instantly.
        # Extensions keep the instant path.
        if not extension:
            try:
                import ufa_consideration as _uc
                _cons = _uc.submit_ufa_offer(
                    self, getattr(self, "league", None), person,
                    getattr(self, "user_team", None),
                    asking, years, is_user=True,
                    clause_kind=person.offered_clause_kind,
                    clause_size=person.offered_clause_list_size)
                if _cons is not None:
                    _uc.notify_consideration_started(
                        self, person, asking, years,
                        int(_cons.get("days_left", 4) or 4))
                    self._clear_offered_clause(person)
                    message.action_done = True
                    return True
            except Exception:
                pass
        self._finalize_contract_signing(person, asking, years, asking,
                                        extension)
        self._inbox_contract_result("accepted", person,
                                    getattr(person, "full_name", "The player"),
                                    asking, years, asking, extension,
                                    clause_kind=person.offered_clause_kind,
                                    clause_list_size=
                                    person.offered_clause_list_size)
        self._clear_offered_clause(person)
        message.action_done = True
        return True

    def add_news(self, story):
        """Add a news item to the news log."""
        self.news_log.append({'date': self.current_date, 'story': story})
        # Mirror into the canonical list that save files and multiplayer
        # snapshots carry, so every manager sees the same league lore.
        stories = None
        try:
            gm = getattr(self, 'game_manager', None)
            stories = getattr(gm, 'news_stories', None)
            if stories is None and gm is not None:
                gm.news_stories = stories = []
            if stories is not None:
                d = self.current_date
                stories.append({'date': d.isoformat() if hasattr(d, 'isoformat') else d,
                                'story': story})
        except Exception:
            pass
        # Bound the feed: keep the most recent stories so the log (and the
        # save file) can't grow unbounded across seasons.
        try:
            import headlines as _hl
            cap = _hl.NEWS_LOG_CAP
        except Exception:
            cap = 500
        if stories is not None and len(stories) > cap:
            del stories[:len(stories) - cap]
        if len(self.news_log) > cap:
            del self.news_log[:len(self.news_log) - cap]
        # Notify UI to refresh news displays (no-op headless)
        self._ui_notify("news_updated")

    def apply_arbitration_walkaway_decision(self, message, walk_away):
        """Inbox action: walk away from an arbitration award (48h window)."""
        # MP: route to the host (authoritative).
        if self._mp_client_mode():
            from windows import _mp_route as _route
            if _route(self, "arbitration_walkaway", {
                    "message_id": str(getattr(message, "id", "")),
                    "walk_away": bool(walk_away)}):
                message.action_done = True
                return True
            return False
        import rfa_system as _rfa
        data = message.action_data or {}
        aav = int(data.get("award_aav", 0) or 0)
        term = int(data.get("term_years", 1) or 1)
        player_id = data.get("player_id")
        if not walk_away:
            # Accept: sign at the awarded terms.
            person = self._find_inbox_player(data)
            if person is not None:
                c = getattr(person, "contract", None)
                if c is not None:
                    c.salary = aav
                    c.years_remaining = term
        res = _rfa.apply_walk_away(
            self, self.league, self.user_team, player_id, bool(walk_away))
        if res.get("ok"):
            message.action_done = True
        try:
            self.update_all_views()
        except Exception:
            pass
        return bool(res.get("ok"))

    def apply_buyout_decision(self, message, player_id, buyout):
        """Inbox action: buy out (or keep) one flagged contract.

        The message itself is the June 15-30 window authorization, so --
        like the RFA actions -- this does NOT re-check the calendar gate
        in transaction_windows (the user may resolve it after July 1).
        """
        # MP: route to host (buyout_player protocol action exists).
        if self._mp_client_mode():
            from windows import _mp_route as _route
            _data = getattr(message, "action_data", None) or {}
            _person = self._find_inbox_player(_data)
            if _route(self, "buyout_player", {
                    "player_id": str(getattr(_person, "id", "")),
            }):
                message.action_done = True
                return True
        import buyout_window as _bw
        data = message.action_data or {}
        ok = False
        if buyout:
            person = self._find_inbox_player({"player_id": player_id})
            team = getattr(self, "user_team", None)
            if person is not None and team is not None \
                    and person in (getattr(team, "roster", None) or []):
                try:
                    season_year = int(data.get("season_year") or
                                     getattr(self.league, "season_year", 2026)
                                     or 2026)
                    total, annual, byears, _rows = _bw.execute_buyout(
                        self.league, team, person,
                        season_year=season_year)
                    ok = True
                    # D4: buying out a star is a board headline.
                    try:
                        import reputation_system as _rs4b
                        _rs4b.note_star_departure(
                            getattr(getattr(self, "career", None),
                                    "board", None), person)
                    except Exception:
                        pass
                    try:
                        self.add_news(
                            f"✂️ You bought out "
                            f"{getattr(person, 'full_name', 'a player')} "
                            f"(${int(total):,} over {int(byears)} years).")
                    except Exception:
                        pass
                except Exception:
                    ok = False
            else:
                ok = False
        else:
            ok = True  # "Keep" is always a valid decision
        decided = data.get("decided", {}) or {}
        decided[str(player_id)] = bool(buyout)
        data["decided"] = decided
        message.action_data = data
        cards = data.get("cards", []) or []
        if len(decided) >= len(cards):
            message.action_done = True
        try:
            self.update_all_views()
        except Exception:
            pass
        return ok

    def apply_offer_sheet_match_decision(self, message, match):
        """Inbox action: match an offer sheet or take the pick compensation."""
        # MP: route to the host (authoritative).
        if self._mp_client_mode():
            from windows import _mp_route as _route
            if _route(self, "offer_sheet_match", {
                    "message_id": str(getattr(message, "id", "")),
                    "match": bool(match)}):
                message.action_done = True
                return True
            return False
        import rfa_system as _rfa
        data = message.action_data or {}
        res = _rfa.apply_offer_sheet_match(
            self, self.league, data.get("player_id"), bool(match))
        if res.get("ok"):
            message.action_done = True
        try:
            self.update_all_views()
        except Exception:
            pass
        return bool(res.get("ok"))

    def apply_offer_sheet_trade_alt_decision(self, message, accept):
        """Inbox action: accept the sign-and-trade package or take the
        pick compensation on a declined offer sheet."""
        # MP: route to the host (authoritative).
        if self._mp_client_mode():
            from windows import _mp_route as _route
            if _route(self, "offer_sheet_trade_alt", {
                    "message_id": str(getattr(message, "id", "")),
                    "accept": bool(accept)}):
                message.action_done = True
                return True
            return False
        import rfa_system as _rfa
        data = message.action_data or {}
        res = _rfa.apply_offer_sheet_trade_alt(
            self, self.league, data.get("player_id"), bool(accept))
        if res.get("ok"):
            message.action_done = True
        try:
            self.update_all_views()
        except Exception:
            pass
        return bool(res.get("ok"))

    def apply_rfa_qualifying_decision(self, message, player_id, qualify):
        """Inbox action: extend or decline a qualifying offer for one RFA."""
        # MP: route to the host (authoritative); the host marks the
        # canonical message done so the sync retires the buttons.
        if self._mp_client_mode():
            from windows import _mp_route as _route
            if _route(self, "rfa_qualify", {
                    "message_id": str(getattr(message, "id", "")),
                    "player_id": str(player_id),
                    "qualify": bool(qualify)}):
                data = message.action_data or {}
                decided = data.get("decided", {}) or {}
                decided[str(player_id)] = bool(qualify)
                data["decided"] = decided
                message.action_data = data
                cards = data.get("cards", []) or []
                if len(decided) >= len(cards):
                    message.action_done = True
                return True
            return False
        import rfa_system as _rfa
        data = message.action_data or {}
        res = _rfa.apply_qualifying_decision(
            self, self.league, self.user_team, player_id, bool(qualify))
        decided = data.get("decided", {}) or {}
        decided[str(player_id)] = bool(qualify)
        data["decided"] = decided
        message.action_data = data
        cards = data.get("cards", []) or []
        if len(decided) >= len(cards):
            message.action_done = True
        try:
            self.update_all_views()
        except Exception:
            pass
        return bool(res.get("ok"))

    def apply_staff_renewal_decision(self, message, staff_id, years):
        """Inbox action: re-sign an expired staffer (years=1/2/3) or let
        him walk to the free-agent pool (years=None).

        The D5 tick held him employed pending this decision, so the club
        is never caught short mid-decision; a walked head coach triggers
        the in-house promote fallback, exactly like the automatic path.
        """
        # MP: route to the host (authoritative).
        if self._mp_client_mode():
            from windows import _mp_route as _route
            if _route(self, "staff_renew", {
                    "message_id": str(getattr(message, "id", "")),
                    "staff_id": str(staff_id),
                    "years": years}):
                data = message.action_data or {}
                decided = data.get("decided", {}) or {}
                decided[str(staff_id)] = years
                data["decided"] = decided
                message.action_data = data
                offers = data.get("offers", []) or []
                if len(decided) >= len(offers):
                    message.action_done = True
                return True
            return False
        import staff_renewals as _sr
        data = message.action_data or {}
        try:
            ok, lines = _sr.apply_renewal_decision(
                self.league, staff_id, years)
        except Exception:
            ok, lines = False, []
        decided = data.get("decided", {}) or {}
        decided[str(staff_id)] = years
        data["decided"] = decided
        message.action_data = data
        offers = data.get("offers", []) or []
        if len(decided) >= len(offers):
            message.action_done = True
        for _ln in lines or []:
            try:
                _emo = "✍️ " if years else "🚶 "
                self.add_news(_emo + str(_ln))
            except Exception:
                pass
        try:
            self.update_all_views()
        except Exception:
            pass
        return ok

    def calculate_player_value(self, player):
        """Calculate a player's trade value based on attributes, age, contract, etc."""
        # Base value based on overall rating
        base_value = player.overall_rating() * 100000
        
        # Adjust for potential
        potential_multiplier = {
            'A': 1.5,
            'B': 1.3,
            'C': 1.1,
            'D': 0.9,
            'F': 0.7
        }.get(player.potential_grade, 1.0)
        
        # Age adjustment - younger players are more valuable
        age_factor = max(0.5, 1.2 - (player.age - 22) * 0.03)  # Peaks at age 22
        
        # Contract adjustment - lower salary and longer term is better
        contract_factor = 1.0
        if player.contract.years_remaining > 0:
            # Value cheaper contracts higher
            _lc = self.get_live_cap()
            salary_cap_percentage = player.contract.salary / _lc if _lc else 0
            if salary_cap_percentage < 0.05:  # Less than 5% of cap
                contract_factor = 1.3
            elif salary_cap_percentage < 0.1:  # Less than 10% of cap
                contract_factor = 1.2
            elif salary_cap_percentage > 0.15:  # More than 15% of cap
                contract_factor = 0.8
                
            # Longer contracts for good players add value, for poor players reduce value
            if player.overall_rating() >= 85 and player.contract.years_remaining >= 3:
                contract_factor *= 1.2
            elif player.overall_rating() < 75 and player.contract.years_remaining >= 3:
                contract_factor *= 0.8
        else:
            # Unsigned players are worth less in trades
            contract_factor = 0.7
        
        # Position adjustment - goalies and centers tend to be more valuable
        position_factor = 1.0
        if player.primary_position == PlayerPosition.GOALIE:
            position_factor = 1.3
        elif player.primary_position == PlayerPosition.CENTER:
            position_factor = 1.15
            
        # Production adjustment - players who score more are more valuable
        production_factor = 1.0
        if player.stats.goals > 20 or player.stats.points > 50:
            production_factor = 1.25
            
        # Calculate final value
        final_value = int(base_value * potential_multiplier * age_factor * contract_factor * position_factor * production_factor)
        
        return final_value

    def get_continue_state(self):
        """Football Manager-style continue state.

        Returns (label, blockers):
          - ("Continue", [blockers]) when pressing tasks must be completed
            before the day can advance.
          - ("Next Day", []) when the day can advance freely.

        Each blocker is a dict with 'id', 'title', 'detail' and an optional
        'action' tuple (button label, callable) that takes the user to the
        blocking task. Only REAL systems in this codebase are checked --
        nothing is invented.
        """
        # Timing for web UI performance debugging (2026-10-06)
        import time as _time
        _t_start = _time.time()
        def _tlog(_label):
            try:
                print(f"[blocker-timing] {_label}: {_time.time() - _t_start:.2f}s")
            except Exception:
                pass
        blockers = []
        gm = getattr(self, 'game_manager', None)
        _tlog('start')
        # The one hard day-advancement blocker in the codebase: an active
        # fantasy draft must be finished before the calendar can move.
        if gm is not None and getattr(gm, 'pending_fantasy_draft', False):
            blockers.append({
                'id': 'fantasy_draft',
                'title': 'Fantasy draft in progress',
                'detail': ('You must complete the fantasy draft before '
                           'advancing the day.'),
                'action_id': 'fantasy_draft',
                'action_label': 'Open Fantasy Draft',
            })
        _tlog('fantasy_draft_done')
        # DRAFT AGENCY (Muck 2026-10-02): a parked entry draft with unmade
        # user picks blocks the day -- the rebuild's keystone moment never
        # auto-resolves. The action opens the war room directly.
        try:
            _lg = getattr(self, 'league', None)
            _sess = getattr(_lg, 'entry_draft_session', None) if _lg else None
            if _sess is not None:
                try:
                    from draft_night import EntryDraftSession as _EDS
                    _is_sess = isinstance(_sess, _EDS)
                except Exception:
                    _is_sess = False
                if _is_sess and not _sess.is_complete():
                    try:
                        _ut = getattr(self, 'user_team', None)
                        _uname = getattr(_ut, 'team_name', '') if _ut else ''
                    except Exception:
                        _uname = ''
                    _upicks = []
                    if _uname:
                        try:
                            _made = {int(p.get('overall', -1))
                                     for p in (_sess.picks or [])}
                        except Exception:
                            _made = set()
                        for _slot in (_sess.slots or []):
                            try:
                                if (str(_slot.get('owner', '')) == _uname
                                        and int(_slot.get('overall', -1))
                                        not in _made):
                                    _upicks.append(int(_slot.get('overall')))
                            except Exception:
                                continue
                    if _upicks:
                        _upicks.sort()
                        blockers.append({
                            'id': 'entry_draft',
                            'title': 'Entry draft awaiting your picks',
                            'detail': (
                                f"You hold {len(_upicks)} pick"
                                f"{'s' if len(_upicks) != 1 else ''} in the "
                                f"{getattr(_sess, 'year', '')} NHL Entry Draft "
                                f"(first: #{_upicks[0]} overall). Your picks "
                                f"are never auto-drafted -- make them in the "
                                f"war room or Sim Pick via your head scout."),
                            'action_id': 'entry_draft',
                            'action_label': 'Open Draft War Room',
                        })
        except Exception:
            pass
        _tlog('entry_draft_done')
        # Salary cap compliance: an over-cap roster must shed salary before
        # the day can advance (real NHL rule -- rosters must be cap-compliant).
        try:
            cap_blocker = self._cap_compliance_blocker()
            if cap_blocker:
                blockers.append(cap_blocker)
        except Exception:
            pass
        _tlog('salary_cap_done')
        # D46 (Wave B): the salary floor is a hard league rule -- the day
        # can't advance while the club sits under it.
        try:
            floor_blocker = self._floor_compliance_blocker()
            if floor_blocker:
                blockers.append(floor_blocker)
        except Exception:
            pass
        _tlog('salary_floor_done')
        # R1 (roster limits, true NHL): the 23-man active max and the
        # dressed-lineup minimum (18+2) are hard day gates for the user --
        # the AI side is kept compliant by ai_roster_compliance. The 50 SPC
        # total is advisory only (Chris's call 2026-10-02): only cap +
        # active roster block games. Guarded
        # import so a roster_limits bug can never break day advancement.
        try:
            import roster_limits as _rl
            blockers.extend(_rl.roster_limit_blockers(self))
        except Exception:
            pass
        # Item 7 follow-up: the human club must wear exactly 1 C + 2 As --
        # chosen by the user, never auto-repaired -- before the day can
        # advance. The action opens the mandatory picker directly.
        # Fantasy-draft deferral: after the draft, rosters are letter-less
        # by design until the first preseason game day arms the picker, so
        # the blocker stays suppressed for that window.
        try:
            if gm is not None and not gm._captaincy_blocker_suppressed():
                _ut = getattr(gm, 'user_team', None)
                if _ut is not None and (
                        getattr(gm, '_captaincy_choice_pending', False)
                        or gm._captaincy_needs_choice(_ut)):
                    if not gm._captaincy_mandatory_window_open(_ut):
                        # R1(a): season already underway -- the mandatory
                        # picker must never fire mid-season, so it can
                        # never block day advancement either. Repair
                        # quietly (idempotent) instead of appending a
                        # blocker.
                        try:
                            gm._ensure_captaincy(_ut)
                        except Exception:
                            pass
                        gm._captaincy_choice_pending = False
                    else:
                        def _auto_captains(_t=_ut, _app=self):
                            """Auto-resolve: pick C + 2 As by leadership/tenure."""
                            try:
                                from auto_resolve import auto_choose_captains
                                result, err = auto_choose_captains(_t)
                                if err:
                                    _app.add_news(
                                        f"Auto-captaincy failed: {err}")
                                    return
                                cap, alts = result
                                # Apply via player.captaincy ('C'/'A'/None),
                                # then clear any stale letters first.
                                try:
                                    for _p in (getattr(_t, 'roster', None)
                                               or []):
                                        if getattr(_p, 'captaincy', '') in (
                                                'C', 'A'):
                                            _p.captaincy = ''
                                except Exception:
                                    pass
                                cap.captaincy = 'C'
                                for _a in alts:
                                    _a.captaincy = 'A'
                                try:
                                    gm._captaincy_choice_pending = False
                                except Exception:
                                    pass
                                _names = ", ".join(
                                    getattr(p, 'full_name', '?')
                                    for p in alts)
                                _app.add_news(
                                    f"Auto-named captains: C "
                                    f"{getattr(cap, 'full_name', '?')}, As "
                                    f"{_names}.")
                            except Exception as e:
                                try:
                                    _app.add_news(
                                        f"Auto-captaincy failed: {e}")
                                except Exception:
                                    pass
                        blockers.append({
                            'id': 'captaincy_choice',
                            'title': 'Name your captains',
                            'detail': ('NHL Rule 6.1: your club needs exactly one '
                                       'captain (C) and two alternates (A) before '
                                       'the season can continue.'),
                            'action': ('Choose Captains',
                                       lambda: gm._require_captaincy_choice(_ut)),
                            'auto_action': ('Auto-pick Captains', _auto_captains),
                        })
        except Exception:
            pass
        # Pre-season coach expectations meeting (Eastside-style, non-modal):
        # the user can navigate anywhere; only day-advance is gated until
        # the meeting is held. The blocker dict is built by
        # coach_season_meeting.season_meeting_blocker (None when nothing is
        # pending); _show_continue_blockers presents it automatically.
        try:
            from coach_season_meeting import season_meeting_blocker
            _sm_blocker = season_meeting_blocker(self)
            if _sm_blocker:
                blockers.append(_sm_blocker)
        except Exception:
            pass
        if blockers:
            _tlog('done_with_blockers')
            return ("Continue", blockers)
        # SLATE GUARANTEE, Part 2 (2026-10-02): a short season slate is a
        # hard stop -- the season cannot advance into awards/playoffs with
        # missing games. Armed by _handle_slate_shortfall (GUI mode); no
        # user action can clear it -- the detail names the short clubs and
        # says to report it -- so there is deliberately no 'action' jump.
        # Dismissing the card never clears it: it persists until the data
        # is repaired.
        try:
            _sis = getattr(self, '_season_integrity_shortfall', None)
            if _sis:
                if isinstance(_sis, list):
                    _sis_det = "; ".join(
                        f"{_n} {_gp}/{_t} (short {_t - _gp})"
                        for _n, _gp, _t in _sis)
                else:
                    _sis_det = ("One or more clubs finished short of the "
                                "scheduled slate.")
                blockers.append({
                    'id': 'season_integrity',
                    'title': 'Season slate incomplete -- season halted',
                    'detail': ("The regular season ended with clubs short "
                               "of their scheduled games: "
                               f"{_sis_det}. This is a data-integrity stop, "
                               "not a task to complete -- report it so the "
                               "missing games can be investigated. The "
                               "season will not advance."),
                })
        except Exception:
            pass
        # Gating T2-Phase 2: the pending-items registry is the unified read
        # path. BLOCKS_ADVANCE and PAUSES_DAY entries gate the day exactly
        # like the hardcoded blockers above; RESUMABLE entries never block
        # (they surface via resume chips). No Tier-2 dialog may register a
        # BLOCKS_ADVANCE entry -- dialogs never block the day, their parent
        # flows might.
        try:
            from popup_system import (get_pending_items as _gpi,
                                      BLOCKS_ADVANCE as _BA,
                                      PAUSES_DAY as _PD)
            for _it in _gpi(self, kinds=(_BA, _PD)):
                _iid = _it.get("id")
                if any(b.get("id") == _iid for b in blockers):
                    continue
                _screen = _it.get("screen_id")

                def _jump(_s=_screen):
                    try:
                        self.show_screen(_s)
                    except Exception:
                        pass
                    # The question is waiting where it was left: re-present
                    # any unanswered card parked for that screen.
                    try:
                        from popup_system import represent_screen_questions
                        represent_screen_questions(self, _s, parent=self)
                    except Exception:
                        pass

                blockers.append({
                    "id": _iid,
                    "title": _it.get("title", "Pending item"),
                    "detail": _it.get("detail", ""),
                    "action": ("Go to it", _jump),
                })
        except Exception:
            pass
        if blockers:
            return ("Continue", blockers)
        # Trade deadline day: the day runs on a 30-minute game clock
        # (9:00 AM -> 3:00 PM ET). Each press advances the clock one
        # increment -- instant AI answers, league deals, countdown.
        try:
            if self.is_trade_deadline_day():
                from trade_deadline_manager import get_deadline_manager
                _mgr = get_deadline_manager(self.game_manager)
                if not _mgr.clock_active(self.current_date):
                    return ("Deadline Day", [])
                if not _mgr._clock_store().get('expired'):
                    return (f"+30m ({_mgr.clock_display()})", [])
        except Exception:
            pass
        # Game-day label: pressing it opens the game-day inbox bundle
        # (presser + team talk + Watch/Quick choice) instead of simming.
        try:
            if (self._career_prompts_allowed()
                    and not getattr(self, '_game_day_resolution', None)
                    and self._is_user_game_day()):
                return ("Game Day", [])
        except Exception:
            pass
        return ("Next Day", [])

    def handle_elc_offer(self, player, salary, signing_bonus=0,
                         performance_bonus=0, team=None):
        """Negotiated ELC signing with an unsigned rights-held prospect.

        Validates the ELC band (base inside [floor, ceiling], signing
        bonus <= 10% of base, performance bonus <= $1M/yr), runs the
        prospect handshake (accept / counter / reject), and on acceptance
        finalizes through the league's canonical ELC path: contract with
        bonuses, rights consumed, assigned to junior/AHL by eligibility.

        Returns {verdict, counter, note}. "counter" carries the agent's
        number for one-click acceptance in the view.
        """
        import salary_cap_system as _scs
        league = getattr(self, 'league', None)
        # MP: the host passes the acting manager's team; single-player and
        # the host's own UI leave it None and use user_team as before.
        if team is None:
            team = getattr(self, 'user_team', None)
        try:
            season = getattr(league, 'season_year', None)
        except Exception:
            season = None
        # Guard: only the user's unsigned rights-held prospect.
        try:
            _own = (getattr(player, 'contract', None) is None
                    and (getattr(player, 'rights_team', '') or '')
                    == getattr(team, 'team_name', ''))
        except Exception:
            _own = False
        if not _own or league is None or team is None:
            return {"verdict": "invalid", "counter": None,
                    "note": "He isn't your unsigned prospect."}
        try:
            age = int(getattr(player, 'age', 20) or 20)
        except Exception:
            age = 20
        # CBA 9.2: ELC term and eligibility use the player's age on
        # September 15 of the signing year, not his current age.
        try:
            _s15 = _age_on_sept15(getattr(player, 'birth_date', ''), season)
        except Exception:
            _s15 = None
        _elc_age = _s15 if _s15 is not None else age
        floor, ceil, years = _scs.elc_band(_elc_age, season)
        if years <= 0:
            return {"verdict": "invalid", "counter": None,
                    "note": ("He isn't ELC-eligible: at 25+, the Entry "
                             "Level System no longer applies (new CBA -- "
                             "the old European 25-27 exception is gone). "
                             "Sign him to a standard contract instead.")}
        try:
            salary = int(salary)
            signing_bonus = int(signing_bonus or 0)
            performance_bonus = int(performance_bonus or 0)
        except Exception:
            return {"verdict": "invalid", "counter": None,
                    "note": "Bonuses must be numbers."}
        max_signing = int(round(salary * _scs.ELC_SIGNING_BONUS_PCT))
        if not (floor <= salary <= ceil):
            return {"verdict": "invalid", "counter": None,
                    "note": (f"ELC base must sit inside the band "
                             f"${floor:,} - ${ceil:,}/yr.")}
        if not (0 <= signing_bonus <= max_signing):
            return {"verdict": "invalid", "counter": None,
                    "note": (f"Signing bonus is capped at 10% of base "
                             f"(${max_signing:,}/yr).")}
        if not (0 <= performance_bonus <= _scs.ELC_PERF_BONUS_MAX):
            return {"verdict": "invalid", "counter": None,
                    "note": (f"Performance bonus is capped at "
                             f"${_scs.ELC_PERF_BONUS_MAX:,}/yr.")}
        # 9.3(a): base salary + signing bonus (+ games-played bonuses,
        # not modeled) may not exceed the max annual compensation.
        # Schedule-A performance bonuses are capped separately.
        if salary + signing_bonus > _scs.elc_max_annual_comp(season):
            return {"verdict": "invalid", "counter": None,
                    "note": (f"Base + signing bonus may not exceed the ELC "
                             f"max of "
                             f"${_scs.elc_max_annual_comp(season):,}/yr.")}
        ask = _scs.elc_prospect_ask(player, season)
        res = _scs.elc_handshake(ask, salary, signing_bonus,
                                 performance_bonus)
        if res["verdict"] != "accepted":
            return res
        try:
            ok = bool(league.finalize_elc_signing(
                team, player, salary, years, signing_bonus,
                performance_bonus))
        except Exception:
            ok = False
        if not ok:
            return {"verdict": "invalid", "counter": None,
                    "note": "The signing couldn't be completed."}
        try:
            self.add_news(
                f"{player.full_name} signs an entry-level contract with "
                f"{getattr(team, 'team_name', 'the club')} "
                f"(${salary:,}/yr x {years} yrs, ${signing_bonus:,} signing "
                f"bonus, ${performance_bonus:,}/yr in performance bonuses).")
        except Exception:
            pass
        try:
            self.update_all_views()
        except Exception:
            pass
        return {"verdict": "accepted", "counter": None,
                "note": (f"Signed: ${salary:,}/yr x {years} yrs "
                         f"(+${signing_bonus:,} SB, "
                         f"+${performance_bonus:,}/yr perf). He'll report to "
                         f"{getattr(player, 'playing_where', 'the minors')}.")}

    def open_fantasy_draft_window(self):
        """Open the Fantasy Draft window. UI-agnostic: routes via _ui_notify."""
        self._ui_notify("open_fantasy_draft")

    def process_trade_block_offers(self):
        """Process trade offers for players on the trade block."""
        if not self.trade_block:
            return  # No players on trade block
            
        # Trade offer tracking
        offers_received = []
        
        # For each player on the trade block
        for player in self.trade_block:
            # Calculate player's base value
            base_value = self.calculate_player_value(player)
            
            # Apply discount for being on trade block (teams know you want to move them)
            trade_block_discount = 0.85  # 15% discount
            discounted_value = int(base_value * trade_block_discount)
            
            # Get teams potentially interested in the player
            interested_teams = []
            for team in self.league.teams:
                if team == self.user_team:
                    continue
                    
                # Check if team needs this position
                pos_count = sum(1 for p in team.roster if p.primary_position == player.primary_position)
                pos_need = pos_count < 3
                
                # Check cap space
                has_cap_space = team.cap_space > player.contract.salary
                
                # Check if team is looking to improve (based on standings)
                team_stats = self.league.standings.get(team.team_name, {'Points': 0})
                try:
                    team_rank = sorted(self.league.standings.values(), 
                                     key=lambda x: x['Points'], 
                                     reverse=True).index(team_stats)
                    is_improving = team_rank > 16  # Bottom half of the league
                except ValueError:
                    is_improving = True  # Default to improving if team not found in standings
                
                # Calculate interest factor based on team needs
                interest_level = 0
                
                if pos_need:
                    interest_level += 30
                    
                if has_cap_space:
                    interest_level += 20
                    
                if is_improving:
                    interest_level += 20
                    
                # Adjust based on player quality relative to team
                team_avg_ovr = sum(p.overall_rating() for p in team.roster) / len(team.roster) if team.roster else 70
                if player.overall_rating() > team_avg_ovr + 5:
                    interest_level += 30
                    
                # Positional need based on team composition
                if player.primary_position == PlayerPosition.GOALIE and pos_count == 0:
                    interest_level += 50  # Teams desperately need goalies
                
                # Teams more interested in younger players with potential
                if player.age < 25 and player.potential_grade in ['A', 'B']:
                    interest_level += 25
                
                # Track interested teams with their interest level
                if interest_level >= 50 and has_cap_space:  # Only consider teams with significant interest
                    interested_teams.append((team, interest_level))
            
            # Sort teams by interest level
            interested_teams.sort(key=lambda x: x[1], reverse=True)
            
            # Have interested teams make offers
            for team, interest_level in interested_teams[:3]:  # Top 3 interested teams
                # Generate an offer based on interest level
                willingness_to_pay = 1.0 + (interest_level - 50) / 100  # 1.0 to 1.5 based on interest
                offer_value = int(discounted_value * willingness_to_pay)
                
                # Prepare trade package
                trade_package = self.generate_trade_package(team, player, offer_value)
                
                if trade_package:
                    offers_received.append({
                        'team': team,
                        'player_wanted': player,
                        'offer': trade_package,
                        'interest_level': interest_level
                    })
        
        # If offers were received, present them to the user
        if offers_received:
            self.present_trade_offers(offers_received)

    def send_email_to_user(self, message):
        """Send an email message to the user's inbox."""
        self.user_team.inbox.add_message(message)
        self.update_inbox_notification()

    def simulate_day(self):
        """Completely reworked daily simulation that properly handles all scenarios"""
        # MULTIPLAYER (Phase 2) advance gate: in host mode the day advances
        # ONLY through the EHM ready gate (_mp_fire_authorized_advance sets
        # _mp_advance_authorized). Any other path into here becomes a ready
        # vote instead. Clients never advance -- they vote via Ready.
        if getattr(self, 'mp_host', None) is not None \
                and not getattr(self, '_mp_advance_authorized', False):
            self._mp_toggle_host_ready()
            return
        if getattr(self, 'mp_client', None) is not None \
                and getattr(self, 'mp_host', None) is None:
            self._mp_toast("Only the host advances days -- "
                           "use Ready to vote for the advance.")
            return
        # BLOCKERS FIRST: pressing tasks (e.g. an active fantasy draft) must
        # be completed before the day advances. Show what is blocking and
        # offer a jump to it -- never silently do nothing.
        _label, blockers = self.get_continue_state()
        if blockers:
            # A blocker that appeared after the host readied must rescind
            # the vote -- the day can't advance like this.
            if getattr(self, '_mp_host_ready', False):
                self._mp_host_ready = False
                try:
                    _payload = self.mp_host.broadcast_advance_status(False)
                except Exception:
                    _payload = None
                self._mp_refresh_continue_ui(_payload)
            self._show_continue_blockers(blockers)
            return

        # Prevent double-clicks: the dashboard helper also paints
        # "Processing..." BEFORE the heavy work starts.
        dashboard = getattr(self, 'dashboard', None)
        if (dashboard is not None
                and getattr(getattr(dashboard, 'continue_btn', None), '_enabled', True) is False):
            return  # Already processing, ignore this click
        self._set_continue_feedback(True, "Starting simulation...")

        # TRADE DEADLINE DAY: the day runs on a 30-minute game clock
        # (9:00 AM -> 3:00 PM ET) instead of a full-day sim. Each press of
        # Continue advances the clock one increment: AI GMs answer trade
        # talks instantly, league deals break, and the countdown ticks
        # toward the 3 PM close. When the clock expires the day finishes
        # normally (games sim, date advances).
        if self._maybe_run_deadline_clock_tick():
            self._set_continue_feedback(False)
            # MP: a clock tick IS the gated advance for deadline day -- sync
            # the clients (trades break on ticks). Ready-cycle reset happens
            # in _mp_fire_authorized_advance's finally block.
            if getattr(self, 'mp_host', None) is not None \
                    and getattr(self, '_mp_advance_authorized', False):
                self._mp_after_deadline_tick()
            return

        # Resuming after the game-day inbox bundle: daily maintenance
        # (scout report, career daily, ...) already ran before the bundle
        # opened, so skip it -- the day must not double-process.
        _resuming_after_bundle = bool(getattr(self, '_continue_after_bundle', False))
        if _resuming_after_bundle:
            self._continue_after_bundle = False

        try:
            # PLAYOFF PHASE (date-driven): once the bracket is alive, the
            # date keeps advancing -- each Next Day sims that day's
            # scheduled playoff games through the bracket. Bracket
            # controls keep working: either path driving first wins
            # (exactly-once is enforced in try_play_scheduled_game).
            if self._playoffs_in_progress():
                self._simulate_playoff_day()
                return

            # Check for season end by games completed (primary trigger).
            # The date cutoff is only a safety net set AFTER the last scheduled
            # game, since the generated schedule can run past April 15.
            season_complete = self._check_season_complete()

            if season_complete:
                self.end_of_season()
                self._set_continue_feedback(False)
                return

            last_game_date = getattr(self, '_season_last_game_date', None)
            if last_game_date is None:
                try:
                    game_dates = [e.get('date') for e in self.league.schedule
                                  if isinstance(e, dict) and e.get('date')]
                    if game_dates:
                        last_game_date = max(game_dates)
                except Exception:
                    last_game_date = None
                self._season_last_game_date = last_game_date
            if last_game_date and self.current_date > last_game_date + timedelta(days=7):
                self.end_of_season()
                self._set_continue_feedback(False)
                return

            # Process daily maintenance tasks FIRST (before checking games)
            if not _resuming_after_bundle:
                self._set_continue_feedback(True, "Processing daily tasks...")
                self._process_daily_maintenance()
            
            # Get today's games - OPTIMIZED with early break and caching
            todays_games = []
            
            # Use cached result if available (cache for current date)
            cache_key = f"games_{self.current_date.isoformat()}"
            if hasattr(self, '_schedule_cache') and cache_key in self._schedule_cache:
                todays_games = self._schedule_cache[cache_key]
            else:
                # Create cache if it doesn't exist
                if not hasattr(self, '_schedule_cache'):
                    self._schedule_cache = {}
                
                # Process schedule with early termination
                games_found = 0
                max_games_per_day = 16  # NHL typically has max 16 games per day
                
                for item in self.league.schedule:
                    # Early termination if we found enough games or past today's date
                    if games_found >= max_games_per_day:
                        break
                        
                    try:
                        # Handle tuple format: (date, home_team, away_team) or (date, event_type, event_data)
                        if isinstance(item, tuple) and len(item) >= 2:
                            item_date = item[0]
                            # Skip if date is past today (schedule is sorted)
                            if hasattr(item_date, 'year') and item_date > self.current_date:
                                break
                            # Process if date matches today
                            if item_date == self.current_date:
                                # Only add if it's a game (not an NHL event)
                                if len(item) >= 3 and item[1] != 'NHL_EVENT':
                                    # Convert tuple to standardized dictionary format
                                    game_dict = {
                                        'date': item[0],
                                        'home_team': item[1],
                                        'away_team': item[2],
                                        'event_type': 'GAME'
                                    }
                                    todays_games.append(game_dict)
                                    games_found += 1
                        # Handle dictionary format
                        elif isinstance(item, dict):
                            item_date = item.get('date')
                            # Skip if date is past today
                            if item_date and item_date > self.current_date:
                                break
                            # AHL (and any non-NHL league) games live on the
                            # same schedule list but are NEVER day-simmed --
                            # the minors get a lightweight generated ledger
                            # (ahl_system), not game sims. Letting them into
                            # todays_games burned the 16-game daily budget and
                            # silently dropped real NHL games from the sim.
                            if item.get('league', 'NHL') != 'NHL':
                                continue
                            # Playoff games live on the schedule for display
                            # but are simmed through the playoff bracket --
                            # never double-sim them here.
                            if item.get('playoff'):
                                continue
                            # Process if date matches today
                            if item_date == self.current_date and item.get('event_type') != 'NHL_EVENT':
                                todays_games.append(item)
                                games_found += 1
                    except (AttributeError, TypeError, IndexError) as e:
                        # Skip malformed schedule items
                        continue
                
                # Cache the result for potential future use
                self._schedule_cache[cache_key] = todays_games
                
                # Clean old cache entries to prevent memory bloat
                if len(self._schedule_cache) > 7:  # Keep only last week
                    oldest_key = min(self._schedule_cache.keys())
                    del self._schedule_cache[oldest_key]
            
            # Game-day inbox bundle: pre-match presser + team talk +
            # Watch/Quick choice as one interactive inbox message instead
            # of modals. When it opens, the day waits for the user's pick.
            # Preseason exhibitions skip the bundle -- they're quick-simmed
            # quietly, like the real league treats September hockey.
            _all_preseason = bool(todays_games) and all(
                isinstance(g, dict) and g.get('preseason')
                for g in todays_games)
            if (not _resuming_after_bundle and not _all_preseason
                    and self._maybe_open_game_day_bundle(todays_games)):
                # Bundle opened: the day waits for the user's Watch/Quick
                # pick. Dismiss the loading overlay so they can interact.
                self._set_continue_feedback(False)
                return

            # NHL Rule 6.1: every club must have 1C+2As before opening night.
            # Runs once per phase -- at the first preseason game day AND the
            # first regular-season game day. Preseason: AI clubs auto-repair,
            # human club gets a non-blocking reminder. Regular season: the
            # mandatory picker blocks the human GM until captains are named.
            # A valid existing captain is never overwritten.
            if todays_games:
                _sy = getattr(getattr(self, 'league', None), 'season_year', None)
                _phase = "preseason" if _all_preseason else "regular"
                if (_sy is not None
                        and getattr(self, '_captaincy_checked_phase', None)
                        != (_sy, _phase)):
                    self._captaincy_checked_phase = (_sy, _phase)
                    _ut = getattr(self, 'user_team', None)
                    # Fantasy-draft deferral ends here: the first game day
                    # of preseason (or the regular season, if preseason was
                    # skipped) is when captains get set.
                    try:
                        _dgm = getattr(self, 'game_manager', None)
                        if _dgm is not None:
                            _dgm._fantasy_draft_captaincy_deferred = False
                            # Tell the captaincy check which phase we're in
                            # so it knows whether to remind or block.
                            _dgm._captaincy_check_phase = _phase
                    except Exception:
                        pass
                    # NOTE (Item 7): the captaincy helpers live on
                    # GameManager, but this is a HockeyManagerGUI method --
                    # the old self._ensure_captaincy call here was dead
                    # (AttributeError, swallowed by the except below), so
                    # the opening-night check never ran. Route via the
                    # game manager to make both paths live.
                    _gm = getattr(self, 'game_manager', None)
                    for _t in (getattr(getattr(self, 'league', None),
                                       'teams', None) or []):
                        try:
                            if _gm is not None:
                                _nc = _gm._opening_night_captaincy_check(
                                    _t, _ut)
                            else:
                                _nc = None
                            if _nc and _t is _ut:
                                self.add_news(
                                    f"© {_nc} has been named captain of the "
                                    f"{getattr(_t, 'team_name', 'club')}.")
                        except Exception:
                            pass
                    # Preseason reminder: if the human club still needs
                    # captains, post a non-blocking inbox task. The
                    # regular-season phase will enforce it with the picker.
                    # Preseason reminder with visible timeline: the user sees
                    # exactly how long they have before the picker blocks
                    # at opening night.
                    try:
                        if (_phase == "preseason" and _gm is not None
                                and getattr(_gm, "_captaincy_choice_pending",
                                            False)):
                            _days, _ddl = _gm.get_captaincy_deadline_info()
                            if _days is not None and _ddl is not None:
                                _when = (f"Opening night is in {_days} day"
                                         f"{'s' if _days != 1 else ''} "
                                         f"({_ddl.strftime('%b %d')})")
                            else:
                                _when = "before opening night"
                            self.add_news(
                                f"Ⓒ Preseason tasks: name your captain (C) and "
                                f"two alternates (A) {_when}. "
                                f"Open the roster to choose -- the picker "
                                f"will block you at opening night if "
                                f"it's still not done. You can also assign "
                                f"jersey numbers from the roster.")
                    except Exception:
                        pass
                    # Numbers finalized with the captaincy: freed favorites
                    # get claimed unless the player started a legacy with
                    # his current number. Old saves backfill retired
                    # numbers first so nothing legal gets repaired away.
                    try:
                        import immortality as _im2
                        for _t in (getattr(getattr(self, 'league', None),
                                           'teams', None) or []):
                            try:
                                if (getattr(_t, 'league_name', '')
                                        != "National Hockey League"):
                                    continue
                                _im2.seed_retired_numbers(_t)
                                for _sw in _im2.finalize_team_numbers(_t, _sy):
                                    if _t is _ut and _sw.get("reason") == "favorite":
                                        _p = _sw.get("player")
                                        self.add_news(
                                            f"{getattr(_p, 'full_name', 'A player')} "
                                            f"switches from No. {_sw.get('old')} to "
                                            f"No. {_sw.get('new')} -- his favorite "
                                            f"number freed up.")
                            except Exception:
                                continue
                    except Exception:
                        pass

            # D5 follow-up: undecided staff renewal offers lapse at the
            # first game day of the season (preseason or regular) -- the
            # staffer walks to the free-agent pool. Once per season.
            try:
                _rsy = getattr(getattr(self, 'league', None),
                               'season_year', None)
                if (_rsy is not None
                        and getattr(self, '_renewals_resolved_year', None)
                        != _rsy):
                    self._renewals_resolved_year = _rsy
                    import staff_renewals as _srr
                    for _rl in (_srr.resolve_pending_renewals(
                            self.league) or []):
                        try:
                            self.add_news("🧑‍💼 " + str(_rl))
                        except Exception:
                            pass
            except Exception:
                pass

            self._set_continue_feedback(True, "Simulating games...")
            # Process games if any exist
            if todays_games:
                # Rosters/tactics can change daily (trades, injuries, user tweaks):
                # drop the cached team-strength values so sims stay current.
                if hasattr(self, '_strength_cache'):
                    self._strength_cache.clear()
                # Milestone watches: one scan per day, pre-game presentation.
                # Preseason exhibitions don't count toward career milestones.
                self._milestone_pregame(
                    [g for g in todays_games
                     if not (isinstance(g, dict) and g.get('preseason'))])
                # Narrative ignition: rivalry pregame hype for user games.
                self._rivalry_pregame(
                    [g for g in todays_games
                     if not (isinstance(g, dict) and g.get('preseason'))])
                self._process_todays_games(todays_games)
                if getattr(self, '_abort_day_sim', False):
                    # Mid-team-talk save/load orphaned this day sim (the
                    # pre-load frame's objects are dead). Bail before
                    # post-day processing; the parked talk resumes from
                    # its session on the next Continue. The finally below
                    # still restores the Continue button.
                    self._abort_day_sim = False
                    return
            
            self._set_continue_feedback(True, "Updating injuries...")
            # Process injury recovery: countdown runs in GAMES MISSED, so only
            # teams that played today tick down (and today's new injuries
            # start counting with the next game).
            teams_played = set()
            for game in todays_games:
                try:
                    if isinstance(game, dict):
                        teams_played.add(game.get('home_team'))
                        teams_played.add(game.get('away_team'))
                    else:
                        teams_played.add(game[1])
                        teams_played.add(game[2])
                except Exception:
                    pass
            teams_played.discard(None)
            self.game_manager._process_injury_recovery(teams_played or None)
            self.game_manager._process_suspension_service(teams_played or None)
            
            self._set_continue_feedback(True, "Processing AI decisions...")
            # Process AI team decisions (trades, signings, etc.)
            # Only every 7 days (handled internally by ai_manager)
            try:
                if hasattr(self.league, 'free_agents'):
                    free_agents = self.league.free_agents
                else:
                    free_agents = []
                # Only run AI for NHL teams -- minor league teams don't need
                # trade/FA/contract AI. This cuts 60 teams -> 32 (Small).
                nhl_teams = [t for t in self.league.teams
                             if getattr(t, 'league_name', 'National Hockey League') == 'National Hockey League']
                decisions = self.game_manager.ai_manager.process_daily_decisions(
                    nhl_teams, free_agents, self.current_date
                )
                # Log significant decisions
                for d in decisions[:5]:  # Limit spam
                    if hasattr(d, 'description'):
                        print(f"🤖 AI: {d.description}")
            except Exception as e:
                # Don't crash the game if AI fails
                print(f"AI manager error (non-fatal): {e}")
            # AI trade market (trade_market.py, additive): year-round
            # listings, bidding rounds, request shopping, trade blocks,
            # shortlist nudges. Never raises; cheap no-op when idle.
            try:
                import trade_market
                trade_market.process_market(
                    self, getattr(self, "league", None), self.current_date)
            except Exception as e:
                print(f"Trade market error (non-fatal): {e}")
            # AI signings write their own headlines (signings,
            # market-setters, contract fallout) -- flush them into the
            # news feed with today's date.
            try:
                _ai_mgr = getattr(getattr(self, "game_manager", None),
                                  "ai_manager", None)
                _drain = getattr(_ai_mgr, "drain_pending_news", None)
                if callable(_drain):
                    for _story in _drain():
                        self.news_log.append({'date': self.current_date,
                                              'story': _story})
            except Exception:
                pass
            
            # ALWAYS advance date and update UI (whether games existed or not)
            # Milestones hit today: ledger + four-viewpoint headlines, once
            # the day's career totals are final.
            self._milestone_postgame()
            self.current_date += timedelta(days=1)

            # Pre-season coach expectations meeting: training camp opens
            # every September 1. The user club arms its season meeting;
            # every AI club resolves immediately. Season-idempotent (the
            # arm/resolve functions no-op when this season is done) and
            # never raises -- the meeting itself gates the NEXT advance
            # via the get_continue_state blocker, not this hook.
            try:
                if self.current_date.month == 9 and self.current_date.day == 1:
                    from coach_season_meeting import on_training_camp
                    on_training_camp(getattr(self, "game_manager", None) or self)
            except Exception:
                pass

            # Quarterly coach check-ins: after games ~20/40/60 the GM's
            # club arms a RESUMABLE check-in conversation (never blocks
            # the day; expires when the next quarter arms). AI clubs
            # resolve immediately -- no UI, never skipped. Season- and
            # mandate-idempotent, and never raises.
            try:
                from coach_checkins import on_day_advanced
                on_day_advanced(getattr(self, "game_manager", None) or self)
            except Exception:
                pass

            # Offer-sheet match windows: a sheet whose 7-day clock ran out
            # unanswered resolves as a decline -- the player goes to the
            # offering club at the sheet terms (real CBA rule). Idempotent;
            # only expired pending sheets are touched.
            try:
                import rfa_system as _rfa_os
                _rfa_os.process_offer_sheet_deadlines(self, self.league)
            except Exception:
                pass

            # Real-life jersey retirement ceremonies: the rafters match
            # reality, on the real month/day of the first season.
            # Idempotent -- a retired number never re-fires. Old saves
            # without a schedule get past-dated numbers retired quietly.
            try:
                import immortality as _im_cer
                _league = getattr(self, "league", None)
                for _ct, _cc in _im_cer.ceremonies_due(
                        _league, self.current_date):
                    _story = _im_cer.stage_ceremony(_ct, _cc)
                    if _story:
                        self.news_log.append({'date': self.current_date,
                                              'story': _story})
                for _note in _im_cer.retire_overdue_ceremonies(
                        _league, self.current_date):
                    self.news_log.append({'date': self.current_date,
                                          'story': _note})
            except Exception:
                pass
            # Stanley Cup awarding recap: fires once, the night the Cup is
            # won (flag-guarded; save/load safe via the league key).
            try:
                self._maybe_send_cup_recap()
            except Exception:
                pass

            # All-Star weekend: rosters announced 5 days before the game
            # (fan vote captains + hockey-ops selection, every club
            # represented); the exhibition itself is presentation-only.
            # Idempotent per season via league.all_star_rosters.
            try:
                import all_star as _as
                _asg = _as.all_star_game_date(self.league)
                if _asg is not None and hasattr(_asg, "toordinal"):
                    _sy = int(getattr(self.league, "season_year", 2026))
                    _label = f"{_sy}-{str(_sy + 1)[-2:]}"
                    if self.current_date == _asg - timedelta(days=5):
                        _rosters = _as.select_all_star_rosters(self.league)
                        if _rosters:
                            self.news_log.append({
                                'date': self.current_date,
                                'story': _as.announcement_copy(_rosters, _label)})
                    elif self.current_date == _asg:
                        _rosters = _as.resolve_rosters(self.league, _label)
                        if _rosters:
                            _rng = random.Random(f"allstar-{_label}")
                            for _title, _who, _div in \
                                    _as.skills_winners(_rosters, _rng):
                                self.news_log.append({
                                    'date': self.current_date,
                                    'story': f"⚡ Skills Competition -- {_title}: "
                                             f"{_who} ({_div})."})
                            _res = _as.play_all_star_game(_rosters, _rng)
                            if _res:
                                _champ_coach = (_rosters.get(
                                    _res['champion'], {}) or {}).get(
                                        "coach_name")
                                _coach_bit = (f" {_champ_coach} gets the win "
                                              f"behind the "
                                              f"{_res['champion']} bench."
                                              if _champ_coach else "")
                                self.news_log.append({
                                    'date': self.current_date,
                                    'story': f"🌟 All-Star Game: "
                                             f"{_res['champion']} take the "
                                             f"3v3 tournament "
                                             f"{_res['score']} over "
                                             f"{_res['finalists'][1]} in the "
                                             f"final.{_coach_bit}"})
            except Exception as _ase:
                print(f"All-Star weekend skipped (non-fatal): {_ase}")

            # Future 1st-round pick slots track the standings (regressed
            # toward mid-round -- a projection, not a promise).
            try:
                import trade_engine as _te_ps
                _te_ps.project_pick_slots(getattr(self, "league", None))
            except Exception:
                pass

            # Trade talks: AI GMs answer due offers/counters via the inbox.
            # Non-fatal by design -- a negotiation must never break the sim.
            try:
                import trade_negotiation as _tn
                _tn.process_due_negotiations(self)
            except Exception as _tne:
                print(f"trade negotiation tick failed (non-fatal): {_tne}")

            # Headline hygiene (cheap, once a day): expire inbox news older
            # than 7 game-days unless the user saved it or it's a milestone
            # for their team.
            try:
                self.user_team.inbox.prune_expired(self.current_date)
            except Exception:
                pass

            # Media engine daily tick: narratives cool, beefs go quiet.
            try:
                import media_engine
                media_engine.media_daily_tick(getattr(self, 'league', None))
            except Exception:
                pass
            
            # Daily news engine: 3-8 routine stories/day so the news feed
            # never runs dry. Feed-only (no inbox, no headline cap).
            try:
                import daily_news
                daily_news.generate_daily_news(self, self.current_date)
            except Exception as _dne:
                print(f"Daily news generation failed (non-fatal): {_dne}")
            
            # Clear caches periodically to prevent memory bloat
            if self.current_date.day == 1:  # First day of each month
                # Part 3: draft-season build-up beat (Jan-Jun, once per
                # month per year) + rights-lifecycle news flush. Guarded
                # internally; never breaks the tick.
                try:
                    self._post_draft_season_beat()
                except Exception as _dbe:
                    print(f"Draft season beat failed (non-fatal): {_dbe}")
                if hasattr(self, '_schedule_cache'):
                    self._schedule_cache.clear()
                if hasattr(self, '_strength_cache'):
                    self._strength_cache.clear()
                # Monthly player development (ratings change -> strength recomputed)
                try:
                    self.game_manager._process_monthly_development()
                except Exception as e:
                    print(f"Player development error (non-fatal): {e}")
                # B39 (fixed 2026-09-30): the fracture ladder's production
                # caller. Runs BEFORE the trade-request check so the
                # room's trade-risk multiplier applies in the same pass.
                try:
                    import reputation_system as _rs_tick
                    _rs_tick.room_implications_monthly_tick(self)
                except Exception as e:
                    print(f"Room implications tick error (non-fatal): {e}")
                # Monthly headline check: rare trade requests (risk-model
                # driven, capped league-wide so it stays rare).
                try:
                    import headlines
                    headlines.monthly_trade_request_check(self)
                except Exception as e:
                    print(f"Trade-request check error (non-fatal): {e}")
                # Cup-ambition stars on sellers agitate monthly (additive;
                # the check above is untouched).
                try:
                    import trade_market
                    trade_market.ambition_agitation_tick(self)
                except Exception as e:
                    print(f"Agitation tick error (non-fatal): {e}")
                # Monthly NHL awards: Player of the Month / Rookie of the
                # Month from month splits; banked, announced, baselines
                # re-stamped.
                try:
                    import stars as _stars_mo
                    _stars_mo.monthly_awards_tick(self)
                except Exception as e:
                    print(f"Monthly awards error (non-fatal): {e}")
            
            # Update game_manager's current_date for dashboard synchronization
            self.game_manager.current_date = self.current_date
            
            self._set_continue_feedback(True, "Updating dashboard...")
            # Refresh the atmospheric dashboard with updated data
            if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'refresh_dashboard'):
                self.dashboard.refresh_dashboard()
            
            # Muck 2026-10-02: post-advance landing -- game results only
            # when games were actually played on the simmed day, otherwise
            # the inbox. Deferred while auto-advance owns the flow (it
            # applies the landing once when the loop stops).
            if not getattr(self, '_auto_advance', False):
                self._post_advance_landing()

            # Use async update to prevent blocking
            self.after_idle(self.update_all_views)

            # Bound the ever-growing history logs (game_results ~1344/season,
            # news_log unbounded) so daily scans and save pickles stay O(season).
            self._trim_history_logs()

            # --- MULTIPLAYER (Phase 1) + CHECKPOINTS ---
            # Placed at the end of the try block so it runs ONLY on a
            # successful day advance (the early returns above skip it).
            # Checkpoint + snapshot run on a WORKER thread via
            # broadcast_state_async: create_save_data/pickle/gzip over the
            # ~12k-player league is seconds-scale and must never block the
            # tkinter main thread. announce_day stays synchronous (tiny).
            # While the worker runs, snapshot_busy is True: simulate_day
            # refuses new advances and client actions are deferred, so the
            # game objects being serialized cannot be mutated mid-flight.
            # Completion arrives as a "snapshot_done" poll event.
            try:
                host = getattr(self, 'mp_host', None)
                if host is not None:
                    label = f"Day {self.current_date}"
                    cpm = getattr(self, 'checkpoint_manager', None)
                    pre = (lambda: cpm.checkpoint(label)) \
                        if cpm is not None else None
                    host.announce_day(str(self.current_date))
                    if cpm is not None:
                        host.notify_checkpoint(label, str(self.current_date))
                    host.broadcast_state_async(label, pre_broadcast=pre)
            except Exception as _mp_e:
                print(f"Multiplayer broadcast failed (non-fatal): {_mp_e}")

        finally:
            # Restore the Continue button: re-enable clicks, clear the
            # "Processing..." state and re-apply the smart Continue/Next Day
            # label (blockers may have appeared or cleared).
            self._set_continue_feedback(False)
            # R8(i): the top-nav pill is NOT covered by the dashboard
            # helper above -- refresh it too, or "Continue (1)" goes stale
            # after the blocker is resolved (and "Next Day" goes stale
            # when a blocker appears mid-session).
            try:
                self.refresh_next_day_button()
            except Exception:
                pass
    def handle_contract_offer(self, person, extension=False, notify="popup"):
        # CBA: player bought out cannot re-sign with same team for 1 year
        if not extension:
            try:
                from buyout_window import buyout_re_sign_banned
                user_team = getattr(self, "user_team", None)
                team_name = getattr(user_team, "team_name", "") if user_team else ""
                if team_name and buyout_re_sign_banned(person, team_name):
                    try:
                        self._ui_notify("warning", "Can't sign",
                            f"{getattr(person, 'full_name', 'Player')} was bought out by this team - CBA prohibits re-signing for 1 year.")
                    except Exception:
                        pass
                    return False
            except Exception:
                pass
        # R1 (roster limits): Dec-1 ineligible RFAs can't sign anywhere --
        # refuse the offer up front with the real reason.
        try:
            import roster_limits as _rl
            _ok, _why = _rl.can_sign_player(person)
            if not _ok:
                try:
                    self._ui_notify("warning", "Can't sign", _why)
                except Exception:
                    pass
                return False
        except Exception:
            pass
        # No renegotiation (Muck 2026-10-02): a signed player can't be
        # re-offered as a UFA. Extensions go through is_extension=True;
        # 1-year deals may extend via the normal extension flow.
        if not extension:
            try:
                _fa_pool = getattr(getattr(self, "league", None),
                                   "free_agents", None)
                if isinstance(_fa_pool, list) and person not in _fa_pool:
                    try:
                        self._ui_notify("warning", 
                            "Already signed",
                            f"{getattr(person, 'full_name', 'This player')} "
                            f"is already under contract -- you can't "
                            f"renegotiate a signed deal.")
                    except Exception:
                        pass
                    return False
            except Exception:
                pass
        # NHL contract rules (cap-relative: uses the live league cap):
        # notify: "popup" (legacy messagebox), "inbox" (FM24/EHM-style
        # inbox message; counter-offers become interactive), "quiet" (no
        # notification -- bulk callers send one digest themselves).
        # Defensive: ensure salary and contract_years attributes exist
        salary = getattr(person, "salary",
                         getattr(getattr(person, "contract", None),
                                 "salary", 750_000))
        years = getattr(person, "contract_years",
                        getattr(getattr(person, "contract", None),
                                "years_remaining", 1))
        person.salary = salary
        person.contract_years = years

        ok, err = self._validate_contract_terms(
            person, salary, years, extension=extension)
        if not ok:
            self._ui_notify("error", "Error", err)
            return False

        # Trade protection on the table: a clause the player wants is worth
        # money to him, so the *effective* offer is salary + clause value.
        # Shared valuation with the AI (trade_engine), not a user-only perk.
        import trade_engine as te
        _clause_kind = getattr(person, "offered_clause_kind", "none") or "none"
        _clause_size = getattr(person, "offered_clause_list_size", 10) or 10
        _demand = te.clause_demand_score(
            person, getattr(self, "user_team", None),
            getattr(self, "league", None))
        _clause_val = te.clause_annual_value(person, _clause_kind) \
            if _demand > 0.25 else 0
        _effective_salary = salary + _clause_val

        # If extension, use current salary and offer +X years
        if extension:
            # Create/assign negotiate_contract if missing
            if not hasattr(person, "negotiate_contract"):
                def negotiate_contract(salary, years):
                    # Accept if salary is within 90-120% of value and years >= 1
                    value = getattr(person, "value", getattr(person, "overall_rating", lambda: 10)() * 100000)
                    min_salary = value * 0.9
                    max_salary = value * 1.2
                    return min_salary <= salary <= max_salary and years >= 1
                person.negotiate_contract = negotiate_contract
            accepted = person.negotiate_contract(_effective_salary, years)
            if accepted:
                person.contract_years = years
                person.salary = salary
                # A new SPC starts with no retained salary: the old deal's
                # discount and two-club history die with it (the retaining
                # club's ledger entry survives independently, per CBA).
                try:
                    te.clear_retention_state(person)
                except Exception:
                    pass
                if hasattr(person, "contract"):
                    person.contract.salary = salary
                    person.contract.years_remaining = years
                    te.apply_clause_to_contract(person.contract, _clause_kind,
                                                _clause_size, player=person)
            self._ui_notify("contract_result", "accepted" if accepted else "rejected",
                                         person, salary, years, salary, extension,
                                         notify)
            self._clear_offered_clause(person)
            return accepted

        # Cap-relative asking price: base demand as % of cap, scaled by
        # the live cap and any market-setter premium (the McDavid effect).
        _cap_sys = getattr(getattr(self, 'league', None),
                           'salary_cap_system', None)
        _live_cap = self.get_live_cap()
        _ovr = person.overall_rating()
        try:
            from game_classes import to_100_scale
            _ovr100 = int(to_100_scale(_ovr))
        except Exception:
            _ovr100 = int(_ovr * 2)
        _pos = getattr(person, "primary_position", "")
        _pos_name = _pos.value if hasattr(_pos, "value") else str(_pos)
        try:
            _on_elc = bool(getattr(getattr(person, "contract", None),
                                  "entry_level", False))
        except Exception:
            _on_elc = False
        from salary_cap_system import base_ask_dollars as _bad2
        _base_pct = _bad2(_ovr100, getattr(person, "age", 27),
                          _on_elc, _pos_name) / _live_cap
        # UFA/RFA scarcity: the same market read the AI clubs get -- thin
        # market + many suitors inflates this ask, a flooded pool softens
        # it. Stored on the session so the UI can explain the number.
        _scarc3 = 1.0
        _scarc_sig3 = "balanced"
        try:
            from salary_cap_system import fa_market_scarcity as _fms3
            _sc = _fms3(getattr(self, 'league', None), _pos_name)
            _scarc3 = float(_sc.get("multiplier", 1.0))
            _scarc_sig3 = str(_sc.get("signal", "balanced"))
        except Exception:
            pass
        if _cap_sys is not None:
            _season = getattr(getattr(self, 'league', None), 'season_year', 0)
            asking_price = _cap_sys.demand_for(
                _base_pct, _ovr100, _pos_name,
                getattr(person, "age", 27), _season, scarcity=_scarc3)
        else:
            asking_price = int(_base_pct * _live_cap)
        asking_price = max(asking_price, 750_000)
        # Stash the market read on the negotiation session so the talks UI
        # can explain the number (qualitative signal only, never the
        # multiplier).
        try:
            from popup_system import get_negotiation_session as _gns
            _nsess = _gns(self, person, defaults={})
            if _nsess is not None:
                _nsess["scarcity_signal"] = _scarc_sig3
                _nsess["scarcity_pos"] = _pos_name
        except Exception:
            pass

        # A player who badly wants protection and isn't getting it charges
        # for the missing clause.
        if _demand >= 0.65 and _clause_kind == "none":
            asking_price = int(asking_price * 1.08)

        if _effective_salary >= asking_price * 0.9: # Accepts if offer is 90% or more of asking
            # UFA consideration period (Muck 2026-10-02): no more instant
            # signings. A qualifying UFA offer becomes a BID -- the player
            # fields offers from every club for 3-7 days, then signs with
            # the most appealing one per contract_appeal(). Extensions keep
            # the instant path (they're re-signings, not market bids).
            if not extension:
                try:
                    import ufa_consideration as _uc
                    _cons = _uc.submit_ufa_offer(
                        self, getattr(self, "league", None), person,
                        getattr(self, "user_team", None),
                        person.salary, person.contract_years,
                        is_user=True,
                        clause_kind=_clause_kind,
                        clause_size=_clause_size)
                    if _cons is not None:
                        _uc.notify_consideration_started(
                            self, person, person.salary,
                            person.contract_years,
                            int(_cons.get("days_left", 4) or 4))
                        self._clear_offered_clause(person)
                        return "consideration"
                except Exception:
                    pass
            self._finalize_contract_signing(person, person.salary,
                                            person.contract_years,
                                            asking_price, extension)
            self._ui_notify("contract_result", "accepted", person, person.salary,
                                         person.contract_years, asking_price,
                                         extension, notify,
                                         clause_kind=_clause_kind,
                                         clause_list_size=_clause_size)
            self._clear_offered_clause(person)
            return True
        elif _effective_salary >= asking_price * 0.7: # Counter-offers if between 70-90%
            # The clause offer travels WITH the counter: capture the staged
            # terms into the inbox action and clear them here, so they stay
            # single-use and can't leak into an unrelated later deal.
            _ck, _cs = _clause_kind, _clause_size
            self._clear_offered_clause(person)
            self._ui_notify("contract_result", "counter", person, person.salary,
                                         person.contract_years, asking_price,
                                         extension, notify,
                                         clause_kind=_ck,
                                         clause_list_size=_cs)
            return False
        else: # Rejects if below 70%
            self._ui_notify("contract_result", "rejected", person, person.salary,
                                         person.contract_years, asking_price,
                                         extension, notify)
            self._clear_offered_clause(person)
            return False


    def _finalize_contract_signing(self, person, salary, years, asking_price,
                                   extension):
        """Apply an agreed contract: cap records, market tracking, news,
        media, roster moves. Shared by the negotiation window and the
        inbox counter-offer accept button."""
        person.salary = salary
        person.contract_years = years
        # A new SPC starts with no retained salary: the old deal's discount
        # and two-club history die with it (the retaining club's ledger
        # entry survives independently, per CBA).
        try:
            import trade_engine as _te_clr3
            _te_clr3.clear_retention_state(person)
        except Exception:
            pass
        _contract = getattr(person, "contract", None)
        if _contract is not None:
            _contract.salary = salary
            _contract.years_remaining = years
            # Trade protection negotiated at the table lands on the deal.
            import trade_engine as _te2
            _te2.apply_clause_to_contract(
                _contract,
                getattr(person, "offered_clause_kind", "none") or "none",
                getattr(person, "offered_clause_list_size", 10) or 10,
                player=person)
        _cap_sys = getattr(getattr(self, 'league', None),
                           'salary_cap_system', None)
        # Track market-setting contracts (star + top-5 AAV)
        _set_market = False
        try:
            _ovr = person.overall_rating()
            try:
                from game_classes import to_100_scale
                _ovr100 = int(to_100_scale(_ovr))
            except Exception:
                _ovr100 = int(_ovr * 2)
            _pos = getattr(person, "primary_position", "")
            _pos_name = _pos.value if hasattr(_pos, "value") else str(_pos)
            if _cap_sys is not None:
                _season = getattr(getattr(self, 'league', None), 'season_year', 0)
                _set_market = _cap_sys.register_signing(
                    person.full_name, salary, _ovr100,
                    _pos_name, getattr(person, "age", 27), _season)
                if _set_market:
                    self.news_log.append({
                        'date': self.current_date,
                        'story': (f"{person.full_name}'s "
                                  f"${salary:,} deal sets the market "
                                  f"-- comparable stars will demand more.")})
        except Exception:
            pass
        # Contract-decision fallout: overpay verdict, fan beef, GM rep,
        # and GM-GM heat when the deal resets the market. The salary
        # engine itself (SalaryCapSystem) is untouched.
        try:
            from reputation_system import evaluate_contract_decision
            _cd = evaluate_contract_decision(
                person, salary, asking_price,
                team=self.user_team, league=self.league,
                market_setter=bool(_set_market))
            if _cd.get("story"):
                self.news_log.append({'date': self.current_date,
                                      'story': _cd["story"]})
        except Exception:
            pass
        if not extension:
            try:
                self.league.free_agents.remove(person)
            except Exception:
                pass
            self.user_team.add_player(person, "roster")
            # Rivalry lifecycle: a free-agent signing is a transfer -- his
            # personal beefs follow him to the new room; ambient noise he
            # merely encouraged stays behind. Same chokepoint as trades.
            try:
                from reputation_system import on_player_transfer as _opt
                _rivs = getattr(getattr(self, "league", None), "rivalries", None)
                if isinstance(_rivs, list):
                    _opt(_rivs, person, from_team=None, to_team=self.user_team)
            except Exception:
                pass
            # Dressing room: a new face in the room -- the room reacts to
            # WHO he is (blue-chip hype, veteran gravity), bounded.
            try:
                import dressing_room as _dr_arr
                _dr_arr.cascade_on_arrival(
                    self.user_team, person, how="signing",
                    date_str=str(getattr(self, "current_date", "")))
            except Exception:
                pass
            # D4: signing a star is a board headline (star_signing fuel).
            try:
                import reputation_system as _rs4
                _rs4.note_star_signing(
                    getattr(getattr(self, "career", None), "board", None),
                    person)
            except Exception:
                pass
        self.news_log.append({'date': self.current_date, 'story': f"The {self.user_team.team_name} have signed {person.full_name} to a {years}-year contract."})

        # Generate media event for signing (if media system enabled)
        if hasattr(self, 'media_system') and self.media_system:
            contract_type = 'extension' if extension else 'signing'
            self.media_system.process_signing(person, self.user_team, contract_type, salary, years)

    def _check_season_complete(self):
            """Check if the regular season is complete by counting games played."""
            def _gp(stats):
                # Standings dicts use "W"/"L" keys (some legacy code used "Wins"/"Losses")
                return (stats.get('W', stats.get('Wins', 0))
                        + stats.get('L', stats.get('Losses', 0))
                        + stats.get('OTL', 0))
            try:
                # Get target games per team based on season length. Read the
                # league's persisted slate length first (84 from 2026-27 on);
                # old saves generated before the attribute existed fall back
                # to 82, matching their schedules.
                _lg = getattr(self, 'league', None)
                target_games = getattr(
                    _lg, 'season_games_count',
                    getattr(self, 'season_games_count', 82))

                # Season is complete when every NHL team has played its full slate
                if self.league.standings:
                    nhl_names = {t.team_name for t in self.league.teams
                                 if getattr(t, 'league_name', '') == 'National Hockey League'}
                    gps = [_gp(stats) for name, stats in self.league.standings.items()
                           if name in nhl_names]
                    if gps and min(gps) >= target_games:
                        return True

                return False
            except Exception as e:
                print(f"Error checking season completion: {e}")
                return False
                return False

    def _maybe_run_deadline_clock_tick(self):
            """Advance the deadline clock one 30-minute increment instead of a
            full day sim. Returns True when a tick ran (the day did NOT advance
            and callers should return), False to continue the normal sim."""
            try:
                from trade_deadline_manager import get_deadline_manager
                mgr = get_deadline_manager(self.game_manager)
            except Exception:
                return False
            if not mgr.is_deadline_day(self.current_date):
                return False
            if not mgr.clock_active(self.current_date):
                mgr.start_clock(self.current_date)
                # Tentpole prompt at 9 AM, not 3 PM: the event-day hub asks
                # once whether to open the Trade Deadline Center. (The normal
                # maintenance pass that fires it only runs after the clock
                # expires, which would be too late.)
                try:
                    self._check_for_event_day()
                except Exception as e:
                    print(f"deadline day event prompt failed (non-fatal): {e}")
            tick = mgr.advance_clock()
            # Instant AI answers: any due negotiations resolve right now.
            try:
                import trade_negotiation as _tn
                _tn.process_due_negotiations(self)
            except Exception as e:
                print(f"deadline tick negotiation processing failed (non-fatal): {e}")
            # League-wide dealing for this 30-minute window.
            try:
                self._deadline_tick_activity(mgr, tick)
            except Exception as e:
                print(f"deadline tick activity failed (non-fatal): {e}")
            if tick['expired']:
                # 3 PM: the deadline passes. Lock trading, then let the normal
                # day flow continue (maintenance, games, date advance).
                self._close_trade_deadline(mgr)
                return False
            # Refresh the dashboard so the countdown + button label update.
            try:
                self._refresh_dashboard()
            except Exception:
                pass
            try:
                dl = self.open_windows.get('trade_deadline')
                if dl is not None and dl.winfo_exists():
                    dl.refresh()
            except Exception:
                pass
            return True

    def _maybe_send_cup_recap(self) -> bool:
            """Send the Stanley Cup awarding recap to the inbox, once.

            Fires the night the bracket crowns a champion: winners, Conn Smythe,
            the Cup's first two carriers, the heroes, and the coach's victory
            interview. Flag-guarded on the league (save/load safe)."""
            try:
                league = getattr(self, "league", None)
                bracket = getattr(league, "playoff_bracket", None)
                champ = getattr(bracket, "stanley_cup_champion", None)
                if champ is None or league is None:
                    return False
                key = f"{getattr(league, 'season_year', '?')}:{getattr(champ, 'team_name', '?')}"
                if getattr(league, "cup_recap_sent", None) == key:
                    return False
                import immortality as _im_recap
                story = _im_recap.build_cup_recap(champ, bracket, league)
                if story:
                    self.news_log.append({'date': self.current_date,
                                          'story': story})
                league.cup_recap_sent = key
                return True
            except Exception:
                return False

    def _milestone_postgame(self):
            """Milestones hit today: ledger event + four-viewpoint headline."""
            try:
                import milestones as _ms
                watches = getattr(self, "_milestone_watches", None) or []
                self._milestone_watches = []
                self._milestone_watch_teams = set()
                if not watches:
                    return
                for hit in _ms.check_hits(getattr(self, "league", None), watches):
                    _ms.record_milestone_hit(self, hit)
            except Exception:
                pass

    def _milestone_pregame(self, todays_games):
            """One milestone scan per day + pre-game presentation.

            Caches the watch list for the post-game check and the set of teams
            with a tonight-watch (feeds arena_atmosphere's milestone_home flag).
            Pre-game news when a watch is within 2 -- tonight could be the
            night. Mid-range chases (3-5 away) get a throttled weekly mention
            so anticipation builds without spam. Never spams for distant watches.
            """
            self._milestone_watches = []
            self._milestone_watch_teams = set()
            try:
                import milestones as _ms
                from narrative_ledger import active_ledger as _al
                watches = _ms.scan_watches(getattr(self, "league", None))
                self._milestone_watches = watches
                self._milestone_watch_teams = _ms.watch_teams_tonight(watches)
                if not watches:
                    return
                _led = _al()
                _by_team: dict = {}
                _mid_range: dict = {}
                for _w in watches:
                    if _w["remaining"] <= 2:
                        _by_team.setdefault(_w["team_name"], []).append(_w)
                    elif _w["remaining"] <= 5:
                        _mid_range.setdefault(_w["team_name"], []).append(_w)
                # Bucket 4: mid-range chase anticipation, throttled to weekly.
                try:
                    _today = getattr(self, "current_date", None)
                    _doy = int(getattr(_today, "timetuple", lambda: None)()
                               .tm_yday) if _today else 0
                except Exception:
                    _doy = 0
                if _mid_range and _doy % 7 == 0:
                    for _tn, _ws in _mid_range.items():
                        try:
                            _w0 = _ws[0]
                            self.add_news(_ms.chase_copy(_w0))
                        except Exception:
                            continue
                if not _by_team:
                    return
                for game in todays_games or []:
                    try:
                        if isinstance(game, dict):
                            home, away = game.get("home_team"), game.get("away_team")
                        else:
                            home, away = game[1], game[2]
                        hn = getattr(home, "team_name", "")
                        for _w in _by_team.get(hn, []):
                            _note = _ms.venue_note(_w, home, away, _led)
                            _suffix = f" ({_note})" if _note else ""
                            # Bucket 4: escalating chase copy, not a flat "N away".
                            _chase = _ms.chase_copy(_w)
                            self.add_news(f"{_chase}{_suffix}.")
                    except Exception:
                        continue
            except Exception:
                pass
            # Bucket 4: cross-season chase continuity -- "the chase resumes".
            try:
                import milestones as _ms2
                _ms2.carryover_chases(self)
            except Exception:
                pass

    def _mp_after_deadline_tick(self):
            """Sync clients after an authorized deadline-clock tick.

            No date changes on a tick, so no CONTINUE_DAY -- just the fresh
            state (trades break on ticks) plus a checkpoint, on the worker
            thread like the normal end-of-day path.
            """
            try:
                host = self.mp_host
                label = f"Deadline clock {self.current_date}"
                cpm = getattr(self, 'checkpoint_manager', None)
                pre = (lambda: cpm.checkpoint(label)) \
                    if cpm is not None else None
                host.broadcast_state_async(label, pre_broadcast=pre)
            except Exception as e:
                print(f"Multiplayer tick broadcast failed (non-fatal): {e}")

    def _post_draft_season_beat(self):
            """Post the monthly draft build-up beat (Jan-Jun), once per month.

            Part 3: season_beats() from draft_stories builds the narrative batch;
            this hook only delivers it via add_news. Guarded by
            self._draft_beats_posted {(year, month)} so a month never posts twice
            (e.g. after a save/load). Also flushes league.rights_news, the
            rights-lifecycle messages game_classes collects, posting and clearing
            each string. Every path is wrapped so a missing inbox/news path or
            missing attrs never crash the daily tick.
            """
            try:
                month = getattr(self.current_date, "month", 0)
                year = getattr(self.current_date, "year", 0)
                if month not in (1, 2, 3, 4, 5, 6):
                    return
                posted = getattr(self, "_draft_beats_posted", None)
                if posted is None:
                    posted = set()
                    self._draft_beats_posted = posted
                key = (year, month)
                if key in posted:
                    return
                league = getattr(self, "league", None)
                prospects = list(getattr(league, "draft_prospects", None) or [])
                if not prospects:
                    return
                from draft_stories import season_beats
                for _beat in (season_beats(prospects, year, month) or []):
                    try:
                        self.add_news(
                            "%s — %s" % (_beat.get('title', 'Draft'),
                                         _beat.get('text', '')))
                    except Exception:
                        pass
                posted.add(key)
            except Exception:
                pass
            # Rights-lifecycle flush: post + clear any collected messages.
            try:
                _league = getattr(self, "league", None)
                _msgs = list(getattr(_league, "rights_news", None) or [])
                for _m in _msgs:
                    try:
                        self.add_news(str(_m))
                    except Exception:
                        pass
                try:
                    _live = getattr(_league, "rights_news", None)
                    if _live is not None:
                        del _live[:]
                except Exception:
                    pass
                # Prospect junior/college award headlines (same pattern).
                try:
                    _pmsgs = list(getattr(_league, "prospect_awards_news", None)
                                  or [])
                    for _m in _pmsgs:
                        try:
                            self.add_news("🏆 " + str(_m))
                        except Exception:
                            pass
                    _plive = getattr(_league, "prospect_awards_news", None)
                    if _plive is not None:
                        del _plive[:]
                except Exception:
                    pass
                # Rivalry-review verdicts from end_of_season (same pattern).
                try:
                    _rmsgs = list(getattr(_league, "rivalry_review_news", None)
                                  or [])
                    for _m in _rmsgs:
                        try:
                            self.add_news("⚔️ " + str(_m))
                        except Exception:
                            pass
                    _rlive = getattr(_league, "rivalry_review_news", None)
                    if _rlive is not None:
                        del _rlive[:]
                except Exception:
                    pass
                # Staff breakthrough headlines (same pattern).
                try:
                    _bmsgs = list(getattr(_league, "staff_breakthrough_news",
                                          None) or [])
                    for _m in _bmsgs:
                        try:
                            self.add_news("📈 " + str(_m))
                        except Exception:
                            pass
                    _blive = getattr(_league, "staff_breakthrough_news", None)
                    if _blive is not None:
                        del _blive[:]
                except Exception:
                    pass
                # ELC slide headlines (same pattern).
                try:
                    _smsgs = list(getattr(_league, "elc_slide_news", None) or [])
                    for _m in _smsgs:
                        try:
                            self.add_news("📝 " + str(_m))
                        except Exception:
                            pass
                    _slive = getattr(_league, "elc_slide_news", None)
                    if _slive is not None:
                        del _slive[:]
                except Exception:
                    pass
            except Exception:
                pass

    def _process_daily_maintenance(self):
            """Process daily maintenance tasks with performance optimizations"""
            # Only run heavy tasks on specific days to reduce CPU load

            # UFA consideration period (Muck 2026-10-02): tick open bidding
            # windows -- AI clubs add competing offers, expired windows resolve
            # with the player signing the most appealing bid. Guarded: never
            # breaks day advancement.
            try:
                import ufa_consideration as _uc
                _uc.tick_ufa_considerations(self, getattr(self, "league", None))
            except Exception:
                pass

            # Eastside-style auto fillers (user side): release fill-ins no
            # longer needed and auto-summon any dressed-lineup shortfall, so
            # the user can always ice a team exactly like AI clubs. Guarded:
            # a roster_limits bug can never break day advancement.
            try:
                import roster_limits as _rl
                _utm = getattr(self, "user_team", None)
                if _utm is not None:
                    _rl.user_roster_compliance(_utm)
            except Exception:
                pass

            # AI roster safety net: every AI club maintains >=18 on NHL
            # roster. AI trades can leave rosters short; auto-recall best
            # available from AHL. Guarded: never breaks day advancement.
            try:
                _league = getattr(self, "league", None)
                _utm2 = getattr(self, "user_team", None)
                if _league is not None:
                    for _team in (getattr(_league, "teams", None) or []):
                        if _team is _utm2:
                            continue
                        try:
                            _roster = getattr(_team, "roster", None) or []
                            if len(_roster) >= 18:
                                continue
                            _ahl = getattr(_team, "ahl_roster", None) or []
                            _need = 18 - len(_roster)
                            _sorted = sorted(
                                _ahl,
                                key=lambda p: getattr(p, "overall", 50) or 50,
                                reverse=True)
                            for _p in _sorted[:_need]:
                                _ahl.remove(_p)
                                _roster.append(_p)
                        except Exception:
                            pass
            except Exception:
                pass

            # Narrative ledger clock: one cheap setup per day. Drives callback
            # cooldowns; season rollover prunes old low-weight events once.
            try:
                from narrative_ledger import get_ledger
                _led = get_ledger(self)
                _sy = getattr(getattr(self, "league", None), "season_year", None)
                _day = 0
                try:
                    _season_start = date(_sy, 10, 1) if _sy else None
                    if _season_start is not None and \
                            self.current_date >= _season_start:
                        _day = (self.current_date - _season_start).days
                except Exception:
                    pass
                if _sy is not None and _led.season != _sy:
                    _led.advance_season(_sy)
                else:
                    _led.set_clock(_sy, _day)
            except Exception:
                pass

            # Practice fatigue recovery (P1): practice sessions accrue fatigue
            # on the shared player histories, but recover_fatigue had no live
            # callers -- fatigue was permanent, so the grind gate never
            # reopened. Recover daily at the engine's own tuned rate (2/day)
            # so rest days actually rest. Only histories with fatigue > 0 are
            # visited, so this stays cheap league-wide.
            try:
                import enhanced_practice_system as _eps
                _ph = getattr(_eps, "_SHARED_PLAYER_HISTORIES", None) or {}
                if _ph:
                    _peng = _eps.PracticeEngine()
                    for _pid, _hist in list(_ph.items()):
                        try:
                            if getattr(_hist, "current_fatigue", 0) > 0:
                                _peng.recover_fatigue(_pid, days=1)
                        except Exception:
                            continue
            except Exception:
                pass

            # R1 (roster limits): Dec-1 RFA ineligibility stamping + emergency
            # filler auto-release, league-wide. Guarded: never breaks the day.
            try:
                import roster_limits as _rl
                _rl.daily_roster_tick(self)
            except Exception:
                pass

            # Event-day hubs: prompt once per year when a tentpole day arrives.
            # (Entry draft is handled daily inside _check_for_event_day; it must
            # NOT be Monday-gated since June 23-25 often contains no Monday.)
            self._check_for_event_day()

            # Process trade block offers (once per week) - unchanged
            if self.current_date.weekday() == 0:  # Monday
                self.process_trade_block_offers()
            # Scout value tips: once a month (1st), not weekly -- tips should
            # feel like real pro-scouting work, not a daily cheat sheet.
            if self.current_date.day == 1:
                self._dispatch_scout_value_tips()
                # Wave 1 monthly settlement:
                # - Grade old ledger tips against what happened (scout records).
                # - Steal/sell watches: only post-trade production validates a
                #   scout's tip. The tip alone never pays off -- the breakout
                #   (or the collapse) does. Validated events publish news.
                # - Market ecology: philosophy drift + leadership-change regress.
                try:
                    import reputation_system as _rs
                    import analytics_scouting as _as
                    _teams = list(self.league.teams)
                    _date_str = str(self.current_date)
                    _as.grade_tip_ledger(_teams, _date_str)
                    _as.tick_analytics_philosophy(self.league)
                    for _t in _teams:
                        for _ev in _rs.check_steal_watch(_t, self.league,
                                                         _date_str):
                            _news = _ev.get("news")
                            if _news:
                                try:
                                    self.add_news(_news)
                                except Exception:
                                    pass
                        for _ev in _rs.check_sell_watch(_t, _teams,
                                                        self.league,
                                                        _date_str):
                            _news = _ev.get("news")
                            if _news:
                                try:
                                    self.add_news(_news)
                                except Exception:
                                    pass
                except Exception:
                    pass
                # AI arms race: clubs evaluate, renew and poach scouting staff
                # twice a season. Reads improve only when the people improve.
                if self.current_date.month in (1, 7):
                    try:
                        import analytics_scouting as _as2
                        _as2.ai_scout_staff_review(
                            self.league, str(self.current_date))
                    except Exception:
                        pass
            # Analytics storylines: mid-month (15th), season-aware, deduped,
            # significance-gated. The press reads the same numbers the
            # analytics department does -- but only the loud ones.
            if self.current_date.day == 15:
                try:
                    import analytics_scouting as _as
                    _players = []
                    for _t in self.league.teams:
                        _players.extend(getattr(_t, "roster", []) or [])
                    _as.publish_analytics_storylines(
                        getattr(self, "media_system", None),
                        _players, list(self.league.teams),
                        game_manager=self, limit=3)
                except Exception:
                    pass

            # Process scouting assignments - optimized to run every 3 days instead of daily
            if self.current_date.day % 3 == 0:  # Every 3 days
                self.process_scouting_assignments()
                try:
                    import scouting as scouting_mod
                    scouting_mod.process_regional_scouting(self.game_manager
                                                           if hasattr(self, 'game_manager') else self)
                except Exception:
                    pass
                try:
                    import scouting as _scouting_pro
                    _scouting_pro.process_pro_scouting(self.game_manager
                                                       if hasattr(self, 'game_manager') else self)
                except Exception:
                    pass

            # Process waivers - reduced frequency
            # Waiver clock: exactly 2 calendar days on the wire, as the UI
            # promises. The clock ticks every day; claim *processing* still
            # runs Monday/Thursday only.
            for _wp in list(self.waiver_list):
                try:
                    if _wp.on_waivers and _wp.waiver_days > 0:
                        _wp.waiver_days -= 1
                except Exception:
                    pass
            if self.current_date.weekday() in [0, 3]:  # Monday and Thursday only
                self.process_waivers()

            # Training camp (EHM-style): Sep 12-30, scrimmages every 3rd day
            # from the 15th, camp report + development bumps at close. Runs
            # ahead of the early-October camp cuts so the AI cuts by camp
            # ratings (waiver_logic reads player.camp_avg).
            try:
                import training_camp as _tc
                _tc.run_camp_day(self.league, self.current_date, app=self,
                                 rng=getattr(self, "_rng", None))
            except Exception:
                debug_print("Training camp failed (non-fatal):")
                import traceback
                traceback.print_exc()

            # AI waiver management (BUG-019): cap casualties, AHL shuttle,
            # and early-October camp cuts. Runs Mondays after claim
            # processing; fresh placements enter the wire with a 2-day clock
            # so there are no same-day claims. Never touches the user's club.
            if self.current_date.weekday() == 0:  # Monday only
                try:
                    import waiver_logic as _wl
                    _mdate = self.current_date
                    _camp = (_mdate.month == 10 and _mdate.day <= 7 and int(
                        getattr(self.league, "_waiver_camp_year", 0) or 0)
                        != _mdate.year)
                    if _camp:
                        try:
                            self.league._waiver_camp_year = _mdate.year
                        except Exception:
                            pass
                    _wl.process_ai_waivers(
                        self.league, app=self,
                        rng=getattr(self, "_rng", None), camp_cuts=_camp)
                except Exception:
                    debug_print("AI waivers failed (non-fatal):")
                    import traceback
                    traceback.print_exc()

            # Generate daily emails - optimized
            if self.current_date.weekday() == 0:  # Weekly summary instead of daily
                self._generate_weekly_email_summary()

            # Run Phase 2 optimizations less frequently
            if self.current_date.weekday() == 6:  # Sunday only
                self._run_phase2_maintenance()

            # Process player development weekly (during off days or end of week)
            if self.current_date.weekday() == 6:  # Sunday - weekly development processing
                self._process_player_development()
                self._process_training_programs()
                self._process_room_politics_weekly()

            # FM-style career systems: board, happiness, youth, press (cheap daily)
            self._process_career_daily()

            # AHL farm stat lines: no AHL game sim exists, so the minors get a
            # lightweight generated ledger (ahl_system) -- just enough for the
            # AHL Stats screen to show who's cooking. AHL regular season only
            # (Oct 1 - Apr 20); never during the NHL playoffs.
            try:
                import ahl_system as _ahl
                _sy = getattr(getattr(self, "league", None), "season_year", None)
                _in_window = True
                try:
                    from datetime import date as _d
                    if _sy is not None:
                        _in_window = (_d(_sy, 10, 1) <= self.current_date
                                      <= _d(_sy + 1, 4, 20))
                except Exception:
                    pass
                _bracket = getattr(getattr(self, "league", None),
                                   "playoff_bracket", None)
                _playoffs_live = bool(
                    _bracket is not None
                    and getattr(_bracket, "stanley_cup_champion", None) is None
                    and getattr(_bracket, "playoff_series", None))
                if _in_window and not _playoffs_live:
                    # D41 Phase 2: the AHL is a real scheduled league now. When
                    # a Phase 2 schedule is live for this season, per-player
                    # stat lines are logged per scheduled game (truthful GP --
                    # a player can never exceed his club's GP); the daily
                    # probability ledger then only covers farm lists with no
                    # AHL club. When it isn't (generation failure, <2 AHL
                    # clubs), keep the old daily ledger plus Phase 1's
                    # abstract standings day as the fallback.
                    try:
                        import ahl_league as _ahl2
                        if _ahl2.ahl_schedule_active(self.league):
                            _ahl2.simulate_ahl_scheduled_day(
                                self.league, self.current_date)
                            _ahl.simulate_ahl_day(self.league,
                                                  only_unscheduled=True)
                        else:
                            _ahl.simulate_ahl_day(self.league)
                            _ahl.simulate_ahl_standings_day(self.league)
                    except Exception:
                        try:
                            _ahl.simulate_ahl_standings_day(self.league)
                        except Exception:
                            pass
            except Exception:
                pass
            # D41 Phase 2 backstop: the Calder Cup must fire even if the NHL
            # playoffs gate swallowed the last AHL-window day. Instant (a few
            # dozen ultra-fast games), once per season, never raises.
            try:
                import ahl_league as _ahl2b
                _ahl2b.maybe_run_calder_cup(self.league, self.current_date)
            except Exception:
                pass
            # AHL UI story ecosystem: Calder Cup races, prospect watch,
            # Cinderella runs -- wired into the shared headline system.
            try:
                import ahl_narratives as _ahln
                _ahln.maybe_fire_ahl_narratives(self, self.league,
                                                self.current_date)
            except Exception:
                pass

    def _process_todays_games(self, todays_games):
            """Process all games scheduled for today - OPTIMIZED"""
            user_team = getattr(self, 'user_team', None)

            # Quick user team games identification with optimized logic
            user_team_games = []
            other_games = []

            # Cache user team name for faster comparison
            user_team_name = user_team.team_name if user_team else None

            for game in todays_games:
                try:
                    # All games should now be in dictionary format due to standardization above
                    if isinstance(game, dict):
                        home_team = game.get('home_team')
                        away_team = game.get('away_team')
                    # Legacy tuple format handling (should be rare now)
                    elif isinstance(game, tuple) and len(game) >= 3:
                        game_date, home_team, away_team = game[:3]
                    else:
                        continue  # Skip unknown formats silently

                    # Optimized user team detection
                    is_user_team_game = False
                    if user_team_name and home_team and away_team:
                        # Fast string comparison first
                        if (hasattr(home_team, 'team_name') and home_team.team_name == user_team_name) or \
                           (hasattr(away_team, 'team_name') and away_team.team_name == user_team_name):
                            is_user_team_game = True
                        # Fallback to object comparison
                        elif home_team == user_team or away_team == user_team:
                            is_user_team_game = True

                    if is_user_team_game:
                        user_team_games.append(game)
                    else:
                        other_games.append(game)

                except (ValueError, AttributeError, TypeError) as e:
                    print(f"⚠️ Error processing game {game}: {e}")
                    continue

            # Process user team games individually with potential game viewer
            for game in user_team_games:
                try:
                    if isinstance(game, tuple) and len(game) >= 3:
                        game_date, home_team, away_team = game[0], game[1], game[2]
                    elif isinstance(game, dict) and all(key in game for key in ['date', 'home_team', 'away_team']):
                        game_date, home_team, away_team = game['date'], game['home_team'], game['away_team']
                        # Web visualizer already simmed this game: the result is
                        # recorded and stats are updated. Skip re-simming to avoid
                        # double-counting.
                        if game.get('watched'):
                            continue
                    else:
                        continue  # Skip malformed games silently
                except (IndexError, KeyError, ValueError):
                    continue  # Skip errors silently

                # Preseason exhibitions: quick-simmed quietly -- no viewer, no
                # team talk, no lore, no board/morale, no stats, no standings.
                is_preseason = isinstance(game, dict) and bool(game.get('preseason'))

                # How should this user game be presented? Quick sim, watch live,
                # or ask the GM each game day. Never ask during bulk sims.
                # When the game-day inbox bundle resolved the choice, its stored
                # answers (presser, team talk boost, watch/quick) are used --
                # no modal popups.
                settings = self.get_settings()
                mode = self._get_user_game_mode()
                _bundle_res = getattr(self, '_game_day_resolution', None)
                _bundle_active = (_bundle_res is not None
                                  and _bundle_res.get("date") == self.current_date)
                _bundle_instruction = None  # D1: only the bundle carries one
                if _bundle_active:
                    # Web UI (Batch A, 2026-10-05): a web-set resolution is
                    # consumed by the /watch page, never by the desktop Tk
                    # PBP viewer -- opening it server-side would hang the day
                    # advance on a window nobody can see. Degrade to quick sim;
                    # the bundle's talk boost and instruction still apply.
                    if _bundle_res.get("web"):
                        use_game_viewer = False
                    else:
                        use_game_viewer = bool(_bundle_res.get("watch"))
                    _bundle_talk_boost = float(_bundle_res.get("talk_boost", 1.0) or 1.0)
                    # D1: the user's explicit coach instruction from the bundle.
                    _bundle_instruction = _bundle_res.get("instruction")
                    self._game_day_resolution = None  # consume once
                elif getattr(self, '_bulk_simming', False):
                    use_game_viewer = False
                elif mode == 'watch':
                    use_game_viewer = True
                elif mode == 'ask':
                    # Hide the loading toast before the Watch/Quick choice:
                    # the sim is paused on the user now, and the toast must
                    # never cover or block the Game Day dialog (Muck
                    # 2026-10-02). Overlay-only -- the Continue button stays
                    # disabled until the day finishes.
                    try:
                        self._update_day_sim_overlay(False)
                    except Exception:
                        pass
                    use_game_viewer = self._ask_game_mode_dialog(home_team, away_team) == 'watch'
                    if not use_game_viewer:
                        # Quick Sim picked: re-show the toast for the rest of
                        # the day. (Watch Live opens the visualizer, which
                        # owns the UI from here.)
                        try:
                            self._update_day_sim_overlay(True, "Simulating games...")
                        except Exception:
                            pass
                else:
                    use_game_viewer = False
                if is_preseason:
                    # September hockey is never appointment viewing.
                    use_game_viewer = False

                # Legacy events: Winter Classic / Stadium Series. The stamp rides
                # on the schedule entry; read it before the sim branches so both
                # Watch Live and quick sim get the billing + crowd bump.
                _outdoor_info = None
                try:
                    import outdoor_games as _ogm
                    _outdoor_info = _ogm.outdoor_info_for(game)
                    if _outdoor_info is not None:
                        self._deliver_outdoor_pregame(_outdoor_info, home_team,
                                                     away_team)
                except Exception:
                    _outdoor_info = None

                if use_game_viewer:
                    # Modern visual play-by-play (rink + live player bubbles).
                    # Modal: returns the standard 6-tuple once watched to the end.
                    result = self._simulate_game_with_pbp_visual(
                        home_team, away_team, outdoor=_outdoor_info,
                        coach_instruction=_bundle_instruction)
                    winner, loser, scores, events, notable_events, sim_engine = result
                    # GameSim already updated player season stats itself; the
                    # event-based stat pass below must be skipped to avoid
                    # double counting.
                    stats_from_events = False
                    # Narrative: GameSim modeled incidents live; record the
                    # night's stories (hat tricks, shutouts, steals) -- the
                    # visualizer's story_worthy() never reached the ledger.
                    # (Quick-sim games get this via the call below with
                    # roll_incidents=True; one call per game only.)
                    try:
                        _nwent_ot = any(
                            isinstance(_e, dict) and _e.get('period', 0) > 3
                            for _e in (notable_events or []))
                        self._narrative_postgame(
                            sim_engine, home_team, away_team, scores,
                            went_ot=_nwent_ot, roll_incidents=False,
                            deliver_headlines=True, game_date=game_date)
                    except Exception:
                        pass
                else:
                    # FM-style pre-match team talk (interactive, skipped in bulk sim)
                    opponent = away_team if home_team == self.user_team else home_team
                    if _bundle_active:
                        talk_boost = _bundle_talk_boost
                    elif is_preseason:
                        talk_boost = 1.0  # no dressing-room speeches in September
                    else:
                        talk_boost = self._career_team_talk(opponent)
                        if talk_boost is None:
                            # Save/load landed mid-talk (epoch guard): the
                            # pre-load day sim is stale. Abort this game --
                            # simulate_day bails before post-day processing
                            # touches orphaned objects. The parked talk
                            # survives in its session and re-presents on the
                            # next Continue.
                            self._abort_day_sim = True
                            return
                    # Adaptive Rivals: AI scouts the user (quick sim)
                    _qs_adapted = None
                    _qs_plan = []
                    try:
                        from adaptive_rivals import adapt_for_opponent
                        if opponent != self.user_team:
                            _qs_plan = adapt_for_opponent(
                                opponent, self.user_team,
                                getattr(self, 'game_results', []))
                            _qs_adapted = opponent
                    except Exception:
                        pass
                    # Standard full simulation for user games
                    # Standard full simulation for user games
                    # Narrative ledger: grudge-week presentation. (Skipped for
                    # preseason -- exhibitions build no lore.)
                    if not is_preseason:
                        # Narrative ledger: grudge-week presentation. One dict lookup
                        # per game; the inbox card only fires for the user's games or
                        # genuine league-wide feuds (weight >= 60) so it never spams.
                        try:
                            from narrative_ledger import (get_ledger, interpret,
                                                          incident_short)
                            from headlines import deliver_spec as _deliver_spec
                            _led = get_ledger(self)
                            _cand = _led.callback_candidate(home_team.team_name,
                                                            away_team.team_name)
                            if _cand is not None:
                                _uname = getattr(getattr(self, "user_team", None),
                                                 "team_name", "")
                                _uinvolved = _uname in (home_team.team_name,
                                                        away_team.team_name)
                                if _uinvolved or _cand.get("weight", 0) >= 60:
                                    _facts = _cand.get("facts") or {}
                                    _home = home_team.team_name
                                    _spec = {
                                        "kind": "grudge_callback",
                                        "home": _home,
                                        "away": away_team.team_name,
                                        "short": incident_short(_facts),
                                        "first_meeting": not _cand.get("ref_count"),
                                        "room_line":
                                            interpret(_cand, "room", _home) or "",
                                        "fans_line":
                                            interpret(_cand, "fans", _home) or "",
                                        "media_line":
                                            interpret(_cand, "media", _home) or "",
                                        "league_line":
                                            interpret(_cand, "league", _home) or "",
                                        "involved": (home_team.team_name,
                                                     away_team.team_name),
                                    }
                                    if _deliver_spec(self, _spec):
                                        _led.mark_referenced(_cand["id"])
                        except Exception:
                            pass
                        self._grudge_week_market(game_date, home_team, away_team)
                    # Unified engine 2026-10-04: GameSim replaces AdvancedGameSim
                    from simulation import GameSim
                    sim_engine = GameSim(
                        home_team, away_team,
                        atmosphere=_pregame_atmosphere(
                            home_team, away_team,
                            league=getattr(self, "league", None),
                            milestone_home=home_team.team_name in
                            getattr(self, "_milestone_watch_teams", set()),
                            ceremony=bool(getattr(home_team, "_pending_ceremony",
                                                  None)),
                            outdoor=_outdoor_info is not None),
                        league=getattr(self, "league", None),
                        # High-fidelity (2026-10-04): user's team games sim at
                        # 1-second ticks (visualizer fidelity). Other games use
                        # coarse ticks for speed. Same engine, same outcomes.
                        high_fidelity=bool(
                            getattr(home_team, "is_user_team", False) or
                            getattr(away_team, "is_user_team", False)))
                    if talk_boost != 1.0 and self.user_team is not None:
                        sim_engine.set_team_talk_boost(self.user_team.team_name, talk_boost)
                    # D1: the user's explicit coach instruction from the
                    # game-day bundle -- uniform channel, inert on the quick
                    # path (no hit classifier), but accepted for parity.
                    # "none" is the explicit no-instruction call: nothing to set.
                    if (_bundle_instruction and _bundle_instruction != "none"
                            and self.user_team is not None):
                        try:
                            sim_engine.set_coach_instruction(
                                self.user_team.team_name, _bundle_instruction)
                        except Exception:
                            pass
                    # Pregame ceremony (if one is queued): electric building via
                    # the atmosphere flag above, plus the room's one-game bump.
                    try:
                        import immortality as _im2
                        _im2.consume_ceremony(self, home_team, sim_engine)
                    except Exception:
                        pass
                    winner, loser, scores, events, notable_events = sim_engine.run()
                    # Career service time (waiver-exemption input). Preseason
                    # exhibitions don't count toward the 160-game threshold.
                    try:
                        self._credit_nhl_games_played(home_team, away_team,
                                                      preseason=is_preseason)
                    except Exception:
                        pass
                    # Narrative: the quick-sim never modeled fights/brawls, so
                    # roll them post-game through the shared incident module
                    # (same dice GameSim uses live); record the night's stories
                    # for both engines. Headlines for the user's game only.
                    # Skipped for preseason -- exhibitions build no lore.
                    if not is_preseason:
                        try:
                            _nwent_ot = any(
                                isinstance(_e, dict) and _e.get('period', 0) > 3
                                for _e in (notable_events or []))
                            _nshootout = any(
                                isinstance(_e, dict) and _e.get('event') == 'Shootout Goal'
                                for _e in (notable_events or []))
                            self._narrative_postgame(
                                sim_engine, home_team, away_team, scores,
                                went_ot=_nwent_ot, shootout=_nshootout,
                                roll_incidents=True, deliver_headlines=True,
                                game_date=game_date)
                        except Exception:
                            pass
                    # Revert AI tactics + file tactical intel on the user's systems
                    if _qs_adapted is not None:
                        try:
                            from adaptive_rivals import revert_adaptation
                            revert_adaptation(_qs_adapted, _qs_plan)
                        except Exception:
                            pass
                        try:
                            import tactics as _tx
                            _uname = self.user_team.team_name
                            _user_home = home_team == self.user_team
                            _ugoals = scores[0] if _user_home else scores[1]
                            _agoals = scores[1] if _user_home else scores[0]
                            _ushots = sum(
                                _ps.get('shots', 0)
                                for _ps in (sim_engine.stats.get(_uname, {})
                                            or {}).values()
                                if isinstance(_ps, dict))
                            _tx.record_tactical_intel(_qs_adapted, self.user_team,
                                                      _ugoals, _agoals,
                                                      _ushots or None, None)
                        except Exception:
                            pass
                    # AdvancedGameSim does not touch player season stats --
                    # except in preseason, where nobody's stats count.
                    stats_from_events = not is_preseason

                # Update league standings and store game result for user team games
                # (preseason: stored for viewing, standings untouched).
                self._process_single_game_result(game_date, home_team, away_team, winner, loser, scores, events, notable_events, sim_engine,
                                                 stats_from_events=stats_from_events,
                                                 preseason=is_preseason)
                # Lore: deliver headlines from the watched game (line brawl, ...).
                # Preseason: no lore, no media circus, no board/morale fallout.
                if not is_preseason:
                    try:
                        import headlines
                        headlines.drain_sim_headlines(self, sim_engine)
                    except Exception:
                        pass
                # Legacy events: permanent season memory for outdoor games.
                if locals().get("_outdoor_info") is not None:
                    try:
                        import outdoor_games as _ogr
                        _ogr.record_outdoor_result(self, _outdoor_info,
                                                   scores[0], scores[1])
                    except Exception:
                        pass
                # Media engine: post-game interviews, narratives, fines, beefs.
                # (Not for preseason -- September hockey gets box scores only.)
                # went_ot is computed up here (it used to be read before
                # assignment and only survived inside the try/except).
                went_ot = len([e for e in (notable_events or []) if isinstance(e, dict) and e.get('period', 0) > 3]) > 0
                if not is_preseason:
                    try:
                        import media_engine
                        _mev = media_engine.cover_game(
                            getattr(self, 'league', None), home_team, away_team,
                            winner, loser, scores, went_ot, game_date)
                        media_engine.route_events(self, _mev, game_date)
                    except Exception:
                        pass
                # FM-style: board, profile, morale, post-match presser.
                # (Not for preseason -- the board doesn't judge exhibitions.)
                if not is_preseason:
                    self._career_after_user_game(winner, loser, scores, home_team, away_team, went_ot, sim_engine)

            # Process other games using batch processing
            if other_games:
                self._simulate_games_batch(other_games)

    def _rivalry_pregame(self, todays_games):
            """Pregame rivalry hype for the user's games.

            Narrative ignition (Muck 2026-10-02): rivalry heat was visible in the
            calendar but never reached the user before puck drop. Now high-heat
            rivalry games involving the user's team get a pregame headline.
            Never raises.
            """
            try:
                from narrative_ledger import matchup_narrative as _mn
                from headlines import deliver_spec as _deliver_spec
                user_team = getattr(self, "user_team", None)
                if user_team is None:
                    return
                user_name = getattr(user_team, "team_name", "")
                league = getattr(self, "league", None)
                for game in todays_games or []:
                    try:
                        if isinstance(game, dict):
                            home, away = game.get("home_team"), game.get("away_team")
                        else:
                            home, away = game[1], game[2]
                        hn = getattr(home, "team_name", "")
                        an = getattr(away, "team_name", "")
                        if user_name not in (hn, an):
                            continue
                        narr = _mn(home, away, league=league) or {}
                        heat = float(narr.get("rivalry_heat", 0) or 0)
                        if heat < 50:
                            continue
                        tags = narr.get("hype_tags", []) or []
                        tag_str = f" ({', '.join(tags)})" if tags else ""
                        _deliver_spec(self, {
                            "kind": "rivalry_pregame",
                            "text": f"Bad blood tonight: {away} at {home}. "
                                    f"The rivalry is at a boil{tag_str}.",
                            "home": hn, "away": an,
                            "involved": (hn, an),
                        })
                    except Exception:
                        continue
            except Exception:
                pass

    def _simulate_playoff_day(self):
            """Advance one playoff day through the date-driven path.

            Sims today's scheduled playoff games via the bracket
            (exactly-once: entries the bracket controls already played are
            skipped), advances finished rounds, and crowns the champion.
            No regular-season machinery (maintenance, AI decisions, the
            game-day bundle) runs during the tournament -- the bracket owns
            those weeks, and both playoff paths stay equivalent.
            """
            try:
                self._set_continue_feedback(True, "Simulating playoff games...")
            except Exception:
                pass
            try:
                league = getattr(self, 'league', None)
                bracket = getattr(league, 'playoff_bracket', None)
                if bracket is None:
                    return
                # Restored brackets lose their app pointer on save/load --
                # re-point it so stars/ledger read the right date.
                if getattr(bracket, 'app', None) is None:
                    try:
                        bracket.app = self
                    except Exception:
                        pass
                today = getattr(self, 'current_date', None)
                # Normalize today to a date for comparison (save/load can leave
                # datetime vs date mismatches that silently skip all games).
                try:
                    from datetime import date as _date, datetime as _dt
                    if isinstance(today, _dt):
                        today = today.date()
                except Exception:
                    pass
                for entry in list(getattr(league, 'schedule', None) or []):
                    if not isinstance(entry, dict) or not entry.get('playoff'):
                        continue
                    try:
                        _ed = entry.get('date')
                        if isinstance(_ed, _dt):
                            _ed = _ed.date()
                        # String fallback: parse ISO format.
                        if isinstance(_ed, str):
                            try:
                                _ed = _dt.fromisoformat(_ed).date()
                            except Exception:
                                continue
                        if _ed != today:
                            continue
                    except Exception:
                        continue
                    try:
                        bracket.try_play_scheduled_game(
                            entry.get('series_id'), entry.get('series_game'))
                    except Exception:
                        continue
                # A finished round publishes the next one (dynamic start:
                # REST_DAYS after the last completed series). Idempotent --
                # safe if the bracket window already advanced it. Only try
                # when every series in the current round is actually done,
                # so incomplete days stay quiet.
                try:
                    _cur = getattr(bracket, 'current_round', '')
                    _series = (getattr(bracket, 'playoff_series', {})
                               or {}).get(_cur) or []
                    if _series and all(
                            getattr(s, 'is_complete', False) for s in _series):
                        bracket.advance_to_next_round(_cur)
                except Exception:
                    pass
                # Champion crowned -> Cup recap, then the offseason. The Cup
                # is never skipped: no offseason before a champion.
                if getattr(bracket, 'stanley_cup_champion', None) is not None:
                    try:
                        self._maybe_send_cup_recap()
                    except Exception:
                        pass
                    try:
                        self._start_offseason()
                    except Exception:
                        pass
                    return
                try:
                    self.current_date += timedelta(days=1)
                except Exception:
                    pass
                try:
                    self.game_manager.current_date = self.current_date
                except Exception:
                    pass
                # Narrative ignition (Muck 2026-10-02): deliver the day's
                # "Around the League" digest -- the top AI-game stories the
                # user didn't see live.
                try:
                    import league_digest as _ld
                    _ld.deliver_digest(self)
                except Exception:
                    pass
                try:
                    if hasattr(self, 'dashboard') and hasattr(
                            self.dashboard, 'refresh_dashboard'):
                        self.dashboard.refresh_dashboard()
                except Exception:
                    pass
                try:
                    self.after_idle(self.update_all_views)
                except Exception:
                    pass
            finally:
                try:
                    self._set_continue_feedback(False)
                except Exception:
                    pass

    def _trim_history_logs(self):
            """Bound game_results/news_log so saves and scans stay O(season)."""
            if len(self.game_results) > \
                    self.RESULTS_HISTORY_CAP + self.RESULTS_TRIM_BATCH:
                del self.game_results[:self.RESULTS_TRIM_BATCH]
                self._rebuild_result_index()
            if len(self.news_log) > self.NEWS_HISTORY_CAP + self.NEWS_TRIM_BATCH:
                del self.news_log[:self.NEWS_TRIM_BATCH]

    def _playoffs_in_progress(self) -> bool:
        """True while a generated bracket is alive and uncrowned.

        The regular season is complete AND league.playoff_bracket holds
        a real (non-projection) bracket with no champion yet. Mid-season
        projections never reach league.playoff_bracket, and the
        season-complete check excludes them anyway.

        SAVE/LOAD ROBUSTNESS (Chris 2026-10-04, priority): after restoring
        a mid-playoff save, the season-complete check can fail (standings
        wiped, game-count mismatch) even though a live bracket exists. If
        the bracket is real, uncrowned, and has actual series in it, the
        playoffs are in progress -- period. This prevents the 420-day
        limbo where the date advances with no games simmed and no champion.
        """
        try:
            league = getattr(self, 'league', None)
            bracket = getattr(league, 'playoff_bracket', None)
            if bracket is None \
                    or bool(getattr(bracket, 'is_projection', False)):
                return False
            if getattr(bracket, 'stanley_cup_champion', None) is not None:
                return False
            # A live bracket with real series = playoffs in progress,
            # even if the season-complete check fails post-restore.
            try:
                _series = getattr(bracket, 'playoff_series', None) or {}
                _has_series = any(
                    _series.get(r) for r in (
                        'wild_card', 'division_semifinals', 'division_finals',
                        'conference_finals', 'stanley_cup_final'))
                if _has_series:
                    return True
            except Exception:
                pass
            # Fallback: the original season-complete gate.
            if not self._check_season_complete():
                return False
            return True
        except Exception:
            return False

    def end_of_season(self):
        """Handle end of regular season with awards and transition options."""
        # SLATE GUARANTEE, Part 2 (2026-10-02, BUG-003/004/005): audit the
        # season slate BEFORE anything else -- before the once-per-season
        # guard below. If any NHL club is short of its scheduled games the
        # handler stops loudly (raise in headless/bulk, day-blocker in GUI)
        # and we bail here, so a short season can never slide silently into
        # awards, playoffs or the offseason.
        _slate_short = self._audit_season_slate()
        if _slate_short:
            self._handle_slate_shortfall(_slate_short)
            return
        # Guard: the season-end flow must only fire ONCE per season. Without
        # this, every Continue press after the playoffs start re-shows the
        # season summary / playoff prompt, and there is no path from a
        # completed playoff bracket to the offseason (soft-lock).
        season_year = getattr(getattr(self, 'league', None), 'season_year', None)
        if getattr(self, '_season_end_handled_year', None) == season_year:
            if self._playoffs_complete():
                self._start_offseason()
            elif getattr(self, '_bulk_simming', False):
                # Bulk sim: drive the bracket to completion automatically.
                self.open_playoffs_window()
                w = (getattr(self, 'open_windows', None) or {}).get('playoffs')
                try:
                    if w is not None and w.winfo_exists():
                        if not getattr(w, 'playoff_bracket', None):
                            w._generate_bracket()
                        w._simulate_all_playoffs()
                    else:
                        # No GUI window (headless bulk sim): drive the
                        # bracket directly. Added 2026-10-01 (playthrough
                        # B2): without this the try block silently skipped,
                        # _playoffs_complete() stayed False, and the season
                        # stalled forever. Mirrors
                        # PlayoffView._generate_bracket (league-attached
                        # bracket) + the headless _run_games loop.
                        self._simulate_playoffs_headless()
                    # Cup decided in bulk: send the awarding recap now.
                    try:
                        self._maybe_send_cup_recap()
                    except Exception:
                        pass
                except Exception:
                    pass
                if self._playoffs_complete():
                    self._start_offseason()
            else:
                # Re-entry with the choice deferred: re-present the card
                # rather than opening the bracket (the user never chose).
                # Playoffs actually in progress: focus the bracket.
                _parked = False
                try:
                    _sess = (getattr(self, "pending_sessions", None) or {}).get(
                        "playoffs_mode") or {}
                    _dlg = (_sess.get("dialogs") or {}).get(
                        "playoffs_mode_card") or {}
                    _parked = bool(_dlg.get("parked")) and not _dlg.get(
                        "answered")
                except Exception:
                    _parked = False
                if _parked:
                    try:
                        from popup_system import represent_dialog
                        represent_dialog("playoffs_mode", "playoffs_mode_card",
                                         parent=self)
                    except Exception:
                        pass
                else:
                    self.open_playoffs_window()
            return
        self._season_end_handled_year = season_year

        # Vezina GM vote first: 31 AI GMs + the human ballot decide it
        # before anything banks awards off the model ranking.
        try:
            self._conduct_vezina_vote()
        except Exception:
            pass
        # Bank regular-season reputations before anything else touches stats.
        # (Has its own once-per-season guard; safe under the re-entry guard above.)
        # Never raises -- a reputation failure must not stall the season-end
        # transition (the day loop aborts without advancing the date).
        try:
            self._update_player_reputations()
        except Exception:
            pass
        # Wave B D48: season-end respect decay -- a season's dealings fade
        # toward each GM's stature-derived baseline (goodwill k=0.25,
        # forgiveness k=0.10). Fires once per season, under the guard above.
        try:
            import reputation_system as _rs
            _rs.decay_gm_respect(getattr(self, "league", None))
        except Exception:
            pass
        # Show season summary first (skip the modal dialog when bulk simming)
        if not getattr(self, '_bulk_simming', False):
            self._show_season_summary()

        # Draft state is per-year on the league (draft_held_years); nothing to reset.

        # Check if playoffs should start
        # Headless detection: if running without UI, auto quick-sim
        # (prevents soft-lock when dialog can't be answered)
        _is_headless = getattr(self, '_headless_sim', False)
        if getattr(self, '_bulk_simming', False):
            result = True  # bulk sims auto-start playoffs, matching test behavior
        elif _is_headless:
            result = False  # headless: auto quick-sim, don't wait for dialog
        else:
            # Gating T2-Phase 3: non-modal choice card. Yes opens the
            # bracket; No quick-sims headless. Dismiss = defer (the card
            # is re-presented if end_of_season is re-entered; the
            # _season_end_handled_year guard keeps it honest).
            from popup_system import ask_card as _pm_ask_card
            _set_playoffs_mode_app(self)

            def _pm_on_answer(_ans, _self=self):
                _playoffs_mode_answer(
                    "playoffs_mode", "playoffs_mode_card", bool(_ans),
                    season_year=season_year)

            _pm_ask_card(
                self, "Playoffs",
                "Play through the Stanley Cup Playoffs?\n\n"
                "Play Interactive: open the bracket and sim it yourself.\n"
                "Quick-Sim: the tournament is decided instantly and the "
                "season rolls to the offseason.",
                [("Play Interactive", True, "primary"),
                 ("Quick-Sim", False, "secondary")],
                on_answer=_pm_on_answer,
                session_id="playoffs_mode", dialog_id="playoffs_mode_card",
                resolver="playoffs_mode_answer",
                resolver_args={"season_year": str(season_year)})
            return

        if result:
            self.open_playoffs_window()
        else:
            # Declined the interactive bracket: the tournament still
            # happens -- quick-sim it headless so the season always crowns
            # a champion, then roll to the offseason.
            self._quick_sim_playoffs_headless()
            self._start_offseason()

    def _ask_game_mode_dialog(self, home_team, away_team):
        """Pre-game modal: Quick Sim or Watch Live? Returns 'quick'/'watch'.

        UI-agnostic: asks via _ui_notify, defaults to 'quick' headless.
        UI subclasses override with a real dialog.
        """
        result = self._ui_notify("ask_game_mode", home_team, away_team)
        if isinstance(result, str) and result in ('quick', 'watch'):
            return result
        return 'quick'


    def _cap_compliance_blocker(self):
            """Return a blocker dict if the NHL roster exceeds the salary cap.

            Uses the central cap accounting (roster salaries + all dead-cap
            penalties), so the blocker agrees with trade validation and the
            cap UI -- AI and user see identical numbers.

            Wave B D45 (waiver-aware): players on the wire count their FULL
            hit in the accounting (real NHL -- the shed is gone), but an
            in-flight corrective waive is not a day-advance hard block. When
            the overage resolves once the wire clears (burial rule), the
            blocker stands down; the wire clock is doing its job.
            """
            team = getattr(self, 'user_team', None)
            if team is None:
                return None
            try:
                from salary_cap_system import cap_breakdown, compliance_charge
                bd = cap_breakdown(team)
            except Exception:
                return None
            # R1 (roster limits): the league exception -- emergency fill-ins are
            # cap-exempt at the day gate (summonable even over the cap, per
            # Chris's deadlock ruling). Subtract their charge before judging
            # compliance; zero when no fillers are on the roster.
            try:
                import roster_limits as _rl
                _filler_charge = int(_rl.emergency_filler_charge(team) or 0)
            except Exception:
                _filler_charge = 0
            if not bd["over_cap"]:
                return None
            try:
                # Pending wire resolves it -- not a hard block. The filler
                # charge is excluded first (the league exception: emergency
                # fill-ins are cap-exempt at the day gate). LTIR relief raises
                # the effective ceiling (ir_system.py) -- a team using LTIR
                # space is compliant by design.
                _ltir_relief = 0
                try:
                    import ir_system as _irs
                    _ltir_relief = int(_irs.ltir_relief(team) or 0)
                except Exception:
                    pass
                if (int(compliance_charge(team)) - _filler_charge
                        <= int(bd["cap"]) + _ltir_relief):
                    return None
            except Exception:
                pass
            over = -bd["space"]
            detail = (f"Cap charge ${bd['total']/1e6:.2f}M is ${over/1e6:.2f}M over "
                      f"the ${bd['cap']/1e6:.2f}M cap "
                      f"(roster ${bd['roster']/1e6:.2f}M")
            if bd["dead_cap"]:
                detail += f" + dead cap ${bd['dead_cap']/1e6:.2f}M"
            detail += "). Shed salary via trade, waivers, or demotion before advancing."
            # 2026-10-01 (Sim A S5 debug): expired contracts still count until the
            # GM acts, so a "phantom" overage is often unsigned players, not real
            # payroll. Point the GM at the actual fix instead of just shedding.
            try:
                _unsigned_n = sum(
                    1 for _p in (getattr(team, "roster", None) or [])
                    if getattr(getattr(_p, "contract", None),
                               "years_remaining", 1) == 0)
            except Exception:
                _unsigned_n = 0
            if _unsigned_n:
                detail += (f" {_unsigned_n} unsigned player(s) (expired contracts) "
                           f"still count against the cap -- re-sign them or move "
                           f"them on first.")
            return {
                'id': 'salary_cap',
                'title': 'Roster exceeds salary cap',
                'detail': detail,
                'action': ('Open Trade Center', self.open_trade_window),
                'auto_action': ('Auto-shed salary (waiver-safe)',
                                lambda: self._auto_fix_cap(team, over)),
            }

    def _career_after_user_game(self, winner, loser, scores, home_team, away_team,
                                    went_ot: bool, sim_engine=None):
            """Board/profile/morale updates + post-match presser after user games."""
            try:
                team = self.user_team
                user_won = (winner == team)
                my_strength = self._career_team_strength(team)
                opp = away_team if home_team == team else home_team
                opp_strength = self._career_team_strength(opp)
                was_favorite = my_strength >= opp_strength

                delta = self.career.board.record_result(
                    user_won, went_ot, was_favorite,
                    today_iso=self.current_date.isoformat())
                self.career.profile.record_result(user_won, went_ot, is_playoff=False)

                # Board crisis (8-game skid, disastrous start): surface it as news.
                if self.career.board.last_crisis:
                    self.add_news("🏛️ " + self.career.board.last_crisis)

                # Dressing room mood swing
                for p in (getattr(team, "roster", []) or []):
                    m = getattr(p, "morale", 70) or 70
                    h = getattr(p, "happiness", 70) or 70
                    if user_won:
                        p.morale = min(100, m + 5)
                        p.happiness = min(100, h + 3)
                    else:
                        p.morale = max(1, m - 5)
                        p.happiness = max(0, h - 3)

                if self.career.board.sacked:
                    self._career_handle_sack()
                    return

                # Post-match presser -> interactive inbox message (no modal).
                # The press waits in the inbox; answers apply morale/board
                # effects exactly as the old popup did.
                if self._career_prompts_allowed():
                    from game_classes import EmailMessage
                    hs, aws = scores
                    score_str = f"{hs}-{aws}"
                    star = self._career_star_of_game(sim_engine, team)
                    ctx = {"n": "a few",
                           "drama": getattr(team, "_recent_drama", None)}
                    questions = manager_career.build_postmatch_presser(
                        team, opp, user_won, went_ot, score_str, star, ctx)
                    if questions:
                        opp_name = getattr(opp, 'team_name', 'the opposition')
                        self.send_email_to_user(EmailMessage(
                            sender="Media Relations", sender_type="Media",
                            subject=f"Post-match presser: {score_str} vs {opp_name}",
                            content=(f"Final: {score_str}. The press wants a word. "
                                     "Answer below -- your words move the dressing "
                                     "room and the board."),
                            date_sent=self.current_date, category="Media",
                            requires_response=True, priority=3,
                            action_type="postmatch_presser",
                            action_data={
                                "game_date": self.current_date.isoformat(),
                                "questions": questions,
                                "answered": [False] * len(questions),
                                "kind": "post-match",
                            }))
            except Exception as e:
                print(f"Career post-game error (non-fatal): {e}")

    def _career_prompts_allowed(self) -> bool:
            """Interactive prompts only for manual day-by-day play."""
            return (not getattr(self, "_bulk_simming", False)
                    and self.career.prompts_enabled
                    and not self.career.board.sacked)

    def _career_team_talk(self, opponent):
            """Show pre-match team talk. Returns sim boost multiplier, or None
            when the world was reloaded under a waiting talk (the caller must
            abort the stale day sim -- see _abort_day_sim).

            Screen + callback/session flow (gating: park-on-navigation): the
            talk is a full-screen focus card (not a popup); the answer arrives
            via on_done into a date-keyed Tier-B session that carries the full
            game context (opponent, situation) so a parked talk re-presents
            exactly. Navigating away PARKS the session -- the waiter is NOT
            released, the day sim stays paused on the talk, and a navbar
            resume chip brings the exact session back. Dismiss = defer
            ("not now"): an unanswered talk can never resolve as a silent
            neutral. "Say nothing" remains the explicit, deliberate neutral.
            """
            if not self._career_prompts_allowed():
                return 1.0
            from popup_system import get_pending_session
            my_strength = self._career_team_strength(self.user_team)
            opp_strength = self._career_team_strength(opponent)
            situation = "favorite" if my_strength > opp_strength + 5 else (
                "underdog" if opp_strength > my_strength + 5 else "even")
            if self.career.board.season_losses >= 3 and self._career_team_games() >= 4:
                # recent form check for "after_loss"
                pass
            context = {"situation": situation,
                       "opponent_name": getattr(opponent, "team_name", "the opposition")}
            try:
                _opp_id = getattr(opponent, "id", None)
                _opp_key = _opp_id or getattr(opponent, "team_name", "?")
                _date = self.current_date.isoformat()
            except Exception:
                _opp_id, _opp_key, _date = None, "?", "?"
            session_id = f"team_talk:{_date}:{_opp_key}"

            # Tier-B session carries the full context from creation so a
            # parked talk (navigation, save/load) re-presents exactly.
            # Plain data only -- this session is save-serialized.
            sess = get_pending_session(self, session_id)
            if sess is not None:
                try:
                    sess["kind"] = "team_talk"
                    tt = sess.get("team_talk")
                    if not isinstance(tt, dict):
                        tt = {}
                        sess["team_talk"] = tt
                    tt.update({
                        "when": "prematch",
                        "date": _date,
                        "opponent_id": _opp_id,
                        "opponent_name": context["opponent_name"],
                        "situation": situation,
                        "context": dict(context),
                        "parked": bool(tt.get("parked", False)),
                    })
                except Exception:
                    pass

            # Stale sessions (other dates) can never be resumed -- their game
            # is gone. Prune so the dict stays small and honest.
            self._prune_team_talk_sessions(keep_date=_date)

            def _session_boost():
                try:
                    sess = get_pending_session(self, session_id)
                    prev = ((sess or {}).get("dialogs") or {}).get("talk") or {}
                    if prev.get("answered"):
                        return float(prev.get("boost", 1.0))
                except Exception:
                    pass
                return None

            prev_boost = _session_boost()
            if prev_boost is not None:
                # Consume-once: a parked answer is single-use; the next talk
                # (new date/opponent) starts clean.
                self._consume_team_talk_session(session_id)
                return prev_boost

            # Epoch guard: a save/load under a waiting talk orphans this
            # frame's game objects. on_game_loaded bumps the epoch and wakes
            # us; a mismatch here aborts instead of simming on dead state.
            # UI-agnostic: Tk dialog only when a Tk runtime is present.
            # Headless/Qt: fall through to neutral 1.0 via _ui_notify.
            try:
                import tkinter as _tk
            except ImportError:
                _tk = None
            if _tk is None:
                self._ui_notify("team_talk", opponent)
                return 1.0
            _epoch = getattr(self, "_team_talk_epoch", 0)
            wake = _tk.BooleanVar(master=self, value=False)
            self._active_team_talk = {
                "session_id": session_id, "wake": wake, "epoch": _epoch,
            }
            try:
                _view = self._present_team_talk_screen(sess, wake, _epoch)
                if _view is None:
                    # Screen could not present (genuine failure, not
                    # navigation): pre-existing fail-safe, not a silent park.
                    return 1.0
                self.wait_variable(wake)
            except Exception:
                pass
            finally:
                try:
                    if getattr(self, "_active_team_talk", None) is not None and \
                            self._active_team_talk.get("wake") is wake:
                        self._active_team_talk = None
                except Exception:
                    pass
            if getattr(self, "_team_talk_epoch", 0) != _epoch:
                return None
            prev_boost = _session_boost()
            if prev_boost is not None:
                self._consume_team_talk_session(session_id)
                return prev_boost
            # Unreachable in practice: the waiter is released only by an
            # answer (navigation parks, never releases). Fail closed to the
            # pre-existing neutral only if something truly unexpected broke
            # the wait -- never silently mid-flow.
            return 1.0

    def _check_for_event_day(self):
            """Detect tentpole event days (draft, deadline, free agency).

            - Runs the entry draft once per year on June 23-25. (The draft used
              to be Monday-gated, so in seasons where June 23-25 had no Monday
              it was silently skipped entirely.)
            - Prompts the event-day hub once per year per event.
            State lives on the league object so it survives save/load.
            """
            try:
                from event_day_hubs import get_todays_event, is_draft_day, prompt_event_day
            except ImportError as e:
                debug_print(f"Event-day hubs unavailable: {e}")
                return

            league = getattr(self.game_manager, 'league', None) or getattr(self, 'league', None)
            if league is None:
                return

            today = self.current_date
            year = today.year

            # Entry draft: run once per year inside the draft window. Runs BEFORE
            # the hub prompt so Draft Day Central shows the real draft class.
            if is_draft_day(today):
                held = set(getattr(league, 'draft_held_years', None) or [])
                if year not in held:
                    # Rights lifecycle BEFORE the draft: unsigned CHL prospects
                    # whose rights expire this summer re-enter THIS draft (the
                    # class generator folds league.draft_reentries in). The
                    # end_of_season backstop skips via the per-draft-year guard.
                    try:
                        league._rollover_draft_rights(reference_year=year)
                    except Exception:
                        debug_print("Draft-day rights rollover failed (non-fatal):")
                        import traceback
                        traceback.print_exc()
                    try:
                        self._hold_entry_draft(year)
                    except Exception:
                        debug_print(f"Entry draft failed for {year}:")
                        import traceback
                        traceback.print_exc()
                    else:
                        held.add(year)
                        league.draft_held_years = sorted(held)

            # Draft lottery: televised reveal on May 8, once per year. Runs the
            # real-odds lottery, delivers the inbox card (with a watch-the-reveal
            # action), and applies fan/room reactions for the user's team.
            try:
                from draft_lottery import LOTTERY_DAY_MONTH, LOTTERY_DAY_DAY
                if (today.month, today.day) == (LOTTERY_DAY_MONTH, LOTTERY_DAY_DAY):
                    lotto_held = set(getattr(league, 'lottery_held_years', None) or [])
                    if year not in lotto_held:
                        try:
                            self._hold_draft_lottery(year)
                        except Exception:
                            debug_print("Draft lottery failed (non-fatal):")
                            import traceback
                            traceback.print_exc()
                        else:
                            lotto_held.add(year)
                            league.lottery_held_years = sorted(lotto_held)
            except Exception:
                pass

            # International windows: Olympics (rosters announced Feb 9, medals
            # Feb 22 of Olympic years -- the NHL goes dark Feb 10-24 via the
            # olympic_break in schedule generation) and World Championship
            # (May 12), each once per year. Instant lightweight resolution +
            # inbox card. Catch-up semantics live in the helper so a skipped
            # date still fires late, idempotently.
            try:
                self._daily_international_window(today, year, league)
            except Exception:
                debug_print("International window failed (non-fatal):")
                import traceback
                traceback.print_exc()

    def _close_trade_deadline(self, mgr):
            """3 PM: lock trading, announce the freeze, kill the clock."""
            try:
                mgr.deadline_passed = True
            except Exception:
                pass
            try:
                from email_generator import EmailGenerator
                email = EmailGenerator.create_league_announcement_email(
                    "Trade Deadline Has Passed",
                    "The 3:00 PM ET trade deadline has passed. No further trades "
                    "may be completed this season.\n\n"
                    f"League deals today: "
                    f"{mgr.deadline_stats.get('total_trades', 0)}.")
                email.is_urgent = True
                email.priority = 4
                self.send_email_to_user(email)
            except Exception:
                pass
            print("⏰ Trade deadline passed (3:00 PM ET). Trading locked.")
            # Wave B D48: deadline respect decay -- the deadline frenzy's warmth
            # and grudges fade toward each GM's stature-derived baseline
            # (asymmetric: goodwill k=0.25, forgiveness k=0.10).
            try:
                import reputation_system as _rs
                _rs.decay_gm_respect(getattr(self, "league", None))
            except Exception:
                pass

    def _credit_nhl_games_played(self, home_team, away_team, preseason=False):
            """Career NHL GP counter: one credit per rostered player per
            completed NHL game. This is the service-time half of waiver
            exemption (age is the other half) -- previously a frozen dice
            roll, now a number that actually moves with the season.
            Preseason exhibitions never count (like the real league)."""
            if preseason:
                return
            for _t in (home_team, away_team):
                try:
                    for _p in list(getattr(_t, "roster", None) or []):
                        try:
                            _p.nhl_games_played = int(
                                getattr(_p, "nhl_games_played", 0) or 0) + 1
                        except Exception:
                            pass
                except Exception:
                    pass

    def _deadline_tick_activity(self, mgr, tick):
            """Real AI-vs-AI trades for one 30-minute deadline window, scaled
            by urgency as 3 PM approaches. Deals execute for real (rosters
            change) and break as news."""
            import random
            import trade_engine as te
            import trade_storylines as tsl
            league = getattr(getattr(self, 'game_manager', None), 'league', None) \
                or getattr(self, 'league', None)
            if league is None:
                return
            user_name = getattr(getattr(self, 'user_team', None), 'team_name', '')
            teams = [t for t in getattr(league, 'teams', [])
                     if getattr(t, 'team_name', '') != user_name
                     and getattr(t, 'league_name', 'National Hockey League')
                     == 'National Hockey League']
            if not teams:
                return
            prog = mgr.clock_progress()
            # 0-3 real deals per window, more as the deadline nears.
            random.shuffle(teams)
            deals = 0
            for team in teams:
                if deals >= 3:
                    break
                if random.random() > tsl.ai_initiative_odds(self, team) * 0.45:
                    continue
                if self._try_ai_ai_deadline_deal(team, teams, te, tsl, mgr):
                    deals += 1
            # Trade-market bidding rounds advance once per deadline tick
            # (additive; the organic tick cap above is untouched).
            try:
                import trade_market
                trade_market.process_deadline_tick(
                    self, getattr(getattr(self, 'game_manager', None), 'league', None)
                    or getattr(self, 'league', None), mgr)
            except Exception as e:
                print(f"Trade market tick error (non-fatal): {e}")

    def _deliver_outdoor_pregame(self, info, home_team, away_team):
            """Inbox billing card for a Winter Classic / Stadium Series game.

            Fires once per outdoor game (~3/season), so it never spams. Wrapped
            defensively at every call site.
            """
            try:
                import outdoor_games as _ogd
                from headlines import deliver_spec as _deliver_spec
                pres = _ogd.pregame_presentation(info)
                _deliver_spec(self, {
                    "kind": "outdoor_pregame",
                    "event": info.get("event", "Outdoor Game"),
                    "home": home_team.team_name,
                    "away": away_team.team_name,
                    "venue_line": pres["venue_line"],
                    "alumni_line": pres["alumni_line"],
                    "rivalry_line": pres["rivalry_line"],
                    "involved": (home_team.team_name, away_team.team_name),
                })
            except Exception:
                pass

    def _dispatch_scout_value_tips(self):
            """Monthly pro-scout value reads -- for the USER and every AI GM.

            Even playing field: every team's Head Scout / Professional Scouts
            file their reads on the 1st. The user gets reads in the news feed;
            AI teams store theirs on the team object where their trade logic
            reads them (see trade_engine.scout_adjusted_value).

            Whether a read is RIGHT depends directly on that scout's
            judging_player_ability -- elite scouts spot real value, bad scouts
            chase ghosts. Same rules for silicon and flesh.

            Wave 1 (information asymmetry):
            - Every read is filed in the team's tip ledger via
              record_tip_call() and graded later against what actually
              happened -- the scout's track record, not hidden JPA, is what
              the user sees.
            - Design law: reads show evidence, uncertainty, provenance and
              the person responsible. Never "buy low" / "sell high".
            """
            try:
                import analytics_scouting as scout_mod
                import random as _r
            except ImportError:
                return
            try:
                league = self.league
                teams = list(getattr(league, "teams", []) or [])
                if not teams:
                    return
                try:
                    from game_classes import StaffRole
                    pro_roles = {StaffRole.HEAD_SCOUT, StaffRole.PROFESSIONAL_SCOUT}
                except Exception:
                    pro_roles = set()
                all_players = []
                for t in teams:
                    all_players.extend(getattr(t, "roster", []) or [])
                if not all_players:
                    return
                # Prospects get the same analytics treatment: every club's
                # farm pool is scanned for standouts, so underlying farm
                # numbers (not just pedigree) move prospect trade value.
                all_prospects = []
                for t in teams:
                    all_prospects.extend(getattr(t, "prospects", []) or [])
                # Signed minor-leaguers: same light farm metrics as the
                # prospects, labeled AHL so the scout card reads honestly.
                # This is the gem-finder for the farm -- cheap NHLe /
                # expectation / plus-minus reads, not NHL-grade shot
                # tracking, so the monthly pass stays fast.
                all_ahl = []
                for t in teams:
                    all_ahl.extend(getattr(t, "ahl_roster", []) or [])
                date_str = str(getattr(self, "current_date",
                                       __import__("datetime").date.today()))
                for team in teams:
                    scout_mod.ensure_analytics_fields(team)
                    staff = list(getattr(team, "staff", []) or [])
                    scouts = [s for s in staff
                              if getattr(s, "role", None) in pro_roles] if pro_roles else []
                    if not scouts:
                        continue
                    # Fresh sheet each month; stale reads don't linger.
                    team.scout_buy_tips = {}
                    team.scout_sell_tips = {}
                    for s in scouts:
                        scout_mod.ensure_analytics_fields(s)
                        # Tip cadence scales with the scout's eye (1-20 scale).
                        jpa20 = scout_mod._scout_jpa(s)
                        tip_chance = 0.20 + 0.50 * (jpa20 - 1) / 19.0
                        if _r.random() > tip_chance:
                            continue
                        buy_tips = scout_mod.scout_value_tips(
                            s, all_players, teams,
                            user_team=team, limit=2)
                        sell_tips = scout_mod.scout_sell_high_tips(
                            s, team, limit=2)
                        # Prospect reads ride the same rails: filed into the
                        # buy-tip book, graded by the same ledger, priced by
                        # scout_adjusted_value(), and printed to the user's
                        # news feed below. Analytics matter for the kids too.
                        prospect_tips = []
                        if all_prospects:
                            try:
                                prospect_tips = scout_mod.scout_prospect_tips(
                                    s, all_prospects, user_team=team, limit=2)
                            except Exception:
                                prospect_tips = []
                        ahl_tips = []
                        if all_ahl:
                            try:
                                ahl_tips = scout_mod.scout_prospect_tips(
                                    s, all_ahl, user_team=team, limit=2,
                                    kind="AHL")
                            except Exception:
                                ahl_tips = []
                        buy_tips = (list(buy_tips) + list(prospect_tips)
                                    + list(ahl_tips))
                        # File every read in the ledger: the scout's call is
                        # graded against what happens later. This is what
                        # builds (or exposes) track records.
                        for tip in buy_tips:
                            try:
                                scout_mod.record_tip_call(
                                    s, team, "buy", tip["player"], date_str,
                                    reason=tip.get("reason", ""))
                            except Exception:
                                pass
                        for tip in sell_tips:
                            try:
                                scout_mod.record_tip_call(
                                    s, team, "sell", tip["player"], date_str,
                                    reason=tip.get("reason", ""))
                            except Exception:
                                pass
                        # Tips are private to the club whose scout filed them --
                        # filed where the trade engine reads them, and shown on
                        # the scout's own staff card (open reads). They are
                        # NEVER broadcast in the news feed: no league-wide
                        # "hey look what someone found". The news feed carries
                        # performance headlines (hat tricks, shutouts); scout
                        # reads are your staff's private reports to you.
                        bt = getattr(team, "scout_buy_tips", None)
                        if bt is None:
                            team.scout_buy_tips = bt = {}
                        st = getattr(team, "scout_sell_tips", None)
                        if st is None:
                            team.scout_sell_tips = st = {}
                        for tip in buy_tips:
                            p = tip["player"]
                            pid = getattr(p, "id", id(p))
                            bt[pid] = {"jpa": tip["scout_jpa"],
                                       "correct": tip["correct"],
                                       "scout": tip["scout"],
                                       "scout_id": getattr(s, "id", ""),
                                       "name": tip.get("name", "?"),
                                       "pteam": tip.get("team", "?"),
                                       "kind": tip.get("kind", ""),
                                       "reason": tip.get("reason", ""),
                                       "risks": list(tip.get("risks", "") or []),
                                       "confidence": tip.get("confidence", "")}
                        for tip in sell_tips:
                            p = tip["player"]
                            pid = getattr(p, "id", id(p))
                            st[pid] = {"jpa": tip["scout_jpa"],
                                       "correct": tip["correct"],
                                       "scout": tip["scout"],
                                       "scout_id": getattr(s, "id", ""),
                                       "name": tip.get("name", "?"),
                                       "kind": tip.get("kind", ""),
                                       "reason": tip.get("reason", ""),
                                       "risks": list(tip.get("risks", "") or []),
                                       "confidence": tip.get("confidence", "")}
            except Exception:
                pass

    def _find_inbox_player(self, data):
            """Locate a player referenced by an inbox action (id, then name)."""
            pid = (data or {}).get("player_id")
            name = (data or {}).get("player_name")
            league = getattr(self, "league", None)
            pools = []
            try:
                for t in (getattr(league, "teams", []) or []):
                    pools.append(list(getattr(t, "roster", []) or []))
                pools.append(list(getattr(league, "free_agents", []) or []))
            except Exception:
                pass
            for pool in pools:
                for p in pool:
                    if pid and getattr(p, "id", None) == pid:
                        return p
            if name:
                for pool in pools:
                    for p in pool:
                        if getattr(p, "full_name", "") == name:
                            return p
            return None

    def _floor_compliance_blocker(self):
            """Return a blocker dict if the NHL roster sits under the salary
            floor (D46, Wave B).

            The floor is a hard league rule (real NHL): the day can't advance
            while the club is under it. The action sends the user to free
            agency -- signing is the fix. AI clubs never reach this state:
            ai_consider_trade rejects self-inflicted floor breaches and
            _enforce_salary_floor signs them back up the same day.
            """
            team = getattr(self, 'user_team', None)
            if team is None:
                return None
            try:
                from salary_cap_system import cap_breakdown
                bd = cap_breakdown(team)
            except Exception:
                return None
            if not bd.get("under_floor"):
                return None
            short = int(bd.get("floor", 0)) - int(bd.get("total", 0))
            return {
                'id': 'salary_floor',
                'title': 'Roster under the salary floor',
                'detail': (f"Payroll ${bd['total']/1e6:.2f}M is ${short/1e6:.2f}M "
                           f"under the ${bd['floor']/1e6:.2f}M salary floor. "
                           f"Sign free agents to reach the floor before advancing."),
                'action': ('Open Free Agency', self.open_free_agency_window),
            }

    def _generate_weekly_email_summary(self):
            """Generate a weekly email summary instead of daily emails to reduce CPU load"""
            try:
                # Only generate if there have been significant events this week
                recent_news = [item for item in self.news_log 
                              if item.get('date') and 
                              (self.current_date - item['date']).days <= 7]

                if len(recent_news) >= 3:  # Only send if there's enough news
                    self._generate_daily_emails()
            except Exception as e:
                print(f"Error generating weekly email summary: {e}")

    def _get_user_game_mode(self):
            """How the user's own games are presented. Migrates legacy bool."""
            try:
                sim = self.get_settings().get('simulation', {})
                mode = sim.get('user_game_mode')
                if mode in ('quick', 'watch', 'ask'):
                    return mode
                if sim.get('use_game_viewer', False):
                    return 'watch'
            except Exception:
                pass
            return 'ask'

    def _grudge_week_market(self, game_date, home_team, away_team):
            """Market a genuine feud as grudge week (sellout talk, loud billing).

            Returns True when marketed; the matchup+date is tracked so the
            post-game check can call out hollow overhype honestly.
            """
            try:
                from narrative_ledger import get_ledger as _gl
                _led = _gl(self)
                _mw = float(_led.memory_weight(home_team.team_name,
                                               away_team.team_name) or 0.0)
                if _mw < 60.0:
                    return False
                _mk = (home_team.team_name, away_team.team_name, str(game_date))
                _gm = getattr(self, "_grudge_marketed", None)
                if not isinstance(_gm, set):
                    _gm = set()
                    self._grudge_marketed = _gm
                _gm.add(_mk)
                self.add_news(
                    f"Grudge week in "
                    f"{getattr(home_team, 'city', home_team.team_name)}: "
                    f"{away_team.team_name} @ {home_team.team_name} -- "
                    f"the building is sold out and shaking. This one matters.")
                return True
            except Exception:
                return False

    def _inbox_contract_result(self, kind, person, name, salary, years,
                                   asking_price, extension, clause_kind="none",
                                   clause_list_size=10, reject_note=None):
            """FM24/EHM-style: contract news lands in the inbox. Counter-offers
            arrive as interactive messages (accept / new offer / walk away).

            clause_kind/size travel with a counter so the trade protection the
            user offered is still on the table when the inbox accept lands.
            reject_note overrides the rejected text (e.g. league-office veto)."""
            from game_classes import EmailMessage
            import trade_engine as _te3
            pid = getattr(person, "id", None)
            base = dict(sender="Agent", sender_type="Agent",
                        date_sent=date.today(), category="Contracts",
                        related_player_id=pid, priority=3, is_important=True)
            _clause_txt = _te3.clause_offer_label(clause_kind, clause_list_size) \
                if (clause_kind or "none") != "none" else ""
            if kind == "accepted":
                term = "extension" if extension else "contract"
                _prot = (f" It carries {_clause_txt}."
                         if _clause_txt else "")
                msg = EmailMessage(
                    subject=f"Signed: {name}",
                    content=(f"{name} has agreed to terms: "
                             f"${salary:,} per year over {years} year(s).{_prot}\n\n"
                             f"The {term} is finalized and the paperwork is filed "
                             f"with the league office."),
                    **base)
            elif kind == "rejected":
                _rej_text = (reject_note or
                             (f"{name} has rejected your offer of "
                              f"${salary:,} per year outright and is not "
                              f"countering at this time.\n\n"
                              f"His camp feels the number needs to be "
                              f"significantly higher before talks resume."))
                msg = EmailMessage(
                    subject=f"Talks break down: {name}",
                    content=_rej_text,
                    **base)
            else:  # counter -- interactive
                _still = (f" Your {_clause_txt} offer is still on the table."
                          if _clause_txt else "")
                # Market-demand signal: WHY the ask is what it is (qualitative).
                _msig = ""
                _ss3, _spos3 = "balanced", None
                try:
                    from popup_system import get_negotiation_session as _gns3
                    from salary_cap_system import \
                        scarcity_signal_text as _sst3
                    _ns3 = _gns3(self, person, defaults={})
                    _ss3 = str((_ns3 or {}).get("scarcity_signal", "balanced"))
                    _spos3 = (_ns3 or {}).get("scarcity_pos")
                    if _ss3 and _ss3 != "balanced":
                        _msig = "\n\nMarket: " + _sst3(_ss3, _spos3)
                except Exception:
                    _msig = ""
                msg = EmailMessage(
                    subject=f"Counter-offer: {name}",
                    content=(f"{name}'s camp has rejected your offer of "
                             f"${salary:,} per year, but they are willing to "
                             f"sign for ${asking_price:,} per year over "
                             f"{years} year(s).{_still}{_msig}\n\n"
                             f"Respond below -- the offer waits for you."),
                    requires_response=True,
                    action_type="contract_counter",
                    action_data={"player_id": pid, "player_name": name,
                                 "asking_price": int(asking_price),
                                 "years": int(years),
                                 "is_extension": bool(extension),
                                 "clause_kind": clause_kind or "none",
                                 "clause_list_size": int(clause_list_size or 10),
                                 "scarcity_signal": _ss3,
                                 "scarcity_pos": _spos3},
                    **base)
            self.send_email_to_user(msg)

    def _is_user_game_day(self) -> bool:
            """Cached check: does the user team play today?"""
            try:
                today = getattr(self, 'current_date', None)
                if getattr(self, '_user_game_day_cache_date', None) == today:
                    return bool(getattr(self, '_user_game_day_cache', False))
                val = self._career_user_game_today() is not None
                self._user_game_day_cache = val
                self._user_game_day_cache_date = today
                return val
            except Exception:
                return False

    def _mp_begin_waiver_flow(self, proposal, team, partner, vetoes,
                                  manager):
            """Stash a proposal behind clause-waiver prompts; ask about the
            first veto now. Returns (True, status, no-broadcast)."""
            import uuid as _uuid
            waiver_id = _uuid.uuid4().hex[:10]
            session_id = self._mp_peer_session_for_team(team.team_name)
            if session_id is None:
                return False, "Could not reach your client."
            self._mp_pending_ntc[waiver_id] = {
                "kind": "trade",
                "proposal": proposal,
                "vetoes": [{"player_id": str(getattr(v["player"], "id", "")),
                            "player_name": getattr(v["player"], "full_name",
                                                   "player"),
                            "clause": v.get("detail") or v.get("clause", "NTC"),
                            "dest": partner.team_name}
                           for v in vetoes],
                "veto_idx": 0,
                "team_id": team.team_name,
                "partner_id": partner.team_name,
            }
            return self._mp_send_next_waiver(waiver_id, session_id)

    def _mp_find_team(self, team_id):
            try:
                for t in self.league.teams:
                    if getattr(t, 'team_name', '') == team_id:
                        return t
            except Exception:
                pass
            return None

    def _mp_route_trade_offer(self, proposal):
            """Send a waiver-cleared proposal to its destination: instant AI
            evaluation, a host popup, or a routed offer to another human.
            Returns (ok, detail, broadcast)."""
            import trade_engine as te
            team = self._mp_find_team(proposal["proposer_team_id"])
            partner = self._mp_find_team(proposal["partner_team_id"])
            if team is None or partner is None:
                return False, "A club involved is gone.", True
            # Re-resolve assets against canonical state: rosters may have
            # moved since the proposal was built (waiver prompts take time).
            out_players = [self._mp_team_player(team, pid)
                           for pid in proposal["players_out"]]
            in_players = [self._mp_team_player(partner, pid)
                          for pid in proposal["players_in"]]
            out_picks = [self._mp_team_pick(team, kid)
                         for kid in proposal["picks_out"]]
            in_picks = [self._mp_team_pick(partner, kid)
                        for kid in proposal["picks_in"]]
            if any(p is None for p in out_players + in_players) or \
                    any(k is None for k in out_picks + in_picks):
                self._mp_clear_proposal_waivers(proposal)
                return False, \
                    "An asset changed clubs while you negotiated -- re-propose.", \
                    True
            proposal["_out_players"] = out_players
            proposal["_in_players"] = in_players
            proposal["_out_picks"] = out_picks
            proposal["_in_picks"] = in_picks

            league = getattr(self, "league", None)
            partner_session = self._mp_peer_session_for_team(partner.team_name)
            is_host_team = bool(getattr(partner, "is_user_team", False))

            if partner_session is not None:
                # Human-to-human: the other manager gets the offer live.
                import uuid as _uuid
                offer_id = _uuid.uuid4().hex[:10]
                self._mp_pending_offers[offer_id] = proposal
                offer_wire = self._mp_serialize_offer(
                    proposal, out_players, in_players, out_picks, in_picks)
                try:
                    peer_name = ""
                    try:
                        peer = self.mp_host.find_peer_by_team(partner.team_name)
                        peer_name = getattr(peer, "name", "")
                    except Exception:
                        pass
                    self.mp_host.send_trade_offer(
                        partner_session, offer_id, team.team_name,
                        proposal["manager"], offer_wire)
                except Exception:
                    self._mp_pending_offers.pop(offer_id, None)
                    self._mp_clear_proposal_waivers(proposal)
                    return False, "Could not reach the other manager.", True
                return (True,
                        f"Offer sent to {peer_name or partner.team_name} -- "
                        f"awaiting their answer.",
                        False)
            if is_host_team:
                return self._mp_offer_to_host(proposal, team, partner,
                                              out_players, in_players,
                                              out_picks, in_picks)
            # AI club: clear the partner's movement-clause vetoes the way the
            # AI deadline flow does (the player decides, same roll), then
            # evaluate the deal.
            try:
                for _v in te.trade_vetoes(partner, team, in_players, league):
                    _p = _v["player"]
                    _ok, _why = te.will_waive_ntc(_p, partner, team, league)
                    if not _ok:
                        self._mp_clear_proposal_waivers(proposal)
                        try:
                            self.mp_host.broadcast_chat(
                                f"Trade {team.team_name} -> {partner.team_name} "
                                f"died: {getattr(_p, 'full_name', 'player')} "
                                f"refused to waive ({_why}).")
                        except Exception:
                            pass
                        return False, (
                            f"{getattr(_p, 'full_name', 'A player')} refused "
                            f"to waive his clause -- deal is dead."), True
                    try:
                        _p.contract.ntc_waiver_for = team.team_name
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                ev = te.evaluate_trade(out_players + out_picks,
                                       in_players + in_picks,
                                       user_team=team, partner_team=partner)
                label = getattr(ev, "label", "")
            except Exception:
                label = ""
            # "You overpay" is from the proposer's perspective -- good for AI.
            if label in ("Fair deal", "You overpay"):
                ok, detail = self._mp_execute_mp_trade(proposal)
                return ok, detail, True
            self._mp_clear_proposal_waivers(proposal)
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {team.team_name} -> {partner.team_name} rejected "
                    f"({label or 'not fair value'}).")
            except Exception:
                pass
            return False, \
                f"{partner.team_name} rejected the offer ({label or 'value'}).", \
                True

    def _mp_team_pick(self, team, pick_id):
            """Find a draft pick owned by a team by pick id."""
            pid = str(pick_id or "")
            try:
                for picks in (getattr(team, "draft_picks", None) or {}).values():
                    for pk in picks or []:
                        if str(getattr(pk, "id", "")) == pid:
                            return pk
            except Exception:
                pass
            return None

    def _mp_team_player(self, team, player_id):
            """Find a player on a team's roster / AHL / prospects by id."""
            pid = str(player_id or "")
            for attr in ("roster", "ahl_roster", "prospects"):
                for p in getattr(team, attr, None) or []:
                    if str(getattr(p, "id", "")) == pid:
                        return p
            return None

    def _narrative_postgame(self, sim_engine, home_team, away_team,
                                  scores, went_ot=False, shootout=False,
                                  roll_incidents=True, deliver_headlines=False,
                                  game_date=None):
            """Shared post-game narrative hook (narrative_incidents.py).

            Rolls incidents for engines that don't model them live (AdvGS),
            records game stories for both engines, logs career moments to the
            players who earned them, and feeds the fight count back onto the
            sim so the grudge-week grader sees real numbers.
            Headlines only when deliver_headlines (user-involved games).
            Never raises; never touches scoring or stats.
            """
            try:
                import narrative_incidents as _ni
                from narrative_ledger import active_ledger
                home_score, away_score = scores[0], scores[1]
                rivalries = getattr(getattr(self, "league", None),
                                    "rivalries", None) or []
                res = _ni.process_postgame(
                    sim_engine, home_team, away_team,
                    int(home_score), int(away_score),
                    went_ot=bool(went_ot), shootout=bool(shootout),
                    rivalries=rivalries, ledger=active_ledger(),
                    roll_incidents=bool(roll_incidents),
                    game_date=game_date,
                    season_year=getattr(getattr(self, "league", None),
                                        "season_year", None))
                if roll_incidents and sim_engine is not None:
                    try:
                        if not getattr(sim_engine, "_fights_total", 0):
                            sim_engine._fights_total = int(res.get("fights", 0))
                    except Exception:
                        pass
                # Drama layer: turn tonight's incidents into consequences --
                # rivalry heat, headlines, DoPS fines, room morale, press
                # hooks. Single consumer per game (fed only by rolled
                # incidents; GameSim did its own live), so neither engine
                # can double-fire. Skipped for preseason exhibitions.
                try:
                    _ut = getattr(self, "user_team", None)
                    _ni.apply_incident_consequences(
                        self, home_team, away_team,
                        res.get("incidents"), res.get("incident_details"),
                        bool(res.get("brawl")), (home_score, away_score),
                        game_date, _ut, rivalries)
                    # Item 4 (additive): DoPS review for live borderline hits.
                    # Full-detail GameSim games record their hits on the sim
                    # engine (roll_incidents=False above), so the rolled path
                    # never fires on this branch -- each live hit gets the
                    # same suspension-or-fine decision exactly once. Quick-sim
                    # engines never stash hits, so this is a no-op there.
                    _ni.apply_live_dops_reviews(
                        self, sim_engine, home_team, away_team,
                        (home_score, away_score), game_date, _ut, rivalries)
                except Exception:
                    pass
                if deliver_headlines and res.get("stories"):
                    try:
                        from headlines import deliver_spec as _deliver_spec
                        for _st in res["stories"]:
                            _deliver_spec(self, {
                                "kind": "game_story",
                                "story_kind": _st.get("kind", ""),
                                "text": _st.get("text", ""),
                                "home": _st.get("home", ""),
                                "away": _st.get("away", ""),
                                "involved": _st.get("involved", ()),
                                # Clutch tag epithet (additive): headlines.py
                                # colors the story for a tagged subject.
                                "epithet": _st.get("epithet", ""),
                            })
                    except Exception:
                        pass
                elif res.get("stories"):
                    # Narrative ignition (Muck 2026-10-02): AI-game stories
                    # don't vanish anymore -- they accumulate for the end-of-day
                    # "Around the League" digest.
                    try:
                        import league_digest as _ld
                        _ld.collect_game_stories(self, res["stories"])
                    except Exception:
                        pass
                return res
            except Exception:
                return {}

    def _process_career_daily(self):
            """FM-style daily career processing: board, happiness, youth, press."""
            try:
                career = self.career
                team = self.user_team
                if team is None:
                    return
                # 1. First-run: set board expectation from squad strength
                if not getattr(career, "career_start_date", None):
                    career.career_start_date = self.current_date.isoformat()
                    strength = self._career_team_strength(team)
                    career.board.auto_expectation(strength)
                    ages = [getattr(p, "age", 27) or 27
                            for p in (getattr(team, "roster", []) or [])]
                    avg_age = sum(ages) / len(ages) if ages else 27.0
                    career.board.on_hired(strength, avg_age,
                                          self.current_date.isoformat())
                    exp = manager_career.EXPECTATIONS[career.board.expectation]
                    from game_classes import EmailMessage
                    self.send_email_to_user(EmailMessage(
                        sender="Board of Directors", sender_type="Owner",
                        subject="Season expectations",
                        content=(f"Welcome to {team.team_name}.\n\n"
                                 f"The board's expectation this season is: {exp['label']}.\n"
                                 f"{exp['description']}\n\n"
                                 f"Your owner: {career.board.owner.label}.\n"
                                 f"Board confidence starts at {career.board.confidence}/100. "
                                 f"The board reviews progress monthly — it judges trends, "
                                 f"not single games. If things go badly, you can request "
                                 f"a meeting with the owner from the Manager Hub to ask "
                                 f"for patience. In your first season the board won't "
                                 f"pull the plug over a bumpy year -- barring a genuine "
                                 f"disaster, confidence floors at 1 and you'll get an "
                                 f"owner meeting instead. From year two on, if "
                                 f"confidence hits zero, you're gone."),
                        date_sent=self.current_date, category="General",
                        is_important=True))
                # 2. Weekly update: happiness, concerns, training effects
                if self.current_date.weekday() == 0:
                    self._career_weekly_update()
                # 3. Monthly board review (first Monday of month)
                if self.current_date.weekday() == 0 and self.current_date.day <= 7:
                    self._career_board_review()
                # 5. Matchday: scout report + pre-match presser
                self._career_matchday_pre()
            except Exception as e:
                print(f"Career daily error (non-fatal): {e}")

    def _process_player_development(self):
            """Process weekly player development for all teams"""
            if not hasattr(self, 'development_engine') or self.development_engine is None:
                return

            try:
                development_events = []
                # Per-tick cache: (player, drill) -> coaching multiplier, so
                # the breakdown is priced once per player per drill.
                _coach_cache = {}

                for team in self.league.teams:
                    for roster_type, roster_list in (('roster', team.roster),
                                                       ('ahl', team.ahl_roster),
                                                       ('prospects', team.prospects)):
                        for player in roster_list:
                            try:
                                # Skip if player has no potential info
                                if not hasattr(player, 'potential_info') or player.potential_info is None:
                                    continue

                                # Get player's development stage
                                stage = self.development_engine.get_development_stage(player)

                                # Calculate base development rate
                                base_rate = self.development_engine.calculate_base_development_rate(player)

                                # Apply training modifier based on roster type
                                training_modifier = 1.0
                                if roster_type == 'ahl':
                                    training_modifier = 1.15  # AHL provides more development time
                                elif roster_type == 'prospects':
                                    training_modifier = 1.25  # Prospects focus on development
                                elif roster_type == 'roster':
                                    training_modifier = 0.9  # NHL focuses on performance, less development

                                # Calculate weekly development (scaled from annual to weekly)
                                weekly_rate = (base_rate * training_modifier) / 52.0

                                # FM training schedule: user's weekly schedule modifies development
                                try:
                                    if team == self.user_team:
                                        weekly_rate *= self.career.training.weekly_effects()["development_mult"]
                                except Exception:
                                    pass

                                # Apply development to attributes based on player age and stage.
                                # The age gates slide with the player's development arc
                                # (late bloomers develop longer, early peaks decline
                                # sooner) -- the gates themselves are untouched.
                                try:
                                    from game_classes import arc_peak_shift as _arc_shift
                                    _shift = _arc_shift(player)
                                except Exception:
                                    _shift = 0
                                if player.age <= 27 + _shift:  # Only develop younger players
                                    import random

                                    # Determine which attributes can develop
                                    developable_attrs = self._get_developable_attributes(player)
                                    # Coaching parity: this club's staff shapes the
                                    # weekly tick exactly the way they shape a
                                    # practice session (same model, all 32 teams).
                                    # D8: bench quality splits by roster -- AHL
                                    # skaters learn from the AHL bench, prospects
                                    # from their junior/college/Euro program.
                                    _asg8 = ("nhl" if roster_type == "roster"
                                             else ("ahl" if roster_type == "ahl"
                                                   else "overseas"))
                                    coach_mults = self._weekly_coaching_mults(
                                        team, player, developable_attrs,
                                        _coach_cache, assignment=_asg8)

                                    for attr in developable_attrs:
                                        if hasattr(player, attr):
                                            current_val = getattr(player, attr)
                                            # Potential and attributes are on the native 1-100 scale.
                                            # (potential_info fields are generated 60-100).
                                            try:
                                                ceiling_raw = player.potential_info.get_potential_for_attribute(attr)
                                            except Exception:
                                                ceiling_raw = 75
                                            max_val = ceiling_raw

                                            # Check if there's room to grow
                                            if current_val < max_val and current_val < 100:
                                                # Small chance of improvement each week
                                                improvement_chance = (weekly_rate * 0.15
                                                                      * coach_mults.get(attr, 1.0))

                                                if random.random() < improvement_chance:
                                                    new_val = min(current_val + 1, max_val, 100)
                                                    setattr(player, attr, new_val)

                                                    # Track significant improvements
                                                    if team == self.user_team and new_val >= 75:
                                                        development_events.append({
                                                            'player': player,
                                                            'attribute': attr,
                                                            'old_value': current_val,
                                                            'new_value': new_val
                                                        })

                                # Age-related decline for older players (arc slides the gate)
                                elif player.age >= 33 + _shift:
                                    import random
                                    decline_chance = (player.age - 32) * 0.02  # 2% per year over 32

                                    if random.random() < decline_chance:
                                        physical_attrs = ['skating', 'strength', 'speed']
                                        decline_attr = random.choice([a for a in physical_attrs if hasattr(player, a)])
                                        if decline_attr:
                                            current_val = getattr(player, decline_attr)
                                            if current_val > 5:  # Don't go below 5
                                                setattr(player, decline_attr, current_val - 1)

                            except Exception as e:
                                continue  # Skip player on error

                # Notify user of significant developments on their team
                if development_events:
                    for event in development_events[:3]:  # Limit to 3 notifications per week
                        player = event['player']
                        attr_display = event['attribute'].replace('_', ' ').title()
                        story = f"DEVELOPMENT: {player.full_name}'s {attr_display} has improved to {event['new_value']}!"
                        self.news_log.append({'date': self.current_date, 'story': story})

            except Exception as e:
                print(f"Error processing player development: {e}")

    def _process_room_politics_weekly(self):
            """Weekly room-politics tick (module 03, Wave 2): practice plans are
            executed, captaincy crises surface, demanding coaches' shelf life
            ticks. User and AI teams run the same engine; only the choices
            differ (the GM's vs automated)."""
            try:
                import dressing_room as _dr
                league = getattr(self, "league", None)
                teams = list(getattr(league, "teams", []) or [])
                date_str = ""
                try:
                    date_str = self.current_date.isoformat()
                except Exception:
                    pass
                for team in teams:
                    try:
                        # Multiplayer parity: a club run by a remote human gets
                        # the user's tick (their stored plan runs; crises are
                        # flagged for the human's decision), never the AI tick.
                        _human = _dr.is_user_team(
                            team, getattr(self, "game_manager", self))
                        if not _human:
                            try:
                                import game_classes as _gc
                                _human = bool(_gc.is_human_managed(team))
                            except Exception:
                                pass
                        if _human:
                            _urt = _dr.user_room_politics_tick(
                                team, date_str=date_str, league=league)
                            # Coach's leash, surfaced: the human GM decides --
                            # never an auto-firing. One alert per hot-seat
                            # episode; the flag clears (and re-arms) in
                            # coach_hot_seat_check when the seat cools.
                            try:
                                _hs = (_urt or {}).get("coach_hot_seat")
                                if isinstance(_hs, dict) and _hs.get("coach_name"):
                                    _drf = _dr.ensure_dressing_room_fields(team)
                                    if not _drf.get("coach_hot_seat_surfaced"):
                                        _drf["coach_hot_seat_surfaced"] = True
                                        self._alert_coach_hot_seat(
                                            team, _hs, date_str)
                            except Exception:
                                pass
                        else:
                            _dr.ai_room_politics_tick(
                                team, date_str=date_str, league=league, app=self)
                    except Exception:
                        continue
            except Exception:
                pass

    def _process_single_game_result(self, game_date, home_team, away_team, winner, loser, scores, events, notable_events, sim_engine,
                                          stats_from_events=True, preseason=False):
            """Process a single game result - used for user team games.

            stats_from_events: when True (default), player season stats are
                derived from notable_events. Pass False when the sim engine
                (e.g. GameSim) already updated player.stats itself, to avoid
                double counting.
            preseason: exhibition -- the result is stored for viewing but
                never touches the standings.
            """
            # Update league standings (safely) -- never for preseason.
            home_score, away_score = scores

            if not preseason:
                # Ensure teams exist in standings
                if home_team.team_name not in self.league.standings:
                    self.league.standings[home_team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
                if away_team.team_name not in self.league.standings:
                    self.league.standings[away_team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}

            # Detect if game went to overtime/shootout (for OTL point)
            # NHL rule: loser in OT/SO gets 1 point (OTL)
            went_to_ot = len([e for e in notable_events if e.get('period', 0) > 3]) > 0

            # Grudge-week report card: marketed hard and fizzled gets called out.
            try:
                _ufights = 0
                if sim_engine is not None:
                    _ufights = int(getattr(sim_engine, "_fights_total", 0) or 0)
                self._grudge_week_grade(game_date, home_team, away_team,
                                        home_score, away_score, went_to_ot,
                                        fights=_ufights)
            except Exception:
                pass

            # Winner gets 2 points (regular season only -- preseason
            # exhibitions never touch the table).
            if not preseason:
                self.league.standings[winner.team_name]['W'] += 1
                self.league.standings[winner.team_name]['Points'] += 2

                # Loser: OTL point if game went to OT/SO, else regulation loss
                if went_to_ot:
                    self.league.standings[loser.team_name]['OTL'] += 1
                    self.league.standings[loser.team_name]['Points'] += 1
                else:
                    self.league.standings[loser.team_name]['L'] += 1

                # Sync the Team objects too (the dashboard, standings window,
                # and season-review builder read team.wins/losses/ot_losses/
                # games_played/goals_for/goals_against -- not league.standings).
                # The canonical Team.update_record() keeps streaks consistent.
                try:
                    _wl, _ll = (home_team, away_team) if winner == home_team \
                        else (away_team, home_team)
                    _wl.update_record("WIN")
                    _ll.update_record("LOSS", overtime=went_to_ot)
                    home_team.goals_for = getattr(home_team, 'goals_for', 0) + home_score
                    home_team.goals_against = getattr(home_team, 'goals_against', 0) + away_score
                    away_team.goals_for = getattr(away_team, 'goals_for', 0) + away_score
                    away_team.goals_against = getattr(away_team, 'goals_against', 0) + home_score
                except Exception:
                    pass

            # Store game result for later viewing
            player_ratings = self._calculate_player_ratings(getattr(sim_engine, 'stats', {}), events)
            game_stats = getattr(sim_engine, 'game_stats', None) or {}
            game_result_team_stats = None
            if not game_stats:
                # AdvancedGameSim keeps per-game stats as {team_name: {pid: {...}}};
                # flatten to the {pid: {...}} shape the box score expects.
                by_id = {}
                for _tm in (home_team, away_team):
                    for _p in getattr(_tm, 'roster', []) or []:
                        by_id[_p.id] = _p
                for _tn, _pmap in (getattr(sim_engine, 'stats', {}) or {}).items():
                    if not isinstance(_pmap, dict):
                        continue
                    for _pid, _st in _pmap.items():
                        if not isinstance(_st, dict) or _pid not in by_id:
                            continue
                        # Defensive record: the shared attribute-driven roll --
                        # the same single decision GameSim applies live, so a
                        # quick-simmed game leaves the same statistical trail.
                        # Rolled ONCE here; the values below feed both the
                        # per-game box score and (below, under stats_from_events)
                        # the season totals, so the two always agree. Goalies
                        # are skipped like GameSim's end-of-game roll.
                        try:
                            from game_classes import roll_defensive_game_stats as _rdg
                            _pos = getattr(getattr(by_id[_pid], "primary_position",
                                                    None), "name", "")
                            if _pos == "GOALIE":
                                _dh, _dt, _db = 0, 0, 0
                            else:
                                _dh, _dt, _db = _rdg(by_id[_pid])
                        except Exception:
                            _dh, _dt, _db = 0, 0, 0
                        game_stats[_pid] = {
                            'player': by_id[_pid],
                            'g': _st.get('goals', 0), 'a': _st.get('assists', 0),
                            'shots_on_goal': _st.get('shots', 0),
                            'saves': _st.get('saves', 0),
                            'shots_against': 0,  # derived in the box score
                            'goals_against': 0,
                            'hits': _dh,
                            'blocked_shots': _db,
                            'takeaways': _dt,
                            'giveaways': 0,
                            'faceoffs_won': 0,   # filled by the faceoff roll below
                            'faceoffs_lost': 0,
                            '_def_roll': (_dh, _dt, _db),
                        }
                # Faceoffs: the shared per-game model (GameSim resolves them
                # live; the quick path was leaving zeros). Writes per-player
                # won/lost into the game_stats built above.
                try:
                    from game_classes import roll_faceoff_game_stats as _rfo
                    _fo_home, _fo_away = _rfo(home_team.roster, away_team.roster)
                    for _fo_map in (_fo_home, _fo_away):
                        for _fpid, (_fw, _fl) in _fo_map.items():
                            if _fpid in game_stats:
                                game_stats[_fpid]['faceoffs_won'] = _fw
                                game_stats[_fpid]['faceoffs_lost'] = _fl
                except Exception:
                    pass
                # Team aggregates for the box-score team-stats section
                # (AdvGS has no team_stats of its own).
                try:
                    _team_agg = {}
                    for _pid, _gs in game_stats.items():
                        _pl = _gs.get('player')
                        _tnm = getattr(_pl, 'team_name', None)
                        if not _tnm:
                            continue
                        _ag = _team_agg.setdefault(_tnm, {
                            'hits': 0, 'blocked_shots': 0, 'takeaways': 0,
                            'giveaways': 0, 'faceoffs_won': 0, 'shots': 0,
                        })
                        _ag['hits'] += _gs.get('hits', 0)
                        _ag['blocked_shots'] += _gs.get('blocked_shots', 0)
                        _ag['takeaways'] += _gs.get('takeaways', 0)
                        _ag['giveaways'] += _gs.get('giveaways', 0)
                        _ag['faceoffs_won'] += _gs.get('faceoffs_won', 0)
                        _ag['shots'] += _gs.get('shots_on_goal', 0)
                    if _team_agg:
                        game_result_team_stats = dict(_team_agg)
                    else:
                        game_result_team_stats = None
                except Exception:
                    game_result_team_stats = None
                # GAP-001 (parity): the AdvGS records chance grades per game in
                # sim.stats but never flushed them to season stats. Mirror the
                # GameSim finalization flush so both engines feed the analytics
                # integration's per-player aggregates. This block only runs for
                # the AdvGS shape (GameSim has game_stats and skips it); the
                # stats_from_events guard keeps preseason exhibitions and the
                # GameSim path (already flushed in its finalization) from
                # double-counting.
                if stats_from_events:
                    try:
                        for _tn, _pmap in (getattr(sim_engine, 'stats', {}) or {}).items():
                            if not isinstance(_pmap, dict):
                                continue
                            for _pid, _st in _pmap.items():
                                if not isinstance(_st, dict) or _pid not in by_id:
                                    continue
                                _pl = by_id[_pid]
                                try:
                                    if getattr(getattr(_pl, 'primary_position', None), 'name', '') == 'GOALIE':
                                        continue
                                    for _g in ('a', 'b', 'c'):
                                        _sk = f'grade_{_g}_shots'
                                        _gk = f'grade_{_g}_goals'
                                        setattr(_pl.stats, _sk,
                                                (getattr(_pl.stats, _sk, 0) or 0) + (_st.get(_sk, 0) or 0))
                                        setattr(_pl.stats, _gk,
                                                (getattr(_pl.stats, _gk, 0) or 0) + (_st.get(_gk, 0) or 0))
                                except Exception:
                                    pass
                    except Exception:
                        pass
            game_result = {
                'date': game_date,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'winner': winner,
                'events': events,
                'notable_events': notable_events,
                'player_ratings': player_ratings,
                'event_log': getattr(sim_engine, 'event_log', []),  # Add event log for game viewer
                'game_stats': game_stats,  # Per-player game stats (g/a/shots/...), normalized
                # Per-team game stats: AdvGS has none of its own, so use the
                # aggregates built from the flattened per-player stats above.
                'team_stats': (game_result_team_stats
                               if game_result_team_stats
                               else getattr(sim_engine, 'team_stats', {})),
                'overtime': away_score != home_score and len([e for e in notable_events if e.get('period', 0) > 3]) > 0,
                'shootout': len([e for e in notable_events if e.get('period', 0) == 5]) > 0,
                # Post-game Lines tab: the combos actually dressed (Muck 2026-10-02).
                'lines': self._snapshot_game_lines(home_team, away_team),
            }
            # NEW-A6: per-game TOI + fatigue snapshots from the sim that ran
            # the game (integration read; missing data stays missing).
            try:
                _toi, _fat = self._snapshot_game_toi_fatigue(
                    sim_engine, home_team, away_team)
                game_result['player_toi'] = _toi
                game_result['player_fatigue'] = _fat
            except Exception:
                pass

            self._record_game_result(game_result)

            # Three stars of the game (NHL media criteria) -- stamped on the
            # result and recorded onto the players. Preseason names no stars.
            try:
                import stars as _stars_mod
                _stars_mod.record_game_stars(game_result, home_team, away_team,
                                            preseason=preseason,
                                            game_date=game_date)
            except Exception as _se:
                print(f"Three-stars error (non-fatal): {_se}")

            # Generate media events for the game (if media system enabled)
            if hasattr(self, 'media_system') and self.media_system:
                self.media_system.process_game_result(game_result)

            # Update player stats from game events
            # Records: goals, assists, shots, saves, PIM
            # (Skipped when the sim engine already updated player.stats itself.)
            if stats_from_events:
                # Build roster lookups for assist selection
                home_roster = {p.id: p for p in home_team.roster}
                away_roster = {p.id: p for p in away_team.roster}

                # Identify starting goalies for save tracking
                def get_starting_goalie(team):
                    goalies = [p for p in team.roster
                              if getattr(p, 'primary_position', None) and p.primary_position.name == "GOALIE"]
                    return goalies[0] if goalies else None

                home_goalie = get_starting_goalie(home_team)
                away_goalie = get_starting_goalie(away_team)

                for event in notable_events:
                    event_type = event.get('event')
                    player = event.get('player')
                    team_name = event.get('team')

                    if not player:
                        continue

                    if event_type == 'Goal':
                        # Scorer gets goal + shot
                        player.stats.goals += 1
                        player.stats.shots += 1

                        # Assists: up to 2 teammates, selected by the SHARED
                        # attribute-weighted decision (mesh_system.assist_weight)
                        # -- the same call both engines make. BUG-023: the old
                        # filter checked .name != "G" but the enum member name is
                        # "GOALIE" ("G" is the value), so goalies were never
                        # excluded; and uniform random.sample bypassed the entire
                        # multi-attribute assist rework for user-team games
                        # (backup goalie at 8 assists in October S1).
                        team_roster = home_roster if team_name == home_team.team_name else away_roster
                        potential_assisters = [
                            p for p in team_roster.values()
                            if p.id != player.id
                            and getattr(p, 'primary_position', None)
                            and p.primary_position.name != "GOALIE"
                        ]
                        # P2 (scoring calibration 2026-09-29): trust the sim's
                        # own attribute-weighted assist ledger when the Goal
                        # event carries one -- this is the same single source of
                        # truth the box score uses, so the season log agrees with
                        # it and star playmakers are no longer diluted by a
                        # uniform re-roll. Legacy events without an assist ledger
                        # fall back to the BUG-023 attribute-weighted re-roll
                        # (never uniform, never goalies) at the P1 rate so the
                        # user's team credits assists at league intensity.
                        event_assists = event.get('assists', None)
                        if event_assists is not None:
                            for assister in event_assists:
                                pos_name = getattr(getattr(assister, 'primary_position', None), 'name', '')
                                if (assister is not None
                                        and getattr(assister, 'id', None) != player.id
                                        and pos_name not in ("GOALIE", "G")
                                        and getattr(assister, 'stats', None) is not None):
                                    assister.stats.assists += 1
                        else:
                            num_assists = random.choices([2, 1, 0], weights=[0.68, 0.30, 0.02])[0]
                            if potential_assisters and num_assists > 0:
                                try:
                                    from mesh_system import assist_weight as _aw_ev
                                    _tm_ev = home_team if team_name == home_team.team_name else away_team
                                    _ws = [max(0.05, _aw_ev(p, player, _tm_ev))
                                           for p in potential_assisters]
                                    assisters = []
                                    _pool = list(potential_assisters)
                                    _wp = list(_ws)
                                    for _ in range(min(num_assists, len(_pool))):
                                        _pick = random.choices(_pool, weights=_wp, k=1)[0]
                                        _i = _pool.index(_pick)
                                        assisters.append(_pick)
                                        del _pool[_i]
                                        del _wp[_i]
                                except Exception:
                                    assisters = random.sample(potential_assisters, min(num_assists, len(potential_assisters)))
                                for assister in assisters:
                                    assister.stats.assists += 1

                        # Opposing goalie: shot against (goal counts as shot faced, not a save)
                        opp_goalie = away_goalie if team_name == home_team.team_name else home_goalie
                        if opp_goalie:
                            opp_goalie.stats.shots_against += 1
                            opp_goalie.stats.goals_against += 1

                    elif event_type == 'Shootout Goal':
                        # NHL rule: shootout goals don't count in player stats
                        pass

                    elif event_type == 'Shot':
                        # Shooter gets a shot on goal
                        player.stats.shots += 1
                        # Opposing goalie gets a save + shot against
                        opp_goalie = away_goalie if team_name == home_team.team_name else home_goalie
                        if opp_goalie:
                            opp_goalie.stats.saves += 1
                            opp_goalie.stats.shots_against += 1

                    elif event_type == 'Penalty':
                        # Standard minor penalty: 2 PIM
                        player.stats.penalties += 1
                        player.stats.penalties_in_minutes += 2

            # Games played: all roster players get credit -- but only when stats
            # are derived from events (quick sim). GameSim already credited GP
            # to dressed players itself; running this too would double-count.
            if stats_from_events:
                # (In real NHL only dressed players get GP, but sim doesn't track scratches)
                for team in [home_team, away_team]:
                    for player in team.roster:
                        player.stats.games_played += 1
                # Goalie decisions: the events path credits goals/saves above
                # but not W/L/SO. GameSim and the lightweight path credit them,
                # so do it here too -- monthly awards and the record book must
                # see the same numbers on every sim path.
                if not preseason:
                    for _team, _opp_score, _won in (
                            (home_team, away_score, winner is home_team),
                            (away_team, home_score, winner is away_team)):
                        _g = get_starting_goalie(_team)
                        if _g is None:
                            continue
                        if _won:
                            _g.stats.wins += 1
                        else:
                            _g.stats.losses += 1
                        if _opp_score == 0:
                            _g.stats.shutouts += 1
                # Defensive record: the per-game roll already happened once in
                # the flattening above (stored as _def_roll on each game_stats
                # entry) -- reuse those exact values so the season totals agree
                # with the box score. Fall back to a fresh shared roll only if
                # the flattening didn't run (shouldn't happen on this path).
                try:
                    from game_classes import roll_defensive_game_stats as _rdg
                    for team in [home_team, away_team]:
                        for player in team.roster:
                            try:
                                if getattr(getattr(player, "primary_position",
                                                   None), "name", "") == "GOALIE":
                                    continue
                                _gs = game_stats.get(getattr(player, "id", None), {})
                                _roll = _gs.get("_def_roll") if isinstance(_gs, dict) else None
                                if _roll is None:
                                    _roll = _rdg(player)
                                _h, _t, _b = _roll
                                player.stats.hits += _h
                                player.stats.takeaways += _t
                                player.stats.blocked_shots += _b
                            except Exception:
                                continue
                except Exception:
                    pass
                # Goalie saves: quick-sim notable_events carry goals only
                # ('Shot' save events never make the notable list), so derive
                # saves from the engine's full event log, whose SHOT entries
                # carry a result. Shootout attempts never log SHOT entries,
                # so no shootout contamination by construction.
                try:
                    for _le in getattr(sim_engine, 'event_log', []) or []:
                        if not isinstance(_le, dict) or _le.get('type') != 'SHOT':
                            continue
                        _det = _le.get('details') or {}
                        if _det.get('result') != 'SAVE':
                            continue
                        _shooter = home_roster.get(_det.get('shooter_id'))
                        _opp = away_goalie if _shooter is not None else home_goalie
                        if _shooter is None:
                            _shooter = away_roster.get(_det.get('shooter_id'))
                            _opp = home_goalie
                        if _shooter is None or _opp is None:
                            continue
                        _opp.stats.saves += 1
                        _opp.stats.shots_against += 1
                except Exception:
                    pass

            # Strip the internal _def_roll bookkeeping (used above to sync
            # season totals with the per-game box score) before storing.
            try:
                for _gs in game_stats.values():
                    if isinstance(_gs, dict):
                        _gs.pop("_def_roll", None)
            except Exception:
                pass

            # Update news log for user team games
            if self.user_team in (home_team, away_team):
                opponent = away_team if self.user_team == home_team else home_team
                result = "won" if (winner == self.user_team) else "lost"
                # Format score from user team perspective (user score first)
                if self.user_team == home_team:
                    user_score = home_score
                    opp_score = away_score
                else:
                    user_score = away_score
                    opp_score = home_score

                self.add_news(f"Your team {result} {user_score}-{opp_score} against {opponent.team_name}.")

                # Generate post-game emails for user team games
                self._generate_post_game_emails(game_result, opponent, result, user_score, opp_score, notable_events)

    def _process_training_programs(self):
            """Run one weekly session for each active Development-Center program.

            Programs live on game_manager.training_programs (persisted in saves)
            and are keyed to the GAME date, not the wall clock. The module-level
            ACTIVE_TRAINING_PROGRAMS registry is kept as a mirror for the
            Development Center window.
            """
            try:
                from enhanced_practice_system import (
                    PracticeEngine, PracticeType, ACTIVE_TRAINING_PROGRAMS,
                    FOCUS_TO_PRACTICE_TYPE, INTENSITY_LABEL_TO_ENUM)
                from datetime import date
            except Exception:
                return
            gm = getattr(self, 'game_manager', None)
            user_team = getattr(self, 'user_team', None) or (getattr(gm, 'user_team', None) if gm else None)
            if gm is None or not user_team:
                return
            league = (getattr(self, 'league', None)
                      or (getattr(gm, 'league', None) if gm else None))
            if not hasattr(gm, 'training_programs') or gm.training_programs is None:
                gm.training_programs = {}
            game_today = getattr(self, 'current_date', None) or date.today()

            # One-time adoption: programs assigned through the window registry
            # get stamped with the current game date so they run their full term.
            for pid, prog in list(ACTIVE_TRAINING_PROGRAMS.items()):
                if pid not in gm.training_programs:
                    adopted = dict(prog)
                    adopted['assigned'] = game_today
                    gm.training_programs[pid] = adopted

            engine = PracticeEngine()
            # Every club's programs run, not just the host's: a client GM's
            # training assignment lives in the same registry. (AI clubs never
            # write programs, so SP behavior is unchanged.)
            players = {}
            _teams_by_name = {}
            for _t in (getattr(league, 'teams', None) or []):
                try:
                    _teams_by_name[getattr(_t, 'team_name', '')] = _t
                    for roster_list in (_t.roster, _t.ahl_roster,
                                        _t.prospects):
                        for pl in roster_list or []:
                            players[getattr(pl, 'id', None)] = (pl, _t)
                except Exception:
                    continue
            expired = []
            for pid, prog in list(gm.training_programs.items()):
                assigned = prog.get('assigned')
                if isinstance(assigned, str):
                    try:
                        assigned = date.fromisoformat(assigned)
                    except Exception:
                        assigned = None
                if assigned is None or (game_today - assigned).days >= 30:
                    expired.append(pid)
                    continue
                _hit = players.get(pid)
                if not _hit:
                    continue
                player, _pteam = _hit
                # The drill is run by the player's own coaching staff, not
                # the host's -- fall back to the host club only for legacy
                # programs stamped without a team.
                _coach_team = (_teams_by_name.get(prog.get('team'))
                               or _pteam or user_team)
                ptype = FOCUS_TO_PRACTICE_TYPE.get(prog.get('focus'), PracticeType.SKATING)
                intensity = INTENSITY_LABEL_TO_ENUM.get(prog.get('intensity'))
                if intensity is None:
                    continue
                try:
                    can, _ = engine.can_practice(player, ptype, intensity)
                    if can:
                        # Team context: the real coaching staff runs the drill
                        # (who teaches it, archetype affinity, attitude, fit,
                        # system) instead of a flat trainer number.
                        engine.execute_practice(player, ptype, intensity, 60, 12,
                                                team=_coach_team)
                except Exception:
                    continue
            for pid in expired:
                gm.training_programs.pop(pid, None)
                ACTIVE_TRAINING_PROGRAMS.pop(pid, None)
            # Keep the window registry in sync for display purposes
            for pid, prog in gm.training_programs.items():
                ACTIVE_TRAINING_PROGRAMS[pid] = prog

    def _rebuild_result_index(self):
            """Full rebuild of the derived indexes from the current list."""
            by_date = {}
            by_matchup = {}
            for r in self.game_results:
                key = self._result_date_key(r.get('date'))
                if key is None:
                    continue
                by_date.setdefault(key, []).append(r)
                by_matchup[(key, id(r.get('home_team')),
                            id(r.get('away_team')))] = r
            self._results_by_date = by_date
            self._results_by_matchup = by_matchup
            self._results_index_src = self.game_results

    def _run_phase2_maintenance(self):
            """Run Phase 2 maintenance operations - optimized to reduce frequency"""
            try:
                # Memory optimization (every 30 days instead of 10 to reduce impact)
                if self.memory_optimizer and self.current_date.day % 30 == 0:
                    self.memory_optimizer.optimize_memory()

                # Database optimization (every 2 weeks instead of weekly)
                if self.db_manager and self.current_date.weekday() == 0 and self.current_date.day <= 7:  # First Monday of month
                    self.db_manager.optimize_performance()

                # Lazy loading cleanup (every 14 days instead of 5)
                if self.lazy_manager and self.current_date.day % 14 == 0:
                    self.lazy_manager.optimize_memory_usage()

            except Exception as e:
                print(f"Phase 2 maintenance error: {e}")

    def _simulate_game_with_pbp_visual(self, home_team, away_team,
                                           outdoor=None, coach_instruction=None):
            """Run the modern visual play-by-play window modally for a user game.

            Opens the live PBP viewer (rink + player bubbles driven by real sim
            events) and blocks the daily-sim loop until the game is watched to
            the final whistle and the window is closed. Returns the standard
            6-tuple (winner, loser, scores, events, notable_events, sim_engine)
            so the result processes exactly like any other sim.

            D1: coach_instruction is the user's explicit game-day call,
            forwarded to open_pbp_window (applied via the standard channel).
            """
            from pbp_visual_sim import open_pbp_window

            # Deployment directive: same direction-cache fill as the batch path.
            try:
                from deployment_policy import set_team_direction as _set_tdir
                import trade_storylines as _ts
                _set_tdir({home_team.team_name: _ts.stance(self, home_team.team_name),
                           away_team.team_name: _ts.stance(self, away_team.team_name)})
            except Exception:
                pass

            # Adaptive Rivals: AI scouts the user and adjusts tactics for this game.
            # Reverts to base identity afterwards.
            _adapted_team = None
            _adapted_plan = []
            try:
                from adaptive_rivals import adapt_for_opponent
                user = getattr(self, 'user_team', None)
                user_name = user.team_name if user else None
                ai_team = None
                if home_team.team_name == user_name and away_team.team_name != user_name:
                    ai_team = away_team
                elif away_team.team_name == user_name and home_team.team_name != user_name:
                    ai_team = home_team
                if ai_team is not None and user is not None:
                    _adapted_plan = adapt_for_opponent(
                        ai_team, user, getattr(self, 'game_results', []))
                    _adapted_team = ai_team
            except Exception:
                pass

            holder = {}
            win_ref = {}

            def _on_done(sim):
                holder['sim'] = sim
                # Capture the played event stream (carries period info for OT detection)
                try:
                    holder['pbp_events'] = list(win_ref['win'].events)
                except Exception:
                    holder['pbp_events'] = []
                # Export shot chart to the career store (replayable evidence)
                try:
                    from shot_charts import ShotChartStore
                    viz = win_ref.get('win')
                    shotmap = getattr(viz, '_shotmap', []) if viz else []
                    if shotmap:
                        if not getattr(self, 'shot_chart_store', None):
                            self.shot_chart_store = ShotChartStore()
                        # Build game dict
                        gid = f"{home_team.team_name}_{away_team.team_name}_{self.current_date.isoformat()}"
                        game_dict = {
                            "game_id": gid,
                            "date": self.current_date.isoformat(),
                            "home": home_team.team_name,
                            "away": away_team.team_name,
                            "shots": shotmap,  # list of dicts from _record_shotmap
                        }
                        self.shot_chart_store.add(game_dict)
                except Exception:
                    pass  # shot chart export is non-fatal
                # Only allow closing once the final whistle has played
                try:
                    win_ref['win'].protocol("WM_DELETE_WINDOW", win_ref['win'].destroy)
                except Exception:
                    pass

            win_ref['win'] = None

            # Muck 2026-10-02: hide the day-sim loading toast before the
            # visualizer opens -- the visualizer IS the feedback while
            # watching; the loading bar should only show for quick-sim.
            # Never raises; overlay is re-shown by the day loop if needed.
            try:
                self._update_day_sim_overlay(False)
            except Exception:
                pass

            win = open_pbp_window(self, home_team, away_team, on_complete=_on_done,
                                  rivalries=getattr(getattr(self, "league", None),
                                                    "rivalries", []),
                                  user_team=getattr(self, "user_team", None),
                                  outdoor=outdoor,
                                  coach_instruction=coach_instruction)
            win_ref['win'] = win
            # Prevent closing before the sim finishes: the result is needed below.
            # (Re-enabled by _on_done when game_end plays.)
            win.protocol("WM_DELETE_WINDOW", lambda: None)
            # Failsafe: if the sim thread dies without emitting game_end, don't
            # trap the user forever. Only release the close-block once the sim
            # thread has actually finished — a healthy game runs ~7+ minutes at
            # 1x, so a flat 3-minute timer would let the user close mid-game and
            # we'd process a partial result as final.
            def _failsafe():
                try:
                    if getattr(win, 'sim_done', False):
                        win.protocol("WM_DELETE_WINDOW", win.destroy)
                        return
                except Exception:
                    pass
                try:
                    win.after(60000, _failsafe)
                except Exception:
                    pass
            win.after(180000, _failsafe)
            # Absolute backstop: never trap the user longer than 12 minutes.
            try:
                win.after(720000,
                          lambda: win.protocol("WM_DELETE_WINDOW", win.destroy))
            except Exception:
                pass

            self.wait_window(win)

            sim = holder.get('sim')
            if sim is None:
                # Closed before the final whistle (backstop) or the sim thread
                # died: the visual sim is partial/unusable. Fall back to a fast
                # silent sim so the recorded result is always a valid full game.
                from simulation import GameSim as _GameSim
                sim = _GameSim(home_team, away_team)
                sim.simulate_game()

            home_score = getattr(sim, 'home_score', 0)
            away_score = getattr(sim, 'away_score', 0)
            scores = (home_score, away_score)
            if home_score > away_score:
                winner, loser = home_team, away_team
            elif away_score > home_score:
                winner, loser = away_team, home_team
            else:
                # Should not happen (OT/shootout always resolves), pick home
                winner, loser = home_team, away_team

            events = getattr(sim, 'game_log', []) or []
            notable_events = list(getattr(sim, 'notable_events', []) or [])

            # Career service time (waiver-exemption input).
            try:
                self._credit_nhl_games_played(home_team, away_team)
            except Exception:
                pass

            # GameSim notable events lack period info; derive OT/shootout from the
            # played PBP stream so standings award the OTL point correctly.
            pbp_events = holder.get('pbp_events', [])
            periods = {e.get('period', 0) for e in pbp_events if isinstance(e, dict)}
            went_to_ot = any(p > 3 for p in periods)
            had_shootout = any(isinstance(e, dict) and e.get('type') == 'shootout_end'
                               for e in pbp_events)
            if went_to_ot:
                notable_events.append({'period': 5 if had_shootout else 4,
                                       'event': 'overtime'})

            # Adaptive Rivals: revert AI tactics + file tactical intel
            if _adapted_team is not None:
                try:
                    from adaptive_rivals import revert_adaptation
                    revert_adaptation(_adapted_team, _adapted_plan)
                except Exception:
                    pass
                try:
                    import tactics as _tx
                    _ts = ((getattr(sim, 'team_stats', None) or {})
                           .get(user_name, {})) or {}
                    _ppg = _ts.get('power_play_goals', 0) or 0
                    _ppo = _ts.get('power_play_opportunities', 0) or 0
                    _pp_pct = (_ppg / _ppo) if _ppo else None
                    _ugoals = (home_score if home_team.team_name == user_name
                               else away_score)
                    _agoals = (away_score if home_team.team_name == user_name
                               else home_score)
                    _tx.record_tactical_intel(_adapted_team, user, _ugoals,
                                              _agoals, _ts.get('shots_on_goal'),
                                              _pp_pct)
                except Exception:
                    pass

            return winner, loser, scores, events, notable_events, sim

    def _simulate_games_batch(self, games):
            """Simulate multiple games efficiently using LIGHTWEIGHT batch processing"""
            # Ultra-fast simulation for non-user games
            batch_results = []
            user_team = getattr(self, 'user_team', None)  # Add user_team reference

            for game in games:
                # Extract game data. A malformed entry is a data problem, not a
                # sim problem -- it is skipped loudly below, never silently.
                try:
                    if isinstance(game, dict):
                        game_date = game.get('date')
                        home_team = game.get('home_team')
                        away_team = game.get('away_team')
                    elif isinstance(game, tuple) and len(game) >= 3:
                        game_date, home_team, away_team = game[:3]
                    else:
                        continue
                except Exception:
                    continue
                if home_team is None or away_team is None:
                    # Corrupt schedule entry: no two clubs, nothing to sim. Loud
                    # skip -- the season-slate audit flags the short clubs.
                    print(f"🛟 SLATE-GUARANTEE: corrupt schedule entry on "
                          f"{game_date} -- missing "
                          f"{'home' if home_team is None else 'away'} team; "
                          f"entry skipped")
                    continue
                # Preseason exhibitions: quick-simmed with no footprint --
                # no stats, no standings, no career GP, no lore.
                is_preseason = isinstance(game, dict) and bool(game.get('preseason'))

                # Pregame presentation is best-effort: a failure here must never
                # take the game down with it, and never `continue` past the sim.
                _outdoor_info = None
                try:
                    # Narrative ledger: grudge-week presentation for non-user games.
                    # One dict lookup per game; only genuine league-wide feuds
                    # (weight >= 60) earn the inbox card. Never blocks the sim.
                    # (Skipped for preseason -- exhibitions build no lore.)
                    if not is_preseason:
                        try:
                            from narrative_ledger import (get_ledger, interpret,
                                                          incident_short)
                            from headlines import deliver_spec as _deliver_spec
                            _led = get_ledger(self)
                            _cand = _led.callback_candidate(home_team.team_name,
                                                            away_team.team_name)
                            if _cand is not None and _cand.get("weight", 0) >= 60:
                                _facts = _cand.get("facts") or {}
                                _home = home_team.team_name
                                _spec = {
                                    "kind": "grudge_callback",
                                    "home": _home,
                                    "away": away_team.team_name,
                                    "short": incident_short(_facts),
                                    "first_meeting": not _cand.get("ref_count"),
                                    "room_line":
                                        interpret(_cand, "room", _home) or "",
                                    "fans_line":
                                        interpret(_cand, "fans", _home) or "",
                                    "media_line":
                                        interpret(_cand, "media", _home) or "",
                                    "league_line":
                                        interpret(_cand, "league", _home) or "",
                                    "involved": (home_team.team_name,
                                                 away_team.team_name),
                                }
                                if _deliver_spec(self, _spec):
                                    _led.mark_referenced(_cand["id"])
                        except Exception:
                            pass

                    # Grudge-week presentation for genuine feuds (sellout talk,
                    # loud-building billing); hollow overhype gets graded post-game.
                    # (Not for preseason.)
                    if not is_preseason:
                        self._grudge_week_market(game_date, home_team, away_team)
                    # Legacy events: outdoor-game billing (~3/season, no spam).
                    _outdoor_info = None
                    try:
                        import outdoor_games as _ogb
                        _outdoor_info = _ogb.outdoor_info_for(game)
                        if _outdoor_info is not None:
                            self._deliver_outdoor_pregame(_outdoor_info, home_team,
                                                         away_team)
                    except Exception:
                        _outdoor_info = None
                    # Pregame ceremony (news only on the lightweight path).
                    try:
                        import immortality as _im4
                        _im4.consume_ceremony(self, home_team, None)
                    except Exception:
                        pass

                except Exception as _pre_e:
                    # Pregame presentation failed -- log it loudly, keep the
                    # game. The sim below still runs; nothing is dropped.
                    import traceback as _tb
                    print(f"Pregame presentation failed (non-fatal, game still "
                          f"simmed): {_pre_e}")
                    _tb.print_exc()

                # SLATE GUARANTEE (2026-10-02, BUG-003/004/005): the sim below
                # NEVER raises and NEVER drops the game. Tier 0 is the normal
                # path (full event sim for 'full' leagues, otherwise the
                # lightweight sim); a failure retries via the lightweight sim;
                # a further failure falls back to a deterministic, loudly-logged
                # last-resort result. The preseason flag flows through every
                # tier -- exhibitions never touch standings or stats.
                winner, loser, scores, went_to_ot, full_sim = \
                    self._sim_game_guaranteed(home_team, away_team, game,
                                               game_date, is_preseason)

                # Post-game processing is best-effort too: even if it fails,
                # the result is still recorded below -- the game is never
                # dropped, and the season slate stays whole.
                try:
                    # Career service time: every rostered player on both clubs
                    # banks one NHL game (waiver-exemption input). Not in
                    # preseason.
                    try:
                        self._credit_nhl_games_played(home_team, away_team,
                                                      preseason=is_preseason)
                    except Exception:
                        pass

                    # Update standings immediately (no batch delay) -- never for
                    # preseason exhibitions.
                    self._update_standings_fast(home_team, away_team, winner, scores, went_to_ot,
                                                preseason=is_preseason)

                    # Legacy events: permanent season memory for outdoor games.
                    if _outdoor_info is not None:
                        try:
                            import outdoor_games as _ogr
                            _ogr.record_outdoor_result(self, _outdoor_info,
                                                       scores[0], scores[1])
                        except Exception:
                            pass

                    # Media engine: post-game coverage (cheap, additive).
                    try:
                        import media_engine
                        _mev = media_engine.cover_game(
                            getattr(self, 'league', None), home_team, away_team,
                            winner, loser, scores, went_to_ot, game_date)
                        media_engine.route_events(self, _mev, game_date)
                    except Exception:
                        pass

                    # Tactics: rooms learn their systems one game at a time.
                    try:
                        import tactics as _tx
                        _tx.tick_tactics_familiarity(home_team)
                        _tx.tick_tactics_familiarity(away_team)
                    except Exception:
                        pass

                except Exception as _post_e:
                    # Post-game processing failed -- log it loudly (BUG-001
                    # diagnostic: full traceback, never just str(e)) but keep
                    # the result anyway. The game is NEVER dropped.
                    import traceback as _tb2
                    print(f"Post-game processing failed (non-fatal, result "
                          f"kept): {_post_e}")
                    _tb2.print_exc()

                # GUARANTEED: a scheduled game always produces a recorded
                # result -- this line is reached for every non-corrupt entry,
                # no matter which sim tier produced the result or whether the
                # presentation/processing above failed.
                batch_results.append((game_date, home_team, away_team, winner,
                                      loser, scores, went_to_ot, full_sim))

            # Store minimal game results for performance
            for game_date, home_team, away_team, winner, loser, scores, went_to_ot, full_sim in batch_results:
                home_score, away_score = scores

                # Lore: deliver any headlines the sim collected (line brawls,
                # ...), including CPU-vs-CPU games.
                if full_sim is not None:
                    try:
                        import headlines
                        headlines.drain_sim_headlines(self, full_sim)
                    except Exception:
                        pass

                # Narrative: quick-simmed games never modeled fights/brawls, so
                # roll them post-game through the shared incident module; record
                # the night's stories for both engines. Headlines only if the
                # user's team was involved (no league-wide spam).
                # (Skipped for preseason -- exhibitions build no lore.)
                _gfights = 0
                if not is_preseason:
                    try:
                        _sim_cls = type(full_sim).__name__ if full_sim is not None else ""
                        _nres = self._narrative_postgame(
                            full_sim, home_team, away_team, scores,
                            went_ot=bool(went_to_ot), shootout=False,
                            roll_incidents=_sim_cls != "GameSim",
                            deliver_headlines=bool(user_team) and
                            user_team in (home_team, away_team),
                            game_date=game_date)
                        _gfights = int((_nres or {}).get("fights", 0) or 0)
                    except Exception:
                        _gfights = 0

                # W3: post-game wear-and-tear -> persistent player condition.
                # GameSim path only (it records real per-player TOI seconds; the
                # lightweight path tracks no TOI). Rest days come from the actual
                # schedule date gaps (back-to-backs included).
                if full_sim is not None and not is_preseason:
                    try:
                        from condition_system import apply_postgame_wear_for_game
                        _toi = dict(getattr(full_sim, 'player_toi_seconds', None) or {})
                        _gsec = float(getattr(full_sim, '_w3_game_seconds', 0.0) or 0.0)
                        _gf = getattr(full_sim, 'goaltender_fatigue', None) or {}
                        try:
                            from game_classes import PlayerPosition as _W3_PP
                            for _team in (home_team, away_team):
                                for _p in getattr(_team, 'roster', []) or []:
                                    if getattr(_p, 'primary_position', None) == _W3_PP.GOALIE \
                                            and _gf.get(getattr(_p, 'id', None), 100) < 100:
                                        _toi[_p.id] = _gsec  # dressed goalie: whole game
                        except Exception:
                            pass
                        _intensity = max(0.8, min(1.4, float(
                            getattr(full_sim, 'physical_intensity', 1.0) or 1.0)))
                        if went_to_ot:
                            _intensity = min(1.5, _intensity + 0.1)
                        apply_postgame_wear_for_game(
                            home_team, away_team, game_date,
                            getattr(self.league, 'schedule', None),
                            toi_by_id=_toi, intensity=_intensity)
                    except Exception:
                        pass

                # Store minimal game result
                game_result = {
                    'date': game_date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score,
                    'winner': winner,
                    'events': [],  # No events for batch games
                    'notable_events': [],  # No notable events
                    'player_ratings': {},  # No player ratings
                    'event_log': [],  # No event log
                    'overtime': went_to_ot,  # Track OT for OTL points
                    'shootout': False,
                    # Post-game Lines tab: the combos actually dressed
                    # (Muck 2026-10-02). Never raises; empty when unknown.
                    'lines': self._snapshot_game_lines(home_team, away_team),
                }
                if full_sim is not None:
                    # Full-detail league: keep the event stream for reports/viewer
                    game_result['event_log'] = getattr(full_sim, 'event_log', []) or []
                    game_result['notable_events'] = getattr(full_sim, 'notable_events', []) or []
                    game_result['events'] = getattr(full_sim, 'game_log', []) or []
                    game_result['game_stats'] = getattr(full_sim, 'game_stats', {}) or {}
                    game_result['team_stats'] = getattr(full_sim, 'team_stats', {}) or {}
                    # NEW-A6: same TOI/fatigue snapshot as the detailed path.
                    try:
                        _toi, _fat = self._snapshot_game_toi_fatigue(
                            full_sim, home_team, away_team)
                        game_result['player_toi'] = _toi
                        game_result['player_fatigue'] = _fat
                    except Exception:
                        pass

                # Add to game results (keeps the date/matchup indexes in sync)
                self._record_game_result(game_result)

                # Three stars of the game (regular season only).
                try:
                    import stars as _stars_mod2
                    _stars_mod2.record_game_stars(
                        game_result, home_team, away_team,
                        preseason=is_preseason, game_date=game_date)
                except Exception as _se2:
                    print(f"Three-stars error (non-fatal): {_se2}")

                # Hollow overhype: marketed as grudge week, delivered a
                # snoozer -- the marketing wrote checks the game couldn't cash.
                # (_gfights came from the narrative post-game hook above, which
                # also stamped _fights_total onto the sim.)
                self._grudge_week_grade(game_date, home_team, away_team,
                                        home_score, away_score, went_to_ot,
                                        fights=_gfights)

                # Only generate news for user team games
                if user_team and user_team in (home_team, away_team):
                    opponent = away_team if user_team == home_team else home_team
                    result = "won" if (winner == user_team) else "lost"
                    # Format score from user team perspective
                    if user_team == home_team:
                        user_score = home_score
                        opp_score = away_score
                    else:
                        user_score = away_score
                        opp_score = home_score

                    self.add_news(f"Your team {result} {user_score}-{opp_score} against {opponent.team_name}.")

            # Clean up game tracking flags
            all_teams = []
            for game in games:
                try:
                    # Extract teams based on game format (same logic as above)
                    if isinstance(game, dict):
                        home_team = game.get('home_team')
                        away_team = game.get('away_team')
                    elif isinstance(game, tuple) and len(game) >= 3:
                        _, home_team, away_team = game[:3]
                    else:
                        continue

                    if home_team:
                        all_teams.append(home_team)
                    if away_team:
                        all_teams.append(away_team)
                except Exception:
                    continue

            for team in all_teams:
                if hasattr(team, 'roster'):
                    for player in team.roster:
                        if hasattr(player, '_game_added'):
                            delattr(player, '_game_added')

    def _start_offseason(self):
            """Start the offseason phase."""
            # Season continuity guard (Muck 2026-10-02): validate that the
            # season year follows recorded history without gaps before any
            # rollover logic runs. Detection only -- never blocks or mutates.
            try:
                self._validate_season_continuity()
            except Exception:
                pass
            # Cup recap backstop: if the champion was decided outside the daily
            # loop (bulk sims), the inbox still gets the awarding story. Once.
            try:
                self._maybe_send_cup_recap()
            except Exception:
                pass
            # Controversy cooldown + staff rep + Cup bonus. Reads standings before
            # league.end_of_season() wipes them.
            self._update_offseason_reputations()
            # Captaincy torch-passing (captaincy_change.py): AI clubs rarely
            # and conservatively hand the C to a plainly worthier successor.
            # Same assess/apply logic the human GM faces -- no free lunch.
            try:
                self._ai_offseason_captaincy_changes()
            except Exception:
                pass
            # League Memory: record the completed season (champion, awards,
            # standings) before league.end_of_season() wipes the stats.
            try:
                self._record_season_to_history()
            except Exception:
                pass
            # Board season review (manager_career.BoardSystem.season_review):
            # the year-end reckoning -- expectation vs reality, confidence
            # delta, and the season rollover (honeymoon decay, patience
            # erosion, counter resets). Must run before league.end_of_season()
            # wipes the standings and stats it reads. Previously this method
            # had no caller, so every season played as "year 1" forever.
            try:
                self._offseason_board_review()
            except Exception:
                pass
            # Immortality (immortality.py): retirements, HOF ballot, retired
            # numbers, era arguments. Runs on recorded career totals, before
            # league.end_of_season() wipes the stats. Purely additive.
            try:
                self._offseason_immortality()
            except Exception:
                pass
            # Copycat league: AI teams steal the Cup champion's systems.
            # (Familiarity cost included -- copying isn't free.)
            try:
                import tactics as _tx
                _CAT_LABEL = {"pp": "power play", "pk": "penalty kill",
                              "ozone": "offensive-zone system",
                              "forecheck": "forecheck",
                              "dzone": "defensive-zone coverage"}
                for _tn, _cat, _sys, _lore in _tx.offseason_copycat(
                        getattr(self, 'league', None)):
                    _sysname = _tx.CATALOGS.get(_cat, {}).get(_sys, {}).get(
                        "name", _sys)
                    _lorebit = f" — {_lore}" if _lore else ""
                    self.add_news(
                        f"Copycat league: {_tn} install the {_sysname} "
                        f"{_CAT_LABEL.get(_cat, 'system')} after watching the "
                        f"champions win with it{_lorebit}.")
            except Exception:
                pass
            # Buyout window (June 15-30, real NHL timing): AI GMs clear dead
            # weight; the user's candidates arrive as an interactive inbox
            # message (same pattern as RFA qualifying). The stamped date moves
            # INTO the window -- previously the July-1 jump skipped June 15-30
            # entirely, so the transaction_windows gate meant nobody (user or
            # AI) could ever execute a buyout. Runs before the draft (June
            # 23-25), matching the real calendar order.
            try:
                self._set_current_date(date(self.league.season_year + 1, 6, 15))
            except Exception:
                pass
            try:
                import buyout_window as _bw
                _bw_summary = _bw.process_buyout_window(
                    self.league, app=self, rng=getattr(self, "_rng", None)) or {}
                _n_bought = len(_bw_summary.get("ai_buyouts") or [])
                if _n_bought:
                    self.add_news(
                        f"Buyout window (June 15-30): {_n_bought} player"
                        f"{'s' if _n_bought != 1 else ''} bought out "
                        f"league-wide.")
            except Exception:
                debug_print("Buyout window failed (non-fatal):")
                import traceback
                traceback.print_exc()
            # Tentpole guarantee: the draft lottery (May 8) and entry draft
            # (June 23-25) are date-triggered, but the July-1 jump below would
            # otherwise skip them every season. Run them now when missed; the
            # per-year guards make it a no-op when the date path already ran.
            # Must precede league.end_of_season(), which wipes the standings the
            # draft order is built from.
            self._guarantee_offseason_tentpoles()
            # D5: offseason staff carousel -- AI clubs approach expiring
            # staff (the "stud assistant in his final year who wants a
            # head-coach job" case). Runs BEFORE end_of_season() so the
            # tick below only decrements the staff who stayed.
            try:
                import staff_poaching as _sp
                _pn5 = _sp.offseason_staff_poach(self.league, self.user_team)
                if _pn5:
                    self.league.staff_contract_news = (
                        list(getattr(self.league, "staff_contract_news", None)
                             or []) + [str(_m) for _m in _pn5])
            except Exception:
                pass
            # Age players and reset stats
            self.league.end_of_season()

            # D5 follow-up: the contract tick above held expired staff for
            # renewal instead of releasing them. Their offer arrives as one
            # interactive inbox message (never a popout). Decline/ignore
            # walks them to the free-agent pool.
            # MP: every human-managed club gets its own message; clients
            # answer via the routed staff_renew action.
            try:
                import staff_renewals as _srq
                _human = []
                try:
                    from game_classes import is_human_managed as _ihm
                    for _t in (getattr(self.league, "teams", None) or []):
                        try:
                            if _ihm(_t):
                                _human.append(_t)
                        except Exception:
                            continue
                except Exception:
                    pass
                if not _human:
                    _uq = getattr(self, "user_team", None)
                    if _uq is not None:
                        _human = [_uq]
                for _hq in _human:
                    _srq.queue_user_renewal_message(self.league, _hq, self)
            except Exception:
                pass

            # Draft rights lifecycle: end_of_season() (game_classes) collected
            # re-entry / UFA / retirement / warning messages on league.rights_news.
            # Flush them to the inbox here (the monthly Jan-Jun beat hook would
            # otherwise hold July's rights news until January).
            try:
                _rn = list(getattr(self.league, "rights_news", None) or [])
                for _msg in _rn:
                    try:
                        self.add_news(str(_msg))
                    except Exception:
                        pass
                if _rn:
                    self.league.rights_news = []
            except Exception:
                pass
            # Prospect junior/college award headlines from end_of_season.
            try:
                _pn = list(getattr(self.league, "prospect_awards_news", None)
                           or [])
                for _msg in _pn:
                    try:
                        self.add_news("🏆 " + str(_msg))
                    except Exception:
                        pass
                if _pn:
                    self.league.prospect_awards_news = []
            except Exception:
                pass
            # Rivalry-review verdicts from end_of_season.
            try:
                _rn = list(getattr(self.league, "rivalry_review_news", None)
                           or [])
                for _msg in _rn:
                    try:
                        self.add_news("⚔️ " + str(_msg))
                    except Exception:
                        pass
                if _rn:
                    self.league.rivalry_review_news = []
            except Exception:
                pass
            # D5: staff contract expiries + offseason poach moves.
            try:
                _sn = list(getattr(self.league, "staff_contract_news", None)
                           or [])
                for _msg in _sn:
                    try:
                        self.add_news("🧑‍💼 " + str(_msg))
                    except Exception:
                        pass
                if _sn:
                    self.league.staff_contract_news = []
            except Exception:
                pass
            # Snapshot staff breakthrough headlines for the year-end recap
            # (delivered below), which runs after these lists are drained.
            try:
                self._season_review_staff_news = list(
                    getattr(self.league, "staff_breakthrough_news", None) or [])
            except Exception:
                self._season_review_staff_news = []
            # Staff breakthrough headlines from end_of_season.
            try:
                _bn = list(getattr(self.league, "staff_breakthrough_news", None)
                           or [])
                for _msg in _bn:
                    try:
                        self.add_news("📈 " + str(_msg))
                    except Exception:
                        pass
                if _bn:
                    self.league.staff_breakthrough_news = []
            except Exception:
                pass
            # ELC slide headlines from end_of_season (CBA 9.1(d)).
            try:
                _sn = list(getattr(self.league, "elc_slide_news", None) or [])
                for _msg in _sn:
                    try:
                        self.add_news("📝 " + str(_msg))
                    except Exception:
                        pass
                if _sn:
                    self.league.elc_slide_news = []
            except Exception:
                pass

            # Restricted free agency (rfa_system.py): qualifying offers at the
            # real CBA minimums, rare AI offer sheets with real pick
            # compensation, and salary arbitration at real-life-calibrated filing
            # rates. AI clubs are processed end-to-end; the user's qualifying
            # decisions arrive as an interactive inbox message. Runs after
            # end_of_season() expired the contracts above.
            try:
                import player_decision as _pd
                _pd.seed_league_decision_fields(self.league)
            except Exception:
                pass
            try:
                import rfa_system as _rfa
                _rfa_summary = _rfa.process_rfa_offseason(
                    self.league, app=self, rng=getattr(self, "_rng", None))
                if _rfa_summary.get("arbitration_awards"):
                    self.add_news(
                        f"Arbitration tracker: "
                        f"{_rfa_summary['arbitration_filings']} filed, "
                        f"{len(_rfa_summary['arbitration_awards'])} resolved.")
            except Exception:
                pass

            # BUG-015: generate the new season's slate. generate_schedule() was
            # only ever called on new-career paths, so after the first rollover
            # the league had zero scheduled games -- season 2+ never started
            # (standings frozen at 0-0-0, the season-end safety net had no last
            # date to key on). Real NHL timing: the schedule drops in late June,
            # i.e. right here, before the July-1 jump. The template cache makes
            # the rebuild cheap; generation is deterministic per season_year so
            # a re-run is idempotent.
            try:
                self.league.generate_schedule()
                try:
                    import outdoor_games as _og
                    _og.schedule_outdoor_games(self.league)
                except Exception:
                    pass
            except Exception:
                import traceback
                traceback.print_exc()
            # A new schedule was generated: drop cached season dates/games so the
            # season-end safety net in simulate_day recomputes from the new slate
            # instead of the previous season's.
            self._season_last_game_date = None
            if hasattr(self, '_schedule_cache'):
                self._schedule_cache.clear()
            if hasattr(self, '_strength_cache'):
                self._strength_cache.clear()

            # Generate new draft class (quality from settings: Weak/Normal/Strong/Generational)
            # The upcoming entry draft is held in June of next calendar year; stamp
            # the class with that year and fold in this summer's rights re-entries
            # (unsigned CHL prospects re-entering the draft). The class is
            # regenerated for real on draft day in _hold_entry_draft, which clears
            # league.draft_reentries after consuming them -- so this call must NOT
            # clear the list.
            draft_quality = self.get_settings().get('simulation', {}).get('draft_class_quality', 'Normal')
            from draft_generator import generate_draft_class
            _gen_kwargs = {"num_prospects": 336, "quality": draft_quality}  # 7 rounds x 32 = 224 picks + ~112 undrafted (Eastside-style)
            try:
                import inspect as _inspect
                _params = _inspect.signature(generate_draft_class).parameters
                if "draft_year" in _params:
                    _gen_kwargs["draft_year"] = self.league.season_year + 1
                if "reentries" in _params:
                    _gen_kwargs["reentries"] = getattr(self.league, "draft_reentries", None) or []
            except Exception:
                pass
            self.league.draft_prospects = generate_draft_class(**_gen_kwargs)  # 7 rounds × 32 teams = 224 players

            # Undrafted European free agents: a thin yearly batch (4-8, ~5) of
            # older Euro-league players appended to the FA pool. Mostly AHL/tweener
            # material with usually 0-1 plausible NHL gamble; true impact talent at
            # ~10%/offseason, never scheduled. The AI sees them as ordinary free
            # agents. Runs once per real offseason, before the July-1 jump
            # (guarded by league._euro_fa_year -- a second pass for the same
            # offseason would append a duplicate batch).
            try:
                from euro_free_agents import run_euro_free_agency
                _efa_year = self.league.season_year
                if getattr(self.league, "_euro_fa_year", None) != _efa_year:
                    _efa_summary = run_euro_free_agency(
                        self.league, _efa_year, app=self) or {}
                    if _efa_summary.get("added"):
                        self.league._euro_fa_year = _efa_year
            except Exception:
                pass

            # Post-draft "steal of the draft" retrospective: late-round picks whose
            # displayed stock has exploded since draft day get their retrospective
            # now, once per player, rather than pre-draft hype they never had.
            try:
                from draft_stories import steal_retrospective
                for _story in (steal_retrospective(self.league) or [])[:2]:
                    self.add_news(
                        f"{_story.get('title', 'Draft')} — {_story.get('text', '')}")
            except Exception:
                pass

            # Reset the deadline manager's per-season state so last year's
            # trade activity doesn't leak into the new season's intel panel.
            try:
                from trade_deadline_manager import get_deadline_manager
                get_deadline_manager(getattr(self, 'game_manager', None)).reset_for_new_season()
            except Exception:
                pass

            # Update the current date to offseason
            self._set_current_date(date(self.league.season_year, 7, 1))  # Jump to July 1st (Free Agency)

            self._ui_notify("info",
                            f"Welcome to the {self.league.season_year}-{self.league.season_year + 1} offseason!\n\n"
                            "• Players have aged one year\n"
                            "• Stats have been reset\n"
                            "• New draft class available\n"
                            "• Free agency is now open")

            self.update_all_views()

    def _update_day_sim_overlay(self, busy, status=""):
            """Show/hide the day-sim loading toast (Muck 2026-10-02).

            The day sim blocks the main thread; without a visible loading
            prompt the app looks crashed. The toast is a small non-modal
            spinner + status in the bottom-right corner -- deliberately not
            modal and not centered, so it never covers crucial info and can
            never block the Game Day Watch/Quick choice. Never raises.
            """
            try:
                overlay = getattr(self, '_day_sim_overlay', None)
                if busy:
                    if overlay is None or not overlay.is_showing:
                        try:
                            from day_sim_loading import DaySimLoadingOverlay
                            overlay = DaySimLoadingOverlay(self)
                            self._day_sim_overlay = overlay
                        except Exception:
                            return
                    if status:
                        try:
                            overlay.set_status(status)
                        except Exception:
                            pass
                else:
                    # Auto-advance owns the overlay between days: keep it up
                    # (no flicker) and show the new date instead of tearing it
                    # down and rebuilding it every day.
                    if getattr(self, '_auto_advance', False):
                        if overlay is not None and bool(overlay.is_showing):
                            try:
                                overlay.set_status(
                                    "Auto-advancing… %s  (ESC to stop)"
                                    % self.current_date.strftime('%b %d, %Y'))
                            except Exception:
                                pass
                        return
                    if overlay is not None:
                        try:
                            overlay.destroy()
                        except Exception:
                            pass
                        try:
                            self._day_sim_overlay = None
                        except Exception:
                            pass
            except Exception:
                pass

    def _update_team_colors(self):
            """Update button colors to match the user's team colors"""
            if hasattr(self, 'user_team') and self.user_team and hasattr(self, 'modern_theme'):
                self.modern_theme.update_team_colors(self.style, self.user_team.team_name)
            # App-wide accent follows the user's team: every CustomTkinter
            # widget built after this call (nav pills, primary buttons,
            # selected states) and the game visualizer wear the team color.
            try:
                if getattr(self, 'user_team', None):
                    import ctk_theme
                    from team_identity_system import accent_for_team
                    accent, hover, _text = accent_for_team(self.user_team.team_name)
                    ctk_theme.set_team_accent(accent, hover, _text)
                    # Plain-tkinter dashboard reads modern_ui.AppColors at
                    # build time -- keep it in step (ACCENT_BG is a whisper
                    # of the accent over the window background).
                    from modern_ui import AppColors
                    AppColors.ACCENT = accent
                    AppColors.ACCENT_DIM = hover
                    AppColors.ACCENT_BG = _mix_hex(accent, "#0e0e11", 0.85)
                    # Contrast-safe text colors for the team accent: _text is
                    # readable ON the accent (standings, buttons); the on-dark
                    # variant is the accent itself made readable on dark bgs.
                    AppColors.ACCENT_TEXT = _text
                    from team_identity_system import ensure_text_contrast
                    # The on-dark variant is ensured against the actual whisper
                    # bg it sits on (PillBadge), not pure dark -- the whisper is
                    # a touch lighter and that matters at the margin.
                    AppColors.ACCENT_ON_DARK = ensure_text_contrast(
                        accent, AppColors.ACCENT_BG)
            except Exception:
                pass

    # --- Critical sim methods from HockeyManagerGUI ---

    def _record_game_result(self, game_result):
        """Append a game result and keep the derived indexes in sync."""
        self.game_results.append(game_result)
        if self._results_index_src is self.game_results:
            key = self._result_date_key(game_result.get('date'))
            if key is not None:
                self._results_by_date.setdefault(key, []).append(game_result)
                self._results_by_matchup[
                    (key, id(game_result.get('home_team')),
                     id(game_result.get('away_team')))] = game_result

    def _sim_game_guaranteed(self, home_team, away_team, game, game_date,
                             is_preseason=False):
        """Simulate one scheduled game; NEVER raises, NEVER drops the game.

        Tiers:
          0 -- normal path: the full event sim for 'full'-detail leagues
               (regular season only), else the lightweight sim.
          1 -- retry via the lightweight sim (skipped when tier 0 already
               was the lightweight path).
          2 -- deterministic last-resort result from roster strength
               (seeded, reproducible, loudly logged).

        The preseason flag flows through every tier: exhibitions never
        touch standings or season stats, in ANY tier. Returns
        (winner, loser, scores, went_to_ot, full_sim) with full_sim None
        unless tier 0 ran the full event sim.
        """
        league_key = game.get('league') if isinstance(game, dict) else None
        _want_full = False
        try:
            _want_full = (self._league_sim_detail(league_key) == 'full'
                          and not is_preseason)
        except Exception as _ld_e:
            # Detail lookup failed: fall through to the lightweight sim.
            self._log_slate_fallback(home_team, away_team, game_date,
                                     _ld_e, tier="full->lightweight",
                                     detail="sim-detail lookup failed")
        if _want_full:
            try:
                winner, loser, scores, went_to_ot, full_sim = \
                    self._simulate_game_full_batch(home_team, away_team)
                return winner, loser, scores, went_to_ot, full_sim
            except Exception as _full_e:
                self._log_slate_fallback(
                    home_team, away_team, game_date, _full_e,
                    tier="full->lightweight",
                    detail="full-batch sim failed; retrying lightweight")
                # Fall through to the lightweight retry below.
        try:
            winner, loser, scores, went_to_ot = \
                self._simulate_game_lightweight(home_team, away_team,
                                                preseason=is_preseason)
            return winner, loser, scores, went_to_ot, None
        except Exception as _light_e:
            self._log_slate_fallback(
                home_team, away_team, game_date, _light_e,
                tier="lightweight->deterministic",
                detail=("lightweight sim failed"
                        + (" after full-batch failure" if _want_full else "")))
        # Tier 2: deterministic last resort. Built to not raise; the
        # belt-and-braces except below is for pathological team objects.
        try:
            return self._slate_deterministic_result(home_team, away_team,
                                                    game_date)
        except Exception as _det_e:
            self._log_slate_fallback(home_team, away_team, game_date,
                                     _det_e, tier="deterministic->coinflip",
                                     detail="deterministic builder failed; "
                                            "absolute last resort")
            import random as _r
            _rng = _r.Random(f"coinflip|{game_date}|"
                             f"{getattr(home_team, 'team_name', '?')}|"
                             f"{getattr(away_team, 'team_name', '?')}")
            if _rng.random() < 0.5:
                return home_team, away_team, (2, 1), False, None
            return away_team, home_team, (1, 2), False, None

    def _update_standings_fast(self, home_team, away_team, winner, scores, went_to_ot=False,
                               preseason=False):
        """Fast standings update without complex calculations.

        preseason: exhibitions never touch the table."""
        if preseason:
            return
        home_score, away_score = scores
        
        # Ensure teams exist in standings
        for team in [home_team, away_team]:
            if team.team_name not in self.league.standings:
                self.league.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
        
        # Update winner (2 points)
        self.league.standings[winner.team_name]["W"] += 1
        self.league.standings[winner.team_name]["Points"] += 2
        
        # Update loser (OTL point if went to OT/SO, else regulation loss)
        loser = away_team if winner == home_team else home_team
        if went_to_ot:
            self.league.standings[loser.team_name]["OTL"] += 1
            self.league.standings[loser.team_name]["Points"] += 1
        else:
            self.league.standings[loser.team_name]["L"] += 1

        # Sync the Team objects too (dashboard/standings UI read
        # team.wins/losses/ot_losses/games_played/goals_for/goals_against).
        try:
            winner.update_record("WIN")
            loser.update_record("LOSS", overtime=went_to_ot)
            home_team.goals_for = getattr(home_team, 'goals_for', 0) + home_score
            home_team.goals_against = getattr(home_team, 'goals_against', 0) + away_score
            away_team.goals_for = getattr(away_team, 'goals_for', 0) + away_score
            away_team.goals_against = getattr(away_team, 'goals_against', 0) + home_score
        except Exception:
            pass

    def process_waivers(self):
        """Process waiver claims and update waiver days for all players on waivers."""
        # NHL claim order (CBA Art. 13): lowest points percentage first --
        # previous season's final standings until Nov 1, current standings
        # after that. A club that claims drops to the bottom of the order.
        try:
            import waiver_logic as _wl
            teams_by_ranking = _wl.waiver_priority_order(
                self.league, self.current_date)
        except Exception:
            teams_by_ranking = list(getattr(self.league, "teams", []) or [])
        
        claimed_players = []
        for player in self.waiver_list:
            if player in claimed_players:
                continue

            # The 2-day clock ticks in the daily advance (see above); a
            # player is only eligible for claim processing once it has
            # fully elapsed. No same-day claims for fresh placements.
            if player.waiver_days > 0:
                continue

            # Clock elapsed: process possible claims
            # Determine claiming team (if any)
            claiming_team = None
            for team in teams_by_ranking:
                # Skip player's current team
                if team.team_name == player.team_name:
                    continue

                # The user's club claims only through a submitted pending
                # claim (WaiversView "Claim" button). Real NHL: claims are
                # due by noon and processed in priority order, so a
                # higher-priority rival beats your claim.
                try:
                    import game_classes as _gc
                    _is_user = bool(_gc.is_human_managed(team))
                except Exception:
                    _is_user = bool(getattr(team, 'is_user_team', False))
                if _is_user:
                    # Pending claims are per-team: the legacy host flag
                    # belongs to the host's own club only, client claims
                    # ride in player.mp_claim_teams.
                    _mp_pending = (getattr(player, "mp_claim_teams", None)
                                   or [])
                    _is_host_club = (team is getattr(self, "user_team",
                                                     None))
                    _claimed = (
                        team.team_name in _mp_pending
                        or (getattr(player, "user_claim_pending", False)
                            and _is_host_club))
                    if (_claimed
                            and len(team.roster) < 23
                            and team.cap_space > player.contract.salary):
                        claiming_team = team
                        break
                    continue
                    
                # Check if team is interested (based on player quality and team needs)
                if len(team.roster) < 23 and team.cap_space > player.contract.salary:
                    # Calculate team interest based on player quality vs. team needs
                    player_rating = player.overall_rating()
                    position_need = 1.0  # Default need
                    
                    # Check position needs
                    if player.primary_position == PlayerPosition.GOALIE:
                        goalies = [p for p in team.roster if p.primary_position == PlayerPosition.GOALIE]
                        if len(goalies) < 2:
                            position_need = 1.5  # High need for goalies
                    elif player.primary_position in [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
                        forwards = [p for p in team.roster if p.primary_position in [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]]
                        if len(forwards) < 12:
                            position_need = 1.3  # Need forwards
                    else:  # Defensemen
                        defensemen = [p for p in team.roster if p.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]]
                        if len(defensemen) < 6:
                            position_need = 1.3  # Need defensemen
                            
                    # Teams are more likely to claim higher-rated players
                    claim_chance = min(0.9, (player_rating / 100) * position_need)
                    
                    if random.random() < claim_chance:
                        claiming_team = team
                        break
            
            # Process claim if a team is interested
            if claiming_team:
                self._execute_waiver_claim(player, claiming_team)

                # Mark as claimed
                claimed_players.append(player)
            else:
                # Player cleared waivers
                player.waiver_days = 0
                player.on_waivers = False
                # A pending user claim that never fired (roster filled or
                # cap evaporated before processing) lapses quietly.
                if getattr(player, "user_claim_pending", False):
                    try:
                        player.user_claim_pending = False
                        self.add_news(
                            f"Your waiver claim for {player.full_name} "
                            f"lapsed (roster or cap space changed).")
                    except Exception:
                        pass
                try:
                    _lapsed = list(getattr(player, "mp_claim_teams", None)
                                   or [])
                except Exception:
                    _lapsed = []
                for _loser in _lapsed:
                    try:
                        self.add_news(
                            f"{_loser}'s waiver claim for "
                            f"{player.full_name} lapsed (roster or cap "
                            f"space changed before processing).")
                    except Exception:
                        pass
                try:
                    player.mp_claim_teams = []
                except Exception:
                    pass
                
                # Add to original team's AHL roster on clearance: waiving is
                # always a demotion move (cap burial or AHL shuttle), for
                # AI clubs exactly as for the user's. (BUG-019: AI clubs
                # now use the wire, so this branch fires for them too.)
                original_team = next((t for t in self.league.teams if t.team_name == player.team_name), None)
                if original_team and hasattr(original_team, 'ahl_roster'):
                    if player in original_team.roster:
                        original_team.roster.remove(player)
                    # CHL-NHL agreement: a cleared under-20 CHL prospect
                    # who isn't AHL-eligible (new CBA: 19-year-old
                    # first-rounders excepted) goes back to junior, not
                    # the AHL.
                    try:
                        import game_classes as _gcw
                        _to_junior = (
                            getattr(player, "contract", None) is not None
                            and _gcw.junior_track_of(player) == "CHL"
                            and not _gcw.prospect_ahl_eligible(player))
                    except Exception:
                        _to_junior = False
                    if _to_junior:
                        try:
                            player.playing_where = \
                                _gcw.junior_assignment_label(player)
                        except Exception:
                            pass
                        if player not in original_team.prospects:
                            original_team.prospects.append(player)
                    else:
                        original_team.ahl_roster.append(player)
                        # Jersey number: the drafted prospect wants his
                        # favorite -- preferred, else second choice, else
                        # first free legal number in the org pool.
                        try:
                            import immortality as _im_arr
                            _im_arr.assign_arrival_number(
                                original_team, player,
                                int(getattr(getattr(self, "league", None),
                                            "season_year", 2026) or 2026))
                        except Exception:
                            pass
                        # New-CBA paper-transaction rule: the assignment
                        # stamps the recall gate -- he must play an AHL
                        # game before he can come back up.
                        try:
                            import ahl_system as _ahl_stamp2
                            _ahl_stamp2.stamp_ahl_assignment(player)
                        except Exception:
                            pass
                else:
                    _to_junior = False
                # Clearance is league news regardless of who runs the club.
                if _to_junior:
                    self.add_news(
                        f"{player.full_name} cleared waivers and was "
                        f"returned to junior.")
                else:
                    self.add_news(f"{player.full_name} cleared waivers.")

        # Remove claimed players from waiver list
        for player in claimed_players:
            if player in self.waiver_list:
                self.waiver_list.remove(player)

        # Remove players who cleared waivers (on_waivers=False now).
        # Players whose clock hit 0 but who await the next Mon/Thu
        # processing stay listed -- the shed already ended when the
        # clock elapsed.
        self.waiver_list = [p for p in self.waiver_list if p.on_waivers]
        
        # Update any open waiver windows
        if 'waivers' in self.open_windows and self.open_windows['waivers'].winfo_exists():
            self.open_windows['waivers'].populate_eligible_players()
            self.open_windows['waivers'].populate_waiver_wire()

    def process_scouting_assignments(self):
        """Process all active scouting assignments for the day.

        Ported from HockeyManagerGUI.process_scouting_assignments (main.py);
        Tk window refresh replaced with the _ui_notify hook.
        """
        import random
        assignments = getattr(self, "scouting_assignments", None)
        if not assignments:
            return  # No assignments to process
        user_team = getattr(self, "user_team", None)
        if user_team is None:
            return
        if not hasattr(user_team, "scouting_reports"):
            user_team.scouting_reports = {}

        # Each day, scouts have a chance to watch the players they're assigned to
        for player, scout in list(assignments.items()):
            try:
                pid = getattr(player, "id", None) or getattr(player, "player_id", None)
                # Check if player already has a scouting report
                if pid not in user_team.scouting_reports:
                    # Create new report if none exists
                    user_team.scouting_reports[pid] = ScoutingReport(
                        player=player,
                        scout=scout
                    )

                # Get the existing report
                report = user_team.scouting_reports[pid]

                # Determine if scout makes progress today (random chance)
                # Better scouts work faster
                scout_efficiency = (getattr(scout, "judging_player_ability", 50)
                                    + getattr(scout, "judging_player_potential", 50)) / 40
                viewing_chance = 0.25 * scout_efficiency  # 25% base chance adjusted by scout skill

                if random.random() < viewing_chance:
                    # Scout viewed the player today, update the report
                    report.update_report(player, scout)

                    # Once a report reaches 'A' accuracy, remove the assignment
                    if getattr(report, "accuracy", None) == 'A':
                        del assignments[player]

                        # Add a news item
                        news_item = {
                            'date': self.current_date,
                            'type': 'scouting',
                            'story': f"Scouting Report: {getattr(scout, 'full_name', 'A scout')} has completed a comprehensive "
                            + f"evaluation of {getattr(player, 'full_name', 'a prospect')}. "
                            + f"Projected potential: {getattr(report, 'scouted_potential', 'unknown')}."
                        }
                        self.news_log.append(news_item)
            except Exception:
                continue

        # Notify UI (native Qt or Tk) to refresh any open scouting view
        try:
            self._ui_notify("scouting_reports_updated", {})
        except Exception:
            pass

    def _audit_season_slate(self):
        """SLATE GUARANTEE, Part 2 (2026-10-02, BUG-003/004/005).

        Compare every NHL club's games played against its ACTUALLY
        SCHEDULED regular-season games (counted from league.schedule).
        This is version-proof: an 82-game schedule expects 82 even when
        the code default has moved to 84 (mid-save slate changes must not
        halt a legitimately completed season). Dropped games are still
        caught -- played < scheduled flags regardless of slate length.
        Falls back to season_games_count when the schedule is unavailable.
        Returns [(team_name, gp, target)] -- [] when the season is whole.
        A club missing from the standings entirely counts as 0 GP.
        """
        shortfalls = []
        try:
            _lg = getattr(self, 'league', None)
            _standings = getattr(_lg, 'standings', None) or {}
            _nhl_names = {t.team_name
                          for t in (getattr(_lg, 'teams', None) or [])
                          if getattr(t, 'league_name', '')
                          == 'National Hockey League'}

            # Count scheduled regular-season NHL games per team.
            _scheduled = {}
            try:
                for _e in (getattr(_lg, 'schedule', None) or []):
                    if not isinstance(_e, dict):
                        continue
                    if _e.get('preseason'):
                        continue
                    # BUG-002 fix (2026-10-03): playoff games are not
                    # regular-season games; they must not count toward
                    # the 84-game slate target.
                    if _e.get('playoff'):
                        continue
                    _h = _e.get('home_team')
                    _a = _e.get('away_team')
                    _hn = (getattr(_h, 'team_name', None)
                           or (str(_h) if _h else None))
                    _an = (getattr(_a, 'team_name', None)
                           or (str(_a) if _a else None))
                    for _nm in (_hn, _an):
                        if _nm in _nhl_names:
                            _scheduled[_nm] = _scheduled.get(_nm, 0) + 1
            except Exception:
                _scheduled = {}

            # Fallback target when the schedule can't be counted.
            _fallback = getattr(_lg, 'season_games_count', None)
            if _fallback is None:
                _fallback = getattr(self, 'season_games_count', 82)
            _fallback = _fallback or 82

            def _gp(stats):
                return (stats.get('W', stats.get('Wins', 0))
                        + stats.get('L', stats.get('Losses', 0))
                        + stats.get('OTL', 0))

            for _name in sorted(_nhl_names):
                _played = _gp(_standings.get(_name) or {})
                _expect = _scheduled.get(_name, _fallback)
                if _played < _expect:
                    shortfalls.append((_name, _played, _expect))
        except Exception as _e:
            print(f"Season slate audit failed (non-fatal): {_e}")
        return shortfalls

    def _handle_slate_shortfall(self, shortfalls):
        """Loud stop for a short season slate. Never silent, never a stall.

        Prints a banner naming every short club and its deficit, writes it
        to the news log, and creates an inbox item for the user. Then
        blocks loudly:
          - headless/bulk mode: raises SeasonIntegrityError with the full
            shortfall detail (no GUI exists to show a blocker card);
          - GUI mode: arms the 'season_integrity' day-blocker (picked up by
            get_continue_state on the next Continue press) and returns, so
            end_of_season bails BEFORE the season-end guard is set. An
            exception here would propagate out of end_of_season through
            simulate_day -- whose outer try has only a `finally`, no
            `except` -- into tkinter's callback handler: an ugly stderr
            traceback with no blocking behavior and a re-press loop.
        """
        _lines = [f"{_n}: {_gp}/{_t} (short {_t - _gp})"
                  for _n, _gp, _t in shortfalls]
        _detail = "; ".join(_lines)
        _banner = ("\n"
                   "🚨🚨🚨 SEASON SLATE SHORTFALL -- SEASON HALTED 🚨🚨🚨\n"
                   "The regular season ended with clubs short of their "
                   "scheduled games:\n"
                   + "\n".join(f"  • {_l}" for _l in _lines) + "\n"
                   "This is a data-integrity stop: awards, playoffs and the "
                   "offseason will NOT run on a short slate.\n"
                   "🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨\n")
        print(_banner)
        try:
            _nl = getattr(self, 'news_log', None)
            if isinstance(_nl, list):
                _nl.append({
                    'date': getattr(self, 'current_date', None),
                    'story': (f"🚨 Season integrity stop: slate shortfall -- "
                              f"{_detail}. The season cannot advance until "
                              f"the missing games are investigated.")})
        except Exception:
            pass
        try:
            _ut = getattr(self, 'user_team', None)
            if _ut is not None and getattr(_ut, 'inbox', None) is not None:
                from game_classes import EmailMessage
                _ut.inbox.add_message(EmailMessage(
                    sender="League Office",
                    sender_type="League",
                    subject="🚨 Season integrity stop: season slate shortfall",
                    content=("Commissioner's Office -- URGENT\n\n"
                             "The regular season has ended with clubs short "
                             "of their scheduled games:\n\n"
                             + "\n".join(f"• {_l}" for _l in _lines) + "\n\n"
                             "The season is HALTED: no awards, no playoffs, "
                             "no offseason until this is resolved. This is a "
                             "data-integrity stop, not a task you can complete "
                             "in the UI -- report it so the missing games can "
                             "be investigated and restored."),
                    date_sent=getattr(self, 'current_date', None) or date.today(),
                    is_important=True,
                    is_urgent=True,
                    category="League",
                    priority=4,
                    requires_response=False,
                ))
        except Exception:
            pass
        if getattr(self, '_bulk_simming', False):
            raise SeasonIntegrityError(
                f"Season slate shortfall -- season halted: {_detail}")
        # GUI mode: arm the day-blocker; the next Continue press shows it
        # via get_continue_state instead of re-entering end_of_season.
        try:
            self._season_integrity_shortfall = [
                (str(_n), int(_gp), int(_t)) for _n, _gp, _t in shortfalls]
        except Exception:
            self._season_integrity_shortfall = True

    def _conduct_vezina_vote(self):
        """Run the Vezina Trophy GM vote: 31 AI GMs + the human ballot.

        Runs once per season at the end of the regular season, before
        reputations/trophy cases are banked. The 5-3-1 tally decides the
        winner; the result is stored on the league (persisted in saves)
        so the awards calculator, ceremony, and history book all agree.
        In bulk-sim mode the human ballot auto-fills from the model.
        """
        league = getattr(self, "league", None)
        if league is None:
            return
        season_year = int(getattr(league, "season_year", 0) or 0)
        votes = getattr(league, "vezina_votes", None) or {}
        if str(season_year) in votes:
            return  # already voted this season
        try:
            import awards_race as ar
        except ImportError:
            return
        teams = list(getattr(league, "teams", []) or [])
        players = [p for t in teams for p in (getattr(t, "roster", None) or [])]
        goalies = [p for p in players if "GOALIE" in str(
            getattr(getattr(p, "primary_position", None), "name", ""))]
        try:
            candidates = ar.vezina_race(goalies)
        except Exception:
            candidates = []
        if not candidates:
            return
        team_pct = {}
        for t in teams:
            gp = getattr(t, "games_played", 0) or 0
            pts = getattr(t, "points", 0) or 0
            team_pct[getattr(t, "team_name", "")] = (
                pts / (2 * gp)) if gp else 0.5

        user_team = getattr(self, "user_team", None)
        user_name = getattr(user_team, "team_name", "") if user_team else ""
        ballots = []
        # 31 AI GMs vote their boards.
        for t in teams:
            if getattr(t, "team_name", "") == user_name:
                continue
            try:
                b = ar.gm_vezina_ballot(t, candidates, team_pct,
                                        season_year)
                if b:
                    ballots.append(b)
            except Exception:
                pass
        # The human GM's ballot (auto-filled when bulk simming).
        try:
            if getattr(self, "_bulk_simming", False):
                human = [r.get("player") for r in candidates[:3]]
            else:
                import awards_ceremony as ac
                human = ac.collect_human_vezina_ballot(self, candidates)
            if human:
                ballots.append(human)
        except Exception:
            pass
        try:
            winner, results = ar.tally_vezina_ballots(ballots, candidates)
        except Exception:
            return
        if winner is None:
            return
        try:
            wid = int(getattr(winner, "id", -1) or -1)
        except Exception:
            wid = -1
        votes[str(season_year)] = {
            "winner_id": wid,
            "winner_name": getattr(winner, "full_name",
                                   getattr(winner, "name", "?")),
            "ballots": len(ballots),
            "runner_up": (getattr(results[1]["player"], "full_name",
                                         "?") if len(results) > 1 else ""),
        }
        try:
            league.vezina_votes = votes
        except Exception:
            pass
        # News: the vote happened.
        try:
            self.add_news(
                f"Vezina Trophy vote: {votes[str(season_year)]['winner_name']} "
                f"wins the 5-3-1 ballot of {len(ballots)} GMs.")
        except Exception:
            pass

    def _update_player_reputations(self):
        """End-of-regular-season player reputation update.

        Runs once per season (guarded by _reputation_updated_for_season, since
        end_of_season can re-fire after the playoffs). Reads p.stats BEFORE
        league.end_of_season() wipes them -- do not move this call later in
        the season lifecycle.
        """
        if getattr(self, '_reputation_updated_for_season', None) == self.league.season_year:
            return
        try:
            import reputation_system as rs
        except ImportError:
            return
        all_players = [p for t in self.league.teams for p in t.roster]
        if not all_players:
            return
        # Map award display names -> reputation_system award keys
        awards = self._calculate_season_awards(all_players)
        award_key_map = {
            'Hart Trophy (MVP)': 'hart',
            'Ted Lindsay Award (Most Outstanding Player)': 'ted_lindsay',
            'Art Ross Trophy (Scoring Leader)': 'art_ross',
            'Maurice "Rocket" Richard Trophy': 'rocket',
            'Vezina Trophy (Best Goalie)': 'vezina',
            'Norris Trophy (Best Defenseman)': 'norris',
            'Selke Trophy (Defensive Forward)': 'selke',
            'Lady Byng Trophy (Sportsmanship)': 'lady_byng',
            'Calder Trophy (Rookie of the Year)': 'calder',
        }
        name_to_awards = {}
        for display, key in award_key_map.items():
            info = awards.get(display)
            if info and info.get('name'):
                name_to_awards.setdefault(info['name'], []).append(key)
        # League-average points per game (skaters only)
        skaters = [p for p in all_players
                   if 'GOALIE' not in getattr(getattr(p, 'primary_position', None), 'name', '')]
        total_pts = sum(getattr(getattr(p, 'stats', None), 'points', 0) or 0 for p in skaters)
        total_gp = sum(getattr(getattr(p, 'stats', None), 'games_played', 0) or 0 for p in skaters)
        league_avg_ppg = (total_pts / total_gp) if total_gp else 0.8
        for team in self.league.teams:
            for p in team.roster:
                pstats = getattr(p, 'stats', None)
                rs.update_player_reputation(
                    p,
                    season_points=getattr(pstats, 'points', 0) or 0,
                    games_played=getattr(pstats, 'games_played', 0) or 0,
                    league_avg_ppg=league_avg_ppg,
                    awards=name_to_awards.get(p.full_name, []),
                )
                # Trophy case: bank each season award onto the winner,
                # labeled by ceremony year (e.g. "2027" for the 2026-27
                # season). Idempotent -- re-runs never duplicate.
                for _akey in name_to_awards.get(p.full_name, []):
                    try:
                        import accolades as _acc
                        _acc.bank_accolade(
                            p, _akey,
                            str(getattr(self.league, "season_year", 0) + 1))
                    except Exception:
                        pass
                # Award bump: a player still on the development path
                # (age < 27) who wins a major award proves the ceiling was
                # wrong -- potential jumps one full letter grade (C+ -> B+).
                # One bump per season max, no matter how many trophies.
                _major = {'calder', 'conn_smythe', 'norris', 'rocket',
                          'art_ross', 'vezina', 'ted_lindsay'}
                _won = [a for a in name_to_awards.get(p.full_name, [])
                        if a in _major]
                # Conn Smythe is decided at Cup time, not in the regular-
                # season calculator -- check the bracket too.
                if 'conn_smythe' not in _won:
                    try:
                        _br = getattr(self, '_playoff_bracket', None)
                        _sn = getattr(_br, 'conn_smythe_name', None)
                        if _sn and _sn == p.full_name:
                            _won.append('conn_smythe')
                    except Exception:
                        pass
                if _won and getattr(p, 'age', 99) < 27:
                    try:
                        _bumped, _old, _new = p.bump_potential_full_grade()
                        if _bumped:
                            try:
                                _anames = {
                                    'calder': 'Calder Trophy',
                                    'conn_smythe': 'Conn Smythe Trophy',
                                    'norris': 'Norris Trophy',
                                    'rocket': 'Rocket Richard Trophy',
                                    'art_ross': 'Art Ross Trophy',
                                    'vezina': 'Vezina Trophy',
                                    'ted_lindsay': 'Ted Lindsay Award'}
                                _lbl = _anames.get(_won[0], 'major award')
                                self.add_news(
                                    f"🏆 {p.full_name} wins the {_lbl}! "
                                    f"Potential rises from {_old} to {_new}.")
                            except Exception:
                                pass
                    except Exception:
                        pass
        self._reputation_updated_for_season = self.league.season_year

    def _quick_sim_playoffs_headless(self):
        """Sim the entire playoff tournament without opening the window.

        Used when the user declines the interactive playoffs at season's
        end: every season still decides a Stanley Cup champion.
        """
        try:
            from playoff_system import PlayoffBracket
            league = getattr(self, 'league', None)
            if league is None:
                return
            bracket = getattr(league, 'playoff_bracket', None)
            try:
                _has = bracket is not None and any(
                    bracket.playoff_series.get(r)
                    for r in PlayoffBracket.ROUND_ORDER)
            except Exception:
                _has = False
            if not _has:
                bracket = PlayoffBracket(league)
                bracket.generate_playoff_bracket()
                try:
                    league.playoff_bracket = bracket
                except Exception:
                    pass
            for round_name in PlayoffBracket.ROUND_ORDER:
                try:
                    current = bracket.playoff_series.get(round_name) or []
                except Exception:
                    current = []
                for series in current:
                    while not getattr(series, 'is_complete', True):
                        bracket.simulate_playoff_game(series)
                bracket.advance_to_next_round(round_name)
            try:
                self._maybe_send_cup_recap()
            except Exception:
                pass
        except Exception:
            pass

    def _playoffs_complete(self) -> bool:
        """True once a Stanley Cup champion has been decided."""
        try:
            w = (getattr(self, 'open_windows', None) or {}).get('playoffs')
            if w is not None and w.winfo_exists():
                bracket = getattr(w, 'playoff_bracket', None)
                _lb = getattr(getattr(self, 'league', None),
                              'playoff_bracket', None)
                # BUG-REVIEW-002: the playoffs view is never torn down, so a
                # DECIDED bracket from a previous season can linger on it.
                # Only trust the view's bracket when it IS the league's live
                # bracket (identity is the invariant _generate_bracket
                # establishes); otherwise a stale view silently skips the
                # entire postseason.
                if (bracket is not None and bracket is _lb
                        and getattr(bracket, 'stanley_cup_champion', None)):
                    return True
            lb = getattr(getattr(self, 'league', None), 'playoff_bracket', None)
            if lb is not None and getattr(lb, 'stanley_cup_champion', None):
                return True
        except Exception:
            pass
        return False

    def _simulate_playoffs_headless(self):
        """Generate + simulate the playoff bracket without a GUI window.

        Headless fallback for the bulk-sim season-end path (playthrough
        B2, 2026-10-01). Mirrors PlayoffView._generate_bracket (bracket
        attached to the league, app set for date-aware sim paths) and the
        synchronous _run_games loop from _simulate_all_playoffs; the
        existing _playoffs_complete() then sees the league bracket's
        champion. Additive: the windowed path is untouched.
        """
        from playoff_system import PlayoffBracket
        league = getattr(self, "league", None)
        if league is None:
            return
        bracket = getattr(league, "playoff_bracket", None)
        if bracket is None or not getattr(bracket, "playoff_series", None):
            bracket = PlayoffBracket(league)
            try:
                bracket.app = self
            except Exception:
                pass
            bracket.generate_playoff_bracket()
            try:
                league.playoff_bracket = bracket
            except Exception:
                pass
        try:
            rounds = PlayoffBracket.ROUND_ORDER
        except Exception:
            rounds = ()
        for round_name in rounds:
            try:
                bracket.current_round = round_name
                for series in (bracket.playoff_series.get(round_name) or []):
                    # Guard against a game sim that keeps failing: cap
                    # attempts, then force-complete the series so the
                    # postseason can never stall the day loop.
                    _attempts = 0
                    while not series.is_complete and _attempts < 14:
                        _attempts += 1
                        try:
                            bracket.simulate_playoff_game(series)
                        except Exception as _e:
                            # Last-resort fallback: the full sim failed
                            # (e.g., a roster edge case). Award the game
                            # to the home team so the series progresses.
                            # Rare, logged, and better than a soft-lock.
                            try:
                                _home_is_t1 = (
                                    series.home_team_for_game(
                                        series.games_played + 1)
                                    is series.team1)
                                series.add_game_result(
                                    _home_is_t1,
                                    {"fallback": True,
                                     "reason": str(_e)[:120]})
                            except Exception:
                                break
                bracket.advance_to_next_round(round_name)
            except Exception:
                # Don't abort the entire postseason on a round error;
                # continue to the next round.
                continue
        try:
            import headlines
            headlines.drain_bracket_headlines(self, bracket)
        except Exception:
            pass

    def _show_season_summary(self):
        """Display end of season summary with stats and awards.
        Native: use _ui_notify instead of Tkinter popup (was crashing headless sims)."""
        try:
            season_str = f"{self.league.season_year}-{self.league.season_year + 1}"
            self._ui_notify("info", "Season Complete",
                f"{season_str} season has ended. Awards and summaries available in History.")
        except Exception:
            pass
    def open_playoffs_window(self):
        """Open the NHL Playoffs window (UI-safe: routes via _ui_notify)."""
        self._ui_notify('open_screen', screen='playoffs', title='Playoffs')
        return None

# === Multiplayer event handling (extracted from main.py) ===

# Bot #19: these were on HockeyManagerGUI; the native UI uses a

# bare GameManager, so they live here now. Tk dialogs converted

# to _ui_notify calls; the native UI layer implements them.



    def _apply_management_action(self, action, params, team, manager):
        """Dispatch a Phase-2 management action to its canonical handler."""
        handler = {
            "sign_free_agent": self._mp_sign_free_agent,
            "release_player": self._mp_release_player,
            "send_to_minors": self._mp_send_to_minors,
            "call_up": self._mp_call_up,
            "return_to_junior": self._mp_return_to_junior,
            "claim_waivers": self._mp_claim_waivers,
            "place_on_waivers": self._mp_place_on_waivers,
            "answer_ai_offer": self._mp_answer_ai_offer,
            "rfa_qualify": self._mp_rfa_qualify,
            "staff_renew": self._mp_staff_renew,
            "offer_sheet_match": self._mp_offer_sheet_match,
            "offer_sheet_trade_alt": self._mp_offer_sheet_trade_alt,
            "arbitration_walkaway": self._mp_arbitration_walkaway,
            "coach_checkin": self._mp_coach_checkin,
            "emergency_fill": self._mp_emergency_fill,
            "owner_meeting": self._mp_owner_meeting,
            "fantasy_draft_pick": self._mp_fantasy_draft_pick,
            "buyout_player": self._mp_buyout_player,
            "extend_contract": self._mp_extend_contract,
            "hire_staff": self._mp_hire_staff,
            "fire_staff": self._mp_fire_staff,
            "assign_scout": self._mp_assign_scout,
            "set_practice": self._mp_set_practice,
            "start_practice_plan": self._mp_start_practice_plan,
            "offer_sheet": self._mp_offer_sheet,
            "request_save": self._mp_request_save,
            "practice_session": self._mp_practice_session,
            "team_talk": self._mp_team_talk,
            "press_conference": self._mp_press_conference,
            "propose_trade": self._mp_propose_trade,
            "draft_pick": self._mp_draft_pick,
            "set_captaincy": self._mp_set_captaincy,
            "set_trade_block": self._mp_set_trade_block,
        }.get(action)
        if handler is None:
            return False, f"unsupported action: {action}"
        try:
            return handler(params, team, manager)
        except Exception as e:
            print(f"MP action {action} failed: {e}")
            return False, f"{action} failed: {e}"

    def _apply_morale_action(self, action, params, team):
        """Apply a client's morale/coaching-room intent to canonical state.

        Runs on the host's main thread. net_host already verified the client
        owns team_id; here we validate shapes/values and run the same
        reputation_system functions the host's own Morale window uses, so a
        remote GM gets identical behavior. Returns (ok, detail).
        """
        import reputation_system as rs
        coach = self._mp_head_coach(team)
        if coach is None:
            return False, "no head coach on staff"
        roster = list(getattr(team, "roster", []) or [])

        def _find_player(pid):
            for pl in roster:
                if str(getattr(pl, "id", "")) == str(pid):
                    return pl
            return None

        try:
            if action == "advise_coach":
                key = str(params.get("advice_type", ""))
                if key not in rs.ADVICE_TYPES:
                    return False, f"unknown advice: {key!r}"
                target = None
                if key == "feature_player":
                    target = _find_player(params.get("target_player_id"))
                    if target is None:
                        return False, "player not on your roster"
                out = rs.advise_coach(coach, key, team, roster,
                                      target_player=target)
            elif action == "unfeature_player":
                pl = _find_player(params.get("player_id"))
                if pl is None:
                    return False, "player not on your roster"
                out = rs.unfeature_player(coach, pl, team)
            elif action == "team_event":
                ev = str(params.get("event", ""))
                fn = {"bag_skate": rs.apply_bag_skate,
                      "inspiring_speech": rs.apply_inspiring_speech,
                      "great_practice": rs.apply_great_practice}.get(ev)
                if fn is None:
                    return False, f"unknown team event: {ev!r}"
                out = fn(team, coach, roster)
            elif action == "set_line_control":
                holder = str(params.get("holder", ""))
                if holder not in ("coach", "gm"):
                    return False, "holder must be coach or gm"
                approach = str(params.get("approach", "seize"))
                if approach not in ("discuss", "seize"):
                    return False, "approach must be discuss or seize"
                out = rs.set_line_control(team, holder,
                                          self._mp_team_context(team),
                                          roster, coach=coach,
                                          approach=approach)
            else:
                return False, f"unsupported action: {action}"
        except Exception as e:
            return False, f"action failed: {e}"
        text = out.get("text", "") if isinstance(out, dict) else ""
        return True, (text[:300] if text else "done")

    def _apply_multiplayer_action(self, action, params, manager):
        """Apply a client's management intent to the canonical state.

        Returns (ok, detail). Runs on the main thread, called from the
        host's event poll after net_host validated ownership/shape.

        Phase-2 scoping:
        * set_lines / set_tactics propagate: the host applies the client's
          lineup/tactics to the canonical team objects (validated, flattened
          like the SP editor) and they ride the next STATE_SYNC to the sim.
        * Roster/cap mutations (signings, trades, call-ups) are the
          Phase-1b game-logic surface: validated stubs below. Each real
          handler mutates the host's canonical objects and returns
          (True, summary) or (False, reason).
        """
        team_id = params.get("team_id", "")
        team = self._mp_find_team(team_id)
        if team is None:
            return False, f"unknown team: {team_id}"
        if action in ("set_lines", "set_tactics"):
            handler = {"set_lines": self._mp_set_lines,
                       "set_tactics": self._mp_set_tactics}[action]
            try:
                return handler(params, team, manager)
            except Exception as e:
                print(f"MP action {action} failed: {e}")
                return False, f"{action} failed: {e}"
        if action in ("advise_coach", "unfeature_player", "team_event",
                      "set_line_control"):
            return self._apply_morale_action(action, params, team)
        if action in ("declare_rivalry", "renounce_rivalry"):
            return self._apply_rivalry_action(action, params, team)
        if action in ("sign_free_agent", "propose_trade", "release_player",
                      "send_to_minors", "call_up", "claim_waivers",
                      "buyout_player", "extend_contract", "hire_staff",
                      "fire_staff", "assign_scout", "set_practice",
                      "team_talk", "press_conference", "draft_pick",
                      # Adversarial sweep 2026-10-05: these were in
                      # SUPPORTED_ACTIONS with working handlers + UI
                      # routes, but this gate dropped them as
                      # "unsupported". ntc_waiver_answer / trade_response
                      # stay out: they ride dedicated message types.
                      "set_captaincy", "set_trade_block",
                      "return_to_junior", "practice_session",
                      "start_practice_plan", "offer_sheet",
                      "request_save", "place_on_waivers",
                      "answer_ai_offer", "rfa_qualify", "staff_renew",
                      "offer_sheet_match", "offer_sheet_trade_alt",
                      "arbitration_walkaway", "coach_checkin",
                      "emergency_fill", "owner_meeting",
                      "fantasy_draft_pick"):
            # Phase 2: authoritative host execution of the full management
            # surface. Each handler validates every param against the
            # canonical Team objects and returns (True, summary) or
            # (False, reason); some return a (ok, detail, broadcast) triple
            # when the state didn't change (e.g. an offer that is merely
            # routed to another human needs no state broadcast).
            return self._apply_management_action(action, params, team,
                                                 manager)
        return False, f"unsupported action: {action}"

    def _apply_multiplayer_snapshot(self, save_bytes, label=""):
        """Replace local state with the host's snapshot (main thread).

        Native: Tk dashboard rebuild replaced by _ui_notify; the UI layer
        refreshes all views on "mp_state_synced".
        """
        import gzip
        import pickle
        try:
            data = pickle.loads(gzip.decompress(save_bytes))
        except Exception as e:
            print(f"Snapshot decode failed: {e}")
            self._mp_snapshot_failed(f"Could not decode the host's game "
                                     f"state ({e}). Make sure both sides run "
                                     f"the same build.")
            return
        try:
            self.save_manager._restore_game_state(data)
        except Exception as e:
            print(f"Snapshot restore failed: {e}")
            self._mp_snapshot_failed(f"Could not load the host's game "
                                     f"state ({e}). Make sure both sides run "
                                     f"the same build.")
            return
        try:
            _gm = getattr(self, "game_manager", None) or self
            self.league = _gm.league
            if hasattr(_gm, 'current_date'):
                self.current_date = _gm.current_date
            self._mp_spectator = False
            if self.mp_client is not None and getattr(self.mp_client, 'team_id', None):
                claimed = self._mp_find_team(self.mp_client.team_id)
                if claimed is not None:
                    _gm.user_team = claimed
                    self.user_team = claimed
            elif hasattr(_gm, 'user_team'):
                self.user_team = _gm.user_team
                if self.mp_client is not None:
                    self._mp_spectator = True
                    self._mp_toast(
                        "Spectating -- management actions are disabled.")
            try:
                self._update_team_colors()
            except Exception:
                pass
            if label:
                try:
                    self._rebuild_news_log_from_stories()
                except Exception:
                    pass
            self._mp_toast(f"Synced: {label}")
        except Exception as e:
            print(f"Snapshot view refresh failed (non-fatal): {e}")
        self._ui_notify("mp_state_synced", label)

    def _handle_client_event(self, kind, payload):
        if kind == "state_sync":
            self._apply_multiplayer_snapshot(
                payload.get("save_bytes", b""), payload.get("label", ""))
        elif kind == "day_advanced":
            # New cycle: everyone votes again.
            self._mp_client_ready = False
            self._mp_refresh_continue_ui()
            self._mp_toast(f"Day advanced: {payload.get('game_date', '')}")
        elif kind == "advance_status":
            self._mp_refresh_continue_ui(payload)
        elif kind == "trade_offer":
            self._mp_show_trade_offer(payload)
        elif kind == "ntc_waiver_request":
            self._mp_answer_ntc_request(payload)
        elif kind == "draft_clock":
            self._mp_show_draft_clock(payload)
        elif kind == "fantasy_draft_clock":
            self._mp_show_fantasy_clock(payload)
        elif kind == "draft_update":
            self._mp_on_draft_update(payload)
        elif kind == "action_ack":
            self._mp_toast(f"Accepted: {payload.get('action', '')} "
                            f"({payload.get('result', '')})")
        elif kind == "action_rejected":
            self._mp_toast(f"Rejected: {payload.get('action', '')} -- "
                            f"{payload.get('reason', '')}")
        elif kind == "checkpoint":
            self._mp_toast(f"Host checkpoint: {payload.get('label', '')}")
        elif kind == "chat":
            self._mp_toast(f"{payload.get('from', '?')}: {payload.get('text', '')}")
        elif kind == "error":
            self._mp_toast(f"Host: {payload.get('message', '')}")
        elif kind == "disconnected":
            # Non-modal (screen-shift rule): no blocking question. A
            # dismissible card offers promotion; the last-synced state
            # stays browsable either way.
            try:
                self._mp_last_host_port = int(
                    getattr(self.mp_client, "port", 0) or 0)
            except Exception:
                self._mp_last_host_port = 0
            _reason = payload.get("reason", "")
            self.mp_client = None  # stops the poll loop
            try:
                self._mp_show_promote_card(_reason)
            except Exception:
                pass

    def _handle_host_event(self, kind, payload):
        if kind == "action":
            # Never apply a client action while a snapshot worker is
            # serializing: defer until the "snapshot_done" event.
            if self.mp_host.snapshot_busy:
                self._mp_deferred_actions.append(payload)
                return
            res = self._apply_multiplayer_action(
                payload.get("action"), payload.get("params", {}),
                payload.get("manager", "?"))
            # Phase-2 handlers may return (ok, detail, broadcast): a routed
            # offer changes no state, so it needs no state broadcast.
            if isinstance(res, tuple) and len(res) == 3:
                ok, detail, broadcast = res
            else:
                ok, detail, broadcast = res[0], res[1], True
            try:
                self.mp_host.resolve_action(
                    payload.get("client_id"), payload.get("seq", 0),
                    bool(ok), str(detail),
                    broadcast=bool(broadcast))
            except Exception as e:
                print(f"resolve_action failed (non-fatal): {e}")
        elif kind == "snapshot_done":
            # Serialization finished: game objects are mutable again.
            # Replay any client actions that arrived mid-snapshot.
            deferred, self._mp_deferred_actions = \
                self._mp_deferred_actions, []
            for p in deferred:
                self._handle_host_event("action", p)
            # A ready gate that fired mid-snapshot gets its advance now.
            if getattr(self, '_mp_gate_pending', False):
                self._mp_gate_pending = False
                self._mp_evaluate_advance_gate("snapshot done")
        elif kind == "advance_changed":
            # A client readied/unreadied, claimed a team, or left: push the
            # fresh status and fire the advance if everyone is ready.
            self._mp_evaluate_advance_gate("readiness changed")
        elif kind == "trade_response":
            self._mp_resolve_trade_response(payload)
        elif kind == "ntc_waiver_answer":
            self._mp_resolve_ntc_answer(payload)
        elif kind == "team_claimed":
            team = self._mp_find_team(payload.get("team_id", ""))
            _gtok = str(payload.get("gm_token", "") or "")
            _gname = str(payload.get("name", "?") or "?")
            if team is not None:
                # A real person runs this club now: the AI must leave it
                # alone (parity with the local user's is_user_team).
                team.is_human_managed = True
                # GM persistence: stamp who runs this club. Saved with the
                # team so the seat survives host restarts -- the GM gets
                # their club back on rejoin.
                if _gtok:
                    try:
                        _lg = getattr(self, "league", None)
                        for _t in (getattr(_lg, "teams", None) or []):
                            if (_t is not team and
                                    getattr(_t, "mp_gm_token", "") == _gtok):
                                _t.mp_gm_token = ""
                                _t.mp_gm_name = ""
                    except Exception:
                        pass
                    team.mp_gm_token = _gtok
                    team.mp_gm_name = _gname
            self._mp_toast(
                f"{payload.get('name', '?')} "
                f"claimed {payload.get('team_id', '')}")
        elif kind == "manager_left":
            team = self._mp_find_team(payload.get("team_id", ""))
            if team is not None:
                # Nobody's driving: back to AI control.
                team.is_human_managed = False
            # Drop any waiver/trade flows owned by the departed manager --
            # their one-transaction waivers die with the negotiation.
            _left_team = payload.get("team_id", "")
            if _left_team:
                for _wid in [w for w, p in
                             self._mp_pending_ntc.items()
                             if p.get("team_id") == _left_team]:
                    self._mp_pending_ntc.pop(_wid, None)
                for _oid in [o for o, p in
                             self._mp_pending_offers.items()
                             if p.get("proposer_team_id") == _left_team
                             or p.get("partner_team_id") == _left_team]:
                    _prop = self._mp_pending_offers.pop(_oid, None)
                    if _prop:
                        self._mp_clear_proposal_waivers(_prop)
            self._mp_toast(
                f"{payload.get('name', '?')} left "
                f"({payload.get('reason', '')})")
        elif kind == "manager_joined":
            self._mp_toast(f"{payload.get('name', '?')} joined")
        elif kind == "chat":
            self._mp_toast(f"{payload.get('from', '?')}: {payload.get('text', '')}")

    def _mp_answer_ai_offer(self, params, team, manager):
        """Answer an AI club's inbox trade offer: accept executes the deal,
        decline walks away. Runs the canonical negotiation machinery with
        the acting team swapped in as user_team (so inbox delivery and
        message-done marking address the right club), then restores. The
        trade deadline is enforced -- no post-deadline accepts."""
        import trade_negotiation as tn
        neg_id = str(params.get("negotiation_id", "") or "")
        decision = str(params.get("decision", "") or "")
        if decision not in ("accept", "decline"):
            return False, "Unknown decision."
        neg = tn.get_negotiation(self, neg_id)
        if neg is None or not neg.is_open:
            return False, "That offer is no longer on the table."
        partner = tn.find_team(self, neg.partner_team_name)
        if partner is None:
            return False, "The other club is gone."
        # Ownership: the accepting team must hold the user side's assets.
        try:
            user_objs, missing_u = tn.resolve_assets(self, neg.user_assets)
        except Exception:
            user_objs, missing_u = [], ["?"]
        if missing_u:
            return False, "An asset changed clubs -- the offer is stale."
        try:
            import trade_engine as _te
            _roster_ids = {str(getattr(p, "id", ""))
                           for p in (getattr(team, "roster", None) or [])}
            _asset_ids = {str(getattr(a, "id", "")) for a in user_objs
                          if not _te._is_pick(a)}
            if not _asset_ids <= _roster_ids:
                return False, "That offer wasn't made to your club."
        except Exception:
            pass
        if decision == "accept":
            try:
                import trade_engine as te
                if not te.trades_allowed(
                        str(getattr(self, "current_date", "")),
                        getattr(self, "league", None)):
                    return False, "The trade deadline has passed."
            except Exception:
                pass
        _orig_ut = getattr(self, "user_team", None)
        _gm = getattr(self, "game_manager", None)
        _orig_gm_ut = getattr(_gm, "user_team", None) if _gm else None
        try:
            self.user_team = team
            if _gm is not None:
                _gm.user_team = team
            if decision == "accept":
                ok = tn.accept_negotiation(self, neg.id)
            else:
                ok = tn.decline_negotiation(self, neg.id)
        finally:
            self.user_team = _orig_ut
            if _gm is not None:
                _gm.user_team = _orig_gm_ut
        if decision == "decline":
            return True, "Walked away from the offer."
        return (True, "Deal accepted.") if ok else \
            (False, "The deal fell through -- see your inbox.")

    def _mp_answer_ntc_request(self, payload):
        """No-trade/no-movement waiver prompt: same choices as single-player
        (ask him / remove him / cancel for trades; ask him / keep him for
        waiver exposure).

        Native: route through _ui_notify; the UI layer shows the dialog
        and calls back via _mp_answer_ntc_request_choice.
        """
        self._ui_notify("mp_ntc_request", payload)

    def _mp_answer_ntc_request_choice(self, waiver_id, player_id, choice):
        """UI callback: send the player's NTC waiver answer to the host."""
        if choice not in ("ask", "remove", "cancel"):
            choice = "cancel"
        if self.mp_client is None:
            return
        try:
            self.mp_client.send_ntc_waiver_answer(
                player_id, choice, waiver_id=waiver_id)
        except Exception as e:
            self._mp_toast(f"Waiver answer failed: {e}")

    def _mp_apply_waiver_exposure(self, team, player):
        """The actual wire exposure (runs after any NMC consent)."""
        try:
            player.on_waivers = True
            player.waiver_days = 2
            _wl = getattr(self, "waiver_list", None)
            if isinstance(_wl, list) and player not in _wl:
                _wl.append(player)
            self.add_news(f"{player.full_name} placed on waivers "
                          f"by {team.team_name}.")
        except Exception as e:
            return False, f"Waiver placement failed: {e}"
        return True, (f"{player.full_name} placed on waivers -- exposed "
                      f"for 2 days.")

    def _mp_arbitration_walkaway(self, params, team, manager):
        """Walk away from an arbitration award (48h) or accept it."""
        import rfa_system as _rfa
        walk_away = bool(params.get("walk_away", False))
        msg = self._mp_find_inbox_msg(team, params.get("message_id", ""))
        data = (getattr(msg, "action_data", None) or {}) if msg else {}
        pid = params.get("player_id") or data.get("player_id")
        if not walk_away:
            # Accept: sign at the awarded terms (mirrors the SP path,
            # which mutates the acting club's player, not user_team's).
            try:
                aav = int(data.get("award_aav", 0) or 0)
                term = int(data.get("term_years", 1) or 1)
                person = next(
                    (p for p in (getattr(team, "roster", None) or [])
                     if str(getattr(p, "id", "")) == str(pid)), None)
                if person is not None:
                    c = getattr(person, "contract", None)
                    if c is not None:
                        c.salary = aav
                        c.years_remaining = term
            except Exception:
                pass
        with self._mp_swapped_user_team(team):
            try:
                res = _rfa.apply_walk_away(
                    self, self.league, team, pid, walk_away)
            except Exception as e:
                return False, f"Arbitration decision failed: {e}"
        if (res or {}).get("ok"):
            self._mp_force_inbox_done(team, params.get("message_id", ""))
        return (True, "Walked away from the award." if walk_away else
                "Award accepted.") if (res or {}).get("ok") else \
            (False, str((res or {}).get("reason", "decision failed")))

    def _mp_assign_scout(self, params, team, manager):
        """Assign a scout to a region: same storage the scouting screen
        writes (game_manager.scout_region_assignments, keyed by scout)."""
        sid = str(params.get("scout_id", "") or "")
        region = params.get("region")
        scout = None
        try:
            import scouting as _sc
        except Exception:
            return False, "Scouting isn't available."
        for s in getattr(team, "staff", None) or []:
            if str(getattr(s, "id", "")) == sid and _sc.is_scout(s):
                scout = s
                break
        if scout is None:
            return False, "That scout isn't on your staff."
        if region is not None:
            # Regions are free-form names; only reject an empty string,
            # never a real region name.
            region = str(region).strip() or None
        try:
            _sc.set_scout_region(
                getattr(self, "game_manager", self), scout, region)
        except Exception as e:
            return False, f"Assignment failed: {e}"
        name = getattr(scout, "name", getattr(scout, "full_name", "scout"))
        return True, (f"{name} assigned to {region}."
                      if region else f"{name} recalled from assignment.")

    def _mp_begin_consent_flow(self, team, player, manager, kind="demote"):
        """Host-side NMC consent: stash the intent, ask the client's player
        via NTC_WAIVER_REQUEST (context="waivers"). kind="demote" runs the
        waiver-assignment on grant; kind="expose" only exposes him to the
        wire. Returns (True, status, no-broadcast) -- the mutation itself
        runs when the answer comes back in _mp_resolve_ntc_answer."""
        import uuid as _uuid
        waiver_id = _uuid.uuid4().hex[:10]
        session_id = self._mp_peer_session_for_team(team.team_name)
        if session_id is None:
            return False, "Could not reach your client."
        try:
            import trade_engine as te
            _kind, detail = te.clause_of(player) or ("NMC", "no-movement")
        except Exception:
            detail = "no-movement clause"
        self._mp_pending_ntc[waiver_id] = {
            "kind": kind,
            "team_id": team.team_name,
            "manager": manager,
            "player_id": str(getattr(player, "id", "")),
            "player_name": getattr(player, "full_name", "player"),
            "clause": detail,
        }
        try:
            self.mp_host.send_ntc_waiver_request(
                session_id, waiver_id, str(getattr(player, "id", "")),
                getattr(player, "full_name", "player"), detail,
                "the waiver wire", "waivers")
        except Exception:
            self._mp_pending_ntc.pop(waiver_id, None)
            return False, "Could not reach your client."
        return (True,
                f"{getattr(player, 'full_name', 'He')} has a no-movement "
                f"clause -- waiting on his answer.",
                False)

    def _mp_buyout_player(self, params, team, manager):
        """Buy out a contract: same cap-hit schedule the buyout view
        writes (team.buyout_cap_hits), player becomes a free agent."""
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        # Note: no NMC check here -- matches single-player, where buyouts
        # don't require the player's consent (only waivers/assignment do).
        try:
            import windows as _w
            # Tuple like the single-player view unpacks it:
            # (total_cost, annual_hit, buyout_years, rows).
            _total, annual, byears, rows = _w.buyout_schedule(player)
        except Exception as e:
            return False, f"Buyout failed: {e}"
        annual = int(annual or 0)
        byears = int(byears or 0)
        if not rows:
            return False, "Buyout schedule came back empty."
        try:
            season = int(getattr(getattr(self, "league", None),
                                 "season_year", 2026))
        except Exception:
            season = 2026
        hits = getattr(team, "buyout_cap_hits", None)
        if hits is None:
            hits = {}
            team.buyout_cap_hits = hits
        for _i, _hit, _s in rows:
            yr = season + int(_i) - 1
            hits[yr] = hits.get(yr, 0) + int(_hit)
        team.remove_player(player)
        try:
            fa_pool = self.free_agents()
            if fa_pool is None:
                fa_pool = []
            if player not in fa_pool:
                fa_pool.append(player)
        except Exception:
            pass
        try:
            self.add_news(
                f"{player.full_name} bought out by {team.team_name} "
                f"(dead cap ${annual:,}/yr x {byears}).")
        except Exception:
            pass
        return True, (f"Bought out {player.full_name} "
                      f"(dead cap ${annual:,}/yr x {byears}y).")

    def _mp_call_up(self, params, team, manager):
        """Recall from the AHL: mirrors the waivers-view claim checks."""
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        if player not in (getattr(team, "ahl_roster", None) or []):
            return False, "That player isn't in the minors."
        # New-CBA paper-transaction rule (same as single-player): a
        # freshly assigned player must play at least one AHL game before
        # he can be recalled.
        try:
            import ahl_system as _ahl_gate_mp
            _block = _ahl_gate_mp.ahl_recall_block_reason(player)
        except Exception:
            _block = None
        if _block:
            return False, _block
        if len(getattr(team, "roster", []) or []) >= 23:
            return False, "Roster is full (23)."
        salary = int(getattr(getattr(player, "contract", None),
                             "salary", 0) or 0)
        if salary > self._mp_cap_room(team):
            return False, "Not enough cap space to recall him."
        team.ahl_roster.remove(player)
        team.roster.append(player)
        # Dressing room: first-time NHL arrival only (guarded inside).
        try:
            import dressing_room as _dr_arr
            _dr_arr.cascade_on_arrival(
                team, player, how="callup",
                date_str=str(getattr(self, "current_date", "")))
        except Exception:
            pass
        try:
            self.add_news(f"{player.full_name} recalled by {team.team_name}.")
        except Exception:
            pass
        return True, f"Recalled {player.full_name}."

    def _mp_cap_room(self, team):
        # Central cap accounting (waiver shed, retention, burial, dead
        # cap) -- the same number team.cap_space now reports and the
        # league office enforces.
        try:
            _cap_sys = getattr(getattr(self, 'league', None),
                               'salary_cap_system', None)
            _live_cap = _cap_sys.current_cap if _cap_sys else SALARY_CAP
            from salary_cap_system import total_cap_charge as _tcc
            return max(0, int(_live_cap) - int(_tcc(team)))
        except Exception:
            try:
                return int(getattr(team, "cap_space", 0) or 0)
            except Exception:
                return 0

    def _mp_claim_waivers(self, params, team, manager):
        """Claim off waivers: queue the claim exactly like the SP wire tab.

        The claim is NOT granted instantly -- it is processed at noon in
        waiver priority order by process_waivers(), so a higher-priority
        club (human or AI) that also wants him gets him first. Pending
        claims are tracked per team (mp_claim_teams) so every human GM's
        claim is independent.
        """
        pid = str(params.get("player_id", "") or "")
        player = None
        try:
            for p in self.waiver_list or []:
                if str(getattr(p, "id", "")) == pid:
                    player = p
                    break
        except Exception:
            pass
        if player is None:
            return False, "That player isn't on waivers."
        if getattr(player, "team_name", "") == team.team_name:
            return False, "You can't claim your own player."
        if len(getattr(team, "roster", []) or []) >= 23:
            return False, "Roster is full (23)."
        salary = int(getattr(getattr(player, "contract", None),
                             "salary", 0) or 0)
        if salary > self._mp_cap_room(team):
            return False, "Not enough cap space to claim him."
        pending = getattr(player, "mp_claim_teams", None)
        if not isinstance(pending, list):
            pending = []
            try:
                player.mp_claim_teams = pending
            except Exception:
                pass
        if team.team_name in pending:
            return False, (f"You already have a pending claim on "
                           f"{player.full_name}.")
        pending.append(team.team_name)
        try:
            self.add_news(
                f"{team.team_name} submitted a waiver claim for "
                f"{player.full_name}.")
        except Exception:
            pass
        return True, (f"Claim submitted for {player.full_name} -- processed "
                      f"at noon in waiver priority order.")

    def _mp_clear_proposal_waivers(self, proposal):
        """A dead deal spends nothing: clear one-transaction waivers."""
        for pid in proposal.get("players_out", []) or []:
            for tid in (proposal.get("proposer_team_id"),
                        proposal.get("partner_team_id")):
                team = self._mp_find_team(tid or "")
                p = self._mp_team_player(team, pid) if team else None
                if p is not None:
                    try:
                        p.contract.ntc_waiver_for = ""
                    except Exception:
                        pass

    def _mp_coach_checkin(self, params, team, manager):
        """Complete a quarterly coach check-in: same complete_checkin()
        the conversation UI calls -- trust deltas land on the canonical
        mandate history."""
        try:
            import coach_checkins as _cc
        except Exception:
            return False, "Coach check-ins aren't available."
        fields = params.get("fields", None)
        if not isinstance(fields, dict):
            return False, "Malformed check-in."
        # Plain-data only: notes/framing strings, no live objects.
        _clean = {}
        for k in ("notes", "expectation_framing", "room_framing",
                  "rookie_framing", "tactics_framing"):
            v = fields.get(k)
            if isinstance(v, str):
                _clean[k] = v[:2000]
            elif isinstance(v, list):
                _clean[k] = [str(x)[:500] for x in v[:50]]
        try:
            _entry = _cc.complete_checkin(
                team, _clean, apply_trust=True, per_beat_applied=True)
        except Exception as e:
            return False, f"Check-in failed: {e}"
        return True, "Check-in recorded."

    def _mp_continue_waiver_flow(self, waiver_id, pend, _drop):
        """Advance a waiver flow: next prompt, or route the offer when the
        last veto is cleared."""
        session_id = self._mp_peer_session_for_team(pend["team_id"])
        if not session_id:
            _drop("lost connection to proposer")
            return
        res = self._mp_send_next_waiver(waiver_id, session_id)
        # _mp_send_next_waiver either queued the next prompt (True, …)
        # or routed the finished offer; a routing failure kills the flow.
        ok = res[0] if isinstance(res, tuple) else False
        if not ok:
            detail = res[1] if isinstance(res, tuple) and len(res) > 1 \
                else "routing failed"
            _drop(detail)

    def _mp_demote_player(self, team, player):
        """The actual demotion (runs after any NMC consent).

        Mirrors the single-player rulebook exactly: waiver-exempt
        players (under 25 and under 160 NHL games) are assigned quietly
        to the AHL; everyone else must clear the wire. The client's word
        is never trusted -- eligibility is computed host-side.
        """
        # R1 (roster limits): same dressed-minimum rule as single-player.
        try:
            import roster_limits as _rl
            if _rl.would_break_dress_minimum(team, [player]):
                return False, ("Demoting him would leave the club unable to "
                               "dress a legal lineup (18 skaters + 2 "
                               "goalies).")
        except Exception:
            pass
        try:
            _needs = _player_needs_waivers(player)
        except Exception:
            _needs = True
        if not _needs:
            # Exempt: quiet demotion, same as single-player.
            try:
                (getattr(team, "roster", None) or []).remove(player)
            except Exception:
                pass
            try:
                _ahl = getattr(team, "ahl_roster", None)
                if _ahl is None:
                    _ahl = []
                    try:
                        team.ahl_roster = _ahl
                    except Exception:
                        pass
                if player not in _ahl:
                    _ahl.append(player)
            except Exception:
                pass
            # New-CBA paper-transaction rule: he must play an AHL game
            # before he can be recalled.
            try:
                import ahl_system as _ahl_stamp_mp
                _ahl_stamp_mp.stamp_ahl_assignment(player)
            except Exception:
                pass
            # Audition over -- the next call-up starts a fresh one.
            try:
                player.nhl_audition = None
            except Exception:
                pass
            try:
                self.add_news(f"{player.full_name} assigned to the AHL by "
                              f"{team.team_name}.")
            except Exception:
                pass
            return True, (f"{player.full_name} assigned to the AHL "
                          f"(waiver-exempt).")
        player.on_waivers = True
        player.waiver_days = 2
        try:
            if player not in self.waiver_list:
                self.waiver_list.append(player)
        except Exception:
            pass
        try:
            self.add_news(f"{player.full_name} placed on waivers by "
                          f"{team.team_name}.")
        except Exception:
            pass
        return True, f"{player.full_name} placed on waivers."

    def _mp_draft_pick(self, params, team, manager):
        """Answer the draft clock: validate the prospect is still
        available; the DraftView's wait loop executes the pick on the
        main thread."""
        st = getattr(self, "_mp_draft_clock", None)
        if not st or st.get("done"):
            return False, "No pick is waiting on you.", True
        if st.get("team_id") != team.team_name:
            return False, "It's not your pick.", True
        pid = str(params.get("player_id", "") or "")
        if str(params.get("clock_id", "") or "") \
                and params.get("clock_id") != st.get("clock_id"):
            return False, "That clock expired -- wait for the next one.", \
                True
        # Double-submit guard: the first registered pick is final. A
        # retry/dupe arriving after the pick is locked must not overwrite
        # it (adversarial sweep 2026-10-05).
        if st.get("pick_id"):
            return False, "Your pick is already registered.", True
        prospect = None
        try:
            for p in getattr(getattr(self, "league", None),
                             "draft_prospects", None) or []:
                if str(getattr(p, "id", "")) == pid:
                    prospect = p
                    break
        except Exception:
            pass
        if prospect is None:
            return False, "That prospect is already drafted.", True
        st["pick_id"] = pid
        return True, \
            f"Pick registered: {getattr(prospect, 'full_name', '?')}.", False

    def _mp_draft_pick_window(self, *, title, players, board, my_team_id,
                              clock_id, action_name, answer_attr,
                              expire_toast, draft_button_text,
                              extra_columns=()):
        """Shared pick UI for MP draft clocks.

        Native: route through _ui_notify; the UI layer shows the picker
        and calls back via _mp_answer_draft_clock.
        """
        setattr(self, answer_attr,
                {"clock_id": clock_id, "answered": False})
        self._ui_notify("mp_draft_clock", {
            "title": title,
            "players": players,
            "board": board or [],
            "my_team_id": my_team_id,
            "clock_id": clock_id,
            "action_name": action_name,
            "answer_attr": answer_attr,
            "expire_toast": expire_toast,
            "draft_button_text": draft_button_text,
        })

    def _mp_answer_draft_clock(self, clock_id, action_name, answer_attr,
                               team_id, player_id):
        """UI callback: send a draft pick answer to the host."""
        guard = getattr(self, answer_attr, None) or {}
        if guard.get("answered"):
            return
        if guard.get("clock_id") != clock_id:
            return
        guard["answered"] = True
        if self.mp_client is None:
            return
        try:
            self.mp_client.send_action(action_name, {
                "team_id": team_id,
                "clock_id": clock_id,
                "player_id": player_id,
            })
        except Exception as e:
            self._mp_toast(f"Draft pick failed: {e}")

    def _mp_emergency_fill(self, params, team, manager):
        """Summon emergency fill-ins: the host computes the shortfall on
        canonical state and assigns league fillers (same as SP)."""
        try:
            import roster_limits as _rl
        except Exception:
            return False, "Roster limits aren't available."
        try:
            sk, go = _rl.lineup_shortfall(team)
        except Exception:
            sk, go = 0, 0
        if sk <= 0 and go <= 0:
            return True, "No fill-ins needed -- you can dress a legal lineup."
        try:
            summoned = _rl.summon_emergency_fillers(team)
        except Exception as e:
            return False, f"Summon failed: {e}"
        n = len(summoned or [])
        return True, (f"League office assigned {n} emergency fill-in(s) "
                      f"so you can ice a legal lineup.")

    def _mp_evaluate_advance_gate(self, why=""):
        """Broadcast ADVANCE_STATUS; fire the day's advance when all active
        managers (host included) are ready. Main thread only."""
        host = getattr(self, 'mp_host', None)
        if host is None:
            return
        if host.snapshot_busy:
            # A snapshot worker is serializing: nobody may mutate game
            # objects. Re-evaluate when it finishes (snapshot_done).
            self._mp_gate_pending = True
            try:
                host.broadcast_advance_status(self._mp_host_ready)
            except Exception:
                pass
            self._mp_refresh_continue_ui()
            return
        try:
            payload = host.broadcast_advance_status(self._mp_host_ready)
        except Exception as e:
            print(f"Advance gate broadcast failed (non-fatal): {e}")
            return
        self._mp_refresh_continue_ui(payload)
        if payload.get("all_ready"):
            self._mp_fire_authorized_advance()

    def _mp_execute_mp_trade(self, proposal):
        """Run a fully-cleared proposal through the canonical trade
        engine: clause preflight, cap validation, retention, asset moves."""
        import trade_engine as te
        # Event boundary: a deal proposed before the freeze but accepted
        # after it must still die here -- same as the SP deadline center.
        try:
            if not te.trades_allowed(str(getattr(self, "current_date", "")),
                                     getattr(self, "league", None)):
                self._mp_clear_proposal_waivers(proposal)
                return False, ("Trading is frozen right now "
                               "(trade freeze / deadline).")
        except Exception:
            pass
        team = self._mp_find_team(proposal["proposer_team_id"])
        partner = self._mp_find_team(proposal["partner_team_id"])
        if team is None or partner is None:
            return False, "A club involved is gone."
        out_players = proposal.get("_out_players") or [
            self._mp_team_player(team, pid)
            for pid in proposal["players_out"]]
        in_players = proposal.get("_in_players") or [
            self._mp_team_player(partner, pid)
            for pid in proposal["players_in"]]
        out_picks = proposal.get("_out_picks") or [
            self._mp_team_pick(team, kid) for kid in proposal["picks_out"]]
        in_picks = proposal.get("_in_picks") or [
            self._mp_team_pick(partner, kid) for kid in proposal["picks_in"]]
        if any(p is None for p in out_players + in_players) or \
                any(k is None for k in out_picks + in_picks):
            self._mp_clear_proposal_waivers(proposal)
            return False, "An asset changed clubs -- re-propose."
        # Pick protection rides on the pick objects themselves.
        for kid, prot in (proposal.get("pick_protection") or {}).items():
            for k in out_picks:
                if str(getattr(k, "id", "")) == str(kid):
                    try:
                        k.protection = prot
                    except Exception:
                        pass
        retention = {}
        for pid, pct in (proposal.get("retention") or {}).items():
            for p in out_players:
                if str(getattr(p, "id", "")) == str(pid):
                    retention[str(getattr(p, "id", ""))] = float(pct)
        try:
            date_str = str(getattr(self, "current_date", ""))
        except Exception:
            date_str = ""
        try:
            result = te.execute_trade(
                team, partner, out_players + out_picks,
                in_players + in_picks, date_str=date_str,
                league=getattr(self, "league", None),
                board=getattr(self, "board", None),
                retention=retention or None)
        except Exception as e:
            self._mp_clear_proposal_waivers(proposal)
            return False, f"Trade engine refused: {e}"
        if isinstance(result, str) and result.startswith("BLOCKED"):
            self._mp_clear_proposal_waivers(proposal)
            reason = result[len("BLOCKED:"):].strip() or "league office veto"
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {team.team_name} <-> {partner.team_name} "
                    f"BLOCKED: {reason}")
            except Exception:
                pass
            return False, f"League office blocked it: {reason}"
        try:
            self.mp_host.broadcast_chat(
                f"TRADE: {team.team_name} <-> {partner.team_name} -- "
                f"{len(out_players)} players, {len(out_picks)} picks "
                f"each way. Done deal.")
        except Exception:
            pass
        return True, "Trade completed."

    def _mp_extend_contract(self, params, team, manager):
        """Extend / renegotiate a roster player's deal, clauses included."""
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        try:
            salary = int(params.get("salary", 0))
            years = int(params.get("years", 0))
        except (TypeError, ValueError):
            return False, "Invalid contract terms."
        contract = getattr(player, "contract", None)
        if contract is None:
            return False, "That player has no contract to extend."
        # Extensions are a final-year privilege, same as single-player:
        # no mid-deal renegotiations.
        try:
            _yrs_left = int(getattr(contract, "years_remaining", 1) or 1)
        except Exception:
            _yrs_left = 1
        if _yrs_left > 1:
            return False, (f"{player.full_name} has {_yrs_left} years left -- "
                           f"extensions are for the final year of a deal.")
        # Shared gates: league minimum, 20%-of-cap max, 8-year max for
        # extensions, live-cap budget for the raise.
        ok, err = self._validate_contract_terms(player, salary, years,
                                                extension=True, team=team)
        if not ok:
            return False, err
        old_salary = int(getattr(contract, "salary", 0) or 0)
        if salary - old_salary > self._mp_cap_room(team):
            return False, "Not enough cap space for that raise."
        kind = str(params.get("clause", "none") or "none").lower()
        if kind not in ("none", "ntc", "nmc", "mntc"):
            return False, f"Unknown clause: {params.get('clause')}"
        # Clear, then re-stamp: apply_clause_to_contract enforces the real
        # UFA-eligibility bar (a 23-year-old can't take an NMC).
        try:
            contract.no_trade_clause = False
            contract.no_movement_clause = False
            contract.modified_ntc_teams = 0
        except Exception:
            pass
        if kind != "none":
            try:
                import trade_engine as te
                list_size = 10
                try:
                    list_size = int(params.get("clause_teams", 10) or 10)
                except (TypeError, ValueError):
                    pass
                if not te.apply_clause_to_contract(
                        contract, kind, list_size=list_size, player=player):
                    return False, (
                        f"{player.full_name} isn't eligible for that clause.")
            except Exception as e:
                return False, f"Clause failed: {e}"
        contract.salary = salary
        contract.years_remaining = years
        try:
            contract.ntc_waiver_for = ""
        except Exception:
            pass
        # A new SPC starts with no retained salary: the old deal's discount
        # and two-club history die with it (the retaining club's ledger
        # entry survives independently, per CBA).
        try:
            import trade_engine as _te_clr2
            _te_clr2.clear_retention_state(player)
        except Exception:
            pass
        try:
            self.add_news(
                f"{player.full_name} extended by {team.team_name}: "
                f"{years} years at ${salary:,}/year"
                + (f" ({kind.upper()})" if kind != "none" else "") + ".")
        except Exception:
            pass
        return True, (f"Extended {player.full_name} "
                      f"({years}y, ${salary:,}/yr"
                      f"{', ' + kind.upper() if kind != 'none' else ''}).")

    def _mp_fantasy_draft_pick(self, params, team, manager):
        """Client's live fantasy-draft pick: validate the clock, the turn,
        and availability, then commit and resume the draft."""
        import uuid as _uuid  # noqa (kept for symmetry; unused)
        dm = getattr(self, "_mp_fantasy_dm", None)
        st = getattr(self, "_mp_fantasy_clock", None)
        if dm is None or st is None or st.get("done"):
            return False, "No fantasy pick is waiting on you."
        if str(params.get("clock_id", "") or "") != str(
                st.get("clock_id", "")):
            return False, "Stale draft clock."
        if getattr(team, "team_name", "") != st.get("team_name", ""):
            return False, "It's not your club's pick."
        pick = dm.get_current_pick()
        if pick is None or getattr(
                getattr(pick, "team", None), "team_name", "") != \
                st.get("team_name", ""):
            return False, "The draft moved on."
        pid = str(params.get("player_id", "") or "")
        try:
            available = {str(getattr(p, "id", "")): p
                         for p in (dm.get_available_players() or [])}
        except Exception:
            available = {}
        player = available.get(pid)
        if player is None:
            return False, "That player is already drafted."
        st["done"] = True
        try:
            ok = dm.make_pick(player)
        except Exception as e:
            return False, f"Pick failed: {e}"
        if not ok:
            return False, "Pick didn't commit."
        try:
            dm.assign_drafted_player(pick.team, player)
        except Exception:
            pass
        try:
            if getattr(self, "mp_host", None) is not None:
                self.mp_host.broadcast_draft_update(
                    "fantasy", int(st.get("overall", 0) or 0),
                    int(dm.get_current_round() or 0) if hasattr(
                        dm, "get_current_round") else 0,
                    str(getattr(getattr(pick, "team", None),
                                "team_name", "") or ""),
                    str(getattr(player, "full_name", "?") or "?"))
        except Exception:
            pass
        view = getattr(self, "_mp_fantasy_view", None)
        if view is not None:
            try:
                view.after(200, view.continue_auto_draft)
            except Exception:
                pass
        return True, (f"Drafted {getattr(player, 'full_name', '?')} "
                      f"(#{st.get('overall', '?')}).")

    def _mp_find_free_agent(self, player_id):
        pid = str(player_id or "")
        try:
            for p in self.free_agents() or []:
                if str(getattr(p, "id", "")) == pid:
                    return p
        except Exception:
            pass
        return None

    def _mp_find_inbox_msg(self, team, message_id):
        """Find a message by id in the team's canonical inbox."""
        try:
            msgs = getattr(getattr(team, "inbox", None),
                           "messages", None) or []
            return next((m for m in msgs
                         if str(getattr(m, "id", ""))
                         == str(message_id or "")), None)
        except Exception:
            return None

    def _mp_fire_authorized_advance(self):
        """Run the real day advance exactly once, through the normal
        simulate_day() path (blockers still apply)."""
        self._mp_advance_authorized = True
        # Detect whether the advance was actually consumed: a normal day
        # moves current_date; a deadline-day tick moves the trade-deadline
        # clock instead (no announce_day there). A blocker refuses both --
        # in that case every manager's vote stands and the cycle is NOT
        # reset (the host just re-readies once the blocker clears).
        _before_date = getattr(self, 'current_date', None)
        try:
            _before_clock = dict(
                getattr(getattr(self, 'game_manager', None),
                        'deadline_clock', None) or {})
        except Exception:
            _before_clock = {}
        try:
            self.simulate_day()
        finally:
            self._mp_advance_authorized = False
            try:
                _after_clock = dict(
                    getattr(getattr(self, 'game_manager', None),
                            'deadline_clock', None) or {})
            except Exception:
                _after_clock = {}
            _consumed = (getattr(self, 'current_date', None) != _before_date
                         or _after_clock != _before_clock)
            # New cycle: everyone must ready up again for the next advance.
            self._mp_host_ready = False
            self._mp_gate_pending = False
            if _consumed:
                # The host's per-client ready set must reset here too --
                # deadline 30-minute ticks never reach announce_day(), so
                # without this a client's old vote would linger and the
                # next tick could fire on the host's vote alone.
                try:
                    self.mp_host.reset_advance_cycle()
                except Exception:
                    pass
            try:
                payload = self.mp_host.broadcast_advance_status(False)
            except Exception:
                payload = None
            self._mp_refresh_continue_ui(payload)

    def _mp_fire_staff(self, params, team, manager):
        """Release a staffer back to the pool: mirrors release_staff()."""
        sid = str(params.get("staff_id", "") or "")
        staffer = None
        for s in getattr(team, "staff", None) or []:
            if str(getattr(s, "id", "")) == sid:
                staffer = s
                break
        if staffer is None:
            return False, "That staffer isn't on your club."
        # P15: same firing mechanic as release_staff -- severance +
        # trust shock, never free.
        try:
            from game_classes import process_staff_severance
            process_staff_severance(team, staffer)
        except Exception:
            pass
        try:
            team.staff.remove(staffer)
        except Exception:
            pass
        try:
            pool = getattr(getattr(self, "league", None),
                           "free_agent_staff", None)
            if pool is not None and staffer not in pool:
                pool.append(staffer)
        except Exception:
            pass
        try:
            import analytics_scouting as _as
            _as.refresh_analytics_quality(team)
        except Exception:
            pass
        name = getattr(staffer, "name",
                       getattr(staffer, "full_name", "staffer"))
        return True, f"Released {name}."

    def _mp_force_inbox_done(self, team, message_id):
        """Mark a single-decision inbox message done (offer sheets,
        trade alts, arbitration -- one answer closes the message)."""
        try:
            msg = self._mp_find_inbox_msg(team, message_id)
            if msg is not None:
                msg.action_done = True
        except Exception:
            pass

    def _mp_hire_staff(self, params, team, manager):
        """Hire staff: mirrors sign_free_agent_staff() but against the
        client's club. Resolves all three market sources (free agents,
        overseas coaches, rival AHL staff) and enforces the same approach
        rules and staff-budget gate as single-player."""
        sid = str(params.get("staff_id", "") or "")
        staffer = None
        source = None       # 'free_agent' | 'overseas' | 'ahl_poach'
        employer = None
        try:
            league = getattr(self, "league", None)
            for s in getattr(league, "free_agent_staff", None) or []:
                if str(getattr(s, "id", "")) == sid:
                    staffer, source = s, "free_agent"
                    break
            if staffer is None:
                for s in getattr(league, "overseas_staff", None) or []:
                    if str(getattr(s, "id", "")) == sid:
                        staffer, source = s, "overseas"
                        break
            if staffer is None:
                for t in getattr(league, "teams", None) or []:
                    if t is team:
                        continue
                    for s in getattr(t, "staff", None) or []:
                        if (str(getattr(s, "id", "")) == sid
                                and (getattr(s, "assignment", "nhl")
                                     or "nhl") == "ahl"):
                            staffer, source, employer = s, "ahl_poach", t
                            break
                    if staffer is not None:
                        break
        except Exception:
            pass
        if staffer is None:
            return False, "That staffer isn't available."
        # Approach rules (real rules): rival AHL coaches are only
        # approachable in the offseason; rival NHL staff never.
        if source != "free_agent":
            try:
                from game_classes import can_approach_staff as _approach
                ok, reason = _approach(
                    staffer, employer, team,
                    getattr(self, "current_date", None))
                if not ok:
                    return False, reason or "That staffer can't be approached."
            except Exception:
                pass
        try:
            salary = int(params.get("salary", 0))
            years = int(params.get("years", 0))
        except (TypeError, ValueError):
            return False, "Invalid contract terms."
        if salary <= 0 or not 1 <= years <= 5:
            return False, "Invalid contract terms."
        try:
            from game_classes import team_can_afford_staff as _mp_afford
            if not _mp_afford(team, salary):
                return False, ("That offer exceeds your club's available "
                                "staff budget.")
        except Exception:
            pass
        # SP parity: the staffer can decline the offer. Same acceptance
        # chance the staff view shows (offer vs market ask, club prestige,
        # GM stature) -- the roll happens BEFORE any mutation, exactly as
        # the SP view rolls before sign_free_agent_staff().
        try:
            import random as _r
            from game_classes import staff_market_ask as _sask, \
                to_100_scale as _t100
            _askv = _sask(staffer)
            _mult = salary / max(1, _askv)
            _rating = _t100(staffer.overall_rating)
            _prestige = getattr(team, 'prestige', 50)
            _base = (0.45 + (_mult - 1.0) * 1.4 + (_prestige - 50) / 400
                     - (_rating - 60) / 600)
            try:
                import reputation_system as _rs
                _base += _rs.gm_staff_accept_delta(team)
            except Exception:
                pass
            _chance = max(0.05, min(0.98, _base))
            if _r.random() >= _chance:
                return False, (
                    f"{getattr(staffer, 'full_name', 'Staffer')} declined "
                    f"your offer.")
        except Exception:
            pass
        # Join the new club first; only leave the old source after the
        # hire has landed, so a failure can't strand the staffer.
        # Terms are stamped here -- after the acceptance roll, so a
        # declined offer leaves the market pool untouched.
        try:
            staffer.salary = salary
            staffer.contract_years = years
            _asg = str(params.get("assignment", "nhl") or "nhl").lower()
            staffer.assignment = _asg if _asg in ("nhl", "ahl") else "nhl"
        except Exception:
            pass
        hired = False
        try:
            roster = getattr(team, "staff", None)
            if roster is not None and staffer not in roster:
                roster.append(staffer)
                hired = True
            elif roster is not None:
                hired = True
        except Exception:
            pass
        if not hired:
            return False, "Couldn't complete the hire."
        try:
            league = getattr(self, "league", None)
            if source == "free_agent":
                pool = getattr(league, "free_agent_staff", None)
                if pool is not None and staffer in pool:
                    pool.remove(staffer)
            elif source == "overseas":
                pool = getattr(league, "overseas_staff", None)
                if pool is not None and staffer in pool:
                    pool.remove(staffer)
            elif source == "ahl_poach" and employer is not None:
                if staffer in (getattr(employer, "staff", None) or []):
                    employer.staff.remove(staffer)
        except Exception:
            pass
        try:
            import analytics_scouting as _as
            _as.refresh_analytics_quality(team)
        except Exception:
            pass
        name = getattr(staffer, "name",
                       getattr(staffer, "full_name", "staffer"))
        return True, f"Hired {name} ({years}y, ${salary:,}/yr)."

    def _mp_host_mode(self):
        return getattr(self, 'mp_host', None) is not None

    def _mp_is_goalie(player):
        pos = getattr(player, "primary_position", "")
        return getattr(pos, "value", pos) == "G"

    def _mp_mark_inbox_decision(self, team, message_id, key, value,
                                done_key=None):
        """Record one inbox decision on the team's canonical message:
        decided[key] = value; action_done when every card is decided.
        Returns the message or None."""
        try:
            inbox = getattr(team, "inbox", None)
            msgs = getattr(inbox, "messages", None) or []
            msg = next((m for m in msgs
                        if str(getattr(m, "id", "")) == str(message_id)),
                       None)
            if msg is None:
                return None
            data = getattr(msg, "action_data", None) or {}
            decided = data.get("decided", {}) or {}
            decided[str(key)] = value
            data["decided"] = decided
            msg.action_data = data
            cards = data.get(done_key or "cards", []) or []
            if cards and len(decided) >= len(cards):
                msg.action_done = True
            return msg
        except Exception:
            return None

    def _mp_offer_sheet(self, params, team, manager):
        """Present an offer sheet to an RFA: mirrors the offer-sheet UI's
        _present_offer_sheet flow against the canonical state. The host
        runs window/compensation/cap/willingness/match checks and executes
        the same rfa_system helpers single-player uses."""
        try:
            import rfa_system as _rfa
        except Exception:
            return False, "Offer sheets aren't available."
        # Find the RFA player: search all teams' RFAs for the ID.
        _pid = str(params.get("player_id", ""))
        player, original_team = None, None
        try:
            for _t in getattr(getattr(self, "league", None), "teams", []) or []:
                for _p in getattr(_t, "roster", []) or []:
                    if str(getattr(_p, "id", "")) == _pid:
                        # RFA = restricted: has contract, team holds rights
                        _c = getattr(_p, "contract", None)
                        if _c is not None and getattr(
                                _c, "restricted", False):
                            player, original_team = _p, _t
                            break
                if player is not None:
                    break
        except Exception:
            pass
        if player is None:
            return False, "That player isn't an RFA."
        if original_team is team:
            return False, "You can't offer-sheet your own player."
        try:
            aav = int(params.get("aav", 0))
            years = int(params.get("years", 0))
        except (TypeError, ValueError):
            return False, "Invalid offer sheet terms."
        if aav <= 0 or years <= 0:
            return False, "Offer sheet needs a positive AAV and term."
        league = getattr(self, "league", None)
        # 1. Window.
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "offer_sheet", getattr(self, "current_date", None))
            if not _ok:
                return False, _why
        except Exception:
            pass
        # 2. Compensation + own picks (same fallback the engine uses:
        # walk forward through the club's own upcoming picks).
        label, picks = _rfa.offer_sheet_compensation(aav)
        try:
            _yr = int(getattr(league, "season_year", 2026) or 2026) + 1
            _missing = []
            _used = set()
            for _rnd in picks or []:
                _found = None
                for _yy in range(_yr, _yr + 7):
                    _cand = _rfa.own_pick_available(team, _yy, _rnd)
                    if _cand is not None and id(_cand) not in _used:
                        _found = _cand
                        _used.add(id(_cand))
                        break
                if _found is None:
                    _missing.append(_rnd)
            if _missing:
                return False, (
                    f"You don't hold your own picks for the required "
                    f"compensation ({label}).")
        except Exception:
            pass
        # 3. Cap + roster room.
        try:
            from salary_cap_system import cap_breakdown as _cb
            _space = int(_cb(team).get("space", 0) or 0)
        except Exception:
            _space = 0
        if _space < aav:
            return False, f"Not enough cap space: ${_space:,} vs ${aav:,}/yr."
        if len(getattr(team, "roster", []) or []) >= 23:
            return False, "Your NHL roster is full (23/23)."
        # 4. Player willingness.
        try:
            import player_decision as _pd
            willing, _appeal, reasons = _pd.player_accepts_offer_sheet(
                player, team, aav, years, original_team,
                league=league, app=self, rng=getattr(self, "_rng", None))
        except Exception:
            willing, reasons = True, []
        if not willing:
            _why_txt = f" {reasons[0]}" if reasons else ""
            return False, f"{player.full_name} won't sign.{_why_txt}"
        # 5. Match or decline -- the same ai_match_decision July uses.
        try:
            if _rfa.ai_match_decision(original_team, player, aav, label):
                mres = _rfa.apply_offer_sheet_matched(
                    league, team, original_team, player, aav, years, app=self)
                return True, (f"{original_team.team_name} matched. "
                              f"He stays.")
            res = _rfa.execute_offer_sheet(
                league, team, original_team, player, aav, years,
                app=self, rng=getattr(self, "_rng", None))
        except Exception as e:
            return False, f"Offer sheet failed: {e}"
        if not res.get("ok"):
            return False, f"The sheet failed: {res.get('reason', 'unknown')}."
        try:
            self.add_news(res.get("story", ""))
        except Exception:
            pass
        return True, f"He's yours! {label} goes to {original_team.team_name}."

    def _mp_offer_sheet_match(self, params, team, manager):
        """Match an offer sheet or take the pick compensation."""
        import rfa_system as _rfa
        match = bool(params.get("match", False))
        with self._mp_swapped_user_team(team):
            try:
                res = _rfa.apply_offer_sheet_match(
                    self, self.league,
                    (params.get("player_id")
                     or (getattr(self._mp_find_inbox_msg(
                         team, params.get("message_id", "")), "action_data",
                         None) or {}).get("player_id")),
                    match)
            except Exception as e:
                return False, f"Offer-sheet decision failed: {e}"
        if (res or {}).get("ok"):
            self._mp_force_inbox_done(team, params.get("message_id", ""))
        return (True, "Offer sheet matched." if match else
                "Took the compensation.") if (res or {}).get("ok") else \
            (False, str((res or {}).get("reason", "decision failed")))

    def _mp_offer_sheet_trade_alt(self, params, team, manager):
        """Accept the sign-and-trade package or take the picks."""
        import rfa_system as _rfa
        accept = bool(params.get("accept", False))
        with self._mp_swapped_user_team(team):
            try:
                res = _rfa.apply_offer_sheet_trade_alt(
                    self, self.league,
                    (params.get("player_id")
                     or (getattr(self._mp_find_inbox_msg(
                         team, params.get("message_id", "")), "action_data",
                         None) or {}).get("player_id")),
                    accept)
            except Exception as e:
                return False, f"Trade-alternative decision failed: {e}"
        if (res or {}).get("ok"):
            self._mp_force_inbox_done(team, params.get("message_id", ""))
        return (True, "Sign-and-trade accepted." if accept else
                "Took the compensation.") if (res or {}).get("ok") else \
            (False, str((res or {}).get("reason", "decision failed")))

    def _mp_on_draft_update(self, payload):
        """Spectator feed: a draft pick was committed on the host.
        Toast it and refresh an open draft view so remote managers and
        spectators see progress without waiting for a full STATE_SYNC."""
        try:
            _draft = str(payload.get("draft", "") or "")
            _ov = payload.get("overall", 0)
            _team = str(payload.get("team_id", "") or "?")
            _player = str(payload.get("player_name", "") or "?")
            self._mp_toast(
                f"Draft pick #{_ov}: {_team} selects {_player}.")
            if _draft == "fantasy":
                view = getattr(self, "_mp_fantasy_view", None)
                if view is not None:
                    try:
                        view.after(200, view.continue_auto_draft)
                    except Exception:
                        pass
            elif _draft == "entry":
                try:
                    self.update_all_views()
                except Exception:
                    pass
        except Exception:
            pass

    def _mp_owner_meeting(self, params, team, manager):
        """Request an owner meeting: the room settles (morale +2) when
        patience is granted. The board roll only runs for the host's own
        club -- in MP the board is the host save's single shared board
        and client boards aren't advanced; clients get the team-scoped
        morale effect with honest messaging."""
        try:
            _is_host_team = team is getattr(self, "user_team", None)
        except Exception:
            _is_host_team = False
        if _is_host_team:
            try:
                board = self.career.board
                today = ""
                try:
                    today = self.current_date.isoformat()
                except Exception:
                    pass
                granted, headline, body = board.request_patience(today)
            except Exception as e:
                return False, f"Owner meeting failed: {e}"
        else:
            granted, headline = True, "The room settles"
            body = ("Your owner hears you out. (League boards are the "
                    "host's in multiplayer -- your club's morale still "
                    "responds to the meeting.)")
        if granted:
            try:
                for p in (getattr(team, "roster", None) or []):
                    m = getattr(p, "morale", 70) or 70
                    p.morale = min(100, m + 2)
            except Exception:
                pass
        return True, f"{headline}: {body}"

    def _mp_peer_session_for_team(self, team_id):
        """session_id of the client managing team_id, or None."""
        try:
            peer = self.mp_host.find_peer_by_team(team_id)
            return getattr(peer, "session_id", None)
        except Exception:
            return None

    def _mp_pick_player_age(self, player):
        try:
            return int(getattr(player, "age", 0) or 0)
        except Exception:
            return 0

    def _mp_pick_player_ovr(self, player, ctx=None):
        try:
            if ctx is not None:
                from player_views import column_sort
                v = column_sort("ovr", player, ctx)
                if v is not None:
                    return int(float(v))
        except Exception:
            pass
        try:
            return int(float(
                getattr(player, "overall_rating", lambda: 50)() or 50))
        except Exception:
            return 50

    def _mp_pick_player_pos(self, player):
        try:
            return str(getattr(
                getattr(player, "primary_position", None), "value", "?"))
        except Exception:
            return "?"

    def _mp_place_on_waivers(self, params, team, manager):
        """Expose a player to the waiver wire: mirrors
        WaiversView._place_on_waivers_after_consent (2-day window, claimed
        at noon in priority order). An NMC blocks exposure without the
        player's consent -- the host asks via NTC_WAIVER_REQUEST
        (context="waivers"), exactly like send_to_minors. The client's
        word is never trusted."""
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        if getattr(player, "on_waivers", False):
            return False, f"{player.full_name} is already on waivers."
        # Waiver window, same as single-player (transaction_windows.py).
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "waiver_place", getattr(self, "current_date", None))
            if not _ok:
                return False, f"Waivers are closed ({_why})."
        except Exception:
            pass
        try:
            import trade_engine as te
            kind, _detail = te.clause_of(player) or (None, "")
        except Exception:
            kind = None
        if kind == "NMC":
            return self._mp_begin_consent_flow(team, player, manager,
                                              kind="expose")
        return self._mp_apply_waiver_exposure(team, player)

    def _mp_practice_session(self, params, team, manager):
        """Run one practice session: the same engine call the SP practice
        center makes -- can_practice gate, then execute_practice against
        the canonical player (skill gain + fatigue land on real state)."""
        try:
            from enhanced_practice_system import (
                PracticeEngine, PracticeType, PracticeIntensity)
        except Exception:
            return False, "Practice system isn't available."
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        try:
            ptype = PracticeType(str(params.get("practice_type", "")))
        except Exception:
            return False, "Unknown practice type."
        try:
            intensity = PracticeIntensity(str(params.get("intensity", "")))
        except Exception:
            return False, "Unknown intensity."
        try:
            duration = int(params.get("duration", 60))
        except (TypeError, ValueError):
            duration = 60
        duration = max(15, min(180, duration))
        try:
            trainer_quality = int(params.get("trainer_quality", 12))
        except (TypeError, ValueError):
            trainer_quality = 12
        engine = PracticeEngine()
        try:
            can, why = engine.can_practice(player, ptype, intensity)
        except Exception:
            can, why = True, ""
        if not can:
            return False, why or "He can't practice right now."
        try:
            session = engine.execute_practice(
                player, ptype, intensity, duration, trainer_quality,
                team=team)
        except Exception as e:
            return False, f"Session failed: {e}"
        if not session:
            return False, "Session failed."
        return True, (f"Session complete: +{session.skill_gain:.2f} skill, "
                      f"+{session.fatigue_cost}% fatigue.")

    def _mp_press_conference(self, params, team, manager):
        """Answer the press: the same cascade_on_press() the podium UI
        triggers -- stance maps straight onto the response choice.

        Second shape: {answers: [...], kind} for the inbox bundle pressers.
        Applies the same team-scoped effects (roster morale, fan sentiment)
        _career_apply_press_answers computes. The board effect is skipped:
        in MP the board is the host save's single shared board and client
        boards aren't advanced -- applying a client's presser to it would
        move the host's standing."""
        # Inbox-bundle answer branch.
        if isinstance(params.get("answers"), list):
            _answers = [a for a in (params.get("answers") or [])
                        if isinstance(a, dict)][:8]
            _kind = str(params.get("kind", "presser") or "presser")[:24]
            _tm = sum(int(a.get("morale_effect", 0) or 0) for a in _answers)
            _tf = sum(int(a.get("fan_effect", 0) or 0) for a in _answers)
            try:
                if _tm:
                    for p in (getattr(team, "roster", None) or []):
                        m = getattr(p, "morale", 70) or 70
                        p.morale = max(1, min(100,
                                             m + (5 if _tm > 0 else -5)))
                if _tf:
                    from fan_sentiment import nudge_fan_sentiment
                    nudge_fan_sentiment(
                        team, _tf * 2.5,
                        reason=f"presser ({_kind}): {_tf:+d}",
                        current_date=getattr(self, "current_date", None))
                _summary = (f"{_kind}: " + "; ".join(
                    str(a.get("label", "")) for a in _answers))
                try:
                    _car = getattr(self, "career", None)
                    _ph = getattr(_car, "press_history", None)
                    if isinstance(_ph, list):
                        _ph.append({
                            "date": getattr(
                                getattr(self, "current_date", None),
                                "isoformat", lambda: "")(),
                            "type": _kind,
                            "summary": f"[{team.team_name}] {_summary}"})
                except Exception:
                    pass
            except Exception as e:
                return False, f"Press conference failed: {e}"
            return True, f"Presser answered ({_kind})."
        try:
            import dressing_room as _dr
        except Exception:
            return False, "Dressing room isn't available."
        stance = str(params.get("stance", "professional")
                     or "professional").lower()
        valid = ("confident", "supportive", "professional", "diplomatic",
                 "critical", "dismissive", "controversial")
        if stance not in valid:
            return False, f"Stance must be one of: {', '.join(valid)}."
        topic = str(params.get("topic", "") or "")
        target = str(params.get("player", "") or "")
        event = {"topic": topic}
        if target:
            event["player"] = target
        try:
            lines = _dr.cascade_on_press(team, event, stance)
        except Exception as e:
            return False, f"Press conference failed: {e}"
        head = lines[0] if lines else "The room absorbs it."
        return True, f"Press conference held ({stance}). {head}"

    def _mp_promote_to_host(self):
        """Take over as host from the client's last synced checkpoint.

        Loads saves/checkpoints/client_last_sync.hm into the full game
        state, then starts a MultiplayerHost on the same port so the
        session continues. The promoting client becomes the host and keeps
        managing their claimed team locally.
        """
        import os
        import gzip
        import pickle
        _ckpt = os.path.join("saves", "checkpoints", "client_last_sync.hm")
        if not os.path.exists(_ckpt):
            raise FileNotFoundError(
                "No fallback checkpoint found (client_last_sync.hm).")
        _ok = False
        try:
            _ok = bool(self.save_manager.load_game(_ckpt))
        except Exception:
            _ok = False
        if not _ok:
            with gzip.open(_ckpt, "rb") as _fh:
                _data = pickle.load(_fh)
            try:
                self.save_manager.restore_game_data(_data)
                _ok = True
            except Exception:
                _ok = False
        if not _ok:
            raise RuntimeError("Couldn't load the fallback checkpoint.")
        # Native: the UI layer owns host startup (it has the dialogs and
        # the event pump). Hand off via _ui_notify.
        self._ui_notify("mp_promote_to_host", _ckpt)

    def _mp_release_player(self, params, team, manager):
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        team.remove_player(player)
        try:
            fa_pool = self.free_agents()
            if fa_pool is None:
                fa_pool = []
            if player not in fa_pool:
                fa_pool.append(player)
        except Exception:
            pass
        try:
            self.add_news(f"{player.full_name} released by {team.team_name}.")
        except Exception:
            pass
        return True, f"Released {player.full_name}."

    def _mp_request_save(self, params, team, manager):
        """A client asked the host to save: save canonically and broadcast
        a checkpoint notice so everyone knows the save landed."""
        try:
            _label = f"Save requested by {manager}"
            self.save_manager.save_game()
            try:
                _host = getattr(self, "mp_host", None)
                if _host is not None:
                    _host.notify_checkpoint(
                        _label, str(getattr(self, "current_date", "")))
            except Exception:
                pass
            return True, "Game saved."
        except Exception as e:
            return False, f"Save failed: {e}"

    def _mp_resolve_demote_answer(self, pend, waiver_id, choice):
        """Resolve a demotion NMC consent: "ask" rolls the player's decision
        (context="waivers", like single-player); anything else keeps him
        on the roster. The demotion itself only ever runs here, on the
        host, after a granted answer."""
        import trade_engine as te
        self._mp_pending_ntc.pop(waiver_id, None)
        team = self._mp_find_team(pend.get("team_id", ""))
        name = pend.get("player_name", "The player")
        if team is None:
            return
        player = self._mp_team_player(team, pend.get("player_id", ""))
        if player is None:
            try:
                self.mp_host.broadcast_chat(
                    f"{name} moved clubs while his waiver answer was "
                    f"pending -- demotion cancelled.")
            except Exception:
                pass
            return
        if choice != "ask":
            try:
                self.mp_host.broadcast_chat(
                    f"{name} stays on the roster "
                    f"({pend.get('manager', 'his GM')} didn't ask him to "
                    f"waive his {pend.get('clause', 'no-movement clause')}).")
            except Exception:
                pass
            return
        try:
            league = getattr(self, "league", None)
            granted, why = te.will_waive_ntc(player, team, None, league,
                                             context="waivers")
        except Exception as e:
            granted, why = False, str(e)
        if not granted:
            try:
                self.mp_host.broadcast_chat(
                    f"{name} refused to waive his "
                    f"{pend.get('clause', 'no-movement clause')} ({why}) -- "
                    f"he stays on the roster.")
            except Exception:
                pass
            return
        try:
            self.mp_host.broadcast_chat(
                f"{name} agreed to be exposed on waivers ({why}).")
        except Exception:
            pass
        ok, detail = self._mp_demote_player(team, player)
        if not ok:
            try:
                self.mp_host.broadcast_chat(
                    f"Demotion failed after the waiver was granted: "
                    f"{detail}")
            except Exception:
                pass

    def _mp_resolve_expose_answer(self, pend, waiver_id, choice):
        """Resolve a wire-exposure NMC consent: "ask" rolls the player's
        decision (context="waivers", like single-player); anything else
        keeps him off the wire. The exposure itself only ever runs here,
        on the host, after a granted answer."""
        import trade_engine as te
        self._mp_pending_ntc.pop(waiver_id, None)
        team = self._mp_find_team(pend.get("team_id", ""))
        name = pend.get("player_name", "The player")
        if team is None:
            return
        player = self._mp_team_player(team, pend.get("player_id", ""))
        if player is None:
            try:
                self.mp_host.broadcast_chat(
                    f"{name} moved clubs while his waiver answer was "
                    f"pending -- exposure cancelled.")
            except Exception:
                pass
            return
        if choice != "ask":
            try:
                self.mp_host.broadcast_chat(
                    f"{name} stays off the wire "
                    f"({pend.get('manager', 'his GM')} didn't ask him to "
                    f"waive his {pend.get('clause', 'no-movement clause')}).")
            except Exception:
                pass
            return
        try:
            league = getattr(self, "league", None)
            granted, why = te.will_waive_ntc(player, team, None, league,
                                             context="waivers")
        except Exception as e:
            granted, why = False, str(e)
        if not granted:
            try:
                self.mp_host.broadcast_chat(
                    f"{name} refused to waive his "
                    f"{pend.get('clause', 'no-movement clause')} ({why}) -- "
                    f"he stays off the wire.")
            except Exception:
                pass
            return
        try:
            self.mp_host.broadcast_chat(
                f"{name} agreed to be exposed on waivers ({why}).")
        except Exception:
            pass
        ok, detail = self._mp_apply_waiver_exposure(team, player)
        if not ok:
            try:
                self.mp_host.broadcast_chat(
                    f"Exposure failed after the waiver was granted: "
                    f"{detail}")
            except Exception:
                pass

    def _mp_resolve_ntc_answer(self, payload):
        """Host-side NTC_WAIVER_ANSWER: ask/remove/cancel.

        kind="trade": for one veto, then continue the waiver flow or route
        the (possibly trimmed) proposal.
        kind="demote": the player's answer to a waiver-exposure request --
        on "ask"-granted the demotion runs, anything else keeps him on
        the roster.
        """
        import trade_engine as te
        waiver_id = payload.get("waiver_id", "")
        choice = payload.get("choice", "cancel")
        pend = self._mp_pending_ntc.get(waiver_id)
        if pend is None:
            return
        if pend.get("kind", "trade") == "demote":
            self._mp_resolve_demote_answer(pend, waiver_id, choice)
            return
        if pend.get("kind") == "expose":
            self._mp_resolve_expose_answer(pend, waiver_id, choice)
            return
        proposal = pend["proposal"]
        vetoes = pend["vetoes"]
        if pend["veto_idx"] >= len(vetoes):
            self._mp_pending_ntc.pop(waiver_id, None)
            return
        v = vetoes[pend["veto_idx"]]
        team = self._mp_find_team(pend["team_id"])
        partner = self._mp_find_team(pend["partner_id"])
        session_id = self._mp_peer_session_for_team(pend["team_id"])

        def _drop(msg):
            self._mp_pending_ntc.pop(waiver_id, None)
            self._mp_clear_proposal_waivers(proposal)
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {proposal['proposer_team_id']} -> "
                    f"{proposal['partner_team_id']} died: {msg}")
            except Exception:
                pass

        if team is None or partner is None:
            _drop("a club is gone")
            return
        if choice == "cancel":
            _drop(f"{proposal['manager']} cancelled")
            return
        if choice == "remove":
            pid = v["player_id"]
            if pid in proposal["players_out"]:
                proposal["players_out"].remove(pid)
            proposal["retention"].pop(pid, None)
            if not proposal["players_out"] and not proposal["picks_out"]:
                _drop("nothing left to offer")
                return
            pend["veto_idx"] += 1
            self._mp_continue_waiver_flow(waiver_id, pend, _drop)
            return
        # choice == "ask": the player decides, same roll as single-player.
        player = self._mp_team_player(team, v["player_id"])
        if player is None:
            _drop("player moved clubs mid-negotiation")
            return
        try:
            league = getattr(self, "league", None)
            granted, why = te.will_waive_ntc(player, team, partner, league)
        except Exception as e:
            granted, why = False, str(e)
        if granted:
            try:
                player.contract.ntc_waiver_for = partner.team_name
            except Exception:
                pass
            try:
                self.mp_host.broadcast_chat(
                    f"{v['player_name']} waived his {v['clause']} for a move "
                    f"to {partner.team_name}.")
            except Exception:
                pass
            pend["veto_idx"] += 1
            self._mp_continue_waiver_flow(waiver_id, pend, _drop)
        else:
            _drop(f"{v['player_name']} refused to waive ({why})")

    def _mp_resolve_trade_response(self, payload):
        """Host-side TRADE_RESPONSE: the other human answered an offer."""
        import trade_engine as te
        offer_id = payload.get("offer_id", "")
        decision = payload.get("decision", "")
        proposal = self._mp_pending_offers.pop(offer_id, None)
        if proposal is None:
            return
        team = self._mp_find_team(proposal["proposer_team_id"])
        partner = self._mp_find_team(proposal["partner_team_id"])
        if team is None or partner is None:
            return
        if decision != "accept":
            self._mp_clear_proposal_waivers(proposal)
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {team.team_name} -> {partner.team_name} "
                    f"rejected by {payload.get('manager', '?')}.")
            except Exception:
                pass
            return
        # Accepted: the partner's clause players get asked now -- the
        # partner GM "asks him" by accepting, same roll as single-player.
        league = getattr(self, "league", None)
        in_players = [self._mp_team_player(partner, pid)
                      for pid in proposal["players_in"]]
        if any(p is None for p in in_players):
            self._mp_clear_proposal_waivers(proposal)
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {team.team_name} -> {partner.team_name} died: "
                    f"an asset moved clubs.")
            except Exception:
                pass
            return
        try:
            for _v in te.trade_vetoes(partner, team, in_players, league):
                _p = _v["player"]
                _ok, _why = te.will_waive_ntc(_p, partner, team, league)
                if not _ok:
                    self._mp_clear_proposal_waivers(proposal)
                    try:
                        self.mp_host.broadcast_chat(
                            f"Trade {team.team_name} -> {partner.team_name} "
                            f"died: {getattr(_p, 'full_name', 'player')} "
                            f"refused to waive ({_why}).")
                    except Exception:
                        pass
                    return
                try:
                    _p.contract.ntc_waiver_for = team.team_name
                except Exception:
                    pass
        except Exception:
            pass
        proposal["_in_players"] = in_players
        ok, detail = self._mp_execute_mp_trade(proposal)
        if not ok:
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {team.team_name} -> {partner.team_name} "
                    f"failed: {detail}")
            except Exception:
                pass

    def _mp_return_to_junior(self, params, team, manager):
        """Return a prospect to his junior club: mirrors the single-player
        'Return to Junior' (RosterView AHL tab -> move_player ahl->prospects).

        Same gate as single-player: only SIGNED junior-aged (under-20)
        CHL prospects qualify. An ex-college player can never go back
        once he's signed an NHL deal; anyone else stays with the pro
        club. The client's word is never trusted -- eligibility is
        computed host-side.
        """
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        if getattr(player, "contract", None) is None:
            return False, (f"{player.full_name} isn't signed -- only "
                            f"signed prospects can be returned to junior.")
        try:
            import game_classes as _gc_jr
            _track = _gc_jr.junior_track_of(player)
            _jage = int(getattr(player, "age", 20) or 20)
        except Exception:
            return False, "Couldn't verify his junior eligibility."
        if not (_track == "CHL" and _jage < 20):
            if _track == "NCAA":
                _why = (f"{player.full_name} signed an NHL contract -- "
                        f"that ended his NCAA eligibility. He can only "
                        f"play in the NHL or AHL now, never back in "
                        f"college.")
            else:
                _why = (f"Only junior-aged (under-20) CHL prospects can be "
                        f"returned to junior. {player.full_name} stays "
                        f"with the pro club.")
            return False, _why
        for _attr in ("roster", "ahl_roster"):
            try:
                _lst = getattr(team, _attr, None) or []
                if player in _lst:
                    _lst.remove(player)
            except Exception:
                pass
        try:
            _pros = getattr(team, "prospects", None)
            if _pros is None:
                _pros = []
                try:
                    team.prospects = _pros
                except Exception:
                    pass
            if player not in _pros:
                _pros.append(player)
        except Exception:
            pass
        try:
            player.playing_where = _gc_jr.junior_assignment_label(player)
        except Exception:
            pass
        try:
            self.add_news(f"{player.full_name} was returned to junior "
                          f"({player.playing_where}) by {team.team_name}.")
        except Exception:
            pass
        return True, f"{player.full_name} returned to junior."

    def _mp_rfa_qualify(self, params, team, manager):
        """Extend or decline a qualifying offer for one RFA."""
        import rfa_system as _rfa
        pid = str(params.get("player_id", "") or "")
        qualify = bool(params.get("qualify", False))
        with self._mp_swapped_user_team(team):
            try:
                res = _rfa.apply_qualifying_decision(
                    self, self.league, team, pid, qualify)
            except Exception as e:
                return False, f"Qualifying decision failed: {e}"
        self._mp_mark_inbox_decision(team, params.get("message_id", ""),
                                     pid, qualify)
        ok = bool((res or {}).get("ok", True))
        return (True, "Qualifying offer extended." if qualify else
                "Player non-tendered.") if ok else \
            (False, str((res or {}).get("reason", "decision failed")))

    def _mp_seed_host_reservations(self, host):
        """Seed a new host's GM reservations from the league's save data.

        Teams whose saves carry an mp_gm_token are reserved for that GM:
        they auto-reclaim on rejoin and nobody else can squat them. Also
        stamps the host's own club with this machine's identity so the
        host's seat persists too.
        """
        try:
            _lg = getattr(self, "league", None)
            _res, _names = {}, {}
            for _t in (getattr(_lg, "teams", None) or []):
                _tok = getattr(_t, "mp_gm_token", "") or ""
                if _tok:
                    _res[_tok] = getattr(_t, "team_name", "")
                    _nm = getattr(_t, "mp_gm_name", "") or ""
                    if _nm:
                        _names[_tok] = _nm
            try:
                host.seed_reservations(_res, _names)
            except Exception:
                pass
            # The host's own seat: stamp this machine's identity on the
            # local club so it persists like any other GM's.
            try:
                from multiplayer.net_client import get_machine_token as _gmt
                _mine = _gmt()
                _ut = getattr(self, "user_team", None)
                if _mine and _ut is not None:
                    _ut.mp_gm_token = _mine
                    _ut.is_human_managed = True
                    try:
                        _prof = getattr(self, "gm_profile", None) or {}
                        _nm = (_prof.get("name", "")
                               if isinstance(_prof, dict) else "")
                        if _nm:
                            _ut.mp_gm_name = str(_nm)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _mp_send_next_waiver(self, waiver_id, session_id):
        pend = self._mp_pending_ntc.get(waiver_id)
        if pend is None:
            return False, "Waiver flow expired."
        vetoes = pend["vetoes"]
        if pend["veto_idx"] >= len(vetoes):
            proposal = self._mp_pending_ntc.pop(waiver_id)["proposal"]
            return self._mp_route_trade_offer(proposal)
        v = vetoes[pend["veto_idx"]]
        try:
            self.mp_host.send_ntc_waiver_request(
                session_id, waiver_id, v["player_id"], v["player_name"],
                v["clause"], v["dest"], "trade")
        except Exception:
            self._mp_pending_ntc.pop(waiver_id, None)
            return False, "Could not reach your client."
        return (True,
                f"{v['player_name']} has a {v['clause']} -- "
                f"waiting on your call (ask him / remove / cancel).",
                False)

    def _mp_send_to_minors(self, params, team, manager):
        """Waive-and-assign: mirrors WaiversView.place_on_waivers().

        An NMC blocks the move without the player's consent -- the host
        asks the player itself (will_waive_ntc, context="waivers"), exactly
        like single-player. The client's word is never trusted.
        """
        # Waiver window, same as single-player (transaction_windows.py).
        try:
            import transaction_windows as _tw
            _ok, _why = _tw.check_window(
                "waiver_place", getattr(self, "current_date", None))
            if not _ok:
                return False, _why
        except Exception:
            pass
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        if player not in (getattr(team, "roster", None) or []):
            return False, "Only NHL-roster players go through waivers."
        try:
            import trade_engine as te
            kind, _detail = te.clause_of(player) or (None, "")
        except Exception:
            kind = None
        if kind == "NMC":
            return self._mp_begin_consent_flow(team, player, manager)
        return self._mp_demote_player(team, player)

    def _mp_set_captaincy(self, params, team, manager):
        """Set the club's captain + alternates on canonical state.

        Same 1C+2A rule the SP pickers enforce: two alternates from the
        NHL roster, no goalie letters, no double letters. A deposition
        context (established captain losing the C) runs the shared
        captaincy_change judgment consequences on the host, exactly as
        the SP manual tool does locally -- the conversation happened on
        the client, the fallout lands here.
        """
        alt_ids = params.get("alt_ids") or []
        if not isinstance(alt_ids, list):
            return False, "Malformed alternates."
        alts = [self._mp_team_player(team, pid) for pid in alt_ids]
        if len(alts) != 2 or any(a is None for a in alts):
            return False, "Pick exactly two alternates from your club."
        cap = self._mp_team_player(team, params.get("captain_id", "") or "")
        picked = ([cap] if cap is not None else []) + alts
        if len({str(getattr(pl, "id", "")) for pl in picked}) != len(picked):
            return False, "One player, one letter."
        for pl in picked:
            if self._mp_is_goalie(pl):
                return False, (f"{pl.full_name} is a goalie -- goalies "
                                "can't wear a letter (NHL Rule 6.1).")
            if pl not in (getattr(team, "roster", None) or []):
                return False, (f"{pl.full_name} isn't on the NHL roster.")
        dep = params.get("deposition") or {}
        # Validate EVERYTHING before touching a single letter: a rejected
        # payload must leave the existing captaincy untouched.
        old_c = None
        dep_tier = str(dep.get("tier", "grumbles")) if isinstance(dep, dict) else "grumbles"
        if isinstance(dep, dict) and dep.get("old_captain_id"):
            old_c = self._mp_team_player(team, dep.get("old_captain_id", ""))
            if old_c is None:
                return False, "The deposed captain isn't on your club."
            if dep_tier not in ("graceful", "grumbles", "furious"):
                return False, "Unknown deposition tone."
        roster = list(getattr(team, "roster", None) or [])
        for pl in roster:
            try:
                pl.captaincy = None
            except Exception:
                pass
        if old_c is not None:
            try:
                import captaincy_change as _cc
                report = _cc.apply_deposition(
                    team, old_c, cap, dep_tier,
                    talked=bool(dep.get("talked", False)),
                    date_str=str(dep.get("date_str", "") or ""),
                    compromise_alternate=bool(dep.get("compromise",
                                                      False)))
                for line in (report.get("news") or []):
                    try:
                        self.add_news(line)
                    except Exception:
                        pass
            except Exception as e:
                # Restore the old letters rather than leaving the club
                # letterless on a half-applied deposition.
                try:
                    old_c.captaincy = "C"
                except Exception:
                    pass
                return False, f"Deposition fallout failed: {e}"
            # The C was dealt by apply_deposition (or left vacant); the
            # alternates are (re)written here.
            for al in alts:
                try:
                    al.captaincy = "A"
                except Exception:
                    pass
            try:
                team._captaincy_auto_assigned = False
            except Exception:
                pass
            return True, "Captaincy change applied."
        if cap is None:
            return False, "Choose a captain (C)."
        try:
            cap.captaincy = "C"
            for al in alts:
                al.captaincy = "A"
        except Exception:
            return False, "Couldn't write the letters."
        try:
            team._captaincy_auto_assigned = False
        except Exception:
            pass
        try:
            self.add_news(
                f"{team.team_name} named {cap.full_name} captain "
                f"({alts[0].full_name}, {alts[1].full_name} alternates).")
        except Exception:
            pass
        return True, f"{cap.full_name} named captain."

    def _mp_set_lines(self, params, team, manager):
        """Apply a client's lineup to the canonical team.lineup.

        The client sends player IDs in the editor's nested shape; the host
        resolves them against the canonical roster (ownership validated),
        rejects dupes and non-goalies in net, then stores + flattens exactly
        like the SP editor (flatten_lineup). The next STATE_SYNC carries it
        to everyone and the sim dresses it via resolve_game_lineup.
        """
        lines = params.get("lines")
        if not isinstance(lines, dict):
            return False, "Missing lines payload."
        try:
            from quick_sim import flatten_lineup
        except Exception:
            return False, "Lineup machinery unavailable."
        nested = {}
        seen = set()
        def _resolve(pid):
            if pid in (None, "", "None"):
                return None
            p = self._mp_team_player(team, pid)
            return p
        # Forwards: 4 x 3 — skaters only.
        fw = lines.get("Forwards") or []
        out_fw = []
        for li in range(4):
            line = fw[li] if li < len(fw) else []
            out_line = []
            for si in range(3):
                pid = line[si] if si < len(line) else None
                p = _resolve(pid)
                if p is None:
                    out_line.append(None)
                    continue
                if self._mp_is_goalie(p):
                    return False, (f"{p.full_name} is a goalie -- "
                                   "skaters only on forward lines.")
                key = str(getattr(p, "id", ""))
                if key in seen:
                    return False, (f"{p.full_name} is dressed twice -- "
                                   "each player skates one slot.")
                seen.add(key)
                out_line.append(p)
            out_fw.append(out_line)
        nested["Forwards"] = out_fw
        # Defense: 3 x 2 — skaters only.
        df = lines.get("Defense") or []
        out_df = []
        for li in range(3):
            pair = df[li] if li < len(df) else []
            out_pair = []
            for si in range(2):
                pid = pair[si] if si < len(pair) else None
                p = _resolve(pid)
                if p is None:
                    out_pair.append(None)
                    continue
                if self._mp_is_goalie(p):
                    return False, (f"{p.full_name} is a goalie -- "
                                   "skaters only on defense pairs.")
                key = str(getattr(p, "id", ""))
                if key in seen:
                    return False, (f"{p.full_name} is dressed twice -- "
                                   "each player skates one slot.")
                seen.add(key)
                out_pair.append(p)
            out_df.append(out_pair)
        nested["Defense"] = out_df
        # Goalies: 2 — goalies only.
        gl = lines.get("Goalies") or []
        out_gl = []
        for si in range(2):
            pid = gl[si] if si < len(gl) else None
            p = _resolve(pid)
            if p is None:
                out_gl.append(None)
                continue
            if not self._mp_is_goalie(p):
                return False, (f"{p.full_name} isn't a goalie.")
            key = str(getattr(p, "id", ""))
            if key in seen:
                return False, (f"{p.full_name} is dressed twice.")
            seen.add(key)
            out_gl.append(p)
        nested["Goalies"] = out_gl
        # Special teams ride along when supplied (same keys as the editor).
        # Note: special-teamers are the same skaters dressed at even
        # strength, so duplicate detection restarts here -- it only guards
        # against one player holding two jobs on the SAME unit.
        for key in ("PP1", "PP2", "PK1", "PK2"):
            units = lines.get(key)
            if not isinstance(units, dict):
                continue
            seen_st = set()
            out_units = {}
            for ukey, plist in units.items():
                resolved = []
                for pid in plist or []:
                    p = _resolve(pid)
                    if p is None:
                        continue
                    pkey = str(getattr(p, "id", ""))
                    if pkey in seen_st:
                        return False, (f"{p.full_name} has two jobs on "
                                       f"{key} -- one player, one role.")
                    seen_st.add(pkey)
                    resolved.append(p)
                out_units[ukey] = resolved
            nested[key] = out_units
        team.lineup = flatten_lineup(nested)
        return True, "Lines saved."

    def _mp_set_practice(self, params, team, manager):
        """Set training programs: writes the same game_manager.
        training_programs entries the practice window creates."""
        try:
            from enhanced_practice_system import (
                FOCUS_TO_PRACTICE_TYPE, INTENSITY_LABEL_TO_ENUM)
            from datetime import date as _date
        except Exception:
            return False, "Practice system isn't available."
        focus = str(params.get("focus", "") or "").strip()
        intensity = str(params.get("intensity", "") or "").strip()
        if focus not in FOCUS_TO_PRACTICE_TYPE:
            return False, (
                f"Unknown focus '{focus}'. "
                f"Valid: {', '.join(sorted(FOCUS_TO_PRACTICE_TYPE))}.")
        if intensity not in INTENSITY_LABEL_TO_ENUM:
            return False, (
                f"Unknown intensity '{intensity}'. "
                f"Valid: {', '.join(sorted(INTENSITY_LABEL_TO_ENUM))}.")
        gm = getattr(self, "game_manager", None)
        if gm is None:
            return False, "No game manager."
        if not hasattr(gm, "training_programs") or \
                gm.training_programs is None:
            gm.training_programs = {}
        game_today = getattr(self, "current_date", None) or _date.today()
        ids = params.get("player_ids") or []
        if ids:
            players = [self._mp_team_player(team, pid) for pid in ids]
            players = [p for p in players if p is not None]
            if not players:
                return False, "No matching players on your club."
        else:
            players = list(getattr(team, "roster", []) or [])
        # SP parity: the Development Center stamps int keys
        # (gm.training_programs[player.id]) and runs a first session
        # immediately through the practice engine. String keys would
        # never match the int-keyed lookup in _process_training_programs.
        from enhanced_practice_system import (
            PracticeEngine, FOCUS_TO_PRACTICE_TYPE,
            INTENSITY_LABEL_TO_ENUM)
        _engine = PracticeEngine()
        _ptype = FOCUS_TO_PRACTICE_TYPE.get(focus)
        _intensity = INTENSITY_LABEL_TO_ENUM.get(intensity)
        _applied, _skipped = [], []
        for pl in players:
            try:
                _can, _why = _engine.can_practice(pl, _ptype, _intensity)
            except Exception:
                _can, _why = True, ""
            if not _can:
                _skipped.append(getattr(pl, "full_name", "?"))
                continue
            try:
                gm.training_programs[getattr(pl, "id", "")] = {
                    "focus": focus, "intensity": intensity,
                    "assigned": game_today,
                    "team": getattr(team, "team_name", ""),
                    "player_name": getattr(pl, "full_name", ""),
                }
                # First session runs now, exactly like the SP assignment.
                _engine.execute_practice(pl, _ptype, _intensity, 60, 12)
                _applied.append(pl)
            except Exception:
                _skipped.append(getattr(pl, "full_name", "?"))
        if not _applied:
            return False, ("Nobody could train right now"
                           + (f": {', '.join(_skipped[:3])}"
                              if _skipped else "."))
        _msg = (f"Practice set: {focus} / {intensity} "
                f"for {len(_applied)} players.")
        if _skipped:
            _msg += f" ({len(_skipped)} skipped -- too fatigued.)"
        return True, _msg

    def _mp_set_tactics(self, params, team, manager):
        """Apply a client's tactics to the canonical team tactics state.

        The whiteboard edits the seven zone modules (team.tactics dict);
        line_matchups ride along. Every value is validated against the
        tactics catalogs -- unknown modules/keys are rejected, never
        defaulted. The next STATE_SYNC carries it to the sim.
        """
        tactics = params.get("tactics")
        if not isinstance(tactics, dict):
            return False, "Missing tactics payload."
        try:
            import tactics as tx
        except Exception:
            return False, "Tactics machinery unavailable."
        changed = []
        modules = tactics.get("modules")
        if isinstance(modules, dict):
            if not isinstance(getattr(team, "tactics", None), dict):
                team.tactics = {}
            for mod, key in modules.items():
                mod = str(mod)
                catalog = tx.CATALOGS.get(mod)
                if catalog is None:
                    return False, f"Unknown tactics module: {mod!r}."
                key = str(key)
                if key not in catalog:
                    return False, f"Invalid {mod} system: {key!r}."
                if team.tactics.get(mod) != key:
                    # SP parity: install through the shared helper so the
                    # room's learning-curve familiarity hit applies exactly
                    # as it does on the single-player whiteboard (it also
                    # busts the tactics cache).
                    if tx.set_team_system(team, mod, key):
                        changed.append(mod)
                    else:
                        return False, f"Couldn't install {mod} system."
        if "line_matchups" in tactics:
            lm = tactics["line_matchups"]
            if not isinstance(lm, dict):
                return False, "Invalid line_matchups."
            cur = getattr(team, "line_matchups",
                          {"F": [None] * 4, "D": [None] * 3})
            if not isinstance(cur, dict):
                cur = {"F": [None] * 4, "D": [None] * 3}
            for side, want in (("F", 4), ("D", 3)):
                vals = lm.get(side)
                if vals is None:
                    continue
                if not isinstance(vals, list) or len(vals) != want:
                    return False, f"Invalid line_matchups[{side}]."
                clean = []
                for v in vals:
                    if v is None:
                        clean.append(None)
                        continue
                    try:
                        iv = int(v)
                    except (TypeError, ValueError):
                        return False, f"Invalid matchup value: {v!r}."
                    if not 1 <= iv <= 4:
                        return False, f"Invalid matchup value: {v!r}."
                    clean.append(iv)
                cur[side] = clean
            team.line_matchups = cur
            changed.append("line_matchups")
        if not changed:
            return False, "Nothing to change."
        return True, "Tactics saved."

    def _mp_set_trade_block(self, params, team, manager):
        """Set the club's trade block on the league-level registry
        (trade_market.trade_blocks) -- the signal AI GMs read when
        shopping for deals. Only NHL-roster players are accepted."""
        ids = params.get("player_ids") or []
        if not isinstance(ids, list):
            return False, "Malformed trade block."
        try:
            import trade_market as _tm
            blocks = _tm.get_trade_blocks(getattr(self, "league", None))
        except Exception:
            return False, "Trade market isn't available."
        roster = list(getattr(team, "roster", None) or [])
        valid = []
        for pid in ids:
            pl = self._mp_team_player(team, pid)
            if pl is not None and pl in roster:
                # Raw ids, exactly like refresh_trade_blocks stores them:
                # the registry is indexed and resolved by int player.id.
                valid.append(getattr(pl, "id", ""))
        blocks[team.team_name] = valid
        if valid:
            return True, f"Trade block updated ({len(valid)} players)."
        return True, "Trade block cleared."

    def _mp_show_draft_clock(self, payload):
        """You're on the clock: pick a prospect (60s, then auto-pick).

        Eastside-standard UI: filterable/sortable available list with
        player cards, plus My Picks / All Picks tabs from the board.
        """
        clock_id = payload.get("clock_id", "")
        overall = payload.get("overall", 0)
        round_num = payload.get("round_num", 0)
        prospects = payload.get("prospects") or []
        board = payload.get("board") or []
        team_id = payload.get("team_id", "")
        if not prospects:
            return
        # Resolve prospect dicts -> snapshot Player objects so the
        # filter/card machinery works on real data.
        try:
            _by_id = {}
            _lg = getattr(self, "league", None)
            for _p in (getattr(_lg, "draft_prospects", None) or []):
                _by_id[str(getattr(_p, "id", ""))] = _p
        except Exception:
            _by_id = {}
        players = []
        for _pd in prospects:
            _p = _by_id.get(str(_pd.get("id", "")))
            if _p is not None:
                players.append(_p)
        if not players:
            return
        self._mp_draft_pick_window(
            title=f"Draft pick #{overall} -- you're on the clock",
            players=players, board=board, my_team_id=team_id,
            clock_id=clock_id, action_name="draft_pick",
            answer_attr="_mp_draft_answer",
            expire_toast="Draft clock expired -- auto-pick.",
            draft_button_text="DRAFT SELECTED PROSPECT",
            extra_columns=("rank", "pot"))

    def _mp_show_fantasy_clock(self, payload):
        """Fantasy draft: you're on the clock (60s, then auto-pick).

        Eastside-standard UI: filterable/sortable available list with
        player cards, plus My Picks / All Picks tabs from the board.
        The host sends the available player ids; this client resolves
        them against its snapshot for full Player objects.
        """
        clock_id = payload.get("clock_id", "")
        overall = payload.get("overall", 0)
        round_num = payload.get("round_num", 0)
        available_ids = payload.get("available_ids", []) or []
        shortlist = payload.get("shortlist", []) or []
        board = payload.get("board") or []
        team_id = payload.get("team_id", "")
        if not available_ids:
            return
        # Resolve ids -> snapshot Player objects (kept as objects so
        # filters, sorting, and player cards work on real data).
        try:
            _all = []
            _lg = getattr(self, "league", None)
            for _t in (getattr(_lg, "teams", None) or []):
                for _attr in ("roster", "ahl_roster", "prospects"):
                    _all.extend(getattr(_t, _attr, None) or [])
            _all.extend(getattr(_lg, "free_agents", None) or [])
            _by_id = {str(getattr(p, "id", "")): p for p in _all}
        except Exception:
            _by_id = {}
        players = [_by_id[str(_pid)] for _pid in available_ids
                   if str(_pid) in _by_id]
        if not players and shortlist:
            # Shortlist-only fallback: dicts can't drive filters/cards,
            # so there is nothing useful to show.
            return
        if not players:
            return
        self._mp_draft_pick_window(
            title=f"Fantasy pick #{overall} (Round {round_num}) -- "
                  f"your selection",
            players=players, board=board, my_team_id=team_id,
            clock_id=clock_id, action_name="fantasy_draft_pick",
            answer_attr="_mp_fantasy_answer",
            expire_toast="Fantasy clock expired -- auto-pick.",
            draft_button_text="DRAFT SELECTED PLAYER",
            extra_columns=())

    def _mp_show_promote_card(self, reason):
        """Non-modal disconnect card: offer host promotion without
        blocking. The last-synced state stays browsable either way."""
        # Native: route through _ui_notify; the UI layer shows the card.
        self._ui_notify("mp_disconnected", reason)

    def _mp_show_trade_offer(self, payload):
        """Human-to-human trade offer from another manager.

        Native: route through _ui_notify; the UI layer shows the
        Accept/Reject dialog and calls back via _mp_answer_trade_offer.
        """
        self._ui_notify("mp_trade_offer", payload)

    def _mp_answer_trade_offer(self, offer_id, decision):
        """UI callback: answer a human-to-human trade offer."""
        if decision not in ("accept", "reject"):
            return
        if self.mp_client is None:
            return
        try:
            self.mp_client.send_trade_response(offer_id, decision)
        except Exception as e:
            self._mp_toast(f"Trade answer failed: {e}")

    def _mp_sign_free_agent(self, params, team, manager):
        """Sign a free agent: same contract mutation the FA view applies
        (salary / years / signing bonus / NTC flag on the live contract)."""
        # ELC branch: the client is signing an unsigned rights-held prospect.
        # Route through the same negotiated ELC path as single-player, with
        # the acting manager's team (not the host's user_team).
        if params.get("elc"):
            _pid = str(params.get("player_id", ""))
            _prospect = None
            try:
                for _p in getattr(team, "prospects", []) or []:
                    if str(getattr(_p, "id", "")) == _pid:
                        _prospect = _p
                        break
            except Exception:
                pass
            if _prospect is None:
                return False, "That prospect isn't in your system."
            try:
                _res = self.handle_elc_offer(
                    _prospect, params.get("salary", 0),
                    params.get("signing_bonus", 0),
                    params.get("performance_bonus", 0), team=team)
            except Exception as e:
                return False, f"ELC signing failed: {e}"
            _v = (_res or {}).get("verdict")
            if _v == "accepted":
                return True, f"Signed {_prospect.full_name} to an ELC."
            return False, (_res or {}).get("note") or f"ELC offer {_v}."
        player = self._mp_find_free_agent(params.get("player_id", ""))
        if player is None:
            return False, "That player is no longer a free agent."
        # Draft lock: draft-eligible players can't be signed as free agents
        # (shared rule with single-player -- no sidestepping the draft).
        try:
            from draft_generator import player_locked_by_draft as _locked
            if _locked(player):
                return False, (f"{player.full_name} is draft-eligible and "
                               f"can't be signed as a free agent.")
        except Exception:
            pass
        try:
            salary = int(params.get("salary", 0))
            years = int(params.get("years", 0))
        except (TypeError, ValueError):
            return False, "Invalid contract terms."
        # Same rulebook as single-player: league minimum, 20%-of-cap max,
        # 7-year max for new deals, live-cap budget, draft lock.
        ok, err = self._validate_contract_terms(player, salary, years,
                                                extension=False, team=team)
        if not ok:
            return False, err
        if len(getattr(team, "roster", []) or []) >= 23:
            return False, "Roster is full (23)."
        if salary > self._mp_cap_room(team):
            return False, "Not enough cap space."
        bonus = 0
        try:
            bonus = max(0, int(params.get("signing_bonus", 0) or 0))
        except (TypeError, ValueError):
            pass
        ntc = bool(params.get("ntc", False))
        try:
            import trade_engine as te
            if ntc and not te.clause_eligible(player):
                return False, \
                    f"{player.full_name} isn't eligible for a no-trade clause."
        except Exception:
            pass
        contract = getattr(player, "contract", None)
        if contract is None:
            return False, "That player has no contract to sign."
        contract.salary = salary
        contract.years_remaining = years
        try:
            # Owner cash budget (Eastside): the signing bonus must fit
            # the remaining player budget, else the deal is refused.
            if bonus > 0:
                from salary_cap_system import charge_signing_bonus as _chgb
                if not _chgb(team, bonus):
                    return False, (
                        f"Ownership won't approve the ${bonus:,} signing "
                        f"bonus -- over the remaining player budget.")
            contract.signing_bonus = bonus
        except Exception:
            pass
        try:
            contract.no_trade_clause = bool(ntc)
        except Exception:
            pass
        try:
            contract.ntc_waiver_for = ""
        except Exception:
            pass
        # A new SPC starts with no retained salary: the old deal's discount
        # and two-club history die with it (the retaining club's ledger
        # entry survives independently, per CBA).
        try:
            import trade_engine as _te_clr
            _te_clr.clear_retention_state(player)
        except Exception:
            pass
        # Market feedback: Caleb's market engine learns from MP signings
        # exactly like user and AI signings. register_signing keeps only
        # true market-setters (star + top-5 AAV) as comps, so a bold MP
        # overpay for a star raises the next star's ask -- offers change
        # the league. (The human fallout -- overpay verdict, fan beef --
        # stays on the user/AI paths: the MP path has no agent ask to
        # score the deal against.)
        try:
            _lg_mp = getattr(self, "league", None)
            _cap_sys_mp = getattr(_lg_mp, "salary_cap_system", None)
            if _cap_sys_mp is not None:
                _ppos = getattr(player, "primary_position", "")
                _ppos_name = (_ppos.value if hasattr(_ppos, "value")
                              else str(_ppos))
                try:
                    from game_classes import to_100_scale as _t100mp
                    _ovr100mp = int(_t100mp(player.overall_rating()))
                except Exception:
                    _ovr100mp = 75
                if _cap_sys_mp.register_signing(
                        getattr(player, "full_name", "Unknown"), salary,
                        _ovr100mp, _ppos_name,
                        int(getattr(player, "age", 27) or 27),
                        int(getattr(_lg_mp, "season_year", 0) or 0)):
                    try:
                        self.news_log.append({
                            'date': self.current_date,
                            'story': (f"{player.full_name}'s ${salary:,} "
                                      f"deal sets the market -- comparable "
                                      f"stars will demand more.")})
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            fa_pool = self.free_agents() or []
            if player in fa_pool:
                fa_pool.remove(player)
        except Exception:
            pass
        team.add_player(player)
        # Rivalry lifecycle: an MP free-agent signing is a transfer, same
        # as the single-player path -- personal beefs follow the man.
        try:
            from reputation_system import on_player_transfer as _opt
            _rivs = getattr(getattr(self, "league", None), "rivalries", None)
            if isinstance(_rivs, list):
                _opt(_rivs, player, from_team=None, to_team=team)
        except Exception:
            pass
        # Dressing room: the room reacts to WHO arrives, bounded.
        try:
            import dressing_room as _dr_arr
            _dr_arr.cascade_on_arrival(
                team, player, how="signing",
                date_str=str(getattr(self, "current_date", "")))
        except Exception:
            pass
        try:
            self.add_news(
                f"{player.full_name} signed by {team.team_name}: "
                f"{years} years at ${salary:,}/year.")
        except Exception:
            pass
        return True, f"Signed {player.full_name} ({years}y, ${salary:,}/yr)."

    def _mp_snapshot_failed(self, message):
        """A host snapshot that won't load is fatal for a client -- say so
        loudly instead of leaving a black/broken window."""
        self._ui_notify("error", "Could not join", message)
        self._ui_notify("mp_snapshot_failed", message)

    def _mp_staff_renew(self, params, team, manager):
        """Re-sign an expired staffer (years 1/2/3) or let him walk."""
        import staff_renewals as _sr
        sid = str(params.get("staff_id", "") or "")
        years = params.get("years", None)
        try:
            years = int(years) if years is not None else None
        except (TypeError, ValueError):
            years = None
        # Ownership: the staffer must belong to the acting club.
        try:
            _ids = {str(getattr(s, "id", ""))
                    for s in (getattr(team, "staff", None) or [])}
            if sid not in _ids:
                return False, "That staffer isn't on your club."
        except Exception:
            pass
        try:
            ok, lines = _sr.apply_renewal_decision(
                self.league, sid, years)
        except Exception as e:
            return False, f"Renewal failed: {e}"
        self._mp_mark_inbox_decision(team, params.get("message_id", ""),
                                     sid, years, done_key="offers")
        for _ln in lines or []:
            try:
                _emo = "✍️ " if years else "🚶 "
                self.add_news(_emo + str(_ln))
            except Exception:
                pass
        return (True, "Staffer re-signed." if years else
                "Staffer walks to the pool.") if ok else \
            (False, "Renewal failed.")

    def _mp_start_practice_plan(self, params, team, manager):
        """Start a multi-day practice plan: mirrors the practice view's
        schedule_practice call against the canonical state."""
        player = self._mp_team_player(team, params.get("player_id", ""))
        if player is None:
            return False, "That player isn't on your club."
        try:
            from enhanced_practice_system import (
                PracticeType, PracticeIntensity)
            ptype = PracticeType(params.get("practice_type", ""))
            intensity = PracticeIntensity(params.get("intensity", ""))
            total = int(params.get("total_sessions", 0))
        except (ValueError, TypeError):
            return False, "Invalid practice plan parameters."
        if total <= 0:
            return False, "Practice plan needs at least one session."
        try:
            engine = getattr(self, "practice_engine", None)
            if engine is None:
                # Fall back to a fresh engine (takes no constructor args;
                # histories are module-level shared state).
                from enhanced_practice_system import PracticeEngine
                engine = PracticeEngine()
            result = engine.schedule_practice(player, ptype, intensity, total)
        except Exception as e:
            return False, f"Practice scheduling failed: {e}"
        if getattr(result, "success", False):
            return True, f"Practice plan started for {player.full_name}."
        return False, getattr(result, "message", "Schedule failed.")

    def _mp_team_context(self, team):
        """Host-side equivalent of the Morale window's team context."""
        ctx = {"win_pct": 0.5, "room_leadership": 50, "losing_streak": 0}
        try:
            import reputation_system as rs
            st = (getattr(getattr(self, "league", None), "standings", None)
                  or {}).get(getattr(team, "team_name", ""), {})
            w = st.get("W", st.get("Wins", 0))
            l = st.get("L", st.get("Losses", 0))
            otl = st.get("OTL", 0)
            ctx["win_pct"] = w / max(1, w + l + otl)
            ctx["losing_streak"] = int(st.get("losing_streak", st.get("streak", 0)) or 0)
            leaders = rs.team_hierarchy(list(getattr(team, "roster", []) or [])
                                        ).get("Team Leaders", [])
            if leaders:
                ctx["room_leadership"] = sum(
                    getattr(p, "leadership", 50) or 50 for p in leaders) / len(leaders)
        except Exception:
            pass
        return ctx

    def _mp_team_talk(self, params, team, manager):
        """Deliver a team talk: the same give_talk() the coach's whiteboard
        uses -- same tones, same momentum queue, same outcome tiers.

        Two shapes: tone-based {tone, situation, speaker, ...} (dressing
        room whiteboard) and option-based {option: {...}, context: {...}}
        (manager-hub / inbox bundle talks via mc.apply_team_talk)."""
        # Option-based branch (manager hub + inbox bundle).
        if isinstance(params.get("option"), dict):
            try:
                import manager_career as _mc
            except Exception:
                return False, "Dressing room isn't available."
            _opt = dict(params.get("option") or {})
            _ctx = dict(params.get("talk_context") or {})
            # Sanity bounds: the option rides from the client's snapshot;
            # clamp to the ranges the SP UI can produce.
            try:
                _opt["boost"] = max(0.5, min(2.0,
                                            float(_opt.get("boost", 1.0))))
            except (TypeError, ValueError):
                _opt["boost"] = 1.0
            try:
                _opt["morale"] = max(-5, min(5,
                                             int(_opt.get("morale", 0))))
            except (TypeError, ValueError):
                _opt["morale"] = 0
            if _opt.get("fit") not in ("good", "risky", "neutral"):
                _opt["fit"] = "neutral"
            try:
                reaction, boost = _mc.apply_team_talk(team, _opt, _ctx)
            except Exception as e:
                return False, f"Team talk failed: {e}"
            return True, str(reaction or "The room heard you.")
        try:
            import dressing_room as _dr
        except Exception:
            return False, "Dressing room isn't available."
        tone = str(params.get("tone", "calm") or "calm").lower()
        if tone not in ("calm", "fired-up", "cautious"):
            return False, "Tone must be calm, fired-up or cautious."
        situation = str(params.get("situation", "pregame") or "pregame")
        if situation not in ("pregame", "intermission"):
            situation = "pregame"
        speaker = str(params.get("speaker", "coach") or "coach")
        if speaker not in ("coach", "captain"):
            speaker = "coach"
        score_state = str(params.get("score_state", "tied") or "tied")
        if score_state not in ("leading", "trailing", "tied"):
            score_state = "tied"
        try:
            rival = bool(params.get("rival", False))
            streak = int(params.get("streak", 0) or 0)
        except (TypeError, ValueError):
            rival, streak = False, 0
        try:
            out = _dr.give_talk(
                team, tone,
                {"situation": situation, "score_state": score_state,
                 "rival": rival, "streak": streak},
                speaker)
        except Exception as e:
            return False, f"Team talk failed: {e}"
        tier = (out or {}).get("tier", "steady") if isinstance(out, dict) \
            else "steady"
        return True, f"Team talk delivered ({tone}, {tier})."

    def _rebuild_news_log_from_stories(self):
        """Rebuild the GUI news feed from the canonical news_stories list.

        news_stories is the save/snapshot copy every manager (including
        multiplayer clients) receives; the GUI news_log is the local view.
        """
        try:
            from datetime import date as _date
            stories = getattr(getattr(self, 'game_manager', None),
                              'news_stories', None) or []
            rebuilt = []
            for item in stories:
                if isinstance(item, dict):
                    d = item.get('date')
                    if isinstance(d, str):
                        try:
                            d = _date.fromisoformat(d)
                        except ValueError:
                            pass
                    rebuilt.append({'date': d, 'story': item.get('story', '')})
            self.news_log = rebuilt
        except Exception:
            pass


    def _mp_head_coach(self, team):
        try:
            for stf in getattr(team, "staff", []) or []:
                if "Head Coach" in str(getattr(getattr(stf, "role", None), "value", "")):
                    return stf
        except Exception:
            pass
        return None

    def _apply_rivalry_action(self, action, params, team):
        """Apply a client's rivalry declaration/renounce to canonical state.

        The league's rivalry list syncs to every manager via STATE_SYNC, so a
        declared hate is immediately everyone's problem.
        """
        import reputation_system as rs
        import headlines as hl
        league = getattr(self, "league", None)
        if league is None:
            return False, "no league loaded"
        target_team = self._mp_find_team(str(params.get("target_team", "")))
        kind = str(params.get("target_kind", "team"))
        if kind not in ("team", "coach"):
            return False, "target_kind must be team or coach"
        try:
            if action == "declare_rivalry":
                rec, label = rs.declare_rivalry_for_gm(league, team,
                                                       target_team, kind)
                try:
                    hl.announce_rivalry_declaration(
                        self, getattr(team, "team_name", "?"),
                        getattr(target_team, "team_name", "?"), label, kind)
                except Exception:
                    pass
                return True, (f"Rivalry declared vs {label} "
                              f"(heat {rec['intensity']:.0f})")
            ok = rs.renounce_rivalry_for_gm(league, team, target_team, kind)
            return (True, "Declaration renounced; the hate cools.") if ok else \
                (False, "no live declaration to renounce")
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"action failed: {e}"

    def get_settings(self):
        """Get current user settings or defaults (never builds a window)."""
        if not hasattr(self, 'user_settings'):
            # Load default settings if not already loaded. Reads
            # settings.json directly -- constructing a SettingsWindow here
            # used to flash a GUI and break headless/test use.
            try:
                from settings_window import load_settings
                self.user_settings = load_settings()
            except Exception:
                # Fallback to basic defaults
                self.user_settings = {
                    'game_results': {
                        'show_user_team_only': True,
                        'default_leagues': ['National Hockey League'],
                        'max_games_display': '50',
                        'max_news_display': '10',
                        'default_news_categories': ['Team News', 'League News', 'Trades', 'Injuries']
                    }
                }
        return self.user_settings

    def _calculate_player_ratings(self, game_stats, events):
        """Calculate player ratings out of 10 based on game performance"""
        ratings = {}
        
        for team_name, team_stats in game_stats.items():
            ratings[team_name] = {}
            for player_id, stats in team_stats.items():
                # Base rating starts at 5.0
                rating = 5.0
                
                # Goals are very valuable (+1.5 each)
                rating += stats.get('goals', 0) * 1.5
                
                # Assists are valuable (+1.0 each)
                rating += stats.get('assists', 0) * 1.0
                
                # Shots show offensive involvement (+0.1 each)
                rating += stats.get('shots', 0) * 0.1
                
                # Saves for goalies (+0.05 each)
                rating += stats.get('saves', 0) * 0.05
                
                # Time on ice shows involvement (+0.001 per second)
                rating += stats.get('toi', 0) * 0.001
                
                # Penalties hurt rating (-0.5 each)
                rating -= stats.get('penalties', 0) * 0.5
                
                # Cap rating between 1 and 10
                rating = max(1.0, min(10.0, rating))
                ratings[team_name][player_id] = round(rating, 1)
        
        return ratings

    def _snapshot_game_toi_fatigue(self, sim_engine, home_team, away_team):
        """Per-game TOI (seconds) + fatigue snapshots from the sim that ran
        the game, for the game-results player-stats tab.

        Integration read only: quick-sim stats ({team_name: {pid: {...}}}),
        GameSim's player_toi_seconds / player_fatigue / goaltender_fatigue
        ledgers (energy is 0-100 remaining, so fatigue = 100 - energy).
        Missing data stays missing -- the tab renders 'N/A' for it.
        """
        toi, fatigue = {}, {}
        sim = sim_engine
        # Quick-sim / AdvancedGameSim per-player stats
        try:
            stats = getattr(sim, 'stats', None) or {}
            for team in (home_team, away_team):
                pmap = stats.get(getattr(team, 'team_name', None), {}) or {}
                for pid, st in pmap.items():
                    if not isinstance(st, dict):
                        continue
                    if st.get('toi'):
                        toi[pid] = float(st.get('toi') or 0)
                    if st.get('fatigue'):
                        fatigue[pid] = float(st.get('fatigue') or 0)
        except Exception:
            pass
        # GameSim ledgers
        try:
            for pid, sec in (getattr(sim, 'player_toi_seconds', None)
                             or {}).items():
                if sec:
                    toi[pid] = float(sec)
        except Exception:
            pass
        try:
            _pf = getattr(sim, 'player_fatigue', None) or {}
            _gf = getattr(sim, 'goaltender_fatigue', None) or {}
            for pid, energy in list(_pf.items()) + list(_gf.items()):
                fatigue[pid] = max(0.0, 100.0 - float(energy or 0))
        except Exception:
            pass
        # Dressed goalies skate the whole game (mirrors the post-game wear
        # read): only fill in when the ledger has no entry.
        try:
            _gsec = float(getattr(sim, '_w3_game_seconds', 0.0) or 0.0)
            if _gsec > 0:
                for team in (home_team, away_team):
                    for p in getattr(team, 'roster', []) or []:
                        if getattr(p, 'primary_position', None) is PlayerPosition.GOALIE:
                            toi.setdefault(getattr(p, 'id', None), _gsec)
        except Exception:
            pass
        return toi, fatigue

    @staticmethod
    def _snapshot_team_lines(team):
        """Snapshot one club's even-strength line combos as player IDs.

        Thin wrapper over game_classes.snapshot_team_lines (the shared
        implementation also used by the box score Lines tab fallback).
        Never raises. (Muck 2026-10-02: post-game lines with combined
        ratings.)"""
        try:
            from game_classes import snapshot_team_lines as _snap
            return _snap(team)
        except Exception:
            return None

    def _snapshot_game_lines(self, home_team, away_team):
        """Stamp both clubs' line combos onto a game result. Never raises."""
        try:
            out = {}
            for team in (home_team, away_team):
                name = getattr(team, "team_name", None) or str(team)
                snap = self._snapshot_team_lines(team)
                if snap:
                    out[name] = snap
            return out
        except Exception:
            return {}

    def _generate_daily_emails(self):
        """Generate daily emails based on game events and random occurrences."""
        from game_classes import EmailGenerator
        import random
        
        # 1. Check for player injuries and generate injury reports (only for actual injuries)
        for player in self.user_team.roster + getattr(self.user_team, 'ahl_roster', []):
            if hasattr(player, 'is_injured') and player.is_injured:
                # Random chance to get injury update for actually injured players
                if random.random() < 0.3:  # 30% chance per day
                    # Use the player's ACTUAL injury data, not random flavor text
                    # (Muck 2026-10-02: fake injury reports were confusing)
                    try:
                        _itype = str(getattr(player, 'injury_type', '') or '').strip()
                        if not _itype or _itype.lower() in ('none', 'healthy', ''):
                            _itype = "Undisclosed injury"
                    except Exception:
                        _itype = "Undisclosed injury"
                    try:
                        _games = int(getattr(player, 'games_remaining_injured', 0) or 0)
                    except Exception:
                        _games = 0
                    if _games > 0:
                        _return = f"~{_games} games"
                    else:
                        _return = "Day-to-day"
                    injury_email = EmailGenerator.create_injury_report_email(
                        player.full_name,
                        _itype,
                        _return
                    )
                    self.send_email_to_user(injury_email)
        
        # 2. Scouting report completions (only for actual prospects in the system)
        available_prospects = getattr(self.user_team, 'prospects', []) + getattr(self.league, 'draft_prospects', [])
        if random.random() < 0.15 and available_prospects:  # 15% chance per day if prospects exist
            # Use actual scouts from team staff
            scouts = [staff for staff in getattr(self.user_team, 'staff', []) 
                     if 'scout' in staff.role.value.lower()]
            
            if scouts:
                scout = random.choice(scouts)
                prospect = random.choice(available_prospects)
                grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D"]
                
                scout_email = EmailGenerator.create_scouting_report_email(
                    scout.full_name,
                    prospect.full_name,
                    random.choice(grades)
                )
                self.send_email_to_user(scout_email)
        
        # 3. Contract negotiation updates (only for players with expiring contracts)
        if random.random() < 0.1:  # 10% chance per day
            # Find players with contracts expiring soon
            expiring_players = [p for p in self.user_team.roster 
                              if hasattr(p, 'contract') and p.contract and p.contract.years_remaining <= 1]
            
            if expiring_players:
                player = random.choice(expiring_players)
                agent_names = ["Mike Johnson", "Sarah Williams", "John Anderson", "Lisa Thompson"]
                
                # Generate realistic contract demands based on player rating
                if player.overall_rating() >= 85:
                    demand_range = "$8-12M per year"
                    years = "8 years"
                elif player.overall_rating() >= 78:
                    demand_range = "$5-8M per year" 
                    years = "6 years"
                elif player.overall_rating() >= 70:
                    demand_range = "$3-5M per year"
                    years = "4 years"
                else:
                    demand_range = "$1-3M per year"
                    years = "2-3 years"
                
                demand = f"My client {player.full_name} is seeking a {years} extension worth {demand_range}."
                
                contract_email = EmailGenerator.create_contract_negotiation_email(
                    player.full_name,
                    random.choice(agent_names),
                    demand
                )
                self.send_email_to_user(contract_email)
        
        # 4. Media requests (based on actual team performance)
        if random.random() < 0.08:  # 8% chance per day
            journalists = ["Sports Reporter", "Hockey Insider", "Beat Writer", f"{self.user_team.city} Times Reporter"]
            
            # Generate topics based on team situation
            topics = []
            
            # Add performance-based topics
            if hasattr(self.user_team, 'wins') and hasattr(self.user_team, 'losses'):
                if self.user_team.wins > self.user_team.losses:
                    topics.extend([
                        "the team's strong start to the season",
                        "what's been working well for the team",
                        "maintaining momentum going forward"
                    ])
                else:
                    topics.extend([
                        "how to turn the season around",
                        "addressing the team's recent struggles",
                        "changes being considered"
                    ])
            
            # Add general topics
            topics.extend([
                "upcoming roster decisions",
                "the development of young players", 
                "team chemistry and leadership",
                "expectations for the remainder of the season"
            ])
            
            media_email = EmailGenerator.create_media_request_email(
                random.choice(journalists),
                random.choice(topics)
            )
            self.send_email_to_user(media_email)
        
        # 5. League announcements (based on actual date and season context)
        if self.current_date.day == 1:  # First of every month
            month_name = self.current_date.strftime("%B")
            announcements = [
                (f"{month_name} League Update", f"League standings and statistical leaders for {month_name}."),
                ("Upcoming Schedule", f"Important games and events scheduled for {month_name}."),
                ("Player Safety Update", "Monthly reminder about player safety protocols and equipment checks.")
            ]
            
            subject, content = random.choice(announcements)
            league_email = EmailGenerator.create_league_announcement_email(subject, content)
            self.send_email_to_user(league_email)
        
        # 6. Trade deadline notifications (based on actual calendar)
        try:
            from trade_deadline_manager import trade_deadline_date as _tdd
            _dl = _tdd(getattr(self, "league", None),
                       deadline_year=self.current_date.year)
        except Exception:
            _dl = date(self.current_date.year, 3, 8)
        if _dl is not None:
            days_to_deadline = (_dl - self.current_date).days
            if 0 <= days_to_deadline <= 7 and random.random() < 0.5:
                deadline_email = EmailGenerator.create_league_announcement_email(
                    f"Trade Deadline Alert - {days_to_deadline} Days Remaining",
                    f"The NHL trade deadline is in {days_to_deadline} days. All trades must be completed by 3:00 PM EST on {_dl.strftime('%B %-d')}.\n\n"
                    f"Current roster size: {len(self.user_team.roster)} players\n"
                    f"Salary cap space: ${self.user_team.cap_space:,}"
                )
                deadline_email.is_urgent = True
                deadline_email.priority = 4
                self.send_email_to_user(deadline_email)

    def _generate_post_game_emails(self, game_result, opponent, result, user_score, opp_score, notable_events):
        """Generate emails after user team games based on actual game events."""
        from game_classes import EmailGenerator
        import random
        
        # 1. Post-game media summary (always after games)
        if random.random() < 0.7:  # 70% chance
            # Initialize summary with default value
            summary = f"Game ended {user_score}-{opp_score} against {opponent.team_name}"
            
            if result == "won":
                if user_score - opp_score >= 3:
                    summary = f"Dominant performance leads to {user_score}-{opp_score} victory over {opponent.team_name}"
                elif user_score > opp_score:
                    summary = f"Solid {user_score}-{opp_score} win against {opponent.team_name}"
            else:
                if opp_score - user_score >= 3:
                    summary = f"Team struggles in {opp_score}-{user_score} loss to {opponent.team_name}"
                else:
                    summary = f"Close {opp_score}-{user_score} loss to {opponent.team_name}"
            
            # Add notable events to summary
            goal_scorers = [event['player'].full_name for event in notable_events 
                          if event['event'] in ['Goal', 'Shootout Goal'] and 
                          event['player'] in self.user_team.roster]
            
            if goal_scorers:
                content = f"Game Summary:\n\n{summary}\n\n"
                content += f"Goal scorers: {', '.join(goal_scorers)}\n\n"
                content += f"The team will review game tape and prepare for the next matchup."
            else:
                content = f"Game Summary:\n\n{summary}\n\nThe team will analyze the performance and prepare for the next game."
            
            media_email = EmailGenerator.create_media_request_email(
                f"{self.user_team.city} Sports Reporter",
                content
            )
            media_email.subject = f"Post-Game: {self.user_team.team_name} vs {opponent.team_name}"
            self.send_email_to_user(media_email)
        
        # 2. Outstanding performance recognition
        for event in notable_events:
            if event['event'] == 'Hat Trick' and event['player'] in self.user_team.roster:
                recognition_email = EmailGenerator.create_league_announcement_email(
                    f"Hat Trick Recognition: {event['player'].full_name}",
                    f"Congratulations to {event['player'].full_name} on achieving a hat trick in tonight's game!\n\n"
                    f"This outstanding performance showcases the skill and dedication that makes hockey great.\n\n"
                    f"NHL Player Recognition Committee"
                )
                recognition_email.is_important = True
                self.send_email_to_user(recognition_email)
        
        # 3. Injury reports from game — only for ACTUAL injuries tracked by the
        # sim (Muck 2026-10-02: removed fake random injury reports that were
        # sent for healthy players without setting any injury fields).
        # Real injuries are reported via _generate_daily_emails above.

    def _grudge_week_grade(self, game_date, home_team, away_team,
                           home_score, away_score, went_to_ot, fights=0):
        """Post-game: call out hollow overhype when the game fizzled."""
        try:
            _mk = (home_team.team_name, away_team.team_name, str(game_date))
            _gm = getattr(self, "_grudge_marketed", None)
            if not (isinstance(_gm, set) and _mk in _gm):
                return
            _gm.discard(_mk)
            _margin = abs(home_score - away_score)
            if _margin >= 4 and not went_to_ot and fights == 0:
                self.add_news(
                    f"All that hype for this? "
                    f"{away_team.team_name} @ {home_team.team_name} "
                    f"fizzles {_margin} goals apart -- the fans feel sold "
                    f"a bill of goods.")
        except Exception:
            pass

    @staticmethod

    def _result_date_key(value):
        """Normalize a result's mixed-format date to a datetime.date."""
        try:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, str):
                return datetime.strptime(value, '%Y-%m-%d').date()
            if isinstance(value, date):
                return value
        except (ValueError, AttributeError, TypeError):
            pass
        return None

    def is_trade_deadline_day(self):
        """Game-date check: is today trade deadline day (derived)?"""
        try:
            from trade_deadline_manager import get_deadline_manager
            return get_deadline_manager(self).is_deadline_day(
                self.current_date)
        except Exception:
            return False

    def _set_current_date(self, d):
        """Set the game date on the game manager.

        Moved from HockeyManagerGUI: the GUI version also synced
        game_manager.current_date, but inside GameManager we ARE the
        manager, so a single assignment suffices.
        """
        self.current_date = d

    def update_inbox_notification(self):
        """Update the inbox button notification (UI shim: routes via _ui_notify)."""
        self._ui_notify('inbox_notification_updated')

    def _slate_deterministic_result(self, home_team, away_team, game_date):
        """Deterministic last-resort result (slate-guarantee tier 2).

        Compares average roster overall_rating with a small home-ice edge,
        rolls a seeded RNG (game date + team names -- reproducible), and
        produces a plausible scoreline: winner 2-5, loser 0..winner-1,
        occasional overtime (then a one-goal game). Team-symmetric apart
        from the home edge -- swapping the clubs swaps the outcome
        distribution. Writes no stats and touches no systems; the normal
        post-processing (standings etc.) treats it like any result. This
        is a FALLBACK, never a cheat path: every use is logged loudly via
        _log_slate_fallback and counted in _slate_fallbacks.
        """
        import random

        def _avg_overall(team):
            try:
                _rs = []
                for _p in (getattr(team, 'roster', None) or []):
                    try:
                        _rs.append(float(_p.overall_rating()))
                    except Exception:
                        pass
                if _rs:
                    return sum(_rs) / len(_rs)
            except Exception:
                pass
            return 75.0  # neutral rating when the roster is unreadable

        _hn = getattr(home_team, 'team_name', None) or '?'
        _an = getattr(away_team, 'team_name', None) or '?'
        _home = _avg_overall(home_team) + 1.5  # small home-ice edge, rating pts
        _away = _avg_overall(away_team)
        _rng = random.Random(f"slate-guarantee|{game_date}|{_hn}|{_an}")
        # Logistic win probability on the rating gap; symmetric in the two
        # clubs apart from the home edge. ~8 rating points ~= 70/30.
        _p_home = 1.0 / (1.0 + 10.0 ** (-(_home - _away) / 8.0))
        _p_home = max(0.10, min(0.90, _p_home))
        _home_wins = _rng.random() < _p_home
        _wg = _rng.randint(2, 5)
        _ot = _rng.random() < 0.22
        _lg = _wg - 1 if _ot else _rng.randint(0, _wg - 1)
        if _home_wins:
            return home_team, away_team, (_wg, _lg), _ot, None
        return away_team, home_team, (_lg, _wg), _ot, None

    def _hold_draft_lottery(self, year):
        """Televised draft lottery (May 8). Real weighted odds, inbox card
        with a watch-the-reveal action, fan/room reactions for the user."""
        from draft_lottery import (run_lottery, lottery_reveal_text,
                                   apply_user_reactions)
        league = self.league
        league.initialize_all_draft_picks()
        rows = run_lottery(league, year)
        if not rows:
            return
        # Stash for the inbox "watch the reveal" action (the inbox reads it
        # off game_manager).
        _gm = getattr(self, "game_manager", None) or self
        _gm._pending_lottery_reveal = {
            "year": year, "rows": rows, "app": self,
        }
        summary = lottery_reveal_text(rows, year)
        try:
            from headlines import make_headline, deliver
            msg = make_headline("lottery_results", self.current_date, year=year,
                                summary=summary)
            if msg is not None:
                deliver(self, msg)
        except Exception:
            try:
                self.add_news(summary)
            except Exception:
                pass
        apply_user_reactions(self, rows)
        # Ledger memory: the lottery is a league event worth remembering.
        try:
            from narrative_ledger import active_ledger
            led = active_ledger()
            if led is not None:
                winner = rows[0]["team"]
                _dup = any(e.get("kind") == "draft_lottery"
                           and e.get("facts", {}).get("year") == year
                           for e in led.events)
                if not _dup:
                    led.record(
                        "draft_lottery", teams=[winner], weight=40,
                        facts={"year": year, "winner": winner,
                               "second": rows[1]["team"] if len(rows) > 1 else ""},
                        text=(f"{winner} won the {year} draft lottery "
                              f"(#1 overall)."))
        except Exception:
            pass

    def _hold_entry_draft(self, year):
        """Hold the annual entry draft"""
        print(f"🏒 ENTRY DRAFT {year} BEGINS! 🏒")
        
        # Generate draft prospects if they don't exist. The class is stamped
        # with its draft year: if last year's draft never ran (board never
        # opened), the stale class must NOT be reused for this year's draft.
        _prospect_year = getattr(self.league, 'draft_prospects_year', None)
        if not self.league.draft_prospects or _prospect_year != year:
            print("Generating draft prospects...")
            from draft_generator import generate_draft_class
            draft_quality = self.get_settings().get('simulation', {}).get('draft_class_quality', 'Normal')
            # Undrafted re-entry (real NHL rule): undrafted prospects are
            # automatically eligible again while still draft-eligible for
            # the new draft year (NA 18-20, Europeans 18-22 on Sept 15).
            # Aged-out undrafted players become free agents instead of
            # re-entering the draft pool.
            _undrafted = list(getattr(self.league, "undrafted_pool", None) or [])
            self.league.undrafted_pool = []
            if _undrafted:
                try:
                    from draft_generator import is_draft_eligible as _elig
                    _fa = getattr(self.league, "free_agents", None)
                    for _up in _undrafted:
                        try:
                            if _elig(getattr(_up, "birth_date", ""),
                                     getattr(_up, "nationality", ""), year):
                                _re = getattr(self.league, "draft_reentries",
                                              None)
                                if not isinstance(_re, list):
                                    _re = []
                                    self.league.draft_reentries = _re
                                if _up not in _re:
                                    _re.append(_up)
                                try:
                                    _up.draft_reentry = True
                                except Exception:
                                    pass
                            else:
                                try:
                                    _up.team_name = "Free Agent"
                                except Exception:
                                    pass
                                # Belt-and-suspenders: an aged-out player is a
                                # true free agent -- no stale rights stamps or
                                # re-entry flags may survive on him.
                                try:
                                    _up.rights_team = ""
                                    _up.rights_expiry_year = 0
                                    _up.rights_type = ""
                                    _up.camp_invite = False
                                    _up.draft_reentry = False
                                    _up.draft_reentry_from = ""
                                except Exception:
                                    pass
                                if isinstance(_fa, list) and \
                                        _up not in _fa:
                                    _fa.append(_up)
                        except Exception:
                            continue
                except Exception as _ure:
                    print(f"Undrafted re-entry processing failed: {_ure}")
            # draft_year / reentries params land with the draft_worker pass;
            # only pass what the installed signature accepts so un-patched
            # generators (and old saves) keep working.
            _gen_kwargs = {"num_prospects": 336, "quality": draft_quality}
            try:
                import inspect as _inspect
                _params = _inspect.signature(generate_draft_class).parameters
                if "draft_year" in _params:
                    _gen_kwargs["draft_year"] = year
                if "reentries" in _params:
                    _gen_kwargs["reentries"] = getattr(self.league, "draft_reentries", None)
            except Exception:
                pass
            self.league.draft_prospects = generate_draft_class(**_gen_kwargs)
            print(f"Generated {len(self.league.draft_prospects)} draft prospects")
            self.league.draft_prospects_year = year
            # Re-entries were folded into the class above; clear so they are
            # never double-added in a later draft.
            self.league.draft_reentries = []
            # Draft Story Engine: assign storylines to top prospects
            try:
                from draft_stories import assign_prospect_storylines, deliver_prospect_stories
                storylines = assign_prospect_storylines(self.league.draft_prospects)
                # Store on league for draft-day drama (projected ranks)
                self.league.prospect_storylines = storylines
                # Projected rank = index in the public consensus order
                # (draft_ranking), not current overall -- the projection is
                # about where the prospect is expected to GO.
                ranked = sorted(self.league.draft_prospects,
                                key=lambda p: getattr(p, 'draft_ranking', 0),
                                reverse=True)
                self.league.prospect_projected_rank = {
                    id(p): i + 1 for i, p in enumerate(ranked)
                }
                deliver_prospect_stories(self, storylines)
            except Exception as _dse:
                print(f"Draft storylines failed (non-fatal): {_dse}")
            # Part 3: headline storylines for the class -- posted as news
            # items ("title — text"), following the add_news pattern below.
            # Fully guarded: a missing news path never breaks the draft.
            try:
                from draft_stories import assign_headline_storylines as _ahsl
                for _story in (_ahsl(self.league.draft_prospects, year) or []):
                    try:
                        self.add_news(
                            "%s — %s" % (_story.get('title', 'Draft'),
                                         _story.get('text', '')))
                    except Exception:
                        pass
            except Exception as _ahse:
                print(f"Draft headline storylines failed (non-fatal): {_ahse}")
        
        # Ensure draft picks are set up
        self.league.initialize_all_draft_picks()
        
        # Simulate draft lottery for first round
        self.league.simulate_draft_lottery(year)

        # Draft-day market: the lottery set the order, so every GM knows
        # where they're picking -- the phones light up like the trade
        # deadline. AI clubs trade up for need fits, and rebuilding clubs
        # shop veterans to contenders holding late firsts. (Never runs for
        # fantasy drafts: no trading there, by design.)
        try:
            from draft_day_trades import run_draft_day_trading
            _ddt_deals = run_draft_day_trading(self.league, year, app=self)
            if _ddt_deals:
                self.add_news(
                    f"DRAFT BUZZ: {len(_ddt_deals)} draft-day deal(s) go down "
                    f"as GMs jockey for position.")
        except Exception as _dde:
            print(f"Draft-day trading failed (non-fatal): {_dde}")
        
        # Add news story about the draft
        draft_story = f"The {year} NHL Entry Draft begins today! Teams will select from a pool of {len(self.league.draft_prospects)} eligible prospects over 7 rounds."
        self.add_news(draft_story)
        # NOTE: no UI is opened here. The draft-day hub prompt (Draft Day
        # Central) follows immediately and its buttons open the draft board,
        # so draft day has a single entry point instead of two popups.

    def _calculate_season_awards(self, all_players):
        """Calculate award winners using the awards_race voting model.

        The same rankings the user sees in the Award Races tab decide the
        actual trophies -- no more display-vs-reality split. Each race
        mirrors real voting history (Hart: points + team success, Norris:
        modern offense-first D voting, Vezina: SV%/GAA/wins + GSAx, etc.).
        """
        awards = {}
        try:
            import awards_race as ar
        except ImportError:
            return awards

        players = [p for p in (all_players or []) if p is not None]
        teams = list(getattr(getattr(self, "league", None), "teams", []) or [])

        # Authoritative team strength map for Hart voting (from standings,
        # not player.team_name which may be stale).
        team_pct = {}
        for t in teams:
            gp = getattr(t, "games_played", 0) or 0
            pts = getattr(t, "points", 0) or 0
            team_pct[getattr(t, "team_name", "")] = (pts / (2 * gp)) if gp else 0.5
        # Authoritative player -> team map from roster membership. The
        # roster is the truth; player.team_name is just a label.
        roster_map = ar.roster_team_map(teams)

        def _info(entry):
            """Normalize a race entry to the {name, team, stats} contract."""
            if not entry:
                return None
            p = entry.get("player")
            if p is None:
                # Team-level award (Jennings, Adams)
                return {"name": entry.get("team") or entry.get("coach") or "?",
                        "team": entry.get("team", "?"),
                        "stats": ""} if entry else None
            name = getattr(p, "full_name", getattr(p, "name", "?"))
            try:
                _pid = int(getattr(p, "id", -1) or -1)
            except Exception:
                _pid = -1
            team = roster_map.get(_pid) or getattr(p, "team_name", "Unknown") or "Unknown"
            return {"name": name, "team": team, "stats": ""}

        def _top(race, award_name=None):
            try:
                r = race()
                top = r[0] if r else None
                # Rivalry lifecycle: a photo-finish award race gets
                # personal -- but only when at least one man has the
                # personality to take it personally (record_award_race
                # gates on base_controversy / fiery temperament).
                # Top two within 5% on the race's own score reads as a
                # genuinely contested vote. Runaways don't make enemies.
                # Additive: rivalries only.
                if award_name and r and len(r) >= 2:
                    try:
                        s1 = float(r[0].get("score", 0) or 0)
                        s2 = float(r[1].get("score", 0) or 0)
                        if s1 > 0 and (s1 - s2) / s1 < 0.05:
                            p1, p2 = r[0].get("player"), r[1].get("player")
                            if p1 is not None and p2 is not None \
                                    and p1 is not p2:
                                from reputation_system import \
                                    record_award_race as _rar
                                _rivs = getattr(
                                    getattr(self, "league", None),
                                    "rivalries", None)
                                if isinstance(_rivs, list):
                                    _rar(_rivs, p1, p2, award_name)
                    except Exception:
                        pass
                return top
            except Exception:
                return None

        # Hart Trophy - MVP (points + team success)
        e = _top(lambda: ar.hart_race(players, team_pct,
                                   roster_map=roster_map), "Hart Trophy")
        info = _info(e)
        if info:
            info["stats"] = f"{e['points']} pts ({e['team_pct']:.3f} team)"
        awards["Hart Trophy (MVP)"] = info

        # Ted Lindsay - most outstanding player, voted by the players
        # (less team-success bias than the Hart)
        e = _top(lambda: ar.lindsay_race(players, team_pct,
                                      roster_map=roster_map),
                 "Ted Lindsay Award")
        info = _info(e)
        if info:
            info["stats"] = f"{e['points']} pts ({e['team_pct']:.3f} team)"
        awards["Ted Lindsay Award (Most Outstanding Player)"] = info

        # Art Ross - pure points
        e = _top(lambda: ar.art_ross_race(players), "Art Ross Trophy")
        info = _info(e)
        if info:
            p = e["player"]
            info["stats"] = (f"{getattr(p, 'goals', 0)}G "
                             f"{getattr(p, 'assists', 0)}A = {e['points']} pts")
        awards["Art Ross Trophy (Scoring Leader)"] = info

        # Rocket Richard - pure goals
        e = _top(lambda: ar.rocket_race(players), "Rocket Richard Trophy")
        info = _info(e)
        if info:
            info["stats"] = f"{e['goals']} goals"
        # Canonical: one identifier, one display label. The real trophy
        # is the Maurice "Rocket" Richard Trophy -- no duplicates.
        awards['Maurice "Rocket" Richard Trophy'] = info

        # Vezina - DECIDED BY GM VOTE (31 AI GMs + human ballot).
        # The race models the profile GMs look for, but the 5-3-1 tally
        # in league.vezina_votes is authoritative once the vote is held.
        e = _top(lambda: ar.vezina_race(players), "Vezina Trophy")
        info = _info(e)
        if info:
            p = e["player"]
            sv = getattr(p, "saves", 0) / max(1, getattr(p, "shots_against", 0) or 1)
            info["stats"] = f".{int(sv * 1000)} SV%, {getattr(p, 'wins', 0)}W"
        # Override with the voted winner when the vote has been held.
        try:
            _vv = getattr(getattr(self, "league", None), "vezina_votes",
                          None) or {}
            _syr = str(int(getattr(getattr(self, "league", None),
                                   "season_year", -1) or -1))
            _voted = _vv.get(_syr)
            if _voted and _voted.get("winner_id") not in (None, -1):
                _wid = int(_voted["winner_id"])
                for _pl in players:
                    try:
                        if int(getattr(_pl, "id", -2) or -2) == _wid:
                            info = _info({"player": _pl})
                            if info:
                                _sv = getattr(_pl, "saves", 0) / max(
                                    1, getattr(_pl, "shots_against", 0) or 1)
                                info["stats"] = (
                                    f".{int(_sv * 1000)} SV%, "
                                    f"{getattr(_pl, 'wins', 0)}W "
                                    f"(GM vote)")
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        awards["Vezina Trophy (Best Goalie)"] = info

        # Norris - best defenseman (modern offense-first voting)
        e = _top(lambda: ar.norris_race(players), "Norris Trophy")
        info = _info(e)
        if info:
            info["stats"] = f"{e['points']} pts"
        awards["Norris Trophy (Best Defenseman)"] = info

        # Selke - best defensive forward
        e = _top(lambda: ar.selke_race(players), "Selke Trophy")
        info = _info(e)
        if info:
            info["stats"] = f"{e['score']:.1f} defensive score"
        awards["Selke Trophy (Defensive Forward)"] = info

        # Lady Byng - skill + sportsmanship (points discounted by PIM)
        e = _top(lambda: ar.byng_race(players), "Lady Byng Trophy")
        info = _info(e)
        if info:
            p = e["player"]
            info["stats"] = f"{e['points']} pts, {getattr(p, 'pim', 0)} PIM"
        awards["Lady Byng Trophy (Sportsmanship)"] = info

        # Calder - rookie of the year (NHL rookie eligibility)
        _syr = ar.calder_season_year(getattr(self, "current_date", None))
        e = _top(lambda: ar.calder_race(players, season_year=_syr), "Calder Trophy")
        info = _info(e)
        if info:
            info["stats"] = f"{e['points']} pts (rookie)"
        awards["Calder Trophy (Rookie of the Year)"] = info

        # Jennings - fewest team goals against
        e = _top(lambda: ar.jennings_race(teams))
        if e:
            awards["Jennings Trophy (Fewest GA)"] = {
                "name": e["team"], "team": e["team"],
                "stats": f"{e['goals_against']} GA"}
        else:
            awards["Jennings Trophy (Fewest GA)"] = None

        # Jack Adams - most overachieving coach
        e = _top(lambda: ar.adams_race(teams))
        if e:
            awards["Jack Adams (Best Coach)"] = {
                "name": e["coach"], "team": e["team"],
                "stats": f"+{e['score']:.3f} vs expectation"}
        else:
            awards["Jack Adams (Best Coach)"] = None

        return awards

    def _guarantee_offseason_tentpoles(self):
        """Run the draft lottery + entry draft when the calendar skipped them.

        The lottery (May 8) and entry draft (June 23-25) are date-triggered in
        _check_for_event_day, but _start_offseason jumps straight from the Cup
        to July 1 -- so in every path that completes the playoffs those dates
        are never simulated and the lottery + draft would be silently skipped
        (no prospects would ever enter the league). Run them here when the
        date-based path didn't; the per-year guards (lottery_held_years /
        draft_held_years) make this a no-op otherwise. Dates are set first so
        headlines, inbox cards and news land on the right day.
        """
        try:
            league = self.league
            # Season continuity (Muck 2026-10-02): draft_year derives from
            # GAME STATE, not date arithmetic. This method runs pre-rollover
            # (called from _start_offseason before league.end_of_season()),
            # so league.season_year is the just-completed season and its
            # entry draft is held in calendar year season_year + 1.
            # Manual date manipulation around the playoff gap can no longer
            # skip a season or mis-year the lottery/draft.
            draft_year = int(getattr(league, "season_year", 0) or 0) + 1
            # Sanity backstop: if the wall date disagrees with game state
            # by more than a year, the date was manipulated -- trust game
            # state and log the discrepancy loudly.
            try:
                _date_year = int(getattr(self.current_date, "year", 0) or 0)
                if _date_year and abs(_date_year - draft_year) > 1:
                    try:
                        self.add_news(
                            f"⚠️ Season continuity: wall date "
                            f"({self.current_date}) disagrees with league "
                            f"season {getattr(league, 'season_year', '?')} -- "
                            f"using game state for the {draft_year} draft.")
                    except Exception:
                        pass
            except Exception:
                pass
            # 1. Lottery -- fully automatic, no user input needed.
            lotto_done = set(getattr(league, 'lottery_held_years', None) or [])
            if draft_year not in lotto_done:
                self._set_current_date(date(draft_year, 5, 8))
                try:
                    self._hold_draft_lottery(draft_year)
                except Exception:
                    debug_print("Tentpole lottery failed (non-fatal):")
                    import traceback
                    traceback.print_exc()
                else:
                    held = set(getattr(league, 'lottery_held_years', None) or [])
                    held.add(draft_year)
                    league.lottery_held_years = sorted(held)
            # 2. Entry draft -- setup (class, lottery order, news, storylines).
            # Skip entirely when the year's picks were already conducted
            # (interactive war room): regenerating the class would orphan
            # the drafted prospects and the conductor is idempotent anyway.
            draft_done = set(getattr(league, 'draft_held_years', None) or [])
            conducted = set(
                getattr(league, 'draft_conducted_years', None) or [])
            if draft_year not in draft_done and draft_year not in conducted:
                self._set_current_date(date(draft_year, 6, 24))
                try:
                    self._hold_entry_draft(draft_year)
                except Exception:
                    debug_print("Tentpole draft setup failed (non-fatal):")
                    import traceback
                    traceback.print_exc()
                else:
                    held = set(getattr(league, 'draft_held_years', None) or [])
                    held.add(draft_year)
                    league.draft_held_years = sorted(held)
                # 3. Conduct the picks. Headless auto-draft mirrors the draft
                # board's AI logic (ai_make_pick) for every club.
                # Design follow-up: interactive per-pick drafting via Draft Day
                # Central instead of auto-conducting the user's picks.
                try:
                    self._auto_conduct_entry_draft(draft_year)
                except Exception:
                    debug_print("Tentpole auto-draft failed (non-fatal):")
                    import traceback
                    traceback.print_exc()
        except Exception:
            debug_print("Offseason tentpole guarantee failed (non-fatal):")
            import traceback
            traceback.print_exc()

    def _career_matchday_pre(self):
        """Matchday morning: scout report to inbox + optional pre-match presser."""
        from game_classes import EmailMessage
        matchup = self._career_user_game_today()
        if not matchup:
            return
        home, away = matchup
        opponent = away if home == self.user_team else home
        # Scout report -> inbox (no popup)
        report = manager_career.generate_opposition_report(opponent, self.league.standings)
        lines = [f"SCOUT REPORT: {report['team']} (Danger: {report['danger_level']})",
                 f"Record: {report['record']}", "", "Strengths:"]
        lines += ["• " + s for s in report["strengths"]]
        lines.append("Weaknesses:")
        lines += ["• " + w for w in report["weaknesses"]]
        lines.append("Tactical advice:")
        lines += ["• " + a for a in report["tactical_advice"]]
        # Adaptive Rivals: has the opponent scouted your systems and
        # installed a hockey answer for tonight?
        try:
            from adaptive_rivals import adaptation_report_lines
            _adapt_lines = adaptation_report_lines(
                opponent, self.user_team, getattr(self, 'game_results', []))
            if _adapt_lines:
                lines.append("")
                lines.append("Their answer to your systems:")
                lines += ["• " + _l for _l in _adapt_lines]
        except Exception:
            pass
        self.send_email_to_user(EmailMessage(
            sender="Chief Scout", sender_type="Scout",
            subject=f"Opposition report: {report['team']}",
            content="\n".join(lines), date_sent=self.current_date,
            category="Scouting"))
        # Pre-match presser now lives in the game-day inbox bundle
        # (delivered when Continue is pressed) -- no modal popup here.

    # ------------------------------------------------------------------
    # Game-day inbox bundle: pre-match presser + team talk + Watch Live /
    # Quick Sim choice delivered as ONE interactive inbox message instead
    # of the old modal chain (presser popup, game-mode popup, team-talk
    # popup). Post-match pressers arrive the same way. The gameplay
    # events themselves are unchanged -- only the delivery moved.
    # ------------------------------------------------------------------

    def _career_star_of_game(self, sim_engine, team) -> str:
        """Best performer name for the presser."""
        try:
            stats = getattr(sim_engine, "stats", {}) or {}
            team_stats = stats.get(team.team_name, {})
            best_id, best_g = None, -1
            for pid, st in team_stats.items():
                g = st.get("goals", 0) if isinstance(st, dict) else 0
                if g > best_g:
                    best_g, best_id = g, pid
            if best_id is not None:
                for p in (getattr(team, "roster", []) or []):
                    if p.id == best_id:
                        return f"{p.first_name} {p.last_name}"
        except Exception:
            pass
        # Fallback: captain or random skater
        for p in (getattr(team, "roster", []) or []):
            if getattr(p, "captaincy", None) == "C":
                return f"{p.first_name} {p.last_name}"
        return "your top line"
    
    def _career_team_games(self) -> int:
        b = self.career.board
        return b.season_wins + b.season_losses + b.season_otl

    def _career_team_strength(self, team) -> float:
        """Rough 0-100 squad strength for board expectations."""
        try:
            ratings = [manager_career._player_rating(p)
                       for p in (getattr(team, "roster", []) or [])]
            if not ratings:
                return 50.0
            return max(0.0, min(100.0, sum(ratings) / len(ratings) * 5.0))
        except Exception:
            return 50.0

    def _career_user_game_today(self):
        """Return (home_team, away_team) if the user plays today, else None."""
        team = self.user_team
        today = self.current_date
        for item in (self.league.schedule or []):
            try:
                if isinstance(item, dict):
                    d, h, a = item.get("date"), item.get("home_team"), item.get("away_team")
                elif isinstance(item, (tuple, list)) and len(item) >= 3:
                    d, h, a = item[0], item[1], item[2]
                else:
                    continue
                if d == today and (h == team or a == team):
                    return h, a
            except Exception:
                continue
        return None

    @staticmethod
    def _career_weekly_update(self):
        """Happiness/concerns, training morale & injury risk, assistant advice."""
        from game_classes import EmailMessage
        team = self.user_team
        team_games = self._career_team_games()
        noteworthy = []
        for p in (getattr(team, "roster", []) or []):
            try:
                noteworthy.extend(manager_career.update_player_happiness(p, team_games, team=team))
            except Exception:
                continue
        # Farm confidence: AHL production -> morale / attitude / call-up
        # buzz, once a week (ahl_system.weekly_farm_confidence). The morale
        # moves feed the existing call-up readiness "Confidence right now"
        # term and the happiness chain downstream; notes go to the inbox.
        try:
            import ahl_system
            _league = getattr(self.game_manager, "league", None)
            if _league is not None:
                for _note in ahl_system.weekly_farm_confidence(
                        _league, user_team=team):
                    try:
                        self.send_email_to_user(_note)
                    except Exception:
                        continue
        except Exception:
            pass
        # Fan sentiment (Wave C D34): slow weekly drift toward the
        # results baseline keeps the persistent fanbase mood honest
        # between the discrete presser/win nudges.
        try:
            from fan_sentiment import tick_fan_sentiment
            tick_fan_sentiment(team, current_date=self.current_date)
        except Exception:
            pass
        # Bucket 5 (Muck 2026-10-02): fan-driven narratives fire on
        # sentiment tier changes / extreme tiers (with cooldown).
        try:
            from fan_narratives import maybe_fire_fan_narrative
            maybe_fire_fan_narrative(team, game_manager=self,
                                     current_date=self.current_date)
        except Exception:
            pass
        # L4 wire (Muck 2026-10-02): boardroom narratives -- the board
        # pressure nudge made visible ("Ownership losing patience...").
        # Same weekly cadence, own cooldown.
        try:
            from fan_narratives import maybe_fire_board_narrative
            maybe_fire_board_narrative(team, game_manager=self,
                                       current_date=self.current_date)
        except Exception:
            pass
        # Training effects: morale + injury risk
        fx = self.career.training.weekly_effects()
        if fx["morale_delta"]:
            for p in (getattr(team, "roster", []) or []):
                m = getattr(p, "morale", 70) or 70
                p.morale = max(1, min(100, m + (5 if fx["morale_delta"] > 0 else -5)))
        import random as _r
        if _r.random() < 0.02 * fx["injury_risk_mult"]:
            candidates = [p for p in (getattr(team, "roster", []) or [])
                          if not getattr(p, "is_injured", False)]
            if candidates:
                # W3->W4 contract: the tired/worn player picks up the
                # training knock, not a uniform draw. Defensive: falls back
                # to the old uniform choice if condition_system is missing.
                try:
                    from condition_system import (
                        fatigue_injury_risk_mult as _w3_risk)
                    _weights = [max(0.2, float(_w3_risk(p)))
                                for p in candidates]
                    victim = _r.choices(candidates, weights=_weights, k=1)[0]
                except Exception:
                    victim = _r.choice(candidates)
                victim.is_injured = True
                victim.injury_type = "Training knock"
                victim.games_remaining_injured = _r.randint(1, 4)
                # Muck 2026-10-02: record to injury_history (was missing on this path)
                try:
                    _hist = getattr(victim, "injury_history", None)
                    if not isinstance(_hist, list):
                        _hist = []
                    _hist.append({"type": "Training knock", "region": "?",
                                 "games": victim.games_remaining_injured,
                                 "concussion": False})
                    victim.injury_history = _hist[-8:]
                except Exception:
                    pass
                self.add_news(f"🤕 {victim.first_name} {victim.last_name} injured in training "
                              f"({victim.games_remaining_injured} games).")
        # Player concerns -> inbox (max 2 per week)
        concerns = manager_career.check_squad_concerns(team)[:2]
        for player, text in concerns:
            action_hint = ("Reply via Manager Hub → Squad tab to hold a private chat."
                           if not getattr(player, "transfer_requested", False)
                           else "Urgent: discuss his future in the Manager Hub → Squad tab.")
            self.send_email_to_user(EmailMessage(
                sender=f"{player.first_name} {player.last_name}",
                sender_type="Player",
                subject="Squad concern" + (" — TRANSFER REQUEST" if getattr(player, "transfer_requested", False) else ""),
                content=f"{text}\n\n{action_hint}",
                date_sent=self.current_date, category="Contracts",
                is_important=getattr(player, "transfer_requested", False),
                related_player_id=str(getattr(player, "id", ""))))
        for note in noteworthy[:3]:
            self.add_news(f"📋 {note}")
        # Occasional assistant coach advice
        if _r.random() < 0.25:
            advice = self._career_assistant_advice()
            if advice:
                self.send_email_to_user(EmailMessage(
                    sender="Assistant Coach", sender_type="Staff",
                    subject="Training & squad advice",
                    content=advice, date_sent=self.current_date,
                    category="General"))

    def _consume_team_talk_session(self, session_id):
        """Consume-once: remove a team-talk session after its answer applied."""
        try:
            sessions = getattr(self, "pending_sessions", None) or {}
            if session_id in sessions:
                del sessions[session_id]
            try:
                self.refresh_screen_navbar()
            except Exception:
                pass
        except Exception:
            pass

    def _create_awards_section(self, parent):
        """Create the awards section of the season summary."""
        # Get all players for award calculations
        all_players = []
        for team in self.league.teams:
            all_players.extend(team.roster)
        
        # Calculate award winners
        awards = self._calculate_season_awards(all_players)
        
        # Display awards in a grid
        ttk.Label(parent, text="NHL Award Winners", 
                 font=(self.FONT_FAMILY, 16, 'bold'), style='Title.TLabel').pack(pady=(10, 20))
        
        awards_grid = ttk.Frame(parent, style='Panel.TFrame')
        awards_grid.pack(fill='x', padx=20)
        
        row = 0
        for award_name, winner_info in awards.items():
            # Award name
            ttk.Label(awards_grid, text=f"{award_name}", 
                     font=(self.FONT_FAMILY, 11, 'bold'), 
                     style='Header.TLabel').grid(row=row, column=0, sticky='w', pady=5, padx=10)
            
            # Winner info
            if winner_info:
                winner_text = f"{winner_info['name']} ({winner_info['team']}) - {winner_info['stats']}"
            else:
                winner_text = "N/A"
            ttk.Label(awards_grid, text=winner_text, 
                     style='TLabel').grid(row=row, column=1, sticky='w', pady=5, padx=10)
            row += 1
            
    def _create_leaders_section(self, parent):
        """Create league leaders section."""
        ttk.Label(parent, text="League Statistical Leaders", 
                 font=(self.FONT_FAMILY, 16, 'bold'), style='Title.TLabel').pack(pady=(10, 20))
        
        # Get all players
        all_players = []
        for team in self.league.teams:
            all_players.extend(team.roster)
        
        skaters = [p for p in all_players if hasattr(p, 'stats') and p.primary_position.name != 'GOALIE']
        
        # Sort by points
        top_scorers = sorted(skaters, key=lambda p: getattr(p.stats, 'points', 0), reverse=True)[:10]
        
        # Create treeview
        columns = ('rank', 'name', 'team', 'gp', 'goals', 'assists', 'points')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)
        
        tree.heading('rank', text='#')
        tree.heading('name', text='Player')
        tree.heading('team', text='Team')
        tree.heading('gp', text='GP')
        tree.heading('goals', text='G')
        tree.heading('assists', text='A')
        tree.heading('points', text='P')
        
        tree.column('rank', width=40)
        tree.column('name', width=180)
        tree.column('team', width=80)
        tree.column('gp', width=50)
        tree.column('goals', width=50)
        tree.column('assists', width=50)
        tree.column('points', width=50)
        
        for i, player in enumerate(top_scorers, 1):
            tree.insert('', 'end', values=(
                i,
                player.full_name,
                getattr(player, 'team_name', 'UNK')[:3].upper(),
                getattr(player.stats, 'games_played', 0),
                getattr(player.stats, 'goals', 0),
                getattr(player.stats, 'assists', 0),
                getattr(player.stats, 'points', 0)
            ))
        
        tree.pack(fill='both', expand=True, padx=20, pady=10)
        
    def _create_team_summary_section(self, parent):
        """Create team summary section."""
        team = self.user_team
        team_stats = self.league.standings.get(team.team_name, {})
        
        ttk.Label(parent, text=f"Your Team: {team.team_name}", 
                 font=(self.FONT_FAMILY, 16, 'bold'), style='Title.TLabel').pack(pady=(10, 20))
        
        # Team record
        record_frame = ttk.Frame(parent, style='Panel.TFrame')
        record_frame.pack(fill='x', padx=20, pady=10)
        
        wins = team_stats.get('Wins', 0)
        losses = team_stats.get('Losses', 0)
        otl = team_stats.get('OTL', 0)
        points = team_stats.get('Points', 0)
        
        ttk.Label(record_frame, text=f"Record: {wins}-{losses}-{otl} ({points} pts)", 
                 font=(self.FONT_FAMILY, 14), style='Header.TLabel').pack(anchor='w')
        
        # Calculate league position
        sorted_standings = sorted(self.league.standings.items(), 
                                 key=lambda x: x[1].get('Points', 0), reverse=True)
        position = next((i+1 for i, (name, _) in enumerate(sorted_standings) if name == team.team_name), '?')
        
        ttk.Label(record_frame, text=f"League Position: {position} of {len(self.league.teams)}", 
                 font=(self.FONT_FAMILY, 12), style='TLabel').pack(anchor='w', pady=5)
        
        # Top team scorers
        ttk.Label(parent, text="Top Scorers", 
                 font=(self.FONT_FAMILY, 12, 'bold'), style='Header.TLabel').pack(pady=(20, 10), anchor='w', padx=20)
        
        team_players = sorted(team.roster, 
                             key=lambda p: getattr(p.stats, 'points', 0) if hasattr(p, 'stats') else 0, 
                             reverse=True)[:5]
        
        for player in team_players:
            stats = getattr(player, 'stats', None)
            if stats:
                pts = getattr(stats, 'points', 0)
                g = getattr(stats, 'goals', 0)
                a = getattr(stats, 'assists', 0)
                _tsl = ttk.Label(parent, text=f"  {player.full_name}: {g}G {a}A = {pts} pts", 
                         style='TLabel')
                _tsl.pack(anchor='w', padx=20)
                # EHM/FM24: right-click a scorer -> player menu.
                try:
                    from player_context_menu import bind_player_context
                    bind_player_context(_tsl, player, self)
                except Exception:
                    pass
    
    def _daily_international_window(self, today, year, league) -> None:
        """Fire the day's international window legs (Olympics announce /
        resolve, Worlds) with catch-up semantics: a skipped Feb 9, Feb 22
        or May 12 still fires late. Each leg is idempotent via
        league.intl_announced / league.intl_held, and medal day self-heals
        by announcing first when the prep is missing."""
        from international import (
            OLYMPIC_ANNOUNCE_MONTH, OLYMPIC_ANNOUNCE_DAY,
            OLYMPIC_MEDAL_MONTH, OLYMPIC_MEDAL_DAY,
            WORLDS_MONTH, WORLDS_DAY,
            is_olympic_year, announce_olympics, resolve_olympics,
            hold_worlds)
        _md = (today.month, today.day)
        _oly = is_olympic_year(year)
        _ann = (getattr(league, "intl_announced", None) or [])
        if (_md >= (OLYMPIC_ANNOUNCE_MONTH, OLYMPIC_ANNOUNCE_DAY)
                and _oly and year not in _ann):
            _story = announce_olympics(self, year)
            if _story:
                self.news_log.append({'date': self.current_date,
                                      'story': _story})
        if (_md >= (OLYMPIC_MEDAL_MONTH, OLYMPIC_MEDAL_DAY)
                and _oly):
            _held = (getattr(league, "intl_held", None) or {}).get(
                "olympics", [])
            if year not in _held:
                _res = resolve_olympics(self, year)
                if _res:
                    self._deliver_intl_card(_res)
        if _md >= (WORLDS_MONTH, WORLDS_DAY):
            _held = (getattr(league, "intl_held", None) or {}).get(
                "worlds", [])
            if year not in _held:
                _res = hold_worlds(self, year)
                if _res:
                    self._deliver_intl_card(_res)

        # Hub prompt: once per (event, year)
        try:
            event = get_todays_event(today)
        except Exception as e:
            debug_print(f"Event-day detection failed: {e}")
            return
        if not event:
            return
        prompted = [tuple(p) for p in (getattr(league, 'event_day_prompted', None) or [])]
        key = (event, year)
        if key in prompted:
            return
        prompted.append(key)
        league.event_day_prompted = [list(p) for p in prompted]
        # Defer the prompt so the daily sim UI finishes updating first
        self.after(500, lambda ev=event: self._prompt_event_day_safe(ev))

    def _get_developable_attributes(self, player):
        """Get list of attributes that can develop for a player"""
        from game_classes import PlayerPosition
        
        # Core attributes that all players can develop
        core_attrs = ['skating', 'checking', 'positioning', 'hockey_iq']
        
        # Position-specific developable attributes
        if hasattr(player, 'primary_position'):
            if player.primary_position == PlayerPosition.GOALIE:
                return core_attrs + ['goaltending', 'reflexes', 'rebound_control', 'composure']
            elif player.primary_position in [PlayerPosition.CENTER]:
                return core_attrs + ['passing', 'faceoffs', 'shooting', 'vision']
            elif player.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
                return core_attrs + ['shooting', 'shooting_accuracy', 'speed', 'puck_protection']
            else:  # Defense
                return core_attrs + ['blocking', 'stick_checking', 'strength', 'passing']
        
        return core_attrs

    def _league_sim_detail(self, league_key):
        """Return the configured sim detail for a league ('full' | 'quick' | 'scores').

        Set by the new-game setup wizard (gm.sim_detail). Defaults: the user's
        league runs full, everything else runs quick.

        NOTE (2026-09-29, BUG-025): sim_detail and user_league live on the
        GameManager (gm), not on the app. Reading them from self (the GUI)
        always missed, so every batch game silently ran 'quick'.
        """
        _gm = getattr(self, 'game_manager', None)
        detail = getattr(_gm, 'sim_detail', None) or {}
        if league_key in detail:
            return detail[league_key]
        user_league = getattr(_gm, 'user_league', None)
        if league_key and user_league and league_key == user_league:
            return 'full'
        return 'quick'

    def _mp_offer_to_host(self, proposal, team, partner, out_players,
                          in_players, out_picks, in_picks):
        """The proposal targets the host's own club: ask the host with the
        same prompt the trade screen uses (waivers first, then accept)."""
        # Web UI (Batch E, 2026-10-06): no blocking Tk dialogs on the web
        # host -- the web layer sets _mp_web_host_offers (a dict) and the
        # offer surfaces in /api/mp/game for an in-page Accept/Reject.
        # Desktop path below is untouched.
        _web_offers = getattr(self, "_mp_web_host_offers", None)
        if isinstance(_web_offers, dict):
            try:
                import uuid as _uuid
                _oid = _uuid.uuid4().hex[:10]
                _web_offers[_oid] = {
                    "proposal": proposal,
                    "offer_id": _oid,
                }
                return (True,
                        f"Offer sent to {getattr(partner, 'team_name', 'you')} "
                        f"-- awaiting their answer.",
                        False)
            except Exception:
                pass
        import trade_engine as te
        from popup_system import messagebox
        league = getattr(self, "league", None)
        # Host's own clause players: single-player askyesnocancel.
        kept_in = list(in_players)
        try:
            for _v in te.trade_vetoes(partner, team, list(in_players),
                                      league):
                _p = _v["player"]
                _pname = getattr(_p, "full_name", "player")
                _ans = messagebox.askyesnocancel(
                    "No-trade clause",
                    f"{_pname} has a {_v.get('detail', 'clause')}.\n\n"
                    f"Ask him to waive it for a move to {team.team_name}?\n\n"
                    "Yes = ask him  |  No = remove him from the offer  |  "
                    "Cancel = stop")
                if _ans is None:
                    self._mp_clear_proposal_waivers(proposal)
                    return False, "You cancelled the offer.", True
                if _ans is False:
                    kept_in = [p for p in kept_in if p is not _p]
                    continue
                _ok, _why = te.will_waive_ntc(_p, partner, team, league)
                if _ok:
                    try:
                        _p.contract.ntc_waiver_for = team.team_name
                    except Exception:
                        pass
                    messagebox.showinfo("Waiver granted", _why)
                else:
                    messagebox.showwarning(
                        "Waiver refused",
                        f"{_why}\n\nHe's staying put -- the offer is dead.")
                    self._mp_clear_proposal_waivers(proposal)
                    return False, \
                        f"{_pname} refused to waive -- offer dead.", True
        except Exception:
            pass
        proposal["_in_players"] = kept_in
        if not kept_in and not in_picks:
            self._mp_clear_proposal_waivers(proposal)
            return False, "Nothing left to ask for.", True

        def _names(plist):
            return ", ".join(getattr(p, "full_name", "?") for p in plist) \
                or "none"

        def _knames(klist):
            return ", ".join(
                f"{getattr(k, 'year', '?')} R{getattr(k, 'round', '?')}"
                for k in klist) or "none"

        try:
            accept = messagebox.askyesno(
                f"Trade offer from {proposal['manager']}",
                f"{proposal['manager']} ({team.team_name}) offers:\n\n"
                f"YOU RECEIVE: {_names(out_players)}\n"
                f"Picks: {_knames(out_picks)}\n\n"
                f"YOU SEND: {_names(kept_in)}\n"
                f"Picks: {_knames(in_picks)}\n\n"
                "Accept this trade?")
        except Exception:
            accept = False
        if not accept:
            self._mp_clear_proposal_waivers(proposal)
            try:
                self.mp_host.broadcast_chat(
                    f"Trade {team.team_name} -> {partner.team_name} "
                    f"rejected by {partner.team_name}.")
            except Exception:
                pass
            return False, "You rejected the offer.", True
        ok, detail = self._mp_execute_mp_trade(proposal)
        return ok, detail, True

    def _mp_serialize_offer(self, proposal, out_players, in_players,
                            out_picks, in_picks):
        import trade_engine as te

        def _p(p):
            kind = ""
            try:
                kind = (te.clause_of(p) or ("", ""))[0] or ""
            except Exception:
                pass
            pos = getattr(getattr(p, "primary_position", None), "value",
                          "?")
            return {"id": str(getattr(p, "id", "")),
                    "name": getattr(p, "full_name", "?"),
                    "pos": pos,
                    "ovr": int(getattr(p, "overall", 0) or 0),
                    "salary": int(getattr(getattr(p, "contract", None),
                                          "salary", 0) or 0),
                    "clause": kind}

        def _k(k):
            return {"id": str(getattr(k, "id", "")),
                    "desc": (f"{getattr(k, 'year', '?')} "
                             f"Round {getattr(k, 'round', '?')} "
                             f"({getattr(k, 'original_team', '')})")}

        return {"players_out": [_p(p) for p in out_players],
                "players_in": [_p(p) for p in in_players],
                "picks_out": [_k(k) for k in out_picks],
                "picks_in": [_k(k) for k in in_picks],
                "retention": dict(proposal.get("retention") or {}),
                "pick_protection": dict(proposal.get("pick_protection")
                                        or {})}

    def _mp_swapped_user_team(self, team):
        """Context manager: run a block with the acting team as user_team
        (for machinery that addresses app.user_team), then restore."""
        import contextlib as _cl

        @ _cl.contextmanager
        def _ctx():
            _orig_ut = getattr(self, "user_team", None)
            _gm = getattr(self, "game_manager", None)
            _orig_gm_ut = getattr(_gm, "user_team", None) \
                if _gm is not None else None
            try:
                self.user_team = team
                if _gm is not None:
                    _gm.user_team = team
                yield
            finally:
                self.user_team = _orig_ut
                if _gm is not None:
                    _gm.user_team = _orig_gm_ut
        return _ctx()

    def _offseason_board_review(self):
        """Year-end board reckoning + season rollover (BUG-011 fix).

        Gives BoardSystem.season_review() the first real caller it has
        ever had, then stashes the facts on the app for the season-review
        inbox card (season_review.py builds the full story: big moments,
        standouts, prospects, the four-corner season score).
        """
        career = getattr(self, 'career', None)
        board = getattr(career, 'board', None)
        if board is None or not hasattr(board, 'season_review'):
            return
        made, rounds, cup = self._user_playoff_result()
        headline, body, delta = board.season_review(made, rounds, cup)
        self._season_review_board = {
            "headline": headline, "body": body, "delta": delta,
            "made_playoffs": made, "playoff_rounds_won": rounds,
            "won_cup": cup,
            "expectation": getattr(board, 'expectation', None),
            "confidence": getattr(board, 'confidence', None),
            "season_number": getattr(board, 'season_number', None),
        }
        try:
            self.add_news(f"Board season review: {headline} "
                          f"(confidence {board.confidence}/100).")
        except Exception:
            pass
        # The season-review card: big moments, standouts/tough-go, story of
        # the year, prospect pipeline report, four-corner season score --
        # delivered to the inbox. Must run before league.end_of_season()
        # wipes the per-season stats it reads. Guarded: a card bug must
        # never break the season rollover.
        try:
            from season_review import deliver_season_review
            deliver_season_review(self)
        except Exception:
            pass

    def _offseason_immortality(self):
        """Retirements, HOF vote, retired numbers, era arguments. One pass."""
        import immortality as _im
        league = getattr(self, "league", None)
        if league is None:
            return
        year = int(getattr(league, "season_year", 2026) or 2026)
        hist = getattr(self, "league_history", None)

        # 1. Hang them up.
        retired = _im.process_retirements(league, year)
        for snap in retired:
            try:
                if _im.career_score(snap) >= 60.0:
                    self.add_news(
                        f"{snap['name']} hangs them up: "
                        f"{snap['games']} games, {snap['points']} points"
                        f"{', ' + str(snap['wins']) + ' wins' if snap.get('goalie') else ''}. "
                        f"A career worthy of the Hall conversation.")
            except Exception:
                pass

        # 2. Raise the numbers.
        for snap in retired:
            try:
                if not _im.number_worthy(snap):
                    continue
                team = next(
                    (t for t in (getattr(league, "teams", None) or [])
                     if getattr(t, "team_name", "") == snap.get("team_name")),
                    None)
                if team is not None and _im.retire_number(team, snap, year):
                    try:
                        from headlines import deliver_spec as _deliver_spec
                        _deliver_spec(self, {
                            "kind": "special_event",
                            "event_kind": "jersey_retirement",
                            "text": f"{getattr(team, 'team_name', '')} will retire "
                                    f"{snap['name']}'s No. {snap['number']} -- "
                                    f"a pregame ceremony at the next home game.",
                            "home": getattr(team, 'team_name', ''),
                            "involved": (getattr(team, 'team_name', ''),),
                        })
                    except Exception:
                        pass
                    self.add_news(
                        f"{getattr(team, 'team_name', '')} will retire "
                        f"{snap['name']}'s No. {snap['number']} -- "
                        f"a pregame ceremony at the next home game.")
            except Exception:
                continue

        # 3. The Hall calls (or doesn't).
        if hist is not None:
            report = _im.hof_ballot(league, hist, year)
            for ind in report.get("inducted", []):
                try:
                    _years = ind.get("ballot_years", 1)
                    _arc = (f" -- after {_years} years on the ballot, "
                            f"the wait is over" if _years > 1 else "")
                    self.add_news(
                        f"Hall of Fame: {ind['name']} is in "
                        f"({ind['votes']}/12 votes){_arc}.")
                except Exception:
                    pass
            for bl in report.get("borderline", []):
                try:
                    self.add_news(
                        f"Hall of Fame debate: {bl['name']} falls short "
                        f"({bl['votes']}/12) -- the room is split between "
                        f"the compilers and the peak-value crowd. "
                        f"Back on the ballot next year.")
                except Exception:
                    pass

            # 4. Greatest team ever? Only when there's a real argument.
            arg = _im.era_argument(hist)
            if arg is not None:
                news = _im.era_argument_news(arg)
                if news:
                    self.add_news(news)

    def _present_team_talk_screen(self, sess, wake, epoch):
        """(Re-)present the team-talk screen for a Tier-B session.

        `wake` is the day-sim waiter to release on answer, or None when
        there is no live waiter (e.g. resumed after save/load -- the
        answer then parks in the session and the next Continue applies
        it pre-game, no re-ask). The view always rebuilds from the
        session's stored context: returning resumes the exact session.
        """
        from manager_hub_window import TeamTalkView
        session_id = (sess or {}).get("id") if isinstance(sess, dict) else None
        tt = ((sess or {}).get("team_talk") or {}) if isinstance(sess, dict) else {}
        context = dict(tt.get("context") or {})
        if not context:
            context = {"situation": tt.get("situation", "even"),
                       "opponent_name": tt.get("opponent_name", "the opposition")}
        try:
            if self.user_team is not None:
                _team = self.user_team
            else:
                _team = None
        except Exception:
            _team = None
        # Revalidate the opponent against the live league (pattern:
        # revalidation on re-present). Falls back to the stored name.
        try:
            _opp = self._resolve_team_talk_opponent(tt)
            if _opp is not None:
                context["opponent_name"] = getattr(
                    _opp, "team_name",
                    context.get("opponent_name", "the opposition"))
        except Exception:
            pass

        def _on_done(result):
            try:
                # View contract: (option, reaction, boost) tuple, or None
                # for "say nothing". Record the answer no matter what --
                # a malformed result still counts as answered (dismiss is
                # a separate path that never calls on_done).
                boost = 1.0
                if result:
                    try:
                        _opt, _reaction, boost = result
                    except (TypeError, ValueError):
                        try:
                            boost = float(result)
                        except (TypeError, ValueError):
                            boost = 1.0
                from popup_system import get_pending_session as _gps
                s2 = _gps(self, session_id)
                if s2 is not None:
                    s2["dialogs"]["talk"] = {
                        "answered": True,
                        "boost": float(boost or 1.0),
                    }
                    t2 = s2.get("team_talk")
                    if isinstance(t2, dict):
                        t2["parked"] = False
            except Exception:
                pass
            try:
                self.refresh_screen_navbar()
            except Exception:
                pass
            if wake is not None:
                try:
                    # Don't wake a stale frame: if a load bumped the
                    # epoch after we presented, the waiter is already
                    # released and this answer belongs to the session.
                    if getattr(self, "_team_talk_epoch", 0) == epoch:
                        wake.set(True)
                except Exception:
                    pass

        try:
            view = self.show_screen("team_talk", "Pre-Match Team Talk",
                                    TeamTalkView, _team,
                                    "prematch", context,
                                    on_done=_on_done, fresh=True)
        except Exception:
            return None
        # Park-on-navigation: destroying the view WITHOUT an answer
        # parks the session (context preserved) and surfaces the resume
        # chip. The waiter is deliberately NOT released -- the day sim
        # stays paused on the talk. Dismiss = defer, never an answer.
        try:
            view.bind(
                "<Destroy>",
                lambda e, v=view, s=session_id:
                    self._on_team_talk_destroyed(e, v, s),
                add="+")
        except Exception:
            pass
        return view

    def _prune_team_talk_sessions(self, keep_date):
        """Drop team-talk sessions that can never resume (other dates)."""
        try:
            sessions = getattr(self, "pending_sessions", None) or {}
            for sid in list(sessions.keys()):
                try:
                    sess = sessions.get(sid)
                    if not isinstance(sess, dict) or sess.get("kind") != "team_talk":
                        continue
                    tt = sess.get("team_talk") or {}
                    if tt.get("date") != keep_date:
                        del sessions[sid]
                except Exception:
                    continue
        except Exception:
            pass

    def _record_season_to_history(self):
        """Record the completed season to League Memory.

        Called from _start_offseason after the champion is resolved but
        before league.end_of_season() wipes stats. Purely additive —
        records outcomes, never changes them.
        """
        from league_history import LeagueHistory
        # Get or create the history object on the career
        hist = getattr(self, 'league_history', None)
        if hist is None:
            hist = LeagueHistory()
            self.league_history = hist

        year = getattr(getattr(self, 'league', None), 'season_year', 2026)

        # Champion, runner-up, series score from the playoff bracket
        champion = None
        runner_up = None
        series_score = None
        try:
            pw = (getattr(self, 'open_windows', None) or {}).get('playoffs')
            bracket = None
            if pw is not None and hasattr(pw, 'winfo_exists') and pw.winfo_exists():
                _wb = getattr(pw, 'playoff_bracket', None)
                _lb = getattr(getattr(self, 'league', None),
                              'playoff_bracket', None)
                # BUG-REVIEW-002: ignore a stale decided bracket lingering
                # on the never-torn-down playoffs view; the league's bracket
                # is the live one (same identity invariant as above).
                bracket = _wb if (_wb is not None and _wb is _lb) else _lb
            if bracket is None:
                bracket = getattr(getattr(self, 'league', None), 'playoff_bracket', None)
            if bracket is not None:
                champ = getattr(bracket, 'stanley_cup_champion', None)
                champion = getattr(champ, 'team_name', None)
                # Final series for runner-up and score
                finals = (getattr(bracket, 'playoff_series', {}) or {}).get(
                    'stanley_cup_final', [])
                if finals:
                    s = finals[0]
                    winner = getattr(s, 'winner', None)
                    if winner is not None:
                        wname = getattr(winner, 'team_name', None)
                        # Runner-up is the other team
                        t1 = getattr(getattr(s, 'team1', None), 'team_name', None)
                        t2 = getattr(getattr(s, 'team2', None), 'team_name', None)
                        runner_up = t2 if wname == t1 else t1
                        ww = s.team1_wins if wname == t1 else s.team2_wins
                        lw = s.team2_wins if wname == t1 else s.team1_wins
                        series_score = f"{ww}-{lw}"
        except Exception:
            pass

        # Awards (calculate from current stats before wipe)
        awards = {}
        try:
            all_players = []
            for team in self.league.teams:
                all_players.extend(team.roster)
            raw_awards = self._calculate_season_awards(all_players)
            # Normalize to {award_name: player_name}
            for award_name, winner in raw_awards.items():
                if winner is not None:
                    if isinstance(winner, dict):
                        awards[str(award_name)] = winner.get('name', '?')
                    else:
                        awards[str(award_name)] = getattr(
                            winner, 'full_name', getattr(winner, 'name', str(winner)))
        except Exception:
            pass

        # Conn Smythe: decided at Cup-win time and stashed on the bracket
        # (playoff_system._decide_conn_smythe) -- the awards calculator only
        # covers the regular season, so inject it here for the history book.
        try:
            smythe_name = getattr(bracket, "conn_smythe_name", None)
            if smythe_name:
                awards["Conn Smythe"] = smythe_name
        except Exception:
            pass

        # Presidents' Trophy: best regular-season record
        presidents = None
        standings_snapshot = []
        try:
            best_pts = -1
            for team in self.league.teams:
                st = self.league.standings.get(team.team_name, {})
                w = st.get('W', st.get('Wins', 0))
                l = st.get('L', st.get('Losses', 0))
                otl = st.get('OTL', 0)
                pts = w * 2 + otl
                if pts > best_pts:
                    best_pts = pts
                    presidents = team.team_name
                standings_snapshot.append({
                    "team": team.team_name,
                    "w": w, "l": l, "otl": otl, "pts": pts,
                })
            # Sort by points and keep ALL 32 clubs with their final rank --
            # history should remember a 29th-place finish, not just the
            # playoff field.
            standings_snapshot.sort(key=lambda x: x["pts"], reverse=True)
            for _rank, _row in enumerate(standings_snapshot, 1):
                _row["rank"] = _rank
        except Exception:
            pass

        # Conn Smythe: from awards if present, else None
        conn_smythe = awards.get("Conn Smythe")

        hist.record_season(
            year=year,
            champion=champion,
            runner_up=runner_up,
            series_score=series_score,
            presidents_trophy=presidents,
            conn_smythe=conn_smythe,
            awards=awards,
            standings_snapshot=standings_snapshot,
        )

        # Franchise records: fold each team's season into the record book.
        # Runs before end_of_season() wipes per-season stats.
        try:
            season_label = f"{year}-{str(year + 1)[-2:]}"
            for team in self.league.teams:
                hist.franchise_records.update_from_season(team, season_label)
                try:
                    _streak = int(getattr(team, "longest_win_streak", 0) or 0)
                    if _streak >= 3:
                        hist.franchise_records.record_streak(
                            team.team_name, "win", _streak, season_label)
                except Exception:
                    pass
        except Exception:
            pass

    def _simulate_game_full_batch(self, home_team, away_team):
        """Full event-by-event sim for batch games in 'full'-detail leagues.

        Uses simulation.GameSim (the hooked engine). Player season stats —
        goals, assists, and games played — are updated by the engine itself.
        Returns (winner, loser, scores, went_to_ot, sim).
        """
        from simulation import GameSim
        from arena_atmosphere import crowd_hype_for_tension
        _atm = _pregame_atmosphere(
            home_team, away_team,
            league=getattr(self, "league", None),
            milestone_home=home_team.team_name in
            getattr(self, "_milestone_watch_teams", set()),
            ceremony=bool(getattr(home_team, "_pending_ceremony", None)))
        sim = GameSim(home_team, away_team, atmosphere=_atm,
                      crowd_hype=crowd_hype_for_tension(
                          _atm.get("energy", 50.0), _atm.get("mood", 30.0)))
        # Deployment directive: feed today's trade-deadline stances to the
        # ice-time ecosystem so coaches read team direction (buyer/seller).
        # Additive; the stance model lives in trade_storylines.
        try:
            from deployment_policy import set_team_direction as _set_tdir
            import trade_storylines as _ts
            _set_tdir({home_team.team_name: _ts.stance(self, home_team.team_name),
                       away_team.team_name: _ts.stance(self, away_team.team_name)})
        except Exception:
            pass
        periods = set()
        had_shootout = {'v': False}

        def _sniff(ev):
            if isinstance(ev, dict):
                periods.add(ev.get('period', 1))
                if ev.get('type') == 'shootout_end':
                    had_shootout['v'] = True

        sim.pbp_listeners.append(_sniff)
        # Pregame ceremony (if one is queued).
        try:
            import immortality as _im3
            _im3.consume_ceremony(self, home_team, sim)
        except Exception:
            pass
        winner, loser, scores, _game_log, _notable = sim.run()
        went_to_ot = any(p > 3 for p in periods)
        return winner, loser, scores, went_to_ot, sim

    def _calculate_team_strength(self, team):
        """Quick team strength calculation for lightweight simulation.
        Moved from HockeyManagerGUI (main.py) -- pure game logic, no UI.
        Bot audit 2026-10-07: was missing from GameManager (B-O5)."""
        # Use cached calculation if available
        cache_key = f"strength_{team.team_name}"
        if hasattr(self, '_strength_cache') and cache_key in self._strength_cache:
            return self._strength_cache[cache_key]
        
        if not hasattr(self, '_strength_cache'):
            self._strength_cache = {}
        
        # Enhanced strength calculation based on key players
        total_strength = 0
        player_count = 0

        # Injured or suspended players don't dress: use available skaters
        # (fall back to full roster if the team is decimated)
        skaters = [p for p in team.roster
                   if not getattr(p, 'is_injured', False)
                   and not (getattr(p, 'suspension_games_remaining', 0)
                            or 0)]
        if len(skaters) < 14:
            skaters = list(team.roster)

        # Sample top players for speed, but weight by position importance
        sorted_roster = sorted(skaters, key=lambda p: p.overall_rating(), reverse=True)
        top_forwards = [p for p in sorted_roster if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:9]
        top_defense = [p for p in sorted_roster if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:6]  
        top_goalies = [p for p in sorted_roster if p.primary_position.name == 'GOALIE'][:2]
        
        # Weight positions appropriately
        for player in top_forwards:
            total_strength += player.overall_rating() * 0.6
            player_count += 0.6
            
        for player in top_defense:
            total_strength += player.overall_rating() * 0.3
            player_count += 0.3
            
        for player in top_goalies:
            total_strength += player.overall_rating() * 0.1
            player_count += 0.1
        
        # Normalize to 0.5-1.0 range for goal calculation.
        avg_ovr = (total_strength / max(player_count, 1)) if player_count > 0 else 80.0
        strength = 0.5 + (avg_ovr - 70) / 40.0
        strength = max(0.5, min(1.0, strength))
        
        # Cache the result
        self._strength_cache[cache_key] = strength
        
        return strength

        def _calculate_star_player_effects(self, team, situation_score=None):
            """Calculate individual star player effects on game outcome"""
            effects = {
                'offensive_boost': 0.0,
                'defensive_reduction': 0.0,
                'clutch_factor': 0.0
            }
        
            # Get top players by position -- only dressed players move the
            # needle. Suspended or injured stars don't boost the team from
            # the press box (same exclusion the strength calc uses).
            available = [p for p in team.roster
                         if not getattr(p, 'is_injured', False)
                         and not (getattr(p, 'suspension_games_remaining', 0)
                                  or 0)]
            sorted_roster = sorted(available, key=lambda p: p.overall_rating(), reverse=True)
            top_forwards = [p for p in sorted_roster if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:3]
            top_defense = [p for p in sorted_roster if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:2]
            top_goalies = [p for p in sorted_roster if p.primary_position.name == 'GOALIE'][:1]
        
            # Elite forwards boost offensive production
            # D28 (Wave A, 2026-10-01, Muck): retiered to the true 1-100
            # talent bands. The old thresholds (52/50/47/44) handed nearly
            # every rostered forward the max effect -- a flat +0.4 for all 32
            # teams, the opposite of a hierarchy. Now aligned with the talent
            # tiers: Generational 92+ -> 0.25, Elite 88+ -> 0.18,
            # Very good 84+ -> 0.10, Good 80+ -> 0.05.
            for forward in top_forwards:
                rating = forward.overall_rating()
                if rating >= 92:  # Generational
                    effects['offensive_boost'] += 0.25
                elif rating >= 88:  # Elite
                    effects['offensive_boost'] += 0.18
                elif rating >= 84:  # Very good
                    effects['offensive_boost'] += 0.10
                elif rating >= 80:  # Good
                    effects['offensive_boost'] += 0.05
        
            # Elite defensemen reduce opponent scoring
            # (native 1-100 scale: ~84+ is a top-pair NHL defender)
            # (clutch moved to team_clutch.py -- shared dynamic factor)
            for defenseman in top_defense:
                rating = defenseman.overall_rating()
                if rating >= 93:  # Elite defender (Norris level)
                    effects['defensive_reduction'] += 0.25
                elif rating >= 90:  # Very good defender
                    effects['defensive_reduction'] += 0.15
                elif rating >= 87:  # Good defender
                    effects['defensive_reduction'] += 0.08
                elif rating >= 84:  # Decent defender
                    effects['defensive_reduction'] += 0.03
        
            # Elite goalies have major defensive impact
            # (native 1-100 scale: ~82+ is an NHL starter; 91+ is Vezina-tier)
            # Factor-calibrated 2026-09-29 vs the event sim: the event engine's
            # goalie response is ~2x the old tiers (weak goalie 86->30: +0.37
            # there vs +0.13 here; elite 87->95: -0.30 there vs -0.20 here).
            # Steepened through the NHL range and extended below it -- a bad
            # goalie actively bleeds goals (negative reduction), matching the
            # event sim's continuous (unfloored) goalie skill response.
            for goalie in top_goalies:
                rating = goalie.overall_rating()
                if rating >= 95:  # Generational goalie
                    effects['defensive_reduction'] += 0.60
                elif rating >= 91:  # Elite goalie (Vezina level)
                    effects['defensive_reduction'] += 0.48
                elif rating >= 88:  # Very good goalie
                    effects['defensive_reduction'] += 0.36
                elif rating >= 85:  # Good goalie
                    effects['defensive_reduction'] += 0.25
                elif rating >= 82:  # Decent goalie
                    effects['defensive_reduction'] += 0.16
                elif rating >= 79:  # Fringe starter
                    effects['defensive_reduction'] += 0.08
                elif rating >= 76:  # Replacement level
                    effects['defensive_reduction'] += 0.0
                else:  # Below replacement: actively costs goals
                    effects['defensive_reduction'] -= 0.12
        
            # Cap the effects to prevent unrealistic swings
            effects['offensive_boost'] = min(0.4, effects['offensive_boost'])
            effects['defensive_reduction'] = min(0.7, effects['defensive_reduction'])
            # Clutch: dynamic per-team factor (team_clutch.py), shared with the
            # advanced engine so factor parity holds by construction. Replaces
            # the old saturated accumulation (forward tiers were on the wrong
            # rating scale -- 1.00 for every club).
            try:
                from team_clutch import team_clutch_factor
                effects['clutch_factor'] = team_clutch_factor(
                    team, league=getattr(self, 'league', None),
                    situation_score=situation_score)
            except Exception:
                effects['clutch_factor'] = 1.0
        
            return effects


        def _career_morale_modifier(self, team) -> float:
            """FM-style squad-confidence modifier from average morale.

            Native 1-100 morale: 70 is neutral, each point moves expectations
            0.03% -- factor-calibrated 2026-09-29 vs the event sim, whose
            per-shot morale channel moves a fully toxic room only ~-1.3%
            (the old 0.1%/pt, +/-3% intent, overstated it ~2.5x). Own channel
            next to the situations factor: situations reads room structure,
            bench buy-in and hunger counts; this reads the squad's raw
            confidence level. Applied only in the lightweight quick-sim.
            """
            try:
                roster = getattr(team, "roster", []) or []
                if not roster:
                    return 1.0
                avg = sum((getattr(p, "morale", 70) or 70) for p in roster) / len(roster)
                return max(0.97, min(1.03, 1.0 + (avg - 70) * 0.0003))
            except Exception:
                return 1.0


        def _generate_player_stats(self, home_team, away_team, home_goals, away_goals):
            """Generate realistic individual player statistics from team game results.
        
            Ensures statistical coherence:
            - Team shots = sum of skater shots = opposing goalie shots_against
            - Hat tricks properly detected (3+ goals in one game)
            - Only dressed players (18 skaters + 1 goalie) get GP
            """
            import random
        
            # Track team shot totals for reconciliation
            team_shots = {}
        
            for team, team_goals, opp_goals in [(home_team, home_goals, away_goals), (away_team, away_goals, home_goals)]:
                # Dressed lineup: 12 forwards, 6 defensemen, 1 goalie (NHL standard: 18 skaters)
                # Injured or suspended players don't dress
                healthy = [p for p in team.roster
                           if not getattr(p, 'is_injured', False)
                           and not (getattr(p, 'suspension_games_remaining', 0)
                                    or 0)]
                forwards = [p for p in healthy if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:12]
                defensemen = [p for p in healthy if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:6]
                dressed_skaters = forwards + defensemen  # 18 skaters
            
                # Track per-player game goals for hat trick detection
                game_goals = {p.id: 0 for p in dressed_skaters}
            
                # Distribute goals and assists
                goals_to_distribute = team_goals
                # P1 (scoring calibration 2026-09-29): NHL-shaped assists per
                # goal -- 68% two, 30% one, 2% unassisted (A/G ~1.66). The
                # assister selection below stays ovr-weighted and unchanged.
                assists_to_distribute = sum(
                    random.choices([2, 1, 0], weights=[0.68, 0.30, 0.02])[0]
                    for _ in range(team_goals))
            
                # Weight players by rating for stat distribution
                weighted_players = []
                for player in dressed_skaters:
                    weight = player.overall_rating() / 100.0
                    if player.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']:
                        weight *= 1.5  # Forwards score more
                    weighted_players.append((player, weight))
            
                # Distribute goals
                for _ in range(goals_to_distribute):
                    if weighted_players:
                        weights = [w[1] for w in weighted_players]
                        player = random.choices([w[0] for w in weighted_players], weights=weights)[0]
                    
                        player.stats.goals += 1
                        player.stats.shots += 1  # Goal counts as shot
                        game_goals[player.id] += 1
                    
                        # Check for hat trick (3+ goals in THIS game)
                        if game_goals[player.id] == 3:
                            print(f"🎩 HAT TRICK! {player.first_name} {player.last_name} scores 3 goals!")
                            # GUI has no per-game event feed; stash on a best-effort list
                            notable = getattr(self, 'notable_events', None)
                            if notable is None:
                                notable = self.notable_events = []
                            notable.append({
                                'time': 3600, 'period': 3, 'team': team.team_name,
                                'player': player, 'event': 'Hat Trick'
                            })
                    
                        self._check_player_records(player)
            
                # Distribute assists (1-2 per goal, not to the scorer)
                for _ in range(assists_to_distribute):
                    if weighted_players:
                        # Pick assister (can be same as scorer for simplicity, or exclude)
                        weights = [w[1] for w in weighted_players]
                        player = random.choices([w[0] for w in weighted_players], weights=weights)[0]
                        player.stats.assists += 1
                        self._check_player_records(player)
            
                # Penalty minutes (NHL: ~6-10 PIM per team per game)
                penalty_minutes = random.randint(6, 14)
                pim_remaining = penalty_minutes
                while pim_remaining > 0 and dressed_skaters:
                    player = random.choice(dressed_skaters)
                    pim = min(pim_remaining, random.choice([2, 2, 2, 4, 5]))
                    player.stats.penalties += 1
                    player.stats.penalties_in_minutes += pim
                    pim_remaining -= pim
            
                # Shots: distribute among skaters, track total for goalie reconciliation
                # NHL: ~30 shots per team per game
                total_shots = max(team_goals, random.randint(25, 35))  # At least as many shots as goals
                team_shots[team.team_name] = total_shots
            
                for _ in range(total_shots):
                    # Forwards get 75% of shots, defense 25%
                    if random.random() < 0.75 and forwards:
                        player = random.choice(forwards)
                    elif defensemen:
                        player = random.choice(defensemen)
                    else:
                        player = random.choice(dressed_skaters)
                    player.stats.shots += 1
            
                # Games played: ONLY dressed players (18 skaters)
                for player in dressed_skaters:
                    player.stats.games_played += 1
                    self._check_player_records(player)

                # Defensive record: every dressed skater leaves a hits /
                # takeaways / blocks trail (shutdown defensemen need a
                # performance record, not just points). Same shared roll as
                # every other sim path, so evaluator thresholds are uniform.
                try:
                    from game_classes import roll_defensive_game_stats as _rdg
                    for player in dressed_skaters:
                        _h, _t, _b = _rdg(player)
                        player.stats.hits += _h
                        player.stats.takeaways += _t
                        player.stats.blocked_shots += _b
                except Exception:
                    pass
        
            # Goalie stats: shots_against MUST equal opposing team's shots (coherence!)
            for team, team_goals, opp_goals in [(home_team, home_goals, away_goals), (away_team, away_goals, home_goals)]:
                starting_goalie = self._select_starting_goalie(team)
                if not starting_goalie:
                    continue
                opp_team_name = away_team.team_name if team == home_team else home_team.team_name
            
                # Shots against = opposing team's total shots (from team_shots dict)
                shots_against = team_shots.get(opp_team_name, random.randint(25, 35))
                saves = max(0, shots_against - opp_goals)
            
                won = (team_goals > opp_goals)
                shutout = (opp_goals == 0)
            
                starting_goalie.stats.saves += saves
                starting_goalie.stats.shots_against += shots_against
                starting_goalie.stats.goals_against += opp_goals
                starting_goalie.stats.games_played += 1
                # Note: wins/losses/shutouts tracked elsewhere or via add_game_stats if available
                if hasattr(starting_goalie.stats, 'wins'):
                    if won:
                        starting_goalie.stats.wins += 1
                    else:
                        starting_goalie.stats.losses += 1
                    if shutout:
                        starting_goalie.stats.shutouts += 1
            
                self._check_player_records(starting_goalie)
            
                if shutout:
                    print(f"🥅 SHUTOUT! {starting_goalie.first_name} {starting_goalie.last_name} records a shutout!")


        def _late_six_on_five_news(self, home_team, away_team, ctx,
                                     trailing_team_is_home=False):
            """One headline when the late 6v5 produces the tying goal (ot_drama).

            Single hook: uses the existing GameManager -> GUI news path
            (add_news lives on the GUI; the manager only holds it via .app).
            No-op headless. Never raises.
            """
            try:
                _drivers = (ctx or {}).get("drivers") or []
                _flavor = _drivers[0] if _drivers else "Sheer desperation"
                _trail_team = home_team if trailing_team_is_home else away_team
                _lead_team = away_team if trailing_team_is_home else home_team
                _trailing = (getattr(_trail_team, "team_name", "")
                             or "The visitors")
                _story = (
                    f"\u00a9 LATE EQUALIZER: {_trailing} pull the goalie and force "
                    f"overtime against {getattr(_lead_team, 'team_name', 'the hosts')} -- "
                    f"{_flavor.lower()} willed it to OT.")
                _add = getattr(self, "add_news", None) or getattr(
                    getattr(self, "app", None), "add_news", None)
                if callable(_add):
                    _add(_story)
            except Exception:
                pass



    def _calculate_star_player_effects(self, team, situation_score=None):
        """Calculate individual star player effects on game outcome"""
        effects = {
            'offensive_boost': 0.0,
            'defensive_reduction': 0.0,
            'clutch_factor': 0.0
        }
        
        # Get top players by position -- only dressed players move the
        # needle. Suspended or injured stars don't boost the team from
        # the press box (same exclusion the strength calc uses).
        available = [p for p in team.roster
                     if not getattr(p, 'is_injured', False)
                     and not (getattr(p, 'suspension_games_remaining', 0)
                              or 0)]
        sorted_roster = sorted(available, key=lambda p: p.overall_rating(), reverse=True)
        top_forwards = [p for p in sorted_roster if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:3]
        top_defense = [p for p in sorted_roster if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:2]
        top_goalies = [p for p in sorted_roster if p.primary_position.name == 'GOALIE'][:1]
        
        # Elite forwards boost offensive production
        # D28 (Wave A, 2026-10-01, Muck): retiered to the true 1-100
        # talent bands. The old thresholds (52/50/47/44) handed nearly
        # every rostered forward the max effect -- a flat +0.4 for all 32
        # teams, the opposite of a hierarchy. Now aligned with the talent
        # tiers: Generational 92+ -> 0.25, Elite 88+ -> 0.18,
        # Very good 84+ -> 0.10, Good 80+ -> 0.05.
        for forward in top_forwards:
            rating = forward.overall_rating()
            if rating >= 92:  # Generational
                effects['offensive_boost'] += 0.25
            elif rating >= 88:  # Elite
                effects['offensive_boost'] += 0.18
            elif rating >= 84:  # Very good
                effects['offensive_boost'] += 0.10
            elif rating >= 80:  # Good
                effects['offensive_boost'] += 0.05
        
        # Elite defensemen reduce opponent scoring
        # (native 1-100 scale: ~84+ is a top-pair NHL defender)
        # (clutch moved to team_clutch.py -- shared dynamic factor)
        for defenseman in top_defense:
            rating = defenseman.overall_rating()
            if rating >= 93:  # Elite defender (Norris level)
                effects['defensive_reduction'] += 0.25
            elif rating >= 90:  # Very good defender
                effects['defensive_reduction'] += 0.15
            elif rating >= 87:  # Good defender
                effects['defensive_reduction'] += 0.08
            elif rating >= 84:  # Decent defender
                effects['defensive_reduction'] += 0.03
        
        # Elite goalies have major defensive impact
        # (native 1-100 scale: ~82+ is an NHL starter; 91+ is Vezina-tier)
        # Factor-calibrated 2026-09-29 vs the event sim: the event engine's
        # goalie response is ~2x the old tiers (weak goalie 86->30: +0.37
        # there vs +0.13 here; elite 87->95: -0.30 there vs -0.20 here).
        # Steepened through the NHL range and extended below it -- a bad
        # goalie actively bleeds goals (negative reduction), matching the
        # event sim's continuous (unfloored) goalie skill response.
        for goalie in top_goalies:
            rating = goalie.overall_rating()
            if rating >= 95:  # Generational goalie
                effects['defensive_reduction'] += 0.60
            elif rating >= 91:  # Elite goalie (Vezina level)
                effects['defensive_reduction'] += 0.48
            elif rating >= 88:  # Very good goalie
                effects['defensive_reduction'] += 0.36
            elif rating >= 85:  # Good goalie
                effects['defensive_reduction'] += 0.25
            elif rating >= 82:  # Decent goalie
                effects['defensive_reduction'] += 0.16
            elif rating >= 79:  # Fringe starter
                effects['defensive_reduction'] += 0.08
            elif rating >= 76:  # Replacement level
                effects['defensive_reduction'] += 0.0
            else:  # Below replacement: actively costs goals
                effects['defensive_reduction'] -= 0.12
        
        # Cap the effects to prevent unrealistic swings
        effects['offensive_boost'] = min(0.4, effects['offensive_boost'])
        effects['defensive_reduction'] = min(0.7, effects['defensive_reduction'])
        # Clutch: dynamic per-team factor (team_clutch.py), shared with the
        # advanced engine so factor parity holds by construction. Replaces
        # the old saturated accumulation (forward tiers were on the wrong
        # rating scale -- 1.00 for every club).
        try:
            from team_clutch import team_clutch_factor
            effects['clutch_factor'] = team_clutch_factor(
                team, league=getattr(self, 'league', None),
                situation_score=situation_score)
        except Exception:
            effects['clutch_factor'] = 1.0
        
        return effects

    def _career_morale_modifier(self, team) -> float:
        """FM-style squad-confidence modifier from average morale.

        Native 1-100 morale: 70 is neutral, each point moves expectations
        0.03% -- factor-calibrated 2026-09-29 vs the event sim, whose
        per-shot morale channel moves a fully toxic room only ~-1.3%
        (the old 0.1%/pt, +/-3% intent, overstated it ~2.5x). Own channel
        next to the situations factor: situations reads room structure,
        bench buy-in and hunger counts; this reads the squad's raw
        confidence level. Applied only in the lightweight quick-sim.
        """
        try:
            roster = getattr(team, "roster", []) or []
            if not roster:
                return 1.0
            avg = sum((getattr(p, "morale", 70) or 70) for p in roster) / len(roster)
            return max(0.97, min(1.03, 1.0 + (avg - 70) * 0.0003))
        except Exception:
            return 1.0

    def _generate_player_stats(self, home_team, away_team, home_goals, away_goals):
        """Generate realistic individual player statistics from team game results.
        
        Ensures statistical coherence:
        - Team shots = sum of skater shots = opposing goalie shots_against
        - Hat tricks properly detected (3+ goals in one game)
        - Only dressed players (18 skaters + 1 goalie) get GP
        """
        import random
        
        # Track team shot totals for reconciliation
        team_shots = {}
        
        for team, team_goals, opp_goals in [(home_team, home_goals, away_goals), (away_team, away_goals, home_goals)]:
            # Dressed lineup: 12 forwards, 6 defensemen, 1 goalie (NHL standard: 18 skaters)
            # Injured or suspended players don't dress
            healthy = [p for p in team.roster
                       if not getattr(p, 'is_injured', False)
                       and not (getattr(p, 'suspension_games_remaining', 0)
                                or 0)]
            forwards = [p for p in healthy if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:12]
            defensemen = [p for p in healthy if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:6]
            dressed_skaters = forwards + defensemen  # 18 skaters
            
            # Track per-player game goals for hat trick detection
            game_goals = {p.id: 0 for p in dressed_skaters}
            
            # Distribute goals and assists
            goals_to_distribute = team_goals
            # P1 (scoring calibration 2026-09-29): NHL-shaped assists per
            # goal -- 68% two, 30% one, 2% unassisted (A/G ~1.66). The
            # assister selection below stays ovr-weighted and unchanged.
            assists_to_distribute = sum(
                random.choices([2, 1, 0], weights=[0.68, 0.30, 0.02])[0]
                for _ in range(team_goals))
            
            # Weight players by rating for stat distribution
            weighted_players = []
            for player in dressed_skaters:
                weight = player.overall_rating() / 100.0
                if player.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']:
                    weight *= 1.5  # Forwards score more
                weighted_players.append((player, weight))
            
            # Distribute goals
            for _ in range(goals_to_distribute):
                if weighted_players:
                    weights = [w[1] for w in weighted_players]
                    player = random.choices([w[0] for w in weighted_players], weights=weights)[0]
                    
                    player.stats.goals += 1
                    player.stats.shots += 1  # Goal counts as shot
                    game_goals[player.id] += 1
                    
                    # Check for hat trick (3+ goals in THIS game)
                    if game_goals[player.id] == 3:
                        print(f"🎩 HAT TRICK! {player.first_name} {player.last_name} scores 3 goals!")
                        # GUI has no per-game event feed; stash on a best-effort list
                        notable = getattr(self, 'notable_events', None)
                        if notable is None:
                            notable = self.notable_events = []
                        notable.append({
                            'time': 3600, 'period': 3, 'team': team.team_name,
                            'player': player, 'event': 'Hat Trick'
                        })
                    
                    self._check_player_records(player)
            
            # Distribute assists (1-2 per goal, not to the scorer)
            for _ in range(assists_to_distribute):
                if weighted_players:
                    # Pick assister (can be same as scorer for simplicity, or exclude)
                    weights = [w[1] for w in weighted_players]
                    player = random.choices([w[0] for w in weighted_players], weights=weights)[0]
                    player.stats.assists += 1
                    self._check_player_records(player)
            
            # Penalty minutes (NHL: ~6-10 PIM per team per game)
            penalty_minutes = random.randint(6, 14)
            pim_remaining = penalty_minutes
            while pim_remaining > 0 and dressed_skaters:
                player = random.choice(dressed_skaters)
                pim = min(pim_remaining, random.choice([2, 2, 2, 4, 5]))
                player.stats.penalties += 1
                player.stats.penalties_in_minutes += pim
                pim_remaining -= pim
            
            # Shots: distribute among skaters, track total for goalie reconciliation
            # NHL: ~30 shots per team per game
            total_shots = max(team_goals, random.randint(25, 35))  # At least as many shots as goals
            team_shots[team.team_name] = total_shots
            
            for _ in range(total_shots):
                # Forwards get 75% of shots, defense 25%
                if random.random() < 0.75 and forwards:
                    player = random.choice(forwards)
                elif defensemen:
                    player = random.choice(defensemen)
                else:
                    player = random.choice(dressed_skaters)
                player.stats.shots += 1
            
            # Games played: ONLY dressed players (18 skaters)
            for player in dressed_skaters:
                player.stats.games_played += 1
                self._check_player_records(player)

            # Defensive record: every dressed skater leaves a hits /
            # takeaways / blocks trail (shutdown defensemen need a
            # performance record, not just points). Same shared roll as
            # every other sim path, so evaluator thresholds are uniform.
            try:
                from game_classes import roll_defensive_game_stats as _rdg
                for player in dressed_skaters:
                    _h, _t, _b = _rdg(player)
                    player.stats.hits += _h
                    player.stats.takeaways += _t
                    player.stats.blocked_shots += _b
            except Exception:
                pass
        
        # Goalie stats: shots_against MUST equal opposing team's shots (coherence!)
        for team, team_goals, opp_goals in [(home_team, home_goals, away_goals), (away_team, away_goals, home_goals)]:
            starting_goalie = self._select_starting_goalie(team)
            if not starting_goalie:
                continue
            opp_team_name = away_team.team_name if team == home_team else home_team.team_name
            
            # Shots against = opposing team's total shots (from team_shots dict)
            shots_against = team_shots.get(opp_team_name, random.randint(25, 35))
            saves = max(0, shots_against - opp_goals)
            
            won = (team_goals > opp_goals)
            shutout = (opp_goals == 0)
            
            starting_goalie.stats.saves += saves
            starting_goalie.stats.shots_against += shots_against
            starting_goalie.stats.goals_against += opp_goals
            starting_goalie.stats.games_played += 1
            # Note: wins/losses/shutouts tracked elsewhere or via add_game_stats if available
            if hasattr(starting_goalie.stats, 'wins'):
                if won:
                    starting_goalie.stats.wins += 1
                else:
                    starting_goalie.stats.losses += 1
                if shutout:
                    starting_goalie.stats.shutouts += 1
            
            self._check_player_records(starting_goalie)
            
            if shutout:
                print(f"🥅 SHUTOUT! {starting_goalie.first_name} {starting_goalie.last_name} records a shutout!")

    def _late_six_on_five_news(self, home_team, away_team, ctx,
                                 trailing_team_is_home=False):
        """One headline when the late 6v5 produces the tying goal (ot_drama).

        Single hook: uses the existing GameManager -> GUI news path
        (add_news lives on the GUI; the manager only holds it via .app).
        No-op headless. Never raises.
        """
        try:
            _drivers = (ctx or {}).get("drivers") or []
            _flavor = _drivers[0] if _drivers else "Sheer desperation"
            _trail_team = home_team if trailing_team_is_home else away_team
            _lead_team = away_team if trailing_team_is_home else home_team
            _trailing = (getattr(_trail_team, "team_name", "")
                         or "The visitors")
            _story = (
                f"\u00a9 LATE EQUALIZER: {_trailing} pull the goalie and force "
                f"overtime against {getattr(_lead_team, 'team_name', 'the hosts')} -- "
                f"{_flavor.lower()} willed it to OT.")
            _add = getattr(self, "add_news", None) or getattr(
                getattr(self, "app", None), "add_news", None)
            if callable(_add):
                _add(_story)
        except Exception:
            pass
    def _simulate_game_lightweight(self, home_team, away_team, preseason=False):
        """Ultra-fast game simulation with individual player effects and realistic scoring distribution.

        preseason: skip the individual season-stat pass -- exhibition
        scores stand, nobody's season line moves."""
        import random
        
        # Calculate base team strengths
        home_strength = self._calculate_team_strength(home_team) + 0.05  # Home ice advantage
        away_strength = self._calculate_team_strength(away_team)

        # Situations, once per team per game: the situations channel below
        # and the clutch factor both read it; resolving the room twice per
        # team would double its cost for no new information (pure read).
        try:
            from reputation_system import situations_factor as _sff
            _home_sit = _sff(home_team, {}) or {}
            _away_sit = _sff(away_team, {}) or {}
        except Exception:
            _home_sit, _away_sit = {}, {}

        # Add individual star player effects
        home_star_effects = self._calculate_star_player_effects(
            home_team, _home_sit.get("score"))
        away_star_effects = self._calculate_star_player_effects(
            away_team, _away_sit.get("score"))
        
        # Apply star player bonuses to team strength
        home_strength += home_star_effects['offensive_boost']
        away_strength += away_star_effects['offensive_boost']
        
        # Base goal expectation for NHL-like scoring
        base_goals = 2.11  # Parity-calibrated 2026-09-29 vs the event sim
        # (~3.05 goals/team/game healthy). Note: offensive_boost (+0.40) and
        # the home bonus (+0.05) sit INSIDE the strength term, so the 2.5
        # slope scales them too; the anchor absorbs that level shift while
        # the slope carries the team-quality spread. (Recalibrated +0.24
        # when the harness started deep-copying teams per game -- the old
        # aggregate was injury-depressed; the true healthy reference level
        # is ~3.05, not ~2.9.)
        home_goal_expectation = base_goals + (home_strength - 0.75) * 2.5
        away_goal_expectation = base_goals + (away_strength - 0.75) * 2.5
        
        # Apply defensive effects (elite goalies/defense reduce opponent scoring)
        home_goal_expectation -= away_star_effects['defensive_reduction']
        away_goal_expectation -= home_star_effects['defensive_reduction']
        
        # Allow for low-scoring games but maintain reasonable averages
        home_goal_expectation = max(1.0, min(4.5, home_goal_expectation))
        away_goal_expectation = max(1.0, min(4.5, away_goal_expectation))

        # Installed NHL systems (tactics.py): the single shared tactics
        # channel -- the same matchup_modifiers() the event sims apply per
        # shot. (Factor parity 2026-09-29: the old additive _tactic_shifts
        # double-counted tactics here -- the legacy slider already folds
        # into tactics.py's resolution -- making rush/trap responses ~2x
        # the event sim's. Removed; both engines now read one channel.)
        # Your attack vs their structure; pace moves total goals;
        # PP/PK systems nudge season-level expectations (there is no
        # per-man-advantage state in the lightweight path).
        try:
            import tactics as _tx
            _tx.ensure_team_tactics(home_team)
            _tx.ensure_team_tactics(away_team)
            _mm = _tx.matchup_modifiers(home_team, away_team)
            home_goal_expectation *= _mm["home_goals"] * _mm["pace"]
            away_goal_expectation *= _mm["away_goals"] * _mm["pace"]
            home_goal_expectation *= 1.0 + (_mm["home_pp"] - 1.0) * 0.15
            away_goal_expectation *= 1.0 + (_mm["away_pp"] - 1.0) * 0.15
            # Tactics x home-ice interaction (parity 2026-09-29, lightweight
            # only): in the event sim, rush hockey's extra shot volume
            # interacts with home-ice edges (last change, crowd) so the HOME
            # side converts the extra chances at a higher rate -- the away
            # team's rush boost is partly eaten. The additive lightweight
            # misses this emergent effect; model it as a small dampener on
            # the AWAY tactic multiplier. It fires only when the AWAY team
            # commits to an offensive game (their even-strength tactic --
            # generated clubs all play "Balanced", so ordinary baselines and
            # trap games are exactly untouched), scaled by the actual event
            # level (pace) and their shot volume. The home side is untouched.
            # A few arithmetic ops.
            _es_away = (getattr(away_team, "tactic_even_strength", "Balanced")
                        or "Balanced")
            _rush_posture = {"Very Offensive": 1.0, "Offensive": 0.5}.get(
                _es_away, 0.0)
            if _rush_posture > 0.0:
                _rush_volume = max(0.0, _mm["pace"] - 1.0)
                _away_shot_volume = max(0.0, _mm["away_shot_vol"] - 1.0)
                if _rush_volume > 0.0 and _away_shot_volume > 0.0:
                    _rxhi = (_RUSH_X_HOME_ICE_K * _rush_posture
                             * _rush_volume * _away_shot_volume
                             * _HOME_ICE_EDGE)
                    away_goal_expectation *= max(0.70, 1.0 - _rxhi)
        except Exception:
            pass

        # Situations channel: room + bench + hunger move goal expectation a
        # few percent either way -- the same factor the detailed engines
        # (GameSim, AdvancedGameSim) apply per shot. Computed once per team
        # per game here (see _home_sit/_away_sit above); applies to every
        # team in the league, user or AI.
        # (Replaces the old squad-morale modifier, which situations subsumes.)
        try:
            home_goal_expectation *= float(_home_sit.get("xg_mult", 1.0))
            away_goal_expectation *= float(_away_sit.get("xg_mult", 1.0))
        except Exception:
            pass

        # FM-style squad confidence: raw morale average nudges expectations
        # +/-3% (own channel -- situations reads room structure, this reads
        # the squad's raw confidence level).
        home_goal_expectation *= self._career_morale_modifier(home_team)
        away_goal_expectation *= self._career_morale_modifier(away_team)

        # In-game fatigue (team_fatigue.py): the event sim scales each
        # shooter's shot/deke/pass volume by shift fatigue, paced by the
        # stamina/endurance/durability blend (condition_system, canonical).
        # The ~20% mean scoring drag is already absorbed in the calibrated
        # base_goals; this adds ONLY the team-level variation (iron-lung
        # rooms generate more volume than fragile ones), mean-neutral by
        # construction so the baseline doesn't move. Guarded -> 1.0 when
        # rosters/attributes are missing (exhibition, old saves). Applies
        # to every team, user or AI.
        try:
            from team_fatigue import team_fatigue_factor as _tff
            home_goal_expectation *= _tff(home_team)
            away_goal_expectation *= _tff(away_team)
        except Exception:
            pass
        
        # Generate goals with realistic NHL distribution
        # Use round() not int() to avoid truncation bias (~0.5 goals lost per team)
        # σ=2.05 (parity 2026-09-29, recalibrated 2026-09-30 on Caleb's new
        # tree): the event sim's score spread widened post-eb5101b (talent-
        # gradient restepening) to ~2.05; σ tracks it so the lightweight's
        # measured stddev (~2.0 after round/clip) matches. Team differences
        # carry the systematic variance; σ carries the game-level noise.
        home_goals = max(0, min(8, round(random.normalvariate(home_goal_expectation, 2.05))))
        away_goals = max(0, min(8, round(random.normalvariate(away_goal_expectation, 2.05))))
        
        # Apply clutch performance factors in close games
        if abs(home_goals - away_goals) <= 1:
            home_clutch = home_star_effects['clutch_factor']
            away_clutch = away_star_effects['clutch_factor']
            
            # Star players can tip the balance in close games
            if home_clutch > away_clutch and random.random() < (home_clutch - away_clutch) * 0.3:
                if random.random() < 0.6:  # Add goal
                    home_goals += 1
                else:  # Prevent goal  
                    away_goals = max(0, away_goals - 1)
            elif away_clutch > home_clutch and random.random() < (away_clutch - home_clutch) * 0.3:
                if random.random() < 0.6:
                    away_goals += 1
                else:
                    home_goals = max(0, home_goals - 1)
        
        # Handle ties (NHL: 5-min 3v3 OT, then shootout)
        # Track if game went to OT for OTL point
        went_to_ot = False
        _drama_ctx = None  # ot_drama context; computed lazily, only when needed
        def _drama():
            # Local lazy loader: keeps the fast path fast when the game is
            # decided in regulation by 2+.
            nonlocal _drama_ctx
            if _drama_ctx is None:
                try:
                    from ot_drama import ot_context
                    _drama_ctx = ot_context(
                        home_team, away_team,
                        league=getattr(self, "league", None),
                        atmosphere=_pregame_atmosphere(
                            home_team, away_team,
                            league=getattr(self, "league", None)))
                except Exception:
                    _drama_ctx = {"ot_mult": 1.0, "home_win_edge": 0.0,
                                  "drama01": 0.3, "drivers": []}
            return _drama_ctx
        if home_goals == away_goals:
            went_to_ot = True
        elif abs(home_goals - away_goals) == 1:
            # OT drama, live lever (ot_drama): the trailing coach pulls the
            # goalie and the end-game 6v5 resolves honestly -- tying goal
            # (game goes to OT), empty-netter (lead grows), or nothing.
            # Both scoring outcomes are real goals; nothing is manufactured.
            # Regulation scoring means are never touched.
            try:
                from ot_drama import late_six_on_five as _l65
                _6v5_ctx = _drama()
                _trailing_is_home = home_goals < away_goals
                _seg, _pull_secs = _l65(
                    _6v5_ctx, trailing_team_is_home=_trailing_is_home)
                if _seg == "tie":
                    went_to_ot = True
                    if _trailing_is_home:
                        home_goals += 1
                    else:
                        away_goals += 1
                    self._late_six_on_five_news(
                        home_team, away_team, _6v5_ctx,
                        trailing_team_is_home=_trailing_is_home)
                elif _seg == "empty_net":
                    if _trailing_is_home:
                        away_goals += 1
                    else:
                        home_goals += 1
            except Exception:
                pass
        if went_to_ot:
            _ctx = _drama()
            # Chris 2026-09-29 tuning: dynamic factors decide OT, not a fixed
            # home handout. Base is a coin flip; clutch counts as
            # home-minus-away (both rooms' big-game players matter); the
            # drama edge already nets home vs away morale/situations/crowd.
            # Hard 60/40 cap either way.
            # Clutch 2026-09-29: dynamic per-team factor (team_clutch.py),
            # shared with the advanced engine. Matchup heat lets big-game
            # rooms lift in heated OT; fragile rooms get nothing extra.
            try:
                from team_clutch import team_clutch_factor as _tcf
                _clutch_heat = float(_ctx.get("drama01", 0.0) or 0.0) * 100.0
                _clutch_lg = getattr(self, "league", None)
                clutch_edge = ((_tcf(home_team, league=_clutch_lg,
                                     matchup_heat=_clutch_heat,
                                     situation_score=_home_sit.get("score"))
                                - _tcf(away_team, league=_clutch_lg,
                                       matchup_heat=_clutch_heat,
                                       situation_score=_away_sit.get("score"))) * 0.08)
            except Exception:
                clutch_edge = ((home_star_effects['clutch_factor']
                                - away_star_effects['clutch_factor']) * 0.08)
            home_ot_chance = (0.50 + clutch_edge
                              + _ctx.get("home_win_edge", 0.0))
            # OT drama, live lever (ot_drama): 3v3 matchup choices. The
            # coach's personnel acumen plus the room/crowd edge tilt OT
            # finishing a touch, bounded small.
            try:
                from ot_drama import ot_matchup_tilt as _omt
                from game_classes import StaffRole as _SR
                _hc = (home_team.get_staff_by_role(_SR.HEAD_COACH) or [None])[0]
                _ac = (away_team.get_staff_by_role(_SR.HEAD_COACH) or [None])[0]
                home_ot_chance += _omt(_ctx, home_coach=_hc, away_coach=_ac)
            except Exception:
                pass
            home_ot_chance = max(0.40, min(0.60, home_ot_chance))
            if random.random() < home_ot_chance:
                home_goals += 1
            else:
                away_goals += 1
        
        # Determine winner
        if home_goals > away_goals:
            winner = home_team
            loser = away_team
        else:
            winner = away_team
            loser = home_team
        
        # Generate realistic individual player stats (skipped for
        # preseason -- exhibitions don't touch season lines).
        if not preseason:
            self._generate_player_stats(home_team, away_team, home_goals, away_goals)

        # Gameplay injuries (grounded W4 rate: injury_data.QUICK_ENGINE_GENERAL_RATE
        # = 0.31/team/game -- Rotowire 2024-25; same shared decision as the
        # detailed sim, one decision two fidelities)
        try:
            import injury_data as _injury_data
            _inj_rate = _injury_data.QUICK_ENGINE_GENERAL_RATE
        except Exception:
            _inj_rate = 0.31
        for team in (home_team, away_team):
            if random.random() < _inj_rate:
                hurt = roll_game_injury(team)
                if hurt is not None and hasattr(self, 'notable_events'):
                    try:
                        self.notable_events.append({
                            'time': 3600, 'period': 3, 'team': team.team_name,
                            'player': hurt, 'event': 'Injury',
                            'details': f'{hurt.injury_type} ({hurt.games_remaining_injured} games)'
                        })
                    except Exception:
                        pass
        
        return winner, loser, (home_goals, away_goals), went_to_ot

    def _try_ai_ai_deadline_deal(self, initiator, teams, te, tsl, mgr):
        """One AI-initiated deadline deal. Seller moves a veteran for a
        pick/prospect; the buyer side goes through the real AI evaluation
        (ai_consider_trade + situational context). Returns True on a deal."""
        import random
        from game_classes import DraftPick
        iname = getattr(initiator, 'team_name', '')
        stance = tsl.stance(self, iname)
        # Pair sellers with buyers; anyone else shops opportunistically.
        partners = [t for t in teams if t is not initiator]
        random.shuffle(partners)
        seller, buyer = None, None
        if stance == 'seller':
            seller = initiator
            buyer = next((t for t in partners
                          if tsl.stance(self, getattr(t, 'team_name', ''))
                          in ('buyer', 'bubble')), None)
        else:
            buyer = initiator
            seller = next((t for t in partners
                           if tsl.stance(self, getattr(t, 'team_name', ''))
                           == 'seller'), None)
        if seller is None or buyer is None:
            return False
        # Seller's piece: highest-value veteran (30+) on an expiring-ish deal.
        # Clause-aware: a veteran whose NTC/NMC vetoes the move to this
        # buyer is skipped unless he'd waive for them (waiver stamped so
        # the trade preflight honors it).
        vets = [p for p in getattr(seller, 'roster', [])
                if getattr(p, 'age', 0) >= 29]
        if not vets:
            vets = list(getattr(seller, 'roster', []))
        if not vets:
            return False
        try:
            vets.sort(key=lambda p: te.player_trade_value(p), reverse=True)
        except Exception:
            pass
        piece = None
        for _vet in vets:
            _vetoes = te.trade_vetoes(seller, buyer, [_vet])
            if not _vetoes:
                piece = _vet
                break
            _ok, _why = te.will_waive_ntc(_vet, seller, buyer)
            if _ok:
                try:
                    _vet.contract.ntc_waiver_for = getattr(
                        buyer, 'team_name', '')
                except Exception:
                    pass
                piece = _vet
                break
            print(f"deadline: {getattr(_vet, 'full_name', '?')} vetoed "
                  f"a move to {getattr(buyer, 'team_name', '?')} ({_why})")
        if piece is None:
            return False
        # Buyer's payment: a mid-round pick they own, else a prospect.
        payment = None
        try:
            for yr, picks in getattr(buyer, 'draft_picks', {}).items():
                for pk in picks:
                    if (isinstance(pk, DraftPick)
                            and getattr(pk, 'current_team', '')
                            == getattr(buyer, 'team_name', '')
                            and pk.round in (2, 3, 4)):
                        payment = pk
                        break
                if payment:
                    break
        except Exception:
            payment = None
        if payment is None:
            prospects = [p for p in getattr(buyer, 'roster', [])
                         if getattr(p, 'age', 99) <= 23]
            try:
                prospects.sort(key=lambda p: te.player_trade_value(p))
            except Exception:
                pass
            payment = prospects[0] if prospects else None
        if payment is None:
            return False
        sname = getattr(seller, 'team_name', '')
        bname = getattr(buyer, 'team_name', '')
        try:
            sit = tsl.situational_context(self, buyer, seller)
            # NOTE: user_assets = what the buyer RECEIVES ([piece]),
            # partner_assets = what the buyer GIVES ([payment]).
            resp = te.ai_consider_trade(buyer, [piece], [payment],
                                        user_team=seller, patience=1.0,
                                        situational=sit)
        except TypeError:
            # Older ai_consider_trade without the situational kwarg
            resp = te.ai_consider_trade(buyer, [piece], [payment],
                                        user_team=seller, patience=1.0)
        except Exception:
            return False
        if resp.decision != 'accept':
            # Deal died: the stamped single-use waiver must not survive it.
            try:
                if piece is not None and getattr(piece, "contract", None) \
                        is not None:
                    piece.contract.ntc_waiver_for = ""
            except Exception:
                pass
            return False
        try:
            trade = te.execute_trade(seller, buyer, [piece], [payment],
                                     date_str=self.current_date.isoformat(),
                                     league=getattr(self, "league", None))
        except Exception:
            try:
                if piece is not None and getattr(piece, "contract", None) \
                        is not None:
                    piece.contract.ntc_waiver_for = ""
            except Exception:
                pass
            return False
        if getattr(trade, 'summary', '').startswith("BLOCKED:"):
            # Clause veto at completion -- nothing moved, announce nothing.
            try:
                if piece is not None and getattr(piece, "contract", None) \
                        is not None:
                    piece.contract.ntc_waiver_for = ""
            except Exception:
                pass
            print(f"deadline deal blocked: {trade.summary}")
            return False
        # (Fresh start + steal watch now fire authoritatively inside
        # trade_engine.execute_trade -- every trade path gets them.)
        # Break the news: ticker + inbox.
        pay_label = te.asset_label(payment)
        piece_label = te.asset_label(piece)
        story = (f"TRADE: {bname} acquires {piece_label} from {sname} "
                 f"for {pay_label}.")
        try:
            mgr.breaking_news.append({'time': mgr.clock_display(),
                                      'story': story})
        except Exception:
            pass
        try:
            from email_generator import EmailGenerator
            email = EmailGenerator.create_league_announcement_email(
                f"🚨 Deadline Deal: {piece_label} to {bname}", story)
            email.is_urgent = True
            email.priority = 4
            self.send_email_to_user(email)
        except Exception:
            pass
        try:
            mgr.deadline_stats['total_trades'] += 1
            mgr.deadline_stats['players_moved'] += 1
        except Exception:
            pass
        print(f"⏰ {story}")
        return True

    def _update_offseason_reputations(self):
        """Offseason rollover: controversy cooldown, staff rep, Cup bonus.

        MUST run before league.end_of_season() -- standings (win%) are wiped
        by initialize_standings() inside it.
        """
        try:
            import reputation_system as rs
        except ImportError:
            return
        # Resolve the Cup champion from the playoff window, if one was played.
        champion_name = None
        bracket = None
        champ = None
        try:
            pw = self.open_windows.get('playoffs')
            if pw is not None and pw.winfo_exists():
                bracket = getattr(pw, 'playoff_bracket', None)
            if bracket is None:
                bracket = getattr(getattr(self, 'league', None),
                                  'playoff_bracket', None)
            if bracket is not None:
                champ = getattr(bracket, 'stanley_cup_champion', None)
                champion_name = getattr(champ, 'team_name', None)
        except Exception:
            pass
        # Bucket 5 (Muck 2026-10-02): cross-season fanbase memory.
        # Cup wins buy goodwill; missing playoffs extends the losing streak.
        try:
            from fan_narratives import apply_season_memory
            playoff_teams = set()
            try:
                if bracket is not None:
                    # Collect playoff participants from the bracket
                    for rnd in getattr(bracket, 'rounds', []) or []:
                        for series in getattr(rnd, 'series', []) or []:
                            for t in (getattr(series, 'home_team', None),
                                     getattr(series, 'away_team', None)):
                                tn = getattr(t, 'team_name', getattr(t, 'name', None))
                                if tn:
                                    playoff_teams.add(str(tn))
            except Exception:
                pass
            for _t in getattr(getattr(self, 'league', None), 'teams', []) or []:
                try:
                    _tn = str(getattr(_t, 'name', ''))
                    _won = bool(champion_name and _tn == str(champion_name))
                    _po = _tn in playoff_teams or _won
                    apply_season_memory(_t, won_cup=_won, made_playoffs=_po)
                except Exception:
                    pass
        except Exception:
            pass
        # League-average scoring pace for the reputation recompute below.
        league_avg_ppg = 0.8
        try:
            _tp = _tg = 0
            for _t in self.league.teams:
                for _p in getattr(_t, 'roster', []) or []:
                    _s = getattr(_p, 'stats', None)
                    _g = int(getattr(_s, 'games_played', 0) or 0)
                    if _g > 0:
                        _tg += _g
                        _tp += int(getattr(_s, 'goals', 0) or 0) + int(
                            getattr(_s, 'assists', 0) or 0)
            if _tg > 0:
                league_avg_ppg = _tp / _tg
        except Exception:
            pass
        # Jack Adams: most overachieving coach -- the same race the awards
        # ceremony uses. Matched to a Staff object once, up front.
        adams_staff = None
        try:
            import coach_records as _cr0
            from awards_race import adams_race as _ar0
            _race = _ar0(self.league.teams)
            if _race:
                adams_staff = _cr0.find_coach(
                    self.league.teams, _race[0].get("coach"),
                    _race[0].get("team"))
        except Exception:
            pass
        season_start = f"{self.league.season_year}-09-01"
        for team in self.league.teams:
            st = self.league.standings.get(team.team_name, {})
            w = st.get('W', st.get('Wins', 0))
            l = st.get('L', st.get('Losses', 0))
            otl = st.get('OTL', 0)
            win_pct = w / max(1, w + l + otl)
            is_champ = champion_name is not None and team.team_name == champion_name
            # Playoff result for the record book + playoff-success reputation.
            # 4 = Cup, 3 = lost Final, 2 = lost Division Finals, 1 = lost
            # earlier, 0 = missed.
            playoff_rounds_won = 0
            playoff_result = "Missed playoffs"
            try:
                import coach_records as _crp
                playoff_result = _crp.playoff_result_for_team(
                    team, bracket, champ)
                playoff_rounds_won = {
                    "Won Stanley Cup": 4, "Lost Stanley Cup Final": 3,
                    "Lost Division Finals": 2, "Lost Division Semifinals": 1,
                }.get(playoff_result, 0)
            except Exception:
                pass
            try:
                import accolades as _acc
                import coach_records as _crr
                _syr = getattr(self.league, "season_year", 0)
                _slabel = _crr.season_label(_syr)
                # Trophy-case year labels banked this season: ceremony year
                # ("2027") for the awards show, season label ("2026-27")
                # for the Cup/Smythe. Both count as "this season".
                _season_labels = {str(_syr + 1), _slabel}
            except Exception:
                _season_labels = set()
            # Captaincy growth: the room's regime figure for mentorship
            # (best letter-wearer's leadership). Computed once per team,
            # before any leadership moves, so every learner sees the same
            # number regardless of roster order.
            _cg_mentor_lead = None
            try:
                for _cap in team.roster:
                    if getattr(_cap, "captaincy", "") in ("C", "A"):
                        _cl = float(getattr(_cap, "leadership", 0) or 0)
                        _cg_mentor_lead = max(_cl, _cg_mentor_lead or 0)
            except Exception:
                pass
            for p in team.roster:
                incidents = sum(
                    1 for e in getattr(p, 'controversy_history', []) or []
                    if isinstance(e, dict) and e.get('date', '') >= season_start
                )
                rs.decay_controversy(p, incidents_this_season=incidents,
                                     team=team,
                                     coach=getattr(team, 'head_coach', None),
                                     win_pct=win_pct)
                if is_champ:
                    rs.award_championship(
                        p,
                        season_year=int(
                            getattr(self.league, "season_year", 0)
                            or 0))  # +8, ratchet-safe, season-idempotent
                    # The captain who lifts the Cup banks a little extra
                    # standing -- leading a champion is the signature
                    # leadership credential.
                    try:
                        import captaincy_growth as _cg1
                        _cg1.cup_captain_rep_bonus(
                            p, is_champ=is_champ,
                            season_year=int(
                                getattr(self.league, "season_year", 0)
                                or 0))
                    except Exception:
                        pass
                    # Trophy case: bank the Cup on every champion-roster
                    # player, labeled by season (e.g. "2026-27").
                    # Idempotent -- re-runs never duplicate.
                    try:
                        import accolades as _acc
                        _syr = getattr(self.league, "season_year", 0)
                        if _acc.bank_accolade(
                                p, "stanley_cup",
                                f"{_syr}-{str(_syr + 1)[-2:]}"):
                            # Legacy counter: career Cups. Idempotent via
                            # bank_accolade's True-on-new-add return, so
                            # immortality snapshots see the real total.
                            p.stanley_cups = int(
                                getattr(p, "stanley_cups", 0) or 0) + 1
                    except Exception:
                        pass
                # Playoff success builds reputation for every playoff team,
                # scaled by round. Recomputed from the trophy case (single
                # source of truth) so the Conn Smythe stacks with
                # regular-season awards instead of overwriting them.
                # Ratchet-safe: reputation never decreases.
                if playoff_rounds_won > 0:
                    try:
                        _awards = [
                            e.get("award")
                            for e in getattr(p, 'career_accolades', []) or []
                            if isinstance(e, dict)
                            and str(e.get("year")) in _season_labels]
                        _ps = getattr(p, 'stats', None)
                        rs.update_player_reputation(
                            p,
                            season_points=int(
                                getattr(_ps, 'goals', 0) or 0) + int(
                                getattr(_ps, 'assists', 0) or 0),
                            games_played=int(
                                getattr(_ps, 'games_played', 0) or 0),
                            league_avg_ppg=league_avg_ppg,
                            awards=_awards,
                            playoff_rounds_won=playoff_rounds_won)
                    except Exception:
                        pass
                # Captaincy forges leaders: tenure + team results + personal
                # impact grow leadership (the Toews/Crosby arc). Additive --
                # the development engine is never touched. Season-stamped
                # inside the module, so re-runs are safe.
                try:
                    import captaincy_growth as _cg2
                    _cg_res = _cg2.apply_captaincy_growth(
                        p,
                        season_year=int(
                            getattr(self.league, "season_year", 0) or 0),
                        win_pct=win_pct,
                        playoff_rounds_won=playoff_rounds_won,
                        is_champ=is_champ,
                        league_avg_ppg=league_avg_ppg)
                    _cg_story = _cg_res.get("milestone_story")
                    if _cg_story:
                        # add_news lives on the GUI; the manager only holds
                        # it via .app.
                        _cg_add = getattr(getattr(self, "app", None),
                                          "add_news", None)
                        if callable(_cg_add):
                            _cg_add(_cg_story)
                    # The Yzerman effect: young letter-less players absorb
                    # leadership from an elite, winning room.
                    _cg2.apply_mentorship_growth(
                        p,
                        season_year=int(
                            getattr(self.league, "season_year", 0) or 0),
                        win_pct=win_pct,
                        playoff_rounds_won=playoff_rounds_won,
                        is_champ=is_champ,
                        best_letter_leadership=_cg_mentor_lead)
                    # Legendary captain: the completed Toews/Crosby/Yzerman
                    # arc. Stamped once (flags + team icon status); the
                    # story fires exactly once.
                    try:
                        _cg_syr = int(
                            getattr(self.league, "season_year", 0) or 0)
                    except Exception:
                        _cg_syr = 0
                    if _cg2.stamp_legendary_captain(
                            p, getattr(team, "team_name", "") or "",
                            season_year=_cg_syr):
                        _cg_add2 = getattr(getattr(self, "app", None),
                                           "add_news", None)
                        if callable(_cg_add2):
                            _cg_nm = getattr(p, "full_name", None) \
                                or "The captain"
                            _cg_tn = getattr(team, "team_name", "") \
                                or "the franchise"
                            _cg_add2(
                                f"\u00a9 {_cg_nm} has completed the "
                                f"captain's arc: a LEGENDARY CAPTAIN, the "
                                f"face of {_cg_tn}.")
                except Exception:
                    pass
            for s in getattr(team, 'staff', []) or []:
                is_adams = adams_staff is not None and s is adams_staff
                # +12 for a Cup on the 0-100 career scale; +8 for a Jack
                # Adams; win% moves the rest.
                rs.update_staff_reputation(s, team_win_pct=win_pct,
                                           championships=1 if is_champ else 0,
                                           jack_adams=is_adams)
                # Year-by-year coaching record (head coaches AND assistants):
                # the hiring/firing evidence on the staff card Record tab.
                # Idempotent per (season, team).
                try:
                    import coach_records as _cr2
                    import accolades as _acc2
                    if _cr2.is_coaching_role(s):
                        _syr2 = getattr(self.league, "season_year", 0)
                        _slabel2 = _cr2.season_label(_syr2)
                        _cr2.record_staff_season(
                            s, _slabel2, team.team_name, w, l, otl,
                            playoff_result, jack_adams=is_adams)
                        if is_adams:
                            _acc2.bank_accolade(s, "jack_adams", _slabel2)
                        if is_champ:
                            _acc2.bank_accolade(s, "stanley_cup", _slabel2)
                except Exception:
                    pass
                # Another year with the club: the shelf-life clock ticks.
                try:
                    s.years_with_team = (getattr(s, 'years_with_team', 0) or 0) + 1
                except Exception:
                    pass
                # Coach volatility: losing humbles, a new sweater reforms.
                rs.decay_controversy(s, team=team, win_pct=win_pct)
                # Coach influence: recent success builds it, losing burns it.
                rs.develop_coach_influence(s, win_pct=win_pct, is_champ=is_champ,
                                           roster=team.roster)
            # Stash team results for the staff breakthrough roll: it runs
            # inside league.end_of_season(), after the standings are wiped,
            # so the season's shape has to be captured here. One-shot cache
            # -- the rollover consumes and clears it.
            try:
                _src = getattr(self.league, "_staff_results_cache", None)
                if not isinstance(_src, dict):
                    _src = {}
                    self.league._staff_results_cache = _src
                _src[team.team_name] = {
                    "w": w, "l": l, "otl": otl, "win_pct": win_pct,
                    "playoff": playoff_result, "champ": bool(is_champ),
                    "adams_id": getattr(adams_staff, "id", None),
                }
            except Exception:
                pass
            # Roster churn snapshot for next season's situations factor
            # (gelling vs battle-tested core). Once per team per offseason.
            try:
                rs.snapshot_roster_churn(team)
            except Exception:
                pass

    def _validate_season_continuity(self) -> bool:
        """Guard: season year must follow recorded history without gaps.

        Season transition (Muck 2026-10-02): the season year derives from
        actual game state, not date arithmetic. This validates that
        league.season_year is continuous with the seasons recorded in
        league_history -- no skipped seasons, no double-counting.

        Called from _start_offseason before the rollover. Returns True
        when continuous (or when there's no history yet to check against);
        returns False and logs loudly when a break is detected. Never
        raises, never mutates -- detection only, so a false positive can
        never corrupt numbering.
        """
        try:
            league = getattr(self, "league", None)
            if league is None:
                return True
            season_year = int(getattr(league, "season_year", 0) or 0)
            hist = getattr(self, "league_history", None)
            seasons = list(getattr(hist, "seasons", None) or [])
            if not seasons or not season_year:
                return True  # new career or no history -- nothing to check
            years = sorted(int(s.get("year", 0) or 0) for s in seasons
                           if isinstance(s, dict))
            years = [y for y in years if y]
            if not years:
                return True
            last_recorded = years[-1]
            # Normal mid-season state: the current season (season_year) is
            # in progress and not yet recorded, so it should be exactly
            # one past the last recorded season.
            # At _start_offseason post-record: _record_season_to_history
            # runs before the rollover, so season_year may EQUAL the
            # last recorded year (the just-finished season).
            # Either way, a gap of 2+ means a season was skipped.
            ok_continuous = (season_year == last_recorded or       # just recorded
                            season_year == last_recorded + 1)   # mid-season
            if not ok_continuous:
                try:
                    self.add_news(
                        f"⚠️ Season continuity break: league season_year is "
                        f"{season_year} but league history's last recorded "
                        f"season is {last_recorded}. A season may have been "
                        f"skipped by date manipulation -- numbering will "
                        f"not auto-correct; check the save.")
                except Exception:
                    pass
                return False
            # Internal gap check: recorded history itself must be gapless.
            for prev, cur in zip(years, years[1:]):
                if cur != prev + 1:
                    try:
                        self.add_news(
                            f"⚠️ Season history gap: recorded seasons jump "
                            f"from {prev} to {cur}.")
                    except Exception:
                        pass
                    return False
            return True
        except Exception:
            return True  # never block the transition on a guard failure

    def _weekly_coaching_mults(self, team, player, attrs, _cache,
                               assignment="nhl"):
        """Per-attribute coaching multipliers for the weekly all-team
        development tick. Same practice_breakdown math as practice
        sessions (drill knowledge, archetype affinity, attitude, fit,
        system) -- one mechanic for all 32 clubs, user and AI alike.
        D8: `assignment` ("nhl" | "ahl" | "overseas") splits the quality
        behind the bench by roster. Additive: returns 1.0 for anything it
        can't price. Never raises.
        """
        try:
            import coach_practice as _cp
        except Exception:
            return {}
        out = {}
        for attr in attrs:
            drill = _cp.attribute_drill(attr)
            if drill is None or not hasattr(player, attr):
                continue
            # Keyed by team AND assignment too: the same player object must
            # never borrow another club's staff pricing or another
            # roster's bench quality.
            key = (id(team), id(player), drill, assignment)
            mult = _cache.get(key)
            if mult is None:
                try:
                    mult = float(_cp.practice_breakdown(
                        team, player, drill,
                        assignment=assignment).get("total_mult", 1.0))
                except Exception:
                    mult = 1.0
                _cache[key] = mult
            out[attr] = mult
        return out

    def generate_trade_package(self, team, player_wanted, target_value):
        """Generate a trade package from the specified team targeting the given value."""
        # Sort team's roster by value (descending)
        team_players = sorted(team.roster, key=self.calculate_player_value, reverse=True)
        
        # Don't offer top 3 players unless getting a superstar
        if player_wanted.overall_rating() < 85:
            team_players = team_players[3:]
            
        # Don't offer more than 3 players
        max_players_to_offer = 3
        
        # Start with empty package
        package = []
        package_value = 0
        
        # Try to find a single player close to the target value
        for potential_player in team_players:
            player_value = self.calculate_player_value(potential_player)
            
            # Ideal single-player trade (within 10% of target)
            if 0.9 * target_value <= player_value <= 1.1 * target_value:
                return [potential_player]
        
        # If no ideal single player, build a package
        for potential_player in team_players:
            if len(package) >= max_players_to_offer:
                break
                
            player_value = self.calculate_player_value(potential_player)
            
            # Don't add players worth too little
            if player_value < target_value * 0.1:
                continue
                
            # Add player to package
            package.append(potential_player)
            package_value += player_value
            
            # If we've reached or exceeded target value, we're done
            if package_value >= target_value * 0.9:
                break
        
        # Only return package if it's worth at least 85% of target value
        if package and package_value >= target_value * 0.85:
            return package
            
        return None
    
    def present_trade_offers(self, offers):
        """Route AI trade offers to the inbox as negotiable proposals.

        FM24/EHM-style: no blocking modal. Each offer becomes a live
        negotiation the user can accept, decline, or counter on their own
        time -- closing everything in between answers nothing.
        """
        if not offers:
            return
        import trade_negotiation as tn

        # Group offers by player
        offers_by_player = {}
        for offer in offers:
            player = offer['player_wanted']
            if player not in offers_by_player:
                offers_by_player[player] = []
            offers_by_player[player].append(offer)

        # Add to news log
        self.news_log.append({
            'date': self.current_date,
            'story': f"Trade offers received for {len(offers_by_player)} player(s) on your trade block."
        })

        # One live negotiation per offer, delivered to the inbox
        for player, player_offers in offers_by_player.items():
            for offer in player_offers:
                try:
                    tn.incoming_offer(self, offer['team'],
                                      offer['offer'], player_wanted=player)
                except Exception as e:
                    print(f"incoming trade offer failed (non-fatal): {e}")
    
    def _log_slate_fallback(self, home_team, away_team, game_date, err,
                            tier, detail=""):
        """LOUD logging for every slate-guarantee fallback. Never silent.

        Prints a 🛟 SLATE-GUARANTEE line with game, error and fallback
        tier (plus the BUG-001 full traceback), bumps the
        self._slate_fallbacks counter, and appends to the news log when
        one exists.
        """
        try:
            self._slate_fallbacks = \
                int(getattr(self, '_slate_fallbacks', 0) or 0) + 1
        except Exception:
            self._slate_fallbacks = 1
        _hn = getattr(home_team, 'team_name', '?')
        _an = getattr(away_team, 'team_name', '?')
        _line = (f"🛟 SLATE-GUARANTEE [{tier}] {game_date} {_an} @ {_hn}: "
                 f"{err}"
                 + (f" -- {detail}" if detail else "")
                 + f" (fallback #{self._slate_fallbacks})")
        print(_line)
        try:
            import traceback as _tb
            _tb.print_exc()
        except Exception:
            pass
        try:
            _nl = getattr(self, 'news_log', None)
            if isinstance(_nl, list):
                _d = getattr(self, 'current_date', None) or game_date
                _nl.append({
                    'date': _d,
                    'story': (f"🛟 Slate guarantee ({tier}): {_an} @ {_hn} "
                              f"simmed via fallback sim ({err}).")})
        except Exception:
            pass

    def career(self):
        """Lazy FM-style career state, stored on the GameManager so it survives."""
        gm = self.game_manager
        career = getattr(gm, "career", None)
        if career is None:
            career = manager_career.CareerState()
            gm.career = career
        # Apply the "GM can be sacked" setting (Muck's flag)
        try:
            can_sack = self.get_settings().get('career', {}).get('gm_can_be_sacked', True)
            career.board.can_be_sacked = bool(can_sack)
        except Exception:
            pass
        return career

    def prompts_enabled(self, *args, **kwargs):
        """Generic shim: no-op (auto-generated, method not found in main.py)."""
        self._ui_notify('prompts_enabled', *args, **kwargs)








def launch_game_viewer_with_sim(home_team, away_team):
    """
    Run a full AdvancedGameSim and launch the professional GameViewer with real data
    """
    import tkinter as tk
    from GAME_VIEWER import launch_game_viewer
    
    print("Starting enhanced hockey simulation...")
    
    # Run the simulation (unified engine 2026-10-04: GameSim now has full
    # AdvancedGameSim parity, single engine for watched and simmed games)
    from simulation import GameSim
    sim = GameSim(home_team, away_team)
    winner, loser, scores, events, notable_events = sim.run()
    
    print(f"Simulation complete! {winner.team_name} {scores[0]} - {loser.team_name} {scores[1]}")
    print(f"Total events generated: {len(sim.event_log)}")
    print(f"Notable events: {len(notable_events)}")
    
    # Prepare data for the game viewer
    event_log = sim.event_log
    home_team_name = home_team.team_name
    away_team_name = away_team.team_name
    
    # Launch the professional game viewer using the new function
    print("Launching Professional Game Viewer with real simulation data...")
    launch_game_viewer(event_log, 3600, home_team_name, away_team_name)
    
    return winner, loser, scores, events, notable_events

def clamp(val, minv, maxv):
    """Clamp a value between minimum and maximum bounds"""
    return min(max(val, minv), maxv)
    return max(minv, min(maxv, val))


def _tier_label(player):
    """User-facing talent tier label for a player (never the numeric overall).

    Muck's directive 2026-10-01: the numeric overall is presentation-hidden
    everywhere; the tier table lives in attribute_composites only.
    """
    try:
        from attribute_composites import talent_tier_for_player
        return talent_tier_for_player(player)
    except Exception:
        return "Decent"


def _tier_sort_value(val):
    """Sort key for a tier cell: tier order (Generational first), with a
    numeric fallback for anything that isn't a tier label."""
    try:
        from attribute_composites import TALENT_TIERS, tier_index
        _tv = str(val).strip().removesuffix(' \u2b50').strip()
        if any(_tv == _name for _name, _lo, _hi in TALENT_TIERS):
            return (0, tier_index(_tv))
    except Exception:
        pass
    try:
        return (1, float(str(val).replace('$', '').replace(',', '')))
    except (ValueError, TypeError):
        return (2, str(val).lower())

# --- Advanced Simulation Engine ---


def _pregame_atmosphere(home_team, away_team, is_playoff=False, series_game=1,
                        elimination_game=False, milestone_home=False,
                        ceremony=False, outdoor=False, league=None):
    """Build the crowd state for tonight (arena_atmosphere).

    One dict lookup + arithmetic per game -- no per-tick cost. Returns a
    quiet neutral building on any failure.
    """
    try:
        from arena_atmosphere import pregame_crowd
        from narrative_ledger import active_ledger
        # Rivalry-store heat: the grudge-match boost. The ledger path
        # inside pregame_crowd reads narrative memory; this reads the
        # rivalry system's intensity (playoff wars, declared hate,
        # regional bad blood) -- regular-season games get the same heat
        # the playoff path already passes via series.rivalry_heat.
        _heat = 0.0
        try:
            from reputation_system import get_rivalry_heat
            _riv = getattr(league, "rivalries", None) or []
            _heat = float(get_rivalry_heat(_riv, home_team, away_team)
                          .get("heat", 0.0) or 0.0)
        except Exception:
            _heat = 0.0
        # Wave C (D34/D39): persistent fan sentiment, tonight's fan
        # favourites, and simmering (faced, still-alive) fan hate for the
        # returnees dressing on the visiting side.
        _fs = None
        _favs: list = []
        _hated: list = []
        try:
            from fan_sentiment import get_fan_sentiment
            _fs = get_fan_sentiment(home_team,
                                    getattr(league, "current_date", None))
        except Exception:
            _fs = None
        try:
            from reputation_system import is_fan_favourite, simmering_hate
            for _p in (getattr(home_team, "roster", None) or []):
                try:
                    if is_fan_favourite(home_team, _p):
                        _favs.append(
                            f"{getattr(_p, 'first_name', '')} "
                            f"{getattr(_p, 'last_name', '')}".strip())
                except Exception:
                    continue
            for _h in simmering_hate(
                    getattr(league, "rivalries", None) or [],
                    home_team, away_team):
                try:
                    _hated.append(_h.get("player_name", ""))
                except Exception:
                    continue
        except Exception:
            pass
        return pregame_crowd(
            home_team, away_team, ledger=active_ledger(),
            is_playoff=is_playoff, series_game=series_game,
            elimination_game=elimination_game,
            milestone_home=milestone_home, ceremony=ceremony,
            outdoor=outdoor, rivalry_heat=_heat,
            fan_sentiment=_fs, fan_fav_names=_favs,
            hated_returnee_names=_hated)
    except Exception:
        return {"energy": 50.0, "mood": 30.0, "drivers": [],
                "big_game": False}



# --- Main GUI Application ---
def qol_confirm(parent, title, message, confirm_text="Confirm", cancel_text="Cancel"):
    """Small modern confirm dialog in the charcoal/teal theme.

    Returns True when the user confirms, False otherwise.
    """
    result = {'ok': False}
    dlg = InGamePopup(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.resizable(False, False)
    dlg.configure(bg='#0e0e11')
    try:
        dlg.grab_set()
    except tk.TclError:
        pass

    def _close(ok):
        result['ok'] = ok
        try:
            dlg.grab_release()
        except tk.TclError:
            pass
        dlg.destroy()

    tk.Label(dlg, text=title, bg='#0e0e11', fg='#ffffff',
             font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=18, pady=(16, 6))
    tk.Label(dlg, text=message, bg='#0e0e11', fg='#a1a1aa',
             font=('Segoe UI', 10), wraplength=380, justify='left'
             ).pack(anchor='w', padx=18, pady=(0, 14))

    btn_frame = tk.Frame(dlg, bg='#0e0e11')
    btn_frame.pack(fill='x', padx=18, pady=(0, 16))
    tk.Button(btn_frame, text=cancel_text, command=lambda: _close(False),
              bg='#1e1e24', fg='#ffffff', activebackground='#2a2a32',
              activeforeground='#ffffff', relief='flat', padx=18, pady=8,
              font=('Segoe UI', 10)).pack(side='right')
    tk.Button(btn_frame, text=confirm_text, command=lambda: _close(True),
              bg='#3B82F6', fg='#0e0e11', activebackground='#2563EB',
              activeforeground='#0e0e11', relief='flat', padx=18, pady=8,
              font=('Segoe UI', 10, 'bold')).pack(side='right', padx=(0, 10))

    dlg.bind('<Escape>', lambda e: _close(False))
    dlg.bind('<Return>', lambda e: _close(True))
    dlg._qol_escape_close = lambda: _close(False)

    # Center over the parent window.
    try:
        dlg.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        x = px + max(0, (pw - dw) // 2)
        y = py + max(0, (ph - dh) // 3)
        dlg.geometry(f"+{x}+{y}")
    except tk.TclError:
        pass
    dlg.wait_window()
    return result['ok']


def _mix_hex(a, b, t=0.5):
    """Blend two hex colors; t=0 -> a, t=1 -> b. Never raises."""
    try:
        ha, hb = a.lstrip("#"), b.lstrip("#")
        ra, ga, ba = (int(ha[i:i + 2], 16) for i in (0, 2, 4))
        rb, gb, bb = (int(hb[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % (
            int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))
    except Exception:
        return a


def _player_needs_waivers(player):
    """Waiver eligibility, shared by the single- and multi-player demotion
    paths: non-exempt players (25+ or 160+ NHL games) must clear the wire;
    everyone else can be assigned quietly. Never raises."""
    try:
        _games = getattr(player, 'nhl_games_played', 0) or 0
        _age = getattr(player, 'age', 0) or 0
        return bool(_age >= 25 or _games >= 160)
    except Exception:
        return True


# Tactics x home-ice interaction (parity 2026-09-29, lightweight only): in
# the event sim, rush hockey's extra shot volume interacts with home-ice
# edges (last change, crowd) so the HOME side converts the extra chances
# at a higher rate -- the away team's rush boost is partly eaten. The
# lightweight applies tactic boosts per-team additively and misses this
# emergent effect; it is modeled as a small dampener on the AWAY tactic
# multiplier, firing only when the away team commits to an offensive
# even-strength tactic (generated clubs all play "Balanced", so ordinary
# baselines and trap games are exactly 1.0). Calibrated so the rush-vs-rush
# AWAY response matches the event sim (~+0.11 goals/game); the home-ice factor
# is the existing +0.05 lightweight strength edge. (Tuning review.)
#
# PARKED 2026-09-30 (caleb-integration): re-measured on Caleb's new tree
# (post-eb5101b talent-gradient restepening). The event sim's rush-vs-rush
# response is now home +0.43 / AWAY +0.61 -- the away side benefits MORE,
# the home-favoring interaction this dampener modeled no longer exists.
# K=0.0 disables it; the lightweight's natural rush response (~+0.54 away)
# now matches the event sim within tolerance. If Caleb's engine reverts to
# home-favoring rush dynamics, restore K=1000.0.
_RUSH_X_HOME_ICE_K = 0.0
_HOME_ICE_EDGE = 0.05


# Gating slice 4, Job 2B (Phase 4): the continue-blockers card is a
# non-modal ask_card (Eastside grammar). Dismiss = defer: the blockers
# persist until resolved and the top-nav pill re-reads the live continue
# state. The named resolver below answers post-load re-presents by
# blocker id against freshly recomputed blockers; the app reference is
# kept module-side (same pattern as staff_management_window._chain_app).
_BLOCKERS_APP = None


def _set_blockers_app(app):
    global _BLOCKERS_APP
    _BLOCKERS_APP = app


def _blockers_app():
    app = _BLOCKERS_APP
    if app is not None:
        return app
    try:
        import tkinter as _tk
        _root = _tk._default_root
        if _root is not None and hasattr(_root, "get_continue_state"):
            return _root
    except Exception:
        pass
    return None


def _continue_blockers_answer(session_id, dialog_id, value, **kwargs):
    """DIALOG_RESOLVERS['continue_blockers_answer']: the non-modal
    continue-blockers card answered on a post-load re-present (the live
    callback is gone). value is a blocker id (or '__close__'). Recomputes
    the blockers live, runs the matching jump action, refreshes the pill.
    Never raises."""
    try:
        app = _blockers_app()
        if app is None or value == "__close__":
            return False
        try:
            _label, _live = app.get_continue_state()
        except Exception:
            return False
        for _b in _live or []:
            if _b.get("id") == value:
                _act = _b.get("action")
                if _act:
                    try:
                        _act[1]()
                    except Exception:
                        pass
                break
        try:
            app.refresh_next_day_button()
        except Exception:
            pass
        return True
    except Exception:
        return False


try:
    from popup_system import (register_dialog_resolver as
                              _blockers_reg_resolver)
    _blockers_reg_resolver("continue_blockers_answer",
                           _continue_blockers_answer)
except Exception:
    pass


# -- Gating T2-Phase 3: playoffs-mode choice (end_of_season) ------------
# Yes opens the interactive bracket; No quick-sims the tournament
# headless and rolls to the offseason. Dismiss = defer (re-asked on the
# next end_of_season entry; the guard below keeps it honest). The answer
# survives save/load via resolver_args (season_year); a stale answer
# (season already advanced or playoffs complete) is a no-op.
_PLAYOFFS_MODE_APP = None


def _set_playoffs_mode_app(app):
    global _PLAYOFFS_MODE_APP
    _PLAYOFFS_MODE_APP = app


def _playoffs_mode_answer(session_id, dialog_id, value, **kwargs):
    """DIALOG_RESOLVERS['playoffs_mode_answer']."""
    try:
        app = _PLAYOFFS_MODE_APP
        if app is None:
            return False
        league = getattr(app, "league", None)
        if league is None:
            return False
        if str(getattr(league, "season_year", "")) != str(
                kwargs.get("season_year", "")):
            return False  # stale: season already advanced
        if app._playoffs_complete():
            return False  # already decided
        if value:
            app.open_playoffs_window()
        else:
            app._quick_sim_playoffs_headless()
            app._start_offseason()
        return True
    except Exception:
        return False

