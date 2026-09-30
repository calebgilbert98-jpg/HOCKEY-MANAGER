"""Playoff clutch reputation: "Mr. Game 7" and "Playoff Performer".

Additive lore layer on top of the shipped 3-star system (stars.py):

- ``Player.playoff_stars`` counts every playoff 3-star selection (any
  rank); ``Player.game7_stars`` counts the subset earned in a Game 7.
  Both are career counters -- they are never reset by
  League.end_of_season.
- When a counter crosses its threshold, the player earns a reputational
  tag (``Player.clutch_tags``): PLAYOFF_PERFORMER_TAG for sustained
  playoff starring, MR_GAME_7_TAG for repeated Game 7 heroics. Granting
  is idempotent -- a tag is earned once, never duplicated, never
  re-granted.
- ``clutch_epithet(player)`` is the story hook: headlines and playoff
  narratives call it and get "Mr. Game 7" / "Playoff Performer" for a
  tagged player, "" for everyone else (graceful fallback).

No tuning, no weights, no probabilities here -- just counters, named
thresholds, and tag bookkeeping. Never raises; never touches scoring.
"""

from typing import Any, List

# ----------------------------------------------------------------------
# Named thresholds (tuning review)
# ----------------------------------------------------------------------
# Playoff 3-star selections (any rank, career) for PLAYOFF_PERFORMER_TAG.
# A deep run can yield 2-4 for a star; 5 means sustained starring across
# postseasons, not one hot spring.
PLAYOFF_PERFORMER_STARS = 5
# Game-7 3-star selections (any rank, career) for MR_GAME_7_TAG. Game 7s
# are rare (a club can play at most 4 in one postseason, usually 0-2),
# so 3 means repeated decider heroics.
MR_GAME_7_STARS = 3

# Tag ids stored on Player.clutch_tags.
PLAYOFF_PERFORMER_TAG = "playoff_performer"
MR_GAME_7_TAG = "mr_game_7"

_TAG_LABELS = {
    PLAYOFF_PERFORMER_TAG: "Playoff Performer",
    MR_GAME_7_TAG: "Mr. Game 7",
}


def tag_label(tag: str) -> str:
    """Display label for a tag id; "" for unknown ids."""
    return _TAG_LABELS.get(tag or "", "")


def playoff_star_count(player: Any) -> int:
    """Career playoff 3-star selections (any rank). Old-save safe."""
    try:
        return int(getattr(player, "playoff_stars", 0) or 0)
    except Exception:
        return 0


def game7_star_count(player: Any) -> int:
    """Career Game-7 3-star selections (any rank). Old-save safe."""
    try:
        return int(getattr(player, "game7_stars", 0) or 0)
    except Exception:
        return 0


def clutch_tags(player: Any) -> List[str]:
    """Granted tag ids (never None). Old-save safe."""
    try:
        tags = getattr(player, "clutch_tags", None)
        if isinstance(tags, list):
            return [t for t in tags if isinstance(t, str)]
    except Exception:
        pass
    return []


def has_clutch_tag(player: Any, tag: str) -> bool:
    """True when the player already holds this tag."""
    return tag in clutch_tags(player)


def maybe_grant_clutch_tags(player: Any) -> List[str]:
    """Grant newly-earned tags. Idempotent: already-held tags are never
    re-granted and never duplicated. Returns the list of tag ids granted
    by THIS call (empty when nothing new)."""
    granted: List[str] = []
    try:
        tags = getattr(player, "clutch_tags", None)
        if not isinstance(tags, list):
            try:
                player.clutch_tags = tags = []
            except Exception:
                return granted
        # Rarer first -- the bigger reputation lands first in stories.
        if (game7_star_count(player) >= MR_GAME_7_STARS
                and MR_GAME_7_TAG not in tags):
            tags.append(MR_GAME_7_TAG)
            granted.append(MR_GAME_7_TAG)
        if (playoff_star_count(player) >= PLAYOFF_PERFORMER_STARS
                and PLAYOFF_PERFORMER_TAG not in tags):
            tags.append(PLAYOFF_PERFORMER_TAG)
            granted.append(PLAYOFF_PERFORMER_TAG)
    except Exception:
        pass
    return granted


def clutch_epithet(player: Any) -> str:
    """Story hook: "Mr. Game 7" / "Playoff Performer" for a tagged
    player, "" for everyone else. Callers paste it into headlines and
    playoff narratives; the empty string is the graceful fallback."""
    try:
        tags = clutch_tags(player)
        if MR_GAME_7_TAG in tags:
            return _TAG_LABELS[MR_GAME_7_TAG]
        if PLAYOFF_PERFORMER_TAG in tags:
            return _TAG_LABELS[PLAYOFF_PERFORMER_TAG]
    except Exception:
        pass
    return ""
