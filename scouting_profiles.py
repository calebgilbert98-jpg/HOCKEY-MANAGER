"""Scouting profiles for Puck Dynasty: pre-built and custom player archetypes.

Pure logic, no GUI. Powers the Scouting Department window's profile filtering.

A profile is a named set of attribute minimums (e.g. Enforcer: strength 40,
aggressiveness 40). Applying a profile filters the player pool to skaters who
meet every minimum and sorts them by match score.

Fog of war: unscouted players are evaluated with stable per-player noise, so
profiles are most reliable on scouted players - just like real scouting.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

PROFILES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "scouting_profiles.json")

# ---------------------------------------------------------------------------
# Attribute catalog
# ---------------------------------------------------------------------------
# (key, label) pairs offered in the profile builder. 'toughness' is a
# composite (strength/durability/aggressiveness) since players don't carry a
# raw toughness field.

SKATER_ATTRIBUTES: List[Tuple[str, str]] = [
    ("skating", "Skating"),
    ("speed", "Speed"),
    ("shooting", "Shooting"),
    ("shooting_accuracy", "Shooting Accuracy"),
    ("passing", "Passing"),
    ("checking", "Checking"),
    ("strength", "Strength"),
    ("toughness", "Toughness"),
    ("aggressiveness", "Aggressiveness"),
    ("durability", "Durability"),
    ("balance", "Balance"),
    ("stamina", "Stamina"),
    ("hockey_iq", "Hockey IQ"),
    ("determination", "Determination"),
    ("discipline", "Discipline"),
    ("offensive_awareness", "Offensive Awareness"),
    ("defensive_awareness", "Defensive Awareness"),
    ("vision", "Vision"),
    ("shot_blocking", "Shot Blocking"),
    ("forechecking", "Forechecking"),
    ("puck_protection", "Puck Protection"),
]

GOALIE_ATTRIBUTES: List[Tuple[str, str]] = [
    ("goaltending", "Goaltending"),
    ("reflexes", "Reflexes"),
    ("positioning", "Positioning"),
    ("rebound_control", "Rebound Control"),
    ("puck_handling", "Puck Handling"),
    ("composure", "Composure"),
]

ALL_ATTRIBUTES: Dict[str, str] = dict(SKATER_ATTRIBUTES + GOALIE_ATTRIBUTES)

# Typical ranges (sampled from generation): core attributes run ~25-50 with a
# median near 36; awareness attributes run ~8-26 with a median near 14.
AWARENESS_KEYS = {"offensive_awareness", "defensive_awareness"}


def attribute_value(player, key: str) -> float:
    """Resolve an attribute key to a numeric value for a player."""
    try:
        if key == "toughness":
            parts = [getattr(player, k, 0) or 0
                     for k in ("strength", "durability", "aggressiveness")]
            return sum(parts) / len(parts)
        return float(getattr(player, key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def fogged_value(player, key: str, scouted: bool) -> float:
    """Attribute value with fog-of-war noise for unscouted players.

    Noise is stable per player+attribute (seeded), so repeated views agree.
    """
    val = attribute_value(player, key)
    if scouted:
        return val
    rng = random.Random(f"fog-{getattr(player, 'id', '')}-{key}")
    return val * rng.uniform(0.88, 1.12)


# ---------------------------------------------------------------------------
# Profile model
# ---------------------------------------------------------------------------

@dataclass
class ScoutingProfile:
    name: str
    description: str = ""
    attributes: Dict[str, int] = field(default_factory=dict)  # key -> minimum
    positions: List[str] = field(default_factory=list)  # e.g. ["C","LW","RW"]; empty = any
    builtin: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("builtin", None)
        return d

    @classmethod
    def from_dict(cls, d: dict, builtin: bool = False) -> "ScoutingProfile":
        return cls(
            name=d.get("name", "Unnamed"),
            description=d.get("description", ""),
            attributes={k: int(v) for k, v in d.get("attributes", {}).items()
                        if k in ALL_ATTRIBUTES},
            positions=list(d.get("positions", [])),
            builtin=builtin,
        )


def _builtin_profiles() -> List[ScoutingProfile]:
    """Pre-built profiles are exactly the player archetypes.

    Defined once in player_archetypes; the same attribute minimums drive
    classification, chemistry and the sim engine, so what you scout for is
    what you get on the ice.
    """
    from player_archetypes import ARCHETYPE_FIT
    out = []
    for name, fit in ARCHETYPE_FIT.items():
        out.append(ScoutingProfile(
            name=name,
            description=fit.get("description", ""),
            attributes=dict(fit.get("attributes", {})),
            positions=list(fit.get("positions", [])),
            builtin=True,
        ))
    return out


def _load_custom_profiles() -> List[ScoutingProfile]:
    try:
        with open(PROFILES_FILE, "r") as f:
            data = json.load(f)
        return [ScoutingProfile.from_dict(d) for d in data
                if isinstance(d, dict) and d.get("name")]
    except (OSError, ValueError):
        return []


def list_profiles() -> List[ScoutingProfile]:
    """All profiles: built-ins first, then user-saved customs."""
    return _builtin_profiles() + _load_custom_profiles()


def get_profile(name: str) -> Optional[ScoutingProfile]:
    for p in list_profiles():
        if p.name == name:
            return p
    return None


def save_custom_profile(profile: ScoutingProfile) -> None:
    """Save (or overwrite by name) a user profile."""
    customs = [p for p in _load_custom_profiles() if p.name != profile.name]
    profile.builtin = False
    customs.append(profile)
    try:
        with open(PROFILES_FILE, "w") as f:
            json.dump([p.to_dict() for p in customs], f, indent=2)
    except OSError:
        pass


def delete_custom_profile(name: str) -> bool:
    customs = [p for p in _load_custom_profiles() if p.name != name]
    if len(customs) == len(_load_custom_profiles()):
        return False
    try:
        with open(PROFILES_FILE, "w") as f:
            json.dump([p.to_dict() for p in customs], f, indent=2)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _pos_code(player) -> str:
    try:
        pp = getattr(player, "primary_position", None)
        return getattr(pp, "value", str(pp))
    except Exception:
        return ""


def meets_profile(player, profile: ScoutingProfile, scouted: bool) -> bool:
    """True if the player meets every attribute minimum (fog applied)."""
    if profile.positions and _pos_code(player) not in profile.positions:
        return False
    for key, minimum in profile.attributes.items():
        if fogged_value(player, key, scouted) < minimum:
            return False
    return True


def match_score(player, profile: ScoutingProfile, scouted: bool) -> float:
    """0-100 fit score: average fulfillment of each attribute minimum."""
    if not profile.attributes:
        return 0.0
    total = 0.0
    for key, minimum in profile.attributes.items():
        if minimum <= 0:
            continue
        total += min(1.0, fogged_value(player, key, scouted) / minimum)
    n = sum(1 for m in profile.attributes.values() if m > 0)
    return round(100.0 * total / n, 1) if n else 0.0


def filter_by_profile(players, profile: ScoutingProfile,
                      is_scouted_fn) -> List[tuple]:
    """Return [(player, score)] for players meeting the profile, best first."""
    out = []
    for p in players:
        try:
            scouted = bool(is_scouted_fn(p))
            if meets_profile(p, profile, scouted):
                out.append((p, match_score(p, profile, scouted)))
        except Exception:
            continue
    out.sort(key=lambda t: t[1], reverse=True)
    return out
