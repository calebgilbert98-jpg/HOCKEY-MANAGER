# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""6-on-5 attack model: shared generation-side mechanics for the pulled-goalie
segment (workstream B, 2026-09-30, per Muck).

When a team trails and pulls its goalie, the six-attacker unit is a REAL
attack, not just an empty net. Two generation-side mechanics -- both engines
call the same helpers (one decision, two fidelities):

1. OZ sustenance: six attackers clog the zone -- the leading team's clears
   get picked off and the cycle grinds on. Implemented as a turnover->cycle
   shift on the chance-generation mix (never on finishing). Mostly
   structural (six vs five), modulated by personnel.
2. Scramble factor: net-front chaos -- rebounds, tips, quick-release looks.
   Personnel-scaled attribute-vs-attribute: the unit's net-front craft
   (off_the_puck, offensive_positioning, deflections/hand-eye, loose_puck),
   shooting and hockey IQ against the defense's box-out (strength,
   defensive_positioning, defensive_awareness). Rides the shared grade
   roll's game_ctx as "six_on_five_tilt" -- generation side (WHO grades A),
   never the finishing mults/clamps.

The empty-net risk stays honest: the leading team still converts its live
turnovers through both engines' untouched EN mechanisms.

Protected levers (mesh_system.CHANCE_GRADE_FINISH_MULT /
CHANCE_GRADE_CLAMP) are never touched by this module -- it only moves
chance GENERATION.

