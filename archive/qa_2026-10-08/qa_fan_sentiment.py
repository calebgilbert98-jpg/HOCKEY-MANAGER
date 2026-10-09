# QA: Fan Sentiment Integration (Bucket 5)
"""Verifies sentiment calculation, narrative integration, and cross-season memory."""

import sys
import os

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def make_team(name="Test Team", wins=5, losses=5):
    """Create a mock team for testing."""
    class MockTeam:
        pass
    t = MockTeam()
    t.name = name
    t.recent_results = (["W"] * wins + ["L"] * losses)
    t.games_played = wins + losses
    t.win_pct = wins / max(1, wins + losses)
    t.board_expectation = "bubble_team"
    t.fan_sentiment = 60.0
    t.fan_sentiment_date = None
    return t


def test_sentiment_tiers():
    """Sentiment tiers map correctly."""
    from fan_narratives import sentiment_tier
    from fan_narratives import (TIER_ECSTATIC, TIER_HAPPY, TIER_CONTENT,
                                 TIER_RESTLESS, TIER_ANGRY, TIER_FURIOUS)
    assert sentiment_tier(90) == TIER_ECSTATIC
    assert sentiment_tier(75) == TIER_HAPPY
    assert sentiment_tier(60) == TIER_CONTENT
    assert sentiment_tier(45) == TIER_RESTLESS
    assert sentiment_tier(30) == TIER_ANGRY
    assert sentiment_tier(10) == TIER_FURIOUS
    print("PASS: sentiment tiers")


def test_fan_narrative_generation():
    """Fan narratives generate for extreme tiers."""
    from fan_narratives import generate_fan_narrative

    # Furious fans
    t = make_team()
    t.fan_sentiment = 15.0
    n = generate_fan_narrative(t)
    assert n is not None, "Should generate narrative for furious fans"
    assert "fire" in n["headline"].lower() or "demand" in n["headline"].lower()
    assert n["tier"] == "furious"

    # Ecstatic fans
    t.fan_sentiment = 90.0
    n = generate_fan_narrative(t)
    assert n is not None, "Should generate narrative for ecstatic fans"
    assert n["tier"] == "ecstatic"

    # Content fans (no narrative)
    t.fan_sentiment = 60.0
    n = generate_fan_narrative(t)
    assert n is None, "Should NOT generate narrative for content fans"

    print("PASS: fan narrative generation")


def test_media_tone():
    """Media tone shifts with sentiment."""
    from fan_narratives import media_tone_for_sentiment

    t = make_team()
    t.fan_sentiment = 10.0
    assert media_tone_for_sentiment(t) == "hostile"

    t.fan_sentiment = 90.0
    assert media_tone_for_sentiment(t) == "glowing"

    t.fan_sentiment = 60.0
    assert media_tone_for_sentiment(t) == "neutral"

    print("PASS: media tone shifts")


def test_gameplay_effects():
    """Subtle gameplay effects are bounded."""
    from fan_narratives import crowd_energy_mult, board_pressure, fa_appeal_mult

    t = make_team()

    # Furious
    t.fan_sentiment = 0.0
    assert 0.90 <= crowd_energy_mult(t) <= 0.95, "Crowd energy floor"
    assert 0.9 <= board_pressure(t) <= 1.0, "Board pressure max"
    assert 0.93 <= fa_appeal_mult(t) <= 0.97, "FA appeal floor"

    # Ecstatic
    t.fan_sentiment = 100.0
    assert 1.05 <= crowd_energy_mult(t) <= 1.10, "Crowd energy ceiling"
    assert 0.0 <= board_pressure(t) <= 0.1, "Board pressure min"
    assert 1.03 <= fa_appeal_mult(t) <= 1.07, "FA appeal ceiling"

    print("PASS: gameplay effects bounded")


def test_expectation_adjustment():
    """Performance vs expectations affects baseline."""
    from fan_sentiment import expectation_adjusted_baseline

    # Overachieving: bubble team winning a lot
    t = make_team(wins=8, losses=2)
    t.board_expectation = "bubble_team"  # Expected .500, actually .800
    over = expectation_adjusted_baseline(t)

    # Underachieving: contender losing
    t2 = make_team(wins=2, losses=8)
    t2.board_expectation = "cup_contender"  # Expected .650, actually .200
    under = expectation_adjusted_baseline(t2)

    assert over > 60, f"Overachieving should boost: {over}"
    assert under < 60, f"Underachieving should drag: {under}"

    print("PASS: expectation adjustment")


