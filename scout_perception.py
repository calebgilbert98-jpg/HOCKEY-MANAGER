#!/usr/bin/env python3
"""Scout POV perception layer (Puck Dynasty refinement #3).

The GM's card view stays TRUE everywhere (Overview/Attributes tabs, trade
tags, AI reads) -- ONLY scout-facing surfaces go through this module. It
turns a scout's report into what that scout *believes* the player's
attributes are: noisy, seeded-stable, and narrower on the attributes his
position demands he read well.

Noise model (ported from ScoutingReport._scout_attributes, 1-20 -> 1-100):
    _scout_attributes uses variance bands A:0 B:1 C:2 D:3 F:4 on the 1-20
    scale, with position-primary attributes one band tighter. Ported x5:
        half-spread = {'A': 0, 'B': 5, 'C': 10, 'D': 15, 'F': 20}
        primaries tighten by one band: {'A': 0, 'B': 0, 'C': 5,
                                        'D': 10, 'F': 15}
    The report's accuracy grade already folds viewings + scout skill
    (effective_viewings = viewings + (JPA+JPP)//10 in update_report).

    perceived_center = clamp(true + Uniform(-spread, +spread), 1, 100)
    display = point value when spread == 0, else (lo, hi) with
    lo/hi = clamp(center -/+ spread).

"How often they're right": the scout's graded tip_record (the same data
behind analytics_scouting.scout_record_line) modulates the spread:
    calls >= 5 and hit_rate >= 0.60 -> spread x 0.85
    calls >= 5 and hit_rate <= 0.35 -> spread x 1.15
Modest, bounded, and only with a real sample. The record line itself is
displayed on the tab (rendered by the UI via scout_record_line).

Determinism: the RNG is seeded by sha256 of
    "scout-perception|{player_id}|{scout_id}|{viewings}"
so a scout's read is STABLE across card opens. A new viewing re-rolls the
read (fresh eyes, legitimately new information) -- re-rolling on every
open would be a bug, not fog of war.

Composites: perceived_composites() runs the REAL attribute_composites
blends (get_composite_ratings) on a lightweight proxy whose attribute
reads resolve to perceived values. One code path, no second copy of the
weights. Interval display: the blend is a linear weighted sum, so the
(lo, hi) interval maps cleanly through it -- blend(lo-view),
blend(hi-view).
"""

import hashlib
import random

# ---------------------------------------------------------------------------
# Noise bands: A-F half-spread on the 1-100 scale.
# ---------------------------------------------------------------------------

_GRADE_SPREAD = {'A': 0, 'B': 5, 'C': 10, 'D': 15, 'F': 20}
_PRIMARY_TIGHTEN = 5          # one band tighter on position primaries
_MAX_SPREAD = 25              # hard cap after the hit-rate modulator

# Position-primary attribute sets. Mirror ScoutingReport._scout_attributes'
# focus lists (game_classes.py) so the "reads his position well" behavior
# matches the report's own accuracy model.
_PRIMARIES = {
    'GOALIE': {'goaltending', 'reflexes', 'positioning', 'rebound_control'},
    'DEFENSE': {'defensive_awareness', 'checking', 'passing', 'shot_blocking',
                'skating'},
    'FORWARD': {'shooting', 'passing', 'offensive_awareness', 'deking',
                'skating'},
}

