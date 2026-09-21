#!/usr/bin/env python3
"""Test to debug the consecutive games prevention logic step by step."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League
from datetime import date

def test_consecutive_prevention_logic():
    """Test the consecutive games prevention logic in detail."""
    print("DEBUGGING CONSECUTIVE GAMES PREVENTION LOGIC")
    print("=" * 60)
    
    # First, let me create a minimal test to see what's happening
    # I'll patch the scheduling method to add debug prints
    
    original_schedule_game = League._schedule_game_realistic
    
    def debug_schedule_game(self, home_team, away_team, available_dates, daily_games, 
                          max_per_day, team_tracking, matchup):
        """Debug version of _schedule_game_realistic with prints."""
        home_track = team_tracking[home_team.team_name]
        away_track = team_tracking[away_team.team_name]
        
        print(f"\nTrying to schedule: {home_team.team_name} vs {away_team.team_name}")
        print(f"  Home team consecutive_games: {home_track.get('consecutive_games', 0)}")
        print(f"  Away team consecutive_games: {away_track.get('consecutive_games', 0)}")
        
        # Call original method
        result = original_schedule_game(self, home_team, away_team, available_dates, 
                                      daily_games, max_per_day, team_tracking, matchup)
        
        if result:
            scheduled_date, _, _ = result
            print(f"  ✅ SCHEDULED on {scheduled_date}")
            print(f"  Home team consecutive_games after: {home_track.get('consecutive_games', 0)}")
            print(f"  Away team consecutive_games after: {away_track.get('consecutive_games', 0)}")
        else:
            print(f"  ❌ COULD NOT SCHEDULE")
        
        return result
    
    # Monkey patch for debugging
    League._schedule_game_realistic = debug_schedule_game
    
    try:
        print("Creating league with debug mode...")
        league = League("NHL")
        
        # Let's just generate a small portion of the schedule to see the logic
        print("\nGenerating schedule with debug output...")
        print("(Only showing first few scheduling attempts)\n")
        
        # This will show us exactly what's happening in the scheduling logic
        league.generate_schedule()
        
    finally:
        # Restore original method
        League._schedule_game_realistic = original_schedule_game
    
    print("\nDEBUG TEST COMPLETED")

if __name__ == "__main__":
    test_consecutive_prevention_logic()