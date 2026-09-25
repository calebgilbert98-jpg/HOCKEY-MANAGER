# database_manager.py
# Database management system for Hockey Manager
# Handles player database initialization, team roster management, and player pool maintenance

import random
from typing import List, Dict, Optional
from game_classes import Player, PlayerPosition, Team, League, GameBalance
from player_generator import PlayerGenerator, generate_complete_database
from draft_generator import generate_draft_class

class DatabaseManager:
    """Manages the complete player database and team rosters for Hockey Manager."""
    
    def __init__(self):
        self.generator = PlayerGenerator()
        self.all_players = {}  # Dictionary of all players by ID
        self.free_agents = []
        self.prospects = []
        self.international_players = []
        self.draft_eligibles = []
        
    def initialize_database(self) -> Dict[str, List[Player]]:
        """Initialize the complete player database with all categories."""
        print("Initializing comprehensive player database...")
        
        # Generate complete database
        database = generate_complete_database()
        
        # Store references
        self.free_agents = database["free_agents"]
        self.international_players = database["international"]
        self.prospects = database["rookies"]
        
        # Create all_players dictionary
        for category, players in database.items():
            for player in players:
                self.all_players[player.id] = player
        
        print(f"Database initialized with {len(self.all_players)} total players")
        return database
    
    def populate_nhl_teams(self, teams: List[Team], nhl_players: List[Player]) -> None:
        """Populate NHL teams with realistic rosters."""
        print("Populating NHL teams with players...")
        
        # Sort players by overall rating
        nhl_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Define roster requirements per team
        roster_requirements = {
            PlayerPosition.CENTER: 4,
            PlayerPosition.LEFT_WING: 3,
            PlayerPosition.RIGHT_WING: 3,
            PlayerPosition.LEFT_DEFENSE: 3,
            PlayerPosition.RIGHT_DEFENSE: 3,
            PlayerPosition.GOALIE: 2
        }
        
        # Track assignments
        team_index = 0
        position_assignments = {team.team_name: {pos: 0 for pos in PlayerPosition} for team in teams}
        
        # First pass: snake-draft each position so talent is spread evenly
        # (round 1 goes team 1..32, round 2 goes 32..1, etc.)
        for position, required_count in roster_requirements.items():
            position_players = [p for p in nhl_players if p.primary_position == position and p.team_name == "Free Agent"]

            for pick_round in range(required_count):
                order = teams if pick_round % 2 == 0 else list(reversed(teams))
                for team in order:
                    if position_players:
                        player = position_players.pop(0)
                        player.team_name = team.team_name
                        team.add_player(player, "roster")
                        position_assignments[team.team_name][position] += 1
        
        # Second pass: Distribute remaining players
        remaining_players = [p for p in nhl_players if p.team_name == "Free Agent"]
        
        for player in remaining_players:
            # Find team with fewest players at this position
            teams_by_position_need = sorted(
                teams, 
                key=lambda t: position_assignments[t.team_name][player.primary_position]
            )
            
            target_team = teams_by_position_need[0]
            player.team_name = target_team.team_name
            
            # Determine roster level based on overall rating (50-point scale)
            overall = player.overall_rating()
            if overall >= 44:
                target_team.add_player(player, "roster")
            elif overall >= 40:
                # Some go to AHL
                if random.random() < 0.3:
                    target_team.add_player(player, "ahl")
                else:
                    target_team.add_player(player, "roster")
            else:
                target_team.add_player(player, "ahl")
            
            position_assignments[target_team.team_name][player.primary_position] += 1
            
            # If roster is getting too big, start putting players in AHL
            if len(target_team.roster) > 23:
                # Move lowest rated NHL player to AHL
                nhl_players_on_team = target_team.roster
                if nhl_players_on_team:
                    lowest_player = min(nhl_players_on_team, key=lambda p: p.overall_rating())
                    target_team.remove_player(lowest_player)
                    target_team.add_player(lowest_player, "ahl")
        
        # Add prospects to teams
        for team in teams:
            # Each team gets 8-12 prospects
            prospect_count = random.randint(8, 12)
            available_prospects = [p for p in self.prospects if p.team_name == "Free Agent"]
            
            for _ in range(min(prospect_count, len(available_prospects))):
                prospect = available_prospects.pop(0)
                prospect.team_name = team.team_name
                team.add_player(prospect, "prospects")
        
        # Generate contracts now that players are on NHL teams
        contract_gen = PlayerGenerator()
        for team in teams:
            for player in list(team.roster) + list(team.ahl_roster):
                ovr = player.overall_rating()
                if ovr >= 49:
                    tier = "NHL_ELITE"
                elif ovr >= 44:
                    tier = "NHL_STARTER"
                elif ovr >= 38:
                    tier = "NHL_DEPTH"
                else:
                    tier = "AHL_VETERAN"
                salary, years = contract_gen.determine_contract_info(player, tier)
                player.contract.salary = salary
                player.contract.years_remaining = years

        print("NHL teams populated successfully")
        self._print_roster_summary(teams)
    
    def populate_ahl_teams(self, ahl_teams: List[Team]) -> None:
        """Populate AHL teams with appropriate players."""
        print("Populating AHL teams...")
        
        # Generate AHL-specific players
        ahl_players = []
        for _ in range(len(ahl_teams) * 20):  # 20 players per AHL team
            player = self.generator.create_player(
                skill_tier=random.choice(["AHL_VETERAN", "AHL_PROSPECT"]),
                age_category=random.choice(["YOUNG", "PRIME", "VETERAN"])
            )
            ahl_players.append(player)
            self.all_players[player.id] = player
        
        # Distribute players among AHL teams
        team_index = 0
        for player in ahl_players:
            team = ahl_teams[team_index % len(ahl_teams)]
            player.team_name = team.team_name
            team.add_player(player, "roster")
            team_index += 1
        
        print(f"Populated {len(ahl_teams)} AHL teams")
    
    def generate_draft_class(self, year: int, size: int = 224) -> List[Player]:
        """Generate a new draft class for the specified year."""
        print(f"Generating {year} draft class...")
        
        draft_class = generate_draft_class(size)
        
        # Add to database
        for player in draft_class:
            self.all_players[player.id] = player
        
        self.draft_eligibles = draft_class
        return draft_class
    
    def create_free_agent_market(self, player_count: int = 100) -> List[Player]:
        """Create a robust free agent market."""
        print(f"Creating free agent market with {player_count} players...")
        
        free_agents = []
        
        # Mix of skill levels for free agents
        skill_distributions = {
            "NHL_DEPTH": 0.30,
            "AHL_VETERAN": 0.40,
            "INTERNATIONAL": 0.20,
            "JUNIOR_ELITE": 0.10
        }
        
        age_distributions = {
            "YOUNG": 0.20,
            "PRIME": 0.30,
            "VETERAN": 0.35,
            "OLDTIMER": 0.15
        }
        
        for _ in range(player_count):
            skill_tier = random.choices(
                list(skill_distributions.keys()),
                weights=list(skill_distributions.values()),
                k=1
            )[0]
            
            age_category = random.choices(
                list(age_distributions.keys()),
                weights=list(age_distributions.values()),
                k=1
            )[0]
            
            player = self.generator.create_player(
                skill_tier=skill_tier,
                age_category=age_category,
                team_name="Free Agent"
            )
            
            free_agents.append(player)
            self.all_players[player.id] = player
        
        self.free_agents.extend(free_agents)
        return free_agents
    
    def add_international_discovery_pool(self, size: int = 200) -> List[Player]:
        """Add international players that can be discovered through scouting."""
        print(f"Adding {size} international players to discovery pool...")
        
        international_players = self.generator.generate_international_players(size)
        
        for player in international_players:
            self.all_players[player.id] = player
        
        self.international_players.extend(international_players)
        return international_players
    
    def get_players_by_criteria(self, 
                               position: Optional[PlayerPosition] = None,
                               min_age: Optional[int] = None,
                               max_age: Optional[int] = None,
                               min_overall: Optional[int] = None,
                               max_overall: Optional[int] = None,
                               team_name: Optional[str] = None,
                               nationality: Optional[str] = None) -> List[Player]:
        """Get players matching specific criteria."""
        matching_players = []
        
        for player in self.all_players.values():
            # Position filter
            if position and player.primary_position != position:
                continue
            
            # Age filters
            if min_age and player.age < min_age:
                continue
            if max_age and player.age > max_age:
                continue
            
            # Overall rating filters
            if min_overall and player.overall_rating() < min_overall:
                continue
            if max_overall and player.overall_rating() > max_overall:
                continue
            
            # Team filter
            if team_name and player.team_name != team_name:
                continue
            
            # Nationality filter
            if nationality and getattr(player, 'nationality', '') != nationality:
                continue
            
            matching_players.append(player)
        
        return matching_players
    
    def get_free_agents(self) -> List[Player]:
        """Get all free agent players."""
        return [p for p in self.all_players.values() if p.team_name == "Free Agent"]
    
    def get_prospects(self) -> List[Player]:
        """Get all prospect players."""
        return self.prospects
    
    def get_international_players(self) -> List[Player]:
        """Get all international players."""
        return self.international_players
    
    def simulate_offseason_movement(self, teams: List[Team]) -> None:
        """Simulate some offseason player movement to create realistic turnover."""
        print("Simulating offseason player movement...")
        
        # Some players become free agents
        for team in teams:
            # 2-5 players per team might leave
            departing_count = random.randint(2, 5)
            
            # Prefer older, lower-rated players to leave
            candidates = []
            for player_list in [team.roster, team.ahl_roster]:
                candidates.extend(player_list)
            
            if candidates:
                # Sort by combination of age and reverse overall rating
                candidates.sort(key=lambda p: (p.age * 2) - p.overall_rating(), reverse=True)
                
                for i in range(min(departing_count, len(candidates))):
                    player = candidates[i]
                    team.remove_player(player)
                    player.team_name = "Free Agent"
                    if player not in self.free_agents:
                        self.free_agents.append(player)
        
        print("Offseason movement simulation complete")
    
    def _print_roster_summary(self, teams: List[Team]) -> None:
        """Log a one-line summary of team rosters."""
        total = sum(len(t.roster) + len(t.ahl_roster) for t in teams)
        print(f"Rosters populated: {len(teams)} teams, {total} players")
    
    def get_database_statistics(self) -> Dict[str, any]:
        """Get comprehensive database statistics."""
        stats = {
            "total_players": len(self.all_players),
            "free_agents": len(self.get_free_agents()),
            "prospects": len(self.prospects),
            "international": len(self.international_players),
            "position_distribution": {},
            "age_distribution": {},
            "nationality_distribution": {},
            "overall_distribution": {}
        }
        
        # Calculate distributions
        all_players_list = list(self.all_players.values())
        
        # Position distribution
        for position in PlayerPosition:
            count = len([p for p in all_players_list if p.primary_position == position])
            stats["position_distribution"][position.name] = count
        
        # Age distribution
        for age_range in ["18-22", "23-27", "28-32", "33-37", "38+"]:
            if age_range == "18-22":
                count = len([p for p in all_players_list if 18 <= p.age <= 22])
            elif age_range == "23-27":
                count = len([p for p in all_players_list if 23 <= p.age <= 27])
            elif age_range == "28-32":
                count = len([p for p in all_players_list if 28 <= p.age <= 32])
            elif age_range == "33-37":
                count = len([p for p in all_players_list if 33 <= p.age <= 37])
            else:  # 38+
                count = len([p for p in all_players_list if p.age >= 38])
            
            stats["age_distribution"][age_range] = count
        
        # Overall rating distribution (50-point scale)
        for rating_range in ["25-32", "33-39", "40-44", "45-49", "50+"]:
            lo, hi = {"25-32": (25, 32), "33-39": (33, 39), "40-44": (40, 44),
                      "45-49": (45, 49), "50+": (50, 99)}[rating_range]
            count = len([p for p in all_players_list if lo <= p.overall_rating() <= hi])
            stats["overall_distribution"][rating_range] = count

        return stats

