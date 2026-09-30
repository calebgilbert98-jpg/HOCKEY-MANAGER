"""QA: Item 6 -- RFA offer sheets complete top to bottom.

Exercises all four combos end to end:
  1. offer -> AI match      (July-pass branch)
  2. offer -> AI no-match   (July-pass branch)
  3. offer -> user match    (inbox decision)
  4. offer -> user no-match (inbox decision)
plus:
  5. the 7-day match window (deadline stamped, expiry auto-resolves as a
     decline, no sheet left pending after the window)
  6. the user's own sheet matched by an AI club (offer_sheet_ui path)

Asserts for every combo: player ends on the correct team, contract terms
equal the sheet terms, cap registration happened (recorded via the cap
system's register_signing), compensation picks transferred on non-match,
no pending sheet left after the window.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
random.seed(20260929)  # pinned BEFORE any generation

from datetime import date

import game_classes as g
from game_classes import PlayerPosition, DraftPick
import rfa_system as rfa
from salary_cap_system import SalaryCapSystem

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


# ---------------------------------------------------------------- fixtures

def mkteam(name):
    t = g.Team(name, "T", "D", "C")
    t.team_name = name
    t.league_name = "National Hockey League"
    t.salary_cap = 110_000_000
    return t


def mkrfa(first, last, age, ovr, prior_salary):
    p = g.Player(first_name=first, last_name=last, age=age,
                 primary_position=PlayerPosition.CENTER)
    p.overall_rating = lambda _o=ovr: _o
    p.contract.salary = prior_salary
    p.contract.years_remaining = 0  # expired deal = unsigned RFA
    return p


def mkpick(year, rnd, team_name):
    return DraftPick(year=year, round=rnd, original_team=team_name,
                     current_team=team_name)


class FakeLeague:
    def __init__(self, teams):
        self.teams = teams
        self.season_year = 2028
        self.rivalries = []
        self.free_agents = []
        self.salary_cap_system = SalaryCapSystem()


class FakeApp:
    def __init__(self, user_team, start_date):
        self.user_team = user_team
        self.current_date = start_date
        self.news = []

    def send_email_to_user(self, msg):
        self.user_team.inbox.messages.append(msg)

    def add_news(self, story):
        self.news.append(story)


def cap_recorder(league):
    """Wrap register_signing: record every call, still call through."""
    calls = []
    cap_sys = league.salary_cap_system
    real = cap_sys.register_signing

    def rec(*a, **k):
        calls.append(a)
        return real(*a, **k)

    cap_sys.register_signing = rec
    return calls


class StubRng:
    """Deterministic rng: always holds out (July pass), first choice."""

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]

    def shuffle(self, x):
        pass


def july_harness(monkey_match):
    """Run the real July pass with the offer-sheet dice rigged.

    monkey_match: True -> ai_match_decision always matches;
                  False -> never matches.
    Returns (league, orig, offering, player, calls, summary, exp_aav,
    exp_picks).
    """
    orig = mkteam("Originals")
    offering = mkteam("Poachers")
    player = mkrfa("Core", "Kid", 23, 85, 4_000_000)
    orig.roster.append(player)
    for yr in range(2029, 2036):
        offering.draft_picks[yr] = [mkpick(yr, rnd, "Poachers")
                                    for rnd in (1, 2, 3)]
    # Expected sheet terms, computed on the pristine player exactly the
    # way the July pass computes them (StubRng.random() == 0.0).
    exp_aav = int(rfa._market_value(player) * 1.05)
    _exp_label, exp_picks = rfa.offer_sheet_compensation(exp_aav)
    league = FakeLeague([orig, offering])
    calls = cap_recorder(league)

    import player_decision as _pd
    saved = {
        "match": rfa.ai_match_decision,
        "rate": rfa.OFFER_SHEET_BASE_RATE,
        "score": rfa.ai_offer_sheet_target_score,
        "qual": rfa._ai_qualify_decision,
        "budget": rfa._spending_budget,
        "accepts": _pd.player_accepts_offer_sheet,
    }
    try:
        rfa.ai_match_decision = lambda *a: monkey_match
        rfa.OFFER_SHEET_BASE_RATE = 1.0
        rfa.ai_offer_sheet_target_score = lambda *a: 1.0
        rfa._ai_qualify_decision = lambda *a: True
        rfa._spending_budget = lambda *a, **k: 50_000_000
        _pd.player_accepts_offer_sheet = (
            lambda *a, **k: (True, 0.9, ["he wants the money"]))
        summary = rfa.process_rfa_offseason(league, app=None,
                                            rng=StubRng())
    finally:
        rfa.ai_match_decision = saved["match"]
        rfa.OFFER_SHEET_BASE_RATE = saved["rate"]
        rfa.ai_offer_sheet_target_score = saved["score"]
        rfa._ai_qualify_decision = saved["qual"]
        rfa._spending_budget = saved["budget"]
        _pd.player_accepts_offer_sheet = saved["accepts"]
    return league, orig, offering, player, calls, summary, exp_aav, exp_picks


def user_sheet_setup():
    """League + app for the user-decision combos; returns everything."""
    user = mkteam("User")
    offering = mkteam("Poachers")
    player = mkrfa("Young", "Star", 23, 86, 3_500_000)
    user.roster.append(player)
    for yr in (2029, 2030):
        offering.draft_picks[yr] = [mkpick(yr, rnd, "Poachers")
                                    for rnd in (1, 2, 3)]
    league = FakeLeague([user, offering])
    calls = cap_recorder(league)
    app = FakeApp(user, date(2028, 7, 3))
    aav, years = 8_000_000, 4
    label, _picks = rfa.offer_sheet_compensation(aav)
    rfa._queue_offer_sheet_match(app, league, offering, user, player,
                                 aav, years, label)
    return league, user, offering, player, calls, app, aav, years, label


def pending_msg(app, player):
    for m in app.user_team.inbox.messages:
        if (getattr(m, "action_type", None) == "offer_sheet_match"
                and (m.action_data or {}).get("player_id") == player.id):
            return m
    return None


print("== combo 1: offer -> AI match (July pass) ==")
league, orig, offering, player, calls, summary, exp_aav, exp_picks = \
    july_harness(True)
check("player stays with original club",
      player in orig.roster and player not in offering.roster)
check("signed AT the sheet terms",
      int(player.contract.salary) == exp_aav
      and int(player.contract.years_remaining) == 1)
check("cap registration happened on the match",
      len(calls) == 1 and int(calls[0][1]) == exp_aav)
check("no-trade flag set on match",
      getattr(player, "offer_sheet_match_no_trade_until", None) == 2029)
check("pending flag cleared after match",
      not bool(getattr(player, "offer_sheet_pending", False)))
check("matched player skips arbitration",
      not bool(getattr(player, "arbitration_filed", False))
      and not rfa.contract_expired(player))
check("no compensation moves on a match",
      not any(pk.original_team == "Poachers"
              for yr, pool in orig.draft_picks.items() for pk in pool))

print("== combo 2: offer -> AI no-match (July pass) ==")
(league2, orig2, offering2, player2, calls2, summary2,
 exp_aav2, exp_picks2) = july_harness(False)
check("offer sheet executed", summary2["offer_sheets"] == 1)
check("player moves to offering team",
      player2 in offering2.roster and player2 not in orig2.roster)
check("signed AT the sheet terms on the new club",
      int(player2.contract.salary) == exp_aav2
      and int(player2.contract.years_remaining) == 1)
check("cap registration happened on the poach",
      len(calls2) == 1 and int(calls2[0][1]) == exp_aav2)
moved = [pk for yr, pool in orig2.draft_picks.items() for pk in pool
         if pk.original_team == "Poachers"]
check(f"all compensation picks transferred ({sorted(exp_picks2)})",
      sorted(pk.round for pk in moved) == sorted(exp_picks2)
      and len(moved) == len(exp_picks2))
check("pending flag cleared after poach",
      not bool(getattr(player2, "offer_sheet_pending", False)))

print("== combo 3: offer -> user match (inbox) ==")
(league3, user3, offering3, player3, calls3, app3,
 aav3, years3, label3) = user_sheet_setup()
msg3 = pending_msg(app3, player3)
check("sheet is pending while undecided",
      msg3 is not None
      and bool(getattr(player3, "offer_sheet_pending", False)))
check("7-day deadline stamped",
      (msg3.action_data or {}).get("match_deadline") == "2028-07-10")
check("pending sheet blocks arbitration filing",
      not rfa.arbitration_eligible(player3))
res3 = rfa.apply_offer_sheet_match(app3, league3, player3.id, True)
check("match accepted", res3.get("ok") and res3.get("matched") is True)
check("player stays with user club",
      player3 in user3.roster and player3 not in offering3.roster)
check("user match signs AT the sheet terms",
      int(player3.contract.salary) == aav3
      and int(player3.contract.years_remaining) == years3)
check("cap registration happened on user match",
      len(calls3) == 1 and int(calls3[0][1]) == aav3)
check("no-trade flag set on user match",
      getattr(player3, "offer_sheet_match_no_trade_until", None) == 2029)
check("message closed, pending cleared",
      bool(msg3.action_done)
      and not bool(getattr(player3, "offer_sheet_pending", False)))
check("no compensation moves on a user match",
      not any(pk.original_team == "Poachers"
              for yr, pool in user3.draft_picks.items() for pk in pool))

print("== combo 4: offer -> user no-match (inbox) ==")
(league4, user4, offering4, player4, calls4, app4,
 aav4, years4, label4) = user_sheet_setup()
msg4 = pending_msg(app4, player4)
res4 = rfa.apply_offer_sheet_match(app4, league4, player4.id, False)
check("decline accepted", res4.get("ok") and res4.get("matched") is False)
check("player moves to offering team",
      player4 in offering4.roster and player4 not in user4.roster)
check("signed AT the sheet terms on the new club",
      int(player4.contract.salary) == aav4
      and int(player4.contract.years_remaining) == years4)
check("cap registration happened on user decline",
      len(calls4) == 1 and int(calls4[0][1]) == aav4)
moved4 = [pk for yr, pool in user4.draft_picks.items() for pk in pool
          if pk.original_team == "Poachers"]
check("compensation picks transferred (1st+2nd+3rd for 8M)",
      len(moved4) == 3
      and sorted(pk.round for pk in moved4) == [1, 2, 3])
check("message closed, pending cleared",
      bool(msg4.action_done)
      and not bool(getattr(player4, "offer_sheet_pending", False)))

print("== combo 5: 7-day window enforcement ==")
(league5, user5, offering5, player5, calls5, app5,
 aav5, years5, label5) = user_sheet_setup()
msg5 = pending_msg(app5, player5)
app5.current_date = date(2028, 7, 8)  # deadline day: not yet expired
n = rfa.process_offer_sheet_deadlines(app5, league5)
check("sweep leaves an in-window sheet alone",
      n == 0 and not bool(msg5.action_done)
      and bool(getattr(player5, "offer_sheet_pending", False)))
app5.current_date = date(2028, 7, 11)  # past the Jul 10 deadline
n = rfa.process_offer_sheet_deadlines(app5, league5)
check("sweep resolves the expired sheet", n == 1)
check("expired sheet -> player goes to offering club",
      player5 in offering5.roster and player5 not in user5.roster)
check("expired sheet signs at the sheet terms",
      int(player5.contract.salary) == aav5
      and int(player5.contract.years_remaining) == years5)
check("cap registered on expiry resolution", len(calls5) == 1)
moved5 = [pk for yr, pool in user5.draft_picks.items() for pk in pool
          if pk.original_team == "Poachers"]
check("compensation transferred on expiry", len(moved5) == 3)
check("no sheet left pending after the window",
      bool(msg5.action_done)
      and not bool(getattr(player5, "offer_sheet_pending", False)))

print("== combo 5b: clicking match after expiry ==")
(league6, user6, offering6, player6, calls6, app6,
 aav6, years6, label6) = user_sheet_setup()
msg6 = pending_msg(app6, player6)
app6.current_date = date(2028, 7, 20)  # well past the deadline
res6 = rfa.apply_offer_sheet_match(app6, league6, player6.id, True)
check("late match click -> treated as decline",
      res6.get("ok") and res6.get("matched") is False
      and res6.get("expired") is True)
check("late click still moves the player at sheet terms",
      player6 in offering6.roster
      and int(player6.contract.salary) == aav6)
check("late click closes the message", bool(msg6.action_done))

print("== combo 6: user's own sheet matched by an AI club (UI path) ==")
user7 = mkteam("User")
ai_orig = mkteam("Originals")
target = mkrfa("Target", "Man", 24, 84, 3_000_000)
ai_orig.roster.append(target)
league7 = FakeLeague([user7, ai_orig])
calls7 = cap_recorder(league7)
mres = rfa.apply_offer_sheet_matched(league7, user7, ai_orig, target,
                                     7_000_000, 5, app=None)
check("AI match of user sheet: ok", mres.get("ok") is True)
check("player stays with original club at sheet terms",
      target in ai_orig.roster
      and int(target.contract.salary) == 7_000_000
      and int(target.contract.years_remaining) == 5)
check("cap registration happened", len(calls7) == 1)
check("no-trade flag set",
      getattr(target, "offer_sheet_match_no_trade_until", None) == 2029)

print("== combo 7: failed sheet moves nothing (atomic compensation) ==")
user8 = mkteam("User")
poor = mkteam("CashStrapped")
victim = mkrfa("Victim", "Zero", 24, 84, 3_000_000)
user8.roster.append(victim)
# Only TWO years of picks: not enough for the four-1sts tier at 12M AAV.
for yr in (2029, 2030):
    poor.draft_picks[yr] = [mkpick(yr, rnd, "CashStrapped")
                            for rnd in (1, 2, 3)]
league8 = FakeLeague([user8, poor])
calls8 = cap_recorder(league8)
res8 = rfa.execute_offer_sheet(league8, poor, user8, victim, 12_000_000, 5,
                               app=None, rng=random.Random(3),
                               as_of=date(2028, 7, 15))
check("sheet fails without the picks", res8.get("ok") is False
      and res8.get("reason") == "missing_own_picks")
check("no partial compensation left behind",
      not any(pk.original_team == "CashStrapped"
              for yr, pool in user8.draft_picks.items() for pk in pool))
check("player not moved on failure",
      victim in user8.roster and victim not in poor.roster)
check("no cap registration on failure", len(calls8) == 0)
check("player still unsigned after failure",
      rfa.contract_expired(victim))

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:", failed)
    sys.exit(1)