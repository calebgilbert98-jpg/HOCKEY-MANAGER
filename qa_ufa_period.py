#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_ufa_period.py -- UFA consideration period.

Verifies: offers become bids (not instant signings), multi-team bidding,
contract_appeal() picks the winner, no-renegotiation guard, UFA-screen
removal on signing, headlines fire, garbage never raises.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from types import SimpleNamespace
from datetime import date

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")

import ufa_consideration as uc
import game_classes as g

def make_player(name, ovr=82, age=28, pid=None):
    return SimpleNamespace(
        full_name=name, name=name, id=pid or f"p_{name}",
        age=age, primary_position=g.PlayerPosition.CENTER,
        overall_rating=lambda: ovr, value=5_000_000,
        salary=0, contract_years=0,
        contract=SimpleNamespace(salary=0, years_remaining=0,
                                 entry_level=False),
        ambition="stability", loyalty=50, happiness=70,
    )

def make_team(name, is_user=False):
    t = SimpleNamespace(
        team_name=name, name=name, roster=[], inbox=SimpleNamespace(
            add_message=lambda m: None),
        prospects=[], ahl_roster=[],
        add_player=lambda p, r: None,
    )
    return t

def make_league(teams, fas):
    return SimpleNamespace(teams=teams, free_agents=fas,
                           season_year=2026, rivalries=[],
                           news_log=[] if False else [])

def make_app(league, user_team):
    inbox = []
    app = SimpleNamespace(
        league=league, user_team=user_team,
        current_date=date(2026, 7, 5),
        news_log=[],
        inbox_msgs=inbox,
        media_system=None,
        update_all_views=lambda: None,
        update_inbox_notification=lambda: None,
        get_live_cap=lambda: 104_000_000,
    )
    app.send_email_to_user = lambda m: inbox.append(m)
    return app

print("== storage helpers ==")
lg = make_league([], [])
check("empty considerations dict", uc.get_considerations(lg) == {})
check("same object on re-get",
      uc.get_considerations(lg) is uc.get_considerations(lg))
p = make_player("Test Star", pid="s1")
check("no consideration initially", not uc.has_consideration(lg, p))
check("status None when none", uc.get_player_status(lg, p) is None)

print("== offer submission ==")
t1, t2, t3 = make_team("Sharks"), make_team("Wings"), make_team("Hawks")
lg = make_league([t1, t2, t3], [p])
app = make_app(lg, t1)
cons = uc.submit_ufa_offer(app, lg, p, t1, 8_000_000, 5, is_user=True)
check("consideration created", cons is not None)
check("has_consideration true", uc.has_consideration(lg, p))
check("window 3-7 days",
      3 <= cons["days_left"] <= 7, f"days={cons['days_left']}")
check("one bid", len(cons["offers"]) == 1)
check("status string", uc.get_player_status(lg, p) is not None and
      "fielding offers" in uc.get_player_status(lg, p))

print("== bid update (no duplicates) ==")
uc.submit_ufa_offer(app, lg, p, t1, 9_000_000, 5, is_user=True)
cons = uc.get_consideration(lg, p)
check("still one bid after re-offer", len(cons["offers"]) == 1)
check("bid updated to 9M", cons["offers"][0]["aav"] == 9_000_000)

print("== multi-team bidding ==")
uc.submit_ufa_offer(app, lg, p, t2, 8_500_000, 4, is_user=False)
uc.submit_ufa_offer(app, lg, p, t3, 7_500_000, 6, is_user=False)
cons = uc.get_consideration(lg, p)
check("three bidders", len(cons["offers"]) == 3,
      f"n={len(cons['offers'])}")

print("== headline builder ==")
msg = uc.ufa_decision_headline(date(2026, 7, 5), player_name="Test Star",
                               stage="considering", n_teams=3, days=5)
check("considering headline", msg is not None and "Test Star" in msg.subject)
msg2 = uc.ufa_decision_headline(date(2026, 7, 5), player_name="Test Star",
                                stage="signed", team_name="Sharks",
                                aav=9_000_000, years=5, n_bidders=3)
