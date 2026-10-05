# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Web game visualizer (2026-10-04).

GPU-accelerated canvas renderer for live games. Streams REAL position
snapshots from a live GameSim via Server-Sent Events and renders at
60fps with interpolation, glow, and motion trails.

Live mode: when the bridge holds a game, opening /watch starts a real
GameSim (high_fidelity 1s ticks) for the user's next game in a
background thread. The sim's pbp_listeners feed a thread-safe queue;
the SSE endpoint replays events at watchable speed.

Mock mode: used when no live game is attached (tests, no career).
"""

import json
import queue
import random
import threading
import time
from flask import Blueprint, Response, jsonify, render_template, request

import web_ui.bridge as _bridge
from web_ui.bridge import _safe, get_schedule

bp = Blueprint("watch", __name__)

# Rink dimensions (feet, NHL): 200 x 85
RINK_L, RINK_W = 200.0, 85.0

# ------------------------------------------------------------------
# Live sim state (module-level, guarded by _watch_lock).
# The sim runs on its own thread; Flask threads only read the queue.
# ------------------------------------------------------------------
_watch_lock = threading.Lock()
_watch = {
    "thread": None,     # sim thread (daemon)
    "queue": None,      # queue.Queue of raw pbp events
    "done": False,      # sim finished
    "home": "",         # home team name
    "away": "",         # away team name
    "home_abbr": "",    # abbreviations for the scorebug
    "away_abbr": "",
    "id_meta": {},      # player id (str) -> {"team": 0/1, "name": str, "goalie": bool}
    "error": None,
}


def _fmt_clock(seconds):
    try:
        s = max(0, int(seconds))
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return "0:00"


def _player_name(p):
    if p is None:
        return "Unknown"
    return (getattr(p, "full_name", None)
            or getattr(p, "name", None)
            or str(p))


def _find_team_by_name(live, name):
    """Resolve a team display name to the live Team object."""
    gm = _safe(lambda: live.game_manager)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []
    want = str(name or "").strip().lower()
    for t in teams:
        if str(_safe(lambda: t.team_name, "")).strip().lower() == want:
            return t
    return None


def _team_abbr(team):
    try:
        from web_ui.bridge import TEAM_ABBR
        name = _safe(lambda: team.team_name, "")
        return TEAM_ABBR.get(name) or "".join(w[0] for w in name.split()[:2]).upper()
    except Exception:
        return ""


def _build_id_meta(home_team, away_team):
    """Map player id -> team/name/goalie for both rosters."""
    meta = {}
    for idx, team in enumerate((home_team, away_team)):
        roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
        for p in roster:
            try:
                pid = str(getattr(p, "id", ""))
                if not pid:
                    continue
                pos = str(getattr(p, "primary_position", "")).upper()
                meta[pid] = {
                    "team": idx,
                    "name": _player_name(p),
                    "goalie": "GOALIE" in pos,
                    "jersey": _safe(lambda: getattr(p, "jersey_number", ""), ""),
                }
            except Exception:
                continue
    return meta


def _ensure_live_sim():
    """Start a live GameSim for the user's next game if none is running.

    Returns the _watch dict on success, None when no live game exists
    (caller should fall back to the mock).
    """
    with _watch_lock:
        t = _watch["thread"]
        if t is not None and t.is_alive():
            return _watch  # already running; attach to it
        live = _safe(lambda: _bridge._web_app_ref)
        if live is None:
            return None
        sched = _safe(lambda: get_schedule(live, limit=5), []) or []
        if not sched:
            return None
        g = sched[0]
        home = _find_team_by_name(live, g.get("home"))
        away = _find_team_by_name(live, g.get("away"))
        if home is None or away is None:
            return None

        try:
            from simulation import GameSim
        except Exception:
            return None

        q = queue.Queue()
        sim = GameSim(home, away, high_fidelity=True)
        # League passthrough for league-aware systems (ot_drama etc.)
        try:
            sim.league = _safe(lambda: live.game_manager.league)
        except Exception:
            pass

        def _listener(ev):
            try:
                q.put(dict(ev))
            except Exception:
                pass

        try:
            sim.pbp_listeners.append(_listener)
        except Exception:
            return None

        id_meta = _build_id_meta(home, away)

        def _run():
            try:
                sim.run()
            except Exception as e:  # never kill the thread silently
                try:
                    q.put({"type": "sim_error", "error": str(e)})
                except Exception:
                    pass
            finally:
                try:
                    hs = _safe(lambda: sim.home_score, 0)
                    aws = _safe(lambda: sim.away_score, 0)
                    q.put({
                        "type": "game_end",
                        "home_score": hs,
                        "away_score": aws,
                        "period": _safe(lambda: sim.period, 3),
                    })
                    # Mark the game as watched so advance-day doesn't re-sim it.
                    # The sim already updated player stats; we just need to
                    # record the result and flag the schedule entry.
                    _mark_game_watched(home, away, hs, aws)
                except Exception:
                    pass
                with _watch_lock:
                    _watch["done"] = True

        thread = threading.Thread(target=_run, daemon=True,
                                  name="puck-watch-sim")
        _watch.update(
            thread=thread, queue=q, done=False, error=None,
            home=_safe(lambda: home.team_name, ""),
            away=_safe(lambda: away.team_name, ""),
            home_abbr=_team_abbr(home), away_abbr=_team_abbr(away),
            id_meta=id_meta,
        )
        thread.start()
        return _watch


def _mark_game_watched(home_team, away_team, home_score, away_score):
    """Record a watched game's result so advance-day skips re-simming it.

    The GameSim already updated player/team stats. This records the
    result in game_results and flags the schedule entry as watched.
    """
    try:
        live = _safe(lambda: _bridge._web_app_ref)
        if live is None:
            return
        gm = _safe(lambda: live.game_manager)
        if gm is None:
            return
        from datetime import date as _date
        today = _safe(lambda: gm.current_date)
        hn = _safe(lambda: home_team.team_name, "")
        an = _safe(lambda: away_team.team_name, "")

        # 1. Flag the schedule entry
        sched = _safe(lambda: list(getattr(getattr(gm, "league", None), "schedule", None) or []), []) or []
        for g in sched:
            try:
                if not isinstance(g, dict):
                    continue
                gd = g.get("date")
                # Match date and teams
                if gd != today:
                    continue
                gh = g.get("home_team")
                ga = g.get("away_team")
                # Handle both Team objects and strings
                ghn = getattr(gh, "team_name", gh) if gh else ""
                gan = getattr(ga, "team_name", ga) if ga else ""
                if ghn == hn and gan == an:
                    g["watched"] = True
                    g["watched_home_score"] = home_score
                    g["watched_away_score"] = away_score
                    break
            except Exception:
                continue

        # 2. Record in game_results so the day-advance sees it as played
        try:
            result = {
                "date": today,
                "home_team": hn,
                "away_team": an,
                "home_score": home_score,
                "away_score": away_score,
                "watched": True,
            }
            rec = _safe(lambda: getattr(live, "_record_game_result", None))
            if callable(rec):
                rec(result)
            else:
                gr = _safe(lambda: getattr(live, "game_results", None))
                if isinstance(gr, list):
                    gr.append(result)
        except Exception:
            pass
    except Exception:
        pass


# ------------------------------------------------------------------
# Event -> client JSON
# ------------------------------------------------------------------

def _skate_to_client(ev, meta):
    """Transform a sim 'skate' event into the watch.js snapshot format."""
    positions = ev.get("positions") or {}
    home_ids = {str(i) for i in (ev.get("on_ice_home") or [])}
    away_ids = {str(i) for i in (ev.get("on_ice_away") or [])}
    skaters, goalies = [], []
    # Stable order: sort by player id so the client can interpolate.
    for pid in sorted(positions.keys(), key=str):
        try:
            x, y = positions[pid]
        except Exception:
            continue
        pids = str(pid)
        m = meta.get(pids, {})
        team = m.get("team")
        if team is None:
            team = 0 if pids in home_ids else (1 if pids in away_ids else 0)
        entry = {"x": round(float(x), 1), "y": round(float(y), 1),
                 "team": team, "name": m.get("name", ""),
                 "jersey": m.get("jersey", "")}
        if m.get("goalie"):
            goalies.append(entry)
        else:
            skaters.append(entry)
    puck = ev.get("puck") or (100.0, 42.5)
    try:
        px, py = float(puck[0]), float(puck[1])
    except Exception:
        px, py = 100.0, 42.5
    poss = ev.get("possession_team")
    poss_idx = None
    if poss is not None:
        pl = str(poss).lower()
        if _watch["home"] and pl in _watch["home"].lower():
            poss_idx = 0
        elif _watch["away"] and pl in _watch["away"].lower():
            poss_idx = 1
    return {
        "type": "skate",
        "period": ev.get("period", 1),
        "clock": _fmt_clock(ev.get("clock", 0)),
        "score": {"home": ev.get("home_score", 0),
                  "away": ev.get("away_score", 0)},
        "home_abbr": _watch["home_abbr"], "away_abbr": _watch["away_abbr"],
        "home_name": _watch["home"], "away_name": _watch["away"],
        "skaters": skaters,
        "goalies": goalies,
        "puck": {"x": round(px, 1), "y": round(py, 1)},
        "possession": poss_idx,
    }


def _highlight_to_client(ev):
    """Big moments: goals, hits, penalties, fights, milestones."""
    et = ev.get("type")
    kind = et
    home_abbr, away_abbr = _watch["home_abbr"], _watch["away_abbr"]
    scoring = str(ev.get("scoring_team") or ev.get("team") or "")
    team = 0 if scoring and _watch["home"] and scoring in _watch["home"] else 1
    if et == "goal":
        text = (f"GOAL! {_player_name(ev.get('shooter'))}"
                f" ({home_abbr if team == 0 else away_abbr})")
        assists = ev.get("assists") or []
        if assists:
            text += f" — assists: {', '.join(_player_name(a) for a in assists)}"
    elif et == "hit":
        text = (f"Hit: {_player_name(ev.get('hitting_player'))} on "
                f"{_player_name(ev.get('target_player'))}")
    elif et == "penalty":
        text = f"Penalty: {_player_name(ev.get('player'))} ({ev.get('infraction', '')})"
    elif et == "fight":
        text = "Fight!"
    elif et == "milestone":
        text = str(ev.get("kind", "milestone")).replace("_", " ").title()
    else:
        text = str(et).replace("_", " ").title()
    return {
        "type": "highlight", "kind": kind, "text": text, "team": team,
        "period": ev.get("period", 1),
        "clock": _fmt_clock(ev.get("clock", 0)),
        "score": {"home": ev.get("home_score", 0),
                  "away": ev.get("away_score", 0)},
    }


_HIGHLIGHT_TYPES = {"goal", "hit", "penalty", "fight", "milestone",
                    "goalie_pulled", "icing", "offside"}


def _client_event(ev, meta):
    et = ev.get("type")
    if et == "skate":
        return _skate_to_client(ev, meta)
    if et in _HIGHLIGHT_TYPES:
        return _highlight_to_client(ev)
    if et == "period_start":
        return {"type": "highlight", "kind": "period_start",
                "text": f"Period {ev.get('period', 1)}",
                "period": ev.get("period", 1),
                "clock": _fmt_clock(ev.get("clock", 0)),
                "score": {"home": ev.get("home_score", 0),
                          "away": ev.get("away_score", 0)}}
    if et == "period_end":
        return {"type": "highlight", "kind": "period_end",
                "text": f"End of period {ev.get('period', 1)}",
                "period": ev.get("period", 1),
                "clock": "0:00",
                "score": {"home": ev.get("home_score", 0),
                          "away": ev.get("away_score", 0)}}
    if et == "game_start":
        return {"type": "highlight", "kind": "game_start",
                "text": f"{ev.get('away_team', '')} at {ev.get('home_team', '')}",
                "period": 1, "clock": "20:00",
                "score": {"home": 0, "away": 0}}
    if et == "game_end":
        return {"type": "game_end", "period": ev.get("period", 3),
                "clock": "0:00",
                "score": {"home": ev.get("home_score", 0),
                          "away": ev.get("away_score", 0)},
                "home_abbr": _watch["home_abbr"],
                "away_abbr": _watch["away_abbr"],
                "text": "Final"}
    if et == "sim_error":
        return {"type": "highlight", "kind": "error",
                "text": f"Sim error: {str(ev.get('error', ''))[:120]}",
                "period": 1, "clock": "0:00",
                "score": {"home": 0, "away": 0}}
    return None  # skip uninteresting types


# ------------------------------------------------------------------
# Streams
# ------------------------------------------------------------------

# Pacing: seconds of real time per event type. ~3600 skate ticks at
# 0.09s => ~5.5 minutes for a full game. Big moments get a beat.
_PACE = {"skate": 0.09, "goal": 2.0, "fight": 2.0, "penalty": 1.2,
         "period_end": 1.5, "period_start": 1.0, "milestone": 1.0}


def live_game_stream(speed=1.0):
    """Yield SSE events from the live GameSim, paced for watching."""
    st = _ensure_live_sim()
    if st is None:
        yield from mock_game_stream()
        return
    q = st["queue"]
    meta = st["id_meta"]
    pace_scale = 1.0 / max(0.25, min(8.0, speed))
    # Opening meta so the client has teams immediately.
    yield ("data: " + json.dumps({
        "type": "meta", "home": st["home"], "away": st["away"],
        "home_abbr": st["home_abbr"], "away_abbr": st["away_abbr"]}) + "\n\n")
    while True:
        try:
            ev = q.get(timeout=45)
        except queue.Empty:
            break  # sim died or stalled
        try:
            out = _client_event(ev, meta)
        except Exception:
            out = None
        if out is not None:
            yield f"data: {json.dumps(out, default=str)}\n\n"
        et = ev.get("type")
        if et in ("game_end", "sim_error"):
            break
        time.sleep(_PACE.get(et, 0.25) * pace_scale)


# ------------------------------------------------------------------
# Mock fallback (unchanged): used when no live game is attached.
# ------------------------------------------------------------------

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
    goalies = [{"x": 11, "y": 42.5, "team": 0, "name": ""},
               {"x": 189, "y": 42.5, "team": 1, "name": ""}]
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
                    # shot: puck flies to net, maybe scores
                    net_x = 189 if poss_team == 0 else 11
                    puck["vx"] = (net_x - puck["x"]) / 8
                    puck["vy"] = rng.uniform(-6, 6)
                    if rng.random() < 0.12:
                        if poss_team == 0:
                            home_g += 1
                        else:
                            away_g += 1
        # move skaters toward targets
        for s in skaters:
            s["x"] += (s["tx"] - s["x"]) * 0.08
            s["y"] += (s["ty"] - s["y"]) * 0.08
        # puck follows carrier or flies
        carrier = skaters[poss_team * 5 + poss_idx]
        if abs(puck["vx"]) + abs(puck["vy"]) > 0.5:
            puck["x"] += puck["vx"]
            puck["y"] += puck["vy"]
            puck["vx"] *= 0.92
            puck["vy"] *= 0.92
        else:
            puck["x"] += (carrier["x"] - puck["x"]) * 0.3
            puck["y"] += (carrier["y"] - puck["y"]) * 0.3
        clock -= 1
        if clock <= 0:
            period += 1
            clock = 20 * 60
            if period > 3:
                break
        snap = {
            "type": "skate",
            "period": period,
            "clock": _fmt_clock(clock),
            "score": {"home": home_g, "away": away_g},
            "home_abbr": "HOM", "away_abbr": "AWY",
            "home_name": "Home", "away_name": "Away",
            "skaters": [{"x": round(s["x"], 1), "y": round(s["y"], 1),
                         "team": s["team"], "name": ""} for s in skaters],
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
    try:
        speed = float(request.args.get("speed", 1))
    except Exception:
        speed = 1.0
    return Response(live_game_stream(speed), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@bp.route("/api/watch/status")
def watch_status():
    """Which mode is the visualizer in? (live vs mock)"""
    with _watch_lock:
        running = _watch["thread"] is not None and _watch["thread"].is_alive()
        return jsonify({
            "live": running,
            "done": _watch["done"],
            "home": _watch["home"],
            "away": _watch["away"],
        })
