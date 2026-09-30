# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Real shift engine for Puck Dynasty.

Replaces the clock-math line rotation (`(clock // 45) % 4 + 1`) with actual
shift state: who is on the ice, when their shift started, and conditional
change logic (whistles, on-the-fly, line matching, fatigue).

Design doc: docs/SHIFT_ENGINE_DESIGN.md

Engine boundary: this changes WHO is on the ice and WHEN they change. It does
NOT touch goal probabilities, shot math, save logic, tactics multipliers, or
fatigue drain rates.

Rotation is policy-driven (icetime-ecosystem, W2): the next line/pair comes
from deployment_policy.deployment_weights -- coaching style, morale, score
state, talent, attitude, archetype fit, relationships, honored GM advice --
with a ~30-min soft-cap governor. Per-game TOI is credited at every change
via deployment_policy's accumulator.
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
        # W2 (icetime-ecosystem): TOI accounting anchor -- the goalie credit
        # clock starts when the state is created.
        st._toi_flush_clock = clock
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
        # W2 (icetime-ecosystem): credit the truncated shift to the horn so
        # per-game TOI stays exact across periods. deployment_policy owns
        # the accounting; this is just the hook.
        try:
            from deployment_policy import flush_team_toi_at_clock
            flush_team_toi_at_clock(sim, team, st, 0.0)
        except Exception:
            pass
        st.f_shift_start = clock
        st.d_shift_start = clock
        st.st_shift_start = clock
        st._toi_flush_clock = clock
        st._period = period
    return st


def _next_in_rotation(current: int, max_n: int) -> int:
    return (current % max_n) + 1




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


def _credit_outgoing(sim: Any, team: Any, st: ShiftState, clock: float,
                   side: str) -> None:
    """Hook: credit the outgoing unit's elapsed ice time before it changes.

    Delegates to deployment_policy (manpower-aware: PP/PK time credits the
    special-teams unit the sim actually dressed). Never raises.
    """
    try:
        from deployment_policy import (credit_forwards_elapsed,
                                        credit_defense_elapsed)
        if side == "F":
            credit_forwards_elapsed(sim, team, st, clock)
        else:
            credit_defense_elapsed(sim, team, st, clock)
    except Exception:
        pass


def _policy_next_line(sim: Any, team: Any, st: ShiftState, side: str,
                      reason: str = "rotation",
                      leverage_mode: Optional[str] = None) -> int:
    """Next line/pair by coaching deployment policy (weighted rotation).

    Replaces the fixed 1->2->3->4 round-robin: shares come from
    deployment_policy.deployment_weights (coach style, morale, score state,
    talent, fit, relationships, honored advice), then the ~30-min soft-cap
    governor downweights lines whose skaters hit the cap. A change means a
    change -- the unit coming off is excluded from the pick. Falls back to
    plain round-robin if the policy is unavailable.

    leverage_mode ("attack" | "defend" | None) is within-line differentiation:
    after the soft-cap governor, each line's share is multiplied by its mean
    leverage (attack: premium offensive minutes -- OZ starts, hot scorers) or
    defensive trust (defend: trusted checkers soak DZ draws). This changes
    WHICH minutes a line gets, never WHO plays -- the soft-cap zeroing and
    the quantity shares are untouched, and the quantity clamp [0.95, 1.05]
    still binds minutes. None = pre-leverage behavior.
    """
    n = 4 if side == "F" else 3
    current = st.f_line if side == "F" else st.d_pair
    try:
        from deployment_policy import (deployment_weights_for_game,
                                        soft_cap_adjust_shares,
                                        pick_weighted_line,
                                        LEVERAGE_ENABLED,
                                        line_leverage, line_trust)
        weights = deployment_weights_for_game(sim, team)
        shares = list(weights["F" if side == "F" else "D"])
        shares = soft_cap_adjust_shares(sim, team, side, shares)
        if leverage_mode and LEVERAGE_ENABLED:
            kind = "F" if side == "F" else "D"
            mults = []
            for i in range(1, n + 1):
                if leverage_mode == "attack":
                    mults.append(line_leverage(sim, team, kind, i))
                else:
                    mults.append(line_trust(sim, team, kind, i))
            shares = [s * m for s, m in zip(shares, mults)]
            tot = sum(shares)
            shares = [s / tot for s in shares] if tot > 0 else shares
        return pick_weighted_line(shares, n, exclude=current)
    except Exception:
        return _next_in_rotation(current, n)


