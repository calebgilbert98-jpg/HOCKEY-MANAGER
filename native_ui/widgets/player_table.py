"""Reusable player table widget.

Sortable, clickable player list used across roster, free agents,
scouting, draft, and other screens. Replaces the HTML tables in web UI.
"""
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction


class PlayerTable(QTableWidget):
    """Sortable table of players with click-to-open-profile."""

    player_clicked = Signal(object)  # emits the player object

    # Columns: (key, header, width)
    COLUMNS = [
        ("name", "PLAYER", 180),
        ("pos", "POS", 60),
        ("age", "AGE", 50),
        ("overall", "OVR", 60),
        ("cap_hit", "CAP HIT", 100),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels([c[1] for c in self.COLUMNS])
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSortingEnabled(True)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for i, (_, _, w) in enumerate(self.COLUMNS):
            self.setColumnWidth(i, w)

        self._players = []
        self.cellDoubleClicked.connect(self._on_double_click)

        # Right-click context menu (Caleb: "everything should be clickable")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._main_window = None  # set via set_main_window()

    def set_main_window(self, main_window):
        """Set for context menu navigation."""
        self._main_window = main_window

    def _on_context_menu(self, pos):
        if not self._main_window:
            return
        try:
            from .context_menu import EntityContextMenu
            row = self.rowAt(pos.y())
            if row < 0 or row >= self.rowCount():
                return
            # Sort changes displayed row order, so self._players[row]
            # would target the wrong player. Use the player reference
            # stored on the name-column item instead.
            item = self.item(row, 0)
            player = item.data(Qt.UserRole + 1) if item is not None else None
            if player is None:
                return
            # Check if this is the user's team (for extra menu items)
            is_user = False
            try:
                team = getattr(
                    self._main_window.game, "user_team", None)
                if team and player in (getattr(team, "roster", None) or []):
                    is_user = True
            except Exception:
                pass
            menu = EntityContextMenu.player_menu(
                self._main_window, player, is_user_team=is_user)
            menu.exec(self.mapToGlobal(pos))
        except Exception as e:
            print(f"[player-table] context menu failed: {e}")

    def set_players(self, players):
        """Populate from a list of player objects. Direct Python objects,
        no JSON serialization."""
        self._players = list(players or [])
        self.setRowCount(len(self._players))
        self.setSortingEnabled(False)
        for row, p in enumerate(self._players):
            self._set_row(row, p)
        self.setSortingEnabled(True)

    def _set_row(self, row, p):
        vals = {
            "name": getattr(p, "full_name", "?"),
            "pos": self._pos_str(p),
            "age": str(getattr(p, "age", "?")),
            "overall": str(self._overall(p)),
            "cap_hit": self._cap_str(p),
        }
        for col, (key, _, _) in enumerate(self.COLUMNS):
            item = QTableWidgetItem(vals[key])
            # Numeric columns sort numerically
            if key in ("age", "overall"):
                try:
                    item.setData(Qt.UserRole, int(vals[key]))
                except (ValueError, TypeError):
                    pass
            # Store player ref on the name column
            if key == "name":
                item.setData(Qt.UserRole + 1, p)
            self.setItem(row, col, item)

    def _on_double_click(self, row, col):
        # Sort changes displayed row order, so self._players[row] would
        # emit the wrong player. Use the stored player reference instead.
        item = self.item(row, 0)
        player = item.data(Qt.UserRole + 1) if item is not None else None
        if player is not None:
            self.player_clicked.emit(player)

    @staticmethod
    def _pos_str(p):
        pos = getattr(p, "position", "?")
        # Handle enum or string
        return getattr(pos, "value", str(pos))

    @staticmethod
    def _overall(p):
        try:
            from game_classes import to_100_scale
            return to_100_scale(getattr(p, "overall", 50))
        except Exception:
            return getattr(p, "overall", "?")

    @staticmethod
    def _cap_str(p):
        try:
            contract = getattr(p, "contract", None)
            if contract:
                hit = getattr(contract, "cap_hit",
                              getattr(contract, "salary", 0))
                return f"${hit / 1e6:.2f}M"
        except Exception:
            pass
        return "—"
