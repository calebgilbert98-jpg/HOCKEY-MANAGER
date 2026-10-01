# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Staff morale as a living system.

Audit (2026-09-30): ``Staff.morale`` was initialized once at creation and
never touched again -- zero writers anywhere in the codebase -- and the
field comment admitted the sim engine never read it. The only consumers
were display reads: the staff-screen morale column, the coach-meeting
"Mood" chip, the meeting dialogue pool, and the season-assessment notch.
A coach's morale had no effect on anything he actually does.

This module makes morale live, additively and on the shared layer so both
engines see the same decision:

  * ``morale_target(staff, team, win_pct, ctx)`` -- where a staffer's
    morale wants to be, from results, job security, contract, ambition
    fit, and controversy.
  * ``staff_morale_tick(team, win_pct)`` -- the monthly engine: morale
    drifts toward its target (deterministic, bounded 1..100). Returns
    news-worthy lines for the storytelling layer.
  * ``morale_factor(morale)`` -- pure 0.90..1.10 effectiveness multiplier
    (60 -> 1.0, the neutral point).
  * ``head_coach_morale_factor(team)`` -- the same, read off the bench boss.

Wired in (all additive, all bounded):
  * parity_engine._coach_quality is scaled by the head coach's morale
    factor -- a miserable elite motivator no longer coaches exactly like
    a happy one. Both engines call pregame_multiplier(), so both fidelities
    share the one decision.
  * assistant_coaches.assistants_monthly_tick drift gains a morale term
    (thriving assistants +1.0, checked-out ones -1.5).
  * coach_practice.coach_drill_rating is scaled by the session coach's
    morale factor -- an inspired teacher teaches better.

Old saves: every read is getattr-defensive; a staffer without a morale
field behaves as a neutral 60.
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Tuning: deliberately small. Morale is the difference between a good month
# and a bad one behind the bench, never the whole story.
# ---------------------------------------------------------------------------
BASELINE = 60.0
TICK_PULL = 0.35          # fraction of the gap to target closed per month
CRISIS_LINE = 30.0        # below this, the papers start asking questions
SPARK_LINE = 75.0         # above this, the room feels the energy

# Target drivers (points added to the 60 baseline, clamped to [5, 98]).
RES_WP_HIGH = 0.600
RES_WP_MID_HIGH = 0.550
RES_WP_MID_LOW = 0.450
RES_WP_LOW = 0.400
RES_BONUS_HIGH = 12.0
RES_BONUS_MID = 6.0
RES_DRAG_MID = -6.0
RES_DRAG_LOW = -12.0

TRUST_LOW = 40.0
TRUST_SOFT = 55.0
TRUST_HIGH = 80.0
TRUST_DRAG = -10.0
TRUST_SOFT_DRAG = -4.0
TRUST_LIFT = 5.0

EXPIRING_YEARS = 1
EXPIRING_DRAG = -5.0

AMBITION_MISMATCH_DRAG = -8.0   # cup-or-bust coach on a rebuild
AMBITION_SOFT_DRAG = -5.0       # developer coach on a contender

CONTROVERSY_HIGH = 50.0
CONTROVERSY_MID = 25.0
CONTROVERSY_DRAG_HIGH = -8.0
CONTROVERSY_DRAG_MID = -3.0

FIRST_CHAIR_LIFT = 8.0          # gratitude: the GM believed in him
SETTLED_YEARS = 5
SETTLED_LIFT = 3.0


def _num(obj: Any, name: str, default: float = 0.0) -> float:
    try:
        v = getattr(obj, name, default)
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _staff_list(team: Any) -> List[Any]:
    try:
        return list(getattr(team, "staff", []) or [])
    except Exception:
        return []


def _team_name(team: Any) -> str:
    try:
        return str(getattr(team, "team_name", "") or "the club")
    except Exception:
        return "the club"


def _staff_name(staff: Any) -> str:
    try:
        n = (f"{getattr(staff, 'first_name', '')} "
             f"{getattr(staff, 'last_name', '')}").strip()
        return n or "The coach"
    except Exception:
        return "The coach"


