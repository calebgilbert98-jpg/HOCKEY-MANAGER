#!/usr/bin/env python3
"""QA for E4-E8 engine fixes (Muck 2026-10-02).

E4: personal_grade_ceiling lower bound scales with finishing (not fixed floor)
E5: GameSim uses situational_goalie_skill + effective_goalie_skill (parity)
E6: quick_sim passes all skaters (F+D) to ceiling_scenario_mult, not just F
E7: quick_sim._calculate_fatigue_factor reads condition_system pools
E8: D27 morale gate (neutral 70, 1-100) present

Run: python3 qa_engine_e4_e8.py (from repo root, isolated subprocess)
"""
import sys
import os

# pt.py isolation per ~/AGENTS.md
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib

# Purge any pristine imports
for _mod in list(sys.modules.keys()):
    if _mod in ("mesh_system", "quick_sim", "simulation", "condition_system",
                "player_traits", "pt"):
        del sys.modules[_mod]

import mesh_system
assert "HOCKEY-MANAGER" in mesh_system.__file__, f"Wrong mesh_system: {mesh_system.__file__}"

passed = 0
failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")

class FakePlayer:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

print("E4: personal grade ceiling lower bound scales with finishing")
# Grade A clamp is (0.10, 0.18) — protected, must be unchanged.
_lo_c, _hi_c = mesh_system.chance_grade_clamp(mesh_system.CHANCE_GRADE_A)
check("CHANCE_GRADE_CLAMP Grade A unchanged (0.10, 0.18)",
      (_lo_c, _hi_c) == (0.10, 0.18), f"got {(_lo_c, _hi_c)}")

# finishing_rating is a 13-member harmonic blend; build players with
# realistic attribute spreads so the blend actually differs.
def _mk(fin):
    attrs = dict(wristshot=fin, slapshot=fin, one_timer=fin, backhand=fin,
                 shooting_accuracy=fin, composure=fin, hockey_iq=fin,
                 offensive_positioning=fin, off_the_puck=fin,
                 anticipation=fin, pressure_player=fin, deflections=fin,
                 balance=fin, strength=fin, determination=fin,
                 aggressiveness=fin, morale=70)
    return FakePlayer(**attrs)

p60 = _mk(60)
p95 = _mk(95)
# Sanity: the blend should separate them.
f60 = mesh_system.finishing_rating(p60)
f95 = mesh_system.finishing_rating(p95)
check("finishing_rating separates 60 vs 95", f95 - f60 > 15,
      f"f60={f60:.1f} f95={f95:.1f}")
lo60, hi60 = mesh_system.personal_grade_ceiling(p60, mesh_system.CHANCE_GRADE_A)
lo95, hi95 = mesh_system.personal_grade_ceiling(p95, mesh_system.CHANCE_GRADE_A)
check("60-finisher lo < 95-finisher lo (separation)", lo60 < lo95,
      f"60:[{lo60:.3f},{hi60:.3f}] 95:[{lo95:.3f},{hi95:.3f}]")
check("60-finisher lo below old 0.10 floor", lo60 < 0.10, f"lo60={lo60:.3f}")
check("95-finisher keeps full envelope", abs(hi95 - 0.18) < 0.01 and abs(lo95 - 0.10) < 0.01,
      f"95:[{lo95:.3f},{hi95:.3f}]")

print("E5: GameSim situational goalie (parity with quick_sim)")
# situational_goalie_skill exists and re-weights by situation.
g = FakePlayer(positioning=90, reflexes=60, glove_hand=70, stick_side=70,
               rebound_control=80, composure=85)
s_clean = mesh_system.situational_goalie_skill(g, "clean")
s_tip = mesh_system.situational_goalie_skill(g, "tip")
check("situational re-weighting changes skill by situation", abs(s_clean - s_tip) > 0.5,
      f"clean={s_clean:.1f} tip={s_tip:.1f}")
# effective_goalie_skill compresses toward mean.
import inspect
sim_src = inspect.getsource(__import__("simulation"))
check("simulation.py uses situational_goalie_skill",
      "situational_goalie_skill" in sim_src)
check("simulation.py uses effective_goalie_skill",
      "effective_goalie_skill" in sim_src)

print("E6: quick_sim passes all skaters to ceiling_scenario_mult")
qs_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "quick_sim.py")).read()
check("quick_sim includes Defense in linemates",
      "_oi.get('Defense'" in qs_src or '"Defense"' in qs_src)

print("E7: quick_sim fatigue reads condition_system")
check("quick_sim imports get_game_energy",
      "get_game_energy" in qs_src)
check("quick_sim imports fatigue_resistance",
      "fatigue_resistance" in qs_src)

print("E8: D27 morale gate (neutral 70, 1-100 scale)")
check("morale default 70 in mesh_system",
      'getattr(player, "morale", 70)' in open(
          os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "mesh_system.py")).read())

print(f"\n{passed}/{passed+failed} checks passed")
sys.exit(0 if failed == 0 else 1)
