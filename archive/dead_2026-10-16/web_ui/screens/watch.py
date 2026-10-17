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
from web_ui.bridge import _safe, get_schedule, _resolve_gm

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
    "sim": None,        # GameSim reference (read-only box-score access)
    "events": [],       # JSON-safe event log for text/shot-chart modes
    "done": False,      # sim finished
    "home": "",         # home team name
    "away": "",         # away team name
    "home_abbr": "",    # abbreviations for the scorebug
    "away_abbr": "",
    "id_meta": {},      # player id (str) -> {"team": 0/1, "name": str, "goalie": bool}
    "error": None,
}

# Cap on the retained event log (a full game is ~2-4k events).
_EVENTS_CAP = 8000


def _ev_json(ev):
    """Deep-convert a pbp event to JSON-safe primitives.

    Player objects -> display name; tuples/sets -> lists; enums ->
    their value; anything else unknown -> str().
    """
    def _conv(v):
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if isinstance(v, dict):
            return {str(k): _conv(x) for k, x in v.items()}
        if isinstance(v, (list, tuple, set)):
            return [_conv(x) for x in v]
        # Player-like objects: prefer display name, never leak the object.
        nm = getattr(v, "full_name", None) or getattr(v, "name", None)
        if nm:
            return str(nm)
        val = getattr(v, "value", None)
        if isinstance(val, (bool, int, float, str)):
            return val
        return str(v)
    try:
        return _conv(dict(ev))
    except Exception:
        return {"type": str(ev.get("type", "?")) if isinstance(ev, dict) else "?"}


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
    gm = _resolve_gm(live)
    teams = _safe(lambda: list(getattr(getattr(gm, "league", None), "teams", None) or []), []) or []
    want = str(name or "").strip().lower()
    for t in teams:
        if str(_safe(lambda: t.team_name, "")).strip().lower() == want:
            return t
    return None


def _team_abbr(team):
    try:
        from web_ui.bridge import TEAM_ABBR, _resolve_gm
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
        # Game-day inbox bundle (Batch A): the GM's pre-game team talk
        # boost and coach's instruction apply to the watched sim, exactly
        # like the desktop viewer path (main._process_todays_games).
        try:
            _res = getattr(live, "_game_day_resolution", None)
            _today = _safe(lambda: live.game_manager.current_date)
            if (_res is not None and _res.get("date") == _today
                    and bool(_res.get("watch"))):
                _tb = float(_res.get("talk_boost", 1.0) or 1.0)
                _instr = _res.get("instruction")
                _uname = _safe(lambda: live.game_manager.user_team.team_name, "")
                if _tb != 1.0 and _uname:
                    try:
                        sim.set_team_talk_boost(_uname, _tb)
                    except Exception:
                        pass
                if _instr and _uname:
                    try:
                        sim.set_coach_instruction(_uname, _instr)
                    except Exception:
                        pass
                live._game_day_resolution = None  # consume once
        except Exception:
            pass

        def _listener(ev):
            try:
                q.put(dict(ev))
            except Exception:
                pass
            # Retain a JSON-safe copy for text/shot-chart/box-score modes.
            try:
                with _watch_lock:
                    _watch["events"].append(_ev_json(ev))
                    if len(_watch["events"]) > _EVENTS_CAP:
                        del _watch["events"][: len(_watch["events"]) - _EVENTS_CAP]
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
            sim=sim, events=[],
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
        gm = _resolve_gm(live)
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


@bp.route("/api/watch/events")
def watch_events():
    """Full JSON-safe event log for text and shot-chart modes.

    Starts the live sim on first call (same as the SSE stream) so the
    modes work even if the visualizer tab was never opened.
    """
    st = _ensure_live_sim()
    with _watch_lock:
        evs = list(_watch["events"])
        done = _watch["done"]
        home, away = _watch["home"], _watch["away"]
        habbr, aabbr = _watch["home_abbr"], _watch["away_abbr"]
    if st is None:
        return jsonify({"events": [], "live": False, "done": done,
                        "home": home, "away": away,
                        "home_abbr": habbr, "away_abbr": aabbr})
    return jsonify({"events": evs, "live": True, "done": done,
                    "home": home, "away": away,
                    "home_abbr": habbr, "away_abbr": aabbr})


