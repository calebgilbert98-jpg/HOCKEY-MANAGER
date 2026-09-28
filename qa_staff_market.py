"""QA: staff market rules -- budgets, asks, approach rules, pools, save/load.

Run: python3 qa_staff_market.py
"""
import os
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(7)

from game_classes import (
    League, Staff, StaffRole, Team,
    can_approach_staff, default_staff_budget, is_offseason,
    staff_market_ask, team_can_afford_staff,
)

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" +
          (f" -- {extra}" if extra and not cond else ""))


def mkteam(name):
    t = Team(name, "City", "Div", "Conf", "NHL", "GM", None)
    t.staff_budget = default_staff_budget(name)
    return t


def mkstaff(role=StaffRole.HEAD_COACH, rep=70, assignment="nhl"):
    s = Staff("Test", "Coach", role)
    s.reputation = rep
    s.assignment = assignment
    return s


JULY = date(2026, 7, 15)
NOV = date(2026, 11, 15)

# --- 1. ask model ------------------------------------------------------------
elite = mkstaff(StaffRole.HEAD_COACH, 95)
mid_hc = mkstaff(StaffRole.HEAD_COACH, 60)
scout = mkstaff(StaffRole.AMATEUR_SCOUT, 60)
check("elite HC ask is top-coach money",
      3_000_000 <= staff_market_ask(elite) <= 5_000_000,
      f"{staff_market_ask(elite):,}")
check("ask rises with reputation",
      staff_market_ask(elite) > staff_market_ask(mid_hc))
check("HC ask dwarfs scout ask",
      staff_market_ask(mid_hc) > 3 * staff_market_ask(scout))
check("ask rounds to $25k", staff_market_ask(elite) % 25_000 == 0)

# --- 2. budgets ---------------------------------------------------------------
big = mkteam("Toronto Maple Leafs")
small = mkteam("Utah Hockey Club")
mid = mkteam("Seattle Kraken")
check("big market gets $13M", big.staff_budget == 13_000_000)
check("small market gets $7M", small.staff_budget == 7_000_000)
check("mid market gets $10M", mid.staff_budget == 10_000_000)
check("unknown club defaults to mid",
      default_staff_budget("Somewhere Else") == 10_000_000)

s1 = mkstaff(); s1.salary = 2_000_000
s2 = mkstaff(StaffRole.ASSISTANT_COACH); s2.salary = 600_000
mid.staff.extend([s1, s2])
check("payroll sums staff salaries", mid.staff_payroll() == 2_600_000)
check("remaining = budget - payroll",
      mid.staff_budget_remaining() == 7_400_000)
check("affordable offer passes",
      team_can_afford_staff(mid, 7_400_000))
check("unaffordable offer fails",
      not team_can_afford_staff(mid, 7_400_001))

# --- 3. approach rules ----------------------------------------------------------
user = mkteam("Seattle Kraken")
rival = mkteam("Boston Bruins")
fa = mkstaff()
overseas = mkstaff(assignment="overseas")
ahl = mkstaff(StaffRole.ASSISTANT_COACH, assignment="ahl")
nhl = mkstaff()
own = mkstaff()

check("free agent approachable in-season",
      can_approach_staff(fa, None, user, NOV)[0])
check("overseas approachable in-season",
      can_approach_staff(overseas, None, user, NOV)[0])
check("rival AHL approachable in offseason",
      can_approach_staff(ahl, rival, user, JULY)[0])
ok, reason = can_approach_staff(ahl, rival, user, NOV)
check("rival AHL blocked in-season", not ok)
check("in-season block names the offseason rule",
      "offseason" in reason.lower(), reason)
ok, reason = can_approach_staff(nhl, rival, user, JULY)
check("rival NHL staff never approachable", not ok)
check("own staff not approachable",
      not can_approach_staff(own, user, user, JULY)[0])
check("offseason covers May-Sep",
      all(is_offseason(date(2026, m, 15)) for m in (5, 6, 7, 8, 9)))
check("in-season months are not offseason",
      not any(is_offseason(date(2026, m, 15)) for m in (1, 2, 3, 10, 11)))

