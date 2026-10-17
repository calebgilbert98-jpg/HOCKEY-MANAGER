"""Player profile screen: 7 tabs (Overview / Health / Analytics /
Personality / Scout / Dynamics / History).

Native port of web_ui player (templates/player.html + screens/player.py +
static/js/player.js), which was itself a 1:1 port of the Tkinter
modern_profile.py. Calls the game object directly -- no Flask/HTTP.

The Overview tab is complete (stats, contract, composites, attribute
bars). Other tabs pull real game data with defensive fallbacks.
"""
import hashlib
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QGridLayout, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QInputDialog, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from .base import BaseScreen
from native_ui.safe import safe_call
from ..widgets.attribute_bar import AttributeBar
from .roster import _jersey_validation, _clean_position, _fmt_money


# ---------------------------------------------------------------------------
# attribute field lists (verbatim from web_ui/screens/player.py)
# ---------------------------------------------------------------------------

_SKATER_TECHNICAL = [
    ("Shooting", "shooting"), ("Shot Accuracy", "shooting_accuracy"),
    ("Shot Power", "shooting_power"), ("Wrist Shot", "wristshot"),
    ("Slap Shot", "slapshot"), ("One Timer", "one_timer"),
    ("Backhand", "backhand"), ("Deflections", "deflections"),
    ("Passing", "passing"), ("Pass Accuracy", "passing_accuracy"),
    ("Passing Creativity", "passing_creativity"),
    ("Puck Handling", "puck_handling"), ("Stickhandling", "stickhandling"),
    ("Deking", "deking"), ("Off. Positioning", "offensive_positioning"),
    ("Faceoffs", "faceoffs"), ("First Pass", "first_pass"),
    ("Breakout Passes", "breakout_passes"),
    ("Puck Protection", "puck_protection"), ("Loose Puck", "loose_puck"),
    ("Pokecheck", "pokecheck"),
]
_SKATER_MENTAL = [
    ("Vision", "vision"), ("Hockey IQ", "hockey_iq"),
    ("Anticipation", "anticipation"), ("Decisions", "decision_making"),
    ("Off. Awareness", "off_the_puck"),
    ("Def. Awareness", "defensive_awareness"),
    ("Creativity", "creativity"), ("Determination", "determination"),
    ("Composure", "composure"), ("Confidence", "confidence"),
    ("Focus", "focus"), ("Pressure Player", "pressure_player"),
    ("Teamwork", "teamwork"), ("Discipline", "discipline"),
    ("Flair", "flair"), ("Work Ethic", "work_ethic"),
    ("Coachability", "coachability"), ("Adaptability", "adaptability"),
]
_SKATER_PHYSICAL = [
    ("Skating", "skating"), ("Speed", "speed"), ("Agility", "agility"),
    ("Balance", "balance"), ("Strength", "strength"),
    ("Stamina", "stamina"), ("Endurance", "endurance"),
    ("Durability", "durability"), ("Injury Proneness", "injury_proneness"),
    ("Aggression", "aggressiveness"), ("Checking", "checking"),
    ("Bodycheck", "bodycheck"), ("Shot Blocking", "shot_blocking"),
    ("Forechecking", "forechecking"), ("Screening", "screen_shots"),
    ("Work Rate", "work_rate"), ("Shoot Tendency", "shoot_pass_tendency"),
    ("Hitting Tendency", "hitting_tendency"),
]
_GOALIE_TECHNICAL = [
    ("Goaltending", "goaltending"), ("Positioning", "positioning"),
    ("Reflexes", "reflexes"), ("Glove Hand", "glove_hand"),
    ("Stick Side", "stick_side"), ("Rebound Ctrl", "rebound_control"),
    ("Breakaway Skill", "breakaway_skill"),
    ("Puck Handling", "puck_handling"), ("Passing", "passing"),
]
_GOALIE_MENTAL = [
    ("Anticipation", "anticipation"), ("Decisions", "decision_making"),
    ("Vision", "vision"), ("Focus", "focus"),
    ("Determination", "determination"), ("Composure", "composure"),
    ("Confidence", "confidence"), ("Teamwork", "teamwork"),
    ("Discipline", "discipline"), ("Work Ethic", "work_ethic"),
    ("Adaptability", "adaptability"),
]
_GOALIE_PHYSICAL = [
    ("Skating", "skating"), ("Speed", "speed"), ("Agility", "agility"),
    ("Balance", "balance"), ("Strength", "strength"),
    ("Stamina", "stamina"), ("Endurance", "endurance"),
    ("Durability", "durability"), ("Injury Proneness", "injury_proneness"),
    ("Aggression", "aggressiveness"),
]

_SKATER_COMPOSITES = [
    ("chance_creation", "Chance Creation"), ("finishing", "Finishing"),
    ("skating", "Skating"), ("defensive_play", "Defensive Play"),
    ("physicality", "Physicality"), ("faceoff", "Faceoffs"),
    ("puck_retrieval", "Puck Retrieval"), ("discipline", "Discipline"),
]
_GOALIE_COMPOSITES = [
    ("goalie_save", "Goaltending"), ("skating", "Skating"),
    ("puck_retrieval", "Puck Retrieval"), ("discipline", "Discipline"),
]

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _to100(v):
    return safe_call(lambda: __import__("game_classes").to_100_scale(v),
                 50, context='player_profile/_to100') or 50


def _is_goalie(p):
    return "GOALIE" in str(
        safe_call(lambda: getattr(p, "primary_position", ""), "", context='player_profile/_is_goalie')).upper()


def _portrait_path(player_id):
    """md5(player id) -> portrait file in assets/web_portraits/.

    (R17 2026-10-16: moved from web_ui/static/img/portraits/ when the dead
    web_ui tree was archived; assets/ is bundled by puck_dynasty_native.spec
    so portraits now work in the shipped build too.)"""
    try:
        d = os.path.join(_REPO_ROOT, "assets", "web_portraits")
        files = sorted(
            f for f in os.listdir(d)
            if f.lower().endswith((".webp", ".png", ".jpg", ".jpeg")))
        if not files:
            return None
        h = hashlib.md5(str(player_id).encode("utf-8")).hexdigest()
        return os.path.join(d, files[int(h, 16) % len(files)])
    except Exception:
        return None


def _league_of(team, p):
    try:
        if team is not None:
            for attr, label in (("roster", "NHL"),
                                ("ahl_roster", "AHL")):
                lst = getattr(team, attr, None) or []
                if any(q is p for q in lst):
                    return label
        tn = str(getattr(p, "team_name", "") or "")
        if tn.lower() == "europe":
            return "Europe"
        rt = str(getattr(p, "rights_type", "") or "").upper()
        if rt in ("CHL", "NCAA", "EUROPE"):
            return {"CHL": "CHL", "NCAA": "NCAA",
                    "EUROPE": "Europe"}.get(rt, rt)
        jl = str(getattr(p, "junior_league", "") or "").strip()
        if jl:
            return jl
        if not tn or tn.lower() == "free agent":
            return "Free Agent"
        return tn
    except Exception:
        return ""


