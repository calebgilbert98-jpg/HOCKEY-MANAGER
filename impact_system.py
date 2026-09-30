# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Impact-tier engine: every shot, hit and save resolves at one of three
impact levels -- TIRED, NORMAL, BIG.

This is an *additive* layer over the existing sim resolution. Nothing here
replaces existing probability logic: each event is classified from personnel
(attributes, archetype, personality), fatigue, game state and coaching, and
the classifier returns small multipliers / nudges that the existing
resolvers apply on top of their own math.

Design notes (from the brief):
- Tired shots are uncommon and reflect a bad game: elite talent almost
  never throws one unless gassed (end of a long shift) or killing a
  penalty. Fringe rookies are streakier: more tired, fewer big, higher
  variance -- scaled by game difficulty via the existing scoring level.
- Big is the opposite: the highlight-reel / tone-setting version.
- A coach instructing his team to play harder shifts the *hit* tier
  distribution up (capped -- nothing crazy). Big hits carry more injury
  risk and move game intensity.
- Big moments only "tell the story" when they need to: tied/late/close
  games, playoffs, or genuine impact players. Everything else stays
  quiet so the broadcast doesn't cry wolf.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

TIRED = 0
NORMAL = 1
BIG = 2

TIER_NAME = {TIRED: "tired", NORMAL: "normal", BIG: "big"}


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class ImpactContext:
    """Everything the classifiers need about the moment of the event."""
    fatigue: float = 100.0          # actor's energy 0-100
    shift_seconds: float = 0.0      # time since actor's line hit the ice
    on_pk: bool = False
    on_pp: bool = False
    score_diff: int = 0            # from the actor's team perspective
    period: int = 1
    clock_seconds: float = 1200.0   # time remaining in period
    is_playoff: bool = False
    tension: float = 0.0           # 0-100 live game intensity
    crowd_energy: float = 50.0     # 0-100 building loudness (arena_atmosphere)
    crowd_mood: float = 0.0        # actor-relative: + = crowd behind them
    coach_instruction: Optional[str] = None   # e.g. "play_harder"
    coach: Any = None
    team: Any = None
    scoring_mult: float = 1.0      # game difficulty (existing scoring level)
    # "Special night" counters: what the actor has done *in this game*.
    # A player with 2 goals / 3 points, or a goalie standing on his head
    # with 25+ saves, has earned the broadcast treatment for his next big
    # moment -- the story is the man, not just the moment.
    game_goals: int = 0
    game_points: int = 0
    game_saves: int = 0


# ---------------------------------------------------------------------------
# Small helpers (all defensive -- never raise)
# ---------------------------------------------------------------------------

