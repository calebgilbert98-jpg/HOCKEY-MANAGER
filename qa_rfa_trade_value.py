# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: RFA trade value (workstream B).

Part 1: unsigned-RFA rights at a genuine signing impasse
(rfa_system.rfa_rights_at_impasse) trade at the risk-adjusted value in
trade_engine.player_trade_value -- exactly RFA_IMPASSE_RIGHTS_MULT of
the non-impasse value, one additive adjustment, no weight retuned.

Part 2: the offer-sheet trade alternative (sign-and-trade door).
  (a) AI-AI: a trade alternative that beats the compensation executes;
      picks/players/cap land on the correct clubs.
  (b) AI offering -> user original: the choice is surfaced via inbox and
      honored both ways (accept = trade, decline = compensation).
  (c) User offering -> AI original: the synchronous choice is honored
      both ways (dialog patched -- headless has no display).
  (d) No trade agreed -> the compensation executes exactly as today.
  (e) An unanswered trade-alternative choice expires to the picks via
      the daily sweep.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(20260929)  # BEFORE any Player construction (uses global RNG)
from datetime import date
from copy import deepcopy

import game_classes as g
from game_classes import PlayerPosition, DraftPick
import rfa_system as rfa_s
import trade_engine as te

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

JULY = date(2027, 7, 15)

# ---------------------------------------------------------------- fixtures

def mkteam(name, cap=110_000_000, user=False):
    t = g.Team(name, "T", "D", "C")
    t.team_name = name
    t.league_name = "National Hockey League"
    t.salary_cap = cap
    t.is_user_team = user
    return t

def mksigned(name, age, ovr, salary, years=3, pos=PlayerPosition.CENTER):
    p = g.Player(first_name=name.split()[0], last_name=name.split()[-1],
                 age=age, primary_position=pos)
    p.overall_rating = lambda _o=ovr: _o
    p.contract.salary = salary
    p.contract.years_remaining = years
    return p

def mkrfa(name, age, ovr, prior_salary):
    p = mksigned(name, age, ovr, prior_salary, years=0)
    p.contract.years_remaining = 0  # expired deal = unsigned RFA
    p.qo_extended = True            # club holds his rights
    return p

def mkpick(year, rnd, team_name):
    return DraftPick(year=year, round=rnd, original_team=team_name,
                     current_team=team_name)

class FakeLeague:
    def __init__(self, teams):
        self.teams = teams
        self.season_year = 2027
        self.rivalries = []
        self.free_agents = []

class FakeApp:
    def __init__(self, user_team, current_date):
        self.user_team = user_team
        self.current_date = current_date
        self.news = []
    def send_email_to_user(self, msg):
        self.user_team.inbox.messages.append(msg)
    def add_news(self, story):
        self.news.append(story)

def give_picks(team, years=(2028, 2029), rounds=(1, 2, 3)):
    for yr in years:
        team.draft_picks[yr] = [mkpick(yr, rnd, team.team_name)
                                for rnd in rounds]

def cap_total(team):
    return sum(te._player_cap_hit(p) for p in team.roster)

def tuned_package_player(offering, comp_picks):
    """Fixture helper: find a signed roster player whose trade value
    lands inside the [comp, 1.25*comp] window, trying ovr 80..86.
    Deterministic under the pinned seed; raises loudly if none fits
    (a fixture problem, not a code problem)."""
    comp_value = sum(te.pick_trade_value(pk) for pk in comp_picks)
    floor, ceiling = comp_value, comp_value * rfa_s.OFFER_SHEET_TRADE_GIVE_UP_MULT
    for ovr in (80, 81, 82, 83, 84, 85, 86):
        cand = mksigned("Package Pete", 27, ovr, 6_000_000)
        v = te.asset_value(cand)
        if floor <= v <= ceiling:
            offering.roster.append(cand)
            print(f"    (fixture: comp_value={comp_value}, "
                  f"candidate ovr={ovr} value={v})")
            return cand
    raise AssertionError(
        f"fixture: no candidate ovr 80..86 landed in [{floor}, {ceiling}]")

# ================================================================ Part 1
print("== Part 1: impasse rights value ==")
imp = mkrfa("Holdout Harry", 24, 82, 3_000_000)
imp.happiness = 20
imp.loyalty = 40          # wants_out -> genuine "won't sign" impasse
check("wants_out holdout is at impasse", rfa_s.rfa_rights_at_impasse(imp))
imp2 = mkrfa("Holdout Harry", 24, 82, 3_000_000)  # same shape, no impasseimp2.happiness = 70
imp2.loyalty = 60
check("happy unsigned RFA is NOT at impasse",
      not rfa_s.rfa_rights_at_impasse(imp2))

