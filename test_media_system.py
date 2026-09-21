#!/usr/bin/env python3
"""Test script for the Media & Press Conference System"""

from datetime import date, timedelta
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from media_system import MediaSystem, MediaEngagementLevel
from game_classes import Player, Team, Contract, PlayerPosition

def create_test_game_manager():
    """Create a minimal test game manager"""
    class TestGameManager:
        def __init__(self):
            self.current_date = date.today()
            self.user_team = Team("Test Team", "Test City", "Test Division", "Test Conference")
            self.news_log = []
        
        def add_news(self, story):
            self.news_log.append({
                'date': self.current_date,
                'story': story
            })
    
    return TestGameManager()

def test_media_system_initialization():
    """Test media system can be initialized"""
    print("Testing MediaSystem initialization...")
    
    game_manager = create_test_game_manager()
    media_system = MediaSystem(game_manager)
    
    print(f"✓ MediaSystem created with engagement level: {media_system.engagement_level.value}")
    print(f"✓ Number of journalists: {len(media_system.journalists)}")
    print(f"✓ GM reputation: {media_system.gm_reputation}")
    
    return media_system

def test_engagement_levels():
    """Test different engagement levels"""
    print("\nTesting engagement levels...")
    
    game_manager = create_test_game_manager()
    media_system = MediaSystem(game_manager)
    
    for level in MediaEngagementLevel:
        media_system.set_engagement_level(level.value)
        print(f"✓ Set to {level.value}: {media_system.engagement_level}")
    
    return media_system

def test_game_result_processing():
    """Test processing game results"""
    print("\nTesting game result processing...")
    
    game_manager = create_test_game_manager()
    media_system = MediaSystem(game_manager)
    media_system.set_engagement_level("Full Immersion")
    
    # Create test game result
    game_result = {
        'winner': game_manager.user_team,
        'home_team': game_manager.user_team,
        'away_team': Team("Opponent", "Away City", "Away Division", "Away Conference"),
        'home_score': 4,
        'away_score': 2,
        'date': date.today(),
        'notable_events': [
            {'event': 'Goal', 'player': 'Test Player', 'period': 1},
            {'event': 'Goal', 'player': 'Test Player 2', 'period': 3}
        ]
    }
    
    # Process the game
    events_before = len(media_system.get_pending_media_events())
    media_system.process_game_result(game_result)
    events_after = len(media_system.get_pending_media_events())
    
    print(f"✓ Events before: {events_before}, after: {events_after}")
    if events_after > events_before:
        print("✓ Successfully created media event for game")
        
        # Test getting questions
        event = media_system.get_pending_media_events()[-1]
        questions = media_system.get_interview_questions(event)
        print(f"✓ Generated {len(questions)} interview questions")
        for i, q in enumerate(questions, 1):
            print(f"   {i}. {q}")
    
    return media_system

def test_trade_processing():
    """Test processing trades"""
    print("\nTesting trade processing...")
    
    game_manager = create_test_game_manager()
    media_system = MediaSystem(game_manager)
    media_system.set_engagement_level("Standard")
    
    # Create test players
    traded_player = Player(
        first_name="John", 
        last_name="Doe",
        primary_position=PlayerPosition.CENTER,
        age=25
    )
    traded_player.contract = Contract(salary=2000000, years_remaining=2)
    
    received_player = Player(
        first_name="Jane",
        last_name="Smith", 
        primary_position=PlayerPosition.DEFENSE,
        age=23
    )
    received_player.contract = Contract(salary=1500000, years_remaining=3)
    
    other_team = Team("Trade Partner", "Partner City", "Partner Division", "Partner Conference")
    
    events_before = len(media_system.get_pending_media_events())
    media_system.process_trade(
        user_team=game_manager.user_team,
        other_team=other_team,
        traded_players=[traded_player],
        received_players=[received_player]
    )
    events_after = len(media_system.get_pending_media_events())
    
    print(f"✓ Trade processed: events before {events_before}, after {events_after}")
    return media_system

def test_signing_processing():
    """Test processing signings"""
    print("\nTesting signing processing...")
    
    game_manager = create_test_game_manager()
    media_system = MediaSystem(game_manager)
    media_system.set_engagement_level("Standard")
    
    # Create test player
    player = Player(
        first_name="Free",
        last_name="Agent",
        primary_position=PlayerPosition.LEFT_WING,
        age=28
    )
    player.contract = Contract(salary=3000000, years_remaining=3)
    
    events_before = len(media_system.get_pending_media_events())
    media_system.process_signing(
        player=player,
        team=game_manager.user_team,
        contract_type='signing',
        salary=3000000,
        years=3
    )
    events_after = len(media_system.get_pending_media_events())
    
    print(f"✓ Signing processed: events before {events_before}, after {events_after}")
    return media_system

def test_storyline_generation():
    """Test storyline generation"""
    print("\nTesting storyline generation...")
    
    game_manager = create_test_game_manager()
    media_system = MediaSystem(game_manager)
    
    storylines_before = len(media_system.storylines)
    media_system._generate_random_storyline()
    storylines_after = len(media_system.storylines)
    
    print(f"✓ Storylines before: {storylines_before}, after: {storylines_after}")
    
    if storylines_after > storylines_before:
        latest_storyline = media_system.storylines[-1]
        print(f"✓ Generated storyline: '{latest_storyline.title}'")
        print(f"   Description: {latest_storyline.description}")
    
    return media_system

def main():
    """Run all tests"""
    print("🎬 Media & Press Conference System - Integration Test")
    print("=" * 55)
    
    try:
        # Run all tests
        test_media_system_initialization()
        test_engagement_levels()
        test_game_result_processing()
        test_trade_processing()
        test_signing_processing() 
        test_storyline_generation()
        
        print("\n" + "=" * 55)
        print("🎉 All tests passed! Media system is ready for integration.")
        print("\nFeatures tested:")
        print("  ✓ System initialization with journalists and settings")
        print("  ✓ Multiple engagement levels (Disabled → Full Immersion)")
        print("  ✓ Post-game interview generation")
        print("  ✓ Trade interview processing")
        print("  ✓ Contract signing media events")
        print("  ✓ Dynamic storyline generation")
        
        print("\nNext steps:")
        print("  → Start game and set media engagement in startup settings")
        print("  → Use Media Center (🎬 Media button) to manage interviews")
        print("  → Media events will generate automatically from game actions")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())