def _attr(p: Any, name: str, default: float = 50.0) -> float:
    try:
        v = getattr(p, name, default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _overall(p: Any) -> float:
    try:
        r = p.overall_rating()
        return float(r) if r is not None else 70.0
    except Exception:
        return _attr(p, "overall", 70.0)


def _archetype(p: Any) -> str:
    try:
        from player_archetypes import get_archetype
        return str(get_archetype(p) or "")
    except Exception:
        return ""


def _personality_heat(p: Any, team: Any = None, coach: Any = None) -> float:
    """His volatility offset: positive = escalates, negative = calms."""
    try:
        import reputation_system as rs
        off, _reasons = rs._player_volatility_offset(p, team, coach)
        return float(off or 0)
    except Exception:
        return 0.0


def _coach_play_harder(coach: Any, ctx: ImpactContext) -> float:
    """0..1 intensity of a 'play harder' instruction.

    Explicit instruction wins; otherwise derived from the coach's own
    makeup and the game state (a demanding coach trailing late demands
    more). Returns 0 when nobody is asking for more.
    """
    if (ctx.coach_instruction or "") == "play_harder":
        return 1.0
    try:
        if coach is None:
            return 0.0
        discipline = _attr(coach, "discipline", 10)
        motivating = _attr(coach, "motivating", 10)
        # Demanding, motivational benches dial it up when chasing late.
        if discipline >= 14 and motivating >= 13:
            if ctx.period >= 3 and ctx.score_diff < 0:
                return 0.7
            if ctx.score_diff < 0:
                return 0.35
        return 0.0
    except Exception:
        return 0.0


def _talent_tier_probs(overall: float) -> Tuple[float, float, float]:
    """Base (tired, normal, big) probabilities scaled by talent.

    Elite players live at normal-or-better; fringe players are streakier:
    more tired nights, fewer big moments, and the caller adds variance.
    """
    if overall >= 88:      # star / McDavid tier
        return (0.04, 0.76, 0.20)
    if overall >= 80:      # top-six quality
        return (0.07, 0.78, 0.15)
    if overall >= 72:      # solid NHLer
        return (0.10, 0.80, 0.10)
    # fringe / rookie: streaky
    return (0.16, 0.78, 0.06)


def _roll(pt: float, pn: float, pb: float) -> int:
    r = random.random()
    if r < pb:
        return BIG
    if r < pb + pn:
        return NORMAL
    return TIRED


def _crowd_tier_nudge(ctx: ImpactContext) -> float:
    """Crowd nudge on big-moment probability (multiplier ~0.85-1.20).

    Loud buildings produce more big moments for everyone -- the energy is
    contagious. But the mood decides who it helps: being backed by the
    crowd adds, being booed or skating into a hostile barn takes away --
    and the mood outweighs the raw noise.
    """
    try:
        e = (float(ctx.crowd_energy) - 50.0) / 50.0      # -1..1
        m = max(-1.0, min(1.0, float(ctx.crowd_mood) / 100.0))
    except Exception:
        return 1.0
    return max(0.85, min(1.20, 1.0 + 0.08 * e + 0.12 * m))


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------

def classify_shot_impact(shooter: Any, ctx: ImpactContext) -> int:
    """Tier of a shot attempt."""
    overall = _overall(shooter)
    pt, pn, pb = _talent_tier_probs(overall)

    # Attribute engine: pure shooters threaten more.
    shoot = (_attr(shooter, "shooting_power") + _attr(shooter, "shooting_accuracy")
             + _attr(shooter, "shooting")) / 3.0
    pb += max(-0.06, min(0.08, (shoot - 70) / 400.0))

    # Archetype voice.
    arch = _archetype(shooter).lower()
    if "sniper" in arch:
        pb += 0.06
    elif "playmaker" in arch:
        pb -= 0.03
        pt += 0.02
    elif "grinder" in arch or "enforcer" in arch:
        pb -= 0.02
        pt += 0.03

    # Fatigue: the McDavid rule. Tired legs make tired shots -- but elite
    # talent on fresh legs almost never throws one.
    if ctx.fatigue < 35:
        pt += 0.14
        pb -= 0.08
    elif ctx.fatigue < 55:
        pt += 0.06
        pb -= 0.03
    # End of a long shift: heavy legs for anyone.
    if ctx.shift_seconds > 75:
        pt += 0.10
        pb -= 0.05
    elif ctx.shift_seconds > 50:
        pt += 0.05
    # Killing a penalty is exhausting; the shot is usually a clearance.
    if ctx.on_pk:
        pt += 0.10
        pb -= 0.06

    # Personality heat: volatile players occasionally uncork one.
    heat = _personality_heat(shooter, ctx.team, ctx.coach)
    if heat > 4:
        pb += 0.03

    # Fringe-player variance: streaky, both directions.
    if overall < 72:
        swing = random.uniform(-0.03, 0.03)
        pb += swing
        pt -= swing

    # Normalize and roll.
    # Crowd: loud buildings make big moments likelier; a hostile or
    # nervous barn takes a touch away from the unsupported side.
    pb *= _crowd_tier_nudge(ctx)

    pt = max(0.01, pt)
    pb = max(0.01, pb)
    pn = max(0.01, 1.0 - pt - pb)
    s = pt + pn + pb
    return _roll(pt / s, pn / s, pb / s)


# ---------------------------------------------------------------------------
# Bodycheck refinement (T1 refinement, 2026-09-30)
#
# bodycheck is truth-in-display since the attributes pass (4th voice in the
# hit blend above). The refinement gives it two more jobs, both bounded and
# both additive -- no tier threshold, band, or existing constant changes:
#
# 1. LIKELIHOOD: _bodycheck_big_roll_mult -- a bounded multiplier on the
#    big-hit roll inside classify_hit_impact (applied above).
# 2. POWER: _bodycheck_power_mult -- a bounded within-tier multiplier on
#    the downstream hit effects (injury / turnover / heat) in hit_effects
#    below. A high-bodycheck hitter's connects land heavier without ever
#    changing which tier the hit classified into.
# ---------------------------------------------------------------------------

def _bodycheck_big_roll_mult(hitter: Any) -> float:
    """Big-hit roll multiplier from bodycheck. Rails [0.90, 1.15]."""
    try:
        bc = float(getattr(hitter, "bodycheck", 70) or 70)
    except (TypeError, ValueError):
        bc = 70.0
    mult = 1.0 + (bc - 70.0) / 200.0
    return max(0.90, min(1.15, mult))


def _bodycheck_power_mult(hitter: Any) -> float:
    """Within-tier hit-power multiplier from bodycheck. Rails [0.92, 1.12]:
    a 90-bodycheck hitter's connects scale injury/turnover/heat ~+8%;
    a 50-bodycheck hitter's ~-8%; 70 is neutral."""
    try:
        bc = float(getattr(hitter, "bodycheck", 70) or 70)
    except (TypeError, ValueError):
        bc = 70.0
    mult = 1.0 + (bc - 70.0) / 250.0
    return max(0.92, min(1.12, mult))


def classify_hit_impact(hitter: Any, target: Any, ctx: ImpactContext) -> int:
    """Tier of a body check."""
    overall = _overall(hitter)
    pt, pn, pb = _talent_tier_probs(overall)

    # Attribute engine: hitters hit.
    # T1 truth-in-display (2026-09-29): bodycheck was card-only decoration.
    # It now feeds the big-hit tier as a fourth voice in the blend -- the
    # (-0.05, +0.09) band is unchanged, so no existing outcome can move
    # further than it already could; only the input is more truthful.
    hit_attr = (_attr(hitter, "checking") + _attr(hitter, "aggressiveness")
                + _attr(hitter, "determination")
                + _attr(hitter, "bodycheck")) / 4.0
    pb += max(-0.05, min(0.09, (hit_attr - 70) / 350.0))

    # T1 refinement (2026-09-30): bodycheck raises the BIG-tier
    # classification probability directly -- a bounded multiplier on the
    # big-hit roll, applied after the attribute blend and before the
    # archetype/coach/personality voices (those still add on top).
    # Formula: mult = clamp(1 + (bodycheck - 70) / 200, 0.90, 1.15).
    # Rails [0.90, 1.15]: a 90-bodycheck hitter rolls ~+10% big
    # probability; a 50-bodycheck hitter rolls ~-10%; 70 is neutral
    # (missing attr defaults to 70 -- no penalty on old saves).
    # Tier thresholds are untouched; this only reweights the roll.
    # Guardrail: enforcer big-hit rate (~33.9% vs ~30% band) is Muck's
    # standing calibration -- shrink the rails if the league rate drifts.
    pb *= _bodycheck_big_roll_mult(hitter)

    arch = _archetype(hitter).lower()
    if "enforcer" in arch:
        # FLAG (Muck, 2026-09-28): enforcers roll ~34% big-hit -- deliberately
        # above the ~30% band. Big hits are an enforcer's claim to fame and
        # roster value in this league; do not "normalize" this bonus down
        # without his call.
        pb += 0.08
    elif "grinder" in arch or "power forward" in arch or "powerforward" in arch:
        pb += 0.05
    elif "sniper" in arch or "playmaker" in arch:
        pb -= 0.03
        pt += 0.02

    # Coach instruction: "play harder" shifts the distribution up --
    # capped, nothing crazy (+8% big at full instruction).
    harder = _coach_play_harder(ctx.coach, ctx)
    if harder:
        pb += 0.08 * harder
        pt -= 0.03 * harder

    # Hotheads finish everything.
    heat = _personality_heat(hitter, ctx.team, ctx.coach)
    if heat > 4:
        pb += 0.04
    elif heat < -4:
        pb -= 0.02

    # Gassed hitters arm-tackle.
    if ctx.fatigue < 35:
        pt += 0.12
        pb -= 0.07
    elif ctx.fatigue < 55:
        pt += 0.05

    # Target matters a little: trucking a star is the statement.
    if _overall(target) >= 85:
        pb += 0.02

    if overall < 72:
        swing = random.uniform(-0.03, 0.03)
        pb += swing
        pt -= swing

    # Crowd: loud buildings make big moments likelier; a hostile or
    # nervous barn takes a touch away from the unsupported side.
    pb *= _crowd_tier_nudge(ctx)

    pt = max(0.01, pt)
    pb = max(0.01, pb)
    pn = max(0.01, 1.0 - pt - pb)
    s = pt + pn + pb
    return _roll(pt / s, pn / s, pb / s)


def classify_save_impact(goalie: Any, shooter: Any, shot_quality: float,
                         distance: float, ctx: ImpactContext) -> int:
    """Tier of a save. A routine wrister from the boards can't be big;
    a robbery on a grade-A look can."""
    overall = _overall(goalie)
    pt, pn, pb = _talent_tier_probs(overall)

    tech = (_attr(goalie, "reflexes") + _attr(goalie, "positioning")
            + _attr(goalie, "rebound_control")) / 3.0
    pb += max(-0.05, min(0.08, (tech - 70) / 400.0))

    # Danger of the look gates the ceiling: no big saves on muffins.
    try:
        q = float(shot_quality)
    except (TypeError, ValueError):
        q = 0.4
    if q > 0.65 and distance < 30:
        pb += 0.10  # grade-A robbery territory
    elif q < 0.3:
        pb = min(pb, 0.03)
        pt += 0.05

    # Big-game goalies: steadier when it matters.
    if ctx.is_playoff or (ctx.period >= 3 and abs(ctx.score_diff) <= 1):
        if overall >= 85:
            pb += 0.04
            pt -= 0.03
        elif overall < 72:
            pt += 0.05  # fringe goalies leak tired ones late

    # Gassed goalie: five-hole gets bigger.
    if ctx.fatigue < 40:
        pt += 0.10
        pb -= 0.05

    if overall < 72:
        swing = random.uniform(-0.03, 0.03)
        pb += swing
        pt -= swing

    # Crowd: loud buildings make big moments likelier; a hostile or
    # nervous barn takes a touch away from the unsupported side.
    pb *= _crowd_tier_nudge(ctx)

    pt = max(0.01, pt)
    pb = max(0.01, pb)
    pn = max(0.01, 1.0 - pt - pb)
    s = pt + pn + pb
    return _roll(pt / s, pn / s, pb / s)


# ---------------------------------------------------------------------------
# Effects: small multipliers the existing resolvers apply
# ---------------------------------------------------------------------------

def shot_effects(tier: int) -> Dict[str, float]:
    """Multipliers on the existing save-probability math."""
    if tier == BIG:
        return {"save_prob_mult": 0.80, "rebound_mult": 1.5,
                "heat": 1.0, "momentum": 0.5}
    if tier == TIRED:
        return {"save_prob_mult": 1.15, "rebound_mult": 0.8,
                "heat": 0.0, "momentum": 0.0}
    return {"save_prob_mult": 1.0, "rebound_mult": 1.0,
            "heat": 0.0, "momentum": 0.0}


def hit_effects(tier: int, hitter: Any = None) -> Dict[str, float]:
    """Adjustments to the existing hit-result weights + intensity.

    T1 refinement (2026-09-30): pass the hitter to scale the *within-tier*
    effects by bodycheck power -- injury_mult, turnover_mult and heat are
    multiplied by _bodycheck_power_mult(hitter) (rails [0.92, 1.12]), so a
    high-bodycheck hitter's connects land heavier without changing tier
    thresholds or the tier table. hitter=None returns the tier table
    unchanged (byte-identical for existing callers). penalty_mult and the
    momentum story-gate are never scaled: heavier hits don't draw more
    penalties and don't buy more stories.
    """
    if tier == BIG:
        base = {"turnover_mult": 1.6, "injury_mult": 2.2,
                "penalty_mult": 1.3, "heat": 2.0, "momentum": 1.0}
    elif tier == TIRED:
        base = {"turnover_mult": 0.6, "injury_mult": 0.5,
                "penalty_mult": 0.8, "heat": 0.0, "momentum": 0.0}
    else:
        base = {"turnover_mult": 1.0, "injury_mult": 1.0,
                "penalty_mult": 1.0, "heat": 0.0, "momentum": 0.0}
    if hitter is None:
        return base
    try:
        pm = _bodycheck_power_mult(hitter)
    except Exception:
        return base
    if pm == 1.0:
        return base
    out = dict(base)
    out["turnover_mult"] = base["turnover_mult"] * pm
    out["injury_mult"] = base["injury_mult"] * pm
    out["heat"] = base["heat"] * pm
    return out


def save_effects(tier: int) -> Dict[str, float]:
    """What a save does beyond the stop itself."""
    if tier == BIG:
        return {"freeze_mult": 1.4, "rebound_mult": 0.6,
                "heat": 1.5, "momentum": 1.0}
    if tier == TIRED:
        return {"freeze_mult": 0.7, "rebound_mult": 1.6,
                "heat": 0.0, "momentum": 0.0}
    return {"freeze_mult": 1.0, "rebound_mult": 1.0,
            "heat": 0.0, "momentum": 0.0}


# ---------------------------------------------------------------------------
# Story gating: only tell the story when it needs telling
# ---------------------------------------------------------------------------

def _key_moment(ctx: ImpactContext) -> bool:
    """Tied or one-goal game late, overtime, or playoffs."""
    if ctx.is_playoff:
        return True
    if ctx.period >= 4:
        return True
    if ctx.period == 3 and ctx.clock_seconds < 600 and abs(ctx.score_diff) <= 1:
        return True
    if ctx.period >= 2 and abs(ctx.score_diff) <= 1 and ctx.tension >= 75:
        return True
    return False


def story_worthy(tier: int, actor: Any, ctx: ImpactContext) -> bool:
    """A big moment earns the broadcast treatment only when the moment or
    the man demands it: key moments, genuine impact players in a close
    game, or a player having a special night (2+ goals / 3+ points for a
    skater, 25+ saves for a goalie). Everything else is just a good play,
    not a story."""
    if tier != BIG:
        return False
    if _key_moment(ctx):
        return True
    # Special night: the man's performance tonight demands the spotlight,
    # regardless of reputation.
    try:
        if ctx.game_goals >= 2 or ctx.game_points >= 3 or ctx.game_saves >= 25:
            return True
    except Exception:
        pass
    try:
        ov = _overall(actor)
        if ov >= 88 and abs(ctx.score_diff) <= 2:
            return True
        if ov >= 85 and abs(ctx.score_diff) <= 1:
            return True
    except Exception:
        pass
    return False


STORY_BUDGET_PER_GAME = 6


def _story_budget_left(sim: Any) -> bool:
    """Per-game cap so the broadcast doesn't cry wolf: only a handful of
    moments per game get the full momentum-swing treatment."""
    try:
        used = int(getattr(sim, "_impact_stories_told", 0) or 0)
        if used >= STORY_BUDGET_PER_GAME:
            return False
        sim._impact_stories_told = used + 1
        return True
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Momentum: additive one-step nudges (never jumps the scale)
# ---------------------------------------------------------------------------

def nudge_momentum(sim: Any, team: Any, strength: float = 1.0) -> bool:
    """Nudge the existing GameMomentum one step toward `team`.

    Additive and capped: at most one step per call, never past the ends,
    and bounded by the per-game story budget so only a handful of
    moments per game move the needle.
    Returns True if the needle moved.
    """
    try:
        if strength <= 0:
            return False
        if not _story_budget_left(sim):
            return False
        from simulation import GameMomentum
        order = list(GameMomentum)
        cur = order.index(sim.momentum)
        home_side = (team is getattr(sim, "home_team", None))
        if strength <= 0:
            return False
        # order runs heavily-home(0) .. heavily-away(6); step toward team.
        target = cur - 1 if home_side else cur + 1
        target = max(0, min(len(order) - 1, target))
        if target != cur:
            sim.momentum = order[target]
            try:
                sim.momentum_history.append(
                    (getattr(sim, "period", 1), sim.momentum))
                name = getattr(team, "team_name", "?")
                if name in getattr(sim, "team_stats", {}):
                    sim.team_stats[name]["momentum_shifts"] += 1
            except Exception:
                pass
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Context builder (kept next to the sim so call sites stay one-liners)
# ---------------------------------------------------------------------------

def build_context(sim: Any, actor: Any, team: Any) -> ImpactContext:
    """Assemble an ImpactContext from live sim state. All defensive."""
    ctx = ImpactContext()
    try:
        ctx.fatigue = float(sim.player_fatigue.get(
            getattr(actor, "id", None), 100))
    except Exception:
        pass
    # No shift clock in the engine; estimate shift length from the fatigue
    # deficit (~3 game-seconds per point lost tracks with the drain rate).
    try:
        ctx.shift_seconds = max(0.0, (100.0 - ctx.fatigue) * 3.0)
    except Exception:
        pass
    try:
        ctx.on_pk = bool(sim._is_on_penalty_kill(actor))
        ctx.on_pp = bool(sim._is_on_power_play(actor))
    except Exception:
        pass
    try:
        gs = sim._game_state_for(team)
        ctx.score_diff = int(gs.get("score_diff", 0))
        ctx.period = int(gs.get("period", 1))
        ctx.is_playoff = bool(gs.get("is_playoff", False))
        ctx.tension = float(gs.get("tension", 0) or 0)
    except Exception:
        pass
    try:
        ctx.clock_seconds = float(getattr(sim, "clock", 1200) or 1200)
    except Exception:
        pass
    try:
        ctx.coach = sim._find_head_coach(team)
    except Exception:
        pass
    try:
        instr = getattr(sim, "_coach_instructions", {})
        ctx.coach_instruction = instr.get(
            getattr(team, "team_name", None))
    except Exception:
        pass
    ctx.team = team
    try:
        ctx.scoring_mult = float(getattr(sim, "scoring_multiplier", 1.0) or 1.0)
    except Exception:
        pass
    # Crowd state from the sim (home perspective), flipped to the actor's
    # team's perspective: + means the building is behind them.
    try:
        from arena_atmosphere import actor_crowd_mood as _actor_mood
        ctx.crowd_energy = float(getattr(sim, "_crowd_energy", 50.0) or 50.0)
        ctx.crowd_mood = _actor_mood(getattr(sim, "home_team", None), team,
                                     float(getattr(sim, "_crowd_mood", 0.0) or 0.0))
    except Exception:
        pass
    # Special-night counters from this game's stats (all defensive).
    try:
        gs = getattr(sim, "game_stats", {}) or {}
        st = gs.get(getattr(actor, "id", None), {}) or {}
        ctx.game_goals = int(st.get("g", 0) or 0)
        ctx.game_points = int(st.get("g", 0) or 0) + int(st.get("a", 0) or 0)
        ctx.game_saves = int(st.get("saves", 0) or 0)
    except Exception:
        pass
    return ctx
