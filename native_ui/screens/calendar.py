"""Calendar: month-grid view of the season schedule.

Port of web_ui/screens/calendar.py. Prev/next month buttons with
year rollover; the month grid is built in code (padding cells,
per-day game counts, event markers for the trade deadline, entry
draft, opening night, and season end). A deadline countdown banner
sits above the grid. Clicking a day opens a details dialog listing
that day's games with teams, scores, and status.

Mainline parity (calendar_window.py): the month grid also surfaces
mainline's marquee events (NHL special events stamped on the
schedule, jersey-retirement ceremonies, the Olympic window, break
days, and fixed league dates) with mainline's marker priority, and
the day-detail dialog enriches user-team games with team form and
the season series. Event markers in the grid are clickable:
deadline/draft markers navigate to the Deadline Center / Draft Day
Central, other markers open the day-detail dialog.
"""
import calendar as _cal
from datetime import date, datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
    QPushButton, QScrollArea, QDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from .base import BaseScreen
from .schedule import _game_played_state, _results_by_date
from native_ui.safe import safe_call


def _gm(game):
    return safe_call(lambda: getattr(game, "game_manager", None),
                     context="calendar/gm") or game


def _league(game):
    return safe_call(lambda: _gm(game).league, context="calendar/league")


def _iso(d):
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if d is None:
        return ""
    return safe_call(lambda: str(d), "", context="calendar/iso") or ""


def _team_name(t):
    if isinstance(t, str):
        return t
    return safe_call(lambda: getattr(t, "team_name", str(t)), "?",
                     context="calendar/team_name") or "?"


_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November",
           "December"]

_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _game_status(g, iso, today_iso):
    """Human status line for one game: Final (+OT/SO), Today, Scheduled."""
    if g.get("played"):
        s = "Final"
        if g.get("shootout"):
            s += " (SO)"
        elif g.get("overtime"):
            s += " (OT)"
    elif iso == today_iso:
        s = "Today"
    else:
        s = "Scheduled"
    if g.get("preseason"):
        s += " · Preseason"
    return s


class _DayCell(QFrame):
    """Calendar day cell that emits ``day_clicked`` on left-click."""

    day_clicked = Signal(str)

    def __init__(self, iso, parent=None):
        super().__init__(parent)
        self._iso = iso
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        try:
            if event is not None and event.button() == Qt.LeftButton:
                self.day_clicked.emit(self._iso)
        except Exception:
            pass
        super().mousePressEvent(event)


