# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Scoring-balance tuning knobs shared by both sim engines.

One decision, two fidelities: GameSim (simulation.py) and AdvancedGameSim
(quick_sim.py) apply the SAME decisions below; each applies them at its own
shot-resolution gate. Never two copies of a decision.

Knobs (2026-09-28, Muck's direction: nudge OT rate toward the NHL ~23% and
goalie SV% slightly toward .900):
  - BASE_SAVE_TUNE: multiplicative goal-suppression applied at each engine's
    base save calculation. 0.95 ~= -5% goals, SV% .892 -> ~.897, GPG stays
    inside the 2.70-3.60 band.
  - tie_late_factor(): "protect the point" is real hockey -- tied in the 3rd
    with under 10:00 left, both teams trade chances for structure. Applied on
    the xG/shot-chance gate (finishing), own channel, never overrides agreed
    math. Manufactures the regulation ties the NHL's OT rate expects.

Perf: pure arithmetic, called per shot. No state, no I/O.
Kill switch: set both constants to 1.0 to restore prior behavior exactly.
"""

BASE_SAVE_TUNE = 0.95

TIE_LATE_WINDOW_SECONDS = 600
TIE_LATE_XG_MULT = 0.80


def tie_late_factor(period, seconds_left, home_score, away_score):
    """Return the xG multiplier for tie-game late tightening.

    0.80 when tied in the 3rd with under 10:00 remaining, else 1.0.
    Never raises; garbage in -> 1.0 out.
    """
    try:
        if (int(period) == 3
                and float(seconds_left) < TIE_LATE_WINDOW_SECONDS
                and int(home_score) == int(away_score)):
            return TIE_LATE_XG_MULT
        return 1.0
    except Exception:
        return 1.0
