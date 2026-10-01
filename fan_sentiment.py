# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Persistent fan sentiment: how the fanbase feels about its team, 0-100.

Design (Wave C, D22/D34, Muck 2026-10-01): the building's mood shouldn't be
recomputed from nothing every night. Fan sentiment is a slow-moving stock:

  - a baseline from recent results (winning fills barns, skids empty them),
  - drift toward that baseline over days (feelings fade),
  - discrete nudges from things fans actually react to: press conferences
    (D22 -- defending your players endears you, throwing them under the bus
    doesn't), big wins, embarrassing losses.

Scale: 0-100, 60 = content default. Stored as plain attributes on the team
object (pickle-safe, old saves degrade to the default via getattr).

Feeds arena_atmosphere.pregame_crowd as the `fan_sentiment` parameter, so a
happy fanbase is louder and more behind its team, and a toxic one makes the
building nervous. Game-day experience only -- no revenue/ticket model, per
Muck's explicit call (D34).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

DEFAULT_SENTIMENT = 60.0
_DRIFT_PER_DAY = 1.5  # points per day toward baseline


def _today_iso(current_date: Any) -> Optional[str]:
    try:
        if isinstance(current_date, date):
            return current_date.isoformat()
        if isinstance(current_date, str) and len(current_date) >= 10:
            return current_date[:10]
    except Exception:
        pass
    return None


def _days_since(iso_then: Optional[str], iso_now: Optional[str]) -> float:
    try:
        if not iso_then or not iso_now:
            return 0.0
        d_then = date.fromisoformat(iso_then[:10])
        d_now = date.fromisoformat(iso_now[:10])
        return max(0.0, float((d_now - d_then).days))
    except Exception:
        return 0.0


def _recent_win_pct(team: Any) -> Optional[float]:
    """Win% over recent results; None when unreadable."""
    try:
        results = getattr(team, "recent_results", None) or []
        wins = 0
        n = 0
        for r in results[:10]:
            s = str(r).upper()
            if s.startswith("W") or "WIN" in s:
                wins += 1
                n += 1
            elif s.startswith("L") or "LOSS" in s:
                n += 1
        if n:
            return wins / n
    except Exception:
        pass
    try:
        gp = float(getattr(team, "games_played", 0) or 0)
        if gp > 0:
            return float(getattr(team, "win_pct", 0.5) or 0.5)
    except Exception:
        pass
    return None


def sentiment_baseline(team: Any) -> float:
    """Where sentiment drifts toward, from recent results.

    .500 hockey = content (60). A hot streak pushes toward 85; a deep skid
    drags toward 25. Unknown form = 60.
    """
    try:
        pct = _recent_win_pct(team)
        if pct is None:
            return 60.0
        return max(15.0, min(95.0, 60.0 + (pct - 0.5) * 70.0))
    except Exception:
        return 60.0


def get_fan_sentiment(team: Any,
                      current_date: Any = None) -> float:
    """Read persistent fan sentiment, applying lazy drift to today."""
    try:
        stored = float(getattr(team, "fan_sentiment", DEFAULT_SENTIMENT))
    except Exception:
        stored = DEFAULT_SENTIMENT
    iso_now = _today_iso(current_date)
    if not iso_now:
        return max(0.0, min(100.0, stored))
    iso_then = getattr(team, "fan_sentiment_date", None)
    days = _days_since(iso_then, iso_now)
    if days <= 0:
        return max(0.0, min(100.0, stored))
    base = sentiment_baseline(team)
    drift = min(abs(base - stored), _DRIFT_PER_DAY * days)
    value = stored + drift if base > stored else stored - drift
    return max(0.0, min(100.0, value))


def nudge_fan_sentiment(team: Any, delta: float, reason: str = "",
                        current_date: Any = None) -> float:
    """Apply drift-to-today, then a discrete nudge. Returns the new value."""
    try:
        value = get_fan_sentiment(team, current_date)
        value = max(0.0, min(100.0, value + float(delta or 0.0)))
        team.fan_sentiment = value
        iso_now = _today_iso(current_date)
        if iso_now:
            team.fan_sentiment_date = iso_now
        # Keep a short human-readable trail for the media/fan screens.
        try:
            trail = list(getattr(team, "fan_sentiment_trail", None) or [])
            if reason:
                trail.append({"date": iso_now or "", "delta": round(float(delta or 0.0), 1),
                              "reason": str(reason)[:80]})
                team.fan_sentiment_trail = trail[-12:]
        except Exception:
            pass
        return value
    except Exception:
        return DEFAULT_SENTIMENT


def tick_fan_sentiment(team: Any, current_date: Any = None) -> float:
    """Weekly-style maintenance: drift to today and re-stamp. Returns value."""
    try:
        value = get_fan_sentiment(team, current_date)
        team.fan_sentiment = value
        iso_now = _today_iso(current_date)
        if iso_now:
            team.fan_sentiment_date = iso_now
        return value
    except Exception:
        return DEFAULT_SENTIMENT


def sentiment_label(value: float) -> str:
    """Human label for screens."""
    try:
        v = float(value)
    except Exception:
        return "Content"
    if v >= 85:
        return "Electric"
    if v >= 70:
        return "Happy"
    if v >= 55:
        return "Content"
    if v >= 40:
        return "Restless"
    if v >= 25:
        return "Disgruntled"
    return "Toxic"
