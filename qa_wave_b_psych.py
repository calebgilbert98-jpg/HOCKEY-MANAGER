# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: Wave B negotiation psychology (D31 untouchables + D40 rivalry gate +
D42 stinginess + D43 market participation + D44 bid strategy).

Covers the three commits that shipped with zero new QA (23b7005, 8d5be2f).
Pure-logic tests, no UI. Run from the worktree:

    cd ~/workspace/wt-wave-b && python3 qa_wave_b_psych.py

Exit 0 = all green.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

WT = "/home/hatch/workspace/wt-wave-b"
if WT in sys.path:
    sys.path.remove(WT)
sys.path.insert(0, WT)

import trade_engine as te
import trade_market as tm
import trade_storylines as tsl
import ai_extension_planning as aep

# Provenance: these MUST be the worktree modules, never the pristine repo.
for _m in (te, tm, tsl, aep):
    assert "wt-wave-b" in _m.__file__, f"WRONG TREE: {_m.__file__}"
print(f"[provenance] worktree modules OK: {te.__file__}")

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
class C:
    def __init__(self, s, y=2):
        self.salary = s
        self.years_remaining = y
        self.entry_level = False


class P:
    """Lightweight player fixture (trade value + franchise reads only)."""
    _ids = [0]

    def __init__(self, n, ovr, age, sal, yrs=2, grade="C", rnd=0, db="",
                 pos="C", morale=60, requested=False):
        P._ids[0] += 1
        self.id = P._ids[0]
        self.full_name = n
        self._ovr = ovr
        self.age = age
        self.contract = C(sal, yrs)
        self.potential_grade = grade
        self.true_potential_grade = ""
        self.draft_round = rnd
        self.drafted_by = db
        self.rights_team = db
        self.primary_position = SimpleNamespace(value=pos)
        self.morale = morale
        self.transfer_requested = requested

    def overall_rating(self):
        return self._ovr


def team(name, roster=(), staff=()):
    return SimpleNamespace(team_name=name, roster=list(roster),
                           staff=list(staff), draft_picks={})


def ident(loyalty=0.5, aggression=0.5):
    return SimpleNamespace(loyalty=loyalty, aggression=aggression)


# Deterministic negotiation: no random greed jitter, no stinginess delta.
def det_neg():
    return (patch("random.uniform", return_value=0.0),
            patch.object(te, "_stinginess_delta", return_value=0.0))


# ---------------------------------------------------------------------------
# D31 / D42 shared reads: tier_label + franchise tiers
# ---------------------------------------------------------------------------
def test_tier_label_shim():
    print("== tier_label (talent-tiers coherence shim) ==")
    for ovr, want in ((98, "Generational"), (92, "Generational"),
                      (91, "Elite"), (88, "Elite"),
                      (87, "Very good"), (84, "Very good"),
                      (83, "Good"), (80, "Good"),
                      (79, "Decent"), (60, "Decent")):
        got = te.tier_label(P("T", ovr, 27, 3_000_000))
        check(f"ovr {ovr} -> {want}", got == want, got)
    check("tier_index_of: Generational is 0",
          te.tier_index_of(P("T", 95, 27, 3_000_000)) == 0)
    check("tier_index_of: Decent is 4",
          te.tier_index_of(P("T", 70, 27, 3_000_000)) == 4)


def test_franchise_tiers():
    print("== asset_franchise_tiers (GM-relative value reads) ==")
    unt = P("Cornerstone", 98, 23, 12_000_000, 4, "A", 1, "X")
    core = P("Star", 91, 28, 10_000_000, 2, "A", 1, "X")
    gettable = P("Grinder", 76, 30, 2_500_000, 1, "D", 5, "")
    t = team("X")
    tiers = te.asset_franchise_tiers(t, [unt, core, gettable], None)
    check("98ovr cornerstone -> UNTOUCHABLE",
          tiers[unt.id][0] == "UNTOUCHABLE", tiers[unt.id])
    check("91ovr star -> CORE", tiers[core.id][0] == "CORE", tiers[core.id])
    check("76ovr grinder -> GETTABLE",
          tiers[gettable.id][0] == "GETTABLE", tiers[gettable.id])
    check("untouchable needs 80+ franchise_score",
          tiers[unt.id][1] >= 80.0, tiers[unt.id][1])
    # Picks are skipped, never tiered.
    from game_classes import DraftPick
    pk = DraftPick(year=2027, round=1, original_team="X", current_team="X")
    check("picks skipped by tiering",
          te.asset_franchise_tiers(t, [pk], None) == {})