# Same-object delta: toggle impasse on one player, nothing else changes.
v_no_impasse = te.player_trade_value(imp2)
imp2.happiness = 20
imp2.loyalty = 40
check("toggled to impasse", rfa_s.rfa_rights_at_impasse(imp2))
v_impasse = te.player_trade_value(imp2)
check("impasse value discounted vs non-impasse", v_impasse < v_no_impasse)
check("discount is exactly RFA_IMPASSE_RIGHTS_MULT (0.75)",
      abs(v_impasse - v_no_impasse * te.RFA_IMPASSE_RIGHTS_MULT) <= 1)
print(f"    (non-impasse {v_no_impasse} -> impasse {v_impasse})")

arb = mkrfa("Arb Andy", 25, 80, 2_500_000)
arb.happiness = 70
arb.loyalty = 60
arb.arbitration_filed = True
check("arbitration-filed RFA is at impasse",
      rfa_s.rfa_rights_at_impasse(arb))
arb.arbitration_filed = False  # same player, impasse off
v_arb_off = te.player_trade_value(arb)
arb.arbitration_filed = True   # impasse on
v_arb_on = te.player_trade_value(arb)
check("arbitration impasse discounted by the same 0.75",
      v_arb_on < v_arb_off
      and abs(v_arb_on - v_arb_off * te.RFA_IMPASSE_RIGHTS_MULT) <= 1)

signed = mksigned("Signed Sam", 24, 82, 5_000_000, years=4)
signed.happiness = 10
signed.loyalty = 10
check("signed player never at impasse (not rights)",
      not rfa_s.rfa_rights_at_impasse(signed))

pend = mkrfa("Pending Pete", 24, 82, 3_000_000)
pend.happiness = 20
pend.loyalty = 40
pend.offer_sheet_pending = True
check("live offer sheet excluded from impasse",
      not rfa_s.rfa_rights_at_impasse(pend))

noqo = mkrfa("Walkon Will", 24, 78, 1_000_000)
noqo.qo_extended = False
noqo.happiness = 20
noqo.loyalty = 40
check("unqualified (no rights held) not at impasse",
      not rfa_s.rfa_rights_at_impasse(noqo))

# ================================================================ Part 2
print("== Part 2a: AI-AI trade alternative executes ==")
AAV, YEARS = 5_000_000, 5  # comp band: 1st + 3rd-round picks
label, bands = rfa_s.offer_sheet_compensation(AAV)
check("5M -> 1st+3rd comp", bands == [1, 3])

def build_ai_ai():
    original = mkteam("Original")
    offering = mkteam("Offering")
    rfa = mkrfa("Young Star", 23, 84, 3_000_000)
    original.roster.append(rfa)
    give_picks(offering)
    give_picks(original)
    comp_picks = [rfa_s._own_pick(offering, 2028, 1),
                  rfa_s._own_pick(offering, 2028, 3)]
    # Package candidate tuned to land inside [comp, 1.25*comp].
    pkg = tuned_package_player(offering, comp_picks)
    for i in range(9):
        offering.roster.append(mksigned(f"Depth D{i}", 29, 74, 2_500_000))
    for i in range(9):
        original.roster.append(mksigned(f"Reg R{i}", 29, 75, 3_000_000))
    league = FakeLeague([original, offering])
    return league, original, offering, rfa, pkg

league, original, offering, rfa, pkg = build_ai_ai()
comp_picks = [rfa_s._own_pick(offering, 2028, 1),
              rfa_s._own_pick(offering, 2028, 3)]
alt = rfa_s.consider_offer_sheet_trade_alternative(
    None, league, offering, original, rfa, AAV, YEARS, comp_picks,
    rng=random.Random(5))
print(f"    comp_value={alt['comp_value']} package_value={alt['package_value']} "
      f"pkg={alt['package_names']}")
check("AI-AI: trade alternative agreed", alt["agreed"] is True)
check("AI-AI: package is the tuned player",
      [p.full_name for p in alt["package"]] == [pkg.full_name])
check("AI-AI: package beats comp, within give-up ceiling",
      alt["package_value"] >= alt["comp_value"] and
      alt["package_value"] <= alt["comp_value"] * 1.25 + 1)

orig_cap_before, off_cap_before = cap_total(original), cap_total(offering)
pkg_hits = te._player_cap_hit(pkg)
rfa_hit_before = te._player_cap_hit(rfa)  # placeholder salary on the unsigned RFA
res = rfa_s.execute_offer_sheet(
    league, offering, original, rfa, AAV, YEARS,
    app=None, rng=random.Random(5), as_of=JULY)
