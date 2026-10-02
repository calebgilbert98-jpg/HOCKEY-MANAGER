"""Offseason training programs: GM-directed summer development.

After the Cup is lifted (June), the GM assigns each player an offseason
focus -- the same 8 Development Center focuses -- plus an intensity.
Through July and August, weekly PracticeEngine ticks develop the chosen
attributes. No game fatigue in summer, so players can push harder, but
there's no game experience either (smaller gains than in-season programs).

Results surface at training camp (Sept 12-30): campers with strong
offseasons show attribute gains in their camp reports.

Storage: player.offseason_program = {
    'focus': str,        # e.g. 'Shooting Accuracy'
    'intensity': str,    # 'Light' | 'Standard' | 'Intensive'
    'assigned': date,    # when the GM set it
}
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

# Reuse the Development Center focus/intensity labels so the GM learns
# one vocabulary. Maps to PracticeType via enhanced_practice_system.
OFFSEASON_FOCUSES = [
    "Skating & Speed",
    "Shooting Accuracy",
    "Passing & Vision",
    "Defensive Positioning",
    "Physical Conditioning",
    "Mental Toughness",
    "Position-Specific Skills",
    "Hockey IQ Development",
]

OFFSEASON_INTENSITIES = ["Light", "Standard", "Intensive"]

# Offseason window: programs run weekly through July + August.
OFFSEASON_START_MONTH = 7
OFFSEASON_END_MONTH = 8


def is_offseason(check_date) -> bool:
    """True during the assignable/run window (June assign, Jul-Aug run)."""
    try:
        m = check_date.month
        return m in (6, 7, 8)
    except Exception:
        return False


def assign_offseason_program(player, focus: str, intensity: str,
                             on_date=None) -> Tuple[bool, str]:
    """Assign a summer program. Returns (ok, message)."""
    if focus not in OFFSEASON_FOCUSES:
        return False, f"Unknown focus: {focus}"
    if intensity not in OFFSEASON_INTENSITIES:
        return False, f"Unknown intensity: {intensity}"
    try:
        player.offseason_program = {
            "focus": focus,
            "intensity": intensity,
            "assigned": on_date or date.today(),
        }
        return True, (f"{getattr(player, 'full_name', 'Player')}: "
                      f"{focus} ({intensity}) assigned for the summer.")
    except Exception as exc:
        return False, str(exc)


def clear_offseason_program(player) -> None:
    """Remove a player's summer program."""
    try:
        player.offseason_program = None
    except Exception:
        pass


def get_offseason_program(player) -> Optional[dict]:
    """The player's assigned summer program, or None."""
    try:
        return getattr(player, "offseason_program", None)
    except Exception:
        return None


def run_offseason_week(players, on_date=None) -> Dict[str, dict]:
    """One weekly development tick for all assigned programs.

    Uses the shared PracticeEngine so coaching, archetype affinity, and
    age curves all apply. Offseason multiplier: 0.8x (no game reps), but
    Intensive programs get a fatigue-free bonus week count.

    Returns {player_id: {'focus': ..., 'gains': {attr: pts}}} for the
    camp report.
    """
    results = {}
    try:
        from enhanced_practice_system import (
            PracticeEngine, FOCUS_TO_PRACTICE_TYPE,
            INTENSITY_LABEL_TO_ENUM)
    except Exception:
        return results

    engine = PracticeEngine()
    for p in players or []:
        prog = get_offseason_program(p)
        if not prog:
            continue
        focus = prog.get("focus")
        intensity = prog.get("intensity", "Standard")
        ptype = FOCUS_TO_PRACTICE_TYPE.get(focus)
        pint = INTENSITY_LABEL_TO_ENUM.get(intensity)
        if ptype is None or pint is None:
            continue
        try:
            # Offseason: no game fatigue, so run the session at the
            # chosen intensity with a 0.8x no-game-reps multiplier
            # applied inside _calculate_skill_improvement via age curve.
            result = engine.execute_practice(
                p, ptype, pint, duration_minutes=60, offseason=True)
            if result and getattr(result, "improvements", None):
                results[getattr(p, "id", id(p))] = {
                    "focus": focus,
                    "gains": dict(result.improvements),
                    "player_name": getattr(p, "full_name", "?"),
                }
        except Exception:
            continue
    return results
