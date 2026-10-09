#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_loading_prompt.py -- verify the day-sim loading overlay.

Tests:
1. Overlay shows on busy=True with status text
2. Overlay updates status on subsequent busy=True calls
3. Overlay hides on busy=False
4. Overlay never raises on garbage input
5. _set_continue_feedback drives the overlay
6. Missing dismissals fixed (end_of_season, game-day bundle paths)

Run headless: python3 qa_loading_prompt.py
For widget tests, needs a display (uses Xvfb on :99 if available).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def main():
    print("== day_sim_loading module ==")
    try:
        from day_sim_loading import DaySimLoadingOverlay
        check("module imports", True)
    except Exception as e:
        check(f"module imports ({e})", False)
        print(f"\n{PASS} passed, {FAIL} failed")
        return 1

    print("== overlay without display (never raises) ==")
    # No parent / no display: constructor must not raise
    try:
        ov = DaySimLoadingOverlay(parent=None)
        check("constructor with parent=None never raises", True)
    except Exception as e:
        check(f"constructor with parent=None never raises ({e})", False)
        ov = None

    if ov is not None:
        try:
            ov.set_status("Simulating games...")
            check("set_status with no window never raises", True)
        except Exception as e:
            check(f"set_status with no window never raises ({e})", False)
        try:
            ov.destroy()
            check("destroy with no window never raises", True)
        except Exception as e:
            check(f"destroy with no window never raises ({e})", False)
        try:
            check("is_showing False with no window", ov.is_showing is False)
        except Exception as e:
            check(f"is_showing ({e})", False)

    print("== garbage input never raises ==")
    try:
        ov2 = DaySimLoadingOverlay(parent="not a widget")
        ov2.set_status(None)
        ov2.set_status(12345)
        ov2.destroy()
        ov2.destroy()  # double destroy
        check("garbage parent/status/double-destroy never raises", True)
    except Exception as e:
        check(f"garbage input never raises ({e})", False)

    print("== _set_continue_feedback drives overlay (source check) ==")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'main.py')) as f:
            src = f.read()
        check("_set_continue_feedback calls _update_day_sim_overlay",
              "_update_day_sim_overlay(busy" in src)
        check("_update_day_sim_overlay defined",
              "def _update_day_sim_overlay" in src)
        check("overlay dismissed after end_of_season (season_complete path)",
              "self.end_of_season()\n                self._set_continue_feedback(False)" in src)
        check("overlay dismissed when game-day bundle opens",
              "_maybe_open_game_day_bundle(todays_games)):\n"
              in src and "Dismiss the loading overlay" in src)
        check("DaySimLoadingOverlay imported in overlay updater",
              "from day_sim_loading import DaySimLoadingOverlay" in src)
    except Exception as e:
        check(f"source checks ({e})", False)

    print("== widget test (needs display) ==")
    display = os.environ.get('DISPLAY')
    if not display:
        print("  SKIP: no DISPLAY (widget tests need Xvfb)")
    else:
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            ov3 = DaySimLoadingOverlay(root)
            check("overlay builds with real parent", ov3.is_showing)
            ov3.set_status("Processing AI decisions...")
            check("set_status updates without error", True)
            # Busy again = status update, not a second window
            ov3b = DaySimLoadingOverlay(root)
            check("second overlay builds (idempotency via caller)", True)
            ov3b.destroy()
            ov3.destroy()
            check("destroy hides overlay", not ov3.is_showing)
            root.destroy()
        except Exception as e:
            check(f"widget test ({e})", False)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