def _contract_type_label(p):
    try:
        c = getattr(p, "contract", None)
        labels = []
        if c is not None and getattr(c, "entry_level", False):
            labels.append("ELC")
        if c is not None and getattr(c, "two_way", False):
            labels.append("2-way")
        if c is not None and getattr(c, "no_movement_clause", False):
            labels.append("NMC")
        elif c is not None and getattr(c, "no_trade_clause", False):
            labels.append("NTC")
        elif c is not None and int(getattr(c, "modified_ntc_teams", 0) or 0) > 0:
            labels.append("M-NTC")
        try:
            import rfa_system as _rs
            if _rs.is_ufa(p):
                labels.append("UFA")
            elif _rs.is_rfa(p):
                labels.append("RFA")
        except Exception:
            pass
        return " / ".join(labels)
    except Exception:
        return ""


def _history_season_label(season):
    try:
        y = int(season)
        return f"{y}-{str(y + 1)[-2:]}"
    except Exception:
        return str(season)


class _PillLabel(QLabel):
    def __init__(self, text, fg="#9aa4b8", parent=None):
        super().__init__(text, parent)
        style = ("border: 1px solid #33415e; border-radius: 10px;"
                 f" padding: 2px 8px; color: {fg}; font-size: 12px;")
        self.setStyleSheet(style)


