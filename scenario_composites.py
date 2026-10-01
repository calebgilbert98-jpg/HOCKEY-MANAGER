#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Scenario-level composite combinations — the shared battle layer.

Pipeline: attributes -> composites (attribute_composites.py) ->
scenario combos (this module) -> on-ice scenario probabilities.

A *scenario* is a recognizable hockey situation (odd-man rush, net-front
scramble, 3v3 dash, PK clear...) resolved as a composite-vs-composite
battle: the offense's scenario rating against the defense's, mapped
through one bounded logistic into a probability amplifier.

THE shared copy. Both engines (GameSim watch, AdvancedGameSim quick)
call apply_scenario() identically — one decision, two fidelities.

Design contract (per the Scenario Combos design doc, 2026-09-30):
- Pipeline purity: scenarios read COMPOSITE ratings only, never raw
  attributes. Enforced at import: every scenario member must be a key
  of COMPOSITE_KEYS.
- Strictly additive: amp = 1 + R*tanh(edge / 20), hard-clamped to the
  scenario's rails. No 0%/100% mappings.
- Mean-neutral: edge 0 -> amp exactly 1.0.
- Dynamic: circumstance_shift flows per player per composite.
- Storytelling: narrative tags + story line; detail=True reports the
  decisiveness band for pbp/headlines.
- Additive layering: this module goes on top; it supersedes overlapping
  single-composite hooks at wiring time (never stacks with them).

Also home to two shared parity mechanisms (2026-09-30, Muck):
- apply_schemed_threat(): the schemed-against-superstars battle, expressed
  AS a scenario battle (offense-threat composites vs the defending TEAM's
  collective defensive commitment) instead of a bolt-on. Elite-gated,
  McDavid floor, zero-sum linemate relief, spontaneity kept.
- LiveHeat: the shared bounded in-game heat accumulator both engines
  update (fights/majors/brawls) so a game that boils over feels alive
  watched or quick.
