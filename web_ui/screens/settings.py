"""Settings screen: full read/write parity with the desktop SettingsWindow.

Desktop parity (settings_window.py): the 5 tabs (Game Results, Interface,
Simulation, Notifications, Career) read from settings.json merged over
built-in defaults via settings_window.load_settings() -- no GUI
involved -- and writes persist to the same settings.json the desktop
writes (settings_window.SettingsWindow._save_settings).

Every write path is verified: after persisting, the value is read back
through load_settings() and must match, or the write is reported as
failed. Reads never construct a SettingsWindow (the desktop's own
main.get_settings headless pattern).

Behavior notes:
- simulation.auto_continue_non_game_days and
  simulation.always_show_daily_results drive the hub's Continue flow
  (the web hub reads them on load).
- simulation.scoring_level / draft_class_quality are read by the game
  engine the same way the desktop reads them (settings.json is the
  single source of truth both UIs share).
"""
import json
import os

from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe

bp = Blueprint("settings", __name__)

_TAB_TITLES = {
    "game_results": "Game Results",
    "ui_preferences": "Interface",
    "simulation": "Simulation",
    "notifications": "Notifications",
    "career": "Career",
}

# Field layout: (label, key, widget, options-or-None, hint)
# widget: "bool" | "select" | "text" | "multiselect"
# For "multiselect" the stored value is a JSON list of strings.
_FIELDS = {
    "game_results": [
        ("Show only my team's games by default", "show_user_team_only",
         "bool", None, ""),
        ("Default leagues to display", "default_leagues", "multiselect",
         ["National Hockey League", "American Hockey League"], ""),
        ("Maximum games to display", "max_games_display", "select",
         ["25", "50", "100", "200", "All"], "Recommended: 50 for performance"),
        ("Maximum news items to display", "max_news_display", "select",
         ["5", "10", "20", "50", "All"], ""),
        ("Default news categories to display", "default_news_categories",
         "multiselect",
         ["Team News", "League News", "Trades", "Injuries", "Contracts",
          "Draft"], ""),
    ],
    "ui_preferences": [
        ("Theme", "theme", "select", ["Dark (Current)"], ""),
        ("Font size", "font_size", "select",
         ["Compact", "Small", "Default", "Large", "Extra Large"],
         "Applies instantly to most windows."),
        ("Automatically close settings after saving", "auto_close_settings",
         "bool", None, ""),
        ("Remember window positions and sizes", "remember_window_positions",
         "bool", None, ""),
        ("Auto-fit text size to window size", "auto_fit_ui", "bool", None, ""),
    ],
    "simulation": [
        ("Auto-continue through non-game days", "auto_continue_non_game_days",
         "bool", None, "Drives the hub Continue flow."),
        ("Always show daily results window", "always_show_daily_results",
         "bool", None, "Show the daily results after each advance."),
        ("Use visual game viewer for my team's games", "use_game_viewer",
         "bool", None, ""),
        ("Game viewer mode", "game_viewer_mode", "select",
         ["Full Game", "Highlights Only", "Fast Forward"], ""),
        ("Draft class quality", "draft_class_quality", "select",
         ["Weak", "Normal", "Strong", "Generational"],
         "Applies to future draft classes."),
        ("Scoring level", "scoring_level", "select",
         ["Low (Current)", "Medium (NHL Baseline)", "High (Arcade)"],
         "Goals per game: ~5.5 / ~6.0 / 7+"),
    ],
    "notifications": [
        ("Email: Trade Offers", "email_Trade Offers", "emailbool", None, ""),
        ("Email: Contract Expiring Soon",
         "email_Contract Expiring Soon", "emailbool", None, ""),
        ("Email: Injury Reports", "email_Injury Reports", "emailbool", None, ""),
        ("Email: Player Milestones", "email_Player Milestones", "emailbool",
         None, ""),
        ("Email: League News", "email_League News", "emailbool", None, ""),
        ("Email: Draft Updates", "email_Draft Updates", "emailbool", None, ""),
        ("Enable sound effects", "enable_sounds", "bool", None, ""),
        ("Sound volume", "sound_volume", "select",
         ["Off", "Low", "Medium", "High"], ""),
    ],
    "career": [
        ("Board can sack the GM (job is on the line)", "gm_can_be_sacked",
         "bool", None,
         "If off, your job is safe no matter what -- board confidence "
         "still affects budgets and morale."),
    ],
}


def _sw():
    """settings_window module (the game's settings module). Never raises."""
    try:
        import settings_window
        return settings_window
    except Exception:
        return None


def _settings_path():
    sw = _sw()
    if sw is None:
        return None
    return os.path.join(os.path.dirname(sw.__file__), "settings.json")


