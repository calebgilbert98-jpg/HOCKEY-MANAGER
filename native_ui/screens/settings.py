"""Settings screen: schema-driven, fully writable -- web parity.

Replicates web_ui/screens/settings.py:
- 5 tabs: Game Results, Interface, Simulation, Notifications, Career
- Field schema drives widget types: bool/emailbool -> switch buttons,
  select -> dropdowns, multiselect -> multi-select lists, with hints
- Every setting writable; each change saves immediately with
  "Saving.../Saved" transient feedback
- Writes are validated, persisted to settings.json, then read back and
  verified (write only counts if the game's loader returns the new value)
- Game Day card: watch-mode segmented control (Watch games / Quick sim all)

Settings backend: the game's own loader (settings_window.load_settings,
merged over built-in defaults) persisted to the same settings.json the
desktop reads. settings_window imports customtkinter, which is not
installed in a pure-Qt runtime, so the loader is resolved lazily: if
settings_window is importable its own loader + path are used (the exact
web behavior); otherwise a local copy of the same defaults + merge logic
reads/writes the same settings.json. Either way settings.json remains the
single source of truth shared with the desktop game.
"""
import json
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QComboBox, QListWidget, QLineEdit, QButtonGroup, QScrollArea,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen


# ----------------------------------------------------------------------
# Field schema (mirrors web_ui/screens/settings.py _FIELDS / _TAB_TITLES)
# widget: "bool" | "emailbool" | "select" | "text" | "multiselect"
# ----------------------------------------------------------------------
_TAB_TITLES = {
    "game_results": "Game Results",
    "ui_preferences": "Interface",
    "simulation": "Simulation",
    "notifications": "Notifications",
    "career": "Career",
}

_FIELDS = {
    "game_results": [
        ("Show only my team's games by default", "show_user_team_only",
         "bool", None, ""),
        ("Default leagues to display", "default_leagues", "multiselect",
         ["National Hockey League", "American Hockey League"], ""),
        ("Maximum games to display", "max_games_display", "select",
         ["25", "50", "100", "200", "All"], "Recommended: 50 for performance"),
        ("Maximum news items to display", "max_news_display", "select",
         ["5", "10", "20", "50", "All"], ""),
        ("Default news categories to display", "default_news_categories",
         "multiselect",
         ["Team News", "League News", "Trades", "Injuries", "Contracts",
          "Draft"], ""),
    ],
    "ui_preferences": [
        ("Theme", "theme", "select", ["Dark (Current)"], ""),
        ("Font size", "font_size", "select",
         ["Compact", "Small", "Default", "Large", "Extra Large"],
         "Applies instantly to most windows."),
        ("Automatically close settings after saving", "auto_close_settings",
         "bool", None, ""),
        ("Remember window positions and sizes", "remember_window_positions",
         "bool", None, ""),
        ("Auto-fit text size to window size", "auto_fit_ui", "bool", None, ""),
    ],
    "simulation": [
        ("Auto-continue through non-game days", "auto_continue_non_game_days",
         "bool", None, "Drives the hub Continue flow."),
        ("Always show daily results window", "always_show_daily_results",
         "bool", None, "Show the daily results after each advance."),
        ("Use visual game viewer for my team's games", "use_game_viewer",
         "bool", None, ""),
        ("Game viewer mode", "game_viewer_mode", "select",
         ["Full Game", "Highlights Only", "Fast Forward"], ""),
        ("Draft class quality", "draft_class_quality", "select",
         ["Weak", "Normal", "Strong", "Generational"],
         "Applies to future draft classes."),
        ("Scoring level", "scoring_level", "select",
         ["Low (Current)", "Medium (NHL Baseline)", "High (Arcade)"],
         "Goals per game: ~5.5 / ~6.0 / 7+"),
    ],
    "notifications": [
        ("Email: Trade Offers", "email_Trade Offers", "emailbool", None, ""),
        ("Email: Contract Expiring Soon",
         "email_Contract Expiring Soon", "emailbool", None, ""),
        ("Email: Injury Reports", "email_Injury Reports", "emailbool", None, ""),
        ("Email: Player Milestones", "email_Player Milestones", "emailbool",
         None, ""),
        ("Email: League News", "email_League News", "emailbool", None, ""),
        ("Email: Draft Updates", "email_Draft Updates", "emailbool", None, ""),
        ("Enable sound effects", "enable_sounds", "bool", None, ""),
        ("Sound volume", "sound_volume", "select",
         ["Off", "Low", "Medium", "High"], ""),
    ],
    "career": [
        ("Board can sack the GM (job is on the line)", "gm_can_be_sacked",
         "bool", None,
         "If off, your job is safe no matter what -- board confidence "
         "still affects budgets and morale."),
    ],
}