# ---------------------------------------------------------------------------
# D31: untouchables are a flat no, never sweeteners
# ---------------------------------------------------------------------------
def test_d31_flat_no():
    print("== D31: untouchable = flat no ==")
    unt = P("Cornerstone", 98, 23, 12_000_000, 4, "A", 1, "X")
    partner = team("PART", roster=[unt,
                                   P("S1", 78, 27, 4_000_000),
                                   P("S2", 76, 29, 3_000_000)])
    # Massive overpay: three 82s for the cornerstone. Still a no --
    # untouchability is not a price.
    rich = [P("R1", 82, 27, 5_000_000), P("R2", 82, 26, 5_000_000),
            P("R3", 82, 28, 5_000_000)]
    u1, u2 = det_neg()
    with u1, u2:
        r = te.ai_consider_trade(partner, rich, [unt])
    check("untouchable ask -> reject", r.decision == "reject", r.decision)
    check("not a counter (no negotiation at any price)",
          r.decision != "counter", r.decision)
    check("plain-spoken message",
          "isn't available at any price" in (r.message or ""),
          (r.message or "")[:80])


def test_d31_no_sweetener():
    print("== D31: untouchables never volunteered as sweeteners ==")
    unt = P("Cornerstone", 98, 23, 12_000_000, 4, "A", 1, "X")
    scrub = P("Scrub", 65, 27, 1_000_000)          # value 180
    partner = team("PART", roster=[unt, scrub,
                                   P("F1", 82, 27, 5_000_000),
                                   P("F2", 81, 27, 5_000_000),
                                   P("F3", 80, 27, 4_000_000)])
    # The user has nothing covering the shortfall, so the AI sweetens
    # from its own side instead of countering for a user asset.
    user = team("USER", roster=[])
    # ratio 900/1020 = 0.882: inside the sweetener band [greed-0.15, greed).
    u_in = P("In", 80, 30, 5_000_000)              # value 900
    p_out = P("Out", 79, 27, 4_000_000)            # value 1020
    ev = te.evaluate_trade([u_in], [p_out])
    check("fixture ratio in sweetener band",
          0.85 <= ev.ratio < 1.0, round(ev.ratio, 4))
    u1, u2 = det_neg()
    with u1, u2:
        r = te.ai_consider_trade(partner, [u_in], [p_out], user_team=user)
    check("close offer -> sweetener counter", r.decision == "counter",
          r.decision)
    check("sweetener offered", bool(r.will_add), r.decision)
    if r.will_add:
        check("sweetener is the scrub, not the cornerstone",
              r.will_add[0].full_name == "Scrub",
              r.will_add[0].full_name)
        check("cornerstone never volunteered",
              all(a.full_name != "Cornerstone" for a in r.will_add))


