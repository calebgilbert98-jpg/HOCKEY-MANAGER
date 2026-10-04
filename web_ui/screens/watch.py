# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Web game visualizer (2026-10-04).

GPU-accelerated canvas renderer for live games — the Tkinter canvas
visualizer rebuilt for the browser. Streams position snapshots via
Server-Sent Events and renders at 60fps with interpolation, glow,
and motion trails.

POC mode: mock sim generates realistic movement. Live mode (when the
bridge is active) will subscribe to GameSim's pbp_listeners "skate"
events instead.
"""
import json
import math
import random
import time
from flask import Blueprint, Response, render_template

bp = Blueprint("watch", __name__)

# Rink dimensions (feet, NHL): 200 x 85
RINK_L, RINK_W = 200.0, 85.0


def _mock_skater(team_idx, idx):
    """Initial formation spots."""
    # 5v5: C, LW, RW, LD, RD per team + goalie
    spots_home = [(100, 42), (70, 25), (70, 60), (40, 30), (40, 55)]
    spots_away = [(100, 42), (130, 25), (130, 60), (160, 30), (160, 55)]
    spots = spots_home if team_idx == 0 else spots_away
    x, y = spots[idx % 5]
    return {"x": x, "y": y, "vx": 0.0, "vy": 0.0,
            "tx": x, "ty": y, "team": team_idx, "idx": idx}


def mock_game_stream():
    """Yield SSE skate events from a lightweight mock sim."""
    rng = random.Random(42)
    skaters = [_mock_skater(t, i) for t in range(2) for i in range(5)]
    goalies = [{"x": 11, "y": 42.5, "team": 0}, {"x": 189, "y": 42.5, "team": 1}]
    puck = {"x": 100.0, "y": 42.5, "vx": 0.0, "vy": 0.0}
    poss_team, poss_idx = 0, 0
    period, clock = 1, 20 * 60
    home_g, away_g = 0, 0
    tick = 0

    while True:
        tick += 1
        # pick new targets occasionally (hockey-ish flow)
        if tick % 12 == 0:
            for s in skaters:
                s["tx"] = max(8, min(192, s["tx"] + rng.uniform(-38, 38)))
                s["ty"] = max(8, min(77, s["ty"] + rng.uniform(-26, 26)))
            # puck carrier drives play
            carrier = skaters[poss_team * 5 + poss_idx]
            if rng.random() < 0.25:
                # pass or shoot: pick a teammate / the net
                if rng.random() < 0.7:
                    mates = [i for i in range(5) if i != poss_idx]
                    poss_idx = rng.choice(mates)
                else:
                    # shot on net
                    gx = 11 if poss_team == 1 else 189
                    puck["vx"] = (gx - puck["x"]) * 0.09
                    puck["vy"] = (42.5 - puck["y"]) * 0.09
                    if rng.random() < 0.12:
                        if poss_team == 0:
                            home_g += 1
                        else:
                            away_g += 1
                        # reset to center ice faceoff
                        for s in skaters:
                            base = _mock_skater(s["team"], s["idx"])
                            s["tx"], s["ty"] = base["tx"], base["ty"]
                        puck.update(x=100.0, y=42.5, vx=0.0, vy=0.0)
                        poss_team, poss_idx = 1 - poss_team, 2
            poss_team_carrier = skaters[poss_team * 5 + poss_idx]
            puck["x"] = poss_team_carrier["x"]
            puck["y"] = poss_team_carrier["y"]

        # move skaters toward targets
        for s in skaters:
            s["x"] += (s["tx"] - s["x"]) * 0.12
            s["y"] += (s["ty"] - s["y"]) * 0.12
        # puck physics when shot
        if abs(puck["vx"]) > 0.05 or abs(puck["vy"]) > 0.05:
            puck["x"] += puck["vx"]
            puck["y"] += puck["vy"]
            puck["vx"] *= 0.94
            puck["vy"] *= 0.94

        clock = max(0, clock - 1)
        snap = {
            "type": "skate",
            "tick": tick,
            "period": period,
            "clock": f"{clock // 60}:{clock % 60:02d}",
            "score": {"home": home_g, "away": away_g},
            "skaters": [{"x": round(s["x"], 1), "y": round(s["y"], 1),
                         "team": s["team"]} for s in skaters],
            "goalies": goalies,
            "puck": {"x": round(puck["x"], 1), "y": round(puck["y"], 1)},
            "possession": poss_team,
        }
        yield f"data: {json.dumps(snap)}\n\n"
        time.sleep(0.12)  # ~8 snapshots/sec; client interpolates to 60fps


@bp.route("/watch")
def watch_page():
    return render_template("watch.html")


@bp.route("/api/watch/stream")
def watch_stream():
    return Response(mock_game_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})
