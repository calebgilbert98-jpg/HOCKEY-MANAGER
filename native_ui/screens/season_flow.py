"""Season Flow: automated season progression (native Qt port).

Ports season_flow_ui.py (SeasonFlowControlPanel, AutomationSettingsView,
MilestoneNotificationView) to PySide6. Calls the real
``automated_season_flow.AutomatedSeasonFlow`` engine directly -- no Flask,
no HTTP.

Native differences from the tkinter original (all deliberate):
  - The engine's ``_automation_loop`` uses tkinter ``after()``, which does
    not exist under Qt. The loop is driven here by a ``QTimer`` that calls
    the engine's ``should_auto_advance()`` / milestone APIs directly.
    ``AutomatedSeasonFlow.start_automation()`` is never called (it would
    crash on ``game_manager.after``).
  - OBS-2 root-cause fix: ``simulate_day()`` NEVER runs on the Qt UI
    thread here. The automation loop and the quick-advance actions run the
    sim on a worker thread and marshal completion back to the UI thread
    (mirroring ``run_threaded`` from ``native_ui.dialogs.sim_progress``,
    the same pattern ``MainWindow.on_continue`` uses). The automation
    loop shows the non-modal ``DaySimLoadingOverlay`` so the app stays
    usable between days; quick advances use the cancelable
    ``run_threaded`` progress dialog with per-day progress.
  - Worker-thread ``_ui_notify`` guard (``_install_worker_notify_guard``):
    ``MainWindow`` rebinds ``game._ui_notify`` to a dispatcher whose
    worker-thread path deadlocks (``QTimer.singleShot`` from a non-Qt
    thread never fires). While a season-flow worker sims, notifies from
    that thread are answered with the native headless defaults instead
    of blocking; the original is restored afterwards. The main_window
    marshal itself is owned by whoever owns that file.
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

import queue
import threading

from .base import BaseScreen
from native_ui.safe import safe_call

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


def _install_worker_notify_guard(game):
    """Make ``game._ui_notify`` safe to call from a sim worker thread.

    WHY (root cause, cross-file): ``MainWindow.__init__`` rebinds
    ``game._ui_notify`` to its dispatcher, whose worker-thread path
    (``QTimer.singleShot(0, ...)`` from a non-Qt thread, then
    ``threading.Event.wait()``) never fires -- a worker-thread
    ``simulate_day()`` deadlocks on the first ``_set_continue_feedback``
    instead of simming. Until that marshal is fixed in main_window.py,
    this guard answers worker-thread notifies with the native headless
    defaults instead of blocking forever.

    Worker-thread answers mirror the native UI-thread behavior:
      - "continue_feedback" -> None (our progress UI covers feedback)
      - "game_day_bundle"   -> False (== MainWindow._notify_game_day_bundle)
      - "ask_game_mode"     -> "quick" (background advance: quick-sim,
        never open the viewer/modal off-thread)
      - "ask_playoffs_mode" -> False (non-interactive)
      - everything else      -> None (fire-and-forget kinds)

    Calls made on the UI thread still delegate to the original. The
    guard is nesting-safe via a depth counter; the returned ``restore``
    callable must be called exactly once per install (use try/finally).
    """
    depth = getattr(game, "_sf_notify_guard_depth", 0)
    if depth == 0:
        original = game._ui_notify
        ui_thread = threading.current_thread()

        def _guard(kind, *args, **kwargs):
            if threading.current_thread() is ui_thread:
                return original(kind, *args, **kwargs)
            if kind == "game_day_bundle":
                return False
            if kind == "ask_game_mode":
                return "quick"
            if kind == "ask_playoffs_mode":
                return False
            return None

        game._ui_notify = _guard
        game._sf_notify_guard_original = original
    game._sf_notify_guard_depth = depth + 1

    def _restore():
        left = getattr(game, "_sf_notify_guard_depth", 1) - 1
        game._sf_notify_guard_depth = max(left, 0)
        if left <= 0:
            try:
                game._ui_notify = game._sf_notify_guard_original
            except Exception:
                pass
            try:
                del game._sf_notify_guard_original
            except Exception:
                pass

    return _restore


class MilestoneDialog(QDialog):
    """Native milestone notification (ports MilestoneNotificationView)."""

    def __init__(self, parent, milestone, main_window):
        super().__init__(parent)
        self._milestone = milestone
        self._main_window = main_window
        phase_value = safe_call(
            lambda: milestone.phase.value, "",
            context="season_flow:milestone:phase")
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

        date_lbl = QLabel(safe_call(
            lambda: milestone.date.strftime("%B %d, %Y"), "",
            context="season_flow:milestone:date"))
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
        if safe_call(lambda: milestone.is_critical, False,
                       context="season_flow:milestone:critical"):
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
        # Worker-thread state (OBS-2): the day sim never runs on the UI
        # thread, so these guards live for the whole screen lifetime.
        self._sim_in_progress = False
        self._auto_overlay = None
        self._quick_btns = []
        self._running = False
        self._day_result_q = None
        self._day_restore_notify = None

        if not _ENGINE_OK:
            err = QLabel(
                "Season automation is unavailable: "
                f"could not load automated_season_flow ({_ENGINE_ERR})")
            err.setWordWrap(True)
            self._layout.addWidget(err)
            self._layout.addStretch()
            self._automation = None
            return
        if self.game is None or safe_call(
                lambda: self.game.league, None,
                context="season_flow:build:league") is None:
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
            self._quick_btns.append(btn)
            quick_row.addWidget(btn)
        self._layout.addWidget(quick_box)

        # ---- automation timer (schedules days; the sim itself runs on a
        # worker thread -- see _automation_tick) ----
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._automation_tick)

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
                safe_call(lambda: phase.value, "Unknown",
                          context="season_flow:refresh:phase"))
            nxt = self._automation.get_next_milestone()
            if nxt and format_days_until_milestone:
                days_txt = format_days_until_milestone(
                    nxt, self.game.current_date)
                self._milestone_lbl.setText(f"{nxt.name} \u2014 {days_txt}")
            else:
                self._milestone_lbl.setText("No upcoming milestones")
            # OBS-2: while a worker sim is in flight (automation day or
            # quick advance), all sim-triggering controls stay disabled so
            # the user cannot stack overlapping workers.
            busy = bool(self._running) or bool(
                getattr(self, "_sim_in_progress", False))
            self._start_btn.setEnabled(not busy)
            self._stop_btn.setEnabled(bool(self._running))
            self._mode_combo.setEnabled(not busy)
            self._settings_btn.setEnabled(not busy)
            for btn in getattr(self, "_quick_btns", []):
                btn.setEnabled(not busy)
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
        speed = safe_call(
            lambda: self._automation.settings.days_per_second, 1.0,
            context="season_flow:tick:speed") or 1.0
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
        self._hide_auto_overlay()
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
        """Schedule one automation step.

        OBS-2: the QTimer only schedules. ``simulate_day()`` runs on a
        daemon worker thread (see ``_start_day_worker``); per-day
        UI-thread logic (milestones, refresh) runs in
        ``_on_day_sim_done``, which the worker marshals back to the UI
        thread via ``QTimer.singleShot(0, ...)``. The UI stays responsive
        the whole time.
        """
        auto = self._automation
        if not self._running or auto is None:
            return
        if self._sim_in_progress:
            # Previous day's worker still running -- skip this tick; the
            # next tick will pick up where it left off.
            return
        try:
            if not safe_call(auto.should_auto_advance, False,
                             context="season_flow:auto:should_advance"):
                return
            # Native improvement: never sim past blockers the user must
            # resolve -- stop and surface them instead.
            _label, blockers = safe_call(
                lambda: self.game.get_continue_state(), (None, []),
                context="season_flow:auto:continue_state")
            if blockers:
                self._stop_automation()
                try:
                    self.main_window.show_blockers(blockers)
                except Exception as e:
                    print(f"[season_flow] show_blockers failed: {e}")
                return
            self._start_day_worker()
        except Exception as e:
            print(f"[season_flow] automation tick failed: {e}")
            self._stop_automation()

    def _start_day_worker(self):
        """Run one day of sim on a worker thread.

        Completion is reported through a ``queue.Queue`` which the UI
        thread drains via ``_poll_day_worker`` -- the same structure as
        ``run_threaded`` in ``native_ui.dialogs.sim_progress``. (A plain
        ``QTimer.singleShot(0, ...)`` issued from the worker thread never
        fires: the timer is created in the calling thread, which has no
        event loop.) The worker touches only sim objects, never widgets.

        The worker-thread ``_ui_notify`` guard is installed here on the
        UI thread and restored in ``_poll_day_worker`` once the result is
        drained -- see ``_install_worker_notify_guard``.
        """
        game = self.game
        self._sim_in_progress = True
        self._show_auto_overlay()
        self.refresh()
        result_q = queue.Queue()
        self._day_result_q = result_q
        restore_notify = _install_worker_notify_guard(game)

        def _worker():
            try:
                _bulk = getattr(game, "_bulk_simming", None)
                try:
                    if _bulk is not None:
                        game._bulk_simming = True
                    game.simulate_day()
                finally:
                    if _bulk is not None:
                        try:
                            game._bulk_simming = False
                        except Exception:
                            pass
                result_q.put((False, None))
            except Exception as e:  # noqa: BLE001 -- reported on UI thread
                result_q.put((True, e))

        threading.Thread(target=_worker, daemon=True,
                         name="season-flow-day").start()
        QTimer.singleShot(100, self._poll_day_worker)
        # Keep restore paired with this worker even if the poll chain is
        # somehow dropped: stash it for the poll to consume.
        self._day_restore_notify = restore_notify

    def _poll_day_worker(self):
        """Drain the day worker's result queue. Runs ON the UI thread."""
        result_q = getattr(self, "_day_result_q", None)
        if result_q is None:
            return
        try:
            failed, payload = result_q.get_nowait()
        except queue.Empty:
            if getattr(self, "_sim_in_progress", False):
                QTimer.singleShot(100, self._poll_day_worker)
            return
        self._day_result_q = None
        restore = getattr(self, "_day_restore_notify", None)
        self._day_restore_notify = None
        try:
            self._on_day_sim_done(payload if failed else None)
        finally:
            if restore is not None:
                try:
                    restore()
                except Exception:
                    pass

    def _on_day_sim_done(self, error):
        """Day worker finished. Runs ON the UI thread.

        On error: stop automation, report, leave state consistent -- the
        failed day is the only one affected; no further days are simmed.
        """
        self._sim_in_progress = False
        if error is not None:
            print(f"[season_flow] automation day sim failed: {error}")
            self._stop_automation()
            QMessageBox.critical(
                self, "Simulation Error",
                "The day simulation failed and automation was stopped:\n"
                f"{error}\n\n"
                "No further days were simulated.")
            return
        if not self._running:
            # Stopped while the worker was in flight (e.g. user hit Stop
            # mid-day). The day completed atomically; just clean up.
            self._hide_auto_overlay()
            self.refresh()
            return
        safe_call(self._automation.update_season_phase,
                  context="season_flow:auto:update_phase")
        self._check_milestone_triggers()
        if self._running:
            # A critical milestone may have stopped automation above.
            self._update_auto_overlay()
        self.refresh()
        # Keep the hub/dashboard behind us fresh.
        try:
            hub = getattr(self.main_window, "hub", None)
            if hub is not None and hasattr(hub, "refresh"):
                hub.refresh(self.game)
        except Exception:
            pass

    # -- non-modal progress indicator for the automation loop --
    def _show_auto_overlay(self):
        """Show the day-sim toast (non-modal; app stays usable)."""
        if self._auto_overlay is not None:
            return
        try:
            from native_ui.dialogs.sim_progress import DaySimLoadingOverlay
        except Exception as e:
            print(f"[season_flow] overlay import failed: {e}")
            return
        try:
            parent = self.main_window if self.main_window is not None else self
            self._auto_overlay = DaySimLoadingOverlay(parent)
            self._auto_overlay.set_auto_mode(True)
            self._update_auto_overlay()
        except Exception as e:
            print(f"[season_flow] overlay show failed: {e}")
            self._auto_overlay = None

    def _update_auto_overlay(self):
        if self._auto_overlay is None:
            return
        try:
            date_txt = safe_call(
                lambda: self.game.current_date.strftime("%b %d, %Y"), "",
                context="season_flow:auto:overlay_date")
            self._auto_overlay.set_status(
                f"Auto-advancing\u2026 {date_txt}".strip())
        except Exception:
            pass

    def _hide_auto_overlay(self):
        overlay, self._auto_overlay = self._auto_overlay, None
        if overlay is not None:
            try:
                overlay.destroy()
            except Exception:
                pass

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
                if safe_call(lambda: m.is_critical, False,
                               context="season_flow:milestone:critical") \
                        and self._running:
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
        """Advance N days off the UI thread via run_threaded.

        Mirrors ``MainWindow.on_continue``: the sim runs on a worker
        thread with a cancelable progress dialog (per-day progress);
        ``_on_done`` runs on the UI thread and does all widget updates.
        A busy guard rejects overlapping runs (double-click safe).
        """
        if not self._automation:
            return
        if self._sim_in_progress or self._running:
            QMessageBox.information(
                self, "Busy",
                "A simulation is already running. "
                "Wait for it to finish before advancing again.")
            return
        try:
            _label, blockers = self.game.get_continue_state()
            if blockers:
                self.main_window.show_blockers(blockers)
                return
            try:
                from native_ui.dialogs.sim_progress import (
                    run_threaded, create_fallback_save)
            except Exception as e:
                print(f"[season_flow] sim progress import failed: {e}")
                QMessageBox.critical(
                    self, "Error",
                    "Could not start the background sim. Try again.")
                return

            create_fallback_save(self.game, "season_flow_advance")
            self._sim_in_progress = True
            self.refresh()
            game = self.game
            restore_notify = _install_worker_notify_guard(game)

            def _worker(cancel_event, progress):
                # Runs OFF the UI thread. Must not touch widgets.
                done = 0
                _bulk = getattr(game, "_bulk_simming", None)
                try:
                    if _bulk is not None:
                        game._bulk_simming = True
                    for i in range(days):
                        if cancel_event.is_set():
                            break
                        game.simulate_day()
                        done += 1
                        progress((i + 1) / days,
                                 f"Day {i + 1} of {days}\u2026")
                finally:
                    if _bulk is not None:
                        try:
                            game._bulk_simming = False
                        except Exception:
                            pass
                return done

            def _on_done(cancelled, error):
                # Runs ON the UI thread.
                self._sim_in_progress = False
                try:
                    restore_notify()
                except Exception:
                    pass
                if error is not None:
                    print(f"[season_flow] advance days failed: {error}")
                    QMessageBox.critical(
                        self, "Error",
                        f"Failed to advance: {error}\n\n"
                        "No further days were simulated.")
                else:
                    try:
                        hub = getattr(self.main_window, "hub", None)
                        if hub is not None and hasattr(hub, "refresh"):
                            hub.refresh(self.game)
                    except Exception:
                        pass
                    if not cancelled:
                        QMessageBox.information(
                            self, "Advanced",
                            f"Advanced {days} day"
                            f"{'s' if days != 1 else ''}.")
                self.refresh()

            run_threaded(self, f"Advancing {days} day"
                               f"{'s' if days != 1 else ''}\u2026",
                         _worker, on_done=_on_done,
                         status="Starting\u2026")
        except Exception as e:
            print(f"[season_flow] advance days failed: {e}")
            self._sim_in_progress = False
            self.refresh()
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
