"""
Simplified Schedule Interfaces for Phase 3
=========================================

Clean interface definitions for the schedule system components.
Simplified version that focuses on core functionality.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional
from simple_schedule_data import CalendarEvent, ValidationResult


class IScheduleEngine(ABC):
    """Interface for schedule generation engines."""
    
    @abstractmethod
    def generate_schedule(self) -> List[CalendarEvent]:
        """Generate a complete schedule based on configuration."""
        pass
    
    @abstractmethod
    def get_events_for_date_range(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        """Get all events within a specific date range."""
        pass
    
    @abstractmethod
    def get_events_for_team(self, team_name: str) -> List[CalendarEvent]:
        """Get all events involving a specific team."""
        pass
    
    @abstractmethod
    def validate_current_schedule(self) -> ValidationResult:
        """Validate the currently generated schedule."""
        pass


class IScheduleValidator(ABC):
    """Interface for schedule validation."""
    
    @abstractmethod
    def validate_schedule(self, events: List[CalendarEvent]) -> ValidationResult:
        """Perform comprehensive schedule validation."""
        pass


class ICalendarManager(ABC):
    """Interface for calendar management and UI operations."""
    
    @abstractmethod
    def load_events(self, events: List[CalendarEvent]) -> None:
        """Load events into the calendar."""
        pass
    
    @abstractmethod
    def get_events_for_date(self, target_date: date) -> List[CalendarEvent]:
        """Get all events for a specific date."""
        pass
    
    @abstractmethod
    def refresh_display(self) -> None:
        """Refresh the calendar display."""
        pass


if __name__ == "__main__":
    """Test interface definitions."""
    print("=== TESTING SCHEDULE INTERFACES ===")
    
    # Check that interfaces are properly defined
    print(f"IScheduleEngine methods: {len(IScheduleEngine.__abstractmethods__)}")
    print(f"IScheduleValidator methods: {len(IScheduleValidator.__abstractmethods__)}")
    print(f"ICalendarManager methods: {len(ICalendarManager.__abstractmethods__)}")
    
    print("✅ SIMPLIFIED INTERFACES WORKING!")