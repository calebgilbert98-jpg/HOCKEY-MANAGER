#!/usr/bin/env python3
"""
Test the Professional Scouting Window with main app context
"""

import tkinter as tk
import sys
import os

# Add the project directory to sys.path
project_dir = r"c:\Users\caleb\OneDrive\Desktop\HOCKEY MANAGER"
if project_dir not in sys.path:
    sys.path.append(project_dir)

def test_with_main_app():
    """Test scouting window within main app context"""
    print("=== TESTING WITH MAIN APP CONTEXT ===")
    
    try:
        from main import HockeyManagerGUI
        
        print("Step 1: Creating main application...")
        root = tk.Tk()
        root.withdraw()  # Hide main window
        
        app = HockeyManagerGUI(root)
        print("  ✓ Main application created")
        
        print("Step 2: Checking app data...")
        print(f"  Game manager exists: {hasattr(app, 'game_manager')}")
        print(f"  User team exists: {hasattr(app, 'user_team')}")
        print(f"  League exists: {hasattr(app, 'league')}")
        
        if hasattr(app, 'game_manager') and app.game_manager:
            all_players = app.game_manager.get_all_players()
            print(f"  Total players in game: {len(all_players)}")
            
            if all_players:
                sample = all_players[0]
                print(f"  Sample player: {sample.full_name}")
                print(f"  Sample player attributes: age={sample.age}, overall={sample.overall_rating()}")
        
        print("Step 3: Opening ProfessionalScoutingWindow through main app...")
        app.open_scouting_management_window()
        
        # Get the window
        scouting_window = app.open_windows.get('scouting')
        if scouting_window:
            print("  ✓ Scouting window opened successfully")
            
            # Check what's in the players tree
            if hasattr(scouting_window, 'players_tree'):
                children = scouting_window.players_tree.get_children()
                print(f"  Players tree has {len(children)} entries")
                
                if len(children) > 0:
                    first_item = scouting_window.players_tree.item(children[0])
                    values = first_item['values']
                    print(f"  First entry values: {values}")
                    
                    if values and len(values) > 0:
                        if 'No players' in str(values[0]):
                            print("  ❌ Shows 'No players' message")
                            
                            # Debug the data flow
                            print("\nDebugging data flow:")
                            print(f"    Game data players: {len(scouting_window.game_data.get('players', []))}")
                            
                            # Check filter variables
                            print("    Filter variables:")
                            for var_name, var in scouting_window.filter_vars.items():
                                if 'player_' in var_name:
                                    print(f"      {var_name}: '{var.get()}'")
                            
                            # Check filtered results
                            filtered = scouting_window._get_filtered_players()
                            print(f"    Filtered players: {len(filtered)}")
                            
                        else:
                            print(f"  ✓ Shows real player: {values[0]}")
            
            scouting_window.destroy()
        else:
            print("  ❌ Scouting window not found in open_windows")
        
        root.destroy()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== MAIN APP TEST COMPLETE ===")

if __name__ == "__main__":
    test_with_main_app()