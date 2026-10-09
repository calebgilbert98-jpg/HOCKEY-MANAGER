"""Roster screen: 5 tabs (NHL / AHL / Prospects / Depth Chart / Salary Cap).

Native port of web_ui roster (templates/roster.html + screens/roster.py +
static/js/roster.js). Calls the game object directly -- no Flask/HTTP.
"""
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QLineEdit, QButtonGroup, QTableWidgetItem, QMenu, QMessageBox,
    QInputDialog, QFrame, QGridLayout, QScrollArea, QTableWidget,
    QProgressBar, QHeaderView, QSizePolicy,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable


# ---------------------------------------------------------------------------
# helpers (ported from web_ui roster.js / screens/roster.py)
# ---------------------------------------------------------------------------

_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}

_SLOT_RE = re.compile(r"^([A-Z]+?)(\d*)$")


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _clean_position(pos):
    try:
        s = str(pos or "")
        if "." in s:
            s = s.split(".")[-1]
        s = s.strip().upper()
        return _POSITION_ABBR.get(s, s or "?")
    except Exception:
        return "?"


def _pos_group(pos_abbr):
    """F / D / G grouping used by the Pos pill filter."""
    p = (pos_abbr or "").upper()
    if p == "G":
        return "G"
    if p in ("D", "LD", "RD"):
        return "D"
    return "F"


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,}"


def _player_ovr(p):
    try:
        fn = getattr(p, "overall_rating", None)
        if callable(fn):
            v = fn()
            if v:
                return int(v)
        v = getattr(p, "overall", None)
        if v:
            return int(v)
    except Exception:
        pass
    return 0


def _tier_label(ovr):
    try:
        o = int(ovr or 0)
    except Exception:
        return "?"
    if o >= 90:
        return "Elite"
    if o >= 85:
        return "Top"
    if o >= 80:
        return "1st"
    if o >= 75:
        return "2nd"
    if o >= 70:
        return "3rd"
    if o >= 65:
        return "4th"
    if o >= 60:
        return "Depth"
    return "Minors"


def _health_badges(p):
    badges = []
    try:
        import ir_system as _irs
        st = _irs.ir_status_of(p)
        if st and st != "None":
            badges.append(st)
    except Exception:
        pass
    if _safe(lambda: bool(getattr(p, "is_injured", False)), False):
        if "IR" not in badges and "LTIR" not in badges:
            badges.append("INJ")
    try:
        import roster_limits as _rl
        if _rl.is_emergency_filler(p):
            badges.append("EMERGENCY")
    except Exception:
        pass
    return badges


def _morale_label(v):
    if v >= 80:
        return "Elated"
    if v >= 60:
        return "Happy"
    if v >= 40:
        return "Content"
    if v >= 20:
        return "Unhappy"
    return "Angry"


def _player_salary(p):
    """Per-player cap hit: contract salary first (matches finances screen),
    then direct .salary. The direct Player.salary attr is legacy/unset."""
    c = _safe(lambda: getattr(p, "contract", None))
    if c is not None:
        hit = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0)
        if hit:
            return hit
    return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0) or 0


def _contract_years(p):
    c = _safe(lambda: getattr(p, "contract", None))
    if c is None:
        return 0
    return _safe(lambda: int(getattr(c, "years_remaining", 0) or 0), 0)


def _jersey_validation(team, player, number):
    """(ok, reason) -- desktop rulebook for a jersey number change.
    Never raises. Ported from web_ui/screens/roster.py."""
    try:
        n = int(number)
    except (TypeError, ValueError):
        return False, "Enter a number between 1 and 98."
    if not (1 <= n <= 98):
        return False, "Numbers run 1-98."
    try:
        import immortality as _im
        from game_classes import PlayerPosition as _PP
        goalie = getattr(player, "primary_position", None) == _PP.GOALIE
        if _im.is_number_retired(team, n) or n in _im.LEAGUE_RETIRED_NUMBERS:
            return False, (f"No. {n} is retired by "
                           f"{getattr(team, 'team_name', 'the club')} "
                           f"-- pick another.")
        if not goalie and n in _im.SKATER_BARRED_NUMBERS:
            return False, (f"No. {n} is reserved for goaltenders "
                           f"-- pick another.")
        taken = set()
        for attr in ("roster", "ahl_roster"):
            for q in (getattr(team, attr, None) or []):
                if q is player:
                    continue
                try:
                    taken.add(int(getattr(q, "jersey_number", 0) or 0))
                except Exception:
                    continue
        if n in taken:
            return False, (f"No. {n} is already worn on the NHL/AHL roster "
                           f"-- pick another.")
        return True, ""
    except Exception:
        return False, "Could not validate the number."


