"""
NHL Records System for Hockey Manager
Tracks all-time NHL records and compares current players against historical achievements
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json

@dataclass
class RecordEntry:
    """Individual record entry with player info and achievement details"""
    player_name: str
    value: int  # The record value (goals, assists, etc.)
    season: str  # Season when achieved (e.g., "1985-86")
    team: str  # Team player was on
    date_achieved: Optional[str] = None  # Specific date if available
    games_played: Optional[int] = None  # Context for rate stats
    additional_info: str = ""  # Extra context or notes

@dataclass 
class SeasonRecord:
    """Record for a single season"""
    single_season: RecordEntry
    rookie_record: Optional[RecordEntry] = None  # Best by a rookie

@dataclass
class CareerRecord:
    """Career/all-time record"""
    all_time: RecordEntry
    active_leader: Optional[RecordEntry] = None  # Current active player leader

class NHL_Records:
    """
    Comprehensive NHL records database with historical achievements
    Based on actual NHL records through 2024-25 season
    """
    
    def __init__(self):
        self.records = self._initialize_nhl_records()
        self.current_season = "2024-25"  # Will be updated by game
        
    def _initialize_nhl_records(self) -> Dict[str, Any]:
        """Initialize with actual NHL records"""
        return {
            # SKATER SINGLE SEASON RECORDS
            "single_season_goals": SeasonRecord(
                single_season=RecordEntry("Wayne Gretzky", 92, "1981-82", "Edmonton Oilers", games_played=80),
                rookie_record=RecordEntry("Teemu Selanne", 76, "1992-93", "Winnipeg Jets", games_played=84)
            ),
            "single_season_assists": SeasonRecord(
                single_season=RecordEntry("Wayne Gretzky", 163, "1985-86", "Edmonton Oilers", games_played=80),
                rookie_record=RecordEntry("Wayne Gretzky", 109, "1979-80", "Edmonton Oilers", games_played=79)
            ),
            "single_season_points": SeasonRecord(
                single_season=RecordEntry("Wayne Gretzky", 215, "1985-86", "Edmonton Oilers", games_played=80),
                rookie_record=RecordEntry("Wayne Gretzky", 137, "1979-80", "Edmonton Oilers", games_played=79)
            ),
            "single_season_plus_minus": SeasonRecord(
                single_season=RecordEntry("Larry Robinson", 120, "1976-77", "Montreal Canadiens", games_played=80)
            ),
            "single_season_pim": SeasonRecord(
                single_season=RecordEntry("Dave Schultz", 472, "1974-75", "Philadelphia Flyers", games_played=76)
            ),
            "single_season_shots": SeasonRecord(
                single_season=RecordEntry("Phil Esposito", 550, "1970-71", "Boston Bruins", games_played=78)
            ),
            
            # SKATER CAREER RECORDS  
            "career_goals": CareerRecord(
                all_time=RecordEntry("Wayne Gretzky", 894, "1979-1999", "Multiple Teams", additional_info="1,487 GP")
            ),
            "career_assists": CareerRecord(
                all_time=RecordEntry("Wayne Gretzky", 1963, "1979-1999", "Multiple Teams", additional_info="1,487 GP")
            ),
            "career_points": CareerRecord(
                all_time=RecordEntry("Wayne Gretzky", 2857, "1979-1999", "Multiple Teams", additional_info="1,487 GP")
            ),
            "career_games": CareerRecord(
                all_time=RecordEntry("Gordie Howe", 1767, "1946-1980", "Multiple Teams", additional_info="26 seasons")
            ),
            "career_pim": CareerRecord(
                all_time=RecordEntry("Tiger Williams", 3966, "1974-1988", "Multiple Teams", additional_info="962 GP")
            ),
            
            # GOALIE SINGLE SEASON RECORDS
            "single_season_wins": SeasonRecord(
                single_season=RecordEntry("Martin Brodeur", 48, "2006-07", "New Jersey Devils", games_played=78),
                rookie_record=RecordEntry("Tony Esposito", 38, "1969-70", "Chicago Blackhawks", games_played=63)
            ),
            "single_season_shutouts": SeasonRecord(
                single_season=RecordEntry("George Hainsworth", 22, "1928-29", "Montreal Canadiens", games_played=44),
                rookie_record=RecordEntry("Tony Esposito", 15, "1969-70", "Chicago Blackhawks", games_played=63)
            ),
            "single_season_saves": SeasonRecord(
                single_season=RecordEntry("Roberto Luongo", 2303, "2003-04", "Florida Panthers", games_played=72)
            ),
            "single_season_gaa": SeasonRecord(
                single_season=RecordEntry("George Hainsworth", 0.92, "1928-29", "Montreal Canadiens", games_played=44),
                rookie_record=RecordEntry("Tony Esposito", 2.17, "1969-70", "Chicago Blackhawks", games_played=63)
            ),
            "single_season_save_percentage": SeasonRecord(
                single_season=RecordEntry("Tim Thomas", 0.938, "2010-11", "Boston Bruins", games_played=57)
            ),
            
            # GOALIE CAREER RECORDS
            "career_wins": CareerRecord(
                all_time=RecordEntry("Martin Brodeur", 691, "1991-2015", "Multiple Teams", additional_info="1,266 GP")
            ),
            "career_shutouts": CareerRecord(
                all_time=RecordEntry("Martin Brodeur", 125, "1991-2015", "Multiple Teams", additional_info="1,266 GP")
            ),
            "career_saves": CareerRecord(
                all_time=RecordEntry("Martin Brodeur", 28928, "1991-2015", "Multiple Teams", additional_info="1,266 GP")
            ),
            "career_games_goalie": CareerRecord(
                all_time=RecordEntry("Martin Brodeur", 1266, "1991-2015", "Multiple Teams", additional_info="22 seasons")
            ),
            
            # TEAM RECORDS
            "team_most_wins": RecordEntry("Montreal Canadiens", 62, "1976-77", "Montreal Canadiens", games_played=80),
            "team_most_points": RecordEntry("Montreal Canadiens", 132, "1976-77", "Montreal Canadiens", games_played=80),
            "team_most_goals": RecordEntry("Edmonton Oilers", 446, "1983-84", "Edmonton Oilers", games_played=80),
            "team_fewest_losses": RecordEntry("Montreal Canadiens", 8, "1976-77", "Montreal Canadiens", games_played=80),
            
            # SPECIAL ACHIEVEMENTS
            "longest_point_streak": RecordEntry("Wayne Gretzky", 51, "1983-84", "Edmonton Oilers", additional_info="51 consecutive games"),
            "longest_goal_streak": RecordEntry("Wayne Gretzky", 16, "1981-82", "Edmonton Oilers", additional_info="16 consecutive games"),
            "fastest_goal": RecordEntry("Mike Bossy", 9, "1981-01-24", "New York Islanders", additional_info="9 seconds from start"),
            "most_hat_tricks_season": RecordEntry("Wayne Gretzky", 10, "1981-82", "Edmonton Oilers"),
            "most_hat_tricks_career": RecordEntry("Wayne Gretzky", 50, "1979-1999", "Multiple Teams"),
        }
        
    def get_record(self, record_type: str) -> Optional[Any]:
        """Get a specific record"""
        return self.records.get(record_type)
        
    def get_all_records_by_category(self, category: str) -> Dict[str, Any]:
        """Get all records in a category (single_season, career, team, special)"""
        filtered = {}
        for key, value in self.records.items():
            if category in key:
                filtered[key] = value
        return filtered
        
    def is_record_broken(self, record_type: str, value: int, player_name: str) -> bool:
        """Check if a record has been broken"""
        record = self.get_record(record_type)
        if not record:
            return False
            
        if isinstance(record, (SeasonRecord, CareerRecord)):
            current_record_value = record.single_season.value if hasattr(record, 'single_season') else record.all_time.value
        else:
            current_record_value = record.value
            
        return value > current_record_value
        
    def is_rookie_record_broken(self, record_type: str, value: int, player_name: str, is_rookie: bool) -> bool:
        """Check if a rookie record has been broken"""
        if not is_rookie:
            return False
            
        record = self.get_record(record_type)
        if not record or not hasattr(record, 'rookie_record') or not record.rookie_record:
            return False
            
        return value > record.rookie_record.value
        
    def get_record_chase_info(self, record_type: str, current_value: int) -> Dict[str, Any]:
        """Get information about how close a player is to breaking a record"""
        record = self.get_record(record_type)
        if not record:
            return {}
            
        if isinstance(record, (SeasonRecord, CareerRecord)):
            target_value = record.single_season.value if hasattr(record, 'single_season') else record.all_time.value
            record_holder = record.single_season.player_name if hasattr(record, 'single_season') else record.all_time.player_name
        else:
            target_value = record.value
            record_holder = record.player_name
            
        difference = target_value - current_value
        percentage = (current_value / target_value) * 100 if target_value > 0 else 0
        
        return {
            'target_value': target_value,
            'current_value': current_value,
            'difference': difference,
            'percentage': percentage,
            'record_holder': record_holder,
            'is_close': difference <= 5,  # Within 5 of record
            'is_very_close': difference <= 2,  # Within 2 of record
        }
        
    def add_new_record(self, record_type: str, player_name: str, value: int, season: str, team: str, **kwargs):
        """Add a new record when one is broken"""
        new_record = RecordEntry(
            player_name=player_name,
            value=value,
            season=season,
            team=team,
            date_achieved=datetime.now().strftime("%Y-%m-%d"),
            **kwargs
        )
        
        record = self.get_record(record_type)
        if isinstance(record, SeasonRecord):
            record.single_season = new_record
        elif isinstance(record, CareerRecord):
            record.all_time = new_record
        else:
            self.records[record_type] = new_record
            
    def get_top_performers_current_season(self, stat_type: str, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top performers in current season for a stat"""
        # This will be populated with actual player data from the game
        # For now, return empty list - will be implemented when integrated
        return []
        
    def format_record_display(self, record_type: str) -> str:
        """Format a record for display in UI"""
        record = self.get_record(record_type)
        if not record:
            return f"No record found for {record_type}"
            
        if isinstance(record, SeasonRecord):
            r = record.single_season
            result = f"{r.player_name}: {r.value} ({r.season}, {r.team})"
            if record.rookie_record:
                rr = record.rookie_record
                result += f"\n  Rookie: {rr.player_name}: {rr.value} ({rr.season}, {rr.team})"
        elif isinstance(record, CareerRecord):
            r = record.all_time
            result = f"{r.player_name}: {r.value} ({r.season}, {r.team})"
            if r.additional_info:
                result += f" - {r.additional_info}"
        else:
            result = f"{record.player_name}: {record.value} ({record.season}, {record.team})"
            if record.additional_info:
                result += f" - {record.additional_info}"
                
        return result
        
    def save_records_to_file(self, filename: str = "nhl_records.json"):
        """Save current records to file for persistence"""
        # Convert records to JSON-serializable format
        serializable_records = {}
        for key, value in self.records.items():
            if isinstance(value, (SeasonRecord, CareerRecord)):
                serializable_records[key] = {
                    'type': type(value).__name__,
                    'data': value.__dict__
                }
            else:
                serializable_records[key] = {
                    'type': 'RecordEntry',
                    'data': value.__dict__
                }
                
        with open(filename, 'w') as f:
            json.dump(serializable_records, f, indent=2)
            
    def load_records_from_file(self, filename: str = "nhl_records.json"):
        """Load records from file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            # Reconstruct records from JSON
            for key, value in data.items():
                record_type = value['type']
                record_data = value['data']
                
                if record_type == 'SeasonRecord':
                    self.records[key] = SeasonRecord(**record_data)
                elif record_type == 'CareerRecord':
                    self.records[key] = CareerRecord(**record_data)
                else:
                    self.records[key] = RecordEntry(**record_data)
                    
        except FileNotFoundError:
            print(f"Records file {filename} not found, using default records")
        except Exception as e:
            print(f"Error loading records: {e}, using default records")

@dataclass
class PlayerStatTracker:
    """Tracks individual player statistics for record comparison"""
    player_id: str
    player_name: str
    
    # Current season stats
    season_goals: int = 0
    season_assists: int = 0
    season_points: int = 0
    season_games: int = 0
    season_pim: int = 0
    season_plus_minus: int = 0
    season_shots: int = 0
    
    # Goalie specific season stats
    season_wins: int = 0
    season_losses: int = 0
    season_shutouts: int = 0
    season_saves: int = 0
    season_goals_against: int = 0
    season_shots_against: int = 0
    
    # Career stats
    career_goals: int = 0
    career_assists: int = 0
    career_points: int = 0
    career_games: int = 0
    career_pim: int = 0
    
    # Goalie career stats
    career_wins: int = 0
    career_shutouts: int = 0
    career_saves: int = 0
    career_goals_against: int = 0
    career_games_goalie: int = 0
    
    # Streaks and achievements
    current_point_streak: int = 0
    current_goal_streak: int = 0
    longest_point_streak: int = 0
    longest_goal_streak: int = 0
    hat_tricks_season: int = 0
    hat_tricks_career: int = 0
    
    # Meta information
    is_rookie: bool = False
    team_name: str = ""
    seasons_played: int = 0
    
    def add_game_stats(self, goals: int = 0, assists: int = 0, pim: int = 0, plus_minus: int = 0, 
                      shots: int = 0, wins: int = 0, saves: int = 0, goals_against: int = 0, 
                      shots_against: int = 0, shutout: bool = False):
        """Add stats from a single game"""
        # Skater stats
        self.season_goals += goals
        self.season_assists += assists
        self.season_points += goals + assists
        self.season_games += 1
        self.season_pim += pim
        self.season_plus_minus += plus_minus
        self.season_shots += shots
        
        # Career stats
        self.career_goals += goals
        self.career_assists += assists
        self.career_points += goals + assists
        self.career_games += 1
        self.career_pim += pim
        
        # Goalie stats
        if wins > 0:
            self.season_wins += wins
            self.career_wins += wins
        if shutout:
            self.season_shutouts += 1
            self.career_shutouts += 1
        self.season_saves += saves
        self.season_goals_against += goals_against
        self.season_shots_against += shots_against
        self.career_saves += saves
        self.career_goals_against += goals_against
        if saves > 0 or goals_against > 0:  # Only count goalie games
            self.career_games_goalie += 1
            
        # Handle streaks
        if goals + assists > 0:
            self.current_point_streak += 1
            self.longest_point_streak = max(self.longest_point_streak, self.current_point_streak)
        else:
            self.current_point_streak = 0
            
        if goals > 0:
            self.current_goal_streak += 1
            self.longest_goal_streak = max(self.longest_goal_streak, self.current_goal_streak)
        else:
            self.current_goal_streak = 0
            
        # Track hat tricks
        if goals >= 3:
            self.hat_tricks_season += 1
            self.hat_tricks_career += 1
            
    def reset_season_stats(self):
        """Reset season stats for new season"""
        self.season_goals = 0
        self.season_assists = 0
        self.season_points = 0
        self.season_games = 0
        self.season_pim = 0
        self.season_plus_minus = 0
        self.season_shots = 0
        self.season_wins = 0
        self.season_losses = 0
        self.season_shutouts = 0
        self.season_saves = 0
        self.season_goals_against = 0
        self.season_shots_against = 0
        self.hat_tricks_season = 0
        self.current_point_streak = 0
        self.current_goal_streak = 0
        self.seasons_played += 1
        self.is_rookie = (self.seasons_played == 1)
        
    def get_gaa(self) -> float:
        """Calculate goals against average"""
        if self.career_games_goalie == 0:
            return 0.0
        return (self.career_goals_against / self.career_games_goalie)
        
    def get_season_gaa(self) -> float:
        """Calculate season goals against average"""
        games = max(self.season_wins + self.season_losses, 1)
        return (self.season_goals_against / games)
        
    def get_save_percentage(self) -> float:
        """Calculate career save percentage"""
        total_shots = self.career_saves + self.career_goals_against
        if total_shots == 0:
            return 0.0
        return self.career_saves / total_shots
        
    def get_season_save_percentage(self) -> float:
        """Calculate season save percentage"""
        if self.season_shots_against == 0:
            return 0.0
        return self.season_saves / self.season_shots_against

class RecordManager:
    """Manages record tracking and notifications for the game"""
    
    def __init__(self):
        self.nhl_records = NHL_Records()
        self.player_trackers: Dict[str, PlayerStatTracker] = {}
        self.recent_records_broken: List[Dict[str, Any]] = []
        
    def get_or_create_tracker(self, player_id: str, player_name: str, team_name: str = "", is_rookie: bool = False) -> PlayerStatTracker:
        """Get existing tracker or create new one for player"""
        if player_id not in self.player_trackers:
            self.player_trackers[player_id] = PlayerStatTracker(
                player_id=player_id,
                player_name=player_name,
                team_name=team_name,
                is_rookie=is_rookie
            )
        return self.player_trackers[player_id]
        
    def update_player_stats(self, player_id: str, **stats):
        """Update player stats and check for records"""
        if player_id not in self.player_trackers:
            return
            
        tracker = self.player_trackers[player_id]
        tracker.add_game_stats(**stats)
        
        # Check for record breaks
        self._check_for_records(tracker)
        
    def _check_for_records(self, tracker: PlayerStatTracker):
        """Check if player has broken any records"""
        records_to_check = [
            ('single_season_goals', tracker.season_goals),
            ('single_season_assists', tracker.season_assists),
            ('single_season_points', tracker.season_points),
            ('career_goals', tracker.career_goals),
            ('career_assists', tracker.career_assists),
            ('career_points', tracker.career_points),
            ('longest_point_streak', tracker.current_point_streak),
            ('longest_goal_streak', tracker.current_goal_streak),
            ('most_hat_tricks_season', tracker.hat_tricks_season),
            ('most_hat_tricks_career', tracker.hat_tricks_career),
        ]
        
        # Goalie records
        if tracker.career_games_goalie > 0:
            records_to_check.extend([
                ('single_season_wins', tracker.season_wins),
                ('single_season_shutouts', tracker.season_shutouts),
                ('career_wins', tracker.career_wins),
                ('career_shutouts', tracker.career_shutouts),
            ])
            
        for record_type, value in records_to_check:
            if self.nhl_records.is_record_broken(record_type, value, tracker.player_name):
                self._record_broken(tracker, record_type, value)
                
            # Check rookie records
            if tracker.is_rookie and self.nhl_records.is_rookie_record_broken(record_type, value, tracker.player_name, True):
                self._rookie_record_broken(tracker, record_type, value)
                
    def _record_broken(self, tracker: PlayerStatTracker, record_type: str, value: int):
        """Handle when a record is broken"""
        record_info = {
            'player_name': tracker.player_name,
            'player_id': tracker.player_id,
            'record_type': record_type,
            'new_value': value,
            'team': tracker.team_name,
            'season': self.nhl_records.current_season,
            'is_rookie_record': False,
            'timestamp': datetime.now().isoformat()
        }
        
        self.recent_records_broken.append(record_info)
        
        # Update the official record
        self.nhl_records.add_new_record(
            record_type=record_type,
            player_name=tracker.player_name,
            value=value,
            season=self.nhl_records.current_season,
            team=tracker.team_name
        )
        
        print(f"🏆 RECORD BROKEN! {tracker.player_name} sets new {record_type.replace('_', ' ').title()} record with {value}!")
        
    def _rookie_record_broken(self, tracker: PlayerStatTracker, record_type: str, value: int):
        """Handle when a rookie record is broken"""
        record_info = {
            'player_name': tracker.player_name,
            'player_id': tracker.player_id,
            'record_type': record_type,
            'new_value': value,
            'team': tracker.team_name,
            'season': self.nhl_records.current_season,
            'is_rookie_record': True,
            'timestamp': datetime.now().isoformat()
        }
        
        self.recent_records_broken.append(record_info)
        print(f"🌟 ROOKIE RECORD! {tracker.player_name} sets new rookie {record_type.replace('_', ' ').title()} record with {value}!")
        
    def get_record_chase_leaders(self, record_type: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Get players closest to breaking a specific record"""
        leaders = []
        
        for tracker in self.player_trackers.values():
            if record_type == 'single_season_goals':
                current_value = tracker.season_goals
            elif record_type == 'single_season_assists':
                current_value = tracker.season_assists
            elif record_type == 'single_season_points':
                current_value = tracker.season_points
            elif record_type == 'career_goals':
                current_value = tracker.career_goals
            elif record_type == 'career_assists':
                current_value = tracker.career_assists
            elif record_type == 'career_points':
                current_value = tracker.career_points
            else:
                continue
                
            chase_info = self.nhl_records.get_record_chase_info(record_type, current_value)
            if chase_info and current_value > 0:
                leaders.append((tracker.player_name, chase_info))
                
        # Sort by percentage of record achieved
        leaders.sort(key=lambda x: x[1]['percentage'], reverse=True)
        return leaders[:10]  # Top 10
        
    def get_recent_records(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recently broken records"""
        return self.recent_records_broken[-limit:] if self.recent_records_broken else []
        
    def save_state(self, filename: str = "record_manager_state.json"):
        """Save current state to file"""
        state = {
            'player_trackers': {pid: tracker.__dict__ for pid, tracker in self.player_trackers.items()},
            'recent_records_broken': self.recent_records_broken
        }
        
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2)
            
        self.nhl_records.save_records_to_file()
        
    def load_state(self, filename: str = "record_manager_state.json"):
        """Load state from file"""
        try:
            with open(filename, 'r') as f:
                state = json.load(f)
                
            # Reconstruct player trackers
            for pid, tracker_data in state.get('player_trackers', {}).items():
                self.player_trackers[pid] = PlayerStatTracker(**tracker_data)
                
            self.recent_records_broken = state.get('recent_records_broken', [])
            self.nhl_records.load_records_from_file()
            
        except FileNotFoundError:
            print(f"State file {filename} not found, starting fresh")
        except Exception as e:
            print(f"Error loading state: {e}, starting fresh")