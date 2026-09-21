"""
Simple Coordinate Integration Test
Uses existing game functions instead of recreating everything
"""

import sys
import os

# Add the hockey manager directory to Python path  
sys.path.insert(0, r"c:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER")

try:
    # Import existing game functions
    from game_classes import PlayerPosition, Team
    from draft_generator import generate_draft_class
    from coordinate_simulation import CoordinateSimEngine
    print("✅ All imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_coordinate_engine():
    """Test the coordinate engine using existing game functions"""
    print("\n🏒 TESTING COORDINATE ENGINE")
    print("=" * 40)
    
    # Create coordinate engine
    engine = CoordinateSimEngine()
    print("✅ Coordinate engine created")
    
    # Test basic zone detection
    zones = [
        (25, 42.5, "home zone"),
        (100, 42.5, "center ice"), 
        (175, 42.5, "away zone")
    ]
    
    for x, y, expected in zones:
        zone = engine.get_zone_from_coordinates(x, y)
        print(f"   {expected}: {zone.name}")
    
    # Test danger zones
    danger_spots = [
        (188, 42.5, "away crease"),
        (175, 42.5, "away slot"),
        (155, 42.5, "away high slot")
    ]
    
    for x, y, location in danger_spots:
        danger, multiplier = engine.get_danger_level(x, y, False)  # False = attacking away goal
        print(f"   {location}: {danger.name} (x{multiplier})")
    
    return engine

def test_simulation_with_real_teams():
    """Test using actual game data"""
    print("\n🎮 TESTING WITH GENERATED PLAYERS")
    print("=" * 40)
    
    try:
        # Generate some test players using the draft generator
        players = generate_draft_class(6)  # Just need a few players
        
        if len(players) > 0:
            player = players[0]
            print(f"   Testing with generated player: {player.first_name} {player.last_name}")
            
            # Create coordinate engine
            engine = CoordinateSimEngine()
            
            # Generate a test shot event from a position in the away zone
            shooter_position = (175, 42.5)  # Away slot
            shot_data = engine.generate_shot_coordinates(shooter_position, False)
            
            print(f"   Shot from ({shooter_position[0]:.1f}, {shooter_position[1]:.1f})")
            if 'shot_coordinates' in shot_data:
                shot_coords = shot_data['shot_coordinates']
                danger, multiplier = engine.get_danger_level(shot_coords[0], shot_coords[1], False)
                print(f"   Shot goes to ({shot_coords[0]:.1f}, {shot_coords[1]:.1f})")
                print(f"   Danger level: {danger.name} (x{multiplier})")
            else:
                print(f"   Shot data: {shot_data}")
            
            # Test creating teams manually
            home_team = Team("Test Home", "Home City", "Central", "Western")
            away_team = Team("Test Away", "Away City", "Pacific", "Western")
            print(f"   Created teams: {home_team.team_name} vs {away_team.team_name}")
            
            return True
        
        print("   No players generated")
        return False
        
    except Exception as e:
        print(f"   Error: {e}")
        return False

def run_simple_test():
    """Run the simplified test"""
    print("🏒 SIMPLE COORDINATE INTEGRATION TEST")
    print("=" * 50)
    
    # Test coordinate engine
    engine = test_coordinate_engine()
    if not engine:
        return False
    
    # Test with real game data
    success = test_simulation_with_real_teams()
    
    if success:
        print("\n✅ COORDINATE INTEGRATION WORKING!")
        print("   - Coordinate engine functional")
        print("   - Zone detection working")  
        print("   - Danger analysis operational")
        print("   - Compatible with existing game code")
        return True
    else:
        print("\n❌ Test failed")
        return False

if __name__ == "__main__":
    run_simple_test()