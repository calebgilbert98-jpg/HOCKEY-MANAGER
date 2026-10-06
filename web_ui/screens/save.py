"""Save/Load screen: REAL in-page save/load (no Tk windows).

The old flow queued "save_game"/"load_game", which opened the hidden Tk
SaveLoadView — an invisible, unusable window. This module drives the
real GameSaveManager through the Flask backend instead:

  GET  /api/save/list     — saves in the saves dir (JSON-safe metadata)
  POST /api/save/do       — {name?, nonce} enqueue in-page save
  POST /api/save/load     — {save_id, nonce} enqueue in-page load
  POST /api/save/delete   — {save_id, nonce} enqueue in-page delete
  GET  /api/save/result   — poll the queued op outcome (?nonce=)

Writes go through enqueue_command("save_game_web" / "load_game_web" /
"delete_save_web"); the Tk-thread executors live in web_ui.bridge and
stash outcomes on app._web_save_result. tkinter.messagebox is
suppressed during the calls so failures report in-page.
"""
import os
import uuid

from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, enqueue_command

bp = Blueprint("save", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _save_manager(live):
    from web_ui.bridge import _web_save_manager
    return _web_save_manager(live) if live is not None else None


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


@bp.route("/api/save/list")
def api_save_list():
    """All save files with metadata + autosave status. Read-only."""
    live = _live()
    if live is None:
        return jsonify({"saves": [], "autosave": {"enabled": False}})
    try:
        from web_ui.bridge import _web_saves_dir
        sm = _save_manager(live)
        if sm is None:
            return jsonify({"saves": [], "autosave": {"enabled": False}})
        base = _web_saves_dir(sm)
        files = _safe(lambda: sm.get_save_files(), []) or []
        out = []
        for f in files:
            try:
                if not isinstance(f, dict):
                    continue
                fp = f.get("filepath", "") or ""
                rel = os.path.relpath(fp, base) if fp else ""
                mod = f.get("modified")
                mod_s = (mod.strftime("%Y-%m-%d %H:%M")
                         if hasattr(mod, "strftime") else str(mod or ""))
                out.append({
                    "id": rel,
                    "filename": str(f.get("filename", "")),
                    "team": str(f.get("team", "Unknown") or "Unknown"),
                    "game_date": str(f.get("game_date", "Unknown")
                                     or "Unknown"),
                    "modified": mod_s,
                    "size_kb": int((f.get("size") or 0) // 1024),
                    "is_autosave": bool(f.get("is_autosave")),
                    "category": str(f.get("category", "General")
                                    or "General"),
                    "description": str(f.get("description", "") or ""),
                })
            except Exception:
                continue
        last_auto = _safe(lambda: sm.last_autosave)
        auto = {
            "enabled": bool(_safe(lambda: sm.autosave_enabled, False)),
            "frequency_days": int(_safe(
                lambda: sm.autosave_frequency, 0) or 0),
            "last": (last_auto.strftime("%Y-%m-%d %H:%M")
                     if hasattr(last_auto, "strftime") else None),
            "directory": base,
        }
        return jsonify({"saves": out, "autosave": auto})
    except Exception as e:
        return jsonify({"saves": [], "autosave": {"enabled": False},
                        "error": str(e)})


def _nonce(data):
    n = (data.get("nonce") or "").strip() if isinstance(data, dict) else ""
    return n or uuid.uuid4().hex[:12]


@bp.route("/api/save/do", methods=["POST"])
def api_save_do():
    """Enqueue an in-page save with an optional custom name."""
    data = request.get_json(force=True, silent=True) or {}
    nonce = _nonce(data)
    ok = enqueue_command("save_game_web",
                         name=str(data.get("name") or ""), nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/save/load", methods=["POST"])
def api_save_load():
    """Enqueue an in-page load of a save chosen on the page."""
    data = request.get_json(force=True, silent=True) or {}
    nonce = _nonce(data)
    ok = enqueue_command("load_game_web",
                         save_id=str(data.get("save_id") or ""),
                         nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/save/delete", methods=["POST"])
def api_save_delete():
    """Enqueue an in-page save deletion."""
    data = request.get_json(force=True, silent=True) or {}
    nonce = _nonce(data)
    ok = enqueue_command("delete_save_web",
                         save_id=str(data.get("save_id") or ""),
                         nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/save/result")
def api_save_result():
    """Poll the outcome of a queued save/load/delete (?nonce=)."""
    live = _live()
    nonce = (request.args.get("nonce") or "").strip()
    r = _safe(lambda: getattr(live, "_web_save_result", None)) \
        if live is not None else None
    if not r or (nonce and str(r.get("nonce") or "") != nonce):
        return jsonify({"pending": True})
    return jsonify({"pending": False, "result": {
        "ok": bool(r.get("ok")),
        "message": str(r.get("message") or ""),
    }})
