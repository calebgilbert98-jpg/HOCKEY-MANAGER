"""Standings screen: league standings with 4 tabs (overview, team analytics,
division analysis, divisions grid).

Native port of web_ui/templates/standings.html +
web_ui/screens/standings.py + web_ui/static/js/standings.js. Calls the game
object DIRECTLY -- no Flask/HTTP, no JSON.

Game attributes used (all real, same as the web bridge read):
  - game / game.game_manager -> gm.league
  - league.standings (dict: team name -> {W, L, OTL, Points})
  - league.teams (list of Team: team_name, conference, division,
    goals_for, goals_against, streak, is_user_team, power_play_pct,
    penalty_kill_pct, team_gaa, team_save_pct)
  - league.schedule (list of dicts with home_team/away_team/played)
  - league.user_team
"""

from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
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
    gm = _resolve_gm(game)
    return _safe(lambda: gm.league)


def _rich_team_rows(game):
    """One row per team: W/L/OTL/PTS, GF/GA/diff, PT%, streak, conf/div.
    Mirrors the web bridge's _rich_team_rows."""
    league = _league(game)
    if league is None:
        return [], None
    table = _safe(lambda: dict(league.standings), {}) or {}
    teams = _safe(lambda: list(league.teams), []) or []
    user_team_name = (_safe(lambda: league.user_team.team_name)
                      or _safe(lambda: getattr(game, "user_team", None)
                               and game.user_team.team_name))

    rows = []
    for t in teams:
        try:
            name = _safe(lambda: t.team_name, "")
            if not name:
                continue
            row = _safe(lambda: table.get(name), {}) or {}
            w = _safe(lambda: int(row.get("W", 0) or 0), 0)
            l = _safe(lambda: int(row.get("L", 0) or 0), 0)
            otl = _safe(lambda: int(row.get("OTL", 0) or 0), 0)
            pts = _safe(lambda: int(row.get("Points", 0) or 0), 0)
            gf = _safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0)
            ga = _safe(lambda: int(getattr(t, "goals_against", 0) or 0), 0)
            gp = w + l + otl
            rows.append({
                "name": name,
                "division": _safe(lambda: t.division, "") or "",
                "conf": _safe(lambda: t.conference, "") or "",
                "gp": gp, "w": w, "l": l, "otl": otl, "pts": pts,
                "gf": gf, "ga": ga, "diff": gf - ga,
                "pt_pct": round(pts / (2 * gp), 3) if gp else 0.0,
                "streak": _safe(lambda: getattr(t, "streak", "") or "", ""),
                "is_user": (_safe(lambda: bool(t.is_user_team), False)
                            or name == user_team_name),
            })
        except Exception:
            continue
    return rows, user_team_name


_STANDINGS_VIEWS = [
    "League Overview", "Eastern Conference", "Western Conference",
    "Wild Card Race", "Division Leaders", "Playoff Picture",
]


def _standings_view_teams(rows, view):
    by_points = sorted(rows, key=lambda r: (-r["pts"], -r["w"], r["name"]))
    if view == "Eastern Conference":
        return [r for r in by_points if r["conf"] == "Eastern"]
    if view == "Western Conference":
        return [r for r in by_points if r["conf"] == "Western"]
    if view == "Wild Card Race":
        out = []
        for conf in ("Eastern", "Western"):
            conf_teams = [r for r in by_points if r["conf"] == conf]
            out.extend(conf_teams[3:8])  # wild-card bubble: 4th-8th
        return out
    if view == "Division Leaders":
        seen = {}
        for r in by_points:
            div = r["division"] or "Unknown"
            if div not in seen:
                seen[div] = r
        return [seen[d] for d in sorted(seen)]
    if view == "Playoff Picture":
        out = []
        for conf in ("Eastern", "Western"):
            conf_teams = [r for r in by_points if r["conf"] == conf]
            out.extend(conf_teams[:8])
        return out
    return by_points  # League Overview


def _apply_standings_sort(rows, sort):
    if sort == "Wins":
        return sorted(rows, key=lambda r: (-r["w"], -r["pts"], r["name"]))
    if sort == "Goal Differential":
        return sorted(rows, key=lambda r: (-r["diff"], -r["pts"], r["name"]))
    return sorted(rows, key=lambda r: (-r["pts"], -r["w"], r["name"]))


