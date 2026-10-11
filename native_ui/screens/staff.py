"""Staff screen: coaches & management.

Three tabs (lazy-loaded, one at a time): Staff list, Org Chart, Staff Report.
Per-staff actions: Negotiate (multi-round contract negotiation with
persist/resume chain), Release (confirm dialog mentioning severance),
Reassign (modal dialog with role selector), Declare Rival (personal
rivalry via the reputation system). Staff are grouped by role;
names click through to StaffDetailScreen.

Calls the game object directly -- no HTTP, no serialization.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QScrollArea, QDialog, QComboBox, QMessageBox, QGridLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QSpinBox, QFormLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen
from native_ui.safe import safe_call

# Backwards-compat alias: staff_detail.py does
# `from .staff import _safe, ...`. It now points at the shared helper
# (no duplicated wrapper); new code must call
# safe_call(..., context=...) directly.
_safe = safe_call


# ----------------------------------------------------------------------
# Helpers (web_ui/screens/staff.py + staff_detail.py parity)
# ----------------------------------------------------------------------

def _staff_name(s):
    name = safe_call(lambda: getattr(s, "full_name", None), None, context="staff full_name")
    if name:
        return name
    fn = safe_call(lambda: getattr(s, "first_name", ""), "", context="staff first_name") or ""
    ln = safe_call(lambda: getattr(s, "last_name", ""), "", context="staff last_name") or ""
    return f"{fn} {ln}".strip() or "?"


def _staff_role_value(s):
    """Display role string, e.g. 'Head Coach'."""
    role = getattr(s, "role", None)
    if role is None:
        return "Staff"
    return safe_call(lambda: getattr(role, "value", None) or str(role), "Staff", context="staff role value")


def _staff_role_name(s):
    """Enum name of the role, e.g. 'HEAD_COACH'."""
    return str(safe_call(lambda: getattr(getattr(s, "role", None), "name", ""),
                     "", context="staff role name") or "")


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


# ---------------------------------------------------------------------------
# Negotiate-chain persist/resume (D-16 port of mainline's
# staff_management_window.py "Gating: staff negotiate-chain persist/resume").
#
# Mainline keeps the chain in app.pending_sessions ("staff_negotiate_chain",
# JSON-safe: staff IDs + result strings only): write-through on start and
# every advance; navigating away mid-step parks it (resume question on
# return, dismiss = keep parked); a parked chain survives save/load and
# resumes via its named resolver with stale IDs skipped honestly.
#
# Native port: the same session schema lives on the game manager's
# pending_sessions dict (the object GameSaveManager wraps). Root-cause
# note: GameSaveManager's session serializer/restorer read
# self.app.pending_sessions, but GameSaveManager.app was never assigned
# anywhere in mainline, so the whitelisted chain kind could never
# actually survive save/load there. Commit 872f6d7 fixed this at the
# source by wiring GameSaveManager.app at construction in
# save_load_system.py (preferring the GUI-app back-reference the game
# manager carries, else falling back to the wrapped game manager
# itself -- the session owner). The two in-file repairs below are now
# harmless no-op fallbacks, kept for safety:
#   _ensure_save_bridge() assigns save_manager.app to the session owner
#     (only when unset) on every chain write;
#   _install_pending_session_repair() runs at import and falls back to
#     self.game_manager inside both save/load functions, so a fresh
#     process that loads a save (no staff interaction yet) still
#     restores the chain. Both short-circuit when app is already
#     assigned, which is now always the case.
#
# The in-progress multi-round step is part of the session ("step"):
# round number, offer history, half-typed draft offer, and the staffer's
# demands snapshot -- all JSON-safe, so a mid-negotiation save/load
# resumes at the exact round with the exact state.
# ---------------------------------------------------------------------------
_CHAIN_SESSION_ID = "staff_negotiate_chain"
_CHAIN_KIND = "staff_negotiate_chain"


def _chain_owner(game):
    """Object owning pending_sessions (the one the save manager wraps)."""
    try:
        return getattr(game, "game_manager", None) or game
    except Exception:
        return game


def _chain_store(game):
    """The pending_sessions dict (created on demand). Never raises."""
    owner = _chain_owner(game)
    try:
        store = getattr(owner, "pending_sessions", None)
        if not isinstance(store, dict):
            store = {}
            owner.pending_sessions = store
        return store
    except Exception:
        return {}


def _ensure_save_bridge(game):
    """Point GameSaveManager.app at the session owner so the whitelisted
    chain kind actually survives save/load (mainline's intended design;
    its wiring was dead). Only assigns when unset. Never raises."""
    try:
        owner = _chain_owner(game)
        sm = getattr(owner, "save_manager", None)
        if sm is None:
            return
        if getattr(sm, "app", None) is None:
            sm.app = owner
    except Exception:
        pass


def _chain_session(game):
    """The live chain session dict, or None. Never raises."""
    try:
        sess = _chain_store(game).get(_CHAIN_SESSION_ID)
        return sess if isinstance(sess, dict) else None
    except Exception:
        return None


def _drop_chain(game):
    """Consume the chain session (exactly-once completion/discard)."""
    try:
        _chain_store(game).pop(_CHAIN_SESSION_ID, None)
    except Exception:
        pass


def _touch_chain(game, **fields):
    """Write-through update of the chain session (creates it if missing).
    Every value must stay JSON-safe. Never raises."""
    try:
        _ensure_save_bridge(game)
        store = _chain_store(game)
        sess = store.get(_CHAIN_SESSION_ID)
        if not isinstance(sess, dict):
            sess = {"kind": _CHAIN_KIND}
            store[_CHAIN_SESSION_ID] = sess
        sess["kind"] = _CHAIN_KIND
        for key, value in fields.items():
            sess[key] = value
        return sess
    except Exception:
        return None


class _StaffNegotiationDialog(QDialog):
    """Multi-round staff contract negotiation (D-16 port of mainline's
    StaffContractView renegotiate flow: demands + offer + accept/reject
    roll via staff.negotiate_contract()).

    step: the persisted in-progress step dict (mutated in place):
      {staff_id, round, offers:[{salary, years, result}], draft_salary,
       draft_years, demands:{salary, years}}
    Every keystroke writes through via on_draft; every offer via on_offer;
    closing without agreement parks via on_walk_away (mainline: cancel
    keeps the session for resume).
    """

    def __init__(self, parent, staff, step, on_draft, on_offer,
                 on_walk_away):
        super().__init__(parent)
        self._staff = staff
        self._step = step
        self._on_draft = on_draft
        self._on_offer = on_offer
        self._on_walk_away = on_walk_away
        self._resolved = False
        self._walked_away = False

        name = _staff_name(staff)
        self.setWindowTitle(f"Contract Negotiation \u2014 {name}")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        title = QLabel(f"Negotiating with {name}")
        title.setObjectName("dialog-title")
        lay.addWidget(title)
        self._round_lbl = QLabel("")
        self._round_lbl.setStyleSheet("color: #8b95ab; font-size: 13px;")
        lay.addWidget(self._round_lbl)

        # Demands card (the staffer's stance -- snapshot, survives reload).
        demands = step.get("demands") or {}
        try:
            d_sal = int(demands.get("salary") or 0)
        except Exception:
            d_sal = 0
        try:
            d_yrs = int(demands.get("years") or 0)
        except Exception:
            d_yrs = 0
        dcard = QFrame()
        dcard.setObjectName("tile")
        dl = QVBoxLayout(dcard)
        dl.setContentsMargins(12, 8, 12, 8)
        dl.setSpacing(2)
        dh = QLabel("Current Demands")
        dh.setStyleSheet("font-size: 12px; font-weight: 700;")
        dl.addWidget(dh)
        dd = QLabel(f"Asking salary: {_fmt_money(d_sal)}/yr \u00b7 "
                    f"Contract length: {d_yrs or '?'} year"
                    f"{'s' if d_yrs != 1 else ''}")
        dd.setStyleSheet("color: #8b95ab; font-size: 12px;")
        dl.addWidget(dd)
        lay.addWidget(dcard)

        # Offer history (this negotiation's rounds).
        self._history_lbl = QLabel("")
        self._history_lbl.setStyleSheet(
            "color: #8b95ab; font-size: 12px;")
        self._history_lbl.setWordWrap(True)
        lay.addWidget(self._history_lbl)

        # Offer frame.
        form = QFormLayout()
        form.setSpacing(8)
        self._salary_edit = QLineEdit(str(step.get("draft_salary") or ""))
        self._salary_edit.setPlaceholderText("e.g. 850000")
        self._salary_edit.textChanged.connect(self._emit_draft)
        form.addRow("Salary offer ($ / year):", self._salary_edit)
        self._years_spin = QSpinBox()
        self._years_spin.setRange(1, 5)
        try:
            self._years_spin.setValue(
                max(1, min(5, int(step.get("draft_years") or 2))))
        except Exception:
            self._years_spin.setValue(2)
        self._years_spin.valueChanged.connect(self._emit_draft)
        form.addRow("Contract length (years):", self._years_spin)
        lay.addLayout(form)

        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet("font-size: 13px;")
        self._result_lbl.setWordWrap(True)
        lay.addWidget(self._result_lbl)

        row = QHBoxLayout()
        walk = QPushButton("Walk Away")
        walk.setCursor(Qt.PointingHandCursor)
        walk.setToolTip("Pause this negotiation -- it stays parked and "
                        "resumable from the Staff screen")
        walk.clicked.connect(self.reject)
        row.addWidget(walk)
        row.addStretch()
        offer_btn = QPushButton("Make Offer")
        offer_btn.setObjectName("primary-btn")
        offer_btn.setCursor(Qt.PointingHandCursor)
        offer_btn.clicked.connect(self._make_offer)
        row.addWidget(offer_btn)
        lay.addLayout(row)

        self._refresh_state()

    # -- internal ------------------------------------------------------
    def _emit_draft(self, *_a):
        try:
            self._on_draft(self._salary_edit.text(),
                           str(self._years_spin.value()))
        except Exception:
            pass

    def _refresh_state(self):
        step = self._step
        self._round_lbl.setText(
            f"{_staff_role_value(self._staff)} \u00b7 "
            f"Round {int(step.get('round') or 1)}")
        offers = step.get("offers") or []
        if offers:
            lines = []
            for i, o in enumerate(offers, 1):
                try:
                    lines.append(
                        f"Round {i}: {_fmt_money(int(o.get('salary') or 0))}"
                        f" \u00d7 {int(o.get('years') or 0)}y \u2014 "
                        f"{o.get('result', '?')}")
                except Exception:
                    continue
            self._history_lbl.setText("Offer history:\n" + "\n".join(lines))
        else:
            self._history_lbl.setText("No offers yet this negotiation.")

    def _parse_offer(self):
        raw = self._salary_edit.text().strip()
        raw = raw.replace("$", "").replace(",", "").replace(" ", "")
        try:
            salary = int(float(raw))
        except Exception:
            return None, None
        years = int(self._years_spin.value())
        if salary <= 0 or not 1 <= years <= 5:
            return None, None
        return salary, years

    def _make_offer(self):
        salary, years = self._parse_offer()
        if salary is None:
            QMessageBox.warning(
                self, "Invalid Offer",
                "Enter a positive salary and a term of 1\u20135 years.")
            return
        staff = self._staff
        try:
            accepted = bool(staff.negotiate_contract(salary, years))
        except Exception:
            accepted = False
        offer = {"salary": int(salary), "years": int(years)}
        # Record the round + write through BEFORE the callback advances.
        offers = list(self._step.get("offers") or [])
        offers.append({"salary": int(salary), "years": int(years),
                       "result": "accepted" if accepted else "rejected"})
        self._step["offers"] = offers
        if not accepted:
            self._step["round"] = int(self._step.get("round") or 1) + 1
        self._step["draft_salary"] = str(salary)
        self._step["draft_years"] = str(years)
        try:
            self._on_offer(self, offer, accepted)
        except Exception:
            pass
        if not accepted:
            self._result_lbl.setText(
                "Offer rejected. Try adjusting your offer.")
            self._result_lbl.setStyleSheet(
                "font-size: 13px; color: #ff8a8a;")
            self._refresh_state()

    def mark_resolved(self):
        """The step ended in agreement -- do not park on close."""
        self._resolved = True

    def closeEvent(self, event):
        # Mainline parity: tearing down the open step without resolution
        # parks the chain (resume question on return, never silent loss).
        if not self._resolved and not self._walked_away:
            self._walked_away = True
            try:
                self._on_walk_away()
            except Exception:
                pass
        super().closeEvent(event)


def _start_chain_session(game, staff_list):
    """Begin a fresh chain: pops any previous session, writes the new one
    write-through. staff_list: live staff objects, in chain order."""
    try:
        _drop_chain(game)
        ids = []
        names = {}
        for s in staff_list or []:
            sid = str(safe_call(lambda: getattr(s, "id", ""),
                                "", context="chain staff id") or "")
            if not sid:
                continue
            ids.append(sid)
            names[sid] = _staff_name(s)
        sess = _touch_chain(
            game,
            remaining_staff_ids=ids,
            completed_results=[],
            total=len(ids),
            step_open=ids[0] if ids else None,
            staff_names=names,
            step=None,
            parked=False,
            notice_message_id=None,
        )
        return sess
    except Exception:
        return None


def _install_pending_session_repair():
    """Root-cause repair for the parked-session save/load path.

    GameSaveManager._serializable_team_talk_sessions() and
    _restore_team_talk_sessions() read self.app.pending_sessions, but
    nothing in mainline ever assigns GameSaveManager.app -- so the
    whitelisted Tier-B kinds (team_talk, staff_negotiate_chain) silently
    never survive save/load, in either direction. The fallback uses
    self.game_manager (the object the manager wraps).

    It only changes the current silent no-op path (self.app is None);
    when .app is properly assigned, behavior is untouched. In mainline
    tkinter the fallback is behavior-preserving (the GUI app keeps no
    pending_sessions on the game manager, so saves still carry {}).
    save_load_system.py is no longer edited by another dev for this:
    commit 872f6d7 now assigns GameSaveManager.app at construction, so
    this patch is a harmless no-op fallback (left in place, untouched).
    Idempotent; runs at import (this module loads at app startup via
    the screen registry, i.e. before any load).
    """
    try:
        from save_load_system import GameSaveManager as _GSM
        if getattr(_GSM, "_staff_chain_app_fallback", False):
            return

        def _with_fallback(fn):
            def _inner(self, *args, **kwargs):
                if getattr(self, "app", None) is None:
                    try:
                        self.app = getattr(self, "game_manager", None)
                    except Exception:
                        pass
                return fn(self, *args, **kwargs)
            return _inner

        _GSM._serializable_team_talk_sessions = _with_fallback(
            _GSM._serializable_team_talk_sessions)
        _GSM._restore_team_talk_sessions = _with_fallback(
            _GSM._restore_team_talk_sessions)
        _GSM._staff_chain_app_fallback = True
    except Exception:
        pass


_install_pending_session_repair()


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
            self._team_name = safe_call(
                lambda: getattr(team, "team_name", ""), "", context="load team_name") or ""
            self._staff = [s for s in
                           safe_call(lambda: list(getattr(team, "staff", []) or []),
                                 [], context="load team staff list")]
        except Exception as e:
            print(f"[staff] load failed: {e}")

    def refresh(self):
        self._load_data()
        self._loaded = {0: False, 1: False, 2: False, 3: False}
        self._on_tab_changed(self._tabs.currentIndex())
        # D-16: a parked negotiate chain re-presents its resume question
        # whenever the Staff screen is (re)shown.
        self._maybe_resume_parked_chain()

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
        header = QHBoxLayout()
        header.addWidget(self._count_label)
        header.addStretch()
        hire_btn = QPushButton("Hire Staff")
        hire_btn.setObjectName("primary-btn")
        hire_btn.setCursor(Qt.PointingHandCursor)
        hire_btn.setToolTip("Open the free-agent staff market")
        hire_btn.clicked.connect(self._open_hire_staff)
        header.addWidget(hire_btn)
        lay.addLayout(header)
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
                safe_call(lambda: getattr(m, "overall_rating", 0), 0, context="list sort overall_rating") or 0),
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

        rating = int(safe_call(lambda: getattr(s, "overall_rating", 0), 0, context="card overall_rating") or 0)
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
        age = safe_call(lambda: getattr(s, "age", 0), 0, context="card age") or 0
        nat = safe_call(lambda: getattr(s, "nationality", ""), "", context="card nationality") or ""
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
        morale = safe_call(lambda: getattr(s, "morale", "—"), "—", context="card morale")
        exp = safe_call(lambda: getattr(s, "experience", "—"), "—", context="card experience")
        sal = _fmt_salary(safe_call(lambda: getattr(s, "salary", 0), 0, context="card salary"))
        meta = QLabel(
            f"<span style='color:#8b95ab'>Morale</span> <b>{morale}</b>"
            f" &nbsp; <span style='color:#8b95ab'>Exp</span> <b>{exp}y</b>"
            f" &nbsp; <span style='color:#8b95ab'>Salary</span> <b>{sal}</b>")
        meta.setStyleSheet("font-size: 12px; color: #d6dbe6;")
        v.addWidget(meta)

        # Actions
        row = QHBoxLayout()
        row.setSpacing(8)
        negotiate_btn = QPushButton("Negotiate")
        negotiate_btn.setCursor(Qt.PointingHandCursor)
        negotiate_btn.setToolTip(
            "Negotiate a new contract -- multi-round, parks and resumes")
        negotiate_btn.clicked.connect(
            lambda _=False, staff=s: self._negotiate_contract(staff))
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
        # No "Declare Rival" button here by design: these cards show the
        # user's OWN staff and _declare_rival_staff refuses own staff
        # (mainline parity: rivalries are declared from an OPPOSING
        # staffer's card, e.g. the Morale window's opposing-staff
        # popup). A button here would be dead, misleading UI.
        row.addWidget(negotiate_btn)
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
                safe_call(lambda: getattr(m, "overall_rating", 0), 0, context="org/report sort overall_rating") or 0),
                reverse=True)

        def has_role(s, *names):
            return _staff_role_name(s) in names

        def nhl_first(members):
            """Vacant chairs first, then NHL-assigned, then AHL/farm staff."""
            return sorted(
                members,
                key=lambda m: 0 if str(safe_call(
                    lambda: getattr(m, "assignment", ""), "", context="org assignment sort") or ""
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
        rating = safe_call(lambda: getattr(s, "overall_rating", 0), 0, context="org person overall_rating") or 0
        sal = int(safe_call(lambda: getattr(s, "salary", 0), 0, context="org person salary") or 0)
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
        exp = sum(int(safe_call(lambda: getattr(s, "experience", 0), 0, context="report total experience") or 0)
                  for s in staff)
        rat = sum(int(safe_call(lambda: getattr(s, "overall_rating", 0), 0, context="report total rating") or 0)
                  for s in staff)
        tot_sal = sum(int(safe_call(lambda: getattr(s, "salary", 0), 0, context="report total salary") or 0)
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
                safe_call(lambda: getattr(m, "overall_rating", 0), 0, context="org/report sort overall_rating") or 0),
                reverse=True)
            sal_sum = sum(int(safe_call(lambda: getattr(s, "salary", 0), 0, context="report dept salary sum") or 0)
                          for s in members)
            rat_sum = sum(int(safe_call(lambda: getattr(s, "overall_rating", 0),
                                    0, context="report dept rating sum") or 0) for s in members)
            avg = round(rat_sum / len(members), 1) if members else 0
            header = QLabel(
                f"{cat.upper()} DEPARTMENT  ({len(members)})"
                f"   avg {avg} · {_fmt_money(sal_sum)}")
            header.setObjectName("section-header")
            lay.addWidget(header)
            for s in members:
                years = int(safe_call(lambda: getattr(s, "contract_years", 0),
                                  0, context="report row contract_years") or 0)
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
                    f"{safe_call(lambda: getattr(s, 'overall_rating', '?'), '?', context="report row overall_rating")} "
                    f"OVR · "
                    f"{safe_call(lambda: getattr(s, 'experience', '?'), '?', context="report row experience")}y · "
                    f"{_fmt_money(safe_call(lambda: getattr(s, 'salary', 0), 0, context="report row salary"))} "
                    f"· {years}y left · {_staff_status(s)}")
                detail.setStyleSheet("color: #8b95ab; font-size: 12px;")
                rl.addWidget(detail, 1)
                lay.addWidget(row)

        expiring = [s for s in staff
                    if int(safe_call(lambda: getattr(s, "contract_years", 99),
                                 99, context="report expiring filter") or 99) <= 1]
        if expiring:
            header = QLabel("CONTRACT EXPIRATIONS")
            header.setObjectName("section-header")
            lay.addWidget(header)
            for s in expiring:
                years = int(safe_call(lambda: getattr(s, "contract_years", 0),
                                  0, context="report row contract_years") or 0)
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
            if safe_call(lambda: _Staff.is_unique_role(new_role), False, context="reassign unique-role check"):
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
            pname = safe_call(
                lambda: getattr(p, "full_name", None), None, context="assistant player full_name") or \
                f"{safe_call(lambda: getattr(p, 'first_name', ''), '', context="assistant player first_name")} " \
                f"{safe_call(lambda: getattr(p, 'last_name', ''), '', context="assistant player last_name")}".strip() \
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

    def _open_hire_staff(self):
        """Jump to the Free Agents screen with the Staff tab selected.

        Mainline parity: Staff Management's 'Hire Staff' tab redirected to
        the Free Agency staff page (staff_management_window
        _redirect_to_free_agency). The native free-agent staff market handles
        search, department filter, offer dialog, acceptance roll, and
        game_manager.sign_free_agent_staff. Never raises.
        """
        try:
            mw = self.main_window
            if mw is None:
                return
            mw.show_screen("free_agents")
            scroll = (mw._screens.get("free_agents")
                      if hasattr(mw, "_screens") else None)
            inner = (scroll.widget() if scroll is not None
                     and hasattr(scroll, "widget") else None)
            if inner is not None and hasattr(inner, "show_staff_tab"):
                inner.show_staff_tab()
        except Exception as e:
            print(f"[staff] hire-staff navigation failed: {e}")

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

    # --- contract negotiation chain (D-16 port) ---------------------------
    # Mainline parity: negotiate_selected_staff()/_negotiate_chain() run a
    # chained series of renegotiation steps (demands + offer +
    # staff.negotiate_contract() roll). The chain is write-through
    # persisted (JSON-safe); walking away mid-step parks it; the Staff
    # screen re-presents the resume question; save/load resumes at the
    # exact round with offer history, demands, and draft offer intact.

    @staticmethod
    def _staff_id(staff):
        return str(safe_call(lambda: getattr(staff, "id", ""), "",
                             context="negotiate staff id") or "")

    def _live_staff_by_id(self):
        team = self._user_team()
        out = {}
        try:
            for s in (safe_call(
                    lambda: list(getattr(team, "staff", []) or []), [],
                    context="chain live staff") or []):
                sid = self._staff_id(s)
                if sid:
                    out[sid] = s
        except Exception:
            pass
        return out

    def _fresh_step(self, staff):
        try:
            sal = int(safe_call(lambda: getattr(staff, "salary", 0), 0,
                                context="fresh step salary") or 0)
        except Exception:
            sal = 0
        try:
            yrs = int(safe_call(lambda: getattr(staff, "contract_years", 2),
                                2, context="fresh step years") or 2)
        except Exception:
            yrs = 2
        return {
            "staff_id": self._staff_id(staff),
            "round": 1,
            "offers": [],
            "draft_salary": str(sal),
            "draft_years": str(max(1, min(5, yrs))),
            "demands": {"salary": sal,
                        "years": max(1, min(5, yrs))},
        }

    @staticmethod
    def _sanitize_step(saved, staff):
        """Defensive rebuild of a restored step (old/foreign saves)."""
        try:
            rnd = max(1, int(saved.get("round") or 1))
        except Exception:
            rnd = 1
        offers = []
        for o in (saved.get("offers") or []):
            if not isinstance(o, dict):
                continue
            try:
                offers.append({
                    "salary": int(o.get("salary") or 0),
                    "years": int(o.get("years") or 0),
                    "result": str(o.get("result") or "rejected"),
                })
            except Exception:
                continue
        demands = saved.get("demands") \
            if isinstance(saved.get("demands"), dict) else {}

        def _num(value, fallback):
            """int() with a live-staff fallback for corrupt values."""
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
            try:
                return int(fallback)
            except (TypeError, ValueError):
                return 0

        dsal = _num(demands.get("salary"), getattr(staff, "salary", 0))
        dyrs = _num(demands.get("years"),
                    getattr(staff, "contract_years", 2))
        return {
            "staff_id": str(getattr(staff, "id", "") or ""),
            "round": rnd,
            "offers": offers,
            "draft_salary": str(saved.get("draft_salary") or ""),
            "draft_years": str(saved.get("draft_years") or ""),
            "demands": {"salary": dsal,
                        "years": max(1, min(5, dyrs))},
        }

    def _negotiate_contract(self, staff):
        """Entry point: negotiate a new contract (chain of one)."""
        team = self._user_team()
        if team is None:
            QMessageBox.warning(self, "Negotiate Contract",
                                "No team loaded.")
            return
        sid = self._staff_id(staff)
        if not sid or sid not in self._live_staff_by_id():
            QMessageBox.warning(
                self, "Negotiate Contract",
                f"{_staff_name(staff)} is no longer on the staff.")
            return
        _start_chain_session(self.game, [staff])
        step = self._fresh_step(staff)
        _touch_chain(self.game, step=dict(step))
        self._open_negotiation_dialog(staff, step, [])

    def _open_negotiation_dialog(self, staff, step, results):
        def _on_draft(salary_text, years_text):
            step["draft_salary"] = str(salary_text or "")
            step["draft_years"] = str(years_text or "")
            _touch_chain(self.game, step=dict(step))

        def _on_offer(dlg, offer, accepted):
            _touch_chain(self.game, step=dict(step))
            if not accepted:
                return
            try:
                staff.salary = int(offer["salary"])
                staff.contract_years = int(offer["years"])
            except Exception:
                pass
            results.append(
                f"{_staff_name(staff)}: agreement reached")
            dlg.mark_resolved()
            dlg.accept()
            self._chain_advance(results)

        def _on_walk_away():
            # Park: keep the session (step_open + step intact) and post
            # the resume notice. No re-prompt now -- the Staff screen
            # re-presents the resume question on return.
            _touch_chain(self.game, parked=True)
            self._post_park_notice()

        dlg = _StaffNegotiationDialog(self, staff, step, _on_draft,
                                      _on_offer, _on_walk_away)
        dlg.exec()

    def _chain_advance(self, results):
        """Advance the chain past the finished step (mainline
        _negotiate_chain parity)."""
        sess = _chain_session(self.game)
        if not isinstance(sess, dict):
            self.refresh()
            return
        remaining = [str(i)
                     for i in (sess.get("remaining_staff_ids") or [])]
        names = dict(sess.get("staff_names") or {})
        if remaining:
            remaining = remaining[1:]  # consume the finished step
        _touch_chain(
            self.game,
            remaining_staff_ids=remaining,
            completed_results=[str(r) for r in results],
            step_open=remaining[0] if remaining else None,
            step=None,
            parked=False,
        )
        if not remaining:
            self._chain_complete(results)
            return
        live = self._live_staff_by_id()
        nxt = live.get(remaining[0])
        if nxt is None:
            # Stale ID: honest digest note, never a crash (mainline).
            results.append(
                f"{names.get(remaining[0], remaining[0])}: "
                "no longer on staff -- skipped")
            self._chain_advance(results)
            return
        step = self._fresh_step(nxt)
        _touch_chain(self.game, step=dict(step),
                     staff_names={remaining[0]: _staff_name(nxt)})
        self._open_negotiation_dialog(nxt, step, results)

    def _chain_complete(self, results):
        """Land the chain: consume the session FIRST (exactly-once),
        clear the park notice, post one digest. Mainline parity."""
        sess = _chain_session(self.game)
        _drop_chain(self.game)
        self._clear_park_notice(sess)
        if results:
            content = ("Contract negotiations complete:\n" + "\n".join(
                f"\u2022 {r}" for r in results))
            try:
                team = self._user_team()
                inbox = safe_call(lambda: getattr(team, "inbox", None),
                                  None, context="chain digest inbox")
                msgs = safe_call(
                    lambda: list(getattr(inbox, "messages", []) or []),
                    [], context="chain digest scan") or []
                already = any(
                    getattr(m, "subject", "")
                    == "Staff Negotiation Results"
                    and getattr(m, "content", "") == content
                    for m in msgs)
                if not already:
                    from game_classes import EmailMessage
                    from datetime import date
                    gm = _chain_owner(self.game)
                    send = safe_call(
                        lambda: getattr(gm, "send_email_to_user", None),
                        None, context="chain digest sender")
                    if callable(send):
                        send(EmailMessage(
                            sender="System", sender_type="System",
                            date_sent=date.today(), category="Contracts",
                            priority=2,
                            subject="Staff Negotiation Results",
                            content=content))
            except Exception:
                pass
        self.refresh()

    def _post_park_notice(self):
        """Idempotent park-time inbox notice (mainline priority-3 pill)."""
        sess = _chain_session(self.game)
        if not isinstance(sess, dict) or sess.get("notice_message_id"):
            return
        try:
            from game_classes import EmailMessage
            from datetime import date
            remaining = [str(i)
                         for i in (sess.get("remaining_staff_ids") or [])]
            total = int(sess.get("total") or len(remaining) or 0)
            names = dict(sess.get("staff_names") or {})
            first = [str(names.get(sid, sid)) for sid in remaining[:3]]
            detail = (f"{len(remaining)} of {total} negotiations remaining"
                      + (f" ({', '.join(first)}"
                         + ("..." if len(remaining) > 3 else "") + ")"
                         if first else ""))
            gm = _chain_owner(self.game)
            send = safe_call(
                lambda: getattr(gm, "send_email_to_user", None), None,
                context="park notice sender")
            if not callable(send):
                return
            msg = EmailMessage(
                sender="System", sender_type="System",
                date_sent=date.today(), category="Contracts",
                priority=3, subject="Staff negotiations parked",
                content=(f"Contract negotiations paused -- {detail}.\n"
                         "Resume any time from the Staff screen."))
            send(msg)
            _touch_chain(self.game,
                         notice_message_id=getattr(msg, "id", None))
        except Exception:
            pass

    def _clear_park_notice(self, sess):
        """Delete the park-time inbox notice, if it still exists."""
        try:
            mid = (sess or {}).get("notice_message_id")
            if not mid:
                return
            team = self._user_team()
            inbox = safe_call(lambda: getattr(team, "inbox", None),
                              None, context="clear notice inbox")
            deleter = safe_call(
                lambda: getattr(inbox, "delete_message", None), None,
                context="clear notice deleter")
            if callable(deleter):
                deleter(mid)
        except Exception:
            pass

    def _maybe_resume_parked_chain(self):
        """Re-present the resume question when returning to the Staff
        screen with a parked chain. Dismiss (X/Esc) = keep parked, never
        auto-answer (mainline parity)."""
        sess = _chain_session(self.game)
        if not isinstance(sess, dict) or not sess.get("parked"):
            return
        if getattr(self, "_resume_asked", False):
            return
        self._resume_asked = True
        remaining = [str(i)
                     for i in (sess.get("remaining_staff_ids") or [])]
        try:
            total = int(sess.get("total") or len(remaining) or 0)
        except (TypeError, ValueError):
            # Corrupt/hand-edited save: fall back to the live list.
            total = len(remaining)
        names = dict(sess.get("staff_names") or {})
        first = ", ".join(str(names.get(sid, sid)) for sid in remaining[:3])
        detail = f"{len(remaining)} of {total} negotiations remaining"
        if first:
            detail += (f" ({first}"
                       + ("..." if len(remaining) > 3 else "") + ")")
        box = QMessageBox(self)
        box.setWindowTitle("Resume negotiations?")
        box.setText(
            f"Contract negotiations paused -- {detail}.\n\n"
            "Resume where you left off, or discard the remaining "
            "negotiations.")
        resume_btn = box.addButton("Resume", QMessageBox.AcceptRole)
        box.addButton("Discard", QMessageBox.DestructiveRole)
        box.setDefaultButton(resume_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked == resume_btn:
            self._resume_asked = False
            self._resume_chain()
        elif clicked is None:
            # Dismissed: keep parked; allow re-prompt on next return.
            self._resume_asked = False
        else:
            self._resume_asked = False
            _drop_chain(self.game)
            self.refresh()

    def _resume_chain(self):
        """Resume a parked chain: revalidate IDs, restore the exact step
        (round, offer history, demands, draft), reopen the dialog."""
        sess = _chain_session(self.game)
        if not isinstance(sess, dict):
            return
        _touch_chain(self.game, parked=False)
        self._clear_park_notice(sess)
        remaining = [str(i)
                     for i in (sess.get("remaining_staff_ids") or [])]
        names = dict(sess.get("staff_names") or {})
        results = [str(r) for r in (sess.get("completed_results") or [])]
        live = self._live_staff_by_id()
        staff_objs = []
        for sid in remaining:
            s = live.get(sid)
            if s is None:
                results.append(f"{names.get(sid, sid)}: "
                               "no longer on staff -- skipped")
            else:
                staff_objs.append(s)
        if not staff_objs:
            self._chain_complete(results)
            return
        first = staff_objs[0]
        first_id = self._staff_id(first)
        saved_step = sess.get("step")
        if isinstance(saved_step, dict) and \
                str(saved_step.get("staff_id") or "") == first_id:
            step = self._sanitize_step(saved_step, first)
        else:
            step = self._fresh_step(first)
        _touch_chain(
            self.game,
            remaining_staff_ids=[self._staff_id(s) for s in staff_objs],
            completed_results=list(results),
            step_open=first_id,
            step=dict(step),
            parked=False,
        )
        self._open_negotiation_dialog(first, step, results)

    # --- declare rival (D-16 port) ---------------------------------------
    # Mainline parity: staff_management_window._declare_rival_staff --
    # non-head-coach staff can declare personal rivalries through the
    # EXISTING rivalry system (reputation_system.declare_rivalry,
    # kind="gm_coach"). Staff on the user's own club are refused with an
    # explanation; feed + inbox go through the headlines machinery.
    # Effects: heat 70, grudge 80, declared floor 40, user_declared.

    def _declare_rival_staff(self, staff):
        """Declare a personal rivalry with a staff member. Never raises."""
        try:
            gm = _chain_owner(self.game)
            league = safe_call(lambda: getattr(gm, "league", None), None,
                               context="declare rival league")
            team = self._user_team()
            name = _staff_name(staff)
            if league is None or team is None:
                QMessageBox.warning(
                    self, "Declare Rival",
                    "No active league to declare a rivalry in.")
                return
            own_ids = {self._staff_id(s)
                       for s in self._live_staff_by_id().values()}
            if self._staff_id(staff) in own_ids:
                QMessageBox.information(
                    self, "Declare Rival",
                    f"{name} works for your club.\n\n"
                    "Declare rival is for opposing staff -- declare from "
                    "their card to start a personal beef.")
                return
            import reputation_system as rs
            try:
                existing = rs.rivalry_between(
                    getattr(league, "rivalries", None) or [],
                    rs.gm_persona(team), staff, kind="gm_coach")
            except Exception:
                existing = None
            if existing and existing.get("user_declared"):
                QMessageBox.information(
                    self, "Declare Rival",
                    f"You already declared {name} a personal rival "
                    f"(heat {existing.get('intensity', 0):.0f}).")
                return
            rec = rs.declare_rivalry(league, rs.gm_persona(team), staff,
                                     kind="gm_coach")
            if not rec:
                QMessageBox.warning(self, "Declare Rival",
                                    "Could not register the rivalry.")
                return
            # Feed + inbox (headlines parity). deliver() always lands the
            # inbox via human_teams(); the feed needs a native add_news
            # (or the engine news_log) since GameManager has neither.
            try:
                import headlines as hl
                from datetime import date
                team_name = str(safe_call(
                    lambda: getattr(team, "team_name", "?"), "?",
                    context="declare rival team name") or "?")
                target_team_name = "?"
                for t in (safe_call(
                        lambda: list(getattr(league, "teams", []) or []),
                        [], context="declare rival league teams") or []):
                    tids = {self._staff_id(s) for s in
                            (safe_call(lambda: list(
                                getattr(t, "staff", []) or []), [],
                                context="declare rival team staff") or [])}
                    if self._staff_id(staff) in tids:
                        target_team_name = str(safe_call(
                            lambda: getattr(t, "team_name", "?"), "?",
                            context="declare rival target team") or "?")
                        break
                game_date = safe_call(
                    lambda: getattr(gm, "current_date", None), None,
                    context="declare rival game date") or date.today()
                msg = hl.make_headline(
                    "rivalry_declared", game_date,
                    declarer_name=team_name, target_name=name,
                    target_kind="coach")
                if msg is not None:
                    hl.deliver(gm, msg,
                              involved=(team_name, target_team_name))
                    story = str(getattr(msg, "subject", "") or "")
                    feed_fn = safe_call(
                        lambda: getattr(self.main_window, "add_news",
                                        None), None,
                        context="declare rival feed mw") or safe_call(
                        lambda: getattr(self.game, "add_news", None),
                        None, context="declare rival feed game")
                    if callable(feed_fn):
                        feed_fn(story)
                    else:
                        log = safe_call(
                            lambda: getattr(gm, "news_log", None), None,
                            context="declare rival news_log")
                        if isinstance(log, list):
                            log.append({"date": game_date,
                                        "story": story})
            except Exception:
                pass
            QMessageBox.information(
                self, "Rival Declared",
                f"Declared: {name} "
                f"(heat {rec.get('intensity', 70):.0f}). "
                "Those games just got personal.")
        except Exception as e:
            QMessageBox.warning(self, "Declare Rival",
                                f"Could not declare rival: {e}")


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
