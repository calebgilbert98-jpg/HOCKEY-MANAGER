"""Lines editor: 9-tab layout per Caleb's v0.26.13 redesign.

Tabs: OVERVIEW (read-only condensed) | LINE 1-4 | PP1 | PP2 | PK1 | PK2
Each line tab shows forwards + D pairings. Goalies on Line 1.
Save posts the complete slot map so unseen lines are preserved.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QGridLayout, QScrollArea, QMessageBox,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable


class LineSlot(QFrame):
    """Single player slot in a line (click to fill from roster)."""

    def __init__(self, slot_id, label, parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.player = None
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(56)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self._label = QLabel(label)
        self._label.setObjectName("tile-title")
        self._name = QLabel("— empty —")
        self._name.setStyleSheet(
            "color: #ffffff; font-size: 14px; font-weight: 700;")
        layout.addWidget(self._label)
        layout.addWidget(self._name)

    def set_player(self, player):
        self.player = player
        if player:
            self._name.setText(getattr(player, "full_name", "?"))
        else:
            self._name.setText("— empty —")

    def clear(self):
        self.set_player(None)


class LineEditorTab(QWidget):
    """Editable tab for a single line (forwards + defense)."""

    # Slot definitions per tab
    SLOTS = {
        "line1": [("LW1", "Left Wing"), ("C1", "Center"), ("RW1", "Right Wing"),
                  ("D1", "Defense"), ("D2", "Defense"),
                  ("G1", "Goalie")],
        "line2": [("LW2", "Left Wing"), ("C2", "Center"), ("RW2", "Right Wing"),
                  ("D3", "Defense"), ("D4", "Defense")],
        "line3": [("LW3", "Left Wing"), ("C3", "Center"), ("RW3", "Right Wing"),
                  ("D5", "Defense"), ("D6", "Defense")],
        "line4": [("LW4", "Left Wing"), ("C4", "Center"), ("RW4", "Right Wing")],
        "pp1": [("PP1_LW", "Left Wing"), ("PP1_C", "Center"),
                ("PP1_RW", "Right Wing"), ("PP1_D1", "Defense"),
                ("PP1_D2", "Defense")],
        "pp2": [("PP2_LW", "Left Wing"), ("PP2_C", "Center"),
                ("PP2_RW", "Right Wing"), ("PP2_D1", "Defense"),
                ("PP2_D2", "Defense")],
        "pk1": [("PK1_F1", "Forward"), ("PK1_F2", "Forward"),
                ("PK1_D1", "Defense"), ("PK1_D2", "Defense")],
        "pk2": [("PK2_F1", "Forward"), ("PK2_F2", "Forward"),
                ("PK2_D1", "Defense"), ("PK2_D2", "Defense")],
    }

    def __init__(self, tab_id, title, game, parent=None):
        super().__init__(parent)
        self.tab_id = tab_id
        self.game = game
        self._slots = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel(title.upper())
        header.setObjectName("section-header")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (slot_id, label) in enumerate(self.SLOTS.get(tab_id, [])):
            slot = LineSlot(slot_id, label)
            slot.mousePressEvent = lambda e, s=slot: self._on_slot_click(s)
            row, col = divmod(i, 3)
            grid.addWidget(slot, row, col)
            self._slots[slot_id] = slot
        layout.addLayout(grid)
        layout.addStretch()

    def _on_slot_click(self, slot):
        # Emit signal to parent to open roster picker
        parent = self.parent()
        while parent and not hasattr(parent, "open_roster_picker"):
            parent = parent.parent()
        if parent:
            parent.open_roster_picker(slot)

    def get_slot_map(self):
        """Return {slot_id: player} for saving."""
        return {sid: s.player for sid, s in self._slots.items()}

    def load_slot_map(self, slot_map):
        for sid, slot in self._slots.items():
            slot.set_player(slot_map.get(sid))


class LinesScreen(BaseScreen):
    title = "Lines"

    TAB_ORDER = [
        ("overview", "OVERVIEW"),
        ("line1", "LINE 1"),
        ("line2", "LINE 2"),
        ("line3", "LINE 3"),
        ("line4", "LINE 4"),
        ("pp1", "PP1"),
        ("pp2", "PP2"),
        ("pk1", "PK1"),
        ("pk2", "PK2"),
    ]

    def _build_body(self):
        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs, 1)

        # Overview tab (read-only condensed)
        self._overview = QLabel("Overview — condensed line view")
        self._overview.setAlignment(Qt.AlignTop)
        self._overview.setStyleSheet("color: #9aa4b8; font-size: 14px;")
        self.tabs.addTab(self._overview, "OVERVIEW")

        # Editable line tabs
        self._line_tabs = {}
        for tab_id, title in self.TAB_ORDER[1:]:
            tab = LineEditorTab(tab_id, title, self.game)
            self.tabs.addTab(tab, title)
            self._line_tabs[tab_id] = tab

        # Save button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save Lines")
        save_btn.setObjectName("primary-btn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        self._layout.addLayout(btn_row)

    def open_roster_picker(self, slot):
        """Open a dialog to pick a player for the slot."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Select player for {slot.slot_id}")
        dlg.setMinimumSize(700, 500)
        layout = QVBoxLayout(dlg)

        table = PlayerTable()
        table.set_main_window(self.main_window)
        try:
            team = getattr(self.game, "user_team", None)
            if team:
                players = list(getattr(team, "roster", None) or [])
                table.set_players(players)
        except Exception:
            pass
        layout.addWidget(table)

        def _pick(player):
            slot.set_player(player)
            dlg.accept()

        table.player_clicked.connect(_pick)
        dlg.exec()

    def _save(self):
        """Save the complete slot map (all tabs) so unseen lines are preserved."""
        try:
            full_map = {}
            for tab_id, tab in self._line_tabs.items():
                full_map.update(tab.get_slot_map())
            # Convert native slot IDs (LW1, C1, RW1) to sim format (F1_LW, F1_C, F1_RW)
            # The sim reads F1_LW..F4_RW / D1_L..D3_R / G1 keys
            sim_map = self._to_sim_format(full_map)
            # Save to game: user_team.lineup (both formats for compatibility)
            user_team = getattr(self.game, "user_team", None)
            if user_team is not None:
                # Merge: keep native keys for load-back, add sim keys for the engine
                merged = dict(full_map)
                merged.update(sim_map)
                user_team.lineup = merged
            QMessageBox.information(self, "Lines", "Lines saved.")
        except Exception as e:
            QMessageBox.warning(self, "Lines", f"Save failed: {e}")

    @staticmethod
    def _to_sim_format(slot_map):
        """Convert native slot IDs to sim-readable F1_LW format."""
        import re
        sim = {}
        # LW1 -> F1_LW, C1 -> F1_C, RW1 -> F1_RW
        for slot_id, player in slot_map.items():
            if not player:
                continue
            m = re.match(r'^(LW|C|RW)(\d+)$', slot_id)
            if m:
                pos, num = m.groups()
                sim[f'F{num}_{pos}'] = player
                continue
            # D1, D2 -> D1_L, D1_R (pair them)
            m = re.match(r'^D(\d+)$', slot_id)
            if m:
                num = int(m.group(1))
                pair = (num + 1) // 2  # D1,D2 -> D1 pair; D3,D4 -> D2 pair
                side = 'L' if num % 2 == 1 else 'R'
                sim[f'D{pair}_{side}'] = player
                continue
            # G1 -> G1 (already correct)
            if slot_id == 'G1':
                sim['G1'] = player
        return sim

    def refresh(self):
        """Load current lines from game object."""
        try:
            user_team = getattr(self.game, "user_team", None)
            if user_team is None:
                return
            lineup = getattr(user_team, "lineup", None)
            if not lineup:
                return
            # Populate slots from saved lineup
            for tab_id, tab in self._line_tabs.items():
                slot_map = tab.get_slot_map()
                for slot_id in slot_map:
                    if slot_id in lineup:
                        player = lineup[slot_id]
                        # Find the slot widget and set player
                        for i in range(tab.layout().count()):
                            widget = tab.layout().itemAt(i).widget()
                            if hasattr(widget, "slot_id") and widget.slot_id == slot_id:
                                widget.set_player(player)
                                break
        except Exception:
            pass
