"""Calendar: month-grid view of the season schedule (read-only).

Port of web_ui/screens/calendar.py. Prev/next month buttons with
year rollover; the month grid is built in code (padding cells,
per-day game counts, event markers for the trade deadline, entry
draft, opening night, and season end). A deadline countdown banner
sits above the grid.
"""
import calendar as _cal
from datetime import date, datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
    QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _league(game):
    return _safe(lambda: _gm(game).league)


def _iso(d):
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if d is None:
        return ""
    return _safe(lambda: str(d), "") or ""


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November",
           "December"]

_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


class CalendarScreen(BaseScreen):
    """Month calendar with per-day game counts and event markers."""

    title = "Calendar"

    def _build_body(self):
        # deadline countdown banner
        self._banner = QFrame()
        self._banner.setObjectName("tile")
        bl = QHBoxLayout(self._banner)
        self._banner_tag = QLabel("")
        self._banner_tag.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #e8b34b;")
        self._banner_text = QLabel("")
        self._banner_text.setStyleSheet(
            "color: #cdd6e4; font-size: 13px;")
        self._banner_text.setWordWrap(True)
        self._banner_btn = QPushButton("Open Deadline Center →")
        self._banner_btn.clicked.connect(self._open_deadline)
        bl.addWidget(self._banner_tag)
        bl.addWidget(self._banner_text, 1)
        bl.addWidget(self._banner_btn)
        self._banner.setVisible(False)
        self._layout.addWidget(self._banner)

        # month nav header
        head = QHBoxLayout()
        self._prev_btn = QPushButton("‹")
        self._prev_btn.setFixedWidth(48)
        self._prev_btn.clicked.connect(lambda: self._shift_month(-1))
        self._next_btn = QPushButton("›")
        self._next_btn.setFixedWidth(48)
        self._next_btn.clicked.connect(lambda: self._shift_month(1))
        self._title_lbl = QLabel("—")
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setStyleSheet(
            "font-size: 24px; font-weight: 800;")
        kicker = QLabel("SEASON")
        kicker.setAlignment(Qt.AlignCenter)
        kicker.setStyleSheet(
            "color: #9aa4b8; font-size: 12px; letter-spacing: 2px;")
        titlebox = QVBoxLayout()
        titlebox.addWidget(kicker)
        titlebox.addWidget(self._title_lbl)
        head.addWidget(self._prev_btn)
        head.addLayout(titlebox, 1)
        head.addWidget(self._next_btn)
        self._layout.addLayout(head)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setAlignment(Qt.AlignCenter)
        self._sub_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(self._sub_lbl)

        # legend
        legend = QHBoxLayout()
        legend.addStretch()
        for dot_color, txt in (("#3B82F6", "Your team"),
                              ("#e8b34b", "Today")):
            dl = QLabel(f'<span style="color:{dot_color}">●</span> {txt}')
            dl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            legend.addWidget(dl)
        pre = QLabel('<span style="color:#9aa4b8">PRE</span> Preseason')
        pre.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        legend.addWidget(pre)
        legend.addStretch()
        self._layout.addLayout(legend)

        # weekday header
        wd_row = QGridLayout()
        wd_row.setSpacing(4)
        for i, d_ in enumerate(_WEEKDAYS):
            wl = QLabel(d_)
            wl.setAlignment(Qt.AlignCenter)
            wl.setStyleSheet(
                "color: #9aa4b8; font-size: 12px; font-weight: 700;")
            wd_row.addWidget(wl, 0, i)
        self._layout.addLayout(wd_row)

        # month grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(4)
        self._grid.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._grid_host)
        self._layout.addWidget(scroll, 1)

        # view state
        self._view_year = 0
        self._view_month = 0  # 0-11
        self._today_iso = ""
        self._my_name = ""
        self._games_by_date = {}
        self._events_by_date = {}

    # ------------------------------------------------------------------
    def _open_deadline(self):
        try:
            self.navigate_to("deadline")
        except Exception as e:
            self._banner_text.setText(
                "Deadline Center is not registered in this build.")

    def _shift_month(self, delta):
        m = self._view_month + delta
        y = self._view_year
        while m < 0:
            m += 12
            y -= 1
        while m > 11:
            m -= 12
            y += 1
        self._view_month, self._view_year = m, y
        self._render_grid()

    # ------------------------------------------------------------------
    def _load_data(self):
        gm = _gm(self.game)
        team = (_safe(lambda: gm.user_team)
                or _safe(lambda: getattr(self.game, "user_team", None)))
        self._my_name = (_safe(lambda: team.team_name, "") or "") if team \
            else ""
        today = _safe(lambda: gm.current_date)
        self._today_iso = _iso(today)
        if not self._today_iso:
            self._today_iso = date.today().isoformat()

        games = {}
        league = _league(self.game)
        raw = _safe(lambda: list(getattr(league, "schedule", None)
                                 or []), []) or []
        for g in raw:
            try:
                if not isinstance(g, dict):
                    continue
                home = _team_name(g.get("home_team"))
                away = _team_name(g.get("away_team"))
                gd = _iso(g.get("date"))
                if not gd:
                    continue
                mine = bool(self._my_name) and self._my_name in (home, away)
                games.setdefault(gd, []).append({
                    "home": home, "away": away, "mine": mine,
                    "is_home": bool(mine) and home == self._my_name,
                    "opponent": (away if home == self._my_name
                                 else (home if mine else "")),
                    "preseason": bool(g.get("preseason", False)),
                })
            except Exception:
                continue
        self._games_by_date = games

        events = {}
        # trade deadline
        try:
            from trade_deadline_manager import trade_deadline_date
            dd = trade_deadline_date(league)
            if dd:
                events.setdefault(dd.isoformat(), []).append({
                    "kind": "deadline", "label": "Trade Deadline"})
        except Exception:
            pass
        # entry draft (late June)
        try:
            session = _safe(lambda: getattr(league, "entry_draft_session",
                                           None))
            dyear = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
            if not dyear:
                dyear = _safe(lambda: int(
                    getattr(league, "season_year", 0) or 0), 0) + 1
            if dyear:
                events.setdefault(f"{dyear}-06-28", []).append(
                    {"kind": "draft", "label": f"{dyear} Entry Draft"})
        except Exception:
            pass
        # season bounds from the regular-season schedule
        try:
            dates = sorted(gd for gd, gs in games.items()
                           if gd and not any(x["preseason"] for x in gs))
            if dates:
                events.setdefault(dates[0], []).append(
                    {"kind": "season", "label": "Opening Night"})
                if dates[-1] != dates[0]:
                    events.setdefault(dates[-1], []).append(
                        {"kind": "season", "label": "Regular Season Ends"})
        except Exception:
            pass
        self._events_by_date = events

    def _render_banner(self):
        league = _league(self.game)
        if league is None:
            self._banner.setVisible(False)
            return
        try:
            from trade_deadline_manager import trade_deadline_date
            dd = trade_deadline_date(league)
        except Exception:
            dd = None
        if not dd:
            self._banner.setVisible(False)
            return
        gm = _gm(self.game)
        today = _safe(lambda: gm.current_date)
        try:
            today = today.date() if isinstance(today, datetime) else today
        except Exception:
            today = None
        days_left = (dd - today).days if today else None
        is_today = bool(today and dd == today)
        passed = days_left is not None and days_left < 0
        if is_today:
            self._banner.setVisible(True)
            self._banner_tag.setText("DEADLINE DAY")
            self._banner_text.setText(
                "Deals lock at 3 PM ET today.")
        elif not passed and days_left is not None:
            self._banner.setVisible(True)
            self._banner_tag.setText("TRADE DEADLINE")
            label = dd.strftime("%B %d, %Y")
            self._banner_text.setText(
                f"{label} — {days_left} day"
                f"{'' if days_left == 1 else 's'} away")
        else:
            self._banner.setVisible(False)

    def _render_grid(self):
        # clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        year, month = self._view_year, self._view_month
        self._title_lbl.setText(f"{_MONTHS[month]} {year}")
        prefix = f"{year:04d}-{month + 1:02d}-"
        mine_this_month = sum(
            1 for gd, gs in self._games_by_date.items()
            if gd.startswith(prefix) for g in gs if g["mine"])
        sub = (f"{self._my_name} · " if self._my_name else "")
        sub += f"{mine_this_month} game{'s' if mine_this_month != 1 else ''} this month"
        self._sub_lbl.setText(sub)

        first = _cal.monthrange(year, month + 1)[0]  # 0 = Monday
        first = (first + 1) % 7  # shift to Sun-first
        days = _cal.monthrange(year, month + 1)[1]
        row = 0
        col = first
        for d_ in range(1, days + 1):
            iso = f"{year:04d}-{month + 1:02d}-{d_:02d}"
            games = self._games_by_date.get(iso, [])
            events = self._events_by_date.get(iso, [])
            cell = self._day_cell(d_, iso, games, events)
            self._grid.addWidget(cell, row, col)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _day_cell(self, day_num, iso, games, events):
        cell = QFrame()
        cell.setObjectName("tile")
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(6, 6, 6, 6)
        cl.setSpacing(2)
        dl = QLabel(str(day_num))
        style = "font-size: 13px; font-weight: 700; color: #cdd6e4;"
        if iso == self._today_iso:
            style = ("font-size: 13px; font-weight: 800; color: #111827; "
                     "background: #e8b34b; border-radius: 10px; "
                     "padding: 1px 6px;")
            dl.setAlignment(Qt.AlignLeft)
        dl.setStyleSheet(style)
        cl.addWidget(dl)
        mine = [g for g in games if g["mine"]]
        others = [g for g in games if not g["mine"]]
        if mine:
            gl = QLabel(f"{len(mine)} game{'s' if len(mine) != 1 else ''}")
            gl.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #3B82F6;")
            cl.addWidget(gl)
            for g in mine[:2]:
                ol = QLabel(
                    f"{'vs' if g['is_home'] else '@'} {g['opponent'] or g['away']}"
                    + (" (PRE)" if g["preseason"] else ""))
                ol.setStyleSheet("font-size: 10px; color: #9aa4b8;")
                cl.addWidget(ol)
        elif games:
            gl = QLabel(f"{len(games)} league")
            gl.setStyleSheet("font-size: 11px; color: #6b7488;")
            cl.addWidget(gl)
        for ev in events:
            kind = ev.get("kind", "")
            icon = {"deadline": "\u23F0", "draft": "\U0001F3AF",
                    "season": "\U0001F3C1"}.get(kind, "\u2022")
            el = QLabel(f"{icon} {ev.get('label', '')}")
            el.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #e8b34b;")
            el.setWordWrap(True)
            cl.addWidget(el)
        cl.addStretch()
        return cell

    # ------------------------------------------------------------------
    def refresh(self):
        self._load_data()
        if not self._view_year:
            m = self._today_iso[:7]
            try:
                self._view_year = int(m[:4])
                self._view_month = int(m[5:7]) - 1
            except Exception:
                t = date.today()
                self._view_year, self._view_month = t.year, t.month - 1
        self._render_banner()
        self._render_grid()
