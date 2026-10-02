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


# ---------------------------------------------------------------------------
# Bucket 5 extensions (Muck 2026-10-02): expectations, events, cross-season
# ---------------------------------------------------------------------------

# Board expectation -> expected win% mapping
_EXPECTATION_WIN_PCT = {
    "cup_contender": 0.65,
    "playoff_team": 0.58,
    "bubble_team": 0.50,
    "rebuilding": 0.38,
    "lottery_team": 0.32,
}


def expectation_adjusted_baseline(team: Any) -> float:
    """Baseline adjusted for performance vs preseason expectations.

    Overachieving (winning more than expected) boosts sentiment beyond
    raw win%. Underachieving drags it down even with a decent record.
    Never raises.
    """
    try:
        base = sentiment_baseline(team)
        expectation = str(getattr(team, "board_expectation", "bubble_team") or "bubble_team")
        expected_pct = _EXPECTATION_WIN_PCT.get(expectation, 0.50)

        pct = _recent_win_pct(team)
        if pct is None:
            return base

        # Over/underachievement shifts baseline by up to +/- 10 points
        diff = pct - expected_pct
        adjustment = max(-10.0, min(10.0, diff * 50.0))
        return max(15.0, min(95.0, base + adjustment))
    except Exception:
        try:
            return sentiment_baseline(team)
        except Exception:
            return 60.0


def nudge_for_trade(team: Any, trade_grade: str = "neutral",
                    current_date: Any = None) -> float:
    """Fan reaction to a trade. Never raises."""
    try:
        deltas = {
            "fleeced": -8.0,      # Fans think we got robbed
            "lost": -4.0,         # Questionable deal
            "neutral": 0.0,
            "won": 4.0,           # Good value
            "blockbuster_won": 8.0,  # Landed a star
        }
        delta = deltas.get(str(trade_grade).lower(), 0.0)
        return nudge_fan_sentiment(team, delta, f"trade ({trade_grade})", current_date)
    except Exception:
        return DEFAULT_SENTIMENT


def nudge_for_signing(team: Any, player_tier: str = "depth",
                      current_date: Any = None) -> float:
    """Fan reaction to a free agent signing. Never raises."""
    try:
        deltas = {
            "superstar": 10.0,
            "star": 6.0,
            "top_six": 3.0,
            "depth": 1.0,
            "overpay": -3.0,      # Fans hate overpays
        }
        delta = deltas.get(str(player_tier).lower(), 0.0)
        return nudge_fan_sentiment(team, delta, f"signing ({player_tier})", current_date)
    except Exception:
        return DEFAULT_SENTIMENT


def nudge_for_coaching_change(team: Any, was_fired: bool = True,
                               current_date: Any = None) -> float:
    """Fan reaction to a coaching change. Never raises.

    Firing a coach when fans are furious = relief (+). Firing when fans
    are happy = outrage (-). Hiring is generally positive.
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        if was_fired:
            # If fans were furious, firing is relief. If happy, it's anger.
            if sentiment < 30:
                delta = 6.0
            elif sentiment < 50:
                delta = 2.0
            elif sentiment > 70:
                delta = -8.0  # "Why did you fire a winning coach?!"
            else:
                delta = -2.0
            return nudge_fan_sentiment(team, delta, "coach fired", current_date)
        else:
            return nudge_fan_sentiment(team, 3.0, "new coach hired", current_date)
    except Exception:
        return DEFAULT_SENTIMENT


def get_fan_sentiment_with_memory(team: Any,
                                  current_date: Any = None) -> float:
    """Fan sentiment with cross-season memory applied.

    Applies goodwill floor (recent Cup) and cynicism ceiling (sustained
    losing) on top of the base sentiment. Never raises.
    """
    try:
        value = get_fan_sentiment(team, current_date)

        # Goodwill floor: recent Cup wins prevent full collapse
        try:
            from fan_narratives import goodwill_sentiment_floor, cynicism_sentiment_ceiling
            floor = goodwill_sentiment_floor(team)
            ceiling = cynicism_sentiment_ceiling(team)
            value = max(floor, min(ceiling, value))
        except Exception:
            pass

        return max(0.0, min(100.0, value))
    except Exception:
        return DEFAULT_SENTIMENT
