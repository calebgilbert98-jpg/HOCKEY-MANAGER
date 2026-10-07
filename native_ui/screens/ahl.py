"""AHL league hub: standings, scores, Calder Cup bracket, team view,
prospects (read-only).

Port of web_ui/screens/ahl.py (which ported ahl_league_window.py and
ahl_stats_window.py "Who's Cooking"). Five tabs: Standings, Scores,
Calder Cup, Team, Prospects. The Team tab has a farm-club picker
defaulting to the user's affiliate.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QScrollArea, QFrame,
    QAbstractItemView, QHeaderView,
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


def _ahl_teams(league):
    try:
        from ahl_league import ahl_team_list
        return ahl_team_list(league)
    except Exception:
        return []


def _tname(teams, idx):
    try:
        from ahl_league import _tname as _tn
        return _tn(teams, idx)
    except Exception:
        try:
            return teams[idx].team_name
        except Exception:
            return f"Team {idx}"


def _pname(p):
    return (getattr(p, "full_name", None) or getattr(p, "name", None)
            or "Unknown")


def _pos_str(p):
    try:
        return str(p.primary_position.value)
    except Exception:
        return str(getattr(p, "primary_position", ""))[:2]


def _farm_fake_league(teams):
    """Adapter so ahl_system helpers run over farm teams (desktop
    _FakeLeague pattern)."""

    class _FakeLeague:
        def __init__(self, t):
            self.teams = t

    return _FakeLeague(teams)


def _user_farm_idx(league, game):
    """Index of the user's farm club (desktop _user_farm_idx)."""
    try:
        gm = _gm(game)
        user = (_safe(lambda: gm.user_team)
                or _safe(lambda: getattr(game, "user_team", None)))
        uname = _safe(lambda: user.team_name, "")
        teams = _ahl_teams(league)
        for i, t in enumerate(teams):
            parent = getattr(t, "parent_team", None)
            if parent is not None and \
                    getattr(parent, "team_name", "") == uname:
                return i
    except Exception:
        pass
    return None


