"""R7 acceptance: trade AI passivity -- salary-aware bid construction.

1. _cap_ok_after is LTIR-aware: a club with LTIR relief bids against the
   EFFECTIVE cap (cap + relief), the same rule the day gate enforces.
2. build_bid pass 2 (salary matching): a cap-blocked bidder whose picks
   all fail the dry-check assembles a bid out of movable contracts.
3. build_bid pass 3 (retention): with no salary package available, the
   bidder proposes minimal seller retention (slot preflighted); the
   terms ride on Bid.retention into ai_consider_trade / execute_trade.
4. No retention is ever proposed on user-sale listings (allow_retention).
5. Anti-flip guard: execute_trade blocks a same-player Seller<->Buyer
   reversal within a season, allows it the next season, and allows
   non-reversal chains.
6. Bid stays a plain list for every existing call-site idiom.

Deterministic: all randomness seeded; synthetic players/teams.
"""
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from types import SimpleNamespace

from game_classes import Player, PlayerPosition, Contract, Team, DraftPick
import trade_engine as te
import trade_market as tm
import salary_cap_system as scs

random.seed(20261014)

_PID = [1000]


def _mkplayer(name, ovr, age, salary, pos=PlayerPosition.CENTER, term=3):
    _PID[0] += 1
    p = Player(name, "T", age, pos)
    p.id = _PID[0]
    p.overall_rating = lambda: ovr  # noqa: E731 -- deterministic test overall
    p.potential_grade = "B"
    p.contract = Contract(salary=salary, years_remaining=term)
    return p


def _mkteam(name, roster, picks=None):
    t = Team(name, "City", "Div", "Conf")
    t.salary_cap = 104_000_000
    t.roster = list(roster)
    t.ahl_roster = []
    t.prospects = []
    t.draft_picks = picks or {}
    t.retained_salary = []
    return t


def _fill_to_space(team, space):
    """Add $950k filler skaters until cap space lands in [space, space+950k].

    The lower bound is exact (loop stops only once charge is low enough);
    the upper bound is one filler of overshoot. Tests that need a precise
    space band should size the other salaries around this window.
    """
    target_charge = 104_000_000 - space - 950_000
    n = 0
    while scs.total_cap_charge(team) < target_charge and n < 200:
        team.roster.append(_mkplayer("Fill", 70, 24, 950_000))
        n += 1
    got = int(104_000_000 - scs.total_cap_charge(team))
    assert space <= got <= space + 950_000, (space, got)
    return got


def _exact_space(team, space):
    """Set cap space to EXACTLY `space` (for pass-2/pass-3 boundary tests).

    Fills with $950k skaters plus one remainder skater; the remainder's
    odd salary keeps it out of the salary-matching pool's top ranks
    (70ovr, cheap) so it never perturbs which pass fires.
    """
    cur = int(scs.total_cap_charge(team))
    need = (104_000_000 - space) - cur
    assert need > 0, need
    n_full, rem = divmod(need, 950_000)
    for _ in range(int(n_full)):
        team.roster.append(_mkplayer("Fill", 70, 24, 950_000))
    if rem:
        team.roster.append(_mkplayer("FillR", 70, 24, int(rem)))
    got = int(104_000_000 - scs.total_cap_charge(team))
    assert got == space, (space, got)
    return got


def _mkpicks(team_name):
    return {2027: [DraftPick(2027, 1, team_name, team_name),
                   DraftPick(2027, 2, team_name, team_name),
                   DraftPick(2027, 3, team_name, team_name)]}


# ---------------------------------------------------------------------------
# 1. LTIR-aware cap dry-check
# ---------------------------------------------------------------------------

def test_effective_cap_space_counts_ltir_relief():
    team = _mkteam("LTIR", [_mkplayer("A", 80, 28, 20_000_000)])
    got_space = _fill_to_space(team, 4_000_000)  # $4M nominal space
    assert 3_000_000 <= got_space <= 5_000_000, got_space
    assert te._effective_cap_space(team) == got_space
    # Incoming $6M deal: blocked on the raw cap ...
    piece = _mkplayer("Piece", 85, 27, 6_000_000)
    assert te._cap_ok_after(team, [], [piece]) is False
    # ... but legal once the club holds $5M of LTIR relief (day-gate rule).
    import ir_system as _irs
    _real = _irs.ltir_relief
    _irs.ltir_relief = lambda t: 5_000_000
    try:
        assert te._effective_cap_space(team) == got_space + 5_000_000
        assert te._cap_ok_after(team, [], [piece]) is True
    finally:
        _irs.ltir_relief = _real


