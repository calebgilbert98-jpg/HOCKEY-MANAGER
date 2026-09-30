"""QA: prospect accolades + light reputation (prospect_accolades.py).

Covers:
  1. Reputation seeding is a pure function of PERCEIVED grade (no truth leak).
  2. Draft-class preseason stories: sane counts, real award keys, well-formed
     year labels, idempotent banking.
  3. Season rollover: exactly-one semantics (1 Memorial Cup, 1 Hobey, ...),
     rep cap respected, truth untouched, idempotent.
  4. Performance: generation + rollover passes stay well under budget.
  5. Trophy-case ordering: junior awards display below pro awards.

Run: python3 qa_prospect_accolades.py
"""
import random
import re
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, ".")

import accolades as acc
import prospect_accolades as pa

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


def make_player(pid, age=18, pos="C", nat="Canada", league="OHL",
                ppg=1.0, gp=60, grade="B", true="B", rep_missing=True):
    p = SimpleNamespace(
        id=pid, age=age, full_name=f"Test Player {pid}",
        primary_position=SimpleNamespace(value=pos),
        nationality=nat, potential_grade=grade,
        true_potential_grade=true, generational=False,
        junior_league=league,
        farm_season={"league": league, "gp": gp, "g": 20, "a": 25,
                     "pts": 45, "ppg": ppg},
        prior_nhl_gp=[0], stats=SimpleNamespace(games_played=0),
    )
    if not rep_missing:
        p.reputation = 10
    return p


def make_goalie(pid, age=19, league="OHL", sv=0.910, gaa=2.60):
    p = make_player(pid, age=age, pos="G", league=league)
    p.farm_season = {"league": league, "gp": 40, "w": 22, "l": 18,
                     "sv_pct": sv, "gaa": gaa}
    return p


# ---------------------------------------------------------------- 1. seeding
random.seed(7)
p1 = make_player(1, grade="A", true="C")     # perceived A, true C
p2 = make_player(2, grade="A", true="A+")    # perceived A, true A+
r1, r2 = pa.seed_prospect_reputation(p1), pa.seed_prospect_reputation(p2)
check("rep is pure function of perceived grade (no truth leak)", r1 == r2 == 21,
      f"{r1} vs {r2}")

p3 = make_player(3, grade="D", true="A+")
r3 = pa.seed_prospect_reputation(p3)
check("hidden gem gets no hype from truth", r3 == 2, f"rep={r3}")

p4 = make_player(4, grade="B", true="B")
p4.generational = True
check("generational flag caps at 30", pa.seed_prospect_reputation(p4) == 30)

check("rep cap respected at seed", all(
    0 < pa.seed_prospect_reputation(make_player(100 + i, grade=g)) <= 30
    for i, g in enumerate(["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"])))


# ------------------------------------------------- 2. draft-class stories
random.seed(1234)
import draft_generator as dg
cls = dg.generate_draft_class(num_prospects=224, quality="Normal", draft_year=2026)
check("class generated", len(cls) == 224, f"n={len(cls)}")
storied = [p for p in cls if acc.accolade_count(p) > 0]
check("some prospects have junior stories", 5 < len(storied) < 90,
      f"storied={len(storied)}")

cup_re = re.compile(r"^\d{4}-\d{2}$")
yr_re = re.compile(r"^\d{4}$")
bad_keys, bad_years, dupes = [], [], 0
for p in storied:
    seen = set()
    for e in p.career_accolades:
        k, y = e.get("award"), str(e.get("year"))
        if k not in acc.ACCOLADE_LABELS:
            bad_keys.append(k)
        # Championship keys (the module's own _CUP_KEYS) take season labels
        # like 2025-26; award trophies with "cup" in the name (RDS Cup is
        # the QMJHL rookie award) take calendar years like real awards.
        want_cup = k in pa._CUP_KEYS
        if want_cup and not cup_re.match(y):
            bad_years.append((k, y))
        if not want_cup and not yr_re.match(y):
            bad_years.append((k, y))
        if (k, y) in seen:
            dupes += 1
        seen.add((k, y))
check("all story keys are real awards", not bad_keys, str(bad_keys[:3]))
check("year labels well-formed", not bad_years, str(bad_years[:3]))
check("no duplicate accolades", dupes == 0, f"dupes={dupes}")
check("all class prospects repped 1..30",
      all(0 < int(getattr(p, "reputation", 0) or 0) <= 30 for p in cls))
# idempotent: same seed twice adds nothing (bank_accolade dedupes)
cls2 = dg.generate_draft_class(num_prospects=224, quality="Normal", draft_year=2026)
pa.seed_draft_class(cls2, 2026, rng=random.Random(999))
before = sum(acc.accolade_count(p) for p in cls2)
pa.seed_draft_class(cls2, 2026, rng=random.Random(999))
after = sum(acc.accolade_count(p) for p in cls2)
check("re-seeding adds no duplicates", before == after, f"{before}->{after}")


