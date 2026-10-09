# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: waiver wire cap accounting (Wave B D45 -- the shed is gone).

Covers: a player on the wire counts his FULL hit (no shed on placement,
no relief while pending); waiver_shed_charge retired to 0; hit transfer
on claim (claimer assumes the full hit, original club drops it);
burial-only charge for a cleared one-way player assigned to the AHL;
full exemption for a cleared two-way player in the AHL; full hit for a
cleared player staying on the NHL roster; compliance_charge counts a
pending wire at its expected post-clearing (burial) charge so the
day-advance blocker doesn't soft-lock a corrective waive; the
waivers_shed line in cap_breakdown reads 0.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(20260928)
import game_classes as g
from game_classes import PlayerPosition
import salary_cap_system as scs

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=104_000_000):
    t = g.Team(name, "T", "D", "C"); t.salary_cap = cap; return t

def mkplayer(salary, two_way=False, ahl_salary=100_000):
    p = g.Player(first_name="A", last_name="B", age=27,
                 primary_position=PlayerPosition.CENTER)
    p.contract.salary = salary
    p.contract.two_way = two_way
    p.contract.ahl_salary = ahl_salary
    return p

def place_on_waivers(player):
    """Mirror of WaiversView.place_on_waivers / waive-and-assign."""
    player.on_waivers = True
    player.waiver_days = 2

def clear_waivers_claimed(player, orig_team, claim_team):
    """Mirror of the claim branch in the daily waiver processing."""
    if player in orig_team.roster:
        orig_team.roster.remove(player)
    elif player in getattr(orig_team, "ahl_roster", []):
        orig_team.ahl_roster.remove(player)
    claim_team.add_player(player)
    player.team_name = claim_team.team_name
    player.on_waivers = False
    player.waiver_days = 0

def clear_waivers_cleared(player, team, to_ahl=True):
    """Mirror of the cleared branch (auto-assigned to AHL)."""
    player.waiver_days = 0
    player.on_waivers = False
    if to_ahl and hasattr(team, "ahl_roster"):
        if player in team.roster:
            team.roster.remove(player)
        team.ahl_roster.append(player)

# -- 1. no shed on placement (D45: the loophole is dead) ------------------------
t = mkteam("Over")
t.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M base
check("starts under cap", not scs.is_over_cap(t))
star = mkplayer(8_000_000)
t.roster.append(star)  # $108M
check("over after adding star", scs.is_over_cap(t))
before = scs.total_cap_charge(t)
place_on_waivers(star)
after = scs.total_cap_charge(t)
check("placement sheds nothing (full $8M still counts)", before - after == 0)
check("still over cap while on the wire", scs.is_over_cap(t))
check("waiver_shed_charge retired to 0", scs.waiver_shed_charge(t) == 0)
check("breakdown waivers_shed 0",
      scs.cap_breakdown(t)["waivers_shed"] == 0)

# -- 2. no relief while pending --------------------------------------------------
star.waiver_days = 1  # a day passes, still on the wire
check("no relief while pending",
      scs.total_cap_charge(t) == 108_000_000)
check("cap_space still negative", scs.cap_space(t) == -4_000_000)

# -- 3. claim transfers the FULL hit ----------------------------------------------
claimer = mkteam("Claimer")
claimer.roster.extend([mkplayer(5_000_000) for _ in range(10)])  # $50M
c_before = scs.total_cap_charge(claimer)
t_before = scs.total_cap_charge(t)
clear_waivers_claimed(star, t, claimer)
check("claimer assumes full $8M hit",
      scs.total_cap_charge(claimer) - c_before == 8_000_000)
check("original club drops the full $8M on claim",
      t_before - scs.total_cap_charge(t) == 8_000_000)
check("claimed player off the wire", not star.on_waivers and star.waiver_days == 0)

