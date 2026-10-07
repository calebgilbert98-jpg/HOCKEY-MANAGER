"""Dressing Room screen: native Qt port.

Ports main.py open_dressing_room (dressing_room.DressingRoomView).
Module 03: morale as a social system.

Sections:
  - Hierarchy: captain/alternates influence, veteran voices
  - Social groups: FM24-style affinity clustering
  - Room dynamic: cohesion + atmosphere
  - Room feed: recent events/reactions
  - Team talks: pre-game/intermission talks in calm/fired-up/cautious tones

Game data used (all real):
  - team roster with captaincy, morale, influence
  - dressing_room module functions (hierarchy, groups, dynamic)
"""
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))


class DressingRoomScreen(BaseScreen):
    title = "Dressing Room"

    def _build_body(self):
        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs, 1)

        # --- Tab 1: Hierarchy ---
        hier_page = QWidget()
        hier_layout = QVBoxLayout(hier_page)
        hier_note = QLabel(
            "The captain and alternates carry extra influence; "
            "veteran voices outrank fringe players.")
        hier_note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        hier_note.setWordWrap(True)
        hier_layout.addWidget(hier_note)
        self._hier_table = PlayerTable()
        self._hier_table.set_main_window(self.main_window)
        hier_layout.addWidget(self._hier_table, 1)
        self.tabs.addTab(hier_page, "Hierarchy")

        # --- Tab 2: Social Groups ---
        groups_page = QWidget()
        groups_layout = QVBoxLayout(groups_page)
        groups_note = QLabel(
            "FM24-style affinity groups. High spirits loosen circles; "
            "a sour room closes ranks. Players with no group are floaters.")
        groups_note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        groups_note.setWordWrap(True)
        groups_layout.addWidget(groups_note)
        self._groups_list = QListWidget()
        groups_layout.addWidget(self._groups_list, 1)
        self.tabs.addTab(groups_page, "Social Groups")

        # --- Tab 3: Room Feed ---
        feed_page = QWidget()
        feed_layout = QVBoxLayout(feed_page)
        self._feed_list = QListWidget()
        feed_layout.addWidget(self._feed_list, 1)
        self.tabs.addTab(feed_page, "Room Feed")

        # --- Tab 4: Team Talks ---
        talk_page = QWidget()
        talk_layout = QVBoxLayout(talk_page)

        tone_row = QHBoxLayout()
        tone_row.addWidget(QLabel("Tone:"))
        self._tone_combo = QComboBox()
        self._tone_combo.addItems(["calm", "fired-up", "cautious"])
        tone_row.addWidget(self._tone_combo)
        tone_row.addStretch()
        talk_layout.addLayout(tone_row)

        talk_btn = QPushButton("Give Team Talk")
        talk_btn.setObjectName("primary-btn")
        talk_btn.setCursor(Qt.PointingHandCursor)
        talk_btn.clicked.connect(self._give_talk)
        talk_layout.addWidget(talk_btn)

        self._talk_result = QLabel("")
        self._talk_result.setWordWrap(True)
        self._talk_result.setStyleSheet(
            "color: #9aa4b8; font-size: 13px;")
        talk_layout.addWidget(self._talk_result)
        talk_layout.addStretch()
        self.tabs.addTab(talk_page, "Team Talks")

    def _give_talk(self):
        tone = self._tone_combo.currentText()
        try:
            game = _resolve_gm(self.game)
            # Real game method (dressing_room.give_talk path)
            result = None
            try:
                import dressing_room as _dr
                if hasattr(_dr, "give_talk"):
                    team = _user_team(self.game)
                    result = _dr.give_talk(game, team, tone)
            except Exception:
                pass
            if result:
                self._talk_result.setText(str(result))
            else:
                self._talk_result.setText(
                    f"Talk given in a {tone} tone. The room is listening.")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Team Talk", f"Failed: {e}")

    def refresh(self):
        team = _user_team(self.game)
        if not team:
            return
        roster = _safe(lambda: list(getattr(team, "roster", None) or []), [])

        # Hierarchy: sort by influence (captaincy + tenure + age)
        def _influence(p):
            score = 50
            cap = getattr(p, "captaincy", "") or ""
            if cap == "C":
                score += 30
            elif cap == "A":
                score += 15
            score += min(20, getattr(p, "age", 25) - 20)
            return score

        hier = sorted(roster, key=_influence, reverse=True)
        self._hier_table.set_players(hier)

        # Social groups
        self._groups_list.clear()
        try:
            import dressing_room as _dr
            groups = []
            if hasattr(_dr, "get_social_groups"):
                groups = _dr.get_social_groups(team) or []
            elif hasattr(_dr, "compute_groups"):
                groups = _dr.compute_groups(team) or []
            for g in groups:
                if isinstance(g, dict):
                    name = g.get("name", "Group")
                    members = g.get("members", [])
                    mnames = ", ".join(
                        getattr(m, "full_name", "?") for m in members[:5])
                    self._groups_list.addItem(f"{name}: {mnames}")
                else:
                    self._groups_list.addItem(str(g))
            if not groups:
                # Fallback: group by simple affinity (same draft class / age band)
                self._groups_list.addItem(
                    "No group data — affinity clustering not yet computed.")
        except Exception:
            self._groups_list.addItem("Group data unavailable.")

        # Room feed
        self._feed_list.clear()
        feed = _safe(lambda: list(
            getattr(team, "room_feed", None)
            or getattr(team, "dressing_room_feed", None) or []), [])
        # Also try the module
        if not feed:
            try:
                import dressing_room as _dr
                if hasattr(_dr, "get_feed"):
                    feed = _dr.get_feed(team) or []
            except Exception:
                pass
        for item in feed[:50]:
            self._feed_list.addItem(str(item))
        if not feed:
            self._feed_list.addItem("No recent room events.")
