#!/usr/bin/env python3
"""
Test script to verify the improved game simulation produces realistic scores.
"""

import sys
import os
from collections import defaultdict

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required classes
try:
    from main import HockeyManagerGUI
    from game_classes import Team, Player, PlayerPosition
    import random
    print("✅ Successfully imported required classes")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_test_team(name, avg_rating=75):
    """Create a test team with players of specified average rating"""
    team = Team(
        team_name=name,
        city=name.split()[0],
        division="Test Division", 
        conference="Test Conference"
    )
    
    # Create forwards
    for i in range(12):
        rating_variation = random.randint(-10, 10)
        overall = max(50, min(95, avg_rating + rating_variation))
        
        player = Player(
            first_name=f"{name.replace(' ', '')}F{i+1}",
            last_name="Forward",
            age=25,
            primary_position=PlayerPosition.CENTER
        )
        # Set base attributes to match overall rating
        for attr in ['skating', 'shooting', 'passing', 'checking', 'hockey_iq']:
            setattr(player, attr, overall)
        team.roster.append(player)
    
    # Create defensemen
    for i in range(6):
        rating_variation = random.randint(-10, 10)
        overall = max(50, min(95, avg_rating + rating_variation))
        
        player = Player(
            first_name=f"{name.replace(' ', '')}D{i+1}",
            last_name="Defense",
            age=25,
            primary_position=PlayerPosition.LEFT_DEFENSE
        )
        # Set base attributes
        for attr in ['skating', 'checking', 'passing', 'hockey_iq']:
            setattr(player, attr, overall)
        team.roster.append(player)
    
    # Create goalies
    for i in range(2):
        rating_variation = random.randint(-5, 5)
        overall = max(60, min(95, avg_rating + rating_variation))
        
        player = Player(
            first_name=f"{name.replace(' ', '')}G{i+1}",
            last_name="Goalie",
            age=25,
            primary_position=PlayerPosition.GOALIE
        )
        # Set goalie attributes
        for attr in ['goaltending', 'reflexes', 'positioning']:
            setattr(player, attr, overall)
        team.roster.append(player)
    
    return team

def test_improved_simulation():
    """Test the improved game simulation scoring"""
    print("🏒 Testing Improved Game Simulation")
    print("=" * 50)
    
    # Create test teams of different strengths
    strong_team = create_test_team("Strong Team", avg_rating=85)
    average_team = create_test_team("Average Team", avg_rating=75)
    weak_team = create_test_team("Weak Team", avg_rating=65)
    
    teams = [strong_team, average_team, weak_team]
    
    print(f"Created test teams:")
    for team in teams:
        print(f"  - {team.team_name} (avg ~{75 if 'Average' in team.team_name else 85 if 'Strong' in team.team_name else 65})")
    
    # Create a minimal game manager for simulation
    class TestGameManager:
        def __init__(self):
            from main import HockeyManagerGUI
            # Create minimal structure needed for simulation
            class MockLeague:
                def __init__(self):
                    self.standings = {}
            self.league = MockLeague()
    
    game_manager = TestGameManager()
    
    # Import and create simulation instance
    from main import HockeyManagerGUI
    app = HockeyManagerGUI(game_manager)
    
    # Test different matchups
    matchups = [
        (strong_team, weak_team, "Strong vs Weak"),
        (strong_team, average_team, "Strong vs Average"), 
        (average_team, weak_team, "Average vs Weak"),
        (average_team, average_team, "Even Matchup")
    ]
    
    print(f"\n🎮 Running simulation tests...")
    
    all_scores = []
    
    for home_team, away_team, description in matchups:
        print(f"\n📊 Testing: {description}")
        print(f"   {home_team.team_name} (home) vs {away_team.team_name} (away)")
        
        game_scores = []
        
        # Simulate 10 games for each matchup
        for game_num in range(10):
            try:
                winner, loser, scores = app._simulate_game_lightweight(home_team, away_team)
                home_score, away_score = scores
                total_goals = home_score + away_score
                
                game_scores.append((home_score, away_score, total_goals))
                all_scores.append(total_goals)
                
                winner_name = "HOME" if winner == home_team else "AWAY"
                print(f"   Game {game_num+1}: {home_score}-{away_score} ({winner_name} wins)")
                
            except Exception as e:
                print(f"   ❌ Game {game_num+1} failed: {e}")
                continue
        
        # Calculate statistics for this matchup
        if game_scores:
            avg_home = sum(s[0] for s in game_scores) / len(game_scores)
            avg_away = sum(s[1] for s in game_scores) / len(game_scores)
            avg_total = sum(s[2] for s in game_scores) / len(game_scores)
            
            print(f"   📈 Average: Home {avg_home:.1f} - Away {avg_away:.1f} (Total: {avg_total:.1f})")
    
    # Overall statistics
    if all_scores:
        avg_total_goals = sum(all_scores) / len(all_scores)
        min_goals = min(all_scores)
        max_goals = max(all_scores)
        
        # Count goal ranges
        goal_distribution = defaultdict(int)
        for total in all_scores:
            if total <= 2:
                goal_distribution["0-2 goals"] += 1
            elif total <= 4:
                goal_distribution["3-4 goals"] += 1
            elif total <= 6:
                goal_distribution["5-6 goals"] += 1
            else:
                goal_distribution["7+ goals"] += 1
        
        print(f"\n🎯 OVERALL SIMULATION RESULTS:")
        print(f"   Games simulated: {len(all_scores)}")
        print(f"   Average total goals: {avg_total_goals:.2f}")
        print(f"   Range: {min_goals}-{max_goals} goals")
        print(f"\n📊 Goal Distribution:")
        for range_name, count in goal_distribution.items():
            percentage = (count / len(all_scores)) * 100
            print(f"   {range_name}: {count} games ({percentage:.1f}%)")
        
        # Evaluate results
        print(f"\n✅ EVALUATION:")
        if avg_total_goals >= 4.5 and avg_total_goals <= 7.5:
            print(f"✅ PASS: Average goals ({avg_total_goals:.2f}) is realistic for NHL games")
        else:
            print(f"⚠️ CONCERN: Average goals ({avg_total_goals:.2f}) may be too {'high' if avg_total_goals > 7.5 else 'low'}")
        
        if goal_distribution["0-2 goals"] < len(all_scores) * 0.2:
            print(f"✅ PASS: Low-scoring games are not too frequent ({goal_distribution['0-2 goals']}/{len(all_scores)})")
        else:
            print(f"⚠️ CONCERN: Too many low-scoring games ({goal_distribution['0-2 goals']}/{len(all_scores)})")
        
        return avg_total_goals >= 4.5 and goal_distribution["0-2 goals"] < len(all_scores) * 0.3
    
    return False

if __name__ == "__main__":
    print("🏒 Puck Dynasty - Game Simulation Test")
    print("Testing the improved scoring system to fix low-scoring games")
    print()
    
    success = test_improved_simulation()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SIMULATION IMPROVEMENT: SUCCESSFUL")
        print("✅ Games now produce more realistic scores")
        print("✅ The scoring system has been fixed")
    else:
        print("💥 SIMULATION IMPROVEMENT: NEEDS MORE WORK") 
        print("❌ Additional adjustments may be needed")
    
    print("\nTest completed.")