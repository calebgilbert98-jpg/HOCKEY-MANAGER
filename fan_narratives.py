# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Fan-driven narratives — Bucket 5 (Muck 2026-10-02).

Wires fan sentiment into the story ecosystem. When fans are furious, the
media talks about firing the coach. When they're ecstatic, it's Cup parade
talk. Fan mood shapes narratives, media tone, and (subtly) gameplay.

Design principles:
- Additive only: never replaces existing narrative logic, only adds fan-driven stories
- Never raises: all functions try/except guarded
- Subtle effects: fan sentiment nudges, never dictates
- Cross-season memory: Cup wins buy goodwill; losing decades breed cynicism
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fan_sentiment import get_fan_sentiment, sentiment_label
except Exception:
    def get_fan_sentiment(team: Any, current_date: Any = None) -> float:  # type: ignore
        return 60.0

    def sentiment_label(value: float) -> str:  # type: ignore
        return "Content"


# ---------------------------------------------------------------------------
# Sentiment tiers (aligned with fan_sentiment.sentiment_label)
# ---------------------------------------------------------------------------

TIER_ECSTATIC = "ecstatic"      # 85+
TIER_HAPPY = "happy"            # 70-84
TIER_CONTENT = "content"        # 55-69
TIER_RESTLESS = "restless"      # 40-54
TIER_ANGRY = "angry"            # 25-39
TIER_FURIOUS = "furious"        # 0-24


def sentiment_tier(value: float) -> str:
    """Map 0-100 sentiment to a narrative tier."""
    try:
        v = float(value)
    except Exception:
        return TIER_CONTENT
    if v >= 85:
        return TIER_ECSTATIC
    if v >= 70:
        return TIER_HAPPY
    if v >= 55:
        return TIER_CONTENT
    if v >= 40:
        return TIER_RESTLESS
    if v >= 25:
        return TIER_ANGRY
    return TIER_FURIOUS


# ---------------------------------------------------------------------------
# Fan-driven narrative generation
# ---------------------------------------------------------------------------

def _team_name(team: Any) -> str:
    try:
        return str(getattr(team, "name", getattr(team, "city", "the team")))
    except Exception:
        return "the team"


def _coach_name(team: Any) -> str:
    try:
        coach = getattr(team, "head_coach", None)
        if coach:
            return str(getattr(coach, "name", getattr(coach, "full_name", "the coach")))
    except Exception:
        pass
    return "the coach"


def generate_fan_narrative(team: Any, current_date: Any = None) -> Optional[Dict[str, Any]]:
    """Generate a fan-driven narrative based on current sentiment.

    Returns a narrative dict (or None) suitable for the narrative ledger /
    media system. Never raises.
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        tier = sentiment_tier(sentiment)
        tname = _team_name(team)
        cname = _coach_name(team)

        if tier == TIER_FURIOUS:
            return {
                "kind": "fan_unrest",
                "tier": tier,
                "headline": f"{tname} fans demand change: 'Fire {cname}' chants ring out",
                "body": (f"The fanbase has reached a breaking point. Boos cascade down "
                        f"with every mistake, and social media is ablaze with calls for "
                        f"{cname}'s job. The building feels toxic."),
                "weight": 75,
                "audience": "fans",
            }
        elif tier == TIER_ANGRY:
            return {
                "kind": "fan_unrest",
                "tier": tier,
                "headline": f"Restless in {tname}: fans growing impatient",
                "body": (f"Grumbling in the stands is getting louder. {tname} supporters "
                        f"are questioning the direction, and patience is wearing thin."),
                "weight": 50,
                "audience": "fans",
            }
        elif tier == TIER_ECSTATIC:
            return {
                "kind": "fan_buzz",
                "tier": tier,
                "headline": f"{tname} fever: Cup parade routes being discussed",
                "body": (f"The building is electric every night. {tname} fans are dreaming "
                        f"big, and the buzz around this team is palpable. Sellout crowds "
                        f"are the norm."),
                "weight": 70,
                "audience": "fans",
            }
        elif tier == TIER_HAPPY:
            return {
                "kind": "fan_buzz",
                "tier": tier,
                "headline": f"{tname} fans riding high",
                "body": (f"Good vibes in {tname}. The fanbase is behind this team, "
                        f"and the building has real energy."),
                "weight": 40,
                "audience": "fans",
            }
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Media tone shifts
# ---------------------------------------------------------------------------

def media_tone_for_sentiment(team: Any, current_date: Any = None) -> str:
    """Return a media tone modifier based on fan sentiment.

    Used by the media system to shift headline tone. Never raises.
    Returns: "hostile" | "critical" | "neutral" | "warm" | "glowing"
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        tier = sentiment_tier(sentiment)
        return {
            TIER_FURIOUS: "hostile",
            TIER_ANGRY: "critical",
            TIER_RESTLESS: "neutral",
            TIER_CONTENT: "neutral",
            TIER_HAPPY: "warm",
            TIER_ECSTATIC: "glowing",
        }.get(tier, "neutral")
    except Exception:
        return "neutral"


