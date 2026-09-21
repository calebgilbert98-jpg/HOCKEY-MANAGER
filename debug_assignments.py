#!/usr/bin/env python3
"""
Debug exactly what games each team is getting assigned.
"""

import sys
sys.path.append('.')

def debug_nhl_assignments():
    print("🔍 DEBUGGING NHL GAME ASSIGNMENTS")
    print("=" * 50)
    
    from game_classes import League
    
    # Create a simple test with just a few teams
    league = League(league_name='NHL')
    nhl_teams = [t for t in league.teams if t.league_name == 'National Hockey League']
    
    # Get first team from each division for testing
    test_teams = []
    divisions_seen = set()
    
    for team in nhl_teams:
        div_key = (team.conference, team.division)
        if div_key not in divisions_seen:
            test_teams.append(team)
            divisions_seen.add(div_key)
            if len(test_teams) >= 4:  # One from each division
                break
    
    print(f"Test teams:")
    for team in test_teams:
        print(f"  {team.team_name} ({team.conference} {team.division})")
    
    # Test the assignment functions manually
    divisions = {}
    for team in nhl_teams:
        div_key = f"{team.conference}_{team.division}"
        if div_key not in divisions:
            divisions[div_key] = []
        divisions[div_key].append(team)
    
    print(f"\nDivisions:")
    for div_name, teams in divisions.items():
        print(f"  {div_name}: {len(teams)} teams")
    
    # Test just one team's assignments
    test_team = test_teams[0]  # Boston Bruins (Eastern Atlantic)
    print(f"\n🎯 Testing assignments for {test_team.team_name}:")
    
    matchup_assignments = {test_team.team_name: []}
    
    # 1. Divisional games
    div_teams = divisions['Eastern_Atlantic']
    div_rivals = [t for t in div_teams if t != test_team]
    print(f"\nDivision rivals (should be 7): {len(div_rivals)}")
    for rival in div_rivals:
        print(f"  vs {rival.team_name}: 4 games")
        # 4 games each = 28 total divisional games
        for _ in range(2):
            matchup_assignments[test_team.team_name].append(('HOME', rival))
        for _ in range(2):
            matchup_assignments[test_team.team_name].append(('AWAY', rival))
    
    divisional_games = len([g for g in matchup_assignments[test_team.team_name]])
    print(f"Total divisional games assigned: {divisional_games}")
    
    # 2. Conference games (Eastern Metropolitan)
    metro_teams = divisions['Eastern_Metropolitan']
    print(f"\nConference rivals (should be 8): {len(metro_teams)}")
    
    # Assign 22 games total against 8 teams: 6×3 + 2×2 = 22
    games_assigned = 0
    target_games = 22
    
    for i, metro_team in enumerate(metro_teams):
        remaining_teams = len(metro_teams) - i
        remaining_games = target_games - games_assigned
        
        if remaining_games > remaining_teams * 2:
            games = 3
        else:
            games = 2
            
        games = min(games, remaining_games)
        games_assigned += games
        
        print(f"  vs {metro_team.team_name}: {games} games")
        
        # Add to assignments
        home_games = (games + 1) // 2
        away_games = games // 2
        for _ in range(home_games):
            matchup_assignments[test_team.team_name].append(('HOME', metro_team))
        for _ in range(away_games):
            matchup_assignments[test_team.team_name].append(('AWAY', metro_team))
    
    conference_games = len([g for g in matchup_assignments[test_team.team_name]]) - divisional_games
    print(f"Total conference games assigned: {conference_games}")
    
    # 3. Interconference games (all Western teams)
    western_teams = divisions['Western_Central'] + divisions['Western_Pacific']
    print(f"\nWestern Conference teams (should be 16): {len(western_teams)}")
    
    for west_team in western_teams:
        # 2 games each: 1 home, 1 away
        matchup_assignments[test_team.team_name].append(('HOME', west_team))
        matchup_assignments[test_team.team_name].append(('AWAY', west_team))
        print(f"  vs {west_team.team_name}: 2 games")
    
    interconference_games = len([g for g in matchup_assignments[test_team.team_name]]) - divisional_games - conference_games
    print(f"Total interconference games assigned: {interconference_games}")
    
    # Final tally
    total_games = len(matchup_assignments[test_team.team_name])
    print(f"\n📊 FINAL TALLY FOR {test_team.team_name}:")
    print(f"  Divisional: {divisional_games} games")
    print(f"  Conference: {conference_games} games")
    print(f"  Interconference: {interconference_games} games")
    print(f"  TOTAL: {total_games} games")
    print(f"  TARGET: 82 games")
    
    if total_games == 82:
        print("✅ PERFECT 82-GAME ASSIGNMENT!")
    else:
        print(f"❌ Missing {82 - total_games} games")

if __name__ == "__main__":
    debug_nhl_assignments()