"""

import math

try:
    from attribute_composites import (
        COMPOSITE_KEYS as _KEYS,
        raw_composite as _raw,
        circumstance_shift as _shift,
        BASELINE as _BASELINE,
    )
except Exception:  # pragma: no cover - defensive for headless import order
    _KEYS = ()
    _raw = None
    _shift = None
    _BASELINE = 70.0

_SPREAD = 20.0  # logistic spread, matches attribute_composites

# ---------------------------------------------------------------------------
# 18-scenario catalog (ships as specced in the design doc; reweight only if
# QA demands it). Weights sum to 1.0 per side. Rails straddle 1.0; scoring-
# adjacent scenarios carry tighter rails.
# ---------------------------------------------------------------------------
SCENARIOS = {
    # -- even strength -----------------------------------------------------
    "rush_chance": {
        "offense": {"skating": 0.35, "chance_creation": 0.35, "finishing": 0.30},
        "defense": {"defensive_play": 0.55, "goalie_save": 0.45},
        "rails": (0.95, 1.05),
        "event": "rush chance generation",
        "context": ("EV",),
        "story": "speed through the neutral zone turns into a clean look",
        "tags": ("rush", "even-strength"),
    },
    "odd_man_rush": {
        "offense": {"skating": 0.30, "chance_creation": 0.30, "finishing": 0.40},
        "defense": {"defensive_play": 0.40, "goalie_save": 0.60},
        "rails": (0.94, 1.06),
        "event": "2-on-1 / 3-on-2 conversion",
        "context": ("EV",),
        "story": "numbers the other way — the goalie is on an island",
        "tags": ("odd-man", "even-strength"),
    },
    "breakaway": {
        "offense": {"skating": 0.35, "finishing": 0.45, "chance_creation": 0.20},
        "defense": {"goalie_save": 1.00},
        "rails": (0.95, 1.05),
        "event": "breakaway conversion",
        "context": ("EV", "PK"),
        "story": "in alone — daylight between him and the goalie",
        "tags": ("breakaway",),
    },
    "netfront_scramble": {
        "offense": {"finishing": 0.40, "physicality": 0.30, "puck_retrieval": 0.30},
        "defense": {"goalie_save": 0.55, "defensive_play": 0.45},
        "rails": (0.95, 1.05),
        "event": "rebound / deflection goal",
        "context": ("EV", "PP"),
        "story": "a scramble at the netfront — sticks and bodies everywhere",
        "tags": ("netfront", "rebound"),
    },
    "point_shot_traffic": {
        "offense": {"finishing": 0.60, "chance_creation": 0.40},
        "defense": {"defensive_play": 0.50, "goalie_save": 0.50},
        "rails": (0.96, 1.04),
        "event": "screened point-shot goal",
        "context": ("EV", "PP"),
        "story": "a screened bomb from the point through traffic",
        "tags": ("point-shot", "screen"),
    },
    "cycle_grind": {
        "offense": {"puck_retrieval": 0.40, "physicality": 0.35, "chance_creation": 0.25},
        "defense": {"defensive_play": 0.60, "physicality": 0.40},
        "rails": (0.93, 1.07),
        "event": "cycle-generated chance",
        "context": ("EV",),
        "story": "the cycle wears the defense down until a seam opens",
        "tags": ("cycle", "grind"),
    },
    "zone_entry": {
        "offense": {"skating": 0.45, "chance_creation": 0.35, "puck_retrieval": 0.20},
        "defense": {"defensive_play": 0.70, "physicality": 0.30},
        "rails": (0.93, 1.07),
        "event": "controlled entry success",
        "context": ("EV", "PP"),
        "story": "a controlled entry with speed — the defense is back on its heels",
        "tags": ("zone-entry", "transition"),
    },
    "board_battle": {
        "offense": {"physicality": 0.45, "puck_retrieval": 0.55},
        "defense": {"physicality": 0.45, "puck_retrieval": 0.55},
        "rails": (0.93, 1.07),
        "event": "loose-puck recovery",
        "context": ("EV", "PK"),
        "story": "a board battle — leverage and hunger decide it",
        "tags": ("boards", "battle"),
    },
    "d_to_d_onetimer": {
        "offense": {"finishing": 0.55, "chance_creation": 0.45},
        "defense": {"goalie_save": 0.65, "defensive_play": 0.35},
        "rails": (0.95, 1.05),
        "event": "one-timer conversion",
        "context": ("EV", "PP"),
        "story": "the D-to-D one-timer — the goalie is moving laterally",
        "tags": ("one-timer", "point-shot"),
    },
    # -- special teams ------------------------------------------------------
    "pp_seam_play": {
        "offense": {"chance_creation": 0.50, "finishing": 0.30, "skating": 0.20},
        "defense": {"defensive_play": 0.65, "goalie_save": 0.35},
        "rails": (0.95, 1.05),
        "event": "PP chance conversion",
        "context": ("PP",),
        "story": "the seam play — the PK is stretched past its shape",
        "tags": ("power-play", "seam"),
    },
    "pk_clear": {
        "offense": {"defensive_play": 0.60, "puck_retrieval": 0.40},
        "defense": {"physicality": 0.50, "chance_creation": 0.50},
        "rails": (0.93, 1.07),
        "event": "shorthanded clear",
        "context": ("PK",),
        "story": "the killers win the puck and send it 200 feet",
        "tags": ("penalty-kill", "clear"),
    },
    "pp_faceoff_setplay": {
        "offense": {"faceoff": 0.50, "chance_creation": 0.50},
        "defense": {"faceoff": 0.50, "defensive_play": 0.50},
        "rails": (0.93, 1.07),
        "event": "set play off a won draw",
        "context": ("PP", "EV"),
        "story": "the set play off a clean faceoff win",
        "tags": ("faceoff", "set-play"),
    },
    # -- late / close / overtime --------------------------------------------
    "late_push": {
        "offense": {"finishing": 0.35, "chance_creation": 0.35, "physicality": 0.30},
        "defense": {"defensive_play": 0.60, "goalie_save": 0.40},
        "rails": (0.94, 1.06),
        "event": "tying-chance generation",
        "context": ("late_trailing",),
        "story": "the late push — everything is going at the net",
        "tags": ("late", "tying-goal"),
    },
    "protect_lead": {
        "offense": {"defensive_play": 0.65, "physicality": 0.35},
        "defense": {"chance_creation": 0.50, "finishing": 0.50},
        "rails": (0.94, 1.06),
        "event": "tying-chance prevention",
        "context": ("late_leading",),
        "story": "protecting the lead — sticks in lanes, bodies boxed out",
        "tags": ("late", "lead-protection"),
    },
    "ot_3v3_dash": {
        "offense": {"skating": 0.45, "chance_creation": 0.30, "finishing": 0.25},
        "defense": {"defensive_play": 0.40, "goalie_save": 0.60},
        "rails": (0.94, 1.06),
        "event": "3v3 chance conversion",
        "context": ("OT",),
        "story": "3-on-3 open ice — a track meet with a goalie at each end",
        "tags": ("overtime", "3v3"),
    },
    "empty_net_gamble": {
        "offense": {"finishing": 0.40, "chance_creation": 0.35, "skating": 0.25},
        "defense": {"defensive_play": 0.70, "physicality": 0.30},
        "rails": (0.95, 1.05),
        "event": "empty-net goal",
        "context": ("empty_net",),
        "story": "the empty net — six attackers hunting the insurance marker",
        "tags": ("empty-net", "6v5"),
    },
    # -- goalie & transition -------------------------------------------------
    "goalie_puckplay": {
        "offense": {"goalie_save": 0.70, "puck_retrieval": 0.30},
        "defense": {"physicality": 0.60, "puck_retrieval": 0.40},
        "rails": (0.93, 1.07),
        "event": "goalie breakout vs turnover",
        "context": ("EV",),
        "story": "the goalie plays the puck — a breakout or a disaster",
        "tags": ("goalie", "breakout"),
    },
    "draw_penalty": {
        "offense": {"skating": 0.40, "chance_creation": 0.30, "physicality": 0.30},
        "defense": {"discipline": 1.00},
        "rails": (0.93, 1.07),
        "event": "penalty drawn",
        "context": ("EV", "PP"),
        "story": "he draws the defender into the foul — arms go up",
        "tags": ("penalty", "drawn"),
    },
}

# -- pipeline purity: enforced at import ------------------------------------
for _name, _spec in SCENARIOS.items():
    for _side in ("offense", "defense"):
        _w = _spec[_side]
        assert abs(sum(_w.values()) - 1.0) < 1e-9, f"{_name}.{_side} weights != 1.0"
        for _k in _w:
            assert _k in _KEYS, f"{_name}.{_side} member '{_k}' not a composite key"
    _lo, _hi = _spec["rails"]
    assert _lo < 1.0 < _hi, f"{_name} rails must straddle 1.0"

__all__ = [
    "SCENARIOS",
    "scenario_rating",
    "battle_amplifier",
    "apply_scenario",
    "apply_schemed_threat",
    "schemed_factor_for_shooter",
    "LiveHeat",
    "add_live_heat",
    "live_heat_value",
]


def _as_list(players):
    if players is None:
        return []
    if isinstance(players, (list, tuple)):
        return [p for p in players if p is not None]
    return [players]


def scenario_rating(players, weights, sim=None, team=None, energy=None):
    """One side's scenario rating: mean over participants of the weighted
    composite sum (with circumstance shifts). Missing side -> BASELINE."""
    plist = _as_list(players)
    if not plist or _raw is None:
        return _BASELINE
    _total = 0.0
    for p in plist:
        _s = 0.0
        for _key, _w in weights.items():
            try:
                _r = float(_raw(p, _key))
            except Exception:
                _r = _BASELINE
            if _shift is not None:
                try:
                    _r += max(-3.0, min(3.0, float(_shift(
                        p, _key, sim=sim, team=team, energy=energy) or 0.0)))
                except Exception:
                    pass
            _s += _w * _r
        _total += _s
    return _total / len(plist)


def battle_amplifier(off_rating, def_rating, rails):
    """The shared battle core: amp = 1 + R*tanh(edge / 20), hard-clamped.
    Edge 0 -> exactly 1.0 (mean-neutral)."""
    lo, hi = rails
    try:
        edge = float(off_rating) - float(def_rating)
        r = (hi - lo) / 2.0
        amp = 1.0 + r * math.tanh(edge / _SPREAD)
        return max(lo, min(hi, amp)), edge
    except Exception:
        return 1.0, 0.0


def _decisiveness(edge):
    _a = abs(edge)
    if _a >= 12.0:
        return "decisive"
    if _a >= 5.0:
        return "lean"
    return "coin flip"


def apply_scenario(prob, offense, defense, scenario, sim=None, off_team=None,
                   def_team=None, energy=None, detail=False):
    """prob *= scenario amplifier. One scenario per event per side — do not
    stack multiple scenario amplifiers on the same probability.

    detail=True returns (new_prob, info) with scenario, edge, amplifier,
    decisiveness band, story, tags, context, event for pbp/headlines.
    Bad key / None participants / bare sim -> probability undisturbed.
    """
    _spec = SCENARIOS.get(scenario)
    if _spec is None:
        return (prob, None) if detail else prob
    try:
        _off = scenario_rating(offense, _spec["offense"], sim=sim,
                               team=off_team, energy=energy)
        _def = scenario_rating(defense, _spec["defense"], sim=sim,
                               team=def_team, energy=energy)
        _amp, _edge = battle_amplifier(_off, _def, _spec["rails"])
        _new = prob * _amp
        if not detail:
            return _new
        return _new, {
            "scenario": scenario,
            "edge": round(_edge, 2),
            "amplifier": round(_amp, 4),
            "decisiveness": _decisiveness(_edge),
            "story": _spec["story"],
            "tags": _spec["tags"],
            "context": _spec["context"],
            "event": _spec["event"],
        }
    except Exception:
        return (prob, None) if detail else prob


# ---------------------------------------------------------------------------
# Schemed-against superstars, expressed AS a scenario battle.
# Offense-threat composites (the star's) vs the defending TEAM's collective
# defensive commitment — the same battle core as every scenario above.
#
# The scouting report, not a coefficient. When a generational talent hops
# the boards, the defending TEAM tilts the ice: the weak-side winger sags
# into his wheelhouse, the D pair plays the pass instead of the man, the
# second layer takes away the give-and-go. One defender never stops
# McDavid — he walks one defender — so the denial is computed from the
# whole defending unit's collective defensive quality, never one matchup.
# That is also what makes the zero-sum honest: the attention visibly
# reallocated to the star is exactly what leaves his linemates a half-step
# cleaner. League totals stay stable while the tail compresses.
#
# Elite/generational ONLY. The threat curve is ~zero below the elite tier
# and ramps at the very top — an average top-six forward feels nothing.
# Grade-A CREATION (contest), never finishing.
#
# The McDavid principle (hard floor): this shaves the margin, it never
# flattens the star into the pack and never inverts the talent hierarchy.
# Spontaneity kept: no caps anywhere on the outcome — a perfect
# generational season can still spike.
# ---------------------------------------------------------------------------
_SCHEME_THREAT_FLOOR = 90.0   # overall below this: zero threat, nothing felt
_SCHEME_THREAT_RAMP = 7.0     # 90 -> 0.0 threat, 97 -> 1.0 threat
_SCHEME_RAILS = (0.82, 1.00)  # star suppression: bounded shave, never a wall
_SCHEME_RELIEF_RAILS = (1.00, 1.10)  # linemate dividend rails
_SCHEME_OFF_WHEELHOUSE = 0.45  # denial outside his preferred zones — the
                               # scheme takes away his SPOTS; he can shoot
                               # from anywhere, but the shading lives where
                               # he lives.

# Location vocabulary normalization (2026-09-30, (c) parity fix): GameSim
# passes raw ShotLocation enum names ("high_slot", "left_circle", ...),
# quick-sim passes grade-location strings ("slot", "netfront", ...).
# The wheelhouse sets below use the GRADE vocabulary. Normalize once,
# here, at the shared layer — both engines then shade the same spots,
# and the denial bites identically watched vs quick. Mirrors
# GameSim._GRADE_LOCATION_MAP (simulation.py); unknown strings pass
# through unchanged (off-wheelhouse fraction, as before).
_SCHEME_LOCATION_ALIASES = {
    "crease": "crease",
    "low_slot": "slot", "high_slot": "slot",
    "left_circle": "slot", "right_circle": "slot",
    "point": "point",
    "left_wing": "perimeter", "right_wing": "perimeter",
    "behind_net": "perimeter",
    "slot": "slot", "netfront": "netfront", "perimeter": "perimeter",
    "breakaway": "breakaway",
}


def _scheme_norm_location(location):
    try:
        _l = str(location or "").lower()
    except Exception:
        _l = ""
    return _SCHEME_LOCATION_ALIASES.get(_l, _l)


# Wheelhouse zones per role: where the scheme shades. Denial concentrates
# here; everywhere else he sees a fraction of it.
_SCHEME_WHEELHOUSE = {
    "Sniper": {"slot", "netfront", "crease"},
    "Playmaker": {"slot", "perimeter"},
    "Power Forward": {"netfront", "crease", "slot"},
    "Grinder": {"netfront", "crease"},
    "Enforcer": {"crease"},
    "Two-Way Forward": {"slot", "netfront"},
    "Offensive Defenseman": {"point", "slot"},
    "Defensive Defenseman": {"point"},
    "Two-Way Defenseman": {"point", "slot"},
}

# Offense-threat composite weights for the threat rating: what makes a
# superstar's looks dangerous, as composites (pipeline purity).
_SCHEME_THREAT_WEIGHTS = {
    "finishing": 0.40,
    "chance_creation": 0.35,
    "skating": 0.25,
}


def _scheme_team_commitment(defending_onice, sim=None, team=None):
    """The defending TEAM's collective defensive commitment. The D pair
    carries the scheme (weight 1.0); forwards sink as support layers
    (weight 0.5). A great scheme run by bad defenders is just standing
    around — execution quality belongs to the team, not one man."""
    _plist = _as_list(defending_onice)
    if not _plist:
        return _BASELINE
    _num, _den = 0.0, 0.0
    for p in _plist:
        try:
            _pos = getattr(p, "primary_position", None)
            _pname = getattr(_pos, "name", "") or str(_pos)
            _is_d = "DEFENSE" in _pname
        except Exception:
            _is_d = False
        _q = scenario_rating(p, {"defensive_play": 1.0}, sim=sim, team=team)
        _w = 1.0 if _is_d else 0.5
        _num += _q * _w
        _den += _w
    return _num / _den if _den > 0 else _BASELINE


def apply_schemed_threat(shooter, attacking_onice, defending_onice,
                         location, sim=None, off_team=None, def_team=None):
    """The schemed-against battle. Returns (star_factor, relief_factor):
    - star_factor (<= 1.0): multiplies the star's grade-A creation chance.
    - relief_factor (>= 1.0): the UNIT-WIDE relief budget funded by the
      attention the star draws (1.0 + budget). It is NOT applied flat to
      every linemate — schemed_factor_for_shooter apportions it across the
      unit through line_chemistry.chemistry_relief_share (fit-weighted),
      so the total dividend never exceeds the budget.

    For non-elite shooters both are exactly 1.0 (feels nothing). Bounded
    rails, mean-neutral at even threat, no finishing touch. Callers apply
    star_factor to the star's chance; the relief budget is apportioned
    per-shooter by schemed_factor_for_shooter.

    Battle structure: the scheme's execution (team commitment vs league
    baseline, through the shared battle core) scaled by the elite threat
    gate and the wheelhouse weight. This is not a talent-vs-talent battle
    — a scheme doesn't need better players than McDavid to take away his
    spots; it needs commitment and execution. The threat gate decides HOW
    MUCH attention he draws; the commitment battle decides how well the
    team converts that attention into denial.
    """
    try:
        # Granular (Muck 2026-10-01: schemed-against is 90+). The gate reads
        # the TRUE 1-point overall, not the tier proxy — the tier proxy
        # mapped Elite (88-91) to rep 90, which sat exactly on the
        # floor (90.0) and gated to 0.0, silently disabling scheming
        # for 90-91 players and hard-cliffing at 91.9->92.0.
        try:
            _ovr = float(shooter.overall_rating())
            except Exception:
                return 1.0, 1.0
        if _ovr < _SCHEME_THREAT_FLOOR:
            return 1.0, 1.0
        _gate = min(1.0, (_ovr - _SCHEME_THREAT_FLOOR) / _SCHEME_THREAT_RAMP)
        # The star's denial battle. The denial FOLLOWS THE STAR
        # (Muck 2026-09-30): the coach puts his best shutdown pair on him,
        # so the commitment is anchored on the top D pair (pair 0), with
        # the on-ice unit's support blended in.
        try:
            _q1 = _d_pair_quality(defending_onice, sim=sim, team=def_team,
                                  pair=0)
        except Exception:
            _q1 = _BASELINE
        _commit = (0.70 * _q1
                   + 0.30 * _scheme_team_commitment(defending_onice, sim=sim,
                                                    team=def_team))
        # Wheelhouse: the scheme shades his spots. Off-wheelhouse, only a
        # fraction of the commitment actually finds him.
        try:
            _role = shooter.get_role()
            _rname = getattr(_role, "value", "") or str(_role)
        except Exception:
            _rname = ""
        _loc = _scheme_norm_location(location)
        _in_wheel = _loc in _SCHEME_WHEELHOUSE.get(_rname, set())
        _wheel = 1.0 if _in_wheel else _SCHEME_OFF_WHEELHOUSE
        # The battle: team commitment vs league baseline, through the
        # shared core. A well-drilled unit wins this; an average one ties.
        _commit_amp, _ = battle_amplifier(_commit, _BASELINE, (0.85, 1.15))
        _scheme_effect = max(0.0, _commit_amp - 1.0)
        # Scale to a max ~0.006 suppression at full gate, wheelhouse,
        # elite commitment — a shave, not a wall. (The McDavid floor is a
        # hard constraint: in-scenario, 97-ovr beats 88-ovr by only ~0.8%,
        # so the shave must stay below that or the hierarchy inverts at
        # the battle level. Season-level, the generational talent's volume
        # advantage keeps him ahead by daylight.)
        _suppression = _gate * _wheel * _scheme_effect * 0.044
        _star = max(_SCHEME_RAILS[0], 1.0 - _suppression)
        # Zero-sum relief: the attention reallocated to the star is what
        # frees his linemates. Scales with the suppression actually felt.
        _relief = 1.0 + min(0.10, (1.0 - _star) * 0.55)
        _relief = max(_SCHEME_RELIEF_RAILS[0],
                      min(_SCHEME_RELIEF_RAILS[1], _relief))
        return _star, _relief
    except Exception:
        return 1.0, 1.0


def schemed_factor_for_shooter(shooter, attacking_onice, defending_onice,
                               location, sim=None, off_team=None,
                               def_team=None):
    """Single factor to multiply one shooter's grade-A chance. If the
    shooter is elite, the star suppression; if he's a linemate of an
    elite, his matchup-ladder relief (one rung down, IQ-gated);
    otherwise exactly 1.0. This is the call-site helper — one factor per
    chance, never stacked.

    Matchup ladder (Muck 2026-09-30): the star draws the BEST defensive
    matchup -- it does NOT leave his linemate wide open. The linemate's
    matchup improves by exactly ONE RUNG, and how much he converts it
    scales with HIS OWN hockey IQ / awareness / finishing. Archetype
    complementarity weights who gets the freed looks through
    line_chemistry.chemistry_relief_share (the Raffl fix). Defensive
    import — if line_chemistry is unavailable, falls back to an even
    split."""
    try:
        _unit = _as_list(attacking_onice)
        _star, _ = apply_schemed_threat(shooter, attacking_onice,
                                        defending_onice, location,
                                        sim=sim, off_team=off_team,
                                        def_team=def_team)
        if _star < 1.0:
            return _star
        # Not the star — find the elite linemate drawing the shade.
        _best_star = None
        _best_suppression = 0.0
        for _p in _unit:
            if _p is None or _p is shooter:
                continue
            # Tier-based (Muck 2026-10-01): the 90 floor reads the tier
            # representative, not the 1-point overall.
            try:
                from attribute_composites import tier_proxy_overall \
                    as _tpo_lm
                _lm_ovr = float(_tpo_lm(float(_p.overall_rating())))
            except Exception:
                try:
                    _lm_ovr = float(_p.overall_rating())
                except Exception:
                    continue
            try:
                if _lm_ovr < _SCHEME_THREAT_FLOOR:
                    continue
            except Exception:
                continue
            _s, _ = apply_schemed_threat(_p, attacking_onice,
                                         defending_onice, location,
                                         sim=sim, off_team=off_team,
                                         def_team=def_team)
            _supp = 1.0 - _s
            if _supp > _best_suppression:
                _best_suppression = _supp
                _best_star = _p
        if _best_star is None or _best_suppression <= 0.0:
            return 1.0
        # Matchup ladder (Muck 2026-09-30): the star draws the BEST
        # defensive matchup -- it does NOT leave his linemate wide open.
        # The linemate's matchup improves by exactly ONE RUNG (2nd pair
        # instead of 1st), a modest help, and how much of it he converts
        # scales with HIS OWN hockey IQ / awareness / finishing -- "it
        # just helps their looks if they know what they're doing." A
        # low-awareness plug converts almost nothing; a smart finisher
        # converts most of it.
        try:
            _q1 = _d_pair_quality(defending_onice, sim=sim, team=def_team,
                                  pair=0)
            _q2 = _d_pair_quality(defending_onice, sim=sim, team=def_team,
                                  pair=1)
        except Exception:
            _q1, _q2 = _BASELINE, _BASELINE
        _rung_delta = max(0.0, _q1 - _q2)
        # The freed half-step: the rung gap, scaled by the suppression
        # actually felt (no shade, no freed ice). Smooth, tiny, additive.
        _relief_pool = ((_rung_delta / 100.0) * 0.60
                        * min(1.0, _best_suppression / 0.05))
        # Who converts it: archetype fit with the star (kept: the Raffl
        # fix -- fit-weighted, never flat) TIMES his own IQ/awareness/
        # finishing gate.
        try:
            from line_chemistry import chemistry_relief_share as _crs
            _share = _crs(shooter, _best_star, _unit)
        except Exception:
            _n = max(1, len([p for p in _unit if p is not None]) - 1)
            _share = 1.0 / _n
        _iq = _linemate_iq_gate(shooter)
        return 1.0 + _relief_pool * max(0.0, min(1.0, _share)) * _iq
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Stacked-amplifier combining + matchup ladder + talent gates
# (2026-09-30, workstream C stacking audit, Muck).
#
# C1 combining rule: opportunity AMPLIFIERS combine sub-multiplicatively
# (strongest-wins + allowance). Suppressors / denials keep multiplying
# fully -- they are honest brakes, never muted.
# ---------------------------------------------------------------------------

_STACK_ALLOWANCE = 0.30


def combine_stacked_amplifiers(*factors, allowance=_STACK_ALLOWANCE):
    """Combine opportunity amplifiers sub-multiplicatively.

    Rule: the strongest BOOST keeps its full value; every further
    boost contributes only `allowance` (default 0.30) of its excess.
    Denials (<1) are NOT softened -- they multiply at full power, exactly
    as before: suppressors are honest brakes, never muted. Boosts and
    denials combine independently inside their own direction; the two
    directions then multiply normally.

    Properties:
      - single factor      -> identity (no behavior change alone),
      - smooth, unbounded  -> no caps, no ceilings, no cliffs,
      - denials untouched   -> multiplicative, full power.

    Examples:
      combine(1.75)            == 1.75
      combine(1.75, 1.14)      == 1.75 * 1.14**0.30  ~= 1.820  (free: 1.995)
      combine(1.75, 1.14, 1.05)
                               == 1.75 * 1.14**0.30 * 1.05**0.30 ~= 1.847
                                  (free multiplicative: 2.095)
      combine(0.90, 0.65)      == 0.585  (denials: full multiplicative)
      combine(1.75, 1.14, 0.65)
                               == 1.820 * 0.65      ~= 1.183
    """
    try:
        _ups = []
        _downs = []
        for _f in factors:
            try:
                _f = float(_f)
            except (TypeError, ValueError):
                continue
            if _f <= 0.0:
                continue
            if _f > 1.0:
                _ups.append(_f)
            elif _f < 1.0:
                _downs.append(_f)
        _out = 1.0
        if _ups:
            _ups.sort(reverse=True)
            _out *= _ups[0]
            for _f in _ups[1:]:
                _out *= _f ** allowance
        if _downs:
            for _f in _downs:
                _out *= _f
        return _out
    except Exception:
        return 1.0


# Matchup-ladder internals -------------------------------------------------
#
# Muck's design directive (2026-09-30): a schemed-against superstar draws
# the BEST defensive matchup -- the denial follows the star. His linemate's
# matchup improves by exactly ONE rung (2nd pair instead of 1st), a modest
# help, and how much of it he converts scales with his OWN hockey IQ /
# awareness / finishing -- "it just helps their looks if they know what
# they're doing." This structurally kills the cartoon-linemate failure
# (no more 75-ovr 138-point seasons off the star's gravity).

def _resolve_team_obj(sim, team):
    """Resolve a team object from a name/string via the sim's league."""
    try:
        if team is not None and not isinstance(team, str):
            return team
        if sim is None or team is None:
            return None
        _lg = getattr(sim, "league", None)
        if _lg is None:
            return None
        for _t in getattr(_lg, "teams", []) or []:
            if getattr(_t, "team_name", None) == team:
                return _t
    except Exception:
        pass
    return None


