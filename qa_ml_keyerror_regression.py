"""Regression: _predict_player_development KeyError (~1/60 games, pre-existing).

Root cause (fixed 2026-09-27): when a roster has no goalie,
Team.get_starting_goalie() fabricates a throwaway "Default Goalie" who can
land on the ice without being in either roster or GameSim.game_stats; the
Stage-10 ML update then indexed the missing player id. _update_ml_predictions
now skips on-ice players absent from game_stats.

These tests pin the guard: a direct unit probe plus a multi-seed game sweep
with goalie-less rosters (the Default Goalie path).
"""
import random
import sys

sys.path.insert(0, ".")

passed, failed = [], []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" -- {detail}" if detail and not cond else ""))


import game_classes as g
from game_classes import PlayerPosition
from simulation import GameSim


def make_teams(seed, goalies=True):
    random.seed(seed)
    t1 = g.Team("Home HC", "HHC", "Div", "Conf")
    t2 = g.Team("Away HC", "AHC", "Div", "Conf")
    for i in range(13):
        for t in (t1, t2):
            pos = PlayerPosition.CENTER if i % 3 else PlayerPosition.LEFT_WING
            t.roster.append(g.Player(
                first_name=f"S{seed}", last_name=f"P{i}", age=25,
                primary_position=pos, jersey_number=i + 1))
    if goalies:
        for t in (t1, t2):
            t.roster.append(g.Player(
                first_name=f"G{seed}", last_name="Net", age=30,
                primary_position=PlayerPosition.GOALIE, jersey_number=30))
    return t1, t2


# 1: direct probe -- a phantom on-ice player must be skipped, not crash ----
t1, t2 = make_teams(1)
sim = GameSim(t1, t2)
phantom = g.Player(first_name="Default", last_name="Goalie", age=35,
                   primary_position=PlayerPosition.GOALIE, jersey_number=0)
assert phantom.id not in sim.game_stats
sim.home_on_ice.append(phantom)
try:
    sim._update_ml_predictions()
    check("phantom on-ice player skipped without KeyError", True)
except KeyError as e:
    check("phantom on-ice player skipped without KeyError", False, f"KeyError {e}")

# 2: normal players still get predictions ------------------------------------
t1, t2 = make_teams(2)
sim = GameSim(t1, t2)
real = t1.roster[0]
sim.home_on_ice.append(real)
sim._update_ml_predictions()
check("real on-ice player still gets a development prediction",
      sim.game_stats[real.id].get("development_prediction") is not None)

# 3: multi-seed sweep, goalie-less rosters (Default Goalie path) --------------
crashes = 0
N = 30
for seed in range(100, 100 + N):
    try:
        h, a = make_teams(seed, goalies=False)
        GameSim(h, a).simulate_game()
    except Exception as e:  # noqa: BLE001 -- counting any crash
        crashes += 1
        print(f"    seed {seed}: {type(e).__name__}: {e}")
check(f"{N}-game goalie-less sweep: zero crashes", crashes == 0,
      f"{crashes} crashes")

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
