"""Training Camp: camp storyline timeline, camp ratings, and scrimmages.

Camp runs Sep 12-30 per training_camp.py CAMP_START=(9,12).

Tabs:
- Timeline: camp storyline from league.preseason_stories (read-only)
- Camp Ratings: per-scrimmage 1-10 player ratings, camp averages,
  standout flags, with right-click player context menu
- Scrimmages: Red vs White scrimmage log with 3 stars

Ratings data comes from training_camp.get_camp_table(team) which
returns [(player, ratings, avg, standout), ...]. Scrimmage data from
team.camp_scrimmages (list of dicts with date/red/white/stars).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
)
from PySide6.QtCore import Qt

from .base import BaseScreen

# Training camp window (training_camp.py CAMP_START=(9,12), runs Sep 12-30).
CAMP_LABEL = "Sep 12 – 30"
ROSTER_LIMIT = 23


class CampScreen(BaseScreen):
    title = "Training Camp"

    def _build_body(self):
        self._tabs = QTabWidget()

        # --- Timeline tab (existing functionality) ---
        timeline_page = QWidget()
        tl_layout = QVBoxLayout(timeline_page)
        tl_layout.setContentsMargins(0, 8, 0, 0)

        window_lbl = QLabel(f"Camp window: {CAMP_LABEL}")
        window_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        tl_layout.addWidget(window_lbl)

        self._note = QLabel("")
        self._note.setStyleSheet("color: #cdd6e4; font-size: 14px;")
        self._note.setWordWrap(True)
        tl_layout.addWidget(self._note)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._timeline = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline)
        self._timeline_layout.setSpacing(10)
        self._timeline_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._timeline)
        tl_layout.addWidget(self._scroll, 1)

        # --- Camp Ratings tab ---
        ratings_page = QWidget()
        rt_layout = QVBoxLayout(ratings_page)
        rt_layout.setContentsMargins(0, 8, 0, 0)

        self._ratings_status = QLabel("")
        self._ratings_status.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        rt_layout.addWidget(self._ratings_status)

        self._ratings_table = QTableWidget()
        self._ratings_table.setAlternatingRowColors(True)
        self._ratings_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._ratings_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._ratings_table.setSortingEnabled(True)
        self._ratings_table.verticalHeader().setVisible(False)
        # Right-click -> player context menu (EHM-style)
        self._ratings_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._ratings_table.customContextMenuRequested.connect(
            self._on_ratings_context_menu)
        # Double-click -> open player profile
        self._ratings_table.cellDoubleClicked.connect(self._on_ratings_double_click)
        rt_layout.addWidget(self._ratings_table, 1)
        self._ratings_players = []  # parallel list of player objects

        # --- Scrimmages tab ---
        scrims_page = QWidget()
        sc_layout = QVBoxLayout(scrims_page)
        sc_layout.setContentsMargins(0, 8, 0, 0)

        self._scrims_status = QLabel("")
        self._scrims_status.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        sc_layout.addWidget(self._scrims_status)

        self._scrims_table = QTableWidget()
        self._scrims_table.setColumnCount(3)
        self._scrims_table.setHorizontalHeaderLabels(
            ["Date", "Red – White", "3 Stars"])
        self._scrims_table.setAlternatingRowColors(True)
        self._scrims_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._scrims_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._scrims_table.setSortingEnabled(True)
        self._scrims_table.verticalHeader().setVisible(False)
        header = self._scrims_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        sc_layout.addWidget(self._scrims_table, 1)

        # --- Refresh button ---
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(120)
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()

        # --- Assemble ---
        self._tabs.addTab(timeline_page, "Timeline")
        self._tabs.addTab(ratings_page, "Camp Ratings")
        self._tabs.addTab(scrims_page, "Scrimmages")
        self._layout.addWidget(self._tabs, 1)
        self._layout.addLayout(btn_row)

    # --- data helpers -----------------------------------------------------
    def _team(self):
        try:
            team = getattr(self.game, "user_team", None)
            if team is None:
                gm = getattr(self.game, "game_manager", None)
                team = getattr(gm, "user_team", None) if gm else None
            return team
        except Exception:
            return None

    def _stories(self):
        """Return [(date_str, story)] from league.preseason_stories."""
        entries = []
        try:
            league = getattr(self.game, "league", None)
            if league is None:
                gm = getattr(self.game, "game_manager", None)
                league = getattr(gm, "league", None) if gm else None
            stories = getattr(league, "preseason_stories", None) or []
        except Exception:
            stories = []
        for s in stories:
            try:
                if isinstance(s, dict):
                    d, story = s.get("date"), s.get("story")
                elif isinstance(s, (list, tuple)) and len(s) >= 2:
                    d, story = s[0], s[1]
                else:
                    continue
                text = str(story or "").strip()
                if not text:
                    continue
                try:
                    date_str = d.strftime("%b %d")
                except Exception:
                    date_str = str(d) if d is not None else ""
                entries.append((date_str, text))
            except Exception:
                continue
        return entries

    def _roster_size(self):
        try:
            team = self._team()
            return len(getattr(team, "roster", None) or [])
        except Exception:
            return 0

    def _camp_rows(self):
        """Return [(player, ratings, avg, standout)] from training_camp."""
        try:
            import training_camp as _tc
        except Exception:
            return []
        team = self._team()
        if team is None:
            return []
        try:
            return list(_tc.get_camp_table(team) or [])
        except Exception:
            return []

    def _scrimmages(self):
        team = self._team()
        if team is None:
            return []
        return list(getattr(team, "camp_scrimmages", None) or [])

    def _tier_label(self, player):
        """User-facing talent tier label (never the numeric overall)."""
        try:
            from attribute_composites import talent_tier_for_player
            return talent_tier_for_player(player)
        except Exception:
            return "Decent"

    # --- timeline ---------------------------------------------------------
    def _clear_timeline(self):
        while self._timeline_layout.count():
            item = self._timeline_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _story_card(self, date_str, text):
        card = QFrame()
        card.setObjectName("tile")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        date_lbl = QLabel(date_str)
        date_lbl.setObjectName("tile-title")
        story_lbl = QLabel(text)
        story_lbl.setStyleSheet("color: #cdd6e4; font-size: 14px;")
        story_lbl.setWordWrap(True)
        layout.addWidget(date_lbl)
        layout.addWidget(story_lbl)
        return card

    def _refresh_timeline(self):
        stories = self._stories()
        roster_size = self._roster_size()

        # Client-side over-23-man warning (mirrors camp.js renderCamp).
        over = (" — camp invites have the roster over the 23-man limit, "
                "so cut/waiver decisions are pending"
                if roster_size > ROSTER_LIMIT else "")
        self._note.setText(
            f"Camp ran {CAMP_LABEL} and its storylines are below. "
            f"{roster_size} players are currently on the roster{over}.")

        self._clear_timeline()
        if stories:
            for date_str, text in stories:
                self._timeline_layout.addWidget(
                    self._story_card(date_str, text))
        else:
            empty = QLabel(
                "No camp report yet\n\n"
                "Training camp runs Sep 12–30 during new-season setup. "
                "Start or load a season that went through camp to see "
                "the storylines here.")
            empty.setStyleSheet(
                "color: #6b7488; font-size: 14px; font-weight: 700;")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            self._timeline_layout.addWidget(empty)

    # --- ratings tab ------------------------------------------------------
    def _note_for(self, player, ratings, avg, standout):
        if standout:
            return "Standout"
        if avg and avg <= 4.5 and len(ratings) >= 2:
            return "Poor camp"
        try:
            age = int(getattr(player, "age", 99) or 99)
        except Exception:
            age = 99
        if age <= 21 and avg and avg >= 7.0 and len(ratings) >= 2:
            return "Pushing for a spot"
        return ""

    def _condition_str(self, player):
        try:
            import condition_ui as _cu
            c = _cu.get_condition(player)
            return f"{c} ({_cu.condition_label(c)})"
        except Exception:
            return "--"

    def _pos_str(self, player):
        pos = getattr(player, "primary_position", None) or getattr(
            player, "position", "")
        return getattr(pos, "name", str(pos) or "")

    def _refresh_ratings(self):
        rows = self._camp_rows()
        scrims = self._scrimmages()
        n_games = max((len(r) for _, r, _, _ in rows), default=0)

        # Status line: in session / final report / opens Sep 12
        try:
            import training_camp as _tc
            cur = getattr(self.game, "current_date", None)
            if _tc.is_camp_day(cur):
                status = (f"Camp in session — {len(scrims)} scrimmage(s) "
                          f"played. Camp closes September 30; cuts follow "
                          f"in early October.")
            elif rows:
                status = (f"Final camp report — {len(rows)} players "
                          f"attended, {len(scrims)} scrimmages.")
            else:
                status = "Camp opens September 12."
        except Exception:
            status = ""
        self._ratings_status.setText(status)

        cols = (["Player", "Age", "Pos", "Tier"]
                + [f"S{i + 1}" for i in range(n_games)]
                + ["Avg", "Cond", "Note"])
        table = self._ratings_table
        table.setSortingEnabled(False)
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setRowCount(len(rows) if rows else 1)
        self._ratings_players = []

        if rows:
            for row, (p, ratings, avg, standout) in enumerate(rows):
                self._ratings_players.append(p)
                vals = [
                    str(getattr(p, "full_name", "?")),
                    str(getattr(p, "age", "?")),
                    self._pos_str(p),
                    self._tier_label(p),
                ]
                for i in range(n_games):
                    try:
                        vals.append(f"{ratings[i]:.1f}"
                                    if i < len(ratings) else "--")
                    except Exception:
                        vals.append("--")
                try:
                    vals.append(f"{avg:.1f}")
                except Exception:
                    vals.append("--")
                vals.append(self._condition_str(p))
                vals.append(self._note_for(p, ratings, avg, standout))
                for col, v in enumerate(vals):
                    item = QTableWidgetItem(v)
                    if col == 0:
                        item.setData(Qt.UserRole + 1, p)
                    # Numeric columns sort numerically
                    if col in (1, 4 + n_games):  # Age, Avg
                        try:
                            item.setData(Qt.UserRole, float(v))
                        except (ValueError, TypeError):
                            pass
                    table.setItem(row, col, item)
        else:
            item = QTableWidgetItem(
                "No camp data yet — camp opens September 12.")
            table.setItem(0, 0, item)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)

    def _on_ratings_context_menu(self, pos):
        if not self.main_window:
            return
        try:
            from ..widgets.context_menu import EntityContextMenu
            row = self._ratings_table.rowAt(pos.y())
            if row < 0 or row >= len(self._ratings_players):
                return
            player = self._ratings_players[row]
            is_user = False
            try:
                team = self._team()
                if team and player in (getattr(team, "roster", None) or []):
                    is_user = True
            except Exception:
                pass
            menu = EntityContextMenu.player_menu(
                self.main_window, player, is_user_team=is_user)
            menu.exec(self._ratings_table.mapToGlobal(pos))
        except Exception:
            pass

    def _on_ratings_double_click(self, row, col):
        if 0 <= row < len(self._ratings_players):
            try:
                self.main_window.show_player(self._ratings_players[row])
            except Exception:
                pass

    # --- scrimmages tab ---------------------------------------------------
    def _refresh_scrimmages(self):
        scrims = self._scrimmages()
        self._scrims_status.setText(
            f"{len(scrims)} scrimmage(s) played."
            if scrims else "No scrimmages played yet — camp opens September 12.")

        table = self._scrims_table
        table.setSortingEnabled(False)
        table.setRowCount(len(scrims) if scrims else 1)
        if scrims:
            for row, s in enumerate(scrims):
                try:
                    if isinstance(s, dict):
                        date = str(s.get("date", ""))
                        score = f"{s.get('red', 0)} - {s.get('white', 0)}"
                        stars = ", ".join(s.get("stars", []) or [])
                    else:
                        date = str(getattr(s, "date", ""))
                        score = (f"{getattr(s, 'red', 0)} - "
                                 f"{getattr(s, 'white', 0)}")
                        stars = ", ".join(getattr(s, "stars", []) or [])
                except Exception:
                    date, score, stars = "", "", ""
                table.setItem(row, 0, QTableWidgetItem(date))
                table.setItem(row, 1, QTableWidgetItem(score))
                table.setItem(row, 2, QTableWidgetItem(stars))
        else:
            table.setItem(0, 0, QTableWidgetItem("No scrimmages played yet."))
        table.setSortingEnabled(True)

    # --- refresh ----------------------------------------------------------
    def refresh(self):
        self._refresh_timeline()
        self._refresh_ratings()
        self._refresh_scrimmages()
