"""Tactics screen — native Qt port of the web tactics page.

Five tabs: Systems, Identity, Analyst, Coach, Practice.

Calls the game object directly (no Flask/HTTP). The web UI translated
writes into command-queue ops; here we call the same underlying
``tactics`` module functions directly:

- install a whiteboard module : ``tactics.set_team_system(team, cat, key)``
- identity preset              : ``tactics.apply_identity_preset(team, preset)``
- whiteboard ownership         : via ``reputation_system.take_over_tactics`` /
                                 ``reputation_system.hand_back_tactics`` so
                                 coach-personality reactions, trust deltas,
                                 room events, morale shifts and news fire
                                 (mainline parity -- never flip control raw)
- staged changes               : ``self._pending`` (category -> system key),
                                 mirroring mainline tactics_window; clicks stage
                                 while the coach owns the whiteboard and apply
                                 immediately when the GM does
- coach enforce                : ``rs.enforce_tactics(team, pending, ctx)`` --
                                 a ONE-TIME overrule of the staged changes;
                                 control NEVER flips (mainline parity)
- coach takeover               : ``rs.take_over_tactics(team, ctx)`` --
                                 PERMANENT GM control of the whiteboard
- coach handback               : ``rs.hand_back_tactics(team)`` --
                                 control flips back and trust is repaired;
                                 SYSTEMS STAY as the GM left them (mainline
                                 parity -- install_coach_systems is the hire
                                 path only)
- preferred tactics            : ``tactics.save_preferred_tactics`` /
                                 ``tactics.get_preferred_tactics``
- legacy slider pills         : ``_apply_legacy_tactic_change`` -- the
                                 GM-owned whiteboard writes directly via
                                 setattr; coach-owned stages into
                                 ``self._pending_legacy``; fail-closed when
                                 the reputation service is down
- weekly practice plan         : ``team.dressing_room["practice_plan"]``
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QGroupBox, QTabWidget, QCheckBox, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QAbstractItemView,
    QMessageBox,
)
import importlib  # R18: deferred Tk-module imports use importlib.import_module
                  # (invisible to PyInstaller's static analysis).
from PySide6.QtCore import Qt, QTimer, QEvent

import time

from .base import BaseScreen
from native_ui.safe import safe_call

try:
    import tactics as _tx
except Exception:
    _tx = None

try:
    import reputation_system as _rs
except Exception:
    _rs = None


# ---------------------------------------------------------------- helpers

def _staff_role_str(s):
    """Staff role as a display string, enum-aware."""
    try:
        return str(getattr(getattr(s, "role", None), "value",
                           getattr(s, "role", "") or ""))
    except Exception:
        return ""


# ---------------------------------------------------------------- constants

CATEGORY_LABELS = {
    "forecheck": "Forecheck",
    "neutral_zone": "Neutral Zone",
    "dzone": "D-Zone Coverage",
    "ozone": "O-Zone Attack",
    "breakout": "Breakout",
    "pp": "Power Play",
    "pk": "Penalty Kill",
}

CATEGORY_HINTS = {
    "forecheck": "Pressure scheme in the offensive zone — how you hunt the puck",
    "neutral_zone": "The 80-foot battleground — how you defend and exit the middle",
    "dzone": "Protecting the house — coverage shape in your own end",
    "ozone": "How you generate chances at 5v5",
    "breakout": "How you exit your own zone with the puck",
    "pp": "Man-advantage formation — where PP shots come from",
    "pk": "Short-handed shape — how you take away time and space",
}

# Legacy aggression sliders (Tkinter TacticsView parity). They still feed
# the sim: tactic_even_strength/power_play/penalty_kill fold into
# resolve_team_tactics(), tactic_line_matching drives home-ice deployment,
# tactic_forecheck/tactic_offense are read by the shot engine.
TACTIC_GROUPS = [
    ("Even Strength", "tactic_even_strength", "Balanced",
     ["Very Defensive", "Defensive", "Balanced", "Offensive", "Very Offensive"],
     "5v5 play style"),
    ("Power Play", "tactic_power_play", "Offensive",
     ["Conservative", "Balanced", "Offensive", "Very Offensive"],
     "Man-advantage approach"),
    ("Penalty Kill", "tactic_penalty_kill", "Defensive",
     ["Very Defensive", "Defensive", "Balanced", "Aggressive"],
     "Short-handed defense"),
    ("Line Matching", "tactic_line_matching", "Standard",
     ["Conservative", "Standard", "Aggressive"],
     "Home-ice line deployment vs score state"),
    ("Forecheck", "tactic_forecheck", "2-1-2",
     ["2-1-2", "1-2-2", "1-4"],
     "Pressure scheme when the other team has the puck"),
    ("Offensive Zone", "tactic_offense", "Spread",
     ["Overload", "Umbrella", "Spread", "Crash the Net"],
     "5v5 attacking shape — where your shots come from"),
]

_ES_ATTACK = {'Very Defensive': 0.94, 'Defensive': 0.97, 'Balanced': 1.0,
              'Offensive': 1.04, 'Very Offensive': 1.08}
_ES_DEFENSE = {'Very Defensive': 0.92, 'Defensive': 0.96, 'Balanced': 1.0,
               'Offensive': 1.03, 'Very Offensive': 1.06}
_PP_MULT = {'Conservative': 0.96, 'Balanced': 1.0, 'Offensive': 1.05,
            'Very Offensive': 1.10}
_PK_DIV = {'Very Defensive': 1.10, 'Defensive': 1.05, 'Balanced': 1.0,
           'Aggressive': 0.96}

# Engine-multiplier badges: (key, label, invert). invert=True means a
# *lower* multiplier is better (chances allowed, PK suppression).
ENGINE_BADGES = [
    ("attack", "Attack", False),
    ("defense", "Chances allowed", True),
    ("pace", "Pace", False),
    ("shot_vol", "Shot volume", False),
    ("shot_qual", "Shot quality", False),
    ("pp", "PP", False),
    ("pk", "PK suppression", True),
    ("pressure", "Pressure", False),
]

GOOD = "#4CAF50"
WARN = "#FFC107"
BAD = "#F44336"
DIM = "#9aa4b8"

# Fallback practice labels if dressing_room can't be imported (it pulls in
# customtkinter at module scope, which may be absent in some environments).
_PRACTICE_FOCI_FALLBACK = {
    "special_teams": "Special Teams",
    "conditioning": "Conditioning",
    "systems": "Systems",
    "skills": "Skills",
    "recovery": "Recovery",
}
_PRACTICE_INT_FALLBACK = {
    "light": "Light",
    "moderate": "Moderate",
    "hard": "Hard",
    "brutal": "Brutal",
}


class TacticsScreen(BaseScreen):
    title = "Tactics"

    # ------------------------------------------------------------ framework

    def __init__(self, game, main_window, parent=None):
        self._gm = None
        self._team = None
        self._practice_focus = "systems"
        self._practice_intensity = "moderate"
        self._foci_labels = dict(_PRACTICE_FOCI_FALLBACK)
        self._int_labels = dict(_PRACTICE_INT_FALLBACK)
        # Staged tactical changes (category -> new system key), mirroring
        # mainline tactics_window._pending. Clicks stage while the coach owns
        # the whiteboard; Suggest / Enforce / Take Over consume them.
        self._pending = {}
        # Staged legacy game-management slider changes (attr -> value). The
        # legacy pills carry plain team attributes (tactic_even_strength,
        # ...), not whiteboard catalog keys, so they can't ride in
        # self._pending -- the reputation engine applies that map via
        # tactics.set_team_system, which is a no-op for unknown categories.
        # They stage in this parallel map, consumed at the same commit
        # points (Suggest accept / Enforce / Take Over).
        self._pending_legacy = {}
        # Response lines that survive tab rebuilds (mainline _response_text).
        self._coach_msg = ""
        self._systems_msg = ""
        self._legacy_msg = ""
        # Human-readable group titles for the legacy staging message.
        self._legacy_labels = {attr: title
                               for title, attr, _d, _v, _h in TACTIC_GROUPS}
        # T2: double-click-guard timestamps live ON THE PILL
        # (pill._last_dblclick), set at creation. Qt still emits clicked()
        # on release after a handled double-click -- the pill records when
        # its own dblclick was handled so _on_module_pill_clicked can
        # ignore that trailing click. A single global timestamp swallowed
        # single clicks on NEIGHBORING pills within 300ms of any handled
        # double-click, so it was replaced with the per-pill version.
        # T6: identity of the team _pending was staged for -- pending is
        # cleared whenever the resolved team changes (career switches).
        self._pending_team_marker = None
        super().__init__(game, main_window, parent)

    def _resolve_team(self):
        gm = getattr(self.game, "game_manager", None) or self.game
        self._gm = gm
        self._team = (getattr(gm, "user_team", None)
                      or getattr(self.game, "user_team", None))
        # T6: staged changes belong to one team. If the resolved team
        # changed (career switch in the same session), drop the pending
        # map rather than letting another career's stages leak onto it.
        team = self._team
        marker = (id(team), getattr(team, "team_name", None)) \
            if team is not None else None
        if marker != self._pending_team_marker:
            self._pending.clear()
            # T6: legacy stages belong to the same team -- drop them too.
            self._pending_legacy.clear()
            self._legacy_msg = ""
            self._pending_team_marker = marker
        return self._team

    def _head_coach(self, team):
        for s in safe_call(lambda: list(getattr(team, "staff", [])), [],
                           context="tactics/head_coach") or []:
            if "head coach" in _staff_role_str(s).lower():
                return s
        return None

    def _team_context(self):
        """Record/team-shape context for the personality engine.

        Mirrors mainline tactics_window._team_context(): drives the
        control_need reactions in take_over_tactics / enforce_tactics
        (e.g. overruling an authoritarian on a winning team stings more).
        """
        ctx = {"win_pct": 0.5, "losing_streak": 0}
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            league = getattr(gm, "league", None) or getattr(self.game, "league", None)
            st = (getattr(league, "standings", {}) or {}).get(
                getattr(self._team, "team_name", ""), {})
            w = st.get("W", st.get("Wins", 0))
            l = st.get("L", st.get("Losses", 0))
            otl = st.get("OTL", 0)
            ctx["win_pct"] = w / max(1, w + l + otl)
            ctx["losing_streak"] = int(st.get("losing_streak", st.get("streak", 0)) or 0)
        except Exception:
            pass
        return ctx

    def _push_tactics_news(self, text):
        """Post a tactics headline to the news feed (mainline parity)."""
        if not text:
            return
        try:
            add_news = getattr(self.main_window, "add_news", None) \
                or getattr(self.game, "add_news", None)
            if callable(add_news):
                add_news(f"Tactics: {text}")
        except Exception:
            pass

    def _skaters(self, team):
        roster = safe_call(lambda: list(team.roster), [],
                           context="tactics/skaters") or []
        return [p for p in roster
                if not str(safe_call(lambda: getattr(p, "primary_position", ""),
                                     "",
                                     context="tactics/skaters")
                           ).upper().startswith("G")]

    def _build_body(self):
        intro = QLabel(
            "Your game plan shapes sim results in every situation. Seven "
            "whiteboard modules drive the engine — pick each phase's system, "
            "or install a whole identity in one click.")
        intro.setStyleSheet(f"color: {DIM}; font-size: 13px;")
        intro.setWordWrap(True)
        self._layout.addWidget(intro)

        self._tabs = QTabWidget()
        self._tab_widgets = {}
        for key, label in (("systems", "Systems"), ("identity", "Identity"),
                           ("analyst", "Analyst"), ("coach", "Coach"),
                           ("practice", "Practice")):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            body = QWidget()
            lay = QVBoxLayout(body)
            lay.setSpacing(14)
            lay.setContentsMargins(4, 4, 4, 4)
            scroll.setWidget(body)
            self._tab_widgets[key] = (scroll, body, lay)
            self._tabs.addTab(scroll, label)
        self._tabs.currentChanged.connect(lambda _i: self.refresh())
        self._layout.addWidget(self._tabs, 1)

    def refresh(self):
        team = self._resolve_team()
        if team is None or _tx is None:
            return
        # Practice tab labels refresh (cheap; keep import guarded)
        self._refresh_practice_labels()
        builders = {
            "systems": self._rebuild_systems_tab,
            "identity": self._rebuild_identity_tab,
            "analyst": self._rebuild_analyst_tab,
            "coach": self._rebuild_coach_tab,
            "practice": self._rebuild_practice_tab,
        }
        for key, fn in builders.items():
            _scroll, _body, lay = self._tab_widgets[key]
            self._clear_layout(lay)
            try:
                fn(lay)
            except Exception:
                lay.addWidget(QLabel("Couldn't load this tab."))
        self._tab_widgets["systems"][2].addStretch(1)

    @staticmethod
    def _clear_layout(lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                TacticsScreen._clear_layout(sub)

    @staticmethod
    def _section(title, lay):
        head = QLabel(title.upper())
        head.setObjectName("section-header")
        lay.addWidget(head)

    # ---------------------------------------------------------------- pill

    def _make_pill(self, text, active=False):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setCheckable(True)
        btn.setChecked(active)
        self._style_pill(btn)
        return btn

    @staticmethod
    def _style_pill(btn):
        btn.setStyleSheet("""
            QPushButton {
                background: #1b2230; color: #cfd6e4;
                border: 1px solid #2c3648; border-radius: 14px;
                padding: 6px 14px; font-size: 13px;
            }
            QPushButton:hover { border-color: #3B82F6; color: #ffffff; }
            QPushButton:checked {
                background: #3B82F6; color: #ffffff;
                border-color: #3B82F6; font-weight: bold;
            }
            QPushButton:disabled { color: #6b7488; background: #141a26; }
        """)

    # ------------------------------------------------------------- systems

    def _rebuild_systems_tab(self, lay):
        team = self._team
        try:
            tk = _tx.ensure_team_tactics(team)
        except Exception:
            tk = {}

        # ---- status bar
        bar = QHBoxLayout()
        bar.setSpacing(16)
        active = safe_call(lambda: _tx.matching_identity(team),
                           context="tactics/matching_identity")
        preset_name = "Custom mix"
        try:
            if active:
                preset_name = _tx.IDENTITY_PRESETS.get(active, {}).get(
                    "name", active)
        except Exception:
            pass
        fam = safe_call(lambda: float(getattr(team, "tactics_familiarity", 85)), 85,
                        context="tactics/familiarity")
        control = safe_call(lambda: _tx.get_tactics_control(team), "coach",
                            context="tactics/get_control")
        roster_fit = safe_call(lambda: _tx.team_system_fit(team),
                               context="tactics/system_fit")
        self._status_chip(bar, "Identity", preset_name)
        fam_col = GOOD if fam >= 70 else WARN if fam >= 50 else BAD
        fam_lab = QLabel(
            f"<span style='color:{DIM};font-size:11px;'>FAMILIARITY</span><br>"
            f"<b style='color:{fam_col};font-size:15px;'>{fam:.0f}/100</b>")
        fam_bar = QProgressBar()
        fam_bar.setRange(0, 100)
        fam_bar.setValue(int(fam))
        fam_bar.setTextVisible(False)
        fam_bar.setFixedWidth(90)
        fam_bar.setStyleSheet(
            f"QProgressBar {{ background: #1b2230; border-radius: 4px; "
            f"height: 8px; }} "
            f"QProgressBar::chunk {{ background: {fam_col}; "
            f"border-radius: 4px; }}")
        fam_box = QVBoxLayout()
        fam_box.addWidget(fam_lab)
        fam_box.addWidget(fam_bar)
        bar.addLayout(fam_box)
        self._status_chip(bar, "Whiteboard",
                          "YOU (GM)" if control == "gm" else "Coach")
        self._status_chip(bar, "Roster fit",
                          f"{roster_fit * 100:.0f}%"
                          if roster_fit is not None else "—")
        bar.addStretch(1)
        lay.addLayout(bar)

        # ---- module cards
        self._section("Whiteboard Modules", lay)
        hint = QLabel(
            "Click a system to install it. Double-click for the scout report: "
            "blurb, tradeoffs, roster fit vs current, and NHL exemplars. "
            "While the coach owns the whiteboard, clicks are STAGED — "
            "Suggest, Enforce, or Take Over from the Coach tab.")
        hint.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self._systems_out = QLabel(self._systems_msg)
        self._systems_out.setStyleSheet(f"color: {WARN}; font-size: 12px;")
        self._systems_out.setWordWrap(True)
        self._systems_out.setVisible(bool(self._systems_msg))
        lay.addWidget(self._systems_out)

        for cat, _label, _attr in _tx.ALL_CATEGORIES:
            catalog = _tx.CATALOGS.get(cat, {})
            current = tk.get(cat) if isinstance(tk, dict) else None
            card = QGroupBox(CATEGORY_LABELS.get(cat, cat))
            card.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
            card_lay = QVBoxLayout(card)
            hint_lab = QLabel(CATEGORY_HINTS.get(cat, ""))
            hint_lab.setStyleSheet(f"color: {DIM}; font-size: 12px;")
            hint_lab.setWordWrap(True)
            card_lay.addWidget(hint_lab)

            cur = catalog.get(current, {})
            cur_name = cur.get("name", current or "—")
            cur_trade = safe_call(lambda: _tx.system_tradeoffs(cat, current), "",
                                  context="tactics/system_tradeoffs")
            running = QLabel(
                f"Running: <b>{cur_name}</b>"
                + (f" <span style='color:{DIM};'>({cur_trade})</span>"
                   if cur_trade else ""))
            running.setWordWrap(True)
            card_lay.addWidget(running)

            pill_row = QHBoxLayout()
            pill_row.setSpacing(6)
            pills_wrap = QWidget()
            pills_wrap.setLayout(pill_row)

            # Inspector detail (blurb / tradeoffs / fit / exemplars)
            detail = QLabel(
                self._system_detail_text(cat, current, current,
                                         catalog, team))
            detail.setStyleSheet(f"color: {DIM}; font-size: 12px;")
            detail.setWordWrap(True)

            for skey, s in catalog.items():
                pill = self._make_pill(s.get("name", skey),
                                       # A staged change shows as the
                                       # selected one (mainline parity).
                                       active=(skey == self._pending.get(
                                           cat, current)))
                pill.setProperty("sys_key", skey)
                pill.setToolTip(s.get("blurb", ""))
                pill.installEventFilter(self)
                # single-click installs; dblclick opens the inspector
                # instead (disambiguated with a short timer).
                pill._pending = None
                # T2: per-pill double-click-guard timestamp (see __init__).
                pill._last_dblclick = 0.0
                pill._cat = cat
                pill._detail = detail
                pill.clicked.connect(self._on_module_pill_clicked)
                pill_row.addWidget(pill)
            pill_row.addStretch(1)
            card_lay.addWidget(pills_wrap)
            card_lay.addWidget(detail)
            lay.addWidget(card)

        # ---- legacy game-management sliders
        self._section("Game Management", lay)
        sub = QLabel(
            "Legacy aggression sliders and home-ice deployment — they still "
            "fold into the engine.")
        sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        lay.addWidget(sub)
        self._legacy_out = QLabel(self._legacy_msg)
        self._legacy_out.setStyleSheet(f"color: {WARN}; font-size: 12px;")
        self._legacy_out.setWordWrap(True)
        self._legacy_out.setVisible(bool(self._legacy_msg))
        lay.addWidget(self._legacy_out)
        for title, attr, default, values, hint_text in TACTIC_GROUPS:
            box = QGroupBox(title)
            box_lay = QVBoxLayout(box)
            desc = QLabel(hint_text)
            desc.setStyleSheet(f"color: {DIM}; font-size: 12px;")
            box_lay.addWidget(desc)
            row = QHBoxLayout()
            current = safe_call(lambda: getattr(team, attr, default), default,
                                context="tactics/legacy_attr")
            if not safe_call(lambda: hasattr(team, attr), False,
                             context="tactics/legacy_attr"):
                safe_call(lambda: setattr(team, attr, current),
                          context="tactics/legacy_attr")
            for v in values:
                pill = self._make_pill(
                    v,
                    # A staged change shows as the selected one (mainline
                    # parity), same as the whiteboard module pills.
                    active=(v == self._pending_legacy.get(attr, current)))
                pill.setProperty("tactic_attr", attr)
                pill.setProperty("tactic_value", v)
                pill.setProperty("tactic_default", default)
                pill.clicked.connect(self._on_legacy_pill_clicked)
                row.addWidget(pill)
            row.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(row)
            box_lay.addWidget(wrap)
            lay.addWidget(box)

        # ---- expected impact
        self._section("Expected Impact", lay)
        engine = safe_call(lambda: _tx.resolve_team_tactics(team), {},
                           context="tactics/resolve") or {}
        eng_lab = QLabel("Engine multipliers from the seven modules:")
        eng_lab.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        lay.addWidget(eng_lab)
        badges = QHBoxLayout()
        shown = False
        for key, label, invert in ENGINE_BADGES:
            v = engine.get(key)
            if v is None or not isinstance(v, (int, float)):
                continue
            shown = True
            pct = round((v - 1.0) * 100)
            good = (pct < 0) if invert else (pct > 0)
            col = GOOD if good else BAD if pct != 0 else DIM
            sign = "+" if pct >= 0 else ""
            b = QLabel(f"<b style='color:{col};'>{label} {sign}{pct}%</b>")
            b.setStyleSheet(
                "background:#1b2230; border:1px solid #2c3648; "
                "border-radius:10px; padding:5px 10px; font-size:12px;")
            badges.addWidget(b)
        if not shown:
            badges.addWidget(QLabel("—"))
        badges.addStretch(1)
        lay.addLayout(badges)

        id_lines = safe_call(lambda: _tx.describe_team_tactics(team), [],
                           context="tactics/describe") or []
        id_lab = QLabel("Identity: " + (" · ".join(id_lines) if id_lines else "—"))
        id_lab.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        id_lab.setWordWrap(True)
        lay.addWidget(id_lab)

        for line in self._impact_lines(team):
            il = QLabel(line)
            il.setStyleSheet("font-size: 13px;")
            il.setWordWrap(True)
            lay.addWidget(il)

    def _system_detail_text(self, cat, skey, current, catalog, team):
        s = catalog.get(skey, {})
        blurb = s.get("blurb", "")
        trade = safe_call(lambda: _tx.system_tradeoffs(cat, skey), "",
                          context="tactics/system_tradeoffs")
        ex = s.get("exemplars", []) or []
        fit_txt = ""
        try:
            skaters = self._skaters(team)
            if skaters:
                fit = (sum(_tx.player_system_fit(p, skey, cat)
                           for p in skaters) / len(skaters))
                if skey == current:
                    fit_txt = f" Roster fit {fit:.0%}."
                else:
                    cur_fit = (sum(_tx.player_system_fit(p, current, cat)
                                   for p in skaters) / len(skaters)) \
                        if current else fit
                    d = fit - cur_fit
                    fit_txt = (f" Roster fit {fit:.0%} "
                               f"({d:+.0%} vs current).")
        except Exception:
            pass
        ex_txt = (" Run by: " + ", ".join(ex)) if ex else ""
        return (f"<b>{s.get('name', skey)}</b> — {blurb}"
                + (f" <span style='color:{WARN};'>{trade}</span>" if trade else "")
                + fit_txt + ex_txt)

    def _status_chip(self, lay, label, value):
        lab = QLabel(
            f"<span style='color:{DIM};font-size:11px;'>"
            f"{label.upper()}</span><br>"
            f"<b style='font-size:15px;'>{value}</b>")
        lay.addWidget(lab)

    def _impact_lines(self, team):
        es = safe_call(lambda: getattr(team, 'tactic_even_strength', 'Balanced'), 'Balanced',
                       context="tactics/legacy_attr")
        pp = safe_call(lambda: getattr(team, 'tactic_power_play', 'Offensive'), 'Offensive',
                       context="tactics/legacy_attr")
        pk = safe_call(lambda: getattr(team, 'tactic_penalty_kill', 'Defensive'), 'Defensive',
                       context="tactics/legacy_attr")
        lm = safe_call(lambda: getattr(team, 'tactic_line_matching', 'Standard'), 'Standard',
                       context="tactics/legacy_attr")
        fc = safe_call(lambda: getattr(team, 'tactic_forecheck', '2-1-2'), '2-1-2',
                       context="tactics/legacy_attr")
        off = safe_call(lambda: getattr(team, 'tactic_offense', 'Spread'), 'Spread',
                        context="tactics/legacy_attr")
        atk = (_ES_ATTACK.get(es, 1.0) - 1.0) * 100
        allowed = (_ES_DEFENSE.get(es, 1.0) - 1.0) * 100
        pp_mult = _PP_MULT.get(pp, 1.05)
        pk_effect = (1.0 / _PK_DIV.get(pk, 1.05) - 1.0) * 100
        return [
            f"Even strength: chance quality {atk:+.0f}%, chances allowed {allowed:+.0f}%",
            f"Power play ({pp}): chance quality {(pp_mult - 1.0) * 100:+.0f}% (before opponent's PK)",
            f"Penalty kill ({pk}): opponent chances {pk_effect:+.0f}% when shorthanded",
            f"Line matching ({lm}): " + (
                "top lines sheltered when leading, leaned on when trailing" if lm == "Aggressive"
                else "standard rotation" if lm == "Standard"
                else "even ice time regardless of score"),
            f"Forecheck ({fc}): " + (
                "heavy pressure on breakouts, more risk" if fc == "2-1-2"
                else "balanced pressure through the neutral zone" if fc == "1-2-2"
                else "concede the zone, protect the middle"),
            f"Offensive zone ({off}): " + (
                "numbers to the strong side, slot chances" if off == "Overload"
                else "point shots through traffic" if off == "Umbrella"
                else "balanced looks from everywhere" if off == "Spread"
                else "net-front chaos, tips and rebounds"),
        ]

    # -- module pill interactions -----------------------------------

    def eventFilter(self, obj, event):
        # Disambiguate single vs double click on module pills:
        # single click installs, double click opens the inline inspector.
        if event.type() == QEvent.MouseButtonDblClick:
            t = getattr(obj, "_pending", None)
            if t is not None and t.isActive():
                t.stop()
            # T2: Qt still emits clicked() on release after the double
            # click -- record the timestamp ON THE PILL so
            # _on_module_pill_clicked ignores only that pill's trailing
            # click instead of starting a new timer nothing cancels (which
            # would install the system anyway). A global timestamp here
            # swallowed single clicks on neighboring pills too.
            obj._last_dblclick = time.monotonic()
            self._show_inspector(obj)
            return True
        return super().eventFilter(obj, event)

    def _on_module_pill_clicked(self):
        pill = self.sender()
        if pill is None:
            return
        # T2: ignore the clicked() that trails a handled double-click.
        # The guard is per-pill: only this pill's own double-click
        # suppresses its trailing click, so fast clicks on neighboring
        # pills still go through.
        if time.monotonic() - getattr(pill, "_last_dblclick", 0.0) < 0.3:
            return
        old = getattr(pill, "_pending", None)
        if old is not None and old.isActive():
            old.stop()
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(lambda: self._install_module(pill))
        pill._pending = t
        t.start(250)

    def _show_inspector(self, pill):
        try:
            cat = pill._cat
            skey = pill.property("sys_key")
            team = self._team
            catalog = _tx.CATALOGS.get(cat, {})
            current = safe_call(lambda: _tx.team_tactics(team).get(cat),
                                context="tactics/team_tactics")
            pill._detail.setText(
                self._system_detail_text(cat, skey, current, catalog, team))
        except Exception:
            pass

    def _apply_system_change(self, cat, skey, operation):
        """Apply a whiteboard system change through the canonical ownership flow.

        - GM owns the whiteboard -> apply directly via ``tactics.set_team_system``.
        - Coach owns it -> STAGE the change in ``self._pending`` (mainline
          tactics_window parity); it flows through Suggest / Enforce /
          Take Over from the Coach tab. Control never flips here.
        - Reputation service unavailable while the coach owns the whiteboard ->
          block the mutation and show an actionable error instead of silently
          bypassing coach consequences.
        """
        team = self._team
        if _tx is None:
            QMessageBox.warning(
                self, "Tactics",
                "The tactics engine is unavailable. No changes were made.")
            return False
        control = safe_call(
            lambda: _tx.get_tactics_control(team), "coach",
            context="tactics/get_control")
        if control == "gm":
            _tx.set_team_system(team, cat, skey)
            self._pending.pop(cat, None)
            return True
        # Coach owns the whiteboard: stage, don't suggest immediately.
        if _rs is None:
            QMessageBox.warning(
                self, "Tactics",
                "The coach owns the whiteboard, but the reputation service "
                "is unavailable, so the change cannot be proposed to the "
                "coach. No changes were made. Restart the application and "
                "try again.")
            return False
        try:
            current = (safe_call(lambda: _tx.team_tactics(team), {},
                                 context="tactics/team_tactics") or {}).get(cat)
        except Exception:
            current = None
        if skey == current:
            self._pending.pop(cat, None)
            self._systems_msg = ""
            self.refresh()
            return True
        self._pending[cat] = skey
        try:
            sname = (_tx.CATALOGS.get(cat, {}).get(skey, {})
                     .get("name", skey))
        except Exception:
            sname = skey
        self._systems_msg = (
            f"Staged: {CATEGORY_LABELS.get(cat, cat)} → {sname}. "
            "Go to the Coach tab to Suggest, Enforce, or Take Over.")
        self.refresh()
        return False

    def _install_module(self, pill):
        try:
            cat = pill._cat
            skey = pill.property("sys_key")
            self._apply_system_change(cat, skey, "install_module")
        except Exception:
            pass
        self.refresh()

    def _apply_legacy_tactic_change(self, attr, value, default, operation):
        """Apply a legacy game-management slider change through the canonical
        ownership flow (mirrors _apply_system_change).

        - GM owns the whiteboard -> apply directly via setattr.
        - Coach owns it -> STAGE the change in ``self._pending_legacy``
          (attr -> value); it flows through Suggest / Enforce / Take Over
          from the Coach tab. Control never flips here.
        - Reputation service unavailable while the coach owns the
          whiteboard -> block the mutation and show an actionable error
          instead of silently bypassing coach consequences (fail closed).
        """
        team = self._team
        if team is None:
            QMessageBox.warning(
                self, "Tactics",
                "No team is loaded. No changes were made.")
            return False
        if _tx is None:
            QMessageBox.warning(
                self, "Tactics",
                "The tactics engine is unavailable. No changes were made.")
            return False
        control = safe_call(
            lambda: _tx.get_tactics_control(team), "coach",
            context="tactics/get_control")
        if control == "gm":
            try:
                setattr(team, attr, value)
            except Exception:
                pass
            self._pending_legacy.pop(attr, None)
            self._legacy_msg = ""
            return True
        # Coach owns the whiteboard: stage, never write directly.
        if _rs is None:
            self._warn_rs_unavailable("legacy game-management change")
            return False
        current = safe_call(lambda: getattr(team, attr, default), default,
                            context="tactics/legacy_attr")
        if value == current:
            self._pending_legacy.pop(attr, None)
            self._legacy_msg = ""
            self.refresh()
            return True
        self._pending_legacy[attr] = value
        label = self._legacy_labels.get(attr, attr)
        self._legacy_msg = (
            f"Staged: {label} → {value}. "
            "Go to the Coach tab to Suggest, Enforce, or Take Over.")
        self.refresh()
        return False

    def _apply_staged_legacy(self):
        """Commit staged legacy game-management changes via setattr.

        Called at the same commit points that consume ``self._pending``
        (Suggest accept / Enforce / Take Over). Returns the count applied.
        """
        team = self._team
        staged = list(self._pending_legacy.items())
        self._pending_legacy.clear()
        self._legacy_msg = ""
        if team is None:
            return 0
        n = 0
        for attr, value in staged:
            try:
                setattr(team, attr, value)
                n += 1
            except Exception:
                pass
        return n

    def _on_legacy_pill_clicked(self):
        pill = self.sender()
        if pill is None:
            return
        try:
            attr = pill.property("tactic_attr")
            value = pill.property("tactic_value")
            default = pill.property("tactic_default")
            if attr and attr.startswith("tactic_"):
                self._apply_legacy_tactic_change(attr, value, default,
                                                 "legacy_pill")
        except Exception:
            pass
        self.refresh()

    # ------------------------------------------------------------ identity

    def _rebuild_identity_tab(self, lay):
        team = self._team
        sub = QLabel(
            "One click installs a unified identity across all seven modules. "
            "The room has to re-learn its reads — familiarity dips, then rebuilds.")
        sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        active = safe_call(lambda: _tx.matching_identity(team),
                           context="tactics/matching_identity")
        for key, p in _tx.IDENTITY_PRESETS.items():
            box = QGroupBox(p.get("name", key))
            box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 15px; }")
            bl = QVBoxLayout(box)
            head_row = QHBoxLayout()
            tag = QLabel(p.get("tagline", ""))
            tag.setStyleSheet(f"color: {DIM}; font-size: 12px; font-style: italic;")
            head_row.addWidget(tag)
            head_row.addStretch(1)
            if active == key:
                badge = QLabel("INSTALLED")
                badge.setStyleSheet(
                    f"color:{GOOD}; border:1px solid {GOOD}; border-radius:8px; "
                    "padding:2px 8px; font-size:11px; font-weight:bold;")
                head_row.addWidget(badge)
            bl.addLayout(head_row)
            blurb = QLabel(p.get("blurb", ""))
            blurb.setStyleSheet("font-size: 13px;")
            blurb.setWordWrap(True)
            bl.addWidget(blurb)
            mods = p.get("modules", {})
            grid = QGridLayout()
            for i, (c, s) in enumerate(mods.items()):
                sname = _tx.CATALOGS.get(c, {}).get(s, {}).get("name", s)
                cell = QLabel(
                    f"<span style='color:{DIM};'>{CATEGORY_LABELS.get(c, c)}</span>"
                    f"<br><b>{sname}</b>")
                cell.setStyleSheet("font-size: 12px;")
                grid.addWidget(cell, i // 4, i % 4)
            bl.addLayout(grid)
            ex = p.get("exemplars", []) or []
            if ex:
                ex_lab = QLabel("Exemplars: " + ", ".join(ex))
                ex_lab.setStyleSheet(f"color:{DIM}; font-size:11px;")
                ex_lab.setWordWrap(True)
                bl.addWidget(ex_lab)
            btn = QPushButton("Current Identity" if active == key
                              else "Install Identity")
            if active == key:
                btn.setEnabled(False)
            else:
                btn.setObjectName("primary-btn")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setProperty("preset_key", key)
                btn.clicked.connect(self._on_install_preset)
            bl.addWidget(btn)
            lay.addWidget(box)
        lay.addStretch(1)

    def _on_install_preset(self):
        btn = self.sender()
        if btn is None:
            return
        try:
            preset = btn.property("preset_key")
            meta = _tx.IDENTITY_PRESETS.get(preset, {})
            modules = meta.get("modules", {})
            control = safe_call(lambda: _tx.get_tactics_control(self._team),
                                "coach", context="tactics/get_control")
            if control == "gm":
                # The GM owns the whiteboard: install immediately.
                _tx.apply_identity_preset(self._team, preset)
                self._pending.clear()
            else:
                # Coach owns it: stage every differing module as pending
                # (mainline parity) -- Suggest / Enforce / Take Over consume
                # them from the Coach tab.
                try:
                    current = (safe_call(
                        lambda: _tx.team_tactics(self._team), {},
                        context="tactics/team_tactics") or {})
                except Exception:
                    current = {}
                n = 0
                for cat, key in modules.items():
                    catalog = _tx.CATALOGS.get(cat, {})
                    if key in catalog and current.get(cat) != key:
                        self._pending[cat] = key
                        n += 1
                name = meta.get("name", preset)
                self._coach_msg = (
                    f"{name} staged ({n} modules) -- suggest it to the coach "
                    "or enforce it from the Coach tab." if n else
                    f"{name} already installed.")
        except Exception:
            pass
        self.refresh()

    # ------------------------------------------------------------ analyst

    def _rebuild_analyst_tab(self, lay):
        team = self._team
        coach = self._head_coach(team)
        sub = QLabel(
            "Analyst suggestions from your roster, your coach, and what's "
            "actually hurting opponents on film.")
        sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        cards = []
        skaters = self._skaters(team)

        # 1. Roster-fit suggestions
        try:
            tk = _tx.team_tactics(team)
            for cat, _label, _attr in _tx.ALL_CATEGORIES:
                catalog = _tx.CATALOGS.get(cat, {})
                if not catalog or not skaters:
                    continue
                cur = tk.get(cat)
                fits = {}
                for skey in catalog:
                    try:
                        fits[skey] = (sum(_tx.player_system_fit(p, skey, cat)
                                          for p in skaters) / len(skaters))
                    except Exception:
                        fits[skey] = 1.0
                best = max(fits, key=lambda k: fits[k])
                if best != cur and fits[best] - fits.get(cur, 1.0) >= 0.04:
                    sys = catalog[best]
                    cards.append({
                        "kind": "roster",
                        "title": f"Personnel fit: {sys.get('name', best)}",
                        "text": (f"Your skaters grade {fits[best]:.0%} in "
                                 f"{sys.get('name', best)} vs "
                                 f"{fits.get(cur, 1.0):.0%} in the current "
                                 f"{CATEGORY_LABELS.get(cat, cat)} system. "
                                 f"{sys.get('blurb', '')[:180]}"),
                        "action_label": "Install it",
                        "action": ("system", cat, best),
                    })
                if len([c for c in cards if c["kind"] == "roster"]) >= 3:
                    break
        except Exception:
            pass

        # 2. Coach fit
        try:
            if coach is not None:
                prefs = _tx.ensure_coach_tactics(coach)
                mine = _tx.team_tactics(team)
                style = "Balanced"
                if _rs is not None:
                    style = safe_call(
                        lambda: _rs.coach_style(coach).get("label", "Balanced"),
                        "Balanced", context="tactics/coach_style")
                mism = []
                for cat, _label, _attr in _tx.ALL_CATEGORIES:
                    want = prefs.get(cat)
                    if want and want != mine.get(cat):
                        cat_dict = _tx.CATALOGS.get(cat, {})
                        mism.append(
                            f"{CATEGORY_LABELS.get(cat, cat)}: he wants "
                            f"{cat_dict.get(want, {}).get('name', want)}")
                fit = _tx.coach_tactics_fit(coach, team)
                cname = str(safe_call(lambda: getattr(coach, "full_name",
                                                 "Coach"), "Coach",
                                      context="tactics/coach_name"))
                if mism:
                    cards.append({
                        "kind": "coach",
                        "title": f"{cname} ({style}) disagrees with the whiteboard",
                        "text": (f"Coach-system fit is {fit:.0%}. "
                                 f"{len(mism)} of 7 modules differ from what he'd run: "
                                 + "; ".join(mism[:4])
                                 + (f" (+{len(mism) - 4} more)"
                                    if len(mism) > 4 else "")
                                 + ". A coach running someone else's systems coaches worse."),
                        "action_label": "Let him install his systems",
                        "action": ("hand_back_whiteboard",),
                    })
        except Exception:
            pass

        # 3. Opponent intel
        try:
            league = safe_call(lambda: self._gm.league,
                             context="tactics/league_teams")
            teams = safe_call(lambda: list(league.teams), [],
                              context="tactics/league_teams") or []
            hits = []
            for ai in teams:
                if ai is team:
                    continue
                if not getattr(ai, "tactical_intel", None):
                    continue
                for cat, sys_key, heat in _tx.damaging_user_systems(ai, team):
                    aname = safe_call(lambda: getattr(ai, "team_name", "?"), "?",
                                      context="tactics/league_teams")
                    sname = _tx.CATALOGS.get(cat, {}).get(
                        sys_key, {}).get("name", sys_key)
                    hits.append((heat, aname, CATEGORY_LABELS.get(cat, cat),
                                 sname))
            hits.sort(reverse=True)
            for heat, aname, clabel, sname in hits[:2]:
                cards.append({
                    "kind": "opponent",
                    "title": f"Intel: your {clabel.lower()} is torching {aname}",
                    "text": (f"Across recent meetings your {sname} is producing "
                             f"{heat:.1f}x the damage threshold against them. "
                             f"They've seen it on film — expect an answer soon."),
                    "action_label": None,
                    "action": None,
                })
            if not hits and teams:
                cards.append({
                    "kind": "opponent",
                    "title": "No damaging trends on film yet",
                    "text": ("Rival coaches need at least two meetings against a "
                             "system before it shows up here. Nothing you're "
                             "running is consistently hurting anyone yet."),
                    "action_label": None,
                    "action": None,
                })
        except Exception:
            pass

        # 4. Familiarity
        try:
            fam = float(safe_call(lambda: getattr(team, "tactics_familiarity",
                                             85), 85,
                                      context="tactics/familiarity"))
            if fam < 70:
                cards.append({
                    "kind": "familiarity",
                    "title": f"Room still learning ({fam:.0f}/100)",
                    "text": ("New systems play muted until the reads are "
                             "automatic — every edge is dampened toward average "
                             "while familiarity rebuilds. It ticks up every game. "
                             "Avoid more changes until it settles."),
                    "action_label": None,
                    "action": None,
                })
        except Exception:
            pass

        if not cards:
            empty = QLabel("No analyst notes right now. The whiteboard looks sound.")
            empty.setStyleSheet(f"color: {DIM}; font-size: 13px;")
            lay.addWidget(empty)
        for card in cards:
            box = QGroupBox()
            bl = QVBoxLayout(box)
            kind_lab = QLabel(card["kind"].upper())
            kind_lab.setStyleSheet(f"color: {DIM}; font-size: 11px;")
            bl.addWidget(kind_lab)
            title_lab = QLabel(f"<b style='font-size:14px;'>{card['title']}</b>")
            title_lab.setWordWrap(True)
            bl.addWidget(title_lab)
            text_lab = QLabel(card["text"])
            text_lab.setStyleSheet("font-size: 13px;")
            text_lab.setWordWrap(True)
            bl.addWidget(text_lab)
            if card.get("action"):
                btn = QPushButton(card["action_label"])
                btn.setCursor(Qt.PointingHandCursor)
                btn.setProperty("intel_action", card["action"])
                btn.clicked.connect(self._on_intel_action)
                bl.addWidget(btn)
            lay.addWidget(box)
        lay.addStretch(1)

    def _on_intel_action(self):
        btn = self.sender()
        if btn is None:
            return
        action = btn.property("intel_action")
        if not action:
            return
        try:
            if action[0] == "system":
                cat, skey = action[1], action[2]
                self._apply_system_change(cat, skey, "intel_action")
            elif action[0] == "hand_back_whiteboard":
                self._hand_back_whiteboard()
        except Exception:
            pass
        self.refresh()

    # -------------------------------------------------------------- coach

    def _rebuild_coach_tab(self, lay):
        team = self._team
        coach = self._head_coach(team)
        if coach is None:
            lay.addWidget(QLabel("No head coach on staff."))
            lay.addStretch(1)
            return
        try:
            style = ("Balanced" if _rs is None else safe_call(
                lambda: _rs.coach_style(coach).get("label", "Balanced"),
                "Balanced", context="tactics/coach_style"))
        except Exception:
            style = "Balanced"
        prefs = safe_call(lambda: _tx.ensure_coach_tactics(coach), {},
                        context="tactics/coach_prefs") or {}
        mine = safe_call(lambda: _tx.team_tactics(team), {},
                         context="tactics/team_tactics") or {}
        fit = safe_call(lambda: _tx.coach_tactics_fit(coach, team),
                        context="tactics/coach_fit")
        control = safe_call(lambda: _tx.get_tactics_control(team), "coach",
                            context="tactics/get_control")
        cname = str(safe_call(lambda: getattr(coach, "full_name", "Coach"),
                         "Coach", context="tactics/coach_name"))

        # Whiteboard control
        self._section("Whiteboard Control", lay)
        info = QLabel(
            f"<b>{cname}</b> · {style} · coach-system fit "
            f"{fit * 100:.0f}%." if fit is not None else f"<b>{cname}</b> · {style}.")
        info.setStyleSheet("font-size: 13px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        ctl = QLabel(
            "He owns the whiteboard — he may adjust systems between periods."
            if control == "coach"
            else "You own the whiteboard — he coaches the systems you install.")
        ctl.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        ctl.setWordWrap(True)
        lay.addWidget(ctl)
        ctl_row = QHBoxLayout()
        wb_coach = QPushButton("Coach Controls")
        wb_gm = QPushButton("I Control")
        if control == "coach":
            wb_coach.setObjectName("primary-btn")
        else:
            wb_gm.setObjectName("primary-btn")
        for b, who in ((wb_coach, "coach"), (wb_gm, "gm")):
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("control_who", who)
            b.clicked.connect(self._on_set_control)
            ctl_row.addWidget(b)
        ctl_row.addStretch(1)
        lay.addLayout(ctl_row)

        # His systems vs yours
        self._section("His Systems vs Yours", lay)
        sub = QLabel(
            "What your head coach would run, from his coaching style — "
            "against what's on the whiteboard now.")
        sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ["Phase", "Coach wants", "Currently running", ""])
        rows = []
        for cat, _label, _attr in _tx.ALL_CATEGORIES:
            want = prefs.get(cat)
            cur = mine.get(cat)
            cat_dict = _tx.CATALOGS.get(cat, {})
            rows.append({
                "category": CATEGORY_LABELS.get(cat, cat),
                "coach_wants": (cat_dict.get(want, {}).get("name", want)
                                if want else "—"),
                "coach_wants_key": want,
                "current": (cat_dict.get(cur, {}).get("name", cur)
                            if cur else "—"),
                "match": bool(want and want == cur),
            })
        table.setRowCount(len(rows))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for i, r in enumerate(rows):
            for j, key in (0, "category"), (1, "coach_wants"), (2, "current"):
                table.setItem(i, j, QTableWidgetItem(str(r[key])))
            tag = QTableWidgetItem("Aligned" if r["match"] else "Differs")
            tag.setForeground(Qt.green if r["match"] else Qt.yellow)
            table.setItem(i, 3, tag)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setFixedHeight(min(34 + 30 * len(rows), 280))
        lay.addWidget(table)

        # Coach actions
        self._section("Coach Actions", lay)
        act_sub = QLabel(
            "Stage systems on the Systems tab, then act here. <b>Suggest</b> "
            "asks him to adopt your staged changes. <b>Enforce</b> overrules "
            "him ONCE for those changes — he keeps the whiteboard and stays "
            "in charge of mid-game adjustments. <b>Take Over</b> seizes the "
            "whiteboard PERMANENTLY (his personality decides how he takes "
            "it). <b>Hand Back</b> returns it to him -- your systems stay "
            "on the board as you left them.")
        act_sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        act_sub.setWordWrap(True)
        lay.addWidget(act_sub)
        act_row = QHBoxLayout()
        suggest_btn = QPushButton("Suggest to Coach")
        enforce_btn = QPushButton("Enforce My Systems")
        takeover_btn = QPushButton("Take Over Whiteboard")
        handback_btn = QPushButton("Hand Back Whiteboard")
        suggest_btn.setObjectName("primary-btn")
        for b in (suggest_btn, enforce_btn, takeover_btn, handback_btn):
            b.setCursor(Qt.PointingHandCursor)
            act_row.addWidget(b)
        act_row.addStretch(1)
        lay.addLayout(act_row)

        pref_row = QHBoxLayout()
        save_pref_btn = QPushButton("Save as Preferred")
        load_pref_btn = QPushButton("Load Preferred")
        for b in (save_pref_btn, load_pref_btn):
            b.setCursor(Qt.PointingHandCursor)
            pref_row.addWidget(b)
        pref_row.addStretch(1)
        lay.addLayout(pref_row)

        self._coach_suggest_out = QLabel(self._coach_msg)
        self._coach_suggest_out.setStyleSheet(f"color: {DIM}; font-size: 13px;")
        self._coach_suggest_out.setWordWrap(True)
        lay.addWidget(self._coach_suggest_out)

        def _show_recommendation():
            mism = [r for r in rows if not r["match"]]
            last = cname.split(" ")[-1]
            if mism:
                parts = "; ".join(
                    f"{r['category']} to <b>{r['coach_wants']}</b>"
                    for r in mism)
                self._coach_msg = (
                    f"<b>{last}'s recommendation ({style}):</b> switch {parts}. "
                    "Or hand him the whiteboard and let him install it all.")
            else:
                self._coach_msg = (
                    f"He's happy — all seven modules already match his "
                    f"{style} preferences.")
            self.refresh()

        def _suggest():
            # T7: fail closed with an actionable warning, not a shrug.
            if _rs is None:
                self._warn_rs_unavailable("suggestion")
                return
            if not self._pending and not self._pending_legacy:
                _show_recommendation()
                return
            # T3: when the GM owns the whiteboard there is no coach to
            # suggest to -- clicks apply immediately, so pending should be
            # empty; refuse rather than running a coach-overrule path.
            if safe_call(lambda: _tx.get_tactics_control(team), "coach",
                         context="tactics/get_control") == "gm":
                self._coach_msg = (
                    "You already own the whiteboard -- your changes apply "
                    "immediately, so there is nothing to suggest.")
                self.refresh()
                return
            if not self._pending:
                # Legacy-only stages: the coach's preview/summary engine is
                # keyed on whiteboard categories, so Suggest can't float
                # game-management sliders past him -- Enforce or Take Over
                # applies them instead.
                self._coach_msg = (
                    "Only game-management tweaks are staged — the coach "
                    "discusses whiteboard systems over Suggest, not "
                    "game-management sliders. Use Enforce or Take Over to "
                    "put the staged tweaks in.")
                self.refresh()
                return
            res = {}
            try:
                res = _rs.suggest_tactics_to_coach(
                    team, dict(self._pending),
                    self._team_context()) or {}
            except Exception:
                res = {}
            if not res:
                self._warn_rs_unavailable("suggestion")
                return
            if res.get("applied"):
                self._pending.clear()
                # Staged legacy sliders ride along with the accepted
                # package: the coach bought in, so commit them too.
                n_legacy = self._apply_staged_legacy()
                text = res.get("text", "")
                if n_legacy:
                    text += (f" ({n_legacy} game-management tweak"
                             f"{'s' if n_legacy != 1 else ''} applied too.)")
                if text:
                    self._push_tactics_news(f"Tactics: {text}")
                self._coach_msg = text
            else:
                self._coach_msg = res.get("text", "")
            self.refresh()

        def _enforce():
            # ONE-TIME overrule (mainline parity): rs.enforce_tactics applies
            # the staged changes for the next game and dings trust/morale --
            # it NEVER flips whiteboard control. The permanent flip is the
            # separate Take Over path below; take_over_tactics must not be
            # called from here.
            # T7: fail closed with an actionable warning, not a shrug.
            if _rs is None:
                self._warn_rs_unavailable("enforcement")
                return
            if not self._pending and not self._pending_legacy:
                self._coach_msg = ("Nothing staged — pick systems or "
                                   "game-management tweaks on the Systems "
                                   "tab first.")
                self.refresh()
                return
            # T3: when the GM owns the whiteboard there was no overrule --
            # running enforce_tactics would apply the staged changes AND
            # ding trust/morale "over the coach's objections" unjustifiably.
            if safe_call(lambda: _tx.get_tactics_control(team), "coach",
                         context="tactics/get_control") == "gm":
                self._coach_msg = (
                    "You already own the whiteboard -- there is no coach "
                    "to overrule.")
                self.refresh()
                return
            ans = QMessageBox.question(
                self, "Enforce Tactics",
                "Overrule your head coach and enforce these systems?\n"
                "It works -- and he won't forget it.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
            if not self._pending:
                # Legacy-only enforce: the trust/morale engine is keyed on
                # whiteboard categories (an empty package would crash its
                # summary), so commit the staged game-management tweaks
                # directly -- the GM confirmed the overrule above.
                n = self._apply_staged_legacy()
                self._coach_msg = (
                    f"Enforced {n} game-management tweak"
                    f"{'s' if n != 1 else ''} over the coach's objections.")
                self._push_tactics_news(f"Tactics: {self._coach_msg}")
                self.refresh()
                return
            res = {}
            try:
                res = _rs.enforce_tactics(
                    team, dict(self._pending),
                    self._team_context()) or {}
            except Exception:
                res = {}
            if not res:
                self._warn_rs_unavailable("enforcement")
                return
            if res.get("applied"):
                self._pending.clear()
                # Staged legacy sliders ride along with the enforced
                # package: commit them too.
                n_legacy = self._apply_staged_legacy()
                text = res.get("text", "")
                if n_legacy:
                    text += (f" ({n_legacy} game-management tweak"
                             f"{'s' if n_legacy != 1 else ''} applied too.)")
                if text:
                    self._push_tactics_news(f"Tactics: {text}")
                self._coach_msg = text
            else:
                self._coach_msg = res.get("text", "")
            self.refresh()

        def _takeover():
            # PERMANENT path (mainline parity): the GM takes the whiteboard.
            # Routes through the shared confirmed-takeover flow (same
            # permanence disclosure as the "I Control" button) -- this is
            # the explicit, confirmed seizure path.
            self._confirmed_takeover()

        def _save_pref():
            try:
                _tx.save_preferred_tactics(team)
                self._coach_msg = ("Preferred tactics saved -- one click "
                                   "gets you back to your hockey.")
            except Exception as e:
                self._coach_msg = f"Could not save: {e}"
            self.refresh()

        def _load_pref():
            try:
                pref = _tx.get_preferred_tactics(team)
            except Exception:
                pref = None
            if not pref:
                self._coach_msg = "No preferred tactics saved yet."
                self.refresh()
                return
            try:
                current = (safe_call(lambda: _tx.team_tactics(team), {},
                                     context="tactics/team_tactics") or {})
            except Exception:
                current = {}
            self._pending = {c: k for c, k in pref.items()
                             if current.get(c) != k}
            if safe_call(lambda: _tx.get_tactics_control(team), "coach",
                         context="tactics/get_control") == "gm":
                try:
                    for cat, key in list(self._pending.items()):
                        _tx.set_team_system(team, cat, key)
                    self._pending.clear()
                except Exception:
                    pass
                self._coach_msg = "Preferred tactics installed."
            else:
                self._coach_msg = ("Preferred tactics staged -- suggest them "
                                   "to your coach, enforce them, or take "
                                   "over.")
            self.refresh()

        suggest_btn.clicked.connect(_suggest)
        enforce_btn.clicked.connect(_enforce)
        takeover_btn.clicked.connect(_takeover)
        handback_btn.clicked.connect(self._hand_back_refresh)
        save_pref_btn.clicked.connect(_save_pref)
        load_pref_btn.clicked.connect(_load_pref)
        lay.addStretch(1)

    def _warn_rs_unavailable(self, action):
        """Fail-closed warning when the reputation service can't be reached.

        Same actionable pattern as _apply_system_change: no raw control
        flip, no silent shrug -- the mutation is blocked and the user is
        told what to do.
        """
        QMessageBox.warning(
            self, "Tactics",
            f"The reputation service is unavailable, so the {action} "
            "cannot be made with the coach's personality consequences "
            "applied. No changes were made. Restart the application and "
            "try again.")

    def _confirmed_takeover(self):
        """PERMANENT whiteboard seizure with permanence disclosure (mainline).

        Shared by the Coach tab's "Take Over Whiteboard" button and the
        "I Control" control button -- take_over_tactics is permanent and
        personality-reactive, so BOTH routes go through the same confirm
        dialog. Applies and clears staged changes on success (pending is
        yours once you own the board). Fail-closed when the reputation
        service is unavailable: no raw control flip.
        Returns True if the takeover ran, False on cancel/unavailable.
        """
        team = self._team
        # T4: _rs is None -> block with an actionable warning, never a
        # consequence-free raw flip that pretends the full path ran.
        if _rs is None:
            self._warn_rs_unavailable("takeover")
            return False
        ans = QMessageBox.question(
            self, "Take Over Whiteboard",
            "Take permanent control of tactics from your head coach?\n"
            "His reaction will depend on his personality.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return False
        res = {}
        try:
            res = _rs.take_over_tactics(team, self._team_context()) or {}
        except Exception:
            res = {}
        if not res:
            # Engine call failed mid-path -- fail closed, never flip raw.
            self._warn_rs_unavailable("takeover")
            return False
        if res.get("changed"):
            # Pending changes are yours now -- apply them (mainline).
            try:
                for cat, key in list(self._pending.items()):
                    _tx.set_team_system(team, cat, key)
                self._pending.clear()
                # Staged legacy game-management tweaks are yours now too.
                self._apply_staged_legacy()
            except Exception:
                pass
            text = res.get("text", "")
            if text:
                self._push_tactics_news(f"Tactics: {text}")
        self._coach_msg = res.get(
            "text",
            "Whiteboard is yours. He will coach your systems and stop "
            "adjusting mid-game.")
        self.refresh()
        return True

    def _hand_back_whiteboard(self):
        team = self._team
        # Personality-safe handback: trust repair, morale shift and room
        # event fire inside (mainline parity). hand_back_tactics flips
        # control to "coach" internally; the engine docstring says
        # "Systems stay; trust is repaired" and the QA suite pins handback
        # as control-flip + trust repair only -- install_coach_systems is
        # the head-coach-hire path, never a handback side effect (it also
        # silently resets familiarity to 55). T5.
        if _rs is None:
            self._warn_rs_unavailable("handback")
            return
        res = {}
        try:
            res = _rs.hand_back_tactics(team) or {}
        except Exception:
            res = {}
        if not res:
            self._warn_rs_unavailable("handback")
            return
        if res.get("changed"):
            self._push_tactics_news(res.get("text", ""))

    def _hand_back_refresh(self):
        self._hand_back_whiteboard()
        self.refresh()

    def _on_set_control(self):
        btn = self.sender()
        if btn is None:
            return
        who = btn.property("control_who")
        who = who if who in ("coach", "gm") else "coach"
        # Route through the personality engine so trust/morale/room-event
        # consequences fire (mainline parity); never flip control raw.
        # T1/T4: the "I Control" (gm) branch is a PERMANENT,
        # personality-reactive takeover, so it runs through the SAME
        # confirmed seizure flow as "Take Over Whiteboard" (same
        # permanence disclosure dialog) instead of calling
        # take_over_tactics unconfirmed. The "coach" branch is the same
        # handback the "Hand Back Whiteboard" button runs.
        if _rs is None:
            self._warn_rs_unavailable("whiteboard change")
            return
        if who == "gm":
            self._confirmed_takeover()
        else:
            self._hand_back_whiteboard()
        self.refresh()

    # ------------------------------------------------------------ practice

    def _refresh_practice_labels(self):
        # dressing_room pulls in customtkinter at module scope; guard it.
        try:
            _dr = importlib.import_module("dressing_room")
            self._foci_labels = {
                k: v.get("label", k)
                for k, v in _dr.PRACTICE_FOCI.items()}
            self._int_labels = {
                k: v.get("label", k)
                for k, v in _dr.PRACTICE_INTENSITIES.items()}
        except Exception:
            self._foci_labels = dict(_PRACTICE_FOCI_FALLBACK)
            self._int_labels = dict(_PRACTICE_INT_FALLBACK)

    def _practice_plan(self):
        plan = safe_call(lambda: (getattr(self._team, "dressing_room", None)
                                  or {}).get("practice_plan"),
                         context="tactics/practice_plan") or {}
        return plan

    def _rebuild_practice_tab(self, lay):
        plan = self._practice_plan()
        self._practice_focus = plan.get("focus", "systems")
        self._practice_intensity = plan.get("intensity", "moderate")
        bag = bool(plan.get("bag_skate", False))

        self._section("Weekly Practice Planner", lay)
        sub = QLabel(
            "Set the week's focus. The plan repeats every Sunday until you "
            "change it.")
        sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        focus_head = QLabel("FOCUS")
        focus_head.setObjectName("section-header")
        lay.addWidget(focus_head)
        focus_row = QHBoxLayout()
        self._focus_pills = []
        for key, label in self._foci_labels.items():
            pill = self._make_pill(label, active=(key == self._practice_focus))
            pill.setProperty("focus_key", key)
            pill.clicked.connect(self._on_focus_pill)
            self._focus_pills.append(pill)
            focus_row.addWidget(pill)
        focus_row.addStretch(1)
        lay.addLayout(focus_row)

        int_head = QLabel("INTENSITY")
        int_head.setObjectName("section-header")
        lay.addWidget(int_head)
        int_row = QHBoxLayout()
        self._int_pills = []
        for key, label in self._int_labels.items():
            pill = self._make_pill(label, active=(key == self._practice_intensity))
            pill.setProperty("intensity_key", key)
            pill.clicked.connect(self._on_intensity_pill)
            self._int_pills.append(pill)
            int_row.addWidget(pill)
        int_row.addStretch(1)
        lay.addLayout(int_row)

        self._bag_check = QCheckBox("Bag skate (punishment skate)")
        self._bag_check.setChecked(bag)
        lay.addWidget(self._bag_check)
        bag_note = QLabel(
            "May stop a slide now (+2% one-game compete edge). Repeated "
            "punishment erodes trust — every skate is logged.")
        bag_note.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        bag_note.setWordWrap(True)
        lay.addWidget(bag_note)

        save = QPushButton("Set Weekly Practice Plan")
        save.setObjectName("primary-btn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._on_save_practice)
        lay.addWidget(save)
        self._practice_out = QLabel("")
        self._practice_out.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        self._practice_out.setWordWrap(True)
        lay.addWidget(self._practice_out)
        lay.addStretch(1)

    def _on_focus_pill(self):
        pill = self.sender()
        self._practice_focus = pill.property("focus_key")
        for p in self._focus_pills:
            p.setChecked(p is pill)

    def _on_intensity_pill(self):
        pill = self.sender()
        self._practice_intensity = pill.property("intensity_key")
        for p in self._int_pills:
            p.setChecked(p is pill)

    def _on_save_practice(self):
        team = self._team
        try:
            dr = getattr(team, "dressing_room", None)
            if not isinstance(dr, dict):
                dr = {}
            plan = dr.get("practice_plan")
            if not isinstance(plan, dict):
                plan = {}
            plan["focus"] = self._practice_focus
            plan["intensity"] = self._practice_intensity
            plan["bag_skate"] = bool(self._bag_check.isChecked())
            dr["practice_plan"] = plan
            team.dressing_room = dr
            fl = self._foci_labels.get(self._practice_focus,
                                       self._practice_focus)
            il = self._int_labels.get(self._practice_intensity,
                                      self._practice_intensity)
            self._practice_out.setText(
                f"Practice plan set: {fl} focus, {il} intensity"
                + (" — bag skate on." if plan["bag_skate"] else "."))
        except Exception:
            self._practice_out.setText("Couldn't save the practice plan.")
