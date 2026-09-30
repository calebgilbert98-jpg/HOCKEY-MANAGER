# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: staff aging and development -- young coaches grow with experience,
60+ non-icons regress, icons hold their craft, the oldest retire.

Run: python3 qa_staff_development.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as gc
from game_classes import (
    League, Staff, StaffRole, Team,
    _STAFF_DEVELOP_ATTRS, age_staff_one_year, develop_staff_member,
    staff_is_icon,
)

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def mkstaff(age=30, rep=60, assignment="nhl", icon_level=""):
    s = Staff("Test", "Coach", StaffRole.HEAD_COACH)
    s.age = age
    s.reputation = rep
    s.assignment = assignment
    s.icon_level = icon_level
    s.experience = 5
    for a in _STAFF_DEVELOP_ATTRS:
        setattr(s, a, 60)
    return s


def avg_attrs(s):
    return sum(getattr(s, a) for a in _STAFF_DEVELOP_ATTRS) / len(_STAFF_DEVELOP_ATTRS)


def run_years(s, n, employed=True, assignment="nhl"):
    for _ in range(n):
        develop_staff_member(s, employed=employed, assignment=assignment)


# --- 1. young NHL coach develops ---------------------------------------------
random.seed(11)
young = mkstaff(age=28, rep=60)
before = avg_attrs(young)
run_years(young, 5, employed=True, assignment="nhl")
gain = avg_attrs(young) - before
check("young NHL coach develops (+~7 over 5y)", gain >= 5, f"gain={gain:.1f}")

# --- 2. AHL develops slower than NHL ------------------------------------------
random.seed(21)
nhl_gains, ahl_gains = [], []
for i in range(30):
    a = mkstaff(age=28, rep=60)
    b = mkstaff(age=28, rep=60)
    random.seed(1000 + i)
    develop_staff_member(a, employed=True, assignment="nhl")
    random.seed(1000 + i)
    develop_staff_member(b, employed=True, assignment="ahl")
    nhl_gains.append(avg_attrs(a) - 60)
    ahl_gains.append(avg_attrs(b) - 60)
check("NHL chair develops faster than AHL chair",
      sum(nhl_gains) / 30 > sum(ahl_gains) / 30,
      f"nhl={sum(nhl_gains)/30:.2f} ahl={sum(ahl_gains)/30:.2f}")

# --- 3. unemployed develops slower than employed -------------------------------
random.seed(31)
emp_g, unemp_g = [], []
for i in range(30):
    a = mkstaff(age=28, rep=60)
    b = mkstaff(age=28, rep=60)
    random.seed(2000 + i)
    develop_staff_member(a, employed=True, assignment="nhl")
    random.seed(2000 + i)
    develop_staff_member(b, employed=False)
    emp_g.append(avg_attrs(a) - 60)
    unemp_g.append(avg_attrs(b) - 60)
check("employed coach develops faster than unemployed",
      sum(emp_g) / 30 > sum(unemp_g) / 30,
      f"emp={sum(emp_g)/30:.2f} unemp={sum(unemp_g)/30:.2f}")

# --- 4. prime coach holds steady ------------------------------------------------
random.seed(41)
prime = mkstaff(age=45, rep=70)
before = avg_attrs(prime)
run_years(prime, 5, employed=True, assignment="nhl")
drift = avg_attrs(prime) - before
check("prime coach (45) holds steady", abs(drift) <= 3, f"drift={drift:.1f}")

# --- 5. 60+ non-icon regresses --------------------------------------------------
random.seed(51)
old = mkstaff(age=62, rep=60)
before = avg_attrs(old)
run_years(old, 5, employed=True, assignment="nhl")
loss = avg_attrs(old) - before
check("62yo non-icon regresses", loss <= -4, f"delta={loss:.1f}")

# --- 6. 60+ icon by reputation holds --------------------------------------------
random.seed(61)
icon_rep = mkstaff(age=62, rep=90)
before = avg_attrs(icon_rep)
run_years(icon_rep, 5, employed=True, assignment="nhl")
drift = avg_attrs(icon_rep) - before
check("62yo icon (rep 90) does not regress", abs(drift) <= 2,
      f"drift={drift:.1f}")
check("icon reputation is untouched", icon_rep.reputation == 90,
      f"rep={icon_rep.reputation}")

# --- 7. 60+ icon by icon_level holds --------------------------------------------
random.seed(71)
icon_stamp = mkstaff(age=64, rep=55, icon_level="icon")
before = avg_attrs(icon_stamp)
run_years(icon_stamp, 5, employed=True, assignment="nhl")
drift = avg_attrs(icon_stamp) - before
check("64yo stamped icon does not regress", abs(drift) <= 2,
      f"drift={drift:.1f}")

