"""UI scale: 5 text-size tiers + live font registry + windowed auto-fit.

Central choke point for type scale across the app.

- Settings -> Font size offers five tiers: Compact / Small / Default /
  Large / Extra Large. Old setting values ("Small", "Medium (Current)",
  "Large") migrate automatically.
- ``font(family, size, weight)`` returns a real ``tkinter.font.Font``
  registered for live rescaling: changing the tier resizes every open
  window's text instantly, no restart, no reopen.
- ``scaled(px)`` is kept for call-time users (ctk_theme, canvas code that
  can't hold Font objects).
- Windowed auto-fit (Settings -> "Auto-fit text to window size"): a
  debounced <Configure> listener on the root derives a multiplier from
  the window size vs a 1600x900 design baseline and applies it on top of
  the tier base, so shrinking the window shrinks text instead of
  clipping it, and big monitors get proportionally larger text.
- ``card_size(w, h)`` scales fixed popup-card geometry by the same
  effective factor so cards don't clip their own content at Large/XL.

Effective scale = tier_base x auto_factor (auto_factor is 1.0 unless
auto-fit is enabled).
"""

import json
import os

# ---------------------------------------------------------------- tiers
_TIERS = {
    "Compact": 0.85,
    "Small": 0.925,
    "Default": 1.0,
    "Large": 1.12,
    "Extra Large": 1.25,
}
TIER_NAMES = list(_TIERS)

# Old setting values -> new tier names.
_LEGACY_TIERS = {
    "Small": "Small",
    "Medium": "Default",
    "Medium (Current)": "Default",
    "Large": "Large",
}

_BASELINE_W, _BASELINE_H = 1600.0, 900.0

_tier_base = 1.0
_auto_factor = 1.0
_auto_enabled = False
_tier_name = "Default"


def _effective() -> float:
    return max(0.7, min(1.35, _tier_base * _auto_factor))


def get_scale() -> float:
    """Effective scale factor (tier x auto-fit)."""
    return _effective()


def get_tier_name() -> str:
    return _tier_name


def tier_factor(name: str) -> float:
    return _TIERS.get(_LEGACY_TIERS.get(str(name), str(name)), 1.0)


def normalize_tier_name(value: str) -> str:
    v = str(value)
    return _LEGACY_TIERS.get(v, v) if v not in _TIERS else v


# ---------------------------------------------------------------- live font registry
_registry = []  # list of (tkinter.font.Font, base_size)
_scale_listeners = []  # callbacks invoked after every effective-scale change


def on_scale_change(callback) -> None:
    """Subscribe to effective-scale changes (tier or auto-fit).

    Use for layout reflows that depend on text metrics (e.g. reflowing
    a chip row when fonts grow). Callbacks run on the calling thread;
    keep them cheap and exception-safe (they are guarded).
    """
    if callable(callback) and callback not in _scale_listeners:
        _scale_listeners.append(callback)


def _notify_scale_listeners() -> None:
    for cb in list(_scale_listeners):
        try:
            cb()
        except Exception:
            pass


def _make_font(family, size, weight):
    """Build the Font object (or a tuple fallback pre-root/headless)."""
    try:
        import tkinter.font as tkfont
        import tkinter as tk
        # Ensure a default root exists for the Font constructor.
        try:
            tk._default_root.update_idletasks()  # noqa: SLF001
        except Exception:
            pass
        return tkfont.Font(family=family,
                           size=max(6, int(round(float(size) * _effective()))),
                           weight=weight or "normal")
    except Exception:
        # Headless / pre-root: fall back to a plain tuple; the caller
        # still gets a valid font spec.
        return (family, size, weight) if weight else (family, size)


def font(family, size, weight=""):
    """Create a scale-aware Font, registered for live rescaling.

    Use instead of ``font=(family, size, weight)`` tuples on any surface
    that should honor Settings -> Font size. The returned Font object is
    kept alive by the registry; changing the tier resizes it in place.
    Safe to call before a Tk root exists only if one is created later --
    in practice every caller runs after the app root exists.
    """
    f = _make_font(family, size, weight)
    try:
        import tkinter.font as tkfont
        if isinstance(f, tkfont.Font):
            _registry.append((f, float(size)))
    except Exception:
        pass
    return f


