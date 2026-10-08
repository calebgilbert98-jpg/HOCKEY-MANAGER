"""Team Analytics: native Qt port.

Team-focused season analytics -- DISTINCT from the player-focused
Analytics Hub (native_ui/screens/analytics.py: shot maps, momentum
graphs, zone-entry maps, per-player xG, Ask the Analyst). This screen
works from season aggregates only:

  Overview tab   -- port of mainline windows.TeamAnalyticsView cards:
                    Offense, Defense, Special Teams, Goaltenders,
                    Scoring Mix, Discipline, Top Scorers
  League tab     -- team rank vs every league club on GF/GP, GA/GP,
                    shots, shooting %, PP%, PK%, SV% + league averages
  Division tab   -- user's division: GP, W-L-OTL, PTS, GF/GA per rival
  Lines tab      -- current 4 forward lines + 3 D pairs with combined
                    season production from member player.stats
  Trends tab     -- last 10 played games (record, GF/GA) + season pace

Data sources (all real, read directly off the game object):
  - game / game.game_manager -> gm.user_team (Team)
  - player.stats (PlayerStats: goals, assists, shots, PIM, goalie stats)
  - team.power_play_goals/_opportunities,
    team.penalty_kill_opportunities/_goals_against (with
    game_manager.team_stats[team_name] dict fallback, same as
    dashboard_home._special_teams_pct)
  - league.teams (Team: team_name, division, conference, goals_for,
    goals_against, wins, losses, ot_losses) for comparisons
  - team.lineup dict (Forwards: 4x3, Defense: 3x2) for line combos
  - league.schedule entries (home_team/away_team/home_score/
    away_score dicts) for last-10 trends

Every data read is _safe-wrapped: a fresh (0-game) season shows
placeholders, never tracebacks.
"""

from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtGui import QColor

from .base import BaseScreen


# ---------------------------------------------------------------------------
# safe data access
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return _safe(lambda: getattr(gm, "user_team", None)) or \
        _safe(lambda: getattr(game, "user_team", None))


def _league(game):
    gm = _resolve_gm(game)
    return _safe(lambda: getattr(gm, "league", None)) or \
        _safe(lambda: getattr(game, "league", None))


def _league_teams(game):
    league = _league(game)
    return _safe(lambda: list(league.teams), []) or []


def _is_goalie(p):
    try:
        return p.primary_position.value == "G"
    except Exception:
        return False


def _pos_value(p):
    return _safe(lambda: p.primary_position.value, "") or ""


def _team_special_teams(team, gm):
    """(ppg, ppo, pp_pct, pk_kills, pk_opp, pk_pct) or None-ish.

    Reads team attrs first, falls back to game_manager.team_stats dict
    (same pattern as mainline dashboard_home._special_teams_pct).
    Percentages are None when there were no opportunities.
    """
    name = _safe(lambda: team.team_name, "") or ""
    ts = _safe(lambda: dict(getattr(gm, "team_stats", {}) or {}).get(name, {})) or {}

    ppg = _safe(lambda: int(getattr(team, "power_play_goals", 0) or 0), 0)
    ppo = _safe(lambda: int(getattr(team, "power_play_opportunities", 0) or 0), 0)
    if not ppo and ts:
        ppg = int(ts.get("power_play_goals", 0) or 0)
        ppo = int(ts.get("power_play_opportunities", 0) or 0)

    pkga = _safe(lambda: int(getattr(team, "penalty_kill_goals_against", 0) or 0), 0)
    pko = _safe(lambda: int(getattr(team, "penalty_kill_opportunities", 0) or 0), 0)
    if not pko and ts:
        pkga = int(ts.get("penalty_kill_goals_against", 0) or 0)
        pko = int(ts.get("penalty_kill_opportunities", 0) or 0)

    pp_pct = (ppg / ppo * 100.0) if ppo else None
    pk_pct = ((pko - pkga) / pko * 100.0) if pko else None
    return {"ppg": ppg, "ppo": ppo, "pp_pct": pp_pct,
            "pk_kills": pko - pkga, "pk_opp": pko, "pk_pct": pk_pct}


