# Phase 2: New Schedule Architecture Design

## Executive Summary
This document outlines the complete architectural design for the new NHL scheduling and calendar system. The design focuses on **clean separation of concerns**, **standardized data formats**, and **robust error handling**.

## Core Design Principles

### 1. Single Responsibility Principle
- **ScheduleEngine**: Only handles game scheduling logic
- **CalendarEvent**: Only represents event data
- **CalendarDisplay**: Only handles UI presentation
- **ScheduleValidator**: Only validates schedule integrity

### 2. Standardized Data Format
All events use a single, consistent format regardless of type.

### 3. Clear Interfaces
Well-defined interfaces between components with proper abstraction layers.

### 4. Immutable Data Structures
Events are immutable once created to prevent accidental modification.

### 5. Comprehensive Validation
Every operation includes validation with clear error reporting.

## Data Model Design

### CalendarEvent (Base Event Class)
```python
@dataclass(frozen=True)
class CalendarEvent:
    """Immutable base class for all calendar events."""
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
```

### GameEvent (Specialized for Hockey Games)
```python
@dataclass(frozen=True)
class GameEvent(CalendarEvent):
    """Specialized event for hockey games."""
    home_team: Team
    away_team: Team
    game_time: time
    league: str
    venue: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        if self.home_team == self.away_team:
            raise ValueError("Home and away teams must be different")
        if self.event_type not in [EventType.NHL_GAME, EventType.AHL_GAME]:
            raise ValueError(f"Invalid game event type: {self.event_type}")
    
    @property
    def is_user_team_game(self) -> bool:
        """Check if this game involves the user's team."""
        # Implementation will check against current user team
        pass
    
    @property
    def is_home_game(self) -> bool:
        """Check if this is a home game for user team."""
        # Implementation will check if user team is home team
        pass
```

### SpecialEvent (For Non-Game Events)
```python
@dataclass(frozen=True)
class SpecialEvent(CalendarEvent):
    """Special NHL events like All-Star, Draft, etc."""
    importance_level: ImportanceLevel
    affects_schedule: bool = False
    
    def __post_init__(self):
        super().__post_init__()
        if self.event_type not in [EventType.ALL_STAR, EventType.TRADE_DEADLINE, 
                                   EventType.DRAFT, EventType.FREE_AGENCY]:
            raise ValueError(f"Invalid special event type: {self.event_type}")
```

### EventType Enumeration
```python
class EventType(Enum):
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
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
```

## Architecture Components

### 1. ScheduleEngine (Core Logic)
```python
class ScheduleEngine:
    """Core scheduling engine with strict constraint enforcement."""
    
    def __init__(self, teams: List[Team], season_year: int):
        self.teams = teams
        self.season_year = season_year
        self.validator = ScheduleValidator()
    
    def generate_nhl_schedule(self) -> List[GameEvent]:
        """Generate complete NHL schedule with all constraints."""
        # 1. Create game matchups (82 games per team)
        matchups = self._create_nhl_matchups()
        
        # 2. Distribute games chronologically with constraints
        games = self._distribute_games_with_constraints(matchups)
        
        # 3. Validate final schedule
        validation_result = self.validator.validate_schedule(games)
        if not validation_result.is_valid:
            raise ScheduleValidationError(validation_result.errors)
        
        return games
    
    def _create_nhl_matchups(self) -> List[Tuple[Team, Team]]:
        """Create authentic NHL matchup distribution."""
        # Implementation follows real NHL structure:
        # - 26 division games (4×3 + 3×4 against 7 division rivals)  
        # - 24 conference games (3 each vs 8 same-conference teams)
        # - 32 interconference games (2 each vs 16 other conference teams)
        # Total: 82 games per team
        pass
    
    def _distribute_games_with_constraints(self, matchups: List[Tuple[Team, Team]]) -> List[GameEvent]:
        """Distribute games with strict constraint enforcement."""
        # Constraints:
        # 1. No team plays multiple games on same day
        # 2. No team has 3+ consecutive games  
        # 3. Balanced monthly distribution
        # 4. Reasonable back-to-back limits
        pass
```

