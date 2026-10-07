"""Box score dialog: completed-game drill-down.

Ported from web_ui/screens/schedule.py (/api/boxscore) + web_ui/static/js
/boxscore.js. Opened from the Schedule and Playoffs screens for a given
(date, home, away) -- never from nav. 4 tabs: Scoring, Player Stats,
Lines, Team Stats.
"""
from datetime import date, datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


# ----------------------------------------------------------------------
# Game-data helpers (ported from web_ui/screens/schedule.py, Flask removed)
# ----------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


def _abbr(name):
    try:
        from web_ui.bridge import TEAM_ABBR
        hit = TEAM_ABBR.get(name)
        if hit:
            return hit
    except Exception:
        pass
    try:
        return "".join(w[0] for w in str(name).split()[:2]).upper() or "?"
    except Exception:
        return "?"


def _iso(d):
    """date/datetime/ISO string -> 'YYYY-MM-DD' or None."""
    try:
        if isinstance(d, datetime):
            return d.date().isoformat()
        if isinstance(d, date):
            return d.isoformat()
        s = str(d or "")[:10]
        return date.fromisoformat(s).isoformat()
    except Exception:
        return None


def _date_key(value):
    """Normalize a mixed-format date to datetime.date."""
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def _results_by_date(game):
    """{date: [game_result, ...]} via the app's O(1) index, rebuilt on fallback."""
    try:
        idx = getattr(game, "_results_by_date_index", None)
        if callable(idx):
            return idx() or {}
    except Exception:
        pass
    by_date = {}
    results = _safe(lambda: list(getattr(game, "game_results", None) or []), []) or []
    for r in results:
        try:
            k = _date_key(r.get("date"))
            if k is not None:
                by_date.setdefault(k, []).append(r)
        except Exception:
            continue
    return by_date


def _match_result(results, home_name, away_name):
    for r in results or []:
        try:
            if _team_name(r.get("home_team")) == home_name and \
                    _team_name(r.get("away_team")) == away_name:
                return r
        except Exception:
            continue
    return None


def _find_game_result(game, date_iso, home_name, away_name=None):
    """Locate one completed game's result dict. Never raises."""
    try:
        key = _date_key(date_iso)
        if key is None or not home_name:
            return None
        results = _results_by_date(game).get(key, [])
        if away_name:
            hit = _match_result(results, home_name, away_name)
            if hit is not None:
                return hit
        for r in results:
            try:
                if _team_name(r.get("home_team")) == home_name:
                    return r
            except Exception:
                continue
    except Exception:
        pass
    return None


def _pos_short(player):
    pos = _safe(lambda: getattr(player, "primary_position", None))
    val = _safe(lambda: getattr(pos, "value", None)) or \
        _safe(lambda: getattr(pos, "name", ""), "") or ""
    return str(val)


def _is_goalie(player):
    def _pos_name():
        return getattr(getattr(player, "primary_position", None), "name", "")
    name = str(_safe(_pos_name, "") or "").upper()
    return "GOALIE" in name


def _roster_lookup(r):
    by_id = {}
    for team in (r.get("home_team"), r.get("away_team")):
        for p in _safe(lambda: list(getattr(team, "roster", None) or []), []) or []:
            try:
                pid = getattr(p, "id", None)
                if pid is not None and pid not in by_id:
                    by_id[pid] = p
            except Exception:
                continue
    # Merge game_stats-embedded players (traded away since, etc.).
    for pid, gs in ((r.get("game_stats") or {}).items()):
        try:
            p = gs.get("player") if isinstance(gs, dict) else None
            if p is not None and pid not in by_id:
                by_id[pid] = p
        except Exception:
            continue
    return by_id


def _period_label(period):
    try:
        p = int(period)
    except (TypeError, ValueError):
        return "?"
    if p <= 3:
        return f"Period {p}"
    if p == 4:
        return "Overtime"
    return "Shootout"


def _player_name(by_id, pid):
    return _safe(lambda: getattr(by_id.get(pid), "full_name", "Unknown"),
                 "Unknown")