def _d_pair_quality(defending_onice, sim=None, team=None, pair=0):
    """Defensive quality of the defending team's D pair `pair`.

    pair=0 is the top shutdown pair (the unit the scheme puts on the
    star); pair=1 is the next pair down -- one rung lower on the ladder.
    Resolved from the team's D corps (defensive_play composite); cached
    per game. Falls back to the on-ice pair (which, by scheme design, is
    the shutdown pair) plus a rung down.
    """
    try:
        _cache = getattr(sim, "_scheme_rung_cache", None) if sim else None
        if _cache is None and sim is not None:
            _cache = {}
            try:
                sim._scheme_rung_cache = _cache
            except Exception:
                pass
        _team_obj = _resolve_team_obj(sim, team)
        _key = (getattr(_team_obj, "team_name", None) or str(team), pair)
        if isinstance(_cache, dict) and _key in _cache:
            return _cache[_key]
        _q = None
        if _team_obj is not None:
            _dmen = [p for p in getattr(_team_obj, "roster", []) or []
                     if str(getattr(getattr(p, "primary_position", None),
                                    "name", "")).upper()
                     in ("DEFENSE", "LEFT_DEFENSE", "RIGHT_DEFENSE", "D",
                         "LD", "RD")]
            _dmen.sort(key=lambda p: scenario_rating(p, {"defensive_play": 1.0}),
                       reverse=True)
            _seg = _dmen[pair * 2:pair * 2 + 2]
            if len(_seg) == 2:
                _q = sum(scenario_rating(p, {"defensive_play": 1.0})
                         for p in _seg) / 2.0
        if _q is None:
            # Fallback: the on-ice D IS the shutdown pair by scheme design.
            _onice_d = [p for p in _as_list(defending_onice)
                        if str(getattr(getattr(p, "primary_position", None),
                                       "name", "")).upper()
                        in ("DEFENSE", "LEFT_DEFENSE", "RIGHT_DEFENSE",
                            "D", "LD", "RD")]
            if _onice_d:
                _q1 = sum(scenario_rating(p, {"defensive_play": 1.0})
                          for p in _onice_d) / len(_onice_d)
                _q = _q1 if pair == 0 else (_BASELINE + (_q1 - _BASELINE) * 0.55)
            else:
                _q = _BASELINE
        if isinstance(_cache, dict):
            _cache[_key] = _q
        return _q
    except Exception:
        return _BASELINE


