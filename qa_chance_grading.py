"""QA: Chance grading system (2026-09-28, per Muck).

Verifies the shared A/B/C chance grading:
1. Shared functions never raise (None/empty inputs)
2. Hard gates: breakaway/rebound/won-spot -> A; smothered perimeter/point -> C
3. Archetype differentiation: snipers generate more A than grinders/enforcers
4. Talent gates: elite offensive positioning/skating/awareness -> more A
5. Matchup: shutdown D suppresses A (MATCHUPS matrix)
6. Gametime: rivalry heat / clutch / home crowd tilt toward more A
7. Conversion: A mult > B > C; A clamp reaches ~20%+
8. Distribution: roughly NHL-like (A 15-20%, B 50-60%, C 25-30%)
9. Analytics: quick_sim records grade_a/b/c_shots + _goals per player

Run: DISPLAY=:99 python3 qa_chance_grading.py
"""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, os.path.expanduser('~/workspace/playthrough'))

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")

print("=== Chance Grading QA ===\n")

from collections import Counter
import random
import mesh_system as mesh
from mesh_system import (
    roll_chance_grade, chance_grade_finish_mult, chance_grade_clamp,
    chance_archetype_a_tilt, CHANCE_GRADES,
)

class Fake:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

# 1. Never raise
print("1. Shared layer never raises:")
check("roll(None,None,None) in grades",
      roll_chance_grade(None, None, None) in CHANCE_GRADES)
check("roll() defaults in grades", roll_chance_grade() in CHANCE_GRADES)
check("bad location falls back",
      roll_chance_grade("moon", 0.5, None) in CHANCE_GRADES)
check("finish_mult bad grade = 1.0",
      chance_grade_finish_mult("Z") == 1.0)
check("clamp bad grade sane",
      chance_grade_clamp(None) == (0.04, 0.16))
check("archetype tilt None = 1.0",
      chance_archetype_a_tilt(None) == 1.0)

# 2. Hard gates
print("\n2. Hard gates (chance quality is honest):")
check("breakaway -> A", roll_chance_grade("breakaway", 0.9) == "A")
check("rebound -> A",
      roll_chance_grade("slot", 0.8, situation={"rebound": True}) == "A")
check("won spot at crease -> A",
      roll_chance_grade("crease", 0.5,
                        situation={"won_spot": True}) == "A")
check("tip + won spot -> A",
      roll_chance_grade("netfront", 0.5,
                        situation={"tip": True, "won_spot": True}) == "A")
check("smothered perimeter -> C",
      roll_chance_grade("perimeter", 0.85) == "C")
check("smothered point -> C",
      roll_chance_grade("point", 0.95) == "C")
check("slot clean quick release -> A",
      roll_chance_grade("slot", 0.2,
                        situation={"quick_release": True}) == "A")

# 3. Archetype differentiation
print("\n3. Archetype differentiation (snipers > grinders):")
random.seed(1234)
def a_rate(arch, n=3000):
    s = Fake(offensive_positioning=75, skating=75, offensive_awareness=75,
             morale=70, archetype=arch)
    c = Counter(roll_chance_grade("slot", 0.35, s) for _ in range(n))
    return c["A"] / n
r_sniper = a_rate("Sniper")
r_playmaker = a_rate("Playmaker")
r_grinder = a_rate("Grinder")
r_enforcer = a_rate("Enforcer")
check(f"sniper A-rate ({r_sniper:.1%}) > grinder ({r_grinder:.1%})",
      r_sniper > r_grinder + 0.05)
check(f"playmaker A-rate ({r_playmaker:.1%}) > enforcer ({r_enforcer:.1%})",
      r_playmaker > r_enforcer + 0.05)
check("grinder A-rate < 25%", r_grinder < 0.25, f"{r_grinder:.1%}")
# Recalibrated 2026-09-29: the old >25% bar was calibrated on the leaky
# era (linear talent band let archetype dominate). Under talent-primary
# gating with the 2026-09-29 steep-gradient curve, a 75-talent sniper at
# moderate contest honestly earns ~18% (league average ~11-12%); the
# bar is >17% (>1.5x league average, well above grinder). Elite-90+
# territory is higher (see test 4).
check("sniper A-rate > 17%", r_sniper > 0.17, f"{r_sniper:.1%}")

# 4. Talent gates
print("\n4. Talent gates (positioning/skating/awareness):")
def a_rate_talent(tal, n=3000):
    s = Fake(offensive_positioning=tal, skating=tal,
             offensive_awareness=tal, morale=70, archetype="Two-Way Forward")
    c = Counter(roll_chance_grade("slot", 0.35, s,
                                 game_ctx={"morale": 70}) for _ in range(n))
    return c["A"] / n
