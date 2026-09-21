"""
PERFECTED GAME VIEWER TEST
Complete test of the corrected game viewer with proper coordinates and layout
"""

from GAME_VIEWER import launch_game_viewer
import random

def create_corrected_test_events():
    """Create test events that respect the corrected coordinate system"""
    events = []
    current_time = 0.0
    
    # Game start - face-off at center
    events.append({
        'timestamp': current_time,
        'type': 'FACE_OFF',
        'details': {'location': 'center'}
    })
    current_time += 2.0
    
    # Test movement within corrected boundaries
    movements = [
        # Home team movements (left side)
        ('home_0', (90, 42.5)),    # Center to face-off
        ('home_1', (80, 30)),      # Left wing position
        ('home_2', (80, 55)),      # Right wing position
        ('home_3', (50, 20)),      # Defense position
        ('home_4', (50, 65)),      # Defense position
        ('home_5', (25, 42.5)),    # Goalie in net (CORRECTED)
        
        # Away team movements (right side)
        ('away_0', (110, 42.5)),   # Center
        ('away_1', (120, 55)),     # Left wing
        ('away_2', (120, 30)),     # Right wing
        ('away_3', (150, 65)),     # Defense
        ('away_4', (150, 20)),     # Defense
        ('away_5', (175, 42.5)),   # Goalie in net (CORRECTED)
    ]
    
    # Add movement events
    for player_id, (x, y) in movements:
        events.append({
            'timestamp': current_time,
            'type': 'SKATE',
            'details': {
                'player_id': player_id,
                'target_pos': (x, y)
            }
        })
        current_time += 1.0
    
    # Puck movement following play
    puck_movements = [
        (100, 42.5),  # Center ice
        (120, 40),    # Towards away zone
        (150, 35),    # In away zone
        (170, 42.5),  # Near away goal
        (160, 45),    # Rebound
        (140, 50),    # Back out
        (100, 42.5),  # Back to center
    ]
    
    for pos in puck_movements:
        events.append({
            'timestamp': current_time,
            'type': 'PUCK_MOVEMENT',
            'details': {'target_pos': pos}
        })
        current_time += 2.0
    
    # Game action events
    action_events = [
        ('SHOT', {'player_id': 'home_1', 'target': 'away_goal'}),
        ('SAVE', {'goalie_id': 'away_5'}),
        ('PASS', {'from': 'away_5', 'to': 'away_3'}),
        ('SKATE', {'player_id': 'away_3', 'target_pos': (130, 50)}),
        ('SHOT', {'player_id': 'away_2', 'target': 'home_goal'}),
        ('GOAL', {'scorer': 'away_2', 'assist': 'away_3'}),
        ('FACE_OFF', {'location': 'center'}),
    ]
    
    for event_type, details in action_events:
        events.append({
            'timestamp': current_time,
            'type': event_type,
            'details': details
        })
        current_time += 3.0
    
    return events

def test_perfected_viewer():
    """Test the perfected viewer with corrected coordinates"""
    print("🏒 PERFECTED GAME VIEWER TEST")
    print("=" * 50)
    
    # Create test events
    events = create_corrected_test_events()
    print(f"✅ Created {len(events)} test events with corrected coordinates")
    
    print()
    print("🎯 TESTING FEATURES:")
    print("   • Compact rink display (700x350)")
    print("   • Corrected goalie positions (x=25, x=175)")
    print("   • All players within rink boundaries")
    print("   • Side panels with stats and controls")
    print("   • Interactive canvas with coordinate display")
    print("   • Professional PNG background integration")
    print()
    print("🚀 Launching Perfected Game Viewer...")
    
    # Launch with test data
    launch_game_viewer(
        event_log=events,
        duration=300,  # 5 minutes
        home_team="Philadelphia Flyers",
        away_team="New York Rangers"
    )

if __name__ == "__main__":
    test_perfected_viewer()