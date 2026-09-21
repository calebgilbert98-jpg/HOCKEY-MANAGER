"""
New Schedule System - Core Data Structures

This module defines the standardized data structures for the new 
scheduling and calendar system. All components use these immutable data 
structures to ensure consistency and prevent accidental modifications.
"""

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

# Forward reference for Team to avoid circular imports
if TYPE_CHECKING:
    from game_classes import Team

# ===== ENUMERATIONS =====

class EventType(Enum):
    """All possible calendar event types."""
    # Game events
    NHL_GAME = "nhl_game"
    AHL_GAME = "ahl_game"
    
    # Special events
    ALL_STAR = "all_star"
    ALL_STAR_SKILLS = "all_star_skills"
    TRADE_DEADLINE = "trade_deadline"
    DRAFT = "draft" 
    FREE_AGENCY = "free_agency"
    
    # Schedule events
    BREAK_DAY = "break_day"
    SEASON_START = "season_start"
    SEASON_END = "season_end"
    PLAYOFFS_START = "playoffs_start"


class ImportanceLevel(Enum):
    """Importance levels for events."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# ===== CORE DATA STRUCTURES =====

@dataclass(frozen=True)
class CalendarEvent:
    """
    Immutable base class for all calendar events.
    
    This is the foundation of the new system - every event (game, special event,
    etc.) inherits from this class to ensure consistency.
    """
    event_id: str
    date: date
    event_type: EventType
    title: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate event data on creation."""
        if not self.event_id:
            raise ValueError("Event ID cannot be empty")
        if not self.title:
            raise ValueError("Event title cannot be empty")
        if not isinstance(self.date, date):
            raise ValueError("Date must be a date object")
        if not isinstance(self.event_type, EventType):
            raise ValueError("Event type must be an EventType enum")


@dataclass(frozen=True)
class GameEvent(CalendarEvent):
    """
    Specialized event for hockey games.
    
    This handles all game-specific logic and validation while inheriting
    the base event structure.
    """
    home_team: 'Team'
    away_team: 'Team'
    game_time: time
    league: str
    venue: str = ""
    
    def __init__(self, event_id: str, date: date, event_type: EventType, title: str, 
                 description: str, home_team: 'Team', away_team: 'Team', 
                 game_time: time, league: str, venue: str = "", metadata: Dict[str, Any] = None):
        if metadata is None:
            metadata = {}
        object.__setattr__(self, 'event_id', event_id)
        object.__setattr__(self, 'date', date)
        object.__setattr__(self, 'event_type', event_type)
        object.__setattr__(self, 'title', title)
        object.__setattr__(self, 'description', description)
        object.__setattr__(self, 'metadata', metadata)
        object.__setattr__(self, 'home_team', home_team)
        object.__setattr__(self, 'away_team', away_team)
        object.__setattr__(self, 'game_time', game_time)
        object.__setattr__(self, 'league', league)
        object.__setattr__(self, 'venue', venue)
        self.__post_init__()
    
    def __post_init__(self):
        super().__post_init__()
        if self.home_team.team_name == self.away_team.team_name:
            raise ValueError("Home and away teams must be different")
        if self.event_type not in [EventType.NHL_GAME, EventType.AHL_GAME]:
            raise ValueError(f"Invalid game event type: {self.event_type}")
        if not isinstance(self.game_time, time):
            raise ValueError("Game time must be a time object")
    
    def is_user_team_game(self, user_team: 'Team') -> bool:
        """Check if this game involves the user's team."""
        return (self.home_team.team_name == user_team.team_name or 
                self.away_team.team_name == user_team.team_name)
    
    def is_home_game_for_team(self, team: 'Team') -> bool:
        """Check if this is a home game for the specified team."""
        return self.home_team.team_name == team.team_name
    
    def get_opponent(self, team: 'Team') -> Optional['Team']:
        """Get the opponent for the specified team."""
        if self.home_team.team_name == team.team_name:
            return self.away_team
        elif self.away_team.team_name == team.team_name:
            return self.home_team
        else:
            return None


