"""team_fatigue.py -- team-level in-game fatigue factor for the lightweight.

The event sim (AdvancedGameSim) multiplies each shooter's shot/deke/pass
probability by an in-game fatigue factor (0.4-1.0) that declines as shifts
accumulate, paced by the stamina/endurance/durability blend
(condition_system.fatigue_resistance -- the canonical W3 blend, read here,
never redefined).

Measured 2026-09-30 (150 paired games, fatigue on vs patched-off):
  event-sim scoring WITH the channel is ~20% lower than without it;
  the event-weighted mean multiplier is 0.835 (SD 0.10), team-game mean
  0.836 (SD 0.012). The lightweight's calibrated baseline (base_goals)
  already absorbs that mean -- verified by aggregate scoring parity --
  so this module adds back ONLY the team-level variation: iron-lung rooms
  tire slower and generate more shot volume than fragile rooms.

Mean-neutral by construction (1.0 at the canonical resistance 70), so the
calibrated baseline doesn't move. Pure read: never mutates team/league/
player state. Never raises -- any failure degrades to 1.00.

E7-era note (2026-10-02): the event sim's fatigue differentiation widened
~3.6x when it moved onto the canonical per-game energy pool, so the slope
was re-sized 0.0013 -> 0.0045 to keep tracking it (F2). The absolute design
carries a small, stable ~1.5% league-mean lift because generated
top-10-by-OVR stamina blends average ~73, not the canonical 70 -- documented
and bounded by QA F4, well within sim calibration noise.
"""

# ----------------------------------------------------------------------
# Tuning (flagged for Chris's sign-off -- not yet approved)
# ----------------------------------------------------------------------
#: Per-point slope of the fatigue factor on the stamina blend. Sized from
#: the event sim on current main: fresh-vs-gassed (90/50 stamina blend)
#: mean fatigue-multiplier delta is 0.178 over a 40-pt blend gap ->
#: ~0.0045/pt. (2026-09-30 sizing was 0.0013/pt against a 0.0495 delta;
#: Caleb's E7 retargeted the event sim onto the canonical per-game
#: energy pool, widening the stamina differentiation ~3.6x, so the
#: bridge was re-sized to track it.) A 10-point blend gap (large) moves
#: goal expectation ~4.5%.
_FATIGUE_SLOPE = 0.0045
#: Canonical neutral resistance (condition_system: neutral at 70).
_FATIGUE_BASELINE = 70.0
#: Hard cap on the deviation -- binds at ~+/-23 blend points from neutral
#: (same design ratio as the original 0.03 cap at 0.0013 slope).
_FATIGUE_CAP = 0.10
#: Skaters counted, by overall_rating: the shot-volume drivers.
_FATIGUE_CORE_N = 10


def team_fatigue_factor(team):
    """Team-level in-game fatigue multiplier for goal expectation.

    1.0 = neutral (league-average stamina blend). Above 1.0 for iron-lung
    rooms, below for fragile ones. Clamped to [0.90, 1.10].
    """
    try:
        from condition_system import fatigue_resistance as _res
        roster = getattr(team, "roster", None) or []
        skaters = [p for p in roster
                   if getattr(getattr(p, "primary_position", None),
                              "name", "") != "GOALIE"]
        if not skaters:
            return 1.0
        try:
            skaters.sort(key=lambda p: p.overall_rating(), reverse=True)
        except Exception:
            pass
        core = skaters[:_FATIGUE_CORE_N]
        blend = sum(_res(p) for p in core) / max(1, len(core))
        factor = 1.0 + _FATIGUE_SLOPE * (blend - _FATIGUE_BASELINE)
        return max(1.0 - _FATIGUE_CAP, min(1.0 + _FATIGUE_CAP, factor))
    except Exception:
        return 1.0
