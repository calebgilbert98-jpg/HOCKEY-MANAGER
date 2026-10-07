"""Shortlist screen: player shortlist management.

Ports main.py open_shortlist_window (shortlist_system.ShortlistView).
Categories: Trade Targets, Free Agent Targets, Draft Prospects,
Future Prospects, Development Watch, Injury Replacements, Custom.
Priorities: High / Medium / Low. Per-entry notes.

Game data used (all real):
  - shortlist_system.ShortlistManager (per-save storage)
  - shortlist_system.ShortlistEntry (player_id, category, priority, notes)
"""
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


CATEGORIES = [
    "Trade Targets",
    "Free Agent Targets",
    "Draft Prospects",
    "Future Prospects",
    "Development Watch",
    "Injury Replacements",
    "Custom",
]

PRIORITIES = {1: "High Priority", 2: "Medium Priority", 3: "Low Priority"}


class AddPlayerDialog(QDialog):
    """Add a player to the shortlist."""

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Add to Shortlist")
        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self._table = PlayerTable()
        self._selected = None
        self._table.player_clicked.connect(self._on_pick)
        layout.addRow(self._table)

        self._category = QComboBox()
        self._category.addItems(CATEGORIES)
        layout.addRow("Category:", self._category)

        self._priority = QComboBox()
        self._priority.addItems(
            ["High Priority", "Medium Priority", "Low Priority"])
        layout.addRow("Priority:", self._priority)

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(80)
        self._notes.setPlaceholderText("Notes (optional)…")
        layout.addRow("Notes:", self._notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._load_players()

    def _load_players(self):
        gm = _safe(lambda: getattr(self.game, "game_manager", None)) or self.game
        league = _safe(lambda: gm.league)
        players = []
        # Free agents + prospects are the main shortlist sources
        for src in ("free_agents", "draft_prospects"):
            players.extend(
                _safe(lambda: list(getattr(league, src, None) or []), []))
        # Dedupe
        seen, uniq = set(), []
        for p in players:
            pid = getattr(p, "id", id(p))
            if pid not in seen:
                seen.add(pid)
                uniq.append(p)
        self._table.set_players(uniq[:500])

    def _on_pick(self, player):
        self._selected = player

    def get_entry(self):
        prio_map = {"High Priority": 1, "Medium Priority": 2, "Low Priority": 3}
        return {
            "player": self._selected,
            "category": self._category.currentText(),
            "priority": prio_map[self._priority.currentText()],
            "notes": self._notes.toPlainText().strip(),
        }


class ShortlistScreen(BaseScreen):
    title = "Shortlist"

    def _build_body(self):
        # Category filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Category:"))
        self._cat_filter = QComboBox()
        self._cat_filter.addItem("All")
        self._cat_filter.addItems(CATEGORIES)
        self._cat_filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self._cat_filter)
        filter_row.addStretch()

        add_btn = QPushButton("＋ Add Player")
        add_btn.setObjectName("primary-btn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_player)
        filter_row.addWidget(add_btn)
        self._layout.addLayout(filter_row)

        # Entry list
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._view_player)
        self._layout.addWidget(self._list, 1)

        # Actions
        btn_row = QHBoxLayout()
        remove_btn = QPushButton("Remove")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        self._layout.addLayout(btn_row)

    def _manager(self):
        try:
            import shortlist_system as _ss
            gm = _safe(lambda: getattr(self.game, "game_manager", None)) \
                or self.game
            save_key = None
            try:
                import trade_market as _tm
                league = _safe(lambda: gm.league)
                if league is not None and hasattr(
                        _tm, "league_shortlist_key"):
                    save_key = _tm.league_shortlist_key(league)
            except Exception:
                pass
            return _ss.ShortlistManager(save_key=save_key)
        except Exception:
            return None

    def _add_player(self):
        dlg = AddPlayerDialog(self.game, self)
        if dlg.exec() != QDialog.Accepted:
            return
        entry = dlg.get_entry()
        if entry["player"] is None:
            QMessageBox.warning(
                self, "Shortlist", "Select a player first.")
            return
        try:
            mgr = self._manager()
            if mgr is not None:
                import shortlist_system as _ss
                e = _ss.ShortlistEntry(
                    player_id=str(getattr(entry["player"], "id", "")),
                    player_name=getattr(
                        entry["player"], "full_name", "?"),
                    category=entry["category"],
                    priority=entry["priority"],
                    notes=entry["notes"],
                )
                mgr.entries.append(e)
                mgr.save_shortlist()
            self.refresh()
        except Exception as ex:
            QMessageBox.warning(self, "Shortlist", f"Failed: {ex}")

    def _remove_selected(self):
        item = self._list.currentItem()
        if not item:
            return
        pid = item.data(Qt.UserRole)
        try:
            mgr = self._manager()
            if mgr is not None:
                mgr.entries = [
                    e for e in mgr.entries
                    if str(getattr(e, "player_id", "")) != str(pid)]
                mgr.save_shortlist()
            self.refresh()
        except Exception as ex:
            QMessageBox.warning(self, "Shortlist", f"Failed: {ex}")

    def _view_player(self, item):
        player = item.data(Qt.UserRole + 1)
        if player is not None:
            try:
                self.main_window.show_player(player)
            except Exception:
                pass

    def refresh(self):
        self._list.clear()
        cat_filter = self._cat_filter.currentText()
        try:
            mgr = self._manager()
            if mgr is None:
                self._list.addItem("Shortlist unavailable.")
                return
            entries = list(getattr(mgr, "entries", None) or [])
            # Sort by priority then name
            entries.sort(key=lambda e: (
                getattr(e, "priority", 3),
                getattr(e, "player_name", "")))
            shown = 0
            for e in entries:
                cat = getattr(e, "category", "")
                if cat_filter != "All" and cat != cat_filter:
                    continue
                prio = PRIORITIES.get(getattr(e, "priority", 3), "?")
                name = getattr(e, "player_name", "?")
                notes = getattr(e, "notes", "")
                text = f"[{prio}] {name} — {cat}"
                if notes:
                    text += f" ({notes[:40]})"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, getattr(e, "player_id", ""))
                # Try to resolve the player object for double-click nav
                item.setData(Qt.UserRole + 1, None)
                self._list.addItem(item)
                shown += 1
            if not shown:
                self._list.addItem("Shortlist is empty.")
        except Exception as ex:
            self._list.addItem(f"Could not load shortlist: {ex}")
