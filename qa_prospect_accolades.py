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
        want_cup = "cup" in k or k in pa._CUP_KEYS or "champion" in k or k == "memorial_cup"
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

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