# Attribute universe: everything the modern card displays (modern_profile
# SKATER_/GOALIE_* lists) plus the composite member attributes that live
# outside those lists (offensive_awareness vs off_the_puck, the split
# defensive_positioning, faceoff_wins, acceleration). Every composite
# member MUST resolve here so the proxy never falls back to truth.
SKATER_ATTRS = [
    "shooting", "shooting_accuracy", "shooting_power", "wristshot",
    "slapshot", "one_timer", "backhand", "deflections", "passing",
    "passing_accuracy", "passing_creativity", "puck_handling",
    "stickhandling", "deking", "offensive_positioning", "faceoffs",
    "first_pass", "breakout_passes", "puck_protection", "loose_puck",
    "pokecheck",
    "vision", "hockey_iq", "anticipation", "decision_making",
    "off_the_puck", "defensive_awareness", "creativity", "determination",
    "composure", "confidence", "focus", "pressure_player", "teamwork",
    "discipline", "flair", "work_ethic", "coachability", "adaptability",
    "skating", "speed", "agility", "balance", "strength", "stamina",
    "endurance", "durability", "injury_proneness", "aggressiveness",
    "checking", "bodycheck", "shot_blocking", "forechecking",
    "screen_shots", "work_rate", "shoot_pass_tendency",
    "hitting_tendency",
    # composite members outside the card lists
    "offensive_awareness", "defensive_positioning", "faceoff_wins",
    "acceleration",
]
GOALIE_ATTRS = [
    "goaltending", "positioning", "reflexes", "glove_hand", "stick_side",
    "rebound_control", "breakaway_skill", "puck_handling", "passing",
    "anticipation", "decision_making", "vision", "focus", "determination",
    "composure", "confidence", "teamwork", "discipline", "work_ethic",
    "adaptability",
    "skating", "speed", "agility", "balance", "strength", "stamina",
    "endurance", "durability", "injury_proneness", "aggressiveness",
]

# Display labels for the tab (card-list labels from modern_profile, plus
# the composite-only members).
_ATTR_LABELS = {
    "shooting": "Shooting", "shooting_accuracy": "Shot Accuracy",
    "shooting_power": "Shot Power", "wristshot": "Wrist Shot",
    "slapshot": "Slap Shot", "one_timer": "One Timer",
    "backhand": "Backhand", "deflections": "Deflections",
    "passing": "Passing", "passing_accuracy": "Pass Accuracy",
    "passing_creativity": "Passing Creativity",
    "puck_handling": "Puck Handling", "stickhandling": "Stickhandling",
    "deking": "Deking", "offensive_positioning": "Off. Positioning",
    "faceoffs": "Faceoffs", "first_pass": "First Pass",
    "breakout_passes": "Breakout Passes",
    "puck_protection": "Puck Protection", "loose_puck": "Loose Puck",
    "pokecheck": "Pokecheck",
    "vision": "Vision", "hockey_iq": "Hockey IQ",
    "anticipation": "Anticipation", "decision_making": "Decisions",
    "off_the_puck": "Off. Awareness",
    "offensive_awareness": "Off. Awareness",
    "defensive_awareness": "Def. Awareness",
    "defensive_positioning": "Def. Positioning",
    "creativity": "Creativity", "determination": "Determination",
    "composure": "Composure", "confidence": "Confidence",
    "focus": "Focus", "pressure_player": "Pressure Player",
    "teamwork": "Teamwork", "discipline": "Discipline", "flair": "Flair",
    "work_ethic": "Work Ethic", "coachability": "Coachability",
    "adaptability": "Adaptability",
    "skating": "Skating", "speed": "Speed", "agility": "Agility",
    "balance": "Balance", "strength": "Strength", "stamina": "Stamina",
    "endurance": "Endurance", "durability": "Durability",
    "injury_proneness": "Injury Proneness",
    "aggressiveness": "Aggression", "checking": "Checking",
    "bodycheck": "Bodycheck", "shot_blocking": "Shot Blocking",
    "forechecking": "Forechecking", "screen_shots": "Screening",
    "work_rate": "Work Rate", "shoot_pass_tendency": "Shoot Tendency",
    "hitting_tendency": "Hitting Tendency", "faceoff_wins": "Draw Skill",
    "acceleration": "Acceleration",
    "goaltending": "Goaltending", "positioning": "Positioning",
    "reflexes": "Reflexes", "glove_hand": "Glove Hand",
    "stick_side": "Stick Side", "rebound_control": "Rebound Ctrl",
    "breakaway_skill": "Breakaway Skill",
}

# Composite display names and per-position visibility.
_COMPOSITE_LABELS = {
    "chance_creation": "Chance Creation", "finishing": "Finishing",
    "defensive_play": "Defensive Play", "physicality": "Physicality",
    "faceoff": "Faceoffs", "puck_retrieval": "Puck Retrieval",
    "goalie_save": "Goaltending", "skating": "Skating",
    "discipline": "Discipline",
}
_SKATER_COMPOSITES = ("chance_creation", "finishing", "defensive_play",
                      "physicality", "faceoff", "puck_retrieval",
                      "skating", "discipline")
