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
        self.database_manager = initialize_game_database(self.league.teams)

        # P-5 is handled at creation time by name_safety (star-surname
        # filter in the name generators) -- no post-hoc scrub: there is no
        # real/fictional flag, so a scrub could not tell a generated
        # "Mikko Rantanen" from the real one.
        
        # Initialize media system
        self.media_system = MediaSystem(self)
        
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
