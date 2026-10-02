# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Game box score — drill-down view for any completed game.

Opened from the daily results window (double-click / Box Score button) and
from the Schedule screen's Recap/Stats buttons. Shows a real box score:

  - Scoring Summary: every goal grouped by period, with scorer, assists,
    strength (EV/PP/SH/EN), goal type and the running score.
  - Player Stats: per-team skater table (G/A/P/SOG/Hits/Blocks/FO) and
    goalie table (SA/Saves/SV%/GA) built from the sim's per-game stats.
  - Team Stats: side-by-side team comparison.
  - Three Stars, when player ratings are available.

Degrades gracefully for quick-simmed games that only carry scores.
"""

from player_context_menu import bind_player_context
import customtkinter as ctk
from popup_system import InGamePopup


def compute_line_ratings(lines_snapshot, game_stats, by_id):
    """Pure: per-line player grades + combined line ratings for the Lines tab.

    lines_snapshot: {'Forwards': [[pid..] x4], 'Defense': [[pid..] x3]}
      (player IDs, as stamped on the game result by
      HockeyManagerGUI._snapshot_game_lines).
    game_stats: {pid: {'g': int, 'a': int}} for that game.
    by_id: {pid: Player}.

    Returns a list of
      {'label': 'Line 1', 'players': [{'player', 'pos', 'g', 'a', 'p',
                                       'grade'}], 'rating': float|None}
    'grade' is the player's 0-10 game grade for THIS game (the exact
    formula record_performance appends to recent_game_grades, /10) or None
    when the player has no stats for the game. 'rating' is the mean of the
    available grades, or None when nobody on the unit has a grade.
    Never raises. (Muck 2026-10-02: "that way we know if lines are working".)
    """
    out = []
    try:
        from mesh_system import compute_skater_game_grade
    except Exception:
        compute_skater_game_grade = None
    try:
        from game_classes import position_label as _pos_label
    except Exception:
        _pos_label = None

    def _grade(player, pid):
        if compute_skater_game_grade is None:
            return None
        try:
            if pid not in (game_stats or {}):
                # No stats recorded for this player in this game: honest
                # "no data", never a neutral-looking 5.0.
                return None
            gs = game_stats.get(pid) or {}
            if not isinstance(gs, dict):
                return None
            return round(compute_skater_game_grade(
                player, gs.get('g', 0), gs.get('a', 0)) / 10.0, 1)
        except Exception:
            return None

    def _pos(player):
        try:
            if _pos_label is not None:
                return _pos_label(player)
        except Exception:
            pass
        try:
            pos = getattr(player, 'primary_position', None)
            return str(getattr(pos, 'value', None)
                       or getattr(pos, 'name', '') or '?')
        except Exception:
            return '?'

    try:
        snap = lines_snapshot or {}
        units = []
        for i, line in enumerate((snap.get('Forwards') or [])[:4]):
            units.append((f"Line {i + 1}", line or []))
        for i, pair in enumerate((snap.get('Defense') or [])[:3]):
            units.append((f"Pair {i + 1}", pair or []))
        for label, pids in units:
            players = []
            grades = []
            for pid in pids or []:
                try:
                    p = (by_id or {}).get(pid)
                    if p is None:
                        continue
                    gs = (game_stats or {}).get(pid) or {}
                    g = int(gs.get('g', 0) or 0)
                    a = int(gs.get('a', 0) or 0)
                    grade = _grade(p, pid)
                    if grade is not None:
                        grades.append(grade)
                    players.append({'player': p, 'pos': _pos(p),
                                    'g': g, 'a': a, 'p': g + a,
                                    'grade': grade})
                except Exception:
                    continue
            rating = round(sum(grades) / len(grades), 1) if grades else None
            out.append({'label': label, 'players': players,
                        'rating': rating})
    except Exception:
        pass
    return out


class GameBoxScoreView(ctk.CTkFrame):
    """Game box score view (embedded full-screen).

    A plain CTkFrame so it can be embedded anywhere: full-screen inside the
    main window (the default, via HockeyManagerGUI.show_screen) or inside
    the legacy GameBoxScoreWindow popup card.
    """
    TABS = ("Scoring Summary", "Player Stats", "Lines", "Team Stats")

    def __init__(self, parent, game_result, initial_tab="Scoring Summary", app=None):
        from ctk_theme import (
            BG, PANEL, CARD, BORDER, TEXT, TEXT_DIM, TEXT_FAINT,
            TEAL, GOLD, GREEN, RED,
        )
        self._c = dict(BG=BG, PANEL=PANEL, CARD=CARD, BORDER=BORDER, TEXT=TEXT,
                       TEXT_DIM=TEXT_DIM, TEXT_FAINT=TEXT_FAINT, TEAL=TEAL,
                       GOLD=GOLD, GREEN=GREEN, RED=RED)
        self.app = app if app is not None else parent
        ctk.CTkFrame.__init__(self, parent, fg_color=BG)
        # Set by show_screen() (dashboard) or the GameBoxScoreWindow wrapper (card).
        self._close_screen = None
        self.result = game_result

        r = self.result
        home, away = r.get('home_team'), r.get('away_team')
        self._home_name = getattr(home, 'team_name', str(home))
        self._away_name = getattr(away, 'team_name', str(away))
        self._home_score = r.get('home_score', 0)
        self._away_score = r.get('away_score', 0)

        self._build_header()
        self._build_tabs(initial_tab)

    # ------------------------------------------------------------------
    # data helpers
    # ------------------------------------------------------------------
    def _roster_lookup(self):
        by_id = {}
        for team in (self.result.get('home_team'), self.result.get('away_team')):
            roster = getattr(team, 'roster', None) or []
            for p in roster:
                by_id[getattr(p, 'id', None)] = p
        return by_id

    def _player_name(self, pid, by_id):
        p = by_id.get(pid)
        return getattr(p, 'full_name', 'Unknown') if p is not None else 'Unknown'

    def _is_goalie(self, player):
        pos = getattr(player, 'primary_position', None)
        name = getattr(pos, 'name', '') or str(pos)
        return 'GOALIE' in str(name).upper()

    def _goals(self):
        events = self.result.get('event_log') or []
        goals = [e for e in events if e.get('type') == 'GOAL_ADVANCED']
        def key(e):
            d = e.get('details', {})
            return (d.get('period', 99), e.get('timestamp', 0))
        return sorted(goals, key=key)

    @staticmethod
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

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_header(self):
        c = self._c
        r = self.result
        header = ctk.CTkFrame(self, fg_color=c['PANEL'], corner_radius=12)
        header.pack(fill='x', padx=14, pady=(14, 8))

        date = r.get('date')
        date_str = date.strftime("%b %d, %Y") if hasattr(date, 'strftime') else str(date or '')
        note = date_str
        if r.get('shootout'):
            note += "  •  Shootout"
        elif r.get('overtime'):
            note += "  •  Overtime"

        score = ctk.CTkLabel(
            header,
            text=f"{self._away_name}  {self._away_score}  @  {self._home_score}  {self._home_name}",
            font=('Segoe UI', 17, 'bold'), text_color=c['TEXT'])
        score.pack(pady=(12, 2))
        ctk.CTkLabel(header, text=note, font=('Segoe UI', 11),
                     text_color=c['TEXT_DIM']).pack(pady=(0, 6))

        stars = self._three_stars()
        if stars:
            row = ctk.CTkFrame(header, fg_color='transparent')
            row.pack(pady=(0, 10))
            medals = ["1st", "2nd", "3rd"]
            for i, (name, team_name, rating) in enumerate(stars[:3]):
                ctk.CTkLabel(
                    row,
                    text=f"★ {medals[i]}: {name} ({team_name})",
                    font=('Segoe UI', 11, 'bold' if i == 0 else 'normal'),
                    text_color=c['GOLD'] if i == 0 else c['TEXT_DIM']
                ).pack(side='left', padx=10)

    def _three_stars(self):
        # Prefer the stars recorded at game time (stars.record_game_stars)
        # so the box score agrees with the player card and monthly
        # narratives. Older results fall back to the ratings sort.
        saved = self.result.get('three_stars')
        if saved:
            return [(s.get('name'), s.get('team_name'), s.get('line'))
                    for s in saved[:3] if isinstance(s, dict)]
        ratings = self.result.get('player_ratings') or {}
        by_id = self._roster_lookup()
        stars = []
        for team_name, pmap in ratings.items():
            if not isinstance(pmap, dict):
                continue
            for pid, rating in pmap.items():
                stars.append((rating, self._player_name(pid, by_id), team_name))
        stars.sort(key=lambda s: s[0], reverse=True)
        return [(n, t, r_) for r_, n, t in stars[:3]]

    def _build_tabs(self, initial_tab):
        c = self._c
        self.tabs = ctk.CTkTabview(self, fg_color=c['PANEL'], corner_radius=12,
                                   segmented_button_fg_color=c['CARD'],
                                   segmented_button_selected_color=c['TEAL'],
                                   segmented_button_selected_hover_color=c['TEAL'],
                                   text_color=c['TEXT'])
        self.tabs.pack(fill='both', expand=True, padx=14, pady=(0, 8))
        for name in self.TABS:
            self.tabs.add(name)
        self._fill_scoring(self.tabs.tab("Scoring Summary"))
        self._fill_players(self.tabs.tab("Player Stats"))
        self._fill_lines(self.tabs.tab("Lines"))
        self._fill_teams(self.tabs.tab("Team Stats"))
        if initial_tab in self.TABS:
            try:
                self.tabs.set(initial_tab)
            except Exception:
                pass

        from ctk_theme import secondary_button
        secondary_button(self, text="Close", command=self.close_view).pack(pady=(0, 14))

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # Scoring Summary tab
    # ------------------------------------------------------------------
    def _fill_scoring(self, tab):
        c = self._c
        goals = self._goals()
        by_id = self._roster_lookup()
        body = ctk.CTkScrollableFrame(tab, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=6, pady=6)

        if not goals:
            ctk.CTkLabel(body, text="Detailed scoring data is unavailable for this game.",
                         font=('Segoe UI', 12), text_color=c['TEXT_DIM'],
                         wraplength=600, justify='center').pack(pady=40)
            return

        home_running = away_running = 0
        last_period = None
        for e in goals:
            d = e.get('details', {})
            period = d.get('period', 1)
            if period != last_period:
                last_period = period
                ctk.CTkLabel(body, text=self._period_label(period),
                             font=('Segoe UI', 13, 'bold'),
                             text_color=c['TEAL'], anchor='w').pack(
                                 anchor='w', padx=8, pady=(10, 4))

            scorer = self._player_name(d.get('scorer_id'), by_id)
            assists = [self._player_name(a, by_id) for a in (d.get('assist_ids') or [])]
            assist_txt = f"  ({', '.join(assists)})" if assists else "  (unassisted)"

            scorer_team = None
            sp = by_id.get(d.get('scorer_id'))
            if sp is not None:
                scorer_team = getattr(sp, 'team_name', None)
            if scorer_team == self._home_name:
                home_running += 1
            elif scorer_team == self._away_name:
                away_running += 1

            strength = d.get('strength', 'EV')
            gtype = str(d.get('goal_type', '')).replace('_', ' ').title()
            time_str = d.get('time_str', '')

            card = ctk.CTkFrame(body, fg_color=c['CARD'], corner_radius=8)
            card.pack(fill='x', padx=8, pady=3)
            left = ctk.CTkFrame(card, fg_color='transparent')
            left.pack(side='left', fill='x', expand=True, padx=10, pady=8)
            ctk.CTkLabel(left, text=f"{scorer}{assist_txt}",
                         font=('Segoe UI', 12, 'bold'), text_color=c['TEXT'],
                         anchor='w').pack(anchor='w')
            sub = f"{time_str}"
            if strength and strength != 'EV':
                sub += f"  •  {strength}"
            if gtype:
                sub += f"  •  {gtype}"
            ctk.CTkLabel(left, text=sub.strip(),
                         font=('Segoe UI', 10), text_color=c['TEXT_FAINT'],
                         anchor='w').pack(anchor='w')

            badge_color = {'PP': c['GREEN'], 'SH': c['GOLD'],
                           'EN': c['TEXT_FAINT']}.get(strength, c['TEXT_FAINT'])
            right = ctk.CTkFrame(card, fg_color='transparent')
            right.pack(side='right', padx=10)
            if strength and strength != 'EV':
                ctk.CTkLabel(right, text=strength, font=('Segoe UI', 10, 'bold'),
                             text_color=c['BG'], fg_color=badge_color,
                             corner_radius=6, width=34).pack(pady=(0, 2))
            ctk.CTkLabel(right, text=f"{self._away_name[:3].upper()} {away_running} – "
                                     f"{home_running} {self._home_name[:3].upper()}",
                         font=('Segoe UI', 12, 'bold'),
                         text_color=c['TEXT']).pack()

    # ------------------------------------------------------------------
    # Player Stats tab
    # ------------------------------------------------------------------
    def _fill_players(self, tab):
        c = self._c
        game_stats = self.result.get('game_stats') or {}
        by_id = self._roster_lookup()

        top = ctk.CTkFrame(tab, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(8, 4))
        ctk.CTkLabel(top, text="Team:", font=('Segoe UI', 11, 'bold'),
                     text_color=c['TEXT_DIM']).pack(side='left')
        self._team_var = ctk.StringVar(value=self._home_name)
        combo = ctk.CTkComboBox(top, variable=self._team_var,
                                values=[self._away_name, self._home_name],
                                state='readonly', width=220,
                                fg_color=c['CARD'], border_color=c['BORDER'],
                                button_color=c['TEAL'],
                                command=lambda _v: self._refresh_players())
        combo.pack(side='left', padx=8)

        self._players_body = ctk.CTkScrollableFrame(tab, fg_color='transparent')
        self._players_body.pack(fill='both', expand=True, padx=6, pady=4)

        if not game_stats:
            ctk.CTkLabel(self._players_body,
                         text="Per-player stats are unavailable for this game.",
                         font=('Segoe UI', 12), text_color=c['TEXT_DIM']
                         ).pack(pady=40)
            self._players_body = None
            return
        self._refresh_players()

    def _refresh_players(self):
        body = self._players_body
        if body is None:
            return
        c = self._c
        for child in body.winfo_children():
            child.destroy()

        game_stats = self.result.get('game_stats') or {}
        by_id = self._roster_lookup()
        team_name = self._team_var.get()

        skaters, goalies = [], []
        for pid, gs in game_stats.items():
            p = gs.get('player') or by_id.get(pid)
            if p is None:
                continue
            if getattr(p, 'team_name', None) != team_name:
                continue
            (goalies if self._is_goalie(p) else skaters).append((p, gs))

        skaters.sort(key=lambda ps: (ps[1].get('g', 0) + ps[1].get('a', 0),
                                      ps[1].get('g', 0)), reverse=True)

        ctk.CTkLabel(body, text="Skaters", font=('Segoe UI', 13, 'bold'),
                     text_color=c['TEAL'], anchor='w').pack(anchor='w', padx=8, pady=(4, 2))
        self._grid_table(
            body,
            headers=["Player", "Pos", "G", "A", "P", "SOG", "Hits", "Blk", "FO"],
            widths=[220, 52, 40, 40, 40, 52, 52, 52, 64],
            rows=[[getattr(p, 'full_name', '?'),
                   self._pos_short(p),
                   gs.get('g', 0), gs.get('a', 0),
                   gs.get('g', 0) + gs.get('a', 0),
                   gs.get('shots_on_goal', 0), gs.get('hits', 0),
                   gs.get('blocked_shots', gs.get('blocked_shots_by', 0)),
                   f"{gs.get('faceoffs_won', 0)}-{gs.get('faceoffs_lost', 0)}"]
                  for p, gs in skaters],
            players=[p for p, gs in skaters])

        if goalies:
            ctk.CTkLabel(body, text="Goaltenders", font=('Segoe UI', 13, 'bold'),
                         text_color=c['TEAL'], anchor='w').pack(anchor='w', padx=8, pady=(10, 2))
            # Goals against per goalie from the goal events (engines that
            # don't track per-goalie GA still record the beaten goalie).
            ga_by_goalie = {}
            for e in self._goals():
                gid = e.get('details', {}).get('goaltender_id')
                if gid:
                    ga_by_goalie[gid] = ga_by_goalie.get(gid, 0) + 1
            grows = []
            for p, gs in goalies:
                sa = gs.get('shots_against', 0)
                sv = gs.get('saves', 0)
                ga = gs.get('goals_against', 0) or ga_by_goalie.get(p.id, 0)
                if sa <= sv:  # engine didn't track shots against; derive it
                    sa = sv + ga
                svp = f"{(sv / sa * 100):.1f}%" if sa else "–"
                grows.append([getattr(p, 'full_name', '?'), sa, sv, svp, ga])
            self._grid_table(
                body,
                headers=["Goaltender", "SA", "Saves", "SV%", "GA"],
                widths=[220, 52, 64, 64, 52],
                rows=grows,
                players=[p for p, gs in goalies])

    # ------------------------------------------------------------------
    # Lines tab (Muck 2026-10-02): even-strength combos with combined
    # per-line game ratings, so you can see whether lines are working.
    # ------------------------------------------------------------------
    def _fill_lines(self, tab):
        c = self._c
        top = ctk.CTkFrame(tab, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(8, 4))
        ctk.CTkLabel(top, text="Team:", font=('Segoe UI', 11, 'bold'),
                     text_color=c['TEXT_DIM']).pack(side='left')
        self._lines_team_var = ctk.StringVar(value=self._home_name)
        combo = ctk.CTkComboBox(top, variable=self._lines_team_var,
                                values=[self._away_name, self._home_name],
                                state='readonly', width=220,
                                fg_color=c['CARD'], border_color=c['BORDER'],
                                button_color=c['TEAL'],
                                command=lambda _v: self._refresh_lines())
        combo.pack(side='left', padx=8)
        ctk.CTkLabel(top, text="Even-strength lines with combined ratings (0-10).",
                     font=('Segoe UI', 10), text_color=c['TEXT_FAINT']
                     ).pack(side='left', padx=12)

        self._lines_body = ctk.CTkScrollableFrame(tab, fg_color='transparent')
        self._lines_body.pack(fill='both', expand=True, padx=6, pady=4)
        self._refresh_lines()

    def _refresh_lines(self):
        body = getattr(self, '_lines_body', None)
        if body is None:
            return
        c = self._c
        for child in body.winfo_children():
            child.destroy()
        try:
            self._render_lines(body)
        except Exception:
            ctk.CTkLabel(body, text="Line data unavailable for this game.",
                         font=('Segoe UI', 12), text_color=c['TEXT_DIM']
                         ).pack(pady=40)

    def _render_lines(self, body):
        c = self._c
        game_stats = self.result.get('game_stats') or {}
        by_id = self._roster_lookup()
        # Merge game_stats-embedded players (traded away since, etc.).
        for pid, gs in (game_stats or {}).items():
            try:
                p = gs.get('player') if isinstance(gs, dict) else None
                if p is not None and pid not in by_id:
                    by_id[pid] = p
            except Exception:
                continue

        team_name = self._lines_team_var.get()
        snap = (self.result.get('lines') or {}).get(team_name)
        caveat = ""
        if not snap:
            # Fallback for saves predating line stamping: current lines.
            try:
                from game_classes import snapshot_team_lines as _snap_fn
                team = None
                for t in (self.result.get('home_team'),
                          self.result.get('away_team')):
                    if getattr(t, 'team_name', None) == team_name:
                        team = t
                        break
                snap = _snap_fn(team) if team is not None else None
                if snap:
                    caveat = " (current lines -- game-time combos not recorded)"
            except Exception:
                snap = None

        if not snap:
            ctk.CTkLabel(body,
                         text="Line combinations unavailable for this game.",
                         font=('Segoe UI', 12), text_color=c['TEXT_DIM']
                         ).pack(pady=40)
            return

        lines = compute_line_ratings(snap, game_stats, by_id)
        if not lines or not any(L['players'] for L in lines):
            ctk.CTkLabel(body,
                         text="Line combinations unavailable for this game.",
                         font=('Segoe UI', 12), text_color=c['TEXT_DIM']
                         ).pack(pady=40)
            return

        if caveat:
            ctk.CTkLabel(body, text=f"Showing {team_name}'s{caveat}",
                         font=('Segoe UI', 10, 'italic'),
                         text_color=c['TEXT_FAINT'], anchor='w'
                         ).pack(anchor='w', padx=8, pady=(2, 6))

        for L in lines:
            rating = L['rating']
            if rating is None:
                rtxt, rcolor = "--", c['TEXT_DIM']
            else:
                rtxt = f"{rating:.1f}"
                rcolor = (c['GREEN'] if rating >= 7.0
                          else c['GOLD'] if rating >= 5.5 else c['RED'])
            hdr = ctk.CTkFrame(body, fg_color='transparent')
            hdr.pack(fill='x', padx=8, pady=(10, 2))
            ctk.CTkLabel(hdr, text=L['label'], font=('Segoe UI', 13, 'bold'),
                         text_color=c['TEAL'], anchor='w').pack(side='left')
            ctk.CTkLabel(hdr, text=f"Rating  {rtxt}",
                         font=('Segoe UI', 13, 'bold'),
                         text_color=rcolor, anchor='e').pack(side='right',
                                                            padx=4)
            rows, players = [], []
            for pl in L['players']:
                p = pl['player']
                grade = pl['grade']
                rows.append([getattr(p, 'full_name', '?'), pl['pos'],
                             pl['g'], pl['a'], pl['p'],
                             f"{grade:.1f}" if grade is not None else "--"])
                players.append(p)
            self._grid_table(body,
                             headers=["Player", "Pos", "G", "A", "P", "Grade"],
                             widths=[220, 52, 40, 40, 40, 64],
                             rows=rows, players=players)

    @staticmethod
    def _pos_short(player):
        pos = getattr(player, 'primary_position', None)
        val = getattr(pos, 'value', None) or getattr(pos, 'name', '') or ''
        return str(val)

    def _grid_table(self, parent, headers, widths, rows, players=None):
        c = self._c
        frame = ctk.CTkFrame(parent, fg_color=c['CARD'], corner_radius=8)
        frame.pack(fill='x', padx=8, pady=2)
        for ci, (h, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(frame, text=h, font=('Segoe UI', 10, 'bold'),
                         text_color=c['TEXT_DIM'], width=w,
                         anchor='w' if ci == 0 else 'center').grid(
                             row=0, column=ci, padx=4, pady=(8, 4), sticky='w' if ci == 0 else '')
        for ri, row in enumerate(rows, start=1):
            bg = c['CARD'] if ri % 2 else c['PANEL']
            for ci, (val, w) in enumerate(zip(row, widths)):
                lbl = ctk.CTkLabel(frame, text=str(val),
                                   font=('Segoe UI', 11,
                                         'bold' if ci == 0 else 'normal'),
                                   text_color=c['TEXT'], width=w,
                                   anchor='w' if ci == 0 else 'center',
                                   fg_color=bg, corner_radius=4)
                lbl.grid(row=ri, column=ci, padx=4, pady=2,
                         sticky='ew' if ci == 0 else '')
                # Right-click player name for context menu
                if ci == 0 and players and ri - 1 < len(players):
                    try:
                        bind_player_context(lbl, players[ri - 1], self)
                    except Exception:
                        pass
        frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Team Stats tab
    # ------------------------------------------------------------------
    def _fill_teams(self, tab):
        c = self._c
        body = ctk.CTkScrollableFrame(tab, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=6, pady=6)

        team_stats = self.result.get('team_stats') or {}
        a_ts = team_stats.get(self._away_name, {})
        h_ts = team_stats.get(self._home_name, {})

        def val(ts, key, default=0):
            v = ts.get(key, default)
            return v if isinstance(v, (int, float)) else default

        # Fallbacks from the event log when team_stats are missing
        shots_a = shots_h = saves_a = saves_h = 0
        if not a_ts and not h_ts:
            by_id = self._roster_lookup()
            for e in (self.result.get('event_log') or []):
                d = e.get('details', {})
                if e.get('type') == 'GOAL_ADVANCED':
                    p = by_id.get(d.get('scorer_id'))
                    if p is not None and getattr(p, 'team_name', None) == self._home_name:
                        shots_h += 1
                    else:
                        shots_a += 1
                elif e.get('type') == 'SAVE_ADVANCED':
                    p = by_id.get(d.get('goaltender_id'))
                    if p is not None and getattr(p, 'team_name', None) == self._home_name:
                        saves_h += 1
                        shots_a += 1
                    else:
                        saves_a += 1
                        shots_h += 1
                elif e.get('type') == 'SHOT':
                    # Visual engine logs SHOT results instead of SAVE_ADVANCED
                    if d.get('result') not in ('GOAL', 'SAVE'):
                        continue
                    p = by_id.get(d.get('shooter_id'))
                    if p is None:
                        continue
                    if getattr(p, 'team_name', None) == self._home_name:
                        shots_h += 1
                        if d.get('result') == 'SAVE':
                            saves_a += 1
                    else:
                        shots_a += 1
                        if d.get('result') == 'SAVE':
                            saves_h += 1

        rows = [
            ("Goals", self._away_score, self._home_score),
            ("Shots on Goal",
             val(a_ts, 'shots_on_goal', shots_a), val(h_ts, 'shots_on_goal', shots_h)),
            ("Saves",
             val(a_ts, 'saves', saves_a), val(h_ts, 'saves', saves_h)),
            ("Hits", val(a_ts, 'hits'), val(h_ts, 'hits')),
            ("Blocked Shots",
             val(a_ts, 'blocked_shots_by_team', val(a_ts, 'blocked_shots')),
             val(h_ts, 'blocked_shots_by_team', val(h_ts, 'blocked_shots'))),
            ("Faceoffs Won", val(a_ts, 'faceoffs_won'), val(h_ts, 'faceoffs_won')),
            ("Takeaways", val(a_ts, 'takeaways'), val(h_ts, 'takeaways')),
            ("Giveaways", val(a_ts, 'giveaways'), val(h_ts, 'giveaways')),
            ("Power Play",
             f"{val(a_ts, 'power_play_goals')}/{val(a_ts, 'power_play_opportunities')}",
             f"{val(h_ts, 'power_play_goals')}/{val(h_ts, 'power_play_opportunities')}"),
            ("Short-handed Goals",
             val(a_ts, 'short_handed_goals'), val(h_ts, 'short_handed_goals')),
        ]

        frame = ctk.CTkFrame(body, fg_color=c['CARD'], corner_radius=8)
        frame.pack(fill='x', padx=8, pady=8)
        ctk.CTkLabel(frame, text="", width=170).grid(row=0, column=0)
        ctk.CTkLabel(frame, text=self._away_name, font=('Segoe UI', 11, 'bold'),
                     text_color=c['TEXT'], width=150).grid(row=0, column=1, pady=(10, 4))
        ctk.CTkLabel(frame, text=self._home_name, font=('Segoe UI', 11, 'bold'),
                     text_color=c['TEXT'], width=150).grid(row=0, column=2, pady=(10, 4))
        for ri, (label, av, hv) in enumerate(rows, start=1):
            bg = c['CARD'] if ri % 2 else c['PANEL']
            ctk.CTkLabel(frame, text=label, font=('Segoe UI', 11),
                         text_color=c['TEXT_DIM'], anchor='w', width=170,
                         fg_color=bg, corner_radius=4).grid(
                             row=ri, column=0, padx=6, pady=2, sticky='ew')
            ctk.CTkLabel(frame, text=str(av), font=('Segoe UI', 11, 'bold'),
                         text_color=c['TEXT'], width=150,
                         fg_color=bg, corner_radius=4).grid(
                             row=ri, column=1, padx=6, pady=2)
            ctk.CTkLabel(frame, text=str(hv), font=('Segoe UI', 11, 'bold'),
                         text_color=c['TEXT'], width=150,
                         fg_color=bg, corner_radius=4).grid(
                             row=ri, column=2, padx=6, pady=2)
        frame.grid_columnconfigure(0, weight=1)


class GameBoxScoreWindow(InGamePopup):
    """Popup wrapper around GameBoxScoreView (backward compatibility).

    New code should embed GameBoxScoreView as a full-screen view via
    ``HockeyManagerGUI.show_screen('box_score', 'Box Score', GameBoxScoreView,
    game_result)`` instead of opening this card.
    """

    def __init__(self, parent, game_result, initial_tab="Scoring Summary"):
        super().__init__(parent)
        self.title("Box Score")
        # Closing the card must tear down the popup card (manager-owned),
        # not just the inner frame.
        self._view = GameBoxScoreView(self, game_result, initial_tab, app=parent)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