# ---------------------------------------------------------------------------
# Subtle gameplay effects
# ---------------------------------------------------------------------------

def crowd_energy_mult(team: Any, current_date: Any = None) -> float:
    """Home crowd energy multiplier from fan sentiment.

    Subtle: 0.92 (furious) to 1.08 (ecstatic). Never dictates outcomes.
    Never raises.
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        # Map 0-100 to 0.92-1.08
        return 0.92 + (sentiment / 100.0) * 0.16
    except Exception:
        return 1.0


def board_pressure(team: Any, current_date: Any = None) -> float:
    """Board pressure on GM/coach from fan sentiment.

    0.0 (ecstatic fans, no pressure) to 1.0 (furious fans, hot seat).
    Feeds GM job security calculations. Never raises.
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        # Invert: low sentiment = high pressure
        return max(0.0, min(1.0, (70.0 - sentiment) / 70.0))
    except Exception:
        return 0.0


def fa_appeal_mult(team: Any, current_date: Any = None) -> float:
    """Free agent appeal modifier from fan sentiment.

    Players want to play for happy fanbases. Subtle: 0.95 to 1.05.
    Never raises.
    """
    try:
        sentiment = get_fan_sentiment(team, current_date)
        return 0.95 + (sentiment / 100.0) * 0.10
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Cross-season memory
# ---------------------------------------------------------------------------

def apply_season_memory(team: Any, won_cup: bool = False,
                       made_playoffs: bool = False) -> None:
    """Apply cross-season fanbase memory. Called at season end.

    - Cup win: sets a goodwill buffer that decays slowly over ~3 seasons
    - Missing playoffs: adds a cynicism marker
    - Decade of losing (tracked via consecutive losing seasons): deep cynicism

    Never raises.
    """
    try:
        # Goodwill from Cup wins (decays over seasons)
        if won_cup:
            team.fan_goodwill_seasons = 3
        else:
            gw = int(getattr(team, "fan_goodwill_seasons", 0) or 0)
            team.fan_goodwill_seasons = max(0, gw - 1)

        # Track consecutive losing seasons for deep cynicism
        if not made_playoffs:
            losing = int(getattr(team, "fan_losing_streak", 0) or 0)
            team.fan_losing_streak = losing + 1
        else:
            team.fan_losing_streak = 0
    except Exception:
        pass


def goodwill_sentiment_floor(team: Any) -> float:
    """Minimum sentiment floor from Cup goodwill.

    A recent Cup win prevents sentiment from fully collapsing —
    fans remember. Never raises.
    """
    try:
        gw = int(getattr(team, "fan_goodwill_seasons", 0) or 0)
        if gw >= 3:
            return 45.0  # Fresh champs: fans stay patient
        elif gw >= 2:
            return 38.0
        elif gw >= 1:
            return 32.0
    except Exception:
        pass
    return 0.0


