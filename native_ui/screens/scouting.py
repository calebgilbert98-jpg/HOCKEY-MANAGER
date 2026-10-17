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
    QTableWidgetItem, QVBoxLayout, QWidget, QMenu, QTextEdit,
)
import importlib  # R18: deferred Tk-module imports use importlib.import_module
                  # (invisible to PyInstaller's static analysis).
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable
from native_ui.safe import safe_call

# Mainline logic ports (scouting_window_helpers.py, scouting.py, trade_market.py):
# cancel assignment, assignment ETA, 30-assignment cap, scout suggestions,
# advanced analysis. Imported lazily so the screen still loads if a mainline
# module is unavailable; the wrappers below fall back to identical semantics.
try:
    _scout_helpers = importlib.import_module("scouting_window_helpers")
    import scouting as _scout_logic
    import trade_market as _trade_market
    _MAINLINE_SCOUT_HELPERS = True
except Exception:
    _scout_helpers = None
    _scout_logic = None
    _trade_market = None
    _MAINLINE_SCOUT_HELPERS = False

#: Standing 30-assignment cap (mainline: scouting_window_helpers).
#: Communicated to the user in the assignments section header and in the
#: refusal message from _create_assignment -- never silently enforced.
if _MAINLINE_SCOUT_HELPERS:
    _MAX_ACTIVE_ASSIGNMENTS = int(
        getattr(_scout_helpers, "_MAX_ACTIVE_ASSIGNMENTS", 30) or 30)
else:
    _MAX_ACTIVE_ASSIGNMENTS = 30


def _create_assignment(game, player, scout):
    """Create a REAL scouting assignment. Mainline-faithful port of
    scouting_window_helpers.create_scout_assignment: refuses duplicates,
    enforces the 30-assignment cap with a message, and reports the ETA
    pace. Returns (ok: bool, message: str)."""
    if _MAINLINE_SCOUT_HELPERS:
        try:
            return _scout_helpers.create_scout_assignment(game, player, scout)
        except Exception as e:
            return False, f"Could not create the assignment: {e}"
    # Local fallback: identical semantics to the mainline helper.
    if player is None:
        return False, "No player selected."
    if scout is None:
        return False, "No scout selected."
    try:
        assigns = getattr(game, "scouting_assignments", None)
        if assigns is None:
            assigns = {}
            game.scouting_assignments = assigns
        if player in assigns:
            other = assigns[player]
            return False, (
                f"{getattr(player, 'full_name', 'That player')} is already "
                f"being scouted by {getattr(other, 'full_name', 'a scout')}.")
        if len(assigns) >= _MAX_ACTIVE_ASSIGNMENTS:
            return False, (
                f"You have {_MAX_ACTIVE_ASSIGNMENTS} active assignments "
                "already. Cancel one to free up a scout.")
        assigns[player] = scout
        days = _estimate_days(game, player, scout)
        pace = f" (~{days} days at this scout's pace)" if days else ""
        return True, (
            f"{getattr(scout, 'full_name', 'Scout')} will scout "
            f"{getattr(player, 'full_name', 'the player')}{pace}.\n"
            "The report builds up day by day in the Reports tab.")
    except Exception as e:
        return False, f"Could not create the assignment: {e}"


def _cancel_assignment(game, player):
    """Remove a REAL scouting assignment. Mainline-faithful port of
    scouting_window_helpers.cancel_scout_assignment: pops the player from
    the assignments dict, freeing the scout; filed reports are kept.
    Returns (ok: bool, message: str)."""
    if _MAINLINE_SCOUT_HELPERS:
        try:
            return _scout_helpers.cancel_scout_assignment(game, player)
        except Exception as e:
            return False, f"Could not cancel the assignment: {e}"
    # Local fallback: identical semantics to the mainline helper.
    if player is None:
        return False, "No assignment selected."
    try:
        assigns = getattr(game, "scouting_assignments", None) or {}
        if player not in assigns:
            return False, "That assignment is no longer active."
        scout = assigns.pop(player)
        return True, (
            f"Assignment cancelled: {getattr(scout, 'full_name', 'Scout')} "
            f"is no longer scouting {getattr(player, 'full_name', 'the player')}.")
    except Exception as e:
        return False, f"Could not cancel the assignment: {e}"


def _estimate_days(game, player, scout):
    """Real estimated days until the report reaches 'A' accuracy.

    Mainline-faithful port of scouting_window_helpers.estimate_completion_days
    (0 = complete, None = cannot estimate). Never raises."""
    if _MAINLINE_SCOUT_HELPERS:
        try:
            return _scout_helpers.estimate_completion_days(
                game, player, scout)
        except Exception:
            return None
    return None

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
    return (safe_call(lambda: getattr(game, "game_manager", None),
                      context="scouting/resolve_gm") or game)


