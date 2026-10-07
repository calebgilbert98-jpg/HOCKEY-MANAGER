"""Playoffs screen: Stanley Cup playoff bracket.

Ported from web_ui/screens/playoffs.py + web_ui/static/js/playoffs.js.
Bracket renders champion / live / not-started modes; each series card
opens a series detail dialog (status, tale of the tape, games,
storylines, players to watch, road ahead). Before Round 1 the bracket
is a standings projection.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .base import BaseScreen


# ----------------------------------------------------------------------
# Game-data helpers (ported from web_ui/screens/playoffs.py, Flask removed)
# ----------------------------------------------------------------------

ROUND_LABELS = {
    "wild_card": "Round 1",
    "division_semifinals": "Round 2",
    "division_finals": "Division Finals",
    "conference_finals": "Conference Finals",
    "stanley_cup_final": "Stanley Cup Final",
}

ROUND_ORDER = ["wild_card", "division_semifinals", "division_finals",
               "conference_finals", "stanley_cup_final"]


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return getattr(game, "game_manager", None) or game


def _abbr(team):
    try:
        from web_ui.bridge import to_web_team
        t = to_web_team(team)
        return _safe(lambda: t.get("abbr") or t.get("name"), "?") or "?"
    except Exception:
        pass
    try:
        name = getattr(team, "team_name", str(team))
        return "".join(w[0] for w in str(name).split()[:2]).upper() or "?"
    except Exception:
        return "?"


def _series_to_web(s):
    """PlayoffSeries -> plain dict."""
    t1 = _safe(lambda: s.team1)
    t2 = _safe(lambda: s.team2)
    t1_wins = _safe(lambda: int(s.team1_wins or 0), 0)
    t2_wins = _safe(lambda: int(s.team2_wins or 0), 0)
    complete = _safe(lambda: bool(s.is_complete), False)
    winner = _safe(lambda: s.winner)
    winner_name = _abbr(winner) if winner else None
    return {
        "id": _safe(lambda: str(getattr(s, "series_id", "") or ""), ""),
        "round": _safe(lambda: getattr(s, "round_name", "") or ""),
        "team1": _abbr(t1),
        "team1_name": _safe(lambda: getattr(t1, "team_name", "") or ""),
        "team2": _abbr(t2),
        "team2_name": _safe(lambda: getattr(t2, "team_name", "") or ""),
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "score": f"{t1_wins}-{t2_wins}",
        "complete": complete,
        "winner": winner_name,
        "leader": winner_name or (_abbr(t1) if t1_wins > t2_wins
                                 else _abbr(t2) if t2_wins > t1_wins else None),
    }


def _bracket(game):
    gm = _resolve_gm(game)
    league = _safe(lambda: getattr(gm, "league", None))
    if league is None:
        league = _safe(lambda: getattr(game, "league", None))
    return _safe(lambda: getattr(league, "playoff_bracket", None))


def _bracket_payload(game):
    """Whole bracket -> plain dict. Never raises."""
    bracket = _bracket(game)
    if bracket is None:
        return {"started": False, "champion": None, "current_round": None,
                "rounds": [], "is_projection": True}
    series_map = _safe(lambda: dict(getattr(bracket, "playoff_series", None)
                                    or {}), {})
    rounds = []
    for key in ROUND_ORDER:
        series_list = _safe(lambda: list(series_map.get(key, []) or []), [])
        rounds.append({
            "key": key,
            "label": ROUND_LABELS.get(key, key.replace("_", " ").title()),
            "series": [_series_to_web(s) for s in series_list],
        })
    started = any(r["series"] for r in rounds)
    current_key = _safe(lambda: getattr(bracket, "current_round", ""), "")
    champion = _safe(lambda: getattr(bracket, "stanley_cup_champion", None))
    return {
        "started": started,
        "champion": _abbr(champion) if champion else None,
        "champion_name": _safe(lambda: getattr(champion, "team_name", ""), "")
        if champion else "",
        "current_round": ROUND_LABELS.get(current_key, current_key)
        if current_key else None,
        "rounds": rounds,
        "is_projection": not started,
    }


def _projection_payload(game):
    """Standings-based projection bracket (built on a copy, never the real one)."""
    try:
        import playoff_system as ps
    except Exception:
        return {"available": False, "rounds": []}
    bracket = _bracket(game)
    if bracket is None:
        try:
            bracket = ps.PlayoffBracket()
        except Exception:
            return {"available": False, "rounds": []}
    try:
        proj = ps.PlayoffBracket()
        proj.build_projection()
    except Exception:
        return {"available": False, "rounds": []}
    sm = _safe(lambda: dict(getattr(proj, "playoff_series", None) or {}), {})
    rounds = []
    for key in ROUND_ORDER:
        series_list = _safe(lambda: list(sm.get(key, []) or []), [])
        rounds.append({
            "key": key,
            "label": ROUND_LABELS.get(key, key.replace("_", " ").title()),
            "series": [_series_to_web(s) for s in series_list],
        })
    return {"available": any(r["series"] for r in rounds), "rounds": rounds}


def _series_index(game):
    """Map series id -> (series, bracket) for detail lookup."""
    idx = {}
    bracket = _bracket(game)
    if bracket is None:
        return idx
    sm = _safe(lambda: dict(getattr(bracket, "playoff_series", None) or {}),
               {}) or {}
    for series_list in sm.values():
        for s in _safe(lambda: list(series_list or []), []) or []:
            sid = _safe(lambda: str(getattr(s, "series_id", "") or ""))
            if sid:
                idx[sid] = (s, bracket)
    return idx


def _series_detail(game, series_id):
    """Series detail dict: status, tape, games, storylines, watch, road ahead."""
    try:
        import playoff_system as ps
    except Exception:
        return {"found": False}
    found = _series_index(game).get(series_id)
    projected = False
    if found is None:
        # Maybe it's a projection series id.
        proj = _projection_payload(game)
        if proj["available"]:
            # Look up the projection bracket again for the raw series.
            bracket = _bracket(game)
            try:
                import playoff_system as ps2
                pbr = ps2.PlayoffBracket()
                pbr.build_projection()
                pbr.is_projection = True
                sm = _safe(lambda: dict(getattr(pbr, "playoff_series", None)
                                        or {}), {}) or {}
                for series_list in sm.values():
                    for s in _safe(lambda: list(series_list or []), []) or []:
                        if _safe(lambda: str(getattr(s, "series_id", "")
                                             or "")) == series_id:
                            found = (s, pbr)
                            break
                    if found:
                        break
            except Exception:
                pass
    if found is None:
        return {"found": False}
    series, bracket = found
    projected = bool(_safe(lambda: getattr(bracket, "is_projection", False),
                           False))
    try:
        t1 = _safe(lambda: series.team1)
        t2 = _safe(lambda: series.team2)
        status, _dec = ps.series_status_text(series)

        def _team_card(t):
            nm = _safe(lambda: getattr(t, "team_name", "") or "", "")
            pos = _safe(lambda: getattr(t, "standings_position", ""), "")
            return {
                "name": nm, "abbr": _abbr(t), "seed": pos,
                "record": {
                    "w": _safe(lambda: int(getattr(t, "wins", 0) or 0), 0),
                    "l": _safe(lambda: int(getattr(t, "losses", 0) or 0), 0),
                    "otl": _safe(lambda: int(getattr(t, "ot_losses", 0)
                                             or getattr(t, "otl", 0) or 0), 0),
                },
                "gf": _safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0),
                "ga": _safe(lambda: int(getattr(t, "goals_against", 0) or 0),
                            0),
            }

        detail = {
            "found": True,
            "id": series_id,
            "projected": projected,
            "round": _safe(lambda: getattr(series, "round_name", "") or ""),
            "teams": [_team_card(t1), _team_card(t2)],
            "score": _series_to_web(series),
            "status": status or "Not started",
            "storylines": _safe(
                lambda: list(ps._series_storylines(series)), []) or [],
            "players_to_watch": [],
            "games": [],
            "road_ahead": None,
        }
        for g in _safe(lambda: list(getattr(series, "game_results", None)
                                    or []), []) or []:
            try:
                detail["games"].append({
                    "game": g.get("game_number", len(detail["games"]) + 1),
                    "team1_won": bool(g.get("team1_won")),
                    "score": str(g.get("score", "") or ""),
                    "ot": bool(g.get("ot", False)),
                })
            except Exception:
                continue
        if not projected:
            for t in (t1, t2):
                for pts, name, g, a in ps._top_playoff_scorers(t, n=3):
                    detail["players_to_watch"].append({
                        "team": _abbr(t), "name": name,
                        "pts": pts, "g": g, "a": a,
                    })
        try:
            nxt_key, nxt = ps.series_target(bracket, series)
            if nxt_key:
                detail["road_ahead"] = {
                    "round": ROUND_LABELS.get(
                        nxt_key, nxt_key.replace("_", " ").title()),
                    "opponent": (_abbr(nxt.team1) + " vs " +
                                 _abbr(nxt.team2)) if nxt is not None
                                 else "TBD",
                }
        except Exception:
            pass
        return detail
    except Exception:
        return {"found": False}


# ----------------------------------------------------------------------
# Series detail dialog
# ----------------------------------------------------------------------

class SeriesDetailDialog(QDialog):
    """Series detail (desktop SeriesDetailPopup parity)."""

    def __init__(self, game, series_id, parent=None):
        super().__init__(parent)
        self.game = game
        self.series_id = series_id
        self.setWindowTitle("Series Detail")
        self.setMinimumSize(620, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._title = QLabel("Series")
        self._title.setObjectName("dialog-title")
        layout.addWidget(self._title)
        self._sub = QLabel("")
        self._sub.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(self._sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll, 1)
        inner = QWidget()
        self._body = QVBoxLayout(inner)
        self._body.setSpacing(8)
        self._body.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary-btn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._load()

    def _load(self):
        try:
            d = _series_detail(self.game, self.series_id)
        except Exception as e:
            print(f"[playoffs] series detail failed: {e}")
            d = {"found": False}
        if not d.get("found"):
            self._body.addWidget(self._empty("Series not found."))
            return
        t1, t2 = d["teams"]
        self._title.setText(f"{t1['name']} vs {t2['name']}")
        self._sub.setText(
            f"{d['round']}{' · projection' if d['projected'] else ''}")
        score = d["score"]
        self._body.addWidget(self._section_label(d["status"]))
        s_line = QLabel(f"{score['score']}"
                        + (" · final" if score["complete"] else ""))
        s_line.setStyleSheet(
            "color: #ffffff; font-size: 20px; font-weight: 800;")
        self._body.addWidget(s_line)

        # Tale of the tape
        tape = QFrame()
        tape.setObjectName("tile")
        tl = QHBoxLayout(tape)
        tl.setContentsMargins(14, 10, 14, 10)
        for t in (t1, t2):
            seed = f" #{t['seed']}" if t["seed"] else ""
            card = QLabel(
                f"<b>{t['abbr']}</b>{seed}<br>{t['name']}<br>"
                f"<span style='color:#8b95ab'>{t['record']['w']}-"
                f"{t['record']['l']}-{t['record']['otl']} · "
                f"{t['gf']} GF / {t['ga']} GA</span>")
            card.setStyleSheet("color: #ffffff; font-size: 13px;")
            card.setTextFormat(Qt.RichText)
            tl.addWidget(card)
            if t is t1:
                x = QLabel("VS")
                x.setStyleSheet(
                    "color: #8b95ab; font-weight: 800; font-size: 14px;")
                tl.addWidget(x)
        self._body.addWidget(tape)
        if d["projected"]:
            note = QLabel("Tale of the tape (regular season). Projection "
                          "only — the real series starts at 0–0.")
            note.setStyleSheet("color: #8b95ab; font-size: 12px;")
            note.setWordWrap(True)
            self._body.addWidget(note)

        # Games
        if d["games"]:
            self._body.addWidget(self._section_label("Games"))
            tbl = QTableWidget(len(d["games"]), 3)
            tbl.setHorizontalHeaderLabels(["", "Result", "Score"])
            tbl.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for i, g in enumerate(d["games"]):
                winner = t1["abbr"] if g["team1_won"] else t2["abbr"]
                tbl.setItem(i, 0, QTableWidgetItem(f"G{g['game']}"))
                tbl.setItem(i, 1, QTableWidgetItem(f"{winner} win"))
                tbl.setItem(i, 2, QTableWidgetItem(
                    g["score"] + (" (OT)" if g["ot"] else "")))
            self._body.addWidget(tbl)

        # Storylines
        if d["storylines"]:
            self._body.addWidget(self._section_label("Storylines"))
            for line in d["storylines"]:
                lbl = QLabel(f"•  {line}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: #ffffff; font-size: 13px;")
                self._body.addWidget(lbl)

        # Players to watch
        if d["players_to_watch"]:
            self._body.addWidget(
                self._section_label("Players to watch (playoff scoring)"))
            ptw = d["players_to_watch"]
            tbl = QTableWidget(len(ptw), 3)
            tbl.setHorizontalHeaderLabels(["Team", "Player", "Pts (G, A)"])
            tbl.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for i, p in enumerate(ptw):
                tbl.setItem(i, 0, QTableWidgetItem(p["team"]))
                tbl.setItem(i, 1, QTableWidgetItem(p["name"]))
                tbl.setItem(i, 2, QTableWidgetItem(
                    f"{p['pts']} pts ({p['g']}G, {p['a']}A)"))
            self._body.addWidget(tbl)

        # Road ahead
        if d["road_ahead"]:
            self._body.addWidget(self._section_label("Road ahead"))
            ra = d["road_ahead"]
            lbl = QLabel(
                f"Winner advances to the <b>{ra['round']}</b>"
                + (f" vs <b>{ra['opponent']}</b>"
                   if ra.get("opponent") and ra["opponent"] != "TBD" else "."))
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("color: #8b95ab; font-size: 13px;")
            lbl.setWordWrap(True)
            self._body.addWidget(lbl)

    @staticmethod
    def _section_label(text):
        lbl = QLabel(text)
        lbl.setObjectName("section-header")
        return lbl

    @staticmethod
    def _empty(msg):
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px; padding: 24px;")
        return lbl


# ----------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------

class PlayoffsScreen(BaseScreen):
    """Stanley Cup playoff bracket. title: PLAYOFFS."""

    title = "Playoffs"

    def _build_body(self):
        self._status = QLabel("Stanley Cup Playoffs")
        self._status.setStyleSheet(
            "color: #8b95ab; font-size: 14px; font-weight: 600;")
        self._layout.addWidget(self._status)

        # Projection banner
        self._proj_banner = QFrame()
        self._proj_banner.setObjectName("tile")
        pb = QHBoxLayout(self._proj_banner)
        pb.setContentsMargins(14, 8, 14, 8)
        tag = QLabel("PROJECTION")
        tag.setStyleSheet("color: #e8b923; font-weight: 800; font-size: 12px;")
        txt = QLabel("Based on current standings — the real bracket locks in "
                     "when the regular season ends.")
        txt.setStyleSheet("color: #ffffff; font-size: 13px;")
        txt.setWordWrap(True)
        pb.addWidget(tag)
        pb.addWidget(txt, 1)
        self._proj_banner.hide()
        self._layout.addWidget(self._proj_banner)

        # Bracket scroll area (horizontal round columns)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self._bracket_layout = QHBoxLayout(inner)
        self._bracket_layout.setSpacing(16)
        self._bracket_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._scroll.setWidget(inner)
        self._layout.addWidget(self._scroll, 1)

        # Empty state
        self._empty_wrap = QFrame()
        self._empty_wrap.setObjectName("tile")
        el = QVBoxLayout(self._empty_wrap)
        el.setContentsMargins(24, 32, 24, 32)
        icon = QLabel("🏆")
        icon.setStyleSheet("font-size: 42px;")
        icon.setAlignment(Qt.AlignCenter)
        el.addWidget(icon)
        h = QLabel("Playoffs begin in April")
        h.setStyleSheet(
            "color: #ffffff; font-size: 18px; font-weight: 800;")
        h.setAlignment(Qt.AlignCenter)
        el.addWidget(h)
        p = QLabel("The bracket appears here once the regular season wraps up "
                   "and the playoff field is set.")
        p.setStyleSheet("color: #8b95ab; font-size: 13px;")
        p.setAlignment(Qt.AlignCenter)
        p.setWordWrap(True)
        el.addWidget(p)
        self._empty_wrap.hide()
        self._layout.addWidget(self._empty_wrap)
        self._layout.addStretch()

    # -- data ---------------------------------------------------------

    def refresh(self):
        try:
            data = _bracket_payload(self.game)
        except Exception as e:
            print(f"[playoffs] load failed: {e}")
            data = {"started": False, "champion": None, "current_round": None,
                    "rounds": [], "is_projection": False}
        self._render(data)

    # -- render --------------------------------------------------------

    def _clear_bracket(self):
        while self._bracket_layout.count():
            item = self._bracket_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render(self, data):
        self._clear_bracket()
        started = data["started"]
        is_projection = data.get("is_projection", False)
        rounds = data["rounds"]

        if data["champion"]:
            self._status.setText(
                f"🏆 {data.get('champion_name') or data['champion']} "
                f"win the Stanley Cup")
        elif data["current_round"]:
            self._status.setText(f"Now: {data['current_round']}")
        elif is_projection:
            self._status.setText("Projected bracket")
        else:
            self._status.setText("Stanley Cup Playoffs")

        if not started and not is_projection:
            self._scroll.hide()
            self._empty_wrap.show()
            self._proj_banner.hide()
            self._status.setText("Not yet started")
            return

        if not started and is_projection:
            # Projection bracket from standings.
            try:
                proj = _projection_payload(self.game)
            except Exception as e:
                print(f"[playoffs] projection failed: {e}")
                proj = {"available": False, "rounds": []}
            if proj["available"]:
                rounds = proj["rounds"]
                self._proj_banner.show()
            else:
                self._scroll.hide()
                self._empty_wrap.show()
                self._proj_banner.hide()
                return

        self._empty_wrap.hide()
        self._scroll.show()
        for rnd in rounds:
            if not rnd["series"]:
                continue
            col = self._round_col(rnd, data)
            self._bracket_layout.addWidget(col)
        self._bracket_layout.addStretch()

    def _round_col(self, rnd, data):
        col = QFrame()
        cl = QVBoxLayout(col)
        cl.setSpacing(10)
        cl.setAlignment(Qt.AlignTop)
        is_current = data.get("current_round") == rnd["label"]
        title = QLabel(("● " if is_current else "") + rnd["label"].upper())
        title.setStyleSheet(
            "color: %s; font-size: 14px; font-weight: 800;" %
            ("#34d399" if is_current else "#8b95ab"))
        title.setAlignment(Qt.AlignCenter)
        cl.addWidget(title)
        for s in rnd["series"]:
            cl.addWidget(self._series_card(s))
        cl.addStretch()
        return col

    def _series_card(self, s):
        card = QFrame()
        card.setObjectName("tile")
        card.setMinimumWidth(230)
        card.setCursor(Qt.PointingHandCursor)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(6)

        t1w = s["complete"] and s["winner"] == s["team1"]
        t2w = s["complete"] and s["winner"] == s["team2"]
        lead1 = not s["complete"] and s["leader"] == s["team1"]
        lead2 = not s["complete"] and s["leader"] == s["team2"]

        cl.addLayout(self._series_row(
            s["team1"], s["team1_name"], s["team1_wins"],
            winner=t1w, leads=lead1, dim=s["complete"] and not t1w))
        cl.addLayout(self._series_row(
            s["team2"], s["team2_name"], s["team2_wins"],
            winner=t2w, leads=lead2, dim=s["complete"] and not t2w))
        if s["complete"] and s["winner"]:
            note = QLabel(f"🏆 {s['winner']} wins {s['score']}")
            note.setStyleSheet(
                "color: #e8b923; font-size: 12px; font-weight: 700;")
            note.setWordWrap(True)
            cl.addWidget(note)

        if s.get("id"):
            card.setToolTip("Open series detail")
            sid = s["id"]

            def _open(event, sid=sid):
                try:
                    SeriesDetailDialog(self.game, sid, parent=self).exec()
                except Exception as e:
                    print(f"[playoffs] series detail failed: {e}")

            card.mousePressEvent = _open
        return card

    @staticmethod
    def _series_row(abbr, full_name, wins, winner=False, leads=False,
                    dim=False):
        row = QHBoxLayout()
        row.setSpacing(8)
        name = QLabel(abbr)
        name.setToolTip(full_name)
        name.setStyleSheet(
            "color: %s; font-size: 15px; font-weight: %s;" %
            ("#6b7488" if dim else "#ffffff", "800" if winner else "600"))
        row.addWidget(name)
        row.addStretch()
        badge = QLabel("★" if winner else ("leads" if leads else ""))
        badge.setStyleSheet(
            "color: %s; font-size: 12px; font-weight: 700;" %
            ("#e8b923" if winner else "#34d399"))
        row.addWidget(badge)
        w = QLabel(str(wins))
        w.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800;")
        row.addWidget(w)
        return row
