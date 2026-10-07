"""GM Relationships dashboard: stature, respect, heat, trend.

Port of main.open_gm_relationships_window / gm_relationships_window.py
(GMRelationshipsView). Read-only: all data comes from reputation_system,
nothing is reimplemented here.

Table: Team | GM | Stature | Respect | Tier | Heat | Trend.
Click a row to open the per-GM detail panel. Color-coded: green = high
respect, red = high heat.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QFrame, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen

try:
    import reputation_system as _rs
except Exception:
    _rs = None


_TREND_ARROW = {"warming": "\u2191", "cooling": "\u2193", "steady": "\u2192"}

_TIER_COLORS = {
    "warm": "#4CAF50",      # green
    "cordial": "#8BC34A",   # light green
    "wary": "#FF9800",      # orange
    "cold": "#F44336",      # red
}

_TIER_BLURBS = {
    "warm": "Deals flow easily here -- this GM gives your proposals the "
            "benefit of the doubt.",
    "cordial": "A generally positive working relationship. Standard "
               "negotiations apply.",
    "wary": "Tread carefully -- your offers get extra scrutiny and "
            "counteroffers run harder.",
    "cold": "Hostile. Expect rejections, hard counters, and cold "
            "shoulders on the trade call.",
}

_TREND_BLURBS = {
    "warming": "Respect has been warming over the last 90 days of dealings.",
    "cooling": "Respect has been cooling over the last 90 days of dealings.",
    "steady": "Respect is holding steady -- no recent drift.",
}


class _NumericItem(QTableWidgetItem):
    """Table item that sorts numerically on its stored value."""

    def __init__(self, text, value):
        super().__init__(text)
        try:
            self.setData(Qt.UserRole, float(value))
        except Exception:
            self.setData(Qt.UserRole, 0.0)

    def __lt__(self, other):
        try:
            return self.data(Qt.UserRole) < other.data(Qt.UserRole)
        except Exception:
            return super().__lt__(other)


class GmRelationshipsScreen(BaseScreen):
    """Dashboard of all 31 rival GMs: stature, respect, heat, trend."""

    title = "GM Relationships"

    def _build_body(self):
        top = QHBoxLayout()
        explainer = QLabel(
            "Stature: your league-wide reputation (0-100).  "
            "Respect: how this GM views you (-100 to 100).  "
            "Heat: personal friction (0-100).  "
            "Trend: which way respect is moving (\u2191 warming, "
            "\u2193 cooling, \u2192 steady).\n"
            "Respect decays toward your stature baseline over time.")
        explainer.setWordWrap(True)
        explainer.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        top.addWidget(explainer, 1)
        self._own_stature_lbl = QLabel("")
        self._own_stature_lbl.setStyleSheet(
            "color: #e8b34b; font-size: 13px; font-weight: 700;")
        top.addWidget(self._own_stature_lbl)
        self._layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Team", "GM", "Stature", "Respect", "Tier", "Heat", "Trend"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col, width in ((2, 70), (3, 75), (4, 85), (5, 65), (6, 65)):
            self._table.setColumnWidth(col, width)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        self._detail = QFrame()
        self._detail.setObjectName("tile")
        self._detail.setMinimumWidth(260)
        detail_layout = QVBoxLayout(self._detail)
        self._detail_title = QLabel("Select a GM")
        self._detail_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;")
        self._detail_title.setWordWrap(True)
        detail_layout.addWidget(self._detail_title)
        self._detail_body = QLabel("")
        self._detail_body.setWordWrap(True)
        self._detail_body.setAlignment(Qt.AlignTop)
        self._detail_body.setStyleSheet("font-size: 12px;")
        detail_layout.addWidget(self._detail_body, 1)
        splitter.addWidget(self._detail)
        splitter.setSizes([700, 300])

        self._layout.addWidget(splitter, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        self._layout.addLayout(btn_row)

        self._rows = []
        self.refresh()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_int(fn, *args, default=0):
        try:
            return int(fn(*args))
        except Exception:
            return default

    @staticmethod
    def _safe_str(fn, *args, default=""):
        try:
            v = fn(*args)
            return str(v) if v is not None else default
        except Exception:
            return default

    @staticmethod
    def _gm_name(team):
        try:
            gm = _rs._team_gm_staff(team)
            if gm is not None:
                name = (getattr(gm, "full_name", None)
                        or getattr(gm, "name", None))
                if name:
                    return str(name)
        except Exception:
            pass
        try:
            return f"{getattr(team, 'team_name', '')} GM"
        except Exception:
            return "Unknown GM"

    @staticmethod
    def _team_name(team):
        try:
            return str(getattr(team, "team_name", "Unknown") or "Unknown")
        except Exception:
            return "Unknown"

    def _collect_rows(self):
        rows = []
        if _rs is None or self.game is None:
            return rows
        try:
            league = getattr(self.game, "league", None)
            user_team = getattr(self.game, "user_team", None)
            teams = list(getattr(league, "teams", []) or [])
        except Exception:
            return rows
        user_id = getattr(user_team, "id", None)
        for team in teams:
            try:
                if team is user_team:
                    continue
                if user_id is not None and getattr(team, "id", None) == user_id:
                    continue
                stature = self._safe_int(_rs.gm_stature, team, default=50)
                respect = self._safe_int(
                    _rs.gm_gm_respect, league, user_team, team, default=0)
                heat = self._safe_int(
                    _rs.gm_gm_heat, league, user_team, team, default=0)
                tier = self._safe_str(
                    _rs.respect_tier_label, respect, default="wary")
                trend = self._safe_str(
                    _rs.respect_trend, league, user_team, team,
                    default="steady")
                rows.append({
                    "team": self._team_name(team),
                    "gm": self._gm_name(team),
                    "stature": stature,
                    "respect": respect,
                    "tier": tier,
                    "heat": heat,
                    "trend": trend,
                    "arrow": _TREND_ARROW.get(trend, "\u2192"),
                })
            except Exception:
                continue
        return rows

    def refresh(self):
        if _rs is not None and self.game is not None:
            try:
                user_team = getattr(self.game, "user_team", None)
                own = self._safe_int(_rs.gm_stature, user_team, default=50)
                self._own_stature_lbl.setText(f"Your stature: {own}/100")
            except Exception:
                self._own_stature_lbl.setText("")
        self._rows = self._collect_rows()
        # Default sort: highest respect first (matches the Tkinter view).
        self._rows.sort(key=lambda r: r["respect"], reverse=True)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._rows))
        for row, r in enumerate(self._rows):
            tier_color = _TIER_COLORS.get(r["tier"], "#9aa4b8")
            respect_color = ("#4CAF50" if r["respect"] >= 50
                             else "#F44336" if r["respect"] <= -25
                             else None)
            heat_color = ("#F44336" if r["heat"] >= 60
                          else "#4CAF50" if r["heat"] <= 20
                          else None)
            items = [
                QTableWidgetItem(r["team"]),
                QTableWidgetItem(r["gm"]),
                _NumericItem(str(r["stature"]), r["stature"]),
                _NumericItem(f"{r['respect']:+d}", r["respect"]),
                QTableWidgetItem(r["tier"].capitalize()),
                _NumericItem(str(r["heat"]), r["heat"]),
                QTableWidgetItem(r["arrow"]),
            ]
            if respect_color:
                items[3].setForeground(QColor(respect_color))
            if heat_color:
                items[5].setForeground(QColor(heat_color))
            items[4].setForeground(QColor(tier_color))
            for col, item in enumerate(items):
                self._table.setItem(row, col, item)
        self._table.setSortingEnabled(True)
        self._detail_title.setText("Select a GM")
        self._detail_body.setText("")

    # ------------------------------------------------------------------
    # Detail panel
    # ------------------------------------------------------------------
    def _on_row_selected(self):
        row = self._table.currentRow()
        if not (0 <= row < len(self._rows)):
            return
        r = self._rows[row]
        tier = r["tier"]
        self._detail_title.setText(f"{r['gm']}\n{r['team']}")
        own = ""
        if _rs is not None and self.game is not None:
            try:
                own_val = self._safe_int(
                    _rs.gm_stature,
                    getattr(self.game, "user_team", None), default=50)
                own = f"Your stature: {own_val}/100\n"
            except Exception:
                pass
        lines = [
            own + f"Their stature: {r['stature']}/100",
            f"Respect: {r['respect']:+d}  ({r['trend']})",
            f"Heat: {r['heat']}/100",
            "",
            _TIER_BLURBS.get(tier, ""),
            "",
            _TREND_BLURBS.get(r["trend"], ""),
            "",
            "Respect decays toward your stature baseline over time.",
        ]
        self._detail_body.setText("\n".join(lines))
        self._detail_body.setStyleSheet(
            f"font-size: 12px; color: #d5dbe7;")
