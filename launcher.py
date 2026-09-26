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

        # --- MULTIPLAYER/CHECKPOINTS: crash-detection session flag ---
        # Written at launch, removed on clean exit (atexit below). A
        # leftover flag at the next launch means the previous session
        # died uncleanly -> the launcher offers checkpoint recovery.
        try:
            from checkpoint_manager import (
                mark_session_start, mark_clean_shutdown)
            mark_session_start()
            import atexit
            atexit.register(mark_clean_shutdown)
        except Exception as e:
            print(f"Session flag unavailable (non-fatal): {e}")

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