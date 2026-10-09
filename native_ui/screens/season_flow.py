"""Season Flow: automated season progression (native Qt port).

Ports season_flow_ui.py (SeasonFlowControlPanel, AutomationSettingsView,
MilestoneNotificationView) to PySide6. Calls the real
``automated_season_flow.AutomatedSeasonFlow`` engine directly -- no Flask,
no HTTP.

Native differences from the tkinter original (all deliberate):
  - The engine's ``_automation_loop`` uses tkinter ``after()``, which does
    not exist under Qt. The loop is driven here by a ``QTimer`` that calls
    the engine's ``should_auto_advance()`` / ``simulate_day()`` /
    milestone APIs directly. ``AutomatedSeasonFlow.start_automation()`` is
    never called (it would crash on ``game_manager.after``).
  - The engine's ``_show_milestone_notification`` imports tkinter's
    messagebox. Critical milestones are surfaced here with a native
    ``QDialog`` instead.
  - The auto loop respects native blockers: if ``get_continue_state()``
    reports blockers, automation stops and the blocker dialog opens
    instead of simming past decisions the user must make.
  - The single ``AutomatedSeasonFlow`` instance is cached on the main
    window so mode/speed/settings survive screen navigation.

Engine functions used (all real):
  - automated_season_flow.AutomatedSeasonFlow, AutoAdvanceMode,
    SeasonPhase, format_days_until_milestone
  - automation.update_season_phase(), get_next_milestone(),
    should_auto_advance(), _get_upcoming_user_games(),
    _check_milestone_triggers() is replicated natively (see above)
  - game.get_continue_state(), game.simulate_day(),
    game.add_news(), main_window.show_blockers()
"""

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QCheckBox, QSlider, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen

# The engine module is stdlib-only at import time (datetime/enum/dataclass),
# so this top-level import is bundling-safe. Its tkinter usage is confined
# to function bodies we never call (see module docstring).
try:
    from automated_season_flow import (
        AutomatedSeasonFlow,
        AutoAdvanceMode,
        SeasonPhase,
        format_days_until_milestone,
    )
    _ENGINE_OK = True
    _ENGINE_ERR = ""
except Exception as e:  # pragma: no cover - defensive
    AutomatedSeasonFlow = None
    AutoAdvanceMode = None
    SeasonPhase = None
    format_days_until_milestone = None
    _ENGINE_OK = False
    _ENGINE_ERR = str(e)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# Phase -> native screen name for the milestone dialog's "open" button.
_PHASE_SCREENS = {
    "Trade Deadline Period": "deadline",
    "Playoffs": "playoffs",
    "Playoff Push": "playoffs",
    "Entry Draft": "draft_central",
    "Draft Lottery": "draft_central",
    "Free Agency": "free_agents",
    "Pre-Season": "schedule",
    "Regular Season": "schedule",
    "Off-Season": "schedule",
}

_PHASE_ICONS = {
    "Trade Deadline Period": "\u23f0",
    "Playoffs": "\U0001f3d2",
    "Entry Draft": "\U0001f4cb",
    "Free Agency": "\U0001f4b0",
}


