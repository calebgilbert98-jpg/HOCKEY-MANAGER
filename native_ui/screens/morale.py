"""Team Morale / Dressing Room (native Qt port).

Port of web_ui/screens/morale.py (itself migrated from Tkinter
MoraleView / morale_window.py).

Six tabs: Room | Social Groups | Cascades | Team Talk | Rivalries |
Coach Carousel. GM action buttons (Bag Skate, Speech, Practice, Back Room,
Advise Coach, Line Control) call the game logic directly -- no HTTP, no
command queue.

Data sources (all called on self.game, wrapped in try/except):
  reputation_system: team_chemistry, team_hierarchy, hierarchy_score,
      player_coach_response, engagement_style, detect_dynamics_issues,
      get_dynamics_feed, coach_style, apply_bag_skate,
      apply_inspiring_speech, apply_great_practice, advise_coach,
      unfeature_player, ADVICE_TYPES, get_rivalries_for,
      declared_rivalries_for, declare_rivalry_for_gm,
      renounce_rivalry_for_gm
  dressing_room:     form_cliques, floaters, room_atmosphere,
      ensure_dressing_room_fields, integration_of, captain_of,
      influence_of, give_talk, TONE_FIT, _coach_influence, _name,
      _room_head_coach, coach_demanding_axis, coaching_candidates,
      fire_coach, hire_coach, detect_captaincy_crisis,
      resolve_captaincy_crisis
  media_engine:      gm_public_backing
"""
from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QFrame,
    QScrollArea, QComboBox, QSpinBox, QCheckBox, QDialog, QGroupBox,
    QButtonGroup,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from .base import BaseScreen

try:
    import reputation_system as _rs
except Exception:
    _rs = None

try:
    import dressing_room as _dr
except Exception:
    _dr = None

try:
    import media_engine as _me
except Exception:
    _me = None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _role_str(s):
    """Staff role as display string, enum-aware (mirrors web_ui.bridge)."""
    try:
        return str(getattr(getattr(s, "role", None), "value",
                           getattr(s, "role", "") or ""))
    except Exception:
        return ""


def _safe(fn, default=None):
    try:
        v = fn()
        return default if v is None else v
    except Exception:
        return default


def _bar_color(v):
    if v >= 65:
        return "#4CAF50"
    if v >= 50:
        return "#FFC107"
    return "#F44336"


TIER_LABEL = {
    "landed": "Landed (+2)",
    "steady": "Steady (+1)",
    "flat": "Flat (0)",
    "backfired": "Backfired (\u22121)",
}

CRISIS_CHOICES = [
    ("keep", "Back him publicly",
     "The C stays. The room steadies, barely \u2014 he is on notice, not exonerated."),
    ("challenge", "Challenge him privately",
     "Behind closed doors. He responds (leadership +3) or resents it (trade-request risk up)."),
    ("strip", "Strip the C",
     "The C comes off. Loyalists grieve, the rest exhale. No successor named."),
    ("reassign", "Reassign the C",
     "Hand the C to a named successor. Legitimacy decides whether the room buys it."),
]

TALK_TONES = [
    ("calm", "Calm",
     "Steadies nerves. Best when tied or protecting a lead \u2014 and the tone losing streaks crave."),
    ("fired-up", "Fired Up",
     "Chases a deficit. Electric when trailing or in rivalry games; reads as panic when comfortably ahead."),
    ("cautious", "Cautious",
     "Protects a lead. Locks in structure \u2014 the intermission talk of a coach sitting on two goals."),
]


class _PillGroup(QWidget):
    """Exclusive toggle-pills row (tone pills, situation pills, score pills)."""

    def __init__(self, options, default=None, parent=None):
        """options: list of (key, label)."""
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for key, label in options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName("pill")
            layout.addWidget(btn)
            self._group.addButton(btn)
            self._buttons[key] = btn
            if key == (default if default is not None
                       else options[0][0]):
                btn.setChecked(True)
        layout.addStretch()

    def value(self):
        for key, btn in self._buttons.items():
            if btn.isChecked():
                return key
        return None

    def set_value(self, key):
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def connect(self, fn):
        self._group.buttonClicked.connect(lambda _b: fn())


# ----------------------------------------------------------------------
# Advise Coach dialog (port of morale_window.AdviseCoachPopup)
# ----------------------------------------------------------------------

class AdviseCoachDialog(QDialog):
    """Advise the coach: advice-type buttons, feature-player picker,
    request/rescind, result showing LISTENED/IGNORED (p=NN%)."""

    def __init__(self, game, team, coach, roster, parent=None):
        super().__init__(parent)
        self._game = game
        self._team = team
        self._coach = coach
        self._roster = list(roster or [])
        self.setWindowTitle("Advise the Coach")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        sub = QLabel(
            f"{_safe(lambda: getattr(coach, 'full_name', 'Coach'), 'Coach')} "
            f"\u00b7 GM trust {_safe(lambda: int(getattr(coach, 'gm_trust', 70) or 70), 70)}/100 "
            "\u2014 whether he listens depends on personality; brash coaches take advice as an insult.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        layout.addWidget(sub)

        self._type_buttons = []
        types_box = QGroupBox("Advice")
        types_layout = QVBoxLayout(types_box)
        row = QHBoxLayout()
        row.setSpacing(6)
        advice_types = []
        if _rs is not None:
            try:
                advice_types = list(_rs.ADVICE_TYPES.items())
            except Exception:
                advice_types = []
        n = 0
        for key, label in advice_types:
            if key == "feature_player":
                continue
            btn = QPushButton(str(label))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c, k=key: self._send_advice(k))
            row.addWidget(btn)
            self._type_buttons.append(btn)
            n += 1
            if n % 3 == 0:
                types_layout.addLayout(row)
                row = QHBoxLayout()
                row.setSpacing(6)
        if n % 3:
            row.addStretch()
            types_layout.addLayout(row)
        layout.addWidget(types_box)

        feat_box = QGroupBox("Feature a player \u2014 more ice time, bigger role")
        feat_layout = QHBoxLayout(feat_box)
        self._feature_pick = QComboBox()
        self._feature_pick.setMinimumWidth(200)
        for p in self._roster:
            pid = _safe(lambda: str(getattr(p, "id", "")), "")
            name = _safe(lambda: getattr(p, "full_name", "?"), "?")
            self._feature_pick.addItem(name, pid)
        feat_layout.addWidget(self._feature_pick)
        req = QPushButton("Request")
        req.clicked.connect(lambda: self._send_advice(
            "feature_player", self._feature_pick.currentData()))
        feat_layout.addWidget(req)
        rescind = QPushButton("Rescind")
        rescind.clicked.connect(lambda: self._send_advice(
            "feature_player", self._feature_pick.currentData(), unfeature=True))
        feat_layout.addWidget(rescind)
        feat_layout.addStretch()
        layout.addWidget(feat_box)

        featured = ""
        for p in self._roster:
            try:
                if getattr(p, "usage_featured", False):
                    featured = _safe(
                        lambda: getattr(p, "full_name", "?"), "?")
                    break
            except Exception:
                continue
        if featured:
            f_lbl = QLabel(f"Currently featured: {featured}. Rescind to hand usage back to the coach.")
            f_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            layout.addWidget(f_lbl)

        self._result = QLabel("")
        self._result.setWordWrap(True)
        self._result.setStyleSheet("font-size: 13px;")
        layout.addWidget(self._result)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _send_advice(self, advice, player_id="", unfeature=False):
        if _rs is None or self._coach is None:
            self._result.setText("No head coach on staff.")
            return
        self._result.setText("Advising\u2026")
        target = None
        if player_id:
            for p in self._roster:
                try:
                    if str(getattr(p, "id", "")) == str(player_id):
                        target = p
                        break
                except Exception:
                    continue
        try:
            if unfeature and target is not None:
                out = _rs.unfeature_player(self._coach, target, self._team)
            else:
                out = _rs.advise_coach(
                    self._coach, advice, self._team, self._roster,
                    target_player=target)
        except Exception as e:
            self._result.setText(f"Advice lost in the noise: {e}")
            return
        if out is None:
            self._result.setText("No coach or no advice given.")
            return
        listened = bool(out.get("listened", out.get("ok", False)))
        prob = out.get("probability")
        ptxt = f" (p={round(prob * 100)}%)" if prob is not None else ""
        word = "LISTENED" if listened else "IGNORED"
        color = "#4CAF50" if listened else "#F44336"
        text = _safe(lambda: out.get("text", ""), "")
        self._result.setText(
            f"<b style='color:{color}'>{word}{ptxt}</b>: {text}")
        parent_screen = self.parent()
        if hasattr(parent_screen, "refresh"):
            QTimer.singleShot(800, parent_screen.refresh)


