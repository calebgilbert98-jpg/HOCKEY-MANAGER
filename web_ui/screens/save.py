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

from web_ui.bridge import _safe, enqueue_command, _resolve_gm

bp = Blueprint("save", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _save_manager(live):
    from web_ui.bridge import _web_save_manager, _resolve_gm
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
        from web_ui.bridge import _web_saves_dir, _resolve_gm
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


# ======================================================================
# Batch E (2026-10-06): multiplayer client snapshot load.
#
# A joining client has no game yet -- it holds only a MultiplayerClient
# connection from the setup page. When the host starts the league,
# POST /api/mp/apply_snapshot {save_b64} builds the full local game
# from the host's snapshot bytes on the Tk main thread (the same
# restore path the desktop client's _apply_multiplayer_snapshot uses),
# points user_team at the claimed club (or flags spectator mode), and
# attaches the client so day-advance syncs keep flowing.
# Poll the outcome with GET /api/save/result?nonce=.
# ======================================================================
@bp.route("/api/mp/apply_snapshot", methods=["POST"])
def api_mp_apply_snapshot():
    """Build the client's local game from the host's snapshot bytes."""
    data = request.get_json(force=True, silent=True) or {}
    nonce = _nonce(data)
    save_b64 = str(data.get("save_b64") or "")
    if not save_b64:
        return jsonify({"ok": False, "error": "save_b64 required"}), 400
    ok = enqueue_command("mp_apply_snapshot", save_b64=save_b64,
                         label=str(data.get("label") or "Joined game"),
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


# ======================================================================
# Batch D: Save/Load depth.
# Desktop parity (save_load_system.py):
#   - quick-save slots 1-6: QuickSaves/QuickSave_Slot_{i}.hm
#   - rename / properties / export / import
#   - autosave config (enabled + frequency)
# Writes run on the Tk main thread through bridge ops; reads are
# direct GameSaveManager reads (read-only, no thread affinity).
# ======================================================================

def _quick_slots(live):
    """6 quick-save slots with metadata (desktop _get_quick_save_slots).
    Never raises."""
    out = []
    try:
        from web_ui.bridge import _web_saves_dir as _sdir, _resolve_gm
        sm = _save_manager(live)
        if sm is None:
            return out
        qdir = os.path.join(_sdir(sm), "QuickSaves")
        for i in range(1, 7):
            fp = os.path.join(qdir, f"QuickSave_Slot_{i}.hm")
            slot = {"slot": i, "name": f"Quick Save {i}",
                    "occupied": False, "modified": None,
                    "team": None, "game_date": None}
            if os.path.exists(fp):
                try:
                    st = os.stat(fp)
                    import datetime as _dt
                    mod = _dt.datetime.fromtimestamp(st.st_mtime)
                    meta = _safe(lambda: sm._load_save_metadata(fp), {}) or {}
                    slot.update(
                        occupied=True,
                        modified=mod.strftime("%Y-%m-%d %H:%M"),
                        team=str(meta.get("user_team", "Unknown") or "Unknown"),
                        game_date=str(meta.get("game_date", "") or ""),
                        size_kb=int(st.st_size // 1024),
                    )
                except Exception:
                    slot["occupied"] = True
            out.append(slot)
    except Exception:
        pass
    return out


@bp.route("/api/save/quick_slots")
def api_save_quick_slots():
    live = _live()
    if live is None:
        return jsonify({"slots": []})
    return jsonify({"slots": _quick_slots(live)})


@bp.route("/api/save/quicksave", methods=["POST"])
def api_save_quicksave():
    """Quick-save into slot 1-6 (desktop Ctrl+S path)."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        slot = int(data.get("slot", 1))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "slot must be 1-6"}), 400
    if not 1 <= slot <= 6:
        return jsonify({"ok": False, "error": "slot must be 1-6"}), 400
    nonce = _nonce(data)
    ok = enqueue_command("save_quicksave_web", slot=slot, nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce, "slot": slot})


@bp.route("/api/save/rename", methods=["POST"])
def api_save_rename():
    """Rename a save file (desktop SaveLoadView rename)."""
    data = request.get_json(force=True, silent=True) or {}
    sid = str(data.get("save_id") or "")
    name = str(data.get("name") or "").strip()
    if not sid or not name:
        return jsonify({"ok": False, "error": "save_id and name required"}), 400
    nonce = _nonce(data)
    ok = enqueue_command("save_rename_web", save_id=sid, name=name,
                         nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})


@bp.route("/api/save/properties")
def api_save_properties():
    """Save-file properties: metadata + description + category."""
    live = _live()
    sid = (request.args.get("save_id") or "").strip()
    if live is None or not sid:
        return jsonify({"ok": False}), 400
    try:
        from web_ui.bridge import _web_resolve_save_id, _web_saves_dir, _resolve_gm
        sm = _save_manager(live)
        fp = _web_resolve_save_id(sm, sid)
        if not fp or not os.path.exists(fp):
            return jsonify({"ok": False, "error": "not found"}), 404
        meta = _safe(lambda: sm._load_save_metadata(fp), {}) or {}
        st = os.stat(fp)
        import datetime as _dt
        return jsonify({
            "ok": True,
            "filename": os.path.basename(fp),
            "team": str(meta.get("user_team", "Unknown") or "Unknown"),
            "game_date": str(meta.get("game_date", "") or ""),
            "modified": _dt.datetime.fromtimestamp(
                st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "size_kb": int(st.st_size // 1024),
            "category": str(meta.get("category", "General") or "General"),
            "description": str(meta.get("description", "") or ""),
            "is_autosave": bool(meta.get("is_autosave")),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/save/export")
def api_save_export():
    """Download a save file (desktop _export_save copies the .hm)."""
    from flask import send_file
    live = _live()
    sid = (request.args.get("save_id") or "").strip()
    if live is None or not sid:
        return jsonify({"ok": False, "error": "save_id required"}), 400
    try:
        from web_ui.bridge import _web_resolve_save_id, _resolve_gm
        sm = _save_manager(live)
        fp = _web_resolve_save_id(sm, sid)
        if not fp or not os.path.exists(fp):
            return jsonify({"ok": False, "error": "not found"}), 404
        return send_file(fp, as_attachment=True,
                         download_name=os.path.basename(fp))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/save/import", methods=["POST"])
def api_save_import():
    """Upload a .hm save into the saves directory (desktop _import_save)."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "no live game"}), 503
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"ok": False, "error": "no file uploaded"}), 400
    fname = os.path.basename(f.filename)
    if not fname.lower().endswith(".hm"):
        return jsonify({"ok": False,
                        "error": "only .hm save files can be imported"}), 400
    # Keep inside the saves dir (never trust the client filename).
    safe = "".join(c for c in fname if c.isalnum() or c in "._- ")[:80]
    if not safe:
        return jsonify({"ok": False, "error": "bad filename"}), 400
    try:
        from web_ui.bridge import _web_saves_dir, _resolve_gm
        sm = _save_manager(live)
        if sm is None:
            return jsonify({"ok": False, "error": "no save manager"}), 503
        dest = os.path.join(_web_saves_dir(sm), safe)
        if os.path.exists(dest):
            return jsonify({"ok": False, "error":
                            f"{safe} already exists"}), 409
        f.save(dest)
        return jsonify({"ok": True, "filename": safe})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/save/autosave_config", methods=["POST"])
def api_save_autosave_config():
    """Set autosave enabled + frequency (days)."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        freq = int(data.get("frequency_days", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False,
                        "error": "frequency_days must be an integer"}), 400
    enabled = bool(data.get("enabled", True))
    if freq < 0 or freq > 365:
        return jsonify({"ok": False,
                        "error": "frequency_days must be 0-365"}), 400
    nonce = _nonce(data)
    ok = enqueue_command("save_autosave_config_web", enabled=enabled,
                         frequency_days=freq, nonce=nonce)
    return jsonify({"ok": bool(ok), "nonce": nonce})
