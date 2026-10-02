# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Modern Scouting Management Window
Professional scouting system with comprehensive features
Includes: Scout management, player evaluation, assignments, reports, and draft analysis
"""

from attribute_composites import talent_tier
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from popup_system import messagebox, InGamePopup, confirm_card
from typing import (Dict, Any)
import datetime
from game_classes import (Player, Staff, to_100_scale)
from scouting_profiles import displayed_overall, displayed_attribute
from player_context_menu import PlayerContextMenu


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


class ModernScoutingView(ctk.CTkFrame):
    """Professional scouting management interface with dedicated draft support"""
    
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ModernScoutingWindow wrapper
        self.configure(fg_color=self.app.BG_COLOR)
        
        # Data containers
        self.game_data = self._get_game_data()
        self.all_players = list(self.game_data.get('players', []))
        self.all_scouts = list(self.game_data.get('scouts', []))
        self.filter_vars = {}
        self.ui_components = {}
        self.current_assignments = {}
        
        # Initialize UI management
        self._ensure_tree_maps()
        
        # Build interface
        self._create_interface()
        self._load_initial_data()
        
        # Register window
        self.app.open_windows['scouting'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()
        
    def _get_game_data(self) -> Dict[str, Any]:
        """Get all game data in organized structure"""
        try:
            game_manager = getattr(self.app, 'game_manager', None)
            if not game_manager:
                return {'players': [], 'scouts': [], 'user_team': None, 'league': None, 'draft_class': []}
            
            # Get user team and league
            user_team = getattr(game_manager, 'user_team', None)
            league = getattr(game_manager, 'league', None)
            
            # Get all players
            all_players = []
            if league and hasattr(league, 'teams'):
                for team in league.teams:
                    # Collect from all roster types
                    for roster_type in ['roster', 'ahl_roster', 'prospects']:
                        roster = getattr(team, roster_type, [])
                        if roster:
                            all_players.extend(roster)
            
            # Add free agents
            free_agents = getattr(game_manager, 'free_agents', [])
            if free_agents:
                all_players.extend(free_agents)
            
            # Get scouts from user team
            scouts = []
            if user_team and hasattr(user_team, 'staff'):
                scouts = [s for s in user_team.staff if self._is_scouting_staff(s)]
            
            # Get draft class if available
            draft_class = getattr(game_manager, 'current_draft_class', [])
            
            return {
                'players': all_players,
                'scouts': scouts,
                'user_team': user_team,
                'league': league,
                'draft_class': draft_class
            }
            
        except Exception as e:
            print(f"Error loading game data: {e}")
            return {'players': [], 'scouts': [], 'user_team': None, 'league': None, 'draft_class': []}
    
    def _is_scouting_staff(self, staff: Staff) -> bool:
        """Check if staff member is involved in scouting"""
        if not staff:
            return False
        
        # Check role
        role_str = str(getattr(staff, 'role', '')).lower()
        if any(keyword in role_str for keyword in ['scout', 'evaluate', 'assess']):
            return True
        
        # Check for scouting attributes
        scouting_attrs = ['judging_player_ability', 'judging_player_potential', 'scouting_network']
        return any(hasattr(staff, attr) for attr in scouting_attrs)
    
    def _ensure_tree_maps(self):
        """Ensure tree maps exist for UI management"""
        if not hasattr(self.app, 'tree_maps'):
            self.app.tree_maps = {}
        
        required_maps = ['players_tree', 'scouts_tree', 'assignments_tree', 'reports_tree', 'draft_tree',
                         'targets_tree']
        for map_name in required_maps:
            if map_name not in self.app.tree_maps:
                self.app.tree_maps[map_name] = {}
    
    def _create_interface(self):
        """Create the main scouting interface with 5 professional tabs"""
        # Header with modern styling
        self._create_header()
        
        # Main tabbed interface
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Create all tabs
        self._create_players_tab()
        self._create_scouts_tab() 
        self._create_draft_tab()  # New dedicated draft tab
        self._create_assignments_tab()
        self._create_reports_tab()
        self._create_targets_tab()  # Scouting shortlist (trade_market)
        
        # Professional status bar
        self._create_status_bar()
        
    def _create_header(self):
        """Create professional header section"""
        header_frame = tk.Frame(self, bg=self.app.TITLE_BAR_COLOR, height=70)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Title and subtitle
        title_frame = tk.Frame(header_frame, bg=self.app.TITLE_BAR_COLOR)
        title_frame.pack(expand=True)
        
        
        # Current date and status
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        subtitle = f"Scouting Operations • {current_date}"
        subtitle_label = tk.Label(title_frame, text=subtitle,
                                font=_sfont(self.app.FONT_FAMILY, 10),
                                bg=self.app.TITLE_BAR_COLOR, fg=self.app.TEXT_COLOR)
        subtitle_label.pack()
        
    def _create_status_bar(self):
        """Create professional status bar"""
        status_frame = tk.Frame(self, bg=self.app.TITLE_BAR_COLOR, height=35)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        # Left side - main status
        self.status_label = tk.Label(status_frame, text="System Ready",
                                   bg=self.app.TITLE_BAR_COLOR, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 9))
        self.status_label.pack(side='left', padx=15, pady=8)
        
        # Right side - data counts
        self.data_label = tk.Label(status_frame, text="Loading data...",
                                 bg=self.app.TITLE_BAR_COLOR, fg=self.app.TEXT_COLOR,
                                 font=_sfont(self.app.FONT_FAMILY, 9))
        self.data_label.pack(side='right', padx=15, pady=8)
    
    def _create_players_tab(self):
        """Create players browsing and scouting tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Players")
        
        # Filter frame at top
        filter_frame = tk.LabelFrame(tab_frame, text="Player Filters", 
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                   relief="solid", bd=1)
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        filter_row = tk.Frame(filter_frame, bg=self.app.CONTENT_BG)
        filter_row.pack(fill='x', padx=10, pady=5)
        
        # Position filter — segmented pills instead of dropdown
        tk.Label(filter_row, text="Position:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR).pack(side='left')

        self.position_filter = tk.StringVar(value="All")
        from modern_widgets import SegmentedControl
        self.position_segmented = SegmentedControl(
            filter_row, ["All", "F", "D", "G"], initial=0,
            command=lambda v: (self.position_filter.set(v), self._filter_players()),
            accent=self.app.ACCENT_COLOR, bg=self.app.CONTENT_BG,
            fg=self.app.TEXT_COLOR,
            font=_sfont(self.app.FONT_FAMILY, 10, 'bold'))
        self.position_segmented.pack(side='left', padx=(5, 15))
        
        # Team filter
        tk.Label(filter_row, text="Team:", bg=self.app.CONTENT_BG, 
                fg=self.app.TEXT_COLOR).pack(side='left')
        
        self.team_filter = tk.StringVar(value="All")
        self.team_combo = ttk.Combobox(filter_row, textvariable=self.team_filter, width=12)
        self.team_combo.pack(side='left', padx=(5, 15))
        self.team_combo.bind('<<ComboboxSelected>>', self._filter_players)
        
        # Name search
        # Name search lives in the elite filter bar now (StringVar kept for
        # _clear_player_filters compatibility).
        self.name_search = tk.StringVar()
        
        # Clear button
        from modern_widgets import RoundedButton
        clear_btn = RoundedButton(filter_row, text="Clear",
                                  bg=self.app.ACCENT_COLOR,
                                  fg=self.app.HEADER_COLOR,
                                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                  radius=9, padx=14, pady=7,
                                  command=self._clear_player_filters)
        clear_btn.pack(side='left', padx=5)

        # Scouting profile filter
        tk.Label(filter_row, text="Profile:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR).pack(side='left', padx=(15, 0))

        self.profile_filter = tk.StringVar(value="All")
        self.profile_combo = ttk.Combobox(filter_row, textvariable=self.profile_filter,
                                          width=22, state='readonly')
        self.profile_combo.pack(side='left', padx=(5, 5))
        self.profile_combo.bind('<<ComboboxSelected>>', self._filter_players)

        profiles_btn = RoundedButton(filter_row, text="Profiles",
                                     bg=self.app.CONTENT_BG,
                                     fg=self.app.TEXT_COLOR,
                                     font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                     radius=9, padx=14, pady=7,
                                     command=self._open_profile_manager)
        profiles_btn.pack(side='left', padx=5)
        self._refresh_profile_combo()

        # Unified Views & Filters panel (Eastside-style) -- replaces the
        # separate view combobox + filter bar.
        from player_view_ui import ViewsFiltersPanel
        self._pro_view_name = "Scouting Board"
        self._pro_view_ctx = None
        self._pro_sort_col = None
        self._pro_sort_rev = False
        self._pro_panel = ViewsFiltersPanel(
            tab_frame, default_label="Scouting Board",
            on_view_change=self._set_pro_view,
            on_filter_change=self._filter_players)
        self._pro_panel.pack(fill='x', padx=10, pady=(0, 2))

        # Players list
        list_frame = tk.LabelFrame(tab_frame, text="Available Players", 
                                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                 font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                   relief="solid", bd=1)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview
        columns = ['Name', 'Position', 'Age', 'Team', 'Tier', 'Scouted']
        self.players_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        widths = [200, 80, 60, 150, 80, 80]
        for col, width in zip(columns, widths):
            self.players_tree.heading(col, text=col)
            self.players_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.players_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.players_tree.xview)
        self.players_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.players_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # Bind events
        self.players_tree.bind('<Double-1>', self._scout_player)
        self.players_tree.bind('<Button-3>', self._show_player_context_menu)
        
        # Action buttons
        btn_frame = tk.Frame(list_frame, bg=self.app.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        scout_btn = tk.Button(btn_frame, text="Scout Player", 
                             bg=self.app.ACCENT_COLOR, fg=self.app.HEADER_COLOR,
                             command=self._scout_player)
        scout_btn.pack(side='left', padx=(0, 10))
        
        profile_btn = tk.Button(btn_frame, text="View Profile", 
                               bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                               command=self._view_player_profile)
        profile_btn.pack(side='left')
    
    def _create_scouts_tab(self):
        """Create scouts management tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Scouts")
        
        # Scouts list
        list_frame = tk.LabelFrame(tab_frame, text="Scouting Staff", 
                                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                 font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                   relief="solid", bd=1)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview
        columns = ['Name', 'Role', 'Ability', 'Potential', 'Experience', 'Active Tasks']
        self.scouts_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        widths = [150, 120, 80, 80, 80, 100]
        for col, width in zip(columns, widths):
            self.scouts_tree.heading(col, text=col)
            self.scouts_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.scouts_tree.yview)
        self.scouts_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # Pack widgets
        self.scouts_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        
        # Bind events
        self.scouts_tree.bind('<Double-1>', self._view_scout_details)
        # EHM/FM24: right-click a scout row -> staff context menu.
        try:
            from player_context_menu import bind_staff_context

            def _scout_getter(event):
                try:
                    _item = self.scouts_tree.identify_row(event.y)
                    if _item:
                        return self.app.tree_maps.get(
                            'scouts_tree', {}).get(_item)
                except Exception:
                    pass
                return None

            bind_staff_context(self.scouts_tree, _scout_getter, self)
        except Exception:
            pass
        
        # Action buttons
        btn_frame = tk.Frame(list_frame, bg=self.app.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        hire_btn = tk.Button(btn_frame, text="Hire Scout", 
                            bg=self.app.ACCENT_COLOR, fg=self.app.HEADER_COLOR,
                            command=self._hire_scout)
        hire_btn.pack(side='left', padx=(0, 10))
        
        edit_btn = tk.Button(btn_frame, text="Edit Scout", 
                            bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                            command=self._edit_scout)
        edit_btn.pack(side='left')
    
    def _create_draft_tab(self):
        """Create draft prospects tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Draft")

        header = tk.Label(tab_frame, text="Upcoming Draft Class",
                          bg=self.app.CONTENT_BG, fg=self.app.HEADER_COLOR,
                          font=_sfont(self.app.FONT_FAMILY, 12, 'bold'))
        header.pack(anchor="w", padx=12, pady=(10, 4))

        cols = ("Player", "Pos", "Age", "Potential")
        tree = ttk.Treeview(tab_frame, columns=cols, show="headings", height=20)
        for c, w in zip(cols, (220, 70, 60, 100)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center" if c != "Player" else "w")
        tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # EHM/FM24: right-click a draft-class row -> player context menu.
        try:
            _dtm = self.app.tree_maps.setdefault(tree, {})
            _dtm.clear()
        except Exception:
            _dtm = None
        for p in self.game_data.get("draft_class", [])[:200]:
            try:
                pos = getattr(p.primary_position, "value", None)
                if pos is None:
                    pos = str(p.primary_position)
                _iid = tree.insert("", "end", values=(
                    getattr(p, "full_name", "?"), pos,
                    getattr(p, "age", "?"),
                    getattr(p, "potential_grade", getattr(p, "potential", "?"))))
                if _dtm is not None:
                    _dtm[_iid] = p
            except Exception:
                continue
        try:
            self.app._bind_player_context_menu(tree, 'modern_scouting_draft', False)
        except Exception:
            pass

    def _create_assignments_tab(self):
        """Create scouting assignments tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Assignments")
        
        # Active assignments
        active_frame = tk.LabelFrame(tab_frame, text="Active Assignments", 
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                   relief="solid", bd=1)
        active_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview
        columns = ['Scout', 'Player', 'Viewings', 'Accuracy', 'Est. Completion']
        self.assignments_tree = ttk.Treeview(active_frame, columns=columns, show='headings', height=12)
        
        # Configure columns
        widths = [120, 150, 100, 80, 100]
        for col, width in zip(columns, widths):
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(active_frame, orient='vertical', command=self.assignments_tree.yview)
        self.assignments_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # Pack widgets
        self.assignments_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        
        # Action buttons
        btn_frame = tk.Frame(active_frame, bg=self.app.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        new_btn = tk.Button(btn_frame, text="New Assignment", 
                           bg=self.app.ACCENT_COLOR, fg=self.app.HEADER_COLOR,
                           command=self._create_assignment)
        new_btn.pack(side='left', padx=(0, 10))
        
        cancel_btn = tk.Button(btn_frame, text="Cancel Assignment", 
                              bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                              command=self._cancel_assignment)
        cancel_btn.pack(side='left')
    
    def _create_reports_tab(self):
        """Create scouting reports tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Reports")
        
        # Split view: reports list on left, report details on right
        main_paned = tk.PanedWindow(tab_frame, orient='horizontal', bg=self.app.CONTENT_BG)
        main_paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Reports list
        left_frame = tk.LabelFrame(main_paned, text="Scouting Reports", 
                                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                 font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                   relief="solid", bd=1)
        main_paned.add(left_frame)
        
        # Create treeview
        columns = ['Player', 'Scout', 'Date', 'Rating']
        self.reports_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        widths = [150, 120, 100, 80]
        for col, width in zip(columns, widths):
            self.reports_tree.heading(col, text=col)
            self.reports_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(left_frame, orient='vertical', command=self.reports_tree.yview)
        self.reports_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # Pack widgets
        self.reports_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        
        # Bind events
        self.reports_tree.bind('<<TreeviewSelect>>', self._on_report_select)
        
        # Right side - Report details
        right_frame = tk.LabelFrame(main_paned, text="Report Details", 
                                  bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                   relief="solid", bd=1)
        main_paned.add(right_frame)
        
        # Text area for report content
        self.report_text = tk.Text(right_frame, wrap='word', height=15, width=40,
                                  bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                  font=_sfont(self.app.FONT_FAMILY, 10))
        
        report_scrollbar = ttk.Scrollbar(right_frame, orient='vertical', command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scrollbar.set)
        
        # Pack widgets
        self.report_text.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        report_scrollbar.pack(side='right', fill='y', pady=10)

    # ------------------------------------------------------------------
    # Targets tab (scouting shortlist, backed by trade_market -- no
    # parallel store; all reads/writes go through trade_market)
    # ------------------------------------------------------------------
    def _targets_user_team(self):
        """User team: app.user_team first, game_manager fallback."""
        try:
            ut = getattr(self.app, 'user_team', None)
            if ut is not None:
                return ut
        except Exception:
            pass
        try:
            gm = getattr(self.app, 'game_manager', None)
            return getattr(gm, 'user_team', None) if gm else None
        except Exception:
            return None

    def _targets_league(self):
        """League: app.league first, game_manager fallback."""
        try:
            lg = getattr(self.app, 'league', None)
            if lg is not None:
                return lg
        except Exception:
            pass
        try:
            gm = getattr(self.app, 'game_manager', None)
            return getattr(gm, 'league', None) if gm else None
        except Exception:
            return None

    def _targets_section(self, parent, title, pady, columns=None, widths=None):
        """Build one targets section: full-width tree on top, button row
        below. Returns (tree, button_frame)."""
        frame = tk.LabelFrame(parent, text=title,
                              bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                              font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                              relief="solid", bd=1)
        frame.pack(fill='both', expand=True, padx=10, pady=pady)

        list_wrap = tk.Frame(frame, bg=self.app.CONTENT_BG)
        list_wrap.pack(fill='both', expand=True)

        if columns is None:
            columns = ['Player', 'Pos', 'Age', 'Tier', 'Team',
                       'Source', 'Note']
        if widths is None:
            widths = [170, 60, 50, 60, 150, 140, 420]
        tree = ttk.Treeview(list_wrap, columns=columns, show='headings',
                            height=14)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, minwidth=40)

        scrollbar = ttk.Scrollbar(list_wrap, orient='vertical',
                                  command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        btn_frame = tk.Frame(frame, bg=self.app.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        return tree, btn_frame

    def _create_targets_tab(self):
        """Create the Targets tab: the ONE unified trade-targets surface.

        Scout suggestions and user targets share this single list (backed
        by ShortlistManager 'Trade Targets' via trade_market) -- there is
        no second tab and no import step. Scout rows carry the scout's name
        and confidence band; the truth behind a tip is never shown.
        """
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Targets")

        self.targets_tree, t_btn = self._targets_section(
            tab_frame, "Trade targets (unified)", pady=(10, 10))

        add_btn = tk.Button(t_btn, text="Add target",
                            bg=self.app.ACCENT_COLOR, fg=self.app.HEADER_COLOR,
                            command=self._targets_add)
        add_btn.pack(side='left', padx=(0, 10))

        remove_btn = tk.Button(t_btn, text="Remove",
                               bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                               command=self._targets_remove)
        remove_btn.pack(side='left', padx=(0, 10))

        refresh_btn = tk.Button(t_btn, text="Refresh suggestions",
                                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                command=self._targets_refresh_suggestions)
        refresh_btn.pack(side='left')

    def _populate_targets(self):
        """Populate the unified targets list from trade_market."""
        tree = getattr(self, 'targets_tree', None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            import trade_market
        except Exception:
            return
        user_team = self._targets_user_team()
        league = self._targets_league()
        if user_team is None or league is None:
            return
        try:
            entries = trade_market.get_unified_targets(league)
        except Exception:
            entries = []
        maps = getattr(self.app, 'tree_maps', None) or {}
        maps.setdefault('targets_tree', {}).clear()
        if not hasattr(self.app, 'tree_maps'):
            self.app.tree_maps = maps
        for e in entries or []:
            pid = e.get('player_id')
            notes = e.get('notes', '') or ''
            player, team = None, None
            try:
                player, team = trade_market.resolve_player(league, pid)
            except Exception:
                pass
            if player is None:
                try:
                    player, team = trade_market.resolve_player(
                        league, int(pid))
                except Exception:
                    pass
            if player is None:
                player = self._find_nhl_player_by_name(
                    league, e.get('player_name', ''))
            if player is None:
                continue  # left the NHL since being added
            if team is None:
                try:
                    _p, team = trade_market.resolve_player(
                        league, getattr(player, 'id', None))
                except Exception:
                    team = None
            try:
                pos = (player.primary_position.value
                       if hasattr(player.primary_position, 'value')
                       else str(player.primary_position))
            except Exception:
                pos = '?'
            try:
                talent_tier(displayed_overall(player, self._user_team()))  # tier of the
                # fogged estimate -- Muck's directive 2026-10-01: never numeric
            except Exception:
                ovr = '?'
            team_name = getattr(team, 'team_name', '—') if team else '—'
            try:
                kind, who = trade_market._target_source(notes)
            except Exception:
                kind, who = 'user', 'You'
            source = f"Scout: {who}" if kind == 'scout' else who
            # Display note: strip the machine prefixes, keep the meaning
            # (incl. the scout's confidence band).
            disp = notes
            if kind == 'scout' and ':' in notes:
                disp = notes.split(':', 1)[1].strip()
            elif notes.startswith('[') and ']' in notes:
                disp = notes.partition(']')[2].strip()
            values = (
                e.get('player_name') or getattr(player, 'full_name', '?'),
                pos,
                getattr(player, 'age', '?'),
                ovr,
                team_name,
                source,
                disp,
            )
            item = tree.insert('', 'end', values=values)
            maps['targets_tree'][item] = player

    def _targets_add(self):
        """Add-target dialog: pick any NHL player into the shortlist."""
        try:
            import trade_market
        except Exception:
            messagebox.showerror("Targets", "Trade market module unavailable.")
            return
        user_team = self._targets_user_team()
        league = self._targets_league()
        if user_team is None or league is None:
            messagebox.showwarning("No Data", "No league data available.")
            return

        dialog = InGamePopup(self)
        dialog.title("Add Target")
        dialog.geometry("720x520")
        dialog.configure(background=self.app.BG_COLOR)

        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Select a player to add to your targets:",
                  style='Title.TLabel').pack(pady=(0, 8))

        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=(0, 6))
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 6))
        search_var = tk.StringVar(master=dialog)
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side='left')

        columns = ('Name', 'Pos', 'Age', 'Tier', 'Team')
        picker = ttk.Treeview(frame, columns=columns, show='headings', height=14)
        for col, w in zip(columns, (200, 60, 50, 60, 180)):
            picker.heading(col, text=col)
            picker.column(col, width=w)
        picker.pack(fill='both', expand=True)

        # All NHL players across every roster.
        all_rows = []
        try:
            for t in (getattr(league, 'teams', None) or []):
                if getattr(t, 'league_name', '') != 'National Hockey League':
                    continue
                for p in (getattr(t, 'roster', None) or []):
                    all_rows.append((p, t))
        except Exception:
            pass

        rowmap = {}

        def _refill(*_args):
            q = search_var.get().lower()
            for it in picker.get_children():
                picker.delete(it)
            rowmap.clear()
            for p, t in all_rows:
                try:
                    name = p.full_name
                except Exception:
                    continue
                if q and q not in name.lower():
                    continue
                try:
                    pos = (p.primary_position.value
                           if hasattr(p.primary_position, 'value')
                           else str(p.primary_position))
                except Exception:
                    pos = '?'
                try:
                    ovr = p.overall_rating()
                except Exception:
                    ovr = '?'
                iid = picker.insert('', 'end', values=(
                    name, pos, getattr(p, 'age', '?'), talent_tier(ovr),
                    getattr(t, 'team_name', '?')))
                rowmap[iid] = p

        search_var.trace_add('write', _refill)
        _refill()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        def add_selected():
            added = 0
            for iid in picker.selection():
                player = rowmap.get(iid)
                if player is None:
                    continue
                if trade_market.add_to_shortlist(user_team, player,
                                                 added_by="user",
                                                 league=league):
                    added += 1
            self._populate_targets()
            dialog.destroy()
            if added:
                messagebox.showinfo("Targets",
                                    f"Added {added} player(s) to your targets.")

        ttk.Button(btn_frame, text="Add Selected",
                   command=add_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel",
                   command=dialog.destroy).pack(side='left', padx=5)

    def _targets_remove(self):
        """Remove the selected target(s) from the shortlist."""
        try:
            import trade_market
        except Exception:
            return
        user_team = self._targets_user_team()
        league = self._targets_league()
        if user_team is None:
            return
        selection = self.targets_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection",
                                   "Please select a target to remove.")
            return
        for iid in selection:
            player = self.app.tree_maps.get('targets_tree', {}).get(iid)
            if player is None:
                continue
            trade_market.remove_from_shortlist(user_team, player.id,
                                               league=league)
        self._populate_targets()

    def _find_nhl_player_by_name(self, league, name):
        """Name fallback for shortlist entries whose id doesn't resolve."""
        if not name:
            return None
        want = name.strip().lower()
        try:
            for t in (getattr(league, 'teams', None) or []):
                if getattr(t, 'league_name', '') != 'National Hockey League':
                    continue
                for p in (getattr(t, 'roster', None) or []):
                    try:
                        if p.full_name.strip().lower() == want:
                            return p
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def _targets_refresh_suggestions(self):
        """Ask the user's scouts for new value tips (JPA-scaled inside
        trade_market)."""
        try:
            import trade_market
        except Exception:
            return
        user_team = self._targets_user_team()
        league = self._targets_league()
        if user_team is None or league is None:
            messagebox.showwarning("No Data", "No league data available.")
            return
        n = trade_market.refresh_scout_suggestions(self.app, league)
        self._populate_targets()
        if n:
            messagebox.showinfo("Scout suggestions",
                                f"{n} new suggestion(s) from your scouts.")
        else:
            messagebox.showinfo("Scout suggestions",
                                "No new suggestions (your scouts found no new "
                                "value, or you have no scouts on staff).")

    def _load_initial_data(self):
        """Initial data load after the interface is built."""
        self._populate_data()

    def _populate_data(self):
        """Populate all tabs with data"""
        try:
            self._populate_players()
            self._populate_scouts()
            self._populate_assignments()
            self._populate_reports()
            self._populate_targets()
            self._update_status()
        except Exception as e:
            print(f"Error populating scouting data: {e}")
            self.status_label.config(text=f"Error: {e}")
    
    def _user_team(self):
        """The user's team, for fog-of-war display decisions."""
        try:
            gm = getattr(self.app, 'game_manager', None)
            return getattr(gm, 'user_team', None) if gm else None
        except Exception:
            return None

    def _is_player_scouted(self, player):
        """Check if the user team has a scouting report for a player.

        Delegates to the central fog-of-war definition so the label always
        agrees with displayed_overall: own-team players and fog-disabled
        games count as scouted, not just filed reports.
        """
        try:
            from scouting_profiles import is_scouted as central_is_scouted
            return bool(central_is_scouted(player, self._user_team()))
        except Exception:
            pass
        try:
            gm = getattr(self.app, 'game_manager', None)
            team = getattr(gm, 'user_team', None) if gm else None
            reports = getattr(team, 'scouting_reports', None)
            if reports is not None:
                return getattr(player, 'id', str(player)) in reports
        except Exception:
            pass
        return False

    def _refresh_profile_combo(self, select=None):
        """Fill the profile filter dropdown with built-in + custom profiles."""
        try:
            from scouting_profiles import list_profiles
            names = ["All"] + [p.name for p in list_profiles()]
        except Exception:
            names = ["All"]
        if hasattr(self, 'profile_combo'):
            self.profile_combo['values'] = names
            current = select or self.profile_filter.get()
            self.profile_filter.set(current if current in names else "All")

    def _open_profile_manager(self):
        """Open the scouting profile manager as a screen."""
        try:
            from scouting_profile_dialog import ScoutingProfileView

            def _on_apply(name):
                self._refresh_profile_combo(select=name)
                self._populate_players()

            app = self.app if hasattr(self, 'app') else getattr(self, 'parent', None)
            app.show_screen('scouting_profiles', 'Scouting Profiles',
                            ScoutingProfileView, on_apply=_on_apply)
            # Refresh list in case customs were added/removed
            self._refresh_profile_combo()
            self._populate_players()
        except Exception as e:
            messagebox.showerror("Profiles", f"Could not open profile manager:\n{e}")

    def _active_profile(self):
        """Return the selected ScoutingProfile, or None if 'All'."""
        try:
            name = self.profile_filter.get() if hasattr(self, 'profile_filter') else "All"
            if not name or name == "All":
                return None
            from scouting_profiles import get_profile
            return get_profile(name)
        except Exception:
            return None

    def _configure_player_columns(self, with_match):
        """Rebuild treeview columns; adds a Match column when profiling."""
        view_name = getattr(self, '_pro_view_name', 'Scouting Board')
        if view_name != "Scouting Board":
            self._configure_pro_view_columns()
            return
        cols = ['Name', 'Position', 'Age', 'Team', 'Tier', 'Scouted']
        widths = [200, 80, 60, 150, 80, 80]
        if with_match:
            cols.append('Match')
            widths.append(70)
        self.players_tree['columns'] = cols
        self.players_tree['show'] = 'headings'
        for col, width in zip(cols, widths):
            self.players_tree.heading(col, text=col)
            self.players_tree.column(col, width=width, minwidth=50,
                                     anchor='center' if col == 'Match' else 'w')

    # -- FM/Eastside-style views for the pro player list ---------------------
    def _pro_view_ctx_fn(self):
        if self._pro_view_ctx is None:
            from player_views import ViewContext
            self._pro_view_ctx = ViewContext(app=self.app, mode="scouted")
        return self._pro_view_ctx

    def _set_pro_view(self, name):
        self._pro_view_name = name
        self._pro_sort_col = None
        self._pro_sort_rev = False
        self._populate_players()

    def _configure_pro_view_columns(self):
        from player_views import get_view_columns, COLUMN_DEFS
        cols = []
        for key in get_view_columns(self._pro_view_name) or []:
            d = COLUMN_DEFS.get(key)
            if d is not None:
                cols.append((key, d.header, d.width))
        tree = self.players_tree
        tree['columns'] = [k for k, _, _ in cols]
        tree['show'] = 'headings'
        for key, header, width in cols:
            tree.heading(key, text=header,
                         command=lambda c=key: self._sort_pro_players(c))
            tree.column(key, width=width, minwidth=40,
                        anchor='w' if key == 'name' else 'center')

    def _sort_pro_players(self, col):
        from player_views import column_sort
        tree = self.players_tree
        if self._pro_sort_col == col:
            self._pro_sort_rev = not self._pro_sort_rev
        else:
            self._pro_sort_col = col
            self._pro_sort_rev = False
        rev = self._pro_sort_rev
        ctx = self._pro_view_ctx_fn()
        tm = self.app.tree_maps.get('players_tree', {})
        numeric, textual, missing = [], [], []
        for item_id in tree.get_children():
            p = tm.get(item_id)
            try:
                v = column_sort(col, p, ctx) if p is not None else None
            except Exception:
                v = None
            nm = getattr(p, "full_name", "") or ""
            if v is None:
                missing.append(item_id)
            elif isinstance(v, (int, float)):
                numeric.append((v, nm.lower(), item_id))
            else:
                textual.append((str(v).lower(), item_id))
        numeric.sort(key=lambda r: (r[0], r[1]), reverse=not rev)
        textual.sort(key=lambda r: r[0], reverse=rev)
        ordered = ([iid for _, _, iid in numeric] +
                   [iid for _, iid in textual] + missing)
        for i, item_id in enumerate(ordered):
            tree.move(item_id, '', i)

    def _populate_players(self):
        """Populate the players tree"""
        # Clear existing items
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)

        # Initialize tree maps
        if 'players_tree' not in self.app.tree_maps:
            self.app.tree_maps['players_tree'] = {}

        # Get team names for filter
        teams = set()
        for player in self.all_players:
            team_name = getattr(player, 'team_name', 'Free Agent')
            teams.add(team_name)

        # Update team filter combobox if it exists
        if hasattr(self, 'team_combo') and teams:
            current_teams = ["All"] + sorted(list(teams))
            self.team_combo['values'] = current_teams

        # Apply current filters
        filtered_players = self._apply_player_filters()
        profile_active = bool(getattr(self, '_profile_scores', None))

        # Configure columns (Match column appears when a profile is applied)
        self._configure_player_columns(profile_active)

        # Add players to tree
        for player in filtered_players:
            try:
                # FM-style alternate view: shared column preset.
                if getattr(self, '_pro_view_name',
                           'Scouting Board') != "Scouting Board":
                    self._add_pro_view_row(player)
                    continue
                # Check if player has been scouted
                scouted = "Yes" if self._is_player_scouted(player) else "No"

                values = (
                    player.full_name,
                    player.primary_position.value if hasattr(player.primary_position, 'value') else str(player.primary_position),
                    player.age,
                    getattr(player, 'team_name', 'Free Agent'),
                    # Fog of war: unscouted players show a noisy estimate;
                    # the tier is derived from the noisy value (Muck's
                    # directive 2026-10-01 -- never the numeric overall)
                    talent_tier(displayed_overall(player, self._user_team())),
                    scouted
                )
                if profile_active:
                    pid = getattr(player, 'id', str(player))
                    score = self._profile_scores.get(pid, 0)
                    values = values + (f"{score:.0f}%",)

                item = self.players_tree.insert('', 'end', values=values)

                # Store player reference
                self.app.tree_maps['players_tree'][item] = player

            except Exception as e:
                print(f"Error adding player {getattr(player, 'full_name', 'Unknown')}: {e}")
                continue

        fb = getattr(self, '_pro_panel', None)
        if fb is not None:
            try:
                fb.set_count(len(self.players_tree.get_children()),
                             len(self.all_players))
            except Exception:
                pass

    def _add_pro_view_row(self, player):
        """One row from the shared view definition (scout-perceived)."""
        from player_views import get_view_columns, column_text
        cols = [c for c in (get_view_columns(self._pro_view_name) or [])
                if c]
        ctx = self._pro_view_ctx_fn()
        values = [column_text(c, player, ctx) for c in cols]
        item = self.players_tree.insert('', 'end', values=values)
        self.app.tree_maps['players_tree'][item] = player

    def _populate_scouts(self):
        """Populate the scouts tree"""
        # Clear existing items
        for item in self.scouts_tree.get_children():
            self.scouts_tree.delete(item)
        
        # Initialize tree maps
        if 'scouts_tree' not in self.app.tree_maps:
            self.app.tree_maps['scouts_tree'] = {}
        
        # Add scouts to tree
        try:
            from scouting_window_helpers import assignments_of
            _live_assigns = assignments_of(self.app)
        except Exception:
            _live_assigns = {}
        for scout in self.all_scouts:
            try:
                # Count real active assignments for this scout
                active_tasks = sum(1 for s in _live_assigns.values() if s is scout)
                
                item = self.scouts_tree.insert('', 'end', values=(
                    scout.full_name,
                    getattr(scout, 'scout_title', getattr(scout, 'role', 'Scout')),
                    getattr(scout, 'judging_player_ability', 'N/A'),
                    getattr(scout, 'judging_player_potential', 'N/A'),
                    f"{getattr(scout, 'scouting_experience', 0)} yrs",
                    str(active_tasks)
                ))
                
                # Store scout reference
                self.app.tree_maps['scouts_tree'][item] = scout
                
            except Exception as e:
                print(f"Error adding scout {getattr(scout, 'full_name', 'Unknown')}: {e}")
                continue
    
    def _populate_assignments(self):
        """Populate the assignments tree from the REAL scouting_assignments.

        Rows are the live {Player: Staff} assignments the engine processes
        daily; progress/accuracy come from the real filed reports and the
        completion estimate is derived from live state. Item -> player refs
        are kept in app.tree_maps['assignments_tree'] for cancel.
        """
        # Clear existing items
        for item in self.assignments_tree.get_children():
            self.assignments_tree.delete(item)

        try:
            from scouting_window_helpers import (
                assignments_of, estimate_completion_days, reports_of)
        except Exception:
            return
        assigns = assignments_of(self.app)
        reports = reports_of(self.app)
        if 'assignments_tree' not in self.app.tree_maps:
            self.app.tree_maps['assignments_tree'] = {}
        tree_map = self.app.tree_maps['assignments_tree']
        tree_map.clear()

        for player, scout in assigns.items():
            try:
                report = reports.get(getattr(player, "id", None))
                views = getattr(report, "viewings", 0) if report else 0
                acc = getattr(report, "accuracy", "—") if report else "—"
                days = estimate_completion_days(self.app, player, scout)
                if days == 0:
                    eta = "complete"
                elif days is None:
                    eta = "—"
                else:
                    eta = f"~{days}d"
                item = self.assignments_tree.insert('', 'end', values=(
                    getattr(scout, "full_name", "?"),
                    getattr(player, "full_name", "?"),
                    views,
                    acc,
                    eta,
                ))
                tree_map[item] = player
            except Exception as e:
                print(f"Error adding assignment: {e}")
                continue

    def _populate_reports(self):
        """Populate the reports tree from the REAL filed scouting_reports.

        Every row is a real ScoutingReport the engine built up via
        report.update_report; dates are the real last-viewed timestamps and
        ratings are the real accuracy grades. Item -> (player, report) refs
        are kept in app.tree_maps['reports_tree'] for the detail pane.
        """
        # Clear existing items
        for item in self.reports_tree.get_children():
            self.reports_tree.delete(item)

        try:
            from scouting_window_helpers import reports_of
        except Exception:
            return
        reports = reports_of(self.app)
        if 'reports_tree' not in self.app.tree_maps:
            self.app.tree_maps['reports_tree'] = {}
        tree_map = self.app.tree_maps['reports_tree']
        tree_map.clear()

        def _player_for(pid):
            for p in (self.all_players or []):
                if getattr(p, "id", None) == pid:
                    return p
            return None

        rows = []
        for pid, report in reports.items():
            try:
                player = _player_for(pid)
                name = getattr(player, "full_name", None) or f"Player {pid}"
                scout_name = getattr(getattr(report, "scout", None),
                                     "full_name", "—")
                last = getattr(report, "last_viewed", None)
                try:
                    datestr = last.strftime("%Y-%m-%d") if last else "—"
                except Exception:
                    datestr = "—"
                acc = getattr(report, "accuracy", "?")
                rows.append((datestr, name, scout_name, acc, player, report))
            except Exception as e:
                print(f"Error adding report: {e}")
                continue
        rows.sort(key=lambda r: r[0], reverse=True)
        for datestr, name, scout_name, acc, player, report in rows:
            item = self.reports_tree.insert('', 'end', values=(
                name, scout_name, datestr, acc))
            tree_map[item] = (player, report)
    
    def _apply_player_filters(self):
        """Apply current filters to player list"""
        filtered = self.all_players.copy()
        
        # Position filter (supports F/D/G groups from the segmented control)
        if hasattr(self, 'position_filter'):
            position = self.position_filter.get()
            if position != "All":
                group_map = {"F": ("C", "LW", "RW", "F"),
                             "D": ("LD", "RD", "D"),
                             "G": ("G",)}
                wanted = group_map.get(position, (position,))
                def _pos_of(p):
                    pp = getattr(p, 'primary_position', '')
                    return getattr(pp, 'value', str(pp))
                filtered = [p for p in filtered if _pos_of(p) in wanted]
        
        # Team filter
        if hasattr(self, 'team_filter'):
            team = self.team_filter.get()
            if team != "All":
                filtered = [p for p in filtered if getattr(p, 'team_name', 'Free Agent') == team]
        
        # Name search (legacy box removed; the elite filter bar owns search
        # now -- skip the dead StringVar when the bar exists)
        if hasattr(self, 'name_search') and not hasattr(self, '_pro_panel'):
            search = self.name_search.get().lower()
            if search:
                filtered = [p for p in filtered if search in p.full_name.lower()]

        # Scouting profile filter (sorted by match score, best first)
        self._profile_scores = {}
        profile = self._active_profile()
        if profile is not None:
            try:
                from scouting_profiles import filter_by_profile
                matches = filter_by_profile(filtered, profile, self._is_player_scouted)
                self._profile_scores = {
                    getattr(p, 'id', str(p)): score for p, score in matches
                }
                filtered = [p for p, _ in matches]
            except Exception as e:
                print(f"Error applying scouting profile: {e}")

        # Elite filter bar (text search + attribute thresholds), additive.
        # Thresholds use the scout-perception lens: barely-scouted players
        # filter on what your scouts actually know.
        fb = getattr(self, '_pro_panel', None)
        if fb is not None:
            pf = fb.get_filter()
            if not pf.is_empty():
                ctx = self._pro_view_ctx_fn()
                filtered = [p for p in filtered if pf.matches(p, ctx)]

        return filtered

    def _update_status(self):
        """Update the status bar"""
        try:
            player_count = len(self.all_players)
            scout_count = len(self.all_scouts)
            text = f"Players: {player_count} | Scouts: {scout_count}"
            profile = self._active_profile()
            if profile is not None:
                n = len(getattr(self, '_profile_scores', {}) or {})
                text += f" | Profile: {profile.name} ({n} matches)"
            self.status_label.config(text=text)
        except Exception as e:
            self.status_label.config(text=f"Error: {e}")

    
    # Event handlers and action methods
    def _filter_players(self, event=None):
        """Filter players based on current settings"""
        self._populate_players()
    
    def _clear_player_filters(self):
        """Clear all player filters"""
        if hasattr(self, 'position_segmented'):
            self.position_segmented.set("All")  # also sets StringVar + refilters
        else:
            self.position_filter.set("All")
        self.team_filter.set("All")
        self.name_search.set("")
        if hasattr(self, 'profile_filter'):
            self.profile_filter.set("All")
        self._populate_players()
    
    def _scout_player(self, event=None):
        """Scout selected player -- opens the real assignment dialog.

        Writes a REAL scouting assignment into app.scouting_assignments
        (the dict the engine processes daily). The dialog is non-modal and
        shows the real estimated completion derived from live state.
        Dismissing it defers -- nothing is created.
        """
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to scout.")
            return

        item = selection[0]
        player = self.app.tree_maps['players_tree'].get(item)

        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return

        try:
            from scouting_window_helpers import (
                open_assignment_dialog, scouts_of)
        except Exception as e:
            messagebox.showerror("Scouting", f"Scouting helpers unavailable: {e}")
            return

        if not scouts_of(self.app):
            messagebox.showwarning(
                "No Scouts",
                "You need scouts before you can assign scouting tasks.\n\n"
                "Hire scouts via Staff → Hire Staff (free-agent staff market).")
            return

        open_assignment_dialog(self, self.app, player=player,
                               on_created=self._populate_assignments)
    
    def _view_player_profile(self):
        """View selected player's profile"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to view.")
            return
        
        item = selection[0]
        player = self.app.tree_maps['players_tree'].get(item)
        
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Open the player profile as a full screen in the main instance
        try:
            if hasattr(self.app, "open_player_profile"):
                self.app.open_player_profile(player)
            else:
                from ui_components import PlayerProfileWindow
                PlayerProfileWindow(self.app, player)
        except ImportError:
            # Fallback - show basic info
            info = f"""