check("staff_is_icon: rep>=85", staff_is_icon(mkstaff(age=62, rep=85)))
check("staff_is_icon: stamped", staff_is_icon(mkstaff(age=62, rep=40,
                                                      icon_level="icon")))
check("staff_is_icon: neither", not staff_is_icon(mkstaff(age=62, rep=60)))

# --- 8. attribute clamps ----------------------------------------------------------
random.seed(81)
capped = mkstaff(age=28, rep=60)
for a in _STAFF_DEVELOP_ATTRS:
    setattr(capped, a, 99)
develop_staff_member(capped, employed=True, assignment="nhl")
check("attributes never exceed 99",
      all(getattr(capped, a) <= 99 for a in _STAFF_DEVELOP_ATTRS))

random.seed(82)
floored = mkstaff(age=66, rep=50)
for a in _STAFF_DEVELOP_ATTRS:
    setattr(floored, a, 26)
run_years(floored, 5, employed=True, assignment="nhl")
check("attributes never drop below 25",
      all(getattr(floored, a) >= 25 for a in _STAFF_DEVELOP_ATTRS))

# --- 9. age_staff_one_year: aging + experience ------------------------------------
random.seed(91)
s = mkstaff(age=30, rep=60)
exp0 = s.experience
ret = age_staff_one_year(s, employed=True, assignment="nhl")
check("staffer ages one year", s.age == 31, f"age={s.age}")
check("employed staffer gains experience", s.experience == exp0 + 1)
check("young staffer does not retire", ret is False)

random.seed(92)
u = mkstaff(age=30, rep=60)
exp0 = u.experience
age_staff_one_year(u, employed=False)
check("unemployed staffer gains no experience", u.experience == exp0)

# --- 10. retirement ---------------------------------------------------------------
random.seed(101)
never = [age_staff_one_year(mkstaff(age=40, rep=60), employed=True)
         for _ in range(50)]
check("40yo never retires", not any(never))

orig_random = gc.random.random
try:
    gc.random.random = lambda: 0.0  # force every probability roll to hit
    check("75yo non-icon retires",
          age_staff_one_year(mkstaff(age=75, rep=60), employed=True) is True)
    check("75yo icon (rep 90) retires eventually too",
          age_staff_one_year(mkstaff(age=75, rep=92), employed=True) is True)
finally:
    gc.random.random = orig_random

random.seed(102)
icon70 = [age_staff_one_year(mkstaff(age=70, rep=92), employed=True)
          for _ in range(50)]
check("70yo icon does not retire yet", not any(icon70))

# --- 11. reputation drifts with the craft ------------------------------------------
random.seed(111)
riser = mkstaff(age=28, rep=50)
run_years(riser, 5, employed=True, assignment="nhl")
check("rising young coach gains reputation", riser.reputation > 50,
      f"rep={riser.reputation}")

random.seed(112)
fader = mkstaff(age=63, rep=60)
run_years(fader, 5, employed=True, assignment="nhl")
check("fading veteran loses reputation", fader.reputation < 60,
      f"rep={fader.reputation}")

# --- 12. end_of_season integration ---------------------------------------------------
random.seed(121)
league = League("NHL")
league.season_year = 2028
t = Team("Testers", "Testville", "Atlantic", "Eastern", "NHL", "GM", None)
young_nhl = mkstaff(age=30, rep=60)
old_nhl = mkstaff(age=90, rep=60)
old_nhl.first_name, old_nhl.last_name = "Old", "Timer"
t.staff = [young_nhl, old_nhl]
league.teams = [t]
fa = mkstaff(age=35, rep=55)
league.free_agent_staff = [fa]
ov = mkstaff(age=40, rep=65, assignment="overseas")
league.overseas_staff = [ov]

orig_random = gc.random.random
try:
    gc.random.random = lambda: 0.0  # force the 90yo's retirement roll
    league.end_of_season()
finally:
    gc.random.random = orig_random

check("rollover ages team staff", young_nhl.age == 31, f"age={young_nhl.age}")
check("rollover ages free agents", fa.age == 36, f"age={fa.age}")
check("rollover ages overseas staff", ov.age == 41, f"age={ov.age}")
check("90yo retires out of team staff", old_nhl not in t.staff,
      f"staff={len(t.staff)}")
check("retirement is recorded",
      getattr(league, "staff_retirement_news", []),
      f"news={getattr(league, 'staff_retirement_news', [])}")
check("retirement news names the coach",
      any("Old Timer" in n for n in league.staff_retirement_news))
check("young coach still employed after rollover", young_nhl in t.staff)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