def _policy_pick_from(sim: Any, team: Any, side: str,
                      candidates: Tuple[int, ...]) -> int:
    """Weighted pick among explicit candidate lines (chase/protect calls).

    Unlike _policy_next_line this is the coach's explicit call, so the
    current line is NOT excluded -- sending the top line back out to chase
    a game is the whole point.
    """
    n = 4 if side == "F" else 3
    try:
        from deployment_policy import (deployment_weights_for_game,
                                        soft_cap_adjust_shares,
                                        pick_weighted_line)
        weights = deployment_weights_for_game(sim, team)
        shares = list(weights["F" if side == "F" else "D"])
        shares = soft_cap_adjust_shares(sim, team, side, shares)
        sub = [shares[c - 1] if 1 <= c <= n else 0.0 for c in candidates]
        if sum(sub) <= 0:
            sub = [1.0 / len(candidates)] * len(candidates)
        pick = random.choices(list(candidates), weights=sub, k=1)[0]
        return pick
    except Exception:
        return random.choice(list(candidates))


def _leverage_pick_from(sim: Any, team: Any, side: str,
                        candidates: Tuple[int, ...],
                        mode: str, log_key: str = "") -> int:
    """Weighted pick among candidate lines, leverage-weighted (clutch calls).

    Like _policy_pick_from, but each candidate's share is multiplied by its
    mean leverage (mode "attack": chase/empty-net -- the hot scorers get the
    call) or defensive trust (mode "defend": protect-lead -- the trusted
    checkers close it out). The current line is NOT excluded (explicit coach
    call). Falls back to the plain pick when leverage is off or unavailable.

    A narrative line goes to the broadcast feed when a genuinely hot
    (leverage >= 1.15) line gets the call -- throttled per game.
    """
    n = 4 if side == "F" else 3
    try:
        from deployment_policy import (deployment_weights_for_game,
                                        soft_cap_adjust_shares,
                                        LEVERAGE_ENABLED,
                                        line_leverage, line_trust,
                                        line_leverage_leader,
                                        log_leverage)
        if not LEVERAGE_ENABLED:
            return _policy_pick_from(sim, team, side, candidates)
        weights = deployment_weights_for_game(sim, team)
        shares = list(weights["F" if side == "F" else "D"])
        shares = soft_cap_adjust_shares(sim, team, side, shares)
        kind = "F" if side == "F" else "D"
        sub = []
        for c in candidates:
            s = shares[c - 1] if 1 <= c <= n else 0.0
            m = (line_leverage(sim, team, kind, c) if mode == "attack"
                 else line_trust(sim, team, kind, c))
            sub.append(max(0.0, s) * m)
        if sum(sub) <= 0:
            return _policy_pick_from(sim, team, side, candidates)
        pick = random.choices(list(candidates), weights=sub, k=1)[0]
        # Narrative: a genuinely hot line getting the clutch call.
        try:
            if mode == "attack" and log_key:
                lev = line_leverage(sim, team, kind, pick)
                if lev >= 1.15:
                    leader = line_leverage_leader(sim, team, kind, pick)
                    pname = getattr(leader, "full_name",
                                    getattr(leader, "name", "?"))
                    tname = getattr(team, "team_name", "?")
                    log_leverage(sim, team, f"{log_key}_{pick}",
                                  f"{tname}: riding the hot hand -- {pname} "
                                  f"over the boards ({log_key}).")
        except Exception:
            pass
        return pick
    except Exception:
        return _policy_pick_from(sim, team, side, candidates)


def _leverage_best_line(sim: Any, team: Any,
                        candidates: Tuple[int, ...]) -> Optional[int]:
    """Candidate line (1-based) with the highest mean leverage.

    Used for mismatch exploitation: when the away team declares its 4th
    line, the HOTTEST scoring line (not just "line 1") gets the mismatch.
    Returns None when leverage is off or unavailable (caller keeps the
    default pick).
    """
    try:
        from deployment_policy import LEVERAGE_ENABLED, line_leverage
        if not LEVERAGE_ENABLED:
            return None
        scored = [(line_leverage(sim, team, "F", c), c) for c in candidates]
        if not scored:
            return None
        return max(scored)[1]
    except Exception:
        return None


def _policy_score_thresholds(sim: Any, team: Any) -> Tuple[int, int]:
    """(chase_at, protect_at) goal-diff thresholds, parameterized by policy.

    Defaults (-2, +2) preserve the historical behavior; an aggressive coach
    (high concentration) trailing late starts chasing at -1.
    """
    try:
        from deployment_policy import (deployment_weights_for_game,
                                        score_state_thresholds)
        weights = deployment_weights_for_game(sim, team)
        gs = weights.get("meta", {})
        concentration = float(gs.get("concentration", 0.40))
        return score_state_thresholds(
            {"period": getattr(sim, "period", 1),
             "clock": getattr(sim, "clock", 1200),
             "score_diff": _goal_diff_for(sim, team,
                                          team is getattr(sim, "home_team",
                                                           None))},
            concentration)
    except Exception:
        return -2, 2


