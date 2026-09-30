"""
Professional Scouting Management System
Clean, comprehensive scouting interface with dedicated draft analysis
Features: Player database, scout management, draft prospects, assignments, and reports
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from popup_system import messagebox, InGamePopup
from typing import (Dict, List, Any)
import datetime
import random
from game_classes import Player, PlayerPosition, Staff, StaffRole, to_100_scale
from game_classes import debug_print
from ui_widgets import PillButton
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


class ProfessionalScoutingView(ctk.CTkFrame):
    """Professional scouting management interface with comprehensive features"""
    
    def __init__(self, parent, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ProfessionalScoutingWindow wrapper
        self.configure(fg_color=self.app.BG_COLOR)
        
        # Data containers
        self.game_data = self._initialize_game_data()
        self.filter_vars = {}
        self.ui_components = {}
        
        # Initialize UI management
        self._ensure_tree_maps()
        
        # Build interface
        self._create_interface()
        self._load_initial_data()
        
        # Register window (if parent supports it)
        if hasattr(self.app, 'open_windows'):
            self.app.open_windows['scouting'] = self

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()
        
    def _initialize_game_data(self) -> Dict[str, Any]:
        """Initialize game data structure with proper error handling"""
        try:
            game_manager = getattr(self.app, 'game_manager', None)
            debug_print(f"DEBUG: game_manager exists: {game_manager is not None}")
            if not game_manager:
                debug_print("DEBUG: Using fallback data (no game_manager)")
                return self._generate_fallback_data()
            
            # Get core game objects
            user_team = getattr(game_manager, 'user_team', None)
            league = getattr(game_manager, 'league', None)
            debug_print(f"DEBUG: user_team exists: {user_team is not None}")
            debug_print(f"DEBUG: league exists: {league is not None}")
            
            # Collect all players
            all_players = self._collect_all_players(league, game_manager)
            debug_print(f"DEBUG: Collected {len(all_players)} players")
            
            # Real scouting staff only -- never fabricated. An empty staff
            # shows honest empty states ("hire scouts") downstream.
            scouts = self._get_scouting_staff(user_team)
            
            # Get current draft class
            draft_class = self._get_draft_prospects(game_manager)
            
            # No sample players: an empty league shows honest empty states.
            
            return {
                'players': all_players,
                'scouts': scouts,
                'user_team': user_team,
                'league': league,
                'draft_class': draft_class,
                'assignments': {},
                'reports': {}
            }
            
        except Exception as e:
            print(f"Error initializing scouting data: {e}")
            return self._empty_data_structure()
    
    def _empty_data_structure(self) -> Dict[str, Any]:
        """Return empty data structure as fallback"""
        return {
            'players': [],
            'scouts': [],
            'user_team': None,
            'league': None,
            'draft_class': [],
            'assignments': {},
            'reports': {}
        }
    
    def _generate_fallback_data(self) -> Dict[str, Any]:
        """Honest empty data when no game manager exists.

        The sample generators below are retained for reference only and are
        never called in the live path -- fabricated players/scouts must not
        appear as real data.
        """
        return self._empty_data_structure()
    
    def _generate_sample_players(self) -> List:
        """Generate sample players for testing/fallback"""
        from game_classes import Player, PlayerPosition
        import random
        
        sample_players = []
        names = [
            ("Connor", "McDavid"), ("Auston", "Matthews"), ("Nathan", "MacKinnon"),
            ("Sidney", "Crosby"), ("Leon", "Draisaitl"), ("David", "Pastrnak"),
            ("Erik", "Karlsson"), ("Victor", "Hedman"), ("Igor", "Shesterkin"),
            ("Frederik", "Andersen"), ("Brad", "Marchand"), ("Patrice", "Bergeron")
        ]
        
        positions = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING, 
                    PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.GOALIE]
        
        for i, (first, last) in enumerate(names):
            try:
                player = Player(
                    first_name=first,
                    last_name=last,
                    age=random.randint(20, 35),
                    primary_position=positions[i % len(positions)]
                )
                player.team_name = "Sample Team"
                sample_players.append(player)
            except:
                continue  # Skip if Player creation fails
        
        return sample_players
    
    def _generate_sample_scouts(self) -> List:
        """Generate sample scouts for testing/fallback"""
        from game_classes import Staff, StaffRole
        
        sample_scouts = []
        scout_names = [
            ("Mike", "Thompson"), ("Sarah", "Johnson"), ("Alex", "Rodriguez")
        ]
        
        for first, last in scout_names:
            try:
                scout = Staff(
                    first_name=first,
                    last_name=last,
                    age=random.randint(35, 60),
                    role=StaffRole.SCOUT
                )
                sample_scouts.append(scout)
            except:
                continue  # Skip if Staff creation fails
                
        return sample_scouts
    
    def _generate_basic_scouts(self, user_team) -> List:
        """Generate basic scouts for the user team"""
        if not user_team:
            return self._generate_sample_scouts()
            
        # Try to create scouts and add them to the team
        scouts = self._generate_sample_scouts()
        
        # Add scouts to team if it has staff attribute
        if hasattr(user_team, 'staff') and isinstance(user_team.staff, list):
            for scout in scouts:
                if scout not in user_team.staff:
                    user_team.staff.append(scout)
                    
        return scouts
    
    def _collect_all_players(self, league, game_manager) -> List[Player]:
        """Collect all players from league and free agents"""
        all_players = []
        
        # First try to get players from game manager's method
        if game_manager and hasattr(game_manager, 'get_all_players'):
            try:
                all_players = game_manager.get_all_players()
                debug_print(f"DEBUG: get_all_players() returned {len(all_players)} players")
                if all_players:  # If we got players this way, return them
                    return all_players
            except Exception as e:
                debug_print(f"DEBUG: get_all_players() failed: {e}")
                pass  # Fall back to manual collection
        
        # Fallback: collect manually from league
        if league and hasattr(league, 'teams'):
            for team in league.teams:
                # Get players from all roster types (use correct attribute names)
                if hasattr(team, 'roster') and team.roster:
                    all_players.extend(team.roster)
                if hasattr(team, 'ahl_roster') and team.ahl_roster:
                    all_players.extend(team.ahl_roster)
                if hasattr(team, 'prospects') and team.prospects:
                    all_players.extend(team.prospects)
        
        # Add free agents from league
        if league and hasattr(league, 'free_agents') and league.free_agents:
            all_players.extend(league.free_agents)
        
        # Also check game manager free agents
        if game_manager:
            free_agents = getattr(game_manager, 'free_agents', [])
            if free_agents:
                all_players.extend(free_agents)
        
        # Remove duplicates by player ID
        unique_players = []
        seen_ids = set()
        for player in all_players:
            player_id = getattr(player, 'id', id(player))
            if player_id not in seen_ids:
                seen_ids.add(player_id)
                unique_players.append(player)
        
        return unique_players
    
    def _get_scouting_staff(self, user_team) -> List[Staff]:
        """Get all scouting staff from user team"""
        scouts = []
        
        if user_team and hasattr(user_team, 'staff') and user_team.staff:
            for staff in user_team.staff:
                if self._is_scouting_staff(staff):
                    scouts.append(staff)
        
        # No fabrication: an empty staff list is honest and the UI
        # guides the user to hire scouts through the real staff market.
        
        return scouts
    
    def _is_scouting_staff(self, staff: Staff) -> bool:
        """Determine if staff member can perform scouting duties"""
        if not staff:
            return False
        
        # Check role
        role_str = str(getattr(staff, 'role', '')).lower()
        scouting_keywords = ['scout', 'evaluate', 'assess', 'analyst']
        if any(keyword in role_str for keyword in scouting_keywords):
            return True
        
        # Check for scouting attributes
        scouting_attrs = ['judging_player_ability', 'judging_player_potential', 'scouting_network']
        return any(hasattr(staff, attr) for attr in scouting_attrs)
    
    def _get_draft_prospects(self, game_manager) -> List[Player]:
        """Get current draft class prospects"""
        # Check for draft class in various possible locations
        draft_class = getattr(game_manager, 'current_draft_class', [])
        if not draft_class:
            draft_class = getattr(game_manager, 'draft_prospects', [])
        if not draft_class:
            draft_class = getattr(game_manager, 'upcoming_draft', [])
        
        return draft_class if draft_class else []
    
    def _ensure_tree_maps(self):
        """Ensure tree maps exist for UI management"""
        if not hasattr(self.app, 'tree_maps'):
            self.app.tree_maps = {}
        
        required_maps = ['players_tree', 'scouts_tree', 'draft_tree', 'assignments_tree', 'reports_tree']
        for map_name in required_maps:
            if map_name not in self.app.tree_maps:
                self.app.tree_maps[map_name] = {}
    
    def _create_interface(self):
        """Create the main scouting interface with professional styling"""
        # Header section
        self._create_header()
        
        # Main tabbed interface
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Create all tabs
        self._create_player_database_tab()
        self._create_scouting_staff_tab()
        self._create_draft_center_tab()  # New dedicated draft tab
        self._create_assignments_tab()
        self._create_reports_tab()
        
        # Professional status bar
        self._create_status_bar()
        
    def _create_header(self):
        """Create professional header section"""
        header_frame = tk.Frame(self, bg=self.app.TITLE_BAR_COLOR, height=75)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Main title and date
        title_frame = tk.Frame(header_frame, bg=self.app.TITLE_BAR_COLOR)
        title_frame.pack(expand=True)
        
        
        # Current date and context
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        team_name = self.game_data['user_team'].team_name if self.game_data.get('user_team') else "Organization"
        subtitle = f"{team_name} Scouting Operations • {current_date}"
        subtitle_label = tk.Label(title_frame, text=subtitle,
                                font=_sfont(self.app.FONT_FAMILY, 10),
                                bg=self.app.TITLE_BAR_COLOR, fg=self.app.TEXT_COLOR)
        subtitle_label.pack()
        
    def _create_status_bar(self):
        """Create comprehensive status bar"""
        status_frame = tk.Frame(self, bg=self.app.TITLE_BAR_COLOR, height=40)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        # Left side - system status
        self.status_label = tk.Label(status_frame, text="System Ready",
                                   bg=self.app.TITLE_BAR_COLOR, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 9))
        self.status_label.pack(side='left', padx=15, pady=10)
        
        # Right side - data summary
        self._update_data_counts()
        
    def _update_data_counts(self):
        """Update data counts in status bar"""
        player_count = len(self.game_data.get('players', []))
        scout_count = len(self.game_data.get('scouts', []))
        draft_count = len(self.game_data.get('draft_class', []))
        
        count_text = f"Players: {player_count:,} | Scouts: {scout_count} | Draft Prospects: {draft_count}"
        
        if hasattr(self, 'data_label'):
            self.data_label.config(text=count_text)
        else:
            status_frame = self.winfo_children()[-1]  # Get status frame
            self.data_label = tk.Label(status_frame, text=count_text,
                                     bg=self.app.TITLE_BAR_COLOR, fg=self.app.TEXT_COLOR,
                                     font=_sfont(self.app.FONT_FAMILY, 9))
            self.data_label.pack(side='right', padx=15, pady=10)
    
    def _create_player_database_tab(self):
        """Create comprehensive player database interface"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Player Database")
        
        # Advanced filters
        self._create_advanced_player_filters(tab_frame)
        
        # Player list with enhanced features
        self._create_enhanced_player_list(tab_frame)
        
    def _create_advanced_player_filters(self, parent):
        """Create comprehensive filtering system"""
        filter_frame = tk.LabelFrame(parent, text="Advanced Player Search & Analysis", \
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,\
                                   font=_sfont(self.app.FONT_FAMILY, 11, 'bold'), relief='groove')
        filter_frame.pack(fill='x', padx=15, pady=10)

        # Initialize filter variables with broadest settings to show all players
        self.filter_vars.update({
            'player_position': tk.StringVar(value="All Positions"),
            'player_team': tk.StringVar(value="All Teams"),
            'player_age_min': tk.StringVar(value="16"),
            'player_age_max': tk.StringVar(value="60"),
            'player_overall_min': tk.StringVar(value="1"),  # Start at 1 to show all players
            'player_search': tk.StringVar(value=""),  # Empty search
            'player_status': tk.StringVar(value="All Players")
        })

        # Top row: name search + team dropdown (dynamic, too many teams for pills) + clear
        top_row = tk.Frame(filter_frame, bg=self.app.CONTENT_BG)
        top_row.pack(fill='x', padx=12, pady=8)
        tk.Label(top_row, text="Search:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR, font=_sfont(self.app.FONT_FAMILY, 10)).pack(side='left')
        search_entry = tk.Entry(top_row, textvariable=self.filter_vars['player_search'],
                              width=22, font=_sfont(self.app.FONT_FAMILY, 10))
        search_entry.pack(side='left', padx=(5, 20))
        search_entry.bind('<KeyRelease>', lambda e: self._apply_player_filters())
        tk.Label(top_row, text="Team:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR, font=_sfont(self.app.FONT_FAMILY, 10)).pack(side='left')
        self.player_team_combo = ttk.Combobox(top_row, textvariable=self.filter_vars['player_team'],
                                           width=16, state="readonly")
        self.player_team_combo.pack(side='left', padx=(5, 0))
        self.player_team_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_player_filters())
        clear_btn = PillButton(top_row, text="Clear All", bg=self.app.CONTENT_BG,
                               font=_sfont(self.app.FONT_FAMILY, 9, 'bold'),
                               padx=12, pady=4, command=self._clear_player_filters)
        clear_btn.pack(side='right')

        # Pill filter rows (instant-apply; no Apply button needed)
        self._scout_pill_groups = []
        _AGE_RANGES = {'all': ('16', '60'), 'u18': ('16', '17'), '1822': ('18', '22'),
                       '2329': ('23', '29'), '30p': ('30', '60')}
        self._scout_age_ranges = _AGE_RANGES
        self._scout_pill_setters = {
            'position': lambda v: self.filter_vars['player_position'].set(v),
            'status': lambda v: self.filter_vars['player_status'].set(v),
            'age': lambda v: (self.filter_vars['player_age_min'].set(_AGE_RANGES[v][0]),
                              self.filter_vars['player_age_max'].set(_AGE_RANGES[v][1])),
            'overall': lambda v: self.filter_vars['player_overall_min'].set(v),
        }
        self._scout_pill_getters = {
            'position': lambda: self.filter_vars['player_position'].get(),
            'status': lambda: self.filter_vars['player_status'].get(),
            'age': lambda: next((k for k, r in _AGE_RANGES.items()
                                 if r == (self.filter_vars['player_age_min'].get(),
                                          self.filter_vars['player_age_max'].get())), 'all'),
            'overall': lambda: self.filter_vars['player_overall_min'].get(),
        }

        def _scout_pill_row(row_id, label, options):
            row = tk.Frame(filter_frame, bg=self.app.CONTENT_BG)
            row.pack(fill='x', padx=12, pady=2)
            tk.Label(row, text=label, bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                     font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                     width=10, anchor='w').pack(side='left')
            btns = {}
            for value, text in options:
                b = PillButton(row, text=text, bg=self.app.CONTENT_BG,
                               font=_sfont(self.app.FONT_FAMILY, 9, 'bold'),
                               padx=11, pady=4,
                               command=lambda v=value: self._scout_set_filter(row_id, v))
                b.pack(side='left', padx=2)
                btns[value] = b
            self._scout_pill_groups.append((row_id, btns))

        _scout_pill_row('position', "Position:",
                        [("All Positions", "All"), ("Forwards", "Forwards"),
                         ("Defensemen", "Defense"), ("Goalies", "Goalies")])
        _scout_pill_row('status', "Status:",
                        [("All Players", "All"), ("NHL Roster", "NHL"),
                         ("AHL Roster", "AHL"), ("Prospects", "Prospects"),
                         ("Free Agents", "Free Agents")])
        _scout_pill_row('age', "Age:",
                        [("all", "All"), ("u18", "U18"), ("1822", "18-22"),
                         ("2329", "23-29"), ("30p", "30+")])
        _scout_pill_row('overall', "Min OVR:",
                        [("1", "All"), ("70", "70+"), ("80", "80+"),
                         ("85", "85+"), ("90", "90+")])
        self._paint_scout_pills()

    def _scout_set_filter(self, row_id, value):
        """Set a scouting pill filter and refresh instantly."""
        self._scout_pill_setters[row_id](value)
        self._paint_scout_pills()
        self._apply_player_filters()

    def _paint_scout_pills(self):
        for row_id, btns in getattr(self, '_scout_pill_groups', []):
            try:
                current = self._scout_pill_getters[row_id]()
            except Exception:
                current = None
            for value, btn in btns.items():
                btn.set_selected(value == current)

    def _create_enhanced_player_list(self, parent):
        """Create enhanced player list with sorting and context menus"""
        list_frame = tk.LabelFrame(parent, text="Player Database & Scouting Targets", 
                                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                 font=_sfont(self.app.FONT_FAMILY, 11, 'bold'), relief='groove')
        list_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        
        # Enhanced player tree
        columns = ['Name', 'Pos', 'Age', 'Team', 'Overall', 'Potential', 'Status', 'Scout Priority', 'Last Scouted']
        self.players_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=16)
        
        # Column configuration with sorting
        col_config = {
            'Name': 180, 'Pos': 50, 'Age': 50, 'Team': 120, 
            'Overall': 70, 'Potential': 80, 'Status': 100, 
            'Scout Priority': 100, 'Last Scouted': 100
        }
        
        for col, width in col_config.items():
            self.players_tree.heading(col, text=col, command=lambda c=col: self._sort_players_by(c))
            self.players_tree.column(col, width=width, minwidth=40)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.players_tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient='horizontal', command=self.players_tree.xview)
        self.players_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Grid layout
        self.players_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Event bindings
        self.players_tree.bind('<Double-1>', self._on_player_double_click)
        self.players_tree.bind('<Button-3>', self._show_player_context_menu)
        self.players_tree.bind('<<TreeviewSelect>>', self._on_player_select)
        
        # Professional toolbar
        self._create_player_toolbar(list_frame)
        
    def _create_player_toolbar(self, parent):
        """Create professional player action toolbar"""
        toolbar_frame = tk.Frame(parent, bg=self.app.CONTENT_BG, height=50)
        toolbar_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        toolbar_frame.grid_propagate(False)
        
        # Primary actions
        scout_btn = tk.Button(toolbar_frame, text="Assign Scout", 
                            bg=self.app.ACCENT_COLOR, fg=self.app.HEADER_COLOR,
                            font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                            command=self._assign_scout_to_player)
        scout_btn.pack(side='left', padx=(10, 8))
        
        profile_btn = tk.Button(toolbar_frame, text="View Profile", 
                               bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                               font=_sfont(self.app.FONT_FAMILY, 10),
                               command=self._view_player_profile)
        profile_btn.pack(side='left', padx=(0, 8))
        
        shortlist_btn = tk.Button(toolbar_frame, text="Add to Shortlist", 
                                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                font=_sfont(self.app.FONT_FAMILY, 10),
                                command=self._add_to_shortlist)
        shortlist_btn.pack(side='left', padx=(0, 8))
        
        compare_btn = tk.Button(toolbar_frame, text="Compare Players", 
                               bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                               font=_sfont(self.app.FONT_FAMILY, 10),
                               command=self._compare_players)
        compare_btn.pack(side='left', padx=(0, 8))
        
        # Info label on right
        info_label = tk.Label(toolbar_frame, text="Double-click player for detailed analysis",
                            bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                            font=_sfont(self.app.FONT_FAMILY, 9, 'italic'))
        info_label.pack(side='right', padx=10)
    
    def _create_scouting_staff_tab(self):
        """Create scouting staff management interface"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Scouting Staff")
        
        # Staff overview
        self._create_staff_overview(tab_frame)
        
        # Staff list
        self._create_staff_list(tab_frame)
        
    def _create_draft_center_tab(self):
        """Create dedicated draft analysis center - THE NEW FEATURE"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Draft Center")
        
        # Draft year info
        self._create_draft_header(tab_frame)
        
        # Draft prospect filters
        self._create_draft_filters(tab_frame)
        
        # Draft prospect rankings
        self._create_draft_rankings(tab_frame)
        
    def _create_assignments_tab(self):
        """Create scouting assignments management"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Assignments")
        
        # Assignment management interface
        self._create_assignment_interface(tab_frame)
        
    def _create_reports_tab(self):
        """Create scouting reports interface"""
        tab_frame = tk.Frame(self.notebook, bg=self.app.CONTENT_BG)
        self.notebook.add(tab_frame, text="Reports")
        
        # Reports interface
        self._create_reports_interface(tab_frame)
    
    # Data loading and management methods
    def _load_initial_data(self):
        """Load initial data for all tabs"""
        try:
            self._populate_player_database()
            self._populate_scouting_staff()
            self._populate_draft_prospects()
            self._populate_assignments()
            self._populate_reports()
            self._update_data_counts()
            self._update_status("Data loaded successfully")
        except Exception as e:
            print(f"Error loading initial scouting data: {e}")
            self._update_status(f"Error loading data: {e}")
    
    def _populate_player_database(self):
        """Populate the player database tree"""
        debug_print(f"DEBUG: _populate_player_database called")
        
        # Clear existing
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)
        
        # Get players from game data
        players = self.game_data.get('players', [])
        debug_print(f"DEBUG: Found {len(players)} players in game_data")
        
        if not players:
            # Show message if no players found
            debug_print("DEBUG: No players found - showing 'No players found' message")
            self.players_tree.insert('', 'end', values=(
                'No players found', '', '', '', '', '', '', '', ''
            ))
            self._update_status("No players available - check game database")
            return
        
        # Get team names for filter
        teams = set()
        for player in players:
            team_name = getattr(player, 'team_name', 'Free Agent')
            teams.add(team_name)
        
        # Update team filter dropdown
        if hasattr(self, 'player_team_combo'):
            team_list = ["All Teams"] + sorted(list(teams))
            self.player_team_combo['values'] = team_list
        
        # Apply current filters and populate
        filtered_players = self._get_filtered_players()
        debug_print(f"DEBUG: After filtering: {len(filtered_players)} players remain")
        
        if not filtered_players:
            # Show message if no players pass filters
            debug_print("DEBUG: No players pass filters - showing 'No players match current filters' message")
            self.players_tree.insert('', 'end', values=(
                'No players match current filters', '', '', '', '', '', '', '', ''
            ))
            self._update_status("No players match current filters")
            return
        
        added_count = 0
        error_count = 0
        
        for player in filtered_players:
            try:
                # Safely get player attributes
                first_name = getattr(player, 'first_name', 'Unknown')
                last_name = getattr(player, 'last_name', 'Player')
                full_name = getattr(player, 'full_name', f"{first_name} {last_name}")
                
                if not full_name or full_name.strip() == " ":
                    full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    full_name = f"Player #{player.id}" if hasattr(player, 'id') else "Unknown Player"
                
                # Get position
                position = getattr(player, 'primary_position', 'F')
                position_str = self._format_position(position)
                
                # Get age
                age = getattr(player, 'age', 20)
                
                # Get team
                team_name = getattr(player, 'team_name', 'Free Agent')
                if not team_name:
                    team_name = 'Free Agent'
                
                # Get overall rating safely
                try:
                    if hasattr(player, 'overall_rating') and callable(player.overall_rating):
                        overall = player.overall_rating()
                        overall_str = f"{to_100_scale(overall):.0f}" if isinstance(overall, (int, float)) else str(overall)
                    else:
                        overall_str = 'N/A'
                except:
                    overall_str = 'N/A'
                
                # Get potential
                potential = getattr(player, 'potential', 'Unknown')
                potential_str = f"{potential:.0f}" if isinstance(potential, (int, float)) else str(potential)
                
                # Get scouting information
                status = self._get_player_status(player)
                scout_priority = self._get_scout_priority(player)
                last_scouted = self._get_last_scouted(player)
                
                # Insert into tree
                item = self.players_tree.insert('', 'end', values=(
                    full_name,
                    position_str,
                    age,
                    team_name,
                    overall_str,
                    potential_str,
                    status,
                    scout_priority,
                    last_scouted
                ))
                
                # Store player reference for tree mapping
                if 'players_tree' not in self.app.tree_maps:
                    self.app.tree_maps['players_tree'] = {}
                self.app.tree_maps['players_tree'][item] = player
                
                added_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        # Update status with results
        status_msg = f"Loaded {added_count:,} players"
        if error_count > 0:
            status_msg += f" ({error_count} errors)"
        self._update_status(status_msg)
    
    # Utility and helper methods
    def _format_position(self, position):
        """Format position for display"""
        if hasattr(position, 'value'):
            return position.value
        return str(position)
    
    def _get_player_status(self, player):
        """Determine player's current status"""
        team_name = getattr(player, 'team_name', '')
        if not team_name or team_name == 'Free Agent':
            return 'Free Agent'
        
        # Try to determine roster level
        if hasattr(player, 'roster_status'):
            return player.roster_status
        
        # Determine status based on age, overall rating, and team
        overall = getattr(player, 'overall_rating', lambda: 50)()
        age = getattr(player, 'age', 25)
        
        if age < 20:
            return 'Prospect'
        elif age > 35:
            return 'Veteran'
        elif overall > 46:
            return 'NHL Star'
        elif overall > 40:
            return 'NHL Regular'
        elif overall > 35:
            return 'AHL/Fringe'
        else:
            return 'Minor League'
    
    def _get_scout_priority(self, player):
        """Get scouting priority for player based on attributes"""
        try:
            overall = getattr(player, 'overall_rating', lambda: 50)()
            age = getattr(player, 'age', 25)
            
            # High priority for young high-potential players
            if age < 22 and overall > 42:
                return 'High'
            elif age < 25 and overall > 40:
                return 'High'
            elif overall > 46:
                return 'High'
            elif age < 20 or overall > 35:
                return 'Medium'
            else:
                return 'Low'
        except:
            return 'Medium'
    
    def _get_last_scouted(self, player):
        """Get last scouted date for player"""
        import random
        import datetime
        
        # Generate realistic scouting dates for some players
        if random.random() < 0.3:  # 30% have been scouted
            days_ago = random.randint(1, 90)
            scout_date = datetime.date.today() - datetime.timedelta(days=days_ago)
            return scout_date.strftime("%Y-%m-%d")
        else:
            return 'Never'
    
    def _get_filtered_players(self):
        """Apply current filters to player list"""
        players = self.game_data.get('players', [])
        
        if not players:
            return []
        
        filtered_players = players.copy()
        
        # Apply position filter
        try:
            position_filter = self.filter_vars.get('player_position', tk.StringVar()).get()
            if position_filter and position_filter not in ["All Positions", ""]:
                if position_filter == "Forwards":
                    filtered_players = [p for p in filtered_players 
                                     if self._format_position(getattr(p, 'primary_position', '')).upper() in ['C', 'LW', 'RW']]
                elif position_filter == "Defensemen":
                    filtered_players = [p for p in filtered_players 
                                     if self._format_position(getattr(p, 'primary_position', '')).upper() in ['LD', 'RD', 'D']]
                elif position_filter == "Goalies":
                    filtered_players = [p for p in filtered_players 
                                     if self._format_position(getattr(p, 'primary_position', '')).upper() == 'G']
                elif position_filter == "Centers":
                    filtered_players = [p for p in filtered_players 
                                     if self._format_position(getattr(p, 'primary_position', '')).upper() == 'C']
                elif position_filter == "Wingers":
                    filtered_players = [p for p in filtered_players 
                                     if self._format_position(getattr(p, 'primary_position', '')).upper() in ['LW', 'RW']]
                else:
                    filtered_players = [p for p in filtered_players 
                                     if self._format_position(getattr(p, 'primary_position', '')).upper() == position_filter.upper()]
        except:
            pass
        
        # Apply team filter
        try:
            team_filter = self.filter_vars.get('player_team', tk.StringVar()).get()
            if team_filter and team_filter not in ["All Teams", ""]:
                filtered_players = [p for p in filtered_players 
                                  if getattr(p, 'team_name', 'Free Agent') == team_filter]
        except:
            pass

        # Apply status filter (was read but never applied)
        try:
            status_filter = self.filter_vars.get('player_status', tk.StringVar()).get()
            if status_filter and status_filter not in ["All Players", ""]:
                status_map = {
                    "NHL Roster": {'NHL Star', 'NHL Regular'},
                    "AHL Roster": {'AHL/Fringe', 'Minor League'},
                    "Prospects": {'Prospect'},
                    "Free Agents": {'Free Agent'},
                }
                allowed = status_map.get(status_filter, set())
                filtered_players = [p for p in filtered_players
                                    if self._get_player_status(p) in allowed]
        except:
            pass
        
        # Apply age range
        try:
            min_age = int(self.filter_vars.get('player_age_min', tk.StringVar(value="16")).get())
            max_age = int(self.filter_vars.get('player_age_max', tk.StringVar(value="45")).get())
            filtered_players = [p for p in filtered_players 
                              if min_age <= getattr(p, 'age', 20) <= max_age]
        except (ValueError, TypeError):
            pass
        
        # Apply overall minimum
        try:
            min_overall = int(self.filter_vars.get('player_overall_min', tk.StringVar(value="1")).get())
            # Only filter if minimum overall is above 1 (to show all players by default)
            if min_overall > 1:
                filtered_players = [p for p in filtered_players 
                                  if to_100_scale(self._get_safe_overall_rating(p)) >= min_overall]
        except (ValueError, TypeError):
            pass
        
        # Apply name search
        try:
            search_term = self.filter_vars.get('player_search', tk.StringVar()).get()
            if search_term and search_term.strip():
                search_term = search_term.lower().strip()
                filtered_players = [p for p in filtered_players 
                                  if search_term in self._get_safe_full_name(p).lower()]
        except:
            pass
        
        return filtered_players
    
    def _get_safe_overall_rating(self, player):
        """Safely get overall rating from player"""
        try:
            if hasattr(player, 'overall_rating') and callable(player.overall_rating):
                rating = player.overall_rating()
                return rating if isinstance(rating, (int, float)) else 50
            return 50
        except:
            return 50
    
    def _get_safe_full_name(self, player):
        """Safely get full name from player"""
        try:
            full_name = getattr(player, 'full_name', None)
            if full_name:
                return full_name
            
            first_name = getattr(player, 'first_name', 'Unknown')
            last_name = getattr(player, 'last_name', 'Player')
            return f"{first_name} {last_name}"
        except:
            return "Unknown Player"
    
    def _update_status(self, message):
        """Update status bar message"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
    
    # Event handlers and action methods
    def _apply_player_filters(self):
        """Apply current player filters"""
        self._populate_player_database()
    
    def _clear_player_filters(self):
        """Clear all player filters to broadest settings"""
        for var_name, var in self.filter_vars.items():
            if 'player_' in var_name:
                if 'position' in var_name:
                    var.set("All Positions")
                elif 'team' in var_name:
                    var.set("All Teams")
                elif 'status' in var_name:
                    var.set("All Players")
                elif 'age_min' in var_name:
                    var.set("16")
                elif 'age_max' in var_name:
                    var.set("60")  # Broad age range
                elif 'overall_min' in var_name:
                    var.set("1")   # Show all players regardless of rating
                elif 'search' in var_name:
                    var.set("")
        self._paint_scout_pills()
        self._populate_player_database()
    
    def _sort_players_by(self, column):
        """Sort players by specified column"""
        # Get current data from tree
        items = []
        for item_id in self.players_tree.get_children():
            item = self.players_tree.item(item_id)
            items.append((item_id, item['values']))
        
        # Determine sort key based on column
        if column == 'Name':
            sort_key = lambda x: str(x[1][0]).lower()
        elif column == 'Age':
            sort_key = lambda x: int(x[1][2]) if str(x[1][2]).isdigit() else 0
        elif column == 'Overall':
            sort_key = lambda x: int(x[1][4]) if str(x[1][4]).isdigit() else 0
        elif column == 'Potential':
            sort_key = lambda x: int(x[1][5]) if str(x[1][5]).isdigit() else 0
        elif column == 'Team':
            sort_key = lambda x: str(x[1][3]).lower()
        elif column == 'Pos':
            sort_key = lambda x: str(x[1][1]).lower()
        elif column == 'Scout Priority':
            priority_order = {'High': 3, 'Medium': 2, 'Low': 1}
            sort_key = lambda x: priority_order.get(str(x[1][7]), 0)
        elif column == 'Last Scouted':
            sort_key = lambda x: str(x[1][8]) if x[1][8] != 'Never' else '0000-00-00'
        else:
            sort_key = lambda x: str(x[1][0]).lower()
        
        # Toggle sort order if same column clicked twice
        if not hasattr(self, '_last_sort_column') or self._last_sort_column != column:
            self._sort_reverse = False
        else:
            self._sort_reverse = not getattr(self, '_sort_reverse', False)
        
        self._last_sort_column = column
        
        # Sort items
        try:
            items.sort(key=sort_key, reverse=self._sort_reverse)
        except Exception as e:
            print(f"Error sorting by {column}: {e}")
            return
        
        # Clear and repopulate tree
        self.players_tree.delete(*self.players_tree.get_children())
        
        for old_item_id, values in items:
            new_item_id = self.players_tree.insert('', 'end', values=values)
            # Preserve player reference mapping
            if old_item_id in self.app.tree_maps['players_tree']:
                self.app.tree_maps['players_tree'][new_item_id] = self.app.tree_maps['players_tree'][old_item_id]
                del self.app.tree_maps['players_tree'][old_item_id]
        
        # Update status
        sort_direction = "↓" if self._sort_reverse else "↑"
        self._update_status(f"Sorted by {column} {sort_direction}")
    
    def _on_player_double_click(self, event):
        """Handle player double-click"""
        self._view_player_profile()
    
    def _on_player_select(self, event):
        """Handle player selection"""
        selection = self.players_tree.selection()
        if selection:
            self._update_status(f"Selected: {len(selection)} player(s)")
    
    def _show_player_context_menu(self, event):
        """Show full player context menu (universal + scouting actions)."""
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
                ("Assign Scout", self._assign_scout_to_player),
                ("Add to Shortlist", self._add_to_shortlist),
                ("Compare", self._compare_players),
                ("Advanced Analysis", self._advanced_analysis),
            ])
    
    def _assign_scout_to_player(self):
        """Assign a scout to evaluate selected player"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to scout.")
            return
        
        scouts = self.game_data.get('scouts', [])
        if not scouts:
            messagebox.showwarning("No Scouts", "You need scouts before you can assign scouting tasks.\n\nHire scouts in the Scouting Staff tab.")
            return
        
        player = self.app.tree_maps['players_tree'].get(selection[0])
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Show scout assignment dialog
        self._show_scout_assignment_dialog(player, scouts)
    
    def _show_scout_assignment_dialog(self, player, scouts):
        """Show dialog for assigning scout to player.

        Non-modal (Eastside grammar -- no grab_set; dismissing defers).
        Creates a REAL assignment in app.scouting_assignments and shows the
        real estimated completion derived from live state.
        """
        dialog = InGamePopup(self)
        dialog.title(f"Assign Scout - {player.full_name}")
        dialog.geometry("400x380")
        dialog.configure(bg=self.app.CONTENT_BG)
        dialog.resizable(False, False)

        # Dialog content
        tk.Label(dialog, text=f"Assign Scout to Evaluate {player.full_name}",
                font=_sfont(self.app.FONT_FAMILY, 12, 'bold'),
                bg=self.app.CONTENT_BG, fg=self.app.HEADER_COLOR).pack(pady=15)

        # Scout selection
        tk.Label(dialog, text="Available Scouts:",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR).pack(pady=(10, 5))

        scout_var = tk.StringVar()
        scout_listbox = tk.Listbox(dialog, height=6)
        scout_listbox.pack(pady=5, padx=20, fill='x')

        for i, scout in enumerate(scouts):
            scout_name = scout.full_name
            scout_ability = getattr(scout, 'judging_player_ability', 'Unknown')
            scout_listbox.insert(tk.END, f"{scout_name} (Ability: {scout_ability})")

        # Real estimated completion, derived from live state
        pace_label = tk.Label(dialog, text="",
                              bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                              font=_sfont(self.app.FONT_FAMILY, 9),
                              wraplength=340, justify='left')
        pace_label.pack(pady=(5, 5), padx=20)

        def _refresh_pace(*_args):
            try:
                from scouting_window_helpers import estimate_completion_days
                sel = scout_listbox.curselection()
                if not sel:
                    pace_label.config(text="Select a scout to see the estimated completion.")
                    return
                days = estimate_completion_days(self.app, player, scouts[sel[0]])
                if days == 0:
                    pace_label.config(text="This player already has a complete report.")
                elif days is None:
                    pace_label.config(text="Estimated completion: unknown.")
                else:
                    pace_label.config(
                        text=f"Estimated completion: ~{days} days at this scout's pace "
                             "(report reaches 'A' accuracy, then the assignment closes).")
            except Exception:
                pace_label.config(text="")

        scout_listbox.bind('<<ListboxSelect>>', _refresh_pace)
        _refresh_pace()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.app.CONTENT_BG)
        btn_frame.pack(pady=20)

        def assign_scout():
            selection = scout_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Scout", "Please select a scout.")
                return

            scout = scouts[selection[0]]

            try:
                from scouting_window_helpers import create_scout_assignment
            except Exception as e:
                messagebox.showerror("Scouting", f"Scouting helpers unavailable: {e}")
                return

            ok, msg = create_scout_assignment(self.app, player, scout)
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Assignment Created" if ok else "Scouting", msg)
            if ok:
                self._populate_assignments()
                dialog.destroy()

        tk.Button(btn_frame, text="Assign Scout", command=assign_scout,
                 bg=self.app.ACCENT_COLOR, fg=self.app.HEADER_COLOR,
                 font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(side='left', padx=(0, 10))

        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR).pack(side='left')
    
    def _view_player_profile(self):
        """View detailed player profile"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to view.")
            return
        
        player = self.app.tree_maps['players_tree'].get(selection[0])
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
            # Fallback to basic info dialog
            self._show_basic_player_info(player)
    
    def _show_basic_player_info(self, player):
        """Show basic player information dialog"""
        info = f"""
