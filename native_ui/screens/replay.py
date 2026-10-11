"""Replay screen: completed-game play-by-play replay + box score.

Ported from web_ui/screens/watch.py (replay endpoints) +
web_ui/templates/replay.html + web_ui/static/js/replay.js.

Pick a completed game, replay its stored event log in four modes
(Animated / Watch All / Highlights / Text), jump between big moments,
and drill into the full box score via the shared BoxscoreDialog.
set_game(game_idx) is the deep-link equivalent of /replay?idx=N
(index into the newest-first completed-games list).

ANIMATED PLAYBACK (mainline pbp_visual_sim.py parity, STEP 0):
  Mainline's replay is a timer-driven event-stream player: GameSim emits
  dict events (type/period/clock/t/game-seconds + payload) through
  pbp_listeners; a 33ms tick advances a playhead by
  TICK_DT * speed * GAME_RATE (GAME_RATE = 4 game-sec/real-sec) and
  consumes every event whose game-time <= playhead. Controls: Play/Pause,
  1x/2x/4x speed pills, auto-pace, Sim-to-End, Next Big Moment,
  instant goal replays from recent tick frames, ticker + big-moment beat.

  The completed-game log only stores GOAL_ADVANCED / SAVE_ADVANCED
  entries (no per-tick positions), so the rink animation synthesizes
  on-ice setups from event details (shot spot ported from mainline's
  shot_spot, goalie in the crease, game-clock puck flights). The Qt rink
  itself is reused from native_ui/screens/watch.py:draw_rink -- no
  second rendering stack.
"""
import random
import re
import time
from datetime import date, datetime

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QComboBox, QTextBrowser, QWidget,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsRectItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QPen, QPainter, QKeySequence, QShortcut,
)

from .base import BaseScreen
from ..dialogs.boxscore import BoxscoreDialog
from native_ui.safe import safe_call
from .watch import draw_rink, RINK_L, RINK_W


# ----------------------------------------------------------------------
# Helpers (ported from web_ui/screens/watch.py, Flask removed)
# ----------------------------------------------------------------------

# pbp_visual_sim BIG_MOMENTS parity (web_ui/static/js/replay.js).
_BIG = ("GOAL", "PENALTY", "FIGHT", "PENALTY_SHOT")

# Playback tuning (mainline pbp_visual_sim parity):
# 33ms tick, playhead advances _GAME_RATE game-seconds per real second
# at 1x. Text detail runs 25x (mainline: "fast enough to feel like a
# live wire, slow enough to read").
_GAME_RATE = 4.0
_TICK_MS = 33
_TEXT_RATE = 25.0
# Big-moment beat (real seconds the playhead holds on a big event;
# watch.py _PACE parity: goal 2.0, fight 2.0, penalty 1.2).
_PACE = {"GOAL": 2.0, "FIGHT": 2.0, "PENALTY_SHOT": 1.6, "PENALTY": 1.2}

# Shot spots ported from mainline pbp_visual_sim.SHOT_SPOTS: coordinates
# for a team attacking in +x (home); mirrored for the away side, with
# mainline's jitter so repeated shots don't stack perfectly.
_SHOT_SPOTS = {
    "crease": (182, 42.5),
    "low_slot": (172, 42.5),
    "high_slot": (160, 42.5),
    "left_circle": (166, 27),
    "right_circle": (166, 58),
    "point": (145, 42.5),
    "left_wing": (150, 18),
    "right_wing": (150, 67),
    "behind_net": (193, 42.5),
}

# Dot colors (watch.py parity).
_HOME_COLOR = QColor("#3b82f6")
_AWAY_COLOR = QColor("#ef4444")
_POSS_COLOR = QColor("#ffd700")


def _team_name(t):
    if isinstance(t, str):
        return t
    return safe_call(lambda: getattr(t, "team_name", str(t)), "?",
                     context="replay: team_name") or "?"


def _date_str(d):
    try:
        if isinstance(d, datetime):
            return d.strftime("%b %d, %Y")
        if isinstance(d, date):
            return d.strftime("%b %d, %Y")
        return str(d or "")
    except Exception:
        return ""


def _fmt_ts(sec):
    try:
        sec = max(0, int(round(float(sec or 0))))
    except Exception:
        sec = 0
    return f"{sec // 60}:{sec % 60:02d}"


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


def _strip_html(s):
    try:
        return re.sub(r"<[^>]+>", "", str(s or ""))
    except Exception:
        return str(s or "")


def _past_results(game):
    """Completed game_results, newest first. Never raises."""
    try:
        results = safe_call(
            lambda: list(getattr(game, "game_results", None) or []), [],
            context="replay: game_results") or []
    except Exception:
        return []
    return list(reversed(results))


def _roster_lookup(result):
    """str(pid) -> Player for a stored result (roster + game_stats)."""
    by_id = {}
    for key in ("home_team", "away_team"):
        try:
            team = result.get(key)
            for p in safe_call(
                    lambda: list(getattr(team, "roster", None) or []), [],
                    context="replay: team roster") or []:
                try:
                    pid = getattr(p, "id", None)
                    if pid is not None and str(pid) not in by_id:
                        by_id[str(pid)] = p
                except Exception:
                    continue
        except Exception:
            continue
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


