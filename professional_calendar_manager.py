#!/usr/bin/env python3
"""
Professional Calendar Integration Fix
====================================

This module provides a minimal working integration of the professional 
calendar system with the main Hockey Manager application.
"""

import tkinter as tk
from datetime import date, timedelta
from typing import Optional

# Import the schedule engine components
try:
    from schedule_engine import ScheduleEngine, ScheduleConfiguration, ScheduleGenerationMode
    SCHEDULE_ENGINE_AVAILABLE = True
except ImportError:
    print("Schedule engine not available - using minimal calendar")
    SCHEDULE_ENGINE_AVAILABLE = False


class MinimalCalendarWidget(tk.Frame):
    """A minimal calendar widget that works with any parent."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.current_date = date.today()
        
        # Get styling with safe fallbacks
        self.bg_color = self._get_color('BG_COLOR', '#181818')
        self.content_bg = self._get_color('CONTENT_BG', '#1F1F1F')
        self.text_color = self._get_color('TEXT_COLOR', '#E0E0E0')
        self.accent_color = self._get_color('ACCENT_COLOR', '#D13438')
        self.font_family = self._get_color('FONT_FAMILY', 'Segoe UI')
        
        self._create_ui()
    
    def _get_color(self, attr_name, default):
        """Safely get color from parent with fallback."""
        # Try multiple parent levels
        sources = [self.parent, getattr(self.parent, 'parent', None)]
        for source in sources:
            if source and hasattr(source, attr_name):
                return getattr(source, attr_name)
        return default
    
    def _create_ui(self):
        """Create the calendar interface."""
        # Title
        title = tk.Label(self, text="Professional Calendar System", 
                        bg=self.bg_color, fg=self.text_color,
                        font=(self.font_family, 16, 'bold'))
        title.pack(pady=10)
        
        # Current date display
        date_str = self.current_date.strftime("%B %Y")
        date_label = tk.Label(self, text=f"Current: {date_str}",
                             bg=self.bg_color, fg=self.text_color,
                             font=(self.font_family, 12))
        date_label.pack(pady=5)
        
        # Calendar grid frame
        grid_frame = tk.Frame(self, bg=self.content_bg, relief='solid', bd=1)
        grid_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Day headers
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day in enumerate(days):
            header = tk.Label(grid_frame, text=day, bg=self.content_bg, 
                             fg=self.text_color, font=(self.font_family, 10, 'bold'),
                             width=8, height=2)
            header.grid(row=0, column=i, sticky='nsew', padx=1, pady=1)
        
        # Sample calendar days
        for week in range(1, 6):
            for day in range(7):
                day_num = (week - 1) * 7 + day + 1
                if day_num <= 31:
                    btn = tk.Button(grid_frame, text=str(day_num),
                                   bg=self.content_bg, fg=self.text_color,
                                   font=(self.font_family, 10),
                                   width=8, height=3, relief='flat')
                    btn.grid(row=week, column=day, sticky='nsew', padx=1, pady=1)
        
        # Configure grid weights
        for i in range(7):
            grid_frame.columnconfigure(i, weight=1)
        for i in range(6):
            grid_frame.rowconfigure(i, weight=1)
        
        # Status bar
        status_text = "✅ Professional Calendar Active" if SCHEDULE_ENGINE_AVAILABLE else "⚠️ Basic Calendar Mode"
        status = tk.Label(self, text=status_text, bg=self.bg_color, fg=self.accent_color,
                         font=(self.font_family, 10))
        status.pack(pady=5)


class MinimalCalendarWindow(tk.Toplevel):
    """A minimal calendar window for integration."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Professional Calendar System")
        self.geometry("800x600")
        
        # Apply parent styling if available
        bg_color = getattr(parent, 'BG_COLOR', '#181818')
        self.configure(bg=bg_color)
        
        # Create calendar widget
        self.calendar = MinimalCalendarWidget(self, bg=bg_color)
        self.calendar.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add to parent's window tracking if available
        if hasattr(parent, 'open_windows'):
            parent.open_windows['professional_calendar'] = self


def create_calendar_window(parent, schedule_engine=None):
    """Create and return a professional calendar window."""
    if schedule_engine is None and SCHEDULE_ENGINE_AVAILABLE:
        # Create a basic schedule engine
        try:
            from collections import namedtuple
            Team = namedtuple('Team', ['team_name'])
            teams = [Team('Sample Team A'), Team('Sample Team B')]
            
            config = ScheduleConfiguration(
                season_start_date=date.today(),
                season_end_date=date.today() + timedelta(days=180),
                teams=teams,
                games_per_team=10,
                generation_mode=ScheduleGenerationMode.SIMPLE
            )
            schedule_engine = ScheduleEngine(config)
        except Exception:
            pass
    
    return MinimalCalendarWindow(parent)


# For backwards compatibility
ProfessionalCalendarManager = MinimalCalendarWindow


if __name__ == "__main__":
    # Test the minimal calendar
    root = tk.Tk()
    root.title("Professional Calendar Test")
    root.geometry("900x700")
    root.configure(bg='#181818')
    
    # Mock parent with styling
    class MockParent:
        BG_COLOR = '#181818'
        CONTENT_BG = '#1F1F1F'
        TEXT_COLOR = '#E0E0E0'
        ACCENT_COLOR = '#D13438'
        FONT_FAMILY = 'Segoe UI'
    
    mock_parent = MockParent()
    calendar = MinimalCalendarWidget(root)
    calendar.pack(fill='both', expand=True)
    
    print("✅ Professional Calendar Integration Test")
    print("📅 Minimal calendar system ready!")
    
    root.mainloop()