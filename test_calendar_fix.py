#!/usr/bin/env python3
"""
Test script to verify calendar system works with new schedule format
"""

import tkinter as tk
from datetime import date
from collections import namedtuple

# Mock the required components
class MockParent(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        
        # Required styling attributes
        self.BG_COLOR = '#181818'
        self.CONTENT_BG = '#1F1F1F'
        self.TITLE_BAR_COLOR = '#2A2A2A'
        self.TEXT_COLOR = '#E0E0E0'
        self.HEADER_COLOR = '#FFFFFF'
        self.ACCENT_COLOR = '#D13438'
        self.ACCENT_ACTIVE = '#A1272A'
        self.FONT_FAMILY = 'Segoe UI'
        
        # Mock game data with NEW dictionary format
        Team = namedtuple('Team', ['team_name', 'city'])
        self.user_team = Team('Ottawa Senators', 'Ottawa')
        self.current_date = date(2024, 10, 15)
        
        # Create mock schedule using NEW format (dictionaries)
        mock_schedule = [
            {
                'date': date(2024, 10, 16),
                'home_team': self.user_team,
                'away_team': Team('Toronto Maple Leafs', 'Toronto'),
                'time': '7:00 PM',
                'league': 'NHL'
            },
            {
                'date': date(2024, 10, 18),
                'home_team': Team('Montreal Canadiens', 'Montreal'),
                'away_team': self.user_team,
                'time': '7:30 PM',
                'league': 'NHL'
            },
            # Add old format for compatibility test
            (date(2024, 10, 20), 'NHL_EVENT', {
                'type': 'trade_deadline',
                'title': 'Trade Deadline',
                'description': 'NHL Trade Deadline'
            })
        ]
        
        League = namedtuple('League', ['schedule'])
        self.league = League(schedule=mock_schedule)
        self.game_results = []
        self.open_windows = {}

def test_calendar_with_new_format():
    """Test that calendar works with new dictionary format"""
    print("Testing calendar with new schedule format...")
    
    try:
        from calendar_window import CalendarWindow
        
        parent = MockParent()
        calendar_window = CalendarWindow(parent)
        
        print("✅ Calendar window created successfully!")
        print(f"✅ Events loaded: {len(calendar_window.events_by_date)}")
        
        # Check that events were properly loaded
        for event_date, events in calendar_window.events_by_date.items():
            print(f"   {event_date}: {len(events)} events")
            for event in events:
                print(f"     - {event['type']}: {event['title']}")
        
        calendar_window.destroy()
        parent.destroy()
        
        print("✅ NEW SCHEDULE FORMAT COMPATIBILITY: SUCCESS!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_calendar_with_new_format()
    if success:
        print("\n🎉 Calendar system is now compatible with new schedule format!")
    else:
        print("\n💥 Calendar system still has issues!")