#!/usr/bin/env python3
"""Test the actual game app to check consecutive games at start."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import GameManager
from datetime import date

def test_actual_app_consecutive_games():
    """Test consecutive games in the actual app at startup."""
    print("TESTING CONSECUTIVE GAMES IN ACTUAL APP")
    print("=" * 50)
    
    # Create GameManager like the real app does
    print("Creating GameManager...")
    gm = GameManager()
    
    # Check if user team has consecutive games at the start
    if not gm.user_team:
        print("No user team found")
        return
    
    team_name = gm.user_team.team_name
    print(f"User team: {team_name}")
    print(f"Current date: {gm.current_date}")
    
    # Get team schedule from league
    team_schedule = []
    
    if gm.league and hasattr(gm.league, 'schedule'):
        for date, home_team, away_team in gm.league.schedule:
            if isinstance(home_team, str):  # Skip NHL events
                continue
                
            if home_team.team_name == team_name:
                team_schedule.append((date, 'HOME', away_team.team_name))
            elif away_team.team_name == team_name:
                team_schedule.append((date, 'AWAY', home_team.team_name))
        
        # Sort by date
        team_schedule.sort(key=lambda x: x[0])
        
        print(f"Team has {len(team_schedule)} games scheduled")
        
        # Look at games around current date
        current_date = gm.current_date
        print(f"\nGames around current date ({current_date}):")
        
        # Find games within 10 days of current date
        nearby_games = []
        for game_date, venue, opponent in team_schedule:
            days_diff = abs((game_date - current_date).days)
            if days_diff <= 10:
                nearby_games.append((game_date, venue, opponent, days_diff))
        
        # Sort by date
        nearby_games.sort(key=lambda x: x[0])
        
        for game_date, venue, opponent, days_diff in nearby_games:
            status = "TODAY" if days_diff == 0 else f"{days_diff} days"
            print(f"  {game_date} ({status}): {venue} vs {opponent}")
        
        # Check for consecutive games at the start
        print("\nChecking for consecutive games from start of season:")
        consecutive_count = 1
        max_consecutive = 1
        
        for i in range(1, min(10, len(team_schedule))):  # Check first 10 games
            prev_date = team_schedule[i-1][0]
            curr_date = team_schedule[i][0]
            
            if (curr_date - prev_date).days == 1:
                consecutive_count += 1
                max_consecutive = max(max_consecutive, consecutive_count)
                print(f"  Games {i} and {i+1}: {prev_date} -> {curr_date} (consecutive)")
            else:
                if consecutive_count > 1:
                    print(f"  Consecutive streak ended at {consecutive_count} games")
                consecutive_count = 1
        
        if max_consecutive >= 3:
            print(f"\nWARNING: Team has {max_consecutive} consecutive games at season start!")
            print("This explains why you saw 3 games in a row immediately.")
        else:
            print(f"\nTeam's max consecutive games at start: {max_consecutive}")
    
    else:
        print("No league schedule found")

if __name__ == "__main__":
    test_actual_app_consecutive_games()