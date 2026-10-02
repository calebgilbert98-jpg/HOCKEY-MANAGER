"""Scout-speculation FA tiering (D41 Phase 1).

Muck's directive: the NHL/AHL/Euro tags are NOT ground truth -- they're
what YOUR SCOUTS think. A player tagged "AHL" might actually be
NHL-caliber (your scout missed it) or Euro-bound (your scout overrated
him). Bad scouts mistier more often; elite scouts rarely do.

The true tier is hidden. The user only ever sees scout_tier.

Tiers (by true overall_rating):
    NHL  : 78+
    AHL  : 68-77
    Euro : <68  (depth / European-league bound)

Perception noise (deterministic per player+scout, so reports don't flicker):
    JPA 16-20 (elite)   : +/- 2
    JPA 11-15 (solid)   : +/- 5
    JPA  6-10 (suspect) : +/- 8
    JPA  1-5  (guesswork): +/- 12
"""

import hashlib
import random as _random

# True-tier cutoffs on overall_rating()
NHL_CUTOFF = 78
AHL_CUTOFF = 68

TIER_NHL = "NHL"
TIER_AHL = "AHL"
TIER_EURO = "Euro"

_ALL_TIERS = (TIER_NHL, TIER_AHL, TIER_EURO)


def true_tier(player) -> str:
    """Ground-truth tier from the player's actual overall. Never shown to the user."""
    try:
        ovr = int(player.overall_rating())
    except Exception:
        try:
            ovr = int(getattr(player, "overall", 0) or 0)
        except Exception:
            return TIER_EURO
    if ovr >= NHL_CUTOFF:
        return TIER_NHL
    if ovr >= AHL_CUTOFF:
        return TIER_AHL
    return TIER_EURO


def _scout_jpa(scout) -> int:
    """Head-scout eye on the 1-20 EHM scale. Mirrors analytics_scouting._scout_jpa."""
    try:
        raw = int(getattr(scout, "judging_player_ability", 50) or 50)
    except (TypeError, ValueError):
        raw = 50
    raw = max(1, min(100, raw))
    return max(1, min(20, int(round(raw / 5.0))))


def _noise_half_width(jpa: int) -> int:
    """How far off a scout's read can be, by quality."""
    if jpa >= 16:
        return 2
    if jpa >= 11:
        return 5
    if jpa >= 6:
        return 8
    return 12


def _deterministic_seed(player, scout) -> int:
    """Stable seed per player+scout so tiering doesn't flicker between views."""
    try:
        pid = str(getattr(player, "id", getattr(player, "full_name", "p")))
        sid = str(getattr(scout, "id", getattr(scout, "full_name", "s")))
        h = hashlib.md5(f"{pid}|{sid}".encode("utf-8")).hexdigest()
        return int(h[:8], 16)
    except Exception:
        return 0


def perceived_overall(player, scout) -> int:
    """What this scout THINKS the player's overall is. Never raises."""
    try:
        true_ovr = int(player.overall_rating())
    except Exception:
        try:
            true_ovr = int(getattr(player, "overall", 50) or 50)
        except Exception:
            true_ovr = 50
    try:
        jpa = _scout_jpa(scout)
        half = _noise_half_width(jpa)
        rng = _random.Random(_deterministic_seed(player, scout))
        noise = rng.randint(-half, half)
        return max(30, min(99, true_ovr + noise))
    except Exception:
        return true_ovr


def scout_tier_for(player, scout) -> str:
    """The tier this scout assigns. Never raises."""
    try:
        pov = perceived_overall(player, scout)
        if pov >= NHL_CUTOFF:
            return TIER_NHL
        if pov >= AHL_CUTOFF:
            return TIER_AHL
        return TIER_EURO
    except Exception:
        return TIER_AHL


def tier_mismatch(player, scout) -> bool:
    """True when the scout's tier disagrees with ground truth (a hidden gem or a bust)."""
    try:
        return scout_tier_for(player, scout) != true_tier(player)
    except Exception:
        return False


def get_head_scout(team):
    """Find the team's HEAD_SCOUT staffer, or None."""
    try:
        from game_classes import StaffRole
        for s in (getattr(team, "staff", None) or []):
            try:
                if getattr(s, "role", None) == StaffRole.HEAD_SCOUT:
                    return s
            except Exception:
                continue
    except Exception:
        pass
    return None


def tier_player(player, scout) -> str:
    """Assign (and stamp) a scout tier on a player. Returns the tier. Never raises."""
    try:
        tier = scout_tier_for(player, scout)
        player.scout_tier = tier
        try:
            player.scout_tier_by = str(
                getattr(scout, "full_name", getattr(scout, "name", "scout")))
        except Exception:
            pass
        return tier
    except Exception:
        try:
            player.scout_tier = TIER_AHL
        except Exception:
            pass
        return TIER_AHL


def tier_free_agents(league, user_team) -> int:
    """Tier every FA in league.free_agents with the user's head scout's eye.

    Returns the number of players tiered. Never raises.
    """
    try:
        scout = get_head_scout(user_team)
        pool = list(getattr(league, "free_agents", None) or [])
        n = 0
        for p in pool:
            try:
                tier_player(p, scout)
                n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


def retier_on_scout_change(team, league) -> int:
    """Re-tier the FA pool when the head scout changes -- new eyes, new reads.

    Returns the number of players re-tiered. Never raises.
    """
    try:
        return tier_free_agents(league, team)
    except Exception:
        return 0


def backfill_tiers(league, user_team) -> int:
    """Old-save backfill: tier any FA missing a scout_tier. Never raises."""
    try:
        scout = get_head_scout(user_team)
        n = 0
        for p in (getattr(league, "free_agents", None) or []):
            try:
                if not getattr(p, "scout_tier", None):
                    tier_player(p, scout)
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


def tier_summary(league) -> dict:
    """Count FAs per scout tier. Never raises."""
    try:
        counts = {TIER_NHL: 0, TIER_AHL: 0, TIER_EURO: 0, "untiered": 0}
        for p in (getattr(league, "free_agents", None) or []):
            try:
                t = getattr(p, "scout_tier", None)
                if t in counts:
                    counts[t] += 1
                else:
                    counts["untiered"] += 1
            except Exception:
                continue
        return counts
    except Exception:
        return {}
