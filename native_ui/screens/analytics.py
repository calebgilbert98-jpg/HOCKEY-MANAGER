"""Analytics Hub: native Qt port.

Ports main.py open_analytics_hub (analytics_hub.AnalyticsHubView).
Shot/xG maps, momentum graphs, zone-entry maps, line trends, and
Ask the Analyst -- all rendered with QPainter, no stubs.

Data source: team.analytics_games (list of per-game records, oldest
first, max 10). Each record carries shots, momentum, entries,
assist_pairs, and lines. The aggregation functions below are ported
from analytics_hub.py (mainline) so this screen has zero dependency
on customtkinter, which is not installed in the native build.
"""
from collections import Counter, defaultdict

from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Analytics aggregation (ported from analytics_hub.py -- pure Python,
# no UI dependencies, so the native build needs no customtkinter)
# ---------------------------------------------------------------------------

MAX_GAMES = 10

_MOMENTUM_VALUE = {
    "heavily_favoring_home": 3,
    "favoring_home": 2,
    "slightly_favoring_home": 1,
    "neutral": 0,
    "slightly_favoring_away": -1,
    "favoring_away": -2,
    "heavily_favoring_away": -3,
}


def _team_games(team):
    """Recent per-game analytics records, oldest first (max 10)."""
    try:
        games = list(getattr(team, "analytics_games", None) or [])
    except Exception:
        games = []
    return games[-MAX_GAMES:]


def _latest_game(team):
    games = _team_games(team)
    return games[-1] if games else None


def _game_label(rec, team_name=""):
    """Short label like 'vs TOR · Mar 4 · 3-2 W'."""
    try:
        home, away = rec.get("home", ""), rec.get("away", "")
        hs, aws = rec.get("score", (0, 0))
        if team_name and team_name == home:
            opp, us, them = away, hs, aws
            tag = "vs"
        elif team_name and team_name == away:
            opp, us, them = home, aws, hs
            tag = "@"
        else:
            opp, us, them, tag = away, hs, aws, ""
        result = "W" if us > them else "L" if us < them else "T"
        date = (rec.get("date") or "").strip()
        bits = [f"{tag} {opp}".strip(), f"{us}-{them} {result}"]
        if date:
            bits.insert(1, date)
        return " · ".join(bits)
    except Exception:
        return "game"


def _shots_for(rec, team_name):
    try:
        return [s for s in rec.get("shots", [])
                if s.get("team") == team_name]
    except Exception:
        return []


def _entries_for(rec, team_name):
    try:
        return [e for e in rec.get("entries", [])
                if e.get("team") == team_name]
    except Exception:
        return []


def _momentum_points(rec, team_name=""):
    """Momentum stream with value signed for the viewed team
    (positive = their momentum)."""
    pts = []
    try:
        home = rec.get("home", "")
        flip = -1 if (team_name and team_name != home) else 1
        for m in rec.get("momentum", []):
            raw = m.get("momentum", "neutral")
            val = _MOMENTUM_VALUE.get(str(raw), 0)
            pts.append({
                "period": int(m.get("period", 1) or 1),
                "time": float(m.get("time", 0) or 0),
                "value": val * flip,
                "trigger": str(m.get("trigger", "")),
            })
    except Exception:
        pass
    return pts


def _team_xg(shots):
    xg = sum(float(s.get("xg", 0) or 0) for s in shots)
    goals = sum(1 for s in shots if s.get("outcome") == "goal")
    return round(xg, 2), goals


def _player_xg_rows(shots):
    """Per-shooter: shots, xG, goals, goals-minus-xG. Sorted by xG."""
    agg = defaultdict(lambda: {"shots": 0, "xg": 0.0, "goals": 0})
    for s in shots:
        a = agg[s.get("shooter", "?")]
        a["shots"] += 1
        a["xg"] += float(s.get("xg", 0) or 0)
        if s.get("outcome") == "goal":
            a["goals"] += 1
    rows = [{"shooter": k, "shots": v["shots"],
             "xg": round(v["xg"], 2), "goals": v["goals"],
             "diff": round(v["goals"] - v["xg"], 2)}
            for k, v in agg.items()]
    rows.sort(key=lambda r: (-r["xg"], -r["shots"]))
    return rows


def _grade_xg_rows(shots):
    """Per chance-grade (A/B/C): shots, xG, goals, conversion."""
    agg = defaultdict(lambda: {"shots": 0, "xg": 0.0, "goals": 0})
    for s in shots:
        try:
            _g = str(s.get("grade") or "").upper()
        except Exception:
            _g = ""
        if _g not in ("A", "B", "C"):
            _g = "?"
        a = agg[_g]
        a["shots"] += 1
        a["xg"] += float(s.get("xg", 0) or 0)
        if s.get("outcome") == "goal":
            a["goals"] += 1
    rows = [{"grade": k, "shots": v["shots"],
             "xg": round(v["xg"], 2), "goals": v["goals"],
             "conv": round(v["goals"] / v["shots"], 3) if v["shots"] else 0.0,
             "diff": round(v["goals"] - v["xg"], 2)}
            for k, v in agg.items()]
    order = {"A": 0, "B": 1, "C": 2, "?": 3}
    rows.sort(key=lambda r: order.get(r["grade"], 9))
    return rows


def _player_grade_xg_rows(shots):
    """Per-shooter per-grade: shots and xG split by chance grade."""
    agg = defaultdict(lambda: {"A": 0, "B": 0, "C": 0,
                               "xg_a": 0.0, "xg_b": 0.0, "xg_c": 0.0,
                               "shots": 0, "xg": 0.0, "goals": 0})
    for s in shots:
        try:
            _g = str(s.get("grade") or "").upper()
        except Exception:
            _g = ""
        a = agg[s.get("shooter", "?")]
        a["shots"] += 1
        _xg = float(s.get("xg", 0) or 0)
        a["xg"] += _xg
        if _g in ("A", "B", "C"):
            a[_g] += 1
            a[f"xg_{_g.lower()}"] += _xg
        if s.get("outcome") == "goal":
            a["goals"] += 1
    rows = [{"shooter": k, "shots": v["shots"],
             "a_shots": v["A"], "b_shots": v["B"], "c_shots": v["C"],
             "a_share": round(v["A"] / v["shots"], 3) if v["shots"] else 0.0,
             "xg": round(v["xg"], 2), "goals": v["goals"],
             "diff": round(v["goals"] - v["xg"], 2)}
            for k, v in agg.items()]
    rows.sort(key=lambda r: (-r["xg"], -r["shots"]))
    return rows


def _line_xg_rows(shots, line_chem=None):
    """Per forward line: shots, xG, goals, latest chemistry."""
    agg = defaultdict(lambda: {"shots": 0, "xg": 0.0, "goals": 0})
    for s in shots:
        a = agg[s.get("line", "-")]
        a["shots"] += 1
        a["xg"] += float(s.get("xg", 0) or 0)
        if s.get("outcome") == "goal":
            a["goals"] += 1
    chem = line_chem or {}
    rows = [{"line": k, "shots": v["shots"],
             "xg": round(v["xg"], 2), "goals": v["goals"],
             "diff": round(v["goals"] - v["xg"], 2),
             "chemistry": (chem.get(k) or {}).get("chemistry", "-")}
            for k, v in agg.items() if k != "-"]
    order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}
    rows.sort(key=lambda r: order.get(r["line"], 9))
    return rows


