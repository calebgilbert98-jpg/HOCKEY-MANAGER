"""Parity test: player_trade_value_breakdown total must equal
player_trade_value for the same player, exactly.

Covers the REV-E3 findings:
  1. Age-band boundary drift (engine <=21 vs breakdown <=23 for the 1.3x
     youth premium). Per commit 4121d47 ("extend 1.3x youth premium to age
     23 (was 21)"), the documented intent is <=23 everywhere.
  2. Trade-request discount (wants-out x0.75; risk >=75/50/25 -> x0.70/0.80/0.90)
     applied by the engine after the RFA-impasse multiplier -- the
     breakdown must mirror it with its own component line.

Acceptance criteria:
  AC1: breakdown(player)[0] == player_trade_value(player, team) EXACTLY
       for every player in the matrix (ages 20-35, risk levels, RFA, etc.)
  AC2: component deltas sum to the total within per-component truncation
       tolerance (|base + sum(deltas) - total| <= number of components)
  AC3: age-band continuity: identical 22yo and 23yo get the same 1.3x
       youth multiplier as a 21yo (no 22-23 hole); bands are contiguous
       (<=23 -> 1.3, 24-29 -> 1.2, 30-32 -> 1.0, 33-34 -> 0.8, 35+ -> 0.5)
  AC4: existing trade-engine behaviour elsewhere unchanged (spot checks)
"""
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trade_engine
from trade_engine import player_trade_value, player_trade_value_breakdown


class FakeContract:
    def __init__(self, salary):
        self.salary = salary


def make_player(*, age, ovr=76, risk=0, wants_out=False, rfa_impasse=False,
                potential_grade='B', position=None, grades=None, salary=None):
    """Minimal stub exercising the same attrs the engine/breakdown read."""
    p = SimpleNamespace()
    p.age = age
    p.overall_rating = lambda: ovr  # noqa: E731 - stub
    p.potential_grade = potential_grade
    # Fair-market salary so the contract-efficiency branch stays neutral
    # unless a specific salary is requested.
    p.contract = FakeContract(salary if salary is not None else 4_000_000)
    p.primary_position = position
    p.recent_game_grades = list(grades) if grades else []
    p.trade_request_risk = risk
    p.happiness = 20 if wants_out else 70
    p.loyalty = 40 if wants_out else 60
    return p


def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}" + (f" -- {detail}" if detail and not cond else ""))
    return cond