# ---------------------------------------------------------------------------
# D40: one shared rivalry gate
# ---------------------------------------------------------------------------
def test_d40_gate_units():
    print("== D40: rivalry_trade_gate units ==")
    g = te.rivalry_trade_gate
    v, tax, _ = g(None, None, None)
    check("no situational -> open (never blocks blind)",
          v == "open" and tax == 1.0, (v, tax))
    v, tax, _ = g({"rivalry_intensity01": 0.3}, None, None)
    check("intensity 0.3 -> open", v == "open", v)
    v, tax, why = g({"rivalry_intensity01": 0.7}, None, None,
                    ident(loyalty=0.9))
    check("intensity 0.7 -> taxed", v == "taxed", v)
    check("tax scales with loyalty: 1.018",
          abs(tax - 1.018) < 1e-9, tax)
    check("tax reason mentions rivalry", "Rivalry tax" in why, why)
    # Bitter: crown jewel closed.
    tiers = {1: ("UNTOUCHABLE", 95.0)}
    v, _, why = g({"rivalry_intensity01": 0.9}, None, None, None, tiers)
    check("bitter + UNTOUCHABLE -> closed", v == "closed", v)
    check("McDavid-to-Calgary message",
          "face of the franchise" in why, why)
    # Bitter: contender core closed.
    tiers = {1: ("CORE", 60.0)}
    v, _, why = g({"rivalry_intensity01": 0.9, "stance": "buyer"},
                  None, None, None, tiers)
    check("bitter + buyer CORE -> closed", v == "closed", v)
    check("contender message", "rival" in why, why)
    # Bitter: seller veterans taxed, never closed.
    vet = P("Vet", 84, 33, 5_000_000)
    tiers = {7: ("VALUED", 40.0)}
    v, tax, _ = g({"rivalry_intensity01": 0.9, "stance": "seller"},
                  None, [vet], None, tiers)
    check("bitter + seller veteran -> taxed, never closed",
          v == "taxed", v)
    check("seller tax > 1", tax > 1.0, tax)
    # Bitter: role players always move.
    tiers = {9: ("GETTABLE", 10.0)}
    v, _, _ = g({"rivalry_intensity01": 0.95}, None, None, None, tiers)
    check("bitter + role player -> taxed (moves)", v == "taxed", v)


def test_d40_tax_wiring():
    print("== D40: gate tax multiplies the greed threshold ==")
    # ratio 960/950 = 1.0105: accepted at fair, countered under rivalry tax.
    u_in = P("In", 78, 27, 5_000_000)     # 960
    p_out = P("Out", 81, 30, 5_000_000)   # 950 (GETTABLE: no D31/D40 closure)
    ev = te.evaluate_trade([u_in], [p_out])
    check("fixture ratio ~1.0105", abs(ev.ratio - 960 / 950) < 1e-9,
          round(ev.ratio, 4))
    partner = team("PART", roster=[p_out, P("F1", 80, 27, 4_000_000)])
    user = team("USER", roster=[P("Extra", 68, 27, 1_000_000)])
    u1, u2 = det_neg()
    with u1, u2:
        r_fair = te.ai_consider_trade(partner, [u_in], [p_out],
                                      user_team=user, situational=None)
    check("no rivalry -> accept", r_fair.decision == "accept", r_fair.decision)
    with u1, u2:
        r_tax = te.ai_consider_trade(
            partner, [u_in], [p_out], user_team=user,
            situational={"rivalry_intensity01": 0.8})
    # tax = 1 + 0.05*0.5*((0.8-0.6)/0.25) = 1.02 > 1.0105
    check("rivalry tax -> no longer accepted", r_tax.decision != "accept",
          r_tax.decision)


def test_d40_bitter_paths_behavioral():
    print("== D40: bitter-rival closures, behavioral ==")
    core = P("Core", 91, 28, 9_000_000, 2, "A", 1, "X")   # CORE tier
    partner = team("PART", roster=[core, P("F1", 80, 27, 4_000_000)])
    u1, u2 = det_neg()
    with u1, u2:
        r = te.ai_consider_trade(
            partner, [P("R1", 82, 27, 5_000_000)], [core],
            situational={"rivalry_intensity01": 0.9, "stance": "buyer"})
    check("bitter contender CORE -> reject", r.decision == "reject", r.decision)
    check("rivalry reason given", "rival" in (r.message or "").lower(),
          (r.message or "")[:80])
    # Seller veteran between bitter rivals: taxed, never closed. Offer at
    # ratio comfortably above the 1.04 seller tax -> accept.
    vet = P("Vet", 84, 33, 5_000_000)
    partner2 = team("P2", roster=[vet, P("F1", 80, 27, 4_000_000)])
    u_in = P("In", 79, 24, 5_000_000)     # 1050
    ev = te.evaluate_trade([u_in], [vet])
    check("fixture ratio clears the 1.04 seller tax",
          ev.ratio >= 1.05, round(ev.ratio, 4))
    with u1, u2:
        r2 = te.ai_consider_trade(
            partner2, [u_in], [vet],
            situational={"rivalry_intensity01": 0.9, "stance": "seller"})
    check("bitter seller veteran still moves (taxed, not closed)",
          r2.decision == "accept", r2.decision)