def _linemate_iq_gate(shooter):
    """0..1: how much of the freed half-step THIS shooter converts.

    HIS OWN hockey IQ / awareness / finishing. An aware 82-ovr converts
    most of it; a 75-ovr with poor awareness converts almost nothing --
    the help only lands on looks he can actually finish.
    """
    try:
        _iq = (float(getattr(shooter, "hockey_iq", 70)) * 0.40
               + float(getattr(shooter, "offensive_awareness", 70)) * 0.35
               + float(_raw(shooter, "finishing")) * 0.25)
    except Exception:
        _iq = 70.0
    return max(0.0, min(1.0, (_iq - 55.0) / 35.0))


def point_shot_talent_gate(shooter):
    """0.85..1.0: a defenseman's point-shot value scales with HIS OWN
    shooting tools and hockey IQ. Elite point shooters ~1.0; mediocre
    shooters ~0.85. Smooth, never a wall -- play design feeds the looks,
    talent decides what they become."""
    try:
        _tool = (float(getattr(shooter, "slapshot", 70)) * 0.45
                 + float(getattr(shooter, "one_timer", 70)) * 0.30
                 + float(getattr(shooter, "hockey_iq", 70)) * 0.25)
    except Exception:
        _tool = 70.0
    return 0.85 + 0.15 * max(0.0, min(1.0, (_tool - 60.0) / 30.0))