def _pos_short(p):
    try:
        pos = getattr(p, "primary_position", None)
        return str(getattr(pos, "value", None)
                   or getattr(pos, "name", "") or "")
    except Exception:
        return ""


def _normalize_gs(game_stats):
    """{str(pid): stats} regardless of key type."""
    out = {}
    try:
        for pid, st in (game_stats or {}).items():
            if isinstance(st, dict):
                out[str(pid)] = st
    except Exception:
        pass
    return out


def _lines_grades_payload(team_obj, team_idx, team_name, gs, by_id):
    """Lines tab: per-line grades via the desktop's compute_line_ratings.

    gs/by_id keyed by str(pid). Returns JSON-safe lines list.
    """
    try:
        from game_box_score import compute_line_ratings
        from game_classes import snapshot_team_lines
    except Exception:
        return []
    try:
        snap = snapshot_team_lines(team_obj)
        if not snap:
            return []
        snap = {
            "Forwards": [[str(i) for i in (line or [])]
                         for line in (snap.get("Forwards") or [])],
            "Defense": [[str(i) for i in (pair or [])]
                        for pair in (snap.get("Defense") or [])],
        }
        lines = compute_line_ratings(snap, gs, by_id)
    except Exception:
        return []
    out = []
    for L in (lines or []):
        try:
            players = []
            for pl in (L.get("players") or []):
                p = pl.get("player")
                grade = pl.get("grade")
                players.append({
                    "name": _player_name(p),
                    "pos": pl.get("pos", ""),
                    "g": int(pl.get("g", 0) or 0),
                    "a": int(pl.get("a", 0) or 0),
                    "p": int(pl.get("p", 0) or 0),
                    "grade": round(float(grade), 1)
                    if grade is not None else None,
                    "why": pl.get("why") or "",
                })
            rating = L.get("rating")
            out.append({
                "label": L.get("label", ""),
                "rating": round(float(rating), 1)
                if rating is not None else None,
                "players": players,
            })
        except Exception:
            continue
    return out


def _team_stats_from_gs(gs, meta):
    """Aggregate per-team stats from normalized game_stats."""
    agg = {0: {"goals": 0, "shots": 0, "saves": 0, "hits": 0,
               "blocks": 0, "fo_won": 0, "takeaways": 0, "giveaways": 0},
           1: {"goals": 0, "shots": 0, "saves": 0, "hits": 0,
               "blocks": 0, "fo_won": 0, "takeaways": 0, "giveaways": 0}}
    for pid, st in (gs or {}).items():
        try:
            m = meta.get(str(pid), {})
            ti = 0 if m.get("team", 0) == 0 else 1
            a = agg[ti]
            if m.get("goalie"):
                a["saves"] += int(st.get("saves", 0) or 0)
            else:
                a["goals"] += int(st.get("g", 0) or 0)
                a["shots"] += int(st.get("shots_on_goal", 0) or 0)
                a["hits"] += int(st.get("hits", 0) or 0)
                a["blocks"] += int(st.get("blocked_shots", 0) or 0) + \
                    int(st.get("blocked_shots_by", 0) or 0)
                a["fo_won"] += int(st.get("faceoffs_won", 0) or 0)
                a["takeaways"] += int(st.get("takeaways", 0) or 0)
                a["giveaways"] += int(st.get("giveaways", 0) or 0)
        except Exception:
            continue
    return agg


