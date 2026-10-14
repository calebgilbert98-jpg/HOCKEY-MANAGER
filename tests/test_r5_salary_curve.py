"""R5: salary-curve smoothness regression tests.

Acceptance: max |ask(ovr+1) - ask(ovr)| <= $0.6M for ovr 70-99.
The old tiered bands had $0.75-0.83M/point in-band steps and
$2.08M/$4.8M/$6.2M cliffs at the 94/95, youth and veteran edges.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from salary_cap_system import base_ask_dollars as ask


def test_r5_max_adjacent_step_all_ages_positions():
    worst = 0
    for age in range(18, 41):
        for pos in ("", "C", "G", "D", "W", "LW", "RD"):
            for on_elc in (False, True):
                prev = None
                for ovr in range(70, 100):
                    v = ask(ovr, age, on_elc, pos)
                    if prev is not None:
                        worst = max(worst, abs(v - prev))
                    prev = v
    assert worst <= 600_000, f"max adjacent step ${worst/1e6:.3f}M > $0.6M"


def test_r5_star_run_values():
    # 89 anchors the $9M core top; 89->99 climbs $0.5M/point to $14M.
    assert ask(89, 27, False, "") == 9_000_000
    assert ask(90, 27, False, "") == 9_500_000
    assert ask(95, 27, False, "") == 12_000_000
    assert ask(99, 27, False, "") == 14_000_000
    # No 94->95 jump anymore (was +$2.08M).
    assert abs(ask(95, 27, False, "") - ask(94, 27, False, "")) <= 600_000


def test_r5_band_edges_gone():
    # Old youth edge: 79->80 jumped +$4.83M at age 24. Old veteran edge:
    # 81->82 jumped +$6.18M at age 33. Both must be smooth now.
    assert abs(ask(80, 24, False, "") - ask(79, 24, False, "")) <= 600_000
    assert abs(ask(82, 33, False, "") - ask(81, 33, False, "")) <= 600_000


def test_r5_low_end_bands_preserved():
    # Youth/veteran bands keep their old values through 74 OVR
    # (only the cliff edges were fixed, not the discount levels).
    # The veteran expectation is derived from league_minimum_salary(),
    # not hard-coded: the minimum escalates by season, so a fixed
    # constant would rot (Copilot PR #11 review).
    from salary_cap_system import league_minimum_salary
    assert abs(ask(70, 24, False, "") - 2_285_714) < 2  # old youth band
    _vlo = int(league_minimum_salary())
    _expected_vet70 = _vlo + (3_750_000 - _vlo) * (8 / 28)
    assert abs(ask(70, 35, False, "") - _expected_vet70) < 2


def test_r5_monotonic():
    for age in (20, 24, 27, 33, 38):
        vals = [ask(o, age, False, "") for o in range(70, 100)]
        assert all(b >= a for a, b in zip(vals, vals[1:])), f"not monotonic at age {age}"


def test_r5_elc_band_flat():
    # ELC band is flat by design: no ovr cliff possible, values tiny.
    vals = [ask(o, 20, False, "") for o in range(70, 100)]
    assert max(vals) - min(vals) <= 300_000
    assert max(vals) <= 1_100_000


def test_r5_ai_estimate_no_duplicated_bands():
    # Anti-rot: the AI's estimate must delegate to base_ask_dollars, not
    # duplicate the band table (the duplication is how the cliffs survived
    # in that path). ai_team_management.py must not contain the old band
    # literals anymore.
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "ai_team_management.py")
    src = open(path).read()
    assert "14_000_000, 19_000_000" not in src
    assert "9_000_000, 13_500_000" not in src
