# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: parity engine -- cross-game form, coach/player corrective forces,
target-on-back, trap games, engine hooks. Headless.
Run: python3 qa_parity.py"""
import sys
from types import SimpleNamespace
sys.path.insert(0, '.')

import parity_engine as pe

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ok   {name}")
    else: FAIL += 1; print(f"  FAIL {name}")

def close(a, b, tol=1e-9):
    return abs(a - b) <= tol

def stub_team(name, coach=None, leaders=0):
    roster = [SimpleNamespace(leadership=90) for _ in range(leaders)]
    roster += [SimpleNamespace(leadership=50) for _ in range(18 - leaders)]
    return SimpleNamespace(team_name=name, roster=roster, head_coach=coach)

def stub_coach(motivating=50, man_management=50, discipline=50):
    return SimpleNamespace(id="c1", motivating=motivating,
                           man_management=man_management, discipline=discipline)

pe.DISABLED = False
pe.new_season()

# --- form updates ---
A = stub_team("AAA"); B = stub_team("BBB")
pe.record_result(A, B, True)
check("win +8 form", close(pe._state(A)["form"], 8.0))
check("loss -8 form", close(pe._state(B)["form"], -8.0))
check("winner streak +1", pe._state(A)["streak"] == 1)
check("loser streak -1", pe._state(B)["streak"] == -1)
check("winner winless 0", pe._state(A)["winless"] == 0)
check("loser winless 1", pe._state(B)["winless"] == 1)

# OTL: point salvaged, loss-streak snaps, winless continues
pe.record_result(A, B, True, went_ot=True)
st = pe._state(B)
check("OTL +1 form", close(st["form"], -8.0 * 0.96 + 1.0))
check("OTL snaps loss streak", st["streak"] == 0)
check("OTL keeps winless", st["winless"] == 2)

# streak extension bonus: 3rd straight win adds +2
pe.new_season()
C = stub_team("CCC"); D = stub_team("DDD")
pe.record_result(C, D, True); pe.record_result(C, D, True)
pe.record_result(C, D, True)
check("3rd straight win form bonus",
      close(pe._state(C)["form"], (8.0 + 8.0 * 0.96) * 0.96 + 10.0,
            tol=1e-6))

# per-game decay toward zero
pe.new_season()
E = stub_team("EEE"); F = stub_team("FFF")
pe.record_result(E, F, True)   # +8
pe.record_result(E, F, False)  # loss: 8*.96 - 8
check("form decays across games",
      close(pe._state(E)["form"], 8.0 * 0.96 - 8.0))

# caps
pe.new_season()
G = stub_team("GGG"); H = stub_team("HHH")
for _ in range(30):
    pe.record_result(G, H, True)
check("form capped at +100", pe._state(G)["form"] <= 100.0)
check("form floored at -100", pe._state(H)["form"] >= -100.0)

# --- pregame multiplier: pure form ---
pe.new_season()
T1 = stub_team("T1"); T2 = stub_team("T2")
pe._state(T1)["form"] = 100.0
check("form +100 -> 1.04", close(pe.pregame_multiplier(T1, T2), 1.04))
pe._state(T1)["form"] = -100.0
check("form -100 -> 0.96", close(pe.pregame_multiplier(T1, T2), 0.96))

# --- coach adjustment on a skid; better coach -> bigger adjustment ---
def skid_result(coach):
    pe.new_season()
    sk = stub_team("SK", coach=coach); op = stub_team("OP")
    for _ in range(8):
        pe.record_result(op, sk, True)
    return pe.pregame_multiplier(sk, op)

m_good = skid_result(stub_coach(motivating=90, man_management=90))
m_bad = skid_result(stub_coach(motivating=10, man_management=10))
check("good coach adjusts better than bad coach", m_good > m_bad)
# exact: form after 8 straight losses, adj with q=0.9, plus new-coach
# bounce (first pregame call detects the hire)
pe.new_season()
SK = stub_team("SK", coach=stub_coach(motivating=90, man_management=90))
OP = stub_team("OP")
for _ in range(8):
    pe.record_result(OP, SK, True)
st = pe._state(SK)
check("8-game skid counted", st["winless"] == 8)
form_fx = 1 + st["form"] / 100 * 0.04
adj = 1 + 8 * 0.008 * (0.6 + 0.8 * 0.9)
check("skid math exact",
      close(pe.pregame_multiplier(SK, OP), form_fx * adj * 1.05, tol=1e-9))

# --- new-coach bounce ---
pe.new_season()
NC = stub_team("NC", coach=stub_coach()); NO = stub_team("NO")
m1 = pe.pregame_multiplier(NC, NO)   # first call detects the hire
check("new-coach bounce +5%", close(m1, 1.05))
pe.record_result(NC, NO, True)
m2 = pe.pregame_multiplier(NC, NO)
check("bounce decay math", close(m2, 1.0032 * 1.045, tol=1e-9))
check("bounce decays", m2 < m1)
# no re-trigger without an actual change
pe.record_result(NC, NO, True)
m4 = pe.pregame_multiplier(NC, NO)
st = pe._state(NC)
check("no re-trigger without a change",
      close(m4, (1 + st["form"] / 100 * 0.04)
            * (1 + 0.05 * st["new_coach_games"] / 10), tol=1e-9))
# a real change re-triggers
NC.head_coach = stub_coach(motivating=60, man_management=60)
NC.head_coach.id = "c2"
m5 = pe.pregame_multiplier(NC, NO)
st = pe._state(NC)
check("coaching change re-triggers bounce", st["new_coach_games"] == 10)
check("re-trigger math",
      close(m5, (1 + st["form"] / 100 * 0.04) * 1.05, tol=1e-9))

# --- player pride: veteran leaders on a skid ---
pe.new_season()
PR = stub_team("PRIDE", leaders=4); PO = stub_team("PO2")
for _ in range(6):
    pe.record_result(PO, PR, True)
st = pe._state(PR)
m = pe.pregame_multiplier(PR, PO)
form_fx = 1 + st["form"] / 100 * 0.04
adj = 1 + 6 * 0.008 * (0.6 + 0.8 * 0.5)   # no coach -> q=0.5
pride = 1 + 4 * 0.005 * 6 / 6.0
check("veteran pride math", close(m, form_fx * adj * pride, tol=1e-9))
pe.new_season()
PR0 = stub_team("PRIDE0", leaders=0)
for _ in range(6):
    pe.record_result(PO, PR0, True)
check("no leaders -> no pride",
      pe.pregame_multiplier(PR0, PO) < m)

# --- target on your back / trap games (mature table) ---
pe.new_season()
tops = [stub_team(f"TOP{i}") for i in range(8)]
mids = [stub_team(f"MID{i}") for i in range(2)]
bots = [stub_team(f"BOT{i}") for i in range(8)]
for _ in range(20):
    for i, t in enumerate(tops):
        pe.record_result(t, bots[i % 8], True)
for _ in range(10):
    for i, md in enumerate(mids):
        pe.record_result(md, bots[(i + 3) % 8], True)
        pe.record_result(tops[i], md, True)
check("top5 tier", pe._tier("TOP0") == "top5")
check("mid tier", pe._tier("MID0") == "mid")
check("bottom8 tier", pe._tier("BOT0") == "bottom8")
mt = pe.pregame_multiplier(mids[0], tops[0])
check("target on your back +2%",
      close(mt, 1.02 * (1 + pe._state(mids[0])["form"] / 100 * 0.04),
            tol=1e-9))
tt = pe.pregame_multiplier(tops[0], bots[0])
check("trap-game flatness -1.5%",
      close(tt, 0.985 * (1 + pe._state(tops[0])["form"] / 100 * 0.04),
            tol=1e-9))
# disciplined coach suppresses complacency
pe.new_season()
DT = stub_team("DT", coach=stub_coach(discipline=85))
DB = stub_team("DB")
pe.pregame_multiplier(DT, DB)  # trigger coach detection (bounce starts)
for _ in range(20):
    pe.record_result(DT, DB, True)  # bounce fully decays over 20 games
m = pe.pregame_multiplier(DT, DB)
check("demanding coach kills trap flatness",
      close(m, 1 + pe._state(DT)["form"] / 100 * 0.04, tol=1e-9))
# playoffs: table psychology off
mp = pe.pregame_multiplier(mids[0], tops[0], playoffs=True)
check("no target-on-back in playoffs",
      close(mp, 1 + pe._state(mids[0])["form"] / 100 * 0.04, tol=1e-9))
# young table: no tiers yet
pe.new_season()
YT = stub_team("YT"); YO = stub_team("YO")
pe.record_result(YT, YO, True)
check("young table -> no tier", pe._tier("YT") is None)
check("young table -> pure form",
      close(pe.pregame_multiplier(YT, YO),
            1 + pe._state(YT)["form"] / 100 * 0.04, tol=1e-9))

# --- safety ---
pe.new_season()
check("never raises on junk", pe.pregame_multiplier(None, None) == 1.0)
try:
    pe.record_result(None, None, True); check("record junk ok", True)
except Exception:
    check("record junk ok", False)
check("form_state never raises", isinstance(pe.form_state(None), dict))
pe.DISABLED = True
check("kill switch -> 1.0", pe.pregame_multiplier(T1, T2) == 1.0)
pe.DISABLED = False
pe.new_season()
X = stub_team("X"); Y = stub_team("Y")
pe._state(X)["form"] = -100.0
pe._state(X)["winless"] = 8
check("multiplier clamped", 0.90 <= pe.pregame_multiplier(X, Y) <= 1.12)

# --- engine smoke: both engines apply + record ---
pe.new_season()
import random
random.seed(7)
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator
from quick_sim import AdvancedGameSim
league = League("National Hockey League", "NHL")
gen = PlayerGenerator()
for team in league.teams[:2]:
    if not team.roster:
        for _ in range(14):
            team.roster.append(gen.create_player(
                position=random.choice([PlayerPosition.CENTER,
                                        PlayerPosition.LEFT_WING,
                                        PlayerPosition.RIGHT_WING]),
                team_name=team.team_name))
        for _ in range(8):
            team.roster.append(gen.create_player(
                position=PlayerPosition.DEFENSE, team_name=team.team_name))
        for _ in range(3):
            team.roster.append(gen.create_player(
                position=PlayerPosition.GOALIE, team_name=team.team_name))
EH, EA = league.teams[0], league.teams[1]
asim = AdvancedGameSim(EH, EA)
check("AdvGS parity edge installed",
      set(asim._parity_matchup.keys()) == {"home", "away"})
check("AdvGS parity edge sane",
      all(0.90 <= v <= 1.12 for v in asim._parity_matchup.values()))
w, l, scores, ev, ne = asim.run()
check("AdvGS records form post-game",
      abs(pe._state(EH)["form"]) > 0 and abs(pe._state(EA)["form"]) > 0)
check("AdvGS season table grows", pe.season_table()[EH.team_name]["gp"] == 1)

from simulation import GameSim
gsim = GameSim(EH, EA)
check("GameSim parity cache starts empty", gsim._parity_mult is None)
w2, l2, scores2, log2, ne2 = gsim.run()
check("GameSim populates parity cache", gsim._parity_mult is not None)
check("GameSim records form post-game",
      pe.season_table()[EH.team_name]["gp"] == 2)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)