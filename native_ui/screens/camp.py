"""Training Camp: camp storyline timeline (read-only).

Data comes from league.preseason_stories (camp ran Sep 12-30 per
training_camp.py CAMP_START=(9,12)). Read-only; no game calls mutate
state. The over-23-man roster warning is computed client-side from the
roster count.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt

from .base import BaseScreen

# Training camp window (training_camp.py CAMP_START=(9,12), runs Sep 12-30).
CAMP_LABEL = "Sep 12 – 30"
ROSTER_LIMIT = 23


class CampScreen(BaseScreen):
    title = "Training Camp"

    def _build_body(self):
        window_lbl = QLabel(f"Camp window: {CAMP_LABEL}")
        window_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(window_lbl)

        self._note = QLabel("")
        self._note.setStyleSheet("color: #cdd6e4; font-size: 14px;")
        self._note.setWordWrap(True)
        self._layout.addWidget(self._note)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._timeline = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline)
        self._timeline_layout.setSpacing(10)
        self._timeline_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._timeline)
        self._layout.addWidget(self._scroll, 1)

    # --- data -------------------------------------------------------------
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
            team = getattr(self.game, "user_team", None)
            if team is None:
                gm = getattr(self.game, "game_manager", None)
                team = getattr(gm, "user_team", None) if gm else None
            return len(getattr(team, "roster", None) or [])
        except Exception:
            return 0

    # --- refresh ----------------------------------------------------------
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

    def refresh(self):
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