def _team_analytics_rows(game, category):
    """Category table for the Team Analytics tab."""
    rows, user_team = _rich_team_rows(game)
    league = _league(game)
    teams_by_name = {}
    if league is not None:
        for t in (_safe(lambda: list(league.teams), []) or []):
            n = _safe(lambda: t.team_name, "")
            if n:
                teams_by_name[n] = t

    out = []
    for r in rows:
        t = teams_by_name.get(r["name"])
        gp = max(1, r["gp"])
        pp = _safe(lambda: float(getattr(t, "power_play_pct", 0) or 0), 0)
        pk = _safe(lambda: float(getattr(t, "penalty_kill_pct", 0) or 0), 0)
        gaa_team = _safe(lambda: float(getattr(t, "team_gaa", 0) or 0), 0)
        svp_team = _safe(lambda: float(getattr(t, "team_save_pct", 0) or 0), 0)
        gf, ga = r["gf"], r["ga"]
        out.append({
            "name": r["name"], "division": r["division"], "conf": r["conf"],
            "gp": r["gp"], "w": r["w"], "l": r["l"], "otl": r["otl"],
            "pts": r["pts"], "is_user": r["is_user"],
            "gf": gf, "ga": ga, "diff": r["diff"],
            "gf_gp": round(gf / gp, 2),
            "ga_gp": round(ga / gp, 2),
            "pp_pct": round(pp, 1), "pk_pct": round(pk, 1),
            "team_gaa": round(gaa_team, 2),
            "team_sv_pct": round(svp_team, 3),
            "goal_share": round(gf / (gf + ga) * 100, 1) if (gf + ga) else 0.0,
            "pythag_pts": round(
                ((gf ** 2) / ((gf ** 2) + (ga ** 2)) if (gf or ga) else 0.5)
                * 2 * r["gp"], 1),
        })

    avgs = {}
    if out:
        for k in ("gf_gp", "ga_gp", "pp_pct", "pk_pct", "goal_share"):
            avgs[k] = round(sum(r[k] for r in out) / len(out), 2)

    if category == "Offensive Stats":
        out.sort(key=lambda r: (-r["gf_gp"], -r["gf"]))
    elif category == "Defensive Stats":
        out.sort(key=lambda r: (r["ga_gp"], r["ga"]))
    elif category == "Goaltending":
        out.sort(key=lambda r: (-r["team_sv_pct"], r["team_gaa"]))
    elif category == "Advanced Analytics":
        out.sort(key=lambda r: (-r["goal_share"], -r["diff"]))
    else:
        out.sort(key=lambda r: (-r["pts"], -r["w"]))
    return out, avgs, user_team


_TA_CATS = ["Overall Performance", "Offensive Stats", "Defensive Stats",
            "Goaltending", "Advanced Analytics"]
_TA_FILTERS = ["All Teams", "Eastern Conference", "Western Conference",
               "Division Rivals", "Playoff Teams"]
_TA_MODES = ["League Rankings", "vs League Average"]
_TA_COLS = {
    "Overall Performance": [("pts", "PTS"), ("w", "W"), ("diff", "+/-"),
                            ("goal_share", "Goal Share%")],
    "Offensive Stats": [("gf_gp", "GF/GP"), ("gf", "GF"), ("pp_pct", "PP%"),
                        ("goal_share", "Goal Share%")],
    "Defensive Stats": [("ga_gp", "GA/GP"), ("ga", "GA"), ("pk_pct", "PK%"),
                        ("diff", "+/-")],
    "Goaltending": [("team_sv_pct", "SV%"), ("team_gaa", "Team GAA"),
                    ("ga", "GA"), ("pk_pct", "PK%")],
    "Advanced Analytics": [("goal_share", "Goal Share%"), ("pythag_pts", "xPts"),
                           ("diff", "+/-"), ("pt_pct", "PT%")],
}
_DIV_TYPES = ["Standings", "Head-to-Head", "Strength of Schedule",
              "Division vs League"]


