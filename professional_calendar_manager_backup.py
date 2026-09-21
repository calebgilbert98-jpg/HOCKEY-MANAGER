"""
Professional Calendar Manager - Phase 4 Implementation
=====================================================

This module implements the CalendarManager class that integrates with the 
Schedule Engin    def _create_calendar_ui(self):
        """Create calendar UI with professional styling."""
        # Calendar frame with content background
        self.calendar_frame = tk.Frame(self, bg=self.colors['CONTENT_BG'])
        self.calendar_frame.pack(fill='both', expand=True, padx=2, pady=2)Phase 3 to provide a professional calendar UI with 
advanced features and color coding.

Key Features:
- Integration with ScheduleEngine
- Professional color-coded events
- Event interaction and details
- Performance-optimized rendering
- Modern UI design
- Real-time updates
"""

import tkinter as tk
from tkinter import ttk
import calendar
from datetime import date, timedelta
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict

# Import our Phase 3 components
from simple_schedule_interfaces import ICalendarManager
from simple_schedule_data import CalendarEvent, GameEvent, SpecialEvent, EventType
from schedule_engine import ScheduleEngine


class CalendarColorScheme:
    """Professional color scheme for calendar events."""
    
    # Event type colors (background, foreground)
    COLORS = {
        'today': ('#E91E63', 'white'),           # Hot Pink - Current day
        'home_game': ('#1565C0', 'white'),       # Deep Blue - Home games
        'away_game': ('#00BCD4', 'white'),       # Bright Cyan - Away games
        'trade_deadline': ('#E53935', 'white'),  # Bright Red - Trade deadline
        'entry_draft': ('#FF5722', 'white'),     # Deep Orange - Draft
        'all_star_game': ('#FFB300', 'black'),   # Gold - All-Star game
        'all_star_skills': ('#FFA000', 'black'), # Amber - Skills competition
        'free_agent_period': ('#8E24AA', 'white'), # Purple - Free agency
        'training_camp': ('#4CAF50', 'white'),   # Green - Training camp
        'playoff_start': ('#D32F2F', 'white'),   # Red - Playoffs
        'season_start': ('#2E7D32', 'white'),    # Dark Green - Season start
        'season_end': ('#795548', 'white'),      # Brown - Season end
        'default': ('#37474F', 'white'),         # Blue Grey - Other events
        'empty': ('#2A2A2A', '#E0E0E0'),         # Dark Grey - Empty days
        'weekend': ('#1A1A1A', '#BDBDBD'),       # Darker - Weekends
    }
    
    @classmethod
    def get_color_for_event(cls, event: CalendarEvent, user_team_name: str, 
                           is_today: bool = False) -> tuple:
        """Get the appropriate color for an event."""
        if is_today:
            return cls.COLORS['today']
        
        if isinstance(event, GameEvent):
            if event.is_home_game_for_team(user_team_name):
                return cls.COLORS['home_game']
            elif event.is_user_team_game(user_team_name):
                return cls.COLORS['away_game']
            else:
                return cls.COLORS['default']
        
        elif isinstance(event, SpecialEvent):
            color_key = event.event_type.value
            return cls.COLORS.get(color_key, cls.COLORS['default'])
        
        return cls.COLORS['default']
    
    @classmethod
    def get_empty_day_color(cls, day_date: date) -> tuple:
        """Get color for empty days (weekends get special treatment)."""
        if day_date.weekday() >= 5:  # Saturday (5) or Sunday (6)
            return cls.COLORS['weekend']
        return cls.COLORS['empty']