def _team_goalie_totals(team):
    """(games, sv_pct, gaa) from roster goalies' player.stats.

    Port of the mainline TeamAnalyticsView aggregation:
    GA = shots_against - saves.
    """
    goalies = [p for p in (_safe(lambda: list(team.roster), []) or [])
               if _is_goalie(p)]
    sa = sum(_safe(lambda: int(p.stats.shots_against or 0), 0) for p in goalies)
    sv = sum(_safe(lambda: int(p.stats.saves or 0), 0) for p in goalies)
    ga = sa - sv
    gp = max(1, max([_safe(lambda: int(p.stats.games_played or 0), 0)
                     for p in goalies] or [0]))
    sv_pct = (sv / sa * 100.0) if sa else None
    gaa = ga / gp
    return {"sa": sa, "sv": sv, "ga": ga, "gp": gp,
            "sv_pct": sv_pct, "gaa": gaa, "goalies": goalies}


def _skater_totals(team):
    """Aggregate skater stats (mainline TeamAnalyticsView formulas)."""
    roster = _safe(lambda: list(team.roster), []) or []
    skaters = [p for p in roster if not _is_goalie(p)]
    tgp_raw = max([_safe(lambda: int(p.stats.games_played or 0), 0)
                   for p in roster] or [0])
    tgp = max(1, tgp_raw)
    gf = sum(_safe(lambda: int(p.stats.goals or 0), 0) for p in skaters)
    shots = sum(_safe(lambda: int(p.stats.shots or 0), 0) for p in skaters)
    pim = sum(_safe(lambda: int(p.stats.penalties_in_minutes or 0), 0)
              for p in roster)
    return {"skaters": skaters, "tgp": tgp, "tgp_raw": tgp_raw, "gf": gf,
            "shots": shots, "pim": pim}


def _entry_team_name(val):
    """Schedule entries may store a name string or a Team object."""
    if val is None:
        return ""
    name = _safe(lambda: val.team_name, None)
    if name:
        return str(name).strip()
    return str(val).strip()


def _played_games_for(game, team_name, limit=10):
    """Last `limit` played games involving team_name, oldest first.

    Reads league.schedule dict entries (home_team/away_team/
    home_score/away_score). Returns list of
    (opponent, gf, ga, result, ot) where result in W/L/OTL.
    """
    league = _league(game)
    sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
    mine = _safe(lambda: str(team_name).strip().lower(), "") or ""
    out = []
    for item in sched:
        try:
            if not isinstance(item, dict):
                continue
            if item.get("league", "NHL") != "NHL" or item.get("playoff"):
                continue
            hs = item.get("home_score")
            aws = item.get("away_score")
            if hs is None or aws is None:
                continue
            home = _entry_team_name(item.get("home_team"))
            away = _entry_team_name(item.get("away_team"))
            if home.lower() == mine:
                opp, gf, ga = away, int(hs), int(aws)
            elif away.lower() == mine:
                opp, gf, ga = home, int(aws), int(hs)
            else:
                continue
            ot = bool(item.get("overtime") or item.get("shootout"))
            if gf > ga:
                res = "W"
            elif ot:
                res = "OTL"
            else:
                res = "L"
            out.append({"opp": opp or "?", "gf": gf, "ga": ga,
                        "result": res, "ot": ot})
        except Exception:
            continue
    return out[-limit:]


def _resolve_line_player(entry, by_id):
    """Lineup slots may hold player objects or ids (save-safe snapshots)."""
    if entry is None:
        return None
    pid = _safe(lambda: getattr(entry, "id", None), None)
    if pid is not None:
        return entry
    key = entry if isinstance(entry, (str, int)) else None
    return by_id.get(key) if key is not None else None


