"""Staff detail screen: profile for one coach/staff member.

Header: name, role, department, Negotiate button. Facts grid with
bio/rating/contract facts. Detail tabs (role-conditional like the web UI):
Attributes, Standing, Personality, Record, Track Record, Analytics.

The Negotiate button opens the extension-negotiation modal: year term as
pill buttons (1-5, not a slider), salary line edit with a debounced live
acceptance-chance preview, Offer/Close buttons. Applies directly via
staff.negotiate_contract -- no HTTP round-trip.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QGridLayout, QDialog, QLineEdit, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from .base import BaseScreen
from .staff import (
    _safe, _staff_name, _staff_role_value, _staff_role_name,
    _fmt_money,
)
from ..widgets.attribute_bar import AttributeBar


# ----------------------------------------------------------------------
# Detail-tab builders (web_ui/screens/staff_detail.py _staff_tabs parity)
# ----------------------------------------------------------------------

_STAFF_ATTR_GROUPS = [
    ("Coaching", ["coaching_forwards", "coaching_defensemen",
                  "coaching_goalies", "attacking_coaching",
                  "defensive_coaching", "technical_coaching",
                  "mental_coaching"]),
    ("Tactical", ["tactical_knowledge", "game_preparation",
                  "match_preparation"]),
    ("Development", ["working_with_youngsters", "player_development",
                     "judging_player_ability", "judging_player_potential"]),
    ("Management", ["man_management", "motivating", "discipline",
                    "level_of_discipline", "media_handling"]),
    ("Personality", ["leadership", "determination", "adaptability"]),
]


def _staff_tabs(s):
    """Attribute/standing/personality/role-conditional tabs. Never raises."""
    tabs = {}
    # -- Attributes --
    attr_groups = []
    for label, attrs in _STAFF_ATTR_GROUPS:
        items = []
        for a in attrs:
            v = _safe(lambda: getattr(s, a, None))
            if isinstance(v, (int, float)) and v > 0:
                items.append({"name": a.replace("_", " ").title(),
                              "value": int(v)})
        if items:
            attr_groups.append({"label": label, "items": items})
    tabs["attributes"] = attr_groups
    # -- Standing --
    standing = []
    try:
        import reputation_system as _rs
        st = _rs.room_status(s)
        if isinstance(st, dict):
            level = st.get("level", "Secure")
            risk = float(st.get("risk", 0.0) or 0.0)
            standing.append({"text": "Room standing: %s (%.0f%% "
                                     "losing-the-room risk)"
                                     % (level, risk * 100),
                             "kind": "warn" if risk >= 0.45 else "info"})
    except Exception:
        pass
    try:
        if _staff_role_name(s) == "HEAD_COACH":
            standing.append({
                "text": "GM trust: %d/100" % int(
                    getattr(s, "gm_trust", 70) or 70),
                "kind": "info"})
    except Exception:
        pass
    try:
        eff = getattr(s, "assistant_effect", None)
        if eff:
            standing.append({"text": "Assistant effectiveness: %.0f"
                                     % float(eff), "kind": "ok"})
    except Exception:
        pass
    try:
        cn = getattr(s, "control_need", None)
        if cn is not None:
            standing.append({"text": "Control need: %.0f/100" % float(cn),
                             "kind": "info"})
    except Exception:
        pass
    tabs["standing"] = standing or [{"text": "No standing data recorded.",
                                     "kind": "info"}]
    # -- Personality --
    personality = {"style": "", "style_description": "", "lines": []}
    try:
        import reputation_system as _rs
        style = _rs.coach_style(s)
        personality["style"] = _safe(lambda: style.get("label", ""), "")
        personality["style_description"] = _safe(
            lambda: style.get("description", ""), "")
    except Exception:
        pass
    ambition_text = {
        "stanley_cup": "Burning to win the Stanley Cup.",
        "climb": "Climbing -- wants a bigger chair.",
        "developer": "Lives to develop young players.",
        "hometown": "Dreams of coaching his hometown team.",
        "lifer": "A lifer -- happy wherever the game takes him.",
    }.get(str(getattr(s, "ambition", "") or ""), "")
    if ambition_text:
        personality["lines"].append("Ambition: " + ambition_text)
    fav = _safe(lambda: getattr(s, "favorite_team", None))
    if fav:
        personality["lines"].append("Boyhood team: " + str(fav))
    try:
        cn = float(getattr(s, "control_need", 50))
        personality["lines"].append(
            "Runs the room his way -- needs full control." if cn >= 75
            else "Comfortable sharing the room with his staff." if cn >= 45
            else "Collaborative -- delegates freely to assistants.")
    except Exception:
        pass
    try:
        mot = float(getattr(s, "motivating", 50))
        disc = float(getattr(s, "discipline", 50))
        if mot >= 75 and disc >= 75:
            personality["lines"].append(
                "Demanding and inspiring in equal measure.")
        elif mot >= 75 and disc < 60:
            personality["lines"].append("An arm-around-the-shoulder motivator.")
        elif disc >= 75 and mot < 60:
            personality["lines"].append("A demanding disciplinarian.")
        elif mot < 45 and disc < 45:
            personality["lines"].append(
                "Hands-off -- lets the leaders run the room.")
    except Exception:
        pass
    tabs["personality"] = personality
    # -- role-conditional tabs --
    try:
        from game_classes import StaffRole as _SR
        role = getattr(s, "role", None)
        scout_roles = {_SR.HEAD_SCOUT, _SR.PROFESSIONAL_SCOUT,
                       _SR.AMATEUR_SCOUT, _SR.EUROPEAN_SCOUT}
        is_scout = role in scout_roles
        is_director = role == _SR.ANALYTICS_DIRECTOR
        try:
            import coach_records as _crw
            is_coach = _crw.is_coaching_role(s)
        except Exception:
            is_coach = False
    except Exception:
        is_scout = is_director = is_coach = False
    if is_coach:
        tabs["record"] = _coaching_record_tab(s)
    if is_scout:
        tabs["track_record"] = _track_record_tab(s)
    if is_director:
        tabs["analytics"] = _analytics_tab(s)
    return tabs


def _coaching_record_tab(s):
    """Record page: year-by-year W-L-OTL, playoff results, honours."""
    out = {"totals": "", "honours": [], "seasons": []}
    try:
        import coach_records as _cr
        record = list(getattr(s, "career_record", None) or [])
        t = _cr.career_totals(record)
        out["totals"] = ("%d-%d-%d (%.3f) over %d seasons · %d Stanley Cups "
                         "· %d Jack Adams" % (
                             t["w"], t["l"], t["otl"], t["win_pct"],
                             t["seasons"], t["cups"], t["adams"]))
        for e in reversed(record):
            if not isinstance(e, dict):
                continue
            out["seasons"].append({
                "season": str(e.get("season", "?")),
                "team": str(e.get("team", "?"))[:26],
                "role": str(e.get("role", "?"))[:18],
                "wl": "%s-%s-%s" % (e.get("w", 0), e.get("l", 0),
                                    e.get("otl", 0)),
                "playoffs": str(e.get("playoff", "?"))[:28],
                "cup": e.get("playoff") == "Won Stanley Cup",
                "adams": bool(e.get("jack_adams")),
            })
    except Exception:
        pass
    try:
        import accolades as _acc
        for label, years in _acc.group_accolades(s) or []:
            out["honours"].append("%s Winner: %s" % (label, ", ".join(years)))
    except Exception:
        pass
    return out


def _track_record_tab(s):
    """Track Record page: graded calls, hit rate, recent reads."""
    out = {"record_line": "", "history": []}
    try:
        import analytics_scouting as _as
        _as.ensure_analytics_fields(s)
        out["record_line"] = str(_as.scout_record_line(s) or "")
        hist = list(reversed(list(getattr(s, "tip_history", []) or [])))[-8:]
        for h in hist:
            try:
                res = h.get("result", "?")
                out["history"].append({
                    "mark": ("hit" if res == "hit" else "miss"
                             if res == "miss" else "pending"),
                    "player": h.get("player_name", h.get("player", "?")),
                    "kind": h.get("kind", ""),
                    "date": h.get("date", ""),
                })
            except Exception:
                continue
    except Exception:
        pass
    return out


def _analytics_tab(s):
    """Analytics page: what the director's department does for the club."""
    out = {"quality": 0, "tier": "", "club_quality": None,
           "refresh_days": None, "note": ""}
    try:
        import analytics_scouting as _as
        import advanced_metrics as _am
        personal = _as.analytics_director_quality(s)
        tier = _as.department_tier_label(personal)
        out.update(quality=int(personal), tier=str(tier))
        out["refresh_days"] = int(_am.department_refresh_days(personal))
        out["note"] = ("A better department sharpens the picture, never the "
                       "players: tighter confidence intervals on modeled "
                       "metrics, fresher model snapshots, less visible "
                       "noise. Box-score facts stay exact at every tier.")
    except Exception:
        pass
    return out


