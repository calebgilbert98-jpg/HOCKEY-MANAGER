"""League-wide "Around the League" digest.

The narrative systems (narrative_incidents.record_stories, media_engine.cover_game)
fire for every game, but headlines only deliver for user-involved games. The other
15 games' stories vanish into the ledger. This module collects the day's AI-game
stories and delivers the top 2-3 as a curated digest -- not spam, the night's
actual best stories.

Narrative ignition (Muck 2026-10-02): the league felt dead because only the user's
games produced visible stories. Now the user sees what happened around the league.

Never raises. Additive only.
"""

from typing import Any, Dict, List, Optional

# Per-day story accumulation. Keyed by id() of app to avoid cross-save leakage.
# Cleared after each digest delivery.
_DIGEST_STORE: Dict[int, List[Dict[str, Any]]] = {}

# Story-kind weights for digest ranking. Higher = more digest-worthy.
# These mirror narrative_incidents weights but are tuned for "would a fan care?"
_DIGEST_WEIGHTS = {
    "hat_trick": 15,
    "goalie_steal": 14,   # 35+ save steal is a better story than a shutout
    "shutout": 12,
    "blowout": 10,
    "ot_thriller": 11,    # OT drama plays well in a digest
    "line_brawl": 13,     # brawls are rare and memorable
    "fight": 5,
}

# Maximum stories per digest. 3 is the sweet spot -- enough to feel alive,
# not enough to feel like spam.
_DIGEST_MAX = 3


def collect_game_stories(app: Any, stories: Optional[List[Dict[str, Any]]]) -> None:
    """Accumulate one game's stories for the end-of-day digest.

    Called from _narrative_postgame when deliver_headlines is False (AI games).
    Stories already delivered as headlines (user games) are not collected --
    the digest is for what the user DIDN'T see.
    Never raises.
    """
    try:
        if not stories:
            return
        key = id(app)
        bucket = _DIGEST_STORE.get(key)
        if bucket is None:
            bucket = []
            _DIGEST_STORE[key] = bucket
        for st in stories:
            try:
                if isinstance(st, dict) and st.get("text"):
                    bucket.append(st)
            except Exception:
                continue
    except Exception:
        pass


def _story_weight(story: Dict[str, Any]) -> int:
    """Digest-worthiness weight for ranking."""
    try:
        kind = str(story.get("kind", ""))
        base = _DIGEST_WEIGHTS.get(kind, 5)
        # Rivalry games get a bump -- bad blood is a better story.
        try:
            facts = story.get("facts") or {}
            if facts.get("rivalry"):
                base += 3
        except Exception:
            pass
        return base
    except Exception:
        return 0


def deliver_digest(app: Any) -> int:
    """Deliver the day's top stories as an "Around the League" digest.

    Picks the top _DIGEST_MAX stories by weight, delivers each as a headline,
    clears the accumulation. Returns count delivered. Never raises.
    """
    n = 0
    try:
        key = id(app)
        bucket = _DIGEST_STORE.pop(key, None)
        if not bucket:
            return 0
        # Rank by weight, take the top N.
        try:
            ranked = sorted(bucket, key=_story_weight, reverse=True)
        except Exception:
            ranked = bucket
        top = ranked[:_DIGEST_MAX]
        if not top:
            return 0
        try:
            from headlines import deliver_spec as _deliver_spec
        except Exception:
            return 0
        # One digest header, then the stories.
        try:
            _deliver_spec(app, {
                "kind": "league_digest",
                "text": "Around the league tonight:",
                "digest_count": len(top),
            })
        except Exception:
            pass
        for st in top:
            try:
                spec = {
                    "kind": "game_story",
                    "story_kind": st.get("kind", ""),
                    "text": st.get("text", ""),
                    "home": st.get("home", ""),
                    "away": st.get("away", ""),
                    "involved": st.get("involved", ()),
                    "digest": True,  # marks it as from the digest, not live
                }
                if st.get("epithet"):
                    spec["epithet"] = st["epithet"]
                if _deliver_spec(app, spec):
                    n += 1
            except Exception:
                continue
    except Exception:
        pass
    return n


def clear_digest(app: Any) -> None:
    """Drop accumulated stories without delivering (e.g., on load). Never raises."""
    try:
        _DIGEST_STORE.pop(id(app), None)
    except Exception:
        pass
