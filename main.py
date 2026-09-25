# main.py
# The central application file, now with an enhanced visual design.

import random
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, timedelta, datetime
from game_classes import League, Player, PlayerPosition, Staff, StaffRole, ScoutingReport, to_100_scale
from windows import (RosterWindow, FreeAgencyWindow, TradeWindow, ScoutingWindow, 
                     DraftWindow, ScheduleWindow, FinancesWindow, NewsWindow, 
                     GMOptionsWindow, EditLinesWindow, ContractNegotiationWindow, 
                     TradeBlockWindow, WaiversWindow, SetCaptainsWindow)
from ui_components import PlayerProfileWindow
from inbox_window import InboxWindow
# Professional Calendar System (Phase 4) - replaces old calendar_window
from calendar_window import CalendarWindow
from schedule_engine import ScheduleEngine, ScheduleConfiguration, ScheduleGenerationMode
from staff_management_window import StaffManagementWindow
from professional_scouting_window import ProfessionalScoutingWindow
from modern_scouting_window import ModernScoutingWindow
from stats_standings_window import StatsStandingsWindow
from GAME_VIEWER import launch_game_viewer
from draft_generator import generate_draft_class
from database_manager import initialize_game_database
from database_generator import generate_database, get_database_options
from save_load_system import GameSaveManager
# Import will be done dynamically in open_player_profile to avoid circular imports
import threading
from PIL import Image, ImageTk  # For icons/logos

# Import new modern UI systems
from ui_theme_system import create_modern_theme, ModernUITheme, ProfessionalWidgets
from typography_system import TypographySystem, TextStyles
from team_identity_system import nhl_identity
from modern_dashboard import ModernDashboard

# Import Trade Deadline Center
from trade_deadline_center import TradeDeadlineCenter, is_trade_deadline_day
from event_day_hubs import (DraftDayCentral, FreeAgencyFrenzy, is_draft_day,
                            is_free_agency_day, prompt_event_day)

# Import Phase 1 systems
from save_load_system import SaveLoadWindow, GameSaveManager
from playoff_system import PlayoffWindow
from atmospheric_dashboard import AtmosphericDashboard
from visual_identity_system import HockeyAtmosphereSystem
from smart_data_widgets import PlayerStatsCard, TeamStandingsWidget

# Import Player Development System
from player_development_system import PlayerDevelopmentEngine, initialize_player_potential

# Import optional Media System
from media_system import MediaSystem
from media_center_window import MediaCenterWindow

# Import Football Manager-style career systems
import manager_career

# Import position-specific attributes if available
try:
    from position_specific_attributes import PlayerV2, convert_to_v2
    POSITION_SPECIFIC_ATTRIBUTES_AVAILABLE = True
except ImportError:
    POSITION_SPECIFIC_ATTRIBUTES_AVAILABLE = False

# --- Constants for Data Generation ---
FIRST_NAMES = ["John", "Mike", "David", "Chris", "James", "Robert", "Daniel", "William", "Matt", "Joe", "Alex", "Connor", "Jack", "Ryan", "Nick", "Kyle", "Erik", "Peter", "Paul", "Mark", "Auston", "Sidney", "Nathan", "Leon", "Brad", "David"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Martin", "Lee", "Thompson", "White", "Harris", "Matthews", "Crosby", "MacKinnon", "Draisaitl", "Marchand", "Pastrnak"]

# --- Game Configuration Constants ---
PLAYER_POOL_SIZE = 2000
STAFF_POOL_SIZE = 600  # Increased to support 13-17 staff per team (32 teams)
NHL_ROSTER_SIZE = 23
AHL_ROSTER_SIZE = 20
PROSPECT_POOL_SIZE = 15
GAMES_PER_SIM_DAY = 8 
SALARY_CAP = 83_500_000
PLAYER_BUDGET = 92_000_000
START_DATE = date(datetime.now().year, 10, 1)

# --- Game Engine Class ---
class GameManager:
    """Manages the overall game state, including setup and season progression."""
    def __init__(self, league_name="EHM Clone Hockey League"):
        self.league = League(league_name)
        self.league.set_game_manager(self)  # Set reference for database access
        self.user_team = None
        self.startup_settings = None

        # New-game setup options (filled by apply_startup_settings)
        self.fog_of_war = True
        self.sim_detail = {}
        self.user_league = 'NHL'
        self.gm_name = 'General Manager'
        
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
        return self._ai_manager
        
    @property
    def record_manager(self):
        """Lazy initialization of record manager to avoid blocking startup"""
        if self._record_manager is None:
            from nhl_records import RecordManager
            self._record_manager = RecordManager()
        return self._record_manager
        
    def apply_startup_settings(self, settings):
        """Apply settings from startup window and generate database"""
        print("DEBUG: apply_startup_settings called!")
        print(f"DEBUG: Settings received: {settings}")
        
        self.startup_settings = settings
        print(f"Applying startup settings: {settings}")
        
        # Generate database based on selected size
        database_size = settings.get('database_size', 'Medium')
        print(f"Generating {database_size} database...")
        
        try:
            print("DEBUG: Attempting to import progress_window...")
            # Import progress window
            from progress_window import DatabaseGenerationProgress
            print("DEBUG: Progress window import successful")
            
            print("DEBUG: Attempting to import database_generator...")
            # Generate the comprehensive database with progress tracking
            from database_generator import generate_database, DatabaseGenerator, DATABASE_CONFIGURATIONS
            print("DEBUG: Database generator import successful")
            
            print(f"DEBUG: Available database configurations: {list(DATABASE_CONFIGURATIONS.keys())}")
            
            # Always generate database regardless of existing league
            print("DEBUG: Generating new database with full roster population...")
            # Show progress window during database generation
            with DatabaseGenerationProgress() as progress:
                def progress_callback(percentage, status, detail=""):
                    progress.update(percentage, status, detail)
                    print(f"DEBUG: Progress - {percentage}% - {status} - {detail}")
                
                config = DATABASE_CONFIGURATIONS[database_size]
                print(f"DEBUG: Using config: {config.name}")
                # New-game setup wizard can supply a custom DatabaseConfig
                # (league selection); otherwise use the size preset.
                db_config = settings.get('database_config')
                if db_config is not None:
                    print(f"DEBUG: Using wizard database config: {db_config.name}")
                    generator = DatabaseGenerator(db_config)
                else:
                    generator = DatabaseGenerator(config)
                print("DEBUG: DatabaseGenerator created, starting generation...")
                self.league = generator.generate_comprehensive_database(progress_callback)
                print("DEBUG: Database generation completed")
                self.league.set_game_manager(self)

                # New-game wizard options (stored for the session)
                self.fog_of_war = settings.get('fog_of_war', True)
                self.sim_detail = settings.get('sim_detail', {}) or {}
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
            
            # Apply comprehensive game settings
            print("DEBUG: Applying game settings...")
            self.apply_all_game_settings(settings)
            print("DEBUG: Game settings applied successfully")
            
            # Handle fantasy draft if enabled
            if settings.get('fantasy_draft', False):
                print("Fantasy draft enabled - starting interactive fantasy draft...")
                self.start_interactive_fantasy_draft()
            
            # Generate league schedule
            print("Generating league schedule...")
            if hasattr(self.league, 'generate_schedule'):
                self.league.generate_schedule()
            
            print(f"Database generation complete! {len(self.league.get_all_players())} total players.")
            print(f"Teams with players: {len([t for t in self.league.teams if len(t.roster) > 0])}")
            print(f"Teams with staff: {len([t for t in self.league.teams if len(t.staff) > 0])}")
            
        except Exception as e:
            print(f"Error generating database: {e}")
            import traceback
            traceback.print_exc()
            print("DEBUG: Falling back to old system...")
            
            # Initialize a basic league if none exists
            if not hasattr(self, 'league') or self.league is None:
                print("DEBUG: Creating basic league structure...")
                from game_classes import League
                self.league = League("NHL")
                # Add basic NHL teams
                from startup_window import NHL_TEAMS
                from game_classes import Team
                for team_name in NHL_TEAMS:
                    team = Team(team_name=team_name, city=team_name.split()[-1])
                    self.league.add_team(team)
                print(f"DEBUG: Created {len(self.league.teams)} basic teams")
                
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
        if "20 games" in season_length:
            self.games_per_season = 20
        elif "41 games" in season_length:
            self.games_per_season = 41
        else:
            self.games_per_season = 82
            
        print(f"Season configured for {self.games_per_season} games")
    
    def set_user_team(self, team_name):
        """Set the user's selected team"""
        if team_name and team_name != "Select your team...":
            for team in self.league.teams:
                if team.team_name == team_name:
                    self.user_team = team
                    print(f"User team set to: {team_name}")
                    return
            print(f"Warning: Could not find team '{team_name}'")
    
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
        print(f"DEBUG apply_all_game_settings: selected_team_name = '{selected_team_name}'")
        if selected_team_name and hasattr(self, 'league') and self.league:
            print(f"DEBUG: Looking for team in {len(self.league.teams)} teams...")
            team_found = False
            for team in self.league.teams:
                print(f"DEBUG: Checking team '{team.team_name}' == '{selected_team_name}'")
                if team.team_name == selected_team_name:
                    self.user_team = team
                    team.is_user_team = True
                    team_found = True
                    print(f"User team set to: {selected_team_name}")
                    break
            if not team_found:
                print(f"WARNING: Could not find team '{selected_team_name}' in league teams!")
        else:
            print(f"DEBUG: No team to set - selected_team_name={selected_team_name}, has league={hasattr(self, 'league') and self.league is not None}")
        
        # Basic game settings
        self.apply_game_difficulty(settings.get('difficulty', 'Normal'))
        self.configure_season_length(settings.get('season_length', 'Full Season (82 games)'))
        
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
                        team.salary_cap = 83500000  # Standard NHL cap
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

    def setup_new_game(self):
        """Initializes a new game world with teams, players, and staff using the comprehensive database system."""
        print("Setting up a new game with comprehensive player database...")
        
        # Initialize the comprehensive database system
        self.database_manager = initialize_game_database(self.league.teams)
        
        # Initialize media system
        self.media_system = MediaSystem(self)
        
        # Generate league schedule
        self.league.generate_schedule()
        
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
                setattr(goalie, "reflexes", random.randint(10, 18))
                setattr(goalie, "positioning", random.randint(10, 18))
                setattr(goalie, "rebound_control", random.randint(10, 18))
            else:
                # Position-specific base attributes (legacy system)
                goalie_attrs = {
                    "goaltending": random.randint(10, 18),
                    "reflexes": random.randint(10, 20),
                    "positioning": random.randint(10, 20),
                    "rebound_control": random.randint(8, 20),
                    "puck_handling": random.randint(5, 18),
                    "glove_hand": random.randint(8, 18),
                    "stick_side": random.randint(8, 18),
                    "breakaway_skill": random.randint(8, 18),
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
                setattr(defenseman, "checking", random.randint(10, 18))
                setattr(defenseman, "defensive_awareness", random.randint(10, 18))
                setattr(defenseman, "shot_blocking", random.randint(10, 18))
                setattr(defenseman, "strength", random.randint(10, 18))
            else:
                # Position-specific base attributes (legacy system)
                defense_attrs = {
                    "checking": random.randint(10, 18),
                    "defensive_awareness": random.randint(10, 18),
                    "shot_blocking": random.randint(10, 18),
                    "stickhandling": random.randint(8, 18),
                    "passing": random.randint(8, 18),
                    "skating": random.randint(10, 18),
                    "strength": random.randint(10, 18),
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
                setattr(forward, "shooting", random.randint(10, 18))
                setattr(forward, "passing", random.randint(10, 18))
                setattr(forward, "offensive_awareness", random.randint(10, 18))
                setattr(forward, "stickhandling", random.randint(10, 18))
                
                # Enhance centers with better faceoff skills
                if position == PlayerPosition.CENTER:
                    setattr(forward, "faceoffs", random.randint(10, 18))
            else:
                # Position-specific base attributes (legacy system)
                forward_attrs = {
                    "shooting": random.randint(8, 18),
                    "passing": random.randint(8, 18),
                    "offensive_awareness": random.randint(10, 18),
                    "deking": random.randint(8, 18),
                    "stickhandling": random.randint(8, 18),
                    "skating": random.randint(10, 18),
                }
                
                # Enhance centers with better faceoff skills
                if position == PlayerPosition.CENTER:
                    forward_attrs["faceoffs"] = random.randint(10, 18)
                
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
            "determination": random.randint(5, 20),
            "teamwork": random.randint(5, 20),
            "leadership": random.randint(5, 20),
            "discipline": random.randint(5, 20),
            "flair": random.randint(5, 20),
            "consistency": random.randint(5, 20),
            "important_matches": random.randint(5, 20),
            "morale": 10,
            
            # Physical attributes (affected by age)
            "strength": min(20, max(5, int(random.randint(8, 18) * (1 + youth_bonus - veteran_penalty)))),
            "injury_proneness": min(20, max(1, int(random.randint(1, 15) * (1 - youth_bonus + veteran_penalty)))),
            "endurance": min(20, max(5, int(random.randint(8, 18) * (1 + youth_bonus - veteran_penalty)))),
            "stamina": min(20, max(5, int(random.randint(8, 18) * (1 + youth_bonus - veteran_penalty)))),
            "speed": min(20, max(5, int(random.randint(8, 18) * (1 + youth_bonus - veteran_penalty)))),
            "durability": min(20, max(5, int(random.randint(8, 18) * (1 - youth_bonus + veteran_penalty)))),
            
            # Advanced attributes
            "vision": random.randint(5, 20),
            "shooting_accuracy": random.randint(5, 20),
            "shooting_power": random.randint(5, 20),
            "passing_accuracy": random.randint(5, 20),
            "passing_creativity": random.randint(5, 20),
            "puck_protection": random.randint(5, 20),
            "deflections": random.randint(5, 20),
            "hockey_iq": random.randint(5, 20),
            "composure": random.randint(5, 20),
            "aggressiveness": random.randint(5, 20),
            "work_rate": random.randint(5, 20),
            "anticipation": random.randint(5, 20),
            "decision_making": random.randint(5, 20),
            "focus": random.randint(5, 20),
            "confidence": random.randint(5, 20),
            "acceleration": random.randint(5, 20),
            "balance": random.randint(5, 20),
            "agility": random.randint(5, 20),
            
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
        
        # Elite players might get no-trade clauses
        if ovr >= 82 and age >= 27:
            player.contract.no_trade_clause = random.random() < 0.4

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
            StaffRole.VIDEO_COACH
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
            # Update team colors in UI if the UI is already set up
            if hasattr(self, 'modern_theme') and hasattr(self, 'style'):
                self._update_team_colors()
        else:
            print(f"Warning: Could not find team '{team_name}'. Available teams:")
            for team in self.league.teams:
                print(f"  - {team.team_name}")

    def _process_injury_recovery(self, teams_played=None):
        """Process injury recovery for all players.
        
        Decrements games_remaining_injured once per GAME PLAYED (not per day):
        only players whose team played today count down, and players hurt in
        today's game start counting down with their next missed game.
        """
        for team in self.league.teams:
            if teams_played is not None and team.team_name not in teams_played:
                continue
            for player in team.roster:
                if getattr(player, 'is_injured', False):
                    # Hurt today? Countdown starts with the next game they miss.
                    if getattr(player, 'injured_today', False):
                        player.injured_today = False
                        continue
                    remaining = getattr(player, 'games_remaining_injured', 0)
                    if remaining > 0:
                        player.games_remaining_injured = remaining - 1
                        
                        if player.games_remaining_injured <= 0:
                            # Player is healed!
                            player.is_injured = False
                            player.injury_type = "None"
                            player.games_remaining_injured = 0
                            print(f"✅ {player.first_name} {player.last_name} has recovered from injury!")
                            
                            # Notify if it's the user's team
                            if hasattr(self, 'user_team') and team == self.user_team:
                                if hasattr(self, 'news_log'):
                                    self.news_log.append({'date': self.current_date, 'story': f"🏥 {player.first_name} {player.last_name} has recovered from injury and is available."})

    def _process_monthly_development(self):
        """Run monthly player development for all players league-wide.
        
        Young players grow toward potential; veterans decline with age.
        Notable changes for the user's team get logged as news.
        """
        if not hasattr(self, '_dev_engine'):
            self._dev_engine = PlayerDevelopmentEngine()
        
        notable = []
        for team in self.league.teams:
            for roster_name in ('roster', 'prospects'):
                for player in getattr(team, roster_name, []) or []:
                    changes = self._dev_engine.process_monthly_development(player)
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

def roll_game_injury(team):
    """Roll a single in-game injury for a team (shared by detailed + batch sims).

    Weighted by injury_proneness and age; skips goalies and already-injured
    players. Returns the injured Player, or None if nobody was hurt.
    """
    import random
    candidates = []
    weights = []
    for p in getattr(team, 'roster', []):
        if getattr(p, 'is_injured', False):
            continue
        pos = getattr(p, 'primary_position', None)
        if pos and pos.name == 'GOALIE':
            continue
        proneness = getattr(p, 'injury_proneness', 10) or 10
        age = getattr(p, 'age', 25) or 25
        age_factor = max(0.5, min(2.0, (age - 20) / 10))
        candidates.append(p)
        weights.append(proneness * age_factor)
    if not candidates:
        return None
    injured = random.choices(candidates, weights=weights, k=1)[0]
    # Severity: Minor 1-3 games (60%), Moderate 4-10 (30%), Severe 11-25 (10%)
    severity_roll = random.random()
    if severity_roll < 0.6:
        games_missed = random.randint(1, 3)
        injury_type = random.choice(['Bruised ribs', 'Minor sprain', 'Sore shoulder', 'Tweaked knee'])
    elif severity_roll < 0.9:
        games_missed = random.randint(4, 10)
        injury_type = random.choice(['Sprained ankle', 'Pulled groin', 'Shoulder strain', 'Knee sprain'])
    else:
        games_missed = random.randint(11, 25)
        injury_type = random.choice(['Broken collarbone', 'Torn MCL', 'Concussion', 'Broken wrist'])
    injured.is_injured = True
    injured.injury_type = injury_type
    injured.games_remaining_injured = games_missed
    injured.last_injury = injury_type
    injured.injured_today = True  # recovery countdown starts with the NEXT game
    return injured

def best_lines(team):
    """Builds the best possible lineup for the given team based on player ratings and positions."""
    # Injured players can't dress: filter them out (fall back to full group if empty)
    def _healthy(players):
        healthy = [p for p in players if not getattr(p, 'is_injured', False)]
        return healthy if healthy else players
    # Select top 13 forwards, 8 defensemen, 2 goalies by position and rating
    forwards = _healthy([p for p in team.roster if p.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING]])
    defensemen = _healthy([p for p in team.roster if p.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]])
    goalies = _healthy([p for p in team.roster if p.primary_position == PlayerPosition.GOALIE])

    # Sort by overall rating
    forwards = sorted(forwards, key=lambda p: p.overall_rating(), reverse=True)[:13]  # Changed to 13 to ensure line 4 gets players
    defensemen = sorted(defensemen, key=lambda p: p.overall_rating(), reverse=True)[:8]  # Changed to 8 for 4 pairs
    goalies = sorted(goalies, key=lambda p: p.overall_rating(), reverse=True)[:2]

    # Build forward lines
    fw_lines = []
    
    # Keep track of players already assigned to lines
    assigned_forwards = []
    
    # For first line, try to get the best players by position
    lw1 = next((p for p in forwards if p.primary_position == PlayerPosition.LEFT_WING and p not in assigned_forwards), None)
    c1 = next((p for p in forwards if p.primary_position == PlayerPosition.CENTER and p not in assigned_forwards), None)
    rw1 = next((p for p in forwards if p.primary_position == PlayerPosition.RIGHT_WING and p not in assigned_forwards), None)
    
    # If we're missing players, fill with best remaining players
    remaining_for_line1 = [p for p in forwards if p not in [lw1, c1, rw1] and p not in assigned_forwards]
    if not lw1 and remaining_for_line1:
        lw1 = remaining_for_line1.pop(0)
    if not c1 and remaining_for_line1:
        c1 = remaining_for_line1.pop(0)
    if not rw1 and remaining_for_line1:
        rw1 = remaining_for_line1.pop(0)
    
    # Mark these players as assigned
    if lw1: assigned_forwards.append(lw1)
    if c1: assigned_forwards.append(c1)
    if rw1: assigned_forwards.append(rw1)
    fw_lines.append([lw1, c1, rw1])
    
    # For the remaining 3 lines, build with best available players
    for line_num in range(1, 4):
        line = []
        for pos_type in [PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING]:
            # Try to get a natural fit first
            player = next((p for p in forwards if p.primary_position == pos_type and p not in assigned_forwards), None)
            
            # If no natural fit, take best available
            if not player:
                remaining = [p for p in forwards if p not in assigned_forwards]
                if remaining:
                    player = remaining[0]
            
            # Add player to line and mark as assigned
            if player:
                line.append(player)
                assigned_forwards.append(player)
            else:
                line.append(None)
        
        fw_lines.append(line)

    # Build defense pairs with natural LD/RD if possible
    def_pairs = []
    assigned_defense = []
    
    # For each pair, try to get a natural LD and RD - changed to 4 pairs
    for _ in range(4):
        ld = next((p for p in defensemen if (p.primary_position == PlayerPosition.LEFT_DEFENSE or p.primary_position == PlayerPosition.DEFENSE) and p not in assigned_defense), None)
        rd = next((p for p in defensemen if (p.primary_position == PlayerPosition.RIGHT_DEFENSE or p.primary_position == PlayerPosition.DEFENSE) and p != ld and p not in assigned_defense), None)
        
        # Mark these players as assigned
        if ld: assigned_defense.append(ld)
        if rd: assigned_defense.append(rd)
        def_pairs.append([ld, rd])
    
    # Build Power Play units
    # Use top offensive forwards and offensive defensemen
    offensive_forwards = sorted(forwards, key=lambda p: (
        getattr(p, 'offensive_awareness', 0) * 0.4 + 
        getattr(p, 'shooting', 0) * 0.3 + 
        getattr(p, 'passing', 0) * 0.3
    ), reverse=True)
    
    offensive_defensemen = sorted(defensemen, key=lambda p: (
        getattr(p, 'offensive_awareness', 0) * 0.4 + 
        getattr(p, 'shooting', 0) * 0.3 + 
        getattr(p, 'passing', 0) * 0.3
    ), reverse=True)
    
    pp1_forwards = offensive_forwards[:3] if len(offensive_forwards) >= 3 else offensive_forwards + [None] * (3 - len(offensive_forwards))
    pp2_forwards = offensive_forwards[3:6] if len(offensive_forwards) >= 6 else offensive_forwards[3:] + [None] * (3 - len(offensive_forwards[3:]))
    
    pp1_defense = offensive_defensemen[:2] if len(offensive_defensemen) >= 2 else offensive_defensemen + [None] * (2 - len(offensive_defensemen))
    pp2_defense = offensive_defensemen[2:4] if len(offensive_defensemen) >= 4 else offensive_defensemen[2:] + [None] * (2 - len(offensive_defensemen[2:]))
    
    # Build Penalty Kill units
    # Use defensively strong forwards
    defensive_forwards = sorted(forwards, key=lambda p: (
        getattr(p, 'defensive_awareness', 0) * 0.4 + 
        getattr(p, 'shot_blocking', 0) * 0.3 + 
        getattr(p, 'work_rate', 0) * 0.3
    ), reverse=True)
    
    defensive_defensemen = sorted(defensemen, key=lambda p: (
        getattr(p, 'defensive_awareness', 0) * 0.4 + 
        getattr(p, 'shot_blocking', 0) * 0.4 + 
        getattr(p, 'checking', 0) * 0.2
    ), reverse=True)
    
    pk1_forwards = defensive_forwards[:2] if len(defensive_forwards) >= 2 else defensive_forwards + [None] * (2 - len(defensive_forwards))
    pk2_forwards = defensive_forwards[2:4] if len(defensive_forwards) >= 4 else defensive_forwards[2:] + [None] * (2 - len(defensive_forwards[2:]))
    
    pk1_defense = defensive_defensemen[:2] if len(defensive_defensemen) >= 2 else defensive_defensemen + [None] * (2 - len(defensive_defensemen))
    pk2_defense = defensive_defensemen[2:4] if len(defensive_defensemen) >= 4 else defensive_defensemen[2:] + [None] * (2 - len(defensive_defensemen[2:]))

    # Build the complete lineup
    lines = {
        'Forwards': fw_lines,
        'Defense': def_pairs,
        'Goalies': goalies[:2] if len(goalies) >= 2 else goalies + [None] * (2 - len(goalies)),
        'PP1': {'Forwards': pp1_forwards, 'Defense': pp1_defense},
        'PP2': {'Forwards': pp2_forwards, 'Defense': pp2_defense},
        'PK1': {'Forwards': pk1_forwards, 'Defense': pk1_defense},
        'PK2': {'Forwards': pk2_forwards, 'Defense': pk2_defense},
        'Strategies': {
            'EvenStrength': 'Balanced',
            'PowerPlay': 'Offensive',
            'PenaltyKill': 'Defensive',
            'LeadingBy2+': 'Defensive',
            'TrailingBy2+': 'Very Offensive',
            'ForeCheckIntensity': 50,
            'DefensiveStructure': 'Standard',
            'Aggression': 50
        }
    }
    return lines

def launch_game_viewer_with_sim(home_team, away_team):
    """
    Run a full AdvancedGameSim and launch the professional GameViewer with real data
    """
    import tkinter as tk
    from GAME_VIEWER import RebuiltNHLGameViewer, launch_game_viewer
    
    print("Starting enhanced hockey simulation...")
    
    # Run the advanced simulation
    sim = AdvancedGameSim(home_team, away_team)
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

# --- Advanced Simulation Engine ---

class LiveHockeySimulation:
    """Real-time live hockey simulation engine that generates events as they happen"""
    
    def __init__(self, home_team="Thunderbirds", away_team="Eagles"):
        self.home_team = home_team
        self.away_team = away_team
        
        # Live game state
        self.game_state = {
            'period': 1,
            'time_remaining': 1200,  # 20 minutes in seconds
            'home_score': 0,
            'away_score': 0,
            'possession': home_team,
            'zone': 'neutral',  # defensive, neutral, offensive
            'game_situation': 'even_strength',  # even_strength, powerplay, penalty_kill
            'faceoff_location': 'center_ice'
        }
        
        # Live event tracking
        self.live_events = []
        self.current_shift_time = 0
        self.shift_length = random.randint(30, 90)  # Shift length in seconds
        
        # Player energy and fatigue
        self.player_energy = {self.home_team: {}, self.away_team: {}}
        self._initialize_players()
        
        # Live statistics
        self.live_stats = {
            'shots': {self.home_team: 0, self.away_team: 0},
            'hits': {self.home_team: 0, self.away_team: 0},
            'faceoffs': {self.home_team: 0, self.away_team: 0},
            'penalties': {self.home_team: 0, self.away_team: 0}
        }
        
        # Real-time callbacks for the viewer
        self.event_callbacks = []
        self.state_callbacks = []
        
    def _initialize_players(self):
        """Initialize player rosters with realistic names and stats"""
        positions = ['C', 'LW', 'RW', 'LD', 'RD', 'G']
        
        # Generate realistic hockey player names
        first_names = ['Connor', 'Nathan', 'Alexander', 'William', 'David', 'Erik', 'Ryan', 'Tyler', 'Brandon', 'Jake', 
                      'Mitchell', 'Trevor', 'Jonathan', 'Michael', 'Patrick', 'Kyle', 'Zach', 'Matt', 'Justin', 'Sean']
        last_names = ['Johnson', 'Anderson', 'Williams', 'Brown', 'Wilson', 'Miller', 'Davis', 'Garcia', 'Rodriguez', 'Martinez',
                     'Lindstrom', 'Karlsson', 'Johansson', 'Petersen', 'Nielsen', 'Hansen', 'Olsen', 'Larsen', 'Andersen', 'Christensen']
        
        for team in [self.home_team, self.away_team]:
            self.player_energy[team] = {}
            for i in range(20):  # 20 players per team
                name = f"{random.choice(first_names)} {random.choice(last_names)}"
                position = positions[i % len(positions)]
                jersey = i + 1
                
                self.player_energy[team][name] = {
                    'jersey': jersey,
                    'position': position,
                    'energy': 100.0,
                    'skill': random.randint(65, 95),
                    'on_ice': i < 6,  # First 6 players start on ice
                    'goals': 0,
                    'assists': 0,
                    'shots': 0,
                    'hits': 0,
                    'penalties': 0,
                    'ice_time': 0
                }
    
    def register_event_callback(self, callback):
        """Register a callback function to receive live events"""
        self.event_callbacks.append(callback)
    
    def register_state_callback(self, callback):
        """Register a callback function to receive game state updates"""
        self.state_callbacks.append(callback)
    
    def _fire_event(self, event):
        """Fire an event to all registered callbacks"""
        self.live_events.append(event)
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in event callback: {e}")
    
    def _fire_state_update(self):
        """Fire a state update to all registered callbacks"""
        for callback in self.state_callbacks:
            try:
                callback(self.game_state.copy())
            except Exception as e:
                print(f"Error in state callback: {e}")
    
    def simulate_live_second(self):
        """Simulate one second of live hockey action"""
        if self.game_state['time_remaining'] <= 0:
            return self._handle_period_end()
        
        # Decrease time
        self.game_state['time_remaining'] -= 1
        self.current_shift_time += 1
        
        # Update player ice time
        self._update_ice_time()
        
        # Check for line changes
        if self.current_shift_time >= self.shift_length:
            self._handle_line_change()
        
        # Generate random events based on game situation
        event_chance = self._calculate_event_probability()
        
        if random.random() < event_chance:
            event = self._generate_live_event()
            if event:
                self._fire_event(event)
                self._fire_state_update()
        
        return True
    
    def _calculate_event_probability(self):
        """Calculate probability of an event happening this second"""
        base_probability = 0.15  # 15% chance per second
        
        # Adjust based on zone
        if self.game_state['zone'] == 'offensive':
            base_probability *= 1.8
        elif self.game_state['zone'] == 'defensive':
            base_probability *= 1.2
        
        # Adjust based on game situation
        if self.game_state['game_situation'] == 'powerplay':
            base_probability *= 1.5
        
        return min(base_probability, 0.3)  # Cap at 30%
    
    def _generate_live_event(self):
        """Generate a realistic live hockey event"""
        event_types = ['shot', 'pass', 'hit', 'faceoff', 'turnover', 'save', 'penalty', 'goal']
        weights = [0.25, 0.20, 0.15, 0.10, 0.12, 0.08, 0.05, 0.05]
        
        # Adjust weights based on zone
        if self.game_state['zone'] == 'offensive':
            weights[0] *= 2.5  # More shots in offensive zone
            weights[6] *= 1.5  # More goals in offensive zone
        
        event_type = random.choices(event_types, weights=weights)[0]
        
        # Get active players for the possessing team
        possessing_team = self.game_state['possession']
        active_players = [name for name, data in self.player_energy[possessing_team].items() if data['on_ice']]
        
        if not active_players:
            return None
        
        player = random.choice(active_players)
        
        # Generate event based on type
        event = {
            'type': event_type,
            'timestamp': 1200 - self.game_state['time_remaining'],
            'period': self.game_state['period'],
            'time': self._format_game_time(),
            'team': possessing_team,
            'player': player,
            'zone': self.game_state['zone'],
            'location': self._generate_location()
        }
        
        # Handle specific event logic
        if event_type == 'shot':
            return self._handle_shot_event(event)
        elif event_type == 'goal':
            return self._handle_goal_event(event)
        elif event_type == 'penalty':
            return self._handle_penalty_event(event)
        elif event_type == 'faceoff':
            return self._handle_faceoff_event(event)
        else:
            event['description'] = f"{player} - {event_type.title()}"
            return event
    
    def _handle_shot_event(self, event):
        """Handle a shot event with realistic outcomes"""
        player = event['player']
        team = event['team']
        
        # Update player stats
        self.player_energy[team][player]['shots'] += 1
        self.live_stats['shots'][team] += 1
        
        # Determine if it's a goal (realistic NHL shooting percentage ~10%)
        goal_chance = 0.10
        
        if self.game_state['zone'] == 'offensive':
            goal_chance *= 1.5
        
        if random.random() < goal_chance:
            # It's a goal!
            return self._convert_shot_to_goal(event)
        else:
            # It's a save or miss
            event['description'] = f"Shot by {player} - SAVED!"
            event['outcome'] = 'save'
            return event
    
    def _convert_shot_to_goal(self, event):
        """Convert a shot into a goal"""
        player = event['player']
        team = event['team']
        
        # Update score
        if team == self.home_team:
            self.game_state['home_score'] += 1
        else:
            self.game_state['away_score'] += 1
        
        # Update player stats
        self.player_energy[team][player]['goals'] += 1
        
        # Possibly add an assist
        active_players = [name for name, data in self.player_energy[team].items() 
                         if data['on_ice'] and name != player]
        if active_players and random.random() < 0.7:  # 70% chance of assist
            assist_player = random.choice(active_players)
            self.player_energy[team][assist_player]['assists'] += 1
            event['assist'] = assist_player
        
        event['type'] = 'goal'
        event['description'] = f"GOAL! {player} scores!"
        
        # Reset faceoff to center ice after goal
        self.game_state['faceoff_location'] = 'center_ice'
        self.game_state['zone'] = 'neutral'
        
        return event
    
    def _handle_penalty_event(self, event):
        """Handle a penalty event"""
        player = event['player']
        team = event['team']
        
        penalties = ['Tripping', 'Slashing', 'High-sticking', 'Interference', 'Roughing', 'Cross-checking']
        penalty_type = random.choice(penalties)
        
        self.player_energy[team][player]['penalties'] += 1
        self.live_stats['penalties'][team] += 1
        
        event['penalty_type'] = penalty_type
        event['description'] = f"PENALTY: {player} - {penalty_type} (2:00)"
        
        # Change game situation to powerplay/penalty kill
        if team == self.game_state['possession']:
            self.game_state['game_situation'] = 'penalty_kill'
        else:
            self.game_state['game_situation'] = 'powerplay'
        
        return event
    
    def _handle_faceoff_event(self, event):
        """Handle a faceoff event"""
        # Determine faceoff winner
        home_center = random.choice([name for name, data in self.player_energy[self.home_team].items() 
                                   if data['on_ice'] and data['position'] == 'C'])
        away_center = random.choice([name for name, data in self.player_energy[self.away_team].items() 
                                   if data['on_ice'] and data['position'] == 'C'])
        
        winner = random.choice([self.home_team, self.away_team])
        winner_player = home_center if winner == self.home_team else away_center
        
        self.game_state['possession'] = winner
        self.live_stats['faceoffs'][winner] += 1
        
        event['team'] = winner
        event['player'] = winner_player
        event['description'] = f"Faceoff won by {winner_player}"
        
        return event
    
    def _update_ice_time(self):
        """Update ice time for all players currently on ice"""
        for team in [self.home_team, self.away_team]:
            for player, data in self.player_energy[team].items():
                if data['on_ice']:
                    data['ice_time'] += 1
                    data['energy'] -= 0.1  # Fatigue over time
    
    def _handle_line_change(self):
        """Handle line changes when shift is over"""
        for team in [self.home_team, self.away_team]:
            # Bring tired players off ice
            on_ice_players = [name for name, data in self.player_energy[team].items() if data['on_ice']]
            off_ice_players = [name for name, data in self.player_energy[team].items() if not data['on_ice']]
            
            # Change some players (realistic line change)
            players_to_change = random.randint(1, 3)
            for _ in range(min(players_to_change, len(on_ice_players), len(off_ice_players))):
                # Player coming off
                off_player = random.choice(on_ice_players)
                self.player_energy[team][off_player]['on_ice'] = False
                on_ice_players.remove(off_player)
                
                # Player going on
                on_player = random.choice(off_ice_players)
                self.player_energy[team][on_player]['on_ice'] = True
                self.player_energy[team][on_player]['energy'] = min(100, self.player_energy[team][on_player]['energy'] + 20)
                off_ice_players.remove(on_player)
        
        # Reset shift timer
        self.current_shift_time = 0
        self.shift_length = random.randint(30, 90)
        
        # Fire line change event
        event = {
            'type': 'line_change',
            'timestamp': 1200 - self.game_state['time_remaining'],
            'period': self.game_state['period'],
            'time': self._format_game_time(),
            'description': 'Line change'
        }
        self._fire_event(event)
    
    def _handle_period_end(self):
        """Handle end of period"""
        if self.game_state['period'] < 3:
            self.game_state['period'] += 1
            self.game_state['time_remaining'] = 1200  # Reset to 20 minutes
            
            # Fire period end event
            event = {
                'type': 'period_end',
                'timestamp': 1200,
                'period': self.game_state['period'] - 1,
                'time': '00:00',
                'description': f"End of Period {self.game_state['period'] - 1}"
            }
            self._fire_event(event)
            
            return True
        else:
            # Game over
            event = {
                'type': 'game_end',
                'timestamp': 1200,
                'period': 3,
                'time': '00:00',
                'description': 'Game Over',
                'final_score': f"{self.home_team} {self.game_state['home_score']} - {self.away_team} {self.game_state['away_score']}"
            }
            self._fire_event(event)
            return False
    
    def _format_game_time(self):
        """Format remaining time as MM:SS"""
        minutes = self.game_state['time_remaining'] // 60
        seconds = self.game_state['time_remaining'] % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def _generate_location(self):
        """Generate a random location on the ice"""
        return {
            'x': random.randint(10, 90),
            'y': random.randint(10, 40)
        }
    
    def get_current_stats(self):
        """Get current game statistics"""
        home_players = []
        away_players = []
        
        for team, players in self.player_energy.items():
            player_list = home_players if team == self.home_team else away_players
            
            for name, data in players.items():
                player_list.append({
                    'name': name,
                    'jersey': data['jersey'],
                    'position': data['position'],
                    'goals': data['goals'],
                    'assists': data['assists'],
                    'points': data['goals'] + data['assists'],
                    'shots': data['shots'],
                    'penalties': data['penalties'],
                    'toi': f"{data['ice_time']//60:02d}:{data['ice_time']%60:02d}",
                    'on_ice': data['on_ice']
                })
        
        return {
            'home_team': self.home_team,
            'away_team': self.away_team,
            'home_score': self.game_state['home_score'],
            'away_score': self.game_state['away_score'],
            'period': self.game_state['period'],
            'time': self._format_game_time(),
            'home_players': sorted(home_players, key=lambda x: x['points'], reverse=True),
            'away_players': sorted(away_players, key=lambda x: x['points'], reverse=True),
            'team_stats': self.live_stats,
            'events': self.live_events.copy()
        }

class AdvancedGameSim:
    """Simulates a hockey game and produces a structured event log for visualization."""
    def __init__(self, home_team, away_team):
        self.home_team = home_team
        self.away_team = away_team
        # FM team-talk boost: team_name -> multiplier (default 1.0)
        self.team_boost = {home_team.team_name: 1.0, away_team.team_name: 1.0}

        # Initialize performance cache
        from performance_optimizations import get_global_cache
        self.cache = get_global_cache()
        
        # Initialize coordinate-based simulation engine
        from coordinate_simulation import CoordinateSimEngine
        self.coordinate_engine = CoordinateSimEngine()

        # Defensive: always ensure lineup dict has required keys
        def ensure_lineup(team):
            lineup = getattr(team, 'lineup', None)
            if not lineup or not isinstance(lineup, dict):
                return best_lines(team)
            # Defensive: fill missing keys with best_lines
            keys = ['Forwards', 'Defense', 'Goalies']
            missing = [k for k in keys if k not in lineup]
            if missing:
                base = best_lines(team)
                for k in missing:
                    lineup[k] = base[k]
            return lineup

        self.lineups = {
            home_team.team_name: ensure_lineup(home_team),
            away_team.team_name: ensure_lineup(away_team)
        }
        self.score = {home_team.team_name: 0, away_team.team_name: 0}
        self.events = []
        self.stats = {
            home_team.team_name: {p.id: {'goals': 0, 'assists': 0, 'shots': 0, 'toi': 0, 'fatigue': 0} for p in home_team.roster},
            away_team.team_name: {p.id: {'goals': 0, 'assists': 0, 'shots': 0, 'toi': 0, 'fatigue': 0} for p in away_team.roster}
        }
        # Ensure stats dict includes all stat keys for each player
        for team in [home_team, away_team]:
            for p in team.roster:
                self.stats[team.team_name][p.id] = {
                    'goals': 0, 'assists': 0, 'shots': 0, 'saves': 0, 'penalties': 0, 'toi': 0, 'fatigue': 0
                }
        self.puck_pos = 'neutral'
        self.time = 0
        self.period = 1
        self.on_ice = {
            home_team.team_name: {'Forwards': [], 'Defense': [], 'Goalie': None},
            away_team.team_name: {'Forwards': [], 'Defense': [], 'Goalie': None}
        }
        self.pp_team = None
        self.pk_team = None
        self.pp_end_time = None  # When the current power play expires (penalty clock)
        self.puck_x = 100  # X position of puck on ice (center ice)
        self.puck_y = 42.5  # Y position of puck on ice (center)
        self.state_history = []  # List to store state after each shift/event
        self.event_log = []  # Structured event log for visualization
        
        # Initialize player positions using coordinate engine
        home_players = [p for p in home_team.roster]
        away_players = [p for p in away_team.roster] 
        self.coordinate_engine.initialize_player_positions(home_players, away_players)

    def set_team_talk_boost(self, team_name: str, multiplier: float):
        """FM-style: apply a team-talk/morale multiplier to a team's scoring."""
        self.team_boost[team_name] = max(0.9, min(1.1, multiplier))

    def _select_lines(self, team_name, fatigue=False):
        lineup = self.lineups[team_name]
        fw_lines = lineup['Forwards']
        df_pairs = lineup['Defense']
        goalies = lineup['Goalies']
        fw_idx = min(range(len(fw_lines)), key=lambda i: sum(self.stats[team_name].get(p.id, {}).get('fatigue', 0) for p in fw_lines[i] if p))
        df_idx = min(range(len(df_pairs)), key=lambda i: sum(self.stats[team_name].get(p.id, {}).get('fatigue', 0) for p in df_pairs[i] if p))
        goalie = goalies[0] if goalies and goalies[0] else None
        return fw_lines[fw_idx], df_pairs[df_idx], goalie

    def _advance_time(self, seconds):
        self.time += seconds
        if self.time >= 1200 * self.period:
            self.period += 1
            if self.period > 3 and self.score[self.home_team.team_name] == self.score[self.away_team.team_name]:
                self.period = 4
                self.time = 3600
            elif self.period > 4:
                self.time = 9999

    def _record_state(self):
        # Collect positions of all on-ice players and puck
        state = {
            'home': [
                {'id': p.id, 'x': p.x, 'y': p.y}
                for p in self.on_ice[self.home_team.team_name]['Forwards'] + self.on_ice[self.home_team.team_name]['Defense']
                if p
            ],
            'away': [
                {'id': p.id, 'x': p.x, 'y': p.y}
                for p in self.on_ice[self.away_team.team_name]['Forwards'] + self.on_ice[self.away_team.team_name]['Defense']
                if p
            ],
            'home_goalie': (
                {'id': self.on_ice[self.home_team.team_name]['Goalie'].id,
                 'x': self.on_ice[self.home_team.team_name]['Goalie'].x,
                 'y': self.on_ice[self.home_team.team_name]['Goalie'].y}
                if self.on_ice[self.home_team.team_name]['Goalie'] else None
            ),
            'away_goalie': (
                {'id': self.on_ice[self.away_team.team_name]['Goalie'].id,
                 'x': self.on_ice[self.away_team.team_name]['Goalie'].x,
                 'y': self.on_ice[self.away_team.team_name]['Goalie'].y}
                if self.on_ice[self.away_team.team_name]['Goalie'] else None
            ),
            'puck': {'x': self.puck_x, 'y': self.puck_y},
            'time': self.time,
            'period': self.period
        }
        self.state_history.append(state)

    def _simulate_shift(self):
        # Enhanced shift simulation for realistic hockey flow
        for team_name in [self.home_team.team_name, self.away_team.team_name]:
            fw, df, g = self._select_lines(team_name)
            self.on_ice[team_name]['Forwards'] = fw
            self.on_ice[team_name]['Defense'] = df
            self.on_ice[team_name]['Goalie'] = g
            for idx, p in enumerate(fw + df):
                if p:
                    # Defensive: ensure stat keys exist
                    if p.id not in self.stats[team_name]:
                        self.stats[team_name][p.id] = {'goals':0,'assists':0,'shots':0,'saves':0,'penalties':0,'toi':0,'fatigue':0}
                    self.stats[team_name][p.id]['toi'] += 45
                    self.stats[team_name][p.id]['fatigue'] += 1
            if g:
                if g.id not in self.stats[team_name]:
                    self.stats[team_name][g.id] = {'goals':0,'assists':0,'shots':0,'saves':0,'penalties':0,'toi':0,'fatigue':0}
                self.stats[team_name][g.id]['toi'] += 45
        
        # Enhanced player movement with coordinate-based positioning
        for team_name in [self.home_team.team_name, self.away_team.team_name]:
            is_home_team = team_name == self.home_team.team_name
            
            for p in self.on_ice[team_name]['Forwards'] + self.on_ice[team_name]['Defense']:
                if p:
                    # Get current position from coordinate engine
                    current_pos = self.coordinate_engine.player_positions.get(p.id, (100, 42.5))
                    
                    # Determine target position based on game situation and player role
                    if hasattr(p, 'primary_position') and p.primary_position:
                        if 'WING' in str(p.primary_position):
                            # Wingers move along the boards and cycle
                            if is_home_team:
                                target_x = random.randint(120, 180)  # Attacking zone
                                target_y = random.choice([15, 70]) + random.randint(-8, 8)  # Wing positions
                            else:
                                target_x = random.randint(20, 80)   # Defending/neutral zone
                                target_y = random.choice([15, 70]) + random.randint(-8, 8)
                        elif 'CENTER' in str(p.primary_position):
                            # Centers control the middle of the ice
                            if is_home_team:
                                target_x = random.randint(110, 170)  # Attacking area
                            else:
                                target_x = random.randint(30, 90)   # Defensive area
                            target_y = 42.5 + random.randint(-15, 15)  # Central corridor
                        else:  # Defense
                            # Defensemen stay back unless rushing
                            rush_chance = 0.15 if random.random() < 0.15 else 0
                            if is_home_team:
                                if rush_chance:
                                    target_x = random.randint(140, 160)  # Offensive rush
                                else:
                                    target_x = random.randint(80, 120)   # Stay back
                            else:
                                if rush_chance:
                                    target_x = random.randint(40, 60)    # Offensive rush  
                                else:
                                    target_x = random.randint(80, 120)   # Stay back
                            target_y = 42.5 + random.randint(-20, 20)
                    else:
                        # Fallback positioning
                        target_x = current_pos[0] + random.randint(-15, 15)
                        target_y = current_pos[1] + random.randint(-8, 8)
                    
                    # Ensure target is within rink bounds
                    target_x = max(5, min(195, target_x))
                    target_y = max(5, min(80, target_y))
                    target_pos = (target_x, target_y)
                    
                    # Generate realistic movement events
                    movement_events = self.coordinate_engine.simulate_player_movement(
                        p.id, target_pos, "skate"
                    )
                    
                    # Add movement events to event log
                    for event in movement_events:
                        event['timestamp'] = self.time + event['timestamp']
                        self.event_log.append(event)
                    
                    # Update legacy position tracking for compatibility
                    p.x, p.y = target_pos
        
        # Generate realistic events per shift (reduced from 6-12 to 2-4 for performance)
        num_events = random.randint(2, 4)  # Reduced event count for better performance
        for _ in range(num_events):
            self._simulate_event()
            # Slightly larger time increments between events
            self._advance_time(random.randint(8, 15))  # 8-15 seconds between events
            
        # Final shift time advancement (remaining time)
        remaining_time = 45 - (num_events * 10)  # Approximate remaining time
        if remaining_time > 0:
            self._advance_time(remaining_time)
        self._record_state()

    def _simulate_event(self):
        puck_team_name = self.home_team.team_name if random.random() < 0.5 else self.away_team.team_name
        opp_team_name = self.away_team.team_name if puck_team_name == self.home_team.team_name else self.home_team.team_name
        if self.pp_team:
            puck_team_name = self.pp_team
            opp_team_name = self.pk_team
        shooters = [p for p in self.on_ice[puck_team_name]['Forwards'] + self.on_ice[puck_team_name]['Defense'] if p]
        if not shooters:
            return
        shooter = random.choices(shooters, weights=[p.overall_rating() for p in shooters], k=1)[0]
        goalie = self.on_ice[opp_team_name]['Goalie']

        # --- Enhanced Fatigue System ---
        fatigue_factor = self._calculate_fatigue_factor(shooter, puck_team_name)
        
        # --- Pressure Situations ---
        pressure_modifier = self._calculate_pressure_modifier(shooter)
        
        # --- Position and Formation Factors ---
        position_factor = self._calculate_position_factor(shooter, puck_team_name)
        
        # --- Determine Event Type based on player attributes ---
        event_type = self._determine_event_type(shooter, shooters, fatigue_factor)
        
        if event_type == "SHOT":
            self._resolve_shot_event(shooter, goalie, puck_team_name, opp_team_name, fatigue_factor, pressure_modifier, position_factor, shooters)
        elif event_type == "PASS":
            self._resolve_pass_event(shooter, shooters, puck_team_name, opp_team_name, fatigue_factor)
        elif event_type == "DEKE":
            self._resolve_deke_event(shooter, puck_team_name, fatigue_factor)
        elif event_type == "PUCK_BATTLE":
            self._resolve_puck_battle(shooters, puck_team_name, fatigue_factor)
        elif event_type == "SCREEN":
            self._resolve_screen_event(shooter, shooters, puck_team_name)
        elif event_type == "DEFLECTION":
            self._resolve_deflection_event(shooter, shooters, goalie, puck_team_name, opp_team_name)
            
        # --- Random penalty check with improved logic ---
        self._check_for_penalty(shooters, puck_team_name, opp_team_name, fatigue_factor)
        
        # --- End power play when the 2-minute penalty clock expires ---
        if self.pp_team and self.pp_end_time and self.time >= self.pp_end_time:
            self.pp_team = None
            self.pk_team = None
            self.pp_end_time = None
        self._record_state()
        
        # Don't advance time here - it's managed in _simulate_shift
        self._record_state()

    def _resolve_pass_event(self, shooter, shooters, puck_team_name, opp_team_name, fatigue_factor):
        """Handle pass events with cached player skills for better performance"""
        if len(shooters) <= 1:
            return
            
        receiver = random.choice([p for p in shooters if p != shooter])
        
        # Use cached skills instead of multiple getattr() calls
        shooter_cache = self.cache.get_player_cache(shooter)
        pass_skill = shooter_cache.passing_skill * fatigue_factor
        
        # Defensive pressure using cached skills
        defenders = [p for p in self.on_ice[opp_team_name]['Defense'] if p]
        if defenders:
            defender = random.choice(defenders)
            defender_cache = self.cache.get_player_cache(defender)
            defense_skill = defender_cache.defensive_skill
        else:
            defense_skill = 10.0
        
        pass_success = pass_skill > defense_skill or random.random() < 0.75
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': random.uniform(0.7, 1.2),
            'type': 'PASS',
            'details': {
                'passer_id': shooter.id,
                'passer_name': shooter.full_name,
                'receiver_id': receiver.id,
                'receiver_name': receiver.full_name,
                'success': pass_success,
                'team': puck_team_name
            }
        })
        
        if pass_success:
            self.puck_x, self.puck_y = receiver.x, receiver.y
        else:
            if defender:
                self.puck_x, self.puck_y = defender.x, defender.y

    def _resolve_deke_event(self, shooter, puck_team_name, fatigue_factor):
        """Handle deke/stickhandling events with cached skills"""
        # Use cached skills for better performance
        shooter_cache = self.cache.get_player_cache(shooter)
        deke_skill = shooter_cache.deking_skill * fatigue_factor
        
        success = deke_skill > 12 and random.random() < 0.6
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': random.uniform(1.0, 2.0),
            'type': 'DEKE',
            'details': {
                'player_id': shooter.id,
                'player_name': shooter.full_name,
                'success': success,
                'team': puck_team_name
            }
        })

    def _resolve_puck_battle(self, shooters, puck_team_name, fatigue_factor):
        """Handle puck battle events"""
        if len(shooters) < 2:
            return
            
        battlers = random.sample(shooters, 2)
        winner = random.choice(battlers)
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': random.uniform(2.0, 4.0),
            'type': 'PUCK_BATTLE',
            'details': {
                'winner_id': winner.id,
                'winner_name': winner.full_name,
                'team': puck_team_name
            }
        })

    def _resolve_screen_event(self, shooter, shooters, puck_team_name):
        """Handle screening events in front of net"""
        screener = random.choice([p for p in shooters if p != shooter]) if len(shooters) > 1 else shooter
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': random.uniform(1.5, 3.0),
            'type': 'SCREEN',
            'details': {
                'screener_id': screener.id,
                'screener_name': screener.full_name,
                'team': puck_team_name
            }
        })

    def _resolve_deflection_event(self, shooter, shooters, goalie, puck_team_name, opp_team_name):
        """Handle puck deflection events"""
        deflector = random.choice([p for p in shooters if p != shooter]) if len(shooters) > 1 else shooter
        
        deflection_skill = getattr(deflector, 'deflections', 10)
        success = deflection_skill > 12 and random.random() < 0.3
        
        if success and random.random() < 0.2:  # 20% chance deflection becomes goal
            self.score[puck_team_name] += 1
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name, 'player': deflector, 'event': 'Deflection Goal'})
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': random.uniform(0.8, 1.5),
            'type': 'DEFLECTION',
            'details': {
                'deflector_id': deflector.id,
                'deflector_name': deflector.full_name,
                'success': success,
                'team': puck_team_name
            }
        })

    def _calculate_fatigue_factor(self, player, team_name):
        """Calculate comprehensive fatigue factor"""
        player_fatigue = self.stats[team_name][player.id].get('fatigue', 0)
        endurance = getattr(player, 'endurance', 10)
        stamina = getattr(player, 'stamina', 10)
        durability = getattr(player, 'durability', 10)
        
        # Better players with high endurance/stamina maintain performance longer
        fatigue_resistance = (endurance + stamina + durability) / 3
        fatigue_factor = 1.0 - min(0.6, player_fatigue / max(1, fatigue_resistance))
        return max(0.4, fatigue_factor)  # Never go below 40% performance
    
    def _calculate_pressure_modifier(self, player):
        """Calculate how player performs under pressure"""
        pressure_rating = getattr(player, 'pressure_player', 10)
        composure = getattr(player, 'composure', 10)
        confidence = getattr(player, 'confidence', 10)
        determination = getattr(player, 'determination', 10)
        
        # Close games and late periods increase pressure
        score_diff = abs(self.score[self.home_team.team_name] - self.score[self.away_team.team_name])
        is_late_game = self.period >= 3 and self.time > 3000
        is_close_game = score_diff <= 1
        
        pressure_level = 1.0
        if is_late_game and is_close_game:
            pressure_level = 1.3
        elif is_close_game:
            pressure_level = 1.1
            
        pressure_skill = (pressure_rating + composure + confidence + determination) / 4
        pressure_modifier = 1.0 + (pressure_skill - 10) * 0.02 * pressure_level
        return max(0.7, min(1.4, pressure_modifier))
    
    def _calculate_position_factor(self, player, team_name):
        """Calculate positional advantage/disadvantage"""
        off_the_puck = getattr(player, 'off_the_puck', 10)
        anticipation = getattr(player, 'anticipation', 10)
        hockey_iq = getattr(player, 'hockey_iq', 10)
        
        # Players with better off-the-puck movement get better opportunities
        position_skill = (off_the_puck + anticipation + hockey_iq) / 3
        return 1.0 + (position_skill - 10) * 0.03
    
    def _determine_event_type(self, player, shooters, fatigue_factor):
        """Determine what type of event occurs based on player attributes"""
        creativity = getattr(player, 'creativity', 10)
        decision_making = getattr(player, 'decision_making', 10)
        stickhandling = getattr(player, 'stickhandling', 10)
        passing = getattr(player, 'passing', 10)
        
        # Base probabilities - tuned for realistic NHL game flow
        # Target: ~70-75 shot attempts from ~225 events per game (~32% shots)
        # Hockey is mostly passing and puck battles, not constant shooting
        shot_prob = 0.32
        pass_prob = 0.40 if len(shooters) > 1 else 0.0
        deke_prob = 0.08
        battle_prob = 0.12
        screen_prob = 0.05
        deflection_prob = 0.03
        
        # Modify based on attributes
        if creativity > 15:
            deke_prob *= 1.5
            pass_prob *= 1.2
        if decision_making > 15:
            pass_prob *= 1.3
        if stickhandling > 15:
            deke_prob *= 1.4
        if passing > 15:
            pass_prob *= 1.3
            
        # Fatigue reduces creative plays
        deke_prob *= fatigue_factor
        pass_prob *= fatigue_factor
        
        # Random selection based on probabilities
        rand = random.random()
        if rand < shot_prob:
            return "SHOT"
        elif rand < shot_prob + pass_prob:
            return "PASS"
        elif rand < shot_prob + pass_prob + deke_prob:
            return "DEKE"
        elif rand < shot_prob + pass_prob + deke_prob + battle_prob:
            return "PUCK_BATTLE"
        elif rand < shot_prob + pass_prob + deke_prob + battle_prob + screen_prob:
            return "SCREEN"
        else:
            return "DEFLECTION"

    def run(self):
        # NHL rules: 5-minute 3v3 sudden-death OT, then shootout
        overtime_limit = 300  # 5 minutes OT (NHL regular season)
        shootout_rounds = 3  # Initial shootout rounds, then sudden death
        
        # Regulation: 60 minutes
        while self.time < 3600:
            self._simulate_shift()
        
        # Overtime: sudden death - first goal wins
        if self.score[self.home_team.team_name] == self.score[self.away_team.team_name]:
            ot_start = self.time
            ot_home_start = self.score[self.home_team.team_name]
            ot_away_start = self.score[self.away_team.team_name]
            self.period = 4
            while (self.time < ot_start + overtime_limit and 
                   self.score[self.home_team.team_name] == self.score[self.away_team.team_name]):
                self._simulate_shift()
                # Sudden death: stop immediately on goal
                # (The loop condition checks the tie each iteration)
            
            # Enforce true sudden death: max 1 goal per team in OT
            # (A shift might generate multiple goals before the loop checks)
            home_ot_goals = self.score[self.home_team.team_name] - ot_home_start
            away_ot_goals = self.score[self.away_team.team_name] - ot_away_start
            if home_ot_goals > 1:
                self.score[self.home_team.team_name] = ot_home_start + 1
            if away_ot_goals > 1:
                self.score[self.away_team.team_name] = ot_away_start + 1
        # If still tied after OT, do shootout

        # Defensive: get home/away goalies safely
        def get_goalie(team, lineup):
            goalies = lineup.get('Goalies', [])
            if goalies and goalies[0]:
                return goalies[0]
            # Fallback: pick a random goalie from roster
            candidates = [p for p in team.roster if getattr(p, 'primary_position', None) and p.primary_position.name == "G"]
            return candidates[0] if candidates else None

        home_goalie = get_goalie(self.home_team, self.lineups[self.home_team.team_name])
        away_goalie = get_goalie(self.away_team, self.lineups[self.away_team.team_name])

        if self.score[self.home_team.team_name] == self.score[self.away_team.team_name]:
            # Shootout: 3 rounds, then sudden-death rounds until winner
            # NHL rule: shootout winner is credited with +1 goal
            home_goals = 0
            away_goals = 0
            
            # Get shooters (cycle through forwards if needed for sudden death)
            home_forwards = [p for line in self.lineups[self.home_team.team_name].get('Forwards', []) for p in line if p]
            away_forwards = [p for line in self.lineups[self.away_team.team_name].get('Forwards', []) for p in line if p]
            
            def shootout_attempt(shooter, goalie, team_name):
                """Single shootout attempt. Returns True if goal scored."""
                shot_skill = (
                    getattr(shooter, 'wristshot', 10) * 0.4 +
                    getattr(shooter, 'deking', 10) * 0.4 +
                    getattr(shooter, 'composure', 10) * 0.2
                )
                goalie_skill = (
                    getattr(goalie, 'reflexes', 10) * 0.4 +
                    getattr(goalie, 'positioning', 10) * 0.3 +
                    getattr(goalie, 'breakaway_skill', 10) * 0.3
                ) if goalie else 10
                
                success_chance = 0.33 + (shot_skill - goalie_skill) * 0.015
                if random.random() < min(0.7, max(0.1, success_chance)):
                    self.events.append({'time': self.time, 'period': 5, 'team': team_name, 'player': shooter, 'event': 'Shootout Goal'})
                    return True
                return False
            
            # Initial 3 rounds
            round_num = 0
            for i in range(shootout_rounds):
                round_num += 1
                if i < len(home_forwards):
                    if shootout_attempt(home_forwards[i], away_goalie, self.home_team.team_name):
                        home_goals += 1
                if i < len(away_forwards):
                    if shootout_attempt(away_forwards[i], home_goalie, self.away_team.team_name):
                        away_goals += 1
            
            # Sudden death rounds if tied (NHL rule)
            sudden_death_round = 0
            while home_goals == away_goals and sudden_death_round < 20:  # Safety cap
                sudden_death_round += 1
                # Cycle through shooters
                home_shooter = home_forwards[(shootout_rounds + sudden_death_round - 1) % max(1, len(home_forwards))] if home_forwards else None
                away_shooter = away_forwards[(shootout_rounds + sudden_death_round - 1) % max(1, len(away_forwards))] if away_forwards else None
                
                home_scored = shootout_attempt(home_shooter, away_goalie, self.home_team.team_name) if home_shooter else False
                away_scored = shootout_attempt(away_shooter, home_goalie, self.away_team.team_name) if away_shooter else False
                
                if home_scored:
                    home_goals += 1
                if away_scored:
                    away_goals += 1
                
                # In sudden death, if one scores and the other doesn't, it's over
                # (both scored or both missed = continue)
                if home_scored != away_scored:
                    break
            
            # Determine winner (no more auto-win for away on tie - sudden death ensures a winner)
            if home_goals > away_goals:
                winner, loser = self.home_team, self.away_team
                # NHL: shootout winner credited with +1 goal
                self.score[self.home_team.team_name] += 1
            elif away_goals > home_goals:
                winner, loser = self.away_team, self.home_team
                self.score[self.away_team.team_name] += 1
            else:
                # Extremely rare: still tied after 20 sudden death rounds
                # Home team wins coin flip (better than auto-away-win)
                winner, loser = self.home_team, self.away_team
                self.score[self.home_team.team_name] += 1
            
            scores = (self.score[self.home_team.team_name], self.score[self.away_team.team_name])
            notable_events = [e for e in self.events if e['event'] == 'Goal' or e['event'] == 'Shootout Goal']
            return winner, loser, scores, self.events, notable_events
        if self.score[self.home_team.team_name] > self.score[self.away_team.team_name]:
            winner, loser = self.home_team, self.away_team
        else:
            winner, loser = self.away_team, self.home_team
        scores = (self.score[self.home_team.team_name], self.score[self.away_team.team_name])
        notable_events = [e for e in self.events if e['event'] == 'Goal']
        
        # Gameplay injuries: small chance per game (NHL: ~1 injury per 3-4 games)
        self._process_gameplay_injuries()
        
        return winner, loser, scores, self.events, notable_events

    def _process_gameplay_injuries(self):
        """Process potential injuries from gameplay.
        
        NHL averages roughly 1 man-game lost to injury per 3-4 games.
        Injury-prone players (high injury_proneness) are more likely to get hurt.
        """
        import random
        
        # ~13% chance per team per game -> ~25% chance of at least one injury per game
        # Pick an injury victim from either team's healthy skaters
        victims = []
        for team in [self.home_team, self.away_team]:
            if random.random() > 0.13:
                continue
            v = roll_game_injury(team)
            if v is not None:
                victims.append((team, v))

        for team, injured in victims:
            # Log the injury event
            self.events.append({
                'time': self.time,
                'period': self.period,
                'team': team.team_name,
                'player': injured,
                'event': 'Injury',
                'details': f'{injured.injury_type} ({injured.games_remaining_injured} games)'
            })

            print(f"🏥 Injury: {injured.first_name} {injured.last_name} - {injured.injury_type} ({injured.games_remaining_injured} games)")

    def _resolve_shot_event(self, shooter, goalie, puck_team_name, opp_team_name, fatigue_factor, pressure_modifier, position_factor, shooters):
        """Enhanced shot resolution using multiple attributes"""
        # Determine shot type based on position and situation
        wristshot_val = getattr(shooter, 'wristshot', 10)
        slapshot_val = getattr(shooter, 'slapshot', 10)
        one_timer_val = getattr(shooter, 'one_timer', 10)
        backhand_val = getattr(shooter, 'backhand', 10)
        
        # Choose shot type
        if self.pp_team and random.random() < 0.3:  # More one-timers on PP
            shooting_base = one_timer_val
            shot_type = "one-timer"
        elif shooter.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            if random.random() < 0.7:
                shooting_base = wristshot_val
                shot_type = "wrist shot"
            else:
                shooting_base = backhand_val
                shot_type = "backhand"
        elif shooter.primary_position == PlayerPosition.CENTER:
            shooting_base = wristshot_val * 0.6 + one_timer_val * 0.4
            shot_type = "wrist shot"
        else:  # Defense
            shooting_base = slapshot_val
            shot_type = "slap shot"
            
        # Shooter skill on 1-20 scale (no multiplicative inflation)
        # Fatigue reduces effectiveness; pressure/position are situational, not skill multipliers
        shooter_skill = (
            shooting_base * 0.3 +
            getattr(shooter, 'shooting_accuracy', 10) * 0.25 +
            getattr(shooter, 'off_the_puck', 10) * 0.2 +
            getattr(shooter, 'composure', 10) * 0.15 +
            getattr(shooter, 'vision', 10) * 0.1
        ) * fatigue_factor

        # Enhanced goalie attributes
        goalie_skill = self._calculate_goalie_save_skill(goalie, shot_type) if goalie else 8
        
        # NHL-realistic shooting percentage: ~9% base
        # Each point of skill difference shifts scoring chance by ~0.8%
        # (Elite 18 vs weak 8 = +8% → ~17% is the realistic ceiling for great chances)
        skill_diff = shooter_skill - goalie_skill
        shot_chance = 0.09 + (skill_diff * 0.008)
        
        # Team tactics affect shot quality
        # Get the shooting team's tactics
        shooting_team = self.home_team if puck_team_name == self.home_team.team_name else self.away_team
        defending_team = self.away_team if puck_team_name == self.home_team.team_name else self.home_team
        
        if self.pp_team:
            # Power play tactics
            pp_tactic = getattr(shooting_team, 'tactic_power_play', 'Offensive')
            if pp_tactic == 'Very Offensive':
                shot_chance += 0.035  # More aggressive, higher risk/reward
            elif pp_tactic == 'Offensive':
                shot_chance += 0.025
            elif pp_tactic == 'Conservative':
                shot_chance += 0.005  # Patient, prevent shorthanded goals against
            else:  # Balanced
                shot_chance += 0.015
        elif self.pk_team == puck_team_name:
            # Shorthanded: PK tactics affect shorthanded chances
            pk_tactic = getattr(shooting_team, 'tactic_penalty_kill', 'Defensive')
            if pk_tactic == 'Aggressive':
                shot_chance += 0.01  # More shorthanded rushes
            elif pk_tactic == 'Balanced':
                shot_chance += 0.005
            elif pk_tactic == 'Very Defensive':
                shot_chance -= 0.005  # Pure survival mode
            # Defensive: focus on clearing, fewer shots
        else:
            # Even strength tactics
            es_tactic = getattr(shooting_team, 'tactic_even_strength', 'Balanced')
            if es_tactic == 'Very Offensive':
                shot_chance += 0.02  # All-out attack
            elif es_tactic == 'Offensive':
                shot_chance += 0.01  # More shots, higher quality chances
            elif es_tactic == 'Defensive':
                shot_chance -= 0.008  # Fewer shots, focus on defense
            elif es_tactic == 'Very Defensive':
                shot_chance -= 0.014  # Trap hockey
            
            # Defending team's tactics affect shot quality against
            def_tactic = getattr(defending_team, 'tactic_even_strength', 'Balanced')
            if def_tactic == 'Very Defensive':
                shot_chance -= 0.012  # Maximum structure
            elif def_tactic == 'Defensive':
                shot_chance -= 0.008  # Tight defense reduces quality
            elif def_tactic == 'Offensive':
                shot_chance += 0.005  # Aggressive D leaves gaps
            elif def_tactic == 'Very Offensive':
                shot_chance += 0.008  # Pinching D, odd-man rushes both ways
        
        # Home-ice advantage: small boost for home team (NHL home win ~55%)
        # +0.5% absolute shooting chance ≈ the observed home edge
        if puck_team_name == self.home_team.team_name:
            shot_chance += 0.005
        
        # Clamp to realistic NHL range (5% - 15%)
        shot_chance = max(0.05, min(0.15, shot_chance))

        # FM team-talk / morale boost (set via set_team_talk_boost)
        shot_chance *= self.team_boost.get(puck_team_name, 1.0)
        shot_chance = max(0.04, min(0.16, shot_chance))

        # Shot blocking check
        shot_blocked = self._check_shot_blocking(opp_team_name, fatigue_factor)
        
        # Position shooter and determine result
        shot_start = (shooter.x, shooter.y)
        duration = random.uniform(1.0, 1.7)
        
        if shot_blocked:
            shot_result = 'BLOCKED'
        elif random.random() < shot_chance:  # Direct shot chance calculation
            shot_result = 'GOAL'
            self.score[puck_team_name] += 1
            # Update stats
            self.stats[puck_team_name][shooter.id]['goals'] = self.stats[puck_team_name][shooter.id].get('goals', 0) + 1
            # Add goal event
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name, 'player': shooter, 'event': 'Goal'})
            # PP ends when the PP team scores (NHL rule)
            if self.pp_team == puck_team_name:
                self.pp_team = None
                self.pk_team = None
                self.pp_end_time = None
        elif goalie and random.random() < 0.8:
            shot_result = 'SAVE'
            if goalie:
                self.stats[opp_team_name][goalie.id]['saves'] = self.stats[opp_team_name][goalie.id].get('saves', 0) + 1
            # Add shot/save event
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name, 'player': shooter, 'event': 'Shot'})
        else:
            shot_result = 'MISS'
            # Add missed shot event
            self.events.append({'time': self.time, 'period': self.period, 'team': puck_team_name, 'player': shooter, 'event': 'Shot'})
            
        # Update shot stats
        self.stats[puck_team_name][shooter.id]['shots'] = self.stats[puck_team_name][shooter.id].get('shots', 0) + 1
        
        # Log event
        self.event_log.append({
            'timestamp': self.time,
            'duration': duration,
            'type': 'SHOT',
            'details': {
                'shooter_id': shooter.id,
                'shot_type': shot_type,
                'puck_start_pos': shot_start,
                'result': shot_result
            }
        })
        
        # Add stoppage if needed
        if shot_result in ['GOAL', 'SAVE']:
            self.event_log.append({
                'timestamp': self.time + duration,
                'duration': 2.0 if shot_result == 'GOAL' else 1.5,
                'type': 'STOPPAGE',
                'details': {
                    'reason': 'Goal Scored' if shot_result == 'GOAL' else 'Save',
                    'faceoff_pos': (50, 25)
                }
            })
    
    def _calculate_goalie_save_skill(self, goalie, shot_type, danger_level=None, distance=None):
        """Enhanced goalie skill calculation with coordinate-based danger awareness"""
        if not goalie:
            return 8.0
            
        base_skill = (
            getattr(goalie, 'goaltending', 10) * 0.4 +
            getattr(goalie, 'reflexes', 10) * 0.25 +
            getattr(goalie, 'positioning', 10) * 0.2 +
            getattr(goalie, 'rebound_control', 10) * 0.1 +
            getattr(goalie, 'composure', 10) * 0.05
        )
        
        # Danger level adjustments for coordinate-based analysis
        if danger_level:
            danger_penalties = {
                'very_high': -4,  # Very hard saves in high danger
                'high': -2,       # Moderately difficult
                'medium': 0,      # Neutral
                'low': 2          # Easier saves from distance/bad angles
            }
            base_skill += danger_penalties.get(danger_level, 0)
        
        # Shot type specific adjustments
        shot_type_modifiers = {
            'one-timer': -3,      # Quick shots harder to stop
            'wrist shot': 0,      # Standard
            'slap shot': 1,       # Easier to see coming
            'backhand': -1,       # Deceptive
            'tip': -4,            # Very difficult
            'deflection': -3      # Hard to react to
        }
        base_skill += shot_type_modifiers.get(shot_type, 0)
        
        # Distance factor for coordinate analysis
        if distance:
            if distance < 15:
                base_skill -= 2  # Close shots harder
            elif distance > 35:
                base_skill += 1  # Long shots easier
        
        # Legacy adjustments for compatibility
        if shot_type == "slap shot":
            base_skill += getattr(goalie, 'glove_hand', 10) * 0.05
        elif shot_type == "one-timer":
            base_skill += getattr(goalie, 'reflexes', 10) * 0.05
        elif shot_type == "backhand":
            base_skill += getattr(goalie, 'positioning', 10) * 0.05
        elif shot_type == "breakaway":
            base_skill += getattr(goalie, 'breakaway_skill', 10) * 0.1
            
        return max(5, base_skill)
    
    def _check_shot_blocking_coordinate(self, opp_team_name, shot_details, fatigue_factor):
        """Enhanced shot blocking with coordinate-based positioning"""
        defenders = [p for p in self.on_ice[opp_team_name]['Defense'] if p]
        if not defenders:
            return False
            
        shot_pos = shot_details['puck_start_pos']
        danger_level = shot_details['danger_level']
        
        # Higher chance of blocks in high danger areas (defenders collapse)
        base_block_chance = {
            'very_high': 0.25,  # Defenders pack the crease
            'high': 0.15,       # Active shot blocking in slot
            'medium': 0.08,     # Some blocking from point
            'low': 0.03         # Minimal blocking from distance
        }.get(danger_level, 0.08)
        
        # Find closest defender to shot location
        closest_defender = min(defenders, key=lambda d: (
            (self.coordinate_engine.player_positions.get(d.id, (d.x, d.y))[0] - shot_pos[0])**2 +
            (self.coordinate_engine.player_positions.get(d.id, (d.x, d.y))[1] - shot_pos[1])**2
        ))
        
        # Calculate block skill
        block_skill = (
            getattr(closest_defender, 'shot_blocking', 10) * 0.5 +
            getattr(closest_defender, 'defensive_awareness', 10) * 0.3 +
            getattr(closest_defender, 'aggressiveness', 10) * 0.2
        ) * fatigue_factor
        
        # Distance factor - closer defenders more likely to block
        defender_pos = self.coordinate_engine.player_positions.get(closest_defender.id, (closest_defender.x, closest_defender.y))
        distance_to_shot = ((defender_pos[0] - shot_pos[0])**2 + (defender_pos[1] - shot_pos[1])**2)**0.5
        distance_factor = max(0.3, 1.0 - (distance_to_shot / 30))  # Reduced effectiveness beyond 30 feet
        
        final_block_chance = base_block_chance * (block_skill / 15) * distance_factor
        
        if random.random() < final_block_chance:
            self.events.append({
                'time': self.time, 
                'period': self.period, 
                'team': opp_team_name, 
                'player': closest_defender, 
                'event': 'Shot Blocked'
            })
            return True
        
        return False

    def _check_shot_blocking(self, defending_team, fatigue_factor):
        """Legacy shot blocking method for compatibility"""
        if random.random() > 0.05:  # Drastically reduced from 0.12 to 0.05 (only 5% block rate)
            return False
            
        defenders = [p for p in self.on_ice[defending_team]['Defense'] if p]
        if not defenders:
            return False
            
        defender = random.choice(defenders)
        block_skill = (
            getattr(defender, 'shot_blocking', 10) * 0.5 +
            getattr(defender, 'defensive_awareness', 10) * 0.3 +
            getattr(defender, 'aggressiveness', 10) * 0.2
        ) * fatigue_factor
        
        if block_skill > 15:  # Made it harder to block (was 12, now 15)
            self.events.append({
                'time': self.time, 'period': self.period, 
                'team': defending_team, 'player': defender, 
                'event': 'Shot Blocked'
            })
            return True
        return False
    
    def _resolve_pass_event(self, passer, shooters, puck_team_name, opp_team_name, fatigue_factor):
        """Enhanced pass resolution"""
        if len(shooters) <= 1:
            return
            
        receiver = random.choice([p for p in shooters if p != passer])
        
        # Calculate pass skill
        pass_skill = (
            getattr(passer, 'passing_accuracy', 10) * 0.3 +
            getattr(passer, 'passing_creativity', 10) * 0.25 +
            getattr(passer, 'vision', 10) * 0.2 +
            getattr(passer, 'off_the_puck', 10) * 0.15 +
            getattr(passer, 'hockey_iq', 10) * 0.1
        ) * fatigue_factor
        
        # Defensive pressure
        defenders = [p for p in self.on_ice[opp_team_name]['Defense'] if p]
        defender = random.choice(defenders) if defenders else None
        
        defense_skill = (
            getattr(defender, 'pokecheck', 10) * 0.4 +
            getattr(defender, 'defensive_awareness', 10) * 0.4 +
            getattr(defender, 'anticipation', 10) * 0.2
        ) if defender else 10
        
        pass_success = pass_skill > defense_skill or random.random() < 0.7
        
        # Log pass event
        puck_start = (passer.x, passer.y)
        puck_end = (receiver.x, receiver.y)
        duration = random.uniform(0.7, 1.2)
        
        self.event_log.append({
            'timestamp': self.time,
            'duration': duration,
            'type': 'PASS',
            'details': {
                'passer_id': passer.id,
                'receiver_id': receiver.id,
                'puck_start_pos': puck_start,
                'puck_end_pos': puck_end,
                'success': pass_success
            }
        })
        
        # Move puck
        if pass_success:
            self.puck_x, self.puck_y = puck_end
            # Update assist potential
            if hasattr(receiver, 'assist_potential'):
                receiver.assist_potential = passer.id
        else:
            if defender:
                self.puck_x, self.puck_y = defender.x, defender.y
    
    def _resolve_deke_event(self, deker, puck_team_name, fatigue_factor):
        """Resolve deke attempt"""
        deke_skill = (
            getattr(deker, 'stickhandling', 10) * 0.4 +
            getattr(deker, 'agility', 10) * 0.3 +
            getattr(deker, 'anticipation', 10) * 0.3
        ) * fatigue_factor
        
        if deke_skill > 12:
            self.events.append({
                'time': self.time, 'period': self.period, 
                'team': puck_team_name, 'player': deker, 
                'event': 'Successful Deke'
            })
    
    def _resolve_puck_battle(self, shooters, puck_team_name, fatigue_factor):
        """Resolve puck battle between teammates"""
        if len(shooters) < 2:
            return
            
        battlers = random.sample(shooters, 2)
        p1, p2 = battlers
        
        p1_skill = (
            getattr(p1, 'strength', 10) * 0.25 +
            getattr(p1, 'aggressiveness', 10) * 0.2 +
            getattr(p1, 'balance', 10) * 0.2 +
            getattr(p1, 'work_rate', 10) * 0.2 +
            getattr(p1, 'loose_puck', 10) * 0.15
        ) * fatigue_factor
        
        p2_skill = (
            getattr(p2, 'strength', 10) * 0.25 +
            getattr(p2, 'aggressiveness', 10) * 0.2 +
            getattr(p2, 'balance', 10) * 0.2 +
            getattr(p2, 'work_rate', 10) * 0.2 +
            getattr(p2, 'loose_puck', 10) * 0.15
        ) * fatigue_factor
        
        winner = p1 if p1_skill >= p2_skill else p2
        self.events.append({
            'time': self.time, 'period': self.period, 
            'team': puck_team_name, 'player': winner, 
            'event': 'Puck Battle Won'
        })
    
    def _resolve_screen_event(self, screener, shooters, puck_team_name):
        """Resolve screening attempt"""
        screen_skill = getattr(screener, 'screen_shots', 10)
        if screen_skill > 13:
            self.events.append({
                'time': self.time, 'period': self.period, 
                'team': puck_team_name, 'player': screener, 
                'event': 'Screen Set'
            })
    
    def _resolve_deflection_event(self, deflector, shooters, goalie, puck_team_name, opp_team_name):
        """Resolve deflection attempt"""
        deflection_skill = getattr(deflector, 'deflections', 10)
        if deflection_skill > 14 and random.random() < 0.3:
            # Successful deflection increases goal chance
            goalie_skill = self._calculate_goalie_save_skill(goalie, "deflection") if goalie else 8
            goal_chance = 0.25 + (deflection_skill - goalie_skill) * 0.01
            
            if random.random() < goal_chance:
                self.score[puck_team_name] += 1
                self.stats[puck_team_name][deflector.id]['goals'] = self.stats[puck_team_name][deflector.id].get('goals', 0) + 1
                self.events.append({
                    'time': self.time, 'period': self.period, 
                    'team': puck_team_name, 'player': deflector, 
                    'event': 'Deflection Goal'
                })
    
    def _check_for_penalty(self, players, puck_team_name, opp_team_name, fatigue_factor):
        """Penalty checking tuned to NHL rates (~3-4 penalties per team per game).

        Called once per game event (~110 events/game), so per-event probability
        of ~6% yields realistic penalty totals. Player discipline/aggressiveness
        and fatigue modulate the chance. Sets a real 2-minute penalty clock.
        """
        if not players:
            return

        penalized = random.choice(players)
        discipline_rating = getattr(penalized, 'discipline', 10)
        aggressiveness = getattr(penalized, 'aggressiveness', 10)

        # Base ~2.2% per check (~250 checks/game -> ~6-8 penalties/game, NHL rate);
        # tired/undisciplined/aggressive players foul more
        base = 0.022 * (2.0 - fatigue_factor)
        discipline_mod = (10 - discipline_rating) * 0.001
        aggr_mod = (aggressiveness - 10) * 0.0008
        penalty_chance = min(0.06, max(0.005, base + discipline_mod + aggr_mod))

        if random.random() >= penalty_chance:
            return

        self.stats[puck_team_name][penalized.id]['penalties'] = \
            self.stats[puck_team_name][penalized.id].get('penalties', 0) + 1
        self.events.append({
            'time': self.time, 'period': self.period,
            'team': puck_team_name, 'player': penalized,
            'event': 'Penalty'
        })
        self.pp_team = opp_team_name
        self.pk_team = puck_team_name
        # 2-minute minor; on a 5-on-3 the PP lasts until the later expiry
        new_expiry = self.time + 120
        self.pp_end_time = new_expiry if not self.pp_end_time else max(self.pp_end_time, new_expiry)

    def get_state(self, step):
        # Defensive: check bounds
        if step < 0 or step >= len(self.state_history):
            return {'players': [], 'puck': {}, 'events': []}
        state = self.state_history[step]
        players = []
        # Home skaters
        for p in state['home']:
            player_obj = next((pl for pl in self.home_team.roster if pl.id == p['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': p['x'], 'y': p['y'], 'id': p['id'], 'team': 'home', 'number': number})
        # Away skaters
        for p in state['away']:
            player_obj = next((pl for pl in self.away_team.roster if pl.id == p['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': p['x'], 'y': p['y'], 'id': p['id'], 'team': 'away', 'number': number})
        # Home goalie
        if state['home_goalie']:
            player_obj = next((pl for pl in self.home_team.roster if pl.id == state['home_goalie']['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': state['home_goalie']['x'], 'y': state['home_goalie']['y'], 'id': state['home_goalie']['id'], 'team': 'home', 'number': number})
        # Away goalie
        if state['away_goalie']:
            player_obj = next((pl for pl in self.away_team.roster if pl.id == state['away_goalie']['id']), None)
            number = player_obj.jersey_number if player_obj else ""
            players.append({'x': state['away_goalie']['x'], 'y': state['away_goalie']['y'], 'id': state['away_goalie']['id'], 'team': 'away', 'number': number})
        puck = {'x': state['puck']['x'], 'y': state['puck']['y']}
        events = []
        for event in self.events:
            if event['event'] == 'Goal' and step == event['time'] // 45:
                events.append(f"Goal by {event['player'].full_name}!")
        return {
            'players': players,
            'puck': puck,
            'events': events
        }

# --- Main GUI Application ---
class HockeyManagerGUI(tk.Tk):
    """Main GUI for the hockey manager application with modern UI design."""
    
    # Modern UI constants
    MODERN_UI_ENABLED = True

    def __init__(self, game_manager):
        super().__init__()

        # Dark form controls app-wide: no more white text boxes.
        try:
            from modern_widgets import apply_dark_form_theme
            apply_dark_form_theme(self)
        except Exception:
            pass

        # Initialize modern UI systems FIRST
        self.modern_theme = create_modern_theme()
        self.typography = TypographySystem()
        self.professional_widgets = ProfessionalWidgets(self.modern_theme)
        
        # Font family for backward compatibility
        self.FONT_FAMILY = self.typography.font_family
        
        # Legacy color constants for backwards compatibility
        self.BG_COLOR = self.modern_theme.colors.primary_bg
        self.CONTENT_BG = self.modern_theme.colors.secondary_bg
        self.TEXT_COLOR = self.modern_theme.colors.secondary_text
        self.HEADER_COLOR = self.modern_theme.colors.primary_text
        self.ACCENT_COLOR = self.modern_theme.colors.primary_accent
        self.CALENDAR_ACCENT_COLOR = self.modern_theme.colors.calendar_accent
        self.TITLE_BAR_COLOR = self.modern_theme.colors.tertiary_bg
        self.ACCENT_ACTIVE = self.modern_theme.colors.danger
        self.ACCENT_HOVER = self.modern_theme.colors.warning
        
        # Initialize Phase 2 optimizations
        self._initialize_phase2_systems()
        
        # Initialize Phase 3 UI/UX optimizations
        self._initialize_phase3_systems()
        
        self.game_manager = game_manager
        self.league = game_manager.league
        self.user_team = None
        self.is_new_game = True  # Track if this is a new game (no autosave until first manual save)
        self.tree_maps = {}
        self.scouting_assignments = {}
        self.open_windows = {}
        self.current_date = START_DATE
        self.game_manager.current_date = self.current_date  # Sync with game_manager for dashboard
        self.news_log = [{'date': self.current_date, 'story': "Welcome to the new season!"}]
        self.game_results = []  # Store completed game results for viewing
        self.waiver_list = []
        self.trade_block = []
        
        # Initialize Season Flow system
        self.season_flow_panel = None
        self.season_flow_visible = False

        # FM-style career systems: bulk-sim flag suppresses interactive prompts
        self._bulk_simming = False

        # use_game_viewer is now controlled through settings.json, no longer a hardcoded instance variable

        self._setup_styles()
        self.title("Puck Dynasty - Hockey Manager")
        self.geometry("1400x800")
        self.configure(background=self.BG_COLOR)
        
        # Set application icon
        self._set_application_icon()
        
        # Load UI icons for buttons and menus
        self._load_ui_icons()

        # Initialize save/load system
        self.save_manager = GameSaveManager(self.game_manager)
        
        # Initialize shortlist system
        from shortlist_system import ShortlistManager
        self.shortlist_manager = ShortlistManager()
        
        self.withdraw()
        # Check if user team is already set from startup
        print(f"DEBUG HockeyManagerGUI: Checking for user_team...")
        print(f"DEBUG: hasattr(game_manager, 'user_team') = {hasattr(self.game_manager, 'user_team')}")
        if hasattr(self.game_manager, 'user_team'):
            print(f"DEBUG: game_manager.user_team = {self.game_manager.user_team}")
        
        # Try to get user team from multiple sources
        user_team_found = None
        
        # First, check if game_manager already has user_team set
        if hasattr(self.game_manager, 'user_team') and self.game_manager.user_team:
            user_team_found = self.game_manager.user_team
            print(f"DEBUG: Found user_team from game_manager: {user_team_found.team_name}")
        
        # If not found, try to find it from startup_settings
        if not user_team_found and hasattr(self.game_manager, 'startup_settings') and self.game_manager.startup_settings:
            selected_team_name = self.game_manager.startup_settings.get('selected_team') or self.game_manager.startup_settings.get('user_team')
            print(f"DEBUG: Looking for team from startup_settings: '{selected_team_name}'")
            if selected_team_name and hasattr(self, 'league') and self.league:
                # Try exact match first
                for team in self.league.teams:
                    if team.team_name == selected_team_name:
                        user_team_found = team
                        self.game_manager.user_team = team
                        print(f"DEBUG: Found team from startup_settings (exact): {team.team_name}")
                        break
                
                # If not found, try case-insensitive partial match (handles encoding differences)
                if not user_team_found:
                    selected_lower = selected_team_name.lower().replace('é', 'e').replace('ö', 'o')
                    for team in self.league.teams:
                        team_lower = team.team_name.lower().replace('é', 'e').replace('ö', 'o')
                        if selected_lower in team_lower or team_lower in selected_lower:
                            user_team_found = team
                            self.game_manager.user_team = team
                            print(f"DEBUG: Found team from startup_settings (partial): {team.team_name}")
                            break
                
                # If still not found, just use the first team to avoid hanging
                if not user_team_found and self.league.teams:
                    user_team_found = self.league.teams[0]
                    self.game_manager.user_team = user_team_found
                    print(f"DEBUG: Team not found, defaulting to: {user_team_found.team_name}")
        
        if user_team_found:
            # Team already selected from startup window
            self.user_team = user_team_found
            self.user_team.is_user_team = True
            
            # Set GM profile from startup settings
            if hasattr(self.game_manager, 'startup_settings') and self.game_manager.startup_settings:
                gm_name = self.game_manager.startup_settings.get('gm_name', 'General Manager')
                gm_profile = self.game_manager.startup_settings.get('gm_profile', None)
                
                self.user_team.gm_name = gm_name
                if gm_profile:
                    self.user_team.gm_profile = gm_profile
                    print(f"GM Profile: {gm_profile.name} ({gm_profile.age} years old) from {gm_profile.birthplace}")
                    print(f"Background: {gm_profile.management_style} style, {gm_profile.education_level}")
                
                print(f"GM {gm_name} assigned to {self.user_team.team_name}")
                
                # Add comprehensive GM hiring announcement to news
                if gm_profile and gm_profile.former_player:
                    playing_background = f"The former {gm_profile.playing_position.lower()} played {gm_profile.nhl_games_played} NHL games and scored {gm_profile.career_points} career points. "
                else:
                    playing_background = ""
                    
                management_background = ""
                if gm_profile:
                    if gm_profile.coaching_experience:
                        management_background += f"With {gm_profile.years_coaching} years of coaching experience, "
                    if gm_profile.assistant_gm_experience:
                        management_background += f"and {gm_profile.years_as_assistant} years as an assistant GM, "
                        
                gm_announcement = f"BREAKING: The {self.user_team.team_name} have officially announced the hiring of {gm_name} as their new General Manager. {playing_background}{management_background}{gm_name} takes over hockey operations immediately and will be responsible for all roster decisions, trades, and draft picks. Welcome to the organization, {gm_name}!"
                self.news_log.append({'date': self.current_date, 'story': gm_announcement})
                print(f"GM announcement added to news: {gm_name} hired by {self.user_team.team_name}")
            
            self.title(f"{self.user_team.team_name} - Hockey Manager")
            
            # Initialize databases and preload user team data
            self._finalize_phase2_initialization()
            self._generate_initial_emails()
            self.deiconify()
            self._create_main_dashboard()
            self._apply_phase3_optimizations()
            self.setup_autosave()  # Set up autosave system
            self.setup_close_protocol()  # Set up save prompt on close
            self.update_all_views()
        else:
            # For now, skip launcher integration and use simple team selection
            # The launcher system needs to be redesigned for proper integration
            print("Using simplified team selection for now...")
            
            # Temporarily show main window so the team selection dialog is visible
            self.deiconify()
            self.update()
            
            # Simple team selection dialog
            team_names = [team.team_name for team in self.league.teams]
            
            # Create simple selection window as a Toplevel (child of main window)
            selection_window = tk.Toplevel(self)
            selection_window.title("Select Your Team - Puck Dynasty")
            selection_window.geometry("400x300")
            selection_window.configure(bg='#181818')
            
            # Center the window
            selection_window.update_idletasks()
            x = (selection_window.winfo_screenwidth() // 2) - 200
            y = (selection_window.winfo_screenheight() // 2) - 150
            selection_window.geometry(f"400x300+{x}+{y}")
            
            # Make it modal
            selection_window.transient(self)
            selection_window.grab_set()
            
            # Make it stay on top and focused
            selection_window.lift()
            selection_window.focus_force()
            selection_window.attributes('-topmost', True)
            
            tk.Label(selection_window, text="Choose Your Team:",
                    font=('Segoe UI', 16, 'bold'),
                    bg='#181818', fg='#FFFFFF').pack(pady=20)
            
            team_var = tk.StringVar(master=selection_window, value=team_names[0])
            team_listbox = tk.Listbox(selection_window, 
                                     font=('Segoe UI', 12),
                                     bg='#2A2A2A', fg='#FFFFFF',
                                     selectbackground='#D13438')
            
            for team_name in team_names:
                team_listbox.insert(tk.END, team_name)
            
            team_listbox.pack(pady=10, padx=20, fill='both', expand=True)
            team_listbox.selection_set(0)  # Select first team by default
            
            selected_team = [None]  # Use list to store result
            
            def on_select():
                selection = team_listbox.curselection()
                if selection:
                    selected_team_name = team_listbox.get(selection[0])
                    user_team = next((t for t in self.league.teams if t.team_name == selected_team_name), None)
                    
                    if user_team:
                        selected_team[0] = user_team
                        selection_window.destroy()
            
            def on_cancel():
                print("Team selection cancelled - exiting...")
                selection_window.destroy()
                self.destroy()  # Close the main app too
                sys.exit()
            
            button_frame = tk.Frame(selection_window, bg='#181818')
            button_frame.pack(pady=10)
            
            tk.Button(button_frame, text="Select Team", 
                     command=on_select,
                     bg='#D13438', fg='white', font=('Segoe UI', 12)).pack(side='left', padx=5)
            
            tk.Button(button_frame, text="Cancel",
                     command=on_cancel, 
                     bg='#666666', fg='white', font=('Segoe UI', 12)).pack(side='left', padx=5)
            
            # Wait for window to close (modal dialog)
            print("Showing team selection window...")
            selection_window.wait_window()
            print("Team selection completed")
            
            if selected_team[0]:
                print(f"User selected: {selected_team[0].team_name}")
                user_team = selected_team[0]
                self.game_manager.user_team = user_team
                self.user_team = user_team
                user_team.is_user_team = True
                self.title(f"{user_team.team_name} - Puck Dynasty")
                
                # Generate initial emails and continue setup
                self._finalize_phase2_initialization()
                self._generate_initial_emails()
                
                # Continue with main game setup
                print("Showing main game window...")
                self.deiconify()
                self._create_main_dashboard()
                self._apply_phase3_optimizations()
                self.setup_autosave()
                self.setup_close_protocol()
                self.update_all_views()
            else:
                print("No team selected, exiting...")
                self.quit()
                return
            
    def add_news(self, story):
        """Add a news item to the news log."""
        self.news_log.append({'date': self.current_date, 'story': story})
        # Update news window if it's open
        if 'news' in self.open_windows and self.open_windows['news'].winfo_exists():
            self.open_windows['news'].populate_news()
        # Update front page news panel
        self.update_news_panel()
            
    def process_waivers(self):
        """Process waiver claims and update waiver days for all players on waivers."""
        # Process claims by CPU teams (from worst team to best)
        teams_by_ranking = sorted(self.league.teams, key=lambda t: sum(p.overall_rating() for p in t.roster), reverse=False)
        
        claimed_players = []
        for player in self.waiver_list:
            if player in claimed_players:
                continue
                
            # Don't process players just placed on waivers
            if player.waiver_days == 2:
                player.waiver_days -= 1
                continue
                
            # Last day on waivers, process possible claims
            if player.waiver_days == 1:
                # Determine claiming team (if any)
                claiming_team = None
                for team in teams_by_ranking:
                    # Skip player's current team
                    if team.team_name == player.team_name:
                        continue
                        
                    # Skip user team (user must claim manually)
                    if team.is_user_team:
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
                    # Remove from original team
                    original_team = next((t for t in self.league.teams if t.team_name == player.team_name), None)
                    if original_team:
                        if player in original_team.roster:
                            original_team.remove_player(player)
                        elif hasattr(original_team, 'ahl_roster') and player in original_team.ahl_roster:
                            original_team.ahl_roster.remove(player)
                    
                    # Add to claiming team
                    claiming_team.add_player(player)
                    player.team_name = claiming_team.team_name
                    
                    # Reset waiver status
                    player.on_waivers = False
                    player.waiver_days = 0
                    
                    # Add to news log
                    self.add_news(f"{player.full_name} claimed off waivers by {claiming_team.team_name}.")
                    
                    # Mark as claimed
                    claimed_players.append(player)
                else:
                    # Player cleared waivers
                    player.waiver_days = 0
                    player.on_waivers = False
                    
                    # Add to original team's AHL roster if they're the user team
                    original_team = next((t for t in self.league.teams if t.team_name == player.team_name), None)
                    if original_team and original_team.is_user_team and hasattr(original_team, 'ahl_roster'):
                        if player in original_team.roster:
                            original_team.roster.remove(player)
                        original_team.ahl_roster.append(player)
                        
                    self.add_news(f"{player.full_name} cleared waivers.")
            
            # Reduce waiver days for players still on waivers
            elif player.waiver_days > 0:
                player.waiver_days -= 1
        
        # Remove claimed players from waiver list
        for player in claimed_players:
            if player in self.waiver_list:
                self.waiver_list.remove(player)
                
        # Remove players who cleared waivers
        self.waiver_list = [p for p in self.waiver_list if p.on_waivers and p.waiver_days > 0]
        
        # Update any open waiver windows
        if 'waivers' in self.open_windows and self.open_windows['waivers'].winfo_exists():
            self.open_windows['waivers'].populate_eligible_players()
            self.open_windows['waivers'].populate_waiver_wire()

    def _setup_styles(self):
        """Configures the modern visual style of the application."""
        self.style = ttk.Style(self)
        
        # Apply modern theme to ttk.Style
        self.modern_theme.apply_to_style(self.style)
        
        # Set color constants for backward compatibility
        self.BG_COLOR = self.modern_theme.colors.primary_bg
        self.CONTENT_BG = self.modern_theme.colors.secondary_bg
        self.TITLE_BAR_COLOR = self.modern_theme.colors.tertiary_bg
        self.TEXT_COLOR = self.modern_theme.colors.secondary_text
        self.HEADER_COLOR = self.modern_theme.colors.primary_text
        self.ACCENT_COLOR = self.modern_theme.colors.primary_accent
        self.CALENDAR_ACCENT_COLOR = self.modern_theme.colors.calendar_accent
        self.ACCENT_ACTIVE = self.modern_theme.colors.danger
        self.ACCENT_HOVER = self.modern_theme.colors.warning
        
        # Configure window background
        self.configure(background=self.BG_COLOR)
        
        # Apply team-specific styling if user team is set
        self._update_team_colors()

    def _update_team_colors(self):
        """Update button colors to match the user's team colors"""
        if hasattr(self, 'user_team') and self.user_team and hasattr(self, 'modern_theme'):
            self.modern_theme.update_team_colors(self.style, self.user_team.team_name)

    def _set_application_icon(self):
        """Set the Puck Dynasty logo as the application icon"""
        try:
            import os
            # Get the path to the logo file
            logo_path = os.path.join(os.path.dirname(__file__), "PUCK DYNASTY LOGO.png")
            
            if os.path.exists(logo_path):
                # Check if PIL is available for image processing
                try:
                    from PIL import Image, ImageTk
                    
                    # Load the image and resize it for icon use
                    icon_image = Image.open(logo_path)
                    # Resize to standard icon sizes (keeping aspect ratio)
                    icon_image = icon_image.resize((64, 64), Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    self.icon_photo = ImageTk.PhotoImage(icon_image)
                    
                    # Set as window icon
                    self.iconphoto(True, self.icon_photo)
                    
                    print("✅ Puck Dynasty logo set as application icon")
                except ImportError:
                    print("⚠️ PIL not available for icon, using text icon")
                    self.title("🏒 Puck Dynasty - Hockey Manager")
            else:
                print(f"⚠️ Logo file not found at: {logo_path}")
                # Set a text-based icon as fallback
                self.title("🏒 Puck Dynasty - Hockey Manager")
        except Exception as e:
            print(f"⚠️ Error setting application icon: {e}")
            # Continue without icon - don't crash the application
            pass

    def _load_ui_icons(self):
        """Load UI icons from the icons folder for buttons and menus"""
        self.ui_icons = {}
        
        try:
            from PIL import Image, ImageTk
            import os
            
            # Define icon mappings (filename -> icon_key)
            icon_mappings = {
                'managericon.png': 'manager',
                'playericon.png': 'player', 
                'statsicon.png': 'stats',
                'trophyicon.png': 'trophy',
                'settingsicon.png': 'settings',
                'news icon.png': 'news',
                'clipboard png.png': 'clipboard'
            }
            
            icons_folder = os.path.join(os.path.dirname(__file__), "icons")
            
            for filename, icon_key in icon_mappings.items():
                icon_path = os.path.join(icons_folder, filename)
                
                if os.path.exists(icon_path):
                    try:
                        # Load and resize icon for button use (20x20 for menu buttons)
                        icon_image = Image.open(icon_path)
                        
                        # Resize to button-appropriate size
                        icon_image = icon_image.resize((20, 20), Image.Resampling.LANCZOS)
                        
                        # Convert to PhotoImage and store with proper reference
                        photo_image = ImageTk.PhotoImage(icon_image)
                        
                        # Store the PhotoImage with a strong reference to prevent garbage collection
                        self.ui_icons[icon_key] = photo_image
                        
                        # Keep an additional reference in a list to prevent garbage collection
                        if not hasattr(self, '_icon_references'):
                            self._icon_references = []
                        self._icon_references.append(photo_image)
                        
                        print(f"✅ Loaded UI icon: {icon_key}")
                        
                    except Exception as e:
                        print(f"⚠️ Failed to load icon {filename}: {e}")
                        self.ui_icons[icon_key] = None
                else:
                    print(f"⚠️ Icon file not found: {filename}")
                    self.ui_icons[icon_key] = None
            
            print(f"✅ UI Icons loaded: {len([k for k, v in self.ui_icons.items() if v is not None])}/{len(icon_mappings)}")
            
        except ImportError:
            print("⚠️ PIL not available for UI icons, using text labels")
            self.ui_icons = {}
        except Exception as e:
            print(f"⚠️ Error loading UI icons: {e}")
            self.ui_icons = {}

    def _select_team(self):
        team_names = sorted([t.team_name for t in self.league.teams])
        chosen_team_name = simpledialog.askstring("Team Selection", "Enter the name of the team you want to manage:", initialvalue=random.choice(team_names))
        if chosen_team_name:
            self.user_team = next((t for t in self.league.teams if t.team_name == chosen_team_name), None)
            if self.user_team:
                self.user_team.is_user_team = True
                self.game_manager.user_team = self.user_team
                self.title(f"{self.user_team.team_name} - Hockey Manager")
                
                # Generate initial welcome emails
                self._generate_initial_emails()
                
                return True
        messagebox.showerror("Error", "Team not found or selection cancelled. Exiting.")
        return False
        
    def _generate_initial_emails(self):
        """Generate initial emails when starting the game."""
        from game_classes import EmailGenerator
        
        # Add GM hiring announcement email
        gm_name = getattr(self.user_team, 'gm_name', 'General Manager')
        
        hiring_email = EmailGenerator.create_league_announcement_email(
            f"Welcome Aboard, {gm_name}!",
            f"Dear {gm_name},\n\n"
            f"On behalf of the entire {self.user_team.team_name} organization, we are thrilled to officially welcome you as our new General Manager!\n\n"
            f"Your appointment has been announced to the media, and the hockey world is excited to see what you bring to our franchise. As GM, you will have complete authority over:\n\n"
            f"🏒 ROSTER MANAGEMENT\n"
            f"• Managing our NHL roster and salary cap (Current space: ${self.user_team.cap_space:,})\n"
            f"• Making trades and signing free agents\n"
            f"• Promoting/demoting players between NHL, AHL, and prospects\n\n"
            f"📋 STRATEGIC DECISIONS\n"
            f"• Setting lineups and game strategy\n"
            f"• Developing prospects and managing our farm system\n"
            f"• Negotiating contracts and managing the salary cap\n\n"
            f"We have complete confidence in your abilities to lead this organization to success. The fans are counting on you, and we're here to support you every step of the way.\n\n"
            f"Welcome to the family, {gm_name}. Let's bring a championship to our city!\n\n"
            f"Team Owner & Board of Directors\n{self.user_team.team_name}"
        )
        self.user_team.inbox.add_message(hiring_email)
        
        # Add a welcome message based on actual team
        welcome_email = EmailGenerator.create_league_announcement_email(
            f"NHL Commissioner's Welcome - {gm_name}",
            f"Dear {gm_name},\n\n"
            f"Congratulations on being appointed as the General Manager of the {self.user_team.team_name}!\n\n"
            f"The National Hockey League welcomes you to the exclusive fraternity of NHL General Managers. Your responsibilities include:\n"
            f"• Managing the roster and salary cap (Current cap space: ${self.user_team.cap_space:,})\n"
            f"• Making trades and signing free agents\n"
            f"• Setting lineups and game strategy\n"
            f"• Developing prospects and managing the farm system\n\n"
            f"We look forward to working with you and wish you great success in your new role.\n\n"
            f"Good luck with your new role, {gm_name}!\n\n"
            f"Commissioner\nNational Hockey League"
        )
        self.user_team.inbox.add_message(welcome_email)
        
        # Generate season preview email with actual roster data
        if self.user_team.roster:
            top_players = sorted(self.user_team.roster, key=lambda p: p.overall_rating(), reverse=True)[:3]
            player_names = [p.full_name for p in top_players]
            
            season_email = EmailGenerator.create_league_announcement_email(
                f"{self.current_date.year}-{self.current_date.year + 1} Season Preview",
                f"The new NHL season is approaching!\n\n"
                f"Your {self.user_team.team_name} roster features:\n"
                f"• {player_names[0]} (Overall: {top_players[0].overall_rating()}/20)\n"
                f"• {player_names[1]} (Overall: {top_players[1].overall_rating()}/20)\n"
                f"• {player_names[2]} (Overall: {top_players[2].overall_rating()}/20)\n\n"
                f"Current roster size: {len(self.user_team.roster)} NHL players\n"
                f"AHL affiliates: {len(getattr(self.user_team, 'ahl_roster', []))}\n\n"
                f"Best of luck for the upcoming season!\n\n"
                f"NHL Public Relations"
            )
            self.user_team.inbox.add_message(season_email)

    def _create_main_dashboard(self):
        """Creates the main dashboard with enhanced menu bar and modern dashboard system."""
        # Clear any existing content
        for widget in self.winfo_children():
            widget.destroy()
        
        # Create main container with proper layout
        main_container = ttk.Frame(self, style='Panel.TFrame')
        main_container.pack(fill="both", expand=True)
        
        # Configure grid weights for proper expansion
        main_container.grid_rowconfigure(0, weight=0)  # Menu bar - fixed height
        main_container.grid_rowconfigure(1, weight=1)  # Dashboard - expandable
        main_container.grid_columnconfigure(0, weight=1)
        
        # Create enhanced menu bar at the top
        self._create_enhanced_menu_bar(main_container)
        
        # Create atmospheric dashboard instance for immersive GM experience
        self.dashboard = AtmosphericDashboard(
            parent=self,
            game_manager=self.game_manager,
            user_team=self.user_team
        )
        
        # Create the dashboard UI in its own frame
        dashboard_frame = ttk.Frame(main_container, style='Panel.TFrame')
        dashboard_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.dashboard.create_immersive_dashboard(dashboard_frame)
        
        # Update dashboard with current data
        self.update_dashboard_data()
        
    def update_dashboard_data(self):
        """Update the dashboard with current game data."""
        if hasattr(self, 'dashboard') and self.dashboard:
            # Update with current game state
            current_date = self.game_manager.current_date if hasattr(self.game_manager, 'current_date') else "Season Start"
            
            # Get team record
            wins = getattr(self.user_team, 'wins', 0)
            losses = getattr(self.user_team, 'losses', 0)
            ot_losses = getattr(self.user_team, 'ot_losses', 0)
            
            self.dashboard.update_data(
                current_date=current_date,
                team_record=f"{wins}-{losses}-{ot_losses}",
                next_game=self._get_next_game_info(),
                roster_highlights=self._get_roster_highlights(),
                recent_news=self._get_recent_news()
            )
    
    def _get_next_game_info(self):
        """Get information about the next scheduled game."""
        # Placeholder - would integrate with actual scheduling system
        return {
            'opponent': 'TBD',
            'date': 'TBD',
            'home_away': 'Home',
            'time': 'TBD'
        }
    
    def _get_roster_highlights(self):
        """Get key roster information for dashboard."""
        if not self.user_team:
            return []
        
        highlights = []
        
        # Top scorer
        if self.user_team.roster:
            top_scorer = max(self.user_team.roster, key=lambda p: getattr(p, 'goals', 0))
            highlights.append({
                'title': 'Leading Scorer',
                'player': top_scorer.full_name,
                'stat': f"{getattr(top_scorer, 'goals', 0)}G, {getattr(top_scorer, 'assists', 0)}A"
            })
        
        return highlights
    
    def _get_recent_news(self):
        """Get recent news items for dashboard."""
        # Placeholder for news system
        return [
            {'title': 'Welcome to Hockey Manager', 'description': 'Begin your management career!'}
        ]
        
    def _create_enhanced_top_bar(self, parent):
        """Create an enhanced top bar with more team information."""
        top_bar = ttk.Frame(parent, style='TitleBar.TFrame', padding=10)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Team logo and info section
        team_info_frame = ttk.Frame(top_bar, style='TitleBar.TFrame')
        team_info_frame.pack(side="left", fill="y")
        
        # Team logo placeholder with better styling
        logo_frame = ttk.Frame(team_info_frame, style='Panel.TFrame', padding=5)
        logo_frame.pack(side="left", padx=(0, 15))
        
        logo_placeholder = tk.Canvas(logo_frame, width=60, height=60, 
                                   bg=self.TITLE_BAR_COLOR, highlightthickness=1,
                                   highlightbackground=self.TEXT_COLOR)
        logo_placeholder.pack()
        logo_placeholder.create_text(30, 30, text="LOGO", fill="white", 
                                    font=(self.FONT_FAMILY, 8, 'bold'))
        
        # Team name and record
        team_text_frame = ttk.Frame(team_info_frame, style='TitleBar.TFrame')
        team_text_frame.pack(side="left", fill="y")
        
        ttk.Label(team_text_frame, text=f"{self.user_team.team_name}", 
                 style='Header.TLabel', font=(self.FONT_FAMILY, 18, 'bold')).pack(anchor='w')
        
        # Team record and standing (will be updated)
        self.team_record_label = ttk.Label(team_text_frame, text="Record: 0-0-0", 
                                         style='Header.TLabel', font=(self.FONT_FAMILY, 12))
        self.team_record_label.pack(anchor='w')
        
        # Right side - Date and important info
        right_info_frame = ttk.Frame(top_bar, style='TitleBar.TFrame')
        right_info_frame.pack(side="right", fill="y")
        
        # Current date
        self.date_label = ttk.Label(right_info_frame, text="", 
                                  style='Header.TLabel', font=(self.FONT_FAMILY, 14, 'bold'))
        self.date_label.pack(anchor='e')
        
        # Quick info labels
        info_frame = ttk.Frame(right_info_frame, style='TitleBar.TFrame')
        info_frame.pack(anchor='e', pady=(5, 0))
        
        self.cap_space_label = ttk.Label(info_frame, text="Cap Space: $0", 
                                       style='Header.TLabel', font=(self.FONT_FAMILY, 10))
        self.cap_space_label.pack(anchor='e')
        
        # Season Flow Controls and Continue button
        season_controls_frame = ttk.Frame(top_bar, style='TitleBar.TFrame')
        season_controls_frame.pack(side="right", padx=(20, 0))
        
        # Automated Season Flow button
        from modern_widgets import RoundedButton
        self.season_flow_btn = RoundedButton(season_controls_frame, text="⚡ Season Flow",
                                            command=self.toggle_season_flow_panel,
                                            bg="#2E7BD6", radius=10,
                                            font=(self.FONT_FAMILY, 11, "bold"))
        self.season_flow_btn.pack(pady=(2, 5))

        # Continue button with better styling
        self.continue_btn = RoundedButton(season_controls_frame, text="Continue ▶",
                                          command=self.simulate_day,
                                          bg=self.ACCENT_COLOR, radius=10,
                                          font=(self.FONT_FAMILY, 12, "bold"),
                                          padx=26, pady=12)
        self.continue_btn.pack(pady=(0, 5))
        
    def _create_enhanced_menu_bar(self, parent):
        """Create a streamlined menu bar with dropdown organization."""
        menu_bar = ttk.Frame(parent, style='Panel.TFrame', padding=4)
        menu_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        # Left side - Main action buttons (most frequently used)
        left_menu_frame = ttk.Frame(menu_bar, style='Panel.TFrame')
        left_menu_frame.pack(side="left", fill="x", expand=True)
        
        # Primary action buttons (always visible) - temporarily disable icons
        self.inbox_btn = ttk.Button(left_menu_frame, text=self._get_inbox_button_text(), 
                                  style="TeamMenu.TButton", command=self.open_inbox_window)
        self.inbox_btn.pack(side="left", padx=4)

        ttk.Button(left_menu_frame, text="Roster",
                 style="TeamMenu.TButton", 
                 command=self.open_roster_window).pack(side="left", padx=4)        # Schedule & Calendar dropdown
        self._create_dropdown_menu(left_menu_frame, "Schedule", {
            "Schedule": self.open_schedule_window,
            "🗓️ Calendar": self.open_calendar_window
        })
        
        # Separator
        separator1 = ttk.Separator(left_menu_frame, orient='vertical')
        separator1.pack(side="left", fill="y", padx=8)
        
        # Team Management dropdown
        self._create_dropdown_menu(left_menu_frame, "Team", {
            "📋 Edit Lines": self.open_edit_lines_window,
            "👥 Staff Management": self.open_staff_management_window,
            "� Player Development": self.open_development_window,
            "Scouting": self.open_scouting_management_window,
            "📊 Performance": self.open_performance_monitor,
            "🏒 Practice Center": self.open_practice_center,
            "🎩 Manager Hub": self.open_manager_hub
        })
        
        # Finances dropdown
        self._create_dropdown_menu(left_menu_frame, "Finances", {
            "💰 Team Finances": self.open_finances_window,
            "📝 Negotiate Extensions": self.open_contract_extensions_window
        })
        
        # Transactions dropdown  
        self._create_dropdown_menu(left_menu_frame, "Transactions", {
            "� Fantasy Draft": self.open_fantasy_draft_window,
            "�🆓 Free Agents": self.open_free_agency_window,
            "💥 Free Agent Frenzy": self.open_free_agency_frenzy,  # Only visible on July 1
            "🔄 Trade Center": self.open_trade_window,
            "� Trade Deadline": self.open_trade_deadline_center,  # Only visible on deadline day
            "🏒 Draft Day Central": self.open_draft_day_central,  # Only visible on draft days
            "�📋 Trade Block": self.open_trade_block_window,
            "⚖️ Waivers": self.open_waivers_window
        })
        
        # Right side - Settings and utilities
        right_menu_frame = ttk.Frame(menu_bar, style='Panel.TFrame')
        right_menu_frame.pack(side="right")

        # Save/Load dropdown
        self._create_dropdown_menu(right_menu_frame, "Save/Load", {
            "💾 Save Game": self.open_save_window,
            "📁 Load Game": self.open_load_window,
            "🏆 Playoffs": self.open_playoffs_window
        })

        # Right menu buttons - temporarily back to text
        ttk.Button(right_menu_frame, text="News", style="TeamMenu.TButton", 
                 command=self.open_news_window).pack(side="right", padx=4)

        # Media Center button (optional system)
        ttk.Button(right_menu_frame, text="Media", style="TeamMenu.TButton", 
                 command=self.open_media_center).pack(side="right", padx=4)

        # Stats & Standings button
        ttk.Button(right_menu_frame, text="Stats", style="TeamMenu.TButton", 
                 command=self.open_stats_standings_window).pack(side="right", padx=4)
        
        # GM Options as standalone button
        ttk.Button(right_menu_frame, text="GM Options", style="TeamMenu.TButton", 
                 command=self.open_gm_options_window).pack(side="right", padx=4)
        
        # Settings as its own button
        ttk.Button(right_menu_frame, text="Settings", style="TeamMenu.TButton", 
                 command=self.open_settings_window).pack(side="right", padx=4)
    
    def _create_dropdown_menu(self, parent, button_text, menu_items):
        """Create a dropdown menu button with organized menu items."""
        import tkinter as tk
        
        # Create the main dropdown button
        dropdown_btn = ttk.Button(parent, text=button_text, style="TeamMenu.TButton")
        dropdown_btn.pack(side="left", padx=4)
        
        # Create dropdown menu
        dropdown_menu = tk.Menu(self.master, tearoff=0, font=(self.FONT_FAMILY, 9))
        
        # Add menu items with conditional logic
        for item_text, command in menu_items.items():
            # Special handling for Trade Deadline Center - only show on deadline day
            if "Trade Deadline" in item_text and not is_trade_deadline_day():
                continue  # Skip this menu item if it's not deadline day
            # Draft Day Central - only show on draft days
            if "Draft Day Central" in item_text and not is_draft_day(self.current_date):
                continue
            # Free Agent Frenzy - only show on July 1
            if "Free Agent Frenzy" in item_text and not is_free_agency_day(self.current_date):
                continue
            dropdown_menu.add_command(label=item_text, command=command)
        
        # Bind button click to show menu
        def show_dropdown(event=None):
            try:
                # Get button position
                x = dropdown_btn.winfo_rootx()
                y = dropdown_btn.winfo_rooty() + dropdown_btn.winfo_height()
                dropdown_menu.post(x, y)
            except:
                pass
        
        dropdown_btn.configure(command=show_dropdown)
        
        return dropdown_btn

    def _create_panel(self, parent, title, row, col, rowspan=1, colspan=1):
        outer_frame = ttk.Frame(parent, style='Panel.TFrame', padding=1)
        outer_frame.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan, sticky="nsew", padx=0, pady=8)
        
        frame = ttk.Frame(outer_frame, style='Panel.TFrame')
        frame.grid(row=0, column=0, sticky='nsew')

        title_bar = ttk.Frame(frame, style='TitleBar.TFrame')
        title_bar.grid(row=0, column=0, sticky='ew')
        ttk.Label(title_bar, text=title, style='Title.TLabel', padding=(10, 5)).grid(row=0, column=0, sticky='ew')
        return frame
        
    def _create_packed_panel(self, parent, title):
        """Creates a panel that uses pack layout instead of grid."""
        outer_frame = ttk.Frame(parent, style='Panel.TFrame', padding=1)
        outer_frame.pack(fill='both', expand=True, padx=0, pady=8)
        
        frame = ttk.Frame(outer_frame, style='Panel.TFrame')
        frame.pack(fill='both', expand=True)

        title_bar = ttk.Frame(frame, style='TitleBar.TFrame')
        title_bar.pack(fill='x')
        
        ttk.Label(title_bar, text=title, style='Title.TLabel', padding=(10, 5)).pack(side='left')
        return frame

    def _create_player_focus_panel(self, parent):
        panel = self._create_panel(parent, "Player Focus", 0, 0)
        self.player_focus_label = ttk.Label(panel, text="Loading player...", justify="left", font=(self.FONT_FAMILY, 11))
        self.player_focus_label.grid(row=1, column=0, pady=15, padx=20, sticky='w')  # Use grid instead of pack

    def _create_latest_news_panel(self, parent):
        panel = self._create_panel(parent, "Latest News", 1, 0)
        self.news_text = tk.Text(panel, height=8, bg='#1F1F1F', fg='#CCCCCC', wrap='word', font=(self.FONT_FAMILY, 9), borderwidth=0, relief='flat')
        self.news_text.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)  # Use grid instead of pack
        self.news_text.config(state='disabled')

    def _create_team_finances_panel(self, parent):
        panel = self._create_panel(parent, "Team Finances", 2, 0)
        self.finance_label = ttk.Label(panel, text="Loading finances...", justify="left", font=('Consolas', 11))
        self.finance_label.grid(row=1, column=0, padx=20, pady=15, sticky='w')  # Use grid instead of pack

    def _create_top_lines_panel(self, parent):
        panel = self._create_panel(parent, "Top Lines", 3, 0)
        self.top_lines_label = ttk.Label(panel, text="Loading lines...", justify="left", font=(self.FONT_FAMILY, 10))
        self.top_lines_label.grid(row=1, column=0, padx=20, pady=15, sticky='w')  # Use grid instead of pack

    def _create_team_leaders_panel(self, parent):
        panel = self._create_panel(parent, "Team Leaders", 0, 0)
        self.team_leaders_label = ttk.Label(panel, text="G: (0)\nA: (0)\nP: (0)", justify="left", font=(self.FONT_FAMILY, 11))
        self.team_leaders_label.grid(row=1, column=0, pady=15, padx=20, sticky='w')  # Use grid instead of pack

    def _create_schedule_panel(self, parent):
        panel = self._create_panel(parent, "Schedule", 1, 0)
        columns = {'date': ('Date', 100), 'opponent': ('Opponent', 150), 'result': ('Result', 80)}
        self.schedule_tree = ttk.Treeview(panel, columns=list(columns.keys()), show='headings', height=10)
        for col, (text, width) in columns.items():
            self.schedule_tree.heading(col, text=text)
            self.schedule_tree.column(col, width=width, anchor='center')
        self.schedule_tree.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)  # Use grid instead of pack
        
        # Add click handler for viewing game results
        self.schedule_tree.bind('<Double-Button-1>', self._on_schedule_double_click)

    def _create_standings_panel(self, parent):
        panel = self._create_panel(parent, "League Standings", 2, 0)
        columns = {'team': ('Team', 200), 'pts': ('Pts', 50)}
        self.standings_tree = ttk.Treeview(panel, columns=list(columns.keys()), show='headings', height=8)
        for col, (text, width) in columns.items():
            self.standings_tree.heading(col, text=text)
            self.standings_tree.column(col, width=width, anchor='w')
        self.standings_tree.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)  # Use grid instead of pack
        
    # Enhanced EHM-style panel methods
    def _create_enhanced_player_focus_panel(self, parent):
        """Enhanced player focus panel with more detailed information and better space usage."""
        panel = self._create_panel(parent, "⭐ Player Spotlight", 0, 0)
        
        # Create content frame with better layout
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=10)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Player info header with compact layout
        header_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        header_frame.pack(fill='x', pady=(0, 8))
        
        self.player_name_label = ttk.Label(header_frame, text="Loading player...", 
                                         style='PlayerInfo.TLabel', 
                                         font=(self.FONT_FAMILY, 13, 'bold'))
        self.player_name_label.pack(anchor='w')
        
        self.player_position_label = ttk.Label(header_frame, text="", 
                                             style='Info.TLabel', 
                                             font=(self.FONT_FAMILY, 10))
        self.player_position_label.pack(anchor='w')
        
        # Stats grid for efficient space usage
        stats_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        stats_frame.pack(fill='x', pady=(0, 8))
        
        # Configure grid for stats
        for i in range(3):
            stats_frame.grid_columnconfigure(i, weight=1)
        
        # Create compact stat boxes
        self.player_stats_labels = {}
        
        # Row 1: Age, OVR, Salary
        ttk.Label(stats_frame, text="Age:", style='Info.TLabel', font=(self.FONT_FAMILY, 8)).grid(row=0, column=0, sticky='w')
        self.player_stats_labels['age'] = ttk.Label(stats_frame, text="-", style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 9, 'bold'))
        self.player_stats_labels['age'].grid(row=1, column=0, sticky='w')
        
        ttk.Label(stats_frame, text="OVR:", style='Info.TLabel', font=(self.FONT_FAMILY, 8)).grid(row=0, column=1, sticky='w')
        self.player_stats_labels['ovr'] = ttk.Label(stats_frame, text="-", style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 9, 'bold'))
        self.player_stats_labels['ovr'].grid(row=1, column=1, sticky='w')
        
        ttk.Label(stats_frame, text="Salary:", style='Info.TLabel', font=(self.FONT_FAMILY, 8)).grid(row=0, column=2, sticky='w')
        self.player_stats_labels['salary'] = ttk.Label(stats_frame, text="-", style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 9, 'bold'))
        self.player_stats_labels['salary'].grid(row=1, column=2, sticky='w')
        
        # Row 2: Performance stats
        ttk.Label(stats_frame, text="Goals:", style='Info.TLabel', font=(self.FONT_FAMILY, 8)).grid(row=2, column=0, sticky='w', pady=(5,0))
        self.player_stats_labels['goals'] = ttk.Label(stats_frame, text="-", style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 9, 'bold'))
        self.player_stats_labels['goals'].grid(row=3, column=0, sticky='w')
        
        ttk.Label(stats_frame, text="Assists:", style='Info.TLabel', font=(self.FONT_FAMILY, 8)).grid(row=2, column=1, sticky='w', pady=(5,0))
        self.player_stats_labels['assists'] = ttk.Label(stats_frame, text="-", style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 9, 'bold'))
        self.player_stats_labels['assists'].grid(row=3, column=1, sticky='w')
        
        ttk.Label(stats_frame, text="Points:", style='Info.TLabel', font=(self.FONT_FAMILY, 8)).grid(row=2, column=2, sticky='w', pady=(5,0))
        self.player_stats_labels['points'] = ttk.Label(stats_frame, text="-", style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 9, 'bold'))
        self.player_stats_labels['points'].grid(row=3, column=2, sticky='w')
        
        # Action buttons in a compact layout
        action_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        action_frame.pack(fill='x', pady=(8, 0))
        
        # Configure button frame
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)
        
        self.view_profile_btn = ttk.Button(action_frame, text="View Profile", 
                                         command=self.view_player_profile,
                                         style='Compact.TButton')
        self.view_profile_btn.grid(row=0, column=0, sticky='ew', padx=(0, 2))
        
        self.change_focus_btn = ttk.Button(action_frame, text="Change Focus", 
                                         command=self.change_player_focus,
                                         style='Compact.TButton')
        self.change_focus_btn.grid(row=0, column=1, sticky='ew', padx=(2, 0))
        
    def _create_enhanced_inbox_summary_panel(self, parent):
        """Enhanced inbox summary panel optimized for narrow column."""
        panel = self._create_panel(parent, "📧 Messages", 0, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=6)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=3, pady=3)
        
        # Quick stats at top
        stats_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        stats_frame.pack(fill='x', pady=(0, 8))
        
        self.inbox_count_label = ttk.Label(stats_frame, text="Unread: 0", 
                                         style='PlayerInfo.TLabel', 
                                         font=(self.FONT_FAMILY, 10, 'bold'))
        self.inbox_count_label.pack()
        
        self.urgent_count_label = ttk.Label(stats_frame, text="Urgent: 0", 
                                          style='Info.TLabel', 
                                          font=(self.FONT_FAMILY, 9))
        self.urgent_count_label.pack()
        
        # Recent messages preview (compact)
        messages_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        messages_frame.pack(fill='both', expand=True, pady=(0, 8))
        
        self.recent_preview_text = tk.Text(messages_frame, height=6, width=20,
                                         bg=self.CONTENT_BG, fg=self.TEXT_COLOR,
                                         font=(self.FONT_FAMILY, 8), wrap='word',
                                         state='disabled', relief='flat', 
                                         borderwidth=0, cursor='arrow')
        self.recent_preview_text.pack(fill='both', expand=True)
        
        # Action button
        action_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        action_frame.pack(fill='x')
        
        self.inbox_btn = ttk.Button(action_frame, text="Open Inbox", 
                                  command=self.open_inbox_window,
                                  style='Compact.TButton')
        self.inbox_btn.pack(fill='x')
        
    def _create_enhanced_team_finances_panel(self, parent):
        """Enhanced team finances panel with more detailed information and better space usage."""
        panel = self._create_panel(parent, "💰 Financial Overview", 1, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=8)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Cap space - prominent display
        cap_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        cap_frame.pack(fill='x', pady=(0, 8))
        
        self.cap_space_main_label = ttk.Label(cap_frame, text="Cap Space: Loading...", 
                                            style='PlayerInfo.TLabel', 
                                            font=(self.FONT_FAMILY, 12, 'bold'))
        self.cap_space_main_label.pack()
        
        # Financial details in grid
        details_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        details_frame.pack(fill='x', pady=(0, 8))
        
        # Configure grid
        for i in range(2):
            details_frame.grid_columnconfigure(i, weight=1)
        
        # Current payroll
        ttk.Label(details_frame, text="Current Payroll:", style='Info.TLabel', 
                 font=(self.FONT_FAMILY, 8)).grid(row=0, column=0, sticky='w')
        self.payroll_value_label = ttk.Label(details_frame, text="$0", style='PlayerInfo.TLabel', 
                                           font=(self.FONT_FAMILY, 9, 'bold'))
        self.payroll_value_label.grid(row=1, column=0, sticky='w')
        
        # Salary cap
        ttk.Label(details_frame, text="Salary Cap:", style='Info.TLabel', 
                 font=(self.FONT_FAMILY, 8)).grid(row=0, column=1, sticky='w')
        self.cap_value_label = ttk.Label(details_frame, text="$83.5M", style='PlayerInfo.TLabel', 
                                       font=(self.FONT_FAMILY, 9, 'bold'))
        self.cap_value_label.grid(row=1, column=1, sticky='w')
        
        # Players counts
        ttk.Label(details_frame, text="NHL Roster:", style='Info.TLabel', 
                 font=(self.FONT_FAMILY, 8)).grid(row=2, column=0, sticky='w', pady=(5,0))
        self.nhl_count_label = ttk.Label(details_frame, text="0/23", style='PlayerInfo.TLabel', 
                                       font=(self.FONT_FAMILY, 9, 'bold'))
        self.nhl_count_label.grid(row=3, column=0, sticky='w')
        
        # Contracts expiring
        ttk.Label(details_frame, text="Expiring (2025):", style='Info.TLabel', 
                 font=(self.FONT_FAMILY, 8)).grid(row=2, column=1, sticky='w', pady=(5,0))
        self.expiring_count_label = ttk.Label(details_frame, text="0", style='PlayerInfo.TLabel', 
                                            font=(self.FONT_FAMILY, 9, 'bold'))
        self.expiring_count_label.grid(row=3, column=1, sticky='w')
        
        # Quick action button
        action_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        action_frame.pack(fill='x', pady=(8, 0))
        
        self.finances_btn = ttk.Button(action_frame, text="View Full Finances", 
                                     command=self.open_finances_window,
                                     style='Compact.TButton')
        self.finances_btn.pack(fill='x')
        
    def _create_enhanced_top_lines_panel(self, parent):
        """Enhanced top lines panel with line chemistry info."""
        panel = self._create_panel(parent, "🏒 Current Lines", 3, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=8)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        self.top_lines_frame = content_frame
        self.top_lines_label = ttk.Label(content_frame, text="Loading lines...", 
                                       justify="left", font=(self.FONT_FAMILY, 9))
        self.top_lines_label.pack(anchor='w')
        
    def _create_enhanced_quick_stats_panel(self, parent):
        """Create a compact quick stats panel with essential team information."""
        panel = self._create_panel(parent, "⚡ Quick Stats", 1, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=8)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Team record and standings position
        record_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        record_frame.pack(fill='x', pady=(0, 5))
        
        self.quick_record_label = ttk.Label(record_frame, text="0-0-0", 
                                          style='PlayerInfo.TLabel', 
                                          font=(self.FONT_FAMILY, 12, 'bold'))
        self.quick_record_label.pack()
        
        self.quick_standing_label = ttk.Label(record_frame, text="Position: -", 
                                            style='Info.TLabel', 
                                            font=(self.FONT_FAMILY, 9))
        self.quick_standing_label.pack()
        
        # Separator line
        separator = ttk.Separator(content_frame, orient='horizontal')
        separator.pack(fill='x', pady=5)
        
        # Top performers (compact)
        leaders_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        leaders_frame.pack(fill='x', pady=(0, 5))
        
        ttk.Label(leaders_frame, text="Team Leaders", 
                 style='Info.TLabel', font=(self.FONT_FAMILY, 9, 'bold')).pack()
        
        self.quick_leaders_label = ttk.Label(leaders_frame, text="G: Loading...\nA: Loading...\nP: Loading...", 
                                           justify="left", font=(self.FONT_FAMILY, 8))
        self.quick_leaders_label.pack(anchor='w')
        
        # Separator line
        separator2 = ttk.Separator(content_frame, orient='horizontal')
        separator2.pack(fill='x', pady=5)
        
        # Recent form and streak
        form_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        form_frame.pack(fill='x')
        
        ttk.Label(form_frame, text="Recent Form", 
                 style='Info.TLabel', font=(self.FONT_FAMILY, 9, 'bold')).pack()
        
        self.quick_form_label = ttk.Label(form_frame, text="Last 5: -----", 
                                        style='Info.TLabel', font=(self.FONT_FAMILY, 8))
        self.quick_form_label.pack()
        
        self.quick_streak_label = ttk.Label(form_frame, text="Current: None", 
                                          style='Info.TLabel', font=(self.FONT_FAMILY, 8))
        self.quick_streak_label.pack()

    def _create_enhanced_team_leaders_panel(self, parent):
        """Enhanced team leaders panel with more statistics."""
        panel = self._create_panel(parent, "🏆 Team Leaders", 0, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=8)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Create tabs for different stats
        notebook = ttk.Notebook(content_frame)
        notebook.pack(fill='both', expand=True)
        
        # Scoring leaders
        scoring_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(scoring_frame, text='Scoring')
        
        self.team_leaders_label = ttk.Label(scoring_frame, text="G: (0)\nA: (0)\nP: (0)", 
                                          justify="left", font=(self.FONT_FAMILY, 10))
        self.team_leaders_label.pack(anchor='w', padx=5, pady=5)
        
        # Goalie stats
        goalie_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(goalie_frame, text='Goalies')
        
        self.goalie_stats_label = ttk.Label(goalie_frame, text="Loading goalie stats...", 
                                          justify="left", font=(self.FONT_FAMILY, 10))
        self.goalie_stats_label.pack(anchor='w', padx=5, pady=5)
        
    def _create_enhanced_schedule_panel(self, parent):
        """Enhanced schedule panel with better game information."""
        panel = self._create_panel(parent, "Schedule", 1, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=5)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Enhanced columns with more info
        columns = {
            'date': ('Date', 80),
            'opponent': ('Opponent', 120), 
            'location': ('Location', 60),
            'result': ('Result', 70)
        }
        
        self.schedule_tree = ttk.Treeview(content_frame, columns=list(columns.keys()), 
                                        show='headings', height=12)
        
        for col, (text, width) in columns.items():
            self.schedule_tree.heading(col, text=text)
            self.schedule_tree.column(col, width=width, anchor='center')
            
        # Scrollbar
        schedule_scrollbar = ttk.Scrollbar(content_frame, orient='vertical', 
                                         command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=schedule_scrollbar.set)
        
        self.schedule_tree.pack(side='left', fill='both', expand=True)
        schedule_scrollbar.pack(side='right', fill='y')
        
        # Bind events
        self.schedule_tree.bind('<Double-Button-1>', self._on_schedule_double_click)
        
    def _create_enhanced_standings_panel(self, parent):
        """Enhanced standings panel with more detailed standings."""
        panel = self._create_panel(parent, "🏆 League Standings", 2, 0)
        
        content_frame = ttk.Frame(panel, style='Panel.TFrame', padding=5)
        content_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Enhanced columns
        columns = {
            'team': ('Team', 140),
            'w': ('W', 35),
            'l': ('L', 35), 
            'otl': ('OT', 35),
            'pts': ('Pts', 45),
            'streak': ('Streak', 50)
        }
        
        self.standings_tree = ttk.Treeview(content_frame, columns=list(columns.keys()), 
                                         show='headings', height=10)
        
        for col, (text, width) in columns.items():
            self.standings_tree.heading(col, text=text)
            self.standings_tree.column(col, width=width, anchor='center')
        
        # Configure tags for styling
        self.standings_tree.tag_configure('user_team', background='#404040', foreground='#FFD700')
        self.standings_tree.tag_configure('division_header', background='#2E2E2E', foreground='#FFFFFF', 
                                        font=('Arial', 10, 'bold'))
            
        # Scrollbar
        standings_scrollbar = ttk.Scrollbar(content_frame, orient='vertical', 
                                          command=self.standings_tree.yview)
        self.standings_tree.configure(yscrollcommand=standings_scrollbar.set)
        
        self.standings_tree.pack(side='left', fill='both', expand=True)
        standings_scrollbar.pack(side='right', fill='y')

    def view_player_profile(self):
        """Open the selected focus player's profile."""
        if hasattr(self, 'current_focus_player') and self.current_focus_player:
            self.open_player_profile(self.current_focus_player)
        else:
            messagebox.showinfo("No Player", "No player currently in focus.")
    
    def change_player_focus(self):
        """Allow user to select a different player to focus on."""
        if not self.user_team.roster:
            messagebox.showinfo("No Players", "No players available on the roster.")
            return
            
        # Create selection dialog
        selection_window = tk.Toplevel(self)
        selection_window.title("Select Player Focus")
        selection_window.configure(background=self.BG_COLOR)
        selection_window.geometry("400x500")
        selection_window.transient(self)
        selection_window.grab_set()
        
        # Create player list
        ttk.Label(selection_window, text="Select a player to focus on:", 
                 style='Header.TLabel').pack(pady=10)
        
        listbox_frame = ttk.Frame(selection_window, style='Panel.TFrame')
        listbox_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        listbox = tk.Listbox(listbox_frame, bg=self.CONTENT_BG, fg=self.TEXT_COLOR, 
                           font=(self.FONT_FAMILY, 10), selectbackground=self.ACCENT_COLOR)
        scrollbar = ttk.Scrollbar(listbox_frame, orient='vertical', command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Populate with roster players
        for player in sorted(self.user_team.roster, key=lambda p: p.overall_rating(), reverse=True):
            display_text = f"{player.full_name} ({player.overall_rating()} OVR)"
            listbox.insert(tk.END, display_text)
        
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons
        button_frame = ttk.Frame(selection_window, style='Panel.TFrame')
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def select_player():
            selection = listbox.curselection()
            if selection:
                selected_player = sorted(self.user_team.roster, key=lambda p: p.overall_rating(), reverse=True)[selection[0]]
                self.current_focus_player = selected_player
                self.update_enhanced_player_focus_panel()
                selection_window.destroy()
        
        def cancel_selection():
            selection_window.destroy()
        
        ttk.Button(button_frame, text="Select", command=select_player).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_selection).pack(side='left', padx=5)

    def update_all_views(self):
        """Update all views with current data"""
        # Update the modern dashboard instead of legacy UI elements
        if hasattr(self, 'dashboard') and self.dashboard:
            current_date = self.current_date.strftime("%a, %b %d, %Y") if hasattr(self, 'current_date') else "Season Start"
            
            # Get team record
            record = self.league.standings.get(self.user_team.team_name, {'W': 0, 'L': 0, 'OTL': 0}) if hasattr(self, 'league') else {'W': 0, 'L': 0, 'OTL': 0}
            team_record = f"{record['W']}-{record['L']}-{record['OTL']}"
            
            self.dashboard.update_data(
                current_date=current_date,
                team_record=team_record,
                next_game=self._get_next_game_info(),
                roster_highlights=self._get_roster_highlights(),
                recent_news=self._get_recent_news()
            )
        
        # Schedule other updates asynchronously to prevent blocking
        self.after_idle(self._update_heavy_panels)
        
    def _update_heavy_panels(self):
        """Update computationally heavy panels asynchronously"""
        try:
            # Update enhanced panels with new layout
            self.update_enhanced_schedule_panel()
            self.update_enhanced_standings_panel()
            self.update_enhanced_finances_panel()
            self.update_enhanced_inbox_panel()
            self.update_enhanced_player_focus_panel()
            self.update_enhanced_quick_stats_panel()
            self.update_inbox_notification()  # Update inbox button
            
            # Update other open windows
            for window in self.open_windows.values():
                if window.winfo_exists() and hasattr(window, 'update_views'):
                    window.update_views()
        except Exception as e:
            print(f"Error updating heavy panels: {e}")
                
    def _generate_daily_emails(self):
        """Generate daily emails based on game events and random occurrences."""
        from game_classes import EmailGenerator
        import random
        
        # 1. Check for player injuries and generate injury reports (only for actual injuries)
        for player in self.user_team.roster + getattr(self.user_team, 'ahl_roster', []):
            if hasattr(player, 'is_injured') and player.is_injured:
                # Random chance to get injury update for actually injured players
                if random.random() < 0.3:  # 30% chance per day
                    injury_types = ["Upper body injury", "Lower body injury", "Day-to-day", "Concussion protocol"]
                    injury_email = EmailGenerator.create_injury_report_email(
                        player.full_name,
                        random.choice(injury_types),
                        f"{random.randint(1, 4)} weeks"
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
                if player.overall_rating() >= 48:
                    demand_range = "$8-12M per year"
                    years = "8 years"
                elif player.overall_rating() >= 44:
                    demand_range = "$5-8M per year" 
                    years = "6 years"
                elif player.overall_rating() >= 40:
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
        if self.current_date.month == 3:  # March - trade deadline season
            trade_deadline = date(self.current_date.year, 3, 8)
            days_to_deadline = (trade_deadline - self.current_date).days
            if 0 <= days_to_deadline <= 7 and random.random() < 0.5:
                deadline_email = EmailGenerator.create_league_announcement_email(
                    f"Trade Deadline Alert - {days_to_deadline} Days Remaining",
                    f"The NHL trade deadline is in {days_to_deadline} days. All trades must be completed by 3:00 PM EST on March 8th.\n\n"
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
        
        # 3. Injury reports from game (if any occurred)
        # Note: This would need actual injury tracking in the simulation
        if random.random() < 0.05:  # 5% chance of injury report after game
            roster_players = [p for p in self.user_team.roster if random.random() < 0.1]  # Random subset
            if roster_players:
                player = random.choice(roster_players)
                injury_email = EmailGenerator.create_injury_report_email(
                    player.full_name,
                    "Game-related injury - evaluation in progress",
                    "Day-to-day"
                )
                injury_email.is_urgent = True
                self.send_email_to_user(injury_email)
    
    def _show_email_notification(self, message):
        """Show a popup notification for urgent emails."""
        notification_window = tk.Toplevel(self)
        notification_window.title("New Email")
        notification_window.geometry("400x200")
        notification_window.configure(background=self.BG_COLOR)
        notification_window.resizable(False, False)
        
        # Center the window
        notification_window.transient(self)
        notification_window.grab_set()
        
        # Content frame
        content_frame = ttk.Frame(notification_window, style='Panel.TFrame', padding=20)
        content_frame.pack(fill='both', expand=True)
        
        # Icon and title
        title_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        title_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(title_frame, text="📧", font=(self.FONT_FAMILY, 24)).pack(side='left')
        ttk.Label(title_frame, text="Urgent Email Received", 
                 style='Header.TLabel', font=(self.FONT_FAMILY, 14, 'bold')).pack(side='left', padx=(10, 0))
        
        # Message details
        ttk.Label(content_frame, text=f"From: {message.sender}", 
                 style='PlayerInfo.TLabel').pack(anchor='w', pady=2)
        ttk.Label(content_frame, text=f"Subject: {message.subject}", 
                 style='PlayerInfo.TLabel', font=(self.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=2)
        
        # Buttons
        button_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        button_frame.pack(fill='x', pady=(20, 0))
        
        def open_inbox():
            notification_window.destroy()
            self.open_inbox_window()
        
        def dismiss():
            notification_window.destroy()
        
        ttk.Button(button_frame, text="Open Inbox", command=open_inbox, 
                 style='TButton').pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Dismiss", command=dismiss, 
                 style='TButton').pack(side='right')

    def update_schedule_panel(self):
        self.schedule_tree.delete(*self.schedule_tree.get_children())
        
        # Show past games (last 5) and future games (next 5)
        user_games = []
        for game_date, home, away in self.league.schedule:
            if self.user_team in (home, away):
                user_games.append((game_date, home, away))
        
        # Sort by date
        user_games.sort(key=lambda x: x[0])
        
        # Get games around current date
        past_games = [g for g in user_games if g[0] < self.current_date][-5:]
        future_games = [g for g in user_games if g[0] >= self.current_date][:5]
        
        # Add past games
        for game_date, home, away in past_games:
            opponent = away.team_name if self.user_team == home else f"@ {home.team_name}"
            
            # Find game result
            result = ""
            for game_result in self.game_results:
                if (game_result['date'] == game_date and 
                    game_result['home_team'] == home and 
                    game_result['away_team'] == away):
                    # Show score from user team perspective (user score first)
                    if self.user_team == home:
                        user_score = game_result['home_score']
                        opp_score = game_result['away_score']
                    else:
                        user_score = game_result['away_score']
                        opp_score = game_result['home_score']
                    
                    if game_result['winner'] == self.user_team:
                        result = f"W {user_score}-{opp_score}"
                    else:
                        result = f"L {user_score}-{opp_score}"
                    break
            
            # If no result found, check if this is because the game hasn't been simulated yet
            if not result:
                # This was a past game but no result was stored - mark as missing data
                result = "N/A"
            
            item_id = self.schedule_tree.insert('', 'end', values=(
                game_date.strftime("%b %d"), 
                opponent, 
                result
            ), tags=('past_game',))
            
        # Add future games
        for game_date, home, away in future_games:
            opponent = away.team_name if self.user_team == home else f"@ {home.team_name}"
            self.schedule_tree.insert('', 'end', values=(
                game_date.strftime("%b %d"), 
                opponent, 
                ""
            ), tags=('future_game',))
        
        # Configure tags for visual distinction
        self.schedule_tree.tag_configure('past_game', background='#2a2a2a')
        self.schedule_tree.tag_configure('future_game', background='#1a1a1a')

    def update_standings_panel(self):
        self.standings_tree.delete(*self.standings_tree.get_children())
        div_teams = [t for t in self.league.teams if t.division == self.user_team.division]
        sorted_teams = sorted(div_teams, key=lambda t: self.league.standings.get(t.team_name, {'Points': 0})['Points'], reverse=True)
        for team in sorted_teams:
            pts = self.league.standings.get(team.team_name, {'Points': 0})['Points']
            self.standings_tree.insert('', 'end', values=(team.team_name, pts))

    def update_finances_panel(self):
        finance_text = (
            f"{'Player Budget:':<18}${PLAYER_BUDGET:,}\n"
            f"{'Salary Cap:':<18}${SALARY_CAP:,}\n"
            f"{'Total Salaries:':<18}${self.user_team.payroll:,}\n"
            f"{'Cap Space:':<18}${self.user_team.cap_space:,}"
        )
        self.finance_label.config(text=finance_text)
        
    def update_team_leaders_panel(self):
        roster = self.user_team.roster
        if not roster: return
        
        top_goal_scorer = max(roster, key=lambda p: p.stats.goals)
        top_assist_man = max(roster, key=lambda p: p.stats.assists)
        top_point_getter = max(roster, key=lambda p: p.stats.points)

        leaders_text = (
            f"G: {top_goal_scorer.last_name} ({top_goal_scorer.stats.goals})\n"
            f"A: {top_assist_man.last_name} ({top_assist_man.stats.assists})\n"
            f"P: {top_point_getter.last_name} ({top_point_getter.stats.points})"
        )
        self.team_leaders_label.config(text=leaders_text)

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

    def _on_schedule_double_click(self, event):
        """Handle double-click on schedule item to view game results"""
        selection = self.schedule_tree.selection()
        if not selection:
            return
            
        item = self.schedule_tree.item(selection[0])
        tags = self.schedule_tree.item(selection[0], 'tags')
        
        # Only show results for past games
        if 'past_game' not in tags:
            return
            
        # Get the game date and find the corresponding game result
        date_str = item['values'][0]  # "Nov 15" format
        opponent_str = item['values'][1]  # "Team Name" or "@ Team Name"
        
        # Find the game result
        for game_result in self.game_results:
            game_date = game_result['date']
            if game_date.strftime("%b %d") == date_str:
                # Check if this is the right opponent
                if self.user_team == game_result['home_team']:
                    expected_opponent = game_result['away_team'].team_name
                else:
                    expected_opponent = f"@ {game_result['home_team'].team_name}"
                    
                if opponent_str == expected_opponent:
                    self._show_game_results_window(game_result)
                    break

    def _show_game_results_window(self, game_result):
        """Show comprehensive professional game results window"""
        if 'game_results' in self.open_windows and self.open_windows['game_results'].winfo_exists():
            self.open_windows['game_results'].destroy()
            
        window = tk.Toplevel(self)
        window.title(f"Game Results - {game_result['date'].strftime('%B %d, %Y')}")
        window.geometry("1200x800")
        window.configure(bg=self.BG_COLOR)
        window.resizable(True, True)
        self.open_windows['game_results'] = window
        
        # Main container with custom styling
        main_container = tk.Frame(window, bg=self.BG_COLOR)
        main_container.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header section with enhanced design
        header_frame = tk.Frame(main_container, bg=self.TITLE_BAR_COLOR, relief='solid', bd=1)
        header_frame.pack(fill='x', pady=(0, 15))
        
        home_team = game_result['home_team']
        away_team = game_result['away_team']
        home_score = game_result['home_score']
        away_score = game_result['away_score']
        
        # Team vs Team header
        team_vs_frame = tk.Frame(header_frame, bg=self.TITLE_BAR_COLOR)
        team_vs_frame.pack(fill='x', pady=20, padx=20)
        
        # Away team info
        away_frame = tk.Frame(team_vs_frame, bg=self.TITLE_BAR_COLOR)
        away_frame.pack(side='left', fill='both', expand=True)
        
        away_name_label = tk.Label(away_frame, text=away_team.team_name, 
                                  font=('Segoe UI', 18, 'bold'), fg=self.HEADER_COLOR, bg=self.TITLE_BAR_COLOR)
        away_name_label.pack(anchor='center')
        
        away_score_label = tk.Label(away_frame, text=str(away_score), 
                                   font=('Segoe UI', 36, 'bold'), fg=self.ACCENT_COLOR, bg=self.TITLE_BAR_COLOR)
        away_score_label.pack(anchor='center')
        
        # VS separator
        vs_label = tk.Label(team_vs_frame, text="VS", 
                           font=('Segoe UI', 14, 'bold'), fg=self.TEXT_COLOR, bg=self.TITLE_BAR_COLOR)
        vs_label.pack(side='left', padx=30, fill='y')
        
        # Home team info
        home_frame = tk.Frame(team_vs_frame, bg=self.TITLE_BAR_COLOR)
        home_frame.pack(side='right', fill='both', expand=True)
        
        home_name_label = tk.Label(home_frame, text=home_team.team_name, 
                                  font=('Segoe UI', 18, 'bold'), fg=self.HEADER_COLOR, bg=self.TITLE_BAR_COLOR)
        home_name_label.pack(anchor='center')
        
        home_score_label = tk.Label(home_frame, text=str(home_score), 
                                   font=('Segoe UI', 36, 'bold'), fg=self.ACCENT_COLOR, bg=self.TITLE_BAR_COLOR)
        home_score_label.pack(anchor='center')
        
        # Game result indicator
        if game_result['winner'] == self.user_team:
            result_text = "🏆 VICTORY"
            result_color = '#4CAF50'
        else:
            result_text = "😞 DEFEAT"
            result_color = '#F44336'
            
        result_label = tk.Label(header_frame, text=result_text, 
                               font=('Segoe UI', 14, 'bold'), fg=result_color, bg=self.TITLE_BAR_COLOR)
        result_label.pack(pady=(0, 10))
        
        # Enhanced notebook with better styling
        style = ttk.Style()
        style.configure('GameResults.TNotebook', background=self.BG_COLOR, borderwidth=0)
        style.configure('GameResults.TNotebook.Tab', padding=[20, 10], font=('Segoe UI', 10))
        
        notebook = ttk.Notebook(main_container, style='GameResults.TNotebook')
        notebook.pack(fill='both', expand=True)
        
        # 1. GAME SUMMARY TAB
        summary_frame = self._create_summary_tab(notebook, game_result)
        notebook.add(summary_frame, text="📋 Game Summary")
        
        # 2. SCORING TAB  
        scoring_frame = self._create_scoring_tab(notebook, game_result)
        notebook.add(scoring_frame, text="🥅 Scoring")
        
        # 3. PLAYER STATS TAB
        stats_frame = self._create_player_stats_tab(notebook, game_result)
        notebook.add(stats_frame, text="📊 Player Stats")
        
        # 4. TEAM STATS TAB
        team_stats_frame = self._create_team_stats_tab(notebook, game_result)
        notebook.add(team_stats_frame, text="🏒 Team Stats")
        
        # 5. GAME VIEWER TAB (if event log exists)
        if 'event_log' in game_result and game_result['event_log']:
            viewer_frame = self._create_game_viewer_tab(notebook, game_result)
            notebook.add(viewer_frame, text="🎮 Game Viewer")
        
        # Bottom action bar
        action_frame = tk.Frame(main_container, bg=self.BG_COLOR)
        action_frame.pack(fill='x', pady=(15, 0))
        
        # Launch EHM game viewer button - check settings for game viewer
        settings = self.get_settings()
        use_game_viewer = settings.get('simulation', {}).get('use_game_viewer', False)
        if use_game_viewer and 'event_log' in game_result and game_result['event_log']:
            viewer_btn = tk.Button(action_frame, text="� Launch EHM Game Viewer", 
                                  font=('Segoe UI', 10, 'bold'), bg=self.ACCENT_COLOR, fg='white',
                                  activebackground=self.ACCENT_ACTIVE, relief='flat', padx=20, pady=8,
                                  command=lambda: self._launch_ehm_replay_viewer(game_result))
            viewer_btn.pack(side='left')
        
        # Close button
        close_btn = tk.Button(action_frame, text="Close", 
                             font=('Segoe UI', 10), bg=self.CONTENT_BG, fg=self.TEXT_COLOR,
                             activebackground='#333333', relief='flat', padx=20, pady=8,
                             command=window.destroy)
        close_btn.pack(side='right')

    def _create_summary_tab(self, parent, game_result):
        """Create comprehensive game summary tab"""
        frame = tk.Frame(parent, bg=self.CONTENT_BG)
        
        # Scrollable content
        canvas = tk.Canvas(frame, bg=self.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.CONTENT_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Game information section
        info_section = tk.LabelFrame(scrollable_frame, text="Game Information", 
                                    font=('Segoe UI', 12, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        info_section.pack(fill='x', padx=20, pady=10)
        
        info_text = f"Date: {game_result['date'].strftime('%A, %B %d, %Y')}\n"
        info_text += f"Venue: {game_result['home_team'].team_name} Home Arena\n"
        info_text += f"Final Score: {game_result['away_team'].team_name} {game_result['away_score']} - {game_result['home_score']} {game_result['home_team'].team_name}\n"
        
        if game_result.get('overtime', False):
            info_text += "Result: Overtime Victory\n"
        elif game_result.get('shootout', False):
            info_text += "Result: Shootout Victory\n"
        else:
            info_text += "Result: Regulation Victory\n"
            
        info_label = tk.Label(info_section, text=info_text, font=('Segoe UI', 10), 
                             fg=self.TEXT_COLOR, bg=self.CONTENT_BG, justify='left')
        info_label.pack(anchor='w', padx=10, pady=10)
        
        # Key moments section
        moments_section = tk.LabelFrame(scrollable_frame, text="Key Moments", 
                                       font=('Segoe UI', 12, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        moments_section.pack(fill='x', padx=20, pady=10)
        
        moments_text = tk.Text(moments_section, height=8, wrap='word', font=('Segoe UI', 9),
                              bg='#2A2A2A', fg=self.TEXT_COLOR, relief='flat')
        moments_scroll = ttk.Scrollbar(moments_section, orient='vertical', command=moments_text.yview)
        moments_text.configure(yscrollcommand=moments_scroll.set)
        
        # Add key events
        key_events = []
        for event in game_result.get('notable_events', []):
            if event['event'] in ['Goal', 'Penalty', 'Save']:
                period_text = f"P{event['period']}" if event['period'] <= 3 else "OT" if event['period'] == 4 else "SO"
                time_text = f"{event['time']//60:02d}:{event['time']%60:02d}"
                player_name = event['player'].full_name if hasattr(event['player'], 'full_name') else "Unknown"
                key_events.append(f"[{period_text} {time_text}] {event['event']}: {player_name} ({event['team']})")
        
        if key_events:
            moments_text.insert('end', '\n'.join(key_events))
        else:
            moments_text.insert('end', "No key events recorded for this game.")
            
        moments_text.config(state='disabled')
        moments_text.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        moments_scroll.pack(side='right', fill='y', pady=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return frame

    def _create_scoring_tab(self, parent, game_result):
        """Create detailed scoring breakdown tab"""
        frame = tk.Frame(parent, bg=self.CONTENT_BG)
        
        # Goals by period
        period_frame = tk.LabelFrame(frame, text="Goals by Period", 
                                    font=('Segoe UI', 12, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        period_frame.pack(fill='x', padx=20, pady=10)
        
        # Create period breakdown table
        periods_table = ttk.Treeview(period_frame, columns=('team', 'p1', 'p2', 'p3', 'ot', 'total'), 
                                    show='headings', height=3)
        
        periods_table.heading('team', text='Team')
        periods_table.heading('p1', text='1st')
        periods_table.heading('p2', text='2nd') 
        periods_table.heading('p3', text='3rd')
        periods_table.heading('ot', text='OT/SO')
        periods_table.heading('total', text='Total')
        
        for col in ('team', 'p1', 'p2', 'p3', 'ot', 'total'):
            periods_table.column(col, width=80, anchor='center')
        
        # Calculate goals by period
        def count_period_goals(team_name, period):
            return sum(1 for event in game_result.get('notable_events', [])
                      if event['event'] == 'Goal' and event['team'] == team_name and event['period'] == period)
        
        # Away team row
        away_goals = [
            count_period_goals(game_result['away_team'].team_name, 1),
            count_period_goals(game_result['away_team'].team_name, 2),
            count_period_goals(game_result['away_team'].team_name, 3),
            count_period_goals(game_result['away_team'].team_name, 4) + count_period_goals(game_result['away_team'].team_name, 5)
        ]
        
        periods_table.insert('', 'end', values=(
            game_result['away_team'].team_name,
            away_goals[0], away_goals[1], away_goals[2], away_goals[3],
            game_result['away_score']
        ))
        
        # Home team row
        home_goals = [
            count_period_goals(game_result['home_team'].team_name, 1),
            count_period_goals(game_result['home_team'].team_name, 2),
            count_period_goals(game_result['home_team'].team_name, 3),
            count_period_goals(game_result['home_team'].team_name, 4) + count_period_goals(game_result['home_team'].team_name, 5)
        ]
        
        periods_table.insert('', 'end', values=(
            game_result['home_team'].team_name,
            home_goals[0], home_goals[1], home_goals[2], home_goals[3],
            game_result['home_score']
        ))
        
        periods_table.pack(fill='x', padx=10, pady=10)
        
        # Detailed goal list
        goals_frame = tk.LabelFrame(frame, text="Goal Details", 
                                   font=('Segoe UI', 12, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        goals_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        goals_tree = ttk.Treeview(goals_frame, columns=('time', 'period', 'team', 'scorer'), 
                                 show='headings', height=10)
        
        goals_tree.heading('time', text='Time')
        goals_tree.heading('period', text='Period')
        goals_tree.heading('team', text='Team')
        goals_tree.heading('scorer', text='Goal Scorer')
        
        for col in ('time', 'period', 'team', 'scorer'):
            goals_tree.column(col, width=150, anchor='center')
        
        goals_scroll = ttk.Scrollbar(goals_frame, orient='vertical', command=goals_tree.yview)
        goals_tree.configure(yscrollcommand=goals_scroll.set)
        
        # Add goals to tree
        goal_events = [event for event in game_result.get('notable_events', []) if event['event'] == 'Goal']
        goal_events.sort(key=lambda x: (x['period'], x['time']))
        
        for event in goal_events:
            period_text = f"Period {event['period']}" if event['period'] <= 3 else "OT" if event['period'] == 4 else "SO"
            time_text = f"{event['time']//60:02d}:{event['time']%60:02d}"
            player_name = event['player'].full_name if hasattr(event['player'], 'full_name') else "Unknown"
            
            goals_tree.insert('', 'end', values=(time_text, period_text, event['team'], player_name))
        
        goals_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        goals_scroll.pack(side='right', fill='y', pady=10)
        
        return frame

    def _create_player_stats_tab(self, parent, game_result):
        """Create comprehensive player statistics tab"""
        frame = tk.Frame(parent, bg=self.CONTENT_BG)
        
        # Team selector
        selector_frame = tk.Frame(frame, bg=self.CONTENT_BG)
        selector_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(selector_frame, text="Select Team:", font=('Segoe UI', 10, 'bold'), 
                fg=self.HEADER_COLOR, bg=self.CONTENT_BG).pack(side='left')
        
        team_var = tk.StringVar(master=self, value=game_result['home_team'].team_name)
        team_combo = ttk.Combobox(selector_frame, textvariable=team_var, 
                                 values=[game_result['home_team'].team_name, game_result['away_team'].team_name],
                                 state='readonly', width=30)
        team_combo.pack(side='left', padx=10)
        
        # Player stats table
        stats_frame = tk.Frame(frame, bg=self.CONTENT_BG)
        stats_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('player', 'pos', 'rating', 'goals', 'assists', 'shots', 'toi', 'fatigue')
        stats_tree = ttk.Treeview(stats_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        column_config = {
            'player': ('Player', 150),
            'pos': ('Pos', 60),
            'rating': ('Rating', 70),
            'goals': ('G', 50),
            'assists': ('A', 50),
            'shots': ('SOG', 50),
            'toi': ('TOI', 70),
            'fatigue': ('Fatigue', 70)
        }
        
        for col, (heading, width) in column_config.items():
            stats_tree.heading(col, text=heading)
            stats_tree.column(col, width=width, anchor='center')
        
        stats_scroll = ttk.Scrollbar(stats_frame, orient='vertical', command=stats_tree.yview)
        stats_tree.configure(yscrollcommand=stats_scroll.set)
        
        def update_player_stats():
            # Clear existing items
            for item in stats_tree.get_children():
                stats_tree.delete(item)
            
            selected_team_name = team_var.get()
            selected_team = game_result['home_team'] if selected_team_name == game_result['home_team'].team_name else game_result['away_team']
            
            # Get player statistics
            player_data = []
            for player in selected_team.roster:
                # Get player stats from game result
                goals = sum(1 for event in game_result.get('notable_events', [])
                           if hasattr(event['player'], 'id') and event['player'].id == player.id and event['event'] == 'Goal')
                
                assists = 0  # Would need assist tracking implementation
                
                shots = sum(1 for event in game_result.get('events', [])
                           if hasattr(event.get('player'), 'id') and event.get('player').id == player.id and event.get('event') == 'Shot')
                
                # Get rating, TOI, and fatigue from player_ratings if available
                rating = game_result.get('player_ratings', {}).get(selected_team_name, {}).get(player.id, 'N/A')
                toi = "N/A"  # Would need TOI tracking
                fatigue = "N/A"  # Would need fatigue tracking
                
                player_data.append((
                    player.full_name,
                    player.primary_position.name if hasattr(player, 'primary_position') and player.primary_position else "N/A",
                    rating,
                    goals,
                    assists,
                    shots,
                    toi,
                    fatigue
                ))
            
            # Sort by goals, then rating
            player_data.sort(key=lambda x: (x[3], x[2] if isinstance(x[2], (int, float)) else 0), reverse=True)
            
            for player_info in player_data:
                stats_tree.insert('', 'end', values=player_info)
        
        # Bind team selection change
        team_combo.bind('<<ComboboxSelected>>', lambda e: update_player_stats())
        
        # Initial population
        update_player_stats()
        
        stats_tree.pack(side='left', fill='both', expand=True)
        stats_scroll.pack(side='right', fill='y')
        
        return frame

    def _create_team_stats_tab(self, parent, game_result):
        """Create team statistics comparison tab"""
        frame = tk.Frame(parent, bg=self.CONTENT_BG)
        
        # Team comparison table
        comparison_frame = tk.LabelFrame(frame, text="Team Statistics Comparison", 
                                        font=('Segoe UI', 12, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        comparison_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        columns = ('stat', 'away_team', 'home_team')
        comparison_tree = ttk.Treeview(comparison_frame, columns=columns, show='headings', height=12)
        
        comparison_tree.heading('stat', text='Statistic')
        comparison_tree.heading('away_team', text=game_result['away_team'].team_name)
        comparison_tree.heading('home_team', text=game_result['home_team'].team_name)
        
        comparison_tree.column('stat', width=200, anchor='w')
        comparison_tree.column('away_team', width=150, anchor='center')
        comparison_tree.column('home_team', width=150, anchor='center')
        
        comparison_scroll = ttk.Scrollbar(comparison_frame, orient='vertical', command=comparison_tree.yview)
        comparison_tree.configure(yscrollcommand=comparison_scroll.set)
        
        # Calculate team statistics
        def calculate_team_stat(team_name, stat_type):
            count = 0
            for event in game_result.get('events', []):
                if event.get('team') == team_name and event.get('event') == stat_type:
                    count += 1
            return count
        
        # Statistical categories
        stats_categories = [
            ('Goals', 'Goal'),
            ('Shots on Goal', 'Shot'),
            ('Penalties', 'Penalty'),
            ('Blocked Shots', 'Shot Blocked'),
            ('Power Play Opportunities', 'Power Play'),
            ('Saves', 'Save')
        ]
        
        for stat_name, event_type in stats_categories:
            away_stat = calculate_team_stat(game_result['away_team'].team_name, event_type)
            home_stat = calculate_team_stat(game_result['home_team'].team_name, event_type)
            
            comparison_tree.insert('', 'end', values=(stat_name, away_stat, home_stat))
        
        # Add final score row
        comparison_tree.insert('', 'end', values=('Final Score', game_result['away_score'], game_result['home_score']), tags=('final_score',))
        
        # Style the final score row
        comparison_tree.tag_configure('final_score', background='#404040', font=('Segoe UI', 10, 'bold'))
        
        comparison_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        comparison_scroll.pack(side='right', fill='y', pady=10)
        
        return frame

    def _create_game_viewer_tab(self, parent, game_result):
        """Create embedded game viewer tab"""
        frame = tk.Frame(parent, bg=self.CONTENT_BG)
        
        # Header
        header_label = tk.Label(frame, text="🎮 Interactive Game Viewer", 
                               font=('Segoe UI', 16, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        header_label.pack(pady=20)
        
        # Info text
        info_text = ("Experience the game through our interactive viewer!\n"
                    "Watch key plays, goals, and game events as they unfold.")
        info_label = tk.Label(frame, text=info_text, font=('Segoe UI', 10), 
                             fg=self.TEXT_COLOR, bg=self.CONTENT_BG, justify='center')
        info_label.pack(pady=10)
        
        # Launch button
        launch_btn = tk.Button(frame, text="🚀 Launch Game Viewer", 
                              font=('Segoe UI', 14, 'bold'), bg=self.ACCENT_COLOR, fg='white',
                              activebackground=self.ACCENT_ACTIVE, relief='flat', padx=40, pady=15,
                              command=lambda: self._launch_standalone_viewer(game_result['event_log']))
        launch_btn.pack(pady=30)
        
        # Event summary
        events_frame = tk.LabelFrame(frame, text="Event Summary", 
                                    font=('Segoe UI', 12, 'bold'), fg=self.HEADER_COLOR, bg=self.CONTENT_BG)
        events_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        events_text = tk.Text(events_frame, height=8, wrap='word', font=('Segoe UI', 9),
                             bg='#2A2A2A', fg=self.TEXT_COLOR, relief='flat', state='disabled')
        events_scroll = ttk.Scrollbar(events_frame, orient='vertical', command=events_text.yview)
        events_text.configure(yscrollcommand=events_scroll.set)
        
        # Populate event summary
        events_text.config(state='normal')
        event_count = len(game_result.get('event_log', []))
        events_text.insert('end', f"Total Events Recorded: {event_count}\n\n")
        
        # Show event type breakdown
        event_types = {}
        for event in game_result.get('event_log', []):
            event_type = event.get('type', 'Unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        events_text.insert('end', "Event Type Breakdown:\n")
        for event_type, count in sorted(event_types.items()):
            events_text.insert('end', f"• {event_type}: {count}\n")
        
        events_text.config(state='disabled')
        events_text.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        events_scroll.pack(side='right', fill='y', pady=10)
        
        return frame

    def _launch_ehm_replay_viewer(self, game_result):
        """Launch the EHM game viewer for replay viewing."""
        try:
            # Use the EHM integration for replay viewing
            from ehm_integration import EHMReplayViewer
            
            # Extract teams and event log from game result
            home_team = game_result.get('home_team')
            away_team = game_result.get('away_team')
            event_log = game_result.get('event_log', [])
            
            if not event_log:
                print("No event log found in game result")
                return
                
            # Launch the EHM replay viewer
            viewer = EHMReplayViewer(self.root, home_team, away_team, event_log)
            
        except Exception as e:
            print(f"Error launching EHM replay viewer: {e}")
            # Fallback to old viewer if needed
            self._launch_standalone_viewer(game_result.get('event_log', []))

    def _launch_standalone_viewer(self, event_log):
        """Launch the standalone game viewer window"""
        try:
            # Determine team names
            home_team_name = "HOME"
            away_team_name = "AWAY"
            
            # Try to get actual team names from recent game results
            if self.game_results:
                recent_game = self.game_results[-1]
                home_team_name = recent_game['home_team'].team_name
                away_team_name = recent_game['away_team'].team_name
            
            launch_game_viewer(event_log, 1200, home_team_name, away_team_name)
        except Exception as e:
            messagebox.showerror("Game Viewer Error", f"Error launching game viewer: {str(e)}")
            print(f"Game viewer error: {e}")
            import traceback
            traceback.print_exc()

    def update_news_panel(self):
        # News panel doesn't exist in the current dashboard layout
        # News is handled through the dedicated news window instead
        pass
        
    def update_player_focus_panel(self):
        if not self.user_team.roster: return
        
        if random.random() < 0.75: 
            focused_player = max(self.user_team.roster, key=lambda p: p.overall_rating())
        else:
            focused_player = random.choice(self.user_team.roster)

        info_text = (
            f"{focused_player.full_name}\n"
            f"{focused_player.primary_position.name}\n"
            f"Age: {focused_player.age}\n"
            f"OVR: {focused_player.overall_rating()}"
        )
        self.player_focus_label.config(text=info_text)

    def update_top_lines_panel(self):
        info = self._get_top_lines_info()
        self.top_lines_label.config(text=info)

    def _get_top_lines_info(self):
        # Defensive: fallback if lineup missing
        lineup = getattr(self.user_team, 'lineup', {})
        forwards = lineup.get('Forwards', [[None]*3 for _ in range(4)])
        defense = lineup.get('Defense', [[None]*2 for _ in range(3)])
        goalies = lineup.get('Goalies', [None, None])

        def player_name(p):
            return p.full_name if p else "—"

        top_fw = forwards[0] if forwards else [None, None, None]
        top_df = defense[0] if defense else [None, None]
        starter_g = goalies[0] if goalies else None

        fw_str = " / ".join(player_name(p) for p in top_fw)
        df_str = " & ".join(player_name(p) for p in top_df)
        g_str = player_name(starter_g)

        return (
            f"Top Forward Line:\n  {fw_str}\n\n"
            f"Top Defense Pair:\n  {df_str}\n\n"
            f"Starting Goaltender:\n  {g_str}"
        )

    def toggle_game_viewer(self):
        """Toggle the game viewer setting and update the button display"""
        # Get current settings
        settings = self.get_settings()
        
        # Toggle the game viewer setting
        current_setting = settings.get('simulation', {}).get('use_game_viewer', False)
        new_setting = not current_setting
        
        print(f"DEBUG: Toggling game viewer from {current_setting} to {new_setting}")
        
        # Update settings
        settings['simulation']['use_game_viewer'] = new_setting
        
        # Save settings to file
        import json
        import os
        settings_file = os.path.join(os.path.dirname(__file__), 'settings.json')
        try:
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            print(f"Game viewer toggled: {'ON' if new_setting else 'OFF'}")
            print(f"DEBUG: Settings saved to file successfully")
        except Exception as e:
            print(f"Error saving game viewer setting: {e}")
        
        # Update button text (menu-bar button was removed; the toggle now
        # lives in GM Options -> Game Presentation)
        if hasattr(self, 'game_viewer_btn'):
            self.game_viewer_btn.config(text=f"🎮 Viewer: {'ON' if new_setting else 'OFF'}")
        print(f"DEBUG: Button text updated to: {'ON' if new_setting else 'OFF'}")

    def _update_game_viewer_button_state(self):
        """Update the game viewer button to show the current setting"""
        if hasattr(self, 'game_viewer_btn'):
            settings = self.get_settings()
            current_setting = settings.get('simulation', {}).get('use_game_viewer', False)
            print(f"DEBUG: Loading game viewer button state: {current_setting}")
            print(f"DEBUG: Full simulation settings: {settings.get('simulation', {})}")
            self.game_viewer_btn.config(text=f"Viewer: {'ON' if current_setting else 'OFF'}")

    def toggle_season_flow_panel(self):
        """Toggle the visibility of the automated season flow panel"""
        if self.season_flow_visible:
            self._hide_season_flow_panel()
        else:
            self._show_season_flow_panel()
            
    def _show_season_flow_panel(self):
        """Show the automated season flow control panel"""
        try:
            if self.season_flow_panel is None:
                # Import here to avoid circular imports
                from season_flow_ui import SeasonFlowControlPanel
                
                # Find the main container to add the panel to
                if hasattr(self, 'main_frame'):
                    # Create a new frame for the season flow panel
                    self.season_flow_container = ttk.Frame(self.main_frame, style='Panel.TFrame')
                    
                    # Pack it at the top, before other content
                    self.season_flow_container.pack(fill='x', padx=10, pady=5, before=self.main_frame.winfo_children()[0] if self.main_frame.winfo_children() else None)
                    
                    # Create the season flow panel
                    self.season_flow_panel = SeasonFlowControlPanel(self.season_flow_container, self)
                    self.season_flow_panel.pack(fill='x', expand=True)
                    
                else:
                    print("Warning: Could not find main_frame for season flow panel")
                    return
                    
            self.season_flow_visible = True
            self.season_flow_btn.config(text="⚡ Hide Flow")
            print("Season flow panel shown")
            
        except ImportError as e:
            print(f"Error importing season flow UI: {e}")
            tk.messagebox.showerror("Error", f"Could not load season flow controls: {e}")
        except Exception as e:
            print(f"Error showing season flow panel: {e}")
            tk.messagebox.showerror("Error", f"Failed to show season flow panel: {e}")
            
    def _hide_season_flow_panel(self):
        """Hide the automated season flow control panel"""
        try:
            if hasattr(self, 'season_flow_container') and self.season_flow_container:
                self.season_flow_container.destroy()
                self.season_flow_container = None
                
            self.season_flow_panel = None
            self.season_flow_visible = False
            self.season_flow_btn.config(text="⚡ Season Flow")
            print("Season flow panel hidden")
            
        except Exception as e:
            print(f"Error hiding season flow panel: {e}")
            
    def get_automation_status(self):
        """Get the current automation status for other components"""
        if self.season_flow_panel and hasattr(self.season_flow_panel, 'automation'):
            return {
                'active': self.season_flow_panel.automation.automation_active,
                'mode': self.season_flow_panel.automation.settings.mode,
                'current_phase': self.season_flow_panel.automation.current_phase
            }
        return {'active': False, 'mode': 'Manual', 'current_phase': 'Regular Season'}

    def open_performance_monitor(self):
        """Open the performance monitoring window"""
        if 'performance_monitor' not in self.open_windows or not self.open_windows['performance_monitor'].winfo_exists():
            from performance_monitor import PerformanceMonitorWindow
            self.open_windows['performance_monitor'] = PerformanceMonitorWindow(self)
        self.open_windows['performance_monitor'].focus_set()
        
    # Enhanced panel update methods
    def update_enhanced_schedule_panel(self):
        """Update the enhanced schedule panel."""
        if hasattr(self, 'schedule_tree'):
            self.schedule_tree.delete(*self.schedule_tree.get_children())
            
            # Show past games (last 5) and future games (next 5)
            user_games = []
            for item in self.league.schedule:
                # Normalize schedule entry (dict or legacy tuple)
                if isinstance(item, dict):
                    game_date, home, away = item.get('date'), item.get('home_team'), item.get('away_team')
                elif isinstance(item, (tuple, list)) and len(item) >= 3:
                    game_date, home, away = item[0], item[1], item[2]
                else:
                    continue
                if game_date is None or home == 'NHL_EVENT':
                    continue
                if self.user_team in (home, away):
                    user_games.append((game_date, home, away))
            
            # Sort by date
            user_games.sort(key=lambda x: x[0])
            
            # Get games around current date
            past_games = [g for g in user_games if g[0] < self.current_date][-5:]
            future_games = [g for g in user_games if g[0] >= self.current_date][:5]
            
            # Add past games
            for game_date, home, away in past_games:
                opponent = away if self.user_team == home else home
                location = "vs" if self.user_team == home else "@"
                result = "W 3-2"  # Placeholder result
                
                self.schedule_tree.insert('', 'end', values=(
                    game_date.strftime("%m/%d"),
                    opponent.team_name,
                    location,
                    result
                ))
            
            # Add future games
            for game_date, home, away in future_games:
                opponent = away if self.user_team == home else home
                location = "vs" if self.user_team == home else "@"
                
                self.schedule_tree.insert('', 'end', values=(
                    game_date.strftime("%m/%d"),
                    opponent.team_name,
                    location,
                    "—"
                ))
                
    def update_enhanced_standings_panel(self):
        """Update the enhanced standings panel with proper NHL divisions."""
        if hasattr(self, 'standings_tree'):
            self.standings_tree.delete(*self.standings_tree.get_children())
            
            # Group teams by conference and division
            eastern_atlantic = []
            eastern_metro = []
            western_central = []
            western_pacific = []
            
            # Sort all teams by points first
            sorted_teams = sorted(self.league.standings.items(), 
                                key=lambda x: x[1]['Points'], reverse=True)
            
            # Group teams by division
            for team_name, record in sorted_teams:
                # Find the team object to get division info
                team_obj = None
                for team in self.league.teams:
                    if team.team_name == team_name:
                        team_obj = team
                        break
                
                if team_obj:
                    if team_obj.conference == "Eastern":
                        if team_obj.division == "Atlantic":
                            eastern_atlantic.append((team_name, record))
                        elif team_obj.division == "Metropolitan":
                            eastern_metro.append((team_name, record))
                    elif team_obj.conference == "Western":
                        if team_obj.division == "Central":
                            western_central.append((team_name, record))
                        elif team_obj.division == "Pacific":
                            western_pacific.append((team_name, record))
            
            # Insert division headers and teams
            divisions = [
                ("EASTERN CONFERENCE", None, None),
                ("Atlantic Division", eastern_atlantic, None),
                ("Metropolitan Division", eastern_metro, None),
                ("", None, None),  # Spacer
                ("WESTERN CONFERENCE", None, None),
                ("Central Division", western_central, None),
                ("Pacific Division", western_pacific, None)
            ]
            
            for div_name, teams, _ in divisions:
                if teams is None:
                    # Insert division header
                    self.standings_tree.insert('', 'end', values=(
                        div_name, "", "", "", "", ""
                    ), tags=['division_header'])
                elif teams:
                    # Insert teams in this division
                    for i, (team_name, record) in enumerate(teams):
                        # Highlight user team
                        tags = ['user_team'] if team_name == self.user_team.team_name else []
                        
                        self.standings_tree.insert('', 'end', values=(
                            f"  {team_name}",
                            record['W'],
                            record['L'],
                            record.get('OTL', 0),
                            record['Points'],
                            "W2"  # Placeholder streak
                        ), tags=tags)
                
    def update_enhanced_finances_panel(self):
        """Update the enhanced finances panel."""
        if hasattr(self, 'finance_label'):
            payroll = self.user_team.payroll
            cap_space = self.user_team.cap_space
            cap_used_pct = (payroll / self.user_team.salary_cap) * 100
            
            finance_info = (
                f"Salary Cap:      ${self.user_team.salary_cap:,}\n"
                f"Payroll:         ${payroll:,}\n"
                f"Cap Space:       ${cap_space:,}\n"
                f"Cap Used:        {cap_used_pct:.1f}%\n\n"
                f"Budget Status:   {'Over Budget' if cap_space < 0 else 'Under Budget'}"
            )
            self.finance_label.config(text=finance_info)
            
    def update_enhanced_inbox_panel(self):
        """Update the enhanced inbox summary panel."""
        if hasattr(self, 'inbox_stats_label') and hasattr(self, 'recent_messages_text'):
            inbox = self.user_team.inbox
            unread_count = inbox.unread_count
            urgent_count = len(inbox.get_urgent_messages())
            
            # Update stats
            self.inbox_stats_label.config(text=f"Unread: {unread_count} | Urgent: {urgent_count}")
            
            # Update recent messages
            self.recent_messages_text.config(state='normal')
            self.recent_messages_text.delete(1.0, tk.END)
            
            recent_messages = inbox.messages[:5]  # Last 5 messages
            for i, message in enumerate(recent_messages):
                status_icon = "📧" if not message.is_read else "📩"
                priority_icon = "🔴" if message.is_urgent else "🟡" if message.is_important else ""
                
                line = f"{status_icon} {priority_icon} {message.sender}: {message.subject[:30]}{'...' if len(message.subject) > 30 else ''}\n"
                self.recent_messages_text.insert(tk.END, line)
                
            if not recent_messages:
                self.recent_messages_text.insert(tk.END, "No messages")
                
            self.recent_messages_text.config(state='disabled')
            
    def update_enhanced_player_focus_panel(self):
        """Update the enhanced player focus panel."""
        if hasattr(self, 'focus_player_name_label') and hasattr(self, 'focus_player_info_label'):
            # Get the current focus player or select the best player
            if hasattr(self, 'current_focus_player') and self.current_focus_player:
                focus_player = self.current_focus_player
            elif self.user_team.roster:
                focus_player = max(self.user_team.roster, key=lambda p: p.overall_rating())
                self.current_focus_player = focus_player
            else:
                # No players available
                self.focus_player_name_label.config(text="No Player Selected")
                self.focus_player_info_label.config(text="No players available on roster")
                return
            
            # Update player name
            self.focus_player_name_label.config(text=focus_player.full_name)
            
            # Update player info
            contract_info = f"${focus_player.contract.salary:,}/year" if hasattr(focus_player, 'contract') and focus_player.contract else "No contract"
            stats_info = f"{getattr(focus_player.stats, 'goals', 0)}G {getattr(focus_player.stats, 'assists', 0)}A"
            
            info_text = (
                f"Position: {focus_player.primary_position.value}\n"
                f"Age: {focus_player.age} | Overall: {focus_player.overall_rating()}/20\n"
                f"Contract: {contract_info}\n"
                f"Stats: {stats_info}\n"
                f"Status: Healthy"
            )
            self.focus_player_info_label.config(text=info_text)
    
    def update_enhanced_quick_stats_panel(self):
        """Update the enhanced quick stats panel."""
        # Team record
        team_name = self.user_team.team_name
        record = self.league.standings.get(team_name, {'W': 0, 'L': 0, 'OTL': 0})
        
        if hasattr(self, 'quick_record_label'):
            self.quick_record_label.config(text=f"{record['W']}-{record['L']}-{record['OTL']}")
        
        # Points and standing position
        if hasattr(self, 'quick_standing_label'):
            points = record['W'] * 2 + record['OTL']
            standings_list = sorted(self.league.standings.items(), 
                                   key=lambda x: x[1]['W'] * 2 + x[1]['OTL'], reverse=True)
            position = next((i+1 for i, (team, _) in enumerate(standings_list) if team == team_name), '-')
            self.quick_standing_label.config(text=f"Position: {position}{self._get_ordinal_suffix(position)} ({points} pts)")
        
        # Team leaders
        if hasattr(self, 'quick_leaders_label') and self.user_team.roster:
            try:
                top_goal_scorer = max(self.user_team.roster, key=lambda p: getattr(p.stats, 'goals', 0))
                top_assist_leader = max(self.user_team.roster, key=lambda p: getattr(p.stats, 'assists', 0))
                top_point_scorer = max(self.user_team.roster, key=lambda p: getattr(p.stats, 'goals', 0) + getattr(p.stats, 'assists', 0))
                
                leaders_text = (
                    f"G: {top_goal_scorer.first_name[0]}.{top_goal_scorer.last_name} ({getattr(top_goal_scorer.stats, 'goals', 0)})\n"
                    f"A: {top_assist_leader.first_name[0]}.{top_assist_leader.last_name} ({getattr(top_assist_leader.stats, 'assists', 0)})\n"
                    f"P: {top_point_scorer.first_name[0]}.{top_point_scorer.last_name} ({getattr(top_point_scorer.stats, 'goals', 0) + getattr(top_point_scorer.stats, 'assists', 0)})"
                )
                self.quick_leaders_label.config(text=leaders_text)
            except (ValueError, AttributeError):
                self.quick_leaders_label.config(text="G: No data\nA: No data\nP: No data")
        
        # Recent form (last 5 games)
        if hasattr(self, 'quick_form_label'):
            try:
                games_played = []
                if hasattr(self.league, 'schedule') and self.league.schedule:
                    for game in self.league.schedule:
                        # Handle different schedule formats
                        if hasattr(game, 'date') and hasattr(game, 'home_team') and hasattr(game, 'away_team'):
                            if (game.date < self.current_date and 
                                (game.home_team == team_name or game.away_team == team_name)):
                                games_played.append(game)
                        # Handle tuple format if needed
                        elif isinstance(game, (list, tuple)) and len(game) >= 3:
                            game_date, home_team, away_team = game[:3]
                            if (hasattr(game_date, 'date') or isinstance(game_date, str)):
                                if (home_team == team_name or away_team == team_name):
                                    games_played.append(game)
                
                recent_games = sorted(games_played, key=lambda x: x.date if hasattr(x, 'date') else x[0])[-5:]
                
                if recent_games:
                    form = []
                    for game in recent_games:
                        if hasattr(game, 'home_score') and hasattr(game, 'away_score'):
                            if game.home_score is not None and game.away_score is not None:
                                if hasattr(game, 'home_team'):
                                    if game.home_team == team_name:
                                        result = 'W' if game.home_score > game.away_score else 'L'
                                    else:
                                        result = 'W' if game.away_score > game.home_score else 'L'
                                    form.append(result)
                    
                    form_str = '-'.join(form) if form else '-----'
                    self.quick_form_label.config(text=f"Last 5: {form_str}")
                else:
                    self.quick_form_label.config(text="Last 5: -----")
            except Exception as e:
                print(f"Error updating quick form: {e}")
                self.quick_form_label.config(text="Last 5: -----")
    
    def _get_ordinal_suffix(self, n):
        """Get ordinal suffix for numbers (1st, 2nd, 3rd, etc.)"""
        if isinstance(n, str):
            return ''
        if 10 <= n % 100 <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return suffix
    
    def launch_live_viewer(self):
        """Launch the game viewer for live simulation"""
        try:
            # Get team names for live game
            home_team = "Thunderbirds"
            away_team = "Eagles"
            
            # Use the main game viewer system instead of separate live viewer
            # Create a simple event log for demonstration
            demo_event_log = [
                {'timestamp': 0.0, 'type': 'GAME_START', 'details': {}},
                {'timestamp': 10.0, 'type': 'FACE_OFF', 'details': {'location': 'center'}},
                {'timestamp': 30.0, 'type': 'SHOT', 'details': {'player_id': 'home_1', 'target_pos': (400, 200)}}
            ]
            
            # Launch using the unified game viewer system
            launch_game_viewer(demo_event_log, 3600, home_team, away_team)
            
        except Exception as e:
            messagebox.showerror("Game Viewer Error", f"Error launching game viewer: {str(e)}")
            print(f"Game viewer error: {e}")
    
    def launch_ehm_viewer(self):
        """Launch the EHM-style game with enhanced simulation"""
        try:
            # Import EHM integration
            from ehm_integration import EHMGameIntegration
            
            # Initialize EHM integration if not already done
            if not hasattr(self, 'ehm_integration'):
                self.ehm_integration = EHMGameIntegration(self)
            
            # Get teams for the game (use real teams from game manager)
            teams = list(self.game_manager.league.teams)
            if len(teams) >= 2:
                home_team = teams[0]
                away_team = teams[1]
            else:
                # Create sample teams if needed
                from game_classes import Team
                home_team = Team("Thunderbirds")
                away_team = Team("Eagles")
                
                # Add sample players
                from game_classes import Player, PlayerPosition
                for team in [home_team, away_team]:
                    for _ in range(25):  # 25 players per team
                        position = random.choice(list(PlayerPosition))
                        player = Player(
                            first_name=random.choice(FIRST_NAMES),
                            last_name=random.choice(LAST_NAMES),
                            age=random.randint(18, 35),
                            primary_position=position
                        )
                        team.roster.append(player)
            
            # Launch EHM game viewer
            self.ehm_integration.launch_ehm_game_viewer(home_team, away_team)
            
        except Exception as e:
            messagebox.showerror("EHM Viewer Error", f"Error launching EHM viewer: {str(e)}")
            print(f"EHM viewer error: {e}")
            import traceback
            traceback.print_exc()

    def simulate_day(self):
        """Completely reworked daily simulation that properly handles all scenarios"""
        # CHECK FOR ACTIVE FANTASY DRAFT - PREVENT DAY ADVANCEMENT
        if hasattr(self.game_manager, 'pending_fantasy_draft') and self.game_manager.pending_fantasy_draft:
            from tkinter import messagebox
            messagebox.showwarning("Fantasy Draft Active", 
                                 "🏒 Fantasy Draft in Progress!\n\n"
                                 "You must complete the fantasy draft before advancing the day.\n"
                                 "Go to Tools → Fantasy Draft to continue or complete the draft.")
            return
            
        # Prevent multiple clicks by disabling button during simulation
        continue_btn = None
        if hasattr(self, 'continue_btn'):
            continue_btn = self.continue_btn
        elif hasattr(self, 'dashboard') and hasattr(self.dashboard, 'continue_btn'):
            continue_btn = self.dashboard.continue_btn
        elif hasattr(self, 'dashboard') and hasattr(self.dashboard, 'widgets') and 'continue_btn' in self.dashboard.widgets:
            continue_btn = self.dashboard.widgets['continue_btn']
            
        if continue_btn and continue_btn['state'] == 'disabled':
            return  # Already processing, ignore this click
            
        if continue_btn:
            continue_btn.config(state='disabled')
            
        try:
            # Check for season end by games completed (primary trigger).
            # The date cutoff is only a safety net set AFTER the last scheduled
            # game, since the generated schedule can run past April 15.
            season_complete = self._check_season_complete()

            if season_complete:
                self.end_of_season()
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
                return

            # Process daily maintenance tasks FIRST (before checking games)
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
            
            # Process games if any exist
            if todays_games:
                # Rosters/tactics can change daily (trades, injuries, user tweaks):
                # drop the cached team-strength values so sims stay current.
                if hasattr(self, '_strength_cache'):
                    self._strength_cache.clear()
                self._process_todays_games(todays_games)
            
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
            
            # Process AI team decisions (trades, signings, etc.)
            # Only every 7 days (handled internally by ai_manager)
            try:
                if hasattr(self.league, 'free_agents'):
                    free_agents = self.league.free_agents
                else:
                    free_agents = []
                decisions = self.game_manager.ai_manager.process_daily_decisions(
                    self.league.teams, free_agents, self.current_date
                )
                # Log significant decisions
                for d in decisions[:5]:  # Limit spam
                    if hasattr(d, 'description'):
                        print(f"🤖 AI: {d.description}")
            except Exception as e:
                # Don't crash the game if AI fails
                print(f"AI manager error (non-fatal): {e}")
            
            # ALWAYS advance date and update UI (whether games existed or not)
            self.current_date += timedelta(days=1)
            
            # Clear caches periodically to prevent memory bloat
            if self.current_date.day == 1:  # First day of each month
                if hasattr(self, '_schedule_cache'):
                    self._schedule_cache.clear()
                if hasattr(self, '_strength_cache'):
                    self._strength_cache.clear()
                # Monthly player development (ratings change -> strength recomputed)
                try:
                    self.game_manager._process_monthly_development()
                except Exception as e:
                    print(f"Player development error (non-fatal): {e}")
            
            # Update game_manager's current_date for dashboard synchronization
            self.game_manager.current_date = self.current_date
            
            # Refresh the atmospheric dashboard with updated data
            if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'refresh_dashboard'):
                self.dashboard.refresh_dashboard()
            
            # Show daily results window after processing games
            settings = self.get_settings()
            should_show_results = (
                todays_games or  # Show if there were scheduled games today
                settings.get('simulation', {}).get('always_show_daily_results', True) or  # Or if always show is enabled
                len(self.game_results) > 0  # Or if there are any game results at all
            )
            
            if should_show_results:
                self._show_daily_results_window()
            
            # Use async update to prevent blocking
            self.after_idle(self.update_all_views)
            
        finally:
            # Re-enable continue button after simulation is complete
            continue_btn = None
            if hasattr(self, 'continue_btn'):
                continue_btn = self.continue_btn
            elif hasattr(self, 'dashboard') and hasattr(self.dashboard, 'continue_btn'):
                continue_btn = self.dashboard.continue_btn
            elif hasattr(self, 'dashboard') and hasattr(self.dashboard, 'widgets') and 'continue_btn' in self.dashboard.widgets:
                continue_btn = self.dashboard.widgets['continue_btn']
                
            if continue_btn:
                continue_btn.config(state='normal')

    def _check_season_complete(self):
        """Check if the regular season is complete by counting games played."""
        def _gp(stats):
            # Standings dicts use "W"/"L" keys (some legacy code used "Wins"/"Losses")
            return (stats.get('W', stats.get('Wins', 0))
                    + stats.get('L', stats.get('Losses', 0))
                    + stats.get('OTL', 0))
        try:
            # Get target games per team based on season length
            target_games = getattr(self, 'season_games_count', 82)

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

    def _process_daily_maintenance(self):
        """Process daily maintenance tasks with performance optimizations"""
        # Only run heavy tasks on specific days to reduce CPU load

        # Event-day hubs: prompt once per year when a tentpole day arrives
        self._check_for_event_day()
        
        # Check for Entry Draft (held in June) - only check once per week
        if self.current_date.weekday() == 0:  # Monday only
            self._check_for_entry_draft()
        
        # Process trade block offers (once per week) - unchanged
        if self.current_date.weekday() == 0:  # Monday
            self.process_trade_block_offers()
        
        # Process scouting assignments - optimized to run every 3 days instead of daily
        if self.current_date.day % 3 == 0:  # Every 3 days
            self.process_scouting_assignments()
            try:
                import scouting as scouting_mod
                scouting_mod.process_regional_scouting(self.game_manager
                                                       if hasattr(self, 'game_manager') else self)
            except Exception:
                pass
        
        # Process waivers - reduced frequency
        if self.current_date.weekday() in [0, 3]:  # Monday and Thursday only
            self.process_waivers()
        
        # Generate daily emails - optimized
        if self.current_date.weekday() == 0:  # Weekly summary instead of daily
            self._generate_weekly_email_summary()
        
        # Run Phase 2 optimizations less frequently
        if self.current_date.weekday() == 6:  # Sunday only
            self._run_phase2_maintenance()
        
        # Process player development weekly (during off days or end of week)
        if self.current_date.weekday() == 6:  # Sunday - weekly development processing
            self._process_player_development()

        # FM-style career systems: board, happiness, youth, press (cheap daily)
        self._process_career_daily()
    
    def _process_player_development(self):
        """Process weekly player development for all teams"""
        if not hasattr(self, 'development_engine') or self.development_engine is None:
            return
        
        try:
            development_events = []
            
            for team in self.league.teams:
                for roster_list in (team.roster, team.ahl_roster, team.prospects):
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
                            
                            # Apply development to attributes based on player age and stage
                            if player.age <= 27:  # Only develop younger players
                                import random
                                
                                # Determine which attributes can develop
                                developable_attrs = self._get_developable_attributes(player)
                                
                                for attr in developable_attrs:
                                    if hasattr(player, attr):
                                        current_val = getattr(player, attr)
                                        max_val = getattr(player.potential_info, f'{attr}_ceiling', 20) if hasattr(player.potential_info, f'{attr}_ceiling') else 20
                                        
                                        # Check if there's room to grow
                                        if current_val < max_val and current_val < 20:
                                            # Small chance of improvement each week
                                            improvement_chance = weekly_rate * 0.15
                                            
                                            if random.random() < improvement_chance:
                                                new_val = min(current_val + 1, max_val, 20)
                                                setattr(player, attr, new_val)
                                                
                                                # Track significant improvements
                                                if team == self.user_team and new_val >= 15:
                                                    development_events.append({
                                                        'player': player,
                                                        'attribute': attr,
                                                        'old_value': current_val,
                                                        'new_value': new_val
                                                    })
                            
                            # Age-related decline for older players
                            elif player.age >= 33:
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
                else:
                    continue  # Skip malformed games silently
            except (IndexError, KeyError, ValueError):
                continue  # Skip errors silently
            
            # Check if game viewer is enabled in settings (simplified)
            settings = self.get_settings()
            use_game_viewer = settings.get('simulation', {}).get('use_game_viewer', False)
            
            if use_game_viewer:
                # Modern visual play-by-play (rink + live player bubbles).
                # Modal: returns the standard 6-tuple once watched to the end.
                result = self._simulate_game_with_pbp_visual(home_team, away_team)
                winner, loser, scores, events, notable_events, sim_engine = result
            else:
                # FM-style pre-match team talk (interactive, skipped in bulk sim)
                opponent = away_team if home_team == self.user_team else home_team
                talk_boost = self._career_team_talk(opponent)
                # Standard full simulation for user games
                sim_engine = AdvancedGameSim(home_team, away_team)
                if talk_boost != 1.0 and self.user_team is not None:
                    sim_engine.set_team_talk_boost(self.user_team.team_name, talk_boost)
                winner, loser, scores, events, notable_events = sim_engine.run()

            # Update league standings and store game result for user team games
            self._process_single_game_result(game_date, home_team, away_team, winner, loser, scores, events, notable_events, sim_engine)
            # FM-style: board, profile, morale, post-match presser
            went_ot = len([e for e in (notable_events or []) if isinstance(e, dict) and e.get('period', 0) > 3]) > 0
            self._career_after_user_game(winner, loser, scores, home_team, away_team, went_ot, sim_engine)
        
        # Process other games using batch processing
        if other_games:
            self._simulate_games_batch(other_games)

    def _process_single_game_result(self, game_date, home_team, away_team, winner, loser, scores, events, notable_events, sim_engine):
        """Process a single game result - used for user team games"""
        # Update league standings (safely)
        home_score, away_score = scores
        
        # Ensure teams exist in standings
        if home_team.team_name not in self.league.standings:
            self.league.standings[home_team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
        if away_team.team_name not in self.league.standings:
            self.league.standings[away_team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
        
        # Detect if game went to overtime/shootout (for OTL point)
        # NHL rule: loser in OT/SO gets 1 point (OTL)
        went_to_ot = len([e for e in notable_events if e.get('period', 0) > 3]) > 0
        
        # Winner gets 2 points
        self.league.standings[winner.team_name]['W'] += 1
        self.league.standings[winner.team_name]['Points'] += 2
        
        # Loser: OTL point if game went to OT/SO, else regulation loss
        if went_to_ot:
            self.league.standings[loser.team_name]['OTL'] += 1
            self.league.standings[loser.team_name]['Points'] += 1
        else:
            self.league.standings[loser.team_name]['L'] += 1
        
        # Store game result for later viewing
        player_ratings = self._calculate_player_ratings(getattr(sim_engine, 'stats', {}), events)
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
            'overtime': away_score != home_score and len([e for e in notable_events if e['period'] > 3]) > 0,
            'shootout': len([e for e in notable_events if e['period'] == 5]) > 0
        }
        
        self.game_results.append(game_result)
        
        # Generate media events for the game (if media system enabled)
        if hasattr(self, 'media_system') and self.media_system:
            self.media_system.process_game_result(game_result)
        
        # Update player stats from game events
        # Records: goals, assists, shots, saves, PIM, games played
        
        # Build roster lookups for assist selection
        home_roster = {p.id: p for p in home_team.roster}
        away_roster = {p.id: p for p in away_team.roster}
        
        # Identify starting goalies for save tracking
        def get_starting_goalie(team):
            goalies = [p for p in team.roster 
                      if getattr(p, 'primary_position', None) and p.primary_position.name == "G"]
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
                
                # Assists: up to 2 teammates (NHL: ~70% get 2, ~20% get 1, ~10% unassisted)
                team_roster = home_roster if team_name == home_team.team_name else away_roster
                potential_assisters = [
                    p for p in team_roster.values()
                    if p.id != player.id 
                    and getattr(p, 'primary_position', None) 
                    and p.primary_position.name != "G"
                ]
                num_assists = random.choices([2, 1, 0], weights=[0.7, 0.2, 0.1])[0]
                if potential_assisters and num_assists > 0:
                    assisters = random.sample(potential_assisters, min(num_assists, len(potential_assisters)))
                    for assister in assisters:
                        assister.stats.assists += 1
                
                # Opposing goalie: shot against (goal counts as shot faced, not a save)
                opp_goalie = away_goalie if team_name == home_team.team_name else home_goalie
                if opp_goalie:
                    opp_goalie.stats.shots_against += 1
            
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
        
        # Games played: all roster players get credit
        # (In real NHL only dressed players get GP, but sim doesn't track scratches)
        for team in [home_team, away_team]:
            for player in team.roster:
                player.stats.games_played += 1
        
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

    def _show_daily_results_window(self):
        """Show the daily game results window after day advance"""
        try:
            # Get today's game results (the day we just simulated, before date advancement)
            simulated_date = self.current_date - timedelta(days=1)
            today_results = []
            user_game_result = None
            
            # Find games from the simulated date
            for result in self.game_results:
                result_date = result['date']
                
                # Handle different date formats/types consistently
                try:
                    if hasattr(result_date, 'date'):
                        # If it's a datetime object, extract the date part
                        result_date = result_date.date()
                    elif isinstance(result_date, str):
                        # If it's a string, try to parse it
                        from datetime import datetime
                        result_date = datetime.strptime(result_date, '%Y-%m-%d').date()
                    # If already a date object, use as is
                    
                    # Ensure simulated_date is also a date object for comparison
                    if hasattr(simulated_date, 'date'):
                        simulated_date_only = simulated_date.date()
                    else:
                        simulated_date_only = simulated_date
                        
                except (ValueError, AttributeError) as e:
                    # Skip results with unparseable dates
                    continue
                    
                if result_date == simulated_date_only:
                    today_results.append(result)
                    # Check if user team played
                    if self.user_team in (result['home_team'], result['away_team']):
                        user_game_result = result
            
            # Get league standings
            league_results = []
            for team_name, stats in self.league.standings.items():
                league_results.append({
                    'team': team_name,
                    'wins': stats['W'],
                    'losses': stats['L'],
                    'otl': stats['OTL'],
                    'points': stats['Points']
                })
            
            # Sort by points
            league_results.sort(key=lambda x: x['points'], reverse=True)
            
            # Get recent news
            recent_news = []
            if hasattr(self, 'news_log'):
                # Get last 5 news items
                recent_news = self.news_log[-5:] if len(self.news_log) >= 5 else self.news_log[:]
            
            # Generate game highlights if user team played
            game_highlights = []
            if user_game_result:
                # Create highlights from notable events
                for event in user_game_result.get('notable_events', []):
                    if event.get('event') in ['Goal', 'Save', 'Hit', 'Fight']:
                        player_name = "Unknown"
                        if 'player' in event and event['player']:
                            player_name = event['player'].full_name if hasattr(event['player'], 'full_name') else str(event['player'])
                        highlight = f"{event.get('event')}: {player_name} - Period {event.get('period', 1)}"
                        game_highlights.append(highlight)
            
            # Show the results window
            from game_results_window import GameResultsWindow
            
            # Package all data into the format GameResultsWindow expects
            results_data = {
                'date': self.current_date.strftime("%B %d, %Y"),
                'user_game_result': user_game_result,
                'all_games': today_results,  # GameResultsWindow expects 'all_games' not 'today_results'
                'league_results': league_results,
                'news_events': recent_news,  # GameResultsWindow expects 'news_events' not 'recent_news'
                'game_highlights': game_highlights,
                'games_played': len(today_results) if today_results else 0,
                'new_messages_count': 0  # TODO: Calculate actual new message count
            }
            
            results_window = GameResultsWindow(
                self,
                results_data
            )
            
        except Exception as e:
            print(f"Error showing daily results: {e}")
            import traceback
            traceback.print_exc()

    def _check_for_event_day(self):
        """Detect tentpole event days (draft, deadline, free agency) and offer the hub once per year."""
        try:
            from event_day_hubs import get_todays_event
            event = get_todays_event(self.current_date)
            if not event:
                return
            if not hasattr(self, '_event_day_prompted'):
                self._event_day_prompted = set()
            key = (event, self.current_date.year)
            if key in self._event_day_prompted:
                return
            self._event_day_prompted.add(key)
            # Defer the prompt so the daily sim UI finishes updating first
            self.after(500, lambda: prompt_event_day(self, self.game_manager, event))
        except Exception:
            pass

    def _check_for_entry_draft(self):
        """Check if today is the Entry Draft and open draft window if so"""
        try:
            # Entry Draft is typically held in late June
            draft_month = 6  # June
            draft_day = 23   # Usually around June 23-25
            
            if (self.current_date.month == draft_month and 
                self.current_date.day >= draft_day and 
                self.current_date.day <= draft_day + 2):  # Give 3-day window
                
                # Check if we've already held the draft this year
                if not hasattr(self, '_draft_held_this_year'):
                    self._draft_held_this_year = set()
                
                current_year = self.current_date.year
                if current_year not in self._draft_held_this_year:
                    # It's draft time! 
                    self._hold_entry_draft(current_year)
                    self._draft_held_this_year.add(current_year)
                    
        except Exception as e:
            print(f"Error checking for entry draft: {e}")
            import traceback
            traceback.print_exc()

    def _hold_entry_draft(self, year):
        """Hold the annual entry draft"""
        print(f"🏒 ENTRY DRAFT {year} BEGINS! 🏒")
        
        # Generate draft prospects if they don't exist
        if not self.league.draft_prospects:
            print("Generating draft prospects...")
            from draft_generator import generate_draft_class
            self.league.draft_prospects = generate_draft_class(year)
            print(f"Generated {len(self.league.draft_prospects)} draft prospects")
        
        # Ensure draft picks are set up
        self.league.initialize_all_draft_picks()
        
        # Simulate draft lottery for first round
        self.league.simulate_draft_lottery(year)
        
        # Add news story about the draft
        draft_story = f"The {year} NHL Entry Draft begins today! Teams will select from a pool of {len(self.league.draft_prospects)} eligible prospects over 7 rounds."
        self.add_news_story(draft_story)
        
        # Open the draft window
        if 'draft' not in self.open_windows or not self.open_windows['draft'].winfo_exists():
            self.open_windows['draft'] = DraftWindow(self)
        self.open_windows['draft'].focus_set()
        
        # Show notification to user
        messagebox.showinfo(
            "Entry Draft", 
            f"The {year} NHL Entry Draft is beginning!\n\n"
            f"The draft window has been opened. Your team can now make selections "
            f"when it's your turn to pick.\n\n"
            f"Good luck building your franchise!"
        )

    def conduct_fantasy_draft(self):
        """Conduct a fantasy draft by redistributing all players among NHL teams"""
        print("🌟 FANTASY DRAFT BEGINNING! 🌟")
        print("Redistributing all players among NHL teams...")
        
        # Get all NHL teams
        nhl_teams = [team for team in self.league.teams if team.league_name == "National Hockey League"]
        if not nhl_teams:
            print("No NHL teams found for fantasy draft!")
            return
        
        # Collect all players from NHL teams (excluding prospects and staff)
        all_players = []
        for team in nhl_teams:
            # Collect players from all roster levels
            all_players.extend(team.roster)
            all_players.extend(team.ahl_roster)
            # Keep prospects with their original teams - they haven't been drafted yet
            
            # Clear team rosters
            team.roster = []
            team.ahl_roster = []
        
        print(f"Collected {len(all_players)} players for fantasy draft")
        
        # Sort players by overall rating (best players drafted first)
        all_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Conduct serpentine draft (team order reverses each round)
        draft_order = list(range(len(nhl_teams)))
        team_index = 0
        round_num = 1
        picks_this_round = 0
        
        for i, player in enumerate(all_players):
            # Assign player to current team
            current_team = nhl_teams[draft_order[team_index]]
            
            # Assign to NHL roster for top players, AHL for others
            if len(current_team.roster) < 23:  # NHL roster limit
                current_team.roster.append(player)
                player.team_name = current_team.team_name
                player.current_team = current_team.team_name
            else:
                current_team.ahl_roster.append(player)
                player.team_name = current_team.team_name
                player.current_team = current_team.team_name
            
            # Move to next team
            team_index += 1
            picks_this_round += 1
            
            # Check if round is complete
            if picks_this_round >= len(nhl_teams):
                print(f"Fantasy Draft Round {round_num} complete")
                round_num += 1
                picks_this_round = 0
                # Reverse draft order for serpentine draft
                draft_order.reverse()
                team_index = 0
        
        # Add news story about fantasy draft
        fantasy_story = f"Fantasy Draft Complete! All {len(all_players)} NHL players have been redistributed among the 32 teams. Every franchise starts fresh with a completely new roster!"
        self.add_news_story(fantasy_story)
        
        print("🎉 Fantasy draft complete! All teams have new rosters.")
        print(f"Players redistributed: {len(all_players)}")
        
        # Show notification to user
        messagebox.showinfo(
            "Fantasy Draft Complete", 
            f"The Fantasy Draft is complete!\n\n"
            f"All {len(all_players)} NHL players have been redistributed among teams using a serpentine draft format.\n\n"
            f"Every team now has a completely fresh roster. Good luck with your new lineup!"
        )

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

    def _initialize_phase2_systems(self):
        """Initialize Phase 2 optimization systems"""
        print("Initializing Phase 2 optimization systems...")
        
        # Initialize memory optimization
        try:
            from memory_optimization import initialize_memory_optimizer
            self.memory_optimizer = initialize_memory_optimizer()
            print("✓ Memory optimization initialized")
        except Exception as e:
            print(f"⚠ Memory optimization failed: {e}")
            self.memory_optimizer = None
        
        # Initialize lazy loading (will be set up after game manager is available)
        self.lazy_manager = None
        
        # Initialize database indexing (will be set up after league is available)
        self.db_manager = None
    
    def _finalize_phase2_initialization(self):
        """Complete Phase 2 initialization after game data is available"""
        print("Finalizing Phase 2 optimization systems...")
        
        # Initialize database indexing
        try:
            from database_indexing import get_database_manager
            self.db_manager = get_database_manager()
            if self.league:
                init_time = self.db_manager.initialize(self.league)
                print(f"✓ Database indexing initialized in {init_time:.2f}s")
        except Exception as e:
            print(f"⚠ Database indexing failed: {e}")
        
        # Initialize lazy loading
        try:
            from lazy_loading import initialize_lazy_manager
            self.lazy_manager = initialize_lazy_manager(self.game_manager)
            if self.user_team:
                self.lazy_manager.preload_user_team_data(self.user_team.team_name)
            print("✓ Lazy loading initialized")
        except Exception as e:
            print(f"⚠ Lazy loading failed: {e}")
        
        # Initialize Player Development Engine
        try:
            self.development_engine = PlayerDevelopmentEngine()
            # Initialize player potentials if needed
            if self.league and self.league.teams:
                players_initialized = 0
                for team in self.league.teams:
                    for roster_list in (team.roster, team.ahl_roster, team.prospects):
                        for player in roster_list:
                            if not hasattr(player, 'potential_info') or player.potential_info is None:
                                player.potential_info = initialize_player_potential(player)
                                players_initialized += 1
                print(f"✓ Player Development Engine initialized ({players_initialized} player potentials set)")
        except Exception as e:
            print(f"⚠ Player Development Engine failed: {e}")
            self.development_engine = None
        
        print("Phase 2 optimization systems ready!")

    def _initialize_phase3_systems(self):
        """Initialize Phase 3 UI/UX optimization systems"""
        print("Initializing Phase 3 UI/UX optimization systems...")
        
        # Initialize UI optimizations
        try:
            from ui_optimizations import UIOptimizationManager
            self.ui_optimizer = UIOptimizationManager(self)
            self.ui_metrics = self.ui_optimizer.ui_metrics
            print("✓ UI optimization manager initialized")
        except Exception as e:
            print(f"⚠ UI optimization failed: {e}")
            self.ui_optimizer = None
            self.ui_metrics = None
        
        # Initialize rendering optimizations
        try:
            from rendering_optimizations import RenderingManager
            self.rendering_manager = RenderingManager(self)
            print("✓ Rendering optimization manager initialized")
        except Exception as e:
            print(f"⚠ Rendering optimization failed: {e}")
            self.rendering_manager = None
        
        print("Phase 3 UI/UX optimization systems ready!")

    def _apply_phase3_optimizations(self):
        """Apply Phase 3 optimizations to the main UI"""
        print("Applying Phase 3 UI/UX optimizations...")
        
        if self.rendering_manager:
            # Optimize all widgets in the main window
            def optimize_widgets(widget):
                try:
                    self.rendering_manager.optimize_widget(widget)
                    for child in widget.winfo_children():
                        optimize_widgets(child)
                except tk.TclError:
                    pass
            
            optimize_widgets(self)
            print("✓ Rendering optimizations applied")
        
        # Apply responsive button optimizations to existing buttons
        if self.ui_optimizer:
            # This will be applied to new buttons via create methods
            print("✓ UI optimizations ready for new components")
        
        print("Phase 3 optimizations applied to main interface!")

    def _simulate_games_batch(self, games):
        """Simulate multiple games efficiently using LIGHTWEIGHT batch processing"""
        # Ultra-fast simulation for non-user games
        batch_results = []
        user_team = getattr(self, 'user_team', None)  # Add user_team reference
        
        for game in games:
            try:
                # Extract game data
                if isinstance(game, dict):
                    game_date = game.get('date')
                    home_team = game.get('home_team')
                    away_team = game.get('away_team')
                elif isinstance(game, tuple) and len(game) >= 3:
                    game_date, home_team, away_team = game[:3]
                else:
                    continue
                
                # Per-league sim detail (new-game setup): 'full' leagues get the
                # event-by-event engine with player stats; everything else
                # uses the ultra-fast lightweight path.
                league_key = game.get('league') if isinstance(game, dict) else None
                full_sim = None
                if self._league_sim_detail(league_key) == 'full':
                    winner, loser, scores, went_to_ot, full_sim = \
                        self._simulate_game_full_batch(home_team, away_team)
                else:
                    # LIGHTWEIGHT simulation - just calculate winner and score
                    result = self._simulate_game_lightweight(home_team, away_team)
                    winner, loser, scores, went_to_ot = result

                batch_results.append((game_date, home_team, away_team, winner,
                                      loser, scores, went_to_ot, full_sim))
                
                # Update standings immediately (no batch delay)
                self._update_standings_fast(home_team, away_team, winner, scores, went_to_ot)
                
            except Exception as e:
                print(f"Error in batch simulation: {e}")
                continue
        
        # Store minimal game results for performance
        for game_date, home_team, away_team, winner, loser, scores, went_to_ot, full_sim in batch_results:
            home_score, away_score = scores

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
                'shootout': False
            }
            if full_sim is not None:
                # Full-detail league: keep the event stream for reports/viewer
                game_result['event_log'] = getattr(full_sim, 'event_log', []) or []
                game_result['notable_events'] = getattr(full_sim, 'notable_events', []) or []
                game_result['events'] = getattr(full_sim, 'game_log', []) or []
            
            # Add to game results
            self.game_results.append(game_result)
            
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
    
    def _league_sim_detail(self, league_key):
        """Return the configured sim detail for a league ('full' | 'quick' | 'scores').

        Set by the new-game setup wizard (gm.sim_detail). Defaults: the user's
        league runs full, everything else runs quick.
        """
        detail = getattr(self, 'sim_detail', None) or {}
        if league_key in detail:
            return detail[league_key]
        user_league = getattr(self, 'user_league', None)
        if league_key and user_league and league_key == user_league:
            return 'full'
        return 'quick'

    def _simulate_game_full_batch(self, home_team, away_team):
        """Full event-by-event sim for batch games in 'full'-detail leagues.

        Uses simulation.GameSim (the hooked engine). Player season stats are
        updated by the engine itself. Returns
        (winner, loser, scores, went_to_ot, sim).
        """
        from simulation import GameSim
        sim = GameSim(home_team, away_team)
        periods = set()
        had_shootout = {'v': False}

        def _sniff(ev):
            if isinstance(ev, dict):
                periods.add(ev.get('period', 1))
                if ev.get('type') == 'shootout_end':
                    had_shootout['v'] = True

        sim.pbp_listeners.append(_sniff)
        winner, loser, scores, _game_log, _notable = sim.run()
        went_to_ot = any(p > 3 for p in periods)
        return winner, loser, scores, went_to_ot, sim

    def _simulate_game_lightweight(self, home_team, away_team):
        """Ultra-fast game simulation with individual player effects and realistic scoring distribution"""
        import random
        
        # Calculate base team strengths
        home_strength = self._calculate_team_strength(home_team) + 0.05  # Home ice advantage
        away_strength = self._calculate_team_strength(away_team)
        
        # Add individual star player effects
        home_star_effects = self._calculate_star_player_effects(home_team)
        away_star_effects = self._calculate_star_player_effects(away_team)
        
        # Apply star player bonuses to team strength
        home_strength += home_star_effects['offensive_boost']
        away_strength += away_star_effects['offensive_boost']
        
        # Base goal expectation for NHL-like scoring
        base_goals = 2.95  # Lowered slightly for more realistic low-scoring games
        home_goal_expectation = base_goals + (home_strength - 0.75) * 2.2
        away_goal_expectation = base_goals + (away_strength - 0.75) * 2.2
        
        # Apply defensive effects (elite goalies/defense reduce opponent scoring)
        home_goal_expectation -= away_star_effects['defensive_reduction']
        away_goal_expectation -= home_star_effects['defensive_reduction']
        
        # Allow for low-scoring games but maintain reasonable averages
        home_goal_expectation = max(1.0, min(4.5, home_goal_expectation))
        away_goal_expectation = max(1.0, min(4.5, away_goal_expectation))

        # Team tactics shape scoring (EHM-style: style matters, not just talent).
        # Offensive hockey opens the game up (both teams score more);
        # defensive systems suppress scoring at both ends.
        def _tactic_shifts(es_tactic):
            own_shift = {'Very Offensive': 0.14, 'Offensive': 0.10, 'Balanced': 0.0,
                         'Defensive': -0.08, 'Very Defensive': -0.11}.get(es_tactic, 0.0)
            opp_shift = {'Very Offensive': 0.11, 'Offensive': 0.08, 'Balanced': 0.0,
                         'Defensive': -0.06, 'Very Defensive': -0.09}.get(es_tactic, 0.0)
            return own_shift, opp_shift

        home_own, home_opp = _tactic_shifts(getattr(home_team, 'tactic_even_strength', 'Balanced'))
        away_own, away_opp = _tactic_shifts(getattr(away_team, 'tactic_even_strength', 'Balanced'))
        home_goal_expectation += home_own + away_opp
        away_goal_expectation += away_own + home_opp

        # FM-style squad morale modifier (subtle: +/-3%)
        home_goal_expectation *= self._career_morale_modifier(home_team)
        away_goal_expectation *= self._career_morale_modifier(away_team)
        
        # Generate goals with realistic NHL distribution
        # Use round() not int() to avoid truncation bias (~0.5 goals lost per team)
        # σ=1.0 gives ~7% shutout rate (NHL realistic) vs 24.5% with σ=1.25
        home_goals = max(0, min(8, round(random.normalvariate(home_goal_expectation, 1.0))))
        away_goals = max(0, min(8, round(random.normalvariate(away_goal_expectation, 1.0))))
        
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
        if home_goals == away_goals:
            went_to_ot = True
            home_ot_chance = 0.55 + (home_star_effects['clutch_factor'] * 0.1)  # Star players help in OT
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
        
        # Generate realistic individual player stats
        self._generate_player_stats(home_team, away_team, home_goals, away_goals)

        # Gameplay injuries (same ~13%/team rate as the detailed sim)
        for team in (home_team, away_team):
            if random.random() < 0.13:
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
    
    def _calculate_team_strength(self, team):
        """Quick team strength calculation for lightweight simulation"""
        # Use cached calculation if available
        cache_key = f"strength_{team.team_name}"
        if hasattr(self, '_strength_cache') and cache_key in self._strength_cache:
            return self._strength_cache[cache_key]
        
        if not hasattr(self, '_strength_cache'):
            self._strength_cache = {}
        
        # Enhanced strength calculation based on key players
        total_strength = 0
        player_count = 0

        # Injured players don't dress: use healthy skaters (fall back to full
        # roster if the team is decimated)
        skaters = [p for p in team.roster if not getattr(p, 'is_injured', False)]
        if len(skaters) < 14:
            skaters = list(team.roster)

        # Sample top players for speed, but weight by position importance
        sorted_roster = sorted(skaters, key=lambda p: p.overall_rating(), reverse=True)
        top_forwards = [p for p in sorted_roster if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:9]
        top_defense = [p for p in sorted_roster if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:6]  
        top_goalies = [p for p in sorted_roster if p.primary_position.name == 'GOALIE'][:2]
        
        # Weight positions appropriately
        for player in top_forwards:
            total_strength += player.overall_rating() * 0.6  # Forwards are 60% of team strength
            player_count += 0.6
            
        for player in top_defense:
            total_strength += player.overall_rating() * 0.3  # Defense is 30% of team strength  
            player_count += 0.3
            
        for player in top_goalies:
            total_strength += player.overall_rating() * 0.1  # Goalies are 10% of team strength
            player_count += 0.1
        
        # Normalize to 0.5-1.0 range for better goal calculation
        # (50-point OVR scale: ~35 avg -> 0.5, ~50 avg -> 1.0)
        avg_ovr = (total_strength / max(player_count, 1)) if player_count > 0 else 37.5
        strength = 0.5 + (avg_ovr - 35) / 30.0
        strength = max(0.5, min(1.0, strength))  # Clamp between 50-100% strength
        
        # Cache the result
        self._strength_cache[cache_key] = strength
        
        return strength
    
    def _calculate_star_player_effects(self, team):
        """Calculate individual star player effects on game outcome"""
        effects = {
            'offensive_boost': 0.0,
            'defensive_reduction': 0.0,
            'clutch_factor': 0.0
        }
        
        # Get top players by position
        sorted_roster = sorted(team.roster, key=lambda p: p.overall_rating(), reverse=True)
        top_forwards = [p for p in sorted_roster if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:3]
        top_defense = [p for p in sorted_roster if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:2]
        top_goalies = [p for p in sorted_roster if p.primary_position.name == 'GOALIE'][:1]
        
        # Elite forwards boost offensive production
        for forward in top_forwards:
            rating = forward.overall_rating()
            if rating >= 52:  # Generational talent
                effects['offensive_boost'] += 0.25
                effects['clutch_factor'] += 0.4
            elif rating >= 50:  # Superstar
                effects['offensive_boost'] += 0.18
                effects['clutch_factor'] += 0.3
            elif rating >= 47:  # Elite
                effects['offensive_boost'] += 0.10
                effects['clutch_factor'] += 0.18
            elif rating >= 44:  # Very good
                effects['offensive_boost'] += 0.05
                effects['clutch_factor'] += 0.08
        
        # Elite defensemen reduce opponent scoring and add clutch
        for defenseman in top_defense:
            rating = defenseman.overall_rating()
            if rating >= 51:  # Elite defender (Norris level)
                effects['defensive_reduction'] += 0.25
                effects['clutch_factor'] += 0.25
            elif rating >= 49:  # Very good defender
                effects['defensive_reduction'] += 0.15
                effects['clutch_factor'] += 0.15
            elif rating >= 46:  # Good defender
                effects['defensive_reduction'] += 0.08
                effects['clutch_factor'] += 0.08
            elif rating >= 43:  # Decent defender
                effects['defensive_reduction'] += 0.03
                effects['clutch_factor'] += 0.03
        
        # Elite goalies have major defensive impact
        for goalie in top_goalies:
            rating = goalie.overall_rating()
            if rating >= 52:  # Elite goalie (Vezina level)
                effects['defensive_reduction'] += 0.35
                effects['clutch_factor'] += 0.3
            elif rating >= 50:  # Very good goalie
                effects['defensive_reduction'] += 0.22
                effects['clutch_factor'] += 0.2
            elif rating >= 47:  # Good goalie
                effects['defensive_reduction'] += 0.12
                effects['clutch_factor'] += 0.12
            elif rating >= 44:  # Decent goalie
                effects['defensive_reduction'] += 0.05
                effects['clutch_factor'] += 0.05
        
        # Cap the effects to prevent unrealistic swings
        effects['offensive_boost'] = min(0.4, effects['offensive_boost'])
        effects['defensive_reduction'] = min(0.5, effects['defensive_reduction'])
        effects['clutch_factor'] = min(1.0, effects['clutch_factor'])
        
        return effects
    
    def _select_starting_goalie(self, team):
        """Pick tonight's starting goalie with realistic rotation.

        Starters play ~75-80% of games; the backup's chance grows the longer
        the starter's consecutive-starts streak runs (covers back-to-backs).
        Injured goalies never dress.
        """
        import random
        goalies = sorted(
            [p for p in team.roster
             if p.primary_position.name == 'GOALIE'
             and not getattr(p, 'is_injured', False)],
            key=lambda p: p.overall_rating(), reverse=True)
        if not goalies:
            return None
        if len(goalies) == 1:
            return goalies[0]
        if not hasattr(self, '_goalie_tracker'):
            self._goalie_tracker = {}
        track = self._goalie_tracker.setdefault(team.team_name, {'last': None, 'consec': 0})
        starter, backup = goalies[0], goalies[1]
        # Backup probability grows with the starter's streak
        p_backup = 0.08 + 0.15 * track['consec']
        if track['last'] == starter.id and random.random() < p_backup:
            pick = backup
        else:
            pick = starter
        if pick.id == starter.id:
            track['consec'] = track['consec'] + 1 if track['last'] == starter.id else 1
        else:
            track['consec'] = 0
        track['last'] = pick.id
        return pick

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
            # Injured players don't dress
            healthy = [p for p in team.roster if not getattr(p, 'is_injured', False)]
            forwards = [p for p in healthy if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:12]
            defensemen = [p for p in healthy if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:6]
            dressed_skaters = forwards + defensemen  # 18 skaters
            
            # Track per-player game goals for hat trick detection
            game_goals = {p.id: 0 for p in dressed_skaters}
            
            # Distribute goals and assists
            goals_to_distribute = team_goals
            assists_to_distribute = team_goals * random.randint(1, 2)
            
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
    
    def _check_player_records(self, player):
        """Check if player broke any records and notify if so"""
        # record_manager lives on GameManager; GUI lookup falls through to Tk.__getattr__
        # Initialize player in record manager if needed
        tracker = self.game_manager.record_manager.get_or_create_tracker(
            str(player.id), 
            player.full_name, 
            player.team_name,
            player.is_rookie
        )
        
        # Update the tracker with current stats
        self.game_manager.record_manager.player_trackers[str(player.id)] = tracker
        tracker.season_goals = player.goals
        tracker.season_assists = player.assists
        tracker.season_points = player.points
        tracker.season_games = player.games_played
        tracker.season_pim = player.penalty_minutes
        tracker.season_wins = player.wins
        tracker.season_shutouts = player.shutouts
        tracker.career_goals = player.career_goals
        tracker.career_assists = player.career_assists
        tracker.career_points = player.career_points
        tracker.career_games = player.career_games
        tracker.career_wins = player.career_wins
        tracker.career_shutouts = player.career_shutouts
        tracker.longest_point_streak = player.longest_point_streak
        tracker.longest_goal_streak = player.longest_goal_streak
        tracker.hat_tricks_season = player.hat_tricks_season
        tracker.hat_tricks_career = player.hat_tricks_career
        tracker.current_point_streak = player.current_point_streak
        tracker.current_goal_streak = player.current_goal_streak
        
        # Check for broken records
        self.game_manager.record_manager._check_for_records(tracker)
        
        # Show record breaking notifications
        recent_records = self.game_manager.record_manager.get_recent_records(1)  # Just the most recent
        if recent_records and recent_records[-1]['player_id'] == str(player.id):
            self._show_record_notification(recent_records[-1])
    
    def _show_record_notification(self, record_info):
        """Show a prominent notification when a record is broken"""
        player_name = record_info['player_name']
        record_type = record_info['record_type'].replace('_', ' ').title()
        new_value = record_info['new_value']
        is_rookie = record_info.get('is_rookie_record', False)
        team_name = record_info.get('team', 'Unknown')
        
        if is_rookie:
            title = "🌟 ROOKIE RECORD BROKEN! 🌟"
            message = f"{player_name} has set a new ROOKIE {record_type} record with {new_value}!"
            emoji = "🌟"
        else:
            title = "🏆 NHL RECORD BROKEN! 🏆"
            message = f"{player_name} has broken the NHL {record_type} record with {new_value}!"
            emoji = "🏆"
        
        # Add to news feed
        self.add_news(f"RECORD ALERT: {message}")
        
        # Show enhanced popup notification if it's the user's team
        user_team = getattr(self, 'user_team', None)
        if user_team and team_name == user_team.team_name:
            self._show_record_achievement_popup(record_info, title, message, emoji)
        
        # Console notification
        print(f"\n🚨 {title}")
        print(f"   {message}")
        print(f"   Team: {team_name}")
        print(f"   Season: {record_info.get('season', 'Unknown')}")
        
        # Update any open records windows
        if 'stats_standings' in self.open_windows and self.open_windows['stats_standings'].winfo_exists():
            try:
                self.open_windows['stats_standings'].refresh_records_data()
            except:
                pass
    
    def _show_record_achievement_popup(self, record_info, title, message, emoji):
        """Show an enhanced record achievement popup"""
        try:
            import tkinter as tk
            import tkinter.messagebox as msgbox
            from tkinter import ttk
            
            # Create custom achievement window
            achievement_window = tk.Toplevel(self)
            achievement_window.title("Record Achievement!")
            achievement_window.configure(bg=self.BG_COLOR)
            achievement_window.geometry("500x350")
            achievement_window.resizable(False, False)
            
            # Center the window
            achievement_window.update_idletasks()
            x = (achievement_window.winfo_screenwidth() // 2) - (250)
            y = (achievement_window.winfo_screenheight() // 2) - (175)
            achievement_window.geometry(f"500x350+{x}+{y}")
            
            # Make it stay on top and grab focus
            achievement_window.attributes('-topmost', True)
            achievement_window.grab_set()
            
            # Main frame
            main_frame = ttk.Frame(achievement_window, style='Panel.TFrame')
            main_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Large emoji header
            emoji_label = ttk.Label(main_frame, text=emoji, font=('Segoe UI', 48))
            emoji_label.pack(pady=(0, 10))
            
            # Title
            title_label = ttk.Label(main_frame, text=title,
                                   font=(self.FONT_FAMILY, 16, 'bold'),
                                   foreground=self.ACCENT_COLOR,
                                   background=self.BG_COLOR)
            title_label.pack(pady=(0, 15))
            
            # Player info
            player_frame = ttk.Frame(main_frame, style='Panel.TFrame')
            player_frame.pack(fill='x', pady=(0, 15))
            
            player_label = ttk.Label(player_frame, 
                                    text=f"Player: {record_info['player_name']}",
                                    font=(self.FONT_FAMILY, 12, 'bold'),
                                    foreground='#FFFFFF',
                                    background=self.BG_COLOR)
            player_label.pack()
            
            team_label = ttk.Label(player_frame,
                                  text=f"Team: {record_info.get('team', 'Unknown')}",
                                  font=(self.FONT_FAMILY, 11),
                                  foreground='#E0E0E0',
                                  background=self.BG_COLOR)
            team_label.pack()
            
            # Record details
            record_frame = ttk.Frame(main_frame, style='Panel.TFrame')
            record_frame.pack(fill='x', pady=(0, 20))
            
            record_type_label = ttk.Label(record_frame,
                                         text=f"Record: {record_info['record_type'].replace('_', ' ').title()}",
                                         font=(self.FONT_FAMILY, 12),
                                         foreground='#E0E0E0',
                                         background=self.BG_COLOR)
            record_type_label.pack()
            
            value_label = ttk.Label(record_frame,
                                   text=f"New Record: {record_info['new_value']}",
                                   font=(self.FONT_FAMILY, 14, 'bold'),
                                   foreground='#FFD700',  # Gold
                                   background=self.BG_COLOR)
            value_label.pack(pady=(5, 0))
            
            # Congratulations message
            congrats_label = ttk.Label(main_frame,
                                      text="Congratulations on this historic achievement!",
                                      font=(self.FONT_FAMILY, 11),
                                      foreground='#B0B0B0',
                                      background=self.BG_COLOR)
            congrats_label.pack(pady=(0, 15))
            
            # Buttons
            button_frame = ttk.Frame(main_frame, style='Panel.TFrame')
            button_frame.pack(fill='x')
            
            view_records_btn = ttk.Button(button_frame, text="🏆 View Records",
                                         command=lambda: [achievement_window.destroy(), 
                                                         self.open_stats_standings_window('records')])
            view_records_btn.pack(side='left', padx=(0, 10))
            
            close_btn = ttk.Button(button_frame, text="✅ Awesome!",
                                  command=achievement_window.destroy)
            close_btn.pack(side='right')
            
            # Auto-close after 10 seconds
            achievement_window.after(10000, achievement_window.destroy)
            
        except Exception as e:
            # Fallback to simple messagebox
            try:
                import tkinter.messagebox as msgbox
                msgbox.showinfo(title, message + "\n\nCongratulations on this historic achievement!")
            except:
                pass
    
    def _update_standings_fast(self, home_team, away_team, winner, scores, went_to_ot=False):
        """Fast standings update without complex calculations"""
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

    def _simulate_game_with_viewer(self, home_team, away_team):
        """Simulate a game using the visual game viewer"""
        print(f"DEBUG: _simulate_game_with_viewer CALLED!")
        print(f"DEBUG: Starting game viewer simulation: {home_team.team_name} vs {away_team.team_name}")
        
        import tkinter as tk
        from GAME_VIEWER import launch_game_viewer
        
        print(f"Starting game viewer simulation: {home_team.team_name} vs {away_team.team_name}")
        
        # Run the advanced simulation first to get the data
        sim_engine = AdvancedGameSim(home_team, away_team)
        winner, loser, scores, events, notable_events = sim_engine.run()
        
        print(f"Simulation complete! {winner.team_name} {scores[0]} - {loser.team_name} {scores[1]}")
        print(f"Total events generated: {len(sim_engine.event_log)}")
        print(f"Notable events: {len(notable_events)}")
        
        # Prepare data for the game viewer
        game_data = {
            'event_log': sim_engine.event_log,
            'home_team': home_team.team_name,
            'away_team': away_team.team_name,
            'final_score': scores,
            'all_events': events,
            'home_roster': [p for p in home_team.roster],
            'away_roster': [p for p in away_team.roster],
            'game_stats': getattr(sim_engine, 'stats', {}),
            'state_history': getattr(sim_engine, 'state_history', []),
            'notable_events': notable_events
        }
        
        print(f"DEBUG: About to launch game viewer")
        
        # Launch the game viewer using the launch function
        # Opens as a modal Toplevel on the main window; returns when closed
        launch_game_viewer(
            event_log=sim_engine.event_log,
            duration=3600,  # Game duration in seconds
            home_team=home_team.team_name,
            away_team=away_team.team_name,
            parent=self  # HockeyManagerGUI is itself the tk.Tk root
        )
        
        print("Game viewer launched and completed")
        
        # Return the simulation results INCLUDING the sim_engine
        return winner, loser, scores, events, notable_events, sim_engine

    def _simulate_game_with_pbp_visual(self, home_team, away_team):
        """Run the modern visual play-by-play window modally for a user game.

        Opens the live PBP viewer (rink + player bubbles driven by real sim
        events) and blocks the daily-sim loop until the game is watched to
        the final whistle and the window is closed. Returns the standard
        6-tuple (winner, loser, scores, events, notable_events, sim_engine)
        so the result processes exactly like any other sim.
        """
        from pbp_visual_sim import open_pbp_window

        holder = {}
        win_ref = {}

        def _on_done(sim):
            holder['sim'] = sim
            # Capture the played event stream (carries period info for OT detection)
            try:
                holder['pbp_events'] = list(win_ref['win'].events)
            except Exception:
                holder['pbp_events'] = []
            # Only allow closing once the final whistle has played
            try:
                win_ref['win'].protocol("WM_DELETE_WINDOW", win_ref['win'].destroy)
            except Exception:
                pass

        win = open_pbp_window(self, home_team, away_team, on_complete=_on_done)
        win_ref['win'] = win
        # Prevent closing before the sim finishes: the result is needed below.
        # (Re-enabled by _on_done when game_end plays.)
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        # Failsafe: if the sim thread dies without emitting game_end, don't
        # trap the user forever — allow close after 3 minutes.
        win.after(180000, lambda: win.protocol("WM_DELETE_WINDOW", win.destroy))

        self.wait_window(win)

        sim = holder.get('sim', getattr(win, 'sim', None))
        if sim is None:
            raise RuntimeError("PBP visual sim did not produce a result")

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
        return winner, loser, scores, events, notable_events, sim

    def end_of_season(self):
        """Handle end of regular season with awards and transition options."""
        # Show season summary first (skip the modal dialog when bulk simming)
        if not getattr(self, '_bulk_simming', False):
            self._show_season_summary()

        # Reset draft flag for new season
        if hasattr(self, '_draft_held_this_year'):
            self._draft_held_this_year.clear()

        # Check if playoffs should start
        if getattr(self, '_bulk_simming', False):
            result = True  # bulk sims auto-start playoffs, matching test behavior
        else:
            result = messagebox.askyesno("Playoffs", "Start the Stanley Cup Playoffs?")
        if result:
            self.open_playoffs_window()
        else:
            # Skip directly to offseason
            self._start_offseason()
            
    def _show_season_summary(self):
        """Display end of season summary with stats and awards."""
        season_str = f"{self.league.season_year}-{self.league.season_year + 1}"
        
        # Create a summary window
        summary_window = tk.Toplevel(self)
        summary_window.title(f"🏆 {season_str} Season Summary")
        summary_window.geometry("900x700")
        summary_window.configure(background=self.BG_COLOR)
        summary_window.transient(self)
        summary_window.grab_set()
        
        # Main container with scrolling
        main_frame = ttk.Frame(summary_window, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        ttk.Label(main_frame, text=f"🏒 {season_str} Season Complete!", 
                 font=(self.FONT_FAMILY, 20, 'bold'), style='Title.TLabel').pack(pady=(0, 20))
        
        # Create notebook for different summary sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)
        
        # Awards Tab
        awards_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(awards_frame, text="🏆 Awards")
        self._create_awards_section(awards_frame)
        
        # League Leaders Tab
        leaders_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(leaders_frame, text="⭐ League Leaders")
        self._create_leaders_section(leaders_frame)
        
        # Your Team Tab
        team_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(team_frame, text="📊 Your Team")
        self._create_team_summary_section(team_frame)
        
        # Close button
        ttk.Button(main_frame, text="Continue", 
                  command=summary_window.destroy, style='TButton').pack(pady=20)
        
        # Wait for window to close
        self.wait_window(summary_window)
        
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
            ttk.Label(awards_grid, text=f"🏆 {award_name}", 
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
            
    def _calculate_season_awards(self, all_players):
        """Calculate award winners based on season performance."""
        awards = {}
        
        # Filter out players without stats
        players_with_stats = [p for p in all_players if hasattr(p, 'stats') and p.stats]
        skaters = [p for p in players_with_stats if p.primary_position.name != 'GOALIE']
        goalies = [p for p in players_with_stats if p.primary_position.name == 'GOALIE']
        
        # Hart Trophy - MVP
        if skaters:
            mvp = max(skaters, key=lambda p: getattr(p.stats, 'points', 0) + p.overall_rating() * 0.5)
            awards['Hart Trophy (MVP)'] = {
                'name': mvp.full_name,
                'team': getattr(mvp, 'team_name', 'Unknown'),
                'stats': f"{getattr(mvp.stats, 'points', 0)} pts"
            }
        else:
            awards['Hart Trophy (MVP)'] = None
            
        # Art Ross Trophy - Scoring Leader
        if skaters:
            scoring_leader = max(skaters, key=lambda p: getattr(p.stats, 'points', 0))
            awards['Art Ross Trophy (Scoring Leader)'] = {
                'name': scoring_leader.full_name,
                'team': getattr(scoring_leader, 'team_name', 'Unknown'),
                'stats': f"{getattr(scoring_leader.stats, 'goals', 0)}G {getattr(scoring_leader.stats, 'assists', 0)}A = {getattr(scoring_leader.stats, 'points', 0)} pts"
            }
        else:
            awards['Art Ross Trophy (Scoring Leader)'] = None
            
        # Rocket Richard Trophy - Goal Leader
        if skaters:
            goal_leader = max(skaters, key=lambda p: getattr(p.stats, 'goals', 0))
            awards['Rocket Richard Trophy (Goal Leader)'] = {
                'name': goal_leader.full_name,
                'team': getattr(goal_leader, 'team_name', 'Unknown'),
                'stats': f"{getattr(goal_leader.stats, 'goals', 0)} goals"
            }
        else:
            awards['Rocket Richard Trophy (Goal Leader)'] = None
            
        # Vezina Trophy - Best Goalie
        if goalies:
            best_goalie = max(goalies, key=lambda p: getattr(p.stats, 'save_percentage', 0) if hasattr(p.stats, 'save_percentage') else p.overall_rating())
            sv_pct = getattr(best_goalie.stats, 'save_percentage', 0)
            awards['Vezina Trophy (Best Goalie)'] = {
                'name': best_goalie.full_name,
                'team': getattr(best_goalie, 'team_name', 'Unknown'),
                'stats': f".{int(sv_pct * 1000) if sv_pct > 0 else 'N/A'} SV%"
            }
        else:
            awards['Vezina Trophy (Best Goalie)'] = None
            
        # Norris Trophy - Best Defenseman
        defensemen = [p for p in skaters if 'DEFENSE' in p.primary_position.name]
        if defensemen:
            best_dman = max(defensemen, key=lambda p: getattr(p.stats, 'points', 0) + p.overall_rating() * 0.3)
            awards['Norris Trophy (Best Defenseman)'] = {
                'name': best_dman.full_name,
                'team': getattr(best_dman, 'team_name', 'Unknown'),
                'stats': f"{getattr(best_dman.stats, 'points', 0)} pts"
            }
        else:
            awards['Norris Trophy (Best Defenseman)'] = None
            
        # Calder Trophy - Rookie of the Year (age <= 24 and first year)
        rookies = [p for p in skaters if p.age <= 24]
        if rookies:
            best_rookie = max(rookies, key=lambda p: getattr(p.stats, 'points', 0))
            awards['Calder Trophy (Rookie of the Year)'] = {
                'name': best_rookie.full_name,
                'team': getattr(best_rookie, 'team_name', 'Unknown'),
                'stats': f"{getattr(best_rookie.stats, 'points', 0)} pts"
            }
        else:
            awards['Calder Trophy (Rookie of the Year)'] = None
            
        return awards
    
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
                ttk.Label(parent, text=f"  {player.full_name}: {g}G {a}A = {pts} pts", 
                         style='TLabel').pack(anchor='w', padx=20)
    
    def _start_offseason(self):
        """Start the offseason phase."""
        # Age players and reset stats
        self.league.end_of_season()

        # A new schedule was generated: drop cached season dates/games so the
        # season-end safety net in simulate_day recomputes from the new slate
        # instead of the previous season's.
        self._season_last_game_date = None
        if hasattr(self, '_schedule_cache'):
            self._schedule_cache.clear()
        if hasattr(self, '_strength_cache'):
            self._strength_cache.clear()

        # Generate new draft class
        self.league.draft_prospects = generate_draft_class(num_prospects=224)  # 7 rounds × 32 teams = 224 players
        
        # Update the current date to offseason
        self.current_date = date(self.league.season_year, 7, 1)  # Jump to July 1st (Free Agency)
        
        messagebox.showinfo("Offseason", 
                           f"Welcome to the {self.league.season_year}-{self.league.season_year + 1} offseason!\n\n"
                           "• Players have aged one year\n"
                           "• Stats have been reset\n"
                           "• New draft class available\n"
                           "• Free agency is now open")
        
        self.update_all_views()
        
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
            salary_cap_percentage = player.contract.salary / SALARY_CAP
            if salary_cap_percentage < 0.05:  # Less than 5% of cap
                contract_factor = 1.3
            elif salary_cap_percentage < 0.1:  # Less than 10% of cap
                contract_factor = 1.2
            elif salary_cap_percentage > 0.15:  # More than 15% of cap
                contract_factor = 0.8
                
            # Longer contracts for good players add value, for poor players reduce value
            if player.overall_rating() >= 47 and player.contract.years_remaining >= 3:
                contract_factor *= 1.2
            elif player.overall_rating() < 44 and player.contract.years_remaining >= 3:
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
    
    def process_scouting_assignments(self):
        """Process all active scouting assignments for the day."""
        if not self.scouting_assignments:
            return  # No assignments to process
        
        # Each day, scouts have a chance to watch the players they're assigned to
        for player, scout in list(self.scouting_assignments.items()):
            # Check if player already has a scouting report
            if player.id not in self.user_team.scouting_reports:
                # Create new report if none exists
                self.user_team.scouting_reports[player.id] = ScoutingReport(
                    player=player,
                    scout=scout
                )
            
            # Get the existing report
            report = self.user_team.scouting_reports[player.id]
            
            # Determine if scout makes progress today (random chance)
            # Better scouts work faster
            scout_efficiency = (scout.judging_player_ability + scout.judging_player_potential) / 40
            viewing_chance = 0.25 * scout_efficiency  # 25% base chance adjusted by scout skill
            
            if random.random() < viewing_chance:
                # Scout viewed the player today, update the report
                report.update_report(player, scout)
                
                # Once a report reaches 'A' accuracy, remove the assignment
                if report.accuracy == 'A':
                    del self.scouting_assignments[player]
                    
                    # Add a news item
                    news_item = {
                        'date': self.current_date,
                        'type': 'scouting',
                        'story': f"Scouting Report: {scout.full_name} has completed a comprehensive " +
                                f"evaluation of {player.full_name}. " +
                                f"Projected potential: {report.scouted_potential}."
                    }
                    self.news_log.append(news_item)
        
        # Update any open scouting windows
        if 'scouting' in self.open_windows and self.open_windows['scouting'].winfo_exists():
            self.open_windows['scouting'].update_views()
    
    def generate_trade_package(self, team, player_wanted, target_value):
        """Generate a trade package from the specified team targeting the given value."""
        # Sort team's roster by value (descending)
        team_players = sorted(team.roster, key=self.calculate_player_value, reverse=True)
        
        # Don't offer top 3 players unless getting a superstar
        if player_wanted.overall_rating() < 48:
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
        """Present trade offers to the user and process their response."""
        if not offers:
            return
            
        # Group offers by player
        offers_by_player = {}
        for offer in offers:
            player = offer['player_wanted']
            if player not in offers_by_player:
                offers_by_player[player] = []
            offers_by_player[player].append(offer)
        
        # Prepare a detailed message for each player
        message = "Trade offers received:\n\n"
        
        for player, player_offers in offers_by_player.items():
            message += f"For {player.full_name} ({player.primary_position.name}, OVR: {player.overall_rating()}):\n"
            
            for i, offer in enumerate(player_offers, 1):
                team = offer['team']
                package = offer['offer']
                
                message += f"  Offer {i} from {team.team_name}:\n"
                for offered_player in package:
                    message += f"    - {offered_player.full_name} ({offered_player.primary_position.name}, OVR: {offered_player.overall_rating()})\n"
                
                message += "\n"
        
        # Add to news log
        self.news_log.append({
            'date': self.current_date,
            'story': f"Trade offers received for {len(offers_by_player)} player(s) on your trade block."
        })
        
        # Show notification to user
        messagebox.showinfo("Trade Offers Received", message)
    
    def open_roster_window(self):
        if 'roster' not in self.open_windows or not self.open_windows['roster'].winfo_exists():
            self.open_windows['roster'] = RosterWindow(self)
        self.open_windows['roster'].focus_set()

    def open_free_agency_window(self):
        if 'free_agency' not in self.open_windows or not self.open_windows['free_agency'].winfo_exists():
            self.open_windows['free_agency'] = FreeAgencyWindow(self)
        self.open_windows['free_agency'].focus_set()

    def open_trade_window(self):
        if 'trade' not in self.open_windows or not self.open_windows['trade'].winfo_exists():
            self.open_windows['trade'] = TradeWindow(self)
        self.open_windows['trade'].focus_set()

    def open_trade_deadline_center(self):
        """Open the Trade Deadline Center - only available on trade deadline day"""
        if not is_trade_deadline_day():
            messagebox.showinfo("Trade Deadline Center", 
                              "The Trade Deadline Center is only available on Trade Deadline Day (March 8th).\n\n"
                              "Check back when the deadline approaches!")
            return
            
        if 'trade_deadline' not in self.open_windows or not self.open_windows['trade_deadline'].winfo_exists():
            self.open_windows['trade_deadline'] = TradeDeadlineCenter(self)
        self.open_windows['trade_deadline'].focus_set()

    def open_draft_day_central(self):
        """Open Draft Day Central - the draft-day event hub"""
        if 'draft_central' not in self.open_windows or not self.open_windows['draft_central'].winfo_exists():
            self.open_windows['draft_central'] = DraftDayCentral(self, self.game_manager)
        self.open_windows['draft_central'].focus_set()

    def open_free_agency_frenzy(self):
        """Open Free Agent Frenzy - the July 1 event hub"""
        if 'fa_frenzy' not in self.open_windows or not self.open_windows['fa_frenzy'].winfo_exists():
            self.open_windows['fa_frenzy'] = FreeAgencyFrenzy(self, self.game_manager)
        self.open_windows['fa_frenzy'].focus_set()

    def open_fantasy_draft_window(self):
        """Open the Fantasy Draft window."""
        try:
            from fantasy_draft import FantasyDraftWindow
            
            # Check if fantasy draft is available or needed
            if not hasattr(self.game_manager, 'pending_fantasy_draft') or not self.game_manager.pending_fantasy_draft:
                messagebox.showinfo("Fantasy Draft", 
                                  "Fantasy draft is only available when starting a new game with the fantasy draft option enabled.")
                return
                
            if 'fantasy_draft' not in self.open_windows or not self.open_windows['fantasy_draft'].winfo_exists():
                self.open_windows['fantasy_draft'] = FantasyDraftWindow(self, self.game_manager)
            self.open_windows['fantasy_draft'].focus_set()
        except Exception as e:
            print(f"Error opening fantasy draft window: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not open fantasy draft window: {e}")

    def open_scouting_window(self):
        if 'scouting' not in self.open_windows or not self.open_windows['scouting'].winfo_exists():
            self.open_windows['scouting'] = ScoutingWindow(self)
        self.open_windows['scouting'].focus_set()
    
    def open_scouting_management_window(self):
        if 'scouting' not in self.open_windows or not self.open_windows['scouting'].winfo_exists():
            try:
                from modern_scouting_window import ModernScoutingWindow
                self.open_windows['scouting'] = ModernScoutingWindow(self)
            except Exception:
                self.open_windows['scouting'] = ProfessionalScoutingWindow(self)
        self.open_windows['scouting'].focus_set()
    
    def open_staff_management_window(self):
        if 'staff_management' not in self.open_windows or not self.open_windows['staff_management'].winfo_exists():
            self.open_windows['staff_management'] = StaffManagementWindow(self)
        self.open_windows['staff_management'].focus_set()
        
    def open_draft_window(self):
        if 'draft' not in self.open_windows or not self.open_windows['draft'].winfo_exists():
            self.open_windows['draft'] = DraftWindow(self)
        self.open_windows['draft'].focus_set()

    def open_schedule_window(self):
        if 'schedule' not in self.open_windows or not self.open_windows['schedule'].winfo_exists():
            self.open_windows['schedule'] = ScheduleWindow(self)
        self.open_windows['schedule'].focus_set()

    def open_finances_window(self):
        if 'finances' not in self.open_windows or not self.open_windows['finances'].winfo_exists():
            self.open_windows['finances'] = FinancesWindow(self)
        self.open_windows['finances'].focus_set()
    
    def open_news_window(self):
        if 'news' not in self.open_windows or not self.open_windows['news'].winfo_exists():
            self.open_windows['news'] = NewsWindow(self)
        self.open_windows['news'].focus_set()
    
    def open_media_center(self):
        """Open the optional Media & Press Conference Center"""
        if 'media_center' not in self.open_windows or not self.open_windows['media_center'].winfo_exists():
            self.open_windows['media_center'] = MediaCenterWindow(self)
        self.open_windows['media_center'].focus_set()
        
    def open_stats_standings_window(self, focus_tab=None):
        """Open the comprehensive Stats and Standings window with optional tab focus."""
        if 'stats_standings' not in self.open_windows or not self.open_windows['stats_standings'].winfo_exists():
            self.open_windows['stats_standings'] = StatsStandingsWindow(self)
            
        window = self.open_windows['stats_standings']
        window.focus_set()
        window.lift()
        
        # Set focus to specific tab if requested
        if focus_tab:
            window.set_focus_tab(focus_tab)
    
    def open_records_window(self):
        """Open the NHL Records in the Stats window."""
        # Open stats window focused on records tab instead of separate window
        self.open_stats_standings_window(focus_tab='records')
        
    def open_inbox_window(self):
        """Open the Email Inbox window."""
        if 'inbox' not in self.open_windows or not self.open_windows['inbox'].winfo_exists():
            self.open_windows['inbox'] = InboxWindow(self)
        self.open_windows['inbox'].focus_set()
        
    def _get_inbox_button_text(self):
        """Get the text for the inbox button with unread count."""
        unread_count = self.user_team.inbox.unread_count
        if unread_count > 0:
            return f"Inbox ({unread_count})"
        return "Inbox"
        
    def update_inbox_notification(self):
        """Update the inbox button notification."""
        if hasattr(self, 'inbox_btn'):
            self.inbox_btn.config(text=self._get_inbox_button_text())
            
    def send_email_to_user(self, message):
        """Send an email message to the user's inbox."""
        self.user_team.inbox.add_message(message)
        self.update_inbox_notification()

    # ------------------------------------------------------------------
    # Football Manager-style career systems
    # ------------------------------------------------------------------
    @property
    def career(self):
        """Lazy FM-style career state, stored on the GameManager so it survives."""
        gm = self.game_manager
        career = getattr(gm, "career", None)
        if career is None:
            career = manager_career.CareerState()
            gm.career = career
        return career

    def open_manager_hub(self):
        """Open the FM-style Manager Hub window."""
        from manager_hub_window import ManagerHubWindow
        if "manager_hub" not in self.open_windows or not self.open_windows["manager_hub"].winfo_exists():
            self.open_windows["manager_hub"] = ManagerHubWindow(self)
        self.open_windows["manager_hub"].focus_set()

    def _career_prompts_allowed(self) -> bool:
        """Interactive prompts only for manual day-by-day play."""
        return (not getattr(self, "_bulk_simming", False)
                and self.career.prompts_enabled
                and not self.career.board.sacked)

    def _process_career_daily(self):
        """FM-style daily career processing: board, happiness, youth, press."""
        try:
            career = self.career
            team = self.user_team
            if team is None:
                return
            # 1. First-run: set board expectation from squad strength
            if not career.career_start_date:
                career.career_start_date = self.current_date.isoformat()
                strength = self._career_team_strength(team)
                career.board.auto_expectation(strength)
                exp = manager_career.EXPECTATIONS[career.board.expectation]
                from game_classes import EmailMessage
                self.send_email_to_user(EmailMessage(
                    sender="Board of Directors", sender_type="Owner",
                    subject="Season expectations",
                    content=(f"Welcome to {team.team_name}.\n\n"
                             f"The board's expectation this season is: {exp['label']}.\n"
                             f"{exp['description']}\n\n"
                             f"Board confidence starts at {career.board.confidence}/100. "
                             f"Results, signings and your media handling will move it. "
                             f"If it hits zero, you're gone."),
                    date_sent=self.current_date, category="General",
                    is_important=True))
            # 2. Weekly update: happiness, concerns, training effects
            if self.current_date.weekday() == 0:
                self._career_weekly_update()
            # 3. Monthly board review (first Monday of month)
            if self.current_date.weekday() == 0 and self.current_date.day <= 7:
                self._career_board_review()
            # 4. Youth intake cycle
            self._career_youth_check()
            # 5. Matchday: scout report + pre-match presser
            self._career_matchday_pre()
        except Exception as e:
            print(f"Career daily error (non-fatal): {e}")

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

    def _career_team_games(self) -> int:
        b = self.career.board
        return b.season_wins + b.season_losses + b.season_otl

    def _career_morale_modifier(self, team) -> float:
        """Subtle goal-expectation modifier from squad morale (0.97-1.03)."""
        try:
            roster = getattr(team, "roster", []) or []
            if not roster:
                return 1.0
            avg = sum((getattr(p, "morale", 7) or 7) for p in roster) / len(roster)
            return 1.0 + (avg - 7) * 0.01
        except Exception:
            return 1.0

    def _career_weekly_update(self):
        """Happiness/concerns, training morale & injury risk, assistant advice."""
        from game_classes import EmailMessage
        team = self.user_team
        team_games = self._career_team_games()
        noteworthy = []
        for p in (getattr(team, "roster", []) or []):
            try:
                noteworthy.extend(manager_career.update_player_happiness(p, team_games))
            except Exception:
                continue
        # Training effects: morale + injury risk
        fx = self.career.training.weekly_effects()
        if fx["morale_delta"]:
            for p in (getattr(team, "roster", []) or []):
                m = getattr(p, "morale", 7) or 7
                p.morale = max(1, min(10, m + (1 if fx["morale_delta"] > 0 else -1)))
        import random as _r
        if _r.random() < 0.02 * fx["injury_risk_mult"]:
            candidates = [p for p in (getattr(team, "roster", []) or [])
                          if not getattr(p, "is_injured", False)]
            if candidates:
                victim = _r.choice(candidates)
                victim.is_injured = True
                victim.injury_type = "Training knock"
                victim.games_remaining_injured = _r.randint(1, 4)
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

    def _career_assistant_advice(self) -> str:
        """Generate a context-aware tip from the assistant coach."""
        import random as _r
        team = self.user_team
        roster = getattr(team, "roster", []) or []
        unhappy = [p for p in roster if (getattr(p, "happiness", 70) or 70) < 40]
        low_morale = sum(1 for p in roster if (getattr(p, "morale", 7) or 7) <= 4)
        tips = []
        if unhappy:
            p = _r.choice(unhappy)
            tips.append(f"{p.first_name} {p.last_name} looks unhappy — maybe a private chat would help (Manager Hub → Squad).")
        if low_morale >= 5:
            tips.append("Dressing-room morale is low. Consider a lighter training week or an encouraging team talk.")
        fx = self.career.training.weekly_effects()
        if fx["injury_risk_mult"] >= 1.5:
            tips.append("This training load is brutal — I'd schedule a recovery week before someone breaks down.")
        if not tips:
            tips.append("The squad looks in good shape. Keep the routine going.")
        return "Morning boss.\n\n" + "\n".join("• " + t for t in tips)

    def _career_board_review(self):
        """Monthly board confidence review email."""
        from game_classes import EmailMessage
        b = self.career.board
        games = self._career_team_games()
        if games == 0:
            return
        points = b.season_wins * 2 + b.season_otl
        pct = points / (games * 2)
        headline, body = b.monthly_review(pct)
        self.send_email_to_user(EmailMessage(
            sender="Board of Directors", sender_type="Owner",
            subject=headline, content=body, date_sent=self.current_date,
            category="General", is_important=b.confidence < 30))
        if b.sacked:
            self._career_handle_sack()

    def _career_handle_sack(self):
        """Board has lost patience: game-over flow."""
        from tkinter import messagebox
        self.add_news("🚨 BREAKING: The board has sacked the manager.")
        messagebox.showwarning(
            "Sacked",
            "The board has lost faith and terminated your contract.\n\n"
            "Your career at this club is over. You can start a new career "
            "from the main menu.")
        # Disable further prompts; user can keep browsing but career is over
        self.career.prompts_enabled = False

    def _career_youth_check(self):
        """April preview + July 1 academy intake."""
        from game_classes import EmailMessage, Player, PlayerPosition
        career = self.career
        year = self.current_date.year
        # Preview in April
        if self.current_date.month == 4 and self.current_date.day == 1 \
                and career.intake_preview_sent != year:
            career.intake_preview_sent = year
            self.send_email_to_user(EmailMessage(
                sender="Head of Academy", sender_type="Staff",
                subject="Youth intake preview",
                content=("Our scouts are excited about this summer's academy class. "
                         "Expect 3-6 graduates in July — a couple could push for "
                         "first-team minutes within a year."),
                date_sent=self.current_date, category="Scouting"))
        # Intake on July 1
        if self.current_date.month == 7 and self.current_date.day == 1 \
                and career.last_intake_year != year:
            career.last_intake_year = year
            import random as _r
            prospects = manager_career.generate_youth_intake(
                self.user_team.team_name, _r.randint(3, 6))
            pos_map = {"C": PlayerPosition.CENTER, "LW": PlayerPosition.LEFT_WING,
                       "RW": PlayerPosition.RIGHT_WING, "D": PlayerPosition.DEFENSE,
                       "G": PlayerPosition.GOALIE}
            added = []
            if not hasattr(self.user_team, "prospects") or self.user_team.prospects is None:
                self.user_team.prospects = []
            for pr in prospects:
                p = Player(pr["first_name"], pr["last_name"], pr["age"],
                           pos_map.get(pr["position"], PlayerPosition.CENTER))
                p.potential = pr["potential"]
                p.squad_status = "Prospect"
                p.happiness = 80
                self.user_team.prospects.append(p)
                added.append(f"{pr['first_name']} {pr['last_name']} ({pr['position']}, POT {pr['potential']})")
            career.youth_history.append({"year": year, "prospects": prospects})
            self.send_email_to_user(EmailMessage(
                sender="Head of Academy", sender_type="Staff",
                subject=f"Academy intake {year}: {len(added)} graduates",
                content=("The new academy class has graduated:\n\n" +
                         "\n".join("• " + a for a in added) +
                         "\n\nThey've been added to your prospects list."),
                date_sent=self.current_date, category="Scouting",
                is_important=True))
            self.add_news(f"🌱 Academy intake: {len(added)} prospects graduate.")

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
        self.send_email_to_user(EmailMessage(
            sender="Chief Scout", sender_type="Scout",
            subject=f"Opposition report: {report['team']}",
            content="\n".join(lines), date_sent=self.current_date,
            category="Scouting"))
        # Pre-match presser (interactive)
        if not self._career_prompts_allowed():
            return
        from manager_hub_window import PressConferenceDialog
        form_word = self._career_form_word()
        ctx = {"form_word": form_word,
               "opp": report["team"], "opp_word": report["danger_level"].lower()}
        questions = manager_career.build_prematch_presser(self.user_team, opponent, ctx)
        dlg = PressConferenceDialog(self, questions, title="Pre-Match Press Conference")
        self._career_apply_press_answers(dlg.chosen, "pre-match")

    def _career_form_word(self) -> str:
        b = self.career.board
        games = self._career_team_games()
        if games < 3:
            return "mixed"
        pct = (b.season_wins * 2 + b.season_otl) / (games * 2)
        if pct >= 0.65:
            return "excellent"
        if pct >= 0.5:
            return "decent"
        return "poor"

    def _career_apply_press_answers(self, answers, kind: str):
        """Apply press conference answer effects."""
        if not answers:
            return
        team = self.user_team
        total_morale = sum(a.get("morale_effect", 0) for a in answers)
        total_board = sum(a.get("board_effect", 0) for a in answers)
        if total_morale:
            for p in (getattr(team, "roster", []) or []):
                m = getattr(p, "morale", 7) or 7
                p.morale = max(1, min(10, m + (1 if total_morale > 0 else -1)))
        if total_board:
            self.career.board.confidence = max(0, min(100, self.career.board.confidence + total_board))
        summary = f"{kind}: " + "; ".join(a.get("label", "") for a in answers)
        self.career.press_history.append(
            {"date": self.current_date.isoformat(), "type": kind, "summary": summary})

    def _career_team_talk(self, opponent) -> float:
        """Show pre-match team talk dialog. Returns sim boost multiplier."""
        if not self._career_prompts_allowed():
            return 1.0
        from manager_hub_window import TeamTalkDialog
        my_strength = self._career_team_strength(self.user_team)
        opp_strength = self._career_team_strength(opponent)
        situation = "favorite" if my_strength > opp_strength + 5 else (
            "underdog" if opp_strength > my_strength + 5 else "even")
        if self.career.board.season_losses >= 3 and self._career_team_games() >= 4:
            # recent form check for "after_loss"
            pass
        context = {"situation": situation,
                   "opponent_name": getattr(opponent, "team_name", "the opposition")}
        dlg = TeamTalkDialog(self, self.user_team, "prematch", context)
        if dlg.result:
            _opt, _reaction, boost = dlg.result
            return boost
        return 1.0

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

            delta = self.career.board.record_result(user_won, went_ot, was_favorite)
            self.career.profile.record_result(user_won, went_ot, is_playoff=False)

            # Dressing room mood swing
            for p in (getattr(team, "roster", []) or []):
                m = getattr(p, "morale", 7) or 7
                h = getattr(p, "happiness", 70) or 70
                if user_won:
                    p.morale = min(10, m + 1)
                    p.happiness = min(100, h + 3)
                else:
                    p.morale = max(1, m - 1)
                    p.happiness = max(0, h - 3)

            if self.career.board.sacked:
                self._career_handle_sack()
                return

            # Post-match presser (interactive)
            if self._career_prompts_allowed():
                from manager_hub_window import PressConferenceDialog
                hs, aws = scores
                score_str = f"{hs}-{aws}"
                star = self._career_star_of_game(sim_engine, team)
                ctx = {"n": "a few"}
                questions = manager_career.build_postmatch_presser(
                    team, opp, user_won, went_ot, score_str, star, ctx)
                dlg = PressConferenceDialog(
                    self, questions,
                    title="Post-Match Press Conference")
                self._career_apply_press_answers(dlg.chosen, "post-match")
        except Exception as e:
            print(f"Career post-game error (non-fatal): {e}")

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
    
    def open_save_window(self):
        """Open the Save Game window."""
        if 'save_game' not in self.open_windows or not self.open_windows['save_game'].winfo_exists():
            self.open_windows['save_game'] = SaveLoadWindow(self, mode='save')
        self.open_windows['save_game'].focus_set()
        
    def open_load_window(self):
        """Open the Load Game window."""
        if 'load_game' not in self.open_windows or not self.open_windows['load_game'].winfo_exists():
            self.open_windows['load_game'] = SaveLoadWindow(self, mode='load')
        self.open_windows['load_game'].focus_set()
        
    def open_playoffs_window(self):
        """Open the NHL Playoffs window."""
        if 'playoffs' not in self.open_windows or not self.open_windows['playoffs'].winfo_exists():
            self.open_windows['playoffs'] = PlayoffWindow(self)
        self.open_windows['playoffs'].focus_set()
        
    def on_game_loaded(self):
        """Called when a game is loaded from save file."""
        self.is_new_game = False
        print("Game loaded from save - autosave enabled")
        
    def on_game_saved(self):
        """Called when game is manually saved for the first time."""
        if self.is_new_game:
            self.enable_autosave()
            
    def enable_autosave(self):
        """Enable autosave after first manual save or when loading a game."""
        self.is_new_game = False
        print("Autosave enabled - will save automatically every 24 hours")
        # Start autosave system if not already running
        if not hasattr(self, '_autosave_running'):
            self.setup_autosave()
            self._autosave_running = True
    
    def setup_autosave(self):
        """Set up automatic saving system - only for existing saves, not new games."""
        if not hasattr(self, 'save_manager'):
            self.save_manager = GameSaveManager(self)
        
        # Only enable autosave if this is not a new game
        if getattr(self, 'is_new_game', True):
            print("New game detected - autosave disabled until first manual save")
            return
        
        # Check for autosave every day
        def check_autosave():
            if hasattr(self, 'save_manager') and not getattr(self, 'is_new_game', True):
                self.save_manager.autosave()
            # Schedule next check
            self.after(24 * 60 * 60 * 1000, check_autosave)  # 24 hours in milliseconds
        
        # Start autosave checking
        self.after(60000, check_autosave)  # Start after 1 minute
    
    def setup_close_protocol(self):
        """Set up the window close protocol to prompt for saving"""
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self):
        """Handle application closing with enhanced save prompt"""
        # Check if this is a new game or if there are unsaved changes
        if getattr(self, 'is_new_game', True):
            # For new games, show enhanced save options
            response = messagebox.askyesnocancel(
                "Save Before Exit",
                "You have an unsaved game. Would you like to save before exiting?\n\n"
                "• Yes: Open save dialog with full options\n"
                "• No: Exit without saving\n"
                "• Cancel: Return to game",
                icon='question'
            )
            
            if response is True:  # Yes - show enhanced save dialog
                try:
                    # Open the enhanced save window
                    from save_load_system import SaveLoadWindow
                    save_window = SaveLoadWindow(self, mode='save')
                    
                    # Wait for the save window to close with timeout protection
                    try:
                        self.wait_window(save_window)
                    except tk.TclError:
                        # Handle case where window was already destroyed
                        pass
                    
                    # Check result and close appropriately
                    if hasattr(save_window, 'save_completed') and save_window.save_completed:
                        # Save was successful, safe to exit
                        self.destroy()
                    elif hasattr(save_window, 'was_cancelled') and save_window.was_cancelled:
                        # User cancelled, remain in game
                        pass
                    else:
                        # Unclear state, ask user
                        if messagebox.askyesno("Exit Confirmation", "Save dialog closed unexpectedly. Exit anyway?"):
                            self.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to open save dialog: {str(e)}")
                    # Ask if they still want to exit
                    if messagebox.askyesno("Exit Anyway?", "Save dialog failed. Do you still want to exit?"):
                        self.destroy()
                        
            elif response is False:  # No - exit without saving
                if messagebox.askyesno("Confirm Exit", "Are you sure you want to exit without saving?"):
                    self.destroy()
            # Cancel - do nothing, return to game
        else:
            # For existing saves, offer quick save option
            response = messagebox.askyesnocancel(
                "Exit Game",
                "Would you like to save your progress before exiting?\n\n"
                "• Yes: Quick save and exit\n"
                "• No: Exit without saving\n"
                "• Cancel: Return to game",
                icon='question'
            )
            
            if response is True:  # Yes - quick save and exit
                try:
                    if hasattr(self, 'save_manager'):
                        # Try to do a quick save using the last filename
                        success = self.save_manager.save_game(compress=True)
                        if success:
                            messagebox.showinfo("Game Saved", "Your progress has been saved!")
                            self.destroy()
                        else:
                            # If quick save fails, offer enhanced save dialog
                            if messagebox.askyesno("Quick Save Failed", "Quick save failed. Open save dialog instead?"):
                                from save_load_system import SaveLoadWindow
                                save_window = SaveLoadWindow(self, mode='save')
                                try:
                                    self.wait_window(save_window)
                                except tk.TclError:
                                    pass
                                if hasattr(save_window, 'save_completed') and save_window.save_completed:
                                    self.destroy()
                    else:
                        # No save manager, show enhanced save dialog
                        from save_load_system import SaveLoadWindow
                        save_window = SaveLoadWindow(self, mode='save')
                        try:
                            self.wait_window(save_window)
                        except tk.TclError:
                            pass
                        if hasattr(save_window, 'save_completed') and save_window.save_completed:
                            self.destroy()
                            
                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save: {str(e)}")
                    if messagebox.askyesno("Exit Anyway?", "Save failed. Do you still want to exit?"):
                        self.destroy()
                        
            elif response is False:  # No - exit without saving
                if messagebox.askyesno("Confirm Exit", "Are you sure you want to exit without saving?"):
                    self.destroy()
            # Cancel - do nothing, return to game
            
    def open_calendar_window(self):
        """Open the Season Calendar window."""
        if 'calendar' not in self.open_windows or not self.open_windows['calendar'].winfo_exists():
            self.open_windows['calendar'] = CalendarWindow(self)
        self.open_windows['calendar'].focus_set()

    def open_gm_options_window(self):
        if 'gm_options' not in self.open_windows or not self.open_windows['gm_options'].winfo_exists():
            self.open_windows['gm_options'] = GMOptionsWindow(self)
        self.open_windows['gm_options'].focus_set()
        
    def open_settings_window(self):
        """Open the comprehensive settings window."""
        if 'settings' not in self.open_windows or not self.open_windows['settings'].winfo_exists():
            from settings_window import SettingsWindow
            self.open_windows['settings'] = SettingsWindow(self)
        self.open_windows['settings'].focus_set()
        
    def apply_settings(self, settings):
        """Apply settings changes from the settings window."""
        self.user_settings = settings
        print(f"Settings applied: {settings}")
        # TODO: Apply specific settings to relevant components
        
    def get_settings(self):
        """Get current user settings or defaults."""
        if not hasattr(self, 'user_settings'):
            # Load default settings if not already loaded
            try:
                from settings_window import SettingsWindow
                temp_settings = SettingsWindow(self)
                self.user_settings = temp_settings.settings
                temp_settings.destroy()
            except:
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
        
    def open_edit_lines_window(self):
        if 'edit_lines' not in self.open_windows or not self.open_windows['edit_lines'].winfo_exists():
            # Use the clean, simple EditLinesWindow from main.py instead of the complex one
            self.open_windows['edit_lines'] = CleanEditLinesWindow(self)
        self.open_windows['edit_lines'].focus_set()
        
    def open_development_window(self):
        """Open the Player Development window."""
        if 'development' not in self.open_windows or not self.open_windows['development'].winfo_exists():
            from player_development_window_professional import PlayerDevelopmentWindowProfessional
            self.open_windows['development'] = PlayerDevelopmentWindowProfessional(self)
        self.open_windows['development'].focus_set()
    
    def open_development_overview(self):
        """Open the Development Overview window."""
        self.open_development_window()
    
    def open_practice_center(self):
        """Open the Practice Center window for active roster players."""
        if 'practice_center' not in self.open_windows or not self.open_windows['practice_center'].winfo_exists():
            from enhanced_practice_system import PracticeCenterWindow
            self.open_windows['practice_center'] = PracticeCenterWindow(self)
        self.open_windows['practice_center'].focus_set()
        
    def open_trade_block_window(self):
        """Open the Trade Block management window."""
        if 'trade_block' not in self.open_windows or not self.open_windows['trade_block'].winfo_exists():
            self.open_windows['trade_block'] = TradeBlockWindow(self)
        self.open_windows['trade_block'].focus_set()
        
    def open_contract_extensions_window(self):
        """Open the Contract Extensions window."""
        if 'contract_extensions' not in self.open_windows or not self.open_windows['contract_extensions'].winfo_exists():
            self.open_windows['contract_extensions'] = ContractExtensionsWindow(self)
        self.open_windows['contract_extensions'].focus_set()

    def open_waivers_window(self):
        """Open the Waivers management window."""
        if 'waivers' not in self.open_windows or not self.open_windows['waivers'].winfo_exists():
            self.open_windows['waivers'] = WaiversWindow(self)
        self.open_windows['waivers'].focus_set()

    def open_set_captains_window(self):
        """Open the Set Captains window."""
        if 'set_captains' not in self.open_windows or not self.open_windows['set_captains'].winfo_exists():
            self.open_windows['set_captains'] = SetCaptainsWindow(self)
        self.open_windows['set_captains'].focus_set()
        
    def convert_roster_to_position_specific(self):
        """Convert all players in the roster to the position-specific attribute system."""
        if not POSITION_SPECIFIC_ATTRIBUTES_AVAILABLE:
            messagebox.showerror("Error", "Position-specific attributes system is not available.")
            return
            
        # Convert NHL and AHL rosters
        count = 0
        for player_list in [self.user_team.roster, self.user_team.ahl_roster]:
            for i, player in enumerate(player_list[:]):
                if not isinstance(player, PlayerV2):
                    # Convert the player to PlayerV2
                    v2_player = convert_to_v2(player)
                    player_list[i] = v2_player
                    count += 1
        
        if count > 0:
            messagebox.showinfo("Conversion Complete", f"Successfully converted {count} players to the position-specific attribute system.")
            self.update_all_views()
        else:
            messagebox.showinfo("No Changes", "All players are already using the position-specific attribute system.")

    def _create_treeview(self, parent, columns, height=15, is_staff=False, context_type='default'):
        tree = ttk.Treeview(parent, columns=list(columns.keys()), show='headings', height=height)
        for col, (text, width) in columns.items():
            tree.heading(col, text=text, command=lambda c=col, t=tree: self._sort_treeview_generic(t, c))
            tree.column(col, width=width, anchor='center')
        
        self._bind_player_context_menu(tree, context_type, is_staff)
        return tree

    def _sort_treeview_generic(self, tree, col):
        """Generic sorting method for treeviews that works for any treeview widget."""
        # Get current sorting state for this tree
        tree_id = str(tree)
        if not hasattr(self, '_sort_info'):
            self._sort_info = {}
            
        if tree_id not in self._sort_info:
            self._sort_info[tree_id] = {'column': None, 'reverse': False}
            
        # Toggle sort order
        if self._sort_info[tree_id]['column'] == col:
            self._sort_info[tree_id]['reverse'] = not self._sort_info[tree_id]['reverse']
        else:
            self._sort_info[tree_id]['column'] = col
            self._sort_info[tree_id]['reverse'] = False
            
        # Sort by column
        data = []
        for item_id in tree.get_children(''):
            values = tree.item(item_id, 'values')
            data.append((values, item_id))
            
        # Clean and convert value for sorting
        def get_sort_value(item, col_idx):
            val = item[0][col_idx]
            # Try to convert to number if possible
            if isinstance(val, str):
                # Remove special characters for numeric conversion
                cleaned = val.replace('$', '').replace(',', '').replace('#', '').replace('✔', '')
                cleaned = cleaned.replace('☑', '').replace('☐', '')
                try:
                    return int(cleaned)
                except ValueError:
                    try:
                        return float(cleaned)
                    except ValueError:
                        return val.lower()  # Case-insensitive string comparison
            return val
            
        # Get column index
        columns = tree['columns']
        col_idx = columns.index(col)
        
        # Sort the data
        data.sort(key=lambda x: get_sort_value(x, col_idx), 
                  reverse=self._sort_info[tree_id]['reverse'])
                  
        # Rearrange items in the tree
        for idx, (_, item_id) in enumerate(data):
            tree.move(item_id, '', idx)
        
        # Update the headings to show sort direction
        for c in columns:
            if c == col:
                tree.heading(c, text=tree.heading(c, 'text').rstrip(' ↑').rstrip(' ↓') + 
                             (' ↑' if not self._sort_info[tree_id]['reverse'] else ' ↓'))
            else:
                # Remove arrows from other columns
                text = tree.heading(c, 'text')
                if text.endswith(' ↑') or text.endswith(' ↓'):
                    tree.heading(c, text=text[:-2])

    def _populate_player_tree(self, tree, players, trade_view=False):
        tree.delete(*tree.get_children())
        tree_map = {}
        for player in sorted(players, key=lambda p: p.overall_rating(), reverse=True):
            if trade_view:
                values = (player.full_name, player.overall_rating())
            else:
                salary_str = f"${player.contract.salary:,}" if player.contract.years_remaining > 0 else "Unsigned"
                values = (player.captaincy or '', f"#{player.jersey_number}", player.full_name, player.primary_position.name, player.age, player.overall_rating(), player.potential_grade, player.morale, salary_str)
            item_id = tree.insert('', 'end', values=values)
            tree_map[item_id] = player
        self.tree_maps[tree] = tree_map
        
    def _populate_staff_tree(self, tree, staff_list):
        tree.delete(*tree.get_children())
        tree_map = {}
        for staff in staff_list:
            values = (staff.full_name, staff.role.value, staff.judging_player_ability, staff.judging_player_potential)
            item_id = tree.insert('', 'end', values=values)
            tree_map[item_id] = staff
        self.tree_maps[tree] = tree_map

    def _bind_player_context_menu(self, tree, context_type, is_staff):
        if is_staff:
            tree.bind("<Button-3>", lambda event: self._show_staff_context_menu(event, tree))
        else:
            tree.bind("<Button-3>", lambda event: self._show_player_context_menu(event, tree, context_type))
            # Add double-click event to open player profile
            tree.bind("<Double-1>", lambda event: self._handle_player_double_click(event, tree))

    def _show_player_context_menu(self, event, tree, context_type):
        item_id = tree.identify_row(event.y)
        if not item_id: return
        tree.selection_set(item_id)
        player = self.tree_maps.get(tree, {}).get(item_id)
        if not player: return

        menu = tk.Menu(self, tearoff=0, bg="#3C3C3C", fg="white")
        menu.add_command(label="View Player Profile", command=lambda: self.open_player_profile(player))
        
        if context_type in ['nhl_roster', 'ahl_roster']:
            menu.add_command(label="Assign Jersey Number...", command=lambda: self.assign_jersey_number(player))
            if player.contract.years_remaining == 1:
                menu.add_command(label="Negotiate Extension", command=lambda: self.open_contract_negotiation_window(player, is_extension=True))

        if context_type == 'nhl_roster':
            menu.add_command(label="Send to AHL", command=lambda: self.send_to_ahl(player))
        elif context_type == 'ahl_roster':
            menu.add_command(label="Call up to NHL", command=lambda: self.call_up_to_nhl(player))
        elif context_type == 'free_agent':
            menu.add_command(label="Offer Contract", command=lambda: self.open_contract_negotiation_window(player))
            
        menu.tk_popup(event.x_root, event.y_root)
        
    def _handle_player_double_click(self, event, tree):
        """Handle double-clicking on a player in any tree view."""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
            
        tree.selection_set(item_id)
        player = self.tree_maps.get(tree, {}).get(item_id)
        if not player:
            return
            
        # Open the enhanced player profile by default
        self.open_player_profile(player)

    def _show_staff_context_menu(self, event, tree):
        item_id = tree.identify_row(event.y)
        if not item_id: return
        tree.selection_set(item_id)
        staff = self.tree_maps.get(tree, {}).get(item_id)
        if not staff: return

        menu = tk.Menu(self, tearoff=0, bg="#3C3C3C", fg="white")
        menu.add_command(label="Offer Contract", command=lambda: messagebox.showinfo("WIP", "Staff contracts not yet implemented."))
        menu.tk_popup(event.x_root, event.y_root)

    def open_player_profile(self, player):
        """
        Opens the player profile window with detailed player information.
        
        Args:
            player: The player object to display
        """
        report = self.user_team.scouting_reports.get(player.id)
        is_scouted = report is not None
        
        # Use the standard player profile window
        PlayerProfileWindow(self, player, is_scouted, report)
        
    def send_to_ahl(self, player):
        self.user_team.roster.remove(player)
        self.user_team.ahl_roster.append(player)
        self.update_all_views()

    def call_up_to_nhl(self, player):
        self.user_team.ahl_roster.remove(player)
        self.user_team.roster.append(player)
        self.update_all_views()
        
    def open_contract_negotiation_window(self, player, is_extension=False):
        if 'contract' not in self.open_windows or not self.open_windows['contract'].winfo_exists():
            self.open_windows['contract'] = ContractNegotiationWindow(self, player, is_extension)
        self.open_windows['contract'].focus_set()

    def handle_contract_offer(self, person, extension=False):
        # NHL contract rules:
        min_salary = 750_000
        max_salary = int(0.20 * SALARY_CAP)
        max_years = 8 if extension else 7

        # Defensive: ensure salary and contract_years attributes exist
        salary = getattr(person, "salary", getattr(person.contract, "salary", min_salary))
        years = getattr(person, "contract_years", getattr(person.contract, "years_remaining", 1))
        person.salary = salary
        person.contract_years = years

        if salary < min_salary:
            messagebox.showerror("Error", f"Minimum salary is ${min_salary:,}.")
            return False
        if salary > max_salary:
            messagebox.showerror("Error", f"Maximum salary is ${max_salary:,}.")
            return False
        if years > max_years:
            messagebox.showerror("Error", f"Maximum contract length is {max_years} years.")
            return False
        if self.user_team.payroll + salary > PLAYER_BUDGET:
            messagebox.showerror("Error", "This contract would exceed the player budget.")
            return False

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
            accepted = person.negotiate_contract(salary, 2)
            if accepted:
                person.contract_years = 2
                person.salary = salary
                if hasattr(person, "contract"):
                    person.contract.salary = salary
                    person.contract.years_remaining = 2
            return accepted

        # Simple AI logic for contract negotiation
        asking_price = 750000 + (person.overall_rating() * 100000)
        
        if person.salary >= asking_price * 0.9: # Accepts if offer is 90% or more of asking
            messagebox.showinfo("Contract Accepted", f"{person.full_name} has accepted your contract offer!")
            person.contract.salary = person.salary
            person.contract.years_remaining = person.contract_years
            if not extension:
                self.league.free_agents.remove(person)
                self.user_team.add_player(person, "roster")
            self.news_log.append({'date': self.current_date, 'story': f"The {self.user_team.team_name} have signed {person.full_name} to a {person.contract_years}-year contract."})
            
            # Generate media event for signing (if media system enabled)
            if hasattr(self, 'media_system') and self.media_system:
                contract_type = 'extension' if extension else 'signing'
                self.media_system.process_signing(person, self.user_team, contract_type, person.salary, person.contract_years)
            
            self.update_all_views()
        elif person.salary >= asking_price * 0.7: # Counter-offers if between 70-90%
            messagebox.showinfo("Counter Offer", f"{person.full_name} has rejected your offer, but is willing to sign for ${asking_price:,} per year.")
        else: # Rejects if below 70%
            messagebox.showerror("Contract Rejected", f"{person.full_name} has rejected your contract offer.")

    def assign_jersey_number(self, player):
        new_number = simpledialog.askinteger("Assign Jersey Number", f"Enter a new jersey number for {player.full_name}:", initialvalue=player.jersey_number)
        if new_number:
            player.jersey_number = new_number
            self.update_all_views()

    def set_best_lines(self):
        """Sets the user's team lineup to the best lines for all positions and refreshes the UI."""
        best = best_lines(self.user_team)
        self.user_team.lineup = {
            'Forwards': best['Forwards'],
            'Defense': best['Defense'],
            'Goalies': best['Goalies']
        }
        self.update_all_views()
        messagebox.showinfo("Lines Updated", "Your team's best lines have been set!")

class CleanEditLinesWindow(tk.Toplevel):
    """Clean, simple, and intuitive line editor with proper contrast and readability"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Edit Lines")
        self.geometry("1000x700")
        self.configure(bg=parent.BG_COLOR)
        self.resizable(True, True)
        
        # Make text more readable with better contrast
        self.LABEL_BG = parent.CONTENT_BG  # Dark background for labels
        self.ENTRY_BG = '#FFFFFF'  # White background for input fields
        self.ENTRY_FG = '#000000'  # Black text on white background
        self.LABEL_FG = parent.TEXT_COLOR  # Light text on dark background
        
        # Configure custom style for perfect readability
        self.style = ttk.Style()
        self.style.configure('Clean.TCombobox',
                            fieldbackground='white',
                            background='white', 
                            foreground='black',
                            borderwidth=1,
                            relief='solid',
                            selectbackground='#4CAF50',
                            selectforeground='white',
                            font=(parent.FONT_FAMILY, 10))
        
        # Modern styling
        self.style.configure('Modern.TFrame',
                            background='#f8f9fa',
                            relief='flat',
                            borderwidth=0)
        
        self.style.configure('Card.TFrame',
                            background='white',
                            relief='solid',
                            borderwidth=1)
        
        self.style.configure('Header.TLabel',
                            background='#343a40',
                            foreground='white',
                            font=(parent.FONT_FAMILY, 12, 'bold'),
                            padding=10)
        
        # Drag and drop state
        self.drag_data = {"item": None, "source": None}
        self.player_widgets = {}  # Track all player display widgets
        
        # Initialize lineup data
        self.lineup = getattr(parent.user_team, "lineup", None)
        if not self.lineup:
            self.lineup = best_lines(parent.user_team)
        parent.user_team.lineup = self.lineup
        
        # Get players organized by position
        self.forwards = [p for p in parent.user_team.roster 
                        if p.primary_position.name in ['LEFT_WING', 'CENTER', 'RIGHT_WING']]
        self.defensemen = [p for p in parent.user_team.roster 
                          if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE', 'DEFENSE']]
        self.goalies = [p for p in parent.user_team.roster 
                       if p.primary_position.name == 'GOALIE']
        
        # Sort by overall rating
        self.forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
        self.defensemen.sort(key=lambda p: p.overall_rating(), reverse=True)
        self.goalies.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Create the interface
        self.create_clean_interface()
        self.load_current_lineup()
        self.refresh_all_line_ratings()
    
    def create_team_overview(self, parent_frame):
        """Create a quick team overview with key stats"""
        overview_frame = ttk.LabelFrame(parent_frame, text="Team Overview", padding=10, style='TLabelframe')
        overview_frame.pack(fill=tk.X, pady=5)
        
        # Calculate team stats
        total_players = len(self.parent.user_team.roster)
        avg_rating = sum(p.overall_rating() for p in self.parent.user_team.roster) / max(total_players, 1)
        
        # Top line rating
        if self.lineup and 'Forwards' in self.lineup and self.lineup['Forwards']:
            top_line = [p for p in self.lineup['Forwards'][0] if p is not None]
            top_line_rating = sum(p.overall_rating() for p in top_line) / max(len(top_line), 1) if top_line else 0
        else:
            top_line_rating = 0
        
        # Create info labels
        info_frame = ttk.Frame(overview_frame)
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text=f"Team Avg: {avg_rating:.1f}", 
                 style='TLabel', font=(self.parent.FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(info_frame, text=f"Top Line: {top_line_rating:.1f}", 
                 style='TLabel', font=(self.parent.FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(info_frame, text=f"Roster Size: {total_players}", 
                 style='TLabel', font=(self.parent.FONT_FAMILY, 9)).pack(side=tk.LEFT)
    
    def create_roster_panel(self, parent_paned):
        """Create the draggable player roster panel"""
        roster_frame = tk.Frame(parent_paned, bg='#f8f9fa', relief='flat', bd=0)
        parent_paned.add(roster_frame, weight=1)  # Takes less space
        
        # Modern header with subtle styling
        header_frame = tk.Frame(roster_frame, bg='#495057', height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        header_content = tk.Frame(header_frame, bg='#495057')
        header_content.pack(expand=True, fill='both', padx=15, pady=10)
        
        tk.Label(header_content, text="🏒 Active Roster", 
                bg='#495057', fg='white',
                font=(self.parent.FONT_FAMILY, 14, 'bold')).pack(side=tk.LEFT)
        
        tk.Label(header_content, text="Drag to Assign", 
                bg='#495057', fg='#adb5bd',
                font=(self.parent.FONT_FAMILY, 9)).pack(side=tk.RIGHT)
        
        # Create notebook for different position groups with subtle styling
        notebook_frame = tk.Frame(roster_frame, bg='#f8f9fa')
        notebook_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        roster_notebook = ttk.Notebook(notebook_frame, style='TNotebook')
        roster_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Position tabs
        self.create_forwards_roster_tab(roster_notebook)
        self.create_defense_roster_tab(roster_notebook)
        self.create_goalies_roster_tab(roster_notebook)
    
    def create_forwards_roster_tab(self, notebook):
        """Create draggable forwards roster"""
        forwards_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(forwards_frame, text="Forwards")
        
        # Create scrollable frame
        canvas = tk.Canvas(forwards_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(forwards_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make sure the scrollable frame stretches to fill canvas width
            canvas_width = event.width
            canvas.itemconfig(window_id, width=canvas_width)
        
        canvas.bind('<Configure>', configure_scroll_region)
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add draggable player widgets
        for i, player in enumerate(self.forwards):
            self.create_draggable_player_widget(scrollable_frame, player, "forward")
    
    def create_defense_roster_tab(self, notebook):
        """Create draggable defense roster"""
        defense_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(defense_frame, text="Defense")
        
        # Create scrollable frame
        canvas = tk.Canvas(defense_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(defense_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make sure the scrollable frame stretches to fill canvas width
            canvas_width = event.width
            canvas.itemconfig(window_id, width=canvas_width)
        
        canvas.bind('<Configure>', configure_scroll_region)
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add draggable player widgets
        for i, player in enumerate(self.defensemen):
            self.create_draggable_player_widget(scrollable_frame, player, "defense")
    
    def create_goalies_roster_tab(self, notebook):
        """Create draggable goalies roster"""
        goalies_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(goalies_frame, text="Goalies")
        
        # Add draggable player widgets
        for i, player in enumerate(self.goalies):
            self.create_draggable_player_widget(goalies_frame, player, "goalie")
    
    def create_draggable_player_widget(self, parent, player, position_type):
        """Create a draggable player widget with comprehensive info"""
        # Darker player card with modern styling - easier on the eyes
        player_frame = tk.Frame(parent, bg='#495057', relief='flat', bd=0, cursor='hand2')
        player_frame.pack(fill=tk.X, pady=3, padx=8)
        
        # Darker card with rounded appearance
        card_inner = tk.Frame(player_frame, bg='#6c757d', relief='flat', bd=0)
        card_inner.pack(fill=tk.X, padx=1, pady=1)
        
        # Bind drag events
        for widget in [player_frame, card_inner]:
            widget.bind('<Button-1>', lambda e: self.start_drag(e, player, player_frame))
            widget.bind('<B1-Motion>', self.on_drag)
            widget.bind('<ButtonRelease-1>', self.end_drag)
        
        # Player info layout with darker styling
        info_frame = tk.Frame(card_inner, bg='#6c757d')
        info_frame.pack(fill=tk.X, padx=12, pady=8)
        
        # Top row - Name and rating with modern typography
        top_row = tk.Frame(info_frame, bg='#6c757d')
        top_row.pack(fill=tk.X)
        
        name_label = tk.Label(top_row, text=player.full_name, bg='#6c757d', fg='white',
                             font=(self.parent.FONT_FAMILY, 10, 'bold'), anchor='w')
        name_label.pack(side=tk.LEFT)
        
        # Accent rating badge
        rating_frame = tk.Frame(top_row, bg='#343a40', relief='flat')
        rating_frame.pack(side=tk.RIGHT)
        
        rating_label = tk.Label(rating_frame, text=str(player.overall_rating()), bg='#343a40', fg='white',
                               font=(self.parent.FONT_FAMILY, 9, 'bold'), padx=6, pady=2)
        rating_label.pack()
        
        # Middle row - Position and condition with darker styling
        middle_row = tk.Frame(info_frame, bg='#6c757d')
        middle_row.pack(fill=tk.X, pady=(4, 0))
        
        pos_label = tk.Label(middle_row, text=f"📍 {player.primary_position.name}", bg='#6c757d', fg='#f8f9fa',
                            font=(self.parent.FONT_FAMILY, 8))
        pos_label.pack(side=tk.LEFT)
        
        # Darker condition indicator
        condition = getattr(player, 'condition', 100)
        condition_color = '#343a40'  # Dark gray for all conditions
        condition_text = "🟢" if condition > 85 else "🟡" if condition > 70 else "🔴"
        
        condition_frame = tk.Frame(middle_row, bg=condition_color, relief='flat')
        condition_frame.pack(side=tk.RIGHT)
        
        condition_label = tk.Label(condition_frame, text=f"{condition_text} {condition}%", 
                                  bg=condition_color, fg='white',
                                  font=(self.parent.FONT_FAMILY, 8, 'bold'), padx=4, pady=1)
        condition_label.pack()
        
        # Bottom row - Stats if available
        if hasattr(player, 'stats'):
            bottom_row = tk.Frame(info_frame, bg='#6c757d')
            bottom_row.pack(fill=tk.X, pady=(2, 0))
            
            goals = getattr(player.stats, 'goals', 0)
            assists = getattr(player.stats, 'assists', 0)
            stats_label = tk.Label(bottom_row, text=f"⚽ {goals}G  🎯 {assists}A", bg='#6c757d', fg='#f8f9fa',
                                  font=(self.parent.FONT_FAMILY, 8))
            stats_label.pack(side=tk.LEFT)
        
        # Store reference for tracking
        self.player_widgets[player.id] = {
            'widget': player_frame,
            'player': player,
            'position_type': position_type,
            'assigned_position': None
        }
        
        # Bind drag events to all child widgets
        for widget in [info_frame, top_row, middle_row, name_label, rating_frame, rating_label, 
                      pos_label, condition_frame, condition_label]:
            widget.bind('<Button-1>', lambda e: self.start_drag(e, player, player_frame))
            widget.bind('<B1-Motion>', self.on_drag)
            widget.bind('<ButtonRelease-1>', self.end_drag)
    
    def create_clean_interface(self):
        """Create a clean, easy-to-read interface"""
        # Modern header with gradient-like appearance
        header_frame = tk.Frame(self, bg='#343a40', height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # Header content
        header_content = tk.Frame(header_frame, bg='#343a40')
        header_content.pack(expand=True, fill='both', padx=20, pady=15)
        
        title_label = tk.Label(header_content, text="🏒 Line Editor", 
                              bg='#343a40', fg='white', 
                              font=(self.parent.FONT_FAMILY, 18, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        # Modern action buttons in header
        header_buttons = tk.Frame(header_content, bg='#343a40')
        header_buttons.pack(side=tk.RIGHT)
        
        # Stylish buttons
        self.create_modern_button(header_buttons, "Auto Best Lines", self.auto_populate_best_lines, 
                                 bg='#28a745', hover_bg='#218838')
        self.create_modern_button(header_buttons, "Save Lines", self.save_lines_with_feedback, 
                                 bg='#007bff', hover_bg='#0056b3')
        self.create_modern_button(header_buttons, "Reset", self.reset_lines, 
                                 bg='#6c757d', hover_bg='#545b62')
        
        instruction_label = tk.Label(header_content, 
                                   text="Drag players from the roster to positions • Auto-assign or manually build your lines", 
                                   bg='#343a40', fg='#adb5bd', 
                                   font=(self.parent.FONT_FAMILY, 10))
        instruction_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # Team overview in a modern card
        stats_card = tk.Frame(self, bg='white', relief='solid', bd=1)
        stats_card.pack(fill=tk.X, padx=20, pady=10)
        
        self.create_team_overview(stats_card)
        
        # Main content with modern styling
        content_frame = tk.Frame(self, bg='#f8f9fa')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Create main layout with roster panel and tabs
        main_paned = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Player roster panel
        self.create_roster_panel(main_paned)
        
        # Right side - Line editing tabs
        self.notebook = ttk.Notebook(main_paned, style='TNotebook')
        main_paned.add(self.notebook, weight=3)  # Takes more space
        
        # Create tabs
        self.create_forwards_tab()
        self.create_defense_tab()
        self.create_goalies_tab()
        self.create_special_teams_tab()
    
    def create_modern_button(self, parent, text, command, bg='#007bff', hover_bg='#0056b3'):
        """Create a modern styled button with hover effects"""
        button = tk.Button(parent, text=text, command=command,
                          bg=bg, fg='white', border=0, relief='flat',
                          font=(self.parent.FONT_FAMILY, 10, 'bold'),
                          padx=15, pady=8, cursor='hand2')
        button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Hover effects
        def on_enter(e):
            button.config(bg=hover_bg)
        def on_leave(e):
            button.config(bg=bg)
        
        button.bind('<Enter>', on_enter)
        button.bind('<Leave>', on_leave)
        
        return button
    
    def auto_populate_best_lines(self):
        """Automatically populate all lines with the best available players"""
        # Clear all current assignments
        self.clear_all_assignments()
        
        # Get best lineup using the existing algorithm
        best_lineup = best_lines(self.parent.user_team)
        
        # Populate forward lines
        forward_lines = best_lineup.get('Forwards', [])
        for line_idx, line in enumerate(forward_lines[:4]):  # Max 4 lines
            if line:
                for pos_idx, player in enumerate(line[:3]):  # Max 3 positions per line
                    if player:
                        zone_id = f"forward_line_{line_idx}_pos_{pos_idx}"
                        drop_zone = self.find_drop_zone_by_id(zone_id)
                        if drop_zone:
                            self.assign_player_to_zone(player, drop_zone)
        
        # Populate defense pairs
        defense_pairs = best_lineup.get('Defense', [])
        for pair_idx, pair in enumerate(defense_pairs[:3]):  # Max 3 pairs
            if pair:
                for pos_idx, player in enumerate(pair[:2]):  # Max 2 positions per pair
                    if player:
                        zone_id = f"defense_pair_{pair_idx}_pos_{pos_idx}"
                        drop_zone = self.find_drop_zone_by_id(zone_id)
                        if drop_zone:
                            self.assign_player_to_zone(player, drop_zone)
        
        # Populate goalies
        goalies_list = best_lineup.get('Goalies', [])
        for role_idx, player in enumerate(goalies_list[:2]):  # Max 2 goalies
            if player:
                zone_id = f"goalie_role_{role_idx}"
                drop_zone = self.find_drop_zone_by_id(zone_id)
                if drop_zone:
                    self.assign_player_to_zone(player, drop_zone)
        
        # Populate Power Play units
        for pp_unit in range(2):  # PP1 and PP2
            pp_key = f'PP{pp_unit + 1}'
            pp_data = best_lineup.get(pp_key, {})
            
            # PP Forwards (LW, C, RW)
            pp_forwards = pp_data.get('Forwards', [])
            position_names = ['LW', 'C', 'RW']
            for pos_idx, player in enumerate(pp_forwards[:3]):
                if player:
                    zone_id = f"powerplay_{pp_unit}_{position_names[pos_idx]}"
                    drop_zone = self.find_drop_zone_by_id(zone_id)
                    if drop_zone:
                        self.assign_player_to_zone(player, drop_zone)
            
            # PP Defense (LD, RD)
            pp_defense = pp_data.get('Defense', [])
            defense_names = ['LD', 'RD']
            for pos_idx, player in enumerate(pp_defense[:2]):
                if player:
                    zone_id = f"powerplay_{pp_unit}_{defense_names[pos_idx]}"
                    drop_zone = self.find_drop_zone_by_id(zone_id)
                    if drop_zone:
                        self.assign_player_to_zone(player, drop_zone)
        
        # Populate Penalty Kill units
        for pk_unit in range(2):  # PK1 and PK2
            pk_key = f'PK{pk_unit + 1}'
            pk_data = best_lineup.get(pk_key, {})
            
            # PK Forwards (LW, RW - only 2 forwards in PK)
            pk_forwards = pk_data.get('Forwards', [])
            forward_names = ['LW', 'RW']
            for pos_idx, player in enumerate(pk_forwards[:2]):
                if player:
                    zone_id = f"penalty_kill_{pk_unit}_{forward_names[pos_idx]}"
                    drop_zone = self.find_drop_zone_by_id(zone_id)
                    if drop_zone:
                        self.assign_player_to_zone(player, drop_zone)
            
            # PK Defense (LD, RD)
            pk_defense = pk_data.get('Defense', [])
            defense_names = ['LD', 'RD']
            for pos_idx, player in enumerate(pk_defense[:2]):
                if player:
                    zone_id = f"penalty_kill_{pk_unit}_{defense_names[pos_idx]}"
                    drop_zone = self.find_drop_zone_by_id(zone_id)
                    if drop_zone:
                        self.assign_player_to_zone(player, drop_zone)
        
        # Show success message
        self.show_modern_notification("✅ Best Lines Set", "Your optimal lineup with special teams has been automatically configured!", "success")
        
        # Refresh visual indicators
        self.refresh_roster_panel()
    
    def save_lines_with_feedback(self):
        """Save the current lineup with user feedback"""
        try:
            # Extract and save lineup
            self.save_lineup_from_interface()
            self.parent.user_team.lineup = self.lineup
            
            # Show success notification
            self.show_modern_notification("💾 Lines Saved", "Your lineup has been saved successfully!", "success")
            
        except Exception as e:
            # Show error notification
            self.show_modern_notification("❌ Save Failed", f"Error saving lineup: {str(e)}", "error")
    
    def show_modern_notification(self, title, message, notification_type="info"):
        """Show a modern notification popup"""
        # Create notification window
        notification = tk.Toplevel(self)
        notification.title(title)
        notification.geometry("350x150")
        notification.configure(bg='#1a2030')
        notification.resizable(False, False)
        
        # Center the notification
        notification.transient(self)
        notification.grab_set()
        
        # Color scheme based on type (dark theme)
        colors = {
            "success": {"bg": "#1d2b22", "border": "#28a745", "icon": "✅"},
            "error": {"bg": "#2b1d1f", "border": "#dc3545", "icon": "❌"},
            "info": {"bg": "#1b2630", "border": "#17a2b8", "icon": "ℹ️"}
        }
        
        color_scheme = colors.get(notification_type, colors["info"])
        
        # Header
        header_frame = tk.Frame(notification, bg=color_scheme["border"], height=40)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        header_content = tk.Frame(header_frame, bg=color_scheme["border"])
        header_content.pack(expand=True, fill='both', padx=15, pady=8)
        
        tk.Label(header_content, text=f"{color_scheme['icon']} {title}", 
                bg=color_scheme["border"], fg='white',
                font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(side=tk.LEFT)
        
        # Content
        content_frame = tk.Frame(notification, bg=color_scheme["bg"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        tk.Label(content_frame, text=message, bg=color_scheme["bg"], fg='#e8ecf4',
                font=(self.parent.FONT_FAMILY, 10), wraplength=300).pack()
        
        # OK button
        button_frame = tk.Frame(content_frame, bg=color_scheme["bg"])
        button_frame.pack(pady=(15, 0))
        
        ok_button = tk.Button(button_frame, text="OK", command=notification.destroy,
                             bg=color_scheme["border"], fg='white', border=0, relief='flat',
                             font=(self.parent.FONT_FAMILY, 10, 'bold'),
                             padx=20, pady=5, cursor='hand2')
        ok_button.pack()
        
        # Auto-close after 3 seconds
        notification.after(3000, notification.destroy)
    
    def clear_all_assignments(self):
        """Clear all player assignments from all drop zones"""
        for widget in self.winfo_children():
            self.clear_assignments_recursive(widget)
        
        # Reset player widget tracking
        for player_id, widget_info in self.player_widgets.items():
            widget_info['assigned_position'] = None
    
    def clear_assignments_recursive(self, widget):
        """Recursively clear all assignments"""
        if hasattr(widget, 'zone_id') and hasattr(widget, 'assigned_player'):
            if widget.assigned_player:
                self.clear_drop_zone(widget, widget.zone_id)
        
        # Check children
        for child in widget.winfo_children():
            self.clear_assignments_recursive(child)
    
    def find_drop_zone_by_id(self, zone_id):
        """Find a drop zone by its ID"""
        for widget in self.winfo_children():
            found = self.find_drop_zone_by_id_recursive(widget, zone_id)
            if found:
                return found
        return None
    
    def find_drop_zone_by_id_recursive(self, widget, zone_id):
        """Recursively find a drop zone by ID"""
        if hasattr(widget, 'zone_id') and widget.zone_id == zone_id:
            return widget
        
        # Check children
        for child in widget.winfo_children():
            found = self.find_drop_zone_by_id_recursive(child, zone_id)
            if found:
                return found
        return None
    
    def create_forwards_tab(self):
        """Create the forwards tab with horizontal LW-C-RW layout and scrolling"""
        forwards_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=20)
        self.notebook.add(forwards_frame, text="⚡ Forwards")
        
        # Create scrollable frame
        canvas = tk.Canvas(forwards_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(forwards_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make sure the scrollable frame stretches to fill canvas width
            canvas_width = event.width
            canvas.itemconfig(window_id, width=canvas_width)
        
        canvas.bind('<Configure>', configure_scroll_region)
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.forward_vars = []
        
        for i in range(4):
            # Line header with clear styling and line stats
            line_frame = ttk.LabelFrame(scrollable_frame, text=f"Line {i+1} - {self.get_line_type_name(i)}", 
                                       padding=15, style='TLabelframe')
            line_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Line info frame
            line_info_frame = ttk.Frame(line_frame)
            line_info_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Ice time suggestion
            ice_times = ["22-25 min", "18-22 min", "12-16 min", "8-12 min"]
            ttk.Label(line_info_frame, text=f"Suggested Ice Time: {ice_times[i]}", 
                     style='TLabel', font=(self.parent.FONT_FAMILY, 9, 'italic')).pack(side=tk.LEFT)
            
            # Line rating display (will be updated when players are selected)
            rating_label = ttk.Label(line_info_frame, text="Line Rating: --",
                                   style='TLabel', font=(self.parent.FONT_FAMILY, 9, 'bold'))
            rating_label.pack(side=tk.RIGHT)
            if not hasattr(self, 'forward_rating_labels'):
                self.forward_rating_labels = {}
            self.forward_rating_labels[i] = rating_label
            
            # Horizontal position layout: LW - C - RW
            positions_frame = ttk.Frame(line_frame)
            positions_frame.pack(fill=tk.X, pady=5)
            
            positions = ["Left Wing", "Center", "Right Wing"]
            line_vars = []
            
            for j, position in enumerate(positions):
                # Create position column
                pos_column = ttk.Frame(positions_frame)
                pos_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
                
                # Position label
                pos_label = ttk.Label(pos_column, text=position, 
                                     style='TLabel', font=(self.parent.FONT_FAMILY, 10, 'bold'))
                pos_label.pack(pady=(0, 5))
                
                # Drop zone for player
                drop_zone = self.create_drop_zone(pos_column, f"forward_line_{i}_pos_{j}")
                drop_zone.pack(fill=tk.BOTH, expand=True, ipady=20)
                
                line_vars.append(drop_zone)
            
            self.forward_vars.append(line_vars)
    
    def create_defense_tab(self):
        """Create the defense tab with horizontal LD-RD layout and scrolling"""
        defense_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=20)
        self.notebook.add(defense_frame, text="Defense")
        
        # Create scrollable frame
        canvas = tk.Canvas(defense_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(defense_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make sure the scrollable frame stretches to fill canvas width
            canvas_width = event.width
            canvas.itemconfig(window_id, width=canvas_width)
        
        canvas.bind('<Configure>', configure_scroll_region)
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.defense_vars = []
        
        for i in range(3):
            # Pair header with clear styling
            pair_frame = ttk.LabelFrame(scrollable_frame, text=f"Defense Pair {i+1} - {self.get_defense_pair_name(i)}", 
                                       padding=15, style='TLabelframe')
            pair_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Pair info frame
            pair_info_frame = ttk.Frame(pair_frame)
            pair_info_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Ice time suggestion
            ice_times = ["24-28 min", "20-24 min", "16-20 min"]
            ttk.Label(pair_info_frame, text=f"Suggested Ice Time: {ice_times[i]}", 
                     style='TLabel', font=(self.parent.FONT_FAMILY, 9, 'italic')).pack(side=tk.LEFT)
            
            # Pair rating display
            rating_label = ttk.Label(pair_info_frame, text="Pair Rating: --",
                                   style='TLabel', font=(self.parent.FONT_FAMILY, 9, 'bold'))
            rating_label.pack(side=tk.RIGHT)
            if not hasattr(self, 'defense_rating_labels'):
                self.defense_rating_labels = {}
            self.defense_rating_labels[i] = rating_label
            
            # Horizontal position layout: LD - RD
            positions_frame = ttk.Frame(pair_frame)
            positions_frame.pack(fill=tk.X, pady=5)
            
            positions = ["Left Defense", "Right Defense"]
            pair_vars = []
            
            for j, position in enumerate(positions):
                # Create position column
                pos_column = ttk.Frame(positions_frame)
                pos_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
                
                # Position label
                pos_label = ttk.Label(pos_column, text=position, 
                                     style='TLabel', font=(self.parent.FONT_FAMILY, 10, 'bold'))
                pos_label.pack(pady=(0, 5))
                
                # Drop zone for player
                drop_zone = self.create_drop_zone(pos_column, f"defense_pair_{i}_pos_{j}")
                drop_zone.pack(fill=tk.BOTH, expand=True, ipady=20)
                
                pair_vars.append(drop_zone)
            
            self.defense_vars.append(pair_vars)

    def get_line_type_name(self, line_index):
        """Get descriptive name for each line"""
        line_types = ["Top Line", "Second Line", "Third Line", "Fourth Line"]
        return line_types[line_index] if line_index < len(line_types) else f"Line {line_index + 1}"
    
    def get_defense_pair_name(self, pair_index):
        """Get descriptive name for each defense pair"""
        pair_types = ["Top Pair", "Second Pair", "Third Pair"]
        return pair_types[pair_index] if pair_index < len(pair_types) else f"Pair {pair_index + 1}"
    
    def get_position_role_info(self, position, line_index):
        """Get role information for position based on line"""
        role_info = {
            0: {"Left Wing": "Primary Scorer", "Center": "Playmaker", "Right Wing": "Finisher"},
            1: {"Left Wing": "Secondary Scoring", "Center": "Two-Way", "Right Wing": "Power Forward"},
            2: {"Left Wing": "Energy", "Center": "Checking", "Right Wing": "Grinder"},
            3: {"Left Wing": "Physical", "Center": "Faceoffs", "Right Wing": "Enforcer"}
        }
        return role_info.get(line_index, {}).get(position, "Versatile")
    
    def update_line_rating(self, line_index, rating_label):
        """Update the line rating display when players change"""
        if line_index >= len(self.forward_vars):
            return
            
        line_vars = self.forward_vars[line_index]
        players = []
        
        for combo, var in line_vars:
            selection = var.get()
            if selection and selection != "-- Select Player --":
                player_name = selection.split(" (")[0]
                player = next((p for p in self.forwards if p.full_name == player_name), None)
                if player:
                    players.append(player)
        
        if players:
            avg_rating = sum(p.overall_rating() for p in players) / len(players)
            chemistry_bonus = self.calculate_chemistry_bonus(players)
            final_rating = avg_rating + chemistry_bonus
            
            color = "green" if final_rating >= 85 else "orange" if final_rating >= 75 else "red"
            rating_label.config(text=f"Line Rating: {final_rating:.1f} (+{chemistry_bonus:.1f})")
        else:
            rating_label.config(text="Line Rating: --")
    
    def calculate_chemistry_bonus(self, players):
        """Calculate chemistry bonus based on player compatibility"""
        if len(players) < 2:
            return 0.0
        
        # Simple chemistry calculation based on age and attributes
        total_bonus = 0.0
        
        # Age chemistry - players within 3 years of each other get bonus
        ages = [p.age for p in players]
        age_range = max(ages) - min(ages)
        if age_range <= 3:
            total_bonus += 2.0
        elif age_range <= 5:
            total_bonus += 1.0
        
        # Nationality bonus - same country players get bonus
        if hasattr(players[0], 'nationality'):
            nationalities = [getattr(p, 'nationality', 'Unknown') for p in players]
            if len(set(nationalities)) == 1:
                total_bonus += 1.5
        
        # Attribute synergy - balanced lines get bonus
        if len(players) >= 3:
            # Check for good mix of skills
            avg_shooting = sum(getattr(p, 'shooting', 10) for p in players) / len(players)
            avg_passing = sum(getattr(p, 'passing', 10) for p in players) / len(players)
            avg_checking = sum(getattr(p, 'checking', 10) for p in players) / len(players)
            
            if min(avg_shooting, avg_passing, avg_checking) > 12:  # Well-rounded line
                total_bonus += 2.5
        
        return min(total_bonus, 5.0)  # Cap at +5 rating points
    
    def create_drop_zone(self, parent, zone_id):
        """Create a drop zone for players"""
        drop_frame = tk.Frame(parent, bg='#e9ecef', relief='flat', bd=0, height=70)
        drop_frame.pack_propagate(False)  # Maintain size
        
        # Subtle placeholder with modern styling
        placeholder_frame = tk.Frame(drop_frame, bg='#e9ecef')
        placeholder_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Subtle icon and text
        icon_label = tk.Label(placeholder_frame, text="👤", bg='#e9ecef', fg='#adb5bd',
                             font=(self.parent.FONT_FAMILY, 18))
        icon_label.pack()
        
        text_label = tk.Label(placeholder_frame, text="Drop Player Here", bg='#e9ecef', fg='#6c757d',
                             font=(self.parent.FONT_FAMILY, 9))
        text_label.pack()
        
        # Bind drop events and hover effects
        for widget in [drop_frame, placeholder_frame, icon_label, text_label]:
            widget.bind('<Button-1>', lambda e: self.clear_drop_zone(drop_frame, zone_id))
            widget.bind('<Enter>', lambda e: self.on_drop_zone_enter(drop_frame))
            widget.bind('<Leave>', lambda e: self.on_drop_zone_leave(drop_frame))
        
        # Store zone info
        drop_frame.zone_id = zone_id
        drop_frame.assigned_player = None
        drop_frame.placeholder_frame = placeholder_frame
        drop_frame.original_bg = '#e9ecef'
        
        return drop_frame
    
    def on_drop_zone_enter(self, drop_zone):
        """Handle mouse entering drop zone during drag"""
        if self.drag_data["item"] and not drop_zone.assigned_player:
            drop_zone.config(bg='#d1ecf1', relief='flat')  # Subtle blue highlight
    
    def on_drop_zone_leave(self, drop_zone):
        """Handle mouse leaving drop zone"""
        if not drop_zone.assigned_player:
            drop_zone.config(bg=drop_zone.original_bg, relief='flat')
    
    def start_drag(self, event, player, widget):
        """Start dragging a player"""
        self.drag_data["item"] = player
        self.drag_data["source"] = widget
        widget.config(relief='raised', bd=3)
        
        # Change cursor to indicate dragging
        widget.config(cursor='plus')
    
    def on_drag(self, event):
        """Handle drag motion"""
        if self.drag_data["item"]:
            # Update cursor position
            pass
    
    def end_drag(self, event):
        """Handle end of drag - check for drop targets"""
        if not self.drag_data["item"]:
            return
            
        # Reset source widget appearance
        if self.drag_data["source"]:
            self.drag_data["source"].config(relief='raised', bd=1, cursor='hand2')
        
        # Find drop target under cursor
        x, y = event.widget.winfo_pointerx(), event.widget.winfo_pointery()
        target = self.winfo_containing(x, y)
        
        if target:
            drop_zone = self.find_drop_zone_parent(target)
            if drop_zone:
                self.handle_drop(self.drag_data["item"], drop_zone)
        
        # Clear drag data
        self.drag_data = {"item": None, "source": None}
    
    def find_drop_zone_parent(self, widget):
        """Find the drop zone parent of a widget"""
        current = widget
        while current:
            if hasattr(current, 'zone_id'):
                return current
            current = current.master
        return None
    
    def handle_drop(self, player, drop_zone):
        """Handle dropping a player on a drop zone"""
        if not drop_zone or not hasattr(drop_zone, 'zone_id'):
            return
            
        # Check if player is compatible with this position
        zone_parts = drop_zone.zone_id.split('_')
        if len(zone_parts) >= 2:
            position_type = zone_parts[0]  # 'forward', 'defense', 'goalie'
            
            # Validate position compatibility
            if not self.is_position_compatible(player, position_type):
                # Show error message
                tk.messagebox.showwarning("Invalid Position", 
                                        f"{player.full_name} cannot be assigned to this position type.")
                return
        
        # Clear any existing assignment for this player
        self.clear_player_assignments(player)
        
        # Assign player to this drop zone
        self.assign_player_to_zone(player, drop_zone)
        
        # Update line ratings if it's a forward line
        if 'forward_line' in drop_zone.zone_id:
            line_idx = int(zone_parts[2]) if len(zone_parts) > 2 else 0
            self.update_line_rating_for_drop_zones(line_idx)
    
    def is_position_compatible(self, player, position_type):
        """Check if player can play this position type"""
        player_pos = player.primary_position.name
        
        # Goalies can only play goalie positions
        if player_pos == 'GOALIE':
            return position_type == "goalie"
        
        # Non-goalies can play any non-goalie position
        if position_type == "goalie":
            return False  # Only goalies can play goalie
        
        # Allow forwards and defensemen to play any forward/defense/special teams position
        return position_type in ["forward", "defense", "powerplay", "penalty_kill"]
    
    def clear_player_assignments(self, player):
        """Clear any existing assignments for this player"""
        # Update player widget tracking
        if player.id in self.player_widgets:
            self.player_widgets[player.id]['assigned_position'] = None
        
        # Find and clear any drop zones containing this player
        for widget in self.winfo_children():
            self.clear_player_from_zones_recursive(widget, player)
    
    def clear_player_from_zones_recursive(self, widget, player):
        """Recursively clear player from drop zones"""
        if hasattr(widget, 'zone_id') and hasattr(widget, 'assigned_player'):
            if widget.assigned_player and widget.assigned_player.id == player.id:
                self.clear_drop_zone(widget, widget.zone_id)
        
        # Check children
        for child in widget.winfo_children():
            self.clear_player_from_zones_recursive(child, player)
    
    def assign_player_to_zone(self, player, drop_zone):
        """Assign a player to a drop zone"""
        # Clear the drop zone first
        for widget in drop_zone.winfo_children():
            widget.destroy()
        
        # Create subtle player display in drop zone
        player_display = tk.Frame(drop_zone, bg='#dee2e6', relief='flat', bd=0)
        player_display.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Subtle assigned player card
        card_frame = tk.Frame(player_display, bg='#6c757d', relief='flat')
        card_frame.pack(fill='both', expand=True)
        
        # Player info with subtle styling
        info_frame = tk.Frame(card_frame, bg='#6c757d')
        info_frame.pack(expand=True, fill='both', padx=8, pady=6)
        
        name_label = tk.Label(info_frame, text=player.full_name, bg='#6c757d', fg='white',
                             font=(self.parent.FONT_FAMILY, 9, 'bold'))
        name_label.pack()
        
        rating_label = tk.Label(info_frame, text=f"⭐ {to_100_scale(player.overall_rating())}", bg='#6c757d', fg='white',
                               font=(self.parent.FONT_FAMILY, 8))
        rating_label.pack()
        
        # Bind click to clear with subtle feedback
        for widget in [player_display, card_frame, info_frame, name_label, rating_label]:
            widget.bind('<Button-1>', lambda e: self.clear_drop_zone(drop_zone, drop_zone.zone_id))
            widget.bind('<Enter>', lambda e: card_frame.config(bg='#dc3545'))  # Red on hover
            widget.bind('<Leave>', lambda e: card_frame.config(bg='#6c757d'))  # Back to gray
        
        # Store assignment
        drop_zone.assigned_player = player
        if player.id in self.player_widgets:
            self.player_widgets[player.id]['assigned_position'] = drop_zone.zone_id
        try:
            self._refresh_ratings_for_zone(drop_zone.zone_id)
        except AttributeError:
            pass
    
    def clear_drop_zone(self, drop_zone, zone_id):
        """Clear a drop zone"""
        # Clear assigned player
        if hasattr(drop_zone, 'assigned_player'):
            player = drop_zone.assigned_player
            if player and player.id in self.player_widgets:
                self.player_widgets[player.id]['assigned_position'] = None
        
        drop_zone.assigned_player = None
        try:
            self._refresh_ratings_for_zone(zone_id)
        except AttributeError:
            pass
        
        # Clear widgets
        for widget in drop_zone.winfo_children():
            widget.destroy()
        
        # Restore subtle placeholder
        placeholder_frame = tk.Frame(drop_zone, bg='#e9ecef')
        placeholder_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        icon_label = tk.Label(placeholder_frame, text="👤", bg='#e9ecef', fg='#adb5bd',
                             font=(self.parent.FONT_FAMILY, 20))
        icon_label.pack()
        
        text_label = tk.Label(placeholder_frame, text="Drop Player Here", bg='#e9ecef', fg='#6c757d',
                             font=(self.parent.FONT_FAMILY, 9))
        text_label.pack()
        
        # Rebind events
        for widget in [placeholder_frame, icon_label, text_label]:
            widget.bind('<Button-1>', lambda e: self.clear_drop_zone(drop_zone, zone_id))
            widget.bind('<Enter>', lambda e: self.on_drop_zone_enter(drop_zone))
            widget.bind('<Leave>', lambda e: self.on_drop_zone_leave(drop_zone))
        
        drop_zone.placeholder_frame = placeholder_frame
        
        # Update line ratings if it's a forward line
        if 'forward_line' in zone_id:
            zone_parts = zone_id.split('_')
            line_idx = int(zone_parts[2]) if len(zone_parts) > 2 else 0
            self.update_line_rating_for_drop_zones(line_idx)
    
    def update_line_rating_for_drop_zones(self, line_index):
        """Update line rating for drop zone based lines."""
        if line_index >= len(self.forward_vars):
            return
        players = [getattr(dz, 'assigned_player', None) for dz in self.forward_vars[line_index]]
        players = [p for p in players if p is not None]
        label = getattr(self, 'forward_rating_labels', {}).get(line_index)
        if label is None:
            return
        if players:
            avg = sum(p.overall_rating() for p in players) / len(players)
            chem = self.calculate_chemistry_bonus(players)
            label.config(text=f"Line Rating: {avg:.1f} (+{chem:.1f} chem)")
        else:
            label.config(text="Line Rating: --")

    def update_pair_rating_for_drop_zones(self, pair_index):
        """Update pair rating for drop zone based defense pairs."""
        if pair_index >= len(self.defense_vars):
            return
        players = [getattr(dz, 'assigned_player', None) for dz in self.defense_vars[pair_index]]
        players = [p for p in players if p is not None]
        label = getattr(self, 'defense_rating_labels', {}).get(pair_index)
        if label is None:
            return
        if players:
            avg = sum(p.overall_rating() for p in players) / len(players)
            chem = self.calculate_chemistry_bonus(players)
            label.config(text=f"Pair Rating: {avg:.1f} (+{chem:.1f} chem)")
        else:
            label.config(text="Pair Rating: --")

    def _refresh_ratings_for_zone(self, zone_id):
        """Refresh line/pair rating labels affected by a drop-zone change."""
        try:
            parts = zone_id.split("_")
            if zone_id.startswith("forward_line_"):
                self.update_line_rating_for_drop_zones(int(parts[2]))
            elif zone_id.startswith("defense_pair_"):
                self.update_pair_rating_for_drop_zones(int(parts[2]))
        except (ValueError, IndexError, AttributeError):
            pass

    def refresh_all_line_ratings(self):
        """Refresh every line and pair rating (call after initial load)."""
        for i in range(len(getattr(self, 'forward_vars', []))):
            self.update_line_rating_for_drop_zones(i)
        for i in range(len(getattr(self, 'defense_vars', []))):
            self.update_pair_rating_for_drop_zones(i)
    
    def refresh_roster_panel(self):
        """Refresh the roster panel to show current assignments"""
        # Update visual indicators on player widgets to show assignments
        for player_id, widget_info in self.player_widgets.items():
            widget = widget_info['widget']
            assigned_pos = widget_info['assigned_position']
            
            if assigned_pos:
                # Change appearance to show assigned
                widget.config(bg='#e8f5e8', relief='solid')
            else:
                # Reset to unassigned appearance
                widget.config(bg='white', relief='raised')
    
    def extract_lineup_from_drop_zones(self):
        """Extract the current lineup from all drop zones"""
        lineup = {
            'Forwards': [None] * 4,
            'Defense': [None] * 3,
            'Goalies': [None] * 2,
            'PowerPlay': [None] * 2,
            'PenaltyKill': [None] * 2
        }
        
        # Walk through all widgets to find drop zones
        self.extract_assignments_recursive(self, lineup)
        
        return lineup
    
    def extract_assignments_recursive(self, widget, lineup):
        """Recursively extract assignments from drop zones"""
        if hasattr(widget, 'zone_id') and hasattr(widget, 'assigned_player'):
            zone_id = widget.zone_id
            player = widget.assigned_player
            
            if player and zone_id:
                # Parse zone ID and assign to appropriate lineup position
                if 'forward_line' in zone_id:
                    parts = zone_id.split('_')
                    if len(parts) >= 5:
                        try:
                            line_idx = int(parts[2])
                            pos_idx = int(parts[4])
                            if line_idx < 4 and pos_idx < 3:
                                if not lineup['Forwards'][line_idx]:
                                    lineup['Forwards'][line_idx] = [None, None, None]
                                lineup['Forwards'][line_idx][pos_idx] = player
                        except ValueError:
                            pass  # Skip invalid zone IDs
                
                elif 'defense_pair' in zone_id:
                    parts = zone_id.split('_')
                    if len(parts) >= 5:
                        try:
                            pair_idx = int(parts[2])
                            pos_idx = int(parts[4])
                            if pair_idx < 3 and pos_idx < 2:
                                if not lineup['Defense'][pair_idx]:
                                    lineup['Defense'][pair_idx] = [None, None]
                                lineup['Defense'][pair_idx][pos_idx] = player
                        except ValueError:
                            pass  # Skip invalid zone IDs
                
                elif 'goalie_role' in zone_id:
                    parts = zone_id.split('_')
                    if len(parts) >= 3:
                        try:
                            role_idx = int(parts[2])
                            if role_idx < 2:
                                lineup['Goalies'][role_idx] = player
                        except ValueError:
                            pass  # Skip invalid zone IDs
                
                elif 'powerplay' in zone_id:
                    # Handle powerplay zones: powerplay_0_LW, powerplay_1_C, etc.
                    parts = zone_id.split('_')
                    if len(parts) >= 3:
                        try:
                            pp_unit = int(parts[1])  # 0 or 1
                            position = parts[2]  # LW, C, RW, LD, RD
                            
                            if pp_unit < 2:
                                if not lineup['PowerPlay'][pp_unit]:
                                    lineup['PowerPlay'][pp_unit] = {}
                                lineup['PowerPlay'][pp_unit][position] = player
                        except (ValueError, IndexError):
                            pass  # Skip invalid zone IDs
                
                elif 'penalty_kill' in zone_id:
                    # Handle penalty kill zones: penalty_kill_0_LW, penalty_kill_1_RD, etc.
                    parts = zone_id.split('_')
                    if len(parts) >= 3:
                        try:
                            pk_unit = int(parts[2])  # 0 or 1
                            position = parts[3]  # LW, RW, LD, RD
                            
                            if pk_unit < 2:
                                if not lineup['PenaltyKill'][pk_unit]:
                                    lineup['PenaltyKill'][pk_unit] = {}
                                lineup['PenaltyKill'][pk_unit][position] = player
                        except (ValueError, IndexError):
                            pass  # Skip invalid zone IDs
        
        # Check children
        for child in widget.winfo_children():
            self.extract_assignments_recursive(child, lineup)
    
    def create_goalies_tab(self):
        """Create the goalies tab with clean, readable layout"""
        goalies_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=20)
        self.notebook.add(goalies_frame, text="🥅 Goalies")
        
        self.goalie_vars = []
        roles = ["Starting Goalie", "Backup Goalie"]
        
        for i, role in enumerate(roles):
            # Goalie frame
            goalie_frame = ttk.LabelFrame(goalies_frame, text=role, 
                                         padding=15, style='TLabelframe')
            goalie_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Create drop zone instead of combobox
            drop_zone = self.create_drop_zone(goalie_frame, f"goalie_role_{i}")
            drop_zone.pack(pady=5, fill=tk.X)
            
            self.goalie_vars.append(drop_zone)
    
    def create_special_teams_tab(self):
        """Create the special teams tab with horizontal layouts and scrolling"""
        special_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=20)
        self.notebook.add(special_frame, text="⚡ Special Teams")
        
        # Create scrollable frame
        canvas = tk.Canvas(special_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(special_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make sure the scrollable frame stretches to fill canvas width
            canvas_width = event.width
            canvas.itemconfig(window_id, width=canvas_width)
        
        canvas.bind('<Configure>', configure_scroll_region)
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Power Play section
        pp_frame = ttk.LabelFrame(scrollable_frame, text="Power Play Units", padding=15, style='TLabelframe')
        pp_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.powerplay_vars = []
        
        for i in range(2):  # PP1 and PP2
            unit_frame = ttk.LabelFrame(pp_frame, text=f"Power Play {i+1}", padding=10, style='TLabelframe')
            unit_frame.pack(fill=tk.X, pady=5)
            
            # Horizontal layout: LW - C - RW - LD - RD
            positions_frame = ttk.Frame(unit_frame)
            positions_frame.pack(fill=tk.X, pady=5)
            
            unit_vars = []
            positions = ["LW", "C", "RW", "LD", "RD"]
            position_names = ["Left Wing", "Center", "Right Wing", "Left Defense", "Right Defense"]
            
            for j, (pos, pos_name) in enumerate(zip(positions, position_names)):
                # Create position column
                pos_column = ttk.Frame(positions_frame)
                pos_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
                
                # Position label
                pos_label = ttk.Label(pos_column, text=pos_name, 
                                     style='TLabel', font=(self.parent.FONT_FAMILY, 9, 'bold'))
                pos_label.pack(pady=(0, 5))
                
                # Drop zone for special teams
                drop_zone = self.create_drop_zone(pos_column, f"powerplay_{i}_{pos}")
                drop_zone.pack(fill=tk.BOTH, expand=True, ipady=15)
                
                unit_vars.append(drop_zone)
            
            self.powerplay_vars.append(unit_vars)
        
        # Penalty Kill section
        pk_frame = ttk.LabelFrame(scrollable_frame, text="Penalty Kill Units", padding=15, style='TLabelframe')
        pk_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.penalty_kill_vars = []
        
        for i in range(2):  # PK1 and PK2
            unit_frame = ttk.LabelFrame(pk_frame, text=f"Penalty Kill {i+1}", padding=10, style='TLabelframe')
            unit_frame.pack(fill=tk.X, pady=5)
            
            # Horizontal layout: LW - RW - LD - RD (4-man PK unit)
            positions_frame = ttk.Frame(unit_frame)
            positions_frame.pack(fill=tk.X, pady=5)
            
            unit_vars = []
            positions = ["LW", "RW", "LD", "RD"]  # 4-man PK unit
            position_names = ["Left Wing", "Right Wing", "Left Defense", "Right Defense"]
            
            for j, (pos, pos_name) in enumerate(zip(positions, position_names)):
                # Create position column
                pos_column = ttk.Frame(positions_frame)
                pos_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
                
                # Position label
                pos_label = ttk.Label(pos_column, text=pos_name, 
                                     style='TLabel', font=(self.parent.FONT_FAMILY, 9, 'bold'))
                pos_label.pack(pady=(0, 5))
                
                # Create drop zone for penalty kill
                drop_zone = self.create_drop_zone(pos_column, f"penalty_kill_{i}_{pos}")
                drop_zone.pack(fill=tk.BOTH, expand=True, ipady=15)
                
                unit_vars.append(drop_zone)
            
            self.penalty_kill_vars.append(unit_vars)
    
    def load_current_lineup(self):
        """Load the current lineup into the drop zones"""
        # Load forwards
        forward_lines = self.lineup.get('Forwards', [[None]*3 for _ in range(4)])
        for i, line_vars in enumerate(self.forward_vars):
            if i < len(forward_lines):
                current_line = forward_lines[i]
                for j, drop_zone in enumerate(line_vars):
                    if j < len(current_line) and current_line[j]:
                        player = current_line[j]
                        self.assign_player_to_zone(player, drop_zone)
        
        # Load defense
        defense_pairs = self.lineup.get('Defense', [[None]*2 for _ in range(3)])
        for i, pair_vars in enumerate(self.defense_vars):
            if i < len(defense_pairs):
                current_pair = defense_pairs[i]
                for j, drop_zone in enumerate(pair_vars):
                    if j < len(current_pair) and current_pair[j]:
                        player = current_pair[j]
                        self.assign_player_to_zone(player, drop_zone)
        
        # Load goalies
        goalies_list = self.lineup.get('Goalies', [None, None])
        for i, drop_zone in enumerate(self.goalie_vars):
            if i < len(goalies_list) and goalies_list[i]:
                player = goalies_list[i]
                self.assign_player_to_zone(player, drop_zone)
        
        # Load special teams
        # Load Power Play units
        for pp_unit in range(2):
            pp_key = f'PP{pp_unit + 1}'
            pp_data = self.lineup.get(pp_key, {})
            if pp_unit < len(self.powerplay_vars):
                unit_vars = self.powerplay_vars[pp_unit]
                
                # Load PP forwards (LW, C, RW)
                pp_forwards = pp_data.get('Forwards', [])
                for pos_idx in range(min(3, len(unit_vars))):
                    if pos_idx < len(pp_forwards) and pp_forwards[pos_idx]:
                        player = pp_forwards[pos_idx]
                        self.assign_player_to_zone(player, unit_vars[pos_idx])
                
                # Load PP defense (LD, RD)
                pp_defense = pp_data.get('Defense', [])
                for pos_idx in range(min(2, len(pp_defense))):
                    defense_idx = pos_idx + 3  # Defense positions are at index 3,4
                    if defense_idx < len(unit_vars) and pp_defense[pos_idx]:
                        player = pp_defense[pos_idx]
                        self.assign_player_to_zone(player, unit_vars[defense_idx])
        
        # Load Penalty Kill units
        for pk_unit in range(2):
            pk_key = f'PK{pk_unit + 1}'
            pk_data = self.lineup.get(pk_key, {})
            if pk_unit < len(self.penalty_kill_vars):
                unit_vars = self.penalty_kill_vars[pk_unit]
                
                # Load PK forwards (LW, RW)
                pk_forwards = pk_data.get('Forwards', [])
                for pos_idx in range(min(2, len(pk_forwards), len(unit_vars))):
                    if pk_forwards[pos_idx]:
                        player = pk_forwards[pos_idx]
                        self.assign_player_to_zone(player, unit_vars[pos_idx])
                
                # Load PK defense (LD, RD)
                pk_defense = pk_data.get('Defense', [])
                for pos_idx in range(min(2, len(pk_defense))):
                    defense_idx = pos_idx + 2  # Defense positions are at index 2,3 for PK
                    if defense_idx < len(unit_vars) and pk_defense[pos_idx]:
                        player = pk_defense[pos_idx]
                        self.assign_player_to_zone(player, unit_vars[defense_idx])
    
    def auto_set_best(self):
        """Automatically set the best possible lines"""
        self.auto_populate_best_lines()
        messagebox.showinfo("Lines Set", "Your best players have been automatically assigned to lines!")
    
    def reset_lines(self):
        """Reset all lines to empty"""
        self.clear_all_assignments()
        messagebox.showinfo("Reset", "All lines have been cleared!")
    
    def save_and_close(self):
        """Save the current lineup and close the window"""
        # Extract player selections and save to lineup
        self.save_lineup_from_interface()
        self.parent.user_team.lineup = self.lineup
        messagebox.showinfo("Saved", "Your lines have been saved!")
        self.destroy()
    
    def save_lineup_from_interface(self):
        """Extract player selections from drop zones and save to lineup structure"""
        # Extract from drop zones instead of comboboxes
        new_lineup = self.extract_lineup_from_drop_zones()
        
        # Convert to the expected format
        forward_lines = []
        for i in range(4):
            line = new_lineup['Forwards'][i] if new_lineup['Forwards'][i] else [None, None, None]
            forward_lines.append(line)
        
        defense_pairs = []
        for i in range(3):
            pair = new_lineup['Defense'][i] if new_lineup['Defense'][i] else [None, None]
            defense_pairs.append(pair)
        
        goalies_list = new_lineup['Goalies']
        
        # Update lineup structure
        self.lineup['Forwards'] = forward_lines
        self.lineup['Defense'] = defense_pairs
        self.lineup['Goalies'] = goalies_list
        
        # Handle special teams
        if 'PowerPlay' in new_lineup and new_lineup['PowerPlay']:
            for i, pp_unit in enumerate(new_lineup['PowerPlay']):
                if pp_unit:
                    pp_key = f'PP{i + 1}'
                    if pp_key not in self.lineup:
                        self.lineup[pp_key] = {'Forwards': [], 'Defense': []}
                    
                    # Convert position dict to lists
                    pp_forwards = [
                        pp_unit.get('LW'),
                        pp_unit.get('C'), 
                        pp_unit.get('RW')
                    ]
                    pp_defense = [
                        pp_unit.get('LD'),
                        pp_unit.get('RD')
                    ]
                    
                    self.lineup[pp_key]['Forwards'] = pp_forwards
                    self.lineup[pp_key]['Defense'] = pp_defense
        
        if 'PenaltyKill' in new_lineup and new_lineup['PenaltyKill']:
            for i, pk_unit in enumerate(new_lineup['PenaltyKill']):
                if pk_unit:
                    pk_key = f'PK{i + 1}'
                    if pk_key not in self.lineup:
                        self.lineup[pk_key] = {'Forwards': [], 'Defense': []}
                    
                    # Convert position dict to lists  
                    pk_forwards = [
                        pk_unit.get('LW'),
                        pk_unit.get('RW')
                    ]
                    pk_defense = [
                        pk_unit.get('LD'),
                        pk_unit.get('RD')
                    ]
                    
                    self.lineup[pk_key]['Forwards'] = pk_forwards
                    self.lineup[pk_key]['Defense'] = pk_defense
    
    def show_line_analytics(self):
        """Show detailed analytics for current line combinations"""
        analytics_window = tk.Toplevel(self)
        analytics_window.title("🏒 Line Analytics")
        analytics_window.geometry("800x600")
        analytics_window.configure(bg=self.parent.BG_COLOR)
        
        main_frame = ttk.Frame(analytics_window, style='Panel.TFrame', padding=15)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main_frame, text="Line Performance Analytics", 
                 style='Title.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold')).pack(pady=(0, 15))
        
        # Create notebook for different analytics
        analytics_notebook = ttk.Notebook(main_frame, style='TNotebook')
        analytics_notebook.pack(fill='both', expand=True)
        
        # Forward lines analysis
        forward_frame = ttk.Frame(analytics_notebook, style='Panel.TFrame', padding=10)
        analytics_notebook.add(forward_frame, text="Forward Lines")
        
        # Analyze each forward line
        for i, line_vars in enumerate(self.forward_vars):
            line_analysis_frame = ttk.LabelFrame(forward_frame, text=f"Line {i+1} Analysis", 
                                               padding=10, style='TLabelframe')
            line_analysis_frame.pack(fill='x', pady=5)
            
            # Get players in this line
            players = []
            for combo, var in line_vars:
                selection = var.get()
                if selection and selection != "-- Select Player --":
                    player_name = selection.split(" (")[0]
                    player = next((p for p in self.forwards if p.full_name == player_name), None)
                    if player:
                        players.append(player)
            
            if players:
                # Calculate analytics
                avg_rating = sum(p.overall_rating() for p in players) / len(players)
                avg_age = sum(p.age for p in players) / len(players)
                chemistry = self.calculate_chemistry_bonus(players)
                
                # Display analytics
                analytics_text = (
                    f"Players: {', '.join(p.full_name for p in players)}\n"
                    f"Average Rating: {avg_rating:.1f}\n"
                    f"Average Age: {avg_age:.1f}\n"
                    f"Chemistry Bonus: +{chemistry:.1f}\n"
                    f"Final Line Rating: {avg_rating + chemistry:.1f}\n"
                )
                
                # Add individual player stats if available
                if hasattr(players[0], 'stats'):
                    total_goals = sum(getattr(p.stats, 'goals', 0) for p in players)
                    total_assists = sum(getattr(p.stats, 'assists', 0) for p in players)
                    analytics_text += f"Combined: {total_goals}G {total_assists}A"
                
                text_widget = tk.Text(line_analysis_frame, height=6, width=70, 
                                    bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                    font=(self.parent.FONT_FAMILY, 9))
                text_widget.pack(fill='x')
                text_widget.insert('1.0', analytics_text)
                text_widget.config(state='disabled')
            else:
                ttk.Label(line_analysis_frame, text="No players assigned to this line", 
                         style='TLabel').pack()
        
        # Team overview
        overview_frame = ttk.Frame(analytics_notebook, style='Panel.TFrame', padding=10)
        analytics_notebook.add(overview_frame, text="Team Overview")
        
        # Calculate team-wide stats
        all_assigned_players = []
        for line_vars in self.forward_vars:
            for combo, var in line_vars:
                selection = var.get()
                if selection and selection != "-- Select Player --":
                    player_name = selection.split(" (")[0]
                    player = next((p for p in self.forwards if p.full_name == player_name), None)
                    if player and player not in all_assigned_players:
                        all_assigned_players.append(player)
        
        if all_assigned_players:
            team_avg_rating = sum(p.overall_rating() for p in all_assigned_players) / len(all_assigned_players)
            team_avg_age = sum(p.age for p in all_assigned_players) / len(all_assigned_players)
            
            team_stats = (
                f"Forwards Assigned: {len(all_assigned_players)}/{len(self.forwards)}\n"
                f"Average Rating: {team_avg_rating:.1f}\n"
                f"Average Age: {team_avg_age:.1f}\n"
                f"Unassigned Players: {len(self.forwards) - len(all_assigned_players)}\n"
            )
            
            if len(self.forwards) - len(all_assigned_players) > 0:
                unassigned = [p for p in self.forwards if p not in all_assigned_players]
                unassigned_names = [f"{p.full_name} ({p.overall_rating()})" for p in unassigned[:5]]
                team_stats += f"Top Unassigned: {', '.join(unassigned_names)}"
            
            team_text_widget = tk.Text(overview_frame, height=10, width=70,
                                     bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                     font=(self.parent.FONT_FAMILY, 10))
            team_text_widget.pack(fill='both', expand=True)
            team_text_widget.insert('1.0', team_stats)
            team_text_widget.config(state='disabled')


class EditLinesWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Edit Lines - Simple & Easy")
        self.geometry("800x600")
        self.configure(bg=parent.BG_COLOR)

        # Get current lineup or create a simple one
        self.lineup = getattr(self.parent.user_team, "lineup", None)
        if not self.lineup:
            self.lineup = best_lines(self.parent.user_team)
        self.parent.user_team.lineup = self.lineup

        # Get all players sorted by rating
        self.all_players = sorted(list(self.parent.user_team.roster), 
                                 key=lambda p: p.overall_rating(), reverse=True)
        
        # Create super simple interface
        self.create_simple_interface()
    def create_simple_interface(self):
        """Create the simplest possible interface for editing lines."""
        # Simple header
        header_frame = ttk.Frame(self, style='TitleBar.TFrame', padding=15)
        header_frame.pack(fill=tk.X)
        
        ttk.Label(header_frame, text="Edit Your Lines - Just Click & Pick!",
                 style='Title.TLabel', font=(self.parent.FONT_FAMILY, 14, 'bold')).pack()
        
        # Main content frame
        content_frame = ttk.Frame(self, style='Panel.TFrame', padding=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create simple line displays
        self.create_simple_lines(content_frame)
        
        # Simple bottom buttons
        button_frame = ttk.Frame(self, style='Panel.TFrame', padding=15)
        button_frame.pack(fill=tk.X)
        
        # Auto-set button (most users will want this)
        ttk.Button(button_frame, text="Auto-Set Best Lines", 
                  command=self.auto_set_best, style='Accent.TButton',
                  width=20).pack(side=tk.LEFT, padx=10)
        
        # Save button
        ttk.Button(button_frame, text="Save & Close", 
                  command=self.save_and_close, style='Accent.TButton',
                  width=15).pack(side=tk.RIGHT, padx=10)
        
        # Cancel button
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy, style='TButton',
                  width=10).pack(side=tk.RIGHT, padx=5)
    
    def create_simple_lines(self, parent):
        """Create extremely simple line displays."""
        
        # Forward Lines (just the important ones)
        forwards_frame = ttk.LabelFrame(parent, text="Forward Lines", padding=15)
        forwards_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.forward_vars = []
        for i in range(4):  # 4 forward lines
            line_frame = ttk.Frame(forwards_frame)
            line_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(line_frame, text=f"Line {i+1}:", 
                     font=(self.parent.FONT_FAMILY, 10, 'bold'), width=8).pack(side=tk.LEFT)
            
            # Get current line players
            current_line = self.lineup.get('Forwards', [[None]*3 for _ in range(4)])[i]
            
            line_vars = []
            for j in range(3):  # LW, C, RW
                player = current_line[j] if j < len(current_line) else None
                
                # Simple dropdown with all forwards
                forwards = [p for p in self.all_players if p.primary_position.name in 
                           ['LEFT_WING', 'CENTER', 'RIGHT_WING']]
                
                var = tk.StringVar(master=self)
                if player:
                    var.set(f"{player.full_name} ({player.overall_rating()})")
                else:
                    var.set("-- Select Player --")
                
                combo = ttk.Combobox(line_frame, textvariable=var, width=25, state='readonly')
                combo['values'] = ["-- Select Player --"] + [f"{p.full_name} ({p.overall_rating()})" 
                                                            for p in forwards]
                combo.pack(side=tk.LEFT, padx=5)
                
                line_vars.append((combo, var))
            
            self.forward_vars.append(line_vars)
        
        # Defense Pairs (simplified)
        defense_frame = ttk.LabelFrame(parent, text="Defense Pairs", padding=15)
        defense_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.defense_vars = []
        for i in range(3):  # 3 defense pairs
            pair_frame = ttk.Frame(defense_frame)
            pair_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(pair_frame, text=f"Pair {i+1}:", 
                     font=(self.parent.FONT_FAMILY, 10, 'bold'), width=8).pack(side=tk.LEFT)
            
            # Get current pair
            current_pair = self.lineup.get('Defense', [[None]*2 for _ in range(3)])[i]
            
            pair_vars = []
            for j in range(2):  # LD, RD
                player = current_pair[j] if j < len(current_pair) else None
                
                # Simple dropdown with all defensemen
                defensemen = [p for p in self.all_players if p.primary_position.name in 
                             ['LEFT_DEFENSE', 'RIGHT_DEFENSE', 'DEFENSE']]
                
                var = tk.StringVar(master=self)
                if player:
                    var.set(f"{player.full_name} ({player.overall_rating()})")
                else:
                    var.set("-- Select Player --")
                
                combo = ttk.Combobox(pair_frame, textvariable=var, width=25, state='readonly')
                combo['values'] = ["-- Select Player --"] + [f"{p.full_name} ({p.overall_rating()})" 
                                                            for p in defensemen]
                combo.pack(side=tk.LEFT, padx=5)
                
                pair_vars.append((combo, var))
            
            self.defense_vars.append(pair_vars)
        
        # Goalies (super simple)
        goalies_frame = ttk.LabelFrame(parent, text="Goalies", padding=15)
        goalies_frame.pack(fill=tk.X)
        
        self.goalie_vars = []
        goalie_roles = ["Starter", "Backup"]
        for i, role in enumerate(goalie_roles):
            goalie_frame = ttk.Frame(goalies_frame)
            goalie_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(goalie_frame, text=f"{role}:", 
                     font=(self.parent.FONT_FAMILY, 10, 'bold'), width=8).pack(side=tk.LEFT)
            
            # Get current goalie
            current_goalie = self.lineup.get('Goalies', [None, None])[i]
            
            # Simple dropdown with all goalies
            goalies = [p for p in self.all_players if p.primary_position.name == 'GOALIE']
            
            var = tk.StringVar(master=self)
            if current_goalie:
                var.set(f"{current_goalie.full_name} ({current_goalie.overall_rating()})")
            else:
                var.set("-- Select Goalie --")
            
            combo = ttk.Combobox(goalie_frame, textvariable=var, width=25, state='readonly')
            combo['values'] = ["-- Select Goalie --"] + [f"{p.full_name} ({p.overall_rating()})" 
                                                        for p in goalies]
            combo.pack(side=tk.LEFT, padx=5)
            
            self.goalie_vars.append((combo, var))
    
    def auto_set_best(self):
        """Automatically set the best possible lines."""
        self.lineup = best_lines(self.parent.user_team)
        self.parent.user_team.lineup = self.lineup
        
        # Update all the dropdowns to reflect the new lineup
        self.update_dropdowns()
        
        messagebox.showinfo("Lines Set", "Your best players have been automatically assigned to lines!")
    
    def update_dropdowns(self):
        """Update all dropdown selections to match current lineup."""
        # Update forward lines
        for i, line_vars in enumerate(self.forward_vars):
            current_line = self.lineup.get('Forwards', [[None]*3 for _ in range(4)])[i]
            for j, (combo, var) in enumerate(line_vars):
                player = current_line[j] if j < len(current_line) else None
                if player:
                    var.set(f"{player.full_name} ({player.overall_rating()})")
                else:
                    var.set("-- Select Player --")
        
        # Update defense pairs
        for i, pair_vars in enumerate(self.defense_vars):
            current_pair = self.lineup.get('Defense', [[None]*2 for _ in range(3)])[i]
            for j, (combo, var) in enumerate(pair_vars):
                player = current_pair[j] if j < len(current_pair) else None
                if player:
                    var.set(f"{player.full_name} ({player.overall_rating()})")
                else:
                    var.set("-- Select Player --")
        
        # Update goalies
        for i, (combo, var) in enumerate(self.goalie_vars):
            current_goalie = self.lineup.get('Goalies', [None, None])[i]
            if current_goalie:
                var.set(f"{current_goalie.full_name} ({current_goalie.overall_rating()})")
            else:
                var.set("-- Select Goalie --")
    
    def save_and_close(self):
        """Save the current lineup and close."""
        # Build lineup from dropdown selections
        new_lineup = {'Forwards': [], 'Defense': [], 'Goalies': []}
        
        # Process forward lines
        for line_vars in self.forward_vars:
            line = []
            for combo, var in line_vars:
                selection = var.get()
                if selection != "-- Select Player --":
                    # Extract player name from "Name (Rating)" format
                    player_name = selection.split(' (')[0]
                    player = next((p for p in self.all_players if p.full_name == player_name), None)
                    line.append(player)
                else:
                    line.append(None)
            new_lineup['Forwards'].append(line)
        
        # Process defense pairs
        for pair_vars in self.defense_vars:
            pair = []
            for combo, var in pair_vars:
                selection = var.get()
                if selection != "-- Select Player --":
                    player_name = selection.split(' (')[0]
                    player = next((p for p in self.all_players if p.full_name == player_name), None)
                    pair.append(player)
                else:
                    pair.append(None)
            new_lineup['Defense'].append(pair)
        
        # Process goalies
        goalies = []
        for combo, var in self.goalie_vars:
            selection = var.get()
            if selection != "-- Select Goalie --":
                player_name = selection.split(' (')[0]
                player = next((p for p in self.all_players if p.full_name == player_name), None)
                goalies.append(player)
            else:
                goalies.append(None)
        new_lineup['Goalies'] = goalies
        
        # Save the lineup
        self.lineup = new_lineup
        self.parent.user_team.lineup = self.lineup
        
        messagebox.showinfo("Lines Saved", "Your lineup has been saved successfully!")
        self.destroy()
        
class TradeBlockWindow(tk.Toplevel):
    """
    Enhanced Trade Block window with filtering, sorting, bulk actions, context menu, and summary.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Manage Trade Block")
        self.geometry("900x700")
        self.configure(bg=parent.BG_COLOR)
        self.resizable(False, False)

        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('Panel.TFrame', background=parent.CONTENT_BG)
        self.style.configure('TitleBar.TFrame', background=parent.TITLE_BAR_COLOR)
        self.style.configure('Title.TLabel', background=parent.TITLE_BAR_COLOR, foreground=parent.HEADER_COLOR, font=(parent.FONT_FAMILY, 13, 'bold'))
        self.style.configure('TButton', font=(parent.FONT_FAMILY, 11, 'bold'), foreground='white', background=parent.ACCENT_COLOR, padding=(10, 6), borderwidth=0)
        self.style.map('TButton', background=[('active', parent.ACCENT_ACTIVE), ('hover', parent.ACCENT_HOVER)])
        self.style.configure('Summary.TLabel', background=parent.CONTENT_BG, foreground=parent.ACCENT_COLOR, font=(parent.FONT_FAMILY, 12, 'bold'))

        # --- Title bar ---
        title_bar = ttk.Frame(self, style='TitleBar.TFrame')
        title_bar.pack(fill="x")
        ttk.Label(title_bar, text="Manage Trade Block", style='Title.TLabel', padding=(10, 8)).pack(side="left")
        # Team logo (placeholder)
        logo_canvas = tk.Canvas(title_bar, width=40, height=40, bg=parent.TITLE_BAR_COLOR, highlightthickness=0)
        logo_canvas.pack(side="right", padx=8)
        logo_canvas.create_text(20, 20, text="LOGO", fill="white", font=(parent.FONT_FAMILY, 8, 'bold'))

        # --- Summary panel ---
        self.summary_panel = ttk.Frame(self, style='Panel.TFrame', padding=8)
        self.summary_panel.pack(fill="x", padx=18, pady=(8, 0))
        self.summary_label = ttk.Label(self.summary_panel, text="", style='Summary.TLabel')
        self.summary_label.pack(anchor="w")

        # --- Filter panel ---
        filter_panel = ttk.Frame(self, style='Panel.TFrame', padding=8)
        filter_panel.pack(fill="x", padx=18, pady=(8, 0))
        self.filter_vars = {
            'pos': tk.StringVar(master=self, value="All"),
            'min_ovr': tk.StringVar(master=self, value=""),
            'max_age': tk.StringVar(master=self, value=""),
            'contract': tk.StringVar(master=self, value="All"),
            'on_block': tk.StringVar(master=self, value="All"),
        }
        ttk.Label(filter_panel, text="Position:").pack(side="left")
        pos_options = ["All", "LW", "C", "RW", "LD", "RD", "G"]
        ttk.Combobox(filter_panel, textvariable=self.filter_vars['pos'], values=pos_options, width=6, state="readonly").pack(side="left", padx=2)
        ttk.Label(filter_panel, text="Min OVR:").pack(side="left")
        tk.Entry(filter_panel, textvariable=self.filter_vars['min_ovr'], width=4, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, insertbackground=self.parent.TEXT_COLOR).pack(side="left", padx=2)
        ttk.Label(filter_panel, text="Max Age:").pack(side="left")
        tk.Entry(filter_panel, textvariable=self.filter_vars['max_age'], width=4, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, insertbackground=self.parent.TEXT_COLOR).pack(side="left", padx=2)
        ttk.Label(filter_panel, text="Contract:").pack(side="left")
        ttk.Combobox(filter_panel, textvariable=self.filter_vars['contract'], values=["All", "Signed", "Unsigned"], width=8, state="readonly").pack(side="left", padx=2)
        ttk.Label(filter_panel, text="On Block:").pack(side="left")
        ttk.Combobox(filter_panel, textvariable=self.filter_vars['on_block'], values=["All", "Yes", "No"], width=5, state="readonly").pack(side="left", padx=2)
        ttk.Button(filter_panel, text="Apply", command=self._populate_tree).pack(side="left", padx=8)

        # --- Panel frame ---
        panel = ttk.Frame(self, style='Panel.TFrame', padding=12)
        panel.pack(fill="both", expand=True, padx=18, pady=18)

        # --- Treeview columns ---
        columns = {
            'sel': ('', 30),
            'trade_block': ('On Block', 60),
            'number': ('#', 40),
            'name': ('Player', 180),
            'pos': ('Pos', 70),
            'ovr': ('OVR', 60),
            'age': ('Age', 50),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'potential': ('Pot', 50),
            'morale': ('Morale', 60),
            'g': ('G', 40),
            'a': ('A', 40),
            'p': ('P', 40),
            'trade_value': ('Value', 80),
            'interest': ('Interest', 120),
        }
        self.tree = ttk.Treeview(panel, columns=list(columns.keys()), show='headings', height=20)
        for col, (text, width) in columns.items():
            self.tree.heading(col, text=text, command=lambda c=col: self._sort_treeview(c))
            self.tree.column(col, width=width, anchor='center')
        self.tree.pack(fill="both", expand=True, pady=(0, 10))
        self.tree.bind("<Button-1>", self._handle_checkbox_click)
        self.tree.bind("<Double-1>", self.toggle_trade_block)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.tag_configure('selected', background='#333333')

        # --- Bulk action buttons ---
        btn_frame = ttk.Frame(panel, style='Panel.TFrame')
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="Add to Trade Block", command=self.add_selected_to_block).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remove from Trade Block", command=self.remove_selected_from_block).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Shop Player", command=self.shop_selected_players).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Suggest Trade Value", command=self.suggest_trade_value).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Simulate Trade Offers", command=self.simulate_trade_offers).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side="right", padx=5)

        # --- Checkbox state ---
        self.selected_items = set()
        self.sort_column = None
        self.sort_reverse = False

        self._populate_tree()

    def _filter_players(self, roster):
        pos = self.filter_vars['pos'].get()
        min_ovr = self.filter_vars['min_ovr'].get()
        max_age = self.filter_vars['max_age'].get()
        contract = self.filter_vars['contract'].get()
        on_block = self.filter_vars['on_block'].get()
        filtered = []
        for p in roster:
            if pos != "All" and p.primary_position.name != pos:
                continue
            if min_ovr and p.overall_rating() < int(min_ovr):
                continue
            if max_age and p.age > int(max_age):
                continue
            if contract == "Signed" and p.contract.years_remaining == 0:
                continue
            if contract == "Unsigned" and p.contract.years_remaining > 0:
                continue
            if on_block == "Yes" and p not in self.parent.trade_block:
                continue
            if on_block == "No" and p in self.parent.trade_block:
                continue
            filtered.append(p)
        return filtered

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.player_map = {}
        roster = self.parent.user_team.roster
        trade_block = self.parent.trade_block
        filtered_roster = self._filter_players(roster)
        for player in sorted(filtered_roster, key=lambda p: p.overall_rating(), reverse=True):
            # Trade block icon
            on_block = "✔" if player in trade_block else ""
            # Checkbox
            sel = "☑" if player.id in self.selected_items else "☐"
            # Contract status
            contract_status = "Signed" if player.contract.years_remaining > 0 else "Unsigned"
            # Stats
            g, a, pnt = player.stats.goals, player.stats.assists, player.stats.points
            # Trade value (simple formula)
            potential_value = 0
            if player.potential_grade == 'A':
                potential_value = 250000
            elif player.potential_grade == 'B':
                potential_value = 150000
            elif player.potential_grade == 'C':
                potential_value = 100000
            elif player.potential_grade == 'D':
                potential_value = 50000
            
            trade_value = int(player.overall_rating() * 100_000 + potential_value)
            # Interested teams (simple AI: teams needing position and cap space)
            interested = self._get_interested_teams(player)
            interest_str = ", ".join(interested) if interested else "—"
            # Salary
            salary_str = f"${player.contract.salary:,}" if player.contract.years_remaining > 0 else "Unsigned"
            values = (
                sel,
                on_block,
                f"#{player.jersey_number}",
                player.full_name,
                player.primary_position.name,
                player.overall_rating(),
                player.age,
                salary_str,
                contract_status,
                player.potential_grade,
                player.morale,
                g, a, pnt,
                trade_value,
                interest_str
            )
            item_id = self.tree.insert('', 'end', values=values, tags=('selected' if player.id in self.selected_items else ''))
            self.player_map[item_id] = player
        self._update_summary()

    def _sort_treeview(self, col):
        # Toggle sort order
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        # Sort player_map by column
        def get_val(item_id):
            val = self.tree.set(item_id, col)
            try:
                return int(val.replace("✔", "").replace("☑", "").replace("☐", "").replace("#", "").replace("$", "").replace(",", ""))
            except:
                return val
        items = list(self.tree.get_children())
        items.sort(key=get_val, reverse=self.sort_reverse)
        for idx, item_id in enumerate(items):
            self.tree.move(item_id, '', idx)

    def _handle_checkbox_click(self, event):
        col = self.tree.identify_column(event.x)
        if col == '#1':  # Checkbox column
            item_id = self.tree.identify_row(event.y)
            if item_id:
                player = self.player_map.get(item_id)
                if player and player.id in self.selected_items:
                    self.selected_items.remove(player.id)
                elif player:
                    self.selected_items.add(player.id)
                self._populate_tree()

    def add_selected_to_block(self):
        # Convert selected IDs to player objects
        selected_players = [p for p in self.parent.user_team.roster if p.id in self.selected_items]
        for player in selected_players:
            if player not in self.parent.trade_block:
                self.parent.trade_block.append(player)
        self.selected_items.clear()
        self._populate_tree()
        self.parent.update_all_views()

    def remove_selected_from_block(self):
        # Convert selected IDs to player objects
        selected_players = [p for p in self.parent.user_team.roster if p.id in self.selected_items]
        for player in selected_players:
            if player in self.parent.trade_block:
                self.parent.trade_block.remove(player)
        self.selected_items.clear()
        self._populate_tree()
        self.parent.update_all_views()

    def shop_selected_players(self):
        """Show detailed information about team interest in selected players."""
        msg = ""
        selected_players = [p for p in self.parent.user_team.roster if p.id in self.selected_items]
        
        if not selected_players:
            messagebox.showinfo("Shop Player", "No players selected.")
            return
            
        shop_window = tk.Toplevel(self)
        shop_window.title("Shop Players")
        shop_window.geometry("700x500")
        shop_window.configure(bg=self.parent.BG_COLOR)
        shop_window.grab_set()  # Make window modal
        
        # Create scrollable text widget
        frame = ttk.Frame(shop_window, style='Panel.TFrame', padding=15)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        title = ttk.Label(frame, text="Team Interest Report", style='Title.TLabel', font=(self.parent.FONT_FAMILY, 14, 'bold'))
        title.pack(anchor='w', pady=(0, 15))
        
        text = tk.Text(frame, wrap='word', bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, 
                      font=(self.parent.FONT_FAMILY, 11), relief='flat', pady=10, padx=10, height=20)
        text.pack(fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(text, orient='vertical', command=text.yview)
        scrollbar.pack(side='right', fill='y')
        text.configure(yscrollcommand=scrollbar.set)
        
        # For each selected player
        for player in selected_players:
            player_value = self.parent.calculate_player_value(player)
            discounted_value = int(player_value * 0.85)  # Trade block discount
            
            text.insert('end', f"Player: {player.full_name}\n", 'heading')
            text.insert('end', f"Position: {player.primary_position.name}  |  OVR: {player.overall_rating()}  |  " +
                             f"Age: {player.age}  |  Potential: {player.potential_grade}\n\n")
            
            text.insert('end', f"Market Value: ${player_value:,}\n")
            text.insert('end', f"Trade Block Value: ${discounted_value:,} (15% discount applied)\n\n")
            
            # Get interested teams with interest level
            interested_teams = []
            for team in self.parent.league.teams:
                if team == self.parent.user_team:
                    continue
                    
                # Calculate interest level
                pos_count = sum(1 for p in team.roster if p.primary_position == player.primary_position)
                pos_need = pos_count < 3
                has_cap_space = team.cap_space > player.contract.salary
                
                team_stats = self.parent.league.standings.get(team.team_name, {'Points': 0})
                try:
                    team_rank = sorted(self.parent.league.standings.values(), 
                                     key=lambda x: x['Points'], 
                                     reverse=True).index(team_stats)
                    is_improving = team_rank > 16
                except ValueError:
                    is_improving = True  # Default to improving if team not found in standings
                
                interest_level = 0
                if pos_need: interest_level += 30
                if has_cap_space: interest_level += 20
                if is_improving: interest_level += 20
                
                team_avg_ovr = sum(p.overall_rating() for p in team.roster) / len(team.roster) if team.roster else 70
                if player.overall_rating() > team_avg_ovr + 5:
                    interest_level += 30
                    
                if player.primary_position == PlayerPosition.GOALIE and pos_count == 0:
                    interest_level += 50
                
                if player.age < 25 and player.potential_grade in ['A', 'B']:
                    interest_level += 25
                
                if interest_level >= 50 and has_cap_space:
                    interested_teams.append((team, interest_level))
            
            # Sort by interest level and display
            interested_teams.sort(key=lambda x: x[1], reverse=True)
            
            if interested_teams:
                text.insert('end', "Interested Teams:\n", 'subheading')
                for team, interest in interested_teams:
                    interest_text = "Very High" if interest >= 90 else \
                                   "High" if interest >= 70 else \
                                   "Medium" if interest >= 50 else "Low"
                    
                    text.insert('end', f"• {team.team_name}: {interest_text} interest\n")
                    
                    # Show what team might offer
                    if interest >= 70:  # Only show potential offers for high interest
                        potential_offer = self.parent.generate_trade_package(
                            team, player, discounted_value)
                        
                        if potential_offer:
                            text.insert('end', "  Potential offer: ")
                            for i, p in enumerate(potential_offer):
                                if i > 0:
                                    text.insert('end', ", ")
                                text.insert('end', f"{p.full_name} ({p.overall_rating()})")
                            text.insert('end', "\n")
                            
                text.insert('end', "\n")
            else:
                text.insert('end', "No teams showing significant interest\n\n")
            
            text.insert('end', "-" * 50 + "\n\n")
        
        # Configure tags
        text.tag_configure('heading', font=(self.parent.FONT_FAMILY, 12, 'bold'), foreground=self.parent.ACCENT_COLOR)
        text.tag_configure('subheading', font=(self.parent.FONT_FAMILY, 11, 'bold'))
        text.config(state='disabled')  # Make read-only
        
        # Close button
        ttk.Button(frame, text="Close", command=shop_window.destroy).pack(pady=10)

    def suggest_trade_value(self):
        """Show suggested trade value for selected players with more detailed valuation."""
        msg = ""
        selected_players = [p for p in self.parent.user_team.roster if p.id in self.selected_items]
        
        for player in selected_players:
            # Use the parent's calculate_player_value method for consistent valuation
            base_value = self.parent.calculate_player_value(player)
            
            # Apply trade block discount if applicable
            value = base_value
            if player in self.parent.trade_block:
                value = int(base_value * 0.85)  # 15% discount
                msg += f"{player.full_name}: ${value:,} (Trade block discount applied)\n"
            else:
                msg += f"{player.full_name}: ${value:,}\n"
                
            # Add potential teams interested
            interested = self._get_interested_teams(player)
            if interested:
                msg += f"  Potential Interest: {', '.join(interested[:3])}"
                if len(interested) > 3:
                    msg += f" and {len(interested) - 3} more"
                msg += "\n"
            else:
                msg += "  No teams showing significant interest\n"
                
        messagebox.showinfo("Trade Value Analysis", msg or "No players selected.")

    def toggle_trade_block(self, event):
        item_id = self.tree.identify_row(event.y)
        player = self.player_map.get(item_id)
        if not player:
            return
        if player in self.parent.trade_block:
            self.parent.trade_block.remove(player)
        else:
            self.parent.trade_block.append(player)
        self._populate_tree()
        self.parent.update_all_views()

    def _show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        player = self.player_map.get(item_id)
        if not player:
            return
        menu = tk.Menu(self, tearoff=0, bg="#3C3C3C", fg="white")
        menu.add_command(label="View Player Profile", command=lambda: self.parent.open_player_profile(player))
        menu.add_command(label="Shop Player", command=lambda: self.shop_selected_players())
        if player in self.parent.trade_block:
            menu.add_command(label="Remove from Trade Block", command=lambda: self.remove_selected_from_block())
        else:
            menu.add_command(label="Add to Trade Block", command=lambda: self.add_selected_to_block())
        menu.tk_popup(event.x_root, event.y_root)

    def _get_interested_teams(self, player):
        """Get a list of teams that might be interested in the player with improved AI logic."""
        interested = []
        
        for team in self.parent.league.teams:
            if team == self.parent.user_team:
                continue
                
            # Check if team needs this position
            pos_count = sum(1 for p in team.roster if p.primary_position == player.primary_position)
            pos_need = pos_count < 3
            
            # Check cap space
            has_cap_space = team.cap_space > player.contract.salary
            
            # Check if team is looking to improve (based on standings)
            team_stats = self.parent.league.standings.get(team.team_name, {'Points': 0})
            try:
                team_rank = sorted(self.parent.league.standings.values(), 
                                 key=lambda x: x['Points'], 
                                 reverse=True).index(team_stats)
            except ValueError:
                team_rank = 20  # Default to low rank if team not found in standings
            is_improving = team_rank > 16  # Bottom half of the league
            
            # Calculate interest level
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
                
            # Special case for goalies
            if player.primary_position == PlayerPosition.GOALIE and pos_count == 0:
                interest_level += 50  # Teams desperately need goalies
            
            # Teams more interested in younger players with potential
            if player.age < 25 and player.potential_grade in ['A', 'B']:
                interest_level += 25
            
            # Add to interested teams if significant interest
            if interest_level >= 50 and has_cap_space:
                interested.append(team.team_name)
                
        return interested

    def _update_summary(self):
        block = self.parent.trade_block
        n_block = len(block)
        avg_ovr = int(sum(p.overall_rating() for p in block) / n_block) if n_block else 0
        cap_freed = sum(p.contract.salary for p in block if p.contract.years_remaining > 0)
        self.summary_label.config(text=f"Players on block: {n_block}   Avg OVR: {avg_ovr}   Cap space freed: ${cap_freed:,}")

    def simulate_trade_offers(self):
        """Manually trigger trade offers for players on the trade block."""
        if not self.parent.trade_block:
            messagebox.showinfo("No Players on Block", "Add players to the trade block first.")
            return
        
        # Call the parent's method to process trade block offers
        self.parent.process_trade_block_offers()
        
        # Update the view
        self._populate_tree()

    def update_views(self):
        self._populate_tree()
        
class ContractExtensionsWindow(tk.Toplevel):
    """Window for handling contract extensions."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Contract Extensions")
        self.configure(background=parent.BG_COLOR)
        self.minsize(1000, 600)
        
        # Ensure global constants are accessible
        global SALARY_CAP
        
        # Set styles consistent with parent application
        self.style = parent.style
        
        # Eligible players are those whose contracts expire at end of season
        self.eligible_players = self.get_eligible_players()
        self.player_map = {}  # Maps tree item IDs to player objects
        
        # Create main frame with padding
        main_frame = ttk.Frame(self, style='Dark.TFrame', padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and description
        header_frame = ttk.Frame(main_frame, style='TitleBar.TFrame', padding=(10, 5))
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(
            header_frame, 
            text="CONTRACT EXTENSIONS", 
            style='Title.TLabel',
            font=(self.parent.FONT_FAMILY, 16, 'bold')
        )
        title_label.pack(side=tk.LEFT)
        
        desc_label = ttk.Label(
            header_frame, 
            text="Manage contract extensions for players with expiring contracts. New: Enhanced NHL-style contracts with performance bonuses!", 
            style='Subtitle.TLabel'
        )
        desc_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # Team info frame
        team_frame = ttk.Frame(main_frame, style='Panel.TFrame', padding=10)
        team_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Use the global SALARY_CAP constant
        current_payroll = self.get_current_payroll()
        projected_space = self.get_projected_cap_space()
        cap_info_text = f"Salary Cap: ${SALARY_CAP:,}  |  Current Payroll: ${current_payroll:,}  |  Projected Space: ${projected_space:,}"
        cap_info = ttk.Label(team_frame, text=cap_info_text, style='Info.TLabel')
        cap_info.pack()
        
        # Create treeview for player list
        columns = {
            'jersey': ('Jersey', 60), 
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'pot': ('Potential', 80),
            'salary': ('Current Salary', 120),
            'years': ('Years Left', 80),
            'market': ('Market Value', 120),
            'morale': ('Morale', 100)
        }
        
        # Treeview frame with scrollbar
        tree_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create the treeview with scrollbar
        self.tree = ttk.Treeview(tree_frame, columns=list(columns.keys()), show='headings', style='Dark.Treeview')
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the scrollbar and treeview
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure columns and headings
        for i, (col, (text, width)) in enumerate(columns.items()):
            self.tree.heading(col, text=text, command=lambda c=col: self.parent._sort_treeview_generic(self.tree, c, False))
            self.tree.column(col, width=width, anchor=tk.W if col == 'name' else tk.CENTER)
        
        # Populate the treeview
        self._populate_tree()
        
        # Add right-click context menu and double-click handler
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # Action buttons frame
        button_frame = ttk.Frame(main_frame, style='Dark.TFrame', padding=(0, 10, 0, 0))
        button_frame.pack(fill=tk.X)
        
        # Create buttons
        self.negotiate_button = ttk.Button(
            button_frame, 
            text="Negotiate Extension",
            style='Accent.TButton',
            command=self.negotiate_selected
        )
        self.negotiate_button.pack(side=tk.LEFT, padx=5)
        
        # Help button with tooltip for new features
        self.help_button = ttk.Button(
            button_frame,
            text="Contract Features",
            style='TButton',
            command=self.show_contract_features_help
        )
        self.help_button.pack(side=tk.LEFT, padx=5)
        
        self.negotiate_all_button = ttk.Button(
            button_frame, 
            text="Negotiate All", 
            style='TButton',
            command=self.negotiate_all
        )
        self.negotiate_all_button.pack(side=tk.LEFT, padx=5)
        
        self.close_button = ttk.Button(
            button_frame, 
            text="Close", 
            style='TButton',
            command=self.destroy
        )
        self.close_button.pack(side=tk.RIGHT, padx=5)
        
        # Center the window on the screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def get_eligible_players(self):
        """Get all players with one year left on their contract."""
        eligible = []
        team = self.parent.game_manager.user_team
        
        # Find players with 1 year left on contract
        for player in team.roster:
            years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 0))
            if years == 1:
                eligible.append(player)
                
        return eligible
        
        # Populate the tree with eligible players
        self.eligible_players = self.get_eligible_players()
        self._populate_tree()
    
    def get_current_payroll(self):
        """Calculate the current team payroll."""
        payroll = 0
        for player in self.parent.game_manager.user_team.roster:
            salary = getattr(player, "salary", getattr(player.contract, "salary", 0))
            payroll += salary
        return payroll
        
    def get_projected_cap_space(self):
        """Calculate projected cap space for next season."""
        # Get current payroll
        current_payroll = self.get_current_payroll()
        
        # Subtract salaries of expiring contracts
        expiring_salary = sum(
            getattr(player, "salary", getattr(player.contract, "salary", 0))
            for player in self.eligible_players
        )
        
        # Use the global SALARY_CAP constant
        return SALARY_CAP - (current_payroll - expiring_salary)
    
    def calculate_market_value(self, player):
        """Calculate the market value of a player."""
        # Base value determined by overall rating
        base_value = player.overall_rating() * 100000
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= player.age <= 29:
            age_modifier = 1.2
        elif player.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((player.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if player.primary_position == PlayerPosition.CENTER:
            position_modifier = 1.15
        elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            position_modifier = 1.1
        elif player.primary_position == PlayerPosition.GOALIE:
            # Goalies have different value curve
            position_modifier = 1.0 if player.overall_rating() >= 50 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if player.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(player.potential_grade, 1.0)
        
        # Stats performance bonus
        performance_bonus = 0
        if hasattr(player, 'stats'):
            performance_bonus = player.stats.goals * 50000 + player.stats.assists * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def _populate_tree(self):
        """Populate the treeview with eligible players."""
        self.tree.delete(*self.tree.get_children())
        self.player_map = {}
        
        for player in sorted(self.eligible_players, key=lambda p: p.overall_rating(), reverse=True):
            current_salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
            years_left = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 0))
            market_value = self.calculate_market_value(player)
            
            # Format values for better readability
            jersey = f"#{player.jersey_number}"
            
            # Add position color coding
            position_tags = {
                'C': 'center',
                'LW': 'wing', 
                'RW': 'wing',
                'LD': 'defense',
                'RD': 'defense',
                'D': 'defense',
                'G': 'goalie'
            }
            position_tag = position_tags.get(player.primary_position.name, '')
            
            # Format the rest
            salary_str = f"${current_salary:,}"
            market_str = f"${market_value:,}"
            
            # Determine morale status for display
            morale_str = ""
            if player.morale >= 15:
                morale_str = "Very Happy"
                morale_tag = "high_morale"
            elif player.morale >= 10:
                morale_str = "Satisfied"
                morale_tag = "med_morale"
            elif player.morale >= 5:
                morale_str = "Concerned"
                morale_tag = "low_morale"
            else:
                morale_str = "Unhappy"
                morale_tag = "vlow_morale"
            
            values = (
                jersey,
                player.full_name,
                player.primary_position.name,
                player.age,
                player.overall_rating(),
                player.potential_grade,
                salary_str,
                years_left,
                market_str,
                morale_str,
            )
            
            # Determine row tag based on player attributes
            tags = [position_tag, morale_tag]
            
            item_id = self.tree.insert('', 'end', values=values, tags=tags)
            self.player_map[item_id] = player
            
        # Configure tags for color coding - using standard RGB colors without alpha channel
        # Color tints for positions
        self.tree.tag_configure('center', background='#BBDEFB')  # Center (light blue)
        self.tree.tag_configure('wing', background='#1E3A8A', foreground='#FFFFFF')    # Wing (dark blue with white text)
        self.tree.tag_configure('defense', background='#166534', foreground='#FFFFFF') # Defense (dark green with white text)
        self.tree.tag_configure('goalie', background='#B91C1C', foreground='#FFFFFF')  # Goalie (dark red with white text)
        
        # Morale tags
        self.tree.tag_configure('high_morale', foreground='#4CAF50')   # Green
        self.tree.tag_configure('med_morale', foreground='#8BC34A')    # Light green
        self.tree.tag_configure('low_morale', foreground='#FFC107')    # Yellow
        self.tree.tag_configure('vlow_morale', foreground='#F44336')   # Red
    
    def show_context_menu(self, event):
        """Show right-click context menu for the tree."""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        self.tree.selection_set(item_id)
        player = self.player_map.get(item_id)
        if not player:
            return
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        context_menu.add_command(label=f"Negotiate with {player.full_name}", 
                                command=lambda: self.negotiate_with_player(player))
        context_menu.add_command(label="View Player Profile", 
                                command=lambda: self.parent.open_player_profile(player))
        
        # Display the menu
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def negotiate_with_player(self, player):
        """Open negotiation window for a specific player."""
        # Calculate market value
        market_value = self.calculate_market_value(player)
        
        # Maximum contract length - NHL rules allow 8 years for your own players
        max_years = 8
        
        # Create negotiation window
        negotiation_window = ContractNegotiationWindow(self.parent, player, market_value, max_years)
        self.parent.open_windows['extension_negotiation'] = negotiation_window
    
    def negotiate_selected(self):
        """Negotiate with selected player(s)."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select at least one player to negotiate with.")
            return
            
        results = []
        for item_id in selected_items:
            player = self.player_map.get(item_id)
            if player:
                # Set default contract values
                market_value = self.calculate_market_value(player)
                player.salary = market_value
                player.contract_years = 2  # Default offer for extension
                
                # Negotiate
                accepted = self.parent.handle_contract_offer(player, extension=True)
                results.append(f"{player.full_name}: {'Accepted' if accepted else 'Rejected'}")
        
        # Show results
        msg = "Extension Results:\n" + "\n".join(results)
        messagebox.showinfo("Negotiation Results", msg)
        
        # Refresh the view after negotiations
        self.eligible_players = self.get_eligible_players()
        self._populate_tree()
    
    def negotiate_all(self):
        """Negotiate with all eligible players."""
        if not self.eligible_players:
            messagebox.showinfo("No Players", "No players are eligible for contract extensions.")
            return
            
        results = []
        for player in self.eligible_players:
            # Set default contract values
            market_value = self.calculate_market_value(player)
            player.salary = market_value
            player.contract_years = 2  # Default offer for extension
            
            # Negotiate
            accepted = self.parent.handle_contract_offer(player, extension=True)
            results.append(f"{player.full_name}: {'Accepted' if accepted else 'Rejected'}")
        
        # Show results
        msg = "Extension Results:\n" + "\n".join(results)
        messagebox.showinfo("Negotiation Results", msg)
        
        # Refresh the view after negotiations
        self.eligible_players = self.get_eligible_players()
        self._populate_tree()
        
    def show_contract_features_help(self):
        """Show help information about the enhanced contract features."""
        help_window = tk.Toplevel(self)
        help_window.title("NHL-Style Contract Features")
        help_window.geometry("700x500")
        help_window.configure(background=self.parent.BG_COLOR)
        
        main_frame = ttk.Frame(help_window, style='Panel.TFrame', padding=15)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        ttk.Label(main_frame, 
                 text="NHL-Style Contract Features", 
                 font=(self.parent.FONT_FAMILY, 16, 'bold'),
                 style='Header.TLabel').pack(anchor='w', pady=(0, 10))
        
        # Help text
        help_text = tk.Text(main_frame, wrap='word', bg=self.parent.CONTENT_BG, 
                           fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 10))
        help_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(help_text, orient='vertical', command=help_text.yview)
        scrollbar.pack(side='right', fill='y')
        help_text.configure(yscrollcommand=scrollbar.set)
        
        # Help content
        content = """
The new contract negotiation system includes these NHL-style features:

1. Basic Contract Terms:
   • Annual Salary: The base yearly salary for the player
   • Contract Length: Number of years for the contract (up to 8 years for your own players)
   • Signing Bonus: One-time bonus paid at signing (counts against cap)

2. Contract Clauses:
   • No-Trade Clause: Prevents the player from being traded without consent
   • Front-Loaded Contract: Higher salary in earlier years, declining over time

3. Performance Bonuses:
   • Achievement-based bonuses that pay out only if the player meets specific targets
   • Examples: Scoring goals, reaching assist thresholds, making the All-Star team
   • Particularly valuable for young players (under 22) and veterans (over 35)

4. Player Considerations:
   • Age: Younger players generally prefer longer terms
   • Veterans: Older players value no-trade clauses and front-loaded contracts
   • Position: Different positions have position-specific bonuses available

5. NHL-Style Rules:
   • Minimum salary: $750,000 (NHL minimum)
   • Maximum term: 8 years for your own players
   • Performance bonuses: Primarily for entry-level and 35+ contracts

Tips for Negotiation:
   • For young stars (under 25): Lock them up long-term (7-8 years)
   • For prime players (26-32): Offer 4-6 year deals
   • For older players (33+): Short term deals (1-3 years) with bonuses
   • Use front-loaded contracts for players likely to decline
   • Use performance bonuses to incentivize specific areas of improvement

The Contract Summary tab shows the yearly breakdown of the contract and
estimated likelihood of the player accepting your offer.
        """
        
        help_text.insert('1.0', content)
        help_text.config(state='disabled')
        
        # Close button
        ttk.Button(main_frame, text="Close", 
                  command=help_window.destroy).pack(pady=10)

    def on_double_click(self, event):
        """Handle double-click on a player row."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            player = self.player_map.get(item_id)
            if player:
                self.negotiate_with_player(player)

class ExtensionNegotiationWindow(tk.Toplevel):
    """Window for negotiating contract extensions with a player."""
    
    def __init__(self, parent, player, market_value=None):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        
        # Calculate market value if not provided
        self.market_value = market_value or self.calculate_market_value(player)
        
        # Configure window
        self.title(f"Contract Extension - {player.full_name}")
        self.configure(background=parent.BG_COLOR)
        self.minsize(800, 600)
        
        # Create main container with modern styling
        main_frame = ttk.Frame(self, style='Dark.TFrame', padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header with player name
        header_frame = ttk.Frame(main_frame, style='TitleBar.TFrame', padding=(10, 8))
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            header_frame, 
            text=f"CONTRACT EXTENSION: {player.full_name.upper()}", 
            style='Title.TLabel',
            font=(parent.FONT_FAMILY, 16, 'bold')
        ).pack(anchor=tk.W)
                  
        # Two column layout with a divider
        content_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Left column - Player info
        left_col = ttk.Frame(content_frame, style='Panel.TFrame', padding=15)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Vertical separator
        separator = ttk.Separator(content_frame, orient='vertical')
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=15)
        
        # Right column - Contract offer
        right_col = ttk.Frame(content_frame, style='Panel.TFrame', padding=15)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # --- PLAYER INFO (LEFT COLUMN) ---
        
        # Player header with visual styling
        player_header = ttk.Frame(left_col, style='SubHeader.TFrame', padding=(5, 3))
        player_header.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            player_header, 
            text="PLAYER INFORMATION", 
            style='SubTitle.TLabel',
            font=(parent.FONT_FAMILY, 12, 'bold')
        ).pack(anchor=tk.W)
        
        # Player display with jersey number and info
        player_display = ttk.Frame(left_col, style='Dark.TFrame')
        player_display.pack(fill=tk.X, pady=(0, 15))
        
        # Jersey number as visual element
        jersey_frame = ttk.Frame(player_display, style='Dark.TFrame', width=80, height=80)
        jersey_frame.grid(row=0, column=0, rowspan=3, padx=(0, 15), pady=5)
        jersey_frame.pack_propagate(False)
        
        # Background circle for jersey number
        jersey_circle = ttk.Frame(jersey_frame, style='Dark.TFrame')
        jersey_circle.pack(expand=True)
        jersey_circle.configure(width=60, height=60)
        
        jersey_label = ttk.Label(
            jersey_circle, 
            text=f"{player.jersey_number}", 
            font=(parent.FONT_FAMILY, 24, 'bold'),
            foreground=parent.ACCENT_COLOR
        )
        jersey_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Player name and info
        ttk.Label(
            player_display, 
            text=player.full_name, 
            font=(parent.FONT_FAMILY, 14, 'bold'),
            foreground=parent.HEADER_COLOR
        ).grid(row=0, column=1, sticky=tk.W)
        
        position_age = f"{player.primary_position.name} | Age: {player.age}"
        ttk.Label(
            player_display, 
            text=position_age, 
            font=(parent.FONT_FAMILY, 12),
            foreground=parent.TEXT_COLOR
        ).grid(row=1, column=1, sticky=tk.W)
        
        # Status based on morale
        status_text = "Very Happy" if player.morale >= 15 else \
                     "Satisfied" if player.morale >= 10 else \
                     "Concerned" if player.morale >= 5 else "Unhappy"
                     
        status_color = "#4CAF50" if player.morale >= 15 else \
                      "#8BC34A" if player.morale >= 10 else \
                      "#FFC107" if player.morale >= 5 else "#F44336"
        
        ttk.Label(
            player_display, 
            text=f"Status: {status_text}", 
            font=(parent.FONT_FAMILY, 12),
            foreground=status_color
        ).grid(row=2, column=1, sticky=tk.W)
        
        # Player attributes
        attributes_frame = ttk.Frame(left_col, style='Panel.TFrame', padding=10)
        attributes_frame.pack(fill=tk.X, pady=10)
        attributes_frame.configure(relief='solid', borderwidth=1)
        
        # Title for attributes section
        ttk.Label(
            attributes_frame, 
            text="KEY ATTRIBUTES", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.HEADER_COLOR
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # Attributes grid for better alignment
        attr_grid = ttk.Frame(attributes_frame, style='Dark.TFrame')
        attr_grid.pack(fill=tk.X)
        
        # Rating display with visual styling
        ttk.Label(attr_grid, text="Overall:", style='Info.TLabel').grid(row=0, column=0, sticky=tk.W, pady=5)
        
        rating_value = ttk.Frame(attr_grid, style='Dark.TFrame', width=50, height=26)
        rating_value.grid(row=0, column=1, sticky=tk.W, pady=5, padx=10)
        rating_value.pack_propagate(False)
        
        ovr_bg_color = "#1A9B00" if player.overall_rating() >= 50 else \
                      "#4CAF50" if player.overall_rating() >= 47 else \
                      "#8BC34A" if player.overall_rating() >= 44 else \
                      "#FFC107" if player.overall_rating() >= 40 else "#FF9800"
        
        rating_label = ttk.Label(
            rating_value,
            text=f"{to_100_scale(player.overall_rating())}", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground="#FFFFFF",
            background=ovr_bg_color
        )
        rating_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Potential with visual styling
        ttk.Label(attr_grid, text="Potential:", style='Info.TLabel').grid(row=1, column=0, sticky=tk.W, pady=5)
        
        pot_value = ttk.Frame(attr_grid, style='Dark.TFrame', width=50, height=26)
        pot_value.grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)
        pot_value.pack_propagate(False)
        
        pot_bg_color = "#1A9B00" if player.potential_grade in ['A+', 'A'] else \
                      "#4CAF50" if player.potential_grade in ['A-', 'B+'] else \
                      "#8BC34A" if player.potential_grade in ['B', 'B-'] else \
                      "#FFC107" if player.potential_grade in ['C+', 'C'] else "#FF9800"
        
        pot_label = ttk.Label(
            pot_value,
            text=player.potential_grade, 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground="#FFFFFF",
            background=pot_bg_color
        )
        pot_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Current contract details
        contract_frame = ttk.Frame(left_col, style='Panel.TFrame', padding=10)
        contract_frame.pack(fill=tk.X, pady=10)
        contract_frame.configure(relief='solid', borderwidth=1)
        
        ttk.Label(
            contract_frame, 
            text="CURRENT CONTRACT", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.HEADER_COLOR
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # Contract details grid
        contract_grid = ttk.Frame(contract_frame, style='Dark.TFrame')
        contract_grid.pack(fill=tk.X)
        
        current_salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
        years_left = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 0))
        
        ttk.Label(contract_grid, text="Salary:", style='Info.TLabel').grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(
            contract_grid, 
            text=f"${current_salary:,}", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.ACCENT_COLOR
        ).grid(row=0, column=1, sticky=tk.W, pady=5, padx=10)
        
        ttk.Label(contract_grid, text="Years Remaining:", style='Info.TLabel').grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(
            contract_grid, 
            text=str(years_left), 
            font=(parent.FONT_FAMILY, 12)
        ).grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)
        
        # --- CONTRACT OFFER (RIGHT COLUMN) ---
        
        # Offer header
        offer_header = ttk.Frame(right_col, style='SubHeader.TFrame', padding=(5, 3))
        offer_header.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            offer_header, 
            text="CONTRACT OFFER", 
            style='SubTitle.TLabel',
            font=(parent.FONT_FAMILY, 12, 'bold')
        ).pack(anchor=tk.W)
        
        # Market value display with accent styling
        market_frame = ttk.Frame(right_col, style='TitleBar.TFrame', padding=10)
        market_frame.pack(fill=tk.X, pady=10)
        market_frame.configure(relief='solid', borderwidth=1)
        
        ttk.Label(
            market_frame, 
            text="ESTIMATED MARKET VALUE", 
            font=(parent.FONT_FAMILY, 11, 'bold'),
            foreground=parent.HEADER_COLOR
        ).pack(anchor=tk.W)
        
        ttk.Label(
            market_frame, 
            text=f"${self.market_value:,}", 
            font=(parent.FONT_FAMILY, 16, 'bold'),
            foreground=parent.ACCENT_COLOR
        ).pack(anchor=tk.W, pady=5)
        
        # Player interest display
        interest_level = "Very Interested" if player.morale >= 15 else \
                        "Interested" if player.morale >= 10 else \
                        "Somewhat Interested" if player.morale >= 5 else "Not Interested"
                        
        interest_color = "#4CAF50" if player.morale >= 15 else \
                        "#8BC34A" if player.morale >= 10 else \
                        "#FFC107" if player.morale >= 5 else "#F44336"
                        
        interest_text = f"Player Interest: {interest_level}"
        
        interest_frame = ttk.Frame(right_col, style='Panel.TFrame', padding=10)
        interest_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            interest_frame, 
            text=interest_text, 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=interest_color
        ).pack(anchor=tk.W)
        
        # Rules info
        rules_frame = ttk.Frame(right_col, style='Panel.TFrame', padding=10)
        rules_frame.pack(fill=tk.X, pady=10)
        rules_frame.configure(background="#2A2A2A")
        
        ttk.Label(
            rules_frame, 
            text="NHL Contract Rules", 
            font=(parent.FONT_FAMILY, 11, 'bold'),
            foreground=parent.HEADER_COLOR
        ).pack(anchor=tk.W)
        
        ttk.Label(
            rules_frame, 
            text="• Maximum 8 years for own players\n• Minimum salary: $750,000\n• All contracts are guaranteed", 
            style='Info.TLabel',
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=5)
        
        # Offer inputs section
        inputs_frame = ttk.Frame(right_col, style='Panel.TFrame', padding=10)
        inputs_frame.pack(fill=tk.X, pady=10)
        inputs_frame.configure(relief='solid', borderwidth=1)
        
        ttk.Label(
            inputs_frame, 
            text="YOUR OFFER", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.HEADER_COLOR
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # Salary input with visual enhancements
        salary_label_frame = ttk.Frame(inputs_frame, style='Dark.TFrame')
        salary_label_frame.pack(fill=tk.X)
        
        ttk.Label(
            salary_label_frame, 
            text="Salary Per Year:", 
            font=(parent.FONT_FAMILY, 11),
            foreground=parent.TEXT_COLOR
        ).pack(anchor=tk.W)
        
        # Input with dollar sign
        salary_input_frame = ttk.Frame(inputs_frame, style='Dark.TFrame')
        salary_input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            salary_input_frame, 
            text="$", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.TEXT_COLOR
        ).pack(side=tk.LEFT)
        
        # Default to market value
        self.salary_var = tk.StringVar(master=self, value=f"{self.market_value:,}")
        salary_entry = ttk.Entry(salary_input_frame, textvariable=self.salary_var, width=15, font=(parent.FONT_FAMILY, 12))
        salary_entry.pack(side=tk.LEFT, padx=5)
        
        # Salary guideline
        min_salary = max(750000, int(self.market_value * 0.8))
        max_salary = int(self.market_value * 1.2)
        
        guideline_frame = ttk.Frame(inputs_frame, style='Dark.TFrame')
        guideline_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            guideline_frame, 
            text=f"Recommended Range: ${min_salary:,} to ${max_salary:,}",
            font=(parent.FONT_FAMILY, 10),
            foreground="#AAAAAA"
        ).pack(anchor=tk.W)
        
        # Contract term with slider
        term_label_frame = ttk.Frame(inputs_frame, style='Dark.TFrame', padding=(0, 10, 0, 0))
        term_label_frame.pack(fill=tk.X)
        
        ttk.Label(
            term_label_frame, 
            text="Contract Length:", 
            font=(parent.FONT_FAMILY, 11),
            foreground=parent.TEXT_COLOR
        ).pack(anchor=tk.W)
        
        # Max 8 years per NHL rules for extending own players
        max_years = 8
        
        self.years_var = tk.IntVar(master=self, value=2)
        years_scale_frame = ttk.Frame(inputs_frame, style='Dark.TFrame', padding=(0, 5))
        years_scale_frame.pack(fill=tk.X)
        
        years_scale = ttk.Scale(
            years_scale_frame, 
            from_=1, 
            to=max_years, 
            variable=self.years_var,
            orient=tk.HORIZONTAL
        )
        years_scale.pack(fill=tk.X)
        
        # Year labels below slider
        years_label_frame = ttk.Frame(inputs_frame, style='Dark.TFrame')
        years_label_frame.pack(fill=tk.X, pady=5)
        
        # Create tick marks for each year
        for year in range(1, max_years + 1):
            year_percent = (year - 1) / (max_years - 1)
            year_frame = ttk.Frame(years_label_frame, style='Dark.TFrame')
            year_frame.place(relx=year_percent, rely=0, anchor=tk.N)
            
            ttk.Label(
                year_frame, 
                text=str(year), 
                font=(parent.FONT_FAMILY, 9),
                foreground="#AAAAAA"
            ).pack()
        
        # Current selected years display
        selected_years_frame = ttk.Frame(inputs_frame, style='Dark.TFrame', padding=(0, 5))
        selected_years_frame.pack(fill=tk.X)
        
        years_display = ttk.Label(
            selected_years_frame, 
            text="2 Years", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.ACCENT_COLOR
        )
        years_display.pack(anchor=tk.CENTER)
        
        # Update year display when slider changes
        def update_years_display(*args):
            years = self.years_var.get()
            years_display.configure(text=f"{years} {'Year' if years == 1 else 'Years'}")
            
        self.years_var.trace_add("write", update_years_display)
        
        # Total contract value
        total_frame = ttk.Frame(right_col, style='Panel.TFrame', padding=10)
        total_frame.pack(fill=tk.X, pady=10)
        total_frame.configure(background="#2A2A2A")
        
        self.total_value_label = ttk.Label(
            total_frame, 
            text="Total Contract: $0", 
            font=(parent.FONT_FAMILY, 12, 'bold'),
            foreground=parent.HEADER_COLOR
        )
        self.total_value_label.pack(anchor=tk.W)
        
        # Update total when values change
        def update_total(*args):
            try:
                salary_str = self.salary_var.get().replace(',', '')
                salary = int(salary_str)
                years = self.years_var.get()
                total = salary * years
                self.total_value_label.configure(text=f"Total Contract: ${total:,}")
            except ValueError:
                self.total_value_label.configure(text="Total Contract: $0")
                
        self.salary_var.trace_add("write", update_total)
        self.years_var.trace_add("write", update_total)
        
        # Trigger initial update
        update_total()
        
        # Action buttons
        buttons_frame = ttk.Frame(main_frame, style='Dark.TFrame', padding=(0, 15, 0, 0))
        buttons_frame.pack(fill=tk.X)
        
        submit_btn = ttk.Button(
            buttons_frame, 
            text="Submit Offer", 
            style='Accent.TButton',
            command=self.submit_offer
        )
        submit_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(
            buttons_frame, 
            text="Cancel", 
            style='Secondary.TButton',
            command=self.destroy
        )
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def calculate_market_value(self, player):
        """Calculate the player's market value based on attributes."""
        # Base value determined by overall rating
        base_value = player.overall_rating() * 100000
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= player.age <= 29:
            age_modifier = 1.2
        elif player.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((player.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if player.primary_position.name == 'C':
            position_modifier = 1.15
        elif player.primary_position.name in ['LD', 'RD']:
            position_modifier = 1.1
        elif player.primary_position.name == 'G':
            # Goalies have different value curve
            position_modifier = 1.0 if player.overall_rating() >= 50 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if player.age <= 25:
            potential_map = {'A+': 1.5, 'A': 1.4, 'B+': 1.3, 'B': 1.2, 'C+': 1.1}
            grade = player.potential_grade
            potential_modifier = potential_map.get(grade, 1.0)
        
        # Calculate final market value
        market_value = base_value * age_modifier * position_modifier * potential_modifier
        
        # Round to nearest $50,000 for clean numbers
        market_value = round(market_value / 50000) * 50000
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
                  
    def submit_offer(self):
        """Process the contract extension offer."""
        try:
            # Parse the salary value, removing commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()
            
            # Input validation
            if salary < 750000:
                messagebox.showerror("Invalid Salary", "Salary must be at least $750,000 (league minimum).")
                return
                
            if years < 1 or years > 8:
                messagebox.showerror("Invalid Term", "Contract term must be between 1 and 8 years.")
                return
            
            # Set the values on the player object first
            self.player.salary = salary
            self.player.contract_years = years
            
            # Determine if player accepts based on how fair the offer is
            fair_value = self.market_value
            offer_percent = salary / fair_value
            
            # Base acceptance chance
            accept_chance = 0.5
            
            # Adjust based on offer vs market value
            if offer_percent >= 1.1:  # Great offer
                accept_chance = 0.9
            elif offer_percent >= 1.0:  # Fair offer
                accept_chance = 0.7
            elif offer_percent >= 0.9:  # Slightly under market
                accept_chance = 0.5
            elif offer_percent >= 0.8:  # Under market
                accept_chance = 0.3
            else:  # Way under market
                accept_chance = 0.1
                
            # Adjust based on player morale
            if self.player.morale >= 15:  # Very happy
                accept_chance += 0.2
            elif self.player.morale >= 10:  # Happy
                accept_chance += 0.1
            elif self.player.morale < 5:  # Unhappy
                accept_chance -= 0.2
                
            # Cap at 0.95 - always a small chance to reject
            accept_chance = min(0.95, accept_chance)
            
            # Determine if accepted
            accepted = random.random() < accept_chance
            
            # Apply the result
            if accepted:
                # Update contract details
                self.player.contract.salary = salary
                self.player.contract.years_remaining = years
                
                # Set extension flag to avoid free agency
                self.player.contract.is_extended = True
                
                # Adjust morale based on quality of deal
                if offer_percent >= 1.1:
                    self.player.morale = min(20, self.player.morale + 2)
                elif offer_percent >= 1.0:
                    self.player.morale = min(20, self.player.morale + 1)
                
                messagebox.showinfo(
                    "Contract Accepted", 
                    f"{self.player.full_name} has accepted your extension offer for ${salary:,} over {years} years."
                )
            else:
                # Determine counter offer if rejected
                counter_salary = max(int(fair_value * 1.05), salary + 250000)
                counter_salary = round(counter_salary / 50000) * 50000  # Round to nearest 50k
                
                # Adjust morale down slightly for rejection
                self.player.morale = max(1, self.player.morale - 1)
                
                message = f"{self.player.full_name} has rejected your extension offer for ${salary:,} over {years} years.\n\n"
                message += f"Agent: \"We were hoping for something closer to ${counter_salary:,} per year.\""
                
                messagebox.showinfo("Contract Rejected", message)
            
            self.destroy()
            
            # Refresh any open contract extension windows
            for window_name, window in self.parent.open_windows.items():
                if isinstance(window, ContractExtensionsWindow) and window.winfo_exists():
                    window.eligible_players = window.get_eligible_players()
                    window._populate_tree()
                    
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for salary.")

class GMOptionsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("GM Options")
        self.geometry("500x720")
        self.configure(bg=parent.BG_COLOR)
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('TButton', font=(parent.FONT_FAMILY, 11, 'bold'), foreground='white', background=parent.ACCENT_COLOR, padding=(10, 6), borderwidth=0)
        self.style.map('TButton', background=[('active', parent.ACCENT_ACTIVE), ('hover', parent.ACCENT_HOVER)])

        # Title bar
        title_bar = ttk.Frame(self, padding=(20, 10))
        title_bar.pack(fill="x")
        ttk.Label(title_bar, text="GM Options", font=(parent.FONT_FAMILY, 16, 'bold'), 
                 background=parent.BG_COLOR, foreground=parent.HEADER_COLOR).pack()
        
        # Subtitle
        subtitle = ttk.Label(title_bar, text="Executive Management Tools", 
                           font=(parent.FONT_FAMILY, 10), 
                           background=parent.BG_COLOR, foreground=parent.TEXT_COLOR)
        subtitle.pack(pady=(0, 5))

        # Main content frame
        content_frame = ttk.Frame(self, padding=20)
        content_frame.pack(fill="both", expand=True)

        # Player Management section
        player_section = ttk.LabelFrame(content_frame, text="🎯 Player Management", padding=15)
        player_section.pack(fill="x", pady=(0, 15))
        
        ttk.Button(player_section, text="📋 Player Shortlist", 
                  command=self.open_shortlist_window).pack(fill="x", pady=3)
        ttk.Button(player_section, text="👑 Set Captains", 
                  command=parent.open_set_captains_window).pack(fill="x", pady=3)
        
        # Executive Actions section
        exec_section = ttk.LabelFrame(content_frame, text="🏢 Executive Actions", padding=15)
        exec_section.pack(fill="x", pady=(0, 15))
        
        ttk.Button(exec_section, text="📊 GM Dashboard", 
                  command=self.open_gm_dashboard).pack(fill="x", pady=3)
        ttk.Button(exec_section, text="📈 Team Analytics", 
                  command=self.open_team_analytics).pack(fill="x", pady=3)
        ttk.Button(exec_section, text="🎯 Season Goals", 
                  command=self.open_season_goals).pack(fill="x", pady=3)
        
        # Quick Actions section
        quick_section = ttk.LabelFrame(content_frame, text="⚡ Quick Actions", padding=15)
        quick_section.pack(fill="x", pady=(0, 15))
        
        ttk.Button(quick_section, text="🔄 Auto-Negotiate Extensions", 
                  command=self.auto_negotiate_extensions).pack(fill="x", pady=3)
        ttk.Button(quick_section, text="📧 Check Inbox", 
                  command=parent.open_inbox_window).pack(fill="x", pady=3)

        # Game Presentation section — visual PBP viewer toggle lives here
        # (moved off the crowded menu bar)
        pres_section = ttk.LabelFrame(content_frame, text="Game Presentation", padding=15)
        pres_section.pack(fill="x", pady=(0, 15))
        self._viewer_btn = ttk.Button(pres_section, text="",
                                      command=self._toggle_viewer)
        self._viewer_btn.pack(fill="x", pady=3)
        self._refresh_viewer_btn()

        # Close button
        ttk.Button(content_frame, text="Close", command=self.destroy).pack(fill="x", pady=(10, 0))

    def _viewer_enabled(self):
        try:
            return bool(self.parent.get_settings().get('simulation', {}).get('use_game_viewer', False))
        except Exception:
            return False

    def _refresh_viewer_btn(self):
        state = "ON" if self._viewer_enabled() else "OFF"
        self._viewer_btn.config(text=f"Watch Games Live: {state}")

    def _toggle_viewer(self):
        self.parent.toggle_game_viewer()
        self._refresh_viewer_btn()

    def open_shortlist_window(self):
        """Open the player shortlist management window"""
        from shortlist_system import ShortlistWindow
        if 'shortlist' not in self.parent.open_windows or not self.parent.open_windows['shortlist'].winfo_exists():
            self.parent.open_windows['shortlist'] = ShortlistWindow(self.parent)
        self.parent.open_windows['shortlist'].focus_set()
    
    def open_gm_dashboard(self):
        """Open GM dashboard with key team metrics"""
        messagebox.showinfo("GM Dashboard", 
                           "GM Dashboard coming soon!\n\nWill include:\n• Team Performance Overview\n• Budget Management\n• Contract Status\n• Season Progress")
    
    def open_team_analytics(self):
        """Open advanced team analytics"""
        messagebox.showinfo("Team Analytics", 
                           "Team Analytics coming soon!\n\nWill include:\n• Player Performance Trends\n• Line Combination Analysis\n• Opponent Scouting Reports\n• Statistical Breakdowns")
    
    def open_season_goals(self):
        """Open season goals and objectives"""
        messagebox.showinfo("Season Goals", 
                           "Season Goals coming soon!\n\nWill include:\n• Playoff Expectations\n• Development Targets\n• Budget Objectives\n• Achievement Tracking")
    
    def auto_negotiate_extensions(self):
        """Auto-negotiate contract extensions with expiring players"""
        expiring = []
        team = self.parent.user_team
        
        # Find players with 1 year left on contract
        for player in team.roster + team.ahl_roster:
            years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 0))
            if years == 1:
                expiring.append(player)
        
        # Find staff with 1 year left on contract
        for staff in getattr(team, "staff", []):
            years = getattr(staff, "contract_years", getattr(staff, "years_remaining", 0))
            if years == 1:
                expiring.append(staff)
        
        if not expiring:
            messagebox.showinfo("No Extensions Needed", "No expiring contracts found.")
            return
        
        # Confirm action
        if not messagebox.askyesno("Confirm Auto-Negotiate", 
                                 f"Automatically negotiate extensions with {len(expiring)} expiring contracts?"):
            return
        
        results = []
        for person in expiring:
            # Ensure salary and contract_years attributes exist
            salary = getattr(person, "salary", getattr(person.contract, "salary", 750000))
            person.salary = salary
            person.contract_years = getattr(person, "contract_years", getattr(person.contract, "years_remaining", 1))
            accepted = self.parent.handle_contract_offer(person, extension=True)
            results.append(f"{getattr(person, 'full_name', getattr(person, 'name', 'Unknown'))}: {'Accepted' if accepted else 'Rejected'}")
        
        msg = "Auto-Negotiation Results:\n" + "\n".join(results)
        messagebox.showinfo("Extension Results", msg)

def test_enhanced_simulation():
    """Test the enhanced simulation and game viewer integration"""
    from game_classes import Team, Player, PlayerPosition, Contract, Staff, StaffRole
    import random
    
    def create_test_player(name, position, overall=15, jersey_num=1):
        """Create a test player with realistic attributes"""
        player = Player(
            first_name=name.split()[0],
            last_name=name.split()[1] if len(name.split()) > 1 else "Player",
            age=25,
            primary_position=position,
            jersey_number=jersey_num
        )
        
        # Set contract
        player.contract = Contract(salary=1000000, years_remaining=1)
        
        # Set enhanced attributes for realistic gameplay
        for attr in ['wristshot', 'slapshot', 'passing_accuracy', 'stickhandling', 
                    'shooting_accuracy', 'vision', 'hockey_iq', 'agility', 'speed',
                    'strength', 'endurance', 'stamina', 'composure', 'determination',
                    'reflexes', 'positioning', 'defensive_awareness', 'anticipation']:
            setattr(player, attr, random.randint(12, 18))
        
        # Set position on ice
        player.x = random.randint(10, 90)
        player.y = random.randint(10, 40)
        
        return player
    
    def create_test_team(team_name, city):
        """Create a test team with full roster"""
        team = Team(team_name=team_name, city=city, division="Test", conference="Test")
        
        # Create forwards
        forwards = [
            create_test_player(f"Forward {i}", PlayerPosition.CENTER if i % 3 == 0 else PlayerPosition.LEFT_WING if i % 3 == 1 else PlayerPosition.RIGHT_WING, jersey_num=10+i)
            for i in range(12)
        ]
        
        # Create defensemen
        defensemen = [
            create_test_player(f"Defense {i}", PlayerPosition.LEFT_DEFENSE if i % 2 == 0 else PlayerPosition.RIGHT_DEFENSE, jersey_num=1+i)
            for i in range(6)
        ]
        
        # Create goalies
        goalies = [
            create_test_player(f"Goalie {i}", PlayerPosition.GOALIE, jersey_num=30+i)
            for i in range(2)
        ]
        
        # Add special goalie attributes
        for goalie in goalies:
            for attr in ['reflexes', 'positioning', 'rebound_control', 'glove_hand', 'stick_side']:
                setattr(goalie, attr, random.randint(13, 19))
        
        team.roster = forwards + defensemen + goalies
        
        # Create staff
        team.staff = [
            Staff(first_name="Head", last_name="Coach", role=StaffRole.HEAD_COACH),
            Staff(first_name="Assistant", last_name="Coach", role=StaffRole.ASSISTANT_COACH)
        ]
        
        return team
    
    print("=" * 60)
    print("ENHANCED HOCKEY SIMULATION - STAGE 1 DEMONSTRATION")
    print("=" * 60)
    print()
    
    # Create test teams
    home_team = create_test_team("Thunderbirds", "Seattle")
    away_team = create_test_team("Eagles", "Philadelphia")
    
    print(f"Created teams: {home_team.team_name} vs {away_team.team_name}")
    print(f"Home roster: {len(home_team.roster)} players")
    print(f"Away roster: {len(away_team.roster)} players")
    print()
    
    # Run enhanced simulation with professional viewer
    print("Starting Stage 1: Enhanced Event Generation + Professional Viewer Integration")
    print("-" * 60)
    
    try:
        launch_game_viewer_with_sim(home_team, away_team)
    except Exception as e:
        print(f"Error launching game viewer: {e}")
        print("Running simulation only...")
        
        # Fallback: run simulation without viewer
        sim = AdvancedGameSim(home_team, away_team)
        winner, loser, scores, events, notable_events = sim.run()
        
        print(f"\nSimulation Results:")
        print(f"Winner: {winner.team_name}")
        print(f"Final Score: {scores[0]} - {scores[1]}")
        print(f"Total Events: {len(sim.event_log)}")
        print(f"Notable Events: {len(notable_events)}")
        print(f"Event Types Generated:")
        
        event_types = {}
        for event in sim.event_log:
            event_type = event['type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        for event_type, count in sorted(event_types.items()):
            print(f"  {event_type}: {count}")
        
        print("\nFirst 10 events:")
        for i, event in enumerate(sim.event_log[:10]):
            print(f"  {i+1}. {event['type']} at {event['timestamp']:.1f}s")
    
    print("\n" + "=" * 60)
    print("STAGE 1 & 2 COMPLETE: Enhanced Hockey Simulation")
    print("- More frequent events (6-12 per shift vs 1-4)")
    print("- Realistic player positioning based on role")
    print("- Enhanced event types with player names")
    print("- Professional game viewer integration")
    print("- Real-time event processing and synchronization")
    print("- Dynamic shot charts with real data")
    print("- Smooth player animations and visual effects")
    print("=" * 60)

def main():
    """Main function to start the game with splash launcher"""
    try:
        print("Starting Puck Dynasty...")
        
        # Import and launch splash screen first
        try:
            from splash_launcher import SplashLauncher
            print("Launching splash screen...")
            splash = SplashLauncher()
            splash._launch_enhanced = False  # Initialize flag
            splash.mainloop()
            
            # After mainloop exits, check if we should launch enhanced
            if getattr(splash, '_launch_enhanced', False):
                splash._run_enhanced_launcher()
            
            print("Application completed")
            
        except ImportError as e:
            print(f"Splash launcher not available: {e}")
            print("Falling back to direct launch...")
            _direct_launch()
            
        except Exception as e:
            print(f"Splash launcher error: {e}")
            import traceback
            traceback.print_exc()
            print("Falling back to direct launch...")
            _direct_launch()
            
    except KeyboardInterrupt:
        print("Interrupted by user")
        
    except Exception as e:
        import traceback
        print("Critical error launching Hockey Manager:", e)
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Critical Launch Error", f"Failed to start Hockey Manager:\n{str(e)}")
        except:
            pass

def _direct_launch():
    """Direct launch fallback method"""
    try:
        print("🚀 Starting Hockey Manager directly...")
        
        # Create game manager with default settings
        print("🎮 Initializing game manager...")
        gm = GameManager()
        print("✅ Game manager created successfully")
        
        # Apply default startup settings to generate rosters
        print("🏒 Applying default startup settings...")
        default_settings = {
            'database_size': 'Medium',
            'fantasy_draft': False,
            'user_team': 'Carolina Hurricanes'
        }
        gm.apply_startup_settings(default_settings)
        print("✅ Startup settings applied, rosters generated")
        
        # Create and start the main game application
        print("🖥️ Creating main application window...")
        app = HockeyManagerGUI(gm)
        print("✅ GUI created successfully")
        
        # Ensure window is visible and focused
        print("👁️ Making window visible...")
        app.lift()
        app.focus_force()
        app.attributes('-topmost', True)
        app.after(100, lambda: app.attributes('-topmost', False))
        
        print("🎯 Starting main loop...")
        app.mainloop()
        print("✅ Application closed normally")
        
    except Exception as e:
        import traceback
        print("❌ Direct launch error:", e)
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Launch Error", f"Failed to start Hockey Manager:\n{str(e)}")
        except:
            pass
    
# --- Main execution
if __name__ == "__main__":
    import sys
    
    # Check for test argument
    if len(sys.argv) > 1 and sys.argv[1] == "test_enhanced_sim":
        test_enhanced_simulation()
    elif len(sys.argv) > 1 and sys.argv[1] == "direct":
        # Direct launch — new-game setup wizard (Quick Start / Custom Setup)
        import tkinter as tk
        from new_game_setup import open_setup_wizard, build_database_config

        holder = {}
        root = tk.Tk()
        root.withdraw()

        wiz = open_setup_wizard(root, lambda cfg: holder.setdefault('config', cfg))
        root.wait_window(wiz)
        config = holder.get('config')
        root.destroy()

        if config:
            try:
                print("Starting Puck Dynasty with setup wizard settings...")
                settings = {
                    'database_size': config['database_size'].capitalize(),
                    'database_config': build_database_config(config),
                    'fantasy_draft': False,
                    'user_team': config['user_team'],
                    'user_league': config['user_league'],
                    'gm_name': config['gm_name'],
                    'fog_of_war': config['fog_of_war'],
                    'sim_detail': config['sim_detail'],
                }
                gm = GameManager()
                gm.apply_startup_settings(settings)
                gm.set_user_team(config['user_team'])

                app = HockeyManagerGUI(gm)
                app.startup_settings = settings
                app._update_game_viewer_button_state()
                app.mainloop()

            except Exception as e:
                import traceback
                print("Error launching Hockey Manager:", e)
                traceback.print_exc()
                try:
                    messagebox.showerror("Launch Error", f"Failed to start Hockey Manager:\n{str(e)}")
                except:
                    pass
        else:
            print("User cancelled setup - game not launched")
    else:
        # Use the main function for direct launch
        main()