def _user_team(game):
    gm = _resolve_gm(game)
    return (safe_call(lambda: gm.user_team,
                      context="scouting/user_team")
            or safe_call(lambda: getattr(game, "user_team", None),
                         context="scouting/user_team"))


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

        # ETA pace preview (mainline parity): the scout's estimated
        # completion for the currently selected prospect + scout.
        self._pace_label = QLabel("")
        self._pace_label.setStyleSheet("color: #6b7488; font-size: 11px;")
        self._pace_label.setWordWrap(True)
        layout.addRow("", self._pace_label)
        self._prospect_combo.currentIndexChanged.connect(self._update_pace)
        self._scout_combo.currentIndexChanged.connect(self._update_pace)
        self._update_pace()

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

    def _update_pace(self, *args):
        """ETA preview for the selected prospect + scout.

        Mainline parity with scouting_window_helpers._update_pace: shows
        the estimated days until the report reaches 'A' accuracy.
        """
        prospect = self._prospect_combo.currentData()
        scout = self._scout_combo.currentData()
        if prospect is None or scout is None:
            self._pace_label.setText("")
            return
        days = safe_call(
            lambda: _estimate_days(self.game, prospect, scout), None,
            context="scouting/estimate_pace")
        sname = getattr(scout, "full_name", getattr(scout, "name", "this scout"))
        if days == 0:
            self._pace_label.setText(
                "This player already has a complete report.")
        elif days is None:
            self._pace_label.setText("Estimated completion: unknown.")
        else:
            self._pace_label.setText(
                f"Estimated completion: ~{days} days at {sname}'s pace "
                "(report reaches 'A' accuracy, then the assignment closes).")


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
        staff = safe_call(lambda: list(getattr(team, "staff", None) or []), [],
                          context="scouting/load_staff")
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


