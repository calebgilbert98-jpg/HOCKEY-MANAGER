"""Lines editor: 9-tab layout per Caleb's v0.26.13 redesign.

Tabs: OVERVIEW (read-only condensed) | LINE 1-4 | PP1 | PP2 | PK1 | PK2
Each line tab shows forwards + D pairings. Goalies on Line 1.
Save posts the complete slot map so unseen lines are preserved.

Web parity (lines.html/lines.js):
  - Auto Best / Clear / Cancel toolbar buttons (contextual per tab)
  - Player picker: search box, position filters (All/F/D/G),
    streak filters (hot/cold), sort dropdown
  - Position-fit legend (green=natural, yellow=playable, red=out of position)
  - Overview tab: condensed read-only grid of every line/unit with fit colors
  - Remove player from slot (right-click on a filled slot)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QGridLayout, QScrollArea, QMessageBox, QDialog, QLineEdit,
    QComboBox, QMenu,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable


# ---------------------------------------------------------------------------
# Position fit (mirrors web FAM table; uses engine familiarity when available)
# ---------------------------------------------------------------------------

def _pos_key(pos):
    """Normalize a position to its string key."""
    try:
        return pos.value if hasattr(pos, "value") else str(pos)
    except Exception:
        return str(pos)


def _natural_fit(primary_pos, slot_pos):
    """True when primary_pos is a natural fit for slot_pos, treating
    generic 'F'/'D' slots (e.g. PK1_F1, PP1_D1) by position group."""
    p, s = primary_pos.upper(), slot_pos.upper()
    if p == s:
        return True
    if s == "F":
        return p in ("LW", "C", "RW", "F")
    if s == "D":
        return p in ("LD", "RD", "D")
    return False


def position_fit(player, slot_id):
    """Return 'green' (natural), 'yellow' (playable), or 'red' (out of
    position) for a player in a slot. Mirrors web lines.js fitClass."""
    if player is None:
        return ""
    try:
        from position_training import get_familiarity
        slot_pos = _slot_pos(slot_id)
        primary = _pos_key(getattr(player, "primary_position", None)
                           or getattr(player, "position", None))
        if not slot_pos or not primary:
            return ""
        if _natural_fit(primary, slot_pos):
            return "green"
        fam_pos = slot_pos
        if slot_pos.upper() == "F":
            # The familiarity table has no generic 'F' key (falls back to 30
            # for everyone); use center as the representative forward slot.
            fam_pos = "C"
        fam = get_familiarity(player, fam_pos)
        return "yellow" if fam >= 60 else "red"
    except Exception:
        pass
    # Fallback: natural fit by position group, else red
    try:
        primary = _pos_key(getattr(player, "primary_position", None)
                           or getattr(player, "position", None))
        slot_pos = _slot_pos(slot_id)
        if primary and slot_pos and _natural_fit(primary, slot_pos):
            return "green"
        return "red"
    except Exception:
        return ""


def _slot_pos(slot_id):
    """'LW1' -> 'LW'; 'PP1_LW' -> 'LW'; 'D3' -> 'D';
    'PP1_D1'/'PP1_D2' -> 'D'; 'PK1_F1'/'PK2_F2' -> 'F'."""
    import re
    s = str(slot_id or "")
    m = re.match(r"^([A-Z]+)\d+$", s)
    if m:
        return m.group(1)
    # Unit prefix with numeric position suffix: strip the digits so
    # special-teams slots resolve to a generic position.
    m = re.match(r"^[A-Z]+\d+_([A-Z]+?)(\d*)$", s)
    if m:
        return m.group(1)
    return ""


def _pos_group(player):
    """'F', 'D', or 'G' for filter pills."""
    pos = _pos_key(getattr(player, "primary_position", None)
                   or getattr(player, "position", "")).upper()
    if pos == "G":
        return "G"
    if pos in ("LD", "RD", "D"):
        return "D"
    return "F"


def _fit_stylesheet(fit):
    """Border color for a slot based on position fit."""
    if fit == "green":
        return "border: 2px solid #22c55e;"
    if fit == "yellow":
        return "border: 2px solid #eab308;"
    if fit == "red":
        return "border: 2px solid #ef4444;"
    return ""


class LineSlot(QFrame):
    """Single player slot in a line (click to fill from roster).

    Right-click a filled slot to remove the player.
    """

    def __init__(self, slot_id, label, parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.player = None
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(56)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self._label = QLabel(label)
        self._label.setObjectName("tile-title")
        self._name = QLabel("— empty —")
        self._name.setStyleSheet(
            "color: #ffffff; font-size: 14px; font-weight: 700;")
        layout.addWidget(self._label)
        layout.addWidget(self._name)

    def _on_context_menu(self, pos):
        if self.player is None:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("Remove player from slot")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == remove_action:
            self.clear()
            # Notify parent tab so it can mark dirty / refresh overview
            parent = self.parent()
            while parent and not hasattr(parent, "on_slot_changed"):
                parent = parent.parent()
            if parent and hasattr(parent, "on_slot_changed"):
                parent.on_slot_changed()

    def set_player(self, player):
        self.player = player
        if player:
            self._name.setText(getattr(player, "full_name", "?"))
        else:
            self._name.setText("— empty —")
        self._update_fit_style()

    def _update_fit_style(self):
        fit = position_fit(self.player, self.slot_id)
        base = ""
        self.setStyleSheet(base + _fit_stylesheet(fit))

    def clear(self):
        self.set_player(None)


class LineEditorTab(QWidget):
    """Editable tab for a single line (forwards + defense)."""

    # Slot definitions per tab
    SLOTS = {
        "line1": [("LW1", "Left Wing"), ("C1", "Center"), ("RW1", "Right Wing"),
                  ("D1", "Defense"), ("D2", "Defense"),
                  ("G1", "Starter"), ("G2", "Backup")],
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
        self._on_change = None  # callback set by LinesScreen

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

        # Position-fit legend (web parity: lines.html .le-legend)
        legend = QHBoxLayout()
        legend.setSpacing(8)
        legend.addWidget(QLabel("Fit:"))
        for color, text in (("#22c55e", "Natural position"),
                            ("#eab308", "Playable"),
                            ("#ef4444", "Out of position")):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            legend.addWidget(dot)
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)
        layout.addStretch()

    def on_slot_changed(self):
        """Called when a slot is cleared via right-click."""
        if self._on_change:
            self._on_change()

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

    def clear_slots(self):
        """Empty all slots on this tab."""
        for slot in self._slots.values():
            slot.clear()
        if self._on_change:
            self._on_change()

    def auto_best(self, all_players, used_ids):
        """Fill this tab's slots with the best available players.

        Mirrors web autoBestLine: prefer natural position, fall back to
        best overall. Skips players already dressed elsewhere.
        """
        def _overall(p):
            try:
                return float(getattr(p, "overall", 0) or 0)
            except Exception:
                return 0

        def _is_goalie(p):
            return _pos_key(getattr(p, "primary_position", None)
                            or getattr(p, "position", "")).upper() == "G"

        skaters = sorted(
            [p for p in all_players if not _is_goalie(p)],
            key=_overall, reverse=True)
        goalies = sorted(
            [p for p in all_players if _is_goalie(p)],
            key=_overall, reverse=True)

        def _pid(p):
            return str(getattr(p, "id", id(p)))

        def pick_skater(want_pos):
            want = want_pos.upper()
            # For generic 'D' slots, accept LD/RD/D players;
            # for generic 'F' slots, accept LW/C/RW/F players.
            def _matches(p):
                ppos = _pos_key(getattr(p, "primary_position", None)
                                or getattr(p, "position", "")).upper()
                if ppos == want:
                    return True
                if want == "D" and ppos in ("LD", "RD", "D"):
                    return True
                if want == "F" and ppos in ("LW", "C", "RW", "F"):
                    return True
                if want in ("LD", "RD") and ppos == "D":
                    return True
                return False
            # Prefer natural position match
            for p in skaters:
                if _pid(p) in used_ids:
                    continue
                if _matches(p):
                    used_ids.add(_pid(p))
                    return p
            # Fall back to best available
            for p in skaters:
                if _pid(p) not in used_ids:
                    used_ids.add(_pid(p))
                    return p
            return None

        def pick_goalie():
            for p in goalies:
                if _pid(p) not in used_ids:
                    used_ids.add(_pid(p))
                    return p
            return None

        for slot_id, slot in self._slots.items():
            want = _slot_pos(slot_id)
            if want == "G":
                slot.set_player(pick_goalie())
            else:
                slot.set_player(pick_skater(want))
        if self._on_change:
            self._on_change()


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
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._layout.addWidget(self.tabs, 1)

        # Overview tab (read-only condensed) — scrollable
        overview_scroll = QScrollArea()
        overview_scroll.setWidgetResizable(True)
        self._overview_label = QLabel("Loading overview…")
        self._overview_label.setAlignment(Qt.AlignTop)
        self._overview_label.setStyleSheet(
            "color: #e8ecf4; font-size: 14px; padding: 12px;")
        self._overview_label.setTextFormat(Qt.RichText)
        self._overview_label.setWordWrap(True)
        overview_scroll.setWidget(self._overview_label)
        self.tabs.addTab(overview_scroll, "OVERVIEW")

        # Editable line tabs
        self._line_tabs = {}
        for tab_id, title in self.TAB_ORDER[1:]:
            tab = LineEditorTab(tab_id, title, self.game)
            tab._on_change = self._on_slots_changed
            self.tabs.addTab(tab, title)
            self._line_tabs[tab_id] = tab

        # Snapshot for Cancel (revert unsaved changes)
        self._saved_snapshot = {}

        # Toolbar: Auto Best / Clear / Cancel / Save (web parity)
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._auto_btn = QPushButton("Auto Best")
        self._auto_btn.setToolTip("Fill this tab with the best available players")
        self._auto_btn.setCursor(Qt.PointingHandCursor)
        self._auto_btn.clicked.connect(self._auto_best)
        btn_row.addWidget(self._auto_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Empty this tab's slots")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_tab)
        btn_row.addWidget(self._clear_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setToolTip("Revert unsaved changes")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel_edits)
        btn_row.addWidget(self._cancel_btn)

        save_btn = QPushButton("Save Lines")
        save_btn.setObjectName("primary-btn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        self._layout.addLayout(btn_row)

        self._update_toolbar()

    def _on_tab_changed(self, index):
        """Refresh overview when switching to it; update toolbar state."""
        self._update_toolbar()
        if index == 0:
            self._render_overview()

    def _update_toolbar(self):
        """Auto Best / Clear / Cancel only make sense on editable tabs."""
        is_overview = self.tabs.currentIndex() == 0
        self._auto_btn.setEnabled(not is_overview)
        self._clear_btn.setEnabled(not is_overview)
        self._cancel_btn.setEnabled(not is_overview)

    def _current_tab(self):
        idx = self.tabs.currentIndex()
        if idx <= 0:
            return None
        tab_id = self.TAB_ORDER[idx][0]
        return self._line_tabs.get(tab_id)

    def _on_slots_changed(self):
        """A slot was filled or cleared — refresh overview if visible."""
        if self.tabs.currentIndex() == 0:
            self._render_overview()

    def _all_dressed_ids(self, exclude_tab=None):
        """Player IDs currently dressed on any tab (optionally excluding one)."""
        ids = set()
        for tab_id, tab in self._line_tabs.items():
            if tab_id == exclude_tab:
                continue
            for player in tab.get_slot_map().values():
                if player is not None:
                    ids.add(str(getattr(player, "id", id(player))))
        return ids

    def _find_dressed_slot(self, player_id, exclude_slot=None):
        """Return the slot_id where player_id is currently dressed, or None.

        exclude_slot: a LineSlot whose own occupant is ignored, so
        re-picking the player already in the target slot is a no-op
        rather than a duplicate.
        """
        for tab in self._line_tabs.values():
            for sid, s in tab._slots.items():
                if exclude_slot is not None and s is exclude_slot:
                    continue
                p = s.player
                if p is not None and str(getattr(p, "id", id(p))) == player_id:
                    return sid
        return None

    def _auto_best(self):
        """Fill the current tab with the best available players."""
        tab = self._current_tab()
        if tab is None:
            return
        try:
            team = getattr(self.game, "user_team", None)
            if not team:
                QMessageBox.warning(self, "Lines", "No team loaded.")
                return
            players = list(getattr(team, "roster", None) or [])
            # Free this tab's own slots so its players are re-pickable
            used = self._all_dressed_ids(exclude_tab=tab.tab_id)
            tab.auto_best(players, used)
            QMessageBox.information(
                self, "Lines",
                f"Auto Best applied to {tab.tab_id.upper()} — "
                "review the fits, then Save Lines.")
        except Exception as e:
            QMessageBox.warning(self, "Lines", f"Auto Best failed: {e}")

    def _clear_tab(self):
        """Empty all slots on the current tab."""
        tab = self._current_tab()
        if tab is None:
            return
        tab.clear_slots()

    def _cancel_edits(self):
        """Revert all tabs to the last saved snapshot."""
        try:
            for tab_id, tab in self._line_tabs.items():
                snap = self._saved_snapshot.get(tab_id, {})
                tab.load_slot_map(snap)
            self._render_overview()
            QMessageBox.information(self, "Lines", "Changes reverted.")
        except Exception as e:
            QMessageBox.warning(self, "Lines", f"Cancel failed: {e}")

    def _take_snapshot(self):
        """Snapshot current slot assignments for Cancel."""
        self._saved_snapshot = {
            tab_id: dict(tab.get_slot_map())
            for tab_id, tab in self._line_tabs.items()
        }

    def open_roster_picker(self, slot):
        """Open a dialog to pick a player for the slot.

        Web parity: search box, position filter pills (All/F/D/G),
        streak filters (hot/cold), sort dropdown.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Select player for {slot.slot_id}")
        dlg.setMinimumSize(760, 560)
        layout = QVBoxLayout(dlg)

        # --- Search ---
        search = QLineEdit()
        search.setPlaceholderText("Search players…")
        search.setClearButtonEnabled(True)
        layout.addWidget(search)

        # --- Filter pills: All / F / D / G / Hot / Cold ---
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_btns = {}
        self._picker_filter = "ALL"

        def _set_filter(f):
            self._picker_filter = f
            for key, btn in filter_btns.items():
                btn.setStyleSheet(
                    "font-weight: 700;" if key == f else "")
            _apply_filters()

        for key, label, tip in [
            ("ALL", "All", "All players"),
            ("F", "F", "Forwards"),
            ("D", "D", "Defense"),
            ("G", "G", "Goalies"),
            ("HOT", "🔥", "Players on a 3+ game point streak"),
            ("COLD", "❄️", "Scoreless drought"),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _c=False, k=key: _set_filter(k))
            filter_row.addWidget(btn)
            filter_btns[key] = btn
        filter_btns["ALL"].setChecked(True)
        filter_btns["ALL"].setStyleSheet("font-weight: 700;")
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # --- Sort dropdown ---
        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Sort:"))
        sort_box = QComboBox()
        sort_box.addItems(["Overall", "Points", "Hot streak",
                           "Age (youngest)", "Name"])
        sort_row.addWidget(sort_box)
        sort_row.addStretch()
        layout.addLayout(sort_row)

        # --- Player table ---
        table = PlayerTable()
        table.set_main_window(self.main_window)
        layout.addWidget(table, 1)

        # Roster pool
        try:
            team = getattr(self.game, "user_team", None)
            all_players = list(getattr(team, "roster", None) or []) if team else []
        except Exception:
            all_players = []

        def _points(p):
            try:
                return float(getattr(p, "goals", 0) or 0) + float(
                    getattr(p, "assists", 0) or 0)
            except Exception:
                return 0

        def _streak(p):
            try:
                return int(getattr(p, "current_point_streak", 0) or 0)
            except Exception:
                return 0

        def _apply_filters():
            q = search.text().strip().lower()
            f = self._picker_filter
            result = []
            for p in all_players:
                # Position / streak filter
                if f == "F" and _pos_group(p) != "F":
                    continue
                if f == "D" and _pos_group(p) != "D":
                    continue
                if f == "G" and _pos_group(p) != "G":
                    continue
                if f == "HOT" and _streak(p) < 3:
                    continue
                if f == "COLD" and _streak(p) > 0:
                    continue
                # Search filter
                if q and q not in str(
                        getattr(p, "full_name", "")).lower():
                    continue
                result.append(p)
            # Sort
            mode = sort_box.currentText()
            if mode == "Points":
                result.sort(key=lambda p: (_points(p),
                                           float(getattr(p, "overall", 0) or 0)),
                            reverse=True)
            elif mode == "Hot streak":
                result.sort(key=lambda p: (_streak(p), _points(p)),
                            reverse=True)
            elif mode == "Age (youngest)":
                result.sort(key=lambda p: float(getattr(p, "age", 99) or 99))
            elif mode == "Name":
                result.sort(key=lambda p: str(getattr(p, "full_name", "")))
            else:  # Overall
                result.sort(key=lambda p: float(getattr(p, "overall", 0) or 0),
                            reverse=True)
            table.set_players(result)

        search.textChanged.connect(lambda _t: _apply_filters())
        sort_box.currentTextChanged.connect(lambda _t: _apply_filters())
        _apply_filters()

        # Show current slot fit hint
        hint = QLabel(
            "Tip: green border = natural position, yellow = playable, "
            "red = out of position.")
        hint.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        def _pick(player):
            # One player, one slot (web parity: lines.js rejects a drop when
            # the player is already dressed elsewhere). Re-picking the player
            # already in this slot is a no-op, not a duplicate.
            if player is not None:
                pid = str(getattr(player, "id", id(player)))
                cur = slot.player
                cur_pid = (str(getattr(cur, "id", id(cur)))
                           if cur is not None else None)
                if pid != cur_pid:
                    dup_slot = self._find_dressed_slot(pid, exclude_slot=slot)
                    if dup_slot:
                        QMessageBox.warning(
                            dlg, "Lines",
                            f"{getattr(player, 'full_name', '?')} is already "
                            f"dressed on {dup_slot} — one player, one slot.")
                        return
            slot.set_player(player)
            self._on_slots_changed()
            dlg.accept()

        table.player_clicked.connect(_pick)
        dlg.exec()

    def _save(self):
        """Save the complete slot map (all tabs) so unseen lines are preserved."""
        try:
            full_map = {}
            for tab_id, tab in self._line_tabs.items():
                full_map.update(tab.get_slot_map())
            # One player, one slot: validate the whole map before writing.
            # The picker rejects duplicates at selection time; this guards
            # against tampered or programmatically-built state.
            seen = {}
            dupes = []
            for sid, player in full_map.items():
                if player is None:
                    continue
                pid = str(getattr(player, "id", id(player)))
                if pid in seen:
                    dupes.append((getattr(player, "full_name", "?"),
                                  seen[pid], sid))
                else:
                    seen[pid] = sid
            if dupes:
                details = "; ".join(
                    f"{name} on {a} and {b}" for name, a, b in dupes)
                QMessageBox.warning(
                    self, "Lines",
                    f"Cannot save: duplicate assignments — {details}. "
                    "One player, one slot.")
                return
            # Convert native slot IDs (LW1, C1, RW1) to sim format (F1_LW, F1_C, F1_RW)
            # The sim reads F1_LW..F4_RW / D1_L..D3_R / G1..G2 keys
            sim_map = self._to_sim_format(full_map)
            # Save to game: user_team.lineup (both formats for compatibility)
            user_team = getattr(self.game, "user_team", None)
            if user_team is not None:
                # Merge: keep native keys for load-back, add sim keys for the engine
                merged = dict(full_map)
                merged.update(sim_map)
                user_team.lineup = merged
            self._take_snapshot()
            self._render_overview()
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
            # G1/G2 -> G1/G2 (flat keys the sim reads; G2 is the backup —
            # web parity: web_ui writes both flat G1/G2 keys)
            if slot_id in ('G1', 'G2'):
                sim[slot_id] = player
                continue
            # PP/PK slots: PP1_LW -> PP1_F_LW, PP1_D1 -> PP1_D_L, PK1_F1 -> PK1_F_L
            m = re.match(r'^(PP\d+|PK\d+)_(LW|C|RW|D\d+|F\d+|G)$', slot_id)
            if m:
                unit, pos = m.groups()
                if pos in ('LW', 'C', 'RW'):
                    sim[f'{unit}_F_{pos}'] = player
                elif pos.startswith('D'):
                    dnum = int(pos[1:])
                    side = 'L' if dnum % 2 == 1 else 'R'
                    sim[f'{unit}_D_{side}'] = player
                elif pos.startswith('F'):
                    sim[f'{unit}_{pos}'] = player
                elif pos == 'G':
                    sim[f'{unit}_G'] = player
                continue
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
            # Populate slots from saved lineup using the tab's _slots dict
            for tab_id, tab in self._line_tabs.items():
                slots = getattr(tab, "_slots", {})
                for slot_id, slot in slots.items():
                    # Try direct match, then sim-key fallback (F1_LW -> LW1)
                    player = lineup.get(slot_id)
                    if player is None:
                        # Try converting sim key to native key
                        native_key = self._sim_to_native_key(slot_id)
                        if native_key:
                            player = lineup.get(native_key)
                    if player:
                        try:
                            slot.set_player(player)
                        except Exception:
                            pass
            self._take_snapshot()
            # Update overview tab
            self._render_overview()
        except Exception:
            pass

    def _sim_to_native_key(self, sim_key):
        """Convert sim key (F1_LW) to native key (LW1)."""
        import re
        m = re.match(r'^F(\d+)_(LW|C|RW)$', sim_key)
        if m:
            num, pos = m.groups()
            return f'{pos}{num}'
        m = re.match(r'^D(\d+)_(L|R)$', sim_key)
        if m:
            num, side = m.groups()
            # D1_L -> D1, D1_R -> D2, D2_L -> D3, etc.
            base = (int(num) - 1) * 2 + (1 if side == 'L' else 2)
            return f'D{base}'
        if sim_key in ('G1', 'G2'):
            return sim_key
        return None

    def _render_overview(self):
        """Render the overview tab with current line assignments.

        Condensed read-only grid of every line/unit with position-fit
        colors (web parity: lines.js renderOverview).
        """
        try:
            label = getattr(self, "_overview_label", None)
            if label is None:
                return
            # Collect current slot assignments from the tabs (live, unsaved)
            slot_map = {}
            for tab in self._line_tabs.values():
                slot_map.update(tab.get_slot_map())

            def _chip(slot_id, player):
                fit = position_fit(player, slot_id)
                if player:
                    name = getattr(player, "full_name", "?")
                    color = {"green": "#22c55e", "yellow": "#eab308",
                             "red": "#ef4444"}.get(fit, "#e8ecf4")
                    return (f'<span style="color:#9aa4b8;">{slot_id}</span> '
                            f'<b style="color:{color};">{name}</b>')
                return (f'<span style="color:#9aa4b8;">{slot_id}</span> '
                        '<span style="color:#555;">—</span>')

            def _line_avg(slot_ids):
                vals = []
                for sid in slot_ids:
                    p = slot_map.get(sid)
                    if p is not None:
                        try:
                            vals.append(float(getattr(p, "overall", 0) or 0))
                        except Exception:
                            pass
                return round(sum(vals) / len(vals)) if vals else None

            html = ['<div style="font-size:13px; line-height:1.9;">']
            html.append('<h3 style="color:#fff; margin:6px 0;">Even Strength</h3>')
            for i in range(1, 5):
                sids = [f"LW{i}", f"C{i}", f"RW{i}"]
                avg = _line_avg(sids)
                avg_txt = f" <span style='color:#9aa4b8;'>(OVR {avg})</span>" if avg else ""
                chips = " &nbsp;|&nbsp; ".join(_chip(s, slot_map.get(s)) for s in sids)
                html.append(f"<div><b>Line {i}</b>{avg_txt}: {chips}</div>")
            html.append('<h3 style="color:#fff; margin:6px 0;">Defense Pairings</h3>')
            for n in range(1, 4):
                sids = [f"D{(n - 1) * 2 + 1}", f"D{(n - 1) * 2 + 2}"]
                avg = _line_avg(sids)
                avg_txt = f" <span style='color:#9aa4b8;'>(OVR {avg})</span>" if avg else ""
                chips = " &nbsp;|&nbsp; ".join(_chip(s, slot_map.get(s)) for s in sids)
                html.append(f"<div><b>Pair {n}</b>{avg_txt}: {chips}</div>")
            g_avg = _line_avg(["G1", "G2"])
            g_txt = f" <span style='color:#9aa4b8;'>(OVR {g_avg})</span>" if g_avg else ""
            g_chips = " &nbsp;|&nbsp; ".join(
                _chip(s, slot_map.get(s)) for s in ("G1", "G2"))
            html.append(f"<div><b>Goalies</b>{g_txt}: {g_chips}</div>")

            html.append('<h3 style="color:#fff; margin:6px 0;">Special Teams</h3>')
            for unit, sids in [
                ("PP1", ["PP1_LW", "PP1_C", "PP1_RW", "PP1_D1", "PP1_D2"]),
                ("PP2", ["PP2_LW", "PP2_C", "PP2_RW", "PP2_D1", "PP2_D2"]),
                ("PK1", ["PK1_F1", "PK1_F2", "PK1_D1", "PK1_D2"]),
                ("PK2", ["PK2_F1", "PK2_F2", "PK2_D1", "PK2_D2"]),
            ]:
                chips = " &nbsp;|&nbsp; ".join(_chip(s, slot_map.get(s)) for s in sids)
                html.append(f"<div><b>{unit}</b>: {chips}</div>")

            html.append(
                '<p style="color:#9aa4b8; font-size:12px; margin-top:10px;">'
                "Read-only overview — pick a line or unit tab above to edit. "
                '<span style="color:#22c55e;">●</span> natural '
                '<span style="color:#eab308;">●</span> playable '
                '<span style="color:#ef4444;">●</span> out of position</p>')
            html.append("</div>")
            label.setText("".join(html))
        except Exception:
            pass

    def _get_player_name(self, player):
        """Get display name for a player object or None."""
        if not player:
            return "---"
        return getattr(player, 'full_name', getattr(player, 'name', '---'))
