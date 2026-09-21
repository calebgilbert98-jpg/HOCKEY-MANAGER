#!/usr/bin/env python3
"""
Visual test to see what the game viewer actually displays
"""

import tkinter as tk
from GAME_VIEWER import RebuiltNHLGameViewer

def test_visual_viewer():
    """Create a visible game viewer window to see what's displayed"""
    print("🏒 Creating visible game viewer test...")
    
    root = tk.Tk()
    root.title("Visual Game Viewer Test")
    
    # Create the viewer
    viewer = RebuiltNHLGameViewer(root)
    
    # Add a close button
    close_frame = tk.Frame(root, bg='#0f1419')
    close_frame.pack(side='bottom', fill='x', padx=10, pady=5)
    
    close_btn = tk.Button(
        close_frame, 
        text="Close Test", 
        command=root.destroy,
        bg='#D13438', 
        fg='white',
        font=('Segoe UI', 10)
    )
    close_btn.pack()
    
    print("🏒 Test window created - check what's displayed!")
    print("🏒 Look for:")
    print("   - Should see the PUCKDYNASTYRINKCOMPLETE.png image")
    print("   - Should NOT see a light blue rectangle with red center line")
    print("   - Press 'Close Test' when done examining")
    
    # Start the GUI
    root.mainloop()
    
    print("🏒 Visual test completed")

if __name__ == "__main__":
    test_visual_viewer()