class _DayDetailDialog(QDialog):
    """Modal showing every game scheduled on one calendar day.

    Mirrors the DailyResultsDialog layout (dialog-title, date header,
    scrollable game cards, Close button). Games come from the real
    league schedule; an empty day shows "No games scheduled".

    Event markers (trade deadline, entry draft) are clickable and
    navigate to the Deadline Center / Draft Day Central. Team names
    in game cards are clickable and open the team page. User-team
    games are enriched with team form (last 5) and the season series
    vs the opponent, from real results and the schedule (mainline
    parity with calendar_window._insert_game_details).
    """

    def __init__(self, iso_date, games, events, my_name, today_iso,
                 parent=None, main_window=None, games_by_date=None):
        super().__init__(parent)
        self._iso = str(iso_date or "")
        self._today_iso = today_iso or ""
        self._main_window = main_window
        self._games_by_date = games_by_date or {}
        self._cards = []
        self._event_labels = []
        self._empty_label = None

        self.setWindowTitle("Day Details")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)

        self._title_label = QLabel("DAY DETAILS")
        self._title_label.setObjectName("dialog-title")
        layout.addWidget(self._title_label)

        self._date_label = QLabel(self._format_date(self._iso))
        self._date_label.setStyleSheet("color: #8b95ab; font-size: 13px;")
        layout.addWidget(self._date_label)

        for ev in events or []:
            kind = ev.get("kind", "") if isinstance(ev, dict) else ""
            icon = {"deadline": "\u23F0", "draft": "\U0001F3AF",
                    "season": "\U0001F3C1"}.get(kind, "\u2022")
            label = ev.get("label", "") if isinstance(ev, dict) else ""
            # Deadline/draft events get action buttons; others are labels.
            target = {"deadline": "deadline",
                      "draft": "draft_central"}.get(kind)
            if target and self._main_window is not None:
                btn = QPushButton(f"{icon} {label}  →")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton { font-size: 13px; font-weight: 700; "
                    "color: #e8b34b; background: transparent; border: none; "
                    "text-align: left; padding: 2px; } "
                    "QPushButton:hover { color: #f5c86e; "
                    "text-decoration: underline; }")
                btn.clicked.connect(
                    lambda _c=False, t=target: self._goto(t))
                layout.addWidget(btn)
                self._event_labels.append(btn)
            else:
                el = QLabel(f"{icon} {label}")
                el.setStyleSheet(
                    "font-size: 13px; font-weight: 700; color: #e8b34b;")
                el.setWordWrap(True)
                layout.addWidget(el)
                self._event_labels.append(el)

        # Scrollable game list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll, 1)

        games_widget = QWidget()
        games_layout = QVBoxLayout(games_widget)
        games_layout.setSpacing(8)
        scroll.setWidget(games_widget)

        if not games:
            self._empty_label = QLabel("No games scheduled")
            self._empty_label.setAlignment(Qt.AlignCenter)
            self._empty_label.setStyleSheet(
                "color: #6b7488; font-size: 14px;")
            games_layout.addWidget(self._empty_label)
        else:
            for g in games:
                games_layout.addWidget(self._make_game_card(g))
        games_layout.addStretch()

        # Day enrichment (mainline parity): team form + season series
        # for each distinct opponent the user team faced this day.
        mine_games = [g for g in (games or [])
                      if g.get("mine") and g.get("opponent")]
        seen_opps = []
        for g in mine_games:
            if g["opponent"] not in seen_opps:
                seen_opps.append(g["opponent"])
        for opp in seen_opps:
            games_layout.addWidget(self._make_enrichment(opp))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary-btn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _format_date(iso):
        try:
            return date.fromisoformat(str(iso)[:10]).strftime(
                "%A, %B %d, %Y")
        except Exception:
            return str(iso or "Unknown date")

    def _goto(self, screen_name):
        """Navigate to a screen and close this dialog."""
        try:
            if self._main_window is not None:
                self.accept()
                self._main_window.show_screen(screen_name)
        except Exception:
            pass

    def _open_team(self, team_name):
        """Open a team page and close this dialog."""
        try:
            if self._main_window is not None and team_name:
                self.accept()
                self._main_window.open_team(team_name)
        except Exception:
            pass

    def _team_link(self, team_name):
        """Clickable team-name button styled as a link."""
        btn = QPushButton(str(team_name or "?"))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { font-size: 15px; font-weight: 700; "
            "color: #ffffff; background: transparent; border: none; "
            "padding: 0px; } "
            "QPushButton:hover { color: #3B82F6; "
            "text-decoration: underline; }")
        btn.clicked.connect(
            lambda _c=False, t=str(team_name or ""): self._open_team(t))
        return btn

    # ------------------------------------------------------------------
    # Day-detail enrichment (port of mainline calendar_window.py:
    # _recent_form_lines, _describe_user_result, _season_series_lines).
    # ------------------------------------------------------------------
    def _user_played_games(self):
        """Played user-team games, oldest first, from the real schedule."""
        out = []
        for iso in sorted(self._games_by_date):
            for g in self._games_by_date[iso]:
                try:
                    if g.get("mine") and g.get("played"):
                        out.append((iso, g))
                except Exception:
                    continue
        return out

    @staticmethod
    def _describe_game(iso, g):
        """Return (outcome, summary line) for a played user-team game.

        Outcome is 'W', 'L' or 'T'. Returns None when the scores are
        missing or malformed.
        """
        try:
            is_home = bool(g.get("is_home"))
            us = g.get("home_score") if is_home else g.get("away_score")
            them = g.get("away_score") if is_home else g.get("home_score")
            if us is None or them is None:
                return None
            outcome = "W" if us > them else ("L" if us < them else "T")
            try:
                when = date.fromisoformat(str(iso)[:10]).strftime("%b %d")
            except Exception:
                when = str(iso)
            venue = "vs" if is_home else "@"
            opp = g.get("opponent") or g.get("away") or "?"
            return outcome, f"{when}: {outcome} {us}-{them} {venue} {opp}"
        except Exception:
            return None

    def _recent_form_lines(self):
        """Last-5 form lines plus record and streak, from real results."""
        played = self._user_played_games()
        if not played:
            return ["No games played yet this season."]
        described = [d for d in
                     (self._describe_game(i, g) for i, g in played[-5:])
                     if d]
        if not described:
            return ["No games played yet this season."]
        lines = [f"  {text}" for _outcome, text in described]
        w = sum(1 for o, _ in described if o == "W")
        l = sum(1 for o, _ in described if o == "L")
        lines.append(f"  Last 5: {w}-{l}")
        # Current streak (walk back from the most recent result).
        streak_outcome, streak_n = None, 0
        for iso, g in reversed(played):
            d = self._describe_game(iso, g)
            if not d or d[0] == "T":
                break
            if streak_outcome is None:
                streak_outcome = d[0]
            if d[0] == streak_outcome:
                streak_n += 1
            else:
                break
        if streak_outcome:
            lines.append(f"  Streak: {streak_outcome}{streak_n}")
        return lines

    def _season_series_lines(self, opponent):
        """Season series vs an opponent: results plus upcoming meetings."""
        lines = []
        meetings = [(i, g) for i, g in self._user_played_games()
                    if g.get("opponent") == opponent]
        described = [d for d in
                     (self._describe_game(i, g) for i, g in meetings) if d]
        if not described:
            lines.append("First meeting this season.")
        else:
            w = sum(1 for o, _ in described if o == "W")
            l = sum(1 for o, _ in described if o == "L")
            lines.append(f"Series record: {w}-{l}")
            for _outcome, text in described:
                lines.append(f"  {text}")
        # Upcoming meetings from the schedule.
        upcoming = []
        for iso in sorted(self._games_by_date):
            if iso <= self._iso:
                continue
            for g in self._games_by_date[iso]:
                try:
                    if (g.get("mine") and g.get("opponent") == opponent
                            and not g.get("played")):
                        venue = "vs" if g.get("is_home") else "@"
                        try:
                            when = date.fromisoformat(
                                str(iso)[:10]).strftime("%b %d")
                        except Exception:
                            when = str(iso)
                        upcoming.append(f"{when}: {venue} {opponent}")
                        break  # one line per day
                except Exception:
                    continue
        if upcoming:
            lines.append("Upcoming: " + "; ".join(upcoming[:4]))
        else:
            lines.append("No further meetings scheduled.")
        return lines

    def _make_enrichment(self, opponent):
        """Team Form (Last 5) + Season Series vs an opponent."""
        box = QFrame()
        box.setObjectName("tile")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(2)
        fh = QLabel("Team Form (Last 5)")
        fh.setStyleSheet("font-size: 13px; font-weight: 800; color: #e8b34b;")
        bl.addWidget(fh)
        for line in self._recent_form_lines():
            fl = QLabel(line)
            fl.setStyleSheet("font-size: 12px; color: #cdd6e4;")
            bl.addWidget(fl)
        sh = QLabel(f"Season Series vs {opponent}")
        sh.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #e8b34b; "
            "margin-top: 6px;")
        sh.setWordWrap(True)
        bl.addWidget(sh)
        for line in self._season_series_lines(opponent):
            sl = QLabel(line)
            sl.setStyleSheet("font-size: 12px; color: #cdd6e4;")
            sl.setWordWrap(True)
            bl.addWidget(sl)
        return box

    def _make_game_card(self, g):
        card = QFrame()
        card.setObjectName("tile")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        mine = bool(g.get("mine"))
        # Clickable team names (away @ home).
        matchup_row = QHBoxLayout()
        matchup_row.setSpacing(4)
        matchup_row.setContentsMargins(0, 0, 0, 0)
        away_btn = self._team_link(g.get("away", "?"))
        at_lbl = QLabel("@")
        at_lbl.setStyleSheet("font-size: 15px; color: #9aa4b8;")
        home_btn = self._team_link(g.get("home", "?"))
        if mine:
            for b in (away_btn, home_btn):
                b.setStyleSheet(
                    "QPushButton { font-size: 15px; font-weight: 700; "
                    "color: #3B82F6; background: transparent; border: none; "
                    "padding: 0px; } "
                    "QPushButton:hover { text-decoration: underline; }")
        matchup_row.addWidget(away_btn)
        matchup_row.addWidget(at_lbl)
        matchup_row.addWidget(home_btn)
        matchup_row.addStretch()
        layout.addLayout(matchup_row)

        status = _game_status(g, self._iso, self._today_iso)
        if g.get("played"):
            score_txt = (f"{g.get('away_score', '?')} – "
                         f"{g.get('home_score', '?')}  ·  {status}")
        else:
            score_txt = status
        score = QLabel(score_txt)
        score.setStyleSheet("font-size: 13px; color: #9aa4b8;")
        layout.addWidget(score)

        self._cards.append(
            {"matchup_row": matchup_row, "score": score, "mine": mine})
        return card


