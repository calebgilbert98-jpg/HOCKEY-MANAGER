"""Settings screen: view game settings (read-only v1).

Editing a setting is a follow-up: it needs an `update_settings` command
wired into web_ui.bridge._execute_command.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, enqueue_command  # noqa: F401 (exported for future use)

bp = Blueprint("settings", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


class _Missing:
    pass


_MISSING = _Missing()


# category -> list of (label, attr path candidates, fmt)
_SETTINGS_LAYOUT = [
    ("Gameplay", [
        ("Difficulty", ["difficulty", "game_difficulty"], None),
        ("Season length", ["season_length"], None),
        ("Season start", ["season_start_type"], None),
        ("Fantasy draft", ["fantasy_draft"], "bool"),
    ]),
    ("League systems", [
        ("Salary cap", ["salary_cap_enabled"], "bool"),
        ("Financial realism", ["financial_realism_enabled"], "bool"),
        ("Trades", ["trades_enabled"], "bool"),
        ("Trade difficulty", ["trade_difficulty_modifier"], "mult"),
        ("Injuries", ["injuries_enabled"], "bool"),
        ("Entry draft", ["draft_enabled"], "bool"),
        ("Playoffs", ["playoffs_enabled"], "bool"),
    ]),
    ("Development & morale", [
        ("Rookie development rate", ["rookie_development_rate"], "mult"),
        ("Morale system", ["morale_system_enabled"], "bool"),
        ("Player personalities", ["player_personalities_enabled"], "bool"),
    ]),
    ("Media & display", [
        ("Media pressure", ["media_pressure_enabled"], "bool"),
        ("Media engagement", ["media_engagement"], None),
        ("Composite ratings", ["show_composite_ratings"], "bool"),
    ]),
]


def _get_first(obj, names):
    """First readable attr (or startup_settings dict key) among names."""
    for name in names:
        v = _safe(lambda n=name: getattr(obj, n, _MISSING), _MISSING)
        if not isinstance(v, _Missing):
            return v
    return _MISSING


class _Missing:
    pass


_MISSING = _Missing()


def _fmt(value, kind):
    if isinstance(value, _Missing) or value is None:
        return None
    if kind == "bool":
        return "On" if bool(value) else "Off"
    if kind == "mult":
        try:
            return f"{float(value):.2f}x"
        except (TypeError, ValueError):
            return None
    return str(value)


def get_settings(app):
    """JSON-safe settings snapshot, all reads defensive."""
    gm = _safe(lambda: app.game_manager)
    raw = _safe(lambda: getattr(gm, "startup_settings", None) or
                getattr(app, "startup_settings", None) or {}, {})
    raw = raw if isinstance(raw, dict) else {}

    out = {"categories": [], "readonly": True,
           "note": "Settings are read-only in the web UI for now. Changing "
                   "them needs an `update_settings` command."}
    missing_api = 0
    for cat, rows in _SETTINGS_LAYOUT:
        items = []
        for label, names, kind in rows:
            v = _get_first(gm, names)
            if v is _MISSING:
                # fall back to the raw startup dict (camel/underscore keys)
                v = _MISSING
                for n in names:
                    if n in raw:
                        v = raw[n]
                        break
            text = _fmt(v, kind)
            if text is None:
                missing_api += 1
            items.append({"label": label, "value": text})
        out["categories"].append({"title": cat, "items": items})
    if missing_api:
        out["note"] += (f" {missing_api} value(s) could not be read from the "
                        "live game and need a settings API.")
    return out


@bp.route("/settings")
def settings_page():
    return render_template("settings.html")


@bp.route("/api/settings")
def api_settings():
    live = _live()
    if live is None:
        return jsonify({"categories": [], "readonly": True,
                        "note": "No live game connected."})
    return jsonify(get_settings(live))