PLAYER PROFILE
═══════════════════

Personal Information:
Name: {player.full_name}
Position: {self._format_position(player.primary_position)}
Age: {player.age}
Team: {getattr(player, 'team_name', 'Free Agent')}

Performance Ratings:
Overall: {to_100_scale(player.overall_rating())}
Potential: {getattr(player, 'potential', 'Unknown')}

Key Attributes:
Skating: {getattr(player, 'skating', 'N/A')}
Shooting: {getattr(player, 'shooting', 'N/A')}
Passing: {getattr(player, 'passing', 'N/A')}
Hockey IQ: {getattr(player, 'hockey_iq', 'N/A')}
Physical: {getattr(player, 'checking', 'N/A')}

Scouting Notes:
Status: {self._get_player_status(player)}
Priority: {self._get_scout_priority(player)}
Last Scouted: {self._get_last_scouted(player)}
        """
        
        messagebox.showinfo("Player Profile", info.strip())
    
    def _add_to_shortlist(self):
        """Add the selected player to the REAL ShortlistManager."""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to add to the shortlist.")
            return

        player = self.app.tree_maps['players_tree'].get(selection[0])
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return

        try:
            from scouting_window_helpers import open_shortlist_dialog
        except Exception as e:
            messagebox.showerror("Shortlist", f"Shortlist helpers unavailable: {e}")
            return
        open_shortlist_dialog(self, self.app, player)
    
    def _compare_players(self):
        """Compare players with the REAL comparison tool.

        Routes to PlayerContextMenu's enhanced comparison window (the same
        tool the "Compare with Another Player" context action opens): pick
        a player here and choose the comparison target inside the tool.
        Reused, not rebuilt.
        """
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to compare.")
            return

        player = self.app.tree_maps['players_tree'].get(selection[0])
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return

        try:
            from player_context_menu import PlayerContextMenu
            PlayerContextMenu(self.app)._compare_players(player)
        except Exception as e:
            messagebox.showerror("Compare", f"Could not open the comparison tool:\n{e}")
    
    def _advanced_analysis(self):
        """Show advanced analysis built from REAL live state.

        Analytics stays a puzzle: everything shown is scout-filtered --
        the filed report's graded potential range, its accuracy-graded
        attribute bands, strengths/weaknesses the scout actually listed,
        comparables and projection. With no report, only the public
        consensus range is shown. Never raw attributes.
        """
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player for analysis.")
            return

        player = self.app.tree_maps['players_tree'].get(selection[0])
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return

        try:
            from scouting_window_helpers import reports_of, report_display_lines
            from scouting import consensus_range
        except Exception as e:
            messagebox.showerror("Analysis", f"Analysis helpers unavailable: {e}")
            return

        report = reports_of(self.app).get(getattr(player, "id", None))

        win = InGamePopup(self)
        win.title(f"Advanced Analysis — {getattr(player, 'full_name', '?')}")
        win.geometry("560x560")
        win.configure(bg=self.app.CONTENT_BG)
        # Eastside grammar: non-modal. No grab_set; closing defers.

        try:
            pos = player.primary_position.value
        except Exception:
            pos = str(getattr(player, "primary_position", "?"))
        tk.Label(win, text=f"{getattr(player, 'full_name', '?')}  ·  {pos}  ·  Age {getattr(player, 'age', '?')}",
                 font=_sfont(self.app.FONT_FAMILY, 12, 'bold'),
                 bg=self.app.CONTENT_BG, fg=self.app.HEADER_COLOR,
                 wraplength=520, justify='left').pack(anchor='w', padx=16, pady=(14, 6))

        body = tk.Text(win, wrap='word', height=24,
                       bg=self.app.BG_COLOR, fg=self.app.TEXT_COLOR,
                       font=_sfont(self.app.FONT_FAMILY, 10))
        body.pack(fill='both', expand=True, padx=16, pady=6)

        def _hdr(text):
            body.insert('end', f"{text}\n", "hdr")

        body.tag_config("hdr", font=_sfont(self.app.FONT_FAMILY, 10, 'bold'))

        if report is not None:
            rows, pot = report_display_lines(player, report)
            _hdr("SCOUT-FILTERED BREAKDOWN")
            body.insert('end', f"Graded potential: {pot}\n")
            body.insert('end', f"Report accuracy: {getattr(report, 'accuracy', '?')} "
                               f"({getattr(report, 'viewings', 0)} viewings)\n")
            body.insert('end', f"Reliability: {getattr(report, 'reliability', 0.0):.0%}\n\n")

            # Accuracy-graded attribute bands the scout actually filed
            scouted = getattr(report, "scouted_attributes", None) or {}
            if scouted:
                _hdr("ATTRIBUTE BANDS (as graded by the scout)")
                for attr in sorted(scouted):
                    label = attr.replace("_", " ").title()
                    body.insert('end', f"• {label}: {scouted[attr]}\n")
                body.insert('end', "\n")

            for label, text in rows:
                if label in ("Accuracy", "Viewings"):
                    continue  # already shown above
                _hdr(label.upper())
                body.insert('end', f"{text}\n\n")

            body.insert('end',
                        "These are the scout's graded reads, not measurements. "
                        "Higher accuracy narrows the bands.")
        else:
            crange = consensus_range(player)
            _hdr("PUBLIC CONSENSUS (UN SCOUTED)")
            body.insert('end', f"Potential range: {crange}\n\n")
            body.insert('end',
                        "No filed report exists for this player, so there is no "
                        "advanced breakdown to show -- anything more would be guessing.\n\n"
                        "Assign a scout to build a real evaluation; the breakdown "
                        "above fills in as viewings accumulate and accuracy rises.")

        body.configure(state='disabled')
        tk.Button(win, text="Close", command=win.destroy,
                  bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR).pack(pady=(0, 14))
    
    # Placeholder methods for other tabs - to be implemented
    def _create_staff_overview(self, parent):
        """Create staff overview section with REAL live numbers."""
        overview_frame = tk.LabelFrame(parent, text="Scouting Department Overview",
                                     bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                     font=_sfont(self.app.FONT_FAMILY, 11, 'bold'))
        overview_frame.pack(fill='x', padx=15, pady=10)

        try:
            from scouting_window_helpers import (
                assignments_of, reports_of, scouts_of, user_team_of)
            scouts = scouts_of(self.app)
            assigns = assignments_of(self.app)
            reports = reports_of(self.app)
            completed = sum(1 for r in reports.values()
                            if getattr(r, 'accuracy', '') == 'A')
            team = user_team_of(self.app)
            try:
                budget_left = team.staff_budget_remaining()
                budget_text = f"${budget_left:,}"
            except Exception:
                budget_text = "—"
            info_text = (
                f"Staff Count: {len(scouts)}\n"
                f"Active Assignments: {len(assigns)}\n"
                f"Completed Reports: {completed}\n"
                f"Staff Budget Remaining: {budget_text}"
            )
        except Exception:
            info_text = (
                f"Staff Count: {len(self.game_data.get('scouts', []))}\n"
                "Active Assignments: —\n"
                "Completed Reports: —\n"
                "Staff Budget Remaining: —"
            )

        tk.Label(overview_frame, text=info_text.strip(),
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10), justify='left').pack(pady=10)

        # Refresh the numbers whenever the tab is re-shown
        def _refresh(_e=None):
            try:
                from scouting_window_helpers import (
                    assignments_of as _a, reports_of as _r,
                    scouts_of as _s, user_team_of as _u)
                _scouts = _s(self.app)
                _assigns = _a(self.app)
                _reports = _r(self.app)
                _completed = sum(1 for r in _reports.values()
                                 if getattr(r, 'accuracy', '') == 'A')
                _team = _u(self.app)
                try:
                    _budget = f"${_team.staff_budget_remaining():,}"
                except Exception:
                    _budget = "—"
                for w in overview_frame.winfo_children():
                    if isinstance(w, tk.Label):
                        w.config(text=(
                            f"Staff Count: {len(_scouts)}\n"
                            f"Active Assignments: {len(_assigns)}\n"
                            f"Completed Reports: {_completed}\n"
                            f"Staff Budget Remaining: {_budget}"))
            except Exception:
                pass
        parent.bind('<Visibility>', _refresh, add='+')
    
    def _create_staff_list(self, parent):
        """Create scouting staff list"""
        list_frame = tk.LabelFrame(parent, text="Scouting Staff",
                                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                 font=_sfont(self.app.FONT_FAMILY, 11, 'bold'))
        list_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        
        # Create treeview for scouts
        staff_cols = ('Name', 'Age', 'Ability', 'Status')
        self.staff_tree = ttk.Treeview(list_frame, columns=staff_cols, show='headings', height=12)
        
        for col in staff_cols:
            self.staff_tree.heading(col, text=col)
            self.staff_tree.column(col, width=120, minwidth=100)
        
        self.staff_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add scrollbar
        staff_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.staff_tree.yview)
        self.staff_tree.configure(yscrollcommand=staff_scrollbar.set)
        staff_scrollbar.pack(side='right', fill='y')
    
    def _create_draft_header(self, parent):
        """Create draft year header information"""
        header_frame = tk.LabelFrame(parent, text="Draft Information",
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 11, 'bold'))
        header_frame.pack(fill='x', padx=15, pady=10)
        
        current_year = datetime.datetime.now().year
        draft_prospects = len(self.game_data.get('draft_class', []))
        
        info_text = f"""