class PlayerProfileScreen(BaseScreen):
    """Player detail with 7 tabs."""

    title = "Player"

    def __init__(self, game, main_window, parent=None):
        self.player = None
        super().__init__(game, main_window, parent)

    def set_player(self, player):
        self.player = player
        self.refresh()

    # -- layout ---------------------------------------------------------------

    def _build_body(self):
        # header
        header = QFrame()
        header.setObjectName("tile")
        hl = QHBoxLayout(header)
        self._portrait = QLabel("?")
        self._portrait.setFixedSize(96, 96)
        self._portrait.setAlignment(Qt.AlignCenter)
        self._portrait.setStyleSheet(
            "background: #1a2338; border-radius: 48px; font-size: 36px;"
            " color: #9aa4b8; font-weight: 700;")
        hl.addWidget(self._portrait)
        info = QVBoxLayout()
        self._name = QLabel("--")
        self._name.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #ffffff;")
        info.addWidget(self._name)
        self._pills = QHBoxLayout()
        self._pills.setSpacing(6)
        self._pills.addStretch()
        info.addLayout(self._pills)
        self._strip = QLabel("")
        self._strip.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._strip.setWordWrap(True)
        info.addWidget(self._strip)
        self._rights_strip = QLabel("")
        self._rights_strip.setStyleSheet("color: #6b7488; font-size: 12px;")
        self._rights_strip.setWordWrap(True)
        info.addWidget(self._rights_strip)
        hl.addLayout(info, 1)
        self._layout.addWidget(header)

        # tabs
        self._tab_defs = ["overview", "health", "analytics", "personality",
                          "scout", "dynamics", "history"]
        self._tab_labels = ["Overview", "Health", "Analytics", "Personality",
                            "Scout Report", "Dynamics", "History"]
        self._tabs = QTabWidget()
        self._scrolls = {}
        for key, label in zip(self._tab_defs, self._tab_labels):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            self._tabs.addTab(scroll, label)
            self._scrolls[key] = scroll
        self._layout.addWidget(self._tabs, 1)

    # -- context ---------------------------------------------------------------

    def _resolve_gm(self):
        return safe_call(lambda: getattr(self.game, "game_manager", None), context='player_profile/_resolve_gm') or self.game

    def _user_team(self):
        gm = self._resolve_gm()
        return (safe_call(lambda: gm.user_team, context='player_profile/_user_team')
                or safe_call(lambda: getattr(self.game, "user_team", None), context='player_profile/_user_team'))

    def _find_team(self, p):
        gm = self._resolve_gm()
        league = (safe_call(lambda: getattr(gm, "league", None), context='player_profile/_find_team')
                  or safe_call(lambda: getattr(self.game, "league", None), context='player_profile/_find_team'))
        teams = safe_call(lambda: list(getattr(league, "teams", []) or []), [], context='player_profile/_find_team') or []
        user_team = self._user_team()
        if user_team is not None and all(t is not user_team for t in teams):
            teams = [user_team] + teams
        for team in teams:
            for attr in ("roster", "ahl_roster", "prospects"):
                for q in (safe_call(lambda: list(getattr(team, attr, []) or []),
                                [], context='player_profile/_find_team') or []):
                    if q is p:
                        return team
        return user_team

    # -- refresh ----------------------------------------------------------------

    def refresh(self):
        p = self.player
        if p is None:
            self._name.setText("No player selected")
            self._set_portrait_fallback("?")
            for key in self._tab_defs:
                inner = QWidget()
                lay = QVBoxLayout(inner)
                lay.addWidget(QLabel("Select a player to view their profile."))
                lay.addStretch()
                self._scrolls[key].setWidget(inner)
            return
        team = self._find_team(p)
        self._build_header(p, team)
        builders = {
            "overview": self._tab_overview,
            "health": self._tab_health,
            "analytics": self._tab_analytics,
            "personality": self._tab_personality,
            "scout": self._tab_scout,
            "dynamics": self._tab_dynamics,
            "history": self._tab_history,
        }
        for key in self._tab_defs:
            inner = QWidget()
            lay = QVBoxLayout(inner)
            lay.setSpacing(10)
            try:
                builders[key](p, team, lay)
            except Exception as e:
                lay.addWidget(QLabel(f"Could not load this tab: {e}"))
            lay.addStretch()
            self._scrolls[key].setWidget(inner)

    # -- small widget helpers ----------------------------------------------------

    def _section_title(self, text):
        lab = QLabel(text.upper())
        lab.setObjectName("section-header")
        return lab

    def _kv(self, k, v):
        lab = QLabel()
        lab.setText(f"<span style='color:#9aa4b8'>{k}:</span> "
                    f"<b style='color:#ffffff'>{v}</b>")
        lab.setWordWrap(True)
        return lab

    def _note(self, text):
        lab = QLabel(text)
        lab.setStyleSheet("color: #6b7488; font-size: 12px;")
        lab.setWordWrap(True)
        return lab

    def _stat_cards(self, lay, items):
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (label, value) in enumerate(items):
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 8, 10, 8)
            lv = QLabel(str(value))
            lv.setStyleSheet(
                "font-size: 22px; font-weight: 800; color: #ffffff;")
            kv = QLabel(str(label))
            kv.setStyleSheet("font-size: 11px; color: #9aa4b8;")
            cl.addWidget(lv)
            cl.addWidget(kv)
            grid.addWidget(card, 0, i)
        lay.addLayout(grid)

    # -- header -------------------------------------------------------------------

    def _set_portrait_fallback(self, initials):
        self._portrait.setPixmap(QPixmap())
        self._portrait.setText(initials)

    def _build_header(self, p, team):
        pid = str(safe_call(lambda: getattr(p, "id", ""), "", context='player_profile/_build_header'))
        try:
            name = f"{p.first_name} {p.last_name}"
        except Exception:
            name = str(safe_call(lambda: getattr(p, "full_name", "Unknown Player"),
                             "Unknown Player", context='player_profile/_build_header'))
        self._name.setText(name)

        # portrait
        path = _portrait_path(pid)
        pix = QPixmap(path) if path else QPixmap()
        if not pix.isNull():
            self._portrait.setPixmap(
                pix.scaled(96, 96, Qt.KeepAspectRatioByExpanding,
                           Qt.SmoothTransformation))
            self._portrait.setText("")
        else:
            initials = safe_call(
                lambda: f"{p.first_name[0]}{p.last_name[0]}".upper(), "?", context='player_profile/_build_header')
            self._set_portrait_fallback(initials)

        # pills
        while self._pills.count() > 1:
            child = self._pills.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        def add_pill(text, fg="#9aa4b8"):
            self._pills.insertWidget(self._pills.count() - 1,
                                     _PillLabel(text, fg))

        pos = _clean_position(safe_call(lambda: getattr(p, "primary_position",
                                                    ""), "", context='player_profile/_build_header'))
        add_pill(pos)
        arch = safe_call(lambda: getattr(p, "archetype", None), context='player_profile/_build_header')
        if arch:
            add_pill(str(arch))
        add_pill(f"Age {safe_call(lambda: getattr(p, 'age', '?'), '?', context='player_profile/_build_header')}")
        tier = None
        try:
            from attribute_composites import talent_tier_for_player, \
                talent_tier_color
            tier = safe_call(lambda: talent_tier_for_player(p), context='player_profile/_build_header')
            if tier:
                add_pill(str(tier),
                         safe_call(lambda: talent_tier_color(tier), "#9aa3b2", context='player_profile/_build_header'))
        except Exception:
            pass
        try:
            import condition_ui as _cu
            cond = safe_call(lambda: _cu.get_condition(p), None, context='player_profile/_build_header')
            if cond is not None:
                add_pill(f"{cond} {_cu.condition_label(cond)}",
                         safe_call(lambda: _cu.condition_color(cond), "#8fd14f", context='player_profile/_build_header'))
            inj = safe_call(lambda: _cu.injury_status(p), context='player_profile/_build_header')
            if inj:
                add_pill(inj, "#f85149")
        except Exception:
            pass
        form = safe_call(lambda: float(getattr(p, "mesh_form", 0) or 0), 0.0, context='player_profile/_build_header')
        if abs(form) > 1.0:
            form = form / 100.0
        if form >= 0.5:
            add_pill("\U0001F525 Hot hand", "#ff9e4a")
        elif form <= -0.5:
            add_pill("\u2744 Cold", "#7aa2f7")

        jersey = safe_call(lambda: int(getattr(p, "jersey_number", 0) or 0), 0, context='player_profile/_build_header')
        user_team = self._user_team()
        editable = safe_call(lambda: any(
            p is q
            for attr in ("roster", "ahl_roster")
            for q in (getattr(user_team, attr, None) or [])), False, context='player_profile/_build_header')
        if jersey:
            if editable:
                btn = QPushButton(f"#{jersey}")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setToolTip("Click to change jersey number")
                btn.setStyleSheet(
                    "border: 1px solid #2f6fed; border-radius: 10px;"
                    " padding: 2px 8px; color: #7aa2f7; font-size: 12px;"
                    " font-weight: 700;")
                btn.clicked.connect(lambda: self._edit_jersey(p, user_team))
                self._pills.insertWidget(self._pills.count() - 1, btn)
            else:
                add_pill(f"#{jersey}")

        # strips
        team_name = (safe_call(lambda: getattr(team, "team_name", None), context='player_profile/_build_header')
                     or str(safe_call(lambda: getattr(p, "team_name", ""),
                                  "", context='player_profile/_build_header') or "Free Agent"))
        contract = safe_call(lambda: getattr(p, "contract", None), context='player_profile/_build_header')
        salary = (safe_call(lambda: getattr(p, "salary", None), context='player_profile/_build_header')
                  or safe_call(lambda: getattr(contract, "salary", None), context='player_profile/_build_header'))
        years = (safe_call(lambda: getattr(p, "contract_years", None), context='player_profile/_build_header')
                 or safe_call(lambda: getattr(contract, "years_remaining", None), context='player_profile/_build_header'))
        strip = [team_name]
        if salary:
            strip.append(f"${int(salary):,} / yr")
        if years is not None:
            strip.append(f"{years} yr{'s' if years != 1 else ''} left")
        ct = _contract_type_label(p)
        if ct:
            strip.append(ct)
        self._strip.setText("   \u2022   ".join(strip))

        rights_bits = []
        lg = _league_of(team, p)
        if lg:
            rights_bits.append(f"League: {lg}")
        rt_team = str(safe_call(lambda: getattr(p, "rights_team", ""),
                            "", context='player_profile/_build_header') or "").strip()
        if rt_team:
            rt_type = str(safe_call(lambda: getattr(p, "rights_type", ""),
                                "", context='player_profile/_build_header') or "").strip()
            rt_exp = safe_call(lambda: getattr(p, "rights_expiry_year", 0), 0, context='player_profile/_build_header') or 0
            r = f"Rights: {rt_team}"
            if rt_type:
                r += f" ({rt_type})"
            if rt_exp:
                r += f" thru {rt_exp}"
            rights_bits.append(r)
        self._rights_strip.setText("   \u2022   ".join(rights_bits))

    def _edit_jersey(self, p, user_team):
        cur = safe_call(lambda: int(getattr(p, "jersey_number", 0) or 0), 0, context='player_profile/_edit_jersey')
        name = safe_call(lambda: getattr(p, "full_name", "?"), "?", context='player_profile/_edit_jersey')
        n, ok = QInputDialog.getInt(
            self, "Jersey Number",
            f"Number for {name} (current #{cur}).\n"
            f"Retired numbers stay retired; goalie numbers stay with "
            f"goalies; duplicates blocked.",
            cur, 1, 98)
        if not ok or n == cur:
            return
        valid, reason = _jersey_validation(user_team, p, n)
        if not valid:
            QMessageBox.warning(self, "Jersey Number", reason)
            return
        try:
            p.jersey_number = n
        except Exception as e:
            QMessageBox.warning(self, "Jersey Number",
                                f"Could not set number: {e}")
            return
        self.refresh()

    # -- overview ------------------------------------------------------------------

    def _tab_overview(self, p, team, lay):
        goalie = _is_goalie(p)
        # season stats cards
        st = safe_call(lambda: getattr(p, "stats", None), context='player_profile/_tab_overview')
        if goalie:
            items = [
                ("GP", safe_call(lambda: getattr(st, "games_played", 0), 0, context='player_profile/_tab_overview')),
                ("W", safe_call(lambda: getattr(st, "wins", 0), 0, context='player_profile/_tab_overview')),
                ("SV%", safe_call(lambda: f"{getattr(st, 'save_percentage', 0):.3f}",
                              ".000", context='player_profile/_tab_overview')),
                ("GAA", safe_call(lambda: f"{getattr(st, 'goals_against_average', 0):.2f}",
                              "0.00", context='player_profile/_tab_overview')),
            ]
        else:
            g = safe_call(lambda: getattr(st, "goals", 0), 0, context='player_profile/_tab_overview')
            a = safe_call(lambda: getattr(st, "assists", 0), 0, context='player_profile/_tab_overview')
            items = [
                ("GP", safe_call(lambda: getattr(st, "games_played", 0), 0, context='player_profile/_tab_overview')),
                ("G", g), ("A", a), ("PTS", g + a),
            ]
        lay.addWidget(self._section_title("Season Stats"))
        self._stat_cards(lay, items)

        # per-team splits
        try:
            import game_classes as _gc
            splits = safe_call(lambda: list(_gc.current_season_splits(p)),
                           [], context='player_profile/_tab_overview') or []
            splits = [s for s in splits
                      if isinstance(s, dict) and int(s.get("gp", 0) or 0) > 0]
            if len({s.get("team") for s in splits if s.get("team")}) > 1:
                lay.addWidget(self._section_title("Per-Team Splits"))
                for s in splits:
                    lay.addWidget(self._kv(
                        str(s.get("team", "?")),
                        f"{s.get('gp', 0)} GP  {s.get('g', 0)} G  "
                        f"{s.get('a', 0)} A  "
                        f"{int(s.get('g', 0) or 0) + int(s.get('a', 0) or 0)} PTS"))
        except Exception:
            pass

        # contract card
        lay.addWidget(self._section_title("Contract"))
        rows = []
        team_name = (safe_call(lambda: getattr(team, "team_name", None), context='player_profile/_tab_overview')
                     or str(safe_call(lambda: getattr(p, "team_name", ""),
                                  "", context='player_profile/_tab_overview') or "Free Agent"))
        rows.append(("Club", team_name))
        lg = _league_of(team, p)
        if lg:
            rows.append(("League", lg))
        c = safe_call(lambda: getattr(p, "contract", None), context='player_profile/_tab_overview')
        if c is not None:
            sal = safe_call(lambda: getattr(c, "salary", 0), 0, context='player_profile/_tab_overview') or 0
            if sal:
                rows.append(("Salary", _fmt_money(sal)))
            yrs = safe_call(lambda: getattr(c, "years_remaining", None), context='player_profile/_tab_overview')
            if yrs is not None:
                rows.append(("Term", f"{yrs} yr{'s' if yrs != 1 else ''} left"))
            ct = _contract_type_label(p)
            if ct:
                rows.append(("Type", ct))
            sb = safe_call(lambda: getattr(c, "signing_bonus", 0), 0, context='player_profile/_tab_overview') or 0
            if sb:
                rows.append(("Signing bonus", _fmt_money(sb)))
            if safe_call(lambda: getattr(c, "two_way", False), False, context='player_profile/_tab_overview'):
                ahl = safe_call(lambda: getattr(c, "ahl_salary", 0), 0, context='player_profile/_tab_overview') or 0
                rows.append(("AHL salary", _fmt_money(ahl) if ahl else "--"))
            clauses = []
            if safe_call(lambda: getattr(c, "no_movement_clause", False), False, context='player_profile/_tab_overview'):
                clauses.append("NMC")
            if safe_call(lambda: getattr(c, "no_trade_clause", False), False, context='player_profile/_tab_overview'):
                clauses.append("NTC")
            mntc = safe_call(lambda: int(getattr(c, "modified_ntc_teams", 0) or 0),
                         0, context='player_profile/_tab_overview')
            if mntc:
                clauses.append(f"M-NTC ({mntc} teams)")
            if clauses:
                rows.append(("Clauses", ", ".join(clauses)))
        rt_team = str(safe_call(lambda: getattr(p, "rights_team", ""),
                            "", context='player_profile/_tab_overview') or "").strip()
        if rt_team:
            rt_type = str(safe_call(lambda: getattr(p, "rights_type", ""),
                                "", context='player_profile/_tab_overview') or "").strip()
            rt_exp = safe_call(lambda: getattr(p, "rights_expiry_year", 0), 0, context='player_profile/_tab_overview') or 0
            r = rt_team
            if rt_type:
                r += f" ({rt_type})"
            if rt_exp:
                r += f" -- thru {rt_exp}"
            rows.append(("Rights", r))
        dy = safe_call(lambda: getattr(p, "draft_year", None), context='player_profile/_tab_overview')
        dp = str(safe_call(lambda: getattr(p, "draft_position", ""),
                       "", context='player_profile/_tab_overview') or "").strip()
        if dy or dp:
            rows.append(("Drafted", f"{dy or '?'} {dp}".strip()))
        if not rows:
            rows.append(("Contract", "No contract on file"))
        for k, v in rows:
            lay.addWidget(self._kv(k, v))

        # composite ratings
        try:
            import attribute_composites as _ac
            comp = _ac.get_composite_ratings(p)
            labels = _GOALIE_COMPOSITES if goalie else _SKATER_COMPOSITES
            bars = []
            for key, label in labels:
                if key in comp:
                    bars.append((label, _to100(comp[key])))
            if bars:
                lay.addWidget(self._section_title("Composite Ratings"))
                for label, val in bars:
                    lay.addWidget(AttributeBar(label, val))
        except Exception:
            pass

        # attribute groups
        lay.addWidget(self._section_title("Attributes"))
        groups = [("Technical", _GOALIE_TECHNICAL if goalie else _SKATER_TECHNICAL),
                  ("Mental", _GOALIE_MENTAL if goalie else _SKATER_MENTAL),
                  ("Physical", _GOALIE_PHYSICAL if goalie else _SKATER_PHYSICAL)]
        for gname, attrs in groups:
            sub = QLabel(gname)
            sub.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #c8d2e8;"
                " margin-top: 6px;")
            lay.addWidget(sub)
            for label, field in attrs:
                val = safe_call(lambda: getattr(p, field, None), context='player_profile/_tab_overview')
                if val is None:
                    continue
                lay.addWidget(AttributeBar(label, _to100(val)))

    # -- health --------------------------------------------------------------------

    def _tab_health(self, p, team, lay):
        lay.addWidget(self._section_title("Medical Status"))
        try:
            import condition_ui as _cu
        except Exception:
            _cu = None
        cond = safe_call(lambda: _cu.get_condition(p), None, context='player_profile/_tab_health') if _cu else None
        if cond is not None:
            lay.addWidget(self._kv(
                "Condition",
                f"{cond} {safe_call(lambda: _cu.condition_label(cond), '', context='player_profile/_tab_health')}"))
        injured = bool(safe_call(lambda: getattr(p, "is_injured", False), False, context='player_profile/_tab_health'))
        status = safe_call(lambda: _cu.injury_status(p), context='player_profile/_tab_health') if _cu else None
        if injured and status:
            lab = QLabel(f"\U0001F691 {status}")
            lab.setStyleSheet("color: #f85149; font-weight: 700;")
            lay.addWidget(lab)
        elif injured:
            lab = QLabel("\U0001F691 Injured")
            lab.setStyleSheet("color: #f85149; font-weight: 700;")
            lay.addWidget(lab)
        else:
            lab = QLabel("\u2705 Healthy")
            lab.setStyleSheet("color: #3fb950; font-weight: 700;")
            lay.addWidget(lab)

        prone = safe_call(lambda: getattr(p, "injury_proneness",
                                      getattr(p, "injury_prone", 50)), 50, context='player_profile/_tab_health')
        try:
            prone = int(prone or 0)
        except Exception:
            prone = 50
        dur = max(0, min(100, 100 - prone))
        dlab = "Durable" if prone <= 25 else ("Average" if prone <= 55
                                             else "Fragile")
        lay.addWidget(self._kv("Durability", dlab))
        lay.addWidget(AttributeBar("Durability", dur))

        if injured:
            lay.addWidget(self._section_title("Active Injury"))
            itype = str(safe_call(lambda: getattr(p, "injury_type", "Injured"),
                              "Injured", context='player_profile/_tab_health') or "Injured").strip() or "Injured"
            n = safe_call(lambda: int(getattr(p, "games_remaining_injured", 0)
                                  or 0), 0, context='player_profile/_tab_health')
            lay.addWidget(self._kv("Injury", itype))
            lay.addWidget(self._kv("Games remaining", str(n)))
            last_inj = safe_call(lambda: str(getattr(p, "last_injury", "") or ""),
                             "", context='player_profile/_tab_health')
            if last_inj and last_inj != "None":
                lay.addWidget(self._kv("Region", last_inj))
            if "concussion" in itype.lower():
                lab = QLabel("\u26a0 Concussion protocol")
                lab.setStyleSheet("color: #d29922; font-weight: 700;")
                lay.addWidget(lab)

        lay.addWidget(self._section_title("Injury History"))
        entries = []
        last_inj = safe_call(lambda: str(getattr(p, "last_injury", "") or ""), "", context='player_profile/_tab_health')
        inj_type = safe_call(lambda: str(getattr(p, "injury_type", "") or ""), "", context='player_profile/_tab_health')
        if last_inj and last_inj != "None":
            bits = inj_type if inj_type and inj_type != "None" else "Injury"
            bits += f" ({last_inj})"
            entries.append(bits)
        if entries:
            for e in entries:
                lay.addWidget(self._kv("Last injury", e))
        else:
            lay.addWidget(self._note("No recorded injuries."))
        lay.addWidget(self._kv(
            "Career games missed",
            str(safe_call(lambda: int(getattr(p, "career_games_missed", 0)
                                  or 0), 0, context='player_profile/_tab_health'))))
        lay.addWidget(self._kv(
            "Days missed",
            str(safe_call(lambda: int(getattr(p, "days_missed", 0) or 0), 0, context='player_profile/_tab_health'))))
        lay.addWidget(self._kv(
            "Career concussions",
            str(safe_call(lambda: int(getattr(p, "career_concussions", 0)
                                  or 0), 0, context='player_profile/_tab_health'))))

    # -- analytics -------------------------------------------------------------------

    def _basic_analytics(self, p, goalie):
        gp = safe_call(lambda: int(getattr(p, "games_played", 0) or 0), 0, context='player_profile/_basic_analytics') or 1
        if goalie:
            w = safe_call(lambda: int(getattr(p, "wins", 0) or 0), 0, context='player_profile/_basic_analytics')
            sv = safe_call(lambda: float(getattr(p, "save_pct", 0) or 0), 0, context='player_profile/_basic_analytics')
            gaa = safe_call(lambda: float(getattr(p, "gaa", 0) or 0), 0, context='player_profile/_basic_analytics')
            return [("Goaltending -- Basic",
                     [("Wins", str(w), ""), ("Save %", f"{sv:.3f}", ""),
                      ("GAA", f"{gaa:.2f}", "")])]
        g = safe_call(lambda: int(getattr(p, "goals", 0) or 0), 0, context='player_profile/_basic_analytics')
        a = safe_call(lambda: int(getattr(p, "assists", 0) or 0), 0, context='player_profile/_basic_analytics')
        sog = safe_call(lambda: int(getattr(p, "shots", 0) or 0), 0, context='player_profile/_basic_analytics')
        return [("Offense -- Basic",
                 [("Goals / game", f"{g / gp:.2f}", ""),
                  ("Points / game", f"{(g + a) / gp:.2f}", ""),
                  ("Shooting %", f"{(g / sog * 100) if sog else 0:.1f}%", ""),
                  ("Shots", str(sog), "")])]

    def _tab_analytics(self, p, team, lay):
        goalie = _is_goalie(p)
        sections = None
        lens_info = ""
        try:
            import advanced_metrics as am
            import dataclasses as _dc
            lens = None
            user_team = self._user_team() or team
            date_str = str(safe_call(lambda: getattr(self.game,
                                                 "current_date", ""), "", context='player_profile/_tab_analytics'))
            try:
                if user_team is not None:
                    lens = (am.display_goalie_metrics(p, user_team, date_str)
                            if goalie
                            else am.display_skater_metrics(p, user_team,
                                                           date_str))
            except Exception:
                lens = None

            def _val(field, fallback):
                try:
                    if lens is not None and field in lens.values:
                        return lens.values[field]
                except Exception:
                    pass
                return fallback

            def _with_ci(field, text, pct100=False):
                try:
                    if lens is not None and field in lens.ci:
                        ci = lens.ci[field]
                        if text.rstrip().endswith("%"):
                            return (f"{text} ±{ci:.1f} pts" if pct100
                                    else f"{text} ±{ci * 100:.1f} pts")
                        return f"{text} ±{ci:.1f}"
                except Exception:
                    pass
                return text

            def _gloss(key):
                return safe_call(lambda: am.GLOSSARY.get(key, ""), "", context='player_profile/_gloss')

            if lens is not None:
                lens_info = (f"{safe_call(lambda: lens.tier, '', context='player_profile/_tab_analytics')}  "
                             f"as of {safe_call(lambda: lens.as_of, '', context='player_profile/_tab_analytics')}")
            if goalie:
                m = _dc.asdict(am.goalie_advanced(p))
                sections = [
                    ("Goaltending -- Above Expected", [
                        ("GSAx", _with_ci("gsax",
                                          f"{_val('gsax', m['gsax']):+.1f}"),
                         _gloss("GSAx")),
                        ("GSAA", f"{_val('gsaa', m['gsaa']):+.1f}",
                         _gloss("GSAA")),
                        ("High-danger SV%",
                         _with_ci("hdsv_pct",
                                   f"{_val('hdsv_pct', m['hdsv_pct']):.3f}"),
                         _gloss("HDSV%")),
                        ("Quality-start %",
                         _with_ci("qs_pct",
                                   f"{_val('qs_pct', m['qs_pct']):.1%}"),
                         _gloss("QS%")),
                    ]),
                    ("Workload", [
                        ("Save %", f"{_val('sv_pct', m['sv_pct']):.3f}", ""),
                        ("GAA", f"{_val('gaa', m['gaa']):.2f}", ""),
                        ("Shots against / 60",
                         f"{_val('sa_per60', m['sa_per60']):.1f}", ""),
                    ]),
                ]
            else:
                m = _dc.asdict(am.skater_advanced(p))
                sections = [
                    ("Offense -- Finishing & Creation", [
                        ("Shooting %",
                         f"{_val('sh_pct', m['sh_pct']):.1f}%",
                         _gloss("SH%")),
                        ("Individual xG",
                         _with_ci("ixg", f"{_val('ixg', m['ixg']):.1f}"),
                         _gloss("ixG")),
                        ("Goals / 60",
                         f"{_val('g_per60', m['g_per60']):.2f}", ""),
                        ("Points / 60",
                         f"{_val('p_per60', m['p_per60']):.2f}",
                         _gloss("P/60")),
                        ("Game Score",
                         f"{_val('game_score', m['game_score']):.1f}",
                         _gloss("Game Score")),
                    ]),
                    ("Possession -- Driving Play", [
                        ("Corsi %",
                         _with_ci("cf_pct",
                                   f"{_val('cf_pct', m['cf_pct']):.1f}%", True),
                         _gloss("CF%")),
                        ("Fenwick %",
                         _with_ci("ff_pct",
                                   f"{_val('ff_pct', m['ff_pct']):.1f}%", True),
                         _gloss("FF%")),
                        ("Expected-goal share",
                         _with_ci("xgf_pct",
                                   f"{_val('xgf_pct', m['xgf_pct']):.1f}%",
                                   True),
                         _gloss("xGF%")),
                        ("Offensive-zone starts",
                         _with_ci("oz_pct",
                                   f"{_val('oz_pct', m['oz_pct']):.1f}%", True),
                         _gloss("OZ%")),
                    ]),
                    ("Defense & Luck", [
                        ("PDO",
                         _with_ci("pdo", f"{_val('pdo', m['pdo']):.3f}"),
                         _gloss("PDO")),
                        ("Hits", str(int(_val("hits", m["hits"]))), ""),
                        ("Blocked shots",
                         str(int(_val("blocks", m["blocks"]))), ""),
                    ]),
                ]
        except Exception:
            sections = None
        if not sections:
            sections = self._basic_analytics(p, goalie)
        if lens_info:
            lay.addWidget(self._note(lens_info))
        for title, rows in sections:
            lay.addWidget(self._section_title(title))
            table = QTableWidget()
            table.setColumnCount(2)
            table.setRowCount(len(rows))
            table.setHorizontalHeaderLabels(["Metric", "Value"])
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch)
            for r, (k, v, _gloss_text) in enumerate(rows):
                table.setItem(r, 0, QTableWidgetItem(str(k)))
                table.setItem(r, 1, QTableWidgetItem(str(v)))
            table.setMaximumHeight(min(44 + 30 * len(rows), 420))
            lay.addWidget(table)

        # shot tracking summary (real game tracking data)
        try:
            pid = getattr(p, "id", None)
            pname = safe_call(lambda: getattr(p, "full_name", ""), "", context='player_profile/_tab_analytics') or ""
            games = list(safe_call(lambda: getattr(team, "analytics_games",
                                                None) or [], [], context='player_profile/_tab_analytics') or [])
            shots = []
            for rec in games:
                if not isinstance(rec, dict):
                    continue
                for s in (rec.get("shots") or []):
                    if not isinstance(s, dict):
                        continue
                    if pid is not None and s.get("shooter_id") == pid:
                        shots.append(s)
                    elif pname and s.get("shooter") == pname:
                        shots.append(s)
            if shots:
                n_goals = sum(1 for s in shots
                              if str(s.get("outcome", "")).lower() == "goal")
                tot_xg = sum(float(s.get("xg", 0) or 0) for s in shots)
                lay.addWidget(self._note(
                    f"Shot tracking (last {len(games)} tracked games): "
                    f"{len(shots)} shots, {n_goals} goals, {tot_xg:.1f} xG."))
        except Exception:
            pass

    # -- personality ------------------------------------------------------------------

    def _tab_personality(self, p, team, lay):
        lay.addWidget(self._section_title("Personality"))
        try:
            import reputation_system as _rs
            _rs.ensure_reputation_fields(p)
            rs = _rs
        except Exception:
            rs = None
        try:
            import player_decision as _pd
            _pd.ensure_decision_fields(p)
        except Exception:
            pass
        att = safe_call(lambda: rs.describe_attitude(p), None, context='player_profile/_tab_personality') if rs else None
        ff = safe_call(lambda: rs.fan_favourite_score(p, team),
                   {}, context='player_profile/_tab_personality') or {} if rs else {}
        att_colors = {
            "Volatile": "#f85149", "Fiery": "#d29922",
            "Emotional": "#d29922", "Even-keeled": "#3fb950",
            "Model professional": "#58a6ff",
        }
        if att:
            lab = QLabel(f"Attitude: {att}")
            lab.setStyleSheet(
                f"color: {att_colors.get(att, '#9aa3b2')}; font-weight: 700;")
            lay.addWidget(lab)
        fans_tier = safe_call(lambda: ff.get("tier"), "", context='player_profile/_tab_personality')
        if fans_tier:
            lay.addWidget(self._kv("Fan favourite", str(fans_tier)))
        for label, field in (("Morale", "morale"), ("Happiness", "happiness"),
                             ("Loyalty", "loyalty")):
            lay.addWidget(AttributeBar(
                label, _to100(safe_call(lambda: getattr(p, field, 50), 50, context='player_profile/_tab_personality'))))
        amb_labels = {"cup": "Stanley Cup", "money": "Money",
                      "ice_time": "Ice Time", "stability": "Stability",
                      "home": "Hometown"}
        amb = amb_labels.get(
            safe_call(lambda: getattr(p, "ambition", ""), "", context='player_profile/_tab_personality') or "", "")
        rep = safe_call(lambda: int(getattr(p, "reputation", 0) or 0), 0, context='player_profile/_tab_personality')
        lead = safe_call(lambda: int(getattr(p, "leadership", 0) or 0), 0, context='player_profile/_tab_personality')
        rep_line = f"Reputation {rep}/100   \u2022   Leadership {lead}/100"
        if amb:
            rep_line += f"   \u2022   Ambition: {amb}"
        lay.addWidget(self._kv("Profile", rep_line))
        reasons = safe_call(lambda: list(ff.get("reasons", []) or []), [], context='player_profile/_tab_personality') or []
        if reasons:
            lay.addWidget(self._section_title("Why Fans Care"))
            for r in reasons[:2]:
                lay.addWidget(self._kv("\u2022", str(r)))

    # -- scout -------------------------------------------------------------------------

    def _tab_scout(self, p, team, lay):
        lay.addWidget(self._section_title("NHL Readiness"))
        try:
            import prospect_development as pd
            base = pd.callup_readiness(p)
            score, deltas = pd.situational_readiness(p, self._user_team())
            lay.addWidget(self._kv("Readiness",
                                   f"{round(score, 0)}  (base {round(base, 0)})"))
            for label, d in deltas:
                sign = "+" if d > 0 else ""
                lay.addWidget(self._kv(str(label), f"{sign}{round(d, 1)}"))
        except Exception as e:
            lay.addWidget(self._note(f"Readiness unavailable: {e}"))

        lay.addWidget(self._section_title("Scout Report"))
        try:
            import scout_perception as _sp
        except Exception:
            _sp = None
        if _sp is None:
            lay.addWidget(self._note("Scouting module unavailable."))
            return
        try:
            scout, report = _sp.resolve_tab_scout(self._user_team(), p)
        except Exception as e:
            lay.addWidget(self._note(f"Report unavailable: {e}"))
            return
        if scout is None:
            lay.addWidget(self._note("No scout has viewed this player yet."))
            return
        try:
            import analytics_scouting as _as
            record = safe_call(lambda: _as.scout_record_line(scout),
                           "no graded calls yet", context='player_profile/_tab_scout') or "no graded calls yet"
        except Exception:
            record = "no graded calls yet"
        lay.addWidget(self._kv("Scout", safe_call(lambda: _sp.scout_display_name(
            scout), "?", context='player_profile/_tab_scout')))
        lay.addWidget(self._kv("Record", record))
        lay.addWidget(self._kv(
            "Accuracy / Viewings",
            f"{safe_call(lambda: getattr(report, 'accuracy', 'F'), 'F', context='player_profile/_tab_scout') if report else 'F'}"
            f"  \u2022  "
            f"{safe_call(lambda: getattr(report, 'viewings', 0), 0, context='player_profile/_tab_scout') if report else 0}"))
        try:
            comps = _sp.perceived_composites(p, scout, report) or {}
            for key, val in comps.items():
                label = safe_call(lambda: _sp.composite_label(key), key, context='player_profile/_tab_scout')
                if isinstance(val, tuple):
                    lay.addWidget(self._kv(label, f"{val[0]:.0f}-{val[1]:.0f}"))
                else:
                    lay.addWidget(self._kv(label, f"{val:.0f}"))
        except Exception:
            pass
        try:
            import scouting as _sc
            pot = safe_call(lambda: _sc.report_potential_display(report, p), "?", context='player_profile/_tab_scout')
        except Exception:
            pot = "?"
        lay.addWidget(self._kv("Potential", str(pot)))
        strengths, weaknesses = safe_call(
            lambda: _sp.perceived_strengths_weaknesses(p, scout, report),
            ([], []), context='player_profile/_tab_scout')
        if strengths:
            lay.addWidget(self._section_title("Strengths"))
            for s in strengths:
                lay.addWidget(self._kv("\u2022", str(s)))
        if weaknesses:
            lay.addWidget(self._section_title("Weaknesses"))
            for w in weaknesses:
                lay.addWidget(self._kv("\u2022", str(w)))
        notes = ""
        if report and safe_call(lambda: getattr(report, "notes", ""), "", context='player_profile/_tab_scout'):
            notes = str(report.notes)[:600]
        if notes:
            lay.addWidget(self._section_title("Scout Notes"))
            lay.addWidget(self._note(notes))

    # -- dynamics ------------------------------------------------------------------------

    def _tab_dynamics(self, p, team, lay):
        lay.addWidget(self._section_title("Dressing Room Dynamics"))
        try:
            import reputation_system as rs
            rs.ensure_reputation_fields(p)
        except Exception:
            lay.addWidget(self._note("Dynamics unavailable."))
            return
        roster = safe_call(lambda: list(getattr(team, "roster", []) or []),
                       [], context='player_profile/_tab_dynamics') or []
        if roster:
            tiers = safe_call(lambda: rs.team_hierarchy(roster), {}, context='player_profile/_tab_dynamics') or {}
            for tname, ps in tiers.items():
                try:
                    if p in ps:
                        lay.addWidget(self._kv("Room tier", tname))
                        break
                except Exception:
                    continue
        coach = None
        try:
            for s in (getattr(team, "staff", []) or []):
                if str(getattr(getattr(s, "role", None), "name", "")) == \
                        "HEAD_COACH":
                    coach = s
                    break
        except Exception:
            pass
        if coach is not None:
            resp = safe_call(lambda: rs.player_coach_response(p, coach), None, context='player_profile/_tab_dynamics')
            fit = (resp.get("response", "Neutral") if isinstance(resp, dict)
                   else str(resp)) if resp is not None else "Neutral"
            lay.addWidget(self._kv("Coach fit", fit))
        risk = safe_call(lambda: rs.trade_request_risk(p), None, context='player_profile/_tab_dynamics')
        if risk is not None:
            if risk >= 0.5:
                lab = QLabel("Trade risk: HIGH")
                lab.setStyleSheet("color: #f85149; font-weight: 700;")
                lay.addWidget(lab)
            elif risk >= 0.3:
                lab = QLabel("Trade risk: elevated")
                lab.setStyleSheet("color: #d29922; font-weight: 700;")
                lay.addWidget(lab)
        friends = safe_call(lambda: rs.get_friends(p, roster), [], context='player_profile/_tab_dynamics') or []
        if friends:
            lay.addWidget(self._section_title("Friends"))
            for f in friends:
                pl = f.get("player") if isinstance(f, dict) else None
                if pl is not None:
                    lay.addWidget(self._kv(
                        "\u2022", safe_call(
                            lambda: f"{pl.first_name} {pl.last_name}", "?", context='player_profile/_tab_dynamics')))
        league = (safe_call(lambda: getattr(self._resolve_gm(), "league", None), context='player_profile/_tab_dynamics')
                  or safe_call(lambda: getattr(self.game, "league", None), context='player_profile/_tab_dynamics'))
        rivals = safe_call(lambda: rs.get_rivals(p, roster, league), [], context='player_profile/_tab_dynamics') or []
        if rivals:
            lay.addWidget(self._section_title("Rivals"))
            for d in rivals:
                if isinstance(d, dict):
                    lay.addWidget(self._kv(
                        "\u2022",
                        f"{d.get('name', '?')} ({d.get('origin', '?')})"))
        bonds_src = safe_call(lambda: getattr(p, "coach_bonds", None), None, context='player_profile/_tab_dynamics')
        bonds = []
        if isinstance(bonds_src, dict):
            bonds = [str(s) for s in list(bonds_src.values())[:3]]
        elif isinstance(bonds_src, (list, tuple)):
            bonds = [str(s) for s in list(bonds_src)[:3]]
        if bonds:
            lay.addWidget(self._section_title("Coach Bonds"))
            for b in bonds:
                lay.addWidget(self._note(b))

    # -- history --------------------------------------------------------------------------

    def _tab_history(self, p, team, lay):
        goalie = _is_goalie(p)
        try:
            import game_classes as _gc
        except Exception:
            _gc = None
        by_season = {}
        for s in (safe_call(lambda: getattr(p, "season_history", None),
                        [], context='player_profile/_tab_history') or []):
            if isinstance(s, dict):
                by_season.setdefault(s.get("season"), []).append(s)
        seasons = sorted((s for s in by_season if s is not None),
                         reverse=True)
        live = []
        if _gc is not None:
            live = [s for s in (safe_call(lambda: list(
                _gc.current_season_splits(p)), [], context='player_profile/_tab_history') or [])
                if isinstance(s, dict) and int(s.get("gp", 0) or 0) > 0]

        def stint_line(st):
            t = st.get("team", "???")
            gp = int(st.get("gp", 0) or 0)
            if goalie:
                w = int(st.get("w", 0) or 0)
                l = int(st.get("l", 0) or 0)
                sa = int(st.get("sa", 0) or 0)
                sv = int(st.get("sv", 0) or 0)
                return f"{t}: {gp} GP  {w}-{l}  " \
                       f"{(sv / sa if sa else 0.0):.3f} SV%"
            g = int(st.get("g", 0) or 0)
            a = int(st.get("a", 0) or 0)
            return f"{t}: {gp} GP  {g} G  {a} A  {g + a} PTS"

        def season_tot(stints):
            if len(stints) <= 1 or goalie:
                return None
            tg = sum(int(s.get("g", 0) or 0) for s in stints)
            ta = sum(int(s.get("a", 0) or 0) for s in stints)
            tgp = sum(int(s.get("gp", 0) or 0) for s in stints)
            return f"TOT  {tgp} GP  {tg} G  {ta} A  {tg + ta} PTS"

        if seasons or live:
            lay.addWidget(self._section_title("Season History"))
            for s in seasons:
                stints = by_season.get(s, [])
                lab = QLabel(_history_season_label(s))
                lab.setStyleSheet(
                    "font-weight: 700; color: #c8d2e8; margin-top: 8px;")
                lay.addWidget(lab)
                for st in stints:
                    lay.addWidget(self._kv("", stint_line(st)))
                tot = season_tot(stints)
                if tot:
                    lay.addWidget(self._note(tot))
            if live:
                lab = QLabel("Current season")
                lab.setStyleSheet(
                    "font-weight: 700; color: #c8d2e8; margin-top: 8px;")
                lay.addWidget(lab)
                for st in live:
                    lay.addWidget(self._kv("", stint_line(st)))
                tot = season_tot(live)
                if tot:
                    lay.addWidget(self._note(tot))

        # career totals
        all_stints = []
        for s in seasons:
            all_stints.extend(by_season.get(s, []))
        if all_stints:
            lay.addWidget(self._section_title("Career"))
            tgp = sum(int(s.get("gp", 0) or 0) for s in all_stints)
            if goalie:
                tw = sum(int(s.get("w", 0) or 0) for s in all_stints)
                tl = sum(int(s.get("l", 0) or 0) for s in all_stints)
                tsv = sum(int(s.get("sv", 0) or 0) for s in all_stints)
                tsa = sum(int(s.get("sa", 0) or 0) for s in all_stints)
                tso = sum(int(s.get("so", 0) or 0) for s in all_stints)
                lay.addWidget(self._kv(
                    "Career",
                    f"{tgp} GP  {tw}-{tl}  "
                    f"{(tsv / tsa if tsa else 0.0):.3f} SV%  {tso} SO"))
            else:
                tg = sum(int(s.get("g", 0) or 0) for s in all_stints)
                ta = sum(int(s.get("a", 0) or 0) for s in all_stints)
                tpim = sum(int(s.get("pim", 0) or 0) for s in all_stints)
                lay.addWidget(self._kv(
                    "Career",
                    f"{tgp} GP  {tg} G  {ta} A  {tg + ta} PTS  {tpim} PIM"))
        else:
            lay.addWidget(self._note("No season history recorded."))

        # playoffs
        phist = [pl for pl in (safe_call(lambda: getattr(p, "playoff_history",
                                                    None), [], context='player_profile/_tab_history') or [])
                 if isinstance(pl, dict) and int(pl.get("gp", 0) or 0) > 0]
        cur = safe_call(lambda: getattr(p, "playoff_stats", None), context='player_profile/_tab_history')
        if cur is not None and safe_call(lambda: int(
                getattr(cur, "games_played", 0) or 0), 0, context='player_profile/_tab_history') > 0:
            phist.append({
                "season": "Current",
                "gp": safe_call(lambda: int(getattr(cur, "games_played", 0)
                                        or 0), 0, context='player_profile/_tab_history'),
                "g": safe_call(lambda: int(getattr(cur, "goals", 0) or 0), 0, context='player_profile/_tab_history'),
                "a": safe_call(lambda: int(getattr(cur, "assists", 0) or 0), 0, context='player_profile/_tab_history'),
                "pim": safe_call(lambda: int(getattr(cur, "penalties_in_minutes",
                                                 0) or 0), 0, context='player_profile/_tab_history'),
                "w": safe_call(lambda: int(getattr(cur, "wins", 0) or 0), 0, context='player_profile/_tab_history'),
                "l": safe_call(lambda: int(getattr(cur, "losses", 0) or 0), 0, context='player_profile/_tab_history'),
                "sv": safe_call(lambda: int(getattr(cur, "saves", 0) or 0), 0, context='player_profile/_tab_history'),
                "sa": safe_call(lambda: int(getattr(cur, "shots_against", 0)
                                        or 0), 0, context='player_profile/_tab_history'),
                "so": safe_call(lambda: int(getattr(cur, "shutouts", 0) or 0), 0, context='player_profile/_tab_history'),
            })
        phist.sort(key=lambda pl: (0 if pl.get("season") == "Current" else 1,
                                   -(pl["season"]
                                     if isinstance(pl.get("season"), int)
                                     else 0)))
        if phist:
            lay.addWidget(self._section_title("Playoffs"))
            for pl in phist:
                lbl = ("Current playoffs (in progress)"
                       if pl.get("season") == "Current"
                       else _history_season_label(pl.get("season")))
                gp = int(pl.get("gp", 0) or 0)
                if goalie:
                    w = int(pl.get("w", 0) or 0)
                    l = int(pl.get("l", 0) or 0)
                    sv = int(pl.get("sv", 0) or 0)
                    sa = int(pl.get("sa", 0) or 0)
                    lay.addWidget(self._kv(
                        lbl, f"{gp} GP  {w}-{l}  "
                             f"{(sv / sa if sa else 0.0):.3f} SV%"))
                else:
                    g = int(pl.get("g", 0) or 0)
                    a = int(pl.get("a", 0) or 0)
                    lay.addWidget(self._kv(
                        lbl, f"{gp} GP  {g} G  {a} A  {g + a} PTS"))
