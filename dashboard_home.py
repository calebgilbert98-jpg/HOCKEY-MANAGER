# dashboard_home.py
# Puck Dynasty home dashboard.
# Dense, information-rich GM dashboard: team header, stat strip, standings
# (with scope dropdown), team leaders (with category dropdown), schedule
# (with view dropdown), next game, injuries, inbox, and quick actions.
# All cards navigate to their full windows. update_data() performs a real
# refresh that preserves dropdown selections.

import tkinter as tk
from tkinter import ttk
from datetime import datetime

from modern_ui import (
    AppColors, AppFonts, AppCard, StatCard,
    PlayerRow, PillBadge, AppButton, apply_app_theme,
)

try:
    from manager_career import morale_label
except Exception:
    def morale_label(m):  # fallback if career module is unavailable
        return {9: "Superb", 8: "Superb", 7: "Good", 6: "Good",
                5: "Okay", 4: "Okay", 3: "Poor", 2: "Poor"}.get(int(m), "Abysmal")


class AppDropdown(ttk.Combobox):
    """Themed dropdown (combobox) matching the dark UI.

    Use for view selectors (standings scope, leader category, schedule view).
    """

    def __init__(self, parent, values, initial=None, on_select=None, width=16):
        self._var = tk.StringVar(value=initial or (values[0] if values else ""))
        super().__init__(parent, textvariable=self._var, values=list(values),
                         state="readonly", width=width,
                         font=AppFonts.SMALL)
        self._on_select = on_select
        self.bind("<<ComboboxSelected>>", self._handle_select)
        self._style()

    def _style(self):
        style = ttk.Style()
        # Unique style name per instance to avoid clashes
        name = f"AppDropdown_{id(self)}.TCombobox"
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(name,
                        fieldbackground=AppColors.BG_ELEVATED,
                        background=AppColors.BG_ELEVATED,
                        foreground=AppColors.TEXT_PRIMARY,
                        arrowcolor=AppColors.TEXT_SECONDARY,
                        bordercolor=AppColors.BORDER,
                        lightcolor=AppColors.BORDER,
                        darkcolor=AppColors.BORDER,
                        padding=6)
        style.map(name,
                  fieldbackground=[("readonly", AppColors.BG_ELEVATED),
                                   ("disabled", AppColors.BG)],
                  foreground=[("readonly", AppColors.TEXT_PRIMARY)],
                  background=[("readonly", AppColors.BG_HOVER)],
                  arrowcolor=[("readonly", AppColors.ACCENT)])
        self.configure(style=name)
        # Dropdown list colors
        try:
            self.tk.call("ttk::combobox::PopdownWindow", self)
        except Exception:
            pass
        option = f"{self}._popdown.f.l"
        try:
            self.tk.call(option, "configure", "-background", AppColors.BG_ELEVATED,
                         "-foreground", AppColors.TEXT_PRIMARY,
                         "-selectbackground", AppColors.ACCENT_BG,
                         "-selectforeground", AppColors.TEXT_PRIMARY)
        except Exception:
            pass

    def _handle_select(self, _event=None):
        if self._on_select:
            self._on_select(self._var.get())

    def get_value(self):
        return self._var.get()

    def set_value(self, value):
        self._var.set(value)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class HomeDashboard:
    """Information-dense home dashboard for Puck Dynasty."""

    STANDINGS_SCOPES = ["Division", "Conference", "League"]
    LEADER_CATS = ["Points", "Goals", "Assists", "+/-", "PIM", "Hits", "Shots"]
    SCHEDULE_VIEWS = ["Upcoming", "Results"]

    def __init__(self, parent, game_manager, user_team, on_continue=None):
        self.parent = parent
        self.game_manager = game_manager
        self.user_team = user_team
        self.on_continue = on_continue
        # Preserved across refreshes
        self._standings_scope = "Division"
        self._leaders_cat = "Points"
        self._schedule_view = "Upcoming"
        self._container = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_dashboard(self, container):
        """Build (or rebuild) the dashboard inside container."""
        self._container = container
        self._section_anchors = {}
        self._canvas = None
        for widget in container.winfo_children():
            widget.destroy()

        main = tk.Frame(container, bg=AppColors.BG)
        main.pack(fill="both", expand=True)

        canvas = tk.Canvas(main, bg=AppColors.BG, highlightthickness=0)
        self._canvas = canvas
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=AppColors.BG)
        scrollable.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # Tag the inner window so we can resize it with the canvas --
        # without this the content stays at its requested width and the
        # right side of the screen is dead space.
        canvas.create_window((0, 0), window=scrollable, anchor="nw",
                             tags="dashboard_inner")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig("dashboard_inner", width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling
        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        content = tk.Frame(scrollable, bg=AppColors.BG)
        content.pack(fill="both", expand=True, padx=24, pady=20)

        self._create_header(content)
        self._create_stat_strip(content)
        self._create_section_nav(content)
        self._create_main_grid(content)
        return main

    def _create_section_nav(self, parent):
        """Jump-to nav pills: scrolls to each dashboard section."""
        nav = tk.Frame(parent, bg=AppColors.BG)
        nav.pack(fill="x", pady=(0, 18))

        tk.Label(nav, text="Jump to:", font=AppFonts.SMALL_BOLD,
                 fg=AppColors.TEXT_TERTIARY, bg=AppColors.BG).pack(side="left", padx=(0, 8))

        sections = [
            ("Standings", "standings"),
            ("Team Leaders", "leaders"),
            ("Schedule", "schedule"),
            ("Next Game", "next_game"),
            ("Injuries", "injuries"),
            ("Morale", "morale"),
            ("Prospects", "prospects"),
            ("Milestones", "milestones"),
            ("Inbox", "inbox"),
        ]
        for label, key in sections:
            pill = tk.Label(nav, text=label, font=AppFonts.SMALL_BOLD,
                            fg=AppColors.TEXT_SECONDARY, bg=AppColors.BG_ELEVATED,
                            padx=12, pady=6, cursor="hand2")
            pill.pack(side="left", padx=4)
            pill.bind("<Button-1>", lambda _e, k=key: self._scroll_to(k))
            pill.bind("<Enter>", lambda e: e.widget.config(fg=AppColors.ACCENT))
            pill.bind("<Leave>", lambda e: e.widget.config(fg=AppColors.TEXT_SECONDARY))

    def _scroll_to(self, key):
        """Scroll the dashboard canvas so the named card is at the top."""
        if not self._canvas:
            return
        widget = self._section_anchors.get(key)
        if widget is None or not widget.winfo_exists():
            return
        try:
            self._canvas.update_idletasks()
            total = self._canvas.bbox("all")
            if not total:
                return
            y = widget.winfo_rooty() - self._canvas.winfo_rooty()
            frac = max(0.0, min(1.0, y / max(total[3], 1)))
            self._canvas.yview_moveto(frac)
        except Exception:
            pass

    def update_data(self, current_date=None, team_record=None,
                    next_game=None, roster_highlights=None, recent_news=None):
        """Real refresh: rebuild the dashboard, preserving dropdown state.

        Accepts the same kwargs as before for compatibility; the dashboard
        reads live from game_manager/user_team so kwargs are informational.
        """
        if self._container is not None:
            self.create_dashboard(self._container)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------
    def _nav(self, method_name):
        """Open a main-window screen if available."""
        fn = getattr(self.parent, method_name, None)
        if callable(fn):
            try:
                fn()
            except Exception as e:
                print(f"Dashboard nav {method_name} failed: {e}")

    def _link(self, parent, text, method_name):
        """Small accent 'view all' link."""
        lbl = tk.Label(parent, text=text, font=AppFonts.SMALL_BOLD,
                       fg=AppColors.ACCENT, bg=parent.cget("bg") if self._has_bg(parent) else AppColors.BG_ELEVATED,
                       cursor="hand2")
        lbl.bind("<Button-1>", lambda _e: self._nav(method_name))
        return lbl

    @staticmethod
    def _has_bg(widget):
        try:
            widget.cget("bg")
            return True
        except Exception:
            return False

    def _card_title_row(self, content, title, link_text=None, link_method=None):
        row = tk.Frame(content, bg=content.cget("bg"))
        row.pack(fill="x", pady=(0, 10))
        tk.Label(row, text=title, font=AppFonts.H2,
                 fg=AppColors.TEXT_PRIMARY, bg=row.cget("bg")).pack(side="left")
        if link_text and link_method:
            self._link(row, link_text, link_method).pack(side="right")
        return row

    def _card_header_with_dropdown(self, content, title, dropdown_label,
                                   values, initial, on_select):
        """Card header: big title on row 1, labeled dropdown toolbar on row 2.

        The explicit label (e.g. 'Scope:', 'Sort by:') makes the dropdown
        discoverable instead of a bare combobox in the corner.
        """
        bg = content.cget("bg")
        tk.Label(content, text=title, font=AppFonts.H2,
                 fg=AppColors.TEXT_PRIMARY, bg=bg).pack(anchor="w", pady=(0, 8))
        toolbar = tk.Frame(content, bg=bg)
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Label(toolbar, text=dropdown_label, font=AppFonts.SMALL_BOLD,
                 fg=AppColors.TEXT_SECONDARY, bg=bg).pack(side="left", padx=(0, 8))
        dd = AppDropdown(toolbar, values, initial=initial,
                         on_select=on_select, width=18)
        dd.pack(side="left")
        return dd

    def _view_all_button(self, content, text, method_name):
        """Full-width button at the bottom of a card linking to the full window."""
        btn = AppButton(content, text=text, style="secondary",
                        command=lambda: self._nav(method_name),
                        width=200, height=36)
        btn.pack(fill="x", pady=(12, 0))
        return btn

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _league_teams(self):
        gm = self.game_manager
        league = getattr(gm, "league", None)
        return list(getattr(league, "teams", []) or [])

    def _team_points(self, team):
        return team.wins * 2 + team.ot_losses

    def _sorted_standings(self, teams):
        return sorted(teams,
                      key=lambda t: (self._team_points(t), t.wins,
                                     getattr(t, "goals_for", 0) - getattr(t, "goals_against", 0)),
                      reverse=True)

    def _standings_teams(self):
        teams = self._league_teams()
        me = self.user_team
        scope = self._standings_scope
        if scope == "Division" and me is not None:
            div = getattr(me, "division", "")
            teams = [t for t in teams if getattr(t, "division", "") == div]
        elif scope == "Conference" and me is not None:
            conf = getattr(me, "conference", "")
            teams = [t for t in teams if getattr(t, "conference", "") == conf]
        return self._sorted_standings(teams)

    def _division_rank(self):
        me = self.user_team
        if me is None:
            return "-"
        div = getattr(me, "division", "")
        teams = [t for t in self._league_teams()
                 if getattr(t, "division", "") == div]
        ordered = self._sorted_standings(teams)
        for i, t in enumerate(ordered, 1):
            if t is me or getattr(t, "team_name", "") == getattr(me, "team_name", ""):
                return f"{i}{self._ordinal(i)}"
        return "-"

    @staticmethod
    def _ordinal(n):
        if 10 <= n % 100 <= 20:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

    def _recent_form(self, n=5):
        """Last n results as W/L/O list from the schedule."""
        results = []
        try:
            sched = getattr(self.game_manager.league, "schedule", []) or []
            me_name = getattr(self.user_team, "team_name", "")
            today = getattr(self.game_manager, "current_date", None)
            for entry in reversed(sched):
                if len(results) >= n:
                    break
                # Schedule entries: (date, home, away) or dicts
                if isinstance(entry, dict):
                    d = entry.get("date")
                    hs, aws = entry.get("home_score"), entry.get("away_score")
                    hn = self._team_name_of(entry.get("home_team"))
                    an = self._team_name_of(entry.get("away_team"))
                elif isinstance(entry, (list, tuple)) and len(entry) >= 3:
                    d, hteam, ateam = entry[0], entry[1], entry[2]
                    hn, an = self._team_name_of(hteam), self._team_name_of(ateam)
                    hs = getattr(entry, "home_score", None) if not isinstance(entry, dict) else None
                    aws = None
                    # tuple schedules rarely carry scores; try attrs on league results
                    hs, aws = self._lookup_result(d, hn, an)
                else:
                    continue
                if hn != me_name and an != me_name:
                    continue
                if hs is None or aws is None:
                    continue
                if today is not None and d is not None and d >= today:
                    continue
                my = hs if hn == me_name else aws
                opp = aws if hn == me_name else hs
                if my > opp:
                    results.append("W")
                elif my == opp:
                    results.append("T")
                else:
                    # Assume OT loss vs regulation loss unknown -> L
                    results.append("L")
        except Exception:
            pass
        return results

    def _lookup_result(self, _d, _hn, _an):
        return None, None

    @staticmethod
    def _team_name_of(obj):
        if obj is None:
            return ""
        return getattr(obj, "team_name", str(obj))

    def _streak_text(self):
        form = self._recent_form(10)
        if not form:
            return "-"
        first = form[0]
        count = 0
        for r in form:
            if r == first:
                count += 1
            else:
                break
        label = {"W": "W", "L": "L", "T": "T"}.get(first, first)
        return f"{label}{count}"

    def _skaters(self):
        try:
            return [p for p in self.user_team.roster
                    if "GOALIE" not in str(getattr(p, "primary_position", ""))]
        except Exception:
            return []

    def _leader_value(self, player, cat):
        s = getattr(player, "stats", None)
        if s is None:
            return 0
        return {
            "Points": getattr(s, "points", s.goals + s.assists),
            "Goals": getattr(s, "goals", 0),
            "Assists": getattr(s, "assists", 0),
            "+/-": getattr(s, "plus_minus", 0),
            "PIM": getattr(s, "penalties_in_minutes", 0),
            "Hits": getattr(s, "hits", 0),
            "Shots": getattr(s, "shots", 0),
        }.get(cat, 0)

    def _top_leaders(self, cat, n=8):
        skaters = self._skaters()
        ranked = sorted(skaters, key=lambda p: self._leader_value(p, cat),
                        reverse=True)
        return ranked[:n]

    def _injured_players(self):
        out = []
        try:
            for p in self.user_team.roster:
                inj = getattr(p, "injury", None)
                if inj:
                    desc = getattr(inj, "description", None) or getattr(inj, "injury_type", "Injured")
                    games = getattr(inj, "games_remaining", getattr(inj, "days_remaining", "?"))
                    out.append((p, desc, games))
                elif getattr(p, "is_injured", False):
                    out.append((p, "Injured", "?"))
        except Exception:
            pass
        return out

    def _next_game(self):
        """Find the next scheduled game involving the user team."""
        try:
            sched = getattr(self.game_manager.league, "schedule", []) or []
            me_name = getattr(self.user_team, "team_name", "")
            today = getattr(self.game_manager, "current_date", None)
            candidates = []
            for entry in sched:
                if isinstance(entry, dict):
                    d = entry.get("date")
                    hn = self._team_name_of(entry.get("home_team"))
                    an = self._team_name_of(entry.get("away_team"))
                    if entry.get("home_score") is not None:
                        continue  # already played
                elif isinstance(entry, (list, tuple)) and len(entry) >= 3:
                    d, hteam, ateam = entry[0], entry[1], entry[2]
                    hn, an = self._team_name_of(hteam), self._team_name_of(ateam)
                else:
                    continue
                if hn != me_name and an != me_name:
                    continue
                if today is not None and d is not None and d < today:
                    continue
                candidates.append((d, hn, an))
            candidates.sort(key=lambda c: (c[0] is None, c[0]))
            return candidates[0] if candidates else None
        except Exception:
            return None

    def _last_results(self, n=5):
        """Most recent completed games involving the user team."""
        out = []
        try:
            # Prefer a results list if the league tracks one
            results = getattr(self.game_manager.league, "results", None) or \
                      getattr(self.game_manager, "results", None) or []
            me_name = getattr(self.user_team, "team_name", "")
            for r in reversed(results):
                if len(out) >= n:
                    break
                if isinstance(r, dict):
                    hn = self._team_name_of(r.get("home_team", r.get("home")))
                    an = self._team_name_of(r.get("away_team", r.get("away")))
                    hs, aws = r.get("home_score"), r.get("away_score")
                    d = r.get("date")
                else:
                    continue
                if hn != me_name and an != me_name or hs is None:
                    continue
                out.append((d, hn, an, hs, aws))
        except Exception:
            pass
        return out

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------
    def _create_header(self, parent):
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 18))

        # Avatar
        avatar_size = 72
        avatar = tk.Canvas(header, width=avatar_size, height=avatar_size,
                           bg=AppColors.BG, highlightthickness=0)
        avatar.pack(side="left")
        team_color = getattr(self.user_team, "primary_color", AppColors.ACCENT)
        if str(team_color).lower() in ("#ffffff", "white"):
            team_color = AppColors.ACCENT
        avatar.create_oval(2, 2, avatar_size - 2, avatar_size - 2,
                           fill=team_color, outline="")
        name = getattr(self.user_team, "team_name", "Team")
        initials = "".join(w[0] for w in name.split()[:2]).upper()
        avatar.create_text(avatar_size // 2, avatar_size // 2, text=initials,
                           font=("Segoe UI", 20, "bold"), fill="white")

        info = tk.Frame(header, bg=AppColors.BG)
        info.pack(side="left", padx=16)
        tk.Label(info, text=name, font=AppFonts.H1,
                 fg=AppColors.TEXT_PRIMARY, bg=AppColors.BG).pack(anchor="w")

        record_frame = tk.Frame(info, bg=AppColors.BG)
        record_frame.pack(anchor="w", pady=(8, 0))
        w = getattr(self.user_team, "wins", 0)
        l = getattr(self.user_team, "losses", 0)
        otl = getattr(self.user_team, "ot_losses", 0)
        PillBadge(record_frame, text=f"{w}-{l}-{otl}",
                  bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).pack(side="left")
        # Streak pill
        streak = self._streak_text()
        PillBadge(record_frame, text=f"Streak {streak}",
                  bg=AppColors.ACCENT_BG, fg=AppColors.ACCENT).pack(side="left", padx=(8, 0))
        # Division rank pill
        PillBadge(record_frame, text=f"{self._division_rank()} in {getattr(self.user_team, 'division', '')}",
                  bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY).pack(side="left", padx=(8, 0))

        # Right: date + continue
        date_frame = tk.Frame(header, bg=AppColors.BG)
        date_frame.pack(side="right")
        try:
            current_date = getattr(self.game_manager, "current_date", None)
            date_str = current_date.strftime("%B %d, %Y")
            day_str = current_date.strftime("%A")
        except Exception:
            date_str = datetime.now().strftime("%B %d, %Y")
            day_str = datetime.now().strftime("%A")
        tk.Label(date_frame, text=date_str, font=AppFonts.BODY_BOLD,
                 fg=AppColors.TEXT_PRIMARY, bg=AppColors.BG).pack(anchor="e")
        tk.Label(date_frame, text=day_str, font=AppFonts.SMALL,
                 fg=AppColors.ACCENT, bg=AppColors.BG).pack(anchor="e")
        AppButton(date_frame, text="Continue", command=self._on_continue,
                  style="primary", width=140, height=40).pack(pady=(12, 0))

    def _create_stat_strip(self, parent):
        strip = tk.Frame(parent, bg=AppColors.BG)
        strip.pack(fill="x", pady=(0, 18))

        t = self.user_team
        gp = max(getattr(t, "games_played", 0), 1)
        gf = getattr(t, "goals_for", 0)
        ga = getattr(t, "goals_against", 0)
        pts = self._team_points(t)
        # Special teams from team stats if tracked
        pp_pct = self._special_teams_pct("power_play_goals", "power_play_opportunities")
        pk_pct = self._special_teams_pct("penalty_kill_goals_against", "penalty_kill_opportunities",
                                         invert=True)

        stats = [
            ("Record", f"{t.wins}-{t.losses}-{t.ot_losses}", f"{gp} GP", AppColors.TEXT_PRIMARY, False),
            ("Points", str(pts), self._division_rank() + " division", AppColors.ACCENT, True),
            ("Goals/Gm", f"{gf / gp:.1f}", "Offense", AppColors.TEXT_PRIMARY, False),
            ("Against/Gm", f"{ga / gp:.1f}", "Defense", AppColors.TEXT_PRIMARY, False),
            ("Power Play", pp_pct, "Conversion", AppColors.TEXT_PRIMARY, False),
            ("Penalty Kill", pk_pct, "Kill rate", AppColors.TEXT_PRIMARY, False),
            ("Streak", self._streak_text(), "Last 10", AppColors.TEXT_PRIMARY, False),
            ("Cap Space", self._cap_space_text(), "Salary cap", AppColors.TEXT_PRIMARY, False),
        ]
        for i, (label, value, caption, color, accent) in enumerate(stats):
            card = StatCard(strip, value=value, label=label, caption=caption,
                            value_color=color, accent_top=accent)
            card.pack(side="left", fill="both", expand=True,
                      padx=(0, 10) if i < len(stats) - 1 else (0, 0))

    def _special_teams_pct(self, goals_key, opps_key, invert=False):
        try:
            ts = self.game_manager.team_stats.get(self.user_team.team_name, {}) \
                if hasattr(self.game_manager, "team_stats") else {}
            g = ts.get(goals_key, 0)
            o = ts.get(opps_key, 0)
            if not o:
                return "-"
            pct = 100.0 * g / o
            return f"{100 - pct:.1f}%" if invert else f"{pct:.1f}%"
        except Exception:
            return "-"

    def _cap_space_text(self):
        try:
            cap = getattr(self.user_team, "salary_cap", 0)
            payroll = sum(getattr(p, "salary", 0) or 0 for p in self.user_team.roster)
            space = (cap - payroll) / 1e6
            return f"${space:.1f}M"
        except Exception:
            return "-"

    def _create_main_grid(self, parent):
        grid = tk.Frame(parent, bg=AppColors.BG)
        grid.pack(fill="both", expand=True)

        # Use grid with weighted columns for a proportional split that
        # scales with window width (roughly 62/38). Pack's side=left/right
        # gives unpredictable widths; grid weights keep both columns
        # filling the available space.
        grid.grid_columnconfigure(0, weight=62)
        grid.grid_columnconfigure(1, weight=38)
        grid.grid_rowconfigure(0, weight=1)

        left = tk.Frame(grid, bg=AppColors.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = tk.Frame(grid, bg=AppColors.BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        self._create_standings_card(left)
        self._create_leaders_card(left)
        self._create_schedule_card(left)

        self._create_next_game_card(right)
        self._create_injuries_card(right)
        self._create_morale_card(right)
        self._create_prospects_card(right)
        self._create_milestones_card(right)
        self._create_inbox_card(right)
        self._create_quick_actions_card(right)

    # ---------------- Standings ----------------
    def _create_standings_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["standings"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")

        self._card_header_with_dropdown(content, "Standings", "Scope:",
                                        self.STANDINGS_SCOPES,
                                        self._standings_scope,
                                        self._on_standings_scope)

        # Table header
        teams = self._standings_teams()
        table = tk.Frame(content, bg=bg)
        table.pack(fill="x")
        cols = [("Team", 22), ("GP", 4), ("W", 4), ("L", 4), ("OTL", 5), ("PTS", 5)]
        hdr = tk.Frame(table, bg=bg)
        hdr.pack(fill="x")
        for text, w in cols:
            tk.Label(hdr, text=text, font=AppFonts.LABEL,
                     fg=AppColors.TEXT_TERTIARY, bg=bg,
                     width=w, anchor="w" if text == "Team" else "center").pack(
                         side="left" if text == "Team" else "right")

        me_name = getattr(self.user_team, "team_name", "")
        for i, tm in enumerate(teams[:8], 1):
            row_bg = AppColors.ACCENT_BG if getattr(tm, "team_name", "") == me_name else bg
            row = tk.Frame(table, bg=row_bg)
            row.pack(fill="x", pady=1)
            fg = AppColors.TEXT_PRIMARY
            tk.Label(row, text=f"{i}. {tm.team_name}", font=AppFonts.SMALL_BOLD,
                     fg=fg, bg=row_bg, width=26, anchor="w").pack(side="left")
            for val, w in [(tm.games_played, 4), (tm.wins, 4), (tm.losses, 4),
                           (tm.ot_losses, 5), (self._team_points(tm), 5)]:
                tk.Label(row, text=str(val), font=AppFonts.SMALL,
                         fg=AppColors.TEXT_SECONDARY, bg=row_bg,
                         width=w, anchor="center").pack(side="right")

        self._view_all_button(content, "View full standings →",
                              "open_stats_standings_window")

    def _on_standings_scope(self, value):
        self._standings_scope = value
        self.update_data()

    # ---------------- Leaders ----------------
    def _create_leaders_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["leaders"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")

        self._card_header_with_dropdown(content, "Team Leaders", "Sort by:",
                                        self.LEADER_CATS, self._leaders_cat,
                                        self._on_leaders_cat)

        leaders = self._top_leaders(self._leaders_cat, 8)
        if not leaders:
            tk.Label(content, text="No skaters yet.", font=AppFonts.SMALL,
                     fg=AppColors.TEXT_TERTIARY, bg=bg).pack(anchor="w")
            return
        for rank, p in enumerate(leaders, 1):
            row = tk.Frame(content, bg=bg)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=str(rank), font=AppFonts.SMALL,
                     fg=AppColors.TEXT_TERTIARY, bg=bg, width=3).pack(side="left")
            name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip() or "Player"
            pos = str(getattr(p, "primary_position", "")).split(".")[-1]
            tk.Label(row, text=f"{name} ({pos})", font=AppFonts.SMALL_BOLD,
                     fg=AppColors.TEXT_PRIMARY, bg=bg, anchor="w").pack(side="left", fill="x", expand=True)
            tk.Label(row, text=str(self._leader_value(p, self._leaders_cat)),
                     font=AppFonts.STAT_SMALL, fg=AppColors.ACCENT,
                     bg=bg).pack(side="right")

        self._view_all_button(content, "View full roster →",
                              "open_roster_window")

    def _on_leaders_cat(self, value):
        self._leaders_cat = value
        self.update_data()

    # ---------------- Schedule ----------------
    def _create_schedule_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["schedule"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")

        self._card_header_with_dropdown(content, "Schedule", "Show:",
                                        self.SCHEDULE_VIEWS, self._schedule_view,
                                        self._on_schedule_view)

        if self._schedule_view == "Upcoming":
            game = self._next_game()
            if game:
                d, hn, an = game
                me = getattr(self.user_team, "team_name", "")
                opp = an if hn == me else hn
                where = "vs" if hn == me else "at"
                date_s = d.strftime("%a %b %d") if hasattr(d, "strftime") else str(d or "TBD")
                tk.Label(content, text=f"{where} {opp}", font=AppFonts.BODY_BOLD,
                         fg=AppColors.TEXT_PRIMARY, bg=bg).pack(anchor="w")
                tk.Label(content, text=date_s, font=AppFonts.SMALL,
                         fg=AppColors.TEXT_SECONDARY, bg=bg).pack(anchor="w", pady=(2, 0))
            else:
                tk.Label(content, text="No upcoming games found.",
                         font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY, bg=bg).pack(anchor="w")
        else:
            results = self._last_results(5)
            if not results:
                tk.Label(content, text="No completed games yet.",
                         font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY, bg=bg).pack(anchor="w")
            for d, hn, an, hs, aws in results:
                me = getattr(self.user_team, "team_name", "")
                opp = an if hn == me else hn
                where = "vs" if hn == me else "at"
                my, opps = (hs, aws) if hn == me else (aws, hs)
                wl = "W" if my > opps else ("L" if my < opps else "T")
                color = AppColors.SUCCESS if wl == "W" else (AppColors.DANGER if wl == "L" else AppColors.TEXT_SECONDARY)
                row = tk.Frame(content, bg=bg)
                row.pack(fill="x", pady=2)
                PillBadge(row, text=wl, bg=color, fg="#ffffff").pack(side="left")
                tk.Label(row, text=f" {where} {opp}  {my}-{opps}",
                         font=AppFonts.SMALL, fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="left")

        self._view_all_button(content, "View full schedule →",
                              "open_schedule_window")

    def _on_schedule_view(self, value):
        self._schedule_view = value
        self.update_data()

    # ---------------- Next game ----------------
    def _create_next_game_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["next_game"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")
        self._card_title_row(content, "Next Game")

        game = self._next_game()
        if not game:
            tk.Label(content, text="No upcoming game scheduled.",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY, bg=bg).pack(anchor="w")
            return
        d, hn, an = game
        me = getattr(self.user_team, "team_name", "")
        opp_name = an if hn == me else hn
        where = "Home" if hn == me else "Away"
        opp = next((t for t in self._league_teams()
                    if getattr(t, "team_name", "") == opp_name), None)
        tk.Label(content, text=f"{'vs' if where == 'Home' else 'at'} {opp_name}",
                 font=AppFonts.H3, fg=AppColors.ACCENT, bg=bg).pack(anchor="w")
        if opp is not None:
            tk.Label(content,
                     text=f"{opp.wins}-{opp.losses}-{opp.ot_losses}  ({self._team_points(opp)} pts)",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY, bg=bg).pack(anchor="w", pady=(4, 0))
        date_s = d.strftime("%A, %B %d") if hasattr(d, "strftime") else str(d or "TBD")
        tk.Label(content, text=f"{date_s} · {where}",
                 font=AppFonts.SMALL, fg=AppColors.TEXT_SECONDARY, bg=bg).pack(anchor="w", pady=(2, 0))
        self._view_all_button(content, "View schedule →",
                              "open_schedule_window")

    # ---------------- Injuries ----------------
    def _create_injuries_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["injuries"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")
        self._card_title_row(content, "Injuries")

        injured = self._injured_players()
        if not injured:
            tk.Label(content, text="No injuries. Squad is healthy.",
                     font=AppFonts.SMALL, fg=AppColors.SUCCESS, bg=bg).pack(anchor="w")
            return
        for p, desc, games in injured[:5]:
            row = tk.Frame(content, bg=bg)
            row.pack(fill="x", pady=2)
            name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
            tk.Label(row, text=name, font=AppFonts.SMALL_BOLD,
                     fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="left")
            tk.Label(row, text=f"{desc} ({games})", font=AppFonts.SMALL,
                     fg=AppColors.DANGER, bg=bg).pack(side="right")
        self._view_all_button(content, "View roster →",
                              "open_roster_window")

    # ---------------- Team morale ----------------
    def _create_morale_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["morale"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")
        self._card_title_row(content, "Team Morale", "Roster →",
                             "open_roster_window")

        roster = list(getattr(self.user_team, "roster", []) or [])
        if not roster:
            tk.Label(content, text="No players on the roster.",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY,
                     bg=bg).pack(anchor="w")
            return

        mor = [getattr(p, "morale", 7) or 7 for p in roster]
        avg = sum(mor) / len(mor)
        label = morale_label(int(round(avg)))

        head = tk.Frame(content, bg=bg)
        head.pack(fill="x")
        tk.Label(head, text=f"{avg:.1f} / 10", font=AppFonts.H2,
                 fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="left")
        tk.Label(head, text=label, font=AppFonts.SMALL_BOLD,
                 fg=AppColors.TEXT_SECONDARY, bg=bg).pack(
                     side="left", padx=(10, 0))

        bar = tk.Frame(content, bg=AppColors.BG, height=10)
        bar.pack(fill="x", pady=(8, 10))
        bar.pack_propagate(False)
        color = (AppColors.SUCCESS if avg >= 7
                 else AppColors.WARNING if avg >= 5
                 else AppColors.DANGER)
        fill = tk.Frame(bar, bg=color, height=10)
        fill.place(relx=0, rely=0, relwidth=max(0.03, min(1.0, avg / 10.0)),
                   relheight=1.0)

        counts = {}
        for m in mor:
            band = morale_label(int(m))
            counts[band] = counts.get(band, 0) + 1
        for band in ("Superb", "Good", "Okay", "Poor", "Abysmal"):
            n = counts.get(band)
            if n:
                row = tk.Frame(content, bg=bg)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=band, font=AppFonts.SMALL,
                         fg=AppColors.TEXT_SECONDARY, bg=bg).pack(side="left")
                tk.Label(row, text=f"{n} players", font=AppFonts.SMALL_BOLD,
                         fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="right")

    # ---------------- Top prospects ----------------
    def _create_prospects_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["prospects"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")
        self._card_title_row(content, "Top Prospects", "Scouting →",
                             "open_scouting_window")

        team = self.user_team
        pool = (list(getattr(team, "prospects", []) or [])
                + list(getattr(team, "ahl_roster", []) or []))
        if not pool:
            tk.Label(content, text="No prospects in the system.",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY,
                     bg=bg).pack(anchor="w")
            return

        ladder = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]

        def pot_rank(p):
            g = str(getattr(p, "potential_grade", "C") or "C").strip().upper()
            return ladder.index(g) if g in ladder else 4

        pool.sort(key=lambda p: (pot_rank(p),
                                 getattr(p, "overall_rating", lambda: 0)()),
                  reverse=True)
        for p in pool[:5]:
            try:
                pos = p.primary_position.name
            except Exception:
                pos = str(getattr(p, "primary_position", "?"))
            name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
            detail = (f"Age {getattr(p, 'age', '?')} · {pos} · "
                      f"OVR {getattr(p, 'overall_rating', lambda: '?')()} · "
                      f"POT {getattr(p, 'potential_grade', '?')}")
            row = tk.Frame(content, bg=bg)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=name, font=AppFonts.SMALL_BOLD,
                     fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="left")
            tk.Label(row, text=detail, font=AppFonts.CAPTION,
                     fg=AppColors.TEXT_TERTIARY, bg=bg).pack(side="right")

    # ---------------- Upcoming milestones ----------------
    def _create_milestones_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["milestones"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")
        self._card_title_row(content, "Upcoming Milestones", "Stats →",
                             "open_stats_standings_window")

        roster = list(getattr(self.user_team, "roster", []) or [])
        skaters = [p for p in roster
                   if "GOALIE" not in str(getattr(p, "primary_position", ""))]
        hits = []
        for p in skaters:
            name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
            pts = (getattr(p, "goals", 0) or 0) + (getattr(p, "assists", 0) or 0)
            for m in (25, 50, 75, 100):
                if pts < m <= pts + 8:
                    hits.append((m - pts, name, f"{m - pts} PTS from {m}"))
            cg = getattr(p, "career_games", 0) or 0
            for m in (500, 1000, 1500):
                if cg < m <= cg + 10:
                    hits.append((m - cg, name, f"{m - cg} GP from {m} career"))
        hits.sort(key=lambda h: h[0])
        if not hits:
            tk.Label(content, text="No milestones within reach.",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY,
                     bg=bg).pack(anchor="w")
            return
        for _gap, name, text in hits[:6]:
            row = tk.Frame(content, bg=bg)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="●", font=AppFonts.CAPTION,
                     fg=AppColors.ACCENT, bg=bg).pack(side="left",
                                                     padx=(0, 6))
            tk.Label(row, text=name, font=AppFonts.SMALL_BOLD,
                     fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="left")
            tk.Label(row, text=text, font=AppFonts.SMALL,
                     fg=AppColors.TEXT_SECONDARY, bg=bg).pack(side="right")

    # ---------------- Inbox ----------------
    def _create_inbox_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        self._section_anchors["inbox"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")

        header = tk.Frame(content, bg=bg)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="Inbox", font=AppFonts.H2,
                 fg=AppColors.TEXT_PRIMARY, bg=bg).pack(side="left")

        inbox = getattr(self.user_team, "inbox", None)
        unread = getattr(inbox, "unread_count", 0) or 0
        if unread:
            PillBadge(header, text=f"{unread} new", bg=AppColors.DANGER,
                      fg="#ffffff").pack(side="right")

        messages = list(getattr(inbox, "messages", []) or [])[:3]
        if not messages:
            tk.Label(content, text="No messages.",
                     font=AppFonts.SMALL, fg=AppColors.TEXT_TERTIARY, bg=bg).pack(anchor="w")
        for m in messages:
            subject = getattr(m, "subject", "Message")
            sender = getattr(m, "sender", "")
            is_read = getattr(m, "is_read", True)
            row = tk.Frame(content, bg=bg)
            row.pack(fill="x", pady=3)
            dot_color = AppColors.ACCENT if not is_read else AppColors.BORDER
            dot = tk.Canvas(row, width=8, height=8, bg=bg, highlightthickness=0)
            dot.create_oval(1, 1, 7, 7, fill=dot_color, outline="")
            dot.pack(side="left", padx=(0, 8))
            tk.Label(row, text=subject, font=AppFonts.SMALL_BOLD if not is_read else AppFonts.SMALL,
                     fg=AppColors.TEXT_PRIMARY, bg=bg, anchor="w").pack(side="left", fill="x", expand=True)
            if sender:
                tk.Label(row, text=sender, font=AppFonts.CAPTION,
                         fg=AppColors.TEXT_TERTIARY, bg=bg).pack(side="right")

        self._view_all_button(content, "Open inbox →", "open_inbox_window")

    # ---------------- Quick actions ----------------
    def _create_quick_actions_card(self, parent):
        card = AppCard(parent)
        card.pack(fill="x")
        self._section_anchors["actions"] = card
        content = card.get_content_frame()
        bg = content.cget("bg")
        self._card_title_row(content, "Go to…")

        actions = [
            ("Roster", "open_roster_window"),
            ("Edit Lines", "open_edit_lines_window"),
            ("Tactics", "open_tactics_window"),
            ("Schedule", "open_schedule_window"),
            ("Standings", "open_stats_standings_window"),
            ("Trade Center", "open_trade_window"),
            ("Inbox", "open_inbox_window"),
            ("Finances", "open_finances_window"),
        ]
        grid = tk.Frame(content, bg=bg)
        grid.pack(fill="x")
        for i, (label, method) in enumerate(actions):
            btn = AppButton(grid, text=label, style="secondary",
                            command=lambda m=method: self._nav(m),
                            width=120, height=36)
            btn.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="ew")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

    def _on_continue(self):
        if self.on_continue:
            self.on_continue()
        else:
            print("Continue clicked (no handler)")