Player Profile
══════════════

Name: {player.full_name}
Position: {player.primary_position.value if hasattr(player.primary_position, 'value') else str(player.primary_position)}
Age: {player.age}
Team: {getattr(player, 'team_name', 'Free Agent')}
Tier: {talent_tier(displayed_overall(player, self._user_team()))}

Attributes:
Skating: {to_100_scale(displayed_attribute(player, 'skating', self._user_team())):.0f}
Shooting: {to_100_scale(displayed_attribute(player, 'shooting', self._user_team())):.0f}
Passing: {to_100_scale(displayed_attribute(player, 'passing', self._user_team())):.0f}
Checking: {to_100_scale(displayed_attribute(player, 'checking', self._user_team())):.0f}
            """
            messagebox.showinfo("Player Profile", info.strip())
    
    def _show_player_context_menu(self, event):
        """Show full player context menu (universal + scouting actions)."""
        # Select item under cursor
        item = self.players_tree.identify_row(event.y)
        if not item:
            return
        self.players_tree.selection_set(item)
        player = self.app.tree_maps.get('players_tree', {}).get(item)
        if not player:
            return
        PlayerContextMenu(self.app).show_context_menu(
            event, player,
            additional_options=[
                ("Scout Player", self._scout_player),
                ("Add to Shortlist", self._add_to_shortlist),
            ])

    def _add_to_shortlist(self):
        """Add the selected player to the REAL ShortlistManager."""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to add to the shortlist.")
            return

        item = selection[0]
        player = self.app.tree_maps['players_tree'].get(item)

        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return

        try:
            from scouting_window_helpers import open_shortlist_dialog
        except Exception as e:
            messagebox.showerror("Shortlist", f"Shortlist helpers unavailable: {e}")
            return
        open_shortlist_dialog(self, self.app, player)
    
    def _view_scout_details(self, event=None):
        """View scout details"""
        selection = self.scouts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scout to view details.")
            return
        
        item = selection[0]
        scout = self.app.tree_maps['scouts_tree'].get(item)
        
        if not scout:
            messagebox.showerror("Error", "Could not find selected scout.")
            return
        
        # Show scout details
        details = f"""