def main():
    ok = True
    team = SimpleNamespace(team_name="Test Club")

    print("== AC1: breakdown total == engine value (exact) ==")
    cases = []
    # Age sweep: every band boundary and interior point.
    for age in (18, 20, 21, 22, 23, 24, 25, 27, 29, 30, 32, 33, 34, 35, 38):
        cases.append((f"age {age}", dict(age=age)))
    # Trade-request risk ladder (below/at/above each threshold).
    for risk in (0, 24, 25, 49, 50, 74, 75, 80, 100):
        cases.append((f"age 27 risk {risk}", dict(age=27, risk=risk)))
    # wants_out flag beats the risk ladder in the engine.
    cases.append(("wants_out", dict(age=27, wants_out=True)))
    cases.append(("wants_out + risk 100", dict(age=27, wants_out=True, risk=100)))
    # Young + trade request (both fixes interact here).
    cases.append(("age 22 risk 80", dict(age=22, risk=80)))
    cases.append(("age 23 wants_out", dict(age=23, wants_out=True)))
    # Overpaid / bargain contract branches.
    cases.append(("overpaid", dict(age=27, salary=12_000_000)))
    cases.append(("bargain", dict(age=27, salary=1_000_000)))
    # Goalie premium (80+ OVR goalie).
    from game_classes import PlayerPosition
    cases.append(("goalie 82ovr", dict(age=27, ovr=82, position=PlayerPosition.GOALIE)))
    # Performance slump / heater.
    cases.append(("slump", dict(age=27, grades=[30, 32, 35, 31])))
    cases.append(("heater", dict(age=27, grades=[70, 72, 68, 71])))
    # Floor: terrible player must clamp at 10 in both.
    cases.append(("floor", dict(age=35, ovr=63, salary=12_000_000, risk=100)))

    for label, kwargs in cases:
        p = make_player(**kwargs)
        engine_val = player_trade_value(p, team)
        total, comps = player_trade_value_breakdown(p, team)
        ok &= check(f"{label}: engine={engine_val} breakdown={total}",
                    engine_val == total,
                    f"divergence of {total - engine_val}")

    print("== AC1b: RFA-impasse path ==")
    p = make_player(age=24)
    orig = trade_engine._rfa_system.rfa_rights_at_impasse
    trade_engine._rfa_system.rfa_rights_at_impasse = lambda pl: True
    try:
        engine_val = player_trade_value(p, team)
        total, comps = player_trade_value_breakdown(p, team)
        ok &= check(f"rfa impasse: engine={engine_val} breakdown={total}",
                    engine_val == total,
                    f"divergence of {total - engine_val}")
        ok &= check("rfa impasse component present",
                    any(c['label'] == 'RFA-impasse rights' for c in comps))
        # RFA impasse + trade request: engine applies impasse first, then request.
        p.trade_request_risk = 80
        engine_val = player_trade_value(p, team)
        total, comps = player_trade_value_breakdown(p, team)
        ok &= check(f"impasse+risk80: engine={engine_val} breakdown={total}",
                    engine_val == total,
                    f"divergence of {total - engine_val}")
        ok &= check("trade-request component present",
                    any(c['label'] == 'Trade-request discount' for c in comps))
    finally:
        trade_engine._rfa_system.rfa_rights_at_impasse = orig

    print("== AC2: component deltas sum to total (within truncation) ==")
    for label, kwargs in cases:
        p = make_player(**kwargs)
        total, comps = player_trade_value_breakdown(p, team)
        base_delta = comps[0]['delta'] if comps else 0
        reconstructed = base_delta + sum(c['delta'] for c in comps[1:])
        # Each displayed delta is int()-truncated, so the sum can drift by
        # at most one point per component; the max(10, ...) floor is exact.
        tol = max(1, len(comps))
        ok &= check(f"{label}: deltas sum within {tol}",
                    abs(reconstructed - total) <= tol,
                    f"reconstructed={reconstructed} total={total}")

    print("== AC3: age-band continuity (no 22-23 hole) ==")
    def engine_only_age_mult(age):
        # Isolate the age-curve multiplier by comparing against a 30yo
        # (1.0 band) with identical attributes.
        a = make_player(age=age, ovr=76, potential_grade='F')
        b = make_player(age=30, ovr=76, potential_grade='F')
        return player_trade_value(a, team) / player_trade_value(b, team)

    for age, expected in ((21, 1.3), (22, 1.3), (23, 1.3), (24, 1.2),
                          (29, 1.2), (30, 1.0), (33, 0.8), (35, 0.5)):
        got = engine_only_age_mult(age)
        ok &= check(f"engine age {age}: mult ~{expected}",
                    abs(got - expected) < 0.01, f"got {got:.3f}")
    # Breakdown labels mirror the engine bands.
    p = make_player(age=22)
    _, comps = player_trade_value_breakdown(p, team)
    age_comp = next(c for c in comps if c['label'] == 'Age curve')
    ok &= check("breakdown age-22 label is 23-and-under x1.3",
                age_comp['detail'] == "23-and-under: x1.3",
                age_comp['detail'])
    # The reviewer example: 22yo must no longer diverge.
    p22 = make_player(age=22)
    ok &= check("22yo parity (was 1326 vs 1020)",
                player_trade_value(p22, team) == player_trade_value_breakdown(p22, team)[0])

    print("== AC4: trade-request discount ladder ==")
    base_p = make_player(age=27, risk=0)
    base_val = player_trade_value(base_p, team)
    for risk, mult in ((25, 0.90), (50, 0.80), (75, 0.70)):
        p = make_player(age=27, risk=risk)
        got = player_trade_value(p, team) / base_val
        ok &= check(f"risk {risk}: engine mult ~{mult}", abs(got - mult) < 0.01,
                    f"got {got:.3f}")
        total, comps = player_trade_value_breakdown(p, team)
        tr = next((c for c in comps if c['label'] == 'Trade-request discount'), None)
        ok &= check(f"risk {risk}: breakdown has labeled component", tr is not None)
        if tr:
            ok &= check(f"risk {risk}: component detail shows x{mult}",
                        f"x{mult:g}" in tr['detail'], tr['detail'])
    p = make_player(age=27, wants_out=True)
    got = player_trade_value(p, team) / base_val
    ok &= check("wants_out: engine mult ~0.75", abs(got - 0.75) < 0.01, f"got {got:.3f}")

    print()
    print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


def test_main_returns_zero():
    """The script's own main() returns 0 iff all its internal checks pass."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
