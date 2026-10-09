"""Schedule screen: full season schedule (fixtures & results).

Ported from web_ui/screens/schedule.py (/api/schedule_full) +
web_ui/static/js/schedule.js. Two tabs (My Team / League), month filter,
sortable columns, per-game actions computed in code:

- played          -> Box Score dialog
- today's user game -> Watch + Quick
- past, unplayed  -> Simulate (confirm-gated, records the result)
- future          -> dash
"""
from datetime import date, datetime

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen
from ..dialogs.boxscore import BoxscoreDialog
from ..dialogs.daily_results import DailyResultsDialog


# ----------------------------------------------------------------------
# Game-data helpers (ported from web_ui/screens/schedule.py, Flask removed)
# ----------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return getattr(game, "game_manager", None) or game


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


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


def _iso(d):
    try:
        if isinstance(d, datetime):
            return d.date().isoformat()
        if isinstance(d, date):
            return d.isoformat()
        s = str(d or "")[:10]
        return date.fromisoformat(s).isoformat()
    except Exception:
        return None


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


def _results_by_date(game):
    try:
        idx = getattr(game, "_results_by_date_index", None)
        if callable(idx):
            return idx() or {}
    except Exception:
        pass
    by_date = {}
    results = _safe(lambda: list(getattr(game, "game_results", None) or []), []) or []
    for r in results:
        try:
            k = _date_key(r.get("date"))
            if k is not None:
                by_date.setdefault(k, []).append(r)
        except Exception:
            continue
    return by_date


def _match_result(results, home_name, away_name):
    for r in results or []:
        try:
            if _team_name(r.get("home_team")) == home_name and \
                    _team_name(r.get("away_team")) == away_name:
                return r
        except Exception:
            continue
    return None


def _schedule_entries(game):
    """Normalized schedule entries (tuple or dict formats)."""
    gm = _resolve_gm(game)
    league = _safe(lambda: getattr(gm, "league", None)) or \
        _safe(lambda: getattr(game, "league", None))
    sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
    for item in sched:
        try:
            if isinstance(item, tuple) and len(item) >= 3:
                if len(item) >= 2 and item[1] == "NHL_EVENT":
                    continue
                yield {"date": item[0], "home_team": item[1],
                       "away_team": item[2], "event_type": "GAME",
                       "preseason": False}
            elif isinstance(item, dict):
                if item.get("event_type") == "NHL_EVENT":
                    continue
                if item.get("league", "NHL") != "NHL":
                    continue
                if item.get("playoff"):
                    continue
                yield item
        except Exception:
            continue


def _game_played_state(entry, game, by_date):
    """(played, home_score, away_score, overtime, shootout)."""
    try:
        hs = entry.get("home_score")
        aws = entry.get("away_score")
        if hs is not None and aws is not None:
            return True, int(hs), int(aws), False, False
    except Exception:
        pass
    try:
        key = _date_key(entry.get("date"))
        home = _team_name(entry.get("home_team"))
        away = _team_name(entry.get("away_team"))
        r = _match_result((by_date or {}).get(key, []), home, away)
        if r is not None:
            return (True, int(r.get("home_score", 0) or 0),
                    int(r.get("away_score", 0) or 0),
                    bool(r.get("overtime")), bool(r.get("shootout")))
    except Exception:
        pass
    return False, None, None, False, False


