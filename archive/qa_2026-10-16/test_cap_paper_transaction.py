#!/usr/bin/env python3
"""Acceptance + adversarial tests for the cap auto-fix Step 3
(demote+recall paper transactions). See DEV_PROCESS.md."""
import os, sys
sys.path.insert(0, os.path.expanduser("~/workspace/hockey-manager"))
os.chdir(os.path.expanduser("~/workspace/hockey-manager"))

from game_classes import Contract, PlayerPosition
from salary_cap_system import (cap_breakdown, compliance_charge,
                               _active_roster_hit, minor_league_cap_charge)
from roster_limits import (can_dress_lineup, dressable_skaters,
                           dressable_goalies)
from auto_resolve import auto_fix_salary_cap, apply_cap_fix_moves

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}"
          + (f" -- {detail}" if detail and not cond else ""))


class P:
    def __init__(self, first, last, age, pos, salary, overall,
                 two_way=False, nmc=False, years_remaining=3,
                 exempt=False, nhl_games=200, pro_seasons=6,
                 injured=False):
        self.first_name = first
        self.last_name = last
        self.age = age
        self.primary_position = pos
        c = Contract()
        c.salary = salary
        c.signing_bonus = 0
        c.years_remaining = years_remaining
        c.two_way = two_way
        c.no_movement_clause = nmc
        self.contract = c
        self._overall = overall
        self.is_injured = injured
        self.on_ir = False
        self.on_waivers = False
        self.emergency_filler = False
        self.ir_status = None
        self.season_ineligible = False
        self.retained_amount = 0
        self.nhl_games_played = nhl_games
        self.pro_seasons_accrued = pro_seasons
        self.first_contract_age = 18
        self.games_remaining_injured = 0
        self.captaincy = None
        if exempt:
            self.first_contract_age = 21
            self.pro_seasons_accrued = 1
            self.nhl_games_played = 30

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def overall_rating(self):
        return self._overall


class T:
    def __init__(self, roster, ahl=None, cap=113_500_000):
        self.roster = roster
        self.ahl_roster = ahl or []
        self.salary_cap = cap
        self.team_name = "Test Club"


def frozen_team(ahl=None, all_risky=False, nmc_idx=None):
    """The day-623 state: $170k over, exactly 18+2 dressable."""
    positions = ([PlayerPosition.CENTER] * 4 + [PlayerPosition.LEFT_WING] * 4
                 + [PlayerPosition.RIGHT_WING] * 4
                 + [PlayerPosition.LEFT_DEFENSE] * 3
                 + [PlayerPosition.RIGHT_DEFENSE] * 3)
    salaries = ([9_000_000, 8_500_000, 8_000_000, 7_500_000]
                + [8_100_000] * 4 + [5_500_000] * 4 + [4_500_000] * 4
                + [3_500_000, 3_000_000])
    overalls = [88, 86, 85, 84, 82, 81, 80, 79, 78, 77, 76, 75,
                74, 73, 72, 71, 70, 69]
    ages = [29, 30, 31, 28, 32, 33, 29, 30, 31, 28, 34, 29,
            30, 35, 31, 32, 28, 33]
    roster = []
    for i, pos in enumerate(positions):
        kw = {}
        if not all_risky and i >= 16:
            kw = dict(exempt=True, two_way=True)
            overalls[i], ages[i] = 74, 21
        if nmc_idx is not None and i == nmc_idx:
            kw["nmc"] = True
        roster.append(P(f"Vet{i}", f"P{i}", ages[i], pos, salaries[i],
                        overalls[i], **kw))
    roster.append(P("Goalie0", "Net", 30, PlayerPosition.GOALIE,
                    900_000, 78))
    roster.append(P("Goalie1", "Net", 31, PlayerPosition.GOALIE,
                    870_000, 74))
    assert sum(_active_roster_hit(p) for p in roster) == 113_670_000
    return T(roster, ahl)


def ahl_callup(name, salary, pos=PlayerPosition.CENTER, two_way=True,
               overall=65, injured=False):
    return P(name, "AHL", 24, pos, salary, overall, two_way=two_way,
             exempt=True, injured=injured)


# --- AC1: the freeze -- $170k over at 18+2, cheap AHL callup available ---
team = frozen_team(ahl=[ahl_callup("Cheap", 800_000),
                        ahl_callup("Cheaper", 775_000),
                        ahl_callup("Pricey", 2_500_000)])
bd = cap_breakdown(team)
over = -bd["space"]
check("AC1a: repro state is $170k over", over == 170_000, f"over={over}")
moves, err = auto_fix_salary_cap(team, over)
pairs = [m for m in moves if m[0] == 'demote_recall']
check("AC1b: planner returns a demote+recall pair",
      len(pairs) == 1 and err is None,
      f"moves={[(k, p[0].full_name if isinstance(p, tuple) else p.full_name, ch) for k, p, ch in moves]} err={err}")