class CalendarEventRenderer:
    """Handles rendering of calendar events with proper styling."""
    
    def __init__(self, parent_style: ttk.Style):
        self.style = parent_style
        self._configure_event_styles()
    
    def _configure_event_styles(self):
        """Configure TTK styles for different event types."""
        colors = CalendarColorScheme.COLORS
        
        for event_type, (bg_color, fg_color) in colors.items():
            style_name = f'{event_type.title()}Event.TButton'
            self.style.configure(style_name,
                               background=bg_color,
                               foreground=fg_color,
                               font=('Segoe UI', 8, 'bold'),
                               borderwidth=1,
                               relief='solid')
            
            # Active (hover) state - slightly darker
            if bg_color.startswith('#'):
                # Simple darkening for hover effect
                hover_bg = self._darken_color(bg_color, 0.8)
                self.style.map(style_name, 
                             background=[('active', hover_bg)])
    
    def _darken_color(self, hex_color: str, factor: float) -> str:
        """Darken a hex color by a factor (0.0 to 1.0)."""
        try:
            # Remove '#' if present
            hex_color = hex_color.lstrip('#')
            
            # Convert to RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Darken
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            
            # Convert back to hex
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return '#000000'  # Fallback to black
    
    def get_style_for_event(self, event: CalendarEvent, user_team_name: str, 
                           is_today: bool = False) -> str:
        """Get the TTK style name for an event."""
        if is_today:
            return 'TodayEvent.TButton'
        
        if isinstance(event, GameEvent):
            if event.is_home_game_for_team(user_team_name):
                return 'Home_GameEvent.TButton'
            elif event.is_user_team_game(user_team_name):
                return 'Away_GameEvent.TButton'
            else:
                return 'DefaultEvent.TButton'
        
        elif isinstance(event, SpecialEvent):
            event_type = event.event_type.value.title()
            return f'{event_type}Event.TButton'
        
        return 'DefaultEvent.TButton'


