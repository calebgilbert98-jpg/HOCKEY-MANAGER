"""Readable momentum: crowd energy + territorial pressure + recent chances.

The player can READ it -- the visualizer shows a meter with labeled drivers
("3 dangerous chances in 2:40", "Crowd roaring"). Momentum changes
perception and RISK (AI pull timing, forecheck/pinch appetite via
risk_appetite()) -- never conversion. There is no hidden rubber-band boost
anywhere in this module; scoreboard effects are exactly zero.

Inputs, home-positive (-100..+100):
  - story base: the existing GameMomentum enum (big story moments only),
  - rolling events: goals, dangerous chances, controlled entries, big hits,
    big saves, fights -- exponential decay, ~4 minute half-life,
  - crowd lean: a loud building behind you sustains a push; a nervous or
    hostile one undercuts it (reads sim._crowd_energy/_crowd_mood live).
"""

from typing import Any, Dict, List, Optional

HALF_LIFE = 240.0          # seconds of game time
_MAX_EVENTS = 400
_PRUNE_AFTER = 900.0       # drop events older than 15 min

# Signed base weights; crowd scales them a touch at observe time.
_WEIGHTS = {
    "goal": 30.0,
    "high_danger": 8.0,
    "medium_danger": 3.0,
    "oz_entry": 2.0,       # controlled zone entry with possession
    "big_hit": 5.0,
    "big_save": 6.0,       # for the defending team -- kills the push
    "fight": 6.0,          # signed to the instigator's team; barn buzzes
}


def _elapsed(sim: Any) -> float:
    """Monotonic game seconds for decay math. Defensive."""
    try:
        period = max(1, int(getattr(sim, "period", 1)))
        clock = float(getattr(sim, "clock", 1200.0))
        return (period - 1) * 1200.0 + max(0.0, 1200.0 - clock)
    except Exception:
        return 0.0


def _is_home(sim: Any, team: Any) -> Optional[bool]:
    try:
        if team is None:
            return None
        return team is getattr(sim, "home_team", None)
    except Exception:
        return None


def observe(sim: Any, kind: str, team: Any = None) -> None:
    """Record a momentum event. Cheap: one append + occasional prune."""
    try:
        w = _WEIGHTS.get(kind)
        if not w:
            return
        home = _is_home(sim, team)
        if home is None:
            signed = 0.0
        else:
            signed = w if home else -w
        # The building amplifies: loud + behind you sustains, loud + against
        # you takes the edge off. Small on purpose (+/-25% at the extremes).
        try:
            e = max(0.0, min(100.0, float(getattr(sim, "_crowd_energy", 50.0)))) / 100.0
            m = max(-1.0, min(1.0, float(getattr(sim, "_crowd_mood", 0.0)) / 100.0))
            if home is True:
                signed *= 1.0 + 0.25 * e * m
            elif home is False:
                signed *= 1.0 - 0.25 * e * m
        except Exception:
            pass
        now = _elapsed(sim)
        evts = getattr(sim, "_momentum_events", None)
        if evts is None:
            evts = []
            sim._momentum_events = evts
        evts.append((now, signed, kind))
        if len(evts) > _MAX_EVENTS or (evts and now - evts[0][0] > _PRUNE_AFTER):
            sim._momentum_events = [e_ for e_ in evts
                                    if now - e_[0] <= _PRUNE_AFTER][- _MAX_EVENTS:]
    except Exception:
        pass


def _rolling(sim: Any, now: float) -> float:
    """Decayed event sum, scaled to -100..100.

    Saturates at ~120 raw weight (about four fresh goals, or a long
    sustained push): beyond that the building can't get louder. A single
    goal reads mid-20s ("tilting"); two quick goals read low-50s
    ("surging").
    """
    try:
        evts = getattr(sim, "_momentum_events", None) or []
        total = 0.0
        for t, signed, _kind in evts:
            age = max(0.0, now - t)
            total += signed * (0.5 ** (age / HALF_LIFE))
        return max(-100.0, min(100.0, total / 120.0 * 100.0))
    except Exception:
        return 0.0


def _story_base(sim: Any) -> float:
    """Existing GameMomentum enum mapped to -100..100 (home-positive)."""
    try:
        m = getattr(sim, "momentum", None)
        if m is None:
            return 0.0
        order = list(type(m))
        idx = order.index(m)          # heavily-home(0) .. heavily-away(6)
        return (3 - idx) * (100.0 / 3.0)
    except Exception:
        return 0.0


