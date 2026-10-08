"""Staff screen: coaches & management.

Three tabs (lazy-loaded, one at a time): Staff list, Org Chart, Staff Report.
Per-staff actions: Release (confirm dialog mentioning severance) and
Reassign (modal dialog with role selector). Staff are grouped by role;
names click through to StaffDetailScreen.

Calls the game object directly -- no HTTP, no serialization.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QScrollArea, QDialog, QComboBox, QMessageBox, QGridLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen


# ----------------------------------------------------------------------
# Helpers (web_ui/screens/staff.py + staff_detail.py parity)
# ----------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _staff_name(s):
    name = _safe(lambda: getattr(s, "full_name", None), None)
    if name:
        return name
    fn = _safe(lambda: getattr(s, "first_name", ""), "") or ""
    ln = _safe(lambda: getattr(s, "last_name", ""), "") or ""
    return f"{fn} {ln}".strip() or "?"


def _staff_role_value(s):
    """Display role string, e.g. 'Head Coach'."""
    role = getattr(s, "role", None)
    if role is None:
        return "Staff"
    return _safe(lambda: getattr(role, "value", None) or str(role), "Staff")


def _staff_role_name(s):
    """Enum name of the role, e.g. 'HEAD_COACH'."""
    return str(_safe(lambda: getattr(getattr(s, "role", None), "name", ""),
                     "") or "")


def _fmt_salary(sal):
    """Compact salary: $1.25M / $850K (staff.js parity)."""
    sal = int(sal or 0)
    if sal >= 1_000_000:
        return f"${sal / 1_000_000:.2f}M"
    return f"${round(sal / 1_000)}K"


def _fmt_money(sal):
    return f"${int(sal or 0):,}"


def _rating_color(v):
    """Bar badge color thresholds (staff.js barColor parity)."""
    if v >= 80:
        return "#4CAF50"
    if v >= 65:
        return "#8BC34A"
    if v >= 50:
        return "#FFC107"
    if v >= 35:
        return "#FF9800"
    return "#F44336"


_STAFF_CATEGORIES = [
    ("Management", ["GENERAL_MANAGER", "ASSISTANT_GENERAL_MANAGER"]),
    ("Coaching", ["HEAD_COACH", "ASSISTANT_COACH", "ASSOCIATE_COACH",
                  "GOALIE_COACH", "POWER_PLAY_COACH", "PENALTY_KILL_COACH",
                  "SKATING_COACH", "SKILLS_COACH", "STRENGTH_COACH",
                  "CONDITIONING_COACH", "VIDEO_COACH"]),
    ("Scouting", ["HEAD_SCOUT", "PROFESSIONAL_SCOUT", "AMATEUR_SCOUT",
                  "EUROPEAN_SCOUT", "ADVANCE_SCOUT"]),
    ("Medical", ["TEAM_DOCTOR", "PHYSIOTHERAPIST"]),
    ("Analytics", ["ANALYTICS_DIRECTOR", "STATISTICIAN",
                   "MEDIA_RELATIONS"]),
]


def _staff_cat(s):
    name = _staff_role_name(s)
    for cat, roles in _STAFF_CATEGORIES:
        if name in roles:
            return cat
    return "Other"


def _staff_status(s):
    """One-line staff status (web staff_detail parity)."""
    try:
        morale = int(getattr(s, "morale", 70) or 70)
    except Exception:
        morale = 70
    try:
        years = int(getattr(s, "contract_years", 2) or 2)
    except Exception:
        years = 2
    if years <= 1:
        return "Expiring contract"
    if morale >= 80:
        return "Content"
    if morale >= 60:
        return "Steady"
    if morale >= 40:
        return "Restless"
    return "Unhappy"


class StaffScreen(BaseScreen):
    """Coaches & management."""

    title = "Staff"

    def _build_body(self):
        self._staff = []          # raw staff objects
        self._team_name = ""
        self._loaded = {0: False, 1: False, 2: False, 3: False}

        self._tabs = QTabWidget()
        self._tabs.setObjectName("staff-tabs")
        self._tabs.addTab(self._make_list_page(), "Staff")
        self._tabs.addTab(self._make_org_page(), "Org Chart")
        self._tabs.addTab(self._make_report_page(), "Staff Report")
        self._tabs.addTab(self._make_assistant_page(), "Assistants")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._layout.addWidget(self._tabs)

    # --- tab page scaffolds ------------------------------------------------
    def _page_scroll(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setSpacing(12)
        scroll.setWidget(inner)
        return scroll, lay

    def _make_list_page(self):
        self._list_scroll, self._list_lay = self._page_scroll()
        self._count_label = QLabel("")
        self._count_label.setStyleSheet(
            "color: #8b95ab; font-size: 13px;")
        self._list_lay.addWidget(self._count_label)
        self._list_lay.addStretch()
        return self._list_scroll

    def _make_org_page(self):
        self._org_scroll, self._org_lay = self._page_scroll()
        self._org_lay.addStretch()
        return self._org_scroll

    def _make_report_page(self):
        self._report_scroll, self._report_lay = self._page_scroll()
        self._report_lay.addStretch()
        return self._report_scroll

    def _make_assistant_page(self):
        self._asst_scroll, self._asst_lay = self._page_scroll()
        self._asst_lay.addStretch()
        return self._asst_scroll

    # --- data ---------------------------------------------------------------
    def _load_data(self):
        self._staff = []
        self._team_name = ""
        try:
            game = self.game
            if game is None:
                return
            gm = getattr(game, "game_manager", None) or game
            team = getattr(gm, "user_team", None) or \
                getattr(game, "user_team", None)
            if team is None:
                return
            self._team_name = _safe(
                lambda: getattr(team, "team_name", ""), "") or ""
            self._staff = [s for s in
                           _safe(lambda: list(getattr(team, "staff", []) or []),
                                 [])]
        except Exception as e:
            print(f"[staff] load failed: {e}")

    def refresh(self):
        self._load_data()
        self._loaded = {0: False, 1: False, 2: False, 3: False}
        self._on_tab_changed(self._tabs.currentIndex())

    def _on_tab_changed(self, idx):
        if self._loaded.get(idx):
            return
        if idx == 0:
            self._render_list()
        elif idx == 1:
            self._render_org()
        elif idx == 2:
            self._render_report()
        elif idx == 3:
            self._render_assistants()
        self._loaded[idx] = True

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
            child_lay = item.layout()
            if child_lay is not None:
                self._clear(child_lay)

    # --- Staff list tab ------------------------------------------------------
    def _render_list(self):
        lay = self._list_lay
        self._clear(lay)
        count = len(self._staff)
        self._count_label.setText(
            f"{count} staff member{'s' if count != 1 else ''}")
        lay.addWidget(self._count_label)
        if not count:
            empty = QLabel("No staff on the team.")
            empty.setStyleSheet("color: #6b7488; font-size: 14px;")
            empty.setAlignment(Qt.AlignCenter)
            lay.addWidget(empty)
            lay.addStretch()
            return

        # Group by role, preserving first-seen order
        groups = {}
        for s in self._staff:
            role = _staff_role_value(s)
            groups.setdefault(role, []).append(s)

        for role, members in groups.items():
            members.sort(key=lambda m: int(
                _safe(lambda: getattr(m, "overall_rating", 0), 0) or 0),
                         reverse=True)
            header = QLabel(
                f"{role.upper()}  ({len(members)})")
            header.setObjectName("section-header")
            lay.addWidget(header)

            grid = QGridLayout()
            grid.setSpacing(10)
            for i, s in enumerate(members):
                grid.addWidget(self._make_staff_card(s), i // 3, i % 3)
            lay.addLayout(grid)
        lay.addStretch()

    def _make_staff_card(self, s):
        card = QFrame()
        card.setObjectName("tile")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)

        rating = int(_safe(lambda: getattr(s, "overall_rating", 0), 0) or 0)
        color = _rating_color(rating)

        # Header: rating badge + name/sub
        head = QHBoxLayout()
        badge = QLabel(str(rating))
        badge.setStyleSheet(
            f"font-size: 26px; font-weight: 900; color: {color};"
            " min-width: 40px;")
        badge.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        head.addWidget(badge)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name_lbl = QLabel(_staff_name(s))
        name_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #4ea1ff;"
            " text-decoration: underline;")
        name_lbl.setCursor(Qt.PointingHandCursor)
        name_lbl.setToolTip("Open staff profile")
        name_lbl.mousePressEvent = \
            lambda e, staff=s: self._open_staff_detail(staff)
        name_col.addWidget(name_lbl)
        age = _safe(lambda: getattr(s, "age", 0), 0) or 0
        nat = _safe(lambda: getattr(s, "nationality", ""), "") or ""
        sub = " · ".join(x for x in
                         ([f"Age {age}"] if age else []) + ([nat] if nat
                                                           else []))
        sub_lbl = QLabel(sub or _staff_role_value(s))
        sub_lbl.setStyleSheet("font-size: 12px; color: #8b95ab;")
        name_col.addWidget(sub_lbl)
        head.addLayout(name_col, 1)
        v.addLayout(head)

        # Rating bar
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(min(100, max(0, rating)))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setStyleSheet(
            "QProgressBar { background-color: #1a2338; border: none;"
            " border-radius: 3px; }"
            f"QProgressBar::chunk {{ background-color: {color};"
            " border-radius: 3px; }")
        v.addWidget(bar)

        # Meta
        morale = _safe(lambda: getattr(s, "morale", "—"), "—")
        exp = _safe(lambda: getattr(s, "experience", "—"), "—")
        sal = _fmt_salary(_safe(lambda: getattr(s, "salary", 0), 0))
        meta = QLabel(
            f"<span style='color:#8b95ab'>Morale</span> <b>{morale}</b>"
            f" &nbsp; <span style='color:#8b95ab'>Exp</span> <b>{exp}y</b>"
            f" &nbsp; <span style='color:#8b95ab'>Salary</span> <b>{sal}</b>")
        meta.setStyleSheet("font-size: 12px; color: #d6dbe6;")
        v.addWidget(meta)

        # Actions
        row = QHBoxLayout()
        row.setSpacing(8)
        reassign_btn = QPushButton("Reassign Role")
        reassign_btn.setCursor(Qt.PointingHandCursor)
        reassign_btn.clicked.connect(
            lambda _=False, staff=s: self._show_reassign(staff))
        release_btn = QPushButton("Release")
        release_btn.setCursor(Qt.PointingHandCursor)
        release_btn.setStyleSheet(
            "QPushButton { background-color: #3a1d22; color: #ff8a8a;"
            " border: 1px solid #6b2a32; border-radius: 6px; padding: 6px; }"
            "QPushButton:hover { background-color: #4d2329; }")
        release_btn.clicked.connect(
            lambda _=False, staff=s: self._release_staff(staff))
        row.addWidget(reassign_btn)
        row.addWidget(release_btn)
        row.addStretch()
        v.addLayout(row)
        return card

    # --- Org chart tab --------------------------------------------------------
    def _org_tree(self):
        """Build org-chart levels (web api_staff_org_chart parity)."""
        cats = {}
        for s in self._staff:
            cats.setdefault(_staff_cat(s), []).append(s)
        for members in cats.values():
            members.sort(key=lambda m: int(
                _safe(lambda: getattr(m, "overall_rating", 0), 0) or 0),
                reverse=True)

        def has_role(s, *names):
            return _staff_role_name(s) in names

        def nhl_first(members):
            """Vacant chairs first, then NHL-assigned, then AHL/farm staff."""
            return sorted(
                members,
                key=lambda m: 0 if str(_safe(
                    lambda: getattr(m, "assignment", ""), "") or ""
                ).lower() != "ahl" else 1)

        tree = []
        mgmt = cats.get("Management", [])
        gm_s = next((s for s in nhl_first(mgmt)
                     if has_role(s, "GENERAL_MANAGER")), None)
        agms = [s for s in mgmt if s is not gm_s]
        tree.append(("Management", [
            ("General Manager", "person", gm_s),
            ("Assistant General Manager", "people", agms),
        ]))
        coaches = cats.get("Coaching", [])
        hc = next((s for s in nhl_first(coaches)
                   if has_role(s, "HEAD_COACH")), None)
        assistants = [s for s in coaches
                      if has_role(s, "ASSISTANT_COACH", "ASSOCIATE_COACH")]
        specialists = [s for s in coaches
                       if s is not hc and s not in assistants]
        tree.append(("Coaching Staff", [
            ("Head Coach", "person", hc),
            ("Assistant Coaches", "people", assistants),
            ("Specialized Coaches", "people", specialists),
        ]))
        for dept in ("Scouting", "Medical", "Analytics"):
            tree.append((dept, [(dept, "people", cats.get(dept, []))]))
        other = cats.get("Other", [])
        if other:
            tree.append(("Other", [("Other", "people", other)]))
        return tree

    def _org_person_widget(self, s):
        """Clickable name + dim detail line."""
        box = QVBoxLayout()
        box.setSpacing(0)
        name_lbl = QLabel(f"<b>{_staff_name(s)}</b>")
        name_lbl.setStyleSheet(
            "color: #4ea1ff; text-decoration: underline; font-size: 13px;")
        name_lbl.setCursor(Qt.PointingHandCursor)
        name_lbl.setToolTip("Open staff profile")
        name_lbl.mousePressEvent = \
            lambda e, staff=s: self._open_staff_detail(staff)
        box.addWidget(name_lbl)
        rating = _safe(lambda: getattr(s, "overall_rating", 0), 0) or 0
        sal = int(_safe(lambda: getattr(s, "salary", 0), 0) or 0)
        money = f" · {_fmt_salary(sal)}" if sal else ""
        dim = QLabel(
            f"{_staff_role_value(s)} · {rating} OVR{money}")
        dim.setStyleSheet("color: #8b95ab; font-size: 11px;")
        box.addWidget(dim)
        w = QWidget()
        w.setLayout(box)
        return w

    def _render_org(self):
        lay = self._org_lay
        self._clear(lay)
        title = QLabel(
            f"{self._team_name or 'Club'} Organizational Chart"
            .upper())
        title.setObjectName("section-header")
        lay.addWidget(title)

        for level, reports in self._org_tree():
            level_lbl = QLabel(level.upper())
            level_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: #8b95ab;"
                " margin-top: 8px; letter-spacing: 1px;")
            lay.addWidget(level_lbl)
            for role_lbl, kind, payload in reports:
                frame = QFrame()
                frame.setObjectName("tile")
                fl = QVBoxLayout(frame)
                fl.setContentsMargins(12, 8, 12, 8)
                fl.setSpacing(4)
                rl = QLabel(role_lbl)
                rl.setStyleSheet(
                    "font-size: 12px; font-weight: 700; color: #d6dbe6;")
                fl.addWidget(rl)
                if kind == "person":
                    if payload is None:
                        vacant = QLabel("Vacant")
                        vacant.setStyleSheet(
                            "color: #6b7488; font-style: italic;")
                        fl.addWidget(vacant)
                    else:
                        fl.addWidget(self._org_person_widget(payload))
                else:
                    people = payload or []
                    if not people:
                        fl.addWidget(QLabel("—"))
                    for s in people:
                        fl.addWidget(self._org_person_widget(s))
                lay.addWidget(frame)
        lay.addStretch()

    # --- Staff report tab ------------------------------------------------------
    def _render_report(self):
        lay = self._report_lay
        self._clear(lay)
        title = QLabel(
            f"{self._team_name or 'Club'} Staff Analysis Report"
            .upper())
        title.setObjectName("section-header")
        lay.addWidget(title)

        staff = self._staff
        total = len(staff)
        exp = sum(int(_safe(lambda: getattr(s, "experience", 0), 0) or 0)
                  for s in staff)
        rat = sum(int(_safe(lambda: getattr(s, "overall_rating", 0), 0) or 0)
                  for s in staff)
        tot_sal = sum(int(_safe(lambda: getattr(s, "salary", 0), 0) or 0)
                      for s in staff)
        avg_exp = round(exp / total, 1) if total else 0
        avg_rat = round(rat / total, 1) if total else 0

        summary = QHBoxLayout()
        summary.setSpacing(10)
        for val, lbl in [(str(total), "Total staff"),
                         (_fmt_money(tot_sal), "Total salary"),
                         (f"{avg_exp}y", "Avg experience"),
                         (str(avg_rat), "Avg rating")]:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            vl = QLabel(val)
            vl.setObjectName("tile-value")
            ll = QLabel(lbl)
            ll.setObjectName("tile-sub")
            cl.addWidget(vl)
            cl.addWidget(ll)
            summary.addWidget(card, 1)
        lay.addLayout(summary)

        cats = {}
        for s in staff:
            cats.setdefault(_staff_cat(s), []).append(s)
        for cat in [c for c, _ in _STAFF_CATEGORIES] + ["Other"]:
            members = cats.get(cat, [])
            if not members:
                continue
            members.sort(key=lambda m: int(
                _safe(lambda: getattr(m, "overall_rating", 0), 0) or 0),
                reverse=True)
            sal_sum = sum(int(_safe(lambda: getattr(s, "salary", 0), 0) or 0)
                          for s in members)
            rat_sum = sum(int(_safe(lambda: getattr(s, "overall_rating", 0),
                                    0) or 0) for s in members)
            avg = round(rat_sum / len(members), 1) if members else 0
            header = QLabel(
                f"{cat.upper()} DEPARTMENT  ({len(members)})"
                f"   avg {avg} · {_fmt_money(sal_sum)}")
            header.setObjectName("section-header")
            lay.addWidget(header)
            for s in members:
                years = int(_safe(lambda: getattr(s, "contract_years", 0),
                                  0) or 0)
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 2, 0, 2)
                nm = QLabel(f"<b>{_staff_name(s)}</b>")
                nm.setStyleSheet(
                    "color: #4ea1ff; text-decoration: underline;")
                nm.setCursor(Qt.PointingHandCursor)
                nm.mousePressEvent = \
                    lambda e, staff=s: self._open_staff_detail(staff)
                rl.addWidget(nm)
                detail = QLabel(
                    f"{_staff_role_value(s)} · "
                    f"{_safe(lambda: getattr(s, 'overall_rating', '?'), '?')} "
                    f"OVR · "
                    f"{_safe(lambda: getattr(s, 'experience', '?'), '?')}y · "
                    f"{_fmt_money(_safe(lambda: getattr(s, 'salary', 0), 0))} "
                    f"· {years}y left · {_staff_status(s)}")
                detail.setStyleSheet("color: #8b95ab; font-size: 12px;")
                rl.addWidget(detail, 1)
                lay.addWidget(row)

        expiring = [s for s in staff
                    if int(_safe(lambda: getattr(s, "contract_years", 99),
                                 99) or 99) <= 1]
        if expiring:
            header = QLabel("CONTRACT EXPIRATIONS")
            header.setObjectName("section-header")
            lay.addWidget(header)
            for s in expiring:
                years = int(_safe(lambda: getattr(s, "contract_years", 0),
                                  0) or 0)
                row = QLabel(
                    f"• <b>{_staff_name(s)}</b> "
                    f"<span style='color:#8b95ab'>{_staff_role_value(s)} — "
                    f"{years} year{'s' if years != 1 else ''} remaining</span>")
                lay.addWidget(row)
        lay.addStretch()

    # --- actions --------------------------------------------------------------
    def _user_team(self):
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            return getattr(gm, "user_team", None) or \
                getattr(self.game, "user_team", None)
        except Exception:
            return None

    def _release_staff(self, staff):
        """Release with severance -- mirrors web release_staff op."""
        name = _staff_name(staff)
        confirm = QMessageBox.question(
            self, "Release Staff",
            f"Are you sure you want to release {name}?\n"
            "This ends their contract immediately. "
            "Severance is owed on the remaining term.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        try:
            team = self._user_team()
            if team is None:
                QMessageBox.warning(self, "Release Staff",
                                    "No team loaded.")
                return
            live = list(getattr(team, "staff", []) or [])
            if staff not in live:
                QMessageBox.warning(self, "Release Staff",
                                    f"{name} is no longer on the staff.")
                return
            # Severance + trust shock (game_classes:4373), firing is never free
            try:
                from game_classes import process_staff_severance
                entry = process_staff_severance(team, staff)
                if entry:
                    print(f"[staff] release: severance "
                          f"${int(entry.get('amount', 0)):,} for {name}")
            except Exception:
                pass
            team.staff.remove(staff)
            try:
                add_news = getattr(self.main_window, "add_news", None) \
                    or getattr(self.game, "add_news", None)
                if callable(add_news):
                    add_news(f"{name} released by "
                             f"{getattr(team, 'team_name', 'your team')}.")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Release Staff",
                                f"Could not release: {e}")
            return
        self.refresh()

    def _staff_roles(self):
        """All reassignable roles: (enum_name, display_value)."""
        try:
            from game_classes import StaffRole
            return [(r.name, r.value) for r in StaffRole]
        except Exception:
            return []

    def _show_reassign(self, staff):
        roles = self._staff_roles()
        if not roles:
            QMessageBox.warning(self, "Reassign",
                                "Role list unavailable.")
            return
        dlg = _ReassignDialog(self, staff, roles)
        if dlg.exec() != QDialog.Accepted:
            return
        ok, err = self._do_reassign(staff, dlg.role_name)
        if not ok:
            QMessageBox.warning(self, "Reassign", err or
                                "Reassignment failed.")
        self.refresh()

    def _do_reassign(self, staff, role_name):
        """Apply reassignment with server-side validation parity."""
        try:
            from game_classes import Staff as _Staff, StaffRole as _SR
            try:
                new_role = _SR[role_name]
            except Exception:
                return False, f"Unknown role: {role_name}"
            if getattr(staff, "role", None) == new_role:
                return False, "Already in that role."
            team = self._user_team()
            if team is None:
                return False, "No team loaded."
            # Unique-role guard (GM / Head Coach)
            if _safe(lambda: _Staff.is_unique_role(new_role), False):
                conflict = [s for s in
                            list(getattr(team, "staff", []) or [])
                            if s is not staff
                            and getattr(s, "role", None) == new_role]
                if conflict:
                    cname = _staff_name(conflict[0])
                    return False, (
                        f"Team already has a {new_role.value}: {cname}. "
                        "Reassign or release them first.")
            staff.role = new_role
            return True, ""
        except Exception as e:
            return False, str(e)

    # --- Assistant coaches tab (TRACK C #6 port: assistant_coaches.py) ----
    # Engine reads -- everything below comes from the engine, nothing
    # invented. prowess: resume (attributes + pedigree). effect: right now
    # (results, mesh, shelf life move it via assistants_monthly_tick).
    # deltas: the real per-player development terms assistant_development_
    # deltas computes for U27 players, grouped by coach.

    def _assistant_engine(self):
        """Import the engine module (repo-root, same as free_agents.py)."""
        import assistant_coaches as aco
        return aco

    def _assistants_of(self):
        """Raw assistant staff objects on the user's team."""
        try:
            game = self.game
            gm = getattr(game, "game_manager", None) or game
            team = getattr(gm, "user_team", None) or \
                getattr(game, "user_team", None)
            if team is None:
                return None, []
            aco = self._assistant_engine()
            assistants = aco._assistants_of(team) or []
            return team, assistants
        except Exception:
            return None, []

    def _render_assistants(self):
        lay = self._asst_lay
        self._clear(lay)
        team, assistants = self._assistants_of()
        if team is None:
            lay.addWidget(self._asst_empty("No team loaded."))
            lay.addStretch()
            return
        try:
            aco = self._assistant_engine()
        except Exception:
            lay.addWidget(self._asst_empty(
                "Assistant-coach engine unavailable."))
            lay.addStretch()
            return
        if not assistants:
            lay.addWidget(self._asst_empty(
                "No assistant coaches on staff. Hire some in Staff "
                "Management — this tab will show what each one does."))
            lay.addStretch()
            return

        # Per-coach numbers, all from engine reads.
        rows = []
        for ac in assistants:
            try:
                spec = aco.assistant_specialty(ac)
                prow = float(aco.assistant_prowess(ac))
                eff = float(aco.assistant_effect(ac))
                icon = aco.is_franchise_icon(ac, team)
                rows.append({"staff": ac,
                             "name": _staff_name(ac),
                             "role": _staff_role_value(ac),
                             "specialty": spec,
                             "prowess": prow,
                             "effect": eff,
                             "icon": icon})
            except Exception:
                continue
        rows.sort(key=lambda r: r["effect"], reverse=True)

        # Development deltas, grouped per coach (real engine terms).
        deltas = self._assistant_deltas(team, assistants, aco)

        lay.addWidget(self._asst_overview_table(rows))
        for r in rows:
            lay.addWidget(self._asst_coach_card(r, deltas.get(
                r["name"], []), aco))
        lay.addStretch()

    def _asst_empty(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        return lbl

    def _assistant_deltas(self, team, assistants, aco):
        """{(coach name): [(player name, pts)]} from real engine deltas."""
        names = {_staff_name(ac) for ac in assistants}
        grouped = {}
        try:
            roster = list(getattr(team, "roster", None) or [])
        except Exception:
            roster = []
        for p in roster:
            try:
                if (getattr(p, "age", 99) or 99) > 26:
                    continue
            except Exception:
                continue
            try:
                terms = aco.assistant_development_deltas(p, team) or []
            except Exception:
                continue
            pname = _safe(
                lambda: getattr(p, "full_name", None), None) or \
                f"{_safe(lambda: getattr(p, 'first_name', ''), '')} " \
                f"{_safe(lambda: getattr(p, 'last_name', ''), '')}".strip() \
                or "?"
            for label, pts in terms:
                # Labels are "<Spec> assistant: <Name>" or
                # "Learning from <Name> (franchise icon)" -- match by name.
                for cname in names:
                    if cname and cname in label:
                        grouped.setdefault(cname, []).append(
                            (pname, float(pts), label))
                        break
        return grouped

    def _asst_form_text(self, drift):
        if abs(drift) >= 0.5:
            return f"{drift:+.0f}"
        return "on resume"

    def _asst_overview_table(self, rows):
        """Ranked comparison: coach / specialty / prowess / effectiveness /
        form. Ordered by current effectiveness."""
        card = QFrame()
        card.setObjectName("tile")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)
        head = QLabel("THE BENCH — RANKED BY EFFECTIVENESS")
        head.setObjectName("section-header")
        v.addWidget(head)
        note = QLabel("Assistants grow players at their position group "
                      "(defense / offense / goalie). Prowess is the resume; "
                      "effectiveness is right now — results, mesh and shelf "
                      "life move it month to month.")
        note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        note.setWordWrap(True)
        v.addWidget(note)

        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(
            ["Coach", "Specialty", "Prowess", "Effectiveness", "Form"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        for i, r in enumerate(rows):
            drift = r["effect"] - r["prowess"]
            vals = [r["name"], r["specialty"].title(),
                    f"{r['prowess']:.0f}", f"{r['effect']:.0f}",
                    self._asst_form_text(drift)]
            for j, t in enumerate(vals):
                item = QTableWidgetItem(t)
                if j >= 2:
                    item.setTextAlignment(Qt.AlignCenter)
                table.setItem(i, j, item)
            # Effectiveness cell tinted by the same thresholds as ratings.
            eff_item = table.item(i, 3)
            if eff_item is not None:
                eff_item.setForeground(QColor(_rating_color(r["effect"])))
        table.setMaximumHeight(34 * len(rows) + 36)
        v.addWidget(table)
        return card

    def _asst_coach_card(self, r, terms, aco):
        """One coach: effectiveness story + the actual dev deltas on the
        user's roster."""
        card = QFrame()
        card.setObjectName("tile")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)

        drift = r["effect"] - r["prowess"]
        head = QHBoxLayout()
        badge = QLabel(f"{r['effect']:.0f}")
        badge.setStyleSheet(
            f"font-size: 26px; font-weight: 900; "
            f"color: {_rating_color(r['effect'])}; min-width: 40px;")
        head.addWidget(badge)
        ncol = QVBoxLayout()
        ncol.setSpacing(0)
        title = f"{r['name']}  —  {r['specialty'].title()} assistant"
        if r["icon"]:
            title += "  ★ franchise icon"
        name_lbl = QLabel(title)
        name_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #ffffff;")
        ncol.addWidget(name_lbl)
        sub = (f"Prowess {r['prowess']:.0f} · Effectiveness "
               f"{r['effect']:.0f} · Form {self._asst_form_text(drift)} "
               f"· {r['role']}")
        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet("color: #8b95ab; font-size: 12px;")
        ncol.addWidget(sub_lbl)
        head.addLayout(ncol)
        head.addStretch()
        v.addLayout(head)

        if not terms:
            none = QLabel("No development terms on the current roster — "
                          "assistants move the needle only for U27 players "
                          "at their position group.")
            none.setStyleSheet("color: #6b7488; font-size: 12px;")
            none.setWordWrap(True)
            v.addWidget(none)
            return card

        total = sum(pts for _, pts, _ in terms)
        dhead = QLabel(
            f"DEVELOPMENT IMPACT — {len(terms)} player"
            f"{'s' if len(terms) != 1 else ''}, "
            f"{total:+.1f} total development points")
        dhead.setStyleSheet(
            "color: #8b95ab; font-size: 12px; font-weight: 700;")
        v.addWidget(dhead)
        table = QTableWidget(len(terms), 3)
        table.setHorizontalHeaderLabels(
            ["Player", "Development Δ", "Why"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i, (pname, pts, label) in enumerate(
                sorted(terms, key=lambda t: -abs(t[1]))):
            name_item = QTableWidgetItem(pname)
            delta_item = QTableWidgetItem(f"{pts:+.1f}")
            delta_item.setTextAlignment(Qt.AlignCenter)
            delta_item.setForeground(
                QColor("#4CAF50") if pts >= 0 else QColor("#F44336"))
            why = label.replace(r["name"], "").strip(" :()-") or label
            why_item = QTableWidgetItem(why or label)
            why_item.setToolTip(label)
            table.setItem(i, 0, name_item)
            table.setItem(i, 1, delta_item)
            table.setItem(i, 2, why_item)
        table.setMaximumHeight(30 * len(terms) + 36)
        v.addWidget(table)
        return card

    def _open_staff_detail(self, staff):
        """Open the staff detail screen for one staffer."""
        try:
            from .staff_detail import StaffDetailScreen
            mw = self.main_window
            screen = StaffDetailScreen(self.game, mw)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(screen)
            mw.stack.addWidget(scroll)
            mw.stack.setCurrentWidget(scroll)
            screen.set_staff(staff)
        except Exception as e:
            QMessageBox.warning(self, "Staff",
                                f"Could not open staff profile: {e}")


class _ReassignDialog(QDialog):
    """Reassign modal: role selector + inline error note."""

    def __init__(self, parent, staff, roles):
        super().__init__(parent)
        self.role_name = None
        name = _staff_name(staff)
        current_value = _staff_role_value(staff)
        current_name = _staff_role_name(staff)

        self.setWindowTitle(f"Reassign {name}")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        title = QLabel(f"Reassign {name}")
        title.setObjectName("dialog-title")
        lay.addWidget(title)
        sub = QLabel(f"Current role: {current_value}")
        sub.setStyleSheet("color: #8b95ab; font-size: 13px;")
        lay.addWidget(sub)

        lay.addWidget(QLabel("New role"))
        self._combo = QComboBox()
        for rname, rlabel in roles:
            self._combo.addItem(rlabel, rname)
            if rname == current_name or rlabel == current_value:
                idx = self._combo.count() - 1
                self._combo.model().item(idx).setEnabled(False)
        lay.addWidget(self._combo)

        self._note = QLabel("")
        self._note.setStyleSheet("color: #ff8a8a; font-size: 12px;")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("Confirm Reassignment")
        confirm.setObjectName("primary-btn")
        confirm.clicked.connect(self._on_confirm)
        row.addWidget(cancel)
        row.addStretch()
        row.addWidget(confirm)
        lay.addLayout(row)

    def _on_confirm(self):
        self.role_name = self._combo.currentData()
        self.accept()
