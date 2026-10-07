"""Finances screen: salary-cap dashboard, future-season projections, the 5
desktop financial reports, management recommendations + quick actions,
contracts view with filters, cap-position breakdown, and the buyout
calculator.

Native port of the web UI finances screen
(web_ui/templates/finances.html + web_ui/screens/finances.py +
web_ui/static/js/finances.js). Calls the game object DIRECTLY --
no Flask/HTTP, no command queue, no JSON.

Game methods used (all real, same as the web bridge called):
  - game manager / game.user_team, game.league.season_year
  - salary_cap_system: cap_breakdown, cap_space, total_cap_charge,
    BURY_THRESHOLD, SALARY_CAP_FLOOR, DEFAULT_CAP
  - windows.buyout_schedule(player)                    (real NHL buyout math)
  - buyout_window.execute_buyout(league, team, player)  (the single mutation)
  - transaction_windows.check_window("buyout", current_date)
  - game._validate_contract_terms / game.handle_contract_offer /
    game.send_email_to_user (auto-negotiate quick action)
"""

from datetime import date

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, QProgressBar,
    QMessageBox, QScrollArea, QWidget, QHeaderView, QSplitter,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


# ---------------------------------------------------------------------------
# generic helpers (same conventions as native_ui/screens/contracts.py)
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


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


def _pid(p):
    return str(_safe(lambda: getattr(p, "id", id(p)), ""))


_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD",
    "DEFENSE": "D", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}


def _clean_position(pos):
    try:
        s = str(pos or "")
        if "." in s:
            s = s.split(".")[-1]
        s = s.strip().upper()
        return _POSITION_ABBR.get(s, s or "?")
    except Exception:
        return "?"


def _pos_str(p):
    """Enum-safe position string: PlayerPosition -> 'RW', never raw enum."""
    pos = _safe(lambda: getattr(p, "primary_position", ""), "")
    return _clean_position(getattr(pos, "value", pos))


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


def _player_name(p):
    return _safe(lambda: getattr(p, "full_name", "?"), "?")


def _resolve_gm(game):
    gm = _safe(lambda: getattr(game, "game_manager", None))
    return gm if gm is not None else game


def _user_team(game):
    gm = _resolve_gm(game)
    return _safe(lambda: gm.user_team) or _safe(lambda: game.user_team)


def _season_year(game):
    gm = _resolve_gm(game)
    return _safe(
        lambda: int(getattr(getattr(gm, "league", None), "season_year", 0)
                    or 0), 0)


# ---------------------------------------------------------------------------
# contract helpers (ported from web_ui/screens/finances.py)
# ---------------------------------------------------------------------------

def _contract_salary(p):
    c = _safe(lambda: getattr(p, "contract", None))
    s = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0)
    if s <= 0:
        s = _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)
    return max(0, s)


def _contract_years_left(p):
    c = _safe(lambda: getattr(p, "contract", None))
    y = _safe(lambda: getattr(c, "years_remaining", None))
    if y is None:
        y = _safe(lambda: getattr(p, "contract_years", 1), 1)
    return max(0, _safe(lambda: int(y or 0), 0))


def _contract_status(p, years_left):
    """Desktop determine_contract_status: RFA / UFA / Expiring / Long-term."""
    age = _safe(lambda: int(getattr(p, "age", 22) or 22), 22)
    if years_left <= 1:
        return "RFA" if age < 25 else "UFA"
    if years_left <= 2:
        return "Expiring"
    return "Long-term"


def _estimate_ask(p):
    """Deterministic port of estimate_contract_ask (web uses the band
    midpoint so the number is stable and honest)."""
    try:
        ovr = float(p.overall_rating())
    except Exception:
        ovr = 75.0
    age = _safe(lambda: int(getattr(p, "age", 22) or 22), 22)
    cur = _contract_salary(p)
    if ovr >= 85:
        lo, hi = 8_000_000, 12_000_000
    elif ovr >= 80:
        lo, hi = 5_000_000, 8_000_000
    elif ovr >= 75:
        lo, hi = 3_000_000, 5_000_000
    elif ovr >= 70:
        lo, hi = 1_500_000, 3_000_000
    else:
        lo, hi = 750_000, 1_500_000
    base = (lo + hi) / 2
    if age < 25:
        base *= 0.9
    elif age > 32:
        base *= 0.8
    if cur > 0:
        base = max(cur * 0.7, min(cur * 1.5, base))
    return int(base)


def _player_cap_hit(p):
    """Best-effort per-player cap hit: contract AAV first, then .salary."""
    hit = _safe(
        lambda: int(getattr(getattr(p, "contract", None), "salary", 0) or 0)
        + int(getattr(getattr(p, "contract", None), "signing_bonus", 0) or 0)
        - int(getattr(p, "retained_amount", 0) or 0), None)
    if hit is not None and hit > 0:
        return max(0, hit)
    return _safe(lambda: int(getattr(p, "salary", 0) or 0), 0)


def _cap_breakdown(team):
    """Cap breakdown dict. Real salary_cap_system.cap_breakdown first,
    sum-of-salaries fallback (same chain as the web endpoint)."""
    try:
        from salary_cap_system import cap_breakdown as _cb
        bd = _safe(lambda: _cb(team))
    except Exception:
        bd = None
    cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                            or 104_000_000), 104_000_000)
    floor = _safe(lambda: int(getattr(team, "salary_floor", 78_000_000)
                              or 78_000_000), 78_000_000)
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    sum_hits = _safe(lambda: sum(_player_cap_hit(p) for p in roster), 0)
    if (not isinstance(bd, dict)
            or (_safe(lambda: int(bd.get("total", 0) or 0), 0) == 0
                and sum_hits > 0)):
        bd = {
            "cap": cap, "roster": sum_hits, "buried": 0,
            "waivers_shed": 0, "buyouts": 0, "seeded_buyout": 0,
            "seeded_retained": 0, "seeded_overage": 0, "retained": 0,
            "retention_slots": "0/3", "dead_cap": 0, "total": sum_hits,
            "space": cap - sum_hits, "over_cap": (cap - sum_hits) < 0,
            "floor": floor, "floor_space": sum_hits - floor,
            "under_floor": sum_hits < floor,
        }
    return bd or {}


