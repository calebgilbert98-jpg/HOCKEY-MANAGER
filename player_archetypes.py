"""Player archetypes for Puck Dynasty: the single source of truth.

An archetype (Sniper, Grinder, Shutdown Defenseman...) describes *how* a player
plays. It drives three systems:

1. Scouting   - pre-built scouting profiles are exactly these archetypes.
2. Chemistry  - linemates with complementary archetypes gel; redundant or
                clashing ones don't (COMPLEMENTARITY matrix).
3. Simulation - archetype-vs-archetype matchups modify shot quality, e.g. a
                Shutdown Defenseman suppresses Snipers but gets burned by
                speed (MATCHUPS matrix).

Attribute thresholds use the real 50-point attribute scale (core attributes
run ~25-50, median ~36; awareness attributes run ~8-26, median ~14).

Pure logic, no GUI.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Archetype definitions: name -> fit profile
# ---------------------------------------------------------------------------
# attributes: {attribute_key: minimum on the 50-point scale}
# positions:  position codes this archetype applies to

ARCHETYPE_FIT: Dict[str, dict] = {
    # -- Forwards ----------------------------------------------------------
    "Sniper": {
        "description": "Elite finishing ability. Lives to put the puck in the net.",
        "attributes": {"shooting": 42, "shooting_accuracy": 42, "offensive_awareness": 18, "skating": 40},
        "positions": ["C", "LW", "RW"],
    },
    "Playmaker": {
        "description": "Sees plays before they happen. Makes linemates better.",
        "attributes": {"passing": 42, "vision": 41, "hockey_iq": 41, "offensive_awareness": 18},
        "positions": ["C", "LW", "RW"],
    },
    "Power Forward": {
        "description": "Size, skill and snarl. Dominates the front of the net.",
        "attributes": {"strength": 41, "checking": 38, "shooting": 40, "balance": 40, "puck_protection": 39},
        "positions": ["C", "LW", "RW"],
    },
    "Two-Way Forward": {
        "description": "Trusted in all situations. Shuts down top lines, chips in offense.",
        "attributes": {"defensive_awareness": 18, "checking": 38,
                       "skating": 38, "discipline": 36},
        "positions": ["C", "LW", "RW"],
    },
    "Grinder": {
        "description": "Relentless on the forecheck. Wins board battles, wears teams down.",
        "attributes": {"determination": 42, "checking": 40, "stamina": 41, "strength": 38, "aggressiveness": 38},
        "positions": ["C", "LW", "RW"],
    },
    "Enforcer": {
        "description": "The toughest player on the ice. Protects teammates, punishes opponents.",
        "attributes": {"toughness": 40, "strength": 39, "aggressiveness": 41, "checking": 38, "durability": 39},
        "positions": ["C", "LW", "RW"],
    },
    # -- Defensemen --------------------------------------------------------
    "Offensive Defenseman": {
        "description": "A fourth forward. Runs the power play from the point.",
        "attributes": {"skating": 40, "passing": 39, "offensive_awareness": 17, "shooting": 39, "vision": 39},
        "positions": ["LD", "RD"],
    },
    "Defensive Defenseman": {
        "description": "Stay-at-home rock. Erases the other team's best players.",
        "attributes": {"checking": 40, "strength": 38, "defensive_awareness": 19,
                       "shot_blocking": 40, "discipline": 36},
        "positions": ["LD", "RD"],
    },
    "Two-Way Defenseman": {
        "description": "Steady in his own end, joins the rush at the right time.",
        "attributes": {"defensive_awareness": 18, "skating": 38, "passing": 38, "checking": 39, "hockey_iq": 40},
        "positions": ["LD", "RD"],
    },
    "Physical Defenseman": {
        "description": "Punishing hitter. Forwards hear footsteps in his corner.",
        "attributes": {"strength": 40, "checking": 40, "toughness": 40, "aggressiveness": 40, "shot_blocking": 39},
        "positions": ["LD", "RD"],
    },
    "Puck-Moving Defenseman": {
        "description": "Clean first pass, skates it out. Starts the breakout.",
        "attributes": {"passing": 40, "vision": 40, "skating": 40, "hockey_iq": 39, "defensive_awareness": 16},
        "positions": ["LD", "RD"],
    },
    # -- Goalies -----------------------------------------------------------
    "Butterfly Goalie": {
        "description": "Technical butterfly. Seals the ice, swallows rebounds.",
        "attributes": {"goaltending": 38, "positioning": 40,
                       "rebound_control": 36},
        "positions": ["G"],
    },
    "Hybrid Goalie": {
        "description": "Reads the play and reacts. Balanced, adaptable style.",
        "attributes": {"goaltending": 38, "reflexes": 38, "positioning": 37},
        "positions": ["G"],
    },
    "Athletic Goalie": {
        "description": "Spectacular saves. Steals games pure athleticism.",
        "attributes": {"reflexes": 40, "goaltending": 36, "composure": 39},
        "positions": ["G"],
    },
    "Puck-Handling Goalie": {
        "description": "A third defenseman. Kills forechecks with his stick.",
        "attributes": {"puck_handling": 39, "goaltending": 36, "composure": 40},
        "positions": ["G"],
    },
}

FORWARD_ARCHETYPES = [n for n, d in ARCHETYPE_FIT.items()
                      if set(d["positions"]) <= {"C", "LW", "RW"}]
DEFENSE_ARCHETYPES = [n for n, d in ARCHETYPE_FIT.items()
                      if set(d["positions"]) <= {"LD", "RD"}]
GOALIE_ARCHETYPES = [n for n, d in ARCHETYPE_FIT.items()
                     if d["positions"] == ["G"]]

FALLBACK_ARCHETYPE = {
    "F": "Depth Forward",
    "D": "Depth Defenseman",
    "G": "Backup Goalie",
}

# Map archetype -> simulation LineRole name (resolved in simulation.py)
ARCHETYPE_TO_ROLE_NAME = {
    "Sniper": "PRIMARY_SCORER",
    "Playmaker": "PLAYMAKER",
    "Power Forward": "POWER_FORWARD",
    "Two-Way Forward": "DEFENSIVE_FORWARD",
    "Grinder": "GRINDER",
    "Enforcer": "ENFORCER",
    "Offensive Defenseman": "OFFENSIVE_DEFENDER",
    "Defensive Defenseman": "SHUTDOWN_DEFENDER",
    "Two-Way Defenseman": "TWO_WAY_DEFENDER",
    "Physical Defenseman": "SHUTDOWN_DEFENDER",
    "Puck-Moving Defenseman": "OFFENSIVE_DEFENDER",
}

# ---------------------------------------------------------------------------
# Attribute resolution (mirrors scouting_profiles)
# ---------------------------------------------------------------------------

def attribute_value(player, key: str) -> float:
    try:
        if key == "toughness":
            parts = [getattr(player, k, 0) or 0
                     for k in ("strength", "durability", "aggressiveness")]
            return sum(parts) / len(parts)
        return float(getattr(player, key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _pos_code(player) -> str:
    try:
        pp = getattr(player, "primary_position", None)
        return getattr(pp, "value", str(pp))
    except Exception:
        return ""


def _pos_group(player) -> str:
    code = _pos_code(player)
    if code == "G":
        return "G"
    if code in ("LD", "RD"):
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def fit_score(player, archetype: str) -> float:
    """0-100: how well a player's true attributes fit an archetype."""
    prof = ARCHETYPE_FIT.get(archetype)
    if not prof or not prof["attributes"]:
        return 0.0
    total = sum(min(1.0, attribute_value(player, k) / m)
                for k, m in prof["attributes"].items() if m > 0)
    n = sum(1 for m in prof["attributes"].values() if m > 0)
    return round(100.0 * total / n, 1) if n else 0.0