def _rolling_line_trends(team, n=5):
    """Per-line xG across the last n games: {line: [(label, xg), ...]}."""
    trends = defaultdict(list)
    for rec in _team_games(team)[-n:]:
        name = getattr(team, "team_name", "")
        lx = _line_xg_rows(_shots_for(rec, name))
        have = {r["line"]: r["xg"] for r in lx}
        for line in ("L1", "L2", "L3", "L4"):
            trends[line].append((_game_label(rec, name),
                                 have.get(line, 0.0)))
    return dict(trends)


def _assist_pair_rows(recs, name_lookup=None, limit=12):
    """Line-combination effectiveness from the assist-pairs ledger."""
    counts = Counter()
    for rec in recs or []:
        try:
            pairs = rec.get("assist_pairs") or []
        except Exception:
            continue
        for t in pairs:
            try:
                counts[(t[0], t[1])] += 1
            except Exception:
                continue
    nl = name_lookup or {}
    return [{"passer": nl.get(pid, pid), "scorer": nl.get(sid, sid),
             "goals": n}
            for (pid, sid), n in counts.most_common(limit)]


def _entry_breakdown(entries):
    counts = Counter(e.get("type", "?") for e in entries)
    total = sum(counts.values())
    controlled = sum(c for t, c in counts.items()
                     if "CONTROLLED" in str(t).upper()
                     or "CARRY" in str(t).upper())
    return {
        "counts": dict(counts),
        "total": total,
        "controlled": controlled,
        "controlled_pct": round(100.0 * controlled / total, 1)
        if total else 0.0,
    }