def onetimer_talent_gate(shooter):
    """0..1: who EARNS the one-timer spotlight volume. Elite trigger +
    awareness + finishing ~1.0; average ~0.4; below-average ~0.15. The
    design can feed looks, but the looks concentrate on the shooters."""
    try:
        _t = (float(getattr(shooter, "one_timer", 60)) * 0.50
              + float(getattr(shooter, "offensive_awareness", 60)) * 0.25
              + float(_raw(shooter, "finishing")) * 0.25)
    except Exception:
        _t = 60.0
    return max(0.0, min(1.0, (_t - 55.0) / 35.0))


# One-timer archetype factor (2026-09-30, workstream C2, Muck): the talent
# gate above measures the TOOL; this measures the ROLE. The EV one-timer is
# a sniper's signature -- snipers and playmakers live in the one-timer
# spot, power forwards flash it, two-way/grinder/enforcer types get their
# offense other ways. Without this, the attribute-only gate passes
# high-awareness role players (two-way forwards dominate the population)
# and enforcers wire 20+ one-timers a sample. PP one-timer rate is the
# tuning crew's lane -- untouched. D keep 1.0 (their EV one-timer resolves
# through the d_to_d_onetimer scenario, not this gate).
_ONETIMER_ARCHETYPE_FACTOR = {
    "Sniper": 1.0,
    "Playmaker": 0.9,
    "Power Forward": 0.85,
    "Two-Way Forward": 0.6,
    "Grinder": 0.4,
    "Enforcer": 0.3,
}