def _read_settings():
    """Full settings dict via the game's own loader (defaults merged)."""
    sw = _sw()
    if sw is None:
        return {}
    try:
        return sw.load_settings() or {}
    except Exception:
        return {}


def _field_value(tab, key, settings):
    sec = settings.get(tab, {}) if isinstance(settings, dict) else {}
    if key.startswith("email_"):
        emails = (sec.get("email_notifications", {}) or {})
        return bool(emails.get(key[len("email_"):], False))
    return sec.get(key)


def get_settings(app=None):
    """JSON-safe, editable settings snapshot. All reads defensive."""
    settings = _read_settings()
    out = {"tabs": [], "readonly": False,
           "note": "Changes save to settings.json -- the same file the "
                   "desktop game reads."}
    for tab, title in _TAB_TITLES.items():
        items = []
        for label, key, widget, options, hint in _FIELDS.get(tab, []):
            v = _field_value(tab, key, settings)
            items.append({
                "label": label, "key": key, "widget": widget,
                "options": options or [],
                "value": v if widget != "multiselect"
                else (list(v) if isinstance(v, list) else []),
                "hint": hint,
            })
        out["tabs"].append({"id": tab, "title": title, "items": items})
    return out


def _validate(tab, key, value):
    """Validate one write against the field layout. Returns
    (ok, coerced_value, error)."""
    fields = {f[1]: f for f in _FIELDS.get(tab, [])}
    if key not in fields:
        return False, None, f"unknown setting {tab}.{key}"
    label, _k, widget, options, _hint = fields[key]
    if widget in ("bool", "emailbool"):
        if isinstance(value, bool):
            return True, value, ""
        if isinstance(value, str) and value.lower() in ("true", "1", "on"):
            return True, True, ""
        if isinstance(value, str) and value.lower() in ("false", "0", "off"):
            return True, False, ""
        return False, None, f"{label}: expected true/false"
    if widget == "select":
        v = str(value)
        if options and v not in options:
            return False, None, (f"{label}: {v!r} not one of "
                                 f"{', '.join(options)}")
        return True, v, ""
    if widget == "multiselect":
        if not isinstance(value, list):
            return False, None, f"{label}: expected a list"
        vals = [str(x) for x in value]
        bad = [x for x in vals if x not in (options or [])]
        if bad:
            return False, None, f"{label}: invalid choices {bad}"
        return True, vals, ""
    return False, None, f"{label}: unsupported widget {widget}"


def set_setting(tab, key, value):
    """Write one setting through the game's settings module: load,
    patch, persist to settings.json, then READ BACK and verify the
    value stuck. Returns (ok, message)."""
    ok, coerced, err = _validate(tab, key, value)
    if not ok:
        return False, err
    sw = _sw()
    path = _settings_path()
    if sw is None or path is None:
        return False, "settings module unavailable"
    try:
        settings = sw.load_settings() or {}
    except Exception as e:
        return False, f"could not load settings: {e}"
    settings.setdefault(tab, {})
    if key.startswith("email_"):
        settings[tab].setdefault("email_notifications", {})
        settings[tab]["email_notifications"][key[len("email_"):]] = coerced
    else:
        settings[tab][key] = coerced
    try:
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        return False, f"could not save settings.json: {e}"
    # Read-back verification: the write only counts if the game's own
    # loader returns the new value (this is the same persistence the
    # desktop game reads on every launch and via main.get_settings).
    try:
        reloaded = sw.load_settings() or {}
        back = _field_value(tab, key, reloaded)
        if back != coerced:
            return False, (f"write did not stick: read back {back!r}, "
                           f"expected {coerced!r}")
    except Exception as e:
        return False, f"read-back failed: {e}"
    return True, "saved"


@bp.route("/settings")
def settings_page():
    return render_template("settings.html")


@bp.route("/api/settings")
def api_settings():
    return jsonify(get_settings())


@bp.route("/api/settings", methods=["POST"])
def api_settings_write():
    """Write one setting: {"tab", "key", "value"}. Validated, persisted
    to settings.json, read back and verified. Returns the verified value
    so the UI can confirm the change actually landed."""
    data = request.get_json(force=True, silent=True) or {}
    tab = str(data.get("tab") or "")
    key = str(data.get("key") or "")
    if tab not in _TAB_TITLES or not key:
        return jsonify({"ok": False,
                        "error": "tab and key required"}), 400
    ok, msg = set_setting(tab, key, data.get("value"))
    if not ok:
        return jsonify({"ok": False, "error": msg}), 422
    # Verified value, re-read from the game's loader (drives real game
    # behavior on the next read, exactly like the desktop).
    back = _field_value(tab, key, _read_settings())
    return jsonify({"ok": True, "tab": tab, "key": key, "value": back,
                    "message": msg})
