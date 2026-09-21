"""
New Schedule System - Interface Definitions

This module defines the clean interfaces and contracts for the new 
scheduling system components. These interfaces ensure proper separation
of concerns and enable easy testing and extensibility.
"""

from abc import ABC, abstractmethod
from datetime import date, time, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

# Import our schedule data structures
from schedule_data_structures import CalendarEvent, EventType

# Define missing enums and classes
class ImportanceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class TeamScheduleStats:
    """Statistics about a team's schedule"""
    team_name: str
    total_games: int = 0
    home_games: int = 0
    away_games: int = 0
    back_to_back_games: int = 0
    longest_homestand: int = 0
    longest_road_trip: int = 0
    
@dataclass  
class SpecialEvent:
    """Special event in the schedule"""
    name: str
    date: date
    description: str
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
from simple_schedule_data import (
    CalendarEvent, GameEvent, SpecialEvent, ValidationResult, EventType
)


# ===== CORE INTERFACES =====

class IScheduleEngine(ABC):
    """
    Interface for schedule generation engines.
    
    This is the core interface for generating NHL schedules. Different
    implementations can use different algorithms while maintaining the
    same interface.
    """
    
    @abstractmethod
    def generate_nhl_schedule(self, teams: List, season_year: int) -> List[GameEvent]:
        """
        Generate complete NHL schedule for given teams and season.
        
        Args:
            teams: List of NHL teams
            season_year: Starting year of season (e.g., 2024 for 2024-25 season)
            
        Returns:
            List of GameEvent objects representing complete season
            
        Raises:
            ScheduleValidationError: If generated schedule fails validation
            TeamScheduleError: If team-specific constraints can't be met
        """
        pass
    
    @abstractmethod
    def generate_special_events(self, season_year: int) -> List[SpecialEvent]:
        """
        Generate special NHL events (All-Star, Draft, etc.) for season.
        
        Args:
            season_year: Starting year of season
            
        Returns:
            List of SpecialEvent objects for the season
        """
        pass
    
    @abstractmethod
    def validate_schedule_constraints(self, events: List[CalendarEvent]) -> ValidationResult:
        """
        Validate generated schedule meets all NHL constraints.
        
        Args:
            events: List of all calendar events to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        pass


class ICalendarManager(ABC):
    """
    Interface for calendar event management.
    
    This manages all events (games and special events) and provides
    efficient access methods for the UI and other components.
    """
    
    @abstractmethod
    def add_events(self, events: List[CalendarEvent]) -> None:
        """
        Add multiple events to calendar.
        
        Args:
            events: List of CalendarEvent objects to add
            
        Raises:
            EventConflictError: If events conflict with existing events
        """
        pass
    
    @abstractmethod
    def get_events_for_date(self, target_date: date) -> List[CalendarEvent]:
        """
        Get all events for a specific date.
        
        Args:
            target_date: Date to get events for
            
        Returns:
            List of CalendarEvent objects for the date (empty if none)
        """
        pass
    
    @abstractmethod
    def get_events_for_month(self, month: int, year: int) -> Dict[date, List[CalendarEvent]]:
        """
        Get all events for a specific month.
        
        Args:
            month: Month number (1-12)
            year: Year
            
        Returns:
            Dictionary mapping dates to lists of events
        """
        pass
    
    @abstractmethod
    def get_events_in_range(self, start_date: date, end_date: date) -> Dict[date, List[CalendarEvent]]:
        """
        Get all events in a date range.
        
        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            
        Returns:
            Dictionary mapping dates to lists of events
        """
        pass
    
    @abstractmethod
    def get_team_schedule(self, team_name: str) -> List[GameEvent]:
        """
        Get all games for a specific team.
        
        Args:
            team_name: Name of team to get schedule for
            
        Returns:
            List of GameEvent objects for the team, sorted by date
        """
        pass
    
    @abstractmethod
    def clear_all_events(self) -> None:
        """Remove all events from calendar."""
        pass


class IScheduleValidator(ABC):
    """
    Interface for schedule validation.
    
    This handles all validation logic to ensure schedules meet NHL
    requirements and constraints.
    """
    
    @abstractmethod
    def validate_complete_schedule(self, events: List[CalendarEvent]) -> ValidationResult:
        """
        Validate complete schedule against all constraints.
        
        Args:
            events: All calendar events to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        pass
    
    @abstractmethod
    def validate_team_schedule(self, team_name: str, events: List[CalendarEvent]) -> ValidationResult:
        """
        Validate schedule for a specific team.
        
        Args:
            team_name: Name of team to validate
            events: All calendar events (will filter to team's games)
            
        Returns:
            ValidationResult for the team's schedule
        """
        pass
    
    @abstractmethod
    def check_no_multiple_games_per_day(self, events: List[CalendarEvent]) -> ValidationResult:
        """
        Check that no team has multiple games on the same day.
        
        This is a critical constraint that must never be violated.
        
        Args:
            events: All calendar events to check
            
        Returns:
            ValidationResult with any violations found
        """
        pass
    
    @abstractmethod
    def check_no_excessive_consecutive_games(self, events: List[CalendarEvent], max_consecutive: int = 2) -> ValidationResult:
        """
        Check that no team has too many consecutive games.
        
        Args:
            events: All calendar events to check
            max_consecutive: Maximum allowed consecutive games (default: 2)
            
        Returns:
            ValidationResult with any violations found
        """
        pass
    
    @abstractmethod
    def get_team_schedule_stats(self, team_name: str, events: List[CalendarEvent]) -> TeamScheduleStats:
        """
        Get detailed statistics for a team's schedule.
        
        Args:
            team_name: Name of team to analyze
            events: All calendar events
            
        Returns:
            TeamScheduleStats with detailed schedule analysis
        """
        pass