def _cap_status(bd):
    total = _safe(lambda: int(bd.get("total", 0) or 0), 0)
    space = _safe(lambda: int(bd.get("space", 0) or 0), 0)
    cap = _safe(lambda: int(bd.get("cap", 1) or 1), 1)
    if _safe(lambda: bool(bd.get("over_cap", space < 0)), space < 0):
        return "over"
    if _safe(lambda: bool(bd.get("under_floor", False)), False):
        return "under_floor"
    if cap and space / cap < 0.03:
        return "tight"
    return "comfortable"


def _position_breakdown(team):
    """Desktop calculate_position_breakdown: Goalies / Defense / Forwards."""
    pos = {"Goalies": {"count": 0, "total": 0},
           "Defense": {"count": 0, "total": 0},
           "Forwards": {"count": 0, "total": 0}}
    try:
        from game_classes import PlayerPosition as _PP
    except Exception:
        _PP = None
    roster = _safe(lambda: list(getattr(team, "roster", None) or []), []) or []
    for p in roster:
        try:
            s = _contract_salary(p)
            pp = getattr(p, "primary_position", None)
            if _PP is not None and pp == _PP.GOALIE:
                key = "Goalies"
            elif _PP is not None and pp in (
                    _PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE,
                    getattr(_PP, "DEFENSE", None)):
                key = "Defense"
            else:
                key = "Forwards"
            pos[key]["count"] += 1
            pos[key]["total"] += s
        except Exception:
            continue
    for d in pos.values():
        d["avg"] = d["total"] // d["count"] if d["count"] else 0
    return pos


# ---------------------------------------------------------------------------
# buyout helpers (ported from web_ui/screens/finances.py)
# ---------------------------------------------------------------------------

def _buyout_schedule(p):
    """(total, annual, byears, rows) via the game's real NHL buyout math."""
    try:
        from windows import buyout_schedule
        return buyout_schedule(p)
    except Exception:
        return 0, 0, 0, []


def _buyout_candidate(p):
    c = _safe(lambda: getattr(p, "contract", None))
    if c is None:
        return None
    salary = _safe(lambda: int(getattr(c, "salary", 0) or 0), 0)
    years = _safe(lambda: int(getattr(c, "years_remaining", 0) or 0), 0)
    if salary <= 0 or years <= 0:
        return None
    total, annual, byears, rows = _buyout_schedule(p)
    if not rows:
        return None
    return {
        "player": p,
        "name": _player_name(p),
        "position": _pos_str(p),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
        "cap_hit": salary,
        "years_left": years,
        "buyout_cost": int(total),
        "annual_dead": int(annual),
        "dead_years": int(byears),
        "schedule": [(int(i), int(hit), int(sav)) for (i, hit, sav) in rows],
        "nmc": _safe(lambda: bool(getattr(c, "no_movement_clause", False)),
                     False),
        "ntc": _safe(lambda: bool(getattr(c, "no_trade_clause", False)),
                     False),
    }


def _buyout_window_ok(game):
    try:
        import transaction_windows as _tw
        cur = _safe(lambda: getattr(_resolve_gm(game), "current_date", None))
        return _tw.check_window("buyout", cur)
    except Exception:
        return True, ""


# ---------------------------------------------------------------------------
# table helpers
# ---------------------------------------------------------------------------

def _make_table(columns, rows, stretch_last=True):
    tbl = QTableWidget()
    tbl.setColumnCount(len(columns))
    tbl.setHorizontalHeaderLabels(columns)
    tbl.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            tbl.setItem(r, c, item)
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tbl.setSelectionBehavior(QTableWidget.SelectRows)
    tbl.setEditTriggers(QTableWidget.NoEditTriggers)
    return tbl


def _kv_rows(pairs):
    """Small key-value table. Values may be pre-formatted strings."""
    tbl = _make_table(["Item", "Value"], [(k, v) for k, v in pairs])
    # Use row height from the table instead of hardcoded 24px
    row_h = tbl.rowHeight(0) if tbl.rowCount() > 0 else 24
    tbl.setMaximumHeight(row_h * (len(pairs) + 1) + 8)
    return tbl


