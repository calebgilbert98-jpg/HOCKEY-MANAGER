#!/usr/bin/env python3
"""Debug the divisional games assignment to see why teams get 31 instead of 26 games."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import random

def debug_divisional_games():
    """Debug the divisional game assignment calculation."""
    print("=" * 80)
    print("🔍 DEBUGGING DIVISIONAL GAMES ASSIGNMENT")
    print("=" * 80)
    
    # Simulate the divisional games assignment logic
    div_teams = ["Team A", "Team B", "Team C", "Team D", "Team E", "Team F", "Team G", "Team H"]
    team = "Team A"
    rotation_seed = 2024
    
    print(f"🏒 Division teams: {div_teams}")
    print(f"🎯 Focus team: {team}")
    
    # Get division rivals (the other 7 teams)
    division_rivals = [t for t in div_teams if t != team]
    print(f"🎯 Division rivals: {division_rivals} ({len(division_rivals)} teams)")
    
    # Use rotation seed to determine which teams get 4 games vs 3 games
    random.seed(rotation_seed + hash(team) % 1000)
    original_rivals = division_rivals.copy()
    random.shuffle(division_rivals)
    
    print(f"🔀 Shuffled rivals: {division_rivals}")
    
    matchup_assignments = []
    
    # Give everyone base 2 games first (1H, 1A)  
    print(f"\n📋 Base assignment (2 games each):")
    for rival in division_rivals:
        matchup_assignments.append(('HOME', rival))
        matchup_assignments.append(('AWAY', rival))
        print(f"   vs {rival}: HOME + AWAY = 2 games")
    
    print(f"\n📊 After base assignment: {len(matchup_assignments)} games")
    
    # Now add extra games to reach 26
    # We need 26 - 14 = 12 more games  
    # But wait, 7 rivals × 2 = 14 games, need 26 total, so 12 more games
    extra_games_needed = 26 - (7 * 2)  # 26 - 14 = 12 extra games
    print(f"\n🎯 Extra games needed: {extra_games_needed}")
    
    # Distribute extra games
    print(f"\n📋 Extra game distribution:")
    for j in range(extra_games_needed):
        rival = division_rivals[j % len(division_rivals)]
        venue = 'HOME' if j % 2 == 0 else 'AWAY'
        matchup_assignments.append((venue, rival))
        print(f"   Extra game {j+1}: {venue} vs {rival}")
    
    print(f"\n📊 Final assignment: {len(matchup_assignments)} games")
    
    # Count games per opponent
    games_per_opponent = {}
    for venue, opponent in matchup_assignments:
        games_per_opponent[opponent] = games_per_opponent.get(opponent, 0) + 1
    
    print(f"\n🎯 Games per opponent:")
    for opponent, count in games_per_opponent.items():
        print(f"   vs {opponent}: {count} games")
    
    total_games = sum(games_per_opponent.values())
    print(f"\n✅ Total divisional games: {total_games} (target: 26)")
    return total_games

if __name__ == "__main__":
    debug_divisional_games()