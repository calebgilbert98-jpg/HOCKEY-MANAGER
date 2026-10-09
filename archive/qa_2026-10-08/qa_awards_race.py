# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: awards races + rookie leaders."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as g
from game_classes import PlayerPosition
import awards_race as ar

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")

class FakeTeam:
    def __init__(self, name, pts=60, gp=50, ga=140):
        self.team_name = name
        self.points = pts
        self.games_played = gp
        self.goals_against = ga
        self.roster = []
        self.coach = type("C", (), {"full_name": f"Coach {name}"})()

def skater(first, goals, assists, gp=50, pos=PlayerPosition.CENTER,
           rookie=False, pim=10, pm=5, da=60, fo=50, tk=20, team="Team A"):
    p = g.Player(first, "Test", 24, pos, 85)
    p.goals = goals; p.assists = assists; p.games_played = gp
    p.penalty_minutes = pim; p.plus_minus = pm
    p.defensive_awareness = da; p.faceoffs = fo; p.takeaways = tk
    p.is_rookie = rookie; p.team_name = team
    p.shots = max(goals * 8, 10)
    # Keep birth_date consistent with age (the game generator does this;
    # the raw constructor randomizes it). Calder age checks read birth_date.
    p.birth_date = "2002-06-01"
    p.prior_nhl_gp = []
    return p

def goalie(first, wins, sv, gaa, gp=30, rookie=False, team="Team A"):
    p = g.Player(first, "Goalie", 26, PlayerPosition.GOALIE, 88)
    p.birth_date = "2000-06-01"
    p.prior_nhl_gp = []
    p.wins = wins; p.games_played = gp; p.shutouts = 3
    sa = 900
    p.shots_against = sa; p.saves = int(sa * sv)
    p.minutes_played = int(gp * 58)
    # adjust saves to hit target gaa approx
    ga = gaa * p.minutes_played / 60
    p.saves = int(sa - ga)
    p.is_rookie = rookie; p.team_name = team
    return p

# --- Hart: points dominate, team success matters ---
elite = skater("Elite", 40, 60, team="Good Team")      # 100 pts
mid = skater("Mid", 35, 55, team="Bad Team")            # 90 pts
team_pct = {"Good Team": 0.650, "Bad Team": 0.400}
hart = ar.hart_race([elite, mid], team_pct)
check("hart ranks elite first", hart[0]["player"] is elite)
# Bad-team scorer gets discounted vs equal good-team scorer
equal_bad = skater("EqualBad", 40, 60, team="Bad Team")
hart2 = ar.hart_race([elite, equal_bad], team_pct)
check("hart prefers winner on good team",
      hart2[0]["player"] is elite)

# --- Art Ross / Rocket: pure ---
ross = ar.art_ross_race([mid, elite])
check("art ross is pure points", ross[0]["player"] is elite)
sniper = skater("Sniper", 55, 20)
rocket = ar.rocket_race([elite, sniper])
check("rocket is pure goals", rocket[0]["player"] is sniper)

# --- Norris: D points dominate ---
d_off = skater("OffD", 20, 60, pos=PlayerPosition.DEFENSE, da=55)
d_def = skater("DefD", 5, 20, pos=PlayerPosition.DEFENSE, da=95, pm=25)
norris = ar.norris_race([d_off, d_def, elite])
check("norris only defensemen", all(
    ar._is_defenseman(r["player"]) for r in norris))
check("norris favors offensive D", norris[0]["player"] is d_off)

# --- Selke: defensive forwards ---
two_way = skater("TwoWay", 25, 35, da=92, fo=58, tk=65, pm=22)
selke = ar.selke_race([two_way, elite])
check("selke favors defensive forward", selke[0]["player"] is two_way)
check("selke excludes D", all(not ar._is_defenseman(r["player"])
                          for r in selke))

# --- Byng: points with low PIM ---
clean = skater("Clean", 30, 50, pim=8)
dirty = skater("Dirty", 32, 52, pim=90)
byng = ar.byng_race([clean, dirty])
check("byng favors low PIM", byng[0]["player"] is clean)

# --- Calder: rookies only, points ---
rk1 = skater("Rk1", 22, 30, rookie=True)
rk2 = skater("Rk2", 15, 20, rookie=True)
vet = skater("Vet", 40, 60, rookie=False)
vet.prior_nhl_gp = [70, 65]  # established veteran: real prior NHL games
calder = ar.calder_race([rk1, rk2, vet])
check("calder rookies only",
      all(r["player"].is_rookie for r in calder))
check("calder ranks by points", calder[0]["player"] is rk1)

# --- Vezina: SV% + GAA + wins ---
g1 = goalie("Elite", 28, 0.925, 2.20)
g2 = goalie("Avg", 25, 0.905, 2.80)
vez = ar.vezina_race([g1, g2])
check("vezina favors elite goalie", vez[0]["player"] is g1)
check("vezina reports gsax", "gsax" in vez[0])

# --- Jennings: fewest team GA ---
t1 = FakeTeam("Stingy", ga=120)
t1.roster = [goalie("G1", 25, 0.915, 2.40, gp=40, team="Stingy")]
t2 = FakeTeam("Leaky", ga=180)
t2.roster = [goalie("G2", 25, 0.905, 2.90, gp=40, team="Leaky")]
jen = ar.jennings_race([t1, t2])
check("jennings fewest GA first", jen[0]["team"] == "Stingy")

# --- Adams: overachievement ---
# Weak roster (75 OVR) winning a lot should beat strong roster (88) winning
weak = FakeTeam("Overachievers", pts=70, gp=50)
for i in range(10):
    p = skater(f"W{i}", 10, 10)
    p.overall = 74
    p.team_name = "Overachievers"
    weak.roster.append(p)
strong = FakeTeam("Underachievers", pts=62, gp=50)
for i in range(10):
    p = skater(f"S{i}", 10, 10)
    p.overall = 89
    p.team_name = "Underachievers"
    strong.roster.append(p)
adams = ar.adams_race([weak, strong])
check("adams favors overachiever", adams[0]["team"] == "Overachievers")

# --- Rookie leaders ---
rl = ar.rookie_skaters([rk1, rk2, vet])
check("rookie skaters exclude vets", all(r["player"].is_rookie for r in rl))
check("rookie skaters sorted", rl[0]["points"] >= rl[1]["points"])
rg1 = goalie("RkG", 12, 0.915, 2.50, gp=20, rookie=True)
g1.prior_nhl_gp = [55]  # established veteran netminder
rg = ar.rookie_goalies([rg1, g1])
check("rookie goalies only rookies", len(rg) == 1 and rg[0]["player"] is rg1)

# --- Award definitions complete ---
check("11 awards defined", len(ar.AWARD_DEFINITIONS) == 11)
keys = {k for _n, _d, k in ar.AWARD_DEFINITIONS}
check("all award keys have race functions",
      keys <= {"hart", "ted_lindsay", "art_ross", "rocket", "norris", "vezina",
               "calder", "selke", "byng", "adams", "jennings"})

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
