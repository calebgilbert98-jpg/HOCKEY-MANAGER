# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: shutdown-D evaluator -- elite defensive seasons move the ceiling.

Covers:
  1. PlayerStats carries the defensive trail (hits/takeaways/blocked_shots),
     save/load round-trips them.
  2. roll_defensive_game_stats: elite defensive attributes >> average ones;
     never raises; goalies get zeros (callers skip them, helper is safe).
  3. NHL evaluator (Player.update_potential_from_season): a defenseman with
     an elite defensive season + weak scoring breaks out (grade rises); a
     good defensive season shields a low-scoring D from the bust tag; a bad
     defensive season + weak scoring still busts.
  4. Farm evaluator (prospect_development): elite plus/minus rate breaks a D
     out; solid plus/minus shields him; poor plus/minus + no scoring busts.
  5. Wiring: all three sim paths call the shared roll (source check).

Run: python3 qa_shutdown_d_evaluator.py
"""
import random
import sys

sys.path.insert(0, ".")

from game_classes import (Player, PlayerPosition, PlayerStats,
                          roll_defensive_game_stats)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def make_d(age=22, grade="B-", da=88, chk=84, poke=82, seed=1):
    random.seed(seed)
    p = Player(first_name="Shut", last_name=f"Down{seed}", age=age,
               primary_position=PlayerPosition.DEFENSE)
    p.potential_grade = grade
    p.true_potential_grade = grade
    p.defensive_awareness = da
    p.checking = chk
    p.pokecheck = poke
    return p


# --- 1. PlayerStats fields + save/load round-trip ---------------------------
st = PlayerStats()
check("stats: defensive fields default 0",
      st.hits == 0 and st.takeaways == 0 and st.blocked_shots == 0)
st.hits, st.takeaways, st.blocked_shots = 97, 54, 162
import save_load_system as sls
saver = sls.GameSaveManager.__new__(sls.GameSaveManager)
blob = saver._serialize_player_stats(st)
back = saver._restore_player_stats(blob)
check("stats: save/load round-trips defensive fields",
      back.hits == 97 and back.takeaways == 54 and back.blocked_shots == 162,
      f"{back.hits}/{back.takeaways}/{back.blocked_shots}")
# old-save safety: missing keys keep defaults
back2 = saver._restore_player_stats({"goals": 5})
check("stats: old save without new keys keeps defaults",
      back2.hits == 0 and back2.takeaways == 0 and back2.blocked_shots == 0)

# --- 2. roll helper ----------------------------------------------------------
random.seed(7)
elite, avg, plug = make_d(da=92, chk=88, poke=86), make_d(da=55, chk=52, poke=50), make_d(da=35, chk=30, poke=32)
def season_totals(p, games=82, seed=0):
    r = random.Random(seed)
    h = t = b = 0
    for _ in range(games):
        _h, _t, _b = roll_defensive_game_stats(p, rng=r)
        h, t, b = h + _h, t + _t, b + _b
    return h, t, b

eh, et, eb = season_totals(elite, seed=11)
ah, at, ab = season_totals(avg, seed=11)
ph, pt, pb = season_totals(plug, seed=11)
check("roll: elite D far out-produces average D",
      (eb + et) > 1.5 * (ab + at),
      f"elite={eb+et} avg={ab+at}")
check("roll: plug D trails average D", (pb + pt) < (ab + at),
      f"plug={pb+pt} avg={ab+at}")
check("roll: elite D hits 2.0+ def events/game",
      (eb + et) / 82 >= 2.0, f"{(eb+et)/82:.2f}")
check("roll: never raises on junk", roll_defensive_game_stats(object()) == (0, 0, 0))
g = Player(first_name="G", last_name="Goal", age=25,
           primary_position=PlayerPosition.GOALIE)
check("roll: safe on goalie", isinstance(roll_defensive_game_stats(g), tuple))

# --- 3. NHL evaluator --------------------------------------------------------
def run_nhl_eval(p, pts, gp=82, seed=0):
    p.stats = PlayerStats()
    p.stats.games_played = gp
    p.stats.goals = 2
    p.stats.assists = max(0, pts - 2)
    # attribute-driven defensive season, like the sims produce
    r = random.Random(seed)
    for _ in range(gp):
        _h, _t, _b = roll_defensive_game_stats(p, rng=r)
        p.stats.hits += _h
        p.stats.takeaways += _t
        p.stats.blocked_shots += _b
    random.seed(12345)  # pin the 65% stick roll: 0.416 < 0.65 -> sticks
    before = p.potential_grade
    p.update_potential_from_season()
    return before, p.potential_grade

# elite shutdown D, 22yo, B-, 18 points in 82 (0.22 ppg -- bust territory on offense)
d1 = make_d(age=22, grade="B-", da=92, chk=88, poke=86, seed=21)
b1, a1 = run_nhl_eval(d1, pts=18, seed=301)
ladder = Player.POTENTIAL_LADDER
check("nhl: elite defensive season breaks the D out (grade rises)",
      ladder.index(a1) > ladder.index(b1), f"{b1} -> {a1}")

# good (not elite) defensive D, 22yo, B-, 18 points: shielded from bust
d2 = make_d(age=22, grade="B-", da=74, chk=70, poke=68, seed=22)
b2, a2 = run_nhl_eval(d2, pts=18, seed=302)
check("nhl: good defensive season shields low-scoring D from bust",
      ladder.index(a2) >= ladder.index(b2), f"{b2} -> {a2}")

# poor defensive D, 22yo, B-, 18 points: bust still applies
d3 = make_d(age=22, grade="B-", da=42, chk=40, poke=38, seed=23)
b3, a3 = run_nhl_eval(d3, pts=18, seed=303)
check("nhl: poor defense + no scoring still busts",
      ladder.index(a3) < ladder.index(b3), f"{b3} -> {a3}")

# forward untouched: elite offense still breaks out the old way
f1 = make_d(age=22, grade="B-", da=50, chk=50, poke=50, seed=24)
f1.primary_position = PlayerPosition.CENTER
b4, a4 = run_nhl_eval(f1, pts=80, seed=304)  # 0.98 ppg >= 0.85
check("nhl: forward offensive breakout unchanged",
      ladder.index(a4) > ladder.index(b4), f"{b4} -> {a4}")

# --- 4. farm evaluator -------------------------------------------------------
import prospect_development as pd

def run_farm(p, pm_total, gp=60, age=19, seed=0):
    season = {"league": "OHL", "gp": gp, "g": 4, "a": 10,
              "pts": 14, "ppg": round(14 / gp, 3), "plus_minus": pm_total}
    p.farm_season = dict(season)
    p.age = age
    rng = random.Random(seed)
    return pd.evaluate_prospect_season(p, rng)

lad = pd._ladder()
# elite shutdown: +18 in 60 (0.30/gp), weak scoring
p1 = make_d(age=19, grade="B-", da=80, chk=76, poke=74, seed=31)
p1.true_potential_grade = "B-"
r1 = run_farm(p1, 18, seed=401)
check("farm: elite plus/minus breaks the D out",
      lad.index(p1.true_potential_grade) > lad.index("B-"),
      f"B- -> {p1.true_potential_grade} ({r1})")

# solid shutdown: +9 in 60 (0.15/gp), weak scoring -> shielded
p2 = make_d(age=19, grade="B-", da=68, chk=64, poke=62, seed=32)
p2.true_potential_grade = "B-"
r2 = run_farm(p2, 9, seed=402)
check("farm: solid plus/minus shields low-scoring D",
      lad.index(p2.true_potential_grade) >= lad.index("B-"),
      f"B- -> {p2.true_potential_grade} ({r2})")

# poor: -8 in 60, weak scoring -> bust still applies
p3 = make_d(age=19, grade="B-", da=45, chk=42, poke=40, seed=33)
p3.true_potential_grade = "B-"
r3 = run_farm(p3, -8, seed=403)
check("farm: poor plus/minus + no scoring still busts",
      lad.index(p3.true_potential_grade) < lad.index("B-"),
      f"B- -> {p3.true_potential_grade} ({r3})")

# --- 5. wiring: all sim paths call the shared roll ---------------------------
main_src = open("main.py").read()
sim_src = open("simulation.py").read()
check("wiring: lightweight batch sim calls the shared roll",
      main_src.count("roll_defensive_game_stats") >= 2,
      f"count={main_src.count('roll_defensive_game_stats')}")
check("wiring: GameSim game-end calls the shared roll",
      "roll_defensive_game_stats" in sim_src)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
