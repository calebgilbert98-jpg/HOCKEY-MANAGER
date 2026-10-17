"""Puck Dynasty native launcher (v2).

Minimal bundling-safe rebuild. The game logic runs in-process;
the UI calls it directly (no Flask, no browser, no HTTP).

Import-time safe: only stdlib path setup runs at import time.
GameManager creation happens inside main().
"""
import sys
import os

# Ensure repo root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    game = None
    try:
        # Create a real GameManager instance (UI-agnostic).
        from game_manager import GameManager
        game = GameManager()
        print(f"[v2] GameManager created ({len(game.league.teams)} teams)")
    except Exception:
        print("[v2] Game init failed:")
        import traceback
        traceback.print_exc()
    from native_ui_v2.main_window import run
    sys.exit(run(game=game))


if __name__ == "__main__":
    main()