if pairs:
    (p, q), net = pairs[0][1], pairs[0][2]
    check("AC1c: demoted player is waiver-safe (exempt youngster)",
          p.full_name.startswith("Vet1"),
          f"demoted={p.full_name}")
    check("AC1d: recall is the cheapest callup",
          q.full_name == "Cheaper AHL", f"recalled={q.full_name}")
before = compliance_charge(team)
applied, skipped = apply_cap_fix_moves(team, moves)
after = compliance_charge(team)
check("AC1e: predicted net == actual compliance delta",
      before - after == net, f"predicted={net} actual={before - after}")
bd2 = cap_breakdown(team)
check("AC1f: team cap-compliant after apply", not bd2["over_cap"],
      f"total=${bd2['total']:,} cap=${bd2['cap']:,}")
check("AC1g: dressed 18+2 still holds after apply",
      can_dress_lineup(team),
      f"{dressable_skaters(team)}+{dressable_goalies(team)}")
check("AC1h: roster still 20 (one out, one in)", len(team.roster) == 20,
      f"roster={len(team.roster)}")

# --- AC4: honest failure -- empty AHL ---
team2 = frozen_team(ahl=[])
moves2, err2 = auto_fix_salary_cap(team2, 170_000)
check("AC4a: no moves when AHL empty", moves2 == [],
      f"moves={moves2}")
check("AC4b: err names the paper-transaction shortfall",
      err2 is not None and "Paper-transaction" in err2,
      f"err={err2}")

# --- AC5 regression: room above the minimum -> standalone demote (old path) ---
team3 = frozen_team(ahl=[ahl_callup("Cheap", 800_000)])
team3.roster.append(ahl_callup("Extra1", 800_000,
                               pos=PlayerPosition.LEFT_WING))
team3.roster.append(ahl_callup("Extra2", 800_000,
                               pos=PlayerPosition.RIGHT_DEFENSE))
bd3 = cap_breakdown(team3)
moves3, err3 = auto_fix_salary_cap(team3, -bd3["space"])
kinds3 = [k for k, _, _ in moves3]
check("AC5a: with room above minimum, standalone demote (no pair)",
      kinds3 == ['demote'] and err3 is None, f"kinds={kinds3} err={err3}")

# --- AC5 regression: unsigned phantom overage -> release path ---
team4 = frozen_team(ahl=[ahl_callup("Cheap", 800_000)])
ghost = P("Ghost", "Expired", 33, PlayerPosition.CENTER, 1_000_000, 70,
          years_remaining=0)
team4.roster.append(ghost)
bd4 = cap_breakdown(team4)
moves4, err4 = auto_fix_salary_cap(team4, -bd4["space"])
kinds4 = [k for k, _, _ in moves4]
check("AC5b: unsigned player released first (phantom overage path)",
      kinds4 and kinds4[0] == 'release', f"kinds={kinds4} err={err4}")

# --- AC6: biggest net first (fewest moves; Step 2 philosophy) ---
team5 = frozen_team(ahl=[ahl_callup("Cheap", 800_000),
                         ahl_callup("Cheaper", 775_000)])
moves5, err5 = auto_fix_salary_cap(team5, 170_000)
pairs5 = [m for m in moves5 if m[0] == 'demote_recall']
if pairs5:
    (p5, q5), net5 = pairs5[0][1], pairs5[0][2]
    # biggest net: demote the $3.5M exempt youngster (Vet16),
    # recall the cheapest body ($775k) -> net 2,725,000
    check("AC6: biggest net first",
          p5.full_name == "Vet16 P16" and q5.full_name == "Cheaper AHL"
          and net5 == 2_725_000,
          f"demoted={p5.full_name} recalled={q5.full_name} net={net5}")
else:
    check("AC6: biggest net first", False, "no pair found")

# --- AC2: NMC-only safe candidate -> no pair; NMC never moved ---
team6 = frozen_team(ahl=[ahl_callup("Cheap", 800_000)], all_risky=True,
                    nmc_idx=10)
moves6, err6 = auto_fix_salary_cap(team6, 170_000)
moved_names = []
for k, pl, _ in moves6:
    if isinstance(pl, (tuple, list)):
        moved_names += [x.full_name for x in pl]
    else:
        moved_names.append(pl.full_name)
check("AC2a: NMC player never moved",
      not any("Vet10" in n for n in moved_names),
      f"moved={moved_names}")
# (old low-value vets at idx 13/15/17 are still safe & pairable)

# --- A1 adversarial: AHL callup MORE expensive than any shed ---
teamA1 = frozen_team(ahl=[ahl_callup("Expensive", 4_000_000, overall=80)])
movesA1, errA1 = auto_fix_salary_cap(teamA1, 170_000)
check("A1: no pair when callup costs more than the shed",
      movesA1 == [] and errA1 is not None and "Paper-transaction" in errA1,
      f"moves={movesA1} err={errA1}")