def classify_player(player) -> str:
    """Best-fit archetype for a player's position group, or a depth fallback."""
    group = _pos_group(player)
    candidates = {"F": FORWARD_ARCHETYPES, "D": DEFENSE_ARCHETYPES,
                  "G": GOALIE_ARCHETYPES}[group]
    best, best_score = None, 0.0
    for name in candidates:
        s = fit_score(player, name)
        if s > best_score:
            best, best_score = name, s
    if best and best_score >= 60.0:
        return best
    return FALLBACK_ARCHETYPE[group]


def get_archetype(player) -> str:
    """Canonical accessor: stored archetype if valid, else classify + store."""
    a = getattr(player, "archetype", None)
    if a in ARCHETYPE_FIT or a in FALLBACK_ARCHETYPE.values():
        return a
    a = classify_player(player)
    try:
        player.archetype = a
    except Exception:
        pass
    return a


def refresh_archetype(player) -> str:
    """Re-classify from current attributes (call after development)."""
    a = classify_player(player)
    try:
        player.archetype = a
    except Exception:
        pass
    return a


# ---------------------------------------------------------------------------
# Chemistry: archetype complementarity between linemates
# ---------------------------------------------------------------------------
# Symmetric pairs -> chemistry delta in the 0-100 chemistry scale.