# ----------------------------------------------------------------------
# Morale screen
# ----------------------------------------------------------------------

class MoraleScreen(BaseScreen):
    """Dressing-room management: six tabs, GM actions, talk composer,
    rivalries, crisis banner, coach carousel with two-step fire."""

    title = "Morale"

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _build_body(self):
        self._crisis_frame = QFrame()
        self._crisis_frame.setObjectName("tile")
        self._crisis_frame.setStyleSheet(
            "#tile { border: 2px solid #F44336; }")
        self._crisis_frame.hide()
        crisis_layout = QVBoxLayout(self._crisis_frame)
        self._crisis_head = QLabel("")
        self._crisis_head.setWordWrap(True)
        crisis_layout.addWidget(self._crisis_head)
        self._crisis_choices = QHBoxLayout()
        crisis_layout.addLayout(self._crisis_choices)
        self._crisis_successor_row = QWidget()
        suc_layout = QHBoxLayout(self._crisis_successor_row)
        suc_layout.setContentsMargins(0, 0, 0, 0)
        suc_layout.addWidget(QLabel("Successor:"))
        self._crisis_successor_pick = QComboBox()
        suc_layout.addWidget(self._crisis_successor_pick)
        suc_confirm = QPushButton("Confirm reassign")
        suc_confirm.clicked.connect(self._resolve_crisis_reassign)
        suc_layout.addWidget(suc_confirm)
        suc_layout.addStretch()
        self._crisis_successor_row.hide()
        crisis_layout.addWidget(self._crisis_successor_row)
        self._crisis_result = QLabel("")
        self._crisis_result.setWordWrap(True)
        crisis_layout.addWidget(self._crisis_result)
        self._layout.addWidget(self._crisis_frame)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.North)

        self._room_tab = self._make_room_tab()
        self._groups_tab = self._make_groups_tab()
        self._cascades_tab = self._make_cascades_tab()
        self._talk_tab = self._make_talk_tab()
        self._rivalries_tab = self._make_rivalries_tab()
        self._coach_tab = self._make_coach_tab()

        self._tabs.addTab(self._room_tab, "Room")
        self._tabs.addTab(self._groups_tab, "Social Groups")
        self._tabs.addTab(self._cascades_tab, "Cascades")
        self._tabs.addTab(self._talk_tab, "Team Talk")
        self._tabs.addTab(self._rivalries_tab, "Rivalries")
        self._tabs.addTab(self._coach_tab, "Coach Carousel")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._layout.addWidget(self._tabs, 1)

        self._loaded = set()
        self.refresh()

    # ------------------------------------------------------------------
    # Game access
    # ------------------------------------------------------------------
    def _resolve(self):
        """Return (gm, team, league), tolerant of app vs gm objects."""
        try:
            gm = getattr(self.game, "game_manager", None) or self.game
            team = (getattr(gm, "user_team", None)
                    or getattr(self.game, "user_team", None))
            league = (getattr(gm, "league", None)
                      or getattr(self.game, "league", None))
            return gm, team, league
        except Exception:
            return None, None, None

    def _date_str(self):
        return _safe(lambda: self.game.current_date.isoformat(), "")

    @staticmethod
    def _head_coach(team):
        try:
            for s in list(getattr(team, "staff", []) or []):
                if "head coach" in _role_str(s).lower():
                    return s
        except Exception:
            pass
        return None

    def _team_context(self):
        """Mirror mainline morale_window._team_context.

        Builds the win_pct / room_leadership / losing_streak context that
        reputation_system.set_line_control needs to decide consequences
        (e.g. seizing the lines on a WINNING team enrages strong
        personalities; on a losing team the room understands).
        """
        ctx = {"win_pct": 0.5, "room_leadership": 50, "losing_streak": 0}
        try:
            gm, team, league = self._resolve()
            if team is None:
                return ctx
            st = {}
            if league is not None:
                st = (_safe(lambda: dict(league.standings).get(
                    getattr(team, "team_name", ""), {}), {}) or {})
            w = st.get("W", st.get("Wins", 0)) or 0
            l = st.get("L", st.get("Losses", 0)) or 0
            otl = st.get("OTL", 0) or 0
            ctx["win_pct"] = w / max(1, w + l + otl)
            ctx["losing_streak"] = int(
                st.get("losing_streak", st.get("streak", 0)) or 0)
            if _rs is not None:
                roster = list(getattr(team, "roster", None) or [])
                leaders = (_safe(lambda: _rs.team_hierarchy(roster).get(
                    "Team Leaders", []), []) or [])
                if leaders:
                    ctx["room_leadership"] = sum(
                        getattr(p, "leadership", 50) or 50
                        for p in leaders) / len(leaders)
        except Exception:
            pass
        return ctx

    def _apply_line_control(self, team, coach, roster, target):
        """Route line-control changes through reputation_system.set_line_control.

        Mainline parity (morale_window._open_line_control_popup /
        LineControlPopup): the engine computes the full consequence chain --
        happiness shifts (strong personalities furious on a winning-team
        seize), gm_trust deltas on discussed takeovers, team-event feed
        entries, and coach line re-installation on give-back. The previous
        native code flipped team.line_control directly, which skipped the
        entire chain: no morale consequences, no happiness shifts, no feed
        entry.

        approach="seize" matches this toggle button's direct-takeover
        semantics (mainline's nuclear option). Giving the pen back
        (gm -> coach) is always amicable per mainline.
        Returns the engine's outcome text for display, or "" / None on
        failure.
        """
        if _rs is None:
            return None
        try:
            out = _rs.set_line_control(
                team, target, self._team_context(), roster,
                coach=coach, approach="seize")
            return (out or {}).get("text", "")
        except Exception as e:
            return f"Line control change failed: {e}"

    # ------------------------------------------------------------------
    # Room tab
    # ------------------------------------------------------------------
    def _make_room_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)

        self._headline = QLabel("DRESSING ROOM")
        self._headline.setObjectName("section-header")
        layout.addWidget(self._headline)

        top_row = QHBoxLayout()

        # Coach card + GM actions
        coach_frame = QFrame()
        coach_frame.setObjectName("tile")
        coach_layout = QVBoxLayout(coach_frame)
        self._coach_body = QLabel("")
        self._coach_body.setWordWrap(True)
        coach_layout.addWidget(self._coach_body)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self._action_buttons = {}
        for action, label in (
                ("bag_skate", "Bag Skate"),
                ("speech", "Speech"),
                ("practice", "Practice"),
                ("back_room", "Back Room"),
                ("advise_coach", "Advise Coach"),
                ("line_control", "Lines: Coach")):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _c, a=action: self._gm_action(a))
            actions.addWidget(btn)
            self._action_buttons[action] = btn
        actions.addStretch()
        coach_layout.addLayout(actions)
        top_row.addWidget(coach_frame, 1)

        # Watch list
        watch_frame = QFrame()
        watch_frame.setObjectName("tile")
        watch_layout = QVBoxLayout(watch_frame)
        watch_title = QLabel("WATCH LIST")
        watch_title.setObjectName("section-header")
        watch_layout.addWidget(watch_title)
        self._watch_body = QLabel("")
        self._watch_body.setWordWrap(True)
        watch_layout.addWidget(self._watch_body)
        watch_layout.addStretch()
        top_row.addWidget(watch_frame, 1)
        layout.addLayout(top_row)

        # Receipts
        receipts_frame = QFrame()
        receipts_frame.setObjectName("tile")
        receipts_layout = QVBoxLayout(receipts_frame)
        receipts_title = QLabel("RECENT ROOM DECISIONS")
        receipts_title.setObjectName("section-header")
        receipts_layout.addWidget(receipts_title)
        receipts_sub = QLabel(
            "Causal receipts: who approved it, who gained, who paid, which relationship shifted.")
        receipts_sub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        receipts_sub.setWordWrap(True)
        receipts_layout.addWidget(receipts_sub)
        self._receipts_body = QLabel("")
        self._receipts_body.setWordWrap(True)
        receipts_layout.addWidget(self._receipts_body)
        layout.addWidget(receipts_frame)

        # Player response table
        resp_frame = QFrame()
        resp_frame.setObjectName("tile")
        resp_layout = QVBoxLayout(resp_frame)
        resp_title = QLabel("PLAYER RESPONSE TO COACH")
        resp_title.setObjectName("section-header")
        resp_layout.addWidget(resp_title)
        self._response_table = QTableWidget()
        self._response_table.setColumnCount(6)
        self._response_table.setHorizontalHeaderLabels(
            ["Player", "Engagement", "Response", "Happiness", "Morale", "Tier"])
        self._response_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self._response_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._response_table.verticalHeader().setVisible(False)
        self._response_table.horizontalHeader().setStretchLastSection(True)
        self._response_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        resp_layout.addWidget(self._response_table)
        layout.addWidget(resp_frame)

        # Feed + hierarchy
        bottom_row = QHBoxLayout()
        feed_frame = QFrame()
        feed_frame.setObjectName("tile")
        feed_layout = QVBoxLayout(feed_frame)
        feed_title = QLabel("DYNAMICS FEED")
        feed_title.setObjectName("section-header")
        feed_layout.addWidget(feed_title)
        self._feed_body = QLabel("")
        self._feed_body.setWordWrap(True)
        self._feed_body.setAlignment(Qt.AlignTop)
        feed_layout.addWidget(self._feed_body)
        bottom_row.addWidget(feed_frame, 1)

        hier_frame = QFrame()
        hier_frame.setObjectName("tile")
        hier_layout = QVBoxLayout(hier_frame)
        hier_title = QLabel("HIERARCHY")
        hier_title.setObjectName("section-header")
        hier_layout.addWidget(hier_title)
        self._hierarchy_body = QLabel("")
        self._hierarchy_body.setWordWrap(True)
        self._hierarchy_body.setAlignment(Qt.AlignTop)
        hier_layout.addWidget(self._hierarchy_body)
        bottom_row.addWidget(hier_frame, 1)
        layout.addLayout(bottom_row)

        scroll.setWidget(inner)
        return scroll

    def _load_room(self):
        _gm, team, league = self._resolve()
        if team is None:
            return
        try:
            roster = list(getattr(team, "roster", None) or [])
        except Exception:
            roster = []

        # Chemistry headline
        score, label = 0, ""
        if _rs is not None:
            try:
                chem = _rs.team_chemistry(roster, {"team": team})
                score = chem.get("score", 0)
                label = chem.get("label", "")
            except Exception:
                pass
        else:
            vals = [_safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0)
                    for p in roster]
            score = round(sum(vals) / len(vals)) if vals else 0
        self._headline.setText(
            f"CHEMISTRY {score}/100  {label}")

        # Coach card
        coach = self._head_coach(team)
        if coach is not None and _rs is not None:
            try:
                _rs.ensure_reputation_fields(coach)
                style = _rs.coach_style(coach)
                name = _safe(lambda: getattr(coach, "full_name", "Coach"), "Coach")
                trust = _safe(lambda: int(getattr(coach, "gm_trust", 70)), 70)
                desc = _safe(lambda: style.get("description", ""), "")
                self._coach_body.setText(
                    f"<b style='font-size:15px'>{name}</b><br>"
                    f"{_safe(lambda: style.get('label', ''), '')}<br>"
                    f"<span style='color:#9aa4b8'>{desc}</span><br>"
                    f"GM trust: {trust}/100")
            except Exception:
                self._coach_body.setText("No head coach on staff.")
                coach = None
        else:
            self._coach_body.setText("No head coach on staff.")
            coach = None
        line_control = _safe(lambda: getattr(team, "line_control", "coach"), "coach")
        if "line_control" in self._action_buttons:
            self._action_buttons["line_control"].setText(
                "Lines: YOU (GM)" if line_control == "gm" else "Lines: Coach")

        # Watch list
        items = []
        if _rs is not None and coach is not None:
            try:
                issues = _rs.detect_dynamics_issues(
                    team, {"team": team}, roster, coach)
                items = [(i.get("severity", "low"), i.get("text", ""))
                         for i in (issues or [])]
            except Exception:
                items = []
        icon = {"high": "\U0001F534", "medium": "\U0001F7E1",
                "low": "\U0001F7E2"}
        if items:
            self._watch_body.setText("\n".join(
                f"{icon.get(s, '•')} {t}" for s, t in items))
        else:
            self._watch_body.setText(
                "\U0001F7E2 No structural issues detected. The room is stable.")

        # Receipts (authority kind only)
        receipts = []
        if _dr is not None:
            try:
                dr = _dr.ensure_dressing_room_fields(team)
                for rec in reversed(list(dr.get("practice_receipts") or [])):
                    if not isinstance(rec, dict) or rec.get("kind") != "authority":
                        continue
                    receipts.append(rec)
                    if len(receipts) >= 5:
                        break
            except Exception:
                receipts = []
        if receipts:
            lines = []
            for r in receipts:
                head = (f"<b>{r.get('title', '')}</b> "
                        f"<span style='color:#9aa4b8'>{r.get('date', '')} \u00b7 "
                        f"choice: {r.get('choice', '')}</span>")
                gained = r.get("gained") or []
                paid = r.get("paid") or []
                body = ""
                if gained:
                    body += "<br><span style='color:#4CAF50'>Gained: " + ", ".join(
                        f"{g[0]} {'+' if g[1] > 0 else ''}{g[1]}" for g in gained) + "</span>"
                if paid:
                    body += "<br><span style='color:#F44336'>Paid: " + ", ".join(
                        f"{g[0]} {g[1]}" for g in paid) + "</span>"
                for x in (r.get("relationships") or []):
                    body += f"<br><span style='color:#9aa4b8'>\u2022 {x}</span>"
                lines.append(head + body)
            self._receipts_body.setText("<br><br>".join(lines))
        else:
            self._receipts_body.setText(
                "No room decisions on record yet this season.")

        # Player response table
        players = []
        if _rs is not None:
            try:
                ctx = {"team": team}
                hierarchy = _rs.team_hierarchy(roster)
                tier_of = {}
                for tier, ps in hierarchy.items():
                    for p in ps:
                        tier_of[id(p)] = tier
                ordered = sorted(
                    roster, key=lambda x: _rs.hierarchy_score(x), reverse=True)
                for p in ordered:
                    _rs.ensure_reputation_fields(p)
                    resp = (_rs.player_coach_response(p, coach, ctx)
                            if coach else {"label": "Neutral"})
                    try:
                        eng = _rs.engagement_style(p).get("label", "")
                    except Exception:
                        eng = ""
                    players.append({
                        "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                        "engagement": eng,
                        "response": resp.get("label", "Neutral"),
                        "happiness": _safe(lambda: int(getattr(p, "happiness", 70) or 0), 70),
                        "morale": _safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0),
                        "tier": tier_of.get(id(p), "-"),
                    })
            except Exception:
                pass
        if not players:
            for p in roster:
                players.append({
                    "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                    "engagement": "", "response": "Neutral",
                    "happiness": 70,
                    "morale": _safe(lambda: int(getattr(p, "morale", 0) or 0) * 10, 0),
                    "tier": "-",
                })
        self._response_table.setRowCount(len(players))
        for row, p in enumerate(players):
            resp = p["response"]
            color = ("#4CAF50" if resp == "Bought in"
                     else "#FFC107" if resp == "Tuning out"
                     else "#F44336" if resp == "Quit on coach" else "#9aa4b8")
            name_item = QTableWidgetItem(p["name"])
            resp_item = QTableWidgetItem(resp)
            resp_item.setForeground(QColor(color))
            for col, item in (
                    (0, name_item),
                    (1, QTableWidgetItem(p["engagement"] or "\u2014")),
                    (2, resp_item),
                    (3, QTableWidgetItem(f"{p['happiness']}/100")),
                    (4, QTableWidgetItem(str(p["morale"]))),
                    (5, QTableWidgetItem(str(p["tier"])))):
                self._response_table.setItem(row, col, item)

        # Dynamics feed
        feed = []
        if _rs is not None:
            try:
                feed = _rs.get_dynamics_feed(team, limit=25) or []
            except Exception:
                feed = []
        if feed:
            icons = {"up": "\u25b2", "down": "\u25bc"}
            self._feed_body.setText("\n".join(
                f"{icons.get(e.get('tone'), '\u2022')} {e.get('date', '')} {e.get('text', '')}"
                for e in feed))
        else:
            self._feed_body.setText("No dynamics yet this season.")

        # Hierarchy
        hier_lines = []
        if _rs is not None:
            try:
                hierarchy = _rs.team_hierarchy(roster)
                for tier, ps in hierarchy.items():
                    names = ", ".join(
                        _safe(lambda: getattr(p, "full_name", "?"), "?")
                        for p in ps[:5])
                    hier_lines.append(f"<b>{tier}</b> ({len(ps)}): {names}")
            except Exception:
                pass
        self._hierarchy_body.setText(
            "<br>".join(hier_lines) if hier_lines else "No hierarchy data.")

    # ------------------------------------------------------------------
    # Social groups tab
    # ------------------------------------------------------------------
    def _make_groups_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)

        atmo_frame = QFrame()
        atmo_frame.setObjectName("tile")
        atmo_layout = QVBoxLayout(atmo_frame)
        t = QLabel("ROOM ATMOSPHERE")
        t.setObjectName("section-header")
        atmo_layout.addWidget(t)
        self._atmosphere_body = QLabel("")
        self._atmosphere_body.setWordWrap(True)
        atmo_layout.addWidget(self._atmosphere_body)
        layout.addWidget(atmo_frame)

        self._clique_container = QVBoxLayout()
        self._clique_container.setSpacing(12)
        clique_wrap = QWidget()
        clique_wrap.setLayout(self._clique_container)
        layout.addWidget(clique_wrap)

        fl_frame = QFrame()
        fl_frame.setObjectName("tile")
        fl_layout = QVBoxLayout(fl_frame)
        ft = QLabel("FLOATERS")
        ft.setObjectName("section-header")
        fl_layout.addWidget(ft)
        sub = QLabel("No circle of their own \u2014 higher integration risk, lower cascade pull.")
        sub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        sub.setWordWrap(True)
        fl_layout.addWidget(sub)
        self._floaters_body = QLabel("")
        self._floaters_body.setWordWrap(True)
        fl_layout.addWidget(self._floaters_body)
        layout.addWidget(fl_frame)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _load_groups(self):
        _gm, team, league = self._resolve()
        if team is None:
            return
        if _dr is None:
            self._atmosphere_body.setText("No dressing-room data yet.")
            self._floaters_body.setText("")
            return
        try:
            atmo = _dr.room_atmosphere(team)
        except Exception:
            atmo = None
        if atmo:
            color = _bar_color(atmo.get("score", 70) or 70)
            self._atmosphere_body.setText(
                f"<b>{atmo.get('label', '')}</b> "
                f"<b style='color:{color}'>{atmo.get('score', '?')}/100</b><br>"
                f"Mood: {atmo.get('mood', '?')} \u00b7 "
                f"Cohesion: {atmo.get('cohesion', '?')}<br>"
                f"<span style='color:#9aa4b8'>Mood is the room's mean morale; "
                f"cohesion is how much of the roster sits inside bonded groups.</span>")
        else:
            self._atmosphere_body.setText("No dressing-room data yet.")

        while self._clique_container.count():
            item = self._clique_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        cliques = []
        floaters = []
        try:
            cliques = _dr.form_cliques(team)
        except Exception:
            cliques = []
        try:
            floaters = _dr.floaters(team)
        except Exception:
            floaters = []
        roster = list(getattr(team, "roster", None) or [])
        by_id = {}
        for p in roster:
            try:
                by_id[_dr._pid(p)] = p
            except Exception:
                continue
        if cliques:
            for c in cliques:
                member_ids = c.get("member_ids", set()) or set()
                members = []
                for pid in member_ids:
                    p = by_id.get(pid)
                    if p is None:
                        continue
                    members.append(_safe(
                        lambda: getattr(p, "full_name", "?"), "?"))
                members.sort()
                card = QFrame()
                card.setObjectName("tile")
                card_layout = QVBoxLayout(card)
                head = QLabel(
                    f"<b style='font-size:14px'>{c.get('name', '')}</b> "
                    f"<span style='color:#9aa4b8'>{c.get('kind', '')}</span>")
                head.setWordWrap(True)
                card_layout.addWidget(head)
                meta = (f"{c.get('size', len(members))} members \u00b7 "
                        f"bond {round((c.get('bond', 0) or 0) * 100)}% \u00b7 "
                        f"voice: <b>{c.get('leader', '\u2014')}</b>")
                if c.get("mean_age") is not None:
                    meta += f" \u00b7 avg age {c.get('mean_age')}"
                if c.get("nationality"):
                    meta += f" \u00b7 {c.get('nationality')}"
                meta_lbl = QLabel(meta)
                meta_lbl.setWordWrap(True)
                meta_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                card_layout.addWidget(meta_lbl)
                mood = c.get("mood", 70) or 70
                mood_lbl = QLabel(
                    f"Mood: <b style='color:{_bar_color(mood)}'>{mood}</b>")
                card_layout.addWidget(mood_lbl)
                mem_lbl = QLabel(", ".join(members) if members
                                 else "No members")
                mem_lbl.setWordWrap(True)
                card_layout.addWidget(mem_lbl)
                self._clique_container.addWidget(card)
        else:
            empty = QLabel("No circles formed yet \u2014 the room is all floaters.")
            empty.setStyleSheet("color: #9aa4b8;")
            self._clique_container.addWidget(empty)
        if floaters:
            self._floaters_body.setText(
                ", ".join(f.get("name", "?") for f in floaters))
        else:
            self._floaters_body.setText(
                "Everyone belongs somewhere. Rare air.")

    # ------------------------------------------------------------------
    # Cascades tab
    # ------------------------------------------------------------------
    def _make_cascades_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)

        row = QHBoxLayout()

        log_frame = QFrame()
        log_frame.setObjectName("tile")
        log_layout = QVBoxLayout(log_frame)
        lt = QLabel("ROOM LOG")
        lt.setObjectName("section-header")
        log_layout.addWidget(lt)
        sub = QLabel("Every arrival, departure, talk, and press moment \u2014 and how the room absorbed it.")
        sub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        sub.setWordWrap(True)
        log_layout.addWidget(sub)
        self._cascade_log = QLabel("")
        self._cascade_log.setWordWrap(True)
        self._cascade_log.setAlignment(Qt.AlignTop)
        log_layout.addWidget(self._cascade_log, 1)
        row.addWidget(log_frame, 1)

        arr_frame = QFrame()
        arr_frame.setObjectName("tile")
        arr_layout = QVBoxLayout(arr_frame)
        at = QLabel("RECENT ARRIVALS")
        at.setObjectName("section-header")
        arr_layout.addWidget(at)
        sub2 = QLabel("How settled each new face is. Integration grows with games played and having a circle.")
        sub2.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        sub2.setWordWrap(True)
        arr_layout.addWidget(sub2)
        self._arrivals_body = QLabel("")
        self._arrivals_body.setWordWrap(True)
        self._arrivals_body.setAlignment(Qt.AlignTop)
        arr_layout.addWidget(self._arrivals_body, 1)
        row.addWidget(arr_frame, 1)

        layout.addLayout(row)
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _load_cascades(self):
        _gm, team, league = self._resolve()
        if team is None:
            return
        if _dr is None:
            self._cascade_log.setText("No dressing-room data yet.")
            self._arrivals_body.setText("No dressing-room data yet.")
            return
        try:
            dr = _dr.ensure_dressing_room_fields(team)
            log = list(dr.get("mood_log", []) or [])[-25:]
        except Exception:
            log, dr = [], {}
        if log:
            self._cascade_log.setText(
                "\n".join(f"\u2022 {l}" for l in reversed(log)))
        else:
            self._cascade_log.setText(
                "Nothing has shaken the room yet this season.")
        roster = list(getattr(team, "roster", None) or [])
        by_id = {}
        for p in roster:
            try:
                by_id[_dr._pid(p)] = p
            except Exception:
                continue
        arrivals = []
        try:
            for pid, rec in (dr.get("arrivals", {}) or {}).items():
                p = by_id.get(pid)
                if p is None:
                    continue
                arrivals.append({
                    "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                    "integration": _dr.integration_of(team, p),
                })
            arrivals.sort(key=lambda a: a["integration"])
        except Exception:
            arrivals = []
        if arrivals:
            self._arrivals_body.setText("\n".join(
                f"<b>{a['name']}</b> \u2014 settled "
                f"<b style='color:{_bar_color(a['integration'])}'>"
                f"{a['integration']}%</b>" for a in arrivals))
        else:
            self._arrivals_body.setText("No new faces this season.")

    # ------------------------------------------------------------------
    # Team talk tab
    # ------------------------------------------------------------------
    def _make_talk_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(10)

        t = QLabel("TEAM TALK")
        t.setObjectName("section-header")
        layout.addWidget(t)
        sub = QLabel(
            "Address the room before the game or between periods. Tone, speaker, "
            "and moment all matter \u2014 the wrong words at the wrong time backfire. "
            "Repeats in the same situation get tuned out.")
        sub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self._talk_pending = QLabel("")
        self._talk_pending.setWordWrap(True)
        layout.addWidget(self._talk_pending)

        for title, attr, options in (
                ("Situation", "_talk_situation",
                 [("pregame", "Pregame"), ("intermission", "Intermission")]),
                ("Score State", "_talk_score",
                 [("trailing", "Trailing"), ("tied", "Tied"),
                  ("leading", "Leading")])):
            h = QLabel(title.upper())
            h.setObjectName("section-header")
            layout.addWidget(h)
            pills = _PillGroup(options, default=options[0][0])
            pills.connect(self._update_talk_preview)
            setattr(self, attr, pills)
            layout.addWidget(pills)
        self._talk_situation.set_value("pregame")
        self._talk_score.set_value("tied")

        h = QLabel("SPEAKER")
        h.setObjectName("section-header")
        layout.addWidget(h)
        self._talk_speaker = _PillGroup(
            [("coach", "Head Coach"), ("captain", "Captain")],
            default="coach")
        self._talk_speaker.connect(self._update_talk_preview)
        layout.addWidget(self._talk_speaker)

        h = QLabel("CONTEXT")
        h.setObjectName("section-header")
        layout.addWidget(h)
        ctx_row = QHBoxLayout()
        self._talk_rival = QCheckBox("Rivalry game")
        self._talk_rival.stateChanged.connect(
            lambda _s: self._update_talk_preview())
        ctx_row.addWidget(self._talk_rival)
        ctx_row.addWidget(QLabel("Losing/winning streak:"))
        self._talk_streak = QSpinBox()
        self._talk_streak.setRange(-20, 20)
        self._talk_streak.setValue(0)
        self._talk_streak.valueChanged.connect(
            lambda _v: self._update_talk_preview())
        ctx_row.addWidget(self._talk_streak)
        ctx_row.addStretch()
        layout.addLayout(ctx_row)

        h = QLabel("TONE")
        h.setObjectName("section-header")
        layout.addWidget(h)
        self._talk_tones = _PillGroup(
            [(k, label) for k, label, _b in TALK_TONES], default="calm")
        self._talk_tones.connect(self._update_talk_preview)
        layout.addWidget(self._talk_tones)
        self._tone_blurbs = {}
        for key, _lab, blurb in TALK_TONES:
            lbl = QLabel(f"\u2022 {blurb}")
            lbl.setStyleSheet("color: #9aa4b8; font-size: 11px;")
            lbl.setWordWrap(True)
            self._tone_blurbs[key] = lbl
            layout.addWidget(lbl)

        self._talk_preview = QLabel("")
        self._talk_preview.setWordWrap(True)
        self._talk_preview.setObjectName("tile")
        layout.addWidget(self._talk_preview)

        deliver = QPushButton("Deliver Talk")
        deliver.setObjectName("primary-btn")
        deliver.setCursor(Qt.PointingHandCursor)
        deliver.clicked.connect(self._deliver_talk)
        layout.addWidget(deliver)
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _talk_inputs(self):
        streak = int(self._talk_streak.value() or 0)
        streak = max(-20, min(20, streak))
        return {
            "tone": self._talk_tones.value() or "calm",
            "situation": self._talk_situation.value() or "pregame",
            "score_state": self._talk_score.value() or "tied",
            "speaker": self._talk_speaker.value() or "coach",
            "rival": bool(self._talk_rival.isChecked()),
            "streak": streak,
        }

    @staticmethod
    def _talk_fit(tone, score_state, situation, rival, streak):
        """Deterministic fit half of give_talk() -- mirrored for preview."""
        try:
            fit = _dr.TONE_FIT.get((tone, score_state), 55) if _dr else 55
        except Exception:
            fit = 55
        if streak <= -2 and tone == "calm":
            fit = min(100, fit + 12)
        if rival and tone == "fired-up" and situation == "pregame":
            fit = min(100, fit + 12)
        if score_state == "leading" and tone == "fired-up":
            fit = max(5, fit - 10)
        return fit

    def _update_talk_preview(self):
        if _dr is None:
            self._talk_preview.setText("Talk engine unavailable.")
            return
        _gm, team, league = self._resolve()
        if team is None:
            return
        inp = self._talk_inputs()
        try:
            if inp["speaker"] == "captain":
                cap = _dr.captain_of(team)
                speaker_inf = _dr.influence_of(cap) if cap is not None else 50
                speaker_name = _dr._name(cap) if cap is not None else "the captain"
                cap_label = (f"Captain ({_dr._name(cap)})"
                             if cap is not None else "Captain")
            else:
                speaker_inf = _dr._coach_influence(team)
                speaker_name = "the coach"
                cap = None
                cap_label = "Captain"
            # keep captain pill label live
            for key, btn in self._talk_speaker._buttons.items():
                if key == "captain":
                    btn.setText(cap_label)
            fit = self._talk_fit(inp["tone"], inp["score_state"],
                                 inp["situation"], inp["rival"], inp["streak"])
            base = 0.55 * speaker_inf + 0.45 * fit
            lo, hi = base - 10, base + 10

            def tier(e):
                if e >= 78:
                    return "landed"
                if e >= 55:
                    return "steady"
                if e >= 35:
                    return "flat"
                return "backfired"

            order = ("landed", "steady", "flat", "backfired")
            likely = sorted({tier(lo), tier(hi), tier(base)},
                            key=order.index)
            dr = _dr.ensure_dressing_room_fields(team)
            key = ("intermission" if inp["situation"] == "intermission"
                   else "pregame")
            pending = dr.get(key)
            repeat = isinstance(pending, dict)

            colors = {"landed": "#4CAF50", "steady": "#9aa4b8",
                      "flat": "#FFC107", "backfired": "#F44336"}
            chips = " ".join(
                f"<b style='color:{colors[t]}'>{TIER_LABEL[t]}</b>"
                for t in likely)
            html = (
                f"Tone fit: <b style='color:{_bar_color(int(fit))}'>"
                f"{int(fit)}/100</b> "
                f"<span style='color:#9aa4b8'>({speaker_name}, influence "
                f"{int(speaker_inf)})</span><br>"
                f"Effectiveness range: {round(lo, 1)}\u2013{round(hi, 1)}<br>"
                f"Likely outcome: {chips}")
            if repeat:
                html += ("<br><span style='color:#FFC107'>\u26a0 The room has "
                         "already heard today's words for this situation \u2014 "
                         "delivering again replaces the pending talk but grants "
                         "no further lift.</span>")
            self._talk_preview.setText(html)
        except Exception as e:
            self._talk_preview.setText(f"Preview unavailable: {e}")

    def _load_talk(self):
        _gm, team, league = self._resolve()
        if team is None or _dr is None:
            return
        try:
            dr = _dr.ensure_dressing_room_fields(team)
            pend_lines = []
            for key, label in (("pregame", "Pregame"),
                               ("intermission", "Intermission")):
                rec = dr.get(key)
                if isinstance(rec, dict):
                    pend_lines.append(
                        f"<b>{label}:</b> {rec.get('speaker', '')} gave a "
                        f"<b>{rec.get('tone', '')}</b> talk \u2014 "
                        f"{rec.get('outcome', '')}. "
                        f"<span style='color:#9aa4b8'>{rec.get('note', '')}</span>")
            self._talk_pending.setText(
                "<br>".join(pend_lines) if pend_lines
                else "No talk pending \u2014 the room is waiting to hear something.")
        except Exception:
            pass
        self._update_talk_preview()

    def _deliver_talk(self):
        if _dr is None:
            return
        _gm, team, league = self._resolve()
        if team is None:
            return
        inp = self._talk_inputs()
        try:
            out = _dr.give_talk(
                team, inp["tone"],
                {"situation": inp["situation"],
                 "score_state": inp["score_state"],
                 "rival": inp["rival"], "streak": inp["streak"]},
                inp["speaker"], day_key=self._date_str())
        except Exception as e:
            self._talk_preview.setText(f"Could not deliver talk: {e}")
            return
        outcome = ""
        if isinstance(out, dict):
            outcome = _safe(lambda: out.get("outcome", ""), "") or ""
            lines = _safe(lambda: out.get("lines", []), []) or []
            if lines:
                outcome = ("<br>".join(lines) + "<br>" + outcome
                           if outcome else "<br>".join(lines))
        self._talk_pending.setText(
            f"<b style='color:#4CAF50'>Delivered.</b> {outcome}"
            if outcome else "<b style='color:#4CAF50'>Delivered.</b>")
        self.refresh()

    # ------------------------------------------------------------------
    # Rivalries tab
    # ------------------------------------------------------------------
    def _make_rivalries_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)

        row = QHBoxLayout()

        blood_frame = QFrame()
        blood_frame.setObjectName("tile")
        blood_layout = QVBoxLayout(blood_frame)
        bt = QLabel("BAD BLOOD ON RECORD")
        bt.setObjectName("section-header")
        blood_layout.addWidget(bt)
        self._rivalries_body = QLabel("")
        self._rivalries_body.setWordWrap(True)
        self._rivalries_body.setAlignment(Qt.AlignTop)
        blood_layout.addWidget(self._rivalries_body, 1)
        row.addWidget(blood_frame, 1)

        decl_frame = QFrame()
        decl_frame.setObjectName("tile")
        decl_layout = QVBoxLayout(decl_frame)
        dt = QLabel("DECLARE A RIVAL")
        dt.setObjectName("section-header")
        decl_layout.addWidget(dt)
        dsub = QLabel(
            "Name your enemy. A declaration sets the heat to 70, makes those games "
            "genuinely hostile, and never fades until you renounce it. The league will hear about it.")
        dsub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        dsub.setWordWrap(True)
        decl_layout.addWidget(dsub)

        dh = QLabel("TEAM RIVAL")
        dh.setObjectName("section-header")
        decl_layout.addWidget(dh)
        team_row = QHBoxLayout()
        self._rival_team_pick = QComboBox()
        self._rival_team_pick.setMinimumWidth(180)
        team_row.addWidget(self._rival_team_pick)
        decl_team_btn = QPushButton("Declare team rival")
        decl_team_btn.clicked.connect(
            lambda: self._declare_rivalry(
                "team", self._rival_team_pick.currentData()))
        team_row.addWidget(decl_team_btn)
        team_row.addStretch()
        decl_layout.addLayout(team_row)

        ch = QLabel("PERSONAL BEEF")
        ch.setObjectName("section-header")
        decl_layout.addWidget(ch)
        csub = QLabel("A personal feud with an opposing head coach \u2014 declared through their team.")
        csub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        csub.setWordWrap(True)
        decl_layout.addWidget(csub)
        coach_row = QHBoxLayout()
        self._rival_coach_pick = QComboBox()
        self._rival_coach_pick.setMinimumWidth(180)
        coach_row.addWidget(self._rival_coach_pick)
        decl_coach_btn = QPushButton("Declare coach beef")
        decl_coach_btn.clicked.connect(
            lambda: self._declare_rivalry(
                "coach", self._rival_coach_pick.currentData()))
        coach_row.addWidget(decl_coach_btn)
        coach_row.addStretch()
        decl_layout.addLayout(coach_row)

        decl_layout.addWidget(QLabel("DECLARED RIVALRIES"))
        self._declared_body = QLabel("")
        self._declared_body.setWordWrap(True)
        decl_layout.addWidget(self._declared_body)
        self._declared_buttons = QVBoxLayout()
        decl_layout.addLayout(self._declared_buttons)
        decl_layout.addStretch()
        row.addWidget(decl_frame, 1)

        layout.addLayout(row)
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _load_rivalries(self):
        _gm, team, league = self._resolve()
        if team is None or league is None:
            return
        my_name = _safe(lambda: getattr(team, "team_name", ""), "")

        # Team pickers
        teams = []
        try:
            teams = sorted(
                str(getattr(t, "team_name", ""))
                for t in (getattr(league, "teams", []) or [])
                if getattr(t, "team_name", "")
                and getattr(t, "team_name", "") != my_name)
        except Exception:
            teams = []
        for combo in (self._rival_team_pick, self._rival_coach_pick):
            combo.blockSignals(True)
            combo.clear()
            for name in teams:
                combo.addItem(name, name)
            combo.blockSignals(False)

        if _rs is None:
            self._rivalries_body.setText(
                "No bad blood on record. Yet.")
            return
        entries = []
        declared = []
        try:
            rivalries = list(getattr(league, "rivalries", []) or [])
            coach = self._head_coach(team)
            cname = (_safe(lambda: getattr(coach, "full_name", ""), "")
                     if coach else "")
            # Coach beefs
            if coach is not None:
                for r in _rs.get_rivalries_for(rivalries, coach)[:3]:
                    other = (r["b_name"] if r["a_name"] == cname
                             else r["a_name"])
                    entries.append({
                        "category": "coach", "label": other,
                        "intensity": round(r.get("intensity", 0)),
                        "origin": str(r.get("origin", "")).replace("_", " "),
                        "solidified": bool(r.get("solidified")),
                    })
            # Team rivalries
            team_rs = [r for r in rivalries
                       if r.get("kind") == "team_team"
                       and (r.get("a", (None, ""))[1] == my_name
                            or r.get("b", (None, ""))[1] == my_name)]
            team_rs.sort(key=lambda r: -r.get("intensity", 0))
            for r in team_rs[:3]:
                other = (r["b_name"] if r.get("a", (None, ""))[1] == my_name
                         else r["a_name"])
                entries.append({
                    "category": "team", "label": other,
                    "intensity": round(r.get("intensity", 0)),
                    "origin": str(r.get("origin", "")).replace("_", " "),
                    "solidified": bool(r.get("solidified")),
                })
            # Loudest player beefs
            beefs = []
            for p in list(getattr(team, "roster", None) or []):
                try:
                    beefs += _rs.get_rivalries_for(rivalries, p)
                except Exception:
                    continue
            beefs.sort(key=lambda r: -r.get("intensity", 0))
            for r in beefs[:2]:
                entries.append({
                    "category": "player",
                    "label": f"{r['a_name']} vs {r['b_name']}",
                    "intensity": round(r.get("intensity", 0)),
                    "origin": str(r.get("origin", "")).replace("_", " "),
                    "solidified": bool(r.get("solidified")),
                })
            # GM-declared (renounceable)
            for r in _rs.declared_rivalries_for(rivalries, team):
                my_keys = {("team", my_name), ("gm", my_name)}
                other = (r["b_name"] if r.get("a") in my_keys
                         else r["a_name"])
                kind = ("team" if r.get("kind") == "team_team"
                        else "coach")
                declared.append({
                    "label": other, "kind": kind,
                    "intensity": round(r.get("intensity", 0)),
                })
        except Exception:
            pass

        icons = {"coach": "\U0001F525", "team": "\U0001F3D2",
                 "player": "\U0001F94A"}
        if entries:
            self._rivalries_body.setText("<br>".join(
                f"{icons.get(x['category'], '\u2022')} "
                f"{'\U0001F512 ' if x['solidified'] else ''}"
                f"<b>{x['label']}</b> "
                f"<span style='color:#9aa4b8'>\u2014 heat {x['intensity']} "
                f"({x['origin'] or 'bad blood'})</span>"
                for x in entries))
        else:
            self._rivalries_body.setText("No bad blood on record. Yet.")

        while self._declared_buttons.count():
            item = self._declared_buttons.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if declared:
            self._declared_body.setText("")
            for x in declared:
                row = QHBoxLayout()
                lbl = QLabel(
                    f"\U0001F4E2 Declared rival: <b>{x['label']}</b> "
                    f"<span style='color:#9aa4b8'>({x['intensity']})</span>")
                lbl.setWordWrap(True)
                row.addWidget(lbl, 1)
                rb = QPushButton("Renounce")
                rb.clicked.connect(
                    lambda _c, k=x["kind"], t=x["label"]:
                    self._renounce_rivalry(k, t))
                row.addWidget(rb)
                wrap = QWidget()
                wrap.setLayout(row)
                self._declared_buttons.addWidget(wrap)
        else:
            self._declared_body.setText("No declared rivalries.")

    def _declare_rivalry(self, kind, target):
        _gm, team, league = self._resolve()
        if team is None or league is None or not target or _rs is None:
            return
        target_team = None
        for t in list(getattr(league, "teams", []) or []):
            try:
                if str(getattr(t, "team_name", "")) == str(target):
                    target_team = t
                    break
            except Exception:
                continue
        if target_team is None:
            self._declared_body.setText(f"Team not found: {target}")
            return
        try:
            rec, label = _rs.declare_rivalry_for_gm(
                league, team, target_team, target_kind=kind)
            self._declared_body.setText(
                f"<b style='color:#4CAF50'>Rivalry declared with {label}.</b> "
                f"The heat is at 70, those games turn hostile, and it never "
                f"fades until renounced. The league heard about it.")
        except ValueError as e:
            self._declared_body.setText(f"<b style='color:#F44336'>{e}</b>")
        except Exception as e:
            self._declared_body.setText(
                f"<b style='color:#F44336'>Could not declare: {e}</b>")
        QTimer.singleShot(1500, self._load_rivalries)

    def _renounce_rivalry(self, kind, target):
        _gm, team, league = self._resolve()
        if team is None or league is None or _rs is None:
            return
        target_team = None
        for t in list(getattr(league, "teams", []) or []):
            try:
                if str(getattr(t, "team_name", "")) == str(target):
                    target_team = t
                    break
            except Exception:
                continue
        if target_team is None:
            return
        try:
            ok = _rs.renounce_rivalry_for_gm(
                league, team, target_team, target_kind=kind)
            self._declared_body.setText(
                f"Rivalry with {target} renounced. The bad blood cools."
                if ok else f"No live declared rivalry with {target} to renounce.")
        except Exception as e:
            self._declared_body.setText(
                f"<b style='color:#F44336'>Could not renounce: {e}</b>")
        QTimer.singleShot(1500, self._load_rivalries)

    # ------------------------------------------------------------------
    # Coach tab (carousel, hot seat, two-step fire)
    # ------------------------------------------------------------------
    def _make_coach_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)

        row = QHBoxLayout()

        cur_frame = QFrame()
        cur_frame.setObjectName("tile")
        cur_layout = QVBoxLayout(cur_frame)
        ct = QLabel("BEHIND THE BENCH")
        ct.setObjectName("section-header")
        cur_layout.addWidget(ct)
        self._carousel_current = QLabel("")
        self._carousel_current.setWordWrap(True)
        cur_layout.addWidget(self._carousel_current)
        self._hotseat_body = QLabel("")
        self._hotseat_body.setWordWrap(True)
        cur_layout.addWidget(self._hotseat_body)
        self._fire_btn = QPushButton("Fire Coach")
        self._fire_btn.setObjectName("pill")
        self._fire_btn.setCursor(Qt.PointingHandCursor)
        self._fire_btn.clicked.connect(self._on_fire_clicked)
        self._fire_armed = False
        self._fire_timer = None
        cur_layout.addWidget(self._fire_btn)
        cur_layout.addStretch()
        row.addWidget(cur_frame, 1)

        list_frame = QFrame()
        list_frame.setObjectName("tile")
        list_layout = QVBoxLayout(list_frame)
        lt = QLabel("THE CAROUSEL")
        lt.setObjectName("section-header")
        list_layout.addWidget(lt)
        lsub = QLabel(
            "Fired coaches carry their hot-seat reputation, tactical identity, "
            "player bonds and grudges into their next chair. Coordinators who "
            "earned interviews sit below.")
        lsub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        lsub.setWordWrap(True)
        list_layout.addWidget(lsub)
        self._carousel_list = QVBoxLayout()
        self._carousel_list.setSpacing(10)
        list_wrap = QWidget()
        list_wrap.setLayout(self._carousel_list)
        list_layout.addWidget(list_wrap)
        list_layout.addStretch()
        row.addWidget(list_frame, 1)

        layout.addLayout(row)
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _load_coach(self):
        _gm, team, league = self._resolve()
        if team is None or _dr is None:
            return
        try:
            coach = _dr._room_head_coach(team)
        except Exception:
            coach = None
        if coach is not None:
            try:
                style = _rs.coach_style(coach) if _rs else {}
            except Exception:
                style = {}
            try:
                axis = _dr.coach_demanding_axis(coach)
                ax = ("Demanding" if axis >= 0.7 else "Players' coach"
                      if axis <= 0.3 else "Balanced")
            except Exception:
                ax = ""
            name = _safe(lambda: getattr(coach, "name", getattr(
                coach, "full_name", "Coach")), "Coach")
            gm_trust = _safe(lambda: int(getattr(coach, "gm_trust", 70) or 70), 70)
            shelf = _safe(lambda: int(getattr(coach, "shelf_weeks", 0) or 0), 0)
            self._carousel_current.setText(
                f"<b style='font-size:15px'>{name}</b><br>"
                f"{_safe(lambda: style.get('label', ''), '')}"
                f"{f' ({ax})' if ax else ''}<br>"
                f"<span style='color:#9aa4b8'>GM trust: {gm_trust}/100"
                f"{f' \u00b7 message age {shelf} wks' if shelf else ''}</span>")
        else:
            self._carousel_current.setText(
                "No head coach. The carousel is your friend \u2014 pick below.")

        # Hot seat: read-only. Never run coach_hot_seat_check() from a
        # read path -- it can apply trust drift (a write).
        try:
            hot = _dr.ensure_dressing_room_fields(team).get("coach_hot_seat")
        except Exception:
            hot = None
        if hot:
            html = (f"\U0001F525 <b>Hot seat:</b> trust {hot.get('trust', '?')}/100 "
                    f"vs board expectation "
                    f"\"{hot.get('expectation', '')}\" "
                    f"(pace {hot.get('pace', '')}, expected "
                    f"{hot.get('expected', '')}).")
            if hot.get("reprieve_p") is not None:
                try:
                    html += (f" Reprieve odds if he pleads his case: "
                             f"{round(hot['reprieve_p'] * 100)}%.")
                except Exception:
                    pass
            if hot.get("pitch"):
                html += (f"<br><span style='color:#9aa4b8'>His pitch: "
                         f"\"{hot.get('pitch')}\"</span>")
            self._hotseat_body.setText(html)
        else:
            self._hotseat_body.setText("")

        while self._carousel_list.count():
            item = self._carousel_list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        candidates = []
        try:
            candidates = _dr.coaching_candidates(team)
        except Exception:
            candidates = []
        arch_icon = {"retread": "\u267B\uFE0F", "specialist": "\U0001F4CB",
                     "fresh blood": "\U0001F331"}
        if candidates:
            for i, c in enumerate(candidates):
                card = QFrame()
                card.setObjectName("tile")
                card_layout = QVBoxLayout(card)
                style_suffix = (f" · style: {c.get('style')}"
                                if c.get('style') else "")
                src = (" · in-house" if c.get('source') == 'promotion'
                       else " · carousel")
                head = QLabel(
                    f"{arch_icon.get(c.get('archetype'), '•')} "
                    f"<b>{c.get('name', '?')}</b> "
                    f"<span style='color:#9aa4b8'>{c.get('archetype', '')}"
                    f"{src}{style_suffix}</span>")
                head.setWordWrap(True)
                card_layout.addWidget(head)
                if c.get("note"):
                    note_lbl = QLabel(c.get("note"))
                    note_lbl.setStyleSheet(
                        "color: #9aa4b8; font-size: 11px;")
                    note_lbl.setWordWrap(True)
                    card_layout.addWidget(note_lbl)
                hire = QPushButton("Hire")
                hire.setCursor(Qt.PointingHandCursor)
                hire.clicked.connect(
                    lambda _c, idx=i: self._hire_candidate(idx))
                card_layout.addWidget(hire)
                self._carousel_list.addWidget(card)
        else:
            empty = QLabel("No candidates on the carousel right now.")
            empty.setStyleSheet("color: #9aa4b8;")
            self._carousel_list.addWidget(empty)

    def _disarm_fire(self):
        self._fire_armed = False
        if self._fire_timer is not None:
            try:
                self._fire_timer.stop()
            except Exception:
                pass
            self._fire_timer = None
        self._fire_btn.setText("Fire Coach")

    def _on_fire_clicked(self):
        if not self._fire_armed:
            # First click arms the two-step confirm; auto-disarms after 4s.
            self._fire_armed = True
            self._fire_btn.setText("Confirm: fire the coach?")
            if self._fire_timer is not None:
                try:
                    self._fire_timer.stop()
                except Exception:
                    pass
            self._fire_timer = QTimer(self)
            self._fire_timer.setSingleShot(True)
            self._fire_timer.timeout.connect(self._disarm_fire)
            self._fire_timer.start(4000)
            return
        self._disarm_fire()
        _gm, team, league = self._resolve()
        if team is None or _dr is None:
            return
        try:
            entry = _dr.fire_coach(
                team, reason="fired", date_str=self._date_str(),
                league=league)
        except Exception as e:
            self._carousel_current.setText(
                f"<b style='color:#F44336'>Could not fire coach: {e}</b>")
            return
        if entry is None:
            self._carousel_current.setText(
                "<b style='color:#F44336'>No head coach to fire.</b>")
        else:
            self._carousel_current.setText(
                f"<b>{entry.get('name', 'The coach')} is out.</b> "
                f"The room absorbs the shock.")
        QTimer.singleShot(1200, self.refresh)

    def _hire_candidate(self, idx):
        _gm, team, league = self._resolve()
        if team is None or _dr is None:
            return
        try:
            # Re-fetch on hire so the pick always matches the advertised list.
            cands = _dr.coaching_candidates(team)
            cand = cands[idx] if 0 <= idx < len(cands) else None
        except Exception:
            cand = None
        if cand is None:
            return
        try:
            lines = _dr.hire_coach(team, cand, date_str=self._date_str())
        except Exception as e:
            self._carousel_current.setText(
                f"<b style='color:#F44336'>Hire failed: {e}</b>")
            return
        text = " ".join(lines) if lines else f"{cand.get('name', '')} hired."
        self._carousel_current.setText(
            f"<b style='color:#4CAF50'>{text}</b>")
        QTimer.singleShot(1500, self.refresh)

    # ------------------------------------------------------------------
    # Crisis banner
    # ------------------------------------------------------------------
    def _load_crisis(self):
        _gm, team, league = self._resolve()
        if team is None or _dr is None:
            self._crisis_frame.hide()
            return
        detail = {}
        try:
            dr = _dr.ensure_dressing_room_fields(team)
            if dr.get("captaincy_crisis"):
                detail = dict(dr.get("captaincy_crisis_detail") or {})
        except Exception:
            detail = {}
        if not detail:
            try:
                crisis = _dr.detect_captaincy_crisis(team, league)
                if crisis is not None:
                    detail = {
                        "captain_name": crisis.get("captain_name", ""),
                        "challenger_names": crisis.get("challenger_names") or [],
                        "severity": crisis.get("severity", 1),
                    }
            except Exception:
                pass
        if not detail:
            self._crisis_frame.hide()
            return

        # Named successors: challengers first, else highest influence.
        successors = []
        try:
            roster = list(getattr(team, "roster", None) or [])
            names = [n for n in (detail.get("challenger_names") or []) if n]
            by_name = {}
            for p in roster:
                try:
                    by_name[_dr._name(p)] = p
                except Exception:
                    continue
            matched = [by_name[n] for n in names if n in by_name]
            if not matched:
                cap = _dr.captain_of(team)
                ranked = sorted(
                    (p for p in roster if p is not cap),
                    key=lambda p: _dr.influence_of(p), reverse=True)
                matched = ranked[:3]
            for p in matched[:4]:
                successors.append((
                    _safe(lambda: str(getattr(p, "id", "")), ""),
                    _safe(lambda: _dr._name(p), "?")))
        except Exception:
            successors = []

        sev = "\U0001F534" * max(1, int(detail.get("severity", 1) or 1))
        challengers = ", ".join(detail.get("challenger_names") or []) or "none named"
        self._crisis_head.setText(
            f"{sev} <b>Captaincy crisis:</b> {detail.get('captain_name', '')} "
            f"is losing the room. Challengers: {challengers}. "
            f"No decision fixes this instantly \u2014 choose the politics you can live with.")
        while self._crisis_choices.count():
            item = self._crisis_choices.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for key, label, blurb in CRISIS_CHOICES:
            btn = QPushButton(f"{label}\n{blurb}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _c, k=key: self._on_crisis_choice(k))
            self._crisis_choices.addWidget(btn)
        self._crisis_successor_pick.clear()
        for pid, name in successors:
            self._crisis_successor_pick.addItem(name, pid)
        self._crisis_successor_row.hide()
        self._crisis_result.setText("")
        self._crisis_frame.show()

    def _on_crisis_choice(self, choice):
        if choice == "reassign":
            # Never silently auto-strip the C: show the successor picker.
            self._crisis_successor_row.show()
            return
        self._resolve_crisis(choice, "")

    def _resolve_crisis_reassign(self):
        pid = self._crisis_successor_pick.currentData()
        if not pid:
            self._crisis_result.setText(
                "Reassign needs a named successor.")
            return
        self._resolve_crisis("reassign", str(pid))

    def _resolve_crisis(self, choice, new_captain_id):
        _gm, team, league = self._resolve()
        if team is None or _dr is None:
            return
        new_c = None
        if new_captain_id:
            for p in list(getattr(team, "roster", None) or []):
                try:
                    if str(getattr(p, "id", "")) == str(new_captain_id):
                        new_c = p
                        break
                except Exception:
                    continue
        if choice == "reassign" and new_c is None:
            self._crisis_result.setText(
                "Reassign needs a named successor \u2014 no auto-strip.")
            return
        try:
            lines = _dr.resolve_captaincy_crisis(
                team, choice, new_captain=new_c,
                date_str=self._date_str())
        except Exception as e:
            self._crisis_result.setText(f"Could not resolve crisis: {e}")
            return
        self._crisis_result.setText(
            "<br>".join(lines) if lines else "The room reacts after the next beat.")
        QTimer.singleShot(1500, self.refresh)

    # ------------------------------------------------------------------
    # GM actions
    # ------------------------------------------------------------------
    def _gm_action(self, action):
        _gm, team, league = self._resolve()
        if team is None or _rs is None:
            return
        coach = self._head_coach(team)
        roster = list(getattr(team, "roster", None) or [])
        if action == "advise_coach":
            dlg = AdviseCoachDialog(
                self.game, team, coach, roster, parent=self)
            dlg.exec()
            return
        if action == "line_control":
            cur = _safe(lambda: getattr(team, "line_control", "coach"), "coach")
            target = "coach" if cur == "gm" else "gm"
            outcome = self._apply_line_control(team, coach, roster, target)
            if outcome and getattr(self, "_coach_body", None) is not None:
                try:
                    self._coach_body.setText(outcome)
                except Exception:
                    pass
            self.refresh()
            return
        if action == "back_room":
            if _me is not None:
                try:
                    _me.gm_public_backing(league, team, "room",
                                          user_triggered=True)
                except Exception as e:
                    self._coach_body.setText(
                        f"<b style='color:#F44336'>Back-room move failed: {e}</b>")
                    return
            self.refresh()
            return
        if coach is None:
            self._coach_body.setText(
                "No head coach on staff \u2014 this action needs a coach.")
            return
        try:
            if action == "bag_skate":
                _rs.apply_bag_skate(team, coach, roster)
            elif action == "speech":
                _rs.apply_inspiring_speech(team, coach, roster)
            elif action == "practice":
                _rs.apply_great_practice(team, coach, roster)
            else:
                return
        except Exception as e:
            self._coach_body.setText(
                f"<b style='color:#F44336'>Action failed: {e}</b>")
            return
        self.refresh()

    # ------------------------------------------------------------------
    # Tab switching + refresh
    # ------------------------------------------------------------------
    def _on_tab_changed(self, index):
        self._load_tab(index)

    def _load_tab(self, index):
        if index == 0:
            self._load_room()
        elif index == 1:
            self._load_groups()
        elif index == 2:
            self._load_cascades()
        elif index == 3:
            self._load_talk()
        elif index == 4:
            self._load_rivalries()
        elif index == 5:
            self._load_coach()

    def refresh(self):
        self._load_crisis()
        self._load_tab(self._tabs.currentIndex())
