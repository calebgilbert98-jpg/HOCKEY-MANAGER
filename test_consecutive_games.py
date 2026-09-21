#!/usr/bin/env python3

"""
Test the fixed NHL schedule generation to ensure no 3+ consecutive games.
"""

import sys
from game_classes import League

def test_consecutive_games():
    """Test schedule generation and check for consecutive games violations."""
    print("🧪 TESTING: NHL Schedule Generation with Consecutive Games Prevention")
    print("=" * 70)
    
    try:
        # Create a league
        print("📋 Creating league...")
        league = League("NHL")
        
        # Generate NHL schedule
        print("🏒 Generating NHL schedule (this may take a moment)...")
        league.generate_schedule()
        
        print(f"✅ Generated {len(league.schedule)} total games")
        
        # Analyze the schedule for consecutive games violations
        print("\n🔍 Analyzing schedule for consecutive games violations...")
        
        # Group games by team
        team_schedules = {}
        for game_date, home_team, away_team in league.schedule:
            # Skip special events
            if home_team == 'NHL_EVENT':
                continue
            
            # Track home team
            home_name = home_team.team_name
            if home_name not in team_schedules:
                team_schedules[home_name] = []
            team_schedules[home_name].append(game_date)
            
            # Track away team
            away_name = away_team.team_name
            if away_name not in team_schedules:
                team_schedules[away_name] = []
            team_schedules[away_name].append(game_date)
        
        # Check for consecutive games violations
        violations = []
        team_stats = {}
        
        for team_name, dates in team_schedules.items():
            dates.sort()
            
            # Count consecutive games
            max_consecutive = 0
            current_consecutive = 1
            consecutive_sequences = []
            
            for i in range(1, len(dates)):
                days_diff = (dates[i] - dates[i-1]).days
                
                if days_diff == 1:  # Back-to-back
                    current_consecutive += 1
                else:
                    if current_consecutive >= 3:
                        consecutive_sequences.append(current_consecutive)
                    max_consecutive = max(max_consecutive, current_consecutive)
                    current_consecutive = 1
            
            # Check final sequence
            if current_consecutive >= 3:
                consecutive_sequences.append(current_consecutive)
            max_consecutive = max(max_consecutive, current_consecutive)
            
            team_stats[team_name] = {
                'total_games': len(dates),
                'max_consecutive': max_consecutive,
                'consecutive_sequences': consecutive_sequences
            }
            
            # Record violations
            if max_consecutive >= 3:
                violations.append({
                    'team': team_name,
                    'max_consecutive': max_consecutive,
                    'sequences': consecutive_sequences
                })
        
        # Report results
        print(f"\n📊 ANALYSIS RESULTS:")
        print(f"   Teams analyzed: {len(team_stats)}")
        
        # Games per team statistics
        game_counts = [stats['total_games'] for stats in team_stats.values()]
        min_games = min(game_counts) if game_counts else 0
        max_games = max(game_counts) if game_counts else 0
        avg_games = sum(game_counts) / len(game_counts) if game_counts else 0
        
        print(f"   Games per team: {min_games}-{max_games} (avg: {avg_games:.1f})")
        print(f"   Target games per team: 82")
        
        # Consecutive games analysis
        if violations:
            print(f"\n❌ CONSECUTIVE GAMES VIOLATIONS FOUND: {len(violations)}")
            print(f"   Teams with 3+ consecutive games:")
            for violation in violations[:10]:  # Show first 10
                team = violation['team']
                max_cons = violation['max_consecutive']
                sequences = violation['sequences']
                print(f"   • {team}: Max {max_cons} consecutive games")
                if sequences:
                    sequence_str = ", ".join(f"{seq} consecutive" for seq in sequences)
                    print(f"     Sequences: {sequence_str}")
            
            if len(violations) > 10:
                print(f"     ... and {len(violations) - 10} more teams")
            
            print(f"\n❌ TEST FAILED: Found consecutive games violations!")
            return False
        else:
            print(f"\n✅ NO CONSECUTIVE GAMES VIOLATIONS FOUND!")
            print(f"   All teams have maximum 2 consecutive games")
            
            # Show some examples of good scheduling
            print(f"\n📋 Sample team schedules (first 5 teams):")
            sample_teams = list(team_stats.keys())[:5]
            for team in sample_teams:
                stats = team_stats[team]
                print(f"   • {team}: {stats['total_games']} games, max {stats['max_consecutive']} consecutive")
            
            print(f"\n✅ TEST PASSED: No 3+ consecutive games found!")
            return True
    
    except Exception as e:
        print(f"\n❌ TEST FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_consecutive_games()
    sys.exit(0 if success else 1)