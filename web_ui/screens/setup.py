# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Web setup / launcher (2026-10-04).

Replaces the Tkinter splash + enhanced launcher: the game boots to a
web setup page (new career team picker, load game) served before any
game exists. POST /api/setup enqueues setup_new_game / setup_load_game;
the main thread builds the game and GET /api/setup_status reports
progress for the page to poll.
"""
import os
from flask import Blueprint, jsonify, render_template, request

from web_ui.bridge import _safe, enqueue_command
import web_ui.bridge as _bridge

bp = Blueprint("setup", __name__)

TEAM_ABBR = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN", "Montréal Canadiens": "MTL",
    "Nashville Predators": "NSH", "New Jersey Devils": "NJD",
    "New York Islanders": "NYI", "New York Rangers": "NYR",
    "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA", "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA", "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


@bp.route("/setup")
def setup_page():
    return render_template("setup.html")


@bp.route("/api/teams")
def api_teams():
    from flask import request as _rq
    league = (_rq.args.get("league") or "NHL").upper()
    try:
        if league == "AHL":
            from database_generator import AHL_TEAMS
            names = list(AHL_TEAMS)
            abbrs = {}
        else:
            from nhl_teams import NHL_TEAMS
            names = list(NHL_TEAMS)
            abbrs = TEAM_ABBR
    except Exception:
        names = sorted(TEAM_ABBR)
        abbrs = TEAM_ABBR
    return jsonify({"ok": True, "league": league, "teams": [
        {"name": t, "abbr": abbrs.get(t, "".join(w[0] for w in t.split()[:3]).upper())}
        for t in names
    ]})


@bp.route("/api/saves")
def api_saves():
    saves = []
    for base in ("saves",):
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base), reverse=True):
            if fn.startswith("template_"):
                continue
            p = os.path.join(base, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            saves.append({"path": p, "name": fn,
                          "size": st.st_size, "mtime": st.st_mtime})
    return jsonify({"ok": True, "saves": saves[:25]})


@bp.route("/api/setup", methods=["POST"])
def api_setup():
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode")
    if mode == "new":
        team = data.get("team") or "Boston Bruins"
        ok = enqueue_command("setup_new_game", team=team,
                             gm_name=data.get("gm_name") or "General Manager",
                             gm_profile=data.get("gm_profile") or {},
                             database_size=data.get("database_size") or "default",
                             leagues=data.get("leagues") or ["NHL", "AHL"],
                             sim_detail=data.get("sim_detail") or {"NHL": "full"},
                             fog_of_war=data.get("fog_of_war", True),
                             fantasy_draft=bool(data.get("fantasy_draft")),
                             salary_cap=data.get("salary_cap", True),
                             injuries=data.get("injuries", True),
                             morale_system=data.get("morale_system", True),
                             start_date=data.get("start_date") or "September 1, 2024",
                             season_length=data.get("season_length") or "Default (84 Games)",
                             difficulty=data.get("difficulty") or "Professional",
                             trade_difficulty=data.get("trade_difficulty") or "Realistic",
                             cpu_gm_intelligence=data.get("cpu_gm_intelligence") or "Medium (Balanced)",
                             international_players=data.get("international_players", True),
                             start_without_cap_penalties=bool(data.get("start_without_cap_penalties")),
                             realistic_progression=data.get("realistic_progression", True),
                             show_composite_ratings=bool(data.get("show_composite_ratings")),
                             playoff_format=data.get("playoff_format") or "divisional",
                             user_league=data.get("user_league") or "NHL",
                             multiplayer_host=bool(data.get("multiplayer_host")))
    elif mode == "load":
        ok = enqueue_command("setup_load_game", path=data.get("path"))
    else:
        return jsonify({"ok": False, "error": "unknown mode"}), 400
    _bridge._web_setup_status = {"status": "starting"}
    return jsonify({"ok": ok})


@bp.route("/api/saves/delete", methods=["POST"])
def api_saves_delete():
    data = request.get_json(force=True, silent=True) or {}
    path = data.get("path") or ""
    # Safety: only allow deleting files inside saves/
    norm = os.path.normpath(path)
    if not norm.startswith("saves" + os.sep) and norm != "saves":
        return jsonify({"ok": False, "error": "invalid path"}), 400
    try:
        os.remove(norm)
        return jsonify({"ok": True})
    except OSError as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/saves/import", methods=["POST"])
def api_saves_import():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no file"}), 400
    import re
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f.filename)[:80]
    os.makedirs("saves", exist_ok=True)
    dest = os.path.join("saves", safe)
    try:
        f.save(dest)
        return jsonify({"ok": True, "path": dest})
    except OSError as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/setup_status")
def api_setup_status():
    st = _safe(lambda: dict(_bridge._web_setup_status)) or {"status": "idle"}
    game_ready = _safe(lambda: _bridge._web_app_ref is not None) or False
    st["game_ready"] = bool(game_ready)
    return jsonify({"ok": True, **st})