def _apply_to_registry() -> None:
    eff = _effective()
    for f, base in list(_registry):
        try:
            f.configure(size=max(6, int(round(base * eff))))
        except Exception:
            pass
    for key, f in list(_cache.items()):
        try:
            f.configure(size=max(6, int(round(_cache_base[key] * eff))))
        except Exception:
            pass
    _notify_scale_listeners()


_cache = {}       # (family, size, weight) -> tkinter.font.Font
_cache_base = {}  # (family, size, weight) -> base size


def get(family, size, weight=""):
    """Cached scale-aware Font: same spec returns the same live object.

    Use for shared constants (e.g. AppFonts) where every attribute
    access must not mint a new Font. Changing the tier resizes the
    cached fonts in place, just like :func:`font`.
    """
    key = (str(family), float(size), str(weight or "normal"))
    f = _cache.get(key)
    if f is not None:
        return f
    f = _make_font(family, size, weight)
    try:
        import tkinter.font as tkfont
        if isinstance(f, tkfont.Font):
            _cache[key] = f
            _cache_base[key] = float(size)
    except Exception:
        pass
    return f


def scaled(px) -> int:
    """Scale a point size at call time (for code holding raw sizes)."""
    try:
        return max(8, int(round(float(px) * _effective())))
    except Exception:
        return int(px) if isinstance(px, int) else 12


def card_size(width, height):
    """Scale fixed popup-card geometry by the effective factor."""
    eff = _effective()
    try:
        return int(round(float(width) * eff)), int(round(float(height) * eff))
    except Exception:
        return int(width), int(height)


# ---------------------------------------------------------------- setters
def set_tier(name: str) -> float:
    """Set the base tier; live-applies to all registered fonts."""
    global _tier_base, _tier_name
    _tier_name = normalize_tier_name(name)
    _tier_base = tier_factor(_tier_name)
    _apply_to_registry()
    return _effective()


def set_scale(factor: float) -> None:
    """Legacy entry point: treat as a direct tier-base override."""
    global _tier_base
    try:
        _tier_base = max(0.7, min(1.35, float(factor)))
    except Exception:
        _tier_base = 1.0
    _tier_name = "Custom"
    _apply_to_registry()


def scale_from_setting(value: str) -> None:
    set_tier(value)


def set_auto_factor(factor: float) -> float:
    global _auto_factor
    try:
        _auto_factor = max(0.8, min(1.2, float(factor)))
    except Exception:
        _auto_factor = 1.0
    _apply_to_registry()
    return _effective()


def set_auto_enabled(enabled: bool) -> None:
    global _auto_enabled
    _auto_enabled = bool(enabled)
    if not _auto_enabled:
        set_auto_factor(1.0)


def auto_factor_for(width, height) -> float:
    """Multiplier for a window of the given pixel size."""
    try:
        w, h = float(width), float(height)
        if w < 50 or h < 50:
            return 1.0
        return max(0.8, min(1.2, min(w / _BASELINE_W, h / _BASELINE_H)))
    except Exception:
        return 1.0


def bind_auto_fit(root) -> None:
    """Debounced <Configure> listener: shrink/grow text with the window.

    No-op unless auto-fit is enabled in prefs. Safe to call once at
    startup; the binding is additive.
    """
    state = {"timer": None}

    def _recompute():
        state["timer"] = None
        if not _auto_enabled:
            return
        try:
            set_auto_factor(
                auto_factor_for(root.winfo_width(), root.winfo_height()))
        except Exception:
            pass

    def _debounced(_event=None):
        try:
            if state["timer"] is not None:
                root.after_cancel(state["timer"])
            state["timer"] = root.after(250, _recompute)
        except Exception:
            pass

    try:
        root.bind("<Configure>", _debounced, add="+")
        root.after_idle(_recompute)
    except Exception:
        pass


# ---------------------------------------------------------------- prefs
def prefs_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "settings.json")


def read_prefs(path: str = None):
    """Return (tier_name, auto_fit_enabled) from settings.json."""
    try:
        with open(path or prefs_path()) as f:
            data = json.load(f)
        ui = data.get("ui_preferences") or {}
        tier = normalize_tier_name(ui.get("font_size") or "Default")
        if tier not in _TIERS:
            tier = "Default"
        return tier, bool(ui.get("auto_fit_ui", False))
    except Exception:
        return "Default", False


def apply_from_prefs(path: str = None) -> float:
    """Read prefs and apply tier + auto-fit flag. Returns eff. scale."""
    tier, auto = read_prefs(path)
    set_tier(tier)
    set_auto_enabled(auto)
    return _effective()
