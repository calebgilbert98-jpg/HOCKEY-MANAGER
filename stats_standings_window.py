"""
Enhanced Stats and Standings Window for Hockey Manager
Comprehensive view with advanced analytics, historical data, and interactive features

CustomTkinter rebuild: CTkToplevel chrome, CTkTabview tab sets, CTkComboBox
filters, dark styled multi-column treeviews. All data/logic methods are
unchanged from the legacy build -- this is a UI rebuild only.
"""

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from typing import Dict, List, Optional
import random
from datetime import datetime, timedelta

import customtkinter as ctk

# (advanced_stats_analytics import removed 2026-09-28: the real-time engine was
# populated on every screen open but never displayed. Live advanced stats on
# the stats screens come from advanced_metrics.)

try:
    from team_identity_system import (jersey_chip as _jersey_chip,
                                      accent_for_team as _accent_for_team)
except Exception:
    _jersey_chip = None
    _accent_for_team = None

try:
    from game_classes import to_100_scale
except ImportError:
    def to_100_scale(v):
        try:
            return max(1, min(100, int(round(float(v)))))
        except (TypeError, ValueError):
            return 50

def _sfont(family, size, weight=""):
    """Scale-aware font tuple replacement (honors Settings -> Font size).

    Returns a live tkinter Font registered with ui_scale; changing the
    tier resizes open-window text in place. Falls back to a plain tuple
    when ui_scale is unavailable (headless stubs).
    """
    try:
        from ui_scale import font as _mkfont
        return _mkfont(family, size, weight)
    except Exception:
        return (family, size, weight) if weight else (family, size)