# ---------------------------------------------------------------------------
# D42: stinginess pass
# ---------------------------------------------------------------------------
def test_d42_stinginess_delta():
    print("== D42: _stinginess_delta units ==")
    t = team("X")
    a = P("A", 80, 27, 4_000_000)
    tiers = {a.id: ("GETTABLE", 20.0)}
    # Baseline: a neutral coach read (0.5). Without this the fixture's
    # missing archetype makes coach_archetype_valuation return 1.0 (+0.04)
    # -- a pre-existing reputation_system behavior, not Wave B's.
    with patch.object(te, "_coach_piece_fit01", return_value=0.5):
        base = te._stinginess_delta(t, [a], ident(), tiers, {"stance": "x"})
        check("neutral piece -> 0.0", base == 0.0, base)
        check("ident None -> no personality read",
              te._stinginess_delta(t, [a], None, tiers) == 0.0)
        core = P("C", 91, 28, 9_000_000)
        tiers_c = {core.id: ("CORE", 60.0)}
        check("CORE piece +0.06",
              te._stinginess_delta(t, [core], ident(), tiers_c) == 0.06)
        sad = P("S", 80, 27, 4_000_000, morale=30)
        check("unhappy player -0.05",
              te._stinginess_delta(t, [sad], ident(), tiers) == -0.05)
        req = P("Q", 80, 27, 4_000_000, requested=True)
        check("trade request -0.05",
              te._stinginess_delta(t, [req], ident(), tiers) == -0.05)
        happy = P("H", 80, 27, 4_000_000, morale=80)
        check("happy piece +0.02",
              te._stinginess_delta(t, [happy], ident(), tiers) == 0.02)
        check("loyal GM +0.03",
              te._stinginess_delta(t, [a], ident(loyalty=0.9), tiers)
              == 0.03)
        check("aggressive deal-maker -0.02",
              te._stinginess_delta(t, [a], ident(aggression=0.9), tiers)
              == -0.02)
        old = P("O", 80, 32, 4_000_000)
        check("seller moves veterans -0.04",
              te._stinginess_delta(t, [old], ident(), tiers,
                                  {"stance": "seller"}) == -0.04)
        many = [P(f"M{i}", 91, 28, 9_000_000) for i in range(5)]
        tiers_m = {p.id: ("CORE", 60.0) for p in many}
        check("delta clamped at +0.25",
              te._stinginess_delta(t, many, ident(loyalty=0.9), tiers_m,
                                  {"stance": "x"}) == 0.25)
    with patch.object(te, "_coach_piece_fit01", return_value=0.8):
        check("coach loves him +0.04",
              te._stinginess_delta(t, [a], ident(), tiers) == 0.04)
    with patch.object(te, "_coach_piece_fit01", return_value=0.2):
        check("coach cold -0.03",
              te._stinginess_delta(t, [a], ident(), tiers) == -0.03)


def test_d42_greed_anchor():
    print("== D42: greed anchored at fair 1.0 ==")
    # 1020/1050 = 0.9714: accepted under the old 0.95 anchor, countered now.
    u_in = P("In", 79, 27, 4_000_000)     # 1020
    p_out = P("Out", 79, 24, 5_000_000)   # 1050
    ev = te.evaluate_trade([u_in], [p_out])
    check("fixture ratio 0.9714 (between 0.95 and 1.0)",
          0.95 < ev.ratio < 1.0, round(ev.ratio, 4))
    partner = team("PART", roster=[p_out, P("F1", 80, 27, 4_000_000)])
    user = team("USER", roster=[P("Extra", 68, 27, 1_000_000)])
    u1, u2 = det_neg()
    with u1, u2:
        r = te.ai_consider_trade(partner, [u_in], [p_out], user_team=user)
    check("97c on the dollar -> counter, not accept", r.decision == "counter",
          r.decision)


