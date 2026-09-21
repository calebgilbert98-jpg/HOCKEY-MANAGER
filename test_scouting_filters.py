#!/usr/bin/env python3
"""
Test the Professional Scouting Window filter system
"""

import tkinter as tk
from professional_scouting_window import ProfessionalScoutingWindow

def test_scouting_filters():
    """Test scouting window filter functionality"""
    print("=== PROFESSIONAL SCOUTING WINDOW FILTER TEST ===")
    
    # Create test parent
    class TestParent(tk.Tk):
        def __init__(self):
            super().__init__()
            self.withdraw()
            
            # Visual attributes
            self.BG_COLOR = '#181818'
            self.CONTENT_BG = '#1F1F1F'
            self.TITLE_BAR_COLOR = '#2A2A2A'
            self.TEXT_COLOR = '#E0E0E0'
            self.HEADER_COLOR = '#FFFFFF'
            self.ACCENT_COLOR = '#D13438'
            self.ACCENT_ACTIVE = '#A1272A'
            self.ACCENT_HOVER = '#E54E52'
            self.FONT_FAMILY = 'Segoe UI'
            
            # Game data attributes
            self.game_manager = None
            self.user_team = None
            self.league = None
    
    parent = TestParent()
    
    try:
        print("Step 1: Creating ProfessionalScoutingWindow...")
        window = ProfessionalScoutingWindow(parent)
        print("  ✓ Window created successfully")
        
        print("Step 2: Checking initial filter settings...")
        for var_name, var in window.filter_vars.items():
            if 'player_' in var_name:
                value = var.get()
                print(f"  {var_name}: '{value}'")
        
        print("Step 3: Checking game data...")
        players = window.game_data.get('players', [])
        print(f"  Game data has {len(players)} players")
        
        if players:
            sample_player = players[0]
            print(f"  Sample player: {getattr(sample_player, 'full_name', 'Unknown')}")
        
        print("Step 4: Testing filter application...")
        filtered_players = window._get_filtered_players()
        print(f"  Filtered players: {len(filtered_players)}")
        
        if len(filtered_players) != len(players):
            print(f"  ⚠️  Filter is restricting players ({len(filtered_players)} vs {len(players)})")
        else:
            print("  ✓ Filter is showing all players (as expected)")
        
        print("Step 5: Testing player tree population...")
        if hasattr(window, 'players_tree'):
            children = window.players_tree.get_children()
            print(f"  Player tree has {len(children)} entries")
            
            if len(children) > 0:
                first_item = window.players_tree.item(children[0])
                values = first_item['values']
                if values and len(values) > 0:
                    if values[0] == 'No players found':
                        print("  ❌ Shows 'No players found'")
                    elif values[0] == 'No players match current filters':
                        print("  ❌ Shows 'No players match current filters'")
                    else:
                        print(f"  ✓ Shows real player: {values[0]}")
                        print("  ✓ FILTERS ARE WORKING CORRECTLY!")
                else:
                    print("  ⚠️  Empty values in first entry")
            else:
                print("  ❌ No entries in player tree")
        
        print("Step 6: Testing clear filters function...")
        window._clear_player_filters()
        print("  ✓ Clear filters executed")
        
        # Check if tree repopulated
        if hasattr(window, 'players_tree'):
            children_after = window.players_tree.get_children()
            print(f"  Player tree after clear: {len(children_after)} entries")
        
        window.destroy()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            parent.destroy()
        except:
            pass
    
    print("\n=== FILTER TEST COMPLETE ===")

if __name__ == "__main__":
    test_scouting_filters()