"""Daily results dialog: shown after advancing the day.

Shows games played, scores, and notable events. Replaces the web UI's
/api/daily_results modal.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QFrame,
)
from PySide6.QtCore import Qt


class DailyResultsDialog(QDialog):
    """Modal showing the results of the simmed day."""

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Daily Results")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        title = QLabel("DAILY RESULTS")
        title.setObjectName("dialog-title")
        layout.addWidget(title)

        self._date_label = QLabel("")
        self._date_label.setStyleSheet("color: #8b95ab; font-size: 13px;")
        layout.addWidget(self._date_label)

        # Scrollable game list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll, 1)

        self._games_widget = QWidget()
        self._games_layout = QVBoxLayout(self._games_widget)
        self._games_layout.setSpacing(8)
        scroll.setWidget(self._games_widget)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Continue")
        close_btn.setObjectName("primary-btn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._load_results()

    def _load_results(self):
        """Load today's game results from the game object."""
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            # Date
            cur_date = getattr(gm, "current_date", None)
            if cur_date and hasattr(cur_date, "strftime"):
                self._date_label.setText(cur_date.strftime("%B %d, %Y"))

            # Get today's completed games from the schedule
            games = self._get_todays_games(gm)
            if not games:
                lbl = QLabel("No games played today.")
                lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
                lbl.setAlignment(Qt.AlignCenter)
                self._games_layout.addWidget(lbl)
                return

            for game_info in games:
                self._games_layout.addWidget(self._make_game_card(game_info))

            self._games_layout.addStretch()
        except Exception as e:
            print(f"[daily-results] load failed: {e}")

    def _get_todays_games(self, gm):
        """Extract today's completed games from the league schedule."""
        games = []
        try:
            league = getattr(gm, "league", None)
            if not league:
                return games
            schedule = getattr(league, "schedule", None) or []
            today = getattr(gm, "current_date", None)
            for entry in schedule:
                if not isinstance(entry, dict):
                    continue
                # Only completed games from today
                if entry.get("home_score") is None:
                    continue
                game_date = entry.get("date")
                # Match today's date (or most recent if no date match)
                if today and game_date and game_date != today:
                    continue
                games.append(entry)
                if len(games) >= 20:  # cap display
                    break
        except Exception:
            pass
        return games

    def _make_game_card(self, game_info):
        card = QFrame()
        card.setObjectName("tile")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)

        home = self._team_name(game_info.get("home_team"))
        away = self._team_name(game_info.get("away_team"))
        hs = game_info.get("home_score", "?")
        aws = game_info.get("away_score", "?")

        label = QLabel(f"{away}  {aws}  —  {hs}  {home}")
        label.setStyleSheet(
            "color: #ffffff; font-size: 15px; font-weight: 700;")
        layout.addWidget(label)
        layout.addStretch()
        return card

    @staticmethod
    def _team_name(team):
        if isinstance(team, str):
            return team
        return getattr(team, "team_name", str(team))
