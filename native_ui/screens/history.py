"""League History: champions, awards, career leaders, Hall of Fame,
advanced stats, season reviews, franchise records (read-only).

Port of web_ui/screens/history.py (which itself ported main.py
LeagueHistoryView ~30206-30653). All data comes from the engine's
LeagueHistory object and helpers -- no HTTP, no serialization.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QScrollArea, QFrame, QPushButton,
    QAbstractItemView, QHeaderView,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


_HISTORY_CATS = ["points", "goals", "assists", "wins", "shutouts", "save_pct"]


def _gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _league(game):
    gm = _gm(game)
    return (_safe(lambda: gm.league)
            or _safe(lambda: getattr(game, "league", None)))


def _hist(game):
    """LeagueHistory with the same defensive fallbacks as the web bridge."""
    h = _safe(lambda: getattr(_gm(game), "league_history", None))
    if h is None:
        h = _safe(lambda: getattr(game, "league_history", None))
    if h is None:
        league = _league(game)
        h = _safe(lambda: getattr(league, "history", None)) if league else None
    return h


def _league_players(game):
    out = []
    league = _league(game)
    for t in (_safe(lambda: list(league.teams), []) or []):
        out.extend(_safe(lambda: list(t.roster), []) or [])
    return out


class HistoryScreen(BaseScreen):
    """Seven-tab read-only league history viewer."""

    title = "History"

    def _build_body(self):
        self._loaded = {}
        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._champions_page = self._make_champions_page()
        self._awards_page = self._make_awards_page()
        self._leaders_page = self._make_leaders_page()
        self._hof_page = self._make_hof_page()
        self._advanced_page = self._make_advanced_page()
        self._reviews_page = self._make_reviews_page()
        self._records_page = self._make_records_page()

        self._tabs.addTab(self._champions_page, "Champions")
        self._tabs.addTab(self._awards_page, "Awards")
        self._tabs.addTab(self._leaders_page, "Leaders")
        self._tabs.addTab(self._hof_page, "Hall of Fame")
        self._tabs.addTab(self._advanced_page, "Advanced")
        self._tabs.addTab(self._reviews_page, "Reviews")
        self._tabs.addTab(self._records_page, "Records")

        self._layout.addWidget(self._tabs, 1)

    # ------------------------------------------------------------------
    # tab scaffolding
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

    def _empty_label(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
        return lbl

    # --- champions ------------------------------------------------------
    def _make_champions_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._champions_layout = layout
        return scroll

    def _load_champions(self):
        hist = _hist(self.game)
        seasons = _safe(lambda: hist.champions_list(), []) or []
        layout = self._champions_layout
        self._clear_layout(layout)
        if not seasons:
            layout.addWidget(self._empty_label(
                "No history yet\n\n"
                "This is a fresh league. Past champions and franchise "
                "records will appear here once the first season is in the books."))
            return
        for s in seasons:
            try:
                card = QFrame()
                card.setObjectName("tile")
                cl = QVBoxLayout(card)
                year = QLabel(str(s.get("year", "")))
                year.setStyleSheet(
                    "font-size: 16px; font-weight: 700; color: #e8b34b;")
                champ = QLabel("\U0001F3C6 " + str(s.get("champion", "") or ""))
                champ.setStyleSheet(
                    "font-size: 18px; font-weight: 700; color: #f2f4f8;")
                cl.addWidget(year)
                cl.addWidget(champ)
                detail = []
                if s.get("runner_up"):
                    d = "def. " + str(s["runner_up"])
                    if s.get("series_score"):
                        d += " " + str(s["series_score"])
                    detail.append(d)
                if s.get("conn_smythe"):
                    detail.append("Conn Smythe: " + str(s["conn_smythe"]))
                if s.get("presidents_trophy"):
                    detail.append(
                        "Presidents' Trophy: " + str(s["presidents_trophy"]))
                for d in detail:
                    dl = QLabel(d)
                    dl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
                    cl.addWidget(dl)
                layout.addWidget(card)
            except Exception:
                continue

    # --- awards ---------------------------------------------------------
    def _make_awards_page(self):
        scroll, _inner, layout = self._scroll_host()
        ctl = QHBoxLayout()
        ctl_lbl = QLabel("Season")
        ctl_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(ctl_lbl)
        self._awards_year = QComboBox()
        self._awards_year.currentIndexChanged.connect(
            lambda _i: self._load_awards())
        ctl.addWidget(self._awards_year)
        ctl.addStretch()
        layout.addLayout(ctl)
        self._awards_layout = layout
        self._awards_year.setProperty("_init", False)
        return scroll

    def _load_awards(self):
        hist = _hist(self.game)
        combo = self._awards_year
        years = []
        if hist is not None:
            seasons = _safe(lambda: list(getattr(hist, "seasons", None) or []),
                            []) or []
            years = sorted({s.get("year") for s in seasons
                            if isinstance(s, dict) and s.get("year")},
                           reverse=True)
        if not self._awards_year.property("_init"):
            combo.blockSignals(True)
            combo.clear()
            for y in years:
                combo.addItem(str(y), y)
            self._awards_year.setProperty("_init", True)
            combo.blockSignals(False)
            if not years:
                self._clear_from(self._awards_layout, 1)
                self._awards_layout.addWidget(self._empty_label(
                    "No awards recorded yet."))
                return
        self._clear_from(self._awards_layout, 1)
        if hist is None or not years:
            self._awards_layout.addWidget(self._empty_label(
                "No awards recorded yet."))
            return
        year = combo.currentData() if combo.count() else years[0]
        season = _safe(lambda: hist.get_season(year), {}) or {}
        awards = dict(season.get("awards", {}) or {})
        if season.get("conn_smythe"):
            awards = dict(awards)
            awards["Conn Smythe"] = season["conn_smythe"]
        if season.get("champion"):
            awards = dict(awards)
            awards.setdefault("Stanley Cup", season["champion"])
        if not awards:
            self._awards_layout.addWidget(self._empty_label(
                "No awards recorded for this season."))
            return
        for name, winner in awards.items():
            row = QFrame()
            row.setObjectName("tile")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            nl = QLabel(str(name))
            nl.setStyleSheet("font-size: 14px; font-weight: 700;")
            wl = QLabel(str(winner))
            wl.setStyleSheet("font-size: 14px; color: #e8b34b;")
            wl.setAlignment(Qt.AlignRight)
            rl.addWidget(nl, 1)
            rl.addWidget(wl, 1)
            self._awards_layout.addWidget(row)
        if season.get("runner_up"):
            note = QLabel("Final: " + str(season.get("series_score") or ""))
            note.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            self._awards_layout.addWidget(note)

    # --- career leaders -------------------------------------------------
    def _make_leaders_page(self):
        scroll, _inner, layout = self._scroll_host()
        ctl = QHBoxLayout()
        ctl_lbl = QLabel("Category")
        ctl_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(ctl_lbl)
        self._leaders_cats = QComboBox()
        for c in _HISTORY_CATS:
            self._leaders_cats.addItem(
                "SV%" if c == "save_pct" else c.upper(), c)
        self._leaders_cats.currentIndexChanged.connect(
            lambda _i: self._load_leaders())
        ctl.addWidget(self._leaders_cats)
        ctl.addStretch()
        layout.addLayout(ctl)
        self._leaders_table = QTableWidget()
        self._leaders_table.setColumnCount(5)
        self._leaders_table.setHorizontalHeaderLabels(
            ["#", "Player", "Team", "GP", "Value"])
        self._leaders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._leaders_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self._leaders_table.setSortingEnabled(True)
        self._leaders_table.verticalHeader().setVisible(False)
        hdr = self._leaders_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self._leaders_table.setAlternatingRowColors(True)
        self._leaders_layout = layout
        layout.addWidget(self._leaders_table)
        return scroll

    def _load_leaders(self):
        cat = self._leaders_cats.currentData() or "points"
        table = self._leaders_table
        table.setRowCount(0)
        leaders = []
        try:
            from league_history import LeagueHistory
            players = _league_players(self.game)
            leaders = LeagueHistory.career_leaders(
                players, cat, limit=25) or []
        except Exception:
            leaders = []
        table.setRowCount(len(leaders))
        for i, ld in enumerate(leaders, 0):
            try:
                v = ld["value"]
                vstr = (f"{v:.3f}" if cat == "save_pct"
                        else str(int(v)))
                row = [
                    str(i + 1),
                    str(ld.get("name", "?")),
                    str(ld.get("team") or ""),
                    str(int(ld.get("games", 0) or 0)),
                    vstr,
                ]
                for col, txt in enumerate(row):
                    item = QTableWidgetItem(txt)
                    if col in (0, 3):
                        try:
                            item.setData(Qt.UserRole, int(txt))
                        except Exception:
                            pass
                    table.setItem(i, col, item)
            except Exception:
                continue
        table.setHorizontalHeaderItem(
            4, QTableWidgetItem("SV%" if cat == "save_pct" else cat.upper()))

    # --- Hall of Fame ---------------------------------------------------
    def _make_hof_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._hof_bar = QLabel("")
        self._hof_bar.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._hof_bar.setWordWrap(True)
        layout.addWidget(self._hof_bar)
        self._hof_layout = layout
        return scroll

    def _load_hof(self):
        hist = _hist(self.game)
        inds = _safe(lambda: list(getattr(hist, "hall_of_fame", None)
                                  or []), []) or []
        inds = sorted(inds,
                      key=lambda x: x.get("year_inducted", 0), reverse=True)
        self._hof_bar.setText(
            "1000+ points / 500+ goals (skaters) \u2022 300+ wins "
            "(goalies) \u2022 icon-level reputation")
        self._clear_from(self._hof_layout, 1)
        if not inds:
            self._hof_layout.addWidget(self._empty_label(
                "No Hall of Famers yet.\n"
                "Players are inducted at retirement when they clear the bar."))
            return
        for ind in inds:
            try:
                pos = str(ind.get("position", "") or "")
                if "GOALIE" in pos.upper():
                    line = (f"{ind.get('games', 0)} GP, "
                            f"{ind.get('wins', 0)} W, "
                            f"{ind.get('shutouts', 0)} SO")
                else:
                    line = (f"{ind.get('games', 0)} GP, "
                            f"{ind.get('goals', 0)} G, "
                            f"{ind.get('assists', 0)} A, "
                            f"{ind.get('points', 0)} Pts")
                card = QFrame()
                card.setObjectName("tile")
                cl = QVBoxLayout(card)
                name = QLabel(f"{ind.get('name', '?')} ({pos})")
                name.setStyleSheet(
                    "font-size: 15px; font-weight: 700; color: #e8b34b;")
                year = QLabel(f"Inducted {ind.get('year_inducted', '?')}")
                year.setStyleSheet("color: #9aa4b8; font-size: 13px;")
                stat = QLabel(line)
                stat.setStyleSheet("color: #cdd6e4; font-size: 13px;")
                cl.addWidget(name)
                cl.addWidget(year)
                cl.addWidget(stat)
                if ind.get("cups"):
                    cups = QLabel(
                        f"\U0001F3C6 {ind.get('cups')}\u00d7 Stanley Cup")
                    cups.setStyleSheet("color: #f2f4f8; font-size: 13px;")
                    cl.addWidget(cups)
                if ind.get("awards"):
                    aw = QLabel(" · ".join(
                        str(a) for a in ind["awards"]))
                    aw.setWordWrap(True)
                    aw.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                    cl.addWidget(aw)
                self._hof_layout.addWidget(card)
            except Exception:
                continue

    # --- advanced stats -------------------------------------------------
    def _make_advanced_page(self):
        scroll, _inner, layout = self._scroll_host()
        hdr = QLabel("Team Advanced Metrics — 5v5 process")
        hdr.setObjectName("section-header")
        layout.addWidget(hdr)
        self._adv_note = QLabel("")
        self._adv_note.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        layout.addWidget(self._adv_note)
        self._adv_table = QTableWidget()
        self._adv_table.setColumnCount(9)
        self._adv_table.setHorizontalHeaderLabels(
            ["Team", "CF%", "FF%", "xGF%", "GF%", "PDO", "PP%", "PK%", "SRS"])
        self._adv_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._adv_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._adv_table.setSortingEnabled(True)
        self._adv_table.verticalHeader().setVisible(False)
        self._adv_table.setAlternatingRowColors(True)
        self._adv_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        layout.addWidget(self._adv_table)
        lh = QLabel("League Leaders — Advanced")
        lh.setObjectName("section-header")
        layout.addWidget(lh)
        self._adv_leaders_layout = QVBoxLayout()
        layout.addLayout(self._adv_leaders_layout)
        gh = QLabel("Glossary")
        gh.setObjectName("section-header")
        layout.addWidget(gh)
        self._adv_gloss_layout = QVBoxLayout()
        layout.addLayout(self._adv_gloss_layout)
        return scroll

    def _load_advanced(self):
        try:
            from advanced_metrics import (team_advanced,
                                          league_leaders_advanced, GLOSSARY)
        except Exception:
            self._adv_note.setText("Advanced metrics module unavailable.")
            return
        league = _league(self.game)
        teams = _safe(lambda: list(league.teams), []) or []
        rows = []
        for t in teams:
            try:
                m = team_advanced(t)
                rows.append((
                    _safe(lambda: t.team_name, "?"),
                    round(float(getattr(m, "cf_pct", 0) or 0), 1),
                    round(float(getattr(m, "ff_pct", 0) or 0), 1),
                    round(float(getattr(m, "xgf_pct", 0) or 0), 1),
                    round(float(getattr(m, "gf_pct", 0) or 0), 1),
                    round(float(getattr(m, "pdo", 0) or 0), 3),
                    round(float(getattr(m, "pp_pct", 0) or 0), 1),
                    round(float(getattr(m, "pk_pct", 0) or 0), 1),
                    round(float(getattr(m, "srs", 0) or 0), 2),
                ))
            except Exception:
                continue
        self._adv_table.setSortingEnabled(False)
        self._adv_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for col, val in enumerate(r):
                item = QTableWidgetItem(str(val))
                if col > 0:
                    try:
                        item.setData(Qt.UserRole, float(val))
                    except Exception:
                        pass
                self._adv_table.setItem(i, col, item)
        self._adv_table.setSortingEnabled(True)
        self._adv_note.setText(
            "Modeled estimates from attributes and production "
            "— not tracking data.")
        # advanced leaders
        self._clear_layout(self._adv_leaders_layout)
        players = _league_players(self.game)
        cats = [("ixG", "ixg"), ("xGF%", "xgf_pct"), ("Corsi%", "cf_pct"),
                ("PDO", "pdo"), ("P/60", "p_per60"),
                ("Game Score", "game_score"), ("GSAx", "gsax")]
        for label, cat in cats:
            try:
                rows_l = []
                for r in league_leaders_advanced(players, cat, limit=5) or []:
                    v = r["value"]
                    vs = (f"{v:.3f}" if cat == "pdo"
                          else f"{v:.1f}" if isinstance(v, float)
                          else str(v))
                    rows_l.append((str(r.get("name", "?")), vs))
                card = QFrame()
                card.setObjectName("tile")
                cl = QVBoxLayout(card)
                h = QLabel(label)
                h.setStyleSheet("font-size: 14px; font-weight: 700;")
                h.setToolTip(str(GLOSSARY.get(label, "")))
                cl.addWidget(h)
                for j, (nm, vs) in enumerate(rows_l):
                    rl = QLabel(f"{j + 1}. {nm} ({vs})")
                    rl.setStyleSheet("color: #cdd6e4; font-size: 13px;")
                    cl.addWidget(rl)
                if not rows_l:
                    cl.addWidget(self._empty_label("—"))
                self._adv_leaders_layout.addWidget(card)
            except Exception:
                continue
        # glossary
        self._clear_layout(self._adv_gloss_layout)
        try:
            gloss = dict(GLOSSARY or {})
        except Exception:
            gloss = {}
        for k, v in gloss.items():
            row = QFrame()
            row.setObjectName("tile")
            rl = QVBoxLayout(row)
            term = QLabel(str(k))
            term.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #e8b34b;")
            defin = QLabel(str(v))
            defin.setWordWrap(True)
            defin.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            rl.addWidget(term)
            rl.addWidget(defin)
            self._adv_gloss_layout.addWidget(row)

    # --- season reviews -------------------------------------------------
    def _make_reviews_page(self):
        scroll, _inner, layout = self._scroll_host()
        ctl = QHBoxLayout()
        club_lbl = QLabel("Club")
        club_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(club_lbl)
        self._reviews_team = QComboBox()
        self._reviews_team.currentIndexChanged.connect(
            lambda _i: self._load_reviews(init=False))
        ctl.addWidget(self._reviews_team)
        yr_lbl = QLabel("Season")
        yr_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        ctl.addWidget(yr_lbl)
        self._reviews_year = QComboBox()
        self._reviews_year.currentIndexChanged.connect(
            lambda _i: self._load_reviews(init=False))
        ctl.addWidget(self._reviews_year)
        ctl.addStretch()
        layout.addLayout(ctl)
        self._review_card = QLabel("")
        self._review_card.setWordWrap(True)
        self._review_card.setStyleSheet(
            "color: #cdd6e4; font-size: 14px;")
        layout.addWidget(self._review_card)
        self._reviews_page_inner = layout
        return scroll

    def _reviews_teams(self):
        league = _league(self.game)
        clubs = [t for t in (_safe(lambda: list(league.teams), []) or [])
                 if getattr(t, "league_name", "") == "National Hockey League"]
        names = sorted({_safe(lambda: t.team_name, "?") for t in clubs})
        user = _safe(lambda: getattr(_gm(self.game), "user_team", None))
        user_name = _safe(lambda: getattr(user, "team_name", ""), "")
        return clubs, names, user_name

    def _load_reviews(self, init=True):
        clubs, names, user_name = self._reviews_teams()
        tcombo, ycombo = self._reviews_team, self._reviews_year
        if init:
            tcombo.blockSignals(True)
            tcombo.clear()
            for n in names:
                tcombo.addItem(n, n)
            default = (user_name if user_name in names
                       else (names[0] if names else ""))
            if default:
                tcombo.setCurrentIndex(tcombo.findText(default))
            tcombo.blockSignals(False)
        team = tcombo.currentData() or ""
        club = next((t for t in clubs
                     if _safe(lambda: t.team_name, "") == team), None)
        archive = dict(getattr(club, "season_reviews", None) or {}) \
            if club is not None else {}
        years = sorted(archive.keys(), reverse=True)
        labels = [f"{archive[y].get('label', y)} ({y})" for y in years]
        ycombo.blockSignals(True)
        ycombo.clear()
        for lab, y in zip(labels, years):
            ycombo.addItem(lab, y)
        ycombo.blockSignals(False)
        year = ycombo.currentData()
        lines = []
        if year is not None:
            lines = list(archive.get(year, {}).get("lines", []) or [])
        self._review_card.setText(
            "\n".join(str(l) for l in lines) or
            "No season reviews archived for this club yet. "
            "They appear here at the end of each season.")

    # --- franchise records ----------------------------------------------
    def _make_records_page(self):
        scroll, _inner, layout = self._scroll_host()
        self._records_layout = layout
        return scroll

    def _load_records(self):
        hist = _hist(self.game)
        fr = _safe(lambda: getattr(hist, "franchise_records", None))
        layout = self._records_layout
        self._clear_layout(layout)
        cards = [
            ("Skater — Career", "career_records"),
            ("Skater — Season", "season_records"),
            ("Goalie — Career", "goalie_career_records"),
            ("Goalie — Season", "goalie_season_records"),
            ("Team — Season", "team_season_records"),
            ("Streaks", "streaks"),
        ]
        any_data = False
        for label, attr in cards:
            try:
                store = _safe(lambda: getattr(fr, attr, None), None) \
                    if fr is not None else None
                d = dict(store or {})
                franchises = len(d)
                records = sum(len(v or {}) for v in d.values())
                any_data = any_data or franchises > 0
                card = QFrame()
                card.setObjectName("tile")
                cl = QVBoxLayout(card)
                l = QLabel(label)
                l.setStyleSheet("font-size: 14px; font-weight: 700;")
                n = QLabel(str(records))
                n.setStyleSheet(
                    "font-size: 28px; font-weight: 700; color: #e8b34b;")
                f = QLabel(f"{franchises} franchises")
                f.setStyleSheet("color: #9aa4b8; font-size: 13px;")
                cl.addWidget(l)
                cl.addWidget(n)
                cl.addWidget(f)
                layout.addWidget(card)
            except Exception:
                continue
        if not any_data:
            layout.addWidget(self._empty_label(
                "No franchise records yet."))

    # ------------------------------------------------------------------
    # tab plumbing
    # ------------------------------------------------------------------
    def _on_tab_changed(self, idx):
        name = ["champions", "awards", "leaders", "hof", "advanced",
                "reviews", "records"][idx]
        if name not in self._loaded:
            self._loaded[name] = True
            self._load_tab(name)

    def _load_tab(self, name):
        loaders = {
            "champions": self._load_champions,
            "awards": self._load_awards,
            "leaders": self._load_leaders,
            "hof": self._load_hof,
            "advanced": self._load_advanced,
            "reviews": lambda: self._load_reviews(init=True),
            "records": self._load_records,
        }
        try:
            loaders[name]()
        except Exception as e:
            print(f"[history] {name} tab failed: {e}")

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                HistoryScreen._clear_layout(sub)

    def _clear_from(self, layout, start):
        # keep the first `start` items (controls row), clear the rest
        items = []
        while layout.count():
            items.append(layout.takeAt(0))
        kept = items[:start]
        for i in items[start:]:
            w = i.widget()
            if w is not None:
                w.deleteLater()
            sub = i.layout()
            if sub is not None:
                HistoryScreen._clear_layout(sub)
        for i in kept:
            layout.addItem(i)

    def refresh(self):
        # invalidate loaded state for the current tab so nav-returns refresh
        idx = self._tabs.currentIndex()
        name = ["champions", "awards", "leaders", "hof", "advanced",
                "reviews", "records"][idx]
        self._loaded.pop(name, None)
        self._loaded[name] = True
        self._load_tab(name)
