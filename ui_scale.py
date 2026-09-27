"""UI scale: honors Settings -> Font size (Small / Medium / Large).

Central choke point for type scale. Text factories (ctk_theme.heading /
body, inbox _iwrap, popup title bars) route their sizes through
``scaled()`` so one setting adjusts the whole modern UI. Legacy hardcoded
fonts are out of scope -- new and touched surfaces use the factories.

Scale is read at call time, so changing the setting applies to every
window opened afterwards (no restart needed).
"""

import json
import os

_SCALE = 1.0

_FACTORS = {
    "Small": 0.9,
    "Medium": 1.0,
    "Medium (Current)": 1.0,
    "Large": 1.12,
}


def set_scale(factor: float) -> None:
    global _SCALE
    try:
        _SCALE = max(0.75, min(1.3, float(factor)))
    except Exception:
        _SCALE = 1.0


def get_scale() -> float:
    return _SCALE


def scaled(px) -> int:
    """Scale a point size, keeping a sane floor."""
    try:
        return max(8, int(round(float(px) * _SCALE)))
    except Exception:
        return int(px) if isinstance(px, int) else 12


def scale_from_setting(value: str) -> None:
    set_scale(_FACTORS.get(str(value), 1.0))


def prefs_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "settings.json")


def apply_from_prefs(path: str = None) -> float:
    """Read ui_preferences.font_size from settings.json and apply it."""
    try:
        with open(path or prefs_path()) as f:
            data = json.load(f)
        value = ((data.get("ui_preferences") or {}).get("font_size")
                 or "Medium (Current)")
        scale_from_setting(value)
    except Exception:
        set_scale(1.0)
    return _SCALE
