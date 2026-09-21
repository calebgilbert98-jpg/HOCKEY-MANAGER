#!/usr/bin/env python3
"""Simple test for consecutive games fix - no Unicode characters."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League

def test_consecutive_games_fix():
    """Test that the consecutive games fix works correctly."""
    print("TESTING CONSECUTIVE GAMES FIX")
    print("=" * 50)
    
    # Create test league
    league = League("Test League")
    
    # Generate teams (no player generation to keep it fast)
    from game_classes import Team
    
    # Create minimal test with just a few teams
    teams_data = {
        "Eastern_Metropolitan": [
            "Carolina Hurricanes", "New Jersey Devils", "New York Rangers", "Pittsburgh Penguins",
            "Columbus Blue Jackets", "New York Islanders", "Philadelphia Flyers", "Washington Capitals"
        ],
        "Eastern_Atlantic": [
            "Boston Bruins", "Buffalo Sabres", "Detroit Red Wings", "Florida Panthers",
            "Montreal Canadiens", "Ottawa Senators", "Tampa Bay Lightning", "Toronto Maple Leafs"
        ],
        "Western_Central": [
            "Chicago Blackhawks", "Colorado Avalanche", "Dallas Stars", "Minnesota Wild",
            "Nashville Predators", "St. Louis Blues", "Utah Hockey Club", "Winnipeg Jets"
        ],
        "Western_Pacific": [
            "Anaheim Ducks", "Calgary Flames", "Edmonton Oilers", "Los Angeles Kings",
            "San Jose Sharks", "Seattle Kraken", "Vancouver Canucks", "Vegas Golden Knights"
        ]
    }
    
    for division, team_names in teams_data.items():
        conference = "Eastern" if division.startswith("Eastern") else "Western"
        for team_name in team_names:
            team = Team(team_name, team_name.split()[-1], division, conference)
            league.add_team(team)
    
    print(f"Created league with {len(league.teams)} teams")
    
    # Generate schedule
    print("Generating schedule...")
    league.generate_schedule(season_year=2024, rotation_seed=2024)
    
    # Analyze consecutive games
    print("\nAnalyzing consecutive games...")
    
    # Group games by team
    team_schedules = {}
    for date, home_team, away_team in league.schedule:
        if isinstance(home_team, str):  # Skip NHL events
            continue
            
        # Add to home team schedule
        if home_team.team_name not in team_schedules:
            team_schedules[home_team.team_name] = []
        team_schedules[home_team.team_name].append((date, 'HOME', away_team.team_name))
        
        # Add to away team schedule  
        if away_team.team_name not in team_schedules:
            team_schedules[away_team.team_name] = []
        team_schedules[away_team.team_name].append((date, 'AWAY', home_team.team_name))
    
    # Check for consecutive games
    teams_with_3plus = 0
    max_consecutive = 0
    
    for team_name, schedule in team_schedules.items():
        # Sort by date
        schedule.sort(key=lambda x: x[0])
        
        # Find longest consecutive streak
        consecutive_count = 1
        max_team_consecutive = 1
        
        for i in range(1, len(schedule)):
            prev_date = schedule[i-1][0]
            curr_date = schedule[i][0]
            
            if (curr_date - prev_date).days == 1:
                consecutive_count += 1
                max_team_consecutive = max(max_team_consecutive, consecutive_count)
            else:
                consecutive_count = 1
        
        if max_team_consecutive >= 3:
            teams_with_3plus += 1
            print(f"  {team_name}: {max_team_consecutive} consecutive games")
        
        max_consecutive = max(max_consecutive, max_team_consecutive)
    
    print(f"\nResults:")
    print(f"  Teams with 3+ consecutive games: {teams_with_3plus}/32")
    print(f"  Maximum consecutive games by any team: {max_consecutive}")
    print(f"  Total games scheduled: {len([g for g in league.schedule if not isinstance(g[1], str)])}")
    
    if teams_with_3plus == 0:
        print("SUCCESS: No teams have 3+ consecutive games!")
    elif teams_with_3plus <= 5:
        print("GOOD: Very few teams have 3+ consecutive games")
    else:
        print("NEEDS WORK: Too many teams still have 3+ consecutive games")
    
    return teams_with_3plus == 0

if __name__ == "__main__":
    success = test_consecutive_games_fix()
    if success:
        print("\nConsecutive games fix is working!")
    else:
        print("\nConsecutive games fix needs more work")