class FinancesScreen(BaseScreen):
    """Salary-cap dashboard + projections, reports, management, contracts,
    cap position, and the buyout calculator."""

    title = "Finances"

    # -- layout ----------------------------------------------------------

    def _build_body(self):
        self._team = None

        # hero: cap status numbers + gauge
        hero = QGroupBox("Salary Cap")
        hl = QVBoxLayout(hero)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("section-header")
        hl.addWidget(self._status_lbl)
        nums = QHBoxLayout()
        self._hero_vals = {}
        for name, key in (("Payroll", "payroll"),
                          ("Cap Space", "space"),
                          ("Salary Cap", "cap")):
            box = QVBoxLayout()
            t = QLabel(name)
            t.setStyleSheet("color: #6b7488; font-size: 11px;")
            v = QLabel("--")
            v.setStyleSheet("font-size: 20px; font-weight: 700;")
            box.addWidget(t)
            box.addWidget(v)
            nums.addLayout(box, 1)
            self._hero_vals[key] = v
        hl.addLayout(nums)
        self._gauge = QProgressBar()
        self._gauge.setRange(0, 100)
        hl.addWidget(self._gauge)
        self._gauge_lbl = QLabel("")
        self._gauge_lbl.setStyleSheet("color: #6b7488; font-size: 11px;")
        hl.addWidget(self._gauge_lbl)
        self._layout.addWidget(hero)

        # cap breakdown + owner budget side by side
        mid = QHBoxLayout()
        self._breakdown_box = QGroupBox("Cap Breakdown")
        self._breakdown_l = QVBoxLayout(self._breakdown_box)
        mid.addWidget(self._breakdown_box, 1)
        self._budget_box = QGroupBox("Owner Budget")
        self._budget_l = QVBoxLayout(self._budget_box)
        mid.addWidget(self._budget_box, 1)
        self._layout.addLayout(mid)

        # tabs
        self._tabs = QTabWidget()
        self._build_roster_tab()
        self._build_projections_tab()
        self._build_reports_tab()
        self._build_management_tab()
        self._build_contracts_tab()
        self._build_cap_tab()
        self._layout.addWidget(self._tabs, 1)

        # buyout calculator
        self._build_buyout_section()

    # -- tabs ------------------------------------------------------------

    def _build_roster_tab(self):
        self._hits_table = _make_table(
            ["#", "Player", "Pos", "Age", "OVR", "Cap Hit", "% of Cap"], [])
        self._hits_table.itemDoubleClicked.connect(self._open_profile)
        page = QWidget()
        l = QVBoxLayout(page)
        l.addWidget(self._hits_table)
        self._hits_players = []
        self._tabs.addTab(page, "Top Cap Hits")

    def _build_projections_tab(self):
        page = QWidget()
        l = QVBoxLayout(page)
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Target season"))
        self._proj_year = QComboBox()
        self._proj_year.currentIndexChanged.connect(self._load_projections)
        ctrls.addWidget(self._proj_year)
        ctrls.addStretch()
        l.addLayout(ctrls)
        stats = QHBoxLayout()
        self._proj_committed = QLabel("--")
        self._proj_cap = QLabel("--")
        self._proj_space = QLabel("--")
        for name, w in (("Committed payroll", self._proj_committed),
                        ("Projected cap", self._proj_cap),
                        ("Projected space", self._proj_space)):
            box = QVBoxLayout()
            t = QLabel(name)
            t.setStyleSheet("color: #6b7488; font-size: 11px;")
            w.setStyleSheet("font-size: 18px; font-weight: 700;")
            box.addWidget(t)
            box.addWidget(w)
            stats.addLayout(box, 1)
        l.addLayout(stats)
        self._proj_note = QLabel("")
        self._proj_note.setStyleSheet("color: #6b7488; font-size: 11px;")
        l.addWidget(self._proj_note)
        self._proj_table = _make_table(
            ["Player", "Pos", "Age", "Status", "Current", "Est. Ask"], [])
        l.addWidget(self._proj_table, 1)
        self._proj_expiring = []
        self._tabs.addTab(page, "Projections")

    def _build_reports_tab(self):
        page = QWidget()
        l = QVBoxLayout(page)
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Report"))
        self._report_combo = QComboBox()
        self._report_combo.addItem("Salary Breakdown", "salary_breakdown")
        self._report_combo.addItem("Contract Timeline", "contract_timeline")
        self._report_combo.addItem("Position Analysis", "position_analysis")
        self._report_combo.addItem("Age Demographics", "age_demographics")
        self._report_combo.addItem("Performance vs Salary", "performance_salary")
        self._report_combo.currentIndexChanged.connect(self._load_report)
        ctrls.addWidget(self._report_combo)
        ctrls.addStretch()
        l.addLayout(ctrls)
        self._report_scroll = QScrollArea()
        self._report_scroll.setWidgetResizable(True)
        self._report_body = QWidget()
        self._report_l = QVBoxLayout(self._report_body)
        self._report_scroll.setWidget(self._report_body)
        l.addWidget(self._report_scroll, 1)
        self._tabs.addTab(page, "Reports")

    def _build_management_tab(self):
        page = QWidget()
        l = QVBoxLayout(page)
        self._mgmt_box = QVBoxLayout()
        l.addLayout(self._mgmt_box)
        acts = QHBoxLayout()
        self._auto_btn = QPushButton("Auto-Negotiate All Expiring Extensions")
        self._auto_btn.setObjectName("primary-btn")
        self._auto_btn.setCursor(Qt.PointingHandCursor)
        self._auto_btn.clicked.connect(self._auto_negotiate)
        self._contracts_btn = QPushButton("Review Contracts")
        self._contracts_btn.clicked.connect(lambda: self.navigate_to("contracts"))
        self._fa_btn = QPushButton("Browse Free Agents")
        self._fa_btn.clicked.connect(
            lambda: self.navigate_to("free_agents"))
        for b in (self._auto_btn, self._contracts_btn, self._fa_btn):
            acts.addWidget(b)
        acts.addStretch()
        l.addLayout(acts)
        l.addStretch()
        self._tabs.addTab(page, "Management")

    def _build_contracts_tab(self):
        page = QWidget()
        l = QVBoxLayout(page)
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Pos"))
        self._ctr_pos = QComboBox()
        self._ctr_pos.addItems(["All", "C", "LW", "RW", "D", "G"])
        self._ctr_pos.currentIndexChanged.connect(self._load_contracts)
        ctrls.addWidget(self._ctr_pos)
        ctrls.addWidget(QLabel("Status"))
        self._ctr_status = QComboBox()
        self._ctr_status.addItems(
            ["All", "Expiring", "UFA", "RFA", "Long-term"])
        self._ctr_status.currentIndexChanged.connect(self._load_contracts)
        ctrls.addWidget(self._ctr_status)
        ctrls.addWidget(QLabel("Search"))
        self._ctr_q = QLineEdit()
        self._ctr_q.setPlaceholderText("player name…")
        self._ctr_q.textChanged.connect(self._load_contracts)
        ctrls.addWidget(self._ctr_q, 1)
        ctrls.addWidget(QLabel("Sort"))
        self._ctr_sort = QComboBox()
        self._ctr_sort.addItems(["Salary", "Name", "Years left", "Age"])
        self._ctr_sort.currentIndexChanged.connect(self._load_contracts)
        ctrls.addWidget(self._ctr_sort)
        ctrls.addStretch()
        l.addLayout(ctrls)
        self._ctr_table = _make_table(
            ["Player", "Pos", "Age", "Status", "AAV", "Yrs Left", "Est. Ask",
             "NTC", "NMC"], [])
        self._ctr_table.itemDoubleClicked.connect(self._open_profile)
        l.addWidget(self._ctr_table, 1)
        self._ctr_players = []
        self._tabs.addTab(page, "Contracts")

    def _build_cap_tab(self):
        page = QWidget()
        l = QVBoxLayout(page)
        self._cap_pos_l = QVBoxLayout()
        l.addLayout(self._cap_pos_l)
        l.addStretch()
        self._tabs.addTab(page, "Cap Position")

    def _build_buyout_section(self):
        box = QGroupBox("Buyout Calculator")
        l = QVBoxLayout(box)
        note = QLabel(
            "NHL rules: 2/3 of remaining salary (1/3 if under 26), spread over "
            "2× remaining term. A bought-out player becomes a free agent and "
            "cannot be re-signed for one year.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6b7488; font-size: 11px;")
        l.addWidget(note)
        self._buyout_window_lbl = QLabel("")
        self._buyout_window_lbl.setStyleSheet("color: #b8860b; font-size: 11px;")
        l.addWidget(self._buyout_window_lbl)

        split = QSplitter(Qt.Horizontal)
        self._buyout_list = _make_table(
            ["Player", "Pos", "Age", "Cap Hit", "Yrs", "Buyout Cost",
             "Annual Dead", "Dead Yrs", "Clause"], [])
        self._buyout_list.itemSelectionChanged.connect(
            self._on_buyout_select)
        split.addWidget(self._buyout_list)

        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(8, 0, 0, 0)
        self._buyout_detail_title = QLabel("Select a player to see their "
                                           "buyout breakdown.")
        self._buyout_detail_title.setWordWrap(True)
        dl.addWidget(self._buyout_detail_title)
        self._buyout_sched = _make_table(["Year", "Cap Hit", "Savings"], [])
        dl.addWidget(self._buyout_sched, 1)
        self._buyout_warn = QLabel("")
        self._buyout_warn.setWordWrap(True)
        self._buyout_warn.setStyleSheet("color: #c0392b; font-size: 12px;")
        dl.addWidget(self._buyout_warn)
        self._buyout_exec = QPushButton("Execute Buyout")
        self._buyout_exec.setObjectName("primary-btn")
        self._buyout_exec.setCursor(Qt.PointingHandCursor)
        self._buyout_exec.clicked.connect(self._execute_buyout)
        dl.addWidget(self._buyout_exec)
        dl.addStretch()
        split.addWidget(detail)
        split.setSizes([560, 340])
        l.addWidget(split)

        self._buyout_active_lbl = QLabel("")
        self._buyout_active_lbl.setStyleSheet("color: #6b7488; font-size: 11px;")
        l.addWidget(QLabel("Active buyout cap hits:"))
        l.addWidget(self._buyout_active_lbl)
        self._layout.addWidget(box)
        self._buyout_candidates = []
        self._buyout_selected = None

    # -- data ------------------------------------------------------------

    def refresh(self):
        self._team = _user_team(self.game)
        if self._team is None:
            self._status_lbl.setText("No team loaded.")
            return
        season = _season_year(self.game)
        yrs = [str(season + i) for i in range(6)]
        cur = self._proj_year.currentText()
        self._proj_year.blockSignals(True)
        self._proj_year.clear()
        self._proj_year.addItems(yrs)
        if cur in yrs:
            self._proj_year.setCurrentText(cur)
        self._proj_year.blockSignals(False)

        self._load_hero()
        self._load_hits()
        self._load_projections()
        self._load_report()
        self._load_management()
        self._load_contracts()
        self._load_cap_position()
        self._load_buyouts()

    def _load_hero(self):
        team = self._team
        bd = _cap_breakdown(team)
        total = _safe(lambda: int(bd.get("total", 0) or 0), 0)
        space = _safe(lambda: int(bd.get("space", 0) or 0), 0)
        cap = _safe(lambda: int(bd.get("cap", 104_000_000) or 104_000_000),
                    104_000_000)
        floor = _safe(lambda: int(bd.get("floor", 78_000_000) or 78_000_000),
                      78_000_000)
        dead = _safe(lambda: int(bd.get("dead_cap", 0) or 0), 0)
        status = _cap_status(bd)
        status_txt = {
            "over": "OVER THE CAP", "under_floor": "UNDER THE CAP FLOOR",
            "tight": "TIGHT AGAINST THE CAP", "comfortable": "COMFORTABLE",
        }.get(status, status.upper())
        self._status_lbl.setText(status_txt)
        self._hero_vals["payroll"].setText(_fmt_money(total))
        self._hero_vals["space"].setText(_fmt_money(space))
        self._hero_vals["cap"].setText(_fmt_money(cap))
        pct = int(100 * total / cap) if cap else 0
        self._gauge.setValue(min(100, max(0, pct)))
        self._gauge_lbl.setText(
            f"{pct}% of cap used · floor {_fmt_money(floor)}")

        # cap breakdown
        self._clear_layout(self._breakdown_l)
        rows = [
            ("Roster payroll", bd.get("roster")),
            ("Buried salary", bd.get("buried")),
            ("Buyout dead cap", bd.get("buyouts")),
            ("Retained salary", bd.get("retained")),
            ("Total dead cap", dead),
            ("Total cap charge", bd.get("total")),
            ("Cap space", bd.get("space")),
        ]
        self._breakdown_l.addWidget(_kv_rows(
            [(k, _fmt_money(v)) for k, v in rows]))
        if bd.get("retention_slots"):
            rs = QLabel(f"Retention slots: {bd.get('retention_slots')}")
            rs.setStyleSheet("color: #6b7488; font-size: 11px;")
            self._breakdown_l.addWidget(rs)

        # owner budget
        self._clear_layout(self._budget_l)
        budget = _safe(lambda: int(getattr(team, "player_budget", 0) or 0), 0)
        spent = _safe(lambda: int(getattr(team, "bonus_spent", 0) or 0), 0)
        remaining = _safe(lambda: int(team.player_budget_remaining()),
                          budget - spent)
        left = QLabel(_fmt_money(remaining))
        left.setStyleSheet("font-size: 20px; font-weight: 700;")
        self._budget_l.addWidget(QLabel("Cash Remaining"))
        self._budget_l.addWidget(left)
        gauge = QProgressBar()
        gauge.setRange(0, 100)
        gauge.setValue(
            int(100 * (budget - remaining) / budget) if budget else 0)
        self._budget_l.addWidget(gauge)
        meta = QLabel(f"Spent {_fmt_money(spent)} · Budget {_fmt_money(budget)}")
        meta.setStyleSheet("color: #6b7488; font-size: 11px;")
        self._budget_l.addWidget(meta)

    def _load_hits(self):
        team = self._team
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        bd = _cap_breakdown(team)
        cap = _safe(lambda: int(bd.get("cap", 104_000_000) or 104_000_000),
                    104_000_000)
        hits = []
        for p in roster:
            try:
                hits.append({
                    "player": p, "name": _player_name(p),
                    "position": _pos_str(p),
                    "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                    "overall": _player_ovr(p),
                    "salary": _player_cap_hit(p),
                    "injured": _safe(
                        lambda: bool(getattr(p, "is_injured", False)), False),
                })
            except Exception:
                continue
        hits.sort(key=lambda h: h["salary"], reverse=True)
        self._hits_players = hits
        rows = []
        for i, h in enumerate(hits[:15], 1):
            pct = f"{100 * h['salary'] / cap:.1f}%" if cap else "--"
            name = h["name"] + ("  (IR)" if h["injured"] else "")
            rows.append([i, name, h["position"], h["age"], h["overall"],
                         _fmt_money(h["salary"]), pct])
        self._set_table(self._hits_table, rows)

    def _load_projections(self):
        team = self._team
        season = _season_year(self.game)
        try:
            year = int(self._proj_year.currentText() or season)
        except (TypeError, ValueError):
            year = season
        years_ahead = max(0, year - season)
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        committed = 0
        expiring = []
        for p in roster:
            try:
                yl = _contract_years_left(p)
                salary = _contract_salary(p)
                if yl > years_ahead:
                    committed += salary
                else:
                    expiring.append({
                        "player": p, "name": _player_name(p),
                        "position": _pos_str(p),
                        "age": _safe(lambda: int(getattr(p, "age", 0) or 0),
                                     0),
                        "salary": salary, "years_left": yl,
                        "status": _contract_status(p, yl),
                        "estimated_ask": _estimate_ask(p),
                    })
            except Exception:
                continue
        expiring.sort(key=lambda e: -e["salary"])
        self._proj_expiring = expiring
        cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                                or 104_000_000), 104_000_000)
        self._proj_committed.setText(_fmt_money(committed))
        self._proj_cap.setText(_fmt_money(cap))
        self._proj_space.setText(_fmt_money(cap - committed))
        self._proj_note.setText(
            f"{len(expiring)} expiring contract(s) before the {year} season")
        rows = [[e["name"], e["position"], e["age"], e["status"],
                 _fmt_money(e["salary"]), _fmt_money(e["estimated_ask"])]
                for e in expiring]
        self._set_table(self._proj_table, rows)

    def _load_contracts(self):
        team = self._team
        if team is None:
            return
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        filt = self._ctr_status.currentText()
        posf = self._ctr_pos.currentText()
        q = self._ctr_q.text().strip().lower()
        sort = self._ctr_sort.currentText()
        rows = []
        for p in roster:
            try:
                yl = _contract_years_left(p)
                status = _contract_status(p, yl)
                pos = _pos_str(p)
                name = _player_name(p)
                if filt == "Expiring" and yl > 1:
                    continue
                if filt == "UFA" and status != "UFA":
                    continue
                if filt == "RFA" and status != "RFA":
                    continue
                if filt == "Long-term" and status != "Long-term":
                    continue
                if posf != "All" and pos.upper() != posf.upper() \
                        and not (posf == "D" and pos in ("LD", "RD")):
                    continue
                if q and q not in name.lower():
                    continue
                c = _safe(lambda: getattr(p, "contract", None))
                rows.append({
                    "player": p, "name": name, "position": pos,
                    "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                    "salary": _contract_salary(p), "years_left": yl,
                    "status": status,
                    "ntc": _safe(lambda: bool(
                        getattr(c, "no_trade_clause", False)), False),
                    "nmc": _safe(lambda: bool(
                        getattr(c, "no_movement_clause", False)), False),
                    "estimated_ask": _estimate_ask(p),
                })
            except Exception:
                continue
        if sort == "Name":
            rows.sort(key=lambda r: r["name"])
        elif sort == "Years left":
            rows.sort(key=lambda r: r["years_left"])
        elif sort == "Age":
            rows.sort(key=lambda r: -r["age"])
        else:
            rows.sort(key=lambda r: -r["salary"])
        self._ctr_players = rows
        tbl_rows = [[r["name"], r["position"], r["age"], r["status"],
                     _fmt_money(r["salary"]), r["years_left"],
                     _fmt_money(r["estimated_ask"]),
                     "✓" if r["ntc"] else "", "✓" if r["nmc"] else ""]
                    for r in rows]
        self._set_table(self._ctr_table, tbl_rows)

    def _load_cap_position(self):
        team = self._team
        self._clear_layout(self._cap_pos_l)
        posd = _position_breakdown(team)
        payroll = sum(d["total"] for d in posd.values())
        cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                                or 104_000_000), 104_000_000)
        floor = _safe(lambda: int(getattr(team, "salary_floor", 78_000_000)
                                  or 78_000_000), 78_000_000)
        self._cap_pos_l.addWidget(_kv_rows([
            ("Salary cap", _fmt_money(cap)),
            ("Cap floor", _fmt_money(floor)),
            ("Payroll", _fmt_money(payroll)),
            ("Cap space", _fmt_money(cap - payroll)),
        ]))
        hdr = QLabel("Spending by position group")
        hdr.setStyleSheet("font-weight: 700; margin-top: 8px;")
        self._cap_pos_l.addWidget(hdr)
        self._cap_pos_l.addWidget(_kv_rows([
            (f"{k} ({d['count']})",
             f"{_fmt_money(d['total'])}  ·  avg {_fmt_money(d['avg'])}")
            for k, d in posd.items()
        ]))
        ahl = _safe(lambda: list(getattr(team, "ahl_roster", None) or []),
                    []) or []
        ahl_payroll = sum(_contract_salary(p) for p in ahl)
        try:
            from salary_cap_system import BURY_THRESHOLD as _bt
            bury_cap = int(_bt)
        except Exception:
            bury_cap = 1_150_000
        buried = sum(max(0, _contract_salary(p) - bury_cap) for p in ahl)
        hdr2 = QLabel("AHL payroll")
        hdr2.setStyleSheet("font-weight: 700; margin-top: 8px;")
        self._cap_pos_l.addWidget(hdr2)
        self._cap_pos_l.addWidget(_kv_rows([
            ("AHL players", str(len(ahl))),
            ("AHL payroll", _fmt_money(ahl_payroll)),
            ("Bury threshold", _fmt_money(bury_cap)),
            ("Buried salary counting vs cap", _fmt_money(buried)),
        ]))

    # -- reports ---------------------------------------------------------

    REPORTS = [
        ("salary_breakdown", "Salary Breakdown"),
        ("contract_timeline", "Contract Timeline"),
        ("position_analysis", "Position Analysis"),
        ("age_demographics", "Age Demographics"),
        ("performance_salary", "Performance vs Salary"),
    ]

    def _report_data(self, key):
        team = self._team
        season = _season_year(self.game)
        cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                                or 104_000_000), 104_000_000)
        if key == "salary_breakdown":
            return self._report_salary_breakdown(team, cap)
        if key == "contract_timeline":
            return self._report_contract_timeline(team, season)
        if key == "position_analysis":
            return self._report_position_analysis(team)
        if key == "age_demographics":
            return self._report_age_demographics(team)
        return self._report_performance_salary(team)

    def _report_salary_breakdown(self, team, cap):
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        payroll = sum(_contract_salary(p) for p in roster)
        rows = []
        for p in sorted(roster, key=_contract_salary, reverse=True)[:10]:
            s = _contract_salary(p)
            rows.append([_player_name(p), _pos_str(p), _fmt_money(s),
                         f"{100 * s / payroll:.1f}%" if payroll else "--"])
        posd = _position_breakdown(team)
        pos_rows = [[k, d["count"], _fmt_money(d["total"]),
                     _fmt_money(d["avg"])] for k, d in posd.items()]
        return {"title": "Salary Breakdown", "widgets": [
            ("Summary", _kv_rows([
                ("Payroll", _fmt_money(payroll)),
                ("Salary cap", _fmt_money(cap)),
                ("Cap space", _fmt_money(cap - payroll)),
                ("Utilization",
                 f"{100 * payroll / cap:.1f}%" if cap else "--"),
            ])),
            ("Top 10 salaries", _make_table(
                ["Player", "Pos", "Salary", "% of Payroll"], rows)),
            ("By position group", _make_table(
                ["Group", "Count", "Total", "Average"], pos_rows)),
        ]}

    def _report_contract_timeline(self, team, season):
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        groups = {}
        for p in roster:
            try:
                yl = _contract_years_left(p)
                yr = season + yl
                age = _safe(lambda: int(getattr(p, "age", 22) or 22), 22)
                groups.setdefault(yr, []).append({
                    "name": _player_name(p),
                    "salary": _contract_salary(p),
                    "age_at_expiry": age + yl,
                    "status": "RFA" if age + yl < 25 else "UFA",
                })
            except Exception:
                continue
        widgets = []
        for yr in sorted(groups):
            ps = sorted(groups[yr], key=lambda r: -r["salary"])
            total = sum(r["salary"] for r in ps)
            rows = [[r["name"], _fmt_money(r["salary"]), r["age_at_expiry"],
                     r["status"]] for r in ps]
            widgets.append(
                (f"{yr} — {len(ps)} contract(s), {_fmt_money(total)}",
                 _make_table(["Player", "Salary", "Age at Expiry", "Status"],
                             rows)))
        return {"title": "Contract Timeline", "widgets": widgets}

    def _report_position_analysis(self, team):
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        try:
            from game_classes import PlayerPosition as _PP
        except Exception:
            _PP = None
        groups = {"Goalies": [], "Defense": [], "Centers": [], "Wingers": []}
        for p in roster:
            try:
                pp = getattr(p, "primary_position", None)
                if _PP is not None and pp == _PP.GOALIE:
                    groups["Goalies"].append(p)
                elif _PP is not None and pp in (
                        _PP.LEFT_DEFENSE, _PP.RIGHT_DEFENSE,
                        getattr(_PP, "DEFENSE", None)):
                    groups["Defense"].append(p)
                elif _PP is not None and pp == _PP.CENTER:
                    groups["Centers"].append(p)
                else:
                    groups["Wingers"].append(p)
            except Exception:
                continue
        widgets = []
        for name, ps in groups.items():
            if not ps:
                continue
            total = sum(_contract_salary(p) for p in ps)
            try:
                avg_ovr = sum(float(p.overall_rating()) for p in ps) / len(ps)
            except Exception:
                avg_ovr = 0
            avg_age = sum(_safe(lambda: int(getattr(p, "age", 22) or 22), 22)
                          for p in ps) / len(ps)
            rows = [[_player_name(p), _fmt_money(_contract_salary(p)),
                     _safe(lambda: int(getattr(p, "age", 0) or 0), 0)]
                    for p in sorted(ps, key=_contract_salary, reverse=True)]
            widgets.append(
                (f"{name} — {len(ps)} players, {_fmt_money(total)} total, "
                 f"{avg_ovr:.1f} avg OVR, {avg_age:.1f} avg age",
                 _make_table(["Player", "Salary", "Age"], rows)))
        return {"title": "Position Analysis", "widgets": widgets}

    def _report_age_demographics(self, team):
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        bands = [("Under 25", 0, 24), ("25-29", 25, 29),
                 ("30-34", 30, 34), ("35+", 35, 99)]
        widgets = []
        for name, lo, hi in bands:
            ps = [p for p in roster
                  if lo <= _safe(lambda: int(getattr(p, "age", 27) or 27), 27)
                  <= hi]
            total = sum(_contract_salary(p) for p in ps)
            rows = [[_player_name(p),
                     _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                     _fmt_money(_contract_salary(p))]
                    for p in sorted(ps, key=_contract_salary, reverse=True)]
            avg = _fmt_money(total // len(ps)) if ps else "--"
            widgets.append(
                (f"{name} — {len(ps)} players, {_fmt_money(total)} total, "
                 f"avg {avg}",
                 _make_table(["Player", "Age", "Salary"], rows)))
        return {"title": "Age Demographics", "widgets": widgets}

    def _report_performance_salary(self, team):
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        rows = []
        for p in roster:
            try:
                pos = _pos_str(p)
                s = _contract_salary(p)
                if pos.upper() in ("G", "GOALIE"):
                    gp = _safe(lambda: int(getattr(p, "games_played", 0)
                                           or 0), 0)
                    sv = _safe(lambda: float(getattr(p, "save_percentage", 0)
                                            or 0), 0.0)
                    metric, label = sv, "SV%"
                    _ = gp
                else:
                    pts = _safe(lambda: int(getattr(p, "points", 0) or 0), 0)
                    metric, label = pts, "PTS"
                per = s / metric if metric else None
                rows.append([_player_name(p), pos, _fmt_money(s),
                             f"{metric:g}" if metric else "--",
                             label,
                             _fmt_money(int(per)) if per else "--",
                             per if per else float("inf")])
            except Exception:
                continue
        rows.sort(key=lambda r: r[-1])
        tbl_rows = [r[:-1] for r in rows]
        return {"title": "Performance vs Salary", "widgets": [
            ("Dollars per point / per SV% point (lower is better)",
             _make_table(["Player", "Pos", "Salary", "Metric", "Type",
                          "$ per"], tbl_rows)),
        ]}

    def _load_report(self):
        self._clear_layout(self._report_l)
        if self._team is None:
            self._report_l.addWidget(QLabel("No team loaded."))
            return
        key = self._report_combo.currentData()
        try:
            data = self._report_data(key)
        except Exception as e:
            self._report_l.addWidget(QLabel(f"Report failed: {e}"))
            return
        title = QLabel(data["title"])
        title.setObjectName("section-header")
        self._report_l.addWidget(title)
        for label, widget in data["widgets"]:
            hdr = QLabel(label)
            hdr.setStyleSheet("font-weight: 700; margin-top: 8px;")
            self._report_l.addWidget(hdr)
            self._report_l.addWidget(widget)
        self._report_l.addStretch()

    # -- management ------------------------------------------------------

    def _load_management(self):
        self._clear_layout(self._mgmt_box)
        team = self._team
        if team is None:
            self._mgmt_box.addWidget(QLabel("No team loaded."))
            return
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        payroll = sum(_contract_salary(p) for p in roster)
        cap = _safe(lambda: int(getattr(team, "salary_cap", 104_000_000)
                                or 104_000_000), 104_000_000)
        space = cap - payroll
        pct = (payroll / cap * 100) if cap else 0
        recs = []
        if pct > 95:
            recs.append(("urgent",
                "You are very close to the salary cap. Consider trading "
                "high-salary players or demoting players to create space."))
        elif pct > 90:
            recs.append(("warning",
                "Limited cap space available. Be cautious with any new "
                "signings."))
        elif pct < 70:
            recs.append(("info",
                "You have significant cap space available. Consider "
                "upgrading your roster through free agency or trades."))
        expiring = [p for p in roster if _contract_years_left(p) <= 1]
        if len(expiring) > 8:
            recs.append(("warning",
                f"You have {len(expiring)} players with expiring contracts. "
                "Start extension negotiations early to avoid losing key "
                "players."))
        old_exp = [p for p in roster
                   if _safe(lambda: int(getattr(p, "age", 22) or 22), 22) > 33
                   and _contract_salary(p) > 4_000_000]
        if old_exp:
            names = ", ".join(_player_name(p) for p in old_exp[:3])
            recs.append(("info",
                f"Consider the future value of older, expensive players: "
                f"{names}{'...' if len(old_exp) > 3 else ''}"))
        posd = _position_breakdown(team)
        if payroll:
            g_pct = 100 * posd["Goalies"]["total"] / payroll
            d_pct = 100 * posd["Defense"]["total"] / payroll
            f_pct = 100 * posd["Forwards"]["total"] / payroll
            if g_pct > 15:
                recs.append(("info",
                    "Your goalie spending is high relative to other "
                    "positions. Consider if this allocation is optimal."))
            if d_pct > 35:
                recs.append(("info",
                    "High spending on defense. Ensure this matches your "
                    "team strategy."))
            if f_pct < 50:
                recs.append(("info",
                    "Consider if your forward spending is sufficient for "
                    "offensive production."))
        if not recs:
            recs.append(("ok",
                "Your financial situation looks stable. Continue monitoring "
                "contract expirations and cap space."))
        colors = {"urgent": "#c0392b", "warning": "#b8860b", "info": "#2471a3",
                  "ok": "#1e8449"}
        summary = QLabel(f"Payroll {_fmt_money(payroll)} / cap "
                         f"{_fmt_money(cap)} ({pct:.1f}% used)")
        summary.setStyleSheet("font-weight: 700;")
        self._mgmt_box.addWidget(summary)
        for lvl, txt in recs:
            icon = {"urgent": "🚨", "warning": "⚠️", "info": "ℹ️",
                    "ok": "✅"}.get(lvl, "•")
            lbl = QLabel(f"{icon}  {txt}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {colors.get(lvl, '#000')}; "
                              "font-size: 13px; padding: 4px 0;")
            self._mgmt_box.addWidget(lbl)
        self._auto_btn.setEnabled(bool(expiring))
        self._fa_btn.setEnabled(space > 1_000_000)

    def _auto_negotiate(self):
        """Auto-negotiate extensions with every expiring deal.

        Mirrors ContractsScreen._auto_negotiate (native_ui/screens/
        contracts.py): offers are pre-validated through the game's own
        gate, run through the real handle_contract_offer(notify="quiet"),
        and results land in one inbox digest. Confirm-gated.
        """
        game = self.game
        team = self._team or _user_team(game)
        if team is None:
            QMessageBox.warning(self, "Auto-Negotiate", "No team loaded.")
            return
        players = []
        for lst in ("roster", "ahl_roster"):
            players.extend(
                _safe(lambda: list(getattr(team, lst, None) or []), []) or [])
        expiring_players = [p for p in players
                            if _contract_years_left(p) == 1]
        expiring_staff = [
            s for s in _safe(lambda: list(getattr(team, "staff", None)
                                          or []), []) or []
            if _safe(lambda: int(getattr(s, "contract_years", 0) or 0),
                     0) == 1]
        n = len(expiring_players) + len(expiring_staff)
        if n == 0:
            QMessageBox.information(
                self, "Auto-Negotiate", "No expiring contracts found.")
            return
        reply = QMessageBox.question(
            self, "Auto-Negotiate",
            f"Auto-negotiate extensions with {n} expiring contract(s)? "
            "Results will arrive in your inbox.")
        if reply != QMessageBox.Yes:
            return
        results = []
        for person in expiring_players + expiring_staff:
            name = _safe(lambda: getattr(person, "full_name", None),
                         None) or _safe(
                             lambda: getattr(person, "name", "Unknown"),
                             "Unknown")
            salary = _contract_salary(person) or _safe(
                lambda: int(getattr(person, "salary", 750_000) or 750_000),
                750_000)
            years = _contract_years_left(person) or _safe(
                lambda: int(getattr(person, "contract_years", 1) or 1), 1)
            ok, reason = _safe(
                lambda: game._validate_contract_terms(
                    person, salary, years, extension=True),
                (False, "validation failed"))
            if not ok:
                results.append(f"{name}: Skipped ({reason})")
                continue
            try:
                person.salary = salary
                person.contract_years = years
            except Exception:
                pass
            try:
                accepted = game.handle_contract_offer(
                    person, extension=True, notify="quiet")
            except Exception as e:
                results.append(f"{name}: Error ({e})")
                continue
            results.append(
                f"{name}: {'Accepted' if accepted else 'Rejected'}")
        try:
            from game_classes import EmailMessage
            game.send_email_to_user(EmailMessage(
                sender="System", sender_type="System", date_sent=date.today(),
                category="Contracts", priority=2,
                subject="Auto-Negotiation Results",
                content="Automatic extension negotiations complete:\n" +
                        "\n".join(f"\u2022 {r}" for r in results)))
        except Exception:
            pass
        QMessageBox.information(
            self, "Auto-Negotiate",
            "Auto-negotiation complete — check your inbox for results.")
        self.refresh()

    # -- buyouts ---------------------------------------------------------

    def _load_buyouts(self):
        team = self._team
        win_ok, win_msg = _buyout_window_ok(self.game)
        if win_ok:
            self._buyout_window_lbl.setText("")
        else:
            self._buyout_window_lbl.setText(
                f"⚠️ Buyout window closed: {win_msg or 'not open'}")
        roster = _safe(lambda: list(getattr(team, "roster", None) or []),
                       []) or []
        cands = []
        for p in roster:
            try:
                c = _buyout_candidate(p)
                if c:
                    cands.append(c)
            except Exception:
                continue
        cands.sort(key=lambda c: -c["cap_hit"])
        self._buyout_candidates = cands
        rows = []
        for c in cands:
            clause = ""
            if c["nmc"]:
                clause = "NMC"
            elif c["ntc"]:
                clause = "NTC"
            rows.append([c["name"], c["position"], c["age"],
                         _fmt_money(c["cap_hit"]), c["years_left"],
                         _fmt_money(c["buyout_cost"]),
                         _fmt_money(c["annual_dead"]), c["dead_years"],
                         clause])
        self._set_table(self._buyout_list, rows)
        self._buyout_selected = None
        self._buyout_detail_title.setText(
            "Select a player to see their buyout breakdown.")
        self._set_table(self._buyout_sched, [])
        self._buyout_warn.setText("")
        self._buyout_exec.setVisible(False)
        hits = _safe(lambda: dict(getattr(team, "buyout_cap_hits", None)
                                  or {}), {}) or {}
        if hits:
            self._buyout_active_lbl.setText(", ".join(
                f"{y}: {_fmt_money(v)}" for y, v in sorted(hits.items())))
        else:
            self._buyout_active_lbl.setText("None")

    def _on_buyout_select(self):
        rows = self._buyout_list.selectionModel().selectedRows()
        if not rows or not self._buyout_candidates:
            self._buyout_selected = None
            self._buyout_exec.setVisible(False)
            return
        idx = rows[0].row()
        if not (0 <= idx < len(self._buyout_candidates)):
            return
        c = self._buyout_candidates[idx]
        self._buyout_selected = c
        self._buyout_detail_title.setText(
            f"{c['name']} — {c['position']}, age {c['age']}\n"
            f"Cap hit {_fmt_money(c['cap_hit'])}, {c['years_left']} yr(s) "
            f"left · buyout cost {_fmt_money(c['buyout_cost'])}, "
            f"{c['dead_years']} yr(s) of dead cap")
        sched_rows = [[f"Year {i}", _fmt_money(hit), _fmt_money(sav)]
                      for (i, hit, sav) in c["schedule"]]
        self._set_table(self._buyout_sched, sched_rows)
        if c["nmc"] or c["ntc"]:
            clause = "no-movement" if c["nmc"] else "no-trade"
            self._buyout_warn.setText(
                f"⚠️ Buyout blocked: {c['name']} has a {clause} clause.")
            self._buyout_exec.setVisible(False)
            return
        win_ok, win_msg = _buyout_window_ok(self.game)
        if not win_ok:
            self._buyout_warn.setText(
                f"⚠️ Buyout window closed: {win_msg or 'not open'}.")
            self._buyout_exec.setVisible(False)
            return
        self._buyout_warn.setText("")
        self._buyout_exec.setVisible(True)

    def _execute_buyout(self):
        c = self._buyout_selected
        if c is None:
            return
        win_ok, win_msg = _buyout_window_ok(self.game)
        if not win_ok:
            QMessageBox.warning(
                self, "Buyout",
                f"Buyout window is closed: {win_msg or 'not open'}.")
            return
        player = c["player"]
        reply = QMessageBox.question(
            self, "Confirm Buyout",
            f"Buy out {c['name']}?\n\n"
            f"Cap hit removed: {_fmt_money(c['cap_hit'])}\n"
            f"Buyout cost: {_fmt_money(c['buyout_cost'])} "
            f"({_fmt_money(c['annual_dead'])}/yr for "
            f"{c['dead_years']} yr(s))\n\n"
            "The player becomes a free agent and cannot be re-signed "
            "for one year.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        team = self._team
        league = _safe(lambda: getattr(_resolve_gm(self.game), "league",
                                       None))
        try:
            from buyout_window import execute_buyout
            execute_buyout(league, team, player)
        except Exception as e:
            QMessageBox.critical(
                self, "Buyout", f"Buyout failed: {e}")
            return
        QMessageBox.information(
            self, "Buyout",
            f"{c['name']} has been bought out.")
        self.refresh()

    # -- navigation ------------------------------------------------------

    def _open_profile(self, item):
        tbl = self.sender()
        if tbl is self._hits_table:
            players = [h["player"] for h in self._hits_players]
        elif tbl is self._ctr_table:
            players = [r["player"] for r in self._ctr_players]
        else:
            return
        row = item.row()
        if not (0 <= row < len(players)):
            return
        player = players[row]
        try:
            self.main_window.show_player(player)
        except Exception:
            try:
                self.navigate_to("player")
            except Exception:
                pass

    # -- small utils -----------------------------------------------------

    @staticmethod
    def _set_table(tbl, rows):
        tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                tbl.setItem(r, c, item)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.setParent(None)
            sub = child.layout()
            if sub is not None:
                FinancesScreen._clear_layout(sub)
