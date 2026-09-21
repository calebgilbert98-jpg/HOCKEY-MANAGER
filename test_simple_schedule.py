#!/usr/bin/env python3

"""
Test script for the new simple NHL scheduling system.
"""

import sys
import os
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League, Team

def create_test_nhl_teams():
    """Create a simplified NHL with 32 teams for testing."""
    teams = []
    
    # Atlantic Division
    atlantic_teams = [
        "Boston Bruins", "Buffalo Sabres", "Detroit Red Wings", "Florida Panthers",
        "Montreal Canadiens", "Ottawa Senators", "Tampa Bay Lightning", "Toronto Maple Leafs"
    ]
    
    # Metropolitan Division  
    metro_teams = [
        "Carolina Hurricanes", "Columbus Blue Jackets", "New Jersey Devils", "New York Islanders",
        "New York Rangers", "Philadelphia Flyers", "Pittsburgh Penguins", "Washington Capitals"
    ]
    
    # Central Division
    central_teams = [
        "Arizona Coyotes", "Chicago Blackhawks", "Colorado Avalanche", "Dallas Stars",
        "Minnesota Wild", "Nashville Predators", "St. Louis Blues", "Winnipeg Jets"
    ]
    
    # Pacific Division
    pacific_teams = [
        "Anaheim Ducks", "Calgary Flames", "Edmonton Oilers", "Los Angeles Kings",
        "San Jose Sharks", "Seattle Kraken", "Vancouver Canucks", "Vegas Golden Knights"
    ]
    
    # Create team objects
    for team_name in atlantic_teams:
        team = Team(team_name, team_name.split()[-1], 'Atlantic', 'Eastern')
        teams.append(team)
    
    for team_name in metro_teams:
        team = Team(team_name, team_name.split()[-1], 'Metropolitan', 'Eastern')
        teams.append(team)
        
    for team_name in central_teams:
        team = Team(team_name, team_name.split()[-1], 'Central', 'Western')
        teams.append(team)
        
    for team_name in pacific_teams:
        team = Team(team_name, team_name.split()[-1], 'Pacific', 'Western')
        teams.append(team)
    
    return teams

def analyze_consecutive_games(games):
    """Analyze schedule for consecutive games issues."""
    print("\n" + "="*60)
    print("CONSECUTIVE GAMES ANALYSIS")
    print("="*60)
    
    # Group games by team and date
    team_games = defaultdict(list)
    
    for game_id, game_info in games.items():
        home_team = game_info['home_team']
        away_team = game_info['away_team']
        game_date = datetime.strptime(game_info['date'], '%Y-%m-%d')
        
        team_games[home_team].append(game_date)
        team_games[away_team].append(game_date)
    
    # Sort each team's games by date
    for team in team_games:
        team_games[team].sort()
    
    # Check for consecutive games
    teams_with_issues = 0
    total_consecutive_violations = 0
    
    for team_name, game_dates in team_games.items():
        consecutive_streaks = []
        current_streak = 1
        
        for i in range(1, len(game_dates)):
            days_diff = (game_dates[i] - game_dates[i-1]).days
            
            if days_diff == 1:  # Consecutive days
                current_streak += 1
            else:
                if current_streak >= 3:
                    consecutive_streaks.append(current_streak)
                current_streak = 1
        
        # Check final streak
        if current_streak >= 3:
            consecutive_streaks.append(current_streak)
        
        if consecutive_streaks:
            teams_with_issues += 1
            total_consecutive_violations += len(consecutive_streaks)
            print(f"❌ {team_name}: {len(consecutive_streaks)} violations - streaks of {consecutive_streaks}")
        else:
            print(f"✅ {team_name}: No 3+ consecutive games")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Teams with consecutive game violations: {teams_with_issues}/32")
    print(f"   Total violations: {total_consecutive_violations}")
    
    if teams_with_issues == 0:
        print("🎉 SUCCESS: No teams have 3+ consecutive games!")
    else:
        print(f"❌ FAILED: {teams_with_issues} teams still have consecutive game issues")
    
    return teams_with_issues == 0

def analyze_schedule_quality(games, teams):
    """Analyze overall schedule quality."""
    print("\n" + "="*60)
    print("SCHEDULE QUALITY ANALYSIS")
    print("="*60)
    
    # Count games per team
    team_game_counts = Counter()
    team_home_counts = Counter()
    team_away_counts = Counter()
    
    for game_info in games.values():
        home_team = game_info['home_team']
        away_team = game_info['away_team']
        
        team_game_counts[home_team] += 1
        team_game_counts[away_team] += 1
        team_home_counts[home_team] += 1
        team_away_counts[away_team] += 1
    
    print(f"📊 GAMES PER TEAM:")
    target_games = 82
    teams_at_target = 0
    
    for team in [t.team_name for t in teams]:
        games_scheduled = team_game_counts.get(team, 0)
        home_games = team_home_counts.get(team, 0)
        away_games = team_away_counts.get(team, 0)
        
        status = "✅" if games_scheduled == target_games else "❌"
        print(f"   {status} {team}: {games_scheduled} total ({home_games}H, {away_games}A)")
        
        if games_scheduled == target_games:
            teams_at_target += 1
    
    print(f"\n📈 SCHEDULE STATS:")
    print(f"   Total games scheduled: {len(games)}")
    print(f"   Teams at target (82 games): {teams_at_target}/32")
    print(f"   Expected total games: {32 * 82 // 2} = {32 * 82 // 2}")

def main():
    """Test the new simple scheduling system."""
    print("🏒 Testing Simple NHL Scheduling System")
    print("="*60)
    
    # Create test league
    league = League("Test NHL", "Hockey")
    teams = create_test_nhl_teams()
    
    for team in teams:
        league.add_team(team)
    
    print(f"Created league with {len(teams)} teams")
    print(f"Conferences: Eastern ({len([t for t in teams if t.conference == 'Eastern'])}), "
          f"Western ({len([t for t in teams if t.conference == 'Western'])})")
    
    # Test the new simple scheduling
    print("\n🔄 Running simple schedule generation...")
    success = league._simple_schedule_nhl_games()
    
    if not success:
        print("❌ Schedule generation failed!")
        return False
    
    print(f"\n✅ Schedule generation completed!")
    print(f"   Total games scheduled: {len(league.games)}")
    
    # Analyze the results
    analyze_schedule_quality(league.games, teams)
    consecutive_success = analyze_consecutive_games(league.games)
    
    # Overall result
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    
    if consecutive_success:
        print("🎉 SUCCESS: Simple scheduling system works!")
        print("   ✅ No teams have 3+ consecutive games")
        print("   ✅ Schedule generated successfully")
        return True
    else:
        print("❌ FAILED: Issues found in schedule")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)