def test_d42_full_shortfall():
    print("== D42: counters demand the FULL shortfall ==")
    # ratio 900/1020 = 0.882; shortfall at greed 1.0 = 120.
    # mid asset (100) covers 0.7*shortfall=84 (old behavior) but not 120.
    u_in = P("In", 80, 30, 5_000_000)     # 900
    p_out = P("Out", 79, 27, 4_000_000)   # 1020
    mid = P("Mid", 64, 32, 1_000_000)     # 100: covers 0.7x, not full
    big = P("Big", 68, 27, 1_000_000)     # 360
    check("mid covers 0.7x shortfall only",
          84 <= te.asset_value(mid) < 120, te.asset_value(mid))
    check("big covers full shortfall",
          te.asset_value(big) >= 120, te.asset_value(big))
    partner = team("PART", roster=[p_out, P("F1", 80, 27, 4_000_000)])
    user = team("USER", roster=[mid, big])
    u1, u2 = det_neg()
    with u1, u2:
        r = te.ai_consider_trade(partner, [u_in], [p_out], user_team=user)
    check("counter (not accept)", r.decision == "counter", r.decision)
    check("counter demands the big asset (full shortfall)",
          r.want_added == [big],
          [a.full_name for a in (r.want_added or [])])


# ---------------------------------------------------------------------------
# D43: market participation (sellers + neutrals bid)
# ---------------------------------------------------------------------------
from game_classes import Player as GPlayer, Team as GTeam, Contract as GContract
from game_classes import PlayerPosition

SKATER_ATTRS = ["skating", "shooting", "shooting_accuracy", "shooting_power",
                "passing", "passing_accuracy", "passing_creativity",
                "stickhandling", "deking", "one_timer", "slapshot",
                "wristshot", "backhand", "screen_shots",
                "offensive_awareness", "defensive_awareness", "hockey_iq",
                "vision", "faceoffs", "strength", "endurance", "composure",
                "determination", "teamwork", "leadership", "discipline",
                "consistency", "loose_puck", "off_the_puck"]

_pid = [1000]


def mkp(fn, pos, age, ovr, salary, morale=70):
    _pid[0] += 1
    p = GPlayer(fn, "T", age, pos)
    for a in SKATER_ATTRS:
        if hasattr(p, a):
            setattr(p, a, ovr)
    p.id = _pid[0]
    p.contract = GContract(salary=salary, years_remaining=2)
    p.potential_grade = "C"
    p.morale = morale
    p.ambition = ""
    return p


def mkt(name, players):
    t = GTeam(name, "City", "Metro", "East")
    t.roster = list(players)
    return t


def no_center_roster(prefix, ovr=80):
    # No centers -> 'C' is the #1 need, then LW (stable order).
    ps = [mkp(f"{prefix}LW{i}", PlayerPosition.LEFT_WING, 27, ovr,
              4_000_000) for i in range(6)]
    ps += [mkp(f"{prefix}D{i}", PlayerPosition.LEFT_DEFENSE, 28, ovr,
               4_000_000) for i in range(4)]
    ps += [mkp(f"{prefix}G", PlayerPosition.GOALIE, 30, 82, 5_000_000)]
    return ps


def test_d43_seller_bids():
    print("== D43: sellers bid on timeline hockey trades ==")
    S = mkt("SELLER", no_center_roster("S"))
    check("seller #1 need is C", tsl and te.team_needs(S)[0] == "C",
          te.team_needs(S)[:3])
    # Overall-setting 70 -> true overall 77 ("Decent"): no BPA override, so
    # participation is decided by the D43 stance logic alone.
    plc = mkp("Piece", PlayerPosition.CENTER, 25, 70, 4_000_000)
    check("listed piece is not a BPA/marquee case",
          te.tier_label(plc) == "Decent" and not tm.is_marquee(
              {"player_id": plc.id}, plc),
          (te.tier_label(plc), plc.overall_rating()))
    L = mkt("LISTER", [plc, mkp("L1", PlayerPosition.LEFT_WING, 30, 76,
                                3_000_000)])
    U = mkt("USER", no_center_roster("U"))
    league = SimpleNamespace(teams=[S, L, U])
    app = SimpleNamespace(user_team=SimpleNamespace(team_name="USER"))
    listing = {"player_id": plc.id, "seller": "LISTER"}
    stances = {"SELLER": "seller", "LISTER": "seller", "USER": "buyer"}
    with patch("trade_storylines.stance",
               side_effect=lambda a, n: stances[n]):
        got = tm._find_bidders(app, league, listing, None, False)
    names = [t.team_name for t in got]
    check("seller bids on 25yo top-2-need center", "SELLER" in names, names)
    # A 33-year-old is not a timeline piece: the seller sits out.
    plc.age = 33
    with patch("trade_storylines.stance",
               side_effect=lambda a, n: stances[n]):
        got = tm._find_bidders(app, league, listing, None, False)
    names = [t.team_name for t in got]
    check("seller does not bid on a 33yo veteran", "SELLER" not in names,
          names)
    # Wrong position (LW is not a top-2 need: needs are C, RW, RD, G...).
    plc.age = 25
    plc.primary_position = PlayerPosition.LEFT_WING
    with patch("trade_storylines.stance",
               side_effect=lambda a, n: stances[n]):
        got = tm._find_bidders(app, league, listing, None, False)
    names = [t.team_name for t in got]
    check("seller does not bid off-need", "SELLER" not in names, names)