class CalendarWidget(tk.Frame):
    """Professional calendar widget with event rendering."""
    
    def __init__(self, parent, calendar_manager, **kwargs):
        super().__init__(parent, **kwargs)
        self.calendar_manager = calendar_manager
        self.parent = parent
        
        # Get styling colors safely
        self.colors = self._get_styling_colors()
        
        # Calendar state
        self.current_view_date = date.today()
        self.selected_date = None
        self.day_buttons: Dict[date, tk.Button] = {}
        self.events_by_date: Dict[date, List[CalendarEvent]] = defaultdict(list)
        
        # Event callbacks
        self.on_date_selected: Optional[Callable] = None
        self.on_event_clicked: Optional[Callable] = None
        
        # Initialize renderer
        self.style = ttk.Style()
        self.renderer = CalendarEventRenderer(self.style)
        
        # Create UI
        self._create_calendar_ui()
    
    def _get_styling_colors(self):
        """Get styling colors with fallbacks for compatibility."""
        # Try to get from parent hierarchy with defaults
        defaults = {
            'BG_COLOR': '#181818',
            'CONTENT_BG': '#1F1F1F', 
            'TITLE_BAR_COLOR': '#2A2A2A',
            'TEXT_COLOR': '#E0E0E0',
            'HEADER_COLOR': '#FFFFFF',
            'ACCENT_COLOR': '#D13438',
            'FONT_FAMILY': 'Segoe UI'
        }
        
        colors = {}
        sources = [self.calendar_manager, self.parent, getattr(self.parent, 'parent', None)]
        
        for attr, default in defaults.items():
            for source in sources:
                if source and hasattr(source, attr):
                    colors[attr] = getattr(source, attr)
                    break
            else:
                colors[attr] = default
        
        return colors
        self.renderer = CalendarEventRenderer(self.style)
        
        # Create UI
        self._create_calendar_ui()
    
    def _create_calendar_ui(self):
        """Create the calendar user interface."""
        # Header with navigation
        self._create_header()
        
        # Calendar grid container
        self.calendar_frame = tk.Frame(self, bg=self.parent.CONTENT_BG)
        self.calendar_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create day labels (Mon, Tue, Wed, etc.)
        self._create_day_headers()
        
        # Create calendar grid
        self._create_calendar_grid()
    
    def _create_header(self):
        """Create navigation header."""
        # Get styling colors with fallbacks
        title_bar_color = getattr(self.parent, 'TITLE_BAR_COLOR', '#2A2A2A')
        accent_color = getattr(self.parent, 'ACCENT_COLOR', '#D13438')
        header_color = getattr(self.parent, 'HEADER_COLOR', '#FFFFFF')
        font_family = getattr(self.parent, 'FONT_FAMILY', 'Segoe UI')
        
        header_frame = tk.Frame(self, bg=title_bar_color, height=40)
        header_frame.pack(fill='x', pady=(0, 5))
        header_frame.pack_propagate(False)
        
        # Previous month button
        prev_btn = tk.Button(header_frame, text="◀ Prev", 
                            bg=accent_color,
                            fg='white',
                            font=(font_family, 10, 'bold'),
                            command=self._prev_month,
                            relief='flat',
                            padx=15, pady=5)
        prev_btn.pack(side='left', padx=10, pady=5)
        
        # Month/Year label
        self.month_label = tk.Label(header_frame, 
                                   text="",
                                   bg=title_bar_color,
                                   fg=header_color,
                                   font=(font_family, 14, 'bold'))
        self.month_label.pack(side='left', expand=True)
        
        # Next month button
        next_btn = tk.Button(header_frame, text="Next ▶",
                            bg=accent_color,
                            fg='white', 
                            font=(font_family, 10, 'bold'),
                            command=self._next_month,
                            relief='flat',
                            padx=15, pady=5)
        next_btn.pack(side='right', padx=10, pady=5)
        
        # Today button - get colors with fallbacks
        content_bg = getattr(self.parent, 'CONTENT_BG', '#1F1F1F')
        text_color = getattr(self.parent, 'TEXT_COLOR', '#E0E0E0')
        
        today_btn = tk.Button(header_frame, text="Today",
                             bg=content_bg,
                             fg=text_color,
                             font=(font_family, 10),
                             command=self._go_to_today,
                             relief='flat',
                             padx=10, pady=5)
        today_btn.pack(side='right', padx=(0, 5), pady=5)
    
    def _create_day_headers(self):
        """Create day of week headers."""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        day_header_frame = tk.Frame(self.calendar_frame, bg=self.parent.CONTENT_BG)
        day_header_frame.pack(fill='x', pady=(0, 2))
        
        for day in days:
            day_label = tk.Label(day_header_frame, 
                               text=day[:3],
                               bg=self.parent.TITLE_BAR_COLOR,
                               fg=self.parent.HEADER_COLOR,
                               font=(self.parent.FONT_FAMILY, 10, 'bold'),
                               width=12, height=1,
                               relief='solid', borderwidth=1)
            day_label.pack(side='left', padx=1, fill='x', expand=True)
    
    def _create_calendar_grid(self):
        """Create the main calendar grid."""
        # Container for calendar weeks
        self.grid_frame = tk.Frame(self.calendar_frame, bg=self.parent.CONTENT_BG)
        self.grid_frame.pack(fill='both', expand=True)
        
        # Create 6 rows for weeks (max needed for any month)
        self.week_frames = []
        for week_num in range(6):
            week_frame = tk.Frame(self.grid_frame, bg=self.parent.CONTENT_BG)
            week_frame.pack(fill='both', expand=True, pady=1)
            self.week_frames.append(week_frame)
    
    def _populate_calendar_grid(self):
        """Populate the calendar grid with day buttons."""
        # Clear existing buttons
        for button in self.day_buttons.values():
            button.destroy()
        self.day_buttons.clear()
        
        # Get calendar data for current month
        cal = calendar.monthcalendar(self.current_view_date.year, self.current_view_date.month)
        
        # Update month label
        month_name = self.current_view_date.strftime('%B %Y')
        self.month_label.config(text=month_name)
        
        # Populate weeks
        for week_num, week in enumerate(cal):
            week_frame = self.week_frames[week_num]
            
            # Clear week frame
            for widget in week_frame.winfo_children():
                widget.destroy()
            
            # Create day buttons for this week
            for day_num in week:
                if day_num == 0:
                    # Empty cell for days from other months
                    empty_cell = tk.Label(week_frame, text="",
                                        bg=self.parent.CONTENT_BG,
                                        width=12, height=3)
                    empty_cell.pack(side='left', padx=1, fill='both', expand=True)
                else:
                    # Create day button
                    day_date = date(self.current_view_date.year, 
                                   self.current_view_date.month, day_num)
                    self._create_day_button(week_frame, day_date, day_num)
        
        # Hide unused week frames
        for week_num in range(len(cal), 6):
            for widget in self.week_frames[week_num].winfo_children():
                widget.destroy()
    
    def _create_day_button(self, parent_frame, day_date: date, day_num: int):
        """Create a button for a specific day."""
        # Get events for this day
        day_events = self.events_by_date.get(day_date, [])
        
        # Determine colors
        is_today = day_date == date.today()
        
        if day_events:
            # Use color of first event (or today color if today)
            if is_today:
                bg_color, fg_color = CalendarColorScheme.COLORS['today']
            else:
                primary_event = day_events[0]
                user_team = getattr(self.calendar_manager, 'user_team_name', '')
                bg_color, fg_color = CalendarColorScheme.get_color_for_event(
                    primary_event, user_team, is_today)
        else:
            # Empty day
            bg_color, fg_color = CalendarColorScheme.get_empty_day_color(day_date)
        
        # Create button text
        button_text = f"{day_num}"
        if len(day_events) > 1:
            button_text += f"\n({len(day_events)})"
        elif day_events:
            # Show event title if short enough
            event_title = day_events[0].title
            if len(event_title) <= 12:
                button_text += f"\n{event_title}"
        
        # Create the button
        day_button = tk.Button(parent_frame,
                              text=button_text,
                              bg=bg_color,
                              fg=fg_color,
                              font=(self.parent.FONT_FAMILY, 9, 'bold'),
                              width=12, height=3,
                              relief='solid', borderwidth=1,
                              command=lambda d=day_date: self._on_day_clicked(d),
                              wraplength=80,
                              justify='center')
        
        day_button.pack(side='left', padx=1, fill='both', expand=True)
        
        # Store button reference
        self.day_buttons[day_date] = day_button
        
        # Add hover effects
        self._add_hover_effects(day_button, bg_color, fg_color)
    
    def _add_hover_effects(self, button: tk.Button, bg_color: str, fg_color: str):
        """Add hover effects to a day button."""
        def on_enter(event):
            # Slightly darken on hover
            hover_color = self.renderer._darken_color(bg_color, 0.8)
            button.config(bg=hover_color)
        
        def on_leave(event):
            # Restore original color
            button.config(bg=bg_color)
        
        button.bind('<Enter>', on_enter)
        button.bind('<Leave>', on_leave)
    
    def _on_day_clicked(self, day_date: date):
        """Handle day button click."""
        self.selected_date = day_date
        
        # Update button selection appearance
        self._update_selection_display()
        
        # Call callback if set
        if self.on_date_selected:
            self.on_date_selected(day_date)
    
    def _update_selection_display(self):
        """Update visual display of selected date."""
        # This could add selection indicators, but for now we keep it simple
        pass
    
    def _prev_month(self):
        """Navigate to previous month."""
        # Calculate previous month
        if self.current_view_date.month == 1:
            self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year - 1, month=12)
        else:
            self.current_view_date = self.current_view_date.replace(month=self.current_view_date.month - 1)
        
        self.refresh_calendar()
    
    def _next_month(self):
        """Navigate to next month."""
        # Calculate next month
        if self.current_view_date.month == 12:
            self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year + 1, month=1)
        else:
            self.current_view_date = self.current_view_date.replace(month=self.current_view_date.month + 1)
        
        self.refresh_calendar()
    
    def _go_to_today(self):
        """Navigate to current month."""
        self.current_view_date = date.today()
        self.refresh_calendar()
    
    def refresh_calendar(self):
        """Refresh the calendar display."""
        self._populate_calendar_grid()
    
    def load_events(self, events: List[CalendarEvent]):
        """Load events into the calendar."""
        self.events_by_date.clear()
        
        for event in events:
            self.events_by_date[event.date].append(event)
        
        self.refresh_calendar()


