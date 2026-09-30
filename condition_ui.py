# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Condition display helpers -- W6 (condition visibility on UI screens).

The canonical per-player condition (0-100) is owned by W3's
condition_system.get_condition(player). Every helper here is deliberately
defensive: if condition_system is not importable yet (W3 still building it)
or the player carries no persisted condition, the helpers fall back to
getattr(player, 'condition', 100) and never raise, so UI screens can call
them unconditionally without crashing.

Shared color scale / labels -- used by every screen for consistency:

    90-100  Fresh   green        #3fb950
    70-89   Good    light green  #8fd14f
    50-69   Worn    amber        #d29922
    0-49    Gassed  red          #f85149
"""

# Band floors (0-100 scale)
FRESH_FLOOR = 90
GOOD_FLOOR = 70
WORN_FLOOR = 50

LABEL_FRESH = "Fresh"
LABEL_GOOD = "Good"
LABEL_WORN = "Worn"
LABEL_GASSED = "Gassed"

COLOR_FRESH = "#3fb950"   # green  (matches AppColors.SUCCESS)
COLOR_GOOD = "#8fd14f"    # light green
COLOR_WORN = "#d29922"    # amber  (matches AppColors.WARNING)
COLOR_GASSED = "#f85149"  # red    (matches AppColors.DANGER)


def get_condition(player):
    """Canonical 0-100 condition for a player.

    Prefers W3's condition_system.get_condition(player) when available;
    falls back to getattr(player, 'condition', 100). Never raises.
    """
    try:
        import condition_system as _cs
        _fn = getattr(_cs, "get_condition", None)
        if callable(_fn):
            try:
                return _clamp(_fn(player))
            except Exception:
                pass
    except Exception:
        pass
    try:
        return _clamp(getattr(player, "condition", 100))
    except Exception:
        return 100


def condition_label(cond):
    """Band label for a 0-100 condition value: Fresh / Good / Worn / Gassed."""
    try:
        c = int(cond)
    except Exception:
        return LABEL_GOOD
    if c >= FRESH_FLOOR:
        return LABEL_FRESH
    if c >= GOOD_FLOOR:
        return LABEL_GOOD
    if c >= WORN_FLOOR:
        return LABEL_WORN
    return LABEL_GASSED


def condition_color(cond):
    """Hex color for a 0-100 condition value (works in tk, ttk and ctk)."""
    try:
        c = int(cond)
    except Exception:
        return COLOR_GOOD
    if c >= FRESH_FLOOR:
        return COLOR_FRESH
    if c >= GOOD_FLOOR:
        return COLOR_GOOD
    if c >= WORN_FLOOR:
        return COLOR_WORN
    return COLOR_GASSED


def condition_text(player):
    """Compact display text for a player, e.g. '82 (Good)'. Never raises."""
    cond = get_condition(player)
    return f"{cond} ({condition_label(cond)})"


def injury_status(player):
    """Injury status string, or None when the player is healthy/unknown.

    Never raises.
    """
    try:
        s = getattr(player, "injury_status", None)
        if s is None:
            return None
        s = str(s).strip()
        if not s or s.lower() in ("healthy", "none", "ok", "fit"):
            return None
        return s
    except Exception:
        return None


def _clamp(v):
    try:
        v = int(round(float(v)))
    except Exception:
        return 100
    return max(0, min(100, v))
