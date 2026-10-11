"""Watch screen: live game viewer with a Qt rink visualizer.

Ported from web_ui/screens/watch.py + web_ui/templates/watch.html
(+ web_ui/static/js/watch.js / watch_modes.js / watch_present.js).

The web's HTML5 canvas was UNFINISHED upstream, so this does NOT port the
canvas -- it builds a functional Qt version instead: a QGraphicsView rink
with player dots driven by a REAL high-fidelity GameSim on a background
thread, plus Text (play-by-play feed), Chart (shot chart) and Box (live
box score) modes.

No Flask/HTTP: the sim's pbp_listeners feed a thread-safe queue drained
by a QTimer on the GUI thread. When the sim finishes, the game is flagged
as watched (so day-advance doesn't re-sim it) and the result is recorded
so the replay screen and box-score dialog can find it.
"""
import math
import queue
import threading
import time
from collections import deque
from datetime import date, datetime

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QComboBox,
    QTabWidget, QTextBrowser, QProgressBar,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsRectItem, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QWidget, QVBoxLayout, QFrame,
)
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QPen, QPainter, QPainterPath, QKeySequence, QShortcut,
)

from .base import BaseScreen
from ..dialogs.boxscore import BoxscoreDialog
from native_ui.safe import safe_call


# ----------------------------------------------------------------------
# Helpers (ported from web_ui/screens/watch.py, Flask removed)
# ----------------------------------------------------------------------

RINK_L, RINK_W = 200.0, 85.0
_EVENTS_CAP = 8000

_HIGHLIGHT_TYPES = {"goal", "hit", "penalty", "fight", "milestone",
                    "goalie_pulled", "icing", "offside", "penalty_shot"}
# Pacing (web _PACE parity): seconds of held "beat" per event type.
_PACE = {"goal": 2.0, "fight": 2.0, "penalty": 1.2, "period_end": 1.5,
         "period_start": 1.0, "milestone": 1.0}

# In-game tactics whiteboard categories (mainline pbp_visual_sim parity:
# (team.tactics key, short label, tactics.py catalog attribute)).
_TAC_CATS = (
    ("forecheck", "Forechk", "FORECHECK_SYSTEMS"),
    ("neutral_zone", "NeutZne", "NEUTRAL_ZONE_SYSTEMS"),
    ("dzone", "D-Zone", "DZONE_SYSTEMS"),
    ("ozone", "O-Zone", "OZONE_SYSTEMS"),
    ("breakout", "Brkout", "BREAKOUT_SYSTEMS"),
    ("pp", "PowPly", "POWERPLAY_SYSTEMS"),
    ("pk", "PenKill", "PENALTY_KILL_SYSTEMS"),
)