# ---------------------------------------------------------------------------
# 2. Salary-matching bid construction
# ---------------------------------------------------------------------------

def _goalies():
    return [_mkplayer("G1", 78, 28, 2_000_000, pos=PlayerPosition.GOALIE),
            _mkplayer("G2", 74, 25, 1_200_000, pos=PlayerPosition.GOALIE)]


def _skaters(n):
    # Bodies to satisfy the dress-minimum guard (18 skaters + 2 goalies).
    return [_mkplayer(f"D{i}", 72, 26, 1_000_000) for i in range(n)]


def _seller_with_piece(salary=5_000_000):
    piece = _mkplayer("Star", 87, 29, salary)
    seller = _mkteam("SEL", [_mkplayer("Mate", 78, 30, 3_000_000)] + _goalies())
    seller.roster.append(piece)
    _fill_to_space(seller, 10_000_000)
    return seller, piece


def test_build_bid_salary_matching_when_picks_blocked():
    seller, piece = _seller_with_piece()
    # Bidder: ~$2M space. Three 88ovr stars sit top-3 by value (protected
    # core, not movable); the $4M 80ovr depth contract is the movable
    # salary. Picks available.
    stars = [_mkplayer(f"S{i}", 88, 27, 8_000_000) for i in range(3)]
    depth = _mkplayer("Depth", 80, 28, 4_000_000)
    bidder = _mkteam("BID", stars + [depth,
                                     _mkplayer("Prosp", 74, 21, 900_000),
                                     _mkplayer("Elc", 71, 20, 850_000)]
                     + _goalies(), picks=_mkpicks("BID"))
    space = _fill_to_space(bidder, 2_000_000)
    assert 2_000_000 <= space <= 3_000_000, space
    ask = float(te.player_trade_value(piece))
    bid = tm.build_bid(None, None, bidder, piece, seller, ask)
    # The old code returned [] here (every pick failed the dry-check, and
    # the greedy per-asset check could not pair salary).
    assert len(bid) > 0, "salary matching produced no bid"
    assert isinstance(bid, list)
    assert bid.retention == {}
    names = [getattr(a, "full_name", "") for a in bid]
    assert any("Depth" in n for n in names), f"no salary in bid: {names}"
    # Whole package is cap-legal for the bidder.
    assert te._cap_ok_after(bidder, list(bid), [piece]) is True


def test_build_bid_empty_when_nothing_can_fit():
    seller, piece = _seller_with_piece()
    # Bidder: $2M space, no movable salary, no picks, retention disallowed.
    bidder = _mkteam("BROKE", [_mkplayer("Cheap", 72, 26, 900_000)])
    _fill_to_space(bidder, 2_000_000)
    ask = float(te.player_trade_value(piece))
    bid = tm.build_bid(None, None, bidder, piece, seller, ask,
                       allow_retention=False)
    assert len(bid) == 0
    assert bid.retention == {}


# ---------------------------------------------------------------------------
# 3. Retention proposals
# ---------------------------------------------------------------------------