def _side_lookup(result):
    """str(pid) -> 0 (home) / 1 (away), from each team's own roster."""
    side = {}
    for key, s in (("home_team", 0), ("away_team", 1)):
        try:
            team = result.get(key)
            for p in safe_call(
                    lambda: list(getattr(team, "roster", None) or []), [],
                    context="replay: team roster (sides)") or []:
                try:
                    pid = getattr(p, "id", None)
                    if pid is not None:
                        side.setdefault(str(pid), s)
                except Exception:
                    continue
        except Exception:
            continue
    return side


def _nm(by_id, v):
    """Resolve a details name field: Player object, id, or raw string."""
    if v is None:
        return "?"
    if not isinstance(v, (int, float, str)):
        return (getattr(v, "full_name", None) or getattr(v, "name", None)
                or str(v))
    p = by_id.get(str(v))
    if p is not None:
        return (getattr(p, "full_name", None) or getattr(p, "name", None)
                or str(v))
    return str(v)


def _is_highlight(e):
    """GAME_VIEWER._is_highlight parity: goals, high-danger saves, majors."""
    t = str(e.get("type", "") or "").upper()
    d = e.get("details") or {}
    if not isinstance(d, dict):
        d = {}
    if "GOAL" in t:
        return True
    if "SAVE" in t:
        return str(d.get("shot_quality", "")).lower() == "high"
    if "PENALTY" in t:
        try:
            return int(d.get("minutes", 0) or 0) >= 5
        except Exception:
            return False
    return False


def _is_big(e):
    t = str(e.get("type", "") or "").upper()
    return any(k in t for k in _BIG)


def _shot_spot(details, attacking_home):
    """Port of mainline pbp_visual_sim.shot_spot().

    Stored GOAL/SAVE_ADVANCED entries carry shot_quality (high/medium/
    low) but no ShotLocation, so quality picks the zone; the attacking
    side mirrors the coordinate and jitter is applied exactly like
    mainline so repeated shots don't stack.
    """
    try:
        q = str((details or {}).get("shot_quality") or "").lower()
    except Exception:
        q = ""
    if q == "high":
        key = "low_slot"
    elif q == "medium":
        key = random.choice(["high_slot", "left_circle", "right_circle"])
    else:
        key = random.choice(
            ["point", "left_wing", "right_wing", "high_slot"])
    x, y = _SHOT_SPOTS.get(key, (160, 42.5))
    if not attacking_home:
        x = RINK_L - x
    return (x + random.uniform(-2, 2), y + random.uniform(-3, 3))


def _event_game_time(e):
    """Stored event -> (period, game-seconds) using timestamp (elapsed
    seconds within the period, simulation._period_length = 1200)."""
    d = e.get("details") or {}
    if not isinstance(d, dict):
        d = {}
    try:
        period = int(d.get("period", e.get("period", 1)) or 1)
    except (TypeError, ValueError):
        period = 1
    period = max(1, min(period, 9))
    try:
        ts = max(0.0, float(e.get("timestamp", 0) or 0))
    except (TypeError, ValueError):
        ts = 0.0
    ts = min(ts, 1200.0)
    return period, (period - 1) * 1200.0 + ts


def _event_text(e, by_id):
    """One stored event_log entry -> HTML row (replay.js eventLine)."""
    t = str(e.get("type", "") or "").upper()
    d = e.get("details") or {}
    if not isinstance(d, dict):
        d = {}
    period = d.get("period", e.get("period", 1))
    ts = _fmt_ts(e.get("timestamp", 0))
    pre = (f'<span style="color:#8b95ab">{_period_label(period)} '
           f'{ts}</span> ')
    if "GOAL" in t:
        a = d.get("assist_ids") or []
        al = (" <span style=\"color:#8b95ab\">(assists: "
              f"{', '.join(_nm(by_id, x) for x in a)})</span>") if a else ""
        who = _nm(by_id, d.get("scorer_id"))
        return pre + f"🚨 <b>GOAL — {who}</b>{al}"
    if "PENALTY_SHOT" in t:
        return (pre + "<b>Penalty shot</b> — "
                f"{_nm(by_id, d.get('player_id'))}.")
    if "PENALTY" in t:
        mins = d.get("minutes", 2)
        inf = d.get("infraction") or d.get("reason") or ""
        inf = f" ({inf})" if inf else ""
        return (pre + f"<b>Penalty</b> — "
                f"{_nm(by_id, d.get('player_id'))} "
                f"({mins} min){inf}.")
    if "FIGHT" in t:
        return pre + "🥊 <b>Fight!</b>"
    if "SAVE" in t:
        q = d.get("shot_quality")
        qd = (f' <span style="color:#8b95ab">({q} danger)</span>'
              if q else "")
        return (pre + f"Save — <b>{_nm(by_id, d.get('goaltender_id'))}</b>"
                f"{qd}.")
    if "SHOT" in t:
        return (pre + f"Shot — <b>{_nm(by_id, d.get('shooter_id'))}</b>.")
    if "HIT" in t:
        hitter = (d.get("hitting_player_id") if d.get("hitting_player_id")
                  is not None else d.get("hitter_id"))
        target = (d.get("target_player_id") if d.get("target_player_id")
                  is not None else d.get("target_id"))
        return (pre + f"Hit — <b>{_nm(by_id, hitter)}</b> on "
                f"<b>{_nm(by_id, target)}</b>.")
    if "FACEOFF" in t:
        return pre + '<span style="color:#8b95ab">Faceoff.</span>'
    if "PERIOD_START" in t:
        return pre + f"Start of period {period}."
    if "PERIOD_END" in t:
        return pre + f"End of period {period}."
    desc = e.get("desc")
    if desc:
        return pre + str(desc)
    return (pre + '<span style="color:#8b95ab">'
            f"{str(e.get('type', '')).replace('_', ' ')}.</span>")


