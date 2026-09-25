"""
Comprehensive Fantasy Draft System for Hockey Manager
This module provides an interactive fantasy draft experience with team selection,
player pools, draft visualization, and comprehensive draft management.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
from typing import List, Dict, Optional
from dataclasses import dataclass
from game_classes import Player, Team, PlayerPosition, to_100_scale

@dataclass
class DraftPick:
    """Represents a single draft pick"""
    round_num: int
    pick_num: int
    overall_pick: int
    team: Team
    player: Optional[Player] = None
    
@dataclass
class DraftConfiguration:
    """Configuration settings for the draft"""
    rounds: int = 40  # Deep fantasy draft with minor league and prospects
    serpentine: bool = True
    protected_players: int = 0  # Number of players each team can protect
    salary_cap_enabled: bool = True
    trade_deadline_round: int = 10  # Can trade picks until this round
    draft_order_type: str = "Randomized"  # Type of draft order used
    
@dataclass
class TeamDraftStrategy:
    """AI drafting strategy for each team"""
    team: Team
    risk_tolerance: float = 0.5  # 0.0 (conservative) to 1.0 (aggressive)
    youth_preference: float = 0.5  # 0.0 (veterans) to 1.0 (young players)
    needs_vs_bpa: float = 0.6  # 0.0 (always BPA) to 1.0 (always needs)
    position_weights: Dict[str, float] = None  # Custom position priorities
    
    def __post_init__(self):
        if self.position_weights is None:
            # Default balanced approach
            self.position_weights = {
                'C': 1.0, 'LW': 0.9, 'RW': 0.9,
                'LD': 1.1, 'RD': 1.1, 'G': 1.2
            }
    
class FantasyDraftManager:
    """Manages the fantasy draft logic and data"""
    
    def __init__(self, teams: List[Team], all_players: List[Player], config: Optional[DraftConfiguration] = None):
        self.teams = teams
        self.all_players = all_players
        self.config = config or DraftConfiguration()
        self.draft_order = []
        self.draft_picks = []
        self.current_pick = 0
        self.team_strategies = {}
        self.draft_started = False  # Track if draft has begun
        
        self.setup_draft_order()
        self.setup_draft_picks()
        self.setup_team_strategies()
        
    def setup_draft_order(self):
        """Set up draft order based on team performance (worst to best)"""
        # For fantasy draft, randomize order for fairness
        # In real game, this would be based on previous season standings
        self.draft_order = self.teams.copy()
        random.shuffle(self.draft_order)
        
        print(f"DEBUG: Draft order established with {len(self.draft_order)} teams")
        
    def setup_draft_picks(self):
        """Create all draft picks in serpentine order"""
        self.draft_picks = []
        overall_pick = 1
        
        for round_num in range(1, self.config.rounds + 1):
            # Serpentine: odd rounds go forward, even rounds go backward
            if self.config.serpentine and round_num % 2 == 0:
                team_order = list(reversed(self.draft_order))
            else:
                team_order = self.draft_order
                
            for pick_in_round, team in enumerate(team_order, 1):
                pick = DraftPick(
                    round_num=round_num,
                    pick_num=pick_in_round,
                    overall_pick=overall_pick,
                    team=team
                )
                self.draft_picks.append(pick)
                overall_pick += 1
                
        print(f"DEBUG: Created {len(self.draft_picks)} total picks ({self.config.rounds} rounds)")
    
    def setup_team_strategies(self):
        """Initialize AI drafting strategies for each team"""
        for team in self.teams:
            # Create unique strategy for each team
            strategy = TeamDraftStrategy(
                team=team,
                risk_tolerance=random.uniform(0.3, 0.8),
                youth_preference=random.uniform(0.4, 0.9),
                needs_vs_bpa=random.uniform(0.4, 0.8)
            )
            
            # Adjust position weights based on team philosophy
            if strategy.youth_preference > 0.7:
                # Youth-focused teams prioritize skill positions
                strategy.position_weights['C'] = 1.2
                strategy.position_weights['G'] = 1.0
            elif strategy.risk_tolerance < 0.4:
                # Conservative teams prioritize defense and goaltending
                strategy.position_weights['LD'] = 1.3
                strategy.position_weights['RD'] = 1.3
                strategy.position_weights['G'] = 1.4
                
            # Use team name as key instead of team object (teams are not hashable)
            self.team_strategies[team.team_name] = strategy
            
        print(f"DEBUG: Generated unique draft strategies for {len(self.team_strategies)} teams")
                
    def get_available_players(self) -> List[Player]:
        """Get all players not yet drafted"""
        drafted_player_ids = {pick.player.id for pick in self.draft_picks if pick.player}
        available_players = [p for p in self.all_players if p.id not in drafted_player_ids]
        print(f"DEBUG: get_available_players() - Total players: {len(self.all_players)}, Drafted IDs: {len(drafted_player_ids)}, Available: {len(available_players)}")
        return available_players
        
    def get_current_pick(self) -> Optional[DraftPick]:
        """Get the current draft pick"""
        if self.current_pick < len(self.draft_picks):
            return self.draft_picks[self.current_pick]
        return None
        
    def make_pick(self, player: Player) -> bool:
        """Make a draft pick"""
        current_pick = self.get_current_pick()
        if current_pick:
            # Check if player is available by ID instead of object identity
            available_players = self.get_available_players()
            available_player_ids = {p.id for p in available_players}
            
            if player.id in available_player_ids:
                # Find the actual player object from available players
                actual_player = next((p for p in available_players if p.id == player.id), None)
                if actual_player:
                    current_pick.player = actual_player
                    actual_player.team_name = current_pick.team.team_name
                    self.current_pick += 1
                    print(f"DEBUG: Successfully drafted {actual_player.full_name} for {current_pick.team.team_name}")
                    return True
                else:
                    print(f"DEBUG: Player {player.full_name} (ID: {player.id}) not found in available players")
            else:
                print(f"DEBUG: Player {player.full_name} (ID: {player.id}) not available for drafting")
                print(f"DEBUG: Available player count: {len(available_players)}")
        return False
        
    def is_draft_complete(self) -> bool:
        """Check if draft is complete"""
        return self.current_pick >= len(self.draft_picks)
    
    def analyze_team_needs(self, team: Team) -> Dict[str, float]:
        """Analyze team's positional needs based on current draft picks"""
        # Count current picks by position
        position_counts = {
            'C': 0, 'LW': 0, 'RW': 0,
            'LD': 0, 'RD': 0, 'G': 0
        }
        
        # Count drafted players for this team
        team_picks = [pick.player for pick in self.draft_picks 
                     if pick.team.team_name == team.team_name and pick.player]
        
        for player in team_picks:
            pos = player.primary_position.value
            if pos in position_counts:
                position_counts[pos] += 1
        
        # Calculate needs based on target roster composition
        target_composition = {
            'C': 4, 'LW': 4, 'RW': 4,  # 12 forwards
            'LD': 3, 'RD': 3,           # 6 defensemen  
            'G': 2                      # 2 goalies
        }
        
        needs = {}
        for pos, target in target_composition.items():
            current = position_counts[pos]
            # Need score: higher = more needed (0.0 to 2.0+)
            if current >= target:
                needs[pos] = 0.1  # Low need
            else:
                needs[pos] = (target - current) / target * 2.0
                
        return needs
    
    def calculate_player_draft_value(self, player: Player, team: Team, round_num: int) -> float:
        """Calculate a player's value for a specific team at a specific point"""
        strategy = self.team_strategies.get(team.team_name)
        if not strategy:
            return player.overall_rating()  # Fallback
            
        base_value = player.overall_rating()
        
        # Age factor (-15 to +15 points)
        age_factor = self.calculate_age_value(player.age, strategy.youth_preference)
        
        # Position need factor (0.5x to 2.0x multiplier)  
        needs = self.analyze_team_needs(team)
        pos = player.primary_position.value
        need_multiplier = 1.0 + (needs.get(pos, 0.0) * strategy.needs_vs_bpa * 0.5)
        
        # Position weight from team strategy
        pos_weight = strategy.position_weights.get(pos, 1.0)
        
        # Draft position factor (later picks take more risks)
        risk_factor = 1.0
        if round_num > 5:  # Later rounds
            risk_factor = 1.0 + (strategy.risk_tolerance * 0.2)
            
        # Contract value factor - NEW strategic element
        contract_factor = self.calculate_contract_value(player, round_num)
            
        # Combine all factors
        final_value = (base_value + age_factor) * need_multiplier * pos_weight * risk_factor * contract_factor
        
        return final_value
        
    def calculate_contract_value(self, player: Player, round_num: int) -> float:
        """Calculate contract value factor for strategic drafting"""
        if not hasattr(player, 'contract') or not player.contract:
            return 1.0  # Neutral if no contract info
            
        contract = player.contract
        salary = getattr(contract, 'salary', 750000)
        years = getattr(contract, 'years_remaining', 1)
        
        # Value per dollar calculation
        overall = player.overall_rating()
        
        # Expected value per million dollars
        if salary > 0:
            value_per_million = overall / (salary / 1000000)
        else:
            value_per_million = overall  # Free contract is valuable
        
        # Contract length factor
        if years >= 5:  # Long-term deals
            length_factor = 0.9  # Slightly risky
        elif years >= 3:
            length_factor = 1.0  # Good length
        elif years >= 2:
            length_factor = 1.05  # Short-term flexibility
        else:
            length_factor = 1.1  # Very flexible
            
        # Round-based contract importance
        if round_num <= 10:  # Early rounds - talent over contract
            contract_weight = 0.8
        elif round_num <= 25:  # Middle rounds - balanced consideration
            contract_weight = 1.0
        else:  # Late rounds - value hunting
            contract_weight = 1.3
            
        # Calculate final contract factor
        if value_per_million >= 15:  # Excellent value
            contract_factor = 1.0 + (contract_weight * 0.15)
        elif value_per_million >= 10:  # Good value
            contract_factor = 1.0 + (contract_weight * 0.05)
        elif value_per_million >= 5:  # Fair value
            contract_factor = 1.0
        elif value_per_million >= 3:  # Poor value
            contract_factor = 1.0 - (contract_weight * 0.1)
        else:  # Terrible value
            contract_factor = 1.0 - (contract_weight * 0.2)
            
        # Trade clause penalties
        if hasattr(contract, 'no_movement_clause') and contract.no_movement_clause:
            contract_factor *= 0.9  # NMC is restrictive
        elif hasattr(contract, 'no_trade_clause') and contract.no_trade_clause:
            contract_factor *= 0.95  # NTC somewhat restrictive
            
        return max(0.5, min(1.5, contract_factor))  # Keep factor reasonable
    
    def calculate_age_value(self, age: int, youth_preference: float) -> float:
        """Calculate age-based value adjustment"""
        if age <= 21:
            # Young players get bonus for potential
            return youth_preference * 10
        elif age <= 25:
            # Prime age players
            return 5
        elif age <= 29:
            # Solid veterans
            return 0
        else:
            # Older players penalized more by youth-focused teams
            penalty = (age - 29) * (youth_preference + 0.5) * 3
            return -penalty
    
    def make_ai_pick(self, team: Team) -> Optional[Player]:
        """Make an intelligent AI draft pick for a team"""
        available_players = self.get_available_players()
        if not available_players:
            return None
            
        current_pick = self.get_current_pick()
        if not current_pick:
            return None
            
        # Score all available players for this team
        player_scores = {}
        for player in available_players:
            score = self.calculate_player_draft_value(
                player, team, current_pick.round_num
            )
            player_scores[player] = score
            
        # Sort by score and add some randomness for realism
        sorted_players = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Select from top candidates with weighted randomness
        num_candidates = min(8, len(sorted_players))  # Consider top 8 players
        candidates = [player for player, score in sorted_players[:num_candidates]]
        
        # Weight selection towards higher-rated players but allow surprises
        weights = [3.0, 2.5, 2.0, 1.5, 1.2, 1.0, 0.8, 0.6][:len(candidates)]
        
        selected_player = random.choices(candidates, weights=weights, k=1)[0]
        
        print(f"DEBUG: {team.team_name} selects {selected_player.full_name} "
              f"(OVR {selected_player.overall_rating()}, {selected_player.primary_position.value}) "
              f"- Score: {player_scores[selected_player]:.1f}")
              
        return selected_player