def _staff_offer_chance(game, s, salary):
    """Acceptance-chance estimate (desktop StaffContractView parity)."""
    try:
        from game_classes import staff_market_ask, to_100_scale
        import reputation_system as _rs
        gm = getattr(game, "game_manager", None) or game
        team = getattr(gm, "user_team", None) or \
            getattr(game, "user_team", None)
        ask = staff_market_ask(s)
        salary_mult = salary / max(1, ask)
        try:
            rating = to_100_scale(getattr(s, "overall_rating", 60) or 60)
        except Exception:
            rating = 60
        prestige = _safe(lambda: getattr(team, "prestige", 50), 50)
        base = (0.45 + (salary_mult - 1.0) * 1.4
                + (prestige - 50) / 400 - (rating - 60) / 600)
        try:
            base += _rs.gm_staff_accept_delta(team) if team else 0
        except Exception:
            pass
        return max(0.05, min(0.98, base))
    except Exception:
        return 0.5


def _negotiation_preview(game, s):
    """Demands + budget preview data (api_staff_negotiate_preview parity)."""
    gm = getattr(game, "game_manager", None) or game
    team = getattr(gm, "user_team", None) or getattr(game, "user_team", None)
    salary = int(_safe(lambda: getattr(s, "salary", 0), 0) or 0)
    rep = float(_safe(lambda: getattr(s, "reputation", 10), 10) or 10)
    ask_min = int(salary * (0.8 + rep / 10 * 0.1))
    ask_max = int(salary * (1.2 + rep / 10 * 0.2))
    try:
        from game_classes import staff_market_ask
        market_ask = int(staff_market_ask(s))
    except Exception:
        market_ask = ask_min
    budget = None
    if team is not None:
        budget = _safe(lambda: team.staff_budget_remaining(), None)
    return {
        "current_salary": salary,
        "current_years": int(
            _safe(lambda: getattr(s, "contract_years", 0), 0) or 0),
        "ask_min": ask_min, "ask_max": ask_max, "market_ask": market_ask,
        "budget_remaining": budget,
    }