# ----------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------

class ReplayScreen(BaseScreen):
    """Completed-game replay: animated rink playback + PBP feed + box score."""

    title = "Replay"

    def __init__(self, game, main_window, parent=None):
        self._games = []        # newest-first result summaries
        self._pending_idx = None
        self._events = []
        self._by_id = {}
        self._side = {}
        self._meta = {}
        self._mode = "animated"  # animated | all | highlights | text
        self._cursor = 0        # next-big-moment cursor (static modes)
        self._big_anchors = []  # anchor ids of big moments in current view
        # Animated-playback state (mainline pbp_visual_sim parity).
        self._anim = None       # {"events": [...], "cursor", "playhead",
                                #  "score": [home, away], "t_max"}
        self._anim_rows = []    # HTML rows consumed so far (animated feed)
        self._playing = False
        self._speed = 1.0
        self._hold_until = 0.0  # big-moment beat (monotonic)
        self._follow_puck = False
        self._dots = {}         # str(pid) -> QGraphicsItem
        self._puck_item = None
        self._puck_pos = (100.0, 42.5)
        self._flight = None     # game-clock puck flight
        self._quiet = False     # instant-consume (seek): no flights/holds
        self._logged_goals = 0  # goals present in the stored event log
        super().__init__(game, main_window, parent)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(_TICK_MS)
        self._anim_timer.timeout.connect(self._pump_anim)

        # Keyboard: Space = play/pause, Left/Right = step one event
        # (REPLAYABLE_EVIDENCE_DESIGN.md: arrows step event-by-event).
        QShortcut(QKeySequence(Qt.Key_Space), self,
                  activated=self._toggle_play,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Left), self,
                  activated=self._step_back,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Right), self,
                  activated=self._step_fwd,
                  context=Qt.WidgetWithChildrenShortcut)

    # -- layout -------------------------------------------------------

    def _build_body(self):
        # Picker row
        picker = QHBoxLayout()
        picker.setSpacing(8)
        picker.addWidget(QLabel("Game:"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(420)
        self._combo.currentIndexChanged.connect(self._on_pick)
        picker.addWidget(self._combo)
        picker.addStretch()
        self._btn_box = QPushButton("📊 Box Score")
        self._btn_box.setObjectName("primary-btn")
        self._btn_box.setCursor(Qt.PointingHandCursor)
        self._btn_box.clicked.connect(self._open_boxscore)
        picker.addWidget(self._btn_box)
        self._layout.addLayout(picker)

        # Scorebug
        self._scorebug = QLabel("—")
        self._scorebug.setObjectName("dialog-title")
        self._scorebug.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._scorebug)

        # Playback controls (mainline _toggle_play/_set_speed/_sim_to_end)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self._btn_play = QPushButton("▶ Play")
        self._btn_play.setCursor(Qt.PointingHandCursor)
        self._btn_play.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._btn_play)
        self._btn_restart = QPushButton("⏹ Restart")
        self._btn_restart.setCursor(Qt.PointingHandCursor)
        self._btn_restart.clicked.connect(self._restart)
        ctrl.addWidget(self._btn_restart)
        self._btn_back = QPushButton("⏮ Step")
        self._btn_back.setCursor(Qt.PointingHandCursor)
        self._btn_back.clicked.connect(self._step_back)
        ctrl.addWidget(self._btn_back)
        self._btn_fwd = QPushButton("Step ⏭")
        self._btn_fwd.setCursor(Qt.PointingHandCursor)
        self._btn_fwd.clicked.connect(self._step_fwd)
        ctrl.addWidget(self._btn_fwd)
        ctrl.addWidget(QLabel("Speed:"))
        self._speed_box = QComboBox()
        for label, val in (("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0),
                           ("4×", 4.0)):
            self._speed_box.addItem(label, val)
        self._speed_box.setCurrentIndex(1)
        self._speed_box.currentIndexChanged.connect(
            lambda i: setattr(self, "_speed",
                              float(self._speed_box.itemData(i))))
        ctrl.addWidget(self._speed_box)
        self._btn_end = QPushButton("⏩ Sim to End")
        self._btn_end.setCursor(Qt.PointingHandCursor)
        self._btn_end.clicked.connect(self._sim_to_end)
        ctrl.addWidget(self._btn_end)
        self._btn_cam = QPushButton("🎥 Follow Puck")
        self._btn_cam.setCheckable(True)
        self._btn_cam.setCursor(Qt.PointingHandCursor)
        self._btn_cam.toggled.connect(self._toggle_follow)
        ctrl.addWidget(self._btn_cam)
        ctrl.addStretch()
        self._clock = QLabel("P1 0:00")
        self._clock.setStyleSheet("color:#8b95ab; font-size: 13px;")
        ctrl.addWidget(self._clock)
        self._layout.addLayout(ctrl)
        self._ctrl_row = ctrl

        # Animated rink (reuses watch.py's draw_rink -- one rendering
        # stack, no duplicate rink code).
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-14, -14, RINK_L + 28, RINK_W + 28)
        try:
            draw_rink(self._scene)
        except Exception as e:
            print(f"[replay] draw_rink failed: {e}")
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setMinimumHeight(300)
        self._layout.addWidget(self._view)

        # Ticker (mainline big-moment ticker parity).
        self._ticker = QLabel("")
        self._ticker.setObjectName("ticker")
        self._ticker.setAlignment(Qt.AlignCenter)
        self._ticker.setWordWrap(True)
        self._layout.addWidget(self._ticker)

        # Mode row
        modes = QHBoxLayout()
        modes.setSpacing(8)
        self._mode_btns = {}
        for key, label in (("animated", "🎬 Animated"),
                           ("all", "📺 Watch All"),
                           ("highlights", "✨ Highlights"),
                           ("text", "📝 Text")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key == "animated")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(
                lambda checked=False, k=key: self._set_mode(k))
            modes.addWidget(b)
            self._mode_btns[key] = b
        modes.addStretch()
        self._btn_next = QPushButton("⏭ Next Big Moment")
        self._btn_next.setCursor(Qt.PointingHandCursor)
        self._btn_next.clicked.connect(self._next_moment)
        modes.addWidget(self._btn_next)
        self._layout.addLayout(modes)

        # Feed
        self._feed = QTextBrowser()
        self._feed.setOpenExternalLinks(False)
        self._layout.addWidget(self._feed, 1)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #8b95ab; font-size: 12px;")
        self._layout.addWidget(self._status)
        self._mark_mode_btn("animated")

    # -- public / lifecycle -------------------------------------------

    def set_game(self, game_idx):
        """/replay?idx=N deep-link equivalent: pick a completed game."""
        try:
            self._pending_idx = int(game_idx)
        except (TypeError, ValueError):
            self._pending_idx = None
        self.refresh()

    def refresh(self):
        """Rebuild the picker from completed games; honor set_game()."""
        try:
            self._anim_timer.stop()
            self._playing = False
            self._combo.blockSignals(True)
            self._combo.clear()
            self._games = []
            for idx, r in enumerate(_past_results(self.game)):
                try:
                    if not isinstance(r, dict):
                        continue
                    hn, an = _team_name(r.get("home_team")), \
                        _team_name(r.get("away_team"))
                    if not hn or not an:
                        continue
                    tag = " (SO)" if r.get("shootout") else \
                        (" (OT)" if r.get("overtime") else "")
                    label = (f"{_date_str(r.get('date'))} — {an} "
                             f"{int(r.get('away_score', 0) or 0)} @ {hn} "
                             f"{int(r.get('home_score', 0) or 0)}{tag}")
                    self._games.append({
                        "idx": idx, "label": label, "result": r,
                        "date": r.get("date"),
                        "home": r.get("home_team"),
                        "away": r.get("away_team"),
                        "home_name": hn, "away_name": an,
                        "home_score": int(r.get("home_score", 0) or 0),
                        "away_score": int(r.get("away_score", 0) or 0),
                    })
                    self._combo.addItem(label, len(self._games) - 1)
                except Exception:
                    continue
            if not self._games:
                self._combo.addItem("No completed games yet", -1)
            elif self._pending_idx is not None:
                for i, g in enumerate(self._games):
                    if g["idx"] == self._pending_idx:
                        self._combo.setCurrentIndex(i)
                        break
            self._combo.blockSignals(False)
            self._load_current()
        except Exception as e:
            print(f"[replay] refresh failed: {e}")
        finally:
            try:
                self._combo.blockSignals(False)
            except Exception:
                pass

    # -- loading / static rendering -----------------------------------

    def _on_pick(self, i):
        self._pending_idx = None
        self._load_current()

    def _load_current(self):
        self._anim_timer.stop()
        self._playing = False
        self._hold_until = 0.0
        i = self._combo.currentData()
        if i is None or i < 0 or i >= len(self._games):
            self._meta = {}
            self._events = []
            self._by_id = {}
            self._side = {}
            self._anim = None
            self._scorebug.setText("—")
            self._clock.setText("P1 0:00")
            self._ticker.setText("")
            self._feed.setHtml(
                '<div style="color:#6b7488;padding:24px" align="center">'
                "No completed games yet — play some games first.</div>")
            self._btn_box.setEnabled(False)
            self._update_ctrl_state()
            return
        g = self._games[i]
        self._meta = g
        r = g["result"]
        self._by_id = _roster_lookup(r)
        self._side = _side_lookup(r)
        self._events = [e for e in (r.get("event_log") or [])
                        if isinstance(e, dict)]
        self._cursor = 0
        self._build_anim()
        self._btn_box.setEnabled(True)
        self._render_feed()
        self._update_ctrl_state()
        self._start_or_stop()

    def _set_mode(self, mode):
        self._mode = mode
        self._cursor = 0
        self._mark_mode_btn(mode)
        if mode == "animated":
            self._build_anim()
            self._render_feed()
            self._start_or_stop()
        else:
            self._anim_timer.stop()
            self._playing = False
            self._ticker.setText("")
            self._render_feed()
        self._update_ctrl_state()

    def _mark_mode_btn(self, mode):
        for k, b in self._mode_btns.items():
            b.setChecked(k == mode)
            if k == mode:
                b.setObjectName("primary-btn")
            else:
                b.setObjectName("")
            try:
                b.style().unpolish(b)
                b.style().polish(b)
            except Exception:
                pass

    def _row_html(self, e, big, compact):
        text = _event_text(e, self._by_id)
        if compact:
            style = ("font-size:13px;padding:1px 0;"
                     "border-bottom:1px solid #1a2233;")
        elif big:
            style = ("font-size:14px;font-weight:700;padding:6px 8px;"
                     "background:#1a2440;border-left:3px solid #e8b923;"
                     "margin:2px 0;")
        else:
            style = ("font-size:13px;padding:2px 0;"
                     "border-bottom:1px solid #1a2233;")
        return f'<div style="{style}">{text}</div>'

    def _render_feed(self):
        if self._mode == "animated":
            self._refresh_anim_feed()
            return
        events = self._events
        if self._mode == "highlights":
            events = [e for e in events if _is_highlight(e)]
        self._big_anchors = []
        if not events:
            self._feed.setHtml(
                '<div style="color:#6b7488;padding:24px" align="center">'
                "No events in this view.</div>")
            return
        compact = self._mode == "text"
        rows = []
        for i, e in enumerate(events):
            big = _is_big(e) and not compact
            anchor = ""
            if big:
                anchor = f'<a name="m{i}"></a>'
                self._big_anchors.append(f"m{i}")
            rows.append(anchor + self._row_html(e, big, compact))
        self._feed.setHtml("".join(rows))
        self._feed.verticalScrollBar().setValue(
            self._feed.verticalScrollBar().maximum())
        self._status.setText(
            f"{len(events)} events"
            f"{f' · {len(self._big_anchors)} big moments' if self._big_anchors else ''}.")

    def _next_moment(self):
        """Jump to the next big moment (goal/penalty/fight).

        Animated mode: consume the event stream up to and including the
        next big event (playback resumes from there). Static modes:
        scroll the feed to the next big-moment anchor (old behavior).
        """
        if self._mode == "animated" and self._anim is not None:
            evs = self._anim["events"]
            cur = self._anim["cursor"]
            for k in range(cur, len(evs)):
                if _is_big(evs[k]["ev"]):
                    keep = self._playing
                    self._seek_anim(k + 1, keep_playing=keep)
                    self._status.setText(
                        f"Jumped to big moment at "
                        f"{_period_label(evs[k]['period'])} "
                        f"{_fmt_ts(evs[k]['ev'].get('timestamp', 0))}.")
                    return
            self._status.setText("No more big moments — at the end.")
            return
        if not self._big_anchors:
            self._status.setText("No big moments in this view.")
            return
        if self._cursor >= len(self._big_anchors):
            self._cursor = 0
            self._status.setText(
                "No more big moments — replay restarts from the top.")
        anchor = self._big_anchors[self._cursor]
        self._cursor += 1
        try:
            self._feed.scrollToAnchor(anchor)
            self._status.setText(
                f"Big moment {self._cursor} of {len(self._big_anchors)}.")
        except Exception as e:
            print(f"[replay] next moment failed: {e}")

    def _open_boxscore(self):
        try:
            g = self._meta
            if not g:
                return
            dlg = BoxscoreDialog(self.game)
            dlg.set_game(g["date"], g["home"], g["away"])
            dlg.exec()
        except Exception as e:
            print(f"[replay] open boxscore failed: {e}")

    # -- animated playback (mainline pbp_visual_sim playback parity) ----

    def _build_anim(self):
        """Normalize the stored event log into a game-time event stream.

        Stored entries carry timestamp = seconds elapsed within their
        period; absolute game time is (period-1)*1200 + timestamp, exactly
        the `t` coordinate mainline's tick loop consumes against.
        """
        self._clear_dots()
        self._anim_rows = []
        self._flight = None
        self._puck_pos = (100.0, 42.5)
        self._ensure_puck()
        self._puck_item.setPos(*self._puck_pos)
        anim_events = []
        for i, e in enumerate(self._events):
            try:
                period, t = _event_game_time(e)
            except Exception:
                continue
            anim_events.append({"t": t, "ev": e, "period": period,
                                "idx": i})
        anim_events.sort(key=lambda a: (a["t"], a["idx"]))
        t_max = max([a["t"] for a in anim_events], default=0.0)
        self._anim = {"events": anim_events, "cursor": 0,
                      "playhead": 0.0, "score": [0, 0], "t_max": t_max}
        self._logged_goals = sum(
            1 for a in anim_events
            if "GOAL" in str(a["ev"].get("type", "") or "").upper())
        self._ticker.setText("")
        self._apply_camera(fit=True)
        if anim_events:
            self._clock.setText("P1 0:00")
        self._render_anim_chrome()

    def _has_anim_events(self):
        return (self._anim is not None
                and len(self._anim["events"]) > 0)

    def _update_ctrl_state(self):
        ok = self._mode == "animated" and self._has_anim_events()
        for w in (self._btn_play, self._btn_restart, self._btn_back,
                  self._btn_fwd, self._btn_end,
                  self._speed_box, self._btn_cam):
            try:
                w.setEnabled(ok)
            except Exception:
                pass
        # Next Big Moment works in every mode with events: animated
        # seeks the stream, static modes scroll the feed.
        try:
            self._btn_next.setEnabled(bool(self._events))
        except Exception:
            pass
        self._sync_play_btn()
        if not self._has_anim_events() and self._meta:
            if not self._events:
                self._status.setText(
                    "No replayable events in this game's log — "
                    "box score only.")
            self._scorebug.setText(
                f"{self._meta.get('away_name', '?')}  "
                f"{self._meta.get('away_score', 0)}  @  "
                f"{self._meta.get('home_score', 0)}  "
                f"{self._meta.get('home_name', '?')}   ·   FINAL")

    def _start_or_stop(self):
        """Mainline autostart parity: begin playing once events exist."""
        if self._mode == "animated" and self._has_anim_events():
            self._playing = True
            self._sync_play_btn()
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            self._anim_timer.stop()
            self._playing = False
            self._sync_play_btn()

    def _sync_play_btn(self):
        try:
            self._btn_play.setText(
                "⏸ Pause" if self._playing else "▶ Play")
        except Exception:
            pass

    # -- playback controls --------------------------------------------

    def _toggle_play(self):
        """Play/Pause (mainline _toggle_play parity). Never raises."""
        try:
            if self._mode != "animated" or not self._has_anim_events():
                return
            a = self._anim
            if (a["cursor"] >= len(a["events"])
                    and a["playhead"] >= a["t_max"]):
                # At the end: restart from the top and play.
                self._seek_anim(0, keep_playing=True)
            else:
                self._playing = not self._playing
            self._sync_play_btn()
            if self._playing and not self._anim_timer.isActive():
                self._anim_timer.start()
        except Exception as e:
            print(f"[replay] toggle play failed: {e}")

    def _restart(self):
        try:
            if not self._has_anim_events():
                return
            self._seek_anim(0, keep_playing=False)
            self._status.setText("Replay restarted.")
        except Exception as e:
            print(f"[replay] restart failed: {e}")

    def _sim_to_end(self):
        """Mainline _sim_to_end parity: consume the whole stream now."""
        try:
            if not self._has_anim_events():
                return
            self._seek_anim(len(self._anim["events"]),
                            keep_playing=False)
            self._finish_anim()
        except Exception as e:
            print(f"[replay] sim to end failed: {e}")

    def _step_back(self):
        try:
            if self._mode != "animated" or not self._has_anim_events():
                return
            k = self._anim["cursor"] - 1
            if k < 0:
                return
            self._seek_anim(k, keep_playing=self._playing)
        except Exception as e:
            print(f"[replay] step back failed: {e}")

    def _step_fwd(self):
        """Step one event forward (←/→ design-doc parity)."""
        try:
            if self._mode != "animated" or not self._has_anim_events():
                return
            a = self._anim
            if a["cursor"] >= len(a["events"]):
                return
            self._quiet = True
            try:
                self._consume_anim(a["events"][a["cursor"]])
                a["cursor"] += 1
                a["playhead"] = max(a["playhead"],
                                    a["events"][a["cursor"] - 1]["t"])
            finally:
                self._quiet = False
            self._render_anim_chrome()
            self._refresh_anim_feed()
            self._apply_camera()
            if (a["cursor"] >= len(a["events"])
                    and a["playhead"] >= a["t_max"]):
                self._finish_anim()
        except Exception as e:
            print(f"[replay] step fwd failed: {e}")

    def _toggle_follow(self, checked):
        self._follow_puck = bool(checked)
        self._apply_camera(fit=True)

    def _seek_anim(self, k, keep_playing=None):
        """Rewind-safe seek: rebuild state by re-consuming from the
        start, so step-back can't drift the score or dots."""
        a = self._anim
        if a is None:
            return
        evs = a["events"]
        k = max(0, min(k, len(evs)))
        self._clear_dots()
        self._anim_rows = []
        a["score"] = [0, 0]
        a["cursor"] = 0
        a["playhead"] = 0.0
        self._flight = None
        self._puck_pos = (100.0, 42.5)
        self._ensure_puck()
        self._puck_item.setPos(*self._puck_pos)
        self._hold_until = 0.0
        self._quiet = True
        try:
            while a["cursor"] < k:
                self._consume_anim(evs[a["cursor"]])
                a["cursor"] += 1
        finally:
            self._quiet = False
        if k:
            a["playhead"] = evs[k - 1]["t"]
        if keep_playing is not None:
            self._playing = keep_playing
        self._render_anim_chrome()
        self._refresh_anim_feed()
        self._apply_camera()
        self._sync_play_btn()

    # -- the tick (mainline _tick/_step parity) ------------------------

    def _pump_anim(self):
        """33ms tick: advance the playhead and consume due events."""
        try:
            if (self._mode != "animated" or self._anim is None
                    or not self._playing):
                return
            now = time.monotonic()
            if now < self._hold_until:
                return  # big-moment beat: hold the frame
            dt = (_TICK_MS / 1000.0) * self._speed * _GAME_RATE
            a = self._anim
            evs = a["events"]
            target = a["playhead"] + dt
            while (a["cursor"] < len(evs)
                   and evs[a["cursor"]]["t"] <= target):
                self._consume_anim(evs[a["cursor"]])
                a["cursor"] += 1
                a["playhead"] = max(a["playhead"],
                                    evs[a["cursor"] - 1]["t"])
                if time.monotonic() < self._hold_until:
                    break  # big moment just set a beat; hold it
            else:
                a["playhead"] = max(a["playhead"], target)
            self._step_flight(dt)
            self._render_anim_chrome()
            self._apply_camera()
            if (a["cursor"] >= len(evs)
                    and a["playhead"] >= a["t_max"]):
                self._finish_anim()
        except Exception as e:
            print(f"[replay] pump failed: {e}")

    def _consume_anim(self, ae):
        """Consume one event: score, rink animation, feed row, ticker."""
        ev = ae["ev"]
        et = str(ev.get("type", "") or "").upper()
        d = ev.get("details") or {}
        if not isinstance(d, dict):
            d = {}
        self._anim_rows.append(
            self._row_html(ev, big=_is_big(ev), compact=False))
        if "GOAL" in et:
            self._animate_goal(ev, d)
        elif "SAVE" in et:
            self._animate_save(ev, d)
        elif "SHOT" in et:
            self._animate_shot(ev, d)
        if self._quiet:
            return
        if _is_big(ev):
            self._ticker.setText(_strip_html(_event_text(ev, self._by_id)))
            for key in ("GOAL", "PENALTY_SHOT", "FIGHT", "PENALTY"):
                if key in et:
                    pace_key = key
                    break
            else:
                pace_key = "PENALTY"
            self._hold_until = (time.monotonic()
                                + _PACE.get(pace_key, 1.0))
        elif _is_highlight(ev):
            self._ticker.setText(_strip_html(_event_text(ev, self._by_id)))

    def _finish_anim(self):
        """End of the stream: stop, show the official final score."""
        try:
            self._playing = False
            self._anim_timer.stop()
            self._sync_play_btn()
            g = self._meta or {}
            hn = g.get("home_name", "?")
            an = g.get("away_name", "?")
            hs = g.get("home_score", 0)
            aws = g.get("away_score", 0)
            self._scorebug.setText(
                f"{an}  {aws}  @  {hs}  {hn}   ·   FINAL")
            self._clock.setText("FINAL")
            live_h, live_aws = self._anim["score"]
            note = ""
            official_total = hs + aws
            if self._logged_goals != official_total:
                # Rebound goals and the shootout winner's +1 are not
                # written to the sim's event log (simulation.py only
                # appends GOAL_ADVANCED on direct shot resolutions), so
                # the stream undercounts. The official final stands.
                note = (f" (event log captured {self._logged_goals} of "
                        f"{official_total} goals)")
            self._status.setText(
                f"Replay complete — {len(self._anim['events'])} events"
                f"{note}.")
            self._ticker.setText(
                f"Final: {an} {aws} — {hs} {hn}")
        except Exception as e:
            print(f"[replay] finish failed: {e}")

    # -- rink animation (synthesized from event details) ----------------

    def _ensure_puck(self):
        if self._puck_item is None:
            try:
                self._puck_item = QGraphicsEllipseItem(-0.9, -0.9, 1.8, 1.8)
                self._puck_item.setBrush(QBrush(QColor("#111111")))
                self._puck_item.setPen(QPen(Qt.NoPen))
                self._puck_item.setZValue(5)
                self._scene.addItem(self._puck_item)
            except Exception as e:
                print(f"[replay] puck create failed: {e}")
                self._puck_item = None

    def _set_puck(self, x, y):
        self._puck_pos = (x, y)
        if self._puck_item is not None:
            try:
                self._puck_item.setPos(x, y)
            except Exception:
                pass

    def _ensure_dot(self, pid, side, goalie):
        """Create (or fetch) a rink dot for a player, watch.py style."""
        if pid is None:
            return None
        key = str(pid)
        item = self._dots.get(key)
        if item is None:
            try:
                if goalie:
                    item = QGraphicsRectItem(-3, -3, 6, 6)
                else:
                    item = QGraphicsEllipseItem(-2.2, -2.2, 4.4, 4.4)
                item.setZValue(2)
                name = _nm(self._by_id, pid)
                if name and name != "?":
                    item.setToolTip(str(name))
                self._scene.addItem(item)
                self._dots[key] = item
            except Exception as e:
                print(f"[replay] dot create failed: {e}")
                return None
        try:
            item.setBrush(QBrush(_HOME_COLOR if side == 0 else _AWAY_COLOR))
            if goalie:
                item.setPen(QPen(QColor("#ffffff"), 1.2))
            else:
                item.setPen(QPen(QColor("#0b0f1a"), 0.8))
        except Exception:
            pass
        return item

    def _clear_dots(self):
        for item in list(self._dots.values()):
            try:
                self._scene.removeItem(item)
            except Exception:
                pass
        self._dots = {}

    def _launch_flight(self, segs):
        """Game-clock puck flight: the puck glides touch-to-touch and
        spans real game time (mainline _launch_flight parity)."""
        x0, y0 = self._puck_pos
        self._flight = {"x0": x0, "y0": y0, "segs": list(segs),
                        "i": 0, "t": 0.0}

    def _step_flight(self, dt):
        f = self._flight
        if not f:
            return
        while dt > 0 and f["i"] < len(f["segs"]):
            x1, y1, dur = f["segs"][f["i"]]
            if dur <= 0:
                f["x0"], f["y0"] = x1, y1
                f["i"] += 1
                continue
            step = min(dt, dur - f["t"])
            frac = (f["t"] + step) / dur
            px = f["x0"] + (x1 - f["x0"]) * frac
            py = f["y0"] + (y1 - f["y0"]) * frac
            f["t"] += step
            dt -= step
            self._set_puck(px, py)
            if f["t"] >= dur:
                f["x0"], f["y0"] = x1, y1
                f["i"] += 1
                f["t"] = 0.0
        if f["i"] >= len(f["segs"]):
            self._flight = None

    def _goal_side(self, d):
        """Which side scored: resolve scorer (or goalie) via the roster."""
        scorer = d.get("scorer_id")
        side = self._side.get(str(scorer)) if scorer is not None else None
        if side is None:
            goalie = d.get("goaltender_id")
            gs = self._side.get(str(goalie)) if goalie is not None else None
            if gs is not None:
                side = 1 - gs
        return side

    def _animate_goal(self, ev, d):
        side = self._goal_side(d)
        scored = side is not None
        if side is None:
            side = 0  # fallback: still render, don't move the score
        else:
            self._anim["score"][side] += 1
        att_home = (side == 0)
        spot = _shot_spot(d, att_home)
        net = (189.0, 42.5) if att_home else (11.0, 42.5)
        crease = (186.0, 42.5) if att_home else (14.0, 42.5)
        # Skater who scored, at the shot spot (gold pen = possession).
        dot = self._ensure_dot(d.get("scorer_id"), side, False)
        if dot is not None:
            dot.setPos(*spot)
            try:
                dot.setPen(QPen(_POSS_COLOR, 1.2))
            except Exception:
                pass
        # Helpers drift near the play.
        for k, aid in enumerate((d.get("assist_ids") or [])[:2]):
            ad = self._ensure_dot(aid, side, False)
            if ad is not None:
                ad.setPos(spot[0] - (6 + 5 * k) * (1 if att_home else -1),
                          spot[1] + (8 if k % 2 else -8))
        # Defending goalie in the crease; one defender in front.
        gdot = self._ensure_dot(d.get("goaltender_id"), 1 - side, True)
        if gdot is not None:
            gdot.setPos(*crease)
        if self._quiet:
            self._set_puck(*net)
        else:
            # Pass into the slot, then the shot into the net.
            self._launch_flight([(spot[0], spot[1], 1.5),
                                 (net[0], net[1], 1.0)])
        if not scored:
            self._ticker.setText(
                "Goal logged without a resolvable scorer — "
                "score unchanged.")

    def _animate_save(self, ev, d):
        shooter = d.get("shooter_id")
        goalie = d.get("goaltender_id")
        side = self._side.get(str(shooter)) if shooter is not None else None
        if side is None:
            gs = self._side.get(str(goalie)) if goalie is not None else None
            side = 1 - gs if gs is not None else 0
        att_home = (side == 0)
        spot = _shot_spot(d, att_home)
        crease = (186.0, 42.5) if att_home else (14.0, 42.5)
        sdot = self._ensure_dot(shooter, side, False)
        if sdot is not None:
            sdot.setPos(*spot)
            try:
                sdot.setPen(QPen(_POSS_COLOR, 1.2))
            except Exception:
                pass
        gdot = self._ensure_dot(goalie, 1 - side, True)
        if gdot is not None:
            gdot.setPos(*crease)
        if self._quiet:
            self._set_puck(*crease)
        else:
            self._launch_flight([(spot[0], spot[1], 1.2),
                                 (crease[0], crease[1], 0.8)])

    def _animate_shot(self, ev, d):
        shooter = d.get("shooter_id")
        side = self._side.get(str(shooter)) if shooter is not None else None
        if side is None:
            side = 0
        att_home = (side == 0)
        spot = _shot_spot(d, att_home)
        net = (189.0, 42.5) if att_home else (11.0, 42.5)
        sdot = self._ensure_dot(shooter, side, False)
        if sdot is not None:
            sdot.setPos(*spot)
        if self._quiet:
            self._set_puck(*net)
        else:
            self._launch_flight([(spot[0], spot[1], 1.2),
                                 (net[0], net[1], 0.9)])

    # -- animated chrome ------------------------------------------------

    def _apply_camera(self, fit=False):
        """Follow-puck broadcast camera (mainline CAM_ZOOM parity)."""
        try:
            if self._follow_puck and self._puck_item is not None and not fit:
                self._view.resetTransform()
                self._view.scale(1.22, 1.22)
                self._view.centerOn(self._puck_item)
            else:
                self._view.resetTransform()
                self._view.fitInView(self._scene.sceneRect(),
                                     Qt.KeepAspectRatio)
        except Exception as e:
            print(f"[replay] camera failed: {e}")

    def _render_anim_chrome(self):
        """Live scorebug + game clock from the animation state."""
        try:
            if self._anim is None or not self._meta:
                return
            g = self._meta
            a = self._anim
            s = a["score"]
            ph = a["playhead"]
            period = int(ph // 1200) + 1
            remaining = 1200.0 - (ph % 1200.0)
            label = (f"{g.get('away_name', '?')}  {s[1]}  @  "
                     f"{s[0]}  {g.get('home_name', '?')}   ·   "
                     f"{_period_label(period)} {_fmt_ts(remaining)}")
            self._scorebug.setText(label)
            self._clock.setText(f"{_period_label(period)} "
                                f"{_fmt_ts(remaining)}")
        except Exception as e:
            print(f"[replay] chrome failed: {e}")

    def _refresh_anim_feed(self):
        """Feed shows the events consumed so far (live PBP feel)."""
        try:
            rows = self._anim_rows
            if not rows:
                a = self._anim
                total = len(a["events"]) if a else 0
                self._feed.setHtml(
                    '<div style="color:#6b7488;padding:24px" align="center">'
                    "Press Play to start the replay"
                    f"{f' — {total} events' if total else ''}.</div>")
            else:
                self._feed.setHtml("".join(rows))
                bar = self._feed.verticalScrollBar()
                bar.setValue(bar.maximum())
            if self._anim is not None:
                a = self._anim
                self._status.setText(
                    f"Event {a['cursor']} of {len(a['events'])}"
                    f" · {_fmt_ts(a['playhead'])} of game time"
                    f"{' · ⏸ paused' if not self._playing else ''}.")
        except Exception as e:
            print(f"[replay] anim feed failed: {e}")