class StatsStandingsView(ctk.CTkFrame):
    """Advanced Stats and Standings window with deep analytics and multiple view modes"""

    # Tab names in order -- kept as lists so tab-name <-> index mapping stays
    # correct everywhere (on_tab_changed, refresh_all_data, set_focus_tab).
    MAIN_TABS = ["Standings", "Team Analytics", "Player Leaders",
                 "Analytics & Trends", "Division Analysis", "Divisions"]
    LEADER_TABS = ["Scoring Leaders", "Advanced Stats", "Goaltending",
                   "Breakout Players", "Rookie Leaders", "Award Races",
                   "Milestone Watch", "NHL Records"]
    ANALYTICS_TABS = ["Dashboard", "Trends", "Insights"]
    RECORD_TABS = ["Season Records", "Career Records", "Current Leaders",
                   "Record Chase", "Achievements"]

    def __init__(self, parent, app=None):
        # Calder season year for rookie eligibility (Sept-15 age cutoff
        # belongs to the season's start year).
        try:
            import awards_race as _ar
            _d = getattr(app, "current_date", None)
            self._calder_year = _ar.calder_season_year(_d) if _d is not None else None
        except Exception:
            self._calder_year = None
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
        self._teamcolor_tags = set()  # reserved (grid table needs no tags)
        self._ff = "Segoe UI"
        init_ctk_theme()
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the StatsStandingsWindow wrapper
        self.configure(fg_color=self._ct['BG'])

        # Enhanced state tracking
        self.selected_tab = 0
        self.historical_data = {}
        self.analytics_cache = {}
        self.filters = {
            'time_period': 'Season',
            'team_filter': 'All Teams',
            'stat_type': 'Overall'
        }

        # (Real-time analytics engine unwired 2026-09-28: advanced_stats_analytics
        # was populated on every screen open but never displayed anywhere. The
        # live advanced stats on this screen come from advanced_metrics.)

        # Dark styling for the multi-column tables (styled ttk.Treeview,
        # per the migration guide)
        self._setup_tree_style()

        # Create the enhanced interface
        self.create_interface()

        # Track window
        self.app.open_windows['stats_standings'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # CTk styling helpers
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the stat tables (styled ttk.Treeview per
        the migration guide -- the tables carry up to 12 columns and use
        playoff/average row tags)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Stats.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=28,
                        font=(self._ff, 10))
        style.configure('Stats.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=(self._ff, 10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Stats.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Stats.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Stats.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Stats.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _card(self, parent, **kw):
        """Rounded dark card frame (selective rounding per theme rules)."""
        kw.setdefault('fg_color', self._ct['CARD'])
        kw.setdefault('corner_radius', 10)
        return ctk.CTkFrame(parent, **kw)

    def _make_tabview(self, parent):
        """CTkTabview styled like the other migrated screens."""
        ct = self._ct
        return self._SafeTabview(
            parent,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
        )

    def _combo(self, parent, variable, values, command, width=150):
        """Dark styled CTkComboBox for the filter rows."""
        ct = self._ct
        return ctk.CTkComboBox(
            parent, variable=variable, values=values, command=command,
            width=width,
            fg_color=ct['PANEL'], border_color=ct['BORDER'],
            button_color=ct['CARD'], button_hover_color=ct['TEAL'],
            text_color=ct['TEXT'],
            dropdown_fg_color=ct['PANEL'],
            dropdown_hover_color=ct['BORDER'],
            dropdown_text_color=ct['TEXT'],
            font=(self._ff, 11))

    def _check(self, parent, text, variable, command):
        """Dark styled CTkCheckBox."""
        ct = self._ct
        return ctk.CTkCheckBox(
            parent, text=text, variable=variable, command=command,
            fg_color=ct['TEAL'], hover_color=ct['TEAL_HOVER'],
            text_color=ct['TEXT'], border_color=ct['BORDER'],
            font=(self._ff, 11))

    def _make_tree(self, parent, columns, height=15, padx=0, pady=0):
        """Dark styled multi-column table with scrollbar, packed to fill.

        Mirrors the legacy raw ttk.Treeview construction (no click sorting;
        tables that had parent-bound sorting keep using _pack_parent_tree).
        """
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree = ttk.Treeview(frame, columns=list(columns.keys()),
                            show='headings', height=height,
                            style='Stats.Treeview')
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='center')
            tree.column(col_id, width=width, anchor='center')
        scrollbar = ttk.Scrollbar(frame, orient="vertical",
                                  command=tree.yview,
                                  style='Stats.Vertical.TScrollbar')
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        frame.pack(fill="both", expand=True, padx=padx, pady=pady)
        return tree

    def _bind_leader_menu(self, tree):
        """Right-click on a leaders-table row -> full player context menu."""
        from player_context_menu import PlayerContextMenu

        def _show(event):
            item = tree.identify_row(event.y)
            if not item:
                return
            tree.selection_set(item)
            player = None
            try:
                player = self.app.tree_maps.get(tree, {}).get(item)
            except Exception:
                player = None
            if player:
                PlayerContextMenu(self.app).show_context_menu(event, player)

        tree.bind("<Button-3>", _show)

    def _pack_parent_tree(self, parent, columns, height=15, padx=0, pady=0):
        """Table built via parent._create_treeview (keeps the legacy column
        sorting and the player context menu), dark-styled, with a scrollbar,
        packed to fill.

        This also fixes the legacy bug where the milestone/records trees
        were created but never packed, rendering them invisible.
        """
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree = self.app._create_treeview(frame, columns, height=height)
        tree.configure(style='Stats.Treeview')
        scrollbar = ttk.Scrollbar(frame, orient="vertical",
                                  command=tree.yview,
                                  style='Stats.Vertical.TScrollbar')
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        frame.pack(fill="both", expand=True, padx=padx, pady=pady)
        return tree

    def _scroll_area(self, parent, padx=10, pady=10):
        """CTkScrollableFrame + inner content frame.

        The inner frame is what repopulate methods clear (winfo_children on
        a CTkScrollableFrame would return its internal canvas/scrollbar).
        """
        ct = self._ct
        scroll = ctk.CTkScrollableFrame(
            parent, fg_color=ct['PANEL'], corner_radius=10,
            border_width=1, border_color=ct['BORDER'])
        scroll.pack(fill="both", expand=True, padx=padx, pady=pady)
        inner = ctk.CTkFrame(scroll, fg_color="transparent")
        inner.pack(fill="both", expand=True)
        return inner
    
    # ------------------------------------------------------------------
    # Tabview with a guard for the CTk 6.0.0 deferred grid-forget race.
    # CTkTabview.set() schedules _grid_forget_all_tabs 100 ms out; rapid
    # programmatic .set() calls (or .set() while the event loop is not
    # pumping) can leave a stale forget callback that grid-forgets the
    # currently selected tab and blanks the content area. Re-asserting the
    # current tab shortly after heals it. Physical clicks are unaffected
    # (they grid synchronously via _segmented_button_callback).
    # ------------------------------------------------------------------
    class _SafeTabview(ctk.CTkTabview):
        def set(self, name):
            super().set(name)
            self.after(150, lambda n=name: self._heal_tab(n))

        def _heal_tab(self, name):
            try:
                if self.winfo_exists() and self.get() == name:
                    super().set(name)
            except Exception:
                pass

    def set_focus_tab(self, tab_name):
        """Set focus to a specific tab - for external navigation.

        Fixed: 'records' previously mapped to nothing (the records UI lives
        under Player Leaders -> NHL Records), so the achievement popup's
        "View Records" button silently did nothing. It now navigates there.

        Note: CTkTabview.set() does not fire the tabview command (unlike
        ttk.Notebook's <<NotebookTabChanged>> on .select()), so the change
        handler is invoked explicitly to keep selected_tab/load state in
        sync for programmatic navigation.
        """
        tab_map = {
            'standings': "Standings",
            'team_stats': "Team Analytics",
            'player_leaders': "Player Leaders",
            'analytics': "Analytics & Trends",
            'divisions': "Division Analysis",
        }
        if tab_name in tab_map:
            self.tabview.set(tab_map[tab_name])
            self._on_main_tab_selected(tab_map[tab_name])
        elif tab_name == 'records':
            self.tabview.set("Player Leaders")
            self._on_main_tab_selected("Player Leaders")
            if hasattr(self, 'leaders_tabview'):
                try:
                    self.leaders_tabview.set("NHL Records")
                except Exception:
                    pass
    
    def create_interface(self):
        """Create the enhanced interface with advanced features"""
        ct = self._ct
        # Main container
        main_frame = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main_frame.pack(fill='both', expand=True, padx=12, pady=12)

        # Title card with live indicator and global filters
        title_card = self._card(main_frame)
        title_card.pack(fill='x', pady=(0, 12))

        title_row = ctk.CTkFrame(title_card, fg_color="transparent")
        title_row.pack(fill='x', padx=16, pady=12)

        self._heading(title_row, text="Advanced League Analytics & Standings",
                      size=20).pack(side='left')

        # LIVE pill
        live_pill = ctk.CTkFrame(title_row, fg_color=ct['TEAL'],
                                 corner_radius=10)
        live_pill.pack(side='left', padx=(12, 0))
        ctk.CTkLabel(live_pill, text="LIVE",
                     font=(self._ff, 10, 'bold'),
                     text_color=ct['BG']).pack(padx=10, pady=2)

        # Global filters (right side)
        filters_frame = ctk.CTkFrame(title_row, fg_color="transparent")
        filters_frame.pack(side='right')

        self._body(filters_frame, text="Period:", dim=True,
                   size=11).pack(side='left', padx=(0, 6))
        self.period_combo = self._combo(
            filters_frame, variable=None,
            values=["Last 10 Games", "Last Month", "Season", "All Time"],
            command=self.on_filter_change, width=130)
        self.period_combo.set("Season")
        self.period_combo.pack(side='left', padx=(0, 12))

        # Regular Season / Playoffs: the whole screen (team analytics,
        # player leaders, dashboard) re-reads from the matching ledger.
        # Standings stay the final regular-season table in both modes.
        self._body(filters_frame, text="Season:", dim=True,
                   size=11).pack(side='left', padx=(0, 6))
        self.season_type = tk.StringVar(value="Regular Season")
        self._combo(
            filters_frame, variable=self.season_type,
            values=["Regular Season", "Playoffs"],
            command=self.on_season_type_change, width=130).pack(
                side='left', padx=(0, 12))

        self._secondary_button(filters_frame, text="Close",
                               command=self.close_view).pack(side='left')

        # Main tabs
        self.tabview = self._make_tabview(main_frame)
        self.tabview.configure(command=self._on_main_tab_selected)
        self.tabview.pack(fill='both', expand=True, pady=(0, 12))
        for name in self.MAIN_TABS:
            self.tabview.add(name)

        # Create the tabs (same content as the legacy build, new chrome)
        self.create_enhanced_standings_tab()
        self.create_advanced_team_stats_tab()
        self.create_enhanced_player_leaders_tab()
        self.create_comprehensive_analytics_tab()
        self.create_division_analysis_tab()
        self.create_divisions_grid_tab()

        # Status bar
        status_card = self._card(main_frame)
        status_card.pack(fill='x')

        status_row = ctk.CTkFrame(status_card, fg_color="transparent")
        status_row.pack(fill='x', padx=16, pady=10)

        self.status_label = self._body(
            status_row, text="Ready - Real game data loaded successfully",
            dim=True, size=11)
        self.status_label.pack(side='left')

        self.data_summary_label = self._body(status_row, text="",
                                             dim=True, size=11)
        self.data_summary_label.pack(side='left', padx=(20, 0))

        btn_row = ctk.CTkFrame(status_row, fg_color="transparent")
        btn_row.pack(side='right')
        self._secondary_button(btn_row, text="Export Data",
                               command=self.export_data).pack(side='right',
                                                             padx=(6, 0))
        self._secondary_button(btn_row, text="Refresh All",
                               command=self.refresh_all_data).pack(side='right')

        # Update data summary
        self.update_data_summary()

    def _on_main_tab_selected(self, tab_name):
        """CTkTabview selection callback -> legacy tab-change handling."""
        try:
            self.on_tab_changed()
        except Exception as e:
            print(f"Error handling tab change: {e}")
    
    def update_data_summary(self):
        """Update the data summary in the status bar"""
        try:
            league = getattr(self.app.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                team_count = len(league.teams)
                # Count total players
                total_players = 0
                for team in league.teams:
                    if hasattr(team, 'roster'):
                        total_players += len(team.roster)
                
                summary = f"{team_count} teams • {total_players:,} players"
                self.data_summary_label.configure(text=summary)
            else:
                self.data_summary_label.configure(text="No league data available")
        except Exception as e:
            self.data_summary_label.configure(text=f"Data error: {str(e)}")
    
    def create_enhanced_standings_tab(self):
        """Create enhanced standings tab with playoff race and momentum indicators"""
        ct = self._ct
        standings_frame = self.tabview.tab("Standings")
        standings_frame.configure(fg_color=ct['PANEL'])

        # Controls card
        controls = self._card(standings_frame)
        controls.pack(fill='x', padx=10, pady=(10, 8))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill='x', padx=12, pady=10)

        # View options
        self._body(row, text="View:", dim=True, size=11).pack(side='left',
                                                              padx=(0, 6))
        self.standings_view = tk.StringVar(value="League Overview")
        self._combo(row, variable=self.standings_view,
                    values=["League Overview", "Eastern Conference",
                            "Western Conference", "Wild Card Race",
                            "Division Leaders", "Playoff Picture"],
                    command=self.update_standings_view,
                    width=180).pack(side='left', padx=(0, 15))

        # Sort options
        self._body(row, text="Sort by:", dim=True, size=11).pack(side='left',
                                                                 padx=(0, 6))
        self.standings_sort = tk.StringVar(value="Points")
        self._combo(row, variable=self.standings_sort,
                    values=["Points", "Wins", "Goal Differential"],
                    command=self.update_standings_view,
                    width=150).pack(side='left', padx=(0, 15))

        # Toggle advanced metrics
        self.show_advanced = tk.BooleanVar(value=True)
        self._check(row, text="Advanced Metrics",
                    variable=self.show_advanced,
                    command=self.update_standings_view).pack(side='left')

        # Main standings area with scrolling
        self.standings_scrollable = self._scroll_area(standings_frame)
        self.populate_enhanced_standings()

    def create_advanced_team_stats_tab(self):
        """Create advanced team statistics with comparative analysis"""
        ct = self._ct
        stats_frame = self.tabview.tab("Team Analytics")
        stats_frame.configure(fg_color=ct['PANEL'])

        # Controls card
        controls = self._card(stats_frame)
        controls.pack(fill='x', padx=10, pady=(10, 8))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill='x', padx=12, pady=10)

        # Category selection with more options
        self._body(row, text="Category:", dim=True, size=11).pack(side='left',
                                                                  padx=(0, 6))
        self.stats_category = tk.StringVar(value="Overall Performance")
        self._combo(row, variable=self.stats_category,
                    values=["Overall Performance", "Offensive Stats",
                            "Defensive Stats", "Goaltending",
                            "Advanced Analytics"],
                    command=self.update_team_stats_view,
                    width=180).pack(side='left', padx=(0, 15))

        # Comparison mode
        self._body(row, text="View Mode:", dim=True, size=11).pack(side='left',
                                                                   padx=(0, 6))
        self.stats_mode = tk.StringVar(value="League Rankings")
        self._combo(row, variable=self.stats_mode,
                    values=["League Rankings", "vs League Average"],
                    command=self.update_team_stats_view,
                    width=150).pack(side='left', padx=(0, 15))

        # Team filter
        self._body(row, text="Teams:", dim=True, size=11).pack(side='left',
                                                               padx=(0, 6))
        self.team_filter = tk.StringVar(value="All Teams")
        self._combo(row, variable=self.team_filter,
                    values=["All Teams", "Eastern Conference",
                            "Western Conference", "Division Rivals",
                            "Playoff Teams"],
                    command=self.update_team_stats_view,
                    width=150).pack(side='left')

        # Stats display area
        self.team_stats_container = ctk.CTkFrame(stats_frame,
                                                 fg_color="transparent")
        self.team_stats_container.pack(fill='both', expand=True,
                                       padx=10, pady=(0, 10))

        self.populate_advanced_team_stats()
    
    def create_enhanced_player_leaders_tab(self):
        """Create enhanced player leaders with advanced filtering"""
        ct = self._ct
        leaders_frame = self.tabview.tab("Player Leaders")
        leaders_frame.configure(fg_color=ct['PANEL'])

        # Controls card
        controls = self._card(leaders_frame)
        controls.pack(fill='x', padx=10, pady=(10, 8))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill='x', padx=12, pady=10)

        # Position filter
        self._body(row, text="Position:", dim=True, size=11).pack(side='left',
                                                                  padx=(0, 6))
        self.position_filter = tk.StringVar(value="All Positions")
        self._combo(row, variable=self.position_filter,
                    values=["All Positions", "Forwards", "Defensemen",
                            "Goalies", "Centers", "Wingers", "Rookies",
                            "Veterans"],
                    command=self.update_player_leaders,
                    width=140).pack(side='left', padx=(0, 15))

        # Minimum games filter (kept as a spinbox: bounded numeric input)
        self._body(row, text="Min Games:", dim=True, size=11).pack(side='left',
                                                                    padx=(0, 6))
        self.min_games = tk.IntVar(value=10)
        games_spin = tk.Spinbox(row, from_=1, to=82,
                                textvariable=self.min_games,
                                width=5, command=self.update_player_leaders,
                                bg=ct['CARD'], fg=ct['TEXT'],
                                buttonbackground=ct['CARD'],
                                highlightthickness=1,
                                highlightbackground=ct['BORDER'],
                                relief='flat')
        games_spin.pack(side='left', padx=(0, 15))

        # Show per-game stats
        self.show_per_game = tk.BooleanVar(value=False)
        self._check(row, text="Per Game Stats",
                    variable=self.show_per_game,
                    command=self.update_player_leaders).pack(side='left')

        # Sub-tabs
        self.leaders_tabview = self._make_tabview(leaders_frame)
        self.leaders_tabview.pack(fill='both', expand=True,
                                  padx=10, pady=(0, 10))
        for name in self.LEADER_TABS:
            self.leaders_tabview.add(name)

        self.create_enhanced_player_section(
            self.leaders_tabview.tab("Scoring Leaders"), "scoring")
        self.create_enhanced_player_section(
            self.leaders_tabview.tab("Advanced Stats"), "advanced")
        self.create_enhanced_player_section(
            self.leaders_tabview.tab("Goaltending"), "goaltending")
        self.create_enhanced_player_section(
            self.leaders_tabview.tab("Breakout Players"), "breakout")
        self.create_rookie_leaders_section(
            self.leaders_tabview.tab("Rookie Leaders"))
        self.create_award_races_section(
            self.leaders_tabview.tab("Award Races"))
        self.create_milestone_watch_section(
            self.leaders_tabview.tab("Milestone Watch"))
        self.create_records_section(
            self.leaders_tabview.tab("NHL Records"))

    # Career milestone definitions: (career attr, season attr, label, milestones, within)
    MILESTONE_WATCH_SKATERS = [
        ('career_goals', 'goals', 'Goals', (100, 200, 300, 400, 500, 600, 700), 12),
        ('career_assists', 'assists', 'Assists', (200, 300, 400, 500, 600, 800, 1000), 12),
        ('career_points', 'points', 'Points', (500, 750, 1000, 1250, 1500), 18),
        ('career_games', 'games_played', 'Games Played', (500, 1000, 1500), 25),
    ]
    MILESTONE_WATCH_GOALIES = [
        ('career_wins', 'wins', 'Wins', (100, 200, 300), 8),
        ('career_shutouts', 'shutouts', 'Shutouts', (25, 50, 75, 100), 4),
        ('career_games_goalie', 'games_played', 'Games Played', (300, 500), 20),
    ]

    # ------------------------------------------------------------------
    # Rookie Leaders + Award Races (new)
    # ------------------------------------------------------------------
    def _league_players_and_teams(self):
        """Return (players, teams) for the NHL league."""
        players, teams = [], []
        try:
            league = getattr(self.app, "league", None)
            if league is None and hasattr(self.app, "game_manager"):
                league = getattr(self.app.game_manager, "league", None)
            candidates = []
            if league is not None:
                if getattr(league, "teams", None):
                    candidates = list(league.teams)
                elif getattr(league, "leagues", None):
                    for lg in league.leagues:
                        if "National Hockey League" in str(getattr(lg, "name", "")):
                            candidates = list(getattr(lg, "teams", []) or [])
                            break
            for team in candidates:
                teams.append(team)
                for p in (getattr(team, "roster", []) or []):
                    players.append(p)
        except Exception:
            pass
        return players, teams

    def _pname(self, p):
        return (getattr(p, "full_name", None) or getattr(p, "name", None)
                or f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
                or "?")

    def _pteam_abbr(self, p, teams):
        tname = getattr(p, "team_name", "") or ""
        if not tname:
            # fall back: find the team whose roster holds this player
            for t in teams:
                if p in (getattr(t, "roster", []) or []):
                    tname = getattr(t, "team_name", "")
                    break
        return self._get_team_abbreviation(tname) if tname else ""

    # ------------------------------------------------------------------
    # Regular Season / Playoffs split
    # ------------------------------------------------------------------
    def _in_playoff_mode(self):
        """True when the Season toggle is on Playoffs."""
        try:
            return self.season_type.get() == "Playoffs"
        except Exception:
            return False

    def _stat_ledger(self, player):
        """The active per-player stat ledger for the current Season toggle.

        Regular Season -> player.stats; Playoffs -> player.playoff_stats
        (folded from GameSim.game_stats after every playoff game). Falls
        back to whichever ledger exists -- old saves predate playoff_stats.
        NHL only: neither ledger ever includes AHL numbers (ahl_stats is a
        separate object read only by the AHL Stats screen).
        """
        if self._in_playoff_mode():
            led = getattr(player, "playoff_stats", None)
            return led if led is not None else getattr(player, "stats", None)
        return getattr(player, "stats", None)

    def _pstat(self, player, attr, default=0):
        """One stat from the active ledger, direct-attr fallback."""
        led = self._stat_ledger(player)
        if led is not None and hasattr(led, attr):
            try:
                return getattr(led, attr)
            except Exception:
                pass
        return getattr(player, attr, default)

    def get_team_playoff_stats(self):
        """Per-team playoff numbers from the bracket's per-game results.

        Returns {team_name: {GP, W, L, GF, GA, result}} where result is
        'Won Stanley Cup' or 'Lost <round>'. Empty dict when no playoff
        games have been played yet. Read-only walk -- nothing persisted.
        """
        out = {}
        try:
            league = getattr(getattr(self.app, "game_manager", self.app),
                             "league", None)
            bracket = getattr(league, "playoff_bracket", None)
            if bracket is None:
                pw = getattr(self.app, "open_windows", {}).get("playoffs")
                if pw is not None:
                    try:
                        if pw.winfo_exists():
                            bracket = getattr(pw, "playoff_bracket", None)
                    except Exception:
                        bracket = None
            if bracket is None:
                return out
            series_map = getattr(bracket, "playoff_series", None) or {}
            champ = getattr(bracket, "stanley_cup_champion", None)
            champ_name = getattr(champ, "team_name", None)
            round_order = ["wild_card", "division_semifinals",
                           "division_finals", "conference_finals",
                           "stanley_cup_final"]
            round_names = {"wild_card": "Round 1",
                           "division_semifinals": "Round 2",
                           "division_finals": "Round 3",
                           "conference_finals": "Conf. Final",
                           "stanley_cup_final": "Cup Final"}
            for key in round_order:
                for s in series_map.get(key, None) or []:
                    t1, t2 = getattr(s, "team1", None), getattr(s, "team2", None)
                    for t, is_t1 in ((t1, True), (t2, False)):
                        if t is None:
                            continue
                        tname = getattr(t, "team_name",
                                        getattr(t, "name", "?"))
                        e = out.setdefault(
                            tname, {"GP": 0, "W": 0, "L": 0, "GF": 0,
                                    "GA": 0, "result": ""})
                        w = getattr(s, "team1_wins", 0) if is_t1 else \
                            getattr(s, "team2_wins", 0)
                        for g in getattr(s, "game_results", None) or []:
                            try:
                                t1s = int(g.get("t1_score", 0) or 0)
                                t2s = int(g.get("t2_score", 0) or 0)
                            except Exception:
                                continue
                            mine, theirs = (t1s, t2s) if is_t1 else (t2s, t1s)
                            e["GP"] += 1
                            e["GF"] += mine
                            e["GA"] += theirs
                        e["W"] += w
                        e["result"] = ("Won Stanley Cup"
                                       if tname == champ_name
                                       else "Lost " + round_names.get(key, key))
            # Losses = games - wins (a team appears in several series).
            for e in out.values():
                e["L"] = max(0, e["GP"] - e["W"])
        except Exception:
            pass
        return out

    def on_season_type_change(self, value=None):
        """Season toggle flipped: regular-season-only tabs can't show
        playoff data, so park the leaders view on Scoring Leaders, then
        refresh whatever main tab is showing."""
        try:
            if self._in_playoff_mode() and hasattr(self, "leaders_tabview"):
                rs_only = {"Breakout Players", "Rookie Leaders",
                           "Award Races", "Milestone Watch", "NHL Records"}
                if self.leaders_tabview.get() in rs_only:
                    self.leaders_tabview.set("Scoring Leaders")
        except Exception:
            pass
        try:
            self.refresh_all_data()
        except Exception as e:
            print(f"Error refreshing on season-type change: {e}")

    def create_rookie_leaders_section(self, parent_frame):
        """Rookie Leaders tab: rookie scoring + rookie goaltending."""
        import awards_race as ar
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])

        players, teams = self._league_players_and_teams()

        # Header
        hdr = ctk.CTkFrame(parent_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        title = ctk.CTkLabel(hdr, text="Rookie Leaders",
                             font=ctk.CTkFont(size=16, weight="bold"),
                             text_color=ct['TEXT'])
        title.pack(side="left")
        sub = ctk.CTkLabel(hdr, text="First-year players (rookie eligibility)",
                           font=ctk.CTkFont(size=11),
                           text_color=ct['TEXT_DIM'])
        sub.pack(side="left", padx=(10, 0))

        body = ctk.CTkFrame(parent_frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Left: rookie skaters
        left = ctk.CTkFrame(body, fg_color=ct['CARD'])
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(left, text="Rookie Scoring",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=10, pady=(8, 2))
        cols_s = {"rank": ("#", 36), "player": ("Player", 150),
                  "team": ("Team", 52), "gp": ("GP", 44),
                  "g": ("G", 40), "a": ("A", 40), "p": ("P", 44)}
        tree_s = self._make_tree(left, cols_s, height=18, padx=10, pady=6)
        self._bind_leader_menu(tree_s)
        tree_s._player_rows = {}

        # Right: rookie goalies
        right = ctk.CTkFrame(body, fg_color=ct['CARD'])
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(right, text="Rookie Goaltending",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=ct['TEXT']).pack(anchor="w", padx=10, pady=(8, 2))
        cols_g = {"rank": ("#", 36), "player": ("Player", 150),
                  "team": ("Team", 52), "gp": ("GP", 44),
                  "w": ("W", 40), "sv": ("SV%", 58), "gaa": ("GAA", 52)}
        tree_g = self._make_tree(right, cols_g, height=18, padx=10, pady=6)
        self._bind_leader_menu(tree_g)
        tree_g._player_rows = {}

        for i, r in enumerate(ar.rookie_skaters(players, season_year=self._calder_year)[:25], 1):
            p = r["player"]
            iid = tree_s.insert("", "end", values=(
                i, self._pname(p), self._pteam_abbr(p, teams),
                r["gp"], r["goals"], r["assists"], r["points"]))
            tree_s._player_rows[iid] = p
        for i, r in enumerate(ar.rookie_goalies(players, season_year=self._calder_year)[:25], 1):
            p = r["player"]
            iid = tree_g.insert("", "end", values=(
                i, self._pname(p), self._pteam_abbr(p, teams),
                r["gp"], r["wins"], f"{r['sv_pct']:.3f}", f"{r['gaa']:.2f}"))
            tree_g._player_rows[iid] = p

    def create_award_races_section(self, parent_frame):
        """Award Races tab: per-award candidate rankings.

        Each award ranks by the criterion that drives real-world voting
        (see awards_race.py for the winner-history rationale).
        """
        import awards_race as ar
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])

        # Top bar: award picker
        topbar = ctk.CTkFrame(parent_frame, fg_color="transparent")
        topbar.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(topbar, text="Award Races",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=ct['TEXT']).pack(side="left")
        award_names = [name for name, _desc, _key in ar.AWARD_DEFINITIONS]
        self._award_var = ctk.StringVar(value=award_names[0])
        picker = ctk.CTkOptionMenu(topbar, variable=self._award_var,
                                   values=award_names, width=260,
                                   command=lambda _v: self._refresh_award_race())
        picker.pack(side="left", padx=(12, 0))

        # Criteria description
        self._award_desc = ctk.CTkLabel(parent_frame, text="",
                                        font=ctk.CTkFont(size=11),
                                        text_color=ct['TEXT_DIM'],
                                        wraplength=900, justify="left")
        self._award_desc.pack(fill="x", padx=12, pady=(0, 6))

        # Candidate table container
        self._award_table_holder = ctk.CTkFrame(parent_frame,
                                                fg_color="transparent")
        self._award_table_holder.pack(fill="both", expand=True,
                                      padx=12, pady=(0, 10))
        self._refresh_award_race()

    def _refresh_award_race(self):
        """Rebuild the award-race table for the selected award."""
        import awards_race as ar
        ct = self._ct
        holder = self._award_table_holder
        for child in holder.winfo_children():
            child.destroy()

        name = self._award_var.get()
        key = next((k for n, _d, k in ar.AWARD_DEFINITIONS if n == name),
                   "hart")
        desc = next((d for n, d, _k in ar.AWARD_DEFINITIONS if n == name), "")
        self._award_desc.configure(
            text=f"{name}: {desc}")

        players, teams = self._league_players_and_teams()
        team_pct = {}
        for t in teams:
            gp = getattr(t, "games_played", 0) or 0
            pts = getattr(t, "points", 0) or 0
            team_pct[getattr(t, "team_name", "")] = (pts / (2 * gp)) if gp else 0.5
        # Authoritative roster mapping: team_name labels can go stale
        # after trades; the roster is the truth.
        roster_map = ar.roster_team_map(teams)

        rows, columns = [], {}
        is_team_award = False

        if key == "hart":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "g": ("G", 40), "a": ("A", 40), "p": ("P", 44),
                       "tpct": ("Team P%", 64)}
            for i, r in enumerate(ar.hart_race(players, team_pct,
                                                roster_map=roster_map)[:15], 1):
                p = r["player"]
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["goals"],
                                 (getattr(p, "assists", 0) or 0),
                                 r["points"], f"{r['team_pct']:.3f}")))
        elif key == "art_ross":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "g": ("G", 40), "a": ("A", 40), "p": ("P", 44)}
            for i, r in enumerate(ar.art_ross_race(players)[:15], 1):
                p = r["player"]
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["goals"], r["assists"], r["points"])))
        elif key == "rocket":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "g": ("G", 40), "p": ("P", 44),
                       "shpct": ("SH%", 52)}
            for i, r in enumerate(ar.rocket_race(players)[:15], 1):
                p = r["player"]
                shots = getattr(p, "shots", 0) or 0
                shpct = (r["goals"] / shots * 100) if shots else 0.0
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["goals"], r["points"], f"{shpct:.1f}")))
        elif key == "norris":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "g": ("G", 40), "a": ("A", 40), "p": ("P", 44),
                       "pm": ("+/-", 48)}
            for i, r in enumerate(ar.norris_race(players)[:15], 1):
                p = r["player"]
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["goals"],
                                 (r["points"] - r["goals"]),
                                 r["points"], r["plus_minus"])))
        elif key == "vezina":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "w": ("W", 40), "sv": ("SV%", 58),
                       "gaa": ("GAA", 52), "so": ("SO", 40),
                       "gsax": ("GSAx", 58)}
            goalies = [p for p in players if self._is_goalie(p)]
            for i, r in enumerate(ar.vezina_race(goalies)[:15], 1):
                p = r["player"]
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["wins"], f"{r['sv_pct']:.3f}",
                                 f"{r['gaa']:.2f}", r["shutouts"],
                                 f"{r['gsax']:+.1f}")))
        elif key == "calder":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "g": ("G", 40), "a": ("A", 40), "p": ("P", 44),
                       "note": ("", 90)}
            for i, r in enumerate(ar.calder_race(players, season_year=self._calder_year)[:15], 1):
                p = r["player"]
                if r.get("goalie"):
                    vals = (i, self._pname(p), self._pteam_abbr(p, teams),
                            getattr(p, "games_played", 0) or 0,
                            "-", "-", "-",
                            f"G: {r['sv_pct']:.3f} SV%")
                else:
                    vals = (i, self._pname(p), self._pteam_abbr(p, teams),
                            getattr(p, "games_played", 0) or 0,
                            r["goals"], r["points"] - r["goals"],
                            r["points"], "")
                rows.append((p, vals))
        elif key == "selke":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "p": ("P", 44), "pm": ("+/-", 48),
                       "tk": ("TK", 44), "fo": ("FO", 44)}
            for i, r in enumerate(ar.selke_race(players)[:15], 1):
                p = r["player"]
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["points"], r["plus_minus"],
                                 r["takeaways"],
                                 getattr(p, "faceoffs", 50) or 50)))
        elif key == "byng":
            columns = {"rank": ("#", 36), "player": ("Player", 160),
                       "team": ("Team", 52), "gp": ("GP", 44),
                       "g": ("G", 40), "a": ("A", 40), "p": ("P", 44),
                       "pim": ("PIM", 48)}
            for i, r in enumerate(ar.byng_race(players)[:15], 1):
                p = r["player"]
                rows.append((p, (i, self._pname(p),
                                 self._pteam_abbr(p, teams),
                                 getattr(p, "games_played", 0) or 0,
                                 r["goals"], r["points"] - r["goals"],
                                 r["points"], r["pim"])))
        elif key == "adams":
            is_team_award = True
            columns = {"rank": ("#", 36), "coach": ("Coach", 160),
                       "team": ("Team", 150), "p": ("Pts", 48),
                       "actual": ("P%", 56), "exp": ("Exp P%", 64),
                       "over": ("Over +/-", 64)}
            for i, r in enumerate(ar.adams_race(teams)[:15], 1):
                rows.append((None, (i, r["coach"], r["team"], r["points"],
                                    f"{r['actual_pct']:.3f}",
                                    f"{r['expected_pct']:.3f}",
                                    f"{r['score']:+.3f}")))
        elif key == "jennings":
            is_team_award = True
            columns = {"rank": ("#", 36), "team": ("Team", 170),
                       "goalies": ("Goaltenders", 220),
                       "ga": ("GA", 48), "gagp": ("GA/GP", 58)}
            for i, r in enumerate(ar.jennings_race(teams)[:15], 1):
                rows.append((None, (i, r["team"], r["goalies"],
                                    r["goals_against"],
                                    f"{r['ga_per_game']:.2f}")))

        card = ctk.CTkFrame(holder, fg_color=ct['CARD'])
        card.pack(fill="both", expand=True)
        tree = self._make_tree(card, columns, height=20, padx=10, pady=10)
        tree._player_rows = {}
        if not is_team_award:
            self._bind_leader_menu(tree)
        for p, vals in rows:
            iid = tree.insert("", "end", values=vals)
            if p is not None:
                tree._player_rows[iid] = p

    def create_milestone_watch_section(self, parent_frame):
        """Milestone Watch sub-tab: players nearing career milestones.

        Uses real career totals from Player (career_goals/assists/points/games,
        career_wins/shutouts for goalies). Shows an honest empty state when no
        player is close to a milestone yet.
        """
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])
        header_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        header_frame.pack(fill='x', padx=10, pady=(10, 8))

        self._heading(header_frame,
                      text="Players nearing career milestones",
                      size=13, text_color=ct['TEAL']).pack(anchor='w')
        self._body(header_frame,
                   text="Real career totals - showing players within striking distance of their next milestone.",
                   dim=True, size=10).pack(anchor='w', pady=(2, 0))

        columns = {
            'player': ('Player', 190),
            'team': ('Team', 70),
            'pos': ('Pos', 60),
            'milestone': ('Milestone', 150),
            'current': ('Current', 80),
            'needed': ('Needed', 80),
            'season': ('This Season', 100),
        }
        # Packed (with scrollbar) -- the legacy build created this tree but
        # never packed it, so it was invisible.
        self.milestone_tree = self._pack_parent_tree(parent_frame, columns,
                                                     height=20,
                                                     padx=10, pady=(0, 10))
        self._populate_milestone_watch()

    def _position_abbr(self, player):
        """Short position label for a player."""
        pos = getattr(player, 'primary_position', 'F')
        if hasattr(pos, 'value'):
            return str(pos.value)
        name = str(pos).split('.')[-1]
        mapping = {'CENTER': 'C', 'LEFT_WING': 'LW', 'RIGHT_WING': 'RW',
                   'DEFENSE': 'D', 'GOALIE': 'G'}
        return mapping.get(name, name[:2])

    def _season_stat_value(self, player, attr):
        """Season stat, preferring the live stats object with player fallback."""
        stats = getattr(player, 'stats', None)
        if stats is not None and hasattr(stats, attr):
            return getattr(stats, attr)
        return getattr(player, attr, 0)

    def _milestone_empty_row(self, message):
        """Insert the honest empty-state row in the milestone tree."""
        tree = getattr(self, 'milestone_tree', None)
        if tree is not None:
            tree.insert('', 'end', values=(message, '', '', '', '', '', ''))

    def _populate_milestone_watch(self):
        """Fill the Milestone Watch tree from real career totals."""
        tree = getattr(self, 'milestone_tree', None)
        if tree is None:
            return
        try:
            for item in tree.get_children():
                tree.delete(item)
            if hasattr(self.app, 'tree_maps'):
                self.app.tree_maps.setdefault(tree, {}).clear()

            league = getattr(self.app, 'league', None)
            teams = getattr(league, 'teams', []) if league else []
            if not teams:
                self._milestone_empty_row("No league data available.")
                return

            watch = []
            for team in teams:
                roster = getattr(team, 'roster', []) or []
                team_abbr = self._get_team_abbreviation(getattr(team, 'team_name', ''))
                for player in roster:
                    is_goalie = self._is_goalie(player)
                    defs = (self.MILESTONE_WATCH_GOALIES if is_goalie
                            else self.MILESTONE_WATCH_SKATERS)
                    for career_attr, season_attr, label, marks, within in defs:
                        current = getattr(player, career_attr, 0) or 0
                        if current <= 0:
                            continue
                        upcoming = [m for m in marks if m > current]
                        if not upcoming:
                            continue
                        target = upcoming[0]
                        needed = target - current
                        if needed <= within:
                            watch.append({
                                'player': getattr(player, 'full_name', 'Unknown'),
                                'player_obj': player,
                                'team': team_abbr,
                                'pos': self._position_abbr(player),
                                'milestone': f"{target} {label}",
                                'current': current,
                                'needed': needed,
                                'season': self._season_stat_value(player, season_attr),
                            })

            if not watch:
                self._milestone_empty_row(
                    "No players approaching career milestones yet - check back as the season progresses.")
                return

            watch.sort(key=lambda w: (w['needed'], -w['current']))
            for w in watch[:40]:
                _mid = tree.insert('', 'end', values=(
                    w['player'], w['team'], w['pos'], w['milestone'],
                    w['current'], w['needed'], w['season']))
                if hasattr(self.app, 'tree_maps'):
                    self.app.tree_maps[tree][_mid] = w['player_obj']
        except Exception as e:
            print(f"Error populating milestone watch: {e}")
    
    def create_records_section(self, parent_frame):
        """Create records section within player leaders tab"""
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])
        self.records_tabview = self._make_tabview(parent_frame)
        self.records_tabview.pack(fill='both', expand=True,
                                  padx=10, pady=(0, 10))
        for name in self.RECORD_TABS:
            self.records_tabview.add(name)

        # Create record category tabs
        self._create_season_records_tab()
        self._create_career_records_tab()
        self._create_current_leaders_tab()
        self._create_record_chase_tab()
        self._create_achievements_tab()
    
    def create_comprehensive_analytics_tab(self):
        """Create comprehensive analytics tab combining analytics, trends, and insights"""
        ct = self._ct
        analytics_frame = self.tabview.tab("Analytics & Trends")
        analytics_frame.configure(fg_color=ct['PANEL'])

        # Sub-tabs for different analytics views
        self.analytics_tabview = self._make_tabview(analytics_frame)
        self.analytics_tabview.pack(fill='both', expand=True,
                                    padx=10, pady=10)
        for name in self.ANALYTICS_TABS:
            self.analytics_tabview.add(name)

        # Analytics Dashboard
        dashboard_frame = self.analytics_tabview.tab("Dashboard")
        dashboard_frame.configure(fg_color=ct['PANEL'])
        self.create_analytics_dashboard_content(dashboard_frame)

    def _analytics_tab(self, name):
        """Return the content frame for an analytics sub-tab."""
        frame = self.analytics_tabview.tab(name)
        frame.configure(fg_color=self._ct['PANEL'])
        return frame

        # Trends Analysis
        trends_frame = self.analytics_tabview.tab("Trends")
        trends_frame.configure(fg_color=ct['PANEL'])
        self.create_trends_analysis_content(trends_frame)

        # Performance Insights
        insights_frame = self.analytics_tabview.tab("Insights")
        insights_frame.configure(fg_color=ct['PANEL'])
        self.create_performance_insights_content(insights_frame)
    
    def create_records_tab(self):
        """Create NHL Records tab with comprehensive record tracking"""
        records_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=15)
        self.notebook.add(records_frame, text="NHL Records")
        
        # Professional header
        header_frame = ttk.Frame(records_frame, style='Panel.TFrame')
        header_frame.pack(fill='x', pady=(0, 20))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title and description
        title_container = ttk.Frame(header_frame, style='Panel.TFrame')
        title_container.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(title_container, text="NHL Records & Achievements", 
                               font=_sfont(self.app.FONT_FAMILY, 16, 'bold'),
                               foreground='#FFFFFF', background=self.app.BG_COLOR)
        title_label.pack(anchor='w')
        
        desc_label = ttk.Label(title_container, text="Track legendary performances and chase greatness",
                              font=_sfont(self.app.FONT_FAMILY, 10),
                              foreground='#B0B0B0', background=self.app.BG_COLOR)
        desc_label.pack(anchor='w', pady=(3, 0))
        
        # Stats summary
        stats_frame = ttk.Frame(header_frame, style='Panel.TFrame')
        stats_frame.grid(row=0, column=2, sticky="e")
        
        try:
            record_manager = self.app.game_manager.record_manager
            total_records = len(record_manager.nhl_records.season_records) + len(record_manager.nhl_records.career_records)
            stats_text = f"{total_records} Official NHL Records"
            if hasattr(record_manager, 'achievements') and record_manager.achievements:
                stats_text += f" • {len(record_manager.achievements)} Achievements"
        except:
            stats_text = "Official NHL Records Database"
            
        stats_label = ttk.Label(stats_frame, text=stats_text,
                               font=_sfont(self.app.FONT_FAMILY, 9),
                               foreground='#888888', background=self.app.BG_COLOR)
        stats_label.pack(anchor='e')
        
        # Enhanced toolbar
        toolbar_frame = ttk.Frame(records_frame, style='Panel.TFrame')
        toolbar_frame.pack(fill='x', pady=(0, 15))
        toolbar_frame.grid_columnconfigure(1, weight=1)
        
        # Search functionality
        search_container = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        search_container.grid(row=0, column=0, sticky="w")
        
        ttk.Label(search_container, text="Search:", 
                 font=_sfont(self.app.FONT_FAMILY, 9), foreground=self.app.TEXT_COLOR,
                 background=self.app.BG_COLOR).pack(side='left', padx=(0, 5))
        
        self.records_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_container, textvariable=self.records_search_var,
                                font=_sfont(self.app.FONT_FAMILY, 9), width=25)
        search_entry.pack(side='left', padx=(0, 20))
        
        # Category filter
        filter_container = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        filter_container.grid(row=0, column=1, sticky="")
        
        ttk.Label(filter_container, text="Category:",
                 font=_sfont(self.app.FONT_FAMILY, 9), foreground=self.app.TEXT_COLOR,
                 background=self.app.BG_COLOR).pack(side='left', padx=(0, 5))
        
        self.records_filter_var = tk.StringVar(value="All Records")
        filter_combo = ttk.Combobox(filter_container, textvariable=self.records_filter_var,
                                   values=["All Records", "Scoring", "Goaltending", "Team Records"],
                                   state="readonly", font=_sfont(self.app.FONT_FAMILY, 9), width=15)
        filter_combo.pack(side='left')
        
        # Refresh button
        refresh_container = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        refresh_container.grid(row=0, column=2, sticky="e")
        
        refresh_btn = ttk.Button(refresh_container, text="Refresh",
                                style='TButton', command=self.refresh_records_data)
        refresh_btn.pack(side='left')
        
        # Records notebook for different categories
        self.records_notebook = ttk.Notebook(records_frame)
        self.records_notebook.pack(fill='both', expand=True)
        
        # Create record category tabs
        self._create_season_records_tab()
        self._create_career_records_tab()
        self._create_current_leaders_tab()
        self._create_record_chase_tab()
        self._create_achievements_tab()
        
    def _create_season_records_tab(self):
        """Create season records tab"""
        ct = self._ct
        season_frame = self.records_tabview.tab("Season Records")
        season_frame.configure(fg_color=ct['PANEL'])

        # Scrollable content (inner frame is what gets repopulated)
        self.season_scrollable_frame = self._scroll_area(season_frame)

        # Populate with season records
        self._populate_season_records()

    def _create_career_records_tab(self):
        """Create career records tab"""
        ct = self._ct
        career_frame = self.records_tabview.tab("Career Records")
        career_frame.configure(fg_color=ct['PANEL'])

        # Scrollable content (inner frame is what gets repopulated)
        self.career_scrollable_frame = self._scroll_area(career_frame)

        # Populate with career records
        self._populate_career_records()

    def _create_current_leaders_tab(self):
        """Create current season leaders tab"""
        ct = self._ct
        leaders_frame = self.records_tabview.tab("Current Leaders")
        leaders_frame.configure(fg_color=ct['PANEL'])

        # Create treeview for current leaders (packed -- the legacy build
        # created this tree but never packed it, so it was invisible)
        columns = {
            'rank': ('Rank', 50),
            'player': ('Player', 180),
            'team': ('Team', 120),
            'position': ('Pos', 60),
            'stat': ('Stat', 100),
            'value': ('Value', 80)
        }

        self.current_leaders_tree = self._pack_parent_tree(
            leaders_frame, columns, height=20, padx=10, pady=10)

        # Populate with current season leaders
        self._populate_current_leaders()

    def _create_record_chase_tab(self):
        """Create record chase tracking tab"""
        ct = self._ct
        chase_frame = self.records_tabview.tab("Record Chase")
        chase_frame.configure(fg_color=ct['PANEL'])

        # Header with explanation
        header_frame = ctk.CTkFrame(chase_frame, fg_color="transparent")
        header_frame.pack(fill='x', padx=10, pady=(10, 8))

        self._body(header_frame,
                   text="Players currently chasing NHL records (25%+ progress toward record)",
                   dim=True, size=11).pack(anchor='w')

        # Create treeview for record chase (packed -- invisible in legacy)
        columns = {
            'rank': ('Rank', 50),
            'player': ('Player', 180),
            'team': ('Team', 120),
            'position': ('Pos', 60),
            'record': ('Record', 100),
            'current': ('Current', 80),
            'target': ('Target', 80),
            'needed': ('Needed', 80),
            'progress': ('Progress', 80)
        }

        self.record_chase_tree = self._pack_parent_tree(
            chase_frame, columns, height=18, padx=10, pady=(0, 10))

        # Populate with record chase data
        self._populate_record_chase()

    def _create_achievements_tab(self):
        """Create achievements and recent records tab"""
        ct = self._ct
        achievements_frame = self.records_tabview.tab("Achievements")
        achievements_frame.configure(fg_color=ct['PANEL'])

        # Create treeview for achievements (packed -- invisible in legacy)
        columns = {
            'date': ('Date', 100),
            'player': ('Player', 180),
            'team': ('Team', 120),
            'record': ('Record', 200),
            'value': ('New Value', 100),
            'previous': ('Previous', 100)
        }

        self.achievements_tree = self._pack_parent_tree(
            achievements_frame, columns, height=20, padx=10, pady=10)

        # Populate with achievements
        self._populate_achievements()
    
    def create_analytics_dashboard_tab(self):
        """Create advanced analytics dashboard"""
        analytics_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(analytics_frame, text="Analytics")
        
        # Dashboard grid
        analytics_frame.grid_rowconfigure(0, weight=1)
        analytics_frame.grid_rowconfigure(1, weight=1)
        analytics_frame.grid_columnconfigure(0, weight=1)
        analytics_frame.grid_columnconfigure(1, weight=1)
        
        # Top left: League trends
        trends_panel = self.create_analytics_panel(analytics_frame, "League Trends", 0, 0)
        self.populate_trends_panel(trends_panel)
        
        # Top right: Statistical outliers
        outliers_panel = self.create_analytics_panel(analytics_frame, "Statistical Outliers", 0, 1)
        self.populate_outliers_panel(outliers_panel)
        
        # Bottom left: Performance predictors
        predictors_panel = self.create_analytics_panel(analytics_frame, "Performance Indicators", 1, 0)
        self.populate_predictors_panel(predictors_panel)
        
        # Bottom right: Advanced metrics
        metrics_panel = self.create_analytics_panel(analytics_frame, "Advanced Metrics", 1, 1)
        self.populate_metrics_panel(metrics_panel)
    
    def create_trends_analysis_tab(self):
        """Create trends and momentum analysis tab"""
        trends_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(trends_frame, text="Trends")
        
        # Time period selector
        period_frame = ttk.Frame(trends_frame, style='Panel.TFrame')
        period_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(period_frame, text="Analysis Period:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.trend_period = tk.StringVar(value="Last 20 Games")
        period_combo = ttk.Combobox(period_frame, textvariable=self.trend_period,
                                   values=["Last 10 Games", "Last 20 Games", "Last Month", "Season"],
                                   state="readonly", width=15)
        period_combo.pack(side='left', padx=(0, 15))
        period_combo.bind('<<ComboboxSelected>>', self.update_trends_analysis)
        
        # Main trends display
        self.trends_container = ttk.Frame(trends_frame, style='Panel.TFrame')
        self.trends_container.pack(fill='both', expand=True)
        
        self.populate_trends_analysis()
    
    def create_division_analysis_tab(self):
        """Create enhanced division analysis tab"""
        ct = self._ct
        division_frame = self.tabview.tab("Division Analysis")
        division_frame.configure(fg_color=ct['PANEL'])

        # Controls card
        controls = self._card(division_frame)
        controls.pack(fill='x', padx=10, pady=(10, 8))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill='x', padx=12, pady=10)

        self._body(row, text="Division:", dim=True, size=11).pack(side='left',
                                                                  padx=(0, 6))
        self.division_view = tk.StringVar(value="All Divisions")
        self._combo(row, variable=self.division_view,
                    values=["All Divisions", "Atlantic", "Metropolitan",
                            "Central", "Pacific"],
                    command=self.update_division_analysis,
                    width=150).pack(side='left', padx=(0, 15))

        # Analysis type
        self._body(row, text="Analysis:", dim=True, size=11).pack(side='left',
                                                                   padx=(0, 6))
        self.div_analysis_type = tk.StringVar(value="Standings")
        self._combo(row, variable=self.div_analysis_type,
                    values=["Standings", "Head-to-Head",
                            "Strength of Schedule", "Division vs League"],
                    command=self.update_division_analysis,
                    width=180).pack(side='left')

        # Division analysis display
        self.division_container = ctk.CTkFrame(division_frame,
                                               fg_color="transparent")
        self.division_container.pack(fill='both', expand=True,
                                     padx=10, pady=(0, 10))

        self.populate_division_analysis()

    def create_divisions_grid_tab(self):
        """Create 2x2 grid tab showing all 4 divisions"""
        ct = self._ct
        division_frame = self.tabview.tab("Divisions")
        division_frame.configure(fg_color=ct['PANEL'])

        # Create a grid layout for all 4 divisions
        self.create_division_grid(division_frame)
    
    def populate_standings(self):
        """Populate the standings with current data"""
        # Clear existing content
        for widget in self.standings_container.winfo_children():
            widget.destroy()
        
        # Get standings data from the dashboard system
        try:
            if hasattr(self.app, 'atmospheric_dashboard'):
                standings_data = self.app.atmospheric_dashboard._get_standings_data()
            else:
                standings_data = self.get_standings_data()
            
            # Create standings tables
            if self.standings_view.get() == "Both Conferences":
                self.create_conference_standings(self.standings_container, standings_data)
            else:
                selected_conf = self.standings_view.get()
                filtered_data = {k: v for k, v in standings_data.items() if selected_conf.split()[0] in k}
                self.create_conference_standings(self.standings_container, filtered_data)
                
        except Exception as e:
            error_label = ttk.Label(self.standings_container, 
                                   text=f"Error loading standings: {e}", 
                                   style='TLabel')
            error_label.pack(pady=20)
    
    def create_conference_standings(self, parent, standings_data):
        """Create standings tables for conferences/divisions"""
        # Create scrollable frame
        canvas = tk.Canvas(parent, bg=self.app.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create standings for each division/conference
        row = 0
        for division_name, teams in standings_data.items():
            # Division header
            division_label = ttk.Label(scrollable_frame, text=division_name, 
                                     style='Heading.TLabel')
            division_label.grid(row=row, column=0, columnspan=8, sticky='w', pady=(10, 5), padx=10)
            row += 1
            
            # Column headers
            headers = ['Rank', 'Team', 'GP', 'W', 'L', 'T', 'PTS', 'PCT']
            for col, header in enumerate(headers):
                header_label = ttk.Label(scrollable_frame, text=header, style='Subheading.TLabel')
                header_label.grid(row=row, column=col, sticky='w', padx=5, pady=2)
            row += 1
            
            # Team data
            for rank, team in enumerate(teams, 1):
                # Highlight user team
                style = 'Title.TLabel' if team['name'] == getattr(self.app, 'user_team', {}).get('team_name', '') else 'TLabel'
                
                ttk.Label(scrollable_frame, text=str(rank), style=style).grid(row=row, column=0, sticky='w', padx=5)
                # Team identity chip + name
                _name_cell = ttk.Frame(scrollable_frame)
                _name_cell.grid(row=row, column=1, sticky='w', padx=5)
                if _jersey_chip is not None:
                    try:
                        _jersey_chip(_name_cell, team['name']).pack(side='left', padx=(0, 6))
                    except Exception:
                        pass
                ttk.Label(_name_cell, text=team['name'], style=style).pack(side='left')
                ttk.Label(scrollable_frame, text=str(team['games_played']), style=style).grid(row=row, column=2, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['wins']), style=style).grid(row=row, column=3, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['losses']), style=style).grid(row=row, column=4, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['ties']), style=style).grid(row=row, column=5, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['points']), style=style).grid(row=row, column=6, sticky='w', padx=5)
                
                # Calculate winning percentage
                pct = team['points'] / (team['games_played'] * 2) if team['games_played'] > 0 else 0
                ttk.Label(scrollable_frame, text=f"{pct:.3f}", style=style).grid(row=row, column=7, sticky='w', padx=5)
                row += 1
            
            row += 1  # Add space between divisions
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def populate_team_stats(self):
        """Populate team statistics based on selected category"""
        # Clear existing content
        for widget in self.team_stats_container.winfo_children():
            widget.destroy()
        
        category = self.stats_category.get()
        
        # Create team stats table
        columns = self.get_team_stats_columns(category)
        
        # Create treeview
        tree = ttk.Treeview(self.team_stats_container, columns=list(columns.keys()), 
                           show='headings', height=20)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='w')
            tree.column(col_id, width=width, anchor='w')
        
        # Use real data instead of sample data
        self.populate_team_stats_data(tree, category)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.team_stats_container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_player_leaders_section(self, parent, category):
        """Create a player leaders section for the given category"""
        columns = self.get_player_leaders_columns(category)
        
        # Create treeview
        tree = ttk.Treeview(parent, columns=list(columns.keys()), 
                           show='headings', height=15)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='w')
            tree.column(col_id, width=width, anchor='w')
        
        # Use real data instead of sample data
        self.populate_player_leaders_data(tree, category)
        self._bind_leader_menu(tree)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_division_grid(self, parent):
        """Create a 2x2 grid showing all 4 NHL divisions"""
        # Main grid frame
        grid_frame = ctk.CTkFrame(parent, fg_color="transparent")
        grid_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Configure grid weights
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        # Eastern Conference divisions
        self.create_division_panel(grid_frame, "Eastern - Atlantic", 0, 0)
        self.create_division_panel(grid_frame, "Eastern - Metropolitan", 0, 1)

        # Western Conference divisions
        self.create_division_panel(grid_frame, "Western - Central", 1, 0)
        self.create_division_panel(grid_frame, "Western - Pacific", 1, 1)

    def create_division_panel(self, parent, division_name, row, col):
        """Create a panel for a single division"""
        ct = self._ct
        # Rounded card panel with teal division title
        panel = self._card(parent)
        panel.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)

        self._heading(panel, text=division_name, size=13,
                      text_color=ct['TEAL']).grid(row=0, column=0, columnspan=4,
                                                 sticky='w', padx=12,
                                                 pady=(10, 6))

        # Get division data
        standings_data = self.get_standings_data()
        division_teams = standings_data.get(division_name, [])

        # Create mini standings table
        for i, team in enumerate(division_teams[:8]):  # Limit to 8 teams per division
            r = i + 1
            # Team rank and name
            self._body(panel, text=f"{i+1}.", dim=True,
                       size=11).grid(row=r, column=0, sticky='w',
                                     padx=(12, 4))
            # Team identity chip + name
            _mini_cell = ctk.CTkFrame(panel, fg_color="transparent")
            _mini_cell.grid(row=r, column=1, sticky='w', padx=(0, 10))
            if _jersey_chip is not None:
                try:
                    _jersey_chip(_mini_cell, team['name'], w=34, h=20).pack(side='left', padx=(0, 6))
                except Exception:
                    pass
            self._body(_mini_cell, text=team['name'][:20],
                       size=11).pack(side='left')
            # Record
            self._body(panel, text=team['record'], dim=True,
                       size=11).grid(row=r, column=2, sticky='w',
                                     padx=(0, 5))
            # Points
            self._body(panel, text=f"{team['points']}pts",
                       size=11).grid(row=r, column=3, sticky='e',
                                     padx=(0, 12))
            panel.grid_rowconfigure(r, pad=2)
    
    def get_standings_data(self):
        """Get standings data from the parent application"""
        try:
            # Try to get data from the atmospheric dashboard
            if hasattr(self.app, 'atmospheric_dashboard'):
                data = self.app.atmospheric_dashboard._get_standings_data()
                if isinstance(data, dict):
                    return data
            # Fallback: get data directly from league
            data = self.get_league_standings()
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"Error getting standings data: {e}")
        return self.get_fallback_standings()
    
    def get_league_standings(self):
        """Get standings directly from league data"""
        if not hasattr(self.app, 'league') or not self.app.league:
            return self.get_fallback_standings()
        
        # Get NHL teams
        nhl_teams = [team for team in self.app.league.teams 
                    if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
        
        if not nhl_teams:
            nhl_teams = self.app.league.teams[:32]  # Assume first 32 are NHL
        
        # Group by division
        divisions = {}
        for team in nhl_teams:
            if hasattr(team, 'division') and hasattr(team, 'conference'):
                division_name = f"{team.conference} - {team.division}"
            elif hasattr(team, 'conference'):
                division_name = f"{team.conference} Conference"
            else:
                division_name = "Eastern Conference" if hash(team.team_name) % 2 == 0 else "Western Conference"
            
            if division_name not in divisions:
                divisions[division_name] = []
            
            # Calculate points — prefer league.standings (the canonical record the
            # sim writes via _update_standings_fast); fall back to team attrs.
            ls = (getattr(self.app.league, 'standings', None) or {}).get(team.team_name)
            if ls:
                w, l, otl = ls.get('W', 0), ls.get('L', 0), ls.get('OTL', 0)
                points = ls.get('Points', w * 2 + otl)
                ties = 0
            else:
                w, l = team.wins, team.losses
                ties = getattr(team, 'ties', 0)
                otl = getattr(team, 'ot_losses', 0)
                points = w * 2 + ties + otl

            divisions[division_name].append({
                'name': team.team_name,
                'record': f"{w}-{l}-{ties}" if not ls else f"{w}-{l}-{otl}",
                'points': points,
                'wins': w,
                'losses': l,
                'ties': ties,
                'games_played': w + l + (otl if ls else ties)
            })
        
        # Sort by points
        for division in divisions:
            divisions[division].sort(key=lambda x: (x['points'], x['wins']), reverse=True)
        
        return divisions
    
    def get_fallback_standings(self):
        """Fallback standings data if real data isn't available"""
        # Try to get some real teams first
        teams = self.get_fallback_teams()
        
        eastern_teams = []
        western_teams = []
        
        for i, team in enumerate(teams):
            team_data = {
                'name': team.team_name,
                'record': f"{team.wins}-{team.losses}-{getattr(team, 'ot_losses', 0)}",
                'points': team.wins * 2 + getattr(team, 'ot_losses', 0),
                'wins': team.wins,
                'losses': team.losses,
                'ties': getattr(team, 'ot_losses', 0),
                'games_played': team.wins + team.losses + getattr(team, 'ot_losses', 0)
            }
            
            # Alternate between conferences
            if i % 2 == 0:
                eastern_teams.append(team_data)
            else:
                western_teams.append(team_data)
        
        return {
            "Eastern Conference": eastern_teams[:4],
            "Western Conference": western_teams[:4]
        }
    
    def get_team_stats_columns(self, category):
        """Get column definitions for team stats based on category"""
        base_columns = {
            'team': ('Team Name', 220),
            'gp': ('Games', 60),
        }
        
        if category == "Overall":
            return {**base_columns, 
                   'w': ('Wins', 55), 'l': ('Losses', 65), 't': ('OTL', 50), 'pts': ('Points', 65),
                   'gf': ('Goals For', 80), 'ga': ('Goals Against', 100), 'diff': ('Goal Diff', 80)}
        elif category == "Offense":
            return {**base_columns,
                   'gf': ('Goals For', 80), 'gpg': ('Goals/Game', 85), 'shots': ('Shots/Game', 90), 'pp': ('PP %', 65)}
        elif category == "Defense":
            return {**base_columns,
                   'ga': ('Goals Against', 100), 'gaa': ('Goals Against Avg', 120), 'shots_against': ('Shots Against', 100), 'pk': ('PK %', 65)}
        elif category == "Special Teams":
            return {**base_columns,
                   'pp': ('PowerPlay %', 90), 'pk': ('Penalty Kill %', 110), 'ppg': ('PP Goals', 80), 'shg': ('SH Goals', 80)}
        else:  # Goaltending
            return {**base_columns,
                   'gaa': ('Goals Against Avg', 120), 'sv_pct': ('Save %', 75), 'so': ('Shutouts', 75), 'wins': ('Wins', 55)}
    
    def get_player_leaders_columns(self, category):
        """Get column definitions for player leaders based on category"""
        if category == "scoring":
            return {
                'rank': ('#', 45),
                'name': ('Player Name', 180),
                'team': ('Team', 70),
                'pos': ('Pos', 55),
                'gp': ('GP', 45),
                'g': ('Goals', 55),
                'a': ('Assists', 65),
                'pts': ('Points', 65)
            }
        elif category == "goaltending":
            return {
                'rank': ('#', 45),
                'name': ('Goaltender', 180),
                'team': ('Team', 70),
                'gp': ('Starts', 60),
                'w': ('Wins', 50),
                'l': ('Losses', 60),
                'gaa': ('GAA', 65),
                'sv_pct': ('Save %', 70)
            }
        else:  # rookies
            return {
                'rank': ('#', 45),
                'name': ('Rookie Name', 180),
                'team': ('Team', 70),
                'pos': ('Pos', 55),
                'gp': ('GP', 45),
                'g': ('Goals', 55),
                'a': ('Assists', 65),
                'pts': ('Points', 65)
            }
    
    def populate_team_stats_data(self, tree, category):
        """Populate team stats with real game data"""
        try:
            # Get teams from game manager - properly access league object
            league = getattr(self.app.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                teams = league.teams
            else:
                teams = []
                
            if not teams:
                # Fallback to sample data if no teams available
                self._populate_sample_team_stats(tree)
                return
            
            # Extract real team statistics
            team_stats = []
            for team in teams:
                try:
                    # Extract team statistics
                    games_played = getattr(team, 'games_played', 0)
                    wins = getattr(team, 'wins', 0)
                    losses = getattr(team, 'losses', 0) 
                    overtime_losses = getattr(team, 'ot_losses', 0)
                    points = wins * 2 + overtime_losses
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0)
                    goal_diff = f"+{goals_for - goals_against}" if goals_for > goals_against else str(goals_for - goals_against)
                    
                    team_name = getattr(team, 'name', getattr(team, 'team_name', 'Unknown Team'))
                    team_stats.append((team_name, games_played, wins, losses, overtime_losses, points, goals_for, goals_against, goal_diff))
                    
                except Exception as e:
                    print(f"Error processing team {getattr(team, 'name', getattr(team, 'team_name', 'Unknown'))}: {e}")
                    continue
            
            # Sort by points (descending)
            team_stats.sort(key=lambda x: x[5], reverse=True)
            
            # Populate tree with real data
            for team_data in team_stats:
                tree.insert('', 'end', values=team_data)
                
        except Exception as e:
            print(f"Error populating team stats: {e}")
            # Fallback to sample data
            self._populate_sample_team_stats(tree)
    
    def _populate_sample_team_stats(self, tree):
        """Fallback method using real teams with calculated stats"""
        try:
            # Try to get some real teams first
            sample_teams = []
            if hasattr(self.app, 'league') and self.app.league.teams:
                real_teams = self.app.league.teams[:8]  # Take first 8 teams
                
                for team in real_teams:
                    # Use real team data if available, fallback to 0 for missing stats
                    games_played = team.games_played
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0)
                    goal_diff = goals_for - goals_against
                    
                    team_data = (
                        team.team_name,
                        games_played,
                        team.wins,
                        team.losses,
                        getattr(team, 'ot_losses', 0),
                        team.points,
                        goals_for,
                        goals_against,
                        f"+{goal_diff}" if goal_diff >= 0 else str(goal_diff)
                    )
                    sample_teams.append(team_data)
            
            # If no real teams available, create minimal fallback display
            if not sample_teams:
                sample_teams = [
                    ("Loading teams...", 0, 0, 0, 0, 0, 0, 0, "0"),
                    ("Season starting...", 0, 0, 0, 0, 0, 0, 0, "0"),
                ]
                
        except Exception as e:
            print(f"Error creating team stats fallback: {e}")
            sample_teams = [
                ("Data loading...", 0, 0, 0, 0, 0, 0, 0, "0"),
            ]
        
        for team_data in sample_teams:
            tree.insert('', 'end', values=team_data)
    
    def populate_player_leaders_data(self, tree, category):
        """Populate player leaders with real game data"""
        # Get all players from all teams
        if hasattr(self.app, 'tree_maps'):
            self.app.tree_maps.setdefault(tree, {}).clear()
        all_players = []
        
        try:
            # Get teams from game manager
            teams = []
            if hasattr(self.app.game_manager, 'league'):
                if hasattr(self.app.game_manager.league, 'teams'):
                    teams = self.app.game_manager.league.teams
                elif hasattr(self.app.game_manager.league, 'leagues'):
                    for league in self.app.game_manager.league.leagues:
                        if hasattr(league, 'name') and "National Hockey League" in league.name:
                            teams = league.teams
                            break
            
            # Collect all players
            for team in teams:
                if hasattr(team, 'roster') and team.roster:
                    for player in team.roster:
                        all_players.append({
                            'player': player,
                            'team_name': team.team_name
                        })
        
        except Exception as e:
            print(f"Error getting player data: {e}")
            # Fall back to real data with enhanced search
            self._populate_real_player_data(tree, category)
            return
        
        if not all_players:
            # Fall back to real data if no players found
            self._populate_real_player_data(tree, category)
            return
        
        # Sort and display based on category
        if category == "scoring":
            # Sort by points (goals + assists) from real player stats
            all_players.sort(key=lambda p: getattr(p['player'], 'goals', 0)
                           + getattr(p['player'], 'assists', 0), reverse=True)
            
            for i, player_data in enumerate(all_players[:20], 1):  # Top 20
                player = player_data['player']
                team_abbr = self._get_team_abbreviation(player_data['team_name'])
                
                # Real season stats live directly on the player object.
                goals = getattr(player, 'goals', 0)
                assists = getattr(player, 'assists', 0)
                points = goals + assists
                games_played = getattr(player, 'games_played', 0)
                
                # Show all players, including those with 0 stats at season start
                position_str = str(getattr(player, 'primary_position', 'C'))
                if '.' in position_str:
                    position_str = position_str.split('.')[-1]
                
                _plid = tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', f"{getattr(player, 'first_name', 'Unknown')} {getattr(player, 'last_name', 'Player')}"),
                    team_abbr,
                    position_str,
                    games_played,
                    goals,
                    assists,
                    points
                ))
                if hasattr(self.app, 'tree_maps'):
                    self.app.tree_maps[tree][_plid] = player
                    
        elif category == "goaltending":
            # Filter for goalies and sort by wins
            goalies = [p for p in all_players if self._is_goalie(p['player'])]
            goalies.sort(key=lambda p: (getattr(p['player'], 'wins', 0),
                                        getattr(p['player'], 'save_percentage', 0)),
                         reverse=True)
            
            for i, player_data in enumerate(goalies[:15], 1):  # Top 15 goalies
                player = player_data['player']
                team_abbr = self._get_team_abbreviation(player_data['team_name'])
                
                # Get real stats if available
                # Real season stats live directly on the player object.
                games_played = getattr(player, 'games_played', 0)
                wins = getattr(player, 'wins', 0)
                losses = getattr(player, 'losses', 0)
                gaa = getattr(player, 'goals_against_avg', 0.0)
                sv = getattr(player, 'save_percentage', 0.0)
                sa = getattr(player, 'shots_against', 0)
                save_pct = f"{sv:.3f}"[1:] if sa > 0 else ".000"

                # Show all goalies, including those with 0 games at season start
                _plid = tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', f"{getattr(player, 'first_name', 'Unknown')} {getattr(player, 'last_name', 'Player')}"),
                    team_abbr,
                    games_played,
                    wins,
                    losses,
                    f"{gaa:.2f}" if games_played > 0 else "0.00",
                    save_pct
                ))
                if hasattr(self.app, 'tree_maps'):
                    self.app.tree_maps[tree][_plid] = player
                    
        else:  # rookies
            # Filter for young players (age < 24) and sort by points
            rookies = [p for p in all_players if getattr(p['player'], 'age', 30) < 24]
            rookies.sort(key=lambda p: getattr(p['player'], 'goals', 0) + getattr(p['player'], 'assists', 0), reverse=True)
            
            for i, player_data in enumerate(rookies[:15], 1):  # Top 15 rookies
                player = player_data['player']
                team_abbr = self._get_team_abbreviation(player_data['team_name'])
                goals = getattr(player, 'goals', 0)
                assists = getattr(player, 'assists', 0)
                points = goals + assists
                games_played = getattr(player, 'games_played', 0)
                
                # Show all rookies, including those with 0 stats at season start
                _plid = tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', 'Unknown'),
                    team_abbr,
                    getattr(player, 'primary_position', 'C'),
                    games_played,
                    goals,
                    assists,
                    points
                ))
                if hasattr(self.app, 'tree_maps'):
                    self.app.tree_maps[tree][_plid] = player
    
    def _get_team_abbreviation(self, team_name):
        """Get team abbreviation from full name"""
        abbreviations = {
            'Boston Bruins': 'BOS',
            'Buffalo Sabres': 'BUF',
            'Detroit Red Wings': 'DET',
            'Montreal Canadiens': 'MTL',
            'Toronto Maple Leafs': 'TOR',
            'Tampa Bay Lightning': 'TBL',
            'Pittsburgh Penguins': 'PIT',
            'Chicago Blackhawks': 'CHI',
            'Colorado Avalanche': 'COL',
            'Edmonton Oilers': 'EDM',
            'Calgary Flames': 'CGY',
            'Vancouver Canucks': 'VAN',
            'Vegas Golden Knights': 'VGK',
        }
        
        return abbreviations.get(team_name, team_name[:3].upper())
    
    def _populate_real_player_data(self, tree, category):
        """Enhanced method that uses real player data and calculates realistic stats"""
        try:
            # Try to get real players from multiple sources
            all_players = []
            
            # Primary source: game manager league
            if hasattr(self.app, 'game_manager') and hasattr(self.app.game_manager, 'league'):
                league = self.app.game_manager.league
                if hasattr(league, 'teams'):
                    for team in league.teams:
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                            if hasattr(team, 'roster'):
                                all_players.extend(team.roster)
            
            # Secondary source: direct league access
            if not all_players and hasattr(self.app, 'league'):
                for team in getattr(self.app.league, 'teams', []):
                    if hasattr(team, 'roster'):
                        all_players.extend(team.roster)
            
            # Tertiary source: user team league
            if not all_players and hasattr(self.app, 'user_team'):
                if hasattr(self.app.user_team, 'league'):
                    for team in getattr(self.app.user_team.league, 'teams', []):
                        if hasattr(team, 'roster'):
                            all_players.extend(team.roster)
            
            if all_players:
                # Sort players by their current stats or calculate from attributes
                if category == "scoring":
                    sorted_players = sorted(all_players, 
                                          key=lambda p: getattr(p, 'points', getattr(p, 'goals', 0) + getattr(p, 'assists', 0)), 
                                          reverse=True)[:20]
                elif category == "goalies":
                    goalies = [p for p in all_players if 'GOALIE' in str(p.primary_position).upper()]
                    sorted_players = sorted(goalies, 
                                          key=lambda p: getattr(p, 'save_percentage', 0.900), 
                                          reverse=True)[:10]
                else:  # breakout or other
                    young_players = [p for p in all_players if p.age <= 25]
                    sorted_players = sorted(young_players, 
                                          key=lambda p: p.overall_rating(), 
                                          reverse=True)[:15]
                
                # Populate with real player data
                for i, player in enumerate(sorted_players, 1):
                    try:
                        if category == "scoring":
                            values = (
                                str(i),
                                player.full_name,
                                getattr(player, 'team_name', 'NHL'),
                                str(player.primary_position),
                                getattr(player, 'goals', 0),
                                getattr(player, 'assists', 0),
                                getattr(player, 'points', getattr(player, 'goals', 0) + getattr(player, 'assists', 0)),
                                getattr(player, 'games_played', 0)
                            )
                        elif category == "goalies":
                            values = (
                                str(i),
                                player.full_name,
                                getattr(player, 'team_name', 'NHL'),
                                getattr(player, 'wins', 0),
                                getattr(player, 'losses', 0),
                                getattr(player, 'saves', 0),
                                f"{getattr(player, 'goals_against_average', 2.50):.2f}",
                                f"{getattr(player, 'save_percentage', 0.900):.3f}"
                            )
                        else:  # breakout
                            values = (
                                str(i),
                                player.full_name,
                                getattr(player, 'team_name', 'NHL'),
                                str(player.primary_position),
                                getattr(player, 'goals', 0),
                                getattr(player, 'assists', 0),
                                getattr(player, 'points', getattr(player, 'goals', 0) + getattr(player, 'assists', 0)),
                                player.age
                            )
                        
                        _plid = tree.insert('', 'end', values=values)
                        if hasattr(self.app, 'tree_maps'):
                            self.app.tree_maps.setdefault(tree, {})[_plid] = player
                        
                    except Exception as e:
                        print(f"Error adding player {player.full_name}: {e}")
                        continue
                        
                return  # Successfully populated with real data
                
        except Exception as e:
            print(f"Error getting real player data: {e}")
        
        # If all else fails, use calculated data from available teams
        self._populate_calculated_player_data(tree, category)
    
    def _populate_calculated_player_data(self, tree, category):
        """Generate calculated player data from available team information - starts at 0 for new season"""
        try:
            # Get teams and show placeholder data with 0 stats for new season
            teams = self.get_fallback_teams()[:8]
            rank = 1
            
            for team in teams:
                # Generate 2-3 players per team with 0 stats for season start
                for i in range(3):  # 3 players per team
                    if rank > 20:  # Limit to top 20
                        break
                        
                    player_name = f"{team.team_name} Player {i+1}"
                    
                    if category == "scoring":
                        # Start season with 0 stats
                        goals = 0
                        assists = 0
                        points = 0
                        games = 0
                        
                        values = (str(rank), player_name, team.team_name, "C", goals, assists, points, games)
                    elif category == "goalies":
                        if i == 0:  # Only one goalie per team
                            wins = 0
                            losses = 0
                            saves = 0
                            gaa = 0.00
                            sv_pct = 0.000
                            
                            values = (str(rank), player_name, team.team_name, wins, losses, saves, f"{gaa:.2f}", f"{sv_pct:.3f}")
                        else:
                            continue
                    else:  # breakout
                        goals = 0
                        assists = 0
                        points = 0
                        age = 20 + i
                        
                        values = (str(rank), player_name, team.team_name, "C", goals, assists, points, age)
                    
                    tree.insert('', 'end', values=values)
                    rank += 1
                    
        except Exception as e:
            print(f"Error generating calculated player data: {e}")
            # Final fallback - minimal data display
            tree.insert('', 'end', values=("--", "No data available", "---", "---", 0, 0, 0, 0))
                                # Base games on player skill and team performance
    def update_standings_view(self, event=None):
        """Update standings view when selection changes"""
        self.populate_enhanced_standings()
    
    def update_team_stats_view(self, event=None):
        """Update team stats view when category changes"""
        self.populate_advanced_team_stats()
    
    def refresh_all_data(self):
        """Refresh all data in the window"""
        try:
            # Update current status
            self.status_label.configure(text="Refreshing data...")
            self.update()

            # Refresh based on current tab.
            # Fixed: tab indices 4/5 were miswired (4 refreshed Trends while
            # showing Division Analysis, 5 refreshed Division Analysis while
            # showing the static Divisions grid).
            current_tab = self.MAIN_TABS.index(self.tabview.get())
            if current_tab == 0:  # Standings
                self.populate_enhanced_standings()
            elif current_tab == 1:  # Team Analytics
                self.populate_advanced_team_stats()
            elif current_tab == 2:  # Player Leaders
                self.update_player_leaders()
                if hasattr(self, 'milestone_tree'):
                    self._populate_milestone_watch()
            elif current_tab == 3:  # Analytics & Trends
                self.create_analytics_dashboard_content(
                    self._analytics_tab("Dashboard"))
                self.create_trends_analysis_content(
                    self._analytics_tab("Trends"))
                self.create_performance_insights_content(
                    self._analytics_tab("Insights"))
            elif current_tab == 4:  # Division Analysis
                self.update_division_analysis()
            elif current_tab == 5:  # Divisions (static grid, populated at creation)
                pass

            # Update timestamp
            current_time = datetime.now().strftime("%H:%M:%S")
            self.status_label.configure(text=f"Last updated: {current_time}")

        except Exception as e:
            self.status_label.configure(text=f"Error refreshing data: {str(e)}")
    
    def export_data(self):
        """Export current data to file"""
        try:
            from datetime import datetime
            import csv
            import os

            # Get current tab and data
            current_tab = self.tabview.get()

            # Define export filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hockey_stats_{current_tab.lower().replace(' ', '_')}_{timestamp}.csv"

            # Get the appropriate data based on current tab
            if current_tab == "League Leaders":
                data = self.get_current_leaders_data()
                headers = ["Rank", "Player", "Team", "Position", "Goals", "Assists", "Points", "Games"]
            elif current_tab == "Team Standings":
                data = self.get_current_standings_data()
                headers = ["Rank", "Team", "GP", "W", "L", "OT", "Points", "GF", "GA", "Diff"]
            elif current_tab == "Advanced Stats":
                data = self.get_current_advanced_data()
                headers = ["Rank", "Player", "Team", "Position", "Corsi", "Fenwick", "PDO", "TOI/G"]
            else:
                # General export for other tabs
                data = self.get_current_view_data()
                headers = ["Data exported from", current_tab]

            if data:
                # Create exports directory if it doesn't exist
                exports_dir = "exports"
                if not os.path.exists(exports_dir):
                    os.makedirs(exports_dir)

                filepath = os.path.join(exports_dir, filename)

                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                    writer.writerows(data)

                messagebox.showinfo("Export Successful",
                                    f"Data exported to:\n{filepath}\n\n{len(data)} records exported.")
            else:
                messagebox.showwarning("Export Warning", "No data available to export.")

        except Exception as e:
            print(f"Error exporting data: {e}")
            messagebox.showerror("Export Error", f"Failed to export data:\n{str(e)}")
    
    def get_current_leaders_data(self):
        """Get current leaders data for export"""
        try:
            # Get the data from the current page
            current_tree = getattr(self, 'current_leaders_tree', None)
            if current_tree:
                data = []
                for child in current_tree.get_children():
                    values = current_tree.item(child)['values']
                    data.append(values)
                return data
        except:
            pass
        return []
    
    def get_current_standings_data(self):
        """Get current standings data for export"""
        try:
            # Export team standings
            data = []
            rank = 1
            for team in sorted(self.app.league.teams, key=lambda t: t.points, reverse=True):
                if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                    data.append([
                        rank,
                        team.team_name,
                        team.games_played,
                        team.wins,
                        team.losses,
                        team.overtimes,
                        team.points,
                        team.goals_for,
                        team.goals_against,
                        team.goal_differential
                    ])
                    rank += 1
            return data
        except:
            return []
    
    def get_current_advanced_data(self):
        """Get current advanced stats data for export"""
        try:
            # Export advanced stats data
            data = []
            rank = 1
            all_players = []
            
            for team in self.app.league.teams:
                if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                    for player in team.roster:
                        all_players.append(player)
            
            # Sort by some advanced metric (using plus_minus as example)
            sorted_players = sorted(all_players, 
                                  key=lambda p: getattr(p, 'plus_minus', 0), reverse=True)[:50]
            
            for player in sorted_players:
                corsi = getattr(player, 'corsi_for_percent', 50.0)
                fenwick = getattr(player, 'fenwick_for_percent', 50.0)
                pdo = getattr(player, 'pdo', 100.0)
                toi = getattr(player, 'time_on_ice_per_game', 15.0)
                
                data.append([
                    rank,
                    player.full_name,
                    player.team_name,
                    player.primary_position.value if hasattr(player.primary_position, 'value') else str(player.primary_position),
                    f"{corsi:.1f}%",
                    f"{fenwick:.1f}%",
                    f"{pdo:.1f}",
                    f"{toi:.1f}"
                ])
                rank += 1
            
            return data
        except:
            return []
    
    def get_current_view_data(self):
        """Get current view data for export"""
        # Fallback method for general data export
        return [["Export completed", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]
    
    def on_tab_changed(self, event=None):
        """Handle tab change events"""
        try:
            current_tab = self.MAIN_TABS.index(self.tabview.get())
        except (ValueError, AttributeError):
            current_tab = 0
        self.selected_tab = current_tab

        # Load data for the selected tab if not already loaded
        self.load_tab_data(current_tab)

    def on_filter_change(self, value=None):
        """Handle global filter changes"""
        # Update filters dictionary
        self.filters['time_period'] = self.period_combo.get()

        # Refresh current tab data
        self.refresh_all_data()
    
    def load_tab_data(self, tab_index):
        """Load data for specific tab"""
        if tab_index == 0:  # Standings
            self.populate_enhanced_standings()
        elif tab_index == 1:  # Team Stats
            self.populate_advanced_team_stats()
        elif tab_index == 2:  # Player Leaders
            self.update_player_leaders()
        elif tab_index == 3:  # Analytics & Trends
            self.refresh_analytics_dashboard()
        elif tab_index == 4:  # Division Analysis
            self.populate_division_analysis()
        elif tab_index == 5:  # Divisions (static grid, populated once at creation)
            pass
    
    # Enhanced populate methods
    def populate_enhanced_standings(self):
        """Populate enhanced standings with advanced metrics"""
        # Clear existing content
        for widget in self.standings_scrollable.winfo_children():
            widget.destroy()
        
        view_type = self.standings_view.get()
        
        # Create enhanced standings table
        self.create_enhanced_standings_table(self.standings_scrollable, view_type)
    
    def create_enhanced_standings_table(self, parent, view_type):
        """Grid-based standings table.

        Team colors live ONLY in the Team column (ttk.Treeview styles
        whole rows, so per-column color needs a real grid); playoff
        locks get the classic green band in the Playoff column.
        """
        show_advanced = self.show_advanced.get()
        # Ordered (key, title) pairs; every column backed by real data.
        if show_advanced:
            columns = [('rank', 'Rank'), ('team', 'Team'), ('gp', 'GP'),
                       ('w', 'W'), ('l', 'L'), ('otl', 'OTL'),
                       ('pts', 'PTS'), ('pt_pct', 'PT%'), ('gf', 'GF'),
                       ('ga', 'GA'), ('diff', '+/-'), ('playoff', 'Playoff')]
        else:
            columns = [('rank', 'Rank'), ('team', 'Team'), ('gp', 'GP'),
                       ('w', 'W'), ('l', 'L'), ('otl', 'OTL'),
                       ('pts', 'PTS'), ('pt_pct', 'PT%'), ('diff', '+/-')]

        # Build the grid straight into the scroll area's inner frame; the
        # outer CTkScrollableFrame owns the scrollbar (nesting a second
        # canvas+scrollbar inside it collapses the viewport).
        body = parent

        # Header row
        for col, (_key, title) in enumerate(columns):
            tk.Label(body, text=title, bg=self.app.BG_COLOR,
                     fg='#9aa3b2',
                     font=('TkDefaultFont', 9, 'bold')).grid(
                row=0, column=col, sticky='w', padx=6, pady=(4, 8))
        body.grid_columnconfigure(1, weight=1)  # team column stretches

        teams = self._standings_teams()
        # League-wide playoff cut (top 16 by points) for the Playoff column
        league_rank = sorted(teams,
                             key=lambda t: (self._team_points(t), t.wins),
                             reverse=True)
        playoff_names = {t.team_name for t in league_rank[:16]}

        view = (self.standings_view.get()
                if hasattr(self, 'standings_view') else view_type)
        sort = (self.standings_sort.get()
                if hasattr(self, 'standings_sort') else "Points")
        teams = self._apply_standings_view(teams, view)
        teams = self._apply_standings_sort(teams, sort)

        _fg_default = '#e8e8e8'
        for r, team in enumerate(teams, 1):  # Show all teams in view
            try:
                otl = getattr(team, 'ot_losses', 0)
                gp = team.wins + team.losses + otl
                points = self._team_points(team)
                pt_pct = (points / (gp * 2) * 100) if gp > 0 else 0.0
                goals_for = getattr(team, 'goals_for', 0)
                goals_against = getattr(team, 'goals_against', 0)
                goal_diff = goals_for - goals_against
                playoff = "In" if team.team_name in playoff_names else "Out"

                vals = {
                    'rank': str(r),
                    'gp': str(gp),
                    'w': str(team.wins),
                    'l': str(team.losses),
                    'otl': str(otl),
                    'pts': str(points),
                    'pt_pct': f"{pt_pct:.1f}%",
                    'gf': str(goals_for),
                    'ga': str(goals_against),
                    'diff': f"{goal_diff:+d}",
                    'playoff': playoff,
                }

                # Team-true color lives ONLY in the Team column.
                _bg, _fg = self.app.BG_COLOR, _fg_default
                if _accent_for_team is not None:
                    try:
                        _bg, _, _fg = _accent_for_team(team.team_name)
                    except Exception:
                        pass
                for col, (key, _title) in enumerate(columns):
                    if key == 'team':
                        cell = tk.Frame(body, bg=_bg)
                        cell.grid(row=r, column=col, sticky='ew',
                                  padx=2, pady=1)
                        if _jersey_chip is not None:
                            try:
                                _jersey_chip(cell, team.team_name,
                                             w=40, h=22).pack(
                                    side='left', padx=(6, 4), pady=2)
                            except Exception:
                                pass
                        tk.Label(cell, text=team.team_name, bg=_bg, fg=_fg,
                                 font=('TkDefaultFont', 9, 'bold')).pack(
                            side='left', padx=(0, 8), pady=2)
                    elif key == 'playoff' and playoff == "In":
                        # Playoff lock: the classic green band.
                        tk.Label(body, text="In", bg='#166534', fg='#FFFFFF',
                                 font=('TkDefaultFont', 9, 'bold')).grid(
                            row=r, column=col, sticky='ew', padx=2, pady=1)
                    else:
                        tk.Label(body, text=vals[key], bg=self.app.BG_COLOR,
                                 fg=_fg_default).grid(
                            row=r, column=col, sticky='w', padx=6, pady=2)
            except Exception as e:
                print(f"Error processing team {team.team_name}: {e}")
                continue
    
    def _standings_teams(self):
        """NHL teams for standings, with real-team fallback."""
        teams = []
        gm = getattr(self.app, 'game_manager', None)
        league = getattr(gm, 'league', None) if gm else None
        if league is None:
            league = getattr(self.app, 'league', None)
        if league is not None and hasattr(league, 'teams'):
            teams = [t for t in league.teams
                     if getattr(t, 'league_name', 'National Hockey League')
                     == 'National Hockey League']
            if not teams:
                teams = list(league.teams)
        if not teams:
            teams = self.get_fallback_teams()
        return teams

    @staticmethod
    def _team_points(team):
        pts = getattr(team, 'points', None)
        if isinstance(pts, (int, float)):
            return pts
        return team.wins * 2 + getattr(team, 'ot_losses', 0)

    def _apply_standings_view(self, teams, view):
        """Filter teams for the selected standings view."""
        by_points = sorted(teams, key=self._team_points, reverse=True)
        if view == "Eastern Conference":
            return [t for t in by_points
                    if getattr(t, 'conference', '') == 'Eastern']
        if view == "Western Conference":
            return [t for t in by_points
                    if getattr(t, 'conference', '') == 'Western']
        if view == "Wild Card Race":
            out = []
            for conf in ('Eastern', 'Western'):
                conf_teams = [t for t in by_points
                              if getattr(t, 'conference', '') == conf]
                out.extend(conf_teams[3:8])  # wild-card bubble: 4th-8th
            return out
        if view == "Division Leaders":
            seen = {}
            for t in by_points:
                div = getattr(t, 'division', '') or 'Unknown'
                if div not in seen:
                    seen[div] = t
            return [seen[d] for d in sorted(seen)]
        if view == "Playoff Picture":
            out = []
            for conf in ('Eastern', 'Western'):
                conf_teams = [t for t in by_points
                              if getattr(t, 'conference', '') == conf]
                out.extend(conf_teams[:8])
            return out
        return by_points  # League Overview

    def _apply_standings_sort(self, teams, sort):
        if sort == "Wins":
            return sorted(teams, key=lambda t: (t.wins, self._team_points(t)),
                          reverse=True)
        if sort == "Goal Differential":
            return sorted(
                teams,
                key=lambda t: (getattr(t, 'goals_for', 0)
                               - getattr(t, 'goals_against', 0),
                               self._team_points(t)),
                reverse=True)
        return sorted(teams, key=lambda t: (self._team_points(t), t.wins),
                      reverse=True)  # Points

    def get_fallback_teams(self):
        """Get teams from alternative data sources if main source fails"""
        try:
            # Try direct access to parent league
            if hasattr(self.app, 'league') and hasattr(self.app.league, 'teams'):
                teams = [team for team in self.app.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
                if teams:
                    return teams
            
            # Try accessing user team's league
            if hasattr(self.app, 'user_team') and hasattr(self.app.user_team, 'league'):
                teams = getattr(self.app.user_team.league, 'teams', [])
                if teams:
                    return teams
            
            # Try game manager league access
            league = getattr(self.app.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                teams = league.teams
                if teams:
                    return teams
                    
        except Exception as e:
            print(f"Error getting fallback teams: {e}")
        
        # Final fallback - create minimal realistic teams from available data
        from game_classes import Team
        fallback_teams = []
        team_names = ["Boston Bruins", "Toronto Maple Leafs", "Tampa Bay Lightning", "Florida Panthers",
                     "Buffalo Sabres", "Ottawa Senators", "Montreal Canadiens", "Detroit Red Wings"]
        
        for i, name in enumerate(team_names):
            team = Team(team_name=name, city=name, division="Atlantic", conference="Eastern")
            # Set all stats to 0 for season start
            team.wins = 0
            team.losses = 0
            team.goals_for = 0
            team.goals_against = 0
            team.games_played = 0
            fallback_teams.append(team)
        
        return fallback_teams
    
    def populate_advanced_team_stats(self):
        """Populate advanced team statistics"""
        # Clear existing content
        for widget in self.team_stats_container.winfo_children():
            widget.destroy()
        
        category = self.stats_category.get()
        mode = self.stats_mode.get()
        
        self.create_advanced_stats_table(self.team_stats_container, category, mode)
    
    def create_advanced_stats_table(self, parent, category, mode):
        """Create advanced statistics table"""
        columns = self.get_advanced_stats_columns(category)

        # Dark styled table
        tree = self._make_tree(parent, columns, height=20)

        # Use real advanced statistics data
        self.add_advanced_stats_data(tree, category, mode)
    
    def get_advanced_stats_columns(self, category):
        """Get column definitions for advanced stats (all backed by real data)"""
        if self._in_playoff_mode():
            # Playoffs: one honest table -- series record from the bracket.
            # Small samples make the per-category splits noise.
            return {
                'team': ('Team', 170),
                'gp': ('GP', 50),
                'w': ('W', 45),
                'l': ('L', 45),
                'gf': ('GF', 55),
                'ga': ('GA', 55),
                'diff': ('+/-', 60),
                'result': ('Playoff Result', 170),
            }
        if category == "Overall Performance":
            return {
                'team': ('Team', 170),
                'gp': ('GP', 50),
                'w': ('W', 45),
                'l': ('L', 45),
                'otl': ('OTL', 50),
                'pts': ('PTS', 55),
                'pt_pct': ('PT%', 65),
                'gf': ('GF', 55),
                'ga': ('GA', 55),
                'diff': ('+/-', 60),
            }
        elif category == "Offensive Stats":
            return {
                'team': ('Team', 170),
                'gp': ('GP', 50),
                'gf': ('GF', 60),
                'gf_gp': ('GF/GP', 70),
                'shots': ('Shots', 70),
                'sh_pct': ('SH%', 65),
            }
        elif category == "Defensive Stats":
            return {
                'team': ('Team', 170),
                'gp': ('GP', 50),
                'ga': ('GA', 60),
                'ga_gp': ('GA/GP', 70),
                'sa': ('Shots Against', 100),
                'sv_pct': ('Team SV%', 80),
            }
        elif category == "Goaltending":
            return {
                'team': ('Team', 170),
                'gp': ('GP', 50),
                'w': ('W', 45),
                'l': ('L', 45),
                'gaa': ('GAA', 60),
                'sv_pct': ('SV%', 65),
                'so': ('SO', 45),
            }
        else:  # Advanced Analytics
            return {
                'team': ('Team', 170),
                'pt_pct': ('PT%', 65),
                'gf_gp': ('GF/GP', 70),
                'ga_gp': ('GA/GP', 70),
                'diff_gp': ('Diff/GP', 70),
                'pdo': ('PDO', 65),
            }
    
    def _filtered_analytics_teams(self):
        """Teams for the Team Analytics tab, honoring the Teams filter."""
        teams = self._standings_teams()
        filt = self.team_filter.get() if hasattr(self, 'team_filter') else "All Teams"
        if filt == "Eastern Conference":
            teams = [t for t in teams if getattr(t, 'conference', '') == 'Eastern']
        elif filt == "Western Conference":
            teams = [t for t in teams if getattr(t, 'conference', '') == 'Western']
        elif filt == "Division Rivals":
            user_div = getattr(getattr(self.app, 'user_team', None), 'division', '')
            if user_div:
                teams = [t for t in teams if getattr(t, 'division', '') == user_div]
        elif filt == "Playoff Teams":
            teams = sorted(teams, key=self._team_points, reverse=True)[:16]
        return teams

    @staticmethod
    def _team_goalie_totals(team):
        """Aggregate real goalie stats from a team's roster goalies."""
        gp = w = l = ga = sv = sa = so = 0
        for p in getattr(team, 'roster', []) or []:
            try:
                is_g = (p.primary_position.value == 'G')
            except Exception:
                is_g = 'GOALIE' in str(getattr(p, 'primary_position', '')).upper()
            if not is_g:
                continue
            gp += getattr(p, 'games_played', 0)
            w += getattr(p, 'wins', 0)
            l += getattr(p, 'losses', 0)
            ga += getattr(p, 'goals_against', 0)
            sv += getattr(p, 'saves', 0)
            sa += getattr(p, 'shots_against', 0)
            so += getattr(p, 'shutouts', 0)
        return {'gp': gp, 'w': w, 'l': l, 'ga': ga, 'sv': sv, 'sa': sa, 'so': so}

    def add_advanced_stats_data(self, tree, category, mode):
        """Add advanced statistics data (all from real tracked stats)"""
        if self._in_playoff_mode():
            self._add_playoff_team_stats(tree, mode)
            return
        try:
            teams = self._filtered_analytics_teams()
            if not teams:
                teams = self.get_fallback_teams()

            rows = []
            for team in teams:
                team_name = getattr(team, 'team_name',
                                    getattr(team, 'name', 'Unknown Team'))
                gp = getattr(team, 'games_played', 0)
                w = getattr(team, 'wins', 0)
                l = getattr(team, 'losses', 0)
                otl = getattr(team, 'ot_losses', 0)
                pts = self._team_points(team)
                pt_pct = (pts / (gp * 2) * 100) if gp > 0 else 0.0
                gf = getattr(team, 'goals_for', 0)
                ga = getattr(team, 'goals_against', 0)
                diff = gf - ga

                roster = getattr(team, 'roster', []) or []
                shots_for = sum(getattr(p, 'shots', 0) for p in roster)
                gt = self._team_goalie_totals(team)
                sh_pct = (gf / shots_for * 100) if shots_for > 0 else 0.0
                team_sv = (gt['sv'] / gt['sa'] * 100) if gt['sa'] > 0 else 0.0
                gaa = (gt['ga'] / gt['gp']) if gt['gp'] > 0 else 0.0
                pdo = sh_pct + team_sv  # classic PDO scale

                if category == "Overall Performance":
                    values = (team_name, gp, w, l, otl, pts, f"{pt_pct:.1f}%",
                              gf, ga, f"{diff:+d}")
                elif category == "Offensive Stats":
                    values = (team_name, gp, gf,
                              f"{gf / gp:.2f}" if gp > 0 else "0.00",
                              shots_for, f"{sh_pct:.1f}%")
                elif category == "Defensive Stats":
                    values = (team_name, gp, ga,
                              f"{ga / gp:.2f}" if gp > 0 else "0.00",
                              gt['sa'], f"{team_sv:.1f}%" if gt['sa'] > 0 else "—")
                elif category == "Goaltending":
                    values = (team_name, gt['gp'], gt['w'], gt['l'],
                              f"{gaa:.2f}" if gt['gp'] > 0 else "—",
                              f"{team_sv / 100:.3f}"[1:] if gt['sa'] > 0 else "—",
                              gt['so'])
                else:  # Advanced Analytics
                    values = (team_name, f"{pt_pct:.1f}%",
                              f"{gf / gp:.2f}" if gp > 0 else "0.00",
                              f"{ga / gp:.2f}" if gp > 0 else "0.00",
                              f"{diff / gp:+.2f}" if gp > 0 else "+0.00",
                              f"{pdo:.1f}" if shots_for > 0 and gt['sa'] > 0 else "—")
                rows.append((team_name, values))

            # Sort: most informative first per category
            if category in ("Offensive Stats",):
                rows.sort(key=lambda r: r[1][2], reverse=True)
            elif category in ("Defensive Stats", "Goaltending"):
                rows.sort(key=lambda r: r[1][2])
            else:
                team_by_name = {t.team_name: t for t in teams}
                rows.sort(key=lambda r: self._team_points(team_by_name[r[0]])
                          if r[0] in team_by_name else 0, reverse=True)

            for _name, values in rows:
                tree.insert('', 'end', values=values)

            if mode == "vs League Average" and rows:
                cols = len(rows[0][1])
                avgs = []
                for c in range(1, cols):
                    nums = []
                    for _n, vals in rows:
                        try:
                            v = str(vals[c]).replace('%', '').replace('+', '')
                            nums.append(float(v))
                        except (ValueError, TypeError):
                            pass
                    avgs.append(f"{sum(nums) / len(nums):.2f}" if nums else "—")
                tree.insert('', 'end',
                            values=("LEAGUE AVG",) + tuple(avgs),
                            tags=('avg',))
                tree.tag_configure('avg', background='#1f2937',
                                   foreground='#9CA3AF')

        except Exception as e:
            print(f"Error adding advanced stats data: {e}")
            # Fallback to basic calculated data
            self._add_calculated_advanced_stats(tree, category)
    
    def _add_playoff_team_stats(self, tree, mode):
        """Playoff-mode Team Analytics: series record per playoff team.

        Built read-only from the bracket's per-game results -- no new
        stored data. Non-playoff teams don't appear: they played zero
        playoff games.
        """
        try:
            pstats = self.get_team_playoff_stats()
            rows = []
            for team_name, e in pstats.items():
                gp, w, l = e["GP"], e["W"], e["L"]
                gf, ga = e["GF"], e["GA"]
                diff = gf - ga
                rows.append((team_name,
                             (team_name, gp, w, l, gf, ga, f"{diff:+d}",
                              e["result"] or "—")))
            # Sort: wins first, then goal differential.
            rows.sort(key=lambda r: (r[1][2], r[1][4] - r[1][5]),
                      reverse=True)
            if not rows:
                tree.insert('', 'end', values=(
                    "No playoff games played yet", "", "", "", "", "", "",
                    ""))
                return
            for _name, values in rows:
                tree.insert('', 'end', values=values)
        except Exception as e:
            print(f"Error adding playoff team stats: {e}")

    def _add_calculated_advanced_stats(self, tree, category):
        """Fallback: basic real team data if the main loader fails."""
        teams = self._standings_teams()[:8]
        for team in teams:
            try:
                otl = getattr(team, 'ot_losses', 0)
                gp = team.wins + team.losses + otl
                pts = self._team_points(team)
                gf = getattr(team, 'goals_for', 0)
                ga = getattr(team, 'goals_against', 0)
                tree.insert('', 'end', values=(
                    team.team_name, gp, team.wins, team.losses, otl, pts,
                    gf, ga, f"{gf - ga:+d}"))
            except Exception as e:
                print(f"Error calculating stats for {team.team_name}: {e}")
                continue
    
    def create_enhanced_player_section(self, parent, category):
        """Create enhanced player leaders section with pagination"""
        ct = self._ct
        parent.configure(fg_color=ct['PANEL'])
        # Initialize pagination data for this category if not exists
        if not hasattr(self, 'pagination_data'):
            self.pagination_data = {}

        if category not in self.pagination_data:
            self.pagination_data[category] = {
                'current_page': 1,
                'players_per_page': 50,  # Show more players by default
                'total_players': 0,
                'all_players': []
            }

        # Create main container
        main_container = ctk.CTkFrame(parent, fg_color="transparent")
        main_container.pack(fill="both", expand=True)

        # Create pagination controls at top
        pagination_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        pagination_frame.pack(fill="x", padx=10, pady=(10, 6))

        # Page info and controls
        self.create_pagination_controls(pagination_frame, category)

        # Honest model-estimate labeling: these tabs show modeled metrics
        # (ixG, xGF%, GSAx, ...), not tracked truth. Same disclosure as
        # the player card's analytics section.
        if category in ("advanced", "breakout", "goaltending"):
            ctk.CTkLabel(
                main_container,
                text=("Estimates, not tracking data: ixG / xGF% / GSAx / HDSV% "
                      "are modeled from your analytics department's lens -- "
                      "useful signal, not measured fact."),
                font=ctk.CTkFont(size=11, slant="italic"),
                text_color=ct['TEXT_DIM'], wraplength=900,
                justify="left").pack(fill="x", padx=12, pady=(0, 4))

        # Create treeview container
        tree_container = ctk.CTkFrame(main_container, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = self.get_enhanced_player_columns(category)

        # Dark styled table with pagination
        tree = self._make_tree(tree_container, columns, height=20)

        # Store tree reference for pagination updates
        self.pagination_data[category]['tree'] = tree

        # Add keyboard bindings for pagination
        tree.bind('<Prior>', lambda e: self.go_to_page(category, self.pagination_data[category]['current_page'] - 1))  # Page Up
        tree.bind('<Next>', lambda e: self.go_to_page(category, self.pagination_data[category]['current_page'] + 1))   # Page Down
        tree.bind('<Home>', lambda e: self.go_to_page(category, 1))  # Home key
        tree.bind('<End>', lambda e: self.go_to_last_page(category))  # End key
        tree.focus_set()  # Allow tree to receive keyboard events

        # Load and display first page of data
        self.load_all_players_data(category)
        self.update_page_display(category)

    def create_pagination_controls(self, parent, category):
        """Create pagination controls for player stats"""
        # Left side - page info
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.pack(side="left")

        page_label = self._body(info_frame, text="", dim=True, size=11)
        page_label.pack(side="left", padx=(0, 20))

        # Store reference for updates
        self.pagination_data[category]['page_label'] = page_label

        # Center - navigation buttons
        nav_frame = ctk.CTkFrame(parent, fg_color="transparent")
        nav_frame.pack(side="left", expand=True)

        # First page button
        first_btn = self._secondary_button(nav_frame, text="First", width=64,
                                           command=lambda: self.go_to_page(category, 1))
        first_btn.pack(side="left", padx=2)

        # Previous page button
        prev_btn = self._secondary_button(nav_frame, text="Previous", width=80,
                                          command=lambda: self.go_to_page(category,
                                          self.pagination_data[category]['current_page'] - 1))
        prev_btn.pack(side="left", padx=2)

        # Page number entry
        page_entry_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
        page_entry_frame.pack(side="left", padx=10)

        self._body(page_entry_frame, text="Page:", dim=True,
                   size=11).pack(side="left")
        page_entry = ctk.CTkEntry(page_entry_frame, width=44, justify='center',
                                  fg_color=self._ct['PANEL'],
                                  border_color=self._ct['BORDER'],
                                  text_color=self._ct['TEXT'],
                                  font=(self._ff, 11))
        page_entry.pack(side="left", padx=(5, 0))
        page_entry.bind('<Return>', lambda e: self.go_to_page_from_entry(category, page_entry))

        self.pagination_data[category]['page_entry'] = page_entry

        # Next page button
        next_btn = self._secondary_button(nav_frame, text="Next", width=64,
                                          command=lambda: self.go_to_page(category,
                                          self.pagination_data[category]['current_page'] + 1))
        next_btn.pack(side="left", padx=2)

        # Last page button
        last_btn = self._secondary_button(nav_frame, text="Last", width=64,
                                          command=lambda: self.go_to_last_page(category))
        last_btn.pack(side="left", padx=2)

        # Store button references for enabling/disabling
        self.pagination_data[category]['buttons'] = {
            'first': first_btn,
            'prev': prev_btn,
            'next': next_btn,
            'last': last_btn
        }

        # Right side - players per page selector
        per_page_frame = ctk.CTkFrame(parent, fg_color="transparent")
        per_page_frame.pack(side="right")

        self._body(per_page_frame, text="Per page:", dim=True,
                   size=11).pack(side="left")
        per_page_var = tk.StringVar(value="50")  # Default to 50 players per page
        per_page_combo = self._combo(per_page_frame, variable=per_page_var,
                                     values=["10", "25", "50", "100", "All"],
                                     command=lambda v: self.change_per_page(category, v),
                                     width=80)
        per_page_combo.pack(side="left", padx=(5, 0))

        self.pagination_data[category]['per_page_var'] = per_page_var
    
    def get_enhanced_player_columns(self, category):
        """Get enhanced column definitions for player stats"""
        if category == "scoring":
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'pos': ('Pos', 50),
                'gp': ('GP', 40),
                'goals': ('G', 40),
                'assists': ('A', 40),
                'points': ('PTS', 50),
                'ppg': ('PPG', 50),
                'plus_minus': ('+/-', 50),
                'pim': ('PIM', 45),
                'shots': ('SOG', 50)
            }
        elif category == "advanced":
            if self._in_playoff_mode():
                # Playoffs: no xG model -- scoring-rate table (min GP
                # enforced by the Min Games filter in playoff mode).
                return {
                    'rank': ('Rank', 50),
                    'player': ('Player', 150),
                    'team': ('Team', 60),
                    'pos': ('Pos', 50),
                    'gp': ('GP', 40),
                    'goals': ('G', 40),
                    'assists': ('A', 40),
                    'points': ('PTS', 50),
                    'ppg': ('P/GP', 55),
                    'gpg': ('G/GP', 55),
                }
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'pos': ('Pos', 50),
                'gp': ('GP', 40),
                'ixg': ('ixG', 55),
                'cf_pct': ('CF%', 55),
                'xgf_pct': ('xGF%', 60),
                'pdo': ('PDO', 60),
                'p_per60': ('P/60', 55),
                'game_score': ('GSc', 55),
                'sh_pct': ('SH%', 55),
            }
        elif category == "breakout":
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'age': ('Age', 40),
                'ixg_vs_g': ('ixG vs G', 90),
                'xgf_pct': ('xGF%', 60),
                'pdo': ('PDO', 60),
                'p_per60': ('P/60', 55),
                'signal': ('Breakout Signal', 140),
            }
        else:  # goaltending
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'gp': ('GP', 40),
                'w': ('W', 35),
                'l': ('L', 35),
                'gaa': ('GAA', 50),
                'sv_pct': ('SV%', 60),
                'gsax': ('GSAx', 55),
                'hdsv': ('HDSV%', 60),
                'so': ('SO', 40),
                'sa': ('SA', 55)
            }
    
    def _player_position_str(self, player):
        pos = getattr(player, 'primary_position', 'F')
        if hasattr(pos, 'value'):
            return str(pos.value)
        return str(pos).split('.')[-1]

    def _enhanced_player_row(self, category, rank, player, team):
        """Build one paginated player-leader row from REAL player stats.

        Player season stats live directly on the player object
        (goals, assists, games_played, ...); there is no `.stats` sub-object.
        """
        team_abbr = self._get_team_abbreviation(getattr(team, 'team_name', ''))
        position = self._player_position_str(player)
        name = getattr(player, 'full_name', 'Unknown')

        if category == "scoring":
            if self._in_playoff_mode():
                # Playoff scoring: +/- isn't tracked in the playoff ledger.
                goals = int(self._pstat(player, "goals", 0) or 0)
                assists = int(self._pstat(player, "assists", 0) or 0)
                games = int(self._pstat(player, "games_played", 0) or 0)
                points = goals + assists
                ppg = round(points / max(games, 1), 2)
                pim = int(self._pstat(player, "penalties_in_minutes", 0) or 0)
                shots = int(self._pstat(player, "shots", 0) or 0)
                return (rank, name, team_abbr, position,
                        games, goals, assists, points, ppg, "—", pim, shots)
            goals = getattr(player, 'goals', 0)
            assists = getattr(player, 'assists', 0)
            games = getattr(player, 'games_played', 0)
            points = goals + assists
            ppg = round(points / max(games, 1), 2)
            plus_minus = getattr(player, 'plus_minus', 0)
            pim = getattr(player, 'penalty_minutes', 0)
            shots = getattr(player, 'shots', 0)
            return (rank, name, team_abbr, position,
                    games, goals, assists, points, ppg, plus_minus, pim, shots)

        elif category == "advanced":
            if self._in_playoff_mode():
                goals = int(self._pstat(player, "goals", 0) or 0)
                assists = int(self._pstat(player, "assists", 0) or 0)
                games = int(self._pstat(player, "games_played", 0) or 0)
                points = goals + assists
                return (rank, name, team_abbr, position, games, goals,
                        assists, points,
                        f"{points / max(games, 1):.2f}",
                        f"{goals / max(games, 1):.2f}")
            import advanced_metrics as am
            try:
                m = am.skater_advanced(player)
                return (rank, name, team_abbr, position,
                        getattr(player, 'games_played', 0),
                        f"{m.ixg:.1f}", f"{m.cf_pct:.1f}%",
                        f"{m.xgf_pct:.1f}%", f"{m.pdo:.3f}",
                        f"{m.p_per60:.2f}", f"{m.game_score:.1f}",
                        f"{m.sh_pct:.1f}%" if m.sh_pct else "—")
            except Exception:
                return (rank, name, team_abbr, position,
                        getattr(player, 'games_played', 0),
                        "—", "—", "—", "—", "—", "—", "—")

        elif category == "breakout":
            import advanced_metrics as am
            age = getattr(player, 'age', 22)
            try:
                m = am.skater_advanced(player)
                goals = getattr(player, 'goals', 0)
                ixg_gap = m.ixg - goals
                # Breakout signal: elite underlying numbers, production catching up
                signals = []
                if m.xgf_pct >= 55 and age <= 25:
                    signals.append("Driving play")
                if ixg_gap >= 5:
                    signals.append("Due for goals")
                if m.pdo <= 0.985:
                    signals.append("Unlucky PDO")
                if m.p_per60 >= 2.5 and age <= 23:
                    signals.append("Elite rate")
                signal = ", ".join(signals) if signals else "Steady"
                return (rank, name, team_abbr, age,
                        f"{m.ixg:.1f} vs {goals}",
                        f"{m.xgf_pct:.1f}%", f"{m.pdo:.3f}",
                        f"{m.p_per60:.2f}", signal)
            except Exception:
                return (rank, name, team_abbr, age,
                        "—", "—", "—", "—", "—")

        else:  # goaltending
            if self._in_playoff_mode():
                # Playoff goalies: GSAx/HDSV% need the season xG model --
                # not available for the playoff sample. Wins + SV% + SO.
                games = int(self._pstat(player, "games_played", 0) or 0)
                wins = int(self._pstat(player, "wins", 0) or 0)
                losses = int(self._pstat(player, "losses", 0) or 0)
                gaa = float(self._pstat(player, "goals_against_avg", 0) or 0)
                sv = float(self._pstat(player, "save_percentage", 0) or 0)
                shutouts = int(self._pstat(player, "shutouts", 0) or 0)
                sa = int(self._pstat(player, "shots_against", 0) or 0)
                sv_pct = f"{sv:.3f}"[1:] if sa > 0 else "—"
                return (rank, name, team_abbr, games, wins, losses,
                        f"{gaa:.2f}" if games > 0 else "—", sv_pct,
                        "—", "—", shutouts, sa)
            import advanced_metrics as am
            games = getattr(player, 'games_played', 0)
            wins = getattr(player, 'wins', 0)
            losses = getattr(player, 'losses', 0)
            gaa = getattr(player, 'goals_against_avg', 0.0)
            sv = getattr(player, 'save_percentage', 0.0)
            shutouts = getattr(player, 'shutouts', 0)
            sa = getattr(player, 'shots_against', 0)
            sv_pct = f"{sv:.3f}"[1:] if sa > 0 else "—"
            try:
                gm = am.goalie_advanced(player)
                gsax_s = f"{gm.gsax:+.1f}"
                hdsv_s = f"{gm.hdsv_pct:.3f}"[1:]
            except Exception:
                gsax_s, hdsv_s = "—", "—"
            return (rank, name, team_abbr, games, wins, losses,
                    f"{gaa:.2f}" if games > 0 else "—", sv_pct,
                    gsax_s, hdsv_s, shutouts, sa)

    def add_enhanced_player_data(self, tree, category):
        """Add enhanced player data from real game data (top 20, no pagination)."""
        try:
            all_players = []
            for team in self.app.league.teams:
                if hasattr(team, 'roster') and team.roster:
                    for player in team.roster:
                        try:
                            is_g = (player.primary_position.value == 'G')
                        except Exception:
                            is_g = 'GOALIE' in str(
                                getattr(player, 'primary_position', '')).upper()
                        if category == "goaltending":
                            if is_g:
                                all_players.append((player, team))
                        elif not is_g:
                            all_players.append((player, team))

            def sort_key(pt):
                player, _team = pt
                if category == "goaltending":
                    return (getattr(player, 'save_percentage', 0),
                            getattr(player, 'wins', 0))
                if category == "advanced":
                    shots = getattr(player, 'shots', 0)
                    shp = (getattr(player, 'goals', 0) / shots) if shots else 0
                    return (getattr(player, 'goals', 0)
                            + getattr(player, 'assists', 0), shp)
                if category == "breakout":
                    return getattr(player, 'potential', 50)
                return getattr(player, 'goals', 0) + getattr(player, 'assists', 0)

            for rank, (player, team) in enumerate(
                    sorted(all_players, key=sort_key, reverse=True)[:20], 1):
                tree.insert('', 'end',
                            values=self._enhanced_player_row(
                                category, rank, player, team))
        except Exception as e:
            print(f"Error loading player data for {category}: {e}")
            tree.insert('', 'end', values=("Error loading data",))
    
    def create_analytics_panel(self, parent, title, row, col):
        """Create an analytics panel"""
        panel = ttk.LabelFrame(parent, text=title, style='Panel.TLabelframe', padding=10)
        panel.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
        return panel
    
    def populate_trends_panel(self, panel):
        """Populate trends analysis panel with real game data"""
        try:
            # Calculate real trends from game data
            total_goals = 0
            total_games = 0
            total_teams = 0
            pp_efficiency_sum = 0
            overtime_games = 0
            shutouts = 0
            
            for team in self.app.league.teams:
                if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                    total_teams += 1
                    team_games = max(team.games_played, 1)
                    total_games += team_games
                    
                    # Use team stats or calculate from wins/losses
                    team_goals = getattr(team, 'goals_for', team.wins * 3 + team.losses * 2)
                    total_goals += team_goals
                    
                    # Estimate PP efficiency (mock calculation)
                    pp_eff = min(30, 15 + (team.wins / max(team_games, 1)) * 10)
                    pp_efficiency_sum += pp_eff
                    
                    # Estimate overtime games
                    if hasattr(team, 'ot_losses'):
                        overtime_games += team.ot_losses
            
            if total_teams > 0:
                avg_goals_per_game = total_goals / max(total_games, 1)
                avg_pp_efficiency = pp_efficiency_sum / total_teams
                
                trends_data = [
                    ("Goals per game", f"{avg_goals_per_game:.2f} league average"),
                    ("Power play efficiency", f"{avg_pp_efficiency:.1f}% league average"),
                    ("Overtime games", f"{overtime_games} total this season"),
                    ("Games played", f"{total_games} total across {total_teams} teams"),
                ]
            else:
                # Fallback if no teams available
                trends_data = [
                    ("League data", "Loading team statistics..."),
                    ("Games played", "Season in progress"),
                    ("Statistics", "Calculating trends..."),
                ]
        
        except Exception as e:
            print(f"Error calculating trends: {e}")
            trends_data = [
                ("Data loading", "Calculating league trends..."),
                ("Season progress", "Games being tracked"),
                ("Statistics", "Real-time updates enabled"),
            ]
        
        for i, (metric, trend) in enumerate(trends_data):
            ttk.Label(panel, text=f"{metric}: {trend}", style='TLabel').pack(anchor='w', pady=2)
    
    def populate_outliers_panel(self, panel):
        """Populate statistical outliers panel with real game data"""
        try:
            outliers = []
            nhl_teams = [team for team in self.app.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
            
            if nhl_teams:
                # Find team with best record
                best_team = max(nhl_teams, key=lambda t: t.wins)
                outliers.append(f"{best_team.team_name}: {best_team.wins} wins (league high)")
                
                # Find team with most losses
                worst_team = max(nhl_teams, key=lambda t: t.losses)
                if worst_team != best_team:
                    outliers.append(f"{worst_team.team_name}: {worst_team.losses} losses (league high)")
                
                # Find highest scoring team
                high_scoring = max(nhl_teams, key=lambda t: getattr(t, 'goals_for', t.wins * 3))
                goals_for = getattr(high_scoring, 'goals_for', high_scoring.wins * 3)
                outliers.append(f"{high_scoring.team_name}: {goals_for} goals scored")
                
                # Find team with best win percentage
                if nhl_teams:
                    best_pct_team = max(nhl_teams, key=lambda t: t.winning_percentage)
                    win_pct = best_pct_team.winning_percentage * 100
                    outliers.append(f"{best_pct_team.team_name}: {win_pct:.1f}% win rate")
                
                # Find top player if possible
                try:
                    all_players = []
                    for team in nhl_teams[:5]:  # Check first 5 teams for performance
                        if hasattr(team, 'roster') and team.roster:
                            for player in team.roster[:3]:  # Top 3 from each team
                                goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else getattr(player, 'goals', 0)
                                assists = getattr(player.stats, 'assists', 0) if hasattr(player, 'stats') else getattr(player, 'assists', 0)
                                points = goals + assists
                                if points > 0:
                                    all_players.append((player, team, points))
                    
                    if all_players:
                        top_player, player_team, points = max(all_players, key=lambda x: x[2])
                        outliers.append(f"{player_team.team_name}: {top_player.full_name} with {points} points")
                        
                except Exception as e:
                    print(f"Error finding top player: {e}")
            
            # Fallback if no outliers found
            if not outliers:
                outliers = [
                    "Season in progress - tracking team performance",
                    "Player statistics being calculated",
                    "League leaders will appear as season progresses",
                    "Real-time statistical analysis active"
                ]
                
        except Exception as e:
            print(f"Error calculating outliers: {e}")
            outliers = [
                "Loading team performance data...",
                "Calculating statistical leaders...",
                "Real-time updates enabled",
                "Season statistics tracking active"
            ]
        
        for outlier in outliers:
            ttk.Label(panel, text=f"• {outlier}", style='TLabel').pack(anchor='w', pady=2)
    
    def populate_predictors_panel(self, panel):
        """Populate performance predictors panel"""
        predictors = [
            "Corsi leaders: 85% playoff rate",
            "Quality starts >60%: +12 pts avg",
            "PP% >25%: 78% top-8 finish",
            "Road record >0.600: Cup contender"
        ]
        
        for predictor in predictors:
            ttk.Label(panel, text=f"→ {predictor}", style='TLabel').pack(anchor='w', pady=2)
    
    def populate_metrics_panel(self, panel):
        """Populate advanced metrics panel"""
        metrics = [
            ("League PDO", "100.2"),
            ("Avg shooting %", "10.8%"),
            ("Avg save %", "0.908"),
            ("Goals/game", "6.1")
        ]
        
        for metric, value in metrics:
            frame = ttk.Frame(panel, style='Panel.TFrame')
            frame.pack(fill='x', pady=2)
            ttk.Label(frame, text=metric, style='TLabel').pack(side='left')
            ttk.Label(frame, text=value, style='Accent.TLabel').pack(side='right')
    
    def populate_trends_analysis(self):
        """Populate trends analysis tab"""
        # Clear existing content
        for widget in self.trends_container.winfo_children():
            widget.destroy()
        
        # Create trends display
        trends_text = tk.Text(self.trends_container, bg=self.app.BG_COLOR, 
                             fg=self.app.TEXT_COLOR, wrap='word', height=20)
        trends_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Get real trends data from actual teams
        trends_content = self.generate_real_trends_analysis()
        
        trends_text.insert(1.0, trends_content)
        trends_text.config(state='disabled')
    
    def generate_real_trends_analysis(self):
        """Generate trends analysis from real team data"""
        try:
            # Get real teams
            teams = []
            if hasattr(self.app, 'league') and hasattr(self.app.league, 'teams'):
                teams = [team for team in self.app.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
            
            if not teams:
                teams = self.get_fallback_teams()
            
            # Calculate league-wide statistics
            total_goals = sum(getattr(team, 'goals_for', 0) for team in teams)
            total_games = sum(getattr(team, 'games_played', 0) for team in teams)
            avg_goals_per_game = total_goals / max(1, total_games)
            
            # Find hot and cold teams
            hot_teams = sorted(teams, key=lambda t: t.wins * 2 + getattr(t, 'ot_losses', 0), reverse=True)[:3]
            cold_teams = sorted(teams, key=lambda t: t.wins * 2 + getattr(t, 'ot_losses', 0))[:3]
            
            # Generate analysis content
            content = f"""LEAGUE TRENDS ANALYSIS
===================

Current League Statistics:
• Average goals per game: {avg_goals_per_game:.2f}
• Total teams analyzed: {len(teams)}
• Season progress: Early season analysis

Team Performance Leaders:
Top Performing Teams:"""
            
            for i, team in enumerate(hot_teams, 1):
                points = team.wins * 2 + getattr(team, 'ot_losses', 0)
                goal_diff = getattr(team, 'goals_for', 0) - getattr(team, 'goals_against', 0)
                content += f"\n   {i}. {team.team_name} ({team.wins}-{team.losses}-{getattr(team, 'ot_losses', 0)}, {points} pts, {goal_diff:+d} goal diff)"
            
            content += f"\n\nTeams Needing Improvement:"
            for i, team in enumerate(cold_teams, 1):
                points = team.wins * 2 + getattr(team, 'ot_losses', 0)
                goal_diff = getattr(team, 'goals_for', 0) - getattr(team, 'goals_against', 0)
                content += f"\n   {i}. {team.team_name} ({team.wins}-{team.losses}-{getattr(team, 'ot_losses', 0)}, {points} pts, {goal_diff:+d} goal diff)"
            
            content += f"""

Statistical Trends:
• League scoring pace tracking well
• Competitive balance across teams
• Goal differential ranges from {min(getattr(t, 'goals_for', 0) - getattr(t, 'goals_against', 0) for t in teams):+d} to {max(getattr(t, 'goals_for', 0) - getattr(t, 'goals_against', 0) for t in teams):+d}

Analysis Notes:
• Data reflects current team standings and performance
• Trends will become more meaningful as season progresses
• Team momentum can shift rapidly in hockey
"""
            
            return content
            
        except Exception as e:
            print(f"Error generating trends analysis: {e}")
            return """LEAGUE TRENDS ANALYSIS
===================

Real-time trends analysis is being calculated from current team data.
Please check back after more games have been played for detailed trends.

Current data sources:
• Team standings and records
• Goal differentials
• Win/loss patterns

Analysis will be updated as the season progresses.
"""
    
    def populate_division_analysis(self):
        """Populate division analysis tab"""
        # Clear existing content
        for widget in self.division_container.winfo_children():
            widget.destroy()
        
        division = self.division_view.get()
        analysis_type = self.div_analysis_type.get()
        
        # Create division display based on selection
        if analysis_type == "Standings":
            self.create_division_standings(self.division_container, division)
        elif analysis_type == "Head-to-Head":
            self.create_head_to_head_analysis(self.division_container, division)
        else:
            # Default to standings
            self.create_division_standings(self.division_container, division)
    
    def create_division_standings(self, parent, division):
        """Create division-specific standings using real team data"""
        # Get real teams for this division
        division_teams = []
        try:
            if hasattr(self.app, 'league') and hasattr(self.app.league, 'teams'):
                all_teams = [team for team in self.app.league.teams
                           if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]

                # For now, take any NHL teams and group them by division placeholder
                # In a real implementation, teams would have division attributes
                division_teams = all_teams[:4]  # Take first 4 for this division

            if not division_teams:
                fallback_teams = self.get_fallback_teams()
                division_teams = fallback_teams[:4]

        except Exception as e:
            print(f"Error getting division teams: {e}")
            division_teams = self.get_fallback_teams()[:4]

        # Convert teams to standings format
        divisions_data = {
            division: []
        }

        for team in division_teams:
            team_data = (
                team.team_name,
                team.wins,
                team.losses,
                getattr(team, 'ot_losses', 0),
                team.wins * 2 + getattr(team, 'ot_losses', 0)  # Points
            )
            divisions_data[division].append(team_data)

        # Sort by points
        divisions_data[division].sort(key=lambda x: x[4], reverse=True)

        # Create dark styled table
        columns = {
            'team': ('Team', 200),
            'w': ('W', 50),
            'l': ('L', 50),
            'otl': ('OTL', 50),
            'pts': ('PTS', 60)
        }

        tree = self._make_tree(parent, columns, height=15, padx=10, pady=10)

        # Add data
        if division in divisions_data:
            for team_data in divisions_data[division]:
                tree.insert('', 'end', values=team_data)

    def create_head_to_head_analysis(self, parent, division):
        """Create head-to-head analysis with real division data"""
        ct = self._ct
        try:
            # Create container for head-to-head matrix
            container = ctk.CTkFrame(parent, fg_color="transparent")
            container.pack(fill='both', expand=True, padx=10, pady=10)

            # Title
            self._heading(container, text=f"{division} Head-to-Head Records",
                          size=15).pack(pady=(0, 10))

            # Get teams from this division
            division_teams = []
            for team in self.app.league.teams:
                if (hasattr(team, 'league_name') and team.league_name == "National Hockey League" and
                    hasattr(team, 'division') and division.lower() in team.division.lower()):
                    division_teams.append(team)

            if not division_teams:
                # Fallback: show a few NHL teams
                division_teams = [team for team in self.app.league.teams
                                if hasattr(team, 'league_name') and team.league_name == "National Hockey League"][:4]

            if division_teams:
                # Create simple head-to-head grid
                info_text = f"Teams in division: {len(division_teams)}\n\n"
                info_text += "Season Records:\n"

                for team in division_teams[:6]:  # Limit to 6 teams for display
                    record = team.record_string
                    points = team.points
                    info_text += f"• {team.team_name}: {record} ({points} pts)\n"

                info_text += f"\nNote: Detailed head-to-head matchup data will be available as the season progresses."

                self._body(container, text=info_text, size=11).pack(anchor='w', padx=20)
            else:
                self._body(container, text="Division data loading...",
                            dim=True).pack(expand=True)

        except Exception as e:
            print(f"Error creating head-to-head analysis: {e}")
            self._body(parent, text="Head-to-head analysis initializing...",
                        dim=True).pack(expand=True)
    
    def _is_goalie(self, player):
        """True if the player is a goalie (value-based, no substring matching)."""
        try:
            return player.primary_position.value == 'G'
        except Exception:
            return str(getattr(player, 'primary_position', '')).upper().endswith('GOALIE')

    def load_all_players_data(self, category):
        """Load all players data for pagination"""
        try:
            all_players = []

            # Collect all players from all teams
            for team in self.app.league.teams:
                if hasattr(team, 'roster') and team.roster:
                    for player in team.roster:
                        is_g = self._is_goalie(player)
                        if category == "goaltending":
                            if is_g:
                                all_players.append((player, team))
                        elif not is_g:
                            all_players.append((player, team))

            # Playoff mode: the active ledger is playoff_stats, and the
            # Min Games filter actually applies (a 1-game 3-point night
            # must not top a P/GP board).
            playoff = self._in_playoff_mode()
            if playoff:
                try:
                    _mg = int(self.min_games.get())
                except Exception:
                    _mg = 1
                all_players = [(p, t) for p, t in all_players
                               if int(self._pstat(p, "games_played", 0) or 0)
                               >= _mg]

            # Sort players based on category
            if category == "scoring":
                def get_points(player_team):
                    player, team = player_team
                    return (int(self._pstat(player, "goals", 0) or 0)
                            + int(self._pstat(player, "assists", 0) or 0))
                sorted_players = sorted(all_players, key=get_points, reverse=True)

            elif category == "advanced":
                if playoff:
                    # No xG model for the playoffs: rate table (P/GP).
                    def get_playoff_rate(player_team):
                        player, team = player_team
                        gp = max(1, int(self._pstat(player, "games_played", 0)
                                        or 0))
                        pts = (int(self._pstat(player, "goals", 0) or 0)
                               + int(self._pstat(player, "assists", 0) or 0))
                        return pts / gp
                    sorted_players = sorted(all_players, key=get_playoff_rate,
                                            reverse=True)
                else:
                    import advanced_metrics as am
                    def get_advanced_score(player_team):
                        player, team = player_team
                        try:
                            m = am.skater_advanced(player)
                            return (m.xgf_pct, m.game_score)
                        except Exception:
                            return (0, 0)
                    sorted_players = sorted(all_players, key=get_advanced_score, reverse=True)

            elif category == "breakout":
                import advanced_metrics as am
                young_players = [(p, t) for p, t in all_players
                                 if getattr(p, 'age', 25) <= 25]
                def get_breakout_potential(player_team):
                    player, team = player_team
                    try:
                        m = am.skater_advanced(player)
                        goals = getattr(player, 'goals', 0) or 0
                        # Elite process + youth + positive regression signals
                        score = ((m.xgf_pct - 50) * 2.0
                                 + max(0, m.ixg - goals) * 1.5
                                 + max(0, 1.000 - m.pdo) * 200
                                 + max(0, 25 - getattr(player, 'age', 25)) * 1.2
                                 + m.p_per60 * 3.0)
                        return score
                    except Exception:
                        return 0
                sorted_players = sorted(young_players, key=get_breakout_potential, reverse=True)
                
            else:  # goaltending
                if playoff:
                    # Playoff goalies: wins first, then SV% -- the Smythe lens.
                    def get_playoff_goalie(player_team):
                        player, team = player_team
                        return (int(self._pstat(player, "wins", 0) or 0),
                                float(self._pstat(player, "save_percentage",
                                                  0) or 0))
                    sorted_players = sorted(all_players,
                                            key=get_playoff_goalie,
                                            reverse=True)
                else:
                    import advanced_metrics as am
                    def get_goalie_score(player_team):
                        player, team = player_team
                        try:
                            return (am.goalie_advanced(player).gsax,
                                    getattr(player, 'save_percentage', 0))
                        except Exception:
                            return (0, 0)
                    sorted_players = sorted(all_players, key=get_goalie_score, reverse=True)
            
            # Store sorted players
            self.pagination_data[category]['all_players'] = sorted_players
            self.pagination_data[category]['total_players'] = len(sorted_players)
            
        except Exception as e:
            print(f"Error loading all players data for {category}: {e}")
            self.pagination_data[category]['all_players'] = []
            self.pagination_data[category]['total_players'] = 0
    
    def update_page_display(self, category):
        """Update the display for current page"""
        data = self.pagination_data[category]
        current_page = data['current_page']
        per_page = data['players_per_page']
        total_players = data['total_players']
        
        if total_players == 0:
            return
            
        # Calculate total pages
        total_pages = max(1, (total_players + per_page - 1) // per_page)
        
        # Ensure current page is valid
        if current_page > total_pages:
            current_page = total_pages
            data['current_page'] = current_page
        elif current_page < 1:
            current_page = 1
            data['current_page'] = current_page
        
        # Calculate start and end indices
        start_idx = (current_page - 1) * per_page
        end_idx = min(start_idx + per_page, total_players)
        
        # Update page label
        page_text = f"Showing {start_idx + 1}-{end_idx} of {total_players} players"
        data['page_label'].configure(text=page_text)
        
        # Update page entry
        data['page_entry'].delete(0, tk.END)
        data['page_entry'].insert(0, str(current_page))
        
        # Enable/disable buttons
        buttons = data['buttons']
        buttons['first']['state'] = 'disabled' if current_page == 1 else 'normal'
        buttons['prev']['state'] = 'disabled' if current_page == 1 else 'normal'
        buttons['next']['state'] = 'disabled' if current_page == total_pages else 'normal'
        buttons['last']['state'] = 'disabled' if current_page == total_pages else 'normal'
        
        # Clear and populate tree with current page data
        tree = data['tree']
        for item in tree.get_children():
            tree.delete(item)
        
        page_players = data['all_players'][start_idx:end_idx]
        
        # Add players to tree with proper ranking (real stats via shared helper)
        for i, (player, team) in enumerate(page_players):
            rank = start_idx + i + 1
            tree.insert('', 'end', values=self._enhanced_player_row(
                category, rank, player, team))
    
    def go_to_page(self, category, page):
        """Navigate to specific page"""
        data = self.pagination_data[category]
        total_pages = max(1, (data['total_players'] + data['players_per_page'] - 1) // data['players_per_page'])
        
        if 1 <= page <= total_pages:
            data['current_page'] = page
            self.update_page_display(category)
    
    def go_to_last_page(self, category):
        """Navigate to last page"""
        data = self.pagination_data[category]
        total_pages = max(1, (data['total_players'] + data['players_per_page'] - 1) // data['players_per_page'])
        self.go_to_page(category, total_pages)
    
    def go_to_page_from_entry(self, category, entry):
        """Navigate to page from entry field"""
        try:
            page = int(entry.get())
            self.go_to_page(category, page)
        except ValueError:
            # Reset entry to current page if invalid input
            data = self.pagination_data[category]
            entry.delete(0, tk.END)
            entry.insert(0, str(data['current_page']))
    
    def change_per_page(self, category, new_per_page_str):
        """Change number of players per page"""
        data = self.pagination_data[category]
        old_per_page = data['players_per_page']
        
        # Handle "All" option
        if new_per_page_str == "All":
            new_per_page = data['total_players']
        else:
            new_per_page = int(new_per_page_str)
        
        # Calculate what the current page should be with new per_page
        current_start_player = (data['current_page'] - 1) * old_per_page + 1
        new_page = max(1, (current_start_player + new_per_page - 1) // new_per_page)
        
        data['players_per_page'] = new_per_page
        data['current_page'] = new_page
        
        self.update_page_display(category)
    
    def update_player_leaders(self, value=None):
        """Update player leaders based on current filter settings"""
        try:
            # Get current sub-tab
            current_tab = self.leaders_tabview.get()

            # Determine category from tab name
            category_map = {
                "Scoring Leaders": "scoring",
                "Advanced Stats": "advanced",
                "Breakout Players": "breakout",
                "Goaltending": "goaltending"
            }

            category = category_map.get(current_tab, "scoring")

            # Reload data and refresh pagination
            if hasattr(self, 'pagination_data') and category in self.pagination_data:
                self.load_all_players_data(category)
                self.update_page_display(category)

                # Update status with current filter info
                if hasattr(self, 'status_label'):
                    filter_text = "All Players"
                    if hasattr(self, 'position_filter') and self.position_filter.get() != "All":
                        filter_text = f"{self.position_filter.get()} Players"

                    total_players = self.pagination_data[category]['total_players']
                    self.status_label.configure(text=f"Player Leaders - {current_tab} ({filter_text}) - {total_players} total players")

        except Exception as e:
            print(f"Error updating player leaders: {e}")
            # Don't crash the UI if there's an error
            # Don't crash the UI if there's an error
    
    def update_trends_analysis(self, event=None):
        """Update trends analysis"""
        self.populate_trends_analysis()
    
    def update_division_analysis(self, event=None):
        """Update division analysis"""
        self.populate_division_analysis()
    
    def refresh_analytics_dashboard(self):
        """Refresh analytics dashboard"""
        # Would refresh all analytics panels
        pass
    
    def refresh_records_data(self):
        """Refresh all records data"""
        try:
            self._populate_season_records()
            self._populate_career_records()
            self._populate_current_leaders()
            self._populate_record_chase()
            self._populate_achievements()
        except Exception as e:
            print(f"Error refreshing records data: {e}")
    
    def _populate_season_records(self):
        """Populate season records display with current player comparisons"""
        try:
            # Clear existing content
            for widget in self.season_scrollable_frame.winfo_children():
                widget.destroy()
            
            record_manager = self.app.game_manager.record_manager
            
            # Get current league for player comparisons
            league = getattr(self.app.game_manager, 'league', None)
            current_leaders = {}
            
            if league and hasattr(league, 'teams'):
                # Find current leaders for each record type
                all_players = []
                for team in league.teams:
                    if hasattr(team, 'roster'):
                        all_players.extend([(player, team.team_name) for player in team.roster])
                
                if all_players:
                    # Calculate current leaders
                    goals_leader = max(all_players, key=lambda x: getattr(x[0], 'goals', 0))
                    assists_leader = max(all_players, key=lambda x: getattr(x[0], 'assists', 0))
                    points_leader = max(all_players, key=lambda x: getattr(x[0], 'goals', 0) + getattr(x[0], 'assists', 0))
                    wins_leader = max(all_players, key=lambda x: getattr(x[0], 'wins', 0) if hasattr(x[0], 'wins') else 0)
                    shutouts_leader = max(all_players, key=lambda x: getattr(x[0], 'shutouts', 0) if hasattr(x[0], 'shutouts') else 0)
                    
                    current_leaders = {
                        'single_season_goals': (goals_leader[0], getattr(goals_leader[0], 'goals', 0)),
                        'single_season_assists': (assists_leader[0], getattr(assists_leader[0], 'assists', 0)),
                        'single_season_points': (points_leader[0], getattr(points_leader[0], 'goals', 0) + getattr(points_leader[0], 'assists', 0)),
                        'single_season_wins': (wins_leader[0], getattr(wins_leader[0], 'wins', 0) if hasattr(wins_leader[0], 'wins') else 0),
                        'single_season_shutouts': (shutouts_leader[0], getattr(shutouts_leader[0], 'shutouts', 0) if hasattr(shutouts_leader[0], 'shutouts') else 0)
                    }
            
            # Season record categories
            season_categories = [
                ("Scoring Records", ["single_season_goals", "single_season_assists", "single_season_points"]),
                ("Goaltending Records", ["single_season_wins", "single_season_shutouts"]),
            ]
            
            row = 0
            for category_name, records in season_categories:
                # Category header
                header = ttk.Label(self.season_scrollable_frame, text=category_name,
                                  font=_sfont(self.app.FONT_FAMILY, 14, 'bold'),
                                  foreground=self.app.ACCENT_COLOR,
                                  background=self.app.CONTENT_BG)
                header.grid(row=row, column=0, columnspan=4, sticky="w", pady=(15, 10), padx=10)
                row += 1
                
                # Records in this category
                for record_type in records:
                    record_display = record_manager.nhl_records.format_record_display(record_type)
                    if record_display and "No record found" not in record_display:
                        # Clean up display name
                        display_name = record_type.replace("_", " ").replace("single season ", "").title()
                        
                        # Record name
                        name_label = ttk.Label(self.season_scrollable_frame, text=f"{display_name}:",
                                              font=_sfont(self.app.FONT_FAMILY, 11),
                                              foreground=self.app.TEXT_COLOR,
                                              background=self.app.CONTENT_BG)
                        name_label.grid(row=row, column=0, sticky="w", padx=(30, 10), pady=2)
                        
                        # NHL Record value
                        value_label = ttk.Label(self.season_scrollable_frame, text=record_display,
                                               font=_sfont(self.app.FONT_FAMILY, 11, 'bold'),
                                               foreground='#FFD700',  # Gold color
                                               background=self.app.CONTENT_BG)
                        value_label.grid(row=row, column=1, sticky="w", pady=2, padx=(0, 20))
                        
                        # Current season leader comparison
                        if record_type in current_leaders:
                            player, current_value = current_leaders[record_type]
                            if current_value > 0:
                                leader_text = f"Current Leader: {getattr(player, 'full_name', 'Unknown')} ({current_value})"
                                
                                # Get NHL record value for comparison
                                nhl_record_value = record_manager.nhl_records.season_records[record_type].value
                                percentage = (current_value / nhl_record_value) * 100 if nhl_record_value > 0 else 0
                                
                                if percentage >= 50:
                                    color = '#FFD700'  # Gold if close to record
                                elif percentage >= 25:
                                    color = '#FFA500'  # Orange if making progress
                                else:
                                    color = '#B0B0B0'  # Gray for normal
                                
                                leader_label = ttk.Label(self.season_scrollable_frame, text=leader_text,
                                                        font=_sfont(self.app.FONT_FAMILY, 9),
                                                        foreground=color,
                                                        background=self.app.CONTENT_BG)
                                leader_label.grid(row=row, column=2, sticky="w", pady=2)
                        
                        row += 1
                
        except Exception as e:
            print(f"Error populating season records: {e}")
    
    def _populate_career_records(self):
        """Populate career records display with current player comparisons"""
        try:
            # Clear existing content
            for widget in self.career_scrollable_frame.winfo_children():
                widget.destroy()
            
            record_manager = self.app.game_manager.record_manager
            
            # Get current league for player comparisons
            league = getattr(self.app.game_manager, 'league', None)
            current_leaders = {}
            
            if league and hasattr(league, 'teams'):
                # Find current leaders for each record type
                all_players = []
                for team in league.teams:
                    if hasattr(team, 'roster'):
                        all_players.extend([(player, team.team_name) for player in team.roster])
                
                if all_players:
                    # Calculate current career leaders
                    career_goals_leader = max(all_players, key=lambda x: getattr(x[0], 'career_goals', 0))
                    career_assists_leader = max(all_players, key=lambda x: getattr(x[0], 'career_assists', 0))
                    career_points_leader = max(all_players, key=lambda x: getattr(x[0], 'career_points', 0))
                    career_wins_leader = max(all_players, key=lambda x: getattr(x[0], 'career_wins', 0) if hasattr(x[0], 'career_wins') else 0)
                    career_shutouts_leader = max(all_players, key=lambda x: getattr(x[0], 'career_shutouts', 0) if hasattr(x[0], 'career_shutouts') else 0)
                    
                    current_leaders = {
                        'career_goals': (career_goals_leader[0], getattr(career_goals_leader[0], 'career_goals', 0)),
                        'career_assists': (career_assists_leader[0], getattr(career_assists_leader[0], 'career_assists', 0)),
                        'career_points': (career_points_leader[0], getattr(career_points_leader[0], 'career_points', 0)),
                        'career_wins': (career_wins_leader[0], getattr(career_wins_leader[0], 'career_wins', 0) if hasattr(career_wins_leader[0], 'career_wins') else 0),
                        'career_shutouts': (career_shutouts_leader[0], getattr(career_shutouts_leader[0], 'career_shutouts', 0) if hasattr(career_shutouts_leader[0], 'career_shutouts') else 0)
                    }
            
            # Career record categories
            career_categories = [
                ("Career Scoring", ["career_goals", "career_assists", "career_points"]),
                ("Career Goaltending", ["career_wins", "career_shutouts"]),
            ]
            
            row = 0
            for category_name, records in career_categories:
                # Category header
                header = ttk.Label(self.career_scrollable_frame, text=category_name,
                                  font=_sfont(self.app.FONT_FAMILY, 14, 'bold'),
                                  foreground=self.app.ACCENT_COLOR,
                                  background=self.app.CONTENT_BG)
                header.grid(row=row, column=0, columnspan=4, sticky="w", pady=(15, 10), padx=10)
                row += 1
                
                # Records in this category
                for record_type in records:
                    record_display = record_manager.nhl_records.format_record_display(record_type)
                    if record_display and "No record found" not in record_display:
                        # Clean up display name
                        display_name = record_type.replace("_", " ").replace("career ", "").title()
                        
                        # Record name
                        name_label = ttk.Label(self.career_scrollable_frame, text=f"{display_name}:",
                                              font=_sfont(self.app.FONT_FAMILY, 11),
                                              foreground=self.app.TEXT_COLOR,
                                              background=self.app.CONTENT_BG)
                        name_label.grid(row=row, column=0, sticky="w", padx=(30, 10), pady=2)
                        
                        # NHL Record value
                        value_label = ttk.Label(self.career_scrollable_frame, text=record_display,
                                               font=_sfont(self.app.FONT_FAMILY, 11, 'bold'),
                                               foreground='#FFD700',  # Gold color
                                               background=self.app.CONTENT_BG)
                        value_label.grid(row=row, column=1, sticky="w", pady=2, padx=(0, 20))
                        
                        # Current career leader comparison
                        if record_type in current_leaders:
                            player, current_value = current_leaders[record_type]
                            if current_value > 0:
                                leader_text = f"Current Leader: {getattr(player, 'full_name', 'Unknown')} ({current_value})"
                                
                                leader_label = ttk.Label(self.career_scrollable_frame, text=leader_text,
                                                        font=_sfont(self.app.FONT_FAMILY, 9),
                                                        foreground='#B0B0B0',
                                                        background=self.app.CONTENT_BG)
                                leader_label.grid(row=row, column=2, sticky="w", pady=2)
                        
                        row += 1
                
        except Exception as e:
            print(f"Error populating career records: {e}")
    
    def _populate_current_leaders(self):
        """Populate current season leaders with real game players"""
        try:
            # Clear existing items
            for item in self.current_leaders_tree.get_children():
                self.current_leaders_tree.delete(item)
            if hasattr(self.app, 'tree_maps'):
                self.app.tree_maps.setdefault(self.current_leaders_tree, {}).clear()
            
            # Get current league data
            league = getattr(self.app.game_manager, 'league', None)
            if not league or not hasattr(league, 'teams'):
                return
            
            # Collect all players with their current stats
            all_players = []
            for team in league.teams:
                if hasattr(team, 'roster'):
                    for player in team.roster:
                        all_players.append((player, team.team_name))
            
            if not all_players:
                return
            
            # Create comprehensive leaders for different stats
            stats_categories = [
                ("Goals", lambda p: getattr(p, 'goals', 0)),
                ("Assists", lambda p: getattr(p, 'assists', 0)),
                ("Points", lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0)),
                ("Games", lambda p: getattr(p, 'games_played', 0)),
                ("PIM", lambda p: getattr(p, 'penalty_minutes', 0)),
                ("Wins", lambda p: getattr(p, 'wins', 0) if hasattr(p, 'wins') else 0),
                ("Shutouts", lambda p: getattr(p, 'shutouts', 0) if hasattr(p, 'shutouts') else 0),
            ]
            
            rank = 1
            for stat_name, stat_func in stats_categories:
                # Sort players by this stat
                sorted_players = sorted(all_players, key=lambda x: stat_func(x[0]), reverse=True)
                
                # Add top 10 for each stat
                for i, (player, team) in enumerate(sorted_players[:10]):
                    value = stat_func(player)
                    if value > 0:  # Only show players with non-zero stats
                        # Determine position for display
                        position = getattr(player, 'primary_position', 'Unknown')
                        if hasattr(player, 'primary_position'):
                            position = str(player.primary_position).split('.')[-1] if '.' in str(player.primary_position) else str(player.primary_position)
                        
                        _lid = self.current_leaders_tree.insert("", "end", values=(
                            str(i + 1),  # Rank within this stat
                            getattr(player, 'full_name', 'Unknown'),
                            team,
                            position,
                            stat_name,
                            str(value)
                        ))
                        if hasattr(self.app, 'tree_maps'):
                            self.app.tree_maps[self.current_leaders_tree][_lid] = player
                
        except Exception as e:
            print(f"Error populating current leaders: {e}")
    
    def _populate_record_chase(self):
        """Populate record chase data with real players approaching records"""
        try:
            # Clear existing items
            for item in self.record_chase_tree.get_children():
                self.record_chase_tree.delete(item)
            if hasattr(self.app, 'tree_maps'):
                self.app.tree_maps.setdefault(self.record_chase_tree, {}).clear()
            
            # Get current league data and record manager
            league = getattr(self.app.game_manager, 'league', None)
            record_manager = self.app.game_manager.record_manager
            
            if not league or not hasattr(league, 'teams') or not record_manager:
                return
            
            # Collect all players with their current stats
            all_players = []
            for team in league.teams:
                if hasattr(team, 'roster'):
                    for player in team.roster:
                        all_players.append((player, team.team_name))
            
            if not all_players:
                return
            
            # Get NHL records to compare against
            nhl_records = record_manager.nhl_records

            def _record_target(records_dict, key):
                """Unwrap a SeasonRecord/CareerRecord to its target value."""
                rec = records_dict.get(key)
                if rec is None:
                    return None
                entry = getattr(rec, 'single_season', None) or getattr(rec, 'all_time', None)
                return getattr(entry, 'value', None)

            def _pstat(player, attr):
                return getattr(getattr(player, 'stats', None), attr, 0) or 0

            # Track players approaching various records
            record_categories = [
                ("single_season_goals", "Goals", lambda p: _pstat(p, 'goals')),
                ("single_season_assists", "Assists", lambda p: _pstat(p, 'assists')),
                ("single_season_points", "Points", lambda p: _pstat(p, 'points')),
                ("single_season_wins", "Wins", lambda p: _pstat(p, 'wins')),
                ("single_season_shutouts", "Shutouts", lambda p: _pstat(p, 'shutouts')),
            ]
            
            chase_data = []
            
            for record_type, display_name, stat_func in record_categories:
                # Get the NHL record for this category
                target_value = _record_target(nhl_records.records, record_type)
                if target_value:
                    # Find players with significant progress toward this record
                    for player, team in all_players:
                        current_value = stat_func(player)

                        if current_value > 0:  # Only consider players with some progress
                            percentage = (current_value / target_value) * 100
                            difference = target_value - current_value
                            
                            # Show players who are at least 25% toward the record
                            if percentage >= 25.0:
                                chase_data.append({
                                    'player_name': getattr(player, 'full_name', 'Unknown'),
                                    'player_obj': player,
                                    'team': team,
                                    'record_type': display_name,
                                    'current_value': current_value,
                                    'target_value': target_value,
                                    'difference': difference,
                                    'percentage': percentage,
                                    'position': getattr(player, 'primary_position', 'Unknown')
                                })
            
            # Sort by percentage (closest to record first)
            chase_data.sort(key=lambda x: x['percentage'], reverse=True)
            
            # Add top 20 record chasers
            for i, chase_info in enumerate(chase_data[:20]):
                position = chase_info['position']
                if hasattr(chase_info['position'], 'name'):
                    position = str(chase_info['position']).split('.')[-1]
                
                _rcid = self.record_chase_tree.insert("", "end", values=(
                    str(i + 1),
                    chase_info['player_name'],
                    chase_info['team'],
                    position,
                    chase_info['record_type'],
                    str(chase_info['current_value']),
                    str(chase_info['target_value']),
                    str(chase_info['difference']),
                    f"{chase_info['percentage']:.1f}%"
                ))
                if hasattr(self.app, 'tree_maps'):
                    self.app.tree_maps[self.record_chase_tree][_rcid] = chase_info['player_obj']
                
        except Exception as e:
            print(f"Error populating record chase: {e}")
    
    def _populate_achievements(self):
        """Populate recent achievements with real game data"""
        try:
            # Clear existing items
            for item in self.achievements_tree.get_children():
                self.achievements_tree.delete(item)
            
            record_manager = self.app.game_manager.record_manager
            
            # Get recent records broken in the game
            recent_records = record_manager.get_recent_records(20)
            
            if recent_records:
                for record in recent_records:
                    # Format record type for display
                    record_type_display = record['record_type'].replace('_', ' ').title()
                    
                    # Get previous record holder info if available
                    previous_info = "Previous Record"
                    if 'previous_value' in record:
                        previous_info = f"Previous: {record['previous_value']}"
                    
                    self.achievements_tree.insert("", "end", values=(
                        record.get('timestamp', 'Unknown')[:10],  # Just date part
                        record['player_name'],
                        record['team'],
                        record_type_display,
                        str(record['new_value']),
                        previous_info
                    ))
            else:
                # Show placeholder message if no records have been broken yet
                self.achievements_tree.insert("", "end", values=(
                    "N/A",
                    "No records broken yet",
                    "Play games to see achievements!",
                    "",
                    "",
                    ""
                ))
                
        except Exception as e:
            print(f"Error populating achievements: {e}")
            # Show error message in the tree
            self.achievements_tree.insert("", "end", values=(
                "Error",
                "Could not load achievements",
                str(e)[:50] + "..." if len(str(e)) > 50 else str(e),
                "",
                "",
                ""
            ))

    def create_analytics_dashboard_content(self, parent_frame):
        """Create analytics dashboard content"""
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])
        # Rebuild-safe: refresh re-calls this on the same frame.
        for _w in parent_frame.winfo_children():
            _w.destroy()
        # Title
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.pack(fill='x', padx=10, pady=(10, 4))

        self._heading(title_frame, text="League Analytics Dashboard",
                      size=18).pack(side='left')

        # Key metrics frame
        metrics_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        metrics_frame.pack(fill='x', padx=10, pady=(0, 8))
        self._metrics_frame = metrics_frame

        # Calculate league-wide statistics
        self._fill_metric_cards(metrics_frame)

        # Charts placeholder card
        charts_card = self._card(parent_frame)
        charts_card.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        self._heading(charts_card, text="Performance Charts", size=13,
                      text_color=ct['TEAL']).pack(anchor='w', padx=14,
                                                 pady=(10, 4))
        self._body(charts_card,
                   text="Advanced charts and visualizations would appear here",
                   dim=True).pack(pady=50)

    def _fill_metric_cards(self, metrics_frame):
        """Fill the analytics metric cards from real league data."""
        if self._in_playoff_mode():
            self._fill_playoff_metric_cards(metrics_frame)
            return
        if hasattr(self.app, 'game_manager') and self.app.game_manager.league:
            league = self.app.game_manager.league

            # Total goals scored across league -- NHL roster ONLY. AHL
            # numbers live on player.ahl_stats and never enter this screen
            # (they have their own AHL Stats screen).
            total_goals = 0
            total_games = 0
            avg_attendance = 0

            for team in league.teams:
                team_goals = sum(getattr(p, 'goals', 0) for p in team.roster)
                total_goals += team_goals
                total_games += team.games_played if hasattr(team, 'games_played') else 0
                avg_attendance += getattr(team, 'avg_attendance', 15000)

            avg_attendance = avg_attendance / len(league.teams) if league.teams else 0

            # Create metric cards
            self._create_metric_card(metrics_frame, "Total Goals", f"{total_goals:,}", "#4CAF50")
            self._create_metric_card(metrics_frame, "Games Played", f"{total_games:,}", "#2196F3")
            self._create_metric_card(metrics_frame, "Avg Attendance", f"{avg_attendance:,.0f}", "#FF9800")
            self._create_metric_card(metrics_frame, "Active Teams", f"{len(league.teams)}", "#9C27B0")

    def _fill_playoff_metric_cards(self, metrics_frame):
        """Playoff-mode dashboard: goals, games, OT games, champion."""
        try:
            pstats = self.get_team_playoff_stats()
            total_goals = sum(e["GF"] for e in pstats.values())
            total_games = sum(e["GP"] for e in pstats.values()) // 2
            ot_games = 0
            champion = "TBD"
            try:
                league = getattr(getattr(self.app, "game_manager", self.app),
                                 "league", None)
                bracket = getattr(league, "playoff_bracket", None)
                if bracket is not None:
                    champ = getattr(bracket, "stanley_cup_champion", None)
                    if champ is not None:
                        champion = getattr(champ, "team_name", "TBD")
                    for series_list in (getattr(
                            bracket, "playoff_series", None) or {}).values():
                        for s in series_list or []:
                            for g in getattr(s, "game_results",
                                             None) or []:
                                if g.get("ot"):
                                    ot_games += 1
            except Exception:
                pass
            self._create_metric_card(metrics_frame, "Playoff Goals",
                                     f"{total_goals:,}", "#4CAF50")
            self._create_metric_card(metrics_frame, "Playoff Games",
                                     f"{total_games:,}", "#2196F3")
            self._create_metric_card(metrics_frame, "OT Games",
                                     f"{ot_games:,}", "#FF9800")
            self._create_metric_card(metrics_frame, "Champion",
                                     champion, "#9C27B0")
        except Exception as e:
            print(f"Error filling playoff metric cards: {e}")
    
    def create_trends_analysis_content(self, parent_frame):
        """Create trends analysis content"""
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])
        # Title
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.pack(fill='x', padx=10, pady=(10, 4))

        self._heading(title_frame, text="League Trends Analysis",
                      size=18).pack(side='left')

        # Trends content card
        trends_card = self._card(parent_frame)
        trends_card.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        self._heading(trends_card, text="Current Trends", size=13,
                      text_color=ct['TEAL']).pack(anchor='w', padx=14,
                                                 pady=(10, 4))

        trends_text = tk.Text(trends_card, height=20, wrap='word',
                              bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                              font=_sfont(self.app.FONT_FAMILY, 10), relief='flat',
                              highlightthickness=0)
        trends_text.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        # Real trends content from league data
        trends_text.insert('1.0', self.generate_real_trends_analysis())
        trends_text.config(state='disabled')
        self._trends_text = trends_text
    
    def create_performance_insights_content(self, parent_frame):
        """Create performance insights content"""
        ct = self._ct
        parent_frame.configure(fg_color=ct['PANEL'])
        # Title
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.pack(fill='x', padx=10, pady=(10, 4))

        self._heading(title_frame, text="Performance Insights",
                      size=18).pack(side='left')

        # Insights tabs
        self.insights_tabview = self._make_tabview(parent_frame)
        self.insights_tabview.pack(fill='both', expand=True,
                                   padx=10, pady=(0, 10))
        for name in ("Team Analysis", "Player Analysis"):
            self.insights_tabview.add(name)

        # Team insights
        team_insights_frame = self.insights_tabview.tab("Team Analysis")
        team_insights_frame.configure(fg_color=ct['PANEL'])

        team_text = tk.Text(team_insights_frame, height=15, wrap='word',
                            bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                            font=_sfont(self.app.FONT_FAMILY, 10), relief='flat',
                            highlightthickness=0)
        team_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Player insights
        player_insights_frame = self.insights_tabview.tab("Player Analysis")
        player_insights_frame.configure(fg_color=ct['PANEL'])

        player_text = tk.Text(player_insights_frame, height=15, wrap='word',
                              bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                              font=_sfont(self.app.FONT_FAMILY, 10), relief='flat',
                              highlightthickness=0)
        player_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Real insights from league data
        team_content, player_content = self._generate_real_insights()

        team_text.insert('1.0', team_content)
        team_text.config(state='disabled')

        player_text.insert('1.0', player_content)
        player_text.config(state='disabled')
        self._team_insights_text = team_text
        self._player_insights_text = player_text

    def _generate_real_insights(self):
        """Build team/player insight text from real league data."""
        try:
            teams = self._standings_teams()
            by_pts = sorted(teams, key=self._team_points, reverse=True)

            team_lines = ["TEAM PERFORMANCE INSIGHTS", ""]
            team_lines.append("Top Performing Teams:")
            for t in by_pts[:5]:
                otl = getattr(t, 'ot_losses', 0)
                diff = getattr(t, 'goals_for', 0) - getattr(t, 'goals_against', 0)
                team_lines.append(
                    f"• {t.team_name}: {t.wins}-{t.losses}-{otl} "
                    f"({self._team_points(t)} pts, {diff:+d} differential)")
            if len(by_pts) > 5:
                team_lines.append("")
                team_lines.append("Needs Improvement:")
                for t in by_pts[-3:]:
                    otl = getattr(t, 'ot_losses', 0)
                    team_lines.append(
                        f"• {t.team_name}: {t.wins}-{t.losses}-{otl} "
                        f"({self._team_points(t)} pts)")

            players = []
            for t in teams:
                for p in getattr(t, 'roster', []) or []:
                    players.append((p, t.team_name))
            skaters = [x for x in players if not self._is_goalie(x[0])]
            goalies = [x for x in players if self._is_goalie(x[0])
                       and getattr(x[0], 'games_played', 0) >= 3]

            player_lines = ["PLAYER PERFORMANCE INSIGHTS", ""]
            if skaters:
                pts_king = max(skaters, key=lambda x: getattr(x[0], 'goals', 0)
                              + getattr(x[0], 'assists', 0))
                g_king = max(skaters, key=lambda x: getattr(x[0], 'goals', 0))
                pm_king = max(skaters, key=lambda x: getattr(x[0], 'plus_minus', 0))
                player_lines.append("Standout Performers:")
                player_lines.append(
                    f"• Points leader: {pts_king[0].full_name} ({pts_king[1]}) - "
                    f"{getattr(pts_king[0], 'goals', 0)}G, "
                    f"{getattr(pts_king[0], 'assists', 0)}A")
                player_lines.append(
                    f"• Goals leader: {g_king[0].full_name} ({g_king[1]}) - "
                    f"{getattr(g_king[0], 'goals', 0)} goals")
                player_lines.append(
                    f"• Best +/-: {pm_king[0].full_name} ({pm_king[1]}) - "
                    f"{getattr(pm_king[0], 'plus_minus', 0):+d}")
            if goalies:
                sv_king = max(goalies,
                              key=lambda x: getattr(x[0], 'save_percentage', 0))
                sv = getattr(sv_king[0], 'save_percentage', 0)
                player_lines.append(
                    f"• Top goalie: {sv_king[0].full_name} ({sv_king[1]}) - "
                    f".{sv * 1000:03.0f} SV%, "
                    f"{getattr(sv_king[0], 'goals_against_avg', 0):.2f} GAA")
            young = [x for x in skaters if getattr(x[0], 'age', 30) <= 23]
            if young:
                y_star = max(young, key=lambda x: getattr(x[0], 'goals', 0)
                            + getattr(x[0], 'assists', 0))
                player_lines.append("")
                player_lines.append("Development Watch:")
                player_lines.append(
                    f"• {y_star[0].full_name} ({y_star[1]}, age "
                    f"{getattr(y_star[0], 'age', '?')}) leads U24 scorers with "
                    f"{getattr(y_star[0], 'goals', 0) + getattr(y_star[0], 'assists', 0)} points")

            return "\n".join(team_lines), "\n".join(player_lines)
        except Exception as e:
            print(f"Error generating insights: {e}")
            return ("TEAM PERFORMANCE INSIGHTS\n\nData loading...",
                    "PLAYER PERFORMANCE INSIGHTS\n\nData loading...")
    
    def _create_metric_card(self, parent, title, value, color):
        """Create a metric card widget"""
        card_frame = self._card(parent)
        card_frame.pack(side='left', padx=5, pady=5, fill='both', expand=True)

        self._body(card_frame, text=title, dim=True, size=11).pack(pady=(10, 0))

        ctk.CTkLabel(card_frame, text=value,
                     font=(self._ff, 16, 'bold'),
                     text_color=color).pack(pady=(0, 10))


class StatsStandingsWindow(InGamePopup):
    """Popup wrapper around StatsStandingsView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Advanced League Analytics & Standings - Hockey Manager")
        self._view = StatsStandingsView(self, app=parent, *args, **kwargs)
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
