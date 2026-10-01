# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: salary floor (Wave B D46) -- $78.0M against the $104M cap.

Covers: the AI never trades ITSELF under the floor (ai_consider_trade
rejects, with a plain-spoken reason); AI auto-compliance signs a
sub-floor club back up the same day on 1-year deals
(_enforce_salary_floor); the user day-advance gate
(_floor_compliance_blocker) blocks under-floor days and clears compliant
ones; the cap blocker stays waiver-aware (D45): a pending corrective
waive that resolves the overage is not a hard block, but one that
doesn't resolve it still blocks.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from types import SimpleNamespace
from datetime import date
import random
random.seed(20261001)

from game_classes import Player, Team, Contract, DraftPick, PlayerPosition
import salary_cap_system as scs
import trade_engine as te

passed, failed = [], []
def check(label, cond, detail=""):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}" + (f" -- {detail}" if detail and not cond else ""))

SKATER_ATTRS = ["skating", "shooting", "passing", "stickhandling",
                "off_the_puck", "hitting", "shot_blocking", "faceoffs",
                "discipline", "durability", "leadership"]

def mk_player(fn, ln, salary, ovr=80, pos=PlayerPosition.CENTER):
    p = Player(fn, ln, 27, pos)
    for a in SKATER_ATTRS:
        if hasattr(p, a):
            setattr(p, a, ovr)
    p.contract = Contract(salary=salary, years_remaining=2)
    p.morale = 70
    return p

def mk_team(name, salaries):
    t = Team(name, "C", "Metro", "East")
    t.salary_cap = 104_000_000
    t.roster = [mk_player(f"P{i}", f"Last{i}", s) for i, s in enumerate(salaries)]
    t.gm_profile = SimpleNamespace(aggression=0.5)
    return t

def mk_pick(team_name, year=2027, rnd=2):
    return DraftPick(year=year, round=rnd, original_team=team_name,
                     current_team=team_name)

# -- 1. AI never trades itself under the floor ---------------------------------------
# Evaluator (AI seller) at $80M: dumping a $5M man for a pick -> $75M < floor.
seller = mk_team("FloorSeller", [5_000_000] * 16)  # $80M
assert scs.total_cap_charge(seller) == 80_000_000
dump = seller.roster[0]
resp = te.ai_consider_trade(seller, [mk_pick("FloorSeller")], [dump],
                            user_team=mk_team("Buyer", [6_000_000] * 16))
check("floor-breach deal rejected", resp.decision == "reject", resp.decision)
check("rejection names the floor", "floor" in resp.message.lower(), resp.message)

# Control: same dump from an $90M club -> $85M, no floor involvement.
rich = mk_team("RichSeller", [5_000_000] * 18)  # $90M
resp2 = te.ai_consider_trade(rich, [mk_pick("RichSeller")], [rich.roster[0]],
                             user_team=mk_team("Buyer2", [6_000_000] * 16))
check("compliant dump not a floor reject",
      "floor" not in resp2.message.lower(), f"{resp2.decision}: {resp2.message}")

# A club ALREADY under the floor isn't floor-blocked from trading -- the
# floor gate only polices the downward crossing; its compliance is owned
# by the day gate (user) / auto-compliance (AI).
sub = mk_team("SubFloor", [5_000_000] * 14)  # $70M
resp3 = te.ai_consider_trade(sub, [mk_pick("SubFloor")], [sub.roster[0]],
                             user_team=mk_team("Buyer3", [6_000_000] * 16))
check("sub-floor club not floor-blocked from trading",
      "floor" not in resp3.message.lower(), f"{resp3.decision}: {resp3.message}")

# -- 2. AI auto-compliance: _enforce_salary_floor ------------------------------------
from ai_team_management import AITeamManager
mgr = AITeamManager()
poor = mk_team("PoorClub", [5_000_000] * 14)  # $70M, $8M under the floor
fas = [mk_player(f"FA{i}", "Agent", 925_000) for i in range(6)]
league = SimpleNamespace(teams=[poor], free_agents=list(fas),
                         season_year=2026, rivalries=[])
