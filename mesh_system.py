# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Perfect-mesh system: non-talent scoring texture.

Talent stays primary -- this module never touches attribute scales or talent
multipliers. Instead it reads situational alignment and pays a super-additive
kicker when the non-talent factors line up ("perfect mesh"):

  - chemistry with linemates
  - fit with the team's tactical system (grows with familiarity: the
    "finding his wings" arc emerges, it is not scripted)
  - morale
  - form (hot/cold)

The kicker tilts toward lower-talent players (bounded: rank order never flips),
so depth guys get their night. Players with playoff-elevator traits wake up in
April. Chance generation gets about half the conversion effect, so a guy's
night can be two primary assists, not just a hat trick.

The mesh both reads form and writes it: a mesh-driven big night moves a depth
player's form needle more than a star's, hot form feeds the next game's mesh,
and a real heater from a developing player can probabilistically tip into a
breakout (coach trust / steadier role). Nothing is guaranteed -- every night is
still a roll, and jumbling his linemates kills it cold.

Additive by design: engines call mesh_factor()/mesh_chance_factor() alongside
their existing math and multiply the result in. Removing this module reverts to
the old behavior.
"""

import math
import random
from typing import NamedTuple

MESH_VERSION = 1

# ---------------------------------------------------------------------------
# Tuning. All magnitudes modest; the per-factor pulls are small and the story
# lives in the alignment kicker, not in any single input.
# ---------------------------------------------------------------------------
_PER_FACTOR_WEIGHT = 0.03    # each factor's pull on the base multiplier
_ALIGN_THRESHOLD = 0.70      # a factor counts as "aligned" above this
_KICKER_BASE = 0.02          # kicker floor when 3+ factors align
_KICKER_PER_ALIGNED = 0.025  # extra per aligned factor beyond 3
_UNDERDOG_TILT = 0.6         # kicker scales up as talent drops (bounded)
_PLAYOFF_ELEVATOR = 0.04     # clutch/big-game trait bonus, playoffs only
_MIN_FACTOR = 0.90
_MAX_FACTOR = 1.22
_CHANCE_COUPLING = 0.5       # chance-gen gets half the conversion effect

# Form / streak / breakout.
_FORM_DECAY = 0.88           # form retained per game played
_FORM_LEARN = 0.30           # how much a surprising night moves the needle
_STREAK_GATE = 0.55          # mesh_form above this counts toward a breakout
_BREAKOUT_GAMES = 5          # consecutive gated games to qualify
_BREAKOUT_CHANCE = 0.35      # probabilistic: heaters don't always become arcs
_BREAKOUT_MORALE_BUMP = 8    # coach trust made tangible (morale floor lift)

# Skill-differential baseline for the AdvancedGameSim recalibration.
# The shot formula was designed for a 1-20 attribute scale ("Elite 18 vs weak
# 8") but both skills resolve on the 1-100 scale, with goalies systematically
# ~15 points above shooters. Recentering restores the designed 9% base for an
# average shot. Measured 2026-09-27 across generated league talent; re-measured
# 2026-09-28 in live games (s2_deadline save, n=834 shots): the in-game
# adjusted differential averages -26.7 (starters + danger/shot-type
# adjustments), not -14.8. Re-measure if rosters or adjustments change.
SKILL_DIFF_BASELINE = -26.7
SHOT_BASE_CHANCE = 0.12
# Talent sensitivity: piecewise -- flat middle, gentle top (parity retune
# 2026-09-28, per Muck: "flat league, fat tails"). The middle of the league
# converts on a gentle slope (SENS_MID) so depth and systems contend; above
# the mean differential a slightly steeper slope (SENS_TOP) preserves a hint
# of superstar separation, and the 0.16 conversion clamp keeps genuine
# 50-goal headroom -- the cap, not the slope, is the cream-rises mechanism.
# Mean-preserving by construction: the baseline sits exactly on the measured
# mean differential (n=834 shots), so the average shot converts at
# SHOT_BASE_CHANCE either way.
# (Old code was 0.008 linear on a miscalibrated -14.8 baseline: accidentally
# flat/fat-tailed, but at 2.20 GPG -- below the band. This keeps that shape
# at an in-band level. Step-5: 0.003/0.004 -- the step-3/4 passes (0.004 /
# 0.006-0.008) still left the best teams at 78-80% and the Art Ross at
# 114-137; the 0.16 clamp preserves genuine 50-goal headroom at the top.)
SHOT_TALENT_SENS_MID = 0.003
SHOT_TALENT_SENS_TOP = 0.006
# Back-compat alias for single-sensitivity import sites.
SHOT_SKILL_SENSITIVITY = SHOT_TALENT_SENS_MID


def _talent_sens(centered_diff: float) -> float:
    """Piecewise slope: gentle through the middle, old steepness at the top."""
    return SHOT_TALENT_SENS_TOP if centered_diff >= 0 else SHOT_TALENT_SENS_MID


# Goaltending parity (parity retune 2026-09-28, step 6). The starter goalie
# ratings run 76.7-98.1 (mean 92.6, n=32) -- a 21-point gap deciding games
# outright (Edmonton 85% on a 97 goalie). Compress the effective goalie
# skill toward the MEASURED mean so the gap halves; the best goalies still
# stand out, just not by 10 points of every skill differential. Mean-
# preserving by construction (92.6 measured 2026-09-28; re-measure if
# rosters change). Applied in the conversion formula only -- the raw
# composite is untouched for UI/AI.
GOALIE_PARITY_MEAN = 92.6
GOALIE_PARITY_K = 0.5


def effective_goalie_skill(goalie_skill: float) -> float:
    """Parity-compressed goalie skill for the shot-conversion formula."""
    try:
        return GOALIE_PARITY_MEAN + (float(goalie_skill) - GOALIE_PARITY_MEAN) * GOALIE_PARITY_K
    except Exception:
        return GOALIE_PARITY_MEAN


# Defenseman point-shot conversion discount (superstar tune 2026-09-28).
# Real NHL: D take ~1/3 of shots but score only ~20% of goals -- a point
# slapshot through traffic converts at roughly half the rate of a forward's
# slot wrister at equal skill. The sim had no distance discount: D point
# shots ran through the same ~9%-base conversion as forwards, so D led the
# league in goals. This is the shared decision (one decision, two
# fidelities) -- both engines multiply it into the conversion formula.
# Forwards return 1.0. Never raises.
# Retune 2026-09-28: 0.20 -> 0.24. Measured D share 14.3% (target ~20-22%);
# the discount was overcorrecting. Combined with the volume bump below,
# targets ~20% D goals while keeping 0 D in the top-10.
# Retune 2026-09-29 (acceptance): 0.24 -> 0.45 -> 0.55 -> 0.65. With the
# chance-grade system live, D point shots grade out B/C (low conversion)
# AND take the discount -- double-penalized to 12.2% share. Real NHL: D
# take ~1/3 of shots at ~0.5x forward conversion -> ~20% of goals.
DEFENSE_POINT_SHOT_DISCOUNT = 0.65


def defense_point_shot_discount(shooter) -> float:
    """Conversion multiplier for defenseman point shots. 1.0 for forwards."""
    try:
        from game_classes import PlayerPosition
        _pos = getattr(shooter, "primary_position", None)
        if _pos in (PlayerPosition.DEFENSE, PlayerPosition.LEFT_DEFENSE,
                    PlayerPosition.RIGHT_DEFENSE):
            return DEFENSE_POINT_SHOT_DISCOUNT
    except Exception:
        pass
    return 1.0


# Sniper archetype finishing tilt (superstar tune 2026-09-28, per Muck).
# Within elite-forward scoring, pure snipers get a modest edge over other
# forward archetypes -- 5-10% range, not a transformation. A 95-ovr sniper
# hits ~50; a 95-ovr playmaker still scores ~35-45 but makes his money on
# assists. Shared decision (one decision, two fidelities). Never raises.
ARCHETYPE_FINISH_TILT = {
    "Sniper": 1.08,
    "Power Forward": 1.03,
    "Playmaker": 0.97,
    "Two-Way Forward": 1.00,
}


def archetype_finish_tilt(shooter) -> float:
    """Small finishing multiplier by forward archetype. 1.0 default."""
    try:
        from player_archetypes import get_archetype
        return float(ARCHETYPE_FINISH_TILT.get(get_archetype(shooter), 1.0))
    except Exception:
        return 1.0


def _clamp01(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.5
    if x != x:  # NaN
        return 0.5
    return max(0.0, min(1.0, x))


def talent_norm(player) -> float:
    """Player talent on 0..1. Talent stays primary: the mesh never changes
    this, it only tilts the kicker around it."""
    try:
        r = float(player.overall_rating())
    except Exception:
        return 0.6
    if r > 1.5:  # 1-100 scale
        r /= 100.0
    return _clamp01(r)


def chemistry_input(shooter, linemates) -> float:
    """0..1 line-chemistry read. Defensive: unknown scales get squashed."""
    players = [p for p in [shooter] + list(linemates or []) if p]
    if len(players) < 2:
        return 0.5
    try:
        from player_archetypes import line_chemistry_score
        delta = float(line_chemistry_score(players))
    except Exception:
        # Fall back to the stored per-player value (10-20 default scale).
        try:
            vals = [float(getattr(p, "line_chemistry", 15)) for p in players]
            avg = sum(vals) / len(vals)
            return _clamp01(avg / 100.0 * 2.5)  # 20 -> 0.5 neutral
        except Exception:
            return 0.5
    # delta is centered near 0; squash to 0..1 around neutral 0.5.
    return _clamp01(0.5 + delta / 200.0)


def system_fit_input(team) -> float:
    """0..1 tactical system fit. Familiarity growth makes this the slow-burn
    input behind the 'finally finding his wings' arc."""
    try:
        from tactics import resolve_team_tactics
        resolved = resolve_team_tactics(team)
        fit = float(resolved.get("fit", 0.5))
        fam = float(resolved.get("familiarity", 85))
    except Exception:
        return 0.5
    # Fit is the structural piece; familiarity (grows through the season)
    # nudges it. Both 0..1-ish; clamp defensively.
    fit_n = _clamp01(fit)
    fam_n = _clamp01(fam / 100.0)
    return _clamp01(0.7 * fit_n + 0.3 * (0.5 + 0.5 * fam_n))


def morale_input(player) -> float:
    try:
        return _clamp01(float(getattr(player, "morale", 70)) / 100.0)
    except Exception:
        return 0.5


def form_input(player) -> float:
    """Mesh-tracked form (-1 cold .. 1 hot) mapped to 0..1."""
    try:
        f = float(getattr(player, "mesh_form", 0.0))
    except Exception:
        f = 0.0
    return _clamp01(0.5 + 0.5 * max(-1.0, min(1.0, f)))


def _factor_values(shooter, linemates, team):
    return [
        chemistry_input(shooter, linemates),
        system_fit_input(team),
        morale_input(shooter),
        form_input(shooter),
    ]


def has_playoff_elevator(player) -> bool:
    try:
        traits = getattr(player, "traits", []) or []
    except Exception:
        return False
    return "clutch" in traits or "big_game_goalie" in traits


def mesh_factor(shooter, linemates, team, is_playoff=False) -> float:
    """Conversion multiplier for a shooter's chance (shot_chance / xG).

    Modest per-factor pulls; the story is the super-additive alignment kicker
    with an underdog tilt. Talent rank order is never flipped: the kicker is
    bounded and talent itself is untouched.
    """
    values = _factor_values(shooter, linemates, team)

    # Base: small pull from each factor's distance from neutral.
    base = 1.0 + _PER_FACTOR_WEIGHT * sum(v - 0.5 for v in values)

    # Alignment kicker: when 3+ factors line up, the whole exceeds the parts.
    aligned = sum(1 for v in values if v >= _ALIGN_THRESHOLD)
    kicker = 0.0
    if aligned >= 3:
        kicker = _KICKER_BASE + _KICKER_PER_ALIGNED * (aligned - 3)
        if aligned >= 4:
            kicker *= 1.5  # perfect mesh: super-additive
        # Underdog tilt: depth players feel the kicker more. Bounded so a
        # grinder's great night never outranks a star's talent.
        tilt = 1.0 + (1.0 - talent_norm(shooter)) * _UNDERDOG_TILT
        kicker *= tilt

    # Playoff magic: elevator traits wake up in April.
    if is_playoff and has_playoff_elevator(shooter):
        kicker += _PLAYOFF_ELEVATOR

    return max(_MIN_FACTOR, min(_MAX_FACTOR, base + kicker))


def mesh_chance_factor(shooter, linemates, team, is_playoff=False) -> float:
    """Lighter coupling for chance generation (event odds, cycle chances).

    A guy doesn't need a hat trick to have his night -- the mesh also creates
    the extra pass, the extra look, the assist that wins the game.
    """
    f = mesh_factor(shooter, linemates, team, is_playoff)
    return max(0.94, min(1.12, 1.0 + _CHANCE_COUPLING * (f - 1.0)))


def recalibrated_shot_chance(skill_diff: float) -> float:
    """The AdvancedGameSim base, recentered so the average shot resolves at
    the designed 9%. Piecewise slope (flat middle, convex top) -- see the
    sensitivity notes above. Restores intent; changes no attribute.
    """
    _d = skill_diff - SKILL_DIFF_BASELINE
    return SHOT_BASE_CHANCE + _d * _talent_sens(_d)


def shooter_finish_mult(shooter_skill: float, mean_skill: float = 65.4) -> float:
    """Multiplicative finishing factor (GameSim fidelity): 1.0 at
    league-average skill, piecewise slope (flat middle, convex top) -- the
    same talent decision quick-sim's additive model makes above. Clamped
    0.80-1.25. Never raises.

    (2026-10-01: re-measured on the new finishing_rating blend --
    mean 65.4, n=600 generated skaters, sd 2.8. The old blend measured
    65.3, so the anchor is effectively unchanged; the constant is updated
    so the comment stays truthful.)
    """
    try:
        _d = float(shooter_skill) - float(mean_skill)
        return min(1.25, max(0.80, 1.0 + _d * _talent_sens(_d)))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Positioning split (2026-09-28, per Muck): the old single `positioning`
# is now offensive_positioning (getting open, net-front spot wins, shot
# quality) and defensive_positioning (gap control, box-outs, blocks,
# takeaways). Goalies keep the single `positioning` (crease) -- these
# helpers return it for goalies. Old saves/players have only `positioning`:
# both helpers fall back to it when the split attrs are absent or None.
# ONE decision, two fidelities -- both engines must read positioning
# through these, never getattr(player, "positioning") for a skater.
# ---------------------------------------------------------------------------

def offensive_positioning(player) -> float:
    """Skater's offensive positioning (1-100). Never raises."""
    try:
        v = getattr(player, "offensive_positioning", None)
        if v is None:
            v = getattr(player, "positioning", 50)
        return max(1.0, min(100.0, float(v)))
    except Exception:
        return 50.0


