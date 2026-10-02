# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""AHL League view -- the AHL as a real, followable league in the UI.

D41 Phase 2 built the backend (schedule, sim, standings, Calder Cup) but
left the UI unwired. This is that UI: standings, scores, Calder Cup
bracket, team pages, and prospect leaders -- all in one place, following
the existing StatsStandingsView / AHLStatsView patterns (ctk_theme,
dark Treeviews, cards).

Story ecosystem: the view surfaces narrative hooks (Calder Cup races,
standout prospects knocking on the door) via ahl_narratives.py; this
file is presentation only and never drives the sim.

Never raises: every data path is try/except guarded.
"""

import tkinter as tk
from tkinter import ttk

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover
    ctk = None


def _sfont(family, size, weight=""):
    try:
        import tkinter.font as _tkf
        return _tkf.Font(family=family, size=size, weight=weight or "normal")
    except Exception:
        return ("TkDefaultFont", size)


class AHLLeagueView(ctk.CTkFrame):
    """Full-screen AHL league hub: standings, scores, Calder Cup, team,
    prospects."""

    TABS = ["Standings", "Scores", "Calder Cup", "Team", "Prospects"]

    def __init__(self, parent, app=None):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        self._ff = "Segoe UI"
        init_ctk_theme()
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None
        self.configure(fg_color=self._ct["BG"])

        self._setup_tree_style()
        self._selected_ahl_idx = None
        self.team_choice = tk.StringVar(value="All Farms")

        self._build()
        self.refresh_all()
        try:
            self.app.open_windows["ahl_league"] = self
        except Exception:
            pass

    # ------------------------------------------------------------------
    # chrome
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        ct = self._ct
        try:
            style = ttk.Style(self)
            style.configure("AHL.Treeview",
                            background=ct["CARD"],
                            fieldbackground=ct["CARD"],
                            foreground=ct["TEXT"],
                            rowheight=26,
                            font=_sfont(self._ff, 10))
            style.configure("AHL.Treeview.Heading",
                            background=ct["PANEL"],
                            foreground=ct["TEXT_DIM"],
                            font=_sfont(self._ff, 10, "bold"))
            style.map("AHL.Treeview",
                      background=[("selected", ct["ROW_SELECTED"])])
        except Exception:
            pass

    def _card(self, parent, **kw):
        ct = self._ct
        kw.setdefault("fg_color", ct["CARD"])
        kw.setdefault("corner_radius", 10)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", ct["BORDER"])
        return ctk.CTkFrame(parent, **kw)

    def _make_tree(self, parent, columns):
        tree = ttk.Treeview(parent, columns=list(columns.keys()),
                            show="headings", style="AHL.Treeview",
                            height=18)
        for key, (label, width) in columns.items():
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center")
        tree.column(list(columns.keys())[1], anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            try:
                fn()
                return
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build(self):
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct["BG"], corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        title_card = self._card(main)
        title_card.pack(fill="x", pady=(0, 10))
        row = ctk.CTkFrame(title_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)
        self._heading(row, text="AHL \u2014 American Hockey League",
                      size=20).pack(side="left")
        self.season_label = self._body(row, text="", dim=True, size=11)
        self.season_label.pack(side="left", padx=(12, 0))
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right")
        self._secondary_button(btns, text="Refresh",
                               command=self.refresh_all).pack(side="left",
                                                              padx=(0, 6))
        self._secondary_button(btns, text="Close",
                               command=self.close_view).pack(side="left")

        # Tab bar
        tabbar = ctk.CTkFrame(main, fg_color="transparent")
        tabbar.pack(fill="x", pady=(0, 10))
        self._tab_buttons = []
        self._tab_var = tk.StringVar(value=self.TABS[0])
        for t in self.TABS:
            b = ctk.CTkButton(tabbar, text=t, width=110,
                              fg_color=ct["PANEL"],
                              hover_color=ct["TEAL_HOVER"],
                              text_color=ct["TEXT"],
                              font=(self._ff, 11, "bold"),
                              command=lambda _t=t: self._select_tab(_t))
            b.pack(side="left", padx=(0, 6))
            self._tab_buttons.append((t, b))

        # Tab bodies (stacked, only one visible)
        self._tab_frames = {}
        body = ctk.CTkFrame(main, fg_color="transparent")
        body.pack(fill="both", expand=True)
        for t in self.TABS:
            f = ctk.CTkFrame(body, fg_color="transparent")
            f.pack(fill="both", expand=True)
            self._tab_frames[t] = f

        self._build_standings_tab()
        self._build_scores_tab()
        self._build_calder_tab()
        self._build_team_tab()
        self._build_prospects_tab()
        self._select_tab(self.TABS[0])

    def _select_tab(self, name):
        try:
            self._tab_var.set(name)
            for t, b in self._tab_buttons:
                try:
                    b.configure(
                        fg_color=self._ct["TEAL"] if t == name
                        else self._ct["PANEL"])
                except Exception:
                    pass
            for t, f in self._tab_frames.items():
                try:
                    if t == name:
                        f.pack(fill="both", expand=True)
                        f.lift()
                    else:
                        f.pack_forget()
                except Exception:
                    pass
        except Exception:
            pass

    def show_team(self, ahl_idx):
        """Jump to the Team tab for one AHL club."""
        try:
            self._selected_ahl_idx = int(ahl_idx)
        except Exception:
            return
        self._select_tab("Team")
        self.refresh_team_tab()

    # ------------------------------------------------------------------
    # data helpers
    # ------------------------------------------------------------------
    def _league(self):
        try:
            gm = getattr(self.app, "game_manager", self.app)
            return getattr(gm, "league", None)
        except Exception:
            return None

    def _current_date(self):
        try:
            return getattr(self.app, "current_date", None)
        except Exception:
            return None

    def _ahl_teams(self):
        try:
            import ahl_league as _al
            return _al.ahl_team_list(self._league())
        except Exception:
            return []

    def _user_farm_idx(self):
        """AHL index of the user's farm club (None if unknown)."""
        try:
            import ahl_league as _al
            gm = getattr(self.app, "game_manager", self.app)
            user_team = getattr(gm, "user_team", None)
            uname = getattr(user_team, "team_name", None)
            for i, t in enumerate(_al.ahl_team_list(self._league())):
                parent = getattr(t, "parent_team", None)
                if parent is not None and getattr(
                        parent, "team_name", None) == uname:
                    return i
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Standings tab
    # ------------------------------------------------------------------
    def _build_standings_tab(self):
        f = self._tab_frames["Standings"]
        card = self._card(f)
        card.pack(fill="both", expand=True)
        self._heading(card, text="Standings", size=14,
                      text_color=self._ct["TEAL"]).pack(
                          anchor="w", padx=14, pady=(10, 4))
        tf = ctk.CTkFrame(card, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.standings_tree = self._make_tree(tf, {
            "rank": ("#", 36), "team": ("Team", 200),
            "affil": ("NHL Affiliate", 170),
            "gp": ("GP", 44), "w": ("W", 44), "l": ("L", 44),
            "otl": ("OTL", 48), "pts": ("PTS", 52),
            "gf": ("GF", 48), "ga": ("GA", 48), "diff": ("DIFF", 52),
        })
        self.standings_tree.bind("<Double-1>", self._on_standings_dblclick)
        self.standings_status = self._body(card, text="", dim=True, size=11)
        self.standings_status.pack(anchor="w", padx=14, pady=(0, 8))

    def _on_standings_dblclick(self, _event):
        try:
            sel = self.standings_tree.selection()
            if not sel:
                return
            iid_map = getattr(self, "_standings_iid_map", None) or {}
            idx = iid_map.get(sel[0])
            if idx is not None:
                self.show_team(idx)
        except Exception:
            pass

    def refresh_standings_tab(self):
        try:
            import ahl_league as _al
            tree = self.standings_tree
            for item in tree.get_children():
                tree.delete(item)
            self._standings_iid_map = {}
            league = self._league()
            if league is None:
                self.standings_status.configure(text="No league loaded.")
                return
            teams = _al.ahl_team_list(league)
            if not teams:
                self.standings_status.configure(
                    text="No AHL clubs found.")
                return
            rows = _al.get_ahl_standings(league)
            mine = self._user_farm_idx()
            label = getattr(league, "ahl_schedule_label", "") or ""
            try:
                self.season_label.configure(
                    text=f"{label} \u2014 48-game schedule"
                    if label else "48-game schedule")
            except Exception:
                pass
            for rank, (idx, rec) in enumerate(rows, 1):
                try:
                    tname = _al._tname(teams, idx)
                    parent = getattr(teams[idx], "parent_team", None)
                    affil = getattr(parent, "team_name", "") if parent else ""
                    gp = int(rec.get("gp", 0))
                    w = int(rec.get("w", 0))
                    l = int(rec.get("l", 0))
                    otl = int(rec.get("otl", 0))
                    pts = int(rec.get("pts", 0))
                    gf = int(rec.get("gf", 0))
                    ga = int(rec.get("ga", 0))
                    tag = ""
                    if mine is not None and idx == mine:
                        tag = "mine"
                        tree.tag_configure("mine",
                                           background=self._ct["ROW_SELECTED"])
                    iid = tree.insert("", "end", values=(
                        rank, tname, affil, gp, w, l, otl, pts, gf, ga,
                        gf - ga), tags=(tag,) if tag else ())
                    # map the row widget -> AHL club index for double-click
                    if not hasattr(self, "_standings_iid_map"):
                        self._standings_iid_map = {}
                    self._standings_iid_map[iid] = idx
                except Exception:
                    continue
            played = sum(1 for _, r in rows if int(r.get("gp", 0)) > 0)
            self.standings_status.configure(
                text=f"{len(rows)} clubs \u2014 double-click a team for "
                     f"its page. {played} clubs have played.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Scores tab
    # ------------------------------------------------------------------
    def _build_scores_tab(self):
        f = self._tab_frames["Scores"]
        top = ctk.CTkFrame(f, fg_color="transparent")
        top.pack(fill="both", expand=True)

        left = self._card(top)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._heading(left, text="Recent Finals", size=14,
                      text_color=self._ct["TEAL"]).pack(
                          anchor="w", padx=14, pady=(10, 4))
        tf1 = ctk.CTkFrame(left, fg_color="transparent")
        tf1.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.recent_tree = self._make_tree(tf1, {
            "date": ("Date", 90), "away": ("Away", 170),
            "score": ("Final", 80), "home": ("Home", 170),
        })

        right = self._card(top)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._heading(right, text="Upcoming", size=14,
                      text_color=self._ct["GOLD"]).pack(
                          anchor="w", padx=14, pady=(10, 4))
        tf2 = ctk.CTkFrame(right, fg_color="transparent")
        tf2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.upcoming_tree = self._make_tree(tf2, {
            "date": ("Date", 90), "away": ("Away", 170),
            "at": ("", 40), "home": ("Home", 170),
        })
        self.scores_status = self._body(f, text="", dim=True, size=11)
        self.scores_status.pack(anchor="w", pady=(6, 0))

    def refresh_scores_tab(self):
        try:
            import ahl_league as _al
            league = self._league()
            for tree in (self.recent_tree, self.upcoming_tree):
                for item in tree.get_children():
                    tree.delete(item)
            if league is None:
                return
            teams = _al.ahl_team_list(league)
            recent = _al.get_ahl_recent_results(league, n=20)
            for r in recent:
                try:
                    hn = _al._tname(teams, r["home"])
                    an = _al._tname(teams, r["away"])
                    hs, aws = r["home_score"], r["away_score"]
                    final = f"{aws} \u2013 {hs}"
                    if r.get("ot"):
                        final += " (OT)"
                    self.recent_tree.insert("", "end", values=(
                        r.get("date", "")[5:], an, final, hn))
                except Exception:
                    continue
            upcoming = _al.get_ahl_upcoming(league, self._current_date(),
                                            n=20)
            for g in upcoming:
                try:
                    self.upcoming_tree.insert("", "end", values=(
                        g.get("date", "")[5:], g.get("away_name", ""),
                        "@", g.get("home_name", "")))
                except Exception:
                    continue
            self.scores_status.configure(
                text=f"{len(recent)} recent finals \u2014 "
                     f"{len(upcoming)} games upcoming.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Calder Cup tab
    # ------------------------------------------------------------------
    def _build_calder_tab(self):
        f = self._tab_frames["Calder Cup"]
        card = self._card(f)
        card.pack(fill="both", expand=True)
        self._heading(card, text="Calder Cup Playoffs", size=14,
                      text_color=self._ct["GOLD"]).pack(
                          anchor="w", padx=14, pady=(10, 4))
        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.calder_body = scroll
        self.calder_status = self._body(card, text="", dim=True, size=11)
        self.calder_status.pack(anchor="w", padx=14, pady=(0, 8))

    def refresh_calder_tab(self):
        try:
            import ahl_league as _al
            for w in self.calder_body.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
            league = self._league()
            if league is None:
                return
            teams = _al.ahl_team_list(league)
            bracket = getattr(league, "ahl_bracket", None)
            champs = getattr(league, "ahl_champions", None) or []

            if isinstance(bracket, dict) and bracket.get("rounds"):
                season = bracket.get("season", "")
                self._heading(self.calder_body,
                              text=f"Bracket \u2014 {season}",
                              size=13,
                              text_color=self._ct["TEAL"]).pack(
                                  anchor="w", padx=8, pady=(4, 8))
                round_names = ["First Round", "Second Round",
                               "Conference Finals", "Calder Cup Final"]
                for ri, rnd in enumerate(bracket["rounds"]):
                    rname = (round_names[ri] if ri < len(round_names)
                             else f"Round {ri + 1}")
                    self._body(self.calder_body, text=rname,
                               size=12).pack(anchor="w", padx=8,
                                             pady=(8, 2))
                    for s in rnd:
                        try:
                            hn = _al._tname(teams, s["home"])
                            an = _al._tname(teams, s["away"])
                            w = _al._tname(teams, s["winner"])
                            gp = s.get("games", 0)
                            line = (f"{an} vs {hn} \u2014 "
                                    f"{w} wins{'' if not gp else f' in {gp}'}")
                            row = ctk.CTkFrame(self.calder_body,
                                               fg_color=self._ct["PANEL"],
                                               corner_radius=6)
                            row.pack(fill="x", padx=8, pady=2)
                            self._body(row, text=line, size=11).pack(
                                anchor="w", padx=10, pady=6)
                        except Exception:
                            continue
                champ = bracket.get("champion_idx")
                if champ is not None:
                    try:
                        cn = _al._tname(teams, champ)
                        self._heading(
                            self.calder_body,
                            text=f"\U0001f3c6 {cn} \u2014 Calder Cup "
                                 f"Champions",
                            size=14,
                            text_color=self._ct["GOLD"]).pack(
                                anchor="w", padx=8, pady=(12, 4))
                    except Exception:
                        pass

            # Champion history
            if champs:
                self._heading(self.calder_body, text="Past Champions",
                              size=13,
                              text_color=self._ct["TEAL"]).pack(
                                  anchor="w", padx=8, pady=(12, 4))
                for c in reversed(champs[-8:]):
                    try:
                        line = (f"{c.get('season', '')}: "
                                f"{c.get('champion', '')} def. "
                                f"{c.get('runner_up', '')}")
                        self._body(self.calder_body, text=line,
                                   dim=True, size=11).pack(
                                       anchor="w", padx=8, pady=1)
                    except Exception:
                        continue
            if not (isinstance(bracket, dict) and bracket.get("rounds")) \
                    and not champs:
                self._body(self.calder_body,
                           text="No Calder Cup played yet \u2014 the "
                                "playoffs run when the AHL regular season "
                                "ends.",
                           dim=True, size=11).pack(anchor="w", padx=8,
                                                   pady=8)
            self.calder_status.configure(
                text="Top 16 by points \u2014 best-of-5 series.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Team tab
    # ------------------------------------------------------------------
    def _build_team_tab(self):
        f = self._tab_frames["Team"]
        card = self._card(f)
        card.pack(fill="both", expand=True)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        self.team_title = self._heading(top, text="Select a team", size=14,
                                       text_color=self._ct["TEAL"])
        self.team_title.pack(side="left")
        self.team_picker = ctk.CTkComboBox(
            top, values=[], width=220,
            command=lambda _v: self._on_team_picked(),
            fg_color=self._ct["PANEL"], border_color=self._ct["BORDER"],
            button_color=self._ct["CARD"],
            button_hover_color=self._ct["TEAL"],
            text_color=self._ct["TEXT"],
            dropdown_fg_color=self._ct["PANEL"],
            dropdown_text_color=self._ct["TEXT"],
            font=(self._ff, 11))
        self.team_picker.pack(side="right")

        mid = ctk.CTkFrame(card, fg_color="transparent")
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        left = self._card(mid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._heading(left, text="Roster", size=13,
                      text_color=self._ct["TEAL"]).pack(
                          anchor="w", padx=14, pady=(8, 4))
        tf1 = ctk.CTkFrame(left, fg_color="transparent")
        tf1.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.team_roster_tree = self._make_tree(tf1, {
            "player": ("Player", 160), "pos": ("Pos", 44),
            "age": ("Age", 40), "ovr": ("OVR", 44),
            "gp": ("GP", 40), "g": ("G", 36), "a": ("A", 36),
            "pts": ("PTS", 44),
        })

        right = self._card(mid)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._heading(right, text="Upcoming Games", size=13,
                      text_color=self._ct["GOLD"]).pack(
                          anchor="w", padx=14, pady=(8, 4))
        tf2 = ctk.CTkFrame(right, fg_color="transparent")
        tf2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.team_sched_tree = self._make_tree(tf2, {
            "date": ("Date", 90), "opp": ("Opponent", 180),
            "where": ("", 50),
        })
        self.team_status = self._body(card, text="", dim=True, size=11)
        self.team_status.pack(anchor="w", padx=14, pady=(0, 8))

    def _team_names(self):
        try:
            import ahl_league as _al
            teams = self._ahl_teams()
            return [(i, _al._tname(teams, i)) for i in range(len(teams))]
        except Exception:
            return []

    def _on_team_picked(self):
        try:
            name = self.team_picker.get()
            for i, n in self._team_names():
                if n == name:
                    self._selected_ahl_idx = i
                    break
            self.refresh_team_tab()
        except Exception:
            pass

    def refresh_team_tab(self):
        try:
            import ahl_league as _al
            names = self._team_names()
            try:
                self.team_picker.configure(values=[n for _, n in names])
            except Exception:
                pass
            # default to the user's farm club
            if self._selected_ahl_idx is None:
                self._selected_ahl_idx = self._user_farm_idx()
            if self._selected_ahl_idx is None and names:
                self._selected_ahl_idx = names[0][0]
            if self._selected_ahl_idx is None:
                return
            idx = self._selected_ahl_idx
            teams = self._ahl_teams()
            if not (0 <= idx < len(teams)):
                return
            team = teams[idx]
            tname = _al._tname(teams, idx)
            try:
                self.team_picker.set(tname)
                self.team_title.configure(text=tname)
            except Exception:
                pass

            # record line
            try:
                rows = dict(_al.get_ahl_standings(self._league()))
                rec = rows.get(idx, {})
                line = (f"{int(rec.get('w', 0))}-"
                        f"{int(rec.get('l', 0))}-"
                        f"{int(rec.get('otl', 0))} \u2014 "
                        f"{int(rec.get('pts', 0))} PTS")
            except Exception:
                line = ""

            # roster (live alias of the parent NHL club's ahl_roster)
            for item in self.team_roster_tree.get_children():
                self.team_roster_tree.delete(item)
            roster = _al.get_ahl_roster(team)
            n = 0
            for p in roster or []:
                try:
                    nm = (getattr(p, "full_name", None)
                          or getattr(p, "name", "Unknown"))
                    try:
                        pos = str(p.primary_position.value)
                    except Exception:
                        pos = str(getattr(p, "primary_position", ""))[:2]
                    try:
                        ovr = int(p.overall_rating())
                    except Exception:
                        ovr = ""
                    led = getattr(p, "ahl_stats", None)
                    gp = g = a = 0
                    if led is not None:
                        gp = getattr(led, "games_played", 0) or 0
                        g = getattr(led, "goals", 0) or 0
                        a = getattr(led, "assists", 0) or 0
                    self.team_roster_tree.insert("", "end", values=(
                        nm, pos, getattr(p, "age", ""), ovr, gp, g, a,
                        g + a))
                    n += 1
                except Exception:
                    continue

            # upcoming schedule
            for item in self.team_sched_tree.get_children():
                self.team_sched_tree.delete(item)
            sched = _al.get_ahl_team_schedule(self._league(), idx,
                                              self._current_date(), n=12)
            for g in sched:
                try:
                    self.team_sched_tree.insert("", "end", values=(
                        g.get("date", "")[5:], g.get("opponent", ""),
                        "vs" if g.get("home") else "@"))
                except Exception:
                    continue
            parent = getattr(team, "parent_team", None)
            affil = getattr(parent, "team_name", "") if parent else ""
            self.team_status.configure(
                text=f"{line} \u2014 {n} players on the farm"
                     + (f" \u2014 NHL affiliate: {affil}" if affil else ""))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Prospects tab (farm leaders -- mirrors AHLStatsView data)
    # ------------------------------------------------------------------
    def _build_prospects_tab(self):
        f = self._tab_frames["Prospects"]
        top_row = ctk.CTkFrame(f, fg_color="transparent")
        top_row.pack(fill="both", expand=True, pady=(0, 10))

        left = self._card(top_row)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._heading(left, text="Top Scorers", size=13,
                      text_color=self._ct["TEAL"]).pack(
                          anchor="w", padx=14, pady=(8, 4))
        tf1 = ctk.CTkFrame(left, fg_color="transparent")
        tf1.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.pros_scorers = self._make_tree(tf1, {
            "rank": ("#", 32), "player": ("Player", 140),
            "team": ("Farm", 120), "pos": ("Pos", 40),
            "gp": ("GP", 40), "g": ("G", 36), "a": ("A", 36),
            "pts": ("PTS", 44),
        })

        right = self._card(top_row)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._heading(right, text="Who's Cooking (min 10 GP)", size=13,
                      text_color=self._ct["GOLD"]).pack(
                          anchor="w", padx=14, pady=(8, 4))
        tf2 = ctk.CTkFrame(right, fg_color="transparent")
        tf2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.pros_cooking = self._make_tree(tf2, {
            "rank": ("#", 32), "player": ("Player", 140),
            "team": ("Farm", 120), "gp": ("GP", 40),
            "pts": ("PTS", 44), "ppg": ("P/GP", 52),
        })

        gcard = self._card(f)
        gcard.pack(fill="both", expand=True)
        self._heading(gcard, text="Top Goalies (min 5 GP)", size=13,
                      text_color=self._ct["TEAL"]).pack(
                          anchor="w", padx=14, pady=(8, 4))
        tf3 = ctk.CTkFrame(gcard, fg_color="transparent")
        tf3.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.pros_goalies = self._make_tree(tf3, {
            "rank": ("#", 32), "player": ("Player", 140),
            "team": ("Farm", 120), "gp": ("GP", 40),
            "w": ("W", 36), "gaa": ("GAA", 52), "svp": ("SV%", 56),
        })
        self.pros_status = self._body(f, text="", dim=True, size=11)
        self.pros_status.pack(anchor="w", pady=(6, 0))

    def refresh_prospects_tab(self):
        try:
            import ahl_system as _ahl
            for tree in (self.pros_scorers, self.pros_cooking,
                         self.pros_goalies):
                for item in tree.get_children():
                    tree.delete(item)
            league = self._league()
            if league is None:
                return

            class _FakeLeague:
                def __init__(self, teams):
                    self.teams = teams

            gm = getattr(self.app, "game_manager", self.app)
            teams = list(getattr(league, "teams", None) or [])
            farm = _FakeLeague(teams)
            skaters = _ahl.top_skaters(farm, limit=20)
            cooks = _ahl.cooking(farm, limit=12)
            goalies = _ahl.top_goalies(farm, limit=12)

            def _pname(p):
                return (getattr(p, "full_name", None)
                        or getattr(p, "name", None) or "Unknown")

            def _pos(p):
                try:
                    return str(p.primary_position.value)
                except Exception:
                    return str(getattr(p, "primary_position", ""))[:2]

            for i, (p, tname, led) in enumerate(skaters, 1):
                try:
                    self.pros_scorers.insert("", "end", values=(
                        i, _pname(p), tname, _pos(p), led.games_played,
                        led.goals, led.assists,
                        led.goals + led.assists))
                except Exception:
                    continue
            for i, (p, tname, led, ppg) in enumerate(cooks, 1):
                try:
                    self.pros_cooking.insert("", "end", values=(
                        i, _pname(p), tname, led.games_played,
                        led.goals + led.assists, f"{ppg:.2f}"))
                except Exception:
                    continue
            for i, (p, tname, led) in enumerate(goalies, 1):
                try:
                    svp = getattr(led, "save_percentage", 0) or 0
                    self.pros_goalies.insert("", "end", values=(
                        i, _pname(p), tname, led.games_played, led.wins,
                        f"{getattr(led, 'goals_against_avg', 0) or 0:.2f}",
                        f"{svp:.3f}"[1:] if led.shots_against else "\u2014"))
                except Exception:
                    continue
            self.pros_status.configure(
                text=f"{len(skaters)} skaters with AHL games \u2014 "
                     f"minors only, NHL numbers never appear here.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # refresh all
    # ------------------------------------------------------------------
    def refresh_all(self):
        for fn in (self.refresh_standings_tab, self.refresh_scores_tab,
                   self.refresh_calder_tab, self.refresh_team_tab,
                   self.refresh_prospects_tab):
            try:
                fn()
            except Exception:
                continue
