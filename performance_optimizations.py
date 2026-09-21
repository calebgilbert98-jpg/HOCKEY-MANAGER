"""
Performance optimization classes for Hockey Manager
Implements caching, fast simulation, and batch processing for better performance
"""

import random
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PlayerSkillCache:
    """Pre-computed player skills to avoid repeated getattr() calls"""
    player_id: str
    
    # Offensive skills
    shooting_skill: float
    passing_skill: float
    deking_skill: float
    
    # Defensive skills
    defensive_skill: float
    checking_skill: float
    
    # Goalie skills
    goalie_skill: float
    
    # Physical attributes
    speed: float
    strength: float
    endurance: float
    
    # Overall rating
    overall_rating: int
    
    def __init__(self, player):
        self.player_id = player.id
        # Get overall rating - handle both method and attribute
        if hasattr(player, 'overall_rating'):
            if callable(player.overall_rating):
                self.overall_rating = player.overall_rating()
            else:
                self.overall_rating = player.overall_rating
        else:
            self.overall_rating = 75  # Default rating
        
        # Pre-calculate composite offensive skills
        self.shooting_skill = (
            getattr(player, 'shooting_accuracy', 10) * 0.3 +
            getattr(player, 'shooting_power', 10) * 0.25 +
            getattr(player, 'composure', 10) * 0.2 +
            getattr(player, 'vision', 10) * 0.15 +
            getattr(player, 'hockey_iq', 10) * 0.1
        )
        
        self.passing_skill = (
            getattr(player, 'passing_accuracy', 10) * 0.3 +
            getattr(player, 'passing_creativity', 10) * 0.25 +
            getattr(player, 'vision', 10) * 0.2 +
            getattr(player, 'off_the_puck', 10) * 0.15 +
            getattr(player, 'hockey_iq', 10) * 0.1
        )
        
        self.deking_skill = (
            getattr(player, 'deking', 10) * 0.4 +
            getattr(player, 'composure', 10) * 0.3 +
            getattr(player, 'agility', 10) * 0.3
        )
        
        # Pre-calculate defensive skills
        self.defensive_skill = (
            getattr(player, 'pokecheck', 10) * 0.3 +
            getattr(player, 'defensive_awareness', 10) * 0.25 +
            getattr(player, 'anticipation', 10) * 0.2 +
            getattr(player, 'positioning', 10) * 0.15 +
            getattr(player, 'hockey_iq', 10) * 0.1
        )
        
        self.checking_skill = (
            getattr(player, 'body_checking', 10) * 0.4 +
            getattr(player, 'strength', 10) * 0.3 +
            getattr(player, 'aggressiveness', 10) * 0.3
        )
        
        # Pre-calculate goalie skills
        self.goalie_skill = (
            getattr(player, 'reflexes', 10) * 0.3 +
            getattr(player, 'positioning', 10) * 0.25 +
            getattr(player, 'rebound_control', 10) * 0.2 +
            getattr(player, 'vision', 10) * 0.15 +
            getattr(player, 'composure', 10) * 0.1
        )
        
        # Physical attributes
        self.speed = getattr(player, 'speed', 10)
        self.strength = getattr(player, 'strength', 10)
        self.endurance = getattr(player, 'endurance', 10)


