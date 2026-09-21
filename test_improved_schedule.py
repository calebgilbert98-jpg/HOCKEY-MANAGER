#!/usr/bin/env python3
"""
Test improved NHL schedule generation system
"""

import sys
import os

# Add the project directory to sys.path
project_dir = r"c:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER"
if project_dir not in sys.path:
    sys.path.append(project_dir)

def test_schedule_generation():
    """Test the improved NHL schedule generation"""
    print("=== TESTING IMPROVED NHL SCHEDULE GENERATION ===\n")
    
    try:
        from main import GameManager
        
        print("Step 1: Creating GameManager with improved scheduling...")
        gm = GameManager()
        
        # Get NHL teams for testing
        nhl_teams = [team for team in gm.league.teams 
                    if getattr(team, 'league_name', '') == 'National Hockey League']
        
        print(f"Found {len(nhl_teams)} NHL teams")
        
        if len(nhl_teams) >= 4:  # Test with subset for faster results
            print(f"Step 2: Testing schedule generation with {len(nhl_teams)} NHL teams...")
            
            # Clear existing schedule
            gm.league.schedule.clear()
            
            # Generate new schedule using improved algorithm
            print("Generating schedule with new NHL-compliant algorithm...")
            gm.league.generate_schedule()
            
            print(f"\nStep 3: Schedule generated successfully!")
            print(f"Total games in league schedule: {len(gm.league.schedule)}")
            
            # The verification report will be printed automatically
            # by the new _verify_schedule_integrity method
            
        else:
            print("❌ Not enough NHL teams found for meaningful test")
            
    except Exception as e:
        print(f"❌ Error during schedule generation test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_schedule_generation()