"""
AI coach tactics (roadmap F1: same-rules AI).

AI coaches pick EHM-style tactical systems based on their roster's
archetype — the same systems the player chooses from. No hidden AI
advantages; the AI plays by the same tactical rules.
"""

import random


def roster_archetype(team):
    """Classify a roster: 'offensive', 'defensive', 'balanced', 'young'."""
    roster = getattr(team, 'roster', []) or []
    skaters = [p for p in roster
               if getattr(p, 'primary_position', None) and
               'GOALIE' not in str(p.primary_position)]
    if not skaters:
        return 'balanced'
    avg_age = sum(getattr(p, 'age', 27) for p in skaters) / len(skaters)
    avg_off = sum(getattr(p, 'offensive_awareness', 50) for p in skaters) / len(skaters)
    avg_def = sum(getattr(p, 'defensive_awareness', 50) for p in skaters) / len(skaters)
    if avg_age < 25:
        return 'young'
    if avg_off - avg_def > 8:
        return 'offensive'
    if avg_def - avg_off > 8:
        return 'defensive'
    return 'balanced'


# System preferences by archetype (same options the player sees)
ARCHETYPE_SYSTEMS = {
    'offensive': {
        'tactic_forecheck': '2-1-2',
        'tactic_neutral_zone': '2-1-2',
        'tactic_breakout': 'wings_cross',
        'tactic_dz_coverage': 'open',
        'tactic_pp': 'umbrella',
        'tactic_pk': 'diamond',
        'tactic_offense': 'Overload',
    },
    'defensive': {
        'tactic_forecheck': '1-4',
        'tactic_neutral_zone': '1-1-3',
        'tactic_breakout': 'positional',
        'tactic_dz_coverage': 'collapse',
        'tactic_pp': 'funnel',
        'tactic_pk': 'tight_box',
        'tactic_offense': 'Crash the Net',
    },
    'young': {
        'tactic_forecheck': '1-2-2',
        'tactic_neutral_zone': '1-2-2',
        'tactic_breakout': 'board_play',
        'tactic_dz_coverage': 'positional',
        'tactic_pp': '1-2-2',
        'tactic_pk': 'wide_box',
        'tactic_offense': 'Spread',
    },
    'balanced': {
        'tactic_forecheck': '2-1-2',
        'tactic_neutral_zone': '1-2-2',
        'tactic_breakout': 'positional',
        'tactic_dz_coverage': 'positional',
        'tactic_pp': 'umbrella',
        'tactic_pk': 'tight_box',
        'tactic_offense': 'Spread',
    },
}


def assign_ai_tactics(team):
    """Give an AI team its archetype's tactical systems.

    Call this for AI-controlled teams at season start (and when their
    roster archetype changes significantly). The player keeps full
    manual control of their own team's systems.
    """
    arch = roster_archetype(team)
    systems = ARCHETYPE_SYSTEMS[arch]
    for attr, value in systems.items():
        setattr(team, attr, value)
    return arch


def maybe_adjust_tactics(team, games_played, goals_for, goals_against):
    """Mid-season AI adjustment: struggling AI teams tweak systems.

    A team getting outscored badly may switch to a more defensive
    posture; a team that can't score may open up. Small chance per
    check to avoid thrashing.
    """
    if games_played < 10:
        return None
    diff = (goals_for - goals_against) / max(1, games_played)
    if diff < -0.75 and random.random() < 0.3:
        # Getting shelled: collapse and trap
        team.tactic_dz_coverage = 'collapse'
        team.tactic_forecheck = '1-4'
        team.tactic_neutral_zone = '1-1-3'
        return 'defensive_shell'
    if diff > 0.75 and random.random() < 0.2:
        # Rolling: press harder
        team.tactic_forecheck = '2-1-2'
        team.tactic_dz_coverage = 'open'
        return 'press'
    return None


# E7: adaptive AI — track what the player does and adjust.
# Maps a player's observed tendency to the AI's counter.
COUNTERS = {
    # Player runs umbrella PP (lots of point shots) -> collapse the slot
    'pp_umbrella': {'tactic_dz_coverage': 'collapse',
                    'tactic_pk': 'tight_box'},
    # Player funnels (slot attack) -> open up, challenge
    'pp_funnel': {'tactic_dz_coverage': 'open',
                  'tactic_pk': 'diamond'},
    # Player dumps and chases (weak breakout) -> aggressive forecheck
    'weak_breakout': {'tactic_forecheck': '2-1-2',
                      'tactic_neutral_zone': '2-1-2'},
    # Player plays collapse D -> crash the net
    'dz_collapse': {'tactic_offense': 'Crash the Net',
                    'tactic_pp': 'funnel'},
}


class OpponentTracker:
    """E7: remembers what a specific opponent does, game to game."""

    def __init__(self):
        # opponent_name -> {'games': int, 'tendencies': {key: count}}
        self._data = {}

    def observe(self, opponent_name, game_tendencies):
        """game_tendencies: dict like {'pp_umbrella': True, ...}."""
        d = self._data.setdefault(opponent_name,
                                  {'games': 0, 'tendencies': {}})
        d['games'] += 1
        for k, v in game_tendencies.items():
            if v:
                d['tendencies'][k] = d['tendencies'].get(k, 0) + 1

    def adapt(self, ai_team, opponent_name):
        """Adjust the AI team's tactics to counter observed tendencies.

        Returns a list of human-readable adjustments for the pre-game report.
        """
        d = self._data.get(opponent_name)
        if not d or d['games'] < 3:
            return []  # need a sample before adjusting
        adjustments = []
        for tendency, count in d['tendencies'].items():
            # Persistent tendency (seen in >60% of games)?
            if count / d['games'] > 0.6 and tendency in COUNTERS:
                for attr, value in COUNTERS[tendency].items():
                    old = getattr(ai_team, attr, None)
                    if old != value:
                        setattr(ai_team, attr, value)
                        adjustments.append(
                            f"adjusted {attr} to {value} "
                            f"(countering your {tendency})")
        return adjustments
