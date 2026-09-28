"""
Coaching carousel (roadmap F1: same-rules AI).

AI head coaches are hired and fired on performance, just like the player
can be. Bad teams fire their coach; good coaches get poached.
"""

import random


def evaluate_coach(team, games_played, points, expectation='bubble_team'):
    """Should this AI team fire its coach?

    Returns (fire: bool, reason: str).
    """
    from board_confidence import EXPECTATION_PACE
    if games_played < 20:
        return False, "too early"
    pace = points / games_played
    target = EXPECTATION_PACE.get(expectation, 1.0)
    # Fire if well below expectation after 20+ games
    if pace < target - 0.35:
        return True, f"pace {pace:.2f} well below target {target:.2f}"
    return False, "meeting expectations"


def generate_coach_candidate():
    """Create a free-agent coach."""
    first = random.choice(['Mike', 'John', 'Sarah', 'David', 'Lisa',
                           'Chris', 'Pat', 'Alex', 'Jamie', 'Taylor'])
    last = random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones',
                          'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor'])
    return {
        'name': f"{first} {last}",
        'tactical_knowledge': random.randint(8, 18),
        'man_management': random.randint(8, 18),
        'motivating': random.randint(8, 18),
        'experience': random.randint(1, 20),
    }


def run_carousel(league_teams, standings):
    """End-of-season coaching carousel.

    league_teams: list of Team. standings: {team_name: (games, points)}.
    Returns list of (team_name, old_coach, new_coach) changes.
    """
    changes = []
    for team in league_teams:
        name = team.team_name
        if name not in standings:
            continue
        games, points = standings[name]
        # Skip the player's team (they decide their own fate via F5)
        if getattr(team, 'is_player_team', False):
            continue
        fire, reason = evaluate_coach(team, games, points,
                                      getattr(team, 'expectation', 'bubble_team'))
        if fire:
            old = getattr(team, 'head_coach', 'Unknown')
            new = generate_coach_candidate()
            team.head_coach = new['name']
            # New coach brings their own tactical identity
            try:
                from ai_coach import assign_ai_tactics
                assign_ai_tactics(team)
            except ImportError:
                pass
            changes.append((name, old, new['name'], reason))
    return changes
