"""Positional familiarity and position training.

Players have familiarity (0-100) with each position. Playing out of
position applies a scaled performance modifier -- a RW filling in at LW
(80 familiarity) is barely affected, while a D-man at LW (35 familiarity)
takes a real hit.

Base familiarity by positional relationship:
  Same position:              100
  LW <-> RW (wings):           80
  LD <-> RD:                   75
  D (generic) <-> LD/RD:       85
  C <-> LW/RW (wing to center): 65  (faceoffs are specialized)
  F <-> D (forward to defense): 35
  Any skater <-> G:              5  (essentially cannot play)

Players can train new positions via practice. Familiarity gains:
  - Faster when young, high hockey IQ, good coaching
  - Diminishing returns as familiarity approaches 100
  - Cannot exceed 100; primary position is always 100

The modifier curve: performance_mult = 0.70 + 0.30 * (fam/100)^0.7
  fam=100 -> 1.00x (no penalty)
  fam= 80 -> 0.95x (wing swap, barely noticeable)
  fam= 65 -> 0.90x (wing to center, moderate)
  fam= 35 -> 0.79x (forward to D, significant)
  fam=  5 -> 0.72x (skater in net, disaster -- but won't happen)
"""

import math


# Base familiarity for each (from_pos, to_pos) pair.
# Keys are position value strings: 'C', 'LW', 'RW', 'LD', 'RD', 'D', 'G'.
_BASE_FAMILIARITY = {
    # Same position
    ('C', 'C'): 100, ('LW', 'LW'): 100, ('RW', 'RW'): 100,
    ('LD', 'LD'): 100, ('RD', 'RD'): 100, ('D', 'D'): 100,
    ('G', 'G'): 100,
    # Wing swaps (easiest)
    ('LW', 'RW'): 80, ('RW', 'LW'): 80,
    # Defense side swaps
    ('LD', 'RD'): 75, ('RD', 'LD'): 75,
    # Generic D to specific side
    ('D', 'LD'): 85, ('D', 'RD'): 85,
    ('LD', 'D'): 85, ('RD', 'D'): 85,
    # Center <-> Wing (faceoff specialization makes this harder)
    ('C', 'LW'): 65, ('C', 'RW'): 65,
    ('LW', 'C'): 65, ('RW', 'C'): 65,
    # Forward <-> Defense (biggest skater jump)
    ('C', 'LD'): 35, ('C', 'RD'): 35, ('C', 'D'): 35,
    ('LW', 'LD'): 35, ('LW', 'RD'): 35, ('LW', 'D'): 35,
    ('RW', 'LD'): 35, ('RW', 'RD'): 35, ('RW', 'D'): 35,
    ('LD', 'C'): 35, ('LD', 'LW'): 35, ('LD', 'RW'): 35,
    ('RD', 'C'): 35, ('RD', 'LW'): 35, ('RD', 'RW'): 35,
    ('D', 'C'): 35, ('D', 'LW'): 35, ('D', 'RW'): 35,
}


def _pos_key(pos):
    """Normalize a position to its string key."""
    try:
        # Enum -> value
        return pos.value if hasattr(pos, 'value') else str(pos)
    except Exception:
        return str(pos)


def base_familiarity(from_pos, to_pos):
    """Base familiarity when playing to_pos with from_pos as primary."""
    fk = _pos_key(from_pos)
    tk = _pos_key(to_pos)
    if fk == tk:
        return 100
    # Goalie <-> skater: essentially zero
    if 'G' in (fk, tk):
        return 5
    return _BASE_FAMILIARITY.get((fk, tk), 30)


def get_familiarity(player, position):
    """Player's familiarity (0-100) with a position.
    Checks trained familiarity first, falls back to base."""
    tk = _pos_key(position)
    try:
        primary = _pos_key(getattr(player, 'primary_position', None))
    except Exception:
        primary = None
    if tk == primary:
        return 100
    # Trained familiarity dict (populated by position training)
    try:
        trained = getattr(player, 'position_familiarity', None) or {}
        if tk in trained:
            return max(0, min(100, float(trained[tk])))
    except Exception:
        pass
    return base_familiarity(primary, tk)


def performance_modifier(player, position):
    """Scaled performance multiplier for playing a position.
    1.0 = no penalty. Scales smoothly with familiarity."""
    fam = get_familiarity(player, position)
    # Curve: 0.70 + 0.30 * (fam/100)^0.7
    # fam=100 -> 1.00, fam=80 -> 0.95, fam=65 -> 0.90,
    # fam=35 -> 0.79, fam=5 -> 0.72
    return 0.70 + 0.30 * math.pow(max(0, fam) / 100.0, 0.7)


def train_position(player, target_pos, coaching_quality=50):
    """One training session toward a new position.
    Returns (new_familiarity, gained_this_session).
    Gains scale with age (young faster), hockey IQ, coaching,
    and diminish as familiarity approaches 100."""
    tk = _pos_key(target_pos)
    try:
        primary = _pos_key(getattr(player, 'primary_position', None))
    except Exception:
        primary = None
    if tk == primary:
        return 100, 0.0  # Already native

    current = get_familiarity(player, tk)
    if current >= 99.5:
        return 100.0, 0.0
    try:
        age = int(getattr(player, 'age', 25) or 25)
    except Exception:
        age = 25
    try:
        iq = float(getattr(player, 'hockey_iq',
                           getattr(player, 'offensive_awareness', 50)) or 50)
    except Exception:
        iq = 50.0
    try:
        coach_q = float(coaching_quality or 50)
    except Exception:
        coach_q = 50.0

    # Base gain: 2-6 points per session
    base = 2.0 + (coach_q / 100.0) * 2.0 + (iq / 100.0) * 2.0
    # Young players learn faster
    if age <= 22:
        base *= 1.5
    elif age <= 25:
        base *= 1.25
    elif age >= 32:
        base *= 0.6
    elif age >= 29:
        base *= 0.8
    # Diminishing returns: harder to go from 80->90 than 30->40
    headroom = (100.0 - current) / 100.0
    gain = base * (0.3 + 0.7 * headroom)

    new_fam = min(100.0, current + gain)
    # Persist trained familiarity
    try:
        if not hasattr(player, 'position_familiarity') or \
                player.position_familiarity is None:
            player.position_familiarity = {}
        player.position_familiarity[tk] = new_fam
    except Exception:
        pass
    return new_fam, new_fam - current


def eligible_training_positions(player):
    """Positions a player can realistically train (not goalie swaps)."""
    try:
        primary = _pos_key(getattr(player, 'primary_position', None))
    except Exception:
        return []
    if primary == 'G':
        return []  # Goalies don't train skater positions
    # Skaters can train any skater position
    return ['C', 'LW', 'RW', 'LD', 'RD']
