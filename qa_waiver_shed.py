"""QA: waiver wire temporary cap shed -- over-cap clubs can waive to comply.

Covers: immediate full relief on placement; Next-Day blocker clearing;
relief persisting while pending; hit transfer on claim; burial-only charge
for a cleared one-way player assigned to the AHL; continued exemption for
a cleared two-way player in the AHL; full hit returning if the player stays
on the NHL roster; the waivers_shed line in cap_breakdown.
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
    """Mirror of the cleared branch (human club: assigned to AHL)."""
    player.waiver_days = 0
    player.on_waivers = False
    if to_ahl and hasattr(team, "ahl_roster"):
        if player in team.roster:
            team.roster.remove(player)
        team.ahl_roster.append(player)

# -- 1. immediate full relief on placement ------------------------------------
t = mkteam("Over")
t.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M base
check("starts under cap", not scs.is_over_cap(t))
star = mkplayer(8_000_000)
t.roster.append(star)  # $108M
check("over after adding star", scs.is_over_cap(t))
before = scs.total_cap_charge(t)
place_on_waivers(star)
after = scs.total_cap_charge(t)
check("placement sheds full $8M immediately", before - after == 8_000_000)
check("waivers_shed line shows $8M", scs.waiver_shed_charge(t) == 8_000_000)
check("breakdown waivers_shed $8M", scs.cap_breakdown(t)["waivers_shed"] == 8_000_000)

# -- 2. Next Day blocker clears -----------------------------------------------
# Waive a second contract so the club is back under the cap.
role = mkplayer(5_000_000)
t.roster.append(role)  # $113M roster, $8M shed -> $105M charge
check("still over after one waiver", scs.is_over_cap(t))
place_on_waivers(role)  # $113M - $13M shed = $100M charge
check("compliant after shedding enough", not scs.is_over_cap(t))
check("cap_space $4M", scs.cap_space(t) == 4_000_000)

# -- 3. relief persists while pending ------------------------------------------
star.waiver_days = 1  # a day passes, still on the wire
check("shed persists while waiver_days > 0",
      scs.waiver_shed_charge(t) == 13_000_000)

# -- 4. claim transfers the hit -------------------------------------------------
claimer = mkteam("Claimer")
claimer.roster.extend([mkplayer(5_000_000) for _ in range(10)])  # $50M
c_before = scs.total_cap_charge(claimer)
t_before = scs.total_cap_charge(t)
clear_waivers_claimed(star, t, claimer)
check("claimer assumes full $8M hit",
      scs.total_cap_charge(claimer) - c_before == 8_000_000)
check("original club keeps its relief on the claimed player",
      t_before - scs.total_cap_charge(t) == 0)  # star was already shed
check("claimed player off the wire", not star.on_waivers and star.waiver_days == 0)

# -- 5. cleared one-way player -> AHL: burial only ------------------------------
t2 = mkteam("T2")
t2.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M
vet = mkplayer(6_000_000, two_way=False)
t2.roster.append(vet)  # $106M over
place_on_waivers(vet)
check("T2 compliant via shed", not scs.is_over_cap(t2))
clear_waivers_cleared(vet, t2, to_ahl=True)
burial = 6_000_000 - scs.BURY_EXEMPTION
check("cleared one-way AHLer counts burial only",
      scs.total_cap_charge(t2) == 100_000_000 + burial)
check("burial line visible", scs.cap_breakdown(t2)["buried"] == burial)
check("no lingering shed", scs.waiver_shed_charge(t2) == 0)

# -- 6. cleared two-way player -> AHL: fully exempt ------------------------------
t3 = mkteam("T3")
t3.roster.extend([mkplayer(5_000_000) for _ in range(20)])
kid = mkplayer(3_000_000, two_way=True, ahl_salary=150_000)
t3.roster.append(kid)
place_on_waivers(kid)
clear_waivers_cleared(kid, t3, to_ahl=True)
check("cleared two-way AHLer fully exempt",
      scs.total_cap_charge(t3) == 100_000_000)

# -- 7. cleared player staying on NHL roster: full hit returns -------------------
t4 = mkteam("T4")
t4.roster.extend([mkplayer(5_000_000) for _ in range(20)])
hold = mkplayer(6_000_000)
t4.roster.append(hold)
place_on_waivers(hold)
check("shed while pending", scs.total_cap_charge(t4) == 100_000_000)
clear_waivers_cleared(hold, t4, to_ahl=False)  # AI club: stays on roster
check("full hit returns on NHL roster", scs.total_cap_charge(t4) == 106_000_000)
check("club over cap again", scs.is_over_cap(t4))

# -- 8. multi-player placement path ----------------------------------------------
t5 = mkteam("T5")
t5.roster.extend([mkplayer(5_000_000) for _ in range(20)])  # $100M
a, b = mkplayer(8_000_000), mkplayer(6_000_000)  # $114M roster
t5.roster.extend([a, b])
check("T5 over before waivers", scs.is_over_cap(t5))
place_on_waivers(a); place_on_waivers(b)
check("multi shed $14M", scs.waiver_shed_charge(t5) == 14_000_000)
check("multi placement compliant", not scs.is_over_cap(t5))

# -- 9. waiver_days == 0 but flag set: no shed (stale flag safety) ----------------
t6 = mkteam("T6")
stale = mkplayer(9_000_000)
t6.roster.append(stale)
stale.on_waivers = True
stale.waiver_days = 0
check("stale flag sheds nothing", scs.waiver_shed_charge(t6) == 0)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