def _direction(team: Any, ctx: Optional[Dict[str, Any]]) -> str:
    """'rebuild' | 'contender' | '' -- best-effort team direction."""
    try:
        if ctx:
            d = str(ctx.get("direction") or "").strip().lower()
            if d:
                return d
        d = str(getattr(team, "direction", "") or "").strip().lower()
        return d
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Where morale wants to be
# ---------------------------------------------------------------------------
def morale_target(staff: Any, team: Any = None,
                  win_pct: Optional[float] = None,
                  ctx: Optional[Dict[str, Any]] = None) -> float:
    """1..100 target morale for a staffer. Pure function -- never raises."""
    try:
        t = BASELINE
        # Winning cures everything; losing poisons the room.
        if win_pct is not None:
            try:
                wp = float(win_pct)
            except (TypeError, ValueError):
                wp = None
            if wp is not None:
                if wp >= RES_WP_HIGH:
                    t += RES_BONUS_HIGH
                elif wp >= RES_WP_MID_HIGH:
                    t += RES_BONUS_MID
                elif wp <= RES_WP_LOW:
                    t += RES_DRAG_LOW
                elif wp <= RES_WP_MID_LOW:
                    t += RES_DRAG_MID
        # Job security: does the GM still believe in him?
        trust = _num(staff, "gm_trust", 70.0)
        if trust < TRUST_LOW:
            t += TRUST_DRAG
        elif trust < TRUST_SOFT:
            t += TRUST_SOFT_DRAG
        elif trust > TRUST_HIGH:
            t += TRUST_LIFT
        # Contract uncertainty.
        try:
            cy = _num(staff, "contract_years", 3.0)
            if cy <= EXPIRING_YEARS:
                t += EXPIRING_DRAG
        except Exception:
            pass
        # Ambition vs reality.
        try:
            amb = str(getattr(staff, "ambition", "") or "").strip().lower()
            direction = _direction(team, ctx)
            if amb == "stanley_cup" and direction == "rebuild":
                t += AMBITION_MISMATCH_DRAG
            elif amb == "developer" and direction == "contender":
                t += AMBITION_SOFT_DRAG
        except Exception:
            pass
        # Controversy follows a man into the room.
        cont = _num(staff, "controversy", 0.0)
        if cont > CONTROVERSY_HIGH:
            t += CONTROVERSY_DRAG_HIGH
        elif cont > CONTROVERSY_MID:
            t += CONTROVERSY_DRAG_MID
        # The gratitude effect: a first NHL chair is a gift.
        try:
            if bool(getattr(staff, "first_nhl_chair", False)):
                t += FIRST_CHAIR_LIFT
        except Exception:
            pass
        # Settled men sleep better.
        if _num(staff, "years_with_team", 0.0) >= SETTLED_YEARS:
            t += SETTLED_LIFT
        return _clamp(t, 5.0, 98.0)
    except Exception:
        return BASELINE


# ---------------------------------------------------------------------------
# The monthly engine
# ---------------------------------------------------------------------------
def staff_morale_tick(team: Any, win_pct: Optional[float] = None,
                      ctx: Optional[Dict[str, Any]] = None) -> List[str]:
    """Move every staffer's morale toward its target. Deterministic.

    No RNG: morale closes TICK_PULL of the gap each month, so the same
    inputs always produce the same outputs. Returns news-worthy lines
    (crossings of the crisis/spark lines) for the storytelling layer.
    Never raises.
    """
    lines: List[str] = []
    try:
        staffers = _staff_list(team)
        if not staffers:
            return lines
        tname = _team_name(team)
        for stf in staffers:
            try:
                # Float precision lives in _morale_float (display stays int);
                # crossing detection needs the unrounded trajectory.
                cur = float(getattr(stf, "_morale_float",
                                    _num(stf, "morale", BASELINE)))
                tgt = morale_target(stf, team, win_pct, ctx)
                new = _clamp(cur + (tgt - cur) * TICK_PULL, 1.0, 100.0)
                stf._morale_float = new
                stf.morale = int(round(new))
                name = _staff_name(stf)
                # Storytelling: only report crossings, never every month.
                # The spark jump filter keeps hover-hum from becoming news.
                if cur >= CRISIS_LINE and new < CRISIS_LINE:
                    lines.append(
                        f"{name} is running on fumes behind the {tname} "
                        f"bench -- morale in the gutter.")
                elif (cur < SPARK_LINE and new >= SPARK_LINE
                        and (new - cur) >= 1.0):
                    lines.append(
                        f"{name} has his spark back in {tname} -- the room "
                        f"feels the energy.")
            except Exception:
                continue
    except Exception:
        pass
    return lines


# ---------------------------------------------------------------------------
# The sim read: morale -> effectiveness
# ---------------------------------------------------------------------------
def morale_factor(morale: Any) -> float:
    """Pure 0.90..1.10 multiplier. 60 -> 1.0 (neutral). Never raises."""
    try:
        m = float(morale)
    except (TypeError, ValueError):
        m = BASELINE
    return _clamp(1.0 + (m - BASELINE) / 400.0, 0.90, 1.10)


def head_coach_morale_factor(team: Any) -> float:
    """Effectiveness multiplier from the head coach's morale. Never raises."""
    try:
        coach = getattr(team, "head_coach", None)
        if coach is None:
            return 1.0
        return morale_factor(_num(coach, "morale", BASELINE))
    except Exception:
        return 1.0


def describe_morale(staff: Any) -> str:
    """Human-readable morale line for UI/debug. Never raises."""
    try:
        m = _num(staff, "morale", BASELINE)
        if m >= SPARK_LINE:
            tag = "flying"
        elif m >= 55.0:
            tag = "steady"
        elif m >= CRISIS_LINE:
            tag = "grumbling"
        else:
            tag = "in crisis"
        return f"{_staff_name(staff)}: morale {int(round(m))}/100 ({tag})"
    except Exception:
        return "morale unknown"