def _load_games(game):
    """Full season schedule: past + future, with scores. Never raises."""
    gm = _resolve_gm(game)
    user_team = _safe(lambda: getattr(gm, "user_team", None)) or \
        _safe(lambda: getattr(game, "user_team", None))
    my_name = _safe(lambda: getattr(user_team, "team_name", ""), "") or ""
    today = _safe(lambda: getattr(gm, "current_date", None)) or \
        _safe(lambda: getattr(game, "current_date", None))
    today_key = _date_key(today)
    by_date = _results_by_date(game)

    games, months = [], []
    seen_months = set()
    for entry in _schedule_entries(game):
        try:
            gd = entry.get("date")
            key = _date_key(gd)
            iso = _iso(gd)
            home = _team_name(entry.get("home_team"))
            away = _team_name(entry.get("away_team"))
            if not home or not away or home == "?" or away == "?":
                continue
            played, hs, aws, ot, so = _game_played_state(entry, game, by_date)
            if key is not None:
                month_label = key.strftime("%B %Y")
                if month_label not in seen_months:
                    seen_months.add(month_label)
                    months.append({"label": month_label,
                                   "key": key.strftime("%Y-%m")})
            else:
                month_label = ""
            is_today = key is not None and today_key is not None and key == today_key
            is_past = key is not None and today_key is not None and key < today_key
            games.append({
                "date_iso": iso,
                "date_label": key.strftime("%a %m/%d") if key else str(gd or ""),
                "month": key.strftime("%Y-%m") if key else "",
                "month_label": month_label,
                "home": home,
                "away": away,
                "home_abbr": _abbr(home),
                "away_abbr": _abbr(away),
                "played": played,
                "home_score": hs,
                "away_score": aws,
                "status": "Final" if played else ("Today" if is_today else "Scheduled"),
                "overtime": ot,
                "shootout": so,
                "preseason": bool(entry.get("preseason", False)),
                "is_user": my_name in (home, away),
                "is_today": is_today,
                "is_past": is_past,
            })
        except Exception:
            continue
    games.sort(key=lambda g: (g["date_iso"] is None, g["date_iso"] or ""))
    return {"user_team": my_name, "months": months, "games": games}


