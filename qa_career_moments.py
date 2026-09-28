"""QA: per-player career game log ("Signature Games").

Covers: moment detection thresholds (hat trick / 4+ pts / shutout /
40 saves / steal), one-moment-per-game dedup, 20-entry cap with
significance pruning, playoff bump, GameSim + AdvGS stat shapes,
never-raises on junk input, and save/load round-trip. Headless.
"""
import sys
from types import SimpleNamespace
from datetime import date

sys.path.insert(0, ".")

import narrative_incidents as ni

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def mk_player(name, pos="CENTER", pid=1):
    pos_ns = SimpleNamespace(name=pos)
    return SimpleNamespace(id=pid, full_name=name, first_name=name.split()[0],
                           last_name=name.split()[-1], primary_position=pos_ns,
                           career_moments=[], team_name="")


def mk_home_away(players_home, players_away):
    home = SimpleNamespace(team_name="Bruins", roster=players_home,
                           ahl_roster=[], prospects=[])
    away = SimpleNamespace(team_name="Sabres", roster=players_away,
                           ahl_roster=[], prospects=[])
    return home, away


def advgs_sim(home, away, lines_home, lines_away):
    """lines: {pid: (goals, assists, saves)}"""
    return SimpleNamespace(stats={
        "Bruins": {pid: {"goals": g, "assists": a, "saves": s, "player": None}
                   for pid, (g, a, s) in lines_home.items()},
        "Sabres": {pid: {"goals": g, "assists": a, "saves": s, "player": None}
                   for pid, (g, a, s) in lines_away.items()},
    })


print("== thresholds ==")
sk = mk_player("A Star", pid=10)
gl = mk_player("B Goalie", pos="GOALIE", pid=20)
home, away = mk_home_away([sk, gl], [])
sim = advgs_sim(home, away, {10: (3, 1, 0), 20: (0, 0, 34)}, {})
n = ni.log_player_moments(sim, home, away, 5, 0,
                          game_date=date(2026, 11, 4))
check("hat trick + shutout logged", n == 2, f"got {n}")
check("skater kind", sk.career_moments[0]["kind"] == "hat_trick",
      sk.career_moments)
check("skater detail", "3 G, 1 A" in sk.career_moments[0]["detail"],
      sk.career_moments[0])
check("goalie kind", gl.career_moments[0]["kind"] == "shutout")
check("date stamped", sk.career_moments[0]["date"] == "2026-11-04")

print("== point nights ==")
p4 = mk_player("C Play", pid=11)
home, away = mk_home_away([p4], [])
sim = advgs_sim(home, away, {11: (1, 3, 0)}, {})
ni.log_player_moments(sim, home, away, 6, 2, game_date=date(2026, 11, 5))
check("4-point night", p4.career_moments[0]["kind"] == "four_point")
p5 = mk_player("D Play", pid=12)
home, away = mk_home_away([p5], [])
sim = advgs_sim(home, away, {12: (2, 3, 0)}, {})
ni.log_player_moments(sim, home, away, 7, 2, game_date=date(2026, 11, 6))
check("5-point night outranks hat trick path",
      p5.career_moments[0]["kind"] == "five_point")
check("one moment per player per game", len(p5.career_moments) == 1)

print("== goalie saves ==")
g40 = mk_player("E Wall", pos="GOALIE", pid=21)
home, away = mk_home_away([], [g40])
sim = advgs_sim(home, away, {}, {21: (0, 0, 42)})
ni.log_player_moments(sim, home, away, 4, 3, game_date=date(2026, 11, 7))
check("42-save win (non-shutout)", g40.career_moments[0]["kind"] == "forty_saves",
      g40.career_moments)
g35 = mk_player("F Steal", pos="GOALIE", pid=22)
home, away = mk_home_away([], [g35])
sim = advgs_sim(home, away, {}, {22: (0, 0, 37)})
ni.log_player_moments(sim, home, away, 2, 3, game_date=date(2026, 11, 8))
check("37-save win = steal", g35.career_moments[0]["kind"] == "steal")
g37l = mk_player("G Loss", pos="GOALIE", pid=23)
home, away = mk_home_away([], [g37l])
sim = advgs_sim(home, away, {}, {23: (0, 0, 37)})
ni.log_player_moments(sim, home, away, 4, 3, game_date=date(2026, 11, 9))
check("37-save loss = nothing", len(g37l.career_moments) == 0,
      g37l.career_moments)
