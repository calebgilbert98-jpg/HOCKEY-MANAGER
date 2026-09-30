# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for scoring_balance.py: shared OT/SV% tuning decisions.

- tie_late_factor math (tied/3rd/under-10:00 -> 0.80, everything else 1.0,
  garbage in -> 1.0 out, kill switch via constants == 1.0)
- both engines import the module and run games end-to-end with it active
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scoring_balance as sb

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")

# --- tie_late_factor math ---
check("tied 3rd, 5:00 left -> 0.80",
      sb.tie_late_factor(3, 300, 2, 2) == sb.TIE_LATE_XG_MULT == 0.80)
check("tied 3rd, 9:59 left -> 0.80", sb.tie_late_factor(3, 599, 0, 0) == 0.80)
check("tied 3rd, exactly 10:00 left -> 1.0 (boundary)",
      sb.tie_late_factor(3, 600, 2, 2) == 1.0)
check("not tied 3rd late -> 1.0", sb.tie_late_factor(3, 300, 3, 2) == 1.0)
check("tied 3rd early -> 1.0", sb.tie_late_factor(3, 900, 1, 1) == 1.0)
check("tied in 2nd -> 1.0", sb.tie_late_factor(2, 100, 2, 2) == 1.0)
check("tied in OT (period 4) -> 1.0", sb.tie_late_factor(4, 200, 3, 3) == 1.0)
check("garbage in -> 1.0", sb.tie_late_factor(None, "x", None, {}) == 1.0)
check("negative clock tied 3rd -> 0.80 (still late)",
      sb.tie_late_factor(3, -5, 2, 2) == 0.80)

# --- kill switch: constants at 1.0 restore prior behavior ---
_orig_mult, _orig_tune = sb.TIE_LATE_XG_MULT, sb.BASE_SAVE_TUNE
sb.TIE_LATE_XG_MULT = 1.0
sb.BASE_SAVE_TUNE = 1.0
check("kill switch: tied late -> 1.0", sb.tie_late_factor(3, 300, 2, 2) == 1.0)
sb.TIE_LATE_XG_MULT, sb.BASE_SAVE_TUNE = _orig_mult, _orig_tune
check("constants restored", sb.tie_late_factor(3, 300, 2, 2) == 0.80)
check("BASE_SAVE_TUNE in (0,1]", 0 < sb.BASE_SAVE_TUNE <= 1.0)
check("TIE_LATE_XG_MULT in (0,1]", 0 < sb.TIE_LATE_XG_MULT <= 1.0)

# --- both engines run end-to-end with the hooks active ---
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator
from simulation import GameSim
from quick_sim import AdvancedGameSim
import random

def _mini_league():
    random.seed(7)
    league = League("Test", "TST")
    gen = PlayerGenerator()
    teams = list(league.teams)[:2]
    for team in teams:
        for _ in range(9):
            team.roster.append(gen.create_player(
                position=random.choice([PlayerPosition.CENTER,
                                        PlayerPosition.LEFT_WING,
                                        PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(6):
            team.roster.append(gen.create_player(position=PlayerPosition.DEFENSE,
                                                team_name=team.team_name))
        for _ in range(2):
            team.roster.append(gen.create_player(position=PlayerPosition.GOALIE,
                                                team_name=team.team_name))
    return teams[0], teams[1]

for eng_name, eng_cls in (("GameSim", GameSim), ("AdvGS", AdvancedGameSim)):
    try:
        ht, at = _mini_league()
        if eng_name == "GameSim":
            g = eng_cls(ht, at)
        else:
            g = eng_cls(ht, at)
        g.run()
        check(f"{eng_name} completes a game with scoring_balance active", True)
    except Exception as e:
        check(f"{eng_name} completes a game with scoring_balance active ({e})", False)

print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