def _scoring_summary(r, by_id, home_name, away_name):
    """Goals grouped by period with running score."""
    events = _safe(lambda: list(r.get("event_log") or []), []) or []
    goals = [e for e in events
             if isinstance(e, dict) and e.get("type") == "GOAL_ADVANCED"]

    def _key(e):
        d = e.get("details", {}) if isinstance(e.get("details"), dict) else {}
        return (d.get("period", 99), e.get("timestamp", 0))

    goals.sort(key=_key)
    if not goals:
        # Fallback for quick-simmed games: notable Goal events.
        for ne in _safe(lambda: list(r.get("notable_events") or []), []) or []:
            try:
                if isinstance(ne, dict) and ne.get("event") == "Goal":
                    goals.append({"_ne": True, "details": {
                        "period": ne.get("period", 1),
                        "time_str": "",
                        "scorer_id": getattr(ne.get("player"), "id", None),
                        "assist_ids": [],
                        "strength": "EV",
                        "goal_type": "",
                    }, "timestamp": 0})
            except Exception:
                continue

    out = []
    home_running = away_running = 0
    for e in goals:
        try:
            d = e.get("details", {}) if isinstance(e.get("details"), dict) else {}
            period = d.get("period", 1)
            scorer_id = d.get("scorer_id")
            sp = by_id.get(scorer_id)
            scorer_team = _safe(lambda: getattr(sp, "team_name", ""), "") or ""
            if scorer_team == home_name:
                home_running += 1
            elif scorer_team == away_name:
                away_running += 1
            assists = [_player_name(by_id, aid)
                       for aid in (d.get("assist_ids") or [])]
            out.append({
                "period": period,
                "period_label": _period_label(period),
                "time_str": str(d.get("time_str", "") or ""),
                "scorer": _player_name(by_id, scorer_id),
                "assists": assists,
                "team": scorer_team,
                "team_abbr": _abbr(scorer_team),
                "strength": str(d.get("strength", "EV") or "EV"),
                "goal_type": str(d.get("goal_type", "") or "").replace("_", " ").title(),
                "away_running": away_running,
                "home_running": home_running,
            })
        except Exception:
            continue
    return out


def _box_player_stats(r, by_id, home_name, away_name):
    """Per-team skater + goalie tables from game_stats."""
    game_stats = r.get("game_stats") or {}
    # GA per goalie from the goal events (engines that don't track
    # per-goalie GA still record the beaten goalie).
    ga_by_goalie = {}
    try:
        events = _safe(lambda: list(r.get("event_log") or []), []) or []
        for e in events:
            if isinstance(e, dict) and e.get("type") == "GOAL_ADVANCED":
                gid = (e.get("details", {}) or {}).get("goaltender_id")
                if gid:
                    ga_by_goalie[gid] = ga_by_goalie.get(gid, 0) + 1
    except Exception:
        pass

    teams = {}
    for team_name in (away_name, home_name):
        skaters, goalies = [], []
        for pid, gs in (game_stats or {}).items():
            try:
                if not isinstance(gs, dict):
                    continue
                p = gs.get("player") or by_id.get(pid)
                if p is None:
                    continue
                if _safe(lambda: getattr(p, "team_name", ""), "") != team_name:
                    continue
                if _is_goalie(p):
                    sa = int(gs.get("shots_against", 0) or 0)
                    sv = int(gs.get("saves", 0) or 0)
                    ga = int(gs.get("goals_against", 0) or 0) or \
                        ga_by_goalie.get(getattr(p, "id", None), 0)
                    if sa <= sv:  # engine didn't track shots against
                        sa = sv + ga
                    svp = round(sv / sa * 100, 1) if sa else None
                    goalies.append({
                        "name": _player_name(by_id, getattr(p, "id", None)),
                        "sa": sa, "saves": sv, "svp": svp, "ga": ga,
                    })
                else:
                    g = int(gs.get("g", 0) or 0)
                    a = int(gs.get("a", 0) or 0)
                    skaters.append({
                        "name": _player_name(by_id, getattr(p, "id", None)),
                        "pos": _pos_short(p),
                        "g": g, "a": a, "p": g + a,
                        "sog": int(gs.get("shots_on_goal", 0) or 0),
                        "hits": int(gs.get("hits", 0) or 0),
                        "blk": int(gs.get("blocked_shots",
                                          gs.get("blocked_shots_by", 0)) or 0),
                        "fo": f"{int(gs.get('faceoffs_won', 0) or 0)}-"
                              f"{int(gs.get('faceoffs_lost', 0) or 0)}",
                    })
            except Exception:
                continue
        skaters.sort(key=lambda s: (s["p"], s["g"]), reverse=True)
        teams[team_name] = {"skaters": skaters, "goalies": goalies,
                            "has_stats": bool(skaters or goalies)}
    return teams


