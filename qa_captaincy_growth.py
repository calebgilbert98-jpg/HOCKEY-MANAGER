"""QA: captaincy forges leaders (tenure + results + impact -> leadership).

Covers the Toews/Crosby arc mechanics in captaincy_growth.py:
- young captain + Cup + impact rockets (capped per season)
- tenure reinforcement in any situation (even a bad one)
- tenure AMPLIFIES situation growth (5yr C + Cup > 1st-yr C + Cup)
- bad situation -> only the flat reinforcement
- alternates get roughly half
- no letter -> no growth, tenure resets; losing the C resets C tenure
- diminishing returns near 100; hard cap at 100
- season-stamp idempotency (re-runs no-op)
- Cup-winning captain banks +4 extra reputation; others don't
- elite-leader milestone story fires once for a young letter-wearer

Headless. QA seed rule: pin random.seed() BEFORE generation.
"""
import random
import sys
import os

random.seed(20260929)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import captaincy_growth as cg

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


class StubStats:
    def __init__(self, points=60, games=82):
        self.points = points
        self.games_played = games


class StubPlayer:
    def __init__(self, name, age=24, leadership=70, letter="C",
                 determination=70, teamwork=70):
        self.full_name = name
        self.age = age
        self.leadership = leadership
        self.captaincy = letter
        self.determination = determination
        self.teamwork = teamwork
        self.stats = StubStats()
        self.game_stars = {"first": 4, "second": 6, "third": 8}  # 9.0 weighted
        self.reputation = 60
        self.reputation_history = []


def carry_of(p):
    return float(getattr(p, "_leadership_carry", 0.0) or 0.0)


def grow(p, year=2027, win_pct=0.65, rounds=4, champ=True, avg=0.8):
    return cg.apply_captaincy_growth(
        p, season_year=year, win_pct=win_pct, playoff_rounds_won=rounds,
        is_champ=champ, league_avg_ppg=avg)


# --- 1. The Toews arc: 21yo C, Cup, big year -> big (capped) jump
toews = StubPlayer("Young Captain", age=21, leadership=70, letter="C")
toews.stats = StubStats(points=110, games=82)  # elite scoring
r = grow(toews)
check("young Cup-winning C jumps 3-4 leadership",
      3 <= r["leadership_delta"] <= 4)
check("tenure starts at 1", r["tenure"] == 1
      and toews.captain_tenure_years == 1)

# --- 2. Tenure reinforcement in a bad situation (no playoffs, losing team).
# Small enough to bank fractionally year one, landing as +1 in year two.
grinder = StubPlayer("Grinder C", age=28, leadership=72, letter="C")
grinder.stats = StubStats(points=40, games=82)
grinder.game_stars = {"first": 0, "second": 1, "third": 2}
r2 = cg.apply_captaincy_growth(grinder, season_year=2027, win_pct=0.42,
                               playoff_rounds_won=0, is_champ=False,
                               league_avg_ppg=0.8)
check("bad-situation C banks tenure reinforcement (carry)",
      carry_of(grinder) > 0.4)
r2b = cg.apply_captaincy_growth(grinder, season_year=2028, win_pct=0.42,
                                playoff_rounds_won=0, is_champ=False,
                                league_avg_ppg=0.8)
check("tenure reinforcement compounds to +1 by year two",
      grinder.leadership == 73)
check("tenure advances in bad years too",
      grinder.captain_tenure_years == 2)

# --- 3. Tenure amplifies situation: 5yr C + deep run > 1st-yr C + deep run
# (a Cup maxes both at the season cap, so use a conference-final run)
vet = StubPlayer("Vet C", age=29, leadership=80, letter="C")
vet.captain_tenure_years = 4  # about to become 5
vet.stats = StubStats(points=85, games=82)
rook = StubPlayer("New C", age=29, leadership=80, letter="C")
rook.stats = StubStats(points=85, games=82)
rv = cg.apply_captaincy_growth(vet, season_year=2028, win_pct=0.58,
                               playoff_rounds_won=2, is_champ=False,
                               league_avg_ppg=0.8)
rr = cg.apply_captaincy_growth(rook, season_year=2028, win_pct=0.58,
                               playoff_rounds_won=2, is_champ=False,
                               league_avg_ppg=0.8)
check("5th-year C outgrows 1st-year C (tenure amplification, carry-aware)",
      (rv["leadership_delta"] + carry_of(vet))
      > (rr["leadership_delta"] + carry_of(rook)))
check("vet tenure is 5", vet.captain_tenure_years == 5)

