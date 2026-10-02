#!/usr/bin/env python3
"""QA: Watch Live opens the visualizer as a real Toplevel window.

Muck's bug (2026-10-02): "clicking watch live does not take you to the
visualizer" -- the Sep 27 InGamePopup migration routed PBPVisualSim into
a 560x420 in-game card instead of its designed 1280x800 Toplevel window.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("== PBPVisualSim is a Toplevel (not an InGamePopup card) ==")
import tkinter as tk
from pbp_visual_sim import PBPVisualSim, open_pbp_window

check("PBPVisualSim extends tk.Toplevel",
      tk.Toplevel in PBPVisualSim.__mro__)

# InGamePopup must NOT be in the MRO (would route into a 560x420 card)
try:
    from popup_system import InGamePopup
    check("PBPVisualSim is not an InGamePopup",
          InGamePopup not in PBPVisualSim.__mro__)
except ImportError:
    check("PBPVisualSim is not an InGamePopup (no popup_system)", True)

print("== open_pbp_window returns a real Toplevel with rink geometry ==")
# Needs a display; skip gracefully headless
try:
    root = tk.Tk()
    root.withdraw()
except tk.TclError:
    print("  SKIP: no display (run under xvfb-run for widget tests)")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

from player_generator import PlayerGenerator
from game_classes import Team, PlayerPosition

gen = PlayerGenerator()
home = Team("Test Home", "TH", "Div", "Conf")
away = Team("Test Away", "TA", "Div", "Conf")
for i in range(12):
    home.roster.append(gen.create_player(position=PlayerPosition.CENTER,
                                         skill_tier="NHL_STARTER"))
for i in range(6):
    home.roster.append(gen.create_player(position=PlayerPosition.DEFENSE,
                                         skill_tier="NHL_STARTER"))
home.roster.append(gen.create_player(position=PlayerPosition.GOALIE,
                                     skill_tier="NHL_STARTER"))
for i in range(12):
    away.roster.append(gen.create_player(position=PlayerPosition.CENTER,
                                         skill_tier="NHL_STARTER"))
for i in range(6):
    away.roster.append(gen.create_player(position=PlayerPosition.DEFENSE,
                                         skill_tier="NHL_STARTER"))
away.roster.append(gen.create_player(position=PlayerPosition.GOALIE,
                                     skill_tier="NHL_STARTER"))

win = open_pbp_window(root, home, away)
check("open_pbp_window returns tk.Toplevel", isinstance(win, tk.Toplevel))
root.update_idletasks()
win.update_idletasks()
geo = win.geometry()
# Designed geometry is 1280x800 (may include +x+y offset)
check(f"visualizer geometry is 1280x800 (got {geo})",
      geo.startswith("1280x800"))
check("visualizer has title", bool(win.title()))
win.destroy()
root.destroy()

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
