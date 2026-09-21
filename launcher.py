#!/usr/bin/env python3
"""
Puck Dynasty - Simple Game Launcher
Clean, simple entry point for the hockey management game
"""

import sys
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

# Ensure we can import from current directory
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Main entry point for Puck Dynasty"""
    try:
        print("🏒 Starting Puck Dynasty...")
        
        # Import and start the simple launcher
        from simple_launcher import PuckDynastyLauncher
        
        # Create and run the launcher
        launcher = PuckDynastyLauncher()
        launcher.mainloop()
        
        print("Puck Dynasty closed.")
        
    except Exception as e:
        print(f"Error: {e}")
        
        # Simple fallback - direct to main game
        try:
            from main import HockeyManagerGUI
            print("Starting game directly...")
            app = HockeyManagerGUI()
            app.mainloop()
        except Exception as e2:
            messagebox.showerror("Critical Error", 
                               f"Could not start Puck Dynasty:\n{str(e2)}")


if __name__ == "__main__":
    main()