class AdvancedAnalysisDialog(QDialog):
    """Fog-of-war-safe advanced analysis for one player.

    Qt port of ProfessionalScoutingView._advanced_analysis: everything
    shown is scout-filtered -- the filed report's graded potential range,
    its accuracy-graded attribute bands, strengths/weaknesses the scout
    actually listed, comparables and projection. With no report, only the
    public consensus range is shown. Never raw attributes.
    """

    def __init__(self, game, player, report=None, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle(
            f"Advanced Analysis — {getattr(player, 'full_name', '?')}")
        self.setMinimumSize(560, 560)

        layout = QVBoxLayout(self)
        header = QLabel(
            f"{getattr(player, 'full_name', '?')}  ·  {_pos_str(player)}  ·  "
            f"Age {getattr(player, 'age', '?')}")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.setWordWrap(True)
        layout.addWidget(header)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(self._analysis_text(player, report))
        layout.addWidget(body, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _report_lines(self, player, report):
        """Fog-of-war-safe (label, text) rows + graded potential."""
        if _scout_helpers is not None:
            try:
                return _scout_helpers.report_display_lines(player, report)
            except Exception:
                pass
        return [], "?"

    def _analysis_text(self, player, report):
        lines = []

        def hdr(text):
            lines.append(text)
            lines.append("=" * len(text))

        if report is not None:
            rows, pot = self._report_lines(player, report)
            hdr("SCOUT-FILTERED BREAKDOWN")
            lines.append(f"Graded potential: {pot}")
            lines.append(
                f"Report accuracy: {getattr(report, 'accuracy', '?')} "
                f"({getattr(report, 'viewings', 0)} viewings)")
            try:
                lines.append(
                    f"Reliability: {getattr(report, 'reliability', 0.0):.0%}")
            except Exception:
                pass
            lines.append("")

            # Accuracy-graded attribute bands the scout actually filed
            scouted = getattr(report, "scouted_attributes", None) or {}
            if scouted:
                hdr("ATTRIBUTE BANDS (as graded by the scout)")
                for attr in sorted(scouted):
                    label = attr.replace("_", " ").title()
                    lines.append(f"• {label}: {scouted[attr]}")
                lines.append("")

            for label, text in rows:
                if label in ("Accuracy", "Viewings"):
                    continue  # already shown above
                hdr(label.upper())
                lines.append(text)
                lines.append("")

            lines.append(
                "These are the scout's graded reads, not measurements. "
                "Higher accuracy narrows the bands.")
        else:
            crange = "?"
            if _scout_logic is not None:
                try:
                    crange = _scout_logic.consensus_range(player)
                except Exception:
                    pass
            hdr("PUBLIC CONSENSUS (UN SCOUTED)")
            lines.append(f"Potential range: {crange}")
            lines.append("")
            lines.append(
                "No filed report exists for this player, so there is no "
                "advanced breakdown to show -- anything more would be "
                "guessing.")
            lines.append("")
            lines.append(
                "Assign a scout to build a real evaluation; the breakdown "
                "above fills in as viewings accumulate and accuracy rises.")
        return "\n".join(lines)


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
        self._build_suggestions_section(work_layout)
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
        cancel_btn = QPushButton("Cancel Selected")
        cancel_btn.setToolTip(
            "Cancel the selected assignment (right-click also works). "
            "The scout is freed up; any report filed so far is kept.")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self._cancel_selected_assignment)
        assign_btn_row.addWidget(cancel_btn)
        # The 30-assignment cap is communicated up front (D-13), never
        # silently enforced.
        self._cap_label = QLabel("")
        self._cap_label.setStyleSheet("color: #8b95ab; font-size: 11px;")
        assign_btn_row.addWidget(self._cap_label)
        assign_btn_row.addStretch()
        assign_layout.addLayout(assign_btn_row)
        self._assign_list = QListWidget()
        # Right-click a live assignment to cancel it (mainline parity with
        # ProfessionalScoutingView._on_assignment_right_click).
        self._assign_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._assign_list.customContextMenuRequested.connect(
            self._on_assign_context_menu)
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

    def _build_suggestions_section(self, layout):
        """Scout suggestions (D-13, mainline parity).

        Qt port of ModernScoutingWindow's Targets tab: the unified
        trade-target surface (trade_market.get_unified_targets) plus the
        "Refresh suggestions" button that asks the user's scouts for new
        value tips (trade_market.refresh_scout_suggestions).
        """
        sugg_box = QGroupBox("Scout Suggestions")
        sugg_layout = QVBoxLayout(sugg_box)
        sugg_note = QLabel(
            "Trade-target tips from your scouts. Hit Refresh Suggestions "
            "to ask them for new value tips.")
        sugg_note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        sugg_note.setWordWrap(True)
        sugg_layout.addWidget(sugg_note)
        sugg_btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Suggestions")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_suggestions)
        sugg_btn_row.addWidget(refresh_btn)
        sugg_btn_row.addStretch()
        sugg_layout.addLayout(sugg_btn_row)
        self._suggest_list = QListWidget()
        sugg_layout.addWidget(self._suggest_list)
        layout.addWidget(sugg_box)

    def _refresh_suggestions(self):
        """Ask the user's scouts for new value tips (mainline parity with
        ModernScoutingWindow._targets_refresh_suggestions)."""
        gm = _resolve_gm(self.game)
        league = safe_call(lambda: gm.league, None,
                           context="scouting/load_league")
        if league is None:
            QMessageBox.warning(self, "No Data", "No league data available.")
            return
        if _trade_market is None:
            QMessageBox.warning(
                self, "Scout Suggestions",
                "Suggestion helpers are unavailable.")
            return
        n = safe_call(
            lambda: _trade_market.refresh_scout_suggestions(gm, league), 0,
            context="scouting/refresh_suggestions")
        self._populate_suggestions()
        if n:
            QMessageBox.information(
                self, "Scout Suggestions",
                f"{n} new suggestion(s) from your scouts.")
        else:
            QMessageBox.information(
                self, "Scout Suggestions",
                "No new suggestions (your scouts found no new "
                "value, or you have no scouts on staff).")

    def _populate_suggestions(self):
        """Fill the suggestions list from the unified targets surface."""
        self._suggest_list.clear()
        gm = _resolve_gm(self.game)
        league = safe_call(lambda: gm.league, None,
                           context="scouting/load_league")
        entries = []
        if league is not None and _trade_market is not None:
            entries = safe_call(
                lambda: _trade_market.get_unified_targets(league), [],
                context="scouting/load_suggestions") or []
        for e in entries:
            try:
                name = e.get("player_name", "?")
                notes = e.get("notes", "") or ""
                self._suggest_list.addItem(
                    f"{name} — {notes}" if notes else name)
            except Exception:
                continue
        if not entries:
            self._suggest_list.addItem(
                "No suggestions yet — hit Refresh Suggestions.")

    def _build_reports_section(self, layout):
        report_box = QGroupBox("Scouting Reports")
        report_layout = QVBoxLayout(report_box)
        analysis_btn = QPushButton("Advanced Analysis…")
        analysis_btn.setToolTip(
            "Fog-of-war-safe breakdown of the selected report "
            "(or public consensus for an unscouted player).")
        analysis_btn.setCursor(Qt.PointingHandCursor)
        analysis_btn.clicked.connect(self._analyze_selected_report)
        report_layout.addWidget(analysis_btn)
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

        analyze_btn = QPushButton("Advanced Analysis…")
        analyze_btn.setToolTip(
            "Fog-of-war-safe breakdown of the selected player "
            "(filed report if scouted, public consensus otherwise)")
        analyze_btn.clicked.connect(self._analyze_selected_db_player)
        filter_row.addWidget(analyze_btn)
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
            # Mainline-faithful create (D-13): the cap, duplicate refusal,
            # and ETA pace are all communicated through the returned message.
            ok, msg = _create_assignment(self.game, prospect, scout)
            if ok:
                QMessageBox.information(self, "Scouting Assignment", msg)
            else:
                QMessageBox.warning(self, "Scouting Assignment", msg)
            self.refresh()

    def _on_assign_context_menu(self, pos):
        """Right-click menu on a live assignment: cancel it.

        Qt port of ProfessionalScoutingView._on_assignment_right_click.
        """
        item = self._assign_list.itemAt(pos)
        if item is None:
            return
        self._assign_list.setCurrentItem(item)
        menu = QMenu(self)
        action = menu.addAction("Cancel Assignment")
        if menu.exec(self._assign_list.mapToGlobal(pos)) == action:
            self._cancel_selected_assignment()

    def _selected_assignment_player(self):
        """The player behind the currently selected assignment row."""
        item = self._assign_list.currentItem()
        if item is None:
            return None
        try:
            return item.data(Qt.UserRole)
        except Exception:
            return None

    def _cancel_selected_assignment(self):
        """Cancel the selected REAL scouting assignment.

        Mainline parity with ProfessionalScoutingView._cancel_assignment:
        confirm first ("The scout is freed up; any report filed so far is
        kept."), then pop the assignment so the scout is freed and the
        assignment state is clean.
        """
        player = self._selected_assignment_player()
        if player is None:
            QMessageBox.warning(
                self, "No Selection",
                "Select an assignment to cancel.")
            return
        pname = getattr(player, "full_name", "this player")
        reply = QMessageBox.question(
            self, "Cancel Assignment",
            f"Stop scouting {pname}?\n\n"
            "The scout is freed up; any report filed so far is kept.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        ok, msg = _cancel_assignment(self.game, player)
        if ok:
            QMessageBox.information(self, "Assignment Cancelled", msg)
        else:
            QMessageBox.warning(self, "Scouting", msg)
        self.refresh()

    # --- Advanced analysis ---
    def _selected_report(self):
        """The (player, report) behind the selected report row."""
        item = self._report_list.currentItem()
        if item is None:
            return None, None
        try:
            data = item.data(Qt.UserRole)
            if isinstance(data, tuple) and len(data) == 2:
                return data
        except Exception:
            pass
        return None, None

    def _analyze_selected_report(self):
        """Advanced analysis for the selected report row (mainline parity:
        the analysis dialog is available from the reports list)."""
        player, report = self._selected_report()
        if report is None:
            QMessageBox.warning(
                self, "No Selection",
                "Select a scouting report to analyze.")
            return
        if player is None:
            player = getattr(report, "player", None)
        if player is None:
            QMessageBox.warning(
                self, "Analysis", "Could not resolve the player.")
            return
        AdvancedAnalysisDialog(self.game, player, report, self).exec()

    def _analyze_selected_db_player(self):
        """Advanced analysis for the selected database row (mainline parity:
        the analysis is available from the player list -- filed report if
        scouted, public consensus range otherwise)."""
        row = self._db_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "No Selection",
                "Select a player in the database to analyze.")
            return
        item = self._db_table.item(row, 0)
        player = item.data(Qt.UserRole + 1) if item is not None else None
        if player is None:
            QMessageBox.warning(
                self, "Analysis", "Could not resolve the player.")
            return
        team = _user_team(self.game)
        report = safe_call(
            lambda: (getattr(team, "scouting_reports", None) or {}).get(
                getattr(player, "id", None)),
            None, context="scouting/load_report_for_analysis")
        AdvancedAnalysisDialog(self.game, player, report, self).exec()

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
        league = safe_call(lambda: gm.league,
                           context="scouting/load_league")
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
                    lambda: list(getattr(league, attr, None) or []), [],
                    context="scouting/load_draft_pool"):
                _add(p, "draft", None)
        for t in safe_call(
                lambda: list(getattr(league, "teams", None) or []), [],
                context="scouting/load_teams"):
            tname = getattr(t, "team_name", "") or ""
            # NHL roster
            for p in safe_call(
                    lambda: list(getattr(t, "roster", None) or []), [],
                    context="scouting/load_roster"):
                _add(p, "nhl", tname)
            # AHL roster
            for p in safe_call(
                    lambda: list(getattr(t, "ahl_roster", None) or []), [],
                    context="scouting/load_ahl_roster"):
                _add(p, "ahl", tname)
            # Prospects
            for p in safe_call(
                    lambda: list(getattr(t, "prospects", None) or []), [],
                    context="scouting/load_prospects"):
                _add(p, "prospects", tname)
        for p in safe_call(
                lambda: list(getattr(league, "free_agents", None) or []), [],
                context="scouting/load_free_agents"):
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
        team = _user_team(self.game)
        staff = safe_call(lambda: list(getattr(team, "staff", None) or []), [],
                          context="scouting/load_staff")
        # Player id -> player map for report/assignment rows that need the
        # player object (advanced analysis, cancel).
        by_id = {str(getattr(p, "id", "") or ""): p
                 for p, _s, _t in self._db_pool()}
        self._refresh_assignments(team)
        self._refresh_beats(staff)
        self._refresh_reports(team, by_id)
        self._populate_suggestions()
        self._refresh_staff_table(staff)

        # Database
        self._refresh_db_teams()
        self._refresh_profile_combo()
        self._refresh_db()

    def _refresh_assignments(self, team):
        """Active assignments with live ETA (D-13).

        Each row shows scout, target, ETA (mainline: "complete" / "~Nd" /
        "—"), and status (viewings · accuracy). The player object rides on
        the item so cancel works by selection.
        """
        self._assign_list.clear()
        assignments = safe_call(
            lambda: list((getattr(self.game, "scouting_assignments", None) or {}).items()), [],
            context="scouting/load_assignments")
        reports = safe_call(
            lambda: dict(getattr(team, "scouting_reports", None) or {}), {},
            context="scouting/load_reports")
        for player, scout in assignments:
            pname = getattr(player, "full_name", "?")
            sname = getattr(scout, "full_name", getattr(scout, "name", "?"))
            report = reports.get(getattr(player, "id", None))
            views = getattr(report, "viewings", 0) if report else 0
            acc = getattr(report, "accuracy", "—") if report else "—"
            days = safe_call(
                lambda: _estimate_days(self.game, player, scout), None,
                context="scouting/estimate_eta")
            eta = "complete" if days == 0 else (f"~{days}d" if days else "—")
            item = QListWidgetItem(
                f"{sname} → {pname} · ETA {eta} · "
                f"{views} viewings · accuracy {acc}")
            item.setData(Qt.UserRole, player)
            self._assign_list.addItem(item)
        if not assignments:
            self._assign_list.addItem("No active assignments")
        # Communicate the 30-assignment cap up front (D-13).
        n = len(assignments)
        self._cap_label.setText(
            f"Active assignments: {n} / {_MAX_ACTIVE_ASSIGNMENTS}")

    def _refresh_beats(self, staff):
        """Regional beats (from scouts with a region set)."""
        self._beat_list.clear()
        beats = 0
        for s in staff:
            region = getattr(s, "region", None) or getattr(s, "beat", None)
            if region:
                sname = getattr(s, "full_name", getattr(s, "name", "?"))
                self._beat_list.addItem(f"{sname}: {region}")
                beats += 1
        if not beats:
            self._beat_list.addItem("No regional beats assigned")

    def _refresh_reports(self, team, by_id):
        """Scouting reports; each row carries (player, report) for the
        advanced-analysis dialog."""
        self._report_list.clear()
        reports = safe_call(
            lambda: list((getattr(team, "scouting_reports", None) or {}).items()), [],
            context="scouting/load_reports")
        for pid, r in reports[:50]:
            player = by_id.get(str(pid))
            if player is None:
                player = getattr(r, "player", None)
            pname = getattr(player, "full_name", None) or f"Player {pid}"
            acc = getattr(r, "accuracy", "?")
            viewings = getattr(r, "viewings", 0)
            item = QListWidgetItem(
                f"{pname} — accuracy {acc} ({viewings} viewings)")
            item.setData(Qt.UserRole, (player, r))
            self._report_list.addItem(item)
        if not reports:
            self._report_list.addItem("No scouting reports yet")

    def _refresh_staff_table(self, staff):
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
