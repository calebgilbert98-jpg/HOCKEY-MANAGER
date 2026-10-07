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
    # Press
    # ------------------------------------------------------------------
    def _build_press(self, lay):
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
