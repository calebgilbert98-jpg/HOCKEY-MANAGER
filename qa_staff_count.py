"""QA: Every team starts with the correct amount of staff (Muck 2026-10-02).

Verifies:
1. All 32 NHL teams get the full 27-role template + 4 AHL affiliate staff
2. AHL teams get skeleton staff (not the wasted full NHL template)
3. Other leagues get basic staff
4. verify_all_teams_staffed() passes on a full league
5. backfill_team_staff() tops up understaffed teams without doubling HC/GM
6. League.add_team() staffs teams added after generation
7. Never raises on edge cases (empty league, None staff, etc.)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import Team, Staff, StaffRole, League
from database_generator import (
    DatabaseGenerator,
    TEAM_STAFF_TEMPLATE,
    verify_all_teams_staffed,
    backfill_team_staff,
)

passed = 0
failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")


def make_teams():
    teams = []
    for i in range(32):
        t = Team(team_name=f"NHL Team {i}", city="C", division="D", conference="C")
        t.league_name = "National Hockey League"
        teams.append(t)
    for i in range(30):
        t = Team(team_name=f"AHL Team {i}", city="C", division="D", conference="C")
        t.league_name = "American Hockey League"
        teams.append(t)
    for i in range(5):
        t = Team(team_name=f"Euro Team {i}", city="C", division="D", conference="C")
        t.league_name = "Swedish Hockey League"
        teams.append(t)
    return teams


print("Test 1: All 32 NHL teams get full staff (27 NHL + 4 AHL)")
teams = make_teams()
gen = DatabaseGenerator.__new__(DatabaseGenerator)
gen._generate_team_staff(teams)
nhl_teams = [t for t in teams if t.league_name == "National Hockey League"]
check("32 NHL teams", len(nhl_teams) == 32, f"got {len(nhl_teams)}")
all_full = True
for t in nhl_teams:
    nhl = sum(1 for s in t.staff if (getattr(s, "assignment", None) or "nhl") == "nhl")
    ahl = sum(1 for s in t.staff if getattr(s, "assignment", None) == "ahl")
    if len(t.staff) != 31 or nhl != 27 or ahl != 4:
        all_full = False
        print(f"    {t.team_name}: total={len(t.staff)} nhl={nhl} ahl={ahl}")
check("every NHL team has 31 staff (27+4)", all_full)

print("Test 2: Template coverage on NHL teams")
from collections import Counter
t0 = nhl_teams[0]
counts = Counter(s.role for s in t0.staff if (getattr(s, "assignment", None) or "nhl") == "nhl")
template_ok = all(counts.get(role, 0) >= count for role, count, _s in TEAM_STAFF_TEMPLATE)
check("template roles all covered", template_ok)
check("exactly 1 head coach", counts.get(StaffRole.HEAD_COACH, 0) == 1)
check("exactly 1 GM", counts.get(StaffRole.GENERAL_MANAGER, 0) == 1)
check("2 assistant coaches", counts.get(StaffRole.ASSISTANT_COACH, 0) == 2)

print("Test 3: AHL affiliate staff on NHL clubs")
ahl_counts = Counter(s.role for s in t0.staff if getattr(s, "assignment", None) == "ahl")
check("1 AHL head coach", ahl_counts.get(StaffRole.HEAD_COACH, 0) == 1)
check("2 AHL assistants", ahl_counts.get(StaffRole.ASSISTANT_COACH, 0) == 2)
check("1 AHL GM", ahl_counts.get(StaffRole.GENERAL_MANAGER, 0) == 1)

print("Test 4: AHL teams get skeleton staff (not full NHL template)")
ahl_teams = [t for t in teams if t.league_name == "American Hockey League"]
check("30 AHL teams", len(ahl_teams) == 30)
skeleton_ok = all(len(t.staff) == 3 for t in ahl_teams)
check("AHL teams have 3 skeleton staff (not 31)", skeleton_ok,
      f"got {[len(t.staff) for t in ahl_teams[:3]]}")

print("Test 5: Other leagues get basic staff")
euro_teams = [t for t in teams if t.league_name == "Swedish Hockey League"]
basic_ok = all(len(t.staff) == 3 for t in euro_teams)
check("Euro teams have 3 basic staff", basic_ok)

print("Test 6: verify_all_teams_staffed() passes")
league = League("Test League")
league.teams = teams
gaps = verify_all_teams_staffed(league)
check("no gaps in fully-staffed league", gaps == {}, f"gaps: {list(gaps.keys())[:3]}")

print("Test 7: verify detects understaffed team")
t_bad = Team(team_name="Bad Team", city="C", division="D", conference="C")
t_bad.league_name = "National Hockey League"
t_bad.staff = []  # empty!
league2 = League("Test2")
league2.teams = [t_bad]
gaps2 = verify_all_teams_staffed(league2)
check("detects empty-staff team", "Bad Team" in gaps2)

print("Test 8: backfill tops up without doubling")
t_old = Team(team_name="Old Team", city="C", division="D", conference="C")
t_old.league_name = "National Hockey League"
t_old.staff = [
    Staff(first_name="A", last_name="B", role=StaffRole.HEAD_COACH, assignment="nhl"),
    Staff(first_name="C", last_name="D", role=StaffRole.GENERAL_MANAGER, assignment="nhl"),
]
league3 = League("Test3")
league3.teams = [t_old]
backfill_team_staff(league3)
nhl_n = sum(1 for s in t_old.staff if (getattr(s, "assignment", None) or "nhl") == "nhl")
ahl_n = sum(1 for s in t_old.staff if getattr(s, "assignment", None) == "ahl")
check("backfilled to 31", len(t_old.staff) == 31, f"got {len(t_old.staff)}")
check("27 NHL staff", nhl_n == 27, f"got {nhl_n}")
check("4 AHL staff", ahl_n == 4, f"got {ahl_n}")
roles = Counter(s.role for s in t_old.staff if (getattr(s, "assignment", None) or "nhl") == "nhl")
check("HC not doubled", roles[StaffRole.HEAD_COACH] == 1)
check("GM not doubled", roles[StaffRole.GENERAL_MANAGER] == 1)
gaps3 = verify_all_teams_staffed(league3)
check("verification passes after backfill", gaps3 == {})

print("Test 9: add_team() staffs late-added teams")
league4 = League("Test4")
t_new = Team(team_name="Expansion Team", city="C", division="D", conference="C")
t_new.league_name = "National Hockey League"
league4.add_team(t_new)
check("expansion team got staff", len(t_new.staff) == 31, f"got {len(t_new.staff)}")

print("Test 10: Never raises on edge cases")
try:
    verify_all_teams_staffed(None)
    verify_all_teams_staffed(League("Empty"))
    backfill_team_staff(None)
    t_none = Team(team_name="X", city="C", division="D", conference="C")
    t_none.staff = None
    l5 = League("T5")
    l5.teams = [t_none]
    backfill_team_staff(l5)
    check("no exceptions on edge cases", True)
except Exception as e:
    check("no exceptions on edge cases", False, str(e))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
