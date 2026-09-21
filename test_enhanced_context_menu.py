#!/usr/bin/env python3
"""
Test script for enhanced player context menu functionality
Demonstrates the new features without requiring full game launch
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from game_classes import Player, PlayerPosition
    from player_context_menu import PlayerContextMenu, add_player_context_menu
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

class TestApp:
    """Test application for enhanced context menu"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enhanced Player Context Menu - Demo")
        self.root.geometry("800x600")
        
        # Set up colors to match game theme
        self.BG_COLOR = '#181818'
        self.CONTENT_BG = '#1F1F1F'
        self.TEXT_COLOR = '#E0E0E0'
        self.HEADER_COLOR = '#FFFFFF'
        self.ACCENT_COLOR = '#D13438'
        
        self.root.configure(bg=self.BG_COLOR)
        
        # Initialize tree maps for context menu
        self.tree_maps = {}
        
        # Create some test players
        self.create_test_players()
        
        # Create the interface
        self.create_interface()
        
        # Set up tree maps for context menu
        self.tree_maps = {}
    
    def create_test_players(self):
        """Create some test players for demonstration"""
        self.test_players = []
        
        # Create test players with different attributes
        players_data = [
            ("Connor McDavid", PlayerPosition.CENTER, 27, 20, 19, 18, 16),
            ("Sidney Crosby", PlayerPosition.CENTER, 36, 18, 17, 19, 17),
            ("Alexander Ovechkin", PlayerPosition.LEFT_WING, 38, 17, 20, 15, 16),
            ("Erik Karlsson", PlayerPosition.RIGHT_DEFENSE, 33, 16, 14, 17, 18),
            ("Carey Price", PlayerPosition.GOALIE, 36, 12, 8, 12, 19),
        ]
        
        for name, position, age, skating, shooting, passing, defense in players_data:
            first_name = name.split()[0]
            last_name = " ".join(name.split()[1:])
            player = Player(
                first_name=first_name,
                last_name=last_name,
                age=age,
                primary_position=position
            )
            player.skating = skating
            player.shooting = shooting
            player.passing = passing
            player.defense = defense
            player.hockey_iq = 16
            player.physical = 15
            player.potential = 18 if age < 25 else 16 if age < 30 else 14
            
            self.test_players.append(player)
    
    def create_interface(self):
        """Create the test interface"""
        # Header
        header = tk.Label(self.root, text="Enhanced Player Context Menu Demo", 
                         font=('Segoe UI', 16, 'bold'), 
                         fg=self.HEADER_COLOR, bg=self.BG_COLOR)
        header.pack(pady=20)
        
        # Instructions
        instructions = tk.Label(self.root, 
                              text="Right-click on any player below to see the enhanced context menu with real functionality:",
                              font=('Segoe UI', 11), 
                              fg=self.TEXT_COLOR, bg=self.BG_COLOR)
        instructions.pack(pady=10)
        
        # Features list
        features_text = """
Enhanced Features:
• Contract Details - Opens player profile with contract tab
• Scout Player - Opens scouting assignment dialog  
• Player Comparison - Advanced comparison tool with multiple tabs
• Trade Proposal - Create trade proposals with teams
• Training Assignment - Assign specific training focuses
• All with professional styling and real functionality!
        """
        
        features = tk.Label(self.root, text=features_text, justify='left',
                           font=('Segoe UI', 9), 
                           fg=self.TEXT_COLOR, bg=self.BG_COLOR)
        features.pack(pady=10)
        
        # Create treeview for players
        tree_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        tree_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        columns = ('Name', 'Position', 'Age', 'Overall', 'Skating', 'Shooting', 'Passing', 'Defense')
        self.player_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        
        # Configure columns
        for col in columns:
            self.player_tree.heading(col, text=col)
            if col == 'Name':
                self.player_tree.column(col, width=150)
            elif col == 'Position':
                self.player_tree.column(col, width=100)
            else:
                self.player_tree.column(col, width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.player_tree.yview)
        self.player_tree.configure(yscrollcommand=scrollbar.set)
        
        self.player_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Populate with test players
        self.populate_players()
        
        # Add enhanced context menu
        add_player_context_menu(self.player_tree, self)
        
        # Close button
        close_btn = ttk.Button(self.root, text="Close Demo", command=self.root.quit)
        close_btn.pack(pady=10)
    
    def populate_players(self):
        """Populate the treeview with test players"""
        self.tree_maps[self.player_tree] = {}
        
        for player in self.test_players:
            values = (
                player.full_name,
                player.primary_position.value,
                player.age,
                player.overall_rating(),
                player.skating,
                player.shooting,
                player.passing,
                player.defense
            )
            
            item_id = self.player_tree.insert('', 'end', values=values)
            self.tree_maps[self.player_tree][item_id] = player
    
    def run(self):
        """Run the demo application"""
        print("Enhanced Player Context Menu Demo")
        print("=" * 40)
        print("Right-click on any player to test the enhanced context menu!")
        print("Features include:")
        print("- Contract details with player profile integration")
        print("- Scout assignment dialog")
        print("- Advanced player comparison tool") 
        print("- Trade proposal system")
        print("- Training assignment interface")
        print("- Professional styling throughout")
        print()
        
        self.root.mainloop()

if __name__ == "__main__":
    try:
        app = TestApp()
        app.run()
    except Exception as e:
        print(f"Error running demo: {e}")
        import traceback
        traceback.print_exc()