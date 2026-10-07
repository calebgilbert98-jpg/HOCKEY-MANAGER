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
    # TODO: initialize game (new career / load career / setup wizard)
    # For now, launch with no game object (UI shell proof of concept).
    game = None
    try:
        # Attempt to create a minimal game instance for UI testing
        pass
    except Exception as e:
        print(f"Game init deferred: {e}")
    sys.exit(run(game=game))


if __name__ == "__main__":
    main()
