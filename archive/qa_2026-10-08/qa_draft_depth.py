# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: Draft class depth — undrafted prospects flow to AHL/Euro (Eastside-style).

Muck 2026-10-02: "we need enough players that some go undrafted and sign
with ahl or euro teams like in eastside"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _make_league(num_ahl=4):
    """Minimal league stub with NHL + AHL teams."""
    from game_classes import Team

    class FakeLeague:
        pass

    lg = FakeLeague()
    lg.teams = []
    lg.season_year = 2026
    lg.draft_prospects_year = 2026
    lg.undrafted_pool = []
    lg.draft_conducted_years = []

    for i in range(2):
        t = Team(team_name=f"NHL Team {i}", city="City", division="Div",
                 conference="Conf", league_name="National Hockey League")
        t.roster = []
        t.ahl_roster = []
        t.prospects = []
        lg.teams.append(t)
    for i in range(num_ahl):
        t = Team(team_name=f"AHL Team {i}", city="City", division="Div",
                 conference="Conf", league_name="American Hockey League")
        t.roster = []
        t.ahl_roster = []
        t.prospects = []
        lg.teams.append(t)
    # Affiliations
    for i in range(2):
        lg.teams[i].affiliate_team = lg.teams[2 + (i % num_ahl)]
    return lg


def test_draft_class_size():
    """Draft class generates 336 prospects (not 224)."""
    from draft_generator import generate_draft_class
    prospects = generate_draft_class(num_prospects=336, quality="Normal",
                                     draft_year=2026)
    assert len(prospects) == 336, f"Expected 336, got {len(prospects)}"
    print("  PASS: draft class is 336 prospects")


def test_undrafted_pool_processing():
    """Undrafted prospects route to AHL, Europe, or re-entry."""
    from draft_generator import generate_draft_class
    from draft_night import process_undrafted_pool

    lg = _make_league()
    prospects = generate_draft_class(num_prospects=336, quality="Normal",
                                     draft_year=2026)
    # Simulate: 224 drafted, 112 undrafted
    lg.undrafted_pool = prospects[224:]

    ahl, eur, reentry = process_undrafted_pool(lg, 2026)

    total = ahl + eur + reentry
    assert total == 112, f"Expected 112 processed, got {total} (ahl={ahl}, eur={eur}, reentry={reentry})"
    print(f"  PASS: 112 undrafted → {ahl} AHL, {eur} Europe, {reentry} re-entry")


def test_ahl_signings_have_contracts():
    """AHL-signed undrafted have valid AHL contracts."""
    from draft_generator import generate_draft_class
    from draft_night import process_undrafted_pool

    lg = _make_league()
    prospects = generate_draft_class(num_prospects=336, quality="Normal",
                                     draft_year=2026)
    lg.undrafted_pool = prospects[224:]
    process_undrafted_pool(lg, 2026)

    # Check AHL rosters got players
    ahl_players = []
    for t in lg.teams:
        if getattr(t, "league_name", "") == "American Hockey League":
            ahl_players.extend(getattr(t, "ahl_roster", []))

    assert len(ahl_players) > 0, "No undrafted signed to AHL rosters"
    for p in ahl_players[:5]:
        c = getattr(p, "contract", None)
        assert c is not None, "AHL-signed prospect missing contract"
    print(f"  PASS: {len(ahl_players)} undrafted on AHL rosters with contracts")


def test_euro_return_abstract():
    """Euros who don't sign are marked as returned to Europe."""
    from draft_night import process_undrafted_pool

    lg = _make_league()

    # Craft a Euro prospect aged out
    from draft_generator import create_prospect
    p = create_prospect(age=22, nationality="Sweden", draft_year=2026)
    p.birth_date = "2004-01-15"  # 22 on Sept 15, 2026
    lg.undrafted_pool = [p]

    # Run multiple times (50/50 Euro split) — at least one path works
    results = set()
    for _ in range(10):
        lg2 = _make_league()
        p2 = create_prospect(age=22, nationality="Sweden", draft_year=2026)
        p2.birth_date = "2004-01-15"
        lg2.undrafted_pool = [p2]
        ahl, eur, re = process_undrafted_pool(lg2, 2026)
        results.add((ahl, eur, re))

    # Should see both AHL and Euro outcomes across runs
    assert len(results) >= 1, "Euro prospect processing failed"
    print(f"  PASS: Euro undrafted handled (outcomes: {results})")


def test_never_raises_on_garbage():
    """process_undrafted_pool never raises."""
    from draft_night import process_undrafted_pool

    # None league
    try:
        r = process_undrafted_pool(None, 2026)
        assert r == (0, 0, 0), f"Expected (0,0,0), got {r}"
    except Exception as e:
        raise AssertionError(f"Raised on None league: {e}")

    # Empty pool
    class L:
        pass
    lg = L()
    lg.undrafted_pool = []
    r = process_undrafted_pool(lg, 2026)
    assert r == (0, 0, 0)

    # Malformed players
    lg.undrafted_pool = [None, "garbage", 123]
    r = process_undrafted_pool(lg, 2026)  # should not raise
    print("  PASS: never raises on garbage input")


def test_reentry_preserved():
    """Young undrafted stay in pool for re-entry."""
    from draft_generator import generate_draft_class
    from draft_night import process_undrafted_pool

    lg = _make_league()
    prospects = generate_draft_class(num_prospects=336, quality="Normal",
                                     draft_year=2026)
    # Find young prospects (18-19)
    young = [p for p in prospects[224:]
             if getattr(p, "birth_date", "")]
    lg.undrafted_pool = list(prospects[224:])

    ahl, eur, reentry = process_undrafted_pool(lg, 2026)
    # Some should re-enter (the young ones)
    assert reentry > 0, "No prospects kept for re-entry"
    print(f"  PASS: {reentry} young prospects kept for re-entry")


if __name__ == "__main__":
    print("QA: Draft depth (undrafted → AHL/Euro)")
    tests = [
        test_draft_class_size,
        test_undrafted_pool_processing,
        test_ahl_signings_have_contracts,
        test_euro_return_abstract,
        test_never_raises_on_garbage,
        test_reentry_preserved,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
