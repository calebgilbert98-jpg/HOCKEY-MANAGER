"""Scouting screen: native Qt port of the web UI scouting page.

Ports web_ui/templates/scouting.html + web_ui/screens/scouting.py.
Calls the game object DIRECTLY -- no Flask, no HTTP, no JSON.

Three tabs:
  - Assignments & Reports: active assignments, regional beats, reports
  - Scouting Staff: department table
  - Player Database: paginated prospect browser with filters

Game data used (all real, same as the web bridge):
  - app.scouting_assignments (dict: player -> scout)
  - team.scouting_reports (dict: player_id -> report)
  - team.staff (filtered for scouts)
  - league.draft_prospects (+ draft_reentries)
  - every team in league.teams: roster + ahl_roster + prospects (trade targets)
  - league.free_agents
"""
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable
from native_ui.safe import safe_call

# Scouting profiles: custom attribute-weight filters (mainline parity).
# The logic module is GUI-free; the dialogs below are the Qt port of
# scouting_profile_dialog.py (Tkinter).
try:
    from scouting_profiles import (
        ALL_ATTRIBUTES, SKATER_ATTRIBUTES, GOALIE_ATTRIBUTES,
        ScoutingProfile, list_profiles, get_profile,
        save_custom_profile, delete_custom_profile,
        filter_by_profile, match_score, is_scouted as _profile_is_scouted,
    )
    _PROFILES_AVAILABLE = True
except Exception:
    _PROFILES_AVAILABLE = False
    ALL_ATTRIBUTES = {}
    SKATER_ATTRIBUTES = []
    GOALIE_ATTRIBUTES = []

_POSITION_GROUPS = [
    ("Any position", []),
    ("Forwards", ["C", "LW", "RW"]),
    ("Defense", ["LD", "RD"]),
    ("Goalies", ["G"]),
]

#: Prospects per page in the scout-assignment prospect picker. The picker is
#: paged, not capped: every prospect in the (optionally filtered) list is
#: reachable through the prev/next page buttons.
ASSIGNMENT_PAGE_SIZE = 200


