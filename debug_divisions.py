#!/usr/bin/env python3
"""
Check the actual NHL division assignments in our data.
"""

import sys
sys.path.append('.')

def check_nhl_divisions():
    print("🔍 CHECKING NHL DIVISION ASSIGNMENTS")
    print("=" * 50)
    
    from game_classes import League
    
    league = League(league_name='NHL')
    nhl_teams = [t for t in league.teams if t.league_name == 'National Hockey League']
    
    # Group by conference and division
    divisions = {}
    for team in nhl_teams:
        key = f"{team.conference} {team.division}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(team.team_name)
    
    print("Current NHL Division Structure:")
    for div_name, teams in divisions.items():
        print(f"\n{div_name} ({len(teams)} teams):")
        for team in sorted(teams):
            print(f"  {team}")
    
    # Check Carolina Hurricanes specifically
    canes = next((t for t in nhl_teams if 'Carolina' in t.team_name), None)
    if canes:
        print(f"\n🎯 Carolina Hurricanes:")
        print(f"  Conference: {canes.conference}")
        print(f"  Division: {canes.division}")
        
        # Find its division rivals
        div_rivals = [t for t in nhl_teams 
                     if t.conference == canes.conference 
                     and t.division == canes.division 
                     and t != canes]
        
        print(f"  Division rivals ({len(div_rivals)}):")
        for rival in div_rivals:
            print(f"    {rival.team_name}")

if __name__ == "__main__":
    check_nhl_divisions()