# Convenience function for main game integration
def initialize_game_database(teams: List[Team]) -> DatabaseManager:
    """Initialize the complete game database with all players and populate teams."""
    print("Initializing game database...")
    
    db_manager = DatabaseManager()
    
    # Initialize player database
    database = db_manager.initialize_database()
    
    # Populate NHL teams
    db_manager.populate_nhl_teams(teams, database["nhl_players"])
    
    # Create additional free agents
    db_manager.create_free_agent_market(150)
    
    # Add international discovery pool
    db_manager.add_international_discovery_pool(300)
    
    # Generate current year draft class
    current_year = 2024
    db_manager.generate_draft_class(current_year)
    
    # Print final statistics
    stats = db_manager.get_database_statistics()
    print(f"\nDatabase initialization complete!")
    print(f"Total players: {stats['total_players']}")
    print(f"Free agents: {stats['free_agents']}")
    print(f"International players: {stats['international']}")
    print(f"Draft eligibles: {len(db_manager.draft_eligibles)}")
    
    return db_manager

# Example usage
if __name__ == "__main__":
    # Test database initialization
    from game_classes import Team
    
    # Create some test teams
    test_teams = [
        Team("Test Team 1"),
        Team("Test Team 2"),
        Team("Test Team 3")
    ]
    
    # Initialize database
    db_manager = initialize_game_database(test_teams)
    
    # Print statistics
    stats = db_manager.get_database_statistics()
    print("\nFinal Database Statistics:")
    for category, data in stats.items():
        if isinstance(data, dict):
            print(f"\n{category.replace('_', ' ').title()}:")
            for key, value in data.items():
                print(f"  {key}: {value}")
        else:
            print(f"{category.replace('_', ' ').title()}: {data}")