def test_build_bid_proposes_minimal_retention():
    # $5M piece, ~$3M space: shortfall $2M needs 40% retention (proposable),
    # while no 2-player bundle of sub-$1M contracts ($1.9M max shed) covers
    # the $2.1M salary need -- pass 2 deterministically fails, pass 3 fires.
    # The seller is compensated: bid must meet target + retention premium
    # (100 pts per $1M of annual retained hit = half the D46b dump rate).
    seller, piece = _seller_with_piece(salary=5_000_000)
    picks = {2027: [DraftPick(2027, 1, "TIGHT", "TIGHT"),
                    DraftPick(2027, 2, "TIGHT", "TIGHT")],
             2028: [DraftPick(2028, 1, "TIGHT", "TIGHT"),
                    DraftPick(2028, 3, "TIGHT", "TIGHT")],
             # Third 1st: the consent price (target + retention premium)
             # needs three first-rounders' worth of value.
             2029: [DraftPick(2029, 1, "TIGHT", "TIGHT")]}
    bidder = _mkteam("TIGHT", [_mkplayer("C1", 73, 26, 950_000),
                               _mkplayer("C2", 72, 27, 900_000)]
                     + _goalies(), picks=picks)
    # Exact $2.5M space: pass 2 needs $2.6M of movable salary (max 2-player
    # shed is $1.9M -> fails deterministically); pass 3 needs exactly 50%.
    space = _exact_space(bidder, 2_500_000)
    ask = float(te.player_trade_value(piece))
    bid = tm.build_bid(None, None, bidder, piece, seller, ask)
    assert len(bid) > 0, "retention pass produced no bid"
    # Minimal pct covering the shortfall.
    shortfall = 5_000_000 - space
    expect = int(math.ceil(shortfall * 100.0 / 5_000_000))
    assert 1 <= expect <= 50, (space, expect)
    assert bid.retention == {piece.id: expect}, bid.retention
    # Consent price: bid value covers target + premium (100 pts per $1M
    # of annual retained hit).
    premium = int(round(100.0 * (5_000_000 * expect / 100.0) / 1_000_000))
    bid_val = sum(te.asset_value(a) for a in bid)
    assert bid_val >= ask + premium, (bid_val, ask, premium)
    # The retention-aware dry-check prices it as legal.
    assert te._cap_ok_after(bidder, list(bid), [piece],
                            retention=bid.retention) is True


def test_retention_bid_refused_when_consent_price_unreachable():
    # The seller is never asked to retain for free: if the bidder's
    # picks/prospects can't reach target + retention premium, pass 3
    # returns None (no retention deal) rather than a free-retention bid.
    seller, piece = _seller_with_piece(salary=5_000_000)
    # Only a single 3rd-rounder: far short of the consent price.
    picks = {2027: [DraftPick(2027, 3, "TIGHT", "TIGHT")]}
    bidder = _mkteam("TIGHT", [_mkplayer("C1", 73, 26, 950_000)]
                     + _goalies(), picks=picks)
    _exact_space(bidder, 2_500_000)
    ask = float(te.player_trade_value(piece))
    bid = tm.build_bid(None, None, bidder, piece, seller, ask)
    # Pass 1 (picks) and pass 2 (salary) both fail; pass 3 must refuse
    # rather than grant free retention.
    assert len(bid) == 0, (list(bid), getattr(bid, "retention", None))


def test_no_retention_when_seller_slots_full():
    seller, piece = _seller_with_piece()
    seller.retained_salary = [
        {"player_id": i, "seasons_remaining": 2} for i in range(3)]
    bidder = _mkteam("TIGHT2", [_mkplayer("C1", 73, 26, 950_000)],
                     picks=_mkpicks("TIGHT2"))
    _fill_to_space(bidder, 3_000_000)
    ask = float(te.player_trade_value(piece))
    bid = tm.build_bid(None, None, bidder, piece, seller, ask)
    assert bid.retention == {}, "seller has no free slot"


# ---------------------------------------------------------------------------
# 4. No retention on user-sale listings
# ---------------------------------------------------------------------------

def test_no_retention_proposal_on_user_sale():
    seller, piece = _seller_with_piece()
    bidder = _mkteam("TIGHT3", [_mkplayer("C1", 73, 26, 950_000)],
                     picks=_mkpicks("TIGHT3"))
    _fill_to_space(bidder, 3_000_000)
    ask = float(te.player_trade_value(piece))
    bid = tm.build_bid(None, None, bidder, piece, seller, ask,
                       allow_retention=False)
    assert bid.retention == {}


# ---------------------------------------------------------------------------
# 5. Anti-flip guard
# ---------------------------------------------------------------------------

def _league():
    lg = SimpleNamespace(season_year=2026)
    lg.trade_market = {}
    return lg


def _trade(a, b, give, get, league, day):
    return te.execute_trade(a, b, give, get, date_str=day, league=league)


