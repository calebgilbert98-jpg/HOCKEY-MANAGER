#!/usr/bin/env python3
"""QA: generational 85+ / elite 80+ thresholds with busts preserved (Muck 2026-10-02).

Covers:
 1. A+ (generational) at 23+: 85+ overall + 85+ signature composites at generation.
 2. A+ prospect (<23): NO generation floor -- must earn it; bust possible.
 3. NHL_ELITE tier: 80+ signature composites at generation (any age).
 4. Best-case development (env 1.6): A+ -> 85+ sig; A -> 80+ sig.
 5. Bust-case development (env 0.6): thresholds can be missed (busts preserved).
 6. Archetype-awareness: Defensive Defenseman gets defensive_play, not finishing.
 7. Never raises on edge cases.
"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from player_generator import PlayerGenerator
from game_classes import PlayerPosition
from attribute_composites import raw_composite
from player_archetypes import (
    get_archetype, signature_composites, ARCHETYPE_SIGNATURE_COMPOSITES,
)

PASS, FAIL = [], []

def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

POSITIONS = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
             PlayerPosition.RIGHT_WING, PlayerPosition.LEFT_DEFENSE,
             PlayerPosition.RIGHT_DEFENSE, PlayerPosition.GOALIE]

# --- 1. A+ established (23+): 85+ overall + signatures ---------------------
print("== 1. A+ at 23+: generation floors apply ==")
random.seed(11)
gen = PlayerGenerator()
gen.get_random_potential = lambda: 'A+'
ok_ovr = ok_sig = 0
n = 30
for i in range(n):
    p = gen.create_player('NHL_STARTER', 'PRIME', random.choice(POSITIONS))
    p.true_potential_grade = 'A+'
    p.potential_grade = 'A+'
    # NOTE: create_player ran with random potential; force re-check by
    # re-running floors is not possible post-hoc, so we generate with A+
    # forced (above) and age PRIME (24-30, all >= 23).
    if p.overall_rating() >= 85:
        ok_ovr += 1
    sigs = [raw_composite(p, s) for s in signature_composites(p)]
    if all(v >= 85 for v in sigs):
        ok_sig += 1
check(f"A+ 23+ overall 85+ ({ok_ovr}/{n})", ok_ovr == n)
check(f"A+ 23+ signatures 85+ ({ok_sig}/{n})", ok_sig == n)

# --- 2. A+ prospect (<23): NO generation floor -----------------------------
print("== 2. A+ prospect (<23): no generation floor (bust possible) ==")
random.seed(12)
gen2 = PlayerGenerator()
gen2.get_random_potential = lambda: 'A+'
prospects = [gen2.create_player('JUNIOR_ELITE', 'ROOKIE', random.choice(POSITIONS))
             for _ in range(30)]
below = sum(1 for p in prospects if p.overall_rating() < 85)
check(f"A+ prospects start below 85 ({below}/30 can bust)", below > 0)
check("all prospects are < 23", all(p.age < 23 for p in prospects))

# --- 3. NHL_ELITE: 80+ signatures ------------------------------------------
print("== 3. NHL_ELITE generation: 80+ signatures ==")
random.seed(13)
gen3 = PlayerGenerator()
gen3.get_random_potential = lambda: 'B'  # non-generational
ok = 0
n = 40
for i in range(n):
    p = gen3.create_player('NHL_ELITE', 'PRIME', random.choice(POSITIONS))
    sigs = [raw_composite(p, s) for s in signature_composites(p)]
    if all(v >= 80 for v in sigs):
        ok += 1
check(f"NHL_ELITE 80+ signatures ({ok}/{n})", ok == n)

# --- 4. Best-case development ------------------------------------------------
print("== 4. Best-case development (env 1.6) hits thresholds ==")
random.seed(14)
gen4 = PlayerGenerator()
gen4.get_random_potential = lambda: 'A+'
p = gen4.create_player('JUNIOR_ELITE', 'ROOKIE', PlayerPosition.CENTER)
p.true_potential_grade = 'A+'
p.potential_grade = 'A+'
for _ in range(18, 26):
    p.age_one_year(env_factor=1.6)
sigs = [raw_composite(p, s) for s in signature_composites(p)]
check(f"A+ best-case signatures 85+ ({[round(v,1) for v in sigs]})",
      all(v >= 85 for v in sigs))

random.seed(15)
gen5 = PlayerGenerator()
gen5.get_random_potential = lambda: 'A'
p = gen5.create_player('JUNIOR_ELITE', 'ROOKIE', PlayerPosition.LEFT_WING)
p.true_potential_grade = 'A'
p.potential_grade = 'A'
for _ in range(18, 27):
    p.age_one_year(env_factor=1.6)
sigs = [raw_composite(p, s) for s in signature_composites(p)]
check(f"A best-case signatures 80+ ({[round(v,1) for v in sigs]})",
      all(v >= 80 for v in sigs))

# --- 5. Bust-case development ------------------------------------------------
print("== 5. Bust-case development (env 0.6): thresholds can be missed ==")
random.seed(16)
gen6 = PlayerGenerator()
gen6.get_random_potential = lambda: 'A+'
p = gen6.create_player('JUNIOR_ELITE', 'ROOKIE', PlayerPosition.CENTER)
p.true_potential_grade = 'A+'
p.potential_grade = 'A+'
for _ in range(18, 26):
    p.age_one_year(env_factor=0.6)
sigs = [raw_composite(p, s) for s in signature_composites(p)]
check(f"A+ bust-case CAN miss 85 ({[round(v,1) for v in sigs]})",
      any(v < 85 for v in sigs))

random.seed(17)
gen7 = PlayerGenerator()
gen7.get_random_potential = lambda: 'A'
p = gen7.create_player('JUNIOR_ELITE', 'ROOKIE', PlayerPosition.LEFT_WING)
p.true_potential_grade = 'A'
p.potential_grade = 'A'
for _ in range(18, 27):
    p.age_one_year(env_factor=0.6)
sigs = [raw_composite(p, s) for s in signature_composites(p)]
check(f"A bust-case CAN miss 80 ({[round(v,1) for v in sigs]})",
      any(v < 80 for v in sigs))

# --- 6. Archetype-awareness ---------------------------------------------------
print("== 6. Archetype-awareness ==")
check("Sniper -> finishing", ARCHETYPE_SIGNATURE_COMPOSITES["Sniper"] == ["finishing"])
check("Playmaker -> chance_creation",
      ARCHETYPE_SIGNATURE_COMPOSITES["Playmaker"] == ["chance_creation"])
check("Defensive Defenseman -> defensive_play (no finishing)",
      ARCHETYPE_SIGNATURE_COMPOSITES["Defensive Defenseman"] == ["defensive_play"])
check("Shutdown D archetype map has no finishing",
      "finishing" not in ARCHETYPE_SIGNATURE_COMPOSITES["Defensive Defenseman"])
check("Goalies -> goalie_save",
      all(ARCHETYPE_SIGNATURE_COMPOSITES[a] == ["goalie_save"]
          for a in ["Butterfly Goalie", "Hybrid Goalie", "Athletic Goalie",
                    "Puck-Handling Goalie", "Backup Goalie"]))

# A shutdown D at NHL_ELITE gets defensive_play 80+, NOT finishing 80+
random.seed(18)
gen8 = PlayerGenerator()
gen8.get_random_potential = lambda: 'B'
found = False
for _ in range(200):
    p = gen8.create_player('NHL_ELITE', 'PRIME', PlayerPosition.LEFT_DEFENSE)
    if get_archetype(p) == "Defensive Defenseman":
        found = True
        dp = raw_composite(p, "defensive_play")
        fin = raw_composite(p, "finishing")
        check(f"Elite shutdown D: defensive_play 80+ ({dp:.1f})", dp >= 80)
        # finishing NOT floored by archetype system (positional forward floor
        # doesn't apply to D either)
        print(f"    (finishing {fin:.1f} -- not archetype-floored)")
        break
if not found:
    FAIL.append("no Defensive Defenseman generated in 200 tries")
    print("  [FAIL] no Defensive Defenseman generated in 200 tries")

# --- 7. Never raises -----------------------------------------------------------
print("== 7. Never raises ==")
try:
    from attribute_composites import bump_composite_to_floor
    class Fake: pass
    f = Fake()
    r1 = bump_composite_to_floor(f, "finishing", 80)
    r2 = bump_composite_to_floor(f, "bogus_key", 80)
    from player_archetypes import signature_composites as sc
    r3 = sc(f)
    check("bump/composite helpers never raise on junk", True)
except Exception as e:
    check(f"helpers never raise (got {e})", False)

# age_one_year with edge-case env_factors never raises (real player)
try:
    random.seed(21)
    gen9 = PlayerGenerator()
    gen9.get_random_potential = lambda: 'A+'
    p = gen9.create_player('JUNIOR_ELITE', 'ROOKIE', PlayerPosition.CENTER)
    p.true_potential_grade = 'A+'
    p.potential_grade = 'A+'
    for _env in (None, "bad", -1.0, 99.0, 1.6):
        p.age_one_year(env_factor=_env)
    check("age_one_year never raises on edge-case env_factors", True)
except Exception as e:
    check(f"age_one_year never raises (got {type(e).__name__}: {e})", False)

print()
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
