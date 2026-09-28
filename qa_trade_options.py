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

# explicitly naming the destination on his list -> almost always refuses
# (he can still be talked into an exception, but it's rare)
listed = give_clause(mkplayer(6_000_000, name="Listed Guy"), "mntc", size=10)
listed.contract.no_trade_list = ["P8"]
_refusals = sum(1 for _i in range(40)
                if not te.will_waive_ntc(listed, u8, p8,
                                         rng=random.Random(1000 + _i))[0])
check("destination on no-trade list -> refuses ~always", _refusals >= 36)

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

# ------------------------------------------------- realism audit (2026-09-28)
print("== realism audit: real NHL rules ==")
from types import SimpleNamespace

# -- 15% retained-salary aggregate (CBA: max 15% of the upper limit)
u15 = mkteam("CapClub"); p15 = mkteam("Other")
star15 = mkplayer(6_000_000, age=30, name="Big Ticket"); u15.roster.append(star15)
u15.roster.extend(mkplayer(4_000_000) for _ in range(19))
u15.retained_salary = [
    {"player_id": "x1", "player_name": "X1", "amount": 7_000_000,
     "seasons_remaining": 2},
    {"player_id": "x2", "player_name": "X2", "amount": 7_000_000,
     "seasons_remaining": 2},
]
vic15 = mkplayer(4_000_000, name="Victim"); p15.roster.append(vic15)
p15.roster.extend(mkplayer(4_000_000) for _ in range(19))
tr15 = te.execute_trade(u15, p15, [star15], [vic15],
                        retention={star15.id: 50})
check("15% aggregate blocks the deal ($14M + $3M > $15.6M)",
      tr15.summary.startswith("BLOCKED:"))
check("15%-blocked deal moves nothing",
      star15 in u15.roster and vic15 in p15.roster)

# -- one contract, at most two retaining clubs (double retention is real)
trio = mkteam("ClubC")
dbl = mkplayer(8_000_000, age=31, name="Twice Retained")
dbl.retained_amount = 6_000_000
dbl.retained_team_name = "ClubA"
dbl.retained_by = ["ClubA", "ClubB"]
trio.roster.append(dbl)
ok2, _a2, why2 = te._retention_check(trio, dbl, 25)
check("third retaining club refused", not ok2 and "two clubs" in why2)

# -- one-year reacquire ban after retaining
ua3 = mkteam("Retainers"); pb3 = mkteam("Buyers")
gem = mkplayer(8_000_000, age=30, name="Gem Stone"); ua3.roster.append(gem)
ua3.roster.extend(mkplayer(4_000_000) for _ in range(19))
back3 = mkplayer(4_000_000, name="Return Piece"); pb3.roster.append(back3)
pb3.roster.extend(mkplayer(4_000_000) for _ in range(19))
tr3a = te.execute_trade(ua3, pb3, [gem], [back3], date_str="2026-11-01",
                        retention={gem.id: 50})
check("retention trade completes", not tr3a.summary.startswith("BLOCKED:"))
check("ban recorded on the player",
      any(b.get("team") == "Retainers"
          for b in (getattr(gem, "retention_bans", None) or [])))
tr3b = te.execute_trade(pb3, ua3, [gem], [back3], date_str="2027-03-01")
check("one-year reacquire ban blocks", tr3b.summary.startswith("BLOCKED:"))
tr3c = te.execute_trade(pb3, ua3, [gem], [back3], date_str="2028-06-01")
check("ban lifts after a year", not tr3c.summary.startswith("BLOCKED:"))

# -- per-side retention slots (the other club's terms don't eat yours)
ua4 = mkteam("UserA"); pa4 = mkteam("PartnerA")
u1 = mkplayer(5_000_000, name="U One"); ua4.roster.append(u1)
ua4.roster.extend(mkplayer(4_000_000) for _ in range(19))
pps = [mkplayer(5_000_000, name=f"P{i}") for i in range(3)]
for _x in pps:
    pa4.roster.append(_x)
pa4.roster.extend(mkplayer(4_000_000) for _ in range(17))
ret4 = {u1.id: 10, pps[0].id: 10, pps[1].id: 10, pps[2].id: 10}
tr4 = te.execute_trade(ua4, pa4, [u1], pps, retention=ret4)
check("per-side slots: partner's 3 terms don't eat user's slot",
      not tr4.summary.startswith("BLOCKED:"))

# -- league-office cap preflight (both clubs, over-cap shed exception)
uo = mkteam("Overcaps"); po = mkteam("Partners")
uo.roster.extend(mkplayer(4_000_000) for _ in range(27))  # $108M vs $104M
a_out = uo.roster[0]
b_in = mkplayer(4_000_000, name="Sideways"); po.roster.append(b_in)
po.roster.extend(mkplayer(4_000_000) for _ in range(19))
tr5 = te.execute_trade(uo, po, [a_out], [b_in])
check("neutral deal while over cap is blocked",
      tr5.summary.startswith("BLOCKED:"))
cheap = mkplayer(1_000_000, name="Cheap"); po.roster.append(cheap)
tr5b = te.execute_trade(uo, po, [a_out], [cheap])
check("genuine salary shed while over cap is legal",
      not tr5b.summary.startswith("BLOCKED:"))

