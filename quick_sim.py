"""
Quick sim (roadmap F7).

Abstract per-shift resolver for background games. The full sim runs
1/4s ticks with commentary and 2D; this resolves each shift as a
unit-vs-unit ratings check. Must reproduce full-sim stat profiles
within tolerance (goals, shots, penalties).
"""

import random
from collections import defaultdict


def team_ratings(team):
    """Extract abstract ratings from a team (1-100 scale)."""
    roster = getattr(team, 'roster', []) or []
    skaters = [p for p in roster
               if 'GOALIE' not in str(getattr(p, 'primary_position', ''))]
    goalies = [p for p in roster
               if 'GOALIE' in str(getattr(p, 'primary_position', ''))]
    if not skaters:
        return {'offense': 50, 'defense': 50, 'goalie': 50}
    off = sum(getattr(p, 'offensive_awareness', 50) for p in skaters) / len(skaters)
    deff = sum(getattr(p, 'defensive_awareness', 50) for p in skaters) / len(skaters)
    g = 50
    if goalies:
        g = sum(getattr(p, 'overall', 50) for p in goalies) / len(goalies)
    return {'offense': off, 'defense': deff, 'goalie': g}


def quick_sim_game(home_team, away_team, seed=None):
    """Simulate one game abstractly. Returns a result dict.

    Resolves ~80 shifts (60 min / 45s avg). Each shift: offense vs
    defense ratings determine shot generation; goalie rating determines
    save probability.
    """
    if seed is not None:
        random.seed(seed)
    h = team_ratings(home_team)
    a = team_ratings(away_team)

    result = {
        'home_team': home_team.team_name,
        'away_team': away_team.team_name,
        'home_score': 0, 'away_score': 0,
        'home_shots': 0, 'away_shots': 0,
        'penalties': 0,
    }

    # ~80 shifts per game
    for _ in range(80):
        for att, deff, prefix in ((h, a, 'home'), (a, h, 'away')):
            # Shot generation: offense vs defense
            # Base: ~0.30 shots per shift per team (~47 shots/game)
            shot_prob = 0.30 + (att['offense'] - deff['defense']) / 500
            shot_prob = max(0.1, min(0.5, shot_prob))
            if random.random() < shot_prob:
                result[f'{prefix}_shots'] += 1
                # Goal: shooter vs goalie
                # Base ~8.5% shooting (matches full-sim ~4.5 goals on ~47 shots)
                goal_prob = 0.085 + (att['offense'] - deff['goalie']) / 2000
                goal_prob = max(0.03, min(0.2, goal_prob))
                if random.random() < goal_prob:
                    result[f'{prefix}_score'] += 1
        # Penalties: ~5 per game total
        if random.random() < 0.06:
            result['penalties'] += 1

    # Home-ice edge: slight boost
    if random.random() < 0.1 and result['home_score'] == result['away_score']:
        result['home_score'] += 1  # OT winner-ish

    return result


def quick_sim_season(teams, schedule):
    """Sim an entire season quickly.

    teams: list of Team. schedule: list of (home, away) tuples.
    Returns list of result dicts.
    """
    results = []
    for i, (home, away) in enumerate(schedule):
        results.append(quick_sim_game(home, away, seed=i))
    return results
