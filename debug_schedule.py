#!/usr/bin/env python3
"""
Debug NHL schedule generation - smaller test
"""

import sys
import os
project_dir = r"c:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER"
if project_dir not in sys.path:
    sys.path.append(project_dir)

def debug_schedule():
    """Debug schedule generation with a smaller test"""
    print("=== DEBUGGING NHL SCHEDULE GENERATION ===\n")
    
    try:
        from game_classes import League, Team
        from datetime import date
        
        # Create a minimal test with just 4 NHL teams
        print("Creating test league with 4 NHL teams...")
        
        # Create test teams
        teams = []
        for i, name in enumerate(['Team A', 'Team B', 'Team C', 'Team D']):
            team = Team(
                team_name=name,
                city=name,
                conference='Eastern' if i < 2 else 'Western',
                division='Metro' if i < 2 else 'Central',
                league_name='National Hockey League'
            )
            teams.append(team)
        
        print(f"Created {len(teams)} teams")
        
        # Create league
        league = League("NHL", teams, 2024)
        
        # Clear schedule and generate new one
        league.schedule.clear()
        print("\nGenerating schedule...")
        
        # Call the league method directly
        league._generate_league_schedule(teams, "National Hockey League")
        
        print(f"Generated {len(league.schedule)} games")
        
        # Run verification
        league._verify_schedule_integrity()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_schedule()