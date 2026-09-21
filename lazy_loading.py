"""
Lazy loading system for Hockey Manager
Implements on-demand loading of data to reduce memory usage and improve startup times
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import time
import threading
from abc import ABC, abstractmethod


@dataclass
class LazyLoadConfig:
    """Configuration for lazy loading behavior"""
    cache_timeout: int = 300  # 5 minutes
    max_cache_size: int = 1000  # Maximum items in cache
    preload_threshold: int = 50  # Preload if less than this many items
    background_loading: bool = True  # Enable background loading


class LazyLoader(ABC):
    """Abstract base class for lazy loading implementations"""
    
    def __init__(self, config: LazyLoadConfig = None):
        self.config = config or LazyLoadConfig()
        self.cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.loading_lock = threading.Lock()
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'loads_performed': 0,
            'background_loads': 0
        }
    
    @abstractmethod
    def _load_data(self, key: str) -> Any:
        """Load data for the given key. Must be implemented by subclasses."""
        pass
    
    def get(self, key: str) -> Any:
        """Get data, loading it lazily if not in cache"""
        current_time = time.time()
        
        # Check if data is in cache and not expired
        if (key in self.cache and 
            key in self.cache_timestamps and 
            current_time - self.cache_timestamps[key] < self.config.cache_timeout):
            self.stats['cache_hits'] += 1
            return self.cache[key]
        
        # Data not in cache or expired - load it
        self.stats['cache_misses'] += 1
        return self._load_and_cache(key)
    
    def _load_and_cache(self, key: str) -> Any:
        """Load data and store in cache"""
        with self.loading_lock:
            # Double-check pattern - another thread might have loaded it
            if key in self.cache:
                return self.cache[key]
            
            # Load the data
            data = self._load_data(key)
            self.stats['loads_performed'] += 1
            
            # Store in cache
            self._store_in_cache(key, data)
            
            return data
    
    def _store_in_cache(self, key: str, data: Any):
        """Store data in cache with size management"""
        current_time = time.time()
        
        # Remove expired entries if cache is getting full
        if len(self.cache) >= self.config.max_cache_size:
            self._cleanup_expired_entries(current_time)
        
        # If still too full, remove oldest entries
        if len(self.cache) >= self.config.max_cache_size:
            self._remove_oldest_entries()
        
        self.cache[key] = data
        self.cache_timestamps[key] = current_time
    
    def _cleanup_expired_entries(self, current_time: float):
        """Remove expired cache entries"""
        expired_keys = [
            key for key, timestamp in self.cache_timestamps.items()
            if current_time - timestamp >= self.config.cache_timeout
        ]
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.cache_timestamps.pop(key, None)
    
    def _remove_oldest_entries(self):
        """Remove oldest cache entries to make room"""
        if not self.cache_timestamps:
            return
        
        # Remove 25% of oldest entries
        num_to_remove = max(1, len(self.cache) // 4)
        oldest_keys = sorted(self.cache_timestamps.keys(), 
                           key=lambda k: self.cache_timestamps[k])[:num_to_remove]
        
        for key in oldest_keys:
            self.cache.pop(key, None)
            self.cache_timestamps.pop(key, None)
    
    def preload(self, keys: List[str]):
        """Preload data for multiple keys"""
        if self.config.background_loading:
            threading.Thread(target=self._background_preload, args=(keys,), daemon=True).start()
        else:
            for key in keys:
                self.get(key)
    
    def _background_preload(self, keys: List[str]):
        """Preload data in background thread"""
        for key in keys:
            if key not in self.cache:
                try:
                    self._load_and_cache(key)
                    self.stats['background_loads'] += 1
                except Exception as e:
                    print(f"Background loading failed for key {key}: {e}")
    
    def clear_cache(self):
        """Clear all cached data"""
        with self.loading_lock:
            self.cache.clear()
            self.cache_timestamps.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / max(1, total_requests)) * 100
        
        return {
            'cache_size': len(self.cache),
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'hit_rate': f"{hit_rate:.1f}%",
            'loads_performed': self.stats['loads_performed'],
            'background_loads': self.stats['background_loads']
        }


class PlayerStatsLoader(LazyLoader):
    """Lazy loader for player statistics"""
    
    def __init__(self, game_manager, config: LazyLoadConfig = None):
        super().__init__(config)
        self.game_manager = game_manager
    
    def _load_data(self, player_id: str) -> Dict:
        """Load player statistics on demand"""
        # This would normally load from database or calculate from game logs
        # For now, return basic stats structure
        return {
            'goals': 0,
            'assists': 0,
            'points': 0,
            'games_played': 0,
            'plus_minus': 0,
            'penalty_minutes': 0,
            'shots': 0,
            'hits': 0,
            'blocked_shots': 0,
            'last_updated': time.time()
        }


class TeamAnalyticsLoader(LazyLoader):
    """Lazy loader for team analytics and advanced stats"""
    
    def __init__(self, game_manager, config: LazyLoadConfig = None):
        super().__init__(config)
        self.game_manager = game_manager
    
    def _load_data(self, team_name: str) -> Dict:
        """Load team analytics on demand"""
        # This would calculate advanced team statistics
        return {
            'possession_percentage': 50.0,
            'shots_for_per_game': 30.0,
            'shots_against_per_game': 30.0,
            'power_play_percentage': 20.0,
            'penalty_kill_percentage': 80.0,
            'face_off_percentage': 50.0,
            'corsi_for_percentage': 50.0,
            'fenwick_for_percentage': 50.0,
            'last_updated': time.time()
        }


class GameHistoryLoader(LazyLoader):
    """Lazy loader for game history and detailed game data"""
    
    def __init__(self, game_manager, config: LazyLoadConfig = None):
        super().__init__(config)
        self.game_manager = game_manager
    
    def _load_data(self, game_id: str) -> Dict:
        """Load detailed game data on demand"""
        # This would load detailed game events, stats, etc.
        return {
            'events': [],
            'player_stats': {},
            'team_stats': {},
            'timeline': [],
            'box_score': {},
            'last_updated': time.time()
        }


class ScoutingReportLoader(LazyLoader):
    """Lazy loader for scouting reports"""
    
    def __init__(self, game_manager, config: LazyLoadConfig = None):
        super().__init__(config)
        self.game_manager = game_manager
    
    def _load_data(self, player_id: str) -> Dict:
        """Load scouting report on demand"""
        # This would generate or load detailed scouting reports
        return {
            'overall_grade': 'B',
            'skating': 7,
            'shooting': 7,
            'passing': 7,
            'hockey_iq': 7,
            'defensive_play': 7,
            'physical': 7,
            'character': 'Good',
            'ceiling': 'Top 6 Forward',
            'floor': 'Bottom 6 Forward',
            'development_timeline': '2-3 years',
            'last_updated': time.time()
        }


class LazyLoadManager:
    """Central manager for all lazy loading operations"""
    
    def __init__(self, game_manager):
        self.game_manager = game_manager
        
        # Configure lazy loading for different data types
        fast_config = LazyLoadConfig(cache_timeout=180, max_cache_size=500)  # 3 minutes, smaller cache
        standard_config = LazyLoadConfig(cache_timeout=300, max_cache_size=1000)  # 5 minutes
        long_config = LazyLoadConfig(cache_timeout=900, max_cache_size=2000)  # 15 minutes, larger cache
        
        # Initialize loaders
        self.player_stats = PlayerStatsLoader(game_manager, fast_config)
        self.team_analytics = TeamAnalyticsLoader(game_manager, standard_config)
        self.game_history = GameHistoryLoader(game_manager, long_config)
        self.scouting_reports = ScoutingReportLoader(game_manager, standard_config)
        
        self.loaders = {
            'player_stats': self.player_stats,
            'team_analytics': self.team_analytics,
            'game_history': self.game_history,
            'scouting_reports': self.scouting_reports
        }
    
    def preload_user_team_data(self, user_team_name: str):
        """Preload commonly accessed data for user's team"""
        if not user_team_name:
            return
        
        print(f"Preloading data for {user_team_name}...")
        
        # Preload team analytics
        self.team_analytics.get(user_team_name)
        
        # Preload player stats for roster (in background)
        from database_indexing import get_database_manager
        db_manager = get_database_manager()
        
        if db_manager.initialized:
            roster_players = db_manager.player_index.get_players_by_team(user_team_name)
            player_ids = [p.id for p in roster_players[:25]]  # Limit to 25 for performance
            self.player_stats.preload(player_ids)
    
    def clear_all_caches(self):
        """Clear all lazy loading caches"""
        for loader in self.loaders.values():
            loader.clear_cache()
    
    def get_performance_report(self) -> str:
        """Get performance report for all loaders"""
        report = ["Lazy Loading Performance Report:", "=" * 40]
        
        for name, loader in self.loaders.items():
            stats = loader.get_cache_stats()
            report.append(f"\n{name.replace('_', ' ').title()}:")
            report.append(f"  Cache Size: {stats['cache_size']}")
            report.append(f"  Hit Rate: {stats['hit_rate']}")
            report.append(f"  Loads Performed: {stats['loads_performed']}")
            report.append(f"  Background Loads: {stats['background_loads']}")
        
        return "\n".join(report)
    
    def optimize_memory_usage(self):
        """Optimize memory usage across all loaders"""
        print("Optimizing lazy loading memory usage...")
        
        for name, loader in self.loaders.items():
            initial_size = len(loader.cache)
            loader._cleanup_expired_entries(time.time())
            
            # If cache is still large, remove some oldest entries
            if len(loader.cache) > loader.config.max_cache_size * 0.8:
                loader._remove_oldest_entries()
            
            final_size = len(loader.cache)
            if initial_size > final_size:
                print(f"  {name}: Reduced cache from {initial_size} to {final_size} items")


# Global lazy load manager (will be initialized by game manager)
_global_lazy_manager: Optional[LazyLoadManager] = None

def get_lazy_manager() -> Optional[LazyLoadManager]:
    """Get the global lazy load manager instance"""
    return _global_lazy_manager

def initialize_lazy_manager(game_manager) -> LazyLoadManager:
    """Initialize the global lazy load manager"""
    global _global_lazy_manager
    _global_lazy_manager = LazyLoadManager(game_manager)
    return _global_lazy_manager
