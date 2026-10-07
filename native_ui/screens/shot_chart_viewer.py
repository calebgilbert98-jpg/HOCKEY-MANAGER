"""Shot chart viewer: native Qt port.

Ports main.py open_shot_chart_viewer (shot_charts.ShotChartStore).
Renders shots on a rink diagram using QPainter.

Shot dict format: {x, y, side ('home'|'away'), result ('goal'|'save'|'block'|'miss')}.

Can view by game, team (last 5 games aggregated), or player.
"""
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class RinkWidget(QWidget):
    """Custom widget that paints a rink with shot markers."""

    # Rink dimensions (NHL: 200ft x 85ft), normalized 0-100
    def __init__(self, parent=None):
        super().__init__(parent)
        self._shots = []
        self.setMinimumSize(600, 300)

    def set_shots(self, shots):
        self._shots = list(shots or [])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        # Rink background
        p.fillRect(0, 0, w, h, QColor("#0d1626"))

        # Rink outline (rounded rect)
        pen = QPen(QColor("#e8edf5"), 2)
        p.setPen(pen)
        p.setBrush(QBrush(Qt.NoBrush))
        margin = 10
        p.drawRoundedRect(margin, margin, w - 2 * margin, h - 2 * margin,
                          30, 30)

        # Center line (red) and blue lines
        p.setPen(QPen(QColor("#ef4444"), 3))
        p.drawLine(w // 2, margin, w // 2, h - margin)
        p.setPen(QPen(QColor("#3B82F6"), 2))
        p.drawLine(w // 4, margin, w // 4, h - margin)
        p.drawLine(3 * w // 4, margin, 3 * w // 4, h - margin)

        # Center circle
        p.setPen(QPen(QColor("#3B82F6"), 2))
        p.drawEllipse(w // 2 - 30, h // 2 - 30, 60, 60)
        p.fillRect(w // 2 - 2, h // 2 - 2, 4, 4, QColor("#3B82F6"))

        # Goals (nets at each end)
        p.setPen(QPen(QColor("#ef4444"), 3))
        net_w, net_h = 8, 36
        p.drawRect(margin - net_w, h // 2 - net_h // 2, net_w, net_h)
        p.drawRect(w - margin, h // 2 - net_h // 2, net_w, net_h)

        # Shots
        for s in self._shots:
            try:
                x = float(s.get("x", 50)) / 100.0  # 0-100 -> 0-1
                y = float(s.get("y", 50)) / 100.0
                px = margin + x * (w - 2 * margin)
                py = margin + y * (h - 2 * margin)
                side = s.get("side", "home")
                result = s.get("result", "miss")
                base = QColor("#00ff9d") if side == "home" \
                    else QColor("#ff6b6b")

                if result == "goal":
                    # Gold X
                    r = 7
                    p.setPen(QPen(QColor("#ffd700"), 3))
                    p.drawLine(int(px - r), int(py), int(px + r), int(py))
                    p.drawLine(int(px), int(py - r), int(px), int(py + r))
                elif result == "save":
                    p.setPen(QPen(QColor("white"), 1))
                    p.setBrush(QBrush(base))
                    p.drawEllipse(int(px - 5), int(py - 5), 10, 10)
                elif result == "block":
                    p.setPen(QPen(base, 2))
                    pts = [(int(px), int(py - 6)),
                           (int(px - 6), int(py + 5)),
                           (int(px + 6), int(py + 5))]
                    from PySide6.QtGui import QPolygon
                    from PySide6.QtCore import QPoint
                    p.drawPolygon(QPolygon([QPoint(*pt) for pt in pts]))
                else:  # miss
                    p.setPen(QPen(base, 2))
                    p.drawEllipse(int(px - 3), int(py - 3), 6, 6)
            except Exception:
                continue

        p.end()


class ShotChartViewerScreen(BaseScreen):
    title = "Shot Chart"

    def __init__(self, game, main_window, parent=None):
        self._shots = []
        self._chart_title = "Shot Chart"
        super().__init__(game, main_window, parent)

    def set_view(self, game_id=None, team_name=None, player_id=None):
        """Load shots for a game, team, or player."""
        try:
            from shot_charts import ShotChartStore
            game = getattr(self.game, "game_manager", None) or self.game
            store = getattr(game, "shot_chart_store", None)
            if store is None:
                store = ShotChartStore()
                game.shot_chart_store = store

            shots = []
            if game_id:
                g = store.get(game_id)
                if g:
                    shots = g.get("shots", [])
                    self._chart_title = (
                        f"Shot Chart: {g.get('away', '')} @ "
                        f"{g.get('home', '')}")
            elif team_name:
                shots = store.aggregate_team_shots(team_name, last_n=5)
                self._chart_title = f"Shot Chart: {team_name} (last 5)"
            elif player_id:
                shots = store.for_player(player_id)
                self._chart_title = "Shot Chart: Player"
            self._shots = shots
            self.refresh()
        except Exception:
            pass

    def _build_body(self):
        self._title_label = QLabel("Shot Chart")
        self._title_label.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #ffffff;")
        self._layout.addWidget(self._title_label)

        # Legend
        legend = QHBoxLayout()
        for text, color in [("Goal", "#ffd700"), ("Save", "#00ff9d"),
                            ("Block", "#ff6b6b"), ("Miss", "#8b95ab")]:
            lbl = QLabel(f"● {text}")
            lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
            legend.addWidget(lbl)
        legend.addStretch()
        self._layout.addLayout(legend)

        self._rink = RinkWidget()
        self._layout.addWidget(self._rink, 1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #8b95ab; font-size: 12px;")
        self._layout.addWidget(self._count_label)

    def refresh(self):
        self._title_label.setText(self._chart_title)
        self._rink.set_shots(self._shots)
        n = len(self._shots)
        goals = sum(1 for s in self._shots if s.get("result") == "goal")
        self._count_label.setText(f"{n} shots, {goals} goals")