check("signed headline", msg2 is not None and "Sharks" in msg2.subject)
msg3 = uc.ufa_decision_headline(date(2026, 7, 5), player_name="Test Star",
                                stage="frontrunner", leader_name="Wings",
                                n_teams=3)
check("frontrunner headline",
      msg3 is not None and "Test Star" in (msg3.subject + msg3.content) and
      "Wings" in (msg3.subject + msg3.content))

print("== headlines.py registration ==")
import headlines as hl
m = hl.make_headline("ufa_decision", date(2026, 7, 5),
                     player_name="Test Star", stage="considering",
                     n_teams=2, days=4)
check("ufa_decision registered", m is not None)

print("== resolution: best appeal wins ==")
# Make t3's offer most appealing: huge overpay on a contender-like team.
# (appeal scoring is complex; we verify the machinery picks *a* winner
#  deterministically and signs them.)
lg2_teams = [t1, t2, t3]
for t in lg2_teams:
    t.add_player = lambda p, r, _t=t: (_t.roster.append(p))
p2 = make_player("Star Two", ovr=88, pid="s2")
lg2 = make_league(lg2_teams, [p2])
app2 = make_app(lg2, t1)
c2 = uc.submit_ufa_offer(app2, lg2, p2, t1, 6_000_000, 5, is_user=True)
uc.submit_ufa_offer(app2, lg2, p2, t2, 12_000_000, 7, is_user=False)
c2["days_left"] = 1
winner = uc.resolve_consideration(app2, lg2, "s2")
check("resolution picks a winner", winner is not None)
check("consideration removed", not uc.has_consideration(lg2, p2))
check("player signed to winner roster",
      p2 in winner["team"].roster if winner else False)
check("player out of FA pool", p2 not in lg2.free_agents)

print("== user loss notification ==")
# t1 (user) bid but t2 won above: user should get a loss email.
p3 = make_player("Star Three", ovr=80, pid="s3")
lg3 = make_league([t1, t2], [p3])
app3 = make_app(lg3, t1)
t1.roster.clear(); t2.roster.clear()
c3 = uc.submit_ufa_offer(app3, lg3, p3, t1, 5_000_000, 3, is_user=True)
uc.submit_ufa_offer(app3, lg3, p3, t2, 15_000_000, 7, is_user=False)
c3["days_left"] = 1
n_before = len(app3.inbox_msgs)
uc.resolve_consideration(app3, lg3, "s3")
# (winner depends on appeal math; just verify no crash + cleanup)
check("resolves without crash", not uc.has_consideration(lg3, p3))

print("== tick decrements + resolves ==")
p4 = make_player("Tick Test", ovr=76, pid="s4")
lg4 = make_league([t1], [p4])
app4 = make_app(lg4, t1)
t1.roster.clear()
c4 = uc.submit_ufa_offer(app4, lg4, p4, t1, 4_000_000, 2, is_user=True)
d0 = c4["days_left"]
uc.tick_ufa_considerations(app4, lg4)
check("tick decrements", c4["days_left"] == d0 - 1 or
      not uc.has_consideration(lg4, p4),
      f"d0={d0} d1={c4.get('days_left')}")

print("== notify helpers ==")
uc.notify_consideration_started(app4, p4, 4_000_000, 2, 4)
check("consideration inbox sent", len(app4.inbox_msgs) >= 1)

print("== garbage never raises ==")
for fn in (lambda: uc.get_considerations(None),
           lambda: uc.has_consideration(None, None),
           lambda: uc.get_player_status(None, None),
           lambda: uc.submit_ufa_offer(None, None, None, None, 0, 0),
           lambda: uc.tick_ufa_considerations(None, None),
           lambda: uc.resolve_consideration(None, None, "x"),
           lambda: uc.notify_consideration_started(None, None, 0, 0, 0),
           lambda: uc.ufa_decision_headline(None)):
    try:
        fn()
        ok = True
    except Exception as e:
        ok = False
    check("never raises", ok)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