def _scoring_from_events(events, home_name):
    """Scoring summary from the JSON-safe event log (live sim)."""
    out = []
    for ev in (events or []):
        try:
            if not isinstance(ev, dict) or ev.get("type") != "goal":
                continue
            scoring = str(ev.get("scoring_team") or "")
            team = 0 if (home_name and scoring
                         and scoring.strip().lower()
                         == str(home_name).strip().lower()) else 1
            assists = ev.get("assists") or []
            out.append({
                "period": int(ev.get("period", 1) or 1),
                "clock": _fmt_clock(ev.get("clock", 0)),
                "elapsed": int(ev.get("elapsed", 0) or 0),
                "scorer": str(ev.get("shooter") or "?"),
                "assists": [str(a) for a in assists],
                "team": team,
                "team_name": scoring,
                "empty_net": bool(ev.get("empty_net")),
                "shot_type": str(ev.get("shot_type") or ""),
            })
        except Exception:
            continue
    out.sort(key=lambda e: (e["period"], e["elapsed"]))
    return out


def _boxscore_payload():
    """Live box score from the sim's game_stats (read-only snapshot).

    Full depth (Batch E): Blocks/FO columns, scoring summary, lines
    grades, team stats, 3 stars -- mirrors game_box_score.py's tabs.
    """
    with _watch_lock:
        sim = _watch["sim"]
        meta = dict(_watch["id_meta"])
        home, away = _watch["home"], _watch["away"]
        habbr, aabbr = _watch["home_abbr"], _watch["away_abbr"]
        events = list(_watch["events"])
    if sim is None:
        return None
    try:
        gs = _normalize_gs(getattr(sim, "game_stats", None))
        if not gs:
            return None
    except Exception:
        return None

    # Player lookup for lines grades: rosters of both clubs.
    by_id = {}
    try:
        for team_obj in (getattr(sim, "home_team", None),
                         getattr(sim, "away_team", None)):
            for p in (getattr(team_obj, "roster", None) or []):
                try:
                    by_id[str(getattr(p, "id", ""))] = p
                except Exception:
                    continue
    except Exception:
        pass

    skaters, goalies = [], []
    for pid, st in gs.items():
        try:
            m = meta.get(str(pid), {})
            p = by_id.get(str(pid))
            name = m.get("name") or _player_name(p)
            is_g = bool(m.get("goalie"))
            row = {
                "id": str(pid),
                "name": name,
                "team": 0 if m.get("team", 0) == 0 else 1,
                "jersey": m.get("jersey", ""),
                "pos": "G" if is_g else _pos_short(p),
            }
            if is_g:
                sa = int(st.get("shots_against", 0) or 0)
                sv = int(st.get("saves", 0) or 0)
                ga = int(st.get("goals_against", 0) or 0)
                if sa <= sv:  # engine didn't track shots against; derive
                    sa = sv + ga
                row.update({
                    "sa": sa, "saves": sv, "ga": ga,
                    "sv_pct": round(sv / sa, 3) if sa else 0.0,
                })
                goalies.append(row)
            else:
                fw = int(st.get("faceoffs_won", 0) or 0)
                fl = int(st.get("faceoffs_lost", 0) or 0)
                row.update({
                    "g": int(st.get("g", 0) or 0),
                    "a": int(st.get("a", 0) or 0),
                    "sog": int(st.get("shots_on_goal", 0) or 0),
                    "hits": int(st.get("hits", 0) or 0),
                    "blk": int(st.get("blocked_shots", 0) or 0)
                    + int(st.get("blocked_shots_by", 0) or 0),
                    "fo": f"{fw}-{fl}",
                })
                row["pts"] = row["g"] + row["a"]
                skaters.append(row)
        except Exception:
            continue
    skaters.sort(key=lambda r: (-r["pts"], -r["g"], r["name"]))
    goalies.sort(key=lambda r: (-r["saves"], r["name"]))
    try:
        hs = int(getattr(sim, "home_score", 0) or 0)
        aws = int(getattr(sim, "away_score", 0) or 0)
        period = int(getattr(sim, "period", 1) or 1)
    except Exception:
        hs, aws, period = 0, 0, 1

    # Lines grades per club (current combos -- the live sim's lines).
    lines = {}
    try:
        for idx, team_obj, tname in (
                (0, getattr(sim, "home_team", None), home),
                (1, getattr(sim, "away_team", None), away)):
            if team_obj is not None:
                lines[str(idx)] = _lines_grades_payload(
                    team_obj, idx, tname, gs, by_id)
    except Exception:
        pass

    stars = [{
        "name": r["name"],
        "team": r["team"],
        "team_name": home if r["team"] == 0 else away,
        "g": r["g"], "a": r["a"],
    } for r in skaters[:3]]

    return {
        "home": home, "away": away,
        "home_abbr": habbr, "away_abbr": aabbr,
        "score": {"home": hs, "away": aws},
        "period": period,
        "skaters": skaters, "goalies": goalies,
        "scoring": _scoring_from_events(events, home),
        "lines": lines,
        "team_stats": _team_stats_from_gs(gs, meta),
        "stars": stars,
    }


