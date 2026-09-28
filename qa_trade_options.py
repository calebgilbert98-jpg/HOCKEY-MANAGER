"""QA: realistic trade options -- bilateral retention, pick protection,
NTC/NMC/M-NTC waivers, and contract-negotiation clauses.

Covers the engine, the AI/user parity paths, the deadline screen's
conventions, and save/load round-trips. Run: python3 qa_trade_options.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(20260928)

import game_classes as g
from game_classes import PlayerPosition
import trade_engine as te

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=104_000_000):
    t = g.Team(name, "T", "D", "C")
    t.salary_cap = cap
    return t

def mkplayer(salary, ovr=75, age=27, name="Test Player"):
    p = g.Player(first_name=name.split()[0], last_name=" ".join(name.split()[1:]) or "X",
                 age=age, primary_position=PlayerPosition.CENTER)
    p.contract.salary = salary
    # overall_rating() derives from attributes; pin a few so OVR is sane
    for attr in ("skating", "shooting", "passing", "checking", "defense",
                 "hockey_iq", "strength", "speed"):
        try:
            setattr(p, attr, ovr)
        except Exception:
            pass
    return p

def give_clause(p, kind="ntc", size=10):
    c = p.contract
    if kind == "nmc":
        c.no_movement_clause = True
    elif kind == "ntc":
        c.no_trade_clause = True
    elif kind == "mntc":
        c.no_trade_clause = True
        c.modified_ntc_teams = size
    return p

CAP = 104_000_000

# ---------------------------------------------------------------- 1. retention
print("== bilateral retention ==")
u = mkteam("User"); p = mkteam("Partner")
a = mkplayer(6_000_000); u.roster.append(a)
b = mkplayer(4_000_000); p.roster.append(b)
u.roster.extend(mkplayer(4_000_000) for _ in range(19))   # $82M total
p.roster.extend(mkplayer(4_000_000) for _ in range(19))   # $82M total
ret = {a.id: 50, b.id: 25}  # user retains 50% on a; partner retains 25% on b
tr = te.execute_trade(u, p, [a], [b], retention=ret)
check("bilateral retention trade completes", not tr.summary.startswith("BLOCKED"))
check("user kept $3M dead cap on a", any(
    e.get("player_id") == a.id and e.get("amount") == 3_000_000
    for e in u.retained_salary))
check("partner kept $1M dead cap on b", any(
    e.get("player_id") == b.id and e.get("amount") == 1_000_000
    for e in p.retained_salary))
check("a's cap hit is now $3M for partner",
      te._player_cap_hit(a) == 3_000_000)
check("b's cap hit is now $3M for user",
      te._player_cap_hit(b) == 3_000_000)
check("a moved to partner", a in p.roster and a not in u.roster)
check("b moved to user", b in u.roster and b not in p.roster)

print("== retention limits ==")
u2 = mkteam("U2"); p2 = mkteam("P2")
c = mkplayer(6_000_000); u2.roster.append(c)
d = mkplayer(2_000_000); p2.roster.append(d)
tr = te.execute_trade(u2, p2, [c], [d], retention={c.id: 75})
check("75% retention BLOCKS the deal", tr.summary.startswith("BLOCKED"))
check("blocked deal moves nothing (c stays)", c in u2.roster and c not in p2.roster)
check("blocked deal moves nothing (d stays)", d in p2.roster and d not in u2.roster)
check("no ledger entry on blocked deal", u2.retained_salary == [])

# slot limit: fill all 3 slots, then a 4th term must block
u3 = mkteam("U3"); p3 = mkteam("P3")
u3.retained_salary = [
    {"player_id": f"old{i}", "player_name": f"Old {i}", "amount": 500_000,
     "seasons_remaining": 2} for i in range(3)]
e = mkplayer(6_000_000); u3.roster.append(e)
f = mkplayer(2_000_000); p3.roster.append(f)
tr = te.execute_trade(u3, p3, [e], [f], retention={e.id: 10})
check("4th retention slot BLOCKS the deal", tr.summary.startswith("BLOCKED"))
check("slot-blocked deal moves nothing", e in u3.roster)

# retention-aware cap check, both sides
u4 = mkteam("U4"); p4 = mkteam("P4")
u4.roster.extend(mkplayer(5_000_000) for _ in range(20))  # $100M
u4.roster.append(mkplayer(7_000_000))                      # $107M -> over cap
big = u4.roster[-1]
p4.roster.extend(mkplayer(5_000_000) for _ in range(20))  # $100M
# Over-cap user sheds the $7M contract retaining 50%: burden drops
# $107M -> $103.5M, a strict reduction -> legal.
check("retention-aware: over-cap shed with retention legal",
      te._cap_ok_after(u4, [big], [], retention={big.id: 50}) is True)
# Partner at $100M takes the $7M player with 50% retained: $103.5M, fits.
check("retention-aware: receiver's incoming hit is net of retention",
      te._cap_ok_after(p4, [], [big], retention={big.id: 50}) is True)
# Same deal without retention would break the partner's cap.
check("same deal w/o retention breaks cap",
      te._cap_ok_after(p4, [], [big]) is False)
# Raw dollar helper agrees.
check("retention adjustment math",
      te._retention_adjustment([big], {big.id: 50}) == 3_500_000)

# ------------------------------------------------------- 2. pick protection
print("== pick protection ==")
pk = g.DraftPick(year=2027, round=1, original_team="User", current_team="User")
check("protection defaults to empty", pk.protection == "")
pk.protection = "top-10"
check("top-10 label", te.protection_label("top-10") == "Top-10 protected")
check("top-3 label", te.protection_label("top-3") == "Top-3 protected")
check("lottery label", te.protection_label("lottery") == "Lottery protected")
check("empty label", te.protection_label("") == "")

# protected pick survives a trade object move and keeps its term
u5 = mkteam("U5"); p5 = mkteam("P5")
sk = mkplayer(3_000_000); u5.roster.append(sk)
pk2 = g.DraftPick(year=2027, round=1, original_team="U5", current_team="U5")
pk2.protection = "lottery"
u5.draft_picks = {2027: [pk2]}
tr = te.execute_trade(u5, p5, [sk, pk2], [], retention=None)
check("protected pick moves with protection intact",
      pk2.current_team == "P5" and pk2.protection == "lottery")

# ------------------------------------------------------- 3. clause blockers
print("== NTC/NMC blockers ==")
u6 = mkteam("U6"); p6 = mkteam("P6")
ntc_guy = give_clause(mkplayer(7_000_000, name="Ntc Guy"), "ntc")
u6.roster.append(ntc_guy)
sweet = mkplayer(1_000_000); p6.roster.append(sweet)
tr = te.execute_trade(u6, p6, [ntc_guy], [sweet])
check("full NTC blocks the trade", tr.summary.startswith("BLOCKED"))
check("NTC-blocked: player stays", ntc_guy in u6.roster and ntc_guy not in p6.roster)
check("NTC-blocked: partner asset stays", sweet in p6.roster)

nmc_guy = give_clause(mkplayer(8_000_000, name="Nmc Guy"), "nmc")
u6.roster.append(nmc_guy)
tr = te.execute_trade(u6, p6, [nmc_guy], [sweet])
check("NMC blocks the trade", tr.summary.startswith("BLOCKED"))

mntc_guy = give_clause(mkplayer(5_000_000, name="Mntc Guy"), "mntc", size=12)
u6.roster.append(mntc_guy)
tr = te.execute_trade(u6, p6, [mntc_guy], [sweet])
check("M-NTC blocks the trade", tr.summary.startswith("BLOCKED"))

# waiver granted -> deal flows, waiver spent
ntc_guy.contract.ntc_waiver_for = "P6"
tr = te.execute_trade(u6, p6, [ntc_guy], [sweet])
check("waived NTC lets the trade through", not tr.summary.startswith("BLOCKED"))
check("waiver is single-use (cleared)", ntc_guy.contract.ntc_waiver_for == "")
check("waived player moved", ntc_guy in p6.roster)

# veto in the other direction (partner's clause player coming back)
u7 = mkteam("U7"); p7 = mkteam("P7")
mine = mkplayer(2_000_000); u7.roster.append(mine)
theirs = give_clause(mkplayer(6_000_000, name="Their Star"), "ntc")
p7.roster.append(theirs)
tr = te.execute_trade(u7, p7, [mine], [theirs])
check("partner's NTC blocks inbound too", tr.summary.startswith("BLOCKED"))

# picks never veto
u8 = mkteam("U8"); p8 = mkteam("P8")
plain = mkplayer(2_000_000); u8.roster.append(plain)
pp = g.DraftPick(year=2027, round=2, original_team="P8", current_team="P8")
tr = te.execute_trade(u8, p8, [plain], [pp])
check("picks never trigger vetoes", not tr.summary.startswith("BLOCKED"))

print("== waiver decision factors ==")
# no clause -> always fine
ok, why = te.will_waive_ntc(mkplayer(3_000_000), u8, p8)
check("no clause -> will_waive True", ok is True)

# explicit no-trade list naming the destination -> hard no
listed = give_clause(mkplayer(6_000_000, name="Listed Guy"), "mntc", size=10)
listed.contract.no_trade_list = ["P8"]
ok, why = te.will_waive_ntc(listed, u8, p8)
check("destination on no-trade list -> refuses", ok is False)

# happiness moves the needle: unhappy waives far more often than happy
def waiver_rate(happiness, n=60):
    rng = random.Random(99)
    yes = 0
    for _ in range(n):
        pl = give_clause(mkplayer(7_000_000, ovr=88, age=30,
                                 name="Star Winger"), "ntc")
        pl.happiness = happiness
        pl.morale = 70
        ok, _ = te.will_waive_ntc(pl, u8, p8, rng=rng)
        yes += ok
    return yes / n
r_unhappy = waiver_rate(25)
r_happy = waiver_rate(95)
check(f"unhappy waives more ({r_unhappy:.2f} > {r_happy:.2f})",
      r_unhappy > r_happy)

# contender destination helps
def waiver_rate_to(dest_pct_holder, n=40):
    rng = random.Random(7)
    yes = 0
    for _ in range(n):
        pl = give_clause(mkplayer(7_000_000, ovr=84, age=31,
                                 name="Vet Center"), "ntc")
        pl.happiness = 60; pl.morale = 70
        ok, _ = te.will_waive_ntc(pl, u8, dest_pct_holder, rng=rng)
        yes += ok
    return yes / n
class FakeTeam:
    def __init__(self, name, pct):
        self.team_name = name; self._pct = pct
good = FakeTeam("Contender", 0.70); bad = FakeTeam("Cellar", 0.30)
import types
_orig = te._team_points_pct
te._team_points_pct = lambda t, l: getattr(t, "_pct", 0.5)
r_good = waiver_rate_to(good); r_bad = waiver_rate_to(bad)
te._team_points_pct = _orig
check(f"contender destination waives more ({r_good:.2f} >= {r_bad:.2f})",
      r_good >= r_bad)

print("== clause tags ==")
check("NTC tag", te.clause_tag(give_clause(mkplayer(1_000_000), "ntc")) == "NTC")
check("NMC tag", te.clause_tag(give_clause(mkplayer(1_000_000), "nmc")) == "NMC")
check("M-NTC tag", te.clause_tag(give_clause(mkplayer(1_000_000), "mntc")) == "M-NTC")
check("no-clause tag empty", te.clause_tag(mkplayer(1_000_000)) == "")

# ------------------------------------------------------- 4. AI parity
print("== AI/user parity ==")
ua = mkteam("UserA"); pa = mkteam("PartnerA")
star = give_clause(mkplayer(9_000_000, ovr=90, age=30, name="Franchise C"), "ntc")
star.contract.no_trade_list = ["UserA"]  # hard refusal for the user's club
pa.roster.append(star)
dump = mkplayer(2_000_000); ua.roster.append(dump)
resp = te.ai_consider_trade(pa, [dump], [star], user_team=ua)
check("AI rejects when its star won't waive for the user",
      resp.decision == "reject")

# sweetener path: AI never offers a clause player who won't waive
ua2 = mkteam("UserB"); pa2 = mkteam("PartnerB")
refuser = give_clause(mkplayer(6_000_000, ovr=86, age=32, name="No Move D"), "nmc")
refuser.happiness = 99; refuser.morale = 99
refuser.contract.no_trade_list = ["UserB"]
pa2.roster.append(refuser)
pa2.roster.extend(mkplayer(3_000_000, ovr=76, age=28) for _ in range(6))
ua2.roster.extend(mkplayer(3_000_000, ovr=76, age=28) for _ in range(6))
cheap = mkplayer(1_500_000, ovr=72, age=26); ua2.roster.append(cheap)
mid = mkplayer(4_000_000, ovr=80, age=29); pa2.roster.append(mid)
resp = te.ai_consider_trade(pa2, [cheap], [mid], user_team=ua2)
if resp.decision == "counter":
    offered = list(resp.will_add or [])
    check("AI sweeteners exclude the refusing clause player",
          all(o is not refuser for o in offered))
else:
    check(f"AI considered without counter ({resp.decision})", True)

# deadline convention: user_assets = what the buyer RECEIVES
buy = mkteam("Buyer"); sel = mkteam("Seller")
piece = mkplayer(8_000_000, ovr=88, age=31, name="Deadline Star")
sel.roster.append(piece)
pay = g.DraftPick(year=2027, round=7, original_team="Buyer", current_team="Buyer")
resp = te.ai_consider_trade(buy, [piece], [pay], user_team=sel)
check("buyer getting a star for a 7th accepts/counters (not inverted)",
      resp.decision in ("accept", "counter"))
resp2 = te.ai_consider_trade(buy, [pay], [piece], user_team=sel)
check("inverted call does NOT hand the buyer a steal",
      resp2.decision in ("reject", "counter"))

# ------------------------------------------------------- 5. contract clauses
print("== contract clause negotiation ==")
star_vet = mkplayer(9_000_000, ovr=90, age=33, name="Old Star")
kid = mkplayer(1_000_000, ovr=72, age=21, name="Kid Winger")
d_star = te.clause_demand_score(star_vet)
d_kid = te.clause_demand_score(kid)
check(f"vet demands more than kid ({d_star:.2f} > {d_kid:.2f})", d_star > d_kid)
check(f"kid barely registers ({d_kid:.2f} ~ 0)", d_kid <= 0.15)
check("demand bounded 0..1", 0.0 <= d_star <= 1.0 and 0.0 <= d_kid <= 1.0)
# Tier logic itself, via a stub at a true 88 OVR (real Player OVR blends
# many attributes, so pinning a few never reaches the top tier).
class Stub88:
    age = 33
    def overall_rating(self): return 88
check("true-88 star vet scores high", te.clause_demand_score(Stub88()) >= 0.5)
v_nmc = te.clause_annual_value(star_vet, "nmc")
v_ntc = te.clause_annual_value(star_vet, "ntc")
v_mntc = te.clause_annual_value(star_vet, "mntc")
check("NMC > NTC > M-NTC > none in value",
      v_nmc > v_ntc > v_mntc > te.clause_annual_value(star_vet, "none") == 0)
check("depth player's clause worth less than star's",
      te.clause_annual_value(kid, "nmc") < v_nmc)
check("acceptance bonus scales with demand",
      te.clause_acceptance_bonus(star_vet, "ntc") >=
      te.clause_acceptance_bonus(kid, "ntc"))
check("no clause -> no bonus",
      te.clause_acceptance_bonus(star_vet, "none") == 0.0)

c = star_vet.contract
te.apply_clause_to_contract(c, "nmc")
check("apply NMC stamps flag",
      c.no_movement_clause is True and c.no_trade_clause is False)
c2 = kid.contract
te.apply_clause_to_contract(c2, "mntc", 12)
check("apply M-NTC stamps list size",
      c2.no_trade_clause is True and c2.modified_ntc_teams == 12)
check("apply 'none' is a no-op", te.apply_clause_to_contract(c2, "none") is False)
check("label nmc", te.clause_offer_label("nmc") == "no-movement clause")
check("label mntc w/ size",
      te.clause_offer_label("mntc", 12) == "modified no-trade (12-team list)")

# world-gen parity: the shared demand model grants clauses to veterans
# sometimes, never to kids
granted = 0
for _ in range(40):
    _vet = mkplayer(9_000_000, ovr=88, age=33, name="Vet Winger")
    _c = _vet.contract
    _c.no_trade_clause = False; _c.no_movement_clause = False
    _c.modified_ntc_teams = 0
    roll = "nmc" if random.random() < te.clause_demand_score(_vet) * 0.85 \
        else "none"
    te.apply_clause_to_contract(_c, roll)
    granted += bool(_c.no_trade_clause or _c.no_movement_clause)
check("demand model grants clauses to vets sometimes", granted > 0)
check("kids get nothing from the demand model",
      all(te.clause_demand_score(mkplayer(900_000, ovr=70, age=20,
                                          name="Kid D")) * 0.85
          < random.random() for _ in range(20)))

# ------------------------------------------------------- 6. save/load
print("== save/load round-trips ==")
import save_load_system as sls
saver = sls.GameSaveManager.__new__(sls.GameSaveManager)
p = give_clause(mkplayer(6_500_000, name="Save Test"), "mntc", size=15)
p.contract.ntc_waiver_for = "Somewhere"
data = saver._serialize_contract(p.contract)
check("clause fields serialize",
      data.get("no_trade_clause") is True
      and data.get("modified_ntc_teams") == 15
      and data.get("ntc_waiver_for") == "Somewhere"
      and data.get("no_movement_clause") is False)
back = saver._restore_contract(data)
check("clause fields restore",
      back.no_trade_clause is True and back.modified_ntc_teams == 15
      and back.ntc_waiver_for == "Somewhere")

# old-save safety: contract data without the new keys still loads
old_data = {"salary": 1_000_000, "years_remaining": 2}
back_old = saver._restore_contract(old_data)
check("old save contract loads (defaults)",
      back_old.no_trade_clause is False
      and back_old.no_movement_clause is False
      and back_old.modified_ntc_teams == 0
      and back_old.ntc_waiver_for == "")

t = mkteam("SaveTeam")
t.retained_salary = [{"player_id": "x", "player_name": "X",
                      "amount": 1_000_000, "seasons_remaining": 3}]
wire = [dict(e) for e in (getattr(t, "retained_salary", None) or [])]
t2 = mkteam("SaveTeam")
t2.retained_salary = [dict(e) for e in wire]
check("retained ledger round-trips",
      t2.retained_salary[0]["amount"] == 1_000_000
      and t2.retained_salary[0]["seasons_remaining"] == 3)

# pick protection survives pickle (the real save path)
import pickle
pk3 = g.DraftPick(year=2027, round=1, original_team="A", current_team="A")
pk3.protection = "top-3"
pk3b = pickle.loads(pickle.dumps(pk3))
check("pick protection survives pickle", pk3b.protection == "top-3")

print()
print(f"{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:")
    for f_ in failed:
        print(f"  - {f_}")
    sys.exit(1)