### 2. ScheduleValidator (Validation Logic)
```python
@dataclass
class ValidationResult:
    """Results of schedule validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
class ScheduleValidator:
    """Comprehensive schedule validation."""
    
    def validate_schedule(self, games: List[GameEvent]) -> ValidationResult:
        """Validate complete schedule against all constraints."""
        result = ValidationResult(is_valid=True)
        
        # Critical validations (errors)
        self._validate_no_multiple_games_per_day(games, result)
        self._validate_no_excessive_consecutive_games(games, result)
        self._validate_team_game_counts(games, result)
        self._validate_game_distribution(games, result)
        
        # Quality validations (warnings)
        self._validate_back_to_back_limits(games, result)
        self._validate_monthly_distribution(games, result)
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def _validate_no_multiple_games_per_day(self, games: List[GameEvent], result: ValidationResult):
        """Ensure no team has multiple games on same day."""
        team_dates = {}
        for game in games:
            for team in [game.home_team, game.away_team]:
                team_name = team.team_name
                game_date = game.date
                
                if team_name not in team_dates:
                    team_dates[team_name] = set()
                
                if game_date in team_dates[team_name]:
                    result.errors.append(f"{team_name} has multiple games on {game_date}")
                else:
                    team_dates[team_name].add(game_date)
```

### 3. CalendarManager (Event Coordination)
```python
class CalendarManager:
    """Manages all calendar events and provides unified interface."""
    
    def __init__(self):
        self._events: Dict[date, List[CalendarEvent]] = {}
        self._event_index: Dict[str, CalendarEvent] = {}
    
    def add_event(self, event: CalendarEvent):
        """Add event to calendar with validation."""
        if event.event_id in self._event_index:
            raise ValueError(f"Event ID already exists: {event.event_id}")
        
        # Add to date index
        if event.date not in self._events:
            self._events[event.date] = []
        self._events[event.date].append(event)
        
        # Add to ID index
        self._event_index[event.event_id] = event
    
    def get_events_for_date(self, target_date: date) -> List[CalendarEvent]:
        """Get all events for a specific date."""
        return self._events.get(target_date, [])
    
    def get_events_in_range(self, start_date: date, end_date: date) -> Dict[date, List[CalendarEvent]]:
        """Get all events in date range."""
        result = {}
        current_date = start_date
        while current_date <= end_date:
            if current_date in self._events:
                result[current_date] = self._events[current_date]
            current_date += timedelta(days=1)
        return result
    
    def get_user_team_events(self, user_team: Team) -> List[GameEvent]:
        """Get all events involving user's team."""
        user_events = []
        for events in self._events.values():
            for event in events:
                if isinstance(event, GameEvent):
                    if event.home_team == user_team or event.away_team == user_team:
                        user_events.append(event)
        return sorted(user_events, key=lambda e: e.date)
```

### 4. CalendarDisplay (Presentation Layer)
```python
class CalendarDisplay:
    """Handles all calendar UI presentation logic."""
    
    def __init__(self, parent, calendar_manager: CalendarManager):
        self.parent = parent
        self.calendar_manager = calendar_manager
        self.color_scheme = CalendarColorScheme()
    
    def create_calendar_widget(self, target_month: int, target_year: int) -> tk.Widget:
        """Create calendar widget for specific month/year."""
        # Implementation creates clean calendar UI
        pass
    
    def get_date_color(self, target_date: date, user_team: Team) -> Tuple[str, str]:
        """Get background and foreground colors for a date."""
        events = self.calendar_manager.get_events_for_date(target_date)
        
        # Priority system for colors
        if target_date == date.today():
            return self.color_scheme.today
        
        for event in events:
            if isinstance(event, GameEvent):
                if event.home_team == user_team:
                    return self.color_scheme.home_game
                elif event.away_team == user_team:
                    return self.color_scheme.away_game
            elif event.event_type == EventType.TRADE_DEADLINE:
                return self.color_scheme.trade_deadline
            elif event.event_type in [EventType.ALL_STAR, EventType.ALL_STAR_SKILLS]:
                return self.color_scheme.all_star
            elif event.event_type == EventType.DRAFT:
                return self.color_scheme.draft
        
        return self.color_scheme.normal_day

class CalendarColorScheme:
    """Centralized color scheme for calendar display."""
    def __init__(self):
        self.today = ('#E91E63', 'white')           # Hot Pink
        self.home_game = ('#1565C0', 'white')       # Deep Blue  
        self.away_game = ('#00BCD4', 'white')       # Bright Cyan
        self.trade_deadline = ('#E53935', 'white')  # Bright Red
        self.all_star = ('#FFC107', 'black')        # Bright Gold
        self.draft = ('#FF5722', 'white')           # Bright Orange
        self.normal_day = ('#2A2A2A', '#E0E0E0')    # Default
```

## Interface Contracts

### IScheduleEngine
```python
from abc import ABC, abstractmethod

class IScheduleEngine(ABC):
    """Interface for schedule generation engines."""
    
    @abstractmethod
    def generate_schedule(self, teams: List[Team], season_year: int) -> List[CalendarEvent]:
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
    def get_events_for_month(self, month: int, year: int) -> Dict[date, List[CalendarEvent]]:
        """Get all events for a specific month."""
        pass
```

## Error Handling Strategy