quiet = mk_player("H Quiet", pid=13)
home, away = mk_home_away([quiet], [])
sim = advgs_sim(home, away, {13: (1, 1, 0)}, {})
ni.log_player_moments(sim, home, away, 3, 2, game_date=date(2026, 11, 10))
check("2-point night = nothing (no overload)",
      len(quiet.career_moments) == 0)

print("== dedup / cap / pruning ==")
dup = mk_player("I Dup", pid=14)
home, away = mk_home_away([dup], [])
sim = advgs_sim(home, away, {14: (3, 0, 0)}, {})
ni.log_player_moments(sim, home, away, 4, 1, game_date=date(2026, 11, 11))
ni.log_player_moments(sim, home, away, 4, 1, game_date=date(2026, 11, 11))
check("same game+kind not double-logged", len(dup.career_moments) == 1)
many = mk_player("J Many", pid=15)
home, away = mk_home_away([many], [])
for i in range(25):
    sim = advgs_sim(home, away, {15: (3, 0, 0)}, {})
    ni.log_player_moments(sim, home, away, 4, 1,
                          game_date=date(2026, 10, 1 + i % 28))
check("capped at 20", len(many.career_moments) == 20,
      len(many.career_moments))
# A playoff hat trick should survive pruning over regular-season ones.
po = mk_player("K Playoff", pid=16)
home, away = mk_home_away([po], [])
for i in range(20):
    sim = advgs_sim(home, away, {16: (3, 0, 0)}, {})
    ni.log_player_moments(sim, home, away, 4, 1,
                          game_date=date(2026, 3, 1 + i % 28))
sim = advgs_sim(home, away, {16: (3, 0, 0)}, {})
ni.log_player_moments(sim, home, away, 4, 1, game_date=date(2026, 4, 20),
                      is_playoff=True)
kinds = [m["kind"] for m in po.career_moments]
check("playoff moment kept after prune",
      any(m.get("playoff") for m in po.career_moments) and
      len(po.career_moments) == 20,
      f"{len(po.career_moments)}")

print("== GameSim shape ==")
gs = mk_player("L Live", pid=30)
home, away = mk_home_away([gs], [])
gsim = SimpleNamespace(game_stats={30: {"g": 3, "a": 0, "player": gs}})
n = ni.log_player_moments(gsim, home, away, 5, 2,
                          game_date=date(2026, 11, 20))
check("GameSim hat trick detected",
      n == 1 and gs.career_moments[0]["kind"] == "hat_trick")

print("== never raises ==")
try:
    ni.log_player_moments(None, None, None, 0, 0)
    ni.log_player_moments(SimpleNamespace(), SimpleNamespace(),
                          SimpleNamespace(), 1, 2)
    ni.process_postgame(None, None, None, 0, 0)
    check("junk input safe", True)
except Exception as e:
    check("junk input safe", False, str(e))

print("== save round-trip ==")
try:
    from game_classes import Player, PlayerPosition
    from save_load_system import GameSaveManager
    p = Player("Test", "Kid", 21, PlayerPosition.CENTER)
    p.career_moments = [{"date": "2026-11-04", "kind": "hat_trick",
                         "label": "Hat trick",
                         "detail": "3 G vs Sabres (5-1 W)",
                         "opp": "Sabres", "score": "5-1 W",
                         "playoff": False, "sig": 40}]
    mgr = GameSaveManager.__new__(GameSaveManager)
    data = mgr._serialize_player(p)
    back = mgr._restore_player(data)
    check("moments survive save/load",
          getattr(back, "career_moments", None) == p.career_moments,
          getattr(back, "career_moments", None))
except Exception as e:
    check("moments survive save/load", False, str(e))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