class _ClickLabel(QLabel):
    """QLabel that fires a callback on mouse click (collapsible panels)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_click = None
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        try:
            if callable(self.on_click):
                self.on_click()
        except Exception as e:
            print(f"[watch] strip click failed: {e}")
        super().mousePressEvent(event)


def _calc_winprob(home_score, away_score, period, clock,
                  home_shots, away_shots):
    """Home win probability: score lead + shot tilt, time-weighted.

    Faithful port of mainline pbp_visual_sim._calc_winprob.
    """
    lead = home_score - away_score
    try:
        t_rem = max(0.0, float(clock) + max(0, 3 - int(period)) * 1200)
    except Exception:
        t_rem = 3600.0
    x = lead * 1.7 / (1.0 + t_rem / 750.0)
    try:
        x += (int(home_shots) - int(away_shots)) * 0.015
    except Exception:
        pass
    p = 1.0 / (1.0 + math.exp(-x))
    return min(0.98, max(0.02, p))


def _momentum_reading(sim, mom, home_name, away_name):
    """Fused momentum (mainline pbp_visual_sim._momentum_reading parity).

    Prefers momentum.read_momentum(sim) when the sim carries a tracker;
    falls back to the local recent-events deques. Returns
    {"score": -100..100, "label", "drivers", "risk_home", "risk_away"}.
    """
    try:
        from momentum import read_momentum as _rm
        if sim is not None and \
                getattr(sim, "_momentum_events", None) is not None:
            return _rm(sim)
    except Exception:
        pass
    try:
        net = sum(mom.get("home", [])) - sum(mom.get("away", []))
    except Exception:
        net = 0.0
    s = max(-100.0, min(100.0, net / 24.0 * 100.0))
    side = "Even" if abs(s) < 15 else ("Home" if s > 0 else "Away")
    return {"score": s, "label": side, "drivers": [],
            "risk_home": 1.0, "risk_away": 1.0}


def _tension_color(v):
    if v >= 75:
        return "#ff6b6b"
    if v >= 50:
        return "#ff9f5c"
    if v >= 25:
        return "#ffd166"
    return "#7bc96f"


def _tension_mood(v):
    if v >= 75:
        return "BOILING"
    if v >= 50:
        return "CHIPPY"
    if v >= 25:
        return "HEATING"
    return "CALM"


def _tension_breakdown(home_team, away_team, gm):
    """Pre-game tension drivers (mainline PBPVisualSim init parity)."""
    try:
        import reputation_system as _rs
        rivalries = safe_call(lambda: getattr(gm, "rivalries", None) or [],
                              [], context="watch/tension:rivalries") or []
        bd = _rs.game_tension_breakdown(
            home_team, away_team, rivalries,
            is_playoff=False, series_game=0)
        if isinstance(bd, dict):
            return bd
    except Exception:
        pass
    return {"tension": 0.0, "drivers": []}


def _side_of(name, home_name, away_name):
    """'home'/'away'/None for a team name (momentum attribution)."""
    try:
        n = str(name or "").strip().lower()
        if n and n == str(home_name or "").strip().lower():
            return "home"
        if n and n == str(away_name or "").strip().lower():
            return "away"
    except Exception:
        pass
    return None


def _resolve_gm(game):
    return getattr(game, "game_manager", None) or game


def _team_name(t):
    if isinstance(t, str):
        return t
    return safe_call(lambda: getattr(t, "team_name", str(t)), "?") or "?"


def _abbr(name):
    try:
        from web_ui.bridge import TEAM_ABBR
        hit = TEAM_ABBR.get(name)
        if hit:
            return hit
    except Exception:
        pass
    try:
        return "".join(w[0] for w in str(name).split()[:2]).upper() or "?"
    except Exception:
        return "?"


def _date_key(value):
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def _fmt_clock(seconds):
    try:
        s = max(0, int(seconds))
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return "0:00"


def _period_label(p):
    try:
        p = int(p)
    except (TypeError, ValueError):
        p = 1
    if p <= 3:
        return f"P{p}"
    if p == 4:
        return "OT"
    return "SO"


def _player_name(p):
    if p is None:
        return "Unknown"
    return (getattr(p, "full_name", None) or getattr(p, "name", None)
            or str(p))


def _pos_short(p):
    pos = safe_call(lambda: getattr(p, "primary_position", None))
    val = safe_call(lambda: getattr(pos, "value", None)) or \
        safe_call(lambda: getattr(pos, "name", ""), "") or ""
    return str(val)


def _is_goalie(p):
    name = str(safe_call(lambda: getattr(
        getattr(p, "primary_position", None), "name", ""), "") or "").upper()
    return "GOALIE" in name


# ----------------------------------------------------------------------
# Rink drawing (shared by the visualizer and the shot chart)
# ----------------------------------------------------------------------

_ICE = QColor("#eef1f6")
_ICE_EDGE = QColor("#c8d2e0")
_RED = QColor("#d0342c")
_BLUE = QColor("#2b5fc7")


def draw_rink(scene):
    """Draw an NHL rink (feet) into a QGraphicsScene. Never raises."""
    try:
        # Dark backdrop + ice surface
        bg = QGraphicsRectItem(-14, -14, RINK_L + 28, RINK_W + 28)
        bg.setBrush(QBrush(QColor("#0b0f1a")))
        bg.setPen(QPen(Qt.NoPen))
        bg.setZValue(-10)
        scene.addItem(bg)

        ice = QGraphicsRectItem(0, 0, RINK_L, RINK_W)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, RINK_L, RINK_W), 28, 28)
        ice_item = scene.addPath(path, QPen(_ICE_EDGE, 1.2), QBrush(_ICE))
        ice_item.setZValue(-9)

        def _line(x, color, width=0.9):
            it = scene.addLine(x, 2, x, RINK_W - 2, QPen(color, width))
            it.setZValue(-8)
            return it

        _line(100, _RED, 1.0)          # center red line
        _line(25, _BLUE, 1.0)          # blue lines
        _line(175, _BLUE, 1.0)
        _line(11, _RED, 0.6)           # goal lines
        _line(189, _RED, 0.6)

        # Center ice circle
        c = scene.addEllipse(100 - 15, RINK_W / 2 - 15, 30, 30,
                             QPen(_BLUE, 0.8), QBrush(Qt.NoBrush))
        c.setZValue(-8)
        dot = scene.addEllipse(100 - 1.2, RINK_W / 2 - 1.2, 2.4, 2.4,
                               QPen(Qt.NoPen), QBrush(_BLUE))
        dot.setZValue(-8)

        # Faceoff circles + dots
        for fx, fy in ((31, 22), (31, 63), (169, 22), (169, 63)):
            ring = scene.addEllipse(fx - 15, fy - 15, 30, 30,
                                    QPen(_RED, 0.8), QBrush(Qt.NoBrush))
            ring.setZValue(-8)
            d = scene.addEllipse(fx - 1.2, fy - 1.2, 2.4, 2.4,
                                 QPen(Qt.NoPen), QBrush(_RED))
            d.setZValue(-8)

        # Creases (light blue half-discs at each net)
        for gx, flip in ((11, 1), (189, -1)):
            crease = QPainterPath()
            crease.moveTo(gx, RINK_W / 2 - 6)
            crease.arcTo(QRectF(gx - 6 * flip, RINK_W / 2 - 6, 12, 12),
                         270 if flip == 1 else 90, 180)
            crease.closeSubpath()
            it = scene.addPath(crease, QPen(_BLUE, 0.6),
                               QBrush(QColor(173, 206, 250, 120)))
            it.setZValue(-7)

        # Nets
        for gx in (10, 188):
            net = scene.addRect(gx, RINK_W / 2 - 3, 2, 6,
                                QPen(Qt.NoPen), QBrush(_RED))
            net.setZValue(-6)
    except Exception as e:
        print(f"[watch] draw_rink failed: {e}")


# ----------------------------------------------------------------------
# Live sim plumbing (module-level, like web_ui/screens/watch.py)
# ----------------------------------------------------------------------

_watch_lock = threading.Lock()
_watch = {
    "thread": None, "queue": None, "sim": None,
    "events": [], "done": False, "error": None,
    "home": None, "away": None, "date": None,
    "home_name": "", "away_name": "",
    "home_abbr": "", "away_abbr": "",
    "id_meta": {}, "game": None,
    # OBS-3: set by _finish_sim when result processing failed and the
    # game was deliberately left UN-watched so the day sim re-processes
    # it. Surfaced loudly in the UI by WatchScreen._finish().
    "finish_alert": None,
}

# When set (by schedule.py's Watch action), _next_game() returns this
# entry instead of auto-picking. Cleared after the sim starts.
_target_entry = None


def set_target_entry(entry):
    """Pin the next watch sim to a specific schedule entry (dict)."""
    global _target_entry
    _target_entry = entry


def _build_id_meta(home_team, away_team):
    meta = {}
    for idx, team in enumerate((home_team, away_team)):
        roster = safe_call(lambda: list(getattr(team, "roster", None) or []), []) or []
        for p in roster:
            try:
                pid = getattr(p, "id", None)
                if pid is None:
                    continue
                meta[str(pid)] = {
                    "team": idx,
                    "name": _player_name(p),
                    "goalie": _is_goalie(p),
                    "jersey": str(safe_call(lambda: getattr(
                        p, "jersey_number", ""), "") or ""),
                }
            except Exception:
                continue
    return meta


def _next_game(game):
    """Next unplayed game: user's team first, else any league game.

    If set_target_entry() pinned a specific schedule entry (e.g. from
    the schedule screen's Watch button), that entry wins.
    """
    global _target_entry
    if _target_entry is not None:
        entry = _target_entry
        _target_entry = None  # one-shot
        return entry
    try:
        from .schedule import (
            _schedule_entries, _game_played_state, _results_by_date)
    except Exception:
        return None
    try:
        gm = _resolve_gm(game)
        user_team = safe_call(lambda: getattr(gm, "user_team", None))
        my_name = _team_name(user_team)
        today = safe_call(lambda: getattr(gm, "current_date", None)) or \
            safe_call(lambda: getattr(game, "current_date", None))
        today = _date_key(today)
        by_date = _results_by_date(game)
        mine, other = [], []
        for entry in _schedule_entries(game):
            try:
                played = _game_played_state(entry, game, by_date)[0]
                if played:
                    continue
                d = _date_key(entry.get("date"))
                if today is not None and d is not None and d < today:
                    continue
                hn, an = _team_name(entry.get("home_team")), \
                    _team_name(entry.get("away_team"))
                if not hn or not an or hn == "?" or an == "?":
                    continue
                (mine if (hn == my_name or an == my_name) else other)\
                    .append((d or date.max, entry))
            except Exception:
                continue
        mine.sort(key=lambda t: t[0])
        other.sort(key=lambda t: t[0])
        pool = mine or other
        return pool[0][1] if pool else None
    except Exception as e:
        print(f"[watch] _next_game failed: {e}")
        return None


def _team_obj(entry_team, gm):
    if not isinstance(entry_team, str):
        return entry_team
    want = entry_team.strip().lower()
    teams = safe_call(lambda: list(getattr(getattr(gm, "league", None),
                                      "teams", None) or []), []) or []
    for t in teams:
        if _team_name(t).strip().lower() == want:
            return t
    return None


def _ensure_live_sim(game):
    """Start a real high-fidelity GameSim for the next game (background).

    Returns the _watch dict, or None when no game is available.
    """
    with _watch_lock:
        t = _watch["thread"]
        if t is not None and t.is_alive():
            return _watch
        _watch["error"] = None
        entry = _next_game(game)
        if entry is None:
            _watch["error"] = "No upcoming games on the schedule."
            return None
        gm = _resolve_gm(game)
        home = _team_obj(entry.get("home_team"), gm)
        away = _team_obj(entry.get("away_team"), gm)
        if home is None or away is None:
            _watch["error"] = "Could not resolve the next game's teams."
            return None
        try:
            from simulation import GameSim
        except Exception as e:
            _watch["error"] = f"Sim engine unavailable: {e}"
            return None

        q = queue.Queue()
        sim = GameSim(home, away, high_fidelity=True)
        try:
            sim.league = safe_call(lambda: getattr(gm, "league", None))
        except Exception:
            pass
        game_date = _date_key(entry.get("date"))

        # Grudge-week presentation (canonical day-sim order: pre-game).
        # Never raises; no-ops when the matchup has no feud history.
        try:
            _gmkt = getattr(gm, "_grudge_week_market", None)
            if callable(_gmkt):
                _gmkt(game_date, home, away)
        except Exception:
            pass

        def _listener(ev):
            try:
                ev = dict(ev)
            except Exception:
                return
            try:
                q.put(ev)
            except Exception:
                pass
            try:
                with _watch_lock:
                    _watch["events"].append(ev)
                    if len(_watch["events"]) > _EVENTS_CAP:
                        del _watch["events"][:len(_watch["events"])
                                            - _EVENTS_CAP]
            except Exception:
                pass

        try:
            sim.pbp_listeners.append(_listener)
        except Exception:
            _watch["error"] = "Sim would not attach a PBP listener."
            return None

        def _run():
            # Capture run()'s own return (winner, loser, scores, game_log,
            # notable_events) -- the canonical inputs for result processing.
            run_result = None
            try:
                run_result = sim.run()
            except Exception as e:
                try:
                    q.put({"type": "sim_error", "error": str(e)})
                except Exception:
                    pass
            finally:
                try:
                    hs = int(safe_call(lambda: sim.home_score, 0) or 0)
                    aws = int(safe_call(lambda: sim.away_score, 0) or 0)
                    per = int(safe_call(lambda: sim.period, 3) or 3)
                    q.put({"type": "game_end", "home_score": hs,
                           "away_score": aws, "period": per})
                    _finish_sim(game, sim, home, away, hs, aws,
                                per, game_date, run_result)
                except Exception as e:
                    print(f"[watch] finish failed: {e}")
                with _watch_lock:
                    _watch["done"] = True

        _watch.update(
            thread=None, queue=q, sim=sim, events=[],
            done=False, error=None, game=game,
            home=home, away=away, date=game_date,
            home_name=_team_name(home), away_name=_team_name(away),
            home_abbr=_abbr(_team_name(home)),
            away_abbr=_abbr(_team_name(away)),
            id_meta=_build_id_meta(home, away),
        )
        thread = threading.Thread(target=_run, daemon=True,
                                  name="puck-watch-sim")
        _watch["thread"] = thread
        thread.start()
        return _watch


def _set_finish_alert(msg):
    """Record a loud, user-visible finish failure (OBS-3).

    Runs on the background sim thread; WatchScreen._finish() surfaces it
    on the GUI thread via the status line, the ticker, and a dialog.
    """
    with _watch_lock:
        _watch["finish_alert"] = msg
    print(f"[watch] FINISH ALERT: {msg}")


def _mark_schedule_watched(gm, today, hn, an, hs, aws):
    """Flag the real schedule entry watched.

    OBS-3: called ONLY after the result was confirmed recorded, so no
    exception path can leave a game marked-watched but unrecorded.
    Mirrors web_ui/screens/watch.py::_mark_game_watched for the watched
    flag. Dict entries get the flag in place. Tuple entries are
    immutable and -- worse -- simulate_day converts them to FRESH dicts
    (game_manager.py), which would drop any flag. So replace a matching
    tuple in-place with an equivalent dict carrying watched=True.
    simulate_day then takes the dict path (same object, flag preserved)
    and its `game.get('watched')` guard skips re-simming. This surpasses
    the web version, which skips tuples entirely.
    """
    try:
        league = safe_call(lambda: getattr(gm, "league", None), None,
                           context="watch/finish_sim:resolve_league")
        sched = safe_call(lambda: getattr(league, "schedule", None), None,
                          context="watch/finish_sim:resolve_schedule")
        if sched is not None:
            for idx, g in enumerate(sched):
                try:
                    if isinstance(g, dict):
                        if _date_key(g.get("date")) != _date_key(today):
                            continue
                        if _team_name(g.get("home_team")) == hn and \
                                _team_name(g.get("away_team")) == an:
                            g["watched"] = True
                            g["watched_home_score"] = hs
                            g["watched_away_score"] = aws
                            break
                    elif isinstance(g, tuple) and len(g) >= 3:
                        # (date, home_team, away_team[, ...]) -- match and
                        # promote to a watched dict in place.
                        if _date_key(g[0]) != _date_key(today):
                            continue
                        if _team_name(g[1]) == hn and \
                                _team_name(g[2]) == an:
                            sched[idx] = {
                                "date": g[0],
                                "home_team": g[1],
                                "away_team": g[2],
                                "event_type": "GAME",
                                "watched": True,
                                "watched_home_score": hs,
                                "watched_away_score": aws,
                            }
                            break
                except Exception:
                    continue
    except Exception:
        pass


def _finish_sim(game, sim, home_team, away_team, hs, aws, period,
                game_date, run_result=None):
    """Never raises: fail-closed finish (OBS-3).

    Any unexpected failure leaves the game UN-watched and records a loud
    alert, so the day sim still processes it normally -- a stranded game
    (marked-watched but never recorded) is impossible by construction.
    """
    try:
        _finish_sim_impl(game, sim, home_team, away_team, hs, aws,
                         period, game_date, run_result)
    except Exception as e:
        _set_finish_alert(
            "⚠️ The watched game could not be recorded "
            f"({type(e).__name__}: {e}). It was left un-watched so the "
            "day sim will process it normally -- advance the day to "
            "re-sim it.")


def _finish_sim_impl(game, sim, home_team, away_team, hs, aws, period,
                     game_date, run_result=None):
    """Record the watched result canonically, then flag the entry watched.

    OBS-3 atomicity (fail-closed): the result is processed FIRST and the
    schedule entry is marked watched ONLY after the record is confirmed.
    A processing failure therefore leaves the game exactly as if it had
    never been watched -- the day sim's `game.get('watched')` guard does
    not fire and the game is re-processed normally instead of stranded.

    Routes the result through GameManager._process_single_game_result --
    the same canonical post-game pipeline the day-sim uses for GameSim
    games. That builder supplies player ratings, lines, TOI/fatigue,
    three stars, the media engine, news log, and narrative hooks, and it
    internally performs the record + standings update -- so the direct
    _record_game_result and _update_standings_fast calls that used to
    live here are gone (calling both double-recorded).

    Exactly-once: the high-fidelity GameSim already flushed player season
    stats live, so stats_from_events=False; it modeled fights/brawls live,
    so the narrative hook runs with roll_incidents=False (the day-sim
    GameSim branch does the same -- rolling again would double-record
    incidents in the rivalry store).
    """
    gm = _resolve_gm(game)
    today = game_date or safe_call(
        lambda: getattr(gm, "current_date", None),
        context="watch/finish_sim:resolve_date")
    hn, an = _team_name(home_team), _team_name(away_team)
    # NOTE (OBS-3): the schedule entry is NOT flagged here. It is marked
    # watched only at the very end, after the result is confirmed
    # recorded -- see _mark_schedule_watched below.
    # 1. Canonical inputs: unpack the sim's own run() return
    #    (winner, loser, scores, game_log, notable_events). If the sim
    #    raised mid-game, fall back to attribute reads / score-derived
    #    values so the game is still recorded.
    winner = loser = None
    events = notable = None
    try:
        if run_result is not None:
            winner, loser, _scores, events, notable = run_result
    except Exception:
        winner = loser = None
        events = notable = None
    if winner is None:
        # The canonical builder needs the winner as a team OBJECT (it
        # reads winner.team_name to label recent_results W/L/OTL); without
        # this both teams get labeled as losers in the feed.
        winner = home_team if hs > aws else away_team
    if loser is None:
        loser = away_team if winner is home_team else home_team
    if events is None:
        events = safe_call(
            lambda: list(getattr(sim, "game_log", None) or []), [],
            context="watch/finish_sim:game_log") or []
    if notable is None:
        notable = safe_call(
            lambda: list(getattr(sim, "notable_events", None) or []), [],
            context="watch/finish_sim:notable") or []
    # 3. Canonical post-game pipeline (day-sim order for GameSim games):
    #    career GP credit -> narrative post-game -> process result ->
    #    drain headlines. _process_single_game_result builds the full
    #    result dict (player ratings, lines, TOI/fatigue, three stars,
    #    media engine, news log, post-game emails) and internally calls
    #    _record_game_result + the standings update.
    went_ot = any(isinstance(e, dict) and e.get("period", 0) > 3
                  for e in notable)
    went_so = any(isinstance(e, dict) and
                  (e.get("period", 0) == 5
                   or e.get("event") == "Shootout Goal")
                  for e in notable)
    try:
        _credit = getattr(gm, "_credit_nhl_games_played", None)
        if callable(_credit):
            _credit(home_team, away_team, preseason=False)
    except Exception:
        pass
    try:
        _npg = getattr(gm, "_narrative_postgame", None)
        if callable(_npg):
            _user_team = safe_call(lambda: getattr(gm, "user_team", None))
            _npg(sim, home_team, away_team, (hs, aws),
                 went_ot=went_ot, shootout=went_so,
                 roll_incidents=False,
                 deliver_headlines=bool(
                     _user_team is not None
                     and _user_team in (home_team, away_team)),
                 game_date=today)
    except Exception:
        pass
    # 2. Record the result FIRST (OBS-3 atomicity). The schedule entry is
    #    only flagged watched afterwards, on a confirmed record -- so a
    #    failure here leaves the game un-watched and the day sim picks it
    #    up normally instead of stranding it.
    recorded = False
    _proc = getattr(gm, "_process_single_game_result", None)
    if callable(_proc):
        # Canonical: record + standings happen inside (exactly once). On
        # failure the fallback below is deliberately NOT run -- a partial
        # canonical write followed by a manual record would double-count.
        try:
            _proc(today, home_team, away_team, winner, loser,
                  (hs, aws), events, notable, sim,
                  stats_from_events=False, preseason=False)
            recorded = True
        except Exception as e:
            _set_finish_alert(
                "⚠️ Result recording failed "
                f"({type(e).__name__}: {e}). The game was left un-watched "
                "so the day sim will re-process it -- advance the day to "
                "re-sim it. (It is NOT recorded yet.)")
    else:
        # Fallback: the game manager predates the canonical API. Record
        # the raw sim output the old way so the game is never dropped.
        # Exactly-once: this branch only runs when the canonical call
        # above did not, so record + standings still happen exactly once.
        try:
            rec = getattr(game, "_record_game_result", None)
            if callable(rec):
                rec({
                    "date": today,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": hs,
                    "away_score": aws,
                    "winner": winner,
                    "watched": True,
                    "overtime": went_ot,
                    "shootout": went_so,
                    "events": events,
                    "notable_events": notable,
                    "event_log": list(
                        getattr(sim, "event_log", None) or []),
                    "game_stats": dict(
                        getattr(sim, "game_stats", None) or {}),
                    "team_stats": dict(
                        getattr(sim, "team_stats", None) or {}),
                })
                recorded = True
            else:
                gr = getattr(game, "game_results", None)
                if isinstance(gr, list):
                    gr.append({
                        "date": today,
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_score": hs,
                        "away_score": aws,
                        "winner": winner,
                    })
                    recorded = True
            if gm is not None and not isinstance(home_team, str) \
                    and not isinstance(away_team, str):
                upd = getattr(gm, "_update_standings_fast", None)
                if callable(upd):
                    upd(home_team, away_team, winner, (hs, aws),
                        went_to_ot=(went_ot or went_so), preseason=False)
        except Exception as e:
            _set_finish_alert(
                "⚠️ Fallback result recording failed "
                f"({type(e).__name__}: {e}). The game was left un-watched "
                "so the day sim will re-process it -- advance the day to "
                "re-sim it. (It is NOT recorded yet.)")
    # 3. Lore: deliver any headlines the sim collected -- the same call
    #    the day-sim makes right after result processing.
    try:
        import headlines as _hl_mod
        _drain = getattr(_hl_mod, "drain_sim_headlines", None)
        if callable(_drain):
            _drain(gm, sim)
    except Exception:
        pass
    # 4. OBS-3: flag the schedule entry watched ONLY on a confirmed
    #    record. Every failure path above leaves the game un-watched, so
    #    the day sim still processes it -- no stranded games, ever.
    if recorded:
        _mark_schedule_watched(gm, today, hn, an, hs, aws)


def _normalize_gs(game_stats):
    out = {}
    try:
        for pid, st in (game_stats or {}).items():
            if isinstance(st, dict):
                out[str(pid)] = st
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------
# Natural-language event text (ported from watch_modes.js eventLine)
# ----------------------------------------------------------------------

def _shot_detail(ev):
    bits = []
    if ev.get("shot_type"):
        bits.append(str(ev["shot_type"]).replace("_", " "))
    if ev.get("location"):
        bits.append(str(ev["location"]).replace("_", " "))
    d = ev.get("distance")
    if d is not None:
        try:
            bits.append(f"{round(float(d))} ft")
        except Exception:
            pass
    return f" ({', '.join(bits)})" if bits else ""


def _event_text(ev):
    """(html, big) for one pbp event."""
    t = str(ev.get("type", ""))
    clk = _fmt_clock(ev.get("clock", 0))
    pl = _period_label(ev.get("period", 1))
    pre = f'<span style="color:#8b95ab">{pl} {clk}</span> '
    if t == "game_start":
        return (pre + f"<b>Puck drop: {ev.get('away_team','')} at "
                f"{ev.get('home_team','')}</b>", True)
    if t == "period_start":
        return pre + f"Start of period {ev.get('period', 1)}.", False
    if t == "period_end":
        return pre + f"End of period {ev.get('period', 1)}.", False
    if t == "game_end":
        return pre + "<b>Final.</b>", True
    if t == "shot":
        return (pre + f"Shot — <b>{_player_name(ev.get('shooter'))}</b>"
                f"{_shot_detail(ev)}.", False)
    if t == "missed_shot":
        return (pre + f"Missed — <b>{_player_name(ev.get('shooter'))}</b>"
                f"{_shot_detail(ev)}.", False)
    if t == "blocked_shot":
        blk = ev.get("blocker")
        by = f" by <b>{_player_name(blk)}</b>" if blk else ""
        return (pre + f"Blocked — <b>{_player_name(ev.get('shooter'))}</b>"
                f"{_shot_detail(ev)}{by}.", False)
    if t == "goal":
        a = ev.get("assists") or []
        al = (" <span style=\"color:#8b95ab\">(assists: "
              f"{', '.join(_player_name(x) for x in a)})</span>") if a else ""
        score = (f" <b>{ev.get('home_score', 0)}–"
                 f"{ev.get('away_score', 0)}</b>")
        en = " <b>(empty net)</b>" if ev.get("empty_net") else ""
        return (pre + "🚨 <b>GOAL — "
                f"{_player_name(ev.get('shooter'))}</b>"
                f"{_shot_detail(ev)}{al}{en}{score}", True)
    if t == "penalty":
        inf = ev.get("infraction") or ev.get("reason") or "infraction"
        mins = ev.get("minutes")
        m = f" ({mins} min)" if mins else ""
        return (pre + f"<b>Penalty</b> — {_player_name(ev.get('player'))}"
                f" ({inf}){m}.", True)
    if t == "penalty_shot":
        return (pre + f"<b>Penalty shot</b> — "
                f"{_player_name(ev.get('player'))}.", True)
    if t == "hit":
        return (pre + f"Hit — <b>{_player_name(ev.get('hitting_player'))}</b>"
                f" on <b>{_player_name(ev.get('target_player'))}</b>.",
                False)
    if t == "fight":
        return pre + "🥊 <b>Fight!</b>", True
    if t == "milestone":
        kind = str(ev.get("kind", "milestone")).replace("_", " ").title()
        pl_ = ev.get("player")
        who = f" — <b>{_player_name(pl_)}</b>" if pl_ else ""
        return pre + f"⭐ <b>{kind}</b>{who}", True
    if t == "icing":
        return pre + "Icing.", False
    if t == "offside":
        return pre + "Offside.", False
    if t == "goalie_pulled":
        return (pre + "<b>Empty net — goalie pulled.</b>", True)
    if t == "save":
        q = ev.get("shot_quality")
        qd = f" ({q} danger)" if q else ""
        return (pre + f"Save — <b>{_player_name(ev.get('goaltender'))}</b>"
                f"{qd}.", False)
    if t == "faceoff":
        return pre + '<span style="color:#8b95ab">Faceoff.</span>', False
    if t == "sim_error":
        return pre + f"<b>Sim error:</b> {ev.get('error', '')}", True
    return (pre + f'<span style="color:#8b95ab">'
            f"{t.replace('_', ' ')}.</span>", False)


# ----------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------

class _ClickScene(QGraphicsScene):
    """QGraphicsScene that forwards mouse presses to a callback.

    Assigning ``scene.mousePressEvent = fn`` on an instance does NOT work
    in real Qt (event dispatch calls the C++ virtual), so this subclass
    is required for the shot chart's click-to-inspect markers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_click = None

    def mousePressEvent(self, event):
        try:
            if callable(self.on_click):
                self.on_click(event)
        except Exception as e:
            print(f"[watch] chart click failed: {e}")
        super().mousePressEvent(event)


class WatchScreen(BaseScreen):
    """Live game viewer: Qt rink visualizer + text / chart / box modes."""

    title = "Watch"

    def __init__(self, game, main_window, parent=None):
        self._watching = False
        self._paused = False
        self._finished = False
        self._speed = 2.0
        self._follow_puck = False
        self._follow_player_pid = None  # str(pid) the camera follows
        self._hold_until = 0.0
        self._skate = None          # latest skate snapshot
        self._score = {"home": 0, "away": 0}
        self._period = 1
        self._clock = 20 * 60
        self._dots = {}             # str(pid) -> QGraphicsEllipseItem
        self._puck_item = None
        self._text_count = 0
        self._last_box_refresh = 0.0
        # D-11 (mainline pbp_visual_sim parity): live game-state meters.
        self._winprob = 0.5         # home win probability
        self._shots = {"home": 0, "away": 0}
        self._mom = {"home": deque(maxlen=10), "away": deque(maxlen=10)}
        self._tension_base = {"tension": 0.0, "drivers": []}
        self._tension_live = []     # in-game contributors: {label, points}
        self._momentum_open = False
        self._tension_open = False
        self._last_strip_refresh = 0.0
        self._fast_forward = False  # sim-to-end: drain the queue instantly
        self._suppress_beats = False
        self._home_name = ""
        self._away_name = ""
        # D-11: in-game tactics whiteboard state (mainline parity).
        self._tac_pending = {}      # cat -> system key (coach-control mode)
        self._tac_response_text = ""
        self._tac_built = False
        self._card_dialog = None    # player-card popup (InGamePopup port)
        super().__init__(game, main_window, parent)

        self._pump_timer = QTimer(self)
        self._pump_timer.setInterval(100)
        self._pump_timer.timeout.connect(self._pump)

        # Keyboard: Space = pause, C = camera (web parity).
        QShortcut(QKeySequence(Qt.Key_Space), self,
                  activated=self._toggle_pause,
                  context=Qt.WindowShortcut)
        QShortcut(QKeySequence("C"), self,
                  activated=self._toggle_camera,
                  context=Qt.WindowShortcut)

    # -- layout -------------------------------------------------------

    def _build_body(self):
        # Scorebug
        self._scorebug = QLabel("—")
        self._scorebug.setObjectName("dialog-title")
        self._scorebug.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._scorebug)

        # D-11 (mainline pbp_visual_sim parity): live game-state strips --
        # win-probability meter, momentum bar, tension meter, matchup
        # (shadowing) indicator.
        strip = QHBoxLayout()
        strip.setSpacing(12)
        self._winprob_bar = QProgressBar()
        self._winprob_bar.setRange(0, 100)
        self._winprob_bar.setValue(50)
        self._winprob_bar.setTextVisible(False)
        self._winprob_bar.setFixedWidth(110)
        self._winprob_bar.setFixedHeight(10)
        self._winprob_bar.setToolTip("Home win probability (score lead + "
                                     "shot tilt, time-weighted)")
        strip.addWidget(QLabel("Win prob:"))
        strip.addWidget(self._winprob_bar)
        self._winprob_label = QLabel("50%")
        self._winprob_label.setStyleSheet("font-weight: bold;")
        strip.addWidget(self._winprob_label)
        strip.addSpacing(8)
        self._mom_bar = QProgressBar()
        self._mom_bar.setRange(0, 100)
        self._mom_bar.setValue(50)
        self._mom_bar.setTextVisible(False)
        self._mom_bar.setFixedWidth(110)
        self._mom_bar.setFixedHeight(10)
        self._mom_bar.setToolTip("Momentum: recent shots, goals, fights "
                                 "(click for drivers)")
        strip.addWidget(QLabel("Momentum:"))
        strip.addWidget(self._mom_bar)
        self._momentum_label = _ClickLabel("Even")
        self._momentum_label.setToolTip("Click for momentum drivers")
        self._momentum_label.on_click = self._toggle_momentum_panel
        strip.addWidget(self._momentum_label)
        strip.addSpacing(8)
        self._tension_label = _ClickLabel("🟢 CALM 0.0")
        self._tension_label.setToolTip("Game intensity (click for drivers)")
        self._tension_label.on_click = self._toggle_tension_panel
        strip.addWidget(QLabel("Tension:"))
        strip.addWidget(self._tension_label)
        strip.addSpacing(8)
        self._matchup_label = QLabel("Matchup: –")
        self._matchup_label.setToolTip("Live line matchup / shadowing")
        strip.addWidget(self._matchup_label)
        strip.addStretch()
        self._layout.addLayout(strip)
        # Collapsible driver panels (mainline momentum/tension panels).
        self._momentum_panel = QLabel("")
        self._momentum_panel.setWordWrap(True)
        self._momentum_panel.setStyleSheet(
            "color: #aeb6c8; font-size: 12px; padding: 2px 4px;")
        self._momentum_panel.hide()
        self._layout.addWidget(self._momentum_panel)
        self._tension_panel = QLabel("")
        self._tension_panel.setWordWrap(True)
        self._tension_panel.setStyleSheet(
            "color: #aeb6c8; font-size: 12px; padding: 2px 4px;")
        self._tension_panel.hide()
        self._layout.addWidget(self._tension_panel)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self._btn_start = QPushButton("▶ Watch Next Game")
        self._btn_start.setObjectName("primary-btn")
        self._btn_start.setCursor(Qt.PointingHandCursor)
        self._btn_start.clicked.connect(self._start)
        ctrl.addWidget(self._btn_start)

        self._btn_pause = QPushButton("⏸ Pause")
        self._btn_pause.setCursor(Qt.PointingHandCursor)
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self._toggle_pause)
        ctrl.addWidget(self._btn_pause)

        # D-11: sim-to-end (mainline PBPVisualSim._sim_to_end parity).
        self._btn_simend = QPushButton("⏩ Sim to End")
        self._btn_simend.setCursor(Qt.PointingHandCursor)
        self._btn_simend.setEnabled(False)
        self._btn_simend.setToolTip("Skip ahead: consume the rest of the "
                                    "game instantly")
        self._btn_simend.clicked.connect(self._sim_to_end)
        ctrl.addWidget(self._btn_simend)

        ctrl.addWidget(QLabel("Speed:"))
        self._speed_box = QComboBox()
        for label, val in (("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0),
                           ("4×", 4.0)):
            self._speed_box.addItem(label, val)
        self._speed_box.setCurrentIndex(2)
        self._speed_box.currentIndexChanged.connect(
            lambda i: setattr(self, "_speed",
                              float(self._speed_box.itemData(i))))
        ctrl.addWidget(self._speed_box)

        self._btn_camera = QPushButton("🎥 Camera: Full Rink")
        self._btn_camera.setCursor(Qt.PointingHandCursor)
        self._btn_camera.clicked.connect(self._toggle_camera)
        ctrl.addWidget(self._btn_camera)

        self._btn_stats = QPushButton("📊 Stats")
        self._btn_stats.setCheckable(True)
        self._btn_stats.setCursor(Qt.PointingHandCursor)
        self._btn_stats.setToolTip(
            "Toggle the live stats overlay (goals, shots, hits, penalties)")
        self._btn_stats.toggled.connect(self._toggle_stats_overlay)
        ctrl.addWidget(self._btn_stats)

        ctrl.addStretch()
        self._btn_replay = QPushButton("📼 Past Games")
        self._btn_replay.setCursor(Qt.PointingHandCursor)
        self._btn_replay.clicked.connect(self._go_replay)
        ctrl.addWidget(self._btn_replay)
        self._layout.addLayout(ctrl)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #8b95ab; font-size: 12px;")
        self._status.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._status)

        # Modes
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, 1)

        # Visual
        visual = QWidget()
        vl = QVBoxLayout(visual)
        vl.setContentsMargins(0, 4, 0, 0)
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-14, -14, RINK_L + 28, RINK_W + 28)
        draw_rink(self._scene)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setMinimumHeight(420)
        vl.addWidget(self._view, 1)
        # Click-to-follow: clicking a player dot makes the camera follow
        # that skater (web parity). Click empty ice to release.
        self._view.mousePressEvent = self._rink_click
        # Stats overlay: floating panel over the rink (web parity).
        self._stats_overlay = QLabel("", self._view)
        self._stats_overlay.setStyleSheet(
            "background: rgba(11, 15, 26, 0.88); color: #e8ecf4; "
            "font-size: 13px; padding: 10px 14px; border-radius: 8px; "
            "border: 1px solid #2a3350;")
        self._stats_overlay.setWordWrap(True)
        self._stats_overlay.move(12, 12)
        self._stats_overlay.setMinimumWidth(220)
        self._stats_overlay.hide()
        self._ticker = QLabel("Press “Watch Next Game” to start a live sim.")
        self._ticker.setObjectName("ticker")
        self._ticker.setAlignment(Qt.AlignCenter)
        self._ticker.setWordWrap(True)
        vl.addWidget(self._ticker)
        self._tabs.addTab(visual, "📺 Visual")

        # Text
        self._text_feed = QTextBrowser()
        self._text_feed.setOpenExternalLinks(False)
        self._tabs.addTab(self._text_feed, "📝 Text")

        # Chart
        chart = QWidget()
        cl = QHBoxLayout(chart)
        cl.setContentsMargins(0, 4, 0, 0)
        self._chart_scene = _ClickScene(self)
        self._chart_scene.setSceneRect(-14, -14, RINK_L + 28, RINK_W + 28)
        self._chart_scene.on_click = self._chart_click
        draw_rink(self._chart_scene)
        self._chart_view = QGraphicsView(self._chart_scene)
        self._chart_view.setRenderHint(QPainter.Antialiasing)
        self._chart_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chart_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chart_view.setMinimumHeight(300)
        cl.addWidget(self._chart_view, 3)
        side = QVBoxLayout()
        side.setSpacing(8)
        self._chart_legend = QLabel("")
        self._chart_legend.setWordWrap(True)
        self._chart_legend.setStyleSheet("font-size: 13px;")
        side.addWidget(self._chart_legend)
        self._chart_detail = QLabel(
            "Click any shot marker for the play details.")
        self._chart_detail.setWordWrap(True)
        self._chart_detail.setStyleSheet("color: #8b95ab; font-size: 13px;")
        side.addWidget(self._chart_detail)
        side.addStretch()
        cl.addLayout(side, 1)
        self._tabs.addTab(chart, "🎯 Shot Chart")
        self._chart_markers = []  # [(item, ev_dict)]

        # Box
        box_scroll = QScrollArea()
        box_scroll.setWidgetResizable(True)
        box_scroll.setFrameShape(QFrame.NoFrame)
        box_inner = QWidget()
        self._box_layout = QVBoxLayout(box_inner)
        self._box_layout.setAlignment(Qt.AlignTop)
        self._box_layout.setSpacing(8)
        box_scroll.setWidget(box_inner)
        self._tabs.addTab(box_scroll, "📊 Box Score")
        self._box_tab_index = self._tabs.count() - 1

        # D-11: in-game tactics whiteboard (mainline PBPVisualSim parity).
        tac_scroll = QScrollArea()
        tac_scroll.setWidgetResizable(True)
        tac_scroll.setFrameShape(QFrame.NoFrame)
        tac_inner = QWidget()
        self._tac_layout = QVBoxLayout(tac_inner)
        self._tac_layout.setAlignment(Qt.AlignTop)
        self._tac_layout.setSpacing(4)
        tac_scroll.setWidget(tac_inner)
        self._tabs.addTab(tac_scroll, "♟ Tactics")
        self._tac_tab_index = self._tabs.count() - 1

        self._tabs.currentChanged.connect(self._on_tab_changed)

    # -- lifecycle ----------------------------------------------------

    def refresh(self):
        """Re-attach to a running sim (or show the idle state)."""
        try:
            with _watch_lock:
                running = (_watch["thread"] is not None
                           and _watch["thread"].is_alive())
                done = _watch["done"]
                err = _watch["error"]
            if running or (done and self._watching):
                self._attach()
            elif err and not self._watching:
                self._status.setText(err)
            self._render_chart()
        except Exception as e:
            print(f"[watch] refresh failed: {e}")

    def _attach(self):
        if not self._watching:
            self._watching = True
            self._finished = False
            self._paused = False
            self._fast_forward = False
            self._skate = None
            self._text_count = 0
            self._text_feed.clear()
            # D-11: reset live meters for the new game.
            self._winprob = 0.5
            self._shots = {"home": 0, "away": 0}
            self._mom = {"home": deque(maxlen=10), "away": deque(maxlen=10)}
            self._tension_live = []
            self._tac_pending = {}
            self._tac_response_text = ""
            self._momentum_open = False
            self._tension_open = False
            self._momentum_panel.hide()
            self._tension_panel.hide()
            self._btn_start.setEnabled(False)
            self._btn_pause.setEnabled(True)
            self._btn_simend.setEnabled(True)
            self._btn_pause.setText("⏸ Pause")
            self._btn_simend.setText("⏩ Sim to End")
            self._status.setText("Live sim running in the background — "
                                 "Space pauses, C toggles the camera.")
            # D-11: pre-game tension drivers (mainline parity).
            try:
                with _watch_lock:
                    home, away = _watch["home"], _watch["away"]
                    self._home_name = _watch["home_name"]
                    self._away_name = _watch["away_name"]
                gm = _resolve_gm(self.game)
                self._tension_base = _tension_breakdown(home, away, gm)
            except Exception:
                self._tension_base = {"tension": 0.0, "drivers": []}
            self._refresh_strips(force=True)
        if not self._pump_timer.isActive():
            self._pump_timer.start()

    def _start(self):
        st = _ensure_live_sim(self.game)
        if st is None:
            with _watch_lock:
                err = _watch["error"] or "Could not start a live sim."
            self._status.setText(err)
            return
        self._attach()
        with _watch_lock:
            self._status.setText(
                f"Watching {_watch['away_name']} @ {_watch['home_name']} — "
                "live.")

    def _go_replay(self):
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            fn("replay")

    # -- controls -----------------------------------------------------

    def _toggle_pause(self):
        if not self._watching or self._finished:
            return
        self._paused = not self._paused
        self._btn_pause.setText("▶ Resume" if self._paused else "⏸ Pause")
        self._ticker.setText("Paused — press Space to resume."
                             if self._paused else "")

    def _toggle_camera(self):
        self._follow_puck = not self._follow_puck
        # Clear player-follow when switching to puck/full-rink modes.
        self._follow_player_pid = None
        self._btn_camera.setText("🎥 Camera: Follow Puck"
                                 if self._follow_puck
                                 else "🎥 Camera: Full Rink")
        self._apply_camera()

    def _toggle_stats_overlay(self, checked):
        """Show/hide the live stats overlay (web's 📊 toggle parity)."""
        if checked:
            self._update_stats_overlay()
            self._stats_overlay.show()
            self._stats_overlay.raise_()
        else:
            self._stats_overlay.hide()

    def _rink_click(self, event):
        """Click a player dot to follow them; click empty ice to release."""
        try:
            pos = self._view.mapToScene(event.pos())
            best_pid, best_d = None, 6.0  # feet
            for pid, item in self._dots.items():
                d = ((item.pos().x() - pos.x()) ** 2 +
                     (item.pos().y() - pos.y()) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_pid = d, pid
            if best_pid:
                self._follow_player_pid = best_pid
                self._follow_puck = False
                with _watch_lock:
                    meta = _watch["id_meta"]
                name = meta.get(best_pid, {}).get("name", "Player")
                self._btn_camera.setText(f"🎥 Following: {name}")
                self._apply_camera()
                # D-11: player card popup (mainline InGamePopup port).
                self._show_player_card(best_pid)
            else:
                # Empty ice: release follow, back to full rink.
                if self._follow_player_pid:
                    self._follow_player_pid = None
                    self._btn_camera.setText("🎥 Camera: Full Rink")
                    self._apply_camera()
        except Exception as e:
            print(f"[watch] rink click failed: {e}")
        # Don't call super() — we replaced the handler entirely, and the
        # default does nothing useful for us (no selection/drag needed).

    def _update_stats_overlay(self):
        """Refresh the overlay text from live sim state."""
        try:
            with _watch_lock:
                events = list(_watch["events"])
                a = _watch["away_abbr"] or "AWY"
                h = _watch["home_abbr"] or "HOM"
            n_goals = n_shots = n_hits = n_pens = n_fights = 0
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                t = ev.get("type")
                if t == "goal":
                    n_goals += 1
                elif t in ("shot", "missed_shot", "blocked_shot"):
                    n_shots += 1
                elif t == "hit":
                    n_hits += 1
                elif t == "penalty":
                    n_pens += 1
                elif t == "fight":
                    n_fights += 1
            s = self._score
            self._stats_overlay.setText(
                f"<b>{a} {s['away']} — {s['home']} {h}</b><br>"
                f"{_period_label(self._period)} {_fmt_clock(self._clock)}<br>"
                f"Shots: {n_shots}<br>"
                f"Hits: {n_hits}<br>"
                f"Penalties: {n_pens}<br>"
                f"Fights: {n_fights}")
        except Exception:
            pass

    # -- D-11 live meters (mainline pbp_visual_sim parity) -------------

    def _push_momentum(self, side, weight):
        """Recent-events momentum deque (mainline _push_momentum)."""
        if side in self._mom:
            self._mom[side].append(weight)

    def _tension_add(self, label, points):
        """Log an in-game moment as a live intensity contributor."""
        try:
            self._tension_live.append({"label": label,
                                       "points": round(float(points), 1)})
            if len(self._tension_live) > 12:
                self._tension_live.pop(0)
        except Exception:
            pass

    def _tension_value(self):
        """Current 0-100 intensity: pre-game drivers + live moments."""
        try:
            v = float((self._tension_base or {}).get("tension", 0.0))
            v += sum(float(d.get("points", 0)) for d in self._tension_live)
            return max(0.0, min(100.0, round(v, 1)))
        except Exception:
            return 0.0

    def _update_winprob(self):
        try:
            self._winprob = _calc_winprob(
                self._score["home"], self._score["away"],
                self._period, self._clock,
                self._shots["home"], self._shots["away"])
        except Exception:
            pass

    def _refresh_strips(self, force=False):
        """Repaint win-prob / momentum / tension / matchup strips."""
        try:
            now = time.monotonic()
            if not force and now - self._last_strip_refresh < 1.0:
                return
            self._last_strip_refresh = now
            with _watch_lock:
                home_name = _watch["home_name"]
                away_name = _watch["away_name"]
                habbr = _watch["home_abbr"] or "HOM"
                aabbr = _watch["away_abbr"] or "AWY"
                sim = _watch["sim"]
            # Win probability (home perspective).
            self._update_winprob()
            p = self._winprob
            self._winprob_bar.setValue(int(round(p * 100)))
            self._winprob_label.setText(f"{habbr} {int(round(p * 100))}%")
            # Momentum.
            r = _momentum_reading(sim, self._mom, home_name, away_name)
            frac = max(-1.0, min(1.0, float(r.get("score", 0.0)) / 100.0))
            self._mom_bar.setValue(int(round(50 + frac * 50)))
            lbl = r.get("label", "")
            drv = (r.get("drivers") or [""])[0]
            self._momentum_label.setText((lbl + (f" — {drv}" if drv else ""))
                                         or "Even")
            if self._momentum_open:
                self._render_momentum_panel()
            # Tension.
            v = self._tension_value()
            col = _tension_color(v)
            self._tension_label.setText(
                f'<span style="color:{col}">●</span> '
                f"{_tension_mood(v)} {v:.1f}")
            if self._tension_open:
                self._render_tension_panel()
            # Matchup / shadowing indicator (throttled ~5s).
            if force or now - self._matchup_tick > 5.0:
                self._matchup_tick = now
                self._refresh_matchup()
        except Exception as e:
            print(f"[watch] strips failed: {e}")

    def _render_momentum_panel(self):
        """Drivers + AI risk appetite (mainline _render_momentum_panel)."""
        try:
            with _watch_lock:
                home_name = _watch["home_name"]
                away_name = _watch["away_name"]
                habbr = _watch["home_abbr"] or "HOM"
                aabbr = _watch["away_abbr"] or "AWY"
                sim = _watch["sim"]
            r = _momentum_reading(sim, self._mom, home_name, away_name)
            lines = []
            for d in (r.get("drivers") or [])[:6]:
                lines.append(f"• {d}")
            if not (r.get("drivers") or []):
                lines.append("No momentum drivers yet — play some hockey.")
            try:
                lines.append(
                    f"AI risk appetite — {habbr} "
                    f"{r.get('risk_home', 1.0):.2f} / {aabbr} "
                    f"{r.get('risk_away', 1.0):.2f} "
                    f"(moves goalie-pull timing, never conversion)")
            except Exception:
                pass
            self._momentum_panel.setText("<br>".join(lines))
        except Exception:
            pass

    def _toggle_momentum_panel(self):
        self._momentum_open = not self._momentum_open
        if self._momentum_open:
            self._render_momentum_panel()
            self._momentum_panel.show()
        else:
            self._momentum_panel.hide()

    def _render_tension_panel(self):
        """Intensity drivers, hottest first (mainline parity)."""
        try:
            drivers = (list((self._tension_base or {}).get("drivers", []))
                       + list(self._tension_live))
            drivers.sort(key=lambda d: -abs(float(d.get("points", 0) or 0)))
            if not drivers:
                self._tension_panel.setText("No intensity data for this game.")
                return
            rows = []
            for d in drivers[:14]:
                pts = float(d.get("points", 0) or 0)
                col = "#ff9f5c" if pts > 0 else "#7bc96f"
                sign = "+" if pts > 0 else ""
                rows.append(
                    f'<span style="color:{col}"><b>{sign}{pts:g}</b></span> '
                    f"{d.get('label', '')}")
            self._tension_panel.setText("<br>".join(rows))
        except Exception:
            pass

    def _toggle_tension_panel(self):
        self._tension_open = not self._tension_open
        if self._tension_open:
            self._render_tension_panel()
            self._tension_panel.show()
        else:
            self._tension_panel.hide()

    def _refresh_matchup(self):
        """Live shadow/matchup readout (mainline _update_matchup_readout)."""
        try:
            with _watch_lock:
                sim = _watch["sim"]
            cm = None
            try:
                from matchups import current_matchup
                if sim is not None:
                    cm = current_matchup(sim)
            except Exception:
                pass
            if cm:
                txt = (f"L{cm['home_line']} vs L{cm['away_line']} · "
                       f"{cm['edge']}")
            else:
                txt = "Matchup: –"
            self._matchup_label.setText(txt)
            edge = (cm or {}).get("edge", "")
            if edge in ("strong edge", "edge"):
                self._matchup_label.setStyleSheet("color: #7bc96f;")
            elif edge in ("outmatched", "strongly outmatched"):
                self._matchup_label.setStyleSheet("color: #ff9f5c;")
            else:
                self._matchup_label.setStyleSheet("")
        except Exception:
            pass

    # -- D-11 in-game tactics whiteboard (mainline pbp_visual_sim parity) --

    def _my_tac_team(self):
        """The user's club in this game (falls back to home)."""
        try:
            with _watch_lock:
                home, away = _watch["home"], _watch["away"]
            gm = _resolve_gm(self.game)
            user_team = safe_call(lambda: getattr(gm, "user_team", None),
                                  None, context="watch/tactics:user_team")
            un = _team_name(user_team)
            if un and un not in ("?", ""):
                if un == _team_name(home):
                    return home
                if un == _team_name(away):
                    return away
        except Exception:
            pass
        with _watch_lock:
            return _watch["home"]

    def _opp_tac_team(self):
        my = self._my_tac_team()
        with _watch_lock:
            home, away = _watch["home"], _watch["away"]
        return away if my is home else home

    def _tac_ctx(self):
        """In-game context for the coach's response: losing big = dry spell."""
        ctx = {"win_pct": 0.5, "losing_streak": 0}
        try:
            my = self._my_tac_team()
            with _watch_lock:
                home = _watch["home"]
            hs, aws = self._score["home"], self._score["away"]
            diff = (hs - aws) if my is home else (aws - hs)
            if diff <= -2:
                ctx["losing_streak"] = 3
        except Exception:
            pass
        return ctx

    def _clear_tac(self):
        while self._tac_layout.count():
            item = self._tac_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh_tactics_tab(self):
        """Rebuild the whiteboard (mainline _refresh_tactics_tab parity)."""
        self._clear_tac()
        try:
            import tactics as _tx
        except Exception:
            lbl = QLabel("Tactics unavailable.")
            lbl.setStyleSheet("color: #8b95ab;")
            self._tac_layout.addWidget(lbl)
            return
        my, opp = self._my_tac_team(), self._opp_tac_team()
        if my is None:
            lbl = QLabel("No live game — start one from the Visual tab.")
            lbl.setStyleSheet("color: #8b95ab;")
            self._tac_layout.addWidget(lbl)
            return
        try:
            _tx.ensure_team_tactics(my)
            if opp is not None:
                _tx.ensure_team_tactics(opp)
        except Exception:
            pass
        my_abbr = _abbr(_team_name(my))
        control = safe_call(lambda: _tx.get_tactics_control(my), "coach",
                            context="watch/tactics:control")

        hdr = QHBoxLayout()
        title = QLabel("TACTICS")
        title.setStyleSheet("font-size: 14px; font-weight: bold; "
                            "color: #7bc96f;")
        hdr.addWidget(title)
        hdr.addStretch()
        badge = QLabel("YOU CALL IT" if control == "gm"
                       else "COACH IN CONTROL")
        if control == "gm":
            badge.setStyleSheet("font-weight: bold; color: #FFD166;")
        else:
            badge.setStyleSheet("font-weight: bold; color: #AEB6C8;")
        hdr.addWidget(badge)
        self._tac_layout.addLayout(hdr)

        wb = QLabel(f"{my_abbr} — YOUR WHITEBOARD")
        wb.setStyleSheet("font-weight: bold;")
        self._tac_layout.addWidget(wb)

        cur = safe_call(lambda: _tx.team_tactics(my), {},
                        context="watch/tactics:current") or {}
        for cat, short, attr in _TAC_CATS:
            catalog = getattr(_tx, attr, {}) or {}
            row = QHBoxLayout()
            lab = QLabel(short)
            lab.setStyleSheet("color: #AEB6C8; font-weight: bold;")
            lab.setFixedWidth(70)
            row.addWidget(lab)
            names = [v.get("name", k) for k, v in catalog.items()]
            key_of = {v.get("name", k): k for k, v in catalog.items()}
            combo = QComboBox()
            combo.addItems(names)
            shown_key = self._tac_pending.get(cat, cur.get(cat))
            shown_name = catalog.get(shown_key, {}).get("name")
            if shown_name in names:
                combo.blockSignals(True)
                combo.setCurrentText(shown_name)
                combo.blockSignals(False)
            combo.currentTextChanged.connect(
                lambda _t, c=cat, ko=key_of, cb=combo:
                self._on_tac_pick(c, ko, cb))
            row.addWidget(combo, 1)
            self._tac_layout.addLayout(row)

        fam = float(safe_call(lambda: getattr(my, "tactics_familiarity", 85),
                              85, context="watch/tactics:familiarity") or 85)
        fl = QLabel(f"Familiarity {fam:.0f}% — changes take effect live "
                    f"(new reads are messy mid-game).")
        fl.setStyleSheet("color: #AEB6C8; font-size: 12px;")
        fl.setWordWrap(True)
        self._tac_layout.addWidget(fl)
        try:
            ident = " / ".join(_tx.describe_team_tactics(my))
        except Exception:
            ident = ""
        if ident:
            il = QLabel(ident)
            il.setWordWrap(True)
            il.setStyleSheet("font-size: 12px;")
            self._tac_layout.addWidget(il)
        if self._tac_response_text:
            rl = QLabel(self._tac_response_text)
            rl.setWordWrap(True)
            rl.setStyleSheet("color: #FFD166; font-size: 12px; "
                             "font-style: italic;")
            self._tac_layout.addWidget(rl)

        brow = QHBoxLayout()
        if control == "coach" and self._tac_pending:
            for label, fn in (("Suggest", self._on_tac_suggest),
                              ("Enforce", self._on_tac_enforce),
                              ("Take over", self._on_tac_takeover)):
                b = QPushButton(label)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(fn)
                brow.addWidget(b)
        elif control == "gm":
            b = QPushButton("Hand back")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip("Give the whiteboard back to your head coach")
            b.clicked.connect(self._on_tac_handback)
            brow.addWidget(b)
        brow.addStretch()
        self._tac_layout.addLayout(brow)

        # Opponent (AI) systems, read-only.
        if opp is not None:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            self._tac_layout.addWidget(sep)
            oh = QLabel(f"{_abbr(_team_name(opp))} — OPPONENT (AI)")
            oh.setStyleSheet("font-weight: bold; color: #7bc96f;")
            self._tac_layout.addWidget(oh)
            ocur = safe_call(lambda: _tx.team_tactics(opp), {},
                             context="watch/tactics:opp_current") or {}
            for cat, short, attr in _TAC_CATS:
                catalog = getattr(_tx, attr, {}) or {}
                val = catalog.get(ocur.get(cat), {}).get("name", "--")
                row = QHBoxLayout()
                lab = QLabel(short)
                lab.setStyleSheet("color: #AEB6C8; font-weight: bold;")
                lab.setFixedWidth(70)
                row.addWidget(lab)
                row.addWidget(QLabel(val), 1)
                self._tac_layout.addLayout(row)
            ofam = float(safe_call(
                lambda: getattr(opp, "tactics_familiarity", 85), 85,
                context="watch/tactics:opp_familiarity") or 85)
            cname = ""
            try:
                for stf in getattr(opp, "staff", []) or []:
                    role = getattr(getattr(stf, "role", None), "value", "")
                    if "Head Coach" in str(role):
                        cname = getattr(stf, "full_name", "")
                        break
            except Exception:
                pass
            ol = QLabel(f"Familiarity {ofam:.0f}%"
                        + (f" — coached by {cname}" if cname else ""))
            ol.setStyleSheet("color: #AEB6C8; font-size: 12px;")
            ol.setWordWrap(True)
            self._tac_layout.addWidget(ol)
        self._tac_layout.addStretch()

    def _on_tac_pick(self, cat, key_of, combo):
        try:
            import tactics as _tx
            my = self._my_tac_team()
            if my is None:
                return
            key = key_of.get(combo.currentText())
            if not key:
                return
            cur = safe_call(lambda: _tx.team_tactics(my).get(cat), None,
                            context="watch/tactics:pick_current")
            if key == cur:
                self._tac_pending.pop(cat, None)
            elif safe_call(lambda: _tx.get_tactics_control(my), "coach",
                           context="watch/tactics:pick_control") == "gm":
                # GM owns the whiteboard: applies live, mid-game.
                _tx.set_team_system(my, cat, key, mid_game=True)
                self._tac_pending.pop(cat, None)
                self._tac_response_text = ""
            else:
                self._tac_pending[cat] = key
            self._refresh_tactics_tab()
        except Exception as e:
            print(f"[watch] tac pick failed: {e}")

    def _on_tac_suggest(self):
        try:
            import reputation_system as _rs
            my = self._my_tac_team()
            if not self._tac_pending or my is None:
                return
            res = _rs.suggest_tactics_to_coach(my, dict(self._tac_pending),
                                               self._tac_ctx(), mid_game=True)
            if (res or {}).get("applied"):
                self._tac_pending.clear()
            self._tac_response_text = (res or {}).get("text", "")
            self._refresh_tactics_tab()
        except Exception as e:
            print(f"[watch] tac suggest failed: {e}")

    def _on_tac_enforce(self):
        try:
            import reputation_system as _rs
            my = self._my_tac_team()
            if not self._tac_pending or my is None:
                return
            ans = QMessageBox.question(
                self, "Enforce Tactics",
                "Overrule your head coach and enforce these systems right "
                "now? He won't forget it.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
            res = _rs.enforce_tactics(my, dict(self._tac_pending),
                                      self._tac_ctx(), mid_game=True)
            if (res or {}).get("applied"):
                self._tac_pending.clear()
            self._tac_response_text = (res or {}).get("text", "")
            self._refresh_tactics_tab()
        except Exception as e:
            print(f"[watch] tac enforce failed: {e}")

    def _on_tac_takeover(self):
        try:
            import reputation_system as _rs
            import tactics as _tx
            my = self._my_tac_team()
            if my is None:
                return
            ans = QMessageBox.question(
                self, "Take Over Tactics",
                "Take the whiteboard from your head coach for the rest of "
                "this game?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
            res = _rs.take_over_tactics(my, self._tac_ctx())
            if (res or {}).get("changed"):
                for cat, key in list(self._tac_pending.items()):
                    _tx.set_team_system(my, cat, key, mid_game=True)
                self._tac_pending.clear()
            self._tac_response_text = (res or {}).get("text", "")
            self._refresh_tactics_tab()
        except Exception as e:
            print(f"[watch] tac takeover failed: {e}")

    def _on_tac_handback(self):
        try:
            import reputation_system as _rs
            my = self._my_tac_team()
            if my is None:
                return
            res = _rs.hand_back_tactics(my)
            self._tac_response_text = (res or {}).get("text", "")
            self._refresh_tactics_tab()
        except Exception as e:
            print(f"[watch] tac handback failed: {e}")

    def _apply_camera(self):
        try:
            if self._follow_player_pid and self._follow_player_pid in self._dots:                # Follow a specific player (click-to-follow).
                item = self._dots[self._follow_player_pid]
                px, py = item.pos().x(), item.pos().y()
                self._view.fitInView(QRectF(px - 45, py - 30, 90, 60),
                                     Qt.KeepAspectRatio)
            elif self._follow_puck and self._skate:
                px, py = self._skate.get("puck", (100.0, 42.5))
                self._view.fitInView(QRectF(px - 45, py - 30, 90, 60),
                                     Qt.KeepAspectRatio)
            else:
                self._view.fitInView(QRectF(-14, -14, RINK_L + 28,
                                           RINK_W + 28),
                                     Qt.KeepAspectRatio)
        except Exception:
            pass

    def _on_tab_changed(self, idx):
        try:
            name = self._tabs.tabText(idx)
            if "Chart" in name:
                self._render_chart()
                self._chart_view.fitInView(
                    QRectF(-14, -14, RINK_L + 28, RINK_W + 28),
                    Qt.KeepAspectRatio)
            elif "Box" in name:
                self._render_box(force=True)
            elif "Tactics" in name:
                self._refresh_tactics_tab()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_camera()

    # -- pump: drain the sim queue on the GUI thread ------------------

    def _sim_to_end(self):
        """Sim-to-end: consume the rest of the game instantly.

        Mainline PBPVisualSim._sim_to_end parity: wait for the sim, then
        consume everything with no pacing/beats until the game ends.
        """
        if not self._watching or self._finished:
            return
        self._paused = False
        self._fast_forward = True
        self._suppress_beats = True
        self._btn_simend.setEnabled(False)
        self._btn_simend.setText("⏩ Fast-forwarding…")
        self._status.setText("Fast-forwarding to the final whistle…")
        if not self._pump_timer.isActive():
            self._pump_timer.start()

    def _pump(self):
        if self._paused:
            return
        now = time.monotonic()
        if now < self._hold_until and not self._fast_forward:
            return  # big-moment beat: hold the frame
        with _watch_lock:
            q = _watch["queue"]
            sim_done = _watch["done"]
        if q is None:
            self._pump_timer.stop()
            return
        # Sim-to-end: drain in big chunks (GUI stays alive); no beats.
        burst = 100000 if self._fast_forward else max(1, int(40 * self._speed))
        latest = None
        try:
            for _ in range(burst):
                try:
                    ev = q.get_nowait()
                except queue.Empty:
                    break
                et = ev.get("type")
                if et == "skate":
                    latest = ev
                    continue
                self._handle_event(ev)
        except Exception as e:
            print(f"[watch] pump failed: {e}")
        if latest is not None:
            self._skate = latest
            self._score = {"home": latest.get("home_score", 0),
                           "away": latest.get("away_score", 0)}
            self._period = latest.get("period", 1)
            self._clock = latest.get("clock", 0)
            self._render_skate(latest)
            self._apply_camera()
        self._render_scorebug()
        # D-11: live meters (throttled inside).
        self._refresh_strips()
        # Refresh the stats overlay if visible.
        if self._btn_stats.isChecked():
            self._update_stats_overlay()
        # Refresh the box tab periodically while it's visible.
        if (self._tabs.currentIndex() == self._box_tab_index and
                now - self._last_box_refresh > 2.0):
            self._last_box_refresh = now
            self._render_box()
        if sim_done and q.empty():
            self._finish()

    def _handle_event(self, ev):
        et = ev.get("type")
        if et == "game_end":
            self._score = {"home": ev.get("home_score", 0),
                           "away": ev.get("away_score", 0)}
            self._period = ev.get("period", 3)
            self._clock = 0
            return
        # D-11: live meters (mainline pbp_visual_sim parity).
        try:
            hn, an = self._home_name, self._away_name
            if et in ("shot", "missed_shot", "blocked_shot"):
                side = _side_of(ev.get("attacking_team"), hn, an)
                if side:
                    self._shots[side] += 1
                    self._push_momentum(side, 1)
            elif et == "goal":
                side = _side_of(ev.get("scoring_team"), hn, an)
                if side:
                    self._shots[side] += 1
                    self._push_momentum(side, 3)
            elif et == "fight":
                side = _side_of(ev.get("winner_team") or ev.get("team_a"),
                                hn, an)
                if side:
                    self._push_momentum(side, 2)
                a = _player_name(ev.get("player_a") or ev.get("hitting_player"))
                b = _player_name(ev.get("player_b") or ev.get("target_player"))
                self._tension_add(f"Fight: {a} vs {b}", 6.0)
            elif et == "hit" and ev.get("result") == "turnover_caused":
                self._tension_add(
                    f"Big hit: {_player_name(ev.get('hitting_player'))} on "
                    f"{_player_name(ev.get('target_player'))}", 3.0)
            elif et == "penalty":
                try:
                    mins = int(ev.get("minutes", 0) or 0)
                except Exception:
                    mins = 0
                if mins >= 5:
                    self._tension_add(
                        f"Major penalty: {_player_name(ev.get('player'))}",
                        4.0)
        except Exception:
            pass
        text, big = _event_text(ev)
        if et in _HIGHLIGHT_TYPES or big:
            self._ticker.setText(text.replace("<b>", "")
                                     .replace("</b>", "")
                                     .replace("🚨 ", "").replace("🥊 ", "")
                                     .replace("⭐ ", ""))
            # Big-moment beat (web _PACE parity) -- skipped in sim-to-end.
            if not self._suppress_beats:
                hold = _PACE.get(et, 0.35) / max(0.25, self._speed)
                self._hold_until = time.monotonic() + hold
        # Text feed (skip raw skate noise).
        bar = self._text_feed.verticalScrollBar()
        near_bottom = (bar.value() >= bar.maximum() - 60)
        self._text_feed.append(text)
        if near_bottom:
            bar.setValue(bar.maximum())
        self._text_count += 1

    def _finish(self):
        self._pump_timer.stop()
        self._finished = True
        self._paused = False
        self._btn_pause.setEnabled(False)
        self._btn_start.setEnabled(True)
        self._btn_simend.setEnabled(False)
        with _watch_lock:
            a, h = _watch["away_abbr"], _watch["home_abbr"]
            alert = _watch["finish_alert"]
            _watch["finish_alert"] = None
        self._ticker.setText(f"Final: {a} {self._score['away']} — "
                             f"{self._score['home']} {h}")
        if alert:
            # OBS-3: the result was NOT recorded and the game was left
            # un-watched on purpose -- say so loudly, never silently.
            self._status.setStyleSheet(
                "color: #ff6b6b; font-size: 13px; font-weight: bold;")
            self._status.setText(alert)
            self._ticker.setText("⚠️ " + alert)
            try:
                QMessageBox.warning(
                    self, "Game not recorded",
                    alert + "\n\nAdvance the day and the day sim will "
                    "process this game normally.")
            except Exception:
                pass
        else:
            self._status.setStyleSheet("color: #8b95ab; font-size: 12px;")
            self._status.setText("Game complete — result recorded. "
                                 "Open the Box Score tab for the full recap.")
        self._show_three_stars()
        self._render_box(force=True)

    # -- rendering ----------------------------------------------------

    def _render_scorebug(self):
        with _watch_lock:
            a, h = _watch["away_abbr"] or "AWY", _watch["home_abbr"] or "HOM"
        s = self._score
        self._scorebug.setText(
            f"{a}  {s['away']}  @  {s['home']}  {h}   ·   "
            f"{_period_label(self._period)}  {_fmt_clock(self._clock)}")

    def _render_skate(self, snap):
        try:
            with _watch_lock:
                meta = _watch["id_meta"]
            positions = snap.get("positions") or {}
            home_ids = {str(i) for i in (snap.get("on_ice_home") or [])}
            away_ids = {str(i) for i in (snap.get("on_ice_away") or [])}
            seen = set()
            poss = snap.get("possession_player")
            poss_s = str(poss) if poss is not None else None
            for pid, xy in positions.items():
                try:
                    x, y = float(xy[0]), float(xy[1])
                except Exception:
                    continue
                pids = str(pid)
                seen.add(pids)
                m = meta.get(pids, {})
                team = m.get("team")
                if team is None:
                    team = 0 if pids in home_ids else 1
                goalie = bool(m.get("goalie"))
                if pids in self._dots:
                    item = self._dots[pids]
                    item.setPos(x, y)
                else:
                    if goalie:
                        item = QGraphicsRectItem(-3, -3, 6, 6)
                    else:
                        item = QGraphicsEllipseItem(-2.2, -2.2, 4.4, 4.4)
                    item.setPos(x, y)
                    item.setZValue(2)
                    name = m.get("name", "")
                    if name:
                        item.setToolTip(name)
                    self._scene.addItem(item)
                    self._dots[pids] = item
                fill = QColor("#3b82f6") if team == 0 else QColor("#ef4444")
                item.setBrush(QBrush(fill))
                if pids == poss_s:
                    item.setPen(QPen(QColor("#ffd700"), 1.2))
                elif goalie:
                    item.setPen(QPen(QColor("#ffffff"), 1.2))
                else:
                    item.setPen(QPen(QColor("#0b0f1a"), 0.8))
            # Remove skaters who left the ice.
            for pids in [k for k in self._dots if k not in seen]:
                try:
                    self._scene.removeItem(self._dots.pop(pids))
                except Exception:
                    pass
            # Puck
            px, py = snap.get("puck") or (100.0, 42.5)
            if self._puck_item is None:
                self._puck_item = QGraphicsEllipseItem(-0.9, -0.9, 1.8, 1.8)
                self._puck_item.setBrush(QBrush(QColor("#111111")))
                self._puck_item.setPen(QPen(Qt.NoPen))
                self._puck_item.setZValue(5)
                self._scene.addItem(self._puck_item)
            self._puck_item.setPos(float(px), float(py))
        except Exception as e:
            print(f"[watch] render_skate failed: {e}")

    # -- shot chart ---------------------------------------------------

    def _render_chart(self):
        try:
            with _watch_lock:
                events = list(_watch["events"])
                home_name = _watch["home_name"]
                habbr = _watch["home_abbr"] or "HOME"
                aabbr = _watch["away_abbr"] or "AWAY"
            # Clear old markers.
            for item, _ in self._chart_markers:
                try:
                    self._chart_scene.removeItem(item)
                except Exception:
                    pass
            self._chart_markers = []
            last_by_shooter = {}
            n_shots = n_goals = 0
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                et = ev.get("type")
                if et in ("shot", "missed_shot", "blocked_shot"):
                    pos = ev.get("shooter_pos")
                    if not pos or len(pos) < 2:
                        continue
                    att = str(ev.get("attacking_team") or "")
                    ti = 0 if att and att == home_name else 1
                    self._chart_markers.append(
                        (None, {"x": float(pos[0]), "y": float(pos[1]),
                                "team": ti, "ev": ev, "goal": False}))
                    sh = ev.get("shooter")
                    key = getattr(sh, "id", None) or _player_name(sh)
                    last_by_shooter[key] = len(self._chart_markers) - 1
                    n_shots += 1
                elif et == "goal":
                    n_goals += 1
                    sh = ev.get("shooter")
                    key = getattr(sh, "id", None) or _player_name(sh)
                    idx = last_by_shooter.get(key)
                    if idx is not None:
                        item, mk = self._chart_markers[idx]
                        mk["goal"] = True
                        mk["goal_ev"] = ev
            # Draw markers.
            drawn = []
            for _, mk in self._chart_markers:
                col = QColor("#3b82f6") if mk["team"] == 0 else QColor(
                    "#ef4444")
                if mk["goal"]:
                    it = QGraphicsEllipseItem(-3.4, -3.4, 6.8, 6.8)
                    it.setBrush(QBrush(col))
                    it.setPen(QPen(QColor("#ffd700"), 2.0))
                    it.setOpacity(0.9)
                else:
                    it = QGraphicsEllipseItem(-2.0, -2.0, 4.0, 4.0)
                    it.setBrush(QBrush(col))
                    it.setPen(QPen(Qt.NoPen))
                    it.setOpacity(0.8)
                it.setPos(mk["x"], mk["y"])
                it.setZValue(3)
                it.setData(0, len(drawn))
                self._chart_scene.addItem(it)
                drawn.append((it, mk))
            self._chart_markers = drawn
            self._chart_legend.setText(
                f'<span style="color:#3b82f6">●</span> {habbr} shots<br>'
                f'<span style="color:#ef4444">●</span> {aabbr} shots<br>'
                f'<span style="color:#ffd700">◉</span> Goal<br>'
                f"{n_shots} shot attempts · {n_goals} goals")
        except Exception as e:
            print(f"[watch] render_chart failed: {e}")

    def _chart_click(self, event):
        try:
            pos = event.scenePos()
            best, bd = None, 8.0
            for item, mk in self._chart_markers:
                d = ((item.pos().x() - pos.x()) ** 2 +
                     (item.pos().y() - pos.y()) ** 2) ** 0.5
                if d < bd:
                    bd, best = d, mk
            if best is None:
                self._chart_detail.setText(
                    "Click any shot marker for the play details.")
                return
            ev = best.get("goal_ev") or best["ev"]
            rows = [
                ("GOAL" if best["goal"] else "Shot attempt", ""),
                ("Shooter", _player_name(ev.get("shooter"))),
                ("Team", str(ev.get("attacking_team")
                             or ev.get("scoring_team") or "")),
                ("When", f"{_period_label(ev.get('period', 1))} "
                         f"{_fmt_clock(ev.get('clock', 0))}"),
            ]
            if ev.get("shot_type"):
                rows.append(("Shot",
                             str(ev["shot_type"]).replace("_", " ")))
            if ev.get("location"):
                rows.append(("From",
                             str(ev["location"]).replace("_", " ")))
            if ev.get("distance") is not None:
                try:
                    rows.append(("Distance",
                                 f"{round(float(ev['distance']))} ft"))
                except Exception:
                    pass
            self._chart_detail.setText("<br>".join(
                f"<b>{k}:</b> {v}" if v else f"<b>{k}</b>"
                for k, v in rows))
        except Exception as e:
            print(f"[watch] chart click failed: {e}")

    # -- live box score ------------------------------------------------

    def _clear_box(self):
        while self._box_layout.count():
            item = self._box_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_box(self, force=False):
        try:
            with _watch_lock:
                sim = _watch["sim"]
                meta = dict(_watch["id_meta"])
                events = list(_watch["events"])
                home_name = _watch["home_name"]
            self._clear_box()
            if sim is None:
                self._box_layout.addWidget(self._empty(
                    "No live game — start one from the Visual tab."))
                return
            gs = _normalize_gs(safe_call(lambda: getattr(sim, "game_stats",
                                                    None), {}) or {})
            if not gs:
                self._box_layout.addWidget(self._empty(
                    "Stats will appear once the sim gets going."))
                return
            # Scoring summary
            sh = QLabel("Scoring Summary")
            sh.setObjectName("section-header")
            self._box_layout.addWidget(sh)
            goals = [e for e in events
                     if isinstance(e, dict) and e.get("type") == "goal"]
            if goals:
                for ev in goals:
                    a = ev.get("assists") or []
                    al = (f" ({', '.join(_player_name(x) for x in a)})"
                          if a else " (unassisted)")
                    lbl = QLabel(
                        f"🚨 {_period_label(ev.get('period', 1))} "
                        f"{_fmt_clock(ev.get('clock', 0))} — "
                        f"<b>{_player_name(ev.get('shooter'))}</b>{al} · "
                        f"{ev.get('home_score', 0)}–{ev.get('away_score', 0)}")
                    lbl.setStyleSheet("font-size: 13px; padding: 2px 0;")
                    self._box_layout.addWidget(lbl)
            else:
                self._box_layout.addWidget(QLabel("No goals yet."))
            # Skaters
            skaters, goalies = [], []
            for pid, st in gs.items():
                try:
                    m = meta.get(pid, {})
                    nm = m.get("name") or "?"
                    if m.get("goalie"):
                        sa = int(st.get("shots_against", 0) or 0)
                        sv = int(st.get("saves", 0) or 0)
                        ga = int(st.get("goals_against", 0) or 0)
                        if sa <= sv:
                            sa = sv + ga
                        goalies.append({"name": nm, "sa": sa, "saves": sv,
                                        "ga": ga,
                                        "svp": (round(sv / sa * 100, 1)
                                                if sa else None)})
                    else:
                        g = int(st.get("g", 0) or 0)
                        a_ = int(st.get("a", 0) or 0)
                        fw = int(st.get("faceoffs_won", 0) or 0)
                        fl = int(st.get("faceoffs_lost", 0) or 0)
                        skaters.append({
                            "name": nm,
                            "player": st.get("player"),
                            "pos": _pos_short(st.get("player")),
                            "g": g, "a": a_, "p": g + a_,
                            "sog": int(st.get("shots_on_goal", 0) or 0),
                            "hits": int(st.get("hits", 0) or 0),
                            "blk": int(st.get("blocked_shots", 0) or 0)
                            + int(st.get("blocked_shots_by", 0) or 0),
                            "fo": f"{fw}-{fl}",
                        })
                except Exception:
                    continue
            skaters.sort(key=lambda r: (r["p"], r["g"]), reverse=True)
            ph = QLabel("Skaters")
            ph.setObjectName("section-header")
            self._box_layout.addWidget(ph)
            tbl = QTableWidget(len(skaters), 9)
            tbl.setHorizontalHeaderLabels(
                ["Player", "Pos", "G", "A", "P", "SOG", "Hits", "Blk", "FO"])
            tbl.horizontalHeader().setSectionResizeMode(0,
                                                        QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for i, s in enumerate(skaters):
                for j, v in enumerate(
                        [s["name"], s["pos"], s["g"], s["a"], s["p"],
                         s["sog"], s["hits"], s["blk"], s["fo"]]):
                    item = QTableWidgetItem(str(v))
                    if j == 0 and s.get("player") is not None:
                        # Store the player object for click-through.
                        item.setData(Qt.UserRole, s["player"])
                    tbl.setItem(i, j, item)
            # Click a player name to open their profile (web parity).
            tbl.cellClicked.connect(
                lambda r, c, _t=tbl: self._box_player_click(_t, r, c))
            self._box_layout.addWidget(tbl)
            if goalies:
                gh = QLabel("Goaltenders")
                gh.setObjectName("section-header")
                self._box_layout.addWidget(gh)
                gl = QTableWidget(len(goalies), 5)
                gl.setHorizontalHeaderLabels(
                    ["Goaltender", "SA", "Saves", "SV%", "GA"])
                gl.horizontalHeader().setSectionResizeMode(
                    0, QHeaderView.Stretch)
                gl.verticalHeader().setVisible(False)
                gl.setEditTriggers(QTableWidget.NoEditTriggers)
                for i, gg in enumerate(goalies):
                    svp = "–" if gg["svp"] is None else f"{gg['svp']:.1f}%"
                    for j, v in enumerate(
                            [gg["name"], gg["sa"], gg["saves"], svp,
                             gg["ga"]]):
                        gl.setItem(i, j, QTableWidgetItem(str(v)))
                self._box_layout.addWidget(gl)
            # Full box score once the game is recorded.
            btn = QPushButton("📊 Open Full Box Score")
            btn.setObjectName("primary-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setEnabled(self._finished)
            btn.setToolTip("Available once the game ends and is recorded."
                           if not self._finished else "")
            btn.clicked.connect(self._open_full_boxscore)
            self._box_layout.addWidget(btn)
            self._box_layout.addStretch()
        except Exception as e:
            print(f"[watch] render_box failed: {e}")

    def _open_full_boxscore(self):
        try:
            with _watch_lock:
                d = _watch["date"]
                home, away = _watch["home"], _watch["away"]
            dlg = BoxscoreDialog(self.game)
            dlg.set_game(d, home, away)
            dlg.exec()
        except Exception as e:
            print(f"[watch] open boxscore failed: {e}")

    def _box_player_click(self, table, row, col):
        """Open the player profile when a box-score name is clicked."""
        try:
            if col != 0:
                return
            item = table.item(row, 0)
            if item is None:
                return
            player = item.data(Qt.UserRole)
            if player is None:
                return
            fn = getattr(self.main_window, "show_player", None)
            if callable(fn):
                fn(player)
        except Exception as e:
            print(f"[watch] box player click failed: {e}")

    # -- D-11 InGamePopup ports (mainline pbp_visual_sim parity) --------

    def _show_player_card(self, pid):
        """Player card popup for a clicked dot (InGamePopup port)."""
        try:
            with _watch_lock:
                meta = dict(_watch["id_meta"])
                sim = _watch["sim"]
                home_name, away_name = _watch["home_name"], _watch["away_name"]
            m = meta.get(str(pid), {})
            name = m.get("name", "Player")
            is_home = m.get("team") == 0
            team = home_name if is_home else away_name
            player = None
            try:
                for team_obj in (getattr(sim, "home_team", None),
                                 getattr(sim, "away_team", None)):
                    for p in (getattr(team_obj, "roster", None) or []):
                        if str(getattr(p, "id", "")) == str(pid):
                            player = p
                            break
                    if player is not None:
                        break
            except Exception:
                pass
            pos = _pos_short(player)
            if not pos:
                pos = "G" if m.get("goalie") else "?"
            # Talent tier (mainline directive: numeric overall is never
            # shown to the user).
            try:
                from attribute_composites import talent_tier_for_player
                tier = (talent_tier_for_player(player)
                        if player is not None else "?")
            except Exception:
                tier = "?"
            # Live game stats from the sim.
            rows = []
            try:
                gs = _normalize_gs(
                    safe_call(lambda: getattr(sim, "game_stats", None), {},
                              context="watch/card:game_stats") or {})
                st = gs.get(str(pid), {})
                if m.get("goalie"):
                    sv = int(st.get("saves", 0) or 0)
                    sa = int(st.get("shots_against", 0) or 0)
                    rows = [("Saves", str(sv)), ("Shots faced", str(sa)),
                            ("SV%", f"{(sv / sa * 100):.1f}%"
                             if sa else "–")]
                else:
                    g = int(st.get("g", 0) or 0)
                    a = int(st.get("a", 0) or 0)
                    rows = [("Goals", str(g)), ("Assists", str(a)),
                            ("Points", str(g + a)),
                            ("Shots", str(int(st.get("shots_on_goal", 0)
                                             or 0))),
                            ("Hits", str(int(st.get("hits", 0) or 0)))]
            except Exception:
                pass
            if self._card_dialog is not None:
                try:
                    self._card_dialog.close()
                except Exception:
                    pass
            dlg = QDialog(self)
            dlg.setWindowTitle("Player")
            dlg.setMinimumWidth(240)
            lay = QVBoxLayout(dlg)
            nm = QLabel(name)
            nm.setStyleSheet("font-size: 14px; font-weight: bold;")
            nm.setWordWrap(True)
            lay.addWidget(nm)
            sub = QLabel(f"{team} · {pos} · {tier}")
            sub.setStyleSheet("color: #7bc96f; font-weight: bold;")
            lay.addWidget(sub)
            for k, v in rows:
                r = QLabel(f"<b>{k}:</b> {v}")
                lay.addWidget(r)
            close = QPushButton("Close")
            close.setCursor(Qt.PointingHandCursor)
            close.clicked.connect(dlg.close)
            lay.addWidget(close)
            self._card_dialog = dlg
            dlg.show()  # non-modal: the game keeps playing
        except Exception as e:
            print(f"[watch] player card failed: {e}")

    def _show_three_stars(self):
        """Three-stars popup at game end (mainline _show_stars port)."""
        try:
            with _watch_lock:
                sim = _watch["sim"]
                meta = dict(_watch["id_meta"])
                home_name, away_name = _watch["home_name"], _watch["away_name"]
            if sim is None:
                return
            gs = _normalize_gs(
                safe_call(lambda: getattr(sim, "game_stats", None), {},
                          context="watch/stars:game_stats") or {})
            if not gs:
                return
            cands = []
            for pid, st in gs.items():
                try:
                    m = meta.get(str(pid), {})
                    name = m.get("name") or "?"
                    ti = 0 if m.get("team", 0) == 0 else 1
                    tname = home_name if ti == 0 else away_name
                    if m.get("goalie"):
                        sv = int(st.get("saves", 0) or 0)
                        sa = int(st.get("shots_against", 0) or 0)
                        svp = f"{(sv / sa * 100):.1f}%" if sa else "–"
                        cands.append((sv, name, tname,
                                      f"{sv} saves · {svp}"))
                    else:
                        g = int(st.get("g", 0) or 0)
                        a = int(st.get("a", 0) or 0)
                        cands.append((g * 2 + a, name, tname,
                                      f"{g}G {a}A · {g + a} pts"))
                except Exception:
                    continue
            cands.sort(key=lambda c: c[0], reverse=True)
            stars = [c for c in cands if c[0] > 0][:3] or cands[:3]
            if not stars:
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("Three Stars")
            dlg.setMinimumWidth(300)
            lay = QVBoxLayout(dlg)
            title = QLabel("THREE STARS")
            title.setStyleSheet("font-size: 14px; font-weight: bold; "
                                "color: #7bc96f;")
            title.setAlignment(Qt.AlignCenter)
            lay.addWidget(title)
            medals = ("1st", "2nd", "3rd")
            for i, (_score, name, tname, line) in enumerate(stars[:3]):
                card = QFrame()
                card.setFrameShape(QFrame.StyledPanel)
                cl = QVBoxLayout(card)
                ml = QLabel(f"{medals[i]} STAR")
                ml.setStyleSheet("color: #FFD166; font-weight: bold;")
                cl.addWidget(ml)
                nl = QLabel(name)
                nl.setStyleSheet("font-size: 13px; font-weight: bold;")
                cl.addWidget(nl)
                sl = QLabel(f"{tname} · {line}")
                sl.setStyleSheet("color: #aeb6c8;")
                cl.addWidget(sl)
                lay.addWidget(card)
            close = QPushButton("Close")
            close.setCursor(Qt.PointingHandCursor)
            close.clicked.connect(dlg.close)
            lay.addWidget(close)
            dlg.show()  # non-modal
        except Exception as e:
            print(f"[watch] three stars failed: {e}")

    @staticmethod
    def _empty(msg):
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px; padding: 24px;")
        return lbl
