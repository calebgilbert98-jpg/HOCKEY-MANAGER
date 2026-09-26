"""
Professional Scouting Management System
Clean, comprehensive scouting interface with dedicated draft analysis
Features: Player database, scout management, draft prospects, assignments, and reports
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Any
import datetime
import random
from game_classes import Player, PlayerPosition, Staff, StaffRole, to_100_scale
from game_classes import debug_print
from ui_widgets import PillButton


class ProfessionalScoutingWindow(tk.Toplevel):
    """Professional scouting management interface with comprehensive features"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Professional Scouting Center")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1400x900")
        self.minsize(1000, 700)
        self.resizable(True, True)
        
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
        if hasattr(self.parent, 'open_windows'):
            self.parent.open_windows['scouting'] = self
        
        # Center window on screen
        self._center_window()
        
    def _initialize_game_data(self) -> Dict[str, Any]:
        """Initialize game data structure with proper error handling"""
        try:
            game_manager = getattr(self.parent, 'game_manager', None)
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
            
            # Get scouting staff - generate some if empty
            scouts = self._get_scouting_staff(user_team)
            if not scouts and user_team:
                scouts = self._generate_basic_scouts(user_team)
            
            # Get current draft class
            draft_class = self._get_draft_prospects(game_manager)
            
            # If no players found, generate some sample data
            if not all_players:
                all_players = self._generate_sample_players()
            
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
        """Generate minimal fallback data when no game manager exists"""
        return {
            'players': self._generate_sample_players(),
            'scouts': self._generate_sample_scouts(),
            'user_team': None,
            'league': None,
            'draft_class': [],
            'assignments': {},
            'reports': {}
        }
    
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
        
        # If no scouts found, create a basic scout for functionality
        if not scouts:
            from game_classes import Staff, Contract
            import datetime
            
            # Create a basic scout
            contract = Contract(
                annual_salary=50000,
                contract_years=1,
                contract_end=datetime.date.today().year + 1
            )
            
            scout = Staff(
                first_name="John",
                last_name="Scout",
                age=40,
                nationality="USA",
                position="Scout",
                ability=12,
                potential=12,
                contract=contract
            )
            scouts.append(scout)
        
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
        if not hasattr(self.parent, 'tree_maps'):
            self.parent.tree_maps = {}
        
        required_maps = ['players_tree', 'scouts_tree', 'draft_tree', 'assignments_tree', 'reports_tree']
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
        header_frame = tk.Frame(self, bg=self.parent.TITLE_BAR_COLOR, height=75)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Main title and date
        title_frame = tk.Frame(header_frame, bg=self.parent.TITLE_BAR_COLOR)
        title_frame.pack(expand=True)
        
        title_label = tk.Label(title_frame, text="PROFESSIONAL SCOUTING CENTER",
                              font=(self.parent.FONT_FAMILY, 18, "bold"),
                              bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.HEADER_COLOR)
        title_label.pack(pady=(18, 2))
        
        # Current date and context
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        team_name = self.game_data['user_team'].team_name if self.game_data.get('user_team') else "Organization"
        subtitle = f"{team_name} Scouting Operations • {current_date}"
        subtitle_label = tk.Label(title_frame, text=subtitle,
                                font=(self.parent.FONT_FAMILY, 10),
                                bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR)
        subtitle_label.pack()
        
    def _create_status_bar(self):
        """Create comprehensive status bar"""
        status_frame = tk.Frame(self, bg=self.parent.TITLE_BAR_COLOR, height=40)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        # Left side - system status
        self.status_label = tk.Label(status_frame, text="System Ready",
                                   bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 9))
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
                                     bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR,
                                     font=(self.parent.FONT_FAMILY, 9))
            self.data_label.pack(side='right', padx=15, pady=10)
    
    def _create_player_database_tab(self):
        """Create comprehensive player database interface"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="Player Database")
        
        # Advanced filters
        self._create_advanced_player_filters(tab_frame)
        
        # Player list with enhanced features
        self._create_enhanced_player_list(tab_frame)
        
    def _create_advanced_player_filters(self, parent):
        """Create comprehensive filtering system"""
        filter_frame = tk.LabelFrame(parent, text="Advanced Player Search & Analysis", \
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,\
                                   font=(self.parent.FONT_FAMILY, 11, "bold"), relief='groove')
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
        top_row = tk.Frame(filter_frame, bg=self.parent.CONTENT_BG)
        top_row.pack(fill='x', padx=12, pady=8)
        tk.Label(top_row, text="Search:", bg=self.parent.CONTENT_BG,
                fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 10)).pack(side='left')
        search_entry = tk.Entry(top_row, textvariable=self.filter_vars['player_search'],
                              width=22, font=(self.parent.FONT_FAMILY, 10))
        search_entry.pack(side='left', padx=(5, 20))
        search_entry.bind('<KeyRelease>', lambda e: self._apply_player_filters())
        tk.Label(top_row, text="Team:", bg=self.parent.CONTENT_BG,
                fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 10)).pack(side='left')
        self.player_team_combo = ttk.Combobox(top_row, textvariable=self.filter_vars['player_team'],
                                           width=16, state="readonly")
        self.player_team_combo.pack(side='left', padx=(5, 0))
        self.player_team_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_player_filters())
        clear_btn = PillButton(top_row, text="Clear All", bg=self.parent.CONTENT_BG,
                               font=(self.parent.FONT_FAMILY, 9, 'bold'),
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
            row = tk.Frame(filter_frame, bg=self.parent.CONTENT_BG)
            row.pack(fill='x', padx=12, pady=2)
            tk.Label(row, text=label, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                     font=(self.parent.FONT_FAMILY, 10, 'bold'),
                     width=10, anchor='w').pack(side='left')
            btns = {}
            for value, text in options:
                b = PillButton(row, text=text, bg=self.parent.CONTENT_BG,
                               font=(self.parent.FONT_FAMILY, 9, 'bold'),
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
                                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                 font=(self.parent.FONT_FAMILY, 11, "bold"), relief='groove')
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
        toolbar_frame = tk.Frame(parent, bg=self.parent.CONTENT_BG, height=50)
        toolbar_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        toolbar_frame.grid_propagate(False)
        
        # Primary actions
        scout_btn = tk.Button(toolbar_frame, text="Assign Scout", 
                            bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                            font=(self.parent.FONT_FAMILY, 10, "bold"),
                            command=self._assign_scout_to_player)
        scout_btn.pack(side='left', padx=(10, 8))
        
        profile_btn = tk.Button(toolbar_frame, text="View Profile", 
                               bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                               font=(self.parent.FONT_FAMILY, 10),
                               command=self._view_player_profile)
        profile_btn.pack(side='left', padx=(0, 8))
        
        watchlist_btn = tk.Button(toolbar_frame, text="Add to Watchlist", 
                                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                font=(self.parent.FONT_FAMILY, 10),
                                command=self._add_to_watchlist)
        watchlist_btn.pack(side='left', padx=(0, 8))
        
        compare_btn = tk.Button(toolbar_frame, text="Compare Players", 
                               bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                               font=(self.parent.FONT_FAMILY, 10),
                               command=self._compare_players)
        compare_btn.pack(side='left', padx=(0, 8))
        
        # Info label on right
        info_label = tk.Label(toolbar_frame, text="Double-click player for detailed analysis",
                            bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                            font=(self.parent.FONT_FAMILY, 9, "italic"))
        info_label.pack(side='right', padx=10)
    
    def _create_scouting_staff_tab(self):
        """Create scouting staff management interface"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="Scouting Staff")
        
        # Staff overview
        self._create_staff_overview(tab_frame)
        
        # Staff list
        self._create_staff_list(tab_frame)
        
    def _create_draft_center_tab(self):
        """Create dedicated draft analysis center - THE NEW FEATURE"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="Draft Center")
        
        # Draft year info
        self._create_draft_header(tab_frame)
        
        # Draft prospect filters
        self._create_draft_filters(tab_frame)
        
        # Draft prospect rankings
        self._create_draft_rankings(tab_frame)
        
    def _create_assignments_tab(self):
        """Create scouting assignments management"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
        self.notebook.add(tab_frame, text="Assignments")
        
        # Assignment management interface
        self._create_assignment_interface(tab_frame)
        
    def _create_reports_tab(self):
        """Create scouting reports interface"""
        tab_frame = tk.Frame(self.notebook, bg=self.parent.CONTENT_BG)
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
                if 'players_tree' not in self.parent.tree_maps:
                    self.parent.tree_maps['players_tree'] = {}
                self.parent.tree_maps['players_tree'][item] = player
                
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
            if old_item_id in self.parent.tree_maps['players_tree']:
                self.parent.tree_maps['players_tree'][new_item_id] = self.parent.tree_maps['players_tree'][old_item_id]
                del self.parent.tree_maps['players_tree'][old_item_id]
        
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
        """Show context menu for selected player"""
        item = self.players_tree.identify_row(event.y)
        if item:
            self.players_tree.selection_set(item)
            
            context_menu = tk.Menu(self, tearoff=0)
            context_menu.add_command(label="Assign Scout", command=self._assign_scout_to_player)
            context_menu.add_command(label="View Profile", command=self._view_player_profile)
            context_menu.add_separator()
            context_menu.add_command(label="Add to Watchlist", command=self._add_to_watchlist)
            context_menu.add_command(label="Compare", command=self._compare_players)
            context_menu.add_separator()
            context_menu.add_command(label="Advanced Analysis", command=self._advanced_analysis)
            
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
    
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
        
        player = self.parent.tree_maps['players_tree'].get(selection[0])
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Show scout assignment dialog
        self._show_scout_assignment_dialog(player, scouts)
    
    def _show_scout_assignment_dialog(self, player, scouts):
        """Show dialog for assigning scout to player"""
        dialog = tk.Toplevel(self)
        dialog.title(f"Assign Scout - {player.full_name}")
        dialog.geometry("400x300")
        dialog.configure(bg=self.parent.CONTENT_BG)
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Dialog content
        tk.Label(dialog, text=f"Assign Scout to Evaluate {player.full_name}",
                font=(self.parent.FONT_FAMILY, 12, "bold"),
                bg=self.parent.CONTENT_BG, fg=self.parent.HEADER_COLOR).pack(pady=15)
        
        # Scout selection
        tk.Label(dialog, text="Available Scouts:",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(pady=(10, 5))
        
        scout_var = tk.StringVar()
        scout_listbox = tk.Listbox(dialog, height=6)
        scout_listbox.pack(pady=5, padx=20, fill='x')
        
        for i, scout in enumerate(scouts):
            scout_name = scout.full_name
            scout_ability = getattr(scout, 'judging_player_ability', 'Unknown')
            scout_listbox.insert(tk.END, f"{scout_name} (Ability: {scout_ability})")
        
        # Priority selection
        tk.Label(dialog, text="Assignment Priority:",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(pady=(15, 5))
        
        priority_var = tk.StringVar(value="Normal")
        priority_frame = tk.Frame(dialog, bg=self.parent.CONTENT_BG)
        priority_frame.pack(pady=5)
        
        for priority in ["Low", "Normal", "High", "Urgent"]:
            tk.Radiobutton(priority_frame, text=priority, variable=priority_var, value=priority,
                          bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                          selectcolor=self.parent.ACCENT_COLOR).pack(side='left', padx=10)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.parent.CONTENT_BG)
        btn_frame.pack(pady=20)
        
        def assign_scout():
            selection = scout_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Scout", "Please select a scout.")
                return
            
            scout = scouts[selection[0]]
            priority = priority_var.get()
            
            # In full implementation, this would create actual assignment
            messagebox.showinfo("Assignment Created", 
                              f"Scout {scout.full_name} assigned to evaluate {player.full_name}\n"
                              f"Priority: {priority}\n"
                              f"Estimated completion: 7-14 days")
            dialog.destroy()
        
        tk.Button(btn_frame, text="Assign Scout", command=assign_scout,
                 bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                 font=(self.parent.FONT_FAMILY, 10, "bold")).pack(side='left', padx=(0, 10))
        
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(side='left')
    
    def _view_player_profile(self):
        """View detailed player profile"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to view.")
            return
        
        player = self.parent.tree_maps['players_tree'].get(selection[0])
        if not player:
            messagebox.showerror("Error", "Could not find selected player.")
            return
        
        # Try to use enhanced player profile if available
        try:
            from ui_components import PlayerProfileWindow
            PlayerProfileWindow(self.parent, player)
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
    
    def _add_to_watchlist(self):
        """Add selected player to watchlist"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to add to watchlist.")
            return
        
        player = self.parent.tree_maps['players_tree'].get(selection[0])
        if player:
            messagebox.showinfo("Watchlist", f"{player.full_name} added to your watchlist!")
    
    def _compare_players(self):
        """Compare selected players"""
        selection = self.players_tree.selection()
        if len(selection) < 2:
            messagebox.showwarning("Insufficient Selection", "Please select 2 or more players to compare.")
            return
        
        messagebox.showinfo("Player Comparison", f"Comparing {len(selection)} players...\n\nDetailed comparison interface would open here.")
    
    def _advanced_analysis(self):
        """Show advanced player analysis"""
        selection = self.players_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player for analysis.")
            return
        
        player = self.parent.tree_maps['players_tree'].get(selection[0])
        if player:
            messagebox.showinfo("Advanced Analysis", f"Advanced statistical analysis for {player.full_name}\n\nWould show detailed breakdowns, trends, comparisons, etc.")
    
    # Placeholder methods for other tabs - to be implemented
    def _create_staff_overview(self, parent):
        """Create staff overview section"""
        overview_frame = tk.LabelFrame(parent, text="Scouting Department Overview",
                                     bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                     font=(self.parent.FONT_FAMILY, 11, "bold"))
        overview_frame.pack(fill='x', padx=15, pady=10)
        
        info_text = f"""
Staff Count: {len(self.game_data.get('scouts', []))}
Active Assignments: 0
Completed Reports: 0
Budget Remaining: $50,000
        """
        
        tk.Label(overview_frame, text=info_text.strip(),
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10), justify='left').pack(pady=10)
    
    def _create_staff_list(self, parent):
        """Create scouting staff list"""
        list_frame = tk.LabelFrame(parent, text="Scouting Staff",
                                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                 font=(self.parent.FONT_FAMILY, 11, "bold"))
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
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 11, "bold"))
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
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10), justify='left').pack(pady=10)
    
    def _create_draft_filters(self, parent):
        """Create draft prospect filters"""
        # Placeholder for draft filters
        filter_frame = tk.LabelFrame(parent, text="Draft Prospect Filters",
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 11, "bold"))
        filter_frame.pack(fill='x', padx=15, pady=(0, 10))
        
        tk.Label(filter_frame, text="Draft prospect filtering system would be implemented here.",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10)).pack(pady=20)
    
    def _create_draft_rankings(self, parent):
        """Create draft prospect rankings"""
        rankings_frame = tk.LabelFrame(parent, text="Draft Prospect Rankings",
                                     bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                     font=(self.parent.FONT_FAMILY, 11, "bold"))
        rankings_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        
        # Create treeview for draft prospects
        draft_cols = ('Rank', 'Name', 'Position', 'Age', 'Overall', 'Potential', 'Grade')
        self.draft_tree = ttk.Treeview(rankings_frame, columns=draft_cols, show='headings', height=15)
        
        # Configure columns
        for col in draft_cols:
            self.draft_tree.heading(col, text=col)
            
        # Set column widths
        col_widths = {'Rank': 50, 'Name': 150, 'Position': 80, 'Age': 50, 'Overall': 70, 'Potential': 80, 'Grade': 60}
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
        """Handle double-click on draft prospect"""
        selection = self.draft_tree.selection()
        if selection:
            item = self.draft_tree.item(selection[0])
            player_name = item['values'][1]
            messagebox.showinfo("Prospect Details", f"Detailed prospect report for {player_name} would open here.")
    
    def _create_assignment_interface(self, parent):
        """Create assignment management interface"""
        main_frame = tk.Frame(parent, bg=self.parent.CONTENT_BG)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header
        header_frame = tk.Frame(main_frame, bg=self.parent.CONTENT_BG)
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_label = tk.Label(header_frame, text="Scouting Assignments",
                              font=(self.parent.FONT_FAMILY, 16, "bold"),
                              bg=self.parent.CONTENT_BG, fg=self.parent.HEADER_COLOR)
        title_label.pack(side='left')
        
        # Action buttons
        btn_frame = tk.Frame(header_frame, bg=self.parent.CONTENT_BG)
        btn_frame.pack(side='right')
        
        new_assignment_btn = tk.Button(btn_frame, text="+ New Assignment",
                                      bg=self.parent.ACCENT_COLOR, fg='white',
                                      font=(self.parent.FONT_FAMILY, 10, "bold"),
                                      command=self._create_new_assignment)
        new_assignment_btn.pack(side='left', padx=(0, 10))
        
        # Content area with two columns
        content_frame = tk.Frame(main_frame, bg=self.parent.CONTENT_BG)
        content_frame.pack(fill='both', expand=True)
        
        # Left: Current assignments
        left_frame = tk.LabelFrame(content_frame, text="Current Assignments",
                                  bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 12, "bold"))
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Assignment list
        assign_cols = ('Scout', 'Target', 'Type', 'Priority', 'Due Date', 'Status')
        self.assignments_tree = ttk.Treeview(left_frame, columns=assign_cols, show='headings', height=15)
        
        for col in assign_cols:
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=100, minwidth=80)
        
        # Populate with real game data
        self._populate_assignments()
        
        self.assignments_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Right: Assignment details
        right_frame = tk.LabelFrame(content_frame, text="Assignment Details",
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 12, "bold"))
        right_frame.pack(side='right', fill='y', padx=(10, 0))
        right_frame.configure(width=300)
        right_frame.pack_propagate(False)
        
        # Assignment type options
        type_frame = tk.Frame(right_frame, bg=self.parent.CONTENT_BG)
        type_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(type_frame, text="Assignment Type:",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10, "bold")).pack(anchor='w')
        
        assignment_types = ["Player Scouting", "Team Analysis", "League Overview", "Prospect Evaluation"]
        for atype in assignment_types:
            tk.Radiobutton(type_frame, text=atype, value=atype,
                          bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                          selectcolor=self.parent.CONTENT_BG,
                          font=(self.parent.FONT_FAMILY, 9)).pack(anchor='w', pady=2)
        
        # Priority selection
        priority_frame = tk.Frame(right_frame, bg=self.parent.CONTENT_BG)
        priority_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(priority_frame, text="Priority Level:",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10, "bold")).pack(anchor='w')
        
        priority_combo = ttk.Combobox(priority_frame, values=["Low", "Medium", "High", "Critical"],
                                     state="readonly", width=25)
        priority_combo.pack(anchor='w', pady=5)
        priority_combo.set("Medium")
        
        # Deadline
        deadline_frame = tk.Frame(right_frame, bg=self.parent.CONTENT_BG)
        deadline_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(deadline_frame, text="Deadline:",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10, "bold")).pack(anchor='w')
        
        deadline_entry = tk.Entry(deadline_frame, width=25,
                                 font=(self.parent.FONT_FAMILY, 9))
        deadline_entry.pack(anchor='w', pady=5)
        deadline_entry.insert(0, "2024-12-01")
    
    def _create_reports_interface(self, parent):
        """Create reports interface"""
        main_frame = tk.Frame(parent, bg=self.parent.CONTENT_BG)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Header
        header_frame = tk.Frame(main_frame, bg=self.parent.CONTENT_BG)
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_label = tk.Label(header_frame, text="Scouting Reports",
                              font=(self.parent.FONT_FAMILY, 16, "bold"),
                              bg=self.parent.CONTENT_BG, fg=self.parent.HEADER_COLOR)
        title_label.pack(side='left')
        
        # Filter and action buttons
        btn_frame = tk.Frame(header_frame, bg=self.parent.CONTENT_BG)
        btn_frame.pack(side='right')
        
        filter_combo = ttk.Combobox(btn_frame, values=["All Reports", "Recent", "High Priority", "My Reports"],
                                   state="readonly", width=15)
        filter_combo.pack(side='left', padx=(0, 10))
        filter_combo.set("All Reports")
        
        new_report_btn = tk.Button(btn_frame, text="+ New Report",
                                  bg=self.parent.ACCENT_COLOR, fg='white',
                                  font=(self.parent.FONT_FAMILY, 10, "bold"),
                                  command=self._create_new_report)
        new_report_btn.pack(side='left')
        
        # Main content area
        content_frame = tk.Frame(main_frame, bg=self.parent.CONTENT_BG)
        content_frame.pack(fill='both', expand=True)
        
        # Left: Reports list
        left_frame = tk.LabelFrame(content_frame, text="Available Reports",
                                  bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 12, "bold"))
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
                                   bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                   font=(self.parent.FONT_FAMILY, 12, "bold"))
        right_frame.pack(side='right', fill='y', padx=(10, 0))
        right_frame.configure(width=350)
        right_frame.pack_propagate(False)
        
        # Report content area
        self.report_details_frame = tk.Frame(right_frame, bg=self.parent.CONTENT_BG)
        self.report_details_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Default report view
        self._show_default_report_view()
        
    def _show_default_report_view(self):
        """Show default report view when no report is selected"""
        for widget in self.report_details_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.report_details_frame, text="Select a report to view details",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 11, "italic")).pack(expand=True)
        
    def _on_report_select(self, event):
        """Handle report selection"""
        selection = self.reports_tree.selection()
        if not selection:
            self._show_default_report_view()
            return
        
        item = self.reports_tree.item(selection[0])
        values = item['values']
        
        # Clear previous content
        for widget in self.report_details_frame.winfo_children():
            widget.destroy()
        
        # Show report details
        player_name = values[0]
        scout_name = values[1]
        report_date = values[2]
        report_grade = values[4]
        
        # Player info
        tk.Label(self.report_details_frame, text=f"Player: {player_name}",
                bg=self.parent.CONTENT_BG, fg=self.parent.HEADER_COLOR,
                font=(self.parent.FONT_FAMILY, 12, "bold")).pack(anchor='w', pady=(0, 5))
        
        tk.Label(self.report_details_frame, text=f"Scout: {scout_name}",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w')
        
        tk.Label(self.report_details_frame, text=f"Date: {report_date}",
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                font=(self.parent.FONT_FAMILY, 10)).pack(anchor='w')
        
        tk.Label(self.report_details_frame, text=f"Grade: {report_grade}",
                bg=self.parent.CONTENT_BG, fg=self.parent.ACCENT_COLOR,
                font=(self.parent.FONT_FAMILY, 11, "bold")).pack(anchor='w', pady=(5, 10))
        
        # Report content
        report_text = tk.Text(self.report_details_frame, height=12, width=35,
                             bg=self.parent.BG_COLOR, fg=self.parent.TEXT_COLOR,
                             font=(self.parent.FONT_FAMILY, 9), wrap='word')
        report_text.pack(fill='both', expand=True)
        
        # Generate dynamic report content based on actual player data
        report_content = self._generate_report_content(player_name, report_grade)
        
        report_text.insert('1.0', report_content)
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
                if hasattr(target_player, 'strength') and target_player.strength < 12:
                    weaknesses.append("Needs to add physical strength")
                if hasattr(target_player, 'discipline') and target_player.discipline < 12:
                    weaknesses.append("Occasional discipline issues")
                if hasattr(target_player, 'consistency') and getattr(target_player, 'consistency', 10) < 12:
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
        """Populate draft prospects data"""
        try:
            all_players = self.game_data.get('players', [])
            
            # Filter for draft-eligible players (typically ages 17-20)
            draft_prospects = []
            for player in all_players:
                age = getattr(player, 'age', 25)
                if 17 <= age <= 20:
                    draft_prospects.append(player)
            
            # Sort by overall rating (descending)
            draft_prospects.sort(key=lambda p: getattr(p, 'overall_rating', lambda: 50)(), reverse=True)
            
            # Clear existing data
            if hasattr(self, 'draft_tree'):
                self.draft_tree.delete(*self.draft_tree.get_children())
            
            # Populate draft tree if it exists
            if hasattr(self, 'draft_tree'):
                for i, prospect in enumerate(draft_prospects[:100]):  # Top 100 prospects
                    name = getattr(prospect, 'full_name', f"{prospect.first_name} {prospect.last_name}")
                    position = getattr(prospect, 'primary_position', 'Unknown')
                    age = getattr(prospect, 'age', 'Unknown')
                    overall = getattr(prospect, 'overall_rating', lambda: 'Unknown')()
                    potential = getattr(prospect, 'potential', 'Unknown')
                    
                    # Convert position enum to string if needed
                    if hasattr(position, 'value'):
                        position = position.value
                    
                    # Grade prospects
                    if isinstance(overall, (int, float)):
                        if overall >= 39:
                            grade = "A+"
                        elif overall >= 37:
                            grade = "A"
                        elif overall >= 35:
                            grade = "A-"
                        elif overall >= 33:
                            grade = "B+"
                        elif overall >= 31:
                            grade = "B"
                        else:
                            grade = "B-"
                    else:
                        grade = "Ungraded"
                    
                    self.draft_tree.insert('', 'end', values=(
                        i + 1, name, str(position), age, overall, potential, grade
                    ))
            
            self._update_status(f"Loaded {len(draft_prospects)} draft prospects")
            
        except Exception as e:
            self._update_status(f"Error loading draft prospects: {str(e)}")
            print(f"Error in _populate_draft_prospects: {e}")
    
    def update_views(self):
        """Update all views when game data changes"""
        self.game_data = self._initialize_game_data()
        self._load_initial_data()
    
    def _create_new_assignment(self):
        """Create a new scouting assignment"""
        messagebox.showinfo("New Assignment", "Assignment creation feature would open a detailed form here.")
    
    def _create_new_report(self):
        """Create a new scouting report"""
        messagebox.showinfo("New Report", "Report creation feature would open a detailed form here.")
    
    def _populate_assignments(self):
        """Populate assignments with real game data"""
        try:
            scouts = self.game_data.get('scouts', [])
            players = self.game_data.get('players', [])
            
            # Clear existing assignments
            self.assignments_tree.delete(*self.assignments_tree.get_children())
            
            if not scouts or not players:
                return
            
            # Create realistic assignments using actual players and scouts
            assignments = []
            import random
            import datetime
            
            # Get some top players for scouting
            top_players = sorted(players, key=lambda p: getattr(p, 'overall_rating', lambda: 50)(), reverse=True)[:20]
            
            # Create assignments for top prospects
            assignment_types = ["Player", "Team", "League Overview"]
            priorities = ["High", "Medium", "Low"]
            statuses = ["Active", "Pending", "Complete"]
            
            for i in range(min(len(scouts), 8)):  # Create up to 8 assignments
                if i < len(scouts) and i < len(top_players):
                    scout = scouts[i % len(scouts)]
                    player = top_players[i]
                    
                    scout_name = getattr(scout, 'full_name', f"{scout.first_name} {scout.last_name}")
                    player_name = getattr(player, 'full_name', f"{player.first_name} {player.last_name}")
                    
                    # Create due date 2-4 weeks from now
                    today = datetime.date.today()
                    due_date = today + datetime.timedelta(days=random.randint(14, 28))
                    
                    assignment = (
                        scout_name,
                        player_name,
                        random.choice(assignment_types),
                        random.choice(priorities),
                        due_date.strftime("%Y-%m-%d"),
                        random.choice(statuses)
                    )
                    assignments.append(assignment)
            
            # Add assignments to tree
            for assignment in assignments:
                self.assignments_tree.insert('', 'end', values=assignment)
                
        except Exception as e:
            print(f"Error populating assignments: {e}")
    
    def _populate_reports(self):
        """Populate reports with real game data"""
        try:
            scouts = self.game_data.get('scouts', [])
            players = self.game_data.get('players', [])
            
            # Clear existing reports
            self.reports_tree.delete(*self.reports_tree.get_children())
            
            if not scouts or not players:
                return
            
            # Create realistic reports using actual players and scouts
            reports = []
            import random
            import datetime
            
            # Get a variety of players for reports
            all_players = players[:50] if len(players) > 50 else players
            
            # Create reports for various players
            report_types = ["Player", "Team"]
            grades = ["A+", "A", "A-", "B+", "B", "B-", "C+"]
            statuses = ["Complete", "In Progress", "Draft"]
            
            for i in range(min(len(scouts) * 2, 15)):  # Create multiple reports per scout
                if scouts and all_players:
                    scout = random.choice(scouts)
                    player = random.choice(all_players)
                    
                    scout_name = getattr(scout, 'full_name', f"{scout.first_name} {scout.last_name}")
                    player_name = getattr(player, 'full_name', f"{player.first_name} {player.last_name}")
                    
                    # Create report date in the past 30 days
                    today = datetime.date.today()
                    report_date = today - datetime.timedelta(days=random.randint(1, 30))
                    
                    # Grade based on player's overall rating
                    overall = getattr(player, 'overall_rating', lambda: random.randint(50, 85))()
                    if isinstance(overall, (int, float)):
                        if overall >= 39:
                            grade = "A+"
                        elif overall >= 37:
                            grade = "A"
                        elif overall >= 35:
                            grade = "A-"
                        elif overall >= 33:
                            grade = "B+"
                        elif overall >= 31:
                            grade = "B"
                        else:
                            grade = "B-"
                    else:
                        grade = random.choice(grades)
                    
                    report = (
                        player_name,
                        scout_name,
                        report_date.strftime("%Y-%m-%d"),
                        random.choice(report_types),
                        grade,
                        random.choice(statuses)
                    )
                    reports.append(report)
            
            # Sort reports by date (newest first)
            reports.sort(key=lambda x: x[2], reverse=True)
            
            # Add reports to tree
            for report in reports:
                self.reports_tree.insert('', 'end', values=report)
                
        except Exception as e:
            print(f"Error populating reports: {e}")
