# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Arena atmosphere: the crowd as a real, two-sided factor.

Design (Muck, 2026-09-28): the crowd must fit into the engine's scaling of all
factors -- it can be positive OR negative depending on team and circumstances.
Big games matter, home advantage matters, but a nervous or toxic building
tightens grips just like real life.

Two channels, both cheap:
  1. energy 0-100  -- how loud/engaged the building is. Feeds the existing
     tension/intensity channel (a loud barn raises everyone's pulse).
  2. mood -100..+100 (home perspective) -- is the building behind the home
     team (+) or nervous/toxic (-)? Scales finishing asymmetrically:
     a jacked crowd lifts the home side; a booing one drags it; a loud
     hostile barn rattles *young* visitors while veterans shrug.

Crowd is live: goals swing energy and mood during the game, so a 3rd-period
comeback bid in a playoff barn actually feels different from a flat Tuesday
in October.

Integration points:
  - pregame_crowd(...)        -> called once per game, pre-sim.
  - live_crowd_update(state, ...) -> called on goals in both sims.
  - crowd_effects(...)        -> (home_mult, away_mult) finishing multipliers,
                                 both in [0.97, 1.03]. Feed through the
                                 existing team_boost channel in the quick sim,
                                 and as ctx fields in the deep sim.
Everything is defensive: missing teams/ledger/rosters degrade to a quiet
neutral building, never raise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Pregame crowd
# ---------------------------------------------------------------------------

def pregame_crowd(home_team: Any, away_team: Any, ledger: Any = None,
                  is_playoff: bool = False, series_game: int = 1,
                  elimination_game: bool = False,
                  milestone_home: bool = False,
                  ceremony: bool = False,
                  outdoor: bool = False,
                  rivalry_heat: float = 0.0,
                  fan_sentiment: Optional[float] = None,
                  fan_fav_names: Optional[List[str]] = None,
                  hated_returnee_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Compute the crowd state at puck drop.

    energy: 0-100 loudness/engagement.
    mood:   -100..+100 from the HOME team's perspective (+ = behind them).
    drivers: short human labels for presentation ("Playoff Game 5", ...).
    big_game: True when the night genuinely matters (drives hype headlines).

    rivalry_heat: 0-100 bad blood between the clubs (reputation system).
    Grudge games are louder before puck drop -- this is the atmosphere
    half of the rivalry loop (the engine half reads heat for hits/fights).

    fan_sentiment: 0-100 persistent fanbase mood (fan_sentiment module).
    A happy fanbase is louder and more behind its team; a disgruntled one
    makes the building nervous. None = skip (legacy callers unaffected).

    fan_fav_names: home-team fan favourites dressing tonight -- the
    building buzzes for its heroes.

    hated_returnee_names: away players the home fans haven't forgiven
    (simmering fan hate, reputation system) -- a hostile buzz.
    """
    drivers: List[str] = []
    energy = 38.0
    mood = 30.0          # a home crowd starts wanting to cheer
    big_game = False

    home_name = _team_name(home_team)
    away_name = _team_name(away_team)

    # --- memory: the ledger knows this matchup's story ---------------------
    mem_weight = 0.0
    if ledger is not None and home_name and away_name:
        try:
            mem_weight = float(ledger.memory_weight(home_name, away_name) or 0.0)
        except Exception:
            mem_weight = 0.0
    if mem_weight >= 70.0:
        energy += 12.0
        mood += 8.0
        drivers.append("Bad blood in this building")
        big_game = True
    elif mem_weight >= 40.0:
        energy += 6.0
        mood += 4.0
        drivers.append("History between these two")

    # --- rivalry heat: the grudge-match boost --------------------------------
    # The ledger path above reads narrative memory; this reads the rivalry
    # system's intensity (playoff wars, declared hate, regional bad blood).
    # They stack on energy but share one driver label.
    try:
        _rh = float(rivalry_heat or 0.0)
    except Exception:
        _rh = 0.0
    if _rh >= 65.0:
        energy += 10.0
        mood += 6.0
        if "Bad blood in this building" not in drivers:
            drivers.append("Bad blood in this building")
        big_game = True
    elif _rh >= 35.0:
        energy += 5.0
        mood += 3.0
        drivers.append("Heated rivalry")

    # --- playoff ramp ------------------------------------------------------
    if is_playoff:
        big_game = True
        energy += 10.0
        mood += 12.0
        drivers.append(f"Playoff Game {max(1, series_game)}")
        energy += min(10.0, max(0, series_game - 1) * 1.5)   # deeper = louder
        if elimination_game:
            energy += 8.0
            mood += 8.0
            drivers.append("Elimination game")
        if series_game >= 7:
            energy += 6.0
            mood += 6.0
            drivers.append("Game 7")

    # --- special nights ----------------------------------------------------
    if milestone_home:
        energy += 6.0
        mood += 10.0
        drivers.append("Milestone night")
    if ceremony:
        energy += 8.0
        mood += 10.0
        drivers.append("Pregame ceremony")

    # --- outdoor games: the loudest night of the regular season --------------
    if outdoor:
        energy += 10.0
        mood += 6.0
        drivers.append("Outdoor game")
        big_game = True

    # --- home-team form: a losing skid makes the building nervous -----------
    skid = _home_skid(home_team)
    if skid >= 4:
        mood -= 18.0
        drivers.append("Restless after %d straight losses" % skid)
    elif skid == 3:
        mood -= 8.0

    # --- home win streak: the building believes (D34 mirror of the skid) -----
    streak = _home_streak(home_team)
    if streak >= 4:
        energy += 8.0
        mood += 10.0
        drivers.append("Winners of %d straight" % streak)
    elif streak == 3:
        energy += 4.0
        mood += 5.0

    # --- persistent fan sentiment: the slow stock beneath the night (D34) ----
    # A fanbase that loves its team is louder and more forgiving; one that
    # has turned makes the building nervous. 60 = content baseline.
    if fan_sentiment is not None:
        try:
            _fs = float(fan_sentiment)
            mood += (_fs - 60.0) * 0.45
            energy += (_fs - 60.0) * 0.25
            if _fs >= 80.0:
                drivers.append("The faithful are buzzing")
            elif _fs <= 35.0:
                drivers.append("A restless, edgy building")
        except Exception:
            pass

    # --- fan favourites: the building buzzes for its heroes (D34) ------------
    try:
        _favs = [str(n) for n in (fan_fav_names or []) if n][:3]
    except Exception:
        _favs = []
    if _favs:
        energy += 4.0 + 2.0 * min(3, len(_favs))
        mood += 4.0
        drivers.append("Buzzing for %s" % _favs[0] +
                       (" (+%d more)" % (len(_favs) - 1) if len(_favs) > 1 else ""))

    # --- simmering hate: still not forgiven in this barn (D39) ----------------
    # Smaller than the first homecoming (reputation_system): the story has
    # cooled but the booing still lifts the building's edge.
    try:
        _hated = [str(n) for n in (hated_returnee_names or []) if n][:3]
    except Exception:
        _hated = []
    if _hated:
        energy += 6.0
        mood += 3.0
        drivers.append("Still not forgiven: %s" % _hated[0] +
                       (" (+%d more)" % (len(_hated) - 1) if len(_hated) > 1 else ""))

    energy = max(8.0, min(97.0, energy))
    mood = max(-90.0, min(95.0, mood))
    return {
        "energy": energy,
        "mood": mood,          # home perspective
        "drivers": drivers,
        "big_game": big_game,
    }


# ---------------------------------------------------------------------------
# Live crowd: call on every goal (both sims)
# ---------------------------------------------------------------------------

def live_crowd_update(state: Dict[str, Any], scorer_is_home: bool,
                      home_score: int, away_score: int,
                      period: int = 1,
                      scorer_is_fan_favourite: bool = False) -> None:
    """Mutate a pregame_crowd dict in place after a goal.

    Real-life shape: home goals erupt the building (bigger when they cut into
    a deficit -- the comeback lift), away goals quiet it and make it nervous,
    especially when the visitors take a late lead.

    scorer_is_fan_favourite: a goal from a fan favourite gets the extra
    roar -- the building's hero scores.
    """
    try:
        energy = float(state.get("energy", 50.0))
        mood = float(state.get("mood", 30.0))
    except Exception:
        return

    if scorer_is_home:
        was_down = home_score < away_score + 1  # scored while trailing/tied
        deficit_before = (away_score - home_score) + 1
        energy += 7.0
        mood += 10.0
        if scorer_is_fan_favourite:
            # the building's hero scores: the extra roar
            energy += 4.0
            mood += 5.0
        if was_down and deficit_before >= 2:
            # cutting into a multi-goal deficit: the building erupts
            energy += 5.0
            mood += 8.0
    else:
        energy -= 3.0
        mood -= 8.0
        if period >= 3 and away_score > home_score:
            # visitors take a late lead: nervous building
            mood -= 14.0
            energy += 4.0     # nervous noise is still noise

    state["energy"] = max(5.0, min(100.0, energy))
    state["mood"] = max(-95.0, min(100.0, mood))


# ---------------------------------------------------------------------------
# On-ice effects
# ---------------------------------------------------------------------------

def crowd_effects(energy: float, mood: float,
                  away_avg_age: Optional[float] = None) -> Tuple[float, float]:
    """(home_mult, away_mult): finishing multipliers from the crowd.

    home_mult: 1 + 0.02 * (energy/100) * (mood/100).
        Loud + behind you  -> up to +2%.  Loud + toxic/nervous -> down to -2%.
    away_mult: hostile barns rattle YOUNG visitors; veterans shrug.
        1 - 0.02 * hostile * youth, where hostile = energy * max(0,mood) / 1e4
        and youth = 1 for avg age <= 26, 0 for >= 28.5, linear between.
    Both clamped to [0.97, 1.03] -- the crowd is a factor, never the game.
    """
    try:
        e = max(0.0, min(100.0, float(energy))) / 100.0
        m = max(-1.0, min(1.0, float(mood) / 100.0))
    except Exception:
        return (1.0, 1.0)

    home_mult = 1.0 + 0.02 * e * m

    hostile = e * max(0.0, m)
    youth = 0.5
    try:
        if away_avg_age is not None:
            a = float(away_avg_age)
            youth = max(0.0, min(1.0, (28.5 - a) / 2.5))
    except Exception:
        pass
    away_mult = 1.0 - 0.02 * hostile * youth

    home_mult = max(0.97, min(1.03, home_mult))
    away_mult = max(0.97, min(1.03, away_mult))
    return (home_mult, away_mult)


def crowd_hype_for_tension(energy: float, mood: float) -> float:
    """Map crowd state onto the 0-100 hype scale the tension engine takes.

    Loud buildings raise everyone's pulse regardless of mood -- even a
    nervous barn is intense. Baseline ~50 for a normal night.
    """
    try:
        e = max(0.0, min(100.0, float(energy)))
        m = abs(max(-100.0, min(100.0, float(mood))))
    except Exception:
        return 50.0
    return max(0.0, min(100.0, 30.0 + 0.55 * e + 0.15 * m))


# ---------------------------------------------------------------------------
# Helpers (all defensive)
# ---------------------------------------------------------------------------

def _team_name(team: Any) -> str:
    try:
        return str(getattr(team, "team_name", "") or "")
    except Exception:
        return ""


def _home_skid(home_team: Any) -> int:
    """Consecutive losses heading into tonight, 0 when unknown."""
    try:
        results = getattr(home_team, "recent_results", None)
        if not results:
            return 0
        skid = 0
        for r in results:
            r = str(r).upper()
            if r.startswith("L") or "LOSS" in r:
                skid += 1
            else:
                break
        return skid
    except Exception:
        return 0


def _home_streak(home_team: Any) -> int:
    """Consecutive wins heading into tonight, 0 when unknown (D34)."""
    try:
        results = getattr(home_team, "recent_results", None)
        if not results:
            return 0
        streak = 0
        for r in results:
            r = str(r).upper()
            if r.startswith("W") or "WIN" in r:
                streak += 1
            else:
                break
        return streak
    except Exception:
        return 0


def roster_avg_age(team: Any) -> Optional[float]:
    """Average roster age; None when the roster isn't readable."""
    try:
        roster = getattr(team, "roster", None) or []
        ages = [float(getattr(p, "age", 0) or 0) for p in roster]
        ages = [a for a in ages if 16.0 < a < 50.0]
        if not ages:
            return None
        return sum(ages) / len(ages)
    except Exception:
        return None


def actor_crowd_mood(home_team: Any, actor_team: Any, home_mood: float) -> float:
    """Mood from the actor's team's perspective (+ = crowd behind them)."""
    try:
        if _team_name(actor_team) and _team_name(actor_team) == _team_name(home_team):
            return float(home_mood)
        return -float(home_mood)
    except Exception:
        return 0.0