class GameSimulationCache:
    """Cache system for game simulation performance"""
    
    def __init__(self):
        self.player_caches: Dict[str, PlayerSkillCache] = {}
        self.team_ratings: Dict[str, float] = {}
        self.last_cache_update = 0
        self.cache_lifetime = 3600  # 1 hour
    
    def get_player_cache(self, player) -> PlayerSkillCache:
        """Get or create cached player skills"""
        if player.id not in self.player_caches:
            self.player_caches[player.id] = PlayerSkillCache(player)
        return self.player_caches[player.id]
    
    def get_team_rating(self, team) -> float:
        """Get cached team overall rating"""
        if team.team_name not in self.team_ratings:
            self.team_ratings[team.team_name] = self._calculate_team_rating(team)
        return self.team_ratings[team.team_name]
    
    def _calculate_team_rating(self, team) -> float:
        """Calculate overall team rating from player ratings"""
        if not team.roster:
            return 70.0
        
        total_rating = sum(self.get_player_cache(player).overall_rating for player in team.roster)
        return total_rating / len(team.roster)
    
    def clear_cache(self):
        """Clear all caches to free memory"""
        self.player_caches.clear()
        self.team_ratings.clear()
    
    def should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed"""
        return time.time() - self.last_cache_update > self.cache_lifetime


class FastGameSimulation:
    """Lightweight simulation for background games"""
    
    def __init__(self, home_team, away_team, cache: GameSimulationCache):
        self.home_team = home_team
        self.away_team = away_team
        self.cache = cache
    
    def run(self) -> Tuple:
        """Run fast simulation and return basic results"""
        home_rating = self.cache.get_team_rating(self.home_team)
        away_rating = self.cache.get_team_rating(self.away_team)
        
        # Simple probability calculation
        rating_diff = home_rating - away_rating
        home_advantage = 2  # Small home ice advantage
        
        home_win_prob = 0.5 + (rating_diff + home_advantage) * 0.01
        home_win_prob = max(0.1, min(0.9, home_win_prob))  # Clamp between 10-90%
        
        # Determine winner
        if random.random() < home_win_prob:
            winner = self.home_team
            loser = self.away_team
        else:
            winner = self.away_team
            loser = self.home_team
        
        # Generate realistic scores
        scores = self._generate_realistic_scores(home_rating, away_rating)
        
        # Return minimal data (no events for performance)
        return winner, loser, scores, [], []
    
    def _generate_realistic_scores(self, home_rating, away_rating) -> Tuple[int, int]:
        """Generate realistic hockey scores based on league and team quality"""
        
        # Determine league type based on team names/attributes
        league_type = self._determine_league_type()
        
        # Set base scoring parameters by league
        if league_type == "NHL":
            # NHL: Higher scoring, more skilled players
            base_goals = 3.2
            rating_multiplier = 0.08
            variance = 1.8
        elif league_type == "AHL":
            # AHL: Slightly lower than NHL
            base_goals = 2.9
            rating_multiplier = 0.07
            variance = 1.7
        elif league_type == "ECHL":
            # ECHL: Lower level, less consistent scoring
            base_goals = 2.7
            rating_multiplier = 0.06
            variance = 2.0
        elif league_type in ["SHL", "Liiga"]:
            # European leagues: Different style, moderate scoring
            base_goals = 2.8
            rating_multiplier = 0.06
            variance = 1.6
        else:
            # Default for other leagues
            base_goals = 2.8
            rating_multiplier = 0.06
            variance = 1.7
        
        # Calculate team-specific goal expectations
        home_base = base_goals + (home_rating - 75) * rating_multiplier
        away_base = base_goals + (away_rating - 75) * rating_multiplier
        
        # Add home ice advantage (about 0.1-0.2 goals)
        home_base += 0.15
        
        # Add randomness with normal distribution
        home_goals = max(0, int(home_base + random.normalvariate(0, variance)))
        away_goals = max(0, int(away_base + random.normalvariate(0, variance)))
        
        # Realistic caps (10+ goal games are rare but possible)
        home_goals = min(home_goals, 12)
        away_goals = min(away_goals, 12)
        
        return home_goals, away_goals
    
    def _determine_league_type(self) -> str:
        """Determine what league type this game is from team names"""
        # Check common NHL team indicators
        nhl_indicators = [
            'Bruins', 'Sabres', 'Red Wings', 'Panthers', 'Canadiens', 'Senators',
            'Lightning', 'Maple Leafs', 'Hurricanes', 'Blue Jackets', 'Devils',
            'Islanders', 'Rangers', 'Flyers', 'Penguins', 'Capitals', 'Blackhawks',
            'Avalanche', 'Stars', 'Wild', 'Predators', 'Blues', 'Jets', 'Ducks',
            'Flames', 'Oilers', 'Kings', 'Sharks', 'Kraken', 'Canucks', 'Golden Knights',
            'Utah Hockey Club'
        ]
        
        # Check AHL indicators
        ahl_indicators = [
            'Americans', 'Griffins', 'Checkers', 'Rocket', 'Crunch', 'Marlies',
            'Wolves', 'Monsters', 'Comets', 'Phantoms', 'Bears', 'Roadrunners',
            'IceHogs', 'Eagles', 'Admirals', 'Thunderbirds', 'Moose', 'Gulls',
            'Wranglers', 'Condors', 'Reign', 'Barracuda', 'Firebirds'
        ]
        
        # Check ECHL indicators (generic team names often used)
        echl_indicators = [
            'Storm', 'Lightning', 'Knights', 'Wolves', 'Hawks', 'Eagles',
            'Rangers', 'Tigers', 'Warriors', 'Fire'
        ]
        
        # Check European league indicators
        european_cities = [
            'Stockholm', 'Gothenburg', 'Malmo', 'Uppsala', 'Linkoping', 'Vasteras',
            'Orebro', 'Umea', 'Lulea', 'Karlstad', 'Helsingborg', 'Jonkoping',
            'Norrkoping', 'Lund', 'Helsinki', 'Tampere', 'Turku', 'Espoo',
            'Vantaa', 'Oulu', 'Jyvaskyla', 'Kuopio', 'Lahti', 'Pori', 'Rovaniemi',
            'Vaasa', 'Joensuu', 'Lappeenranta', 'Hameenlinna', 'Rauma'
        ]
        
        home_name = self.home_team.team_name
        away_name = self.away_team.team_name
        
        # Check for NHL
        if any(indicator in home_name or indicator in away_name for indicator in nhl_indicators):
            return "NHL"
        
        # Check for AHL
        if any(indicator in home_name or indicator in away_name for indicator in ahl_indicators):
            return "AHL"
        
        # Check for European leagues
        if any(city in home_name or city in away_name for city in european_cities):
            # Could be either SHL or Liiga, default to SHL
            return "SHL"
        
        # Check for ECHL (less specific, so check last)
        if any(indicator in home_name or indicator in away_name for indicator in echl_indicators):
            return "ECHL"
        
        # Default fallback
        return "Other"


class BatchProcessor:
    """Process multiple operations in batches for better performance"""
    
    def __init__(self, batch_size: int = 5):
        self.batch_size = batch_size
        self.cache = GameSimulationCache()
    
    def process_games_batch(self, games: List, user_team=None) -> List:
        """Process games in batches with fast simulation for non-user games"""
        results = []
        
        for i in range(0, len(games), self.batch_size):
            batch = games[i:i+self.batch_size]
            batch_results = []
            
            for game in batch:
                try:
                    if isinstance(game, tuple) and len(game) >= 3:
                        game_date, home_team, away_team = game[0], game[1], game[2]
                    elif isinstance(game, dict) and all(key in game for key in ['date', 'home', 'away']):
                        game_date, home_team, away_team = game['date'], game['home'], game['away']
                    else:
                        print(f"DEBUG: Unexpected batch game format: {type(game)} - {game}")
                        continue
                except (IndexError, KeyError, ValueError) as e:
                    print(f"DEBUG: Error processing batch game: {e}")
                    continue
                    
                # Use fast simulation for non-user games
                if user_team and (home_team == user_team or away_team == user_team):
                    # Full simulation for user games (will be implemented later)
                    result = self._full_simulate_game(home_team, away_team)
                else:
                    # Fast simulation for background games
                    fast_sim = FastGameSimulation(home_team, away_team, self.cache)
                    result = fast_sim.run()
                
                batch_results.append((game_date, home_team, away_team, result))
            
            results.extend(batch_results)
        
        return results
    
    def _full_simulate_game(self, home_team, away_team):
        """Placeholder for full simulation (keeps existing AdvancedGameSim for now)"""
        # This will use the existing AdvancedGameSim but with optimizations
        from main import AdvancedGameSim
        sim_engine = AdvancedGameSim(home_team, away_team)
        return sim_engine.run()
    
    def batch_update_standings(self, game_results: List, standings: Dict):
        """Update standings for all games in batch"""
        updates = {}
        
        # Collect all updates first
        for game_date, home_team, away_team, (winner, loser, scores, events, notable_events) in game_results:
            home_name = home_team.team_name
            away_name = away_team.team_name
            
            # Initialize team records if needed
            if home_name not in updates:
                updates[home_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
            if away_name not in updates:
                updates[away_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
            
            # Update based on winner
            if winner == home_team:
                updates[home_name]["W"] += 1
                updates[away_name]["L"] += 1
                updates[home_name]["Points"] += 2
            elif winner == away_team:
                updates[away_name]["W"] += 1
                updates[home_name]["L"] += 1
                updates[away_name]["Points"] += 2
            # Handle OT/SO scenarios if needed
        
        # Apply all updates to standings
        for team_name, team_updates in updates.items():
            if team_name not in standings:
                standings[team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}
            
            for stat, value in team_updates.items():
                standings[team_name][stat] += value


class PerformanceMonitor:
    """Monitor and report performance improvements"""
    
    def __init__(self):
        self.simulation_times = []
        self.batch_times = []
    
    def time_simulation(self, func, *args, **kwargs):
        """Time a simulation function"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        self.simulation_times.append(end_time - start_time)
        return result
    
    def get_average_simulation_time(self) -> float:
        """Get average simulation time"""
        if not self.simulation_times:
            return 0.0
        return sum(self.simulation_times) / len(self.simulation_times)
    
    def report_performance(self):
        """Print performance report"""
        if self.simulation_times:
            avg_time = self.get_average_simulation_time()
            total_time = sum(self.simulation_times)
            print(f"Performance Report:")
            print(f"  Total simulations: {len(self.simulation_times)}")
            print(f"  Average time per simulation: {avg_time:.3f}s")
            print(f"  Total simulation time: {total_time:.3f}s")
        else:
            print("No performance data available")


# Global cache instance
_global_cache = GameSimulationCache()

def get_global_cache() -> GameSimulationCache:
    """Get the global cache instance"""
    return _global_cache
