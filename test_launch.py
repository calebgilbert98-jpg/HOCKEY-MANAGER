"""
Test script to debug game launch issues
"""
import sys
import traceback

print("=" * 60)
print("TESTING GAME LAUNCH")
print("=" * 60)

try:
    print("\n1. Testing imports...")
    import main
    print("✅ main.py imports successfully")
    
    print("\n2. Testing GameManager creation...")
    gm = main.GameManager()
    print("✅ GameManager created")
    
    print("\n3. Testing default settings application...")
    default_settings = {
        'database_size': 'Medium',
        'fantasy_draft': False,
        'user_team': 'Carolina Hurricanes'
    }
    gm.apply_startup_settings(default_settings)
    print("✅ Startup settings applied")
    
    print("\n4. Checking league and teams...")
    if hasattr(gm, 'league') and gm.league:
        print(f"✅ League exists: {gm.league}")
        if hasattr(gm.league, 'teams'):
            print(f"✅ Teams count: {len(gm.league.teams)}")
            if gm.league.teams:
                first_team = gm.league.teams[0]
                print(f"✅ First team: {first_team.name}")
                if hasattr(first_team, 'roster'):
                    print(f"✅ Roster size: {len(first_team.roster)}")
                else:
                    print(f"⚠️ Team has no 'roster' attribute")
                    print(f"   Available attributes: {[a for a in dir(first_team) if not a.startswith('_')]}")
    else:
        print("❌ No league created")
    
    print("\n5. Testing GUI creation (without mainloop)...")
    import tkinter as tk
    
    # Create a test window to verify tkinter works
    test_root = tk.Tk()
    test_root.withdraw()  # Hide it immediately
    
    print("✅ Tkinter works")
    
    # Now try to create the actual GUI
    app = main.HockeyManagerGUI(gm)
    print("✅ HockeyManagerGUI created successfully")
    
    # Check if window exists
    if app.winfo_exists():
        print("✅ Window exists")
    else:
        print("❌ Window does not exist")
    
    print("\n6. Closing test window...")
    app.destroy()
    test_root.destroy()
    print("✅ Clean shutdown")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe game SHOULD launch successfully.")
    print("If it doesn't launch when you run 'python main.py',")
    print("the issue is likely with the splash_launcher.")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("\n" + "=" * 60)
    print("ISSUE FOUND - See error above")
    print("=" * 60)
