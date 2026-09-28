"""Real shift engine for Puck Dynasty.

Replaces the clock-math line rotation (`(clock // 45) % 4 + 1`) with actual
shift state: who is on the ice, when their shift started, and conditional
change logic (whistles, on-the-fly, line matching, fatigue).

Design doc: docs/SHIFT_ENGINE_DESIGN.md

Engine boundary: this changes WHO is on the ice and WHEN they change. It does
NOT touch goal probabilities, shot math, save logic, tactics multipliers, or
fatigue drain rates.
"""

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Shift length targets (seconds of game clock)
TARGET_SHIFT = 30        # ideal even-strength shift
MIN_SHIFT = 20           # don't change before this (unless whistle)
MAX_SHIFT_LIVE = 40      # on-the-fly change by this age
HARD_CAP = 50            # no skater out longer without a whistle
EXTENDED_OZ = 45         # sustained OZ pressure extends to ~45s
ST_SHIFT = 45            # PP/PK unit rotation rhythm


@dataclass
class ShiftState:
    """Per-team shift state for one game."""
    f_line: int = 1              # current forward line (1-4)
    d_pair: int = 1              # current D pair (1-3)
    f_shift_start: float = 0.0   # clock value when F shift started
    d_shift_start: float = 0.0   # clock value when D shift started
    pp_unit: int = 1             # current PP unit (1-2)
    pk_unit: int = 1             # current PK unit (1-2)
    st_shift_start: float = 0.0  # clock when special-teams shift started
    shift_lengths: List[float] = field(default_factory=list)  # completed, for coach's corner
    last_change_was_wholesale: bool = False

    def f_age(self, clock: float) -> float:
        return self.f_shift_start - clock  # clock counts DOWN

    def d_age(self, clock: float) -> float:
        return self.d_shift_start - clock

    def st_age(self, clock: float) -> float:
        return self.st_shift_start - clock

    def record_shift(self, length: float):
        if length > 0:
            self.shift_lengths.append(length)


