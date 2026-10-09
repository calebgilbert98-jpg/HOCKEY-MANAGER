"""Puck Dynasty native main window (PySide6).

Steam-style native application shell. Hosts the hub dashboard and all
game screens as Qt widgets. No browser, no HTTP -- direct Python calls
into the game logic.
"""
import sys
import os
import re
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFrame, QGridLayout,
    QSizePolicy, QComboBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QShortcut, QKeySequence

from .theme import THEME_QSS
from native_ui.dialogs import modal as _modal


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

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(30, 12, 30, 0)
        self._outer.setSpacing(0)


        self._build_header()
        self._build_hero()
        self._build_tiles()
        self._build_strip()
        self._build_panels()
        self._build_ticker()
        self._build_footer()

    def _build_header(self):
        """Build the franchise header (team name, pills, record)."""
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
        self._outer.addLayout(fhead)

        # thin rule
        rule = QFrame()
        rule.setObjectName("hub-rule")
        rule.setFixedHeight(1)
        self._outer.addWidget(rule)
        self._outer.addSpacing(10)


    def _build_hero(self):
        """Build the CONTINUE SEASON hero banner."""
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
        # auto-advance status note (mirrors web th-auto-note)
        self.auto_note = QLabel("")
        self.auto_note.setObjectName("hub-auto-note")
        hero_foot.addWidget(self.auto_note)
        hero_foot.addStretch()
        hero_l.addLayout(hero_foot)
        self._outer.addWidget(self.hero)
        self._outer.addSpacing(12)


    def _build_tiles(self):
        """Build primary and secondary navigation tiles."""
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
        self._outer.addLayout(tile_grid)
        self._outer.addSpacing(14)

        # ---- MORE label ----
        more = QLabel("MORE")
        more.setObjectName("hub-more-label")
        self._outer.addWidget(more)
        self._outer.addSpacing(8)

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
        # ---- secondary tiles row 2: mainline feature ports ----
        secondary2 = [
            ("practice", "PRACTICE", "\U0001f3d2", "Drills & coach runs", "practice_center"),
            ("goals", "SEASON GOALS", "\U0001f3af", "Player targets", "season_goals"),
            ("offseason", "OFFSEASON", "\u2600", "Summer programs", "offseason_programs"),
            ("jerseys", "JERSEYS", "\U0001f455", "Jersey numbers", "jersey_numbers"),
            ("gmrels", "GM RELATIONS", "\U0001f91d", "GM relationships", "gm_relationships"),
            ("gmopts", "GM OPTIONS", "\u2699", "Front-office tools", "gm_options"),
        ]
        for i, (key, label, icon, sub, screen) in enumerate(secondary2):
            tile = self._make_nav_tile(label, icon, screen, big=False,
                                       sub=sub)
            more_grid.addWidget(tile, 1, i)
            self._nav_tiles[key] = tile
        # 6 tiles fill the 6-column grid (matches HTML hub layout)
        self._outer.addLayout(more_grid)
        self._outer.addSpacing(12)


    def _build_strip(self):
        """Build the 8-block stat strip."""
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
        self._outer.addLayout(strip)
        self._outer.addSpacing(12)


    def _build_panels(self):
        """Build the panels grid."""
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
        self.panel_inj = self._make_panel("INJURIES", click_screen="morale")
        panels.addWidget(self.panel_inj, 1, 1)
        self.panel_morale = self._make_panel("MORALE", click_screen="morale")
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
        self._outer.addLayout(panels)

        self._outer.addStretch()


    def _build_ticker(self):
        """Build the scrolling ticker."""
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
        self._outer.addLayout(tick_wrap)


    def _build_footer(self):
        """Build the footer hints bar."""
        # ---- footer hints bar (mirrors web footer.hints) ----
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 6, 0, 8)
        foot.setSpacing(18)
        hint1 = QLabel("<b>Click</b> a tile to open")
        hint1.setObjectName("hub-hint")
        hint1.setTextFormat(Qt.RichText)
        foot.addWidget(hint1)
        hint2 = QLabel("<b>Esc</b> back to hub")
        hint2.setObjectName("hub-hint")
        hint2.setTextFormat(Qt.RichText)
        foot.addWidget(hint2)
        foot.addStretch()
        self.exit_btn = QPushButton("\u23fb Exit")
        self.exit_btn.setObjectName("hub-exit-btn")
        self.exit_btn.setToolTip("Save and quit Puck Dynasty")
        self.exit_btn.setCursor(Qt.PointingHandCursor)
        self.exit_btn.clicked.connect(self._on_hub_exit)
        foot.addWidget(self.exit_btn)
        self._outer.addLayout(foot)

        # loading overlay ("LOADING FRANCHISE…" — mirrors web spinner)
        self._loading = QLabel("\u27f3 LOADING FRANCHISE\u2026")
        self._loading.setObjectName("hub-loading")
        self._loading.setAlignment(Qt.AlignCenter)
        self._loading.hide()
        # overlay is positioned over the page on refresh
        self._loading.setParent(self)

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
            #hub-auto-note {
                font-size: 12px; color: #9aa3b2; font-style: italic;
            }
            #hub-hint { font-size: 12px; color: #8b95ab; }
            #hub-hint b { color: #e5e9f0; font-weight: 700; }
            #hub-exit-btn {
                background: transparent; border: 1px solid #2a3550;
                border-radius: 6px; padding: 4px 14px;
                font-size: 12px; font-weight: 600; color: #c6cdd8;
            }
            #hub-exit-btn:hover { border-color: #F44336; color: #ffffff; }
            #hub-loading {
                background: rgba(6,10,19,0.82);
                font-size: 18px; font-weight: 800; letter-spacing: 3px;
                color: #3B82F6;
            }
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
    def _automation_state_text(self):
        """Current automation state for the hub status note."""
        try:
            auto = getattr(self._main, "_season_flow_automation", None)
            if auto is None:
                return ""
            active = bool(getattr(auto, "automation_active", False))
            mode = getattr(auto, "mode", None)
            mode_name = getattr(mode, "name", "") or str(mode or "")
            if active:
                return "Auto-advance on \u2014 %s" % (
                    mode_name.replace("_", " ").title() or "simming days")
            return ""
        except Exception:
            return ""

    def _refresh_auto_note(self):
        try:
            self.auto_note.setText(self._automation_state_text())
        except Exception:
            pass

    def _on_auto_advance(self):
        game = getattr(self._main, "game", None)
        if game and hasattr(game, "toggle_auto_advance"):
            try:
                game.toggle_auto_advance()
            except Exception as e:
                print("[hub] auto-advance failed: %s" % e)
        else:
            # No hub-level toggle on the game object: open the season-flow
            # screen, which owns the real automation controls.
            try:
                self._main.show_screen("season_flow")
                return
            except Exception as e:
                print("[hub] auto-advance not available: %s" % e)
        self._refresh_auto_note()

    def _on_hub_exit(self):
        """Save and quit (mirrors web footer Exit button)."""
        try:
            self._main.save_game()
        except Exception as e:
            print("[hub] save before exit failed: %s" % e)
        try:
            QApplication.instance().quit()
        except Exception:
            pass

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

    @staticmethod
    def _norm_date(d):
        """Normalize a date/datetime to a plain date for comparisons."""
        try:
            return d.date() if hasattr(d, "date") else d
        except Exception:
            return d

    def _match_result(self, g, game=None, gm=None):
        """Authoritative result record for a schedule entry.

        Canonical join: the sim engine never sets a 'played' flag (or
        scores) on raw league.schedule entries, so completion and scores
        come from joining gm.game_results by date + matchup -- the same
        join _game_played_state uses in native_ui/screens/schedule.py.
        Returns the result dict, or None when the game is unplayed.
        """
        try:
            results = (getattr(game, "game_results", None)
                       or getattr(gm, "game_results", None)) or []
            if not results:
                return None
            key = self._norm_date(self._sched_date(g))
            home, away = self._sched_teams(g)
            for r in results:
                try:
                    if not isinstance(r, dict):
                        continue
                    if self._norm_date(r.get("date")) != key:
                        continue
                    if self._team_name_of(r.get("home_team")) != home:
                        continue
                    if self._team_name_of(r.get("away_team")) != away:
                        continue
                    return r
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _sched_played(self, g, game=None, gm=None):
        """Check if a schedule entry is completed.

        Canonical check: join against the result record by date + matchup
        (_match_result). The raw entry's 'played' flag is never set by the
        sim engine, so reading the flag alone leaves completed games in
        "upcoming". Watched games count as complete too: watch.py marks
        the entry 'watched' and records its result in game_results.
        """
        if bool(self._game_val(g, "played", default=False)):
            return True
        if bool(self._game_val(g, "watched", default=False)):
            return True
        return self._match_result(g, game, gm) is not None

    def _sched_scores(self, g, game=None, gm=None):
        """Return (home_score, away_score, overtime, shootout).

        Canonical: join against the authoritative result record so
        day-simmed games appear in hub Results with the scores and OT
        metadata the engine recorded. Falls back to scores stamped on the
        entry itself (watched_home_score/watched_away_score from the watch
        screen; entry 'overtime'/'went_to_ot'/'shootout' flags) when no
        result record exists. (None, None, False, False) if unplayed.
        """
        def _to_int(v):
            try:
                return int(v)
            except Exception:
                return None
        r = self._match_result(g, game, gm)
        if r is not None:
            hs = _to_int(r.get("home_score"))
            aws = _to_int(r.get("away_score"))
            if hs is not None and aws is not None:
                return (hs, aws, bool(r.get("overtime")),
                        bool(r.get("shootout")))
        hs = _to_int(self._game_val(g, "home_score", "watched_home_score",
                                    default=None))
        aws = _to_int(self._game_val(g, "away_score", "watched_away_score",
                                     default=None))
        if hs is None or aws is None:
            return None, None, False, False
        ot = bool(self._game_val(g, "overtime", "went_to_ot", default=False))
        so = bool(self._game_val(g, "shootout", default=False))
        return hs, aws, ot, so

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
            # loading indicator (mirrors web "LOADING FRANCHISE…" spinner)
            try:
                self._loading.resize(self.size())
                self._loading.move(0, 0)
                self._loading.show()
                self._loading.raise_()
                QApplication.processEvents()
            except Exception:
                pass
            team_name = getattr(team, "team_name", "") or ""
            primary, deep, soft, wash, glow = self._team_colors(team_name)

            # Canonical standings data for the hub: the engine's
            # league.standings table (Points = 2*W + 1*OTL), built and
            # sorted exactly like the standings screen (_rich_team_rows +
            # _apply_standings_sort). Team attributes are only a fallback:
            # Team.update_record tracks OT losses in `ot_losses` (there is
            # no Team.otl), so the old `wins*2 + otl` math silently dropped
            # every OTL point from the hub record/rank/points.
            div_rows = []
            my_row = None
            try:
                from native_ui.screens.standings import (
                    _apply_standings_sort, _rich_team_rows)
                _all_rows, _ = _rich_team_rows(game)
                my_row = next((r for r in _all_rows
                               if r["name"] == team_name), None)
                _division = getattr(team, "division", "") or ""
                div_rows = _apply_standings_sort(
                    [r for r in _all_rows
                     if _division and r["division"] == _division],
                    "Points")
            except Exception:
                div_rows = []

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
            if my_row is not None:
                # Canonical record from the engine's standings table.
                wins, losses, otl = my_row["w"], my_row["l"], my_row["otl"]
            else:
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
            try:
                # Canonical division rank: div_rows are built and sorted by
                # the standings screen's own machinery (points desc, wins
                # desc, name asc). Points come straight from the engine's
                # standings table (2*W + 1*OTL) -- no local formula.
                rank = next((i + 1 for i, r in enumerate(div_rows)
                             if r["name"] == team_name), None)
                pts = my_row["pts"] if my_row is not None else wins * 2 + otl
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
                # league ranks under offense/defense (mirrors web sublabels)
                try:
                    _lg = getattr(game, "league", None) or getattr(gm, "league", None)
                    _teams = list(getattr(_lg, "teams", []) or []) if _lg else []

                    def _rank_suffix(n):
                        if 10 <= n % 100 <= 20:
                            return "th"
                        return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

                    if _teams:
                        # Rank by per-game rates (not raw totals) so teams
                        # with different games played are comparable.
                        def _gf_pg(t):
                            gp = getattr(t, "games_played", 0) or 0
                            gf = getattr(t, "goals_for", 0) or 0
                            return (gf / gp) if gp > 0 else 0.0

                        def _ga_pg(t):
                            gp = getattr(t, "games_played", 0) or 0
                            ga = getattr(t, "goals_against", 0) or 0
                            return (ga / gp) if gp > 0 else float("inf")

                        _by_off = sorted(_teams, key=_gf_pg, reverse=True)
                        _orank = next(
                            (i + 1 for i, t in enumerate(_by_off) if t is team),
                            None)
                        _by_def = sorted(_teams, key=_ga_pg)
                        _drank = next(
                            (i + 1 for i, t in enumerate(_by_def) if t is team),
                            None)
                        self._strip["gf"]._sub.setText(
                            "Offense: %d%s" % (_orank, _rank_suffix(_orank))
                            if _orank else "Offense")
                        self._strip["ga"]._sub.setText(
                            "Defense: %d%s" % (_drank, _rank_suffix(_drank))
                            if _drank else "Defense")
                    else:
                        self._strip["gf"]._sub.setText("Offense")
                        self._strip["ga"]._sub.setText("Defense")
                except Exception:
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

            # ---- next game (date-driven) ----
            # A game dated today is "next" only if it hasn't been played yet;
            # the engine sims games when their date == current_date.
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
                        if today is not None and gd < today:
                            continue
                        if (today is not None and gd == today
                                and self._sched_played(g, game, gm)):
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
            self._fill_standings(div_rows, team_name, division, primary, wash)
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
            try:
                self._loading.hide()
            except Exception:
                pass

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

    def _fill_standings(self, div_rows, team_name, division, primary, wash):
        """Division standings mini-panel from canonical standings rows.

        div_rows are the canonical row dicts from _rich_team_rows
        (native_ui/screens/standings.py), already sorted by the canonical
        sorter: points desc, wins desc, name asc. PTS/W/L/OTL come from the
        engine's standings table (Points = 2*W + 1*OTL).
        """
        panel = self.panel_stand
        panel._head.setText(
            ("%s DIVISION" % division.upper()) if division else "DIVISION STANDINGS")
        panel._head.setStyleSheet(
            "font-size: 13px; font-weight: 700; letter-spacing: 2px;"
            " color: #ffffff; background: #0e1626; padding: 8px 12px;"
            " border-bottom: 2px solid %s;" % primary)
        self._clear_panel(panel)
        if not div_rows:
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
        for i, r in enumerate(div_rows[:8]):
            w = r["w"]
            lv = r["l"]
            o = r["otl"]
            pts = r["pts"]
            tn = r["name"] or "?"
            abbr = _team_abbr(tn)
            me = (tn == team_name)
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
                    hs, aws, _ot, _so = self._sched_scores(g, game, gm)
                    if hs is None:
                        upcoming.append((gd, ds, where, opp_abbr))
                    else:
                        mine = hs if home == team_name else aws
                        theirs = aws if home == team_name else hs
                        # OTL is determined by the game going to overtime/
                        # shootout, not by score margin (a 1-goal regulation
                        # loss is a regulation loss). OT metadata comes from
                        # the authoritative result record, not the schedule
                        # entry.
                        went_ot = bool(_ot or _so)
                        if mine > theirs:
                            wl = "W"
                        elif went_ot:
                            wl = "OTL"
                        else:
                            wl = "L"
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
            mors = [
                float(70 if getattr(p, "morale", None) is None else p.morale)
                for p in roster
            ]
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
                    # Season totals are authoritative in p.stats; legacy
                    # attributes can be stale.
                    stats = getattr(p, "stats", None) or {}
                    pts = (int(stats.get("goals", 0) or 0)
                           + int(stats.get("assists", 0) or 0))
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
                    # Messages may be dicts or objects; check both.
                    requires_response = (
                        m.get("requires_response", False) if isinstance(m, dict)
                        else getattr(m, "requires_response", False)
                    )
                    is_urgent = (
                        m.get("is_urgent", False) if isinstance(m, dict)
                        else getattr(m, "is_urgent", False)
                    )
                    if requires_response:
                        prefix += "\U0001f534 "
                    if is_urgent:
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
                        # date-driven: a game dated after today isn't played; a
                        # game on/before today is played iff it has a recorded
                        # result. The raw entry's 'played' flag is dead (the
                        # sim never sets it), so the canonical results join
                        # decides -- unplayed past games show no fake FINAL.
                        if today is not None and gd > today:
                            continue
                        if not self._sched_played(g, game, gm):
                            continue
                        played.append((gd, g))
                    except Exception:
                        continue
                played.sort(key=lambda x: x[0])
                for _, g in played[-15:]:
                    home, away = self._sched_teams(g)
                    hs, aws, _ot, _so = self._sched_scores(g, game, gm)
                    hs = 0 if hs is None else hs
                    aws = 0 if aws is None else aws
                    items.append("FINAL: %s %s - %s %s" % (away, aws, home, hs))
            except Exception:
                pass
        if not items:
            items = ["Welcome to Puck Dynasty"]
        self._ticker_items = items
        self._ticker_pos = 0
        self.ticker.setText(("   \u2022   ".join(items)).upper()[:400])

        # hide loading indicator; refresh auto-advance status note
        try:
            self._loading.hide()
        except Exception:
            pass
        self._refresh_auto_note()

    def resizeEvent(self, event):
        try:
            if self._loading.isVisible():
                self._loading.resize(self.size())
        except Exception:
            pass
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    """Puck Dynasty native application window."""

    def __init__(self, game=None):
        super().__init__()
        self.game = game  # HockeyManagerGUI or game manager instance
        # Priority 1 bug #4: route GameManager's _ui_notify hook into this
        # window's dispatcher. Base GameManager._ui_notify is `pass`; without
        # this bind every notification call site silently drops.
        if game is not None:
            try:
                game._ui_notify = self._ui_notify
            except Exception as e:
                print(f"[native] _ui_notify wiring failed: {e}")
            # Priority 1 bug #5: GameManager.show_screen bridge. Several
            # GameManager methods call self.show_screen(...) -- a method
            # that only exists on the Tk GUI (main.py). In native the
            # GameManager has no such method, so blocker actions built on
            # it (the pending-item "Go to it" _jump at
            # game_manager.py:3499, the team-talk presenter at :15076)
            # died on AttributeError behind try/except. Route those calls
            # to this window's show_screen instead. Only installed when
            # the game object has no show_screen of its own (a
            # HockeyManagerGUI keeps its Tk version).
            if not hasattr(game, "show_screen"):
                try:
                    _window = self

                    def _gm_show_screen(name, *args, **kwargs):
                        try:
                            _window.show_screen(name)
                        except Exception as e:
                            print(f"[native] game->show_screen({name!r}) "
                                  f"failed: {e}")

                    game.show_screen = _gm_show_screen
                except Exception as e:
                    print(f"[native] show_screen bridge failed: {e}")
        self.setWindowTitle("Puck Dynasty")
        self.setMinimumSize(1280, 800)

        # Top bar
        self.topbar = TopBar(self)
        self.addToolBar(Qt.TopToolBarArea, self._wrap_topbar())

        # Menu-bar directory: every registered screen reachable by click
        self._setup_menu_nav()

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
        """Register all ported screens for lazy instantiation.

        Uses static imports (not dynamic __import__) so PyInstaller's
        static analysis can see and bundle all screen modules.
        """
        # Static imports — PyInstaller bundles these via AST analysis.
        # Imported inside the method (not at module top) to avoid
        # circular-import issues and keep startup fast.
        from native_ui.screens.ahl import AhIScreen
        from native_ui.screens.analytics import AnalyticsScreen
        from native_ui.screens.awards_ceremony import AwardsCeremonyScreen
        from native_ui.screens.calendar import CalendarScreen
        from native_ui.screens.camp import CampScreen
        from native_ui.screens.captains import CaptainsScreen
        from native_ui.screens.coach_checkin import CoachCheckinScreen
        from native_ui.screens.compare import CompareScreen
        from native_ui.screens.contract_negotiation import ContractNegotiationScreen
        from native_ui.screens.contracts import ContractsScreen
        from native_ui.screens.deadline import DeadlineScreen
        from native_ui.screens.development import DevelopmentScreen
        from native_ui.screens.draft import DraftScreen
        from native_ui.screens.draft_central import DraftCentralScreen
        from native_ui.screens.draft_recap import DraftRecapScreen
        from native_ui.screens.dressing_room import DressingRoomScreen
        from native_ui.screens.fa_frenzy import FaFrenzyScreen
        from native_ui.screens.fantasy_draft import FantasyDraftScreen
        from native_ui.screens.finances import FinancesScreen
        from native_ui.screens.free_agents import FreeAgentsScreen
        from native_ui.screens.gm_options import GMOptionsScreen
        from native_ui.screens.gm_relationships import GmRelationshipsScreen
        from native_ui.screens.history import HistoryScreen
        from native_ui.screens.inbox import InboxScreen
        from native_ui.screens.jersey_numbers import JerseyNumbersScreen
        from native_ui.screens.lines import LinesScreen
        from native_ui.screens.lottery import LotteryScreen
        from native_ui.screens.manager import ManagerScreen
        from native_ui.screens.media_center import MediaCenterScreen
        from native_ui.screens.morale import MoraleScreen
        from native_ui.screens.multiplayer import MultiplayerScreen
        from native_ui.screens.news import NewsScreen
        from native_ui.screens.offer_sheets import OfferSheetsScreen
        from native_ui.screens.offseason_programs import OffseasonProgramsScreen
        from native_ui.screens.player_profile import PlayerProfileScreen
        from native_ui.screens.playoffs import PlayoffsScreen
        from native_ui.screens.practice_center import PracticeCenterScreen
        from native_ui.screens.records import RecordsScreen
        from native_ui.screens.recall_picker import RecallPickerScreen
        from native_ui.screens.replay import ReplayScreen
        from native_ui.screens.roster import RosterScreen
        from native_ui.screens.save import SaveScreen
        from native_ui.screens.schedule import ScheduleScreen
        from native_ui.screens.scouting import ScoutingScreen
        from native_ui.screens.season_flow import SeasonFlowScreen
        from native_ui.screens.season_goals import SeasonGoalsScreen
        from native_ui.screens.season_meeting import SeasonMeetingScreen
        from native_ui.screens.season_summary import SeasonSummaryScreen
        from native_ui.screens.settings import SettingsScreen
        from native_ui.screens.setup import SetupScreen
        from native_ui.screens.shortlist import ShortlistScreen
        from native_ui.screens.shot_chart_viewer import ShotChartViewerScreen
        from native_ui.screens.staff import StaffScreen
        from native_ui.screens.staff_detail import StaffDetailScreen
        from native_ui.screens.standings import StandingsScreen
        from native_ui.screens.stats import StatsScreen
        from native_ui.screens.tactics import TacticsScreen
        from native_ui.screens.team import TeamScreen
        from native_ui.screens.team_analytics import TeamAnalyticsScreen
        from native_ui.screens.trade_block import TradeBlockScreen
        from native_ui.screens.trades import TradesScreen
        from native_ui.screens.waivers import WaiversScreen
        from native_ui.screens.watch import WatchScreen
        from native_ui.screens.systems_clutch import SystemsClutchScreen
        from native_ui.screens.systems_circumstance import SystemsCircumstanceScreen
        from native_ui.screens.systems_discipline import SystemsDisciplineScreen
        from native_ui.screens.systems_rivalry import SystemsRivalryScreen
        from native_ui.screens.systems_deployment import SystemsDeploymentScreen
        from native_ui.screens.systems_condition import SystemsConditionScreen

        # Map of screen name -> class (no dynamic import needed)
        _registry = {
            "roster": RosterScreen,
            "player": PlayerProfileScreen,
            "lines": LinesScreen,
            "setup": SetupScreen,
            "multiplayer": MultiplayerScreen,
            "practice_center": PracticeCenterScreen,
            "camp": CampScreen,
            "captains": CaptainsScreen,
            "staff": StaffScreen,
            "staff_detail": StaffDetailScreen,
            "contracts": ContractsScreen,
            "morale": MoraleScreen,
            "development": DevelopmentScreen,
            "tactics": TacticsScreen,
            "season_goals": SeasonGoalsScreen,
            "offseason_programs": OffseasonProgramsScreen,
            "jersey_numbers": JerseyNumbersScreen,
            "gm_options": GMOptionsScreen,
            "gm_relationships": GmRelationshipsScreen,
            "trades": TradesScreen,
            "free_agents": FreeAgentsScreen,
            "waivers": WaiversScreen,
            "offer_sheets": OfferSheetsScreen,
            "trade_block": TradeBlockScreen,
            "deadline": DeadlineScreen,
            "standings": StandingsScreen,
            "stats": StatsScreen,
            "schedule": ScheduleScreen,
            "playoffs": PlayoffsScreen,
            "draft": DraftScreen,
            "draft_central": DraftCentralScreen,
            "draft_recap": DraftRecapScreen,
            "lottery": LotteryScreen,
            "history": HistoryScreen,
            "season_summary": SeasonSummaryScreen,
            "awards_ceremony": AwardsCeremonyScreen,
            "ahl": AhIScreen,
            "calendar": CalendarScreen,
            "team": TeamScreen,
            "team_analytics": TeamAnalyticsScreen,
            "inbox": InboxScreen,
            "news": NewsScreen,
            "finances": FinancesScreen,
            "settings": SettingsScreen,
            "save": SaveScreen,
            "watch": WatchScreen,
            "replay": ReplayScreen,
            "recall_picker": RecallPickerScreen,
            "compare": CompareScreen,
            "coach_checkin": CoachCheckinScreen,
            "manager": ManagerScreen,
            "fa_frenzy": FaFrenzyScreen,
            "fantasy_draft": FantasyDraftScreen,
            "scouting": ScoutingScreen,
            "season_flow": SeasonFlowScreen,
            "season_meeting": SeasonMeetingScreen,
            "contract_negotiation": ContractNegotiationScreen,
            "dressing_room": DressingRoomScreen,
            "media_center": MediaCenterScreen,
            "records": RecordsScreen,
            "shortlist": ShortlistScreen,
            "shot_chart_viewer": ShotChartViewerScreen,
            "analytics": AnalyticsScreen,
            "systems_clutch": SystemsClutchScreen,
            "systems_circumstance": SystemsCircumstanceScreen,
            "systems_discipline": SystemsDisciplineScreen,
            "systems_rivalry": SystemsRivalryScreen,
            "systems_deployment": SystemsDeploymentScreen,
            "systems_condition": SystemsConditionScreen,
        }

        for name, cls in _registry.items():
            try:
                self._screen_classes[name] = cls
            except Exception as e:
                _nav_error(f"[nav] failed to register {name}: {e}")

    def register_screen(self, name, screen_class):
        """Register a screen class for lazy instantiation."""
        self._screen_classes[name] = screen_class

    # --- Navigation ---
    # Centralized section<->screen mapping. show_section() maps section
    # names to screens; _SCREEN_TO_SECTION is the reverse for updating
    # the topbar when navigating directly via show_screen().
    # Canonical topbar sections (uppercase) map to their default screens.
    _SECTION_MAP = {
        "CLUB": "team",
        "PERSONNEL": "staff",
        "LEAGUE": "standings",
        "TRANSACTIONS": "trades",
        "FINANCES": "finances",
        "SYSTEMS": "systems_clutch",
    }
    # Lowercase aliases for convenient navigation (not topbar sections).
    _SCREEN_ALIASES = {
        "hub": "hub",
        "roster": "roster",
        "lines": "lines",
        "team": "team",
        "league": "standings",
        "transactions": "trades",
        "inbox": "inbox",
    }

    @classmethod
    def _section_for_screen(cls, screen_name):
        """Return the topbar section for a screen, or None if none.
        
        Only returns canonical uppercase section names. Screens without
        a topbar section (e.g., hub, roster, inbox) return None, which
        clears the topbar active state.
        """
        for section, screen in cls._SECTION_MAP.items():
            if screen == screen_name:
                return section
        return None

    @classmethod
    def _resolve_screen_name(cls, name):
        """Resolve a section name or alias to a screen name."""
        if name in cls._SECTION_MAP:
            return cls._SECTION_MAP[name]
        if name in cls._SCREEN_ALIASES:
            return cls._SCREEN_ALIASES[name]
        # Assume it's already a screen name
        return name

    def show_screen(self, name):
        """Navigate to a registered screen, instantiating on first use."""
        # Keep the topbar selection in sync with direct navigation.
        # Always call set_active: _section_for_screen returns None for
        # section-less screens (hub, roster, inbox, lines), and
        # set_active(None) unchecks every button, so a section-less
        # screen never leaves a stale topbar selection behind.
        try:
            if hasattr(self, "topbar"):
                self.topbar.set_active(self._section_for_screen(name))
        except Exception:
            pass
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

    def show_section(self, name):
        self.topbar.set_active(name)
        screen = self._resolve_screen_name(name)
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
        """Direct Python call -- no HTTP round-trip.

        The day simulation runs in a worker thread via run_threaded so the
        UI stays responsive (progress dialog with cancel). _ui_notify calls
        from the worker are marshaled to the UI thread automatically.
        """
        if not self.game:
            return
        try:
            label, blockers = self.game.get_continue_state()
            if blockers:
                self.show_blockers(blockers)
                return
            # Heavy-sim confirmation + fallback save (standard pattern).
            try:
                from native_ui.dialogs.sim_progress import (
                    run_threaded, create_fallback_save, ask_heavy_sim)
            except Exception as e:
                print(f"[native] sim progress import failed: {e}")
                # Fall back to synchronous sim if the dialog is unavailable.
                if hasattr(self.game, "simulate_day"):
                    self.game.simulate_day()
                self._refresh_after_continue()
                return

            create_fallback_save(self.game, "continue")

            def _do_sim(cancel_event, progress):
                # Runs OFF the UI thread. Must not touch widgets.
                if hasattr(self.game, "simulate_day"):
                    self.game.simulate_day()

            def _on_done(cancelled, error):
                # Runs ON the UI thread.
                if error is not None:
                    print(f"[native] continue failed: {error}")
                elif not cancelled:
                    self._refresh_after_continue()

            # For a single day the sim is usually fast; run_threaded handles
            # both fast and slow cases with a responsive progress dialog.
            run_threaded(self, "Simulating day...", _do_sim,
                         on_done=_on_done, status="Simulating day...")
        except Exception as e:
            print(f"[native] continue failed: {e}")

    def _refresh_after_continue(self):
        """Refresh the current screen after a day sim completes."""
        try:
            current = self.stack.currentWidget() if hasattr(self, "stack") else None
            if current and hasattr(current, "refresh"):
                current.refresh()
            elif hasattr(self, "hub"):
                self.hub.refresh(self.game)
        except Exception as e:
            print(f"[native] refresh after continue failed: {e}")

    # --- GameManager._ui_notify dispatch (Priority 1 bug #4) ---
    # GameManager routes every UI notification through _ui_notify(kind, ...).
    # The base implementation is `pass` and MainWindow never overrode it, so
    # all 37 call sites silently dropped their notifications (contract
    # results, post-advance landing, blockers, info/warning/error popups,
    # open_screen requests, ...). This override is the root-cause fix:
    # every kind is dispatched to the native UI instead of vanishing.
    #
    # Kinds that expect a return value: "ask_game_mode" ('quick'/'watch'),
    # "game_day_bundle" (bool, was-opened).
    #
    # Thread-safety: simulate_day() may run in a worker thread (via
    # run_threaded in on_continue). _ui_notify handlers show modals and
    # navigate screens, which MUST run on the UI thread. When called from
    # a worker, marshal to the UI thread and block for the result.
    def _ui_notify(self, kind, *args, **kwargs):
        """Dispatch a GameManager notification to the native UI."""
        try:
            from PySide6.QtCore import QThread
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            ui_thread = app.thread() if app is not None else None
            if (ui_thread is not None
                    and QThread.currentThread() != ui_thread):
                return self._ui_notify_from_worker(kind, *args, **kwargs)
        except Exception:
            pass  # Fall through to direct dispatch on any threading issue
        return self._ui_notify_on_ui_thread(kind, *args, **kwargs)

    def _ui_notify_from_worker(self, kind, *args, **kwargs):
        """Marshal a _ui_notify call from a worker thread to the UI thread.

        Blocks the worker until the UI thread completes the handler and
        returns its result. Uses QTimer.singleShot(0) which is processed
        by the UI thread's event loop (including modal dialog loops).
        """
        from PySide6.QtCore import QTimer
        result_box = {}
        error_box = {}
        done = threading.Event()

        def _run_on_ui():
            try:
                result_box["value"] = self._ui_notify_on_ui_thread(
                    kind, *args, **kwargs)
            except Exception as e:  # noqa: BLE001 -- reported to caller
                error_box["error"] = e
            finally:
                done.set()

        QTimer.singleShot(0, _run_on_ui)
        done.wait()
        if "error" in error_box:
            print(f"[native] _ui_notify {kind!r} failed: {error_box['error']}")
            return None
        return result_box.get("value")

    def _ui_notify_on_ui_thread(self, kind, *args, **kwargs):
        """Original _ui_notify dispatch logic. Must run on the UI thread."""
        try:
            handler = getattr(self, "_notify_" + str(kind), None)
            if handler is None:
                # Unknown kind: log, never raise (game logic must not crash
                # because the UI doesn't know a notification type).
                print(f"[native] unhandled _ui_notify kind: {kind!r}")
                return None
            return handler(*args, **kwargs)
        except Exception as e:
            print(f"[native] _ui_notify {kind!r} failed: {e}")
            return None

    # -- message popups --
    def _notify_info(self, *args):
        title, msg = self._notify_title_msg(args, "Puck Dynasty")
        _modal.information(self, title, msg)

    def _notify_warning(self, *args):
        title, msg = self._notify_title_msg(args, "Warning")
        _modal.warning(self, title, msg)

    def _notify_error(self, *args):
        title, msg = self._notify_title_msg(args, "Error")
        _modal.critical(self, title, msg)

    def _notify_achievement(self, *args):
        title, msg = self._notify_title_msg(args, "Achievement")
        _modal.information(self, "\U0001F3C6 " + title, msg)

    @staticmethod
    def _notify_title_msg(args, default_title):
        """Call sites pass (msg,) or (title, msg)."""
        if len(args) >= 2:
            return str(args[0]), str(args[1])
        if len(args) == 1:
            return default_title, str(args[0])
        return default_title, ""

    # -- contract feedback --
    # Call signature: (outcome, person, salary, years, asking_price,
    #                  extension, notify, clause_kind=..., clause_list_size=...)
    # notify: "popup" (legacy messagebox), "inbox" (FM24/EHM-style inbox
    # message; the game already created it via _inbox_contract_result),
    # "quiet" (no notification -- bulk callers send one digest themselves).
    def _notify_contract_result(self, outcome, person=None, salary=0,
                                years=1, asking_price=0, extension=False,
                                notify="popup", **kwargs):
        try:
            name = getattr(person, "full_name", None) or "The player"
            term = "extension" if extension else "contract"
            try:
                salary_s = f"${int(salary):,}"
            except Exception:
                salary_s = str(salary)
            if outcome == "accepted":
                title = "Signed: " + name
                msg = (f"{name} has agreed to terms: {salary_s} per year "
                       f"over {int(years)} year(s).\n\n"
                       f"The {term} is finalized and filed with the league "
                       f"office.")
            elif outcome == "rejected":
                title = "Offer rejected: " + name
                msg = (f"{name} has rejected your offer of {salary_s} per "
                       f"year outright and is not countering at this "
                       f"time.\n\nHis camp feels the number needs to be "
                       f"significantly higher before talks resume.")
            else:  # counter -- interactive, lives in the inbox
                try:
                    ask_s = f"${int(asking_price):,}"
                except Exception:
                    ask_s = str(asking_price)
                title = "Counter-offer: " + name
                msg = (f"{name}'s camp has rejected your offer of "
                       f"{salary_s} per year, but they will sign for "
                       f"{ask_s} per year over {int(years)} year(s).\n\n"
                       f"Respond in the inbox -- the offer waits for you.")
            # Make sure the inbox UI reflects the new message the game
            # just created (badge, recent panel, inbox screen refresh).
            try:
                self._refresh_inbox_ui()
            except Exception:
                pass
            if notify == "quiet":
                return
            if notify == "inbox":
                _modal.information(
                    self, "\U0001F4E9 " + title,
                    msg + "\n\nA full message is waiting in your inbox.")
            else:  # "popup" (legacy) and anything else
                if outcome == "rejected":
                    _modal.warning(self, title, msg)
                else:
                    _modal.information(self, title, msg)
        except Exception as e:
            print(f"[native] contract_result notify failed: {e}")

    def _refresh_inbox_ui(self):
        """Refresh the hub inbox badge/panel and the inbox screen if open."""
        try:
            if hasattr(self, "hub") and self.hub:
                self.hub.refresh(self.game)
        except Exception:
            pass
        try:
            scroll = self._screens.get("inbox")
            inner = scroll.widget() if scroll and hasattr(scroll, "widget") \
                else None
            if inner is not None and hasattr(inner, "refresh"):
                inner.refresh()
        except Exception:
            pass

    # -- day advancement --
    def _notify_blockers(self, blockers):
        self.show_blockers(blockers or [])

    def _notify_post_advance(self):
        """Post-advance landing: show the daily results dialog."""
        try:
            from .dialogs.daily_results import DailyResultsDialog
            dlg = DailyResultsDialog(self.game, self)
            _modal.exec_dialog(dlg, "daily_results")
        except Exception as e:
            print(f"[native] daily results failed: {e}")

    def _notify_continue_feedback(self, busy, status=""):
        """Update continue-button state: wait cursor + status on the hub."""
        try:
            from PySide6.QtWidgets import QApplication
            if busy:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            else:
                QApplication.restoreOverrideCursor()
            if status:
                print(f"[native] continue: {status}")
        except Exception:
            pass

    # -- navigation --
    def _notify_open_screen(self, *args, **kwargs):
        screen = kwargs.get("screen") or (args[0] if args else None)
        if screen:
            self.show_screen(str(screen))

    def _notify_open_fantasy_draft(self, *args, **kwargs):
        self.show_screen("fantasy_draft")

    def _notify_open_trade_window(self, *args, **kwargs):
        self.show_screen("trades")

    def _notify_open_free_agency_window(self, *args, **kwargs):
        self.show_screen("free_agents")

    # -- view refresh --
    def _notify_update_views(self, *args, **kwargs):
        try:
            self.refresh()
        except Exception as e:
            print(f"[native] update_views failed: {e}")

    def _notify_news_updated(self, *args, **kwargs):
        self._refresh_inbox_ui()

    def _notify_inbox_notification_updated(self, *args, **kwargs):
        self._refresh_inbox_ui()

    def _notify_scouting_reports_updated(self, *args, **kwargs):
        try:
            cur = self.stack.currentWidget() if hasattr(self, "stack") else None
            inner = cur.widget() if cur is not None and hasattr(cur, "widget") \
                else cur
            name = type(inner).__name__ if inner is not None else ""
            if "Scout" in name and hasattr(inner, "refresh"):
                inner.refresh()
        except Exception:
            pass

    # -- synchronous dialogs --
    def _notify_ask_game_mode(self, home_team=None, away_team=None):
        """Pre-game modal: Quick Sim or Watch Live? Returns 'quick'/'watch'."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        try:
            home = getattr(home_team, "team_name", None) or str(home_team or "")
            away = getattr(away_team, "team_name", None) or str(away_team or "")
            dlg = QDialog(self)
            dlg.setWindowTitle("Game options")
            dlg.setMinimumWidth(360)
            layout = QVBoxLayout(dlg)
            title = QLabel(f"{away} @ {home}" if home or away else "Game")
            title.setObjectName("dialog-title")
            title.setWordWrap(True)
            layout.addWidget(title)
            result = {"mode": "quick"}

            def _pick(mode):
                result["mode"] = mode
                dlg.accept()

            quick_btn = QPushButton("Quick Sim")
            quick_btn.setObjectName("primary-btn")
            quick_btn.clicked.connect(lambda: _pick("quick"))
            watch_btn = QPushButton("Watch Live")
            watch_btn.setObjectName("primary-btn")
            watch_btn.clicked.connect(lambda: _pick("watch"))
            layout.addWidget(quick_btn)
            layout.addWidget(watch_btn)
            _modal.exec_dialog(dlg, "ask_game_mode")
            return result["mode"]
        except Exception as e:
            print(f"[native] ask_game_mode failed: {e}")
            return "quick"

    def _notify_ask_playoffs_mode(self, *args, **kwargs):
        """Ask user: play through playoffs interactively or quick-sim?

        Returns True (interactive), False (quick-sim), or "defer" when a
        real user dismisses the dialog (X/Escape) without choosing --
        dismissing must never silently quick-sim the season away; the
        season-end flow re-asks on the next Continue. Under automation
        bypass (PUCK_DYNASTY_NO_MODAL=1) returns False so scripted UI
        drivers / headless bots can never defer-loop."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("Playoff options")
            dlg.setMinimumWidth(360)
            layout = QVBoxLayout(dlg)
            title = QLabel("The playoffs are here!\n\nDo you want to play through the playoff games or quick-sim the whole bracket?")
            title.setObjectName("dialog-title")
            title.setWordWrap(True)
            layout.addWidget(title)
            # None = no choice made yet. The old code defaulted this to
            # False, which made an X/Escape dismissal indistinguishable
            # from an explicit "Quick Sim" pick -- the defer/re-ask path
            # could never trigger.
            result = {"interactive": None}

            def _pick(interactive):
                result["interactive"] = interactive
                dlg.accept()

            play_btn = QPushButton("Play Through")
            play_btn.setObjectName("primary-btn")
            play_btn.clicked.connect(lambda: _pick(True))
            quick_btn = QPushButton("Quick Sim")
            quick_btn.setObjectName("primary-btn")
            quick_btn.clicked.connect(lambda: _pick(False))
            layout.addWidget(play_btn)
            layout.addWidget(quick_btn)
            _modal.exec_dialog(dlg, "ask_playoffs_mode")
            # Automation bypass treats the dialog as dismissed without
            # blocking -- a scripted driver has no user to re-ask, so it
            # quick-sims instead of deferring (no defer-loop).
            if _modal.automation_bypass():
                return False
            if result["interactive"] is not None:
                return result["interactive"]
            # Real user dismissed the dialog without choosing: defer the
            # choice; end_of_season re-asks on the next Continue.
            return "defer"
        except Exception as e:
            print(f"[native] ask_playoffs_mode failed: {e}")
            return False

    # -- multiplayer / misc (single-player safe defaults) --
    def _notify_mp_refresh(self, *args, **kwargs):
        self._notify_update_views()

    def _notify_mp_host_ready_toggle(self, *args, **kwargs):
        self._notify_update_views()

    def _notify_mp_state_synced(self, *args, **kwargs):
        self._notify_update_views()

    def _notify_mp_draft_clock(self, *args, **kwargs):
        # Draft clock is owned by the MP draft screens; single-player no-op.
        pass

    def _notify_mp_promote_to_host(self, *args, **kwargs):
        self._notify_info("Multiplayer", "You have been promoted to host.")

    def _notify_mp_disconnected(self, *args, **kwargs):
        reason = str(args[0]) if args else ""
        self._notify_warning("Multiplayer disconnected", reason)

    def _notify_mp_trade_offer(self, *args, **kwargs):
        self._refresh_inbox_ui()
        self._notify_info("Trade offer", "A new trade offer is waiting.")

    def _notify_mp_ntc_request(self, *args, **kwargs):
        self._notify_info("No-trade request",
                          "A player has requested a trade decision.")

    def _notify_mp_snapshot_failed(self, *args, **kwargs):
        msg = str(args[0]) if args else "Could not save the MP snapshot."
        self._notify_error("Could not join", msg)

    def _notify_game_day_bundle(self, *args, **kwargs):
        # Headless default: not opened. Native opens game-day via the
        # schedule screen; the bundle dialog is MP-only.
        return False

    def _notify_team_talk(self, *args, **kwargs):
        # Fallback hook for the Tk team-talk path; Qt returns neutral 1.0
        # game-side, nothing to show.
        pass

    def _notify_prompts_enabled(self, *args, **kwargs):
        # Generic shim; UI just keeps responding to prompts.
        pass

    # Priority 1 bug #5: unified blocker-action -> native-screen map.
    # Covers both the new action_id format and the old tuple format
    # (keyed by blocker id). Previously only 5-6 ids were mapped and
    # roster_limit_23 / dress_minimum rendered dead buttons.
    _BLOCKER_SCREEN_MAP = {
        "fantasy_draft": "fantasy_draft",
        "entry_draft": "draft",
        "trade": "trades",
        "salary_cap": "trades",
        "free_agency": "free_agents",
        "salary_floor": "free_agents",
        "captaincy": "captains",
        "captaincy_choice": "captains",
        "season_meeting": "season_meeting",
        "roster_limit_23": "roster",
        "dress_minimum": "recall_picker",
    }

    def show_blockers(self, blockers):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame

        def _fire_action(cb):
            """Run a blocker callback guarded -- never let a Tk-era
            closure take down the dialog."""
            try:
                cb()
            except Exception as e:
                print(f"[native] blocker action failed: {e}")
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
                    # Map action IDs to native screens
                    native_target = self._BLOCKER_SCREEN_MAP.get(action_id)
                    if native_target:
                        btn = QPushButton(action_label)
                        btn.setObjectName("primary-btn")
                        btn.clicked.connect(
                            lambda _=False, n=native_target: (
                                dlg.accept(), self.show_screen(n)))
                        cl.addWidget(btn)
                    else:
                        # Unknown action_id: LOUD, never a dead button.
                        # Rendering a button with zero `clicked` receivers
                        # is the exact failure mode that burned trust.
                        print(f"[native] show_blockers: unknown "
                              f"action_id {action_id!r} -- no button "
                              f"rendered")
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
                        native_target = self._BLOCKER_SCREEN_MAP.get(
                            blocker_id)
                        if native_target:
                            # Known blocker id: navigate to the native
                            # screen (roster_limit_23 -> roster,
                            # dress_minimum -> recall_picker). The raw
                            # tuple callback is a Tk-era closure and is
                            # deliberately NOT used.
                            btn.clicked.connect(
                                lambda _=False, n=native_target: (
                                    dlg.accept(), self.show_screen(n)))
                        else:
                            # Unknown blocker id (e.g. pending popup
                            # items' "Go to it"): fire the tuple callback
                            # guarded. The GameManager.show_screen bridge
                            # installed in __init__ lets Tk-era closures
                            # like the pending-item _jump resolve.
                            btn.clicked.connect(
                                lambda _=False, cb=callback: (
                                    dlg.accept(), _fire_action(cb)))
                        cl.addWidget(btn)
                    except Exception:
                        pass
                # Render secondary_action button if present (e.g. the IR
                # quick-fix on the roster-limit blocker)
                secondary_action = b.get("secondary_action")
                if secondary_action:
                    try:
                        sec_label, sec_cb = secondary_action
                        sec_btn = QPushButton(sec_label)
                        sec_btn.setObjectName("secondary-btn")
                        sec_btn.clicked.connect(
                            lambda _=False, cb=sec_cb: (
                                dlg.accept(), _fire_action(cb)))
                        cl.addWidget(sec_btn)
                    except Exception:
                        pass
            # Render auto_action button if present (e.g. Auto-pick Captains,
            # Auto-shed salary). These callbacks are UI-agnostic game logic
            # (roster_limits._auto_demote / _auto_recall, game_manager
            # _auto_captains / _auto_fix_cap, coach_season_meeting._auto) --
            # fire them directly via _fire_action so the button actually
            # does what its label promises. The old captaincy special-case
            # that only navigated to the captains screen is gone: the
            # captaincy callback IS the real auto-pick (same code path the
            # headless auto-resolve uses), so "Auto-pick Captains" picks.
            auto_action = b.get("auto_action")
            if auto_action:
                try:
                    auto_label, auto_cb = auto_action
                    auto_btn = QPushButton(auto_label)
                    auto_btn.setObjectName("primary-btn")
                    # NOTE: clicked(bool) passes a `checked` positional, so
                    # the slot must swallow it first. Connecting
                    # `def f(cb=auto_cb)` directly made `cb` receive False,
                    # and False() raised TypeError inside a swallowed
                    # except -- dead buttons that only closed the dialog.
                    auto_btn.clicked.connect(
                        lambda _=False, cb=auto_cb: (
                            dlg.accept(), _fire_action(cb)))
                    cl.addWidget(auto_btn)
                except Exception:
                    pass
            layout.addWidget(card)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        # Centralized modal helper honors PUCK_DYNASTY_NO_MODAL for
        # scripted UI drivers; real users get the blocking dialog.
        _modal.exec_dialog(dlg, "blockers")
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

    def _menu_nav_item(self, menu, label, navigate):
        """Add one navigation entry to a menu-bar menu.

        `navigate` is a zero-arg callable written at the call site with a
        literal show_screen("<key>") call, keeping the navigation graph
        statically greppable (every registered screen must be reachable).
        """
        act = QAction(label, self)
        act.triggered.connect(navigate)
        menu.addAction(act)
        return act

    def _setup_menu_nav(self):
        """Build the menu-bar directory: every registered screen, one click.

        Hub tiles cover the daily screens; this menu makes the full
        feature set (draft central, waivers, offer sheets, systems...)
        discoverable without turning the hub into a maze of tiles.
        """
        mb = self.menuBar()
        mb.setObjectName("nav-menubar")
        mb.setStyleSheet(
            "QMenuBar { background: #0b1220; color: #dbe4f2;"
            " border-bottom: 1px solid rgba(255,255,255,0.08); }"
            "QMenuBar::item { padding: 6px 12px; background: transparent; }"
            "QMenuBar::item:selected { background: rgba(59,130,246,0.25); }"
            "QMenu { background: #0d1526; color: #dbe4f2;"
            " border: 1px solid rgba(255,255,255,0.10); }"
            "QMenu::item { padding: 6px 26px 6px 14px; }"
            "QMenu::item:selected { background: rgba(59,130,246,0.30); }"
        )
        mi = self._menu_nav_item

        club = mb.addMenu("&Club")
        mi(club, "Roster", lambda _c=False: self.show_screen("roster"))
        mi(club, "Lines", lambda _c=False: self.show_screen("lines"))
        mi(club, "Team Overview", lambda _c=False: self.show_screen("team"))
        mi(club, "Practice Center",
           lambda _c=False: self.show_screen("practice_center"))
        mi(club, "Training Camp", lambda _c=False: self.show_screen("camp"))
        mi(club, "Offseason Programs",
           lambda _c=False: self.show_screen("offseason_programs"))
        mi(club, "Tactics", lambda _c=False: self.show_screen("tactics"))
        mi(club, "Morale", lambda _c=False: self.show_screen("morale"))
        mi(club, "Player Development",
           lambda _c=False: self.show_screen("development"))
        mi(club, "Dressing Room",
           lambda _c=False: self.show_screen("dressing_room"))
        mi(club, "Captains", lambda _c=False: self.show_screen("captains"))
        mi(club, "Coach Check-In",
           lambda _c=False: self.show_screen("coach_checkin"))
        mi(club, "AHL Affiliate", lambda _c=False: self.show_screen("ahl"))
        mi(club, "Staff", lambda _c=False: self.show_screen("staff"))
        mi(club, "Jersey Numbers",
           lambda _c=False: self.show_screen("jersey_numbers"))

        league = mb.addMenu("&League")
        mi(league, "Standings", lambda _c=False: self.show_screen("standings"))
        mi(league, "Team Stats", lambda _c=False: self.show_screen("stats"))
        mi(league, "Schedule", lambda _c=False: self.show_screen("schedule"))
        mi(league, "Playoffs", lambda _c=False: self.show_screen("playoffs"))
        mi(league, "Calendar", lambda _c=False: self.show_screen("calendar"))
        mi(league, "League History",
           lambda _c=False: self.show_screen("history"))
        mi(league, "Records", lambda _c=False: self.show_screen("records"))
        mi(league, "Season Summary",
           lambda _c=False: self.show_screen("season_summary"))
        mi(league, "Awards Ceremony",
           lambda _c=False: self.show_screen("awards_ceremony"))
        mi(league, "League News", lambda _c=False: self.show_screen("news"))
        mi(league, "Media Center",
           lambda _c=False: self.show_screen("media_center"))
        mi(league, "Shot Chart Viewer",
           lambda _c=False: self.show_screen("shot_chart_viewer"))

        trans = mb.addMenu("&Transactions")
        mi(trans, "Trade Center", lambda _c=False: self.show_screen("trades"))
        mi(trans, "Trade Block",
           lambda _c=False: self.show_screen("trade_block"))
        mi(trans, "Waivers", lambda _c=False: self.show_screen("waivers"))
        mi(trans, "Free Agents",
           lambda _c=False: self.show_screen("free_agents"))
        mi(trans, "Offer Sheets",
           lambda _c=False: self.show_screen("offer_sheets"))
        mi(trans, "FA Frenzy", lambda _c=False: self.show_screen("fa_frenzy"))
        mi(trans, "Contracts", lambda _c=False: self.show_screen("contracts"))
        mi(trans, "Contract Negotiation",
           lambda _c=False: self.show_screen("contract_negotiation"))
        mi(trans, "Scouting", lambda _c=False: self.show_screen("scouting"))
        mi(trans, "Player Shortlist",
           lambda _c=False: self.show_screen("shortlist"))
        mi(trans, "Entry Draft", lambda _c=False: self.show_screen("draft"))
        mi(trans, "Draft Central",
           lambda _c=False: self.show_screen("draft_central"))
        mi(trans, "Draft Recap",
           lambda _c=False: self.show_screen("draft_recap"))
        mi(trans, "Draft Lottery",
           lambda _c=False: self.show_screen("lottery"))
        mi(trans, "Trade Deadline",
           lambda _c=False: self.show_screen("deadline"))
        mi(trans, "Fantasy Draft",
           lambda _c=False: self.show_screen("fantasy_draft"))

        office = mb.addMenu("Front &Office")
        mi(office, "GM Options Hub",
           lambda _c=False: self.show_screen("gm_options"))
        mi(office, "Manager Dashboard",
           lambda _c=False: self.show_screen("manager"))
        mi(office, "Analytics Hub",
           lambda _c=False: self.show_screen("analytics"))
        mi(office, "Team Analytics",
           lambda _c=False: self.show_screen("team_analytics"))
        mi(office, "GM Relationships",
           lambda _c=False: self.show_screen("gm_relationships"))
        mi(office, "Season Goals",
           lambda _c=False: self.show_screen("season_goals"))
        mi(office, "Season Meeting",
           lambda _c=False: self.show_screen("season_meeting"))
        mi(office, "Finances", lambda _c=False: self.show_screen("finances"))
        mi(office, "Inbox", lambda _c=False: self.show_screen("inbox"))
        mi(office, "Compare Players",
           lambda _c=False: self.show_screen("compare"))

        systems = mb.addMenu("S&ystems")
        mi(systems, "Clutch Systems",
           lambda _c=False: self.show_screen("systems_clutch"))
        mi(systems, "Circumstance Systems",
           lambda _c=False: self.show_screen("systems_circumstance"))
        mi(systems, "Discipline Systems",
           lambda _c=False: self.show_screen("systems_discipline"))
        mi(systems, "Rivalry Systems",
           lambda _c=False: self.show_screen("systems_rivalry"))
        mi(systems, "Deployment Systems",
           lambda _c=False: self.show_screen("systems_deployment"))
        mi(systems, "Condition Systems",
           lambda _c=False: self.show_screen("systems_condition"))

        game = mb.addMenu("&Game")
        mi(game, "Watch Live", lambda _c=False: self.show_screen("watch"))
        mi(game, "Replay Center", lambda _c=False: self.show_screen("replay"))
        mi(game, "Player Profile",
           lambda _c=False: self.show_screen("player"))
        mi(game, "Staff Detail",
           lambda _c=False: self.show_screen("staff_detail"))
        mi(game, "Recall Picker",
           lambda _c=False: self.show_screen("recall_picker"))
        mi(game, "Settings", lambda _c=False: self.show_screen("settings"))
        mi(game, "Save / Load", lambda _c=False: self.show_screen("save"))
        mi(game, "Setup Wizard", lambda _c=False: self.show_screen("setup"))
        mi(game, "Multiplayer",
           lambda _c=False: self.show_screen("multiplayer"))
        game.addSeparator()
        sc = QAction("Keyboard Shortcuts", self)
        sc.triggered.connect(lambda _c=False: self.show_shortcuts_dialog())
        game.addAction(sc)

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
            detail = "registered screens: " + ", ".join(
                sorted(window._screen_classes.keys())[:8]) + "..."
            _nav_error(f"[nav] setup screen not shown after launch. {detail}")
            _modal.critical(
                window, "Setup unavailable",
                "The new-career setup wizard could not be loaded.\n\n"
                "Please report this and attach puck_dynasty_errors.log "
                "from the install folder.")
    return app.exec()
