"""
EHM Integration Demonstration
Shows the sophisticated simulation engine in action
"""

import sys
import os

# Add the hockey manager directory to Python path
sys.path.insert(0, r"c:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER")

from enhanced_player_system import EnhancedPlayer, PersonalityType
from ehm_simulation_engine import EHMSimulationEngine, GameAction, ActionType
from game_classes import PlayerPosition
import random

def create_demo_player(name: str, position: PlayerPosition, personality: PersonalityType) -> EnhancedPlayer:
    """Create a demo player with specific personality"""
    
    # Split name
    first_name, last_name = name.split(' ', 1)
    
    player = EnhancedPlayer(
        id=f"demo_{hash(name)}",
        first_name=first_name,
        last_name=last_name,
        age=random.randint(20, 30),
        primary_position=position,
        overall=random.randint(75, 90),
        personality_type=personality
    )
    
    return player

def demonstrate_ehm_simulation():
    """Demonstrate the EHM-style simulation with personality-driven gameplay"""
    
    print("🏒 EHM-Style Hockey Simulation Demonstration")
    print("=" * 60)
    
    # Create demo teams with different personality types
    print("\n📋 Creating Teams with Diverse Player Personalities")
    print("-" * 50)
    
    # Home Team - "Thunderbirds" (Aggressive, skilled team)
    home_team = [
        create_demo_player("Connor McDavid", PlayerPosition.CENTER, PersonalityType.CLUTCH_PERFORMER),
        create_demo_player("Leon Draisaitl", PlayerPosition.LEFT_WING, PersonalityType.VOLATILE_STAR),
        create_demo_player("Zach Hyman", PlayerPosition.RIGHT_WING, PersonalityType.TEAM_PLAYER),
        create_demo_player("Darnell Nurse", PlayerPosition.LEFT_DEFENSE, PersonalityType.ENFORCER),
        create_demo_player("Evan Bouchard", PlayerPosition.RIGHT_DEFENSE, PersonalityType.PLAYMAKER),
        create_demo_player("Stuart Skinner", PlayerPosition.GOALIE, PersonalityType.STEADY_VETERAN)
    ]
    
    # Away Team - "Eagles" (Balanced, defensive team)
    away_team = [
        create_demo_player("Sidney Crosby", PlayerPosition.CENTER, PersonalityType.STEADY_VETERAN),
        create_demo_player("Jake Guentzel", PlayerPosition.LEFT_WING, PersonalityType.CONSISTENT_GRINDER),
        create_demo_player("Rickard Rakell", PlayerPosition.RIGHT_WING, PersonalityType.TEAM_PLAYER),
        create_demo_player("Kris Letang", PlayerPosition.LEFT_DEFENSE, PersonalityType.PLAYMAKER),
        create_demo_player("Erik Karlsson", PlayerPosition.RIGHT_DEFENSE, PersonalityType.VOLATILE_STAR),
        create_demo_player("Tristan Jarry", PlayerPosition.GOALIE, PersonalityType.INCONSISTENT_PROSPECT)
    ]
    
    # Display team personalities
    print(f"🏠 HOME TEAM - Thunderbirds:")
    for player in home_team:
        print(f"   {player.full_name} ({player.primary_position.value}) - {player.personality_type.value}")
    
    print(f"\n🚌 AWAY TEAM - Eagles:")
    for player in away_team:
        print(f"   {player.full_name} ({player.primary_position.value}) - {player.personality_type.value}")
    
    # Create EHM simulation engine
    print(f"\n🎮 Initializing EHM Simulation Engine")
    print("-" * 40)
    
    sim_engine = EHMSimulationEngine("Thunderbirds", "Eagles", home_team, away_team)
    
    print(f"✅ Simulation initialized!")
    print(f"   Starting lineups set")
    print(f"   Game state: Period {sim_engine.game_state.period}, {sim_engine.game_state.time_remaining//60:02d}:{sim_engine.game_state.time_remaining%60:02d}")
    print(f"   Momentum: {sim_engine.game_state.momentum:.1f}")
    
    # Simulate several events to show personality-driven decision making
    print(f"\n🎯 Simulating Key Game Events")
    print("-" * 35)
    
    events_to_simulate = 20
    interesting_events = []
    
    for i in range(events_to_simulate):
        action = sim_engine.simulate_next_event()
        if not action:
            break
        
        # Track interesting events (goals, big hits, personality-driven decisions)
        if any(keyword in action.description.lower() for keyword in ['goal', 'hit', 'deke', 'check']):
            interesting_events.append(action)
        
        # Stop if game ends
        if 'game_end' in action.consequences:
            break
    
    # Display interesting events with personality analysis
    print(f"\n🌟 Notable Events (Personality-Driven Gameplay):")
    print("=" * 55)
    
    for i, event in enumerate(interesting_events[:10], 1):  # Show top 10 events
        print(f"\n{i}. {event.description}")
        
        # Analyze the decision based on player personality
        player = event.primary_player
        personality_analysis = analyze_personality_decision(player, event)
        if personality_analysis:
            print(f"   🧠 Personality Factor: {personality_analysis}")
    
    # Show final game state
    print(f"\n📊 Final Game State")
    print("-" * 25)
    print(f"Score: Thunderbirds {sim_engine.game_state.home_score} - {sim_engine.game_state.away_score} Eagles")
    print(f"Period: {sim_engine.game_state.period}")
    time_remaining = int(sim_engine.game_state.time_remaining)
    print(f"Time: {time_remaining//60:02d}:{time_remaining%60:02d}")
    print(f"Momentum: {sim_engine.game_state.momentum:.1f}")
    print(f"Total Events: {len(sim_engine.event_log)}")
    
    # Show player performance modifiers
    print(f"\n🎭 Player Performance Analysis")
    print("-" * 35)
    
    all_players = home_team + away_team
    for player in all_players[:6]:  # Show first 6 players
        context = {'pressure_level': 5, 'is_clutch_time': False}
        modifier = player.get_performance_modifier(context)
        print(f"{player.full_name}: {modifier:.2f}x performance ({player.personality_type.value})")