@bp.route("/api/watch/boxscore")
def watch_boxscore():
    """Live box score for the box-score drill-down mode (full depth)."""
    st = _ensure_live_sim()
    if st is None:
        return jsonify({"live": False, "skaters": [], "goalies": []})
    payload = _boxscore_payload()
    if payload is None:
        return jsonify({"live": True, "skaters": [], "goalies": [],
                        "home": _watch["home"], "away": _watch["away"]})
    payload["live"] = True
    return jsonify(payload)


# ------------------------------------------------------------------
# Completed-game replay (Batch E, 2026-10-06).
#
# GAME_VIEWER.py (Watch All / Highlights / Text) vs web /watch = next
# game only. These endpoints expose completed games: pick a past game,
# replay its play-by-play (All / Highlights / Text via the client-side
# filter) and drill into the same full-depth box score (scoring
# summary, player stats, lines grades, team stats, 3 stars) built from
# the stored game_result -- the same data GameBoxScoreView uses.
# ------------------------------------------------------------------

def _result_team_name(t):
    try:
        return str(getattr(t, "team_name", None) or t or "")
    except Exception:
        return ""


def _result_date_str(d):
    try:
        if hasattr(d, "strftime"):
            return d.strftime("%b %d, %Y")
        return str(d or "")
    except Exception:
        return ""


def _past_results():
    """Completed game_results, newest first (defensive)."""
    try:
        live = _safe(lambda: _bridge._web_app_ref)
        if live is None:
            return []
        results = _safe(lambda: list(getattr(live, "game_results", None)
                                    or []), []) or []
    except Exception:
        return []
    return results


@bp.route("/replay")
def replay_page():
    """Completed-game replay: pick a past game, replay its PBP."""
    return render_template("replay.html")


@bp.route("/api/watch/past_games")
def watch_past_games():
    """List completed games for the replay picker."""
    out = []
    for idx, r in enumerate(reversed(_past_results())):
        try:
            if not isinstance(r, dict):
                continue
            hn = _result_team_name(r.get("home_team"))
            an = _result_team_name(r.get("away_team"))
            if not hn or not an:
                continue
            out.append({
                "idx": idx,  # index into the reversed list
                "date": _result_date_str(r.get("date")),
                "home": hn, "away": an,
                "home_score": int(r.get("home_score", 0) or 0),
                "away_score": int(r.get("away_score", 0) or 0),
                "overtime": bool(r.get("overtime")),
                "shootout": bool(r.get("shootout")),
                "watched": bool(r.get("watched")),
            })
        except Exception:
            continue
    return jsonify({"games": out})


def _get_past_result(idx):
    try:
        results = list(reversed(_past_results()))
        r = results[int(idx)]
        return r if isinstance(r, dict) else None
    except Exception:
        return None


