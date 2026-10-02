# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for BUG-001: Stage-10 ML updates must not crash on non-roster players.

Repro: a player on the ice who is present in game_stats but in NEITHER
team's roster (throwaway "Default Goalie", emergency filler). Before the
fix, _calculate_performance_projection and _assess_injury_risk raised
AttributeError ('NoneType' object has no attribute 'team_name') via
self._get_player_team(player).team_name, and the main.py batch wrapper
silently dropped the whole game.

The fix degrades gracefully (Caleb's own _update_ml_predictions /
10508 precedent): player-level updates land, only the team aggregate is
skipped when the team is None.
"""
import os
import sys

_REPO = os.path.dirname(os.path.abspath(__file__))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import simulation


class _FakePlayer:
    def __init__(self, pid):
        self.id = pid


class _FakeTeam:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = roster


def _blank_stats():
    return {
        'g': 0, 'a': 0, 'expected_goals': 0.0, 'goals_above_expected': 0.0,
        'war': 0.0,
        'performance_variance': 0.1, 'development_prediction': None,
        'development_tracking_points': 0, 'ai_learning_contribution': 5,
        'predictive_performance': 0.5, 'performance_trajectory': 0.0,
        'career_projection_confidence': 0.0, 'hits': 1, 'hits_taken': 2,
        'physical_penalties': 0, 'possession_time': 60.0,
        'injury_risk_score': 0.0,
    }


def _make_sim(home_roster):
    sim = simulation.GameSim.__new__(simulation.GameSim)
    sim.game_stats = {}
    sim.ml_models = {
        'player_development': {'training_data': [], 'prediction_count': 0},
        'injury_prediction': {'training_data': []},
    }
    sim.clock = 1200.0
    sim.player_fatigue = {}
    sim.home_team = _FakeTeam("Home", home_roster)
    sim.away_team = _FakeTeam("Away", [])
    sim.team_stats = {
        "Home": {'development_projections': 0, 'injury_predictions': 0},
        "Away": {'development_projections': 0, 'injury_predictions': 0},
    }
    return sim


def test_non_roster_player_no_crash():
    """The BUG-001 repro: must not raise, team counters untouched."""
    ghost = _FakePlayer(99999)
    sim = _make_sim(home_roster=[])
    sim.game_stats[ghost.id] = _blank_stats()

    sim._calculate_performance_projection(ghost)  # raised AttributeError pre-fix
    sim._assess_injury_risk(ghost)                # raised AttributeError pre-fix

    # Player-level updates landed...
    assert sim.game_stats[ghost.id]['career_projection_confidence'] > 0
    assert sim.game_stats[ghost.id]['injury_risk_score'] > 0
    # ...but no team aggregate was touched (no team to attribute to).
    assert sim.team_stats["Home"]['development_projections'] == 0
    assert sim.team_stats["Home"]['injury_predictions'] == 0
    assert sim.team_stats["Away"]['development_projections'] == 0
    assert sim.team_stats["Away"]['injury_predictions'] == 0
    print("PASS: non-roster player degrades gracefully, no crash")


def test_rostered_player_still_counted():
    """Normal path unchanged: rostered player increments team counters."""
    skater = _FakePlayer(12345)
    sim = _make_sim(home_roster=[skater])
    sim.game_stats[skater.id] = _blank_stats()

    sim._calculate_performance_projection(skater)
    sim._assess_injury_risk(skater)

    assert sim.team_stats["Home"]['development_projections'] == 1
    assert sim.team_stats["Home"]['injury_predictions'] == 1
    print("PASS: rostered player still updates team aggregates")


def test_hit_stats_non_roster_no_crash():
    """_record_hit_stats with a teamless hitter (BUG-001 traceback site)."""
    ghost = _FakePlayer(77701)
    sim = _make_sim(home_roster=[])
    sim.game_stats[ghost.id] = _blank_stats()
    sim.team_stats["Home"]['hits'] = 0
    # hitter has stats but no team; target likewise teamless
    sim._record_hit_stats(ghost, ghost, None, 1)
    assert sim.team_stats["Home"]['hits'] == 0
    print("PASS: _record_hit_stats degrades gracefully for teamless players")


def test_shot_stats_non_roster_no_crash():
    """_update_shot_stats with an untracked shooter (BUG-001 KeyError site)."""
    ghost = _FakePlayer(77702)
    sim = _make_sim(home_roster=[])
    home = sim.home_team
    away = sim.away_team
    # no game_stats entry at all -- must not raise
    sim._update_shot_stats(ghost, home, away, "low", 30.0, None)
    print("PASS: _update_shot_stats degrades gracefully for untracked shooter")


if __name__ == "__main__":
    test_non_roster_player_no_crash()
    test_rostered_player_still_counted()
    test_hit_stats_non_roster_no_crash()
    test_shot_stats_non_roster_no_crash()
    print("qa_bug001_none_team_guard: 4/4 passed")