def _unit_label(slot_prefix, idx):
    n = idx if idx else 1
    if slot_prefix in ("LW", "C", "RW"):
        return ("forwards", f"Line {n}", n)
    if slot_prefix in ("LD", "RD"):
        return ("defense", f"Pairing {n}", n)
    if slot_prefix in ("G", "GK"):
        return ("goalies", "Goalies", 0)
    return ("other", "Other", 99)


def _group_lineup(lineup):
    """Group lineup dict into ordered units of slots (player objects)."""
    buckets = {}
    for slot, player in (_safe(lambda: list(lineup.items()), []) or []):
        try:
            slot = str(slot or "")
            m = _SLOT_RE.match(slot)
            prefix = m.group(1) if m else ""
            idx = int(m.group(2)) if m and m.group(2) else 1
            group, label, order = _unit_label(prefix, idx)
            buckets.setdefault((group, label, order),
                               []).append((idx, slot, player))
        except Exception:
            continue
    units = []
    group_rank = {"forwards": 0, "defense": 1, "goalies": 2, "other": 3}
    for (group, label, order), slots in sorted(
            buckets.items(),
            key=lambda kv: (group_rank.get(kv[0][0], 9), kv[0][2])):
        slots.sort(key=lambda s: (s[0], s[1]))
        units.append({
            "group": group,
            "label": label,
            "slots": [{"slot": s[1], "player": s[2]} for s in slots],
        })
    return units


# ---------------------------------------------------------------------------
# sortable item (numeric UserRole wins over display text)
# ---------------------------------------------------------------------------