def _sim_missed_game(game, date_iso, home_name, away_name):
    """Quick-sim one past, never-played scheduled game.

    Ported from web_ui/bridge.py::_sim_missed_game (desktop parity with
    windows.ScheduleView.simulate_selected_game). Never raises.
    """
    try:
        gm = _resolve_gm(game)
        league = _safe(lambda: getattr(gm, "league", None)) or \
            _safe(lambda: getattr(game, "league", None))
        if league is None or not date_iso or not home_name or not away_name:
            return
        try:
            gdate = date.fromisoformat(str(date_iso)[:10])
        except Exception:
            return
        today = _safe(lambda: getattr(gm, "current_date", None)) or \
            _safe(lambda: getattr(game, "current_date", None))
        try:
            today_key = today.date() if hasattr(today, "date") else today
        except Exception:
            today_key = today
        # Today/future games belong to the season sim.
        if not isinstance(gdate, date) or not isinstance(today_key, date):
            return
        if gdate >= today_key:
            return
        # Find the scheduled entry and make sure it was never played.
        sched = _safe(lambda: list(getattr(league, "schedule", None) or []),
                      []) or []
        entry = None
        for item in sched:
            try:
                if isinstance(item, tuple):
                    if len(item) >= 3 and item[1] != "NHL_EVENT" and \
                            _team_name(item[1]) == home_name and \
                            _team_name(item[2]) == away_name:
                        gd = item[0].date() if hasattr(item[0], "date") \
                            else item[0]
                        if gd == gdate:
                            entry = item
                            break
                elif isinstance(item, dict):
                    if _team_name(item.get("home_team")) == home_name and \
                            _team_name(item.get("away_team")) == away_name:
                        gd = item.get("date")
                        gd = gd.date() if hasattr(gd, "date") else gd
                        if gd == gdate and item.get("home_score") is None:
                            entry = item
                            break
            except Exception:
                continue
        if entry is None:
            return
        # Never double-record.
        try:
            idx = getattr(game, "_results_by_date_index", None)
            existing = list(idx().get(gdate, [])) if callable(idx) else []
            for r in existing:
                if _team_name(r.get("home_team")) == home_name and \
                        _team_name(r.get("away_team")) == away_name:
                    return
        except Exception:
            pass
        teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []
        home_team = next((t for t in teams
                          if _team_name(t) == home_name), None)
        away_team = next((t for t in teams
                          if _team_name(t) == away_name), None)
        if home_team is None or away_team is None:
            return
        from simulation import GameSim
        sim = GameSim(home_team, away_team)
        sim.run()
        home_score = int(getattr(sim, "home_score", 0) or 0)
        away_score = int(getattr(sim, "away_score", 0) or 0)
        winner = home_team if home_score > away_score else away_team
        notable = _safe(lambda: list(getattr(sim, "notable_events", None) or []),
                        []) or []
        went_ot = any(isinstance(e, dict) and e.get("period", 0) > 3
                      for e in notable)
        went_so = any(isinstance(e, dict) and e.get("period", 0) == 5
                      for e in notable)
        game_result = {
            "date": gdate,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
            "events": _safe(lambda: list(getattr(sim, "game_log", None) or []),
                            []) or [],
            "notable_events": notable,
            "player_ratings": {},
            "event_log": _safe(lambda: list(getattr(sim, "event_log", None) or []),
                               []) or [],
            "game_stats": _safe(lambda: dict(getattr(sim, "game_stats", None) or {}),
                                {}) or {},
            "team_stats": _safe(lambda: dict(getattr(sim, "team_stats", None) or {}),
                                {}) or {},
            "overtime": went_ot,
            "shootout": went_so,
        }
        # Record (keeps the derived indexes in sync when available).
        rec = getattr(game, "_record_game_result", None)
        if callable(rec):
            rec(game_result)
        else:
            _safe(lambda: getattr(game, "game_results", None).append(game_result))
        # Stamp the schedule entry so the page shows Final.
        try:
            if isinstance(entry, dict):
                entry["home_score"] = home_score
                entry["away_score"] = away_score
        except Exception:
            pass
        # Team records (mirrors _update_team_stats_from_game).
        try:
            home_team.goals_for = getattr(home_team, "goals_for", 0) + home_score
            home_team.goals_against = getattr(home_team, "goals_against", 0) + away_score
            away_team.goals_for = getattr(away_team, "goals_for", 0) + away_score
            away_team.goals_against = getattr(away_team, "goals_against", 0) + home_score
            if home_score > away_score:
                home_team.update_record("WIN")
                away_team.update_record("LOSS", overtime=went_ot)
            elif away_score > home_score:
                away_team.update_record("WIN")
                home_team.update_record("LOSS", overtime=went_ot)
        except Exception:
            pass
        try:
            game.add_news(f"{away_name} {away_score} @ {home_score} {home_name} "
                          f"(simmed {gdate.strftime('%b %d')}).")
        except Exception:
            pass
    except Exception:
        pass


# ----------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------

class _SortItem(QTableWidgetItem):
    """Table item that sorts on a UserRole key instead of display text."""

    def __init__(self, text, sort_key):
        super().__init__(text)
        self.setData(Qt.UserRole, sort_key)

    def __lt__(self, other):
        try:
            return self.data(Qt.UserRole) < other.data(Qt.UserRole)
        except Exception:
            return super().__lt__(other)