check("AI-AI: execute ok", res["ok"] is True)
check("AI-AI: trade alternative taken", res.get("trade_alternative") is True)
check("AI-AI: RFA signed onto offering club at sheet terms",
      rfa in offering.roster and rfa.contract.salary == AAV
      and rfa.contract.years_remaining == YEARS)
check("AI-AI: package player on original club", pkg in original.roster)
check("AI-AI: comp picks NOT moved (offering keeps them)",
      all(pk.current_team == "Offering" for pk in comp_picks))
check("AI-AI: original cap absorbs package hits (RFA's placeholder hit leaves with him)",
      cap_total(original) == orig_cap_before - rfa_hit_before + pkg_hits)
check("AI-AI: offering cap nets sheet minus shed hits",
      cap_total(offering) == off_cap_before - pkg_hits + AAV)

print("== Part 2b: AI-AI no trade agreed -> compensation as today ==")
league2, original2, offering2, rfa2, _pkg2 = build_ai_ai()
# Only an untouchable superstar: worth far more than the give-up ceiling.
offering2.roster = [p for p in offering2.roster
                    if p.full_name != "Package Pete"]
star = mksigned("Untouchable Ulf", 26, 93, 12_000_000)
offering2.roster.append(star)
alt2 = rfa_s.consider_offer_sheet_trade_alternative(
    None, league2, offering2, original2, rfa2, AAV, YEARS,
    [rfa_s._own_pick(offering2, 2028, 1),
     rfa_s._own_pick(offering2, 2028, 3)], rng=random.Random(5))
check("no package in window -> not agreed", alt2["agreed"] is False)
res2 = rfa_s.execute_offer_sheet(
    league2, offering2, original2, rfa2, AAV, YEARS,
    app=None, rng=random.Random(5), as_of=JULY)
check("compensation executes", res2["ok"] is True
      and not res2.get("trade_alternative"))
check("RFA moved to offering club",
      rfa2 in offering2.roster and rfa2 not in original2.roster)
moved2 = [pk for yr, pool in original2.draft_picks.items() for pk in pool
          if pk.original_team == "Offering"]
check("both comp picks transferred", len(moved2) == 2)
check("RFA signed at sheet terms", rfa2.contract.salary == AAV)

print("== Part 2c: AI offering -> user original: inbox choice honored ==")
def build_ai_user(user_is_original=True):
    user = mkteam("User", user=True)
    ai = mkteam("AIClub")
    rfa = mkrfa("Young Star", 23, 84, 3_000_000)
    if user_is_original:
        original, offering = user, ai
    else:
        original, offering = ai, user
    original.roster.append(rfa)
    give_picks(offering)
    give_picks(original)
    comp_picks = [rfa_s._own_pick(offering, 2028, 1),
                  rfa_s._own_pick(offering, 2028, 3)]
    pkg = tuned_package_player(offering, comp_picks)
    for i in range(9):
        offering.roster.append(mksigned(f"Depth D{i}", 29, 74, 2_500_000))
    for i in range(9):
        original.roster.append(mksigned(f"Reg R{i}", 29, 75, 3_000_000))
    league = FakeLeague([original, offering])
    app = FakeApp(user, JULY)
    return league, app, user, ai, original, offering, rfa, pkg

# --- accept the trade ---
league3, app3, user3, ai3, original3, offering3, rfa3, pkg3 = build_ai_user()
res3 = rfa_s.execute_offer_sheet(
    league3, offering3, original3, rfa3, AAV, YEARS,
    app=app3, rng=random.Random(5), as_of=JULY)
check("user choice deferred (pending_trade_choice)",
      res3.get("pending_trade_choice") is True)
msgs3 = [m for m in app3.user_team.inbox.messages
         if getattr(m, "action_type", None) == "offer_sheet_trade_alt"
         and not getattr(m, "action_done", False)]
check("trade-alt inbox message queued", len(msgs3) == 1)
check("compensation NOT executed while choosing",
      rfa3 in original3.roster and rfa3.contract.years_remaining == 0)
acc = rfa_s.apply_offer_sheet_trade_alt(
    app3, league3, rfa3.id, True, rng=random.Random(5))
check("accept ok", acc["ok"] is True and acc["accepted"] is True)
check("accept: package on user club", pkg3 in user3.roster)
check("accept: RFA signed onto AI offering club",
      rfa3 in offering3.roster and rfa3.contract.salary == AAV)
