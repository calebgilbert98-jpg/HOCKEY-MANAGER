# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: rivalry intensity calibration re-check.

Re-verifies the 2026-09-27/28 calibration points for the rivalry engine in
reputation_system.py (formation, escalation, decay, entrenched hatred,
bad-blood transfer, fight/brawl rates, crowd gameplay caps, game_tension,
and save/load round-trip of league.rivalries).

Headless: lightweight fakes only, no UI, no telemetry writes.
Prints PASS/FAIL counts plus a per-point verdict line.
"""
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from types import SimpleNamespace

PASS, FAIL, FAILURES = 0, 0, []
POINTS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


def point(name, ok, detail=""):
    POINTS.append((name, ok, detail))
    check(name, ok, detail)


import reputation_system as rs
from reputation_system import (
    add_rivalry, brawl_probability, decay_rivalries,
    fight_probability, game_tension, game_tension_breakdown,
    get_rivalry_heat, on_player_transfer, record_award_race,
    record_brawl_game, record_game_incident, record_major_injury,
    review_rivalries, rivalry_between, seed_regional_rivalries,
)
from arena_atmosphere import crowd_effects
from game_classes import League, Team


def _mkteam(name, city="City"):
    return Team(name, city, "Atlantic", "Eastern")


def _mkplayer(pid, name):
    return SimpleNamespace(id=pid, full_name=name,
                           primary_position=SimpleNamespace(name="CENTER"))


CGY, EDM = _mkteam("Calgary Flames", "Calgary"), _mkteam("Edmonton Oilers", "Edmonton")
TOR, MTL = _mkteam("Toronto Maple Leafs", "Toronto"), _mkteam("Montreal Canadiens", "Montreal")
# Neutral-chippiness rosters so the tension read is the pure rivalry + pride
# signal (no chippy/clean personnel driver).
for _t in (CGY, EDM, TOR, MTL):
    _t.roster = [SimpleNamespace(base_controversy=35) for _ in range(20)]

# --------------------------------------------------------------------------
# 1. Formation: regional seeding, Battle of Alberta heat
# --------------------------------------------------------------------------
rivs = []
n = seed_regional_rivalries(rivs, [CGY, EDM, TOR, MTL])
boa = rivalry_between(rivs, CGY, EDM, "team_team")
point("formation: Battle of Alberta seeded at 55",
      boa is not None and boa["intensity"] == 55 and boa["grudge"] == 75
      and boa["origin"] == "regional",
      f"seeded={n} boa={boa['intensity'] if boa else None}")

# merge: intensity takes the max, stories accumulate
r2 = add_rivalry(rivs, CGY, EDM, "team_team", 40, "regional", "extra chirps.")
point("formation: add_rivalry merges (max intensity, story grows)",
      boa["intensity"] == 55 and "extra chirps." in boa["story"])

# --------------------------------------------------------------------------
# 2. Regional floor 30: offseason decay cycles
# --------------------------------------------------------------------------
rivs_d = []
seed_regional_rivalries(rivs_d, [CGY, EDM])
boa_d = rivalry_between(rivs_d, CGY, EDM, "team_team")
for _ in range(10):
    decay_rivalries(rivs_d, years=1)
point("decay: regional rivalry never drops below 30",
      boa_d is not None and boa_d["intensity"] >= 30,
      f"after 10 decay years: {boa_d['intensity'] if boa_d else 'REMOVED'}")

# non-regional low heat gets culled by decay
rivs_c = [dict(a=("team", "X"), b=("team", "Y"), a_name="X", b_name="Y",
               kind="team_team", intensity=8, origin="playoff_series",
               story="s", date="2026-01-01", grudge=10, career_cost=0)]
decay_rivalries(rivs_c, years=1)
point("decay: cold non-regional beef is removed",
      len(rivs_c) == 0, f"left={len(rivs_c)}")

# --------------------------------------------------------------------------
# 3. Escalation -> review: severe injury solidifies at 65+
# --------------------------------------------------------------------------
inj, hit = _mkplayer(11, "Star Winger"), _mkplayer(22, "Big Hitter")
rivs_i = []
rec = record_major_injury(rivs_i, inj, hit, season_ending=True)
review_rivalries(rivs_i, years=3)
point("escalation: season-ending injury SOLIDIFIES at >=65",
      rec.get("solidified") is True and rec["intensity"] >= 65,
      f"solidified={rec.get('solidified')} intensity={rec['intensity']}")

# non-season-ending major injury: score 69.25 -> also solidifies
inj2, hit2 = _mkplayer(13, "Second Liner"), _mkplayer(24, "Heavy Hitter")
rivs_i2 = []
rec2 = record_major_injury(rivs_i2, inj2, hit2, season_ending=False)
review_rivalries(rivs_i2, years=3)
point("escalation: non-season-ending major injury also solidifies at >=65",
      rec2.get("solidified") is True and rec2["intensity"] >= 65,
      f"solidified={rec2.get('solidified')} intensity={rec2['intensity']}")

# --------------------------------------------------------------------------
# 4. Personal escalation: "can" solidify -- boundary behavior
# --------------------------------------------------------------------------
# A plain brawl_game record (score ~52) simmers, not solidifies.
c1 = SimpleNamespace(id=301, full_name="Coach A", role="head_coach")
c2 = SimpleNamespace(id=302, full_name="Coach B", role="head_coach")
rivs_b = []
out_b = record_brawl_game(rivs_b, TOR, MTL, c1, c2, aggressor="a", fights=4)
rtt = [r for r in out_b if r["kind"] == "team_team"][0]
review_rivalries(rivs_b, years=3)
plain = (not rtt.get("solidified")) and rtt["intensity"] > 0
# An escalated personal feud (high heat/grudge/cost) DOES solidify at >=65.
rivs_b2 = []
r_hot = add_rivalry(rivs_b2, c1, c2, "coach_coach", 100, "brawl_game",
                    "years of bad blood.", grudge=100, career_cost=30)
review_rivalries(rivs_b2, years=3)
point("escalation: personal feud CAN solidify at >=65 when the weight is there",
      plain and r_hot.get("solidified") is True and r_hot["intensity"] >= 65,
      f"plain_simmers={plain} heated solidified={r_hot.get('solidified')} "
      f"intensity={r_hot['intensity']}")

# --------------------------------------------------------------------------
# 5. Entrenched hatred stays >= 60
# --------------------------------------------------------------------------
rivs_e = []
seed_regional_rivalries(rivs_e, [CGY, EDM])
boa_e = rivalry_between(rivs_e, CGY, EDM, "team_team")
boa_e["solidified"] = True
boa_e["intensity"] = 92
mins = 100
for _ in range(12):
    review_rivalries(rivs_e, years=3)
    mins = min(mins, boa_e["intensity"])
point("entrenched: hatred stays >= 60 across 12 review cycles",
      boa_e["intensity"] >= 60 and mins >= 60,
      f"min_intensity={mins} final={boa_e['intensity']}")

# --------------------------------------------------------------------------
# 6. Battle of Alberta alive at 30 after 12 review cycles
# --------------------------------------------------------------------------
rivs_boa = []
seed_regional_rivalries(rivs_boa, [CGY, EDM])
boa_r = rivalry_between(rivs_boa, CGY, EDM, "team_team")
for _ in range(12):
    review_rivalries(rivs_boa, years=3)
alive = rivalry_between(rivs_boa, CGY, EDM, "team_team")
point("BoA: alive at 30 after 12 review cycles",
      alive is not None and alive["intensity"] == 30,
      f"alive={alive is not None} intensity={alive['intensity'] if alive else None}")

# --------------------------------------------------------------------------
# 7. Fight / brawl rates (NHL-grounded)
# --------------------------------------------------------------------------
point("rates: NHL_FIGHTS_PER_GAME == 0.26",
      rs.NHL_FIGHTS_PER_GAME == 0.26,
      f"got {rs.NHL_FIGHTS_PER_GAME}")
p20 = fight_probability(20.0)
point("rates: fight prob at league-average tension ~0.26",
      0.23 <= p20 <= 0.29, f"p={p20}")
brawls_season = rs.NHL_BRAWLS_PER_GAME * 1312
point("rates: ~1.2 line brawls per 1312-game season",
      1.0 <= brawls_season <= 1.4, f"expected={brawls_season:.2f}")

# Expected fights through the actual postgame count path (Poisson lam =
# fight_probability * 1.15, as in narrative_incidents._roll_incidents).
random.seed(1234)
tot = 0
N = 20000
for _ in range(N):
    lam = max(0.0, p20) * 1.15
    _l = 2.718281828 ** (-lam)
    _k, _p = 0, 1.0
    while _p > _l and _k < 8:
        _k += 1
        _p *= random.random()
    tot += max(0, _k - 1)
avg_fights = tot / N
point("rates: simulated fights/game in [0.20, 0.40] at tension 20",
      0.20 <= avg_fights <= 0.40, f"avg={avg_fights:.3f}")

# --------------------------------------------------------------------------
# 8. Crowd gameplay effects capped ~+/-3%
# --------------------------------------------------------------------------
worst = 0.0
ok = True
for e in range(0, 101, 5):
    for m in range(-100, 101, 5):
        hm, am = crowd_effects(float(e), float(m))
        for v in (hm, am):
            worst = max(worst, abs(v - 1.0))
            if not (0.97 <= v <= 1.03):
                ok = False
point("crowd: finishing multipliers clamped to [0.97, 1.03]",
      ok, f"max|delta|={worst:.4f}")

# --------------------------------------------------------------------------
# 9. game_tension / game_tension_breakdown
# --------------------------------------------------------------------------
rivs_t = []
seed_regional_rivalries(rivs_t, [CGY, EDM])
t_calm = game_tension(CGY, EDM, rivs_t)
bd = game_tension_breakdown(CGY, EDM, rivs_t)
drv = [d for d in bd["drivers"] if d["label"].startswith("Rivalry:")]
point("tension: regional 55 -> rivalry driver 33.0 + pride 8 = 41.0",
      abs(bd["tension"] - 41.0) < 0.01 and drv and drv[0]["points"] == 33.0
      and abs(t_calm - 41.0) < 0.01,
      f"tension={bd['tension']} drivers={len(bd['drivers'])}")
bdp = game_tension_breakdown(CGY, EDM, rivs_t, is_playoff=True, series_game=7)
point("tension: Game 7 adds 15 + 2*7 playoff heat",
      abs(bdp["tension"] - (41.0 + 29.0)) < 0.01, f"tension={bdp['tension']}")
bd0 = game_tension_breakdown(_mkteam("Team X"), _mkteam("Team Y"), [])
point("tension: strangers get the pride baseline, no crash",
      bd0["tension"] >= 0 and any("No recent bad blood" in d["label"]
                                  for d in bd0["drivers"]),
      f"tension={bd0['tension']}")
gh = get_rivalry_heat(rivs_t, CGY, EDM)
point("heat: get_rivalry_heat reads the BoA record",
      gh.get("heat", 0) >= 55 or "55" in str(gh), f"heat={gh}")

# record_game_incident: live-sim incidents land on the team_team record
rr = record_game_incident(rivs_t, CGY, EDM, "brawl", "line brawl in the 3rd")
boa_t = rivalry_between(rivs_t, CGY, EDM, "team_team")
point("incidents: live brawl logged on the feud record",
      rr.get("recorded") and any(i["kind"] == "brawl"
                                 for i in (boa_t.get("incidents") or [])))

# --------------------------------------------------------------------------
# 10. Bad-blood transfer on trades
# --------------------------------------------------------------------------
p_mv = _mkplayer(55, "Moved Star")
hitter_mv = _mkplayer(66, "Old Nemesis")
rivs_tr = []
record_major_injury(rivs_tr, p_mv, hitter_mv, season_ending=True)
p_mv.base_controversy = 60  # award beefs only stick to the type to bristle
record_award_race(rivs_tr, p_mv, _mkplayer(77, "Award Rival"), "Hart")
res_tr = on_player_transfer(rivs_tr, p_mv, from_team=CGY, to_team=EDM)
carried = [r["origin"] for r in res_tr["carried"]]
left = [r["origin"] for r in res_tr["left_behind"]]
point("transfer: personal beef follows the man, ambient stays",
      "major_injury" in carried and "award_race" in left,
      f"carried={carried} left={left}")

# --------------------------------------------------------------------------
# 11. Save/load round-trip of rivalry state
# --------------------------------------------------------------------------
from save_load_system import GameSaveManager as SaveLoadSystem


def _make_gm(league):
    return SimpleNamespace(league=league, league_history=None,
                           narrative_ledger=None)


league = League("NHL")
league.season_year = 2028
league.teams = [CGY, EDM]
lr = []
seed_regional_rivalries(lr, [CGY, EDM])
boa_s = rivalry_between(lr, CGY, EDM, "team_team")
boa_s["solidified"] = True
boa_s["intensity"] = 88
record_game_incident(lr, CGY, EDM, "star_injured", "McOiler hurt McFlame")
boa_s["declared_floor"] = 70
boa_s["user_declared"] = True
league.rivalries = lr

gm = _make_gm(league)
saver = SaveLoadSystem(gm)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "rivalry_test.save")
check("save/load: save succeeds", saver.save_game(path), path)
gm2 = SimpleNamespace(league=None, league_history=None, narrative_ledger=None)
loader = SaveLoadSystem(gm2)
check("save/load: load succeeds", loader.load_game(path), path)
lr2 = gm2.league.rivalries or []
boa2 = rivalry_between(lr2, CGY, EDM, "team_team")
inci = boa2.get("incidents") if boa2 else None
point("save/load: intensity, entrenched flag, incidents, declared floor survive",
      boa2 is not None and boa2["intensity"] == 88
      and boa2.get("solidified") is True
      and isinstance(inci, list) and any(i["kind"] == "star_injured" for i in inci)
      and boa2.get("declared_floor") == 70 and boa2.get("user_declared") is True,
      f"intensity={boa2['intensity'] if boa2 else None} "
      f"incidents={[i.get('kind') for i in (inci or [])]}")

# --------------------------------------------------------------------------
# 12. Postgame path undisturbed (rivalries flow through process_postgame)
# --------------------------------------------------------------------------
import narrative_incidents as ni


def _mkteam2(name):
    t = Team(name, "City", "Atlantic", "Eastern")
    return t


h2, a2 = _mkteam2("Home Club"), _mkteam2("Away Club")
rivs_pg = []
out_pg = ni.process_postgame(None, h2, a2, 4, 2, rivalries=rivs_pg,
                             roll_incidents=True, game_date="2028-03-10")
point("postgame: _roll_incidents path intact inside process_postgame",
      isinstance(out_pg, dict) and {"fights", "brawl", "incidents",
                                   "stories", "moments", "iconic"} <= set(out_pg),
      f"keys={sorted(out_pg)}")

# --------------------------------------------------------------------------
# 13. Responsiveness: tension scan must stay cheap
# --------------------------------------------------------------------------
big = []
for i in range(200):
    big.append({"a": ("team", f"T{i}a"), "b": ("team", f"T{i}b"),
                "a_name": f"T{i}a", "b_name": f"T{i}b",
                "kind": "team_team", "intensity": 50, "origin": "playoff_series",
                "story": "s", "date": "2020-01-01", "grudge": 50,
                "career_cost": 0})
big.append({"a": ("team", "Calgary Flames"), "b": ("team", "Edmonton Oilers"),
            "a_name": "Calgary Flames", "b_name": "Edmonton Oilers",
            "kind": "team_team", "intensity": 88, "origin": "regional",
            "story": "s", "date": "2020-01-01", "grudge": 75,
            "career_cost": 0,
            "incidents": [{"kind": "brawl", "detail": "x",
                           "date": "2026-01-01"}]})
t0 = time.perf_counter()
for _ in range(1000):
    game_tension_breakdown(CGY, EDM, big)
ms = (time.perf_counter() - t0) / 1000 * 1000
point("perf: 201-record tension breakdown < 1ms mean",
      ms < 1.0, f"{ms:.3f} ms/call")

# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
print(f"\n{'POINT':55s} RESULT  DETAIL")
print("-" * 100)
for name, ok, detail in POINTS:
    print(f"{name:55s} {'PASS' if ok else 'FAIL':6s} {detail}")
print("-" * 100)
print(f"qa_rivalry_intensity: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("FAILURES:")
    for f in FAILURES:
        print("  -", f)
sys.exit(1 if FAIL else 0)
