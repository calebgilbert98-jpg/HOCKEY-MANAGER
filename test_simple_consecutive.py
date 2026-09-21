#!/usr/bin/env python3

"""
Simple test to verify consecutive games prevention in the new simple scheduling system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from game_classes import League

def test_consecutive_games_simple():
    """Test that no team has 3+ consecutive games."""
    print("🧪 TESTING: Simple Consecutive Games Prevention")
    print("=" * 60)
    
    # Create league
    print("📋 Creating league...")
    league = League("National Hockey League")
    
    # Generate schedule
    print("🏒 Generating NHL schedule...")
    league.generate_schedule()
    
    print(f"✅ Schedule generated: {len(league.schedule)} total games")
    
    # Group games by team
    team_schedules = {}
    for game in league.schedule:
        if isinstance(game, dict) and 'home_team' in game and 'away_team' in game:
            home_team = game['home_team']
            away_team = game['away_team']
            game_date = game['date']
            
            # Track home team
            if home_team.team_name not in team_schedules:
                team_schedules[home_team.team_name] = []
            team_schedules[home_team.team_name].append(game_date)
            
            # Track away team  
            if away_team.team_name not in team_schedules:
                team_schedules[away_team.team_name] = []
            team_schedules[away_team.team_name].append(game_date)
    
    # Check for consecutive games violations
    print("\n🔍 Checking for consecutive games violations...")
    violations = []
    
    for team_name, dates in team_schedules.items():
        dates.sort()
        print(f"Checking {team_name}: {len(dates)} games")
        
        # Look for 3+ consecutive games
        consecutive_count = 1
        for i in range(1, len(dates)):
            days_diff = (dates[i] - dates[i-1]).days
            
            if days_diff == 1:  # Back-to-back games
                consecutive_count += 1
                if consecutive_count >= 3:
                    violation = f"{team_name}: {consecutive_count} consecutive games ending on {dates[i]}"
                    violations.append(violation)
                    print(f"❌ VIOLATION: {violation}")
            else:
                consecutive_count = 1
    
    # Report results
    print(f"\n📊 RESULTS:")
    print(f"   Teams analyzed: {len(team_schedules)}")
    print(f"   Games per team: {[len(dates) for dates in team_schedules.values()]}")
    print(f"   Consecutive violations: {len(violations)}")
    
    if violations:
        print("❌ TEST FAILED: Consecutive games violations found:")
        for violation in violations:
            print(f"   - {violation}")
        return False
    else:
        print("✅ TEST PASSED: No consecutive games violations!")
        return True

if __name__ == "__main__":
    success = test_consecutive_games_simple()
    sys.exit(0 if success else 1)