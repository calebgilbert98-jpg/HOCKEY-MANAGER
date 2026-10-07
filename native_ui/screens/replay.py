"""Replay screen: completed-game play-by-play replay + box score.

Ported from web_ui/screens/watch.py (replay endpoints) +
web_ui/templates/replay.html + web_ui/static/js/replay.js.

Pick a completed game, replay its stored event log in three modes
(All / Highlights / Text), jump between big moments, and drill into
the full box score via the shared BoxscoreDialog. set_game(game_idx)
is the deep-link equivalent of /replay?idx=N (index into the
newest-first completed-games list).
"""
from datetime import date, datetime

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QComboBox, QTextBrowser, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..dialogs.boxscore import BoxscoreDialog


# ----------------------------------------------------------------------
# Helpers (ported from web_ui/screens/watch.py, Flask removed)
# ----------------------------------------------------------------------

# pbp_visual_sim BIG_MOMENTS parity (web_ui/static/js/replay.js).
_BIG = ("GOAL", "PENALTY", "FIGHT", "PENALTY_SHOT")


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


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


def _past_results(game):
    """Completed game_results, newest first. Never raises."""
    try:
        results = _safe(lambda: list(getattr(game, "game_results", None)
                                     or []), []) or []
    except Exception:
        return []
    return list(reversed(results))


def _roster_lookup(result):
    """str(pid) -> Player for a stored result (roster + game_stats)."""
    by_id = {}
    for key in ("home_team", "away_team"):
        try:
            team = result.get(key)
            for p in _safe(lambda: list(getattr(team, "roster", None)
                                       or []), []) or []:
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
    """Completed-game replay: picker + PBP feed + box score drill-down."""

    title = "Replay"

    def __init__(self, game, main_window, parent=None):
        self._games = []        # newest-first result summaries
        self._pending_idx = None
        self._events = []
        self._by_id = {}
        self._meta = {}
        self._mode = "all"      # all | highlights | text
        self._cursor = 0        # next-big-moment cursor
        self._big_anchors = []  # anchor ids of big moments in current view
        super().__init__(game, main_window, parent)

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

        # Mode row
        modes = QHBoxLayout()
        modes.setSpacing(8)
        self._mode_btns = {}
        for key, label in (("all", "📺 Watch All"),
                           ("highlights", "✨ Highlights"),
                           ("text", "📝 Text")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key == "all")
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

    # -- loading / rendering ------------------------------------------

    def _on_pick(self, i):
        self._pending_idx = None
        self._load_current()

    def _load_current(self):
        i = self._combo.currentData()
        if i is None or i < 0 or i >= len(self._games):
            self._meta = {}
            self._events = []
            self._by_id = {}
            self._scorebug.setText("—")
            self._feed.setHtml(
                '<div style="color:#6b7488;padding:24px" align="center">'
                "No completed games yet — play some games first.</div>")
            self._btn_box.setEnabled(False)
            return
        g = self._games[i]
        self._meta = g
        r = g["result"]
        self._by_id = _roster_lookup(r)
        self._events = [e for e in (r.get("event_log") or [])
                        if isinstance(e, dict)]
        self._cursor = 0
        self._scorebug.setText(
            f"{g['away_name']}  {g['away_score']}  @  "
            f"{g['home_score']}  {g['home_name']}   ·   FINAL")
        self._btn_box.setEnabled(True)
        self._render_feed()

    def _set_mode(self, mode):
        self._mode = mode
        self._cursor = 0
        for k, b in self._mode_btns.items():
            b.setChecked(k == mode)
            if k == mode:
                b.setObjectName("primary-btn")
            else:
                b.setObjectName("")
            b.style().unpolish(b)
            b.style().polish(b)
        self._render_feed()

    def _render_feed(self):
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
            text = _event_text(e, self._by_id)
            big = _is_big(e) and not compact
            anchor = ""
            if big:
                anchor = f'<a name="m{i}"></a>'
                self._big_anchors.append(f"m{i}")
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
            rows.append(f"{anchor}<div style=\"{style}\">{text}</div>")
        self._feed.setHtml("".join(rows))
        self._feed.verticalScrollBar().setValue(
            self._feed.verticalScrollBar().maximum())
        self._status.setText(
            f"{len(events)} events"
            f"{f' · {len(self._big_anchors)} big moments' if self._big_anchors else ''}.")

    def _next_moment(self):
        """Jump the feed to the next big moment (goal/penalty/fight)."""
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