Replaces the old flat 6v5 multiplier (divergence #13): the flat mult forced
every 6v5 tick into a shot, which (a) starved the event mix of any texture
and (b) starved the empty-net feed -- with no live turnovers, the leading
team never got its honest EN chances. The model below keeps the six-man
volume edge but through the mix, so turnovers (and EN risk) stay real.

Pure reads; never raises. Kill-switch SIX_ON_FIVE_MODEL_ENABLED for paired
budget measurement (drama goal-contribution).
"""

# Master switch for paired budget measurement. Engines check it and fall
# back to their pre-model behavior when False.
SIX_ON_FIVE_MODEL_ENABLED = True

# -- tuning: all in one place -------------------------------------------
# Base grade-A tilt from 6v5 chaos (net-front scramble, no structure).
SCRAMBLE_BASE_TILT = 1.30
# Personnel edge mapping: +/-20 net-front edge -> tilt x1.18 / x0.85.
SCRAMBLE_EDGE_SCALE = 0.009
SCRAMBLE_TILT_MIN = 0.85
SCRAMBLE_TILT_MAX = 1.50
# OZ sustenance: base share of turnover mass the six-man unit kills.
SUSTAIN_BASE_KEEP = 0.62
# Personnel edge mapping on the keep: +/-20 forecheck edge -> +/-0.10.
SUSTAIN_EDGE_SCALE = 0.005
SUSTAIN_KEEP_MIN = 0.45
SUSTAIN_KEEP_MAX = 0.85
# Freed turnover mass: this share flows to cycle, the rest to maintain.
SUSTAIN_CYCLE_SHARE = 0.65
# Honest volume: the six-man unit's shot-volume edge, personnel-scaled.
VOLUME_BASE = 1.55
VOLUME_EDGE_SCALE = 0.006
VOLUME_MIN = 1.30
VOLUME_MAX = 1.90
# QS possession retention: probability a 6v5 event keeps the puck with the
# pulling team (vs the 0.50 coin flip). Personnel-scaled.
RETENTION_BASE = 0.66
RETENTION_EDGE_SCALE = 0.004
RETENTION_MIN = 0.56
RETENTION_MAX = 0.78


def _attr(p, name, default=50.0):
    try:
        v = getattr(p, name, default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _off_pos(p):
    try:
        from mesh_system import offensive_positioning as _op
        return float(_op(p))
    except Exception:
        return _attr(p, "offensive_positioning", 50.0)


def _def_pos(p):
    try:
        from mesh_system import defensive_positioning as _dp
        return float(_dp(p))
    except Exception:
        return _attr(p, "defensive_positioning", 50.0)


def _mean(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return 50.0
    return sum(vals) / len(vals)


def _skaters(unit):
    """Goalies never count in a six-attacker unit rating."""
    try:
        from game_classes import PlayerPosition as _PP
        _g = _PP.GOALIE
    except Exception:
        _g = None
    out = []
    for p in (unit or []):
        if p is None:
            continue
        try:
            if _g is not None and getattr(p, "primary_position", None) == _g:
                continue
        except Exception:
            pass
        out.append(p)
    return out


def unit_netfront_rating(unit):
    """Mean net-front craft of a unit (1-100): off_the_puck 0.30 (find the
    soft spot) + offensive_positioning 0.30 (get open, seal it) +
    deflections 0.20 (hand-eye) + loose_puck 0.10 (win the scramble) +
    shooting 0.10 (finish in tight). Never raises."""
    try:
        _u = _skaters(unit)
        if not _u:
            return 50.0
        return _mean([
            _attr(p, "off_the_puck") * 0.30
            + _off_pos(p) * 0.30
            + _attr(p, "deflections") * 0.20
            + _attr(p, "loose_puck") * 0.10
            + _attr(p, "shooting") * 0.10
            for p in _u
        ])
    except Exception:
        return 50.0


def unit_shooting_rating(unit):
    """Mean shooting of a unit: shooting/shooting_accuracy blend."""
    try:
        _u = _skaters(unit)
        if not _u:
            return 50.0
        return _mean([(_attr(p, "shooting") + _attr(p, "shooting_accuracy"))
                      / 2.0 for p in _u])
    except Exception:
        return 50.0


def unit_iq_rating(unit):
    """Mean hockey IQ of a unit: offensive_awareness."""
    try:
        _u = _skaters(unit)
        if not _u:
            return 50.0
        return _mean([_attr(p, "offensive_awareness") for p in _u])
    except Exception:
        return 50.0


def unit_boxout_rating(unit):
    """Mean box-out of a defending unit: strength 0.40 + defensive
    positioning 0.35 + defensive_awareness 0.25. Never raises."""
    try:
        _u = _skaters(unit)
        if not _u:
            return 50.0
        return _mean([
            _attr(p, "strength") * 0.40
            + _def_pos(p) * 0.35
            + _attr(p, "defensive_awareness") * 0.25
            for p in _u
        ])
    except Exception:
        return 50.0


def unit_forecheck_rating(unit):
    """Mean forecheck/keep-in of a unit: skating 0.40 + strength 0.30 +
    balance 0.30 (win the wall battles, hold the line)."""
    try:
        _u = _skaters(unit)
        if not _u:
            return 50.0
        return _mean([
            _attr(p, "skating") * 0.40
            + _attr(p, "strength") * 0.30
            + _attr(p, "balance") * 0.30
            for p in _u
        ])
    except Exception:
        return 50.0


def unit_clear_rating(unit):
    """Mean clear ability of a defending unit: strength 0.40 +
    defensive_awareness 0.30 + composure 0.30 (take the hit, make the
    play under 6v5 pressure)."""
    try:
        _u = _skaters(unit)
        if not _u:
            return 50.0
        return _mean([
            _attr(p, "strength") * 0.40
            + _attr(p, "defensive_awareness") * 0.30
            + _attr(p, "composure") * 0.30
            for p in _u
        ])
    except Exception:
        return 50.0


def scramble_tilt(attacking_unit, defending_unit):
    """Grade-A tilt for 6v5 chances (multiplier on the grade-A probability
    inside the shared grade roll -- generation side only).

    Base chaos 1.30 (six attackers, scrambling structure) scaled by the
    personnel edge, attribute-vs-attribute: attack net-front 0.50 +
    shooting 0.25 + IQ 0.25 vs defense box-out. A +20 edge (elite
    net-front unit vs soft coverage) tilts x1.18; a -20 edge (smothered)
    tilts x0.85. Bounded [0.85, 1.50]. Never raises.
    """
    try:
        if not SIX_ON_FIVE_MODEL_ENABLED:
            return 1.0
        _att = (unit_netfront_rating(attacking_unit) * 0.50
                + unit_shooting_rating(attacking_unit) * 0.25
                + unit_iq_rating(attacking_unit) * 0.25)
        _dfn = unit_boxout_rating(defending_unit)
        _edge = _att - _dfn
        _tilt = SCRAMBLE_BASE_TILT * (1.0 + _edge * SCRAMBLE_EDGE_SCALE)
        return max(SCRAMBLE_TILT_MIN, min(SCRAMBLE_TILT_MAX, _tilt))
    except Exception:
        return 1.0


def oz_sustenance_shift(attacking_unit, defending_unit):
    """(turnover_keep, cycle_share): the six-man unit's zone sustenance.

    turnover_keep: share of the turnover probability mass that SURVIVES
    (the rest is killed by six-man pressure and flows to cycle/maintain).
    cycle_share: of the killed mass, the share flowing to cycle (rest to
    maintain). Mostly structural (six vs five clogs the zone); personnel
    edge (forecheck vs clear) moves the keep +/-0.10. Never raises.
    """
    try:
        if not SIX_ON_FIVE_MODEL_ENABLED:
            return 1.0, SUSTAIN_CYCLE_SHARE
        _edge = (unit_forecheck_rating(attacking_unit)
                 - unit_clear_rating(defending_unit))
        _keep = SUSTAIN_BASE_KEEP + _edge * SUSTAIN_EDGE_SCALE
        _keep = max(SUSTAIN_KEEP_MIN, min(SUSTAIN_KEEP_MAX, _keep))
        return _keep, SUSTAIN_CYCLE_SHARE
    except Exception:
        return SUSTAIN_BASE_KEEP, SUSTAIN_CYCLE_SHARE


def six_on_five_volume(attacking_unit, defending_unit):
    """Shot-volume edge for the six-man unit (multiplier on the volume
    gate, pre-clamp so the engine's texture clamp still binds).
    Personnel-scaled: net-front 0.40 + shooting 0.35 + IQ 0.25 vs
    box-out. Base 1.55, bounded [1.30, 1.90]. Never raises."""
    try:
        if not SIX_ON_FIVE_MODEL_ENABLED:
            return 1.0
        _att = (unit_netfront_rating(attacking_unit) * 0.40
                + unit_shooting_rating(attacking_unit) * 0.35
                + unit_iq_rating(attacking_unit) * 0.25)
        _dfn = unit_boxout_rating(defending_unit)
        _edge = _att - _dfn
        _vol = VOLUME_BASE * (1.0 + _edge * VOLUME_EDGE_SCALE)
        return max(VOLUME_MIN, min(VOLUME_MAX, _vol))
    except Exception:
        return 1.0


def apply_6v5_mix(shot_chance, turnover_chance, cycle_chance,
                  attacking_unit, defending_unit):
    """Apply the 6v5 attack model to an OZ event mix (GameSim fidelity).

    Volume edge rides the shot gate (pre-clamp -- call BEFORE the
    engine's texture clamp so it still binds); the sustenance shift
    kills turnover mass into cycle/maintain AFTER (order-independent).
    Returns (shot_chance, turnover_chance, cycle_chance). Never raises.
    """
    try:
        if not SIX_ON_FIVE_MODEL_ENABLED:
            return shot_chance, turnover_chance, cycle_chance
        _vol = six_on_five_volume(attacking_unit, defending_unit)
        shot_chance = shot_chance * _vol
        _keep, _cyc = oz_sustenance_shift(attacking_unit, defending_unit)
        _freed = turnover_chance * (1.0 - _keep)
        turnover_chance = turnover_chance * _keep
        cycle_chance = cycle_chance + _freed * _cyc
        # the rest of the freed mass flows to maintain downstream
        return shot_chance, turnover_chance, cycle_chance
    except Exception:
        return shot_chance, turnover_chance, cycle_chance


def oz_possession_retention(attacking_unit, defending_unit):
    """QS fidelity of OZ sustenance: probability the NEXT event keeps the
    puck with the 6v5 attack (vs the 0.50 coin flip). The 6v5 lives in
    the OZ -- sustained pressure, not alternating possessions.
    Personnel-scaled via the same forecheck-vs-clear edge. Never raises.
    """
    try:
        if not SIX_ON_FIVE_MODEL_ENABLED:
            return 0.50
        _edge = (unit_forecheck_rating(attacking_unit)
                 - unit_clear_rating(defending_unit))
        _r = RETENTION_BASE + _edge * RETENTION_EDGE_SCALE
        return max(RETENTION_MIN, min(RETENTION_MAX, _r))
    except Exception:
        return RETENTION_BASE


def grade_tilt_ctx(attacking_unit, defending_unit):
    """game_ctx fragment for the shared grade roll: the 6v5 scramble
    tilt. Engines merge this into the game_ctx they already build.
    Generation side only. Never raises."""
    try:
        return {"six_on_five_tilt": scramble_tilt(attacking_unit,
                                                  defending_unit)}
    except Exception:
        return {}
