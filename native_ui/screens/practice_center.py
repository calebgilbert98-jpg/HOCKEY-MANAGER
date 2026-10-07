"""Practice Center: drill assignment + "Coach Runs Practice" (v0.15.0 headline).

Calls the game object directly -- no Flask/HTTP. The "Coach Runs
Practice" button calls the real game method
``auto_resolve.auto_run_practice`` (the same entry point the tkinter
PracticeCenterView used). Individual drill controls call the real
PracticeEngine (schedule_practice / execute_practice /
stop_practice_schedule) when the engine can be loaded.

The practice engine lives in ``enhanced_practice_system`` (a tkinter /
customtkinter module), so every import of it is lazy and guarded: in an
environment without customtkinter the screen shows an "unavailable"
message instead of crashing.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QGroupBox, QScrollArea, QMessageBox,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable

# PracticeType values from enhanced_practice_system (kept as strings so this
# module imports cleanly even when the engine module is unavailable).
DRILL_TYPES = [
    ("skating", "Skating"),
    ("shooting", "Shooting"),
    ("passing", "Passing"),
    ("checking", "Checking"),
    ("defense", "Defense"),
    ("faceoffs", "Faceoffs"),
    ("conditioning", "Conditioning"),
    ("hockey_iq", "Hockey IQ"),
    ("teamwork", "Teamwork"),
    ("leadership", "Leadership"),
]

INTENSITIES = [
    ("light", "Light"),
    ("moderate", "Moderate"),
    ("intense", "Intense"),
    ("extreme", "Extreme"),
]

class PracticeCenterScreen(BaseScreen):
    title = "Practice Center"

    def _build_body(self):
        # Headline: Coach Runs Practice (v0.15.0)
        head = QHBoxLayout()
        coach_btn = QPushButton("Coach Runs Practice")
        coach_btn.setObjectName("primary-btn")
        coach_btn.setCursor(Qt.PointingHandCursor)
        coach_btn.clicked.connect(self._coach_runs_practice)
        head.addWidget(coach_btn)
        head.addStretch()
        self._layout.addLayout(head)

        subtitle = QLabel(
            "Schedule individual practice sessions for players on the "
            "active roster — or let the coach auto-assign weakness-targeted "
            "drills for everyone.")
        subtitle.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        subtitle.setWordWrap(True)
        self._layout.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(16)

        # Left: player list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_head = QLabel("ACTIVE ROSTER")
        left_head.setObjectName("section-header")
        left_layout.addWidget(left_head)
        self._table = PlayerTable()
        self._table.cellClicked.connect(
            lambda row, _col: self._select_player(row))
        left_layout.addWidget(self._table, 1)
        body.addWidget(left, 1)

        # Right: practice controls (scrollable)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_head = QLabel("PRACTICE SESSION")
        right_head.setObjectName("section-header")
        right_layout.addWidget(right_head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._controls = QWidget()
        self._controls_layout = QVBoxLayout(self._controls)
        self._controls_layout.setSpacing(10)
        scroll.setWidget(self._controls)
        right_layout.addWidget(scroll, 1)
        body.addWidget(right, 1)

        self._layout.addLayout(body, 1)

        self._selected_player = None
        self._status = QLabel("")
        self._status.setStyleSheet("color: #eab308; font-size: 13px;")
        self._status.setWordWrap(True)
        self._layout.addWidget(self._status)

    # --- game access ----------------------------------------------------
    def _user_team(self):
        """Resolve the human club from the game object."""
        candidates = [self.game]
        try:
            candidates.append(getattr(self.game, "game_manager", None))
        except Exception:
            pass
        for src in candidates:
            if src is None:
                continue
            try:
                team = getattr(src, "user_team", None)
            except Exception:
                team = None
            if team is not None:
                return team
        return None

    def _engine(self):
        """Return a PracticeEngine instance, or None when unavailable."""
        for src in (self.game,
                    getattr(self.game, "game_manager", None)
                    if self.game is not None else None):
            if src is None:
                continue
            try:
                eng = getattr(src, "practice_engine", None)
            except Exception:
                eng = None
            if eng is not None:
                return eng
        # Build one directly (lazy: module needs customtkinter).
        try:
            from enhanced_practice_system import PracticeEngine
            eng = PracticeEngine()
            try:
                if self.game is not None:
                    self.game.practice_engine = eng
            except Exception:
                pass
            return eng
        except Exception:
            return None

    def _enums(self):
        """(PracticeType, PracticeIntensity) or (None, None)."""
        try:
            from enhanced_practice_system import (
                PracticeType, PracticeIntensity)
            return PracticeType, PracticeIntensity
        except Exception:
            return None, None

    def _condition_text(self, player):
        try:
            import condition_ui
            return condition_ui.condition_text(player)
        except Exception:
            pass
        try:
            return str(int(getattr(player, "condition", 100) or 100))
        except Exception:
            return "100"

    # --- headline feature -----------------------------------------------
    def _coach_runs_practice(self):
        """Auto-assign weakness-targeted drills for the whole roster.

        Calls the real game method: auto_resolve.auto_run_practice(team,
        app) -- the same entry point the tkinter PracticeCenterView's
        "Coach Runs Practice" button used. Returns (sessions, error_msg).
        """
        team = self._user_team()
        if team is None:
            QMessageBox.warning(self, "Coach Runs Practice",
                                "No game loaded.")
            return
        try:
            from auto_resolve import auto_run_practice
        except Exception as e:
            QMessageBox.warning(self, "Coach Runs Practice",
                                f"Coach logic unavailable: {e}")
            return
        try:
            sessions, err = auto_run_practice(team, self.game)
        except Exception as e:
            QMessageBox.warning(self, "Coach Runs Practice",
                                f"Coach run failed: {e}")
            return
        if err:
            QMessageBox.warning(self, "Coach Runs Practice", str(err))
        else:
            try:
                self.game.add_news(
                    f"Coach ran practice: {sessions} sessions assigned "
                    "(weakness-targeted drills, fatigue-aware intensity).")
            except Exception:
                pass
            QMessageBox.information(
                self, "Coach Runs Practice",
                f"Coach assigned {sessions} practice sessions.\n\n"
                "Drills target each player's weakest role-relevant "
                "attributes; intensity is matched to fatigue, age, and "
                "injury status (injured players are skipped).")
        self.refresh()

    # --- player selection ------------------------------------------------
    def _select_player(self, row):
        try:
            players = getattr(self._table, "_players", [])
            if 0 <= row < len(players):
                self._selected_player = players[row]
                self._rebuild_controls()
        except Exception:
            pass

    # --- controls ----------------------------------------------------------
    def _clear_controls(self):
        while self._controls_layout.count():
            item = self._controls_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _rebuild_controls(self):
        self._clear_controls()
        eng = self._engine()
        if eng is None:
            note = QLabel(
                "Practice system unavailable in this environment.\n"
                "It needs the game engine (customtkinter) to run.")
            note.setStyleSheet("color: #eab308; font-size: 13px;")
            note.setWordWrap(True)
            self._controls_layout.addWidget(note)
            return
        if self._selected_player is None:
            note = QLabel("Select a player to configure practice.")
            note.setStyleSheet("color: #6b7488; font-size: 14px;")
            note.setAlignment(Qt.AlignCenter)
            self._controls_layout.addWidget(note)
            return

        player = self._selected_player
        PracticeType, PracticeIntensity = self._enums()

        # Player info
        info = QGroupBox("Player")
        info_layout = QVBoxLayout(info)
        name_lbl = QLabel(getattr(player, "full_name", "?"))
        name_lbl.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700;")
        info_layout.addWidget(name_lbl)
        try:
            history = eng.get_player_history(player.id)
            fatigue = getattr(history, "current_fatigue", 0)
        except Exception:
            history, fatigue = None, 0
        injured = bool(getattr(player, "is_injured", False))
        stat_lbl = QLabel(
            f"Fatigue: {fatigue}%  •  Condition: "
            f"{self._condition_text(player)}"
            + ("  •  INJURED" if injured else ""))
        stat_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        stat_lbl.setWordWrap(True)
        info_layout.addWidget(stat_lbl)

        # Current schedule
        schedule = getattr(history, "current_schedule", None) if history else None
        if schedule:
            try:
                stype = schedule["type"]
                sint = schedule["intensity"]
                stype = getattr(stype, "value", stype)
                sint = getattr(sint, "value", sint)
                remaining = schedule.get("sessions_remaining", "?")
                sched_lbl = QLabel(
                    f"Current: {str(stype).replace('_', ' ').title()} "
                    f"({str(sint).replace('_', ' ').title()}) — "
                    f"{remaining} sessions remaining")
            except Exception:
                sched_lbl = QLabel("Current practice schedule active.")
            sched_lbl.setStyleSheet("color: #3B82F6; font-size: 13px;")
            sched_lbl.setWordWrap(True)
            info_layout.addWidget(sched_lbl)
            stop_btn = QPushButton("Stop Current Practice")
            stop_btn.clicked.connect(self._stop_practice)
            info_layout.addWidget(stop_btn)
        self._controls_layout.addWidget(info)

        # Drill type
        type_box = QGroupBox("Practice Type")
        type_layout = QVBoxLayout(type_box)
        self._drill_combo = QComboBox()
        for value, label in DRILL_TYPES:
            self._drill_combo.addItem(label, value)
        self._drill_combo.currentIndexChanged.connect(
            self._update_coaching_read)
        type_layout.addWidget(self._drill_combo)
        self._controls_layout.addWidget(type_box)

        # Coaching read (who runs the drill, how it lands)
        read_box = QGroupBox("Coaching Read")
        read_layout = QVBoxLayout(read_box)
        self._read_lbl = QLabel("")
        self._read_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._read_lbl.setWordWrap(True)
        read_layout.addWidget(self._read_lbl)
        self._controls_layout.addWidget(read_box)
        self._update_coaching_read()

        # Intensity
        int_box = QGroupBox("Intensity")
        int_layout = QVBoxLayout(int_box)
        self._intensity_combo = QComboBox()
        for value, label in INTENSITIES:
            self._intensity_combo.addItem(label, value)
        self._intensity_combo.setCurrentIndex(1)  # Moderate
        int_layout.addWidget(self._intensity_combo)
        self._controls_layout.addWidget(int_box)

        # Schedule
        sched_box = QGroupBox("Schedule")
        sched_layout = QVBoxLayout(sched_box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Sessions per week:"))
        self._sessions_spin = QSpinBox()
        self._sessions_spin.setRange(1, 7)
        self._sessions_spin.setValue(3)
        row1.addWidget(self._sessions_spin)
        row1.addStretch()
        sched_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Duration (weeks):"))
        self._weeks_spin = QSpinBox()
        self._weeks_spin.setRange(1, 12)
        self._weeks_spin.setValue(4)
        row2.addWidget(self._weeks_spin)
        row2.addStretch()
        sched_layout.addLayout(row2)
        self._controls_layout.addWidget(sched_box)

        # Actions
        btn_row = QHBoxLayout()
        start_btn = QPushButton("Start Practice Schedule")
        start_btn.setObjectName("primary-btn")
        start_btn.clicked.connect(self._start_schedule)
        single_btn = QPushButton("Single Session")
        single_btn.clicked.connect(self._run_single_session)
        btn_row.addWidget(start_btn)
        btn_row.addWidget(single_btn)
        btn_row.addStretch()
        self._controls_layout.addLayout(btn_row)
        self._controls_layout.addStretch()

    def _update_coaching_read(self, _idx=None):
        lbl = getattr(self, "_read_lbl", None)
        if lbl is None or self._selected_player is None:
            return
        try:
            import coach_practice as _cp
            team = self._user_team()
            value = self._drill_combo.currentData()
            bd = _cp.practice_breakdown(team, self._selected_player,
                                        str(value))
            desc = _cp.describe_session(bd)
            if desc:
                lbl.setText("\n".join("• " + line for line in desc))
            else:
                lbl.setText("No coaching staff on file.")
        except Exception:
            lbl.setText("Coaching read unavailable.")

    def _drill_and_intensity(self):
        """Resolve combo selections to PracticeType/PracticeIntensity enums."""
        PracticeType, PracticeIntensity = self._enums()
        if PracticeType is None or PracticeIntensity is None:
            return None, None
        try:
            drill = PracticeType(self._drill_combo.currentData())
        except Exception:
            return None, None
        try:
            intensity = PracticeIntensity(self._intensity_combo.currentData())
        except Exception:
            return None, None
        return drill, intensity

    def _start_schedule(self):
        if self._selected_player is None:
            return
        eng = self._engine()
        if eng is None:
            QMessageBox.warning(self, "Practice",
                                "Practice system unavailable.")
            return
        drill, intensity = self._drill_and_intensity()
        if drill is None or intensity is None:
            QMessageBox.warning(self, "Practice",
                                "Select a drill type and intensity.")
            return
        total = self._sessions_spin.value() * self._weeks_spin.value()
        try:
            result = eng.schedule_practice(self._selected_player, drill,
                                           intensity, total)
        except Exception as e:
            QMessageBox.warning(self, "Practice",
                                f"Failed to schedule practice: {e}")
            return
        if getattr(result, "success", False):
            QMessageBox.information(
                self, "Practice Scheduled",
                f"Practice schedule started for "
                f"{getattr(self._selected_player, 'full_name', '?')}!\n"
                f"Type: {self._drill_combo.currentText()}\n"
                f"Intensity: {self._intensity_combo.currentText()}\n"
                f"Sessions: {total}")
            self.refresh()
        else:
            QMessageBox.warning(self, "Schedule Failed",
                                str(getattr(result, "message",
                                            "Unknown error")))

    def _run_single_session(self):
        if self._selected_player is None:
            QMessageBox.warning(self, "Practice",
                                "Please select a player first.")
            return
        eng = self._engine()
        if eng is None:
            QMessageBox.warning(self, "Practice",
                                "Practice system unavailable.")
            return
        drill, intensity = self._drill_and_intensity()
        if drill is None or intensity is None:
            QMessageBox.warning(self, "Practice",
                                "Select a drill type and intensity.")
            return
        try:
            can, reason = eng.can_practice(self._selected_player, drill,
                                           intensity)
        except Exception as e:
            QMessageBox.warning(self, "Practice", f"Cannot check: {e}")
            return
        if not can:
            QMessageBox.warning(self, "Cannot Practice", str(reason))
            return
        try:
            session = eng.execute_practice(
                self._selected_player, drill, intensity,
                duration_minutes=60, trainer_quality=10,
                team=self._user_team())
        except Exception as e:
            QMessageBox.warning(self, "Practice",
                                f"Failed to run practice: {e}")
            return
        if session:
            QMessageBox.information(
                self, "Practice Complete",
                f"Practice session completed for "
                f"{getattr(self._selected_player, 'full_name', '?')}!\n"
                f"Skill gain: {getattr(session, 'skill_gain', 0):.2f}\n"
                f"Fatigue: +{getattr(session, 'fatigue_cost', 0)}%\n"
                f"Duration: {getattr(session, 'duration_minutes', 60)} "
                "minutes")
            self.refresh()
        else:
            QMessageBox.warning(self, "Practice Failed",
                                "Failed to complete practice session.")

    def _stop_practice(self):
        if self._selected_player is None:
            return
        eng = self._engine()
        if eng is None:
            return
        try:
            eng.stop_practice_schedule(self._selected_player)
            QMessageBox.information(
                self, "Practice Stopped",
                f"Practice schedule stopped for "
                f"{getattr(self._selected_player, 'full_name', '?')}.")
        except Exception as e:
            QMessageBox.warning(self, "Practice", f"Failed: {e}")
        self.refresh()

    # --- refresh ----------------------------------------------------------
    def refresh(self):
        try:
            team = self._user_team()
            roster = list(getattr(team, "roster", None) or []) \
                if team is not None else []
            self._table.set_players(roster)
            # Keep selection on refresh
            if self._selected_player is not None:
                ids = [str(getattr(p, "id", "")) for p in roster]
                sel = str(getattr(self._selected_player, "id", ""))
                if sel in ids:
                    self._table.selectRow(ids.index(sel))
            self._rebuild_controls()
            self._status.setText("")
        except Exception as e:
            self._status.setText(f"Could not load practice data: {e}")
