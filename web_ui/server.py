# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Puck Dynasty web UI backend (proof of concept, 2026-10-04).

Flask server that will eventually bridge the live game state to a
2K-style tile frontend. For the POC it serves realistic mock data
shaped like the real game objects so the tile UI can be evaluated
before we wire the real bridge.

Run:  python3 web_ui/server.py
Then: http://localhost:5050/
"""
import os
from flask import Flask, jsonify, render_template

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

# ------------------------------------------------------------------
# Mock game state (shaped like the real objects; the real bridge will
# swap this for live GameManager data).
# ------------------------------------------------------------------
MOCK_STATE = {
    "team": {
        "name": "Boston Bruins",
        "abbr": "BOS",
        "record": {"w": 12, "l": 5, "otl": 2},
        "points": 26,
        "standing": "2nd in Atlantic",
    },
    "team_colors": {"primary": "#FFB81C", "secondary": "#000000"},
    "date": "November 18, 2026",
    "next_game": {
        "opponent": "Toronto Maple Leafs",
        "opponent_abbr": "TOR",
        "home": True,
        "date": "Tonight, 7:00 PM",
    },
    "inbox": {"unread": 3, "action_needed": 1},
    "tiles": [
        {"id": "continue", "title": "Continue", "subtitle": "Advance to next game",
         "size": "hero", "icon": "▶", "accent": True},
        {"id": "roster", "title": "Roster", "subtitle": "29 players · 6 on the bubble",
         "size": "large", "icon": "🏒"},
        {"id": "inbox", "title": "Inbox", "subtitle": "3 unread · 1 needs action",
         "size": "medium", "icon": "✉️", "badge": 3},
        {"id": "schedule", "title": "Schedule", "subtitle": "Next: vs TOR tonight",
         "size": "medium", "icon": "📅"},
        {"id": "stats", "title": "Team Stats", "subtitle": "12-5-2 · 3.42 GF/G",
         "size": "medium", "icon": "📊"},
        {"id": "lines", "title": "Lines", "subtitle": "Edit line combinations",
         "size": "small", "icon": "📋"},
        {"id": "trades", "title": "Trades", "subtitle": "Trade center",
         "size": "small", "icon": "🔄"},
        {"id": "scouting", "title": "Scouting", "subtitle": "2 assignments active",
         "size": "small", "icon": "🔭"},
        {"id": "staff", "title": "Staff", "subtitle": "Coaches & management",
         "size": "small", "icon": "👔"},
    ],
    "panels": {
        "division": "Atlantic",
        "standings": [
            {"name": "Toronto Maple Leafs", "abbr": "TOR", "w": 13, "l": 4, "otl": 2, "pts": 28, "is_user": False},
            {"name": "Boston Bruins", "abbr": "BOS", "w": 12, "l": 5, "otl": 2, "pts": 26, "is_user": True},
            {"name": "Florida Panthers", "abbr": "FLA", "w": 11, "l": 6, "otl": 2, "pts": 24, "is_user": False},
            {"name": "Tampa Bay Lightning", "abbr": "TBL", "w": 10, "l": 7, "otl": 2, "pts": 22, "is_user": False},
        ],
        "leaders": {
            "points": [
                {"id": "mock-pastrnak", "name": "David Pastrnak", "portrait": "/static/img/portraits/portrait_03.webp", "pos": "RW", "g": 14, "a": 12, "pts": 26},
                {"id": "mock-marchand", "name": "Brad Marchand", "portrait": "/static/img/portraits/portrait_03.webp", "pos": "LW", "g": 9, "a": 15, "pts": 24},
                {"id": "mock-mcavoy", "name": "Charlie McAvoy", "portrait": "/static/img/portraits/portrait_04.webp", "pos": "D", "g": 4, "a": 16, "pts": 20},
            ],
            "goals": [
                {"id": "mock-pastrnak", "name": "David Pastrnak", "portrait": "/static/img/portraits/portrait_03.webp", "pos": "RW", "g": 14, "a": 12, "pts": 26},
                {"id": "mock-marchand", "name": "Brad Marchand", "portrait": "/static/img/portraits/portrait_03.webp", "pos": "LW", "g": 9, "a": 15, "pts": 24},
                {"name": "Pavel Zacha", "portrait": "/static/img/portraits/portrait_01.webp", "pos": "C", "g": 8, "a": 10, "pts": 18},
            ],
            "assists": [
                {"id": "mock-mcavoy", "name": "Charlie McAvoy", "portrait": "/static/img/portraits/portrait_04.webp", "pos": "D", "g": 4, "a": 16, "pts": 20},
                {"id": "mock-marchand", "name": "Brad Marchand", "portrait": "/static/img/portraits/portrait_03.webp", "pos": "LW", "g": 9, "a": 15, "pts": 24},
                {"id": "mock-pastrnak", "name": "David Pastrnak", "portrait": "/static/img/portraits/portrait_03.webp", "pos": "RW", "g": 14, "a": 12, "pts": 26},
            ],
        },
        "form": {
            "last5": [
                {"res": "W", "opp": "Toronto Maple Leafs", "opp_abbr": "TOR", "score": "4-2", "home": True},
                {"res": "W", "opp": "Montreal Canadiens", "opp_abbr": "MTL", "score": "3-1", "home": False},
                {"res": "OTL", "opp": "Florida Panthers", "opp_abbr": "FLA", "score": "2-3", "home": True},
                {"res": "W", "opp": "Ottawa Senators", "opp_abbr": "OTT", "score": "5-2", "home": True},
                {"res": "L", "opp": "Tampa Bay Lightning", "opp_abbr": "TBL", "score": "1-4", "home": False},
            ],
            "streak": "W2",
        },
        "next_game": {
            "date": "Thu Nov 19", "time": "7:00 PM",
            "home": "Boston Bruins", "away": "Toronto Maple Leafs",
            "home_abbr": "BOS", "away_abbr": "TOR",
            "home_rec": "12-5-2", "away_rec": "13-4-2",
            "is_home": True,
        },
    },
    "stat_strip": {
        "record": "12-5-2", "gp": 19, "points": 26, "div_rank": 2,
        "gpg": 3.42, "off_rank": 4, "gapg": 2.68, "def_rank": 6,
        "pp_pct": 22.4, "pk_pct": 84.1,
        "streak": "W2", "last10": "7-2-1", "cap_space": 4250000,
    },
    "ticker": [
        {"kind": "score", "text": "BOS 4 — 2 TOR  FINAL"},
        {"kind": "score", "text": "NYR 3 — 5 PIT  FINAL"},
        {"kind": "score", "text": "EDM 2 — 1 VAN  FINAL  ·  Nov 18"},
        {"kind": "news", "text": "Bruins sign F Jake DeBrusk to 2-year extension"},
        {"kind": "news", "text": "TRADE: Maple Leafs acquire D from Blackhawks for 2nd-round pick"},
        {"kind": "news", "text": "Panthers place G on IR, recall backup from AHL"},
        {"kind": "news", "text": "Lightning F fined $5,000 for slashing"},
    ],
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    """Full mock state for the hub."""
    return jsonify(MOCK_STATE)


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "mode": "poc-mock"})


if __name__ == "__main__":
    # threaded so API + static serve concurrently; debug off for the POC
    app.run(host="127.0.0.1", port=5050, threaded=True)
