"""
Simplified Schedule Data Structures for Phase 3
==============================================

This module provides simplified, working data structures for Phase 3
implementation. It avoids complex inheritance issues while maintaining
the core functionality needed for schedule generation.
"""

from dataclasses import dataclass
from datetime import date, time
from typing import Optional, List
from enum import Enum


class EventType(Enum):
    """Types of calendar events."""
    GAME = "game"
    TRADE_DEADLINE = "trade_deadline"
    ENTRY_DRAFT = "entry_draft"
    FREE_AGENT_PERIOD = "free_agent_period"
    ALL_STAR_GAME = "all_star_game"
    ALL_STAR_SKILLS = "all_star_skills"
    SEASON_START = "season_start"
    SEASON_END = "season_end"
    PLAYOFF_START = "playoff_start"
    TRAINING_CAMP = "training_camp"


class ValidationSeverity(Enum):
    """Severity levels for validation results."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    severity: ValidationSeverity
    message: str
    details: dict


@dataclass(frozen=True)
class CalendarEvent:
    """Base class for all calendar events."""
    event_id: str
    date: date
    title: str
    description: str = ""
    event_type: EventType = EventType.GAME
    
    def __post_init__(self):
        """Validate the event data."""
        if not isinstance(self.date, date):
            raise ValueError("Date must be a date object")
        if not isinstance(self.event_type, EventType):
            raise ValueError("Event type must be an EventType enum")


@dataclass(frozen=True)
class GameEvent(CalendarEvent):
    """Specialized event for hockey games."""
    home_team_name: str = ""
    away_team_name: str = ""
    game_time: str = "19:00"
    
    def is_user_team_game(self, user_team_name: str) -> bool:
        """Check if this game involves the user's team."""
        return (self.home_team_name == user_team_name or 
                self.away_team_name == user_team_name)
    
    def is_home_game_for_team(self, team_name: str) -> bool:
        """Check if this is a home game for the specified team."""
        return self.home_team_name == team_name
    
    def get_opponent(self, team_name: str) -> Optional[str]:
        """Get the opponent team name for the specified team."""
        if self.home_team_name == team_name:
            return self.away_team_name
        elif self.away_team_name == team_name:
            return self.home_team_name
        return None


@dataclass(frozen=True)
class SpecialEvent(CalendarEvent):
    """Specialized event for NHL special events."""
    participants: List[str] = None
    location: str = ""
    
    def __post_init__(self):
        """Initialize participants list if None."""
        super().__post_init__()
        if self.participants is None:
            # Use object.__setattr__ for frozen dataclass
            object.__setattr__(self, 'participants', [])


# For testing and demonstration
def create_sample_events():
    """Create sample events for testing."""
    from datetime import date
    
    # Sample game event
    game = GameEvent(
        event_id="GAME_001",
        date=date(2024, 10, 15),
        title="Rangers @ Bruins",
        home_team_name="Boston Bruins",
        away_team_name="New York Rangers",
        event_type=EventType.GAME
    )
    
    # Sample special event
    special = SpecialEvent(
        event_id="SPECIAL_001",
        date=date(2024, 12, 15),
        title="NHL Trade Deadline",
        event_type=EventType.TRADE_DEADLINE,
        location="League Office"
    )
    
    return [game, special]


if __name__ == "__main__":
    """Test the data structures."""
    print("=== TESTING SIMPLIFIED DATA STRUCTURES ===")
    
    events = create_sample_events()
    print(f"Created {len(events)} sample events")
    
    game = events[0]
    print(f"Game: {game.title} on {game.date}")
    print(f"Is Boston home game: {game.is_home_game_for_team('Boston Bruins')}")
    print(f"Is Rangers game: {game.is_user_team_game('New York Rangers')}")
    print(f"Boston's opponent: {game.get_opponent('Boston Bruins')}")
    
    special = events[1]
    print(f"Special event: {special.title} on {special.date}")
    
    # Test immutability
    try:
        game.home_team_name = "Changed"
        print("ERROR: Should not be able to modify frozen dataclass!")
    except Exception as e:
        print(f"✓ Immutability working: {type(e).__name__}")
    
    print("✅ SIMPLIFIED DATA STRUCTURES WORKING!")