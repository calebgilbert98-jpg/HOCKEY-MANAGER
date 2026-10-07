"""Season Summary + Awards Ceremony hub (read-only).

Port of web_ui/screens/season_end.py (which ported main.py
_show_season_summary ~19203 and awards_ceremony.py ~255).

Four tabs: Awards, Leaders, Team, Ceremony. The ceremony is a
client-side staged reveal over the engine's real ceremony script
(finalists, winners, voting stories) -- reveal pacing, per-award
stepping with a hidden winner, progress dots, and a "That's a wrap"
finale.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QScrollArea, QFrame, QPushButton, QAbstractItemView,
    QHeaderView,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _league(game):
    return _safe(lambda: _gm(game).league)


def _season_label(league):
    y = _safe(lambda: int(getattr(league, "season_year", 0) or 0), 0)
    return f"{y}-{y + 1}" if y else ""


def _season_over(league):
    """True when the regular season is complete."""
    try:
        sched = _safe(lambda: list(getattr(league, "schedule", None)
                                   or []), []) or []
        if sched:
            return not any(not g.get("played", False)
                           for g in sched if isinstance(g, dict))
        bracket = _safe(lambda: getattr(league, "playoff_bracket", None))
        champ = _safe(lambda: getattr(bracket, "stanley_cup_champion", None))
        return champ is not None
    except Exception:
        return False


def _players(league):
    out = []
    for t in (_safe(lambda: list(league.teams), []) or []):
        out.extend(_safe(lambda: list(t.roster), []) or [])
    return out


def _roster_map(league):
    try:
        import awards_race as ar
        return ar.roster_team_map(
            _safe(lambda: list(league.teams), []) or [])
    except Exception:
        return {}


def _calc_season_awards_impl(game, league):
    """Web mirror of main.py _calculate_season_awards: the same
    awards_race rankings decide the trophies (no display-vs-reality
    split)."""
    import awards_race as ar
    players = _players(league)
    teams = _safe(lambda: list(league.teams), []) or []
    team_pct = {}
    for t in teams:
        gp = getattr(t, "games_played", 0) or 0
        pts = getattr(t, "points", 0) or 0
        team_pct[getattr(t, "team_name", "")] = (pts / (2 * gp)) if gp else 0.5
    roster_map = _roster_map(league)

    def _info(entry):
        if not entry:
            return None
        p = entry.get("player")
        if p is None:
            return {"name": entry.get("team") or entry.get("coach") or "?",
                    "team": entry.get("team", "?"), "stats": "", "id": ""}
        name = getattr(p, "full_name", getattr(p, "name", "?"))
        try:
            pid = int(getattr(p, "id", -1) or -1)
        except Exception:
            pid = -1
        team = (roster_map.get(pid) or getattr(p, "team_name", "Unknown")
                or "Unknown")
        g = int(getattr(p, "goals", 0) or 0)
        a = int(getattr(p, "assists", 0) or 0)
        gp = int(getattr(p, "games_played", 0) or 0)
        return {"name": name, "team": team,
                "stats": f"{g}G {a}A, {g + a} pts in {gp} GP",
                "id": str(getattr(p, "id", ""))}

    def _top(race_fn):
        try:
            r = race_fn()
            return _info(r[0]) if r else None
        except Exception:
            return None

    d = _safe(lambda: getattr(_gm(game), "current_date", None))

    awards = {}
    awards["Hart Trophy (MVP)"] = _top(
        lambda: ar.hart_race(players, team_pct, roster_map=roster_map))
    awards["Ted Lindsay Award (Most Outstanding Player)"] = _top(
        lambda: ar.lindsay_race(players, team_pct, roster_map=roster_map))
    awards["Art Ross Trophy (Scoring Leader)"] = _top(
        lambda: ar.art_ross_race(players))
    awards['Maurice "Rocket" Richard Trophy'] = _top(
        lambda: ar.rocket_race(players))
    goalies = [p for p in players
               if "GOALIE" in str(getattr(
                   getattr(p, "primary_position", None), "name", "")).upper()]
    awards["Vezina Trophy (Best Goalie)"] = _top(
        lambda: ar.vezina_race(goalies))
    awards["Norris Trophy (Best Defenseman)"] = _top(
        lambda: ar.norris_race(players))
    awards["Selke Trophy (Defensive Forward)"] = _top(
        lambda: ar.selke_race(players))
    awards["Lady Byng Trophy (Sportsmanship)"] = _top(
        lambda: ar.byng_race(players))
    syr = ar.calder_season_year(d) if d is not None else None
    awards["Calder Trophy (Rookie of the Year)"] = _top(
        lambda: ar.calder_race(players, season_year=syr))
    awards["Jennings Trophy (Fewest GA)"] = _top(
        lambda: ar.jennings_race(teams))
    awards["Jack Adams (Best Coach)"] = _top(
        lambda: ar.adams_race(teams))
    return awards


def _ceremony_script(game, league):
    """Engine's full ceremony script via awards_ceremony.build_ceremony_data
    over the thin proxy (same as the web route)."""
    try:
        import awards_ceremony as ac
    except Exception:
        return []
    gm = _gm(game)

    class _Proxy:
        pass

    p = _Proxy()
    p.league = league
    p.current_date = _safe(lambda: getattr(gm, "current_date", None))
    p._playoff_bracket = _safe(
        lambda: getattr(league, "playoff_bracket", None))

    def _calc(players):
        return _calc_season_awards_impl(game, league)

    p._calculate_season_awards = _calc
    try:
        script = ac.build_ceremony_data(p)
    except Exception:
        return []
    out = []
    for e in script or []:
        try:
            w = e.get("winner")
            if isinstance(w, str):
                winner = {"name": w, "team": e.get("winner_team", ""),
                          "stats": e.get("winner_stats", "")}
            elif w is not None:
                winner = {
                    "name": getattr(w, "full_name", getattr(w, "name", "?")),
                    "id": str(getattr(w, "id", "")),
                    "team": e.get("winner_team", ""),
                    "stats": e.get("winner_stats", ""),
                }
            else:
                continue
            finalists = []
            for f in e.get("finalists", []) or []:
                fp = f.get("player")
                finalists.append({
                    "name": f.get("name", "?"),
                    "id": str(getattr(fp, "id", "")) if fp is not None else "",
                    "team": f.get("team", ""),
                    "stats": f.get("stats", ""),
                })
            out.append({
                "trophy": e.get("trophy", ""),
                "flavor": e.get("flavor", ""),
                "winner": winner,
                "finalists": finalists,
                "electorate": e.get("electorate") or "",
                "vote_story": e.get("vote_story") or "",
            })
        except Exception:
            continue
    return out


class SeasonSummaryScreen(BaseScreen):
    """Season awards, leaders, team review, and the staged awards ceremony."""

    title = "Season"

    def _build_body(self):
        self._subtitle = QLabel("")
        self._subtitle.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(self._subtitle)

        self._loaded = {}
        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._awards_page = self._make_awards_page()
        self._leaders_page = self._make_leaders_page()
        self._team_page = self._make_team_page()
        self._ceremony_page = self._make_ceremony_page()

        self._tabs.addTab(self._awards_page, "Awards")
        self._tabs.addTab(self._leaders_page, "Leaders")
        self._tabs.addTab(self._team_page, "Team")
        self._tabs.addTab(self._ceremony_page, "Ceremony")

        self._layout.addWidget(self._tabs, 1)

    # ------------------------------------------------------------------
    def _scroll_host(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(10)
        scroll.setWidget(inner)
        return scroll, inner, layout

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                SeasonSummaryScreen._clear_layout(sub)

    def _empty(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
        return lbl

    # ------------------------------------------------------------------
    # summary data (loaded once per refresh)
    # ------------------------------------------------------------------
    def _summary(self):
        league = _league(self.game)
        if league is None:
            return None
        season = _season_label(league)
        over = _season_over(league)
        awards = {}
        if over:
            try:
                awards = _calc_season_awards_impl(self.game, league) or {}
            except Exception:
                awards = {}
        players = _players(league)
        roster_map = _roster_map(league)
        leaders = {}
        for key, keyfn, fmt in (
            ("Points",
             lambda p: int(getattr(p, "goals", 0) or 0)
             + int(getattr(p, "assists", 0) or 0),
             lambda p: int(getattr(p, "goals", 0) or 0)
             + int(getattr(p, "assists", 0) or 0)),
            ("Goals", lambda p: int(getattr(p, "goals", 0) or 0),
             lambda p: int(getattr(p, "goals", 0) or 0)),
            ("Assists", lambda p: int(getattr(p, "assists", 0) or 0),
             lambda p: int(getattr(p, "assists", 0) or 0)),
        ):
            try:
                top = sorted(players, key=keyfn, reverse=True)[:5]
                rows = []
                for p in top:
                    try:
                        pid = int(getattr(p, "id", -1) or -1)
                    except Exception:
                        pid = -1
                    rows.append((getattr(p, "full_name", "?"),
                                 roster_map.get(pid, ""), str(fmt(p))))
                leaders[key] = rows
            except Exception:
                continue
        try:
            goalies = [p for p in players
                       if "GOALIE" in str(getattr(
                           getattr(p, "primary_position", None),
                           "name", "")).upper()]
            topg = sorted(goalies,
                          key=lambda p: float(
                              getattr(p, "save_percentage", 0) or 0),
                          reverse=True)[:5]
            leaders["Save %"] = [
                (getattr(p, "full_name", "?"),
                 roster_map.get(int(getattr(p, "id", -1) or -1), ""),
                 str(round(float(getattr(p, "save_percentage", 0) or 0), 3)))
                for p in topg]
        except Exception:
            pass

        team_info = None
        try:
            ut = (_safe(lambda: _gm(self.game).user_team)
                  or _safe(lambda: getattr(self.game, "user_team", None)))
            if ut is not None:
                w = int(getattr(ut, "wins", 0) or 0)
                l = int(getattr(ut, "losses", 0) or 0)
                otl = int(getattr(ut, "ot_losses", 0)
                          or getattr(ut, "otl", 0) or 0)
                pts = int(getattr(ut, "points", 0) or 0)
                table = _safe(lambda: dict(league.standings), {}) or {}
                ordered = sorted(
                    table.items(),
                    key=lambda kv: (-int(kv[1].get("Points", 0) or 0),
                                    -int(kv[1].get("W", 0) or 0)))
                names = [k for k, _ in ordered]
                pos = (names.index(ut.team_name) + 1
                       if ut.team_name in names else None)
                tscorers = sorted(
                    [p for p in (_safe(lambda: list(ut.roster), []) or [])
                     if "GOALIE" not in str(getattr(
                         getattr(p, "primary_position", None),
                         "name", "")).upper()],
                    key=lambda p: (int(getattr(p, "goals", 0) or 0)
                                   + int(getattr(p, "assists", 0) or 0)),
                    reverse=True)[:5]
                team_info = {
                    "name": ut.team_name,
                    "record": f"{w}-{l}-{otl} ({pts} pts)",
                    "position": pos, "of_teams": len(names),
                    "top_scorers": [
                        (getattr(p, "full_name", "?"),
                         (f"{int(getattr(p, 'goals', 0) or 0)}G "
                          f"{int(getattr(p, 'assists', 0) or 0)}A = "
                          f"{int(getattr(p, 'goals', 0) or 0) + int(getattr(p, 'assists', 0) or 0)} pts"))
                        for p in tscorers],
                }
        except Exception:
            pass

        return {"season": season, "season_over": over, "awards": awards,
                "leaders": leaders, "team": team_info}

    # --- Awards tab -----------------------------------------------------
    def _make_awards_page(self):
        _scroll, _inner, layout = self._scroll_host()
        self._awards_layout = layout
        return _scroll

    def _load_awards(self):
        d = self._summary()
        self._clear_layout(self._awards_layout)
        aw = (d.get("awards") if d else {}) or {}
        if not aw:
            self._awards_layout.addWidget(self._empty(
                "Awards are decided when the season ends."))
            return
        for name, w in aw.items():
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            nl = QLabel(str(name))
            nl.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #e8b34b;")
            cl.addWidget(nl)
            if w:
                wl = QLabel(str(w.get("name", "")))
                wl.setStyleSheet(
                    "font-size: 16px; font-weight: 700; color: #f2f4f8;")
                cl.addWidget(wl)
                if w.get("team"):
                    tl = QLabel(str(w["team"]))
                    tl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
                    cl.addWidget(tl)
                if w.get("stats"):
                    sl = QLabel(str(w["stats"]))
                    sl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
                    cl.addWidget(sl)
            else:
                tl = QLabel("TBD")
                tl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
                cl.addWidget(tl)
            self._awards_layout.addWidget(card)

    # --- Leaders tab ----------------------------------------------------
    def _make_leaders_page(self):
        _scroll, _inner, layout = self._scroll_host()
        self._leaders_layout = layout
        return _scroll

    def _load_leaders(self):
        d = self._summary()
        self._clear_layout(self._leaders_layout)
        lg = (d.get("leaders") if d else {}) or {}
        if not lg:
            self._leaders_layout.addWidget(self._empty("No leaders yet."))
            return
        for key, rows in lg.items():
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            h = QLabel(str(key))
            h.setStyleSheet("font-size: 15px; font-weight: 700;")
            cl.addWidget(h)
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["#", "Player", "Team", "Value"])
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.Stretch)
            table.setAlternatingRowColors(True)
            table.setRowCount(len(rows))
            for i, (name, team, value) in enumerate(rows):
                for col, txt in enumerate(
                        [str(i + 1), str(name), str(team), str(value)]):
                    item = QTableWidgetItem(txt)
                    if col == 3:
                        item.setStyleSheet("color: #e8b34b;")
                    table.setItem(i, col, item)
            cl.addWidget(table)
            self._leaders_layout.addWidget(card)

    # --- Team tab -------------------------------------------------------
    def _make_team_page(self):
        _scroll, _inner, layout = self._scroll_host()
        self._team_layout = layout
        return _scroll

    def _load_team(self):
        d = self._summary()
        self._clear_layout(self._team_layout)
        t = d.get("team") if d else None
        if not t:
            self._team_layout.addWidget(self._empty("No team data."))
            return
        card = QFrame()
        card.setObjectName("tile")
        cl = QVBoxLayout(card)
        h = QLabel(str(t["name"]))
        h.setObjectName("section-header")
        cl.addWidget(h)
        rec = QLabel(str(t["record"]))
        rec.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #f2f4f8;")
        cl.addWidget(rec)
        if t.get("position"):
            pl = QLabel(f"League position: {t['position']} of {t['of_teams']}")
            pl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            cl.addWidget(pl)
        sh = QLabel("Top scorers")
        sh.setStyleSheet("font-size: 14px; font-weight: 700; margin-top: 8px;")
        cl.addWidget(sh)
        for name, line in t.get("top_scorers", []):
            rl = QLabel(f"{name}  —  {line}")
            rl.setStyleSheet("color: #cdd6e4; font-size: 13px;")
            cl.addWidget(rl)
        self._team_layout.addWidget(card)

    # --- Ceremony tab ---------------------------------------------------
    def _make_ceremony_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(12)
        scroll.setWidget(inner)

        self._cer_kicker = QLabel("")
        self._cer_kicker.setStyleSheet(
            "color: #9aa4b8; font-size: 12px; letter-spacing: 2px;")
        self._cer_kicker.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._cer_kicker)

        self._cer_progress = QLabel("")
        self._cer_progress.setStyleSheet(
            "color: #9aa4b8; font-size: 13px;")
        self._cer_progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._cer_progress)

        self._cer_dots = QLabel("")
        self._cer_dots.setAlignment(Qt.AlignCenter)
        self._cer_dots.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._cer_dots)

        self._cer_trophy = QLabel("")
        self._cer_trophy.setAlignment(Qt.AlignCenter)
        self._cer_trophy.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #e8b34b;")
        self._cer_trophy.setWordWrap(True)
        layout.addWidget(self._cer_trophy)

        self._cer_flavor = QLabel("")
        self._cer_flavor.setAlignment(Qt.AlignCenter)
        self._cer_flavor.setWordWrap(True)
        self._cer_flavor.setStyleSheet(
            "color: #cdd6e4; font-size: 14px; font-style: italic;")
        layout.addWidget(self._cer_flavor)

        self._cer_body = QWidget()
        self._cer_body_layout = QVBoxLayout(self._cer_body)
        self._cer_body_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._cer_body)

        ctl = QHBoxLayout()
        self._cer_reveal_btn = QPushButton("Reveal Winner")
        self._cer_reveal_btn.setObjectName("primary-btn")
        self._cer_reveal_btn.clicked.connect(self._cer_reveal)
        self._cer_next_btn = QPushButton("Next Award")
        self._cer_next_btn.clicked.connect(self._cer_next)
        self._cer_all_btn = QPushButton("Reveal All")
        self._cer_all_btn.clicked.connect(self._cer_reveal_all)
        ctl.addStretch()
        ctl.addWidget(self._cer_reveal_btn)
        ctl.addWidget(self._cer_next_btn)
        ctl.addWidget(self._cer_all_btn)
        ctl.addStretch()
        layout.addLayout(ctl)

        # staged-reveal state
        self._cer_script = []
        self._cer_idx = 0
        self._cer_revealed = False
        self._cer_season = ""
        return scroll

    def _load_ceremony(self):
        league = _league(self.game)
        if league is None:
            self._cer_render_empty("No league data.")
            return
        self._cer_season = _season_label(league)
        self._cer_script = _ceremony_script(self.game, league) or []
        self._cer_idx = 0
        self._cer_revealed = False
        if not self._cer_script:
            self._cer_render_empty(
                "No awards to present yet — the ceremony follows the season.")
            return
        self._cer_render_step()

    def _cer_render_empty(self, text):
        self._cer_kicker.setText("")
        self._cer_progress.setText("")
        self._cer_dots.setText("")
        self._cer_trophy.setText("")
        self._cer_flavor.setText("")
        self._clear_layout(self._cer_body_layout)
        self._cer_body_layout.addWidget(self._empty(text))
        self._cer_reveal_btn.setVisible(False)
        self._cer_next_btn.setVisible(False)
        self._cer_all_btn.setVisible(False)

    def _cer_render_step(self):
        script = self._cer_script
        idx = self._cer_idx
        if idx >= len(script):
            self._cer_render_finale()
            return
        e = script[idx]
        self._cer_kicker.setText(
            f"NHL AWARDS {self._cer_season}" if self._cer_season
            else "NHL AWARDS")
        self._cer_progress.setText(f"Award {idx + 1} of {len(script)}")
        dots = []
        for i in range(len(script)):
            if i < idx:
                dots.append('<span style="color:#22c55e">●</span>')
            elif i == idx:
                dots.append('<span style="color:#e8b34b">●</span>')
            else:
                dots.append('<span style="color:#3a4356">●</span>')
        self._cer_dots.setText(" ".join(dots))
        self._cer_trophy.setText(str(e.get("trophy", "")))
        self._cer_flavor.setText(str(e.get("flavor", "")))

        self._clear_layout(self._cer_body_layout)
        # finalists (winner stays hidden until revealed)
        ftitle = QLabel("Finalists")
        ftitle.setStyleSheet("font-size: 14px; font-weight: 700;")
        self._cer_body_layout.addWidget(ftitle)
        for f in e.get("finalists", []) or []:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            nl = QLabel(str(f.get("name", "?")))
            nl.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #f2f4f8;")
            cl.addWidget(nl)
            sub = QLabel(f"{f.get('team', '')} · {f.get('stats', '')}")
            sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            cl.addWidget(sub)
            self._cer_body_layout.addWidget(card)

        if self._cer_revealed:
            wtitle = QLabel("Winner")
            wtitle.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #e8b34b;")
            self._cer_body_layout.addWidget(wtitle)
            w = e.get("winner", {})
            wcard = QFrame()
            wcard.setObjectName("tile")
            wcl = QVBoxLayout(wcard)
            wname = QLabel(str(w.get("name", "")))
            wname.setStyleSheet(
                "font-size: 20px; font-weight: 800; color: #e8b34b;")
            wcl.addWidget(wname)
            wsub = QLabel(f"{w.get('team', '')} · {w.get('stats', '')}")
            wsub.setStyleSheet("color: #cdd6e4; font-size: 13px;")
            wcl.addWidget(wsub)
            if e.get("vote_story"):
                vs = QLabel(str(e["vote_story"]))
                vs.setWordWrap(True)
                vs.setStyleSheet("color: #cdd6e4; font-size: 13px;")
                wcl.addWidget(vs)
            if e.get("electorate"):
                el = QLabel("Decided by: " + str(e["electorate"]))
                el.setStyleSheet("color: #9aa4b8; font-size: 12px;")
                wcl.addWidget(el)
            self._cer_body_layout.addWidget(wcard)

        self._cer_reveal_btn.setVisible(not self._cer_revealed)
        self._cer_next_btn.setVisible(True)
        self._cer_all_btn.setVisible(True)
        self._cer_next_btn.setText(
            "Finish" if idx + 1 >= len(script) else "Next Award →")

    def _cer_render_finale(self):
        self._cer_kicker.setText("")
        self._cer_progress.setText("")
        self._cer_dots.setText("")
        self._cer_trophy.setText("\U0001F3C6 That's a wrap")
        self._cer_flavor.setText("All awards presented. See you next season.")
        self._clear_layout(self._cer_body_layout)
        self._cer_reveal_btn.setVisible(False)
        self._cer_next_btn.setVisible(False)
        self._cer_all_btn.setVisible(False)

    def _cer_reveal(self):
        self._cer_revealed = True
        self._cer_render_step()

    def _cer_next(self):
        self._cer_idx += 1
        self._cer_revealed = False
        self._cer_render_step()

    def _cer_reveal_all(self):
        script = self._cer_script
        if not script:
            return
        self._cer_kicker.setText(
            f"NHL AWARDS {self._cer_season}" if self._cer_season
            else "NHL AWARDS")
        self._cer_progress.setText("")
        self._cer_dots.setText("")
        self._cer_trophy.setText("\U0001F3C6 Full Results")
        self._cer_flavor.setText("")
        self._clear_layout(self._cer_body_layout)
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Award", "Winner", "Team"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setRowCount(len(script))
        for i, s in enumerate(script):
            w = s.get("winner", {})
            for col, txt in enumerate(
                    [str(s.get("trophy", "")), str(w.get("name", "")),
                     str(w.get("team", ""))]):
                table.setItem(i, col, QTableWidgetItem(txt))
        self._cer_body_layout.addWidget(table)
        self._cer_reveal_btn.setVisible(False)
        self._cer_next_btn.setVisible(False)
        self._cer_all_btn.setVisible(False)

    # ------------------------------------------------------------------
    def _on_tab_changed(self, idx):
        name = ["awards", "leaders", "team", "ceremony"][idx]
        if name not in self._loaded:
            self._loaded[name] = True
            self._load_tab(name)

    def _load_tab(self, name):
        loaders = {
            "awards": self._load_awards,
            "leaders": self._load_leaders,
            "team": self._load_team,
            "ceremony": self._load_ceremony,
        }
        try:
            loaders[name]()
        except Exception as e:
            print(f"[season-summary] {name} tab failed: {e}")

    def refresh(self):
        idx = self._tabs.currentIndex()
        name = ["awards", "leaders", "team", "ceremony"][idx]
        d = self._summary() if idx < 3 else None
        if d is not None:
            season = d.get("season", "")
            over = d.get("season_over")
            self._subtitle.setText(
                (f"{season} Season Complete! · "
                 if season else "") +
                ("Final results" if over
                 else "Season still in progress — awards finalize at season "
                      "end"))
        self._loaded.pop(name, None)
        self._loaded[name] = True
        self._load_tab(name)