def onetimer_archetype_factor(shooter):
    """0.3..1.0: role-based share of EV one-timer volume. Sniper 1.0;
    unlisted/unknown forward archetypes 0.75; D 1.0. Never raises volume,
    only concentrates it on the shooters.

    Elite tool overrides role: a 90+ one-timer wires it like a sniper
    wherever it lives -- a generational two-way with a 95 trigger is a
    one-timer threat, not a role player (the archetype classifier labels
    flat-elite players "Two-Way Forward" on their defensive half). Smooth
    ramp 80->90, no cliff."""
    try:
        _pos = str(getattr(getattr(shooter, "primary_position", None),
                           "name", "")).upper()
        if "DEFEN" in _pos:
            return 1.0
        try:
            from player_archetypes import get_archetype as _ga
            _arch = _ga(shooter)
        except Exception:
            _arch = None
        if _arch in _ONETIMER_ARCHETYPE_FACTOR:
            _base = _ONETIMER_ARCHETYPE_FACTOR[_arch]
        else:
            _base = 0.75
        try:
            _ot = float(getattr(shooter, "one_timer", 70))
        except Exception:
            _ot = 70.0
        if _ot >= 90.0:
            return 1.0
        if _ot > 80.0:
            _ramp = (_ot - 80.0) / 10.0
            return _base + (1.0 - _base) * _ramp
        return _base
    except Exception:
        return 0.75