def test_d43_neutral_opportunistic():
    print("== D43: neutrals bid opportunistically at a discount ==")
    from salary_cap_system import base_ask_dollars
    N = mkt("NEUTRAL", no_center_roster("N"))
    check("neutral #1 need is C", te.team_needs(N)[0] == "C")
    pn = mkp("Flier", PlayerPosition.CENTER, 30, 70, 1_000_000)
    check("flier is not a BPA/marquee case",
          te.tier_label(pn) == "Decent", te.tier_label(pn))
    fair = base_ask_dollars(pn.overall_rating(), 30)
    pn.contract.salary = int(fair / 0.72)
    wr, _ = tm.contract_worth(pn)
    check("fixture is buy-low (worth in 0.65..0.80)",
          0.65 < wr < 0.80, round(wr, 3))
    pf, _ = tm.perception_discount(
        SimpleNamespace(user_team=SimpleNamespace(team_name="USER")),
        SimpleNamespace(teams=[N]), pn)
    check("no perception discount on fixture", pf == 1.0, pf)
    L = mkt("LISTER", [pn])
    U = mkt("USER", no_center_roster("U"))
    league = SimpleNamespace(teams=[N, L, U])
    app = SimpleNamespace(user_team=SimpleNamespace(team_name="USER"))
    listing = {"player_id": pn.id, "seller": "LISTER"}
    stances = {"NEUTRAL": "neutral", "LISTER": "seller", "USER": "buyer"}
    with patch("trade_storylines.stance",
               side_effect=lambda a, n: stances[n]):
        got = tm._find_bidders(app, league, listing, None, False)
    names = [t.team_name for t in got]
    check("neutral bids on #1-need buy-low flier", "NEUTRAL" in names, names)
    # Same player at a fair salary: no discount, no bid.
    pn.contract.salary = int(fair)
    wr2, _ = tm.contract_worth(pn)
    check("fair-salary fixture has no discount", wr2 >= 0.95, round(wr2, 3))
    with patch("trade_storylines.stance",
               side_effect=lambda a, n: stances[n]):
        got = tm._find_bidders(app, league, listing, None, False)
    names = [t.team_name for t in got]
    check("neutral does not pay retail", "NEUTRAL" not in names, names)
    # Buy-low but not the #1 need: no bid.
    pn.contract.salary = int(fair / 0.72)
    pn.primary_position = PlayerPosition.LEFT_WING
    with patch("trade_storylines.stance",
               side_effect=lambda a, n: stances[n]):
        got = tm._find_bidders(app, league, listing, None, False)
    names = [t.team_name for t in got]
    check("neutral only bites on the #1 need", "NEUTRAL" not in names, names)


def test_d43_headliner_tiers():
    print("== D43/D44: _is_headliner reads tiers, not raw overall ==")
    check("Generational headliner at 35",
          tm._is_headliner(P("G", 95, 35, 10_000_000)))
    check("Elite headliner at 34",
          tm._is_headliner(P("E", 90, 34, 9_000_000)))
    check("Very good + young headliner",
          tm._is_headliner(P("V", 85, 24, 6_000_000)))
    check("Very good + 30 not a headliner",
          not tm._is_headliner(P("V2", 85, 30, 6_000_000)))
    check("Good never a headliner",
          not tm._is_headliner(P("Gd", 82, 22, 4_000_000)))


