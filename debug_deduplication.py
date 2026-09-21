#!/usr/bin/env python3
"""Debug the deduplication logic to see why we're only getting 496 instead of 1312 games."""

def debug_deduplication():
    """Debug the deduplication logic."""
    print("=" * 80)
    print("🔍 DEBUGGING DEDUPLICATION LOGIC")
    print("=" * 80)
    
    # Simulate the assignment structure
    # Each team has both HOME and AWAY assignments
    sample_assignments = {
        'Team A': [
            ('HOME', 'Team B'),  # Team A hosts Team B
            ('AWAY', 'Team C'),  # Team A visits Team C  
            ('HOME', 'Team D'),  # Team A hosts Team D
            ('AWAY', 'Team B'),  # Team A visits Team B (wait - this is weird!)
        ],
        'Team B': [
            ('AWAY', 'Team A'),  # Team B visits Team A
            ('HOME', 'Team C'),  # Team B hosts Team C
            ('AWAY', 'Team D'),  # Team B visits Team D
            ('HOME', 'Team A'),  # Team B hosts Team A (wait - this is also weird!)
        ]
    }
    
    print("📋 Sample assignments:")
    for team, assignments in sample_assignments.items():
        print(f"  {team}: {len(assignments)} games")
        for venue, opponent in assignments:
            print(f"    {venue} vs {opponent}")
    
    # Now apply the deduplication logic
    games_to_schedule = []
    processed_matchups = set()
    
    for team_name, assignments in sample_assignments.items():
        for venue, opponent in assignments:
            # The deduplication logic
            if venue == 'HOME':
                home_team_name = team_name
                away_team_name = opponent
            else:
                home_team_name = opponent
                away_team_name = team_name
            
            # Create matchup key
            matchup_key = tuple(sorted([home_team_name, away_team_name]))
            
            print(f"🔍 Processing: {team_name} {venue} vs {opponent}")
            print(f"   -> Home: {home_team_name}, Away: {away_team_name}")
            print(f"   -> Key: {matchup_key}")
            
            if matchup_key not in processed_matchups:
                games_to_schedule.append((home_team_name, away_team_name))
                processed_matchups.add(matchup_key)
                print(f"   -> ✅ Added game")
            else:
                print(f"   -> ❌ Duplicate, skipped")
            print()
    
    print(f"📊 Results:")
    print(f"   Total assignments processed: {sum(len(a) for a in sample_assignments.values())}")
    print(f"   Unique games scheduled: {len(games_to_schedule)}")
    print(f"   Games: {games_to_schedule}")

if __name__ == "__main__":
    debug_deduplication()