def _box_team_stats(r, by_id, home_name, away_name):
    """Side-by-side team comparison rows."""
    team_stats = r.get("team_stats") or {}
    a_ts = team_stats.get(away_name, {}) if isinstance(team_stats, dict) else {}
    h_ts = team_stats.get(home_name, {}) if isinstance(team_stats, dict) else {}
    if not isinstance(a_ts, dict):
        a_ts = {}
    if not isinstance(h_ts, dict):
        h_ts = {}

    def _val(ts, key, default=0):
        v = ts.get(key, default)
        return v if isinstance(v, (int, float)) else default

    # Fallbacks from the event log when team_stats are missing.
    shots_a = shots_h = saves_a = saves_h = 0
    if not a_ts and not h_ts:
        for e in _safe(lambda: list(r.get("event_log") or []), []) or []:
            try:
                if not isinstance(e, dict):
                    continue
                d = e.get("details", {}) or {}
                if e.get("type") == "GOAL_ADVANCED":
                    p = by_id.get(d.get("scorer_id"))
                    if p is not None and _safe(lambda: getattr(
                            p, "team_name", ""), "") == home_name:
                        shots_h += 1
                    else:
                        shots_a += 1
                elif e.get("type") == "SAVE_ADVANCED":
                    p = by_id.get(d.get("goaltender_id"))
                    if p is not None and _safe(lambda: getattr(
                            p, "team_name", ""), "") == home_name:
                        saves_h += 1
                        shots_a += 1
                    else:
                        saves_a += 1
                        shots_h += 1
            except Exception:
                continue

    def _blk(ts):
        return _val(ts, "blocked_shots_by_team", _val(ts, "blocked_shots"))

    return [
        {"label": "Goals", "away": r.get("away_score", 0),
         "home": r.get("home_score", 0)},
        {"label": "Shots on Goal",
         "away": _val(a_ts, "shots_on_goal", shots_a),
         "home": _val(h_ts, "shots_on_goal", shots_h)},
        {"label": "Saves",
         "away": _val(a_ts, "saves", saves_a),
         "home": _val(h_ts, "saves", saves_h)},
        {"label": "Hits",
         "away": _val(a_ts, "hits"), "home": _val(h_ts, "hits")},
        {"label": "Blocked Shots",
         "away": _blk(a_ts), "home": _blk(h_ts)},
        {"label": "Faceoffs Won",
         "away": _val(a_ts, "faceoffs_won"),
         "home": _val(h_ts, "faceoffs_won")},
        {"label": "Takeaways",
         "away": _val(a_ts, "takeaways"), "home": _val(h_ts, "takeaways")},
        {"label": "Giveaways",
         "away": _val(a_ts, "giveaways"), "home": _val(h_ts, "giveaways")},
        {"label": "Power Play",
         "away": f"{_val(a_ts, 'power_play_goals')}/"
                 f"{_val(a_ts, 'power_play_opportunities')}",
         "home": f"{_val(h_ts, 'power_play_goals')}/"
                 f"{_val(h_ts, 'power_play_opportunities')}"},
        {"label": "Short-handed Goals",
         "away": _val(a_ts, "short_handed_goals"),
         "home": _val(h_ts, "short_handed_goals")},
    ]