def _analyst_report(team):
    """Return [(heading, [lines])] grounded in the team's game records.

    A diagnosis, not an answer key: observations plus open questions.
    """
    games = _team_games(team)
    name = getattr(team, "team_name", "")
    if not games:
        return [("No data yet",
                 ["Play a game and the analyst will have something "
                  "to work with."])]

    recent = games[-5:]
    shots = [s for g in recent for s in _shots_for(g, name)]
    entries = [e for g in recent for e in _entries_for(g, name)]

    sections = []

    # -- Finishing vs chance creation ------------------------------------
    xg = sum(float(s.get("xg", 0) or 0) for s in shots)
    goals = sum(1 for s in shots if s.get("outcome") == "goal")
    diff = goals - xg
    lines = [
        f"Last {len(recent)} games: {goals} goals on {xg:.1f} expected "
        f"({len(shots)} shots).",
    ]
    if diff <= -1.5:
        lines.append("The chances are there; the finish isn't. That's "
                     "usually shooting luck, not the system -- it tends "
                     "to even out.")
    elif diff >= 1.5:
        lines.append("Outscoring the chances. Enjoy it, but don't budget "
                     "on it -- the model says this pace is borrowed.")
    else:
        lines.append("Finishing is tracking the chances. What you see is "
                     "roughly what the chances deserved.")
    if shots:
        lines.append(f"Average chance quality: {xg / len(shots):.3f} xG "
                     "per shot.")
    sections.append(("Finishing vs. chance creation", lines))

    # -- Shot quality ------------------------------------------------------
    if shots:
        hd = sum(1 for s in shots if float(s.get("xg", 0) or 0) >= 0.12)
        lines = [
            f"High-danger share: {hd}/{len(shots)} shots "
            f"({100.0 * hd / len(shots):.0f}%).",
        ]
        if hd / len(shots) < 0.25:
            lines.append("A lot of perimeter looks. If the shot map "
                         "shows everything from outside, the issue is "
                         "chance quality, not the shooters.")
        else:
            lines.append("Getting to the dangerous ice. If the goals "
                         "still aren't coming, that's a finishing "
                         "question, not a systems one.")
        sections.append(("Shot quality", lines))

    # -- Momentum ----------------------------------------------------------
    lg = _latest_game(team)
    pts = _momentum_points(lg, name) if lg else []
    if pts:
        vals = [p["value"] for p in pts]
        swing = max(vals) - min(vals)
        talk_driven = sum(1 for p in pts
                          if "talk" in p["trigger"].lower()
                          or "dressing" in p["trigger"].lower())
        lines = [
            f"Biggest swing last game: {swing:+d} momentum steps.",
            f"Momentum shifts tracked: {len(pts)}.",
        ]
        if talk_driven:
            lines.append(f"{talk_driven} shift(s) followed a team talk -- "
                         "the room is listening, for better or worse.")
        if swing >= 4:
            lines.append("A rollercoaster. When the game tilts this far, "
                         "look at what started the slide -- the trigger "
                         "log on the Momentum tab names it.")
        sections.append(("Momentum", lines))

    # -- Zone entries ------------------------------------------------------
    eb = _entry_breakdown(entries)
    if eb["total"]:
        lines = [
            f"Controlled entries: {eb['controlled']}/{eb['total']} "
            f"({eb['controlled_pct']:.0f}%).",
        ]
        if eb["controlled_pct"] < 40:
            lines.append("The breakout is leaking -- most entries are "
                         "dump-ins. Controlled entries are where the "
                         "xG comes from; check whether the breakout "
                         "tactic actually favors carrying it in.")
        else:
            lines.append("Winning the blue line. If the xG still lags, "
                         "the problem starts after the entry, not "
                         "before it.")
        sections.append(("Zone entries", lines))

    # -- Lines -------------------------------------------------------------
    if lg:
        lx = _line_xg_rows(_shots_for(lg, name), lg.get("lines"))
        if lx:
            best = max(lx, key=lambda r: r["xg"])
            worst = min(lx, key=lambda r: r["xg"])
            lines = [
                f"Last game xG by line: " +
                ", ".join(f"{r['line']} {r['xg']:.1f}" for r in lx) + ".",
                f"{best['line']} drove play "
                f"({best['xg']:.1f} xG, chemistry {best['chemistry']}).",
            ]
            if worst["xg"] < best["xg"] / 2 and len(lx) > 1:
                lines.append(f"{worst['line']} is a passenger right now "
                             f"({worst['xg']:.1f} xG). Matchup problem, "
                             "chemistry problem, or just one game?")
            sections.append(("Lines", lines))

    # -- Open questions ----------------------------------------------------
    pr = _player_xg_rows(shots)
    if pr:
        hot = pr[0]
        cold = [r for r in pr
                if r["shots"] >= 5 and r["diff"] <= -1.0]
        lines = []
        if cold:
            c = cold[0]
            lines.append(f"{c['shooter']}: {c['goals']} goals on "
                         f"{c['xg']:.1f} xG ({c['shots']} shots). "
                         "Slump or decline? The shot map is the tiebreak.")
        lines.append(f"{hot['shooter']} is generating the most "
                     f"({hot['xg']:.1f} xG). Ride that line while it's "
                     "hot -- or sell high? Your call.")
        sections.append(("What to watch", lines))

    return sections