def _result_roster_lookup(result):
    """{str(pid): Player} from the game's clubs (defensive)."""
    by_id = {}
    for key in ("home_team", "away_team"):
        try:
            team = result.get(key)
            for p in (getattr(team, "roster", None) or []):
                try:
                    by_id[str(getattr(p, "id", ""))] = p
                except Exception:
                    continue
        except Exception:
            continue
    # Merge game_stats-embedded players (traded away since, etc.).
    try:
        for pid, gs in ((result.get("game_stats") or {}).items()):
            try:
                p = gs.get("player") if isinstance(gs, dict) else None
                if p is not None and str(pid) not in by_id:
                    by_id[str(pid)] = p
            except Exception:
                continue
    except Exception:
        pass
    return by_id


def _result_player_team(pid, gs, by_id):
    p = gs.get("player") if isinstance(gs, dict) else None
    if p is None:
        p = by_id.get(str(pid))
    try:
        return str(getattr(p, "team_name", "") or "")
    except Exception:
        return ""


def _result_boxscore(result):
    """Full-depth box score from a stored game_result (JSON-safe)."""
    home = _result_team_name(result.get("home_team"))
    away = _result_team_name(result.get("away_team"))
    try:
        from web_ui.bridge import TEAM_ABBR, _resolve_gm
        habbr = TEAM_ABBR.get(home) or "".join(
            w[0] for w in home.split()[:2]).upper()
        aabbr = TEAM_ABBR.get(away) or "".join(
            w[0] for w in away.split()[:2]).upper()
    except Exception:
        habbr, aabbr = "", ""
    hs = int(result.get("home_score", 0) or 0)
    aws = int(result.get("away_score", 0) or 0)
    by_id = _result_roster_lookup(result)
    gs = _normalize_gs(result.get("game_stats"))

    def _is_goalie(pid, st):
        p = by_id.get(str(pid))
        try:
            pos = getattr(p, "primary_position", None)
            pv = str(getattr(pos, "value", None)
                     or getattr(pos, "name", "") or "").upper()
            if "GOALIE" in pv:
                return True
        except Exception:
            pass
        return False

    skaters, goalies = [], []
    for pid, st in gs.items():
        try:
            p = by_id.get(str(pid))
            tname = _result_player_team(pid, st, by_id)
            ti = 0 if tname == home else 1
            name = _player_name(p)
            if _is_goalie(pid, st):
                sa = int(st.get("shots_against", 0) or 0)
                sv = int(st.get("saves", 0) or 0)
                ga = int(st.get("goals_against", 0) or 0)
                if sa <= sv:
                    sa = sv + ga
                goalies.append({
                    "id": str(pid), "name": name, "team": ti,
                    "jersey": str(_safe(
                        lambda: getattr(p, "jersey_number", "")) or ""),
                    "pos": "G", "sa": sa, "saves": sv, "ga": ga,
                    "sv_pct": round(sv / sa, 3) if sa else 0.0,
                })
            else:
                fw = int(st.get("faceoffs_won", 0) or 0)
                fl = int(st.get("faceoffs_lost", 0) or 0)
                g = int(st.get("g", 0) or 0)
                a = int(st.get("a", 0) or 0)
                skaters.append({
                    "id": str(pid), "name": name, "team": ti,
                    "jersey": str(_safe(
                        lambda: getattr(p, "jersey_number", "")) or ""),
                    "pos": _pos_short(p),
                    "g": g, "a": a, "pts": g + a,
                    "sog": int(st.get("shots_on_goal", 0) or 0),
                    "hits": int(st.get("hits", 0) or 0),
                    "blk": int(st.get("blocked_shots", 0) or 0)
                    + int(st.get("blocked_shots_by", 0) or 0),
                    "fo": f"{fw}-{fl}",
                })
        except Exception:
            continue
    skaters.sort(key=lambda r: (-r["pts"], -r["g"], r["name"]))
    goalies.sort(key=lambda r: (-r["saves"], r["name"]))

    # Scoring summary from GOAL_ADVANCED events.
    scoring = []
    try:
        goals = [e for e in (result.get("event_log") or [])
                 if isinstance(e, dict)
                 and e.get("type") == "GOAL_ADVANCED"]
        home_run = away_run = 0

        def _gkey(e):
            d = e.get("details", {}) or {}
            return (d.get("period", 99), e.get("timestamp", 0))

        for e in sorted(goals, key=_gkey):
            d = e.get("details", {}) or {}
            scorer = _player_name(by_id.get(str(d.get("scorer_id"))))
            assists = [_player_name(by_id.get(str(a)))
                       for a in (d.get("assist_ids") or [])]
            sp = by_id.get(str(d.get("scorer_id")))
            stname = ""
            try:
                stname = str(getattr(sp, "team_name", "") or "")
            except Exception:
                pass
            ti = 0 if stname == home else 1
            if ti == 0:
                home_run += 1
            else:
                away_run += 1
            strength = str(d.get("strength", "EV") or "EV")
            scoring.append({
                "period": int(d.get("period", 1) or 1),
                "clock": str(d.get("time_str", "") or ""),
                "scorer": scorer, "assists": assists,
                "team": ti, "team_name": stname,
                "strength": strength,
                "goal_type": str(d.get("goal_type", "") or "")
                .replace("_", " ").title(),
                "running": f"{aabbr} {away_run} - {home_run} {habbr}",
            })
    except Exception:
        pass

    # Lines grades from the stamped snapshot (desktop parity).
    lines = {}
    try:
        from game_box_score import compute_line_ratings
        for idx, tname in ((0, home), (1, away)):
            snap = (result.get("lines") or {}).get(tname)
            if not snap:
                continue
            snap = {
                "Forwards": [[str(i) for i in (line or [])]
                             for line in (snap.get("Forwards") or [])],
                "Defense": [[str(i) for i in (pair or [])]
                            for pair in (snap.get("Defense") or [])],
            }
            # compute_line_ratings works on the snapshot directly
            # (same helper the desktop Lines tab uses).
            units = compute_line_ratings(snap, gs, by_id)
            rendered = []
            for L in (units or []):
                players = []
                for pl in (L.get("players") or []):
                    grade = pl.get("grade")
                    players.append({
                        "name": _player_name(pl.get("player")),
                        "pos": pl.get("pos", ""),
                        "g": int(pl.get("g", 0) or 0),
                        "a": int(pl.get("a", 0) or 0),
                        "p": int(pl.get("p", 0) or 0),
                        "grade": round(float(grade), 1)
                        if grade is not None else None,
                        "why": pl.get("why") or "",
                    })
                rating = L.get("rating")
                rendered.append({
                    "label": L.get("label", ""),
                    "rating": round(float(rating), 1)
                    if rating is not None else None,
                    "players": players,
                })
            lines[str(idx)] = rendered
    except Exception:
        pass

    # Team stats (stored aggregates, keyed by team name).
    team_stats = {0: {}, 1: {}}
    try:
        ts = result.get("team_stats") or {}
        for idx, tname in ((0, home), (1, away)):
            d = ts.get(tname) or {}
            team_stats[idx] = {
                "goals": hs if idx == 0 else aws,
                "shots": int(d.get("shots_on_goal", d.get("shots", 0)) or 0),
                "saves": int(d.get("saves", 0) or 0),
                "hits": int(d.get("hits", 0) or 0),
                "blocks": int(d.get("blocked_shots_by_team",
                                    d.get("blocked_shots", 0)) or 0),
                "fo_won": int(d.get("faceoffs_won", 0) or 0),
                "takeaways": int(d.get("takeaways", 0) or 0),
                "giveaways": int(d.get("giveaways", 0) or 0),
                "pp": f"{int(d.get('power_play_goals', 0) or 0)}/"
                      f"{int(d.get('power_play_opportunities', 0) or 0)}",
                "shg": int(d.get("short_handed_goals", 0) or 0),
            }
    except Exception:
        pass

    # 3 stars: recorded stars first, ratings fallback (desktop parity).
    stars = []
    try:
        saved = result.get("three_stars") or []
        if saved:
            for s in saved[:3]:
                if isinstance(s, dict):
                    tn = s.get("team_name", "")
                    stars.append({
                        "name": s.get("name", "?"), "team_name": tn,
                        "team": 0 if tn == home else 1,
                    })
        else:
            ratings = result.get("player_ratings") or {}
            cand = []
            for tname, pmap in ratings.items():
                if not isinstance(pmap, dict):
                    continue
                for pid, rating in pmap.items():
                    try:
                        cand.append((float(rating),
                                     _player_name(by_id.get(str(pid))),
                                     tname))
                    except Exception:
                        continue
            cand.sort(key=lambda x: x[0], reverse=True)
            for rating, name, tname in cand[:3]:
                stars.append({"name": name, "team_name": tname,
                              "team": 0 if tname == home else 1})
    except Exception:
        pass
    if not stars:
        stars = [{
            "name": r["name"], "team_name": home if r["team"] == 0 else away,
            "team": r["team"],
        } for r in skaters[:3]]

    return {
        "home": home, "away": away,
        "home_abbr": habbr, "away_abbr": aabbr,
        "score": {"home": hs, "away": aws},
        "date": _result_date_str(result.get("date")),
        "overtime": bool(result.get("overtime")),
        "shootout": bool(result.get("shootout")),
        "skaters": skaters, "goalies": goalies,
        "scoring": scoring, "lines": lines,
        "team_stats": team_stats, "stars": stars,
    }


