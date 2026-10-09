#!/usr/bin/env python3
"""QA: 1x speed slowed down + pause actually pauses the visualizer.

Checks (no GUI needed — inspects code structure and constants):
1. GAME_RATE is slower than the old 8.0 (1x should be watchable)
2. Dot skating dt_gs is 0 when paused (dots freeze)
3. Puck drift pstep is 0 when paused (puck freezes)
4. _step_pending_shot returns early when paused (shots don't fire)
5. Speed buttons still 1x/2x/4x (multipliers proportional)
6. _toggle_play flips self.playing
"""
import re
import sys

SRC = "/tmp/wt-speed1x/pbp_visual_sim.py"
with open(SRC) as f:
    src = f.read()

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

print("== 1x speed ==")
m = re.search(r"GAME_RATE\s*=\s*([\d.]+)", src)
rate = float(m.group(1)) if m else None
check(f"GAME_RATE is defined (found {rate})", rate is not None)
check(f"GAME_RATE ({rate}) slower than old 8.0", rate is not None and rate < 8.0)
check(f"GAME_RATE ({rate}) still positive", rate is not None and rate > 0)
if rate:
    full_game_min = 3600 / rate / 60
    print(f"  INFO: full 60-min game at 1x = {full_game_min:.1f} min real time")
    check("full game between 10-30 min (watchable)", 10 <= full_game_min <= 30)

print("== pause freezes dots ==")
# dt_gs gated on self.playing
check("dot skating dt_gs gated on self.playing",
      re.search(r"dt_gs\s*=.*if self\.playing else 0\.0", src, re.DOTALL) is not None)

print("== pause freezes puck drift ==")
check("puck drift pstep gated on self.playing",
      re.search(r"pstep\s*=.*if self\.playing else 0\.0", src, re.DOTALL) is not None)

print("== pause stops pending shots ==")
m2 = re.search(r"def _step_pending_shot\(self, now\):(.*?)(?=\n    def )", src, re.DOTALL)
body = m2.group(1) if m2 else ""
check("_step_pending_shot checks self.playing",
      "not self.playing" in body)

print("== speed controls intact ==")
check("1x/2x/4x buttons present",
      all(f'"{x}x"' in src for x in (1, 2, 4)))
check("_toggle_play flips self.playing",
      "self.playing = not self.playing" in src)
check("_set_speed sets self.speed",
      re.search(r"def _set_speed.*?self\.speed\s*=\s*v", src, re.DOTALL) is not None)

print("== pause gates event consumption ==")
check("event consumption gated on self.playing",
      "if (self.playing and now >=" in src)

print(f"\n{passed}/{passed+failed} pass")
sys.exit(0 if failed == 0 else 1)