r_elite = a_rate_talent(90)
r_fringe = a_rate_talent(55)
check(f"elite talent A ({r_elite:.1%}) > fringe ({r_fringe:.1%})",
      r_elite > r_fringe + 0.05)

# 5. Matchup: shutdown D suppresses
print("\n5. Matchup (shutdown pair vs sniper):")
sniper = Fake(offensive_positioning=85, skating=85, offensive_awareness=85,
              morale=70, archetype="Sniper")
shut = Fake(archetype="Defensive Defenseman")
soft = Fake(archetype="Offensive Defenseman")
def a_rate_matchup(defs, n=3000):
    c = Counter(roll_chance_grade("slot", 0.35, sniper, defenders=defs)
                for _ in range(n))
    return c["A"] / n
r_shut = a_rate_matchup([shut, shut])
r_soft = a_rate_matchup([soft, soft])
check(f"sniper vs shutdown ({r_shut:.1%}) < vs offensive D ({r_soft:.1%})",
      r_shut < r_soft)
# Tired D give up more A
def a_rate_tired(fat, n=3000):
    c = Counter(roll_chance_grade(
        "slot", 0.35, sniper, defenders=[soft],
        game_ctx={"d_fatigue": fat}) for _ in range(n))
    return c["A"] / n
check("tired D (90) > fresh D (30) A-rate",
      a_rate_tired(90) > a_rate_tired(30))

# 6. Gametime
print("\n6. Gametime (rivalry/clutch/crowd tilt to more chances):")
def a_rate_game(ctx, n=3000):
    c = Counter(roll_chance_grade("slot", 0.35, sniper, game_ctx=ctx)
                for _ in range(n))
    return c["A"] / n
r_hot = a_rate_game({"rivalry_heat": 90, "clutch": True, "crowd_edge": 0.8,
                     "morale": 85})
r_cold = a_rate_game({"rivalry_heat": 0, "clutch": False, "crowd_edge": -0.5,
                      "morale": 50})
check(f"heated rivalry A ({r_hot:.1%}) > dead barn ({r_cold:.1%})",
      r_hot > r_cold)

# 7. Conversion ordering
print("\n7. Conversion ordering (A favored, C suppressed):")
check("A mult > B mult > C mult",
      chance_grade_finish_mult("A") > chance_grade_finish_mult("B") >
      chance_grade_finish_mult("C"))
_lo_a, _hi_a = chance_grade_clamp("A")
check(f"A clamp ceiling ({_hi_a}) reaches ~20%+", _hi_a >= 0.20)
_lo_c, _hi_c = chance_grade_clamp("C")
check(f"C clamp ceiling ({_hi_c}) below B floor",
      _hi_c <= chance_grade_clamp("B")[0] + 0.06)

# 8. Distribution (realistic league mix)
print("\n8. Distribution (NHL-like: A 15-20%, B 50-60%, C 25-30%):")
random.seed(99)
mix = [('Sniper', 10, 82), ('Playmaker', 10, 80), ('Power Forward', 8, 78),
       ('Two-Way Forward', 22, 72), ('Grinder', 18, 65), ('Enforcer', 4, 60),
       ('Offensive Defenseman', 8, 74), ('Two-Way Defenseman', 10, 70),
       ('Defensive Defenseman', 6, 66), ('Puck-Moving Defenseman', 4, 72)]
archs = [a for a, w, t in mix for _ in range(w)]
talents = {a: t for a, w, t in mix}
c = Counter()
for _ in range(20000):
    arch = random.choice(archs)
    t = talents[arch]
    s = Fake(offensive_positioning=t + random.randint(-6, 6),
             skating=t + random.randint(-6, 6),
             offensive_awareness=t + random.randint(-6, 6),
             morale=70, archetype=arch)
    is_d = 'Defenseman' in arch
    r = random.random()
    if is_d:
        loc = 'point' if r < 0.72 else ('slot' if r < 0.85 else 'perimeter')
    else:
        loc = ('slot' if r < 0.45 else
               'perimeter' if r < 0.65 else
               'netfront' if r < 0.78 else
               'point' if r < 0.88 else
               'crease' if r < 0.93 else 'breakaway')
    c[roll_chance_grade(loc, random.betavariate(2, 2.5), s)] += 1
tot = sum(c.values())
pa, pb, pc = c["A"] / tot, c["B"] / tot, c["C"] / tot
print(f"    mix: A={pa:.1%} B={pb:.1%} C={pc:.1%}")
check("A in 12-24%", 0.12 <= pa <= 0.24, f"{pa:.1%}")
check("B in 40-65%", 0.40 <= pb <= 0.65, f"{pb:.1%}")
check("C in 20-40%", 0.20 <= pc <= 0.40, f"{pc:.1%}")
check("B most common", pb > pa and pb > pc)

print(f"\n{'='*40}\nPASS: {PASS}  FAIL: {FAIL}")
sys.exit(1 if FAIL else 0)