### Custom Exceptions
```python
class ScheduleError(Exception):
    """Base exception for scheduling errors."""
    pass

class ScheduleValidationError(ScheduleError):
    """Raised when schedule fails validation."""
    def __init__(self, validation_errors: List[str]):
        self.validation_errors = validation_errors
        super().__init__(f"Schedule validation failed: {'; '.join(validation_errors)}")

class EventConflictError(ScheduleError):
    """Raised when events conflict."""
    pass

class TeamScheduleError(ScheduleError):
    """Raised for team-specific scheduling issues."""
    pass
```

### Error Recovery
```python
class ScheduleRecovery:
    """Handles error recovery and schedule repair."""
    
    def attempt_schedule_repair(self, broken_schedule: List[CalendarEvent]) -> List[CalendarEvent]:
        """Attempt to repair a broken schedule."""
        # Try to fix common issues:
        # 1. Remove duplicate games
        # 2. Reschedule conflicting games  
        # 3. Fill missing games
        pass
    
    def create_fallback_schedule(self, teams: List[Team]) -> List[CalendarEvent]:
        """Create minimal working schedule as fallback."""
        # Simple but valid schedule if main generation fails
        pass
```

## Integration Points

### With Existing System
```python
class ScheduleLegacyAdapter:
    """Adapter to integrate new system with existing code."""
    
    def __init__(self, new_calendar_manager: CalendarManager):
        self.calendar_manager = new_calendar_manager
    
    def get_legacy_schedule_format(self) -> List[Tuple]:
        """Convert new events to legacy tuple format if needed."""
        # Temporary compatibility layer
        pass
    
    def import_legacy_schedule(self, legacy_schedule: List) -> List[CalendarEvent]:
        """Import existing schedule data to new format."""
        pass
```

### With UI Components
```python
class CalendarUIAdapter:
    """Adapter for UI component integration."""
    
    def create_treeview_data(self, events: List[CalendarEvent]) -> List[Dict]:
        """Convert events to treeview-compatible format."""
        pass
    
    def handle_event_selection(self, event_id: str) -> CalendarEvent:
        """Handle UI event selection."""
        pass
```

## Performance Considerations

### Lazy Loading
- Events loaded only when needed for display
- Month-based caching for calendar views
- Background generation of future schedules

### Memory Management
- Immutable events prevent accidental modifications
- Efficient indexing by date and team
- Cleanup of old events not needed for display

### Scalability
- System designed to handle multiple leagues
- Efficient validation algorithms
- Parallel processing for schedule generation

## Testing Strategy

### Unit Tests
- Each component has comprehensive unit tests
- Mock objects for external dependencies
- Edge case testing for all constraints

### Integration Tests  
- Test component interactions
- Validate data flow between layers
- Test error handling and recovery

### Performance Tests
- Schedule generation speed benchmarks
- Memory usage monitoring
- UI responsiveness testing

## Migration Strategy

### Phase 1: New Components
- Implement new data structures and interfaces
- Create comprehensive test suite
- Validate against existing schedules

### Phase 2: Integration
- Create adapter layers for existing code
- Gradual replacement of legacy components
- Maintain backward compatibility

### Phase 3: Full Migration
- Remove legacy code
- Optimize performance
- Add advanced features

## Benefits of New Architecture

### Reliability
- ✅ **ELIMINATED**: Multiple games per day impossible by design
- ✅ **ELIMINATED**: Format inconsistencies through standardized events
- ✅ **ELIMINATED**: Consecutive games violations through proper validation
- ✅ **ELIMINATED**: Calendar compatibility issues through unified interface

### Maintainability
- ✅ **CLEAR**: Single responsibility for each component
- ✅ **TESTABLE**: Each component can be tested in isolation
- ✅ **EXTENSIBLE**: Easy to add new event types or constraints

### Performance
- ✅ **EFFICIENT**: Optimized data structures and algorithms
- ✅ **SCALABLE**: Designed for multiple leagues and seasons
- ✅ **RESPONSIVE**: Lazy loading and caching strategies

### User Experience
- ✅ **RELIABLE**: No more scheduling bugs and inconsistencies
- ✅ **FAST**: Quick calendar navigation and event display
- ✅ **INFORMATIVE**: Rich event information and color coding

## Next Steps

This architecture design provides the foundation for **Phase 3: Implement Core Schedule Engine**. The design ensures:

1. **No Multiple Games Per Day**: Impossible by validation design
2. **No Consecutive Games**: Enforced by constraint system
3. **Format Consistency**: Single event format for all use cases
4. **Calendar Compatibility**: Native integration between schedule and display
5. **Extensibility**: Easy to add new features and event types

**Phase 2 Status: COMPLETED** ✓

Ready to proceed to **Phase 3: Implement Core Schedule Engine** with this solid architectural foundation.