# ----------------------------------------------------------------------
# Watch mode (native equivalent of web_ui.bridge._watch_mode)
# ----------------------------------------------------------------------
_watch_mode = "quick"


def get_watch_mode():
    """Current game-day mode: 'watch' or 'quick'. Hub/continue reads this."""
    return _watch_mode


def set_watch_mode(mode):
    global _watch_mode
    if mode in ("watch", "quick"):
        _watch_mode = mode


# ----------------------------------------------------------------------
# Settings backend: the game's own loader when available, local mirror
# of the same defaults otherwise. settings.json stays shared.
# ----------------------------------------------------------------------

def _settings_dir():
    """Directory holding settings.json (repo root, same as desktop)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


def _local_defaults():
    """Mirror of settings_window.default_settings (used only when
    settings_window itself can't be imported)."""
    return {
        'game_results': {
            'show_user_team_only': True,
            'default_leagues': ['National Hockey League'],
            'max_games_display': '50',
            'max_news_display': '10',
            'default_news_categories': ['Team News', 'League News',
                                        'Trades', 'Injuries'],
        },
        'ui_preferences': {
            'theme': 'Dark (Current)',
            'font_size': 'Default',
            'auto_close_settings': False,
            'remember_window_positions': True,
        },
        'simulation': {
            'simulation_speed': 'Fast (Current)',
            'auto_continue_non_game_days': False,
            'always_show_daily_results': True,
            'use_game_viewer': False,
            'game_viewer_mode': 'Full Game',
            'draft_class_quality': 'Normal',
            'scoring_level': 'Low (Current)',
        },
        'notifications': {
            'email_notifications': {
                'Trade Offers': True,
                'Contract Expiring Soon': True,
                'Injury Reports': True,
                'Player Milestones': False,
                'League News': False,
                'Draft Updates': True,
            },
            'enable_sounds': True,
            'sound_volume': 'Medium',
        },
        'career': {
            'gm_can_be_sacked': True,
        },
    }


def _local_merge(defaults, loaded):
    for key, value in loaded.items():
        if key in defaults:
            if isinstance(value, dict) and isinstance(defaults[key], dict):
                _local_merge(defaults[key], value)
            else:
                defaults[key] = value


def _loader():
    """Return (load_settings_fn, settings_path). Prefers the game's own
    settings_window module; falls back to the local mirror. Never raises."""
    try:
        import settings_window as sw
        path = os.path.join(os.path.dirname(os.path.abspath(sw.__file__)),
                            "settings.json")
        return sw.load_settings, path
    except Exception:
        path = os.path.join(_settings_dir(), "settings.json")

        def _load(p=None):
            settings = _local_defaults()
            try:
                with open(p or path, "r") as f:
                    _local_merge(settings, json.load(f))
            except Exception:
                pass
            return settings

        return _load, path


def _read_settings():
    loader, _path = _loader()
    try:
        return loader() or {}
    except Exception:
        return {}


def _field_value(tab, key, settings):
    sec = settings.get(tab, {}) if isinstance(settings, dict) else {}
    if key.startswith("email_"):
        emails = (sec.get("email_notifications", {}) or {})
        return bool(emails.get(key[len("email_"):], False))
    return sec.get(key)


def _validate(tab, key, value):
    """Mirror of web's _validate. Returns (ok, coerced, error)."""
    fields = {f[1]: f for f in _FIELDS.get(tab, [])}
    if key not in fields:
        return False, None, f"unknown setting {tab}.{key}"
    label, _k, widget, options, _hint = fields[key]
    if widget in ("bool", "emailbool"):
        if isinstance(value, bool):
            return True, value, ""
        if isinstance(value, str) and value.lower() in ("true", "1", "on"):
            return True, True, ""
        if isinstance(value, str) and value.lower() in ("false", "0", "off"):
            return True, False, ""
        return False, None, f"{label}: expected true/false"
    if widget == "select":
        v = str(value)
        if options and v not in options:
            return False, None, (f"{label}: {v!r} not one of "
                                 f"{', '.join(options)}")
        return True, v, ""
    if widget == "multiselect":
        if not isinstance(value, list):
            return False, None, f"{label}: expected a list"
        vals = [str(x) for x in value]
        bad = [x for x in vals if x not in (options or [])]
        if bad:
            return False, None, f"{label}: invalid choices {bad}"
        return True, vals, ""
    if widget == "text":
        return True, str(value), ""
    return False, None, f"{label}: unsupported widget {widget}"


def set_setting(tab, key, value):
    """Write one setting: validate, persist to settings.json, read back
    through the loader and verify the value stuck. Returns (ok, message)."""
    ok, coerced, err = _validate(tab, key, value)
    if not ok:
        return False, err
    loader, path = _loader()
    try:
        settings = loader() or {}
    except Exception as e:
        return False, f"could not load settings: {e}"
    settings.setdefault(tab, {})
    if key.startswith("email_"):
        settings[tab].setdefault("email_notifications", {})
        settings[tab]["email_notifications"][key[len("email_"):]] = coerced
    else:
        settings[tab][key] = coerced
    try:
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        return False, f"could not save settings.json: {e}"
    try:
        reloaded = loader() or {}
        back = _field_value(tab, key, reloaded)
        if back != coerced:
            return False, (f"write did not stick: read back {back!r}, "
                           f"expected {coerced!r}")
    except Exception as e:
        return False, f"read-back failed: {e}"
    return True, "saved"


# ----------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------

class SettingsScreen(BaseScreen):
    title = "Settings"

    def _build_body(self):
        note = QLabel("Changes save to settings.json -- the same file the "
                      "desktop game reads.")
        note.setStyleSheet("color: #8a94a8; font-size: 12px;")
        self._layout.addWidget(note)

        self._tabs = QTabWidget()
        self._tab_layouts = {}  # tab_id -> QVBoxLayout holding the fields
        for tab_id, tab_title in _TAB_TITLES.items():
            page, layout = self._make_tab_page(tab_id)
            self._tabs.addTab(page, tab_title)
            self._tab_layouts[tab_id] = layout
        self._layout.addWidget(self._tabs, 1)

        # --- Game Day card: watch-mode segmented control (web parity) ---
        gd = QFrame()
        gd.setObjectName("tile")
        gl = QVBoxLayout(gd)
        gl.addWidget(self._section_label("GAME DAY"))
        row = QHBoxLayout()
        lab = QLabel("How to handle games")
        lab.setStyleSheet("font-weight: 700;")
        hint = QLabel("Watch opens the live visualizer on game days. "
                      "Quick sim resolves them instantly.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a94a8; font-size: 12px;")
        lab_col = QVBoxLayout()
        lab_col.addWidget(lab)
        lab_col.addWidget(hint)
        row.addLayout(lab_col, 1)

        seg = QHBoxLayout()
        seg.setSpacing(0)
        self._watch_group = QButtonGroup(self)
        self._watch_group.setExclusive(True)
        self._watch_btn = QPushButton("Watch games")
        self._quick_btn = QPushButton("Quick sim all")
        for i, btn in enumerate((self._watch_btn, self._quick_btn)):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { padding: 10px 22px; border: none; "
                "background-color: #162032; color: #9aa4b8; "
                "font-weight: 800; font-size: 13px; }"
                "QPushButton:checked { background-color: #3B82F6; "
                "color: #ffffff; }"
                "QPushButton:hover { color: #ffffff; }")
            self._watch_group.addButton(btn, i)
            seg.addWidget(btn)
        self._watch_btn.toggled.connect(
            lambda checked: checked and self._set_watch("watch"))
        self._quick_btn.toggled.connect(
            lambda checked: checked and self._set_watch("quick"))
        row.addLayout(seg)
        gl.addLayout(row)
        self._layout.addWidget(gd)

        # --- transient save feedback (web #settings-save-state parity) ---
        self._save_state = QLabel("")
        self._save_state.setStyleSheet("color: #8a94a8; font-size: 12px;")
        self._layout.addWidget(self._save_state)
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(
            lambda: self._save_state.setText(""))

        self.refresh()

    def _section_label(self, text):
        lab = QLabel(text)
        lab.setObjectName("section-header")
        return lab

    def _make_tab_page(self, tab_id):
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(14)
        outer_layout.addWidget(scroll)
        scroll.setWidget(inner)
        return outer, layout

    def _clear_tab(self, tab_id):
        layout = self._tab_layouts[tab_id]
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def refresh(self):
        """Rebuild every tab from the loader (fresh values on navigation)."""
        settings = _read_settings()
        for tab_id, _title in _TAB_TITLES.items():
            self._clear_tab(tab_id)
            layout = self._tab_layouts[tab_id]
            for label, key, widget, options, hint in _FIELDS.get(tab_id, []):
                value = _field_value(tab_id, key, settings)
                layout.addWidget(
                    self._make_field_row(tab_id, label, key, widget,
                                         options, hint, value))
            layout.addStretch()
        # sync watch-mode buttons without firing toggles
        for btn in (self._watch_btn, self._quick_btn):
            btn.blockSignals(True)
        if get_watch_mode() == "watch":
            self._watch_btn.setChecked(True)
        else:
            self._quick_btn.setChecked(True)
        for btn in (self._watch_btn, self._quick_btn):
            btn.blockSignals(False)

    # -- fields -------------------------------------------------------
    def _make_field_row(self, tab_id, label, key, widget, options, hint,
                        value):
        frame = QFrame()
        frame.setObjectName("tile")
        row = QHBoxLayout(frame)

        lab_col = QVBoxLayout()
        name = QLabel(label)
        name.setWordWrap(True)
        name.setStyleSheet("font-weight: 700;")
        lab_col.addWidget(name)
        if hint:
            h = QLabel(hint)
            h.setWordWrap(True)
            h.setStyleSheet("color: #8a94a8; font-size: 12px;")
            lab_col.addWidget(h)
        row.addLayout(lab_col, 1)

        ctl_holder = QHBoxLayout()
        if widget in ("bool", "emailbool"):
            tgl = QPushButton()
            tgl.setCheckable(True)
            tgl.setObjectName("set-toggle")
            tgl.setCursor(Qt.PointingHandCursor)
            self._paint_toggle(tgl, bool(value))
            tgl.toggled.connect(
                lambda checked, k=key, t=tab_id, b=tgl:
                    self._on_setting_changed(t, k, bool(checked), b))
            ctl_holder.addWidget(tgl)
        elif widget == "multiselect":
            lst = QListWidget()
            lst.setSelectionMode(QAbstractItemView.MultiSelection)
            lst.setMaximumHeight(110)
            cur = set(value or [])
            for opt in options or []:
                lst.addItem(opt)
                if opt in cur:
                    lst.item(lst.count() - 1).setSelected(True)
            lst.itemSelectionChanged.connect(
                lambda t=tab_id, k=key, l=lst:
                    self._on_setting_changed(
                        t, k, [it.text() for it in l.selectedItems()], l))
            ctl_holder.addWidget(lst)
        elif widget == "text":
            edit = QLineEdit(str(value or ""))
            edit.editingFinished.connect(
                lambda t=tab_id, k=key, e=edit:
                    self._on_setting_changed(t, k, e.text(), e))
            ctl_holder.addWidget(edit)
        else:  # select
            combo = QComboBox()
            for opt in options or []:
                combo.addItem(opt)
            idx = combo.findText(str(value))
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentTextChanged.connect(
                lambda text, t=tab_id, k=key, c=combo:
                    self._on_setting_changed(t, k, text, c))
            ctl_holder.addWidget(combo)
        row.addLayout(ctl_holder)
        return frame

    @staticmethod
    def _paint_toggle(btn, on):
        btn.setChecked(on)
        btn.setText("On" if on else "Off")
        btn.setStyleSheet(
            "QPushButton#set-toggle { min-width: 84px; padding: 8px 0; "
            "border-radius: 6px; font-weight: 800; "
            "background-color: #162032; color: #9aa4b8; border: none; }"
            "QPushButton#set-toggle:checked { background-color: #3B82F6; "
            "color: #ffffff; }"
            "QPushButton#set-toggle:hover { color: #ffffff; }")

    def _set_watch(self, mode):
        set_watch_mode(mode)
        self._save_state.setText("Saved ✓")
        self._clear_timer.start(2000)

    def _on_setting_changed(self, tab_id, key, value, control):
        """Immediate write with Saving.../Saved feedback (web parity)."""
        self._save_state.setText("Saving…")
        ok, msg = set_setting(tab_id, key, value)
        if ok:
            self._paint_back(tab_id, key, control)
            self._save_state.setText("Saved ✓")
            self._clear_timer.start(2000)
        else:
            self._save_state.setText(f"Save failed: {msg}")
            # restore the previous value so the control shows the truth
            back = _field_value(tab_id, key, _read_settings())
            self._restore_control(tab_id, key, control, back)

    def _paint_back(self, tab_id, key, control):
        """Repaint the control from the verified loader value."""
        back = _field_value(tab_id, key, _read_settings())
        self._restore_control(tab_id, key, control, back)

    def _restore_control(self, tab_id, key, control, value):
        fields = {f[1]: f for f in _FIELDS.get(tab_id, [])}
        widget = fields.get(key, (None, None, "select", None, None))[2]
        if isinstance(control, QPushButton) and widget in ("bool",
                                                          "emailbool"):
            control.blockSignals(True)
            self._paint_toggle(control, bool(value))
            control.blockSignals(False)
        elif isinstance(control, QComboBox):
            control.blockSignals(True)
            idx = control.findText(str(value))
            if idx >= 0:
                control.setCurrentIndex(idx)
            control.blockSignals(False)
        elif isinstance(control, QListWidget):
            control.blockSignals(True)
            cur = set(value or [])
            for i in range(control.count()):
                control.item(i).setSelected(control.item(i).text() in cur)
            control.blockSignals(False)
        elif isinstance(control, QLineEdit):
            control.blockSignals(True)
            control.setText(str(value or ""))
            control.blockSignals(False)
