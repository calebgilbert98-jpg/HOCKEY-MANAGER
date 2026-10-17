#!/usr/bin/env python3
"""Integration test: Step 3 with REAL game_classes Player/Team objects."""
import os, sys
sys.path.insert(0, os.path.expanduser("~/workspace/hockey-manager"))
os.chdir(os.path.expanduser("~/workspace/hockey-manager"))

from game_classes import Player, Team, Contract, PlayerPosition
from salary_cap_system import cap_breakdown, compliance_charge
from roster_limits import can_dress_lineup
from auto_resolve import auto_fix_salary_cap, apply_cap_fix_moves

SKATER_ATTRS = ["skating", "shooting", "shooting_accuracy", "shooting_power",
                "passing", "passing_accuracy", "offensive_awareness",
                "defensive_awareness", "checking", "strength", "faceoffs",
                "puck_handling", "agility", "balance", "stamina"]
GOALIE_ATTRS = ["goaltending", "reflexes", "positioning", "rebound_control",
                "puck_handling", "glove_hand", "stick_side",
                "breakaway_skill", "confidence", "focus", "composure"]


def mk(first, pos, salary, overall, age=29, two_way=False, exempt=False,
       years_remaining=3, nmc=False, injured=False):
    p = Player(first_name=first, last_name="Test", age=age,
               primary_position=pos)
    for a in (GOALIE_ATTRS if pos == PlayerPosition.GOALIE else SKATER_ATTRS):
        try:
            setattr(p, a, overall)
        except Exception:
            pass
    c = Contract()
    c.salary = salary
    c.years_remaining = years_remaining
    c.two_way = two_way
    c.no_movement_clause = nmc
    p.contract = c
    p.is_injured = injured
    if exempt:
        p.first_contract_age = 21
        p.pro_seasons_accrued = 1
        p.nhl_games_played = 30
    else:
        p.first_contract_age = 18
        p.pro_seasons_accrued = 6
        p.nhl_games_played = 300
    return p


positions = ([PlayerPosition.CENTER] * 4 + [PlayerPosition.LEFT_WING] * 4
             + [PlayerPosition.RIGHT_WING] * 4
             + [PlayerPosition.LEFT_DEFENSE] * 3
             + [PlayerPosition.RIGHT_DEFENSE] * 3)
salaries = ([9_000_000, 8_500_000, 8_000_000, 7_500_000]
            + [8_100_000] * 4 + [5_500_000] * 4 + [4_500_000] * 4
            + [3_500_000, 3_000_000])
roster = []
for i, pos in enumerate(positions):
    kw = dict(two_way=True, exempt=True, age=21) if i >= 16 else {}
    roster.append(mk(f"Vet{i}", pos, salaries[i], 74 if i >= 16 else 80,
                     **kw))
roster.append(mk("G0", PlayerPosition.GOALIE, 900_000, 78))
roster.append(mk("G1", PlayerPosition.GOALIE, 870_000, 74))

ahl = [mk("Cheap", PlayerPosition.CENTER, 800_000, 65, age=24,
          two_way=True, exempt=True),
       mk("Cheaper", PlayerPosition.LEFT_WING, 775_000, 64, age=23,
          two_way=True, exempt=True)]

team = Team(team_name="Integers", city="Test", division="D", conference="C")
team.roster = roster
team.ahl_roster = ahl
team.salary_cap = 113_500_000

bd = cap_breakdown(team)
over = -bd["space"]
print(f"real-player state: total=${bd['total']:,} cap=${bd['cap']:,} "
      f"over=${over:,}")
assert over == 170_000, over

moves, err = auto_fix_salary_cap(team, over)
print("moves:", [(k, p[0].full_name if isinstance(p, tuple) else p.full_name, ch)
                 for k, p, ch in moves])
print("err:", err)
assert err is None and any(k == "demote_recall" for k, _, _ in moves), \
    "expected a demote+recall pair"

before = compliance_charge(team)
applied, skipped = apply_cap_fix_moves(team, moves)
after = compliance_charge(team)
print(f"applied={[(p.full_name, k, ch) for p, k, ch in applied]} "
      f"skipped={skipped}")
print(f"compliance: ${before:,} -> ${after:,}")
assert not skipped, skipped
bd2 = cap_breakdown(team)
assert not bd2["over_cap"], bd2
assert can_dress_lineup(team), "dressed minimum broken"
assert len(team.roster) == 20, len(team.roster)
print("INTEGRATION PASS: real Player/Team, $170k over -> paper transaction -> "
      "compliant, 18+2 dressed")