class RinkMapWidget(QWidget):
    """QPainter rink diagram with shot/entry markers.

    Shot dicts use the analytics_hub coordinate system: x 100-200
    (attacking zone), y 0-85. Shots are converted to widget space.
    """

    def __init__(self, parent=None, x_range=(100.0, 200.0), full_rink=False):
        super().__init__(parent)
        self._shots = []      # [{x, y, xg, outcome}]
        self._entries = []    # [{x, y, type}]
        self._x_range = x_range
        self._full_rink = full_rink
        self.setMinimumSize(640, 300)

    def set_shots(self, shots):
        self._shots = list(shots or [])
        self._entries = []
        self.update()

    def set_entries(self, entries):
        self._entries = list(entries or [])
        self._shots = []
        self.update()

    def _transform(self, w, h):
        x0, x1 = self._x_range
        pad = 14
        def f(x, y):
            cx = pad + (x - x0) / (x1 - x0) * (w - 2 * pad)
            cy = pad + y / 85.0 * (h - 2 * pad)
            return cx, cy
        return f

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0d1626"))

        # Rink outline
        p.setPen(QPen(QColor("#e8edf5"), 2))
        p.setBrush(QBrush(Qt.NoBrush))
        margin = 10
        p.drawRoundedRect(margin, margin, w - 2 * margin, h - 2 * margin,
                          30, 30)

        f = self._transform(w, h)
        x0, x1 = self._x_range

        # Lines: red line, blue line, goal line
        for x, color in ((100.0, "#ef4444"), (125.0, "#3B82F6"),
                         (189.0, "#ef4444")):
            if x0 <= x <= x1:
                ax, ay = f(x, 0)
                _, by = f(x, 85)
                p.setPen(QPen(QColor(color), 3))
                p.drawLine(int(ax), int(ay), int(ax), int(by))

        # Faceoff circles (attacking zone)
        for cy0 in (20.5, 64.5):
            ax, ay = f(169, cy0)
            r = 15 / (x1 - x0) * (w - 28)
            p.setPen(QPen(QColor("#7f8c8d"), 1))
            p.drawEllipse(int(ax - r), int(ay - r), int(2 * r), int(2 * r))
            p.fillRect(int(ax - 2), int(ay - 2), 4, 4, QColor("#7f8c8d"))

        # Crease + net
        if x1 >= 189:
            ax, ay = f(189, 42.5)
            r = 6 / (x1 - x0) * (w - 28)
            p.setPen(QPen(Qt.NoPen))
            p.setBrush(QBrush(QColor("#3d6b8c")))
            p.drawPie(int(ax - r), int(ay - r), int(2 * r), int(2 * r),
                      270 * 16, 180 * 16)
            nx, _ = f(190.5, 42.5)
            p.setBrush(QBrush(QColor("#ef4444")))
            p.drawRect(int(nx - 3), int(ay - 8), 6, 16)

        # Shots
        outcome_colors = {
            "goal": "#22c55e", "save": "#3B82F6",
            "blocked": "#7f8c8d", "block": "#7f8c8d",
            "disallowed": "#f1c40f", "miss": "#ecf0f1",
            "pending": "#ecf0f1",
        }
        for s in self._shots:
            try:
                x = float(s.get("x", 160))
                y = float(s.get("y", 42.5))
                cx, cy = f(x, y)
                r = 3 + float(s.get("xg", 0) or 0) * 14
                outcome = str(s.get("outcome", ""))
                col = outcome_colors.get(outcome, "#ecf0f1")
                if outcome == "disallowed":
                    p.setPen(QPen(QColor(col), 2))
                    p.setBrush(QBrush(Qt.NoBrush))
                    p.drawEllipse(int(cx - r), int(cy - r),
                                  int(2 * r), int(2 * r))
                else:
                    p.setPen(QPen(Qt.NoPen))
                    p.setBrush(QBrush(QColor(col)))
                    p.drawEllipse(int(cx - r), int(cy - r),
                                  int(2 * r), int(2 * r))
                if outcome == "goal":
                    p.setPen(QPen(QColor("#f1c40f"), 2))
                    p.setBrush(QBrush(Qt.NoBrush))
                    p.drawEllipse(int(cx - r - 2), int(cy - r - 2),
                                  int(2 * r + 4), int(2 * r + 4))
            except Exception:
                continue

        # Zone entries
        type_colors = {
            "CONTROLLED_CARRY": "#22c55e",
            "DUMP_IN": "#e67e22",
            "CONTROLLED_PASS": "#3B82F6",
        }
        for e in self._entries:
            try:
                x = float(e.get("x", 125))
                y = float(e.get("y", 42.5))
                cx, cy = f(x, y)
                col = type_colors.get(str(e.get("type", "")), "#7f8c8d")
                p.setPen(QPen(Qt.NoPen))
                p.setBrush(QBrush(QColor(col)))
                p.drawEllipse(int(cx - 4), int(cy - 4), 8, 8)
            except Exception:
                continue