@bp.route("/api/watch/boxscore_history")
def watch_boxscore_history():
    """Full-depth box score for a completed game (?idx=, see past_games)."""
    idx = request.args.get("idx", "0")
    r = _get_past_result(idx)
    if r is None:
        return jsonify({"ok": False, "error": "unknown game"}), 404
    payload = _result_boxscore(r)
    payload["ok"] = True
    payload["idx"] = idx
    return jsonify(payload)


@bp.route("/api/watch/replay_events")
def watch_replay_events():
    """JSON-safe event log for a completed game (?idx=), for PBP replay."""
    idx = request.args.get("idx", "0")
    r = _get_past_result(idx)
    if r is None:
        return jsonify({"ok": False, "error": "unknown game"}), 404
    home = _result_team_name(r.get("home_team"))
    away = _result_team_name(r.get("away_team"))
    by_id = _result_roster_lookup(r)
    out = []
    for e in (r.get("event_log") or []):
        try:
            if not isinstance(e, dict):
                continue
            d = e.get("details", {}) or {}
            item = {
                "type": str(e.get("type", "")),
                "period": int(d.get("period", e.get("period", 1)) or 1),
                "timestamp": float(e.get("timestamp", 0) or 0),
                "desc": str(e.get("desc", "") or ""),
            }
            # Resolve the interesting name fields for display.
            for key in ("scorer_id", "shooter_id", "goaltender_id",
                        "player_id", "hitting_player_id",
                        "target_player_id"):
                if d.get(key) is not None:
                    item[key] = _player_name(by_id.get(str(d.get(key))))
            aids = d.get("assist_ids") or []
            if aids:
                item["assist_ids"] = [_player_name(by_id.get(str(a)))
                                     for a in aids]
            sq = d.get("shot_quality")
            if sq:
                item["shot_quality"] = str(sq)
            mins = d.get("minutes")
            if mins is not None:
                try:
                    item["minutes"] = int(mins)
                except Exception:
                    pass
            out.append(item)
        except Exception:
            continue
    try:
        from web_ui.bridge import TEAM_ABBR, _resolve_gm
        habbr = TEAM_ABBR.get(home, "")
        aabbr = TEAM_ABBR.get(away, "")
    except Exception:
        habbr = aabbr = ""
    return jsonify({"ok": True, "events": out, "home": home, "away": away,
                    "home_abbr": habbr, "away_abbr": aabbr,
                    "home_score": int(r.get("home_score", 0) or 0),
                    "away_score": int(r.get("away_score", 0) or 0)})