class CalendarScreen(BaseScreen):
    """Month calendar with per-day game counts and event markers.

    Clicking a day opens a details panel with that day's games
    (teams, scores, status) from the real league schedule.
    """

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
        hint = QLabel("Click a day for details")
        hint.setStyleSheet(
            "color: #6b7488; font-size: 12px; font-style: italic;")
        legend.addWidget(hint)
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
        self._selected_iso = ""

    # ------------------------------------------------------------------
    def _open_team_page(self, team_name):
        """Open a team page from a clickable opponent name."""
        try:
            if team_name and hasattr(self, "main_window"):
                self.main_window.open_team(team_name)
        except Exception:
            pass

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
        team = (safe_call(lambda: gm.user_team,
                          context="calendar/load_data/user_team")
                or safe_call(lambda: getattr(self.game, "user_team", None),
                             context="calendar/load_data/fallback_user_team"))
        self._my_name = (safe_call(lambda: team.team_name, "",
                                   context="calendar/load_data/user_team_name")
                         or "") if team else ""
        today = safe_call(lambda: gm.current_date,
                          context="calendar/load_data/current_date")
        self._today_iso = _iso(today)
        if not self._today_iso:
            self._today_iso = date.today().isoformat()

        games = {}
        events = {}
        league = _league(self.game)
        entries = safe_call(
            lambda: list(getattr(league, "schedule", None) or []), [],
            context="calendar/load_data/schedule") or []
        # Played-state index (scores/OT/SO) from the real game results,
        # shared with the schedule screen so statuses always agree.
        by_date = safe_call(lambda: _results_by_date(self.game), {},
                            context="calendar/load_data/results_by_date") or {}
        for g in entries:
            try:
                # Mainline parity: schedule-stamped NHL special events
                # (all-star skills/game, trade deadline) are tuple entries
                # the games loop below would otherwise skip.
                if (isinstance(g, (tuple, list)) and len(g) >= 3
                        and g[1] == "NHL_EVENT"):
                    ed = _iso(g[0])
                    edata = g[2] if isinstance(g[2], dict) else {}
                    etype = edata.get("type", "")
                    # Mainline parity: the stamped entry_draft/free_agency
                    # events get the DRAFT/FA badges (mainline's
                    # _style_for_day maps these event types directly).
                    # Stamped titles are kept verbatim.
                    etitle = str(edata.get("title", "") or etype)
                    kind, label = {
                        "all_star_skills":
                            ("allstar", "All-Star Skills Competition"),
                        "all_star_game": ("allstar", "All-Star Game"),
                        "trade_deadline": ("deadline", "Trade Deadline"),
                        "entry_draft": ("draft", etitle),
                        "free_agency": ("freeagency", etitle),
                    }.get(etype, ("important", etitle))
                    if ed and label:
                        self._add_event(events, ed, kind, label)
                    continue
                if not isinstance(g, dict):
                    continue
                home = _team_name(g.get("home_team"))
                away = _team_name(g.get("away_team"))
                gd = _iso(g.get("date"))
                if not gd:
                    continue
                mine = bool(self._my_name) and self._my_name in (home, away)
                played, hs, aws, ot, so = safe_call(
                    lambda: _game_played_state(g, self.game, by_date),
                    (False, None, None, False, False),
                    context="calendar/load_data/played_state")
                games.setdefault(gd, []).append({
                    "home": home, "away": away, "mine": mine,
                    "is_home": bool(mine) and home == self._my_name,
                    "opponent": (away if home == self._my_name
                                 else (home if mine else "")),
                    "preseason": bool(g.get("preseason", False)),
                    "played": played, "home_score": hs, "away_score": aws,
                    "overtime": ot, "shootout": so,
                })
                # Outdoor games stamped on the schedule (Winter Classic,
                # Stadium Series) — ported from mainline.
                od = g.get("outdoor")
                if isinstance(od, dict) and od.get("event"):
                    self._add_event(
                        events, gd, "outdoor",
                        f"{od.get('event')}: {away} @ {home}")
            except Exception:
                continue
        self._games_by_date = games

        # trade deadline
        try:
            from trade_deadline_manager import trade_deadline_date
            dd = trade_deadline_date(league)
            if dd:
                self._add_event(events, dd.isoformat(),
                                "deadline", "Trade Deadline")
        except Exception:
            pass
        # Entry draft: the marker comes from the engine-stamped NHL_EVENT
        # (type "entry_draft", Jun 27 — the same date mainline badges
        # DRAFT). No derived marker is added: the stamp is the single
        # source of truth, so June always shows exactly one draft marker.
        # season bounds from the regular-season schedule
        try:
            dates = sorted(gd for gd, gs in games.items()
                           if gd and not any(x["preseason"] for x in gs))
            if dates:
                self._add_event(events, dates[0],
                                "season", "Opening Night")
                if dates[-1] != dates[0]:
                    self._add_event(events, dates[-1],
                                    "season", "Regular Season Ends")
        except Exception:
            pass
        # Mainline parity: marquee events, break days, fixed league dates.
        self._add_marquee_events(events)
        self._add_break_days_and_holidays(events)
        self._add_important_dates(events)
        self._events_by_date = events

    # ------------------------------------------------------------------
    # Mainline calendar parity (calendar_window.py)
    # ------------------------------------------------------------------
    @staticmethod
    def _add_event(events, iso, kind, label):
        """Append one event, skipping exact (kind, label) duplicates."""
        day = events.setdefault(iso, [])
        if any(e.get("kind") == kind and e.get("label") == label
               for e in day):
            return
        day.append({"kind": kind, "label": label})

    def _season_year(self):
        """Year the season started (e.g. 2026 for 2026-27).

        Port of mainline's _get_season_year: league.season_year, falling
        back to deriving from the current date (Jan-Sep => started last
        year).
        """
        league = _league(self.game)
        sy = safe_call(lambda: int(getattr(league, "season_year", 0) or 0),
                       0, context="calendar/season_year")
        if sy:
            return sy
        try:
            cur = date.fromisoformat(self._today_iso[:10]) \
                if self._today_iso else date.today()
        except Exception:
            cur = date.today()
        return cur.year if cur.month >= 10 else cur.year - 1

    def _add_marquee_events(self, events):
        """Surface marquee calendar events the sim actually stages.

        Port of mainline's _add_marquee_events:
        - jersey-retirement ceremonies (the league's ceremony schedule,
          skipped once the number is retired);
        - the Olympic window in Olympic years (roster announcement Feb 9,
          NHL dark Feb 10-24, medal games Feb 22).
        Outdoor games are stamped on the schedule itself (handled in
        _load_data). All additive; never crashes on a missing system.
        """
        league = _league(self.game)
        season_year = self._season_year()
        # -- Jersey ceremonies -------------------------------------
        try:
            import immortality as _im
            sched = (safe_call(
                lambda: getattr(league, "ceremony_schedule", None),
                context="calendar/marquee/ceremony_schedule")
                or _im.ceremony_schedule_for(season_year))
            for c in sched or []:
                try:
                    y, m, d = (int(x) for x in
                               str(c.get("date", ""))[:10].split("-"))
                    ciso = date(y, m, d).isoformat()
                except Exception:
                    continue
                team = next(
                    (t for t in (getattr(league, "teams", None) or [])
                     if getattr(t, "team_name", "") == c.get("team", "")),
                    None)
                if team is not None and safe_call(
                        lambda: _im.is_number_retired(
                            team, int(c.get("number", 0) or 0)),
                        False,
                        context="calendar/marquee/retired_check"):
                    continue  # already in the rafters
                self._add_event(
                    events, ciso, "ceremony",
                    f"Jersey retirement: {c.get('player', '')} "
                    f"No. {c.get('number', '')} ({c.get('team', '')})")
        except Exception:
            pass
        # -- Olympic window ----------------------------------------
        try:
            from international import is_olympic_year
            if is_olympic_year(season_year + 1):
                self._add_event(events, date(season_year + 1, 2, 9).isoformat(),
                                "olympics", "Olympic rosters announced")
                cur = date(season_year + 1, 2, 10)
                while cur <= date(season_year + 1, 2, 24):
                    # Styled as a break so the dark stretch reads on the
                    # grid; the details dialog names it.
                    self._add_event(events, cur.isoformat(), "break",
                                    "Olympic break \u2014 NHL dark")
                    cur += timedelta(days=1)
                self._add_event(events, date(season_year + 1, 2, 22).isoformat(),
                                "olympics", "Olympic medal games")
        except Exception:
            pass

    def _add_break_days_and_holidays(self, events):
        """All-Star / Christmas break days (port of mainline).

        Days that already carry an all-star event from the schedule keep
        their event instead of getting a generic break marker.
        """
        season_year = self._season_year()
        cur = date(season_year + 1, 2, 5)
        while cur <= date(season_year + 1, 2, 11):
            iso = cur.isoformat()
            if not any(e.get("kind") == "allstar"
                       for e in events.get(iso, [])):
                self._add_event(events, iso, "break", "All-Star Break")
            cur += timedelta(days=1)
        self._add_event(events, date(season_year, 12, 24).isoformat(),
                        "break", "Christmas Break")
        self._add_event(events, date(season_year, 12, 25).isoformat(),
                        "xmas", "Christmas Day")

    def _add_important_dates(self, events):
        """Fixed league dates (port of mainline's _add_important_dates).

        A date that already has events keeps them (mainline skips those
        days). Mainline's fixed "Draft Day" (Jun 27) is intentionally not
        ported: the engine stamps the real NHL_EVENT (type
        "entry_draft", Jun 27) on the schedule, and the NHL_EVENT mapping
        in _load_data turns that stamp into the single DRAFT marker —
        exactly one draft marker, same date and badge as mainline.
        """
        season_year = self._season_year()
        important = [
            (date(season_year, 10, 8), "important", "Season Opener"),
            (date(season_year + 1, 1, 1), "important", "New Year's Day"),
            (date(season_year + 1, 2, 14), "important", "Valentine's Day"),
            (date(season_year + 1, 4, 25), "important",
             "Regular Season End"),
            (date(season_year + 1, 4, 26), "important", "Playoffs Begin"),
            (date(season_year + 1, 7, 1), "freeagency", "Free Agency"),
        ]
        for event_date, kind, label in important:
            iso = event_date.isoformat()
            if iso in events:
                continue  # mainline: skip days that already have events
            self._add_event(events, iso, kind, label)

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
        today = safe_call(lambda: gm.current_date,
                          context="calendar/banner/current_date")
        try:
            today = today.date() if isinstance(today, datetime) else today
        except Exception:
            today = None
        if not isinstance(today, date):
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

    def _show_day_detail(self, iso):
        """Click handler: open the day-detail panel for one calendar day.

        Looks the day's games up in the real league schedule (via
        ``_load_data``) and renders them in a dialog. Days with no games
        show "No games scheduled"; unknown dates are handled gracefully.
        """
        try:
            iso = str(iso or "")
            games = list(self._games_by_date.get(iso, []) or [])
            events = list(self._events_by_date.get(iso, []) or [])
            self._selected_iso = iso
            self._render_grid()
            dlg = _DayDetailDialog(iso, games, events, self._my_name,
                                   self._today_iso, parent=self,
                                   main_window=self.main_window,
                                   games_by_date=self._games_by_date)
            dlg.exec()
        except Exception as e:
            print(f"[calendar] day detail failed: {e}")
            try:
                QMessageBox.warning(
                    self, "Day Details",
                    f"Could not open the day details: {e}")
            except Exception:
                pass

    def _goto_screen(self, screen_name):
        """Navigate to another screen from a calendar event marker."""
        try:
            if self.main_window is not None:
                self.main_window.show_screen(screen_name)
        except Exception:
            pass

    def _day_marker(self, iso, games, events):
        """Priority marker badge for a day cell.

        Port of mainline's _style_for_day priority: user game
        (HOME/AWAY) > league games > all-star (ASG) > trade deadline
        (TDL) > draft (DRAFT) > free agency (FA) > christmas (XMAS) >
        ceremony (RETIRE) / outdoor (WC) / olympics (OLY) > break
        (BREAK) > other events (!). Like mainline, today keeps its
        game marker but drops event badges.
        Returns (marker_text, emphasis) with emphasis one of
        'home'/'away'/'event'/''.
        """
        kinds = [e.get("kind", "") for e in events]
        marker, emphasis = "", ""
        if any(g.get("mine") and g.get("is_home") for g in games):
            marker, emphasis = "HOME", "home"
        elif any(g.get("mine") and not g.get("is_home") for g in games):
            marker, emphasis = "AWAY", "away"
        elif games:
            marker, emphasis = f"{len(games)} games", ""
        elif "allstar" in kinds:
            marker, emphasis = "ASG", "event"
        elif "deadline" in kinds:
            marker, emphasis = "TDL", "event"
        elif "draft" in kinds:
            marker, emphasis = "DRAFT", "event"
        elif "freeagency" in kinds:
            marker, emphasis = "FA", "event"
        elif "xmas" in kinds:
            marker, emphasis = "XMAS", "event"
        elif "ceremony" in kinds:
            marker, emphasis = "RETIRE", "event"
        elif "outdoor" in kinds:
            marker, emphasis = "WC", "event"
        elif "olympics" in kinds:
            marker, emphasis = "OLY", "event"
        elif "break" in kinds:
            marker, emphasis = "BREAK", "event"
        elif kinds:
            marker, emphasis = "!", "event"
        if iso == self._today_iso and emphasis not in ("home", "away"):
            # Today keeps its game marker but not the event badge.
            marker = "" if emphasis == "event" else marker
            if emphasis == "event":
                emphasis = ""
        return marker, emphasis

    def _day_cell(self, day_num, iso, games, events):
        cell = _DayCell(iso)
        cell.setObjectName("tile")
        cell.day_clicked.connect(self._show_day_detail)
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
        if iso == self._selected_iso:
            style = ("font-size: 13px; font-weight: 800; color: #111827; "
                     "background: #3B82F6; border-radius: 10px; "
                     "padding: 1px 6px;")
            dl.setAlignment(Qt.AlignLeft)
        dl.setStyleSheet(style)
        cl.addWidget(dl)
        # Mainline parity: one priority badge per day (HOME/AWAY/"N games"
        # on game days, ASG/TDL/DRAFT/FA/XMAS/RETIRE/WC/OLY/BREAK/! on
        # event days) instead of the plain counts.
        marker, emphasis = self._day_marker(iso, games, events)
        mine = [g for g in games if g["mine"]]
        if mine:
            badge = QLabel(marker)  # HOME or AWAY
            badge.setStyleSheet(
                "font-size: 10px; font-weight: 800; color: "
                f"{'#3B82F6' if emphasis == 'home' else '#0ea5b7'};")
            cl.addWidget(badge)
            for g in mine[:2]:
                opp = g['opponent'] or g['away']
                pre = 'vs' if g['is_home'] else '@'
                row = QHBoxLayout()
                row.setSpacing(2)
                row.setContentsMargins(0, 0, 0, 0)
                pre_lbl = QLabel(pre + (" (PRE)" if g["preseason"] else ""))
                pre_lbl.setStyleSheet("font-size: 10px; color: #9aa4b8;")
                row.addWidget(pre_lbl)
                if opp:
                    ob = QPushButton(opp)
                    ob.setCursor(Qt.PointingHandCursor)
                    ob.setStyleSheet(
                        "QPushButton { font-size: 10px; color: #9aa4b8; "
                        "background: transparent; border: none; padding: 0px; "
                        "text-align: left; } "
                        "QPushButton:hover { color: #3B82F6; "
                        "text-decoration: underline; }")
                    ob.clicked.connect(
                        lambda _c=False, t=opp: self._open_team_page(t))
                    row.addWidget(ob)
                row.addStretch()
                cw = QWidget()
                cw.setLayout(row)
                cl.addWidget(cw)
        elif games:
            gl = QLabel(f"{len(games)} league")
            gl.setStyleSheet("font-size: 11px; color: #6b7488;")
            cl.addWidget(gl)
        elif marker:
            # Event-day badge (ASG/TDL/DRAFT/FA/XMAS/RETIRE/WC/OLY/BREAK/!).
            badge = QLabel(marker)
            badge.setStyleSheet(
                "font-size: 10px; font-weight: 800; color: #e8b34b;")
            cl.addWidget(badge)
        # Event markers are clickable (E-15): deadline/draft markers
        # navigate straight to the Deadline Center / Draft Day Central;
        # every other marker opens the day-detail dialog, the same panel
        # clicking the day cell itself opens.
        for ev in events:
            kind = ev.get("kind", "")
            icon = {"deadline": "\u23F0", "draft": "\U0001F3AF",
                    "season": "\U0001F3C1", "allstar": "\u2B50",
                    "ceremony": "\U0001F3A9", "olympics": "\U0001F3C5",
                    "outdoor": "\u2744\uFE0F", "freeagency": "\U0001F4B0",
                    "break": "\u23F8\uFE0F", "xmas": "\U0001F384",
                    "important": "\u2757"}.get(kind, "\u2022")
            full = str(ev.get("label", ""))
            short = full if len(full) <= 30 else full[:29] + "\u2026"
            target = {"deadline": "deadline",
                      "draft": "draft_central"}.get(kind)
            btn = QPushButton(f"{icon} {short}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { font-size: 10px; font-weight: 700; "
                "color: #e8b34b; background: transparent; border: none; "
                "padding: 0px; text-align: left; } "
                "QPushButton:hover { color: #f5c86e; "
                "text-decoration: underline; }")
            if target:
                btn.setToolTip(f"Open {full}")
                btn.clicked.connect(
                    lambda _c=False, t=target: self._goto_screen(t))
            else:
                btn.setToolTip(f"Day details: {full}")
                btn.clicked.connect(
                    lambda _c=False, i=iso: self._show_day_detail(i))
            cl.addWidget(btn)
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