class ICalendarDisplay(ABC):
    """
    Interface for calendar UI display logic.
    
    This handles all presentation logic for the calendar while staying
    decoupled from the underlying data management.
    """
    
    @abstractmethod
    def create_month_calendar(self, month: int, year: int, user_team_name: str = None):
        """
        Create calendar widget for a specific month.
        
        Args:
            month: Month number (1-12)
            year: Year
            user_team_name: Name of user's team for highlighting games
            
        Returns:
            Calendar widget ready for display
        """
        pass
    
    @abstractmethod
    def get_date_display_info(self, target_date: date, user_team_name: str = None) -> Dict:
        """
        Get display information for a specific date.
        
        Args:
            target_date: Date to get info for
            user_team_name: Name of user's team for context
            
        Returns:
            Dictionary with display info (colors, text, events, etc.)
        """
        pass
    
    @abstractmethod
    def update_calendar_view(self) -> None:
        """Refresh the calendar display with current data."""
        pass
    
    @abstractmethod
    def handle_date_selection(self, selected_date: date) -> None:
        """
        Handle user selection of a date.
        
        Args:
            selected_date: Date that was selected
        """
        pass


class IScheduleConstraintChecker(ABC):
    """
    Interface for checking specific schedule constraints.
    
    This allows for modular constraint checking and easy addition
    of new constraints.
    """
    
    @abstractmethod
    def check_constraint(self, events: List[CalendarEvent], teams: List = None) -> ValidationResult:
        """
        Check if constraint is satisfied by the given events.
        
        Args:
            events: Events to check
            teams: Teams to check (if constraint is team-specific)
            
        Returns:
            ValidationResult indicating if constraint is satisfied
        """
        pass
    
    @abstractmethod
    def get_constraint_name(self) -> str:
        """Get human-readable name of this constraint."""
        pass
    
    @abstractmethod
    def get_constraint_description(self) -> str:
        """Get detailed description of what this constraint checks."""
        pass


# ===== SPECIALIZED CONSTRAINT INTERFACES =====

class INoMultipleGamesConstraint(IScheduleConstraintChecker):
    """Constraint: No team has multiple games on same day."""
    pass


class INoConsecutiveGamesConstraint(IScheduleConstraintChecker):
    """Constraint: No team has too many consecutive games."""
    pass


class IGameCountConstraint(IScheduleConstraintChecker):
    """Constraint: Each team has correct number of games (82 for NHL)."""
    pass


class IHomeAwayBalanceConstraint(IScheduleConstraintChecker):
    """Constraint: Home/away games are reasonably balanced."""
    pass


class IMonthlyDistributionConstraint(IScheduleConstraintChecker):
    """Constraint: Games are reasonably distributed across months."""
    pass


# ===== ADAPTER INTERFACES =====

class ILegacyScheduleAdapter(ABC):
    """
    Interface for adapting between new and legacy schedule formats.
    
    This allows gradual migration from the old system to the new one
    without breaking existing functionality.
    """
    
    @abstractmethod
    def convert_to_legacy_format(self, events: List[CalendarEvent]) -> List[tuple]:
        """
        Convert new events to legacy tuple format.
        
        Args:
            events: New format events
            
        Returns:
            Legacy format event tuples
        """
        pass
    
    @abstractmethod
    def convert_from_legacy_format(self, legacy_events: List[tuple]) -> List[CalendarEvent]:
        """
        Convert legacy format to new events.
        
        Args:
            legacy_events: Legacy format event tuples
            
        Returns:
            New format CalendarEvent objects
        """
        pass
    
    @abstractmethod
    def is_legacy_format_compatible(self, data) -> bool:
        """
        Check if data is in legacy format.
        
        Args:
            data: Data to check
            
        Returns:
            True if data appears to be legacy format
        """
        pass