_GOALIE_COMPOSITES = ("goalie_save", "skating", "discipline")


# ---------------------------------------------------------------------------
# Seeded RNG + noise
# ---------------------------------------------------------------------------

def _seeded_rng(player, scout, viewings):
    """Stable RNG for one scout's read of one player at N viewings."""
    pid = str(getattr(player, 'id', '') or '')
    sid = str(getattr(scout, 'id', '') or '')
    key = f"scout-perception|{pid}|{sid}|{int(viewings or 0)}"
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    return random.Random(digest)


def _position_group(player):
    try:
        name = getattr(getattr(player, 'primary_position', None), 'name', '')
    except Exception:
        name = ''
    if name == 'GOALIE':
        return 'GOALIE'
    if 'DEFENSE' in name:
        return 'DEFENSE'
    return 'FORWARD'


def _hit_rate_modulator(scout):
    """Modest confidence modulator from the scout's graded hit-rate.

    >=60% over 5+ graded calls tightens the spread x0.85; <=35% widens
    it x1.15. Too small a sample (or no record) -> no modulation.
    """
    try:
        rec = getattr(scout, 'tip_record', None) or {}
        calls = int(rec.get('calls', 0) or 0)
        hits = int(rec.get('hits', 0) or 0)
    except Exception:
        return 1.0
    if calls < 5:
        return 1.0
    rate = hits / calls
    if rate >= 0.60:
        return 0.85
    if rate <= 0.35:
        return 1.15
    return 1.0


def _spread(grade, is_primary, scout):
    base = _GRADE_SPREAD.get((grade or 'F').upper(), 20)
    if is_primary:
        base = max(0, base - _PRIMARY_TIGHTEN)
    return min(_MAX_SPREAD, base * _hit_rate_modulator(scout))


def _true_attr(player, attr):
    """True 1-100 attribute, or None when unset (old-save split attrs)."""
    try:
        v = getattr(player, attr, None)
    except Exception:
        return None
    if v is None:
        return None
    try:
        return max(1.0, min(100.0, float(v)))
    except (TypeError, ValueError):
        return None


def perceived_attributes(player, scout, report=None):
    """One scout's read of a player's attributes.

    Returns {attr: int} for point reads or {attr: (lo, hi)} for ranged
    reads. report=None (no viewings yet) is the coldest read: F-grade
    bands at 0 viewings.
    """
    grade = getattr(report, 'accuracy', 'F') if report is not None else 'F'
    viewings = getattr(report, 'viewings', 0) if report is not None else 0
    rng = _seeded_rng(player, scout, viewings)
    primaries = _PRIMARIES[_position_group(player)]
    attrs = (GOALIE_ATTRS if _position_group(player) == 'GOALIE'
             else SKATER_ATTRS)
    out = {}
    for attr in attrs:
        true = _true_attr(player, attr)
        if true is None:
            continue  # unset on old saves: skip rather than invent
        spread = _spread(grade, attr in primaries, scout)
        if spread <= 0:
            out[attr] = int(round(true))
            continue
        center = max(1.0, min(100.0, true + rng.uniform(-spread, spread)))
        lo = int(round(max(1.0, min(100.0, center - spread))))
        hi = int(round(max(1.0, min(100.0, center + spread))))
        if lo >= hi:
            out[attr] = int(round(center))
        else:
            out[attr] = (lo, hi)
    return out


# ---------------------------------------------------------------------------
# Perceived composites: the REAL blends, run on perceived values.
# ---------------------------------------------------------------------------

class _PerceivedPlayerView:
    """Proxy: attribute reads resolve to perceived values, everything else
    falls through to the real player (team_name, morale, ...)."""

    def __init__(self, player, values):
        object.__setattr__(self, '_player', player)
        object.__setattr__(self, '_values', dict(values))

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        if name in values:
            return values[name]
        player = object.__getattribute__(self, '_player')
        v = getattr(player, name, None)
        # Same old-save fallback as attribute_composites._attr.
        if v is None and name in ('offensive_positioning',
                                  'defensive_positioning'):
            v = getattr(player, 'positioning', None)
        return v