class ScheduleScreen(BaseScreen):
    """Full season schedule with per-game actions. title: SCHEDULE."""

    title = "Schedule"

    def _build_body(self):
        self._tab = "mine"   # 'mine' | 'league'
        self._month = "all"
        self._data = {"user_team": "", "months": [], "games": []}

        # Controls row
        controls = QHBoxLayout()
        self._tab_mine = QPushButton("My Team")
        self._tab_mine.setCheckable(True)
        self._tab_mine.setChecked(True)
        self._tab_mine.setObjectName("primary-btn")
        self._tab_mine.setCursor(Qt.PointingHandCursor)
        self._tab_mine.clicked.connect(lambda: self._set_tab("mine"))
        self._tab_league = QPushButton("League")
        self._tab_league.setCheckable(True)
        self._tab_league.setCursor(Qt.PointingHandCursor)
        self._tab_league.clicked.connect(lambda: self._set_tab("league"))
        controls.addWidget(self._tab_mine)
        controls.addWidget(self._tab_league)
        controls.addSpacing(16)

        controls.addWidget(QLabel("Month:"))
        self._month_combo = QComboBox()
        self._month_combo.addItem("All", "all")
        self._month_combo.currentIndexChanged.connect(self._on_month_changed)
        controls.addWidget(self._month_combo)

        controls.addStretch()
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #8b95ab; font-size: 13px;")
        controls.addWidget(self._count_label)
        self._layout.addLayout(controls)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Date", "Matchup", "Score", "Status", "Action"])
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._layout.addWidget(self._table, 1)

        self._empty = QLabel("No games match this filter.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet("color: #6b7488; font-size: 14px;")
        self._empty.hide()
        self._layout.addWidget(self._empty)

    # -- data ---------------------------------------------------------

    def refresh(self):
        try:
            self._data = _load_games(self.game)
        except Exception as e:
            print(f"[schedule] load failed: {e}")
            self._data = {"user_team": "", "months": [], "games": []}
        self._rebuild_months()
        self._render()

    def _rebuild_months(self):
        self._month_combo.blockSignals(True)
        cur = self._month
        self._month_combo.clear()
        self._month_combo.addItem("All", "all")
        for m in self._data["months"]:
            self._month_combo.addItem(m["label"], m["key"])
        idx = self._month_combo.findData(cur)
        self._month_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._month = self._month_combo.currentData()
        self._month_combo.blockSignals(False)

    def _filtered(self):
        rows = list(self._data["games"])
        if self._tab == "mine":
            rows = [g for g in rows if g["is_user"]]
        if self._month != "all":
            rows = [g for g in rows if g["month"] == self._month]
        return rows

    # -- render --------------------------------------------------------

    def _set_tab(self, tab):
        self._tab = tab
        self._tab_mine.setChecked(tab == "mine")
        self._tab_league.setChecked(tab == "league")
        self._tab_mine.setObjectName("primary-btn" if tab == "mine" else "")
        self._tab_league.setObjectName("primary-btn" if tab == "league" else "")
        self._tab_mine.style().unpolish(self._tab_mine)
        self._tab_mine.style().polish(self._tab_mine)
        self._tab_league.style().unpolish(self._tab_league)
        self._tab_league.style().polish(self._tab_league)
        self._render()

    def _on_month_changed(self):
        self._month = self._month_combo.currentData() or "all"
        self._render()

    def _render(self):
        rows = self._filtered()
        played = sum(1 for g in self._data["games"] if g["played"])
        label = (f"{len(self._data['games'])} games · {played} played")
        if self._tab == "mine" and self._data["user_team"]:
            label += f" · {self._data['user_team']}"
        self._count_label.setText(label)
        self._empty.setVisible(not rows)

        table = self._table
        table.setSortingEnabled(False)
        table.setRowCount(0)
        table.setRowCount(len(rows))
        for i, g in enumerate(rows):
            # Date
            d_item = _SortItem(g["date_label"], g["date_iso"] or "")
            table.setItem(i, 0, d_item)
            # Matchup
            matchup = f"{g['away_abbr']} @ {g['home_abbr']}"
            m_item = _SortItem(matchup,
                               (g["away"] + " " + g["home"]).lower())
            m_item.setToolTip(f"{g['away']} @ {g['home']}")
            table.setItem(i, 1, m_item)
            # Score
            if g["played"]:
                score_txt = f"{g['away_score']} – {g['home_score']}"
                if g["shootout"]:
                    score_txt += " SO"
                elif g["overtime"]:
                    score_txt += " OT"
                s_item = _SortItem(score_txt, g["away_score"] + g["home_score"])
            else:
                s_item = _SortItem("–", -1)
            s_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 2, s_item)
            # Status
            status_txt = g["status"]
            if g["preseason"] and not g["played"]:
                status_txt += " · Pre"
            st_item = _SortItem(
                status_txt,
                (0 if g["played"] else 1 if g["is_today"] else 2
                 if g["is_past"] else 3, g["status"]))
            st_item.setTextAlignment(Qt.AlignCenter)
            if g["played"]:
                st_item.setForeground(QColor("#34d399"))
            elif g["is_today"]:
                st_item.setForeground(QColor("#e8b923"))
            table.setItem(i, 3, st_item)
            # Action
            table.setCellWidget(i, 4, self._make_action_cell(g))
        table.setSortingEnabled(True)

    def _make_action_cell(self, g):
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        if g["played"] and g["date_iso"]:
            btn = QPushButton("Box Score")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, gg=g: self._open_boxscore(gg))
            layout.addWidget(btn)
        elif g["is_today"] and g["is_user"] and not g["played"]:
            watch = QPushButton("Watch")
            watch.setObjectName("primary-btn")
            watch.setCursor(Qt.PointingHandCursor)
            watch.clicked.connect(lambda _=False, gg=g: self._watch_game(gg))
            quick = QPushButton("Quick")
            quick.setCursor(Qt.PointingHandCursor)
            quick.clicked.connect(lambda _=False, gg=g: self._quick_sim(gg))
            layout.addWidget(watch)
            layout.addWidget(quick)
        elif not g["played"] and g["is_past"] and g["date_iso"]:
            btn = QPushButton("Simulate")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, gg=g: self._sim_game(gg))
            layout.addWidget(btn)
        else:
            lbl = QLabel("–")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #6b7488;")
            layout.addWidget(lbl)
        return wrap

    # -- actions -------------------------------------------------------

    def _open_boxscore(self, g):
        try:
            dlg = BoxscoreDialog(self.game, parent=self)
            dlg.set_game(g["date_iso"], g["home"], g["away"])
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Box Score",
                                f"Could not open the box score: {e}")

    def _watch_game(self, g):
        try:
            # Pin this specific game so the watch screen sims it
            # instead of auto-picking the next game.
            from .watch import set_target_entry
            # Watch consumes the shared entry schema (date/home_team/away_team)
            # while the schedule screen row uses date_iso/home/away -- adapt.
            set_target_entry({
                "date": g.get("date_iso"),
                "date_iso": g.get("date_iso"),
                "home_team": g.get("home"),
                "away_team": g.get("away"),
                "home": g.get("home"),
                "away": g.get("away"),
            })
            self.navigate_to("watch")
            # Auto-start the sim for the pinned game.
            mw = self.main_window
            scroll = mw._screens.get("watch") if mw else None
            inner = scroll.widget() if scroll and hasattr(
                scroll, "widget") else None
            if inner is not None and hasattr(inner, "_start"):
                inner._start()
        except Exception as e:
            QMessageBox.warning(
                self, "Watch",
                f"Could not open the Watch screen: {e}")

    def _quick_sim(self, g):
        resp = QMessageBox.question(
            self, "Quick Sim",
            f"Quick-sim today's game ({g['away']} @ {g['home']})? "
            f"This advances the day.",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        try:
            fn = (getattr(self.game, "simulate_day", None)
                  or getattr(self.game, "_on_continue_pressed", None))
            if not callable(fn):
                QMessageBox.warning(
                    self, "Quick Sim",
                    "The game does not expose a day-advance method.")
                return
            fn()
            self.refresh()
            dlg = DailyResultsDialog(self.game, parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Quick Sim",
                                f"Quick sim failed: {e}")

    def _sim_game(self, g):
        resp = QMessageBox.question(
            self, "Simulate Game",
            f"Simulate {g['away']} @ {g['home']} ({g['date_iso']})? "
            f"This records the result in your season.",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        try:
            _sim_missed_game(self.game, g["date_iso"], g["home"], g["away"])
            self.refresh()
            dlg = BoxscoreDialog(self.game, parent=self)
            dlg.set_game(g["date_iso"], g["home"], g["away"])
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Simulate",
                                f"Simulate failed: {e}")
