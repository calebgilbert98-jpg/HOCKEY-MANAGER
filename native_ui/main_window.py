"""Puck Dynasty native main window (PySide6).

Steam-style native application shell. Hosts the hub dashboard and all
game screens as Qt widgets. No browser, no HTTP -- direct Python calls
into the game logic.
"""
import sys
import os
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame, QGridLayout,
    QSizePolicy, QComboBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QShortcut, QKeySequence

from .theme import THEME_QSS


# Canonical NHL abbreviations (Team objects don't carry an `abbreviation`
# attribute). Mirrors web_ui/bridge.py TEAM_ABBR and playoff_system.TEAM_ABBREVIATIONS.
_TEAM_ABBR = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN", "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL", "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD", "New York Islanders": "NYI",
    "New York Rangers": "NYR", "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS", "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL", "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR", "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA", "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


def _team_abbr(team_name):
    """Canonical NHL 3-letter abbreviation (Team objects don't carry one)."""
    if not team_name:
        return "???"
    return _TEAM_ABBR.get(team_name, team_name[:3].upper())


class TopBar(QWidget):
    """Application header: brand + nav + inbox/save."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self._main = main_window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # Brand (never shrink below content: truncated "PUCK DYN." otherwise)
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand = QLabel("PUCK DYNASTY")
        brand.setObjectName("brand")
        brand.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        brand_sub = QLabel("HOCKEY MANAGER")
        brand_sub.setObjectName("brand-sub")
        brand_sub.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        brand_box.addWidget(brand)
        brand_box.addWidget(brand_sub)
        layout.addLayout(brand_box)
        layout.addSpacing(24)

        # Nav buttons (Minimum horizontal policy: never elide labels like
        # "TRANSACTIONS" -> "RANSACTION" when the window is at 1280px)
        self._nav_buttons = {}
        for name in ["CLUB", "PERSONNEL", "LEAGUE", "TRANSACTIONS",
                     "FINANCES", "SYSTEMS"]:
            btn = QPushButton(name)
            btn.setObjectName("nav-btn")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked, n=name: self._main.show_section(n))
            layout.addWidget(btn)
            self._nav_buttons[name] = btn

        layout.addStretch()

        # Inbox + Save
        self.inbox_btn = QPushButton("INBOX")
        self.inbox_btn.setObjectName("nav-btn")
        self.inbox_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.inbox_btn.setCursor(Qt.PointingHandCursor)
        self.inbox_btn.clicked.connect(self._main.show_inbox)
        layout.addWidget(self.inbox_btn)

        self.save_btn = QPushButton("SAVE")
        self.save_btn.setObjectName("nav-btn")
        self.save_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(lambda: self._main.show_screen("save"))
        layout.addWidget(self.save_btn)

        self.mp_btn = QPushButton("MULTIPLAYER")
        self.mp_btn.setObjectName("nav-btn")
        self.mp_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.mp_btn.setCursor(Qt.PointingHandCursor)
        self.mp_btn.clicked.connect(
            lambda: self._main.show_screen("multiplayer"))
        layout.addWidget(self.mp_btn)

        self.settings_btn = QPushButton("SETTINGS")
        self.settings_btn.setObjectName("nav-btn")
        self.settings_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(
            lambda: self._main.show_screen("settings"))
        layout.addWidget(self.settings_btn)

        self.shortcuts_btn = QPushButton("?")
        self.shortcuts_btn.setObjectName("nav-btn")
        self.shortcuts_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.shortcuts_btn.setCursor(Qt.PointingHandCursor)
        self.shortcuts_btn.setToolTip("Keyboard shortcuts (?)")
        self.shortcuts_btn.clicked.connect(
            lambda: self._main.show_shortcuts_dialog())
        layout.addWidget(self.shortcuts_btn)

    def set_active(self, name):
        for n, btn in self._nav_buttons.items():
            btn.setChecked(n == name)


class HubPage(QWidget):
    """Main dashboard: HTML-hub clone — team header, hero, tiles,
    stat strip, panels, scrolling ticker. Team-color themed."""

    # ---------- color helpers (mirror web hub.js) ----------
    @staticmethod
    def _hex_rgb(hexstr):
        m = re.match(r'^#([0-9a-fA-F]{6})$', str(hexstr or '').strip())
        if not m:
            return None
        n = int(m.group(1), 16)
        return ((n >> 16) & 255, (n >> 8) & 255, n & 255)

    @classmethod
    def _mix_hex(cls, a, b, t):
        ca, cb = cls._hex_rgb(a), cls._hex_rgb(b)
        if not ca or not cb:
            return a
        c = [round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3)]
        return '#%02x%02x%02x' % tuple(c)

    @classmethod
    def _rgba(cls, hexstr, alpha):
        c = cls._hex_rgb(hexstr)
        if not c:
            return hexstr
        return 'rgba(%d,%d,%d,%s)' % (c[0], c[1], c[2], alpha)

    def _team_colors(self, team_name):
        """Return (primary, deep, soft, wash, glow) from real team data."""
        primary = '#3B82F6'
        try:
            from team_identity_system import NHLTeamIdentity
            ident = NHLTeamIdentity()
            tc = ident.get_team_colors(team_name or '')
            if tc and self._hex_rgb(getattr(tc, 'primary', '')):
                primary = tc.primary
        except Exception:
            pass
        deep = self._mix_hex(primary, '#000000', 0.45)
        soft = self._mix_hex(primary, '#0e1626', 0.55)
        wash = self._rgba(primary, 0.10)
        glow = self._rgba(primary, 0.28)
        return primary, deep, soft, wash, glow

    # ---------- construction ----------
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self.setObjectName("hub-page")
        self._ticker_items = []
        self._ticker_pos = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 12, 30, 0)
        outer.setSpacing(0)

        # ---- franchise header ----
        fhead = QHBoxLayout()
        fhead.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(2)
        self.eyebrow = QLabel("FRANCHISE")
        self.eyebrow.setObjectName("hub-eyebrow")
        left.addWidget(self.eyebrow)
        self.team_label = QLabel("\u2014")
        self.team_label.setObjectName("hub-team")
        left.addWidget(self.team_label)
        # pills row (date + streak)
        pills = QHBoxLayout()
        pills.setSpacing(8)
        self.date_pill = QLabel("\u2014")
        self.date_pill.setObjectName("hub-pill")
        self.streak_pill = QLabel("\u2014")
        self.streak_pill.setObjectName("hub-pill")
        pills.addWidget(self.date_pill)
        pills.addWidget(self.streak_pill)
        pills.addStretch()
        left.addLayout(pills)
        fhead.addLayout(left)
        fhead.addStretch()
        self.record_label = QLabel("0-0-0")
        self.record_label.setObjectName("hub-record")
        self.record_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        fhead.addWidget(self.record_label)
        outer.addLayout(fhead)

        # thin rule
        rule = QFrame()
        rule.setObjectName("hub-rule")
        rule.setFixedHeight(1)
        outer.addWidget(rule)
        outer.addSpacing(10)

        # ---- hero CONTINUE SEASON banner ----
        self.hero = QFrame()
        self.hero.setObjectName("hub-hero")
        self.hero.setCursor(Qt.PointingHandCursor)
        self.hero.mousePressEvent = lambda e: self._main.on_continue()
        hero_l = QVBoxLayout(self.hero)
        hero_l.setContentsMargins(26, 16, 26, 12)
        hero_l.setSpacing(8)
        hero_top = QHBoxLayout()
        hero_top.setSpacing(18)
        self.ready_pill = QLabel("\u25cf Ready to play")
        self.ready_pill.setObjectName("hub-ready-pill")
        hero_top.addWidget(self.ready_pill)
        hero_title = QLabel("CONTINUE SEASON")
        hero_title.setObjectName("hub-hero-title")
        hero_top.addWidget(hero_title)
        hero_top.addStretch()
        # arrow circle + next game
        self.hero_arrow = QLabel("\u2192")
        self.hero_arrow.setObjectName("hub-hero-arrow")
        self.hero_arrow.setAlignment(Qt.AlignCenter)
        hero_top.addWidget(self.hero_arrow)
        self.hero_next = QLabel("Next: \u2014")
        self.hero_next.setObjectName("hub-hero-next")
        hero_top.addWidget(self.hero_next)
        hero_l.addLayout(hero_top)
        # auto-advance row
        hero_foot = QHBoxLayout()
        self.auto_btn = QPushButton("\u25b6 Auto-advance")
        self.auto_btn.setObjectName("hub-auto-btn")
        self.auto_btn.setCursor(Qt.PointingHandCursor)
        self.auto_btn.clicked.connect(self._on_auto_advance)
        hero_foot.addWidget(self.auto_btn)
        hero_foot.addStretch()
        hero_l.addLayout(hero_foot)
        outer.addWidget(self.hero)
        outer.addSpacing(12)

        # ---- primary tiles: ROSTER / INBOX / SCHEDULE / TEAM STATS ----
        tile_grid = QGridLayout()
        tile_grid.setSpacing(12)
        self._nav_tiles = {}
        primary = [
            ("roster", "ROSTER", "\U0001f465", "roster"),
            ("inbox", "INBOX", "\U0001f4e5", "inbox"),
            ("schedule", "SCHEDULE", "\U0001f4c5", "schedule"),
            ("stats", "TEAM STATS", "\U0001f4ca", "stats"),
        ]
        for i, (key, label, icon, screen) in enumerate(primary):
            tile = self._make_nav_tile(label, icon, screen, big=True)
            tile_grid.addWidget(tile, 0, i)
            self._nav_tiles[key] = tile
        # inbox badge
        self.inbox_badge = QLabel("0")
        self.inbox_badge.setObjectName("hub-badge")
        self.inbox_badge.setAlignment(Qt.AlignCenter)
        self.inbox_badge.hide()
        self._nav_tiles["inbox"]._badge_holder.addWidget(self.inbox_badge)
        outer.addLayout(tile_grid)
        outer.addSpacing(14)

        # ---- MORE label ----
        more = QLabel("MORE")
        more.setObjectName("hub-more-label")
        outer.addWidget(more)
        outer.addSpacing(8)

        # ---- secondary tiles ----
        more_grid = QGridLayout()
        more_grid.setSpacing(12)
        secondary = [
            ("lines", "LINES", "\U0001f4cb", "Line combinations", "lines"),
            ("trades", "TRADES", "\u21c4", "Trade center", "trades"),
            ("scouting", "SCOUTING", "\U0001f50d", "Assignments", "scouting"),
            ("staff", "STAFF", "\U0001f454", "Coaches & management", "staff"),
            ("tactics", "TACTICS", "\U0001f3af", "Systems & practice", "tactics"),
        ]
        for i, (key, label, icon, sub, screen) in enumerate(secondary):
            tile = self._make_nav_tile(label, icon, screen, big=False,
                                       sub=sub)
            more_grid.addWidget(tile, 0, i)
            self._nav_tiles[key] = tile
        # 6th column spacer to match HTML 6-col grid (5 tiles + empty)
        outer.addLayout(more_grid)
        outer.addSpacing(12)

        # ---- stat strip (8 blocks) ----
        strip = QHBoxLayout()
        strip.setSpacing(8)
        self._strip = {}
        strip_defs = [
            ("record", "RECORD"), ("points", "POINTS"),
            ("gf", "GOALS / GM"), ("ga", "AGAINST / GM"),
            ("pp", "POWER PLAY"), ("pk", "PENALTY KILL"),
            ("streak", "STREAK"), ("cap", "CAP SPACE"),
        ]
        for key, label in strip_defs:
            cell = self._make_strip_cell(label)
            strip.addWidget(cell, 1)
            self._strip[key] = cell
        outer.addLayout(strip)
        outer.addSpacing(12)

        # ---- panels grid (4 columns, matching HTML .th-panels) ----
        panels = QGridLayout()
        panels.setSpacing(12)
        self.panel_next = self._make_panel("NEXT GAME")
        panels.addWidget(self.panel_next, 0, 0)
        self.panel_stand = self._make_panel("DIVISION")
        panels.addWidget(self.panel_stand, 0, 1)
        self.panel_lead = self._make_panel("TEAM LEADERS")
        panels.addWidget(self.panel_lead, 0, 2)
        self.panel_form = self._make_panel("RECENT FORM")
        panels.addWidget(self.panel_form, 0, 3)
        # Batch D: the 7 HTML panels the native hub was missing
        self.panel_sched = self._make_panel("SCHEDULE")
        panels.addWidget(self.panel_sched, 1, 0)
        self.panel_inj = self._make_panel("INJURIES", click_screen="dressing_room")
        panels.addWidget(self.panel_inj, 1, 1)
        self.panel_morale = self._make_panel("MORALE", click_screen="dressing_room")
        panels.addWidget(self.panel_morale, 1, 2)
        self.panel_prosp = self._make_panel("TOP PROSPECTS", click_screen="development")
        panels.addWidget(self.panel_prosp, 1, 3)
        self.panel_mile = self._make_panel("MILESTONES")
        panels.addWidget(self.panel_mile, 2, 0)
        self.panel_iconic = self._make_panel("ICONIC GAMES", click_screen="history")
        panels.addWidget(self.panel_iconic, 2, 1)
        self.panel_inbox = self._make_panel("INBOX \u2014 RECENT", click_screen="inbox")
        panels.addWidget(self.panel_inbox, 2, 2)
        panels.setColumnStretch(0, 11)
        panels.setColumnStretch(1, 13)
        panels.setColumnStretch(2, 15)
        panels.setColumnStretch(3, 10)
        outer.addLayout(panels)

        outer.addStretch()

        # ---- ticker (bottom, scrolling marquee) ----
        tick_wrap = QHBoxLayout()
        tick_wrap.setSpacing(0)
        tick_wrap.setContentsMargins(0, 0, 0, 0)
        tick_label = QLabel("PUCK DYNASTY WIRE")
        tick_label.setObjectName("hub-ticker-label")
        tick_wrap.addWidget(tick_label)
        self.ticker = QLabel("Loading scores\u2026")
        self.ticker.setObjectName("hub-ticker")
        self.ticker.setCursor(Qt.PointingHandCursor)
        self.ticker.mousePressEvent = lambda e: self._main.show_screen("news")
        tick_wrap.addWidget(self.ticker, 1)
        outer.addLayout(tick_wrap)

        # ticker scroll timer
        self._ticker_timer = QTimer(self)
        self._ticker_timer.timeout.connect(self._scroll_ticker)
        self._ticker_timer.start(120)

        self._apply_base_styles()

    # ---------- widget factories ----------
    def _apply_base_styles(self):
        self.setStyleSheet("""
            #hub-page { background: #060a13; }
            #hub-eyebrow {
                font-size: 12px; font-weight: 800; letter-spacing: 3px;
                color: #3B82F6;
            }
            #hub-team {
                font-size: 46px; font-weight: 900; color: #ffffff;
            }
            #hub-record {
                font-size: 30px; font-weight: 800; color: #ffffff;
                letter-spacing: 1px;
            }
            #hub-pill {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 12px; padding: 4px 12px;
                font-size: 12px; color: #e5e9f0;
            }
            #hub-rule { background: rgba(255,255,255,0.09); border: none; }
            #hub-ready-pill {
                background: rgba(6,12,26,0.32);
                border: 1px solid rgba(255,255,255,0.28);
                border-radius: 14px; padding: 6px 14px;
                font-size: 13px; font-weight: 600; color: #ffffff;
            }
            #hub-hero-title {
                font-size: 44px; font-weight: 900; color: #ffffff;
            }
            #hub-hero-arrow {
                background: #ffffff; color: #1c3f92;
                border-radius: 22px; min-width: 44px; min-height: 44px;
                max-width: 44px; max-height: 44px;
                font-size: 22px; font-weight: 800;
            }
            #hub-hero-next { font-size: 15px; color: rgba(255,255,255,0.94); }
            #hub-auto-btn {
                background: #1b2334; color: #c6cdd8;
                border: 1px solid #2a3550; border-radius: 8px;
                padding: 6px 14px; font-size: 13px;
            }
            #hub-auto-btn:hover { border-color: #3B82F6; color: #f2f5fa; }
            #hub-more-label {
                font-size: 12px; font-weight: 800; letter-spacing: 4px;
                color: rgba(255,255,255,0.38);
            }
            #hub-badge {
                background: #f0435a; color: #ffffff; border-radius: 16px;
                min-width: 32px; min-height: 32px; max-width: 32px; max-height: 32px;
                font-size: 16px; font-weight: 800;
            }
            #hub-strip-cell {
                background: #131a26;
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 4px; padding: 8px 10px;
            }
            #hub-strip-val { font-size: 22px; font-weight: 800; color: #ffffff; }
            #hub-strip-label {
                font-size: 10px; font-weight: 700; letter-spacing: 1px;
                color: #3B82F6;
            }
            #hub-strip-sub { font-size: 10px; color: #6b7280; }
            #hub-panel {
                background: #070b14;
                border: 1px solid #1b2740; border-radius: 3px;
            }
            #hub-panel-head {
                font-size: 13px; font-weight: 700; letter-spacing: 2px;
                color: #ffffff;
                background: #0e1626; padding: 8px 12px;
            }
            #hub-ticker-label {
                background: #1e3a8a; color: #ffffff;
                font-size: 11px; font-weight: 800; letter-spacing: 2px;
                padding: 8px 14px;
            }
            #hub-ticker {
                background: #04060b; color: #f4f6fb;
                font-size: 13px; font-weight: 600; letter-spacing: 0.6px;
                padding: 8px 12px;
            }
        """)

    def _make_nav_tile(self, label, icon, screen, big=True, sub=""):
        frame = QFrame()
        frame.setObjectName("hub-nav-tile")
        frame.setCursor(Qt.PointingHandCursor)
        frame.setMinimumHeight(132 if big else 96)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        ic = QLabel(icon)
        ic.setStyleSheet(
            "font-size: %dpx; color: #3B82F6; background: transparent; border: none;"
            % (32 if big else 26))
        top.addWidget(ic)
        top.addStretch()
        badge_holder = QVBoxLayout()
        badge_holder.setContentsMargins(0, 0, 0, 0)
        top.addLayout(badge_holder)
        lay.addLayout(top)
        lay.addStretch()
        lb = QLabel(label)
        lb.setStyleSheet(
            "font-size: %dpx; font-weight: 900; color: #ffffff; background: transparent;"
            % (22 if big else 17))
        lay.addWidget(lb)
        if sub:
            sb = QLabel(sub)
            sb.setStyleSheet(
                "font-size: 12px; color: rgba(255,255,255,0.55);"
                " background: transparent;")
            lay.addWidget(sb)
        frame.setStyleSheet(
            "#hub-nav-tile { background: #0d1526;"
            " border: 1px solid rgba(255,255,255,0.09);"
            " border-radius: 10px; }")
        frame.mousePressEvent = lambda e, s=screen: self._main.show_screen(s)
        frame._badge_holder = badge_holder
        return frame

    def _make_strip_cell(self, label):
        cell = QFrame()
        cell.setObjectName("hub-strip-cell")
        lay = QVBoxLayout(cell)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(1)
        val = QLabel("\u2014")
        val.setObjectName("hub-strip-val")
        val.setAlignment(Qt.AlignCenter)
        lab = QLabel(label)
        lab.setObjectName("hub-strip-label")
        lab.setAlignment(Qt.AlignCenter)
        sub = QLabel("")
        sub.setObjectName("hub-strip-sub")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(val)
        lay.addWidget(lab)
        lay.addWidget(sub)
        cell._val = val
        cell._sub = sub
        return cell

    def _make_panel(self, title, click_screen=None):
        panel = QFrame()
        panel.setObjectName("hub-panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QLabel(title)
        head.setObjectName("hub-panel-head")
        if click_screen:
            head.setCursor(Qt.PointingHandCursor)
            head.setStyleSheet(
                "font-size: 12px; font-weight: 800; letter-spacing: 2px;"
                " color: #9aa3b2; padding: 10px 12px 0 12px;"
                " background: transparent; text-decoration: underline;")
            head.mousePressEvent = (
                lambda e, s=click_screen: self._main.show_screen(s))
        lay.addWidget(head)
        body_wrap = QWidget()
        body = QVBoxLayout(body_wrap)
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(6)
        lay.addWidget(body_wrap)
        panel._body = body
        panel._head = head
        return panel

    def _clear_panel(self, panel):
        while panel._body.count():
            item = panel._body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            else:
                sub = item.layout()
                if sub:
                    while sub.count():
                        si = sub.takeAt(0)
                        sw = si.widget()
                        if sw:
                            sw.deleteLater()

    # ---------- interactions ----------
    def _on_auto_advance(self):
        game = getattr(self._main, "game", None)
        if game and hasattr(game, "toggle_auto_advance"):
            try:
                game.toggle_auto_advance()
            except Exception as e:
                print("[hub] auto-advance failed: %s" % e)
        else:
            print("[hub] auto-advance not available on this game object")

    def _scroll_ticker(self):
        if not self._ticker_items:
            return
        text = "   \u2022   ".join(self._ticker_items)
        if len(text) < 2:
            return
        self._ticker_pos = (self._ticker_pos + 1) % len(text)
        window = 140
        doubled = text + "   \u2022   " + text
        start = self._ticker_pos % len(text)
        self.ticker.setText(doubled[start:start + window].upper())

    # ---------- data helpers ----------
    def set_tile(self, key, value, sub=""):
        # Back-compat shim: old tile keys map to strip cells
        if key in self._strip:
            self._strip[key]._val.setText(str(value))
            self._strip[key]._sub.setText(str(sub))

    def _game_val(self, obj, *names, default=None):
        for n in names:
            if isinstance(obj, dict):
                v = obj.get(n, None)
            else:
                v = getattr(obj, n, None)
            if v is not None:
                return v
        return default

    @staticmethod
    def _team_name_of(t):
        """Normalize a schedule team ref (Team object or plain string) to a name."""
        if t is None:
            return ""
        if isinstance(t, str):
            return t
        return getattr(t, "team_name", "") or ""

    def _sched_date(self, g):
        if isinstance(g, (tuple, list)) and len(g) >= 1:
            return g[0]
        return self._game_val(g, "date")

    def _sched_teams(self, g):
        if isinstance(g, (tuple, list)):
            home = g[1] if len(g) > 1 else None
            away = g[2] if len(g) > 2 else None
        else:
            home = self._game_val(g, "home_team", "home", default=None)
            away = self._game_val(g, "away_team", "away", default=None)
        return self._team_name_of(home), self._team_name_of(away)

    def _sched_is_game(self, g):
        """True if this schedule entry is a real game (not an event marker)."""
        if isinstance(g, (tuple, list)):
            return len(g) >= 3 and g[1] != 'NHL_EVENT'
        if self._game_val(g, "event_type") == 'NHL_EVENT':
            return False
        if self._game_val(g, "playoff"):
            return False
        if (self._game_val(g, "league", default="NHL") or "NHL") != "NHL":
            return False
        return True

    def _sched_played(self, g):
        return bool(self._game_val(g, "played", default=False))

    def _sched_scores(self, g):
        """Return (home_score, away_score) or (None, None) if not played."""
        hs = self._game_val(g, "home_score", default=None)
        aws = self._game_val(g, "away_score", default=None)
        if hs is None or aws is None:
            return None, None
        try:
            return int(hs), int(aws)
        except Exception:
            return None, None

    def _pstat(self, p, field, default=0):
        """Authoritative season stat for a player.

        The sim writes season totals to p.stats (PlayerStats); the direct
        Player attributes (p.goals etc.) are legacy and never updated.
        Falls back to the direct attribute for non-Player objects.
        """
        st = getattr(p, "stats", None)
        if st is not None:
            v = getattr(st, field, None)
            if v is not None:
                return v
        return getattr(p, field, default)

    def _team_recent_results(self, gm, team, n=10):
        """Last-n W/L/OTL results for team, oldest first.

        Prefers team.recent_results; derives from gm.game_results when the
        attribute was never populated (root cause of the empty STREAK tile).
        """
        recent = getattr(team, "recent_results", None) or []
        if recent:
            return [str(r) for r in recent[-n:]]
        tname = getattr(team, "team_name", "") or ""
        if not tname:
            return []
        results = getattr(gm, "game_results", None) or []
        out = []
        for r in results:
            if not isinstance(r, dict):
                continue
            h = self._team_name_of(r.get("home_team"))
            a = self._team_name_of(r.get("away_team"))
            if tname not in (h, a):
                continue
            w = self._team_name_of(r.get("winner"))
            if w == tname:
                out.append("W")
            elif r.get("overtime") or r.get("shootout"):
                out.append("OTL")
            else:
                out.append("L")
        return out[-n:]

    # ---------- refresh ----------
    def refresh(self, game=None):
        if game is None:
            game = getattr(self._main, "game", None)
        if game is None:
            return
        try:
            gm = getattr(game, "game_manager", None) or game
            team = getattr(gm, "user_team", None) or getattr(game, "user_team", None)
            if not team:
                return
            team_name = getattr(team, "team_name", "") or ""
            primary, deep, soft, wash, glow = self._team_colors(team_name)

            # ---- team theming ----
            self.eyebrow.setStyleSheet(
                "font-size: 12px; font-weight: 800; letter-spacing: 3px; "
                "color: %s;" % primary)
            self.hero.setStyleSheet(
                "#hub-hero { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                " stop:0 %s, stop:0.55 #1f5ad0, stop:1 #16367f);"
                " border-radius: 12px; }" % deep)
            for _key, tile in self._nav_tiles.items():
                tile.setStyleSheet(
                    "#hub-nav-tile { background: #0d1526;"
                    " border: 1px solid rgba(255,255,255,0.09);"
                    " border-top: 3px solid %s;"
                    " border-radius: 10px; }" % soft)
            for _key, cell in self._strip.items():
                cell.setStyleSheet(
                    "#hub-strip-cell { background: #131a26;"
                    " border: 1px solid rgba(255,255,255,0.07);"
                    " border-top: 2px solid %s;"
                    " border-radius: 4px; padding: 8px 10px; }" % soft)

            # ---- header ----
            self.team_label.setText(team_name.upper())
            wins = getattr(team, "wins", 0) or 0
            losses = getattr(team, "losses", 0) or 0
            otl = getattr(team, "otl", 0) or getattr(team, "ties", 0) or 0
            self.record_label.setText("%d-%d-%d" % (wins, losses, otl))

            try:
                date = getattr(game, "current_date", None) or getattr(gm, "current_date", None)
                datestr = str(date) if date else ""
                m = re.search(r"(19|20)\d{2}", datestr)
                if m:
                    y = int(m.group(0))
                    self.eyebrow.setText(
                        "FRANCHISE \u00b7 %d-%s SEASON" % (y, str(y + 1)[2:]))
                if date:
                    try:
                        self.date_pill.setText(
                            "\U0001f4c5 " + date.strftime("%B %d, %Y"))
                    except Exception:
                        self.date_pill.setText("\U0001f4c5 " + datestr)
            except Exception:
                pass

            try:
                recent = self._team_recent_results(gm, team, 10)
                if recent:
                    self.streak_pill.setText(
                        "\U0001f525 " + str(recent[-1]).upper())
                else:
                    self.streak_pill.setText("\U0001f525 \u2014")
            except Exception:
                pass

            # ---- strip ----
            gp = wins + losses + otl
            self._strip["record"]._val.setText("%d-%d-%d" % (wins, losses, otl))
            self._strip["record"]._sub.setText("%d GP" % gp)

            division = getattr(team, "division", "") or ""
            div_teams = []
            try:
                league = getattr(game, "league", None) or getattr(gm, "league", None)
                if league and division:
                    div_teams = [t for t in (getattr(league, "teams", []) or [])
                                 if getattr(t, "division", "") == division]

                    def _pts(t):
                        return (getattr(t, "wins", 0) or 0) * 2 + (getattr(t, "otl", 0) or 0)
                    div_teams.sort(key=_pts, reverse=True)
                rank = next((i + 1 for i, t in enumerate(div_teams) if t is team), None)
                pts = wins * 2 + otl
                self._strip["points"]._val.setText(str(pts))
                if rank:
                    suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank, "th")
                    self._strip["points"]._sub.setText(
                        "%d%s in division" % (rank, suffix))
                else:
                    self._strip["points"]._sub.setText(division or "")
            except Exception:
                pass

            try:
                gf = getattr(team, "goals_for", 0) or 0
                ga = getattr(team, "goals_against", 0) or 0
                if gp > 0:
                    self._strip["gf"]._val.setText("%.1f" % (gf / gp))
                    self._strip["ga"]._val.setText("%.1f" % (ga / gp))
                self._strip["gf"]._sub.setText("Offense")
                self._strip["ga"]._sub.setText("Defense")
            except Exception:
                pass

            try:
                pp = getattr(team, "power_play_pct", None)
                pk = getattr(team, "penalty_kill_pct", None)
                self._strip["pp"]._val.setText(
                    ("%.1f%%" % pp) if pp is not None else "\u2014")
                self._strip["pk"]._val.setText(
                    ("%.1f%%" % pk) if pk is not None else "\u2014")
                self._strip["pp"]._sub.setText("Conversion")
                self._strip["pk"]._sub.setText("Kill rate")
            except Exception:
                pass

            try:
                recent = self._team_recent_results(gm, team, 10)
                if recent:
                    last10 = recent[-10:]
                    w = sum(1 for r in last10 if str(r).upper().startswith("W"))
                    l = sum(1 for r in last10 if str(r).upper().startswith("L"))
                    o = len(last10) - w - l
                    self._strip["streak"]._val.setText(
                        ("%d-%d-%d" % (w, l, o)) if o else ("%d-%d" % (w, l)))
                else:
                    self._strip["streak"]._val.setText("\u2014")
                self._strip["streak"]._sub.setText("Last 10")
            except Exception:
                pass

            try:
                from salary_cap_system import cap_breakdown
                bd = cap_breakdown(team)
                space = bd.get("space", 0)
                self._strip["cap"]._val.setText("$%.2fM" % (space / 1e6))
                self._strip["cap"]._sub.setText("Salary cap")
            except Exception:
                pass

            # ---- next game (date-driven: the schedule carries no 'played'
            # flag; games sim when their date == current_date, so upcoming
            # means date > today and involving the user's team) ----
            next_txt = "Next: \u2014"
            next_game = None
            try:
                league = getattr(game, "league", None) or getattr(gm, "league", None)
                sched = getattr(league, "schedule", None) or []
                today = getattr(game, "current_date", None) or getattr(gm, "current_date", None)
                upcoming = []
                for g in sched:
                    try:
                        if not self._sched_is_game(g):
                            continue
                        gd = self._sched_date(g)
                        if gd is None:
                            continue
                        if today is not None and gd <= today:
                            continue
                        home, away = self._sched_teams(g)
                        if team_name and team_name in (home, away):
                            upcoming.append((gd, g))
                    except Exception:
                        continue
                upcoming.sort(key=lambda x: x[0])
                if upcoming:
                    next_game = upcoming[0][1]
                    home, away = self._sched_teams(next_game)
                    if home == team_name:
                        next_txt = "Next: %s at %s" % (away, team_name)
                    else:
                        next_txt = "Next: %s at %s" % (team_name, home)
            except Exception:
                pass
            self.hero_next.setText(next_txt)
            if next_game is not None:
                self._fill_next_panel(next_game, team_name)

            # ---- inbox badge ----
            try:
                inbox = getattr(game, "inbox", None) or getattr(gm, "inbox", None) or []
                unread = 0
                for msg in inbox:
                    if isinstance(msg, dict):
                        if not msg.get("read", False):
                            unread += 1
                    elif not getattr(msg, "read", False):
                        unread += 1
                if unread > 0:
                    self.inbox_badge.setText(str(unread))
                    self.inbox_badge.show()
                else:
                    self.inbox_badge.hide()
            except Exception:
                pass

            # ---- panels ----
            self._fill_standings(div_teams, team, division, primary, wash)
            self._fill_leaders(team)
            self._fill_form(team, gm)
            # Batch D: the 7 HTML panels the native hub was missing
            self._fill_sched_panel(game, gm, team, team_name)
            self._fill_injuries(team)
            self._fill_morale_panel(team)
            self._fill_prospects(team)
            self._fill_milestones(team)
            self._fill_iconic(team)
            self._fill_inbox_recent(team)

            # ---- ticker ----
            self._fill_ticker(game, gm)
        except Exception as e:
            print("[hub] refresh failed: %s" % e)

    def _fill_next_panel(self, g, team_name):
        panel = self.panel_next
        self._clear_panel(panel)
        home, away = self._sched_teams(g)
        is_home = (home == team_name)
        try:
            when = self._game_val(g, "date", default="")
            datestr = when.strftime("%a %b %d").upper()
        except Exception:
            datestr = str(self._game_val(g, "date", default="")).upper()
        date_l = QLabel(datestr or "")
        date_l.setStyleSheet(
            "font-size: 12px; letter-spacing: 1px; color: #9aa3b2;"
            " background: transparent;")
        panel._body.addWidget(date_l)

        def _team_col(abbr, name):
            col = QVBoxLayout()
            col.setSpacing(2)
            a = QLabel(abbr)
            a.setStyleSheet(
                "font-size: 26px; font-weight: 800; color: #ffffff;"
                " background: transparent;")
            n = QLabel(name)
            n.setStyleSheet(
                "font-size: 12px; color: #f4f6fb; background: transparent;")
            n.setWordWrap(True)
            col.addWidget(a)
            col.addWidget(n)
            return col

        row = QHBoxLayout()
        row.setSpacing(10)
        my_abbr = _team_abbr(team_name)
        if is_home:
            opp_abbr = _team_abbr(away)
            row.addLayout(_team_col(opp_abbr, away))
            at = QLabel("@")
            at.setStyleSheet(
                "font-size: 18px; color: #3B82F6; font-weight: 700;"
                " background: transparent;")
            row.addWidget(at)
            row.addLayout(_team_col(my_abbr, team_name))
        else:
            opp_abbr = _team_abbr(home)
            row.addLayout(_team_col(my_abbr, team_name))
            at = QLabel("@")
            at.setStyleSheet(
                "font-size: 18px; color: #3B82F6; font-weight: 700;"
                " background: transparent;")
            row.addWidget(at)
            row.addLayout(_team_col(opp_abbr, home))
        panel._body.addLayout(row)
        venue = QLabel("HOME" if is_home else "AWAY")
        venue.setStyleSheet(
            "font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #3B82F6;"
            " border: 1px solid #3B82F6; border-radius: 3px; padding: 2px 10px;"
            " background: transparent;")
        panel._body.addWidget(venue)

    def _fill_standings(self, div_teams, team, division, primary, wash):
        panel = self.panel_stand
        panel._head.setText(
            ("%s DIVISION" % division.upper()) if division else "DIVISION STANDINGS")
        panel._head.setStyleSheet(
            "font-size: 13px; font-weight: 700; letter-spacing: 2px;"
            " color: #ffffff; background: #0e1626; padding: 8px 12px;"
            " border-bottom: 2px solid %s;" % primary)
        self._clear_panel(panel)
        if not div_teams:
            e = QLabel("No standings data")
            e.setStyleSheet("color: #6b7280; font-size: 12px; background: transparent;")
            panel._body.addWidget(e)
            return
        grid = QGridLayout()
        grid.setSpacing(4)
        headers = ["#", "TEAM", "W", "L", "OTL", "PTS"]
        for j, h in enumerate(headers):
            l = QLabel(h)
            l.setStyleSheet(
                "font-size: 11px; letter-spacing: 1px; color: #6b7280;"
                " background: transparent;")
            l.setAlignment(Qt.AlignLeft if j == 1 else Qt.AlignRight)
            grid.addWidget(l, 0, j)
        for i, t in enumerate(div_teams[:8]):
            w = getattr(t, "wins", 0) or 0
            lv = getattr(t, "losses", 0) or 0
            o = getattr(t, "otl", 0) or 0
            pts = w * 2 + o
            tn = getattr(t, "team_name", "?") or "?"
            abbr = _team_abbr(tn)
            me = (t is team)
            vals = [str(i + 1), "%s  %s" % (abbr, tn),
                    str(w), str(lv), str(o), str(pts)]
            for j, v in enumerate(vals):
                lab = QLabel(v)
                st = "font-size: 12.5px; color: #f4f6fb; padding: 3px 6px;" \
                     " background: transparent;"
                if me:
                    st = "font-size: 12.5px; color: #ffffff; padding: 3px 6px;" \
                         " background: %s; font-weight: 700;" % wash
                if j == 5:
                    st += " font-weight: 800;"
                lab.setStyleSheet(st)
                lab.setAlignment(Qt.AlignLeft if j == 1 else Qt.AlignRight)
                grid.addWidget(lab, i + 1, j)
        panel._body.addLayout(grid)

    def _fill_leaders(self, team):
        panel = self.panel_lead
        self._clear_panel(panel)
        try:
            roster = [p for p in (getattr(team, "roster", None) or [])
                      if not getattr(p, "is_goalie", False)]
            if not roster:
                return
            cols = QHBoxLayout()
            cols.setSpacing(10)
            for title, keyfn in [
                    ("POINTS", lambda p: self._pstat(p, "goals") + self._pstat(p, "assists")),
                    ("GOALS", lambda p: self._pstat(p, "goals")),
                    ("ASSISTS", lambda p: self._pstat(p, "assists"))]:
                col = QVBoxLayout()
                col.setSpacing(2)
                t = QLabel(title)
                t.setStyleSheet(
                    "font-size: 11px; letter-spacing: 1px; color: #9aa3b2;"
                    " background: transparent;")
                col.addWidget(t)
                top3 = sorted(roster, key=keyfn, reverse=True)[:3]
                for i, p in enumerate(top3):
                    name = getattr(p, "full_name", "?") or "?"
                    pos = getattr(p, "position", "") or ""
                    val = keyfn(p)
                    row = QHBoxLayout()
                    row.setSpacing(6)
                    rk = QLabel(str(i + 1))
                    rk.setStyleSheet(
                        "font-size: 11px; color: #6b7280; background: transparent;")
                    nm = QLabel(name)
                    nm.setStyleSheet(
                        "font-size: 12.5px; color: #f4f6fb; background: transparent;")
                    em = QLabel(pos)
                    em.setStyleSheet(
                        "font-size: 11px; color: #6b7280; background: transparent;")
                    vl = QLabel(str(val))
                    vl.setStyleSheet(
                        "font-size: 15px; font-weight: 800; color: #ffffff;"
                        " background: transparent;")
                    row.addWidget(rk)
                    row.addWidget(nm, 1)
                    row.addWidget(em)
                    row.addWidget(vl)
                    col.addLayout(row)
                cols.addLayout(col, 1)
            panel._body.addLayout(cols)
        except Exception as e:
            print("[hub] leaders failed: %s" % e)

    def _fill_form(self, team, gm=None):
        panel = self.panel_form
        self._clear_panel(panel)
        try:
            gm = gm or getattr(self._main, "game", None)
            recent = self._team_recent_results(gm, team, 10)
            if recent:
                streak_l = QLabel("STREAK   " + str(recent[-1]).upper())
            else:
                streak_l = QLabel("STREAK   \u2014")
            streak_l.setStyleSheet(
                "font-size: 12px; letter-spacing: 2px; color: #9aa3b2;"
                " background: transparent;")
            panel._body.addWidget(streak_l)
            if not recent:
                e = QLabel("No games yet")
                e.setStyleSheet(
                    "color: #6b7280; font-size: 12px; padding: 6px 0;"
                    " background: transparent;")
                panel._body.addWidget(e)
                return
            row = QHBoxLayout()
            row.setSpacing(6)
            for r in recent[-10:]:
                s = str(r).upper()
                if s.startswith("W"):
                    res, bg = "W", "#16a34a"
                elif s.startswith("L"):
                    res, bg = "L", "#dc2626"
                else:
                    res, bg = "OTL", "#b45309"
                cell = QLabel(res)
                cell.setAlignment(Qt.AlignCenter)
                cell.setStyleSheet(
                    "font-size: 13px; font-weight: 800; color: #ffffff;"
                    " background: %s; border-radius: 3px; padding: 6px 4px;" % bg)
                row.addWidget(cell, 1)
            panel._body.addLayout(row)
        except Exception as e:
            print("[hub] form failed: %s" % e)

    # ---------- Batch D panels (HTML hub parity) ----------
    def _hub_empty_label(self, text):
        e = QLabel(text)
        e.setStyleSheet(
            "color: #6b7280; font-size: 12px; padding: 6px 0;"
            " background: transparent;")
        return e

    def _hub_row(self, left_text, right_text, left_bold=False):
        row = QHBoxLayout()
        row.setSpacing(6)
        nm = QLabel(left_text)
        nm.setStyleSheet(
            "font-size: 12.5px; %s color: #f4f6fb; background: transparent;"
            % ("font-weight: 700;" if left_bold else ""))
        vl = QLabel(right_text)
        vl.setStyleSheet(
            "font-size: 12px; color: #9aa3b2; background: transparent;")
        vl.setAlignment(Qt.AlignRight)
        row.addWidget(nm, 1)
        row.addWidget(vl)
        return row

    def _fill_sched_panel(self, game, gm, team, team_name):
        panel = self.panel_sched
        self._clear_panel(panel)
        try:
            league = getattr(game, "league", None) or getattr(gm, "league", None)
            sched = getattr(league, "schedule", None) or []
            today = getattr(game, "current_date", None) or getattr(gm, "current_date", None)
            upcoming, results = [], []
            for g in sched:
                try:
                    if not self._sched_is_game(g):
                        continue
                    home, away = self._sched_teams(g)
                    if team_name and team_name not in (home, away):
                        continue
                    gd = self._sched_date(g)
                    ds = gd.strftime("%a %b %d") if hasattr(gd, "strftime") else str(gd or "")
                    opp = away if home == team_name else home
                    opp_abbr = self._team_abbr(opp)
                    where = "vs" if home == team_name else "at"
                    hs, aws = self._sched_scores(g)
                    if hs is None:
                        upcoming.append((gd, ds, where, opp_abbr))
                    else:
                        mine = hs if home == team_name else aws
                        theirs = aws if home == team_name else hs
                        wl = "W" if mine > theirs else ("OTL" if abs(mine - theirs) == 1 else "L")
                        results.append((gd, ds, where, opp_abbr, "%d-%d" % (mine, theirs), wl))
                except Exception:
                    continue
            upcoming.sort(key=lambda r: (r[0] is None, r[0]))
            results.sort(key=lambda r: (r[0] is None, r[0]), reverse=True)

            scope = QComboBox()
            scope.addItems(["Upcoming", "Results"])
            scope.setStyleSheet(
                "font-size: 11px; color: #c7d0e0; background: #131a26;"
                " border: 1px solid rgba(255,255,255,0.12); border-radius: 4px;"
                " padding: 3px 6px;")
            body_rows = QVBoxLayout()
            body_rows.setSpacing(6)

            def paint():
                while body_rows.count():
                    it = body_rows.takeAt(0)
                    w = it.widget()
                    if w:
                        w.deleteLater()
                    else:
                        sub = it.layout()
                        if sub:
                            while sub.count():
                                si = sub.takeAt(0)
                                sw = si.widget()
                                if sw:
                                    sw.deleteLater()
                rows = upcoming[:5] if scope.currentText() == "Upcoming" else results[:5]
                if not rows:
                    body_rows.addWidget(self._hub_empty_label("\u2014"))
                    return
                for r in rows:
                    if len(r) == 4:
                        _, ds, where, opp_abbr = r
                        row = QHBoxLayout()
                        row.setSpacing(6)
                        d = QLabel(ds)
                        d.setStyleSheet("font-size: 12px; color: #9aa3b2; background: transparent;")
                        o = QLabel("%s %s" % (where, opp_abbr))
                        o.setStyleSheet("font-size: 12.5px; color: #f4f6fb; background: transparent;")
                        row.addWidget(d)
                        row.addWidget(o, 1)
                        body_rows.addLayout(row)
                    else:
                        _, ds, where, opp_abbr, score, wl = r
                        row = QHBoxLayout()
                        row.setSpacing(6)
                        d = QLabel(ds)
                        d.setStyleSheet("font-size: 12px; color: #9aa3b2; background: transparent;")
                        o = QLabel("%s %s" % (where, opp_abbr))
                        o.setStyleSheet("font-size: 12.5px; color: #f4f6fb; background: transparent;")
                        res = QLabel(wl)
                        bg = "#16a34a" if wl == "W" else ("#b45309" if wl == "OTL" else "#dc2626")
                        res.setStyleSheet(
                            "font-size: 11px; font-weight: 800; color: #ffffff;"
                            " background: %s; border-radius: 3px; padding: 2px 6px;" % bg)
                        sc = QLabel(score)
                        sc.setStyleSheet("font-size: 12px; color: #9aa3b2; background: transparent;")
                        row.addWidget(d)
                        row.addWidget(o, 1)
                        row.addWidget(res)
                        row.addWidget(sc)
                        body_rows.addLayout(row)

            scope.currentTextChanged.connect(lambda _t: paint())
            panel._body.addWidget(scope)
            panel._body.addLayout(body_rows)
            paint()
        except Exception as e:
            print("[hub] schedule panel failed: %s" % e)

    def _fill_injuries(self, team):
        panel = self.panel_inj
        self._clear_panel(panel)
        try:
            injured = []
            for p in (getattr(team, "roster", None) or []):
                try:
                    inj = getattr(p, "injury", None)
                    name = getattr(p, "full_name", "?") or "?"
                    if inj:
                        desc = (getattr(inj, "description", None)
                                or getattr(inj, "injury_type", "Injured"))
                        games = getattr(inj, "games_remaining",
                                        getattr(inj, "days_remaining", "?"))
                        injured.append((name, "%s \u00b7 %s out" % (desc, games)))
                    elif getattr(p, "is_injured", False):
                        injured.append((name, "Injured \u00b7 ? out"))
                except Exception:
                    continue
            if not injured:
                panel._body.addWidget(self._hub_empty_label("No injuries"))
                return
            for name, desc in injured[:5]:
                panel._body.addLayout(self._hub_row(name, desc))
        except Exception as e:
            print("[hub] injuries panel failed: %s" % e)

    def _fill_morale_panel(self, team):
        panel = self.panel_morale
        self._clear_panel(panel)
        try:
            roster = getattr(team, "roster", None) or []
            mors = [float(getattr(p, "morale", 70) or 70) for p in roster]
            if not mors:
                panel._body.addWidget(self._hub_empty_label("\u2014"))
                return
            avg = sum(mors) / len(mors)
            label = self._morale_label(avg)
            head = QLabel("AVG   %.1f \u00b7 %s" % (avg, label))
            head.setStyleSheet(
                "font-size: 12px; letter-spacing: 2px; color: #9aa3b2;"
                " background: transparent;")
            panel._body.addWidget(head)
            bands = {}
            for m in mors:
                b = self._morale_label(m)
                bands[b] = bands.get(b, 0) + 1
            for b in ("Superb", "Good", "Okay", "Poor", "Abysmal"):
                if bands.get(b):
                    panel._body.addLayout(
                        self._hub_row(b, "%d players" % bands[b]))
        except Exception as e:
            print("[hub] morale panel failed: %s" % e)

    @staticmethod
    def _morale_label(m):
        try:
            from career import morale_label as _ml
            return _ml(int(m))
        except Exception:
            pass
        m = int(m)
        if m >= 85:
            return "Superb"
        if m >= 65:
            return "Good"
        if m >= 45:
            return "Okay"
        if m >= 25:
            return "Poor"
        return "Abysmal"

    def _fill_prospects(self, team):
        panel = self.panel_prosp
        self._clear_panel(panel)
        try:
            pool = (list(getattr(team, "prospects", None) or [])
                    + list(getattr(team, "ahl_roster", None) or []))
            ladder = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]

            def _pot_rank(p):
                g = str(getattr(p, "potential_grade", "C") or "C").strip().upper()
                return ladder.index(g) if g in ladder else 4

            scored = []
            for p in pool:
                try:
                    ovr = float(p.overall_rating()) if hasattr(p, "overall_rating") else 0.0
                    scored.append((_pot_rank(p), ovr, p))
                except Exception:
                    continue
            scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
            if not scored:
                panel._body.addWidget(self._hub_empty_label("No prospects tracked"))
                return
            try:
                from attribute_composites import talent_tier_for_player as _ttfp
            except Exception:
                _ttfp = None
            for _, _, p in scored[:5]:
                name = getattr(p, "full_name", "?") or "?"
                pos = getattr(p, "primary_position", "?") or "?"
                age = getattr(p, "age", 0) or 0
                pot = getattr(p, "potential_grade", "?") or "?"
                left = "%s  %s \u00b7 %s" % (name, pos, age)
                right = pot
                if _ttfp:
                    try:
                        tier = _ttfp(p)
                        if tier:
                            right = "%s \u00b7 %s" % (pot, tier)
                    except Exception:
                        pass
                panel._body.addLayout(self._hub_row(left, right))
        except Exception as e:
            print("[hub] prospects panel failed: %s" % e)

    def _fill_milestones(self, team):
        panel = self.panel_mile
        self._clear_panel(panel)
        try:
            roster = getattr(team, "roster", None) or []
            hits = []
            for p in roster:
                try:
                    pos = str(getattr(p, "primary_position", "") or "")
                    if "GOALIE" in pos.upper():
                        continue
                    name = getattr(p, "full_name", "?") or "?"
                    pts = (int(getattr(p, "goals", 0) or 0)
                           + int(getattr(p, "assists", 0) or 0))
                    for m in (25, 50, 75, 100):
                        if pts < m <= pts + 8:
                            hits.append((m - pts, name, "%d PTS from %d" % (m - pts, m)))
                    cg = int(getattr(p, "career_games", 0) or 0)
                    for m in (500, 1000, 1500):
                        if cg < m <= cg + 10:
                            hits.append((m - cg, name, "%d GP from %d career" % (m - cg, m)))
                except Exception:
                    continue
            hits.sort(key=lambda h: h[0])
            if not hits:
                panel._body.addWidget(self._hub_empty_label("No milestones near"))
                return
            for _, name, text in hits[:6]:
                panel._body.addLayout(self._hub_row(name, "\U0001f3c6 " + text))
        except Exception as e:
            print("[hub] milestones panel failed: %s" % e)

    def _fill_iconic(self, team):
        panel = self.panel_iconic
        self._clear_panel(panel)
        try:
            entries = [e for e in (getattr(team, "iconic_games", None) or [])
                       if isinstance(e, dict)]
            entries.sort(key=lambda e: (not bool(e.get("starred")),
                                        str(e.get("date", ""))))
            if not entries:
                panel._body.addWidget(self._hub_empty_label("No iconic games yet"))
                return
            for e in entries[:6]:
                star = "\u2b50 " if e.get("starred") else ""
                head = star + str(e.get("headline", "Unforgettable night") or "")
                sub = str(e.get("date", "") or "")
                if e.get("score"):
                    sub = (sub + " \u00b7 " + str(e["score"])).strip(" \u00b7")
                panel._body.addLayout(self._hub_row(head, sub))
            more = len(entries) - 6
            if more > 0:
                panel._body.addWidget(
                    self._hub_empty_label("+%d more in League History" % more))
        except Exception as e:
            print("[hub] iconic panel failed: %s" % e)

    def _fill_inbox_recent(self, team):
        panel = self.panel_inbox
        self._clear_panel(panel)
        try:
            inbox = getattr(team, "inbox", None)
            msgs = list(getattr(inbox, "messages", None) or []) if inbox else []
            if not msgs:
                panel._body.addWidget(self._hub_empty_label("Inbox is quiet"))
                return
            unread = 0
            for m in msgs[:5]:
                try:
                    subject = getattr(m, "subject", "") or ""
                    sender = getattr(m, "sender", "") or ""
                    is_read = getattr(m, "read", True)
                    if isinstance(m, dict):
                        subject = m.get("subject", "")
                        sender = m.get("sender", "")
                        is_read = m.get("read", True)
                    if not is_read:
                        unread += 1
                    prefix = ""
                    if getattr(m, "requires_response", False):
                        prefix += "\U0001f534 "
                    if getattr(m, "is_urgent", False):
                        prefix += "\U0001f7e1 "
                    left = prefix + subject
                    row = self._hub_row(left, sender, left_bold=not is_read)
                    panel._body.addLayout(row)
                except Exception:
                    continue
            if unread:
                panel._body.addWidget(
                    self._hub_empty_label("%d unread" % unread))
        except Exception as e:
            print("[hub] inbox-recent panel failed: %s" % e)

    def _fill_ticker(self, game, gm):
        items = []
        try:
            news = getattr(game, "news_log", None) or getattr(gm, "news_log", None) or []
            seq = news if isinstance(news, list) else []
            for n in seq[-30:]:
                if isinstance(n, dict):
                    txt = n.get("story") or n.get("headline") or ""
                else:
                    txt = getattr(n, "headline", None) or getattr(n, "story", None) or str(n)
                txt = str(txt).strip()
                if txt and len(txt) > 8:
                    items.append(txt)
        except Exception:
            pass
        if not items:
            try:
                league = getattr(game, "league", None) or getattr(gm, "league", None)
                sched = getattr(league, "schedule", None) or []
                today = getattr(game, "current_date", None) or getattr(gm, "current_date", None)
                played = []
                for g in sched:
                    try:
                        if not self._sched_is_game(g):
                            continue
                        gd = self._sched_date(g)
                        if gd is None:
                            continue
                        # date-driven: a game is played once its date has passed
                        if self._game_val(g, "played", default=None) is not None:
                            if not self._sched_played(g):
                                continue
                        elif today is not None and gd > today:
                            continue
                        played.append((gd, g))
                    except Exception:
                        continue
                played.sort(key=lambda x: x[0])
                for _, g in played[-15:]:
                    home, away = self._sched_teams(g)
                    hs = self._game_val(g, "home_score", "home_goals", default=0)
                    aws = self._game_val(g, "away_score", "away_goals", default=0)
                    items.append("FINAL: %s %s - %s %s" % (away, aws, home, hs))
            except Exception:
                pass
        if not items:
            items = ["Welcome to Puck Dynasty"]
        self._ticker_items = items
        self._ticker_pos = 0
        self.ticker.setText(("   \u2022   ".join(items)).upper()[:400])


class MainWindow(QMainWindow):
    """Puck Dynasty native application window."""

    def __init__(self, game=None):
        super().__init__()
        self.game = game  # HockeyManagerGUI or game manager instance
        self.setWindowTitle("Puck Dynasty")
        self.setMinimumSize(1280, 800)

        # Top bar
        self.topbar = TopBar(self)
        self.addToolBar(Qt.TopToolBarArea, self._wrap_topbar())

        # Central stacked widget for screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Hub page
        self.hub = HubPage(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.hub)
        scroll.setFrameShape(QFrame.NoFrame)
        self.stack.addWidget(scroll)

        # Screen registry: name -> widget
        self._screens = {"hub": scroll}
        self._screen_classes = {}
        self._register_all_screens()

        # Apply theme
        self.setStyleSheet(THEME_QSS)

        # Keyboard shortcuts (Space, Ctrl+S, Esc, ?, 1-9)
        self._setup_keyboard_shortcuts()

    def _register_all_screens(self):
        """Register all ported screens for lazy instantiation."""
        # Map of screen name -> (module, class name)
        _registry = {
            "roster": ("native_ui.screens.roster", "RosterScreen"),
            "player": ("native_ui.screens.player_profile", "PlayerProfileScreen"),
            "lines": ("native_ui.screens.lines", "LinesScreen"),
            "setup": ("native_ui.screens.setup", "SetupScreen"),
            "multiplayer": ("native_ui.screens.multiplayer", "MultiplayerScreen"),
            "practice_center": ("native_ui.screens.practice_center", "PracticeCenterScreen"),
            "camp": ("native_ui.screens.camp", "CampScreen"),
            "captains": ("native_ui.screens.captains", "CaptainsScreen"),
            "staff": ("native_ui.screens.staff", "StaffScreen"),
            "staff_detail": ("native_ui.screens.staff_detail", "StaffDetailScreen"),
            "contracts": ("native_ui.screens.contracts", "ContractsScreen"),
            "morale": ("native_ui.screens.morale", "MoraleScreen"),
            "development": ("native_ui.screens.development", "DevelopmentScreen"),
            "tactics": ("native_ui.screens.tactics", "TacticsScreen"),
            "season_goals": ("native_ui.screens.season_goals", "SeasonGoalsScreen"),
            "offseason_programs": ("native_ui.screens.offseason_programs", "OffseasonProgramsScreen"),
            "jersey_numbers": ("native_ui.screens.jersey_numbers", "JerseyNumbersScreen"),
            "gm_relationships": ("native_ui.screens.gm_relationships", "GmRelationshipsScreen"),
            "trades": ("native_ui.screens.trades", "TradesScreen"),
            "free_agents": ("native_ui.screens.free_agents", "FreeAgentsScreen"),
            "waivers": ("native_ui.screens.waivers", "WaiversScreen"),
            "offer_sheets": ("native_ui.screens.offer_sheets", "OfferSheetsScreen"),
            "trade_block": ("native_ui.screens.trade_block", "TradeBlockScreen"),
            "deadline": ("native_ui.screens.deadline", "DeadlineScreen"),
            "standings": ("native_ui.screens.standings", "StandingsScreen"),
            "stats": ("native_ui.screens.stats", "StatsScreen"),
            "schedule": ("native_ui.screens.schedule", "ScheduleScreen"),
            "playoffs": ("native_ui.screens.playoffs", "PlayoffsScreen"),
            "draft": ("native_ui.screens.draft", "DraftScreen"),
            "lottery": ("native_ui.screens.lottery", "LotteryScreen"),
            "history": ("native_ui.screens.history", "HistoryScreen"),
            "season_summary": ("native_ui.screens.season_summary", "SeasonSummaryScreen"),
            "ahl": ("native_ui.screens.ahl", "AhIScreen"),
            "calendar": ("native_ui.screens.calendar", "CalendarScreen"),
            "team": ("native_ui.screens.team", "TeamScreen"),
            "inbox": ("native_ui.screens.inbox", "InboxScreen"),
            "news": ("native_ui.screens.news", "NewsScreen"),
            "finances": ("native_ui.screens.finances", "FinancesScreen"),
            "settings": ("native_ui.screens.settings", "SettingsScreen"),
            "save": ("native_ui.screens.save", "SaveScreen"),
            "watch": ("native_ui.screens.watch", "WatchScreen"),
            "replay": ("native_ui.screens.replay", "ReplayScreen"),
            "compare": ("native_ui.screens.compare", "CompareScreen"),
            "coach_checkin": ("native_ui.screens.coach_checkin", "CoachCheckinScreen"),
            "manager": ("native_ui.screens.manager", "ManagerScreen"),
            "fa_frenzy": ("native_ui.screens.fa_frenzy", "FaFrenzyScreen"),
            "fantasy_draft": ("native_ui.screens.fantasy_draft", "FantasyDraftScreen"),
            "scouting": ("native_ui.screens.scouting", "ScoutingScreen"),
            "contract_negotiation": ("native_ui.screens.contract_negotiation", "ContractNegotiationScreen"),
            "dressing_room": ("native_ui.screens.dressing_room", "DressingRoomScreen"),
            "media_center": ("native_ui.screens.media_center", "MediaCenterScreen"),
            "records": ("native_ui.screens.records", "RecordsScreen"),
            "shortlist": ("native_ui.screens.shortlist", "ShortlistScreen"),
            "shot_chart_viewer": ("native_ui.screens.shot_chart_viewer", "ShotChartViewerScreen"),
            "analytics": ("native_ui.screens.analytics", "AnalyticsScreen"),
        }
        # Systems pages
        for sys_name in ["clutch", "circumstance", "discipline",
                         "rivalry", "deployment", "condition"]:
            _registry[f"systems_{sys_name}"] = (
                f"native_ui.screens.systems_{sys_name}",
                f"Systems{sys_name.title()}Screen")

        for name, (mod_path, cls_name) in _registry.items():
            try:
                mod = __import__(mod_path, fromlist=[cls_name])
                cls = getattr(mod, cls_name)
                self._screen_classes[name] = cls
            except Exception as e:
                _nav_error(f"[nav] failed to register {name}: {e}")

    def register_screen(self, name, screen_class):
        """Register a screen class for lazy instantiation."""
        self._screen_classes[name] = screen_class

    def show_screen(self, name):
        """Navigate to a registered screen, instantiating on first use."""
        if name in self._screens:
            self.stack.setCurrentWidget(self._screens[name])
            # Refresh the screen if it has a refresh method
            widget = self._screens[name]
            # Unwrap scroll area if present
            inner = widget.widget() if hasattr(widget, "widget") else widget
            if hasattr(inner, "refresh"):
                try:
                    inner.refresh()
                except Exception as e:
                    _nav_error(f"[nav] refresh {name} failed: {e}")
            return
        # Lazy instantiate
        cls = self._screen_classes.get(name)
        if cls:
            try:
                screen = cls(self.game, self)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(screen)
                scroll.setFrameShape(QFrame.NoFrame)
                self._screens[name] = scroll
                self.stack.addWidget(scroll)
                self.stack.setCurrentWidget(scroll)
                if hasattr(screen, "refresh"):
                    screen.refresh()
            except Exception as e:
                _nav_error(f"[nav] failed to create screen {name}: {e}")
        else:
            _nav_error(f"[nav] unknown screen: {name}")

    def show_player(self, player):
        """Open a player profile. Used by roster double-click, context menus."""
        self.show_screen("player")
        # Get the inner screen and set the player
        scroll = self._screens.get("player")
        if scroll and hasattr(scroll, "widget"):
            inner = scroll.widget()
            if hasattr(inner, "set_player"):
                inner.set_player(player)

    def open_player(self, player):
        """Alias for show_player (some screens call this)."""
        self.show_player(player)

    def open_team(self, team_name):
        """Open a team overview page."""
        self.show_screen("team")
        scroll = self._screens.get("team")
        if scroll and hasattr(scroll, "widget"):
            inner = scroll.widget()
            if hasattr(inner, "set_team"):
                inner.set_team(team_name)

    def _wrap_topbar(self):
        from PySide6.QtWidgets import QToolBar
        tb = QToolBar()
        tb.setMovable(False)
        tb.addWidget(self.topbar)
        tb.setStyleSheet("QToolBar { border: none; padding: 0; margin: 0; }")
        return tb

    # --- Navigation ---
    def show_section(self, name):
        self.topbar.set_active(name)
        # Map section names to screens (handle uppercase nav button names)
        section_map = {
            "CLUB": "team",
            "PERSONNEL": "staff",
            "LEAGUE": "standings",
            "TRANSACTIONS": "trades",
            "FINANCES": "finances",
            "SYSTEMS": "systems_clutch",
            # Lowercase aliases
            "hub": "hub",
            "roster": "roster",
            "lines": "lines",
            "team": "team",
            "league": "standings",
            "transactions": "trades",
            "inbox": "inbox",
        }
        screen = section_map.get(name, section_map.get(name.lower(), "hub"))
        self.show_screen(screen)

    def show_inbox(self):
        self.show_screen("inbox")

    def save_game(self):
        try:
            if self.game and hasattr(self.game, "save_manager"):
                self.game.save_manager.save_game()
        except Exception as e:
            print(f"[native] save failed: {e}")

    def on_tile_click(self, title):
        # Map hub tile titles to screens (titles are uppercase)
        tile_map = {
            "RECORD": "standings",
            "DIVISION": "standings",
            "STREAK": "schedule",
            "CAP SPACE": "finances",
            "NEXT GAME": "schedule",
            "TOP SCORER": "stats",
            "INJURIES": "roster",
            "MORALE": "morale",
        }
        screen = tile_map.get(title, "hub")
        self.show_screen(screen)

    def on_continue(self):
        """Direct Python call -- no HTTP round-trip."""
        if not self.game:
            return
        try:
            label, blockers = self.game.get_continue_state()
            if blockers:
                self.show_blockers(blockers)
            else:
                # Advance the day
                if hasattr(self.game, "simulate_day"):
                    self.game.simulate_day()
                # Refresh current screen
                current = self.stack.currentWidget() if hasattr(self, "stack") else None
                if current and hasattr(current, "refresh"):
                    current.refresh()
                elif hasattr(self, "hub"):
                    self.hub.refresh(self.game)
        except Exception as e:
            print(f"[native] continue failed: {e}")

    def show_blockers(self, blockers):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame
        dlg = QDialog(self)
        dlg.setWindowTitle("Can't advance yet")
        dlg.setMinimumWidth(600)
        layout = QVBoxLayout(dlg)
        title = QLabel(f"{len(blockers)} things need your attention")
        title.setObjectName("dialog-title")
        layout.addWidget(title)
        for b in blockers:
            card = QFrame()
            card.setObjectName("blocker-card")
            cl = QVBoxLayout(card)
            t = QLabel(b.get("title", "Blocker"))
            t.setObjectName("blocker-title")
            d = QLabel(b.get("detail", ""))
            d.setObjectName("blocker-detail")
            d.setWordWrap(True)
            cl.addWidget(t)
            cl.addWidget(d)
            # Render action button if blocker provides one
            # New format: action_id + action_label (UI-agnostic)
            # Old format: action tuple (label, callable) - deprecated
            action_id = b.get("action_id")
            action_label = b.get("action_label", "Open")
            if action_id:
                try:
                    btn = QPushButton(action_label)
                    btn.setObjectName("primary-btn")
                    # Map action IDs to native screens
                    native_target = {
                        "fantasy_draft": "fantasy_draft",
                        "entry_draft": "draft",
                        "captaincy": "captains",
                    }.get(action_id)
                    if native_target:
                        btn.clicked.connect(
                            lambda _=False, n=native_target: (
                                dlg.accept(), self.show_screen(n)))
                    cl.addWidget(btn)
                except Exception:
                    pass
            else:
                # Fallback: old tuple format
                action = b.get("action")
                if action:
                    try:
                        label, callback = action
                        btn = QPushButton(label)
                        btn.setObjectName("primary-btn")
                        blocker_id = b.get("id", "")
                        native_target = {
                            "fantasy_draft": "fantasy_draft",
                            "entry_draft": "draft",
                            "captaincy_choice": "captains",
                            "captaincy": "captains",
                        }.get(blocker_id)
                        if native_target:
                            btn.clicked.connect(
                                lambda _=False, n=native_target: (
                                    dlg.accept(), self.show_screen(n)))
                        cl.addWidget(btn)
                    except Exception:
                        pass
                # Render auto_action button if present (e.g. Auto-pick Captains)
                auto_action = b.get("auto_action")
                if auto_action:
                    try:
                        auto_label, auto_cb = auto_action
                        # For captaincy auto-pick, we can't call the Tk closure.
                        # Instead, trigger the native captains screen which has
                        # its own auto-pick, or run the logic directly.
                        auto_btn = QPushButton(auto_label)
                        auto_btn.setObjectName("primary-btn")
                        bidder = b.get("id", "")
                        if bidder == "captaincy_choice":
                            # Navigate to captains screen; user can auto-pick there
                            auto_btn.clicked.connect(
                                lambda _=False: (
                                    dlg.accept(),
                                    self.show_screen("captains")))
                        else:
                            # Generic: close dialog and try the callback
                            # (may be Tk-bound; guarded)
                            def _run_auto(cb=auto_cb):
                                dlg.accept()
                                try:
                                    cb()
                                except Exception:
                                    pass
                            auto_btn.clicked.connect(_run_auto)
                        cl.addWidget(auto_btn)
                    except Exception:
                        pass
            layout.addWidget(card)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        # Automation bypass: modal exec() hard-blocks scripted UI drivers
        # (visual test bots). PUCK_DYNASTY_NO_MODAL=1 logs the blockers and
        # skips the dialog instead of blocking forever. Real users unaffected.
        if os.environ.get("PUCK_DYNASTY_NO_MODAL"):
            print("[blockers] (%d, auto-skipped modal): %s" % (
                len(blockers),
                "; ".join(b.get("title", "?") for b in blockers)))
        else:
            dlg.exec()
        # If the club can't dress 18+2, offer the AHL recall picker.
        # maybe_open_recall_picker is a no-op when there's no shortfall.
        try:
            from .dialogs.recall_picker import maybe_open_recall_picker
            maybe_open_recall_picker(self.game, parent=self)
        except Exception as e:
            print(f"[native] recall picker failed: {e}")

    def refresh(self):
        if self.game:
            self.hub.refresh(self.game)
        else:
            # No game loaded — show the setup wizard
            self.show_screen("setup")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------
    _TEXT_INPUT_CLASSES = (
        "QLineEdit", "QTextEdit", "QPlainTextEdit", "QComboBox",
        "QSpinBox", "QDoubleSpinBox", "QDateEdit", "QTimeEdit",
        "QDateTimeEdit",
    )

    def _typing_in_field(self):
        """True when focus is in a text input (shortcuts stay quiet)."""
        try:
            from PySide6.QtWidgets import QApplication
            w = QApplication.focusWidget()
            if w is None:
                return False
            return w.__class__.__name__ in self._TEXT_INPUT_CLASSES
        except Exception:
            return False

    def _modal_dialog_open(self):
        """True when a modal dialog is open (shortcuts stay quiet)."""
        try:
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if w.isModal() and w.isVisible() and w is not self:
                    return True
            return False
        except Exception:
            return False

    def _setup_keyboard_shortcuts(self):
        """Wire up app-wide keyboard shortcuts via QShortcut."""
        if getattr(self, "_shortcuts_bound", False):
            return
        self._shortcuts_bound = True

        def _bind(key_seq, handler):
            sc = QShortcut(QKeySequence(key_seq), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(handler)
            return sc

        # Space: Continue (advance day) — not while typing or in a dialog
        _bind("Space", self._shortcut_continue)
        # Ctrl+S: Quick save
        _bind("Ctrl+S", self._shortcut_save)
        # Esc: Back to hub
        _bind("Escape", self._shortcut_escape)
        # ?: Shortcuts cheat-sheet
        _bind("?", self._shortcut_cheat_sheet)
        _bind("Shift+?", self._shortcut_cheat_sheet)

        # 1-9: Quick navigation
        nav_targets = {
            "1": "hub",
            "2": "roster",
            "3": "lines",
            "4": "team",
            "5": "inbox",
            "6": "standings",
            "7": "stats",
            "8": "trades",
            "9": "schedule",
        }
        for key, screen in nav_targets.items():
            _bind(key, lambda s=screen: self._shortcut_navigate(s))

    def _shortcut_continue(self):
        if self._typing_in_field() or self._modal_dialog_open():
            return
        self.on_continue()

    def _shortcut_save(self):
        self.save_game()

    def _shortcut_escape(self):
        if self._modal_dialog_open():
            return  # Let the dialog handle Esc itself
        self.show_screen("hub")

    def _shortcut_cheat_sheet(self):
        if self._typing_in_field() or self._modal_dialog_open():
            return
        try:
            from .dialogs.shortcuts import show_shortcuts
            show_shortcuts(self)
        except Exception as e:
            print(f"[native] shortcuts dialog failed: {e}")

    def _shortcut_navigate(self, screen):
        if self._typing_in_field() or self._modal_dialog_open():
            return
        self.show_screen(screen)

    def show_shortcuts_dialog(self):
        """Public entry point for the shortcuts cheat-sheet."""
        self._shortcut_cheat_sheet()


def _nav_error(msg):
    """Surface navigation/registration failures visibly.

    The Windows build runs with console=False, so print() goes nowhere.
    Write to a log file next to the executable AND pop a message box for
    the critical setup path.
    """
    try:
        import os
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                                "puck_dynasty_errors.log")
        with open(log_path, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"{datetime.datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass
    print(msg)


def run(game=None):
    """Launch the native Puck Dynasty application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Puck Dynasty")
    app.setOrganizationName("Puck Dynasty")
    window = MainWindow(game=game)
    window.showMaximized()
    window.refresh()
    # Show setup wizard if no game OR game has no career started yet
    # (fresh GameManager from launcher has user_team=None -- V-A1 fix)
    if game is None or getattr(game, "user_team", None) is None:
        try:
            window.show_screen("setup")
        except Exception as e:
            _nav_error(f"[nav] setup wizard failed on launch: {e}")
        # Verify the setup screen actually became visible; if the screen
        # module failed to register (e.g. missing from the bundle), the
        # user would otherwise be stranded on an empty hub with no error.
        cur = window.stack.currentWidget()
        is_setup = cur is window._screens.get("setup")
        if not is_setup:
            from PySide6.QtWidgets import QMessageBox
            detail = "registered screens: " + ", ".join(
                sorted(window._screen_classes.keys())[:8]) + "..."
            _nav_error(f"[nav] setup screen not shown after launch. {detail}")
            QMessageBox.critical(
                window, "Setup unavailable",
                "The new-career setup wizard could not be loaded.\n\n"
                "Please report this and attach puck_dynasty_errors.log "
                "from the install folder.")
    return app.exec()