def defensive_positioning(player) -> float:
    """Skater's defensive positioning (1-100). Never raises."""
    try:
        v = getattr(player, "defensive_positioning", None)
        if v is None:
            v = getattr(player, "positioning", 50)
        return max(1.0, min(100.0, float(v)))
    except Exception:
        return 50.0


def is_goalie_position(player) -> bool:
    """True if the player is a goalie (keeps single `positioning`)."""
    try:
        pos = getattr(player, "primary_position", None)
        name = getattr(pos, "name", "") or str(pos)
        return "GOALIE" in name
    except Exception:
        return False


def roll_positioning_split(off_lo, off_hi, def_lo, def_hi, unicorn_rate=0.015):
    """Roll (offensive_positioning, defensive_positioning) for a new skater.

    Scale-agnostic: the caller passes ranges in its own attribute scale
    (draft prospects use the 20-scale, the database generator the 100-scale).
    Goalies never get the split -- they keep the single `positioning`
    (crease), so callers skip them and leave both attrs None.

    ~1.5% of rolls are Bergeron/Coffey unicorns: genuinely elite at both
    ends (both values rolled near the top of the better range).
    Never raises; always returns a pair of ints.
    """
    try:
        off_lo, off_hi = int(off_lo), int(off_hi)
        def_lo, def_hi = int(def_lo), int(def_hi)
        if off_lo > off_hi:
            off_lo, off_hi = off_hi, off_lo
        if def_lo > def_hi:
            def_lo, def_hi = def_hi, def_lo
        off = random.randint(off_lo, off_hi)
        dfn = random.randint(def_lo, def_hi)
        if random.random() < unicorn_rate:
            top = max(off_hi, def_hi)
            span = max(1, top // 6)
            off = random.randint(max(off_lo, top - span), top)
            dfn = random.randint(max(def_lo, top - span), top)
        return int(off), int(dfn)
    except Exception:
        return 50, 50


# ---------------------------------------------------------------------------
# Talent composites -- ONE decision, two fidelities (divergences #2 and #5).
# Both engines resolve shooter and goalie talent through these functions so
# attribute weighting is a single shared number. Weights are the
# quick-sim's live ones (the richer, considered model); GameSim's side was
# dead code (shooter) or an equal-split (goalie).
#
# SYNERGY GATE (2026-09-28, per Muck): composites aggregate by WEIGHTED
# HARMONIC mean, not arithmetic. A lone 85 spike surrounded by 30s no
# longer carries the bundle -- the harmonic mean drags lopsided profiles
# down hard while leaving balanced profiles essentially untouched
# (harmonic ~= arithmetic when all inputs are close). This is the
# anti-Sbisa gate: an 85 wristshot with 32 offensive awareness and 43
# skating is a 47 finisher, not an 85 one. Real hockey -- you can't
# snipe if you can't get open.
# ---------------------------------------------------------------------------

def harmonic_bundle(pairs) -> float:
    """Weighted harmonic mean of (weight, value) pairs. Never raises.

    Returns 50.0 on empty/bad input. Values are clamped to [1, 100]
    so a single 0/None attribute can't zero the whole bundle.
    """
    try:
        _num = 0.0
        _den = 0.0
        for _w, _v in pairs:
            _w = float(_w)
            _v = min(100.0, max(1.0, float(_v)))
            if _w <= 0:
                continue
            _num += _w
            _den += _w / _v
        if _num <= 0 or _den <= 0:
            return 50.0
        return _num / _den
    except Exception:
        return 50.0


# ---------------------------------------------------------------------------
# Finishing: the ONE shared finishing decision (2026-10-01, per Muck).
#
# WHY THIS EXISTS: the attribute_composites "finishing" was a +/-3%
# amplifier (decorative) while real conversion ran through
# shooter_skill_composite's 6-attribute blend -- two "finishings" that
# disagreed (a 57.9-composite winger scoring 61 goals). Now there is one:
# finishing_rating(). attribute_composites.raw_composite(player,
# "finishing") delegates here, and shooter_skill_composite (kept for API
# stability) is a thin wrapper. They cannot disagree again -- a repo QA
# test asserts the member tables stay in sync.
#
# WHAT IT IS (Muck's directive: diverse, honest): the shot-type-specific
# tool (wristshot/slapshot/one_timer/backhand, chosen per attempt -- the
# release itself, never generic "shooting"), shooting_accuracy (placement:
# corners, not crests), composure (hands under pressure), hockey_iq
# (reading the goalie, picking the spot), offensive_positioning (being in
# the right spot), off_the_puck (finding the seam, losing coverage),
# anticipation (reacting to the developing chance), pressure_player (the
# clutch release), deflections (tipping / hand-eye), balance (shooting in
# stride, through contact), strength (net-front, winning the spot to
# shoot), determination (second effort around the crease),
# aggressiveness (attacking the net, not the perimeter).
#
# Aggregated by harmonic_bundle (the synergy gate, per Muck 2026-09-28):
# a lone 95 wristshot with 45 composure and 50 IQ is a perimeter shooter,
# not a finisher -- the weak links drag, the way real hockey works.
# Form/heat/streak state is NEVER an input (see the composite module's
# FORM/HEAT/STREAK STATEMENT). Never raises.
# ---------------------------------------------------------------------------

#: Canonical finishing member table: (attribute, weight); weights sum to
#: 1.0 (asserted below). "_shot_tool" is the per-attempt shot-type value,
#: substituted by finishing_rating(). attribute_composites documents the
#: same table for the "finishing" composite (UI/introspection).
FINISHING_MEMBERS = (
    ("_shot_tool", 0.22),          # the release itself, per attempt
    ("shooting_accuracy", 0.16),   # placement -- corners, not crests
    ("composure", 0.10),           # hands under pressure
    ("hockey_iq", 0.08),           # reading the goalie, picking the spot
    ("offensive_positioning", 0.08),  # being in the right spot
    ("off_the_puck", 0.08),        # finding the seam, losing coverage
    ("anticipation", 0.06),        # reacting to the developing chance
    ("pressure_player", 0.05),     # the clutch release
    ("deflections", 0.05),         # tipping / hand-eye
    ("balance", 0.04),             # shooting in stride, through contact
    ("strength", 0.04),            # net-front, winning the spot to shoot
    ("determination", 0.02),       # second effort around the crease
    ("aggressiveness", 0.02),      # attacking the net, not the perimeter
)

# Weight-integrity gate: finishing weights must sum to 1.0.
assert abs(sum(_w for _, _w in FINISHING_MEMBERS) - 1.0) < 1e-9, \
    f"FINISHING_MEMBERS weights sum to {sum(_w for _, _w in FINISHING_MEMBERS)}"

#: Shot-tool attributes, in the order finishing_rating prefers them when
#: no per-attempt tool is supplied (best tool wins).
FINISHING_SHOT_TOOLS = ("wristshot", "slapshot", "one_timer", "backhand")


def _fin_attr(player, name, default=10.0):
    """Read one finishing member defensively. None -> default; the
    offensive/defensive_positioning split falls back to legacy
    `positioning` (old saves / generated players), mirroring
    mesh_system.offensive_positioning() and attribute_composites._attr.
    Never raises."""
    try:
        v = getattr(player, name, None)
        if v is None:
            if name in ("offensive_positioning", "defensive_positioning"):
                v = getattr(player, "positioning", None)
            if v is None:
                v = default
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def finishing_rating(player, shot_tool=None) -> float:
    """Canonical finishing rating on the native 1-100 scale.

    shot_tool: the actual shot-type value used on this attempt
    (wristshot/slapshot/one_timer/backhand -- each engine picks it from
    position/shot type the way it always has). When None (UI, AI reads),
    the shooter's best tool is used, so the stable rating reflects what
    he actually shoots with. Harmonic aggregation (synergy gate).
    Never raises.
    """
    try:
        if shot_tool is None:
            _tools = [_fin_attr(player, _t) for _t in FINISHING_SHOT_TOOLS]
            shot_tool = max(_tools)
        _pairs = []
        for _name, _w in FINISHING_MEMBERS:
            _v = (shot_tool if _name == "_shot_tool"
                  else _fin_attr(player, _name))
            _pairs.append((_w, _v))
        return harmonic_bundle(_pairs)
    except Exception:
        return 50.0


def shooter_skill_composite(shooter, shooting_base=None) -> float:
    """Shooter talent on the native 1-100 scale.

    (2026-10-01, per Muck: CONSOLIDATE.) The old 6-attribute blend
    (shot-attr 0.25 + shooting_accuracy 0.20 + offensive_awareness 0.20
    + skating 0.15 + off_the_puck 0.10 + composure 0.10) is retired --
    it disagreed with the attribute_composites "finishing" (two
    "finishings", one decorative). Now a thin wrapper over the ONE shared
    finishing_rating(): the diverse 13-member harmonic blend.
    shooting_base is the shot-type-specific base each engine picks from
    position/shot type the way it always has. Never raises.
    """
    return finishing_rating(shooter, shooting_base)


def goalie_skill_composite(goalie) -> float:
    """Goalie talent on the native 1-100 scale.

    Weights: goaltending 0.40 + reflexes 0.25 + positioning 0.20 +
    rebound_control 0.10 + composure 0.05. Never raises.
    """
    try:
        if goalie is None:
            return 67.5
        return (float(getattr(goalie, "goaltending", 10)) * 0.40
                + float(getattr(goalie, "reflexes", 10)) * 0.25
                + float(getattr(goalie, "positioning", 10)) * 0.20
                + float(getattr(goalie, "rebound_control", 10)) * 0.10
                + float(getattr(goalie, "composure", 10)) * 0.05)
    except Exception:
        return 67.5


# ---------------------------------------------------------------------------
# Assist logic -- ONE decision, two fidelities (Part B).
#
# Talent sits at the heart of every assist: playmaking attributes carry
# 70-80% of the decision weight, and dynamics (relationship closeness x
# line chemistry) are a capped x0.85-1.3 amplifier -- a grinder never
# out-assists elite vision, but linemates who read each other get the
# extra look. Both engines select passers, receivers, and secondary
# assists through these functions.
# ---------------------------------------------------------------------------

def playmaking_score(player) -> float:
    """Raw playmaking talent on the 1-100 scale.

    passing .45 + vision .35 + offensive_awareness .20, aggregated by
    harmonic_bundle (synergy gate) -- a lone passing spike can't carry
    30s vision/awareness. Never raises.
    """
    try:
        return harmonic_bundle([
            (0.45, getattr(player, "passing", 10)),
            (0.35, getattr(player, "vision", 10)),
            (0.20, getattr(player, "offensive_awareness", 10)),
        ])
    except Exception:
        return 30.0


def relationship_mult(a, b) -> float:
    """Dynamics amplifier from pairwise closeness: 1.0 + 0.15 * rel/100.

    rel is Player.relationships (other id -> -100..100, friend..rival).
    Capped 0.85..1.15. Never raises.
    """
    try:
        _rels = getattr(a, "relationships", None) or {}
        _rel = _rels.get(getattr(b, "id", None), 0)
        _rel = max(-100, min(100, int(_rel)))
        return max(0.85, min(1.15, 1.0 + 0.15 * (_rel / 100.0)))
    except Exception:
        return 1.0


def assist_weight(candidate, scorer, team=None, is_playoff=False) -> float:
    """Assist-credit weight for `candidate` on `scorer`'s goal.

    Secondary-assist model (2026-09-28, per Muck): passing LEADS (0.60) +
    awareness, less pressure-weighted. Relationship closeness x line
    chemistry (mesh_chance_factor) combine into one capped x0.85-1.3
    dynamics amplifier. Never raises.
    """
    try:
        _pm = max(5.0, secondary_assist_score(candidate))
        try:
            _chem = mesh_chance_factor(candidate, [scorer], team,
                                       is_playoff=is_playoff)
        except Exception:
            _chem = 1.0
        _dyn = max(0.85, min(1.3, relationship_mult(candidate, scorer)
                             * _chem))
        return _pm * _dyn
    except Exception:
        return 30.0


def record_assist_pair(ledger, passer, scorer, team_name):
    """Append (passer_id, scorer_id, team_name) to a bounded assist-pairs
    ledger (a collections.deque with a maxlen, owned by the engine).
    Feeds the analytics_hub / advanced_stats_analytics line-combination
    views. Never raises.
    """
    try:
        if ledger is not None and passer is not None and scorer is not None:
            ledger.append((getattr(passer, "id", None),
                           getattr(scorer, "id", None), team_name))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Form / streak / breakout: the mesh writes what it reads.
# ---------------------------------------------------------------------------

def _expected_points(player) -> float:
    """Rough points expectation for one game, scaled by talent. A 2-point
    night from a grinder is a surprise; from a star it is Tuesday."""
    t = talent_norm(player)
    return 0.15 + 1.1 * t * t


def _append_game_grade(player, grade: float) -> None:
    """Append one 0-100 game grade to the player's last-10 ledger.

    Capped at 15 entries; never raises. Both sim paths call this through
    record_performance() at the final whistle.
    """
    try:
        grades = getattr(player, "recent_game_grades", None)
        if not isinstance(grades, list):
            grades = []
            player.recent_game_grades = grades
        grades.append(round(max(0.0, min(100.0, float(grade))), 1))
        del grades[:-15]
    except Exception:
        pass


def record_performance(player, goals: int, assists: int, team=None,
                       is_playoff=False, saves: int = 0,
                       shots_against: int = 0) -> str | None:
    """Feed a finished game's line into the mesh form tracker.

    Also appends one 0-100 game grade to the player's recent_game_grades
    ledger (Muck 2026-10-01): skaters graded on points vs expectation,
    goalies on save% vs the .905 league line. The roster "Performance"
    column averages the last 10 -- recent form, never overall.

    Returns a storyline string when something notable happens (streak alive,
    breakout), else None. Probabilistic throughout: heaters are earned, never
    scheduled.
    """
    try:
        points = float(goals or 0) + float(assists or 0)
    except Exception:
        points = 0.0

    # Goaltenders: graded on save%, not points. Skipped when they saw no
    # rubber (didn't play) -- no grade appended.
    try:
        from game_classes import PlayerPosition
        _is_goalie = (getattr(player, "primary_position", None)
                      == PlayerPosition.GOALIE)
    except Exception:
        _is_goalie = False
    if _is_goalie:
        try:
            _sa = int(shots_against or 0)
            _sv = int(saves or 0)
        except Exception:
            _sa, _sv = 0, 0
        if _sa > 0:
            _svpct = _sv / _sa
            _append_game_grade(player, 50.0 + (_svpct - 0.905) * 1000.0)
        return None

    # Surprise relative to talent expectation; underdogs move the needle more.
    expected = _expected_points(player)
    surprise = (points - expected) / max(0.5, expected)
    tilt = 1.0 + (1.0 - talent_norm(player)) * _UNDERDOG_TILT

    # Game grade: 50 for meeting expectation, +/-25 per unit of surprise
    # (clamped to the mesh form's [-1.5, 2.0] window). A point-per-game
    # player going scoreless grades ~25; a 2-point night grades ~88.
    _append_game_grade(player, 50.0 + 25.0 * max(-1.5, min(2.0, surprise)))

    form = getattr(player, "mesh_form", 0.0) or 0.0
    try:
        form = float(form)
    except Exception:
        form = 0.0
    form = form * _FORM_DECAY + _FORM_LEARN * max(-1.5, min(2.0, surprise)) * tilt
    form = max(-1.0, min(1.0, form))
    try:
        player.mesh_form = form
    except Exception:
        pass

    streak = int(getattr(player, "mesh_streak", 0) or 0)
    note = None
    if form >= _STREAK_GATE:
        streak += 1
        # Developing player catching fire in the right conditions: a chance --
        # never a promise -- that this becomes his breakout/role moment.
        try:
            age = int(getattr(player, "age", 30) or 30)
            gp = int(getattr(player, "games_played", 999) or 999)
        except Exception:
            age, gp = 30, 999
        developing = age <= 25 and gp < 200
        if developing and streak >= _BREAKOUT_GAMES:
            if random.random() < _BREAKOUT_CHANCE:
                try:
                    m = int(getattr(player, "morale", 70) or 70)
                    player.morale = min(100, m + _BREAKOUT_MORALE_BUMP)
                except Exception:
                    pass
                name = getattr(player, "full_name", "The kid")
                note = (f"{name} is finding his role -- the game is slowing "
                        f"down for him during this stretch.")
                streak = 0  # one breakout per heater; a new one must be earned
        elif streak == 3:
            name = getattr(player, "full_name", "He")
            note = f"{name} is heating up -- three straight games feeling it."
    else:
        streak = 0
    try:
        player.mesh_streak = streak
    except Exception:
        pass
    return note


# ---------------------------------------------------------------------------
# Defensive contest + net-front battle (superstar mechanics 2026-09-28, per
# Muck). A goal is three things: get open (skating) + IQ (awareness) +
# finish (shooting) -- but defenders are not bystanders. The two on-ice D
# contest every shot (blocks, sticks, gap), and the net front is a real
# sub-model (win the spot -> screen -> tip -> finish), each stage gating
# the next. Shared layer: one decision, two fidelities. Additive; the
# synergy gate is untouched. Never raises.
# ---------------------------------------------------------------------------

# Defensive contest: how much the on-ice defenders reduce conversion.
# NHL reality: ~15-20 shots blocked per game league-wide, but per-shot the
# effect is modest -- an elite shot-blocker takes ~5-8% off, an average
# defender ~2-3%. The best defender's contest matters most (max, not sum).
_DEF_CONTEST_WEIGHTS = (0.35, 0.30, 0.20, 0.15)  # blk, daw, pos, poke


def defensive_contest_mult(defenders) -> float:
    """Multiplier on shot conversion from on-ice defensive pressure.

    1.0 = no contest. Each defender's contest score blends shot_blocking
    (blocks), defensive_awareness (gap), positioning (angles), pokecheck
    (sticks); the best defender's contest dominates. Returns 0.90-1.00.
    defenders: iterable of Player (usually the 2 on-ice D). Never raises.
    """
    try:
        _w = _DEF_CONTEST_WEIGHTS
        best = 0.0
        for d in (defenders or []):
            if d is None:
                continue
            _score = (float(getattr(d, "shot_blocking", 10)) * _w[0]
                      + float(getattr(d, "defensive_awareness", 10)) * _w[1]
                      + defensive_positioning(d) * _w[2]
                      + float(getattr(d, "pokecheck", 10)) * _w[3])
            if _score > best:
                best = _score
        if best <= 0:
            return 1.0
        # 50 (average) -> ~0.975; 85 (elite) -> ~0.93; 20 (poor) -> ~0.995
        _mult = 1.0 - max(0.0, min(0.10, (best - 30.0) * 0.002))
        return max(0.90, min(1.0, _mult))
    except Exception:
        return 1.0


def netfront_spot_win(attacker, defender) -> float:
    """Probability (0-1) the attacker wins the net-front spot.

    Attack: off_the_puck 0.35 (find the soft spot) + offensive_positioning
    0.35 (get open, seal the spot) + strength 0.15 + balance 0.15 (hold
    it). Defense: strength 0.35 (box out) + defensive_awareness 0.35
    (read) + defensive_positioning 0.30 (seal). A 10-point edge is ~65/35;
    20 points is ~80/20. Never raises.
    """
    try:
        _atk = (float(getattr(attacker, "off_the_puck", 10)) * 0.35
                + offensive_positioning(attacker) * 0.35
                + float(getattr(attacker, "strength", 10)) * 0.15
                + float(getattr(attacker, "balance", 10)) * 0.15)
        _dfn = 50.0
        if defender is not None:
            _dfn = (float(getattr(defender, "strength", 10)) * 0.35
                    + float(getattr(defender, "defensive_awareness", 10)) * 0.35
                    + defensive_positioning(defender) * 0.30)
        _edge = _atk - _dfn
        # logistic-ish: 0 -> 0.50, +10 -> 0.65, +20 -> 0.80, -10 -> 0.35
        _p = 0.50 + _edge * 0.015
        return max(0.05, min(0.95, _p))
    except Exception:
        return 0.50


def screen_goalie_mult(screener, goalie) -> float:
    """Goalie-skill multiplier from a net-front screen. <1.0 = screened.

    screen_shots (the screener's craft) vs the goalie's positioning (fight
    through) and anticipation (read the release). An elite screener (85)
    on an average goalie takes ~12% off; a poor screen does almost
    nothing. Applied on the goalie side, not as a shooter bonus -- the
    puck doesn't get harder to stop, the goalie sees it late. Never raises.
    """
    try:
        _screen = float(getattr(screener, "screen_shots", 10))
        _gresist = 50.0
        if goalie is not None:
            _gresist = (float(getattr(goalie, "positioning", 10)) * 0.60
                        + float(getattr(goalie, "anticipation", 10)) * 0.40
                        if hasattr(goalie, "anticipation") else
                        float(getattr(goalie, "positioning", 10)))
        _edge = _screen - _gresist
        # +20 edge -> 0.88; 0 -> 1.0; -20 -> 1.0 (no benefit for bad screen)
        _mult = 1.0 - max(0.0, min(0.15, _edge * 0.006))
        return max(0.85, min(1.0, _mult))
    except Exception:
        return 1.0


def tip_goal_chance(tipper, goalie, goalie_skill: float, screened: bool = False) -> float:
    """Goal probability on a deflection/tip, replacing the flat 25%.

    Tipper: deflections (hand-eye) 0.60 + off_the_puck 0.25 (be there) +
    balance 0.15 (stay upright through contact). Goalie: reflexes 0.70 +
    positioning 0.30, with the shot-type 'tip' penalty (-4) baked in.
    A screened goalie is easier to beat. Calibrated so an average tip is
    ~12-15%, an elite tip ~22-25%. Never raises.
    """
    try:
        _tip = (float(getattr(tipper, "deflections", 10)) * 0.60
                + float(getattr(tipper, "off_the_puck", 10)) * 0.25
                + float(getattr(tipper, "balance", 10)) * 0.15)
        _gsave = 50.0
        if goalie is not None:
            _gsave = (float(getattr(goalie, "reflexes", 10)) * 0.70
                      + float(getattr(goalie, "positioning", 10)) * 0.30)
        # tip penalty: harder to react (-4 ~ -4% absolute)
        _diff = _tip - _gsave - 4.0
        _p = 0.14 + _diff * 0.004
        if screened:
            _p *= 1.25
        return max(0.02, min(0.40, _p))
    except Exception:
        return 0.14


def netfront_finish_chance(finisher, goalie, goalie_skill: float) -> float:
    """Goal probability on a net-front rebound/loose puck.

    (2026-10-01, per Muck: CONSOLIDATE.) The finisher side now reads the
    ONE shared finishing_rating() -- the old bespoke blend (loose_puck
    0.40 + tight-shot 0.40 + composure 0.20) is retired so the rebound
    finish can't disagree with the composite either. The scramble WIN is
    still decided upstream (anticipation + offensive_awareness battle in
    each engine's rebound event); this is the finish once he has the
    puck in tight. Rebounds are high-danger: calibrated base ~22% and
    the [0.05, 0.55] bounds are untouched -- wiring, not recalibration.
    Never raises.
    """
    try:
        _fin = finishing_rating(finisher)
        _gsave = 50.0
        if goalie is not None:
            _gsave = (float(getattr(goalie, "reflexes", 10)) * 0.50
                      + float(getattr(goalie, "positioning", 10)) * 0.30
                      + float(getattr(goalie, "rebound_control", 10)) * 0.20)
        _diff = _fin - _gsave
        _p = 0.22 + _diff * 0.005
        return max(0.05, min(0.55, _p))
    except Exception:
        return 0.22


# Defenseman shot-volume adjustment (superstar mechanics 2026-09-28).
# Measured: D take 47.6% of shots (should be ~33%, real NHL). The sqrt
# flattening in shooter_choice_weight compresses archetype differences.
# This shared multiplier on D shot-selection weight corrects the volume
# to realistic levels. Shared decision (one decision, two fidelities).
# Retune 2026-09-28: 0.40 -> 0.48. D goal share measured 14.3% (target
# ~20-22%); slight volume restoration pairs with the discount softening
# above. Still well below the 47.6% problem level.
DEFENSE_SHOT_VOLUME_MULT = 0.48


# ---------------------------------------------------------------------------
# Assist model (2026-09-28, per Muck): passing is the LEAD attribute.
# A primary assist is not just passing: the passer's passing (lead) +
# offensive_awareness (picking the lane) + composure (under pressure) vs the
# defender's lane contest (pokecheck + defensive_awareness), AND the
# recipient's off_the_puck (getting open -- a great pass to a covered man
# dies). Secondary = the play-starter: passing (lead) + awareness, less
# pressure-weighted. A 95-passing playmaker with average awareness is still
# elite; the reverse is not true. Shared layer (one decision, two
# fidelities). Never raises.
# ---------------------------------------------------------------------------

# Primary assist composite weights: passing LEADS (0.55), awareness 0.20,
# composure 0.15, vision 0.10. Harmonic (synergy gate pattern).
_PRIMARY_ASSIST_WEIGHTS = (0.55, 0.20, 0.15, 0.10)
# Secondary assist: passing LEADS (0.60), awareness 0.25, vision 0.15.
# Less pressure-weighted (no composure).
_SECONDARY_ASSIST_WEIGHTS = (0.60, 0.25, 0.15)


def primary_assist_score(passer) -> float:
    """Passer rating for primary assists (1-100). Passing leads."""
    try:
        _w = _PRIMARY_ASSIST_WEIGHTS
        return harmonic_bundle([
            (_w[0], getattr(passer, "passing", 10)),
            (_w[1], getattr(passer, "offensive_awareness", 10)),
            (_w[2], getattr(passer, "composure", 10)),
            (_w[3], getattr(passer, "vision", 10)),
        ])
    except Exception:
        return 30.0


def secondary_assist_score(passer) -> float:
    """Passer rating for secondary assists (1-100). Passing leads."""
    try:
        _w = _SECONDARY_ASSIST_WEIGHTS
        return harmonic_bundle([
            (_w[0], getattr(passer, "passing", 10)),
            (_w[1], getattr(passer, "offensive_awareness", 10)),
            (_w[2], getattr(passer, "vision", 10)),
        ])
    except Exception:
        return 30.0


def pass_lane_contest_mult(defenders) -> float:
    """Multiplier on assist probability from defenders contesting the lane.

    1.0 = no contest. Uses pokecheck (sticks in lanes) + defensive_awareness
    (read the pass). Best defender contests. Returns 0.85-1.00.
    """
    try:
        best = 0.0
        for d in (defenders or []):
            if d is None:
                continue
            _score = (float(getattr(d, "pokecheck", 10)) * 0.50
                      + float(getattr(d, "defensive_awareness", 10)) * 0.50)
            if _score > best:
                best = _score
        if best <= 0:
            return 1.0
        # 50 -> 0.97; 85 -> 0.90; 20 -> 1.00
        return max(0.85, min(1.0, 1.0 - max(0.0, (best - 30.0) * 0.002)))
    except Exception:
        return 1.0


def recipient_openness_mult(recipient) -> float:
    """Multiplier for the pass recipient getting open (0.85-1.15).

    off_the_puck: 50 -> 1.00; 85 -> 1.12; 20 -> 0.88. A great pass to a
    covered man dies; a great pass to an open man is an assist.
    """
    try:
        _otp = float(getattr(recipient, "off_the_puck", 10))
        return max(0.85, min(1.15, 1.0 + (_otp - 50.0) * 0.004))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Defensive plays (2026-09-28, per Muck): no single-attribute decisions.
# Takeaway = defender's stickwork + awareness + gap vs carrier's control +
# strength (both sides' attributes). Hits = physicality + strength + balance
# vs target's balance/strength (the enforcer big-hit RATE in impact_system.py
# is Muck's standing 33.9% -- DO NOT TOUCH, this is only who wins the puck).
# Blocked shots = positioning + shot-blocking, ties into defensive_contest.
# Shared layer (one decision, two fidelities). Never raises.
# ---------------------------------------------------------------------------

def takeaway_prob(defender, carrier) -> float:
    """Probability defender takes the puck (0-1).

    Defender: pokecheck 0.40 (sticks) + defensive_awareness 0.35 (read) +
    skating 0.25 (gap control). Carrier: puck_handling-ish (stickhandling)
    0.40 + deking 0.30 + strength 0.30 (protect). Even matchup ~50%.
    """
    try:
        _def = (float(getattr(defender, "pokecheck", 10)) * 0.40
                + float(getattr(defender, "defensive_awareness", 10)) * 0.35
                + float(getattr(defender, "skating", 10)) * 0.25)
        _car = (float(getattr(carrier, "stickhandling", 10)) * 0.40
                + float(getattr(carrier, "deking", 10)) * 0.30
                + float(getattr(carrier, "strength", 10)) * 0.30)
        _edge = _def - _car
        return max(0.05, min(0.95, 0.50 + _edge * 0.015))
    except Exception:
        return 0.50


def hit_puck_win_prob(hitter, target) -> float:
    """Probability the hitter wins the puck on contact (0-1).

    Hitter: strength 0.40 + balance 0.30 (drive through) + aggressiveness
    0.30 (commit). Target: balance 0.50 (stay up) + strength 0.50 (absorb).
    This is NOT the big-hit rate (impact_system.py, Muck's 33.9% FLAG) --
    only who comes up with the puck.
    """
    try:
        _hit = (float(getattr(hitter, "strength", 10)) * 0.40
                + float(getattr(hitter, "balance", 10)) * 0.30
                + float(getattr(hitter, "aggressiveness", 10)) * 0.30)
        _tgt = (float(getattr(target, "balance", 10)) * 0.50
                + float(getattr(target, "strength", 10)) * 0.50)
        _edge = _hit - _tgt
        return max(0.05, min(0.95, 0.50 + _edge * 0.015))
    except Exception:
        return 0.50


def shot_block_prob(defender, shooter) -> float:
    """Probability defender blocks the shot attempt (0-1).

    Defender: positioning 0.50 (be in the lane) + shot_blocking 0.50
    (commit). Shooter: offensive_awareness 0.50 (find the lane) +
    composure 0.50 (get it through). Ties into defensive_contest_mult
    (the per-shot conversion effect); this is the discrete block event.

    Base recalibrated 2026-09-29 (per Muck: shot-volume truthfulness):
    the discrete block event targets ~8%. The sim generates ~38 attempts
    (not NHL's 60), so the VISIBLE SOG (~29) is the truth target -- the
    per-attempt block rate is calibrated to the sim's attempt volume,
    while the grade-aware miss below carries the truthful structure
    (clean looks rarely miss, perimeter prayers often do).
    """
    try:
        _blk = (defensive_positioning(defender) * 0.50
                + float(getattr(defender, "shot_blocking", 10)) * 0.50)
        _sht = (float(getattr(shooter, "offensive_awareness", 10)) * 0.50
                + float(getattr(shooter, "composure", 10)) * 0.50)
        _edge = _blk - _sht
        # Base ~8%, +/- by matchup
        return max(0.01, min(0.30, 0.08 + _edge * 0.004))
    except Exception:
        return 0.08


# --- Shared shot-fate decision (2026-09-29, per Muck: shot-volume truthfulness) ---
# NHL truth: ~49% of attempts reach the net (~29.5 SOG of ~60 attempts).
# The box score counts SOG (goals + saves), so the on-net rate is the
# visible number. Fate is GRADE-AWARE (truthful): clean slot looks
# rarely miss; perimeter prayers miss often.
#
# CALIBRATION NOTE (2026-09-29): the sim generates ~38 attempts/game
# (not NHL's 60), so the absolute miss/block rates are scaled to land
# the VISIBLE SOG at ~29 (the truth target). The grade-aware STRUCTURE
# (A<B<C miss ordering, accuracy scaling) is the truthful part; the
# absolute level is calibrated to the sim's attempt volume.
#
# D11 CONSOLIDATION (2026-09-30, per Muck: CONSOLIDATE, sequenced first
# in the re-tune): the genuinely-differing block/miss formulas lived in
# three places -- GameSim._check_shot_blocking/_check_shot_miss
# (location-based, system/tactic/pressure-aware), quick_sim's legacy
# _check_shot_blocking/_check_shot_blocking_coordinate (flat gates),
# and these shared helpers (attribute battle + grade-aware miss).
# There is now ONE decision: shot_fate(), composed of the shared arms
# shot_block_prob() (with resolve_blocker) and shot_miss_prob().
# GameSim calls it DIRECTLY; AdvGS calls approx_shot_fate(), the
# speed-optimized approximation of this same formula (one decision,
# two fidelities). All of GameSim's live situational modifiers fold in
# as `situation` INPUTS -- none dropped (see SHOT_FATE_SITUATION_KEYS).
#
# CRITICAL INVARIANT: fate never changes P(goal|attempt). Goals are
# decided at the attempt level by the conversion pipeline; fate only
# decides whether a non-goal attempt is recorded as a save (on net) or
# a miss/block (off net). Scoring volume is therefore preserved
# exactly while the visible shot count becomes truthful. Both engines
# consume this one decision (one decision, two fidelities).

# Location lane availability (D11): GameSim's live location block table
# (CREASE 0.4 ... wings 0.1), NORMALIZED to a mean of 1.0 over GameSim's
# _determine_shot_location mix (weighted mean of the table = 0.200) so
# the absolute level stays on Muck's approved ~8% block calibration
# (2026-09-29) while the location STRUCTURE becomes honest: slot shots
# meet more bodies in the lane, perimeter shots meet fewer.
SHOT_BLOCK_LANE_MULT = {
    "crease": 2.00,
    "low_slot": 1.50,
    "high_slot": 1.00,
    "left_circle": 0.75,
    "right_circle": 0.75,
    "point": 1.25,
    "left_wing": 0.50,
    "right_wing": 0.50,
    "behind_net": 0.50,
}

# Canonical situation-modifier keys for shot_block_prob(). Every engine
# folds its live situational modifiers in as INPUTS under these keys
# (each default 1.0) -- no live modifier is ever silently dropped by
# the shared decision.
SHOT_FATE_SITUATION_KEYS = (
    "sys",        # defensive system (GameSim: shell 1.2 / forecheck 0.9)
    "dz",         # DZ-coverage tactic (GameSim: collapse 1.25 / open 0.85)
    "pressure",   # defensive pressure scalar
    "tactics",    # installed-tactics "blocks" factor
    "tendency",   # the blocker's archetype block tendency
    "composite",  # defensive-play composite amplifier (bounded rails)
    "fatigue",    # shift-fatigue multiplier (AdvGS live; GameSim treats
                  # fatigue as a volume channel -> 1.0 here)
)


def _lane_mult(location) -> float:
    """Lane-availability multiplier for a shot location. Accepts a
    ShotLocation enum, a location-name string, or None (neutral 1.0).
    Unknown locations -> 1.0. Never raises."""
    try:
        if location is None:
            return 1.0
        _k = getattr(location, "value", location)
        return float(SHOT_BLOCK_LANE_MULT.get(str(_k).lower(), 1.0))
    except Exception:
        return 1.0


def shot_block_battle(defender, shooter) -> float:
    """The attribute lane battle (may be negative): the defender's lane
    presence minus the shooter's lane-finding. Split-aware --
    defensive_positioning (not the pre-split `positioning`) feeds
    blocks, per Muck's attribute-split directive. Never raises."""
    try:
        _blk = (defensive_positioning(defender) * 0.50
                + float(getattr(defender, "shot_blocking", 10)) * 0.50)
        _sht = (float(getattr(shooter, "offensive_awareness", 10)) * 0.50
                + float(getattr(shooter, "composure", 10)) * 0.50)
        return _blk - _sht
    except Exception:
        return 0.0


def resolve_blocker(defenders, weights=None):
    """Resolve the best blocker from the defending unit, by attributes.

    Score: shot_blocking 0.50 (commit) + defensive_positioning 0.30
    (close the lane) + defensive_awareness 0.20 (read the release),
    times the optional weight -- a callable defender->multiplier
    (e.g. archetype block tendency x trait bonus) or a dict keyed by
    defender. The CANDIDATE POOL is the caller's honest input: GameSim
    passes its proximity-filtered skaters (nobody blocks a shot from
    across the ice); AdvGS passes its D corps. Returns None when the
    pool is empty. Never raises.
    """
    try:
        _best, _best_s = None, None
        for _d in defenders or ():
            try:
                _s = (float(getattr(_d, "shot_blocking", 10)) * 0.50
                      + defensive_positioning(_d) * 0.30
                      + float(getattr(_d, "defensive_awareness", 10)) * 0.20)
                if weights is not None:
                    _w = weights(_d) if callable(weights) else weights.get(_d)
                    _s *= max(0.0, float(_w) if _w is not None else 1.0)
            except Exception:
                continue
            if _best_s is None or _s > _best_s:
                _best, _best_s = _d, _s
        return _best
    except Exception:
        return None


def shot_block_prob(defender, shooter, location=None, situation=None) -> float:
    """Probability defender blocks the shot attempt (0-1). THE shared
    block decision -- both engines consume it (GameSim directly, AdvGS
    via its speed-optimized approximation of this same formula).

    Defender: defensive_positioning 0.50 (be in the lane, split-aware)
    + shot_blocking 0.50 (commit). Shooter: offensive_awareness 0.50
    (find the lane) + composure 0.50 (get it through). Ties into
    defensive_contest_mult (the per-shot conversion effect); this is
    the discrete block event.

    location: shot location -> lane-availability multiplier (GameSim's
    live table, normalized to mean 1.0 so the absolute level stays on
    the approved ~8% calibration).
    situation: dict of situational multipliers (see
    SHOT_FATE_SITUATION_KEYS) -- defensive system, DZ tactic,
    pressure, installed tactics, tendency, composite, fatigue.

    Base recalibrated 2026-09-29 (per Muck: shot-volume truthfulness):
    the discrete block event targets ~8%. The sim generates ~38 attempts
    (not NHL's 60), so the VISIBLE SOG (~29) is the truth target -- the
    per-attempt block rate is calibrated to the sim's attempt volume,
    while the grade-aware miss below carries the truthful structure
    (clean looks rarely miss, perimeter prayers often do).

    Cap 0.50 (GameSim's live cap, unified -- the old 0.30 shared cap
    was calibrated for the location-blind version of this formula).
    """
    try:
        _p = 0.08 + shot_block_battle(defender, shooter) * 0.004
        _p *= _lane_mult(location)
        if situation:
            for _k in SHOT_FATE_SITUATION_KEYS:
                try:
                    _p *= float(situation.get(_k, 1.0))
                except Exception:
                    pass
        return max(0.01, min(0.50, _p))
    except Exception:
        return 0.08


SHOT_MISS_BY_GRADE = {
    # Grade-aware miss base: A (slot, clean) rarely misses; C (perimeter,
    # rushed) misses often. Scaled 2026-09-29 to land ~23% total cull
    # (block+miss) on the sim's ~38 attempts -> ~29 SOG (visible truth).
    "A": 0.05,
    "B": 0.15,
    "C": 0.25,
}


def shot_miss_prob(shooter, grade="B", distance=None) -> float:
    """Probability a non-blocked attempt misses the net entirely.

    Grade-aware base (clean looks rarely miss) scaled by the shooter's
    accuracy+composure: elite finishers miss less, rushed depth
    shooters miss more. distance (feet, optional): GameSim's live
    distance term, folded into the shared decision (D11) -- longer
    shots miss more. The old quality-bucket modifier is subsumed by
    the grade (grade IS the shared quality measure now).
    Scale-agnostic (handles 1-20 and 1-100 attribute scales).
    Never raises.
    """
    try:
        _g = str(grade or "B").upper()
        _base = float(SHOT_MISS_BY_GRADE.get(_g, 0.32))
        if distance is not None:
            # GameSim's live term: distance(feet) * 0.005, additive on
            # the base before the accuracy scaling (same structure as
            # the old (0.15 + d*0.005) * acc_factor, with the grade base
            # replacing 0.15 and the grade replacing the quality bucket).
            _base += max(0.0, float(distance)) * 0.005
        _acc = (_chance_attr(shooter, "shooting_accuracy", 50.0)
                + _chance_attr(shooter, "composure", 50.0)) / 2.0
        # Scale-agnostic normalize to 0..1
        _acc_n = _acc / 100.0 if _acc > 20.0 else _acc / 20.0
        _acc_n = max(0.0, min(1.0, _acc_n))
        # Elite (0.9) -> x0.75 miss; average (0.7) -> ~x1.0; poor (0.5) -> x1.2
        _mult = max(0.65, min(1.30, 1.65 - _acc_n))
        return max(0.02, min(0.75, _base * _mult))
    except Exception:
        return 0.32


class ShotFate(NamedTuple):
    """Result of the one shared shot-fate decision."""
    fate: str        # 'blocked' | 'missed' | 'on_net'
    blocker: object  # the defender credited with the block, else None


def shot_fate(shooter, defenders=None, grade="B", location=None,
              distance=None, situation=None, weights=None,
              _rng=None) -> ShotFate:
    """One shared decision: does the attempt get blocked, miss, or reach
    the net? (D11, per Muck: CONSOLIDATE.)

    Block rolls first: the best blocker is resolved from the defending
    unit by attributes (resolve_blocker -- the candidate pool is the
    caller's honest input), then the attribute lane battle rolls with
    the location and situational inputs. Then the grade-aware miss
    (with distance). Both engines consume this decision: GameSim calls
    it directly; AdvGS calls its speed-optimized approximation of this
    same formula (one decision, two fidelities). The goal roll happens
    independently at the attempt level in each engine.

    _rng: optional random.Random for seeded/paired use (testing).
    Never raises.
    """
    try:
        _rand = _rng.random if _rng is not None else random.random
        _blocker = resolve_blocker(defenders, weights) if defenders else None
        if _blocker is not None:
            if _rand() < shot_block_prob(_blocker, shooter,
                                         location, situation):
                return ShotFate("blocked", _blocker)
        if _rand() < shot_miss_prob(shooter, grade, distance):
            return ShotFate("missed", None)
        return ShotFate("on_net", None)
    except Exception:
        return ShotFate("on_net", None)


# ---------------------------------------------------------------------------
# Chance grading (2026-09-28, per Muck): every scoring chance is graded
# A/B/C at CREATION time in the shared layer -- the scoring analogue of the
# hit tiers (tired/normal/big) in impact_system.
#
#   Grade A (high-danger): slot, clean look, won the spot / quick release.
#     The shooter is FAVORED -- conversion premium (~NHL high-danger ~20%+).
#   Grade C (low-danger): perimeter, heavily contested, bad angle.
#     Defense + goalie are FAVORED -- conversion suppressed.
#   Grade B (medium): everything in between, and the MOST COMMON grade.
#     Decided by the full in-game factor stack (shooter composite vs
#     defensive contest vs situational goalie, modulated by rivalry /
#     morale / moment / atmosphere -- the existing conversion pipeline).
#
# WHO gets which grade is itself simulated (the key part):
#   Archetype/talent: snipers and elite playmakers generate more grade-A
#     looks; grinders get fewer. Offensive positioning, skating (separation)
#     and awareness gate grade-A frequency.
#   Matchup: grade-A rate scales against the opponent -- weak defensive
#     teams, tired D pairs and bad goalie matchups give up more grade-A
#     chances. A sniper vs a shutdown pair sees his grade-A share drop;
#     vs a weak third pair it spikes (player_archetypes.MATCHUPS).
#   Gametime: rivalry heat, morale, clutch/late-game moment and home-crowd
#     atmosphere all feed the chance-generation roll, the same way they
#     feed the rest of the on-ice engine. A heated rivalry game with a
#     roaring crowd tilts toward MORE chances, not just harder hits.
#
# Analytics: both engines record the grade on every shot attempt
# (grade_a/b/c_shots, grade_a/b/c_goals per player) -- the xG backbone
# for the analytics stack. ONE decision, two fidelities.
# ---------------------------------------------------------------------------

CHANCE_GRADE_A = "A"
CHANCE_GRADE_B = "B"
CHANCE_GRADE_C = "C"
CHANCE_GRADES = (CHANCE_GRADE_A, CHANCE_GRADE_B, CHANCE_GRADE_C)

# Location priors: (pA, pB, pC) before contest/tilt. Tune to feel, not
# gospel -- NHL-like targets are ~15-20% A, ~50-60% B, ~25-30% C overall.
CHANCE_LOCATION_PRIORS = {
    "breakaway": (0.85, 0.13, 0.02),
    "crease":    (0.50, 0.42, 0.08),
    "netfront":  (0.45, 0.43, 0.12),
    "slot":      (0.36, 0.52, 0.12),
    "point":     (0.08, 0.66, 0.26),
    "perimeter": (0.04, 0.52, 0.44),
}
# Raised 2026-09-29 (heater-damper removal pass): grade-A share had sunk
# to 8.9% after the talent-gradient restepening lowered mid-band tilts.
# Target ~15-20% -- elite talent (steep tilt) captures disproportionately
# more of the increase, which is the star-separation design working.

# Archetype grade-A generation tilt: who LIVES in the high-danger areas.
# Archetype differentiates WITHIN talent bands, never across them --
# talent (below) is the primary gate. A weight, NOT a prohibition
# (per Muck 2026-09-28): a generational enforcer with elite finishing
# attributes can still bury 50; he just earns fewer grade-A looks per
# unit of talent than a sniper does.
CHANCE_ARCHETYPE_A_TILT = {
    "Sniper": 1.08,
    "Playmaker": 1.10,
    "Power Forward": 1.12,
    "Two-Way Forward": 1.00,
    "Grinder": 0.80,
    "Enforcer": 0.72,
    "Offensive Defenseman": 1.04,
    "Puck-Moving Defenseman": 0.96,
    "Two-Way Defenseman": 0.94,
    "Physical Defenseman": 0.88,
    "Defensive Defenseman": 0.86,
}

# Conversion multipliers per grade, applied to the agreed conversion math.
# Grade A carries the NHL high-danger premium (~20%+): the mult is sized
# so a typical grade-A look (pre-grade ~0.09) converts around one in five.
# Grade C is suppressed (perimeter through traffic). Mean-preserving-ish
# across the target distribution -- the grade system REDISTRIBUTES
# finishing (stars separate) rather than inflating league scoring.
# Recalibrated 2026-09-29 (shot-volume pass): A 2.20->1.75 -- with the
# grade-A share restored to ~14%, the premium was inflating the tail
# (19 fifty-goal men). The A>B>C ordering is held; the absolute premium
# is reined in so 50-goal seasons stay rare.
CHANCE_GRADE_FINISH_MULT = {
    CHANCE_GRADE_A: 1.75,
    CHANCE_GRADE_B: 1.00,
    CHANCE_GRADE_C: 0.35,
}

# Grade-specific conversion clamps. Grade A reaches NHL high-danger:
# the ceiling lifts for clean slot looks instead of squashing every
# chance into the same band.
# Tightened 2026-09-29 (shot-volume pass): A ceiling 0.21->0.18 -- with
# ~14% of attempts grading A, the 21% ceiling was letting the tail run
# to 19 fifty-goal men. Still NHL high-danger (~18%), just not cartoon.
# (Open design question for Muck: original brief said ~20%+; the 0.20
# ceiling was tried and pushed fifty-goal men 13->17, so the tail is
# currently tamed here. Revisit on the opportunity/volume side.)
CHANCE_GRADE_CLAMP = {
    CHANCE_GRADE_A: (0.10, 0.18),
    CHANCE_GRADE_B: (0.04, 0.12),
    CHANCE_GRADE_C: (0.015, 0.09),
}


def _chance_attr(p, name: str, default: float = 50.0) -> float:
    try:
        v = getattr(p, name, default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def chance_archetype_a_tilt(player) -> float:
    """Grade-A generation tilt from the shooter's archetype. Never raises."""
    try:
        from player_archetypes import get_archetype as _ga
        return float(CHANCE_ARCHETYPE_A_TILT.get(_ga(player), 1.0))
    except Exception:
        return 1.0


def _piecewise_tilt(x, points):
    """Linear interpolation over (x, tilt) points. The talent gradient is
    explicit -- every point a named, A/B-tunable design decision (per Muck
    2026-09-29). Steep where it matters (the star band), gentle at the
    bottom so the 65-ovr's rare story stays real. Continuous, never a wall,
    no caps."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            _f = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return y0 + _f * (y1 - y0)
    return points[-1][1]


# Grade-A talent tilt curve (2026-09-29, per Muck): separates the star band
# so the leaderboard is star-dominated BY MECHANICS, not by rule.
# Recalibrated 2026-09-29 (damper-removal pass): the absolute level is set
# so 92-ovr elite lands in the 55-65 band. The 95/85 ratio is 1.29x --
# moderate steepness, but the clamp floor (0.50) lets the gradient actually
# separate at the bottom where it matters. Continuous, never a wall, no caps.
CHANCE_TALENT_TILT_POINTS = (
    (50, 0.38), (60, 0.48), (65, 0.58), (70, 0.62), (75, 0.70),
    (80, 0.74), (85, 0.78), (88, 0.82), (90, 0.88), (92, 0.90), (95, 0.94),
)


def _chance_talent_tilt(player) -> float:
    """Talent gate on grade-A frequency -- talent FIRST, archetype second
    (2026-09-29, per Muck wheelhouse). Offensive positioning (getting
    open), skating (separation), offensive awareness (finding the soft
    spot), on the CHANCE_TALENT_TILT_POINTS curve. NO CAPS (per Muck):
    steeply sloped by talent but never a wall. The 65-ovr's story stays
    real when the factors genuinely align (hot form, great linemates,
    weak matchups). Never raises."""
    try:
        _talent = (offensive_positioning(player) * 0.40
                   + _chance_attr(player, "skating") * 0.30
                   + _chance_attr(player, "offensive_awareness") * 0.30)
        return _piecewise_tilt(_talent, CHANCE_TALENT_TILT_POINTS)
    except Exception:
        return 1.0


def _chance_matchup_tilt(shooter, defenders, goalie,
                         d_fatigue: float = 50.0,
                         team_d_weakness: float = 1.0) -> float:
    """Matchup tilt on grade-A rate. Shutdown pairs smother skill
    (MATCHUPS matrix); tired D pairs, weak defensive teams and bad goalie
    matchups give up more grade-A chances. Never raises."""
    _tilt = 1.0
    try:
        from player_archetypes import (
            get_archetype as _ga, matchup_multiplier as _mm)
        _sarch = _ga(shooter)
        _darchs = []
        for _d in (defenders or []):
            try:
                if _d is not None:
                    _darchs.append(_ga(_d))
            except Exception:
                pass
        if _darchs:
            _tilt *= _mm([_sarch], _darchs)
    except Exception:
        pass
    try:
        # Tired D pairs leak high-danger looks (fatigue 0-100 scale).
        _f = max(0.0, min(100.0, float(d_fatigue or 50.0)))
        if _f > 60.0:
            _tilt *= 1.0 + min(0.25, (_f - 60.0) / 100.0 * 0.625)
    except Exception:
        pass
    try:
        _tilt *= max(0.80, min(1.30, float(team_d_weakness or 1.0)))
    except Exception:
        pass
    try:
        # Self-correcting realism (2026-09-29, per Muck): the league
        # adjusts. A heater draws the shutdown checkers -- tighter
        # coverage offsets the heater's swagger. Positive feedback
        # (heat -> chances) meets negative feedback (heat -> tighter
        # checking), so hot streaks self-limit instead of running to
        # 100-goal cartoons. Reuses the existing mesh form tracker.
        _heat = _player_heat(shooter)
        if _heat > 0.5:
            _tilt *= 1.0 - CHANCE_HEAT_CHECK * (_heat - 0.5) * 2.0
    except Exception:
        pass
    try:
        # Bad goalie matchup: shooters get cleaner looks against a
        # struggling netminder (tier rep vs ~88 league starter par).
        # Tier-based (Muck 2026-10-01): the goalie read is coarse.
        _govr = _chance_attr(goalie, "overall", 88.0)
        try:
            from attribute_composites import tier_proxy_overall as _tpo_gm
            _govr = float(_tpo_gm(float(goalie.overall_rating())))
        except Exception:
            try:
                _govr = float(goalie.overall_rating())
            except Exception:
                pass
        _tilt *= max(0.90, min(1.15, 1.0 + (88.0 - _govr) * 0.008))
    except Exception:
        pass
    # Tilt clamp (2026-09-29, damper-removal pass): [0.50, 1.20]. The floor
    # was 0.70 -- that compressed the gradient by preventing the bottom
    # from dropping, so lowering the top only flattened the curve (fatter
    # tail). 0.50 lets the gradient actually separate: elites earn their
    # A's, grinders earn fewer. The 1.20 cap (was 1.45) trims cartoon
    # compounding at the very top -- with the A-conversion ceiling at
    # 0.18, the tilt cap is the remaining tail lever. Still continuous,
    # no walls.
    return max(0.50, min(1.20, _tilt))

# -- Schemed-against superstars: SUPERSEDED 2026-09-30 ------------------
# The bolt-on schemed_against_contest_delta() lived here. It is now expressed
# AS a scenario battle in scenario_composites.py (apply_schemed_threat /
# schemed_factor_for_shooter), per the Scenario Combos design doc. Both
# engines call the scenario version. This stub documents the move; the
# implementation lives in the shared scenario module.



# Heater constants (2026-09-29, per Muck): the INTENSITY factor's player
# component. A player riding a heater earns chances at a hotter rate and
# converts with swagger -- an amplifier, not a cheat code. The boost
# (swagger) is paired with the check above (tighter checking) so the
# net heater effect is positive but self-limiting.
CHANCE_HEAT_BOOST = 0.12   # max +12% grade-A rate from a full heater
# Tighter-checking response (2026-09-29, per Muck): the honest half of
# heater self-correction. A hot player draws the shutdown coverage --
# his premium looks dry up because defenses overplay him, NOT because
# his finishing is nerfed. The player stays dangerous; the league adjusts.
# Calibrated 2026-09-29 (damper-removal pass): 0.18 -> 0.40. The -18%
# was not biting hard enough to self-limit 100-goal paces -- with the
# finishing shutdown gone, the checking response must actually contain
# a scorching star. Still probabilistic, still no wall. (0.40 was the
# intended value in the original shot-volume pass; the code never landed it.)
CHANCE_HEAT_CHECK = 0.40   # up to -40% grade-A rate at full heater


def _player_heat(player) -> float:
    """Heater level 0..1. Reuses the existing mesh form tracker
    (record_performance writes player.mesh_form, -1 cold .. 1 hot) --
    no duplicate engine. In-game 'seize the moment' (multi-goal period
    raising later-period grade-A) wires in via game_ctx in the
    factor-stack phase."""
    try:
        _form = float(getattr(player, "mesh_form", 0.0) or 0.0)
    except Exception:
        _form = 0.0
    return max(0.0, min(1.0, (_form + 1.0) / 2.0))


def chance_heat_boost_tilt(player) -> float:
    """INTENSITY: heater swagger on grade-A earning. The positive half of
    the heater; the negative half (tighter checking) lives in
    _chance_matchup_tilt. Never raises.
    
    Fixed 2026-09-29: was 1.0 + 0.12*heat, giving +6% at NEUTRAL heat
    (0.5) -- a systematic boost for everyone. Now centered: 1.0 at
    neutral, +12% at full heater, -12% at full cold.
    """
    try:
        _h = _player_heat(player)
        # Centered: 1.0 at neutral heat (0.5), +12% at full heater (1.0),
        # -12% at full cold (0.0).
        return 1.0 + CHANCE_HEAT_BOOST * (_h - 0.5) * 2.0
    except Exception:
        return 1.0


def _chance_gametime_tilt(rivalry_heat: float = 0.0, morale: float = 70.0,
                          clutch: bool = False, crowd_edge: float = 0.0,
                          is_playoff: bool = False) -> float:
    """Gametime tilt on chance generation: heated rivalry + roaring crowd
    = MORE chances (not just harder hits). Confident, clutch-time players
    find the premium ice. Never raises."""
    _tilt = 1.0
    try:
        _h = max(0.0, min(100.0, float(rivalry_heat or 0.0)))
        _tilt *= 1.0 + (_h / 100.0) * 0.18
    except Exception:
        pass
    try:
        _m = max(1.0, min(100.0, float(morale if morale else 70.0)))
        _tilt *= 0.92 + (_m / 100.0) * 0.16
    except Exception:
        pass
    try:
        if clutch:
            _tilt *= 1.10
        if is_playoff:
            _tilt *= 1.05
        _tilt *= 1.0 + max(-1.0, min(1.0, float(crowd_edge or 0.0))) * 0.05
    except Exception:
        pass
    return max(0.85, min(1.35, _tilt))


def roll_chance_grade(location: str = "slot", contest: float = 0.5,
                      shooter=None, defenders=None, goalie=None,
                      situation: dict = None,
                      game_ctx: dict = None) -> str:
    """Grade one scoring chance A/B/C at creation time. THE shared
    decision -- both engines roll through here.

    location: "breakaway" | "crease" | "netfront" | "slot" | "point" |
        "perimeter".
    contest: 0.0 (clean look) .. 1.0 (smothered) defensive pressure.
    situation: dict with optional keys quick_release, screened_goalie,
        won_spot, rebound, tip (bools).
    game_ctx: dict with optional keys rivalry_heat (0-100), morale
        (1-100), clutch (bool), crowd_edge (-1..1, + = behind shooter),
        is_playoff (bool), d_fatigue (0-100), team_d_weakness (mult),
        six_on_five_tilt (mult, workstream B), ot_3v3_tilt (mult,
        workstream B).

    Hard gates (chance quality is honest): breakaways, rebounds and won
    net-front spots are grade A; smothered perimeter/point shots are
    grade C. Everything else rolls the simulated distribution. Never
    raises -- falls back to "B".
    """
    try:
        _loc = str(location or "slot").lower()
        if _loc not in CHANCE_LOCATION_PRIORS:
            _loc = "slot"
        _con = max(0.0, min(1.0, float(contest if contest is not None
                                       else 0.5)))
        _sit = situation or {}
        _qr = bool(_sit.get("quick_release", False))
        _ws = bool(_sit.get("won_spot", False))
        _rb = bool(_sit.get("rebound", False))
        _tip = bool(_sit.get("tip", False))

        # -- Hard gates ------------------------------------------------
        if _loc == "breakaway" or _rb:
            return CHANCE_GRADE_A
        if _ws and _loc in ("crease", "netfront"):
            return CHANCE_GRADE_A
        if _tip and _ws:
            return CHANCE_GRADE_A
        if _loc == "perimeter" and _con >= 0.70:
            return CHANCE_GRADE_C
        if _loc == "point" and _con >= 0.80:
            return CHANCE_GRADE_C
        # Slot + clean + (quick release or won spot): the grade-A look.
        if _loc == "slot" and _con <= 0.30 and (_qr or _ws):
            return CHANCE_GRADE_A

        # -- Simulated distribution ------------------------------------
        _pA, _pB, _pC = CHANCE_LOCATION_PRIORS[_loc]

        # Contest shifts mass from A toward C (rushed release).
        # Tuned 2026-09-29: 0.38 -> 0.32 so tight checking suppresses
        # quality without erasing it (grade-A share was 8.9%, target
        # ~15-20%). The fixed value below matches this comment.
        _shift = _con * 0.32
        _moved_a = _pA * _shift
        _moved_b = _pB * _shift * 0.45
        _pA -= _moved_a
        _pB = _pB - _moved_b + _moved_a * 0.35
        _pC += _moved_a * 0.65 + _moved_b

        # Who gets the grade: archetype x talent x matchup x gametime.
        _tilt = (chance_archetype_a_tilt(shooter)
                 * _chance_talent_tilt(shooter))
        # INTENSITY: heater swagger (2026-09-29, per Muck). A player riding
        # a heater earns chances at a hotter rate -- the positive half of
        # the heater; the shutdown response is in _chance_matchup_tilt.
        _tilt *= chance_heat_boost_tilt(shooter)
        _gc = game_ctx or {}
        _tilt *= _chance_matchup_tilt(
            shooter, defenders, goalie,
            d_fatigue=_gc.get("d_fatigue", 50.0),
            team_d_weakness=_gc.get("team_d_weakness", 1.0))
        _tilt *= _chance_gametime_tilt(
            rivalry_heat=_gc.get("rivalry_heat", 0.0),
            morale=_gc.get("morale", _chance_attr(shooter, "morale", 70.0)),
            clutch=bool(_gc.get("clutch", False)),
            crowd_edge=_gc.get("crowd_edge", 0.0),
            is_playoff=bool(_gc.get("is_playoff", False)))
        # 6v5 scramble (workstream B, 2026-09-30): the pulled-goalie
        # segment's net-front chaos tilts grade-A EARNING -- who gets the
        # look -- never finishing. Generation side only; the protected
        # finishing mults/clamps below are untouched. Bounds [0.85, 1.50]
        # keep the scramble from swamping the talent gradient.
        _tilt *= max(0.85, min(1.50, float(_gc.get("six_on_five_tilt", 1.0)
                                          or 1.0)))
        # 3v3 OT (workstream B, 2026-09-30): open ice tilts grade-A earning
        # by the on-ice unit's skill -- generation side, same rule.
        _tilt *= max(0.90, min(1.40, float(_gc.get("ot_3v3_tilt", 1.0)
                                          or 1.0)))
        _tilt = max(0.25, min(3.20, _tilt))

        _pA = _pA * _tilt
        # No caps on _pA (per Muck 2026-09-29): the probability gradient is
        # truthful -- elite talent earns elite grade-A rates. Diminishing
        # returns emerge naturally from the normalization below (_tot grows
        # with _pA), not from a hand-placed ceiling. (Hard gates above
        # return before this; breakaways stay automatic.)
        # Classification (2026-09-30, workstream C2, Muck): a clean point
        # shot is a contested perimeter look, not a grade-A chance.
        # Unscreened, untipped point shots fold their grade-A mass into
        # B/C; the screened bomb (screened_goalie) and the tipped point
        # shot keep the honest path. This is CLASSIFICATION (what grade a
        # chance earns) -- the grade multipliers and clamps are untouched.
        _point_clean = (_loc == "point"
                        and not _sit.get("screened_goalie", False)
                        and not _tip and not _rb)
        if _point_clean and _pA > 0.0:
            _fold = _pA
            _pA = 0.0
            _bc = _pB + _pC
            if _bc > 0.0:
                _pB += _fold * (_pB / _bc)
                _pC += _fold * (_pC / _bc)
            else:
                _pC += _fold
        _pC = _pC / max(0.40, _tilt ** 0.6)
        _tot = _pA + _pB + _pC
        if _tot <= 0:
            return CHANCE_GRADE_B
        _pA, _pB, _pC = _pA / _tot, _pB / _tot, _pC / _tot

        _r = random.random()
        if _r < _pA:
            return CHANCE_GRADE_A
        if _r < _pA + _pB:
            return CHANCE_GRADE_B
        return CHANCE_GRADE_C
    except Exception:
        return CHANCE_GRADE_B


def chance_grade_finish_mult(grade: str) -> float:
    """Conversion multiplier for a graded chance. Never raises."""
    try:
        return float(CHANCE_GRADE_FINISH_MULT.get(str(grade).upper(),
                                                  1.0))
    except Exception:
        return 1.0


def chance_grade_clamp(grade: str):
    """(lo, hi) conversion clamp for a graded chance. Grade A reaches
    NHL high-danger (~20%+). Never raises."""
    try:
        return CHANCE_GRADE_CLAMP.get(str(grade).upper(), (0.04, 0.16))
    except Exception:
        return (0.04, 0.16)


# ---------------------------------------------------------------------------
# Personal finishing ceiling (2026-10-01, per Muck).
#
# THE DISEASE: the grade clamp was FLAT -- every shooter at/above ~60
# skill converted grade-A at the same 0.18. A 60-finishing winger with a
# heavy grade-A diet scored like a generational sniper.
#
# THE FIX: the league envelope (CHANCE_GRADE_CLAMP -- PROTECTED, never
# touched; the gate below asserts it) is the hard outer bound. WITHIN it,
# each shooter's personal ceiling scales with his finishing_rating.
# A 95+ finisher keeps the full envelope (league max unchanged -- the
# 0.18 grade-A ceiling still exists for the players who earn it); the
# mid-band compresses convexly so mediocre finishers can't ride volume
# to 60 goals. Both engines apply this same shared decision at the same
# point (the final clamp on goal probability). No caps, no dampers --
# pure talent. Never raises.
# ---------------------------------------------------------------------------

def finishing_ceiling_fraction(finishing: float) -> float:
    """Map a 1-100 finishing rating to [0, 1] of the grade envelope.

    Convex (exponent 1.1, anchored at 45): stars (90+) keep ~85-100% of
    the envelope, a 75-finishing shooter keeps about 57%, a
    60-finishing shooter about 27%. finishing >= 95 -> 1.0, so the
    league maximum is unchanged. Softened 2026-10-01 (was 1.3): the
    60-80 band was too compressed -- Muck wants windows for breakouts,
    not a structural cap. Never raises.
    """
    try:
        _f = max(1.0, min(100.0, float(finishing)))
        _x = max(0.0, min(1.0, (_f - 45.0) / 50.0))
        return _x ** 1.1
    except Exception:
        return 1.0


def ceiling_scenario_mult(player, linemates=None) -> float:
    """Scenario lift for the personal finishing ceiling (2026-10-01, Muck).

    The base ceiling is pure talent (finishing). But hockey has windows:
    a heater, elite linemates, great chemistry, schemed-against relief.
    Each factor >= 1.0; product capped at 1.8. Stars (95+) are already at
    the envelope max, so the lift only creates windows for the middle --
    separation by probability, not caps. Line FIT gates the linemate
    lifts: an elite linemate only opens your window if you actually fit
    with him (Muck 2026-10-01). Never raises.
    """
    try:
        _mult = 1.0
        # 1. Heat: a heater finishes better. 0.5 neutral -> 1.0;
        #    1.0 (red-hot) -> 1.25. Cold doesn't penalize here (it already
        #    hurts via the matchup tilt).
        try:
            _h = _player_heat(player)
            if _h > 0.5:
                _mult *= 1.0 + 0.50 * (_h - 0.5)
        except Exception:
            pass
        # 2-5. Linemate effects (need the on-ice unit).
        if linemates:
            try:
                _mates = [m for m in linemates if m is not None and m is not player]
                if _mates:
                    # 2. Line fit: how well the shooter's role complements his
                    #    linemates (0..1, 0.5 neutral). A sniper stapled to a
                    #    playmaker fits; two puck-hogs with no distributor
                    #    don't. Fit GATES the linemate lifts below -- a bad
                    #    fit means the elite linemate doesn't open your
                    #    window. (Muck 2026-10-01: "factor in whether
                    #    someones a fit on the line".)
                    _fit01 = 0.5
                    try:
                        from line_chemistry import _pair_complementarity as _pc
                        from line_chemistry import _role_name as _rn
                        _srole = _rn(player)
                        if _srole:
                            _fits = []
                            for _m in _mates:
                                _mr = _rn(_m)
                                if _mr:
                                    _fits.append(max(0.0, min(1.0,
                                        (_pc(_srole, _mr) + 10.0) / 22.0)))
                            if _fits:
                                _fit01 = sum(_fits) / len(_fits)
                    except Exception:
                        pass
                    # 3. Elite linemate, SCALED BY FIT: a 90+ finisher on your
                    #    line means better setups, more time/space -- but only
                    #    if you fit with him. 90 -> up to 1.10, 95 -> up to
                    #    1.15, 100 -> up to 1.20, all × fit01.
                    _best = max((finishing_rating(m) for m in _mates),
                                default=0.0)
                    if _best >= 90.0:
                        _raw = 0.20 * min(1.0, (_best - 90.0) / 10.0 + 0.5)
                        _mult *= 1.0 + _raw * _fit01
                    # 4. Line chemistry: great chemistry lifts everyone.
                    try:
                        from line_chemistry import line_chemistry_score as _lcs
                        _chem = float(_lcs([player] + _mates))
                        if _chem >= 70.0:
                            _mult *= 1.0 + 0.12 * min(1.0, (_chem - 70.0) / 30.0)
                    except Exception:
                        pass
                    # 5. Schemed-against relief, SCALED BY FIT: a star linemate
                    #    drawing the shutdown coverage leaves easier looks --
                    #    but only if you're a fit to exploit them.
                    try:
                        from line_chemistry import chemistry_relief_share as _crs
                        _stars = [m for m in _mates if finishing_rating(m) >= 90.0]
                        if _stars:
                            _relief = max(_crs(player, _s, [player] + _mates)
                                         for _s in _stars)
                            _mult *= (1.0 + 0.15
                                      * max(0.0, min(1.0, _relief)) * _fit01)
                    except Exception:
                        pass
                    # 6. Pure fit bonus: a great fit alone opens a small
                    #    window even without an elite linemate.
                    if _fit01 > 0.65:
                        _mult *= 1.0 + 0.10 * min(1.0, (_fit01 - 0.65) / 0.35)
            except Exception:
                pass
        return min(1.8, _mult)
    except Exception:
        return 1.0


def personal_grade_ceiling(player, grade, shot_tool=None, scenario_mult=1.0):
    """(lo, hi): the shooter's personal conversion ceiling for a graded
    chance. lo is the league floor for the grade; hi is the league
    ceiling scaled by finishing_ceiling_fraction(finishing_rating),
    lifted by scenario_mult (heat, linemates, chemistry, scheme relief)
    up to the envelope max. League max unchanged (95+ finishing -> the
    full envelope). Never raises.

    The scenario lift is ADDITIVE with diminishing returns (Muck
    2026-10-01): a hot 70-finisher gets a window, but cannot leapfrog
    a cold 82-finisher. Multiplicative lifts flatten the hierarchy --
    additive lifts preserve it. Separation by probability, not caps.
    """
    try:
        _lo, _hi = chance_grade_clamp(grade)
        _frac = finishing_ceiling_fraction(
            finishing_rating(player, shot_tool))
        # Additive lift: fills a portion of the headroom. A 0.4-base
        # with 0.8 lift -> 0.4 + 0.8*0.6*0.5 = 0.64. A 0.65-base with
        # no lift stays 0.65. Hierarchy preserved.
        _sm = max(1.0, float(scenario_mult or 1.0))
        _lift = _sm - 1.0  # 0.0 to 0.8
        _frac = min(1.0, _frac + _lift * (1.0 - _frac) * 0.5)
        return (_lo, _lo + (_hi - _lo) * _frac)
    except Exception:
        return chance_grade_clamp(grade)


# ---------------------------------------------------------------------------
# Situational goalie model (2026-09-28, per Muck): no single-attribute saves.
# Base composite goes multi-attribute; situation shifts the weights.
# Screened: positioning + composure (fight through traffic). Tips: reflexes.
# Breakaways: reflexes + composure. Point shots: positioning + rebound
# control. Rebound control feeds net-front chances (juicy rebounds = more
# loose-puck finishes). Shared layer (one decision, two fidelities).
# ---------------------------------------------------------------------------

# Situation weight profiles: (positioning, reflexes, glove, rebound, composure)
_GOALIE_SITUATION_WEIGHTS = {
    "clean":      (0.30, 0.25, 0.15, 0.15, 0.15),
    "screened":   (0.40, 0.15, 0.10, 0.10, 0.25),  # fight through traffic
    "tip":        (0.15, 0.45, 0.15, 0.10, 0.15),  # reaction
    "breakaway":  (0.20, 0.35, 0.15, 0.05, 0.25),  # reflexes + nerve
    "point":      (0.35, 0.20, 0.15, 0.20, 0.10),  # angles + control
}


def situational_goalie_skill(goalie, situation: str = "clean") -> float:
    """Goalie skill (1-100) weighted for the situation.

    Attributes: positioning (angles), reflexes, glove_hand+stick_side/2
    (glove/blocker), rebound_control, composure. Situation shifts weights
    per _GOALIE_SITUATION_WEIGHTS. Never raises.
    """
    try:
        _w = _GOALIE_SITUATION_WEIGHTS.get(situation, _GOALIE_SITUATION_WEIGHTS["clean"])
        _glove = (float(getattr(goalie, "glove_hand", 10))
                  + float(getattr(goalie, "stick_side", 10))) / 2.0
        return (float(getattr(goalie, "positioning", 10)) * _w[0]
                + float(getattr(goalie, "reflexes", 10)) * _w[1]
                + _glove * _w[2]
                + float(getattr(goalie, "rebound_control", 10)) * _w[3]
                + float(getattr(goalie, "composure", 10)) * _w[4])
    except Exception:
        return 67.5


def rebound_chance(goalie) -> float:
    """Probability a save produces a live rebound (0-1).

    Poor rebound_control = juicy rebounds = more net-front finishes.
    Elite (85): ~12%; average (50): ~25%; poor (20): ~38%.
    Feeds netfront_finish_chance via the sim's rebound events.
    """
    try:
        _rc = float(getattr(goalie, "rebound_control", 10))
        return max(0.05, min(0.50, 0.45 - _rc * 0.004))
    except Exception:
        return 0.25


# ---------------------------------------------------------------------------
# Coach instructions (D1 design build, 2026-09-30, per Muck).
# "Coach instructions must be realistic and dynamic to team situations and
# game events" -- with real multi-channel effects, on BOTH engines.
#
# One decision, two fidelities: the instruction SET (which instruction a
# coach wants, from live game state + his personality) and the EFFECTS
# (bounded channel multipliers) live here. GameSim calls directly;
# AdvancedGameSim calls the same functions with its fast state -- same
# inputs, same logic, never a different formula.
#
# Every effect channel is opportunity-mix / volume / behavior. Nothing here
# touches finishing constants or grade ceilings (protected levers).
# ---------------------------------------------------------------------------

#: Realistic coach-instruction vocabulary. What a real bench asks for.
COACH_INSTRUCTIONS = (
    "play_harder",      # demand more: heavier, more physical
    "tighten_up",       # defensive structure: deny the middle
    "crash_net",        # net-front emphasis: bodies and pucks to the blue paint
    "protect_lead",     # sit on it: suppress, don't chase
    "chase_game",       # open it up: volume now, exposure be damned
    "stay_disciplined", # no retaliation, no stupid penalties
)

#: Per-instruction effect channels. All values are small, bounded, additive
#: levers applied on top of the existing systems -- never pasted-on caps.
#:
#: - hit_big_add: added to big-hit probability in the impact tier
#:   (the existing play_harder +0.08 channel; stay_disciplined -0.02).
#: - penalty_mult: multiplies the penalty-draw weight (hit-result table on
#:   the watched path, _check_for_penalty on the quick path).
#: - rush_attack_nudge / rush_defense_nudge: points added to the 1v1 rush
#:   roll on the watched path (chance generation is a roll comparison).
#: - exposure_attack_nudge: when the DEFENDING team is chase_game, added to
#:   the attacker's rush roll (open hockey cuts both ways).
#: - slot_deny_attack / perimeter_shift: multiply the attacker's shot
#:   location weights when the defending team denies the middle -- slot
#:   denial as opportunity mix, never grade ceilings.
#: - crease_mult / lowslot_mult: attacking crash_net location weights.
#: - netfront_event_mult: quick-sim screen/deflection event probability
#:   (net-front presence on the fast path).
#: - shot_volume_mult / opp_shot_volume_mult: quick-sim SHOT event
#:   probability, own team and opponent suppression.
COACH_INSTRUCTION_EFFECTS = {
    "play_harder":      {"hit_big_add": 0.08, "penalty_mult": 1.10,
                         "rush_attack_nudge": 2.0, "shot_volume_mult": 1.02},
    "tighten_up":       {"rush_defense_nudge": 3.0, "penalty_mult": 0.95,
                         "slot_deny_attack": 0.85, "perimeter_shift": 1.12,
                         "shot_volume_mult": 0.98,
                         "opp_shot_volume_mult": 0.95},
    "crash_net":        {"crease_mult": 1.6, "lowslot_mult": 1.25,
                         "netfront_event_mult": 1.5,
                         "shot_volume_mult": 1.02},
    "protect_lead":     {"rush_defense_nudge": 4.0, "rush_attack_nudge": -3.0,
                         "slot_deny_attack": 0.90,
                         "shot_volume_mult": 0.96,
                         "opp_shot_volume_mult": 0.94},
    "chase_game":       {"rush_attack_nudge": 5.0, "shot_volume_mult": 1.08,
                         "exposure_attack_nudge": 3.0,
                         "opp_shot_volume_mult": 1.05},
    "stay_disciplined": {"penalty_mult": 0.85, "hit_big_add": -0.02},
}


def coach_instruction_effects(instruction):
    """Bounded effect dict for an instruction. Defensive copy; {} when none.

    Never raises.
    """
    try:
        _fx = COACH_INSTRUCTION_EFFECTS.get(instruction or "", None)
        return dict(_fx) if _fx else {}
    except Exception:
        return {}


def _coach_attr(coach, name, default=10.0):
    try:
        _v = getattr(coach, name, default)
        return float(_v) if _v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def coach_style_tag(coach):
    """A coach's style from his attributes. Priority: demanding >
    disciplinarian > structured > players_coach. Never raises."""
    try:
        if coach is None:
            return ""
        _disc = _coach_attr(coach, "discipline", 10)
        _mot = _coach_attr(coach, "motivating", 10)
        if _disc >= 14 and _mot >= 13:
            return "demanding"
        if _coach_attr(coach, "level_of_discipline", 10) >= 14:
            return "disciplinarian"
        if _coach_attr(coach, "defensive_coaching", 10) >= 14:
            return "structured"
        if _mot >= 14 and _disc < 12:
            return "players_coach"
    except Exception:
        pass
    return ""


def coach_instruction_efficacy(coach):
    """Buy-in scaler: motivating coaches get more out of the room.
    0.6..1.1, 1.0 at motivating 20. Never raises."""
    try:
        _m = _coach_attr(coach, "motivating", 10)
        return max(0.6, min(1.1, 0.8 + (_m - 10) * 0.02))
    except Exception:
        return 0.8


def instruction_penalty_mult(instruction, player=None, coach=None):
    """Penalty-draw multiplier for a team's instruction, mediated by the
    player's own discipline/composure and the coach's buy-in.

    stay_disciplined helps composed players most (they actually listen);
    play_harder's extra edge costs hotheads more. Bounded, additive.
    Never raises.
    """
    try:
        _fx = COACH_INSTRUCTION_EFFECTS.get(instruction or "", {})
        _base = float(_fx.get("penalty_mult", 1.0))
        if _base == 1.0:
            return 1.0
        _eff = coach_instruction_efficacy(coach)
        _disc = 10.0
        try:
            if player is not None:
                _disc = (float(getattr(player, "discipline", 10) or 10)
                         + float(getattr(player, "composure", 10) or 10)) / 2.0
        except Exception:
            pass
        # 0.7 (undisciplined) .. 1.3 (composed) mediation on the delta.
        _med = max(0.7, min(1.3, 0.7 + _disc / 33.0))
        if _base < 1.0:
            _med = max(0.7, min(1.3, 0.7 + _disc / 33.0))
        else:
            _med = max(0.7, min(1.3, 1.3 - _disc / 33.0))
        return 1.0 + (_base - 1.0) * _eff * _med
    except Exception:
        return 1.0


def ai_coach_instruction_for(score_diff, period, time_remaining, coach,
                             flags=frozenset(), rivalry_heat=0.0,
                             on_pp=False, on_pk=False):
    """The instruction an AI coach wants RIGHT NOW. THE shared decision --
    both engines call this with the same inputs.

    score_diff: from the coach's team's perspective (+ = leading).
    period: 1..4+. time_remaining: seconds left in the period.
    coach: staff object (or None) -- style from attributes.
    flags: set of {"goal_against", "star_injured", "fight",
        "big_hit_on_star"} -- live game events since the last look.
    rivalry_heat: 0-100. on_pp / on_pk: special-teams state.
    Returns an instruction id or None (even keel). Never raises.
    """
    try:
        _flags = set(flags or ())
        _style = coach_style_tag(coach)
        _sd = int(score_diff or 0)
        _per = int(period or 1)
        _t = max(0.0, float(time_remaining if time_remaining is not None
                            else 1200))
        # -- special teams: the situation is the instruction -------------
        if on_pk:
            return "stay_disciplined"
        if on_pp:
            return "crash_net"
        # -- live events: the coach reacts to what just happened ---------
        if "star_injured" in _flags:
            return "play_harder"
        if "fight" in _flags:
            if _style in ("disciplinarian", "structured"):
                return "stay_disciplined"
            if _style == "demanding":
                return "play_harder"
            return None
        if "big_hit_on_star" in _flags:
            if _style == "disciplinarian":
                return "stay_disciplined"
            if _style == "demanding":
                return "play_harder"
            return None
        if "goal_against" in _flags:
            if _style == "demanding":
                return "play_harder"
            if _style in ("structured", "disciplinarian"):
                return "tighten_up"
            if _style == "players_coach":
                return "play_harder"  # a players' coach answers with energy
            return None
        # -- score + clock ------------------------------------------------
        _late = (_per == 3 and _t <= 300) or _per > 3
        if _late:
            if _sd <= -3:
                return "play_harder"
            if _sd <= -1:
                return "chase_game"
            if _sd >= 3:
                return "stay_disciplined"
            if _sd >= 1:
                return "protect_lead"
            # tied late: win it or lock it down -- style decides.
            if _style == "demanding":
                return "play_harder"
            if _style in ("structured", "disciplinarian"):
                return "tighten_up"
            return None
        if _per >= 2 and _sd <= -2 and _style == "demanding":
            return "play_harder"
        # -- pregame: bad blood is the only ask ---------------------------
        if _per == 1 and _sd == 0 and not _flags:
            try:
                if float(rivalry_heat or 0) >= 70:
                    return "play_harder"
            except Exception:
                pass
        return None
    except Exception:
        return None
