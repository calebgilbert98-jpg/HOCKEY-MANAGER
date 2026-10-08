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

        self._prospect_combo = QComboBox()
        self._scout_combo = QComboBox()
        self._load_options()

        layout.addRow("Prospect:", self._prospect_combo)
        layout.addRow("Scout:", self._scout_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_options(self):
        gm = _resolve_gm(self.game)
        league = _safe(lambda: gm.league)
        team = _user_team(self.game)

        prospects = _safe(lambda: list(getattr(league, "draft_prospects", None) or []), [])
        for p in prospects[:200]:
            name = getattr(p, "full_name", "?")
            self._prospect_combo.addItem(
                f"{name} ({_pos_str(p)}, {_overall(p)} OVR)", p)

        staff = _safe(lambda: list(getattr(team, "staff", None) or []), [])
        for s in staff:
            role = str(getattr(getattr(s, "role", None), "value",
                               getattr(s, "role", "") or ""))
            if "scout" in role.lower():
                self._prospect_combo.addItem(
                    getattr(s, "full_name", getattr(s, "name", "?")), s)

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
        staff = _safe(lambda: list(getattr(team, "staff", None) or []), [])
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

    def get_selection(self):
        return (self._scout_combo.currentData(),
                self._region_combo.currentText())


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

        # --- Tab 1: Assignments & Reports ---
        work = QWidget()
        work_layout = QVBoxLayout(work)
        work_layout.setSpacing(12)

        # Active assignments section
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
        work_layout.addWidget(assign_box)

        # Regional beats section
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
        work_layout.addWidget(beat_box)

        # Reports section
        report_box = QGroupBox("Scouting Reports")
        report_layout = QVBoxLayout(report_box)
        self._report_list = QListWidget()
        report_layout.addWidget(self._report_list)
        work_layout.addWidget(report_box)

        self.tabs.addTab(work, "Assignments & Reports")

        # --- Tab 2: Scouting Staff ---
        staff_page = QWidget()
        staff_layout = QVBoxLayout(staff_page)
        self._staff_table = QTableWidget()
        self._staff_table.setColumnCount(6)
        self._staff_table.setHorizontalHeaderLabels(
            ["Scout", "Role", "Ability", "Beat", "Age", "Exp"])
        self._staff_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._staff_table.setSelectionBehavior(QTableWidget.SelectRows)
        staff_layout.addWidget(self._staff_table)
        self.tabs.addTab(staff_page, "Scouting Staff")

        # --- Tab 3: Player Database ---
        db_page = QWidget()
        db_layout = QVBoxLayout(db_page)

        # Filters
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
        self._db_status.addItems(["All", "Draft eligible", "Signed", "Free agent"])
        self._db_status.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_status)

        self._db_team = QComboBox()
        self._db_team.addItem(self._ALL_TEAMS)
        self._db_team.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_team)

        self._db_age = QComboBox()
        self._db_age.addItems(
            ["All ages", "Under 21", "21-24", "25-29", "30+"])
        self._db_age.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_age)

        self._db_ovr = QComboBox()
        self._db_ovr.addItems(
            ["All ratings", "85+", "80-84", "75-79", "70-74", "Under 70"])
        self._db_ovr.currentIndexChanged.connect(self._on_db_filter)
        filter_row.addWidget(self._db_ovr)
        db_layout.addLayout(filter_row)

        # Results table
        self._db_table = PlayerTable()
        self._db_table.set_main_window(self.main_window)
        self._db_table.player_clicked.connect(self._open_prospect)
        db_layout.addWidget(self._db_table, 1)

        # Pagination
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
        db_layout.addLayout(page_row)

        self._db_count = QLabel("")
        self._db_count.setStyleSheet("color: #8b95ab; font-size: 12px;")
        db_layout.addWidget(self._db_count)

        self.tabs.addTab(db_page, "Player Database")

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

    def _refresh_db_teams(self):
        """Populate the team filter from every league team (keeps selection)."""
        gm = _resolve_gm(self.game)
        league = _safe(lambda: gm.league)
        names = sorted({
            getattr(t, "team_name", "") for t in
            _safe(lambda: list(getattr(league, "teams", None) or []), [])
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
        status is one of "draft", "signed", "free"; team_name is None for
        prospects and free agents.
        """
        gm = _resolve_gm(self.game)
        league = _safe(lambda: gm.league)
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
            for p in _safe(
                    lambda: list(getattr(league, attr, None) or []), []):
                _add(p, "draft", None)
        for t in _safe(
                lambda: list(getattr(league, "teams", None) or []), []):
            tname = getattr(t, "team_name", "") or ""
            for attr in ("roster", "ahl_roster", "prospects"):
                for p in _safe(
                        lambda: list(getattr(t, attr, None) or []), []):
                    _add(p, "signed", tname)
        for p in _safe(
                lambda: list(getattr(league, "free_agents", None) or []), []):
            _add(p, "free", None)
        return out

    # Combo-index -> (lo, hi) bands; unknown index = no band applied.
    _DB_AGE_BANDS = {1: (0, 20), 2: (21, 24), 3: (25, 29), 4: (30, 200)}
    _DB_OVR_BANDS = {1: (85, 100), 2: (80, 84), 3: (75, 79),
                     4: (70, 74), 5: (0, 69)}

    def _db_filtered(self):
        q = self._db_filter_q
        pos_idx = self._db_filter_pos
        status_idx = self._db_filter_status
        team = self._db_filter_team
        age_band = self._DB_AGE_BANDS.get(self._db_filter_age)
        ovr_band = self._DB_OVR_BANDS.get(self._db_filter_ovr)
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
            if status_idx == 1 and status != "draft":
                continue
            if status_idx == 2 and status != "signed":
                continue
            if status_idx == 3 and status != "free":
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
        assignments = _safe(
            lambda: list((getattr(self.game, "scouting_assignments", None) or {}).items()), [])
        for player, scout in assignments:
            pname = getattr(player, "full_name", "?")
            sname = getattr(scout, "full_name", getattr(scout, "name", "?"))
            self._assign_list.addItem(f"{pname} → {sname}")
        if not assignments:
            self._assign_list.addItem("No active assignments")

        # Beats (from scouts with region set)
        self._beat_list.clear()
        staff = _safe(lambda: list(getattr(team, "staff", None) or []), [])
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
        reports = _safe(
            lambda: list((getattr(team, "scouting_reports", None) or {}).values()), [])
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
        self._refresh_db()
