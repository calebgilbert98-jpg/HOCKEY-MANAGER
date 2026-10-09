# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: AI contract-extension executor.

Item 5: extension decisions were proposals only. The executor must run
the same rulebook as the user's extension path (league minimum, 20% max,
7-year re-sign max, cap check where the new money REPLACES the old hit),
put the player through the real contract_appeal handshake, respect GM
job security, and feed the market engine like every other signing path.
"""
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, ".")

from game_classes import Player, PlayerPosition, Team, Contract
from ai_team_management import AITeamManager, AIDecision
from salary_cap_system import SalaryCapSystem

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS: {name}")
    else:
        FAIL += 1
        print(f"FAIL: {name}  [{detail}]")
        FAILURES.append(name)


def make_player(name, age, ovr, salary, years_left, **kw):
    # Stable seed: md5, not hash() -- the builtin string hash is salted
    # per process, which made this file's results flip between runs.
    import hashlib as _hl
    random.seed(int(_hl.md5(name.encode()).hexdigest(), 16) % 10_000)
    p = Player(first_name=name, last_name="Ext", age=age,
               primary_position=PlayerPosition.CENTER)
    _ovr = ovr
    p.overall_rating = lambda: float(_ovr)
    p.contract = Contract(salary=salary, years_remaining=years_left)
    p.loyalty = kw.get("loyalty", 70)
    p.happiness = kw.get("happiness", 70)
    p.ambition = kw.get("ambition", "stability")
    p.seasons_played = kw.get("seasons_played", 5)
    p.birthplace = kw.get("birthplace", "Toronto, Canada")
    return p


def make_team(name, players):
    t = Team(name, "Eastern", "Atlantic", "Test")
    t.roster = list(players)
    t.ahl_roster = []
    t.prospects = []
    t.staff = []
    t.wins, t.losses, t.ot_losses = 41, 41, 0
    return t


def make_mgr(team):
    cap = SalaryCapSystem(initial_cap=104_000_000, seed=1)
    league = SimpleNamespace(season_year=2026, salary_cap_system=cap,
                             standings=[], rivalries=[])
    mgr = AITeamManager()
    mgr.set_cap_system(cap, league)
    mgr.initialize_team_strategies([team])
    return mgr, league


def run_full_cycle(team):
    """Evaluation -> execution, the way the weekly tick runs it."""
    mgr, league = make_mgr(team)
    strategy = mgr.team_strategies[team.team_name]
    decs = mgr._evaluate_contract_extensions(team, strategy, date(2026, 11, 1))
    exts = [d for d in decs if d.decision_type == "contract_extension"]
    results = {}
    for d in exts:
        p = d.target_player
        results[p.first_name] = mgr._execute_contract_extension(
            team, d, league)
    return mgr, league, exts, results


# ---------------------------------------------------------------------------
# 1. Evaluation: real expiry detection, wants_out skipped
# ---------------------------------------------------------------------------
expiring = make_player("Expiring", 28, 82, 4_000_000, 1)
mid = make_player("Mid", 28, 80, 3_000_000, 3)
grumpy = make_player("Grumpy", 29, 81, 3_500_000, 1, happiness=20, loyalty=40)
team = make_team("Exts", [expiring, mid, grumpy])
mgr, league = make_mgr(team)
strategy = mgr.team_strategies["Exts"]
decs = mgr._evaluate_contract_extensions(team, strategy, date(2026, 11, 1))
names = {d.target_player.first_name for d in decs
         if d.decision_type == "contract_extension"}
check("expiring player proposed", "Expiring" in names, str(names))
check("mid-deal player not proposed", "Mid" not in names, str(names))
check("wants_out player skipped", "Grumpy" not in names, str(names))

# ---------------------------------------------------------------------------
# 2. Full cycle happy path: loyal core player extended
# ---------------------------------------------------------------------------
p = make_player("Happy", 28, 82, 4_000_000, 1, loyalty=85, happiness=80)
team2 = make_team("Exts", [p])
mgr2, league2, exts2, res2 = run_full_cycle(team2)
check("extension proposed", len(exts2) == 1, str(len(exts2)))
check("extension executed", res2.get("Happy") is True, str(res2))
check("salary rewritten", p.contract.salary != 4_000_000,
      p.contract.salary)
check("term within re-sign max", 1 <= p.contract.years_remaining <= 7,
      p.contract.years_remaining)
check("news queued", any("extension" in s for s in mgr2._pending_news),
      str(mgr2._pending_news[:1]))

# ---------------------------------------------------------------------------
# 3. Term clamp: 8-year proposal becomes 7 (new CBA re-sign max)
# ---------------------------------------------------------------------------
p3 = make_player("Young", 24, 91, 3_000_000, 1, loyalty=85, happiness=85)
team3 = make_team("Exts", [p3])
mgr3, league3 = make_mgr(team3)
ask3 = mgr3._player_ask(p3, league=league3)
d3 = AIDecision(team_name="Exts", decision_type="contract_extension",
                target_player=p3,
                offer_details={"salary": int(ask3 * 0.95), "term": 8},
                priority_score=0.95, reasoning="test",
                timestamp=date(2026, 11, 1))
ok3 = mgr3._execute_contract_extension(team3, d3, league3)
check("8yr clamped, still signs", ok3 is True)
check("term is 7 not 8", p3.contract.years_remaining == 7,
      p3.contract.years_remaining)

# ---------------------------------------------------------------------------
# 4. Cap block: extension that breaks the cap is refused
# ---------------------------------------------------------------------------
fatties = [make_player(f"F{i}", 30, 75, 9_000_000, 4) for i in range(11)]
victim = make_player("Victim", 28, 82, 4_000_000, 1, loyalty=90, happiness=90)
team4 = make_team("Exts", fatties + [victim])
mgr4, league4 = make_mgr(team4)
ask4 = mgr4._player_ask(victim, league=league4)
from salary_cap_system import total_cap_charge as _tcc4
_charge4 = int(_tcc4(team4))
_offer4 = int(ask4 * 1.25)
d4 = AIDecision(team_name="Exts", decision_type="contract_extension",
                target_player=victim,
                offer_details={"salary": _offer4, "term": 5},
                priority_score=0.9, reasoning="test",
                timestamp=date(2026, 11, 1))
# The new money replaces the 4M hit; the offer must break 104M.
check("test setup: would break cap",
      _charge4 - 4_000_000 + _offer4 > 104_000_000,
      f"ask={ask4} charge={_charge4}")
ok4 = mgr4._execute_contract_extension(team4, d4, league4)
check("over-cap extension refused", ok4 is False)
check("contract untouched", victim.contract.salary == 4_000_000
      and victim.contract.years_remaining == 1)

# ---------------------------------------------------------------------------
# 5. Player handshake: floor offer to a star is rejected outright
# ---------------------------------------------------------------------------
star = make_player("Star", 27, 93, 9_000_000, 1, loyalty=50, happiness=55)
team5 = make_team("Exts", [star])
mgr5, league5 = make_mgr(team5)
d5 = AIDecision(team_name="Exts", decision_type="contract_extension",
                target_player=star,
                offer_details={"salary": 850_000, "term": 7},
                priority_score=0.9, reasoning="test",
                timestamp=date(2026, 11, 1))
ok5 = mgr5._execute_contract_extension(team5, d5, league5)
check("insult offer rejected by player", ok5 is False)
check("rejection news queued",
      any("turned down" in s for s in mgr5._pending_news),
      str(mgr5._pending_news[:1]))
check("contract untouched after rejection",
      star.contract.salary == 9_000_000)

# ---------------------------------------------------------------------------
# 6. ELC extension via full cycle: second-contract money, ELC cleared
# ---------------------------------------------------------------------------
kid = make_player("Kid", 21, 85, 900_000, 1, loyalty=85, happiness=85)
kid.contract.entry_level = True
kid.elc_slides_used = 1
team6 = make_team("Exts", [kid])
mgr6, league6, exts6, res6 = run_full_cycle(team6)
check("ELC grad proposed", len(exts6) == 1, str(len(exts6)))
check("ELC extension signs", res6.get("Kid") is True, str(res6))
check("second-contract money", kid.contract.salary > 1_025_000,
      kid.contract.salary)
check("entry_level cleared", kid.contract.entry_level is False)
check("slide state cleared", kid.elc_slides_used == 0)

# ---------------------------------------------------------------------------
# 7. NTC for eligible veterans on long deals
# ---------------------------------------------------------------------------
vet = make_player("Vet", 31, 84, 5_000_000, 1, loyalty=85, happiness=85,
                  seasons_played=9)
team7 = make_team("Exts", [vet])
mgr7, league7 = make_mgr(team7)
ask7 = mgr7._player_ask(vet, league=league7)
d7 = AIDecision(team_name="Exts", decision_type="contract_extension",
                target_player=vet,
                offer_details={"salary": int(ask7 * 0.95), "term": 5},
                priority_score=0.9, reasoning="test",
                timestamp=date(2026, 11, 1))
ok7 = mgr7._execute_contract_extension(team7, d7, league7)
check("veteran extension signs", ok7 is True)
_clause_keys = [k for k in vet.contract.__dict__ if "clause" in k.lower()
                or k.lower() == "ntc"]
check("NTC applied", any(bool(getattr(vet.contract, k, False))
                          for k in _clause_keys),
      str({k: getattr(vet.contract, k) for k in _clause_keys}))

# ---------------------------------------------------------------------------
# 8. Guards: not on roster / already extended / no contract
# ---------------------------------------------------------------------------
outsider = make_player("Outsider", 28, 80, 3_000_000, 1)
team8 = make_team("Exts", [])
mgr8, league8 = make_mgr(team8)
ask8 = mgr8._player_ask(outsider, league=league8)
d8 = AIDecision(team_name="Exts", decision_type="contract_extension",
                target_player=outsider,
                offer_details={"salary": int(ask8), "term": 3},
                priority_score=0.9, reasoning="test",
                timestamp=date(2026, 11, 1))
check("non-roster player refused",
      mgr8._execute_contract_extension(team8, d8, league8) is False)
done = make_player("Done", 28, 80, 4_000_000, 4)
team8b = make_team("Exts", [done])
ask8b = mgr8._player_ask(done, league=league8)
d8b = AIDecision(team_name="Exts", decision_type="contract_extension",
                 target_player=done,
                 offer_details={"salary": int(ask8b), "term": 3},
                 priority_score=0.9, reasoning="test",
                 timestamp=date(2026, 11, 1))
check("non-expiring deal refused",
      mgr8._execute_contract_extension(team8b, d8b, league8) is False)
nocontract = make_player("NoC", 28, 80, 0, 0)
nocontract.contract = None
team8c = make_team("Exts", [nocontract])
d8c = AIDecision(team_name="Exts", decision_type="contract_extension",
                 target_player=nocontract,
                 offer_details={"salary": 4_000_000, "term": 3},
                 priority_score=0.9, reasoning="test",
                 timestamp=date(2026, 11, 1))
check("no-contract player refused",
      mgr8._execute_contract_extension(team8c, d8c, league8) is False)

# ---------------------------------------------------------------------------
# 9. Market feedback: a top-5 AAV star extension registers a comp
# ---------------------------------------------------------------------------
star2 = make_player("Star2", 27, 96, 12_000_000, 1, loyalty=90, happiness=90)
team9 = make_team("Exts", [star2])
mgr9, league9 = make_mgr(team9)
# A top-5 AAV deal (>= 13% of the cap): hand-rolled, the way a bold GM
# keeping his franchise player would. Must move the market like any
# other star signing.
d9 = AIDecision(team_name="Exts", decision_type="contract_extension",
                target_player=star2,
                offer_details={"salary": 14_500_000, "term": 7},
                priority_score=0.95, reasoning="test",
                timestamp=date(2026, 11, 1))
ok9 = mgr9._execute_contract_extension(team9, d9, league9)
n_after = len(league9.salary_cap_system.market_comps)
check("star extension signs", ok9 is True)
check("market-setter comp registered", n_after > 0, f"comps={n_after}")

print(f"\n{40*'='}\nQA ai_extensions: {PASS} passed, {FAIL} failed")
if FAILURES:
    print("FAILURES:", FAILURES)
    sys.exit(1)