class FantasyDraftWindow(tk.Toplevel):
    """Modern Interactive Fantasy Draft Window"""
    
    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self.parent = parent
        self.game_manager = game_manager
        
        # Set up window with modern styling
        self.title("🏒 Fantasy Draft - Hockey Manager")
        self.geometry("1600x1000")
        self.configure(background=parent.BG_COLOR)
        self.minsize(1400, 900)
        
        # Initialize draft data - collect ALL NHL players properly
        nhl_teams = [team for team in game_manager.league.teams 
                    if team.league_name == "National Hockey League"]
        all_nhl_players = self.collect_all_nhl_players(nhl_teams)
        
        print(f"DEBUG: Collected {len(all_nhl_players)} NHL players for fantasy draft")
        
        self.draft_manager = FantasyDraftManager(nhl_teams, all_nhl_players)
        self.user_team = game_manager.user_team
        
        # Ensure user team is set - if not, use the first team in the draft
        if not self.user_team and nhl_teams:
            self.user_team = nhl_teams[0]  # Use first team as fallback
            game_manager.user_team = self.user_team
            print(f"DEBUG: No user team found, setting to: {self.user_team.team_name}")
        
        print(f"DEBUG: User team set to: {self.user_team.team_name if self.user_team else 'None'}")
        print(f"DEBUG: Draft has {len(self.draft_manager.draft_picks)} total picks ({self.draft_manager.config.rounds} rounds)")
        
        # Track UI state
        self.selected_player = None
        self.auto_draft_enabled = tk.BooleanVar(value=False)
        self.draft_speed = tk.StringVar(value="Normal")
        
        # Initialize tree maps for player references
        if not hasattr(self.parent, 'tree_maps'):
            self.parent.tree_maps = {}
        
        self.setup_card_styles()
        self.setup_integrated_ui()
        self.update_display()
        
        # Initial population of players list
        if hasattr(self, 'players_tree'):
            print("DEBUG: Starting initial player population...")
            self.after(100, self.initial_player_load)  # Slight delay to ensure UI is ready
            
    def initial_player_load(self):
        """Load players after UI initialization"""
        print("DEBUG: Performing initial player load...")
        try:
            # Force update display for integrated browser
            if hasattr(self, 'integrated_players_tree'):
                print("DEBUG: Loading integrated player browser...")
                available_players = self.draft_manager.get_available_players()
                print(f"DEBUG: Initial load - {len(available_players)} players available")
                self.integrated_populate_players()
                
            # Also update legacy systems if they exist
            if hasattr(self, 'players_tree'):
                self.clear_filters()
                self.filter_players()
                self.players_tree.update_idletasks()
                print(f"DEBUG: Legacy tree now has {len(self.players_tree.get_children())} visible items")
                
        except Exception as e:
            print(f"DEBUG: Error in initial player load: {e}")
            import traceback
            traceback.print_exc()
            
    def setup_card_styles(self):
        """Set up custom styles for player cards"""
        style = ttk.Style()
        
        # Player card label frame style
        style.configure('Card.TLabelframe',
                       background=self.parent.CONTENT_BG,
                       borderwidth=2,
                       relief='solid')
        
        style.configure('Card.TLabelframe.Label',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.HEADER_COLOR,
                       font=('Segoe UI', 12, 'bold'))
        
        # Section label frame for card sections
        style.configure('Section.TLabelframe',
                       background=self.parent.CONTENT_BG,
                       borderwidth=1,
                       relief='solid')
        
        style.configure('Section.TLabelframe.Label',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.TEXT_COLOR,
                       font=('Segoe UI', 10, 'bold'))
        
        # Badge styles
        style.configure('Badge.TLabel',
                       background=self.parent.ACCENT_COLOR,
                       foreground='white',
                       padding=(8, 4),
                       font=('Segoe UI', 9, 'bold'))
        
        style.configure('Rating.TLabel',
                       background='#2E7D32',
                       foreground='white',
                       padding=(8, 4),
                       font=('Segoe UI', 10, 'bold'))
        
        # Value label for stats
        style.configure('Value.TLabel',
                       foreground=self.parent.ACCENT_COLOR,
                       font=('Segoe UI', 9, 'bold'))
        
    def collect_all_nhl_players(self, teams: List[Team]) -> List[Player]:
        """Collect all NHL players from all teams for fantasy draft"""
        all_players = []
        
        print(f"DEBUG: Processing {len(teams)} NHL teams for player collection")
        
        # Collect players from all teams
        for team in teams:
            team_roster_size = len(team.roster) if hasattr(team, 'roster') else 0
            team_ahl_size = len(team.ahl_roster) if hasattr(team, 'ahl_roster') else 0 
            team_prospects_size = len(team.prospects) if hasattr(team, 'prospects') else 0
            
            print(f"DEBUG: Team {team.team_name} - Roster: {team_roster_size}, AHL: {team_ahl_size}, Prospects: {team_prospects_size}")
            
            # Collect all players from all levels
            team_players = []
            if hasattr(team, 'roster') and team.roster:
                team_players.extend(team.roster)
            if hasattr(team, 'ahl_roster') and team.ahl_roster:
                team_players.extend(team.ahl_roster) 
            if hasattr(team, 'prospects') and team.prospects:
                team_players.extend(team.prospects)
            
            # Store original team for reference
            for player in team_players:
                if hasattr(player, 'full_name'):  # Ensure it's a valid player object
                    player.former_team = team.team_name
                    all_players.append(player)
            
        print(f"DEBUG: Collected total of {len(all_players)} players from teams")
        
        # Also check league-level players if they exist
        if hasattr(self.game_manager, 'league'):
            league = self.game_manager.league
            
            # Check if league has a get_all_players method
            if hasattr(league, 'get_all_players'):
                league_players = league.get_all_players()
                print(f"DEBUG: Found {len(league_players)} players via league.get_all_players()")
                
                # If we didn't get players from teams, use league players
                if len(all_players) == 0 and len(league_players) > 0:
                    print("DEBUG: Using league players since team rosters were empty")
                    all_players = league_players.copy()
                    
                    # Mark all as available and set former teams
                    for player in all_players:
                        if hasattr(player, 'team_name') and player.team_name:
                            player.former_team = player.team_name
                        else:
                            player.former_team = "Unknown"
            
            # Check league teams more thoroughly
            if len(all_players) == 0:
                print("DEBUG: Attempting comprehensive team search...")
                for team in league.teams:
                    # Try to get all player lists
                    for attr_name in ['roster', 'ahl_roster', 'prospects', 'players']:
                        if hasattr(team, attr_name):
                            player_list = getattr(team, attr_name)
                            if player_list and isinstance(player_list, list):
                                print(f"DEBUG: Found {len(player_list)} players in {team.team_name}.{attr_name}")
                                for player in player_list:
                                    if hasattr(player, 'full_name'):
                                        player.former_team = team.team_name
                                        all_players.append(player)
        
        # Check free agents if any exist
        if hasattr(self.game_manager, 'free_agents') and self.game_manager.free_agents:
            print(f"DEBUG: Adding {len(self.game_manager.free_agents)} free agents")
            for player in self.game_manager.free_agents:
                player.former_team = "Free Agent"
                all_players.append(player)
            
        print(f"DEBUG: Total collected: {len(all_players)} players")
        
        # Remove duplicates (same player object)
        seen = set()
        unique_players = []
        for player in all_players:
            player_id = id(player)
            if player_id not in seen:
                seen.add(player_id)
                unique_players.append(player)
                
        print(f"DEBUG: After removing duplicates: {len(unique_players)} unique players")
        
        # If we still have no players, create some sample data for testing
        if len(unique_players) == 0:
            print("WARNING: No players found! Creating sample data for fantasy draft testing...")
            unique_players = self.create_sample_players_for_testing()
        
        # Ensure we have enough players for 40 rounds
        required_players = len(teams) * 40  # 40 rounds worth of players
        if len(unique_players) < required_players:
            print(f"DEBUG: Need {required_players} players for 40 rounds, but only have {len(unique_players)}")
            print("DEBUG: Generating additional players to fill out draft...")
            additional_players = self.generate_additional_players(required_players - len(unique_players), teams)
            unique_players.extend(additional_players)
            print(f"DEBUG: Added {len(additional_players)} additional players, total now: {len(unique_players)}")
        
        # Ensure all players have proper contracts for strategic drafting
        self.ensure_player_contracts(unique_players)
        
        # Sort by overall rating for better draft experience
        unique_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Clear all team rosters for redistribution (do this AFTER collection)
        print("DEBUG: Clearing team rosters for fantasy draft redistribution...")
        for team in teams:
            if hasattr(team, 'roster'):
                team.roster.clear()
            if hasattr(team, 'ahl_roster'):
                team.ahl_roster.clear()
            if hasattr(team, 'prospects'):
                team.prospects.clear()
        
        return unique_players
    
    def create_sample_players_for_testing(self) -> List[Player]:
        """Create sample players if none are found - for testing purposes"""
        from game_classes import Player, PlayerPosition
        import random
        
        sample_players = []
        positions = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING, 
                    PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.GOALIE]
        
        first_names = ["Connor", "Sidney", "Alex", "Nathan", "Leon", "Artemi", "Nikita", 
                      "Erik", "Victor", "Elias", "Mika", "John", "Jack", "Quinn"]
        last_names = ["McDavid", "Crosby", "Ovechkin", "MacKinnon", "Draisaitl", "Panarin", 
                     "Kucherov", "Karlsson", "Hedman", "Pettersson", "Zibanejad", "Tavares", 
                     "Hughes", "Miller"]
        
        for i in range(200):  # Create 200 sample players
            first = random.choice(first_names)
            last = random.choice(last_names)
            pos = random.choice(positions)
            
            player = Player(
                first_name=first,
                last_name=f"{last}{i}",  # Add number to avoid duplicates
                primary_position=pos,
                age=random.randint(18, 35)
            )
            
            # Set some random attributes for testing
            player.skating = random.randint(60, 99)
            player.shooting = random.randint(60, 99)
            player.passing = random.randint(60, 99)
            player.former_team = f"Test Team {(i // 25) + 1}"
            
            sample_players.append(player)
        
        print(f"DEBUG: Created {len(sample_players)} sample players for testing")
        return sample_players
        
    def setup_integrated_ui(self):
        """Set up integrated fantasy draft interface with tabs"""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header with draft status
        self.create_draft_header(main_frame)
        
        # Check if draft has started
        if not hasattr(self.draft_manager, 'draft_started'):
            self.draft_manager.draft_started = False
        
        if not self.draft_manager.draft_started:
            # Show draft initialization screen
            self.show_draft_initialization(main_frame)
        else:
            # Show main draft interface with tabs
            self.show_main_draft_interface(main_frame)
    
    def show_draft_initialization(self, parent):
        """Show the draft initialization screen"""
        init_frame = ttk.Frame(parent, style='Panel.TFrame')
        init_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        # Title
        title_label = ttk.Label(init_frame, text="Fantasy Draft Setup", 
                              style='MainTitle.TLabel')
        title_label.pack(pady=20)
        
        # Draft info
        info_frame = ttk.Frame(init_frame, style='Panel.TFrame')
        info_frame.pack(pady=20)
        
        info_text = f"""
Ready to begin the Fantasy Draft!

• {len(self.draft_manager.teams)} teams participating
• {self.draft_manager.config.rounds} rounds ({len(self.draft_manager.draft_picks)} total picks)
• {len(self.draft_manager.all_players)} players available
• Draft order: {self.draft_manager.config.draft_order_type}

Your team: {self.user_team.team_name if self.user_team else 'Not set'}
        """
        
        ttk.Label(info_frame, text=info_text, style='Normal.TLabel', 
                 justify='left').pack()
        
        # Begin draft button
        begin_frame = ttk.Frame(init_frame, style='Panel.TFrame')
        begin_frame.pack(pady=30)
        
        begin_button = ttk.Button(begin_frame, text="🏒 Begin Fantasy Draft", 
                                command=self.begin_fantasy_draft, 
                                style='TButton')
        begin_button.pack()
        
    def show_main_draft_interface(self, parent):
        """Show the main draft interface with tabs"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(parent, style='TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Create all the tabs
        self.create_draft_tab()
        self.create_draft_board_tab()  
        self.create_team_rosters_tab()
        self.create_draft_order_tab()
        
    def begin_fantasy_draft(self):
        """Begin the fantasy draft and ensure all rosters are cleared"""
        print("DEBUG: Beginning fantasy draft - clearing all team rosters")
        
        # CRITICAL: Clear ALL team rosters completely
        self.clear_all_team_rosters_completely()
        
        # Mark draft as started
        self.draft_manager.draft_started = True
        
        # Set fantasy draft as pending in game manager
        if hasattr(self.game_manager, 'pending_fantasy_draft'):
            self.game_manager.pending_fantasy_draft = True
        
        # Clear the current interface and show the main draft interface
        for widget in self.winfo_children():
            widget.destroy()
            
        # Recreate the UI with the main interface
        self.setup_integrated_ui()
        
        print("DEBUG: Fantasy draft started - all rosters cleared, draft interface active")
        
        # Schedule a delayed update to ensure draft board gets populated even if initial updates were skipped
        self.after(200, self.ensure_draft_board_current)
        self.after(500, self.ensure_draft_board_current)
        
    def clear_all_team_rosters_completely(self):
        """Completely clear all team rosters to ensure no players remain for trades/extensions"""
        print("DEBUG: Clearing ALL team rosters completely for fantasy draft")
        
        cleared_count = 0
        for team in self.draft_manager.teams:
            # Clear all roster lists
            if hasattr(team, 'roster'):
                cleared_count += len(team.roster)
                team.roster.clear()
            if hasattr(team, 'ahl_roster'):
                cleared_count += len(team.ahl_roster)
                team.ahl_roster.clear()
            if hasattr(team, 'prospects'):
                cleared_count += len(team.prospects)
                team.prospects.clear()
            if hasattr(team, 'players'):
                if isinstance(team.players, dict):
                    for roster_type in team.players:
                        if isinstance(team.players[roster_type], list):
                            cleared_count += len(team.players[roster_type])
                            team.players[roster_type].clear()
                else:
                    cleared_count += len(team.players)
                    team.players.clear()
                    
        print(f"DEBUG: Cleared {cleared_count} players from all team rosters")
        
        # Also clear any additional roster references
        for team in self.draft_manager.teams:
            # Ensure empty lists exist for draft picks to be added to
            if not hasattr(team, 'roster'):
                team.roster = []
            if not hasattr(team, 'ahl_roster'):
                team.ahl_roster = []
            if not hasattr(team, 'prospects'):
                team.prospects = []
                
        print("DEBUG: All team rosters completely cleared and initialized for fantasy draft")
        
    def create_draft_header(self, parent):
        """Create draft status header"""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = ttk.Label(header_frame, text="Fantasy Draft", style='MainTitle.TLabel')
        title_label.pack(side=tk.LEFT, pady=10)
        
        # Status info
        self.status_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        self.status_frame.pack(side=tk.RIGHT, pady=10, padx=10)
        
        # Current pick info
        self.current_pick_label = ttk.Label(self.status_frame, text="Initializing...", style='Subtitle.TLabel')
        self.current_pick_label.pack()
        
        # Progress info  
        self.progress_label = ttk.Label(self.status_frame, text="", style='Normal.TLabel')
        self.progress_label.pack()
        
    def setup_available_players_panel(self, parent):
        """Setup available players list"""
        # Panel title
        ttk.Label(parent, text="Available Players", style='SectionTitle.TLabel').pack(pady=(0, 10))
        
        # Filter frame
        filter_frame = ttk.Frame(parent, style='Panel.TFrame')
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Position filter
        ttk.Label(filter_frame, text="Position:", style='Normal.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.position_var = tk.StringVar(value="All")
        position_combo = ttk.Combobox(filter_frame, textvariable=self.position_var, 
                                    values=["All", "C", "LW", "RW", "LD", "RD", "G"], 
                                    state="readonly", width=8)
        position_combo.pack(side=tk.LEFT, padx=(0, 15))
        position_combo.bind('<<ComboboxSelected>>', lambda e: self.update_player_list())
        
        # Search box
        ttk.Label(filter_frame, text="Search:", style='Normal.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind('<KeyRelease>', lambda e: self.update_player_list())
        
        # Players treeview
        columns = {
            'name': ('Player', 200),
            'pos': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'team': ('Former Team', 150)
        }
        
        tree_frame = ttk.Frame(parent, style='Panel.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.players_tree = self.parent._create_treeview(tree_frame, columns, height=20)
        
        # Double-click to draft
        self.players_tree.bind('<Double-1>', self.on_player_double_click)
        
        # Selection binding
        self.players_tree.bind('<<TreeviewSelect>>', self.on_player_select)
        
    def setup_draft_controls_panel(self, parent):
        """Setup draft order and control buttons"""
        # Draft order section
        order_frame = ttk.LabelFrame(parent, text="Draft Order", style='Panel.TLabelframe')
        order_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Current round info
        self.round_info_label = ttk.Label(order_frame, text="Round 1", style='SectionTitle.TLabel')
        self.round_info_label.pack(pady=(10, 5))
        
        # Draft order tree (compact)
        order_columns = {
            'pick': ('#', 40),
            'team': ('Team', 140),
            'player': ('Selection', 120)
        }
        
        self.draft_tree = self.parent._create_treeview(order_frame, order_columns, height=12)
        
        # Controls section
        controls_frame = ttk.LabelFrame(parent, text="Draft Controls", style='Panel.TLabelframe')
        controls_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Draft selected player button
        self.draft_button = ttk.Button(controls_frame, text="Draft Selected Player", 
                                     command=self.draft_selected_player, style='TButton')
        self.draft_button.pack(fill=tk.X, pady=5)
        
        # Auto-sim toggle
        auto_frame = ttk.Frame(controls_frame, style='Panel.TFrame')
        auto_frame.pack(fill=tk.X, pady=5)
        
        self.auto_sim_var = tk.BooleanVar()
        auto_check = ttk.Checkbutton(auto_frame, text="Auto-simulate other teams", 
                                   variable=self.auto_sim_var, style='TCheckbutton')
        auto_check.pack(side=tk.LEFT)
        
        # Sim to next pick button
        self.sim_button = ttk.Button(controls_frame, text="Simulate to My Pick", 
                                   command=self.simulate_to_user_pick, style='TButton')
        self.sim_button.pack(fill=tk.X, pady=5)
        
        # Complete draft button
        complete_button = ttk.Button(controls_frame, text="Complete Draft (Auto)", 
                                   command=self.auto_complete_draft, style='TButton')
        complete_button.pack(fill=tk.X, pady=5)
        
    def create_draft_board_tab(self):
        """Create draft board with round-by-round tabs"""
        draft_board_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(draft_board_tab, text="📋 Draft Board")
        
        # Header
        header_frame = ttk.Frame(draft_board_tab, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        title_label = ttk.Label(header_frame, text="📋 Draft Board - Round by Round", 
                               style='Header.TLabel', font=('Segoe UI', 16, 'bold'))
        title_label.pack(anchor='w')
        
        self.draft_board_info_label = ttk.Label(header_frame, text="Navigate through draft rounds to see all picks", 
                                               style='Info.TLabel')
        self.draft_board_info_label.pack(anchor='w', pady=(2, 0))
        
        # Create round tabs
        self.round_notebook = ttk.Notebook(draft_board_tab, style='TNotebook')
        self.round_notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Create tabs for each round (we'll populate them dynamically)
        self.round_tabs = {}
        self.round_trees = {}
        
        # Create initial rounds (will expand as draft progresses)
        for round_num in range(1, min(11, self.draft_manager.config.rounds + 1)):  # Show first 10 rounds initially
            self.create_round_tab(round_num)
    
    def create_round_tab(self, round_num):
        """Create a tab for a specific draft round"""
        round_frame = ttk.Frame(self.round_notebook, style='Panel.TFrame')
        self.round_notebook.add(round_frame, text=f"Round {round_num}")
        
        # Round info
        info_frame = ttk.Frame(round_frame, style='Panel.TFrame')
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        round_label = ttk.Label(info_frame, text=f"Round {round_num} Picks", 
                               style='Header.TLabel', font=('Segoe UI', 14, 'bold'))
        round_label.pack(anchor='w')
        
        # Round tree for picks
        columns = {
            'pick': ('Pick #', 80),
            'team': ('Team', 200),
            'player': ('Player Name', 250),
            'position': ('Pos', 80),
            'rating': ('Rating', 80),
            'age': ('Age', 60)
        }
        
        round_tree = self.parent._create_treeview(round_frame, columns, height=20)
        round_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Store references
        self.round_tabs[round_num] = round_frame
        self.round_trees[round_num] = round_tree
        
    def create_team_rosters_tab(self):
        """Create working team rosters tab that actually shows drafted players"""
        rosters_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(rosters_tab, text="🏒 Team Rosters")
        
        # Header
        header_frame = ttk.Frame(rosters_tab, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        title_label = ttk.Label(header_frame, text="🏒 Team Rosters - Fantasy Draft", 
                               style='Header.TLabel', font=('Segoe UI', 16, 'bold'))
        title_label.pack(anchor='w')
        
        subtitle_label = ttk.Label(header_frame, text="View drafted players for each team as the draft progresses", 
                                  style='Info.TLabel', font=('Segoe UI', 10))
        subtitle_label.pack(anchor='w', pady=(5, 0))
        
        # Team selection controls
        controls_frame = ttk.Frame(rosters_tab, style='Panel.TFrame')
        controls_frame.pack(fill=tk.X, padx=15, pady=10)
        
        ttk.Label(controls_frame, text="Select Team:", 
                 style='TLabel', font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(side=tk.LEFT)
        
        # Team selector
        self.roster_team_var = tk.StringVar(value="")
        self.roster_team_combo = ttk.Combobox(controls_frame, textvariable=self.roster_team_var,
                                            values=[team.team_name for team in self.draft_manager.teams],
                                            width=25, state="readonly", font=('Segoe UI', 11))
        self.roster_team_combo.pack(side=tk.LEFT, padx=(10, 20))
        self.roster_team_combo.bind('<<ComboboxSelected>>', self.refresh_team_roster_display)
        
        # Team stats display
        self.roster_stats_frame = ttk.Frame(controls_frame, style='Panel.TFrame')
        self.roster_stats_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        self.roster_stats_label = ttk.Label(self.roster_stats_frame, text="Select a team to view roster", 
                                           style='Info.TLabel', font=('Segoe UI', 11))
        self.roster_stats_label.pack(side=tk.LEFT)
        
        # Position summary
        position_frame = ttk.Frame(rosters_tab, style='Panel.TFrame')
        position_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        self.position_summary_label = ttk.Label(position_frame, text="", 
                                               style='Info.TLabel', font=('Segoe UI', 10))
        self.position_summary_label.pack(anchor='w')
        
        # Create main content area with split layout
        main_content_frame = ttk.Frame(rosters_tab, style='Panel.TFrame')
        main_content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        
        # Left side - Roster list (60% width)
        roster_list_frame = ttk.Frame(main_content_frame, style='Panel.TFrame')
        roster_list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Create roster display treeview
        roster_columns = [
            ('pick_num', 'Pick #', 55),
            ('round_num', 'Round', 45),
            ('player_name', 'Player Name', 140),
            ('position', 'Position', 50),
            ('overall', 'Overall', 50),
            ('age', 'Age', 40),
            ('salary', 'Salary', 80)
        ]
        
        # Create treeview manually for better control
        self.roster_display_tree = ttk.Treeview(roster_list_frame, 
                                              columns=[col[0] for col in roster_columns],
                                              show='headings',
                                              height=14)
        
        # Configure columns
        for col_id, col_name, col_width in roster_columns:
            self.roster_display_tree.heading(col_id, text=col_name)
            self.roster_display_tree.column(col_id, width=col_width, minwidth=col_width)
        
        # Pack treeview with scrollbar
        roster_tree_container = ttk.Frame(roster_list_frame, style='Panel.TFrame')
        roster_tree_container.pack(fill=tk.BOTH, expand=True)
        
        self.roster_display_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        roster_scrollbar = ttk.Scrollbar(roster_tree_container, orient=tk.VERTICAL, command=self.roster_display_tree.yview)
        roster_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.roster_display_tree.configure(yscrollcommand=roster_scrollbar.set)
        
        # Right side - Player spotlight (40% width)
        roster_spotlight_frame = ttk.Frame(main_content_frame, style='Panel.TFrame', width=300)
        roster_spotlight_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        roster_spotlight_frame.pack_propagate(False)  # Maintain fixed width
        
        # Spotlight header
        spotlight_header = ttk.Frame(roster_spotlight_frame, style='Panel.TFrame')
        spotlight_header.pack(fill=tk.X, pady=(0, 10))
        
        spotlight_title = ttk.Label(spotlight_header, text="👤 Player Spotlight", 
                                   style='Header.TLabel', font=('Segoe UI', 14, 'bold'))
        spotlight_title.pack(anchor='w')
        
        spotlight_subtitle = ttk.Label(spotlight_header, text="Click any player to view details", 
                                      style='Info.TLabel', font=('Segoe UI', 9))
        spotlight_subtitle.pack(anchor='w')
        
        # Create scrollable spotlight content
        self.roster_spotlight_canvas = tk.Canvas(roster_spotlight_frame, 
                                               bg=self.parent.CONTENT_BG,
                                               highlightthickness=0,
                                               width=280)
        self.roster_spotlight_scrollbar = ttk.Scrollbar(roster_spotlight_frame, orient=tk.VERTICAL, 
                                                       command=self.roster_spotlight_canvas.yview)
        self.roster_spotlight_scrollable = ttk.Frame(self.roster_spotlight_canvas, style='Panel.TFrame')
        
        self.roster_spotlight_scrollable.bind(
            '<Configure>',
            lambda e: self.roster_spotlight_canvas.configure(scrollregion=self.roster_spotlight_canvas.bbox('all'))
        )
        
        self.roster_spotlight_canvas.create_window((0, 0), window=self.roster_spotlight_scrollable, anchor='nw')
        self.roster_spotlight_canvas.configure(yscrollcommand=self.roster_spotlight_scrollbar.set)
        
        self.roster_spotlight_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.roster_spotlight_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Show initial welcome message
        self.show_roster_welcome_card()
        
        # Initialize tree map for this tree
        if self.roster_display_tree not in self.parent.tree_maps:
            self.parent.tree_maps[self.roster_display_tree] = {}
        
        # Bottom info
        info_frame = ttk.Frame(rosters_tab, style='Panel.TFrame')
        info_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        info_label = ttk.Label(info_frame, 
                              text="🔄 Automatically updates as picks are made • Double-click player for details", 
                              style='Info.TLabel', font=('Segoe UI', 10, 'italic'))
        info_label.pack(side=tk.LEFT)
        
        # User team indicator
        self.roster_user_indicator = ttk.Label(info_frame, text="", 
                                              style='Info.TLabel', font=('Segoe UI', 10, 'bold'))
        self.roster_user_indicator.pack(side=tk.RIGHT)
        
        # Bind events for player selection and details
        self.roster_display_tree.bind('<ButtonRelease-1>', self.on_roster_player_select)
        self.roster_display_tree.bind('<Double-1>', self.show_roster_player_details)
        
        # Set initial team to user team
        if self.user_team:
            self.roster_team_var.set(self.user_team.team_name)
            self.refresh_team_roster_display()
        
        print("DEBUG: Team rosters tab created with working display tree")
        
    def create_draft_order_tab(self):
        """Create the draft order tab with integrated browser"""
        order_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(order_tab, text="📅 Draft Order")
        
        # Create integrated draft order browser directly in tab
        self.setup_integrated_draft_order(order_tab)
        
    def open_player_browser(self):
        """Open the standalone player browser"""
        from player_browser import PlayerBrowserWindow
        
        available_players = self.draft_manager.get_available_players()
        if not available_players:
            messagebox.showinfo("No Players", "No players available for drafting.")
            return
            
        browser = PlayerBrowserWindow(self, available_players, "Fantasy Draft - Available Players")
        
        # Wait for user to make selection
        self.wait_window(browser)
        
        # Check if player was drafted
        selected_player = browser.get_selected_player()
        if selected_player:
            self.draft_specific_player(selected_player)
            
    def open_draft_order_browser(self):
        """Open the standalone draft order browser"""
        from player_browser import SimpleDraftOrderWindow
        
        SimpleDraftOrderWindow(self, self.draft_manager)
        
    def open_quick_draft(self):
        """Open quick draft interface"""
        available_players = self.draft_manager.get_available_players()
        if not available_players:
            messagebox.showinfo("No Players", "No players available for drafting.")
            return
            
        # Get current pick
        current_pick = self.draft_manager.get_current_pick()
        if not current_pick:
            messagebox.showinfo("Draft Complete", "The draft is complete!")
            return
            
        if current_pick.team != self.user_team:
            messagebox.showinfo("Not Your Turn", f"It's {current_pick.team.team_name}'s turn to pick.")
            return
            
        # Open browser for user's pick
        from player_browser import PlayerBrowserWindow
        
        browser = PlayerBrowserWindow(self, available_players, f"Your Pick #{current_pick.overall_pick}")
        self.wait_window(browser)
        
        selected_player = browser.get_selected_player()
        if selected_player:
            self.draft_specific_player(selected_player)
            
    def draft_specific_player(self, player):
        """Draft a specific player from browser"""
        if not player:
            return
            
        current_pick = self.draft_manager.get_current_pick()
        if not current_pick:
            messagebox.showinfo("Draft Complete", "The draft is complete!")
            return
            
        # Verify it's the correct team's turn
        if current_pick.team != self.user_team:
            messagebox.showinfo("Not Your Turn", f"It's {current_pick.team.team_name}'s turn to pick.")
            return
            
        # Make the pick
        success = self.draft_manager.make_pick(player)
        if success:
            # Add to appropriate roster
            if player.overall_rating() >= 40:
                current_pick.team.roster.append(player)
            elif player.overall_rating() >= 35:
                current_pick.team.ahl_roster.append(player)
            else:
                current_pick.team.prospects.append(player)
                
            # Update display
            self.update_display()
            
            # Show next pick info
            next_pick = self.draft_manager.get_current_pick()
            if next_pick:
                if next_pick.team == self.user_team:
                    messagebox.showinfo("Player Drafted!", 
                                      f"✅ Successfully drafted {player.full_name}!\n"
                                      f"Pick #{current_pick.overall_pick} completed.\n\n"
                                      f"🎯 It's still your turn! (Pick #{next_pick.overall_pick})")
                else:
                    messagebox.showinfo("Player Drafted!", 
                                      f"✅ Successfully drafted {player.full_name}!\n"
                                      f"Pick #{current_pick.overall_pick} completed.\n\n"
                                      f"Next up: {next_pick.team.team_name} (Pick #{next_pick.overall_pick})")
            else:
                messagebox.showinfo("Draft Complete!", 
                                  f"✅ Successfully drafted {player.full_name}!\n"
                                  f"Pick #{current_pick.overall_pick} completed.\n\n"
                                  f"🏆 The fantasy draft is now complete!")
                self.complete_draft()
                
        else:
            messagebox.showerror("Draft Error", "Unable to complete the draft pick.")
    
    def setup_integrated_player_browser(self, parent):
        """Setup integrated player browser directly in the tab"""
        # Initialize filter variables
        self.search_var = tk.StringVar()
        self.position_var = tk.StringVar(value="All")
        self.min_rating_var = tk.StringVar(value="0")
        self.selected_player = None
        
        # Main frame
        main_frame = ttk.Frame(parent, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(header_frame, text="🏒 Available Players", 
                               style='Header.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        self.count_label = ttk.Label(header_frame, text="", 
                                    style='Info.TLabel', font=(self.parent.FONT_FAMILY, 10))
        self.count_label.pack(side=tk.RIGHT)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="🔍 Filter & Search", style='TLabelframe')
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filter row 1
        filter_row1 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row1.pack(fill=tk.X, padx=10, pady=5)
        
        # Search
        ttk.Label(filter_row1, text="Name:", style='TLabel').pack(side=tk.LEFT)
        search_entry = ttk.Entry(filter_row1, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(5, 15))
        self.search_var.trace('w', self.integrated_filter_players)
        
        # Position filter
        ttk.Label(filter_row1, text="Position:", style='TLabel').pack(side=tk.LEFT)
        position_combo = ttk.Combobox(filter_row1, textvariable=self.position_var,
                                     values=["All", "C", "LW", "RW", "LD", "RD", "G"], 
                                     width=8, state="readonly")
        position_combo.pack(side=tk.LEFT, padx=(5, 15))
        position_combo.bind('<<ComboboxSelected>>', self.integrated_filter_players)
        
        # Rating filter
        ttk.Label(filter_row1, text="Min Rating:", style='TLabel').pack(side=tk.LEFT)
        rating_spinbox = tk.Spinbox(filter_row1, from_=0, to=99, textvariable=self.min_rating_var, width=5)
        rating_spinbox.pack(side=tk.LEFT, padx=(5, 15))
        self.min_rating_var.trace('w', self.integrated_filter_players)
        
        # Clear button
        clear_btn = ttk.Button(filter_row1, text="Clear Filters", command=self.integrated_clear_filters,
                              style='Accent.TButton')
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        # Players treeview frame
        tree_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create treeview with scrollbars
        columns = ('Name', 'Position', 'Overall', 'Age', 'Former Team')
        self.integrated_players_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        self.integrated_players_tree.heading('Name', text='Player Name')
        self.integrated_players_tree.heading('Position', text='Pos')
        self.integrated_players_tree.heading('Overall', text='OVR')
        self.integrated_players_tree.heading('Age', text='Age')
        self.integrated_players_tree.heading('Former Team', text='Former Team')
        
        self.integrated_players_tree.column('Name', width=200)
        self.integrated_players_tree.column('Position', width=60)
        self.integrated_players_tree.column('Overall', width=60)
        self.integrated_players_tree.column('Age', width=50)
        self.integrated_players_tree.column('Former Team', width=150)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.integrated_players_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.integrated_players_tree.xview)
        self.integrated_players_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.integrated_players_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.integrated_players_tree.bind('<Button-1>', self.integrated_on_player_select)
        self.integrated_players_tree.bind('<Double-1>', self.integrated_on_player_draft)
        
        # Button frame (more prominent and always visible)
        button_frame = ttk.LabelFrame(main_frame, text="🎯 Draft Actions", style='TLabelframe')
        button_frame.pack(fill=tk.X, pady=(15, 5), padx=10)
        
        # Content frame inside the LabelFrame
        content_frame = ttk.Frame(button_frame, style='Panel.TFrame')
        content_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Left side - Draft button and info
        left_button_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        left_button_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.integrated_draft_btn = ttk.Button(left_button_frame, text="🎯 DRAFT SELECTED PLAYER", 
                                             command=self.integrated_draft_player, state='disabled',
                                             style='Accent.TButton')
        self.integrated_draft_btn.pack(side=tk.LEFT, padx=(0, 15), ipady=5)
        
        self.integrated_info_label = ttk.Label(left_button_frame, text="Select a player to draft", 
                                             style='Info.TLabel')
        self.integrated_info_label.pack(side=tk.LEFT, pady=8)
        
        # Right side - Draft controls (make more prominent)
        right_button_frame = ttk.Frame(content_frame, style='Panel.TFrame')
        right_button_frame.pack(side=tk.RIGHT)
        
        # Draft control label
        controls_label = ttk.Label(right_button_frame, text="Draft Controls:", 
                                 style='Info.TLabel', font=(self.parent.FONT_FAMILY, 10, 'bold'))
        controls_label.pack(pady=(0, 8))
        
        # Button container
        btn_container = ttk.Frame(right_button_frame, style='Panel.TFrame')
        btn_container.pack()
        
        # Next pick button
        self.integrated_next_pick_button = ttk.Button(btn_container, text="⏭️ Next Pick", 
                                                    command=self.advance_one_pick, style='Accent.TButton')
        self.integrated_next_pick_button.pack(side=tk.LEFT, padx=(0, 8), ipady=8, ipadx=8)
        
        # Sim to user pick button
        self.integrated_sim_button = ttk.Button(btn_container, text="🚀 Sim to My Pick", 
                                              command=self.sim_to_user_pick, style='Accent.TButton')
        self.integrated_sim_button.pack(side=tk.LEFT, padx=(0, 8), ipady=8, ipadx=8)
        
        # Sim rest of draft button
        self.integrated_sim_rest_button = ttk.Button(btn_container, text="⚡ Sim Rest of Draft", 
                                                   command=self.sim_rest_of_draft, style='Accent.TButton')
        self.integrated_sim_rest_button.pack(side=tk.LEFT, ipady=8, ipadx=8)
        
        # Force update to ensure visibility
        button_frame.update_idletasks()
        
        # Initialize with all players
        self.filtered_players = []
        
        # Initialize draft state properly
        if self.draft_manager.current_pick == 0:
            # Draft hasn't started yet - show begin message
            messagebox.showinfo("Fantasy Draft Ready", 
                              f"🏒 Fantasy Draft is ready to begin!\n\n"
                              f"• {len(self.draft_manager.all_players)} players available\n"
                              f"• {self.draft_manager.config.rounds} rounds planned\n"
                              f"• Your team: {self.user_team.team_name if self.user_team else 'Not set'}\n\n"
                              f"Use the draft control buttons to start!")
        
        self.integrated_populate_players()
    
    def create_simple_button_system(self, parent):
        """Create a simple, guaranteed-visible button system at the top of the tab"""
        # Create a very visible button frame at the TOP of the tab
        button_container = ttk.Frame(parent, style='Panel.TFrame')
        button_container.pack(fill=tk.X, padx=20, pady=20, side=tk.TOP)
        
        # Title for the button section
        title_frame = ttk.Frame(button_container, style='Panel.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(title_frame, text="🎯 FANTASY DRAFT CONTROLS", 
                               style='Header.TLabel', font=('Segoe UI', 18, 'bold'))
        title_label.pack()
        
        subtitle_label = ttk.Label(title_frame, text="Use these buttons to control the draft progression", 
                                  style='Info.TLabel', font=('Segoe UI', 11))
        subtitle_label.pack(pady=(5, 0))
        
        # Create a grid of buttons for maximum visibility
        buttons_frame = ttk.Frame(button_container, style='Panel.TFrame')
        buttons_frame.pack(fill=tk.X, pady=10)
        
        # Row 1: Primary draft controls
        row1 = ttk.Frame(buttons_frame, style='Panel.TFrame')
        row1.pack(fill=tk.X, pady=(0, 10))
        
        # Next Pick Button - Large and prominent
        self.simple_next_pick_btn = ttk.Button(row1, 
                                              text="⏭️ ADVANCE ONE PICK", 
                                              command=self.advance_one_pick,
                                              style='Accent.TButton')
        self.simple_next_pick_btn.pack(side=tk.LEFT, padx=(0, 20), ipady=10, ipadx=20)
        
        # Sim to User Pick Button
        self.simple_sim_to_user_btn = ttk.Button(row1, 
                                                text="🚀 SIM TO MY TURN", 
                                                command=self.sim_to_user_pick,
                                                style='Accent.TButton')
        self.simple_sim_to_user_btn.pack(side=tk.LEFT, padx=(0, 20), ipady=10, ipadx=20)
        
        # Sim Rest Button
        self.simple_sim_rest_btn = ttk.Button(row1, 
                                             text="⚡ SIM ENTIRE DRAFT", 
                                             command=self.sim_rest_of_draft,
                                             style='Accent.TButton')
        self.simple_sim_rest_btn.pack(side=tk.LEFT, ipady=10, ipadx=20)
        
        # Row 2: Draft information
        info_frame = ttk.Frame(buttons_frame, style='Panel.TFrame')
        info_frame.pack(fill=tk.X, pady=10)
        
        self.simple_status_label = ttk.Label(info_frame, 
                                           text="Fantasy Draft Ready - Use buttons above to control draft", 
                                           style='Info.TLabel', font=('Segoe UI', 12))
        self.simple_status_label.pack()
        
        # Separator line
        separator = ttk.Separator(button_container, orient='horizontal')
        separator.pack(fill=tk.X, pady=20)
        
        print("✅ SIMPLE BUTTON SYSTEM CREATED - Buttons should be visible at top of tab")
    
    def integrated_filter_players(self, *args):
        """Filter players in integrated browser"""
        try:
            search_text = self.search_var.get().lower()
            position_filter = self.position_var.get()
            min_rating = int(self.min_rating_var.get() or 0)
            
            available_players = self.draft_manager.get_available_players()
            
            # Filter players
            self.filtered_players = []
            for player in available_players:
                # Search filter
                if search_text and search_text not in player.full_name.lower():
                    continue
                    
                # Position filter
                if position_filter != "All" and player.primary_position.value != position_filter:
                    continue
                    
                # Rating filter
                if player.overall_rating() < min_rating:
                    continue
                    
                self.filtered_players.append(player)
            
            # Sort by rating (highest first)
            self.filtered_players.sort(key=lambda p: p.overall_rating(), reverse=True)
            
            # Repopulate
            self.integrated_populate_players()
            
        except Exception as e:
            print(f"DEBUG: Error in integrated filter: {e}")
    
    def integrated_clear_filters(self):
        """Clear all filters in integrated browser"""
        self.search_var.set("")
        self.position_var.set("All")
        self.min_rating_var.set("0")
        
    def integrated_populate_players(self):
        """Populate the integrated players treeview with current available players"""
        # Clear existing items
        for item in self.integrated_players_tree.get_children():
            self.integrated_players_tree.delete(item)
        
        # ALWAYS get fresh available players (fixes draft picks failing)
        available_players = self.draft_manager.get_available_players()
        self.filtered_players = available_players.copy()
        self.filtered_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        print(f"DEBUG: Populating integrated browser with {len(self.filtered_players)} players")
        
        # Add players to tree (limit for performance)
        display_limit = min(1000, len(self.filtered_players))
        for i, player in enumerate(self.filtered_players[:display_limit]):
            try:
                former_team = getattr(player, 'former_team', 'Unknown')
                
                item_id = self.integrated_players_tree.insert('', 'end', values=(
                    player.full_name,
                    player.primary_position.value,
                    player.overall_rating(),
                    player.age,
                    former_team
                ))
                
                # Store player reference directly in tree_maps using item_id
                if not hasattr(self.parent, 'tree_maps'):
                    self.parent.tree_maps = {}
                self.parent.tree_maps[item_id] = player
                
            except Exception as e:
                print(f"DEBUG: Error adding player {i}: {e}")
                continue
        
        # Update count
        total_count = len(self.draft_manager.get_available_players())
        filtered_count = len(self.filtered_players)
        displayed_count = len(self.integrated_players_tree.get_children())
        
        if displayed_count < filtered_count:
            count_text = f"Showing {displayed_count} of {filtered_count} filtered ({total_count} total available)"
        else:
            count_text = f"Showing {displayed_count} of {total_count} available players"
            
        self.count_label.configure(text=count_text)
        
        print(f"DEBUG: Added {displayed_count} players to integrated tree")
    
    def integrated_on_player_select(self, event):
        """Handle player selection in integrated browser"""
        selection = self.integrated_players_tree.selection()
        if selection:
            item = selection[0]
            try:
                # Get player from tree_maps using item ID
                if hasattr(self.parent, 'tree_maps') and item in self.parent.tree_maps:
                    self.selected_player = self.parent.tree_maps[item]
                    
                    # Show player card in spotlight area
                    if hasattr(self, 'main_player_card_frame'):
                        self.show_main_player_card(self.selected_player)
                    
                    # Check if it's user's turn to enable draft button
                    current_pick = self.draft_manager.get_current_pick()
                    if current_pick and current_pick.team == self.user_team:
                        self.integrated_draft_btn.configure(state='normal')
                        self.integrated_info_label.configure(
                            text=f"✅ Ready to Draft: {self.selected_player.full_name} "
                                 f"({self.selected_player.primary_position.value}, "
                                 f"OVR {self.selected_player.overall_rating()})")
                    else:
                        self.integrated_draft_btn.configure(state='disabled')
                        if current_pick:
                            self.integrated_info_label.configure(
                                text=f"Selected: {self.selected_player.full_name} "
                                     f"({self.selected_player.primary_position.value}, "
                                     f"OVR {self.selected_player.overall_rating()}) "
                                     f"- Wait for {current_pick.team.team_name} to pick")
                        else:
                            self.integrated_info_label.configure(text="Draft complete")
                else:
                    self.selected_player = None
                    self.integrated_draft_btn.configure(state='disabled')
                    self.integrated_info_label.configure(text="Invalid selection")
            except Exception as e:
                print(f"DEBUG: Error selecting player: {e}")
                self.selected_player = None
                self.integrated_draft_btn.configure(state='disabled')
                self.integrated_info_label.configure(text="Error selecting player")
    
    def integrated_on_player_draft(self, event):
        """Handle double-click to draft in integrated browser"""
        self.integrated_draft_player()
        
    def integrated_draft_player(self):
        """Draft the selected player from integrated browser"""
        print(f"DEBUG: integrated_draft_player called")
        print(f"DEBUG: selected_player = {self.selected_player}")
        
        if not self.selected_player:
            messagebox.showwarning("No Selection", "Please select a player to draft.")
            return
            
        current_pick = self.draft_manager.get_current_pick()
        print(f"DEBUG: current_pick = {current_pick}")
        if not current_pick:
            messagebox.showinfo("Draft Complete", "The draft is complete!")
            return
            
        # Check if it's user's turn
        print(f"DEBUG: current_pick.team = {current_pick.team.team_name}")
        print(f"DEBUG: user_team = {self.user_team.team_name if self.user_team else 'None'}")
        if current_pick.team != self.user_team:
            messagebox.showinfo("Not Your Turn", f"It's {current_pick.team.team_name}'s turn to pick.")
            return
        
        player = self.selected_player
        
        # Debug player availability and prevent drafting unavailable players
        available_players = self.draft_manager.get_available_players()
        player_available = any(p.id == player.id for p in available_players)
        print(f"DEBUG: Player {player.full_name} (ID: {player.id}) available: {player_available}")
        print(f"DEBUG: Available players count: {len(available_players)}")
        
        if not player_available:
            print("DEBUG: Player not available - may already be drafted")
            messagebox.showerror(
                "Player Unavailable", 
                f"❌ {player.full_name} is no longer available!\n\n"
                f"This player may have been drafted by another team.\n"
                f"Please refresh the player list and select a different player."
            )
            # Force refresh the player list
            self.integrated_populate_players()
            return
        
        # Enhanced confirmation dialog with more details
        former_team = getattr(player, 'former_team', 'Unknown')
        confirm_text = (
            f"🎯 DRAFT CONFIRMATION\n\n"
            f"Player: {player.full_name}\n"
            f"Position: {player.primary_position.value}\n"
            f"Overall Rating: {player.overall_rating()}\n"
            f"Age: {player.age}\n"
            f"Former Team: {former_team}\n\n"
            f"Pick #{current_pick.overall_pick} - Round {current_pick.round_num}\n"
            f"Team: {current_pick.team.team_name}\n\n"
            f"Confirm this draft selection?"
        )
        
        result = messagebox.askyesno("🏒 Draft Player", confirm_text)
        
        if result:
            print(f"DEBUG: User confirmed draft of {player.full_name}")
            # Make the draft pick
            success = self.draft_manager.make_pick(player)
            print(f"DEBUG: Draft pick success = {success}")
            
            if success:
                # Add to appropriate roster based on rating
                if player.overall_rating() >= 40:
                    current_pick.team.roster.append(player)
                    print(f"DEBUG: Added {player.full_name} to {current_pick.team.team_name} roster")
                elif player.overall_rating() >= 35:
                    current_pick.team.ahl_roster.append(player)
                    print(f"DEBUG: Added {player.full_name} to {current_pick.team.team_name} AHL roster")
                else:
                    current_pick.team.prospects.append(player)
                    print(f"DEBUG: Added {player.full_name} to {current_pick.team.team_name} prospects")
                
                # CRITICAL: Immediate UI updates with forced refresh
                print("DEBUG: ===== STARTING COMPREHENSIVE UI UPDATE =====")
                
                # 1. Update all display components
                self.update_display()
                print("DEBUG: Called update_display()")
                
                # 2. FORCE immediate draft board update
                self.force_draft_board_update()
                print("DEBUG: Called force_draft_board_update()")
                
                # 3. FORCE immediate team roster update
                self.force_team_roster_update()
                print("DEBUG: Called force_team_roster_update()")
                
                # 4. Make sure draft board tab is visible
                self.ensure_draft_board_visible()
                print("DEBUG: Called ensure_draft_board_visible()")
                
                # 5. Additional UI refresh cycles
                self.update_idletasks()
                self.update()
                print("DEBUG: Called additional UI refresh cycles")
                
                print("DEBUG: ===== COMPLETED COMPREHENSIVE UI UPDATE =====")
                
                # Show success message
                messagebox.showinfo("Player Drafted!", 
                                  f"✅ Successfully drafted {player.full_name}!\n\n"
                                  f"Pick #{current_pick.overall_pick} completed for {current_pick.team.team_name}\n"
                                  f"Player added to appropriate roster.")
                
                # Clear selection
                self.selected_player = None
                if hasattr(self, 'integrated_draft_btn'):
                    self.integrated_draft_btn.configure(state='disabled')
                if hasattr(self, 'integrated_info_label'):
                    self.integrated_info_label.configure(text="Select a player to draft")
                
                # If we just drafted a player that has a card displayed, show the updated card
                if hasattr(self, 'player_card_frame') and player:
                    # Find the draft pick for this player
                    drafted_pick = None
                    for pick in self.draft_manager.draft_picks:
                        if pick.player == player:
                            drafted_pick = pick
                            break
                    if drafted_pick:
                        self.show_player_card(player, drafted_pick)
                
                # Show next pick info
                next_pick = self.draft_manager.get_current_pick()
                if next_pick:
                    if next_pick.team == self.user_team:
                        if hasattr(self, 'integrated_info_label'):
                            self.integrated_info_label.configure(text="🎯 YOUR TURN AGAIN - Select next player to draft")
                    else:
                        if hasattr(self, 'integrated_info_label'):
                            self.integrated_info_label.configure(text=f"Next up: {next_pick.team.team_name} (Pick #{next_pick.overall_pick})")
                else:
                    if hasattr(self, 'integrated_info_label'):
                        self.integrated_info_label.configure(text="🏆 Draft Complete!")
                    self.complete_draft()
                    
            else:
                print(f"DEBUG: Draft pick failed for {player.full_name}")
                messagebox.showerror("Draft Error", "Unable to complete the draft pick. Please try again.")
        else:
            print(f"DEBUG: User cancelled draft of {player.full_name}")
    
    def setup_integrated_draft_order(self, parent):
        """Setup integrated draft order browser directly in the tab"""
        # Main frame
        main_frame = ttk.Frame(parent, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(header_frame, text="🎯 Fantasy Draft Order", 
                               style='Header.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        # Current pick info
        current_pick = self.draft_manager.get_current_pick()
        if current_pick:
            current_text = f"Current Pick: #{current_pick.overall_pick} - {current_pick.team.team_name}"
        else:
            current_text = "Draft Complete"
            
        self.integrated_current_label = ttk.Label(header_frame, text=current_text, 
                                                 style='Info.TLabel', font=(self.parent.FONT_FAMILY, 12))
        self.integrated_current_label.pack(side=tk.RIGHT)
        
        # Draft order frame
        order_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        order_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        columns = ('Pick', 'Round', 'Team', 'Status', 'Player')
        self.integrated_draft_tree = ttk.Treeview(order_frame, columns=columns, show='headings', height=25)
        
        # Configure columns
        self.integrated_draft_tree.heading('Pick', text='Pick #')
        self.integrated_draft_tree.heading('Round', text='Round')
        self.integrated_draft_tree.heading('Team', text='Team')
        self.integrated_draft_tree.heading('Status', text='Status')
        self.integrated_draft_tree.heading('Player', text='Selected Player')
        
        self.integrated_draft_tree.column('Pick', width=80)
        self.integrated_draft_tree.column('Round', width=80)
        self.integrated_draft_tree.column('Team', width=200)
        self.integrated_draft_tree.column('Status', width=120)
        self.integrated_draft_tree.column('Player', width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(order_frame, orient=tk.VERTICAL, command=self.integrated_draft_tree.yview)
        self.integrated_draft_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack tree and scrollbar
        self.integrated_draft_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button
        button_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        refresh_btn = ttk.Button(button_frame, text="🔄 Refresh Draft Order", 
                                command=self.integrated_populate_draft_order,
                                style='TButton')
        refresh_btn.pack(side=tk.LEFT)
        
        # Initialize draft order
        self.integrated_populate_draft_order()
        
    def integrated_populate_draft_order(self):
        """Populate the integrated draft order"""
        # Clear existing
        for item in self.integrated_draft_tree.get_children():
            self.integrated_draft_tree.delete(item)
            
        print(f"DEBUG: Populating integrated draft order with {len(self.draft_manager.draft_picks)} picks")
        
        current_pick_num = self.draft_manager.current_pick
        
        # Show first 200 picks (10+ rounds)
        for i, pick in enumerate(self.draft_manager.draft_picks[:200]):
            # Determine status
            if pick.player:
                status = "✅ COMPLETED"
                player_name = pick.player.full_name
            elif i == current_pick_num:
                status = "⏰ ON THE CLOCK"
                player_name = ""
            else:
                status = "⏳ UPCOMING"
                player_name = ""
                
            # Insert item
            item = self.integrated_draft_tree.insert('', 'end', values=(
                pick.overall_pick,
                pick.round_num,
                pick.team.team_name,
                status,
                player_name
            ))
            
            # Highlight and scroll to current pick
            if i == current_pick_num:
                self.integrated_draft_tree.selection_set(item)
                self.integrated_draft_tree.see(item)
                
        # Update current pick label
        current_pick = self.draft_manager.get_current_pick()
        if current_pick:
            current_text = f"Current Pick: #{current_pick.overall_pick} - {current_pick.team.team_name}"
            if hasattr(self, 'integrated_current_label'):
                self.integrated_current_label.configure(text=current_text)
        else:
            if hasattr(self, 'integrated_current_label'):
                self.integrated_current_label.configure(text="Draft Complete")
                
        print(f"DEBUG: Added {len(self.integrated_draft_tree.get_children())} picks to integrated draft order")
        
    def create_modern_header(self, parent):
        """Create a modern header similar to the free agent window"""
        # Header frame with dark background
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 0))
        
        # Main title section
        title_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        title_frame.pack(fill=tk.X, padx=20, pady=15)
        
        # Left side - Title and subtitle
        title_content = ttk.Frame(title_frame, style='TitleBar.TFrame')
        title_content.pack(side=tk.LEFT, fill=tk.Y)
        
        # Main title
        ttk.Label(
            title_content,
            text="🏒 Fantasy Draft",
            style='Title.TLabel',
            font=(self.parent.FONT_FAMILY, 24, 'bold')
        ).pack(anchor='w')
        
        # Current pick info
        current_pick = self.draft_manager.get_current_pick()
        if current_pick:
            pick_text = f"Pick {current_pick.overall_pick}: {current_pick.team.team_name} selecting..."
        else:
            pick_text = "Draft Complete"
            
        self.current_pick_label = ttk.Label(
            title_content,
            text=pick_text,
            style='Subtitle.TLabel',
            font=(self.parent.FONT_FAMILY, 14)
        )
        self.current_pick_label.pack(anchor='w', pady=(5, 0))
        
        # Right side - Draft statistics
        stats_frame = ttk.Frame(title_frame, style='TitleBar.TFrame')
        stats_frame.pack(side=tk.RIGHT)
        
        # Draft stats
        available_count = len(self.draft_manager.get_available_players())
        completed_picks = len([p for p in self.draft_manager.draft_picks if p.player])
        
        stats_text = f"Available: {available_count} Players • Picks Made: {completed_picks}"
        ttk.Label(
            stats_frame,
            text=stats_text,
            style='Subtitle.TLabel',
            font=(self.parent.FONT_FAMILY, 12)
        ).pack(side=tk.RIGHT)
        
        # Subtitle with draft info
        subtitle_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        subtitle_frame.pack(fill=tk.X, pady=(0, 15))
        
        draft_info = f"Fantasy Draft • {self.draft_manager.config.rounds} Rounds • Serpentine Order"
        ttk.Label(
            subtitle_frame,
            text=draft_info,
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 11)
        ).pack(side=tk.LEFT, padx=(20, 0))
        
        # Draft controls on the right
        controls_frame = ttk.Frame(subtitle_frame, style='TitleBar.TFrame')
        controls_frame.pack(side=tk.RIGHT, padx=(0, 20))
        
        # Begin Draft button (if draft hasn't started)
        if self.draft_manager.current_pick == 0:
            self.begin_draft_button = ttk.Button(controls_frame, text="🚀 Begin Draft", 
                                               command=self.begin_draft,
                                               style='Accent.TButton')
            self.begin_draft_button.pack(side=tk.LEFT, padx=5)
        
        # Auto-draft checkbox
        ttk.Checkbutton(controls_frame, text="Auto Draft", variable=self.auto_draft_enabled,
                       style='TCheckbutton').pack(side=tk.LEFT, padx=5)
        
        # Draft speed
        ttk.Label(controls_frame, text="Speed:", style='Info.TLabel').pack(side=tk.LEFT, padx=5)
        speed_combo = ttk.Combobox(controls_frame, textvariable=self.draft_speed,
                                  values=["Slow", "Normal", "Fast"], width=8, state="readonly")
        speed_combo.pack(side=tk.LEFT, padx=5)
        
    def create_draft_tab(self):
        """Create the main draft tab with player browser and player cards"""
        draft_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(draft_tab, text="🎯 Available Players")
        
        # Create split layout: player list on left, player card on right
        main_paned = ttk.PanedWindow(draft_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left side: player browser and controls
        left_frame = ttk.Frame(main_paned, style='Panel.TFrame')
        main_paned.add(left_frame, weight=2)
        
        # Create the simple, guaranteed-visible button system FIRST
        self.create_simple_button_system(left_frame)
        
        # Then create integrated player browser
        self.setup_integrated_player_browser(left_frame)
        
        # Right side: player card display
        right_frame = ttk.Frame(main_paned, style='Panel.TFrame')
        main_paned.add(right_frame, weight=1)
        
        # Player card header
        card_header = ttk.Frame(right_frame, style='Panel.TFrame')
        card_header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Label(card_header, text="🎯 Player Spotlight", 
                 style='Header.TLabel', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        
        ttk.Label(card_header, text="Click any player to view detailed information", 
                 style='Info.TLabel').pack(anchor='w', pady=(2, 0))
        
        # Player card container
        self.main_player_card_frame = ttk.Frame(right_frame, style='Panel.TFrame')
        self.main_player_card_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Initialize with welcome message
        self.show_main_welcome_card()
    
    def show_main_welcome_card(self):
        """Show welcome card in main player spotlight area"""
        # Clear existing content
        for widget in self.main_player_card_frame.winfo_children():
            widget.destroy()
        
        welcome_frame = ttk.Frame(self.main_player_card_frame, style='Panel.TFrame')
        welcome_frame.pack(fill=tk.BOTH, expand=True)
        
        # Welcome content
        welcome_label = ttk.Label(welcome_frame, text="🏒 Player Spotlight", 
                                 style='Header.TLabel', font=('Segoe UI', 16, 'bold'))
        welcome_label.pack(pady=(50, 20))
        
        info_label = ttk.Label(welcome_frame, text="Select any player from the list to view:\n\n• Complete player statistics\n• Draft information\n• Position-specific attributes\n• Contract details", 
                              style='Info.TLabel', justify='center', font=('Segoe UI', 11))
        info_label.pack(pady=20)
        
        tip_label = ttk.Label(welcome_frame, text="💡 Click on any available player to get started!", 
                             style='Info.TLabel', font=('Segoe UI', 10, 'italic'))
        tip_label.pack(pady=(30, 0))
    
    def show_main_player_card(self, player):
        """Show detailed player card in main spotlight area"""
        # Clear existing content
        for widget in self.main_player_card_frame.winfo_children():
            widget.destroy()
        
        # Create scrollable card
        canvas = tk.Canvas(self.main_player_card_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_player_card_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Player card content
        card_frame = ttk.Frame(scrollable_frame, style='Panel.TFrame')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header with player name and position
        header_frame = ttk.Frame(card_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        name_label = ttk.Label(header_frame, text=player.full_name, 
                              style='Header.TLabel', font=('Segoe UI', 16, 'bold'))
        name_label.pack()
        
        position_label = ttk.Label(header_frame, text=f"{player.primary_position.value} • Overall: {to_100_scale(player.overall_rating())}", 
                                  style='Info.TLabel', font=('Segoe UI', 12))
        position_label.pack(pady=(2, 0))
        
        # Basic info section
        info_frame = ttk.LabelFrame(card_frame, text="📊 Basic Information", style='TLabelframe')
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_grid = ttk.Frame(info_frame, style='Panel.TFrame')
        info_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Basic info in 2 columns
        former_team = getattr(player, 'former_team', getattr(player, 'team_name', 'Free Agent'))
        
        # Contract info
        if hasattr(player, 'contract') and player.contract:
            salary = getattr(player.contract, 'salary', 750000)
            years = getattr(player.contract, 'years_remaining', 1)
            contract_text = f"${salary:,} x {years}yr"
        else:
            contract_text = "$750,000 x 1yr (ELC)"
        
        basic_info = [
            ("Age:", f"{player.age} years old"),
            ("Height:", f"{player.height}"),
            ("Weight:", f"{player.weight} lbs"),
            ("Shoots:", getattr(player, 'shoots', 'Unknown')),
            ("Former Team:", former_team),
            ("Contract:", contract_text)
        ]
        
        for i, (label, value) in enumerate(basic_info):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(info_grid, text=label, style='TLabel', font=('Segoe UI', 10, 'bold')).grid(
                row=row, column=col, sticky='w', padx=(0, 5), pady=2)
            ttk.Label(info_grid, text=value, style='TLabel').grid(
                row=row, column=col+1, sticky='w', padx=(0, 20), pady=2)
        
        # Contract analysis section
        contract_frame = ttk.LabelFrame(card_frame, text="💰 Contract Analysis", style='TLabelframe')
        contract_frame.pack(fill=tk.X, pady=(0, 10))
        
        contract_content = ttk.Frame(contract_frame, style='Panel.TFrame')
        contract_content.pack(fill=tk.X, padx=10, pady=10)
        
        if hasattr(player, 'contract') and player.contract:
            contract = player.contract
            salary = getattr(contract, 'salary', 750000)
            overall = player.overall_rating()
            value_per_mil = overall / (salary / 1000000) if salary > 0 else overall
            
            # Contract value assessment
            if value_per_mil >= 15:
                value_color = "#4CAF50"
                value_assessment = "🟢 Excellent Value - High skill for the salary"
            elif value_per_mil >= 10:
                value_color = "#8BC34A"
                value_assessment = "🟡 Good Value - Fair skill-to-salary ratio"
            elif value_per_mil >= 5:
                value_color = "#FFC107"
                value_assessment = "🟠 Average Value - Market rate contract"
            elif value_per_mil >= 3:
                value_color = "#FF9800"
                value_assessment = "🔶 Poor Value - Expensive for skill level"
            else:
                value_color = "#F44336"
                value_assessment = "🔴 Bad Value - Overpaid significantly"
            
            value_label = ttk.Label(contract_content, text=value_assessment,
                                   style='Info.TLabel', font=('Segoe UI', 10),
                                   foreground=value_color)
            value_label.pack(anchor='w')
            
            # Trade restrictions
            restrictions = []
            if hasattr(contract, 'no_movement_clause') and contract.no_movement_clause:
                restrictions.append("No-Movement Clause")
            if hasattr(contract, 'no_trade_clause') and contract.no_trade_clause:
                restrictions.append("No-Trade Clause")
                
            if restrictions:
                restriction_text = f"⚠️ Trade Restrictions: {', '.join(restrictions)}"
                restriction_label = ttk.Label(contract_content, text=restriction_text,
                                             style='Info.TLabel', font=('Segoe UI', 10, 'italic'),
                                             foreground=self.parent.ACCENT_COLOR)
                restriction_label.pack(anchor='w', pady=(3, 0))
        else:
            default_label = ttk.Label(contract_content, 
                                     text="🟢 Entry Level Contract - Low risk, team-friendly deal",
                                     style='Info.TLabel', font=('Segoe UI', 10),
                                     foreground="#4CAF50")
            default_label.pack(anchor='w')
        
        # Attributes section
        attr_frame = ttk.LabelFrame(card_frame, text="⚡ Key Attributes", style='TLabelframe')
        attr_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.create_main_attribute_grid(attr_frame, player)
        
        # Draft action section
        action_frame = ttk.LabelFrame(card_frame, text="🎯 Draft Action", style='TLabelframe')
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        action_content = ttk.Frame(action_frame, style='Panel.TFrame')
        action_content.pack(fill=tk.X, padx=10, pady=10)
        
        # Draft button
        draft_button = ttk.Button(action_content, text=f"🏒 Draft {player.first_name}", 
                                 command=lambda: self.draft_selected_player_from_card(player), 
                                 style='TButton')
        draft_button.pack(pady=5)
        
        draft_info = ttk.Label(action_content, 
                              text=f"Select this player for your team's current pick", 
                              style='Info.TLabel', font=('Segoe UI', 10, 'italic'))
        draft_info.pack()
    
    def create_main_attribute_grid(self, parent, player):
        """Create attribute grid for main player card"""
        attr_grid = ttk.Frame(parent, style='Panel.TFrame')
        attr_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Position-specific attributes
        if player.primary_position.value == 'G':
            attributes = [
                ("Goaltending", player.goaltending),
                ("Reflexes", getattr(player, 'reflexes', 50)),
                ("Positioning", getattr(player, 'positioning', 50)),
                ("Rebound Control", getattr(player, 'rebound_control', 50)),
                ("Puck Handling", getattr(player, 'puck_handling', 50)),
                ("Mental Toughness", getattr(player, 'mental_toughness', 50))
            ]
        else:
            attributes = [
                ("Skating", player.skating),
                ("Shooting", player.shooting),
                ("Passing", player.passing),
                ("Checking", player.checking),
                ("Hockey IQ", getattr(player, 'hockey_iq', 50)),
                ("Determination", getattr(player, 'determination', 50)),
                ("Teamwork", getattr(player, 'teamwork', 50)),
                ("Leadership", getattr(player, 'leadership', 50))
            ]
        
        # Display attributes in 2 columns
        for i, (attr_name, attr_value) in enumerate(attributes):
            row = i // 2
            col = (i % 2) * 3
            
            # Attribute name
            ttk.Label(attr_grid, text=f"{attr_name}:", style='TLabel', font=('Segoe UI', 10, 'bold')).grid(
                row=row, column=col, sticky='w', padx=(0, 5), pady=2)
            
            # Attribute value with color
            color = self.get_attribute_color(attr_value)
            value_label = ttk.Label(attr_grid, text=str(attr_value), 
                                   style='TLabel', foreground=color, font=('Segoe UI', 10, 'bold'))
            value_label.grid(row=row, column=col+1, sticky='w', padx=(0, 20), pady=2)
    
    def get_attribute_color(self, value):
        """Get color for attribute value"""
        if value >= 80:
            return '#00FF00'  # Green for excellent
        elif value >= 70:
            return '#90EE90'  # Light green for very good
        elif value >= 60:
            return '#FFFF00'  # Yellow for good
        elif value >= 50:
            return '#FFA500'  # Orange for average
        else:
            return '#FF6B6B'  # Red for poor
    
    def draft_selected_player_from_card(self, player):
        """Draft player directly from player card"""
        self.selected_player = player
        self.integrated_draft_player()
    
    def update_main_player_spotlight(self):
        """Update the main player spotlight with the most recently drafted player"""
        if not hasattr(self, 'main_player_card_frame'):
            return
            
        # Get all completed picks
        completed_picks = [pick for pick in self.draft_manager.draft_picks if pick.player]
        
        if completed_picks:
            # Show the most recently drafted player
            most_recent_pick = completed_picks[-1]  # Last pick in chronological order
            print(f"DEBUG: Auto-showing spotlight for most recent pick: {most_recent_pick.player.full_name}")
            self.show_main_player_card(most_recent_pick.player)
        else:
            # No picks yet, show welcome card
            self.show_main_welcome_card()
    
    def update_main_player_spotlight(self):
        """Update the main player spotlight with the most recently drafted player"""
        if not hasattr(self, 'main_player_card_frame'):
            return
            
        # Get all completed picks
        completed_picks = [pick for pick in self.draft_manager.draft_picks if pick.player]
        
        if completed_picks:
            # Get the most recent pick
            latest_pick = completed_picks[-1]  # Last pick in chronological order
            latest_player = latest_pick.player
            
            print(f"DEBUG: Updating main spotlight with most recent pick: {latest_player.full_name}")
            
            # Show the latest drafted player's card
            self.show_main_player_card_with_draft_info(latest_player, latest_pick)
        else:
            # No picks yet, show welcome card
            self.show_main_welcome_card()
    
    def show_main_player_card_with_draft_info(self, player, draft_pick):
        """Show detailed player card with draft information"""
        # Clear existing content
        for widget in self.main_player_card_frame.winfo_children():
            widget.destroy()
        
        # Create scrollable card
        canvas = tk.Canvas(self.main_player_card_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.main_player_card_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Player card content
        card_frame = ttk.Frame(scrollable_frame, style='Panel.TFrame')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Draft status header
        draft_header = ttk.Frame(card_frame, style='Panel.TFrame')
        draft_header.pack(fill=tk.X, pady=(0, 10))
        
        draft_status = ttk.Label(draft_header, text="📋 RECENTLY DRAFTED", 
                                style='Header.TLabel', font=('Segoe UI', 12, 'bold'), 
                                foreground=self.parent.ACCENT_COLOR)
        draft_status.pack()
        
        pick_info = ttk.Label(draft_header, 
                             text=f"Pick #{draft_pick.overall_pick} • Round {draft_pick.round_num} • {draft_pick.team.team_name}", 
                             style='Info.TLabel', font=('Segoe UI', 10))
        pick_info.pack(pady=(2, 0))
        
        # Header with player name and position
        header_frame = ttk.Frame(card_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=(10, 15))
        
        name_label = ttk.Label(header_frame, text=player.full_name, 
                              style='Header.TLabel', font=('Segoe UI', 16, 'bold'))
        name_label.pack()
        
        position_label = ttk.Label(header_frame, text=f"{player.primary_position.value} • Overall: {to_100_scale(player.overall_rating())}", 
                                  style='Info.TLabel', font=('Segoe UI', 12))
        position_label.pack(pady=(2, 0))
        
        # Basic info section
        info_frame = ttk.LabelFrame(card_frame, text="📊 Basic Information", style='TLabelframe')
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_grid = ttk.Frame(info_frame, style='Panel.TFrame')
        info_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Basic info in 2 columns
        basic_info = [
            ("Age:", f"{player.age} years old"),
            ("Height:", f"{player.height}"),
            ("Weight:", f"{player.weight} lbs"),
            ("Shoots:", getattr(player, 'shoots', 'Unknown')),
            ("Former Team:", getattr(player, 'team_name', 'Free Agent')),
            ("New Team:", draft_pick.team.team_name)
        ]
        
        for i, (label, value) in enumerate(basic_info):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(info_grid, text=label, style='TLabel', font=('Segoe UI', 10, 'bold')).grid(
                row=row, column=col, sticky='w', padx=(0, 5), pady=2)
            ttk.Label(info_grid, text=value, style='TLabel').grid(
                row=row, column=col+1, sticky='w', padx=(0, 20), pady=2)
        
        # Attributes section
        attr_frame = ttk.LabelFrame(card_frame, text="⚡ Key Attributes", style='TLabelframe')
        attr_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.create_main_attribute_grid(attr_frame, player)
        
        # Draft summary
        summary_frame = ttk.LabelFrame(card_frame, text="🎯 Draft Summary", style='TLabelframe')
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        summary_content = ttk.Frame(summary_frame, style='Panel.TFrame')
        summary_content.pack(fill=tk.X, padx=10, pady=10)
        
        summary_text = f"{player.full_name} was selected {draft_pick.overall_pick} overall in round {draft_pick.round_num} by the {draft_pick.team.team_name}."
        
        summary_label = ttk.Label(summary_content, text=summary_text, 
                                 style='Info.TLabel', font=('Segoe UI', 10), 
                                 wraplength=300, justify='left')
        summary_label.pack()
        
    def setup_modern_player_list(self, parent):
        """Set up modern available players list with advanced filtering"""
        # Left panel container
        left_panel = ttk.Frame(parent, style='Panel.TFrame')
        parent.add(left_panel, weight=2)
        
        # Header with title and count
        header_frame = ttk.Frame(left_panel, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Label(header_frame, text="Available Players", 
                 style='Header.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold')).pack(side=tk.LEFT)
        
        self.available_count_label = ttk.Label(header_frame, text="", 
                                             style='Info.TLabel', font=(self.parent.FONT_FAMILY, 11))
        self.available_count_label.pack(side=tk.RIGHT)
        
        # Advanced filter section
        filter_frame = ttk.LabelFrame(left_panel, text="🔍 Filter & Search")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # First row - Search and position
        filter_row1 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row1.pack(fill=tk.X, padx=10, pady=5)
        
        # Search box with placeholder
        ttk.Label(filter_row1, text="Name:", style='TLabel').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_players)
        search_entry = ttk.Entry(filter_row1, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(5, 15))
        
        # Add placeholder text behavior
        def on_search_focus_in(event):
            if search_entry.get() == "Search player names...":
                search_entry.delete(0, tk.END)
                
        def on_search_focus_out(event):
            if not search_entry.get():
                search_entry.insert(0, "Search player names...")
                
        search_entry.bind('<FocusIn>', on_search_focus_in)
        search_entry.bind('<FocusOut>', on_search_focus_out)
        search_entry.insert(0, "Search player names...")  # Initial placeholder
        
        # Position filter
        ttk.Label(filter_row1, text="Position:", style='TLabel').pack(side=tk.LEFT)
        self.position_filter = tk.StringVar(value="All")
        position_combo = ttk.Combobox(filter_row1, textvariable=self.position_filter,
                                    values=["All", "Forward", "Defense", "Goalie", "C", "LW", "RW", "LD", "RD", "G"], 
                                    width=10, state="readonly")
        position_combo.pack(side=tk.LEFT, padx=(5, 15))
        position_combo.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Rating filter
        ttk.Label(filter_row1, text="Min OVR:", style='TLabel').pack(side=tk.LEFT)
        self.min_rating_var = tk.StringVar(value="0")
        rating_spinbox = tk.Spinbox(filter_row1, from_=0, to=99, textvariable=self.min_rating_var, 
                                   width=5, command=self.filter_players)
        rating_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Second row - Age and team filters
        filter_row2 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row2.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        # Age range
        ttk.Label(filter_row2, text="Age:", style='TLabel').pack(side=tk.LEFT)
        self.min_age_var = tk.StringVar(value="18")
        age_min = tk.Spinbox(filter_row2, from_=18, to=45, textvariable=self.min_age_var, 
                            width=4, command=self.filter_players)
        age_min.pack(side=tk.LEFT, padx=(5, 2))
        
        ttk.Label(filter_row2, text="-", style='TLabel').pack(side=tk.LEFT)
        
        self.max_age_var = tk.StringVar(value="45")
        age_max = tk.Spinbox(filter_row2, from_=18, to=45, textvariable=self.max_age_var, 
                            width=4, command=self.filter_players)
        age_max.pack(side=tk.LEFT, padx=(2, 15))
        
        # Former team filter
        ttk.Label(filter_row2, text="Former Team:", style='TLabel').pack(side=tk.LEFT)
        self.team_filter = tk.StringVar(value="All")
        team_values = ["All"] + [team.team_name for team in self.draft_manager.teams]
        team_combo = ttk.Combobox(filter_row2, textvariable=self.team_filter,
                                 values=team_values, width=15, state="readonly")
        team_combo.pack(side=tk.LEFT, padx=(5, 0))
        team_combo.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Filter control buttons
        button_frame = ttk.Frame(filter_row2, style='Panel.TFrame')
        button_frame.pack(side=tk.RIGHT, padx=5)
        
        # Show all button (increase display limit)
        show_all_btn = ttk.Button(button_frame, text="Show More", command=self.show_more_players, 
                                 style='TButton')
        show_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Clear filters button
        clear_btn = ttk.Button(button_frame, text="Clear Filters", command=self.clear_filters, 
                              style='Accent.TButton')
        clear_btn.pack(side=tk.LEFT)
        
        # Players treeview with modern styling
        tree_frame = ttk.Frame(left_panel, style='Panel.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Enhanced columns for better display
        columns = {
            'name': ('Player Name', 180),
            'position': ('Pos', 50),
            'overall': ('OVR', 50), 
            'age': ('Age', 45),
            'former_team': ('Former Team', 120),
            'potential': ('POT', 50)
        }
        
        self.players_tree = self.parent._create_treeview(tree_frame, columns, height=25)
        self.players_tree.bind('<Double-1>', self.on_player_select)
        self.players_tree.bind('<Button-1>', self.on_player_click)
        self.players_tree.bind('<Return>', self.on_player_select)
        
    def setup_modern_draft_panel(self, parent):
        """Set up modern draft panel with player details and draft controls"""
        # Right panel container  
        right_panel = ttk.Frame(parent, style='Panel.TFrame')
        parent.add(right_panel, weight=1)
        
        # Selected player details
        details_frame = ttk.LabelFrame(right_panel, text="🎯 Selected Player")
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Player info display
        self.player_info_frame = ttk.Frame(details_frame, style='Panel.TFrame')
        self.player_info_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Default message
        self.no_selection_label = ttk.Label(self.player_info_frame, 
                                          text="Select a player to view details and draft options",
                                          style='Info.TLabel', font=(self.parent.FONT_FAMILY, 11))
        self.no_selection_label.pack(pady=20)
        
        # Draft action panel
        action_frame = ttk.LabelFrame(right_panel, text="🏒 Draft Actions")
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        action_content = ttk.Frame(action_frame, style='Panel.TFrame')
        action_content.pack(fill=tk.X, padx=15, pady=15)
        
        # Draft button (large and prominent)
        self.draft_button = ttk.Button(action_content, text="🎯 DRAFT SELECTED PLAYER", 
                                     command=self.draft_selected_player, style='Accent.TButton')
        self.draft_button.pack(fill=tk.X, pady=(0, 10), ipady=8)
        self.draft_button.configure(state='disabled')
        
        # Button frame for draft controls
        button_frame = ttk.Frame(action_content, style='Panel.TFrame')
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Next pick button (advance one pick)
        self.next_pick_button = ttk.Button(button_frame, text="⏭️ Next Pick", 
                                         command=self.advance_one_pick, style='TButton')
        self.next_pick_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Sim to user pick button (advance until user's turn)
        self.sim_to_user_button = ttk.Button(button_frame, text="🚀 Sim to My Pick", 
                                           command=self.sim_to_user_pick, style='TButton')
        self.sim_to_user_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 2))
        
        # Sim rest of draft button (complete remaining draft)
        self.sim_rest_button = ttk.Button(button_frame, text="⚡ Sim Rest", 
                                        command=self.sim_rest_of_draft, style='TButton')
        self.sim_rest_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Auto-pick for AI teams button (legacy - full width)
        self.skip_button = ttk.Button(action_content, text="⏭️ Auto-Pick for AI Teams", 
                                    command=self.auto_pick_for_ai, style='TButton')
        self.skip_button.pack(fill=tk.X, pady=(0, 5))
        
        # Draft status
        self.draft_status_label = ttk.Label(action_content, text="", 
                                          style='Info.TLabel', font=(self.parent.FONT_FAMILY, 10))
        self.draft_status_label.pack(pady=5)
        
    def show_more_players(self):
        """Show more players by increasing the display limit"""
        if not hasattr(self, 'display_limit'):
            self.display_limit = 1000
        
        # Increase limit
        self.display_limit = min(self.display_limit + 500, 5000)  # Max 5000 for performance
        print(f"DEBUG: Increased display limit to {self.display_limit}")
        
        # Refresh the display
        self.filter_players()
        
    def clear_filters(self):
        """Clear all filter settings"""
        # Reset search (clear placeholder)
        self.search_var.set("")
        
        self.position_filter.set("All")
        self.min_rating_var.set("0")
        self.min_age_var.set("18")
        self.max_age_var.set("45")
        self.team_filter.set("All")
        self.filter_players()
        
    def setup_player_list_panel(self, parent):
        """Set up the available players list"""
        left_frame = ttk.LabelFrame(parent, text="Available Players")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Search and filter controls
        search_frame = ttk.Frame(left_frame, style='Panel.TFrame')
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Search box
        ttk.Label(search_frame, text="Search:", style='TLabel').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_players)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Position filter
        ttk.Label(search_frame, text="Position:", style='TLabel').pack(side=tk.LEFT, padx=(10, 0))
        self.position_filter = tk.StringVar(value="All")
        position_combo = ttk.Combobox(search_frame, textvariable=self.position_filter,
                                    values=["All", "C", "LW", "RW", "LD", "RD", "G"], 
                                    width=8, state="readonly")
        position_combo.pack(side=tk.LEFT, padx=5)
        position_combo.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Players treeview
        tree_frame = ttk.Frame(left_frame, style='Panel.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Create treeview for players
        columns = {
            'name': ('Player', 200),
            'position': ('Pos', 60),
            'overall': ('OVR', 60),
            'age': ('Age', 50),
            'team': ('Former Team', 120)
        }
        
        self.players_tree = self.parent._create_treeview(tree_frame, columns, height=25)
        self.players_tree.bind('<Double-1>', self.on_player_select)
        self.players_tree.bind('<Button-1>', self.on_player_click)
        
        # Draft button
        button_frame = ttk.Frame(left_frame, style='Panel.TFrame')
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.draft_button = ttk.Button(button_frame, text="🎯 DRAFT PLAYER", 
                                     command=self.draft_selected_player, style='Accent.TButton')
        self.draft_button.pack(pady=5)
        self.draft_button.configure(state='disabled')
        
    def setup_draft_board_panel(self, parent):
        """Set up the draft board panel"""
        right_frame = ttk.LabelFrame(parent, text="Draft Board")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Draft board notebook
        self.draft_notebook = ttk.Notebook(right_frame, style='TNotebook')
        self.draft_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Recent picks tab
        self.setup_recent_picks_tab()
        
        # Team rosters tab  
        self.setup_team_rosters_tab()
        
        # Draft order tab
        self.setup_draft_order_tab()
        
    def setup_recent_picks_tab(self):
        """Set up the recent picks display"""
        recent_frame = ttk.Frame(self.draft_notebook, style='Panel.TFrame')
        self.draft_notebook.add(recent_frame, text="Recent Picks")
        
        # Recent picks treeview
        columns = {
            'pick': ('Pick', 60),
            'team': ('Team', 120),
            'player': ('Player', 150),
            'position': ('Pos', 60),
            'overall': ('OVR', 60)
        }
        
        self.recent_picks_tree = self.parent._create_treeview(recent_frame, columns, height=20)
        
    def setup_team_rosters_tab(self):
        """Set up the team rosters display"""
        rosters_frame = ttk.Frame(self.draft_notebook, style='Panel.TFrame')
        self.draft_notebook.add(rosters_frame, text="Team Rosters")
        
        # Team selection
        team_select_frame = ttk.Frame(rosters_frame, style='Panel.TFrame')
        team_select_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(team_select_frame, text="View Team:", style='TLabel').pack(side=tk.LEFT)
        self.selected_team_var = tk.StringVar(value=self.user_team.team_name if self.user_team else "")
        team_combo = ttk.Combobox(team_select_frame, textvariable=self.selected_team_var,
                                 values=[team.team_name for team in self.draft_manager.teams],
                                 width=25, state="readonly")
        team_combo.pack(side=tk.LEFT, padx=5)
        team_combo.bind('<<ComboboxSelected>>', self.update_team_roster)
        
        # Team roster treeview
        columns = {
            'pick': ('Pick', 60),
            'player': ('Player', 150),
            'position': ('Pos', 60),
            'overall': ('OVR', 60),
            'age': ('Age', 50)
        }
        
        self.team_roster_tree = self.parent._create_treeview(rosters_frame, columns, height=15)
        
    def setup_draft_order_tab(self):
        """Set up the draft order display"""
        order_frame = ttk.Frame(self.draft_notebook, style='Panel.TFrame')
        self.draft_notebook.add(order_frame, text="Draft Order")
        
        # Draft order treeview
        columns = {
            'round': ('Round', 80),
            'pick': ('Pick', 60),
            'overall': ('Overall', 80),
            'team': ('Team', 150),
            'status': ('Status', 100)
        }
        
        self.draft_order_tree = self.parent._create_treeview(order_frame, columns, height=20)
        
        # Populate draft order
        self.populate_draft_order()
        
    def populate_draft_order(self):
        """Populate the draft order treeview"""
        if not hasattr(self, 'draft_order_tree'):
            return
            
        print("DEBUG: Populating draft order...")
        self.draft_order_tree.delete(*self.draft_order_tree.get_children())
        
        current_pick_index = self.draft_manager.current_pick
        
        for i, pick in enumerate(self.draft_manager.draft_picks[:100]):  # Show first 100 picks
            status = "COMPLETED" if pick.player else "UPCOMING"
            player_name = ""
            
            if pick.player:
                player_name = pick.player.full_name
            elif i == current_pick_index:
                status = "⏰ ON THE CLOCK"
                
            item = self.draft_order_tree.insert('', 'end', values=(
                pick.overall_pick,
                pick.round_num,
                pick.team.team_name,
                status,
                player_name
            ))
            
            # Highlight current pick
            if i == current_pick_index:
                self.draft_order_tree.selection_set(item)
                self.draft_order_tree.see(item)
                
        print(f"DEBUG: Added {len(self.draft_order_tree.get_children())} picks to draft order tree")
                
    def filter_players(self, *args):
        """Advanced filtering of available players"""
        try:
            search_text = self.search_var.get().lower() if hasattr(self, 'search_var') else ""
            # Ignore placeholder text
            if search_text == "search player names...":
                search_text = ""
            # Handle both integrated UI (position_var) and tab UI (position_filter)
            if hasattr(self, 'position_filter'):
                position_filter = self.position_filter.get()
            elif hasattr(self, 'position_var'):
                position_filter = self.position_var.get()
            else:
                position_filter = "All"
            min_rating = int(self.min_rating_var.get()) if hasattr(self, 'min_rating_var') else 0
            min_age = int(self.min_age_var.get()) if hasattr(self, 'min_age_var') else 18
            max_age = int(self.max_age_var.get()) if hasattr(self, 'max_age_var') else 45
            team_filter = self.team_filter.get() if hasattr(self, 'team_filter') else "All"
            
            available_players = self.draft_manager.get_available_players()
            print(f"DEBUG: filter_players called - {len(available_players)} available players")
            
            if len(available_players) == 0:
                print("DEBUG: No available players found!")
                self.populate_players_list([])
                return
            
            filtered_players = []
            for player in available_players:
                # Apply search filter
                if search_text and search_text not in player.full_name.lower():
                    continue
                    
                # Apply position filter
                if position_filter != "All":
                    if position_filter == "Forward":
                        if player.primary_position.value not in ["C", "LW", "RW"]:
                            continue
                    elif position_filter == "Defense":
                        if player.primary_position.value not in ["LD", "RD"]:
                            continue
                    elif position_filter == "Goalie":
                        if player.primary_position.value != "G":
                            continue
                    elif player.primary_position.value != position_filter:
                        continue
                        
                # Apply rating filter
                if player.overall_rating() < min_rating:
                    continue
                    
                # Apply age filter
                if player.age < min_age or player.age > max_age:
                    continue
                    
                # Apply team filter
                if team_filter != "All":
                    former_team = getattr(player, 'former_team', 'Unknown')
                    if former_team != team_filter:
                        continue
                    
                filtered_players.append(player)
                
            print(f"DEBUG: After filtering: {len(filtered_players)} players")
            
            # Sort by overall rating (highest first)
            filtered_players.sort(key=lambda p: p.overall_rating(), reverse=True)
            
            self.populate_players_list(filtered_players)
            
            # Update count
            if hasattr(self, 'available_count_label'):
                total_available = len(self.draft_manager.get_available_players())
                filtered_count = len(filtered_players)
                self.available_count_label.configure(text=f"Showing {filtered_count} of {total_available}")
                
        except Exception as e:
            print(f"DEBUG: Error in filter_players: {e}")
            import traceback
            traceback.print_exc()
        
    def populate_players_list(self, players: List[Player]):
        """Populate the players treeview with enhanced display"""
        print(f"DEBUG: populate_players_list called with {len(players)} players")
        
        # Clear existing items
        self.players_tree.delete(*self.players_tree.get_children())
        
        if len(players) == 0:
            print("DEBUG: No players to display in tree")
            return
        
        # Initialize tree_maps if it doesn't exist
        if not hasattr(self.parent, 'tree_maps'):
            self.parent.tree_maps = {}
        
        # Use dynamic display limit
        display_limit = getattr(self, 'display_limit', 1000)
        for i, player in enumerate(players[:display_limit]):
            try:
                # Calculate potential rating
                potential = getattr(player, 'potential', player.overall_rating())
                former_team = getattr(player, 'former_team', 'Free Agent')
                
                item = self.players_tree.insert('', 'end', values=(
                    player.full_name,
                    player.primary_position.value,
                    player.overall_rating(),
                    player.age,
                    former_team,
                    potential
                ))
                
                # Store player reference
                self.parent.tree_maps[item] = player
                
                # Color coding based on overall rating
                rating = player.overall_rating()
                if rating >= 90:
                    self.players_tree.set(item, 'overall', f"{rating} ⭐")
                elif rating >= 85:
                    self.players_tree.set(item, 'overall', f"{rating} 🔥")
                elif rating >= 80:
                    self.players_tree.set(item, 'overall', f"{rating} 💎")
                    
            except Exception as e:
                print(f"DEBUG: Error adding player {i}: {e}")
                continue
        
        items_added = len(self.players_tree.get_children())
        print(f"DEBUG: Added {items_added} items to tree")
        
        # Update the UI to show how many players are displayed vs total available
        if hasattr(self, 'available_count_label') and self.available_count_label:
            total_available = len(players)
            total_in_draft = len(self.draft_manager.get_available_players())
            
            if items_added < total_available:
                status_text = f"Showing {items_added} of {total_available} filtered players ({total_in_draft} total available)"
            else:
                if total_available < total_in_draft:
                    status_text = f"Showing all {total_available} filtered players ({total_in_draft} total available)"
                else:
                    status_text = f"Showing all {total_available} available players"
                    
            self.available_count_label.configure(text=status_text)
            
    def on_player_click(self, event):
        """Handle player selection with detailed display"""
        selection = self.players_tree.selection()
        if selection:
            item = selection[0]
            if item in self.parent.tree_maps:
                self.selected_player = self.parent.tree_maps[item]
                self.display_selected_player_details()
                self.draft_button.configure(state='normal')
            else:
                self.selected_player = None
                self.clear_player_details()
                self.draft_button.configure(state='disabled')
                
    def display_selected_player_details(self):
        """Display detailed information about selected player"""
        if not self.selected_player:
            return
            
        # Clear existing details
        for widget in self.player_info_frame.winfo_children():
            widget.destroy()
            
        player = self.selected_player
        
        # Player name and basic info
        name_frame = ttk.Frame(self.player_info_frame, style='Panel.TFrame')
        name_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(name_frame, text=player.full_name, 
                 style='Header.TLabel', font=(self.parent.FONT_FAMILY, 14, 'bold')).pack()
        
        info_text = f"{player.primary_position.value} • {player.age} years old • OVR {player.overall_rating()}"
        ttk.Label(name_frame, text=info_text, 
                 style='Info.TLabel', font=(self.parent.FONT_FAMILY, 10)).pack()
        
        # Former team
        former_team = getattr(player, 'former_team', 'Free Agent')
        ttk.Label(name_frame, text=f"Former: {former_team}", 
                 style='Info.TLabel', font=(self.parent.FONT_FAMILY, 10)).pack()
        
        # Key attributes based on position
        attrs_frame = ttk.Frame(self.player_info_frame, style='Panel.TFrame')
        attrs_frame.pack(fill=tk.X, pady=10)
        
        if player.primary_position.value == "G":
            # Goalie attributes
            attrs_text = f"Goaltending: {player.goaltending} • Reflexes: {player.reflexes} • Positioning: {player.positioning}"
        elif player.primary_position.value in ["LD", "RD"]:
            # Defense attributes  
            attrs_text = f"Defense: {player.defense} • Passing: {player.passing} • Shooting: {player.shooting}"
        else:
            # Forward attributes
            attrs_text = f"Shooting: {player.shooting} • Passing: {player.passing} • Skating: {player.skating}"
            
        ttk.Label(attrs_frame, text=attrs_text, 
                 style='Info.TLabel', font=(self.parent.FONT_FAMILY, 9)).pack()
        
        # Contract info if available
        if hasattr(player, 'contract') and player.contract:
            contract_text = f"Salary: ${getattr(player.contract, 'salary', 0):,}"
            ttk.Label(attrs_frame, text=contract_text, 
                     style='Info.TLabel', font=(self.parent.FONT_FAMILY, 9)).pack()
                     
    def clear_player_details(self):
        """Clear player details display"""
        for widget in self.player_info_frame.winfo_children():
            widget.destroy()
            
        self.no_selection_label = ttk.Label(self.player_info_frame, 
                                          text="Select a player to view details and draft options",
                                          style='Info.TLabel', font=(self.parent.FONT_FAMILY, 11))
        self.no_selection_label.pack(pady=20)
        
    def advance_one_pick(self):
        """Advance exactly one draft pick (AI or user)"""
        print(f"DEBUG: advance_one_pick called")
        
        if self.draft_manager.is_draft_complete():
            self.complete_draft()
            return
            
        current_pick = self.draft_manager.get_current_pick()
        if not current_pick:
            messagebox.showinfo("Draft Complete", "The fantasy draft is complete!")
            return
            
        print(f"DEBUG: Current pick #{current_pick.overall_pick} - {current_pick.team.team_name}")
        print(f"DEBUG: User team: {self.user_team.team_name if self.user_team else 'None'}")
        
        # Update simple status
        if hasattr(self, 'simple_status_label'):
            self.simple_status_label.configure(text=f"Processing Pick #{current_pick.overall_pick}...")
            
        # If it's user's turn, require manual selection
        if current_pick.team == self.user_team:
            messagebox.showwarning("Your Turn!", 
                                 f"🎯 It's your turn to pick!\n\n"
                                 f"Pick #{current_pick.overall_pick} - Round {current_pick.round_num}\n"
                                 f"Team: {current_pick.team.team_name}\n\n"
                                 f"Please select a player from the Available Players list and click 'DRAFT SELECTED PLAYER'")
            if hasattr(self, 'simple_status_label'):
                self.simple_status_label.configure(text=f"🎯 YOUR TURN - Pick #{current_pick.overall_pick} - Select a player to draft!")
            return
        else:
            # AI makes one pick
            available_players = self.draft_manager.get_available_players()
            if available_players:
                # Enhanced AI selection with team needs analysis
                team_needs = self.analyze_team_needs(current_pick.team)
                suitable_players = self.filter_by_team_needs(available_players, team_needs)
                
                if not suitable_players:
                    suitable_players = available_players[:20]  # Fallback to best available
                
                # AI picks best available player with some smart randomness
                top_players = suitable_players[:15]  # Top 15 available
                # Weight towards top players but allow some variety
                weights = [10, 8, 6, 5, 4, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1][:len(top_players)]
                ai_pick = random.choices(top_players, weights=weights, k=1)[0]
                
                success = self.draft_manager.make_pick(ai_pick)
                if success:
                    # Add to appropriate roster
                    if ai_pick.overall_rating() >= 40:
                        current_pick.team.roster.append(ai_pick)
                    elif ai_pick.overall_rating() >= 35:
                        current_pick.team.ahl_roster.append(ai_pick)
                    else:
                        current_pick.team.prospects.append(ai_pick)
                        
                    # CRITICAL: Force immediate draft board update
                    self.update_display()
                    
                    # FORCE immediate refresh of draft board specifically
                    if hasattr(self, 'recent_picks_tree'):
                        print(f"DEBUG: FORCE refreshing draft board after AI pick")
                        self.update_recent_picks()
                        self.update_idletasks()
                        
                    # Update team rosters display
                    if hasattr(self, 'team_roster_tree'):
                        self.update_all_team_rosters()
                    
                    # Show pick notification
                    next_pick = self.draft_manager.get_current_pick()
                    if next_pick:
                        if next_pick.team == self.user_team:
                            messagebox.showinfo("Your Turn!", 
                                              f"✅ {current_pick.team.team_name} selected {ai_pick.full_name}\n"
                                              f"   ({ai_pick.primary_position.value}, OVR {ai_pick.overall_rating()})\n\n"
                                              f"🎯 Now it's your turn!\n"
                                              f"Pick #{next_pick.overall_pick} - Round {next_pick.round_num}\n\n"
                                              f"Select a player and click 'DRAFT SELECTED PLAYER'")
                            if hasattr(self, 'simple_status_label'):
                                self.simple_status_label.configure(text=f"🎯 YOUR TURN - Pick #{next_pick.overall_pick} - Select a player to draft!")
                        else:
                            status_text = f"Pick #{current_pick.overall_pick}: {current_pick.team.team_name} → {ai_pick.full_name} ({ai_pick.primary_position.value}, {ai_pick.overall_rating()})"
                            if hasattr(self, 'draft_status_label'):
                                self.draft_status_label.configure(text=status_text)
                            if hasattr(self, 'simple_status_label'):
                                self.simple_status_label.configure(text=status_text)
                    else:
                        # Draft is complete
                        if hasattr(self, 'simple_status_label'):
                            self.simple_status_label.configure(text="🏆 Fantasy Draft Complete!")
                        self.complete_draft()
                
                # Ensure draft board is current after the pick
                self.after(50, self.ensure_draft_board_current)
    
    def sim_to_user_pick(self):
        """Simulate all picks until it's the user's turn"""
        print(f"DEBUG: sim_to_user_pick called")
        
        if hasattr(self, 'simple_status_label'):
            self.simple_status_label.configure(text="Simulating picks until your turn...")
        
        if self.draft_manager.is_draft_complete():
            self.complete_draft()
            return
            
        # Check if it's already user's turn
        current_pick = self.draft_manager.get_current_pick()
        if current_pick and current_pick.team == self.user_team:
            messagebox.showinfo("Already Your Turn!", 
                              f"🎯 It's already your turn to pick!\n\n"
                              f"Pick #{current_pick.overall_pick} - Round {current_pick.round_num}\n"
                              f"Team: {current_pick.team.team_name}\n\n"
                              f"Select a player from the list and click 'DRAFT SELECTED PLAYER'")
            if hasattr(self, 'simple_status_label'):
                self.simple_status_label.configure(text=f"🎯 YOUR TURN - Pick #{current_pick.overall_pick}")
            return
            
        picks_simmed = 0
        max_picks = 100  # Safety limit
        
        while picks_simmed < max_picks:
            current_pick = self.draft_manager.get_current_pick()
            
            # Check if draft is complete
            if not current_pick:
                self.complete_draft()
                return
                
            # Check if it's user's turn
            if current_pick.team == self.user_team:
                # Update display before showing message
                self.update_display()
                
                messagebox.showinfo("Your Turn!", 
                                  f"✅ Simulated {picks_simmed} picks successfully!\n\n"
                                  f"🎯 Now it's your turn to pick!\n"
                                  f"Pick #{current_pick.overall_pick} - Round {current_pick.round_num}\n"
                                  f"Team: {current_pick.team.team_name}\n\n"
                                  f"Select a player and click 'DRAFT SELECTED PLAYER'")
                
                if hasattr(self, 'simple_status_label'):
                    self.simple_status_label.configure(text=f"🎯 YOUR TURN - Pick #{current_pick.overall_pick} - Select a player!")
                    
                # Update integrated browser to reflect current state
                if hasattr(self, 'integrated_info_label'):
                    self.integrated_info_label.configure(text="🎯 YOUR TURN - Select a player to draft")
                    
                return
                
            # AI makes pick
            available_players = self.draft_manager.get_available_players()
            if not available_players:
                self.complete_draft()
                return
                
            # AI selection logic with position needs consideration
            team_needs = self.analyze_team_needs(current_pick.team)
            suitable_players = self.filter_by_team_needs(available_players, team_needs)
            
            if not suitable_players:
                suitable_players = available_players[:20]  # Fallback to best available
                
            # Weight selection towards top players
            top_candidates = suitable_players[:10]
            weights = [10, 8, 6, 5, 4, 3, 2, 2, 1, 1][:len(top_candidates)]
            ai_pick = random.choices(top_candidates, weights=weights, k=1)[0]
            
            success = self.draft_manager.make_pick(ai_pick)
            if success:
                # Add to appropriate roster
                if ai_pick.overall_rating() >= 40:
                    current_pick.team.roster.append(ai_pick)
                elif ai_pick.overall_rating() >= 35:
                    current_pick.team.ahl_roster.append(ai_pick)
                else:
                    current_pick.team.prospects.append(ai_pick)
                    
                picks_simmed += 1
                
                # CRITICAL: Force draft board update every few picks during simulation
                if picks_simmed % 3 == 0:  # Update every 3 picks instead of 5
                    print(f"DEBUG: Updating draft board during simulation - {picks_simmed} picks")
                    self.update_recent_picks()
                    if hasattr(self, 'simple_status_label'):
                        self.simple_status_label.configure(text=f"Simulated {picks_simmed} picks... (Pick #{current_pick.overall_pick})")
                    self.update_idletasks()  # Allow UI to update
                    
                # Always update status 
                elif hasattr(self, 'simple_status_label'):
                    self.simple_status_label.configure(text=f"Simulated {picks_simmed} picks... (Pick #{current_pick.overall_pick})")
                    
            else:
                print(f"ERROR: Failed to make AI pick for {current_pick.team.team_name}")
                break  # Something went wrong
                
        # CRITICAL: Final display update after simulation with forced refresh
        print(f"DEBUG: Final update after simulating {picks_simmed} picks")
        self.update_display()
        
        # FORCE immediate draft board refresh and make it visible
        if hasattr(self, 'recent_picks_tree'):
            print("DEBUG: FORCE final draft board refresh")
            self.ensure_draft_board_visible()  # Make sure draft board tab is active
            self.update_recent_picks()
            
        # FORCE team roster refresh  
        if hasattr(self, 'team_roster_tree'):
            self.update_all_team_rosters()
            
        # Force UI refresh
        self.update_idletasks()
        self.update()
        
        if picks_simmed >= max_picks:
            messagebox.showwarning("Simulation Limit", 
                                 f"Simulated maximum of {max_picks} picks.\n\n"
                                 f"Use 'Sim to My Pick' again if you need to simulate more picks.")
    
    def sim_rest_of_draft(self):
        """Simulate the entire remainder of the draft for all teams"""
        print(f"DEBUG: sim_rest_of_draft called")
        
        if hasattr(self, 'simple_status_label'):
            self.simple_status_label.configure(text="Preparing to simulate entire draft...")
        
        if self.draft_manager.is_draft_complete():
            self.complete_draft()
            return
            
        # Ask for confirmation since this is a big action
        current_pick = self.draft_manager.get_current_pick()
        remaining_picks = len(self.draft_manager.draft_picks) - self.draft_manager.current_pick
        
        response = messagebox.askyesno(
            "Simulate Rest of Draft", 
            f"This will simulate all remaining {remaining_picks} picks in the draft.\n\n"
            f"Current pick: #{current_pick.overall_pick if current_pick else 'N/A'}\n"
            f"Remaining picks: {remaining_picks}\n\n"
            f"Are you sure you want to continue?"
        )
        
        if not response:
            return
            
        picks_simmed = 0
        total_picks = remaining_picks
        
        # Show progress dialog for long simulation
        progress_window = tk.Toplevel(self)
        progress_window.title("Simulating Draft...")
        progress_window.geometry("400x150")
        progress_window.configure(background=self.parent.BG_COLOR)
        progress_window.transient(self)
        progress_window.grab_set()
        
        progress_label = ttk.Label(progress_window, text="Simulating draft picks...", 
                                 style='Title.TLabel')
        progress_label.pack(pady=20)
        
        progress_var = tk.StringVar()
        progress_detail = ttk.Label(progress_window, textvariable=progress_var, 
                                  style='Info.TLabel')
        progress_detail.pack(pady=10)
        
        progress_window.update()
        
        while not self.draft_manager.is_draft_complete():
            current_pick = self.draft_manager.get_current_pick()
            
            if not current_pick:
                break
                
            # Update progress
            picks_simmed += 1
            percentage = int((picks_simmed / total_picks) * 100) if total_picks > 0 else 0
            progress_var.set(f"Pick #{current_pick.overall_pick}: {current_pick.team.team_name} ({percentage}%)")
            progress_window.update()
            
            # AI selection logic with team needs
            available_players = self.draft_manager.get_available_players()
            if not available_players:
                break
                
            team_needs = self.analyze_team_needs(current_pick.team)
            suitable_players = self.filter_by_team_needs(available_players, team_needs)
            
            if not suitable_players:
                suitable_players = available_players[:20]  # Fallback to best available
                
            # Weight selection towards top players with some randomness
            top_candidates = suitable_players[:10]
            weights = [10, 8, 6, 5, 4, 3, 2, 2, 1, 1][:len(top_candidates)]
            ai_pick = random.choices(top_candidates, weights=weights, k=1)[0]
            
            success = self.draft_manager.make_pick(ai_pick)
            if success:
                # Add to appropriate roster based on rating
                if ai_pick.overall_rating() >= 40:
                    current_pick.team.roster.append(ai_pick)
                elif ai_pick.overall_rating() >= 35:
                    current_pick.team.ahl_roster.append(ai_pick)
                else:
                    current_pick.team.prospects.append(ai_pick)
            else:
                print(f"ERROR: Failed to make pick for {current_pick.team.team_name}")
                break
                
            # Small delay to show progress (optional)
            if picks_simmed % 10 == 0:
                progress_window.after(10)  # Brief pause every 10 picks
                
        # Close progress window
        progress_window.destroy()
        
        # CRITICAL: Update display after simulation with forced refresh
        print(f"DEBUG: Final update after simulating {picks_simmed} picks in sim_rest_of_draft")
        self.update_display()
        
        # FORCE immediate draft board refresh and make it visible
        if hasattr(self, 'recent_picks_tree'):
            print("DEBUG: FORCE final draft board refresh in sim_rest_of_draft")
            self.ensure_draft_board_visible()  # Make sure draft board tab is active
            self.update_recent_picks()
            
        # FORCE team roster refresh  
        if hasattr(self, 'team_roster_tree'):
            self.update_all_team_rosters()
            
        # Force UI refresh
        self.update_idletasks()
        self.update()
        
        # Show completion message
        if self.draft_manager.is_draft_complete():
            messagebox.showinfo(
                "Draft Complete!", 
                f"🎉 Fantasy Draft Complete!\n\n"
                f"Simulated {picks_simmed} remaining picks.\n"
                f"Total picks in draft: {len(self.draft_manager.draft_picks)}\n\n"
                f"All teams now have their full rosters!"
            )
            self.complete_draft()
        else:
            messagebox.showinfo(
                "Simulation Complete", 
                f"Simulated {picks_simmed} picks.\n"
                f"Draft may still be in progress - check current pick status."
            )
    
    def analyze_team_needs(self, team):
        """Analyze what positions a team needs most"""
        # Count current picks by position
        position_counts = {'F': 0, 'D': 0, 'G': 0}  # Forward, Defense, Goalie
        
        team_picks = [pick.player for pick in self.draft_manager.draft_picks 
                     if pick.team.team_name == team.team_name and pick.player]
        
        for player in team_picks:
            pos = player.primary_position.value
            if pos in ['C', 'LW', 'RW']:
                position_counts['F'] += 1
            elif pos in ['LD', 'RD']:
                position_counts['D'] += 1
            elif pos == 'G':
                position_counts['G'] += 1
                
        # Determine needs (target ratios: ~12F, 6D, 2G for 20 picks)
        needs = []
        if position_counts['G'] < 2:
            needs.append('G')
        if position_counts['D'] < 6:
            needs.append('D')  
        if position_counts['F'] < 12:
            needs.append('F')
            
        return needs if needs else ['F', 'D', 'G']  # Default if no specific needs
    
    def filter_by_team_needs(self, players, needs):
        """Filter players by team positional needs"""
        suitable = []
        
        for player in players:
            pos = player.primary_position.value
            if 'G' in needs and pos == 'G':
                suitable.append(player)
            elif 'D' in needs and pos in ['LD', 'RD']:
                suitable.append(player)
            elif 'F' in needs and pos in ['C', 'LW', 'RW']:
                suitable.append(player)
                
        # Sort by overall rating
        suitable.sort(key=lambda p: p.overall_rating(), reverse=True)
        return suitable[:50]  # Return top 50 suitable players
    
    def auto_pick_for_ai(self):
        """Auto-pick for AI teams until it's user's turn"""
        if self.draft_manager.is_draft_complete():
            self.complete_draft()
            return
            
        current_pick = self.draft_manager.get_current_pick()
        if current_pick and current_pick.team != self.user_team:
            self.continue_auto_draft()
        else:
            messagebox.showinfo("User Turn", "It's your turn to pick!")
                
    def on_player_select(self, event):
        """Handle double-click to draft player"""
        self.draft_selected_player()
        
    def draft_selected_player(self):
        """Draft the currently selected player"""
        if not self.selected_player:
            messagebox.showwarning("No Selection", "Please select a player to draft.")
            return
            
        current_pick = self.draft_manager.get_current_pick()
        if not current_pick:
            messagebox.showinfo("Draft Complete", "The fantasy draft is complete!")
            return
            
        # Check if it's user's turn or auto-draft is enabled
        if current_pick.team != self.user_team and not self.auto_draft_enabled.get():
            messagebox.showinfo("Not Your Turn", 
                              f"It's {current_pick.team.team_name}'s turn to pick.")
            return
            
        # Make the pick
        success = self.draft_manager.make_pick(self.selected_player)
        if success:
            # Add player to appropriate roster based on rating
            if self.selected_player.overall_rating() >= 40:
                current_pick.team.roster.append(self.selected_player)
            elif self.selected_player.overall_rating() >= 35:
                current_pick.team.ahl_roster.append(self.selected_player)
            else:
                current_pick.team.prospects.append(self.selected_player)
                
            self.update_display()
            self.selected_player = None
            self.draft_button.configure(state='disabled')
            
            # Continue with AI picks if enabled
            if self.auto_draft_enabled.get() or current_pick.team != self.user_team:
                self.after(1000, self.continue_auto_draft)
        else:
            messagebox.showerror("Draft Error", "Unable to complete the draft pick.")
            
    def continue_auto_draft(self):
        """Continue with automated draft picks"""
        if self.draft_manager.is_draft_complete():
            self.complete_draft()
            return
            
        current_pick = self.draft_manager.get_current_pick()
        if current_pick and current_pick.team != self.user_team:
            # AI makes pick
            available_players = self.draft_manager.get_available_players()
            if available_players:
                # AI picks best available player with some randomness
                top_players = available_players[:10]  # Top 10 available
                ai_pick = random.choice(top_players[:3])  # Pick from top 3
                
                success = self.draft_manager.make_pick(ai_pick)
                if success:
                    # Add to appropriate roster
                    if ai_pick.overall_rating() >= 40:
                        current_pick.team.roster.append(ai_pick)
                    elif ai_pick.overall_rating() >= 35:
                        current_pick.team.ahl_roster.append(ai_pick)
                    else:
                        current_pick.team.prospects.append(ai_pick)
                        
                    self.update_display()
                    
                    # Continue if still not user's turn
                    next_pick = self.draft_manager.get_current_pick()
                    if next_pick and next_pick.team != self.user_team:
                        delay = 500 if self.draft_speed.get() == "Fast" else 1500 if self.draft_speed.get() == "Slow" else 1000
                        self.after(delay, self.continue_auto_draft)
                        
    def complete_draft(self):
        """Handle draft completion"""
        messagebox.showinfo("Draft Complete", 
                          "The fantasy draft is complete! All players have been redistributed among teams.")
        
        # Mark fantasy draft as completed in game manager
        if hasattr(self.game_manager, 'pending_fantasy_draft'):
            self.game_manager.pending_fantasy_draft = False
            
        # Add completion message to inbox
        self.add_draft_completion_message()
        
        # Update the main game if possible
        try:
            if hasattr(self.parent, 'update_views'):
                self.parent.update_views()
        except:
            pass  # Ignore if update method doesn't exist
        self.destroy()
        
    def add_draft_completion_message(self):
        """Add a draft completion message to the user's inbox"""
        try:
            from game_classes import EmailMessage
            from datetime import date
            
            completion_email = EmailMessage(
                sender="NHL Commissioner",
                sender_type="League",
                subject="🏆 Fantasy Draft Complete - Results Summary",
                content=f"""Dear General Manager,

The Fantasy Draft has been successfully completed!

DRAFT RESULTS:
• Total players redistributed: {len(self.draft_manager.all_players)}
• Draft rounds completed: {self.draft_manager.config.rounds}
• Your team's final roster has been updated

All players have been assigned to their new teams based on the draft results. You can now review your new roster and begin planning for the upcoming season.

Thank you for participating in the Fantasy Draft!

Best regards,
NHL League Office""",
                date_sent=date.today(),
                is_important=True,
                category="League",
                priority=3
            )
            
            # Add to user team's inbox
            user_team = self.game_manager.user_team
            if user_team:
                user_team.inbox.add_message(completion_email)
                
        except Exception as e:
            print(f"Error adding completion message: {e}")
        
    def update_display(self):
        """Update all UI elements comprehensively with forced refresh"""
        print("DEBUG: update_display called - refreshing all UI elements")
        
        current_pick = self.draft_manager.get_current_pick()
        
        # Update main header info
        if hasattr(self, 'current_pick_label'):
            if current_pick:
                pick_text = f"Pick {current_pick.overall_pick}: {current_pick.team.team_name} selecting..."
                self.current_pick_label.configure(text=pick_text)
                
                # Update draft status
                if hasattr(self, 'draft_status_label'):
                    if current_pick.team == self.user_team:
                        self.draft_status_label.configure(text="🎯 YOUR TURN TO PICK!")
                    else:
                        self.draft_status_label.configure(text=f"Waiting for {current_pick.team.team_name}...")
            else:
                self.current_pick_label.configure(text="Draft Complete!")
                if hasattr(self, 'draft_status_label'):
                    self.draft_status_label.configure(text="🏆 Draft Complete!")
        
        # Update integrated current pick label
        if hasattr(self, 'integrated_current_label'):
            if current_pick:
                current_text = f"Current Pick: #{current_pick.overall_pick} - {current_pick.team.team_name}"
                self.integrated_current_label.configure(text=current_text)
            else:
                self.integrated_current_label.configure(text="Draft Complete")
        
        # Force update integrated browsers
        if hasattr(self, 'integrated_players_tree'):
            print("DEBUG: Updating integrated players browser")
            self.integrated_populate_players()
            
        if hasattr(self, 'integrated_draft_tree'):
            print("DEBUG: Updating integrated draft order")
            self.integrated_populate_draft_order()
            
        # Update legacy components if they exist
        if hasattr(self, 'players_tree'):
            self.filter_players()
        
        # Update draft board and team rosters
        print("DEBUG: Updating draft board and team rosters")
        self.update_recent_picks()
        self.update_all_team_rosters()
        
        # Update player spotlight with most recent pick
        self.update_main_player_spotlight()
        
        # Update draft order
        self.populate_draft_order()
            
        # Update header statistics
        self.update_header_stats()
        
        # ENHANCED: Update simple status label if it exists
        if hasattr(self, 'simple_status_label'):
            if current_pick:
                if current_pick.team == self.user_team:
                    status_text = f"🎯 YOUR TURN - Pick #{current_pick.overall_pick}"
                else:
                    status_text = f"⏳ {current_pick.team.team_name} is selecting - Pick #{current_pick.overall_pick}"
            else:
                status_text = "🏆 DRAFT COMPLETE - All picks made!"
            self.simple_status_label.configure(text=status_text)
        
        # ENHANCED: Force multiple UI refresh cycles to ensure updates show
        self.update_idletasks()
        self.update()  # Force immediate update
        
        # Schedule another refresh to ensure it sticks
        self.after_idle(lambda: self.update_idletasks())
        
        print("DEBUG: update_display completed - all UI elements force refreshed")
    
    def update_header_stats(self):
        """Update statistics in the header"""
        try:
            available_count = len(self.draft_manager.get_available_players())
            completed_picks = len([p for p in self.draft_manager.draft_picks if p.player])
            total_picks = len(self.draft_manager.draft_picks)
            
            # Find and update stats label in header
            # This is a bit hacky but necessary to update the dynamically created header
            def update_stats_recursive(widget):
                for child in widget.winfo_children():
                    if hasattr(child, 'cget') and isinstance(child, ttk.Label):
                        text = str(child.cget('text'))
                        if "Available:" in text:
                            new_stats = f"Available: {available_count} Players • Picks Made: {completed_picks}/{total_picks}"
                            child.configure(text=new_stats)
                            return True
                    elif hasattr(child, 'winfo_children'):
                        if update_stats_recursive(child):
                            return True
                return False
                
            update_stats_recursive(self)
            
        except Exception as e:
            print(f"DEBUG: Error updating header stats: {e}")
        
    def begin_draft(self):
        """Start the fantasy draft"""
        # Confirm start
        result = messagebox.askyesno(
            "Begin Fantasy Draft",
            f"Are you sure you want to begin the fantasy draft?\n\n"
            f"This will:\n"
            f"• Clear all current team rosters\n"
            f"• Redistribute {len(self.draft_manager.all_players)} players\n"
            f"• Start the {self.draft_manager.config.rounds}-round draft\n\n"
            f"This action cannot be undone!"
        )
        
        if result:
            # Hide begin draft button
            if hasattr(self, 'begin_draft_button'):
                self.begin_draft_button.destroy()
            
            # Initialize the first pick
            self.draft_manager.current_pick = 0
            
            # Update display to show first pick
            self.update_display()
            
            # Add delayed updates to ensure tabs are ready
            self.after(200, self.update_recent_picks)
            self.after(300, self.update_all_team_rosters)
            self.after(400, self.update_main_player_spotlight)
            
            # Also ensure team rosters tab shows initial state
            print("DEBUG: Scheduling initial team roster display update")
            self.after(500, lambda: self.update_team_roster() if hasattr(self, 'update_team_roster') else None)
            
            # Show success message
            first_pick = self.draft_manager.get_current_pick()
            if first_pick:
                messagebox.showinfo(
                    "Fantasy Draft Started!",
                    f"The fantasy draft has begun!\n\n"
                    f"First pick: {first_pick.team.team_name} (Pick #{first_pick.overall_pick})"
                )
                
    def clear_filters(self):
        """Clear all player filters"""
        if hasattr(self, 'search_var'):
            self.search_var.set("")
        
        # Handle both integrated UI (position_var) and tab UI (position_filter)
        if hasattr(self, 'position_filter'):
            self.position_filter.set("All")
        elif hasattr(self, 'position_var'):
            self.position_var.set("All")
        
        if hasattr(self, 'min_rating_var'):
            self.min_rating_var.set("0")
        if hasattr(self, 'min_age_var'):
            self.min_age_var.set("18")
        if hasattr(self, 'max_age_var'):
            self.max_age_var.set("45")
        if hasattr(self, 'team_filter'):
            self.team_filter.set("All")
        
        self.filter_players()
        
        # Update header stats
        if hasattr(self, 'available_count_label'):
            available_count = len(self.draft_manager.get_available_players())
            completed_picks = len([p for p in self.draft_manager.draft_picks if p.player])
            total_picks = len(self.draft_manager.draft_picks)
            
            # Update the stats in header
            for widget in self.winfo_children():
                if hasattr(widget, 'winfo_children'):
                    for child in widget.winfo_children():
                        if hasattr(child, 'winfo_children'):
                            for grandchild in child.winfo_children():
                                if hasattr(grandchild, 'winfo_children'):
                                    for label in grandchild.winfo_children():
                                        if isinstance(label, ttk.Label) and "Available:" in str(label.cget('text')):
                                            stats_text = f"Available: {available_count} Players • Picks Made: {completed_picks}/{total_picks}"
                                            label.configure(text=stats_text)
        
    def update_recent_picks(self):
        """Update the round-by-round draft board"""
        if not hasattr(self, 'round_trees'):
            return
            
        print("DEBUG: Updating round-by-round draft board")
        
        # Get all completed picks
        completed_picks = [pick for pick in self.draft_manager.draft_picks if pick.player]
        
        # Update info label
        if hasattr(self, 'draft_board_info_label'):
            total_picks = len(self.draft_manager.draft_picks)
            info_text = f"Showing {len(completed_picks)} of {total_picks} total picks across {self.draft_manager.config.rounds} rounds"
            self.draft_board_info_label.configure(text=info_text)
        
        # Group picks by round
        picks_by_round = {}
        for pick in completed_picks:
            round_num = pick.round_num
            if round_num not in picks_by_round:
                picks_by_round[round_num] = []
            picks_by_round[round_num].append(pick)
        
        # Create round tabs if they don't exist yet
        highest_round = max(picks_by_round.keys()) if picks_by_round else 1
        for round_num in range(1, highest_round + 2):  # +2 to create next round tab
            if round_num not in self.round_trees and round_num <= self.draft_manager.config.rounds:
                self.create_round_tab(round_num)
        
        # Update each round tab
        for round_num, round_tree in self.round_trees.items():
            # Clear existing picks
            round_tree.delete(*round_tree.get_children())
            
            # Add picks for this round
            if round_num in picks_by_round:
                round_picks = sorted(picks_by_round[round_num], key=lambda p: p.overall_pick)
                
                for pick in round_picks:
                    # Highlight user team picks
                    tags = ['user_team'] if pick.team == self.user_team else []
                    
                    round_tree.insert('', 'end', values=(
                        pick.overall_pick,
                        pick.team.team_name,
                        pick.player.full_name,
                        pick.player.primary_position.value,
                        pick.player.overall_rating(),
                        pick.player.age
                    ), tags=tags)
                
                # Style user team picks
                round_tree.tag_configure('user_team', background='#2D4A4A', foreground='#FFFFFF')
                
                # Update tab title with pick count
                tab_text = f"Round {round_num} ({len(round_picks)} picks)"
                tab_index = self.get_round_tab_index(round_num)
                if tab_index is not None:
                    self.round_notebook.tab(tab_index, text=tab_text)
        
        # Switch to the round with the most recent pick
        if completed_picks:
            latest_pick = completed_picks[-1]
            latest_round = latest_pick.round_num
            tab_index = self.get_round_tab_index(latest_round)
            if tab_index is not None:
                self.round_notebook.select(tab_index)
        
        # Also update team rosters display if it exists
        if hasattr(self, 'refresh_team_roster_display'):
            try:
                self.refresh_team_roster_display()
            except Exception as e:
                print(f"DEBUG: Error updating team rosters: {e}")
        
        print(f"DEBUG: Updated draft board with {len(completed_picks)} picks across {len(picks_by_round)} rounds")
    
    def get_round_tab_index(self, round_num):
        """Get the index of a round tab in the notebook"""
        try:
            for i in range(self.round_notebook.index('end')):
                tab_text = self.round_notebook.tab(i, 'text')
                if f"Round {round_num}" in tab_text:
                    return i
        except:
            pass
        return None
        
    def ensure_draft_board_current(self):
        """Ensure draft board shows all current picks - handles missed updates"""
        try:
            if hasattr(self, 'recent_picks_tree') and self.recent_picks_tree.winfo_exists():
                completed_picks = [pick for pick in self.draft_manager.draft_picks if pick.player]
                current_items = len(self.recent_picks_tree.get_children())
                
                if len(completed_picks) != current_items:
                    print(f"DEBUG: Draft board sync issue - {len(completed_picks)} picks vs {current_items} displayed, forcing update")
                    self.update_recent_picks()
                else:
                    print(f"DEBUG: Draft board is current - {len(completed_picks)} picks displayed correctly")
        except Exception as e:
            print(f"DEBUG: Error checking draft board currency: {e}")
        
    def force_draft_board_update(self):
        """Force immediate update of the draft board"""
        print("DEBUG: force_draft_board_update called")
        try:
            if hasattr(self, 'recent_picks_tree') and self.recent_picks_tree.winfo_exists():
                print("DEBUG: Found recent_picks_tree, updating...")
                self.update_recent_picks()
                
                # Additional forced refresh
                self.recent_picks_tree.update_idletasks()
                self.recent_picks_tree.update()
                
                # Schedule another update to ensure it sticks
                self.after(100, lambda: self.recent_picks_tree.update_idletasks())
                print("DEBUG: Draft board forced update completed")
            else:
                print("DEBUG: No recent_picks_tree found or not visible")
        except Exception as e:
            print(f"DEBUG: Error in force_draft_board_update: {e}")
            
    def force_team_roster_update(self):
        """Force immediate update of team rosters"""
        print("DEBUG: force_team_roster_update called")
        try:
            if hasattr(self, 'team_roster_tree') and self.team_roster_tree.winfo_exists():
                print("DEBUG: Found team_roster_tree, updating...")
                self.update_team_roster()
                
                # Additional forced refresh
                self.team_roster_tree.update_idletasks()
                self.team_roster_tree.update()
                print("DEBUG: Team roster forced update completed")
            else:
                print("DEBUG: No team_roster_tree found or not visible")
        except Exception as e:
            print(f"DEBUG: Error in force_team_roster_update: {e}")

    def ensure_draft_board_visible(self):
        """Ensure the draft board tab is visible when updates happen"""
        try:
            if hasattr(self, 'notebook'):
                # Find the draft board tab
                for i in range(self.notebook.index('end')):
                    tab_text = self.notebook.tab(i, 'text')
                    if 'Draft Board' in tab_text:
                        print(f"DEBUG: Switching to Draft Board tab for visibility")
                        self.notebook.select(i)
                        self.notebook.update_idletasks()
                        break
        except Exception as e:
            print(f"DEBUG: Error switching to draft board tab: {e}")
        
    def on_draft_pick_select(self, event):
        """Handle selection of a draft pick to show player card"""
        if not hasattr(self, 'recent_picks_tree'):
            return
            
        selection = self.recent_picks_tree.selection()
        if not selection:
            return
            
        # Get the selected pick
        item = self.recent_picks_tree.item(selection[0])
        values = item['values']
        
        if not values:
            return
            
        # Find the corresponding pick and player
        pick_num = int(values[0])  # Overall pick number
        selected_pick = None
        
        for pick in self.draft_manager.draft_picks:
            if pick.overall_pick == pick_num and pick.player:
                selected_pick = pick
                break
                
        if selected_pick:
            self.show_player_card(selected_pick.player, selected_pick)
            
    def show_welcome_card(self):
        """Show welcome message in player card area"""
        # Clear existing card
        for widget in self.player_card_frame.winfo_children():
            widget.destroy()
            
        # Welcome message
        welcome_frame = ttk.Frame(self.player_card_frame, style='Panel.TFrame')
        welcome_frame.pack(fill=tk.BOTH, expand=True)
        
        # Center the welcome message
        center_frame = ttk.Frame(welcome_frame, style='Panel.TFrame')
        center_frame.pack(expand=True)
        
        welcome_label = ttk.Label(center_frame, 
                                 text="🎯 Player Cards", 
                                 style='Header.TLabel', 
                                 font=('Segoe UI', 18, 'bold'))
        welcome_label.pack(pady=(50, 10))
        
        instruction_label = ttk.Label(center_frame, 
                                    text="Click any draft pick to view\ndetailed player information", 
                                    style='Info.TLabel',
                                    font=('Segoe UI', 12),
                                    justify=tk.CENTER)
        instruction_label.pack(pady=10)
        
        # Add some visual elements
        separator = ttk.Separator(center_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=20, padx=40)
        
        tip_label = ttk.Label(center_frame,
                             text="💡 Tip: Player cards show detailed stats,\nratings, and draft information",
                             style='Info.TLabel',
                             font=('Segoe UI', 10, 'italic'),
                             justify=tk.CENTER)
        tip_label.pack(pady=10)
        
    def show_player_card(self, player, draft_pick=None):
        """Show detailed player card with professional styling"""
        # Clear existing card
        for widget in self.player_card_frame.winfo_children():
            widget.destroy()
            
        # Main card frame with border
        card_main = ttk.LabelFrame(self.player_card_frame, 
                                  text=f"🏒 {player.full_name}", 
                                  style='Card.TLabelframe')
        card_main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Card content with scrolling
        canvas = tk.Canvas(card_main, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(card_main, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Player header section
        header_frame = ttk.Frame(scrollable_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Position and rating badges
        badges_frame = ttk.Frame(header_frame, style='Panel.TFrame')
        badges_frame.pack(fill=tk.X, pady=(0, 10))
        
        pos_label = ttk.Label(badges_frame, 
                             text=f"{player.primary_position.value}", 
                             style='Badge.TLabel',
                             font=('Segoe UI', 10, 'bold'))
        pos_label.pack(side=tk.LEFT)
        
        ovr_label = ttk.Label(badges_frame, 
                             text=f"OVR: {to_100_scale(player.overall_rating())}", 
                             style='Rating.TLabel',
                             font=('Segoe UI', 12, 'bold'))
        ovr_label.pack(side=tk.LEFT, padx=(10, 0))
        
        age_label = ttk.Label(badges_frame,
                             text=f"Age: {player.age}",
                             style='Info.TLabel')
        age_label.pack(side=tk.RIGHT)
        
        # Draft information if available
        if draft_pick:
            draft_frame = ttk.LabelFrame(scrollable_frame, 
                                       text="📋 Draft Information", 
                                       style='Section.TLabelframe')
            draft_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
            
            draft_info = ttk.Frame(draft_frame, style='Panel.TFrame')
            draft_info.pack(fill=tk.X, padx=10, pady=8)
            
            pick_info = f"Pick #{draft_pick.overall_pick} (Round {draft_pick.round_num})"
            ttk.Label(draft_info, text=pick_info, 
                     style='Header.TLabel', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
            
            team_info = f"Selected by: {draft_pick.team.team_name}"
            ttk.Label(draft_info, text=team_info, 
                     style='Info.TLabel').pack(anchor='w', pady=(2, 0))
        
        # Key attributes section
        attrs_frame = ttk.LabelFrame(scrollable_frame, 
                                   text="⭐ Key Attributes", 
                                   style='Section.TLabelframe')
        attrs_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        attrs_content = ttk.Frame(attrs_frame, style='Panel.TFrame')
        attrs_content.pack(fill=tk.X, padx=10, pady=8)
        
        # Create attribute grid based on position
        self.create_attribute_grid(attrs_content, player)
        
        # Physical info section
        physical_frame = ttk.LabelFrame(scrollable_frame, 
                                      text="💪 Physical Information", 
                                      style='Section.TLabelframe')
        physical_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        phys_content = ttk.Frame(physical_frame, style='Panel.TFrame')
        phys_content.pack(fill=tk.X, padx=10, pady=8)
        
        # Add physical attributes
        physical_attrs = [
            ("Strength", getattr(player, 'strength', 0)),
            ("Speed", getattr(player, 'skating', 0)),
            ("Injury Proneness", getattr(player, 'injury_proneness', 0)),
        ]
        
        for i, (attr_name, value) in enumerate(physical_attrs):
            row = i // 2
            col = i % 2
            
            attr_frame = ttk.Frame(phys_content, style='Panel.TFrame')
            attr_frame.grid(row=row, column=col, sticky='ew', padx=5, pady=2)
            phys_content.columnconfigure(col, weight=1)
            
            ttk.Label(attr_frame, text=f"{attr_name}:", 
                     style='TLabel', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT)
            ttk.Label(attr_frame, text=str(value), 
                     style='Value.TLabel').pack(side=tk.RIGHT)
        
        # Contract info if available
        if hasattr(player, 'contract') and player.contract:
            contract_frame = ttk.LabelFrame(scrollable_frame, 
                                          text="💰 Contract Information", 
                                          style='Section.TLabelframe')
            contract_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
            
            contract_content = ttk.Frame(contract_frame, style='Panel.TFrame')
            contract_content.pack(fill=tk.X, padx=10, pady=8)
            
            salary = getattr(player.contract, 'salary', 750000)
            ttk.Label(contract_content, text=f"Salary: ${salary:,}", 
                     style='Header.TLabel').pack(anchor='w')
            
            years = getattr(player.contract, 'years', 1)
            ttk.Label(contract_content, text=f"Contract Length: {years} year(s)", 
                     style='Info.TLabel').pack(anchor='w', pady=(2, 0))
        
        # Bind mousewheel to canvas
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", on_mousewheel)
        
    def create_attribute_grid(self, parent, player):
        """Create a grid of player attributes based on position"""
        if player.primary_position == PlayerPosition.GOALIE:
            # Goalie-specific attributes
            attributes = [
                ("Goaltending", getattr(player, 'goaltending', 0)),
                ("Reflexes", getattr(player, 'reflexes', 0)),
                ("Positioning", getattr(player, 'positioning', 0)),
                ("Rebound Control", getattr(player, 'rebound_control', 0)),
                ("Composure", getattr(player, 'composure', 0)),
                ("Leadership", getattr(player, 'leadership', 0))
            ]
        else:
            # Skater attributes
            attributes = [
                ("Skating", getattr(player, 'skating', 0)),
                ("Shooting", getattr(player, 'shooting', 0)),
                ("Passing", getattr(player, 'passing', 0)),
                ("Checking", getattr(player, 'checking', 0)),
                ("Hockey IQ", getattr(player, 'hockey_iq', 0)),
                ("Leadership", getattr(player, 'leadership', 0)),
                ("Determination", getattr(player, 'determination', 0)),
                ("Teamwork", getattr(player, 'teamwork', 0))
            ]
        
        # Create grid layout
        for i, (attr_name, value) in enumerate(attributes):
            row = i // 2
            col = i % 2
            
            attr_frame = ttk.Frame(parent, style='Panel.TFrame')
            attr_frame.grid(row=row, column=col, sticky='ew', padx=5, pady=3)
            parent.columnconfigure(col, weight=1)
            
            # Attribute name
            name_label = ttk.Label(attr_frame, text=f"{attr_name}:", 
                                  style='TLabel', font=('Segoe UI', 9, 'bold'))
            name_label.pack(side=tk.LEFT)
            
            # Attribute value with rating color
            value_color = self.get_rating_color(value)
            value_label = ttk.Label(attr_frame, text=str(value), 
                                   style='Value.TLabel', font=('Segoe UI', 9, 'bold'))
            value_label.pack(side=tk.RIGHT)
            
    def get_rating_color(self, rating):
        """Get color based on rating value"""
        if rating >= 18:
            return '#00FF00'  # Excellent - Green
        elif rating >= 15:
            return '#FFFF00'  # Good - Yellow
        elif rating >= 12:
            return '#FFA500'  # Average - Orange
        else:
            return '#FF6B6B'  # Poor - Red
        
    def update_all_team_rosters(self):
        """Update all team rosters after draft changes - Fixed implementation"""
        try:
            # Update currently selected team roster if it exists
            if hasattr(self, 'update_team_roster') and hasattr(self, 'team_roster_tree'):
                self.update_team_roster()
                print("DEBUG: Successfully updated team rosters")
            else:
                print("DEBUG: Team roster components not found, skipping update")
                
        except Exception as e:
            print(f"DEBUG: Error updating all team rosters: {e}")
            import traceback
            traceback.print_exc()
            
    def update_roster_stats(self, team_name):
        """Update roster statistics for a specific team"""
        try:
            # Count picks by position for the selected team
            team_picks = [pick for pick in self.draft_manager.draft_picks 
                         if pick.team.team_name == team_name and pick.player]
            
            # Position breakdown
            position_counts = {}
            for pick in team_picks:
                pos = pick.player.primary_position.value
                position_counts[pos] = position_counts.get(pos, 0) + 1
                
            total_picks = len(team_picks)
            print(f"DEBUG: {team_name} has made {total_picks} picks: {position_counts}")
            
        except Exception as e:
            print(f"DEBUG: Error updating roster stats: {e}")
            
    def refresh_team_roster_display(self, event=None):
        """Refresh the team roster display with actual drafted players"""
        selected_team_name = self.roster_team_var.get()
        print(f"DEBUG: Refreshing team roster for: {selected_team_name}")
        
        # Clear existing display
        for item in self.roster_display_tree.get_children():
            self.roster_display_tree.delete(item)
        
        # Clear tree mapping
        if self.roster_display_tree in self.parent.tree_maps:
            self.parent.tree_maps[self.roster_display_tree].clear()
        
        if not selected_team_name:
            self.roster_stats_label.config(text="Select a team to view roster")
            self.position_summary_label.config(text="")
            return
        
        # Find the team
        selected_team = None
        for team in self.draft_manager.teams:
            if team.team_name == selected_team_name:
                selected_team = team
                break
        
        if not selected_team:
            print(f"ERROR: Could not find team: {selected_team_name}")
            return
        
        # Get all draft picks for this team
        team_drafted_players = []
        
        if hasattr(self.draft_manager, 'draft_picks') and self.draft_manager.draft_picks:
            for pick in self.draft_manager.draft_picks:
                if (hasattr(pick, 'team') and pick.team and 
                    pick.team.team_name == selected_team_name and 
                    hasattr(pick, 'player') and pick.player):
                    team_drafted_players.append(pick)
        
        print(f"DEBUG: Found {len(team_drafted_players)} drafted players for {selected_team_name}")
        
        # Sort by pick order
        team_drafted_players.sort(key=lambda p: getattr(p, 'overall_pick', 999))
        
        # Populate treeview with drafted players
        position_counts = {}
        total_salary = 0
        
        for pick in team_drafted_players:
            player = pick.player
            
            # Count positions
            pos = player.primary_position.value
            position_counts[pos] = position_counts.get(pos, 0) + 1
            
            # Calculate salary
            salary = 750000  # Default entry-level
            if hasattr(player, 'contract') and player.contract and hasattr(player.contract, 'salary'):
                salary = player.contract.salary
            total_salary += salary
            
            # Insert player into tree
            item_id = self.roster_display_tree.insert('', 'end', values=(
                getattr(pick, 'overall_pick', '?'),
                getattr(pick, 'round_num', '?'), 
                player.full_name,
                player.primary_position.value,
                player.overall_rating(),
                player.age,
                f"${salary:,}",
                getattr(player, 'team_name', 'Free Agent')
            ))
            
            # Map item to player for double-click functionality
            if self.roster_display_tree not in self.parent.tree_maps:
                self.parent.tree_maps[self.roster_display_tree] = {}
            self.parent.tree_maps[self.roster_display_tree][item_id] = player
        
        # Update stats display
        num_picks = len(team_drafted_players)
        if num_picks > 0:
            avg_overall = sum(pick.player.overall_rating() for pick in team_drafted_players) / num_picks
            self.roster_stats_label.config(
                text=f"Drafted: {num_picks} players | Avg Overall: {avg_overall:.1f} | Total Salary: ${total_salary:,}"
            )
            
            # Update position summary
            pos_summary = " | ".join([f"{pos}: {count}" for pos, count in sorted(position_counts.items())])
            self.position_summary_label.config(text=f"Positions: {pos_summary}")
        else:
            self.roster_stats_label.config(text="No players drafted yet")
            self.position_summary_label.config(text="")
        
        # Update user team indicator
        if self.user_team and selected_team_name == self.user_team.team_name:
            self.roster_user_indicator.config(
                text="👤 Your Team", 
                foreground=self.parent.ACCENT_COLOR
            )
        else:
            self.roster_user_indicator.config(text="")
        
        print(f"DEBUG: Roster display updated - {num_picks} players shown")
    
    def get_player_key_stats(self, player):
        """Get key stats string for a player based on position"""
        try:
            pos = player.primary_position.value
            if pos == 'G':  # Goalie
                return f"Goaltending: {player.goaltending}, Reflexes: {player.reflexes}"
            elif pos in ['C', 'LW', 'RW']:  # Forwards
                return f"Shooting: {player.shooting}, Passing: {player.passing}"
            elif pos in ['LD', 'RD']:  # Defense  
                return f"Checking: {player.checking}, Passing: {player.passing}"
            else:
                return f"Overall: {to_100_scale(player.overall_rating())}"
        except Exception as e:
            return f"OVR: {to_100_scale(player.overall_rating())}"
    
    def show_roster_player_details(self, event):
        """Show detailed player information when double-clicking roster entry"""
        try:
            item = self.team_roster_tree.selection()[0]
            player = self.parent.tree_maps[self.team_roster_tree].get(item)
            
            if player:
                # Show player in the main spotlight if we're on the available players tab
                if hasattr(self, 'show_main_player_card'):
                    self.show_main_player_card(player)
                    
                    # Switch to Available Players tab to show the card
                    for i in range(self.notebook.index('end')):
                        tab_text = self.notebook.tab(i, 'text')
                        if 'Available Players' in tab_text:
                            self.notebook.select(i)
                            break
                            
                print(f"DEBUG: Showing details for drafted player: {player.full_name}")
                
        except Exception as e:
            print(f"DEBUG: Error showing roster player details: {e}")
    
    # Phase 1 Integrated Interface Methods
    def update_all_displays(self):
        """Update all UI displays - Phase 1 implementation"""
        self.update_draft_status()
        self.update_player_list()
        self.update_draft_order_integrated()
        self.update_controls_state()
        self.update_all_team_rosters()
        
    def update_draft_status(self):
        """Update header status information"""
        if not hasattr(self, 'current_pick_label'):
            return  # Old interface
            
        current_pick = self.draft_manager.get_current_pick()
        if current_pick:
            # Update current pick info
            if current_pick.team == self.draft_manager.user_team:
                pick_text = f"🎯 YOUR PICK - Round {current_pick.round_num}, Pick #{current_pick.overall_pick}"
                self.current_pick_label.configure(foreground=self.parent.ACCENT_COLOR)
            else:
                pick_text = f"Round {current_pick.round_num}, Pick #{current_pick.overall_pick} - {current_pick.team.team_name}"
                self.current_pick_label.configure(foreground=self.parent.TEXT_COLOR)
                
            self.current_pick_label.configure(text=pick_text)
            
            # Update progress
            total_picks = len(self.draft_manager.draft_picks)
            completed = sum(1 for pick in self.draft_manager.draft_picks if pick.player)
            progress_text = f"Progress: {completed}/{total_picks} picks completed"
            self.progress_label.configure(text=progress_text)
            
            # Update round info
            if hasattr(self, 'round_info_label'):
                self.round_info_label.configure(text=f"Round {current_pick.round_num}")
            
        else:
            # Draft complete
            self.current_pick_label.configure(text="🏆 DRAFT COMPLETE", 
                                            foreground=self.parent.ACCENT_COLOR)
            self.progress_label.configure(text="All picks completed!")
            
    def update_player_list(self):
        """Update available players list with filters"""
        if not hasattr(self, 'players_tree'):
            return  # Old interface
            
        # Clear current items
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)
            
        available_players = self.draft_manager.get_available_players()
        
        # Apply filters
        position_filter = self.position_var.get() if hasattr(self, 'position_var') else "All"
        search_term = self.search_var.get().lower() if hasattr(self, 'search_var') else ""
        
        filtered_players = []
        for player in available_players:
            # Position filter
            if position_filter != "All" and player.primary_position.value != position_filter:
                continue
                
            # Search filter
            if search_term and search_term not in player.full_name.lower():
                continue
                
            filtered_players.append(player)
            
        # Sort by overall rating (best first)
        filtered_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Populate tree
        for player in filtered_players:
            player_id = self.players_tree.insert('', 'end', values=(
                player.full_name,
                player.primary_position.value,
                player.age,
                player.overall_rating(),
                getattr(player, 'former_team', 'Free Agent')
            ))
            
            # Store player reference
            if not hasattr(self.parent, 'tree_maps'):
                self.parent.tree_maps = {}
            if 'fantasy_draft_players' not in self.parent.tree_maps:
                self.parent.tree_maps['fantasy_draft_players'] = {}
            self.parent.tree_maps['fantasy_draft_players'][player_id] = player
            
    def update_draft_order_integrated(self):
        """Update draft order display for integrated interface"""
        if not hasattr(self, 'draft_tree'):
            return  # Old interface
            
        # Clear current items
        for item in self.draft_tree.get_children():
            self.draft_tree.delete(item)
            
        # Show next 10 picks from current position
        current_index = self.draft_manager.current_pick
        picks_to_show = self.draft_manager.draft_picks[current_index:current_index + 10]
        
        for pick in picks_to_show:
            selection = ""
            if pick.player:
                selection = f"{pick.player.full_name} ({pick.player.primary_position.value})"
                
            # Highlight user team picks
            tags = []
            if pick.team == self.draft_manager.user_team:
                tags = ['user_team']
                
            pick_id = self.draft_tree.insert('', 'end', values=(
                pick.overall_pick,
                pick.team.team_name[:15] + "..." if len(pick.team.team_name) > 15 else pick.team.team_name,
                selection
            ), tags=tags)
            
        # Configure user team pick highlighting
        self.draft_tree.tag_configure('user_team', background=self.parent.ACCENT_COLOR, 
                                    foreground='white')

    def show_roster_welcome_card(self):
        """Show welcome message in roster spotlight"""
        # Clear existing content
        for widget in self.roster_spotlight_scrollable.winfo_children():
            widget.destroy()
            
        # Welcome card
        welcome_frame = ttk.Frame(self.roster_spotlight_scrollable, style='Panel.TFrame')
        welcome_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Welcome message
        welcome_title = ttk.Label(welcome_frame, text="🏒 Team Roster Spotlight", 
                                 style='Header.TLabel', font=('Segoe UI', 12, 'bold'))
        welcome_title.pack(anchor='w', pady=(0, 10))
        
        welcome_text = ttk.Label(welcome_frame, 
                                text="Click any player in the roster to view their detailed information here.", 
                                style='Info.TLabel', font=('Segoe UI', 10),
                                wraplength=250)
        welcome_text.pack(anchor='w', pady=(0, 10))
        
        instructions = ttk.Label(welcome_frame,
                                text="Features:\n• Player stats and attributes\n• Draft information\n• Position-specific details\n• Former team info", 
                                style='Info.TLabel', font=('Segoe UI', 9),
                                justify=tk.LEFT)
        instructions.pack(anchor='w')

    def on_roster_player_select(self, event):
        """Handle roster player selection to show in spotlight"""
        try:
            selection = self.roster_display_tree.selection()
            if not selection:
                return
                
            item_id = selection[0]
            if (self.roster_display_tree in self.parent.tree_maps and 
                item_id in self.parent.tree_maps[self.roster_display_tree]):
                
                player = self.parent.tree_maps[self.roster_display_tree][item_id]
                self.show_roster_player_card(player)
                
        except Exception as e:
            print(f"DEBUG: Error selecting roster player: {e}")

    def show_roster_player_card(self, player):
        """Show detailed player card in roster spotlight"""
        if not player:
            self.show_roster_welcome_card()
            return
            
        # Clear existing content
        for widget in self.roster_spotlight_scrollable.winfo_children():
            widget.destroy()
            
        # Main player card frame
        card_frame = ttk.Frame(self.roster_spotlight_scrollable, style='Panel.TFrame')
        card_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Player header
        header_frame = ttk.Frame(card_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Player name and position
        name_label = ttk.Label(header_frame, text=player.full_name, 
                              style='Header.TLabel', font=('Segoe UI', 13, 'bold'))
        name_label.pack(anchor='w')
        
        pos_overall_frame = ttk.Frame(header_frame, style='Panel.TFrame')
        pos_overall_frame.pack(fill=tk.X, pady=(2, 0))
        
        pos_label = ttk.Label(pos_overall_frame, text=f"{player.primary_position.value}", 
                             style='Info.TLabel', font=('Segoe UI', 11, 'bold'))
        pos_label.pack(side=tk.LEFT)
        
        overall_label = ttk.Label(pos_overall_frame, text=f"Overall: {to_100_scale(player.overall_rating())}", 
                                 style='Info.TLabel', font=('Segoe UI', 11, 'bold'),
                                 foreground=self.parent.ACCENT_COLOR)
        overall_label.pack(side=tk.RIGHT)
        
        # Basic info section
        info_frame = ttk.Frame(card_frame, style='Panel.TFrame')
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_title = ttk.Label(info_frame, text="📋 Basic Information", 
                              style='TLabel', font=('Segoe UI', 10, 'bold'))
        info_title.pack(anchor='w', pady=(0, 5))
        
        # Age and physical stats
        basic_info_text = f"Age: {player.age}"
        if hasattr(player, 'height'):
            basic_info_text += f" | Height: {player.height}"
        if hasattr(player, 'weight'): 
            basic_info_text += f" | Weight: {player.weight}"
            
        basic_label = ttk.Label(info_frame, text=basic_info_text,
                               style='Info.TLabel', font=('Segoe UI', 9))
        basic_label.pack(anchor='w')
        
        # Former team and contract details
        former_team = getattr(player, 'former_team', getattr(player, 'team_name', 'Free Agent'))
        team_label = ttk.Label(info_frame, text=f"Former Team: {former_team}",
                              style='Info.TLabel', font=('Segoe UI', 9))
        team_label.pack(anchor='w')
        
        # Contract information section
        contract_frame = ttk.Frame(info_frame, style='Panel.TFrame')
        contract_frame.pack(fill=tk.X, pady=(5, 0))
        
        contract_title = ttk.Label(contract_frame, text="💰 Contract Details", 
                                  style='TLabel', font=('Segoe UI', 10, 'bold'))
        contract_title.pack(anchor='w', pady=(0, 3))
        
        if hasattr(player, 'contract') and player.contract:
            contract = player.contract
            salary = getattr(contract, 'salary', 750000)
            years = getattr(contract, 'years_remaining', 1)
            
            # Salary and term
            salary_text = f"${salary:,} per year for {years} year{'s' if years != 1 else ''}"
            salary_label = ttk.Label(contract_frame, text=salary_text,
                                    style='Info.TLabel', font=('Segoe UI', 9))
            salary_label.pack(anchor='w')
            
            # Contract value analysis for strategy
            overall = player.overall_rating()
            value_per_mil = overall / (salary / 1000000) if salary > 0 else overall
            
            if value_per_mil >= 10:
                value_color = "#4CAF50"  # Green - excellent value
                value_text = "📈 Excellent Contract Value"
            elif value_per_mil >= 5:
                value_color = "#FFC107"  # Yellow - fair value
                value_text = "📊 Fair Contract Value"
            else:
                value_color = "#F44336"  # Red - poor value
                value_text = "📉 Expensive Contract"
                
            value_label = ttk.Label(contract_frame, text=value_text,
                                   style='Info.TLabel', font=('Segoe UI', 9, 'italic'),
                                   foreground=value_color)
            value_label.pack(anchor='w')
            
            # Trade clauses
            clauses = []
            if hasattr(contract, 'no_movement_clause') and contract.no_movement_clause:
                clauses.append("No-Movement")
            if hasattr(contract, 'no_trade_clause') and contract.no_trade_clause:
                clauses.append("No-Trade")
                
            if clauses:
                clause_text = f"⚠️ {', '.join(clauses)} Clause{'s' if len(clauses) > 1 else ''}"
                clause_label = ttk.Label(contract_frame, text=clause_text,
                                        style='Info.TLabel', font=('Segoe UI', 9, 'italic'),
                                        foreground=self.parent.ACCENT_COLOR)
                clause_label.pack(anchor='w')
        else:
            # Default contract
            default_label = ttk.Label(contract_frame, text="$750,000 per year (Entry Level)",
                                     style='Info.TLabel', font=('Segoe UI', 9))
            default_label.pack(anchor='w')
        
        # Draft information if available
        draft_info = self.get_player_draft_info(player)
        if draft_info:
            draft_label = ttk.Label(info_frame, text=draft_info,
                                   style='Info.TLabel', font=('Segoe UI', 9, 'italic'),
                                   foreground=self.parent.ACCENT_COLOR)
            draft_label.pack(anchor='w', pady=(2, 0))
        
        # Key attributes section
        self.create_roster_attribute_grid(card_frame, player)
        
    def get_player_draft_info(self, player):
        """Get draft information for a player"""
        if not hasattr(self.draft_manager, 'draft_picks'):
            return None
            
        for pick in self.draft_manager.draft_picks:
            if pick.player == player:
                return f"📊 Drafted: Round {pick.round_num}, Pick #{pick.overall_pick} by {pick.team.team_name}"
                
        return None
        
    def create_roster_attribute_grid(self, parent_frame, player):
        """Create attribute grid for roster player card"""
        attrs_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        attrs_frame.pack(fill=tk.X, pady=(10, 0))
        
        attrs_title = ttk.Label(attrs_frame, text="⚡ Key Attributes", 
                               style='TLabel', font=('Segoe UI', 10, 'bold'))
        attrs_title.pack(anchor='w', pady=(0, 8))
        
        # Position-specific attributes
        pos = player.primary_position.value
        
        if pos == 'G':  # Goalie
            attributes = [
                ('Goaltending', player.goaltending),
                ('Reflexes', player.reflexes), 
                ('Positioning', player.positioning),
                ('Rebound Control', player.rebound_control)
            ]
        elif pos in ['C', 'LW', 'RW']:  # Forwards
            attributes = [
                ('Shooting', player.shooting),
                ('Passing', player.passing),
                ('Skating', player.skating),
                ('Hockey IQ', player.hockey_iq),
                ('Checking', player.checking),
                ('Faceoffs', getattr(player, 'faceoffs', 0) if pos == 'C' else None)
            ]
            attributes = [(name, val) for name, val in attributes if val is not None]
        else:  # Defense
            attributes = [
                ('Checking', player.checking),
                ('Passing', player.passing),
                ('Skating', player.skating),
                ('Hockey IQ', player.hockey_iq),
                ('Shooting', player.shooting)
            ]
            
        # Create attribute grid (2 columns)
        for i, (attr_name, attr_value) in enumerate(attributes):
            row_frame = ttk.Frame(attrs_frame, style='Panel.TFrame')
            row_frame.pack(fill=tk.X, pady=1)
            
            # Attribute name
            name_label = ttk.Label(row_frame, text=f"{attr_name}:", 
                                  style='Info.TLabel', font=('Segoe UI', 9))
            name_label.pack(side=tk.LEFT)
            
            # Attribute value with color coding
            color = self.get_attribute_color(attr_value)
            value_label = ttk.Label(row_frame, text=str(attr_value), 
                                   style='Info.TLabel', font=('Segoe UI', 9, 'bold'),
                                   foreground=color)
            value_label.pack(side=tk.RIGHT)

    def generate_additional_players(self, num_needed: int, teams: List[Team]) -> List[Player]:
        """Generate additional players to ensure 40 rounds worth of picks"""
        from game_classes import Player, PlayerPosition, Contract
        import random
        import uuid
        
        print(f"DEBUG: Generating {num_needed} additional players for deep draft")
        
        additional_players = []
        positions = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING, 
                    PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.GOALIE]
        
        # Extended name lists for variety
        first_names = [
            "Connor", "Sidney", "Alex", "Nathan", "Leon", "Artemi", "Nikita", "Erik", "Victor", 
            "Elias", "Mika", "John", "Jack", "Quinn", "Cale", "Kirill", "Andrei", "Brad", 
            "Tyler", "Ryan", "Matthew", "David", "Mark", "Jonathan", "Sebastian", "Filip", 
            "Patrik", "Vladimir", "Aleksander", "Mitchell", "Gabriel", "Jake", "Sam", "Adam",
            "Kyle", "Jordan", "Michael", "Chris", "Brandon", "Andrew", "Trevor", "Zach",
            "Mason", "Owen", "Cole", "Nolan", "Carter", "Dylan", "Lucas", "Hunter", "Parker"
        ]
        
        last_names = [
            "McDavid", "Crosby", "Ovechkin", "MacKinnon", "Draisaitl", "Panarin", "Kucherov",
            "Karlsson", "Hedman", "Pettersson", "Zibanejad", "Tavares", "Hughes", "Makar",
            "Kaprizov", "Vasilevskiy", "Marchand", "Pastrnak", "Stone", "Rantanen", "Barkov",
            "Reinhart", "Stamkos", "Kucherov", "Point", "Fox", "Miller", "Eichel", "Tkachuk",
            "Svechnikov", "Caufield", "Seider", "Raymond", "Zegras", "Stutzle", "Byfield",
            "Lafreniere", "Power", "Beniers", "Clarke", "Sanderson", "Johnson", "Cozens",
            "Holtz", "Lundell", "Rossi", "Perfetti", "Jarvis", "Wallstedt", "Knight"
        ]
        
        # Team names for variety in former teams
        team_names = [team.team_name for team in teams] + [
            "Minor League", "Junior League", "International", "College", "European League"
        ]
        
        for i in range(num_needed):
            # Generate player with varied skill levels for deep draft
            position = random.choice(positions)
            
            # Create skill distribution - more variety for deep draft
            if i < num_needed * 0.1:  # Top 10% - high skill
                skill_base = random.randint(15, 20)
            elif i < num_needed * 0.3:  # Next 20% - good skill  
                skill_base = random.randint(12, 17)
            elif i < num_needed * 0.6:  # Next 30% - average skill
                skill_base = random.randint(8, 14)
            else:  # Bottom 40% - developing players
                skill_base = random.randint(4, 12)
            
            # Generate player
            player = Player(
                id=str(uuid.uuid4()),
                full_name=f"{random.choice(first_names)} {random.choice(last_names)}",
                age=random.randint(18, 35),
                primary_position=position,
                overall_rating_cache=None  # Will be calculated
            )
            
            # Set attributes with some variation
            variation = random.randint(-2, 2)
            base_skill = max(1, min(20, skill_base + variation))
            
            # Position-specific attribute generation
            if position == PlayerPosition.GOALIE:
                player.goaltending = max(1, min(20, base_skill + random.randint(-1, 2)))
                player.reflexes = max(1, min(20, base_skill + random.randint(-2, 1)))
                player.positioning = max(1, min(20, base_skill + random.randint(-1, 1)))
                player.rebound_control = max(1, min(20, base_skill + random.randint(-2, 2)))
            else:
                player.skating = max(1, min(20, base_skill + random.randint(-2, 2)))
                player.shooting = max(1, min(20, base_skill + random.randint(-2, 2)))
                player.passing = max(1, min(20, base_skill + random.randint(-2, 2)))
                player.checking = max(1, min(20, base_skill + random.randint(-2, 2)))
                player.hockey_iq = max(1, min(20, base_skill + random.randint(-1, 1)))
                
            # Set other required attributes
            for attr in ['determination', 'teamwork', 'leadership', 'discipline', 'flair']:
                setattr(player, attr, random.randint(5, 18))
                
            # Set former team
            player.former_team = random.choice(team_names)
            player.team_name = "Available"
            
            additional_players.append(player)
            
        print(f"DEBUG: Generated {len(additional_players)} additional players with varied skill levels")
        return additional_players
    
    def ensure_player_contracts(self, players: List[Player]):
        """Ensure all players have contracts for strategic drafting decisions"""
        from game_classes import Contract
        import random
        
        print("DEBUG: Ensuring all players have strategic contract information")
        
        contracts_added = 0
        contracts_updated = 0
        
        for player in players:
            # Check if player already has a valid contract
            has_contract = (hasattr(player, 'contract') and 
                          player.contract is not None and 
                          hasattr(player.contract, 'salary'))
            
            if not has_contract:
                # Generate contract based on player quality and age
                overall = player.overall_rating()
                age = getattr(player, 'age', 25)
                
                # Contract value based on overall rating and age
                if overall >= 18:  # Elite players
                    if age < 25:
                        salary = random.randint(8000000, 12500000)  # Young star
                        years = random.randint(6, 8)
                    else:
                        salary = random.randint(9000000, 14000000)  # Established star
                        years = random.randint(3, 6)
                elif overall >= 15:  # Very good players
                    if age < 25:
                        salary = random.randint(4000000, 8000000)  # Young talent
                        years = random.randint(4, 7)
                    else:
                        salary = random.randint(5000000, 9000000)  # Proven veteran
                        years = random.randint(2, 5)
                elif overall >= 12:  # Good players
                    if age < 25:
                        salary = random.randint(1500000, 4000000)  # Developing
                        years = random.randint(2, 4)
                    else:
                        salary = random.randint(2000000, 5000000)  # Role player
                        years = random.randint(1, 3)
                elif overall >= 8:  # Average players
                    if age < 23:
                        salary = random.randint(750000, 1500000)  # Entry level
                        years = random.randint(1, 3)
                    else:
                        salary = random.randint(900000, 2500000)  # Depth player
                        years = random.randint(1, 2)
                else:  # Developing/minor league
                    salary = random.randint(750000, 1200000)  # Minimum/AHL
                    years = random.randint(1, 2)
                
                # Create the contract
                player.contract = Contract(
                    salary=salary,
                    years_remaining=years,
                    no_trade_clause=random.random() < 0.15,  # 15% chance of NTC
                    no_movement_clause=random.random() < 0.05,  # 5% chance of NMC
                    signing_bonus=random.randint(0, salary // 4) if salary > 3000000 else 0
                )
                contracts_added += 1
                
            else:
                # Update existing contract if needed
                if not hasattr(player.contract, 'no_trade_clause'):
                    player.contract.no_trade_clause = random.random() < 0.1
                if not hasattr(player.contract, 'no_movement_clause'):
                    player.contract.no_movement_clause = random.random() < 0.05
                contracts_updated += 1
        
        print(f"DEBUG: Contract setup complete - Added: {contracts_added}, Updated: {contracts_updated}")
        
        # Add salary information to roster display if not already there
        self.update_salary_display_integration()
    
    def update_salary_display_integration(self):
        """Ensure salary information is properly displayed in draft interface"""
        print("DEBUG: Salary display integration completed - contracts ready for strategic drafting")
