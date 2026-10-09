#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""D11 QA: paired-sample equivalence proof -- approx_shot_fate (AdvGS)
vs mesh_system.shot_fate (the ONE shared decision).

Feeds IDENTICAL contexts (same shooter, defenders, grade, location,
distance, situation, weights, RNG seed) to both paths and reports:
  - fate agreement % (blocked/missed/on_net)
  - blocker agreement % (same defender credited)
  - mean |dp_block|, mean |dp_miss|
Two modes:
  A. exact mode (unit=None): the approximation resolves exactly --
     must agree ~100% / dp ~ 0 (proves "not a different formula").
  B. cached-unit mode: unit pre-resolved once (the live AdvGS path) --
     must also agree ~100% on identical inputs (proves the caching is
     exact while the unit is unchanged).
Also reports the ENGINE-FIDELITY gap: same shots, GameSim-style
situation vs QS-style situation (neutral sys/dz/pressure/tactics) --
this documents the input gap, not a formula gap.

Usage: python3 qa_d11_parity.py [n]   (exit 0 = all pass)
"""
import sys, random
sys.path.insert(0, '/tmp/wt-retune-d11')
assert 'wt-retune-d11' in __import__('quick_sim').__file__

import mesh_system as M
from quick_sim import approx_shot_fate, approx_block_prob
from game_classes import League, PlayerPosition
from player_generator import PlayerGenerator

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ok   {name}")
    else:
        FAIL += 1; print(f"  FAIL {name} {detail}")

random.seed(31337)
league = League("National Hockey League", "NHL")
gen = PlayerGenerator()
Fw = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]
shooters, dcorps = [], []
for team in league.teams[:4]:
    fw, df = [], []
    for _ in range(14):
        fw.append(gen.create_player(position=random.choice(Fw), team_name=team.team_name))
    for _ in range(8):
        df.append(gen.create_player(position=PlayerPosition.DEFENSE, team_name=team.team_name))
    shooters += fw
    dcorps.append(df)

LOCS = ["crease", "low_slot", "high_slot", "left_circle", "right_circle",
        "point", "left_wing", "right_wing", "behind_net", None]
GRADES = ["A", "B", "C"]

def rand_situation(rng):
    return {
        "sys": rng.choice([1.2, 0.9, 1.0]),
        "dz": rng.choice([1.25, 1.0, 0.85]),
        "pressure": rng.choice([1.3, 0.8, 1.1, 1.0]),
        "tactics": round(rng.uniform(0.9, 1.1), 3),
        "tendency": round(rng.uniform(0.7, 1.4), 3),
        "composite": round(rng.uniform(0.94, 1.06), 3),
        "fatigue": round(rng.uniform(0.9, 1.0), 3),
    }

def rand_weights(defenders, rng):
    return {d: round(rng.uniform(0.5, 1.5), 3) for d in defenders}

agree_fate = agree_blk = 0
agree_fate_c = agree_blk_c = 0
dpb_sum = dpm_sum = 0.0
fidelity_gap = 0
rng = random.Random(777)
for i in range(N):
    shooter = rng.choice(shooters)
    defenders = rng.choice(dcorps)
    grade = rng.choice(GRADES)
    loc = rng.choice(LOCS)
    dist = round(rng.uniform(6, 55), 1)
    sit = rand_situation(rng)
    w = rand_weights(defenders, rng)

    # --- exact path ---
    r1 = random.Random(100000 + i)
    f_exact = M.shot_fate(shooter, defenders, grade=grade, location=loc,
                          distance=dist, situation=sit, weights=w.get, _rng=r1)

    # --- A: approx exact mode (unit=None) ---
    r2 = random.Random(100000 + i)
    f_apx = approx_shot_fate(shooter, defenders, grade=grade, location=loc,
                            distance=dist, situation=sit, weights=w.get,
                            unit=None, _rng=r2)
    agree_fate += (f_exact.fate == f_apx.fate)
    agree_blk += ((f_exact.blocker is None and f_apx.blocker is None)
                  or (f_exact.blocker is not None and f_apx.blocker is not None
                      and f_exact.blocker.id == f_apx.blocker.id))
    dpb_sum += abs(M.shot_block_prob(f_exact.blocker or defenders[0], shooter, loc, sit)
                   - f_apx.p_block) if f_exact.blocker else 0.0
    # miss prob compare on a non-blocked draw
    r3 = random.Random(200000 + i); r4 = random.Random(200000 + i)
    _ = M.shot_miss_prob(shooter, grade, dist)
    dpm_sum += abs(M.shot_miss_prob(shooter, grade, dist) - f_apx.p_miss) \
        if f_apx.fate != "blocked" else 0.0

    # --- B: approx cached-unit mode (the live AdvGS path) ---
    blocker = M.resolve_blocker(defenders, w.get)
    if blocker is not None:
        ubattle = (M.defensive_positioning(blocker) * 0.50
                   + float(getattr(blocker, "shot_blocking", 10)) * 0.50)
        unit = (blocker, ubattle, w.get(blocker, 1.0), sit["composite"])
    else:
        unit = (None, None, 1.0, 1.0)
    r5 = random.Random(100000 + i)
    f_c = approx_shot_fate(shooter, defenders, grade=grade, location=loc,
                           distance=dist, situation=sit, weights=w.get,
                           unit=unit, _rng=r5)
    agree_fate_c += (f_exact.fate == f_c.fate)
    agree_blk_c += ((f_exact.blocker is None and f_c.blocker is None)
                    or (f_exact.blocker is not None and f_c.blocker is not None
                        and f_exact.blocker.id == f_c.blocker.id))

    # --- fidelity gap: same shot, QS-style situation (neutral sys/dz/
    # pressure/tactics) vs GameSim-style situation ---
    qs_sit = {"fatigue": sit["fatigue"]}
    r6 = random.Random(300000 + i); r7 = random.Random(300000 + i)
    f_gs = M.shot_fate(shooter, defenders, grade=grade, location=loc,
                       distance=dist, situation=sit, weights=w.get, _rng=r6)
    f_qs = M.shot_fate(shooter, defenders, grade=grade, location=loc,
                       distance=dist, situation=qs_sit, weights=w.get, _rng=r7)
    fidelity_gap += (f_gs.fate != f_qs.fate)

print(f"\nN={N} paired contexts")
print(f"  A. exact-mode fate agreement:   {100.0*agree_fate/N:.2f}%")
print(f"  A. exact-mode blocker agreement:{100.0*agree_blk/N:.2f}%")
print(f"  B. cached-unit fate agreement:  {100.0*agree_fate_c/N:.2f}%")
print(f"  B. cached-unit blocker agree:   {100.0*agree_blk_c/N:.2f}%")
print(f"  mean |dp_block|: {dpb_sum/N:.6f}   mean |dp_miss|: {dpm_sum/N:.6f}")
print(f"  fidelity gap (GS-sit vs QS-sit fate disagreement): {100.0*fidelity_gap/N:.2f}%")

check("exact-mode fate agreement >= 99.9%", agree_fate / N >= 0.999,
      f"{agree_fate}/{N}")
check("exact-mode blocker agreement >= 99.9%", agree_blk / N >= 0.999)
check("cached-unit fate agreement >= 99.9%", agree_fate_c / N >= 0.999)
check("cached-unit blocker agreement >= 99.9%", agree_blk_c / N >= 0.999)
check("mean |dp_block| < 1e-9", dpb_sum / N < 1e-9, f"{dpb_sum/N}")
check("mean |dp_miss| < 1e-9", dpm_sum / N < 1e-9, f"{dpm_sum/N}")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
