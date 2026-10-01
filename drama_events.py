# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Structured drama-event bookkeeping: shared layer for both sim engines.

Pulls, empty-net goals, late equalizers and OT outcomes are recorded as
structured sim events -- measurement reads these, never text logs. Both
engines keep a ``drama_events`` list (created by ``init_drama_events``);
the broadcast view keeps its text log lines / pbp emits unchanged.

Event shapes (dicts, JSON-serializable):
  goalie_pull:    {event, team, period, clock_remaining, coach_style, deficit}
  empty_net_goal: {event, team, scorer, scorer_id, period, clock_remaining}
  late_equalizer: {event, team, scorer, scorer_id, period, clock_remaining,
                   pull_clock_remaining}
  ot_result:      {event, decided: '3v3'|'shootout'|'ot_sudden_death',
                   winner, loser}

clock_remaining is seconds left in the period when the event fired.
Pure appends; never raises.
"""

GOALIE_PULL = "goalie_pull"
EMPTY_NET_GOAL = "empty_net_goal"
LATE_EQUALIZER = "late_equalizer"
OT_RESULT = "ot_result"


def init_drama_events(sim):
    """Create (or reset) the sim's structured drama-event list."""
    try:
        sim.drama_events = []
    except Exception:
        pass


def _append(sim, event):
    try:
        evs = getattr(sim, "drama_events", None)
        if evs is None:
            evs = []
            sim.drama_events = evs
        evs.append(event)
    except Exception:
        pass


def _clock(sim):
    """Seconds remaining in the current period, engine-agnostic."""
    try:
        # GameSim: clock counts down from the period length.
        _c = getattr(sim, "clock", None)
        if _c is not None:
            return max(0.0, float(_c))
    except Exception:
        pass
    try:
        # AdvancedGameSim: time counts up; 1200s periods from 0.
        _t = float(getattr(sim, "time", 0) or 0)
        _p = int(getattr(sim, "period", 1) or 1)
        return max(0.0, 1200.0 * _p - _t)
    except Exception:
        pass
    return 0.0


def _period(sim):
    try:
        return int(getattr(sim, "period", 1) or 1)
    except Exception:
        return 1


def record_goalie_pull(sim, team_name, coach_style=None, deficit=None,
                       delayed=False):
    """A coach pulled the goalie for the extra attacker.

    delayed=True marks the routine delayed-penalty 6th attacker (not a
    strategic late-game pull) -- recorded distinctly so measurement can
    exclude it.
    """
    _append(sim, {
        "event": GOALIE_PULL,
        "team": team_name,
        "period": _period(sim),
        "clock_remaining": round(_clock(sim), 1),
        "coach_style": coach_style,
        "deficit": deficit,
        "delayed": bool(delayed),
    })


def record_empty_net_goal(sim, team_name, scorer=None):
    """The leading team converted into the empty net."""
    _append(sim, {
        "event": EMPTY_NET_GOAL,
        "team": team_name,
        "scorer": getattr(scorer, "full_name", None),
        "scorer_id": getattr(scorer, "id", None),
        "period": _period(sim),
        "clock_remaining": round(_clock(sim), 1),
    })


def record_late_equalizer(sim, team_name, scorer=None,
                          pull_clock_remaining=None):
    """The pulling team tied the game at 6v5 -- the honest late equalizer."""
    _append(sim, {
        "event": LATE_EQUALIZER,
        "team": team_name,
        "scorer": getattr(scorer, "full_name", None),
        "scorer_id": getattr(scorer, "id", None),
        "period": _period(sim),
        "clock_remaining": round(_clock(sim), 1),
        "pull_clock_remaining": pull_clock_remaining,
    })


def record_ot_result(sim, decided, winner_name=None, loser_name=None):
    """How OT ended: '3v3' (regular-season 3-on-3), 'shootout', or
    'ot_sudden_death' (playoff continuous OT)."""
    _append(sim, {
        "event": OT_RESULT,
        "decided": decided,
        "winner": winner_name,
        "loser": loser_name,
    })