def _resolve_gm(game):
    return safe_call(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (safe_call(lambda: gm.user_team)
            or safe_call(lambda: getattr(game, "user_team", None)))


def _pos_str(p):
    pos = getattr(p, "position", "?")
    return getattr(pos, "value", str(pos))


def _overall(p):
    try:
        return int(p.overall_rating())
    except Exception:
        pass
    try:
        from game_classes import to_100_scale
        return int(to_100_scale(getattr(p, "overall", 50)))
    except Exception:
        return int(getattr(p, "overall", 50) or 50)


class AssignDialog(QDialog):
    """New scouting assignment: pick prospect + scout."""

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("New Scouting Assignment")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        # Searchable prospect picker: type to filter, count shown.
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search prospects by name…")
        self._search_edit.textChanged.connect(self._filter_prospects)
        layout.addRow("Search:", self._search_edit)

        self._prospect_combo = QComboBox()
        self._scout_combo = QComboBox()
        self._all_prospects = []  # full list for filtering
        self._filtered = []       # current filter result (full-list order)
        self._page = 0            # 0-based page into _filtered

        self._match_label = QLabel()
        self._match_label.setStyleSheet("color: #6b7488; font-size: 11px;")
        layout.addRow("Prospect:", self._prospect_combo)
        layout.addRow("", self._match_label)

        # Pager: uncapped picker, ASSIGNMENT_PAGE_SIZE per page.
        page_row = QHBoxLayout()
        self._pick_prev = QPushButton("\u2190 Prev")
        self._pick_prev.clicked.connect(self._pick_prev_page)
        page_row.addWidget(self._pick_prev)
        self._pick_page_label = QLabel("Page 1")
        self._pick_page_label.setAlignment(Qt.AlignCenter)
        page_row.addWidget(self._pick_page_label, 1)
        self._pick_next = QPushButton("Next \u2192")
        self._pick_next.clicked.connect(self._pick_next_page)
        page_row.addWidget(self._pick_next)
        layout.addRow("", page_row)

        layout.addRow("Scout:", self._scout_combo)

        # Load options last: _apply_prospects needs the pager widgets above.
        self._load_options()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_options(self):
        gm = _resolve_gm(self.game)
        league = safe_call(lambda: gm.league, context="scouting/load_league")
        team = _user_team(self.game)

        prospects = safe_call(
            lambda: list(getattr(league, "draft_prospects", None) or []), [],
            context="scouting/load_prospects")
        # Keep the full list; the picker pages through all of it, so no
        # prospect is hidden by a cap.
        self._all_prospects = prospects
        self._apply_prospects("")

        staff = safe_call(lambda: list(getattr(team, "staff", None) or []), [],
                          context="scouting/load_staff")
        for s in staff:
            role = str(getattr(getattr(s, "role", None), "value",
                               getattr(s, "role", "") or ""))
            if "scout" in role.lower():
                self._scout_combo.addItem(
                    getattr(s, "full_name", getattr(s, "name", "?")), s)

    def _filter_prospects(self, text):
        self._page = 0
        self._apply_prospects(text)

    def _pick_prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._apply_prospects(self._search_edit.text())

    def _pick_next_page(self):
        self._page += 1
        self._apply_prospects(self._search_edit.text())

    def _apply_prospects(self, filter_text):
        """Recompute the filtered list, clamp the page, fill the combo.

        No cap on the total: every filtered prospect is reachable through
        the prev/next page buttons. Preserves the current selection when
        it is on the displayed page.
        """
        prev = self._prospect_combo.currentData()
        prev_id = (str(getattr(prev, "id", "") or "")
                   if prev is not None else None)
        needle = (filter_text or "").strip().lower()
        self._filtered = [
            p for p in self._all_prospects
            if not needle or needle in getattr(p, "full_name", "?").lower()
        ]
        total = len(self._filtered)
        n_pages = max(
            1, (total + ASSIGNMENT_PAGE_SIZE - 1) // ASSIGNMENT_PAGE_SIZE)
        self._page = min(max(self._page, 0), n_pages - 1)
        start = self._page * ASSIGNMENT_PAGE_SIZE
        end = min(start + ASSIGNMENT_PAGE_SIZE, total)
        self._prospect_combo.blockSignals(True)
        try:
            self._prospect_combo.clear()
            new_prev_index = -1
            for i, p in enumerate(self._filtered[start:end]):
                self._prospect_combo.addItem(
                    f"{getattr(p, 'full_name', '?')} "
                    f"({_pos_str(p)}, {_overall(p)} OVR)", p)
                if (prev_id is not None
                        and str(getattr(p, "id", "") or "") == prev_id):
                    new_prev_index = i
            if new_prev_index >= 0:
                self._prospect_combo.setCurrentIndex(new_prev_index)
        finally:
            self._prospect_combo.blockSignals(False)
        self._pick_page_label.setText(
            f"Page {self._page + 1} of {n_pages}")
        self._pick_prev.setEnabled(self._page > 0)
        self._pick_next.setEnabled(self._page < n_pages - 1)
        shown_from = start + 1 if total else 0
        self._match_label.setText(
            f"Showing {shown_from}-{end} of {total} prospects.")

    def get_selection(self):
        return (self._prospect_combo.currentData(),
                self._scout_combo.currentData())


class BeatDialog(QDialog):
    """Assign a scout to a regional beat."""

    REGIONS = ["OHL", "WHL", "QMJHL", "USHL", "NCAA", "SHL", "Liiga",
               "KHL", "Czech", "Slovakia", "Switzerland", "Germany"]

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Assign Regional Beat")
        self.setMinimumWidth(380)

        layout = QFormLayout(self)

        self._scout_combo = QComboBox()
        self._region_combo = QComboBox()
        self._region_combo.addItems(self.REGIONS)

        team = _user_team(game)
        staff = safe_call(lambda: list(getattr(team, "staff", None) or []), [])
        for s in staff:
            role = str(getattr(getattr(s, "role", None), "value",
                               getattr(s, "role", "") or ""))
            if "scout" in role.lower():
                self._scout_combo.addItem(
                    getattr(s, "full_name", getattr(s, "name", "?")), s)

        layout.addRow("Scout:", self._scout_combo)
        layout.addRow("Region:", self._region_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # Recall button: pull the selected scout off their beat.
        recall_btn = QPushButton("Recall from Beat")
        recall_btn.setToolTip(
            "Remove the selected scout from their current regional beat.")
        recall_btn.clicked.connect(self._recall)
        layout.addRow(recall_btn)

    def _recall(self):
        """Recall the selected scout from their regional beat."""
        scout = self._scout_combo.currentData()
        if scout is None:
            QMessageBox.warning(
                self, "Recall", "Select a scout to recall.")
            return
        try:
            gm = _resolve_gm(self.game)
            import scouting as _sm
            if hasattr(_sm, "set_scout_region"):
                _sm.set_scout_region(gm, scout, None)
            # Also clear on the scout object directly as fallback.
            try:
                setattr(scout, "region", None)
                setattr(scout, "beat", None)
            except Exception:
                pass
            QMessageBox.information(
                self, "Recall",
                f"{getattr(scout, 'full_name', getattr(scout, 'name', '?'))} "
                "recalled from regional beat.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Recall", f"Failed: {e}")

    def get_selection(self):
        return (self._scout_combo.currentData(),
                self._region_combo.currentText())


class ProfileManagerDialog(QDialog):
    """Browse, create, edit and delete scouting profiles.

    Qt port of scouting_profile_dialog.ScoutingProfileView (Tkinter).
    Built-in archetype profiles are read-only (marked ★); custom
    profiles (✎) can be edited and deleted.
    """

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Scouting Profiles")
        self.setMinimumSize(640, 480)

        layout = QHBoxLayout(self)

        # --- Left: profile list ---
        left = QVBoxLayout()
        left.addWidget(QLabel("Profiles"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)
        layout.addLayout(left, 1)

        # --- Right: details ---
        right = QVBoxLayout()
        self._name_label = QLabel("")
        self._name_label.setStyleSheet(
            "font-size: 16px; font-weight: bold;")
        right.addWidget(self._name_label)
        self._desc_label = QLabel("")
        self._desc_label.setStyleSheet("color: #8b95ab; font-size: 12px;")
        self._desc_label.setWordWrap(True)
        right.addWidget(self._desc_label)

        self._attr_table = QTableWidget()
        self._attr_table.setColumnCount(2)
        self._attr_table.setHorizontalHeaderLabels(
            ["Attribute", "Minimum"])
        self._attr_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._attr_table.setSelectionBehavior(QTableWidget.SelectRows)
        right.addWidget(self._attr_table, 1)

        self._pos_label = QLabel("")
        self._pos_label.setStyleSheet("color: #8b95ab; font-size: 12px;")
        right.addWidget(self._pos_label)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        new_btn = QPushButton("New Profile")
        new_btn.clicked.connect(self._new)
        btn_row.addWidget(new_btn)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._edit)
        btn_row.addWidget(self._edit_btn)
        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._delete)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        right.addLayout(btn_row)

        layout.addLayout(right, 2)

        self._profiles = []
        self._refresh_list()

    def _refresh_list(self, select_name=None):
        """Reload profiles from disk and repopulate the list."""
        if not _PROFILES_AVAILABLE:
            return
        self._profiles = list_profiles()
        self._list.clear()
        sel_row = 0
        for i, p in enumerate(self._profiles):
            tag = "★ " if p.builtin else "✎ "
            self._list.addItem(tag + p.name)
            if select_name and p.name == select_name:
                sel_row = i
        if self._profiles:
            self._list.setCurrentRow(sel_row)
        else:
            self._clear_details()

    def _selected(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._profiles):
            return self._profiles[row]
        return None

    def _on_select(self, row=None):
        p = self._selected()
        if not p:
            self._clear_details()
            return
        tag = "★ " if p.builtin else "✎ "
        self._name_label.setText(tag + p.name)
        self._desc_label.setText(p.description or "—")
        attrs = sorted(p.attributes.items(),
                       key=lambda kv: ALL_ATTRIBUTES.get(kv[0], kv[0]))
        self._attr_table.setRowCount(len(attrs))
        for i, (key, minimum) in enumerate(attrs):
            self._attr_table.setItem(
                i, 0, QTableWidgetItem(ALL_ATTRIBUTES.get(key, key)))
            self._attr_table.setItem(i, 1, QTableWidgetItem(str(minimum)))
        pos = ", ".join(p.positions) if p.positions else "Any position"
        self._pos_label.setText(f"Positions: {pos}")
        can_edit = not p.builtin
        self._edit_btn.setEnabled(can_edit)
        self._del_btn.setEnabled(can_edit)

    def _clear_details(self):
        self._name_label.setText("")
        self._desc_label.setText("")
        self._attr_table.setRowCount(0)
        self._pos_label.setText("")
        self._edit_btn.setEnabled(False)
        self._del_btn.setEnabled(False)

    def _new(self):
        dlg = ProfileEditorDialog(self.game, self)
        if dlg.exec() == QDialog.Accepted and dlg.saved_name:
            self._refresh_list(select_name=dlg.saved_name)

    def _edit(self):
        p = self._selected()
        if p and not p.builtin:
            dlg = ProfileEditorDialog(self.game, self, profile=p)
            if dlg.exec() == QDialog.Accepted and dlg.saved_name:
                self._refresh_list(select_name=dlg.saved_name)

    def _delete(self):
        p = self._selected()
        if not p or p.builtin:
            return
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Delete your custom profile '{p.name}'?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            delete_custom_profile(p.name)
            self._refresh_list()


class ProfileEditorDialog(QDialog):
    """Create or edit a single custom scouting profile.

    Qt port of scouting_profile_dialog.ProfileEditorView (Tkinter).
    """

    def __init__(self, game, parent=None, profile=None):
        super().__init__(parent)
        self.game = game
        self._editing_name = profile.name if profile else None
        self.saved_name = None
        self.setWindowTitle(
            "Edit Scouting Profile" if profile else "New Scouting Profile")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # Name + description
        self._name_edit = QLineEdit(profile.name if profile else "")
        form.addRow("Profile name:", self._name_edit)
        self._desc_edit = QLineEdit(profile.description if profile else "")
        form.addRow("Description:", self._desc_edit)

        # Position scope
        self._pos_combo = QComboBox()
        for label, _codes in _POSITION_GROUPS:
            self._pos_combo.addItem(label)
        if profile:
            for i, (_label, codes) in enumerate(_POSITION_GROUPS):
                if codes == (profile.positions or []):
                    self._pos_combo.setCurrentIndex(i)
                    break
        form.addRow("Position scope:", self._pos_combo)

        # Attribute rows
        layout.addWidget(QLabel("Attribute minimums:"))
        self._attr_rows = []  # list of (combo, spinbox, row_widget)
        self._rows_layout = QVBoxLayout()
        layout.addLayout(self._rows_layout)

        add_btn = QPushButton("+ Add Attribute")
        add_btn.clicked.connect(lambda: self._add_row())
        layout.addWidget(add_btn)

        if profile:
            for key, minimum in profile.attributes.items():
                self._add_row(key, minimum)
        else:
            # Starter rows matching the mainline default
            self._add_row("toughness", 38)
            self._add_row("strength", 38)
            self._add_row("aggressiveness", 38)

        # Save / cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _attr_options(self):
        """Display labels for the attribute combo (goalies marked)."""
        opts = [label for _key, label in SKATER_ATTRIBUTES]
        opts += [f"{label} (G)" for _key, label in GOALIE_ATTRIBUTES]
        return opts

    def _label_to_key(self, label):
        label = label.replace(" (G)", "")
        for key, name in ALL_ATTRIBUTES.items():
            if name == label:
                return key
        return None

    def _key_to_label(self, key):
        name = ALL_ATTRIBUTES.get(key, key)
        goalie_keys = {k for k, _ in GOALIE_ATTRIBUTES}
        if key in goalie_keys:
            return name + " (G)"
        return name

    def _add_row(self, key=None, minimum=38):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        combo = QComboBox()
        combo.addItems(self._attr_options())
        combo.setEditable(False)
        if key:
            combo.setCurrentText(self._key_to_label(key))
        row_layout.addWidget(combo, 1)

        row_layout.addWidget(QLabel("min:"))
        from PySide6.QtWidgets import QSpinBox
        spin = QSpinBox()
        spin.setRange(1, 99)
        spin.setValue(minimum)
        row_layout.addWidget(spin)

        remove_btn = QPushButton("✕")
        remove_btn.setMaximumWidth(32)
        remove_btn.clicked.connect(lambda: self._remove_row(row))
        row_layout.addWidget(remove_btn)

        self._rows_layout.addWidget(row)
        self._attr_rows.append((combo, spin, row))

    def _remove_row(self, row_widget):
        self._attr_rows = [r for r in self._attr_rows if r[2] is not row_widget]
        row_widget.setParent(None)
        row_widget.deleteLater()

    def _save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name",
                                "Give your profile a name.")
            return
        existing = get_profile(name) if _PROFILES_AVAILABLE else None
        if existing and existing.builtin:
            QMessageBox.warning(
                self, "Name Taken",
                f"'{name}' is a pre-built profile. Choose another name.")
            return
        attrs = {}
        for combo, spin, _row in self._attr_rows:
            key = self._label_to_key(combo.currentText())
            if not key:
                continue
            attrs[key] = int(spin.value())
        if not attrs:
            QMessageBox.warning(self, "No Attributes",
                                "Add at least one attribute minimum.")
            return
        codes = dict(_POSITION_GROUPS).get(
            self._pos_combo.currentText(), [])
        profile = ScoutingProfile(
            name=name,
            description=self._desc_edit.text().strip(),
            attributes=attrs,
            positions=list(codes))
        save_custom_profile(profile)
        self.saved_name = name
        self.accept()


class ScoutingScreen(BaseScreen):
    title = "Scouting"

    # Database pagination
    DB_PAGE_SIZE = 100

    # Sentinel text for "no team filter" in the DB team combo box.
    # It is always item 0 (added first in _build_body/_refresh_db_teams);
    # filter logic must never hardcode this string -- compare by index.
    _ALL_TEAMS = "All teams"

    def __init__(self, game, main_window, parent=None):
        self._db_page = 0
        self._db_filter_q = ""
        self._db_filter_pos = "all"
        self._db_filter_status = "all"
        self._db_filter_team = "all"
        self._db_filter_age = "all"
        self._db_filter_ovr = "all"
        self._db_filter_profile = None  # ScoutingProfile or None
        self._db_cache = []
        super().__init__(game, main_window, parent)
        # Sync the cached filter state from the actual widget defaults.
        # The seeds above cannot be trusted to match what the widgets say
        # (e.g. _db_filter_team="all" vs the widget's "All teams"), and any
        # hand-seeded copy of widget defaults can drift again. Reading the
        # widgets is the only source of truth.
        self._on_db_filter()

    def _build_body(self):
        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_work_tab(), "Assignments & Reports")
        self.tabs.addTab(self._build_staff_tab(), "Scouting Staff")
        self.tabs.addTab(self._build_db_tab(), "Player Database")

    def _build_work_tab(self):
        """Tab 1: Assignments & Reports."""
        work = QWidget()
        work_layout = QVBoxLayout(work)
        work_layout.setSpacing(12)
        self._build_assignment_section(work_layout)
        self._build_beats_section(work_layout)
        self._build_reports_section(work_layout)
        return work

    def _build_assignment_section(self, layout):
        assign_box = QGroupBox("Active Assignments")
        assign_layout = QVBoxLayout(assign_box)
        assign_btn_row = QHBoxLayout()
        new_btn = QPushButton("＋ New Assignment")
        new_btn.setObjectName("primary-btn")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self._new_assignment)
        assign_btn_row.addWidget(new_btn)
        assign_btn_row.addStretch()
        assign_layout.addLayout(assign_btn_row)
        self._assign_list = QListWidget()
        assign_layout.addWidget(self._assign_list)
        layout.addWidget(assign_box)

    def _build_beats_section(self, layout):
        beat_box = QGroupBox("Regional Beats")
        beat_layout = QVBoxLayout(beat_box)
        beat_note = QLabel(
            "Scouts on a regional beat file reports on prospects "
            "from that region every day.")
        beat_note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        beat_layout.addWidget(beat_note)
        beat_btn_row = QHBoxLayout()
        beat_btn = QPushButton("Assign Regional Beat")
        beat_btn.setCursor(Qt.PointingHandCursor)
        beat_btn.clicked.connect(self._new_beat)
        beat_btn_row.addWidget(beat_btn)
        beat_btn_row.addStretch()
        beat_layout.addLayout(beat_btn_row)
        self._beat_list = QListWidget()
        beat_layout.addWidget(self._beat_list)
        layout.addWidget(beat_box)

    def _build_reports_section(self, layout):
        report_box = QGroupBox("Scouting Reports")
        report_layout = QVBoxLayout(report_box)
        self._report_list = QListWidget()
        report_layout.addWidget(self._report_list)
        layout.addWidget(report_box)

    def _build_staff_tab(self):
        """Tab 2: Scouting Staff."""
        staff_page = QWidget()
        staff_layout = QVBoxLayout(staff_page)
        self._staff_table = QTableWidget()
        self._staff_table.setColumnCount(6)
        self._staff_table.setHorizontalHeaderLabels(
            ["Scout", "Role", "Ability", "Beat", "Age", "Exp"])
        self._staff_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._staff_table.setSelectionBehavior(QTableWidget.SelectRows)
        staff_layout.addWidget(self._staff_table)
        return staff_page

    def _build_db_tab(self):
        """Tab 3: Player Database."""
        db_page = QWidget()
        db_layout = QVBoxLayout(db_page)
        self._build_db_filters(db_layout)
        self._build_db_results(db_layout)
        self._build_db_pagination(db_layout)
        return db_page

    def _build_db_filters(self, layout):
        filter_row = QHBoxLayout()
        self._db_search = QLineEdit()
        self._db_search.setPlaceholderText("Search name…")
        self._db_search.textChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_search)

        self._db_pos = QComboBox()
        self._db_pos.addItems(
            ["All positions", "Forwards", "Defense", "Goalies"])
        self._db_pos.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_pos)

        self._db_status = QComboBox()
        self._db_status.addItems(
            ["All players", "NHL rosters", "AHL rosters", "Prospects",
             "Free agents", "Draft eligible"])
        self._db_status.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_status)

        self._db_team = QComboBox()
        self._db_team.addItem(self._ALL_TEAMS)
        self._db_team.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_team)

        self._db_age = QComboBox()
        self._db_age.addItems(
            ["Any age", "U18", "18-22", "23-29", "30+"])
        self._db_age.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_age)

        self._db_ovr = QComboBox()
        self._db_ovr.addItems(
            ["Any OVR", "90+", "85+", "80+", "70+"])
        self._db_ovr.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_ovr)

        # Scouting profile filter (mainline parity)
        self._db_profile = QComboBox()
        self._db_profile.setToolTip(
            "Filter by scouting profile (attribute minimums)")
        self._db_profile.currentIndexChanged.connect(self._on_db_profile)
        filter_row.addWidget(self._db_profile)

        manage_btn = QPushButton("Manage Profiles…")
        manage_btn.setToolTip(
            "Browse, create, edit and delete scouting profiles")
        manage_btn.clicked.connect(self._manage_profiles)
        filter_row.addWidget(manage_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Reset all database filters")
        clear_btn.clicked.connect(self._clear_db_filters)
        filter_row.addWidget(clear_btn)
        layout.addLayout(filter_row)

    def _build_db_results(self, layout):
        self._db_table = PlayerTable()
        self._db_table.set_main_window(self.main_window)
        self._db_table.player_clicked.connect(self._open_prospect)
        layout.addWidget(self._db_table, 1)

    def _build_db_pagination(self, layout):
        page_row = QHBoxLayout()
        self._db_prev = QPushButton("← Prev")
        self._db_prev.clicked.connect(self._db_prev_page)
        page_row.addWidget(self._db_prev)
        self._db_page_label = QLabel("Page 1")
        self._db_page_label.setAlignment(Qt.AlignCenter)
        page_row.addWidget(self._db_page_label, 1)
        self._db_next = QPushButton("Next →")
        self._db_next.clicked.connect(self._db_next_page)
        page_row.addWidget(self._db_next)
        layout.addLayout(page_row)

        self._db_count = QLabel("")
        self._db_count.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._db_count)

    # --- Assignments ---
    def _new_assignment(self):
        dlg = AssignDialog(self.game, self)
        if dlg.exec() == QDialog.Accepted:
            prospect, scout = dlg.get_selection()
            if prospect is None or scout is None:
                QMessageBox.warning(
                    self, "Assignment", "Select a prospect and a scout.")
                return
            try:
                # Direct game call (web: POST /api/scouting/assignment)
                assignments = getattr(self.game, "scouting_assignments", None)
                if assignments is not None:
                    assignments[prospect] = scout
                else:
                    # Fallback: try the module function
                    try:
                        import scouting as _sm
                        if hasattr(_sm, "apply_player_assignment"):
                            _sm.apply_player_assignment(
                                self.game,
                                getattr(prospect, "id", None),
                                getattr(scout, "id", None))
                    except Exception:
                        pass
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Assignment", f"Failed: {e}")

    def _new_beat(self):
        dlg = BeatDialog(self.game, self)
        if dlg.exec() == QDialog.Accepted:
            scout, region = dlg.get_selection()
            if scout is None:
                QMessageBox.warning(self, "Beat", "Select a scout.")
                return
            try:
                # Direct game call (web: POST /api/scouting/assign)
                try:
                    import scouting as _sm
                    if hasattr(_sm, "apply_region_assignment"):
                        _sm.apply_region_assignment(
                            self.game,
                            getattr(scout, "id", None), region)
                except Exception:
                    pass
                # Also set on the scout object directly as fallback
                try:
                    setattr(scout, "region", region)
                    setattr(scout, "beat", region)
                except Exception:
                    pass
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Beat", f"Failed: {e}")

    # --- Database ---
    def _on_db_filter(self, *args):
        """Read every filter widget into state, then refresh the list.

        Accepts (and ignores) signal args so it can be connected directly
        to currentIndexChanged/textChanged.
        """
        self._db_filter_q = self._db_search.text().strip().lower()
        self._db_filter_pos = self._db_pos.currentIndex()
        self._db_filter_status = self._db_status.currentIndex()
        self._db_filter_team = self._db_team.currentText()
        self._db_filter_age = self._db_age.currentIndex()
        self._db_filter_ovr = self._db_ovr.currentIndex()
        self._db_page = 0
        self._refresh_db()

    def _refresh_profile_combo(self):
        """Populate the profile filter combo (preserves selection)."""
        if not _PROFILES_AVAILABLE:
            return
        prev = self._db_profile.currentData()
        prev_name = prev.name if prev else None
        self._db_profile.blockSignals(True)
        try:
            self._db_profile.clear()
            self._db_profile.addItem("No profile filter", None)
            for p in list_profiles():
                tag = "★ " if p.builtin else "✎ "
                self._db_profile.addItem(tag + p.name, p)
            if prev_name:
                for i in range(self._db_profile.count()):
                    p = self._db_profile.itemData(i)
                    if p is not None and p.name == prev_name:
                        self._db_profile.setCurrentIndex(i)
                        break
        finally:
            self._db_profile.blockSignals(False)
        self._db_filter_profile = self._db_profile.currentData()

    def _on_db_profile(self, index):
        """Profile filter changed — re-filter the database."""
        self._db_filter_profile = self._db_profile.itemData(index)
        self._db_page = 0
        self._refresh_db()

    def _manage_profiles(self):
        """Open the profile manager dialog; refresh combo on close."""
        if not _PROFILES_AVAILABLE:
            QMessageBox.information(
                self, "Scouting Profiles",
                "Scouting profiles are not available.")
            return
        dlg = ProfileManagerDialog(self.game, self)
        dlg.exec()
        # Profiles may have been created/edited/deleted — refresh.
        self._refresh_profile_combo()
        self._db_page = 0
        self._refresh_db()

    def _refresh_db_teams(self):
        """Populate the team filter from every league team (keeps selection)."""
        gm = _resolve_gm(self.game)
        league = safe_call(lambda: gm.league, context="scouting/load_league")
        names = sorted({
            getattr(t, "team_name", "") for t in
            safe_call(lambda: list(getattr(league, "teams", None) or []), [],
                      context="scouting/load_teams")
            if getattr(t, "team_name", "")})
        prev = self._db_team.currentText()
        self._db_team.blockSignals(True)
        try:
            self._db_team.clear()
            self._db_team.addItem(self._ALL_TEAMS)
            for name in names:
                self._db_team.addItem(name)
            idx = self._db_team.findText(prev) if prev else -1
            self._db_team.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._db_team.blockSignals(False)
        # Keep the cached filter in sync with what the combo actually shows:
        # if the previously selected team vanished (e.g. league rebuild),
        # findText returned -1 and the combo reset to ALL_TEAMS — the stale
        # cached text would otherwise filter to 0 players.
        self._db_filter_team = self._db_team.currentText()

    def _db_prev_page(self):
        if self._db_page > 0:
            self._db_page -= 1
            self._refresh_db()

    def _db_next_page(self):
        self._db_page += 1
        self._refresh_db()

    def _db_pool(self):
        """Every scoutable player as (player, status, team_name).

        Covers draft prospects (+ rights re-entries), every league team's
        NHL roster / AHL roster / prospects (trade-target scouting), and
        the free-agent pool. Deduped by player id.
        status is one of "draft", "nhl", "ahl", "prospects", "free";
        team_name is None for prospects and free agents.
        """
        gm = _resolve_gm(self.game)
        league = safe_call(lambda: gm.league)
        out = []
        seen = set()

        def _add(p, status, team_name):
            pid = getattr(p, "id", None)
            key = pid if pid is not None else id(p)
            if key in seen:
                return
            seen.add(key)
            out.append((p, status, team_name))

        for attr in ("draft_prospects", "draft_reentries"):
            for p in safe_call(
                    lambda: list(getattr(league, attr, None) or []), []):
                _add(p, "draft", None)
        for t in safe_call(
                lambda: list(getattr(league, "teams", None) or []), []):
            tname = getattr(t, "team_name", "") or ""
            # NHL roster
            for p in safe_call(
                    lambda: list(getattr(t, "roster", None) or []), []):
                _add(p, "nhl", tname)
            # AHL roster
            for p in safe_call(
                    lambda: list(getattr(t, "ahl_roster", None) or []), []):
                _add(p, "ahl", tname)
            # Prospects
            for p in safe_call(
                    lambda: list(getattr(t, "prospects", None) or []), []):
                _add(p, "prospects", tname)
        for p in safe_call(
                lambda: list(getattr(league, "free_agents", None) or []), []):
            _add(p, "free", None)
        return out

    # Combo-index -> (lo, hi) bands; unknown index = no band applied.
    # Matches web UI: U18, 18-22, 23-29, 30+.
    _DB_AGE_BANDS = {1: (0, 17), 2: (18, 22), 3: (23, 29), 4: (30, 200)}
    # Matches web UI: 90+, 85+, 80+, 70+ (cumulative thresholds).
    _DB_OVR_BANDS = {1: (90, 100), 2: (85, 100), 3: (80, 100), 4: (70, 100)}

    def _clear_db_filters(self):
        """Reset all database filters to defaults (web parity)."""
        self._db_search.blockSignals(True)
        self._db_pos.blockSignals(True)
        self._db_status.blockSignals(True)
        self._db_team.blockSignals(True)
        self._db_age.blockSignals(True)
        self._db_ovr.blockSignals(True)
        try:
            self._db_search.clear()
            self._db_pos.setCurrentIndex(0)
            self._db_status.setCurrentIndex(0)
            self._db_team.setCurrentIndex(0)
            self._db_age.setCurrentIndex(0)
            self._db_ovr.setCurrentIndex(0)
            self._db_profile.setCurrentIndex(0)
        finally:
            self._db_search.blockSignals(False)
            self._db_pos.blockSignals(False)
            self._db_status.blockSignals(False)
            self._db_team.blockSignals(False)
            self._db_age.blockSignals(False)
            self._db_ovr.blockSignals(False)
        self._on_db_filter()

    def _db_filtered(self):
        q = self._db_filter_q
        pos_idx = self._db_filter_pos
        status_idx = self._db_filter_status
        team = self._db_filter_team
        age_band = self._DB_AGE_BANDS.get(self._db_filter_age)
        ovr_band = self._DB_OVR_BANDS.get(self._db_filter_ovr)
        profile = self._db_filter_profile
        out = []
        for p, status, tname in self._db_pool():
            if q and q not in getattr(p, "full_name", "").lower():
                continue
            ps = _pos_str(p).upper()
            if pos_idx == 1 and not any(
                    x in ps for x in ("C", "LW", "RW", "W")):
                continue
            if pos_idx == 2 and "D" not in ps:
                continue
            if pos_idx == 3 and "G" not in ps:
                continue
            if status_idx == 1 and status != "nhl":
                continue
            if status_idx == 2 and status != "ahl":
                continue
            if status_idx == 3 and status != "prospects":
                continue
            if status_idx == 4 and status != "free":
                continue
            if status_idx == 5 and status != "draft":
                continue
            # Team filter: the "no filter" sentinel is item 0 of the combo,
            # whatever its display text is. Comparing the selected text
            # against the combo by index can't drift from the widgets.
            if (team and self._db_team.findText(team) != 0
                    and tname != team):
                continue
            if age_band is not None:
                age = getattr(p, "age", None)
                if age is None or not (age_band[0] <= age <= age_band[1]):
                    continue
            if ovr_band is not None:
                ovr = _overall(p)
                if not (ovr_band[0] <= ovr <= ovr_band[1]):
                    continue
            out.append(p)
        # Scouting profile filter (mainline parity): keep only players
        # meeting every attribute minimum, sorted by match score.
        if profile is not None and _PROFILES_AVAILABLE:
            user_team = _user_team(self.game)
            try:
                scored = filter_by_profile(
                    out, profile,
                    lambda p: _profile_is_scouted(p, user_team))
                out = [p for p, _score in scored]
            except Exception:
                pass
        return out

    def _refresh_db(self):
        filtered = self._db_filtered()
        total = len(filtered)
        start = self._db_page * self.DB_PAGE_SIZE
        page = filtered[start:start + self.DB_PAGE_SIZE]
        self._db_table.set_players(page)

        n_pages = max(1, (total + self.DB_PAGE_SIZE - 1) // self.DB_PAGE_SIZE)
        self._db_page = min(self._db_page, n_pages - 1)
        self._db_page_label.setText(f"Page {self._db_page + 1} of {n_pages}")
        self._db_count.setText(f"{total} players")
        self._db_prev.setEnabled(self._db_page > 0)
        self._db_next.setEnabled(self._db_page < n_pages - 1)

    def _open_prospect(self, player):
        # Navigate to player profile if available
        try:
            self.main_window.show_player(player)
        except Exception:
            pass

    # --- Refresh ---
    def refresh(self):
        gm = _resolve_gm(self.game)
        team = _user_team(self.game)

        # Assignments
        self._assign_list.clear()
        assignments = safe_call(
            lambda: list((getattr(self.game, "scouting_assignments", None) or {}).items()), [],
            context="scouting/load_assignments")
        for player, scout in assignments:
            pname = getattr(player, "full_name", "?")
            sname = getattr(scout, "full_name", getattr(scout, "name", "?"))
            self._assign_list.addItem(f"{pname} → {sname}")
        if not assignments:
            self._assign_list.addItem("No active assignments")

        # Beats (from scouts with region set)
        self._beat_list.clear()
        staff = safe_call(lambda: list(getattr(team, "staff", None) or []), [],
                          context="scouting/load_staff")
        beats = 0
        for s in staff:
            region = getattr(s, "region", None) or getattr(s, "beat", None)
            if region:
                sname = getattr(s, "full_name", getattr(s, "name", "?"))
                self._beat_list.addItem(f"{sname}: {region}")
                beats += 1
        if not beats:
            self._beat_list.addItem("No regional beats assigned")

        # Reports
        self._report_list.clear()
        reports = safe_call(
            lambda: list((getattr(team, "scouting_reports", None) or {}).values()), [],
            context="scouting/load_reports")
        for r in reports[:50]:
            pname = getattr(getattr(r, "player", None), "full_name", "?")
            acc = getattr(r, "accuracy", "?")
            viewings = getattr(r, "viewings", 0)
            self._report_list.addItem(
                f"{pname} — accuracy {acc} ({viewings} viewings)")
        if not reports:
            self._report_list.addItem("No scouting reports yet")

        # Staff table
        scouts = []
        for s in staff:
            role = str(getattr(getattr(s, "role", None), "value",
                               getattr(s, "role", "") or ""))
            if "scout" in role.lower():
                scouts.append(s)
        self._staff_table.setRowCount(len(scouts))
        for i, s in enumerate(scouts):
            self._staff_table.setItem(
                i, 0, QTableWidgetItem(
                    getattr(s, "full_name", getattr(s, "name", "?"))))
            self._staff_table.setItem(
                i, 1, QTableWidgetItem(
                    str(getattr(getattr(s, "role", None), "value",
                                getattr(s, "role", "")))))
            self._staff_table.setItem(
                i, 2, QTableWidgetItem(str(getattr(s, "ability", "?"))))
            self._staff_table.setItem(
                i, 3, QTableWidgetItem(
                    str(getattr(s, "region", None) or getattr(s, "beat", None) or "—")))
            self._staff_table.setItem(
                i, 4, QTableWidgetItem(str(getattr(s, "age", "?"))))
            self._staff_table.setItem(
                i, 5, QTableWidgetItem(str(getattr(s, "experience", "?"))))

        # Database
        self._refresh_db_teams()
        self._refresh_profile_combo()
        self._refresh_db()
