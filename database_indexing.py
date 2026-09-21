"""
Database indexing and lookup optimization for Hockey Manager
Implements fast lookup tables and indexing for large datasets
"""

from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
import time
from game_classes import Player, Team, PlayerPosition


class PlayerIndex:
    """Advanced indexing system for fast player lookups"""
    
    def __init__(self):
        self.by_id: Dict[str, Player] = {}
        self.by_position: Dict[PlayerPosition, List[Player]] = defaultdict(list)
        self.by_team: Dict[str, List[Player]] = defaultdict(list)
        self.by_age_range: Dict[Tuple[int, int], List[Player]] = defaultdict(list)
        self.by_rating_range: Dict[Tuple[int, int], List[Player]] = defaultdict(list)
        self.by_name: Dict[str, List[Player]] = defaultdict(list)
        self.free_agents: Set[str] = set()
        self.rookies: Set[str] = set()
        self.veterans: Set[str] = set()
        
        # Performance tracking
        self.last_rebuild = 0
        self.lookup_stats = {
            'total_lookups': 0,
            'cache_hits': 0,
            'index_rebuilds': 0
        }
    
    def add_player(self, player: Player):
        """Add a player to all relevant indexes"""
        # Primary key index
        self.by_id[player.id] = player
        
        # Position index
        if hasattr(player, 'primary_position') and player.primary_position:
            self.by_position[player.primary_position].append(player)
        
        # Team index
        team_name = getattr(player, 'team_name', 'Free Agent')
        self.by_team[team_name].append(player)
        
        # Age range index (groups of 5 years)
        age = getattr(player, 'age', 25)
        age_range = (age // 5 * 5, age // 5 * 5 + 4)
        self.by_age_range[age_range].append(player)
        
        # Rating range index (groups of 10 points)
        try:
            rating = player.overall_rating() if callable(player.overall_rating) else player.overall_rating
        except:
            rating = 75
        rating_range = (rating // 10 * 10, rating // 10 * 10 + 9)
        self.by_rating_range[rating_range].append(player)
        
        # Name index for search
        full_name = f"{player.first_name} {player.last_name}".lower()
        self.by_name[full_name].append(player)
        
        # Special categories
        if team_name == 'Free Agent':
            self.free_agents.add(player.id)
        
        if age <= 22:
            self.rookies.add(player.id)
        elif age >= 32:
            self.veterans.add(player.id)
    
    def remove_player(self, player_id: str):
        """Remove a player from all indexes"""
        if player_id not in self.by_id:
            return
            
        player = self.by_id[player_id]
        
        # Remove from all indexes
        del self.by_id[player_id]
        
        if hasattr(player, 'primary_position') and player.primary_position:
            if player in self.by_position[player.primary_position]:
                self.by_position[player.primary_position].remove(player)
        
        team_name = getattr(player, 'team_name', 'Free Agent')
        if player in self.by_team[team_name]:
            self.by_team[team_name].remove(player)
        
        # Remove from special categories
        self.free_agents.discard(player_id)
        self.rookies.discard(player_id)
        self.veterans.discard(player_id)
    
    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """Fast O(1) player lookup by ID"""
        self.lookup_stats['total_lookups'] += 1
        if player_id in self.by_id:
            self.lookup_stats['cache_hits'] += 1
            return self.by_id[player_id]
        return None
    
    def get_players_by_position(self, position: PlayerPosition) -> List[Player]:
        """Get all players of a specific position"""
        self.lookup_stats['total_lookups'] += 1
        return self.by_position.get(position, [])
    
    def get_players_by_team(self, team_name: str) -> List[Player]:
        """Get all players on a specific team"""
        self.lookup_stats['total_lookups'] += 1
        return self.by_team.get(team_name, [])
    
    def get_free_agents(self) -> List[Player]:
        """Get all free agent players"""
        self.lookup_stats['total_lookups'] += 1
        return [self.by_id[pid] for pid in self.free_agents if pid in self.by_id]
    
    def get_players_by_age_range(self, min_age: int, max_age: int) -> List[Player]:
        """Get players within an age range"""
        self.lookup_stats['total_lookups'] += 1
        result = []
        for (range_min, range_max), players in self.by_age_range.items():
            if range_max >= min_age and range_min <= max_age:
                result.extend([p for p in players if min_age <= getattr(p, 'age', 25) <= max_age])
        return result
    
    def get_players_by_rating_range(self, min_rating: int, max_rating: int) -> List[Player]:
        """Get players within a rating range"""
        self.lookup_stats['total_lookups'] += 1
        result = []
        for (range_min, range_max), players in self.by_rating_range.items():
            if range_max >= min_rating and range_min <= max_rating:
                for player in players:
                    try:
                        rating = player.overall_rating() if callable(player.overall_rating) else player.overall_rating
                        if min_rating <= rating <= max_rating:
                            result.append(player)
                    except:
                        continue
        return result
    
    def search_players_by_name(self, name_query: str) -> List[Player]:
        """Search players by name (partial matching)"""
        self.lookup_stats['total_lookups'] += 1
        name_query = name_query.lower()
        result = []
        
        for full_name, players in self.by_name.items():
            if name_query in full_name:
                result.extend(players)
        
        return result
    
    def rebuild_index(self, all_players: List[Player]):
        """Rebuild the entire index from scratch"""
        self.lookup_stats['index_rebuilds'] += 1
        self.clear()
        
        for player in all_players:
            self.add_player(player)
        
        self.last_rebuild = time.time()
    
    def clear(self):
        """Clear all indexes"""
        self.by_id.clear()
        self.by_position.clear()
        self.by_team.clear()
        self.by_age_range.clear()
        self.by_rating_range.clear()
        self.by_name.clear()
        self.free_agents.clear()
        self.rookies.clear()
        self.veterans.clear()
    
    def get_stats(self) -> Dict:
        """Get performance statistics"""
        hit_rate = (self.lookup_stats['cache_hits'] / max(1, self.lookup_stats['total_lookups'])) * 100
        return {
            'total_players': len(self.by_id),
            'total_lookups': self.lookup_stats['total_lookups'],
            'cache_hit_rate': f"{hit_rate:.1f}%",
            'index_rebuilds': self.lookup_stats['index_rebuilds'],
            'free_agents': len(self.free_agents),
            'rookies': len(self.rookies),
            'veterans': len(self.veterans)
        }


class TeamIndex:
    """Fast indexing system for team lookups"""
    
    def __init__(self):
        self.by_name: Dict[str, Team] = {}
        self.by_division: Dict[str, List[Team]] = defaultdict(list)
        self.by_conference: Dict[str, List[Team]] = defaultdict(list)
        self.by_city: Dict[str, List[Team]] = defaultdict(list)
        
        # Performance tracking
        self.lookup_stats = {
            'total_lookups': 0,
            'cache_hits': 0
        }
    
    def add_team(self, team: Team):
        """Add a team to all relevant indexes"""
        self.by_name[team.team_name] = team
        
        if hasattr(team, 'division') and team.division:
            self.by_division[team.division].append(team)
        
        if hasattr(team, 'conference') and team.conference:
            self.by_conference[team.conference].append(team)
        
        if hasattr(team, 'city') and team.city:
            self.by_city[team.city].append(team)
    
    def get_team_by_name(self, team_name: str) -> Optional[Team]:
        """Fast O(1) team lookup by name"""
        self.lookup_stats['total_lookups'] += 1
        if team_name in self.by_name:
            self.lookup_stats['cache_hits'] += 1
            return self.by_name[team_name]
        return None
    
    def get_teams_by_division(self, division: str) -> List[Team]:
        """Get all teams in a division"""
        self.lookup_stats['total_lookups'] += 1
        return self.by_division.get(division, [])
    
    def get_teams_by_conference(self, conference: str) -> List[Team]:
        """Get all teams in a conference"""
        self.lookup_stats['total_lookups'] += 1
        return self.by_conference.get(conference, [])
    
    def rebuild_index(self, all_teams: List[Team]):
        """Rebuild the entire index from scratch"""
        self.clear()
        for team in all_teams:
            self.add_team(team)
    
    def clear(self):
        """Clear all indexes"""
        self.by_name.clear()
        self.by_division.clear()
        self.by_conference.clear()
        self.by_city.clear()
    
    def get_stats(self) -> Dict:
        """Get performance statistics"""
        hit_rate = (self.lookup_stats['cache_hits'] / max(1, self.lookup_stats['total_lookups'])) * 100
        return {
            'total_teams': len(self.by_name),
            'total_lookups': self.lookup_stats['total_lookups'],
            'cache_hit_rate': f"{hit_rate:.1f}%"
        }


class DatabaseManager:
    """Centralized database management with advanced indexing"""
    
    def __init__(self):
        self.player_index = PlayerIndex()
        self.team_index = TeamIndex()
        self.initialized = False
        self.last_optimization = 0
        
    def initialize(self, league):
        """Initialize indexes from league data"""
        print("Initializing database indexes...")
        start_time = time.time()
        
        # Index all teams
        if hasattr(league, 'teams') and league.teams:
            self.team_index.rebuild_index(league.teams)
        
        # Index all players from all teams
        all_players = []
        if hasattr(league, 'teams') and league.teams:
            for team in league.teams:
                if hasattr(team, 'roster') and team.roster:
                    all_players.extend(team.roster)
                if hasattr(team, 'ahl_roster') and team.ahl_roster:
                    all_players.extend(team.ahl_roster)
                if hasattr(team, 'prospects') and team.prospects:
                    all_players.extend(team.prospects)
        
        # Add free agents if they exist
        if hasattr(league, 'free_agents') and league.free_agents:
            all_players.extend(league.free_agents)
        
        self.player_index.rebuild_index(all_players)
        
        self.initialized = True
        init_time = time.time() - start_time
        
        print(f"Database indexing complete in {init_time:.2f} seconds")
        print(f"Indexed {len(all_players)} players and {len(league.teams) if hasattr(league, 'teams') else 0} teams")
        
        return init_time
    
    def optimize_performance(self):
        """Run performance optimizations"""
        if not self.initialized:
            return
            
        current_time = time.time()
        
        # Only optimize once every 5 minutes to avoid overhead
        if current_time - self.last_optimization < 300:
            return
        
        print("Running database performance optimization...")
        
        # Clear unused index entries
        self._cleanup_stale_references()
        
        self.last_optimization = current_time
        print("Database optimization complete")
    
    def _cleanup_stale_references(self):
        """Remove stale references from indexes"""
        # Remove players that no longer exist
        stale_player_ids = []
        for player_id, player in self.player_index.by_id.items():
            if not hasattr(player, 'id') or player.id != player_id:
                stale_player_ids.append(player_id)
        
        for player_id in stale_player_ids:
            self.player_index.remove_player(player_id)
    
    def get_performance_report(self) -> str:
        """Get a detailed performance report"""
        if not self.initialized:
            return "Database not initialized"
        
        player_stats = self.player_index.get_stats()
        team_stats = self.team_index.get_stats()
        
        report = f"""
Database Performance Report:
==========================

Player Index:
- Total Players: {player_stats['total_players']}
- Total Lookups: {player_stats['total_lookups']}
- Cache Hit Rate: {player_stats['cache_hit_rate']}
- Free Agents: {player_stats['free_agents']}
- Rookies: {player_stats['rookies']}
- Veterans: {player_stats['veterans']}

Team Index:
- Total Teams: {team_stats['total_teams']}
- Total Lookups: {team_stats['total_lookups']}
- Cache Hit Rate: {team_stats['cache_hit_rate']}

Status: {'Optimized' if self.initialized else 'Not Initialized'}
        """
        
        return report


# Global database manager instance
_global_db_manager = DatabaseManager()

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    return _global_db_manager
