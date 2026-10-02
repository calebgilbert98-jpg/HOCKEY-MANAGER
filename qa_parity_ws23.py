# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: WS2 (assist duality -> one shared decision) + WS3 (D29 grade clamp on
GameSim) parity probes. Headless. Run: python3 qa_parity_ws23.py"""
import sys, random, inspect
sys.path.insert(0, '/home/hatch/workspace/wt-parity')
assert 'wt-parity' in __import__('simulation').__file__, "wrong tree!"
from types import SimpleNamespace
import mesh_system as ms
from simulation import GameSim
from quick_sim import AdvancedGameSim
from game_classes import PlayerPosition

PASS, FAIL = 0, 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ok   {name}")
    else:
        FAIL += 1; print(f"  FAIL {name} {extra}")

def mkp(name, pid, passing=70, vision=70, oaw=70):
    return SimpleNamespace(id=pid, full_name=name, passing=passing,
                           vision=vision, offensive_awareness=oaw,
                           relationships={}, primary_position=PlayerPosition.CENTER)

# --- WS2: one shared setup-man decision -------------------------------
shooter = mkp("Shooter", 1, 80, 80, 80)
pool = [mkp("Playmaker", 2, 95, 95, 95),
        mkp("Grinder", 3, 40, 40, 40),
        mkp("Mid", 4, 65, 65, 65)]
team = SimpleNamespace(team_name="TST")

random.seed(7)
pick1 = ms.select_setup_man(pool, shooter, team)
random.seed(7)
pick2 = ms.select_setup_man(pool, shooter, team)
check("select_setup_man deterministic under seed",
      pick1 is not None and pick2 is not None and pick1.id == pick2.id,
      f"{getattr(pick1,'id',None)} vs {getattr(pick2,'id',None)}")
check("select_setup_man favors the playmaker over 20 seeded draws",
      sum(1 for s in range(20)
          if (random.seed(s), ms.select_setup_man(pool, shooter, team).id == 2)[1]) >= 12)
check("select_setup_man None on empty pool", ms.select_setup_man([], shooter, team) is None)
check("select_setup_man never raises on junk",
      ms.select_setup_man(None, None, None) is None)

# Spy: both engines must call the ONE shared function.
calls = []
_orig = ms.select_setup_man
def _spy(p, s, t, is_playoff=False):
    calls.append((len(p), s.id, t.team_name))
    return p[0]
ms.select_setup_man = _spy
try:
    # GameSim._award_assists with a minimal fake self
    on_ice = [shooter] + pool
    gs_self = SimpleNamespace(
        _get_on_ice=lambda tm: on_ice, assist_pairs=[], is_playoff=False)
    import unittest.mock as _mock
    with _mock.patch("random.random", return_value=0.0):  # pass the 0.75 gate
        assists = GameSim._award_assists(gs_self, shooter, team, passer=None)
    check("GameSim._award_assists calls shared select_setup_man",
          len(calls) == 1 and calls[0] == (3, 1, "TST"), calls)
    check("GameSim primary came from the shared pick",
          assists and assists[0].id == 2, [a.id for a in assists])

    calls.clear()
    # AdvGS._credit_assists with a minimal fake self
    aq_self = SimpleNamespace(
        home_team=team, away_team=SimpleNamespace(team_name="OPP"),
        on_ice={"TST": {"Forwards": on_ice, "Defense": []}},
        stats={"TST": {p.id: {} for p in on_ice}},
        assist_pairs=[], is_playoff=False)
    shooter.assist_potential = None
    with _mock.patch("random.random", return_value=0.0):  # pass the 0.65 gate
        aids, aplayers = AdvancedGameSim._credit_assists(aq_self, shooter, "TST")
    check("AdvGS._credit_assists calls shared select_setup_man",
          len(calls) == 1 and calls[0] == (3, 1, "TST"), calls)
    check("AdvGS primary came from the shared pick",
          aids and aids[0] == 2, aids)
finally:
    ms.select_setup_man = _orig

# --- WS3: D29 grade clamp on GameSim -----------------------------------
src = inspect.getsource(GameSim._resolve_shot_on_goal)
check("GameSim applies chance_grade_clamp", "chance_grade_clamp" in src)
check("GameSim clamp skips empty net", "not empty_net" in src)
check("clamp A band unchanged (protected)", ms.chance_grade_clamp("A") == (0.10, 0.18))
check("clamp B band unchanged (protected)", ms.chance_grade_clamp("B") == (0.04, 0.12))
check("clamp C band unchanged (protected)", ms.chance_grade_clamp("C") == (0.015, 0.09))
check("finish mult unchanged (protected)",
      ms.CHANCE_GRADE_FINISH_MULT == {"A": 1.75, "B": 1.00, "C": 0.35},
      ms.CHANCE_GRADE_FINISH_MULT)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
