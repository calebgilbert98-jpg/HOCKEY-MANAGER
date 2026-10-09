#!/usr/bin/env python3
"""qa_ir_ltir.py -- QA for the IR/LTIR system (Muck 2026-10-02).

Verifies: IR placement, 23-man roster exemption, cap counting (IR counts),
LTIR relief pool, LTIR activation cap check, AI auto-placement, return flow,
old-save defaults, never-raises on garbage.

Test-infra: see ~/AGENTS.md (pt.py isolation). Run standalone per file.
"""
import sys, os
sys.path.insert(0, '/home/hatch/workspace/playthrough')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# pt.py isolation per AGENTS.md
import pt  # noqa: F401  (import for path/chdir side effects)
sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')
for _m in [m for m in list(sys.modules) if m in (
        'ir_system', 'game_classes', 'roster_limits', 'salary_cap_system')]:
    del sys.modules[_m]

from datetime import date, timedelta
from types import SimpleNamespace

import ir_system as irs

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def make_player(pid, salary=5_000_000, injured=False, games_left=0):
    c = SimpleNamespace(salary=salary, two_way=False, years_remaining=3)
    p = SimpleNamespace(
        id=pid, full_name=f"Test Player {pid}",
        first_name="Test", last_name=f"Player{pid}",
        contract=c, is_injured=injured,
        games_remaining_injured=games_left,
        injury_type="Knee" if injured else "None",
        ir_status="None", ir_placed_date="",
        on_waivers=False, emergency_filler=False,
    )
    return p


def make_team(players, cap=88_000_000):
    return SimpleNamespace(
        roster=list(players), ahl_roster=[], prospects=[],
        salary_cap=cap, retained_salary=[],
        team_name="Test Team")


print("== IR eligibility ==")
p_healthy = make_player(1)
ok, _ = irs.eligible_for_ir(p_healthy)
check("healthy player not IR-eligible", not ok)

p_hurt = make_player(2, injured=True, games_left=5)
ok, _ = irs.eligible_for_ir(p_hurt)
check("injured player IR-eligible", ok)
ok, _ = irs.eligible_for_ltir(p_hurt)
check("5-game injury not LTIR-eligible", not ok)

p_long = make_player(3, injured=True, games_left=15)
ok, _ = irs.eligible_for_ltir(p_long)
check("15-game injury LTIR-eligible", ok)

print("== IR placement ==")
team = make_team([p_hurt, p_long, p_healthy])
today = date(2026, 10, 2)
ok, reason = irs.place_on_ir(team, p_hurt, today)
check("place on IR succeeds", ok)
check("ir_status set to IR", irs.ir_status_of(p_hurt) == "IR")
check("ir_placed_date stamped", p_hurt.ir_placed_date == "2026-10-02")
# Not on NHL roster -> blocked
outsider = make_player(99, injured=True, games_left=5)
ok, _ = irs.place_on_ir(team, outsider, today)
check("non-roster player blocked from IR", not ok)

print("== 23-man exemption ==")
import roster_limits as rl
# active_roster_count needs has_active_contract; give players contracts
for p in team.roster:
    pass
n_before = rl.active_roster_count(team)
check("IR player excluded from 23-man count",
      n_before == 2)  # p_hurt on IR, 2 others count

print("== LTIR placement + relief pool ==")
ok, _ = irs.place_on_ltir(team, p_long, today)
check("place on LTIR succeeds", ok)
relief = irs.ltir_relief(team)
check("LTIR relief = player cap hit", relief == 5_000_000)
check("effective ceiling = cap + relief",
      irs.effective_cap_ceiling(team) == 88_000_000 + 5_000_000)

print("== IR activation (7-day minimum) ==")
# p_hurt healed instantly but placed today -> blocked by 7-day rule
p_hurt.is_injured = False
p_hurt.games_remaining_injured = 0
ok, reason = irs.activate_player(team, p_hurt, today)
check("IR activation blocked before 7 days", not ok)
check("reason mentions 7 days", "7" in reason)
later = today + timedelta(days=8)
ok, reason = irs.activate_player(team, p_hurt, later)
check("IR activation succeeds after 7 days", ok)
check("ir_status cleared", irs.ir_status_of(p_hurt) == "None")

print("== LTIR activation cap check ==")
# p_long healed; team has no other charges, so activation is compliant
p_long.is_injured = False
p_long.games_remaining_injured = 0
ok, reason = irs.can_activate_from_ltir(team, p_long)
check("LTIR activation compliant when room exists", ok)
# Now clog the cap: add an expensive player so there's no room
p_exp = make_player(4, salary=88_000_000)
team.roster.append(p_exp)
ok, reason = irs.can_activate_from_ltir(team, p_long)
# charge = 5M (p_long) + 5M (p_healthy) + 88M (p_exp) = 98M
# pool after removing p_long = 0 -> ceiling 88M -> not compliant
check("LTIR activation blocked when over cap", not ok)
check("reason mentions cap room", "cap room" in reason.lower())
team.roster.remove(p_exp)

print("== AI management ==")
p_ai_hurt = make_player(10, injured=True, games_left=20)
p_ai_short = make_player(11, injured=True, games_left=4)
p_ai_healed_ir = make_player(12)
p_ai_healed_ir.ir_status = "IR"
p_ai_healed_ir.ir_placed_date = (today - timedelta(days=10)).isoformat()
ai_team = make_team([p_ai_hurt, p_ai_short, p_ai_healed_ir])
done = irs.ai_manage_ir(ai_team, today)
check("AI places long injury on LTIR", done["ltir_placed"] == 1)
check("AI places short injury on IR", done["ir_placed"] == 1)
check("AI activates healed IR player", done["activated"] == 1)
check("AI LTIR status correct",
      irs.ir_status_of(p_ai_hurt) == "LTIR")
check("AI IR status correct",
      irs.ir_status_of(p_ai_short) == "IR")

print("== Old-save defaults / never-raises ==")
bare = SimpleNamespace()  # no ir fields at all
check("missing ir_status defaults to None",
      irs.ir_status_of(bare) == "None")
check("eligible_for_ir on garbage -> False",
      irs.eligible_for_ir(bare)[0] is False)
check("ltir_relief on garbage -> 0", irs.ltir_relief(bare) == 0)
check("ai_manage_ir on garbage -> zeros",
      irs.ai_manage_ir(bare) == {"ltir_placed": 0, "ir_placed": 0,
                                 "activated": 0})
check("ir_summary_line on empty team", irs.ir_summary_line(bare) == "")
check("days_on_ir garbage -> 0", irs.days_on_ir(bare, today) == 0)

print("== Summary line ==")
line = irs.ir_summary_line(ai_team)
check("summary mentions LTIR", "LTIR" in line)
check("summary mentions IR", "IR" in line)

print(f"\n{ PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
