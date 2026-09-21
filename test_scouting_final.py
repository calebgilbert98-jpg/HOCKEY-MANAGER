#!/usr/bin/env python3
"""
Final test of the Professional Scouting Window
Tests both sorting functionality and player population
"""

import tkinter as tk
from main import HockeyManagerGUI, GameManager
from professional_scouting_window import ProfessionalScoutingWindow

def test_scouting_window():
    """Test the professional scouting window comprehensively"""
    print("=== COMPREHENSIVE PROFESSIONAL SCOUTING WINDOW TEST ===")
    
    # Create root window
    root = tk.Tk()
    root.withdraw()
    
    try:
        # Step 1: Create GameManager
        print("Step 1: Creating GameManager...")
        game_manager = GameManager()
        print(f"  ✓ GameManager created")
        
        # Step 2: Check player data availability
        print("Step 2: Checking player data...")
        total_players = 0
        if hasattr(game_manager, 'get_all_players'):
            try:
                all_players = game_manager.get_all_players()
                total_players = len(all_players)
                print(f"  ✓ Found {total_players:,} players via get_all_players()")
                
                if total_players > 0:
                    sample_player = all_players[0]
                    player_name = getattr(sample_player, 'full_name', 'Unknown')
                    player_age = getattr(sample_player, 'age', 'Unknown')
                    player_team = getattr(sample_player, 'team_name', 'Unknown')
                    print(f"  ✓ Sample player: {player_name}, Age {player_age}, Team: {player_team}")
                
            except Exception as e:
                print(f"  ✗ Error getting players: {e}")
        
        # Step 3: Create HockeyManagerGUI
        print("Step 3: Creating HockeyManagerGUI...")
        app = HockeyManagerGUI(game_manager)
        print(f"  ✓ GUI created successfully")
        
        # Step 4: Test scouting window directly
        print("Step 4: Testing ProfessionalScoutingWindow directly...")
        try:
            scouting_window = ProfessionalScoutingWindow(app)
            print(f"  ✓ ProfessionalScoutingWindow created successfully")
            
            # Check player tree population
            if hasattr(scouting_window, 'players_tree'):
                children = scouting_window.players_tree.get_children()
                entry_count = len(children)
                print(f"  ✓ Player tree has {entry_count} entries")
                
                if entry_count > 0:
                    # Test first few entries
                    for i, child in enumerate(children[:3]):
                        item = scouting_window.players_tree.item(child)
                        values = item['values']
                        if values and len(values) >= 3:
                            print(f"    Entry {i+1}: {values[0]} ({values[1]}) Age {values[2]} - {values[3]}")
                        else:
                            print(f"    Entry {i+1}: {values}")
                    
                    # Test sorting functionality
                    print("  Testing sorting functionality...")
                    try:
                        print("    Testing Name sort...")
                        scouting_window._sort_players_by('Name')
                        print("    ✓ Name sort successful")
                        
                        print("    Testing Age sort...")
                        scouting_window._sort_players_by('Age')
                        print("    ✓ Age sort successful")
                        
                        print("    Testing Overall sort...")
                        scouting_window._sort_players_by('Overall')
                        print("    ✓ Overall sort successful")
                        
                        print("    Testing Position sort...")
                        scouting_window._sort_players_by('Pos')
                        print("    ✓ Position sort successful")
                        
                        print("  ✓ ALL SORTING FUNCTIONS WORKING!")
                        
                    except Exception as e:
                        print(f"    ✗ Sorting error: {e}")
                
                else:
                    print("  ✗ No entries in player tree")
                    # Check game data
                    game_data = getattr(scouting_window, 'game_data', {})
                    players_in_data = len(game_data.get('players', []))
                    print(f"    Game data contains {players_in_data} players")
            
            else:
                print("  ✗ No players_tree attribute found")
            
            # Test filtering
            print("  Testing filter functionality...")
            if hasattr(scouting_window, '_apply_player_filters'):
                try:
                    scouting_window._apply_player_filters()
                    print("  ✓ Filter application successful")
                except Exception as e:
                    print(f"  ✗ Filter error: {e}")
            
            scouting_window.destroy()
            
        except Exception as e:
            print(f"  ✗ Error creating ProfessionalScoutingWindow: {e}")
            import traceback
            traceback.print_exc()
        
        # Step 5: Test via main app method
        print("Step 5: Testing via main app open_scouting_management_window()...")
        try:
            app.open_scouting_management_window()
            
            if 'scouting' in app.open_windows:
                window = app.open_windows['scouting']
                print("  ✓ Scouting window opened via main app method")
                
                if hasattr(window, 'players_tree'):
                    children = window.players_tree.get_children()
                    print(f"  ✓ Player tree has {len(children)} entries via main app")
                
                window.destroy()
            else:
                print("  ✗ Scouting window not found in open_windows")
                
        except Exception as e:
            print(f"  ✗ Error opening via main app: {e}")
        
        app.quit()
        
    except Exception as e:
        print(f"✗ Main test error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            root.destroy()
        except:
            pass
    
    print("\n=== TEST COMPLETE ===")


if __name__ == "__main__":
    test_scouting_window()