# ------------------------------------------------- 3. rollover awards
def fake_league(players):
    return SimpleNamespace(teams=[], get_all_players=lambda: players)


rng = random.Random(42)
prospects = []
pid = 1
for lg in ("OHL", "WHL", "QMJHL"):
    for i in range(10):
        prospects.append(make_player(pid, age=18 + (i % 3), league=lg,
                                     ppg=0.6 + i * 0.12,
                                     nat=["Canada", "USA", "Sweden"][i % 3],
                                     grade="B"))
        pid += 1
    prospects.append(make_goalie(pid, league=lg, sv=0.905 + pid * 0.0004))
    pid += 1
for i in range(8):
    prospects.append(make_player(pid, age=20, league="NCAA", ppg=0.8 + i * 0.1,
                                 nat="USA", grade="B"))
    pid += 1
prospects.append(make_goalie(pid, age=21, league="NCAA", sv=0.920))
pid += 1
for i in range(5):
    prospects.append(make_player(pid, age=18, league="USHL", ppg=0.7 + i * 0.1,
                                 nat="USA", grade="C"))
    pid += 1
# WJC-eligible youngsters across leagues
for i in range(6):
    prospects.append(make_player(pid, age=18, league="OHL", ppg=1.6,
                                 nat=["Canada", "Sweden", "Finland",
                                      "USA", "Czechia", "Slovakia"][i],
                                 grade="A"))
    pid += 1

truth_before = {p.id: p.true_potential_grade for p in prospects}
news = pa.roll_prospect_awards(fake_league(prospects), "2025-26", "2026",
                               rng=random.Random(42))

def count(key):
    return sum(1 for p in prospects
               for e in (getattr(p, "career_accolades", None) or [])
               if e.get("award") == key)

check("exactly one Memorial Cup group (<=3 winners, >=1)",
      1 <= count("memorial_cup") <= 3, f"n={count('memorial_cup')}")
check("exactly one Stafford Smythe", count("stafford_smythe") == 1,
      f"n={count('stafford_smythe')}")
check("exactly one Hobey Baker", count("hobey_baker") == 1,
      f"n={count('hobey_baker')}")
check("exactly one Mike Richter", count("mike_richter") == 1,
      f"n={count('mike_richter')}")
check("one league MVP per CHL league",
      all(count(k) == 1 for k in ("red_tilson", "four_broncos", "michel_briere")))
check("CHL Player of the Year awarded", count("chl_player_of_year") == 1)
check("WJC medals: 3/3/3",
      count("wjc_gold") == 3 and count("wjc_silver") == 3
      and count("wjc_bronze") == 3,
      f"g={count('wjc_gold')} s={count('wjc_silver')} b={count('wjc_bronze')}")
check("Clark Cup awarded", 1 <= count("clark_cup") <= 2)
check("reputation never exceeds prospect cap",
      all(int(getattr(p, "reputation", 0) or 0) <= pa.PROSPECT_REP_CAP
          for p in prospects))
check("award winners got hype bumps",
      any(int(getattr(p, "reputation", 0) or 0) > 2 for p in prospects
          if acc.accolade_count(p) > 0))
check("hidden truth untouched by awards",
      all(p.true_potential_grade == truth_before[p.id] for p in prospects))
check("news lines are short strings", all(isinstance(m, str) for m in news)
      and len(news) <= 14, f"lines={len(news)}")
check("news mentions Memorial Cup", any("Memorial Cup" in m for m in news))

# idempotent: second roll adds nothing
before2 = sum(acc.accolade_count(p) for p in prospects)
news2 = pa.roll_prospect_awards(fake_league(prospects), "2025-26", "2026",
                                rng=random.Random(42))
after2 = sum(acc.accolade_count(p) for p in prospects)
check("re-roll is idempotent", before2 == after2, f"{before2}->{after2}")

# empty / degenerate leagues don't crash
check("empty league safe",
      pa.roll_prospect_awards(fake_league([]), "2025-26", "2026") == [])
tiny = [make_player(900, league="OHL", ppg=1.0)]
check("tiny pool (<3) awards nothing",
      pa.roll_prospect_awards(fake_league(tiny), "2025-26", "2026",
                              rng=random.Random(1)) == []
      and acc.accolade_count(tiny[0]) == 0)
ahl = [make_player(901, league="AHL", ppg=1.2)]
ahl[0].farm_season = {"league": "AHL", "gp": 70, "g": 20, "a": 30,
                      "pts": 50, "ppg": 0.7}
