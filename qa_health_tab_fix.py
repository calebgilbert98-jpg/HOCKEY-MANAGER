#!/usr/bin/env python3
"""QA: Health tab injury fix — verify injury reports match player state.

Muck 2026-10-02: The inbox had "Injury Report: Mason Bernard" but the
player card Health tab showed "Healthy". Root causes:
1. Fake injury reports were generated for healthy players (main.py post-game)
2. Real injury emails used random injury types/timelines, not player's actual data
3. Two injury paths (simulation.py hit, main.py training) didn't append to injury_history
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

print("== Health tab injury fix QA ==")

# 1. Fake post-game injury reports removed
print("\n[1] No fake injury reports")
with open("main.py") as f:
    src = f.read()
check("fake 'Game-related injury' email removed",
      "Game-related injury - evaluation in progress" not in src)
check("fake 5% random injury roll removed",
      'if random.random() < 0.05:  # 5% chance of injury report after game' not in src)

# 2. Daily injury emails use actual player data
print("\n[2] Injury emails use real player data")
check("uses player.injury_type (not random)",
      "getattr(player, 'injury_type'" in src)
check("uses player.games_remaining_injured (not random weeks)",
      "getattr(player, 'games_remaining_injured'" in src)
check("no random injury_types list for email",
      'injury_types = ["Upper body injury", "Lower body injury"' not in src)

# 3. simulation.py hit path appends to injury_history
print("\n[3] simulation.py hit path records history")
with open("simulation.py") as f:
    sim_src = f.read()
check("injury_history append in hit path",
      'victim.injury_history' in sim_src)

# 4. main.py training path appends to injury_history
print("\n[4] main.py training path records history")
# Find the training knock section and check for history append nearby
idx = src.find('victim.injury_type = "Training knock"')
section = src[idx:idx+800] if idx >= 0 else ""
check("injury_history append in training path",
      "injury_history" in section)

# 5. Health tab still reads is_injured correctly
print("\n[5] Health tab logic intact")
with open("modern_profile.py") as f:
    prof_src = f.read()
check("Health tab checks is_injured",
      'getattr(p, "is_injured", False)' in prof_src)
check("Health tab shows Active Injury card when injured",
      "Active Injury" in prof_src)

# 6. Compile check
print("\n[6] Compile check")
import py_compile
for fn in ("main.py", "simulation.py", "modern_profile.py"):
    try:
        py_compile.compile(fn, doraise=True)
        check(f"{fn} compiles", True)
    except Exception as e:
        check(f"{fn} compiles: {e}", False)

print(f"\n{passed}/{passed+failed} passed")
sys.exit(0 if failed == 0 else 1)