def test_trade_signing_nudges():
    """Trades and signings nudge sentiment."""
    from fan_sentiment import nudge_for_trade, nudge_for_signing

    t = make_team()
    t.fan_sentiment = 60.0

    # Blockbuster win
    v = nudge_for_trade(t, "blockbuster_won")
    assert v > 60, f"Blockbuster should boost: {v}"

    # Getting fleeced
    t.fan_sentiment = 60.0
    v = nudge_for_trade(t, "fleeced")
    assert v < 60, f"Fleeced should hurt: {v}"

    # Superstar signing
    t.fan_sentiment = 60.0
    v = nudge_for_signing(t, "superstar")
    assert v > 60, f"Superstar signing should boost: {v}"

    print("PASS: trade/signing nudges")


def test_coaching_change_nudge():
    """Coaching changes affect sentiment contextually."""
    from fan_sentiment import nudge_for_coaching_change

    # Firing when fans are furious = relief
    t = make_team()
    t.fan_sentiment = 20.0
    v = nudge_for_coaching_change(t, was_fired=True)
    assert v > 20, f"Firing bad coach should relieve: {v}"

    # Firing when fans are happy = outrage
    t.fan_sentiment = 80.0
    v = nudge_for_coaching_change(t, was_fired=True)
    assert v < 80, f"Firing good coach should anger: {v}"

    print("PASS: coaching change nudges")


def test_cross_season_memory():
    """Cup wins and losing streaks affect future sentiment bounds."""
    from fan_narratives import (apply_season_memory, goodwill_sentiment_floor,
                                 cynicism_sentiment_ceiling)

    t = make_team()

    # Cup win sets goodwill
    apply_season_memory(t, won_cup=True, made_playoffs=True)
    assert getattr(t, "fan_goodwill_seasons", 0) == 3
    assert goodwill_sentiment_floor(t) == 45.0

    # Goodwill decays
    apply_season_memory(t, won_cup=False, made_playoffs=True)
    assert getattr(t, "fan_goodwill_seasons", 0) == 2

    # Losing streak builds
    t2 = make_team()
    for _ in range(5):
        apply_season_memory(t2, won_cup=False, made_playoffs=False)
    assert getattr(t2, "fan_losing_streak", 0) == 5
    assert cynicism_sentiment_ceiling(t2) == 78.0

    # Playoffs reset the streak
    apply_season_memory(t2, won_cup=False, made_playoffs=True)
    assert getattr(t2, "fan_losing_streak", 0) == 0

    print("PASS: cross-season memory")


def test_sentiment_with_memory():
    """Memory-aware sentiment respects floor/ceiling."""
    from fan_sentiment import get_fan_sentiment_with_memory

    t = make_team()
    t.fan_sentiment = 10.0  # Very low
    t.fan_goodwill_seasons = 3  # But just won Cup

    v = get_fan_sentiment_with_memory(t)
    assert v >= 45.0, f"Goodwill floor should hold: {v}"

    # Cynicism ceiling
    t2 = make_team()
    t2.fan_sentiment = 95.0  # Very high
    t2.fan_losing_streak = 8  # But decade of losing

    v2 = get_fan_sentiment_with_memory(t2)
    assert v2 <= 70.0, f"Cynicism ceiling should hold: {v2}"

    print("PASS: sentiment with memory")


def test_never_raises():
    """All functions handle garbage gracefully."""
    from fan_narratives import (sentiment_tier, generate_fan_narrative,
                                 media_tone_for_sentiment, crowd_energy_mult,
                                 board_pressure, fa_appeal_mult,
                                 apply_season_memory)
    from fan_sentiment import (get_fan_sentiment, nudge_fan_sentiment,
                                 expectation_adjusted_baseline)

    # None team (uses default sentiment 60)
    assert sentiment_tier(None) == "content"
    assert generate_fan_narrative(None) is None
    assert media_tone_for_sentiment(None) == "neutral"
    # Default sentiment 60 -> crowd mult ~1.016, pressure ~0.14, fa ~1.01
    assert 0.9 <= crowd_energy_mult(None) <= 1.1
    assert 0.0 <= board_pressure(None) <= 0.5
    assert 0.9 <= fa_appeal_mult(None) <= 1.1

    # Empty object
    class Empty: pass
    e = Empty()
    generate_fan_narrative(e)  # Should not raise
    apply_season_memory(e)  # Should not raise
    get_fan_sentiment(e)  # Should not raise
    expectation_adjusted_baseline(e)  # Should not raise

    print("PASS: never raises on garbage")


if __name__ == "__main__":
    passed = 0
    failed = 0
    tests = [
        test_sentiment_tiers,
        test_fan_narrative_generation,
        test_media_tone,
        test_gameplay_effects,
        test_expectation_adjustment,
        test_trade_signing_nudges,
        test_coaching_change_nudge,
        test_cross_season_memory,
        test_sentiment_with_memory,
        test_never_raises,
    ]
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as ex:
            print(f"FAIL: {test.__name__}: {ex}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