# ---------------------------------------------------------------------------
# D44: bid strategy (bundling + overpay to close)
# ---------------------------------------------------------------------------
def mkprospect(name, pos, ovr, salary):
    p = P(name, ovr, 21, salary, pos=pos)
    return p


def det_bid():
    """Deterministic build_bid: no perception/contract sizing noise, so the
    target is exactly ask_points (times the D44 premiums under test)."""
    return (patch.object(tm, "perception_discount", return_value=(1.0, "")),
            patch.object(tm, "contract_worth", return_value=(1.0, "")))


def test_d44_overpay_to_close():
    print("== D44: competition bids the price up (+5%/rival, cap +15%) ==")
    # Six prospects; the three cheapest non-core ones are the fill pool.
    pros = [mkprospect(f"Pr{i}", "C", ovr, 900_000)
            for i, ovr in enumerate((68, 70, 72, 74, 76, 78))]
    vals = sorted(te.asset_value(p) for p in pros)
    v1, v2, v3 = vals[0], vals[1], vals[2]
    bidder = team("BID", roster=pros)
    seller = mkt("SELL", no_center_roster("X"))
    star = mkp("Target", PlayerPosition.CENTER, 27, 70, 5_000_000)
    app = SimpleNamespace(user_team=SimpleNamespace(team_name="USER"))
    league = SimpleNamespace(teams=[bidder, seller])
    # ask lands target(n=1) just under v1+v2, target(n=4) above it.
    ask = (v1 + v2) * 0.98
    p1, p2 = det_bid()
    with p1, p2:
        b1 = tm.build_bid(app, league, bidder, star, seller, ask,
                          n_bidders=1)
        b4 = tm.build_bid(app, league, bidder, star, seller, ask,
                          n_bidders=4)
        b10 = tm.build_bid(app, league, bidder, star, seller, ask,
                           n_bidders=10)
    t1 = sum(te.asset_value(a) for a in b1)
    t4 = sum(te.asset_value(a) for a in b4)
    check("uncontested: two cheapest prospects", len(b1) == 2, len(b1))
    check("4 bidders: price bid up to three prospects", len(b4) == 3,
          len(b4))
    check("contested bundle costs more", t4 > t1, (t1, t4))
    check("rival premium capped at +15% (n=10 == n=4)",
          [a.id for a in b10] == [a.id for a in b4],
          (len(b10), len(b4)))


def test_d44_closers_premium():
    print("== D44: closer's premium for desperate buyers ==")
    pros = [mkprospect(f"Pc{i}", "C", ovr, 900_000)
            for i, ovr in enumerate((68, 70, 72, 74, 76, 78))]
    vals = sorted(te.asset_value(p) for p in pros)
    v1, v2 = vals[0], vals[1]
    bidder = team("BID", roster=pros)
    seller = mkt("SELL", no_center_roster("X"))
    star = mkp("Target", PlayerPosition.CENTER, 27, 70, 5_000_000)
    app = SimpleNamespace(user_team=SimpleNamespace(team_name="USER"))
    league = SimpleNamespace(teams=[bidder, seller])
    # Self-calibrating: S = v1+v2. T(0.60) = ask*1.18*1.05,
    # T(0.61) = ask*1.183*1.05*1.05. ask = S/1.27 lands T_cool <= S
    # < T_hot: the 0.25% base difference can't flip the fill, only the
    # 5% closer's premium can.
    s2 = v1 + v2
    ask = s2 / 1.27
    p1, p2 = det_bid()
    with p1, p2, patch.object(tm, "_buyer_desperation",
                             return_value=0.60):
        b_cool = tm.build_bid(app, league, bidder, star, seller, ask,
                              n_bidders=2)
    with p1, p2, patch.object(tm, "_buyer_desperation",
                             return_value=0.61):
        b_hot = tm.build_bid(app, league, bidder, star, seller, ask,
                             n_bidders=2)
    check("desperation 0.60 -> two assets", len(b_cool) == 2, len(b_cool))
    check("desperation 0.61 -> closer's premium adds a third",
          len(b_hot) == 3, len(b_hot))