check("AHLers excluded from junior awards",
      acc.accolade_count(ahl[0]) == 0 or
      not any(e.get("award") in pa._CHL_AWARDS.get("OHL", {}).values()
              or e.get("award") == "memorial_cup"
              for e in (ahl[0].career_accolades or [])))


# ------------------------------------------------- 4. performance
t0 = time.time()
dg.generate_draft_class(num_prospects=224, quality="Normal", draft_year=2027)
gen_s = time.time() - t0
big = [make_player(2000 + i, league=["OHL", "WHL", "QMJHL", "NCAA", "USHL"][i % 5],
                   ppg=0.5 + (i % 20) * 0.05) for i in range(600)]
t0 = time.time()
pa.roll_prospect_awards(fake_league(big), "2026-27", "2027",
                        rng=random.Random(5))
roll_s = time.time() - t0
check("generation pass fast", gen_s < 5.0, f"{gen_s:.2f}s")
check("600-prospect rollover fast", roll_s < 1.0, f"{roll_s:.2f}s")


# ------------------------------------------------- 5. trophy-case order
p = make_player(999)
acc.bank_accolade(p, "stanley_cup", "2025-26")
acc.bank_accolade(p, "memorial_cup", "2023-24")
acc.bank_accolade(p, "hobey_baker", "2024")
order = [lbl for lbl, _ in acc.group_accolades(p)]
check("junior awards display below pro awards",
      order.index("Memorial Cup") > order.index("Stanley Cup")
      and order.index("Hobey Baker Award") > order.index("Stanley Cup"),
      str(order))

def _pm_player(pid, pm, ppg=1.0):
    p = make_player(pid, league="OHL", ppg=ppg, gp=60)
    p.farm_season["plus_minus"] = pm
    return p


# ------------------------------------------------- 6. awards reflect performance
# Every factor the prospect system tracks moves award scores; no number
# is decorative. Deception may only come from sample size, scout
# ability, and judgment -- never from numbers detached from play.
import prospect_development as pd

nhle = pa._nhle_map()

# 6a. Sample-size gate: a 5-game wonder can't win MVP or scoring title.
wonder = make_player(3001, league="OHL", ppg=3.0, gp=5)
wonder.farm_season["pts"] = 90  # rigged totals still shouldn't count
grinder = make_player(3002, league="OHL", ppg=1.1, gp=60)
grinder.farm_season["pts"] = 66
check("5-gp wonder disqualified from MVP",
      pa._skater_impact(wonder, nhle) == -99.0)
check("grinder beats wonder for MVP",
      pa._best([wonder, grinder], lambda p: pa._skater_impact(p, nhle), 1)[0]
      is grinder)
check("grinder beats wonder for scoring title",
      pa._best(pa._qualified_skaters([wonder, grinder]),
               pa._scoring_pts, 1)[0] is grinder)

# 6b. Form: a breakout season beats identical production without one.
hot = make_player(3003, league="OHL", ppg=1.2, gp=60)
hot.farm_result = "breakout"
cold = make_player(3004, league="OHL", ppg=1.2, gp=60)
check("breakout form wins MVP tiebreak",
      pa._skater_impact(hot, nhle) > pa._skater_impact(cold, nhle))
bust = make_player(3005, league="OHL", ppg=1.2, gp=60)
bust.farm_result = "bust"
check("bust tag costs MVP ground",
      pa._skater_impact(bust, nhle) < pa._skater_impact(cold, nhle))

# 6c. Age curve: teenage dominance beats overager stat-padding.
kid = make_player(3006, age=17, league="OHL", ppg=1.20, gp=60)
vet = make_player(3007, age=20, league="OHL", ppg=1.24, gp=60)
check("17yo at 1.20 beats 20yo at 1.24",
      pa._skater_impact(kid, nhle) > pa._skater_impact(vet, nhle))

# 6d. Goalie wins matter alongside sv%.
g1 = make_goalie(3008, sv=0.915, gaa=2.50)
g1.farm_season.update(gp=40, w=30, l=10)
g2 = make_goalie(3009, sv=0.915, gaa=2.50)
g2.farm_season.update(gp=40, w=15, l=25)
check("30-win goalie beats 15-win goalie at equal sv%",
      pa._goalie_impact(g1) > pa._goalie_impact(g2))
g3 = make_goalie(3011)
g3.farm_season.update(gp=8)
check("goalie under 12 gp disqualified",
      pa._goalie_impact(make_goalie(3010)) != -99.0
      and pa._goalie_impact(g3) == -99.0)

# 6e. Track record: voters remember past seasons.
known = make_player(3012, league="OHL", ppg=1.2, gp=60)
known.farm_history = [{"league": "OHL", "gp": 60, "ppg": 1.3},
                      {"league": "OHL", "gp": 62, "ppg": 1.2}]