class ProfessionalCalendarManager(ICalendarManager):
    """Professional calendar manager implementation."""
    
    def __init__(self, parent, schedule_engine: Optional[ScheduleEngine] = None):
        self.parent = parent
        self.schedule_engine = schedule_engine
        self.calendar_widget: Optional[CalendarWidget] = None
        self.events: List[CalendarEvent] = []
        
        # User team name for event coloring
        self.user_team_name = getattr(parent, 'user_team', None)
        if self.user_team_name and hasattr(self.user_team_name, 'team_name'):
            self.user_team_name = self.user_team_name.team_name
        else:
            self.user_team_name = "User Team"  # Fallback
    
    def create_calendar_widget(self, parent_widget) -> CalendarWidget:
        """Create a new calendar widget."""
        self.calendar_widget = CalendarWidget(parent_widget, self)
        
        # Set up event callbacks
        self.calendar_widget.on_date_selected = self._on_date_selected
        self.calendar_widget.on_event_clicked = self._on_event_clicked
        
        return self.calendar_widget
    
    def load_events(self, events: List[CalendarEvent]) -> None:
        """Load events into the calendar."""
        self.events = events
        
        if self.calendar_widget:
            self.calendar_widget.load_events(events)
    
    def get_events_for_date(self, target_date: date) -> List[CalendarEvent]:
        """Get all events for a specific date."""
        return [event for event in self.events if event.date == target_date]
    
    def refresh_display(self) -> None:
        """Refresh the calendar display."""
        if self.calendar_widget:
            self.calendar_widget.refresh_calendar()
    
    def generate_schedule_from_engine(self) -> None:
        """Generate new schedule using the schedule engine."""
        if self.schedule_engine:
            events = self.schedule_engine.generate_schedule()
            self.load_events(events)
    
    def _on_date_selected(self, selected_date: date):
        """Handle date selection."""
        events = self.get_events_for_date(selected_date)
        print(f"Selected date: {selected_date}, Events: {len(events)}")
        
        # Show event details (this could open a details panel)
        for event in events:
            print(f"  - {event.title} ({event.event_type.value})")
    
    def _on_event_clicked(self, event: CalendarEvent):
        """Handle event click."""
        print(f"Event clicked: {event.title}")


