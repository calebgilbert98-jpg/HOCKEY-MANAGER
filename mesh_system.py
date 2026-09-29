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
SHOT_BASE_CHANCE = 0.09
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
SHOT_TALENT_SENS_TOP = 0.004
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


def shooter_finish_mult(shooter_skill: float, mean_skill: float = 65.3) -> float:
    """Multiplicative finishing factor (GameSim fidelity): 1.0 at
    league-average skill, piecewise slope (flat middle, convex top) -- the
    same talent decision quick-sim's additive model makes above. Clamped
    0.80-1.25. Never raises.
    """
    try:
        _d = float(shooter_skill) - float(mean_skill)
        return min(1.25, max(0.80, 1.0 + _d * _talent_sens(_d)))
    except Exception:
        return 1.0


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


def shooter_skill_composite(shooter, shooting_base=None) -> float:
    """Shooter talent on the native 1-100 scale.

    Weights: shot-attr 0.25 + shooting_accuracy 0.20 + offensive_awareness
    0.20 + skating 0.15 + off_the_puck 0.10 + composure 0.10. shooting_base
    is the shot-type-specific base (wristshot/slapshot/one_timer/backhand);
    each engine picks it from position/shot type the way it always has,
    then shares this weighting. Aggregated by harmonic_bundle (synergy
    gate) -- the "get open" attributes (awareness, skating) gate the shot.
    Never raises.
    """
    try:
        if shooting_base is None:
            shooting_base = getattr(shooter, "wristshot", 10)
        return harmonic_bundle([
            (0.25, shooting_base),
            (0.20, getattr(shooter, "shooting_accuracy", 10)),
            (0.20, getattr(shooter, "offensive_awareness", 10)),
            (0.15, getattr(shooter, "skating", 10)),
            (0.10, getattr(shooter, "off_the_puck", 10)),
            (0.10, getattr(shooter, "composure", 10)),
        ])
    except Exception:
        return 50.0


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

    Playmaking attributes dominate; relationship closeness x line
    chemistry (mesh_chance_factor) combine into one capped x0.85-1.3
    dynamics amplifier. Never raises.
    """
    try:
        _pm = max(5.0, playmaking_score(candidate))
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


def record_performance(player, goals: int, assists: int, team=None,
                       is_playoff=False) -> str | None:
    """Feed a finished game's line into the mesh form tracker.

    Returns a storyline string when something notable happens (streak alive,
    breakout), else None. Probabilistic throughout: heaters are earned, never
    scheduled.
    """
    try:
        points = float(goals or 0) + float(assists or 0)
    except Exception:
        points = 0.0

    # Skaters only: points aren't a goaltender's currency.
    try:
        from game_classes import PlayerPosition
        if getattr(player, "primary_position", None) == PlayerPosition.GOALIE:
            return None
    except Exception:
        pass

    # Surprise relative to talent expectation; underdogs move the needle more.
    expected = _expected_points(player)
    surprise = (points - expected) / max(0.5, expected)
    tilt = 1.0 + (1.0 - talent_norm(player)) * _UNDERDOG_TILT

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
