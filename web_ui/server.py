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