def _box_three_stars(r, by_id):
    """Three stars: recorded at game time when available, else ratings sort."""
    saved = r.get("three_stars")
    stars = []
    if saved:
        for s in (saved or [])[:3]:
            try:
                if not isinstance(s, dict):
                    continue
                stars.append({"name": s.get("name", "?"),
                              "team": s.get("team_name", ""),
                              "detail": str(s.get("line", "") or "")})
            except Exception:
                continue
        if stars:
            return stars
    ratings = r.get("player_ratings") or {}
    scored = []
    for team_name, pmap in ratings.items():
        if not isinstance(pmap, dict):
            continue
        for pid, rating in pmap.items():
            try:
                scored.append((float(rating or 0), _player_name(by_id, pid),
                               team_name))
            except Exception:
                continue
    scored.sort(key=lambda s: s[0], reverse=True)
    return [{"name": n, "team": t, "detail": f"{rtg:.1f}"}
            for rtg, n, t in scored[:3]]


def _box_lines(r, by_id, team_name):
    """Per-line player grades + combined line ratings."""
    grade = None
    try:
        from mesh_system import compute_skater_game_grade_v2
        grade = compute_skater_game_grade_v2
    except Exception:
        grade = None
    snap = ((r.get("lines") or {}).get(team_name)) if isinstance(
        r.get("lines"), dict) else None
    if not isinstance(snap, dict):
        return []
    game_stats = r.get("game_stats") or {}
    out = []
    units = []
    for i, line in enumerate((snap.get("Forwards") or [])[:4]):
        units.append((f"Line {i + 1}", line or []))
    for i, pair in enumerate((snap.get("Defense") or [])[:3]):
        units.append((f"Pair {i + 1}", pair or []))
    for label, pids in units:
        players = []
        grades = []
        for pid in pids or []:
            try:
                p = by_id.get(pid)
                if p is None:
                    continue
                gs = (game_stats or {}).get(pid) or {}
                g = int(gs.get("g", 0) or 0)
                a = int(gs.get("a", 0) or 0)
                gv, why = None, ""
                if grade is not None and pid in (game_stats or {}) and \
                        isinstance(gs, dict):
                    try:
                        gv, why = grade(p, gs)
                        if gv is not None:
                            grades.append(float(gv))
                    except Exception:
                        gv, why = None, ""
                players.append({
                    "name": _player_name(by_id, pid),
                    "pos": _pos_short(p),
                    "g": g, "a": a, "p": g + a,
                    "grade": round(float(gv), 1) if gv is not None else None,
                    "why": str(why or ""),
                })
            except Exception:
                continue
        rating = round(sum(grades) / len(grades), 1) if grades else None
        out.append({"label": label, "rating": rating, "players": players})
    return out


# ----------------------------------------------------------------------
# Dialog
# ----------------------------------------------------------------------