# --- 4. Lottery-team C: situation contributes ~nothing
lotto = StubPlayer("Lotto C", age=26, leadership=70, letter="C")
lotto.stats = StubStats(points=55, games=82)
lotto.game_stars = {"first": 1, "second": 2, "third": 2}
rl = cg.apply_captaincy_growth(lotto, season_year=2027, win_pct=0.35,
                                playoff_rounds_won=0, is_champ=False,
                                league_avg_ppg=0.8)
check("lottery C grows only ~tenure reinforcement",
      rl["leadership_delta"] <= 2)

# --- 5. Alternates get roughly half the captain's growth (moderate season
# so neither hits the cap)
cap = StubPlayer("Cap", age=27, leadership=75, letter="C")
alt = StubPlayer("Alt", age=27, leadership=75, letter="A")
cap.stats = alt.stats = StubStats(points=80, games=82)
rc = cg.apply_captaincy_growth(cap, season_year=2029, win_pct=0.58,
                               playoff_rounds_won=2, is_champ=False,
                               league_avg_ppg=0.8)
ra = cg.apply_captaincy_growth(alt, season_year=2029, win_pct=0.58,
                               playoff_rounds_won=2, is_champ=False,
                               league_avg_ppg=0.8)
check("alternate grows roughly half of captain (carry-aware)",
      abs((ra["leadership_delta"] + carry_of(alt)) * 2
          - (rc["leadership_delta"] + carry_of(cap))) < 0.01)
check("alternate tenure tracked separately",
      alt.alternate_tenure_years == 1 and alt.captain_tenure_years == 0)

# --- 6. No letter -> no growth, tenure resets
plain = StubPlayer("Plain", age=27, leadership=75, letter=None)
plain.captain_tenure_years = 3
rp = grow(plain, year=2030)
check("no letter -> no growth", rp["leadership_delta"] == 0)
check("losing the letter resets tenure",
      plain.captain_tenure_years == 0)

# --- 7. Diminishing returns near the top
mid = StubPlayer("Mid", age=27, leadership=70, letter="C")
top = StubPlayer("Top", age=27, leadership=95, letter="C")
mid.stats = top.stats = StubStats(points=80, games=82)
rm = grow(mid, year=2031)
rt = grow(top, year=2031)
check("95 leadership grows less than 70 in same situation",
      0 <= rt["leadership_delta"] < rm["leadership_delta"])

# --- 8. Hard cap at 100
wall = StubPlayer("Wall", age=22, leadership=99, letter="C")
wall.stats = StubStats(points=120, games=82)
rw = grow(wall, year=2032)
check("leadership never exceeds 100", wall.leadership <= 100)

# --- 9. Season-stamp idempotency: second run same season is a no-op
dup = StubPlayer("Dup", age=24, leadership=70, letter="C")
r9a = grow(dup, year=2033)
lead_after_first = dup.leadership
ten_after_first = dup.captain_tenure_years
r9b = grow(dup, year=2033)
check("re-run same season: no double growth",
      dup.leadership == lead_after_first and r9b["leadership_delta"] == 0)
check("re-run same season: tenure +1 only once",
      dup.captain_tenure_years == ten_after_first == 1)

# --- 10. Cup-winning captain banks +4 reputation; others don't
champ_c = StubPlayer("Champ C", age=28, leadership=88, letter="C")
champ_c.reputation = 70
champ_w = StubPlayer("Champ W", age=28, leadership=70, letter=None)
champ_w.reputation = 70
nonchamp_c = StubPlayer("NonChamp C", age=28, leadership=88, letter="C")
nonchamp_c.reputation = 70
check("Cup-winning C banks +4 rep",
      cg.cup_captain_rep_bonus(champ_c) == 74)
check("Cup rep history reason recorded",
      any(e.get("reason") == "stanley_cup_as_captain"
          for e in champ_c.reputation_history))
check("non-C champ gets no bonus", cg.cup_captain_rep_bonus(champ_w) == 70)
check("non-champ C gets no bonus",
      cg.cup_captain_rep_bonus(nonchamp_c, is_champ=False) == 70)

# --- 11. Milestone story: young letter-wearer crosses 90, fires once
star = StubPlayer("Star Kid", age=23, leadership=88, letter="C")
star.stats = StubStats(points=115, games=82)
rs = grow(star, year=2034)
check("young C crossing 90 gets milestone story",
      rs["milestone_story"] is not None and "Star Kid" in rs["milestone_story"]
      and star.leadership >= 90)
rs2 = grow(star, year=2035)  # next season: no repeat story
check("milestone story fires only once", rs2["milestone_story"] is None)

# --- 12. Old-save defaults: player with no tenure fields works
old = StubPlayer("Old Save", age=30, leadership=75, letter="C")
for f in ("captain_tenure_years", "alternate_tenure_years",
          "_captaincy_growth_season"):
    if hasattr(old, f):
        delattr(old, f)
