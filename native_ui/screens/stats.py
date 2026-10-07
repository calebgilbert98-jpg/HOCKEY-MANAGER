"""Stats Center screen: NHL leaders, AHL, franchise records, NHL records,
xG analytics.

Native port of web_ui/templates/stats.html +
web_ui/screens/stats.py + web_ui/static/js/stats.js. Calls the game object
DIRECTLY -- no Flask/HTTP, no JSON.

Top tabs (5) x leader sub-tabs (7) x NHL-record sub-tabs (6).
All data is real: league rosters, ahl_system/ahl_league, league_history,
record_manager, advanced_metrics, awards_race.
"""

from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _league(game):
    return _safe(lambda: _resolve_gm(game).league)


def _clean_position(pos):
    try:
        from web_ui.bridge import _clean_position as _cp
        return _cp(pos)
    except Exception:
        pass
    raw = getattr(pos, "value", pos)
    return str(raw or "?").strip()


def _is_goalie(p):
    try:
        pos = getattr(p, "primary_position", None)
        pname = getattr(pos, "name", str(pos))
        return "GOALIE" in str(pname).upper()
    except Exception:
        return False


def _pstat(p, field, default=0):
    """Authoritative season stat for a player.

    The sim writes season totals to p.stats (PlayerStats); the direct
    Player attributes (p.goals etc.) are legacy and never updated by the
    sim (see awards_race.py). Falls back to the direct attribute so
    non-Player objects and old saves still work.
    """
    st = getattr(p, "stats", None)
    if st is not None:
        v = getattr(st, field, None)
        if v is not None:
            return v
    return getattr(p, field, default)


def _pos_group(p):
    pos = _clean_position(getattr(p, "primary_position", ""))
    if pos.upper() == "G":
        return "G"
    if pos.upper() in ("LD", "RD", "D"):
        return "D"
    return "F"


def _leader_players(game):
    """All league (player, team_name) pairs."""
    league = _league(game)
    if league is None:
        return [], {}
    teams = _safe(lambda: list(league.teams), []) or []
    pairs, team_map = [], {}
    for t in teams:
        try:
            tname = _safe(lambda: t.team_name, "")
            if tname:
                team_map[tname] = t
            for p in _safe(lambda: list(t.roster), []) or []:
                pairs.append((p, tname))
        except Exception:
            continue
    return pairs, team_map


def _apply_leader_filters(pairs, pos="All", min_gp=0, team="All"):
    out = []
    for p, tname in pairs:
        try:
            if pos != "All" and _pos_group(p) != pos:
                continue
            gp = int(_pstat(p, "games_played") or 0)
            if gp < min_gp:
                continue
            if team != "All" and tname != team:
                continue
            out.append((p, tname))
        except Exception:
            continue
    return out


def _leader_row(p, tname, extra=None):
    pos = _safe(lambda: _clean_position(getattr(p, "primary_position", "")), "?")
    gp = int(_pstat(p, "games_played") or 0)
    g = int(_pstat(p, "goals") or 0)
    a = int(_pstat(p, "assists") or 0)
    row = {
        "player": p,
        "id": _safe(lambda: str(getattr(p, "id", id(p))), ""),
        "name": _safe(lambda: getattr(p, "full_name", "?"), "?") or "?",
        "team": tname, "pos": pos, "gp": gp, "g": g, "a": a,
        "pts": g + a,
        "ppg": round((g + a) / gp, 2) if gp else 0.0,
        "pm": int(_pstat(p, "plus_minus") or 0),
        "pim": int(_pstat(p, "penalty_minutes") or 0),
        "sog": int(_pstat(p, "shots") or getattr(p, "shots_on_goal", 0) or 0),
        "age": int(getattr(p, "age", 0) or 0),
        "is_goalie": _is_goalie(p),
    }
    if row["is_goalie"]:
        row["w"] = int(_pstat(p, "wins") or 0)
        row["l"] = int(_pstat(p, "losses") or 0)
        row["sv_pct"] = round(float(_pstat(p, "save_percentage") or 0), 3)
        row["gaa"] = round(float(_pstat(p, "goals_against_avg") or 0), 2)
        row["so"] = int(_pstat(p, "shutouts") or 0)
        row["sa"] = int(_pstat(p, "shots_against") or 0)
    if extra:
        row.update(extra)
    return row


def _pill_row(values, current, on_change):
    box = QWidget()
    h = QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    group = QButtonGroup(box)
    group.setExclusive(True)
    for v in values:
        b = QPushButton(v)
        b.setCheckable(True)
        b.setChecked(v == current)
        b.setStyleSheet(
            "QPushButton { border: 1px solid #33415e; border-radius: 12px;"
            " padding: 3px 10px; color: #9aa4b8; }"
            "QPushButton:checked { background: #2f6fed; color: white;"
            " border-color: #2f6fed; }")
        b.clicked.connect(lambda checked, _v=v: on_change(_v))
        group.addButton(b)
        h.addWidget(b)
    h.addStretch()
    return box


_MILESTONE_WATCH_SKATERS = [
    ('career_goals', 'goals', 'Goals', (100, 200, 300, 400, 500, 600, 700), 12),
    ('career_assists', 'assists', 'Assists', (200, 300, 400, 500, 600, 800, 1000), 12),
    ('career_points', 'points', 'Points', (500, 750, 1000, 1250, 1500), 18),
    ('career_games', 'games_played', 'Games Played', (500, 1000, 1500), 25),
]
_MILESTONE_WATCH_GOALIES = [
    ('career_wins', 'wins', 'Wins', (100, 200, 300), 8),
    ('career_shutouts', 'shutouts', 'Shutouts', (25, 50, 75, 100), 4),
    ('career_games_goalie', 'games_played', 'Games Played', (300, 500), 20),
]

_RECORD_LABELS = {
    "goals": "Goals", "assists": "Assists", "points": "Points",
    "games": "Games Played", "wins": "Wins", "shutouts": "Shutouts",
    "saves": "Saves", "save_pct": "Save %",
    "points_season": "Points", "wins_season": "Wins",
    "championships": "Stanley Cups",
}
_TEAM_RECORD_LABELS = {
    "wins": "Most Wins", "points": "Most Points", "goals_for": "Most Goals For",
    "goals_against": "Fewest Goals Against",
}

