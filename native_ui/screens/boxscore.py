"""Box Score screen: completed-game drill-down.

Native Qt port of web_ui/templates/boxscore.html (+ boxscore.css/js).
Broadcast style: deep blue accent (#3B82F6), dark panels, no white-on-white.

Shows: header (teams/scores/date/stars), pill tabs for
Scoring / Player Stats / Lines / Team Stats.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..dialogs.boxscore import (
    _find_game_result,
    _scoring_summary,
    _box_player_stats,
    _box_team_stats,
    _box_three_stars,
    _box_lines,
    _roster_lookup,
    _team_name,
    _abbr,
    _iso,
    _date_key,
    _safe,
)

# ---------------------------------------------------------------------------
# Style constants (mirror boxscore.css)
# ---------------------------------------------------------------------------
_PANEL = (
    "background: rgba(13, 20, 34, 0.92);"
    "border: 1px solid rgba(59, 130, 246, 0.18);"
    "border-radius: 14px;"
)
_BLUE = "#3B82F6"
_MUTED = "#9aa7bd"
_DIM = "#6b7a94"
_TEXT = "#eef3fb"
_CELL = "#dbe4f2"


class BoxscoreScreen(BaseScreen):
    """Completed-game box score (full screen, not a dialog)."""

    title = "Box Score"

    def __init__(self, game, main_window, parent=None):
        self._date_iso = None
        self._home_name = None
        self._away_name = None
        self._data = None
        self._players_team = None
        self._lines_team = None
        super().__init__(game, main_window, parent)

    # -- body ------------------------------------------------------------

    def _build_body(self):
        # Back link
        back = QPushButton("← Schedule")
        back.setCursor(Qt.PointingHandCursor)
        back.setStyleSheet(
            "background: transparent; border: none; color: %s;"
            "font-size: 13px; font-weight: 700; text-align: left;"
            % _MUTED
        )
        back.clicked.connect(lambda: self.navigate_to("schedule"))
        self._layout.addWidget(back, alignment=Qt.AlignLeft)

        # Loading / error labels
        self._loading = QLabel("Loading box score…")
        self._loading.setAlignment(Qt.AlignCenter)
        self._loading.setStyleSheet(
            "color: %s; font-size: 14px; padding: 40px;" % _MUTED)
        self._layout.addWidget(self._loading)

        self._error = QLabel("")
        self._error.setAlignment(Qt.AlignCenter)
        self._error.setStyleSheet(
            "color: #ff8a8a; font-size: 14px; padding: 40px;")
        self._error.hide()
        self._layout.addWidget(self._error)

        # Content container (hidden until data loads)
        self._content = QWidget()
        self._content.hide()
        self._layout.addWidget(self._content, 1)
        cl = QVBoxLayout(self._content)
        cl.setSpacing(12)
        cl.setContentsMargins(0, 0, 0, 0)

        # Header panel
        self._header_panel = QFrame()
        self._header_panel.setStyleSheet(_PANEL)
        hl = QVBoxLayout(self._header_panel)
        hl.setContentsMargins(22, 22, 22, 16)
        hl.setSpacing(8)

        teams_row = QHBoxLayout()
        teams_row.setSpacing(22)
        teams_row.setAlignment(Qt.AlignCenter)
        self._away_abbr = self._mk_abbr_badge()
        self._away_name_l = self._mk_team_name()
        self._away_score_l = self._mk_score()
        teams_row.addWidget(self._away_abbr)
        teams_row.addWidget(self._away_name_l)
        teams_row.addWidget(self._away_score_l)
        at = QLabel("@")
        at.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: %s;" % _DIM)
        teams_row.addWidget(at)
        self._home_score_l = self._mk_score()
        self._home_name_l = self._mk_team_name()
        self._home_abbr = self._mk_abbr_badge()
        teams_row.addWidget(self._home_score_l)
        teams_row.addWidget(self._home_name_l)
        teams_row.addWidget(self._home_abbr)
        hl.addLayout(teams_row)

        self._meta = QLabel("")
        self._meta.setAlignment(Qt.AlignCenter)
        self._meta.setStyleSheet(
            "color: %s; font-size: 13px;" % _MUTED)
        hl.addWidget(self._meta)

        self._stars = QLabel("")
        self._stars.setAlignment(Qt.AlignCenter)
        self._stars.setWordWrap(True)
        self._stars.setStyleSheet("font-size: 13px; color: %s;" % _MUTED)
        hl.addWidget(self._stars)
        cl.addWidget(self._header_panel)

        # Pill tabs
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(8)
        tabs_row.setAlignment(Qt.AlignLeft)
        self._tab_btns = {}
        self._panes = {}
        for key, label in (("scoring", "Scoring"),
                           ("players", "Player Stats"),
                           ("lines", "Lines"),
                           ("teams", "Team Stats")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, k=key: self._select_tab(k))
            tabs_row.addWidget(btn)
            self._tab_btns[key] = btn
        tabs_row.addStretch()
        cl.addLayout(tabs_row)

        # Panes (stacked, one visible)
        for key in ("scoring", "players", "lines", "teams"):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setStyleSheet("background: transparent;")
            inner = QWidget()
            il = QVBoxLayout(inner)
            il.setSpacing(8)
            il.setAlignment(Qt.AlignTop)
            il.setContentsMargins(2, 2, 2, 2)
            scroll.setWidget(inner)
            scroll._inner = inner
            scroll._layout = il
            scroll.hide()
            cl.addWidget(scroll, 1)
            self._panes[key] = scroll

        self._select_tab("scoring")
        self._layout.addStretch()

    # -- widget factories --------------------------------------------------

    def _mk_abbr_badge(self):
        l = QLabel("")
        l.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #0b1220;"
            "background: %s; border-radius: 6px; padding: 4px 8px;" % _BLUE)
        return l

    def _mk_team_name(self):
        l = QLabel("")
        l.setStyleSheet(
            "font-size: 19px; font-weight: 800; color: %s;" % _TEXT)
        return l

    def _mk_score(self):
        l = QLabel("")
        l.setStyleSheet(
            "font-size: 34px; font-weight: 800; color: %s;"
            "min-width: 52px;" % _BLUE)
        l.setAlignment(Qt.AlignCenter)
        return l

    def _style_tab(self, btn, active):
        if active:
            btn.setChecked(True)
            btn.setStyleSheet(
                "background: %s; border: 1px solid %s; color: #fff;"
                "border-radius: 10px; padding: 9px 18px;"
                "font-size: 13px; font-weight: 700;" % (_BLUE, _BLUE))
        else:
            btn.setChecked(False)
            btn.setStyleSheet(
                "background: rgba(13, 20, 34, 0.86); color: %s;"
                "border: 1px solid rgba(59, 130, 246, 0.18);"
                "border-radius: 10px; padding: 9px 18px;"
                "font-size: 13px; font-weight: 700;" % _MUTED)

    def _select_tab(self, key):
        for k, btn in self._tab_btns.items():
            self._style_tab(btn, k == key)
        for k, pane in self._panes.items():
            pane.setVisible(k == key)
        if key == "players":
            self._render_players()
        elif key == "lines":
            self._render_lines()
        elif key == "teams":
            self._render_teams()

    # -- public API --------------------------------------------------------

    def set_game(self, date_iso, home_team, away_team=None):
        """Load a box score for (date, home, away)."""
        self._date_iso = date_iso
        self._home_name = _team_name(home_team)
        self._away_name = _team_name(away_team) if away_team else None
        self._data = None
        self._players_team = None
        self._lines_team = None
        self.refresh()

    def refresh(self):
        if not self._date_iso or not self._home_name:
            return
        self._loading.show()
        self._error.hide()
        self._content.hide()
        try:
            results = _safe(
                lambda: list(getattr(self.game, "game_results", []) or []),
                [])
            r = _find_game_result(
                self.game, self._date_iso, self._home_name,
                self._away_name)
            if r is None:
                raise ValueError("no recorded result for that game")
            by_id = _roster_lookup(r)
            home_name = _team_name(r.get("home_team"))
            away_name = _team_name(r.get("away_team"))
            d = r.get("date")
            dk = _date_key(d)
            date_label = dk.strftime("%a %b %d, %Y") if dk else str(d or "")
            note = ""
            if r.get("shootout"):
                note = "Shootout"
            elif r.get("overtime"):
                note = "Overtime"
            self._data = {
                "date_label": date_label,
                "note": note,
                "home": {"name": home_name,
                         "abbr": _abbr(home_name),
                         "score": int(r.get("home_score", 0) or 0)},
                "away": {"name": away_name,
                         "abbr": _abbr(away_name),
                         "score": int(r.get("away_score", 0) or 0)},
                "scoring": _scoring_summary(r, by_id, home_name, away_name),
                "players": _box_player_stats(r, by_id, home_name, away_name),
                "team_stats": _box_team_stats(r, by_id, home_name, away_name),
                "three_stars": _box_three_stars(r, by_id),
                "lines": {home_name: _box_lines(r, by_id, home_name),
                          away_name: _box_lines(r, by_id, away_name)},
            }
            self._render_all()
            self._loading.hide()
            self._content.show()
        except Exception as e:
            self._loading.hide()
            self._error.setText(f"Could not load the box score: {e}")
            self._error.show()

    # -- rendering ---------------------------------------------------------

    def _render_all(self):
        d = self._data
        h, a = d["home"], d["away"]
        self._away_abbr.setText(a["abbr"])
        self._away_name_l.setText(a["name"])
        self._away_score_l.setText(str(a["score"]))
        self._home_abbr.setText(h["abbr"])
        self._home_name_l.setText(h["name"])
        self._home_score_l.setText(str(h["score"]))
        note = f" · {d['note']}" if d["note"] else ""
        self._meta.setText(f"{d['date_label']}{note}")
        stars = d.get("three_stars") or []
        if stars:
            medals = ["1st", "2nd", "3rd"]
            parts = []
            for i, s in enumerate(stars):
                name = s.get("name", "?")
                team = f" ({s['team']})" if s.get("team") else ""
                detail = f" {s['detail']}" if s.get("detail") else ""
                star_txt = f"★ {medals[i] if i < 3 else ''} {name}{team}{detail}"
                if i == 0:
                    parts.append(
                        f'<span style="color:#f5c518;font-weight:700;">'
                        f"{star_txt}</span>")
                else:
                    parts.append(star_txt)
            self._stars.setText(" &nbsp;&nbsp; ".join(parts))
        else:
            self._stars.setText("")
        self._render_scoring()

    def _clear_pane(self, key):
        pane = self._panes[key]
        layout = pane._layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _empty_label(self, msg):
        l = QLabel(msg)
        l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet(
            "color: %s; font-size: 14px; padding: 40px;" % _MUTED)
        return l

    def _render_scoring(self):
        self._clear_pane("scoring")
        layout = self._panes["scoring"]._layout
        goals = self._data.get("scoring") or []
        if not goals:
            layout.addWidget(self._empty_label(
                "Detailed scoring data is unavailable for this game."))
            return
        last_period = None
        for g in goals:
            if g.get("period_label") != last_period:
                last_period = g.get("period_label")
                pl = QLabel(str(last_period or "").upper())
                pl.setStyleSheet(
                    "font-size: 13px; font-weight: 800; color: %s;"
                    "letter-spacing: 0.6px; margin-top: 8px;" % _BLUE)
                layout.addWidget(pl)
            card = QFrame()
            card.setStyleSheet(_PANEL.replace("14px", "10px"))
            cl = QHBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            left = QVBoxLayout()
            left.setSpacing(2)
            assists = g.get("assists") or []
            scorer_txt = g.get("scorer", "?")
            if assists:
                scorer_txt += f" ({', '.join(assists)})"
            else:
                scorer_txt += " (unassisted)"
            scorer = QLabel(scorer_txt)
            scorer.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: %s;" % _TEXT)
            scorer.setWordWrap(True)
            left.addWidget(scorer)
            sub = g.get("time_str", "")
            if g.get("strength") and g["strength"] != "EV":
                sub += f" · {g['strength']}"
            if g.get("goal_type"):
                sub += f" · {g['goal_type']}"
            sub_l = QLabel(sub)
            sub_l.setStyleSheet(
                "font-size: 12px; color: %s;" % _DIM)
            left.addWidget(sub_l)
            cl.addLayout(left, 1)
            right = QHBoxLayout()
            right.setSpacing(10)
            strength = g.get("strength", "EV")
            if strength and strength != "EV":
                badge = QLabel(strength)
                bg = {"PP": "#4ade80", "SH": "#f5c518"}.get(
                    strength, "#6b7a94")
                fg = "#0b1220" if strength != "EN" else "#eef3fb"
                badge.setStyleSheet(
                    f"font-size: 11px; font-weight: 800; color: {fg};"
                    f"background: {bg}; border-radius: 6px; padding: 3px 8px;")
                right.addWidget(badge)
            running = (f"{self._data['away']['abbr']} "
                       f"{g.get('away_running', 0)} – "
                       f"{g.get('home_running', 0)} "
                       f"{self._data['home']['abbr']}")
            run_l = QLabel(running)
            run_l.setStyleSheet(
                "font-size: 14px; font-weight: 800; color: %s;" % _TEXT)
            right.addWidget(run_l)
            cl.addLayout(right)
            layout.addWidget(card)

    def _team_toggle(self, layout, names, current, on_pick):
        for n in names:
            btn = QPushButton(n)
            btn.setCursor(Qt.PointingHandCursor)
            active = (n == current)
            btn.setStyleSheet(
                ("background: %s; border: 1px solid %s; color: #fff;"
                 % (_BLUE, _BLUE)) if active else
                ("background: rgba(13, 20, 34, 0.86); color: %s;"
                 "border: 1px solid rgba(59, 130, 246, 0.18);" % _MUTED) +
                "border-radius: 10px; padding: 8px 16px;"
                "font-size: 13px; font-weight: 700;")
            btn.clicked.connect(lambda _=False, nn=n: on_pick(nn))
            layout.addWidget(btn)

    def _make_table(self, headers):
        tbl = QTableWidget()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        tbl.setStyleSheet(
            "QTableWidget { background: rgba(13, 20, 34, 0.86);"
            " border: 1px solid rgba(59, 130, 246, 0.14);"
            " border-radius: 12px; color: %s; font-size: 13px; }"
            "QTableWidget::item { padding: 9px 12px;"
            " border-bottom: 1px solid rgba(255,255,255,0.04); }"
            "QHeaderView::section { background: transparent; color: %s;"
            " font-size: 11px; font-weight: 700; letter-spacing: 0.8px;"
            " border: none; padding: 10px 12px; }"
            % (_CELL, _DIM))
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        return tbl

    def _render_players(self):
        self._clear_pane("players")
        layout = self._panes["players"]._layout
        teams = self._data.get("players") or {}
        names = list(teams.keys())
        if not names:
            layout.addWidget(self._empty_label(
                "Per-player stats are unavailable for this game."))
            return
        if not self._players_team or self._players_team not in teams:
            self._players_team = names[0]
        toggle_row = QHBoxLayout()
        toggle_row.setAlignment(Qt.AlignLeft)
        self._team_toggle(toggle_row, names, self._players_team,
                          lambda n: (setattr(self, "_players_team", n),
                                     self._render_players()))
        layout.addLayout(toggle_row)
        t = teams[self._players_team] or {}
        if not t.get("has_stats", True):
            layout.addWidget(self._empty_label(
                "Per-player stats are unavailable for this game."))
            return
        sec = QLabel("SKATERS")
        sec.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: %s;"
            "letter-spacing: 0.6px; margin-top: 8px;" % _BLUE)
        layout.addWidget(sec)
        skaters = t.get("skaters") or []
        tbl = self._make_table(
            ["Player", "Pos", "G", "A", "P", "SOG", "Hits", "Blk", "FO"])
        tbl.setRowCount(len(skaters))
        for i, s in enumerate(skaters):
            vals = [str(s.get("player", {}).get("name", "?") 
                        if isinstance(s.get("player"), dict)
                        else s.get("player", "?")),
                    str(s.get("pos", "")), str(s.get("g", 0)),
                    str(s.get("a", 0)), str(s.get("p", 0)),
                    str(s.get("sog", 0)), str(s.get("hits", 0)),
                    str(s.get("blk", 0)), str(s.get("fo", ""))]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if j == 0:
                    item.setFont(self._bold_font())
                if j == 4:
                    item.setForeground(Qt.GlobalColor.blue)
                tbl.setItem(i, j, item)
        layout.addWidget(tbl)
        goalies = t.get("goalies") or []
        if goalies:
            sec2 = QLabel("GOALTENDERS")
            sec2.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: %s;"
                "letter-spacing: 0.6px; margin-top: 8px;" % _BLUE)
            layout.addWidget(sec2)
            gt = self._make_table(
                ["Goaltender", "SA", "Saves", "SV%", "GA"])
            gt.setRowCount(len(goalies))
            for i, gg in enumerate(goalies):
                svp = gg.get("svp")
                svp_txt = "–" if svp is None else f"{svp:.1f}%"
                vals = [str(gg.get("player", {}).get("name", "?")
                            if isinstance(gg.get("player"), dict)
                            else gg.get("player", "?")),
                        str(gg.get("sa", 0)), str(gg.get("saves", 0)),
                        svp_txt, str(gg.get("ga", 0))]
                for j, v in enumerate(vals):
                    item = QTableWidgetItem(v)
                    if j == 0:
                        item.setFont(self._bold_font())
                    gt.setItem(i, j, item)
            layout.addWidget(gt)

    def _bold_font(self):
        from PySide6.QtGui import QFont
        f = QFont()
        f.setBold(True)
        return f

    def _rating_color(self, r):
        if r is None:
            return _MUTED
        if r >= 7.0:
            return "#4ade80"
        if r >= 5.5:
            return "#f5c518"
        return "#ff8a8a"

    def _render_lines(self):
        self._clear_pane("lines")
        layout = self._panes["lines"]._layout
        lines = self._data.get("lines") or {}
        names = list(lines.keys())
        if not names:
            layout.addWidget(self._empty_label(
                "Line combinations are unavailable for this game."))
            return
        if not self._lines_team or self._lines_team not in lines:
            self._lines_team = names[0]
        toggle_row = QHBoxLayout()
        toggle_row.setAlignment(Qt.AlignLeft)
        self._team_toggle(toggle_row, names, self._lines_team,
                          lambda n: (setattr(self, "_lines_team", n),
                                     self._render_lines()))
        layout.addLayout(toggle_row)
        legend = QLabel("5.0 = average game · 7.0+ = great")
        legend.setStyleSheet(
            "color: %s; font-size: 12px;" % _DIM)
        layout.addWidget(legend)
        units = lines[self._lines_team] or []
        if not units or not any((u.get("players") or []) for u in units):
            layout.addWidget(self._empty_label(
                "Line combinations are unavailable for this game."))
            return
        for u in units:
            head = QHBoxLayout()
            lbl = QLabel(str(u.get("label", "")))
            lbl.setStyleSheet(
                "font-size: 14px; font-weight: 800; color: %s;" % _TEXT)
            head.addWidget(lbl)
            head.addStretch()
            rating = u.get("rating")
            rt = QLabel(f"Rating {rating:.1f}" if rating is not None else "Rating –")
            rt.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: %s;"
                % self._rating_color(rating))
            head.addWidget(rt)
            layout.addLayout(head)
            players = u.get("players") or []
            tbl = self._make_table(
                ["Player", "Pos", "G", "A", "P", "Grade", "Key Stats"])
            tbl.setRowCount(len(players))
            for i, p in enumerate(players):
                grade = p.get("grade")
                grade_txt = "–" if grade is None else f"{grade:.1f}"
                vals = [str(p.get("player", {}).get("name", "?")
                            if isinstance(p.get("player"), dict)
                            else p.get("player", "?")),
                        str(p.get("pos", "")), str(p.get("g", 0)),
                        str(p.get("a", 0)), str(p.get("p", 0)),
                        grade_txt, str(p.get("why", ""))]
                for j, v in enumerate(vals):
                    item = QTableWidgetItem(v)
                    if j == 0:
                        item.setFont(self._bold_font())
                    if j == 5 and grade is not None:
                        from PySide6.QtGui import QColor
                        item.setForeground(QColor(self._rating_color(grade)))
                    tbl.setItem(i, j, item)
            layout.addWidget(tbl)

    def _render_teams(self):
        self._clear_pane("teams")
        layout = self._panes["teams"]._layout
        rows = self._data.get("team_stats") or []
        a, h = self._data["away"], self._data["home"]
        tbl = self._make_table(["", a["abbr"], h["abbr"]])
        tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [str(r.get("label", "")), str(r.get("away", "")),
                    str(r.get("home", ""))]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if j == 0:
                    item.setForeground(Qt.GlobalColor.gray)
                else:
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFont(self._bold_font())
                tbl.setItem(i, j, item)
        layout.addWidget(tbl)