class _SortItem(QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(Qt.UserRole)
        b = other.data(Qt.UserRole)
        if a is not None and b is not None:
            try:
                return float(a) < float(b)
            except (TypeError, ValueError):
                pass
        return super().__lt__(other)


class RosterTable(PlayerTable):
    """PlayerTable with the full web roster columns.

    Columns: # | PLAYER | POS | AGE | OVR | TIER | POT | CAP HIT | YRS |
    MOR | HEALTH. Double-click opens the profile; the # column click
    edits the jersey number; right-click shows the row context menu.
    """

    COLUMNS = [
        ("jersey", "#", 45),
        ("name", "PLAYER", 190),
        ("pos", "POS", 60),
        ("age", "AGE", 50),
        ("ovr", "OVR", 55),
        ("tier", "TIER", 65),
        ("pot", "POT", 55),
        ("salary", "CAP HIT", 100),
        ("yrs", "YRS", 50),
        ("morale", "MOR", 60),
        ("health", "HEALTH", 130),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def _set_row(self, row, p):
        c = _safe(lambda: getattr(p, "contract", None))
        ovr = _player_ovr(p)
        sal = _player_salary(p)
        # Morale is 1-100 on the Player (the old x10 display mapping was a bug
        # and was removed; the hub already shows the raw 1-100 value).
        morale100 = _safe(lambda: int(getattr(p, "morale", 0) or 0), 0)
        vals = {
            "jersey": str(_safe(lambda: getattr(p, "jersey_number", ""), "")),
            "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
            "pos": _clean_position(_safe(lambda: getattr(
                p, "primary_position", ""), "")),
            "age": str(_safe(lambda: getattr(p, "age", "?"), "?")),
            "ovr": str(ovr),
            "tier": _tier_label(ovr),
            "pot": str(_safe(lambda: getattr(p, "potential", "?"), "?")),
            "salary": _fmt_money(sal),
            "yrs": str(_contract_years(p)) if c is not None else "--",
            "morale": str(morale100),
            "health": ", ".join(_health_badges(p)) or "Healthy",
        }
        numeric = {
            "jersey": _safe(lambda: int(getattr(p, "jersey_number", 0) or 0), 0),
            "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
            "ovr": ovr,
            "pot": _safe(lambda: int(getattr(p, "potential", 0) or 0), 0),
            "salary": sal,
            "yrs": _contract_years(p),
            "morale": morale100,
        }
        for col, (key, _, _) in enumerate(self.COLUMNS):
            item = _SortItem(vals[key])
            if key in numeric:
                item.setData(Qt.UserRole, numeric[key])
            if key == "name":
                item.setData(Qt.UserRole + 1, p)
                item.setToolTip("Double-click to open profile")
            if key == "jersey":
                item.setToolTip("Click to change jersey number")
            if key == "morale":
                item.setToolTip(_morale_label(morale100))
            self.setItem(row, col, item)

    def _on_double_click(self, row, col):
        # Row order may differ from _players after sorting; read the
        # player object off the name cell instead.
        item = self.item(row, 1)
        if item is None:
            return
        p = item.data(Qt.UserRole + 1)
        if p is not None:
            self.player_clicked.emit(p)

    def row_player(self, row):
        item = self.item(row, 1)
        if item is None:
            return None
        return item.data(Qt.UserRole + 1)


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

BULK_ACTIONS = {
    "nhl": [("Send to AHL", "ahl", False)],
    "ahl": [("Call Up", "nhl", True), ("Return to Junior", "prospects", False)],
    "prospects": [("Promote to AHL", "ahl", True)],
}

TAB_DEFS = [
    ("nhl", "NHL Roster"),
    ("ahl", "AHL Roster"),
    ("prospects", "Prospects"),
    ("depth", "Depth Chart"),
    ("cap", "Salary Cap"),
]


class RosterScreen(BaseScreen):
    """Team roster: NHL / AHL / Prospects / Depth Chart / Salary Cap."""

    title = "Roster"

    def _build_body(self):
        self._headline = QLabel("")
        self._headline.setObjectName("tile-title")
        self._layout.addWidget(self._headline)

        # Captaincy-crisis banner (hidden unless a crisis is detected).
        self._crisis_banner = QPushButton("")
        self._crisis_banner.setCursor(Qt.PointingHandCursor)
        self._crisis_banner.setStyleSheet(
            "QPushButton { background: #3a1d1d; color: #f87171; "
            "font-size: 13px; font-weight: 700; border: 1px solid #7f2d2d; "
            "border-radius: 6px; padding: 8px; text-align: left; } "
            "QPushButton:hover { background: #4a2424; }")
        # NOTE: QPushButton has no setWordWrap() in Qt -- calling it raises
        # AttributeError and kills _build_body(). Banner text stays single-line.
        self._crisis_banner.clicked.connect(
            lambda: self._try_navigate("morale"))
        self._crisis_banner.hide()
        self._layout.addWidget(self._crisis_banner)

        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs)

        # --- table tabs ---
        self._views = {}
        for key, label in TAB_DEFS[:3]:
            view = self._make_table_view(key)
            self._tabs.addTab(view["widget"], label)
            self._views[key] = view

        # --- depth chart ---
        depth_w = QWidget()
        depth_layout = QVBoxLayout(depth_w)
        self._depth_scroll = QScrollArea()
        self._depth_scroll.setWidgetResizable(True)
        self._depth_inner = QWidget()
        self._depth_layout = QVBoxLayout(self._depth_inner)
        self._depth_scroll.setWidget(self._depth_inner)
        depth_layout.addWidget(self._depth_scroll)
        self._tabs.addTab(depth_w, "Depth Chart")

        # --- cap ---
        cap_w = QWidget()
        cap_layout = QVBoxLayout(cap_w)
        self._cap_overview = QLabel("")
        self._cap_overview.setWordWrap(True)
        cap_layout.addWidget(self._cap_overview)
        self._cap_bar = QProgressBar()
        self._cap_bar.setRange(0, 1000)
        self._cap_bar.setTextVisible(False)
        self._cap_bar.setFixedHeight(10)
        cap_layout.addWidget(self._cap_bar)
        self._cap_table = QTableWidget()
        self._cap_table.setColumnCount(5)
        self._cap_table.setHorizontalHeaderLabels(
            ["Player", "Pos", "Cap Hit", "Yrs", "Clauses"])
        self._cap_table.verticalHeader().setVisible(False)
        self._cap_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._cap_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._cap_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self._cap_table.cellDoubleClicked.connect(self._on_cap_double_click)
        cap_layout.addWidget(self._cap_table)
        self._tabs.addTab(cap_w, "Salary Cap")

        self._tabs.currentChanged.connect(self._on_tab_changed)

    # -- table view construction -------------------------------------------

    def _make_table_view(self, key):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 4)

        # toolbar: filters + search
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        filters = {"pos": "All", "age": "All", "ovr": "All", "search": ""}
        toolbar.addWidget(QLabel("Pos"))
        toolbar.addWidget(self._make_pills(
            ["All", "F", "D", "G"], "All",
            lambda v: self._set_filter(key, "pos", v)))
        toolbar.addWidget(QLabel("Age"))
        toolbar.addWidget(self._make_pills(
            ["All", "U23", "23-29", "30+"], "All",
            lambda v: self._set_filter(key, "age", v)))
        toolbar.addWidget(QLabel("OVR"))
        toolbar.addWidget(self._make_pills(
            ["All", "70+", "80+", "90+"], "All",
            lambda v: self._set_filter(key, "ovr", v)))
        search = QLineEdit()
        search.setPlaceholderText("Search name...")
        search.setMaximumWidth(200)
        search.textChanged.connect(
            lambda t: self._set_filter(key, "search", t))
        toolbar.addWidget(search)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # bulk actions
        bulk_bar = QHBoxLayout()
        bulk_bar.setSpacing(8)
        for label, to, primary in BULK_ACTIONS[key]:
            btn = QPushButton(label)
            if primary:
                btn.setObjectName("primary-btn")
            btn.clicked.connect(
                lambda checked=False, _to=to, _key=key: self._bulk_move(
                    _key, _to))
            bulk_bar.addWidget(btn)
        if key == "nhl":
            edit = QPushButton("Edit Lines")
            edit.setObjectName("primary-btn")
            edit.clicked.connect(lambda: self._try_navigate("lines"))
            bulk_bar.addWidget(edit)
        bulk_bar.addStretch()
        layout.addLayout(bulk_bar)

        # table
        table = RosterTable()
        table.player_clicked.connect(self._open_profile)
        table.cellClicked.connect(
            lambda r, c, _key=key: self._on_cell_clicked(_key, r, c))
        table.customContextMenuRequested.connect(
            lambda pos, _key=key: self._on_context_menu(_key, pos))
        layout.addWidget(table)

        # summary
        summary = QLabel("")
        layout.addWidget(summary)

        return {"widget": w, "table": table, "filters": filters,
                "summary": summary, "players": []}

    def _make_pills(self, values, default, on_change):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        group = QButtonGroup(self)
        for v in values:
            b = QPushButton(str(v))
            b.setCheckable(True)
            b.setChecked(v == default)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { border: 1px solid #33415e; border-radius: 12px;"
                " padding: 3px 10px; color: #9aa4b8; }"
                "QPushButton:checked { background: #2f6fed; color: white;"
                " border-color: #2f6fed; }")
            group.addButton(b)
            b.clicked.connect(lambda checked, _v=v: on_change(_v))
            h.addWidget(b)
        return w

    def _try_navigate(self, name):
        try:
            self.navigate_to(name)
        except Exception:
            QMessageBox.information(
                self, name.title(),
                f"The {name} screen is not available in this build yet.")

    # -- data ---------------------------------------------------------------

    def _resolve_gm(self):
        return _safe(lambda: getattr(self.game, "game_manager", None)) or self.game

    def _user_team(self):
        gm = self._resolve_gm()
        return (_safe(lambda: gm.user_team)
                or _safe(lambda: getattr(self.game, "user_team", None)))

    def _team_lists(self):
        team = self._user_team()
        if team is None:
            return [], [], []
        nhl = _safe(lambda: list(team.roster), []) or []
        ahl = _safe(lambda: list(getattr(team, "ahl_roster", [])), []) or []
        pros = _safe(lambda: list(getattr(team, "prospects", [])), []) or []
        return nhl, ahl, pros

    def refresh(self):
        self._load_table("nhl")
        self._load_table("ahl")
        self._load_table("prospects")
        self._load_depth()
        self._load_cap()
        self._update_headline()
        self._update_crisis_banner()

    def _update_crisis_banner(self):
        """Show a captaincy-crisis banner when the room is in crisis."""
        try:
            self._crisis_banner.hide()
            team = self._user_team()
            if team is None:
                return
            gm = self._resolve_gm()
            league = _safe(lambda: getattr(gm, "league", None))
            crisis = None
            try:
                import dressing_room as _dr
                # Prefer a stored crisis flag; fall back to live detection.
                dr = _dr.ensure_dressing_room_fields(team)
                if dr.get("captaincy_crisis"):
                    detail = dict(dr.get("captaincy_crisis_detail") or {})
                    crisis = {"captain_name": detail.get("captain_name", ""),
                              "severity": detail.get("severity", 1)}
                else:
                    hit = _dr.detect_captaincy_crisis(team, league)
                    if hit is not None:
                        crisis = {"captain_name": hit.get("captain_name", ""),
                                  "severity": hit.get("severity", 1)}
            except Exception:
                crisis = None
            if not crisis:
                return
            sev = "\U0001F534" * max(1, int(crisis.get("severity", 1) or 1))
            cap = crisis.get("captain_name", "") or "your captain"
            self._crisis_banner.setText(
                f"{sev}  Captaincy crisis: {cap} is losing the room.  "
                f"Click to open Morale →")
            self._crisis_banner.show()
        except Exception:
            try:
                self._crisis_banner.hide()
            except Exception:
                pass

    def _update_headline(self):
        counts = {k: len(self._views[k]["players"]) for k in self._views}
        self._headline.setText(
            f"{counts.get('nhl', 0)}/23 NHL  ·  {counts.get('ahl', 0)} AHL  ·  "
            f"{counts.get('prospects', 0)} Prospects")

    def _on_tab_changed(self, idx):
        key = TAB_DEFS[idx][0]
        if key == "ahl":
            # The full AHL experience (standings, scores, Calder race,
            # farm-club roster, prospects) lives on the AhIScreen -- the
            # tab is a shortcut there, not a second roster table.
            # Reset to the NHL tab so a return visit doesn't strand the
            # tab bar on a tab that always navigates away.
            self._tabs.blockSignals(True)
            try:
                self._tabs.setCurrentIndex(0)
            finally:
                self._tabs.blockSignals(False)
            self._try_navigate("ahl")
            return
        if key in self._views:
            self._load_table(key)
        elif key == "depth":
            self._load_depth()
        elif key == "cap":
            self._load_cap()

    # -- table tabs ----------------------------------------------------------

    def _load_table(self, key):
        view = self._views[key]
        nhl, ahl, pros = self._team_lists()
        players = {"nhl": nhl, "ahl": ahl, "prospects": pros}[key]
        view["players"] = list(players)
        self._render_table(key)

    def _set_filter(self, key, name, value):
        self._views[key]["filters"][name] = value
        self._render_table(key)

    def _filtered(self, key):
        f = self._views[key]["filters"]
        out = []
        for p in self._views[key]["players"]:
            if f["pos"] != "All":
                pos = _clean_position(_safe(lambda: getattr(
                    p, "primary_position", ""), ""))
                if _pos_group(pos) != f["pos"]:
                    continue
            age = _safe(lambda: int(getattr(p, "age", 0) or 0), 0)
            if f["age"] == "U23" and age >= 23:
                continue
            if f["age"] == "23-29" and (age < 23 or age > 29):
                continue
            if f["age"] == "30+" and age < 30:
                continue
            if f["ovr"] != "All" and _player_ovr(p) < int(f["ovr"].rstrip("+")):
                continue
            if f["search"]:
                name = _safe(lambda: getattr(p, "full_name", ""), "")
                if f["search"].lower() not in str(name).lower():
                    continue
            out.append(p)
        return out

    def _render_table(self, key):
        view = self._views[key]
        players = self._filtered(key)
        view["table"].set_players(players)
        n = len(view["players"])
        view["summary"].setText(
            f"{len(players)} shown  ·  {n} total")

    # -- jersey editing -------------------------------------------------------

    def _on_cell_clicked(self, key, row, col):
        if col != 0:  # jersey column
            return
        table = self._views[key]["table"]
        player = table.row_player(row)
        if player is None:
            return
        cur = _safe(lambda: int(getattr(player, "jersey_number", 0) or 0), 0)
        name = _safe(lambda: getattr(player, "full_name", "?"), "?")
        n, ok = QInputDialog.getInt(
            self, "Jersey Number",
            f"Number for {name} (current #{cur}).\n"
            f"Retired numbers stay retired; goalie numbers stay with "
            f"goalies; duplicates blocked.",
            cur, 1, 98)
        if not ok or n == cur:
            return
        team = self._user_team()
        valid, reason = _jersey_validation(team, player, n)
        if not valid:
            QMessageBox.warning(self, "Jersey Number", reason)
            return
        try:
            player.jersey_number = n
        except Exception as e:
            QMessageBox.warning(
                self, "Jersey Number", f"Could not set number: {e}")
            return
        self._render_table(key)

    # -- context menu ----------------------------------------------------------

    def _on_context_menu(self, key, pos):
        table = self._views[key]["table"]
        index = table.indexAt(pos)
        if not index.isValid():
            return
        player = table.row_player(index.row())
        if player is None:
            return
        menu = QMenu(self)
        menu.addAction("View Profile",
                       lambda: self._open_profile(player))
        menu.addAction("Add to Trade Block",
                       lambda: self._add_trade_block(player))
        menu.addAction("Contract Extension",
                       lambda: self._open_contracts(player))
        # IR place/activate -- mirrors EntityContextMenu.player_menu.
        try:
            import ir_system as _irs
            _ir_status = _irs.ir_status_of(player)
        except Exception:
            _ir_status = "None"
        if _ir_status in ("IR", "LTIR"):
            menu.addAction(f"Activate from {_ir_status}",
                           lambda: self._ir_activate(player))
        else:
            menu.addAction("Place on IR",
                           lambda: self._ir_place(player, "IR"))
            menu.addAction("Place on LTIR",
                           lambda: self._ir_place(player, "LTIR"))
        if key == "prospects" and getattr(player, "contract", None) is None:
            menu.addAction("Offer ELC",
                           lambda: self._open_contracts(player, elc=True))
        menu.exec(table.viewport().mapToGlobal(pos))

    def _open_profile(self, player):
        try:
            self.main_window.show_player(player)
        except Exception:
            try:
                self.navigate_to("player")
            except Exception:
                pass

    def _add_trade_block(self, player):
        """Right-click 'Add to Trade Block': open the TradeBlockScreen
        with the player on the block. Delegates to the shared context-
        menu helper so both right-click paths run the same code."""
        try:
            from ..widgets.context_menu import EntityContextMenu
            EntityContextMenu._add_trade_block(
                self.main_window, self.game, player)
        except Exception as e:
            QMessageBox.warning(self, "Trade Block",
                                f"Could not open the trade block: {e}")

    def _open_contracts(self, player, elc=False):
        # The contracts screen is not ported yet; hand off navigation.
        try:
            self.navigate_to("contracts")
        except Exception:
            what = "an entry-level contract" if elc else "a contract extension"
            name = _safe(lambda: getattr(player, "full_name", "?"), "?")
            QMessageBox.information(
                self, "Contracts",
                f"Offer {what} to {name} on the Contracts screen, "
                f"which is not available in this build yet.")

    def _ir_place(self, player, kind):
        """Place a player on IR/LTIR. Delegates to the shared context-menu
        helper so both right-click paths run the same code."""
        try:
            from ..widgets.context_menu import EntityContextMenu
            EntityContextMenu._ir_place(self.main_window, player, kind)
        except Exception as e:
            QMessageBox.warning(self, "Injured Reserve",
                                f"Could not place on {kind}: {e}")

    def _ir_activate(self, player):
        """Activate a player off IR/LTIR. Delegates to the shared helper."""
        try:
            from ..widgets.context_menu import EntityContextMenu
            EntityContextMenu._ir_activate(self.main_window, player)
        except Exception as e:
            QMessageBox.warning(self, "Injured Reserve",
                                f"Could not activate: {e}")

    # -- bulk moves ------------------------------------------------------------

    def _selected_players(self, key):
        table = self._views[key]["table"]
        rows = {i.row() for i in table.selectedIndexes()}
        return [table.row_player(r) for r in sorted(rows)
                if table.row_player(r) is not None]

    def _bulk_move(self, key, to):
        players = self._selected_players(key)
        if not players:
            QMessageBox.information(
                self, "Roster Move", "Select players first.")
            return
        dest = {"nhl": "NHL", "ahl": "AHL", "prospects": "prospects"}[to]
        ok = QMessageBox.question(
            self, "Roster Move",
            f"Move {len(players)} player(s) to {dest}?")
        if ok != QMessageBox.Yes:
            return
        moved, errors = self._move_players(players, key, to)
        if errors:
            QMessageBox.warning(
                self, "Roster Move",
                f"Moved {moved}. Some moves blocked:\n" + "\n".join(errors))
        elif moved:
            QMessageBox.information(
                self, "Roster Move", f"Moved {moved} player(s).")
        for k in self._views:
            self._load_table(k)
        self._update_headline()

    def _move_players(self, players, frm, to):
        """CBA-validated roster moves. Port of execute_roster_move
        (web_ui/screens/roster.py) -- runs synchronously on the Qt thread."""
        team = self._user_team()
        if team is None:
            return 0, ["no team"]
        src_map = {
            "nhl": _safe(lambda: list(team.roster), []) or [],
            "ahl": _safe(lambda: list(getattr(team, "ahl_roster", [])), []) or [],
            "prospects": _safe(lambda: list(getattr(team, "prospects", [])), []) or [],
        }
        src = src_map.get(frm, [])
        dst_attr = {"nhl": "roster", "ahl": "ahl_roster",
                    "prospects": "prospects"}.get(to)
        if dst_attr is None:
            return 0, ["bad destination"]
        by_id = {str(_safe(lambda: getattr(p, "id", ""), "")): p for p in src}
        wanted = [by_id[str(_safe(lambda: getattr(p, "id", ""), ""))]
                  for p in players]
        wanted = [p for p in wanted if p is not None]
        try:
            import game_classes as _gc
        except Exception:
            _gc = None
        moved, errors = 0, []
        is_promotion = frm not in ("nhl", "ahl") and to in ("nhl", "ahl")
        is_junior_return = frm in ("nhl", "ahl") and to not in ("nhl", "ahl")
        dst = getattr(team, dst_attr, None)
        if dst is None:
            return 0, ["bad destination"]
        for player in wanted:
            name = _safe(lambda: getattr(player, "full_name", "?"), "?")
            if is_promotion:
                if to == "ahl" and _gc is not None:
                    try:
                        if not _gc.prospect_ahl_eligible(player):
                            errors.append(
                                f"{name}: not AHL-eligible "
                                f"(CHL-NHL agreement)")
                            continue
                    except Exception:
                        pass
                if to == "nhl" and len(
                        _safe(lambda: list(team.roster), []) or []) >= 23:
                    errors.append(f"{name}: NHL roster full (23)")
                    continue
                if getattr(player, "contract", None) is None:
                    errors.append(
                        f"{name}: needs an entry-level contract first")
                    continue
                try:
                    player.playing_where = "NHL" if to == "nhl" else "AHL"
                except Exception:
                    pass
            elif is_junior_return:
                if getattr(player, "contract", None) is not None \
                        and _gc is not None:
                    try:
                        track = _gc.junior_track_of(player)
                        jage = int(getattr(player, "age", 20) or 20)
                        if not (track == "CHL" and jage < 20):
                            errors.append(
                                f"{name}: only junior-aged CHL prospects "
                                f"can return to junior")
                            continue
                    except Exception:
                        pass
            try:
                src.remove(player)
                dst.append(player)
                moved += 1
            except Exception as e:
                errors.append(f"{name}: move failed ({e})")
        return moved, errors

    # -- depth chart -------------------------------------------------------------

    def _lines_units(self, team):
        lineup = _safe(lambda: getattr(team, "lineup", None), None) or {}
        if not lineup or not lineup.get("Forwards"):
            # Fresh game: use the game's own best-lines algorithm.
            try:
                from quick_sim import best_lines
                raw = best_lines(team) or {}
                norm = {}
                for k, v in raw.items():
                    ks = str(k)
                    if ks.startswith("F") and "_" in ks:
                        parts = ks.split("_", 1)
                        norm[f"{parts[1]}{parts[0][1:]}"] = v
                    elif ks.startswith("D") and "_" in ks:
                        parts = ks.split("_", 1)
                        side = "L" if parts[1] == "L" else "R"
                        norm[f"{side}D{parts[0][1:]}"] = v
                    elif ks in ("G1", "G2"):
                        norm[ks] = v
                lineup = norm
            except Exception:
                lineup = {}
        return _group_lineup(lineup)

    def _load_depth(self):
        while self._depth_layout.count():
            child = self._depth_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        team = self._user_team()
        if team is None:
            self._depth_layout.addWidget(QLabel("No team loaded."))
            return
        units = self._lines_units(team)
        if not units:
            self._depth_layout.addWidget(QLabel("No lines set."))
        for unit in units:
            frame = QFrame()
            frame.setObjectName("tile")
            fl = QVBoxLayout(frame)
            title = QLabel(unit["label"])
            title.setObjectName("tile-title")
            fl.addWidget(title)
            grid = QGridLayout()
            grid.setSpacing(6)
            for i, slot in enumerate(unit["slots"]):
                p = slot["player"]
                if p is not None:
                    name = _safe(lambda: getattr(p, "full_name", "?"), "?")
                    pos = _clean_position(_safe(lambda: getattr(
                        p, "primary_position", ""), ""))
                    btn = QPushButton(
                        f"{slot['slot']}: {name}  ({pos} · {_player_ovr(p)} OVR)")
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.clicked.connect(
                        lambda checked=False, _p=p: self._open_profile(_p))
                    grid.addWidget(btn, i // 2, i % 2)
                else:
                    lab = QLabel(f"{slot['slot']}: Empty")
                    lab.setStyleSheet("color: #6b7488;")
                    grid.addWidget(lab, i // 2, i % 2)
            fl.addLayout(grid)
            self._depth_layout.addWidget(frame)
        self._depth_layout.addStretch()

    # -- salary cap ---------------------------------------------------------------

    def _load_cap(self):
        team = self._user_team()
        if team is None:
            self._cap_overview.setText("No team loaded.")
            return
        try:
            from salary_cap_system import cap_breakdown
            bd = cap_breakdown(team)
            cap = bd["cap"]
            total = bd["total"]
            space = bd["space"]
            dead = bd["dead_cap"]
            extra = {
                "Retained": bd.get("seeded_retained", 0),
                "Overage": bd.get("seeded_overage", 0),
                "Buyouts": bd.get("seeded_buyout", 0),
            }
        except Exception:
            cap = _safe(lambda: getattr(team, "salary_cap", 104_000_000),
                        104_000_000) or 104_000_000
            nhl, _, _ = self._team_lists()
            total = sum(_player_salary(p) for p in nhl)
            space = cap - total
            dead = 0
            extra = {}
        pct = round(total / cap * 100, 1) if cap else 0
        self._cap_bar.setValue(int(min(100, pct) * 10))

        lines = [
            f"Salary Cap: {_fmt_money(cap)}",
            f"Payroll: {_fmt_money(total)}  ({pct}%)",
            f"Cap Space: {_fmt_money(space)}",
        ]
        if dead:
            lines.append(f"Dead Cap: {_fmt_money(dead)}")
        for k, v in extra.items():
            if v:
                lines.append(f"{k}: {_fmt_money(v)}")
        self._cap_overview.setText("   ·   ".join(lines))

        nhl, _, _ = self._team_lists()
        contracts = []
        for p in nhl:
            c = _safe(lambda: getattr(p, "contract", None))
            clauses = []
            if c is not None and _safe(
                    lambda: bool(getattr(c, "no_movement_clause", False)),
                    False):
                clauses.append("NMC")
            elif c is not None and _safe(
                    lambda: bool(getattr(c, "no_trade_clause", False)),
                    False):
                clauses.append("NTC")
            contracts.append({
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "pos": _clean_position(_safe(lambda: getattr(
                    p, "primary_position", ""), "")),
                "salary": _player_salary(p),
                "yrs": _contract_years(p) if c is not None else "--",
                "clauses": " ".join(clauses),
                "player": p,
            })
        contracts.sort(key=lambda c: c["salary"], reverse=True)

        self._cap_table.setSortingEnabled(False)
        self._cap_table.setRowCount(len(contracts))
        for r, cinfo in enumerate(contracts):
            cells = [cinfo["name"], cinfo["pos"],
                     _fmt_money(cinfo["salary"]), str(cinfo["yrs"]),
                     cinfo["clauses"]]
            for col, text in enumerate(cells):
                item = _SortItem(text)
                if col == 2:
                    item.setData(Qt.UserRole, cinfo["salary"])
                if col == 0:
                    item.setData(Qt.UserRole + 1, cinfo["player"])
                self._cap_table.setItem(r, col, item)
        self._cap_table.setSortingEnabled(True)

    def _on_cap_double_click(self, row, col):
        item = self._cap_table.item(row, 0)
        if item is None:
            return
        p = item.data(Qt.UserRole + 1)
        if p is not None:
            self._open_profile(p)