# ---------------------------------------------------------------------------
# LiveHeat — the shared bounded in-game heat accumulator (§5.2, option a).
# Both engines update the same object semantics: fights +6, majors +4,
# brawls +10, hard cap 40. Heat must mean the same thing watched vs quick —
# a game that boils over feels alive in both modes.
# ---------------------------------------------------------------------------
_LIVE_HEAT_CAP = 40.0
_HEAT_FIGHT = 6.0
_HEAT_MAJOR = 4.0
_HEAT_BRAWL = 10.0


class LiveHeat:
    """Bounded heat accumulator. One per game, owned by the sim."""

    def __init__(self):
        self.value = 0.0

    def add(self, amount):
        try:
            self.value = max(0.0, min(_LIVE_HEAT_CAP,
                                      self.value + float(amount or 0.0)))
        except Exception:
            pass
        return self.value

    def fight(self):
        return self.add(_HEAT_FIGHT)

    def major(self):
        return self.add(_HEAT_MAJOR)

    def brawl(self):
        return self.add(_HEAT_BRAWL)


def add_live_heat(sim, amount):
    """Shared update helper: both engines call this (or the LiveHeat
    methods) so heat accumulates identically. Falls back to the legacy
    _live_heat float when no accumulator is attached."""
    try:
        _acc = getattr(sim, "_heat_acc", None)
        if _acc is not None:
            return _acc.add(amount)
        _v = max(0.0, min(_LIVE_HEAT_CAP,
                          float(getattr(sim, "_live_heat", 0.0) or 0.0)
                          + float(amount or 0.0)))
        sim._live_heat = _v
        return _v
    except Exception:
        return 0.0


def live_heat_value(sim):
    """Read heat for circumstance_shift's fallback (0-100 scale there)."""
    try:
        _acc = getattr(sim, "_heat_acc", None)
        if _acc is not None:
            return float(_acc.value)
        return float(getattr(sim, "_live_heat", 0.0) or 0.0)
    except Exception:
        return 0.0
