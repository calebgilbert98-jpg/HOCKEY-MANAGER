#!/usr/bin/env python3
"""
Test NHL special events scheduling and calendar display.
"""

import sys
import os
from datetime import date, timedelta

# Add the project directory to sys.path
project_dir = r"c:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER"
if project_dir not in sys.path:
    sys.path.append(project_dir)

def test_nhl_events_scheduling():
    """Test that NHL special events are properly scheduled and displayed."""
    print("=== TESTING NHL SPECIAL EVENTS SCHEDULING ===\n")
    
    try:
        from main import GameManager
        
        print("Step 1: Creating GameManager with startup settings...")
        gm = GameManager()
        
        # Apply startup settings to trigger database generation and scheduling
        startup_settings = {
            'database_size': 'Small',
            'fantasy_draft': False,
            'start_date': '2024-10-01',
            'salary_cap': True,
            'selected_team': 'Boston Bruins'
        }
        
        print("Applying startup settings...")
        gm.apply_startup_settings(startup_settings)
        
        # Get the schedule
        schedule = gm.league.schedule
        print(f"Total schedule entries: {len(schedule)}")
        
        # Look for NHL special events in the schedule
        nhl_events = []
        game_events = []
        
        for entry in schedule:
            if len(entry) == 3:
                game_date, home_team, away_team = entry
                
                if home_team == 'NHL_EVENT':
                    nhl_events.append((game_date, away_team))  # away_team contains event data
                else:
                    game_events.append((game_date, home_team, away_team))
            elif len(entry) == 4:
                # Handle 4-element entries (likely NHL events with additional data)
                game_date, home_team, away_team, additional_data = entry
                
                if home_team == 'NHL_EVENT':
                    nhl_events.append((game_date, away_team))  # away_team contains event data
                else:
                    game_events.append((game_date, home_team, away_team))
        
        print(f"Regular games: {len(game_events)}")
        print(f"NHL special events: {len(nhl_events)}")
        
        if nhl_events:
            print("\n✅ NHL Special Events Found:")
            for event_date, event_data in sorted(nhl_events):
                print(f"  {event_date}: {event_data['title']}")
                print(f"    Type: {event_data['type']}")
                print(f"    Description: {event_data['description']}")
                print()
        else:
            print("❌ No NHL special events found in schedule!")
            return False
        
        # Test calendar integration
        print("Step 2: Testing calendar integration...")
        import tkinter as tk
        from calendar_window import CalendarWindow
        
        # Create minimal parent for testing
        class TestParent(tk.Tk):
            def __init__(self):
                super().__init__()
                self.withdraw()
                
                # Styling attributes
                self.BG_COLOR = '#181818'
                self.CONTENT_BG = '#1F1F1F'
                self.TITLE_BAR_COLOR = '#2A2A2A'
                self.TEXT_COLOR = '#E0E0E0'
                self.HEADER_COLOR = '#FFFFFF'
                self.ACCENT_COLOR = '#D13438'
                self.ACCENT_ACTIVE = '#A1272A'
                self.FONT_FAMILY = 'Segoe UI'
                
                # Game data
                self.current_date = date(2024, 10, 15)
                self.league = gm.league
                self.user_team = gm.user_team if gm.user_team else gm.league.teams[0]
                self.game_results = []
                self.open_windows = {}
        
        parent = TestParent()
        
        print("Creating calendar window...")
        calendar_window = CalendarWindow(parent)
        
        # Check if NHL events are loaded in calendar
        total_events = sum(len(events) for events in calendar_window.events_by_date.values())
        print(f"Total calendar events loaded: {total_events}")
        
        # Check for NHL event types
        nhl_event_types = {}
        for events in calendar_window.events_by_date.values():
            for event in events:
                if event['type'] in ['all_star_skills', 'all_star_game', 'trade_deadline', 
                                   'entry_draft', 'free_agency']:
                    event_type = event['type']
                    nhl_event_types[event_type] = nhl_event_types.get(event_type, 0) + 1
        
        if nhl_event_types:
            print("\n✅ NHL Events in Calendar:")
            for event_type, count in nhl_event_types.items():
                print(f"  {event_type}: {count}")
        else:
            print("❌ No NHL events found in calendar!")
        
        # Find specific events for verification
        print("\n🔍 Checking specific events...")
        
        # Look for All-Star events (January 2025)
        all_star_dates = []
        for event_date, events in calendar_window.events_by_date.items():
            if event_date.year == 2025 and event_date.month in [1, 2]:
                for event in events:
                    if event['type'] in ['all_star_skills', 'all_star_game']:
                        all_star_dates.append((event_date, event['title']))
        
        if all_star_dates:
            print("All-Star Events:")
            for event_date, title in sorted(all_star_dates):
                print(f"  {event_date}: {title}")
        
        # Look for Trade Deadline (March 2025)
        trade_deadline_events = []
        for event_date, events in calendar_window.events_by_date.items():
            if event_date.year == 2025 and event_date.month == 3:
                for event in events:
                    if event['type'] == 'trade_deadline':
                        trade_deadline_events.append((event_date, event['title']))
        
        if trade_deadline_events:
            print("Trade Deadline:")
            for event_date, title in sorted(trade_deadline_events):
                print(f"  {event_date}: {title}")
        
        calendar_window.destroy()
        parent.destroy()
        
        print("\n✅ NHL special events scheduling test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_nhl_events_scheduling()
    if success:
        print("\n🎉 NHL EVENTS SCHEDULING TEST PASSED!")
    else:
        print("\n💥 NHL EVENTS SCHEDULING TEST FAILED!")
        sys.exit(1)