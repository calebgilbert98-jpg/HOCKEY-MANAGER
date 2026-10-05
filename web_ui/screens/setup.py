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
    try:
        from nhl_teams import NHL_TEAMS
        teams = list(NHL_TEAMS)
    except Exception:
        teams = sorted(TEAM_ABBR)
    return jsonify({"ok": True, "teams": [
        {"name": t, "abbr": TEAM_ABBR.get(t, "?")} for t in teams
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
                             gm_name=data.get("gm_name") or "General Manager")
    elif mode == "load":
        ok = enqueue_command("setup_load_game", path=data.get("path"))
    else:
        return jsonify({"ok": False, "error": "unknown mode"}), 400
    _bridge._web_setup_status = {"status": "starting"}
    return jsonify({"ok": ok})


@bp.route("/api/setup_status")
def api_setup_status():
    st = _safe(lambda: dict(_bridge._web_setup_status)) or {"status": "idle"}
    game_ready = _safe(lambda: _bridge._web_app_ref is not None) or False
    st["game_ready"] = bool(game_ready)
    return jsonify({"ok": True, **st})