ro = grow(old, year=2036)
check("old save without tenure fields grows fine",
      ro["leadership_delta"] > 0 and old.captain_tenure_years == 1)

# --- 14. Mentorship (the Yzerman effect) -------------------------------
def mentor(p, year=2040, win_pct=0.62, rounds=2, champ=False, best=92):
    return cg.apply_mentorship_growth(
        p, season_year=year, win_pct=win_pct, playoff_rounds_won=rounds,
        is_champ=champ, best_letter_leadership=best)


kid = StubPlayer("Kid", age=20, leadership=55, letter=None,
                 determination=85, teamwork=80)
rm = mentor(kid)
check("young high-character kid absorbs from elite winning room",
      rm["mentorship_delta"] + carry_of(kid) > 0.4)

# No elite regime figure -> no lesson
kid2 = StubPlayer("Kid2", age=20, leadership=55, letter=None,
                  determination=85, teamwork=80)
rm2 = mentor(kid2, best=70)
check("no elite leader -> no mentorship",
      rm2["mentorship_delta"] == 0 and carry_of(kid2) == 0.0)

# Elite captain, losing team -> the lesson doesn't land
kid3 = StubPlayer("Kid3", age=20, leadership=55, letter=None,
                  determination=85, teamwork=80)
rm3 = mentor(kid3, win_pct=0.45, rounds=0, best=92)
check("losing regime teaches nothing",
      rm3["mentorship_delta"] == 0 and carry_of(kid3) == 0.0)

# Character matters: low-character kid absorbs less in the same room
low = StubPlayer("LowChar", age=20, leadership=55, letter=None,
                 determination=40, teamwork=45)
high = StubPlayer("HighChar", age=20, leadership=55, letter=None,
                  determination=90, teamwork=88)
rlow = mentor(low, year=2041)
rhigh = mentor(high, year=2041)
check("right personality absorbs more than low character",
      (rhigh["mentorship_delta"] + carry_of(high))
      > (rlow["mentorship_delta"] + carry_of(low)))

# Too old to be shaped
vet_kid = StubPlayer("VetKid", age=27, leadership=55, letter=None,
                     determination=85, teamwork=80)
rmv = mentor(vet_kid, year=2042)
check("27-year-old doesn't get mentorship", rmv["mentorship_delta"] == 0)

# Letter-wearers have their own path
capkid = StubPlayer("CapKid", age=20, leadership=55, letter="A",
                    determination=85, teamwork=80)
rmc = mentor(capkid, year=2043)
check("letter-wearer excluded from mentorship", rmc["mentorship_delta"] == 0)

# Cup-winning regime teaches more
kid4 = StubPlayer("Kid4", age=20, leadership=55, letter=None,
                  determination=85, teamwork=80)
kid5 = StubPlayer("Kid5", age=20, leadership=55, letter=None,
                  determination=85, teamwork=80)
rnc = mentor(kid4, year=2044, win_pct=0.65, rounds=4, champ=False)
rcup = mentor(kid5, year=2044, win_pct=0.65, rounds=4, champ=True)
check("Cup regime teaches more than non-Cup",
      (rcup["mentorship_delta"] + carry_of(kid5))
      > (rnc["mentorship_delta"] + carry_of(kid4)))

# Idempotent within a season
kid6 = StubPlayer("Kid6", age=20, leadership=55, letter=None,
                  determination=85, teamwork=80)
rm6a = mentor(kid6, year=2045)
c_after = carry_of(kid6)
rm6b = mentor(kid6, year=2045)
check("mentorship idempotent within season",
      rm6b["mentorship_delta"] == 0 and carry_of(kid6) == c_after)

# --- 15. Cup-captain reputation: idempotent per season -----------------
cup_c = StubPlayer("Cup C", age=28, leadership=88, letter="C")
cup_c.reputation = 70
r_a = cg.cup_captain_rep_bonus(cup_c, is_champ=True, season_year=2028)
r_b = cg.cup_captain_rep_bonus(cup_c, is_champ=True, season_year=2028)
check("Cup-captain rep bonus pays once per season",
      r_a == 74 and r_b == 74 and cup_c.reputation == 74)
r_c = cg.cup_captain_rep_bonus(cup_c, is_champ=True, season_year=2029)
check("new season pays again", r_c == 78 and cup_c.reputation == 78)
not_c = StubPlayer("Not C", age=28, leadership=88, letter="A")
not_c.reputation = 70
r_nc = cg.cup_captain_rep_bonus(not_c, is_champ=True, season_year=2028)
check("non-captain gets no Cup-captain bonus",
      r_nc == 70 and not_c.reputation == 70)

# --- 13. Constants sanity: no single season exceeds the cap
check("season cap constant respected", cg.SEASON_GROWTH_CAP == 4)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