@dataclass(frozen=True)
class SpecialEvent(CalendarEvent):
    """
    Special NHL events like All-Star, Draft, etc.
    
    These events affect the calendar but aren't games.
    """
    importance_level: ImportanceLevel
    affects_schedule: bool = False
    
    def __post_init__(self):
        super().__post_init__()
        special_types = [
            EventType.ALL_STAR, EventType.ALL_STAR_SKILLS,
            EventType.TRADE_DEADLINE, EventType.DRAFT, 
            EventType.FREE_AGENCY, EventType.BREAK_DAY,
            EventType.SEASON_START, EventType.SEASON_END,
            EventType.PLAYOFFS_START
        ]
        if self.event_type not in special_types:
            raise ValueError(f"Invalid special event type: {self.event_type}")
        if not isinstance(self.importance_level, ImportanceLevel):
            raise ValueError("Importance level must be an ImportanceLevel enum")


# ===== VALIDATION STRUCTURES =====

@dataclass
class ValidationResult:
    """Results of schedule validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str):
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a validation warning."""
        self.warnings.append(warning)


@dataclass
class TeamScheduleStats:
    """Statistics for a team's schedule."""
    team_name: str
    total_games: int
    home_games: int
    away_games: int
    back_to_backs: int
    consecutive_games_max: int
    monthly_distribution: Dict[int, int] = field(default_factory=dict)
    
    @property
    def is_valid_game_count(self) -> bool:
        """Check if team has correct number of games (82 for NHL)."""
        return self.total_games == 82
    
    @property
    def is_balanced_home_away(self) -> bool:
        """Check if home/away split is reasonable (41/41 for NHL)."""
        return abs(self.home_games - self.away_games) <= 1


# ===== EXCEPTIONS =====

class ScheduleError(Exception):
    """Base exception for scheduling errors."""
    pass


class ScheduleValidationError(ScheduleError):
    """Raised when schedule fails validation."""
    def __init__(self, validation_errors: List[str]):
        self.validation_errors = validation_errors
        super().__init__(f"Schedule validation failed: {'; '.join(validation_errors)}")


class EventConflictError(ScheduleError):
    """Raised when events conflict (e.g., team has multiple games on same day)."""
    pass


class TeamScheduleError(ScheduleError):
    """Raised for team-specific scheduling issues."""
    pass


# ===== INTERFACES =====

class IScheduleEngine(ABC):
    """Interface for schedule generation engines."""
    
    @abstractmethod
    def generate_schedule(self, teams: List['Team'], season_year: int) -> List[CalendarEvent]:
        """Generate schedule for given teams and season."""
        pass
    
    @abstractmethod  
    def validate_constraints(self, events: List[CalendarEvent]) -> ValidationResult:
        """Validate generated schedule meets all constraints."""
        pass


class ICalendarManager(ABC):
    """Interface for calendar event management."""
    
    @abstractmethod
    def add_events(self, events: List[CalendarEvent]):
        """Add multiple events to calendar."""
        pass
    
    @abstractmethod
    def get_events_for_date(self, target_date: date) -> List[CalendarEvent]:
        """Get all events for a specific date."""
        pass
    
    @abstractmethod
    def get_events_for_month(self, month: int, year: int) -> Dict[date, List[CalendarEvent]]:
        """Get all events for a specific month."""
        pass


class IScheduleValidator(ABC):
    """Interface for schedule validation."""
    
    @abstractmethod
    def validate_schedule(self, events: List[CalendarEvent]) -> ValidationResult:
        """Validate complete schedule against all constraints."""
        pass
    
    @abstractmethod
    def validate_team_schedule(self, team: 'Team', events: List[CalendarEvent]) -> ValidationResult:
        """Validate schedule for a specific team."""
        pass


# ===== UTILITY FUNCTIONS =====

def create_game_event_id(home_team: 'Team', away_team: 'Team', game_date: date) -> str:
    """Create a unique ID for a game event."""
    return f"GAME_{home_team.team_name.replace(' ', '')}_{away_team.team_name.replace(' ', '')}_{game_date.strftime('%Y%m%d')}"


def create_special_event_id(event_type: EventType, event_date: date) -> str:
    """Create a unique ID for a special event."""
    return f"SPECIAL_{event_type.value.upper()}_{event_date.strftime('%Y%m%d')}"


