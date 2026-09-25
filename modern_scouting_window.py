"""
Modern Scouting Management Window
Professional scouting system with comprehensive features
Includes: Scout management, player evaluation, assignments, reports, and draft analysis
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Any
import datetime
import random
from game_classes import Player, PlayerPosition, Staff, StaffRole


class ModernScoutingWindow(tk.Toplevel):
    """Professional scouting management interface with dedicated draft support"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Professional Scouting Center")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1400x900")
        self.minsize(1000, 700)
        self.resizable(True, True)
        
        # Data containers
        self.game_data = self._get_game_data()
        self.all_players = list(self.game_data.get('players', []))
        self.all_scouts = list(self.game_data.get('scouts', []))
        self.filter_vars = {}
        self.ui_components = {}
        
        # Initialize UI management
        self._ensure_tree_maps()
        
        # Build interface
        self._create_interface()
        self._load_initial_data()
        
        # Register window
        self.parent.open_windows['scouting'] = self
        
        # Center window on screen
        self._center_window()
        
    def _get_game_data(self) -> Dict[str, Any]:
        """Get all game data in organized structure"""
        try:
            game_manager = getattr(self.parent, 'game_manager', None)
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
        if not hasattr(self.parent, 'tree_maps'):
            self.parent.tree_maps = {}
        
        required_maps = ['players_tree', 'scouts_tree', 'assignments_tree', 'reports_tree', 'draft_tree']
        for map_name in required_maps:
            if map_name not in self.parent.tree_maps:
                self.parent.tree_maps[map_name] = {}
    
    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
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
        
        # Professional status bar
        self._create_status_bar()
        
    def _create_header(self):
        """Create professional header section"""
        header_frame = tk.Frame(self, bg=self.parent.TITLE_BAR_COLOR, height=70)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Title and subtitle
        title_frame = tk.Frame(header_frame, bg=self.parent.TITLE_BAR_COLOR)
        title_frame.pack(expand=True)
        
        title_label = tk.Label(title_frame, text="PROFESSIONAL SCOUTING CENTER",
                              font=(self.parent.FONT_FAMILY, 18, "bold"),
                              bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.HEADER_COLOR)
        title_label.pack(pady=(15, 2))
        
        # Current date and status
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        subtitle = f"Scouting Operations • {current_date}"
        subtitle_label = tk.Label(title_frame, text=subtitle,
                                font=(self.parent.FONT_FAMILY, 10),
                                bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR)
        subtitle_label.pack()
        
    def _create_status_bar(self):
        """Create professional status bar"""
        status_frame = tk.Frame(self, bg=self.parent.TITLE_BAR_COLOR, height=35)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        # Left side - main status
        self.status_label = tk.Label(status_frame, text="System Ready",
                                   bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 9))
        self.status_label.pack(side='left', padx=15, pady=8)
        
        # Right side - data counts
        self.data_label = tk.Label(status_frame, text="Loading data...",
                                 bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR,
                                 font=(self.parent.FONT_FAMILY, 9))
        self.data_label.pack(side='right', padx=15, pady=8)
    
    def _create_players_tab(self):
        """Create players browsing and scouting tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="🏒 Players")
        
        # Filter frame at top
        filter_frame = tk.LabelFrame(tab_frame, text="Player Filters", 
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 10, "bold"))
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        filter_row = tk.Frame(filter_frame, bg=self.parent.CONTENT_BG)
        filter_row.pack(fill='x', padx=10, pady=5)
        
        # Position filter
        tk.Label(filter_row, text="Position:", bg=self.parent.CONTENT_BG, 
                fg=self.parent.TEXT_COLOR).pack(side='left')
        
        self.position_filter = tk.StringVar(value="All")
        position_combo = ttk.Combobox(filter_row, textvariable=self.position_filter, width=10,
                                     values=["All", "C", "LW", "RW", "LD", "RD", "G"])
        position_combo.pack(side='left', padx=(5, 15))
        position_combo.bind('<<ComboboxSelected>>', self._filter_players)
        
        # Team filter
        tk.Label(filter_row, text="Team:", bg=self.parent.CONTENT_BG, 
                fg=self.parent.TEXT_COLOR).pack(side='left')
        
        self.team_filter = tk.StringVar(value="All")
        self.team_combo = ttk.Combobox(filter_row, textvariable=self.team_filter, width=12)
        self.team_combo.pack(side='left', padx=(5, 15))
        self.team_combo.bind('<<ComboboxSelected>>', self._filter_players)
        
        # Name search
        tk.Label(filter_row, text="Search:", bg=self.parent.CONTENT_BG, 
                fg=self.parent.TEXT_COLOR).pack(side='left')
        
        self.name_search = tk.StringVar()
        search_entry = tk.Entry(filter_row, textvariable=self.name_search, width=20)
        search_entry.pack(side='left', padx=(5, 15))
        search_entry.bind('<KeyRelease>', self._filter_players)
        
        # Clear button
        from modern_widgets import RoundedButton
        clear_btn = RoundedButton(filter_row, text="Clear",
                                  bg=self.parent.ACCENT_COLOR,
                                  fg=self.parent.HEADER_COLOR,
                                  font=(self.parent.FONT_FAMILY, 10, "bold"),
                                  radius=9, padx=14, pady=7,
                                  command=self._clear_player_filters)
        clear_btn.pack(side='left', padx=5)

        # Scouting profile filter
        tk.Label(filter_row, text="Profile:", bg=self.parent.CONTENT_BG,
                fg=self.parent.TEXT_COLOR).pack(side='left', padx=(15, 0))

        self.profile_filter = tk.StringVar(value="All")
        self.profile_combo = ttk.Combobox(filter_row, textvariable=self.profile_filter,
                                          width=22, state='readonly')
        self.profile_combo.pack(side='left', padx=(5, 5))
        self.profile_combo.bind('<<ComboboxSelected>>', self._filter_players)

        profiles_btn = RoundedButton(filter_row, text="⚙ Profiles",
                                     bg=self.parent.CONTENT_BG,
                                     fg=self.parent.TEXT_COLOR,
                                     font=(self.parent.FONT_FAMILY, 10, "bold"),
                                     radius=9, padx=14, pady=7,
                                     command=self._open_profile_manager)
        profiles_btn.pack(side='left', padx=5)
        self._refresh_profile_combo()
        
        # Players list
        list_frame = tk.LabelFrame(tab_frame, text="Available Players", 
                                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                 font=(self.parent.FONT_FAMILY, 10, "bold"))
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview
        columns = ['Name', 'Position', 'Age', 'Team', 'Overall', 'Scouted']
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
        btn_frame = tk.Frame(list_frame, bg=self.parent.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        scout_btn = tk.Button(btn_frame, text="🔍 Scout Player", 
                             bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                             command=self._scout_player)
        scout_btn.pack(side='left', padx=(0, 10))
        
        profile_btn = tk.Button(btn_frame, text="� View Profile", 
                               bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                               command=self._view_player_profile)
        profile_btn.pack(side='left')
    
    def _create_scouts_tab(self):
        """Create scouts management tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="👥 Scouts")
        
        # Scouts list
        list_frame = tk.LabelFrame(tab_frame, text="Scouting Staff", 
                                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                 font=(self.parent.FONT_FAMILY, 10, "bold"))
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
        
        # Action buttons
        btn_frame = tk.Frame(list_frame, bg=self.parent.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        hire_btn = tk.Button(btn_frame, text="➕ Hire Scout", 
                            bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                            command=self._hire_scout)
        hire_btn.pack(side='left', padx=(0, 10))
        
        edit_btn = tk.Button(btn_frame, text="📝 Edit Scout", 
                            bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                            command=self._edit_scout)
        edit_btn.pack(side='left')
    
    def _create_draft_tab(self):
        """Create draft prospects tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="📋 Draft")

        header = tk.Label(tab_frame, text="Upcoming Draft Class",
                          bg=self.parent.CONTENT_BG, fg=self.parent.HEADER_COLOR,
                          font=(self.parent.FONT_FAMILY, 12, "bold"))
        header.pack(anchor="w", padx=12, pady=(10, 4))

        cols = ("Player", "Pos", "Age", "Potential")
        tree = ttk.Treeview(tab_frame, columns=cols, show="headings", height=20)
        for c, w in zip(cols, (220, 70, 60, 100)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center" if c != "Player" else "w")
        tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for p in self.game_data.get("draft_class", [])[:200]:
            try:
                pos = getattr(p.primary_position, "value", str(p.primary_position))
                tree.insert("", "end", values=(
                    getattr(p, "full_name", "?"), pos,
                    getattr(p, "age", "?"),
                    getattr(p, "potential_grade", getattr(p, "potential", "?"))))
            except Exception:
                continue

    def _create_assignments_tab(self):
        """Create scouting assignments tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="📋 Assignments")
        
        # Active assignments
        active_frame = tk.LabelFrame(tab_frame, text="Active Assignments", 
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 10, "bold"))
        active_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview
        columns = ['Scout', 'Player', 'Started', 'Progress', 'Est. Complete']
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
        btn_frame = tk.Frame(active_frame, bg=self.parent.CONTENT_BG)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        new_btn = tk.Button(btn_frame, text="➕ New Assignment", 
                           bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                           command=self._create_assignment)
        new_btn.pack(side='left', padx=(0, 10))
        
        cancel_btn = tk.Button(btn_frame, text="❌ Cancel Assignment", 
                              bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                              command=self._cancel_assignment)
        cancel_btn.pack(side='left')
    
    def _create_reports_tab(self):
        """Create scouting reports tab"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="📄 Reports")
        
        # Split view: reports list on left, report details on right
        main_paned = tk.PanedWindow(tab_frame, orient='horizontal', bg=self.parent.CONTENT_BG)
        main_paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Reports list
        left_frame = tk.LabelFrame(main_paned, text="Scouting Reports", 
                                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                 font=(self.parent.FONT_FAMILY, 10, "bold"))
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
                                  bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 10, "bold"))
        main_paned.add(right_frame)
        
        # Text area for report content
        self.report_text = tk.Text(right_frame, wrap='word', height=15, width=40,
                                  bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 10))
        
        report_scrollbar = ttk.Scrollbar(right_frame, orient='vertical', command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scrollbar.set)
        
        # Pack widgets
        self.report_text.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        report_scrollbar.pack(side='right', fill='y', pady=10)
    
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
            self._update_status()
        except Exception as e:
            print(f"Error populating scouting data: {e}")
            self.status_label.config(text=f"Error: {e}")
    
    def _is_player_scouted(self, player):
        """Check if the user team has a scouting report for a player."""
        try:
            gm = getattr(self.parent, 'game_manager', None)
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
        """Open the scouting profile manager dialog."""
        try:
            from scouting_profile_dialog import ScoutingProfileDialog

            def _on_apply(name):
                self._refresh_profile_combo(select=name)
                self._populate_players()

            ScoutingProfileDialog(self, on_apply=_on_apply)
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
        cols = ['Name', 'Position', 'Age', 'Team', 'Overall', 'Scouted']
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

    def _populate_players(self):
        """Populate the players tree"""
        # Clear existing items
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)

        # Initialize tree maps
        if 'players_tree' not in self.parent.tree_maps:
            self.parent.tree_maps['players_tree'] = {}

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
                # Check if player has been scouted
                scouted = "Yes" if self._is_player_scouted(player) else "No"

                values = (
                    player.full_name,
                    player.primary_position.value if hasattr(player.primary_position, 'value') else str(player.primary_position),
                    player.age,
                    getattr(player, 'team_name', 'Free Agent'),
                    player.overall_rating(),
                    scouted
                )
                if profile_active:
                    pid = getattr(player, 'id', str(player))
                    score = self._profile_scores.get(pid, 0)
                    values = values + (f"{score:.0f}%",)

                item = self.players_tree.insert('', 'end', values=values)

                # Store player reference
                self.parent.tree_maps['players_tree'][item] = player

            except Exception as e:
                print(f"Error adding player {getattr(player, 'full_name', 'Unknown')}: {e}")
                continue
    
    def _populate_scouts(self):
        """Populate the scouts tree"""
        # Clear existing items
        for item in self.scouts_tree.get_children():
            self.scouts_tree.delete(item)
        
        # Initialize tree maps
        if 'scouts_tree' not in self.parent.tree_maps:
            self.parent.tree_maps['scouts_tree'] = {}
        
        # Add scouts to tree
        for scout in self.all_scouts:
            try:
                # Count active assignments
                active_tasks = 0
                if hasattr(scout, 'id'):
                    active_tasks = len([a for a in self.current_assignments.values() 
                                      if a.get('scout_id') == scout.id])
                
                item = self.scouts_tree.insert('', 'end', values=(
                    scout.full_name,
                    getattr(scout, 'scout_title', getattr(scout, 'role', 'Scout')),
                    getattr(scout, 'judging_player_ability', 'N/A'),
                    getattr(scout, 'judging_player_potential', 'N/A'),
                    f"{getattr(scout, 'scouting_experience', 0)} yrs",
                    str(active_tasks)
                ))
                
                # Store scout reference
                self.parent.tree_maps['scouts_tree'][item] = scout
                
            except Exception as e:
                print(f"Error adding scout {getattr(scout, 'full_name', 'Unknown')}: {e}")
                continue
    
    def _populate_assignments(self):
        """Populate the assignments tree"""
        # Clear existing items
        for item in self.assignments_tree.get_children():
            self.assignments_tree.delete(item)
        
        # Add sample assignments (in real implementation, load from saved data)
        if self.all_scouts:
            sample_assignment = self.assignments_tree.insert('', 'end', values=(
                self.all_scouts[0].full_name if self.all_scouts else "No Scout",
                "Connor McDavid",
                "2024-12-01",
                "In Progress",
                "2024-12-15"
            ))
    
    def _populate_reports(self):
        """Populate the reports tree"""
        # Clear existing items
        for item in self.reports_tree.get_children():
            self.reports_tree.delete(item)
        
        # Add sample reports (in real implementation, load from saved reports)
        if self.all_scouts:
            sample_report = self.reports_tree.insert('', 'end', values=(
                "Sidney Crosby",
                self.all_scouts[0].full_name if self.all_scouts else "Unknown Scout",
                "2024-11-28",
                "A+"
            ))
    
    def _apply_player_filters(self):
        """Apply current filters to player list"""
        filtered = self.all_players.copy()
        
        # Position filter
        if hasattr(self, 'position_filter'):
            position = self.position_filter.get()
            if position != "All":
                filtered = [p for p in filtered 
                          if (hasattr(p.primary_position, 'value') and p.primary_position.value == position) or
                             str(p.primary_position) == position]
        
        # Team filter
        if hasattr(self, 'team_filter'):
            team = self.team_filter.get()
            if team != "All":
                filtered = [p for p in filtered if getattr(p, 'team_name', 'Free Agent') == team]
        
        # Name search
        if hasattr(self, 'name_search'):
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
        self.position_filter.set("All")
        self.team_filter.set("All")
        self.name_search.set("")
        if hasattr(self, 'profile_filter'):
            self.profile_filter.set("All")
        self._populate_players()
    
    def _scout_player(self, event=None):
        """Scout selected player"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to scout.")
            return
        
        item = selection[0]
        player = self.parent.tree_maps['players_tree'].get(item)
        
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Check if we have scouts available
        if not self.all_scouts:
            messagebox.showwarning("No Scouts", "You need scouts before you can assign scouting tasks.")
            return
        
        # Simple scouting assignment
        result = messagebox.askyesno("Scout Player", 
                                   f"Assign a scout to evaluate {player.full_name}?\n\n"
                                   f"This will provide detailed information about the player's abilities.")
        
        if result:
            messagebox.showinfo("Scout Assigned", f"Scout assigned to evaluate {player.full_name}!")
            # In a full implementation, this would create an actual scouting assignment
    
    def _view_player_profile(self):
        """View selected player's profile"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to view.")
            return
        
        item = selection[0]
        player = self.parent.tree_maps['players_tree'].get(item)
        
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Show player profile dialog
        try:
            from ui_components import PlayerProfileWindow
            PlayerProfileWindow(self.parent, player)
        except ImportError:
            # Fallback - show basic info
            info = f"""
