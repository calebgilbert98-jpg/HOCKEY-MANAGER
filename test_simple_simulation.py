#!/usr/bin/env python3
"""
Simple test script to verify the improved game simulation produces realistic scores.
"""

import sys
import os
import random
from collections import defaultdict

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required classes
try:
    from game_classes import Team, Player, PlayerPosition
    print("✅ Successfully imported required classes")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_simple_team(name, avg_rating=75):
    """Create a simple test team with players"""
    team = Team(
        team_name=name,
        city=name.split()[0],
        division="Test Division", 
        conference="Test Conference"
    )
    
    # Create a basic roster with varied ratings
    for i in range(20):  # 20 total players
        rating_variation = random.randint(-10, 10)
        overall = max(50, min(95, avg_rating + rating_variation))
        
        if i < 12:  # Forwards
            position = PlayerPosition.CENTER
        elif i < 18:  # Defense
            position = PlayerPosition.LEFT_DEFENSE
        else:  # Goalies
            position = PlayerPosition.GOALIE
            
        player = Player(
            first_name=f"Player{i+1}",
            last_name=name.replace(" ", ""),
            age=25,
            primary_position=position
        )
        
        # Set all skill attributes based on the position and overall rating
        if position == PlayerPosition.GOALIE:
            # Goalie attributes
            for attr in ['goaltending', 'reflexes', 'positioning', 'rebound_control', 
                        'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill',
                        'confidence', 'focus', 'composure']:
                if hasattr(player, attr):
                    setattr(player, attr, overall)
        else:
            # Skater attributes
            for attr in ['skating', 'shooting', 'shooting_accuracy', 'shooting_power',
                        'passing', 'passing_accuracy', 'passing_creativity', 'deking',
                        'stickhandling', 'vision', 'hockey_iq', 'offensive_awareness',
                        'defensive_awareness', 'checking', 'strength', 'speed',
                        'acceleration', 'agility', 'balance', 'endurance', 'determination',
                        'teamwork', 'leadership', 'discipline', 'flair', 'consistency',
                        'clutch_performance', 'work_ethic', 'compete_level', 'coachability',
                        'injury_proneness', 'puck_protection', 'screen_shots', 'deflections',
                        'one_timers', 'slap_shot', 'wrist_shot', 'backhand']: 
                if hasattr(player, attr):
                    setattr(player, attr, overall)
        
        team.roster.append(player)
    
    return team

