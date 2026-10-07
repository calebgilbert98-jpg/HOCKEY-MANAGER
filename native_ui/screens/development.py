"""Development hub: training programs, per-player practice, positional
training, offseason programs, development analytics, prospect watchlist.

Native Qt port of the web development screen (Batch D). Calls the game
object directly -- no Flask/HTTP. The practice engine lives in
``enhanced_practice_system`` (a tkinter/customtkinter module), so every
import of it is lazy and guarded: engine-dependent sections show an
"unavailable" notice instead of crashing when it can't be loaded.

OVERLAP NOTE (kept separate per port plan): practice_center.py (Wave 1)
is the dedicated Practice Center screen covering the drill engine;
this screen keeps the web-faithful development-hub view -- per-player
practice controls alongside training programs, positional training, the
seasonal offseason panel, and dev analytics.
"""
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QScrollArea, QMessageBox, QRadioButton,
    QButtonGroup, QLineEdit, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.attribute_bar import AttributeBar


class DevelopmentScreen(BaseScreen):
    title = "Development"

    # Desktop vocabulary (web parity: web_ui/screens/development.py
    # _DEV_FOCUSES / _DEV_INTENSITIES).
    DEV_FOCUSES = [
        "Skating & Speed", "Shooting Accuracy", "Passing & Vision",
        "Defensive Positioning", "Physical Conditioning", "Mental Toughness",
        "Position-Specific Skills", "Hockey IQ Development",
    ]
    DEV_INTENSITIES = ["Light", "Standard", "Intensive"]

    # Desktop key-attribute groups (web parity: _DEV_KEY_ATTRS).
    DEV_KEY_ATTRS = {
        "C": ["skating", "passing", "faceoffs", "hockey_iq", "vision",
              "determination"],
        "LW": ["skating", "shooting", "passing", "checking", "determination",
               "conditioning"],
        "RW": ["skating", "shooting", "passing", "checking", "determination",
               "conditioning"],
        "D": ["skating", "defense", "passing", "checking", "positioning",
              "hockey_iq"],
        "G": ["goaltending", "reflexes", "positioning", "rebound_control",
              "mental_toughness", "consistency"],
    }

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_body(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        self._content = QVBoxLayout(content)
        self._content.setSpacing(18)
        scroll.setWidget(content)
        self._layout.addWidget(scroll, 1)

        # Section shells; dynamic content is rebuilt in refresh().
        self._programs_box = self._make_section("ACTIVE TRAINING PROGRAMS")
        self._assign_box = self._make_section(
            "ASSIGN TRAINING PROGRAM",
            "per-player focus + intensity")
        self._practice_box = self._make_section(
            "PRACTICE CENTER", "per-player drills")
        self._pos_box = self._make_section(
            "POSITIONAL TRAINING", "train a new position")
        self._off_box = self._make_section(
            "OFFSEASON PROGRAMS", "summer focuses")
        self._analytics_box = self._make_section(
            "DEVELOPMENT ANALYTICS", "team overview + per-player focus")
        self._prospects_box = self._make_section(
            "PROSPECT WATCHLIST", "age 23 and under")

        self._programs_list = self._list_widget(self._programs_box)
        self._build_assign_form(self._assign_box)
        self._build_practice_form(self._practice_box)
        self._build_position_form(self._pos_box)
        self._off_list = self._list_widget(self._off_box)
        self._build_analytics_form(self._analytics_box)
        self._prospects_list = self._list_widget(self._prospects_box)

        self._analytics = {"overview": {}, "positions": [],
                           "age_bands": [], "players": []}
        self._programs = []
        self._all_players = []  # (player, squad) for dropdowns
        self._status = QLabel("")
        self._status.setStyleSheet("color: #eab308; font-size: 13px;")
        self._status.setWordWrap(True)
        self._layout.addWidget(self._status)

    def _make_section(self, title, sub=""):
        grp = QGroupBox()
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)
        head = QLabel(title)
        head.setObjectName("section-header")
        lay.addWidget(head)
        if sub:
            note = QLabel(sub)
            note.setStyleSheet("color: #6b7488; font-size: 12px;")
            lay.addWidget(note)
        self._content.addWidget(grp)
        return grp

    @staticmethod
    def _list_widget(box):
        """Container layout inside a section for rebuilt content."""
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        box.layout().addWidget(holder)
        return lay

    @staticmethod
    def _clear(lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _dim(self, text, size=13):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: #9aa4b8; font-size: {size}px;")
        lbl.setWordWrap(True)
        return lbl

    # ------------------------------------------------------------------
    # game access
    # ------------------------------------------------------------------
    def _gm_team(self):
        """(game_manager, user team) -- web parity: _batchd_gm_team."""
        try:
            gm = getattr(self.game, "game_manager", None)
            team = (getattr(gm, "user_team", None)
                    if gm is not None else None)
            if team is None:
                team = getattr(self.game, "user_team", None)
            return gm, team
        except Exception:
            return None, None

    def _squads(self):
        """(roster, ahl, prospects) -- web parity: _batchd_squads."""
        _gm, team = self._gm_team()
        out = []
        for attr in ("roster", "ahl_roster", "prospects"):
            try:
                out.append(list(getattr(team, attr, None) or []))
            except Exception:
                out.append([])
        return out

    def _engine(self):
        """Shared PracticeEngine, or None when the module can't load."""
        eng = getattr(self, "_practice_engine", None)
        if eng is not None:
            return eng
        for src in (self.game,
                    getattr(self.game, "game_manager", None)):
            if src is None:
                continue
            try:
                eng = getattr(src, "practice_engine", None)
            except Exception:
                eng = None
            if eng is not None:
                self._practice_engine = eng
                return eng
        try:
            from enhanced_practice_system import PracticeEngine
            eng = PracticeEngine()
            self._practice_engine = eng
            try:
                if self.game is not None:
                    self.game.practice_engine = eng
            except Exception:
                pass
            return eng
        except Exception:
            return None

    @staticmethod
    def _enums():
        """(PracticeType, PracticeIntensity) or (None, None)."""
        try:
            from enhanced_practice_system import (
                PracticeType, PracticeIntensity)
            return PracticeType, PracticeIntensity
        except Exception:
            return None, None

    @staticmethod
    def _ovr(p):
        try:
            from game_classes import to_100_scale
            return int(to_100_scale(getattr(p, "overall", 50)))
        except Exception:
            return getattr(p, "overall", "?")

    @staticmethod
    def _pos_str(p):
        pos = getattr(p, "position", "?")
        return getattr(pos, "value", str(pos))

    def _coaching_quality(self, team):
        """Teaching quality for positional training -- web parity:
        _batchd_coaching_quality."""
        try:
            import coach_practice as _cp
            hc = _cp.head_coach_of(team)
            if hc is not None:
                vals = []
                for a in ("technical_coaching", "tactical_knowledge",
                          "player_development"):
                    try:
                        v = getattr(hc, a, None)
                        if v is not None:
                            vals.append(float(v))
                    except Exception:
                        continue
                if vals:
                    return max(1.0, min(100.0, sum(vals) / len(vals)))
        except Exception:
            pass
        return 50.0

    def _find_player(self, pid):
        """Player object across the user's squads, or None."""
        _, roster, ahl, prospects = (None, *self._squads())
        for p in list(roster) + list(ahl) + list(prospects):
            try:
                if str(getattr(p, "id", None)) == str(pid):
                    return p
            except Exception:
                continue
        return None

    def _player_team(self, team, player):
        """The club whose coaching staff runs a drill -- web parity:
        _batchd_player_team."""
        try:
            gm = getattr(self.game, "game_manager", None)
            league = getattr(gm, "league", None) \
                or getattr(self.game, "league", None)
            for t in list(getattr(league, "teams", None) or []):
                try:
                    for lst in (getattr(t, "roster", None),
                                getattr(t, "ahl_roster", None),
                                getattr(t, "prospects", None)):
                        if player in (lst or []):
                            return t
                except Exception:
                    continue
        except Exception:
            pass
        return team

    def _fill_player_combo(self, combo):
        """Fill with all squad players; injured options are disabled.

        Web parity: injured players are excluded from practice/position
        forms and disabled in every player select.
        """
        combo.clear()
        for p, squad in self._all_players:
            try:
                name = getattr(p, "full_name", "?")
                label = (f"{name} ({self._pos_str(p)}) · "
                         f"Age {getattr(p, 'age', '?')} · {squad}")
                injured = bool(getattr(p, "is_injured", False))
                if injured:
                    label += " · INJURED"
                combo.addItem(label, p)
                if injured:
                    combo.model().item(
                        combo.count() - 1).setEnabled(False)
            except Exception:
                continue

    # ------------------------------------------------------------------
    # section: active training programs
    # ------------------------------------------------------------------
    def _load_programs(self):
        """Merge program sources, de-duplicated by normalized player id.

        Web parity: get_development() merges live.training_programs,
        gm.training_programs, and enhanced_practice_system's
        ACTIVE_TRAINING_PROGRAMS.
        """
        sources = []
        gm, _team = self._gm_team()
        try:
            sources.append(getattr(self.game, "training_programs", None))
        except Exception:
            pass
        if gm is not None:
            try:
                sources.append(getattr(gm, "training_programs", None))
            except Exception:
                pass
        try:
            from enhanced_practice_system import ACTIVE_TRAINING_PROGRAMS
            sources.append(ACTIVE_TRAINING_PROGRAMS)
        except Exception:
            pass
        programs = {}
        for src in sources:
            if not isinstance(src, dict):
                continue
            for pid, prog in src.items():
                if not isinstance(prog, dict):
                    continue
                norm = str(pid)
                if norm in programs:
                    continue
                programs[norm] = (pid, prog)
        entries = []
        for norm, (pid, prog) in programs.items():
            player = self._find_player(pid)
            entries.append({
                "pid": norm,
                "player": player,
                "name": (getattr(player, "full_name", "?") if player
                         else str(prog.get("player_name") or "?")),
                "focus": str(prog.get("focus") or "—"),
                "intensity": str(prog.get("intensity") or "—"),
                "assigned": self._date_str(prog.get("assigned")),
            })
        entries.sort(key=lambda e: (e["name"] or "").lower())
        return entries

    @staticmethod
    def _date_str(d):
        try:
            return d.strftime("%b %d, %Y")
        except Exception:
            return str(d) if d is not None else ""

    def _refresh_programs(self):
        self._clear(self._programs_list)
        self._programs = self._load_programs()
        if not self._programs:
            self._programs_list.addWidget(
                self._dim("No active training programs. Assign one below."))
            return
        count = QLabel(f"{len(self._programs)} active program(s)")
        count.setObjectName("section-header")
        self._programs_list.addWidget(count)
        for entry in self._programs:
            card = QFrame()
            card.setObjectName("tile")
            lay = QHBoxLayout(card)
            info = QVBoxLayout()
            nm = QLabel(entry["name"])
            nm.setStyleSheet(
                "color: #ffffff; font-size: 14px; font-weight: 700;")
            info.addWidget(nm)
            tags = QLabel(f"{entry['focus']} · {entry['intensity']}"
                          + (f" · since {entry['assigned']}"
                             if entry["assigned"] else ""))
            tags.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            tags.setWordWrap(True)
            info.addWidget(tags)
            lay.addLayout(info, 1)
            cancel = QPushButton("Cancel Program")
            cancel.setStyleSheet(
                "background-color: #7f1d1d; color: #fca5a5; "
                "border: none; border-radius: 6px; padding: 8px 14px;")
            cancel.setCursor(Qt.PointingHandCursor)
            cancel.clicked.connect(
                lambda _c=False, pid=entry["pid"]:
                self._cancel_program(pid))
            lay.addWidget(cancel)
            self._programs_list.addWidget(card)

    def _cancel_program(self, pid):
        removed = False
        gm, _team = self._gm_team()
        try:
            from enhanced_practice_system import ACTIVE_TRAINING_PROGRAMS
            sources = [ACTIVE_TRAINING_PROGRAMS]
        except Exception:
            sources = []
        if gm is not None:
            try:
                sources.append(getattr(gm, "training_programs", None))
            except Exception:
                pass
        try:
            sources.append(getattr(self.game, "training_programs", None))
        except Exception:
            pass
        for src in sources:
            if not isinstance(src, dict):
                continue
            for key in (pid, str(pid)):
                if key in src:
                    src.pop(key, None)
                    removed = True
        player = self._find_player(pid)
        name = getattr(player, "full_name", "?") if player else "?"
        QMessageBox.information(
            self, "Training Program",
            f"{name}'s training program "
            f"{'cancelled' if removed else 'was not active'}.")
        self.refresh()

    # ------------------------------------------------------------------
    # section: assign training program
    # ------------------------------------------------------------------
    def _build_assign_form(self, box):
        lay = box.layout()
        row = QHBoxLayout()
        row.addWidget(QLabel("Player"))
        self._assign_player = QComboBox()
        self._assign_player.setMinimumWidth(320)
        self._assign_player.currentIndexChanged.connect(
            self._update_assign_note)
        row.addWidget(self._assign_player, 1)
        lay.addLayout(row)

        focus_grp = QGroupBox("Training Focus")
        fgrid = QGridLayout(focus_grp)
        self._focus_btns = QButtonGroup(self)
        for i, f in enumerate(self.DEV_FOCUSES):
            rb = QRadioButton(f)
            if i == 0:
                rb.setChecked(True)
            self._focus_btns.addButton(rb, i)
            fgrid.addWidget(rb, i // 2, i % 2)
        lay.addWidget(focus_grp)

        int_grp = QGroupBox("Intensity")
        irow = QHBoxLayout(int_grp)
        self._int_btns = QButtonGroup(self)
        for i, iv in enumerate(self.DEV_INTENSITIES):
            rb = QRadioButton(iv)
            if iv == "Standard":
                rb.setChecked(True)
            self._int_btns.addButton(rb, i)
            irow.addWidget(rb)
        lay.addWidget(int_grp)

        btn_row = QHBoxLayout()
        self._assign_btn = QPushButton("Assign Training Program")
        self._assign_btn.setObjectName("primary-btn")
        self._assign_btn.setCursor(Qt.PointingHandCursor)
        self._assign_btn.clicked.connect(self._assign_program)
        btn_row.addWidget(self._assign_btn)
        self._assign_note = self._dim("", 12)
        btn_row.addWidget(self._assign_note, 1)
        lay.addLayout(btn_row)

    def _update_assign_note(self, _idx=None):
        player = self._assign_player.currentData()
        if player is None:
            self._assign_note.setText("")
            return
        eng = self._engine()
        fatigue = "?"
        if eng is not None:
            try:
                fatigue = eng.get_player_history(
                    getattr(player, "id", None)).current_fatigue
            except Exception:
                fatigue = "?"
        self._assign_note.setText(
            f"Fatigue {fatigue}% · Program runs weekly for 30 days; "
            "a first session runs immediately.")

    def _assign_program(self):
        """Web parity: /api/development/assign-program op -- records the
        program (gm.training_programs + ACTIVE_TRAINING_PROGRAMS) and runs
        a real first session immediately (desktop parity with
        _assign_training_confirmed)."""
        player = self._assign_player.currentData()
        if player is None:
            QMessageBox.warning(self, "Assign Program",
                                "Pick a player first.")
            return
        focus = self.DEV_FOCUSES[self._focus_btns.checkedId()] \
            if self._focus_btns.checkedId() >= 0 else ""
        intensity_label = self.DEV_INTENSITIES[self._int_btns.checkedId()] \
            if self._int_btns.checkedId() >= 0 else "Standard"
        if not focus:
            QMessageBox.warning(self, "Assign Program",
                                "Pick a training focus.")
            return
        try:
            from enhanced_practice_system import (
                FOCUS_TO_PRACTICE_TYPE, INTENSITY_LABEL_TO_ENUM,
                ACTIVE_TRAINING_PROGRAMS)
        except Exception as e:
            QMessageBox.warning(self, "Assign Program",
                                f"Training system unavailable: {e}")
            return
        if focus not in FOCUS_TO_PRACTICE_TYPE:
            QMessageBox.warning(self, "Assign Program",
                                f"Unknown focus: {focus}")
            return
        if intensity_label not in INTENSITY_LABEL_TO_ENUM:
            QMessageBox.warning(self, "Assign Program",
                                f"Unknown intensity: {intensity_label}")
            return
        ptype = FOCUS_TO_PRACTICE_TYPE[focus]
        pint = INTENSITY_LABEL_TO_ENUM[intensity_label]
        engine = self._engine()
        if engine is None:
            QMessageBox.warning(self, "Assign Program",
                                "Practice engine unavailable.")
            return
        try:
            can, why = engine.can_practice(player, ptype, pint)
        except Exception as e:
            QMessageBox.warning(self, "Assign Program",
                                f"Cannot check eligibility: {e}")
            return
        if not can:
            QMessageBox.warning(self, "Cannot Assign", str(why))
            return
        gm, _team = self._gm_team()
        try:
            prog = {
                "focus": focus,
                "intensity": intensity_label,
                "assigned": (getattr(self.game, "current_date", None)
                             or date.today()),
                "player_name": getattr(player, "full_name", "?"),
            }
            pkey = getattr(player, "id", None)
            ACTIVE_TRAINING_PROGRAMS[pkey] = prog
            if gm is not None:
                if not getattr(gm, "training_programs", None):
                    gm.training_programs = {}
                gm.training_programs[pkey] = prog
            # First session runs immediately (legacy flat trainer,
            # 60 min, quality 12) -- desktop parity.
            session = engine.execute_practice(player, ptype, pint, 60, 12)
            QMessageBox.information(
                self, "Training Program Assigned",
                f"{getattr(player, 'full_name', 'Player')} assigned to "
                f"{focus} ({intensity_label}).\nFirst session: "
                f"+{getattr(session, 'skill_gain', 0):.2f} skill, "
                f"+{getattr(session, 'fatigue_cost', 0)}% fatigue.")
        except Exception as e:
            QMessageBox.warning(self, "Assign Program",
                                f"Failed: {e}")
        self.refresh()

    # ------------------------------------------------------------------
    # section: practice center (per-player drills)
    # ------------------------------------------------------------------
    def _build_practice_form(self, box):
        lay = box.layout()
        row = QHBoxLayout()
        row.addWidget(QLabel("Player"))
        self._prac_player = QComboBox()
        self._prac_player.setMinimumWidth(220)
        row.addWidget(self._prac_player, 1)
        row.addWidget(QLabel("Drill"))
        self._prac_drill = QComboBox()
        row.addWidget(self._prac_drill, 1)
        row.addWidget(QLabel("Intensity"))
        self._prac_intensity = QComboBox()
        row.addWidget(self._prac_intensity, 1)
        lay.addLayout(row)

        # Trains + cost/eligibility preview (live, updated on every change)
        prev = QGridLayout()
        prev.addWidget(QLabel("Trains"), 0, 0)
        self._prac_trains = self._dim("", 12)
        prev.addWidget(self._prac_trains, 0, 1)
        prev.addWidget(QLabel("Cost"), 1, 0)
        self._prac_cost = self._dim("", 12)
        prev.addWidget(self._prac_cost, 1, 1)
        prev.addWidget(QLabel("Eligibility"), 2, 0)
        self._prac_elig = QLabel("")
        self._prac_elig.setStyleSheet("font-size: 13px; font-weight: 700;")
        self._prac_elig.setWordWrap(True)
        prev.addWidget(self._prac_elig, 2, 1)
        lay.addLayout(prev)
        self._prac_current = self._dim("", 12)
        lay.addWidget(self._prac_current)

        sched = QHBoxLayout()
        sched.addWidget(QLabel("Sessions per week"))
        self._prac_per_week = QSpinBox()
        self._prac_per_week.setRange(1, 7)
        self._prac_per_week.setValue(3)
        sched.addWidget(self._prac_per_week)
        sched.addWidget(QLabel("Weeks"))
        self._prac_weeks = QSpinBox()
        self._prac_weeks.setRange(1, 12)
        self._prac_weeks.setValue(4)
        sched.addWidget(self._prac_weeks)
        sched.addStretch()
        lay.addLayout(sched)

        btns = QHBoxLayout()
        self._prac_run = QPushButton("Run Single Session")
        self._prac_run.setObjectName("primary-btn")
        self._prac_run.setCursor(Qt.PointingHandCursor)
        self._prac_sched = QPushButton("Start Schedule")
        self._prac_stop = QPushButton("Stop Schedule")
        self._prac_stop.setStyleSheet(
            "background-color: #7f1d1d; color: #fca5a5; "
            "border: none; border-radius: 6px; padding: 8px 14px;")
        self._prac_coach = QPushButton("Coach Runs Practice")
        self._prac_coach.setStyleSheet(
            "background-color: #3B82F6; color: #ffffff; "
            "border: none; border-radius: 6px; padding: 8px 14px;")
        for b in (self._prac_run, self._prac_sched, self._prac_stop,
                  self._prac_coach):
            b.setCursor(Qt.PointingHandCursor)
        self._prac_run.clicked.connect(self._practice_run)
        self._prac_sched.clicked.connect(self._practice_schedule)
        self._prac_stop.clicked.connect(self._practice_stop)
        self._prac_coach.clicked.connect(self._coach_runs_practice)
        for b in (self._prac_run, self._prac_sched, self._prac_stop,
                  self._prac_coach):
            btns.addWidget(b)
        btns.addStretch()
        lay.addLayout(btns)

        # Live eligibility preview updates on every change.
        for combo in (self._prac_player, self._prac_drill,
                      self._prac_intensity):
            combo.currentIndexChanged.connect(self._update_practice_preview)

    def _practice_catalog(self):
        """(drills, intensities, fatigue_costs) -- web parity:
        _dev_practice_catalog."""
        PracticeType, PracticeIntensity = self._enums()
        engine = self._engine()
        if PracticeType is None or PracticeIntensity is None:
            return [], [], {}
        drills = []
        for pt in PracticeType:
            attrs = []
            if engine is not None:
                try:
                    eff = engine.practice_effectiveness.get(pt) or {}
                    attrs = sorted(eff.keys())
                except Exception:
                    attrs = []
            drills.append({
                "key": pt.value,
                "label": pt.value.replace("_", " ").title(),
                "trains": attrs[:6],
            })
        intensities = [pi.value for pi in PracticeIntensity]
        costs = {}
        if engine is not None:
            for pi in PracticeIntensity:
                try:
                    costs[pi.value] = engine._calculate_fatigue_cost(pi, 60)
                except Exception:
                    pass
        return drills, intensities, costs

    def _refresh_practice_catalog(self):
        drills, intensities, self._prac_costs = self._practice_catalog()
        keep_d = self._prac_drill.currentData()
        keep_i = self._prac_intensity.currentData()
        self._prac_drill.blockSignals(True)
        self._prac_intensity.blockSignals(True)
        self._prac_drill.clear()
        self._prac_intensity.clear()
        for d in drills:
            self._prac_drill.addItem(d["label"], d["key"])
        for iv in intensities:
            self._prac_intensity.addItem(
                iv[0].upper() + iv[1:], iv)
        if keep_d:
            idx = self._prac_drill.findData(keep_d)
            if idx >= 0:
                self._prac_drill.setCurrentIndex(idx)
        if keep_i:
            idx = self._prac_intensity.findData(keep_i)
            if idx >= 0:
                self._prac_intensity.setCurrentIndex(idx)
        else:
            # Default like the web: moderate
            idx = self._prac_intensity.findData("moderate")
            if idx >= 0:
                self._prac_intensity.setCurrentIndex(idx)
        self._prac_drill.blockSignals(False)
        self._prac_intensity.blockSignals(False)
        self._prac_drills = {d["key"]: d for d in drills}
        engine_ok = self._engine() is not None
        for b in (self._prac_run, self._prac_sched, self._prac_stop):
            b.setEnabled(engine_ok)
        if not engine_ok:
            self._prac_elig.setText(
                "Practice engine unavailable in this environment.")
            self._prac_elig.setStyleSheet(
                "color: #eab308; font-size: 13px;")

    def _update_practice_preview(self, _idx=None):
        """Live eligibility indicator (check/cross) on every change --
        calls engine.can_practice directly (side-effect-free)."""
        eng = self._engine()
        if eng is None:
            return
        PracticeType, PracticeIntensity = self._enums()
        player = self._prac_player.currentData()
        drill_key = self._prac_drill.currentData()
        int_key = self._prac_intensity.currentData()
        d = getattr(self, "_prac_drills", {}).get(drill_key, {})
        self._prac_trains.setText(", ".join(d.get("trains", [])) or "—")
        # Current schedule
        sched_txt = ""
        fatigue = "?"
        if player is not None:
            try:
                history = eng.get_player_history(getattr(player, "id", None))
                fatigue = int(getattr(history, "current_fatigue", 0) or 0)
                schedule = getattr(history, "current_schedule", None)
                if schedule:
                    try:
                        sched_txt = (
                            f"{schedule['type'].value.replace('_', ' ').title()} "
                            f"({schedule['intensity'].value}) - "
                            f"{schedule['sessions_remaining']} left")
                    except Exception:
                        sched_txt = "active"
            except Exception:
                pass
        self._prac_current.setText(
            f"Current schedule: {sched_txt}" if sched_txt else "")
        if player is None or drill_key is None or int_key is None:
            self._prac_elig.setText("")
            self._prac_cost.setText("")
            return
        cost = self._prac_costs.get(int_key) if hasattr(
            self, "_prac_costs") else None
        try:
            drill = PracticeType(str(drill_key))
            pint = PracticeIntensity(str(int_key))
            can, why = eng.can_practice(player, drill, pint)
            fatigue_cost = eng._calculate_fatigue_cost(pint, 60)
        except Exception as e:
            can, why, fatigue_cost = False, str(e), cost
        self._prac_cost.setText(
            f"+{fatigue_cost if fatigue_cost is not None else '?'}% "
            f"fatigue (now {fatigue}%)")
        if can:
            self._prac_elig.setText(f"✓ {why or 'Ready to practice'}")
            self._prac_elig.setStyleSheet(
                "color: #22c55e; font-size: 13px; font-weight: 700;")
        else:
            self._prac_elig.setText(f"✗ {why or 'Unavailable.'}")
            self._prac_elig.setStyleSheet(
                "color: #ef4444; font-size: 13px; font-weight: 700;")

    def _practice_run(self):
        """Web parity: run_practice_session op -- one real per-player
        drill through the engine with coaching staff."""
        player = self._prac_player.currentData()
        if player is None:
            QMessageBox.warning(self, "Practice",
                                "Pick a player first.")
            return
        eng = self._engine()
        PracticeType, PracticeIntensity = self._enums()
        if eng is None or PracticeType is None:
            QMessageBox.warning(self, "Practice",
                                "Practice engine unavailable.")
            return
        try:
            drill = PracticeType(str(self._prac_drill.currentData()))
            pint = PracticeIntensity(str(self._prac_intensity.currentData()))
        except Exception as e:
            QMessageBox.warning(self, "Practice",
                                f"Unknown drill/intensity: {e}")
            return
        try:
            can, why = eng.can_practice(player, drill, pint)
        except Exception as e:
            QMessageBox.warning(self, "Practice", f"Cannot check: {e}")
            return
        if not can:
            QMessageBox.warning(self, "Cannot Practice", str(why))
            return
        try:
            gm, team = self._gm_team()
            coach_team = self._player_team(team, player)
            session = eng.execute_practice(
                player, drill, pint, 60, 10, team=coach_team)
            gains = ""
            try:
                bd = getattr(session, "breakdown", None) or {}
                coach = bd.get("coach_name") or ""
                gains = f" ({coach} ran it)" if coach else ""
            except Exception:
                pass
            QMessageBox.information(
                self, "Practice Complete",
                f"{getattr(player, 'full_name', 'Player')}: "
                f"{drill.value.replace('_', ' ').title()} "
                f"({pint.value}) complete{gains}. "
                f"+{getattr(session, 'skill_gain', 0):.2f} skill, "
                f"+{getattr(session, 'fatigue_cost', 0)}% fatigue.")
        except Exception as e:
            QMessageBox.warning(self, "Practice", f"Failed: {e}")
        self.refresh()

    def _practice_schedule(self):
        eng = self._engine()
        PracticeType, PracticeIntensity = self._enums()
        player = self._prac_player.currentData()
        if player is None:
            QMessageBox.warning(self, "Practice",
                                "Pick a player first.")
            return
        if eng is None or PracticeType is None:
            QMessageBox.warning(self, "Practice",
                                "Practice engine unavailable.")
            return
        try:
            drill = PracticeType(str(self._prac_drill.currentData()))
            pint = PracticeIntensity(str(self._prac_intensity.currentData()))
        except Exception as e:
            QMessageBox.warning(self, "Practice",
                                f"Unknown drill/intensity: {e}")
            return
        total = max(1, min(84, self._prac_per_week.value()
                           * self._prac_weeks.value()))
        try:
            result = eng.schedule_practice(player, drill, pint, total)
        except Exception as e:
            QMessageBox.warning(self, "Practice", f"Failed: {e}")
            return
        if getattr(result, "success", False):
            QMessageBox.information(self, "Practice Scheduled",
                                    str(getattr(result, "message",
                                                "Schedule started.")))
        else:
            QMessageBox.warning(self, "Schedule Failed",
                                str(getattr(result, "message",
                                            "Unknown error")))
        self.refresh()

    def _practice_stop(self):
        eng = self._engine()
        player = self._prac_player.currentData()
        if player is None or eng is None:
            return
        try:
            eng.stop_practice_schedule(player)
            QMessageBox.information(
                self, "Practice Stopped",
                f"{getattr(player, 'full_name', 'Player')}'s practice "
                "schedule stopped.")
        except Exception as e:
            QMessageBox.warning(self, "Practice", f"Failed: {e}")
        self.refresh()

    def _coach_runs_practice(self):
        """Headline button: weakness-targeted drills + fatigue-aware
        intensity for the whole roster via the real auto_resolve entry
        point -- the same call PracticeCenterScreen uses."""
        gm, team = self._gm_team()
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

    # ------------------------------------------------------------------
    # section: positional training
    # ------------------------------------------------------------------
    def _build_position_form(self, box):
        lay = box.layout()
        row = QHBoxLayout()
        row.addWidget(QLabel("Player"))
        self._pos_player = QComboBox()
        self._pos_player.setMinimumWidth(320)
        self._pos_player.currentIndexChanged.connect(self._render_pos_fam)
        row.addWidget(self._pos_player, 1)
        lay.addLayout(row)

        lay.addWidget(QLabel("Familiarity"))
        self._pos_fam = QWidget()
        self._pos_fam_lay = QVBoxLayout(self._pos_fam)
        self._pos_fam_lay.setContentsMargins(0, 0, 0, 0)
        self._pos_fam_lay.setSpacing(6)
        self._pos_target_btns = QButtonGroup(self)
        lay.addWidget(self._pos_fam)

        self._pos_note = self._dim(
            "Young, high-IQ players learn fastest. Diminishing returns "
            "near 100.", 12)
        lay.addWidget(self._pos_note)

        self._pos_train_btn = QPushButton("Run Training Session")
        self._pos_train_btn.setObjectName("primary-btn")
        self._pos_train_btn.setCursor(Qt.PointingHandCursor)
        self._pos_train_btn.clicked.connect(self._position_train)
        lay.addWidget(self._pos_train_btn)

    def _render_pos_fam(self, _idx=None):
        self._clear(self._pos_fam_lay)
        for btn in list(self._pos_target_btns.buttons()):
            self._pos_target_btns.removeButton(btn)
        player = self._pos_player.currentData()
        if player is None:
            self._pos_fam_lay.addWidget(
                self._dim("No player selected.", 12))
            return
        try:
            import position_training as _pt
        except Exception as e:
            self._pos_fam_lay.addWidget(
                self._dim(f"Position training unavailable: {e}", 12))
            return
        try:
            primary = str(getattr(player, "primary_position", "") or "")
            try:
                pp = getattr(player, "primary_position", None)
                primary = (pp.value if hasattr(pp, "value") else primary)
            except Exception:
                pass
            eligible = _pt.eligible_training_positions(player)
            target = str(
                getattr(player, "position_training_target", "") or "")
        except Exception as e:
            self._pos_fam_lay.addWidget(
                self._dim(f"Could not load familiarity: {e}", 12))
            return
        if not eligible:
            self._pos_note.setText("Goalies cannot train skater positions.")
            self._pos_fam_lay.addWidget(
                self._dim("No trainable positions.", 12))
            return
        self._pos_note.setText(
            f"Primary {primary}. Young, high-IQ players learn fastest. "
            "Diminishing returns near 100.")
        for pos in eligible:
            try:
                v = float(_pt.get_familiarity(player, pos))
            except Exception:
                v = 0.0
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rb = QRadioButton(pos)
            if target == pos:
                rb.setChecked(True)
            self._pos_target_btns.addButton(rb)
            rl.addWidget(rb)
            bar = AttributeBar("", v)
            rl.addWidget(bar, 1)
            badge = QLabel("TRAINING" if target == pos else "")
            badge.setStyleSheet(
                "color: #3B82F6; font-size: 11px; font-weight: 700;")
            rl.addWidget(badge)
            self._pos_fam_lay.addWidget(row)

    def _position_train(self):
        """Web parity: assign_position_training op -- one real session
        toward the target position, persisted on
        player.position_familiarity."""
        player = self._pos_player.currentData()
        if player is None:
            QMessageBox.warning(self, "Positional Training",
                                "Pick a player first.")
            return
        btn = self._pos_target_btns.checkedButton()
        target = btn.text() if btn is not None else ""
        if not target:
            QMessageBox.warning(self, "Positional Training",
                                "Pick a target position.")
            return
        try:
            import position_training as _pt
        except Exception as e:
            QMessageBox.warning(self, "Positional Training",
                                f"Position training unavailable: {e}")
            return
        try:
            eligible = _pt.eligible_training_positions(player)
        except Exception as e:
            QMessageBox.warning(self, "Positional Training",
                                f"Could not check eligibility: {e}")
            return
        if target.upper() not in [str(x).upper() for x in eligible]:
            QMessageBox.warning(
                self, "Positional Training",
                f"{target} is not a trainable position for this player.")
            return
        gm, team = self._gm_team()
        try:
            old_fam = _pt.get_familiarity(player, target)
            cq = self._coaching_quality(team)
            new_fam, gain = _pt.train_position(player, target, cq)
            try:
                player.position_training_target = target
            except Exception:
                pass
            QMessageBox.information(
                self, "Positional Training",
                f"{getattr(player, 'full_name', 'Player')}: {target} "
                f"familiarity {old_fam:.0f} → {new_fam:.0f} "
                f"(+{gain:.1f} this session).")
        except Exception as e:
            QMessageBox.warning(self, "Positional Training",
                                f"Failed: {e}")
        self.refresh()

    # ------------------------------------------------------------------
    # section: offseason programs (inline panel, seasonal)
    # ------------------------------------------------------------------
    def _offseason_gate(self):
        """Web parity: _dev_offseason -- assignable Jun-Aug."""
        try:
            import offseason_programs as _osp
            gm, _team = self._gm_team()
            game_date = (getattr(self.game, "current_date", None)
                         or getattr(gm, "current_date", None)
                         or date.today())
            return {"assignable": bool(_osp.is_offseason(game_date)),
                    "month": int(getattr(game_date, "month", 0) or 0)}
        except Exception:
            return {"assignable": False, "month": 0}

    def _refresh_offseason(self):
        self._clear(self._off_list)
        gate = self._offseason_gate()
        if not gate["assignable"]:
            self._off_list.addWidget(self._dim(
                "Offseason programs unlock June–August. Assign one focus "
                "per player for the summer; weekly development runs "
                "July–August and shows up in camp reports.", 13))
            return
        try:
            import offseason_programs as _osp
        except Exception as e:
            self._off_list.addWidget(
                self._dim(f"Offseason module unavailable: {e}", 12))
            return
        row = QHBoxLayout()
        row.addWidget(QLabel("Player"))
        self._off_player = QComboBox()
        self._off_player.setMinimumWidth(220)
        row.addWidget(self._off_player, 1)
        row.addWidget(QLabel("Focus"))
        self._off_focus = QComboBox()
        for f in self.DEV_FOCUSES:
            self._off_focus.addItem(f)
        row.addWidget(self._off_focus, 1)
        row.addWidget(QLabel("Intensity"))
        self._off_int = QComboBox()
        for iv in self.DEV_INTENSITIES:
            self._off_int.addItem(iv)
        self._off_int.setCurrentText("Standard")
        row.addWidget(self._off_int, 1)
        form = QWidget()
        form.setLayout(row)
        self._off_list.addWidget(form)

        self._off_note = self._dim("", 12)
        self._off_list.addWidget(self._off_note)
        self._fill_player_combo(self._off_player)
        self._off_player.currentIndexChanged.connect(
            self._update_offseason_note)
        self._update_offseason_note()

        btns = QHBoxLayout()
        assign = QPushButton("Assign Summer Program")
        assign.setObjectName("primary-btn")
        assign.setCursor(Qt.PointingHandCursor)
        assign.clicked.connect(
            lambda: self._offseason_assign(_osp))
        clear = QPushButton("Clear Program")
        clear.setStyleSheet(
            "background-color: #7f1d1d; color: #fca5a5; "
            "border: none; border-radius: 6px; padding: 8px 14px;")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(lambda: self._offseason_clear(_osp))
        btns.addWidget(assign)
        btns.addWidget(clear)
        btns.addStretch()
        bw = QWidget()
        bw.setLayout(btns)
        self._off_list.addWidget(bw)

    def _update_offseason_note(self, _idx=None):
        player = getattr(self, "_off_player", None)
        note = getattr(self, "_off_note", None)
        if player is None or note is None:
            return
        try:
            import offseason_programs as _osp
            p = player.currentData()
            osp = _osp.get_offseason_program(p) if p else None
            note.setText(
                f"{getattr(p, 'full_name', '')}: {osp.get('focus')} "
                f"({osp.get('intensity')})"
                if isinstance(osp, dict) else "")
        except Exception:
            note.setText("")

    def _offseason_assign(self, _osp):
        player = self._off_player.currentData()
        if player is None:
            QMessageBox.warning(self, "Offseason Program",
                                "Pick a player first.")
            return
        gm, _team = self._gm_team()
        game_date = (getattr(self.game, "current_date", None)
                     or getattr(gm, "current_date", None)
                     or date.today())
        if not _osp.is_offseason(game_date):
            QMessageBox.warning(
                self, "Offseason Program",
                "Offseason programs can only be assigned June–August.")
            return
        try:
            ok, msg = _osp.assign_offseason_program(
                player, self._off_focus.currentText(),
                self._off_int.currentText(), on_date=game_date)
        except Exception as e:
            ok, msg = False, str(e)
        if ok:
            QMessageBox.information(self, "Offseason Program", str(msg))
        else:
            QMessageBox.warning(self, "Offseason Program",
                                str(msg or "Failed."))
        self.refresh()

    def _offseason_clear(self, _osp):
        player = self._off_player.currentData()
        if player is None:
            return
        try:
            _osp.clear_offseason_program(player)
            QMessageBox.information(
                self, "Offseason Program",
                f"{getattr(player, 'full_name', 'Player')}'s summer "
                "program cleared.")
        except Exception as e:
            QMessageBox.warning(self, "Offseason Program",
                                f"Failed: {e}")
        self.refresh()

    # ------------------------------------------------------------------
    # section: development analytics
    # ------------------------------------------------------------------
    def _build_analytics_form(self, box):
        lay = box.layout()
        self._an_overview = QHBoxLayout()
        lay.addLayout(self._an_overview)

        cards = QHBoxLayout()
        self._an_positions = QVBoxLayout()
        self._an_ages = QVBoxLayout()
        pos_card = QGroupBox("Position Analysis")
        pos_card.setLayout(self._an_positions)
        age_card = QGroupBox("Age Distribution")
        age_card.setLayout(self._an_ages)
        cards.addWidget(pos_card, 1)
        cards.addWidget(age_card, 1)
        lay.addLayout(cards)

        filt = QHBoxLayout()
        self._an_search = QLineEdit()
        self._an_search.setPlaceholderText("Search player…")
        self._an_search.textChanged.connect(
            lambda _t: self._render_analytics())
        filt.addWidget(self._an_search, 1)
        self._an_squad = QComboBox()
        for s in ("all", "NHL", "AHL", "Prospect"):
            self._an_squad.addItem("All squads" if s == "all" else s, s)
        self._an_squad.currentIndexChanged.connect(
            lambda _i: self._render_analytics())
        filt.addWidget(self._an_squad)
        self._an_recs = QCheckBox("Only players with recommendations")
        self._an_recs.stateChanged.connect(
            lambda _s: self._render_analytics())
        filt.addWidget(self._an_recs)
        lay.addLayout(filt)

        self._an_cards = QWidget()
        self._an_cards_lay = QVBoxLayout(self._an_cards)
        self._an_cards_lay.setContentsMargins(0, 0, 0, 0)
        self._an_cards_lay.setSpacing(10)
        lay.addWidget(self._an_cards)

    @staticmethod
    def _dev_pos_group(p):
        """Primary position -> desktop key-attribute group (web parity)."""
        try:
            pos = getattr(p, "primary_position", None)
            v = str(getattr(pos, "value", pos) or "").upper()
        except Exception:
            v = ""
        if v in ("C", "CENTER"):
            return "C"
        if v in ("LW", "LEFT_WING"):
            return "LW"
        if v in ("RW", "RIGHT_WING"):
            return "RW"
        if v in ("D", "LD", "RD", "DEFENSE", "DEFENCE", "DEFENSEMAN"):
            return "D"
        if v in ("G", "GOALIE", "GOALTENDER"):
            return "G"
        return "C"

    @staticmethod
    def _dev_grade(value):
        """100-scale letter grade (desktop's 20-scale grades x5)."""
        if value >= 90:
            return "A+"
        if value >= 80:
            return "A"
        if value >= 70:
            return "B+"
        if value >= 60:
            return "B"
        if value >= 50:
            return "C+"
        if value >= 40:
            return "C"
        return "D"

    @staticmethod
    def _dev_recommendations(p, key_attrs):
        """Desktop _generate_recommendations parity: weakness-first,
        age and position aware, top 3 with HIGH/MED/LOW priority."""
        recs = []
        vals = []
        for attr in key_attrs:
            try:
                v = int(getattr(p, attr, 50) or 50)
            except Exception:
                v = 50
            vals.append((attr, v))
        vals.sort(key=lambda x: x[1])
        if vals:
            lowest_attr, lowest_val = vals[0]
            if lowest_val < 70:
                recs.append({
                    "area": lowest_attr.replace("_", " ").title(),
                    "reason": f"Currently {lowest_val}/100 -- below "
                              "team standard",
                })
        try:
            age = int(getattr(p, "age", 26) or 26)
        except Exception:
            age = 26
        if age <= 20:
            recs.append({"area": "Intensive Training",
                         "reason": "Young age allows for rapid development"})
        elif age >= 30:
            recs.append({"area": "Maintenance Focus",
                         "reason": "Prevent attribute decline due to age"})
        if DevelopmentScreen._dev_pos_group(p) == "G":
            try:
                mt = int(getattr(p, "mental_toughness", 50) or 50)
            except Exception:
                mt = 50
            if mt < 75:
                recs.append({"area": "Mental Training",
                             "reason": "Critical for goalie consistency"})
        prios = ["HIGH", "MED", "LOW"]
        out = []
        for i, r in enumerate(recs[:3]):
            r = dict(r)
            r["priority"] = prios[i] if i < len(prios) else "LOW"
            out.append(r)
        return out

    def _load_analytics(self):
        """Web parity: api_development_analytics payload."""
        roster, ahl, prospects = self._squads()
        all_players = list(roster) + list(ahl) + list(prospects)
        total = len(all_players)
        overview = {
            "total_players": total,
            "avg_age": round(sum(getattr(p, "age", 0) or 0
                                 for p in all_players) / total, 1)
            if total else 0,
            "avg_potential": round(sum(getattr(p, "potential", 50) or 50
                                       for p in all_players) / total, 1)
            if total else 0,
        }
        pos_groups = {}
        for p in all_players:
            pos_groups.setdefault(self._dev_pos_group(p), []).append(p)
        positions = []
        for g in ("C", "LW", "RW", "D", "G"):
            ps = pos_groups.get(g, [])
            if not ps:
                continue
            positions.append({
                "position": g, "count": len(ps),
                "avg_potential": round(sum(getattr(p, "potential", 50) or 50
                                           for p in ps) / len(ps), 1),
            })
        age_bands = []
        for label, lo, hi in (("18-22", 18, 22), ("23-25", 23, 25),
                              ("26-29", 26, 29), ("30+", 30, 99)):
            n = sum(1 for p in all_players
                    if lo <= (getattr(p, "age", 0) or 0) <= hi)
            age_bands.append({"band": label, "count": n})
        ahl_ids = {id(p) for p in ahl}
        prospect_ids = {id(p) for p in prospects}
        players = []
        for p in all_players:
            try:
                g = self._dev_pos_group(p)
                key_attrs = self.DEV_KEY_ATTRS[g]
                attrs = []
                for attr in key_attrs:
                    try:
                        from game_classes import to_100_scale
                        v = int(to_100_scale(getattr(p, attr, 50)))
                    except Exception:
                        v = 50
                    attrs.append({
                        "name": attr.replace("_", " ").title(),
                        "value": v, "grade": self._dev_grade(v)})
                pid = id(p)
                players.append({
                    "id": getattr(p, "id", None),
                    "name": getattr(p, "full_name", "?"),
                    "position": self._pos_str(p),
                    "age": getattr(p, "age", "?"),
                    "overall": self._ovr(p),
                    "squad": ("AHL" if pid in ahl_ids
                              else "Prospect" if pid in prospect_ids
                              else "NHL"),
                    "key_attributes": attrs,
                    "recommendations": self._dev_recommendations(
                        p, key_attrs),
                })
            except Exception:
                continue
        players.sort(key=lambda e: (
            e.get("age") if isinstance(e.get("age"), int) else 99,
            -(e.get("overall") if isinstance(e.get("overall"), int)
               else 0)))
        return {"overview": overview, "positions": positions,
                "age_bands": age_bands, "players": players}

    def _refresh_analytics(self):
        self._analytics = self._load_analytics()
        self._clear(self._an_overview)
        o = self._analytics["overview"]
        for val, lbl in ((o.get("total_players", 0), "Total players"),
                         (o.get("avg_age", 0), "Average age"),
                         (o.get("avg_potential", 0), "Average potential")):
            stat = QVBoxLayout()
            v = QLabel(str(val))
            v.setStyleSheet(
                "color: #ffffff; font-size: 22px; font-weight: 800;")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(lbl)
            l.setStyleSheet("color: #9aa4b8; font-size: 11px;")
            l.setAlignment(Qt.AlignCenter)
            stat.addWidget(v)
            stat.addWidget(l)
            self._an_overview.addLayout(stat, 1)
        self._clear(self._an_positions)
        for p in self._analytics["positions"]:
            self._an_positions.addWidget(self._dim(
                f"{p['position']}: {p['count']} players · "
                f"Pot {p['avg_potential']}", 12))
        if not self._analytics["positions"]:
            self._an_positions.addWidget(self._dim("No data.", 12))
        self._clear(self._an_ages)
        tot = o.get("total_players") or 1
        for b in self._analytics["age_bands"]:
            self._an_ages.addWidget(self._dim(
                f"{b['band']}: {b['count']} players "
                f"({round(b['count'] / tot * 100)}%)", 12))
        self._render_analytics()

    def _render_analytics(self):
        """Filter pipeline over cached analytics (web parity)."""
        self._clear(self._an_cards_lay)
        d = self._analytics
        q = (self._an_search.text() or "").lower()
        squad = self._an_squad.currentData() or "all"
        only_recs = self._an_recs.isChecked()
        prio_colors = {"HIGH": "#F44336", "MED": "#FFC107", "LOW": "#3B82F6"}
        shown = 0
        for p in d["players"]:
            if q and q not in (p["name"] or "").lower():
                continue
            if squad != "all" and p["squad"] != squad:
                continue
            if only_recs and not p["recommendations"]:
                continue
            if shown >= 40:
                break
            shown += 1
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            head = QLabel(
                f"{p['name']} · {p['position']} · Age {p['age']} · "
                f"OVR {p['overall']} · {p['squad']}")
            head.setStyleSheet(
                "color: #ffffff; font-size: 14px; font-weight: 700;")
            head.setWordWrap(True)
            cl.addWidget(head)
            for a in p["key_attributes"]:
                bar = AttributeBar(
                    f"{a['name']} ({a['grade']})", a["value"])
                cl.addWidget(bar)
            if p["recommendations"]:
                recs = QVBoxLayout()
                rt = QLabel("Development Focus Recommendations")
                rt.setStyleSheet(
                    "color: #3B82F6; font-size: 12px; font-weight: 700;")
                recs.addWidget(rt)
                for r in p["recommendations"]:
                    c = prio_colors.get(r["priority"], "#9aa4b8")
                    recs.addWidget(self._dim(
                        f"[{r['priority']}] {r['area']}: {r['reason']}",
                        12))
                    recs.itemAt(recs.count() - 1).widget().setStyleSheet(
                        f"color: #c8d1e0; font-size: 12px; "
                        f"border-left: 3px solid {c}; padding-left: 6px;")
                rw = QWidget()
                rw.setLayout(recs)
                cl.addWidget(rw)
            else:
                cl.addWidget(self._dim(
                    "No recommendations — a balanced profile.", 11))
            self._an_cards_lay.addWidget(card)
        if shown == 0:
            self._an_cards_lay.addWidget(self._dim("No players match.", 13))

    # ------------------------------------------------------------------
    # section: prospect watchlist
    # ------------------------------------------------------------------
    def _refresh_prospects(self):
        self._clear(self._prospects_list)
        roster, ahl, prospects = self._squads()
        ahl_ids = {id(p) for p in ahl}
        in_program = {str(getattr(p, "id", None))
                      for e in self._programs for p in ()}
        in_program |= {e["pid"] for e in self._programs}
        young = []
        for p in list(roster) + list(ahl):
            try:
                age = int(getattr(p, "age", 99) or 99)
            except Exception:
                age = 99
            if age <= 23:
                young.append(p)
        young.sort(key=lambda p: (
            -(self._ovr(p) if isinstance(self._ovr(p), int) else 0)))
        if not young:
            self._prospects_list.addWidget(
                self._dim("No young prospects on the roster.", 13))
            return
        for p in young[:12]:
            pid = id(p)
            squad = "AHL" if pid in ahl_ids else "NHL"
            row = QHBoxLayout()
            badge = QLabel(f"{squad}")
            badge.setStyleSheet(
                "background-color: #1e3a5f; color: #7fb3e8; "
                "font-size: 10px; font-weight: 700; border-radius: 4px; "
                "padding: 3px 8px;")
            nm = QLabel(f"{getattr(p, 'full_name', '?')} "
                        f"({self._pos_str(p)}) · Age {getattr(p, 'age', '?')} "
                        f"· OVR {self._ovr(p)}")
            nm.setStyleSheet("color: #e6ebf4; font-size: 13px;")
            prog = QLabel("IN PROGRAM" if str(
                getattr(p, "id", None)) in in_program else "")
            prog.setStyleSheet(
                "color: #22c55e; font-size: 11px; font-weight: 700;")
            row.addWidget(badge)
            row.addWidget(nm, 1)
            row.addWidget(prog)
            w = QWidget()
            w.setLayout(row)
            self._prospects_list.addWidget(w)

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------
    def refresh(self):
        try:
            roster, ahl, prospects = self._squads()
            ahl_ids = {id(p) for p in ahl}
            prospect_ids = {id(p) for p in prospects}
            self._all_players = []
            for p in list(roster) + list(ahl) + list(prospects):
                pid = id(p)
                squad = ("AHL" if pid in ahl_ids
                         else "Prospect" if pid in prospect_ids else "NHL")
                self._all_players.append((p, squad))
            self._all_players.sort(
                key=lambda e: str(getattr(e[0], "full_name", "?")).lower())

            for combo in (self._assign_player, self._prac_player,
                          self._pos_player):
                keep = combo.currentData()
                self._fill_player_combo(combo)
                if keep is not None:
                    idx = combo.findData(keep)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

            self._refresh_programs()
            self._refresh_practice_catalog()
            self._update_practice_preview()
            self._update_assign_note()
            self._render_pos_fam()
            self._refresh_offseason()
            self._refresh_analytics()
            self._refresh_prospects()
            self._status.setText("")
        except Exception as e:
            self._status.setText(f"Could not load development data: {e}")
