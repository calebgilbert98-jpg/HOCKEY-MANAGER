"""
Test script to launch the game directly without splash/launcher
"""
import sys
import traceback

print("=" * 60)
print("DIRECT GAME LAUNCH TEST")
print("=" * 60)

try:
    print("\n1. Importing main modules...")
    from main import GameManager, HockeyManagerGUI
    print("✅ Main modules imported")
    
    print("\n2. Creating GameManager...")
    gm = GameManager()
    print("✅ GameManager created")
    
    print("\n3. Applying default startup settings...")
    default_settings = {
        'database_size': 'Medium',
        'fantasy_draft': False,
        'user_team': 'Carolina Hurricanes'
    }
    gm.apply_startup_settings(default_settings)
    print("✅ Startup settings applied")
    
    print("\n4. Verifying team setup...")
    if hasattr(gm, 'user_team') and gm.user_team:
        print(f"✅ User team: {gm.user_team.team_name}")
        print(f"✅ Roster size: {len(gm.user_team.roster)} players")
    
    print("\n5. Creating GUI...")
    app = HockeyManagerGUI(gm)
    app.startup_settings = default_settings
    app._update_game_viewer_button_state()
    print("✅ GUI created")
    
    print("\n6. Starting main loop...")
    print("=" * 60)
    print("GAME SHOULD NOW LAUNCH")
    print("=" * 60)
    
    app.mainloop()
    
    print("\n✅ Game closed normally")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