def _normalize_lines(lineup, by_id):
    """-> (forward_lines, d_pairs): 4x[player] and 3x[player].

    Handles every lineup shape the game produces:
      * {"Forwards": [[...] x4], "Defense": [[...] x3]}
        (game_classes.snapshot_team_lines; entries may be ids)
      * native slot map {LW1: p, C1: p, RW1: p, D1: p, ...}
        (native_ui LinesScreen save format)
      * sim slot map {F1_LW: p, D1_L: p, ...}
    PP/PK unit keys are ignored -- even-strength lines only.
    """
    import re
    fwd = [[] for _ in range(4)]
    dpr = [[] for _ in range(3)]

    def put(lst, idx, entry):
        if 0 <= idx < len(lst):
            p = _resolve_line_player(entry, by_id)
            if p is not None and p not in lst[idx]:
                lst[idx].append(p)

    if not isinstance(lineup, dict):
        return fwd, dpr

    fw = lineup.get("Forwards")
    dp = lineup.get("Defense")
    if isinstance(fw, (list, tuple)) or isinstance(dp, (list, tuple)):
        if isinstance(fw, (list, tuple)):
            for i, entries in enumerate(fw[:4]):
                for e in entries or []:
                    put(fwd, i, e)
        if isinstance(dp, (list, tuple)):
            for i, entries in enumerate(dp[:3]):
                for e in entries or []:
                    put(dpr, i, e)
        return fwd, dpr

    # slot map: native (LW1/C1/RW1/D1..D6) or sim (F1_LW/D1_L/...) keys
    for key, entry in lineup.items():
        k = str(key or "")
        if k.startswith(("PP", "PK")):
            continue
        m = re.match(r"^(LW|C|RW)(\d+)$", k)
        if m:
            put(fwd, int(m.group(2)) - 1, entry)
            continue
        m = re.match(r"^D(\d+)$", k)
        if m:
            put(dpr, (int(m.group(1)) - 1) // 2, entry)
            continue
        m = re.match(r"^F(\d+)_(LW|C|RW)$", k)
        if m:
            put(fwd, int(m.group(1)) - 1, entry)
            continue
        m = re.match(r"^D(\d+)_(L|R)$", k)
        if m:
            # D1_L -> D1, D1_R -> D2, ... (mirrors LinesScreen mapping)
            native = (int(m.group(1)) - 1) * 2 + (1 if m.group(2) == "L" else 2)
            put(dpr, (native - 1) // 2, entry)
    return fwd, dpr


# ---------------------------------------------------------------------------
# card / table builders
# ---------------------------------------------------------------------------

def _tile(parent_layout, title, row=None, col=None, rowspan=1, colspan=1):
    """One dark card; returns its inner QVBoxLayout.

    Works with QGridLayout (pass row/col) and QVBoxLayout/QHBoxLayout
    (omit them -- falls back to a plain addWidget).
    """
    frame = QFrame()
    frame.setObjectName("tile")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(2)
    head = QLabel(title.upper())
    head.setObjectName("tile-title")
    lay.addWidget(head)
    if row is not None and col is not None:
        try:
            parent_layout.addWidget(frame, row, col, rowspan, colspan)
        except TypeError:
            parent_layout.addWidget(frame)
    else:
        parent_layout.addWidget(frame)
    return lay


def _big(lay, text):
    w = QLabel(text)
    w.setObjectName("tile-value")
    lay.addWidget(w)
    return w


def _sub(lay, text):
    w = QLabel(text)
    w.setObjectName("tile-sub")
    w.setWordWrap(True)
    lay.addWidget(w)
    return w


def _line(lay, text, dim=False):
    w = QLabel(text)
    w.setStyleSheet("color: #6b7488; font-size: 12px;" if dim
                    else "color: #e8edf5; font-size: 12px;")
    w.setWordWrap(True)
    lay.addWidget(w)
    return w


def _make_table(cols, headers):
    t = QTableWidget(0, cols)
    t.setHorizontalHeaderLabels(headers)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _cell(text, bold=False, color=None):
    item = QTableWidgetItem(str(text))
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    if color:
        item.setForeground(QColor(color))
    return item


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

class TeamAnalyticsScreen(BaseScreen):
    """Team-level season analytics (distinct from the player Analytics Hub)."""

    title = "Team Analytics"

    def _build_body(self):
        top = QHBoxLayout()
        self._team_lbl = QLabel("")
        self._team_lbl.setObjectName("section-header")
        top.addWidget(self._team_lbl)
        top.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primary-btn")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        self._layout.addLayout(top)

        self.tabs = QTabWidget()
        self._tab_widgets = {}
        for key, label in (("overview", "Overview"),
                           ("league", "League Comparison"),
                           ("division", "Division"),
                           ("lines", "Line Combos"),
                           ("trends", "Trends")):
            page = QWidget()
            page.setLayout(QVBoxLayout())
            page.layout().setContentsMargins(4, 8, 4, 4)
            self.tabs.addTab(page, label)
            self._tab_widgets[key] = page
        self._layout.addWidget(self.tabs, 1)

    # -- refresh --------------------------------------------------------
    def refresh(self):
        game = self.game
        team = _user_team(game)
        if team is None:
            self._team_lbl.setText("NO TEAM LOADED")
            for key, page in self._tab_widgets.items():
                self._clear(page)
                _sub(page.layout(), "No user team is loaded yet.")
            return
        name = _safe(lambda: team.team_name, "?") or "?"
        self._team_lbl.setText(str(name).upper())
        gm = _resolve_gm(game)
        self._fill_overview(team, gm)
        self._fill_league(team, gm, game)
        self._fill_division(team, gm, game)
        self._fill_lines(team)
        self._fill_trends(team, game)

    @staticmethod
    def _clear(page):
        lay = page.layout()
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    # -- overview: mainline TeamAnalyticsView cards ---------------------
    def _fill_overview(self, team, gm):
        page = self._tab_widgets["overview"]
        self._clear(page)
        grid = QGridLayout()
        grid.setSpacing(10)
        page.layout().addLayout(grid)
        page.layout().addStretch()

        sk = _skater_totals(team)
        gt = _team_goalie_totals(team)
        st = _team_special_teams(team, gm)
        tgp = sk["tgp"]
        gf, shots, pim = sk["gf"], sk["shots"], sk["pim"]

        # Offense (mainline formula)
        lay = _tile(grid, "Offense", 0, 0)
        _big(lay, f"{gf / tgp:.2f}")
        _line(lay, "goals per game", dim=True)
        _line(lay, f"{gf} goals in {sk['tgp_raw']} team games", dim=True)
        if shots:
            _line(lay, f"{shots / tgp:.1f} shots/game — "
                       f"{gf / shots * 100:.1f}% shooting")

        # Defense (mainline formula)
        lay = _tile(grid, "Defense", 0, 1)
        _big(lay, f"{gt['ga'] / tgp:.2f}")
        _line(lay, "goals against per game", dim=True)
        _line(lay, f"{gt['ga']} allowed in {sk['tgp_raw']} team games", dim=True)
        if gt["sa"]:
            _line(lay, f"{gt['sa'] / tgp:.1f} shots against/game — "
                       f"{gt['sv'] / gt['sa'] * 100:.1f}% team save%")

        # Special teams
        lay = _tile(grid, "Special Teams", 0, 2)
        if st["pp_pct"] is None:
            _big(lay, "—")
            _line(lay, "no power plays yet", dim=True)
        else:
            _big(lay, f"{st['pp_pct']:.1f}%")
            _line(lay, "power play", dim=True)
            _line(lay, f"{st['ppg']} goals on {st['ppo']} chances", dim=True)
        if st["pk_pct"] is None:
            _line(lay, "PK: — (no kills yet)", dim=True)
        else:
            _line(lay, f"PK: {st['pk_pct']:.1f}% "
                       f"({st['pk_kills']}/{st['pk_opp']} kills)")

        # Goaltenders (mainline formula)
        lay = _tile(grid, "Goaltenders", 1, 0)
        goalies = sorted(gt["goalies"],
                         key=lambda p: _safe(lambda: int(p.stats.games_played or 0), 0),
                         reverse=True)
        if goalies:
            for g in goalies[:4]:
                gp = _safe(lambda: int(g.stats.games_played or 0), 0)
                gsa = _safe(lambda: int(g.stats.shots_against or 0), 0)
                gsv = _safe(lambda: int(g.stats.saves or 0), 0)
                gga = gsa - gsv
                svp = f"{gsv / gsa * 100:.1f}%" if gsa else "—"
                gag = f"{gga / gp:.2f}" if gp else "—"
                fname = _safe(lambda: g.full_name, "?") or "?"
                _line(lay, f"{fname}: {gp} GP, {svp} SV%, {gag} GA/G")
        else:
            _line(lay, "No goaltenders on roster", dim=True)

        # Scoring mix (mainline formula)
        lay = _tile(grid, "Scoring Mix", 1, 1)
        pos_goals = {}
        for p in sk["skaters"]:
            pos = _pos_value(p)
            pos_goals[pos] = pos_goals.get(pos, 0) + \
                _safe(lambda: int(p.stats.goals or 0), 0)
        total = max(1, sum(pos_goals.values()))
        for pos in ("C", "LW", "RW", "LD", "RD"):
            gls = pos_goals.get(pos, 0)
            bar = "■" * max(1, int(gls / total * 20)) if gls else "—"
            _line(lay, f"{pos:3s} {gls:3d} goals  {bar}")

        # Discipline (mainline formula)
        lay = _tile(grid, "Discipline", 1, 2)
        _big(lay, f"{pim / tgp:.1f}")
        _line(lay, "PIM per game", dim=True)
        roster = _safe(lambda: list(team.roster), []) or []
        offenders = sorted(
            roster,
            key=lambda p: _safe(lambda: int(p.stats.penalties_in_minutes or 0), 0),
            reverse=True)[:3]
        for p in offenders:
            pm = _safe(lambda: int(p.stats.penalties_in_minutes or 0), 0)
            if pm:
                fname = _safe(lambda: p.full_name, "?") or "?"
                _line(lay, f"{fname}: {pm} PIM")

        # Top scorers (mainline formula)
        lay = _tile(grid, "Top Scorers", 2, 0, 1, 3)
        skaters = sorted(
            sk["skaters"],
            key=lambda p: _safe(lambda: int(p.stats.points or 0), 0),
            reverse=True)
        shown = 0
        for p in skaters[:5]:
            pts = _safe(lambda: int(p.stats.points or 0), 0)
            if not pts:
                continue
            gp = max(1, _safe(lambda: int(p.stats.games_played or 0), 0))
            g = _safe(lambda: int(p.stats.goals or 0), 0)
            a = _safe(lambda: int(p.stats.assists or 0), 0)
            fname = _safe(lambda: p.full_name, "?") or "?"
            _line(lay, f"{fname}: {g}G {a}A ({pts / gp:.2f} P/GP)")
            shown += 1
        if not shown:
            _line(lay, "No points recorded yet", dim=True)

    # -- league comparison ----------------------------------------------
    def _fill_league(self, team, gm, game):
        page = self._tab_widgets["league"]
        self._clear(page)
        teams = _league_teams(game)
        my_name = _safe(lambda: team.team_name, "") or ""
        rows = []
        for t in teams:
            try:
                tname = _safe(lambda: t.team_name, "") or ""
                gp = max(0, _safe(lambda: int(getattr(t, "games_played", 0) or 0), 0))
                if not gp:
                    continue
                gf = _safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0)
                ga = _safe(lambda: int(getattr(t, "goals_against", 0) or 0), 0)
                st = _team_special_teams(t, gm)
                gt = _team_goalie_totals(t)
                sk = _skater_totals(t)
                rows.append({
                    "name": tname,
                    "gf_gp": gf / gp,
                    "ga_gp": ga / gp,
                    "pp": st["pp_pct"],
                    "pk": st["pk_pct"],
                    "sv": gt["sv_pct"],
                    "sh_pct": (gf / sk["shots"] * 100.0) if sk["shots"] else None,
                    "mine": tname == my_name,
                })
            except Exception:
                continue

        metrics = [
            ("gf_gp", "Goals For / Game", True),
            ("ga_gp", "Goals Against / Game", False),
            ("sh_pct", "Shooting %", True),
            ("sv", "Team Save %", True),
            ("pp", "Power Play %", True),
            ("pk", "Penalty Kill %", True),
        ]
        if not rows:
            _line(page.layout(), "No league games played yet — "
                                 "comparison unlocks once the season starts.", dim=True)
            page.layout().addStretch()
            return

        def avg(key):
            vals = [r[key] for r in rows if r[key] is not None]
            return sum(vals) / len(vals) if vals else None

        def rank(key, higher_better):
            me = next((r for r in rows if r["mine"]), None)
            if me is None or me[key] is None:
                return "—"
            contenders = [r for r in rows if r[key] is not None]
            better = sum(1 for r in contenders
                         if r is not me
                         and ((r[key] > me[key]) if higher_better
                              else (r[key] < me[key])))
            return f"{better + 1} of {len(contenders)}"

        mine = next((r for r in rows if r["mine"]), None)
        table = _make_table(4, ["Metric", "You", "League Avg", "Rank"])
        table.setRowCount(len(metrics))
        for i, (key, label, higher) in enumerate(metrics):
            mv = mine[key] if mine else None
            av = avg(key)
            table.setItem(i, 0, _cell(label, bold=True))
            table.setItem(i, 1, _cell(f"{mv:.2f}" if mv is not None else "—",
                                      bold=True, color="#3B82F6"))
            table.setItem(i, 2, _cell(f"{av:.2f}" if av is not None else "—"))
            table.setItem(i, 3, _cell(rank(key, higher)))
        table.resizeColumnsToContents()
        page.layout().addWidget(QLabel("Your team vs the league "
                                       "(higher rank = better):"))
        page.layout().addWidget(table)
        page.layout().addStretch()

    # -- division --------------------------------------------------------
    def _fill_division(self, team, gm, game):
        page = self._tab_widgets["division"]
        self._clear(page)
        teams = _league_teams(game)
        my_div = _safe(lambda: team.division, "") or ""
        my_name = _safe(lambda: team.team_name, "") or ""
        rivals = [t for t in teams
                  if (_safe(lambda: t.division, "") or "") == my_div] if my_div else []

        if not rivals:
            _line(page.layout(), "Division data unavailable.", dim=True)
            page.layout().addStretch()
            return

        def points(t):
            w = _safe(lambda: int(getattr(t, "wins", 0) or 0), 0)
            otl = _safe(lambda: int(getattr(t, "ot_losses", 0) or 0), 0)
            return 2 * w + otl

        rivals.sort(key=points, reverse=True)
        table = _make_table(8, ["Team", "GP", "W", "L", "OTL",
                                "PTS", "GF", "GA"])
        table.setRowCount(len(rivals))
        for i, t in enumerate(rivals):
            tname = _safe(lambda: t.team_name, "?") or "?"
            w = _safe(lambda: int(getattr(t, "wins", 0) or 0), 0)
            l = _safe(lambda: int(getattr(t, "losses", 0) or 0), 0)
            otl = _safe(lambda: int(getattr(t, "ot_losses", 0) or 0), 0)
            gf = _safe(lambda: int(getattr(t, "goals_for", 0) or 0), 0)
            ga = _safe(lambda: int(getattr(t, "goals_against", 0) or 0), 0)
            is_me = tname == my_name
            vals = [tname, w + l + otl, w, l, otl, points(t), gf, ga]
            for j, v in enumerate(vals):
                table.setItem(i, j, _cell(v, bold=is_me,
                                          color="#3B82F6" if is_me else None))
        table.resizeColumnsToContents()
        page.layout().addWidget(QLabel(f"{my_div} Division standings:"))
        page.layout().addWidget(table)
        page.layout().addStretch()

    # -- line combos -----------------------------------------------------
    def _fill_lines(self, team):
        page = self._tab_widgets["lines"]
        self._clear(page)
        lineup = _safe(lambda: getattr(team, "lineup", None), None)
        roster = _safe(lambda: list(team.roster), []) or []
        ahl = _safe(lambda: list(team.ahl_roster), []) or []
        by_id = {}
        for p in roster + ahl:
            pid = _safe(lambda: getattr(p, "id", None), None)
            if pid is not None:
                by_id[pid] = p

        def line_card(lay, label, pls):
            g = sum(_safe(lambda: int(p.stats.goals or 0), 0) for p in pls)
            a = sum(_safe(lambda: int(p.stats.assists or 0), 0) for p in pls)
            _big(lay, f"{g}G · {a}A · {g + a}P")
            _line(lay, label, dim=True)
            for p in pls:
                fname = _safe(lambda: p.full_name, "?") or "?"
                pos = _pos_value(p)
                pg = _safe(lambda: int(p.stats.goals or 0), 0)
                pa = _safe(lambda: int(p.stats.assists or 0), 0)
                _line(lay, f"{fname} ({pos}) — {pg}G {pa}A")

        grid = QGridLayout()
        grid.setSpacing(10)
        page.layout().addLayout(grid)
        page.layout().addStretch()

        fwd_lines, d_pairs = _normalize_lines(lineup, by_id)

        any_lines = any(fwd_lines) or any(d_pairs)
        if not any_lines:
            _line(page.layout(),
                  "Line combinations are not set — assign them on the "
                  "Lines screen to see per-line production.", dim=True)
            return

        for i, pls in enumerate(fwd_lines[:4]):
            if not pls:
                continue
            lay = _tile(grid, f"Line {i + 1}", 0, i)
            line_card(lay, "forwards", pls)
        for i, pls in enumerate(d_pairs[:3]):
            if not pls:
                continue
            lay = _tile(grid, f"Pair {i + 1}", 1, i)
            line_card(lay, "defense", pls)

    # -- trends ----------------------------------------------------------
    def _fill_trends(self, team, game):
        page = self._tab_widgets["trends"]
        self._clear(page)
        name = _safe(lambda: team.team_name, "") or ""
        games = _played_games_for(game, name, 10)

        if not games:
            _line(page.layout(), "No games played yet this season — "
                                 "trends appear after the first game.", dim=True)
            page.layout().addStretch()
            return

        w = sum(1 for g in games if g["result"] == "W")
        l = sum(1 for g in games if g["result"] == "L")
        otl = sum(1 for g in games if g["result"] == "OTL")
        gf = sum(g["gf"] for g in games)
        ga = sum(g["ga"] for g in games)

        n = len(games)
        lay = _tile(page.layout(), "Last 10 Games")
        _big(lay, f"{w}-{l}-{otl}")
        _line(lay, f"W-L-OTL over the last {n}", dim=True)
        _line(lay, f"{gf} goals for, {ga} against "
                   f"({gf / n:.2f} / {ga / n:.2f} per game)")

        table = _make_table(4, ["Opponent", "Score", "Result", "Diff"])
        table.setRowCount(n)
        for i, g in enumerate(games):
            res, color = g["result"], {"W": "#22c55e", "L": "#ef4444",
                                       "OTL": "#f59e0b"}[g["result"]]
            table.setItem(i, 0, _cell(g["opp"]))
            table.setItem(i, 1, _cell(f"{g['gf']}–{g['ga']}"))
            table.setItem(i, 2, _cell(res, bold=True, color=color))
            table.setItem(i, 3, _cell(f"{g['gf'] - g['ga']:+d}"))
        table.resizeColumnsToContents()
        page.layout().addWidget(table)

        # season pace
        gw = _safe(lambda: int(getattr(team, "wins", 0) or 0), 0)
        gl = _safe(lambda: int(getattr(team, "losses", 0) or 0), 0)
        gotl = _safe(lambda: int(getattr(team, "ot_losses", 0) or 0), 0)
        gp = gw + gl + gotl
        if gp:
            pts = 2 * gw + gotl
            pace = pts / gp * 82
            pl = _tile(page.layout(), "Season Pace")
            _big(pl, f"{pace:.0f} pts")
            _line(pl, f"{pts} points in {gp} games — 82-game pace", dim=True)
        page.layout().addStretch()