Scout Profile
═════════════

Name: {scout.full_name}
Role: {getattr(scout, 'scout_title', getattr(scout, 'role', 'Scout'))}

Abilities:
Judging Player Ability: {getattr(scout, 'judging_player_ability', 'N/A')}
Judging Player Potential: {getattr(scout, 'judging_player_potential', 'N/A')}
Experience: {getattr(scout, 'scouting_experience', 0)} years

Current Status: Available for assignments
        """
        
        messagebox.showinfo("Scout Details", details.strip())
    
    def _hire_scout(self):
        """Hire a scout through the REAL staff hiring system.

        Scout hiring runs through Staff → Hire Staff (the free-agent staff
        market with real contract negotiation), so this routes there instead
        of inventing a candidate.
        """
        try:
            self.app.open_staff_management_window()
        except Exception as e:
            messagebox.showerror("Staff", f"Could not open Staff Management:\n{e}")

    def _edit_scout(self):
        """Edit the selected scout through the REAL staff system.

        Opens the staff details window (contract, role, release) for the
        selected scout -- the same surface Staff Management uses.
        """
        selection = self.scouts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scout to edit.")
            return

        item = selection[0]
        scout = self.app.tree_maps['scouts_tree'].get(item)

        if not scout:
            messagebox.showerror("Error", "Could not find selected scout.")
            return

        try:
            from staff_management_window import StaffManagementView
            view = self.app.show_screen('staff_management', 'Staff',
                                        StaffManagementView)
            view.show_staff_details_window(scout, True)
        except Exception as e:
            messagebox.showerror("Staff", f"Could not open scout details:\n{e}")

    def _create_assignment(self):
        """Create a REAL scouting assignment (non-modal dialog).

        Writes into app.scouting_assignments -- the same store the engine
        processes daily. Shows the real estimated completion derived from
        live state. Dismissing the dialog defers.
        """
        try:
            from scouting_window_helpers import (
                open_assignment_dialog, scouts_of)
        except Exception as e:
            messagebox.showerror("Scouting", f"Scouting helpers unavailable: {e}")
            return

        if not scouts_of(self.app):
            messagebox.showwarning(
                "No Scouts",
                "You need scouts before you can create assignments.\n\n"
                "Hire scouts via Staff → Hire Staff (free-agent staff market).")
            return

        open_assignment_dialog(self, self.app,
                               on_created=self._populate_assignments)
    
    def _cancel_assignment(self):
        """Cancel the selected REAL scouting assignment."""
        selection = self.assignments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assignment to cancel.")
            return

        player = self.app.tree_maps.get('assignments_tree', {}).get(selection[0])
        if player is None:
            messagebox.showerror("Error", "Could not find the selected assignment.")
            return

        try:
            from scouting_window_helpers import cancel_scout_assignment
        except Exception as e:
            messagebox.showerror("Scouting", f"Scouting helpers unavailable: {e}")
            return

        def _do_cancel():
            ok, msg = cancel_scout_assignment(self.app, player)
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Assignment Cancelled" if ok else "Scouting", msg)
            self._populate_assignments()

        # Gating T2-Phase 3: non-modal confirm; dismiss = keep scouting.
        confirm_card(self, "Cancel Assignment",
                     f"Stop scouting {getattr(player, 'full_name', 'this player')}?\n\n"
                     "The scout is freed up; any report filed so far is kept.",
                     on_yes=_do_cancel)
    
    def _on_report_select(self, event):
        """Handle report selection -- renders the REAL filed report.

        Fog-of-war safe: only the graded information the scout actually
        filed (accuracy, viewings, graded potential range, strengths /
        weaknesses the report lists). Never raw attributes.
        """
        selection = self.reports_tree.selection()
        self.report_text.delete('1.0', tk.END)
        if not selection:
            return

        entry = self.app.tree_maps.get('reports_tree', {}).get(selection[0])
        if not entry:
            return
        player, report = entry
        if report is None:
            return

        try:
            from scouting_window_helpers import report_display_lines
        except Exception:
            return
        rows, pot = report_display_lines(player, report)

        try:
            pos = player.primary_position.value
        except Exception:
            pos = str(getattr(player, "primary_position", "?"))
        header = (f"SCOUTING REPORT\n{'═' * 15}\n\n"
                  f"Player: {getattr(player, 'full_name', '?')}\n"
                  f"Position: {pos}\n"
                  f"Age: {getattr(player, 'age', '?')}\n"
                  f"Team: {getattr(player, 'team_name', 'Free Agent')}\n\n"
                  f"GRADED POTENTIAL: {pot}\n\n")
        self.report_text.insert('1.0', header)
        for label, text in rows:
            self.report_text.insert(tk.END, f"{label.upper()}\n{text}\n\n")
    
    def update_views(self):
        """Update all views (called when game data changes)"""
        self._load_game_data()
        self._populate_data()


class ModernScoutingWindow(InGamePopup):
    """Popup wrapper around ModernScoutingView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Professional Scouting Center")
        self._view = ModernScoutingView(self, app=parent, *args, **kwargs)
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


# Integration function for main application  
