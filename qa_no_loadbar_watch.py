#!/usr/bin/env python3
"""qa_no_loadbar_watch.py — verify the day-sim loading overlay is hidden
when the visualizer opens for a watched game, but still shows for quick-sim.

Muck 2026-10-02: "the simulating loading bar shouldnt need to be active
while im watching a game sim"
"""
import os
import sys
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1

print("== no loading overlay during watched games ==")

with open(os.path.join(_HERE, "main.py"), "r") as f:
    src = f.read()

# 1. Locate the visualizer method and the open_pbp_window call within it.
mstart = src.find("def _simulate_game_with_pbp_visual(")
check("_simulate_game_with_pbp_visual found", mstart != -1)
open_idx = src.find("open_pbp_window(self,", mstart)
check("open_pbp_window call found in visualizer path", open_idx != -1)

if mstart != -1 and open_idx != -1:
    # 2. Overlay-hide call exists between method start and window open.
    hide_idx = src.find("_update_day_sim_overlay(False)", mstart, open_idx)
    check("overlay-hide call present before visualizer opens", hide_idx != -1)
    # 3. It's try/except guarded (never raises).
    guard_region = src[max(mstart, hide_idx - 300):hide_idx + 120]
    check("hide call is try/except guarded",
          hide_idx != -1 and "try:" in guard_region
          and "except" in guard_region)

# 4. Quick-sim path still shows the overlay (Watch/Quick choice -> Quick).
m2 = re.search(r"if not use_game_viewer:.*?_update_day_sim_overlay\(True",
               src, re.DOTALL)
check("quick-sim re-shows overlay after Watch/Quick choice", m2 is not None)

# 5. The overlay helper itself exists (existing never-raises contract).
check("_update_day_sim_overlay exists",
      "def _update_day_sim_overlay(" in src)

# 6. Only one open_pbp_window call site (the one we fixed).
call_sites = re.findall(r"(?<!#)(?<!\w)open_pbp_window\(self,", src)
check("single open_pbp_window call site (all covered)",
      len(call_sites) == 1)

# 7. win_ref defensively initialized (the _on_done callback reads it).
check("win_ref initialized before use (defensive)",
      "win_ref['win'] = None" in src)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