AWARDS = ["hart", "ted_lindsay", "art_ross", "rocket", "norris", "selke",
          "byng", "calder", "vezina", "jennings", "adams"]


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class StatsScreen(BaseScreen):
    title = "Stats"

    def __init__(self, game, main_window, parent=None):
        self.fpos = "All"
        self.fmin_gp = 0
        self.fteam = "All"
        self.ltab = "scoring"
        self.award = "hart"
        self.rtab = "season"
        super().__init__(game, main_window, parent)

    def _build_body(self):
        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs)

        self._nhl_page = QWidget()
        self.tabs.addTab(self._nhl_page, "NHL Leaders")
        self._build_nhl(self._nhl_page)

        self._ahl_page = QWidget()
        self.tabs.addTab(self._ahl_page, "AHL")
        self._build_ahl(self._ahl_page)

        self._records_page = QWidget()
        self.tabs.addTab(self._records_page, "Records")
        self._build_records(self._records_page)

        self._nhlrec_page = QWidget()
        self.tabs.addTab(self._nhlrec_page, "NHL Records")
        self._build_nhl_records(self._nhlrec_page)

        self._xg_page = QWidget()
        self.tabs.addTab(self._xg_page, "xG Analytics")
        self._build_xg(self._xg_page)

        self.tabs.currentChanged.connect(lambda _: self.refresh())

    # -- shared widget builders ------------------------------------------------

    def _make_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        # Keep headers readable when the table is empty: without a minimum,
        # resizeColumnsToContents() collapses columns and clips labels
        # ("Player" -> "laye").
        t.horizontalHeader().setMinimumSectionSize(70)
        t.cellClicked.connect(self._on_cell_clicked)
        t._row_players = {}  # row -> player object for click navigation
        return t

    def _on_cell_clicked(self, row, _col):
        table = self.sender()
        p = (getattr(table, "_row_players", {}) or {}).get(row)
        if p is None:
            return
        try:
            self.main_window.show_player(p)
        except Exception:
            try:
                self.navigate_to("player")
            except Exception:
                QMessageBox.information(
                    self, "Player",
                    "The player screen is not available in this build yet.")

    def _card(self, title, table):
        """GroupBox card with a section title."""
        box = QGroupBox(title)
        v = QVBoxLayout(box)
        v.addWidget(table)
        return box

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("section-header")
        return lbl

    def _empty(self, text="No data yet."):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; padding: 18px;")
        return lbl

    # -- tab 1: NHL leaders ----------------------------------------------------

    def _build_nhl(self, page):
        layout = QVBoxLayout(page)

        # global filters
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Pos"))
        frow.addWidget(_pill_row(["All", "F", "D", "G"], self.fpos,
                                 self._on_fpos))
        frow.addWidget(QLabel("Min GP"))
        self._min_gp_spin = QSpinBox()
        self._min_gp_spin.setRange(0, 200)
        self._min_gp_spin.setValue(self.fmin_gp)
        self._min_gp_spin.setFixedWidth(64)
        self._min_gp_spin.valueChanged.connect(self._on_min_gp)
        frow.addWidget(self._min_gp_spin)
        frow.addWidget(QLabel("Team"))
        self._team_combo = QComboBox()
        self._team_combo.currentTextChanged.connect(self._on_fteam)
        frow.addWidget(self._team_combo)
        frow.addStretch()
        layout.addLayout(frow)

        self._leader_tabs = QTabWidget()
        layout.addWidget(self._leader_tabs)

        self._sub_pages = {}
        for key, label in [("scoring", "Scoring"), ("advanced", "Advanced"),
                           ("goaltending", "Goaltending"),
                           ("breakout", "Breakout"), ("rookies", "Rookies"),
                           ("awards", "Award Races"),
                           ("milestones", "Milestones")]:
            pg = QWidget()
            pg.setLayout(QVBoxLayout())
            self._leader_tabs.addTab(pg, label)
            self._sub_pages[key] = pg
        self._leader_tabs.currentChanged.connect(self._on_leader_tab)

    def _on_leader_tab(self, idx):
        key = ["scoring", "advanced", "goaltending", "breakout", "rookies",
               "awards", "milestones"][idx]
        self.ltab = key
        self._render_nhl()

    def _on_fpos(self, v):
        self.fpos = v
        self._render_nhl()

    def _on_min_gp(self, v):
        self.fmin_gp = int(v)
        self._render_nhl()

    def _on_fteam(self, v):
        self.fteam = v if v != "All teams" else "All"
        self._render_nhl()

    def _populate_team_combo(self):
        self._team_combo.blockSignals(True)
        self._team_combo.clear()
        self._team_combo.addItem("All teams")
        names = sorted({tname for _p, tname in _leader_players(self.game)[0]
                        if tname})
        for n in names:
            self._team_combo.addItem(n)
        idx = self._team_combo.findText(
            "All teams" if self.fteam == "All" else self.fteam)
        self._team_combo.setCurrentIndex(max(0, idx))
        self._team_combo.blockSignals(False)

    def _render_nhl(self):
        self._populate_team_combo()
        render = {"scoring": self._render_scoring,
                  "advanced": self._render_advanced,
                  "goaltending": self._render_goaltending,
                  "breakout": self._render_breakout,
                  "rookies": self._render_rookies,
                  "awards": self._render_awards,
                  "milestones": self._render_milestones}[self.ltab]
        pg = self._sub_pages[self.ltab]
        while pg.layout().count():
            w = pg.layout().takeAt(0).widget()
            if w:
                w.deleteLater()
        try:
            render(pg)
        except Exception:
            pg.layout().addWidget(self._empty("Could not load leaders."))

    def _filtered_pairs(self):
        pairs, _ = _leader_players(self.game)
        return _apply_leader_filters(pairs, self.fpos, self.fmin_gp,
                                    self.fteam)

    def _fill_player_table(self, table, rows, cols, rank_col=True):
        """Fill a QTableWidget from leader-row dicts.

        cols: list of (key, header, fmt) where fmt(row)->str.
        """
        headers = (["#"] if rank_col else []) + ["Player"] + \
            [h for _, h, _ in cols]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        table._row_players = {}
        for i, r in enumerate(rows):
            off = 1 if rank_col else 0
            if rank_col:
                table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            name_item = QTableWidgetItem(
                f"{r['name']}  ·  {r.get('pos', '')}  ·  {r.get('team', '')}")
            table.setItem(i, off, name_item)
            table._row_players[i] = r.get("player")
            for j, (key, _h, fmt) in enumerate(cols):
                try:
                    txt = fmt(r)
                except Exception:
                    txt = ""
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(i, off + 1 + j, item)
        table.resizeColumnsToContents()

    def _render_scoring(self, pg):
        pairs = self._filtered_pairs()
        skaters = [_leader_row(p, t) for p, t in pairs
                   if not _is_goalie(p) and int(_pstat(p, "games_played") or 0) > 0]
        scorers = sorted(skaters, key=lambda r: (-r["pts"], -r["g"], -r["a"],
                                                 r["name"]))[:10]
        goals = sorted(skaters, key=lambda r: (-r["g"], -r["a"], -r["pts"],
                                               r["name"]))[:5]
        goalies = [_leader_row(p, t) for p, t in pairs if _is_goalie(p)]
        max_gp = max([g["gp"] for g in goalies] or [0])
        min_gp = max(3, int(max_gp * 0.15))
        goalie_leaders = sorted(
            [g for g in goalies if g["gp"] >= min_gp and g.get("sv_pct", 0) > 0],
            key=lambda r: (-r["sv_pct"], r["gaa"], r["name"]))[:5]

        skater_cols = [("gp", "GP", lambda r: str(r["gp"])),
                       ("g", "G", lambda r: str(r["g"])),
                       ("a", "A", lambda r: str(r["a"])),
                       ("pts", "PTS", lambda r: str(r["pts"])),
                       ("pm", "+/-", lambda r: ("+" if r["pm"] > 0 else "")
                        + str(r["pm"])),
                       ("pim", "PIM", lambda r: str(r["pim"]))]
        t1 = self._make_table([])
        self._fill_player_table(t1, scorers, skater_cols)
        t2 = self._make_table([])
        self._fill_player_table(t2, goals, skater_cols)
        t3 = self._make_table([])
        self._fill_player_table(t3, goalie_leaders,
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("sv_pct", "SV%",
                                 lambda r: f"{r['sv_pct']:.3f}"),
                                ("gaa", "GAA", lambda r: f"{r['gaa']:.2f}"),
                                ("so", "SO", lambda r: str(r["so"]))])
        pg.layout().addWidget(self._card("Scoring Leaders · Top 10", t1))
        pg.layout().addWidget(self._card("Goal Leaders · Top 5", t2))
        pg.layout().addWidget(self._card(
            f"Save % Leaders · Min {min_gp} GP", t3))

    def _render_advanced(self, pg):
        try:
            import advanced_metrics as am
        except Exception:
            pg.layout().addWidget(self._empty("Advanced metrics unavailable."))
            return
        skaters, goalies = [], []
        for p, tname in self._filtered_pairs():
            try:
                if _is_goalie(p):
                    m = am.goalie_advanced(p)
                    r = _leader_row(p, tname, {
                        "gsax": round(float(getattr(m, "gsax", 0) or 0), 1),
                        "hdsv": round(float(getattr(m, "hd_sv_pct", 0)
                                            or getattr(m, "hdsv_pct", 0)
                                            or 0), 3)})
                    goalies.append(r)
                else:
                    m = am.skater_advanced(p)
                    r = _leader_row(p, tname, {
                        "ixg": round(float(getattr(m, "ixg", 0) or 0), 1),
                        "cf_pct": round(float(getattr(m, "cf_pct", 0) or 0), 1),
                        "xgf_pct": round(float(getattr(m, "xgf_pct", 0) or 0), 1),
                        "pdo": round(float(getattr(m, "pdo", 0) or 0), 1),
                        "p_per60": round(float(getattr(m, "p_per60", 0) or 0), 2),
                        "game_score": round(float(getattr(m, "game_score", 0) or 0), 2),
                        "sh_pct": round(float(getattr(m, "sh_pct", 0) or 0), 1)})
                    skaters.append(r)
            except Exception:
                continue
        skaters.sort(key=lambda r: (-r.get("game_score", 0), -r["pts"]))
        goalies.sort(key=lambda r: (-r.get("gsax", 0), -r.get("sv_pct", 0)))
        t1 = self._make_table([])
        self._fill_player_table(t1, skaters[:100],
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("ixg", "ixG", lambda r: f"{r['ixg']:.1f}"),
                                ("cf_pct", "CF%", lambda r: f"{r['cf_pct']:.1f}"),
                                ("xgf_pct", "xGF%",
                                 lambda r: f"{r['xgf_pct']:.1f}"),
                                ("pdo", "PDO", lambda r: f"{r['pdo']:.1f}"),
                                ("p_per60", "P/60",
                                 lambda r: f"{r['p_per60']:.2f}"),
                                ("game_score", "GSc",
                                 lambda r: f"{r['game_score']:.2f}"),
                                ("sh_pct", "SH%",
                                 lambda r: f"{r['sh_pct']:.1f}")])
        t2 = self._make_table([])
        self._fill_player_table(t2, goalies[:50],
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("gsax", "GSAx", lambda r: f"{r['gsax']:.1f}"),
                                ("hdsv", "HDSV%",
                                 lambda r: f"{r['hdsv']:.3f}"),
                                ("sv_pct", "SV%",
                                 lambda r: f"{r['sv_pct']:.3f}"),
                                ("gaa", "GAA", lambda r: f"{r['gaa']:.2f}")])
        pg.layout().addWidget(self._card(
            "Advanced Stats · ixG / CF% / xGF% / PDO / P/60 / Game Score / SH%",
            t1))
        pg.layout().addWidget(self._card(
            "Goalie Advanced · GSAx / high-danger SV%", t2))

    def _render_goaltending(self, pg):
        try:
            import advanced_metrics as am
        except Exception:
            am = None
        rows = []
        for p, tname in self._filtered_pairs():
            if not _is_goalie(p):
                continue
            r = _leader_row(p, tname)
            if am is not None:
                try:
                    m = am.goalie_advanced(p)
                    r["gsax"] = round(float(getattr(m, "gsax", 0) or 0), 1)
                except Exception:
                    r["gsax"] = 0.0
            rows.append(r)
        rows.sort(key=lambda r: (-r.get("sv_pct", 0), r.get("gaa", 99)))
        t = self._make_table([])
        self._fill_player_table(t, rows[:50],
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("w", "W", lambda r: str(r["w"])),
                                ("sv_pct", "SV%",
                                 lambda r: f"{r['sv_pct']:.3f}"),
                                ("gaa", "GAA", lambda r: f"{r['gaa']:.2f}"),
                                ("gsax", "GSAx", lambda r: f"{r.get('gsax', 0):.1f}"),
                                ("so", "SO", lambda r: str(r["so"])),
                                ("sa", "SA", lambda r: str(r["sa"]))])
        pg.layout().addWidget(self._card("Goaltending Leaders · Traditional + GSAx", t))

    def _render_breakout(self, pg):
        try:
            import advanced_metrics as am
        except Exception:
            pg.layout().addWidget(self._empty("Advanced metrics unavailable."))
            return
        out = []
        for p, tname in self._filtered_pairs():
            try:
                if _is_goalie(p):
                    continue
                age = int(getattr(p, "age", 99) or 99)
                if age > 26:
                    continue
                m = am.skater_advanced(p)
                goals = int(_pstat(p, "goals") or 0)
                xgf_pct = float(getattr(m, "xgf_pct", 50) or 50)
                ixg = float(getattr(m, "ixg", 0) or 0)
                pdo = float(getattr(m, "pdo", 100) or 100)
                p60 = float(getattr(m, "p_per60", 0) or 0)
                score = ((xgf_pct - 50) * 2.0 + max(0, ixg - goals) * 1.5
                         + max(0, 100.0 - pdo) * 2.0
                         + max(0, 25 - age) * 1.2 + p60 * 3.0)
                signals = []
                if xgf_pct >= 55:
                    signals.append("Elite on-ice impact")
                if ixg - goals >= 3:
                    signals.append("Goals due (ixG > G)")
                if pdo < 98:
                    signals.append("Unlucky shooting/luck")
                if p60 >= 2.0:
                    signals.append("Top-line scoring rate")
                r = _leader_row(p, tname, {
                    "breakout_score": round(score, 1),
                    "xgf_pct": round(xgf_pct, 1),
                    "ixg_vs_g": round(ixg - goals, 1),
                    "pdo": round(pdo, 1),
                    "p_per60": round(p60, 2),
                    "signal": "; ".join(signals) or "Watch list"})
                out.append(r)
            except Exception:
                continue
        out.sort(key=lambda r: -r["breakout_score"])
        t = self._make_table([])
        self._fill_player_table(t, out[:50],
                               [("age", "Age", lambda r: str(r["age"])),
                                ("gp", "GP", lambda r: str(r["gp"])),
                                ("pts", "PTS", lambda r: str(r["pts"])),
                                ("xgf_pct", "xGF%",
                                 lambda r: f"{r['xgf_pct']:.1f}"),
                                ("ixg_vs_g", "ixG-G",
                                 lambda r: f"{r['ixg_vs_g']:+.1f}"),
                                ("pdo", "PDO", lambda r: f"{r['pdo']:.1f}"),
                                ("p_per60", "P/60",
                                 lambda r: f"{r['p_per60']:.2f}"),
                                ("signal", "Signal",
                                 lambda r: str(r["signal"]))])
        pg.layout().addWidget(self._card(
            "Breakout Players · Age ≤ 26 · elite process + regression signals",
            t))

    def _render_rookies(self, pg):
        try:
            import awards_race as ar
        except Exception:
            pg.layout().addWidget(self._empty("Awards module unavailable."))
            return
        pairs, _ = _leader_players(self.game)
        players = [p for p, _ in pairs]
        d = _safe(lambda: _resolve_gm(self.game).current_date)
        syr = ar.calder_season_year(d) if d is not None else None

        def _row(r, goalie=False):
            p = r["player"]
            tname = (_safe(lambda: p.team.team_name, "")
                     or _safe(lambda: getattr(p, "team_name", ""), ""))
            base = _leader_row(p, tname)
            if goalie:
                base["sv_pct"] = round(float(r.get("sv_pct", 0) or 0), 3)
                base["gaa"] = round(float(r.get("gaa", 0) or 0), 2)
                base["w"] = int(r.get("wins", 0) or 0)
            else:
                base["g"] = int(r.get("goals", 0) or 0)
                base["a"] = int(r.get("assists", 0) or 0)
                base["pts"] = int(r.get("points", 0) or 0)
                base["gp"] = int(r.get("gp", 0) or 0)
            return base

        sk = [_row(r) for r in ar.rookie_skaters(players, season_year=syr)[:25]]
        gl = [_row(r, goalie=True)
              for r in ar.rookie_goalies(players, season_year=syr)[:15]]
        t1 = self._make_table([])
        self._fill_player_table(t1, sk,
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("g", "G", lambda r: str(r["g"])),
                                ("a", "A", lambda r: str(r["a"])),
                                ("pts", "P", lambda r: str(r["pts"]))])
        t2 = self._make_table([])
        self._fill_player_table(t2, gl,
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("w", "W", lambda r: str(r["w"])),
                                ("sv_pct", "SV%",
                                 lambda r: f"{r['sv_pct']:.3f}"),
                                ("gaa", "GAA", lambda r: f"{r['gaa']:.2f}")])
        pg.layout().addWidget(self._card("Rookie Scoring · Calder eligible", t1))
        pg.layout().addWidget(self._card("Rookie Goaltending", t2))

    def _render_awards(self, pg):
        try:
            import awards_race as ar
        except Exception:
            pg.layout().addWidget(self._empty("Awards module unavailable."))
            return
        defs = [(n, d, k) for n, d, k in ar.AWARD_DEFINITIONS]
        keys = [k for _, _, k in defs]
        award = self.award if self.award in keys else (keys[0] if keys else "hart")
        name = next((n for n, _, k in defs if k == award), award)
        desc = next((d for _, d, k in defs if k == award), "")

        pills = _pill_row(keys, award,
                          lambda v: (setattr(self, "award", v),
                                     self._render_nhl()))
        pg.layout().addWidget(pills)
        desc_lbl = QLabel(f"{name}: {desc}")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #9aa4b8;")
        pg.layout().addWidget(desc_lbl)

        pairs, team_map = _leader_players(self.game)
        players = [p for p, _ in pairs]
        roster_map = ar.roster_team_map(list(team_map.values()))
        team_pct = {}
        for tname, t in team_map.items():
            gp = getattr(t, "games_played", 0) or 0
            pts = getattr(t, "points", 0) or 0
            team_pct[tname] = (pts / (2 * gp)) if gp else 0.5
        d = _safe(lambda: _resolve_gm(self.game).current_date)

        race = []
        try:
            if award == "hart":
                race = ar.hart_race(players, team_pct, roster_map=roster_map)
            elif award == "ted_lindsay":
                race = ar.lindsay_race(players, team_pct, roster_map=roster_map)
            elif award == "art_ross":
                race = ar.art_ross_race(players)
            elif award == "rocket":
                race = ar.rocket_race(players)
            elif award == "norris":
                race = ar.norris_race(players)
            elif award == "selke":
                race = ar.selke_race(players)
            elif award == "byng":
                race = ar.byng_race(players)
            elif award == "calder":
                syr = ar.calder_season_year(d) if d is not None else None
                race = ar.calder_race(players, season_year=syr)
            elif award == "vezina":
                race = ar.vezina_race([p for p in players if _is_goalie(p)])
            elif award == "jennings":
                race = ar.jennings_race(list(team_map.values()))
            elif award == "adams":
                race = ar.adams_race(list(team_map.values()))
        except Exception:
            race = []

        rows = []
        for i, r in enumerate(race[:15], 1):
            p = r.get("player")
            tname = ""
            if p is not None:
                pid = int(getattr(p, "id", -1) or -1)
                tname = roster_map.get(pid, "") or \
                    _safe(lambda: getattr(p, "team_name", ""), "")
            nm = (r.get("name")
                  or (_safe(lambda: getattr(p, "full_name", "?"), "?")
                      if p is not None else "?"))
            rows.append({"player": p, "rank": i, "name": nm, "team": tname,
                         "score": round(float(r.get("score", 0) or 0), 1),
                         "detail": str(r.get("detail", "")
                                       or r.get("note", "") or "")})

        t = self._make_table([])
        t.setColumnCount(5)
        t.setHorizontalHeaderLabels(["#", "Candidate", "Team", "Score", "Case"])
        t.setRowCount(len(rows))
        t._row_players = {}
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["rank"])))
            t.setItem(i, 1, QTableWidgetItem(r["name"]))
            t.setItem(i, 2, QTableWidgetItem(r["team"]))
            sc = QTableWidgetItem(str(r["score"]))
            sc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(i, 3, sc)
            t.setItem(i, 4, QTableWidgetItem(r["detail"]))
            if r["player"] is not None:
                t._row_players[i] = r["player"]
        t.resizeColumnsToContents()
        pg.layout().addWidget(self._card(f"{name} · Top 15 candidates", t))

    def _render_milestones(self, pg):
        pairs, _ = _leader_players(self.game)
        watch = []
        for p, tname in pairs:
            try:
                is_g = _is_goalie(p)
                defs = _MILESTONE_WATCH_GOALIES if is_g \
                    else _MILESTONE_WATCH_SKATERS
                pos = _clean_position(getattr(p, "primary_position", ""))
                for career_attr, season_attr, label, marks, within in defs:
                    current = getattr(p, career_attr, 0) or 0
                    if current <= 0:
                        continue
                    upcoming = [m for m in marks if m > current]
                    if not upcoming:
                        continue
                    target = upcoming[0]
                    needed = target - current
                    if needed <= within:
                        watch.append({
                            "player": p,
                            "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                            "team": tname, "pos": pos,
                            "milestone": f"{target} {label}",
                            "current": int(current), "needed": int(needed),
                            "season": int(getattr(p, season_attr, 0) or 0)})
            except Exception:
                continue
        watch.sort(key=lambda w: (w["needed"], -w["current"]))
        t = self._make_table([])
        t.setColumnCount(5)
        t.setHorizontalHeaderLabels(["Player", "Milestone", "Current",
                                     "Needed", "This Season"])
        rows = watch[:40]
        t.setRowCount(len(rows))
        t._row_players = {}
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(
                f"{r['name']}  ·  {r['pos']}  ·  {r['team']}"))
            t.setItem(i, 1, QTableWidgetItem(r["milestone"]))
            for j, k in enumerate(("current", "needed", "season"), start=2):
                it = QTableWidgetItem(str(r[k]))
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(i, j, it)
            if r.get("player") is not None:
                t._row_players[i] = r["player"]
        t.resizeColumnsToContents()
        pg.layout().addWidget(self._card(
            "Milestone Watch · players closing in on career marks", t))

    # -- tab 2: AHL ------------------------------------------------------------

    def _build_ahl(self, page):
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self._ahl_skaters_table = self._make_table([])
        self._ahl_goalies_table = self._make_table([])
        row.addWidget(self._card("AHL Scoring · Top 25",
                                 self._ahl_skaters_table))
        row.addWidget(self._card("AHL Goalies · Top 15 · Min 5 GP",
                                 self._ahl_goalies_table))
        layout.addLayout(row)
        self._ahl_standings_table = self._make_table([])
        layout.addWidget(self._card("AHL Standings", self._ahl_standings_table))

    def _render_ahl(self):
        try:
            from ahl_system import top_skaters, top_goalies
            from ahl_league import get_ahl_standings, ahl_team_list
        except Exception:
            for t in (self._ahl_skaters_table, self._ahl_goalies_table,
                      self._ahl_standings_table):
                t.setRowCount(0)
            return
        league = _league(self.game)
        if league is None:
            return

        def _row(p, team_name, ledger, goalie=False):
            def _n(a, d=0):
                try:
                    return float(getattr(ledger, a, d) or 0)
                except Exception:
                    return d
            pos = _safe(lambda: _clean_position(
                getattr(p, "primary_position", "")), "?")
            gp = int(_n("games_played"))
            base = {"player": p, "name": _safe(
                lambda: getattr(p, "full_name", "?"), "?") or "?",
                "team": team_name, "pos": pos, "gp": gp}
            if goalie:
                sv = _n("saves"); sa = _n("shots_against")
                base.update({"w": int(_n("wins")),
                             "sv_pct": round(sv / sa, 3) if sa else 0.0,
                             "gaa": round(_n("goals_against_avg"), 2),
                             "so": int(_n("shutouts"))})
            else:
                g = int(_n("goals")); a = int(_n("assists"))
                base.update({"g": g, "a": a, "pts": g + a,
                             "pim": int(_n("penalty_minutes"))})
            return base

        skaters, goalies, standings = [], [], []
        try:
            for p, tname, ledger in top_skaters(league, limit=25):
                skaters.append(_row(p, tname, ledger))
        except Exception:
            pass
        try:
            for p, tname, ledger in top_goalies(league, limit=15, min_gp=5):
                goalies.append(_row(p, tname, ledger, goalie=True))
        except Exception:
            pass
        try:
            teams = ahl_team_list(league)
            for idx, rec in get_ahl_standings(league):
                tname = ""
                try:
                    tname = teams[idx].team_name if 0 <= idx < len(teams) else ""
                except Exception:
                    pass
                standings.append({
                    "team": tname,
                    "gp": int(rec.get("gp", 0) or 0),
                    "w": int(rec.get("w", 0) or 0),
                    "l": int(rec.get("l", 0) or 0),
                    "otl": int(rec.get("otl", 0) or 0),
                    "pts": int(rec.get("pts", 0) or 0),
                    "gf": int(rec.get("gf", 0) or 0),
                    "ga": int(rec.get("ga", 0) or 0)})
        except Exception:
            pass

        self._fill_player_table(self._ahl_skaters_table, skaters,
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("g", "G", lambda r: str(r["g"])),
                                ("a", "A", lambda r: str(r["a"])),
                                ("pts", "PTS", lambda r: str(r["pts"])),
                                ("pim", "PIM", lambda r: str(r["pim"]))])
        self._fill_player_table(self._ahl_goalies_table, goalies,
                               [("gp", "GP", lambda r: str(r["gp"])),
                                ("w", "W", lambda r: str(r["w"])),
                                ("sv_pct", "SV%",
                                 lambda r: f"{r['sv_pct']:.3f}"),
                                ("gaa", "GAA", lambda r: f"{r['gaa']:.2f}"),
                                ("so", "SO", lambda r: str(r["so"]))])
        t = self._ahl_standings_table
        t.setColumnCount(9)
        t.setHorizontalHeaderLabels(["#", "Team", "GP", "W", "L", "OTL",
                                     "PTS", "GF", "GA"])
        t.setRowCount(len(standings))
        t._row_players = {}
        for i, r in enumerate(standings):
            vals = [str(i + 1), r["team"], str(r["gp"]), str(r["w"]),
                    str(r["l"]), str(r["otl"]), str(r["pts"]), str(r["gf"]),
                    str(r["ga"])]
            for c, val in enumerate(vals):
                t.setItem(i, c, QTableWidgetItem(val))
        t.resizeColumnsToContents()

    # -- tab 3: franchise records ------------------------------------------------

    def _build_records(self, page):
        layout = QVBoxLayout(page)
        self._records_scroll = QScrollArea()
        self._records_scroll.setWidgetResizable(True)
        self._records_host = QWidget()
        self._records_layout = QVBoxLayout(self._records_host)
        self._records_scroll.setWidget(self._records_host)
        layout.addWidget(self._records_scroll)

    def _records_payload(self):
        live = self.game
        hist = _safe(lambda: getattr(live, "league_history", None))
        if hist is None:
            hist = _safe(lambda: getattr(_resolve_gm(live), "league_history", None))
        if hist is None:
            return {"teams": [], "champions": [], "empty": True}
        fr = _safe(lambda: hist.franchise_records)
        if fr is None:
            return {"teams": [], "champions": [], "empty": True}

        def _fmt_rec(rec):
            if not isinstance(rec, dict):
                return None
            v = rec.get("value", 0)
            try:
                v = round(float(v), 3) if float(v) != int(float(v)) \
                    else int(float(v))
            except Exception:
                pass
            return {"player": rec.get("player", "?"),
                    "player_id": rec.get("player_id"),
                    "value": v, "season": rec.get("season", "")}

        teams = []
        try:
            stores = [("career_records", "Skater — Career"),
                      ("season_records", "Skater — Single Season"),
                      ("goalie_career_records", "Goalie — Career"),
                      ("goalie_season_records", "Goalie — Single Season")]
            all_teams = set()
            for attr, _ in stores:
                all_teams |= set(_safe(lambda: getattr(fr, attr, {}).keys(),
                                       []) or [])
            all_teams |= set(_safe(lambda: getattr(
                fr, "team_season_records", {}).keys(), []) or [])
            for tname in sorted(all_teams):
                groups = []
                for attr, label in stores:
                    store = _safe(lambda: getattr(fr, attr, {}).get(tname, {}),
                                  {}) or {}
                    cats = []
                    for cat, rec in store.items():
                        r = _fmt_rec(rec)
                        if r:
                            r["category"] = _RECORD_LABELS.get(
                                cat, cat.replace("_", " ").title())
                            cats.append(r)
                    if cats:
                        groups.append({"label": label, "records": cats})
                tstore = _safe(lambda: getattr(
                    fr, "team_season_records", {}).get(tname, {}), {}) or {}
                tcats = []
                for cat, rec in tstore.items():
                    r = _fmt_rec(rec)
                    if r:
                        r["category"] = _TEAM_RECORD_LABELS.get(
                            cat, cat.replace("_", " ").title())
                        tcats.append(r)
                if tcats:
                    groups.append({"label": "Team — Single Season",
                                   "records": tcats})
                if groups:
                    teams.append({"team": tname, "groups": groups})
        except Exception:
            pass

        champions = []
        try:
            for s in hist.champions_list():
                champions.append({"year": s.get("year"),
                                  "champion": s.get("champion"),
                                  "runner_up": s.get("runner_up"),
                                  "series": s.get("series_score"),
                                  "smythe": s.get("conn_smythe")})
        except Exception:
            pass
        return {"teams": teams, "champions": champions,
                "empty": not teams and not champions}

    def _render_records(self):
        while self._records_layout.count():
            w = self._records_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        data = self._records_payload()

        # champions card
        champ_box = QGroupBox("Stanley Cup Champions")
        cv = QVBoxLayout(champ_box)
        ct = self._make_table(["Season", "Champion", "Runner-up", "Series",
                               "Conn Smythe"])
        ct.setRowCount(len(data["champions"]))
        for i, r in enumerate(data["champions"]):
            vals = [str(r["year"] or ""), str(r["champion"] or "—"),
                    str(r["runner_up"] or "—"), str(r["series"] or "—"),
                    str(r["smythe"] or "—")]
            for c, val in enumerate(vals):
                ct.setItem(i, c, QTableWidgetItem(val))
        ct.resizeColumnsToContents()
        cv.addWidget(ct if data["champions"] else self._empty(
            "No completed seasons on record yet."))
        self._records_layout.addWidget(champ_box)

        if not data["teams"]:
            self._records_layout.addWidget(self._empty(
                "The record book is empty — records are written as seasons "
                "complete."))
        for tm in data["teams"]:
            box = QGroupBox(f"{tm['team']} · Franchise records")
            bv = QVBoxLayout(box)
            for g in tm["groups"]:
                bv.addWidget(QLabel(f"<b>{g['label']}</b>"))
                t = self._make_table(["Category", "Holder", "Value"])
                t.setRowCount(len(g["records"]))
                for i, r in enumerate(g["records"]):
                    cat = r["category"] + \
                        (f"  ({r['season']})" if r.get("season") else "")
                    t.setItem(i, 0, QTableWidgetItem(cat))
                    t.setItem(i, 1, QTableWidgetItem(str(r["player"])))
                    val = QTableWidgetItem(str(r["value"]))
                    val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    t.setItem(i, 2, val)
                t.resizeColumnsToContents()
                bv.addWidget(t)
            self._records_layout.addWidget(box)
        self._records_layout.addStretch()

    # -- tab 4: NHL records -------------------------------------------------------

    def _build_nhl_records(self, page):
        layout = QVBoxLayout(page)
        self._nhlrec_tabs = QTabWidget()
        layout.addWidget(self._nhlrec_tabs)
        self._nhlrec_pages = {}
        for key, label in [("season", "Season Records"),
                           ("career", "Career Records"),
                           ("team", "Team Records"),
                           ("special", "Special"),
                           ("chase", "Record Chase"),
                           ("achievements", "Achievements")]:
            pg = QWidget()
            pg.setLayout(QVBoxLayout())
            self._nhlrec_tabs.addTab(pg, label)
            self._nhlrec_pages[key] = pg
        self._nhlrec_tabs.currentChanged.connect(self._on_nhlrec_tab)

    def _on_nhlrec_tab(self, idx):
        self.rtab = ["season", "career", "team", "special", "chase",
                     "achievements"][idx]
        self._render_nhl_records()

    def _nhl_records_payload(self):
        gm = _resolve_gm(self.game)
        rm = _safe(lambda: getattr(gm, "record_manager", None))
        nhl = _safe(lambda: getattr(rm, "nhl_records", None))
        records = _safe(lambda: dict(getattr(nhl, "records", None) or {}),
                        {}) or {}
        if not records:
            return {"empty": True, "season": [], "career": [], "team": [],
                    "special": [], "chase": [], "achievements": [], "total": 0}

        def _entry(e):
            try:
                return {"player": getattr(e, "player_name", "?"),
                        "value": getattr(e, "value", 0),
                        "season": getattr(e, "season", ""),
                        "team": getattr(e, "team", ""),
                        "games": getattr(e, "games_played", None),
                        "info": getattr(e, "additional_info", "") or ""}
            except Exception:
                return None

        def _label(key):
            return key.replace("single_season_", "").replace("career_", "") \
                .replace("team_", "").replace("_", " ").title()

        season, career, team_recs, special = [], [], [], []
        for key, rec in records.items():
            try:
                main = (getattr(rec, "single_season", None)
                        or getattr(rec, "all_time", None) or rec)
                row = {"key": key, "label": _label(key),
                       "record": _entry(main)}
                rookie = getattr(rec, "rookie_record", None)
                if rookie is not None:
                    row["rookie_record"] = _entry(rookie)
                if key.startswith("single_season_"):
                    season.append(row)
                elif key.startswith("career_"):
                    career.append(row)
                elif key.startswith("team_"):
                    team_recs.append(row)
                else:
                    special.append(row)
            except Exception:
                continue

        # Record chase: players >= 25% toward a season record.
        chase = []
        try:
            pairs, _ = _leader_players(self.game)
            chase_cats = [
                ("single_season_goals", "Goals",
                 lambda p: int(_pstat(p, "goals") or 0)),
                ("single_season_assists", "Assists",
                 lambda p: int(_pstat(p, "assists") or 0)),
                ("single_season_points", "Points",
                 lambda p: (int(_pstat(p, "goals") or 0)
                            + int(_pstat(p, "assists") or 0))),
                ("single_season_wins", "Wins",
                 lambda p: int(_pstat(p, "wins") or 0)),
                ("single_season_shutouts", "Shutouts",
                 lambda p: int(_pstat(p, "shutouts") or 0)),
            ]
            for key, label, fn in chase_cats:
                rec = records.get(key)
                entry = (getattr(rec, "single_season", None)
                         or getattr(rec, "all_time", None) or rec)
                target = getattr(entry, "value", 0) or 0
                if not target:
                    continue
                for p, tname in pairs:
                    try:
                        cur = fn(p)
                        if cur <= 0:
                            continue
                        pct = cur / target * 100
                        if pct >= 25.0:
                            chase.append({
                                "player": p,
                                "name": _safe(lambda: getattr(
                                    p, "full_name", "?"), "?"),
                                "team": tname,
                                "pos": _clean_position(
                                    getattr(p, "primary_position", "")),
                                "record": label, "current": cur,
                                "target": target, "needed": target - cur,
                                "pct": round(pct, 1)})
                    except Exception:
                        continue
            chase.sort(key=lambda c: -c["pct"])
            chase = chase[:20]
        except Exception:
            pass

        achievements = []
        try:
            for r in _safe(lambda: rm.get_recent_records(20), []) or []:
                if isinstance(r, dict):
                    achievements.append({
                        "date": str(r.get("date", "") or ""),
                        "player": str(r.get("player",
                                            r.get("player_name", "")) or ""),
                        "record": str(r.get("record",
                                            r.get("record_type", "")) or ""),
                        "value": r.get("value", ""),
                        "previous": r.get("previous", "")})
        except Exception:
            pass
        return {"empty": False, "season": season, "career": career,
                "team": team_recs, "special": special, "chase": chase,
                "achievements": achievements,
                "total": len(season) + len(career) + len(team_recs)
                + len(special)}

    def _render_nhl_records(self):
        data = self._nhl_records_payload()
        pg = self._nhlrec_pages[self.rtab]
        while pg.layout().count():
            w = pg.layout().takeAt(0).widget()
            if w:
                w.deleteLater()

        def _fmt_entry(e):
            if not e:
                return "—"
            s = f"{e['player']}: {e['value']} ({e['season']}) · {e['team']}"
            if e.get("games"):
                s += f"  [{e['games']} GP]"
            return s

        if self.rtab == "chase":
            t = self._make_table([])
            t.setColumnCount(7)
            t.setHorizontalHeaderLabels(["#", "Player", "Record", "Current",
                                         "Target", "Needed", "Progress"])
            rows = data["chase"]
            t.setRowCount(len(rows))
            t._row_players = {}
            for i, r in enumerate(rows):
                t.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                t.setItem(i, 1, QTableWidgetItem(
                    f"{r['name']}  ·  {r['pos']}  ·  {r['team']}"))
                t.setItem(i, 2, QTableWidgetItem(r["record"]))
                for j, k in enumerate(("current", "target", "needed"),
                                      start=3):
                    it = QTableWidgetItem(str(r[k]))
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    t.setItem(i, j, it)
                t.setItem(i, 6, QTableWidgetItem(f"{r['pct']}%"))
                if r.get("player") is not None:
                    t._row_players[i] = r["player"]
            t.resizeColumnsToContents()
            pg.layout().addWidget(self._card(
                "Record Chase · 25%+ progress toward a record", t))
        elif self.rtab == "achievements":
            t = self._make_table([])
            t.setColumnCount(5)
            t.setHorizontalHeaderLabels(["Date", "Player", "Record",
                                         "New Value", "Previous"])
            rows = data["achievements"]
            t.setRowCount(len(rows))
            t._row_players = {}
            for i, r in enumerate(rows):
                vals = [r["date"], r["player"], r["record"],
                        str(r["value"]), str(r["previous"])]
                for c, val in enumerate(vals):
                    t.setItem(i, c, QTableWidgetItem(val))
            t.resizeColumnsToContents()
            pg.layout().addWidget(self._card(
                "Achievements · records broken this career", t))
        else:
            rows = data.get(self.rtab, [])
            t = self._make_table([])
            t.setColumnCount(3)
            t.setHorizontalHeaderLabels(["Record", "Holder", "Rookie Record"])
            t.setRowCount(len(rows))
            t._row_players = {}
            for i, r in enumerate(rows):
                t.setItem(i, 0, QTableWidgetItem(r["label"]))
                t.setItem(i, 1, QTableWidgetItem(_fmt_entry(r.get("record"))))
                t.setItem(i, 2, QTableWidgetItem(
                    _fmt_entry(r.get("rookie_record")) if r.get("rookie_record")
                    else "—"))
            t.resizeColumnsToContents()
            label = {"season": "Season Records", "career": "Career Records",
                     "team": "Team Records",
                     "special": "Special Records"}[self.rtab]
            pg.layout().addWidget(self._card(
                f"{label} · {data.get('total', 0)} official records", t))

    # -- tab 5: xG analytics ----------------------------------------------------

    def _build_xg(self, page):
        layout = QVBoxLayout(page)
        self._xg_scroll = QScrollArea()
        self._xg_scroll.setWidgetResizable(True)
        self._xg_host = QWidget()
        self._xg_layout = QVBoxLayout(self._xg_host)
        self._xg_scroll.setWidget(self._xg_host)
        layout.addWidget(self._xg_scroll)

    @staticmethod
    def _zone_from_coords(x, y, attacking_right=True):
        x, y = float(x or 0), float(y or 0)
        dist = ((100 - x) ** 2 + y ** 2) ** 0.5 if attacking_right \
            else ((x) ** 2 + y ** 2) ** 0.5
        ax = 100 - x if attacking_right else x
        if dist <= 12:
            return "crease"
        if abs(y) <= 15 and ax <= 30:
            return "low_slot"
        if abs(y) <= 30 and ax <= 55:
            return "high_slot"
        if ax <= 70 and abs(y) > 15:
            return "right_circle" if y < 0 else "left_circle"
        if ax <= 100:
            return "point"
        if ax <= 130:
            return "right_wing" if y < 0 else "left_wing"
        return "behind_net"

    def _render_xg(self):
        while self._xg_layout.count():
            w = self._xg_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        gm = _resolve_gm(self.game)
        store = _safe(lambda: getattr(gm, "shot_chart_store", None))
        games = _safe(lambda: list(getattr(store, "games", []) or []), []) or []
        if not games:
            self._xg_layout.addWidget(self._empty(
                "No tracked games yet — watch a game to generate analytics."))
            return
        g = games[-1]
        home = g.get("home", "Home"); away = g.get("away", "Away")
        shots = g.get("shots", []) or []
        try:
            import analytics as _an
            xg_fn = _an.shot_xg
        except Exception:
            xg_fn = None
        total_xg, n_goals = 0.0, 0
        zone_counts, zone_xg = {}, {}
        for s in shots:
            try:
                side = str(s.get("side", "")).lower()
                zone = self._zone_from_coords(s.get("x"), s.get("y"),
                                              attacking_right=side in
                                              ("right", "r", "away"))
                xg = xg_fn(zone) if xg_fn else 0.0
                total_xg += xg
                zone_counts[zone] = zone_counts.get(zone, 0) + 1
                zone_xg[zone] = round(zone_xg.get(zone, 0.0) + xg, 2)
                if str(s.get("result", "")).lower() == "goal":
                    n_goals += 1
            except Exception:
                continue

        head = QLabel(
            f"<b>Expected Goals</b> · Archived game · {away} @ {home}"
            f"{' · ' + str(g.get('date')) if g.get('date') else ''}")
        head.setObjectName("section-header")
        self._xg_layout.addWidget(head)
        tot = QLabel(f"<b>{total_xg:.2f}</b> xG · {len(shots)} shots · "
                     f"{n_goals} goals")
        tot.setStyleSheet("font-size: 18px;")
        self._xg_layout.addWidget(tot)

        zt = self._make_table(["Zone", "Shots", "xG"])
        rows = sorted(zone_counts.items(), key=lambda kv: -kv[1])
        zt.setRowCount(len(rows))
        zt._row_players = {}
        for i, (z, c) in enumerate(rows):
            zt.setItem(i, 0, QTableWidgetItem(z.replace("_", " ")))
            zt.setItem(i, 1, QTableWidgetItem(str(c)))
            zt.setItem(i, 2, QTableWidgetItem(f"{zone_xg.get(z, 0.0):.2f}"))
        zt.resizeColumnsToContents()
        self._xg_layout.addWidget(self._card("Shot Quality by Zone", zt))

        report = (f"Final tracked: {home} vs {away}.\n"
                  f"Total expected goals: {total_xg:.2f} on {len(shots)} "
                  f"attempts.\nArchived shot charts predate team attribution, "
                  f"so xG is shown game-wide — watch a game live for the "
                  f"per-team split.")
        rpt = QLabel(report)
        rpt.setWordWrap(True)
        self._xg_layout.addWidget(self._card("Analyst Report", rpt))
        self._xg_layout.addStretch()

    # -- refresh -----------------------------------------------------------------

    def refresh(self):
        self._render_nhl()
        self._render_ahl()
        self._render_records()
        self._render_nhl_records()
        self._render_xg()
