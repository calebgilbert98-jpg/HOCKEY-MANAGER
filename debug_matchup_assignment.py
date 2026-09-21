#!/usr/bin/env python3
"""Debug the NHL matchup assignment to see why teams only get 60 games instead of 82."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League, Team, Division, PlayerPosition, Conference, TeamType
import random

def create_test_league():
    """Create a realistic NHL league with proper division structure."""
    print("🏒 Creating NHL test league...")
    league = League("National Hockey League")
    
    # NHL Division structure
    nhl_divisions = [
        ("Eastern_Metropolitan", [
            "Carolina Hurricanes", "Columbus Blue Jackets", "New Jersey Devils",
            "New York Islanders", "New York Rangers", "Philadelphia Flyers",
            "Pittsburgh Penguins", "Washington Capitals"
        ]),
        ("Eastern_Atlantic", [
            "Boston Bruins", "Buffalo Sabres", "Detroit Red Wings",
            "Florida Panthers", "Montréal Canadiens", "Ottawa Senators",
            "Tampa Bay Lightning", "Toronto Maple Leafs"
        ]),
        ("Western_Central", [
            "Chicago Blackhawks", "Colorado Avalanche", "Dallas Stars",
            "Minnesota Wild", "Nashville Predators", "St. Louis Blues",
            "Utah Hockey Club", "Winnipeg Jets"
        ]),
        ("Western_Pacific", [
            "Anaheim Ducks", "Calgary Flames", "Edmonton Oilers",
            "Los Angeles Kings", "San Jose Sharks", "Seattle Kraken",
            "Vancouver Canucks", "Vegas Golden Knights"
        ])
    ]
    
    for div_name, team_names in nhl_divisions:
        # Determine conference
        conference = Conference.EASTERN if div_name.startswith("Eastern") else Conference.WESTERN
        
        # Create division
        division = Division(div_name, conference)
        league.add_division(division)
        
        # Create teams
        for team_name in team_names:
            team = Team(team_name, team_name.split()[-1], division, TeamType.NHL)
            team.generate_random_players()
            league.add_team(team)
    
    print(f"📋 Created league with {len(league.teams)} teams in {len(league.divisions)} divisions")
    return league

def debug_matchup_assignments():
    """Debug the NHL matchup assignment process."""
    print("=" * 80)
    print("🔍 DEBUGGING NHL MATCHUP ASSIGNMENT")
    print("=" * 80)
    
    league = create_test_league()
    
    # Test the matchup assignment process
    print("\n🧪 Testing _create_authentic_nhl_matchup_pattern()...")
    
    # Create a season year and rotation seed
    season_year = 2024
    rotation_seed = season_year
    
    print(f"🔄 Season: {season_year}, Rotation seed: {rotation_seed}")
    
    # Call the method directly
    matchup_pattern = league._create_authentic_nhl_matchup_pattern(season_year, rotation_seed)
    
    print(f"\n📊 Matchup Pattern Results:")
    print(f"   Total matchups created: {len(matchup_pattern)}")
    
    # Analyze matchups by team
    team_matchup_counts = {}
    for matchup in matchup_pattern:
        home_team, away_team = matchup
        team_matchup_counts[home_team] = team_matchup_counts.get(home_team, 0) + 1
        team_matchup_counts[away_team] = team_matchup_counts.get(away_team, 0) + 1
    
    print(f"\n📋 Games per team from matchup pattern:")
    for team_name in sorted(team_matchup_counts.keys()):
        count = team_matchup_counts[team_name]
        status = "✅" if count == 82 else f"⚠️ ({count})"
        print(f"   {team_name}: {count} {status}")
    
    # Check if we have the right total
    total_matchups = len(matchup_pattern)
    expected_matchups = 32 * 82 // 2  # 1,312 total games
    print(f"\n🔢 Total Analysis:")
    print(f"   Matchups created: {total_matchups}")
    print(f"   Expected matchups: {expected_matchups}")
    print(f"   Status: {'✅' if total_matchups == expected_matchups else '❌'}")
    
    # Let's also check the division structure used
    print(f"\n🏒 League Structure Used:")
    for division in league.divisions:
        teams_in_div = [team.name for team in league.teams if team.division == division]
        print(f"   {division.name}: {len(teams_in_div)} teams")
        for team_name in teams_in_div:
            print(f"     - {team_name}")
    
    return matchup_pattern, team_matchup_counts

if __name__ == "__main__":
    debug_matchup_assignments()