Player Profile
══════════════

Name: {player.full_name}
Position: {player.primary_position.value if hasattr(player.primary_position, 'value') else str(player.primary_position)}
Age: {player.age}
Team: {getattr(player, 'team_name', 'Free Agent')}
Overall: {player.overall_rating()}

Attributes:
Skating: {getattr(player, 'skating', 'N/A')}
Shooting: {getattr(player, 'shooting', 'N/A')}
Passing: {getattr(player, 'passing', 'N/A')}
Checking: {getattr(player, 'checking', 'N/A')}
            """
            messagebox.showinfo("Player Profile", info.strip())
    
    def _show_player_context_menu(self, event):
        """Show context menu for player"""
        # Select item under cursor
        item = self.players_tree.identify_row(event.y)
        if item:
            self.players_tree.selection_set(item)
            
            # Create context menu
            context_menu = tk.Menu(self, tearoff=0)
            context_menu.add_command(label="🔍 Scout Player", command=self._scout_player)
            context_menu.add_command(label="👤 View Profile", command=self._view_player_profile)
            context_menu.add_separator()
            context_menu.add_command(label="📋 Add to Watchlist", command=self._add_to_watchlist)
            
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
    
    def _add_to_watchlist(self):
        """Add player to watchlist"""
        messagebox.showinfo("Watchlist", "Add to watchlist functionality would be implemented here.")
    
    def _view_scout_details(self, event=None):
        """View scout details"""
        selection = self.scouts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scout to view details.")
            return
        
        item = selection[0]
        scout = self.parent.tree_maps['scouts_tree'].get(item)
        
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
        """Hire a new scout"""
        messagebox.showinfo("Hire Scout", "Scout hiring functionality would be implemented here.\n\n"
                          "This would open a dialog to:\n"
                          "• Browse available scout candidates\n"
                          "• View their skills and experience\n"
                          "• Negotiate contracts\n"
                          "• Add them to your scouting staff")
    
    def _edit_scout(self):
        """Edit scout details"""
        selection = self.scouts_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scout to edit.")
            return
        
        messagebox.showinfo("Edit Scout", "Scout editing functionality would be implemented here.")
    
    def _create_assignment(self):
        """Create new scouting assignment"""
        if not self.all_scouts:
            messagebox.showwarning("No Scouts", "You need scouts before you can create assignments.")
            return
        
        if not self.all_players:
            messagebox.showwarning("No Players", "No players available for scouting assignments.")
            return
        
        messagebox.showinfo("New Assignment", "Assignment creation dialog would be implemented here.\n\n"
                          "This would allow you to:\n"
                          "• Select a scout from your staff\n"
                          "• Choose a player to scout\n"
                          "• Set assignment priority\n"
                          "• Define scouting focus areas")
    
    def _cancel_assignment(self):
        """Cancel scouting assignment"""
        selection = self.assignments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assignment to cancel.")
            return
        
        result = messagebox.askyesno("Cancel Assignment", "Are you sure you want to cancel this assignment?")
        if result:
            messagebox.showinfo("Assignment Cancelled", "Scouting assignment has been cancelled.")
    
    def _on_report_select(self, event):
        """Handle report selection"""
        selection = self.reports_tree.selection()
        if not selection:
            self.report_text.delete('1.0', tk.END)
            return
        
        # Show sample report content
        self.report_text.delete('1.0', tk.END)
        sample_report = """SCOUTING REPORT