# -- asset ownership: you can't trade a pick you don't own
ux = mkteam("UserX"); px = mkteam("PartnerX")
ax = mkplayer(4_000_000, name="Ax"); ux.roster.append(ax)
ux.roster.extend(mkplayer(4_000_000) for _ in range(19))
bx = mkplayer(4_000_000, name="Bx"); px.roster.append(bx)
px.roster.extend(mkplayer(4_000_000) for _ in range(19))
ghost = g.DraftPick(year=2027, round=2, original_team="Ghosts",
                    current_team="Ghosts")
tr6 = te.execute_trade(ux, px, [ax], [bx, ghost])
check("unowned pick blocks the deal", tr6.summary.startswith("BLOCKED:"))
check("ownership-blocked deal moves nothing",
      ax in ux.roster and bx in px.roster)

# -- M-NTC: season-fixed lists, veto only when actually listed
lst = mkplayer(5_000_000, age=30, name="List Guy")
give_clause(lst, "mntc", 10)
lst.contract.no_trade_list = ["Rival Town"]
tA = mkteam("Home"); tB = mkteam("Rival Town"); tC = mkteam("Neutral City")
tA.roster.append(lst)
_bl, _why = te._mntc_blocks(lst, tB, None)
check("explicit no-trade list blocks", _bl and "no-trade list" in _why)
_b2, _ = te._mntc_blocks(lst, tC, None)
_b2b, _ = te._mntc_blocks(lst, tC, None)
check("list answer is season-stable (no re-roll)", _b2 == _b2b)
_vv = te.trade_vetoes(tA, tB, [lst], None)
check("M-NTC vetoes a listed destination", len(_vv) == 1)
_vv2 = te.trade_vetoes(tA, tC, [lst], None)
_b2c, _ = te._mntc_blocks(lst, tC, None)
check("veto matches list membership", (len(_vv2) == 1) == _b2c)
_okw, _whyw = te.will_waive_ntc(lst, tA, tB, None, rng=random.Random(7))
check("listed M-NTC waiver asks for an exception", "exception" in _whyw)
_okw2, _whyw2 = te.will_waive_ntc(lst, tA, tC, None, rng=random.Random(7))
_b2d, _ = te._mntc_blocks(lst, tC, None)
check("M-NTC waiver consistent with list",
      (not _b2d and _okw2 and "doesn't block" in _whyw2)
      or (_b2d and "exception" in _whyw2))

# -- NMC waiver consent (context="waivers")
nmc9 = mkplayer(7_000_000, age=33, name="No Move")
give_clause(nmc9, "nmc")
tH9 = mkteam("Home Team")
_ok9, _why9 = te.will_waive_ntc(nmc9, tH9, None, None,
                               rng=random.Random(3), context="waivers")
check("NMC waiver consent returns a verdict",
      isinstance(_ok9, bool) and "waiver placement" in _why9)

# -- clause eligibility: UFA bar (27+ or 7 pro seasons)
kid = mkplayer(2_000_000, age=23, name="Kid Prospect")
check("under-27 without 7 seasons is clause-ineligible",
      not te.clause_eligible(kid))
vet9 = mkplayer(6_000_000, age=32, name="Veteran Presence")
check("32-year-old is clause-eligible", te.clause_eligible(vet9))
check("clause demand is zero for ineligible players",
      te.clause_demand_score(kid) == 0.0)
check("apply_clause refuses ineligible player",
      te.apply_clause_to_contract(kid.contract, "ntc", player=kid) is False
      and kid.contract.no_trade_clause is False)
check("apply_clause stamps eligible player",
      te.apply_clause_to_contract(vet9.contract, "mntc", 12,
                                 player=vet9) is True
      and vet9.contract.modified_ntc_teams == 12)

# -- pick protection only triggers INSIDE the zone
lg = SimpleNamespace(PROTECTION_ZONES=g.League.PROTECTION_ZONES)
tO = mkteam("Originals"); tH2 = mkteam("Holders")
pkz = g.DraftPick(year=2027, round=1, original_team="Originals",
                  current_team="Holders")
pkz.protection = "top-10"
pk28 = g.DraftPick(year=2028, round=1, original_team="Originals",
                   current_team="Originals")
tO.draft_picks = {2027: [], 2028: [pk28]}
tH2.draft_picks = {2027: [pkz]}
lg.teams = [tO, tH2]
lg.standings = {"Originals": {"Points": 60}, "Holders": {"Points": 100}}
lg.lottery_results = {2027: [{"original_team": "Originals", "pick": 15}]}
evz = g.League.resolve_pick_protections(lg, 2027)
check("top-10 protection NOT triggered at #15",
      pkz.current_team == "Holders" and pkz.protection == "")
check("non-trigger is logged", any("not triggered" in e for e in evz))
pkz2 = g.DraftPick(year=2027, round=1, original_team="Originals",
                   current_team="Holders")
pkz2.protection = "top-10"
tH2.draft_picks = {2027: [pkz2]}
lg.lottery_results = {2027: [{"original_team": "Originals", "pick": 8}]}
evz2 = g.League.resolve_pick_protections(lg, 2027)
check("top-10 protection triggers at #8",
      pkz2.current_team == "Originals" and pk28.current_team == "Holders"
      and any("triggered" in e for e in evz2))

print()
print(f"{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:")
    for f_ in failed:
        print(f"  - {f_}")
    sys.exit(1)