def test_d44_seller_need_bundling():
    print("== D44: bundles shaped to the seller's needs ==")
    a_need = mkprospect("NeedC", "C", 74, 900_000)    # fills seller's #1 need
    b_off = mkprospect("OffW", "LW", 72, 900_000)    # cheaper, off-need
    c1 = mkprospect("D1", "LD", 76, 900_000)
    c2 = mkprospect("D2", "RD", 77, 900_000)
    pros = [a_need, b_off, c1, c2,
            mkprospect("F1", "C", 78, 900_000),
            mkprospect("F2", "RW", 79, 900_000)]
    va = te.asset_value(a_need)
    bidder = team("BID", roster=pros)
    seller = mkt("SELL", no_center_roster("X"))
    check("seller #1 need is C", te.team_needs(seller)[0] == "C")
    star = mkp("Target", PlayerPosition.CENTER, 27, 70, 5_000_000)
    app = SimpleNamespace(user_team=SimpleNamespace(team_name="USER"))
    league = SimpleNamespace(teams=[bidder, seller])
    # Target fits exactly one asset: the need-filler must sort first even
    # though the off-need winger is cheaper.
    ask = va * 0.95
    p1, p2 = det_bid()
    with p1, p2:
        got = tm.build_bid(app, league, bidder, star, seller, ask,
                           n_bidders=1)
    check("one-asset bundle", len(got) == 1, len(got))
    if got:
        check("need-filling asset bundled first",
              got[0].full_name == "NeedC", got[0].full_name)


def test_d44_threading_wiring():
    print("== D44: n_bidders threaded from the bidding rounds (wiring) ==")
    src = open(os.path.join(WT, "trade_market.py")).read()
    check("bidding rounds pass n_bidders=len(bidders)",
          "n_bidders=len(bidders)" in src)


def test_d44_build_bid_never_offers_untouchable():
    print("== D44/D31: build_bid never offers the franchise tier ==")
    # UNTOUCHABLE by franchise_score (88ovr/21/A/1st-round ~ 84) but NOT
    # top-3 by trade value: five 90+ prospects outrank it. Only the D31
    # tier rule keeps it out of the bundle -- the old top-3 cutoff would
    # have offered it.
    unt = P("Franchise", 88, 21, 8_000_000, 4, "A", 1, "X")
    pros = [unt] + [P(f"Pq{i}", 90 + i, 21, 900_000) for i in range(5)]
    t = team("BID")
    tiers = te.asset_franchise_tiers(t, pros, None)
    check("fixture is UNTOUCHABLE-tier",
          tiers[unt.id][0] == "UNTOUCHABLE", tiers[unt.id])
    top3 = sorted((te.player_trade_value(p) for p in pros), reverse=True)[:3]
    check("fixture is NOT top-3 by trade value",
          te.player_trade_value(unt) < min(top3),
          (te.player_trade_value(unt), top3))
    bidder = team("BID", roster=pros)
    seller = mkt("SELL", no_center_roster("X"))
    star = mkp("Target", PlayerPosition.CENTER, 27, 80, 5_000_000)
    app = SimpleNamespace(user_team=SimpleNamespace(team_name="USER"))
    league = SimpleNamespace(teams=[bidder, seller])
    got = tm.build_bid(app, league, bidder, star, seller, 50_000,
                       n_bidders=4)
    check("huge ask still never offers the franchise piece",
          all(a.full_name != "Franchise" for a in got),
          [a.full_name for a in got])


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_tier_label_shim()
    test_franchise_tiers()
    test_d31_flat_no()
    test_d31_no_sweetener()
    test_d40_gate_units()
    test_d40_tax_wiring()
    test_d40_bitter_paths_behavioral()
    test_d42_stinginess_delta()
    test_d42_greed_anchor()
    test_d42_full_shortfall()
    test_d43_seller_bids()
    test_d43_neutral_opportunistic()
    test_d43_headliner_tiers()
    test_d44_overpay_to_close()
    test_d44_closers_premium()
    test_d44_seller_need_bundling()
    test_d44_threading_wiring()
    test_d44_build_bid_never_offers_untouchable()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILURES:", FAIL)
        sys.exit(1)
