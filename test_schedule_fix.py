#!/usr/bin/env python3
"""
Focused test script to verify the schedule generation fix prevents same-day conflicts.
Tests only the specific schedule generation method without launching the full game.
"""

import sys
import os
from datetime import date
from collections import defaultdict

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required classes - minimal imports to avoid full game startup
try:
    from game_classes import League, Team
    print("✅ Successfully imported League and Team classes")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_other_league_schedule_generation():
    """Test that the fixed _generate_other_league_schedule prevents same-day conflicts."""
    print("🧪 Testing Other League Schedule Generation Fix")
    print("=" * 60)
    
    # Create a test league with several teams
    test_league = League("Test League", 2024)
    
    # Create test teams
    teams = []
    for i in range(8):  # 8 teams for a robust test
        team_name = f"Team {chr(65+i)}"  # Team A, Team B, etc.
        team = Team(
            team_name=team_name,
            city=f"City {chr(65+i)}",
            division="Test Division",
            conference="Test Conference"
        )
        teams.append(team)
        test_league.teams.append(team)
    
    print(f"Created test league with {len(teams)} teams:")
    for team in teams:
        print(f"  - {team.team_name}")
    
    print(f"\n🏗️ Generating schedule using NEW conflict-prevention method...")
    
    # Test the specific method that was causing issues
    try:
        test_league._generate_other_league_schedule(teams, "Test League")
        print(f"✅ Schedule generation completed successfully")
    except Exception as e:
        print(f"❌ Schedule generation failed: {e}")
        return False
    
    print(f"\n📊 Generated {len(test_league.schedule)} total games")
    
    # Analyze the schedule for same-day conflicts
    team_games_by_date = defaultdict(lambda: defaultdict(int))
    
    for game_date, home_team, away_team in test_league.schedule:
        team_games_by_date[game_date][home_team.team_name] += 1
        team_games_by_date[game_date][away_team.team_name] += 1
    
    # Check for conflicts
    conflicts_found = 0
    total_dates = len(team_games_by_date)
    
    print(f"\n� Analyzing schedule across {total_dates} game dates...")
    
    sample_dates_shown = 0
    for game_date, team_counts in sorted(team_games_by_date.items()):
        date_conflicts = 0
        teams_with_multiple_games = []
        
        for team_name, game_count in team_counts.items():
            if game_count > 1:
                conflicts_found += 1
                date_conflicts += 1
                teams_with_multiple_games.append(f"{team_name} ({game_count} games)")
        
        # Show sample of dates (first few and any with conflicts)
        if date_conflicts > 0:
            print(f"⚠️ CONFLICT on {game_date}: {', '.join(teams_with_multiple_games)}")
        elif sample_dates_shown < 3:  # Show first 3 good dates as examples
            teams_playing = list(team_counts.keys())
            print(f"✅ {game_date}: {len(teams_playing)} teams playing (no conflicts)")
            sample_dates_shown += 1
    
    # Show team-by-team game count summary
    team_game_counts = defaultdict(int)
    for game_date, home_team, away_team in test_league.schedule:
        team_game_counts[home_team.team_name] += 1
        team_game_counts[away_team.team_name] += 1
    
    print(f"\n📈 Games scheduled per team:")
    for team_name in sorted(team_game_counts.keys()):
        game_count = team_game_counts[team_name]
        print(f"  {team_name}: {game_count} games")
    
    # Final results
    print(f"\n🎯 TEST RESULTS:")
    if conflicts_found == 0:
        print(f"✅ SUCCESS: No same-day conflicts found!")
        print(f"✅ All {len(teams)} teams can play without scheduling conflicts")
        print(f"✅ Schedule generation fix is working correctly")
        return True
    else:
        print(f"❌ FAILURE: Found {conflicts_found} same-day conflicts")
        print(f"❌ The fix needs additional work")
        return False

if __name__ == "__main__":
    print("� Puck Dynasty - Schedule Generation Test")
    print("Testing the fix for teams playing multiple games on the same day")
    print()
    
    success = test_other_league_schedule_generation()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SCHEDULE FIX VERIFICATION: PASSED")
        print("✅ Teams will no longer play multiple games on the same day")
        print("✅ The conflict prevention system is working properly")
    else:
        print("💥 SCHEDULE FIX VERIFICATION: FAILED")
        print("❌ Additional fixes are needed for schedule generation")
    
    print("\nTest completed.")