def analyze_personality_decision(player: EnhancedPlayer, action: GameAction) -> str:
    """Analyze how personality influenced the player's decision"""
    
    personality = player.personality_type
    action_type = action.action_type
    
    if personality == PersonalityType.CLUTCH_PERFORMER and action_type == ActionType.SHOOT:
        return f"{player.full_name} (CLUTCH) takes the shot in a pressure moment"
    
    elif personality == PersonalityType.VOLATILE_STAR and not action.success:
        return f"{player.full_name} (VOLATILE) shows inconsistency with a failed attempt"
    
    elif personality == PersonalityType.TEAM_PLAYER and action_type == ActionType.PASS:
        return f"{player.full_name} (TEAM PLAYER) prioritizes team play with a pass"
    
    elif personality == PersonalityType.ENFORCER and action_type == ActionType.CHECK:
        return f"{player.full_name} (ENFORCER) shows physical dominance with a big hit"
    
    elif personality == PersonalityType.SELFISH_SCORER and action_type == ActionType.SHOOT:
        return f"{player.full_name} (SELFISH) prioritizes personal scoring chance"
    
    elif personality == PersonalityType.STEADY_VETERAN and action.success:
        return f"{player.full_name} (VETERAN) shows reliable, consistent execution"
    
    elif personality == PersonalityType.CONSISTENT_GRINDER:
        return f"{player.full_name} (GRINDER) demonstrates steady work ethic"
    
    return None

if __name__ == "__main__":
    try:
        demonstrate_ehm_simulation()
        
        print(f"\n" + "=" * 60)
        print("🎉 EHM-Style Simulation Complete!")
        print("Key Features Demonstrated:")
        print("  ✅ Personality-driven decision making")
        print("  ✅ Dynamic performance modifiers")
        print("  ✅ Emergent gameplay narratives")
        print("  ✅ Deep attribute-based simulation")
        print("  ✅ Realistic event chains")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Demo Error: {e}")
        import traceback
        traceback.print_exc()