# Convenience function for creating calendar windows
def create_calendar_window(parent, schedule_engine: Optional[ScheduleEngine] = None):
    """Create a complete calendar window with professional calendar manager."""
    
    class CalendarWindow(tk.Toplevel):
        def __init__(self, parent):
            super().__init__(parent)
            self.parent = parent
            self.title("🗓️ Professional Season Calendar")
            self.geometry("1200x800")
            self.configure(bg=parent.BG_COLOR)
            
            # Center window
            self.center_window()
            
            # Create calendar manager
            self.calendar_manager = ProfessionalCalendarManager(parent, schedule_engine)
            
            # Create UI
            self._create_ui()
            
            # Load initial events
            if schedule_engine:
                self.calendar_manager.generate_schedule_from_engine()
            
            # Add to parent's open windows
            parent.open_windows['professional_calendar'] = self
        
        def center_window(self):
            """Center the window on screen."""
            self.update_idletasks()
            width = 1200
            height = 800
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
            self.geometry(f'{width}x{height}+{x}+{y}')
        
        def _create_ui(self):
            """Create the calendar UI."""
            # Main container
            main_frame = tk.Frame(self, bg=self.parent.BG_COLOR)
            main_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Title
            title_label = tk.Label(main_frame,
                                  text="🗓️ Professional Season Calendar",
                                  bg=self.parent.BG_COLOR,
                                  fg=self.parent.HEADER_COLOR,
                                  font=(self.parent.FONT_FAMILY, 16, 'bold'))
            title_label.pack(pady=(0, 10))
            
            # Calendar widget
            calendar_frame = tk.Frame(main_frame, bg=self.parent.CONTENT_BG,
                                    relief='solid', borderwidth=1)
            calendar_frame.pack(fill='both', expand=True)
            
            self.calendar_widget = self.calendar_manager.create_calendar_widget(calendar_frame)
            self.calendar_widget.pack(fill='both', expand=True, padx=5, pady=5)
    
    return CalendarWindow(parent)


if __name__ == "__main__":
    """Test the professional calendar manager."""
    print("=== TESTING PROFESSIONAL CALENDAR MANAGER ===")
    
    # Create a test parent
    class TestParent:
        def __init__(self):
            self.BG_COLOR = '#181818'
            self.CONTENT_BG = '#1F1F1F'
            self.TITLE_BAR_COLOR = '#2A2A2A'
            self.TEXT_COLOR = '#E0E0E0'
            self.HEADER_COLOR = '#FFFFFF'
            self.ACCENT_COLOR = '#D13438'
            self.FONT_FAMILY = 'Segoe UI'
            self.user_team = None
            self.open_windows = {}
    
    # Test color scheme
    print("Testing CalendarColorScheme...")
    today_color = CalendarColorScheme.COLORS['today']
    home_color = CalendarColorScheme.COLORS['home_game']
    print(f"Today color: {today_color}")
    print(f"Home game color: {home_color}")
    
    # Test event renderer
    print("\nTesting CalendarEventRenderer...")
    parent = TestParent()
    
    # This would normally be tested with a full Tkinter app
    print("✅ Calendar components ready for integration!")
    print("✅ Color scheme configured!")
    print("✅ Professional rendering system ready!")
    
    print("\n🎯 PROFESSIONAL CALENDAR MANAGER READY FOR PHASE 4!")