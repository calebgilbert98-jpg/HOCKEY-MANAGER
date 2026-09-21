"""
Quick test to launch the main application and verify NHL events are visible in the calendar.
"""

import sys
import os
from datetime import date

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_calendar_visual():
    """Launch the main app and open calendar to verify NHL events are visible."""
    try:
        print("🚀 Testing NHL Events in Main Application Calendar...")
        
        from main import main
        from main_menu import HockeyManagerGUI
        
        # Create the main application
        print("Creating main application...")
        app = HockeyManagerGUI()
        
        # Apply quick startup settings for testing
        startup_settings = {
            'database_size': 'Small',
            'fantasy_draft': False,
            'start_date': '2024-10-01',
            'salary_cap': True,
            'selected_team': 'Boston Bruins'
        }
        
        print("Applying startup settings...")
        app.game_manager.apply_startup_settings(startup_settings)
        
        # Verify NHL events in the league schedule
        schedule = app.game_manager.league.schedule
        nhl_events = []
        
        for entry in schedule:
            if len(entry) >= 3:
                if len(entry) == 3:
                    game_date, home_team, away_team = entry
                elif len(entry) == 4:
                    game_date, home_team, away_team, _ = entry
                
                if home_team == 'NHL_EVENT':
                    nhl_events.append((game_date, away_team))
        
        print(f"✅ Found {len(nhl_events)} NHL special events in the schedule:")
        for event_date, event_data in sorted(nhl_events):
            print(f"  {event_date}: {event_data.get('title', 'Unknown Event')}")
        
        # Auto-open calendar window
        print("Opening calendar window...")
        app.open_calendar_window()
        
        print("Calendar opened! NHL events should be visible with color coding:")
        print("  🌟 All-Star Events: Gold")
        print("  📈 Trade Deadline: Red")
        print("  🏆 Entry Draft: Purple")
        print("  💰 Free Agency: Green")
        print("  🏒 Home Games: Blue")
        print("  ✈️ Away Games: Cyan")
        
        # Set window title to indicate test mode
        app.title("Puck Dynasty - NHL Events Test Mode")
        
        # Start the application
        app.mainloop()
        
    except Exception as e:
        print(f"❌ Error launching test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_calendar_visual()