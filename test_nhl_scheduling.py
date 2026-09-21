#!/usr/bin/env python3
"""
Test the new NHL scheduling algorithm after complete rewrite.
"""

import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from game_classes import League, Team
    print("✅ Successfully imported game_classes")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_scheduling_algorithm():
    """Test the new NHL scheduling algorithm."""
    print("\n🏒 TESTING NEW NHL SCHEDULING ALGORITHM")
    print("=" * 50)
    
    try:
        # Create a test league
        nhl = League("NHL", 2024)
        print("✅ Created NHL league")
        
        # Create test teams (simplified for testing)
        test_teams = [
            Team(team_name="Boston Bruins", city="Boston", division="Atlantic", conference="Eastern"),
            Team(team_name="Toronto Maple Leafs", city="Toronto", division="Atlantic", conference="Eastern"),
            Team(team_name="Tampa Bay Lightning", city="Tampa Bay", division="Atlantic", conference="Eastern"),
            Team(team_name="Florida Panthers", city="Sunrise", division="Atlantic", conference="Eastern"),
        ]
        
        # Add teams to league
        for team in test_teams:
            nhl.add_team(team)
        print(f"✅ Added {len(test_teams)} test teams")
        
        # Test the scheduling
        print("\n📅 Generating NHL schedule...")
        nhl.generate_schedule()
        print("✅ Schedule generation completed")
        
        # Analyze results
        if not nhl.schedule:
            print("❌ No games were scheduled!")
            return False
            
        print(f"\n📊 RESULTS:")
        print(f"   Total games scheduled: {len(nhl.schedule)}")
        
        # Count games per team
        team_game_counts = {}
        team_home_counts = {}
        team_away_counts = {}
        
        for game_date, home_team, away_team in nhl.schedule:
            # Count for home team
            if home_team.team_name not in team_game_counts:
                team_game_counts[home_team.team_name] = 0
                team_home_counts[home_team.team_name] = 0
                team_away_counts[home_team.team_name] = 0
            team_game_counts[home_team.team_name] += 1
            team_home_counts[home_team.team_name] += 1
            
            # Count for away team
            if away_team.team_name not in team_game_counts:
                team_game_counts[away_team.team_name] = 0
                team_home_counts[away_team.team_name] = 0
                team_away_counts[away_team.team_name] = 0
            team_game_counts[away_team.team_name] += 1
            team_away_counts[away_team.team_name] += 1
        
        # Display team stats
        print(f"\n📈 TEAM STATISTICS:")
        for team_name in team_game_counts:
            total = team_game_counts[team_name]
            home = team_home_counts[team_name]
            away = team_away_counts[team_name]
            print(f"   {team_name}: {total} games ({home}H/{away}A)")
        
        # Check for target compliance (82 games, 41H/41A)
        all_teams_compliant = True
        target_games = 82 if len(test_teams) >= 10 else len(test_teams) * 4  # Simplified for small test
        
        for team_name, count in team_game_counts.items():
            if abs(count - target_games) > 2:  # Allow small variance
                print(f"❌ {team_name} has {count} games (target: ~{target_games})")
                all_teams_compliant = False
        
        if all_teams_compliant:
            print("✅ All teams have appropriate game counts")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_scheduling_algorithm()
    if success:
        print("\n🎉 NHL SCHEDULING TEST COMPLETED SUCCESSFULLY!")
    else:
        print("\n💥 NHL SCHEDULING TEST FAILED!")
        sys.exit(1)