"""Save/Load screen: save game / load game tiles + last-save info.

Writes go through enqueue_command("save_game") / enqueue_command("load_game");
the parent wires the executors in web_ui.bridge._execute_command. Load is
destructive, so the UI confirms before enqueueing.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, enqueue_command  # noqa: F401 (queued via /api/command)

bp = Blueprint("save", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _last_save_info(app):
    """Defensively discover last-save metadata from the live game."""
    candidates = [
        lambda: app.last_save,
        lambda: app.game_manager.last_save,
        lambda: app.save_manager.last_save_file,
        lambda: app.game_manager.save_manager.last_save_file,
        lambda: app.save_file,
        lambda: app.game_manager.save_file,
    ]
    for fn in candidates:
        v = _safe(fn)
        if v:
            return str(v)
    return None


def get_save_info(app):
    """JSON-safe save/load state, all reads defensive."""
    gm = _safe(lambda: app.game_manager)
    cur = _safe(lambda: getattr(gm, "current_date", None))
    date_str = _safe(lambda: cur.strftime("%B %d, %Y")) if cur else None
    return {
        "last_save": _last_save_info(app),
        "current_date": date_str,
        "team": _safe(lambda: getattr(getattr(app, "user_team", None),
                                      "team_name", None)),
    }


@bp.route("/save")
def save_page():
    return render_template("save.html")


@bp.route("/api/save")
def api_save():
    live = _live()
    if live is None:
        return jsonify({"last_save": None, "current_date": None,
                        "team": None})
    return jsonify(get_save_info(live))