def _fmt_num(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.2f}"
    return str(v)


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class StandingsScreen(BaseScreen):
    title = "Standings"

    def __init__(self, game, main_window, parent=None):
        # state (mirrors standings.js standState)
        self.view = "League Overview"
        self.sort = "Points"
        self.advanced = True
        self.ta_cat = "Overall Performance"
        self.ta_mode = "League Rankings"
        self.ta_filter = "All Teams"
        self.div = "All Divisions"
        self.div_type = "Standings"
        super().__init__(game, main_window, parent)

    def _build_body(self):
        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs)

        # --- tab 0: overview ---
        self._overview = QWidget()
        self.tabs.addTab(self._overview, "Standings")
        self._build_overview(self._overview)

        # --- tab 1: team analytics ---
        self._analytics = QWidget()
        self.tabs.addTab(self._analytics, "Team Analytics")
        self._build_analytics(self._analytics)

        # --- tab 2: division analysis ---
        self._division = QWidget()
        self.tabs.addTab(self._division, "Division Analysis")
        self._build_division(self._division)

        # --- tab 3: divisions grid ---
        self._grid = QWidget()
        self.tabs.addTab(self._grid, "Divisions")
        self._build_grid(self._grid)

        self.tabs.currentChanged.connect(lambda _: self.refresh())

    # -- shared pill row -----------------------------------------------------

    def _pill_row(self, values, current, on_change):
        """Horizontal row of checkable pill buttons."""
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

    def _make_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def _open_team(self, name):
        try:
            self.main_window.open_team(name)
        except Exception:
            try:
                self.navigate_to("team")
            except Exception:
                QMessageBox.information(
                    self, "Team",
                    "The team screen is not available in this build yet.")

    # -- overview tab --------------------------------------------------------

    def _build_overview(self, page):
        layout = QVBoxLayout(page)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("View"))
        self._view_pills = QWidget()
        self._view_pills.setLayout(QHBoxLayout())
        self._view_pills.layout().setContentsMargins(0, 0, 0, 0)
        ctl.addWidget(self._view_pills)
        ctl.addWidget(QLabel("Sort"))
        ctl.addWidget(self._pill_row(["Points", "Wins", "Goal Differential"],
                                     self.sort, self._on_sort))
        self._adv_check = QCheckBox("Advanced metrics")
        self._adv_check.setChecked(self.advanced)
        self._adv_check.toggled.connect(self._on_advanced)
        ctl.addWidget(self._adv_check)
        ctl.addStretch()
        layout.addLayout(ctl)

        self._overview_table = self._make_table([])
        self._overview_table.cellClicked.connect(
            lambda r, _c: self._on_table_team_click(self._overview_table, r))
        layout.addWidget(self._overview_table)

    def _rebuild_view_pills(self):
        lay = self._view_pills.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        pillbox = self._pill_row(_STANDINGS_VIEWS, self.view, self._on_view)
        inner = pillbox.layout()
        while inner.count():
            lay.addWidget(inner.takeAt(0).widget())
        pillbox.deleteLater()

    def _on_view(self, v):
        self.view = v
        self._render_overview()

    def _on_sort(self, v):
        self.sort = v
        self._render_overview()

    def _on_advanced(self, on):
        self.advanced = bool(on)
        self._render_overview()

    def _render_overview(self):
        self._rebuild_view_pills()
        try:
            rows, user_team = _rich_team_rows(self.game)
            rows = _standings_view_teams(rows, self.view)
            rows = _apply_standings_sort(rows, self.sort)
        except Exception:
            rows = []
        cutoff = None
        if self.view == "Wild Card Race":
            cutoff = 2
        elif self.view == "Playoff Picture":
            cutoff = 8

        headers = ["#", "Team", "GP", "W", "L", "OTL"]
        if self.advanced:
            headers += ["GF", "GA", "DIFF", "PT%"]
        headers += ["PTS"]
        t = self._overview_table
        t.clear()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setRowCount(len(rows) + (1 if cutoff is not None else 0))

        ridx = 0
        for i, r in enumerate(rows):
            if cutoff is not None and i == cutoff:
                item = QTableWidgetItem("— playoff cut line —")
                item.setTextAlignment(Qt.AlignCenter)
                t.setItem(ridx, 0, item)
                t.setSpan(ridx, 0, 1, len(headers))
                ridx += 1
            cells = [str(i + 1), r["name"], str(r["gp"]), str(r["w"]),
                     str(r["l"]), str(r["otl"])]
            if self.advanced:
                diff = r["diff"]
                cells += [str(r["gf"]), str(r["ga"]),
                          ("+" if diff >= 0 else "") + str(diff),
                          f"{r['pt_pct'] * 100:.1f}"]
            cells.append(str(r["pts"]))
            for c, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, r["name"])
                if r.get("is_user"):
                    item.setForeground(Qt.cyan)
                t.setItem(ridx, c, item)
            ridx += 1
        t.setRowCount(ridx)
        t.resizeColumnsToContents()

    def _on_table_team_click(self, table, row):
        item = table.item(row, 1)
        if item is None:
            item = table.item(row, 0)
        if item is None:
            return
        name = item.data(Qt.UserRole)
        if name:
            self._open_team(name)

    # -- analytics tab -------------------------------------------------------

    def _build_analytics(self, page):
        layout = QVBoxLayout(page)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Category"))
        row1.addWidget(self._pill_row(_TA_CATS, self.ta_cat, self._on_ta_cat))
        row1.addWidget(QLabel("Mode"))
        row1.addWidget(self._pill_row(_TA_MODES, self.ta_mode, self._on_ta_mode))
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Teams"))
        row2.addWidget(self._pill_row(_TA_FILTERS, self.ta_filter,
                                      self._on_ta_filter))
        row2.addStretch()
        layout.addLayout(row2)

        self._ta_table = self._make_table([])
        self._ta_table.cellClicked.connect(
            lambda r, _c: self._on_table_team_click(self._ta_table, r))
        layout.addWidget(self._ta_table)

    def _on_ta_cat(self, v):
        self.ta_cat = v
        self._render_analytics()

    def _on_ta_mode(self, v):
        self.ta_mode = v
        self._render_analytics()

    def _on_ta_filter(self, v):
        self.ta_filter = v
        self._render_analytics()

    def _render_analytics(self):
        try:
            rows, avgs, user_team = _team_analytics_rows(self.game, self.ta_cat)
        except Exception:
            rows, avgs, user_team = [], {}, None
        if self.ta_filter in ("Eastern Conference", "Western Conference"):
            rows = [r for r in rows if r["conf"] == self.ta_filter]
        elif self.ta_filter == "Division Rivals" and user_team:
            udiv = next((r["division"] for r in rows
                         if r["name"] == user_team), "")
            rows = [r for r in rows if r["division"] == udiv]
        elif self.ta_filter == "Playoff Teams":
            keep = set()
            for conf in ("Eastern", "Western"):
                cr = sorted([r for r in rows if r["conf"] == conf],
                            key=lambda r: (-r["pts"], -r["w"]))[:8]
                keep.update(r["name"] for r in cr)
            rows = [r for r in rows if r["name"] in keep]

        cols = _TA_COLS.get(self.ta_cat, _TA_COLS["Overall Performance"])
        vs_avg = self.ta_mode == "vs League Average"
        headers = ["#", "Team"] + [label for _, label in cols]
        t = self._ta_table
        t.clear()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            head = [QTableWidgetItem(str(i + 1))]
            name_item = QTableWidgetItem(r["name"])
            name_item.setData(Qt.UserRole, r["name"])
            head.append(name_item)
            for c, item in enumerate(head):
                if r.get("is_user"):
                    item.setForeground(Qt.cyan)
                t.setItem(i, c, item)
            for j, (key, _label) in enumerate(cols):
                v = r.get(key)
                if vs_avg and avgs.get(key) is not None and isinstance(v, (int, float)):
                    delta = v - avgs[key]
                    txt = ("+" if delta >= 0 else "") + \
                        f"{delta:.{0 if key == 'diff' else 2}f}"
                elif key == "diff" and isinstance(v, (int, float)):
                    txt = ("+" if v >= 0 else "") + str(int(v))
                elif key == "team_sv_pct" and isinstance(v, (int, float)):
                    txt = f"{v:.3f}"
                else:
                    txt = _fmt_num(v)
                item = QTableWidgetItem(txt)
                item.setData(Qt.UserRole, r["name"])
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(i, 2 + j, item)
        t.resizeColumnsToContents()

    # -- division analysis tab -------------------------------------------------

    def _build_division(self, page):
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        row.addWidget(QLabel("Division"))
        self._div_pill_host = QWidget()
        self._div_pill_host.setLayout(QHBoxLayout())
        self._div_pill_host.layout().setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._div_pill_host)
        row.addWidget(QLabel("Analysis"))
        row.addWidget(self._pill_row(_DIV_TYPES, self.div_type,
                                     self._on_div_type))
        row.addStretch()
        layout.addLayout(row)

        self._div_note = QLabel("")
        self._div_note.setWordWrap(True)
        layout.addWidget(self._div_note)

        self._div_extra = QTableWidget()
        self._div_extra.setVisible(False)
        layout.addWidget(self._div_extra)

        self._div_table = self._make_table([])
        self._div_table.cellClicked.connect(
            lambda r, _c: self._on_table_team_click(self._div_table, r))
        layout.addWidget(self._div_table)

    def _on_div_type(self, v):
        self.div_type = v
        self._render_division()

    def _rebuild_div_pills(self, divisions):
        lay = self._div_pill_host.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        if self.div not in ["All Divisions"] + divisions:
            self.div = "All Divisions"
        pillbox = self._pill_row(["All Divisions"] + divisions, self.div,
                                 lambda v: (setattr(self, "div", v),
                                            self._render_division()))
        inner = pillbox.layout()
        while inner.count():
            lay.addWidget(inner.takeAt(0).widget())
        pillbox.deleteLater()

    def _render_division(self):
        try:
            rows, user_team = _rich_team_rows(self.game)
        except Exception:
            rows, user_team = [], None
        divisions = sorted({r["division"] for r in rows if r["division"]})
        self._rebuild_div_pills(divisions)
        div_rows = [r for r in rows
                    if self.div == "All Divisions" or r["division"] == self.div]
        div_rows.sort(key=lambda r: (-r["pts"], -r["w"], r["name"]))

        # extra panels for the special analysis types
        self._div_extra.setVisible(False)
        note = ""
        if self.div_type == "Division vs League":
            divs = {}
            for r in rows:
                d = divs.setdefault(r["division"] or "Unknown",
                                    {"teams": 0, "pts": 0, "gf": 0, "ga": 0})
                d["teams"] += 1
                d["pts"] += r["pts"]; d["gf"] += r["gf"]; d["ga"] += r["ga"]
            t = self._div_extra
            t.clear()
            t.setColumnCount(6)
            t.setHorizontalHeaderLabels(
                ["Division", "Teams", "Avg Pts", "Avg GF", "Avg GA",
                 "Goal Share%"])
            comp = sorted(divs.items())
            t.setRowCount(len(comp))
            for i, (dname, v) in enumerate(comp):
                gs = (round(v["gf"] / (v["gf"] + v["ga"]) * 100, 1)
                      if (v["gf"] + v["ga"]) else 0.0)
                vals = [dname, str(v["teams"]),
                        f"{v['pts'] / v['teams']:.1f}",
                        f"{v['gf'] / v['teams']:.1f}",
                        f"{v['ga'] / v['teams']:.1f}", f"{gs:.1f}"]
                for c, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    t.setItem(i, c, item)
            t.resizeColumnsToContents()
            t.setVisible(True)
        elif self.div_type == "Strength of Schedule":
            sos = self._strength_of_schedule(rows, user_team)
            t = self._div_extra
            t.clear()
            t.setColumnCount(3)
            t.setHorizontalHeaderLabels(["Team", "Games Left", "Opp PT%"])
            t.setRowCount(len(sos))
            for i, s in enumerate(sos):
                name_item = QTableWidgetItem(s["name"])
                name_item.setData(Qt.UserRole, s["name"])
                gl_item = QTableWidgetItem(str(s["games_left"]))
                pct_item = QTableWidgetItem(f"{s['opp_pt_pct'] * 100:.1f}")
                pct_item.setData(Qt.UserRole, s["name"])
                if s["name"] == user_team:
                    name_item.setForeground(Qt.cyan)
                t.setItem(i, 0, name_item)
                t.setItem(i, 1, gl_item)
                t.setItem(i, 2, pct_item)
            t.cellClicked.connect(
                lambda r, _c: self._on_table_team_click(self._div_extra, r))
            t.resizeColumnsToContents()
            t.setVisible(True)
        elif self.div_type == "Head-to-Head":
            note = ("Head-to-head records are not tracked by the sim engine; "
                    "showing intra-division goal differential instead.")
        self._div_note.setText(note)

        headers = ["#", "Team", "GP", "W", "L", "OTL", "DIFF", "PTS"]
        t = self._div_table
        t.clear()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setRowCount(len(div_rows))
        for i, r in enumerate(div_rows):
            diff = r["diff"]
            vals = [str(i + 1), r["name"], str(r["gp"]), str(r["w"]),
                    str(r["l"]), str(r["otl"]),
                    ("+" if diff >= 0 else "") + str(diff), str(r["pts"])]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, r["name"])
                if r.get("is_user"):
                    item.setForeground(Qt.cyan)
                t.setItem(i, c, item)
        t.resizeColumnsToContents()

    def _strength_of_schedule(self, rows, user_team):
        league = _league(self.game)
        sched = _safe(lambda: list(getattr(league, "schedule", None) or []),
                      []) or []
        pct = {r["name"]: r["pt_pct"] for r in rows}
        rem = {}
        for g in sched:
            try:
                if not isinstance(g, dict):
                    continue
                if g.get("played"):
                    continue
                home = str(g.get("home_team", "") or "")
                away = str(g.get("away_team", "") or "")
                for me, opp in ((home, away), (away, home)):
                    if me:
                        rem.setdefault(me, []).append(pct.get(opp, 0.5))
            except Exception:
                continue
        return [{"name": r["name"], "division": r["division"],
                 "games_left": len(rem.get(r["name"], [])),
                 "opp_pt_pct": round(
                     sum(rem.get(r["name"], [])) /
                     max(1, len(rem.get(r["name"], []))), 3)}
                for r in rows
                if self.div == "All Divisions"
                or r["division"] == self.div]

    # -- divisions grid tab ----------------------------------------------------

    def _build_grid(self, page):
        layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._grid_host = QWidget()
        self._grid_layout = QGridLayout(self._grid_host)
        scroll.setWidget(self._grid_host)
        layout.addWidget(scroll)

    def _render_grid(self):
        while self._grid_layout.count():
            w = self._grid_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        try:
            rows, _user = _rich_team_rows(self.game)
        except Exception:
            rows = []
        grid = {}
        for r in sorted(rows, key=lambda r: (-r["pts"], -r["w"], r["name"])):
            grid.setdefault(r["division"] or "Unknown", []).append(r)
        if not grid:
            self._grid_layout.addWidget(QLabel("No divisions yet."), 0, 0)
            return
        for col, dname in enumerate(sorted(grid)):
            box = QGroupBox(dname)
            v = QVBoxLayout(box)
            t = self._make_table(["#", "Team", "W-L-OTL", "PTS"])
            t.setColumnCount(4)
            t.setHorizontalHeaderLabels(["#", "Team", "W-L-OTL", "PTS"])
            div_rows = grid[dname]
            t.setRowCount(len(div_rows))
            for i, r in enumerate(div_rows):
                vals = [str(i + 1), r["name"],
                        f"{r['w']}-{r['l']}-{r['otl']}", str(r["pts"])]
                for c, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setData(Qt.UserRole, r["name"])
                    if r.get("is_user"):
                        item.setForeground(Qt.cyan)
                    t.setItem(i, c, item)
            t.cellClicked.connect(
                lambda r, _c, _t=t: self._on_table_team_click(_t, r))
            t.resizeColumnsToContents()
            v.addWidget(t)
            self._grid_layout.addWidget(box, 0, col)

    # -- refresh ----------------------------------------------------------------

    def refresh(self):
        self._render_overview()
        self._render_analytics()
        self._render_division()
        self._render_grid()