# --- 4. generator: AHL staff, budgets, overseas pool ------------------------------
from database_generator import DatabaseGenerator, DATABASE_CONFIGURATIONS

gen = DatabaseGenerator(DATABASE_CONFIGURATIONS["Small"])
teams = [mkteam(n) for n in ("Toronto Maple Leafs", "Utah Hockey Club")]
gen._generate_team_staff(teams)
for t in teams:
    ahl = [s for s in t.staff
           if (getattr(s, "assignment", "") or "") == "ahl"]
    nhl = [s for s in t.staff
           if (getattr(s, "assignment", "") or "") == "nhl"]
    check(f"{t.team_name}: AHL staff generated (1+2)", len(ahl) == 3,
          f"got {len(ahl)}")
    check(f"{t.team_name}: NHL staff intact", len(nhl) == 8,
          f"got {len(nhl)}")
    check(f"{t.team_name}: budget assigned at gen",
          t.staff_budget == default_staff_budget(t.team_name))
    check(f"{t.team_name}: payroll fits budget",
          t.staff_payroll() <= t.staff_budget,
          f"payroll={t.staff_payroll():,}")

overseas_pool = gen._generate_overseas_staff(40)
check("overseas pool generated", len(overseas_pool) == 40)
check("overseas staff flagged",
      all(getattr(s, "assignment", "") == "overseas"
          for s in overseas_pool))
check("overseas staff have clubs",
      all(getattr(s, "current_club", "") for s in overseas_pool))
check("overseas staff are European",
      all(s.nationality in ("Sweden", "Finland", "Czech Republic", "Russia",
                            "Germany", "Switzerland", "Slovakia")
          for s in overseas_pool))

# --- 5. coach_practice prefers NHL staff -------------------------------------------
import coach_practice as cp

t = mkteam("Seattle Kraken")
nhl_hc = mkstaff(StaffRole.HEAD_COACH, assignment="nhl")
ahl_hc = mkstaff(StaffRole.HEAD_COACH, assignment="ahl")
# AHL coach listed FIRST -- lookup must still prefer the NHL one.
t.staff = [ahl_hc, nhl_hc]
check("head_coach_of prefers NHL assignment",
      cp.head_coach_of(t) is nhl_hc)
t2 = mkteam("Seattle Kraken")
t2.staff = [ahl_hc]
check("head_coach_of falls back to AHL when only AHL",
      cp.head_coach_of(t2) is ahl_hc)

# --- 6. save/load round-trip ----------------------------------------------------------
from save_load_system import GameSaveManager

sl = GameSaveManager(SimpleNamespace())
league = League("NHL", 2026)
league.teams = teams
league.overseas_staff = overseas_pool[:5]
data = {
    "team": sl._serialize_team(teams[0]),
    "league_bits": {
        "overseas_staff": [sl._serialize_staff(s)
                           for s in league.overseas_staff],
    },
}
check("staff_budget serialized",
      data["team"].get("staff_budget") == 13_000_000)
t_rt = sl._restore_team(data["team"])
check("staff_budget restored", t_rt.staff_budget == 13_000_000)
check("AHL assignment survives restore",
      any(getattr(s, "assignment", "") == "ahl" for s in t_rt.staff))
# Old save without the key -> tier default.
old = dict(data["team"])
del old["staff_budget"]
t_old = sl._restore_team(old)
check("old save gets tier default budget",
      t_old.staff_budget == 13_000_000)
overseas_rt = [sl._restore_staff(d)
               for d in data["league_bits"]["overseas_staff"]]
check("overseas pool restores",
      len(overseas_rt) == 5
      and all(getattr(s, "assignment", "") == "overseas"
              for s in overseas_rt))
check("overseas clubs survive",
      all(getattr(s, "current_club", "") for s in overseas_rt))

# --- 7. sign_free_agent_staff budget gate ----------------------------------------------
import main as main_mod