def _crowd_lean(sim: Any) -> float:
    try:
        e = max(0.0, min(100.0, float(getattr(sim, "_crowd_energy", 50.0)))) / 100.0
        m = max(-1.0, min(1.0, float(getattr(sim, "_crowd_mood", 0.0)) / 100.0))
        return 15.0 * e * m
    except Exception:
        return 0.0


def score(sim: Any) -> float:
    """Net momentum, -100..100, home-positive. Read-only, no side effects.

    Rolling events carry the read (0.7); the story enum is the slow base
    (0.3) that pushes a sustained push over the top into "onslaught"; the
    crowd leans it a few points either way.
    """
    try:
        now = _elapsed(sim)
        s = (0.30 * _story_base(sim)
             + 0.70 * _rolling(sim, now)
             + _crowd_lean(sim))
        return max(-100.0, min(100.0, s))
    except Exception:
        return 0.0


def _fmt_ago(secs: float) -> str:
    secs = max(0, int(round(secs)))
    if secs < 60:
        return f"{secs}s ago"
    return f"{secs // 60}:{secs % 60:02d} ago"


_KIND_LABEL = {
    "goal": "Goal",
    "high_danger": "dangerous chances",
    "medium_danger": "medium chances",
    "oz_entry": "controlled entries",
    "big_hit": "big hits",
    "big_save": "big saves",
    "fight": "fight",
}


def drivers(sim: Any, limit: int = 3) -> List[str]:
    """Human-readable why: newest first, grouped, with recency."""
    out: List[str] = []
    try:
        now = _elapsed(sim)
        evts = getattr(sim, "_momentum_events", None) or []
        recent = [(t, s_, k) for (t, s_, k) in evts if now - t <= 180.0]
        # group by kind, keep newest timestamp per group
        groups: Dict[str, List] = {}
        for t, s_, k in sorted(recent, key=lambda e: -e[0]):
            groups.setdefault(k, []).append((t, s_))
        for kind, items in list(groups.items())[:limit]:
            newest = items[0][0]
            n = len(items)
            home_n = sum(1 for _, s_ in items if s_ > 0)
            side = "home" if home_n * 2 >= n else "away"
            label = _KIND_LABEL.get(kind, kind)
            if kind in ("high_danger", "medium_danger", "oz_entry", "big_hit"):
                out.append(f"{n} {label} ({side}) -- {_fmt_ago(now - newest)}")
            elif kind == "goal":
                out.append(f"Goal ({side}) -- {_fmt_ago(now - newest)}")
            elif kind == "big_save":
                out.append(f"Big save ({side}) -- {_fmt_ago(now - newest)}")
            else:
                out.append(f"{label.title()} -- {_fmt_ago(now - newest)}")
        # crowd state always reads honestly
        try:
            e = float(getattr(sim, "_crowd_energy", 50.0))
            m = float(getattr(sim, "_crowd_mood", 0.0))
            if e >= 70:
                out.append("Crowd roaring" if m >= -20 else "Building loud but nervous")
            elif e <= 25:
                out.append("Quiet building")
            elif m <= -40 and e >= 55:
                out.append("Building nervous")
        except Exception:
            pass
    except Exception:
        pass
    return out[:limit]


def label(score_value: float, home_name: str = "Home",
          away_name: str = "Away") -> str:
    a = abs(score_value)
    side = home_name if score_value >= 0 else away_name
    if a < 15:
        return "Even"
    if a < 40:
        return f"Tilting {side}"
    if a < 70:
        return f"{side} surging"
    return f"{side} onslaught"


def risk_appetite(sim: Any, team: Any) -> float:
    """AI risk multiplier for `team`, 0.75..1.25.

    This is the ONLY mechanical output: it feeds pull timing and forecheck
    aggression. It never touches conversion.
    """
    try:
        s = score(sim)
        home = _is_home(sim, team)
        signed = s if home else (-s if home is False else 0.0)
        return max(0.75, min(1.25, 1.0 + 0.25 * signed / 100.0))
    except Exception:
        return 1.0


def read_momentum(sim: Any) -> Dict[str, Any]:
    """Everything the visualizer needs in one call."""
    try:
        s = score(sim)
        home_name = getattr(getattr(sim, "home_team", None), "team_name", "Home")
        away_name = getattr(getattr(sim, "away_team", None), "team_name", "Away")
        return {
            "score": round(s, 1),
            "label": label(s, home_name, away_name),
            "drivers": drivers(sim),
            "risk_home": round(risk_appetite(sim, getattr(sim, "home_team", None)), 3),
            "risk_away": round(risk_appetite(sim, getattr(sim, "away_team", None)), 3),
        }
    except Exception:
        return {"score": 0.0, "label": "Even", "drivers": [],
                "risk_home": 1.0, "risk_away": 1.0}
