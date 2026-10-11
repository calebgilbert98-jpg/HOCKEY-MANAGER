"""Team overview: quick at-a-glance page for any league team (read-only).

Port of web_ui/screens/team.py. Header: team name, record,
division/conference rank, streak. Sections: team leaders
(points/goals/assists), recent form, cap space, roster list.

This was the web UI's "TEAM NOT FOUND" page -- the bug was a lookup
issue in the HTTP layer. The native port looks up the team object
directly from the game, with tolerant name matching and a user-team
fallback, so a 404 can never happen.
"""
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QScrollArea, QFrame, QAbstractItemView, QHeaderView,
)
from PySide6.QtCore import Qt

from .base import BaseScreen
from ..widgets.player_table import PlayerTable
from native_ui.safe import safe_call


def _gm(game):
    return safe_call(lambda: getattr(game, "game_manager", None), context="team/resolve_gm") or game


def _league(game):
    return safe_call(lambda: _gm(game).league, context="team/resolve_league")


def _user_team(game):
    return (safe_call(lambda: _gm(game).user_team, context="team/resolve_user_team")
            or safe_call(lambda: getattr(game, "user_team", None), context="team/resolve_user_team"))


def _norm_team_key(s):
    """Normalize a team name/abbr for tolerant matching."""
    s = str(s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def _team_abbrs(t):
    out = []
    for attr in ("abbr", "abbreviation", "team_abbr", "short_name"):
        v = safe_call(lambda: getattr(t, attr, ""), "", context="team/abbr_attr") or ""
        if v and str(v).strip():
            out.append(str(v).strip())
    return out


def find_team(game, name):
    """Find a Team object by name with tolerant matching.

    Match order (first hit wins): exact team_name, normalized team_name,
    abbreviation (exact, case-insensitive), normalized abbreviation.
    Last resort: the user's team (never None -> never "not found").
    """
    league = _league(game)
    teams = safe_call(lambda: list(getattr(league, "teams", []) or []),
                  [],
                      context="team/find_teams") or []
    user_team = _user_team(game)
    if user_team is not None and all(t is not user_team for t in teams):
        teams = [user_team] + teams
    if not teams:
        return user_team
    raw = str(name or "")
    want = raw.strip().lower()
    want_norm = _norm_team_key(raw)
    # 1. exact team_name
    for t in teams:
        tn = safe_call(lambda: str(getattr(t, "team_name", "")).strip().lower(),
                   "",
                       context="team/find_team_name")
        if tn == want:
            return t
    # 2. normalized team_name
    if want_norm:
        for t in teams:
            if _norm_team_key(safe_call(lambda: getattr(t, "team_name", ""),
                                    "",
                                        context="team/find_norm_name")) == want_norm:
                return t
    # 3. abbreviation, exact (case-insensitive)
    if want:
        for t in teams:
            for ab in _team_abbrs(t):
                if ab.strip().lower() == want:
                    return t
    # 4. normalized abbreviation
    if want_norm:
        for t in teams:
            for ab in _team_abbrs(t):
                if _norm_team_key(ab) == want_norm:
                    return t
    # 5. last resort: user's team
    return user_team


def _fmt_money(n):
    try:
        n = int(n or 0)
    except Exception:
        return "$0"
    if n >= 1_000_000:
        return f"${n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"${round(n / 1_000)}K"
    return f"${n:,}"


class TeamScreen(BaseScreen):
    """Read-only overview of a single team."""

    title = "Team"

    def _build_body(self):
        self._team = None
        self._fallback_note = QLabel("")
        self._fallback_note.setStyleSheet(
            "color: #e8b34b; font-size: 12px; font-style: italic;")
        self._fallback_note.setWordWrap(True)
        self._fallback_note.setVisible(False)
        self._layout.addWidget(self._fallback_note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._host = QWidget()
        self._host_layout = QVBoxLayout(self._host)
        self._host_layout.setAlignment(Qt.AlignTop)
        self._host_layout.setSpacing(12)
        scroll.setWidget(self._host)
        self._layout.addWidget(scroll, 1)

    # ------------------------------------------------------------------
    def set_team(self, team_name):
        """Select which team this screen shows. Never leaves the screen
        empty: falls back to the user's team, then the first league team."""
        league = _league(self.game)
        t = find_team(self.game, team_name)
        note = ""
        if t is None:
            teams = safe_call(lambda: list(getattr(league, "teams", []) or []),
                          [],
                              context="team/load_teams") or []
            t = teams[0] if teams else None
        else:
            tn = safe_call(lambda: getattr(t, "team_name", ""), "", context="team/load_team_name")
            if str(team_name or "").strip().lower() not in (
                    str(tn).strip().lower(),):
                # name matched tolerantly or fell back to user team
                ut = _user_team(self.game)
                if t is ut and team_name:
                    note = (f'Could not match "{team_name}" exactly — '
                            "showing your team instead.")
        self._team = t
        self._fallback_note.setText(note)
        self._fallback_note.setVisible(bool(note))
        self._render()

    def _current_team(self):
        if self._team is not None:
            return self._team
        t = _user_team(self.game)
        if t is None:
            league = _league(self.game)
            teams = safe_call(lambda: list(getattr(league, "teams", []) or []),
                          [],
                              context="team/ensure_teams") or []
            t = teams[0] if teams else None
        self._team = t
        return t

    # ------------------------------------------------------------------
    def refresh(self):
        self._render()

    def _clear_host(self):
        layout = self._host_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                TeamScreen._clear_inner(sub)

    @staticmethod
    def _clear_inner(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                TeamScreen._clear_inner(sub)

    def _render(self):
        self._clear_host()
        t = self._current_team()
        if t is None:
            lbl = QLabel("No team data available yet.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #6b7488; font-size: 14px;")
            self._host_layout.addWidget(lbl)
            return
        user_team = _user_team(self.game)
        is_user = t is user_team
        league = _league(self.game)

        name = safe_call(lambda: getattr(t, "team_name", "?"), "?", context="team/header_name")
        w = safe_call(lambda: int(getattr(t, "wins", 0) or 0), 0, context="team/header_wins")
        l = safe_call(lambda: int(getattr(t, "losses", 0) or 0), 0, context="team/header_losses")
        otl = safe_call(lambda: int(getattr(t, "otl", 0)
                                or getattr(t, "overtime_losses", 0) or 0), 0,
                        context="team/header_otl")
        pts = w * 2 + otl
        gp = w + l + otl

        # ---- header ----
        header = QFrame()
        header.setObjectName("tile")
        hl = QVBoxLayout(header)
        title = QLabel(f"{name}" + ("  ⭐ YOUR TEAM" if is_user else ""))
        title.setObjectName("section-header")
        hl.addWidget(title)
        record = QLabel(f"{w}-{l}-{otl}  ·  {pts} PTS  ·  {gp} GP")
        record.setStyleSheet(
            "font-size: 22px; font-weight: 800; color: #f2f4f8;")
        hl.addWidget(record)
        meta = []
        division = safe_call(lambda: getattr(t, "division", ""), "", context="team/division")
        conference = safe_call(lambda: getattr(t, "conference", ""), "", context="team/conference")
        div_rank = self._division_rank(t, name)
        if division:
            meta.append(f"Division: {division}"
                        + (f" ({div_rank} of {div_rank[1]})"
                           if isinstance(div_rank, tuple) else
                           (f" — #{div_rank}" if div_rank else "")))
        if conference:
            meta.append(f"Conference: {conference}")
        streak = self._streak(t, league, name)
        if streak:
            meta.append(f"Streak: {streak}")
        cap = self._cap_space(t)
        if cap is not None:
            meta.append(f"Cap space: {cap}")
        if meta:
            ml = QLabel("   ·   ".join(meta))
            ml.setStyleSheet("color: #9aa4b8; font-size: 13px;")
            ml.setWordWrap(True)
            hl.addWidget(ml)
        self._host_layout.addWidget(header)

        # ---- leaders ----
        leaders = self._team_leaders(t)
        if leaders:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            h = QLabel("Team Leaders")
            h.setObjectName("section-header")
            cl.addWidget(h)
            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(
                ["Player", "Pos", "GP", "G", "A", "PTS"])
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            hdr = table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.Stretch)
            table.setRowCount(len(leaders))
            for i, (nm, pos, gp_, g_, a_) in enumerate(leaders):
                pts = int(g_ or 0) + int(a_ or 0)
                for col, txt in enumerate(
                        [nm, pos, gp_, g_, a_, str(pts)]):
                    item = QTableWidgetItem(str(txt))
                    if col == 5:
                        from PySide6.QtGui import QFont
                        _f = item.font()
                        _f.setBold(True)
                        item.setFont(_f)
                    table.setItem(i, col, item)
            cl.addWidget(table)
            self._host_layout.addWidget(card)

        # ---- recent form ----
        form = self._recent_form(t, league, name)
        if form:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            h = QLabel("Recent Form")
            h.setObjectName("section-header")
            cl.addWidget(h)
            for res, score, opp, vs in form:
                color = {"W": "#22c55e", "OTL": "#e8b34b",
                         "L": "#ef4444"}.get(res, "#9aa4b8")
                row = QHBoxLayout()
                tag = QLabel(res)
                tag.setStyleSheet(
                    f"font-size: 13px; font-weight: 800; color: {color};")
                row.addWidget(tag)
                detail = QLabel(f"{score}  {vs} {opp}")
                detail.setStyleSheet(
                    "color: #cdd6e4; font-size: 13px;")
                row.addWidget(detail, 1)
                cl.addLayout(row)
            self._host_layout.addWidget(card)

        # ---- roster ----
        roster = safe_call(lambda: list(getattr(t, "roster", []) or []), [], context="team/roster") or []
        if roster:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            h = QLabel(f"Roster ({len(roster)} players)")
            h.setObjectName("section-header")
            cl.addWidget(h)
            pt = PlayerTable()
            pt.set_main_window(self.main_window)
            pt.set_players(roster)
            pt.player_clicked.connect(self._on_player_clicked)
            pt.setMaximumHeight(360)
            cl.addWidget(pt)
            self._host_layout.addWidget(card)

    def _on_player_clicked(self, player):
        try:
            self.main_window.open_player(player)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _division_rank(self, t, name):
        league = _league(self.game)
        division = safe_call(lambda: getattr(t, "division", ""), "", context="team/rank_division")
        standings = safe_call(lambda: list(getattr(league, "standings", [])
                                       or []), [],
                              context="team/rank_standings") or []
        if not standings or not division:
            return None
        div_teams = []
        for s in standings:
            try:
                st = s.get("team") if isinstance(s, dict) else s
                if safe_call(lambda: getattr(st, "division", ""), "", context="team/rank_entry_division") \
                        == division:
                    sw = safe_call(lambda: int(getattr(st, "wins", 0) or 0), 0, context="team/rank_entry_wins")
                    so = safe_call(lambda: int(
                        getattr(st, "otl", 0)
                        or getattr(st, "overtime_losses", 0) or 0), 0,
                                   context="team/rank_entry_otl")
                    div_teams.append(
                        (safe_call(lambda: getattr(st, "team_name", ""), "", context="team/rank_entry_name"),
                         sw * 2 + so))
            except Exception:
                continue
        div_teams.sort(key=lambda x: -x[1])
        for i, (tn, _pts) in enumerate(div_teams):
            if tn == name:
                return i + 1
        return None

    def _streak(self, t, league, name):
        sched = safe_call(lambda: list(getattr(league, "schedule", []) or []),
                      [],
                          context="team/streak_schedule") or []
        form = []
        for g in reversed(sched):
            try:
                if not isinstance(g, dict):
                    continue
                hs = g.get("home_score")
                if hs is None:
                    continue
                hn = safe_call(lambda: str(
                    getattr(g.get("home_team"), "team_name",
                            g.get("home_team", ""))), "",
                               context="team/streak_home_name")
                an = safe_call(lambda: str(
                    getattr(g.get("away_team"), "team_name",
                            g.get("away_team", ""))), "",
                               context="team/streak_away_name")
                if name not in (hn, an):
                    continue
                aws = g.get("away_score", 0) or 0
                mine = hs if hn == name else aws
                theirs = aws if hn == name else hs
                res = ("W" if mine > theirs
                       else ("OTL" if abs(mine - theirs) == 1 else "L"))
                form.append(res)
                if len(form) >= 5:
                    break
            except Exception:
                continue
        streak, n = "", 0
        for r in form:
            r2 = "W" if r == "W" else "L"
            if not streak:
                streak, n = r2, 1
            elif r2 == streak:
                n += 1
            else:
                break
        return f"{streak}{n}" if streak else "—"

    def _team_leaders(self, t):
        roster = safe_call(lambda: list(getattr(t, "roster", []) or []), [], context="team/leaders_roster") or []
        skaters = [p for p in roster
                   if safe_call(lambda: str(getattr(p, "primary_position", "")
                                        ).upper(), "",
                                context="team/leaders_position_filter") not in ("G", "GOALIE")]

        def _pts(p):
            return safe_call(lambda: int(getattr(p, "points", 0) or 0), 0, context="team/leaders_points")

        def _g(p):
            return safe_call(lambda: int(getattr(p, "goals", 0) or 0), 0, context="team/leaders_goals")

        def _a(p):
            return safe_call(lambda: int(getattr(p, "assists", 0) or 0), 0, context="team/leaders_assists")

        out = []
        for p in sorted(skaters, key=lambda p: (-_pts(p), -_g(p)))[:5]:
            pos = safe_call(lambda: str(getattr(p, "primary_position", "")), "", context="team/leaders_position")
            try:
                pos = str(p.primary_position.value)
            except Exception:
                pass
            out.append((
                safe_call(lambda: getattr(p, "full_name", "?"), "?", context="team/leaders_name"),
                pos,
                str(safe_call(lambda: int(getattr(p, "games_played", 0) or 0), 0, context="team/leaders_gp")),
                str(_g(p)), str(_a(p)),
            ))
        return out

    def _recent_form(self, t, league, name):
        sched = safe_call(lambda: list(getattr(league, "schedule", []) or []),
                      [],
                          context="team/form_schedule") or []
        form = []
        for g in reversed(sched):
            try:
                if not isinstance(g, dict):
                    continue
                hs = g.get("home_score")
                if hs is None:
                    continue
                hn = safe_call(lambda: str(
                    getattr(g.get("home_team"), "team_name",
                            g.get("home_team", ""))), "",
                               context="team/form_home_name")
                an = safe_call(lambda: str(
                    getattr(g.get("away_team"), "team_name",
                            g.get("away_team", ""))), "",
                               context="team/form_away_name")
                if name not in (hn, an):
                    continue
                aws = g.get("away_score", 0) or 0
                mine = hs if hn == name else aws
                theirs = aws if hn == name else hs
                res = ("W" if mine > theirs
                       else ("OTL" if abs(mine - theirs) == 1 else "L"))
                form.append((res, f"{mine}-{theirs}",
                             an if hn == name else hn,
                             "vs" if hn == name else "@"))
                if len(form) >= 5:
                    break
            except Exception:
                continue
        return form

    def _cap_space(self, t):
        try:
            from salary_cap_system import cap_breakdown
            bd = cap_breakdown(t)
            space = bd.get("space", 0)
            return _fmt_money(space)
        except Exception:
            pass
        cs = safe_call(lambda: getattr(t, "cap_space", None), context="team/cap_space")
        return _fmt_money(cs) if cs is not None else None