def _centers(perceived):
    """Collapse {attr: int | (lo, hi)} to point values (interval midpoints)."""
    return {a: (v if isinstance(v, int) else (v[0] + v[1]) / 2.0)
            for a, v in perceived.items()}


def _bounds(perceived, which):
    """Collapse to the lo (which=0) or hi (which=1) bound view."""
    return {a: (v if isinstance(v, int) else v[which])
            for a, v in perceived.items()}


def perceived_composites(player, scout, report=None):
    """The scout's composite read through the TRUE blend formulas.

    {composite: float} for tight reads, {composite: (lo, hi)} where the
    underlying attributes were ranged. Imports attribute_composites --
    never copies its weights.
    """
    import attribute_composites as ac
    perceived = perceived_attributes(player, scout, report)
    group = _position_group(player)
    keys = (_GOALIE_COMPOSITES if group == 'GOALIE' else _SKATER_COMPOSITES)

    centers = _centers(perceived)
    point = ac.get_composite_ratings(_PerceivedPlayerView(player, centers))
    ranged = any(not isinstance(v, int) for v in perceived.values())
    if not ranged:
        return {k: point[k] for k in keys}

    lo_view = _PerceivedPlayerView(player, _bounds(perceived, 0))
    hi_view = _PerceivedPlayerView(player, _bounds(perceived, 1))
    lo = ac.get_composite_ratings(lo_view)
    hi = ac.get_composite_ratings(hi_view)
    out = {}
    for k in keys:
        if lo[k] >= hi[k]:
            out[k] = point[k]
        else:
            out[k] = (round(lo[k], 1), round(hi[k], 1))
    return out


def perceived_strengths_weaknesses(player, scout, report=None,
                                  n_strengths=3, n_weaknesses=2,
                                  weak_below=60):
    """(strengths, weaknesses) as [(label, display)] from perceived centers.

    display is "74" for point reads, "68-78" for ranged reads.
    """
    perceived = perceived_attributes(player, scout, report)
    centers = _centers(perceived)
    attrs = (GOALIE_ATTRS if _position_group(player) == 'GOALIE'
             else SKATER_ATTRS)
    # Strengths/weaknesses only over the card-displayed attributes (skip
    # the composite-only extras: they have no card presence).
    card_attrs = [a for a in attrs if a in _ATTR_LABELS and a not in
                  ('offensive_awareness', 'faceoff_wins', 'acceleration')]
    scored = [(a, centers[a]) for a in card_attrs if a in centers]
    scored.sort(key=lambda t: t[1], reverse=True)

    def _display(attr):
        v = perceived[attr]
        label = _ATTR_LABELS.get(attr, attr)
        if isinstance(v, int):
            return f"{label} ({v})"
        return f"{label} ({v[0]}-{v[1]})"

    strengths = [_display(a) for a, _ in scored[:n_strengths]]
    weak = [(a, c) for a, c in scored if c < weak_below]
    weak.sort(key=lambda t: t[1])
    weaknesses = [_display(a) for a, _ in weak[:n_weaknesses]]
    return strengths, weaknesses


# ---------------------------------------------------------------------------
# Tab resolution: which scout's read is on the card?
# ---------------------------------------------------------------------------

def resolve_tab_scout(user_team, player):
    """Return (scout, report) for the Scout Report tab.

    The scout assigned to the player (the ScoutingReport's filing scout)
    wins; otherwise the head scout's cold read. (None, None) when no
    scout is on staff -- the tab must then show the unavailable state,
    never true values as a fallback.
    """
    if user_team is None or player is None:
        return None, None
    try:
        reports = getattr(user_team, 'scouting_reports', None) or {}
        report = reports.get(getattr(player, 'id', None))
    except Exception:
        report = None
    if report is not None:
        scout = getattr(report, 'scout', None)
        if scout is not None:
            return scout, report
    try:
        from team_draft_boards import _head_scout
        head = _head_scout(user_team)
    except Exception:
        head = None
    return head, None


def scout_display_name(scout):
    try:
        return scout.full_name
    except Exception:
        return "Unknown scout"


def attr_label(attr):
    return _ATTR_LABELS.get(attr, attr)


def composite_label(key):
    return _COMPOSITE_LABELS.get(key, key)
