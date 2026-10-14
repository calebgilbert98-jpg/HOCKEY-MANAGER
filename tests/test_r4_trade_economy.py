"""R4 acceptance: trade economy -- franchise pricing + contract term factor.

1. player_trade_value prices contract term: a 95 OVR 24yo with 6 yrs term
   must clear >= 3.2 first-round equivalents (>= 3200 pick points); the
   same player as a pending UFA (final year) must price <= 60% of the
   term version. Curve must be monotonic in years_remaining.
2. franchise_price_mult returns the loyalty tiers (10x/4x/2x, 1.0 for
   non-franchise pieces).
3. franchise_price_mult is wired into the actual ask/accept negotiation
   path (ai_consider_trade): the same overpay offer flips from accept to
   reject when the wiring is active vs neutralized.
4. player_trade_value_breakdown recomputes the identical total and shows
   the Contract term component.

Deterministic: all randomness seeded; accept/reject margins are far from
the greed noise band.
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from types import SimpleNamespace

from game_classes import Player, PlayerPosition, Contract, Team, DraftPick
import trade_engine as te


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _mkplayer(ovr, age, term, salary=12_000_000, pot="A", pos=PlayerPosition.CENTER):
    p = Player("Test", "Star", age, pos)
    p.overall_rating = lambda: ovr  # noqa: E731 -- deterministic test overall
    p.potential_grade = pot
    p.contract = Contract(salary=salary, years_remaining=term)
    return p


def _mkteam(name, staff_attrs):
    t = Team(name, "City", "Div", "Conf")
    t.roster = []
    t.draft_picks = {}
    role = SimpleNamespace(name="GENERAL_MANAGER")
    t.staff = [SimpleNamespace(role=role, **staff_attrs)]
    return t


_HI_LOYALTY = dict(years_with_team=10, man_management=100, leadership=100,
                   controversy=0, ambition="lifer", determination=80,
                   adaptability=80, working_with_youngsters=80,
                   player_development=80, control_need=50)
_MED_LOYALTY = dict(years_with_team=3, man_management=60, leadership=60,
                    controversy=40, ambition="climb", determination=60,
                    adaptability=60, working_with_youngsters=60,
                    player_development=60, control_need=50)
_LO_LOYALTY = dict(years_with_team=0, man_management=20, leadership=20,
                   controversy=90, ambition="climb", determination=40,
                   adaptability=40, working_with_youngsters=40,
                   player_development=40, control_need=50)


def _franchise_star(team):
    """A genuine franchise piece: young generational talent, homegrown,
    1st-round pedigree -- clears the franchise_score 80 bar."""
    p = Player("Gen", "Star", 20, PlayerPosition.CENTER)
    p.overall_rating = lambda: 95  # noqa: E731
    p.potential_grade = "A"
    p.contract = Contract(salary=9_000_000, years_remaining=6)
    p.draft_round = 1
    p.drafted_by = team.team_name
    return p


# ---------------------------------------------------------------------------
# 1. term factor -- acceptance bars
# ---------------------------------------------------------------------------

def test_term_premium_95_ovr_6yr_ge_32_firsts():
    """R4 acceptance: 95 OVR 24yo with 6 yrs term >= 3.2 first-rounders."""
    v = te.player_trade_value(_mkplayer(95, 24, 6))
    assert v >= 3200, f"95/24/6yr must price >= 3200 pts, got {v}"


def test_pending_ufa_le_60pct_of_term_version():
    """R4 acceptance: pending UFA (final year) <= 60% of the 6yr version.

    Uses a UFA-eligible veteran (30yo): a 24yo with 1yr left is a pending
    RFA, not a UFA (rfa_system.is_ufa_eligible: 27+ or 7+ seasons).
    """
    v6 = te.player_trade_value(_mkplayer(95, 30, 6))
    v1 = te.player_trade_value(_mkplayer(95, 30, 1))
    assert v1 <= 0.60 * v6, (
        f"pending UFA {v1} must be <= 60% of 6yr term version {v6}")


def test_final_year_rfa_keeps_control_value():
    """A final-year player who will still be RFA at expiry is not a
    rental: no 0.90 discount (RFA rights = retained team control)."""
    v6 = te.player_trade_value(_mkplayer(95, 24, 6))
    v1 = te.player_trade_value(_mkplayer(95, 24, 1))
    # 24yo: 24+1 < 27 and no accrued seasons -> RFA -> 1.0x, so the ratio
    # is exactly the 6yr premium inverse: 1/1.70 = 58.8% <= 60%.
    assert v1 == v6 / 1.70 or abs(v1 / v6 - 1 / 1.70) < 0.001, (
        f"24yo RFA 1yr {v1} should be 6yr {v6} / 1.70")
    assert v1 <= 0.60 * v6


def test_ufa_at_expiry_projection():
    """26yo with 1yr left will be 27 at expiry -> UFA -> rental discount."""
    v = te.player_trade_value(_mkplayer(90, 26, 1))
    v2 = te.player_trade_value(_mkplayer(90, 26, 2))
    # 1yr UFA-projected (0.90) < 2yr (1.12): the rental dip is real.
    assert v < v2 * 0.90 / 1.12 + 1, f"26yo 1yr {v} should show rental dip vs 2yr {v2}"
    assert abs(v / v2 - 0.90 / 1.12) < 0.01


def test_term_curve_monotonic_across_terms():
    vals = [te.player_trade_value(_mkplayer(88, 27, t)) for t in range(0, 9)]
    assert all(b <= c for b, c in zip(vals, vals[1:])), (
        f"value must be monotonic in years_remaining: {vals}")
    # spot anchors: long term > medium > rental > unsigned
    assert vals[8] > vals[3] > vals[1] > vals[0]


def test_term_premium_direction_across_ages_overalls():
    """Term premium applies generally, not just to the canonical star."""
    for ovr, age in ((95, 24), (88, 27), (82, 30), (76, 22)):
        v_long = te.player_trade_value(_mkplayer(ovr, age, 7))
        v_short = te.player_trade_value(_mkplayer(ovr, age, 1))
        assert v_long > v_short, (
            f"ovr={ovr} age={age}: 7yr {v_long} must exceed 1yr {v_short}")


def test_no_contract_stays_neutral():
    p = _mkplayer(85, 28, 4)
    p.contract = None
    v = te.player_trade_value(p)  # must not raise; term factor skipped
    assert v > 0


# ---------------------------------------------------------------------------
# 2. franchise_price_mult tiers
# ---------------------------------------------------------------------------

def test_franchise_price_mult_loyalty_tiers():
    t_hi = _mkteam("HiLoy", _HI_LOYALTY)
    t_med = _mkteam("MedLoy", _MED_LOYALTY)
    t_lo = _mkteam("LoLoy", _LO_LOYALTY)
    assert te.franchise_price_mult(_franchise_star(t_hi), t_hi) == 10.0
    assert te.franchise_price_mult(_franchise_star(t_med), t_med) == 4.0
    assert te.franchise_price_mult(_franchise_star(t_lo), t_lo) == 2.0


def test_franchise_price_mult_non_franchise_is_one():
    t = _mkteam("Club", _HI_LOYALTY)
    depth = _mkplayer(72, 30, 2, salary=2_000_000, pot="F")
    assert te.franchise_price_mult(depth, t) == 1.0


# ---------------------------------------------------------------------------
# 3. wiring into the ask/accept negotiation path
# ---------------------------------------------------------------------------

def test_franchise_wiring_in_negotiation_path():
    """The same ~3.4x overpay for a franchise piece must REJECT with the
    wiring active and ACCEPT with it neutralized -- proving the multiplier
    lives in the ask/accept path, not just in a helper."""
    random.seed(20261013)
    partner = _mkteam("Partner", _HI_LOYALTY)
    star = _franchise_star(partner)
    partner.roster = [star]

    user = _mkteam("User", _HI_LOYALTY)
    picks = [DraftPick(2027, 1, "User", "User", i + 1, False, "")
             for i in range(12)]
    user.draft_picks = {2027: picks}
    offer_value = sum(te.asset_value(p) for p in picks)
    star_value = te.player_trade_value(star)
    assert offer_value > 3.0 * star_value, "test needs a clear overpay"

    resp_wired = te.ai_consider_trade(
        partner, list(picks), [star], user_team=user, patience=1.0)
    assert resp_wired.decision == "reject", (
        f"10x franchise ask must reject a 3.4x overpay, got "
        f"{resp_wired.decision}")

    real = te.franchise_price_mult
    te.franchise_price_mult = lambda _a, _t: 1.0  # noqa: E731
    try:
        resp_plain = te.ai_consider_trade(
            partner, list(picks), [star], user_team=user, patience=1.0)
    finally:
        te.franchise_price_mult = real
    assert resp_plain.decision == "accept", (
        f"without the franchise ask the same offer must accept, got "
        f"{resp_plain.decision}")


# ---------------------------------------------------------------------------
# 4. breakdown mirrors the engine
# ---------------------------------------------------------------------------

def test_breakdown_matches_engine_with_term():
    p = _mkplayer(95, 24, 6)
    total, comps = te.player_trade_value_breakdown(p)
    assert total == te.player_trade_value(p), (
        f"breakdown {total} != engine {te.player_trade_value(p)}")
    labels = [c["label"] for c in comps]
    assert "Contract term" in labels, f"missing Contract term in {labels}"
