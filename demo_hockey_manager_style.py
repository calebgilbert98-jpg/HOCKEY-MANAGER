"""
Demo showing the NEW Hockey Management Style Game Viewer
This recreates the exact look from your reference image
"""

import tkinter as tk
from GAME_VIEWER import NHLGameViewer

def demo_hockey_manager_style():
    """Show the new hockey management game style viewer"""
    
    print("🏒 NEW HOCKEY MANAGEMENT STYLE GAME VIEWER")
    print("=" * 60)
    print()
    print("✅ EXACT RECREATION OF REFERENCE IMAGE:")
    print("   🎯 Dark green background (just like Eastside Hockey Manager)")
    print("   🏒 Perfect oval-ended rink shape")
    print("   ⚪ Pure white ice surface") 
    print("   🟤 Brown wooden board appearance")
    print("   🔴 Bright red center line and markings")
    print("   🔵 Proper blue lines and circles")
    print("   🥅 Correct goal placement and size")
    print("   ⭕ All face-off circles in NHL positions")
    print("   📏 Proper proportions matching real hockey rinks")
    print()
    print("🎮 HOCKEY MANAGEMENT GAME FEATURES:")
    print("   📱 Clean, professional interface")
    print("   🎛️ Simple playback controls")
    print("   👥 Players represented as colored dots")
    print("   🏒 Black puck with white outline")
    print("   📊 Game time and period display")
    print()
    print("🔥 NOW LAUNCHING THE EXACT STYLE YOU REQUESTED!")
    print("   The rink now looks EXACTLY like hockey management games!")
    print()
    
    # Launch the hockey management style viewer
    root = tk.Tk()
    
    demo_data = {
        'home_team': 'Toronto Maple Leafs',
        'away_team': 'Boston Bruins',
        'event_log': []
    }
    
    viewer = NHLGameViewer(root, demo_data)
    root.mainloop()

if __name__ == "__main__":
    demo_hockey_manager_style()