# --- A2 adversarial: AHL has only a goalie, skater slot needed ---
teamA2 = frozen_team(ahl=[ahl_callup("GoalieOnly", 775_000,
                                     pos=PlayerPosition.GOALIE)])
movesA2, errA2 = auto_fix_salary_cap(teamA2, 170_000)
# demote candidates are skaters (exempt youngsters); goalie recall can't fill
check("A2: no cross-position pair (skater out needs skater in)",
      all(not (isinstance(pl, tuple) and pl[0].primary_position !=
               pl[1].primary_position) for _, pl, _ in movesA2),
      f"moves={movesA2}")
check("A2b: err is honest", errA2 is not None and "Paper-transaction" in errA2,
      f"err={errA2}")

# --- A3 adversarial: $1 overage ---
teamA3 = frozen_team(ahl=[ahl_callup("Cheap", 800_000)])
movesA3, errA3 = auto_fix_salary_cap(teamA3, 1)
check("A3: $1 overage gets a pair", any(k == 'demote_recall' for k, _, _ in movesA3)
      and errA3 is None, f"moves={movesA3} err={errA3}")

# --- A4 adversarial: one-way AHLer with minor-league charge -- exact math ---
oneway = P("OneWay", "AHL", 26, PlayerPosition.CENTER, 2_000_000, 68,
           two_way=False, exempt=True)  # minor charge = 2M - 1.225M = 775k
teamA4 = frozen_team(ahl=[oneway])
movesA4, errA4 = auto_fix_salary_cap(teamA4, 170_000)
pairsA4 = [m for m in movesA4 if m[0] == 'demote_recall']
if pairsA4:
    (pa4, qa4), neta4 = pairsA4[0][1], pairsA4[0][2]
    exp_net = (int(_active_roster_hit(pa4) or 0)
               - int(minor_league_cap_charge(pa4) or 0)
               - (int(_active_roster_hit(qa4) or 0)
                  - int(minor_league_cap_charge(qa4) or 0)))
    check("A4a: predicted net uses exact recall delta", neta4 == exp_net,
          f"net={neta4} expected={exp_net}")
    before4 = compliance_charge(teamA4)
    apply_cap_fix_moves(teamA4, movesA4)
    after4 = compliance_charge(teamA4)
    check("A4b: actual compliance delta == predicted net",
          before4 - after4 == neta4, f"actual={before4 - after4} pred={neta4}")
    check("A4c: compliant after", not cap_breakdown(teamA4)["over_cap"])
else:
    check("A4: pair with one-way callup", False, f"moves={movesA4} err={errA4}")

# --- A5 adversarial: big overage ($5M) at the minimum -> multiple pairs ---
teamA5 = frozen_team(ahl=[ahl_callup("C1", 800_000),
                          ahl_callup("C2", 800_000),
                          ahl_callup("C3", 800_000)])
movesA5, errA5 = auto_fix_salary_cap(teamA5, 5_000_000)
pairsA5 = [m for m in movesA5 if m[0] == 'demote_recall']
tot5 = sum(ch for _, _, ch in movesA5)
check("A5a: multiple pairs cover a $5M overage",
      len(pairsA5) >= 2 and tot5 >= 5_000_000 and errA5 is None,
      f"pairs={len(pairsA5)} total={tot5} err={errA5}")
applied5, skipped5 = apply_cap_fix_moves(teamA5, movesA5)
check("A5b: all applied, none skipped",
      len(skipped5) == 0, f"skipped={skipped5}")
check("A5c: dress minimum holds after multi-pair apply",
      can_dress_lineup(teamA5),
      f"{dressable_skaters(teamA5)}+{dressable_goalies(teamA5)}")
check("A5d: compliant after multi-pair apply",
      not cap_breakdown(teamA5)["over_cap"])

# --- A6 adversarial: injured AHL callup excluded ---
teamA6 = frozen_team(ahl=[ahl_callup("Hurt", 775_000, injured=True)])
movesA6, errA6 = auto_fix_salary_cap(teamA6, 170_000)
check("A6: injured callup not used",
      movesA6 == [] and errA6 is not None, f"moves={movesA6}")

# --- A7: all-risky roster + cheap AHL -> old vets still safe & pairable ---
teamA7 = frozen_team(ahl=[ahl_callup("Cheap", 800_000)], all_risky=True)
movesA7, errA7 = auto_fix_salary_cap(teamA7, 170_000)
pairsA7 = [m for m in movesA7 if m[0] == 'demote_recall']
if pairsA7:
    (pa7, qa7), _ = pairsA7[0][1], pairsA7[0][2]
    from auto_resolve import _player_value
    from waiver_logic import is_waiver_eligible
    check("A7: demoted player is waiver-safe (value<65 or exempt)",
          (not is_waiver_eligible(pa7)) or _player_value(pa7) < 65,
          f"demoted={pa7.full_name} value={_player_value(pa7):.1f}")
else:
    check("A7: pair found on all-risky roster", False, f"err={errA7}")

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