class BoxscoreDialog(QDialog):
    """Completed-game box score for one (date, home, away).

    Use set_game(date, home_team, away_team) after construction (or pass
    them to the constructor). Teams may be names or team objects; date may
    be a date/datetime/ISO string.
    """

    def __init__(self, game, date=None, home_team=None, away_team=None,
                 parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Box Score")
        self.setMinimumSize(900, 700)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        self._header = QLabel("")
        self._header.setObjectName("dialog-title")
        self._header.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._header)
        self._meta = QLabel("")
        self._meta.setAlignment(Qt.AlignCenter)
        self._meta.setStyleSheet("color: #8b95ab; font-size: 13px;")
        layout.addWidget(self._meta)
        self._stars = QLabel("")
        self._stars.setAlignment(Qt.AlignCenter)
        self._stars.setWordWrap(True)
        self._stars.setStyleSheet("color: #e8b923; font-size: 13px;")
        layout.addWidget(self._stars)

        # Error label (shown when no result is found)
        self._error = QLabel("")
        self._error.setAlignment(Qt.AlignCenter)
        self._error.setStyleSheet("color: #e5484d; font-size: 14px;")
        self._error.hide()
        layout.addWidget(self._error)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        self._scoring_pane = self._make_scroll_pane()
        self._tabs.addTab(self._scoring_pane, "Scoring")
        self._players_pane = self._make_scroll_pane()
        self._tabs.addTab(self._players_pane, "Player Stats")
        self._lines_pane = self._make_scroll_pane()
        self._tabs.addTab(self._lines_pane, "Lines")
        self._teams_pane = self._make_scroll_pane()
        self._tabs.addTab(self._teams_pane, "Team Stats")

        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Team toggles (players + lines panes)
        self._players_toggle = QHBoxLayout()
        self._lines_toggle = QHBoxLayout()
        self._players_toggle_btns = []
        self._lines_toggle_btns = []
        self._players_team = None
        self._lines_team = None

        # Close
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary-btn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._data = None
        if date is not None and home_team is not None:
            self.set_game(date, home_team, away_team)

    # -- plumbing -----------------------------------------------------

    def _make_scroll_pane(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(8)
        inner_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        scroll._inner = inner
        scroll._layout = inner_layout
        return scroll

    def _clear_pane(self, pane):
        layout = pane._layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    @staticmethod
    def _empty(msg):
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #6b7488; font-size: 14px; padding: 24px;")
        return lbl

    # -- public --------------------------------------------------------

    def set_game(self, date, home_team, away_team):
        """Load and render the box score for (date, home_team, away_team)."""
        try:
            home_name = _team_name(home_team)
            away_name = _team_name(away_team)
            iso = _iso(date)
            r = _find_game_result(self.game, iso, home_name,
                                  away_name or None)
            if r is None:
                self._data = None
                self._show_error(
                    f"No recorded result for {away_name} @ {home_name}"
                    f" ({iso or date}).")
                return
            home_name = _team_name(r.get("home_team"))
            away_name = _team_name(r.get("away_team"))
            by_id = _roster_lookup(r)
            d = r.get("date")
            key = _date_key(d)
            note = ""
            if r.get("shootout"):
                note = "Shootout"
            elif r.get("overtime"):
                note = "Overtime"
            self._data = {
                "date_label": key.strftime("%a %b %d, %Y") if key else str(d or ""),
                "note": note,
                "home": {"name": home_name, "abbr": _abbr(home_name),
                         "score": int(r.get("home_score", 0) or 0)},
                "away": {"name": away_name, "abbr": _abbr(away_name),
                         "score": int(r.get("away_score", 0) or 0)},
                "scoring": _scoring_summary(r, by_id, home_name, away_name),
                "players": _box_player_stats(r, by_id, home_name, away_name),
                "team_stats": _box_team_stats(r, by_id, home_name, away_name),
                "three_stars": _box_three_stars(r, by_id),
                "lines": {home_name: _box_lines(r, by_id, home_name),
                          away_name: _box_lines(r, by_id, away_name)},
            }
            self._players_team = away_name
            self._lines_team = away_name
            self._error.hide()
            self._render_all()
        except Exception as e:
            print(f"[boxscore] set_game failed: {e}")
            self._data = None
            self._show_error(f"Could not load the box score: {e}")

    def _show_error(self, msg):
        self._error.setText(msg)
        self._error.show()
        self._header.setText("BOX SCORE")
        self._meta.setText("")
        self._stars.setText("")
        for pane in (self._scoring_pane, self._players_pane,
                     self._lines_pane, self._teams_pane):
            self._clear_pane(pane)

    # -- render --------------------------------------------------------

    def _render_all(self):
        data = self._data
        if not data:
            return
        a, h = data["away"], data["home"]
        self._header.setText(
            f"{a['abbr']}  {a['score']}  @  {h['score']}  {h['abbr']}")
        self._meta.setText(
            f"{a['name']} @ {h['name']} · {data['date_label']}"
            + (f" · {data['note']}" if data["note"] else ""))
        stars = data["three_stars"]
        if stars:
            medals = ["1st", "2nd", "3rd"]
            bits = []
            for i, s in enumerate(stars):
                bits.append(
                    f"★ {medals[i] if i < 3 else ''} {s['name']}"
                    f"{(' (' + s['team'] + ')') if s.get('team') else ''}"
                    f"{(' — ' + s['detail']) if s.get('detail') else ''}")
            self._stars.setText("   ".join(bits))
        else:
            self._stars.setText("")
        self._render_scoring()
        self._render_players()
        self._render_lines()
        self._render_teams()

    def _on_tab_changed(self, idx):
        # Tabs render lazily on first view (same as web: renderPlayers /
        # renderLines / renderTeams run when their tab opens).
        try:
            name = self._tabs.tabText(idx)
            if name == "Player Stats":
                self._render_players()
            elif name == "Lines":
                self._render_lines()
            elif name == "Team Stats":
                self._render_teams()
        except Exception:
            pass

    def _render_scoring(self):
        pane = self._scoring_pane
        self._clear_pane(pane)
        layout = pane._layout
        data = self._data
        if not data:
            return
        goals = data["scoring"]
        if not goals:
            layout.addWidget(self._empty(
                "Detailed scoring data is unavailable for this game."))
            return
        a, h = data["away"], data["home"]
        last_period = None
        for g in goals:
            if g["period_label"] != last_period:
                last_period = g["period_label"]
                ph = QLabel(last_period)
                ph.setObjectName("section-header")
                layout.addWidget(ph)
            card = QFrame()
            card.setObjectName("tile")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(14, 8, 14, 8)
            scorer = g["scorer"]
            if g["assists"]:
                scorer += "  (" + ", ".join(g["assists"]) + ")"
            else:
                scorer += "  (unassisted)"
            left = QLabel(scorer)
            left.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
            sub_bits = [g["time_str"]]
            if g["strength"] and g["strength"] != "EV":
                sub_bits.append(g["strength"])
            if g["goal_type"]:
                sub_bits.append(g["goal_type"])
            sub = QLabel(" · ".join(b for b in sub_bits if b))
            sub.setStyleSheet("color: #8b95ab; font-size: 12px;")
            vbox = QVBoxLayout()
            vbox.addWidget(left)
            vbox.addWidget(sub)
            cl.addLayout(vbox)
            cl.addStretch()
            strength = g["strength"]
            if strength and strength != "EV":
                badge = QLabel(strength)
                color = "#3b82f6" if strength == "PP" else "#e8b923"
                badge.setStyleSheet(
                    f"background: {color}; color: #fff; font-weight: 700; "
                    f"font-size: 12px; padding: 2px 8px; border-radius: 4px;")
                cl.addWidget(badge)
            running = QLabel(
                f"{a['abbr']} {g['away_running']} – {g['home_running']} {h['abbr']}")
            running.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
            cl.addWidget(running)
            layout.addWidget(card)
        layout.addStretch()

    def _build_team_toggle(self, toggle_layout, names, current, on_pick):
        while toggle_layout.count():
            item = toggle_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        btns = []
        for n in names:
            b = QPushButton(n)
            b.setCheckable(True)
            b.setChecked(n == current)
            b.setCursor(Qt.PointingHandCursor)
            if n == current:
                b.setObjectName("primary-btn")
            b.clicked.connect(lambda checked=False, name=n: on_pick(name))
            toggle_layout.addWidget(b)
            btns.append(b)
        toggle_layout.addStretch()
        return btns

    def _render_players(self):
        pane = self._players_pane
        self._clear_pane(pane)
        layout = pane._layout
        data = self._data
        if not data:
            return
        teams = data["players"]
        names = list(teams.keys())
        if not names:
            layout.addWidget(self._empty(
                "Per-player stats are unavailable for this game."))
            return
        if self._players_team not in teams:
            self._players_team = names[0]
        toggle_wrap = QWidget()
        toggle_wrap.setLayout(QHBoxLayout())
        toggle_wrap.layout().setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toggle_wrap)
        self._build_team_toggle(
            toggle_wrap.layout(), names, self._players_team,
            lambda n: (setattr(self, "_players_team", n),
                       self._render_players()))
        t = teams[self._players_team]
        if not t["has_stats"]:
            layout.addWidget(self._empty(
                "Per-player stats are unavailable for this game."))
            return
        sh = QLabel("Skaters")
        sh.setObjectName("section-header")
        layout.addWidget(sh)
        sk = QTableWidget(len(t["skaters"]), 9)
        sk.setHorizontalHeaderLabels(
            ["Player", "Pos", "G", "A", "P", "SOG", "Hits", "Blk", "FO"])
        sk.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        sk.verticalHeader().setVisible(False)
        sk.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, s in enumerate(t["skaters"]):
            for j, val in enumerate(
                    [s["name"], s["pos"], s["g"], s["a"], s["p"],
                     s["sog"], s["hits"], s["blk"], s["fo"]]):
                sk.setItem(i, j, QTableWidgetItem(str(val)))
        layout.addWidget(sk)
        if t["goalies"]:
            gh = QLabel("Goaltenders")
            gh.setObjectName("section-header")
            layout.addWidget(gh)
            gl = QTableWidget(len(t["goalies"]), 5)
            gl.setHorizontalHeaderLabels(
                ["Goaltender", "SA", "Saves", "SV%", "GA"])
            gl.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.Stretch)
            gl.verticalHeader().setVisible(False)
            gl.setEditTriggers(QTableWidget.NoEditTriggers)
            for i, gg in enumerate(t["goalies"]):
                svp = "–" if gg["svp"] is None else f"{gg['svp']:.1f}%"
                for j, val in enumerate(
                        [gg["name"], gg["sa"], gg["saves"], svp, gg["ga"]]):
                    gl.setItem(i, j, QTableWidgetItem(str(val)))
            layout.addWidget(gl)
        layout.addStretch()

    def _render_lines(self):
        pane = self._lines_pane
        self._clear_pane(pane)
        layout = pane._layout
        data = self._data
        if not data:
            return
        lines = data["lines"]
        names = list(lines.keys())
        if not names:
            layout.addWidget(self._empty(
                "Line combinations are unavailable for this game."))
            return
        if self._lines_team not in lines:
            self._lines_team = names[0]
        toggle_wrap = QWidget()
        toggle_wrap.setLayout(QHBoxLayout())
        toggle_wrap.layout().setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toggle_wrap)
        self._build_team_toggle(
            toggle_wrap.layout(), names, self._lines_team,
            lambda n: (setattr(self, "_lines_team", n), self._render_lines()))
        legend = QLabel("5.0 = average game · 7.0+ = great")
        legend.setStyleSheet("color: #8b95ab; font-size: 12px;")
        layout.addWidget(legend)
        units = lines[self._lines_team] or []
        if not units or not any((u.get("players") or []) for u in units):
            layout.addWidget(self._empty(
                "Line combinations are unavailable for this game."))
            return
        for u in units:
            head = QHBoxLayout()
            lbl = QLabel(u["label"])
            lbl.setStyleSheet(
                "color: #ffffff; font-size: 14px; font-weight: 700;")
            head.addWidget(lbl)
            head.addStretch()
            r = u.get("rating")
            rlbl = QLabel(f"Rating {'–' if r is None else f'{r:.1f}'}")
            color = "#34d399" if r is not None and r >= 7.0 else \
                ("#e8b923" if r is not None and r >= 5.5 else "#e5484d")
            rlbl.setStyleSheet(
                f"color: {color}; font-size: 13px; font-weight: 700;")
            head.addWidget(rlbl)
            layout.addLayout(head)
            players = u.get("players") or []
            tbl = QTableWidget(len(players), 7)
            tbl.setHorizontalHeaderLabels(
                ["Player", "Pos", "G", "A", "P", "Grade", "Key Stats"])
            tbl.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for i, p in enumerate(players):
                vals = [p["name"], p["pos"], p["g"], p["a"], p["p"],
                        "–" if p["grade"] is None else f"{p['grade']:.1f}",
                        p["why"]]
                for j, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    if j == 5 and p["grade"] is not None:
                        col = "#34d399" if p["grade"] >= 7.0 else \
                            ("#e8b923" if p["grade"] >= 5.5 else "#e5484d")
                        item.setForeground(QColor(col))
                    tbl.setItem(i, j, item)
            layout.addWidget(tbl)
        layout.addStretch()

    def _render_teams(self):
        pane = self._teams_pane
        self._clear_pane(pane)
        layout = pane._layout
        data = self._data
        if not data:
            return
        a, h = data["away"], data["home"]
        tbl = QTableWidget(len(data["team_stats"]), 3)
        tbl.setHorizontalHeaderLabels(["", a["abbr"], h["abbr"]])
        tbl.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, row in enumerate(data["team_stats"]):
            tbl.setItem(i, 0, QTableWidgetItem(str(row["label"])))
            tbl.setItem(i, 1, QTableWidgetItem(str(row["away"])))
            tbl.setItem(i, 2, QTableWidgetItem(str(row["home"])))
        layout.addWidget(tbl)
        layout.addStretch()