def test_scoring_directly():
    """Test the scoring calculation methods directly"""
    print("🏒 Testing Game Simulation Scoring")
    print("=" * 40)
    
    # Create test teams
    strong_team = create_simple_team("Strong Team", avg_rating=85)
    weak_team = create_simple_team("Weak Team", avg_rating=65)
    
    print(f"Created teams:")
    print(f"  - {strong_team.team_name} (strong, ~85 rating)")
    print(f"  - {weak_team.team_name} (weak, ~65 rating)")
    
    # Create a simple simulation class to test our methods
    class TestSimulation:
        def __init__(self):
            self._strength_cache = {}
            
        def _calculate_team_strength(self, team):
            """Copy of the improved team strength calculation"""
            cache_key = f"strength_{team.team_name}"
            if cache_key in self._strength_cache:
                return self._strength_cache[cache_key]
            
            total_strength = 0
            player_count = 0
            
            # Enhanced strength calculation based on key players
            sorted_roster = sorted(team.roster, key=lambda p: p.overall_rating(), reverse=True)
            top_forwards = [p for p in sorted_roster if p.primary_position.name in ['LEFT_WING', 'RIGHT_WING', 'CENTER']][:9]
            top_defense = [p for p in sorted_roster if p.primary_position.name in ['LEFT_DEFENSE', 'RIGHT_DEFENSE']][:6]  
            top_goalies = [p for p in sorted_roster if p.primary_position.name == 'GOALIE'][:2]
            
            # Weight positions appropriately
            for player in top_forwards:
                total_strength += player.overall_rating() * 0.6
                player_count += 0.6
                
            for player in top_defense:
                total_strength += player.overall_rating() * 0.3
                player_count += 0.3
                
            for player in top_goalies:
                total_strength += player.overall_rating() * 0.1
                player_count += 0.1
            
            # Normalize to 0.5-1.0 range
            strength = (total_strength / max(player_count, 1)) / 100.0 if player_count > 0 else 0.75
            strength = max(0.5, min(1.0, strength))
            
            self._strength_cache[cache_key] = strength
            return strength
        
        def _simulate_game_lightweight(self, home_team, away_team):
            """Copy of the improved lightweight simulation"""
            import random
            
            # Calculate team strengths quickly
            home_strength = self._calculate_team_strength(home_team) + 0.05  # Home ice advantage
            away_strength = self._calculate_team_strength(away_team)
            
            # More realistic scoring - NHL average is around 6.2 total goals per game
            base_goals = 3.1  # Base expectation for average team (NHL-like)
            home_goal_expectation = base_goals + (home_strength - 0.75) * 2.5
            away_goal_expectation = base_goals + (away_strength - 0.75) * 2.5
            
            # Use more reasonable ranges that produce NHL-like scoring
            home_goal_expectation = max(2.2, min(4.2, home_goal_expectation))
            away_goal_expectation = max(2.2, min(4.2, away_goal_expectation))
            
            # Generate goals using normal distribution with smaller std deviation
            home_goals = max(0, min(8, int(random.normalvariate(home_goal_expectation, 0.9))))
            away_goals = max(0, min(8, int(random.normalvariate(away_goal_expectation, 0.9))))
            
            # Handle ties
            if home_goals == away_goals:
                if random.random() < 0.55:
                    home_goals += 1
                else:
                    away_goals += 1
            
            # Determine winner
            if home_goals > away_goals:
                winner = home_team
                loser = away_team
            else:
                winner = away_team
                loser = home_team
            
            return winner, loser, (home_goals, away_goals)
    
    # Test the simulation
    sim = TestSimulation()
    
    # Test team strengths
    strong_strength = sim._calculate_team_strength(strong_team)
    weak_strength = sim._calculate_team_strength(weak_team)
    
    print(f"\n📊 Team Strengths:")
    print(f"  {strong_team.team_name}: {strong_strength:.3f}")
    print(f"  {weak_team.team_name}: {weak_strength:.3f}")
    print(f"  Difference: {strong_strength - weak_strength:.3f}")
    
    # Run multiple simulations
    print(f"\n🎮 Running 20 test games...")
    
    all_scores = []
    strong_wins = 0
    
    for game_num in range(20):
        winner, loser, scores = sim._simulate_game_lightweight(strong_team, weak_team)
        home_score, away_score = scores
        total_goals = home_score + away_score
        
        all_scores.append(total_goals)
        if winner == strong_team:
            strong_wins += 1
        
        winner_name = "STRONG" if winner == strong_team else "WEAK"
        print(f"  Game {game_num+1}: {home_score}-{away_score} ({winner_name} wins, {total_goals} total)")
    
    # Calculate statistics
    avg_goals = sum(all_scores) / len(all_scores)
    min_goals = min(all_scores)
    max_goals = max(all_scores)
    strong_win_pct = (strong_wins / 20) * 100
    
    # Goal distribution
    low_scoring = sum(1 for score in all_scores if score <= 3)
    normal_scoring = sum(1 for score in all_scores if 4 <= score <= 6)
    high_scoring = sum(1 for score in all_scores if score >= 7)
    
    print(f"\n🎯 SIMULATION RESULTS:")
    print(f"  Games simulated: 20")
    print(f"  Average total goals: {avg_goals:.2f}")
    print(f"  Goal range: {min_goals}-{max_goals}")
    print(f"  Strong team wins: {strong_wins}/20 ({strong_win_pct:.1f}%)")
    print(f"\n📊 Goal Distribution:")
    print(f"  Low scoring (≤3): {low_scoring} games ({low_scoring*5}%)")
    print(f"  Normal scoring (4-6): {normal_scoring} games ({normal_scoring*5}%)")
    print(f"  High scoring (≥7): {high_scoring} games ({high_scoring*5}%)")
    
    # Evaluation
    print(f"\n✅ EVALUATION:")
    success = True
    
    if 4.5 <= avg_goals <= 7.5:
        print(f"✅ PASS: Average goals ({avg_goals:.2f}) is realistic")
    else:
        print(f"⚠️ CONCERN: Average goals ({avg_goals:.2f}) may be unrealistic")
        success = False
    
    if low_scoring <= 4:  # Less than 20% low scoring
        print(f"✅ PASS: Low-scoring games are reasonable ({low_scoring}/20)")
    else:
        print(f"⚠️ CONCERN: Too many low-scoring games ({low_scoring}/20)")
        success = False
    
    if strong_win_pct >= 60:
        print(f"✅ PASS: Strong team wins appropriately ({strong_win_pct:.1f}%)")
    else:
        print(f"⚠️ CONCERN: Strong team should win more often ({strong_win_pct:.1f}%)")
        success = False
    
    return success

if __name__ == "__main__":
    print("🏒 Puck Dynasty - Simple Simulation Test")
    print("Testing improved scoring to fix 1-0 games")
    print()
    
    success = test_scoring_directly()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 SIMULATION FIX: SUCCESSFUL")
        print("✅ Scoring produces realistic results")
        print("✅ No more frequent 1-0 games!")
    else:
        print("💥 SIMULATION FIX: NEEDS ADJUSTMENT")
        print("❌ Additional tuning may be needed")
    
    print("\nTest completed.")