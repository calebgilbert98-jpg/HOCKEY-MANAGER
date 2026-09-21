"""
FLUID MOVEMENT TEST
Demonstration of the enhanced smooth player movement system
"""

from GAME_VIEWER import launch_game_viewer
import random
import math

def create_fluid_movement_demo():
    """Create events that showcase the fluid movement system"""
    events = []
    current_time = 0.0
    
    # Start with face-off
    events.append({
        'timestamp': current_time,
        'type': 'FACE_OFF',
        'details': {'location': 'center'}
    })
    current_time += 1.0
    
    # Demonstrate smooth player movements
    print("🏒 Creating fluid movement demonstration...")
    
    # 1. SMOOTH SKATING PATTERNS
    skating_patterns = [
        # Home team creates flowing movements
        ('home_0', [(95, 42.5), (90, 40), (85, 35), (80, 30), (75, 25)]),  # Curved path
        ('home_1', [(85, 35), (70, 25), (60, 20), (50, 25), (45, 35)]),    # S-curve
        ('home_2', [(85, 50), (70, 60), (60, 65), (50, 60), (45, 50)]),    # Mirror S-curve
        
        # Away team creates counter-movements
        ('away_0', [(105, 42.5), (110, 45), (115, 50), (120, 55), (125, 60)]),  # Diagonal
        ('away_1', [(115, 35), (130, 25), (140, 20), (150, 25), (155, 35)]),    # Away S-curve
        ('away_2', [(115, 50), (130, 60), (140, 65), (150, 60), (155, 50)]),    # Away mirror
    ]
    
    # Add smooth movement sequences
    for player_id, path in skating_patterns:
        for i, (x, y) in enumerate(path):
            events.append({
                'timestamp': current_time + i * 2.0,
                'type': 'SKATE',
                'details': {
                    'player_id': player_id,
                    'target_pos': (x, y)
                }
            })
        current_time += len(path) * 2.0 + 1.0
    
    # 2. PUCK MOVEMENT WITH REALISTIC PHYSICS
    puck_sequence = [
        (100, 42.5),  # Center
        (110, 40),    # Pass 1
        (125, 35),    # Pass 2
        (140, 30),    # Pass 3
        (160, 35),    # Shot approach
        (175, 42.5),  # At goal
        (165, 45),    # Rebound
        (145, 50),    # Clear
        (120, 55),    # Possession change
        (100, 50),    # Back to center area
        (80, 45),     # Other direction
        (60, 40),     # Deep
        (40, 42.5),   # Very deep
        (25, 42.5),   # At home goal
    ]
    
    print(f"   Adding {len(puck_sequence)} smooth puck movements...")
    
    for i, (x, y) in enumerate(puck_sequence):
        events.append({
            'timestamp': current_time + i * 1.5,
            'type': 'PUCK_MOVEMENT',
            'details': {'target_pos': (x, y)}
        })
    
    current_time += len(puck_sequence) * 1.5 + 2.0
    
    # 3. COMPLEX COORDINATED MOVEMENTS
    print("   Adding coordinated team movements...")
    
    # Power play setup - coordinated movement
    power_play_setup = [
        # Time 1: Initial setup
        [
            ('home_0', (90, 42.5)),   # Center
            ('home_1', (85, 30)),     # Left wing
            ('home_2', (85, 55)),     # Right wing
            ('home_3', (75, 25)),     # Left D
            ('home_4', (75, 60)),     # Right D
        ],
        # Time 2: Rotation
        [
            ('home_0', (95, 35)),     # Center moves
            ('home_1', (80, 25)),     # Wing cycles
            ('home_2', (90, 60)),     # Wing high
            ('home_3', (70, 30)),     # D shifts
            ('home_4', (80, 65)),     # D shifts
        ],
        # Time 3: Attack formation
        [
            ('home_0', (100, 40)),    # Center attacks
            ('home_1', (90, 20)),     # Wing low
            ('home_2', (95, 65)),     # Wing high
            ('home_3', (75, 35)),     # D supports
            ('home_4', (85, 60)),     # D ready
        ]
    ]
    
    for formation_time, formation in enumerate(power_play_setup):
        for player_id, (x, y) in formation:
            events.append({
                'timestamp': current_time + formation_time * 3.0,
                'type': 'SKATE',
                'details': {
                    'player_id': player_id,
                    'target_pos': (x, y)
                }
            })
    
    current_time += len(power_play_setup) * 3.0 + 2.0
    
    # 4. ACTION SEQUENCES WITH SMOOTH EFFECTS
    action_sequence = [
        ('SHOT', {'player_id': 'home_1', 'target': 'goal'}),
        ('SAVE', {'goalie_id': 'away_5'}),
        ('PUCK_MOVEMENT', {'target_pos': (160, 50)}),  # Rebound
        ('SKATE', {'player_id': 'away_3', 'target_pos': (140, 55)}),  # Defense clears
        ('PASS', {'from': 'away_3', 'to': 'away_1'}),
        ('PUCK_MOVEMENT', {'target_pos': (120, 60)}),
        ('SKATE', {'player_id': 'away_1', 'target_pos': (100, 65)}),  # Breakout
        ('GOAL', {'scorer': 'away_1'}),
    ]
    
    print(f"   Adding {len(action_sequence)} action events with effects...")
    
    for event_type, details in action_sequence:
        events.append({
            'timestamp': current_time,
            'type': event_type,
            'details': details
        })
        current_time += 2.5
    
    # 5. CELEBRATION AND RESET
    events.append({
        'timestamp': current_time,
        'type': 'FACE_OFF',
        'details': {'location': 'center'}
    })
    
    print(f"✅ Created {len(events)} events showcasing fluid movement")
    return events

def test_fluid_movement():
    """Test the enhanced fluid movement system"""
    print("🏒 FLUID MOVEMENT DEMONSTRATION")
    print("=" * 50)
    
    events = create_fluid_movement_demo()
    
    print()
    print("🎯 FLUID MOVEMENT FEATURES TO OBSERVE:")
    print("   • 60 FPS smooth animations (vs 20 FPS before)")
    print("   • Natural easing curves for realistic movement")
    print("   • Distance-based animation timing")
    print("   • Smooth puck physics with realistic acceleration")
    print("   • Coordinated team movements")
    print("   • No stuttering or jerky motion")
    print("   • Professional-quality animation system")
    print()
    print("🎬 DEMONSTRATION SEQUENCE:")
    print("   1. Smooth skating patterns (curved paths)")
    print("   2. Realistic puck movement with physics")
    print("   3. Coordinated team formations")
    print("   4. Action sequences with visual effects")
    print("   5. Natural movement flow throughout")
    print()
    print("🚀 Launching Fluid Movement Demo...")
    
    launch_game_viewer(
        event_log=events,
        duration=180,  # 3 minutes
        home_team="Philadelphia Flyers",
        away_team="New York Rangers"
    )

if __name__ == "__main__":
    test_fluid_movement()