class AhIScreen(BaseScreen):
    """Five-tab AHL hub."""

    title = "AHL"

    def _build_body(self):
        self._loaded = {}
        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._standings_page = self._make_standings_page()
        self._scores_page = self._make_scores_page()
        self._calder_page = self._make_calder_page()
        self._team_page = self._make_team_page()
        self._prospects_page = self._make_prospects_page()

        self._tabs.addTab(self._standings_page, "Standings")
        self._tabs.addTab(self._scores_page, "Scores")
        self._tabs.addTab(self._calder_page, "Calder Cup")
        self._tabs.addTab(self._team_page, "Team")
        self._tabs.addTab(self._prospects_page, "Prospects")

        self._layout.addWidget(self._tabs, 1)

    # ------------------------------------------------------------------
    def _scroll_host(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(10)
        scroll.setWidget(inner)
        return scroll, inner, layout

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                AhIScreen._clear_layout(sub)

    def _empty(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
        return lbl

    def _note_label(self):
        lbl = QLabel("")
        lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        lbl.setWordWrap(True)
        return lbl

    # --- Standings ------------------------------------------------------
    def _make_standings_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._stand_table = QTableWidget()
        self._stand_table.setColumnCount(11)
        self._stand_table.setHorizontalHeaderLabels(
            ["#", "Farm Club", "GP", "W", "L", "OTL", "PTS", "PT%",
             "GF", "GA", "NHL Affiliate"])
        self._stand_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._stand_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self._stand_table.setSortingEnabled(True)
        self._stand_table.verticalHeader().setVisible(False)
        self._stand_table.setAlternatingRowColors(True)
        hdr = self._stand_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(10, QHeaderView.Stretch)
        layout.addWidget(self._stand_table)
        return scroll

    def _load_standings(self):
        league = _league(self.game)
        table = self._stand_table
        table.setSortingEnabled(False)
        table.setRowCount(0)
        rows = []
        try:
            from ahl_league import get_ahl_standings
            teams = _ahl_teams(league)
            for idx, rec in get_ahl_standings(league):
                try:
                    parent = ""
                    try:
                        p = getattr(teams[idx], "parent_team", None)
                        parent = getattr(p, "team_name", "") if p else ""
                    except Exception:
                        pass
                    gp = int(rec.get("gp", 0) or 0)
                    pts = int(rec.get("pts", 0) or 0)
                    rows.append((
                        _tname(teams, idx),
                        gp,
                        int(rec.get("w", 0) or 0),
                        int(rec.get("l", 0) or 0),
                        int(rec.get("otl", 0) or 0),
                        pts,
                        round(pts / (2 * gp), 3) if gp else 0.0,
                        int(rec.get("gf", 0) or 0),
                        int(rec.get("ga", 0) or 0),
                        parent,
                    ))
                except Exception:
                    continue
            rows.sort(key=lambda r: (-r[5], -r[2], r[0]))
        except Exception:
            pass
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            cells = [str(i + 1)] + [str(v) for v in r]
            for col, txt in enumerate(cells):
                item = QTableWidgetItem(txt)
                if col not in (1, 10):
                    try:
                        item.setData(Qt.UserRole, float(txt))
                    except Exception:
                        pass
                if col == 6:
                    item.setStyleSheet("font-weight: 700;")
                table.setItem(i, col, item)
        table.setSortingEnabled(True)
        if not rows:
            table.setRowCount(1)
            table.setSpan(0, 0, 1, 11)
            item = QTableWidgetItem("No AHL standings yet.")
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(0, 0, item)

    # --- Scores ---------------------------------------------------------
    def _make_scores_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._scores_note = self._note_label()
        layout.addWidget(self._scores_note)
        h = QLabel("Recent Finals")
        h.setObjectName("section-header")
        layout.addWidget(h)
        self._recent_table = self._score_table(
            ["Date", "Away", "Final", "Home"])
        layout.addWidget(self._recent_table)
        h2 = QLabel("Upcoming")
        h2.setObjectName("section-header")
        layout.addWidget(h2)
        self._upcoming_table = self._score_table(
            ["Date", "Away", "", "Home"])
        layout.addWidget(self._upcoming_table)
        return scroll

    def _score_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        hdr = t.horizontalHeader()
        for i in range(len(headers)):
            hdr.setSectionResizeMode(i, QHeaderView.Stretch)
        return t

    def _load_scores(self):
        league = _league(self.game)
        recent, upcoming = [], []
        try:
            from ahl_league import (get_ahl_recent_results,
                                    get_ahl_upcoming)
            teams = _ahl_teams(league)
            for r in get_ahl_recent_results(league, n=20):
                try:
                    hn = _tname(teams, r["home"])
                    an = _tname(teams, r["away"])
                    final = f"{r['away_score']} – {r['home_score']}"
                    if r.get("ot"):
                        final += " (OT)"
                    recent.append((str(r.get("date", ""))[5:],
                                   an, final, hn))
                except Exception:
                    continue
            today = _safe(lambda: _gm(self.game).current_date)
            for g in get_ahl_upcoming(league, today, n=20):
                try:
                    upcoming.append((str(g.get("date", ""))[5:],
                                     g.get("away_name", ""), "@",
                                     g.get("home_name", "")))
                except Exception:
                    continue
        except Exception:
            pass
        for table, rows in ((self._recent_table, recent),
                            (self._upcoming_table, upcoming)):
            table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                for col, txt in enumerate(r):
                    table.setItem(i, col, QTableWidgetItem(str(txt)))
        self._scores_note.setText(
            f"{len(recent)} recent finals — {len(upcoming)} games upcoming.")

    # --- Calder Cup -----------------------------------------------------
    def _make_calder_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._calder_layout = layout
        return scroll

    def _load_calder(self):
        league = _league(self.game)
        layout = self._calder_layout
        self._clear_layout(layout)
        teams = _ahl_teams(league)
        bracket = _safe(lambda: getattr(league, "ahl_bracket", None))
        champs = _safe(lambda: list(getattr(league, "ahl_champions", None)
                                    or []), []) or []
        made = False
        if isinstance(bracket, dict) and bracket.get("rounds"):
            made = True
            season = str(bracket.get("season", "") or "")
            h = QLabel("Bracket" + (f" — {season}" if season else ""))
            h.setObjectName("section-header")
            layout.addWidget(h)
            round_names = ["First Round", "Second Round",
                           "Conference Finals", "Calder Cup Final"]
            for ri, rnd in enumerate(bracket["rounds"]):
                rn = (round_names[ri] if ri < len(round_names)
                      else f"Round {ri + 1}")
                rl = QLabel(rn)
                rl.setStyleSheet(
                    "font-size: 15px; font-weight: 700; color: #e8b34b;")
                layout.addWidget(rl)
                for s in rnd:
                    try:
                        hn = _tname(teams, s["home"])
                        an = _tname(teams, s["away"])
                        w = (_tname(teams, s["winner"])
                             if s.get("winner") is not None else None)
                        gp = s.get("games", 0)
                        line = f"{an} vs {hn} — "
                        if w:
                            line += f"\U0001F3C6 {w} wins"
                            if gp:
                                line += f" in {gp}"
                        else:
                            line += "TBD"
                        sl = QLabel(line)
                        sl.setStyleSheet(
                            "color: #cdd6e4; font-size: 13px;")
                        layout.addWidget(sl)
                    except Exception:
                        continue
            ci = bracket.get("champion_idx")
            if ci is not None:
                cl = QLabel(f"\U0001F3C6 {_tname(teams, ci)} — "
                            "Calder Cup Champions")
                cl.setStyleSheet(
                    "font-size: 17px; font-weight: 800; color: #e8b34b;")
                layout.addWidget(cl)
        if champs:
            made = True
            h = QLabel("Past Champions")
            h.setObjectName("section-header")
            layout.addWidget(h)
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(
                ["Season", "Champion", "", "Runner-Up"])
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            hist = list(reversed(champs[-8:]))
            table.setRowCount(len(hist))
            for i, c in enumerate(hist):
                try:
                    cells = [c.get("season", ""),
                             "\U0001F3C6 " + c.get("champion", ""),
                             "def.", c.get("runner_up", "")]
                    for col, txt in enumerate(cells):
                        table.setItem(i, col,
                                      QTableWidgetItem(str(txt)))
                except Exception:
                    continue
            layout.addWidget(table)
        if made:
            note = self._note_label()
            note.setText("Top 16 by points — best-of-5 series.")
            layout.addWidget(note)
        else:
            layout.addWidget(self._empty(
                "No Calder Cup played yet — the playoffs run when the "
                "AHL regular season ends."))

    # --- Team -----------------------------------------------------------
    def _make_team_page(self):
        scroll, _inner, layout = self._scroll_host()
        ctl = QHBoxLayout()
        ctl_lbl = QLabel("Farm Club")
        ctl_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(ctl_lbl)
        self._team_picker = QComboBox()
        self._team_picker.currentIndexChanged.connect(
            lambda _i: self._load_team_tab(init=False))
        ctl.addWidget(self._team_picker, 1)
        layout.addLayout(ctl)
        self._team_body = QWidget()
        self._team_body_layout = QVBoxLayout(self._team_body)
        self._team_body_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._team_body)
        return scroll

    def _load_team_tab(self, init=True):
        league = _league(self.game)
        teams = _ahl_teams(league)
        picker = self._team_picker
        if init:
            picker.blockSignals(True)
            picker.clear()
            for i in range(len(teams)):
                picker.addItem(_tname(teams, i), i)
            uf = _user_farm_idx(league, self.game)
            idx = uf if uf is not None else 0
            if teams:
                picker.setCurrentIndex(
                    max(0, picker.findData(idx)))
            picker.blockSignals(False)
        idx = picker.currentData()
        if idx is None or not (0 <= idx < len(teams)):
            self._clear_layout(self._team_body_layout)
            self._team_body_layout.addWidget(
                self._empty("Select a farm club."))
            return
        self._clear_layout(self._team_body_layout)
        team = teams[idx]
        tname = _tname(teams, idx)
        rec = {}
        try:
            from ahl_league import get_ahl_standings
            rec = dict(get_ahl_standings(league)).get(idx, {}) or {}
        except Exception:
            pass
        head = QLabel(tname)
        head.setObjectName("section-header")
        self._team_body_layout.addWidget(head)
        r = rec
        parent = getattr(team, "parent_team", None)
        aff = getattr(parent, "team_name", "") if parent else ""
        sub = QLabel(
            f"{int(r.get('w', 0) or 0)}-{int(r.get('l', 0) or 0)}-"
            f"{int(r.get('otl', 0) or 0)} — "
            f"{int(r.get('pts', 0) or 0)} PTS"
            + (f" · NHL affiliate: {aff}" if aff else ""))
        sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._team_body_layout.addWidget(sub)

        # roster
        rh = QLabel("Roster")
        rh.setObjectName("section-header")
        self._team_body_layout.addWidget(rh)
        roster_rows = []
        try:
            from ahl_league import get_ahl_roster
            for p in get_ahl_roster(team) or []:
                try:
                    led = getattr(p, "ahl_stats", None)
                    gp = g = a = 0
                    if led is not None:
                        gp = int(getattr(led, "games_played", 0) or 0)
                        g = int(getattr(led, "goals", 0) or 0)
                        a = int(getattr(led, "assists", 0) or 0)
                    roster_rows.append((
                        _pname(p), _pos_str(p), str(getattr(p, "age", "")),
                        str(_safe(lambda: int(p.overall_rating()), "")),
                        str(gp), str(g), str(a), str(g + a)))
                except Exception:
                    continue
        except Exception:
            pass
        rtable = QTableWidget()
        rtable.setColumnCount(8)
        rtable.setHorizontalHeaderLabels(
            ["Player", "Pos", "Age", "OVR", "GP", "G", "A", "PTS"])
        rtable.setEditTriggers(QTableWidget.NoEditTriggers)
        rtable.setSelectionBehavior(QAbstractItemView.SelectRows)
        rtable.setSortingEnabled(True)
        rtable.verticalHeader().setVisible(False)
        rtable.setAlternatingRowColors(True)
        rtable.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        rtable.setSortingEnabled(False)
        rtable.setRowCount(len(roster_rows))
        for i, r_ in enumerate(roster_rows):
            for col, txt in enumerate(r_):
                item = QTableWidgetItem(txt)
                if col >= 2:
                    try:
                        item.setData(Qt.UserRole, int(txt))
                    except Exception:
                        pass
                rtable.setItem(i, col, item)
        rtable.setSortingEnabled(True)
        self._team_body_layout.addWidget(rtable)

        # schedule
        sh = QLabel("Upcoming Schedule")
        sh.setObjectName("section-header")
        self._team_body_layout.addWidget(sh)
        sched = []
        try:
            from ahl_league import get_ahl_team_schedule
            today = _safe(lambda: _gm(self.game).current_date)
            for g in get_ahl_team_schedule(league, idx, today, n=12):
                sched.append((
                    str(g.get("date", ""))[5:],
                    str(g.get("opponent", "")),
                    "vs" if g.get("home") else "@"))
        except Exception:
            pass
        stable = QTableWidget()
        stable.setColumnCount(3)
        stable.setHorizontalHeaderLabels(["Date", "Opponent", ""])
        stable.setEditTriggers(QTableWidget.NoEditTriggers)
        stable.setSelectionBehavior(QAbstractItemView.SelectRows)
        stable.verticalHeader().setVisible(False)
        stable.setAlternatingRowColors(True)
        stable.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        stable.setRowCount(len(sched))
        for i, s_ in enumerate(sched):
            for col, txt in enumerate(s_):
                stable.setItem(i, col, QTableWidgetItem(txt))
        if not sched:
            stable.setRowCount(1)
            stable.setSpan(0, 0, 1, 3)
            item = QTableWidgetItem("Nothing scheduled.")
            item.setTextAlignment(Qt.AlignCenter)
            stable.setItem(0, 0, item)
        self._team_body_layout.addWidget(stable)

    # --- Prospects ------------------------------------------------------
    def _make_prospects_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._prospects_layout = layout
        return scroll

    def _load_prospects(self):
        league = _league(self.game)
        teams = _ahl_teams(league)
        farm = _farm_fake_league(teams)
        layout = self._prospects_layout
        self._clear_layout(layout)
        try:
            import ahl_system as _ahl
        except Exception:
            layout.addWidget(self._empty(
                "Prospects module unavailable."))
            return

        # top skaters
        try:
            skaters = []
            for i, (p, tname, led) in enumerate(
                    _ahl.top_skaters(farm, limit=20), 1):
                gp = max(1, int(getattr(led, "games_played", 0) or 0))
                pts = (int(getattr(led, "goals", 0) or 0)
                       + int(getattr(led, "assists", 0) or 0))
                skaters.append((
                    str(i), _pname(p), tname, _pos_str(p),
                    str(getattr(p, "age", "")),
                    str(int(getattr(led, "games_played", 0) or 0)),
                    str(int(getattr(led, "goals", 0) or 0)),
                    str(int(getattr(led, "assists", 0) or 0)),
                    str(pts), f"{round(pts / gp, 2):.2f}"))
            self._prospect_section(
                layout, "Top Skaters",
                ["#", "Player", "Team", "Pos", "Age", "GP", "G", "A",
                 "PTS", "PPG"], skaters)
        except Exception:
            pass

        # who's cooking
        try:
            cooks = []
            for i, (p, tname, led, ppg) in enumerate(
                    _ahl.cooking(farm, limit=12), 1):
                pts = (int(getattr(led, "goals", 0) or 0)
                       + int(getattr(led, "assists", 0) or 0))
                cooks.append((
                    str(i), _pname(p), tname, _pos_str(p),
                    str(getattr(p, "age", "")),
                    str(int(getattr(led, "games_played", 0) or 0)),
                    str(pts), f"{round(float(ppg or 0), 2):.2f}"))
            self._prospect_section(
                layout, "Who's Cooking \U0001F525",
                ["#", "Player", "Team", "Pos", "Age", "GP", "PTS", "PPG"],
                cooks)
        except Exception:
            pass

        # top goalies
        try:
            goalies = []
            for i, (p, tname, led) in enumerate(
                    _ahl.top_goalies(farm, limit=12), 1):
                goalies.append((
                    str(i), _pname(p), tname,
                    str(int(getattr(led, "games_played", 0) or 0)),
                    str(int(getattr(led, "wins", 0) or 0)),
                    f"{round(float(getattr(led, 'goals_against_avg', 0) or 0), 2):.2f}",
                    f"{round(float(getattr(led, 'save_percentage', 0) or 0), 3):.3f}"))
            self._prospect_section(
                layout, "Top Goalies",
                ["#", "Player", "Team", "GP", "W", "GAA", "SV%"],
                goalies)
        except Exception:
            pass

    def _prospect_section(self, layout, title, headers, rows):
        h = QLabel(title)
        h.setObjectName("section-header")
        layout.addWidget(h)
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSortingEnabled(True)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        hdr = t.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for i, r_ in enumerate(rows):
            for col, txt in enumerate(r_):
                item = QTableWidgetItem(txt)
                if col not in (1, 2, 3):
                    try:
                        item.setData(Qt.UserRole, float(txt))
                    except Exception:
                        pass
                t.setItem(i, col, item)
        t.setSortingEnabled(True)
        layout.addWidget(t)

    # ------------------------------------------------------------------
    def _on_tab_changed(self, idx):
        name = ["standings", "scores", "calder", "team", "prospects"][idx]
        if name not in self._loaded:
            self._loaded[name] = True
            self._load_tab(name)

    def _load_tab(self, name):
        loaders = {
            "standings": self._load_standings,
            "scores": self._load_scores,
            "calder": self._load_calder,
            "team": lambda: self._load_team_tab(init=True),
            "prospects": self._load_prospects,
        }
        try:
            loaders[name]()
        except Exception as e:
            print(f"[ahl] {name} tab failed: {e}")

    def refresh(self):
        idx = self._tabs.currentIndex()
        name = ["standings", "scores", "calder", "team", "prospects"][idx]
        self._loaded.pop(name, None)
        self._loaded[name] = True
        self._load_tab(name)
