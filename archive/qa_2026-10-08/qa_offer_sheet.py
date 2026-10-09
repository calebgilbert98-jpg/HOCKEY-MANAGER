# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: offer sheets (BUG-020) -- the user-facing flow and its engine chain.

Covers: is_rfa identification; compensation bands; own-pick availability;
the decline path (player moves, ALL compensation picks transfer, incl. the
empty-pool receiver fix in _transfer_pick); the match path (core young
star matched at fair money); compensation_pick_status never promising
the same pick twice; the offer-sheet window gating (Jul 1 - Dec 1).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
from datetime import date
import game_classes as g
from game_classes import PlayerPosition, DraftPick
import rfa_system as rfa_s
from offer_sheet_ui import compensation_pick_status

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=95_000_000):
    t = g.Team(name, "T", "D", "C")
    t.team_name = name
    t.league_name = "National Hockey League"
    t.salary_cap = cap
    return t

def mkrfa(name, age, ovr, prior_salary):
    p = g.Player(first_name=name.split()[0], last_name=name.split()[-1],
                 age=age, primary_position=PlayerPosition.CENTER)
    p.overall_rating = lambda _o=ovr: _o
    p.contract.salary = prior_salary
    p.contract.years_remaining = 0  # expired deal = unsigned RFA
    p.nhl_games_played = 120
    return p

def mkpick(year, rnd, team):
    return DraftPick(year=year, round=rnd, original_team=team,
                     current_team=team)

class FakeLeague:
    def __init__(self, teams, user):
        self.teams = teams; self.user_team = user; self.season_year = 2027
        self.rivalries = []

rfa = mkrfa("Young Star", 23, 84, 3_000_000)
rival = mkteam("Rival"); rival.roster.append(rfa)
user = mkteam("User")
for i in range(20):
    pl = mkrfa(f"Skater{i} Pro", 28, 78, 4_000_000)
    pl.contract.years_remaining = 3
    user.roster.append(pl)
for yr in (2028, 2029):
    user.draft_picks[yr] = [mkpick(yr, rnd, "User") for rnd in (1, 2, 3)]
league = FakeLeague([rival, user], user)

# --- identification & valuation -----------------------------------------
check("unsigned non-UFA is RFA", rfa_s.is_rfa(rfa))
check("market estimate positive", rfa_s.market_value_estimate(rfa) > 0)
label, picks = rfa_s.offer_sheet_compensation(7_500_000)
check("7.5M -> 1st+2nd+3rd", picks == [1, 2, 3])
label, picks = rfa_s.offer_sheet_compensation(10_500_000)
check("10.5M -> two 1sts+2nd+3rd", picks == [1, 1, 2, 3])
check("own pick found", rfa_s.own_pick_available(user, 2028, 1) is not None)
check("missing round -> None",
      rfa_s.own_pick_available(user, 2028, 4) is None)

# --- preview never double-promises ---------------------------------------
lines, missing = compensation_pick_status(user, 2028, [1, 1, 2, 3])
check("two 1sts need two years of picks",
      sum(1 for ok, _ in lines if ok) == 4 and not missing)
lines2, missing2 = compensation_pick_status(user, 2028, [1, 1, 1, 1])
check("four 1sts from two years -> two missing",
      missing2 == [1, 1])

# --- decline path ---------------------------------------------------------
rfa2 = mkrfa("Mid RFA", 25, 75, 2_800_000)
rival.roster.append(rfa2)
mkt2 = rfa_s.market_value_estimate(rfa2)
aav, years = int(mkt2 * 1.6), 5
label2, picks2 = rfa_s.offer_sheet_compensation(aav)
check("absurd overpay -> club takes picks",
      rfa_s.ai_match_decision(rival, rfa2, aav, label2) is False)
res = rfa_s.execute_offer_sheet(league, user, rival, rfa2, aav, years,
                                app=None, rng=random.Random(1),
                                as_of=date(2027, 7, 15))
check("execute ok", res["ok"])
check("player moved to offering team",
      rfa2 in user.roster and rfa2 not in rival.roster)
moved = [pk for yr, pool in rival.draft_picks.items() for pk in pool
         if pk.original_team == "User"]
check("all compensation picks transferred", len(moved) == len(picks2))

# --- match path ------------------------------------------------------------
rfa3 = mkrfa("Core Kid", 22, 85, 4_000_000)
rival.roster.append(rfa3)
mkt3 = rfa_s.market_value_estimate(rfa3)
aav3 = int(mkt3 * 1.1)
label3, _ = rfa_s.offer_sheet_compensation(aav3)
check("core young star matched at fair money",
      rfa_s.ai_match_decision(rival, rfa3, aav3, label3) is True)

# --- window -----------------------------------------------------------------
import transaction_windows as tw
ok_jul, _ = tw.check_window("offer_sheet", date(2027, 7, 15))
ok_jun, _ = tw.check_window("offer_sheet", date(2027, 6, 20))
ok_jan, _ = tw.check_window("offer_sheet", date(2028, 1, 10))
check("window open in July", ok_jul)
check("window closed in June", not ok_jun)
check("window closed in January", not ok_jan)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