def events_to_legacy_format(events: List[CalendarEvent]) -> List[tuple]:
    """
    Convert new event format to legacy tuple format for compatibility.
    
    This is a temporary adapter function during the migration period.
    """
    legacy_events = []
    for event in events:
        if isinstance(event, GameEvent):
            # Convert to (date, home_team, away_team) format
            legacy_events.append((event.date, event.home_team, event.away_team))
        elif isinstance(event, SpecialEvent):
            # Convert special events to (date, 'NHL_EVENT', metadata) format
            legacy_events.append((event.date, 'NHL_EVENT', {
                'type': event.event_type.value,
                'title': event.title,
                'description': event.description
            }))
    return legacy_events


def events_from_legacy_format(legacy_events: List[tuple]) -> List[CalendarEvent]:
    """
    Convert legacy tuple format to new event format.
    
    This helps import existing schedule data into the new system.
    """
    new_events = []
    for item in legacy_events:
        try:
            if len(item) >= 3:
                game_date, home_team, away_team = item[0], item[1], item[2]
                
                # Handle special events
                if home_team == 'NHL_EVENT' or str(home_team) == 'NHL_EVENT':
                    if len(item) > 3 and isinstance(item[3], dict):
                        metadata = item[3]
                        event_type_str = metadata.get('type', 'unknown')
                        try:
                            event_type = EventType(event_type_str)
                            special_event = SpecialEvent(
                                event_id=create_special_event_id(event_type, game_date),
                                date=game_date,
                                event_type=event_type,
                                title=metadata.get('title', 'Special Event'),
                                description=metadata.get('description', ''),
                                importance_level=ImportanceLevel.MEDIUM
                            )
                            new_events.append(special_event)
                        except ValueError:
                            # Skip unknown event types
                            continue
                else:
                    # Handle regular games
                    if hasattr(home_team, 'team_name') and hasattr(away_team, 'team_name'):
                        game_event = GameEvent(
                            event_id=create_game_event_id(home_team, away_team, game_date),
                            date=game_date,
                            event_type=EventType.NHL_GAME,  # Assume NHL
                            title=f"{away_team.team_name} @ {home_team.team_name}",
                            description=f"NHL game between {away_team.team_name} and {home_team.team_name}",
                            home_team=home_team,
                            away_team=away_team,
                            game_time=time(19, 0),  # Default 7:00 PM
                            league='NHL'
                        )
                        new_events.append(game_event)
        except Exception as e:
            # Skip malformed entries
            continue
    
    return new_events


# ===== COLOR SCHEME =====

@dataclass(frozen=True)
class CalendarColorScheme:
    """Centralized color scheme for calendar display."""
    today: tuple = ('#E91E63', 'white')           # Hot Pink
    home_game: tuple = ('#1565C0', 'white')       # Deep Blue  
    away_game: tuple = ('#00BCD4', 'white')       # Bright Cyan
    trade_deadline: tuple = ('#E53935', 'white')  # Bright Red
    all_star: tuple = ('#FFC107', 'black')        # Bright Gold
    draft: tuple = ('#FF5722', 'white')           # Bright Orange
    free_agency: tuple = ('#9C27B0', 'white')     # Purple
    break_day: tuple = ('#424242', 'white')       # Dark Grey
    normal_day: tuple = ('#2A2A2A', '#E0E0E0')    # Default
    
    def get_color_for_event(self, event: CalendarEvent, user_team: 'Team' = None, is_today: bool = False) -> tuple:
        """Get appropriate color for an event."""
        if is_today:
            return self.today
        
        if isinstance(event, GameEvent) and user_team:
            if event.is_home_game_for_team(user_team):
                return self.home_game
            elif event.is_user_team_game(user_team):
                return self.away_game
        
        if isinstance(event, SpecialEvent):
            if event.event_type == EventType.TRADE_DEADLINE:
                return self.trade_deadline
            elif event.event_type in [EventType.ALL_STAR, EventType.ALL_STAR_SKILLS]:
                return self.all_star
            elif event.event_type == EventType.DRAFT:
                return self.draft
            elif event.event_type == EventType.FREE_AGENCY:
                return self.free_agency
            elif event.event_type == EventType.BREAK_DAY:
                return self.break_day
        
        return self.normal_day