═══════════════

Player: Connor McDavid
Position: Center
Age: 27
Team: Edmonton Oilers

OVERALL ASSESSMENT: Elite (A+)

SKATING: Exceptional speed and acceleration. Elite edge work and balance. 
Can change direction without losing momentum. One of the fastest players 
in the league.

OFFENSIVE SKILLS: Elite puck handling in tight spaces. Excellent vision 
and passing ability. Accurate shot from multiple angles. Creates scoring 
chances for teammates consistently.

HOCKEY SENSE: Outstanding game reading ability. Anticipates play 
development exceptionally well. Makes smart decisions under pressure.

CHARACTER: Natural leader with strong work ethic. Handles pressure well. 
Team-first mentality with championship experience.

RECOMMENDATION: Immediate acquisition target if available. Franchise-
altering talent that would significantly improve our team's championship 
prospects.

Scout: Mike Johnson
Date: December 14, 2024
Confidence: High
"""
        self.report_text.insert('1.0', sample_report)
    
    def update_views(self):
        """Update all views (called when game data changes)"""
        self._load_game_data()
        self._populate_data()


# Integration function for main application  
def open_modern_scouting_window(parent):
    """Open the modern scouting management window"""
    if 'scouting' not in parent.open_windows or not parent.open_windows['scouting'].winfo_exists():
        parent.open_windows['scouting'] = ModernScoutingWindow(parent)
    parent.open_windows['scouting'].focus_set()