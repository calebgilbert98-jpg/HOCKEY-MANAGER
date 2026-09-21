"""
Diagnostic script to find exactly where the game launch fails
"""
import sys
import traceback

print("=" * 70)
print("PUCK DYNASTY LAUNCH DIAGNOSTICS")
print("=" * 70)

step = 0

try:
    step = 1
    print(f"\nStep {step}: Testing Python environment...")
    print(f"   Python version: {sys.version}")
    print(f"   ✅ Python works")
    
    step = 2
    print(f"\nStep {step}: Testing tkinter import...")
    import tkinter as tk
    print(f"   ✅ tkinter imported")
    
    step = 3
    print(f"\nStep {step}: Testing tkinter window creation...")
    test_root = tk.Tk()
    test_root.withdraw()
    print(f"   ✅ tkinter window can be created")
    test_root.destroy()
    
    step = 4
    print(f"\nStep {step}: Importing main module...")
    import main
    print(f"   ✅ main module imported")
    
    step = 5
    print(f"\nStep {step}: Testing GameManager creation...")
    gm = main.GameManager()
    print(f"   ✅ GameManager created")
    
    step = 6
    print(f"\nStep {step}: Testing apply_startup_settings...")
    default_settings = {
        'database_size': 'Medium',
        'fantasy_draft': False,
        'user_team': 'Carolina Hurricanes'
    }
    gm.apply_startup_settings(default_settings)
    print(f"   ✅ Startup settings applied")
    
    step = 7
    print(f"\nStep {step}: Checking league and teams...")
    if hasattr(gm, 'league') and gm.league:
        print(f"   ✅ League exists")
        print(f"   ✅ Teams: {len(gm.league.teams)}")
        if gm.league.teams:
            first_team = gm.league.teams[0]
            print(f"   ✅ First team: {first_team.team_name}")
            print(f"   ✅ Roster size: {len(first_team.roster)}")
    
    step = 8
    print(f"\nStep {step}: Testing HockeyManagerGUI creation (WITHOUT mainloop)...")
    app = main.HockeyManagerGUI(gm)
    print(f"   ✅ GUI object created")
    
    step = 9
    print(f"\nStep {step}: Checking if GUI window exists...")
    if app.winfo_exists():
        print(f"   ✅ Window exists")
        print(f"   Window title: {app.title()}")
        print(f"   Window geometry: {app.geometry()}")
    else:
        print(f"   ❌ Window does not exist")
    
    step = 10
    print(f"\nStep {step}: Testing window visibility...")
    app.update()
    print(f"   ✅ Window updated")
    
    step = 11
    print(f"\nStep {step}: Cleaning up test...")
    app.destroy()
    print(f"   ✅ Window destroyed")
    
    print("\n" + "=" * 70)
    print("✅ ALL DIAGNOSTICS PASSED!")
    print("=" * 70)
    print("\nThe game components work correctly.")
    print("The issue might be with how main.py is being called.")
    print("\nTry running: python main.py")
    print("And look for any error messages in the terminal.")
    
except Exception as e:
    print(f"\n" + "=" * 70)
    print(f"❌ FAILED AT STEP {step}")
    print("=" * 70)
    print(f"\nError: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("\n" + "=" * 70)