class MomentumWidget(QWidget):
    """QPainter momentum graph. Points are dicts with period, time,
    value (-3..+3, positive = viewed team's momentum), trigger."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pts = []
        self.setMinimumSize(640, 280)

    def set_points(self, pts):
        self._pts = list(pts or [])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0d1626"))

        pts = self._pts
        if not pts:
            p.setPen(QColor("#6b7488"))
            p.drawText(20, h // 2, "No momentum shifts tracked this game.")
            return

        pad, mid = 30, h // 2
        step = h / 2 / 3.4

        # Zero line
        p.setPen(QPen(QColor("#3a4a55"), 1))
        p.drawLine(pad, mid, w - pad, mid)

        n = len(pts)
        xs = [pad + i / max(n - 1, 1) * (w - 2 * pad) for i in range(n)]
        ys = [mid - pt["value"] * step for pt in pts]

        # Period separators
        prev_period = pts[0]["period"]
        for i in range(1, n):
            if pts[i]["period"] != prev_period:
                p.setPen(QPen(QColor("#3a4a55"), 1, Qt.DashLine))
                p.drawLine(int(xs[i]), 10, int(xs[i]), h - 10)
                p.setPen(QColor("#6b7488"))
                p.drawText(int(xs[i]) + 4, 18, f"P{pts[i]['period']}")
                prev_period = pts[i]["period"]

        # Line segments (green = our momentum, red = theirs)
        for i in range(1, n):
            col = "#22c55e" if ys[i] <= mid else "#ef4444"
            p.setPen(QPen(QColor(col), 2))
            p.drawLine(int(xs[i - 1]), int(ys[i - 1]),
                       int(xs[i]), int(ys[i]))

        # Points
        for i, pt in enumerate(pts):
            col = "#22c55e" if pt["value"] >= 0 else "#ef4444"
            p.setPen(QPen(Qt.NoPen))
            p.setBrush(QBrush(QColor(col)))
            p.drawEllipse(int(xs[i]) - 3, int(ys[i]) - 3, 6, 6)

        # Annotate the 3 biggest swings
        p.setPen(QColor("#6b7488"))
        swings = sorted(range(1, n),
                        key=lambda i: abs(ys[i] - ys[i - 1]),
                        reverse=True)[:3]
        for i in swings:
            trig = str(pts[i].get("trigger", "")).replace("_", " ")
            if trig:
                y = max(int(ys[i]) - 14, 12)
                p.drawText(int(xs[i]) - 40, y, 120, 14,
                           Qt.AlignCenter, trig[:24])


class AnalyticsScreen(BaseScreen):
    """Analytics Hub: shot/xG maps, momentum graphs, zone entries,
    line trends, and Ask the Analyst."""

    title = "Analytics Hub"

    def _build_body(self):
        # Top bar: game selector + summary
        top = QHBoxLayout()
        self._layout.addLayout(top)

        self._game_label = QLabel("No games recorded yet")
        self._game_label.setObjectName("sub-header")
        top.addWidget(self._game_label)
        top.addStretch()

        self._game_combo = QComboBox()
        self._game_combo.setMinimumWidth(260)
        self._game_combo.currentIndexChanged.connect(self._on_game_changed)
        top.addWidget(self._game_combo)

        # Tabs
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs, 1)

        self._tab_names = ["Shots & xG", "Momentum", "Zone Entries",
                           "Lines", "Ask the Analyst"]
        for name in self._tab_names:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setSpacing(12)
            scroll.setWidget(container)
            self._tabs.addTab(scroll, name)
            setattr(self, f"_layout_{self._tab_key(name)}", layout)

        self._game_idx = -1
        self.refresh()

    @staticmethod
    def _tab_key(name):
        return name.lower().replace(" & ", "_").replace(" ", "_")

    def _team(self):
        return _safe(lambda: self.game.user_team)

    def _games(self):
        team = self._team()
        if team is None:
            return []
        return _safe(lambda: _team_games(team), []) or []

    # -- refresh -------------------------------------------------------------
    def refresh(self):
        team = self._team()
        games = self._games()
        name = _safe(lambda: team.team_name, "?") if team else "?"

        # Populate game selector
        self._game_combo.blockSignals(True)
        self._game_combo.clear()
        for g in games:
            self._game_combo.addItem(_game_label(g, name))
        self._game_combo.blockSignals(False)

        if not games:
            self._game_idx = -1
            self._game_label.setText("No games recorded yet")
            for tab_name in self._tab_names:
                layout = getattr(self, f"_layout_{self._tab_key(tab_name)}")
                self._clear_layout(layout)
                lbl = QLabel("Play a game and the hub will light up.")
                lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
                lbl.setAlignment(Qt.AlignCenter)
                layout.addWidget(lbl)
            return

        if self._game_idx < 0 or self._game_idx >= len(games):
            self._game_idx = len(games) - 1
        self._game_combo.setCurrentIndex(self._game_idx)
        rec = games[self._game_idx]
        self._game_label.setText(
            f"{name} · {_game_label(rec, name)}")

        self._render_shots(rec, name)
        self._render_momentum(rec, name)
        self._render_entries(rec, name)
        self._render_lines(rec, name, team)
        self._render_analyst(team)

    def _on_game_changed(self, idx):
        if idx < 0:
            return
        self._game_idx = idx
        self.refresh()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                self._clear_layout(sub)

    def _card(self, parent_layout, title):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        parent_layout.addWidget(group)
        return layout

    def _legend(self, parent_layout, items):
        """items: [(label, color_hex), ...]"""
        row = QHBoxLayout()
        for label, color in items:
            lbl = QLabel(f"● {label}")
            lbl.setStyleSheet(f"color: {color}; font-size: 13px;")
            row.addWidget(lbl)
        row.addStretch()
        parent_layout.addLayout(row)

    def _make_table(self, headers, rows):
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()
        return table

    # -- Shots & xG ------------------------------------------------------------
    def _render_shots(self, rec, name):
        layout = self._layout_shots_xg
        self._clear_layout(layout)
        shots = _shots_for(rec, name)
        xg, goals = _team_xg(shots)

        card = self._card(layout,
                          f"Shot map · {_game_label(rec, name)}")
        card.addWidget(QLabel(
            f"{len(shots)} shots · {xg:.2f} xG · {goals} goals"))
        rink = RinkMapWidget()
        rink.set_shots(shots)
        card.addWidget(rink)
        self._legend(card, [("Goal", "#22c55e"), ("Save", "#3B82F6"),
                            ("Blocked", "#7f8c8d"),
                            ("Disallowed", "#f1c40f")])
        note = QLabel("Dot size = chance quality (xG). "
                      "All shots shown attacking right.")
        note.setStyleSheet("color: #6b7488; font-size: 12px;")
        card.addWidget(note)

        # Player xG table
        card2 = self._card(layout,
                           "Chance creation by player (engine xG)")
        rows = _player_xg_rows(shots)
        card2.addWidget(self._make_table(
            ["Player", "Shots", "xG", "Goals", "G-xG"],
            [[r["shooter"], r["shots"], f"{r['xg']:.2f}",
              r["goals"], f"{r['diff']:+.2f}"] for r in rows[:14]]))

        # Grade breakdown
        card3 = self._card(layout, "xG by chance grade")
        grows = _grade_xg_rows(shots)
        card3.addWidget(self._make_table(
            ["Grade", "Shots", "xG", "Goals", "Conv", "G-xG"],
            [[r["grade"], r["shots"], f"{r['xg']:.2f}", r["goals"],
              f"{r['conv']:.3f}", f"{r['diff']:+.2f}"] for r in grows]))

        # Per-player grade profile
        card4 = self._card(layout,
                           "Shot quality profile by player (A/B/C grade)")
        pgrows = _player_grade_xg_rows(shots)
        card4.addWidget(self._make_table(
            ["Player", "Shots", "A", "B", "C", "A-share", "xG", "G-xG"],
            [[r["shooter"], r["shots"], r["a_shots"], r["b_shots"],
              r["c_shots"], f"{r['a_share']:.3f}", f"{r['xg']:.2f}",
              f"{r['diff']:+.2f}"] for r in pgrows[:14]]))

    # -- Momentum ----------------------------------------------------------------
    def _render_momentum(self, rec, name):
        layout = self._layout_momentum
        self._clear_layout(layout)
        pts = _momentum_points(rec, name)

        card = self._card(layout,
                          f"Momentum · {_game_label(rec, name)}")
        if not pts:
            lbl = QLabel("No momentum shifts tracked this game.")
            lbl.setStyleSheet("color: #6b7488;")
            card.addWidget(lbl)
            return
        card.addWidget(QLabel(
            "Positive = your momentum. Ticks mark what moved it."))
        mom = MomentumWidget()
        mom.set_points(pts)
        card.addWidget(mom)

        vals = [p["value"] for p in pts]
        card2 = self._card(layout, "Game flow")
        card2.addWidget(QLabel(
            f"Shifts tracked: {len(pts)} · biggest swing: "
            f"{max(vals) - min(vals):+d} steps · finished {vals[-1]:+d}."))

    # -- Zone entries --------------------------------------------------------------
    def _render_entries(self, rec, name):
        layout = self._layout_zone_entries
        self._clear_layout(layout)
        entries = _entries_for(rec, name)
        eb = _entry_breakdown(entries)

        card = self._card(layout,
                          f"Zone entries · {_game_label(rec, name)}")
        card.addWidget(QLabel(
            f"{eb['total']} successful entries · "
            f"{eb['controlled_pct']:.0f}% controlled"))
        rink = RinkMapWidget(x_range=(0.0, 200.0), full_rink=True)
        rink.set_entries(entries)
        card.addWidget(rink)
        self._legend(card, [("Carry-in", "#22c55e"),
                            ("Dump-in", "#e67e22"),
                            ("Pass entry", "#3B82F6")])

        if eb["counts"]:
            card2 = self._card(layout, "Entry mix")
            card2.addWidget(self._make_table(
                ["Type", "Count"],
                [[t.replace("_", " ").title(), c]
                 for t, c in sorted(eb["counts"].items(),
                                    key=lambda kv: -kv[1])]))

    # -- Lines -----------------------------------------------------------------------
    def _render_lines(self, rec, name, team):
        layout = self._layout_lines
        self._clear_layout(layout)
        shots = _shots_for(rec, name)
        rows = _line_xg_rows(shots, rec.get("lines"))

        card = self._card(layout,
                          f"Line trends · {_game_label(rec, name)}")
        if not rows:
            lbl = QLabel("No line data this game.")
            lbl.setStyleSheet("color: #6b7488;")
            card.addWidget(lbl)
        else:
            card.addWidget(self._make_table(
                ["Line", "Shots", "xG", "Goals", "G-xG", "Chemistry"],
                [[r["line"], r["shots"], f"{r['xg']:.2f}", r["goals"],
                  f"{r['diff']:+.2f}", r["chemistry"]] for r in rows]))
            note = QLabel("Chemistry is the engine's live line-chemistry "
                          "rating for this game.")
            note.setStyleSheet("color: #6b7488; font-size: 12px;")
            card.addWidget(note)

        # Rolling trends
        trends = _rolling_line_trends(team, n=5)
        games5 = _team_games(team)[-5:]
        labels = [_game_label(g, name).split(" · ")[0]
                  for g in games5]
        card2 = self._card(layout, "Rolling xG by line (last 5 games)")
        card2.addWidget(self._make_table(
            ["Line"] + labels,
            [[line] + [f"{xg:.1f}" for _, xg in trends[line]]
             for line in ("L1", "L2", "L3", "L4") if line in trends]))

        # Assist pairs (line-combination effectiveness)
        name_lookup = {}
        if team is not None:
            for t in _safe(lambda: self.game.league.teams, []) or []:
                for p in _safe(lambda: t.roster, []) or []:
                    pid = _safe(lambda: p.player_id)
                    pname = _safe(lambda: p.name)
                    if pid and pname:
                        name_lookup[str(pid)] = pname
        pairs = _assist_pair_rows(self._games(), name_lookup)
        if pairs:
            card3 = self._card(layout,
                               "Top line combinations (assist pairs)")
            card3.addWidget(self._make_table(
                ["Passer", "Scorer", "Goals"],
                [[r["passer"], r["scorer"], r["goals"]] for r in pairs]))

    # -- Ask the analyst -----------------------------------------------------------------
    def _render_analyst(self, team):
        layout = self._layout_ask_the_analyst
        self._clear_layout(layout)
        sections = _analyst_report(team)
        for heading_text, lines in sections:
            card = self._card(layout, heading_text)
            for ln in lines:
                lbl = QLabel("•  " + ln)
                lbl.setWordWrap(True)
                card.addWidget(lbl)

        # Refresh button
        refresh_btn = QPushButton("Refresh analysis")
        refresh_btn.clicked.connect(lambda: self.refresh())
        layout.addWidget(refresh_btn)
        layout.addStretch()
