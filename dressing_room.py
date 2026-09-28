"""
Dressing-room dynamics (roadmap F3).

The people-sim: social groups, morale cascades, and team talks.
- Social groups form by tenure (veterans/rookies cluster) and captaincy.
- Big morale moves cascade to group-mates (good and bad).
- Team talks (pre-game, intermission) use a tone system that nudges the
  sim's momentum via a per-team modifier the GameSim reads.

This is the management layer; the sim reads only the momentum modifier.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Team-talk tones (FM12's six, adapted for hockey)
TONES = ('calm', 'fired_up', 'cautious', 'demanding', 'encouraging', 'defiant')

# How each tone shifts the pre-game/intermission momentum modifier.
# Positive = emotional lift (better early legs, riskier decisions);
# negative = steadying (fewer mistakes, less jump).
TONE_EFFECTS = {
    'calm':        0.0,
    'fired_up':   +0.15,
    'cautious':   -0.10,
    'demanding':  +0.05,
    'encouraging':+0.10,
    'defiant':    +0.12,
}


@dataclass
class SocialGroup:
    """A dressing-room clique."""
    name: str  # e.g. 'veterans', 'young_guns', 'leadership'
    member_ids: List[str] = field(default_factory=list)
    cohesion: float = 0.7  # 0-1: how strongly mood spreads inside


class DressingRoom:
    """Per-team people-sim state."""

    def __init__(self, team):
        self.team_name = team.team_name
        self.groups: List[SocialGroup] = []
        # Last team-talk: (tone, momentum_modifier, game_phase)
        self.last_talk: Optional[tuple] = None
        self._build_groups(team)

    def _build_groups(self, team):
        roster = list(getattr(team, 'roster', []) or [])
        if not roster:
            return
        # Leadership group: captain + alternates
        leaders = [p for p in roster
                   if getattr(p, 'captaincy', None) in ('C', 'A')]
        if leaders:
            self.groups.append(SocialGroup(
                'leadership', [p.id for p in leaders], cohesion=0.9))
        # Tenure groups: veterans (30+), prime (25-29), young (<25)
        vets = [p for p in roster if getattr(p, 'age', 27) >= 30]
        young = [p for p in roster if getattr(p, 'age', 27) < 25]
        prime = [p for p in roster
                 if p not in vets and p not in young]
        if vets:
            self.groups.append(SocialGroup(
                'veterans', [p.id for p in vets], cohesion=0.75))
        if young:
            self.groups.append(SocialGroup(
                'young_guns', [p.id for p in young], cohesion=0.7))
        if prime:
            self.groups.append(SocialGroup(
                'core', [p.id for p in prime], cohesion=0.6))

    def morale_cascade(self, team, player, delta):
        """A big morale move spreads to the player's groups.

        delta: the morale change applied to `player` (1-10 scale).
        Group-mates move a fraction (cohesion * 0.5), in the same direction.
        Captains amplify: their moves spread 1.5x.
        """
        if abs(delta) < 2:
            return  # small moves don't cascade
        pid = player.id
        amp = 1.5 if getattr(player, 'captaincy', None) == 'C' else 1.0
        roster_by_id = {p.id: p for p in team.roster}
        for g in self.groups:
            if pid not in g.member_ids:
                continue
            spread = delta * g.cohesion * 0.5 * amp
            for mid in g.member_ids:
                if mid == pid:
                    continue
                mate = roster_by_id.get(mid)
                if mate is None:
                    continue
                new_morale = getattr(mate, 'morale', 5) + spread
                mate.morale = max(1, min(10, round(new_morale)))

    def team_talk(self, tone, phase='pregame'):
        """Deliver a team talk. Returns the momentum modifier.

        phase: 'pregame' or 'intermission'.
        The GameSim reads get_momentum_modifier() at the relevant moment.
        """
        if tone not in TONES:
            raise ValueError(f"unknown tone: {tone}")
        effect = TONE_EFFECTS[tone]
        # Intermission talks hit harder (players are listening, legs are back)
        if phase == 'intermission':
            effect *= 1.25
        self.last_talk = (tone, effect, phase)
        return effect

    def get_momentum_modifier(self):
        """Current talk modifier for the sim (decays to 0 if no talk)."""
        if not self.last_talk:
            return 0.0
        return self.last_talk[1]

    def clear_talk(self):
        self.last_talk = None
