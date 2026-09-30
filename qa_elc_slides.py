"""QA: ELC slide rule (CBA 9.1(d)) + League-Year max comp + minor salary.

Covers: the slide predicate (18/19, <10 NHL GP, double-slide requires the
first, the Sept-16-to-Dec-31 age-19 exception), the League-Year max
annual compensation table (min + $175k per season), the compat helpers,
the draft-year minor-salary progression, and the end-of-season rollover
actually sliding a signed ELC (and not sliding anything else).
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import salary_cap_system as scs
from game_classes import League, Player, PlayerPosition, Team

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


S = scs.elc_slide_applies

# 1. Slide predicate unit tests.
check("18yo, 5 GP -> slides", S(18, 0, 0, 5))
check("18yo, 10 GP -> no slide", not S(18, 0, 0, 10))
check("18yo, 9 GP -> slides", S(18, 0, 0, 9))
check("18yo double slide (1 used, 1 done, 5 GP) -> slides", S(18, 1, 1, 5))
check("18yo no first slide, 2nd season -> no slide", not S(18, 0, 1, 5))
check("18yo slides exhausted -> no slide", not S(18, 2, 2, 5))
check("19yo, 5 GP -> slides", S(19, 0, 0, 5, "2007-06-15", 2026))
check("19yo, 10 GP -> no slide", not S(19, 0, 0, 10, "2007-06-15", 2026))
check("19yo second season -> no slide", not S(19, 1, 1, 5, "2007-06-15", 2026))
# The 9.1(d) exception: nominal 19yo turning 20 between Sept 16 and Dec 31
# of the signing year never slides.
check("19yo born Sep 20 2006 (turns 20 in window) -> no slide",
      not S(19, 0, 0, 5, "2006-09-20", 2026))
check("19yo born Dec 31 2006 (turns 20 in window) -> no slide",
      not S(19, 0, 0, 5, "2006-12-31", 2026))
check("19yo born Sep 15 2006 (turns 20 ON Sep 15) -> slides",
      S(19, 0, 0, 5, "2006-09-15", 2026))
check("19yo born Jan 10 2007 (turns 20 next year) -> slides",
      S(19, 0, 0, 5, "2007-01-10", 2026))
check("20yo -> no slide", not S(20, 0, 0, 5))
check("garbage input -> no slide", not S(None, 0, 0, 5))

# 2. League-Year max annual compensation: league min + $175k.
check("2026-27 max = 1.025M", scs.elc_max_annual_comp(2026) == 1_025_000)
check("2027-28 max = 1.075M", scs.elc_max_annual_comp(2027) == 1_075_000)
check("2028-29 max = 1.125M", scs.elc_max_annual_comp(2028) == 1_125_000)
check("2029-30 max = 1.175M", scs.elc_max_annual_comp(2029) == 1_175_000)
# Compat helpers: flat-salary game -> lowest covered year governs.
check("elc_max_total(3) = 3.075M", scs.elc_max_total(3) == 3_075_000,
      repr(scs.elc_max_total(3)))
check("elc_max_salary(3) = 1.025M", scs.elc_max_salary(3) == 1_025_000)
check("elc_max_salary(2) = 1.025M", scs.elc_max_salary(2) == 1_025_000)

# 3. Draft-year minor-salary progression (CBA 9.4).
check("2021 draft -> 80k", scs.elc_minor_salary_max(2021) == 80_000)
check("2022 draft -> 82.5k", scs.elc_minor_salary_max(2022) == 82_500)
check("2024 draft -> 85k", scs.elc_minor_salary_max(2024) == 85_000)
check("2026 draft -> 87.5k", scs.elc_minor_salary_max(2026) == 87_500)
check("2028 draft -> 90k", scs.elc_minor_salary_max(2028) == 90_000)
check("2030 draft -> 92.5k", scs.elc_minor_salary_max(2030) == 92_500)

# 4. End-to-end rollover: an 18yo signed ELC slides twice, then burns.
def fresh_league():
    lg = League(league_name="Slide League")
    t = Team(team_name="Slide Team", city="Test", division="X", conference="Y")
    lg.teams = [t]
    lg.season_year = 2026
    return lg, t


def signed_elc(t, lg, seed, age, birth_date, name="Slide"):
    random.seed(seed)
    p = Player(name, "Kid", age, PlayerPosition.CENTER)
    p.birth_date = birth_date
    p.contract = None
    p.rights_team = t.team_name
    p.rights_expiry_year = 2030
    p.rights_type = "CHL"
    p.drafted_year = 2026
    t.prospects.append(p)
    ok = lg.finalize_elc_signing(t, p, 900_000, 3, 0, 0)
    assert ok, f"signing failed for {name}"
    return p


def promote_to_nhl(t, p):
    # Real roster move: leaves the prospects pool, joins the NHL roster.
    # (A player in both lists would be aged twice per rollover.)
    if p in t.prospects:
        t.prospects.remove(p)
    t.roster.append(p)


lg, t = fresh_league()
kid = signed_elc(t, lg, 101, 18, "2008-06-15")
promote_to_nhl(t, kid)  # on the NHL roster: his GP counts
check("18yo signs 3-yr ELC", kid.contract.years_remaining == 3)
check("slide state stamped",
      kid.elc_signing_sept15_age == 18 and kid.elc_slides_used == 0)

kid.stats.games_played = 5
lg.end_of_season()
check("5-GP season slides: term back to 3",
      kid.contract.years_remaining == 3,
      repr(kid.contract.years_remaining))
check("slide counted", kid.elc_slides_used == 1)
check("season counted", kid.elc_seasons_completed == 1)
check("slide news collected on the league",
      any("slides" in str(n) for n in getattr(lg, "elc_slide_news", [])))

kid.stats.games_played = 4
lg.end_of_season()
check("double slide: term back to 3 again",
      kid.contract.years_remaining == 3,
      repr(kid.contract.years_remaining))
check("two slides used", kid.elc_slides_used == 2)

kid.stats.games_played = 12
lg.end_of_season()
check("12-GP season burns a year: 3 -> 2",
      kid.contract.years_remaining == 2,
      repr(kid.contract.years_remaining))
check("no third slide", kid.elc_slides_used == 2)

# 5. The age-19 exception, end-to-end: no slide despite 5 GP.
lg2, t2 = fresh_league()
exc = signed_elc(t2, lg2, 102, 19, "2006-09-20", name="Except")
promote_to_nhl(t2, exc)
exc.stats.games_played = 5
lg2.end_of_season()
check("exception 19yo does not slide: 3 -> 2",
      exc.contract.years_remaining == 2,
      repr(exc.contract.years_remaining))
check("exception 19yo uses no slides", exc.elc_slides_used == 0)

# 6. A normal 19yo slides once.
lg3, t3 = fresh_league()
norm = signed_elc(t3, lg3, 103, 19, "2007-06-15", name="Normal")
promote_to_nhl(t3, norm)
norm.stats.games_played = 5
lg3.end_of_season()
check("normal 19yo slides once: term back to 3",
      norm.contract.years_remaining == 3,
      repr(norm.contract.years_remaining))

# 7. Non-ELC deals and unstamped (old-save) ELCs never slide.
lg4, t4 = fresh_league()
from game_classes import Contract
vet = Player("Vet", "Eran", 30, PlayerPosition.CENTER)
vet.contract = Contract(salary=5_000_000, years_remaining=3)
t4.roster.append(vet)
vet.stats.games_played = 5
old = Player("Old", "Save", 20, PlayerPosition.CENTER)
old.contract = Contract(salary=900_000, years_remaining=3, two_way=True)
# No entry_level stamp, no slide state: a pre-review save.
t4.roster.append(old)
old.stats.games_played = 5
lg4.season_year = 2026
lg4.end_of_season()
check("veteran deal burns normally: 3 -> 2", vet.contract.years_remaining == 2)
check("unstamped ELC burns normally: 3 -> 2", old.contract.years_remaining == 2)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