def _sym(pairs: Dict[Tuple[str, str], float]) -> Dict[Tuple[str, str], float]:
    out = {}
    for (a, b), v in pairs.items():
        out[(a, b)] = v
        out[(b, a)] = v
    return out


COMPLEMENTARITY = _sym({
    # classic combos
    ("Playmaker", "Sniper"): 12,
    ("Playmaker", "Power Forward"): 8,
    ("Sniper", "Power Forward"): 4,
    ("Power Forward", "Grinder"): 4,
    ("Grinder", "Grinder"): 6,
    # glue guys fit anywhere
    ("Two-Way Forward", "Sniper"): 4,
    ("Two-Way Forward", "Playmaker"): 4,
    ("Two-Way Forward", "Power Forward"): 4,
    ("Two-Way Forward", "Grinder"): 4,
    ("Two-Way Forward", "Two-Way Forward"): 2,
    # protection
    ("Enforcer", "Sniper"): 4,
    ("Enforcer", "Playmaker"): 4,
    ("Enforcer", "Grinder"): 2,
    # redundancy / clashes
    ("Sniper", "Sniper"): -6,
    ("Playmaker", "Playmaker"): -4,
    ("Power Forward", "Power Forward"): -4,
    ("Enforcer", "Enforcer"): -10,
    ("Grinder", "Sniper"): -4,
    ("Grinder", "Playmaker"): -4,
    # defense pairs
    ("Offensive Defenseman", "Defensive Defenseman"): 8,
    ("Offensive Defenseman", "Physical Defenseman"): 6,
    ("Puck-Moving Defenseman", "Defensive Defenseman"): 8,
    ("Puck-Moving Defenseman", "Physical Defenseman"): 6,
    ("Two-Way Defenseman", "Offensive Defenseman"): 4,
    ("Two-Way Defenseman", "Defensive Defenseman"): 4,
    ("Two-Way Defenseman", "Physical Defenseman"): 4,
    ("Two-Way Defenseman", "Puck-Moving Defenseman"): 4,
    ("Two-Way Defenseman", "Two-Way Defenseman"): 2,
    ("Offensive Defenseman", "Offensive Defenseman"): -6,
    ("Offensive Defenseman", "Puck-Moving Defenseman"): -4,
    ("Defensive Defenseman", "Defensive Defenseman"): -4,
    ("Puck-Moving Defenseman", "Puck-Moving Defenseman"): -4,
    ("Physical Defenseman", "Physical Defenseman"): -4,
    ("Physical Defenseman", "Defensive Defenseman"): -2,
})


def complementarity(a1: str, a2: str) -> float:
    """Chemistry delta for a pair of archetypes. 0 if no defined relationship."""
    if a1 == a2:
        return COMPLEMENTARITY.get((a1, a2), -2)
    return COMPLEMENTARITY.get((a1, a2), 0)


# ---------------------------------------------------------------------------
# Simulation: archetype matchup modifiers (attacking vs defending)
# ---------------------------------------------------------------------------
# (attacker_archetype, defender_archetype) -> shot-quality multiplier.

MATCHUPS = {
    # Shutdown-style defenders smother skill...
    ("Sniper", "Defensive Defenseman"): 0.90,
    ("Sniper", "Physical Defenseman"): 0.94,
    ("Playmaker", "Defensive Defenseman"): 0.90,
    ("Playmaker", "Physical Defenseman"): 0.95,
    ("Power Forward", "Defensive Defenseman"): 0.95,
    ("Power Forward", "Physical Defenseman"): 0.97,
    # ...but get burned by speed and outmuscled at the net by soft defenders
    ("Sniper", "Offensive Defenseman"): 1.05,
    ("Playmaker", "Offensive Defenseman"): 1.05,
    ("Power Forward", "Offensive Defenseman"): 1.06,
    ("Sniper", "Puck-Moving Defenseman"): 1.03,
    ("Playmaker", "Puck-Moving Defenseman"): 1.03,
    # Heavy backchecking wears down skill lines
    ("Sniper", "Two-Way Forward"): 0.96,
    ("Playmaker", "Two-Way Forward"): 0.96,
    ("Sniper", "Grinder"): 0.96,
    ("Playmaker", "Grinder"): 0.96,
    # Net-front presence beats puck-movers
    ("Power Forward", "Puck-Moving Defenseman"): 1.04,
    ("Grinder", "Offensive Defenseman"): 1.03,
}


