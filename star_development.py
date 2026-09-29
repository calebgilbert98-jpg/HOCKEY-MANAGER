"""Item 8: season star counts feed monthly player development.

Wraps (never modifies) the PlayerDevelopmentEngine at its call site in
main.GameManager._process_monthly_development. Star-level play adds a
small nudge alongside the engine's own attribute changes:

- Young players (age <= STAR_DEV_YOUNG_MAX_AGE) piling up stars are
  BREAKING OUT: a few attributes tick up this month.
- Veterans (age >= STAR_DEV_VETERAN_MIN_AGE) starring are AT/NEAR PEAK:
  the engine's age-related decline this month is resisted (softened, never
  flipped positive) -- the same direction the veteran machinery already
  moves, just less far.
- Prime-age players (25-31): untouched.
- No stars: the function is a no-op; existing behavior is unchanged.

Monthly star deltas are tracked against a per-player snapshot
(``player._star_dev_last_seen``) so each tick only credits stars earned
since the last one. Season-ledger resets are handled: if the snapshot is
ahead of the ledger (rollover), the delta counts from the fresh ledger.
"""

import random
from typing import Any, Dict, Optional

# ----------------------------------------------------------------------
# Named constants (all conservative; additive alongside engine output).
# ----------------------------------------------------------------------
STAR_DEV_YOUNG_MAX_AGE = 24      # <= this age counts as young / breaking out
STAR_DEV_VETERAN_MIN_AGE = 32    # >= this age counts as veteran (matches
                                 # DevelopmentStage.VETERAN: 32-35,
                                 # "Gradual decline", and reputation_system
                                 # VETERAN_AGE = 32)
STAR_DEV_MONTHLY_MIN_STARS = 2   # stars earned since the last tick to trigger
STAR_DEV_YOUNG_ATTRS = 3         # attributes nudged per young breakout month
STAR_DEV_YOUNG_BUMP = 1          # +1 per nudged attribute (clamped 1..100)
STAR_DEV_VETERAN_RESIST = 1      # age decline softened by this much per
                                 # attribute this month (a -1 decline flattens
                                 # to 0; a -2 becomes -1; never flips +)

# Developable attribute names, mirroring the engine's list in
# PlayerDevelopmentEngine.process_monthly_development (read-only copy;
# the engine itself is never modified).
_SKATER_DEVELOPABLE = (
    "skating", "shooting", "passing", "checking", "defense",
    "hockey_iq", "determination", "leadership", "strength",
    "conditioning", "faceoffs",
)
_GOALIE_DEVELOPABLE = ("goaltending", "reflexes", "positioning")


def _is_goalie(player: Any) -> bool:
    try:
        return getattr(getattr(player, "primary_position", None),
                       "name", "") == "GOALIE"
    except Exception:
        return False


def _monthly_star_delta(player: Any) -> int:
    """Stars earned since the last monthly tick (season reset-safe)."""
    counts = getattr(player, "game_stars", None)
    cur = {"first": 0, "second": 0, "third": 0}
    if isinstance(counts, dict):
        for k in cur:
            try:
                cur[k] = int(counts.get(k, 0) or 0)
            except Exception:
                cur[k] = 0
    seen = getattr(player, "_star_dev_last_seen", None)
    if isinstance(seen, dict):
        try:
            delta = {k: cur[k] - int(seen.get(k, 0) or 0) for k in cur}
        except Exception:
            delta = dict(cur)
        if any(v < 0 for v in delta.values()):
            # Season rolled over (ledger reset to zeros after the snapshot
            # was taken): count from the fresh ledger, not the stale one.
            delta = dict(cur)
    else:
        delta = dict(cur)
    try:
        player._star_dev_last_seen = dict(cur)
    except Exception:
        pass
    return sum(max(0, v) for v in delta.values())


def apply_star_monthly_nudge(player: Any,
                             engine_changes: Optional[Dict[str, int]] = None,
                             rng: Any = None) -> Dict[str, int]:
    """Apply this month's star-based development nudge.

    ``engine_changes`` is the {attr: delta} dict the engine already applied
    this month (negative deltas are age decline for veterans). This
    function applies its own attribute changes directly to the player and
    returns its own {attr: delta} so the call site can merge them into the
    engine's dict (news + archetype refresh stay consistent).

    Returns {} -- and changes nothing -- when the player earned fewer than
    STAR_DEV_MONTHLY_MIN_STARS stars since the last tick.
    """
    changes: Dict[str, int] = {}
    try:
        age = int(getattr(player, "age", 99) or 99)
    except Exception:
        age = 99
    if _monthly_star_delta(player) < STAR_DEV_MONTHLY_MIN_STARS:
        return changes
    if rng is None:
        rng = random

    if age <= STAR_DEV_YOUNG_MAX_AGE:
        # Breakout nudge: a young player starring regularly gets a few
        # attributes ticking up, in the same direction the engine already
        # grows young players.
        attrs = [a for a in _SKATER_DEVELOPABLE if hasattr(player, a)]
        if _is_goalie(player):
            attrs += [a for a in _GOALIE_DEVELOPABLE if hasattr(player, a)]
        try:
            picks = rng.sample(attrs, min(STAR_DEV_YOUNG_ATTRS, len(attrs)))
        except Exception:
            picks = []
        for attr in picks:
            try:
                cur = int(getattr(player, attr, 50) or 50)
            except Exception:
                cur = 50
            new = max(1, min(100, cur + STAR_DEV_YOUNG_BUMP))
            bump = new - cur
            if bump:
                try:
                    setattr(player, attr, new)
                    changes[attr] = changes.get(attr, 0) + bump
                except Exception:
                    pass
    elif age >= STAR_DEV_VETERAN_MIN_AGE:
        # Peak/plateau: the veteran machinery moves attributes downward this
        # month; starring veterans resist it. Each negative change is
        # softened by STAR_DEV_VETERAN_RESIST, never flipped positive.
        for attr, ch in (engine_changes or {}).items():
            if not isinstance(ch, (int, float)) or ch >= 0:
                continue
            softened = min(0, ch + STAR_DEV_VETERAN_RESIST)
            restore = softened - ch
            if restore <= 0:
                continue
            try:
                cur = int(getattr(player, attr, 50) or 50)
            except Exception:
                cur = 50
            new = max(1, min(100, cur + int(round(restore))))
            gained = new - cur
            if gained:
                try:
                    setattr(player, attr, new)
                    changes[attr] = changes.get(attr, 0) + gained
                except Exception:
                    pass
    # Prime-age players (25-31): no star development effect by design.
    return changes
