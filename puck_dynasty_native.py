"""Puck Dynasty native launcher.

Launches the PySide6/Qt native interface. The game logic runs in-process;
the UI calls it directly (no Flask, no browser, no HTTP).

Requires PySide6. Install the native dependencies first:
    pip install -r requirements-native.txt
(or ensure PySide6 is installed via the native build workflow's pinned
requirements).
"""
import sys
import os

# Ensure repo root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from native_ui.main_window import run
except ImportError as e:
    print("=" * 70)
    print("ERROR: PySide6 is required to run the native UI but is not installed.")
    print()
    print("Install the native dependencies with:")
    print("    pip install -r requirements-native.txt")
    print()
    print(f"(ImportError: {e})")
    print("=" * 70)
    sys.exit(1)


def main():
    game = None
    try:
        # Create a real GameManager instance (UI-agnostic, no Tkinter needed)
        # GameManager holds all game state and logic; native_ui calls it directly.
        from game_manager import GameManager
        game = GameManager()
        print(f"GameManager created for native UI ({len(game.league.teams)} teams)")
    except Exception as e:
        print(f"Game init failed: {e}")
        import traceback
        traceback.print_exc()
    sys.exit(run(game=game))


if __name__ == "__main__":
    main()