# ----------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------

class StaffDetailScreen(BaseScreen):
    """Profile for one staff member."""

    title = "Staff"

    def __init__(self, game, main_window, parent=None):
        self._staff = None
        self._tabs = None
        super().__init__(game, main_window, parent)

    def set_staff(self, staff):
        """Set the staff member to display and reload."""
        self._staff = staff
        self.refresh()

    # --- build -----------------------------------------------------------
    def _build_body(self):
        self._name_lbl = QLabel("—")
        self._name_lbl.setStyleSheet(
            "font-size: 28px; font-weight: 900; color: #ffffff;")
        self._role_lbl = QLabel("—")
        self._role_lbl.setStyleSheet(
            "font-size: 15px; color: #8b95ab;")
        self._layout.addWidget(self._name_lbl)
        self._layout.addWidget(self._role_lbl)

        btn_row = QHBoxLayout()
        self._neg_btn = QPushButton("Negotiate Contract")
        self._neg_btn.setObjectName("primary-btn")
        self._neg_btn.setCursor(Qt.PointingHandCursor)
        self._neg_btn.clicked.connect(self._show_negotiate)
        btn_row.addWidget(self._neg_btn)
        btn_row.addStretch()
        self._layout.addLayout(btn_row)

        self._facts_card = QFrame()
        self._facts_card.setObjectName("tile")
        self._facts_grid = QGridLayout(self._facts_card)
        self._facts_grid.setContentsMargins(14, 10, 14, 10)
        self._facts_grid.setSpacing(8)
        self._layout.addWidget(self._facts_card)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("sd-tabs")
        self._layout.addWidget(self._tabs, 1)

    # --- refresh ----------------------------------------------------------
    def refresh(self):
        s = self._staff
        if s is None:
            return
        name = _staff_name(s)
        dept = _safe(lambda: getattr(s, "department", ""), "") or ""
        role_line = " · ".join(x for x in
                               [_staff_role_value(s), dept] if x)
        self._name_lbl.setText(name)
        self._role_lbl.setText(role_line or "—")

        self._render_facts(s)
        self._render_tabs(s)

    def _render_facts(self, s):
        grid = self._facts_grid
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        rating = _safe(lambda: getattr(s, "overall_rating", 0), 0) or 0
        cy = _safe(lambda: getattr(s, "contract_years", 0), 0) or 0
        facts = [
            ("Rating", f"{rating} / 100" if rating else "—"),
            ("Age", str(_safe(lambda: getattr(s, "age", 0), 0) or "—")),
            ("Nationality",
             _safe(lambda: getattr(s, "nationality", ""), "") or "—"),
            ("Experience",
             f"{_safe(lambda: getattr(s, 'experience', 0), 0)} yrs"),
            ("Years with team",
             str(_safe(lambda: getattr(s, "years_with_team", 0), 0) or "—")),
            ("Salary", _fmt_money(_safe(lambda: getattr(s, "salary", 0), 0))),
            ("Contract", f"{cy} yr{'s' if cy != 1 else ''}" if cy else "—"),
            ("Morale", str(_safe(lambda: getattr(s, "morale", 0), 0) or "—")),
            ("Specialty", _safe(lambda: getattr(s, "specialty", ""), "")
             or "—"),
            ("Reputation", _safe(lambda: getattr(s, "reputation", ""), "")
             or "—"),
        ]
        for i, (k, v) in enumerate(facts):
            kl = QLabel(k)
            kl.setStyleSheet("color: #8b95ab; font-size: 12px;")
            vl = QLabel(str(v))
            vl.setStyleSheet(
                "color: #ffffff; font-size: 14px; font-weight: 700;")
            grid.addWidget(kl, i // 2, (i % 2) * 2)
            grid.addWidget(vl, i // 2, (i % 2) * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

    def _render_tabs(self, s):
        self._tabs.clear()
        tabs = _staff_tabs(s)
        order = ["attributes", "standing", "personality", "record",
                 "track_record", "analytics"]
        labels = {"attributes": "Attributes", "standing": "Standing",
                  "personality": "Personality", "record": "Record",
                  "track_record": "Track Record", "analytics": "Analytics"}
        for k in order:
            if k not in tabs:
                continue
            page = self._render_tab_page(k, tabs[k])
            self._tabs.addTab(page, labels[k])

    def _card(self):
        card = QFrame()
        card.setObjectName("tile")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        return card, lay

    def _render_tab_page(self, key, data):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignTop)
        lay.setSpacing(12)
        if key == "attributes":
            if not data:
                lay.addWidget(QLabel("No attribute data."))
            for group in data:
                card, cl = self._card()
                h = QLabel(group["label"])
                h.setStyleSheet(
                    "font-size: 14px; font-weight: 800; color: #ffffff;")
                cl.addWidget(h)
                for it in group["items"]:
                    cl.addWidget(AttributeBar(it["name"], it["value"]))
                lay.addWidget(card)
        elif key == "standing":
            card, cl = self._card()
            colors = {"ok": "#4CAF50", "warn": "#ff8a8a", "info": "#8b95ab"}
            for line in data:
                lbl = QLabel(f"•  {line['text']}")
                lbl.setStyleSheet(
                    f"color: {colors.get(line.get('kind'), '#8b95ab')};"
                    " font-size: 13px;")
                lbl.setWordWrap(True)
                cl.addWidget(lbl)
            lay.addWidget(card)
        elif key == "personality":
            card, cl = self._card()
            if data.get("style"):
                st = QLabel(data["style"])
                st.setStyleSheet(
                    "font-size: 16px; font-weight: 800; color: #ffffff;")
                cl.addWidget(st)
            if data.get("style_description"):
                sd = QLabel(data["style_description"])
                sd.setStyleSheet("color: #8b95ab; font-size: 13px;")
                sd.setWordWrap(True)
                cl.addWidget(sd)
            for line in data.get("lines", []):
                ll = QLabel(f"•  {line}")
                ll.setStyleSheet("color: #8b95ab; font-size: 13px;")
                ll.setWordWrap(True)
                cl.addWidget(ll)
            lay.addWidget(card)
        elif key == "record":
            card, cl = self._card()
            h = QLabel("Career Totals")
            h.setStyleSheet(
                "font-size: 14px; font-weight: 800; color: #ffffff;")
            cl.addWidget(h)
            totals = data.get("totals") or \
                ("No completed seasons on record yet — the first entry "
                 "lands at season rollover.")
            tl = QLabel(totals)
            tl.setWordWrap(True)
            tl.setStyleSheet("font-size: 13px; color: #d6dbe6;")
            cl.addWidget(tl)
            lay.addWidget(card)

            card2, cl2 = self._card()
            hh = QLabel("Honours")
            hh.setStyleSheet(
                "font-size: 14px; font-weight: 800; color: #ffffff;")
            cl2.addWidget(hh)
            honours = data.get("honours", [])
            if honours:
                for hon in honours:
                    cl2.addWidget(QLabel(f"🏆  {hon}"))
            else:
                dim = QLabel("No honours banked yet.")
                dim.setStyleSheet("color: #8b95ab;")
                cl2.addWidget(dim)
            lay.addWidget(card2)

            seasons = data.get("seasons", [])
            if seasons:
                card3, cl3 = self._card()
                sh = QLabel("Season by Season")
                sh.setStyleSheet(
                    "font-size: 14px; font-weight: 800; color: #ffffff;")
                cl3.addWidget(sh)
                table = QTableWidget()
                table.setColumnCount(6)
                table.setHorizontalHeaderLabels(
                    ["Season", "Team", "Role", "W-L-OTL", "Playoffs", ""])
                table.setRowCount(len(seasons))
                table.verticalHeader().setVisible(False)
                table.setEditTriggers(QTableWidget.NoEditTriggers)
                table.setAlternatingRowColors(True)
                table.horizontalHeader().setSectionResizeMode(
                    QHeaderView.Stretch)
                gold = QColor("#3d3410")
                for r, se in enumerate(seasons):
                    vals = [se["season"], se["team"], se["role"],
                            se["wl"], se["playoffs"],
                            ("🏆" if se["cup"] else "")
                            + (" 🎖" if se["adams"] else "")]
                    for c, val in enumerate(vals):
                        item = QTableWidgetItem(str(val))
                        if se["cup"] or se["adams"]:
                            item.setBackground(gold)
                            if se["cup"] or se["adams"]:
                                item.setForeground(QColor("#ffd75e"))
                        table.setItem(r, c, item)
                cl3.addWidget(table)
                lay.addWidget(card3)
        elif key == "track_record":
            card, cl = self._card()
            h = QLabel("Scout Track Record")
            h.setStyleSheet(
                "font-size: 14px; font-weight: 800; color: #ffffff;")
            cl.addWidget(h)
            rl = QLabel(data.get("record_line") or
                        "No graded calls yet — a blank ledger.")
            rl.setWordWrap(True)
            rl.setStyleSheet("font-weight: 700; font-size: 13px;")
            cl.addWidget(rl)
            note = QLabel(
                "Every read this scout files is graded against what happens "
                "next. A validated breakout banks the club; a miss plants "
                "doubt — and clubs fire scouts under 40% on 10+ graded "
                "calls.")
            note.setWordWrap(True)
            note.setStyleSheet("color: #8b95ab; font-size: 12px;")
            cl.addWidget(note)
            lay.addWidget(card)
            history = data.get("history", [])
            if history:
                card2, cl2 = self._card()
                hh = QLabel("Recent Reads")
                hh.setStyleSheet(
                    "font-size: 14px; font-weight: 800; color: #ffffff;")
                cl2.addWidget(hh)
                mark_styles = {"hit": ("✓", "#4CAF50"),
                               "miss": ("✗", "#ff8a8a"),
                               "pending": ("·", "#8b95ab")}
                for hst in history:
                    mark, color = mark_styles.get(hst["mark"],
                                                  ("·", "#8b95ab"))
                    row = QLabel(
                        f"<span style='color:{color}; font-weight:800; "
                        f"font-size:16px;'>{mark}</span>  {hst['player']} — "
                        f"<span style='color:#8b95ab'>{hst['kind']} read, "
                        f"{hst['date']}</span>")
                    cl2.addWidget(row)
                lay.addWidget(card2)
        elif key == "analytics":
            card, cl = self._card()
            h = QLabel("Analytics Department")
            h.setStyleSheet(
                "font-size: 14px; font-weight: 800; color: #ffffff;")
            cl.addWidget(h)
            big = QLabel(f"{data.get('quality', 0)}/100 — "
                         f"{data.get('tier', '')}")
            big.setStyleSheet(
                "font-size: 20px; font-weight: 900; color: #ffffff;")
            cl.addWidget(big)
            cq = data.get("club_quality")
            rd = data.get("refresh_days")
            if cq is not None:
                ql = QLabel(
                    f"Club department quality: <b>{cq}/100</b> — models "
                    f"rebuild every {rd} days.")
            else:
                ql = QLabel(
                    f"Would run your department at "
                    f"<b>{data.get('quality', 0)}/100</b> — models rebuild "
                    f"every {rd} days.")
            ql.setStyleSheet("font-size: 13px; color: #d6dbe6;")
            cl.addWidget(ql)
            note = QLabel(data.get("note", ""))
            note.setWordWrap(True)
            note.setStyleSheet("color: #8b95ab; font-size: 12px;")
            cl.addWidget(note)
            lay.addWidget(card)
        lay.addStretch()
        return page

    # --- negotiation ---------------------------------------------------------
    def _show_negotiate(self):
        if self._staff is None:
            return
        dlg = NegotiateDialog(self, self.game, self._staff)
        dlg.exec()
        self.refresh()


# ----------------------------------------------------------------------
# Negotiation modal
# ----------------------------------------------------------------------

class NegotiateDialog(QDialog):
    """Extension negotiation: year pills + salary field + live chance.

    Year term is pill buttons (1-5, default 2) -- deliberately not a slider
    (web staff_detail parity). The acceptance-chance preview recomputes on
    salary text change, debounced 350ms via QTimer.
    """

    def __init__(self, parent, game, staff):
        super().__init__(parent)
        self.game = game
        self.staff = staff
        self.years = 2

        name = _staff_name(staff)
        self.setWindowTitle(f"Negotiate — {name}")
        self.setMinimumWidth(520)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        title = QLabel(f"Negotiate — {name}")
        title.setObjectName("dialog-title")
        lay.addWidget(title)

        self._ask_lbl = QLabel("")
        self._ask_lbl.setStyleSheet("color: #8b95ab; font-size: 13px;")
        self._ask_lbl.setWordWrap(True)
        lay.addWidget(self._ask_lbl)
        self._budget_lbl = QLabel("")
        self._budget_lbl.setStyleSheet("color: #8b95ab; font-size: 12px;")
        self._budget_lbl.setWordWrap(True)
        lay.addWidget(self._budget_lbl)

        # Contract length: pill buttons 1-5
        lay.addWidget(QLabel("Contract length"))
        pill_row = QHBoxLayout()
        pill_row.setSpacing(8)
        self._pill_group = QButtonGroup(self)
        self._pill_group.setExclusive(True)
        self._pills = {}
        for v in range(1, 6):
            btn = QPushButton(str(v))
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedWidth(56)
            btn.clicked.connect(
                lambda _=False, val=v: self._set_years(val))
            self._pill_group.addButton(btn)
            self._pills[v] = btn
            pill_row.addWidget(btn)
        pill_row.addStretch()
        lay.addLayout(pill_row)
        self._set_years(2)

        # Salary offer
        lay.addWidget(QLabel("Salary offer ($ / year)"))
        self._salary = QLineEdit()
        self._salary.setPlaceholderText("e.g. 1,250,000")
        self._salary.textChanged.connect(self._on_salary_changed)
        lay.addWidget(self._salary)

        self._chance_lbl = QLabel("")
        self._chance_lbl.setStyleSheet("font-size: 14px;")
        lay.addWidget(self._chance_lbl)
        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet("font-size: 13px;")
        self._result_lbl.setWordWrap(True)
        lay.addWidget(self._result_lbl)

        row = QHBoxLayout()
        self._offer_btn = QPushButton("Make Offer")
        self._offer_btn.setObjectName("primary-btn")
        self._offer_btn.setCursor(Qt.PointingHandCursor)
        self._offer_btn.clicked.connect(self._make_offer)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        row.addWidget(self._offer_btn)
        row.addStretch()
        row.addWidget(close_btn)
        lay.addLayout(row)

        # Debounce timer for the live chance preview
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._update_chance)

        self._load_preview()

    # --- preview data ----------------------------------------------------
    def _load_preview(self):
        try:
            p = _negotiation_preview(self.game, self.staff)
        except Exception as e:
            self._ask_lbl.setText(f"Could not load demands: {e}")
            return
        self._ask_lbl.setText(
            f"Current: {_fmt_money(p['current_salary'])}/yr x "
            f"{p['current_years']}y. Asking window: "
            f"{_fmt_money(p['ask_min'])}–{_fmt_money(p['ask_max'])}/yr "
            f"(market ask {_fmt_money(p['market_ask'])}/yr). "
            f"Demands + your offer + his temperament decide the roll.")
        if p["budget_remaining"] is not None:
            self._budget_lbl.setText(
                f"Club staff budget available: "
                f"{_fmt_money(p['budget_remaining'])}/yr.")
        if not self._salary.text().strip():
            self._salary.setText(f"{p['market_ask']:,}")
        self._update_chance()

    # --- pills -----------------------------------------------------------
    def _set_years(self, v):
        self.years = v
        for val, btn in self._pills.items():
            btn.setChecked(val == v)
            btn.setStyleSheet(
                "QPushButton { border: 1px solid #2a3654; border-radius: 14px;"
                " padding: 8px 0; color: #d6dbe6; background: #141b2e; }"
                "QPushButton:checked { background: #3B82F6; color: #ffffff;"
                " border-color: #3B82F6; font-weight: 800; }")

    # --- live chance preview ----------------------------------------------
    def _parse_offer(self):
        raw = self._salary.text() or ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        try:
            v = int(digits)
        except ValueError:
            return 0
        return v if v > 0 else 0

    def _on_salary_changed(self):
        self._debounce.stop()
        self._debounce.start()

    def _update_chance(self):
        offer = self._parse_offer()
        if not offer:
            self._chance_lbl.setText("Enter an offer amount.")
            return
        chance = _staff_offer_chance(self.game, self.staff, offer)
        color = ("#4CAF50" if chance >= 0.75 else
                 "#FFC107" if chance >= 0.45 else "#F44336")
        self._chance_lbl.setText(
            f"Estimated acceptance chance: "
            f"<span style='color:{color}; font-weight:800;'>"
            f"{round(chance * 100)}%</span>")

    # --- offer ------------------------------------------------------------
    def _make_offer(self):
        offer = self._parse_offer()
        if not offer:
            self._result_lbl.setText("Enter an offer amount.")
            return
        if not (1 <= self.years <= 5):
            self._result_lbl.setText("Pick 1–5 years.")
            return
        self._offer_btn.setEnabled(False)
        self._result_lbl.setText("Making offer…")
        name = _staff_name(self.staff)
        try:
            accepted = bool(self.staff.negotiate_contract(offer, self.years))
            if accepted:
                # Apply the new terms (negotiate_staff_contract op parity)
                try:
                    self.staff.salary = offer
                    self.staff.contract_years = self.years
                except Exception:
                    pass
                # Inbox confirmation (web op parity)
                try:
                    from game_classes import EmailMessage
                    from datetime import date as _date
                    send = getattr(self.game, "send_email_to_user", None)
                    if callable(send):
                        send(EmailMessage(
                            sender="System", sender_type="System",
                            date_sent=_date.today(),
                            category="Contracts", priority=2,
                            subject=f"Staff re-signed: {name}",
                            content=(f"Contract renegotiated with {name} "
                                     f"(${offer:,}/yr x {self.years}y).")))
                except Exception:
                    pass
                self._result_lbl.setText(
                    f"<span style='color:#4CAF50; font-weight:700;'>"
                    f"{name} signed: ${offer:,}/yr x {self.years} "
                    f"year{'s' if self.years != 1 else ''}.</span>"
                    f"<br><span style='color:#8b95ab'>Confirmed in your "
                    f"inbox.</span>")
            else:
                self._result_lbl.setText(
                    f"<span style='color:#ff8a8a; font-weight:700;'>"
                    f"{name} turned the offer down. He wants more -- or "
                    f"is testing you.</span>")
        except Exception as e:
            self._result_lbl.setText(
                f"<span style='color:#ff8a8a;'>Offer failed: {e}</span>")
        finally:
            self._offer_btn.setEnabled(True)
