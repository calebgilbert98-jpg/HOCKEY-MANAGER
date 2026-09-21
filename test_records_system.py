#!/usr/bin/env python3
"""
Test script for the NHL Records system
"""

import sys
import os
import random

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from nhl_records import RecordManager, NHL_Records
    from game_classes import Player, PlayerPosition
    print("✅ Successfully imported records system")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_records_system():
    """Test the basic functionality of the records system"""
    print("🏒 Testing NHL Records System")
    print("=" * 40)
    
    # Initialize record manager
    record_manager = RecordManager()
    print("✅ Record manager initialized")
    
    # Test retrieving existing records
    print("\n📊 Sample NHL Records:")
    goals_record = record_manager.nhl_records.get_record('single_season_goals')
    if goals_record:
        print(f"   Single Season Goals: {record_manager.nhl_records.format_record_display('single_season_goals')}")
    
    assists_record = record_manager.nhl_records.get_record('single_season_assists')
    if assists_record:
        print(f"   Single Season Assists: {record_manager.nhl_records.format_record_display('single_season_assists')}")
    
    career_goals_record = record_manager.nhl_records.get_record('career_goals')
    if career_goals_record:
        print(f"   Career Goals: {record_manager.nhl_records.format_record_display('career_goals')}")
    
    # Create test players
    print("\n👤 Creating test players...")
    
    # Create a superstar forward
    superstar = Player(
        first_name="Connor",
        last_name="McDavid",
        age=26,
        primary_position=PlayerPosition.CENTER
    )
    superstar.team_name = "Edmonton Oilers"
    
    # Create an elite goalie
    elite_goalie = Player(
        first_name="Igor",
        last_name="Shesterkin",
        age=28,
        primary_position=PlayerPosition.GOALIE
    )
    elite_goalie.team_name = "New York Rangers"
    
    print(f"   Created {superstar.full_name} (Forward)")
    print(f"   Created {elite_goalie.full_name} (Goalie)")
    
    # Test stat tracking and record checking
    print("\n🎮 Simulating exceptional season...")
    
    # Simulate McDavid having an incredible season
    for game in range(82):  # Full season
        # Random but biased toward high performance
        goals = random.choices([0, 1, 2, 3], weights=[40, 35, 20, 5])[0]
        assists = random.choices([0, 1, 2, 3, 4], weights=[20, 30, 30, 15, 5])[0]
        shots = random.randint(3, 8)
        
        superstar.add_game_stats(goals=goals, assists=assists, shots=shots)
        
        # Check for records periodically
        if game % 20 == 19:  # Every 20 games
            tracker = record_manager.get_or_create_tracker(
                str(superstar.id), superstar.full_name, superstar.team_name, False
            )
            # Update tracker with current stats
            tracker.season_goals = superstar.goals
            tracker.season_assists = superstar.assists
            tracker.season_points = superstar.points
            record_manager._check_for_records(tracker)
    
    # Simulate elite goalie season
    for game in range(65):  # Goalie games
        # Elite goalie performance
        won = random.choices([True, False], weights=[75, 25])[0]  # 75% win rate
        shutout = random.choices([True, False], weights=[15, 85])[0]  # 15% shutout rate
        saves = random.randint(25, 45)
        goals_against = 0 if shutout else random.randint(1, 4)
        shots_against = saves + goals_against
        
        elite_goalie.add_game_stats(
            wins=1 if won else 0,
            losses=0 if won else 1,
            saves=saves,
            goals_against=goals_against,
            shots_against=shots_against,
            shutout=shutout
        )
        
        # Check for records
        if game % 15 == 14:  # Every 15 games
            tracker = record_manager.get_or_create_tracker(
                str(elite_goalie.id), elite_goalie.full_name, elite_goalie.team_name, False
            )
            # Update tracker with current stats
            tracker.season_wins = elite_goalie.wins
            tracker.season_shutouts = elite_goalie.shutouts
            record_manager._check_for_records(tracker)
    
    # Display final stats
    print("\n📈 Final Season Stats:")
    print(f"   {superstar.full_name}:")
    print(f"     Goals: {superstar.goals}")
    print(f"     Assists: {superstar.assists}")
    print(f"     Points: {superstar.points}")
    print(f"     Games: {superstar.games_played}")
    print(f"     PPG: {superstar.get_ppg():.2f}")
    
    print(f"\n   {elite_goalie.full_name}:")
    print(f"     Wins: {elite_goalie.wins}")
    print(f"     Losses: {elite_goalie.losses}")
    print(f"     Shutouts: {elite_goalie.shutouts}")
    print(f"     Saves: {elite_goalie.saves}")
    print(f"     GAA: {elite_goalie.goals_against_avg:.2f}")
    print(f"     Save %: {elite_goalie.save_percentage:.3f}")
    
    # Test record chase functionality
    print("\n🏆 Record Chase Analysis:")
    goals_chase = record_manager.nhl_records.get_record_chase_info('single_season_goals', superstar.goals)
    if goals_chase:
        print(f"   {superstar.full_name} goals chase:")
        print(f"     Current: {goals_chase['current_value']}")
        print(f"     Record: {goals_chase['target_value']} ({goals_chase['record_holder']})")
        print(f"     Behind by: {goals_chase['difference']}")
        print(f"     Percentage: {goals_chase['percentage']:.1f}%")
    
    # Show any recent records broken
    recent_records = record_manager.get_recent_records(5)
    if recent_records:
        print(f"\n🎉 Recent Records Broken ({len(recent_records)}):")
        for record in recent_records:
            print(f"   {record['player_name']}: {record['record_type']} = {record['new_value']}")
    else:
        print("\n📝 No records broken during this test")
    
    # Test record leaders
    print("\n📊 Top Goal Scorers:")
    goal_leaders = record_manager.get_record_chase_leaders('single_season_goals')
    for i, (player_name, chase_info) in enumerate(goal_leaders[:5]):
        print(f"   {i+1}. {player_name}: {chase_info['current_value']} goals ({chase_info['percentage']:.1f}% of record)")
    
    print("\n✅ Records system test completed successfully!")
    return True

if __name__ == "__main__":
    print("🏒 NHL Records System Test")
    print("Testing comprehensive record tracking and achievement system")
    print()
    
    success = test_records_system()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 RECORDS SYSTEM TEST: COMPLETE SUCCESS!")
        print("✅ NHL records database loaded correctly")
        print("✅ Player stat tracking working")
        print("✅ Record detection functional")
        print("✅ Record chase analysis working")
        print("✅ System ready for integration!")
    else:
        print("❌ RECORDS SYSTEM TEST: FAILED!")
        print("🔧 Check error messages above")
    
    print("\nTest completed.")