mgr._league_ref = league
mgr.team_strategies = {poor.team_name: SimpleNamespace(
    budget_limit=104_000_000, position_needs=[PlayerPosition.CENTER])}
# Ask machinery stubbed: every FA asks $3M on a 1-year deal.
mgr._player_ask = lambda p, league=None: 3_000_000
made = mgr._enforce_salary_floor(poor, league.free_agents, date(2026, 10, 15))
check("floor signings made", made == 3, f"made={made}")
check("club back at/above the floor",
      scs.total_cap_charge(poor) >= 78_000_000,
      f"${scs.total_cap_charge(poor)/1e6:.1f}M")
check("signed players left the FA pool", len(league.free_agents) == 3)
check("signed players on the roster", len(poor.roster) == 17)
_new = [p for p in poor.roster if p not in poor.roster[:14]]
check("1-year floor deals",
      all(int(getattr(getattr(p, 'contract', None), 'years_remaining', 0) or 0) == 1
          for p in poor.roster if getattr(p, 'full_name', '').startswith('FA')),
      "terms")
# Control: compliant club untouched.
fine = mk_team("FineClub", [5_000_000] * 18)  # $90M
league2 = SimpleNamespace(teams=[fine], free_agents=list(fas),
                          season_year=2026, rivalries=[])
mgr._league_ref = league2
mgr.team_strategies[fine.team_name] = SimpleNamespace(
    budget_limit=104_000_000, position_needs=[PlayerPosition.CENTER])
made2 = mgr._enforce_salary_floor(fine, league2.free_agents, date(2026, 10, 15))
check("compliant club: no signings", made2 == 0, f"made={made2}")
check("FA pool untouched", len(league2.free_agents) == 6)

# -- 3. user day-advance gates ---------------------------------------------------------
import main as _main
_G = _main.HockeyManagerGUI

under = mk_team("UnderClub", [2_500_000] * 20)  # $50M
fake = SimpleNamespace(user_team=under,
                       open_free_agency_window=lambda: None,
                       open_trade_window=lambda: None)
fb = _G._floor_compliance_blocker(fake)
check("under-floor day blocked", isinstance(fb, dict) and fb["id"] == "salary_floor",
      str(fb)[:60])
check("blocker names the shortfall", "$28.00M" in fb["detail"], fb["detail"][:80])
ok_team = mk_team("OkClub", [5_000_000] * 18)  # $90M
fake_ok = SimpleNamespace(user_team=ok_team,
                          open_free_agency_window=lambda: None,
                          open_trade_window=lambda: None)
check("compliant day not floor-blocked",
      _G._floor_compliance_blocker(fake_ok) is None)

# -- 4. cap blocker stays waiver-aware (D45) ---------------------------------------------
# $100M + $6M one-way on the wire: real charge $106M (over), but the
# pending wire resolves it via burial ($104M) -> NO hard block.
t7 = mk_team("WireClub", [5_000_000] * 20)
big = mk_player("Big", "Deal", 6_000_000)
t7.roster.append(big)
big.on_waivers = True
big.waiver_days = 2
fake7 = SimpleNamespace(user_team=t7, open_trade_window=lambda: None,
                        open_free_agency_window=lambda: None)
check("corrective waive: no hard block",
      _G._cap_compliance_blocker(fake7) is None,
      f"compliance=${scs.compliance_charge(t7)/1e6:.1f}M")
# $100M + $8M one-way on the wire: burial only relieves $2M -> $106M,
# still over -> the blocker still fires.
t8 = mk_team("WireClub2", [5_000_000] * 20)
big8 = mk_player("Big", "Deal8", 8_000_000)
t8.roster.append(big8)
big8.on_waivers = True
big8.waiver_days = 2
fake8 = SimpleNamespace(user_team=t8, open_trade_window=lambda: None,
                        open_free_agency_window=lambda: None)
cb8 = _G._cap_compliance_blocker(fake8)
check("unresolved overage still blocks",
      isinstance(cb8, dict) and cb8["id"] == "salary_cap", str(cb8)[:60])

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
