"""Manager Hub — the GM dashboard.

Native port of web_ui/screens/manager.py + manager.js (itself a port of
manager_hub_window.py, season_goals.py, gm_relationships_window.py and
analytics_hub.py). All reads are direct Python calls on the game object;
writes (set expectation, request patience) call the real board methods.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QProgressBar, QGridLayout, QFrame,
    QScrollArea, QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# Rough full-season point targets per expectation (estimates, labeled as
# such -- ported from manager_hub_window.ManagerHubView._EXPECTATION_TARGETS).
_EXPECTATION_TARGETS = {
    "win_cup": (108, "roughly 108+ points — a top seed and a full Cup run"),
    "contend": (100, "roughly 100+ points — a top-four seed for a deep run"),
    "playoffs": (94, "roughly 94+ points — the usual playoff cutoff range"),
    "rebuild": (None, "no points target — player development is the goal"),
}

_VERDICT_STYLE = {
    "preseason": ("#6b7488", "Preseason"),
    "rebuild": ("#8BC34A", "Rebuilding"),
    "on_track": ("#4CAF50", "On track"),
    "within_reach": ("#FF9800", "Within reach"),
    "off_the_pace": ("#F44336", "Off the pace"),
}

_GOAL_STATUS_STYLE = {
    "hit": ("#4CAF50", "Hit"),
    "on_track": ("#8BC34A", "On track"),
    "at_risk": ("#FF9800", "At risk"),
    "behind": ("#F44336", "Behind"),
    "preseason": ("#6b7488", "Preseason"),
}

_TREND_ARROW = {"warming": "\u2191", "cooling": "\u2193", "steady": "\u2192"}


class _NumericItem(QTableWidgetItem):
    """Table item that sorts numerically on its stored value."""

    def __init__(self, text, value):
        super().__init__(text)
        try:
            self.setData(Qt.UserRole, float(value))
        except Exception:
            self.setData(Qt.UserRole, 0.0)

    def __lt__(self, other):
        try:
            return (self.data(Qt.UserRole)
                    < other.data(Qt.UserRole))
        except Exception:
            return super().__lt__(other)


def _section(title):
    """Section container with a theme header."""
    box = QFrame()
    box.setObjectName("tile")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(8)
    head = QLabel(title.upper())
    head.setObjectName("section-header")
    lay.addWidget(head)
    return box, lay


def _pill(text, color):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"background: {color}22; color: {color}; "
                      f"border: 1px solid {color}; border-radius: 10px; "
                      f"padding: 2px 10px; font-size: 12px; font-weight: 700;")
    return lbl


class ManagerScreen(BaseScreen):
    """GM hub: board, season goals summary, analytics, relationships,
    profile, press."""

    title = "Manager"

    def __init__(self, game, main_window, parent=None):
        self._exp_combo = None
        self._rels_table = None
        self._rels_rows = []
        self._squad_table = None
        # Weekly training schedule widgets (rebuilt by refresh()).
        self._training_preset_combo = None
        self._training_unit_combos = {}
        self._training_effects = None
        # Active press-conference session: survives refresh() so a presser
        # is parked (not lost) when the user navigates away and back.
        self._presser = None
        super().__init__(game, main_window, parent)

    # ------------------------------------------------------------------
    # navigation helper (show_screen lands when the shell wires it)
    # ------------------------------------------------------------------
    def _navigate(self, name):
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn(name)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # game access
    # ------------------------------------------------------------------
    def _gm(self):
        return getattr(self.game, "game_manager", None) or self.game

    def _league(self):
        gm = self._gm()
        return (_safe(lambda: getattr(gm, "league", None))
                or _safe(lambda: getattr(self.game, "league", None)))

    def _user_team(self):
        gm = self._gm()
        return (_safe(lambda: getattr(gm, "user_team", None))
                or _safe(lambda: getattr(self.game, "user_team", None)))

    def _career(self):
        return (_safe(lambda: getattr(self._gm(), "career", None))
                or _safe(lambda: getattr(self.game, "career", None)))

    def _board(self):
        career = self._career()
        return _safe(lambda: getattr(career, "board", None))

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_body(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(14)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        board_box, board_lay = _section("Board")
        self._build_board(board_lay)
        grid.addWidget(board_box, 0, 0)

        profile_box, profile_lay = _section("Profile")
        self._build_profile(profile_lay)
        grid.addWidget(profile_box, 0, 1)

        goals_box, goals_lay = _section("Season Goals")
        self._build_goals(goals_lay)
        grid.addWidget(goals_box, 1, 0)

        analytics_box, analytics_lay = _section("Team Analytics")
        self._build_analytics(analytics_lay)
        grid.addWidget(analytics_box, 1, 1)

        rels_box, rels_lay = _section("GM Relationships")
        self._build_relationships(rels_lay)
        grid.addWidget(rels_box, 2, 0)

        press_box, press_lay = _section("Press")
        self._build_press(press_lay)
        grid.addWidget(press_box, 2, 1)

        opp_box, opp_lay = _section("Opposition Report")
        self._build_opposition(opp_lay)
        grid.addWidget(opp_box, 3, 0, 1, 2)

        training_box, training_lay = _section("Weekly Training Schedule")
        self._build_training(training_lay)
        grid.addWidget(training_box, 4, 0, 1, 2)

        squad_box, squad_lay = _section("Squad — Private Chats")
        self._build_squad(squad_lay)
        grid.addWidget(squad_box, 5, 0, 1, 2)

        scroll.setWidget(content)
        self._layout.addWidget(scroll, 1)

    def refresh(self):
        # Rebuild everything from the live game state.
        while self._layout.count() > 1:
            child = self._layout.takeAt(1).widget()
            if child is not None:
                child.deleteLater()
        self._build_body()

    # ------------------------------------------------------------------
    # Board
    # ------------------------------------------------------------------
    def _board_data(self):
        import manager_career as mc
        board = self._board()
        if board is None:
            return None
        league = self._league()
        cd = _safe(lambda: getattr(self.game, "current_date", None))
        today = cd.isoformat() if cd is not None and hasattr(
            cd, "isoformat") else ""

        expectations = [{"key": k, "label": v["label"],
                         "description": v["description"]}
                        for k, v in mc.EXPECTATIONS.items()]
        exp = _safe(lambda: getattr(board, "expectation", None)) or "playoffs"
        exp_info = mc.EXPECTATIONS.get(exp, mc.EXPECTATIONS["playoffs"])

        w = _safe(lambda: int(getattr(board, "season_wins", 0) or 0), 0)
        l = _safe(lambda: int(getattr(board, "season_losses", 0) or 0), 0)
        otl = _safe(lambda: int(getattr(board, "season_otl", 0) or 0), 0)
        gp = w + l + otl
        pts = w * 2 + otl
        slate = _safe(lambda: int(
            getattr(league, "season_games_count", 82) or 82), 82)
        target, note = _EXPECTATION_TARGETS.get(exp, (94, ""))

        pace = round(pts / gp * slate, 1) if gp else None
        if gp == 0:
            verdict, gap = "preseason", None
        elif target is None:
            verdict, gap = "rebuild", None
        else:
            gap = round(pace - target, 1)
            verdict = ("on_track" if gap >= -2
                       else "within_reach" if gap >= -8
                       else "off_the_pace")

        return {
            "confidence": _safe(lambda: int(
                getattr(board, "confidence", 60) or 0), 60),
            "job_status": _safe(lambda: str(
                getattr(board, "job_status", "Stable")), "Stable"),
            "sacked": bool(_safe(lambda: getattr(board, "sacked", False),
                                 False)),
            "expectation": exp,
            "expectation_label": exp_info["label"],
            "expectation_description": exp_info["description"],
            "expectations": expectations,
            "record": {"w": w, "l": l, "otl": otl, "pts": pts, "gp": gp,
                       "slate": slate, "pace": pace},
            "verdict": verdict,
            "verdict_gap": gap,
            "target_note": note,
            "last_review": _safe(lambda: str(
                getattr(board, "last_review", "") or ""), ""),
            "patience_status": _safe(lambda: str(
                board.patience_status(today)), ""),
            "owner_archetype": _safe(lambda: str(
                getattr(getattr(board, "owner", None), "archetype", "")),
                ""),
            "consequences": _safe(lambda: list(
                board.current_consequences()), []) or [],
            "cutoff_pace": self._playoff_cutoff_pace(league, slate),
        }

    def _playoff_cutoff_pace(self, league, slate):
        """Approximate full-slate pace of the 16th-place team, or None."""
        try:
            if league is None:
                return None
            gm = self._gm()
            standings = (_safe(lambda: getattr(league, "standings", None))
                         or _safe(lambda: getattr(gm, "standings", None)))
            if not standings or len(standings) < 16:
                return None
            paces = []
            for s in standings.values():
                g = s.get("W", 0) + s.get("L", 0) + s.get("OTL", 0)
                if g > 0:
                    paces.append(s.get("Points", 0) / g * slate)
            if len(paces) < 16:
                return None
            return round(sorted(paces, reverse=True)[15], 0)
        except Exception:
            return None

    def _build_board(self, lay):
        d = _safe(self._board_data)
        if not d:
            lay.addWidget(QLabel("Board data unavailable — no career "
                                 "loaded."))
            return

        # confidence + job status
        top = QHBoxLayout()
        conf_lbl = QLabel(f"Board confidence: {d['confidence']}")
        conf_lbl.setStyleSheet("font-weight: 700;")
        top.addWidget(conf_lbl)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(max(0, min(100, d["confidence"])))
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        top.addWidget(bar, 1)
        job = QLabel(d["job_status"])
        job.setStyleSheet("color: #FF9800; font-weight: 700;")
        top.addWidget(job)
        if d["sacked"]:
            top.addWidget(_pill("SACKED", "#F44336"))
        lay.addLayout(top)

        # expectation + verdict
        rec = d["record"]
        vcolor, vlabel = _VERDICT_STYLE.get(d["verdict"],
                                            ("#6b7488", d["verdict"]))
        gap_txt = ""
        if d["verdict_gap"] is not None:
            gap_txt = (f" ({'+' if d['verdict_gap'] >= 0 else ''}"
                       f"{d['verdict_gap']} vs target)")
        pace_txt = f"on pace for {rec['pace']}" if rec["pace"] else "preseason"
        info = QLabel(
            f"Expectation ({d['expectation_label']}): {d['target_note']}.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #c7d0e0; font-size: 13px;")
        lay.addWidget(info)
        rec_row = QHBoxLayout()
        rec_lbl = QLabel(f"{rec['w']}-{rec['l']}-{rec['otl']} · "
                         f"{rec['pts']} pts · {pace_txt}{gap_txt}")
        rec_lbl.setStyleSheet("font-size: 13px;")
        rec_row.addWidget(rec_lbl)
        rec_row.addWidget(_pill(vlabel, vcolor))
        rec_row.addStretch()
        lay.addLayout(rec_row)

        # expectation picker
        pick = QHBoxLayout()
        pick.addWidget(QLabel("Season expectation:"))
        self._exp_combo = QComboBox()
        for e in d["expectations"]:
            self._exp_combo.addItem(e["label"], e["key"])
        idx = self._exp_combo.findData(d["expectation"])
        if idx >= 0:
            self._exp_combo.setCurrentIndex(idx)
        self._exp_combo.currentIndexChanged.connect(self._update_exp_desc)
        pick.addWidget(self._exp_combo, 1)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary-btn")
        save_btn.clicked.connect(self._on_save_expectation)
        pick.addWidget(save_btn)
        patience_btn = QPushButton("Request Patience")
        patience_btn.clicked.connect(self._on_request_patience)
        pick.addWidget(patience_btn)
        lay.addLayout(pick)
        self._exp_desc = QLabel(d["expectation_description"])
        self._exp_desc.setWordWrap(True)
        self._exp_desc.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        lay.addWidget(self._exp_desc)

        # review / patience / owner / consequences
        meta = []
        if d["last_review"]:
            meta.append(f"Last review: {d['last_review']}")
        if d["patience_status"]:
            meta.append(f"Patience: {d['patience_status']}")
        if d["owner_archetype"]:
            meta.append(f"Owner: {d['owner_archetype']}")
        if d["cutoff_pace"]:
            meta.append(f"Playoff cutoff pace: ~{d['cutoff_pace']} pts")
        if meta:
            meta_lbl = QLabel(" · ".join(meta))
            meta_lbl.setWordWrap(True)
            meta_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            lay.addWidget(meta_lbl)
        for c in d["consequences"]:
            cl = QLabel(f"• {c}")
            cl.setWordWrap(True)
            cl.setStyleSheet("color: #FF9800; font-size: 12px;")
            lay.addWidget(cl)

    def _update_exp_desc(self):
        if self._exp_combo is None:
            return
        d = _safe(self._board_data)
        if not d:
            return
        key = self._exp_combo.currentData()
        ex = next((e for e in d["expectations"] if e["key"] == key), None)
        if ex:
            self._exp_desc.setText(ex["description"])

    def _on_save_expectation(self):
        import manager_career as mc
        board = self._board()
        if board is None or self._exp_combo is None:
            return
        key = str(self._exp_combo.currentData() or "").strip()
        if key not in mc.EXPECTATIONS:
            QMessageBox.warning(self, "Board", "Unknown expectation.")
            return
        try:
            board.set_expectation(key)
        except Exception as exc:
            QMessageBox.warning(self, "Board",
                                f"Could not save: {exc}")
            return
        self.refresh()

    def _on_request_patience(self):
        board = self._board()
        if board is None:
            return
        cd = _safe(lambda: getattr(self.game, "current_date", None))
        today = cd.isoformat() if cd is not None and hasattr(
            cd, "isoformat") else ""
        try:
            granted, headline, body = board.request_patience(today)
        except Exception as exc:
            QMessageBox.warning(self, "Board",
                                f"Request failed: {exc}")
            return
        if granted:
            # Mirror the Tk hub: the room settles knowing the manager
            # is safe.
            team = self._user_team()
            for p in (_safe(lambda: list(getattr(team, "roster", [])
                                         or []), []) or []):
                try:
                    m = float(getattr(p, "morale", 70) or 70)
                    p.morale = min(100.0, m + 2)
                except Exception:
                    pass
        QMessageBox.information(self, "Board",
                                f"{headline}\n\n{body}")
        self.refresh()

    # ------------------------------------------------------------------
    # Weekly training schedule
    # ------------------------------------------------------------------
    def _training(self):
        career = self._career()
        return _safe(lambda: getattr(career, "training", None))

    def _build_training(self, lay):
        import manager_career as mc
        training = self._training()
        if training is None:
            lbl = QLabel("Start a career to set the weekly training schedule.")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
            return

        hint = QLabel("Presets set every unit at once; customise per unit below. "
                      "The schedule drives weekly development rate, injury risk "
                      "and squad morale for your club.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        lay.addWidget(hint)

        prow = QHBoxLayout()
        plbl = QLabel("Preset:")
        prow.addWidget(plbl)
        self._training_preset_combo = QComboBox()
        presets = list(mc.TRAINING_PRESETS.keys())
        # Show "Custom" when the schedule was hand-tuned.
        if training.preset_name not in presets:
            presets = presets + ["Custom"]
        self._training_preset_combo.addItems(presets)
        self._training_preset_combo.setCurrentText(training.preset_name)
        self._training_preset_combo.activated.connect(
            self._on_training_preset_changed)
        prow.addWidget(self._training_preset_combo, 1)
        lay.addLayout(prow)

        grid = QGridLayout()
        grid.setSpacing(6)
        for c, h in enumerate(("Unit", "Intensity", "Focus")):
            hl = QLabel(h)
            hl.setObjectName("section-header")
            grid.addWidget(hl, 0, c)
        self._training_unit_combos = {}
        for i, unit in enumerate(mc.TRAINING_UNITS, start=1):
            ul = QLabel(unit)
            grid.addWidget(ul, i, 0)
            cur_int, cur_foc = _safe(
                lambda u=unit: training.schedule.get(u, ("Normal", "Balanced")),
                ("Normal", "Balanced"))
            icombo = QComboBox()
            icombo.addItems(list(mc.TRAINING_INTENSITIES))
            icombo.setCurrentText(cur_int)
            grid.addWidget(icombo, i, 1)
            fcombo = QComboBox()
            fcombo.addItems(list(mc.TRAINING_FOCI))
            fcombo.setCurrentText(cur_foc)
            grid.addWidget(fcombo, i, 2)
            self._training_unit_combos[unit] = (icombo, fcombo)
        lay.addLayout(grid)

        apply_btn = QPushButton("Apply Custom Schedule")
        apply_btn.clicked.connect(self._on_apply_custom_training)
        lay.addWidget(apply_btn, alignment=Qt.AlignLeft)

        fx = _safe(lambda: training.weekly_effects(), None) or {}
        lines = []
        dev = fx.get("development_mult", 1.0)
        inj = fx.get("injury_risk_mult", 1.0)
        mor = fx.get("morale_delta", 0)
        lines.append(f"Development rate: x{dev}")
        lines.append(f"Injury risk: x{inj}")
        sign = "+" if mor >= 0 else ""
        lines.append(f"Squad morale: {sign}{mor}")
        for note in fx.get("notes", []) or []:
            lines.append(note)
        self._training_effects = QLabel("\n".join("\u2022 " + l for l in lines))
        self._training_effects.setWordWrap(True)
        lay.addWidget(self._training_effects)

    def _on_training_preset_changed(self, index):
        import manager_career as mc
        training = self._training()
        if training is None or self._training_preset_combo is None:
            return
        name = self._training_preset_combo.itemText(index)
        if name not in mc.TRAINING_PRESETS:
            return
        try:
            training.set_preset(name)
        except Exception as exc:
            QMessageBox.warning(self, "Training",
                                f"Could not apply preset: {exc}")
            return
        self.refresh()

    def _on_apply_custom_training(self):
        import manager_career as mc
        training = self._training()
        if training is None:
            return
        try:
            for unit, (icombo, fcombo) in self._training_unit_combos.items():
                training.set_unit(unit, icombo.currentText(),
                                  fcombo.currentText())
        except Exception as exc:
            QMessageBox.warning(self, "Training",
                                f"Could not apply schedule: {exc}")
            return
        # set_unit() flips preset_name to "Custom" itself.
        self.refresh()

    # ------------------------------------------------------------------
    # Season goals summary
    # ------------------------------------------------------------------
    def _goals_data(self):
        import season_goals as sg
        team = self._user_team()
        if team is None:
            return []
        board = self._board()
        w = _safe(lambda: int(getattr(board, "season_wins", 0) or 0), 0)
        l = _safe(lambda: int(getattr(board, "season_losses", 0) or 0), 0)
        otl = _safe(lambda: int(getattr(board, "season_otl", 0) or 0), 0)
        gp = w + l + otl
        league = self._league()
        slate = _safe(lambda: int(
            getattr(league, "season_games_count", 82) or 82), 82)
        expected_pct = (gp / slate * 100) if gp and slate else 0

        roster = _safe(lambda: list(getattr(team, "roster", []) or []),
                       []) or []
        goals = []
        for p in roster:
            prog = _safe(lambda: sg.goal_progress(p))
            if not prog:
                continue
            pct = prog.get("pct", 0) or 0
            if prog.get("hit"):
                status = "hit"
            elif not gp:
                status = "preseason"
            elif pct >= expected_pct * 0.9:
                status = "on_track"
            elif pct >= expected_pct * 0.5:
                status = "at_risk"
            else:
                status = "behind"
            goals.append({
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "label": prog["label"],
                "current": prog["current"],
                "target": prog["target"],
                "pct": pct,
                "status": status,
            })
        goals.sort(key=lambda g: (g["status"] != "hit", -g["pct"]))
        return goals

    def _build_goals(self, lay):
        head = QHBoxLayout()
        head.addStretch()
        open_btn = QPushButton("Open Season Goals →")
        open_btn.clicked.connect(lambda: self._navigate("season_goals"))
        head.addWidget(open_btn)
        lay.addLayout(head)

        goals = _safe(self._goals_data, [])
        if not goals:
            lay.addWidget(QLabel("No season goals set yet. Open Season "
                                 "Goals to set per-player targets."))
            return
        for g in goals[:8]:
            row = QVBoxLayout()
            top = QHBoxLayout()
            name = QLabel(f"{g['name']} — {g['label']}")
            name.setStyleSheet("font-weight: 600; font-size: 13px;")
            top.addWidget(name)
            top.addStretch()
            color, txt = _GOAL_STATUS_STYLE.get(
                g["status"], ("#6b7488", g["status"]))
            top.addWidget(_pill(txt, color))
            row.addLayout(top)
            bar_row = QHBoxLayout()
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(max(0, min(100, g["pct"]))))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar_row.addWidget(bar, 1)
            bar_row.addWidget(QLabel(f"{g['current']}/{g['target']}"))
            row.addLayout(bar_row)
            lay.addLayout(row)
        if len(goals) > 8:
            more = QLabel(f"…and {len(goals) - 8} more in Season Goals.")
            more.setStyleSheet("color: #6b7488; font-size: 12px;")
            lay.addWidget(more)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    def _profile_data(self):
        career = self._career()
        if career is None:
            return None
        gm = self._gm()
        team = self._user_team()
        prof = _safe(lambda: getattr(career, "profile", None))
        gmp = _safe(lambda: getattr(team, "gm_profile", None)) if team else None
        board = self._board()
        profile = {}
        if prof is not None:
            profile = {
                "reputation": _safe(lambda: int(
                    getattr(prof, "reputation", 0) or 0), 0),
                "level": _safe(lambda: str(getattr(prof, "level", "")), ""),
                "career_wins": _safe(lambda: int(
                    getattr(prof, "career_wins", 0) or 0), 0),
                "career_losses": _safe(lambda: int(
                    getattr(prof, "career_losses", 0) or 0), 0),
                "career_otl": _safe(lambda: int(
                    getattr(prof, "career_otl", 0) or 0), 0),
                "titles_won": _safe(lambda: int(
                    getattr(prof, "titles_won", 0) or 0), 0),
                "playoff_appearances": _safe(lambda: int(
                    getattr(prof, "playoff_appearances", 0) or 0), 0),
                "seasons_managed": _safe(lambda: int(
                    getattr(prof, "seasons_managed", 0) or 0), 0),
            }
        bio = []
        if gmp is not None:
            for label, attr in (("Age", "age"), ("Birthplace", "birthplace"),
                                ("Nationality", "nationality"),
                                ("Education", "education_level")):
                v = _safe(lambda: getattr(gmp, attr, None))
                if v:
                    bio.append(f"{label}: {v}")
            if bio:
                bio.append("")
            for label, attr in (("Style", "management_style"),
                                ("Risk tolerance", "risk_tolerance"),
                                ("Loyalty to players", "loyalty_to_players"),
                                ("Media savvy", "media_savvy")):
                v = _safe(lambda: getattr(gmp, attr, None))
                if v:
                    bio.append(f"{label}: {v}")
            if _safe(lambda: getattr(gmp, "former_player", False), False):
                bio.append("")
                bio.append(
                    f"Former {_safe(lambda: getattr(gmp, 'playing_position', 'player'), 'player')}: "
                    f"{_safe(lambda: getattr(gmp, 'nhl_games_played', 0), 0)} NHL games, "
                    f"{_safe(lambda: getattr(gmp, 'career_points', 0), 0)} career points.")
            if _safe(lambda: getattr(gmp, "coaching_experience", False),
                     False):
                bio.append(
                    f"{_safe(lambda: getattr(gmp, 'years_coaching', 0), 0)} "
                    f"years coaching experience.")
            if _safe(lambda: getattr(gmp, "assistant_gm_experience", False),
                     False):
                bio.append(
                    f"{_safe(lambda: getattr(gmp, 'years_as_assistant', 0), 0)} "
                    f"years as an assistant GM.")
        appt = {}
        if team is not None:
            appt["club"] = _safe(lambda: str(getattr(team, "team_name", "")),
                                 "")
        start = _safe(lambda: getattr(career, "career_start_date", ""),
                      "") or ""
        if start:
            appt["since"] = str(start)
        return {"profile": profile, "bio": bio, "appointment": appt,
                "season_record": None if board is None else {
                    "w": _safe(lambda: int(
                        getattr(board, "season_wins", 0) or 0), 0),
                    "l": _safe(lambda: int(
                        getattr(board, "season_losses", 0) or 0), 0),
                    "otl": _safe(lambda: int(
                        getattr(board, "season_otl", 0) or 0), 0),
                }}

    def _build_profile(self, lay):
        d = _safe(self._profile_data)
        if not d:
            lay.addWidget(QLabel("Profile unavailable — no career loaded."))
            return
        p = d["profile"]
        if p:
            rec = (f"{p['career_wins']}-{p['career_losses']}-"
                   f"{p['career_otl']}")
            stats = (f"Reputation {p['reputation']} · {p['level']} · "
                     f"Career {rec} · {p['titles_won']} titles · "
                     f"{p['playoff_appearances']} playoff apps · "
                     f"{p['seasons_managed']} seasons")
            stats_lbl = QLabel(stats)
            stats_lbl.setWordWrap(True)
            stats_lbl.setStyleSheet("color: #c7d0e0; font-size: 13px;")
            lay.addWidget(stats_lbl)
        appt = d["appointment"]
        if appt.get("club"):
            since = f" since {appt['since']}" if appt.get("since") else ""
            club = QLabel(f"GM of the {appt['club']}{since}")
            club.setStyleSheet("font-weight: 700; font-size: 14px;")
            lay.addWidget(club)
        sr = d["season_record"]
        if sr:
            lay.addWidget(QLabel(
                f"This season: {sr['w']}-{sr['l']}-{sr['otl']}"))
        for line in d["bio"]:
            if not line:
                continue
            bl = QLabel(line)
            bl.setWordWrap(True)
            bl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            lay.addWidget(bl)

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------
    def _analytics_data(self):
        team = self._user_team()
        if team is None:
            return {"available": False,
                    "message": "No game attached."}
        try:
            import analytics_hub as ah
        except Exception:
            try:
                import sys
                import types
                stub = types.ModuleType("customtkinter")
                stub.CTkFrame = object
                sys.modules.setdefault("customtkinter", stub)
                sys.modules.pop("analytics_hub", None)
                import analytics_hub as ah
            except Exception:
                return {"available": False,
                        "message": "Analytics module unavailable."}
        name = _safe(lambda: str(getattr(team, "team_name", "")), "")
        games = _safe(lambda: ah.team_games(team), []) or []
        recent = games[-5:]
        if not recent:
            return {"available": False,
                    "message": "Play a game and the analyst will have "
                               "something to work with."}

        per_game, all_shots, all_entries = [], [], []
        for rec in recent:
            shots = _safe(lambda: ah.shots_for(rec, name), []) or []
            try:
                home, away = str(rec.get("home", "")), str(rec.get("away",
                                                                   ""))
                opp = away if name == home else home
            except Exception:
                opp = ""
            opp_shots = [s for s in (rec.get("shots") or [])
                         if str(s.get("team", "")) == opp]
            xg = round(sum(float(s.get("xg", 0) or 0) for s in shots), 2)
            gf = sum(1 for s in shots if s.get("outcome") == "goal")
            xga = round(sum(float(s.get("xg", 0) or 0)
                            for s in opp_shots), 2)
            per_game.append({
                "label": _safe(lambda: ah.game_label(rec, name), "game"),
                "xg_for": xg, "goals_for": gf, "xg_against": xga,
                "shots": len(shots),
            })
            all_shots.extend(shots)
            all_entries.extend(
                _safe(lambda: ah.entries_for(rec, name), []) or [])

        xg_for = round(sum(g["xg_for"] for g in per_game), 2)
        goals_for = sum(g["goals_for"] for g in per_game)
        xg_against = round(sum(g["xg_against"] for g in per_game), 2)
        n_shots = sum(g["shots"] for g in per_game)
        diff = round(goals_for - xg_for, 2)
        hd = sum(1 for s in all_shots
                 if float(s.get("xg", 0) or 0) >= 0.12)
        eb = _safe(lambda: ah.entry_breakdown(all_entries),
                   {"controlled": 0, "total": 0,
                    "controlled_pct": 0.0}) or {}
        shooters = _safe(lambda: ah.player_xg_rows(all_shots), []) or []
        mpts = []
        try:
            mpts = ah.momentum_points(recent[-1], name) or []
        except Exception:
            pass
        mom = None
        if mpts:
            vals = [p.get("value", 0) for p in mpts]
            mom = {"shifts": len(mpts), "swing": max(vals) - min(vals),
                   "latest": vals[-1]}
        return {
            "available": True, "team": name, "window": len(recent),
            "xg_for": xg_for, "goals_for": goals_for,
            "xg_against": xg_against, "shots": n_shots, "diff": diff,
            "avg_chance_quality": (round(xg_for / n_shots, 3)
                                   if n_shots else 0.0),
            "high_danger_share": (round(hd / n_shots, 3)
                                  if n_shots else 0.0),
            "high_danger_count": hd,
            "controlled_entries_pct": eb.get("controlled_pct", 0.0),
            "entries_total": eb.get("total", 0),
            "hot_shooter": shooters[0] if shooters else None,
            "momentum": mom,
        }

    def _build_analytics(self, lay):
        d = _safe(self._analytics_data,
                  {"available": False, "message": "Unavailable."})
        if not d.get("available"):
            lay.addWidget(QLabel(d.get("message", "Unavailable.")))
            return
        lay.addWidget(QLabel(f"Last {d['window']} games"))
        grid = QGridLayout()
        cards = [
            ("xG For", f"{d['xg_for']:.2f}"),
            ("Goals For", str(d["goals_for"])),
            ("xG Against", f"{d['xg_against']:.2f}"),
            ("Finishing",
             f"{'+' if d['diff'] >= 0 else ''}{d['diff']:.2f}"),
            ("Avg chance quality", f"{d['avg_chance_quality']:.3f}"),
            ("High-danger",
             f"{d['high_danger_count']} "
             f"({d['high_danger_share']:.0%})"),
            ("Controlled entries",
             f"{d['controlled_entries_pct']:.0%} "
             f"({d['entries_total']})"),
        ]
        hs = d.get("hot_shooter")
        if hs:
            cards.append(("Hot shooter",
                          f"{hs.get('name', '?')} "
                          f"({hs.get('xg', 0):.2f} xG)"))
        mom = d.get("momentum")
        if mom:
            cards.append(("Momentum",
                          f"{mom['latest']:+.1f} "
                          f"(swing {mom['swing']:.1f})"))
        for i, (label, val) in enumerate(cards):
            cell = QFrame()
            cell.setObjectName("tile")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(10, 8, 10, 8)
            vl = QLabel(val)
            vl.setStyleSheet("font-weight: 700; font-size: 16px;")
            ll = QLabel(label)
            ll.setStyleSheet("color: #9aa4b8; font-size: 11px;")
            cl.addWidget(vl)
            cl.addWidget(ll)
            grid.addWidget(cell, i // 2, i % 2)
        lay.addLayout(grid)

    # ------------------------------------------------------------------
    # GM relationships summary
    # ------------------------------------------------------------------
    def _relationships_data(self):
        try:
            import reputation_system as rs
        except Exception:
            return {"available": False}
        gm = self._gm()
        team = self._user_team()
        league = self._league()
        if team is None or league is None:
            return {"available": False}
        teams = _safe(lambda: list(getattr(league, "teams", []) or []),
                      []) or []
        uid = _safe(lambda: getattr(team, "id", None))
        rows = []
        for t in teams:
            try:
                tid = _safe(lambda: getattr(t, "id", None))
                if uid is not None and tid == uid:
                    continue
                stature = _safe(lambda: int(rs.gm_stature(t)), 50)
                respect = _safe(lambda: int(
                    rs.gm_gm_respect(league, team, t)), 50)
                heat = _safe(lambda: int(
                    rs.gm_gm_heat(league, team, t)), 0)
                tier = _safe(lambda: str(
                    rs.respect_tier_label(respect)), "wary")
                trend = _safe(lambda: str(
                    rs.respect_trend(league, team, t)), "steady")
                staff = _safe(lambda: rs._team_gm_staff(t))
                gm_name = (_safe(lambda: getattr(staff, "full_name", None))
                           or _safe(lambda: getattr(staff, "name", None))
                           or f"{_safe(lambda: getattr(t, 'team_name', 'Unknown'), 'Unknown')} GM")
                rows.append({
                    "team": _safe(lambda: str(
                        getattr(t, "team_name", "Unknown")), "Unknown"),
                    "team_key": "" if tid is None else str(tid),
                    "gm": str(gm_name),
                    "stature": stature,
                    "respect": respect,
                    "tier": tier,
                    "heat": heat,
                    "trend": trend,
                    "arrow": _TREND_ARROW.get(trend, "→"),
                })
            except Exception:
                continue
        rows.sort(key=lambda r: -r["respect"])
        own = {
            "stature": _safe(lambda: int(rs.gm_stature(team)), 50),
            "team": _safe(lambda: str(getattr(team, "team_name", "")), ""),
        }
        return {"available": True, "own": own, "rows": rows}

    def _build_relationships(self, lay):
        head = QHBoxLayout()
        self._own_stature = QLabel("")
        head.addWidget(self._own_stature)
        head.addStretch()
        open_btn = QPushButton("Open GM Relationships →")
        open_btn.clicked.connect(lambda: self._navigate("gm_relationships"))
        head.addWidget(open_btn)
        lay.addLayout(head)

        d = _safe(self._relationships_data, {"available": False})
        if not d.get("available"):
            lay.addWidget(QLabel("Relationship data unavailable."))
            return
        self._own_stature.setText(
            f"Your stature: {d['own']['stature']}")
        self._rels_rows = d["rows"]

        cols = ["Team", "GM", "Stature", "Respect", "Tier", "Heat", "Trend"]
        t = QTableWidget()
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setSelectionMode(QTableWidget.SingleSelection)
        t.setSortingEnabled(False)
        t.setRowCount(len(self._rels_rows))
        for r, row in enumerate(self._rels_rows):
            t.setItem(r, 0, QTableWidgetItem(row["team"]))
            t.setItem(r, 1, QTableWidgetItem(row["gm"]))
            t.setItem(r, 2, _NumericItem(str(row["stature"]),
                                         row["stature"]))
            t.setItem(r, 3, _NumericItem(str(row["respect"]),
                                         row["respect"]))
            t.setItem(r, 4, QTableWidgetItem(
                f"{row['tier'].title()} {row['arrow']}"))
            t.setItem(r, 5, _NumericItem(str(row["heat"]), row["heat"]))
            t.setItem(r, 6, QTableWidgetItem(
                f"{row['arrow']} {row['trend']}"))
            for c in range(len(cols)):
                t.item(r, c).setData(Qt.UserRole + 1, row)
        t.resizeColumnsToContents()
        t.setSortingEnabled(True)   # client-side sortable headers
        t.sortByColumn(3, Qt.DescendingOrder)
        t.setMaximumHeight(240)
        t.itemSelectionChanged.connect(self._on_rel_selected)
        self._rels_table = t
        lay.addWidget(t)

        self._rel_detail = QLabel("Select a GM for detail.")
        self._rel_detail.setWordWrap(True)
        self._rel_detail.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        lay.addWidget(self._rel_detail)

    def _on_rel_selected(self):
        t = self._rels_table
        if t is None:
            return
        items = t.selectedItems()
        if not items:
            return
        row = items[0].data(Qt.UserRole + 1)
        if not row:
            return
        detail = self._rel_detail_data(row)
        if detail:
            self._rel_detail.setText(
                f"{detail['gm']} ({detail['team']}): stature "
                f"{detail['stature']}, respect {detail['respect']} "
                f"({detail['tier']}), heat {detail['heat']}, trend "
                f"{detail['trend']}"
                + (f", baseline {detail['respect_baseline']:.0f}"
                   if detail.get("respect_baseline") is not None else "")
                + ".")

    def _rel_detail_data(self, row):
        try:
            import reputation_system as rs
        except Exception:
            return None
        gm = self._gm()
        team = self._user_team()
        league = self._league()
        if team is None or league is None:
            return None
        key = (row.get("team_key") or row.get("team") or "").strip().lower()
        target = None
        for t in (_safe(lambda: list(getattr(league, "teams", []) or []),
                        []) or []):
            tn = _safe(lambda: str(getattr(t, "team_name", "")).strip().lower(),
                       "")
            tid = _safe(lambda: str(getattr(t, "id", "")), "")
            if tn == key or tid == key:
                target = t
                break
        if target is None:
            return None
        stature = _safe(lambda: int(rs.gm_stature(target)), 50)
        respect = _safe(lambda: int(rs.gm_gm_respect(league, team, target)),
                        50)
        heat = _safe(lambda: int(rs.gm_gm_heat(league, team, target)), 0)
        tier = _safe(lambda: str(rs.respect_tier_label(respect)), "wary")
        trend = _safe(lambda: str(rs.respect_trend(league, team, target)),
                      "steady")
        baseline = _safe(lambda: float(rs.respect_baseline_for(target)),
                         None)
        staff = _safe(lambda: rs._team_gm_staff(target))
        gm_name = (_safe(lambda: getattr(staff, "full_name", None))
                   or _safe(lambda: getattr(staff, "name", None))
                   or f"{_safe(lambda: getattr(target, 'team_name', 'Unknown'), 'Unknown')} GM")
        return {
            "team": _safe(lambda: str(
                getattr(target, "team_name", "Unknown")), "Unknown"),
            "gm": str(gm_name),
            "stature": stature, "respect": respect, "tier": tier,
            "heat": heat, "trend": trend, "respect_baseline": baseline,
        }

    # ------------------------------------------------------------------
    # Press (interactive press-conference focus card + history)
    # ------------------------------------------------------------------
    _PRESSER_FOCI = (
        ("upcoming_game", "Upcoming game"),
        ("player_performance", "Player performance"),
        ("trade_rumors", "Trade rumors"),
    )

    _PRESSER_JOURNALISTS = (
        "Sarah Chen (Hockey Night)",
        "Mike Ross (The Athletic)",
        "Dave Tremblay (TSN)",
        "Lisa Park (Sportsnet)",
    )

    def _build_press(self, lay):
        self._render_presser_card(lay)
        sep = QLabel("Recent press conferences:")
        sep.setStyleSheet("color: #9aa4b8; font-size: 12px; "
                          "font-weight: 700; margin-top: 8px;")
        lay.addWidget(sep)
        self._build_press_history(lay)

    def _render_presser_card(self, lay):
        """Interactive focus card: pick a focus, answer questions."""
        head = QLabel("\U0001f3a4 PRESS CONFERENCE")
        head.setStyleSheet("font-weight: 800; font-size: 14px; "
                           "color: #f0c75e;")
        lay.addWidget(head)
        st = self._presser
        if not st:
            intro = QLabel("Hold a press conference and face the media. "
                           "Pick a focus:")
            intro.setWordWrap(True)
            intro.setStyleSheet("font-size: 13px;")
            lay.addWidget(intro)
            row = QHBoxLayout()
            for key, label in self._PRESSER_FOCI:
                b = QPushButton(label)
                b.clicked.connect(
                    lambda _=False, k=key: self._start_presser(k))
                row.addWidget(b)
            row.addStretch()
            lay.addLayout(row)
            return
        focus_lbl = QLabel(f"Focus: {st.get('focus_label', '')}")
        focus_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px; "
                                "font-weight: 700;")
        lay.addWidget(focus_lbl)
        if st.get("done"):
            s = QLabel(st.get("summary") or "Press conference complete.")
            s.setWordWrap(True)
            s.setStyleSheet("font-size: 13px;")
            lay.addWidget(s)
            again = QPushButton("Hold another press conference")
            again.clicked.connect(self._reset_presser)
            lay.addWidget(again)
            return
        for rec in st.get("answers") or []:
            q, a = rec.get("question", {}), rec.get("answer", {})
            ql = QLabel(f"Q: {q.get('question', '')}")
            ql.setWordWrap(True)
            ql.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            al = QLabel(f"A: {a.get('label', '')}")
            al.setWordWrap(True)
            al.setStyleSheet("font-size: 13px;")
            lay.addWidget(ql)
            lay.addWidget(al)
            reaction = a.get("reaction", "")
            if reaction:
                rl = QLabel(reaction)
                rl.setWordWrap(True)
                rl.setStyleSheet("color: #8BC34A; font-size: 12px;")
                lay.addWidget(rl)
        questions = st.get("questions") or []
        idx = st.get("index", 0)
        if idx < len(questions):
            q = questions[idx]
            prog = QLabel(f"Question {idx + 1} of {len(questions)} — "
                          f"{q.get('journalist', 'Press')}")
            prog.setStyleSheet("color: #9aa4b8; font-size: 12px; "
                               "font-weight: 700;")
            lay.addWidget(prog)
            qt = QLabel(q.get("question", ""))
            qt.setWordWrap(True)
            qt.setStyleSheet("font-size: 14px; font-weight: 700;")
            lay.addWidget(qt)
            for ans in q.get("answers") or []:
                b = QPushButton(str(ans.get("label", "")))
                b.setStyleSheet("text-align: left; padding: 8px 12px;")
                b.clicked.connect(
                    lambda _=False, _q=q, _a=ans:
                    self._answer_presser_question(_q, _a))
                lay.addWidget(b)
            wrap = QPushButton("Wrap up (no more questions)")
            wrap.clicked.connect(self._finish_presser)
            lay.addWidget(wrap)

    def _build_press_history(self, lay):
        career = self._career()
        hist = _safe(lambda: list(getattr(career, "press_history", [])
                                  or []), []) or []
        entries = list(reversed(hist[-20:]))
        if not entries:
            lay.addWidget(QLabel("No press conferences on record yet."))
            return
        for e in entries[:10]:
            date = str(e.get("date", ""))
            etype = str(e.get("type", ""))
            summary = str(e.get("summary", ""))
            row = QVBoxLayout()
            head = QLabel(f"{date} — {etype}")
            head.setStyleSheet("color: #9aa4b8; font-size: 12px; "
                               "font-weight: 700;")
            body = QLabel(summary)
            body.setWordWrap(True)
            body.setStyleSheet("font-size: 13px;")
            row.addWidget(head)
            row.addWidget(body)
            lay.addLayout(row)
        if len(entries) > 10:
            lay.addWidget(QLabel(f"…and {len(entries) - 10} more."))

    # ------------------------------------------------------------------
    # Press conference flow
    # ------------------------------------------------------------------
    def _presser_form_word(self):
        """Recent-form word, mirroring mainline _career_form_word."""
        board = self._board()
        w = _safe(lambda: int(getattr(board, "season_wins", 0) or 0), 0)
        l = _safe(lambda: int(getattr(board, "season_losses", 0) or 0), 0)
        otl = _safe(lambda: int(getattr(board, "season_otl", 0) or 0), 0)
        games = w + l + otl
        if games < 3:
            return "mixed"
        pct = (w * 2 + otl) / (games * 2)
        if pct >= 0.65:
            return "excellent"
        if pct >= 0.5:
            return "decent"
        return "poor"

    def _presser_questions(self, focus):
        """Build the question list for a presser focus. Never raises."""
        try:
            if focus == "upcoming_game":
                return self._presser_game_questions()
            if focus == "player_performance":
                return self._presser_player_questions()
            if focus == "trade_rumors":
                return self._presser_rumor_questions()
        except Exception:
            pass
        return []

    def _presser_game_questions(self):
        """Upcoming-game focus: mainline pre-match question bank."""
        import manager_career as mc
        team = self._user_team()
        opp, _gdate = self._next_opponent()
        if team is None or opp is None:
            return []
        standings = _safe(
            lambda: getattr(self._league(), "standings", None), {}) or {}
        report = _safe(
            lambda: mc.generate_opposition_report(opp, standings), {}) or {}
        ctx = {
            "form_word": self._presser_form_word(),
            "opp": report.get("team") or getattr(opp, "team_name", "them"),
            "opp_word": str(report.get("danger_level", "dangerous")).lower(),
        }
        return _safe(
            lambda: mc.build_prematch_presser(team, opp, ctx), []) or []

    def _presser_player_questions(self):
        """Player-performance focus: questions built from real roster stats."""
        team = self._user_team()
        roster = [p for p in (_safe(
            lambda: list(getattr(team, "roster", []) or []), []) or [])
            if str(getattr(p, "primary_position", "") or "").upper()
            != "GOALIE"]
        if not roster:
            return []

        def _nm(p):
            return (f"{getattr(p, 'first_name', '?')} "
                    f"{getattr(p, 'last_name', '?')}").strip()

        def _pts(p):
            return float(getattr(p, "points", 0) or 0)

        sk = sorted(roster, key=_pts, reverse=True)
        star, slump = sk[0], sk[-1]
        star_nm, slump_nm = _nm(star), _nm(slump)
        star_pts, slump_pts = int(_pts(star)), int(_pts(slump))
        star_gp = int(_safe(lambda: getattr(star, "games_played", 0), 0) or 0)
        journalists = self._PRESSER_JOURNALISTS
        return [
            {
                "id": "star_form",
                "journalist": journalists[0],
                "question": (f"{star_nm} has {star_pts} points"
                             f"{f' in {star_gp} games' if star_gp else ''} "
                             f"— is he your MVP so far?"),
                "answers": [
                    {"label": "Praise him: 'He's been our best player'",
                     "tone": "confident", "morale_effect": 1,
                     "board_effect": 0, "fan_effect": 2,
                     "reaction": (f"{star_nm} hears the praise — the room "
                                  "lifts. The fans love a coach who backs "
                                  "his stars.")},
                    {"label": "Share credit: 'It's a team game'",
                     "tone": "calm", "morale_effect": 0,
                     "board_effect": 1, "fan_effect": 0,
                     "reaction": ("Measured. The board likes the no-ego "
                                  "message.")},
                    {"label": "Demand more: 'I need more from everyone'",
                     "tone": "honest", "morale_effect": -1,
                     "board_effect": 0, "fan_effect": -1,
                     "reaction": ("Blunt. The dressing room didn't enjoy "
                                  "that, and the fans grumble.")},
                ],
            },
            {
                "id": "slump",
                "journalist": journalists[1],
                "question": (f"{slump_nm} has {slump_pts} points and looks "
                             f"lost out there. Are you worried?"),
                "answers": [
                    {"label": "Back him: 'He's working through it'",
                     "tone": "supportive", "morale_effect": 1,
                     "board_effect": 0, "fan_effect": 1,
                     "reaction": (f"{slump_nm} hears his coach went to bat "
                                  "for him — the room tightens.")},
                    {"label": "Steady: 'He knows the standard'",
                     "tone": "calm", "morale_effect": 0,
                     "board_effect": 0, "fan_effect": 0,
                     "reaction": "A shrug. Nobody learned anything."},
                    {"label": "Tough love: 'If he doesn't produce, he sits'",
                     "tone": "tough", "morale_effect": -1,
                     "board_effect": 1, "fan_effect": -1,
                     "reaction": ("The board likes the accountability. The "
                                  "room went quiet.")},
                ],
            },
        ]

    def _presser_rumor_questions(self):
        """Trade-rumor focus: questions built from real roster names."""
        team = self._user_team()
        roster = [p for p in (_safe(
            lambda: list(getattr(team, "roster", []) or []), []) or [])
            if str(getattr(p, "primary_position", "") or "").upper()
            != "GOALIE"]
        if not roster:
            return []

        def _nm(p):
            return (f"{getattr(p, 'first_name', '?')} "
                    f"{getattr(p, 'last_name', '?')}").strip()

        def _age(p):
            return int(_safe(lambda: getattr(p, "age", 99), 99) or 99)

        young = min(roster, key=_age)
        young_nm, young_age = _nm(young), _age(young)
        journalists = self._PRESSER_JOURNALISTS
        return [
            {
                "id": "rumor_player",
                "journalist": journalists[2],
                "question": (f"{young_nm} ({young_age}) is all over the "
                             f"rumor mill this week. Is he going anywhere?"),
                "answers": [
                    {"label": "Shut it down: 'He's part of the future'",
                     "tone": "confident", "morale_effect": 1,
                     "board_effect": 0, "fan_effect": 2,
                     "reaction": (f"{young_nm} hears he's wanted — the room "
                                  "loves it, and so do the fans.")},
                    {"label": "Open for business: 'We listen to every call'",
                     "tone": "honest", "morale_effect": -1,
                     "board_effect": 1, "fan_effect": 0,
                     "reaction": ("The board likes a GM maximizing assets. "
                                  "The room reads the writing on the wall.")},
                    {"label": "No comment on rumors",
                     "tone": "evasive", "morale_effect": 0,
                     "board_effect": 0, "fan_effect": -1,
                     "reaction": ("Terse. The rumor mill spins faster, and "
                                  "the fans grumble.")},
                ],
            },
            {
                "id": "deadline_add",
                "journalist": journalists[3],
                "question": "Are you looking to add before the deadline?",
                "answers": [
                    {"label": "Aggressive: 'If the right deal is there, "
                              "we strike'",
                     "tone": "confident", "morale_effect": 0,
                     "board_effect": 1, "fan_effect": 1,
                     "reaction": ("Ambition plays well in the boardroom and "
                                  "the stands.")},
                    {"label": "Loyal: 'I believe in this group'",
                     "tone": "calm", "morale_effect": 1,
                     "board_effect": 0, "fan_effect": 0,
                     "reaction": ("The room appreciates the vote of "
                                  "confidence.")},
                    {"label": "Noncommittal: 'We're always looking'",
                     "tone": "evasive", "morale_effect": 0,
                     "board_effect": 0, "fan_effect": 0,
                     "reaction": "GM-speak. Nobody learned anything."},
                ],
            },
        ]

    def _start_presser(self, focus):
        """Open a presser on a focus: pick questions, show the card."""
        label = dict(self._PRESSER_FOCI).get(focus, focus)
        questions = self._presser_questions(focus)
        if not questions:
            self._presser = {
                "focus": focus, "focus_label": label, "questions": [],
                "index": 0, "answers": [], "done": True,
                "summary": (f"No questions from the press on '{label}' "
                            f"today — nothing to answer."),
            }
        else:
            self._presser = {
                "focus": focus, "focus_label": label,
                "questions": questions, "index": 0, "answers": [],
                "done": False, "summary": "",
            }
        self.refresh()

    def _reset_presser(self):
        self._presser = None
        self.refresh()

    def _answer_presser_question(self, q, ans):
        """Record one answer; its effects apply immediately (mainline
        applies each answer as given); advance or finish the presser."""
        st = self._presser
        if not st or st.get("done"):
            return
        label = st.get("focus_label") or st.get("focus") or "presser"
        st["answers"].append({
            "question": q, "answer": ans,
            "reaction": ans.get("reaction", "") if isinstance(ans, dict)
            else "",
        })
        st["index"] = st.get("index", 0) + 1
        self._apply_press_answers([ans], label, record=False)
        if st["index"] >= len(st.get("questions") or []):
            self._finish_presser()
        else:
            self.refresh()

    def _finish_presser(self):
        """Record the presser in history and close it (effects were
        already applied answer-by-answer)."""
        st = self._presser
        if not st:
            return
        answers = [rec.get("answer") for rec in (st.get("answers") or [])
                   if isinstance(rec.get("answer"), dict)]
        label = st.get("focus_label") or st.get("focus") or "presser"
        if answers:
            summary = self._presser_summary(answers, label)
            self._record_presser_history(label, summary)
        else:
            summary = "No questions answered — the presser ended quietly."
        st["done"] = True
        st["summary"] = summary
        self.refresh()

    def _presser_summary(self, answers, kind):
        """Combined summary line for a finished presser."""
        total_fan = sum(int(a.get("fan_effect", 0) or 0) for a in answers)
        summary = (f"{kind}: "
                   + "; ".join(str(a.get("label", "")) for a in answers))
        if total_fan:
            summary += (f" [fans {'loved' if total_fan > 0 else 'hated'} "
                        f"it: {total_fan:+d}]")
        return summary

    def _record_presser_history(self, kind, summary):
        career = self._career()
        hist = _safe(lambda: getattr(career, "press_history", None))
        if not isinstance(hist, list):
            return
        gm = self._gm()
        cd = (_safe(lambda: getattr(gm, "current_date", None))
              or _safe(lambda: getattr(self.game, "current_date", None)))
        iso = cd.isoformat() if cd is not None and hasattr(
            cd, "isoformat") else ""
        try:
            hist.append({"date": iso, "type": f"presser ({kind})",
                         "summary": summary})
        except Exception:
            pass

    def _apply_press_answers(self, answers, kind, record=True):
        """Apply press-conference answer effects.

        Mirrors mainline ``_career_apply_press_answers``: roster morale,
        board confidence, fan sentiment, and (unless record=False) a
        press_history entry. Returns the summary string.
        """
        if not answers:
            return ""
        team = self._user_team()
        gm = self._gm()
        cd = (_safe(lambda: getattr(gm, "current_date", None))
              or _safe(lambda: getattr(self.game, "current_date", None)))
        iso = cd.isoformat() if cd is not None and hasattr(
            cd, "isoformat") else ""
        total_morale = sum(int(a.get("morale_effect", 0) or 0)
                           for a in answers)
        total_board = sum(int(a.get("board_effect", 0) or 0)
                          for a in answers)
        total_fan = sum(int(a.get("fan_effect", 0) or 0) for a in answers)
        if total_morale and team is not None:
            for p in (getattr(team, "roster", []) or []):
                try:
                    m = float(getattr(p, "morale", 70) or 70)
                    p.morale = max(
                        1.0, min(100.0, m + (5 if total_morale > 0 else -5)))
                except Exception:
                    pass
        if total_board:
            board = self._board()
            if board is not None:
                _safe(lambda: board.apply_press_board_effect(
                    total_board, iso))
        if total_fan and team is not None:
            try:
                from fan_sentiment import nudge_fan_sentiment
                _safe(lambda: nudge_fan_sentiment(
                    team, total_fan * 2.5,
                    reason=f"presser ({kind}): {total_fan:+d}",
                    current_date=cd))
            except Exception:
                pass
        summary = self._presser_summary(answers, kind)
        if record:
            self._record_presser_history(kind, summary)
        return summary

    # ------------------------------------------------------------------
    # Opposition report (scouting)
    # ------------------------------------------------------------------
    def _next_opponent(self):
        """(opponent_team, game_date) for the next unplayed user-team game.

        Returns (None, None) when there is no upcoming game.
        """
        team = self._user_team()
        league = self._league()
        if team is None or league is None:
            return None, None
        try:
            from .schedule import (_schedule_entries, _game_played_state,
                                   _results_by_date, _date_key)
        except Exception:
            return None, None
        gm = self._gm()
        today = (_safe(lambda: getattr(gm, "current_date", None))
                 or _safe(lambda: getattr(self.game, "current_date", None)))
        today_k = _safe(lambda: _date_key(today))
        by_date = _safe(lambda: _results_by_date(self.game), {}) or {}
        my_name = _safe(lambda: str(getattr(team, "team_name", "")), "") \
            or ""

        def _is_mine(x):
            return x is team or str(getattr(x, "team_name", x) or "") \
                == my_name

        def _resolve(x):
            """Team object for a schedule entry side (object or name)."""
            if getattr(x, "team_name", None) is not None:
                return x
            want = str(x or "")
            for t in (_safe(lambda: list(getattr(league, "teams", [])
                                         or []), []) or []):
                if str(getattr(t, "team_name", "") or "") == want:
                    return t
            return None

        cands = []
        for entry in (_safe(lambda: list(_schedule_entries(self.game)), [])
                      or []):
            try:
                home, away = (entry.get("home_team"),
                              entry.get("away_team"))
                if not (_is_mine(home) or _is_mine(away)):
                    continue
                played = _safe(lambda: _game_played_state(
                    entry, self.game, by_date)[0], True)
                if played:
                    continue
                dk = _safe(lambda: _date_key(entry.get("date")))
                if dk is None:
                    continue
                if today_k is not None and dk < today_k:
                    continue
                opp = _resolve(away if _is_mine(home) else home)
                if opp is None:
                    continue
                cands.append((dk, opp, entry.get("date")))
            except Exception:
                continue
        if not cands:
            return None, None
        cands.sort(key=lambda c: c[0])
        return cands[0][1], cands[0][2]

    @staticmethod
    def _team_facet_avgs(team):
        """Average shooting/defense/physicality/skating/goaltending."""
        roster = [p for p in (_safe(
            lambda: list(getattr(team, "roster", []) or []), []) or [])
            if not getattr(p, "is_injured", False)]
        if not roster:
            return None

        def _avg(players, attr):
            vals = [float(getattr(p, attr, 0) or 0) for p in players]
            return round(sum(vals) / len(vals), 1) if vals else 0.0

        skaters = [p for p in roster
                   if str(getattr(p, "primary_position", "") or "").upper()
                   != "GOALIE"]
        goalies = [p for p in roster
                   if str(getattr(p, "primary_position", "") or "").upper()
                   == "GOALIE"]
        return {
            "shooting": _avg(skaters, "shooting"),
            "defense": _avg(skaters, "defense"),
            "physicality": _avg(skaters, "physicality"),
            "skating": _avg(skaters, "skating"),
            "goaltending": _avg(goalies, "goaltending") if goalies else 10.0,
        }

    def _extra_tactical_advice(self, opp):
        """Matchup advice from real user-team vs opponent stat comparisons."""
        mine = self._team_facet_avgs(self._user_team())
        theirs = self._team_facet_avgs(opp)
        if not mine or not theirs:
            return []
        out = []
        m, t = mine, theirs
        if m["shooting"] > t["defense"] + 1.0:
            out.append(f"Our finishing ({m['shooting']:.1f}) outranks their "
                       f"slot defense ({t['defense']:.1f}) — get pucks to "
                       "the net from the slot.")
        if m["goaltending"] > t["goaltending"] + 1.0:
            out.append(f"Goaltending edge ({m['goaltending']:.1f} vs "
                       f"{t['goaltending']:.1f}) — stay patient; they'll "
                       "have to open up.")
        if m["defense"] > t["shooting"] + 1.0:
            out.append(f"Our team defense ({m['defense']:.1f}) smothers "
                       f"their attack ({t['shooting']:.1f}) — protect the "
                       "slot and let them shoot from outside.")
        if m["physicality"] > t["physicality"] + 1.0:
            out.append(f"We're the heavier side ({m['physicality']:.1f} vs "
                       f"{t['physicality']:.1f}) — finish every check "
                       "early and wear them down.")
        if m["skating"] > t["skating"] + 1.0:
            out.append(f"Skating advantage ({m['skating']:.1f} vs "
                       f"{t['skating']:.1f}) — push the pace in transition.")
        if t["shooting"] > m["defense"] + 1.0:
            out.append(f"Their attack ({t['shooting']:.1f}) beats our "
                       f"defense ({m['defense']:.1f}) — collapse low and "
                       "block the middle.")
        if t["goaltending"] > m["goaltending"] + 1.0:
            out.append(f"Their goalie ({t['goaltending']:.1f}) outranks ours "
                       f"({m['goaltending']:.1f}) — traffic and tips are "
                       "the way through.")
        return out

    def _opposition_report_data(self):
        """Full scout report for the next opponent, or None.

        Combines mainline generate_opposition_report with extra tactical
        advice derived from real user-vs-opponent stat comparisons, and
        guarantees at least 3 advice items.
        """
        opp, gdate = self._next_opponent()
        if opp is None:
            return None
        import manager_career as mc
        league = self._league()
        standings = _safe(
            lambda: getattr(league, "standings", None), {}) or {}
        report = _safe(lambda: mc.generate_opposition_report(opp, standings))
        if not report:
            return None
        advice = [a for a in (report.get("tactical_advice") or []) if a]
        for a in self._extra_tactical_advice(opp):
            if a and a not in advice:
                advice.append(a)
        if len(advice) < 3:
            danger = report.get("danger_level", "unknown")
            record = report.get("record", "unknown")
            team_nm = report.get("team", "the opposition")
            fillers = [
                f"No clear matchup edge on paper (danger: {danger}, "
                f"record {record}) — win the special-teams battle.",
                f"Limited tape on {team_nm} — establish the forecheck "
                "early and force them to show their hand.",
            ]
            for f in fillers:
                if len(advice) >= 3:
                    break
                if f not in advice:
                    advice.append(f)
        while len(advice) < 3:
            advice.append("Play our game: manage the puck, finish checks, "
                          "and stay out of the box.")
        report["tactical_advice"] = advice
        report["game_date_str"] = _safe(
            lambda: gdate.isoformat()
            if hasattr(gdate, "isoformat") else str(gdate), "") or ""
        return report

    def _build_opposition(self, lay):
        data = _safe(self._opposition_report_data)
        if not data:
            lay.addWidget(QLabel("No upcoming game on the schedule — "
                                 "no opposition report."))
            return
        head = QLabel(f"{data.get('team', 'Opponent')}  ·  "
                      f"{data.get('game_date_str', '')}")
        head.setStyleSheet("font-weight: 800; font-size: 15px; "
                           "color: #f0c75e;")
        lay.addWidget(head)
        meta = QLabel(f"Danger: {data.get('danger_level', '?')}  ·  "
                      f"Record: {data.get('record', '?')}")
        meta.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        lay.addWidget(meta)
        for title, items, color in (
                ("Strengths", data.get("strengths") or [], "#F44336"),
                ("Weaknesses", data.get("weaknesses") or [], "#4CAF50")):
            tl = QLabel(title)
            tl.setStyleSheet(f"font-weight: 700; color: {color}; "
                             f"font-size: 13px;")
            lay.addWidget(tl)
            for it in items:
                bl = QLabel(f"• {it}")
                bl.setWordWrap(True)
                bl.setStyleSheet("font-size: 13px;")
                lay.addWidget(bl)
        kp = data.get("key_players") or []
        if kp:
            kpl = QLabel("Key players to watch: " + ", ".join(kp))
            kpl.setWordWrap(True)
            kpl.setStyleSheet("font-size: 13px;")
            lay.addWidget(kpl)
        al = QLabel("Tactical advice")
        al.setStyleSheet("font-weight: 700; color: #7fb3ff; "
                         "font-size: 13px;")
        lay.addWidget(al)
        for i, a in enumerate(data.get("tactical_advice") or [], 1):
            bl = QLabel(f"{i}. {a}")
            bl.setWordWrap(True)
            bl.setStyleSheet("font-size: 13px;")
            lay.addWidget(bl)

    # ------------------------------------------------------------------
    # Squad — private player chats (port of manager_hub_window._build_squad_tab)
    # ------------------------------------------------------------------
    def _build_squad(self, lay):
        """Squad list + private-chat buttons for the selected player."""
        team = self._user_team()
        if team is None:
            lay.addWidget(QLabel("Start a career to manage your squad."))
            return

        cols = ["Player", "Pos", "Age", "Morale", "Mood", "Squad Status",
                "Concern"]
        t = QTableWidget()
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setSelectionMode(QTableWidget.SingleSelection)
        t.setSortingEnabled(False)
        t.setMaximumHeight(280)
        lay.addWidget(t)
        self._squad_table = t

        # Chat buttons — one per CHAT_ACTIONS entry (mainline parity).
        import manager_career as mc
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for key, info in mc.CHAT_ACTIONS.items():
            btn = QPushButton(info["label"])
            btn.setToolTip(info.get("desc", ""))
            btn.clicked.connect(
                lambda _checked=False, k=key: self._do_chat(k))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        hint = QLabel("Select a player, then pick a private chat action. "
                      "Chats lose their punch if repeated within 3 days.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        lay.addWidget(hint)

        self._refresh_squad_table()

    def _refresh_squad_table(self):
        """Rebuild the squad table from the live roster (post-chat refresh)."""
        t = self._squad_table
        if t is None:
            return
        import manager_career as mc
        try:
            from game_classes import position_label as _pl
        except Exception:
            _pl = None
        team = self._user_team()
        roster = sorted(getattr(team, "roster", []) or [],
                        key=lambda p: (getattr(p, "last_name", ""),
                                       getattr(p, "first_name", "")))
        t.setSortingEnabled(False)
        t.setRowCount(len(roster))
        for r, p in enumerate(roster):
            name = (f"{getattr(p, 'first_name', '')} "
                    f"{getattr(p, 'last_name', '')}").strip()
            letter = getattr(p, "captaincy", None)
            if letter:
                name = f"{name} ({letter})"
            pos = _safe(lambda: _pl(p)) if _pl else "?"
            morale = getattr(p, "morale", 70) or 70
            happiness = getattr(p, "happiness", 70) or 70
            t.setItem(r, 0, QTableWidgetItem(name))
            t.setItem(r, 1, QTableWidgetItem(str(pos or "?")))
            t.setItem(r, 2, _NumericItem(str(getattr(p, "age", "") or ""),
                                         getattr(p, "age", 0) or 0))
            t.setItem(r, 3, QTableWidgetItem(
                _safe(lambda: mc.morale_label(morale)) or str(morale)))
            t.setItem(r, 4, QTableWidgetItem(
                _safe(lambda: mc.happiness_label(happiness))
                or str(happiness)))
            t.setItem(r, 5, QTableWidgetItem(
                str(getattr(p, "squad_status", "Rotation") or "Rotation")))
            t.setItem(r, 6, QTableWidgetItem(
                f"{getattr(p, 'playing_time_concern', 0) or 0}%"))
            for c in range(7):
                t.item(r, c).setData(Qt.UserRole + 1, p)
        t.resizeColumnsToContents()
        t.setSortingEnabled(True)

    def _selected_squad_player(self):
        t = self._squad_table
        if t is None:
            return None
        items = t.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole + 1)

    def _do_chat(self, action):
        """Private chat with the selected player (mainline _do_chat parity)."""
        p = self._selected_squad_player()
        if p is None:
            QMessageBox.information(self, "Squad", "Select a player first.")
            return
        import manager_career as mc
        gm = self._gm()
        today = (_safe(lambda: getattr(gm, "current_date", None))
                 or _safe(lambda: getattr(self.game, "current_date", None)))
        try:
            text, _effects = mc.chat_with_player(p, action, today=today)
        except Exception as exc:
            QMessageBox.warning(self, "Private Chat",
                                f"Chat failed: {exc}")
            return
        QMessageBox.information(self, "Private Chat", text)
        self._refresh_squad_table()
