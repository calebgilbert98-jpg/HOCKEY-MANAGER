"""QA: new-CBA AHL recall gate (paper-transaction rule).

A player assigned to the AHL must play at least one AHL game before he
can be recalled. Covers: helper semantics, the sim increment, save
round-trip + old-save grandfathering, and wiring probes at every
demotion/recall chokepoint (SP, MP; AI has no callup path).
"""
import random
import sys
import types

sys.path.insert(0, ".")

import ahl_system
from game_classes import Player, PlayerPosition

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


def fresh_skater(seed=11):
    random.seed(seed)
    return Player("Test", "Winger", 24, PlayerPosition.LEFT_WING)


def fresh_goalie(seed=12):
    random.seed(seed)
    return Player("Test", "Goalie", 26, PlayerPosition.GOALIE)


# 1. Grandfathered: fresh player (None) -> recall legal.
p = fresh_skater()
check("fresh player counter is None", p.ahl_games_since_assignment is None)
check("grandfathered recall allowed",
      ahl_system.ahl_recall_block_reason(p) is None)

# 2. Stamp -> 0 -> blocked with a legible reason.
ahl_system.stamp_ahl_assignment(p)
check("stamp sets counter to 0", p.ahl_games_since_assignment == 0)
reason = ahl_system.ahl_recall_block_reason(p)
check("freshly assigned recall blocked", reason is not None)
check("block reason cites the one-game rule",
      reason is not None and "one AHL game" in reason, repr(reason))

# 3. One appearance -> allowed.
ahl_system.note_ahl_appearance(p)
check("appearance increments to 1", p.ahl_games_since_assignment == 1)
check("recall allowed after one game",
      ahl_system.ahl_recall_block_reason(p) is None)

# 4. Re-assignment re-stamps to 0.
ahl_system.stamp_ahl_assignment(p)
check("re-stamp resets to 0", p.ahl_games_since_assignment == 0)
check("blocked again after re-assignment",
      ahl_system.ahl_recall_block_reason(p) is not None)

# 5. Grandfathered players are untouched by appearances.
g = fresh_skater(seed=21)
ahl_system.note_ahl_appearance(g)
check("note_ahl_appearance leaves None alone",
      g.ahl_games_since_assignment is None)

# 6. Goalie class carries the field too.
gl = fresh_goalie()
check("goalie has the field (None default)",
      getattr(gl, "ahl_games_since_assignment", "missing") is None)
ahl_system.stamp_ahl_assignment(gl)
check("goalie stamp blocks recall",
      ahl_system.ahl_recall_block_reason(gl) is not None)

# 7. simulate_ahl_day: a dressed stamped skater counts a game.
p2 = fresh_skater(seed=31)
ahl_system.stamp_ahl_assignment(p2)
fake_team = types.SimpleNamespace(ahl_roster=[p2])
fake_league = types.SimpleNamespace(teams=[fake_team])
old_prob = ahl_system.GAME_PROBABILITY
ahl_system.GAME_PROBABILITY = 1.0  # everyone dresses, deterministic
try:
    ahl_system.simulate_ahl_day(fake_league)
finally:
    ahl_system.GAME_PROBABILITY = old_prob
check("simmed AHL day increments stamped skater",
      p2.ahl_games_since_assignment == 1,
      f"got {p2.ahl_games_since_assignment}")
check("simmed game clears the gate",
      ahl_system.ahl_recall_block_reason(p2) is None)

# 8. Save round-trip: counter persists; missing key -> None (old save).
try:
    from save_load_system import GameSaveManager
    mgr = GameSaveManager(None)
    p3 = fresh_skater(seed=41)
    ahl_system.stamp_ahl_assignment(p3)
    ahl_system.note_ahl_appearance(p3)
    ahl_system.note_ahl_appearance(p3)  # counter == 2
    data = mgr._serialize_player(p3)
    check("counter serialized",
          data.get("ahl_games_since_assignment") == 2, repr(data.get("ahl_games_since_assignment")))
    back = mgr._restore_player(dict(data))
    check("counter restored",
          getattr(back, "ahl_games_since_assignment", None) == 2)
    check("restored player recall legal",
          ahl_system.ahl_recall_block_reason(back) is None)
    # Old save: no key at all.
    old_data = {k: v for k, v in data.items() if k != "ahl_games_since_assignment"}
    old_back = mgr._restore_player(old_data)
    check("old save restores to None (grandfathered)",
          getattr(old_back, "ahl_games_since_assignment", "missing") is None)
    check("old-save player recall legal",
          ahl_system.ahl_recall_block_reason(old_back) is None)
except Exception as e:  # pragma: no cover
    check("save round-trip (skipped: %s)" % e, False)

# 9. Wiring probes: every chokepoint references the shared helpers.
import os as _os
_here = _os.path.dirname(_os.path.abspath(__file__))
src_main = open(_os.path.join(_here, "main.py")).read()
src_win = open(_os.path.join(_here, "windows.py")).read()
src_ahl = open(_os.path.join(_here, "ahl_system.py")).read()
check("call_up_to_nhl gated",
      "ahl_recall_block_reason" in src_main and "def call_up_to_nhl" in src_main)
check("_mp_call_up gated",
      src_main.count("ahl_recall_block_reason") >= 2)
check("send_to_ahl stamps",
      "stamp_ahl_assignment" in src_main)
check("process_waivers clearing stamps",
      src_main.count("stamp_ahl_assignment") >= 2)
check("roster-move screen gates AHL->NHL",
      "ahl_recall_block_reason" in src_win)
check("roster-move screen stamps NHL->AHL",
      "stamp_ahl_assignment" in src_win)
check("simulate_ahl_day counts appearances",
      "note_ahl_appearance" in src_ahl)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