class IUIAdapter(ABC):
    """
    Interface for adapting calendar data to UI components.
    
    This provides clean separation between data structures and
    UI presentation requirements.
    """
    
    @abstractmethod
    def events_to_treeview_data(self, events: List[CalendarEvent]) -> List[Dict]:
        """
        Convert events to format suitable for treeview display.
        
        Args:
            events: Events to convert
            
        Returns:
            List of dictionaries with treeview-compatible data
        """
        pass
    
    @abstractmethod
    def event_to_tooltip_text(self, event: CalendarEvent) -> str:
        """
        Convert event to tooltip text.
        
        Args:
            event: Event to create tooltip for
            
        Returns:
            Formatted tooltip text
        """
        pass
    
    @abstractmethod
    def events_to_color_map(self, events: List[CalendarEvent], user_team_name: str = None) -> Dict[date, tuple]:
        """
        Create color mapping for calendar dates.
        
        Args:
            events: Events to create colors for
            user_team_name: User's team for context-specific coloring
            
        Returns:
            Dictionary mapping dates to (background, foreground) color tuples
        """
        pass


# ===== EVENT FACTORY INTERFACE =====

class IEventFactory(ABC):
    """
    Interface for creating calendar events.
    
    This provides a clean way to create events with proper validation
    and ID generation.
    """
    
    @abstractmethod
    def create_game_event(self, home_team, away_team, game_date: date, 
                         game_time: Optional[time] = None, league: str = "NHL") -> GameEvent:
        """
        Create a new game event.
        
        Args:
            home_team: Home team object
            away_team: Away team object
            game_date: Date of game
            game_time: Time of game (defaults to 7:00 PM if None)
            league: League name (defaults to "NHL")
            
        Returns:
            New GameEvent object
            
        Raises:
            ValueError: If parameters are invalid
        """
        pass
    
    @abstractmethod
    def create_special_event(self, event_type: EventType, event_date: date,
                           title: str, description: str = "", 
                           importance: ImportanceLevel = ImportanceLevel.MEDIUM) -> SpecialEvent:
        """
        Create a new special event.
        
        Args:
            event_type: Type of special event
            event_date: Date of event
            title: Event title
            description: Event description
            importance: Importance level of event
            
        Returns:
            New SpecialEvent object
            
        Raises:
            ValueError: If parameters are invalid
        """
        pass


# ===== PERFORMANCE INTERFACES =====

class ICacheManager(ABC):
    """
    Interface for managing calendar data caching.
    
    This enables efficient calendar display by caching frequently
    accessed data.
    """
    
    @abstractmethod
    def cache_month_events(self, month: int, year: int, events: Dict[date, List[CalendarEvent]]) -> None:
        """Cache events for a specific month."""
        pass
    
    @abstractmethod
    def get_cached_month_events(self, month: int, year: int) -> Optional[Dict[date, List[CalendarEvent]]]:
        """Get cached events for a month, if available."""
        pass
    
    @abstractmethod
    def invalidate_cache(self, start_date: date = None, end_date: date = None) -> None:
        """Invalidate cache for date range (or all if no dates specified)."""
        pass
    
    @abstractmethod
    def get_cache_statistics(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        pass


# ===== CONFIGURATION INTERFACE =====

class IScheduleConfiguration(ABC):
    """
    Interface for schedule generation configuration.
    
    This allows customization of schedule generation parameters
    without changing the core logic.
    """
    
    @abstractmethod
    def get_games_per_team(self) -> int:
        """Get number of games per team (82 for NHL)."""
        pass
    
    @abstractmethod
    def get_max_consecutive_games(self) -> int:
        """Get maximum allowed consecutive games."""
        pass
    
    @abstractmethod
    def get_season_date_range(self, season_year: int) -> Tuple[date, date]:
        """Get start and end dates for a season."""
        pass
    
    @abstractmethod
    def get_special_event_dates(self, season_year: int) -> Dict[str, date]:
        """Get dates for special events (All-Star, Draft, etc.)."""
        pass
    
    @abstractmethod
    def get_games_per_day_target(self) -> int:
        """Get target number of league games per day."""
        pass


# ===== REPORTING INTERFACE =====

class IScheduleReporter(ABC):
    """
    Interface for generating schedule reports and statistics.
    
    This provides various reports about schedule quality and statistics.
    """
    
    @abstractmethod
    def generate_schedule_summary(self, events: List[CalendarEvent]) -> Dict:
        """Generate overall schedule summary."""
        pass
    
    @abstractmethod
    def generate_team_report(self, team_name: str, events: List[CalendarEvent]) -> Dict:
        """Generate detailed report for a specific team."""
        pass
    
    @abstractmethod
    def generate_constraint_report(self, events: List[CalendarEvent]) -> Dict:
        """Generate report on constraint satisfaction."""
        pass
    
    @abstractmethod
    def export_schedule_csv(self, events: List[CalendarEvent], filename: str) -> None:
        """Export schedule to CSV file."""
        pass