class MilestoneDialog(QDialog):
    """Native milestone notification (ports MilestoneNotificationView)."""

    def __init__(self, parent, milestone, main_window):
        super().__init__(parent)
        self._milestone = milestone
        self._main_window = main_window
        phase_value = _safe(lambda: milestone.phase.value, "")
        self.setWindowTitle(f"Milestone: {milestone.name}")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        icon = QLabel(_PHASE_ICONS.get(phase_value, "\U0001f3af"))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 40px;")
        layout.addWidget(icon)

        title = QLabel(milestone.name)
        title.setObjectName("dialog-title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        date_lbl = QLabel(_safe(
            lambda: milestone.date.strftime("%B %d, %Y"), ""))
        date_lbl.setAlignment(Qt.AlignCenter)
        date_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        layout.addWidget(date_lbl)

        desc = QLabel(milestone.description or "")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        phase_row = QLabel(f"Season phase: {phase_value}")
        phase_row.setAlignment(Qt.AlignCenter)
        phase_row.setStyleSheet("color: #9aa4b8;")
        layout.addWidget(phase_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.button(QDialogButtonBox.Ok).setText("Continue")
        btns.accepted.connect(self.accept)
        if _safe(lambda: milestone.is_critical, False):
            target = _PHASE_SCREENS.get(phase_value)
            if target:
                open_btn = QPushButton("Open Related Screen")
                open_btn.clicked.connect(
                    lambda: self._open_related(target))
                btns.addButton(open_btn, QDialogButtonBox.ActionRole)
        layout.addWidget(btns)

    def _open_related(self, screen_name):
        try:
            self.accept()
            self._main_window.show_screen(screen_name)
        except Exception as e:
            print(f"[season_flow] open related screen failed: {e}")


class AutomationSettingsDialog(QDialog):
    """Native automation settings (ports AutomationSettingsView)."""

    def __init__(self, parent, automation):
        super().__init__(parent)
        self._automation = automation
        self.setWindowTitle("Automation Settings")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- game simulation ---
        sim_box = QGroupBox("Game Simulation")
        sim_form = QFormLayout(sim_box)
        s = automation.settings
        self._sim_away = QCheckBox("Simulate away games automatically")
        self._sim_away.setChecked(bool(s.simulate_away_games))
        self._viewer_home = QCheckBox("Show game viewer for home games")
        self._viewer_home.setChecked(bool(s.show_game_viewer_for_home))
        self._viewer_away = QCheckBox("Show game viewer for away games")
        self._viewer_away.setChecked(bool(s.show_game_viewer_for_away))
        for cb in (self._sim_away, self._viewer_home, self._viewer_away):
            sim_form.addRow(cb)
        layout.addWidget(sim_box)

        # --- automation behavior ---
        beh_box = QGroupBox("Automation Behavior")
        beh_form = QFormLayout(beh_box)
        self._pause_milestones = QCheckBox("Pause at important milestones")
        self._pause_milestones.setChecked(bool(s.pause_at_milestones))
        self._pause_games = QCheckBox("Pause at user team games")
        self._pause_games.setChecked(bool(s.pause_at_user_games))
        self._skip_offseason = QCheckBox("Automatically skip off-season")
        self._skip_offseason.setChecked(bool(s.auto_skip_offseason))
        for cb in (self._pause_milestones, self._pause_games,
                   self._skip_offseason):
            beh_form.addRow(cb)
        layout.addWidget(beh_box)

        # --- upcoming milestones (read-only) ---
        ms_box = QGroupBox("Upcoming Milestones")
        ms_layout = QVBoxLayout(ms_box)
        self._ms_list = QListWidget()
        self._ms_list.setMaximumHeight(180)
        try:
            current = automation.game_manager.current_date
            upcoming = [m for m in automation.milestones
                        if m.date > current][:10]
            for m in upcoming:
                days = (m.date - current).days
                self._ms_list.addItem(
                    f"{m.date.strftime('%b %d')}  \u2014  {m.name}  "
                    f"({days} day{'s' if days != 1 else ''})")
        except Exception as e:
            self._ms_list.addItem(f"Could not load milestones: {e}")
        ms_layout.addWidget(self._ms_list)
        layout.addWidget(ms_box)

        btns = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        try:
            s = self._automation.settings
            s.simulate_away_games = self._sim_away.isChecked()
            s.show_game_viewer_for_home = self._viewer_home.isChecked()
            s.show_game_viewer_for_away = self._viewer_away.isChecked()
            s.pause_at_milestones = self._pause_milestones.isChecked()
            s.pause_at_user_games = self._pause_games.isChecked()
            s.auto_skip_offseason = self._skip_offseason.isChecked()
        except Exception as e:
            print(f"[season_flow] save settings failed: {e}")
        self.accept()


class SeasonFlowScreen(BaseScreen):
    """Automated season progression control panel (native Qt port)."""
    title = "Season Flow"

    # QTimer tick drives one automation step; delay recomputed from speed.
    _MIN_DELAY_MS = 100

    def _build_body(self):
        if not _ENGINE_OK:
            err = QLabel(
                "Season automation is unavailable: "
                f"could not load automated_season_flow ({_ENGINE_ERR})")
            err.setWordWrap(True)
            self._layout.addWidget(err)
            self._layout.addStretch()
            self._automation = None
            return
        if self.game is None or _safe(lambda: self.game.league) is None:
            msg = QLabel("Start or load a career to use automated season flow.")
            msg.setStyleSheet("color: #9aa4b8; font-size: 14px;")
            msg.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(msg)
            self._layout.addStretch()
            self._automation = None
            return

        self._automation = self._get_automation()

        # ---- season status ----
        status_box = QGroupBox("Season Status")
        status_form = QFormLayout(status_box)
        self._phase_lbl = QLabel("\u2014")
        self._milestone_lbl = QLabel("\u2014")
        self._milestone_lbl.setWordWrap(True)
        status_form.addRow("Current phase:", self._phase_lbl)
        status_form.addRow("Next milestone:", self._milestone_lbl)
        self._layout.addWidget(status_box)

        # ---- automation controls ----
        ctrl_box = QGroupBox("Automation Controls")
        ctrl_layout = QVBoxLayout(ctrl_box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._modes = list(AutoAdvanceMode)
        for m in self._modes:
            self._mode_combo.addItem(m.value)
        self._mode_combo.setCurrentText(
            self._automation.settings.mode.value)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_change)
        mode_row.addWidget(self._mode_combo, 1)
        ctrl_layout.addLayout(mode_row)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 100)  # 0.1x .. 10.0x
        self._speed_slider.setValue(
            max(1, min(100, int(self._automation.settings.days_per_second * 10))))
        self._speed_slider.valueChanged.connect(self._on_speed_change)
        speed_row.addWidget(self._speed_slider, 1)
        self._speed_lbl = QLabel()
        self._update_speed_label()
        speed_row.addWidget(self._speed_lbl)
        ctrl_layout.addLayout(speed_row)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Automation")
        self._start_btn.setObjectName("primary-btn")
        self._start_btn.clicked.connect(self._start_automation)
        self._stop_btn = QPushButton("\u23f9 Stop Automation")
        self._stop_btn.clicked.connect(self._stop_automation)
        self._settings_btn = QPushButton("Settings")
        self._settings_btn.clicked.connect(self._open_settings)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._settings_btn)
        ctrl_layout.addLayout(btn_row)
        self._layout.addWidget(ctrl_box)

        # ---- quick actions ----
        quick_box = QGroupBox("Quick Actions")
        quick_row = QHBoxLayout(quick_box)
        for label, handler in (
            ("Next Game", self._advance_to_next_game),
            ("Next Milestone", self._advance_to_milestone),
            ("Skip Week", lambda: self._advance_days(7)),
            ("Skip Month", lambda: self._advance_days(30)),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            quick_row.addWidget(btn)
        self._layout.addWidget(quick_box)

        # ---- automation timer (drives the loop; see module docstring) ----
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._automation_tick)
        self._running = False

        self._layout.addStretch()
        self.refresh()

    # ------------------------------------------------------------------
    # automation instance (cached on the main window for persistence)
    # ------------------------------------------------------------------
    def _get_automation(self):
        auto = getattr(self.main_window, "_season_flow_automation", None)
        if auto is None:
            try:
                auto = AutomatedSeasonFlow(self.game)
            except Exception as e:
                print(f"[season_flow] automation init failed: {e}")
                return None
            try:
                self.main_window._season_flow_automation = auto
            except Exception:
                pass
        return auto

    # ------------------------------------------------------------------
    # display
    # ------------------------------------------------------------------
    def refresh(self):
        if not getattr(self, "_automation", None):
            return
        try:
            phase = self._automation.update_season_phase()
            self._phase_lbl.setText(
                _safe(lambda: phase.value, "Unknown"))
            nxt = self._automation.get_next_milestone()
            if nxt and format_days_until_milestone:
                days_txt = format_days_until_milestone(
                    nxt, self.game.current_date)
                self._milestone_lbl.setText(f"{nxt.name} \u2014 {days_txt}")
            else:
                self._milestone_lbl.setText("No upcoming milestones")
            running = self._running
            self._start_btn.setEnabled(not running)
            self._stop_btn.setEnabled(running)
            self._mode_combo.setEnabled(not running)
        except Exception as e:
            print(f"[season_flow] refresh failed: {e}")

    # ------------------------------------------------------------------
    # controls
    # ------------------------------------------------------------------
    def _on_mode_change(self, idx):
        try:
            if 0 <= idx < len(self._modes):
                self._automation.settings.mode = self._modes[idx]
        except Exception as e:
            print(f"[season_flow] mode change failed: {e}")

    def _on_speed_change(self, _value):
        try:
            self._automation.settings.days_per_second = (
                self._speed_slider.value() / 10.0)
            self._update_speed_label()
            if self._running:
                self._timer.setInterval(self._tick_delay_ms())
        except Exception as e:
            print(f"[season_flow] speed change failed: {e}")

    def _update_speed_label(self):
        self._speed_lbl.setText(
            f"{self._speed_slider.value() / 10.0:.1f}x")

    def _tick_delay_ms(self):
        speed = _safe(
            lambda: self._automation.settings.days_per_second, 1.0) or 1.0
        return max(self._MIN_DELAY_MS, int(1000 / speed))

    def _start_automation(self):
        if self._running or not self._automation:
            return
        self._running = True
        try:
            self._automation.automation_active = True
        except Exception:
            pass
        self._timer.start(self._tick_delay_ms())
        self.refresh()

    def _stop_automation(self):
        self._running = False
        self._timer.stop()
        try:
            self._automation.automation_active = False
        except Exception:
            pass
        self.refresh()

    def _open_settings(self):
        try:
            dlg = AutomationSettingsDialog(self, self._automation)
            dlg.exec()
            self.refresh()
        except Exception as e:
            print(f"[season_flow] settings dialog failed: {e}")

    # ------------------------------------------------------------------
    # automation tick (native replacement for the engine's tkinter loop)
    # ------------------------------------------------------------------
    def _automation_tick(self):
        """One automation step, driven by QTimer."""
        auto = self._automation
        if not self._running or auto is None:
            return
        try:
            if not _safe(auto.should_auto_advance, False)():
                return
            # Native improvement: never sim past blockers the user must
            # resolve -- stop and surface them instead.
            _label, blockers = _safe(
                lambda: self.game.get_continue_state(), (None, []))
            if blockers:
                self._stop_automation()
                try:
                    self.main_window.show_blockers(blockers)
                except Exception as e:
                    print(f"[season_flow] show_blockers failed: {e}")
                return
            _bulk = getattr(self.game, "_bulk_simming", None)
            try:
                if _bulk is not None:
                    self.game._bulk_simming = True
                self.game.simulate_day()
            finally:
                if _bulk is not None:
                    try:
                        self.game._bulk_simming = False
                    except Exception:
                        pass
            _safe(auto.update_season_phase)
            self._check_milestone_triggers()
            self.refresh()
            # Keep the hub/dashboard behind us fresh.
            try:
                hub = getattr(self.main_window, "hub", None)
                if hub is not None and hasattr(hub, "refresh"):
                    hub.refresh(self.game)
            except Exception:
                pass
        except Exception as e:
            print(f"[season_flow] automation tick failed: {e}")
            self._stop_automation()

    def _check_milestone_triggers(self):
        """Native milestone trigger check.

        Replicates ``AutomatedSeasonFlow._check_milestone_triggers`` but
        surfaces critical milestones with a native dialog instead of the
        engine's tkinter messagebox (which cannot run under Qt).
        """
        auto = self._automation
        try:
            current = self.game.current_date
        except Exception:
            return
        for m in list(getattr(auto, "milestones", [])):
            try:
                if m.date != current:
                    continue
                print(f"[season_flow] milestone: {m.name}")
                if callable(getattr(m, "action", None)):
                    try:
                        m.action()
                    except Exception as e:
                        print(f"[season_flow] milestone action failed: {e}")
                try:
                    self.game.add_news(f"Milestone: {m.name} -- {m.description}")
                except Exception:
                    pass
                if _safe(lambda: m.is_critical, False) and self._running:
                    self._stop_automation()
                    try:
                        MilestoneDialog(self, m, self.main_window).exec()
                    except Exception as e:
                        print(f"[season_flow] milestone dialog failed: {e}")
            except Exception as e:
                print(f"[season_flow] milestone trigger failed: {e}")

    # ------------------------------------------------------------------
    # quick actions
    # ------------------------------------------------------------------
    def _advance_days(self, days):
        if not self._automation:
            return
        try:
            _label, blockers = self.game.get_continue_state()
            if blockers:
                self.main_window.show_blockers(blockers)
                return
            _bulk = getattr(self.game, "_bulk_simming", None)
            try:
                if _bulk is not None:
                    self.game._bulk_simming = True
                for _ in range(days):
                    self.game.simulate_day()
            finally:
                if _bulk is not None:
                    try:
                        self.game._bulk_simming = False
                    except Exception:
                        pass
            self.refresh()
            try:
                hub = getattr(self.main_window, "hub", None)
                if hub is not None and hasattr(hub, "refresh"):
                    hub.refresh(self.game)
            except Exception:
                pass
            QMessageBox.information(
                self, "Advanced",
                f"Advanced {days} day{'s' if days != 1 else ''}.")
        except Exception as e:
            print(f"[season_flow] advance days failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to advance: {e}")

    def _advance_to_next_game(self):
        try:
            upcoming = self._automation._get_upcoming_user_games(30)
            if not upcoming:
                QMessageBox.information(
                    self, "No Games",
                    "No upcoming user team games found in the next 30 days.")
                return
            game = upcoming[0]
            if isinstance(game, dict):
                target = game.get("date")
            else:
                target = game[0]
            days = (target - self.game.current_date).days
            if days > 0:
                self._advance_days(days)
            else:
                QMessageBox.information(
                    self, "Next Game", "The next user game is today.")
        except Exception as e:
            print(f"[season_flow] advance to next game failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed: {e}")

    def _advance_to_milestone(self):
        try:
            nxt = self._automation.get_next_milestone()
            if not nxt:
                QMessageBox.information(
                    self, "No Milestones", "No upcoming milestones found.")
                return
            days = (nxt.date - self.game.current_date).days
            if days > 0:
                self._advance_days(days)
            else:
                QMessageBox.information(
                    self, "Milestone", f"{nxt.name} is today.")
        except Exception as e:
            print(f"[season_flow] advance to milestone failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed: {e}")