check("accept: picks unmoved",
      all(pk.current_team == "AIClub"
          for yr, pool in offering3.draft_picks.items() for pk in pool
          if pk.round in (1, 3) and pk.original_team == "AIClub"))
check("accept: news story emitted",
      any("SIGN-AND-TRADE" in n for n in app3.news))
check("accept: message closed", msgs3[0].action_done is True)

# --- decline the trade -> compensation ---
league4, app4, user4, ai4, original4, offering4, rfa4, pkg4 = build_ai_user()
res4 = rfa_s.execute_offer_sheet(
    league4, offering4, original4, rfa4, AAV, YEARS,
    app=app4, rng=random.Random(5), as_of=JULY)
check("decline path: choice queued", res4.get("pending_trade_choice"))
dec = rfa_s.apply_offer_sheet_trade_alt(
    app4, league4, rfa4.id, False, rng=random.Random(5))
check("decline ok", dec["ok"] is True and dec["accepted"] is False)
check("decline: RFA moved to offering club", rfa4 in offering4.roster)
check("decline: package stays put", pkg4 in offering4.roster)
moved4 = [pk for yr, pool in original4.draft_picks.items() for pk in pool
          if pk.original_team == "AIClub"]
check("decline: both comp picks transferred", len(moved4) == 2)
check("decline: RFA signed at sheet terms", rfa4.contract.salary == AAV)

print("== Part 2d: user offering -> AI original: dialog choice honored ==")
league5, app5, user5, ai5, original5, offering5, rfa5, pkg5 = build_ai_user(
    user_is_original=False)
_real_ask = rfa_s._ask_user_offering_trade_alt
try:
    rfa_s._ask_user_offering_trade_alt = lambda *a, **k: True
    res5 = rfa_s.execute_offer_sheet(
        league5, offering5, original5, rfa5, AAV, YEARS,
        app=app5, rng=random.Random(5), as_of=JULY)
    check("dialog accept: trade executed",
          res5["ok"] is True and res5.get("trade_alternative") is True)
    check("dialog accept: package on AI original", pkg5 in original5.roster)
    check("dialog accept: RFA signed onto user club",
          rfa5 in user5.roster and rfa5.contract.salary == AAV)
    check("dialog accept: picks unmoved",
          all(pk.current_team == "User"
              for yr, pool in user5.draft_picks.items() for pk in pool
              if pk.original_team == "User"))

    league6, app6, user6, ai6, original6, offering6, rfa6, pkg6 = \
        build_ai_user(user_is_original=False)
    rfa_s._ask_user_offering_trade_alt = lambda *a, **k: False
    res6 = rfa_s.execute_offer_sheet(
        league6, offering6, original6, rfa6, AAV, YEARS,
        app=app6, rng=random.Random(5), as_of=JULY)
    check("dialog decline: compensation executes",
          res6["ok"] is True and not res6.get("trade_alternative"))
    moved6 = [pk for yr, pool in original6.draft_picks.items()
              for pk in pool if pk.original_team == "User"]
    check("dialog decline: both comp picks transferred", len(moved6) == 2)
    check("dialog decline: RFA signed onto user club",
          rfa6 in user6.roster and rfa6.contract.salary == AAV)
finally:
    rfa_s._ask_user_offering_trade_alt = _real_ask

print("== Part 2e: unanswered choice expires to the picks ==")
league7, app7, user7, ai7, original7, offering7, rfa7, pkg7 = build_ai_user()
res7 = rfa_s.execute_offer_sheet(
    league7, offering7, original7, rfa7, AAV, YEARS,
    app=app7, rng=random.Random(5), as_of=JULY)
check("choice queued", res7.get("pending_trade_choice") is True)
# Jump past the 3-day trade-alt window.
app7.current_date = date(2027, 7, 20)
n = rfa_s.process_offer_sheet_deadlines(app7, league7)
check("sweep resolved the expired choice", n == 1)
moved7 = [pk for yr, pool in original7.draft_picks.items() for pk in pool
          if pk.original_team == "AIClub"]
check("expiry: both comp picks transferred", len(moved7) == 2)
check("expiry: RFA signed onto offering club",
      rfa7 in offering7.roster and rfa7.contract.salary == AAV)
check("expiry: package untouched", pkg7 in offering7.roster)
left = [m for m in app7.user_team.inbox.messages
        if getattr(m, "action_type", None) == "offer_sheet_trade_alt"
        and not getattr(m, "action_done", False)]
check("expiry: message closed", len(left) == 0)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