def cynicism_sentiment_ceiling(team: Any) -> float:
    """Maximum sentiment ceiling from sustained losing.

    A decade of futility breeds cynicism — even winning streaks don't
    fully electrify a beaten-down fanbase. Never raises.
    """
    try:
        losing = int(getattr(team, "fan_losing_streak", 0) or 0)
        if losing >= 8:
            return 70.0  # Deep cynicism: can't reach ecstatic
        elif losing >= 5:
            return 78.0
        elif losing >= 3:
            return 85.0
    except Exception:
        pass
    return 100.0


# ---------------------------------------------------------------------------
# Daily/weekly integration
# ---------------------------------------------------------------------------

# Cooldown: don't spam fan narratives (days between stories per team)
_NARRATIVE_COOLDOWN_DAYS = 14


def maybe_fire_fan_narrative(team: Any, game_manager: Any = None,
                              current_date: Any = None) -> bool:
    """Check if a fan narrative should fire for this team. Returns True if fired.

    Only fires on tier changes (e.g., content -> angry) or extreme tiers,
    with a cooldown to prevent spam. Never raises.
    """
    try:
        from fan_sentiment import get_fan_sentiment

        sentiment = get_fan_sentiment(team, current_date)
        tier = sentiment_tier(sentiment)

        # Only fire for extreme tiers (furious, ecstatic) or tier changes
        last_tier = getattr(team, "_fan_narrative_last_tier", None)

        should_fire = False
        if tier in (TIER_FURIOUS, TIER_ECSTATIC):
            # Extreme tiers: fire (with cooldown)
            should_fire = True
        elif last_tier and last_tier != tier:
            # Tier changed: fire (e.g., content -> angry is newsworthy)
            # But only if moving to a more extreme tier
            tier_order = [TIER_ECSTATIC, TIER_HAPPY, TIER_CONTENT,
                         TIER_RESTLESS, TIER_ANGRY, TIER_FURIOUS]
            try:
                old_idx = tier_order.index(last_tier)
                new_idx = tier_order.index(tier)
                # Fire if moved 2+ steps, or into angry/furious/ecstatic
                if abs(new_idx - old_idx) >= 2 or tier in (TIER_ANGRY, TIER_FURIOUS, TIER_ECSTATIC):
                    should_fire = True
            except Exception:
                pass

        if not should_fire:
            team._fan_narrative_last_tier = tier
            return False

        # Check cooldown
        try:
            from datetime import date
            last_fired = getattr(team, "_fan_narrative_last_date", None)
            if last_fired and current_date:
                if isinstance(current_date, date) and isinstance(last_fired, date):
                    days = (current_date - last_fired).days
                    if days < _NARRATIVE_COOLDOWN_DAYS:
                        return False
                elif isinstance(current_date, str) and isinstance(last_fired, str):
                    d_now = date.fromisoformat(current_date[:10])
                    d_then = date.fromisoformat(last_fired[:10])
                    if (d_now - d_then).days < _NARRATIVE_COOLDOWN_DAYS:
                        return False
        except Exception:
            pass

        # Generate and deliver the narrative
        narrative = generate_fan_narrative(team, current_date)
        if not narrative:
            team._fan_narrative_last_tier = tier
            return False

        # Deliver via headlines system
        try:
            from headlines import make_headline
            msg = make_headline(
                "fan_narrative",
                game_date=current_date,
                headline=narrative["headline"],
                body=narrative["body"],
                tier=narrative["tier"],
                team_name=_team_name(team),
            )
            if msg and game_manager:
                # Add to inbox
                inbox = getattr(game_manager, "inbox", None)
                if inbox is not None:
                    if hasattr(inbox, "add_message"):
                        inbox.add_message(msg)
                    elif hasattr(inbox, "append"):
                        inbox.append(msg)
        except Exception:
            pass

        # Update tracking
        team._fan_narrative_last_tier = tier
        try:
            team._fan_narrative_last_date = current_date
        except Exception:
            pass

        return True
    except Exception:
        return False