mgr = SimpleNamespace()
mgr.user_team = mkteam("Utah Hockey Club")  # $7M budget
mgr.league = SimpleNamespace(free_agent_staff=[])
# Bind the real method to the fake manager.
mgr.sign_free_agent_staff = (
    main_mod.GameManager.sign_free_agent_staff.__get__(mgr))
poor = mkstaff()
mgr.league.free_agent_staff.append(poor)
check("sign blocked when over budget",
      mgr.sign_free_agent_staff(poor, 8_000_000, 3) is False)
check("blocked staffer stays in the pool", poor in mgr.league.free_agent_staff)
check("blocked staffer not hired", poor not in mgr.user_team.staff)
rich = mkstaff()
mgr.league.free_agent_staff.append(rich)
check("sign allowed within budget",
      mgr.sign_free_agent_staff(rich, 2_000_000, 2) is True)
check("hired staffer joins as NHL", rich.assignment == "nhl")

# --- 8. MP hire parity: all three sources, approach rules, budget ---------------
host = SimpleNamespace(
    league=SimpleNamespace(free_agent_staff=[], overseas_staff=[],
                           teams=[]),
    current_date=JULY,
)
host._mp_hire_staff = main_mod.HockeyManagerGUI._mp_hire_staff.__get__(host)

mp_team = mkteam("Seattle Kraken")
mp_rival = mkteam("Boston Bruins")
host.league.teams = [mp_team, mp_rival]

fa_s = mkstaff(StaffRole.HEAD_COACH, 60)
fa_s.id = "mp-fa-1"
ov_s = mkstaff(StaffRole.HEAD_COACH, 75, assignment="overseas")
ov_s.id = "mp-ov-1"
ahl_s = mkstaff(StaffRole.ASSISTANT_COACH, 65, assignment="ahl")
ahl_s.id = "mp-ahl-1"
host.league.free_agent_staff.append(fa_s)
host.league.overseas_staff.append(ov_s)
mp_rival.staff.append(ahl_s)

ok, msg = host._mp_hire_staff({"staff_id": "mp-fa-1", "salary": 1_000_000,
                               "years": 2}, mp_team, None)
check("MP hires free agent", ok, msg)
check("MP FA leaves the pool", fa_s not in host.league.free_agent_staff)
check("MP hire joins as NHL staff", fa_s in mp_team.staff
      and fa_s.assignment == "nhl")

ok, msg = host._mp_hire_staff({"staff_id": "mp-ov-1", "salary": 2_000_000,
                               "years": 3}, mp_team, None)
check("MP hires overseas coach", ok, msg)
check("MP overseas hire leaves the pool",
      ov_s not in host.league.overseas_staff)

ok, msg = host._mp_hire_staff({"staff_id": "mp-ahl-1", "salary": 800_000,
                               "years": 2}, mp_team, None)
check("MP poaches rival AHL coach in offseason", ok, msg)
check("MP poached coach leaves the old club",
      ahl_s not in mp_rival.staff and ahl_s in mp_team.staff)

# In-season AHL approach must be refused, staffer untouched.
host.current_date = NOV
ahl_s2 = mkstaff(StaffRole.ASSISTANT_COACH, 65, assignment="ahl")
ahl_s2.id = "mp-ahl-2"
mp_rival.staff.append(ahl_s2)
ok, msg = host._mp_hire_staff({"staff_id": "mp-ahl-2", "salary": 800_000,
                               "years": 2}, mp_team, None)
check("MP in-season AHL poach refused", not ok, msg)
check("refused poach keeps the staffer at the old club",
      ahl_s2 in mp_rival.staff and ahl_s2 not in mp_team.staff)

# Over-budget MP offer is refused and the pool is untouched.
rich_mp = mkstaff(StaffRole.HEAD_COACH, 80)
rich_mp.id = "mp-rich-1"
host.league.free_agent_staff.append(rich_mp)
ok, msg = host._mp_hire_staff({"staff_id": "mp-rich-1", "salary": 9_000_000,
                               "years": 2}, mp_team, None)
check("MP over-budget hire refused", not ok, msg)
check("refused hire stays in the pool",
      rich_mp in host.league.free_agent_staff
      and rich_mp not in mp_team.staff)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