newbie = make_player(3013, league="OHL", ppg=1.2, gp=60)
check("strong track record wins MVP tiebreak",
      pa._skater_impact(known, nhle) > pa._skater_impact(newbie, nhle))

# 6f. Hype is a whisper, never the decision.
hyped = make_player(3014, league="OHL", ppg=0.9, gp=60)
hyped.draft_hype = 100
hyped.generational = True
quiet = make_player(3015, league="OHL", ppg=1.1, gp=60)
quiet.draft_hype = 0
check("max hype can't overcome a real production gap",
      pa._skater_impact(hyped, nhle) < pa._skater_impact(quiet, nhle))

# 6g. The offseason persists the season's story for awards to read.
rp = dg.create_prospect(age=18, draft_year=2027)
pd.process_prospect_offseason(rp, rng=random.Random(11))
check("process_prospect_offseason persists farm_result",
      getattr(rp, "farm_result", "MISSING") != "MISSING")

# 6h. Draft-year story sim leaves the player untouched.
sp = dg.create_prospect(age=18, draft_year=2027)
snap = (getattr(sp, "farm_league", ""), getattr(sp, "farm_season", None),
        list(getattr(sp, "farm_history", None) or []))
pa._temp_draft_year_score(sp, "OHL", nhle, random.Random(3))
after = (getattr(sp, "farm_league", ""), getattr(sp, "farm_season", None),
         list(getattr(sp, "farm_history", None) or []))
check("story sim has zero persistent side effects", snap == after,
      f"{snap} vs {after}")

# 6i. Stories go to the top performers, not the most hyped.
fakes = []
for i in range(25):
    f = make_player(4000 + i, grade="D", league="OHL")  # low hype for all
    f.junior_league = "OHL"
    fakes.append(f)
preset = {f.id: float(25 - (f.id - 4000)) for f in fakes}  # id order = rank
_orig = pa._temp_draft_year_score
pa._temp_draft_year_score = lambda p, lg, n, r: preset[p.id]
try:
    pa.seed_draft_class(fakes, 2027, rng=random.Random(0))
finally:
    pa._temp_draft_year_score = _orig
storied_ids = [f.id for f in fakes if acc.accolade_count(f) > 0]
top8 = {f.id for f in fakes[:8]}
check("stories follow performance (top-8 by simmed season)",
      len(storied_ids) >= 1 and all(i in top8 for i in storied_ids),
      f"storied={storied_ids}")

# 6j. No decorative numbers: the sim emits a defensive record, and it is
# honest -- shutdown defenders go positive, one-dimensional scorers bleed.
shut = dg.create_prospect(age=18, draft_year=2027)
shut.defensive_awareness = shut.checking = shut.pokecheck = 92
oneway = dg.create_prospect(age=18, draft_year=2027)
oneway.defensive_awareness = oneway.checking = oneway.pokecheck = 35
s_s = pd.simulate_prospect_season(shut, league="OHL",
                                  rng=random.Random(21))
s_o = pd.simulate_prospect_season(oneway, league="OHL",
                                  rng=random.Random(21))
check("sim emits plus_minus",
      "plus_minus" in s_s and "plus_minus" in s_o)
check("shutdown defender goes positive", s_s["plus_minus"] > 5,
      f"pm={s_s['plus_minus']}")
check("one-dimensional scorer bleeds", s_o["plus_minus"] < -5,
      f"pm={s_o['plus_minus']}")

# 6k. Awards read the simulated defensive record, not raw attributes.
d_shut = make_player(3020, pos="D", league="OHL", ppg=0.6, gp=60)
d_shut.farm_season["plus_minus"] = 25
d_off = make_player(3021, pos="D", league="OHL", ppg=1.3, gp=60)
d_off.farm_season["plus_minus"] = -15
check("shutdown performer wins best-defenceman",
      pa._defence_impact(d_shut, nhle) > pa._defence_impact(d_off, nhle))
check("offensive D still wins MVP",
      pa._skater_impact(d_off, nhle) > pa._skater_impact(d_shut, nhle))
check("plus_minus is two-way: +20 beats -15 at equal scoring",
      pa._skater_impact(_pm_player(3022, 20), nhle) >
      pa._skater_impact(_pm_player(3023, -15), nhle))

# 6l. Old saves without plus_minus stay neutral, never crash.
legacy = make_player(3024, league="OHL", ppg=1.0, gp=60)
legacy.farm_season.pop("plus_minus", None)
try:
    v = pa._skater_impact(legacy, nhle)
    d = pa._defence_impact(legacy, nhle)
    ok_legacy = v > -50 and d > -50
except Exception:
    ok_legacy = False
check("missing plus_minus degrades gracefully", ok_legacy)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