def change_lines(sim: Any, team: Any, st: ShiftState,
                 change_f: bool = True, change_d: bool = True,
                 reason: str = "rotation",
                 leverage_mode: Optional[str] = None) -> Dict[str, Any]:
    """Execute a line change. Returns info about what changed.

    leverage_mode ("attack" | "defend" | None) is threaded to the policy
    pick: within-line differentiation on the rotation path (OZ draws get
    leverage-weighted lines; DZ draws get trust-weighted lines).
    """
    clock = getattr(sim, "clock", 0)
    result = {"forwards": False, "defense": False, "wholesale": False}

    if change_f:
        _credit_outgoing(sim, team, st, clock, "F")
        st.record_shift(st.f_age(clock))
        st.f_line = _policy_next_line(sim, team, st, "F", reason, leverage_mode)
        st.f_shift_start = clock
        result["forwards"] = True

    if change_d:
        _credit_outgoing(sim, team, st, clock, "D")
        st.record_shift(st.d_age(clock))
        st.d_pair = _policy_next_line(sim, team, st, "D", reason, leverage_mode)
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

    # Hard cap: no shift beyond 50s, even at a stoppage. This overrides
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
        # Within-line differentiation -- mismatch sheltering: when the away
        # team declares its 4th line, the HOTTEST scoring line gets the
        # mismatch, not just "line 1". Only the auto exploit path (a user
        # "Match to line" pref always wins).
        try:
            prefs = getattr(team, "line_matchups", None) or {}
            f_prefs = list(prefs.get("F") or [])[:4]
            pref_hit = any(w == away_line for w in f_prefs if w)
            if (away_line == 4 and target_line == 1 and not pref_hit):
                best = _leverage_best_line(sim, team, (1, 2))
                if best is not None and best != target_line:
                    from deployment_policy import (line_leverage_leader,
                                                    log_leverage)
                    target_line = best
                    leader = line_leverage_leader(sim, team, "F", best)
                    pname = getattr(leader, "full_name",
                                    getattr(leader, "name", "?"))
                    tname = getattr(team, "team_name", "?")
                    log_leverage(sim, team, f"shelter_{best}",
                                 f"{tname}: {pname}'s line gets the mismatch "
                                 f"-- hot scorers out against the fourth line.")
        except Exception:
            pass
    elif not is_home:
        # Away team rolls rotation (no last change on the road)
        pass

    # Score-state layer (deployment policy, was fixed +-2 for every coach):
    # trailing -> shorten to top six; leading -> bottom six / checkers.
    # Thresholds AND the pick among the short-bench lines now come from the
    # coach's deployment policy. This overrides matching. The pick itself is
    # leverage-weighted: chasing -> the hot scorers; protecting -> the
    # trusted checkers. 6-on-5 (goalie pulled) is the most aggressive state
    # and overrides everything.
    goal_diff = _goal_diff_for(sim, team, is_home)
    chase_at, protect_at = _policy_score_thresholds(sim, team)
    if goal_diff <= chase_at:
        target_line = _leverage_pick_from(sim, team, "F", (1, 2), "attack",
                                          "chasing late")
        result["reason"] = "chase_game"
    elif goal_diff >= protect_at:
        target_line = _leverage_pick_from(sim, team, "F", (3, 4), "defend")
        result["reason"] = "protect_lead"
    try:
        _pulled = team.team_name in (getattr(sim, "goalie_pulled", None)
                                     or set())
    except Exception:
        _pulled = False
    if _pulled and goal_diff <= 0:
        target_line = _leverage_pick_from(sim, team, "F", (1, 2), "attack",
                                          "net empty")
        result["reason"] = "empty_net_attack"

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

    # Within-line differentiation on the rotation path: OZ draws weight the
    # pick toward high-leverage (hot) lines; DZ draws toward trusted
    # defensive units. Neutral-zone stoppages roll the plain shares.
    _zone_leverage = ("attack" if zone == "offensive"
                      else "defend" if zone == "defensive" else None)
    if target_line is not None and change_f:
        _credit_outgoing(sim, team, st, clock, "F")
        st.record_shift(st.f_age(clock))
        st.f_line = target_line
        st.f_shift_start = clock
        result["forwards"] = True
    elif change_f:
        info = change_lines(sim, team, st, change_f=True, change_d=False,
                            reason=result["reason"],
                            leverage_mode=_zone_leverage)
        result["forwards"] = info["forwards"]

    if target_pair is not None and change_d:
        _credit_outgoing(sim, team, st, clock, "D")
        st.record_shift(st.d_age(clock))
        st.d_pair = target_pair
        st.d_shift_start = clock
        result["defense"] = True
    elif change_d:
        info = change_lines(sim, team, st, change_f=False, change_d=True,
                            reason=result["reason"],
                            leverage_mode=_zone_leverage)
        result["defense"] = info["defense"]

    result["wholesale"] = result["forwards"] and result["defense"]
    return result