# -- 4. cleared one-way player -> AHL: burial only ---------------------------------
t2 = mkteam("T2")
t2.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M
vet = mkplayer(6_000_000, two_way=False)
t2.roster.append(vet)  # $106M over
place_on_waivers(vet)
check("T2 over cap while vet on wire (no shed)", scs.is_over_cap(t2))
clear_waivers_cleared(vet, t2, to_ahl=True)
# New CBA: burial exemption floats with the league minimum
# (1.15M + 850k = 2M in 2026-27, up from 1.925M).
burial = 6_000_000 - scs.burial_exemption()
check("cleared one-way AHLer counts burial only",
      scs.total_cap_charge(t2) == 100_000_000 + burial)
check("burial line visible", scs.cap_breakdown(t2)["buried"] == burial)
check("no lingering shed", scs.waiver_shed_charge(t2) == 0)

# -- 5. cleared two-way player -> AHL: fully exempt ----------------------------------
t3 = mkteam("T3")
t3.roster.extend([mkplayer(5_000_000) for _ in range(20)])
kid = mkplayer(3_000_000, two_way=True, ahl_salary=150_000)
t3.roster.append(kid)
place_on_waivers(kid)
check("two-way on wire still counts full $3M (no shed)",
      scs.total_cap_charge(t3) == 103_000_000)
clear_waivers_cleared(kid, t3, to_ahl=True)
check("cleared two-way AHLer fully exempt",
      scs.total_cap_charge(t3) == 100_000_000)

# -- 6. cleared player staying on NHL roster: full hit --------------------------------
t4 = mkteam("T4")
t4.roster.extend([mkplayer(5_000_000) for _ in range(20)])
hold = mkplayer(6_000_000)
t4.roster.append(hold)
place_on_waivers(hold)
check("full hit on wire", scs.total_cap_charge(t4) == 106_000_000)
clear_waivers_cleared(hold, t4, to_ahl=False)  # AI club: stays on roster
check("full hit on NHL roster", scs.total_cap_charge(t4) == 106_000_000)
check("club over cap", scs.is_over_cap(t4))

# -- 7. compliance_charge: pending wire at expected burial charge ---------------------
t7 = mkteam("T7")
t7.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M
big = mkplayer(6_000_000, two_way=False)
t7.roster.append(big)  # $106M, $2M over
place_on_waivers(big)
check("real charge still $106M on the wire",
      scs.total_cap_charge(t7) == 106_000_000)
expected = 100_000_000 + (6_000_000 - scs.burial_exemption())
check("compliance_charge counts expected burial charge",
      scs.compliance_charge(t7) == expected)
check("compliance_charge at cap (waive resolves it)",
      scs.compliance_charge(t7) <= 104_000_000)
two = mkplayer(4_000_000, two_way=True)
t7b = mkteam("T7b")
t7b.roster.extend([mkplayer(5_000_000) for _ in range(20)])
t7b.roster.append(two)
extra = mkplayer(2_000_000)
t7b.roster.append(extra)  # $106M over
place_on_waivers(two)
check("two-way wire: compliance_charge drops the full $4M (exempt)",
      scs.compliance_charge(t7b) == 102_000_000)

# -- 8. stale flag safety: waiver_days == 0 but flag set -------------------------------
t8 = mkteam("T8")
stale = mkplayer(9_000_000)
t8.roster.append(stale)
stale.on_waivers = True
stale.waiver_days = 0
check("stale flag: full hit counts", scs.total_cap_charge(t8) == 9_000_000)
check("stale flag: no shed line", scs.waiver_shed_charge(t8) == 0)

# -- 9. floor keys in cap_breakdown (D46) ----------------------------------------------
t9 = mkteam("T9")
t9.roster.extend([mkplayer(2_500_000) for _ in range(20)])  # $50M
bd9 = scs.cap_breakdown(t9)
check("floor key $78M", bd9["floor"] == 78_000_000)
check("under_floor True", bd9["under_floor"] is True)
check("floor_space -$28M", bd9["floor_space"] == -28_000_000)
check("floor_space() helper agrees", scs.floor_space(t9) == -28_000_000)
t9b = mkteam("T9b")
t9b.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M
bd9b = scs.cap_breakdown(t9b)
check("compliant club not under floor", bd9b["under_floor"] is False)
check("floor_space +$22M", bd9b["floor_space"] == 22_000_000)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