def get_shift_state(sim: Any, team: Any) -> ShiftState:
    """Get (or create) the shift state for a team on this sim."""
    states = getattr(sim, "_shift_states", None)
    if states is None:
        sim._shift_states = states = {}
    key = getattr(team, "team_name", id(team))
    st = states.get(key)
    period = getattr(sim, "period", 1)
    if st is None:
        st = ShiftState()
        # Seed from clock so the opening faceoff isn't always line 1
        clock = getattr(sim, "clock", 1200)
        st.f_line = (int(clock) // 45) % 4 + 1
        st.d_pair = (int(clock) // 60) % 3 + 1
        st.f_shift_start = clock
        st.d_shift_start = clock
        st.st_shift_start = clock
        st._period = period
        states[key] = st
    # Period boundary: the clock resets to 1200 each period. A shift can't
    # span the intermission — reset the shift clocks so ages stay sane.
    if getattr(st, "_period", period) != period:
        clock = getattr(sim, "clock", 1200)
        # Record the (truncated) shift that ended at the horn
        try:
            st.record_shift(st.f_shift_start - 0)  # clock hit 0; length unknown, skip
        except Exception:
            pass
        st.f_shift_start = clock
        st.d_shift_start = clock
        st.st_shift_start = clock
        st._period = period
    return st


def _next_in_rotation(current: int, max_n: int) -> int:
    return (current % max_n) + 1


def _avg_fatigue(sim: Any, players: List[Any]) -> float:
    """Average fatigue (0-100) of the given players."""
    if not players:
        return 100.0
    fatigue = getattr(sim, "player_fatigue", {})
    total = sum(fatigue.get(getattr(p, "id", None), 100) for p in players)
    return total / max(1, len(players))


def should_change_on_fly(sim: Any, team: Any, st: ShiftState) -> Tuple[bool, bool]:
    """Check if forwards and/or D should change on the fly during live play.

    Returns (change_forwards, change_defense).
    Conditions: shift age > ~30s AND puck in neutral/defensive zone AND
    no scoring chance in progress. F and D are independent (staggered).
    """
    clock = getattr(sim, "clock", 0)
    f_age = st.f_age(clock)
    d_age = st.d_age(clock)

    # Hard cap: must change (handled by caller forcing a whistle-side change,
    # but flag it here so the tick loop knows)
    # Puck location: only change on the fly when the puck is not threatening.
    # Use the sim's zone/puck state.
    puck_safe = _puck_is_safe(sim, team)
    scoring_chance = getattr(sim, "_scoring_chance_in_progress", False)

    change_f = False
    change_d = False

    # Forwards: change on the fly when the shift is ripe and the puck is safe
    # (High probability at 28s+ so the 20-40s window holds despite 8-20s
    # tick granularity; deterministic by 38s.)
    if f_age >= 28 and puck_safe and not scoring_chance:
        if f_age >= 38 or random.random() < 0.75:
            change_f = True

    # Defense: independent timer, often stays out through a forward change
    # (staggered). D change slightly later on average.
    if d_age >= 34 and puck_safe and not scoring_chance:
        if d_age >= 44 or random.random() < 0.65:
            change_d = True

    # Sustained OZ pressure extends the shift: if this team's forwards have
    # been grinding in the offensive zone, keep them out to ~45s.
    if _sustained_oz_pressure(sim, team):
        if f_age < EXTENDED_OZ:
            change_f = False

    return change_f, change_d


def _puck_is_safe(sim: Any, team: Any) -> bool:
    """Is the puck in a safe spot for an on-the-fly change?

    Safe: neutral zone, OR this team has possession in the offensive zone
    (attacking teams change on the fly during sustained pressure).
    Not safe: puck in this team's defensive zone (defending, can't change).
    """
    try:
        from simulation import Zone
        zone = getattr(sim, "current_zone", None)
        possession = getattr(sim, "possession_team", None)
        if zone == Zone.NEUTRAL_ZONE:
            return True
        # Attacking in the OZ: safe to change (that's when OZ shifts extend)
        if possession is team:
            return True
        # Defending in our DZ: not safe
        return zone != Zone.DEFENSIVE_ZONE
    except Exception:
        return True


def _sustained_oz_pressure(sim: Any, team: Any) -> bool:
    """Has this team been sustaining offensive-zone pressure?"""
    try:
        zone_time = getattr(sim, "zone_time", 0)
        from simulation import Zone
        return (getattr(sim, "current_zone", None) == Zone.OFFENSIVE_ZONE
                and getattr(sim, "possession_team", None) is team
                and zone_time > 20)
    except Exception:
        return False


def change_lines(sim: Any, team: Any, st: ShiftState,
                 change_f: bool = True, change_d: bool = True,
                 reason: str = "rotation") -> Dict[str, Any]:
    """Execute a line change. Returns info about what changed."""
    clock = getattr(sim, "clock", 0)
    result = {"forwards": False, "defense": False, "wholesale": False}

    if change_f:
        st.record_shift(st.f_age(clock))
        st.f_line = _next_in_rotation(st.f_line, 4)
        st.f_shift_start = clock
        result["forwards"] = True

    if change_d:
        st.record_shift(st.d_age(clock))
        st.d_pair = _next_in_rotation(st.d_pair, 3)
        st.d_shift_start = clock
        result["defense"] = True

    # Wholesale = 3+ skaters (full line + at least one D, or full unit)
    # For now: a change where both F and D swap is wholesale.
    result["wholesale"] = change_f and change_d
    st.last_change_was_wholesale = result["wholesale"]
    return result


def stoppage_change(sim: Any, team: Any, st: ShiftState,
                    is_home: bool, away_line: Optional[int] = None,
                    zone: str = "neutral", icing_frozen: bool = False) -> Dict[str, Any]:
    """Handle a line change at a stoppage (faceoff).

    - Icing: frozen team cannot change.
    - Away team declares first (rolls rotation); home team matches.
    - OZ draw: coach may keep the unit out (fresh legs for the draw).
    - DZ draw with tired unit: must change.
    """
    if icing_frozen:
        return {"forwards": False, "defense": False, "wholesale": False,
                "reason": "icing_frozen"}

    clock = getattr(sim, "clock", 0)
    result = {"forwards": False, "defense": False, "wholesale": False,
              "reason": "stoppage"}

    # Check if the current unit is tired (avg fatigue < 70)
    # For now, use shift age as a proxy (fatigue integration comes from the sim)
    f_age = st.f_age(clock)
    d_age = st.d_age(clock)
    f_tired = f_age > 40
    d_tired = d_age > 45

    # Hard cap: no shift beyond 60s, even at a stoppage. This overrides
    # the OZ-keep and matching logic below.
    must_change_f = f_age >= 50
    must_change_d = d_age >= 50

    # OZ draw: keep the unit out if they're fresh (coach's choice).
    # (But not if they're at the hard cap.)
    if zone == "offensive" and not f_tired and not must_change_f and random.random() < 0.6:
        return {"forwards": False, "defense": False, "wholesale": False,
                "reason": "oz_keep"}

    # DZ draw with tired unit: must change
    must_change_f = must_change_f or (zone == "defensive" and f_tired)
    must_change_d = must_change_d or (zone == "defensive" and d_tired)

    # Line matching (home team with last change)
    target_line = None
    target_pair = None
    if is_home and away_line is not None:
        target_line, target_pair = _matching_response(away_line, sim, team)
    elif not is_home:
        # Away team rolls rotation (no last change on the road)
        pass

    # Score-state layer (existing behavior, preserved):
    # trailing by 2+ -> shorten to top six; leading by 2+ -> bottom six.
    # This overrides matching.
    goal_diff = _goal_diff_for(sim, team, is_home)
    if goal_diff <= -2:
        target_line = 1 if random.random() < 0.5 else 2
        result["reason"] = "chase_game"
    elif goal_diff >= 2:
        target_line = 3 if random.random() < 0.5 else 4
        result["reason"] = "protect_lead"

    # Decide changes
    change_f = must_change_f or (target_line is not None and target_line != st.f_line)
    change_d = must_change_d or (target_pair is not None and target_pair != st.d_pair)

    # Default: change at a whistle if the shift is ripe (>25s) or tired
    if not change_f and (f_age > 25 or f_tired):
        if random.random() < 0.7:
            change_f = True
    if not change_d and (d_age > 30 or d_tired):
        if random.random() < 0.6:
            change_d = True

    if target_line is not None and change_f:
        st.record_shift(st.f_age(clock))
        st.f_line = target_line
        st.f_shift_start = clock
        result["forwards"] = True
    elif change_f:
        info = change_lines(sim, team, st, change_f=True, change_d=False,
                            reason=result["reason"])
        result["forwards"] = info["forwards"]

    if target_pair is not None and change_d:
        st.record_shift(st.d_age(clock))
        st.d_pair = target_pair
        st.d_shift_start = clock
        result["defense"] = True
    elif change_d:
        info = change_lines(sim, team, st, change_f=False, change_d=True,
                            reason=result["reason"])
        result["defense"] = info["defense"]

    result["wholesale"] = result["forwards"] and result["defense"]
    return result


def _matching_response(away_line: int, sim: Any, home_team: Any) -> Tuple[int, int]:
    """Home team's line-matching response to the away team's declared line.

    The user can override the automatic response per line via the lines
    screen "Match to line" dropdowns (Team.line_matchups): the first of my
    lines/pairs targeting the opponent's declared line gets the call, with
    F and D chosen independently. Unset entries fall back to the auto
    behavior below:

    vs 1st line -> checking line (3rd) + top D pair (1st)
    vs 4th line -> 1st line (exploit the mismatch)
    vs 2nd/3rd -> roll (keep current, signaled by returning current)
    """
    # We need the home team's current state to "roll" — get it
    st = get_shift_state(sim, home_team)
    if away_line == 1:
        auto_f, auto_d = 3, 1
    elif away_line == 4:
        auto_f, auto_d = 1, 1  # top pair with the top line to exploit
    else:
        auto_f, auto_d = st.f_line, st.d_pair  # roll

    # User-set matchup preferences (1-4 opponent forward line, or None).
    prefs = getattr(home_team, "line_matchups", None) or {}
    f_prefs = list(prefs.get("F") or [])[:4] + [None] * 4
    d_prefs = list(prefs.get("D") or [])[:3] + [None] * 3
    want_f = next((i + 1 for i, want in enumerate(f_prefs[:4])
                   if want == away_line), None)
    want_d = next((i + 1 for i, want in enumerate(d_prefs[:3])
                   if want == away_line), None)
    return (want_f or auto_f, want_d or auto_d)


def _goal_diff_for(sim: Any, team: Any, is_home: bool) -> int:
    """Goal differential from this team's perspective."""
    hs = getattr(sim, "home_score", 0)
    aws = getattr(sim, "away_score", 0)
    return (hs - aws) if is_home else (aws - hs)


def emit_line_change_event(sim: Any, team: Any, info: Dict[str, Any]):
    """Emit a LINE_CHANGE feed event for wholesale changes."""
    if not info.get("wholesale"):
        return
    try:
        team_name = getattr(team, "team_name", "Team")
        # Get the new units
        st = get_shift_state(sim, team)
        line_names = {1: "First", 2: "Second", 3: "Third", 4: "Fourth"}
        pair_names = {1: "first", 2: "second", 3: "third"}
        msg = (f"{line_names.get(st.f_line, 'Next')} line over the boards "
               f"for {team_name} ({pair_names.get(st.d_pair, 'next')} pair).")
        sim._log_event(msg, "LINE_CHANGE")
        # Also emit to PBP for the visualizer
        if hasattr(sim, "_emit_pbp"):
            sim._emit_pbp("line_change", team=team_name,
                          f_line=st.f_line, d_pair=st.d_pair)
    except Exception:
        pass
