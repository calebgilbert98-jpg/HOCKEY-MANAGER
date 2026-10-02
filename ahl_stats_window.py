# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""AHL Stats screen -- the minors' own home, completely separate from NHL numbers.

Muck's rule: AHL stats must never bleed into the NHL league-stats screen,
and NHL stats must never bleed in here. This view reads ONLY
``player.ahl_stats`` from ``team.ahl_roster`` across the league -- the NHL
``stats`` / ``playoff_stats`` ledgers are never touched.

Deliberately light (no AHL standings/schedules saved anywhere): three
tables answering "who's cooking on the farm" -- top scorers, best
points-per-game, top goalies -- computed on the fly from the per-player
ledger that ahl_system generates each simmed day.
"""

import tkinter as tk

import customtkinter as ctk


class AHLStatsView(ctk.CTkFrame):
    """Full-screen view: AHL scoring leaders, who's cooking, goalie leaders."""

    def __init__(self, parent, app=None):
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
        )
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE)
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
        self.team_choice = tk.StringVar(value="All Farms")
        self._build()
        self.refresh_view()
        try:
            self.app.open_windows["ahl_stats"] = self
        except Exception:
            pass

    # ------------------------------------------------------------------
    # chrome
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        style = tk.ttk.Style(self)
        ct = self._ct
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("AHL.Treeview", background=ct["CARD"],
                        fieldbackground=ct["CARD"], foreground=ct["TEXT"],
                        rowheight=24, borderwidth=0, font=(self._ff, 10))
        style.configure("AHL.Treeview.Heading", background=ct["PANEL"],
                        foreground=ct["TEXT_DIM"], font=(self._ff, 10, "bold"),
                        borderwidth=0)
        style.map("AHL.Treeview",
                  background=[("selected", ct["TEAL"])],
                  foreground=[("selected", ct["BG"])])

    def _card(self, parent, **kw):
        ct = self._ct
        return ctk.CTkFrame(parent, fg_color=ct["CARD"], corner_radius=10,
                            border_width=1, border_color=ct["BORDER"], **kw)

    def _make_tree(self, parent, columns):
        import tkinter.ttk as ttk
        tree = ttk.Treeview(parent, columns=list(columns.keys()),
                            show="headings", height=12,
                            style="AHL.Treeview")
        for key, (label, width) in columns.items():
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center", stretch=False)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        # EHM/FM24: right-click a player row -> player context menu.
        # Rows resolve through app.tree_maps (registered in refresh_view).
        try:
            self.app._bind_player_context_menu(tree, 'ahl', False)
        except Exception:
            pass
        return tree

    def _reg_tree_map(self, tree):
        """Fresh item->player map for a tree; returns the map (or None)."""
        try:
            tm = self.app.tree_maps.setdefault(tree, {})
            tm.clear()
            return tm
        except Exception:
            return None

    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build(self):
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct["BG"], corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        title_card = self._card(main)
        title_card.pack(fill="x", pady=(0, 12))
        row = ctk.CTkFrame(title_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)
        self._heading(row, text="AHL Stats \u2014 Farm Leaders",
                      size=20).pack(side="left")
        self._body(row, text="Minors only \u2014 NHL numbers never appear here",
                   dim=True, size=11).pack(side="left", padx=(12, 0))

        filt = ctk.CTkFrame(row, fg_color="transparent")
        filt.pack(side="right")
        self._body(filt, text="Farm:", dim=True, size=11).pack(
            side="left", padx=(0, 6))
        ctk.CTkComboBox(filt, variable=self.team_choice,
                        values=["All Farms", "My Farm Team"],
                        command=lambda _v: self.refresh_view(),
                        width=140, fg_color=ct["PANEL"],
                        border_color=ct["BORDER"], button_color=ct["CARD"],
                        button_hover_color=ct["TEAL"], text_color=ct["TEXT"],
                        dropdown_fg_color=ct["PANEL"],
                        dropdown_text_color=ct["TEXT"],
                        font=(self._ff, 11)).pack(side="left", padx=(0, 12))
        self._secondary_button(filt, text="Refresh",
                               command=self.refresh_view).pack(side="left",
                                                               padx=(0, 6))
        self._secondary_button(filt, text="Close",
                               command=self.close_view).pack(side="left")

        body = ctk.CTkFrame(main, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # Top scorers (left) + Who's cooking (right)
        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.pack(fill="both", expand=True, pady=(0, 12))

        left = self._card(top_row)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._heading(left, text="Top Scorers", size=14,
                      text_color=ct["TEAL"]).pack(anchor="w", padx=14,
                                                 pady=(10, 4))
        tf1 = ctk.CTkFrame(left, fg_color="transparent")
        tf1.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scorers_tree = self._make_tree(tf1, {
            "rank": ("#", 36), "player": ("Player", 150),
            "team": ("Farm", 130), "pos": ("Pos", 44),
            "age": ("Age", 40), "gp": ("GP", 42), "g": ("G", 40),
            "a": ("A", 40), "pts": ("PTS", 48), "ppg": ("P/GP", 52),
        })

        right = self._card(top_row)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._heading(right, text="Who's Cooking \u2014 Best P/GP (min 10 GP)",
                      size=14, text_color=ct["GOLD"]).pack(
                          anchor="w", padx=14, pady=(10, 4))
        tf2 = ctk.CTkFrame(right, fg_color="transparent")
        tf2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.cooking_tree = self._make_tree(tf2, {
            "rank": ("#", 36), "player": ("Player", 150),
            "team": ("Farm", 130), "pos": ("Pos", 44),
            "age": ("Age", 40), "gp": ("GP", 42), "pts": ("PTS", 48),
            "ppg": ("P/GP", 52),
        })

        # Goalies (bottom)
        gcard = self._card(body)
        gcard.pack(fill="both", expand=True)
        self._heading(gcard, text="Top Goalies (min 5 GP)", size=14,
                      text_color=ct["TEAL"]).pack(anchor="w", padx=14,
                                                 pady=(10, 4))
        tf3 = ctk.CTkFrame(gcard, fg_color="transparent")
        tf3.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.goalies_tree = self._make_tree(tf3, {
            "rank": ("#", 36), "player": ("Player", 150),
            "team": ("Farm", 130), "gp": ("GP", 42), "w": ("W", 40),
            "l": ("L", 40), "gaa": ("GAA", 52), "svp": ("SV%", 56),
            "so": ("SO", 40),
        })

        self.status_label = self._body(main, text="", dim=True, size=11)
        self.status_label.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # data (minors ONLY -- ahl_roster + ahl_stats, never NHL ledgers)
    # ------------------------------------------------------------------
    def _farm_teams(self):
        league = getattr(getattr(self.app, "game_manager", self.app),
                         "league", None)
        teams = list(getattr(league, "teams", None) or [])
        if self.team_choice.get() == "My Farm Team":
            mine = getattr(getattr(self.app, "game_manager", self.app),
                           "user_team", None)
            mname = getattr(mine, "team_name", None)
            teams = [t for t in teams if getattr(t, "team_name", None) == mname]
        return teams

    @staticmethod
    def _is_goalie(p):
        try:
            return p.primary_position.value == "G"
        except Exception:
            return str(getattr(p, "primary_position", "")).upper().endswith(
                "GOALIE")

    @staticmethod
    def _ledger(p):
        led = getattr(p, "ahl_stats", None)
        if led is None:
            try:
                import ahl_system as _ahl
                led = _ahl.ensure_ahl_stats(p)
            except Exception:
                led = None
        return led

    def _pname(self, p):
        return (getattr(p, "full_name", None) or getattr(p, "name", None)
                or "Unknown")

    def _pos(self, p):
        try:
            return str(p.primary_position.value)
        except Exception:
            return str(getattr(p, "primary_position", ""))[:2]

    def refresh_view(self):
        """Recompute all three tables from the farm ledgers."""
        try:
            import ahl_system as _ahl
            league = getattr(getattr(self.app, "game_manager", self.app),
                             "league", None)
            for tree in (self.scorers_tree, self.cooking_tree,
                         self.goalies_tree):
                for item in tree.get_children():
                    tree.delete(item)
            _sm = self._reg_tree_map(self.scorers_tree)
            _cm = self._reg_tree_map(self.cooking_tree)
            _gm = self._reg_tree_map(self.goalies_tree)
            if league is None:
                self.status_label.configure(
                    text="No league loaded yet.")
                return

            farm = _FakeLeague(self._farm_teams())
            skaters = _ahl.top_skaters(farm, limit=25)
            cooks = _ahl.cooking(farm, limit=15)
            goalies = _ahl.top_goalies(farm, limit=15)

            for i, (p, tname, led) in enumerate(skaters, 1):
                pts = led.goals + led.assists
                gp = max(1, led.games_played)
                _iid = self.scorers_tree.insert("", "end", values=(
                    i, self._pname(p), tname, self._pos(p),
                    getattr(p, "age", ""), led.games_played, led.goals,
                    led.assists, pts, f"{pts / gp:.2f}"))
                if _sm is not None:
                    _sm[_iid] = p

            for i, (p, tname, led, ppg) in enumerate(cooks, 1):
                _iid = self.cooking_tree.insert("", "end", values=(
                    i, self._pname(p), tname, self._pos(p),
                    getattr(p, "age", ""), led.games_played,
                    led.goals + led.assists, f"{ppg:.2f}"))
                if _cm is not None:
                    _cm[_iid] = p

            for i, (p, tname, led) in enumerate(goalies, 1):
                svp = getattr(led, "save_percentage", 0) or 0
                _iid = self.goalies_tree.insert("", "end", values=(
                    i, self._pname(p), tname, led.games_played, led.wins,
                    led.losses,
                    f"{getattr(led, 'goals_against_avg', 0) or 0:.2f}",
                    f"{svp:.3f}"[1:] if led.shots_against else "\u2014",
                    led.shutouts))
                if _gm is not None:
                    _gm[_iid] = p

            n_skaters = len(skaters)
            if n_skaters == 0:
                self.status_label.configure(
                    text="No AHL games logged yet \u2014 farm stats "
                         "accumulate as the season sims.")
            else:
                scope = ("your farm team" if self.team_choice.get()
                         == "My Farm Team" else "all 32 farms")
                self.status_label.configure(
                    text=f"{n_skaters} skaters with AHL games \u2014 "
                         f"{scope} \u2014 NHL numbers never appear here.")
        except Exception as e:
            print(f"Error refreshing AHL stats view: {e}")


class _FakeLeague:
    """Tiny adapter so ahl_system helpers run over a filtered team list."""

    def __init__(self, teams):
        self.teams = teams