Draft Year: {current_year}
Available Prospects: {draft_prospects}
Your Draft Position: TBD
Months Until Draft: 6
        """
        
        tk.Label(header_frame, text=info_text.strip(),
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10), justify='left').pack(pady=10)
    
    def _create_draft_filters(self, parent):
        """Create draft prospect filters wired to the real draft class.

        Position group, scouting status, and name search filter the real
        prospects below. All display values are fog-of-war safe (graded
        potential ranges, never raw attributes).
        """
        filter_frame = tk.LabelFrame(parent, text="Draft Prospect Filters",
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 11, 'bold'))
        filter_frame.pack(fill='x', padx=15, pady=(0, 10))

        row = tk.Frame(filter_frame, bg=self.app.CONTENT_BG)
        row.pack(fill='x', padx=10, pady=10)

        tk.Label(row, text="Position:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR).pack(side='left')
        self.draft_pos_filter = tk.StringVar(value="All")
        pos_combo = ttk.Combobox(row, textvariable=self.draft_pos_filter,
                                 values=["All", "Forwards", "Defensemen", "Goalies"],
                                 state='readonly', width=12)
        pos_combo.pack(side='left', padx=(5, 15))
        pos_combo.bind('<<ComboboxSelected>>',
                       lambda _e: self._populate_draft_prospects())

        tk.Label(row, text="Scouting:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR).pack(side='left')
        self.draft_scout_filter = tk.StringVar(value="All")
        scout_combo = ttk.Combobox(row, textvariable=self.draft_scout_filter,
                                   values=["All", "Scouted", "In Progress", "Not Scouted"],
                                   state='readonly', width=12)
        scout_combo.pack(side='left', padx=(5, 15))
        scout_combo.bind('<<ComboboxSelected>>',
                         lambda _e: self._populate_draft_prospects())

        tk.Label(row, text="Search:", bg=self.app.CONTENT_BG,
                fg=self.app.TEXT_COLOR).pack(side='left')
        self.draft_search = tk.StringVar()
        search_entry = tk.Entry(row, textvariable=self.draft_search, width=20)
        search_entry.pack(side='left', padx=(5, 15))
        search_entry.bind('<KeyRelease>',
                          lambda _e: self._populate_draft_prospects())

        tk.Button(row, text="Clear", command=self._clear_draft_filters,
                 bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR).pack(side='left')

    def _clear_draft_filters(self):
        """Reset draft prospect filters to show everything."""
        try:
            self.draft_pos_filter.set("All")
            self.draft_scout_filter.set("All")
            self.draft_search.set("")
        except Exception:
            pass
        self._populate_draft_prospects()

    def _filtered_draft_prospects(self):
        """Real draft class with the current filters applied.

        Source order: league.draft_prospects (the engine's draft class),
        then the game_data draft_class fallback. Sorted by draft_ranking.
        """
        try:
            from scouting_window_helpers import league_of, assignments_of
        except Exception:
            league_of = assignments_of = None
        prospects = []
        try:
            lg = league_of(self.app) if league_of else None
            prospects = list(getattr(lg, 'draft_prospects', None) or [])
        except Exception:
            prospects = []
        if not prospects:
            prospects = list(self.game_data.get('draft_class', []) or [])
        # Dedupe by id, keep ranking order
        seen, uniq = set(), []
        for p in prospects:
            pid = getattr(p, 'id', None)
            if pid not in seen:
                seen.add(pid)
                uniq.append(p)
        uniq.sort(key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)
        prospects = uniq

        # Position group filter
        pos = getattr(self, 'draft_pos_filter', None)
        pos_val = pos.get() if pos else "All"
        if pos_val != "All":
            try:
                from game_classes import PlayerPosition
                groups = {
                    "Forwards": (PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                                 PlayerPosition.RIGHT_WING, PlayerPosition.FORWARD),
                    "Defensemen": (PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
                                   PlayerPosition.DEFENSE),
                    "Goalies": (PlayerPosition.GOALIE,),
                }
                wanted = groups.get(pos_val, ())
                prospects = [p for p in prospects
                             if getattr(p, 'primary_position', None) in wanted]
            except Exception:
                pass

        # Scouting status filter (real reports + real assignments)
        scout_val = self.draft_scout_filter.get() if hasattr(self, 'draft_scout_filter') else "All"
        if scout_val != "All":
            try:
                from scouting_window_helpers import reports_of, user_team_of
                reports = reports_of(self.app)
                assigns = assignments_of(self.app) if assignments_of else {}
            except Exception:
                reports, assigns = {}, {}
            def _status(p):
                pid = getattr(p, 'id', None)
                if pid in reports:
                    return "Scouted"
                if p in assigns:
                    return "In Progress"
                return "Not Scouted"
            prospects = [p for p in prospects if _status(p) == scout_val]

        # Name search
        q = self.draft_search.get().lower().strip() if hasattr(self, 'draft_search') else ""
        if q:
            prospects = [p for p in prospects
                         if q in str(getattr(p, 'full_name', '') or '').lower()]
        return prospects
    
    def _create_draft_rankings(self, parent):
        """Create draft prospect rankings"""
        rankings_frame = tk.LabelFrame(parent, text="Draft Prospect Rankings",
                                     bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                     font=_sfont(self.app.FONT_FAMILY, 11, 'bold'))
        rankings_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        
        # Create treeview for draft prospects
        draft_cols = ('Rank', 'Name', 'Position', 'Age', 'Potential', 'Status')
        self.draft_tree = ttk.Treeview(rankings_frame, columns=draft_cols, show='headings', height=15)

        # Configure columns
        for col in draft_cols:
            self.draft_tree.heading(col, text=col)

        # Set column widths
        col_widths = {'Rank': 50, 'Name': 150, 'Position': 80, 'Age': 50, 'Potential': 100, 'Status': 110}
        for col, width in col_widths.items():
            self.draft_tree.column(col, width=width, minwidth=40)
        
        self.draft_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add scrollbar
        draft_scrollbar = ttk.Scrollbar(rankings_frame, orient='vertical', command=self.draft_tree.yview)
        self.draft_tree.configure(yscrollcommand=draft_scrollbar.set)
        draft_scrollbar.pack(side='right', fill='y')
        
        # Bind double-click event for detailed prospect view
        self.draft_tree.bind('<Double-1>', self._on_prospect_double_click)
        
    def _on_prospect_double_click(self, event):
        """Handle double-click on draft prospect: open the REAL report.

        Routes through the draft war-room report machinery (the same
        fog-of-war rendering ScoutingView uses): the filed ScoutingReport
        if one exists, otherwise the public consensus range with honest
        guidance to assign a scout.
        """
        selection = self.draft_tree.selection()
        if not selection:
            return
        player = self.app.tree_maps.get('draft_tree', {}).get(selection[0])
        if player is None:
            # Fallback: resolve by name from the real draft class
            try:
                name = self.draft_tree.item(selection[0])['values'][1]
                for p in self._filtered_draft_prospects():
                    if getattr(p, 'full_name', '') == name:
                        player = p
                        break
            except Exception:
                player = None
        if player is None:
            messagebox.showwarning("Prospect", "Could not find that prospect.")
            return
        try:
            from scouting_window_helpers import show_prospect_report
            show_prospect_report(self, self.app, player)
        except Exception as e:
            messagebox.showerror("Report", f"Could not open the prospect report:\n{e}")
    
    def _create_assignment_interface(self, parent):
        """Create assignment management interface"""
        main_frame = tk.Frame(parent, bg=self.app.CONTENT_BG)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header
        header_frame = tk.Frame(main_frame, bg=self.app.CONTENT_BG)
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_label = tk.Label(header_frame, text="Scouting Assignments",
                              font=_sfont(self.app.FONT_FAMILY, 16, 'bold'),
                              bg=self.app.CONTENT_BG, fg=self.app.HEADER_COLOR)
        title_label.pack(side='left')
        
        # Action buttons
        btn_frame = tk.Frame(header_frame, bg=self.app.CONTENT_BG)
        btn_frame.pack(side='right')
        
        new_assignment_btn = tk.Button(btn_frame, text="+ New Assignment",
                                      bg=self.app.ACCENT_COLOR, fg='white',
                                      font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                      command=self._create_new_assignment)
        new_assignment_btn.pack(side='left', padx=(0, 10))
        
        # Content area with two columns
        content_frame = tk.Frame(main_frame, bg=self.app.CONTENT_BG)
        content_frame.pack(fill='both', expand=True)
        
        # Left: Current assignments
        left_frame = tk.LabelFrame(content_frame, text="Current Assignments",
                                  bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                  font=_sfont(self.app.FONT_FAMILY, 12, 'bold'))
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Assignment list
        assign_cols = ('Scout', 'Target', 'Type', 'Priority', 'Due Date', 'Status')
        self.assignments_tree = ttk.Treeview(left_frame, columns=assign_cols, show='headings', height=15)

        for col in assign_cols:
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=100, minwidth=80)

        # Right-click a live assignment to cancel it
        self.assignments_tree.bind("<Button-3>", self._on_assignment_right_click)

        # Populate with real game data
        self._populate_assignments()
        
        self.assignments_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Right: Assignment details
        right_frame = tk.LabelFrame(content_frame, text="Assignment Details",
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 12, 'bold'))
        right_frame.pack(side='right', fill='y', padx=(10, 0))
        right_frame.configure(width=300)
        right_frame.pack_propagate(False)
        
        # Scout picker (real scouting staff)
        scout_frame = tk.Frame(right_frame, bg=self.app.CONTENT_BG)
        scout_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(scout_frame, text="Scout:",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w')

        self.assign_scout_var = tk.StringVar()
        self.assign_scout_combo = ttk.Combobox(scout_frame,
                                              textvariable=self.assign_scout_var,
                                              state="readonly", width=25)
        self.assign_scout_combo.pack(anchor='w', pady=5)
        self._refresh_assign_scout_combo()

        # Assignment type options (real variable -- Track B)
        type_frame = tk.Frame(right_frame, bg=self.app.CONTENT_BG)
        type_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(type_frame, text="Assignment Type:",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w')

        self.assign_type_var = tk.StringVar(value="Player Scouting")
        assignment_types = ["Player Scouting", "Team Analysis", "League Overview", "Prospect Evaluation"]
        for atype in assignment_types:
            tk.Radiobutton(type_frame, text=atype, variable=self.assign_type_var, value=atype,
                          bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                          selectcolor=self.app.CONTENT_BG,
                          font=_sfont(self.app.FONT_FAMILY, 9)).pack(anchor='w', pady=2)

        # Priority selection (real variable)
        priority_frame = tk.Frame(right_frame, bg=self.app.CONTENT_BG)
        priority_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(priority_frame, text="Priority Level:",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w')

        self.assign_priority_var = tk.StringVar(value="Medium")
        priority_combo = ttk.Combobox(priority_frame, textvariable=self.assign_priority_var,
                                     values=["Low", "Medium", "High", "Critical"],
                                     state="readonly", width=25)
        priority_combo.pack(anchor='w', pady=5)

        # Desired-by note (free text; the engine closes the assignment when
        # the report reaches 'A' accuracy)
        deadline_frame = tk.Frame(right_frame, bg=self.app.CONTENT_BG)
        deadline_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(deadline_frame, text="Desired by (note):",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10, 'bold')).pack(anchor='w')

        self.assign_deadline_var = tk.StringVar()
        deadline_entry = tk.Entry(deadline_frame, textvariable=self.assign_deadline_var,
                                  width=25,
                                  font=_sfont(self.app.FONT_FAMILY, 9))
        deadline_entry.pack(anchor='w', pady=5)

        # Target hint + create button
        self.assign_target_hint = tk.Label(right_frame,
                text="Target: select a player on the Players tab, or use + New Assignment to search.",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 9), wraplength=260, justify='left')
        self.assign_target_hint.pack(fill='x', padx=10, pady=(4, 4))

        create_btn = tk.Button(right_frame, text="Create Assignment",
                               bg=self.app.ACCENT_COLOR, fg='white',
                               font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                               command=self._create_assignment_from_pane)
        create_btn.pack(padx=10, pady=(4, 10), anchor='w')

    def _refresh_assign_scout_combo(self):
        """Fill the assignment composer scout picker with real scouts."""
        try:
            from scouting_window_helpers import scouts_of
            scouts = scouts_of(self.app)
        except Exception:
            scouts = []
        combo = getattr(self, 'assign_scout_combo', None)
        if combo is None:
            return
        names = [getattr(s, 'full_name', '?') for s in scouts]
        combo['values'] = names
        if names and not self.assign_scout_var.get():
            self.assign_scout_var.set(names[0])
        self._assign_scout_list = scouts

    def _create_assignment_from_pane(self):
        """Create a REAL assignment from the right-pane composer.

        Scout + type + priority come from the pane's real controls; the
        target is the Players tab selection (or the search dialog if none).
        """
        try:
            from scouting_window_helpers import (create_scout_assignment,
                                                 open_assignment_dialog)
        except Exception as e:
            messagebox.showerror("Scouting", f"Scouting helpers unavailable: {e}")
            return

        scouts = getattr(self, '_assign_scout_list', None) or []
        scout = None
        try:
            idx = list(self.assign_scout_combo['values']).index(self.assign_scout_var.get())
            scout = scouts[idx]
        except Exception:
            scout = None
        if scout is None:
            messagebox.showwarning("No Scout", "Please select a scout.")
            return

        player = None
        try:
            sel = self.players_tree.selection()
            if sel:
                player = self.app.tree_maps['players_tree'].get(sel[0])
        except Exception:
            player = None

        req_type = self.assign_type_var.get()
        req_priority = self.assign_priority_var.get()
        deadline = self.assign_deadline_var.get().strip()

        if player is None:
            # No target selected: open the search dialog with pane defaults
            open_assignment_dialog(
                self, self.app, preselected_scout=scout,
                request_type=req_type, request_priority=req_priority,
                on_created=self._populate_assignments)
            return

        ok, msg = create_scout_assignment(self.app, player, scout)
        if deadline:
            msg = f"{msg}\nDesired by: {deadline} (request note)"
        (messagebox.showinfo if ok else messagebox.showwarning)(
            "Scouting Assignment", f"[{req_type} \u00b7 {req_priority}]\n{msg}")
        if ok:
            self._populate_assignments()
    
    def _create_reports_interface(self, parent):
        """Create reports interface"""
        main_frame = tk.Frame(parent, bg=self.app.CONTENT_BG)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header
        header_frame = tk.Frame(main_frame, bg=self.app.CONTENT_BG)
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_label = tk.Label(header_frame, text="Scouting Reports",
                              font=_sfont(self.app.FONT_FAMILY, 16, 'bold'),
                              bg=self.app.CONTENT_BG, fg=self.app.HEADER_COLOR)
        title_label.pack(side='left')
        
        # Filter and action buttons
        btn_frame = tk.Frame(header_frame, bg=self.app.CONTENT_BG)
        btn_frame.pack(side='right')
        
        filter_combo = ttk.Combobox(btn_frame, values=["All Reports", "Recent", "High Priority", "My Reports"],
                                   state="readonly", width=15)
        filter_combo.pack(side='left', padx=(0, 10))
        filter_combo.set("All Reports")
        
        new_report_btn = tk.Button(btn_frame, text="+ New Report",
                                  bg=self.app.ACCENT_COLOR, fg='white',
                                  font=_sfont(self.app.FONT_FAMILY, 10, 'bold'),
                                  command=self._create_new_report)
        new_report_btn.pack(side='left')
        
        # Main content area
        content_frame = tk.Frame(main_frame, bg=self.app.CONTENT_BG)
        content_frame.pack(fill='both', expand=True)
        
        # Left: Reports list
        left_frame = tk.LabelFrame(content_frame, text="Available Reports",
                                  bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                  font=_sfont(self.app.FONT_FAMILY, 12, 'bold'))
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Reports treeview
        report_cols = ('Player/Team', 'Scout', 'Date', 'Type', 'Grade', 'Status')
        self.reports_tree = ttk.Treeview(left_frame, columns=report_cols, show='headings', height=15)
        
        for col in report_cols:
            self.reports_tree.heading(col, text=col)
            self.reports_tree.column(col, width=90, minwidth=70)
        
        # Populate with real game data
        self._populate_reports()
        
        self.reports_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Bind selection event
        self.reports_tree.bind('<<TreeviewSelect>>', self._on_report_select)
        
        # Right: Report details
        right_frame = tk.LabelFrame(content_frame, text="Report Details",
                                   bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                                   font=_sfont(self.app.FONT_FAMILY, 12, 'bold'))
        right_frame.pack(side='right', fill='y', padx=(10, 0))
        right_frame.configure(width=350)
        right_frame.pack_propagate(False)
        
        # Report content area
        self.report_details_frame = tk.Frame(right_frame, bg=self.app.CONTENT_BG)
        self.report_details_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Default report view
        self._show_default_report_view()
        
    def _show_default_report_view(self):
        """Show default report view when no report is selected"""
        for widget in self.report_details_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.report_details_frame, text="Select a report to view details",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 11, 'italic')).pack(expand=True)
        
    def _on_report_select(self, event):
        """Handle report selection: render the REAL filed report.

        Fog-of-war safe: only the graded information the scout actually
        filed (accuracy, viewings, graded potential range, strengths /
        weaknesses the report lists). Never raw attributes.
        """
        selection = self.reports_tree.selection()
        if not selection:
            self._show_default_report_view()
            return

        entry = self.app.tree_maps.get('reports_tree', {}).get(selection[0])
        if not entry:
            self._show_default_report_view()
            return
        player, report = entry
        if report is None:
            self._show_default_report_view()
            return

        try:
            from scouting_window_helpers import report_display_lines
        except Exception:
            self._show_default_report_view()
            return
        rows, pot = report_display_lines(player, report)

        # Clear previous content
        for widget in self.report_details_frame.winfo_children():
            widget.destroy()

        player_name = getattr(player, 'full_name', '?')
        scout_name = getattr(getattr(report, 'scout', None), 'full_name', '\u2014')
        last = getattr(report, 'last_viewed', None)
        try:
            report_date = last.strftime("%Y-%m-%d") if last else "\u2014"
        except Exception:
            report_date = "\u2014"

        # Player info
        tk.Label(self.report_details_frame, text=f"Player: {player_name}",
                bg=self.app.CONTENT_BG, fg=self.app.HEADER_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 12, 'bold')).pack(anchor='w', pady=(0, 5))

        tk.Label(self.report_details_frame, text=f"Scout: {scout_name}",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10)).pack(anchor='w')

        tk.Label(self.report_details_frame, text=f"Date: {report_date}",
                bg=self.app.CONTENT_BG, fg=self.app.TEXT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 10)).pack(anchor='w')

        tk.Label(self.report_details_frame, text=f"Graded potential: {pot}",
                bg=self.app.CONTENT_BG, fg=self.app.ACCENT_COLOR,
                font=_sfont(self.app.FONT_FAMILY, 11, 'bold')).pack(anchor='w', pady=(5, 10))

        # Report content (fog-of-war safe)
        report_text = tk.Text(self.report_details_frame, height=12, width=35,
                             bg=self.app.BG_COLOR, fg=self.app.TEXT_COLOR,
                             font=_sfont(self.app.FONT_FAMILY, 9), wrap='word')
        report_text.pack(fill='both', expand=True)

        for label, text in rows:
            report_text.insert('end', f"{label.upper()}\n", "hdr")
            report_text.insert('end', f"{text}\n\n")
        report_text.tag_config("hdr", font=_sfont(self.app.FONT_FAMILY, 9, 'bold'))
        report_text.configure(state='disabled')
    
    def _generate_report_content(self, player_name, grade):
        """Generate realistic report content based on actual player data"""
        try:
            # Find the actual player
            players = self.game_data.get('players', [])
            target_player = None
            
            for player in players:
                full_name = getattr(player, 'full_name', f"{player.first_name} {player.last_name}")
                if full_name == player_name:
                    target_player = player
                    break
            
            if target_player:
                # Generate content based on actual attributes
                position = getattr(target_player, 'primary_position', 'Forward')
                age = getattr(target_player, 'age', 20)
                overall = getattr(target_player, 'overall_rating', lambda: 70)()
                
                # Convert position enum to string if needed
                if hasattr(position, 'value'):
                    position = position.value
                
                # Generate strengths based on high attributes
                strengths = []
                if hasattr(target_player, 'skating') and target_player.skating > 15:
                    strengths.append("Excellent skating ability and mobility")
                if hasattr(target_player, 'shooting') and target_player.shooting > 15:
                    strengths.append("Strong shooting accuracy and power")
                if hasattr(target_player, 'passing') and target_player.passing > 15:
                    strengths.append("Superior vision and passing skills")
                if hasattr(target_player, 'hockey_iq') and target_player.hockey_iq > 15:
                    strengths.append("High hockey IQ and game awareness")
                if hasattr(target_player, 'determination') and target_player.determination > 15:
                    strengths.append("Strong work ethic and determination")
                
                # Default strengths if none found
                if not strengths:
                    strengths = ["Solid fundamental skills", "Good work ethic", "Coachable attitude"]
                
                # Generate weaknesses based on lower attributes
                weaknesses = []
                if hasattr(target_player, 'strength') and target_player.strength < 60:
                    weaknesses.append("Needs to add physical strength")
                if hasattr(target_player, 'discipline') and target_player.discipline < 60:
                    weaknesses.append("Occasional discipline issues")
                if hasattr(target_player, 'consistency') and getattr(target_player, 'consistency', 50) < 60:
                    weaknesses.append("Consistency can be improved")
                
                # Default weaknesses if none found
                if not weaknesses:
                    weaknesses = ["Minor areas for development", "Needs more experience"]
                
                # Generate projection based on age and overall
                if age < 20:
                    if overall > 42:
                        projection = "Elite prospect with franchise player potential"
                    elif overall > 35:
                        projection = "High-end prospect with top-6 upside"
                    else:
                        projection = "Solid prospect with NHL potential"
                else:
                    if overall > 46:
                        projection = "Ready for immediate NHL impact"
                    elif overall > 40:
                        projection = "NHL-ready with room for growth"
                    else:
                        projection = "Depth player with specific role potential"
                
                content = f"""SCOUTING REPORT - {player_name}

PLAYER INFO:
Position: {position}
Age: {age}
Overall Rating: {overall}

STRENGTHS:
"""
                for strength in strengths[:4]:  # Top 4 strengths
                    content += f"• {strength}\n"
                
                content += f"""
AREAS FOR IMPROVEMENT:
"""
                for weakness in weaknesses[:3]:  # Top 3 weaknesses
                    content += f"• {weakness}\n"
                
                content += f"""
PROJECTION:
{projection}

RECOMMENDATION:
Grade {grade} - {'Highly recommended' if grade in ['A+', 'A'] else 'Recommended' if grade in ['A-', 'B+'] else 'Consider for depth'}"""
                
                return content
            
        except Exception as e:
            print(f"Error generating report content: {e}")
        
        # Fallback generic content
        return f"""SCOUTING REPORT - {player_name}

STRENGTHS:
• Solid fundamental skills
• Good work ethic
• Coachable attitude

AREAS FOR IMPROVEMENT:
• Continue developing all-around game
• Gain more experience

PROJECTION:
Promising player with development potential.

RECOMMENDATION:
Grade {grade} - Worth monitoring progress."""
    
    def _populate_scouting_staff(self):
        """Populate scouting staff data"""
        try:
            scouts = self.game_data.get('scouts', [])
            
            # Clear existing data
            if hasattr(self, 'staff_tree'):
                self.staff_tree.delete(*self.staff_tree.get_children())
            
            # Populate staff tree if it exists
            if hasattr(self, 'staff_tree') and scouts:
                for scout in scouts:
                    name = getattr(scout, 'full_name', f"{scout.first_name} {scout.last_name}")
                    age = getattr(scout, 'age', 'Unknown')
                    ability = getattr(scout, 'ability', 'Unknown')
                    contract_status = "Under Contract" if getattr(scout, 'contract', None) else "No Contract"
                    
                    self.staff_tree.insert('', 'end', values=(
                        name, age, ability, contract_status
                    ))
            
            self._update_status(f"Loaded {len(scouts)} scouts")
            
        except Exception as e:
            self._update_status(f"Error loading scouts: {str(e)}")
            print(f"Error in _populate_scouting_staff: {e}")
    
    def _populate_draft_prospects(self):
        """Populate draft prospects from the REAL draft class.

        Fog-of-war display only: graded potential ranges from real reports
        (or the public consensus range when unscouted) plus the real
        scouting status. Never raw attributes. Rows map to real players in
        app.tree_maps['draft_tree'] for double-click reports.
        """
        try:
            if hasattr(self, 'draft_tree'):
                self.draft_tree.delete(*self.draft_tree.get_children())
        except Exception:
            pass
        try:
            from scouting import (consensus_range, report_potential_display,
                                  GRADE_ORDER, grade_color)
            from scouting_window_helpers import reports_of, assignments_of
            reports = reports_of(self.app)
            assigns = assignments_of(self.app)
        except Exception:
            return

        if 'draft_tree' not in self.app.tree_maps:
            self.app.tree_maps['draft_tree'] = {}
        tree_map = self.app.tree_maps['draft_tree']
        tree_map.clear()

        try:
            prospects = self._filtered_draft_prospects()[:200]
        except Exception as e:
            print(f"Error filtering draft prospects: {e}")
            return

        if hasattr(self, 'draft_tree'):
            for i, prospect in enumerate(prospects):
                try:
                    name = getattr(prospect, 'full_name',
                                   f"{getattr(prospect, 'first_name', '?')} {getattr(prospect, 'last_name', '')}")
                    position = getattr(prospect, 'primary_position', 'Unknown')
                    if hasattr(position, 'value'):
                        position = position.value
                    age = getattr(prospect, 'age', 'Unknown')

                    pid = getattr(prospect, 'id', None)
                    report = reports.get(pid)
                    if report:
                        pot = report_potential_display(report, prospect)
                        status = f"Scouted ({getattr(report, 'accuracy', '?')})"
                        top_grade = pot.split("–")[-1].strip()
                    elif prospect in assigns:
                        pot = consensus_range(prospect)
                        status = "In Progress"
                        top_grade = pot.split("–")[-1].strip()
                    else:
                        pot = consensus_range(prospect)
                        status = "—"
                        top_grade = pot.split("–")[-1].strip()

                    tags = ()
                    if top_grade in GRADE_ORDER:
                        tag = f"pot_{top_grade}"
                        try:
                            self.draft_tree.tag_configure(
                                tag, foreground=grade_color(top_grade))
                        except Exception:
                            pass
                        tags = (tag,)

                    item = self.draft_tree.insert(
                        '', 'end',
                        values=(i + 1, name, str(position), age, pot, status),
                        tags=tags)
                    tree_map[item] = prospect
                except Exception as e:
                    print(f"Error adding prospect: {e}")
                    continue

        self._update_status(f"Loaded {len(prospects)} draft prospects")
    
    def update_views(self):
        """Update all views when game data changes"""
        self.game_data = self._initialize_game_data()
        self._load_initial_data()
    
    def _create_new_assignment(self):
        """Create a REAL scouting assignment (non-modal dialog).

        Writes into app.scouting_assignments -- the same store the engine
        processes daily. Shows the real estimated completion derived from
        live state. Dismissing the dialog defers.
        """
        try:
            from scouting_window_helpers import open_assignment_dialog
        except Exception as e:
            messagebox.showerror("Scouting", f"Scouting helpers unavailable: {e}")
            return
        req_type = getattr(self, 'assign_type_var', None)
        req_pri = getattr(self, 'assign_priority_var', None)
        open_assignment_dialog(
            self, self.app,
            request_type=req_type.get() if req_type else "Player Scouting",
            request_priority=req_pri.get() if req_pri else "Medium",
            on_created=self._populate_assignments)

    def _create_new_report(self):
        """File a new REAL scouting report via the war-room quick-scout flow.

        Picks the best available scout and runs ONE rushed viewing through
        the real ScoutingReport.update_report machinery for the selected
        player, then shows the filed report. Scout-filtered only -- never
        raw attributes.
        """
        selection = None
        try:
            selection = self.players_tree.selection()
        except Exception:
            selection = None
        if not selection:
            messagebox.showwarning("No Selection",
                                   "Select a player on the Players tab first -- "
                                   "the report is filed for that player.")
            return
        player = self.app.tree_maps.get('players_tree', {}).get(selection[0])
        if player is None:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        try:
            from scouting_window_helpers import scouts_of, reports_of
            from game_classes import StaffRole, ScoutingReport
            scouts = scouts_of(self.app)
            if not scouts:
                messagebox.showwarning(
                    "No Scouts",
                    "You need scouts before you can file reports.\n\n"
                    "Hire scouts via Staff \u2192 Hire Staff (free-agent staff market).")
                return

            def _key(s):
                role_bonus = (100 if getattr(s, "role", None) == StaffRole.AMATEUR_SCOUT else 0)
                return (role_bonus
                        + getattr(s, "judging_player_ability", 10)
                        + getattr(s, "judging_player_potential", 10))
            scout = max(scouts, key=_key)

            reports = reports_of(self.app)
            pid = getattr(player, "id", None)
            report = reports.get(pid)
            if report is None:
                report = ScoutingReport(player=player, scout=scout)
                reports[pid] = report
            # One rushed viewing through the real machinery
            report.update_report(player, scout)
            note = "Rushed single viewing filed from the Reports tab."
            report.notes = (note if not report.notes else report.notes + " " + note)
        except Exception as e:
            messagebox.showerror("Report", f"Could not file the report:\n{e}")
            return
        self._populate_reports()
        try:
            from scouting_window_helpers import show_prospect_report
            show_prospect_report(self, self.app, player)
        except Exception:
            messagebox.showinfo(
                "Report Filed",
                f"Report filed for {getattr(player, 'full_name', '?')}: "
                f"accuracy {getattr(report, 'accuracy', '?')} "
                f"({getattr(report, 'viewings', 0)} viewings).")

    def _on_assignment_right_click(self, event):
        """Right-click menu on a live assignment: cancel it for real."""
        row = self.assignments_tree.identify_row(event.y)
        if not row:
            return
        self.assignments_tree.selection_set(row)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Cancel Assignment",
                         command=self._cancel_assignment)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

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

        result = messagebox.askyesno(
            "Cancel Assignment",
            f"Stop scouting {getattr(player, 'full_name', 'this player')}?\n\n"
            "The scout is freed up; any report filed so far is kept.")
        if result:
            ok, msg = cancel_scout_assignment(self.app, player)
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Assignment Cancelled" if ok else "Scouting", msg)
            self._populate_assignments()

    def _populate_assignments(self):
        """Populate the assignments tree from the REAL scouting_assignments.

        Every row is a live {Player: Staff} assignment the engine processes
        daily; progress/accuracy come from the real filed reports and the
        completion estimate is derived from live state. Item -> player refs
        are kept in app.tree_maps['assignments_tree'].
        """
        try:
            self.assignments_tree.delete(*self.assignments_tree.get_children())
        except Exception:
            return
        try:
            from scouting_window_helpers import (
                assignments_of, estimate_completion_days, reports_of)
        except Exception as e:
            print(f"Error populating assignments: {e}")
            return
        try:
            assigns = assignments_of(self.app)
            reports = reports_of(self.app)
            if 'assignments_tree' not in self.app.tree_maps:
                self.app.tree_maps['assignments_tree'] = {}
            tree_map = self.app.tree_maps['assignments_tree']
            tree_map.clear()
            for player, scout in assigns.items():
                report = reports.get(getattr(player, "id", None))
                views = getattr(report, "viewings", 0) if report else 0
                acc = getattr(report, "accuracy", "\u2014") if report else "\u2014"
                days = estimate_completion_days(self.app, player, scout)
                eta = "complete" if days == 0 else (f"~{days}d" if days else "\u2014")
                item = self.assignments_tree.insert('', 'end', values=(
                    getattr(scout, "full_name", "?"),
                    getattr(player, "full_name", "?"),
                    "Player Scouting",
                    "Medium",
                    eta,
                    f"{views} viewings \u00b7 {acc}",
                ))
                tree_map[item] = player
            # Keep the composer scout picker in sync
            self._refresh_assign_scout_combo()
        except Exception as e:
            print(f"Error populating assignments: {e}")

    def _populate_reports(self):
        """Populate the reports tree from the REAL filed scouting_reports.

        Every row is a real ScoutingReport the engine built up via
        report.update_report; dates are the real last-viewed timestamps and
        grades are the real accuracy grades. Selecting a row renders the
        fog-of-war-safe report content.
        """
        try:
            self.reports_tree.delete(*self.reports_tree.get_children())
        except Exception:
            return
        try:
            from scouting_window_helpers import reports_of
        except Exception as e:
            print(f"Error populating reports: {e}")
            return
        try:
            reports = reports_of(self.app)
            if 'reports_tree' not in self.app.tree_maps:
                self.app.tree_maps['reports_tree'] = {}
            tree_map = self.app.tree_maps['reports_tree']
            tree_map.clear()

            def _player_for(pid):
                for p in (self.game_data.get('players', []) or []):
                    if getattr(p, "id", None) == pid:
                        return p
                return None

            rows = []
            for pid, report in reports.items():
                player = _player_for(pid)
                name = getattr(player, "full_name", None) or f"Player {pid}"
                scout_name = getattr(getattr(report, "scout", None), "full_name", "\u2014")
                last = getattr(report, "last_viewed", None)
                try:
                    datestr = last.strftime("%Y-%m-%d") if last else "\u2014"
                except Exception:
                    datestr = "\u2014"
                acc = getattr(report, "accuracy", "?")
                status = "Complete" if acc == "A" else "In Progress"
                rows.append((datestr, name, scout_name, acc, status, player, report))
            rows.sort(key=lambda r: r[0], reverse=True)
            for datestr, name, scout_name, acc, status, player, report in rows:
                item = self.reports_tree.insert('', 'end', values=(
                    name, scout_name, datestr, "Player", acc, status))
                tree_map[item] = (player, report)
        except Exception as e:
            print(f"Error populating reports: {e}")


class ProfessionalScoutingWindow(InGamePopup):
    """Popup wrapper around ProfessionalScoutingView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Professional Scouting Center")
        self._view = ProfessionalScoutingView(self, app=parent, *args, **kwargs)
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