def matchup_multiplier(attacking_archetypes: List[str],
                       defending_archetypes: List[str]) -> float:
    """Combined shot-quality multiplier for on-ice archetype groups."""
    mult = 1.0
    for a in set(attacking_archetypes):
        for d in set(defending_archetypes):
            m = MATCHUPS.get((a, d))
            if m:
                mult *= m
    return max(0.85, min(1.15, mult))


# ---------------------------------------------------------------------------
# Simulation: behavioral tendencies (how archetypes PLAY, not just how well)
# ---------------------------------------------------------------------------
# Multipliers around 1.0 applied to event-selection in the sim:
#   shoot      - likelihood of being picked as the shooter on a shot chance
#   hit        - likelihood of being picked to throw a hit
#   shoot_bias - shoot-vs-pass decision bias (>1 = shoots more; the pass
#                branch scales with (100 - shoot_pass_tendency) / shoot_bias)
#   block      - shot-blocking involvement
#   carry      - controlled zone-entry (rush) tendency
#
# These make archetypes visible in the box score: snipers pile up shots,
# power forwards pile up hits, playmakers pass up shots, grinders block.

ARCHETYPE_TENDENCIES: Dict[str, Dict[str, float]] = {
    # Forwards
    "Sniper":               {"shoot": 1.8, "hit": 0.7, "shoot_bias": 1.5, "block": 0.6, "carry": 1.1},
    "Playmaker":            {"shoot": 0.8, "hit": 0.7, "shoot_bias": 0.6, "block": 0.7, "carry": 1.3},
    "Power Forward":        {"shoot": 1.3, "hit": 1.9, "shoot_bias": 1.1, "block": 0.9, "carry": 1.2},
    "Two-Way Forward":      {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0, "block": 1.3, "carry": 1.0},
    "Grinder":              {"shoot": 0.8, "hit": 1.6, "shoot_bias": 0.9, "block": 1.4, "carry": 0.8},
    "Enforcer":             {"shoot": 0.5, "hit": 2.2, "shoot_bias": 0.7, "block": 1.0, "carry": 0.7},
    # Defense
    "Offensive Defenseman": {"shoot": 1.4, "hit": 0.7, "shoot_bias": 1.2, "block": 0.8, "carry": 1.2},
    "Defensive Defenseman": {"shoot": 0.6, "hit": 1.4, "shoot_bias": 0.8, "block": 1.8, "carry": 0.7},
    "Two-Way Defenseman":   {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0, "block": 1.3, "carry": 1.0},
    "Physical Defenseman":  {"shoot": 0.7, "hit": 2.0, "shoot_bias": 0.8, "block": 1.4, "carry": 0.8},
    "Puck-Moving Defenseman": {"shoot": 0.9, "hit": 0.8, "shoot_bias": 0.9, "block": 0.9, "carry": 1.4},
    # Goalies / depth: neutral
    "Butterfly Goalie":     {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0, "block": 1.0, "carry": 1.0},
    "Hybrid Goalie":        {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0, "block": 1.0, "carry": 1.0},
    "Athletic Goalie":      {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0, "block": 1.0, "carry": 1.0},
    "Puck-Handling Goalie": {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0, "block": 1.0, "carry": 1.0},
}

_DEFAULT_TENDENCY = {"shoot": 1.0, "hit": 1.0, "shoot_bias": 1.0,
                     "block": 1.0, "carry": 1.0}


def get_tendency(player, key: str) -> float:
    """Behavioral tendency multiplier for a player (1.0 = neutral).

    Never raises; falls back to 1.0 for unknown archetypes/keys.
    """
    try:
        arch = get_archetype(player)
        return float(ARCHETYPE_TENDENCIES.get(arch, _DEFAULT_TENDENCY).get(key, 1.0))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Flavor for UI / commentary
# ---------------------------------------------------------------------------

ARCHETYPE_STRENGTHS = {
    "Sniper": "Finishing, one-timers, finding soft spots in coverage.",
    "Playmaker": "Vision, distribution, quarterbacking the attack.",
    "Power Forward": "Net-front dominance, puck protection, physical scoring.",
    "Two-Way Forward": "Positioning, stick detail, matchup reliability.",
    "Grinder": "Forechecking, board battles, wearing opponents down.",
    "Enforcer": "Intimidation, protection, momentum-shifting physicality.",
    "Offensive Defenseman": "Point shots, power-play QB, joining the rush.",
    "Defensive Defenseman": "Gap control, shot blocking, clearing the crease.",
    "Two-Way Defenseman": "Balanced minutes, smart pinches, reliability.",
    "Physical Defenseman": "Big hits, intimidation, punishing along the walls.",
    "Puck-Moving Defenseman": "First pass, zone exits, transition speed.",
}
