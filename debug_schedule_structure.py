#!/usr/bin/env python3
"""Debug the matchup assignment structure to understand the data format."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League

def debug_matchup_structure():
    """Debug the matchup assignment structure."""
    print("=" * 80)
    print("🔍 DEBUGGING MATCHUP ASSIGNMENT STRUCTURE") 
    print("=" * 80)
    
    # Create test league
    league = League("Test League")
    
    # Add a couple teams to see the structure
    from game_classes import Team
    team1 = Team("Team A", "City A", "Division 1", "Eastern")
    team2 = Team("Team B", "City B", "Division 1", "Eastern") 
    team1.generate_random_players()
    team2.generate_random_players()
    
    league.add_team(team1)
    league.add_team(team2)
    
    print(f"🏒 Created test league with {len(league.teams)} teams")
    
    # Generate a schedule to see the structure
    schedule = league.generate_schedule(season_year=2024, rotation_seed=2024)
    
    # Look at first few games to understand structure
    print(f"\n📋 Schedule structure: {type(schedule)}")
    
    if hasattr(schedule, 'items') and callable(schedule.items):
        # It's a dictionary
        print(f"🔍 Schedule keys: {list(schedule.keys())}")
        
        for key, value in list(schedule.items())[:3]:  # First 3 items
            print(f"\n📅 {key}:")
            print(f"   Type: {type(value)}")
            if isinstance(value, list):
                print(f"   Length: {len(value)}")
                if value:
                    print(f"   First item: {value[0]}")
                    print(f"   First item type: {type(value[0])}")
            else:
                print(f"   Value: {value}")
                
    elif isinstance(schedule, list):
        # It's a list
        print(f"📋 Schedule length: {len(schedule)}")
        if schedule:
            print(f"🔍 First game: {schedule[0]}")
            print(f"   Type: {type(schedule[0])}")
            
            # If it's a Game object, check its attributes
            if hasattr(schedule[0], '__dict__'):
                print(f"   Attributes: {schedule[0].__dict__}")
    
    else:
        print(f"📋 Schedule: {schedule}")
        print(f"   Type: {type(schedule)}")

if __name__ == "__main__":
    debug_matchup_structure()