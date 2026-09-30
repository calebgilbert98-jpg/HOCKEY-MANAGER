"""OT drama: live in-game levers for overtime drama, shared pure module.

Chris's five factors -- game intensity, player/coach morale and situational
state, rivalry heat, grudge matches, atmospheric/fan factors -- drive three
LIVE levers that operate inside the game on every sim path (lightweight
day-advance, AdvancedGameSim, watched GameSim):

1. Pulled-goalie timing / 6v5 aggression: in high-drama games the trailing
   coach pulls earlier (extra seconds on the shared goalie_pull window).
   More 6v5 time means more late tying goals AND more empty-netters -- the
   mechanism is honest, both outcomes are real goals.
2. OT 3v3 matchup choices: the coach's personnel/matchup acumen
   (tactical_knowledge, match_preparation, attacking_coaching) plus the
   room/crowd edge tilt OT finishing a touch, bounded small.
3. Shootout composure: the shared player_traits shootout core already
   resolves shooter skill/traits vs the goalie; shootout_edge() carries the
   room/crowd context nudge on every path that reaches a shootout.

There is deliberately NO synthetic post-regulation equalizer: games reach
OT because a real 6v5 goal was scored, never because a roll said so.

Pure reads only: this module never writes to teams, the league, or the
standings, and never raises -- missing inputs degrade to quiet neutrals
(same contract as narrative_ledger.matchup_narrative).

Additive by design: callers pass the context into existing resolution code
via optional parameters with behavior-preserving defaults. Regulation
scoring is never touched directly -- the levers move timing, personnel
edges, and the honest 6v5 segment, not the GPG equilibrium.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# §8 tuning constants -- every knob lives here, in one place.
# ---------------------------------------------------------------------------
OT_MULT_CLAMP = (0.85, 1.35)      # max drama swing on OT likelihood
RIVALRY_OT_WEIGHT = 0.25          # heat/100 * this added to ot_mult
INTENSITY_OT_WEIGHT = 0.10        # league tension contribution
GRUDGE_OT_BONUS = 0.15            # flat bonus for grudge matches
GRUDGE_HOME_EDGE = 0.03           # home pride edge in grudge games
WIN_EDGE_CLAMP = (-0.15, 0.15)    # max home OT win-probability edge
MORALE_WIN_WEIGHT = 0.10          # per 100 morale-diff points
SITUATION_WIN_WEIGHT = 0.50       # per 1.0 xg_mult diff (~+/-0.08 in practice)
CROWD_WIN_WEIGHT = 0.06           # per +/-50 energy from neutral
SHOOTOUT_EDGE_MAX = 0.06          # max shootout probability nudge
SHOOTOUT_EDGE_DAMP = 0.40         # shootouts are coin flips; edge matters less

# Lever 1: pulled-goalie aggression.
PULL_AGGRESSION_MAX_SECS = 45.0   # extra pull-window seconds at full drama
# Lever 2: OT 3v3 matchup tilt.
MATCHUP_TILT_CLAMP = 0.05         # max |tilt| on OT goal probability
MATCHUP_EDGE_FLOW = 0.25          # home_win_edge flows through at 1/4 strength
MATCHUP_COACH_WEIGHT = 0.04       # per 100 tactical-acumen-gap points
# Lever 3 (lightweight path): the end-game 6v5 segment, modeled from the
# same pull decision the shift engines execute live. Real NHL: ~12-15% of
# goalie pulls yield the tying goal, ~25-30% end in an empty-netter.
SIX_ON_FIVE_BASE_SECS = 100.0     # average coach's down-1 pull window
TIE_RATE_PER_MIN = 0.10           # 6v5 tying-goal rate
EN_RATE_PER_MIN = 0.20            # empty-netter-against rate


def _avg_morale(team: Any) -> Any:
    """Mean player morale (native 1-100, 70 neutral). None if unreadable."""
    try:
        roster = getattr(team, "roster", None) or []
        vals = [float(getattr(p, "morale", 70)) for p in roster
                if getattr(p, "morale", None) is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)
    except Exception:
        return None


def ot_context(home_team: Any, away_team: Any, league: Any = None,
               atmosphere: Any = None, is_playoff: bool = False) -> Dict[str, Any]:
    """Aggregate the five drama factors into OT likelihood + home edge.

    Returns {"ot_mult", "home_win_edge", "drama01", "drivers"}.
    drama01 is ot_mult normalized to 0..1 across OT_MULT_CLAMP (neutral 0.3).
    drivers are human-readable strings for news/narrative copy.
    Never raises.
    """
    out: Dict[str, Any] = {
        "ot_mult": 1.0,
        "home_win_edge": 0.0,
        "drama01": 0.3,
        "drivers": [],
    }
    try:
        ot_mult = 1.0
        edge = 0.0
        drivers: List[str] = []

        # 1. League intensity (season tension; playoff series intensity later).
        try:
            from narrative_ledger import active_ledger
            from season_intensity import season_intensity
            _inten = season_intensity(active_ledger()) or {}
            _iv = float(_inten.get("value", 0.0) or 0.0)
            ot_mult += (_iv / 100.0) * INTENSITY_OT_WEIGHT
            if _iv >= 65:
                drivers.append("High league tension")
        except Exception:
            pass

        # 2+3. Rivalry heat + grudge memory (read-only via narrative ledger).
        try:
            from narrative_ledger import matchup_narrative
            _mn = matchup_narrative(home_team, away_team, league=league) or {}
            _heat = float(_mn.get("rivalry_heat", 0.0) or 0.0)
            ot_mult += (_heat / 100.0) * RIVALRY_OT_WEIGHT
            if _heat >= 65:
                drivers.append("Bad blood")
            elif _heat >= 35:
                drivers.append("Simmering rivalry")
            if _mn.get("grudge"):
                ot_mult += GRUDGE_OT_BONUS
                edge += GRUDGE_HOME_EDGE
                drivers.append("Grudge match")
        except Exception:
            pass

        # 4. Player morale: the hotter room wants it more.
        try:
            _mh = _avg_morale(home_team)
            _ma = _avg_morale(away_team)
            if _mh is not None and _ma is not None:
                edge += ((_mh - _ma) / 100.0) * MORALE_WIN_WEIGHT
                if abs(_mh - _ma) >= 12:
                    drivers.append("Hot room" if _mh > _ma else "Cold room")
        except Exception:
            pass

        # 5. Situational state: room/bench/hunger edge per side.
        try:
            from reputation_system import situations_factor
            _sh = situations_factor(home_team) or {}
            _sa = situations_factor(away_team) or {}
            _xh = float(_sh.get("xg_mult", 1.0) or 1.0)
            _xa = float(_sa.get("xg_mult", 1.0) or 1.0)
            edge += (_xh - _xa) * SITUATION_WIN_WEIGHT
        except Exception:
            pass

        # 6. Atmosphere: a jacked building lifts the home side.
        try:
            _energy = None
            if isinstance(atmosphere, dict):
                _energy = atmosphere.get("energy")
            if _energy is not None:
                _energy = float(_energy)
                edge += ((_energy - 50.0) / 50.0) * CROWD_WIN_WEIGHT
                if _energy >= 80:
                    drivers.append("Roaring crowd")
        except Exception:
            pass

        ot_mult = max(OT_MULT_CLAMP[0], min(OT_MULT_CLAMP[1], ot_mult))
        edge = max(WIN_EDGE_CLAMP[0], min(WIN_EDGE_CLAMP[1], edge))
        out["ot_mult"] = ot_mult
        out["home_win_edge"] = edge
        out["drama01"] = (ot_mult - OT_MULT_CLAMP[0]) / (OT_MULT_CLAMP[1] - OT_MULT_CLAMP[0])
        out["drivers"] = drivers
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Lever 1: pulled-goalie timing / 6v5 aggression.
# ---------------------------------------------------------------------------
def pull_aggression_secs(ctx: Optional[Dict[str, Any]]) -> float:
    """Extra seconds on the goalie-pull window from game drama.

    Neutral games (drama01 == 0.3) pull on the coach's window exactly;
    max-drama games pull up to PULL_AGGRESSION_MAX_SECS earlier. Callers add
    this to both down-1 and down-2 windows from goalie_pull.pull_windows.
    Pure; never raises.
    """
    try:
        _d01 = float((ctx or {}).get("drama01", 0.3) or 0.3)
        _secs = (_d01 - 0.3) / 0.7 * PULL_AGGRESSION_MAX_SECS
        return max(0.0, min(PULL_AGGRESSION_MAX_SECS, _secs))
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Lever 2: OT 3v3 matchup choices.
# ---------------------------------------------------------------------------
def _coach_matchup_acumen(coach: Any) -> Optional[float]:
    """3v3 personnel/matchup acumen from coach attributes (1-100 scale).

    None when the coach is unreadable -- the caller degrades to the
    context edge alone.
    """
    try:
        if coach is None:
            return None
        _vals = []
        for _n in ("tactical_knowledge", "match_preparation",
                   "attacking_coaching"):
            _v = getattr(coach, _n, None)
            if _v is not None:
                _vals.append(float(_v))
        if not _vals:
            return None
        return sum(_vals) / len(_vals)
    except Exception:
        return None


def ot_matchup_tilt(ctx: Optional[Dict[str, Any]],
                    home_coach: Any = None,
                    away_coach: Any = None) -> float:
    """Signed OT goal-probability tilt, home-positive, |tilt| <= 0.05.

    The room/crowd/situational edge (home_win_edge) flows through at
    quarter strength -- that's the matchup manifesting on the ice -- plus
    the head-coach 3v3 acumen gap. Shift engines multiply the attacking
    team's OT goal chance by (1 + tilt) / (1 - tilt); the lightweight path
    adds it to the OT coin flip. Pure; never raises.
    """
    try:
        _ctx = ctx or {}
        _tilt = float(_ctx.get("home_win_edge", 0.0) or 0.0) * MATCHUP_EDGE_FLOW
        _ha = _coach_matchup_acumen(home_coach)
        _aa = _coach_matchup_acumen(away_coach)
        if _ha is not None and _aa is not None:
            _tilt += ((_ha - _aa) / 100.0) * MATCHUP_COACH_WEIGHT
        return max(-MATCHUP_TILT_CLAMP, min(MATCHUP_TILT_CLAMP, _tilt))
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Lever 3 (lightweight path): the end-game 6v5 segment.
# ---------------------------------------------------------------------------
def late_six_on_five(ctx: Optional[Dict[str, Any]],
                     trailing_team_is_home: bool = False,
                     rng: Any = None) -> Tuple[str, float]:
    """Model the trailing coach's goalie pull on the lightweight path.

    The shift engines execute this live (pull window + 6v5 shifts +
    empty-net chances); the day-advance path has no shifts, so it resolves
    the same decision probabilistically from the same inputs: pull time =
    the average coach's window plus drama aggression, then competing
    exponential rates for the tying goal vs the empty-netter.

    Returns (outcome, pull_secs) where outcome is "tie", "empty_net", or
    "none". Call ONLY when regulation ends exactly 1 goal apart -- a
    down-2 pull can't change the result, so there's nothing to resolve.
    Both scoring outcomes are real goals. Pure; never raises.
    """
    try:
        import math
        import random as _random
        _rng = rng if rng is not None else _random
        _pull_secs = SIX_ON_FIVE_BASE_SECS + pull_aggression_secs(ctx)
        _mins = _pull_secs / 60.0
        _p_tie = 1.0 - math.exp(-TIE_RATE_PER_MIN * _mins)
        _p_en = 1.0 - math.exp(-EN_RATE_PER_MIN * _mins)
        _r = float(_rng.random())
        if _r < _p_tie:
            return "tie", _pull_secs
        if _r < _p_tie + (1.0 - _p_tie) * _p_en:
            return "empty_net", _pull_secs
        return "none", _pull_secs
    except Exception:
        return "none", 0.0


# ---------------------------------------------------------------------------
# Lever 3 (shootouts): context nudge on the shared shootout core.
# ---------------------------------------------------------------------------
def shootout_edge(ctx: Optional[Dict[str, Any]],
                  shooter_is_home: bool = False) -> float:
    """Small probability nudge for the shared shootout core.

    Damped from home_win_edge (shootouts are coin flips; edges matter
    less), clamped to +/-SHOOTOUT_EDGE_MAX. Positive favors the shooter.
    The composure itself lives in player_traits.resolve_shootout_attempt
    (clutch shooters elevate, big-game goalies elevate). Never raises.
    """
    try:
        _e = float((ctx or {}).get("home_win_edge", 0.0))
        _nudge = _e * SHOOTOUT_EDGE_DAMP
        _nudge = max(-SHOOTOUT_EDGE_MAX, min(SHOOTOUT_EDGE_MAX, _nudge))
        return _nudge if shooter_is_home else -_nudge
    except Exception:
        return 0.0
