"""Awards Ceremony screen — standalone NHL Awards night stage.

Port of main branch ``awards_ceremony.open_awards_ceremony`` /
``AwardsCeremonyWindow`` (Tk) into a native Qt screen.

Full end-of-season awards night: each trophy is presented in ceremony
order with its three finalists, a dramatic winner reveal, and the voting
story (or statistical coronation) behind it. Winners match the official
season awards -- the ceremony is the presentation, not a second election.

Unlike the Ceremony tab inside Season Summary, this is a dedicated
full-screen stage experience: kicker, progress dots, trophy header,
finalist cards, reveal pacing, per-award stepping, and a "That's a wrap"
finale with the full winners table.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
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
    """Mirror of main.py _calculate_season_awards: awards_race rankings
    decide the trophies (no display-vs-reality split)."""
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
        return {"name": name, "team": team, "stats": "", "id": str(pid)}

    def _top(fn):
        try:
            r = fn()
            return _info(r[0]) if r else None
        except Exception:
            return None

    awards = {}
    awards["Hart Trophy (MVP)"] = _top(
        lambda: ar.hart_race(players, team_pct, roster_map=roster_map))
    awards["Ted Lindsay Award (Most Outstanding Player)"] = _top(
        lambda: ar.lindsay_race(players, team_pct, roster_map=roster_map))
    awards["Art Ross Trophy (Scoring Leader)"] = _top(
        lambda: ar.art_ross_race(players))
    awards['Maurice "Rocket" Richard Trophy'] = _top(
        lambda: ar.rocket_race(players))
    awards["Norris Trophy (Best Defenseman)"] = _top(
        lambda: ar.norris_race(players))
    awards["Selke Trophy (Defensive Forward)"] = _top(
        lambda: ar.selke_race(players))
    awards["Lady Byng Trophy (Sportsmanship)"] = _top(
        lambda: ar.byng_race(players))
    awards["Calder Trophy (Rookie of the Year)"] = _top(
        lambda: ar.calder_race(players, season_year=int(
            getattr(league, "season_year", 0) or 0)))
    goalies = [p for p in players if "GOALIE" in str(
        getattr(getattr(p, "primary_position", None), "name", ""))]
    awards["Vezina Trophy (Best Goalie)"] = _top(
        lambda: ar.vezina_race(goalies))
    awards["Jennings Trophy (Fewest GA)"] = _top(
        lambda: ar.jennings_race(teams))
    awards["Jack Adams (Best Coach)"] = _top(
        lambda: ar.adams_race(teams))
    return awards


def _ceremony_script(game, league):
    """Engine's full ceremony script via awards_ceremony.build_ceremony_data
    over a thin proxy (same pattern as the Season Summary Ceremony tab)."""
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


def _electorate_story(entry) -> str:
    """Who decided this award / the story behind the vote."""
    if entry.get("vote_story"):
        return entry["vote_story"]
    electorate = entry.get("electorate")
    trophy = entry.get("trophy", "")
    if not electorate:
        if "Rocket" in trophy or "Richard" in trophy:
            return (f"No vote — the goals speak for themselves: "
                    f"{entry.get('winner', {}).get('stats', '')}.")
        if "Art Ross" in trophy:
            return ("No vote — the scoring title is decided on the ice: "
                    f"{entry.get('winner', {}).get('stats', '')}.")
        if "Jennings" in trophy:
            return "No vote — fewest goals against wins it outright."
        return ""
    if "Conn Smythe" in trophy:
        return ("Decided by the PHWA at the Final — "
                "the playoff story in one name.")
    if "Ted Lindsay" in trophy:
        return ("Voted on by his fellow players — "
                "the one the dressing room respects most.")
    return f"Voted on by the {electorate}."


class AwardsCeremonyScreen(BaseScreen):
    """The NHL Awards night stage: finalists, dramatic reveals, full results."""

    title = "Awards Ceremony"

    def _build_body(self):
        # Stage container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(12)
        scroll.setWidget(inner)

        self._kicker = QLabel("")
        self._kicker.setStyleSheet(
            "color: #9aa4b8; font-size: 12px; letter-spacing: 2px;")
        self._kicker.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._kicker)

        self._progress = QLabel("")
        self._progress.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._progress)

        self._dots = QLabel("")
        self._dots.setAlignment(Qt.AlignCenter)
        self._dots.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._dots)

        self._trophy = QLabel("")
        self._trophy.setAlignment(Qt.AlignCenter)
        self._trophy.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #e8b34b;")
        self._trophy.setWordWrap(True)
        layout.addWidget(self._trophy)

        self._flavor = QLabel("")
        self._flavor.setAlignment(Qt.AlignCenter)
        self._flavor.setWordWrap(True)
        self._flavor.setStyleSheet(
            "color: #cdd6e4; font-size: 14px; font-style: italic;")
        layout.addWidget(self._flavor)

        self._body = QFrame()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._body)

        ctl = QHBoxLayout()
        self._reveal_btn = QPushButton("Reveal Winner")
        self._reveal_btn.setObjectName("primary-btn")
        self._reveal_btn.clicked.connect(self._reveal)
        self._next_btn = QPushButton("Next Award")
        self._next_btn.clicked.connect(self._next)
        self._all_btn = QPushButton("Reveal All")
        self._all_btn.clicked.connect(self._reveal_all)
        ctl.addStretch()
        ctl.addWidget(self._reveal_btn)
        ctl.addWidget(self._next_btn)
        ctl.addWidget(self._all_btn)
        ctl.addStretch()
        layout.addLayout(ctl)

        self._layout.addWidget(scroll)

        # Staged-reveal state
        self._script = []
        self._idx = 0
        self._revealed = False
        self._season = ""

        self.refresh()

    # -- data ---------------------------------------------------------
    def refresh(self):
        league = _league(self.game)
        if league is None:
            self._render_empty("No league data.")
            return
        self._season = _season_label(league)
        self._script = _ceremony_script(self.game, league) or []
        self._idx = 0
        self._revealed = False
        if not self._script:
            self._render_empty(
                "No awards to present yet — the ceremony follows the season.")
            return
        self._render_step()

    # -- rendering ----------------------------------------------------
    def _clear_body(self):
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_empty(self, text):
        self._kicker.setText("")
        self._progress.setText("")
        self._dots.setText("")
        self._trophy.setText("")
        self._flavor.setText("")
        self._clear_body()
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #6b7488; font-size: 16px;")
        lbl.setAlignment(Qt.AlignCenter)
        self._body_layout.addWidget(lbl)
        self._reveal_btn.setVisible(False)
        self._next_btn.setVisible(False)
        self._all_btn.setVisible(False)

    def _render_step(self):
        script = self._script
        idx = self._idx
        if idx >= len(script):
            self._render_finale()
            return
        e = script[idx]
        self._kicker.setText(
            f"NHL AWARDS {self._season}" if self._season else "NHL AWARDS")
        self._progress.setText(f"Award {idx + 1} of {len(script)}")
        dots = []
        for i in range(len(script)):
            if i < idx:
                dots.append('<span style="color:#22c55e">●</span>')
            elif i == idx:
                dots.append('<span style="color:#e8b34b">●</span>')
            else:
                dots.append('<span style="color:#3a4356">●</span>')
        self._dots.setText(" ".join(dots))
        self._trophy.setText(str(e.get("trophy", "")))
        self._flavor.setText(str(e.get("flavor", "")))

        self._clear_body()

        # Finalists (winner stays hidden until revealed)
        ftitle = QLabel("The finalists are…")
        ftitle.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #f2f4f8;")
        ftitle.setAlignment(Qt.AlignCenter)
        self._body_layout.addWidget(ftitle)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        finals = e.get("finalists", []) or []
        if not finals:
            none_lbl = QLabel("Finalists to be announced.")
            none_lbl.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            none_lbl.setAlignment(Qt.AlignCenter)
            self._body_layout.addWidget(none_lbl)
        for f in finals[:3]:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            nl = QLabel(str(f.get("name", "?")))
            nl.setStyleSheet(
                "font-size: 14px; font-weight: 700; color: #f2f4f8;")
            nl.setAlignment(Qt.AlignCenter)
            nl.setWordWrap(True)
            cl.addWidget(nl)
            sub = QLabel(f"{f.get('team', '')} · {f.get('stats', '')}")
            sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            sub.setAlignment(Qt.AlignCenter)
            sub.setWordWrap(True)
            cl.addWidget(sub)
            row.addWidget(card)
        row_wrap = QFrame()
        row_wrap.setLayout(row)
        self._body_layout.addWidget(row_wrap)

        if self._revealed:
            wtitle = QLabel("AND THE WINNER IS…")
            wtitle.setStyleSheet(
                "font-size: 15px; font-weight: 800; color: #e8b34b;")
            wtitle.setAlignment(Qt.AlignCenter)
            self._body_layout.addWidget(wtitle)
            w = e.get("winner", {})
            wcard = QFrame()
            wcard.setObjectName("tile")
            wcl = QVBoxLayout(wcard)
            glyph = QLabel("🏆")
            glyph.setStyleSheet("font-size: 44px;")
            glyph.setAlignment(Qt.AlignCenter)
            wcl.addWidget(glyph)
            wname = QLabel(str(w.get("name", "")))
            wname.setStyleSheet(
                "font-size: 22px; font-weight: 800; color: #e8b34b;")
            wname.setAlignment(Qt.AlignCenter)
            wname.setWordWrap(True)
            wcl.addWidget(wname)
            wsub = QLabel(f"{w.get('team', '')} · {w.get('stats', '')}")
            wsub.setStyleSheet("color: #cdd6e4; font-size: 14px;")
            wsub.setAlignment(Qt.AlignCenter)
            wsub.setWordWrap(True)
            wcl.addWidget(wsub)
            story = _electorate_story(e)
            if story:
                vs = QLabel(story)
                vs.setWordWrap(True)
                vs.setAlignment(Qt.AlignCenter)
                vs.setStyleSheet(
                    "color: #9aa4b8; font-size: 13px; font-style: italic;")
                wcl.addWidget(vs)
            self._body_layout.addWidget(wcard)

        self._reveal_btn.setVisible(not self._revealed)
        self._next_btn.setVisible(True)
        self._all_btn.setVisible(True)
        self._next_btn.setText(
            "Finish" if idx + 1 >= len(script) else "Next Award →")

    def _render_finale(self):
        self._kicker.setText("")
        self._progress.setText("Ceremony complete")
        self._dots.setText("")
        self._trophy.setText("🏆 That's a wrap")
        self._flavor.setText(
            "All awards presented. See you next season.")
        self._clear_body()

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Award", "Winner", "Team"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setRowCount(len(self._script))
        for i, s in enumerate(self._script):
            w = s.get("winner", {})
            for col, txt in enumerate(
                    [str(s.get("trophy", "")), str(w.get("name", "")),
                     str(w.get("team", ""))]):
                table.setItem(i, col, QTableWidgetItem(txt))
        self._body_layout.addWidget(table)
        self._reveal_btn.setVisible(False)
        self._next_btn.setVisible(False)
        self._all_btn.setVisible(False)

    # -- controls -----------------------------------------------------
    def _reveal(self):
        self._revealed = True
        self._render_step()

    def _next(self):
        self._idx += 1
        self._revealed = False
        self._render_step()

    def _reveal_all(self):
        if not self._script:
            return
        self._idx = len(self._script)
        self._render_finale()
