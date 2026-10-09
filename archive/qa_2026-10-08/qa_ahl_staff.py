# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: AHL organization -- one NHL HC + one AHL HC, AHL GM generated,
assignment-aware coach lookup, hireable AHL GM/coach, old-save backfill.
Run: python3 qa_ahl_staff.py
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

random.seed(20260929)
import reputation_system as rs
from game_classes import Staff, StaffRole

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


def mk(role, assignment, name="T"):
    return Staff(first_name=name, last_name="Est", role=role,
                 age=45, experience=10, assignment=assignment)


def coaches(team, assignment):
    return [s for s in team.staff
            if "Head Coach" in s.role.value
            and (s.assignment or "").lower() == assignment]


def gms(team, assignment):
    return [s for s in team.staff
            if "General Manager" in s.role.value
            and (s.assignment or "").lower() == assignment]


# --- 1. generation: exactly one of each chair -------------------------------
from database_generator import DatabaseGenerator
gen = DatabaseGenerator.__new__(DatabaseGenerator)
team = SimpleNamespace(team_name="Test Club", staff=[])
gen._generate_team_staff([team])
check("gen: exactly 1 NHL head coach", len(coaches(team, "nhl")) == 1)
check("gen: exactly 1 AHL head coach", len(coaches(team, "ahl")) == 1)
check("gen: exactly 1 NHL GM", len(gms(team, "nhl")) == 1)
check("gen: exactly 1 AHL GM", len(gms(team, "ahl")) == 1)
check("gen: AHL GM salary below NHL GM band",
      gms(team, "ahl")[0].salary <= 400000)

# --- 2. assignment-aware lookup ----------------------------------------------
nhl_hc, ahl_hc = coaches(team, "nhl")[0], coaches(team, "ahl")[0]
check("_head_coach_of returns the NHL coach",
      rs._head_coach_of(team) is nhl_hc)
check("_ahl_coach_of returns the AHL coach",
      rs._ahl_coach_of(team) is ahl_hc)
check("_ahl_gm_of returns the AHL GM",
      rs._ahl_gm_of(team) is gms(team, "ahl")[0])

# NHL chair empty (fired): lookup must NOT fall through to the AHL coach.
team.staff.remove(nhl_hc)
check("fired NHL HC -> _head_coach_of is None (no AHL confusion)",
      rs._head_coach_of(team) is None)
check("AHL coach still resolvable separately",
      rs._ahl_coach_of(team) is ahl_hc)
team.staff.append(nhl_hc)

# Legacy staff with no assignment at all: falls back to first HC found.
legacy = SimpleNamespace(
    staff=[mk(StaffRole.HEAD_COACH, None, "Old")])
check("no-assignment legacy staff falls back to first HC",
      rs._head_coach_of(legacy) is legacy.staff[0])

# --- 3. old-save backfill ----------------------------------------------------
old = SimpleNamespace(team_name="Old Club", staff=[
    mk(StaffRole.HEAD_COACH, "nhl", "Nhl"),
    mk(StaffRole.HEAD_COACH, "ahl", "Ahl"),
    mk(StaffRole.GENERAL_MANAGER, "nhl", "Gm"),
])
check("backfill creates missing AHL GM",
      rs.ensure_ahl_front_office(old) is True
      and len(gms(old, "ahl")) == 1)
check("backfill keeps existing AHL coach (no duplicate)",
      len(coaches(old, "ahl")) == 1)
check("backfill idempotent (second run creates nothing)",
      rs.ensure_ahl_front_office(old) is False
      and len(gms(old, "ahl")) == 1
      and len(coaches(old, "ahl")) == 1)

# --- 4. hireable AHL staff ----------------------------------------------------
import main as main_mod


class FakeLeague:
    def __init__(self, pool):
        self.free_agent_staff = pool


class FakeGM:
    def __init__(self, team, pool):
        self.user_team = team
        self.league = FakeLeague(pool)


mgr = FakeGM.__new__(FakeGM)
user = SimpleNamespace(team_name="User Club", staff=[
    mk(StaffRole.HEAD_COACH, "nhl", "U"),
    mk(StaffRole.GENERAL_MANAGER, "nhl", "Ug"),
])
fa_gm = mk(StaffRole.GENERAL_MANAGER, None, "Fa")
fa_coach = mk(StaffRole.HEAD_COACH, None, "Fc")
mgr.user_team = user
mgr.league = FakeLeague([fa_gm, fa_coach])
mgr.sign_free_agent_staff = (
    main_mod.GameManager.sign_free_agent_staff.__get__(mgr))

check("hire AHL GM stamps assignment='ahl'",
      mgr.sign_free_agent_staff(fa_gm, 300_000, 2, assignment="ahl") is True
      and fa_gm.assignment == "ahl"
      and fa_gm in user.staff)
check("hire defaults to NHL assignment",
      mgr.sign_free_agent_staff(fa_coach, 500_000, 2) is True
      and fa_coach.assignment == "nhl")
bad = mk(StaffRole.ASSISTANT_COACH, None, "Bad")
mgr.league.free_agent_staff.append(bad)
check("invalid assignment sanitized to nhl",
      mgr.sign_free_agent_staff(bad, 200_000, 1, assignment="echl") is True
      and bad.assignment == "nhl")

# --- 5. carousel integration: no AHL-coach-as-interim ------------------------
import dressing_room as dr
team2 = SimpleNamespace(team_name="Carousel Club", staff=[
    mk(StaffRole.HEAD_COACH, "nhl", "N"),
    mk(StaffRole.HEAD_COACH, "ahl", "A"),
    mk(StaffRole.ASSISTANT_COACH, "nhl", "Ac"),
])
team2.staff[2].prowess = 60  # below interim bar
nhl = coaches(team2, "nhl")[0]
team2.staff.remove(nhl)  # the firing
check("room lookup empty after NHL firing (AHL coach not interim)",
      dr._room_head_coach(team2) is None)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
