"""QA: offer-sheet match no-trade year wired into the trade engine.

Real NHL rule: a club that matches an offer sheet can't trade the player
for one year. rfa_system.apply_offer_sheet_matched sets
player.offer_sheet_match_no_trade_until = season_year + 1 on every match
path (AI July pass, user inbox decision); trade_engine.trade_vetoes vetoes
a flagged player while the flag is live, and execute_trade's both-direction
preflight hard-blocks the deal (the canonical choke point for SP/AI/MP and
draft-day paths). Consent-ask flows are out of scope -- will_waive_ntc
refuses outright for flagged players.

Run: python3 qa_offer_sheet_notrade.py (from the repo root)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(20260929)  # pinned BEFORE any generation
import pickle
from types import SimpleNamespace

import game_classes as g
from game_classes import PlayerPosition
import trade_engine as te
import rfa_system as rfa

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=104_000_000):
    t = g.Team(name, "T", "D", "C")
    t.salary_cap = cap
    return t

def mkplayer(salary, ovr=75, age=27, name="Test Player"):
    p = g.Player(first_name=name.split()[0],
                 last_name=" ".join(name.split()[1:]) or "X",
                 age=age, primary_position=PlayerPosition.CENTER)
    p.contract.salary = salary
    for attr in ("skating", "shooting", "passing", "checking", "defense",
                 "hockey_iq", "strength", "speed"):
        try:
            setattr(p, attr, ovr)
        except Exception:
            pass
    return p

def fill(team, n=19, salary=4_000_000):
    for _ in range(n):
        team.roster.append(mkplayer(salary))

CAP = 104_000_000

# ---------------------------------------------------------------- 1. match
print("== match sets the flag ==")
orig = mkteam("Originals")
off = mkteam("Offerers")
league26 = SimpleNamespace(season_year=2026, rivalries=[],
                           teams=[orig, off], salary_cap_system=None)
star = mkplayer(4_000_000, ovr=82, age=24, name="Matched Star")
orig.roster.append(star)
res = rfa.apply_offer_sheet_matched(league26, off, orig, star,
                                    6_500_000, 3)
check("match returns ok", res.get("ok") and res.get("matched"))
check("flag = season_year + 1",
      getattr(star, "offer_sheet_match_no_trade_until", 0) == 2027)
check("matched player signs at sheet terms",
      star.contract.salary == 6_500_000 and star.contract.years_remaining == 3)

# ---------------------------------------------------------------- 2. vetoes
print("== trade_vetoes while live ==")
v = te.trade_vetoes(orig, off, [star], league26)
check("one veto entry", len(v) == 1)
check("clause kind is OFFER-SHEET-NO-TRADE",
      v and v[0]["clause"] == "OFFER-SHEET-NO-TRADE")
check("detail names the expiry year",
      v and "2027" in v[0]["detail"])
check("veto entry carries the player", v and v[0]["player"] is star)
v_none = te.trade_vetoes(orig, off, [star], None)
check("fail-closed without a league", len(v_none) == 1)
league27 = SimpleNamespace(season_year=2027, rivalries=[],
                           teams=[orig, off], salary_cap_system=None)
v_exp = te.trade_vetoes(orig, off, [star], league27)
check("no veto once the flag expires", v_exp == [])

# ------------------------------------------------- 3. execution, both sides
print("== execute_trade blocks (user path) ==")
u = mkteam("User"); p = mkteam("Partner")
u_star = mkplayer(6_500_000, ovr=82, age=24, name="User Star")
u_star.offer_sheet_match_no_trade_until = 2027  # as apply_offer_sheet_matched sets
u.roster.append(u_star); fill(u)
p_piece = mkplayer(6_500_000, ovr=80, age=26, name="Partner Piece")
p.roster.append(p_piece); fill(p)
league = SimpleNamespace(season_year=2026, rivalries=[],
                         teams=[u, p], salary_cap_system=None)
tr = te.execute_trade(u, p, [u_star], [p_piece], league=league)
check("user trading away a matched player BLOCKS",
      tr.summary.startswith("BLOCKED"))
check("blocked deal moves nothing (star stays)",
      u_star in u.roster and u_star not in p.roster)
check("blocked deal moves nothing (piece stays)",
      p_piece in p.roster and p_piece not in u.roster)
check("block message names the protection",
      "offer-sheet" in tr.summary.lower())

print("== execute_trade blocks (AI path) ==")
u2 = mkteam("User2"); p2 = mkteam("Partner2")
ai_star = mkplayer(6_500_000, ovr=82, age=24, name="AI Star")
ai_star.offer_sheet_match_no_trade_until = 2027
p2.roster.append(ai_star); fill(p2)
u2_piece = mkplayer(6_500_000, ovr=80, age=26, name="User Piece")
u2.roster.append(u2_piece); fill(u2)
league_b = SimpleNamespace(season_year=2026, rivalries=[],
                           teams=[u2, p2], salary_cap_system=None)
tr2 = te.execute_trade(u2, p2, [u2_piece], [ai_star], league=league_b)
check("AI's matched player coming back BLOCKS",
      tr2.summary.startswith("BLOCKED"))
check("AI-side block moves nothing",
      ai_star in p2.roster and u2_piece in u2.roster)

print("== AI GM rejects demanding his matched player ==")
resp = te.ai_consider_trade(p2, [u2_piece], [ai_star], user_team=u2)
check("AI rejects the demand", resp.decision == "reject")
check("AI names the offer-sheet reason",
      "offer sheet" in resp.message.lower())

# ------------------------------------------------------- 4. after expiry
print("== trade completes after expiry ==")
u3 = mkteam("User3"); p3 = mkteam("Partner3")
old_star = mkplayer(6_500_000, ovr=82, age=25, name="Old Star")
old_star.offer_sheet_match_no_trade_until = 2027
u3.roster.append(old_star); fill(u3)
p3_piece = mkplayer(6_500_000, ovr=80, age=26, name="Partner Bit")
p3.roster.append(p3_piece); fill(p3)
league27b = SimpleNamespace(season_year=2027, rivalries=[],
                            teams=[u3, p3], salary_cap_system=None)
tr3 = te.execute_trade(u3, p3, [old_star], [p3_piece], league=league27b)
check("post-expiry trade completes", not tr3.summary.startswith("BLOCKED"))
check("post-expiry star moves", old_star in p3.roster)

# ------------------------------------------------ 5. unaffected players
print("== players with no sheet history unaffected ==")
u4 = mkteam("User4"); p4 = mkteam("Partner4")
plain_a = mkplayer(5_000_000, name="Plain A")
plain_b = mkplayer(5_000_000, name="Plain B")
u4.roster.append(plain_a); fill(u4)
p4.roster.append(plain_b); fill(p4)
league_c = SimpleNamespace(season_year=2026, rivalries=[],
                           teams=[u4, p4], salary_cap_system=None)
check("ordinary player draws no veto",
      te.trade_vetoes(u4, p4, [plain_a], league_c) == [])
tr4 = te.execute_trade(u4, p4, [plain_a], [plain_b], league=league_c)
check("ordinary player trade completes",
      not tr4.summary.startswith("BLOCKED") and plain_a in p4.roster)
# an UNMATCHED sheet never sets the flag: the signed-away player is fine
walked = mkplayer(3_000_000, ovr=78, age=23, name="Walked Away")
check("no flag attr without a match",
      getattr(walked, "offer_sheet_match_no_trade_until", 0) == 0)

# ------------------------------------------------------- 6. no waiving
print("== will_waive_ntc refuses (hard veto) ==")
ok, why = te.will_waive_ntc(u_star, u, p, league)
check("matched player cannot waive out", ok is False)
check("refusal names the protection", "offer sheet" in why.lower())
ok2, _ = te.will_waive_ntc(plain_a, u4, p4, league_c)
check("ordinary player keeps normal waiver answer",
      ok2 is True)

# ------------------------------------------------------- 7. save/load
print("== flag survives save/load ==")
blob = pickle.dumps(star)
star2 = pickle.loads(blob)
check("flag survives pickle round-trip",
      getattr(star2, "offer_sheet_match_no_trade_until", 0) == 2027)
fresh = mkplayer(2_000_000, name="Fresh Rookie")
check("old-save getattr default is 0",
      getattr(fresh, "offer_sheet_match_no_trade_until", 0) == 0)
check("default-0 player draws no veto",
      te.trade_vetoes(u4, p4, [fresh], league_c) == [])

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
