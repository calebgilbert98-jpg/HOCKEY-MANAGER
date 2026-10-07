"""Setup wizard: full launcher parity with web_ui/templates/setup.html.

Tabs: Create GM / Choose Team / Advanced Setup / Load Game / Multiplayer.
New careers go through GameManager.apply_startup_settings (database
generation with the wizard's options) then setup_new_game, mirroring the
web launcher's _do_setup_new_game flow.
"""
import gzip
import os
import pickle
import random
import re
import shutil
import socket
import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTabWidget, QListWidget, QListWidgetItem, QMessageBox,
    QCheckBox, QScrollArea, QProgressDialog, QFileDialog, QGridLayout,
    QGroupBox, QApplication,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


# ---------------------------------------------------------------------------
# Qt shim for progress_window.DatabaseGenerationProgress (Tkinter).
#
# GameManager.apply_startup_settings does a function-local
# `from progress_window import DatabaseGenerationProgress` and drives it as
# a context manager with .update(pct, status, detail).  In the native Qt app
# we shim the module in sys.modules so the import resolves to this Qt-backed
# version.  Contained entirely in native code -- shared engine untouched.
# ---------------------------------------------------------------------------
_active_progress_dialog = None


class _QtDatabaseGenerationProgress:
    """Qt-backed drop-in for the Tkinter DatabaseGenerationProgress."""

    def __init__(self, *args, **kwargs):
        self._dlg = _active_progress_dialog

    def __enter__(self):
        if self._dlg is not None:
            try:
                self._dlg.setValue(0)
                self._dlg.show()
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._dlg is not None:
            try:
                # NOTE: use hide(), not close() -- QProgressDialog.close()
                # marks the dialog canceled (wasCanceled() -> True).
                self._dlg.hide()
            except Exception:
                pass
        return False

    def update(self, percentage, status, detail=""):
        if self._dlg is None:
            return
        try:
            pct = max(0, min(100, int(percentage)))
            label = str(status or "")
            if detail:
                label = f"{label}\n{detail}"
            self._dlg.setLabelText(label)
            self._dlg.setValue(pct)
            QApplication.processEvents()
            if self._dlg.wasCanceled():
                raise RuntimeError("Database generation cancelled.")
        except RuntimeError:
            raise
        except Exception:
            pass


class _ProgressShimModule:
    """Fake module object exposing DatabaseGenerationProgress."""
    DatabaseGenerationProgress = _QtDatabaseGenerationProgress


def _install_qt_progress_shim(dialog):
    global _active_progress_dialog
    _active_progress_dialog = dialog
    sys.modules["progress_window"] = _ProgressShimModule()


def _remove_qt_progress_shim():
    global _active_progress_dialog
    _active_progress_dialog = None
    sys.modules.pop("progress_window", None)


# ---------------------------------------------------------------------------
# Pill button groups (single- or multi-select), mirroring the HTML .fpills.
# ---------------------------------------------------------------------------
_PILL_OFF = (
    "QPushButton { background-color: #1a2340; color: #9fb0d0; border: 1px solid #2a3a5f;"
    " border-radius: 14px; padding: 6px 14px; font-size: 13px; }"
    "QPushButton:hover { border-color: #3B82F6; color: #dbe4ff; }"
)
_PILL_ON = (
    "QPushButton { background-color: #3B82F6; color: #ffffff; border: 1px solid #3B82F6;"
    " border-radius: 14px; padding: 6px 14px; font-size: 13px; font-weight: 700; }"
)


class PillGroup(QWidget):
    """Row of toggle pill buttons."""

    def __init__(self, options, multi=False, parent=None):
        """
        options: list of (value, label[, tooltip]) tuples or plain labels.
        multi: allow multiple selection (checkbox behavior).
        """
        super().__init__(parent)
        self._multi = multi
        self._buttons = {}  # value -> QPushButton
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        for opt in options:
            if isinstance(opt, (list, tuple)):
                value = opt[0]
                label = opt[1] if len(opt) > 1 else str(opt[0])
                tip = opt[2] if len(opt) > 2 else ""
            else:
                value, label, tip = opt, str(opt), ""
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if tip:
                btn.setToolTip(tip)
            btn.setStyleSheet(_PILL_OFF)
            btn.toggled.connect(lambda checked, v=value: self._on_toggled(v, checked))
            lay.addWidget(btn)
            self._buttons[value] = btn
        lay.addStretch(1)

    def _on_toggled(self, value, checked):
        btn = self._buttons[value]
        btn.setStyleSheet(_PILL_ON if checked else _PILL_OFF)
        if checked and not self._multi:
            for v, b in self._buttons.items():
                if v != value and b.isChecked():
                    b.setChecked(False)

    def set_selected(self, values):
        if isinstance(values, str):
            values = [values]
        values = set(values)
        for v, b in self._buttons.items():
            b.setChecked(v in values)

    def selected(self):
        vals = [v for v, b in self._buttons.items() if b.isChecked()]
        return vals if self._multi else (vals[0] if vals else None)


# ---------------------------------------------------------------------------
# Setup screen
# ---------------------------------------------------------------------------
_GM_FIRST = ["Alex", "Jordan", "Casey", "Taylor", "Morgan", "Jamie", "Riley",
             "Cameron", "Blake", "Avery", "Michael", "David", "John",
             "Robert", "Chris", "Daniel", "Mark", "Paul", "Steve", "Kevin"]
_GM_LAST = ["Anderson", "Johnson", "Williams", "Brown", "Jones", "Garcia",
            "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
            "Gonzalez", "Wilson", "Thomas", "Taylor", "Moore", "Jackson",
            "Martin", "Lee"]

_DB_SIZES = [
    ("default", "Default", "~8,000 players · recommended"),
    ("small", "Small", "~2,500 players · fastest"),
    ("medium", "Medium", "~6,000 players · balanced"),
    ("large", "Large", "~12,000 players · slowest"),
]
_START_DATES = ["August 1, 2024", "September 1, 2024",
                "October 1, 2024", "November 1, 2024"]
_SEASON_LENGTHS = ["Default (84 Games)", "Short Season (20 Games)",
                   "Half Season (41 Games)", "Extended Season (100 Games)"]
_DIFFICULTIES = ["Rookie", "Amateur", "Professional", "Realistic",
                 "Hall of Fame"]
_LEAGUES = ["NHL", "AHL", "ECHL", "KHL"]
_SIM_DETAILS = [("full", "Full — event-by-event"),
                ("quick", "Quick — scores + standings"),
                ("scores", "Scores only")]
_SIM_DEFAULTS = {"NHL": "full", "AHL": "quick",
                 "ECHL": "scores", "KHL": "quick"}

_MP_DEFAULT_PORT = 27107


