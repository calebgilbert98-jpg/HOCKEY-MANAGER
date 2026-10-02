# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Player archetypes for Puck Dynasty: the single source of truth.

An archetype (Sniper, Grinder, Shutdown Defenseman...) describes *how* a player
plays. It drives three systems:

1. Scouting   - pre-built scouting profiles are exactly these archetypes.
2. Chemistry  - linemates with complementary archetypes gel; redundant or
                clashing ones don't (COMPLEMENTARITY matrix).
3. Simulation - archetype-vs-archetype matchups modify shot quality, e.g. a
                Shutdown Defenseman suppresses Snipers but gets burned by
                speed (MATCHUPS matrix).

Attribute thresholds use the native 1-100 attribute scale (core attributes
run ~50-90; awareness attributes run ~60-85 for top players).

Pure logic, no GUI.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Archetype definitions: name -> fit profile
# ---------------------------------------------------------------------------
# attributes: {attribute_key: minimum on the 100-point scale}
# positions:  position codes this archetype applies to

ARCHETYPE_FIT: Dict[str, dict] = {
    # -- Forwards ----------------------------------------------------------
    "Sniper": {
        "description": "Elite finishing ability. Lives to put the puck in the net.",
        "attributes": {"shooting": 84, "shooting_accuracy": 84, "offensive_awareness": 72, "skating": 80},
        "positions": ["C", "LW", "RW"],
    },
    "Playmaker": {
        "description": "Sees plays before they happen. Makes linemates better.",
        "attributes": {"passing": 84, "vision": 82, "hockey_iq": 82, "offensive_awareness": 72},
        "positions": ["C", "LW", "RW"],
    },
    "Power Forward": {
        "description": "Size, skill and snarl. Dominates the front of the net.",
        "attributes": {"strength": 82, "checking": 76, "shooting": 80, "balance": 80, "puck_protection": 78},
        "positions": ["C", "LW", "RW"],
    },
    "Two-Way Forward": {
        "description": "Trusted in all situations. Shuts down top lines, chips in offense.",
        "attributes": {"defensive_awareness": 72, "checking": 76,
                       "skating": 76, "discipline": 72},
        "positions": ["C", "LW", "RW"],
    },
    "Grinder": {
        "description": "Relentless on the forecheck. Wins board battles, wears teams down.",
        "attributes": {"determination": 84, "checking": 80, "stamina": 82, "strength": 76, "aggressiveness": 76},
        "positions": ["C", "LW", "RW"],
    },
    "Enforcer": {
        "description": "The toughest player on the ice. Protects teammates, punishes opponents.",
        "attributes": {"toughness": 80, "strength": 78, "aggressiveness": 82, "checking": 76, "durability": 78},
        "positions": ["C", "LW", "RW"],
    },
    # -- Defensemen --------------------------------------------------------
    "Offensive Defenseman": {
        "description": "A fourth forward. Runs the power play from the point.",
        "attributes": {"skating": 80, "passing": 78, "offensive_awareness": 68, "shooting": 78, "vision": 78},
        "positions": ["LD", "RD"],
    },
    "Defensive Defenseman": {
        "description": "Stay-at-home rock. Erases the other team's best players.",
        "attributes": {"checking": 80, "strength": 76, "defensive_awareness": 76,
                       "shot_blocking": 80, "discipline": 72},
        "positions": ["LD", "RD"],
    },
    "Two-Way Defenseman": {
        "description": "Steady in his own end, joins the rush at the right time.",
        "attributes": {"defensive_awareness": 72, "skating": 76, "passing": 76, "checking": 78, "hockey_iq": 80},
        "positions": ["LD", "RD"],
    },
    "Physical Defenseman": {
        "description": "Punishing hitter. Forwards hear footsteps in his corner.",
        "attributes": {"strength": 80, "checking": 80, "toughness": 80, "aggressiveness": 80, "shot_blocking": 78},
        "positions": ["LD", "RD"],
    },
    "Puck-Moving Defenseman": {
        "description": "Clean first pass, skates it out. Starts the breakout.",
        "attributes": {"passing": 80, "vision": 80, "skating": 80, "hockey_iq": 78, "defensive_awareness": 64},
        "positions": ["LD", "RD"],
    },
    # -- Goalies -----------------------------------------------------------
    "Butterfly Goalie": {
        "description": "Technical butterfly. Seals the ice, swallows rebounds.",
        "attributes": {"goaltending": 76, "positioning": 80,
                       "rebound_control": 72},
        "positions": ["G"],
    },
    "Hybrid Goalie": {
        "description": "Reads the play and reacts. Balanced, adaptable style.",
        "attributes": {"goaltending": 76, "reflexes": 76, "positioning": 74},
        "positions": ["G"],
    },
    "Athletic Goalie": {
        "description": "Spectacular saves. Steals games pure athleticism.",
        "attributes": {"reflexes": 80, "goaltending": 72, "composure": 78},
        "positions": ["G"],
    },
    "Puck-Handling Goalie": {
        "description": "A third defenseman. Kills forechecks with his stick.",
        "attributes": {"puck_handling": 78, "goaltending": 72, "composure": 80},
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
        _v = getattr(pp, "value", None)
        return _v if _v is not None else str(pp)
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


# ---------------------------------------------------------------------------
# Signature composites per archetype (Muck 2026-10-02)
# ---------------------------------------------------------------------------
# The composites that define what each archetype IS. Elite prospects must
# reach 80+ and generational prospects 85+ on these in the best-case
# development scenario -- a Sniper's finishing, a Playmaker's chance
# creation, a shutdown D's defensive play. Thresholds are archetype-aware:
# we never demand 80+ finishing from a Defensive Defenseman.
ARCHETYPE_SIGNATURE_COMPOSITES = {
    # Forwards
    "Sniper": ["finishing"],
    "Playmaker": ["chance_creation"],
    "Power Forward": ["finishing", "physicality"],
    "Two-Way Forward": ["defensive_play"],
    "Grinder": ["puck_retrieval", "physicality"],
    "Enforcer": ["physicality"],
    "Depth Forward": ["physicality"],
    # Defense
    "Offensive Defenseman": ["chance_creation"],
    "Defensive Defenseman": ["defensive_play"],
    "Two-Way Defenseman": ["defensive_play", "chance_creation"],
    "Physical Defenseman": ["physicality", "defensive_play"],
    "Puck-Moving Defenseman": ["chance_creation", "skating"],
    "Depth Defenseman": ["defensive_play"],
    # Goalies
    "Butterfly Goalie": ["goalie_save"],
    "Hybrid Goalie": ["goalie_save"],
    "Athletic Goalie": ["goalie_save"],
    "Puck-Handling Goalie": ["goalie_save"],
    "Backup Goalie": ["goalie_save"],
}


def signature_composites(player) -> list:
    """Key composite names for the player's archetype. Never raises."""
    try:
        arch = get_archetype(player)
        sigs = ARCHETYPE_SIGNATURE_COMPOSITES.get(arch)
        if sigs:
            return list(sigs)
    except Exception:
        pass
    # Fallback by position group: never return empty.
    try:
        group = _pos_group(player)
    except Exception:
        group = "F"
    return {
        "F": ["finishing"],
        "D": ["defensive_play"],
        "G": ["goalie_save"],
    }.get(group, ["finishing"])


# ---------------------------------------------------------------------------
# Reusable chemistry report for UI (lines editor, roster screens, etc.)
# ---------------------------------------------------------------------------

def _player_display_name(player) -> str:
    try:
        name = player.full_name
        if name:
            return str(name)
    except Exception:
        pass
    fn = getattr(player, "first_name", "")
    ln = getattr(player, "last_name", "")
    name = f"{fn} {ln}".strip()
    return name or "Player"


def line_chemistry_report(players):
    """Explain exactly what drives a line/pair's chemistry.

    Uses the canonical COMPLEMENTARITY table (archetype pairs). Returns
    ``(total, drivers)`` where ``total`` is the summed chemistry delta and
    ``drivers`` is a list of ``(text, value)`` tuples, one per archetype
    pair, ordered by absolute impact. ``text`` names both players and
    their archetypes so the UI can show precisely what affects chemistry.

    Never raises; unknown archetypes contribute 0 with no driver entry.
    """
    players = [p for p in players if p is not None]
    drivers = []
    total = 0.0
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            p1, p2 = players[i], players[j]
            try:
                a1, a2 = get_archetype(p1), get_archetype(p2)
            except Exception:
                continue
            value = complementarity(a1, a2)
            if value == 0:
                continue
            total += value
            n1, n2 = _player_display_name(p1), _player_display_name(p2)
            sign = "+" if value > 0 else ""
            if value > 0:
                reason = "complement each other"
            else:
                reason = "duplicate roles" if a1 == a2 else "clash stylistically"
            drivers.append(
                (f"{n1} ({a1}) + {n2} ({a2}): {sign}{value:g} — {reason}",
                 value))
            # International bond (additive): NHL teammates who played a
            # tournament together carry a small familiarity bump.
            try:
                from international import intl_bond, intl_bond_event
                bond = intl_bond(p1, p2)
                etag = intl_bond_event(p1, p2) if bond > 0 else ""
            except Exception:
                bond, etag = 0, ""
            if bond > 0:
                bval = min(3.0, 0.5 * bond)
                total += bval
                drivers.append(
                    (f"{n1} + {n2}: +{bval:g} — international bond"
                     + (f" ({etag})" if etag else ""), bval))
    drivers.sort(key=lambda d: abs(d[1]), reverse=True)
    return total, drivers


def line_chemistry_score(players) -> float:
    """Total chemistry delta for a line/pair (convenience wrapper)."""
    total, _ = line_chemistry_report(players)
    return total


# ---------------------------------------------------------------------------
# Shooter-choice weighting -- ONE decision, two fidelities (divergence #14).
# Both engines weight "who takes the team's shot" with this function so the
# shot chart is a single shared number: archetype shoot tendency (snipers
# lead, playmakers defer) x the Sniper-ish shot_frequency_mult trait,
# flattened (sqrt) so a sniper leads the chart without owning it.
# ---------------------------------------------------------------------------

def _piecewise_tilt(x, points):
    """Linear interpolation over (x, tilt) points. Local copy (no import
    cycle with mesh_system): every curve point stays a named constant."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            _f = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return y0 + _f * (y1 - y0)
    return points[-1][1]


# Shot-volume talent gate curve (2026-09-29, per Muck): steep at the star
# band so elite volume separates by mechanics; the absolute level is set
# so 93+ earns clear separation without cartoon volume. Calibrated
# 2026-09-29 (damper-removal pass): top trimmed ~10% -- 6.5 shots/g for
# elites was feeding the tail; NHL elite is ~4.5 SOG/g. 90+ still
# separates from the 80s (1.13x), just not at cartoon volume.
# Continuous, never a wall.
SHOT_VOLUME_TALENT_POINTS = (
    (60, 0.52), (65, 0.60), (70, 0.68), (75, 0.75), (80, 0.80),
    (85, 0.84), (88, 0.86), (90, 0.88), (92, 0.88), (95, 0.90),
)


def shooter_choice_weight(player) -> float:
    """Relative likelihood this skater takes his team's shot. >= 0.05.

    Shared decision (both engines): tendency is ROLE (snipers shoot), the
    talent gate is TALENT (a 65-ovr sniper must not out-shoot a 92-ovr
    star). The gate sits OUTSIDE the sqrt -- the sqrt compresses role
    differences, talent differences must survive it.
    """
    try:
        from player_traits import get_sim_bonus as _bonus
        _t = get_tendency(player, "shoot")
        _w = max(0.05, float(_t)) * float(_bonus(player, "shot_frequency_mult"))
        # Defenseman volume adjustment (shared decision, mesh_system):
        # D take 47.6% of shots, should be ~33%. Correct the volume.
        try:
            from game_classes import PlayerPosition as _PP
            from mesh_system import DEFENSE_SHOT_VOLUME_MULT as _dvm
            _pos = getattr(player, "primary_position", None)
            if _pos in (_PP.DEFENSE, _PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE):
                _w *= _dvm
        except Exception:
            pass
        _w = max(0.05, _w) ** 0.5
        # Talent gates VOLUME (2026-09-29, per Muck): a 65-ovr sniper was
        # taking 7.7 shots/game -- more than stars -- because tendency is
        # archetype-only. SHOT_VOLUME_TALENT_POINTS curve, NO CAPS (per Muck
        # 2026-09-29): steep at the star band so elite volume separates by
        # mechanics, gentle below so depth still shoots. Never a wall.
        # 2026-10-01: Gate on FINISHING, not overall. Shot volume must follow
        # scoring ability -- a 82-ovr playmaker with 70 finishing must not
        # take star-level shots (the 105G cartoon: 74-finisher on 740 attempts).
        # Finishing orders who shoots; overall still matters via the tendency.
        try:
            from mesh_system import finishing_rating as _fr
            _ovr = float(_fr(player))
        except Exception:
            try:
                _ovr = float(player.overall_rating())
            except Exception:
                _ovr = float(getattr(player, "overall", 82.0) or 82.0)
        _talent_gate = _piecewise_tilt(_ovr, SHOT_VOLUME_TALENT_POINTS)
        return max(0.05, _w * _talent_gate)
    except Exception:
        return 1.0