def test_anti_flip_blocks_same_season_reversal():
    lg = _league()
    p1 = _mkplayer("Flip", 82, 27, 4_000_000)
    a = _mkteam("AAA", [p1] + _goalies() + _skaters(18))
    q = _mkplayer("Q", 75, 26, 2_000_000)
    b = _mkteam("BBB", [q] + _goalies() + _skaters(18))
    pk_ab = DraftPick(2027, 2, "BBB", "BBB")
    b.draft_picks = {2027: [pk_ab]}
    pk_ba = DraftPick(2027, 3, "AAA", "AAA")
    a.draft_picks = {2027: [pk_ba]}

    t1 = _trade(a, b, [p1], [pk_ab], lg, "2026-11-01")
    assert not str(t1.summary).startswith("BLOCKED"), t1.summary
    assert p1 in b.roster

    t2 = _trade(b, a, [p1], [pk_ba], lg, "2026-12-15")
    assert str(t2.summary).startswith("BLOCKED:"), t2.summary
    assert "flip" in t2.summary.lower()
    assert p1 in b.roster  # nothing moved


def test_anti_flip_allows_next_season_and_chains():
    lg = _league()
    p1 = _mkplayer("Flip2", 82, 27, 4_000_000)
    a = _mkteam("AAA2", [p1] + _goalies() + _skaters(18))
    q = _mkplayer("Q2", 75, 26, 2_000_000)
    b = _mkteam("BBB2", [q] + _goalies() + _skaters(18))
    r = _mkplayer("R2", 76, 25, 2_500_000)
    c = _mkteam("CCC2", [r] + _goalies() + _skaters(18))
    for t, nm in ((a, "AAA2"), (b, "BBB2"), (c, "CCC2")):
        t.draft_picks = {2027: [DraftPick(2027, 4, nm, nm)]}

    t1 = _trade(a, b, [p1], b.draft_picks[2027], lg, "2026-11-01")
    assert not str(t1.summary).startswith("BLOCKED"), t1.summary
    # B -> C is not a reversal: allowed.
    t2 = _trade(b, c, [p1], c.draft_picks[2027], lg, "2026-12-01")
    assert not str(t2.summary).startswith("BLOCKED"), t2.summary
    assert p1 in c.roster
    # Next season the original reversal is allowed again.
    lg.season_year = 2027
    t3 = _trade(c, a, [p1], a.draft_picks[2027], lg, "2027-10-05")
    assert not str(t3.summary).startswith("BLOCKED"), t3.summary


def test_flip_guard_needs_no_league_gracefully():
    # league=None: guard fails open, deal completes.
    p1 = _mkplayer("Solo", 80, 27, 3_000_000)
    a = _mkteam("AA3", [p1] + _goalies() + _skaters(18))
    b = _mkteam("BB3", [_mkplayer("QQ", 74, 26, 1_500_000)] + _goalies() + _skaters(18))
    t1 = te.execute_trade(a, b, [p1], [b.roster[0]], date_str="2026-11-01",
                          league=None)
    assert not str(t1.summary).startswith("BLOCKED"), t1.summary


# ---------------------------------------------------------------------------
# 6. Bid list-compatibility (existing call-site idioms)
# ---------------------------------------------------------------------------

def test_bid_list_idioms():
    b = tm.Bid()
    assert not b
    assert list(b) == []
    assert b.retention == {}
    b2 = tm.Bid([1, 2], {9: 25})
    assert len(b2) == 2 and list(b2) == [1, 2]
    assert b2.retention == {9: 25}
    assert sum(b2) == 3


def test_execute_market_deal_threads_bid_retention():
    # The accept-path regression (reviewers A/B/C round 1): a retention-
    # sized bid must reach execute_trade WITH its retention terms. Spy on
    # the engine to prove the terms survive _execute_market_deal.
    from unittest.mock import patch
    from datetime import date
    seller, piece = _seller_with_piece(salary=5_000_000)
    bidder = _mkteam("TIGHT", [_mkplayer("C", 72, 26, 1_000_000)]
                     + _goalies(), picks=_mkpicks("TIGHT"))
    bid = tm.Bid([bidder.draft_picks[2027][0]], {piece.id: 30})
    listing = {"player_id": piece.id, "seller": "SELL",
               "ask_points": 1000, "bids": [], "status": "open"}
    seen = {}
    class _Trade:
        summary = "ok"
    def _spy(s, b, s_assets, b_assets, **kw):
        seen.update(kw)
        return _Trade()
    with patch.object(te, "trade_vetoes", return_value=[]), \
         patch.object(te, "execute_trade", side_effect=_spy):
        ok = tm._execute_market_deal(None, None, listing, piece,
                                    seller, bidder, bid, date(2026, 10, 14))
    assert ok is True
    assert seen.get("retention") == {piece.id: 30}, seen