class SetupScreen(BaseScreen):
    title = "Setup"

    # -- BaseScreen hooks -------------------------------------------------
    def _build_header(self):
        # Custom hero below replaces the default header.
        pass

    def _build_body(self):
        # Hero
        hero = QVBoxLayout()
        hero.setSpacing(2)
        crest = QLabel("🏒")
        crest.setStyleSheet("font-size: 40px;")
        crest.setAlignment(Qt.AlignCenter)
        hero.addWidget(crest)
        kicker = QLabel("FRANCHISE MODE · OFFLINE")
        kicker.setStyleSheet("color: #3B82F6; font-size: 12px; font-weight: 700;"
                             " letter-spacing: 3px;")
        kicker.setAlignment(Qt.AlignCenter)
        hero.addWidget(kicker)
        title = QLabel("Puck Dynasty")
        title.setStyleSheet("font-size: 40px; font-weight: 900; color: #ffffff;")
        title.setAlignment(Qt.AlignCenter)
        hero.addWidget(title)
        tag = QLabel("Build your <b>dynasty</b>. Choose your path to the Cup.")
        tag.setStyleSheet("color: #9fb0d0; font-size: 14px;")
        tag.setAlignment(Qt.AlignCenter)
        hero.addWidget(tag)
        self._layout.addLayout(hero)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2a3a5f; border-radius: 8px; }"
            "QTabBar::tab { background: #141b33; color: #9fb0d0; padding: 10px 18px;"
            " margin-right: 4px; border-top-left-radius: 8px;"
            " border-top-right-radius: 8px; font-size: 14px; }"
            "QTabBar::tab:selected { background: #1a2340; color: #ffffff;"
            " font-weight: 700; }"
        )
        self._tab_gm = self._make_gm_tab()
        self._tab_team = self._make_team_tab()
        self._tab_adv = self._make_advanced_tab()
        self._tab_load = self._make_load_tab()
        self._tab_mp = self._make_mp_tab()
        self._tabs.addTab(self._tab_gm, "Create GM")
        self._tabs.addTab(self._tab_team, "Choose Team")
        self._tabs.addTab(self._tab_adv, "Advanced Setup")
        self._tabs.addTab(self._tab_load, "Load Game")
        self._tabs.addTab(self._tab_mp, "Multiplayer")
        self._layout.addWidget(self._tabs, 1)

        # Bottom action bar (always visible, like the HTML .setup-actions)
        bar = QHBoxLayout()
        bar.setSpacing(12)
        self._hint = QLabel("Select a team to start your career.")
        self._hint.setStyleSheet("color: #9fb0d0; font-size: 13px;")
        bar.addWidget(self._hint, 1)

        quick_btn = QPushButton("⚡ Quick Start")
        quick_btn.setCursor(Qt.PointingHandCursor)
        quick_btn.setToolTip(
            "Random GM, random team, default settings — straight into the game")
        quick_btn.clicked.connect(self._quick_start)
        bar.addWidget(quick_btn)
        self._quick_btn = quick_btn

        self._start_btn = QPushButton("Start Career →")
        self._start_btn.setObjectName("primary-btn")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start_career)
        bar.addWidget(self._start_btn)
        self._layout.addLayout(bar)

        foot = QLabel("Puck Dynasty runs <b>fully offline</b> — "
                      "your franchise lives on this machine.")
        foot.setStyleSheet("color: #5a6584; font-size: 12px;")
        foot.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(foot)

        # Multiplayer state
        self._mp_host = None
        self._mp_client = None
        self._mp_pending_host = None  # {name, port} staged by Host button
        self._mp_timer = QTimer(self)
        self._mp_timer.timeout.connect(self._mp_poll)

    # -- shared builders --------------------------------------------------
    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #dbe4ff; font-size: 14px; font-weight: 700;"
                          " margin-top: 10px;")
        return lbl

    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #9fb0d0; font-size: 12px;")
        return lbl

    def _scroll_wrap(self, inner):
        """Put a widget in a scroll area (for the tall option tabs)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.setWidget(inner)
        return scroll

    # -- TAB: Create GM ---------------------------------------------------
    def _make_gm_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        head = QLabel("General Manager Profile")
        head.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800;")
        lay.addWidget(head)
        sub = QLabel("Define your identity as a hockey executive. Your choices "
                     "affect team morale, trade negotiations, and media relations.")
        sub.setStyleSheet("color: #9fb0d0; font-size: 13px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        # Name + random
        lay.addWidget(self._field_label("Full name"))
        row = QHBoxLayout()
        self._gm_name = QLineEdit("General Manager")
        self._gm_name.setMaxLength(40)
        self._gm_name.textChanged.connect(self._update_start_state)
        row.addWidget(self._gm_name, 1)
        dice = QPushButton("🎲")
        dice.setToolTip("Random name")
        dice.setCursor(Qt.PointingHandCursor)
        dice.clicked.connect(self._random_gm_name)
        row.addWidget(dice)
        lay.addLayout(row)

        # Age + experience
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(self._field_label("Age"))
        self._gm_age = QComboBox()
        for a in range(28, 66):
            self._gm_age.addItem(str(a), a)
        self._gm_age.setCurrentText("35")
        box.addWidget(self._gm_age)
        row.addLayout(box, 1)
        box = QVBoxLayout()
        box.addWidget(self._field_label("Experience"))
        self._gm_exp = QComboBox()
        self._gm_exp.addItems(["First-Time GM", "Assistant GM Experience",
                              "Former GM", "Veteran Executive"])
        box.addWidget(self._gm_exp)
        row.addLayout(box, 1)
        lay.addLayout(row)

        # Background + style
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(self._field_label("Hockey background"))
        self._gm_bg = QComboBox()
        self._gm_bg.addItems(["Former Player", "Former Coach", "Former Scout",
                              "Business Executive", "Analytics Expert"])
        box.addWidget(self._gm_bg)
        row.addLayout(box, 1)
        box = QVBoxLayout()
        box.addWidget(self._field_label("Management style"))
        self._gm_style = QComboBox()
        self._gm_style.addItems(["Players' GM", "Strict Disciplinarian",
                                "Analytics-Focused", "Balanced", "Old-School"])
        self._gm_style.setCurrentText("Balanced")
        box.addWidget(self._gm_style)
        row.addLayout(box, 1)
        lay.addLayout(row)

        # Contract + reputation
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(self._field_label("Contract length"))
        self._gm_contract = QComboBox()
        self._gm_contract.addItems(["1 Year (Prove It)", "2 Years", "3 Years",
                                   "4 Years", "5 Years (Long-term)"])
        self._gm_contract.setCurrentText("2 Years")
        box.addWidget(self._gm_contract)
        row.addLayout(box, 1)
        box = QVBoxLayout()
        box.addWidget(self._field_label("Initial reputation"))
        self._gm_rep = QComboBox()
        self._gm_rep.addItems(["Unknown", "Rising Star", "Proven Executive",
                               "Legendary"])
        box.addWidget(self._gm_rep)
        row.addLayout(box, 1)
        lay.addLayout(row)

        # Preview + random profile
        self._gm_preview = QLabel()
        self._gm_preview.setStyleSheet(
            "color: #dbe4ff; font-size: 13px; background: #141b33;"
            " border: 1px solid #2a3a5f; border-radius: 8px; padding: 10px;")
        self._gm_preview.setWordWrap(True)
        lay.addWidget(self._gm_preview)
        for w in (self._gm_name, self._gm_age, self._gm_exp, self._gm_bg,
                  self._gm_style, self._gm_contract, self._gm_rep):
            if isinstance(w, QLineEdit):
                w.textChanged.connect(self._update_gm_preview)
            else:
                w.currentIndexChanged.connect(self._update_gm_preview)

        rnd = QPushButton("Generate Random Profile")
        rnd.setCursor(Qt.PointingHandCursor)
        rnd.clicked.connect(self._random_gm_profile)
        lay.addWidget(rnd, 0, Qt.AlignLeft)
        lay.addStretch(1)
        self._update_gm_preview()
        return self._scroll_wrap(page)

    def _gm_profile_dict(self):
        try:
            age = int(self._gm_age.currentText())
        except Exception:
            age = 35
        return {
            "name": self._gm_name.text().strip() or "General Manager",
            "age": age,
            "experience": self._gm_exp.currentText(),
            "background": self._gm_bg.currentText(),
            "management_style": self._gm_style.currentText(),
            "contract_length": self._gm_contract.currentText(),
            "reputation": self._gm_rep.currentText(),
        }

    def _update_gm_preview(self, *args):
        p = self._gm_profile_dict()
        self._gm_preview.setText(
            f"<b>{p['name']}</b>, {p['age']} — {p['background']} · "
            f"{p['experience']}<br>Style: {p['management_style']} · "
            f"{p['contract_length']} · Reputation: {p['reputation']}")

    def _random_gm_name(self):
        self._gm_name.setText(
            f"{random.choice(_GM_FIRST)} {random.choice(_GM_LAST)}")

    def _random_gm_profile(self):
        self._random_gm_name()
        self._gm_age.setCurrentText(str(random.randint(28, 65)))
        for combo in (self._gm_exp, self._gm_bg, self._gm_style,
                      self._gm_contract, self._gm_rep):
            combo.setCurrentIndex(random.randrange(combo.count()))
        self._update_gm_preview()

    # -- TAB: Choose Team -------------------------------------------------
    def _make_team_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)

        head = QLabel("New Career")
        head.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800;")
        lay.addWidget(head)
        sub = QLabel("Take over a franchise from opening night and shape its future.")
        sub.setStyleSheet("color: #9fb0d0; font-size: 13px;")
        lay.addWidget(sub)

        # League + team pickers
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(self._field_label("League"))
        self._league_picker = QComboBox()
        self._league_picker.addItems(["NHL", "AHL"])
        self._league_picker.currentIndexChanged.connect(self._on_league_changed)
        box.addWidget(self._league_picker)
        row.addLayout(box)
        box = QVBoxLayout()
        box.addWidget(self._field_label("Take control of"))
        self._team_combo = QComboBox()
        self._team_combo.setMinimumWidth(260)
        self._team_combo.currentIndexChanged.connect(self._update_start_state)
        box.addWidget(self._team_combo)
        row.addLayout(box, 1)
        dice = QPushButton("🎲")
        dice.setToolTip("Random team")
        dice.setCursor(Qt.PointingHandCursor)
        dice.clicked.connect(self._random_team)
        row.addWidget(dice, 0, Qt.AlignBottom)
        lay.addLayout(row)

        # Database size
        lay.addWidget(self._section_label("Database size"))
        self._db_pills = PillGroup(
            [(v, lbl, tip) for v, lbl, tip in _DB_SIZES])
        self._db_pills.set_selected(["default"])
        lay.addWidget(self._db_pills)
        self._db_hint = QLabel("~8,000 players · recommended")
        self._db_hint.setStyleSheet("color: #5a6584; font-size: 12px;")
        lay.addWidget(self._db_hint)

        # Season start date
        lay.addWidget(self._section_label("Season start date"))
        self._date_pills = PillGroup([
            ("August 1, 2024", "Aug 1"),
            ("September 1, 2024", "Sep 1"),
            ("October 1, 2024", "Oct 1"),
            ("November 1, 2024", "Nov 1"),
        ])
        self._date_pills.set_selected(["September 1, 2024"])
        lay.addWidget(self._date_pills)

        # Season length
        lay.addWidget(self._section_label("Season length"))
        self._len_pills = PillGroup([
            ("Default (84 Games)", "84 games"),
            ("Short Season (20 Games)", "20 games"),
            ("Half Season (41 Games)", "41 games"),
            ("Extended Season (100 Games)", "100 games"),
        ])
        self._len_pills.set_selected(["Default (84 Games)"])
        lay.addWidget(self._len_pills)

        # Difficulty
        lay.addWidget(self._section_label("Difficulty"))
        self._diff_pills = PillGroup([(d, d) for d in _DIFFICULTIES])
        self._diff_pills.set_selected(["Professional"])
        lay.addWidget(self._diff_pills)

        # Leagues (multi)
        lay.addWidget(self._section_label("Leagues"))
        self._league_pills = PillGroup([(lg, lg) for lg in _LEAGUES], multi=True)
        self._league_pills.set_selected(["NHL", "AHL"])
        # keep the league picker in sync with pill selection
        for _v, _b in self._league_pills._buttons.items():
            _b.toggled.connect(self._on_league_pills_changed)
        lay.addWidget(self._league_pills)

        # Sim detail per league
        lay.addWidget(self._section_label("Simulation detail"))
        self._sim_detail_box = QVBoxLayout()
        self._sim_detail_box.setSpacing(4)
        self._sim_detail_combos = {}
        sim_wrap = QWidget()
        sim_wrap.setLayout(self._sim_detail_box)
        lay.addWidget(sim_wrap)
        self._rebuild_sim_detail()

        # Options
        lay.addWidget(self._section_label("Options"))
        self._opt_fog = QCheckBox("Fog of war — unscouted players show noisy ratings")
        self._opt_fog.setChecked(True)
        self._opt_fantasy = QCheckBox("Fantasy draft — redistribute all players at startup")
        self._opt_cap = QCheckBox("Salary cap — realistic cap management ($104M)")
        self._opt_cap.setChecked(True)
        self._opt_inj = QCheckBox("Injuries — player injuries and recovery system")
        self._opt_inj.setChecked(True)
        self._opt_morale = QCheckBox("Morale system — morale and team chemistry effects")
        self._opt_morale.setChecked(True)
        for cb in (self._opt_fog, self._opt_fantasy, self._opt_cap,
                   self._opt_inj, self._opt_morale):
            cb.setStyleSheet("color: #dbe4ff; font-size: 13px;")
            lay.addWidget(cb)

        # Playoff format
        lay.addWidget(self._section_label("Playoff format"))
        self._playoff_pills = PillGroup([
            ("divisional", "Divisional", "Top 3 per division + 2 wild cards"),
            ("conference", "Conference", "Top 8 per conference, classic 1v8"),
        ])
        self._playoff_pills.set_selected(["divisional"])
        lay.addWidget(self._playoff_pills)

        lay.addStretch(1)
        return self._scroll_wrap(page)

    def _on_league_pills_changed(self):
        sel = self._league_pills.selected()
        if not sel:
            # keep at least one league
            self._league_pills.set_selected(["NHL"])
            sel = ["NHL"]
        # sync the league picker
        cur = self._league_picker.currentText()
        self._league_picker.blockSignals(True)
        self._league_picker.clear()
        self._league_picker.addItems(sel)
        idx = self._league_picker.findText(cur)
        self._league_picker.setCurrentIndex(idx if idx >= 0 else 0)
        self._league_picker.blockSignals(False)
        self._rebuild_sim_detail()
        self._populate_teams()

    def _rebuild_sim_detail(self):
        # clear
        while self._sim_detail_box.count():
            item = self._sim_detail_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._sim_detail_combos = {}
        for lg in self._league_pills.selected():
            row = QHBoxLayout()
            lbl = QLabel(lg)
            lbl.setStyleSheet("color: #9fb0d0; font-size: 13px;")
            lbl.setMinimumWidth(60)
            row.addWidget(lbl)
            combo = QComboBox()
            for val, lab in _SIM_DETAILS:
                combo.addItem(lab, val)
            dflt = _SIM_DEFAULTS.get(lg, "quick")
            combo.setCurrentIndex(
                max(0, combo.findData(dflt)))
            row.addWidget(combo, 1)
            wrap = QWidget()
            wrap.setLayout(row)
            self._sim_detail_box.addWidget(wrap)
            self._sim_detail_combos[lg] = combo

    def _on_league_changed(self):
        self._populate_teams()

    def _random_team(self):
        if self._team_combo.count():
            self._team_combo.setCurrentIndex(
                random.randrange(self._team_combo.count()))

    def _populate_teams(self):
        """Fill the team picker from the current league."""
        try:
            self._team_combo.blockSignals(True)
            self._team_combo.clear()
            league = getattr(self.game, "league", None)
            teams = getattr(league, "teams", []) if league else []
            for team in teams:
                name = getattr(team, "team_name", str(team))
                self._team_combo.addItem(name, name)
        finally:
            try:
                self._team_combo.blockSignals(False)
            except Exception:
                pass
        self._update_start_state()

    # -- TAB: Advanced Setup ----------------------------------------------
    def _make_advanced_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(8)

        head = QLabel("Advanced Configuration")
        head.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800;")
        lay.addWidget(head)
        sub = QLabel("Fine-tune your hockey management experience.")
        sub.setStyleSheet("color: #9fb0d0; font-size: 13px;")
        lay.addWidget(sub)

        lay.addWidget(self._section_label("Presets"))
        self._preset_pills = PillGroup([
            ("arcade", "🕹️ Arcade", "Fast, fun, fantasy draft, no cap"),
            ("realistic", "📊 Realistic", "Full sim, real difficulty"),
            ("challenge", "🔥 Challenge", "Maximum difficulty"),
            ("quick", "⚡ Quick", "Short season, fast"),
        ])
        for _v, _b in self._preset_pills._buttons.items():
            _b.toggled.connect(
                lambda checked, v=_v: checked and self._apply_preset(v))
        lay.addWidget(self._preset_pills)

        lay.addWidget(self._section_label("AI difficulty"))
        row = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(self._field_label("Trade difficulty"))
        self._opt_trade_diff = QComboBox()
        self._opt_trade_diff.addItems(["Very Easy", "Easy", "Realistic",
                                      "Hard", "Nearly Impossible"])
        self._opt_trade_diff.setCurrentText("Realistic")
        box.addWidget(self._opt_trade_diff)
        row.addLayout(box, 1)
        box = QVBoxLayout()
        box.addWidget(self._field_label("CPU GM intelligence"))
        self._opt_cpu_iq = QComboBox()
        self._opt_cpu_iq.addItems(["Low (Predictable)", "Medium (Balanced)",
                                  "High (Challenging)", "Maximum (Ruthless)"])
        self._opt_cpu_iq.setCurrentText("Medium (Balanced)")
        box.addWidget(self._opt_cpu_iq)
        row.addLayout(box, 1)
        lay.addLayout(row)

        lay.addWidget(self._section_label("Gameplay features"))
        self._opt_intl = QCheckBox(
            "International players — European leagues, juniors, prospects")
        self._opt_intl.setChecked(True)
        self._opt_no_pen = QCheckBox(
            "Start without cap penalties — clear real-life dead cap")
        self._opt_prog = QCheckBox(
            "Realistic progression — age curves and usage-based development")
        self._opt_prog.setChecked(True)
        self._opt_composite = QCheckBox(
            "Composite ratings — show Chance Creation, Finishing, Skating…")
        for cb in (self._opt_intl, self._opt_no_pen, self._opt_prog,
                   self._opt_composite):
            cb.setStyleSheet("color: #dbe4ff; font-size: 13px;")
            lay.addWidget(cb)

        lay.addStretch(1)
        return self._scroll_wrap(page)

    def _apply_preset(self, name):
        """Apply an advanced preset bundle (HTML preset-pills parity)."""
        if name == "arcade":
            self._opt_fantasy.setChecked(True)
            self._opt_cap.setChecked(False)
            self._diff_pills.set_selected(["Rookie"])
            self._opt_trade_diff.setCurrentText("Very Easy")
            self._opt_cpu_iq.setCurrentText("Low (Predictable)")
        elif name == "realistic":
            self._opt_fantasy.setChecked(False)
            self._opt_cap.setChecked(True)
            self._diff_pills.set_selected(["Realistic"])
            self._opt_trade_diff.setCurrentText("Realistic")
            self._opt_cpu_iq.setCurrentText("High (Challenging)")
            self._opt_fog.setChecked(True)
            self._opt_prog.setChecked(True)
        elif name == "challenge":
            self._diff_pills.set_selected(["Hall of Fame"])
            self._opt_trade_diff.setCurrentText("Nearly Impossible")
            self._opt_cpu_iq.setCurrentText("Maximum (Ruthless)")
            self._opt_cap.setChecked(True)
        elif name == "quick":
            self._len_pills.set_selected(["Short Season (20 Games)"])
            self._db_pills.set_selected(["small"])
            self._diff_pills.set_selected(["Amateur"])

    # -- TAB: Load Game ---------------------------------------------------
    def _make_load_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        head = QLabel("Load Game")
        head.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800;")
        lay.addWidget(head)
        sub = QLabel("Pick up right where you left off.")
        sub.setStyleSheet("color: #9fb0d0; font-size: 13px;")
        lay.addWidget(sub)

        self._save_list = QListWidget()
        self._save_list.setStyleSheet(
            "QListWidget { background: #141b33; border: 1px solid #2a3a5f;"
            " border-radius: 8px; color: #dbe4ff; font-size: 13px; }"
            "QListWidget::item { padding: 8px; }"
            "QListWidget::item:selected { background: #243154; }")
        self._save_list.itemDoubleClicked.connect(
            lambda item: self._load_selected_save())
        lay.addWidget(self._save_list, 1)
        self._save_rows = []

        row = QHBoxLayout()
        load_btn = QPushButton("Load Selected")
        load_btn.setObjectName("primary-btn")
        load_btn.setCursor(Qt.PointingHandCursor)
        load_btn.clicked.connect(self._load_selected_save)
        row.addWidget(load_btn)
        del_btn = QPushButton("Delete Selected")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self._delete_selected_save)
        row.addWidget(del_btn)
        imp_btn = QPushButton("Import Save")
        imp_btn.setCursor(Qt.PointingHandCursor)
        imp_btn.clicked.connect(self._import_save)
        row.addWidget(imp_btn)
        row.addStretch(1)
        lay.addLayout(row)
        return page

    def _refresh_save_list(self):
        self._save_list.clear()
        self._save_rows = []
        try:
            from .save import _save_manager
            sm = _save_manager(self.game)
            files = (sm.get_save_files() if sm else []) or []
            for f in files:
                if not isinstance(f, dict):
                    continue
                name = str(f.get("filename", ""))
                team = str(f.get("team", "") or "")
                date = str(f.get("game_date", "") or "")
                label = name
                extra = " · ".join(x for x in (team, date) if x and x != "Unknown")
                if extra:
                    label = f"{label}  ({extra})"
                self._save_list.addItem(label)
                self._save_rows.append(f)
        except Exception:
            pass
        if not self._save_rows:
            self._save_list.addItem("No saves found.")

    def _selected_save_row(self):
        idx = self._save_list.currentRow()
        if 0 <= idx < len(self._save_rows):
            return self._save_rows[idx]
        return None

    def _load_selected_save(self):
        s = self._selected_save_row()
        if not s:
            QMessageBox.information(self, "Load Game", "Select a save first.")
            return
        from .save import _save_manager, _resolve_save_id, _suppress_tk_popups
        sm = _save_manager(self.game)
        if sm is None:
            QMessageBox.warning(self, "Load Game", "Save system unavailable.")
            return
        path = _resolve_save_id(sm, s.get("filepath", "") or s.get("id", ""))
        if not path or not os.path.exists(path):
            # fall back: match by filename in saves dir
            path = None
        if not path:
            QMessageBox.warning(self, "Load Game", "Save file not found.")
            return
        ans = QMessageBox.question(
            self, "Load game",
            f'Load "{s.get("filename", "")}"?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with _suppress_tk_popups():
                ok = bool(sm.load_game(path))
        except Exception as e:
            ok = False
            err = str(e)
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            QMessageBox.warning(self, "Load Game",
                               "Load failed — the save may be from an "
                               "incompatible version.")
            return
        try:
            hook = getattr(self.game, "on_game_loaded", None)
            if callable(hook):
                hook()
        except Exception:
            pass
        self._stop_mp()
        self.main_window.refresh()
        self.main_window.show_screen("hub")

    def _delete_selected_save(self):
        s = self._selected_save_row()
        if not s:
            return
        from .save import _save_manager, _resolve_save_id, _saves_dir
        sm = _save_manager(self.game)
        path = _resolve_save_id(sm, s.get("filepath", "") or s.get("id", "")) if sm else None
        if not path or not os.path.exists(path):
            return
        ans = QMessageBox.question(
            self, "Delete save",
            f'Delete "{s.get("filename", "")}" permanently?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        try:
            os.remove(path)
        except Exception as e:
            QMessageBox.warning(self, "Delete save", f"Delete failed: {e}")
            return
        self._refresh_save_list()

    def _import_save(self):
        from .save import _save_manager, _saves_dir
        sm = _save_manager(self.game)
        if sm is None:
            QMessageBox.warning(self, "Import Save", "Save system unavailable.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import save", "",
            "Save files (*.dat *.save *.pkl *.hm);;All files (*)")
        if not path:
            return
        try:
            dest_dir = _saves_dir(sm)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(path))
            shutil.copy2(path, dest)
        except Exception as e:
            QMessageBox.warning(self, "Import Save", f"Import failed: {e}")
            return
        self._refresh_save_list()
        QMessageBox.information(self, "Import Save", "Save imported.")

    # -- TAB: Multiplayer -------------------------------------------------
    def _make_mp_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        head = QLabel("Multiplayer")
        head.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 800;")
        lay.addWidget(head)
        sub = QLabel("Play with friends over your Radmin VPN / virtual LAN network. "
                     "One player hosts the canonical game; others join and claim teams.")
        sub.setStyleSheet("color: #9fb0d0; font-size: 13px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        # Host panel
        host_box = QGroupBox("Host a Game")
        host_box.setStyleSheet(
            "QGroupBox { color: #ffffff; font-size: 15px; font-weight: 700;"
            " border: 1px solid #2a3a5f; border-radius: 8px; margin-top: 16px;"
            " padding-top: 16px; padding-left: 10px; padding-right: 10px;"
            " padding-bottom: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position:"
            " top left; left: 12px; top: 2px; padding: 0 6px;"
            " background-color: transparent; }")
        hl = QVBoxLayout(host_box)
        hl.addWidget(self._field_label("Display name"))
        self._mp_host_name = QLineEdit()
        self._mp_host_name.setMaxLength(30)
        self._mp_host_name.setPlaceholderText("Your name")
        hl.addWidget(self._mp_host_name)
        hl.addWidget(self._field_label("Port"))
        self._mp_host_port = QLineEdit(str(_MP_DEFAULT_PORT))
        self._mp_host_port.setMaxLength(5)
        hl.addWidget(self._mp_host_port)
        hint = QLabel("Friends join using your Radmin VPN IP address.")
        hint.setStyleSheet("color: #5a6584; font-size: 12px;")
        hint.setWordWrap(True)
        hl.addWidget(hint)
        host_btn = QPushButton("Host Game →")
        host_btn.setObjectName("primary-btn")
        host_btn.setCursor(Qt.PointingHandCursor)
        host_btn.clicked.connect(self._mp_host_clicked)
        hl.addWidget(host_btn)
        self._mp_host_status = QLabel("")
        self._mp_host_status.setStyleSheet("color: #9fb0d0; font-size: 12px;")
        self._mp_host_status.setWordWrap(True)
        hl.addWidget(self._mp_host_status)
        self._mp_lobby_box = QWidget()
        ll = QVBoxLayout(self._mp_lobby_box)
        ll.setContentsMargins(0, 0, 0, 0)
        lobby_head = QLabel("Lobby — connected GMs")
        lobby_head.setStyleSheet("color: #dbe4ff; font-size: 13px; font-weight: 700;")
        ll.addWidget(lobby_head)
        self._mp_lobby_list = QListWidget()
        self._mp_lobby_list.setMaximumHeight(120)
        ll.addWidget(self._mp_lobby_list)
        start_mp_btn = QPushButton("Start Multiplayer Game →")
        start_mp_btn.setObjectName("primary-btn")
        start_mp_btn.setCursor(Qt.PointingHandCursor)
        start_mp_btn.clicked.connect(self._mp_start_hosted_game)
        ll.addWidget(start_mp_btn)
        self._mp_lobby_box.setVisible(False)
        hl.addWidget(self._mp_lobby_box)
        hl.addStretch(1)
        cols.addWidget(host_box, 1)

        # Join panel
        join_box = QGroupBox("Join a Game")
        join_box.setStyleSheet(host_box.styleSheet())
        jl = QVBoxLayout(join_box)
        jl.addWidget(self._field_label("Host IP address"))
        self._mp_join_ip = QLineEdit()
        self._mp_join_ip.setPlaceholderText("e.g. 26.123.45.67")
        jl.addWidget(self._mp_join_ip)
        jl.addWidget(self._field_label("Port"))
        self._mp_join_port = QLineEdit(str(_MP_DEFAULT_PORT))
        self._mp_join_port.setMaxLength(5)
        jl.addWidget(self._mp_join_port)
        jl.addWidget(self._field_label("Your name"))
        self._mp_join_name = QLineEdit()
        self._mp_join_name.setMaxLength(30)
        self._mp_join_name.setPlaceholderText("Your name")
        jl.addWidget(self._mp_join_name)
        join_btn = QPushButton("Join Game →")
        join_btn.setObjectName("primary-btn")
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.clicked.connect(self._mp_join_clicked)
        jl.addWidget(join_btn)
        self._mp_join_status = QLabel("")
        self._mp_join_status.setStyleSheet("color: #9fb0d0; font-size: 12px;")
        self._mp_join_status.setWordWrap(True)
        jl.addWidget(self._mp_join_status)
        self._mp_claim_box = QWidget()
        cl = QVBoxLayout(self._mp_claim_box)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(QLabel("Claim your team"))
        self._mp_team_list = QListWidget()
        self._mp_team_list.setMaximumHeight(160)
        self._mp_team_list.itemDoubleClicked.connect(
            lambda item: self._mp_claim_team(item))
        cl.addWidget(self._mp_team_list)
        claim_btn = QPushButton("Claim Selected Team")
        claim_btn.setCursor(Qt.PointingHandCursor)
        claim_btn.clicked.connect(
            lambda: self._mp_claim_team(self._mp_team_list.currentItem()))
        cl.addWidget(claim_btn)
        spec_btn = QPushButton("Join as spectator instead")
        spec_btn.setCursor(Qt.PointingHandCursor)
        spec_btn.clicked.connect(self._mp_spectate)
        cl.addWidget(spec_btn)
        self._mp_claim_box.setVisible(False)
        jl.addWidget(self._mp_claim_box)
        jl.addStretch(1)
        cols.addWidget(join_box, 1)

        lay.addLayout(cols, 1)
        return self._scroll_wrap(page)

    # -- multiplayer logic ------------------------------------------------
    def _local_ips(self):
        ips = []
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None):
                ip = info[4][0]
                if ":" not in ip and not ip.startswith("127.") and ip not in ips:
                    ips.append(ip)
        except Exception:
            pass
        return ips or ["127.0.0.1"]

    def _mp_host_clicked(self):
        name = self._mp_host_name.text().strip() or "Host"
        try:
            port = int(self._mp_host_port.text().strip() or _MP_DEFAULT_PORT)
        except ValueError:
            self._mp_host_status.setText("Port must be a number.")
            return
        self._mp_pending_host = {"name": name, "port": port}
        ips = ", ".join(self._local_ips())
        self._mp_host_status.setText(
            f"Hosting on {ips}:{port}\nShare your Radmin VPN IP with friends.")
        self._mp_lobby_box.setVisible(True)
        self._mp_lobby_list.clear()
        self._mp_lobby_list.addItem("Waiting for players…")

    def _mp_start_hosted_game(self):
        """Create the career, wire the MultiplayerHost, start the league."""
        if not self._mp_pending_host:
            return
        cfg = self._mp_pending_host
        # 1) run the normal new-career flow
        if not self._do_new_career():
            return
        # 2) wire the host on the fresh game
        try:
            from multiplayer.net_host import MultiplayerHost
            from .save import _save_manager
            sm = _save_manager(self.game)
            if sm is None:
                raise RuntimeError("save system unavailable")

            def _state_provider():
                blob = gzip.compress(pickle.dumps(
                    sm.create_save_data(), protocol=pickle.HIGHEST_PROTOCOL))
                return blob, str(getattr(self.game, "current_date", "")), "host-sync"

            def _get_teams():
                try:
                    return [{"id": t.team_name, "name": t.team_name}
                            for t in self.game.league.teams]
                except Exception:
                    return []

            self._stop_mp()
            self._mp_host = MultiplayerHost(
                _state_provider, host_name=cfg["name"],
                port=cfg["port"], get_teams=_get_teams)
            self._mp_host.start()
            try:
                self._mp_host.start_game()
            except Exception:
                pass
            self._mp_timer.start(2000)
            self._mp_poll()
            QMessageBox.information(
                self, "Multiplayer",
                f"League started — welcome, Commissioner.\n"
                f"Hosting on {', '.join(self._local_ips())}:{cfg['port']}")
        except OSError as e:
            QMessageBox.warning(self, "Multiplayer",
                               f"Could not bind port {cfg['port']}: {e}")
            return
        except Exception as e:
            QMessageBox.warning(self, "Multiplayer", f"Host failed: {e}")
            return
        self.main_window.refresh()
        self.main_window.show_screen("hub")

    def _mp_join_clicked(self):
        ip = self._mp_join_ip.text().strip()
        name = self._mp_join_name.text().strip() or "Player"
        try:
            port = int(self._mp_join_port.text().strip() or _MP_DEFAULT_PORT)
        except ValueError:
            self._mp_join_status.setText("Port must be a number.")
            return
        if not ip:
            self._mp_join_status.setText("Enter the host IP address.")
            return
        try:
            from multiplayer.net_client import MultiplayerClient
            self._stop_mp()
            self._mp_client = MultiplayerClient(name)
            self._mp_client.connect(ip, port)
        except Exception as e:
            self._mp_join_status.setText(f"Failed: {e}")
            self._mp_client = None
            return
        self._mp_join_status.setText("Connected — waiting for lobby…")
        self._mp_claim_box.setVisible(True)
        self._mp_timer.start(1500)

    def _mp_claim_team(self, item):
        if item is None or self._mp_client is None:
            return
        team_id = item.data(Qt.UserRole)
        if not team_id:
            return
        try:
            self._mp_client.claim_team(team_id)
            self._mp_join_status.setText(
                "Team claimed! Waiting for host to start…")
        except Exception as e:
            self._mp_join_status.setText(f"Claim failed: {e}")

    def _mp_spectate(self):
        self._mp_join_status.setText(
            "Spectating — waiting for host to start…")

    def _mp_poll(self):
        # Host lobby
        if self._mp_host is not None:
            try:
                members = self._mp_host.get_lobby() or []
                self._mp_lobby_list.clear()
                if members:
                    for m in members:
                        nm = m.get("name", "?")
                        tm = m.get("team")
                        self._mp_lobby_list.addItem(
                            f"{nm}" + (f" — {tm}" if tm else " (no team)"))
                else:
                    self._mp_lobby_list.addItem("Waiting for players…")
            except Exception:
                pass
        # Client events
        if self._mp_client is not None:
            try:
                for etype, data in self._mp_client.poll_events():
                    self._mp_on_client_event(etype, data or {})
            except Exception:
                pass

    def _mp_on_client_event(self, etype, data):
        if etype == "welcome":
            teams = data.get("teams") or []
            taken = data.get("teams_taken") or {}
            self._mp_team_list.clear()
            for t in teams:
                tid = t.get("id") if isinstance(t, dict) else str(t)
                nm = t.get("name") if isinstance(t, dict) else str(t)
                holder = taken.get(tid)
                item = QListWidgetItem(
                    f"{nm}" + (f" — taken by {holder}" if holder else ""))
                item.setData(Qt.UserRole, tid)
                if holder:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                self._mp_team_list.addItem(item)
            self._mp_join_status.setText("Choose your team (double-click).")
        elif etype == "team_claimed":
            if data.get("manager_name") == (self._mp_client.name if self._mp_client else ""):
                self._mp_join_status.setText(
                    "Team claimed! Waiting for host to start…")
        elif etype in ("game_started", "state_sync"):
            self._mp_apply_snapshot(data.get("save_bytes"))
        elif etype == "error":
            self._mp_join_status.setText(
                f"Error: {data.get('message', 'unknown')}")
        elif etype == "disconnected":
            self._mp_join_status.setText(
                f"Disconnected: {data.get('reason', 'host closed')}")
            self._stop_mp()

    def _mp_apply_snapshot(self, save_bytes):
        if not save_bytes:
            self._mp_join_status.setText("Waiting for host sync…")
            return
        self._mp_join_status.setText("Host started — downloading game state…")
        QApplication.processEvents()
        try:
            data = pickle.loads(gzip.decompress(bytes(save_bytes)))
        except Exception as e:
            self._mp_join_status.setText(f"Sync failed: {e}")
            return
        try:
            from .save import _save_manager
            sm = _save_manager(self.game)
            if sm is None:
                raise RuntimeError("save system unavailable")
            ok = bool(sm._restore_game_state(data))
            if not ok:
                raise RuntimeError("could not apply the host's update")
            # point at the claimed club (or spectate)
            team_id = getattr(self._mp_client, "team_id", None)
            gm = self.game
            if team_id:
                for t in getattr(getattr(gm, "league", None), "teams", []) or []:
                    if str(getattr(t, "team_name", "")) == str(team_id):
                        gm.user_team = t
                        break
            try:
                hook = getattr(gm, "on_game_loaded", None)
                if callable(hook):
                    hook()
            except Exception:
                pass
        except Exception as e:
            self._mp_join_status.setText(f"Failed: {e}")
            return
        self._mp_join_status.setText("Synced — entering the league…")
        self._stop_mp()
        self.main_window.refresh()
        self.main_window.show_screen("hub")

    def _stop_mp(self):
        try:
            self._mp_timer.stop()
        except Exception:
            pass
        if self._mp_host is not None:
            try:
                self._mp_host.stop()
            except Exception:
                pass
            self._mp_host = None
        if self._mp_client is not None:
            try:
                self._mp_client.disconnect()
            except Exception:
                pass
            self._mp_client = None

    # -- config collection (HTML collectConfig parity) ----------------------
    def _collect_config(self):
        leagues = self._league_pills.selected() or ["NHL"]
        sim_detail = {}
        for lg in leagues:
            combo = self._sim_detail_combos.get(lg)
            sim_detail[lg] = (combo.currentData()
                              if combo else _SIM_DEFAULTS.get(lg, "quick"))
        team = self._team_combo.currentData()
        gm = self._gm_profile_dict()
        return {
            "team": team,
            "gm_name": gm["name"],
            "gm_profile": gm,
            "database_size": (self._db_pills.selected() or "default"),
            "leagues": leagues,
            "sim_detail": sim_detail,
            "fog_of_war": self._opt_fog.isChecked(),
            "fantasy_draft": self._opt_fantasy.isChecked(),
            "salary_cap": self._opt_cap.isChecked(),
            "injuries": self._opt_inj.isChecked(),
            "morale_system": self._opt_morale.isChecked(),
            "start_date": (self._date_pills.selected()
                           or "September 1, 2024"),
            "season_length": (self._len_pills.selected()
                              or "Default (84 Games)"),
            "difficulty": (self._diff_pills.selected() or "Professional"),
            "trade_difficulty": self._opt_trade_diff.currentText(),
            "cpu_gm_intelligence": self._opt_cpu_iq.currentText(),
            "international_players": self._opt_intl.isChecked(),
            "start_without_cap_penalties": self._opt_no_pen.isChecked(),
            "realistic_progression": self._opt_prog.isChecked(),
            "show_composite_ratings": self._opt_composite.isChecked(),
            "playoff_format": (self._playoff_pills.selected() or "divisional"),
            "user_league": self._league_picker.currentText() or "NHL",
        }

    def _build_engine_settings(self, cfg):
        """Translate the wizard config into apply_startup_settings keys,
        mirroring web_ui/bridge._do_setup_new_game."""
        _size_map = {"small": "Small", "default": "Default",
                     "medium": "Medium", "large": "Large"}
        db_size = _size_map.get(str(cfg["database_size"]).lower(), "Default")
        settings = {
            "database_size": db_size,
            "fantasy_draft": bool(cfg["fantasy_draft"]),
            "user_team": cfg["team"],
            "user_league": cfg["user_league"],
            "gm_name": cfg["gm_name"],
            "fog_of_war": bool(cfg["fog_of_war"]),
            "sim_detail": dict(cfg["sim_detail"]),
            "playoff_format": cfg["playoff_format"],
            "start_date": cfg["start_date"],
            "season_length": cfg["season_length"],
            "difficulty": cfg["difficulty"],
            "trade_difficulty": cfg["trade_difficulty"],
            "cpu_gm_intelligence": cfg["cpu_gm_intelligence"],
            "salary_cap": bool(cfg["salary_cap"]),
            "injuries": bool(cfg["injuries"]),
            "injuries_enabled": bool(cfg["injuries"]),
            "morale_system": bool(cfg["morale_system"]),
            "international_players": bool(cfg["international_players"]),
            "start_without_cap_penalties": bool(cfg["start_without_cap_penalties"]),
            "realistic_progression": bool(cfg["realistic_progression"]),
            "show_composite_ratings": bool(cfg["show_composite_ratings"]),
        }
        # League selection -> DatabaseConfig (web parity via new_game_setup).
        try:
            import new_game_setup as _ngs
            wiz = _ngs.make_config(
                mode="custom",
                database_size=str(cfg["database_size"]).lower(),
                leagues=list(cfg["leagues"]),
                sim_detail=dict(cfg["sim_detail"]),
                fog_of_war=bool(cfg["fog_of_war"]),
                gm_name=cfg["gm_name"],
                user_league=cfg["user_league"],
                user_team=cfg["team"],
                playoff_format=cfg["playoff_format"],
            )
            settings["database_config"] = _ngs.build_database_config(wiz)
            # validated values back into the settings
            settings["user_team"] = wiz["user_team"]
            settings["user_league"] = wiz["user_league"]
        except Exception as e:
            print(f"[setup] database_config build skipped: {e}")
        # GM profile object (web parity)
        try:
            from game_classes import GMProfile
            gp = cfg["gm_profile"]
            settings["gm_profile"] = GMProfile(
                name=gp.get("name") or cfg["gm_name"],
                age=int(gp.get("age") or 35),
                former_player=(gp.get("background") == "Former Player"),
                coaching_experience=(gp.get("background") == "Former Coach"),
                management_style=gp.get("management_style") or "Balanced",
            )
        except Exception:
            pass
        return settings

    # -- new-career flows --------------------------------------------------
    def _update_start_state(self, *args):
        has_team = bool(self._team_combo.currentData())
        teams_loaded = self._team_combo.count() > 0
        self._start_btn.setEnabled(has_team)
        self._quick_btn.setEnabled(teams_loaded)
        self._hint.setText(
            "" if has_team else "Select a team to start your career.")

    def _quick_start(self):
        """Randomize GM profile and team, defaults, straight in (HTML parity)."""
        self._random_gm_profile()
        self._random_team()
        cfg = self._collect_config()
        # HTML basicConfig: default database, NHL+AHL, standard options
        cfg.update({
            "database_size": "default",
            "leagues": ["NHL", "AHL"],
            "sim_detail": {"NHL": "full", "AHL": "quick"},
            "fog_of_war": True,
            "fantasy_draft": False,
            "salary_cap": True,
            "injuries": True,
            "morale_system": True,
            "start_date": "September 1, 2024",
            "season_length": "Default (84 Games)",
            "difficulty": "Professional",
            "trade_difficulty": "Realistic",
            "cpu_gm_intelligence": "Medium (Balanced)",
            "international_players": True,
            "start_without_cap_penalties": False,
            "realistic_progression": True,
            "show_composite_ratings": False,
            "playoff_format": "divisional",
        })
        # sync the visible pills to the quick-start config
        try:
            self._db_pills.set_selected(["default"])
            self._league_pills.set_selected(["NHL", "AHL"])
            self._rebuild_sim_detail()
            self._date_pills.set_selected(["September 1, 2024"])
            self._len_pills.set_selected(["Default (84 Games)"])
            self._diff_pills.set_selected(["Professional"])
            self._playoff_pills.set_selected(["divisional"])
            self._opt_fog.setChecked(True)
            self._opt_fantasy.setChecked(False)
            self._opt_cap.setChecked(True)
            self._opt_inj.setChecked(True)
            self._opt_morale.setChecked(True)
            self._opt_intl.setChecked(True)
            self._opt_no_pen.setChecked(False)
            self._opt_prog.setChecked(True)
            self._opt_composite.setChecked(False)
            self._opt_trade_diff.setCurrentText("Realistic")
            self._opt_cpu_iq.setCurrentText("Medium (Balanced)")
        except Exception:
            pass
        if not self._do_new_career(cfg):
            return
        self.main_window.refresh()
        self.main_window.show_screen("hub")

    def _start_career(self):
        """Start a new career with the wizard's options."""
        if not self._team_combo.currentData():
            QMessageBox.warning(self, "New Career", "Please select a team.")
            return
        if not self._do_new_career():
            return
        self.main_window.refresh()
        self.main_window.show_screen("hub")

    def _do_new_career(self, cfg=None):
        """Full new-game flow. Returns True on success.

        Mirrors web _do_setup_new_game: apply_startup_settings (database
        generation with the wizard's options) -> set_user_team ->
        setup_new_game (DB manager, media, schedule, camp).
        """
        cfg = cfg or self._collect_config()
        team = cfg.get("team")
        if not team:
            QMessageBox.warning(self, "New Career", "Please select a team.")
            return False
        settings = self._build_engine_settings(cfg)

        dlg = QProgressDialog("Starting…", "Cancel", 0, 100, self)
        dlg.setWindowTitle("Puck Dynasty — New Career")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        # Programmatic dialog: never auto-close/reset on reaching 100%,
        # or wasCanceled() misfires on the generation shim's final update.
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)
        _install_qt_progress_shim(dlg)
        try:
            dlg.setLabelText("Generating league database…")
            QApplication.processEvents()
            self.game.apply_startup_settings(settings)
            if dlg.wasCanceled():
                return False
            dlg.setLabelText("Setting up your team…")
            QApplication.processEvents()
            self.game.set_user_team(settings.get("user_team") or team)
            # stash the GM profile for MP display + career screens
            try:
                self.game.gm_profile = dict(cfg.get("gm_profile") or {})
                self.game.gm_name = cfg.get("gm_name") or "General Manager"
            except Exception:
                pass
            dlg.setLabelText("Starting game…")
            dlg.setValue(95)
            QApplication.processEvents()
            self.game.setup_new_game()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "New Career",
                               f"Failed to start career:\n{e}")
            return False
        finally:
            _remove_qt_progress_shim()
            try:
                dlg.close()
            except Exception:
                pass
        # sanity: the team must exist after generation
        if getattr(self.game, "user_team", None) is None:
            QMessageBox.warning(
                self, "New Career",
                "The selected team was not found after league generation.")
            return False
        return True

    # -- refresh -----------------------------------------------------------
    def refresh(self):
        """Populate team list and saves."""
        self._populate_teams()
        self._refresh_save_list()
        self._update_start_state()
        self._update_gm_preview()