def matching_response(away_line: int, f_prefs, d_prefs,
                      roll_f: int, roll_d: int) -> Tuple[int, int]:
    """Shared last-change decision, used by BOTH engines (1-based).

    This is the single source of truth for "who does the home team send
    out against the away team's declared line". GameSim calls it with the
    live shift state's current lines as the roll context; AdvancedGameSim
    (the speed-optimized engine) calls it with its own rotation pick.
    Same decision, different fidelity -- never two copies of the logic.

    The user can override the automatic response per line via the lines
    screen "Match to line" dropdowns (Team.line_matchups): the first of my
    lines/pairs targeting the opponent's declared line gets the call, with
    F and D chosen independently. Unset entries fall back to the auto
    behavior below:

    vs 1st line -> checking line (3rd) + top D pair (1st)
    vs 4th line -> 1st line (exploit the mismatch)
    vs 2nd/3rd -> roll (roll_f, roll_d)
    """
    f_prefs = list(f_prefs or [])[:4] + [None] * 4
    d_prefs = list(d_prefs or [])[:3] + [None] * 3
    if away_line == 1:
        auto_f, auto_d = 3, 1
    elif away_line == 4:
        auto_f, auto_d = 1, 1  # top pair with the top line to exploit
    else:
        auto_f, auto_d = roll_f, roll_d  # roll

    # User-set matchup preferences (1-4 opponent forward line, or None).
    want_f = next((i + 1 for i, want in enumerate(f_prefs[:4])
                   if want == away_line), None)
    want_d = next((i + 1 for i, want in enumerate(d_prefs[:3])
                   if want == away_line), None)
    return (want_f or auto_f, want_d or auto_d)


def matching_is_active(away_line: int, f_prefs, d_prefs) -> Tuple[bool, bool]:
    """Was the last-change decision a real call, per side (1-based)?

    True when the auto behavior names a unit (vs 1st/4th) or a "Match to
    line" pref hit -- i.e. the home bench won the matchup battle rather
    than just rolling its rotation. AdvancedGameSim uses this for its
    small directed-matchup edge channel.
    """
    if away_line in (1, 4):
        return True, True
    f_prefs = list(f_prefs or [])[:4]
    d_prefs = list(d_prefs or [])[:3]
    return (any(w == away_line for w in f_prefs if w),
            any(w == away_line for w in d_prefs if w))


def _matching_response(away_line: int, sim: Any, home_team: Any) -> Tuple[int, int]:
    """GameSim adapter: builds the roll context from the live shift state,
    then delegates to the shared matching_response."""
    st = get_shift_state(sim, home_team)
    prefs = getattr(home_team, "line_matchups", None) or {}
    return matching_response(away_line, prefs.get("F"), prefs.get("D"),
                             st.f_line, st.d_pair)


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


# ---------------------------------------------------------------------------
# Shift fatigue (the EHM lesson, additive)
# ---------------------------------------------------------------------------
# A unit kept out past ~40s degrades: tired legs lose the battles that make
# shots. Both engines share the curve below; each has a thin adapter because
# their clocks differ (GameSim counts down, AdvancedGameSim counts up).

FATIGUE_ONSET_S = 40.0   # no degradation at or below this shift age
FATIGUE_SLOPE = 0.02     # -2% effectiveness per 10s past onset
FATIGUE_FLOOR = 0.90     # never worse than -10%


def fatigue_curve(shift_age_s: float) -> float:
    """Pure curve: 1.0 at/under onset, linear decay after, floored."""
    try:
        age = float(shift_age_s)
    except Exception:
        return 1.0
    if age <= FATIGUE_ONSET_S:
        return 1.0
    return max(FATIGUE_FLOOR, 1.0 - FATIGUE_SLOPE * ((age - FATIGUE_ONSET_S) / 10.0))


def shift_fatigue_mult(sim: Any, team: Any) -> float:
    """GameSim adapter: multiplier for the attacking unit right now.

    Never raises; returns 1.0 when shift state is unavailable.
    """
    try:
        st = get_shift_state(sim, team)
        clock = getattr(sim, "clock", 0)
        age = max(st.f_age(clock), st.d_age(clock))
        return fatigue_curve(age)
    except Exception:
        return 1.0
