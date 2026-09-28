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
# average shot. Measured 2026-09-27 across generated league talent; re-measure
# if the player generator's attribute distributions change.
SKILL_DIFF_BASELINE = -14.8
SHOT_BASE_CHANCE = 0.09
SHOT_SKILL_SENSITIVITY = 0.008


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
    the designed 9%. Restores intent; changes no attribute and no sensitivity.
    """
    return SHOT_BASE_CHANCE + ((skill_diff - SKILL_DIFF_BASELINE)
                               * SHOT_SKILL_SENSITIVITY)


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
