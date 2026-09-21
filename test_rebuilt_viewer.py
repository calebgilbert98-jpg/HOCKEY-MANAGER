"""
TEST SCRIPT FOR REBUILT GAME VIEWER
Comprehensive test of the new game viewer with realistic game events
"""

from GAME_VIEWER import launch_game_viewer
import random
import time

def create_realistic_game_events():
    """Create a realistic sequence of hockey game events"""
    events = []
    current_time = 0.0
    
    # Game start - face-off
    events.append({
        'timestamp': current_time,
        'type': 'FACE_OFF',
        'details': {'location': 'center'}
    })
    current_time += 2.0
    
    # First period action
    for i in range(15):  # 15 events in first period
        # Random player movement
        team = 'home' if random.random() < 0.5 else 'away'
        player_id = f'{team}_{random.randint(0, 5)}'
        
        # Random position within rink bounds
        x = random.uniform(10, 190)
        y = random.uniform(10, 75)
        
        events.append({
            'timestamp': current_time,
            'type': 'SKATE',
            'details': {
                'player_id': player_id,
                'target_pos': (x, y)
            }
        })
        current_time += random.uniform(3, 8)
        
        # Puck follows player sometimes
        if random.random() < 0.4:
            events.append({
                'timestamp': current_time,
                'type': 'PUCK_MOVEMENT',
                'details': {'target_pos': (x + random.uniform(-5, 5), y + random.uniform(-5, 5))}
            })
            current_time += 1.0
        
        # Random game events
        event_type = random.choice(['SHOT', 'PASS', 'HIT', 'SAVE'])
        if event_type == 'SHOT':
            # Shot toward goal
            goal_x = 185 if team == 'home' else 15
            goal_y = random.uniform(35, 50)
            
            events.append({
                'timestamp': current_time,
                'type': 'SHOT',
                'details': {
                    'player_id': player_id,
                    'target_pos': (goal_x, goal_y)
                }
            })
            current_time += 1.5
            
            # Outcome: Goal or Save
            if random.random() < 0.15:  # 15% goal chance
                events.append({
                    'timestamp': current_time,
                    'type': 'GOAL',
                    'details': {'scorer': player_id}
                })
                current_time += 3.0
                
                # Face-off after goal
                events.append({
                    'timestamp': current_time,
                    'type': 'FACE_OFF',
                    'details': {'location': 'center'}
                })
            else:
                events.append({
                    'timestamp': current_time,
                    'type': 'SAVE',
                    'details': {'goalie_id': f'{"away" if team == "home" else "home"}_5'}
                })
            current_time += 2.0
            
        elif event_type == 'PASS':
            teammate_id = f'{team}_{random.randint(0, 4)}'
            events.append({
                'timestamp': current_time,
                'type': 'PASS',
                'details': {'from': player_id, 'to': teammate_id}
            })
            current_time += 1.0
            
        elif event_type == 'HIT':
            events.append({
                'timestamp': current_time,
                'type': 'HIT',
                'details': {'hitter': player_id}
            })
            current_time += 2.0
    
    # Add some penalties
    for _ in range(2):
        events.append({
            'timestamp': current_time,
            'type': 'PENALTY',
            'details': {
                'player_id': f'{"home" if random.random() < 0.5 else "away"}_{random.randint(0, 5)}',
                'penalty': 'Tripping'
            }
        })
        current_time += random.uniform(20, 40)
    
    return events

def test_viewer_with_realistic_data():
    """Test the viewer with realistic game data"""
    print("🏒 Creating realistic game events...")
    events = create_realistic_game_events()
    print(f"✅ Created {len(events)} realistic game events")
    
    print("🚀 Launching Game Viewer with realistic data...")
    print("   - Players will move around the rink")
    print("   - Puck will follow the action")
    print("   - Visual effects for shots, goals, saves")
    print("   - Professional NHL rink background")
    print("   - Proper coordinate mapping")
    
    # Launch viewer
    launch_game_viewer(
        event_log=events,
        duration=600,  # 10 minutes
        home_team="Philadelphia Flyers",
        away_team="New York Rangers"
    )

if __name__ == "__main__":
    test_viewer_with_realistic_data()