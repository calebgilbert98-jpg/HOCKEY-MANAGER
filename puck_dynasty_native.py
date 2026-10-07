"""Puck Dynasty native launcher.

Launches the PySide6/Qt native interface. The game logic runs in-process;
the UI calls it directly (no Flask, no browser, no HTTP).
"""
import sys
import os

# Ensure repo root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from native_ui.main_window import run


def main():
    game = None
    try:
        # Create the game instance (HockeyManagerGUI without running Tk mainloop)
        # The Qt app runs the event loop; we just need the game logic object.
        from main import HockeyManagerGUI
        # Create without showing Tk window
        import tkinter as tk
        # Use a hidden root to avoid Tk window appearing
        game = HockeyManagerGUI.__new__(HockeyManagerGUI)
        # Initialize minimal required attributes
        from game_classes import League
        game.league = League("Puck Dynasty Hockey League")
        game.league.set_game_manager(game)
        game.user_team = None
        game.startup_settings = None
        game.waiver_list = []
        game.trade_block = []
        print("Game instance created for native UI")
    except Exception as e:
        print(f"Game init failed: {e}")
        import traceback
        traceback.print_exc()
    sys.exit(run(game=game))


if __name__ == "__main__":
    main()
